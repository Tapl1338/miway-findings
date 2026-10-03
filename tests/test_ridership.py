"""Tests for the real-APC ridership weighting (``volume_mode="ridership"``)."""

import math

import pandas as pd
import pytest
from app import config
from app.ridership import (
    direction_scale,
    estimate_ridership_volumes,
    estimated_transfer_riders,
    load_ridership,
    load_ridership_rows,
    ridership_coverage,
    route_time_scales,
)
from app.transfer_sync import TransferConnection, TransferNode


@pytest.fixture
def ridership_csv(tmp_path, monkeypatch):
    """Point the config at a tiny APC ridership CSV for the test session."""
    from app import ridership as ridership_mod

    path = tmp_path / "ridership.csv"
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "2", "9999-not-a-route"],
            "boardings": [10_000.0, 1_000.0, 100.0],
        }
    )
    df.to_csv(path, index=False)
    monkeypatch.setattr(config, "RIDERSHIP_CSV", path)
    # Disable live GTFS-RT boardings so tests use the static CSV path.
    monkeypatch.setattr(ridership_mod, "_load_live_boardings", lambda: {})
    load_ridership.cache_clear()
    load_ridership_rows.cache_clear()
    yield path
    load_ridership.cache_clear()
    load_ridership_rows.cache_clear()


def _write_boardings_daily(tmp_path, rows):
    """Write a boardings_daily.csv from list-of-dict rows, return the path."""
    import csv

    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "boardings_daily.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return path


def _rows_for(routes, days):
    """One observed row per (route, day) so the per-route average = len(days)."""
    return [
        {"route_short_name": r, "boardings_lower_pax": 10.0, "service_date": d}
        for r in routes
        for d in days
    ]


class TestLiveBoardingsDeterminism:
    """T01: boardings_daily.csv grows every window; the aggregation must be a
    pure function of the file CONTENT (order-independent), and the per-route
    average must shift when a new day is appended (the drift channel that
    moves transfer node counts 237/238/258 across identical commands)."""

    def test_order_independent(self, tmp_path, monkeypatch):
        # Shuffled input -> identical boardings: the old pattern (any order-
        # dependent accumulation) would fail this. Row order must never
        # change route weights.
        import random

        from app import ridership as ridership_mod

        base = _rows_for(["1", "2", "3"], ["20260817", "20260818", "20260819"])
        shuffled = base[:]
        random.Random(7).shuffle(shuffled)
        _write_boardings_daily(tmp_path, base)
        _write_boardings_daily(tmp_path / "shuf", shuffled)
        monkeypatch.setattr(config, "DATA_DIR", tmp_path)
        d1 = ridership_mod._load_live_boardings()
        monkeypatch.setattr(config, "DATA_DIR", tmp_path / "shuf")
        d2 = ridership_mod._load_live_boardings()
        assert {r: v["boardings"] for r, v in d1.items()} == {
            r: v["boardings"] for r, v in d2.items()
        }

    def test_growth_shifts_average(self, tmp_path, monkeypatch):
        # The T01 drift channel: appending a new collection day changes the
        # per-route average, which is exactly what moves the weight-sorted
        # connection cap (and nodes_analyzed) between regenerations.
        from app import ridership as ridership_mod

        _write_boardings_daily(
            tmp_path, _rows_for(["1", "2"], ["20260817", "20260818"])
        )
        monkeypatch.setattr(config, "DATA_DIR", tmp_path)
        avg_2day = ridership_mod._load_live_boardings()["1"]["boardings"]
        # Append a third (busier) day - the collector does this each window.
        _write_boardings_daily(
            tmp_path,
            _rows_for(["1", "2"], ["20260817", "20260818", "20260819"]),
        )
        avg_3day = ridership_mod._load_live_boardings()["1"]["boardings"]
        assert avg_2day == 10.0  # avg of 10,10
        assert avg_3day == 10.0  # avg of 10,10,10 (same values)
        # Now with a genuinely different observation on the new day:
        rows = _rows_for(["1", "2"], ["20260817", "20260818", "20260819"])
        for r in rows:
            if r["service_date"] == "20260819":
                r["boardings_lower_pax"] = 40.0
        _write_boardings_daily(tmp_path, rows)
        avg_mixed = ridership_mod._load_live_boardings()["1"]["boardings"]
        assert avg_mixed == 20.0  # (10+10+40)/3


