"""Unit tests for ``scripts/weekly_rollup.py`` (weekly coverage + lateness +
ghost + boardings summary). Pure helpers only: row readers, per-day
summaries, and report rendering.
"""

from datetime import date

from scripts.weekly_rollup import (
    context_rows,
    merge_rollup_csv,
    _is_weekend,
    _norm_date,
    _week_span,
    boardings_summary,
    coverage_rows,
    coverage_summary,
    ghost_summary,
    lateness_summary,
    render_csv,
    render_md,
    resolve_span,
)


def test_norm_date_both_formats():
    assert _norm_date("20260818") == "2026-08-18"
    assert _norm_date("2026-08-18") == "2026-08-18"
    assert _norm_date(" 20260817 ") == "2026-08-17"


def test_week_span_monday():
    lo, hi = _week_span(date(2026, 8, 17))  # a Monday
    assert (lo, hi) == ("2026-08-17", "2026-08-23")


def test_resolve_span_keeps_current_week_when_data_present():
    # Mid-week (Wed 09-02, W36) with data in that week: keep W36.
    assert resolve_span(date(2026, 9, 2), "2026-09-02") == (
        "2026-08-31",
        "2026-09-06",
    )


def test_resolve_span_empty_new_week_carries_closing_week():
    # Monday 08-31 (W36) with last data from Sunday 08-30 (W35): the
    # day-close rollover must carry W35 so final Sunday numbers land.
    assert resolve_span(date(2026, 8, 31), "2026-08-30") == (
        "2026-08-24",
        "2026-08-30",
    )


def test_resolve_span_no_data_keeps_current_week():
    # No data anywhere: keep the naive current week (W36).
    assert resolve_span(date(2026, 8, 31), None) == (
        "2026-08-31",
        "2026-09-06",
    )


def test_resolve_span_carries_older_data_week():
    # Data two weeks back also carries that week, not an empty current one.
    assert resolve_span(date(2026, 8, 31), "2026-08-23") == (
        "2026-08-17",
        "2026-08-23",
    )


def test_coverage_rows_filters_and_normalizes_status():
    rows = [
        {
            "date": "2026-08-18",
            "scheduled": "06:00-09:00",
            "status": "completed",
            "polls_succeeded": "180",
            "polls_attempted": "180",
            "observations": "90000",
        },
        {
            "date": "2026-08-18",
            "scheduled": "09:00-15:00",
            "status": "interrupted",
            "polls_succeeded": "10",
            "polls_attempted": "12",
            "observations": "5000",
        },
        {
            "date": "2026-08-17",
            "scheduled": "06:00-09:00",
            "status": "completed",
            "polls_succeeded": "180",
            "polls_attempted": "180",
            "observations": "90000",
        },
    ]
    out = coverage_rows(rows, "2026-08-18", "2026-08-18")
    assert len(out) == 2
    # 'interrupted' is reported as partial (the window ran but was cut short).
    assert [r["status"] for r in out] == ["completed", "partial"]


def test_coverage_summary_am_polled_flag():
    rows = coverage_rows(
        [
            {
                "date": "2026-08-18",
                "scheduled": "06:00-09:00",
                "status": "completed",
                "polls_succeeded": "180",
                "polls_attempted": "180",
                "observations": "90000",
            },
            {
                "date": "2026-08-18",
                "scheduled": "15:00-19:00",
                "status": "completed",
                "polls_succeeded": "240",
                "polls_attempted": "240",
                "observations": "120000",
            },
        ],
        "2026-08-18",
        "2026-08-18",
    )
    cov = coverage_summary(rows, ("2026-08-18", "2026-08-18"))
    d = cov["days"]["2026-08-18"]
    assert d["completed"] == 2
    assert d["am_polled"] is True
    assert cov["total_windows"] == 2
    assert cov["completed_windows"] == 2


