import numpy as np
import pandas as pd
import pytest

from scripts.just_miss_detector import (
    build_table,
    exit_corridor_analysis,
    load_boardings,
    pair_stats,
)


def _pair_arrays():
    # A departs 7:00, 7:20, 7:40; B departs 7:10 and 8:00.
    a = np.array([7 * 3600, 7 * 3600 + 1200, 7 * 3600 + 2400], dtype=float)
    b = np.array([7 * 3600 + 600, 8 * 3600], dtype=float)
    return a, b


def test_pair_stats_misses_and_conversions():
    a, b = _pair_arrays()
    out = pair_stats(a, b, buffer_s=120, horizon_s=15 * 60, shifts_min=(3, 5, 8))
    # A@7:00 -> B@7:10 wait = 8 min <= 15: catch.
    # A@7:20 -> B@8:00 wait = 38 min: miss, over = 38-15 = 23 -> no shift fixes.
    # A@7:40 -> B@8:00 wait = 18 min: miss, over = 3 -> 3', 5', 8' all convert.
    assert out["n_a_departures"] == 3
    assert out["catches"] == 1
    assert out["misses"] == 2
    assert out["misses_no_b"] == 0
    assert out["catches_shift_3min"] == 1
    assert out["catches_shift_5min"] == 1
    assert out["catches_shift_8min"] == 1
    assert out["best_shift_min"] == 3
    # Median miss wait in MINUTES (18, 38 -> 28.0), not seconds.
    assert out["median_miss_wait_min"] == 28.0


def test_pair_stats_no_b_tracked_separately():
    _, b = _pair_arrays()
    # A departs at 9:00, long after B's last departure: unfixable, excluded
    # from miss share and medians.
    out = pair_stats(
        np.array([9 * 3600], dtype=float),
        b,
        buffer_s=120,
        horizon_s=15 * 60,
        shifts_min=(3,),
    )
    assert out["misses_no_b"] == 1
    assert out["misses"] == 0
    assert out["miss_share"] == 0.0
    assert out["median_miss_wait_min"] is None


def test_pair_stats_median_wait_in_minutes_not_seconds():
    # Single miss with a 20-min wait must report 20.0 minutes.
    a = np.array([6 * 3600], dtype=float)
    b = np.array([6 * 3600 + 22 * 60], dtype=float)  # 22 min later
    out = pair_stats(a, b, buffer_s=120, horizon_s=15 * 60, shifts_min=(3, 5, 8))
    assert out["misses"] == 1
    assert out["median_miss_wait_min"] == 20.0


def _events():
    # Two platforms; routes A and B on both, C only on p2.
    return pd.DataFrame(
        {
            "route": ["A", "B", "A", "B", "C"],
            "dep_sec": [25200, 25800, 27600, 27000, 26000],
            "platform": ["p1", "p1", "p2", "p2", "p2"],
        }
    )


def test_build_table_pools_platforms_by_default():
    df = build_table(_events(), buffer_min=2.0, horizon_min=15.0, shifts_min=(3,))
    # Pooled: every ordered pair of A/B/C exists exactly once.
    pairs = set(zip(df.from_route, df.to_route))
    assert ("A", "B") in pairs and ("B", "A") in pairs
    assert ("A", "C") in pairs and ("C", "B") in pairs
    assert (df.platform == "pooled").all()
    assert len(df) == 6


def test_build_table_no_pool_keeps_platforms_separate():
    df = build_table(
        _events(), buffer_min=2.0, horizon_min=15.0, shifts_min=(3,), pool=False
    )
    assert set(df.platform) == {"p1", "p2"}
    # p1 hosts only A and B: every p1 pairing stays within {A, B}.
    p1 = df[df.platform == "p1"]
    assert set(p1.from_route) <= {"A", "B"} and set(p1.to_route) <= {"A", "B"}
    # C pairings exist only on p2, where C actually calls.
    c_rows = df[(df.from_route == "C") | (df.to_route == "C")]
    assert (c_rows.platform == "p2").all()


def test_build_table_platform_filter():
    df = build_table(
        _events(), buffer_min=2.0, horizon_min=15.0, shifts_min=(3,), platform="p1"
    )
    assert set(df.platform) == {"p1"}
    assert set(df.from_route) == {"A", "B"}


def test_load_boardings_period_schema(tmp_path):
    p = tmp_path / "boardings_routes.csv"
    p.write_text(
        "route_short_name,period,boardings_lower_pax\n"
        "42,am_rush,100\n"
        "42,pm_rush,50.5\n"
        "43,midday,0\n",
        encoding="utf-8",
    )
    out = load_boardings(p)
    assert out == {"42": 150.5}