def _nodes_with_connections() -> list[TransferNode]:
    """Synthetic transfer network: route 1 (heavy) x route 2 (light) and
    route 2 x route 9 (absent from the ridership table)."""
    node = TransferNode(
        stop_id="test-stop",
        stop_name="Test Stop",
        stop_lat=0.0,
        stop_lon=0.0,
        routes=["1", "2", "9"],
    )
    node.connections = [
        TransferConnection(
            node_k="test-stop",
            route_i="1",
            route_j="2",
            arr_time=400.0,
            dep_time=404.0,
            base=4.0,
            weight=1.0,
        ),
        TransferConnection(
            node_k="test-stop",
            route_i="2",
            route_j="9",
            arr_time=420.0,
            dep_time=424.0,
            base=4.0,
            weight=1.0,
        ),
    ]
    return [node]


def test_load_ridership_reads_csv(ridership_csv):
    boardings = load_ridership()
    assert boardings == {"1": 10_000.0, "2": 1_000.0, "9999-not-a-route": 100.0}


def test_load_ridership_empty_when_absent(tmp_path, monkeypatch):
    from app import ridership as ridership_mod

    monkeypatch.setattr(config, "RIDERSHIP_CSV", tmp_path / "missing.csv")
    monkeypatch.setattr(ridership_mod, "_load_live_boardings", lambda: {})
    load_ridership.cache_clear()
    load_ridership_rows.cache_clear()
    assert load_ridership() == {}
    assert load_ridership_rows() == {}
    load_ridership.cache_clear()
    load_ridership_rows.cache_clear()


def test_ridership_weights_prefer_real_boardings(ridership_csv):
    """Routes with real APC figures must out-weight proxied ones.

    Route 1 (10k boardings) paired with route 2 (1k) weighs sqrt(2.0*0.2) ~
    0.63, while route 2 paired with route 9 (no figure, 30-min proxy ~ 0.5)
    weighs sqrt(0.2*0.5) ~ 0.32.
    """
    nodes = _nodes_with_connections()
    headways = {"1": 15.0, "2": 30.0, "9": 30.0}
    used = estimate_ridership_volumes(nodes, headways)

    assert used  # real data was available and applied
    conns = {c.route_j: c.weight for c in nodes[0].connections}
    assert conns["2"] > 0
    assert conns["9"] > 0
    assert conns["2"] > conns["9"], (
        f"real-data pair {conns['2']} must out-weight proxied pair {conns['9']}"
    )


def test_ridership_falls_back_without_csv(tmp_path, monkeypatch):
    """No CSV -> returns empty dict and leaves weights untouched, so callers
    fall back to the frequency estimate (contract used by the engine wiring)."""
    from app import ridership as ridership_mod

    monkeypatch.setattr(config, "RIDERSHIP_CSV", tmp_path / "missing.csv")
    monkeypatch.setattr(ridership_mod, "_load_live_boardings", lambda: {})
    load_ridership.cache_clear()
    load_ridership_rows.cache_clear()
    nodes = _nodes_with_connections()
    headways = {"1": 15.0, "2": 30.0, "9": 30.0}
    used = estimate_ridership_volumes(nodes, headways)
    assert used == {}
    assert all(c.weight == 1.0 for node in nodes for c in node.connections)
    load_ridership.cache_clear()
    load_ridership_rows.cache_clear()


def test_ridership_coverage_counts_real_vs_proxied(ridership_csv):
    cov = ridership_coverage(["1", "2", "9"])
    assert cov["routes_with_data"] == 2
    assert cov["routes_proxied"] == 1
    assert cov["total_routes"] == 3
    assert cov["source"]  # the attribution string is present


