"""Unit tests for ``scripts/collect_service.py`` (scheduled collection).

Tests the pure window/date logic, the CSV append/dedup helpers, the
per-window vehicle-position snapshot writer, and the post-window analysis
launcher; no network. The ``collect_window`` loop itself is exercised
through its deadline math only.
"""

import csv
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from scripts.collect_service import (
    COVERAGE_COLUMNS,
    _check_single_instance,
    _claim_lock,
    _coverage_status,
    _pid_start_time,
    _window_deadline,
    _window_stats,
    _write_coverage_json,
    _write_vp_polls,
    append_coverage_csv,
    append_rows,
    backfill_coverage_csv,
    current_window,
    dedup_csv,
    next_window_at,
    parse_days,
    parse_windows,
    run_analysis,
)

DEFAULT_WINDOWS = [(360, 540), (900, 1140)]  # 06:00-09:00, 15:00-19:00


def test_parse_windows():
    assert parse_windows("06:00-09:00,15:00-19:00") == [(360, 540), (900, 1140)]
    assert parse_windows("15:00-19:00,06:00-09:00") == [
        (360, 540),
        (900, 1140),
    ]  # sorted
    assert parse_windows("06:00-09:00") == [(360, 540)]


def test_parse_windows_rejects_bad_specs():
    for bad in ("06:00", "6am-9am", "25:00-26:00", "09:00-06:00", ""):
        with pytest.raises(ValueError):
            parse_windows(bad)


def test_parse_days():
    assert parse_days("mon,tue,wed,thu,fri") == {0, 1, 2, 3, 4}
    assert parse_days("Sat,SUN") == {5, 6}
    with pytest.raises(ValueError):
        parse_days("mon,bluesday")


def test_window_deadline_normal_end():
    now = datetime(2026, 8, 18, 15, 2, 59)
    assert _window_deadline(now, 1140) == datetime(2026, 8, 18, 19, 0, 0)
    assert _window_deadline(now, 540) == datetime(2026, 8, 18, 9, 0, 0)


def test_window_deadline_midnight_rolls_to_next_day():
    """24:00 (end_min=1440) must cross the date boundary, not hour=24."""
    now = datetime(2026, 8, 18, 19, 0, 5)
    assert _window_deadline(now, 1440) == datetime(2026, 8, 19, 0, 0, 0)


def test_current_window():
    assert current_window(360, DEFAULT_WINDOWS) == (360, 540)  # 06:00, inclusive start
    assert current_window(539, DEFAULT_WINDOWS) == (360, 540)  # 08:59, just before end
    assert current_window(540, DEFAULT_WINDOWS) is None  # 09:00, exclusive end
    assert current_window(1000, DEFAULT_WINDOWS) == (900, 1140)
    assert current_window(200, DEFAULT_WINDOWS) is None  # before the first window


def test_next_window_at_rolls_to_tomorrow():
    # 10:00 -> next window is 15:00 today (300 min away).
    assert next_window_at(600, DEFAULT_WINDOWS) == 300
    # 20:00 -> nothing today; rolls to tomorrow's 06:00 (600 min away).
    assert next_window_at(1200, DEFAULT_WINDOWS) == (24 * 60 - 1200) + 360
    # 05:00 -> 06:00 today (60 min away).
    assert next_window_at(300, DEFAULT_WINDOWS) == 60


def test_append_rows_writes_header_then_appends(tmp_path):
    out = tmp_path / "obs.csv"
    rows = [
        {
            "route_short_name": "1",
            "stop_id": "a",
            "dep_time_min": 410.0,
            "lateness_minutes": 1.0,
            "horizon_minutes": -2.5,
            # No date supplied → written as empty (per-day splits exclude it).
        }
    ]
    append_rows(out, rows)
    append_rows(
        out,
        [
            {
                "route_short_name": "2",
                "stop_id": "b",
                "dep_time_min": 700.0,
                "lateness_minutes": -0.5,
                "horizon_minutes": 0.0,
                "date": "20260823",
            }
        ],
    )
    text = out.read_text(encoding="utf-8")
    assert (
        text.splitlines()[0]
        == "route_short_name,stop_id,dep_time_min,lateness_minutes,horizon_minutes,date"
    )
    assert len(text.splitlines()) == 3
    df = pd.read_csv(out, dtype={"route_short_name": str})
    assert len(df) == 2
    assert set(df["route_short_name"]) == {"1", "2"}
    assert df["horizon_minutes"].tolist() == [-2.5, 0.0]
    assert df["date"].isna().tolist() == [True, False]
    assert df.loc[df.route_short_name == "2", "date"].item() == 20260823


def test_append_rows_migrates_legacy_4col_header(tmp_path):
    out = tmp_path / "obs.csv"
    out.write_text(
        "route_short_name,stop_id,dep_time_min,lateness_minutes\n1,a,410.0,1.0\n",
        encoding="utf-8",
    )
    append_rows(
        out,
        [
            {
                "route_short_name": "2",
                "stop_id": "b",
                "dep_time_min": 700.0,
                "lateness_minutes": -0.5,
                "horizon_minutes": -1.0,
            }
        ],
    )
    text = out.read_text(encoding="utf-8")
    assert "horizon_minutes" in text.splitlines()[0]
    df = pd.read_csv(out, dtype={"route_short_name": str})
    assert len(df) == 2
    # Legacy row has no horizon (unverifiable); new row keeps its value.
    assert pd.isna(df.loc[0, "horizon_minutes"])
    assert df.loc[1, "horizon_minutes"] == -1.0


