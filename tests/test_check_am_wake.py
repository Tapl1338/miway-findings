"""Unit tests for ``scripts/check_am_wake.py`` (AM-window wake verification).

Pure helpers only: CSV row parsing and the per-day classification of whether
the 06:00-09:00 window started on time. The wake signal is ``window_start``
(when the collector entered the window), not ``first_poll_at`` (the first
*successful* poll), so a router/feed outage at the start of the window is not
misread as a late wake.
"""

from scripts.check_am_wake import _day_summary, _minutes


def test_minutes_parser():
    assert _minutes("06:00:00") == 360
    assert _minutes("14:53:10") == 893
    assert _minutes("2026-08-19 06:00:39") == 360
    assert _minutes("") is None
    assert _minutes(None) is None
    assert _minutes("bogus") is None


def _row(
    date_str,
    window_start,
    first_poll,
    polls,
    status="completed",
    polls_failed=0,
):
    return {
        "date": date_str,
        "scheduled": "06:00-09:00",
        "status": status,
        "polls_succeeded": str(polls),
        "polls_attempted": str(polls + polls_failed),
        "polls_failed": str(polls_failed),
        "window_start": window_start,
        "first_poll_at": first_poll,
        "last_poll_at": "2026-08-19 08:59:00",
    }


def test_on_time_window_entered_within_window():
    rows = [_row("2026-08-19", "2026-08-19 06:03:12", "2026-08-19 06:03:15", 178)]
    s = _day_summary(rows, "2026-08-19")
    assert s["status"] == "on_time"


def test_late_wake_window_entered_after_0620():
    rows = [_row("2026-08-19", "2026-08-19 07:12:00", "2026-08-19 07:12:03", 111)]
    s = _day_summary(rows, "2026-08-19")
    assert s["status"] == "late_wake"
    assert "72 min late" in s["detail"]


def test_router_outage_is_not_a_late_wake():
    # The 2026-08-19 signature: window entered on time (06:00:39) but the
    # first SUCCESSFUL poll was 07:22:40 after 164 failed polls (router off
    # overnight). Must still be ON TIME, with the outage called out.
    rows = [
        _row(
            "2026-08-19",
            "2026-08-19 06:00:39",
            "2026-08-19 07:22:40",
            191,
            polls_failed=164,
        )
    ]
    s = _day_summary(rows, "2026-08-19")
    assert s["status"] == "on_time"
    assert "first SUCCESS at 07:22" in s["detail"]
    assert "164 failed polls" in s["detail"]


def test_missed_zero_polls():
    rows = [_row("2026-08-19", None, None, 0, status="missed")]
    s = _day_summary(rows, "2026-08-19")
    assert s["status"] == "missed"


def test_no_am_row():
    # A PM-only day: rows exist but no 06:00-09:00 window.
    rows = [{"date": "2026-08-19", "scheduled": "15:00-19:00", "status": "completed"}]
    s = _day_summary(rows, "2026-08-19")
    assert s["status"] == "no_am_row"


def test_latest_attempt_wins_on_reentry():
    # A window re-entered after a crash: the latest attempt is the truth.
    rows = [
        _row("2026-08-19", "2026-08-19 06:00:05", None, 3, status="interrupted"),
        _row("2026-08-19", "2026-08-19 06:01:40", "2026-08-19 06:01:45", 170),
    ]
    s = _day_summary(rows, "2026-08-19")
    assert s["status"] == "on_time"
