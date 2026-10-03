"""Unit tests for the operations router's weekly-rollup trend reader.

Exercises `_read_rollup` (the pure reader) against tmp dirs over the
`weekly_rollup.csv` shape. Collector-health behavior lives in the coverage
router's tests, so this file stays scoped to the trend history.
"""

from pathlib import Path

from app.routers import operations

_HEADER = (
    "date,windows_completed,windows_partial,windows_missed,am_polled,"
    "observations,verifiable_trips,ghost_trips,boardings_lower_pax,"
    "filled_cells,n_recorded,pct_early_gt2\n"
)
_ROWS = (
    "2026-08-28,4,3,0,1,12898641,5180,23,0,0,191774,26.62\n"
    "2026-08-29,0,3,0,0,4579570,1697,22,0,0,76454,25.25\n"
)


def _write(csv_path: Path, body: str):
    csv_path.write_text(_HEADER + body, encoding="utf-8")
    return csv_path


def test_read_rollup_missing(tmp_path):
    got = operations._read_rollup(tmp_path / "nope.csv")
    assert got == {"available": False, "file": "nope.csv", "rows": []}


def test_read_rollup_empty(tmp_path):
    got = operations._read_rollup(_write(tmp_path / "w.csv", ""))
    assert got["available"] is False
    assert got["rows"] == []


def test_read_rollup_rows_and_derived_rate(tmp_path):
    got = operations._read_rollup(_write(tmp_path / "w.csv", _ROWS))
    assert got["available"] is True
    assert got["file"] == "w.csv"
    assert got["updated_at"] is not None
    # Sorted ascending by date.
    assert [r["date"] for r in got["rows"]] == ["2026-08-28", "2026-08-29"]
    r = got["rows"][0]
    assert r["observations"] == 12898641
    assert r["ghost_trips"] == 23
    assert r["windows_completed"] == 4
    # Derived ghost rate = ghosts / verifiable * 100 (23/5180).
    assert abs(r["ghost_rate_pct"] - 0.4) < 0.1
    assert r["pct_early_gt2"] == 26.6


def test_read_rollup_zero_verifiable_ghost_rate_null(tmp_path):
    # P0.1: zero VERIFIABLE trips = unmeasurable day, not a 0.0% ghost rate.
    # A fake 0.0 read as "perfect service" and poisoned week-over-week deltas
    # (whose None handling already mirrors pct_early_gt2's).
    got = operations._read_rollup(
        _write(tmp_path / "w.csv", "2026-08-30,0,0,0,0,0,0,0,0,0,0,0.0\n")
    )
    r = got["rows"][0]
    assert r["verifiable_trips"] == 0
    assert r["ghost_rate_pct"] is None


def test_read_rollup_garbage_numeric_columns_safely(tmp_path):
    # Non-numeric cells must not blow the reader up — they coerce to 0/None.
    got = operations._read_rollup(
        _write(tmp_path / "w.csv", "2026-08-28,a,b,c,d,e,f,g,h,i,j,k\n")
    )
    r = got["rows"][0]
    assert r["observations"] == 0
    # P0.1: garbage verifiable -> 0 verifiable -> unmeasurable -> None (not 0.0).
    assert r["ghost_rate_pct"] is None
    assert r["date"] == "2026-08-28"


def test_read_rollup_null_distinct_from_zero(tmp_path):
    # The acceptance check for P0.1: null and zero must be DIFFERENT values.
    # A real zero-ghost day (verifiable > 0) reports 0.0; an unmeasurable day
    # (verifiable == 0) reports None.
    got = operations._read_rollup(
        _write(
            tmp_path / "w.csv",
            "2026-08-28,4,0,0,1,900,100,0,0,0,500,20.0\n"  # real day, 0 ghosts
            "2026-08-29,0,0,0,0,0,0,0,0,0,0,\n",  # unmeasurable day
        )
    )
    real_zero, unmeasurable = got["rows"]
    assert real_zero["ghost_rate_pct"] == 0.0
    assert unmeasurable["ghost_rate_pct"] is None