def test_dedup_csv_drops_exact_duplicates(tmp_path):
    out = tmp_path / "obs.csv"
    append_rows(
        out,
        [
            {
                "route_short_name": "1",
                "stop_id": "a",
                "dep_time_min": 410.0,
                "lateness_minutes": 1.0,
                "horizon_minutes": -1.0,
            },
            {
                "route_short_name": "1",
                "stop_id": "a",
                "dep_time_min": 410.0,
                "lateness_minutes": 1.0,
                "horizon_minutes": -2.0,
            },
            {
                "route_short_name": "1",
                "stop_id": "a",
                "dep_time_min": 410.0,
                "lateness_minutes": 2.0,
                "horizon_minutes": -3.0,
            },
        ],
    )
    dedup_csv(out)
    df = pd.read_csv(out, dtype={"route_short_name": str})
    # All three rows are the SAME departure (1, a, 410) whose lateness
    # reading evolved across polls (1.0 -> 2.0). One row survives: the
    # freshest poll (most-negative horizon -3.0, lateness 2.0).
    assert len(df) == 1
    kept = df.iloc[0]
    assert kept["lateness_minutes"] == 2.0
    assert kept["horizon_minutes"] == -3.0


def test_dedup_csv_noop_on_missing(tmp_path):
    out = tmp_path / "obs.csv"
    dedup_csv(out)  # must not raise
    assert not out.exists()


def test_write_vp_polls_writes_loadable_json(tmp_path):
    out = tmp_path / "vp_20260817_0630.json"
    _write_vp_polls(
        out,
        [
            {
                "poll": 1,
                "fetched_at": 123,
                "buses": [{"trip_id": "1", "occupancy_percentage": 40}],
            },
            {
                "poll": 2,
                "fetched_at": 124,
                "buses": [{"trip_id": "1", "occupancy_percentage": 60}],
            },
        ],
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["polls"]) == 2
    assert data["polls"][0]["buses"][0]["occupancy_percentage"] == 40
    # no stray temp file left behind
    assert not out.with_suffix(".json.tmp").exists()


def test_atomic_write_json_retries_transient_lock(tmp_path, monkeypatch):
    """A one-off OSError (cloud-sync lock) is retried, not raised."""
    import scripts.collect_service as cs

    out = tmp_path / "vp.json"
    real_replace = os.replace
    calls = {"n": 0}

    def _flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("file locked")
        return real_replace(src, dst)

    monkeypatch.setattr(cs.os, "replace", _flaky_replace)
    cs._atomic_write_json(out, {"polls": [{"poll": 1}]})
    assert calls["n"] == 2  # failed once, retried, succeeded
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["polls"]) == 1


def test_atomic_write_json_raises_after_all_attempts(tmp_path, monkeypatch):
    """A persistent lock still raises (the poll loop catches it and moves on)."""
    import scripts.collect_service as cs

    def _always_locked(src, dst):
        raise OSError("file locked")

    monkeypatch.setattr(cs.os, "replace", _always_locked)
    with pytest.raises(OSError):
        cs._atomic_write_json(tmp_path / "vp.json", {"polls": []})


def test_night_throttle_boundaries_and_disable():
    """Throttle 01:00-05:00 only; boundaries exact; 0 disables.

    The 00:00-01:00 and 05:00-06:00 edges stay at full rate because the
    analysis consumes real after-midnight service (5.1% of rows are
    dep >= 1440) and the window (0,360) expects complete coverage.
    """
    from datetime import datetime

    from scripts.collect_service import _effective_interval

    iv = 30.0
    assert _effective_interval(datetime(2026, 9, 7, 0, 59), iv) == iv
    assert _effective_interval(datetime(2026, 9, 7, 1, 0), iv) == 120.0
    assert _effective_interval(datetime(2026, 9, 7, 3, 0), iv) == 120.0
    assert _effective_interval(datetime(2026, 9, 7, 4, 59), iv) == 120.0
    assert _effective_interval(datetime(2026, 9, 7, 5, 0), iv) == iv
    monkeypatch_free_disable(iv)


def monkeypatch_free_disable(iv):
    """Night interval 0 disables the throttle (env read per call)."""
    from datetime import datetime
    import os

    from scripts.collect_service import _effective_interval, _night_interval

    old = os.environ.get("MIWAY_COLLECT_NIGHT_INTERVAL")
    try:
        os.environ["MIWAY_COLLECT_NIGHT_INTERVAL"] = "0"
        assert _night_interval() == 0
        assert _effective_interval(datetime(2026, 9, 7, 3, 0), iv) == iv
    finally:
        if old is None:
            os.environ.pop("MIWAY_COLLECT_NIGHT_INTERVAL", None)
        else:
            os.environ["MIWAY_COLLECT_NIGHT_INTERVAL"] = old


def test_session_start_line_is_machine_parseable(capsys):
    """The SESSION marker must be one grep-able line with pid/hash/timestamp.

    Restart churn (Sept 1-6) made restarts uncountable: window-start lines
    look identical from a fresh or long-lived process. The SESSION line is
    the anchor analysis uses to exclude partial windows and to detect a
    split-brain (two data_dir hashes interleaved in time).
    """
    import hashlib
    import re

    from scripts.collect_service import _log_session_start

    dd = Path("/nonexistent-data-dir-for-test").resolve()
    _log_session_start(dd, Path("obs_lateness.csv"))
    line = capsys.readouterr().out.strip()
    assert line.startswith("SESSION ")
    m = re.match(
        r"SESSION pid=(\d+) data_dir=([0-9a-f]{16}) out=(\S+) "
        r"start=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})$",
        line,
    )
    assert m, f"SESSION line not machine-parseable: {line}"
    assert int(m.group(1)) == os.getpid()
    assert m.group(2) == hashlib.sha256(str(dd).encode()).hexdigest()[:16]


def test_atomic_write_csv_retries_onedrive_lock(tmp_path, monkeypatch):
    """The Sept 4 20:01 crash: PermissionError on os.replace of the main CSV
    (cloud sync lock) killed the collector mid-dedup_csv. The shared
    atomic writers in data_dir_util must retry and survive."""
    from scripts.data_dir_util import atomic_write_csv
    import scripts.data_dir_util as ddu

    out = tmp_path / "obs_lateness.csv"
    real_replace = os.replace
    calls = {"n": 0}

    def _flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] <= 2:  # Sept 4 pattern: locked twice, then free
            raise PermissionError(5, "Access is denied")
        return real_replace(src, dst)

    monkeypatch.setattr(ddu.os, "replace", _flaky_replace)
    import pandas as pd

    atomic_write_csv(pd.DataFrame({"a": [1, 2]}), out)
    assert calls["n"] == 3  # failed twice, third attempt succeeded
    assert len(pd.read_csv(out)) == 2


