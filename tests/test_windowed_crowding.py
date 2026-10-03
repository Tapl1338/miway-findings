"""Tests for ``scripts/windowed_crowding.py`` — window-scoped crowding.

Covers the service-date bucketing (post-midnight polls count to the
previous day), the epoch bounds, the per-route-period aggregation with the
n_with_percentage SRO denominator, and the after-7pm hot-route rule
(pinned: mean >= 33.3, n_with_percentage >= 1000, evening/late_night).
"""

import pandas as pd
import pytest

from scripts import windowed_crowding as wc


def test_service_date_of_buckets_post_midnight_to_previous_day():
    # 2026-09-09 22:00 Toronto -> same day; 2026-09-10 01:30 -> Sept 9.
    ts_same = 1788990000  # placeholder epoch; compute real ones below
    import datetime as dt
    from zoneinfo import ZoneInfo

    tor = ZoneInfo("America/Toronto")
    evening = dt.datetime(2026, 9, 9, 22, 0, tzinfo=tor).timestamp()
    after_mid = dt.datetime(2026, 9, 10, 1, 30, tzinfo=tor).timestamp()
    noon = dt.datetime(2026, 9, 9, 12, 0, tzinfo=tor).timestamp()
    assert wc.service_date_of(evening) == "2026-09-09"
    assert wc.service_date_of(after_mid) == "2026-09-09"
    assert wc.service_date_of(noon) == "2026-09-09"
    assert ts_same != after_mid  # silence unused-var lint; real asserts above


def test_file_epoch_bounds_end_is_inclusive_spilling_past_midnight():
    lo, hi = wc.file_epoch_bounds("2026-09-08", "2026-09-09")
    import datetime as dt
    from zoneinfo import ZoneInfo

    tor = ZoneInfo("America/Toronto")
    assert lo == dt.datetime(2026, 9, 8, tzinfo=tor).timestamp()
    assert hi == dt.datetime(2026, 9, 10, tzinfo=tor).timestamp()  # end+1 midnight
    assert lo < hi


def _window_frame(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "route_short_name",
            "period",
            "occupancy_status",
            "occupancy_percentage",
            "fetched_at",
        ],
    )


def test_aggregate_window_sro_denominator_is_n_with_percentage():
    # 5 rows route X: 4 with status (2 SRO+), 3 with percentage.
    df = _window_frame(
        [
            ("X", "late_night", 3, 70.0, 1.0),
            ("X", "late_night", 1, 20.0, 1.0),
            ("X", "late_night", 4, 80.0, 1.0),
            ("X", "late_night", 2, None, 1.0),
            ("X", "late_night", None, None, 1.0),
        ]
    )
    out = wc.aggregate_window(df)
    row = out.iloc[0]
    assert int(row["n_observations"]) == 5
    assert int(row["n_with_status"]) == 4
    assert int(row["n_with_percentage"]) == 3
    assert int(row["n_sro_or_worse"]) == 2
    # SRO share divides by n_with_percentage (3), not n_observations (5).
    assert row["sro_share_pct"] == pytest.approx(66.7)
    assert row["mean_percentage"] == pytest.approx((70 + 20 + 80) / 3, abs=0.1)


def test_after7_hot_routes_applies_pinned_rule():
    idx = pd.MultiIndex.from_tuples(
        [
            ("A", "late_night"),
            ("B", "late_night"),
            ("C", "late_night"),
            ("D", "midday"),
            ("E", "late_night"),
        ],
        names=["route_short_name", "period"],
    )
    summary = pd.DataFrame(
        {
            "n_observations": [2000, 2000, 1500, 5000, 900],
            "n_with_percentage": [1500, 1500, 999, 5000, 900],
            "mean_percentage": [33.3, 33.2, 45.0, 50.0, 60.0],
        },
        index=idx,
    )
    hot = wc.after7_hot_routes(summary)
    # A: exactly at threshold, n ok -> IN. B: below mean -> out.
    # C: n_with_percentage 999 < 1000 -> out. D: midday -> out.
    # E: n too small -> out.
    assert list(hot.index.get_level_values("route_short_name")) == ["A"]