def test_endpoint_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(operations, "_ROLLUP_CSV", tmp_path / "nope.csv")
    resp = operations.operations_trends()
    assert resp == {"available": False, "file": "nope.csv", "rows": []}


def test_endpoint_reads(tmp_path, monkeypatch):
    p = _write(tmp_path / "weekly_rollup.csv", _ROWS)
    monkeypatch.setattr(operations, "_ROLLUP_CSV", p)
    resp = operations.operations_trends()
    assert resp["available"] is True
    assert len(resp["rows"]) == 2


def test_read_rollup_nan_pct_early_becomes_none(tmp_path):
    """Regression (2026-09-02, live 500): the rollup writer emits an empty
    ``pct_early_gt2`` on days whose analysis has not run yet, pandas reads that
    as a NaN float, and the reader passed it straight into the response. FastAPI
    then refused to serialize it ("Out of range float values are not JSON
    compliant: nan"), so ``GET /api/operations/trends`` 500'd and the Service
    Quality Trends section was blank. NaN must be coerced to ``None``.
    """
    body = (
        "2026-08-31,3,2,0,1,11490424,5310,27,44777,0,0,\n"
        "2026-09-01,3,2,0,1,12006275,5191,31,0,0,0,25.25\n"
    )
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    r0, r1 = got["rows"]
    # The day with an empty pct_early_gt2 must be None, never a NaN float.
    assert r0["pct_early_gt2"] is None
    assert r1["pct_early_gt2"] == 25.2
    # The endpoint's payload must survive Starlette's serialization, which
    # passes allow_nan=False -- the exact setting that raised the live 500
    # ("Out of range float values are not JSON compliant: nan"). A NaN any-
    # where in the dict must therefore be impossible.
    import json

    # A NaN in any numeric field is what made Starlette's JSONResponse (which
    # serializes with allow_nan=False) 500; the whole payload must serialize.
    json.dumps(got, allow_nan=False)  # must not raise


def test_read_rollup_blank_numeric_becomes_none_not_nan(tmp_path):
    """A blank cell in a float column coerces to None (not NaN) so the endpoint
    stays JSON-safe; integer columns stay 0."""
    got = operations._read_rollup(
        _write(tmp_path / "w.csv", "2026-09-02,1,1,0,1,5570282,439,3,0,0,0,\n")
    )
    r = got["rows"][0]
    assert r["pct_early_gt2"] is None
    import math

    assert (
        not math.isnan(r["pct_early_gt2"]) if r["pct_early_gt2"] is not None else True
    )


def test_read_rollup_flags_holiday_rows(tmp_path, monkeypatch):
    """Labour Day (2026-09-07, a Monday) must be flagged is_holiday so the
    trends strip reads its swing as holiday service, not an incident."""
    import app.services.measured_data as md

    monkeypatch.setattr(
        md, "holiday_dates", lambda: frozenset({"20260907", "20261012"})
    )
    body = (
        "2026-09-05,2,1,0,0,4579570,1697,22,0,0,76454,25.25\n"
        "2026-09-07,4,1,0,1,6200000,2100,14,21000,0,91000,33.90\n"
        "2026-09-08,3,2,0,1,10372314,5191,31,80,0,176197,26.76\n"
    )
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    flags = {r["date"]: r["is_holiday"] for r in got["rows"]}
    assert flags == {
        "2026-09-05": False,
        "2026-09-07": True,
        "2026-09-08": False,
    }


# ---- week over week + rolling trend --------------------------------------


def _rollup_row(
    date: str, obs: int, ghosts: int, verif: int, early: float, n_rec: int | None = None
) -> str:
    # date, completed, partial, missed, am, obs, verif, ghosts, board, cells, n_rec, early
    rec = verif * 40 if n_rec is None else n_rec
    return f"{date},3,1,0,1,{obs},{verif},{ghosts},0,0,{rec},{early}\n"