def test_coverage_rows_collapses_restarted_window():
    """A mid-window restart writes two records for one scheduled window; they
    must collapse into a single window that counts as its eventual outcome."""
    rows = [
        {
            "date": "2026-08-18",
            "scheduled": "09:00-15:00",
            "status": "interrupted",
            "polls_succeeded": "10",
            "polls_attempted": "12",
            "observations": "5000",
        },
        {
            "date": "2026-08-18",
            "scheduled": "09:00-15:00",
            "status": "completed",
            "polls_succeeded": "240",
            "polls_attempted": "240",
            "observations": "120000",
        },
    ]
    out = coverage_rows(rows, "2026-08-18", "2026-08-18")
    # One scheduled window, counted completed (it eventually finished), with
    # polls/obs summed across both run segments.
    assert len(out) == 1
    assert out[0]["status"] == "completed"
    assert out[0]["polls_succeeded"] == 250
    assert out[0]["polls_attempted"] == 252
    assert out[0]["observations"] == 125000

    cov = coverage_summary(out, ("2026-08-18", "2026-08-18"))
    assert cov["total_windows"] == 1
    assert cov["completed_windows"] == 1


def test_coverage_summary_missing_am_window():
    rows = coverage_rows(
        [
            {
                "date": "2026-08-18",
                "scheduled": "09:00-15:00",
                "status": "completed",
                "polls_succeeded": "240",
                "polls_attempted": "240",
                "observations": "120000",
            },
        ],
        "2026-08-18",
        "2026-08-18",
    )
    cov = coverage_summary(rows, ("2026-08-18", "2026-08-18"))
    d = cov["days"]["2026-08-18"]
    assert d["am_present"] is False  # no AM window recorded at all
    assert d["am_polled"] is False


def test_ghost_summary_per_day_and_worst_routes():
    rows = [
        {
            "service_date": "20260817",
            "route_short_name": "2",
            "verifiable_trips": "100",
            "observed_trips": "98",
            "ghost_count": "2",
            "uncovered_trips": "50",
            "ghosts": "a@10:00;b@10:05",
        },
        {
            "service_date": "20260817",
            "route_short_name": "109",
            "verifiable_trips": "80",
            "observed_trips": "78",
            "ghost_count": "2",
            "uncovered_trips": "40",
            "ghosts": "c@11:00;d@11:05",
        },
        {
            "service_date": "20260818",
            "route_short_name": "2",
            "verifiable_trips": "90",
            "observed_trips": "88",
            "ghost_count": "2",
            "uncovered_trips": "30",
            "ghosts": "e@09:00;f@09:05",
        },
        # Out of span (previous week): must be excluded.
        {
            "service_date": "20260810",
            "route_short_name": "2",
            "verifiable_trips": "50",
            "observed_trips": "40",
            "ghost_count": "10",
            "uncovered_trips": "10",
            "ghosts": "x@09:00",
        },
    ]
    g = ghost_summary(rows, "2026-08-17", "2026-08-23")
    assert g["per_day"]["2026-08-17"]["ghosts"] == 4
    assert g["per_day"]["2026-08-18"]["ghosts"] == 2
    assert g["total_ghosts"] == 6
    assert g["total_verifiable"] == 270
    assert g["worst_routes"][0] == ("2", 4)


def test_boardings_summary_counts_fill_status():
    rows = [
        {
            "route_short_name": "1",
            "period": "am_rush",
            "service_date": "20260817",
            "boardings_lower_pax": "100.0",
            "data_status": "observed",
        },
        {
            "route_short_name": "2",
            "period": "am_rush",
            "service_date": "20260817",
            "boardings_lower_pax": "50.0",
            "data_status": "filled",
        },
        {
            "route_short_name": "3",
            "period": "am_rush",
            "service_date": "20260818",
            "boardings_lower_pax": "0.0",
            "data_status": "insufficient",
        },
        {
            "route_short_name": "4",
            "period": "am_rush",
            "service_date": "20260818",
            "boardings_lower_pax": "25.0",
            "data_status": "observed",
        },
        {
            "route_short_name": "5",
            "period": "am_rush",
            "service_date": "20260810",
            "boardings_lower_pax": "999.0",
            "data_status": "observed",
        },
    ]
    b = boardings_summary(rows, "2026-08-17", "2026-08-23")
    assert b["per_day"]["2026-08-17"]["boardings_pax"] == 150.0
    assert b["per_day"]["2026-08-17"]["filled_cells"] == 1
    assert b["per_day"]["2026-08-18"]["insufficient_cells"] == 1
    assert b["total_pax"] == 175.0  # out-of-span 999 excluded
    assert b["status_counts"]["observed"] == 2


