"""Pre-changeover exclusion from the live measured stream.

The schedule change (feed-derived boundary in services.measured_data) split
the collected history into two timetables. The live headline readers must
drop pre-boundary rows at read time (drop_pre_changeover_rows) so post-change
metrics stand alone, with the exclusion auditable in the payload.
"""

import pandas as pd

from app.services import measured_data as md


def _write_calendar_dates(tmp_path, rows):
    p = tmp_path / "calendar_dates.txt"
    p.write_text(
        "service_id,date,exception_type\n"
        + "".join(f"{s},{d},{e}\n" for s, d, e in rows),
        encoding="utf-8",
    )
    return p


def _patch_feed(tmp_path, monkeypatch, cutoff_date="20260907"):
    """Feed whose dominant block flips at cutoff_date (2026-09-07).

    An empty ``cutoff_date`` writes a single-date feed (no transition
    derivable -> block_cutoff() == "").
    """
    rows = [(f"26AU03-CPBlock-Weekday-11-{d}", d, 1) for d in ("20260901", "20260904")]
    if cutoff_date:
        rows += [
            (f"26SE07-MABlock-Weekday-21-{d}", d, 1) for d in (cutoff_date, "20260908")
        ]
    _write_calendar_dates(tmp_path, rows)
    monkeypatch.setattr(md.config, "LOCAL_GTFS_DIR", tmp_path)
    md._block_cutoff_cached.cache_clear()


def test_drop_pre_changeover_rows_both_date_spellings(tmp_path, monkeypatch):
    _patch_feed(tmp_path, monkeypatch)
    df = pd.DataFrame(
        {
            "date": ["2026-09-05", "20260907", "20260908", "20260909", "garbage"],
            "lat": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    out, n, cutoff = md.drop_pre_changeover_rows(df)
    assert cutoff == "20260907"
    # The boundary day itself is "pre" (schedule_block: d <= cutoff — the
    # last day of the old timetable); dashed and compact spellings both
    # recognized; garbage kept (undatable rows pass — the holiday filter's
    # contract, mirrored here).
    assert n == 2
    assert list(out["lat"]) == [3.0, 4.0, 5.0]


def test_drop_pre_changeover_rows_no_boundary_keeps_everything(tmp_path, monkeypatch):
    _patch_feed(tmp_path, monkeypatch, cutoff_date="")
    df = pd.DataFrame({"date": ["20260901", "20260909"], "lat": [1.0, 2.0]})
    out, n, cutoff = md.drop_pre_changeover_rows(df)
    assert cutoff is None
    assert n == 0
    assert len(out) == 2


def test_drop_pre_changeover_rows_missing_date_column(tmp_path, monkeypatch):
    _patch_feed(tmp_path, monkeypatch)
    df = pd.DataFrame({"lat": [1.0, 2.0]})
    out, n, cutoff = md.drop_pre_changeover_rows(df, date_column="service_date")
    assert cutoff == "20260907"
    assert n == 0
    assert len(out) == 2


def test_service_quality_payload_reports_exclusion(tmp_path, monkeypatch):
    """The lateness reader surfaces the exclusion count + boundary."""
    _patch_feed(tmp_path, monkeypatch)
    csv = tmp_path / "obs_lateness.csv"
    csv.write_text(
        "route_short_name,stop_id,dep_time_min,lateness_minutes,"
        "horizon_minutes,date\n"
        "10,1001,480.0,-0.5,-0.5,20260901\n"
        "10,1001,480.0,1.5,-0.5,20260908\n",
        encoding="utf-8",
    )
    from app.routers import service_quality as sq

    monkeypatch.setattr(sq, "_LATENESS_CSV", csv)
    payload = (
        sq._lateness.__wrapped__(  # bypass the mtime debounce
            *(),
            **{},
        )
        if hasattr(sq._lateness, "__wrapped__")
        else None
    )
    # _lateness is decorated; call through the decorator's cache wrapper is
    # not needed — mtime_reader exposes the raw function via __wrapped__.
    assert payload is not None, "expected an unwrapped reader"
    assert payload["available"] is True
    assert payload["n_pre_changeover_observations_excluded"] == 1
    assert payload["schedule_block_boundary"] == "20260907"