def _wow_with_holiday_monday(monkeypatch, tmp_path):
    """Two full weeks entirely in the POST-block window; the second week's
    Monday (Sep 14) is flagged as a holiday. Straddling the Sept-8 boundary
    would make WoW null (a schedule change is not a service trend), so this
    stays within one block to test the holiday-delta math in isolation."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset({"20260921"}))
    body = (
        # Week 1: Mon Sep 14 - Fri Sep 18 (all comparable weekdays)
        _rollup_row("2026-09-14", 10_000_000, 20, 5000, 25.0, n_rec=200_000)
        + _rollup_row("2026-09-15", 10_000_000, 20, 5000, 25.0, n_rec=200_000)
        + _rollup_row("2026-09-16", 10_000_000, 20, 5000, 25.0, n_rec=200_000)
        + _rollup_row("2026-09-17", 10_000_000, 20, 5000, 25.0, n_rec=200_000)
        + _rollup_row("2026-09-18", 10_000_000, 20, 5000, 25.0, n_rec=200_000)
        # Week 2: holiday Monday + 4 normal weekdays, 10% less service volume
        + _rollup_row("2026-09-21", 2_000_000, 0, 1000, 60.0, n_rec=40_000)  # holiday!
        + _rollup_row("2026-09-22", 9_000_000, 18, 5000, 22.5, n_rec=180_000)
        + _rollup_row("2026-09-23", 9_000_000, 18, 5000, 22.5, n_rec=180_000)
        + _rollup_row("2026-09-24", 9_000_000, 18, 5000, 22.5, n_rec=180_000)
        + _rollup_row("2026-09-25", 9_000_000, 18, 5000, 22.5, n_rec=180_000)
    )
    return operations._read_rollup(_write(tmp_path / "w.csv", body))


def test_week_over_week_null_when_spanning_schedule_block(tmp_path, monkeypatch):
    """WoW must NOT compare a post-block week against a pre-block week — the
    Sept-8 schedule change is a timetable switch, not a service trend. A
    comparison whose window straddles the boundary returns None (the frontend
    renders "not enough data") rather than fabricating a 52% "improvement".
    (The holiday-delta math is covered by the same-block variant below.)"""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    body = (
        # Week 1 (pre-block): Mon Aug 31 - Fri Sep 4
        _rollup_row("2026-08-31", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-01", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-02", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-03", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-04", 10_000_000, 20, 5000, 25.0)
        # Week 2 (post-block): Mon Sep 8 - Fri Sep 11 (the schedule changed)
        + _rollup_row("2026-09-08", 15_000_000, 5, 6000, 40.0)
        + _rollup_row("2026-09-09", 15_000_000, 5, 6000, 40.0)
        + _rollup_row("2026-09-10", 15_000_000, 5, 6000, 40.0)
        + _rollup_row("2026-09-11", 15_000_000, 5, 6000, 40.0)
    )
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    assert got["week_over_week"] is None


def test_week_over_week_skips_holiday_monday(tmp_path, monkeypatch):
    """Same-block: WoW reflects the four comparable weekdays, not the holiday
    Monday's collapsed volume. With the holiday included the drop would read
    ~-28%; excluded it is exactly -10%."""
    got = _wow_with_holiday_monday(monkeypatch, tmp_path)
    wow = got["week_over_week"]
    assert wow is not None
    assert wow["this_week"]["days"] == 4
    assert wow["previous_week"]["days"] == 5
    assert wow["n_holiday_days_skipped"] == 1
    # 180k vs 200k recorded departures per comparable day = -10%; a
    # holiday-contaminated raw-sum compare would be -28%.
    assert wow["recorded_change_pct"] == -10.0
    # Ghost rate: 72/20000 vs 100/25000 = 0.36% vs 0.40% -> -10%.
    assert wow["ghost_rate_change_pct"] == -10.0
    # Early %: 22.5 vs 25.0 -> -2.5pp.
    assert wow["pct_early_change_pp"] == -2.5


def test_week_over_week_null_until_two_comparable_weeks(tmp_path):
    body = _rollup_row("2026-09-08", 9_000_000, 18, 5000, 22.5)
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    assert got["week_over_week"] is None


def test_wow_null_carries_block_transition_reason(tmp_path):
    """The WoW empty state explains itself: when a null is caused by the
    schedule-block transition (the previous week is entirely pre-change),
    the payload carries a reader-facing reason naming the first usable date,
    so the frontend renders it instead of a bare 'not enough data'."""
    # Real-feed behavior: one post-block week only (Tue Sep 8 - Sat Sep 12),
    # whose previous-week window is entirely pre-block -> no comparable days.
    got = operations._read_rollup(
        _write(
            tmp_path / "w.csv",
            _rollup_row("2026-09-08", 9_000_000, 18, 5000, 22.5, n_rec=180_000)
            + _rollup_row("2026-09-09", 9_000_000, 18, 5000, 22.5, n_rec=180_000)
            + _rollup_row("2026-09-10", 9_000_000, 18, 5000, 22.5, n_rec=180_000)
            + _rollup_row("2026-09-11", 9_000_000, 18, 5000, 22.5, n_rec=180_000)
            + _rollup_row("2026-09-12", 9_000_000, 18, 5000, 22.5, n_rec=180_000),
        )
    )
    assert got["week_over_week"] is None
    assert "same schedule era" in got["wow_unavailable_reason"]
    # cutoff+9: the boundary week contributes one weekday to any trailing
    # previous-window, and that window needs >=2 comparable days.
    assert "Sep 16" in got["wow_unavailable_reason"]


def test_week_over_week_weekend_days_never_in_baseline(tmp_path, monkeypatch):
    """Saturday/Sunday rows are excluded even when they dominate a window.
    (They also carry n_rec=1, so the zero-recorded guard would exclude them
    too — this fixture pins the weekday rule specifically.)"""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    body = (
        _rollup_row("2026-09-05", 1, 0, 1, 10.0)  # Sat
        + _rollup_row("2026-09-06", 1, 0, 1, 10.0)  # Sun
        + _rollup_row("2026-09-07", 5_000_000, 10, 5000, 20.0)  # Mon
        + _rollup_row("2026-09-08", 5_000_000, 10, 5000, 20.0)  # Tue
        + _rollup_row("2026-09-09", 5_000_000, 10, 5000, 20.0)  # Wed
        + _rollup_row("2026-09-10", 5_000_000, 10, 5000, 20.0)  # Thu
        + _rollup_row("2026-09-11", 5_000_000, 10, 5000, 20.0)  # Fri
        + _rollup_row("2026-09-12", 1, 0, 1, 10.0)  # Sat
        + _rollup_row("2026-09-13", 1, 0, 1, 10.0)  # Sun
    )
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    wow = got["week_over_week"]
    assert wow is None  # only one comparable week so far
    # But the rolling trend never lets a weekend value into the means:
    rolling = {p["date"]: p for p in got["rolling"]}
    assert rolling["2026-09-13"]["pct_early_gt2"] == 20.0


def test_rolling_trend_skips_holiday(tmp_path, monkeypatch):
    """A holiday Monday must not drag the rolling line: the trailing window
    for Tuesday reaches back past it to comparable weekdays."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset({"20260907"}))
    body = (
        _rollup_row("2026-09-02", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-03", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-04", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-07", 2_000_000, 90, 1000, 80.0)  # holiday Monday
        + _rollup_row("2026-09-08", 10_000_000, 20, 5000, 25.0)
    )
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    rolling = {p["date"]: p for p in got["rolling"]}
    # Tuesday's window = Thu, Fri, Tue (Monday skipped): mean early stays 25.0,
    # not dragged toward the holiday's 80.
    assert rolling["2026-09-08"]["pct_early_gt2"] == 25.0
    # The holiday row itself still gets a point (its own trailing window).
    assert rolling["2026-09-07"]["pct_early_gt2"] is not None


# ---- anomaly detection ---------------------------------------------------


def _anomaly_history(tmp_path, monkeypatch):
    """Nine stable comparable weekdays (early=25, ghost rate 0.4) then one
    Tuesday whose early share triples."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    stable = "".join(
        _rollup_row(d, 10_000_000, 20, 5000, 25.0)
        for d in (
            "2026-08-24",
            "2026-08-25",
            "2026-08-26",
            "2026-08-27",
            "2026-08-28",
            "2026-08-31",
            "2026-09-01",
            "2026-09-02",
            "2026-09-03",
        )
    )
    spike = _rollup_row("2026-09-04", 10_000_000, 20, 5000, 75.0)
    return operations._read_rollup(_write(tmp_path / "w.csv", stable + spike))


def test_anomaly_flags_3sigma_spike(tmp_path, monkeypatch):
    got = _anomaly_history(tmp_path, monkeypatch)
    assert got["anomalies"], "75% early vs a 25±0 baseline must flag"
    a = got["anomalies"][-1]
    assert a["date"] == "2026-09-04"
    assert a["is_weekend"] is False
    m = a["metrics"]["pct_early_gt2"]
    assert m["value"] == 75.0
    assert m["direction"] == "high"


def test_anomaly_quiet_on_stable_history(tmp_path, monkeypatch):
    """A normal day after a stable stretch flags nothing."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    stable = "".join(
        _rollup_row(d, 10_000_000, 20, 5000, 25.0)
        for d in (
            "2026-08-24",
            "2026-08-25",
            "2026-08-26",
            "2026-08-27",
            "2026-08-28",
            "2026-08-31",
            "2026-09-01",
            "2026-09-02",
            "2026-09-03",
            "2026-09-04",
        )
    )
    got = operations._read_rollup(_write(tmp_path / "w.csv", stable))
    assert got["anomalies"] == []