def test_load_boardings_simple_schema(tmp_path):
    p = tmp_path / "b.csv"
    p.write_text("route_short_name,boardings_per_day\n2,1000\n", encoding="utf-8")
    assert load_boardings(p) == {"2": 1000.0}


def test_load_boardings_missing_file_returns_none(tmp_path):
    assert load_boardings(tmp_path / "nope.csv") is None


@pytest.fixture
def _geo():
    # Two stops 100 m apart on the same street (1 deg lon ~ 80 km here),
    # one stop 5 km away.
    coord = pd.DataFrame(
        {
            "stop_name": ["s1", "s2", "far"],
            "stop_lat": [43.60, 43.60, 43.65],
            "stop_lon": [-79.60, -79.60125, -79.60],
        },
        index=pd.Index(["s1", "s2", "far"], name="stop_id"),
    )
    route_stops = {
        "A": {"s1"},
        "A_dup": {"s1"},  # same corridor as A
        "B": {"s2", "far"},  # half its stops near A
        "C": {"far"},  # nowhere near A
    }
    return route_stops, coord


def test_exit_corridor_analysis_regimes():
    """Three regimes: substitutes share the exit corridor; down-route
    transfers share part of it (divergence named); real terminal pairs
    share none."""
    # Terminal stem = first 4 stops; exits start at n_after 5.
    downstream_pos = {
        "A": [(f"a{i}", 5 + i) for i in range(12)],
        # B shares A's first 6 exit stops, then goes elsewhere.
        "B": [(f"a{i}", 5 + i) for i in range(6)]
        + [(f"b{i}", 5 + i) for i in range(6, 12)],
        # C shares nothing.
        "C": [(f"c{i}", 5 + i) for i in range(12)],
        # D duplicates A entirely (true substitute).
        "D": [(f"a{i}", 5 + i) for i in range(12)],
    }
    stops = {}
    for i in range(12):
        stops[f"a{i}"] = (43.60, -79.60 - i * 0.0004)  # ~35 m apart: one corridor
        stops[f"b{i}"] = (43.70, -79.70 - i * 0.0004)  # ~12 km away
        stops[f"c{i}"] = (43.80, -79.80 - i * 0.0004)
    coord2 = pd.DataFrame(
        {
            "stop_name": list(stops.keys()),
            "stop_lat": [v[0] for v in stops.values()],
            "stop_lon": [v[1] for v in stops.values()],
        },
        index=pd.Index(list(stops.keys()), name="stop_id"),
    )

    # A vs D: identical exit corridor -> substitute.
    out = exit_corridor_analysis("A", "D", downstream_pos, coord2)
    assert out["exit_ratio"] >= 0.9
    # A vs B: 6 of 12 shared -> flagged as down-route transfer, named.
    out = exit_corridor_analysis("A", "B", downstream_pos, coord2)
    assert 0.25 <= out["exit_ratio"] < 1.0
    assert out["divergence"]
    # A vs C: nothing shared -> real terminal transfer.
    out = exit_corridor_analysis("A", "C", downstream_pos, coord2)
    assert out["exit_ratio"] == 0.0
    assert out["divergence"] == ""


def test_build_table_demotes_substitute_pairs(_geo):
    coord = _geo[1]
    downstream_pos = {
        "A": [("s1", 5), ("s2", 6), ("s3", 7)],
        "B": [("s1", 5), ("s2", 6), ("s3", 7)],  # same exits -> substitute
        "C": [("far", 5), ("far2", 6)],  # elsewhere -> real transfer
    }
    events = pd.DataFrame(
        {
            "route": ["A", "B", "A", "B", "A", "C"],
            "dep_sec": [25200.0, 25800.0, 29700.0, 30600.0, 26400.0, 26000.0],
            "platform": ["p"] * 6,
        }
    )
    df = build_table(
        events,
        buffer_min=2.0,
        horizon_min=15.0,
        shifts_min=(3, 5, 8),
        stop_coord=coord,
        downstream_pos=downstream_pos,
    )
    # A<->B: substitutes in BOTH directions, penalized.
    for a, b in [("A", "B"), ("B", "A")]:
        row = df[(df.from_route == a) & (df.to_route == b)].iloc[0]
        assert row.substitute
        assert row.exit_ratio >= 0.25
        assert row.adjusted_gain <= row.conversions_per_min  # penalized
    # A->C is a real transfer: not flagged, no penalty.
    row = df[(df.from_route == "A") & (df.to_route == "C")].iloc[0]
    assert not row.substitute
    assert row.exit_ratio < 0.25
