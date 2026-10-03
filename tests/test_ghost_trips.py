"""Unit tests for ``scripts/ghost_trips.py`` (scheduled-vs-observed trips).

Pure helpers only: calendar service-day resolution, observed-trip extraction
from snapshots, and the ghost comparison. No network.
"""

import pandas as pd
from scripts.ghost_trips import (
    active_service_ids,
    build_report,
    ghost_rows,
    observed_trips,
    scheduled_trips,
)


def _calendar():
    return pd.DataFrame(
        {
            "service_id": ["wk", "sa", "hol"],
            "monday": [1, 0, 0],
            "tuesday": [1, 0, 0],
            "wednesday": [1, 0, 0],
            "thursday": [1, 0, 0],
            "friday": [1, 0, 0],
            "saturday": [0, 1, 0],
            "sunday": [0, 1, 0],
            "start_date": ["20260801", "20260801", "20260801"],
            "end_date": ["20260901", "20260901", "20260901"],
        }
    )


def test_active_service_ids_weekday_and_window():
    cal = _calendar()
    empty = pd.DataFrame()
    # Tuesday 2026-08-18: weekday services (wk) + any calendar_dates adds.
    assert active_service_ids(cal, empty, "20260818") == {"wk"}
    # Saturday 2026-08-22: saturday services.
    assert active_service_ids(cal, empty, "20260822") == {"sa"}
    # Outside the calendar window the weekday service drops out.
    assert active_service_ids(cal, empty, "20260701") == set()


def test_active_service_ids_calendar_dates_exceptions():
    cal = _calendar()
    # Holiday Tuesday: the weekday service is removed, holiday service added.
    dates = pd.DataFrame(
        {
            "service_id": ["wk", "hol"],
            "date": ["20260818", "20260818"],
            "exception_type": ["2", "1"],
        }
    )
    assert active_service_ids(cal, dates, "20260818") == {"hol"}


def test_active_service_ids_missing_calendar_returns_empty():
    empty = pd.DataFrame()
    assert active_service_ids(empty, empty, "20260818") == set()


def test_scheduled_trips_start_minutes():
    feed = {
        "trips": pd.DataFrame(
            {
                "trip_id": ["t1", "t2", "t3"],
                "route_id": ["r1", "r1", "r2"],
                "service_id": ["wk", "wk", "wk"],
            }
        ),
        "routes": pd.DataFrame(
            {
                "route_id": ["r1", "r2"],
                "route_short_name": ["1", "2"],
            }
        ),
        "stop_times": pd.DataFrame(
            {
                "trip_id": ["t1", "t1", "t2", "t3"],
                "stop_sequence": [1, 2, 1, 1],
                "departure_time": ["07:00:00", "07:15:00", "08:30:00", "24:10:00"],
            }
        ),
    }
    sched = scheduled_trips(feed, {"wk"})
    assert set(sched["trip_id"]) == {"t1", "t2", "t3"}
    start = dict(zip(sched["trip_id"], sched["start_min"]))
    assert start["t1"] == 420.0  # 07:00
    assert start["t3"] == 1450.0  # 24:10 (crosses midnight)
    dur = dict(zip(sched["trip_id"], sched["duration_min"]))
    assert dur["t1"] == 15.0  # 07:00 -> 07:15
    assert dur["t2"] == 0.0  # single observed stop -> 0, allowed
    # With an empty service set (no calendar) every trip qualifies.
    assert len(scheduled_trips(feed, set())) == 3


def test_observed_trips_returns_time_anchored_pairs():
    """Observations are (trip_id, epoch) pairs; vendor service_date ignored."""
    snapshots = [
        {
            "polls": [
                {
                    "fetched_at": 1000,
                    "buses": [
                        {"trip_id": "t1", "service_date": "20260817"},
                        {"trip_id": "t2", "service_date": "20260817"},
                        {"trip_id": "t9", "service_date": "20260817"},
                    ],
                },
                {
                    "fetched_at": 1030,
                    "buses": [{"trip_id": "t1", "service_date": "20260817"}],
                },
            ]
        },
        {
            "polls": [
                {
                    "fetched_at": 2000,
                    "buses": [{"trip_id": "t1", "service_date": "20260818"}],
                }
            ]
        },
    ]
    observations, polls, polls_wallclock = observed_trips(snapshots)
    assert sorted(observations) == [
        ("t1", 1000.0),
        ("t1", 1030.0),
        ("t1", 2000.0),
        ("t2", 1000.0),
        ("t9", 1000.0),
    ]
    # Poll timestamps are per vendor date bucket and deduped.
    assert polls["20260817"] == [1000.0, 1030.0]
    assert polls["20260818"] == [2000.0]
    # S3: wall-clock bucket labels polls by their real Toronto date.
    # Epochs 1000/1030/2000 are 1970-01-01 00:16 UTC, i.e. 1969-12-31
    # evening in Toronto (UTC-5) -- all fall on 19691231.
    assert polls_wallclock["19691231"] == [1000.0, 1030.0, 2000.0]