def test_anomaly_silent_before_min_history(tmp_path, monkeypatch):
    """With fewer than _ANOMALY_MIN_BASELINE comparable days, flag nothing —
    a 4-day history cannot declare an outlier responsibly."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    body = _rollup_row("2026-09-01", 10_000_000, 20, 5000, 25.0) + _rollup_row(
        "2026-09-02", 10_000_000, 20, 5000, 90.0
    )
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    assert got["anomalies"] == []


def test_anomaly_holiday_spike_still_reported(tmp_path, monkeypatch):
    """A holiday that swings >3σ is reported (with is_holiday=true), not
    hidden: holiday service legitimately shifts rates, but a swing far
    outside the weekday baseline is still worth knowing."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset({"20260907"}))
    stable = "".join(
        _rollup_row(d, 10_000_000, 20, 5000, 25.0)
        for d in (
            "2026-08-24",
            "2026-08-25",
            "2026-08-26",
            "2026-08-27",
            "2026-08-28",
            "2026-08-31",
            "2026-09-01",
            "2026-09-02",
            "2026-09-03",
        )
    )
    # Holiday Monday with wildly different early share.
    body = stable + _rollup_row("2026-09-07", 2_000_000, 400, 1000, 85.0)
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    a = [x for x in got["anomalies"] if x["date"] == "2026-09-07"]
    assert a and a[0]["is_holiday"] is True