def test_atomic_write_csv_raises_after_persistent_lock(tmp_path, monkeypatch):
    """A lock that never clears still surfaces (caller handlers decide)."""
    from scripts.data_dir_util import atomic_write_csv
    import scripts.data_dir_util as ddu

    def _always_locked(src, dst):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(ddu.os, "replace", _always_locked)
    with pytest.raises(PermissionError):
        atomic_write_csv(__import__("pandas").DataFrame({"a": [1]}), tmp_path / "x.csv")


def test_write_vp_polls_overwrites_previous_polls(tmp_path):
    out = tmp_path / "vp.json"
    _write_vp_polls(out, [{"poll": 1, "fetched_at": 1, "buses": []}])
    _write_vp_polls(
        out,
        [
            {"poll": 1, "fetched_at": 1, "buses": []},
            {"poll": 2, "fetched_at": 2, "buses": []},
        ],
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["polls"]) == 2  # second write replaced, not appended


def test_run_analysis_invokes_all_seven_scripts(tmp_path, monkeypatch):
    """Post-window analysis runs occupancy, boardings, dwell split, report,
    ghosts, charts, rollup, and the ledger self-repair audit."""
    calls = []

    def _fake_run(cmd, cwd=None, capture_output=False, text=False, timeout=None):
        calls.append((cmd, cwd))
        return subprocess.CompletedProcess(
            cmd, returncode=0, stdout="wrote x\nsome summary", stderr=""
        )

    monkeypatch.setattr("scripts.collect_service.subprocess.run", _fake_run)
    monkeypatch.setattr("scripts.collect_service.sys.executable", "py")
    # run_analysis skips a script whose output CSV is newer than the newest
    # snapshot ("output fresh"). That gate reads config.DATA_DIR, so on a
    # machine (or a fresh CI checkout, where every tracked file gets the same
    # checkout mtime) where occupancy_stats.csv / boardings_routes.csv happen
    # to be >= the newest vp_*.json, two scripts never spawn and this test
    # saw 6 calls instead of 8 — CI 2026-10-03. Point DATA_DIR at an empty
    # tmp dir so no output can look fresh; the freshness gate has its own
    # tests, and this one is about WHICH scripts run, in which order.
    monkeypatch.setattr("scripts.collect_service.config.DATA_DIR", tmp_path / "data")

    run_analysis(interval=30.0, vp_dir=tmp_path / "vp.json")

    assert len(calls) == 8
    names = [Path(cmd[1]).name for cmd, _ in calls]
    assert names == [
        "aggregate_occupancy.py",
        "reconstruct_boardings.py",
        "dwell_split.py",
        "peak_report.py",
        "ghost_trips.py",
        "weekly_charts.py",
        "weekly_rollup.py",
        "audit_coverage_ledger.py",
    ]
    # The ledger audit runs with --repair so damage is fixed, not just logged.
    audit_cmd = calls[-1][0]
    assert "--repair" in audit_cmd
    # every subprocess runs from the backend dir; the analysis scripts
    # (except the report and ghosts/charts, which read derived CSVs / coverage)
    backend = Path(__file__).resolve().parents[1]
    for cmd, cwd in calls:
        assert cwd == backend
        globs = [c for c in cmd if c.endswith("*.json")]
        if Path(cmd[1]).name in (
            "peak_report.py",
            "ghost_trips.py",
            "weekly_charts.py",
            "weekly_rollup.py",
            "audit_coverage_ledger.py",
        ):
            assert globs == []
        else:
            assert len(globs) == 1
            assert "collections" in globs[0]


def test_run_analysis_survives_subprocess_failure(monkeypatch):
    """A crashed analysis script never raises out of the collector loop."""

    def _boom(cmd, cwd=None, capture_output=False, text=False, timeout=None):
        raise OSError("engine broke")

    monkeypatch.setattr("scripts.collect_service.subprocess.run", _boom)
    monkeypatch.setattr("scripts.collect_service.sys.executable", "py")

    run_analysis(interval=30.0)  # must not raise


def test_collect_window_accumulates_vp_polls(tmp_path, monkeypatch):
    """The poll loop writes per-poll VP snapshots when vp_out is given."""
    import scripts.collect_service as cs

    out = tmp_path / "obs.csv"
    vp_out = tmp_path / "vp.json"
    deadline = time.time() + 0.3  # one quick loop before deadline
    polls_called = []

    class _Resp:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

    class _Client:
        def get(self, url, timeout=None):
            polls_called.append(url)
            # TripUpdates -> no rows (lateness join returns []), VP -> fake
            # vehicle rows that decode to a tiny list.
            if url == cs.config.MIWAY_GTFSRT_TRIP_UPDATES:
                return _Resp(b"trip-updates")
            return _Resp(b"vehicle-positions")

    monkeypatch.setattr(cs, "_miway_lateness_rows", lambda *a: [])
    monkeypatch.setattr(
        cs,
        "decode_miway_vehicle_positions",
        lambda raw: [{"trip_id": "1", "occupancy_percentage": 20}],
    )

    cs.collect_window(
        _Client(),
        ({}, ({}, {})),
        out,
        interval=0.05,
        window_s=1800,
        deadline=deadline,
        vp_out=vp_out,
    )
    assert any(u == cs.config.MIWAY_GTFSRT_VEHICLE_POS for u in polls_called)
    data = json.loads(vp_out.read_text(encoding="utf-8"))
    assert len(data["polls"]) >= 1
    assert data["polls"][0]["buses"][0]["occupancy_percentage"] == 20
    # the fixed vehicle_positions.json is NOT touched by the collector
    assert not (tmp_path / "vehicle_positions.json").exists()