def _toronto_epoch(hh: int, mm: int = 0) -> float:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime(2026, 8, 17, hh, mm, tzinfo=ZoneInfo("America/Toronto")).timestamp()


def _scheduled(rows):
    """Scheduled frame helper: trip_id, route, start_min, duration_min."""
    return pd.DataFrame(
        rows,
        columns=[
            "trip_id",
            "route_short_name",
            "start_min",
            "duration_min",
        ],
    )


def test_ghost_rows_compare_scheduled_vs_observed():
    scheduled = _scheduled(
        [
            ["t1", "1", 420.0, 40.0],  # 07:00, runs 07:00-07:40
            ["t2", "1", 480.0, 40.0],  # 08:00, runs 08:00-08:40
            ["t3", "1", 540.0, 40.0],  # 09:00, runs 09:00-09:40
            ["t4", "2", 600.0, 40.0],  # 10:00, observed anyway
            ["t5", "2", 1380.0, 40.0],  # 23:00, no polls nearby
        ]
    )
    # t1 broadcast at its own start; t4 broadcast inside its span.
    observations = [
        ("t1", _toronto_epoch(7)),
        ("t4", _toronto_epoch(10, 5)),
        ("t99", _toronto_epoch(7)),  # not in schedule: ignored
    ]
    polls = {"20260817": [_toronto_epoch(7), _toronto_epoch(8)]}
    rows = ghost_rows(scheduled, observations, polls)
    assert len(rows) == 2
    by_route = {r["route_short_name"]: r for r in rows}
    r1 = by_route["1"]
    assert r1["scheduled_trips"] == 3
    assert r1["observed_trips"] == 1  # t1 ran (observed) even though verifiable
    assert r1["verifiable_trips"] == 2  # t1 (07:00), t2 (08:00)
    assert r1["ghost_count"] == 1  # t2 verifiable, never observed
    assert r1["uncovered_trips"] == 1  # t3: no polls within an hour
    assert "t2@08:00" in r1["ghosts"]
    r2 = by_route["2"]
    assert r2["ghost_count"] == 0
    assert r2["observed_trips"] == 1
    assert r2["uncovered_trips"] == 1  # t5 (23:00) uncovered


def test_ghost_rows_verifiability_uses_local_poll_times():
    """A poll within the trip's on-road span makes it verifiable."""
    scheduled = _scheduled(
        [
            ["t1", "1", 420.0, 40.0],  # 07:00, on road 06:50-07:50
            ["t2", "1", 500.0, 40.0],  # 08:20, on road 08:10-09:10
        ]
    )
    observations: list = []
    polls = {"20260817": [_toronto_epoch(7, 30)]}  # 07:30
    rows = ghost_rows(scheduled, observations, polls)
    r1 = rows[0]
    assert r1["verifiable_trips"] == 1  # t1: poll at 07:30 inside its span
    assert r1["ghost_count"] == 1
    assert r1["uncovered_trips"] == 1  # t2 starts 08:20, poll too early