def test_ridership_rows_carry_provenance(ridership_csv):
    """The row loader exposes source + is_estimate so reports can label
    real APC figures vs calibrated estimates."""
    rows = load_ridership_rows()
    assert rows["1"]["boardings"] == 10_000.0
    assert rows["1"]["is_estimate"] is False
    assert rows["1"]["source"]
    # A CSV without source/is_estimate columns defaults to published-APC.
    assert all(not v["is_estimate"] for v in rows.values())


# ---------------------------------------------------------------------------
# Window/direction-aware weighting (the feed-derived refinements)
# ---------------------------------------------------------------------------


def _trip_feed(trip_specs: list[tuple[str, str, str, float]]) -> tuple:
    """Build synthetic trips/stop_times frames.

    Each spec is (trip_id, route_short_name, direction_id, dep_min).
    """
    trips = pd.DataFrame(
        {
            "trip_id": [s[0] for s in trip_specs],
            "route_short_name": [s[1] for s in trip_specs],
            "direction_id": [s[2] for s in trip_specs],
        }
    )
    stop_times = pd.DataFrame(
        {
            "trip_id": [s[0] for s in trip_specs],
            "dep_min": [s[3] for s in trip_specs],
        }
    )
    return trips, stop_times


def _node(
    stop_id: str, stop_name: str, conns: list[TransferConnection]
) -> TransferNode:
    node = TransferNode(
        stop_id=stop_id,
        stop_name=stop_name,
        stop_lat=0.0,
        stop_lon=0.0,
        routes=sorted({c.route_i for c in conns} | {c.route_j for c in conns}),
    )
    node.connections = conns
    return node


def _conn(
    route_i: str, route_j: str, trip_i: str | None = None, trip_j: str | None = None
) -> TransferConnection:
    return TransferConnection(
        node_k="x",
        route_i=route_i,
        route_j=route_j,
        arr_time=400.0,
        dep_time=404.0,
        base=4.0,
        weight=1.0,
        trip_i=trip_i,
        trip_j=trip_j,
    )


def test_period_scaling_deemphasizes_sparse_windows(ridership_csv):
    """A route running 10% of its trips inside the window must be weighted
    a tenth as heavily as the same connection in a busy period -- floored at
    PERIOD_SHARE_FLOOR so sparse windows never zero a route out."""
    # Route 1: 10 trips, only t1 inside [360, 720) -> share 0.1 -> floored 0.15.
    # Route 2: 10 trips, 9 inside -> share 0.9.
    trips, stop_times = _trip_feed(
        [("t1", "1", "0", 400.0)]
        + [(f"t{i}", "1", "0", 800.0) for i in range(2, 11)]
        + [(f"u{i}", "2", "0", 400.0) for i in range(1, 10)]
        + [("u10", "2", "0", 800.0)]
    )
    nodes = [_node("s1", "Stop 1", [_conn("1", "2")])]
    headways = {"1": 15.0, "2": 30.0}
    estimate_ridership_volumes(
        nodes,
        headways,
        trips=trips,
        stop_times=stop_times,
        window_start=360.0,
        window_end=720.0,
    )
    w_scaled = nodes[0].connections[0].weight

    # Plain daily model (no feed): sqrt(2.0 * 0.2) ~ 0.632.
    plain = _node("s1", "Stop 1", [_conn("1", "2")])
    estimate_ridership_volumes([plain], headways)
    w_plain = plain.connections[0].weight

    # Expected: v1 = 2.0 * 0.15 = 0.3; v2 = 0.2 * 0.9 = 0.18; sqrt(0.3*0.18).
    assert w_scaled == pytest.approx(math.sqrt(0.3 * 0.18), abs=0.001)
    assert w_scaled < w_plain
    assert w_scaled > 0.0


def test_period_share_floor_keeps_sparse_route_rankable(ridership_csv):
    """A route with 1 of 40 daily trips in the window still gets the floor
    (0.15) rather than being erased, so horizon-surfaced waits stay rankable."""
    trips, stop_times = _trip_feed(
        [("t1", "1", "0", 400.0)] + [(f"t{i}", "1", "0", 1400.0) for i in range(2, 41)]
    )
    _dir_id, period_share, _dir_share = route_time_scales(
        trips, stop_times, 360.0, 720.0
    )
    assert period_share["1"] == pytest.approx(config.PERIOD_SHARE_FLOOR)