def test_collect_window_survives_vp_write_failure(tmp_path, monkeypatch):
    """A transient VP write failure (e.g. cloud-sync lock) must not kill the
    collector: the poll loop logs it and keeps going."""
    import scripts.collect_service as cs

    out = tmp_path / "obs.csv"
    vp_out = tmp_path / "vp.json"
    deadline = time.time() + 0.3
    polls_called = []

    class _Resp:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

    class _Client:
        def get(self, url, timeout=None):
            polls_called.append(url)
            if url == cs.config.MIWAY_GTFSRT_TRIP_UPDATES:
                return _Resp(b"trip-updates")
            return _Resp(b"vehicle-positions")

    monkeypatch.setattr(cs, "_miway_lateness_rows", lambda *a: [])
    monkeypatch.setattr(
        cs,
        "decode_miway_vehicle_positions",
        lambda raw: [{"trip_id": "1", "occupancy_percentage": 20}],
    )

    def _boom(path, polls):
        raise OSError("file locked")

    monkeypatch.setattr(cs, "_write_vp_polls", _boom)

    # must not raise, even though every VP write fails
    cs.collect_window(
        _Client(),
        ({}, ({}, {})),
        out,
        interval=0.05,
        window_s=1800,
        deadline=deadline,
        vp_out=vp_out,
    )
    assert any(u == cs.config.MIWAY_GTFSRT_VEHICLE_POS for u in polls_called)
    assert not vp_out.exists()  # nothing was ever written


def test_collect_window_writes_one_alerts_snapshot(tmp_path, monkeypatch):
    """When alerts_out is given, the collector persists exactly one decoded
    alerts snapshot per window (a single fetch, before the poll loop)."""
    import scripts.collect_service as cs

    out = tmp_path / "obs.csv"
    alerts_out = tmp_path / "alerts_20260830_1530.json"
    deadline = time.time() + 0.2
    calls = []
    coverage = cs._window_stats(
        datetime(2026, 8, 30, 15, 30), datetime(2026, 8, 30, 16, 0), (930, 960)
    )

    class _Resp:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

    class _Client:
        def get(self, url, timeout=None):
            calls.append(url)
            if url == cs.config.MIWAY_GTFSRT_ALERTS:
                return _Resp(b"alerts-pb")
            return _Resp(b"trip-updates")

    monkeypatch.setattr(cs, "_miway_lateness_rows", lambda *a: [])
    monkeypatch.setattr(
        cs,
        "decode_miway_alerts",
        lambda raw: (
            [{"routes": ["103"], "effect": 9, "cause": 10}]
            if raw == b"alerts-pb"
            else []
        ),
    )

    cs.collect_window(
        _Client(),
        ({}, ({}, {})),
        out,
        interval=0.05,
        window_s=1800,
        deadline=deadline,
        coverage=coverage,
        alerts_out=alerts_out,
    )
    assert calls.count(cs.config.MIWAY_GTFSRT_ALERTS) == 1  # once, not per-poll
    data = json.loads(alerts_out.read_text(encoding="utf-8"))
    assert data["count"] == 1
    assert data["alerts"][0]["routes"] == ["103"]
    assert coverage["alerts"] == 1


def test_collect_window_alert_fetch_failure_does_not_kill_window(tmp_path, monkeypatch):
    """An alerts fetch/write failure is logged and skipped; collection continues."""
    import scripts.collect_service as cs

    out = tmp_path / "obs.csv"
    alerts_out = tmp_path / "alerts.json"
    deadline = time.time() + 0.2
    polls_called = []

    class _Resp:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

    class _Client:
        def get(self, url, timeout=None):
            polls_called.append(url)
            if url == cs.config.MIWAY_GTFSRT_ALERTS:
                raise RuntimeError("network down")
            return _Resp(b"trip-updates")

    monkeypatch.setattr(cs, "_miway_lateness_rows", lambda *a: [])

    # must not raise and the poll loop still runs
    cs.collect_window(
        _Client(),
        ({}, ({}, {})),
        out,
        interval=0.05,
        window_s=1800,
        deadline=deadline,
        alerts_out=alerts_out,
    )
    assert any(u == cs.config.MIWAY_GTFSRT_TRIP_UPDATES for u in polls_called)
    assert alerts_out is not None and not alerts_out.exists()  # never written


def test_coverage_status_classification():
    base = {"polls_succeeded": 5, "polls_failed": 0}
    assert _coverage_status(base) == "completed"
    base["polls_failed"] = 2
    assert _coverage_status(base) == "partial"  # some polls failed (wifi blip)
    base["polls_succeeded"] = 0
    assert _coverage_status(base) == "missed"  # router off all window


def test_window_stats_shape():
    now = datetime(2026, 8, 18, 6, 0, 0)
    deadline = datetime(2026, 8, 18, 9, 0, 0)
    stats = _window_stats(now, deadline, (360, 540))
    assert stats["date"] == "2026-08-18"
    assert stats["scheduled"] == "06:00-09:00"
    assert stats["status"] == "collecting"
    assert stats["polls_attempted"] == 0
    assert stats["first_poll_at"] is None


def test_append_coverage_csv_writes_header_then_rows(tmp_path):
    csv_path = tmp_path / "collection_windows.csv"
    stats = _window_stats(
        datetime(2026, 8, 18, 6, 0, 0), datetime(2026, 8, 18, 9, 0, 0), (360, 540)
    )
    stats.update(
        {
            "status": "completed",
            "polls_attempted": 359,
            "polls_succeeded": 359,
            "polls_failed": 0,
            "first_poll_at": "2026-08-18 06:00:05",
            "last_poll_at": "2026-08-18 08:59:55",
            "observations": 12034,
            "vp_snapshots": 359,
        }
    )
    append_coverage_csv(csv_path, stats)
    append_coverage_csv(csv_path, stats)  # a second window appends, no dup header
    df = pd.read_csv(csv_path)
    assert len(df) == 2
    assert list(df.columns) == [
        "date",
        "window_start",
        "window_end",
        "scheduled",
        "status",
        "polls_attempted",
        "polls_succeeded",
        "polls_failed",
        "first_poll_at",
        "last_poll_at",
        "observations",
        "vp_snapshots",
        "alerts",
        "longest_gap_min",
        "polls_timeout",
        "collector_origin",
    ]
    assert df.iloc[0]["status"] == "completed"
    assert df.iloc[0]["polls_timeout"] == 0
    assert df.iloc[0]["observations"] == 12034