def test_wow_spans_schedule_change_flagged_across_boundary(tmp_path, monkeypatch):
    """Once the rollup history contains rows on both sides of the Sept-8
    timetable change, WoW flags spans_schedule_change so the frontend keeps a
    visible note — the delta is within-schedule, not a pre-vs-post compare."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    body = (
        # pre-block week
        _rollup_row("2026-09-01", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-02", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-03", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-04", 10_000_000, 20, 5000, 25.0)
        # post-block week
        + _rollup_row("2026-09-08", 9_000_000, 18, 5000, 22.5)
        + _rollup_row("2026-09-09", 9_000_000, 18, 5000, 22.5)
        + _rollup_row("2026-09-10", 9_000_000, 18, 5000, 22.5)
        + _rollup_row("2026-09-11", 9_000_000, 18, 5000, 22.5)
        + _rollup_row("2026-09-14", 9_000_000, 18, 5000, 22.5)
        + _rollup_row("2026-09-15", 9_000_000, 18, 5000, 22.5)
        + _rollup_row("2026-09-16", 9_000_000, 18, 5000, 22.5)
        + _rollup_row("2026-09-17", 9_000_000, 18, 5000, 22.5)
        + _rollup_row("2026-09-18", 9_000_000, 18, 5000, 22.5)
    )
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    wow = got["week_over_week"]
    # History spans both blocks -> the flag is on.
    assert wow is not None
    assert wow["spans_schedule_change"] is True


def test_wow_post_block_single_week_null(tmp_path, monkeypatch):
    """Sampled from the real feed on Sept 8+: only one post-block week of
    history -> WoW is None, not a fabricated delta. A single week cannot
    responsibly support a week-over-week comparison."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    body = (
        _rollup_row("2026-09-08", 9_000_000, 18, 5000, 22.5)
        + _rollup_row("2026-09-09", 9_000_000, 18, 5000, 22.5)
        + _rollup_row("2026-09-10", 9_000_000, 18, 5000, 22.5)
        + _rollup_row("2026-09-11", 9_000_000, 18, 5000, 22.5)
    )
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    assert got["week_over_week"] is None