def test_is_weekend_classifies_sat_sun():
    assert _is_weekend("2026-08-22")  # Saturday
    assert _is_weekend("20260823")  # Sunday (compact form)
    assert not _is_weekend("2026-08-24")  # Monday
    assert not _is_weekend("garbage")


def test_lateness_summary_per_day_and_legacy(tmp_path):
    csv_path = tmp_path / "obs_lateness.csv"
    csv_path.write_text(
        "date,horizon_minutes,lateness_minutes\n"
        "2026-08-22,-1,-3.0\n"  # Sat, early
        "2026-08-22,-1,0.0\n"  # Sat, on time
        "2026-08-23,-1,-2.5\n"  # Sun, early (Sunday is in span 08-17..08-23)
        "2026-08-23,-1,1.0\n"  # Sun, on time
        "2026-08-24,-1,-4.0\n"  # Mon, early
        "2026-08-16,-1,-3.0\n"  # out of span
        ",-1,-2.0\n"  # undated legacy
        "2026-08-23,5,-2.0\n",  # horizon>0: not recorded
        encoding="utf-8",
    )
    late = lateness_summary(csv_path, "2026-08-17", "2026-08-23")
    sat = late["per_day"]["2026-08-22"]
    assert sat["n_recorded"] == 2
    assert sat["pct_early_gt2"] == 50.0
    sun = late["per_day"]["2026-08-23"]
    assert sun["n_recorded"] == 2
    assert sun["pct_early_gt2"] == 50.0
    assert "2026-08-24" not in late["per_day"]  # Monday is out of span
    assert "2026-08-16" not in late["per_day"]
    assert late["legacy_recorded"] == 1
    assert late["read_error"] is False


def test_lateness_summary_missing_file_degrades(tmp_path):
    late = lateness_summary(tmp_path / "nope.csv", "2026-08-17", "2026-08-23")
    assert late["per_day"] == {}
    assert late["read_error"] is True


def test_render_md_and_csv_include_key_numbers():
    cov_rows = coverage_rows(
        [
            {
                "date": "2026-08-17",
                "scheduled": "06:00-09:00",
                "status": "completed",
                "polls_succeeded": "180",
                "polls_attempted": "180",
                "observations": "90000",
            },
        ],
        "2026-08-17",
        "2026-08-23",
    )
    ghost_rows = [
        {
            "service_date": "20260817",
            "route_short_name": "2",
            "verifiable_trips": "100",
            "observed_trips": "98",
            "ghost_count": "2",
            "uncovered_trips": "50",
            "ghosts": "a@10:00;b@10:05",
        },
    ]
    board_rows = [
        {
            "route_short_name": "1",
            "period": "am_rush",
            "service_date": "20260817",
            "boardings_lower_pax": "100.0",
            "data_status": "filled",
        },
    ]
    span = ("2026-08-17", "2026-08-23")
    cov = coverage_summary(cov_rows, span)
    g = ghost_summary(ghost_rows, *span)
    b = boardings_summary(board_rows, *span)
    late = {
        "per_day": {},
        "legacy_recorded": 0,
        "read_error": False,
        "total_recorded": 0,
    }

    md = render_md(cov, g, b, late)
    assert "Weekly Rollup" in md
    assert "1 of 1 windows completed" in md
    assert "2 ghosts of 100 verifiable trips" in md
    assert "gap-filled from other days" in md  # the fill note appears
    assert "100 lower-bound boardings" in md

    csv_txt = render_csv(cov, g, b, late)
    assert "date,is_holiday,windows_completed" in csv_txt
    assert "n_recorded" in csv_txt and "pct_early_gt2" in csv_txt
    assert "2026-08-17,false,1,0,0,1,90000,100,2,100,1,0," in csv_txt
    # The flag comes from the feed authority, same as the API annotation.
    assert ",true," not in csv_txt  # no holidays in this synthetic span


