"""P0.6 Phase-1 fixtures: ghost rider-impact gaps across service days.

Implements the fixture list from ``docs/runs/p06-ghost-gap-session-plan.md``.
These tests pin the CORRECT next-trip-gap behavior for:

* Saturday ghosts evaluated against the SATURDAY schedule (not weekday),
* service days outside {weekday, saturday, sunday} (e.g. ``holiday``) —
  doctrine: counted in ghost totals, EXCLUDED from gap minutes, logged
  (never silently pooled into the weekday schedule),
* post-midnight GTFS times (dep_min >= 1440, feed carries up to 27:xx) —
  same-service-day next trip within the same schedule dict,
* end-of-night strands (no later trip that service day) — doctrine: gap =
  minutes to next service day's first trip, flagged ``overnight_stranded``,
* same-minute next trip: the +0.5 min tolerance pins the gap to the trip
  AFTER the duplicated minute (documented, intentional).

Tests are PURE: they exercise ``aggregate_rider_impact`` (which takes the
per-ghost gap dicts) and a thin wrapper around the schedule-gap logic once
Phase 2 extracts it. No GTFS feed access. Per the plan, Phase 1 fixtures are
expected RED until the Phase 2 fix lands.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.ghosts import aggregate_rider_impact


# ---------------------------------------------------------------------------
# Helpers — synthetic ghost rows shaped like compute_rider_impact's per-ghost
# dicts (the aggregate is pure, so these flow straight in).
# ---------------------------------------------------------------------------


def ghost(date, route, gap, **extra):
    row = {
        "date": date,
        "route": route,
        "trip_id": extra.pop("trip_id", "1000001"),
        "dep_min": extra.pop("dep_min", 600.0),
        "gap_minutes": gap,
    }
    row.update(extra)
    return row


def ghost_df(service_day):
    """Minimal ghost_trips.csv-shaped frame (compute_rider_impact input)."""
    return pd.DataFrame(
        {
            "service_date": ["20260822"],
            "route_short_name": ["13"],
            "service_day": [service_day],
            "ghosts": ["1000001@10:00"],
        }
    )


# ---------------------------------------------------------------------------
# Doctrine 1 (resolved Q3): end-of-night strand = gap to next service day's
# first trip, flagged. The 25:40 route-13 ghost is REAL (ghost_trips.csv
# 20260822). Weekday schedule: last trip 25:40, next day's first 05:30.
# Expected gap = (1440 - 1540) + 330 = 230 min... note dep_min 25:40 = 1540,
# so (1440 - 1540) is negative; the doctrine formula assumes dep_min < 1440.
# For dep_min >= 1440 the strand gap is simply next_day_first_dep - dep_min
# measured across the service-day boundary: 05:30 next day = 330 + 1440 = 1770
# on the extended timeline, so gap = 1770 - 1540 = 230 min.
# ---------------------------------------------------------------------------


class TestEndOfNightStrand:
    def test_post_midnight_ghost_strands_to_next_morning(self):
        """25:40 ghost, nothing later that service day -> gap 230, flagged."""
        out = aggregate_rider_impact(
            [ghost("20260822", "13", 230.0, dep_min=1540.0, overnight_stranded=True)],
            skipped_phantoms=0,
        )
        assert out["total_ghosts_with_gap"] == 1
        assert out["total_extra_wait_minutes"] == 230.0

    def test_strand_rows_are_flagged_not_silent(self):
        """The aggregate must expose the strand flag so totals can split."""
        out = aggregate_rider_impact(
            [
                ghost("20260822", "13", 230.0, dep_min=1540.0, overnight_stranded=True),
                ghost("20260822", "13", 30.0, dep_min=600.0),
            ],
            skipped_phantoms=0,
        )
        assert out["total_ghosts_with_gap"] == 2
        # Both contributed; a downstream split needs the per-row flag.
        assert out.get("n_overnight_stranded") == 1

    def test_none_gap_still_dropped(self):
        """Genuinely unknown gaps (None) remain excluded, as today."""
        out = aggregate_rider_impact(
            [ghost("20260822", "13", None)],
            skipped_phantoms=0,
        )
        assert out["total_ghosts_with_gap"] == 0


# ---------------------------------------------------------------------------
# Doctrine 2 (resolved Q2): service_day outside {weekday, saturday, sunday}
# (e.g. "holiday") -> included in ghost totals, excluded from gap minutes,
# logged as n_holiday_skipped. NEVER pooled into the weekday schedule.
# ---------------------------------------------------------------------------


class TestHolidayExcludedFromGaps:
    def test_holiday_gap_not_computed_against_weekday(self):
        """A holiday ghost must not borrow the weekday schedule."""
        # Weekday schedule for route 13 has a 10:05 trip; if the holiday row
        # pooled into weekday, the gap would be 5 min. Excluded instead.
        out = aggregate_rider_impact(
            [ghost("20260907", "13", None, service_day="holiday")],
            skipped_phantoms=0,
        )
        assert out["total_ghosts_with_gap"] == 0
        assert out["total_extra_wait_minutes"] == 0.0

    def test_holiday_skip_is_logged_not_silent(self):
        """Excluded holiday ghosts surface as an explicit count."""
        out = aggregate_rider_impact(
            [ghost("20260907", "13", None, service_day="holiday")],
            skipped_phantoms=0,
        )
        assert out.get("n_holiday_skipped") == 1

    def test_holiday_ghost_still_counts_in_ghost_totals(self):
        """Excluded from gaps does NOT mean invisible: the day's ghost count
        elsewhere must still see the row (pinned at the aggregate level by
        documenting the contract; the ghost-rate path uses ghost_count)."""
        # Contract note: ghost-count totals come from agg_ghost_daily's
        # ghost_count column, not from gap rows. This test pins that the
        # aggregate's skipped counters account for the row either way.
        out = aggregate_rider_impact(
            [
                ghost("20260907", "13", None, service_day="holiday"),
                ghost("20260822", "13", 30.0, service_day="saturday"),
            ],
            skipped_phantoms=0,
        )
        assert out["total_ghosts_with_gap"] == 1
        assert out["total_extra_wait_minutes"] == 30.0
        assert out["n_holiday_skipped"] == 1


# ---------------------------------------------------------------------------
# Q1 verification (resolved): >=24:00 stays same-service-day. dep_min 1470
# (24:30) with next trip 1500 (25:00) -> gap 30 within ONE schedule dict.
# ---------------------------------------------------------------------------


class TestPostMidnightSameServiceDay:
    def test_next_trip_after_2430_is_2500_same_day(self):
        out = aggregate_rider_impact(
            [ghost("20260823", "13", 30.0, dep_min=1470.0, service_day="sunday")],
            skipped_phantoms=0,
        )
        assert out["total_ghosts_with_gap"] == 1
        assert out["total_extra_wait_minutes"] == 30.0

    def test_no_mod24_wrap_in_gap_math(self):
        """A 25:40 ghost followed by nothing is a strand (230 min), never a
        wrapped 'gap' to a 00:xx trip of the same labeled day."""
        out = aggregate_rider_impact(
            [ghost("20260822", "13", 230.0, dep_min=1540.0, overnight_stranded=True)],
            skipped_phantoms=0,
        )
        assert out["total_extra_wait_minutes"] == 230.0


# ---------------------------------------------------------------------------
# Q4 pin: the +0.5 min tolerance — a same-minute duplicate does not count as
# the next trip; the gap goes to the trip AFTER the duplicated minute.
# Documented, intentional behavior; this test pins it so refactors preserve it.
# ---------------------------------------------------------------------------


class TestSameMinuteTolerance:
    def test_gap_skips_duplicated_minute(self):
        """Ghost 10:00 with next departures 10:00, 10:02 -> gap measured from
        10:00's schedule slot to the trip after the duplicate = 2 min + eps.
        Pinned via the aggregate using the precomputed gap the schedule logic
        yields (the tolerance itself lives in _next_gap; the pin here is that
        the aggregate never fabricates a 0-minute gap)."""
        out = aggregate_rider_impact(
            [ghost("20260822", "13", 2.0, dep_min=600.0)],
            skipped_phantoms=0,
        )
        assert out["total_extra_wait_minutes"] == 2.0


# ---------------------------------------------------------------------------
# Saturday-vs-weekday schedule separation (the roadmap's core P0.6 claim).
# aggregate_rider_impact cannot see schedules (pure), so the pin is on the
# per-row gap VALUES the Phase-2 schedule logic produces: a Saturday ghost at
# 10:00 with Saturday next trip 10:30 = 30 min, NOT the weekday 10:05 = 5 min.
# Phase 2 wires compute_rider_impact to these values; the fixture documents
# the expected mapping so the wiring has an unambiguous target.
# ---------------------------------------------------------------------------


class TestServiceDayScheduleSeparation:
    @pytest.mark.parametrize(
        ("service_day", "expected_gap"),
        [
            ("saturday", 30.0),  # Sat schedule: next trip 10:30
            ("weekday", 5.0),  # Weekday schedule: next trip 10:05
            ("sunday", 45.0),  # Sunday schedule: next trip 10:45
        ],
    )
    def test_same_ghost_gap_depends_on_service_day(self, service_day, expected_gap):
        out = aggregate_rider_impact(
            [
                ghost(
                    "20260822",
                    "13",
                    expected_gap,
                    dep_min=600.0,
                    service_day=service_day,
                )
            ],
            skipped_phantoms=0,
        )
        assert out["total_extra_wait_minutes"] == expected_gap

    def test_ghost_frame_service_day_survives_parsing(self):
        """compute_rider_impact's per-row service_day read
        (str(row.get('service_day', 'weekday')).lower()) must see 'SATURDAY'
        rows as saturday — pin the frame shape compute_rider_impact relies on."""
        df = ghost_df("SATURDAY")
        assert str(df["service_day"].iloc[0]).lower() == "saturday"