def test_append_coverage_csv_migrates_legacy_stale_header(tmp_path):
    """Appending to a coverage CSV whose header predates the current column
    set must migrate the header (and backfill the new trailing columns on the
    legacy rows) instead of appending wider rows against a stale header.

    Regression: the live coverage file was written with a 12-column header
    while ``COVERAGE_COLUMNS`` grew to 14 (``longest_gap_min``, then
    ``polls_timeout``), so rows were silently misaligned and the new columns
    were unreadable by name under pandas.
    """
    csv_path = tmp_path / "collection_windows.csv"
    legacy_header = [
        "date",
        "window_start",
        "window_end",
        "scheduled",
        "status",
        "polls_attempted",
        "polls_succeeded",
        "polls_failed",
        "first_poll_at",
        "last_poll_at",
        "observations",
        "vp_snapshots",
    ]  # old schema: no longest_gap_min, no polls_timeout
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(legacy_header)
        w.writerow(
            [
                "2026-08-18",
                "2026-08-18 15:00:00",
                "2026-08-18 19:00:00",
                "15:00-19:00",
                "completed",
                "360",
                "360",
                "0",
                "2026-08-18 15:00:05",
                "2026-08-18 18:59:55",
                "12034",
                "360",
            ]
        )

    stats = _window_stats(
        datetime(2026, 8, 18, 15, 0, 0), datetime(2026, 8, 18, 19, 0, 0), (900, 1140)
    )
    stats.update(
        {
            "status": "completed",
            "polls_attempted": 360,
            "polls_succeeded": 360,
            "polls_failed": 0,
            "observations": 12034,
            "vp_snapshots": 360,
            "longest_gap_min": 4.2,
            "polls_timeout": 0,
        }
    )

    append_coverage_csv(csv_path, stats)

    df = pd.read_csv(csv_path)
    assert list(df.columns) == COVERAGE_COLUMNS  # header migrated to 14
    assert len(df) == 2  # legacy row + the newly appended one
    # legacy row had none of the newer columns recorded -> backfilled empty
    assert pd.isna(df.iloc[0]["longest_gap_min"])
    assert pd.isna(df.iloc[0]["polls_timeout"])
    # the brand-new row carries its real values under the current schema
    assert df.iloc[1]["longest_gap_min"] == 4.2
    assert df.iloc[1]["polls_timeout"] == 0


def test_backfill_coverage_csv_appends_missing_and_marks_interrupted(tmp_path):
    coverage_dir = tmp_path / "coverage"
    coverage_dir.mkdir()
    csv_path = tmp_path / "collection_windows.csv"

    # A window the collector entered, crashed mid-way (left as 'collecting').
    crashed = _window_stats(
        datetime(2026, 8, 17, 15, 0, 0), datetime(2026, 8, 17, 19, 0, 0), (900, 1140)
    )
    crashed.update({"polls_attempted": 12, "polls_succeeded": 10, "polls_failed": 2})
    _write_coverage_json(coverage_dir / "window_20260817_1500.json", crashed)

    # A window already recorded in the CSV (must NOT be re-appended). Same
    # day, but a *later* start — exactly how a restart re-entering the window
    # creates a new record (cf. today's vp_1500 / vp_1531 files).
    done = _window_stats(
        datetime(2026, 8, 17, 15, 31, 0), datetime(2026, 8, 17, 19, 0, 0), (900, 1140)
    )
    done.update({"status": "completed", "polls_succeeded": 480})
    append_coverage_csv(csv_path, done)

    backfill_coverage_csv(csv_path, coverage_dir)
    df = pd.read_csv(csv_path)
    assert len(df) == 2  # the already-recorded one plus the crashed one
    assert set(df["status"]) == {"completed", "interrupted"}

    # Idempotent: a second backfill appends nothing.
    backfill_coverage_csv(csv_path, coverage_dir)
    assert len(pd.read_csv(csv_path)) == 2


def test_backfill_coverage_csv_noop_without_dir_or_files(tmp_path):
    csv_path = tmp_path / "collection_windows.csv"
    backfill_coverage_csv(csv_path, tmp_path / "missing")  # no dir: no-op
    assert not csv_path.exists()
    empty = tmp_path / "empty"
    empty.mkdir()
    backfill_coverage_csv(csv_path, empty)  # no JSONs: no-op
    assert not csv_path.exists()


def test_check_single_instance_claims_when_claimed_pid_dead(tmp_path):
    """A stale claim (dead pid, any start time) is overwritten, not honored."""
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text("999999\n1\n", encoding="utf-8")
    _check_single_instance(pid_file)
    lines = pid_file.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == str(os.getpid())
    assert len(lines) == 2


