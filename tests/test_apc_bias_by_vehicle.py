import numpy as np
import pandas as pd
import pytest
from scripts.apc_bias_by_vehicle import bias_table


def _frame(rows):
    return pd.DataFrame(
        rows,
        columns=["ts", "vehicle_id", "trip_id", "route", "reported_pct", "counted_pax"],
    )


def test_flip_miss_and_floor_detection():
    ts = [f"2026-08-18 12:{m:02d}:00" for m in range(6)]
    # Vehicle 100: load moves 5->12 (no bucket change), then falls back to 4
    # while the bucket stays put; one clean flip later.
    rows = [
        [ts[0], 100, "T1", 10, 20.0, 5],
        [ts[1], 100, "T1", 10, 20.0, 12],  # +7 pax, flat bucket → conflict
        [ts[2], 100, "T1", 10, 40.0, 16],  # real up-flip
        [ts[3], 100, "T1", 10, 40.0, 15],  # small move, ignored
        [ts[4], 100, "T1", 10, 40.0, 9],  # -6 down, flat bucket → conflict
        [ts[5], 100, "T1", 10, 20.0, 4],
    ]
    tbl = bias_table(_frame(rows))
    r = tbl.iloc[0]
    assert r.vehicle_id == 100
    assert r.flip_pairs == 4  # +7, +4, -6, -5 all clear the 4-pax bar
    assert r.conflict_pairs == 2
    assert r.flip_miss_share == 0.5
    # floor (20%) seen with 12 and 5 pax: only 12 counts as floor-stuck
    assert r.floor_stuck_share == round(1 / 6, 3)


def test_widest_bucket_span_and_overlaps():
    rows = [
        ["2026-08-18 13:00:00", 200, "A", 42, 20.0, 5],
        ["2026-08-18 13:01:00", 200, "A", 42, 20.0, 14],  # span 5..14 under 20%
        ["2026-08-18 13:02:00", 200, "B", 42, 40.0, 13],  # overlaps 20% range
        ["2026-08-18 13:03:00", 200, "B", 42, 60.0, 30],
    ]
    tbl = bias_table(_frame(rows))
    r = tbl.iloc[0]
    assert r.widest_bucket_span == 9.0
    assert r.overlapping_buckets == 1
    assert r.buckets_seen == 3


def test_missing_columns_raise():
    with pytest.raises(ValueError, match="missing columns"):
        bias_table(pd.DataFrame({"ts": [], "vehicle_id": []}))


def test_sorted_by_conflicts_desc_and_multi_vehicle():
    def veh(vid, conflicts):
        rows = []
        minute = 0
        for _ in range(conflicts):
            rows.append([f"2026-08-18 14:{minute:02d}:00", vid, "T", 2, 20.0, 5])
            minute += 1
            rows.append([f"2026-08-18 14:{minute:02d}:00", vid, "T", 2, 20.0, 20])
            minute += 1
        return rows

    tbl = bias_table(_frame(veh(300, 3) + veh(400, 1)))
    assert list(tbl.vehicle_id) == [300, 400]
    assert np.all(tbl.conflict_pairs.diff().dropna() <= 0)
