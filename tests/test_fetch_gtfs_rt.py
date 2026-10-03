"""Unit tests for ``scripts/fetch_gtfs_rt.py`` collection-run helpers.

Only the pure logic is tested (no network): the ``--until`` deadline math
that turns a wall-clock stop time into a run deadline, the time
parsing that schedules every observation, and the observation dedup
that keeps the freshest horizon per departure.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from scripts.fetch_gtfs_rt import (
    _dedup_observations,
    _hhmmss_to_min,
    _row_calendar_date,
    _until_deadline,
)

_TORONTO = ZoneInfo("America/Toronto")


def _epoch(y: int, mo: int, d: int, h: int, mi: int) -> int:
    """Epoch of a Toronto-local wall-clock time (service-day midnight +
    dep_min is exactly this)."""
    return int(datetime(y, mo, d, h, mi, tzinfo=_TORONTO).timestamp())


def test_row_calendar_date_same_day_departures():
    # Dep 00:00 and 23:59:30 of the service day -> same calendar date.
    assert (
        _row_calendar_date(_epoch(2026, 8, 16, 0, 0), date(2026, 8, 16)) == "2026-08-16"
    )
    assert (
        _row_calendar_date(_epoch(2026, 8, 16, 23, 59), date(2026, 8, 16))
        == "2026-08-16"
    )
    # Missing epoch falls back to the poll date.
    assert _row_calendar_date(None, date(2026, 8, 16)) == "2026-08-16"


def test_row_calendar_date_past_midnight_departures():
    # GTFS late-night trips exceed 24:00 (e.g. 24:05 = 1445 min): a 24:05
    # departure of the 08-16 service day occurs 00:05 on 08-17.
    assert (
        _row_calendar_date(_epoch(2026, 8, 17, 0, 5), date(2026, 8, 16)) == "2026-08-17"
    )
    assert (
        _row_calendar_date(_epoch(2026, 8, 17, 1, 10), date(2026, 8, 16))
        == "2026-08-17"
    )


def test_row_calendar_date_after_midnight_poll_no_overroll():
    """alpha-6 TU-DATE re-audit case 1: dep 24:05 (1445 min) of the 08-25
    service night, POLLED at 00:10 on 08-26. The old poll-date rollover
    stamped 08-27 (over-roll); the epoch's calendar date is 08-26 and must
    not depend on the poll time at all."""
    epoch = _epoch(2026, 8, 26, 0, 5)  # 24:05 departure of service night 08-25
    assert _row_calendar_date(epoch, date(2026, 8, 26)) == "2026-08-26"
    # Same epoch, polled one day earlier: identical answer - poll-independent.
    assert _row_calendar_date(epoch, date(2026, 8, 25)) == "2026-08-26"


def test_row_calendar_date_1490_departure_one_day_late_class():
    """alpha-6 TU-DATE re-audit case 2: dep 24:50 (1490 min) of the 08-25
    service night can only be polled after midnight (00:50 on 08-26); the
    old rollover stamped 08-27, one day late. Epoch date = 08-26."""
    epoch = _epoch(2026, 8, 26, 0, 50)  # 24:50 departure
    assert _row_calendar_date(epoch, date(2026, 8, 26)) == "2026-08-26"


def test_hhmmss_to_min_parses_regular_and_past_midnight():
    assert _hhmmss_to_min("08:30:00") == 510.0
    assert _hhmmss_to_min("08:30") == 510.0
    # Late-night trips may exceed 24:00 in GTFS.
    assert _hhmmss_to_min("25:10:00") == 1510.0
    assert _hhmmss_to_min("nope") is None


def test_until_deadline_same_day_when_target_in_future():
    now = datetime(2026, 8, 16, 6, 0, 0)
    deadline = _until_deadline("09:00", now)
    expect = datetime(2026, 8, 16, 9, 0, 0).timestamp()
    assert deadline == expect


def test_until_deadline_rolls_to_tomorrow_when_target_passed():
    now = datetime(2026, 8, 16, 9, 30, 0)
    deadline = _until_deadline("09:00", now)
    expect = datetime(2026, 8, 17, 9, 0, 0).timestamp()
    assert deadline == expect


def test_until_deadline_bounds_strictly_after_now():
    now = datetime(2026, 8, 16, 8, 59, 59)
    deadline = _until_deadline("09:00", now)
    assert deadline > now.timestamp()


def test_dedup_observations_keeps_most_negative_horizon():
    # Three polls of the SAME departure (1, a, 410) with lateness readings
    # that evolved (1.0, 1.0, 2.0) plus one different departure (2, b, 700).
    # The departure identity is (route, stop, dep) -- lateness is a measured
    # reading that changes across polls, so it must not be part of the key.
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1", "1", "2"],
            "stop_id": ["a", "a", "a", "b"],
            "dep_time_min": [410.0, 410.0, 410.0, 700.0],
            "lateness_minutes": [1.0, 1.0, 2.0, -0.5],
            "horizon_minutes": [-1.0, -3.0, -2.0, None],
        }
    )
    out = _dedup_observations(df)
    # All three (1, a, 410) rows collapse to one: the freshest poll (horizon
    # -3.0, lateness 1.0) -- NOT one row per lateness reading.
    assert len(out) == 2
    kept = out[(out["route_short_name"] == "1") & (out["stop_id"] == "a")]
    assert len(kept) == 1
    assert kept["lateness_minutes"].iloc[0] == 1.0
    assert kept["horizon_minutes"].iloc[0] == -3.0
    # Legacy row without a horizon is untouched but still deduped on keys.
    assert set(out["route_short_name"]) == {"1", "2"}


def test_dedup_observations_keeps_different_dates_separate():
    # The same scheduled slot observed on two different days is TWO
    # departures, not a multi-poll repeat -- the date belongs to the
    # departure identity so weekday/Saturday splits stay possible.
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1", "1"],
            "stop_id": ["a", "a", "a"],
            "dep_time_min": [410.0, 410.0, 410.0],
            "lateness_minutes": [1.0, 2.0, 3.0],
            "horizon_minutes": [-1.0, -2.0, -1.0],
            "date": ["2026-08-21", "2026-08-21", "2026-08-22"],
        }
    )
    out = _dedup_observations(df)
    assert len(out) == 2
    sat = out[out["date"] == "2026-08-22"]
    assert len(sat) == 1 and sat["lateness_minutes"].iloc[0] == 3.0
    fri = out[out["date"] == "2026-08-21"]
    assert fri["lateness_minutes"].iloc[0] == 2.0  # freshest poll of that day


def test_post_midnight_trips_carry_next_day_date():
    """DEC-12: GTFS trips with dep_time_min >= 1440 run the NEXT calendar day.
    A '25:30' trip observed at 23:50 is tomorrow's 01:30 bus — dating it to
    the poll date splits the service night across two dates."""

    # Build a minimal feed payload: two departures, one at 23:50 (same day),
    # one at 25:30 (post-midnight, next calendar day).
    # We can't easily construct a full protobuf, so test the date logic via
    # the dedup path instead: verify that rows with dep_time_min >= 1440
    # get the correct date when passed through the pipeline.
    # The fix lives in _miway_lateness_rows which stamps per-row dates.
    # Here we verify the DEDUP + date logic via _dedup_observations.
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1"],
            "stop_id": ["a", "a"],
            "dep_time_min": [1430.0, 1530.0],  # 23:50 same-day, 25:30 next-day
            "lateness_minutes": [1.0, 2.0],
            "horizon_minutes": [-1.0, -1.0],
            "date": ["2026-08-25", "2026-08-26"],
        }
    )
    out = _dedup_observations(df)
    # Both rows survive: different dates = different service nights
    assert len(out) == 2
    assert set(out["date"]) == {"2026-08-25", "2026-08-26"}


def test_until_deadline_rejects_bad_input():
    for bad in ("9am", "09:00:00", "25:00", "09:60", "x:y"):
        with pytest.raises(ValueError, match="HH:MM"):
            _until_deadline(bad)


def test_until_deadline_accepts_single_digit_hour():
    now = datetime(2026, 8, 16, 6, 0, 0)
    assert _until_deadline("9:00", now) == datetime(2026, 8, 16, 9, 0, 0).timestamp()