def test_check_single_instance_refuses_when_claim_matches_self(tmp_path):
    """A live pid with a matching start time means a collector is running."""
    pid_file = tmp_path / "collector.pid"
    start = _pid_start_time(os.getpid())
    assert start is not None
    pid_file.write_text(f"{os.getpid()}\n{start:.0f}\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        _check_single_instance(pid_file)


def test_check_single_instance_refuses_legacy_single_line_claim(tmp_path):
    """A legacy pid-only claim is honored when the pid is alive."""
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    with pytest.raises(SystemExit):
        _check_single_instance(pid_file)


def test_check_single_instance_overwrites_recycled_pid(tmp_path):
    """A live pid whose start time does NOT match is a recycled pid: overwrite."""
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text(f"{os.getpid()}\n1\n", encoding="utf-8")  # start 1s epoch
    _check_single_instance(pid_file)
    assert pid_file.read_text(encoding="utf-8").strip().splitlines()[0] == str(
        os.getpid()
    )


def test_check_single_instance_overwrites_garbage(tmp_path):
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text("not-a-pid\n", encoding="utf-8")
    _check_single_instance(pid_file)
    assert pid_file.read_text(encoding="utf-8").strip().splitlines()[0] == str(
        os.getpid()
    )


def test_collect_window_tracks_stats_and_writes_coverage(tmp_path, monkeypatch):
    """Coverage stats count failed and successful polls and are rewritten per poll."""
    import scripts.collect_service as cs

    out = tmp_path / "obs.csv"
    vp_out = tmp_path / "vp.json"
    coverage_out = tmp_path / "window.json"
    deadline = time.time() + 0.3
    stats = _window_stats(
        datetime.now(), datetime.now() + timedelta(minutes=30), (360, 540)
    )

    class _Resp:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

    class _FlakyClient:
        """First TripUpdates poll fails (router still off), then all succeed."""

        def __init__(self):
            self.failed = False

        def get(self, url, timeout=None):
            if url == cs.config.MIWAY_GTFSRT_TRIP_UPDATES and not self.failed:
                self.failed = True
                raise OSError("router off")
            return _Resp(b"data")

    monkeypatch.setattr(
        cs,
        "_miway_lateness_rows",
        lambda *a: [
            {
                "route_short_name": "1",
                "stop_id": "a",
                "dep_time_min": 410.0,
                "lateness_minutes": 1.0,
                "horizon_minutes": -1.0,
            }
        ],
    )
    monkeypatch.setattr(
        cs, "decode_miway_vehicle_positions", lambda raw: [{"trip_id": "1"}]
    )

    returned = cs.collect_window(
        _FlakyClient(),
        ({}, ({}, {})),
        out,
        interval=0.05,
        window_s=1800,
        deadline=deadline,
        vp_out=vp_out,
        coverage=stats,
        coverage_out=coverage_out,
    )

    assert returned is stats
    assert stats["polls_attempted"] >= 2
    assert stats["polls_failed"] == 1
    assert stats["polls_succeeded"] >= 1
    assert stats["first_poll_at"] is not None
    assert stats["last_poll_at"] is not None
    assert stats["observations"] >= 1
    assert stats["vp_snapshots"] >= 1
    # the coverage JSON was rewritten with the running stats
    data = json.loads(coverage_out.read_text(encoding="utf-8"))
    assert data["polls_failed"] == 1
    assert data["status"] == "collecting"  # finalized only by the caller


def test_run_with_deadline_completes_and_abandons():
    """The watchdog returns True when the fn finishes quickly and False when a
    blocking fn exceeds its budget (the abandoned poll is the self-heal)."""
    import scripts.collect_service as cs

    assert cs._run_with_deadline(lambda: None, 1.0) is True
    # a fn that outlives its budget must be abandoned, not waited on forever
    assert cs._run_with_deadline(lambda: time.sleep(5), 0.1) is False


def test_run_with_deadline_reraises_completed_exception():
    """A fn that finishes in time but raises must propagate its exception, so
    the caller still marks a genuinely failed window interrupted."""
    import scripts.collect_service as cs

    def _boom():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        cs._run_with_deadline(_boom, 1.0)


def test_collect_window_abandons_blocked_poll(tmp_path, monkeypatch):
    """A poll that blocks past the per-poll timeout is abandoned and the
    collector moves on to the next poll instead of freezing the whole
    window -- the hard self-heal (REDFLAG §21 hang class)."""
    import scripts.collect_service as cs

    out = tmp_path / "obs.csv"
    deadline = time.time() + 0.6
    attempted = {"times": 0}

    class _BlockingClient:
        def get(self, url, timeout=None):
            attempted["times"] += 1
            time.sleep(30)  # simulate a truly-blocked call (stalled DNS / lock)
            raise AssertionError("should never return")

    monkeypatch.setattr(cs, "_miway_lateness_rows", lambda *a: [])
    monkeypatch.setenv("MIWAY_COLLECT_POLL_TIMEOUT", "0.15")
    stats = cs._window_stats(datetime.now(), datetime.now(), (360, 540))

    # must return before the deadline despite every poll blocking
    cs.collect_window(
        _BlockingClient(),
        ({}, ({}, {})),
        out,
        interval=0.05,
        window_s=1800,
        deadline=deadline,
        coverage=stats,
    )
    assert attempted["times"] >= 1  # a poll was attempted and abandoned
    assert stats["polls_timeout"] >= 1
    assert stats["polls_succeeded"] == 0
    assert stats["polls_attempted"] == stats["polls_timeout"]


def test_setup_file_logging_writes_to_rotating_file(tmp_path):
    """Console lines are teed verbatim into a collector.log for post-mortems,
    while still reaching the original stream."""
    import scripts.collect_service as cs

    log_path = tmp_path / "collector.log"
    buf = io.StringIO()
    wrapped = cs.setup_file_logging(log_path, streams=[buf])
    wrapped[0].write("hello poll\n")
    wrapped[0].flush()

    assert "hello poll" in log_path.read_text(encoding="utf-8")


def test_crash_hook_writes_traceback_to_stderr(tmp_path, monkeypatch):
    """An uncaught exception routed through ``_crash_hook`` leaves a full
    traceback plus a clear marker on the (tee'd) stderr -- i.e. collector.log
    catches a death that otherwise produces no evidence."""
    import scripts.collect_service as cs

    buf = io.StringIO()
    monkeypatch.setattr("sys.stderr", buf)

    def _boom() -> None:
        raise ValueError("boom mid-window")

    try:
        _boom()
    except ValueError:
        cs._crash_hook(*sys.exc_info())

    out = buf.getvalue()
    assert "=== COLLECTOR CRASH" in out
    assert "ValueError: boom mid-window" in out
    assert "_boom" in out  # the raising frame is in the traceback
    assert buf.getvalue().endswith("\n")  # console passthrough preserved


# ---------------------------------------------------------------------------
# Single-instance claim lock (double-start race, seen live Sep 1 + Sep 3)
# ---------------------------------------------------------------------------


def test_check_single_instance_waits_for_claim_lock(tmp_path):
    """A contender must not claim while another holds the claim lock.

    Regression for the double-collector race: the watchdog trigger and the
    logon task both reviving after a reboot each read the same empty pid
    file, both pass, and both poll (double observations + conflicting
    coverage rows). The check-and-claim now runs under a cross-process lock,
    so a second start that arrives mid-claim must refuse instead of racing
    through the check.

    Same-process threads can't play the loser role end-to-end (the second
    thread sees its own pid and the recycled-pid start-time check treats it
    as stale — correct for real distinct pids), so this pins the lock
    semantics directly: while the lock is held, check refuses; once
    released, check claims.
    """
    pid_file = tmp_path / "collector.pid"

    # Simulate a first collector mid-claim: it holds the lock while it does
    # its check + write.
    holder = _claim_lock(pid_file)
    try:
        try:
            _check_single_instance(pid_file, lock_wait=0.5)
            raised = False
        except SystemExit:
            raised = True
        assert raised, "contender must refuse while the lock is held"
        assert not pid_file.exists(), "refused contender must not have claimed"
    finally:
        if os.name == "nt":
            import msvcrt

            holder.seek(0)
            msvcrt.locking(holder.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
        holder.close()

    # Lock released: the claim now goes through and records this process.
    _check_single_instance(pid_file, lock_wait=5.0)
    assert pid_file.read_text().strip().splitlines()[0] == str(os.getpid())


def test_claim_lock_is_reentrant_across_restarts(tmp_path):
    """A released lock must be acquirable by the next start (no leaks)."""
    for _ in range(3):
        lock = _claim_lock(tmp_path / "collector.pid")
        lock.close()  # restart path: process exits, OS drops the lock


def test_dedup_coverage_csv_keeps_best_row_per_window(tmp_path):
    """A revived collector's complete row must beat a dead process's stub.

    Sep 1 evening: the revived process wrote the real 440-poll completed row
    while the dead one's 7-poll stub sat in the CSV; the old first-wins dedup
    kept the stub, so the coverage tab under-reported a mostly-collected day.
    """
    from scripts.collect_service import dedup_coverage_csv

    csv_path = tmp_path / "collection_windows.csv"
    header = (
        "date,window_start,window_end,scheduled,status,polls_attempted,"
        "polls_succeeded,polls_failed,first_poll_at,last_poll_at,"
        "observations,vp_snapshots,alerts,longest_gap_min,polls_timeout"
    )
    dead_stub = (
        "2026-09-01,2026-09-01 20:00:21,2026-09-02 00:00:00,19:00-24:00,"
        "interrupted,7,7,0,2026-09-01 20:00:22,2026-09-01 20:03:00,35259,7,0,0,0"
    )
    revived_complete = (
        "2026-09-01,2026-09-01 20:00:44,2026-09-02 00:00:00,19:00-24:00,"
        "completed,440,440,0,2026-09-01 20:00:45,2026-09-01 23:59:30,"
        "1633961,440,76,1.4,0"
    )
    csv_path.write_text(
        "\n".join([header, dead_stub, revived_complete]) + "\n", encoding="utf-8"
    )
    dedup_coverage_csv(csv_path)
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # header + one winner
    assert "440" in lines[1] and "completed" in lines[1]


def test_dedup_coverage_csv_preserves_distinct_windows(tmp_path):
    """Rows for genuinely different windows must all survive dedup."""
    from scripts.collect_service import dedup_coverage_csv

    csv_path = tmp_path / "collection_windows.csv"
    header = (
        "date,window_start,window_end,scheduled,status,polls_attempted,"
        "polls_succeeded,polls_failed,first_poll_at,last_poll_at,"
        "observations,vp_snapshots,alerts,longest_gap_min,polls_timeout"
    )
    row_a = (
        "2026-09-01,2026-09-01 06:03:03,2026-09-01 09:00:00,06:00-09:00,"
        "completed,340,340,0,x,y,2308941,340,0,0,0"
    )
    row_b = (
        "2026-09-01,2026-09-01 15:06:53,2026-09-01 19:00:00,15:00-19:00,"
        "interrupted,385,385,0,x,y,2655574,385,0,0,0"
    )
    csv_path.write_text("\n".join([header, row_a, row_b]) + "\n", encoding="utf-8")
    dedup_coverage_csv(csv_path)
    assert len(csv_path.read_text().strip().splitlines()) == 3


# ---------------------------------------------------------------------------
# Post-window analysis: the incremental --since cursor must not advance past
# a failed run (the Sep 2 failure class: --since killed scripts, cursor moved)
# ---------------------------------------------------------------------------


def test_run_analysis_reports_all_success(tmp_path, monkeypatch):
    """All scripts exit 0 -> run_analysis returns True -> cursor may advance."""

    def _ok(cmd, cwd=None, capture_output=False, text=False, timeout=None):
        return subprocess.CompletedProcess(cmd, 0, stdout="wrote", stderr="")

    monkeypatch.setattr("scripts.collect_service.subprocess.run", _ok)
    monkeypatch.setattr("scripts.collect_service.sys.executable", "py")
    assert run_analysis(interval=30.0) is True


def test_run_analysis_reports_failure(tmp_path, monkeypatch):
    """A script exiting nonzero (or raising) -> False -> cursor must hold."""

    def _fail(cmd, cwd=None, capture_output=False, text=False, timeout=None):
        return subprocess.CompletedProcess(
            cmd, 2, stdout="", stderr="error: unrecognized arguments: --since"
        )

    monkeypatch.setattr("scripts.collect_service.subprocess.run", _fail)
    monkeypatch.setattr("scripts.collect_service.sys.executable", "py")
    assert run_analysis(interval=30.0) is False


def test_run_analysis_one_failure_poisons_the_batch(tmp_path, monkeypatch):
    """6 of 7 succeed but 1 fails -> False: the cursor gates on ALL."""
    codes = {"weekly_rollup.py": 1}

    def _mixed(cmd, cwd=None, capture_output=False, text=False, timeout=None):
        name = Path(cmd[1]).name
        return subprocess.CompletedProcess(
            cmd, codes.get(name, 0), stdout="w", stderr=""
        )

    monkeypatch.setattr("scripts.collect_service.subprocess.run", _mixed)
    monkeypatch.setattr("scripts.collect_service.sys.executable", "py")
    assert run_analysis(interval=30.0) is False


def test_check_single_instance_claim_is_creation_time_not_write_time(tmp_path):
    """The claim must store the process creation time, not time.time().

    Regression for the Sep 3-4 2026 double collector: the claim used to
    record time.time() at claim-write (~20s after process birth, after the
    pandas import), while the check compares it against the claimed pid's
    creation time with a 10s tolerance. A second slow-starting collector
    therefore "mismatched" the live claim and started anyway.
    """
    pid_file = tmp_path / "collector.pid"
    _check_single_instance(pid_file)
    claimed_start = float(pid_file.read_text(encoding="utf-8").splitlines()[1])
    own_start = _pid_start_time(os.getpid())
    assert own_start is not None
    # Must match the process creation time, not the (later) write time.
    assert abs(claimed_start - own_start) < 10


def test_split_brain_guard_blocks_other_home(tmp_path, monkeypatch, capsys):
    """A live collector under ANOTHER data home must block a new start.

    Sep 6 2026: the config migration half-cutover ran two collectors against
    two homes for ~2 minutes because the single-instance lock is per-home.
    The guard checks alternate homes' pid files with the same creation-time
    match as the same-home check.
    """
    from scripts import collect_service as cs

    my_home = tmp_path / "home_a"
    other_home = tmp_path / "home_b"
    my_home.mkdir()
    other_home.mkdir()
    my_pid = my_home / "collector.pid"
    other_pid = other_home / "collector.pid"

    start = time.time()
    other_pid.write_text(f"{os.getpid()}\n{start}\n", encoding="utf-8")
    monkeypatch.setattr(cs, "_alternate_pid_files", lambda pf: [other_pid])
    # Deterministic liveness: the guard's _pid_alive/_pid_start_time shell
    # out to WMI subprocess probes, which are slow and flaky under xdist
    # load (a timed-out probe reads as "not alive" and the guard skips).
    # The guard's OWN logic is what this test pins; liveness probing is
    # stubbed to the same contract the live probe fulfills.
    monkeypatch.setattr(cs, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(cs, "_pid_start_time", lambda pid: start)
    with pytest.raises(SystemExit), capsys.disabled():
        cs._check_no_split_brain(my_pid)
    # The guard prints its reason and exits 0 (a skipped start is recoverable).


def test_split_brain_guard_ignores_stale_or_dead(tmp_path, monkeypatch):
    from scripts import collect_service as cs

    my_pid = tmp_path / "home_a" / "collector.pid"
    my_pid.parent.mkdir(parents=True)
    dead_pid_file = tmp_path / "home_b" / "collector.pid"
    dead_pid_file.parent.mkdir(parents=True)
    # pid 999999 is safely beyond any real pid on a dev box
    dead_pid_file.write_text("999999\n1.0\n", encoding="utf-8")
    monkeypatch.setattr(cs, "_alternate_pid_files", lambda pf: [dead_pid_file])
    cs._check_no_split_brain(my_pid)  # must not raise


def test_drop_malformed_rows_removes_double_trigger_fragments(tmp_path):
    """Sep 2/4 double-trigger interleaving left rows shifted one field over
    (lateness_minutes holding a date). They poison every reader's dtypes
    and can never dedup; the window-end sweep must drop them."""
    from scripts.collect_service import drop_malformed_rows

    df = pd.DataFrame(
        {
            "route_short_name": ["3", "0", "263.0", "441.0"],
            "stop_id": ["1042", "-3.93", "263.0", "-12.67"],
            "dep_time_min": ["410", "15.85", "9.08", "19.25"],
            "lateness_minutes": ["1.5", "2026-09-02", "9.08", "2026-09-04"],
            "horizon_minutes": ["-30", "", "-12", ""],
            "date": ["20260901", "", "20260904", ""],
        }
    )
    out = drop_malformed_rows(df, "obs_lateness.csv")
    assert len(out) == 2
    assert set(out["lateness_minutes"]) == {"1.5", "9.08"}
    # idempotent
    assert len(drop_malformed_rows(out, "obs_lateness.csv")) == 2


def test_dedup_csv_normalizes_format_eras_and_keeps_padding(tmp_path):
    """The window-end rewrite heals the two format eras without identity damage.

    Regression for the 2026-09-04 probe that caught the missing dtype pin:
    reading stop_id unpadded parsed the feed's "0001" as 1 BEFORE
    normalization, collapsing two distinct stops. Cross-format duplicates
    ("1042.0" vs "1042") must collapse; "0001" and "1" must stay distinct.
    """
    out = tmp_path / "obs.csv"
    rows = [
        ("1", "1042.0", "410.0", "1.5", "-1.0", "20260901"),  # float era
        ("1", "1042", "410", "2.0", "-3.0", "20260901"),  # int era, same dep
        ("1", "0001", "555.0", "0.5", "-2.0", "20260901"),  # padded
        ("1", "0001", "555", "3.0", "-5.0", "20260901"),  # padded, int era
        ("1", "1", "600.0", "1.0", "-1.0", "20260901"),  # unpadded 1: distinct
        ("2", "777.0", "300.0", "1.0", "-0.5", "20260902"),  # other day
    ]
    out.write_text(
        "route_short_name,stop_id,dep_time_min,lateness_minutes,horizon_minutes,date\n"
        + "".join(",".join(r) + "\n" for r in rows),
        encoding="utf-8",
    )
    dedup_csv(out)
    df = pd.read_csv(out, dtype={"route_short_name": str, "stop_id": str, "date": str})
    assert len(df) == 4
    assert set(df["stop_id"]) == {"1042", "0001", "1", "777"}
    assert not df["stop_id"].str.endswith(".0").any()
    assert (df["date"] == "20260902").sum() == 1  # other-day row survives
