"""Tests for scripts/validate_ground_truth.py (ground_truth.csv quality gate)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.validate_ground_truth import (
    validate_counted_pax,
    validate_pct_format,
    validate_rows,
    validate_sched_times,
    validate_trip_id_format,
    validate_trip_id_presence,
    validate_ts,
    validate_vehicle_id,
)

GT_CSV = Path(__file__).resolve().parents[1] / "app" / "data" / "ground_truth.csv"


def _row(
    sched="12:08:00",
    ts="2026-08-18 12:00:00",
    trip="T1",
    loc="Test St",
    pct="20",
    pax="12",
    vid="3289",
):
    return {
        "ts": ts,
        "vehicle_id": vid,
        "trip_id": trip,
        "location": loc,
        "reported_pct": pct,
        "counted_pax": pax,
        "sched_time": sched,
    }


# ---- sched_time ----


def test_all_valid_rows_pass():
    rows = [
        _row(sched="12:08:00"),
        _row(sched="18:06:00"),
        _row(sched="25:10:00"),  # GTFS permits >24h for post-midnight service
        _row(sched="9:05:00"),  # 1-digit hour is fine
    ]
    assert validate_sched_times(rows) == []


def test_missing_sched_time_flagged():
    problems = validate_sched_times(
        [_row(sched=""), _row(sched=None), _row(sched="   ")]
    )
    assert len(problems) == 3
    assert all("missing sched_time" in p for p in problems)


def test_malformed_sched_time_flagged():
    for bad in ("12:30", "12:30:00:00", "abc", "30:00:00"):
        problems = validate_sched_times([_row(sched=bad)])
        assert len(problems) == 1, bad
        assert "sched_time" in problems[0], bad


def test_out_of_range_parts_flagged():
    for bad in ("12:60:00", "12:00:61", "30:00:00"):
        problems = validate_sched_times([_row(sched=bad)])
        assert len(problems) == 1, bad


def test_hour_29_accepted():
    # GTFS permits 24-26:xx for post-midnight service; 29 stays in range.
    assert validate_sched_times([_row(sched="29:59:59")]) == []


def test_row_numbers_include_header():
    problems = validate_sched_times(
        [_row(sched="12:00:00"), _row(sched=""), _row(sched="13:00:00")]
    )
    assert len(problems) == 1
    assert problems[0].startswith("row 3")


# ---- ts ----


def test_valid_ts_pass():
    assert validate_ts([_row(ts="2026-08-18 12:00:00")]) == []


def test_malformed_ts_flagged():
    for bad in ("", "2026-08-18", "2026-8-18 12:00:00", "2026-08-18 12:00", "12:00:00"):
        problems = validate_ts([_row(ts=bad)])
        assert len(problems) == 1, bad
        assert "ts" in problems[0], bad


def test_impossible_ts_flagged():
    for bad in ("2026-13-01 12:00:00", "2026-02-30 12:00:00", "2026-08-18 25:00:00"):
        problems = validate_ts([_row(ts=bad)])
        assert len(problems) == 1, bad
        assert "impossible ts" in problems[0], bad


# ---- trip_id ----


def test_trip_id_required_when_location_present():
    assert validate_trip_id_presence([_row(trip="T1")]) == []
    # empty, missing, and whitespace-only trip_id are all flagged
    problems = validate_trip_id_presence(
        [_row(trip=""), _row(trip=None), _row(trip="   ")]
    )
    assert len(problems) == 3
    assert all("location without trip_id" in p for p in problems)


def test_trip_id_not_required_without_location():
    assert validate_trip_id_presence([_row(trip="", loc="")]) == []


# ---- vehicle_id / trip_id / reported_pct canonical format ----


def test_trip_id_canonical_pass():
    assert validate_trip_id_format([_row(trip="30310713"), _row(trip="7")]) == []


def test_trip_id_float_formatted_flagged():
    problems = validate_trip_id_format([_row(trip="30310713.0")])
    assert len(problems) == 1
    assert "float-formatted trip_id" in problems[0]
    assert "'30310713.0'" in problems[0]


def test_trip_id_blank_not_flagged():
    # presence is validate_trip_id_presence's job; format check only fires on
    # values that exist
    assert validate_trip_id_format([_row(trip=""), _row(trip=None)]) == []


def test_vehicle_id_canonical_pass():
    assert validate_vehicle_id([_row(vid="3289"), _row(vid="7")]) == []


def test_vehicle_id_float_formatted_flagged():
    problems = validate_vehicle_id([_row(vid="3289.0")])
    assert len(problems) == 1
    assert "float-formatted vehicle_id" in problems[0]
    assert "'3289.0'" in problems[0]


def test_vehicle_id_blank_not_flagged():
    assert validate_vehicle_id([_row(vid=""), _row(vid=None), _row(vid="   ")]) == []


def test_pct_canonical_pass():
    assert validate_pct_format([_row(pct="20"), _row(pct="80")]) == []


def test_pct_float_formatted_flagged():
    problems = validate_pct_format([_row(pct="20.0")])
    assert len(problems) == 1
    assert "float-formatted reported_pct" in problems[0]
    assert "'20.0'" in problems[0]


def test_pct_blank_not_flagged():
    assert validate_pct_format([_row(pct=""), _row(pct=None)]) == []


def test_live_ground_truth_canonical_formats():
    """Regression gate: canonical vehicle_id/trip_id/pct formats on the live
    file."""
    with open(GT_CSV, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert validate_vehicle_id(rows) == []
    assert validate_trip_id_format(rows) == []
    assert validate_pct_format(rows) == []


# ---- counted_pax ----


def test_counted_pax_required_and_numeric_with_sensor():
    problems = validate_counted_pax([_row(pct="40", pax="")])
    assert len(problems) == 1
    assert "reported_pct without counted_pax" in problems[0]
    for bad in ("abc", "-1", "nan", "1,000"):
        problems = validate_counted_pax([_row(pct="40", pax=bad)])
        assert len(problems) == 1, bad
        assert "counted_pax" in problems[0], bad


def test_counted_pax_not_required_without_sensor():
    assert validate_counted_pax([_row(pct="", pax=""), _row(pct=None, pax=None)]) == []


# ---- live gate ----


def test_live_ground_truth_valid():
    """Regression gate: ride logs must not regress ts/sched_time/trip_id/counts."""
    with open(GT_CSV, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    problems = validate_rows(rows)
    assert not problems, (
        "ground_truth.csv has invalid rows - fill sched_time via "
        "`python scripts/backfill_ground_truth_sched.py` and re-check:\n"
        + "\n".join(problems[:20])
    )