def test_ghost_rows_tail_only_poll_after_gap_cannot_verify():
    """A poll in the tail-forgiveness zone (past scheduled end, within +tail)
    must NOT grant verifiability -- only a poll inside the scheduled run does.

    This is the collection-gap false-positive seen on 2026-08-22: polling
    resumed at 11:18 after a morning gap, and ~15 long trips whose scheduled
    end sat at ~11:18 were counted ghosts solely because that first poll fell
    in their tail. Such trips must fall back to ``uncovered``.
    """
    # t1 runs 10:00-11:20 (dur 80). The ONLY poll is at 11:22 -- past end
    # (11:20) but within end+tail (11:25). Old code: verifiable -> ghost.
    scheduled = _scheduled([["t1", "1", 600.0, 80.0]])  # 10:00, on road to 11:20
    observations: list = []
    polls = {"20260817": [_toronto_epoch(11, 22)]}  # 11:22, in the tail only
    r1 = ghost_rows(scheduled, observations, polls)[0]
    assert r1["verifiable_trips"] == 0
    assert r1["ghost_count"] == 0
    assert r1["uncovered_trips"] == 1

    # Sanity: a poll INSIDE the scheduled run (11:00) still makes it verifiable.
    r2 = ghost_rows(scheduled, observations, {"20260817": [_toronto_epoch(11)]})[0]
    assert r2["verifiable_trips"] == 1
    assert r2["ghost_count"] == 1


def test_ghost_rows_seen_in_tail_still_observed():
    """A bus glimpsed broadcasting past its scheduled end is still OBSERVED
    (never a ghost) even though a tail poll doesn't grant verifiability."""
    scheduled = _scheduled([["t1", "1", 600.0, 80.0]])  # 10:00-11:20
    observations = [("t1", _toronto_epoch(11, 22))]  # seen broadcasting 11:22
    polls = {"20260817": [_toronto_epoch(11, 22)]}
    r1 = ghost_rows(scheduled, observations, polls)[0]
    assert r1["verifiable_trips"] == 0
    assert r1["observed_trips"] == 1
    assert r1["ghost_count"] == 0
    assert r1["observed_not_verifiable"] == 1
    assert r1["uncovered_trips"] == 0


def test_ghost_rows_poll_too_late_cannot_verify():
    """A trip that finished before polling started is uncovered, not a ghost.

    This is the 14:05-trip / 15:00-polling-start false-positive: a poll after
    the trip's span ends cannot verify anything.
    """
    scheduled = _scheduled(
        [["t1", "1", 845.0, 45.0]]  # 14:05, on road 13:55-15:00
    )
    observations: list = []
    polls = {"20260817": [_toronto_epoch(15, 1)]}  # first poll 15:01
    rows = ghost_rows(scheduled, observations, polls)
    r1 = rows[0]
    assert r1["verifiable_trips"] == 0
    assert r1["ghost_count"] == 0
    assert r1["uncovered_trips"] == 1


def test_ghost_rows_poll_before_start_cannot_verify():
    """A trip scheduled after the last poll is uncovered, not a ghost.

    Polls at 14:26-14:34 fall within a 14:36 trip's on-road span under the
    old lead-in rule, but the trip hasn't started yet -- its bus may appear
    exactly at 14:36, after the last poll. A pre-start poll cannot prove the
    trip didn't run, so it must stay uncovered.
    """
    scheduled = _scheduled(
        [["t1", "1", 876.0, 45.0]]  # 14:36, on road 14:36-15:26
    )
    observations: list = []
    polls = {"20260817": [_toronto_epoch(14, 30), _toronto_epoch(14, 34)]}
    rows = ghost_rows(scheduled, observations, polls)
    r1 = rows[0]
    assert r1["verifiable_trips"] == 0
    assert r1["ghost_count"] == 0
    assert r1["uncovered_trips"] == 1


def test_ghost_rows_poll_at_start_verifies():
    """A poll at the scheduled start makes the trip verifiable."""
    scheduled = _scheduled(
        [["t1", "1", 876.0, 45.0]]  # 14:36, on road 14:36-15:26
    )
    observations: list = []
    polls = {"20260817": [_toronto_epoch(14, 36)]}
    rows = ghost_rows(scheduled, observations, polls)
    r1 = rows[0]
    assert r1["verifiable_trips"] == 1
    assert r1["ghost_count"] == 1
    assert r1["uncovered_trips"] == 0


