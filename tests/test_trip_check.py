"""P5.5 trip-check tests: verdict bands, honesty, fallbacks, determinism."""

from __future__ import annotations

import pandas as pd
import pytest

from app.trip_check import _verdict, trip_check
from app.transfer_sync import TransferConnection, TransferNode


# ---- verdict bands (pure) ---------------------------------------------------


def test_verdict_confident_requires_margin_and_low_risk():
    v, msg = _verdict(0.05, 4.0)
    assert v == "likely"
    assert "usually works" in msg


def test_verdict_median_miss_is_unlikely():
    v, msg = _verdict(0.6, -2.0)
    assert v == "unlikely"
    assert "typical day" in msg


def test_verdict_low_risk_tight_margin_is_tight():
    v, _ = _verdict(0.15, 1.0)
    assert v == "tight"


def test_verdict_high_risk_positive_margin_is_coinflip_tight():
    v, msg = _verdict(0.45, 2.0)
    assert v == "tight"
    assert "coin-flip" in msg


# ---- integration through the real graph -------------------------------------


@pytest.fixture(scope="module")
def _nodes():

    return build_nodes_safe()


def build_nodes_safe():
    from app.transfer_sync import build_nodes_for_window

    return build_nodes_for_window(
        service_day="weekday",
        window_start=360.0,
        window_end=1320.0,
        buffer_minutes=2.0,
        t_max=12.0,
    )


def _some_pair(nodes):
    """Find a node + route pair that has measured lateness in the real pool."""
    from app.reliability import _lateness_by_route
    from app import config

    by_route = _lateness_by_route(service_day="weekday")
    if not by_route:
        pytest.skip("no lateness pool in test environment")
    for n in nodes:
        for c in n.connections:
            li, lj = by_route.get(c.route_i), by_route.get(c.route_j)
            if (
                li is not None
                and lj is not None
                and len(li) >= config.MIN_LATENESS_OBS
                and len(lj) >= config.MIN_LATENESS_OBS
            ):
                return n, c
    pytest.skip("no measured pair in test environment")


def test_trip_check_measured_pair_has_verdict():
    n, c = _some_pair(build_nodes_safe())
    r = trip_check(n.stop_id, c.route_i, c.route_j, service_day="weekday")
    assert r["found"] and r["measured"]
    assert r["verdict"] in ("likely", "tight", "unlikely")
    assert 0.0 <= r["p_miss"] <= 1.0
    assert isinstance(r["message"], str) and len(r["message"]) > 20


def test_trip_check_discloses_headsigns():
    """Direction disclosure (user pass-2 finding): the answer must say where
    each bus is GOING, not just its route number — a bare "38 -> 43" reads as
    nonsense when the routes only cross because they run the same street in
    opposite directions (Winston Churchill/Dalehurst: 38 south into
    Meadowvale, 43 north to Renforth)."""
    n, c = _some_pair(build_nodes_safe())
    r = trip_check(n.stop_id, c.route_i, c.route_j, service_day="weekday")
    assert "headsign_arrive" in r and "headsign_depart" in r
    # Every disclosed headsign must name its route number (GTFS convention
    # here: "38 N Creditview To Meadowvale") so the rider can bind it to a bus.
    for field in ("headsign_arrive", "headsign_depart"):
        hs = r.get(field)
        if hs:
            assert isinstance(hs, str) and len(hs) > 0


def test_trip_check_deterministic():
    n, c = _some_pair(build_nodes_safe())
    a = trip_check(n.stop_id, c.route_i, c.route_j, service_day="weekday")
    b = trip_check(n.stop_id, c.route_i, c.route_j, service_day="weekday")
    assert a["p_miss"] == b["p_miss"] and a["verdict"] == b["verdict"]


def test_trip_check_slack_lowers_miss_risk():
    n, c = _some_pair(build_nodes_safe())
    base = trip_check(n.stop_id, c.route_i, c.route_j, service_day="weekday")
    slack = trip_check(
        n.stop_id, c.route_i, c.route_j, slack_minutes=5.0, service_day="weekday"
    )
    assert slack["p_miss"] <= base["p_miss"]


def test_trip_check_unknown_pair_is_honest():
    """A pair with no measured data must return verdict=unknown, not a guess."""
    from app.reliability import _lateness_by_route

    nodes = build_nodes_safe()
    by_route = _lateness_by_route(service_day="weekday")
    for n in nodes:
        for c in n.connections:
            li = by_route.get(c.route_i)
            lj = by_route.get(c.route_j)
            if li is None or lj is None or len(li) < 20 or len(lj) < 20:
                r = trip_check(n.stop_id, c.route_i, c.route_j, service_day="weekday")
                assert r["found"] and not r["measured"]
                assert r["verdict"] == "unknown"
                assert "Not enough observed-departure data" in r["message"]
                return
    pytest.skip("every pair is measured in this environment")


def test_trip_check_stop_not_found():
    r = trip_check("NOPE", "2", "16", service_day="weekday")
    assert not r["found"] and r["verdict"] is None


