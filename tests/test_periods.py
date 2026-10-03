"""Tests for collection-period labeling (AM/PM separation in the analysis)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import period_for_epoch
from scripts.reconstruct_boardings import _trip_period

_TZ = ZoneInfo("America/Toronto")


def _epoch(hour: int, minute: int = 0) -> float:
    """Epoch for a 2026-08-17 local Toronto wall-clock time (EDT)."""
    return datetime(2026, 8, 17, hour, minute, tzinfo=_TZ).timestamp()


def test_period_for_epoch_maps_windows():
    assert period_for_epoch(_epoch(7, 30)) == "am_rush"  # 06-09
    assert period_for_epoch(_epoch(8, 59)) == "am_rush"
    assert period_for_epoch(_epoch(9, 0)) == "midday"  # 09-15, start inclusive
    assert period_for_epoch(_epoch(12, 0)) == "midday"
    assert period_for_epoch(_epoch(16, 30)) == "pm_rush"  # 15-19
    assert period_for_epoch(_epoch(18, 59)) == "pm_rush"
    assert period_for_epoch(_epoch(19, 0)) == "late_night"  # 19-02
    assert period_for_epoch(_epoch(22, 0)) == "late_night"


def test_period_for_epoch_crosses_midnight_and_off_window():
    # late_night wraps past midnight (19:00 -> 02:00).
    assert period_for_epoch(_epoch(1, 0)) == "late_night"
    # 05:00 is outside every collection window.
    assert period_for_epoch(_epoch(5, 0)) == "off"
    assert period_for_epoch(_epoch(3, 0)) == "off"


def test_trip_period_uses_last_observation_timestamp():
    obs = [
        {"ts": _epoch(16, 0)},  # pm_rush
        {"ts": _epoch(16, 20)},
        {"ts": _epoch(16, 40)},
    ]
    assert _trip_period(obs) == "pm_rush"


def test_trip_period_falls_back_to_off_without_timestamps():
    assert _trip_period([{"ts": None}, {"ts": 0}]) == "off"
    assert _trip_period([]) == "off"