def test_post_midnight_trip_matched_across_wall_clock_midnight():
    """Regression (REDFLAG 2026-08-25): vendor stamps service_date with the
    WALL-CLOCK date, so a trip scheduled 24:30 on service day D broadcasts
    after midnight carrying date D+1. Matching is by real-time window, so
    the trip must count OBSERVED on D -- never a ghost.
    """
    scheduled = _scheduled(
        [["t1", "1", 1470.0, 30.0]]  # GTFS 24:30 -> real 00:30 on Aug 18
    )
    # Bus broadcasts at 00:20 on Aug 18 (10 min before its real start),
    # tagged with the wall-clock service_date "20260818".
    observations = [("t1", _toronto_epoch(0, 20) + 86400.0)]  # Aug 18, 00:20
    polls = {
        "20260817": [_toronto_epoch(0, 20)],
        "20260818": [
            _toronto_epoch(0, 20) + 86400.0,
            _toronto_epoch(0, 40) + 86400.0,  # inside the on-road span
        ],
    }
    rows = ghost_rows(scheduled, observations, polls)
    r1 = rows[0]
    assert r1["verifiable_trips"] == 1
    assert r1["observed_trips"] == 1
    assert r1["ghost_count"] == 0


def test_ghost_rows_observed_not_verifiable_lead_grace():
    """S3: a trip seen only in the lead-grace window is observed but NOT
    verifiable -- observed may then exceed verifiable, and the report must
    explain it rather than silently showing a contradiction.
    """
    scheduled = _scheduled([["t1", "1", 420.0, 40.0]])  # 07:00-07:40
    # Broadcast at 06:30 (inside the 45-min lead grace) but the ONLY poll is
    # that 06:30 one -- nothing inside [07:00, 07:45], so not verifiable.
    observations = [("t1", _toronto_epoch(6, 30))]
    polls = {"20260817": [_toronto_epoch(6, 30)]}
    rows = ghost_rows(scheduled, observations, polls)
    r1 = rows[0]
    assert r1["observed_trips"] == 1
    assert r1["verifiable_trips"] == 0
    assert r1["observed_not_verifiable"] == 1
    assert r1["ghost_count"] == 0
    assert r1["uncovered_trips"] == 0


def test_build_report_explains_observed_above_verifiable():
    """S3: the report labels days from real wall-clock epochs and explains
    any day where observed > verifiable instead of showing a contradiction.
    """
    rows = [
        {
            "service_date": "20260817",
            "route_short_name": "1",
            "scheduled_trips": 3,
            "verifiable_trips": 2,
            "observed_trips": 3,
            "ghost_count": 0,
            "uncovered_trips": 0,
            "observed_not_verifiable": 1,
            "ghosts": "",
        }
    ]
    # Wall-clock poll bucket: 07:00 and 12:00 Toronto time on 2026-08-17.
    polls_wallclock = {"20260817": [_toronto_epoch(7), _toronto_epoch(12)]}
    report = build_report(rows, {"20260817": []}, polls_wallclock)
    assert "## 20260817 — polled 07:00–12:00 (2 polls)" in report
    assert "Observed (3) exceeds verifiable (2)" in report
    assert "lead-grace window" in report

    # No explanation line when observed <= verifiable.
    ok_rows = [
        {
            "service_date": "20260817",
            "route_short_name": "1",
            "scheduled_trips": 3,
            "verifiable_trips": 3,
            "observed_trips": 3,
            "ghost_count": 0,
            "uncovered_trips": 0,
            "observed_not_verifiable": 0,
            "ghosts": "",
        }
    ]
    ok = build_report(ok_rows, {"20260817": []}, polls_wallclock)
    assert "exceeds verifiable" not in ok


def test_observation_far_outside_window_does_not_observe():
    """A same-trip-id broadcast ~23h away must not mark the trip observed."""
    scheduled = _scheduled([["t1", "1", 420.0, 40.0]])  # 07:00-07:40
    observations = [
        ("t1", _toronto_epoch(6, 30)),  # inside lead grace: observed
    ]
    observations_far = [
        ("t1", _toronto_epoch(23, 30)),  # way outside: must NOT observe
    ]
    polls = {"20260817": [_toronto_epoch(7)]}
    rows_ok = ghost_rows(scheduled, observations, polls)
    assert rows_ok[0]["observed_trips"] == 1
    assert rows_ok[0]["ghost_count"] == 0

    rows_no = ghost_rows(scheduled, observations_far, polls)
    assert rows_no[0]["observed_trips"] == 0
    assert rows_no[0]["ghost_count"] == 1  # verifiable but unseen
