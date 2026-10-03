"""Unit tests for ``merge_ghost_csv`` — ghost_trips.csv history preservation.

The recompute reads whatever snapshot files survive ``prune_vp_snapshots.py``
(raw vp_*.json are deleted after ~10 weeks), so a direct write would drop
older service dates from the file. ``merge_ghost_csv`` preserves history the
same way ``weekly_rollup.merge_rollup_csv`` does (fixed 2026-09-08).
"""

from pathlib import Path

import pandas as pd

from scripts.ghost_trips import merge_ghost_csv


def _fresh(dates_routes):
    rows = [
        {
            "service_date": sd,
            "route_short_name": route,
            "scheduled_trips": 10,
            "verifiable_trips": 5,
            "observed_trips": 4,
            "ghost_count": 1,
            "uncovered_trips": 1,
            "observed_not_verifiable": 0,
            "ghosts": "t1@07:00",
        }
        for sd, route in dates_routes
    ]
    return pd.DataFrame(rows)


def _write_history(path: Path, rows: list[str]) -> Path:
    header = "service_date,route_short_name,scheduled_trips,verifiable_trips,observed_trips,ghost_count,uncovered_trips,observed_not_verifiable,ghosts"
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def test_merge_preserves_dates_outside_the_fresh_cut(tmp_path):
    history = _write_history(
        tmp_path / "ghost_trips.csv",
        [
            "20260817,1,20,10,9,1,1,0,x",  # pruned-snapshot era: must survive
            "20260818,10,30,20,19,1,1,0,y",
        ],
    )
    fresh = _fresh([("20260908", "1")])
    merged = merge_ghost_csv(fresh, history)
    assert len(merged) == 3
    assert set(merged["service_date"]) == {"20260817", "20260818", "20260908"}
    # Historical rows verbatim.
    r17 = merged[merged.service_date == "20260817"].iloc[0]
    assert r17["ghost_count"] == 1
    assert r17["ghosts"] == "x"


def test_fresh_rows_replace_their_own_keys(tmp_path):
    history = _write_history(
        tmp_path / "ghost_trips.csv",
        [
            "20260908,1,20,10,9,1,1,0,old",
            "20260908,10,30,20,19,1,1,0,old2",
        ],
    )
    fresh = _fresh([("20260908", "1")])  # only route 1 recomputed
    merged = merge_ghost_csv(fresh, history)
    assert len(merged) == 2
    # Route ids come back from CSV as ints; normalize for comparison.
    route = merged["route_short_name"].astype(str)
    r1 = merged[route == "1"].iloc[0]
    assert r1["ghosts"] == "t1@07:00"  # fresh value wins
    r10 = merged[route == "10"].iloc[0]
    assert r10["ghosts"] == "old2"  # not in the fresh cut: preserved


def test_duplicate_history_keys_collapse_to_last(tmp_path):
    history = _write_history(
        tmp_path / "ghost_trips.csv",
        [
            "20260817,1,20,10,9,1,1,0,first",
            "20260817,1,25,12,11,1,1,0,second",
        ],
    )
    fresh = _fresh([("20260908", "1")])
    merged = merge_ghost_csv(fresh, history)
    r17 = merged[merged.service_date == "20260817"].iloc[0]
    assert r17["ghosts"] == "second"


def test_missing_history_degrades_to_fresh(tmp_path):
    fresh = _fresh([("20260908", "1")])
    merged = merge_ghost_csv(fresh, tmp_path / "nope.csv")
    assert len(merged) == 1


def test_corrupt_history_degrades_to_fresh(tmp_path):
    p = tmp_path / "ghost_trips.csv"
    p.write_bytes(b"\xff\xfe not a csv \x00")
    fresh = _fresh([("20260908", "1")])
    merged = merge_ghost_csv(fresh, p)
    assert len(merged) == 1


def test_output_sorted_by_date_and_route(tmp_path):
    history = _write_history(
        tmp_path / "ghost_trips.csv",
        ["20260817,10,30,20,19,1,1,0,y"],
    )
    fresh = _fresh([("20260908", "1"), ("20260908", "10")])
    merged = merge_ghost_csv(fresh, history)
    keys = list(
        zip(
            merged["service_date"].astype(str),
            merged["route_short_name"].astype(str),
        )
    )
    assert keys == [("20260817", "10"), ("20260908", "1"), ("20260908", "10")]
