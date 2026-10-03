import pandas as pd
from scripts.ground_truth_insights import (
    flip_brackets,
    flip_lag_minutes,
    route_failures,
    summarize_brackets,
)


def _df(rows):
    return pd.DataFrame(
        rows,
        columns=list(rows[0].keys())
        if isinstance(rows[0], dict)
        else ["ts", "vehicle_id", "trip_id", "route", "reported_pct", "counted_pax"],
    )


def _row(ts, vid, trip, route, pct, pax):
    return {
        "ts": ts,
        "vehicle_id": vid,
        "trip_id": trip,
        "route": route,
        "reported_pct": pct,
        "counted_pax": pax,
    }


def test_flip_brackets_bounds_threshold():
    rows = [
        _row("2026-08-18 12:00:00", 100, "T1", 10, 20.0, 12),
        _row("2026-08-18 12:02:00", 100, "T1", 10, 40.0, 15),
        _row("2026-08-18 12:04:00", 100, "T1", 10, 40.0, 17),
    ]
    b = flip_brackets(_df([rows[0], rows[1], rows[2]]))
    assert len(b) == 1
    r = b.iloc[0]
    # threshold for 40% lives in (12, 15]
    assert r.last_seen_at_old == 12 and r.first_seen_at_new == 15


def test_summarize_brackets_detects_overlap_and_separation():
    sep = pd.DataFrame(
        [
            {
                "vehicle_id": 1,
                "from_bucket": 20.0,
                "to_bucket": 40.0,
                "last_seen_at_old": 8.0,
                "first_seen_at_new": 9.0,
            },
            {
                "vehicle_id": 2,
                "from_bucket": 20.0,
                "to_bucket": 40.0,
                "last_seen_at_old": 20.0,
                "first_seen_at_new": 22.0,
            },
        ]
    )
    s_sep = summarize_brackets(sep)
    assert s_sep["vehicle_pairs_compared"] == 1
    assert s_sep["vehicle_pairs_overlapping"] == 0  # thresholds differ

    ovl = pd.DataFrame(
        [
            {
                "vehicle_id": 1,
                "from_bucket": 20.0,
                "to_bucket": 40.0,
                "last_seen_at_old": 10.0,
                "first_seen_at_new": 14.0,
            },
            {
                "vehicle_id": 2,
                "from_bucket": 20.0,
                "to_bucket": 40.0,
                "last_seen_at_old": 11.0,
                "first_seen_at_new": 13.0,
            },
        ]
    )
    assert summarize_brackets(ovl)["vehicle_pairs_overlapping"] == 1


def test_flip_lag_measures_catch_up_and_never():
    rows = [
        _row("2026-08-18 12:00:00", 100, "T1", 2, 20.0, 5),
        _row("2026-08-18 12:03:00", 100, "T1", 2, 20.0, 12),  # stale event starts
        _row("2026-08-18 12:08:00", 100, "T1", 2, 40.0, 16),  # catches up after 5 min
    ]
    lag = flip_lag_minutes(_df(rows))
    assert lag["stale_events"] == 1
    assert lag["caught_up"] == 1
    assert lag["median_lag_min"] == 5.0

    never_rows = [
        _row("2026-08-18 12:00:00", 100, "T2", 2, 20.0, 5),
        _row("2026-08-18 12:03:00", 100, "T2", 2, 20.0, 12),
        _row("2026-08-18 12:06:00", 100, "T2", 2, 20.0, 20),
    ]
    lag2 = flip_lag_minutes(_df(never_rows))
    # Two qualifying moves (5->12 and 12->20), neither display catches up.
    assert lag2["stale_events"] == 2
    assert lag2["never_caught_up"] == 2
    assert lag2["caught_up"] == 0


def test_route_failures_groups_across_vehicles():
    rows = [
        _row("2026-08-18 12:00:00", 100, "T1", 10, 20.0, 5),
        _row("2026-08-18 12:01:00", 100, "T1", 10, 20.0, 12),  # miss
        _row("2026-08-18 12:00:00", 200, "T9", 10, 40.0, 30),
        _row("2026-08-18 12:01:00", 200, "T9", 10, 60.0, 34),  # clean flip
    ]
    rf = route_failures(_df(rows))
    r10 = rf[rf.route == 10].iloc[0]
    assert r10.checkins == 4
    assert r10.flip_miss_share == 0.5