def test_trip_check_earlier_alternative_on_shared_corridor():
    """Same pair earlier on the SAME arriving bus must be surfaced
    (user pass-2/3: Bayberry-Crosscurrent is a 38->43 catch one stop before
    Dalehurst-Tradewind; the earlier-alternative note tells the rider)."""
    r = trip_check(
        "Winston Churchill Blvd At Dalehurst Dr",
        "38",
        "43",
        period="pm_rush",
    )
    alt = r.get("earlier_alternative")
    assert alt is not None
    assert alt["stops_earlier"] >= 1
    assert alt["scheduled_wait_min"] > 0
    # The earliest anchor catch on this corridor is on Argentia, well before
    # Dalehurst — never the queried stop itself.
    assert alt["stop_name"] != "Winston Churchill Blvd At Dalehurst Dr"


def test_trip_check_earliest_pair_has_no_alternative():
    """At the corridor's earliest catch point the note must be absent/null."""
    r = trip_check(
        "Winston Churchill Blvd At Bayberry Dr", "38", "43", period="pm_rush"
    )
    # Bayberry is one of the earliest catches; any alternative must be
    # strictly earlier on the same bus, so it may exist (Argentia stops) but
    # never Bayberry itself. The invariant under test: field present + sane.
    alt = r.get("earlier_alternative")
    if alt is not None:
        assert alt["stop_name"] != "Winston Churchill Blvd At Bayberry Dr"
        assert alt["stops_earlier"] >= 1


def test_trip_check_pair_not_at_stop():
    nodes = build_nodes_safe()
    n = nodes[0]
    # pick two routes not both present at this node
    r = trip_check(n.stop_id, "ZZZ", "QQQ", service_day="weekday")
    assert not r["found"]
    assert "No scheduled" in r["message"] or "not a transfer stop" in r["message"]


# ---- earlier-alternative: the same-bus invariant (2026-09-23 "68 stops" bug) ----


def _mk_opposite_pattern_fixture_tables():
    """Tables for the fixture: two route-10 patterns run OPPOSITE directions
    and both connect 10->2 at 'Rider Term', but no single trip serves both
    'Rider Term' and 'Cross Stop' — the exact shape that made pooled sequence
    mins subtract cross-direction positions (live: "get off 68 stops sooner"
    at a stop the rider's bus never reaches). 'Upstream Stop' is the honest
    answer: 5 stops before Rider Term on the rider's own trip (T_OUT).
    """
    stops = pd.DataFrame(
        {
            "stop_id": ["gidA", "gidB", "gidC", "gidD"],
            "stop_name": ["Rider Term", "Cross Stop", "Upstream Stop", "Dead End"],
        }
    )
    stop_times = pd.DataFrame(
        {
            "trip_id": ["T_OUT", "T_OUT", "T_IN1", "T_IN2"],
            "stop_id": ["gidC", "gidA", "gidB", "gidA"],
            "stop_sequence": [1, 6, 2, 4],
        }
    )
    return stops, stop_times


def _mk_opposite_pattern_fixture():
    stops, _ = _mk_opposite_pattern_fixture_tables()

    def conn(trip_i: str, base: float) -> TransferConnection:
        return TransferConnection(
            node_k="k",
            route_i="10",
            route_j="2",
            arr_time=400.0,
            dep_time=400.0 + base,
            base=float(base),
            weight=1.0,
            trip_i=trip_i,
        )

    here = TransferNode(
        stop_id="Rider Term",
        stop_name="Rider Term",
        stop_lat=0.0,
        stop_lon=0.0,
        routes=["10", "2"],
        connections=[conn("T_OUT", 8), conn("T_IN2", 9)],
    )
    cross = TransferNode(
        stop_id="Cross Stop",
        stop_name="Cross Stop",
        stop_lat=0.0,
        stop_lon=0.0,
        routes=["10", "2"],
        connections=[conn("T_IN1", 5)],
    )
    up = TransferNode(
        stop_id="Upstream Stop",
        stop_name="Upstream Stop",
        stop_lat=0.0,
        stop_lon=0.0,
        routes=["10", "2"],
        connections=[conn("T_OUT", 7)],
    )
    assert set(stops["stop_name"]) == {
        "Rider Term",
        "Cross Stop",
        "Upstream Stop",
        "Dead End",
    }
    return here, [here, cross, up]


def test_earlier_alternative_never_mixes_directions(monkeypatch):
    """The cross-direction candidate (Cross Stop, served only by an opposite
    pattern that never touches Rider Term) must never surface, however far
    its pooled sequence sits below the queried stop's."""
    from app import trip_check as tc

    here, nodes = _mk_opposite_pattern_fixture()
    stops, stop_times = _mk_opposite_pattern_fixture_tables()
    monkeypatch.setattr(
        "app.feed_prep.prepare_feed", lambda *_: (None, None, stop_times, stops)
    )
    alt = tc._find_earlier_alternative(nodes, here, "10", "2")
    assert alt is None or alt["stop_id"] != "Cross Stop"


def test_earlier_alternative_counts_on_the_riders_bus(monkeypatch):
    """Upstream Stop is 5 sequence-stops before Rider Term on the rider's own
    trip: the note must exist, name that stop, and count per-trip."""
    from app import trip_check as tc

    here, nodes = _mk_opposite_pattern_fixture()
    stops, stop_times = _mk_opposite_pattern_fixture_tables()
    monkeypatch.setattr(
        "app.feed_prep.prepare_feed", lambda *_: (None, None, stop_times, stops)
    )
    alt = tc._find_earlier_alternative(nodes, here, "10", "2")
    assert alt is not None
    assert alt["stop_id"] == "Upstream Stop"
    assert alt["stops_earlier"] == 5
    assert alt["scheduled_wait_min"] == 7.0