def test_whole_day_window_is_a_noop(ridership_csv):
    """A window covering the whole day leaves period shares at 1.0, so the
    weight matches the plain daily model exactly."""
    trips, stop_times = _trip_feed(
        [("t1", "1", "0", 400.0), ("t2", "1", "0", 800.0), ("u1", "2", "0", 400.0)]
    )
    nodes = [_node("s1", "Stop 1", [_conn("1", "2")])]
    headways = {"1": 15.0, "2": 30.0}
    estimate_ridership_volumes(
        nodes,
        headways,
        trips=trips,
        stop_times=stop_times,
        window_start=0.0,
        window_end=24 * 60.0,
    )
    plain = _node("s1", "Stop 1", [_conn("1", "2")])
    estimate_ridership_volumes([plain], headways)
    assert nodes[0].connections[0].weight == pytest.approx(plain.connections[0].weight)


def test_direction_split_weights_dominant_direction(ridership_csv):
    """Route boardings are bidirectional; a connection in the dominant
    direction (70% of trips) must out-weight the same pair in the minor one."""
    trips, stop_times = _trip_feed(
        [(f"t{i}", "1", "0", 400.0) for i in range(1, 8)]
        + [(f"t{i}", "1", "1", 400.0) for i in range(8, 11)]
        + [(f"u{i}", "2", "0", 400.0) for i in range(1, 6)]
        + [(f"u{i}", "2", "1", 400.0) for i in range(6, 11)]
    )
    nodes = [
        _node(
            "s1",
            "Stop 1",
            [
                _conn("1", "2", trip_i="t1", trip_j="u1"),  # dir 0 / dir 0
                _conn("1", "2", trip_i="t8", trip_j="u6"),  # dir 1 / dir 1
            ],
        )
    ]
    headways = {"1": 15.0, "2": 30.0}
    estimate_ridership_volumes(
        nodes,
        headways,
        trips=trips,
        stop_times=stop_times,
        window_start=0.0,
        window_end=1440.0,
    )
    w_dom, w_min = [c.weight for c in nodes[0].connections]
    # v1_dir0 = 2.0*0.7; v2_dir0 = 0.2*0.5; sqrt -> sqrt(1.4*0.1).
    assert w_dom == pytest.approx(math.sqrt(1.4 * 0.1), abs=0.001)
    assert w_min == pytest.approx(math.sqrt(0.6 * 0.1), abs=0.001)
    assert w_dom > w_min


def test_estimated_transfer_riders_direction_and_shared_stops():
    """The card's riders/day: geometric mean of the *directional* boardings,
    x the per-stop share, divided over the stops the pair connects at."""
    b_i, b_j = 10_000.0, 1_000.0
    full = estimated_transfer_riders(b_i, b_j, 1.0, 1.0, 1)
    assert full == pytest.approx(math.sqrt(b_i * b_j) * config.CONNECTION_RIDERSHARE)
    # Direction split halves-ish the volume; 6 shared stops -> ~1/6 per stop.
    split = estimated_transfer_riders(b_i, b_j, 0.7, 0.5, 6)
    expected = math.sqrt(b_i * 0.7 * b_j * 0.5) * config.CONNECTION_RIDERSHARE / 6
    assert split == pytest.approx(expected)
    assert split < full / 6  # direction split makes it smaller still
    # A single shared stop keeps the classic formula (no division).
    assert estimated_transfer_riders(b_i, b_j, 1.0, 1.0, 1) == full


def test_direction_scale_unknown_trip_is_noop():
    """Connections without a resolvable trip/direction are not split, so a
    fallback connection never collapses to zero."""
    dir_share = {("1", "0"): 0.7}
    assert direction_scale({}, dir_share, "1", None) == 1.0
    assert direction_scale({"t1": ""}, dir_share, "1", "t1") == 1.0
    assert direction_scale({"t1": "1"}, dir_share, "1", "t1") == 1.0
    assert direction_scale({"t1": "0"}, dir_share, "1", "t1") == 0.7