def test_wow_excludes_zero_recorded_days(tmp_path, monkeypatch):
    """A day with 0 recorded departures (today, half-collected, or a dead
    collector day) is not a measurement: it must never join a comparison
    week, or its empty sums drag the per-day mean and fabricate a collapse."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    body = (
        # Previous week: two real post-boundary weekdays (Sept 7 is pre-block
        # and would be excluded by the schedule-block rule, so it stays out).
        _rollup_row("2026-09-08", 9_000_000, 18, 5000, 22.5, n_rec=100_000)
        + _rollup_row("2026-09-09", 9_000_000, 18, 5000, 22.5, n_rec=100_000)
        # This week: a dead day in-window that must be skipped, not counted
        # as a near-zero member, plus three real weekdays.
        + _rollup_row("2026-09-10", 9_000_000, 18, 5000, 22.5, n_rec=0)
        + _rollup_row("2026-09-14", 9_000_000, 18, 5000, 22.5, n_rec=100_000)
        + _rollup_row("2026-09-15", 9_000_000, 18, 5000, 22.5, n_rec=100_000)
        + _rollup_row("2026-09-16", 9_000_000, 18, 5005, 22.6, n_rec=100_000)
    )
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    wow = got["week_over_week"]
    assert wow is not None
    assert wow["previous_week"]["days"] == 2
    assert wow["this_week"]["days"] == 3  # dead day excluded
    # Both sides are 100k/day -> 0%, not the -33% the dead day would fabricate.
    assert wow["recorded_change_pct"] == 0.0


def test_wow_single_comparable_day_per_side_null(tmp_path, monkeypatch):
    """One comparable weekday per side is an anecdote, not a trend: WoW
    stays null even though both windows are non-empty."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    body = _rollup_row(
        "2026-09-08", 9_000_000, 18, 5000, 22.5, n_rec=100_000
    ) + _rollup_row("2026-09-15", 9_000_000, 18, 5000, 30.0, n_rec=100_000)
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    assert got["week_over_week"] is None


def test_wow_post_block_two_weeks_usable(tmp_path, monkeypatch):
    """Once a second post-block week lands, WoW computes — the endpoint gives
    a real within-schedule comparison, not the pre-vs-post contamination."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    body = (
        # post-block week 1
        _rollup_row("2026-09-08", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-09", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-10", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-11", 10_000_000, 20, 5000, 25.0)
        + _rollup_row("2026-09-12", 10_000_000, 20, 5000, 25.0)
        # post-block week 2 (5% less volume per day)
        + _rollup_row("2026-09-14", 10_000_000, 20, 5000, 25.0, n_rec=200_000)
        + _rollup_row("2026-09-15", 9_500_000, 19, 5000, 24.0, n_rec=190_000)
        + _rollup_row("2026-09-16", 9_500_000, 19, 5000, 24.0, n_rec=190_000)
        + _rollup_row("2026-09-17", 9_500_000, 19, 5000, 24.0, n_rec=190_000)
        + _rollup_row("2026-09-18", 9_500_000, 19, 5000, 24.0, n_rec=190_000)
    )
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    wow = got["week_over_week"]
    assert wow is not None
    # Weeks: prev = Sep 5-11 (Tue-Fri) -> 4; this = Sep 12-18 (Mon-Fri) -> 5.
    # Per-comparable-day recorded departures: 192k (Mon 200k + 4×190k over 5
    # days) vs 200k -> -4.0% (not a raw-sum compare, which would report -5%
    # purely from the extra Monday; and not the poll-snapshot count, which
    # tracks cadence not service).
    assert wow["previous_week"]["days"] == 4
    assert wow["this_week"]["days"] == 5
    assert abs(wow["recorded_change_pct"] - (-4.0)) < 0.1
    # This is a same-block (post) comparison -> no transition flag.
    assert wow["spans_schedule_change"] is False


def test_anomaly_constant_baseline_small_drift_not_flagged(tmp_path, monkeypatch):
    """A constant baseline (σ=0) plus a 1-point drift (24.0 vs 25.0) must NOT
    read as a −99σ collapse: the degenerate path requires the deviation to be
    large in relative terms (≥ 20% of the mean) before flagging."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    body = "".join(
        _rollup_row(d, 10_000_000, 20, 5000, 25.0)
        for d in ("2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11", "2026-09-14")
    ) + _rollup_row("2026-09-15", 10_000_000, 20, 5000, 24.0)
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    assert got["anomalies"] == []