def test_weekend_section_renders_when_weekend_data_present():
    span = ("2026-08-22", "2026-08-28")  # Sat .. Fri
    cov = coverage_summary([], span)
    ghost_rows = [
        {
            "service_date": "20260822",  # Saturday
            "route_short_name": "5",
            "verifiable_trips": "80",
            "observed_trips": "74",
            "ghost_count": "6",
            "uncovered_trips": "10",
            "ghosts": "c@10:00",
        },
        {
            "service_date": "20260824",  # Monday
            "route_short_name": "5",
            "verifiable_trips": "80",
            "observed_trips": "79",
            "ghost_count": "1",
            "uncovered_trips": "10",
            "ghosts": "d@10:00",
        },
    ]
    board_rows = [
        {
            "route_short_name": "2",
            "period": "midday",
            "service_date": "20260822",
            "boardings_lower_pax": "500.0",
            "data_status": "observed",
        },
        {
            "route_short_name": "2",
            "period": "midday",
            "service_date": "20260824",
            "boardings_lower_pax": "2000.0",
            "data_status": "observed",
        },
    ]
    late = {
        "per_day": {
            "2026-08-22": {
                "date": "2026-08-22",
                "n_recorded": 100,
                "pct_early_gt2": 12.0,
            },
            "2026-08-24": {
                "date": "2026-08-24",
                "n_recorded": 400,
                "pct_early_gt2": 30.0,
            },
        },
        "legacy_recorded": 5,
        "read_error": False,
        "total_recorded": 500,
    }
    g = ghost_summary(ghost_rows, *span)
    b = boardings_summary(board_rows, *span)
    md = render_md(cov, g, b, late)

    assert "## Weekend (Sat/Sun) measured service" in md
    assert (
        "### Lateness" in md
        and "### Ghost trips" in md
        and "### Boardings (lower bounds)" in md
    )
    # Weekend early share vs weekday comparison (12% vs 30%, weighted).
    assert "Weekend early-departure share: 12.0% vs 30.0% on weekdays" in md
    # Weekend ghost row and worst weekend routes (only the Saturday ghost counts).
    assert "2026-08-22" in md
    assert "**Worst weekend routes:** 5 (6)" in md
    # Weekend boardings total excludes the Monday row.
    assert "**500 lower-bound boardings across Sat/Sun.**" in md
    assert "**Top weekend routes:** 2 (500)" in md
    # LEGACY note surfaced.
    assert "LEGACY: 5 recorded rows carry no date" in md


def test_weekend_section_empty_for_weekday_only_span():
    span = ("2026-08-17", "2026-08-21")  # Mon .. Fri only
    cov = coverage_summary([], span)
    g = ghost_summary([], *span)
    b = boardings_summary([], *span)
    late = {
        "per_day": {},
        "legacy_recorded": 0,
        "read_error": False,
        "total_recorded": 0,
    }
    md = render_md(cov, g, b, late)
    assert "## Weekend (Sat/Sun) measured service" in md
    assert "all-week collection began 2026-08-23" in md