# ---------------------------------------------------------------------------
# Per-day aggregation: riders/day proxy, not per-period density
# ---------------------------------------------------------------------------


def _multi_period_rows():
    """Simulate collection windows across 15 days.

    Route '25' is observed in 2 windows/day, route '109' in 4 windows/day.
    Both have 10 observations per window.  Per-row average would give both
    10.0; per-day sum gives 25=20, 109=40 -- the correct riders/day proxy.
    """
    rows = []
    for day_offset in range(15):
        date = f"2026081{day_offset}"
        for _period in ("AM", "PM"):
            rows.append(
                {
                    "route_short_name": "25",
                    "boardings_lower_pax": 10.0,
                    "service_date": date,
                }
            )
        for _period in ("AM", "MIDDAY", "PM", "EVENING"):
            rows.append(
                {
                    "route_short_name": "109",
                    "boardings_lower_pax": 10.0,
                    "service_date": date,
                }
            )
    return rows


class TestLiveBoardingsPerDayAggregation:
    """Per-day aggregation gives a consistent riders/day figure regardless
    of how many collection windows a route appears in.

    The collector runs a few windows per day; each trip is observed at most
    once per window.  The per-period-row count reflects collection frequency,
    not service frequency.  Summing per day and averaging across days gives
    a consistent riders/day proxy that the geometric-mean weight can use.
    """

    def test_per_day_sum_not_per_row_average(self, tmp_path, monkeypatch):
        """Route observed in 2 windows/day gets 20, not 10 per-row average."""
        from app import ridership as ridership_mod

        rows = _multi_period_rows()
        _write_boardings_daily(tmp_path, rows)
        monkeypatch.setattr(config, "DATA_DIR", tmp_path)
        live = ridership_mod._load_live_boardings()
        assert live["25"]["boardings"] == pytest.approx(20.0)
        assert live["109"]["boardings"] == pytest.approx(40.0)

    def test_sparse_route_not_penalised(self, tmp_path, monkeypatch):
        """Two routes with the same total daily observations but different
        window counts get the same riders/day figure."""
        from app import ridership as ridership_mod

        rows = []
        for day_offset in range(15):
            date = f"2026081{day_offset}"
            # Route A: 1 window/day, obs=10
            rows.append(
                {
                    "route_short_name": "A",
                    "boardings_lower_pax": 10.0,
                    "service_date": date,
                }
            )
            # Route B: 4 windows/day, obs=2.5 each (same total 10/day)
            for _ in range(4):
                rows.append(
                    {
                        "route_short_name": "B",
                        "boardings_lower_pax": 2.5,
                        "service_date": date,
                    }
                )
        _write_boardings_daily(tmp_path, rows)
        monkeypatch.setattr(config, "DATA_DIR", tmp_path)
        live = ridership_mod._load_live_boardings()
        assert live["A"]["boardings"] == pytest.approx(10.0)
        assert live["B"]["boardings"] == pytest.approx(10.0)

    def test_asymmetric_days_handled(self, tmp_path, monkeypatch):
        """Different observation counts per day are averaged correctly."""
        from app import ridership as ridership_mod

        rows = [
            {
                "route_short_name": "C",
                "boardings_lower_pax": 20.0,
                "service_date": "20260817",
            },
            {
                "route_short_name": "C",
                "boardings_lower_pax": 40.0,
                "service_date": "20260818",
            },
            {
                "route_short_name": "C",
                "boardings_lower_pax": 60.0,
                "service_date": "20260819",
            },
        ]
        _write_boardings_daily(tmp_path, rows)
        monkeypatch.setattr(config, "DATA_DIR", tmp_path)
        live = ridership_mod._load_live_boardings()
        assert live["C"]["boardings"] == pytest.approx(40.0)  # (20+40+60)/3