def test_anomaly_constant_baseline_genuine_spike_still_flagged(tmp_path, monkeypatch):
    """The stable-week-then-jump case is exactly what the degenerate path
    exists for: a 25.0→10.0 collapse on a constant baseline still flags."""
    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    body = "".join(
        _rollup_row(d, 10_000_000, 20, 5000, 25.0)
        for d in ("2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11", "2026-09-14")
    ) + _rollup_row("2026-09-15", 10_000_000, 20, 5000, 10.0)
    got = operations._read_rollup(_write(tmp_path / "w.csv", body))
    assert got["anomalies"], "genuine spike on a constant baseline must flag"
    m = got["anomalies"][-1]["metrics"]["pct_early_gt2"]
    assert m["direction"] == "low"
    assert abs(m["z"]) == 99.0  # capped, finite


def test_trends_http_endpoint_post_block(tmp_path, monkeypatch):
    """Integration: GET /api/operations/trends through the FastAPI app with a
    post-block (Sept 8+) rollup behind it — must serialize cleanly (no NaN),
    tag rows with the feed-derived schedule block, and give a usable WoW once
    two post-block weeks exist."""
    from datetime import date as _date, timedelta as _timedelta

    from app.main import app
    from fastapi.testclient import TestClient

    import app.services.measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    monkeypatch.setattr(operations, "_ROLLUP_CSV", tmp_path / "weekly_rollup.csv")

    # Two post-block weeks of Tue Sep 8 - Fri Sep 18 2026 (real weekdays),
    # 5% worse volume in week 2.
    lines = []
    d = _date(2026, 9, 8)
    while d <= _date(2026, 9, 18):
        if d.weekday() >= 5:
            d += _timedelta(days=1)
            continue
        vol = 10_000_000 if d <= _date(2026, 9, 11) else 9_500_000
        rec = 200_000 if d <= _date(2026, 9, 11) else 190_000
        lines.append(_rollup_row(d.isoformat(), vol, 20, 5000, 25.0, n_rec=rec))
        d += _timedelta(days=1)
    _write(tmp_path / "weekly_rollup.csv", "".join(lines))

    with TestClient(app) as client:
        resp = client.get("/api/operations/trends")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    # Rows carry the feed-derived block (the real feed's boundary is Sept 7,
    # so all Sept 8+ rows are 'post').
    blocks = {r["schedule_block"] for r in data["rows"]}
    assert blocks == {"post"}
    # Usable same-block WoW: week 2 is uniformly 5% below week 1 per
    # comparable day (Sep 12 is a Saturday, so week 1 has Tue-Fri = 4 days
    # and week 2 has Mon-Fri = 5; per-day compare, not raw sums).
    wow = data["week_over_week"]
    assert wow is not None
    assert wow["spans_schedule_change"] is False
    assert abs(wow["recorded_change_pct"] - (-5.0)) < 0.1
    # No NaN ever reaches the JSON (the 2026-09-02 live-500 regression class).
    assert "NaN" not in resp.text