def test_context_rows_flags_and_render():
    rows = [
        {
            "date": "2026-09-02",
            "temp_max_c": "29.3",
            "precip_mm": "16.6",
            "holiday": "",
            "service_change": "",
            "note": "thunderstorm",
        },
        {
            "date": "2026-09-07",
            "precip_mm": "",
            "holiday": "Labour Day",
            "service_change": "Sept-7 service change",
            "note": "",
        },
        {"date": "2026-09-10", "precip_mm": "0.0"},  # in span, unflagged
        {"date": "2026-09-20", "precip_mm": "99.0"},  # out of span
    ]
    ctx = context_rows(rows, "2026-09-01", "2026-09-14")
    assert "2026-09-02" in ctx["per_day"]
    assert ctx["per_day"]["2026-09-02"]["precip_mm"] == 16.6
    assert "2026-09-20" not in ctx["per_day"]  # outside span excluded
    md = render_md(
        {"days": {}, "span": ("2026-09-01", "2026-09-14")},
        {"per_day": {}},
        {"per_day": {}},
        {"per_day": {}, "legacy_recorded": 0, "read_error": False, "total_recorded": 0},
        ctx,
    )
    assert "## Context (weather, holidays, service changes)" in md
    assert "heavy rain 16.6mm" in md
    assert "Labour Day" in md
    assert "2026-09-10" not in md  # unflagged day stays out of the section


HEADER = "date,is_holiday,windows_completed,windows_partial"


def _write_history(tmp_path, lines):
    p = tmp_path / "weekly_rollup.csv"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_merge_rollup_csv_preserves_other_weeks_and_refreshes_span(tmp_path):
    history = _write_history(
        tmp_path,
        [
            HEADER,
            "2026-08-18,false,2,0",  # pre-changeover week — must survive
            "2026-08-19,false,1,1",  # duplicate date: last occurrence wins
            "2026-08-19,false,3,0",
        ],
    )
    new = HEADER + "\n2026-09-08,false,4,0\n2026-09-09,false,5,0\n"
    merged = merge_rollup_csv(history, new)
    lines = merged.strip().splitlines()
    assert lines[0] == HEADER
    # Sorted: archived weeks first (verbatim, deduped to last occurrence),
    # then the fresh span rows.
    assert lines[1:4] == [
        "2026-08-18,false,2,0",
        "2026-08-19,false,3,0",
        "2026-09-08,false,4,0",
    ]
    assert lines[4] == "2026-09-09,false,5,0"


def test_merge_rollup_csv_new_span_dates_replace_archived_ones(tmp_path):
    history = _write_history(
        tmp_path,
        [
            HEADER,
            "2026-09-08,false,1,1",  # stale same-date row...
            "2026-09-08,true,0,0",  # ...and a duplicate of it
        ],
    )
    new = HEADER + "\n2026-09-08,false,4,0\n"
    lines = merge_rollup_csv(history, new).strip().splitlines()
    # Both stale rows for the span date are dropped; the fresh row wins.
    assert lines == [HEADER, "2026-09-08,false,4,0"]


def test_merge_rollup_csv_missing_history_degrades_to_new(tmp_path):
    new = HEADER + "\n2026-09-08,false,4,0\n"
    assert merge_rollup_csv(tmp_path / "nope.csv", new) == new


def test_merge_rollup_csv_corrupt_history_degrades_to_new(tmp_path):
    p = tmp_path / "weekly_rollup.csv"
    p.write_bytes(b"\xff\xfe not a csv \x00")
    new = HEADER + "\n2026-09-08,false,4,0\n"
    assert merge_rollup_csv(p, new) == new


def test_merge_rollup_csv_new_header_backfills_older_rows(tmp_path):
    """A column added later must not crash the merge: older rows render
    with an empty cell for it."""
    history = _write_history(
        tmp_path,
        [
            HEADER,
            "2026-08-18,false,2,0",
        ],
    )
    extended = HEADER + ",n_recorded"
    new = extended + "\n2026-09-08,false,4,0,1500\n"
    lines = merge_rollup_csv(history, new).strip().splitlines()
    assert lines[0] == extended
    assert lines[1] == "2026-08-18,false,2,0,"  # backfilled empty
    assert lines[2] == "2026-09-08,false,4,0,1500"


def test_context_absent_file_renders_nothing():
    md = render_md(
        {"days": {}, "span": ("2026-08-17", "2026-08-23")},
        {"per_day": {}},
        {"per_day": {}},
        {"per_day": {}, "legacy_recorded": 0, "read_error": False, "total_recorded": 0},
        None,
    )
    assert "## Context" not in md  # ctx=None keeps the old shape
