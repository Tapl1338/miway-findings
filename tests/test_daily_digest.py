"""Tests for the digest's nightly-backup check.

The 02:10 backup has no other morning-visible signal: the scheduled task
writes nothing an analyst reads. ``_check_backup`` in the digest is what
surfaces a failed or missing backup at 06:15.
"""

from __future__ import annotations

import os
import sys
import time
import types
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import daily_digest


@pytest.fixture()
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the digest's config.DATA_DIR and backup dir at temp locations."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(daily_digest.config, "DATA_DIR", data_dir)
    monkeypatch.setenv("MIWAY_BACKUP_DIR", str(tmp_path / "backup"))
    return tmp_path


def _write_log(tmp_path: Path, body: str) -> Path:
    log_dir = tmp_path / "logs"
    log_dir.mkdir(exist_ok=True)
    log = log_dir / "backup_last.log"
    log.write_text(body, encoding="utf-8")
    return log


def test_ok_when_log_records_success(isolated: Path) -> None:
    _write_log(
        isolated,
        "=== backup run 2026-09-04 02:10:01 ===\n"
        "collections robocopy rc=1 \n"
        "Backup OK: snapshots=1 coverage=1 derived=3 \n",
    )
    ok, detail = daily_digest._check_backup()
    assert ok is True
    assert detail == "ok"


def test_failed_when_log_records_failure(isolated: Path) -> None:
    _write_log(
        isolated,
        "=== backup run 2026-09-04 02:10:01 ===\nBACKUP FAILED: derived copy rc=16 \n",
    )
    ok, detail = daily_digest._check_backup()
    assert ok is False
    assert "FAILED" in detail
    assert "backup_last.log" in detail


def test_latest_run_wins_over_older_failure(isolated: Path) -> None:
    _write_log(
        isolated,
        "=== backup run 2026-09-03 02:10:01 ===\n"
        "BACKUP FAILED: derived copy rc=16 \n"
        "=== backup run 2026-09-04 02:10:01 ===\n"
        "Backup OK: snapshots=1 coverage=1 derived=3 \n",
    )
    ok, _detail = daily_digest._check_backup()
    assert ok is True


def test_missing_log_fresh_backup_dir_passes(isolated: Path) -> None:
    backup = Path(os.environ["MIWAY_BACKUP_DIR"])
    sub = backup / "collections"
    sub.mkdir(parents=True)
    (sub / "vp_20260904_0210.json").write_text("{}", encoding="utf-8")
    ok, _detail = daily_digest._check_backup()
    assert ok is True


def test_missing_log_stale_backup_dir_fails(isolated: Path) -> None:
    backup = Path(os.environ["MIWAY_BACKUP_DIR"])
    backup.mkdir()
    stale = backup / "obs_lateness.csv"
    stale.write_text("x", encoding="utf-8")
    old = time.time() - 48 * 3600
    os.utime(stale, (old, old))
    ok, detail = daily_digest._check_backup()
    assert ok is False
    assert "did not run" in detail or "copied nothing" in detail


def test_missing_log_absent_backup_dir_fails(isolated: Path) -> None:
    ok, detail = daily_digest._check_backup()
    assert ok is False
    assert "does not exist" in detail


# --- scheduled-task launch-failure check -----------------------------------


def _fake_pscall(stdout: str, returncode: int = 0):
    """Build a stand-in for subprocess.run returning canned PowerShell output."""

    def fake(*args, **kwargs):
        r = types.SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)
        return r

    return fake


def test_task_failures_empty_when_no_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(daily_digest.subprocess, "run", _fake_pscall(""))
    assert daily_digest._check_task_failures() == []


def test_task_failures_flags_203(monkeypatch: pytest.MonkeyPatch) -> None:
    out = '2026-09-05 02:10:01|203|failed to launch action "C:\\...\\backup_data.bat" in task "MiWayDataBackup".'
    monkeypatch.setattr(daily_digest.subprocess, "run", _fake_pscall(out + "\n"))
    findings = daily_digest._check_task_failures()
    assert len(findings) == 1
    assert "203" in findings[0]
    assert "MiWayDataBackup" in findings[0]


def test_task_failures_flags_204(monkeypatch: pytest.MonkeyPatch) -> None:
    out = '2026-09-05 07:30:00|204|failed to retrieve the event triggering values for task "MiWayPostSept7Capture".'
    monkeypatch.setattr(daily_digest.subprocess, "run", _fake_pscall(out + "\n"))
    findings = daily_digest._check_task_failures()
    assert len(findings) == 1
    assert "204" in findings[0]


def test_task_failures_powershell_error_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        daily_digest.subprocess,
        "run",
        _fake_pscall("", returncode=1),
    )
    findings = daily_digest._check_task_failures()
    assert len(findings) == 1
    assert "rc=1" in findings[0]


def test_task_failures_caps_output(monkeypatch: pytest.MonkeyPatch) -> None:
    out = "\n".join(
        f'2026-09-05 0{i % 10}:00:00|203|task "MiWayBad" launch {i}' for i in range(14)
    )
    monkeypatch.setattr(daily_digest.subprocess, "run", _fake_pscall(out))
    findings = daily_digest._check_task_failures()
    assert len(findings) == 11  # 10 shown + truncation note
    assert "more" in findings[-1]


# --- Sept-8 capture watch ---------------------------------------------------


def test_capture_check_silent_outside_window(isolated: Path) -> None:
    ok, _ = daily_digest._check_capture_progress(
        log_path=isolated / "nonexistent.log", today=date(2026, 9, 1)
    )
    assert ok is True


def test_capture_check_fails_when_never_ran_in_window(isolated: Path) -> None:
    ok, detail = daily_digest._check_capture_progress(
        log_path=isolated / "nonexistent.log", today=date(2026, 9, 10)
    )
    assert ok is False
    assert "never run" in detail


def test_capture_check_fails_on_stale_log(isolated: Path) -> None:
    log = isolated / "capture_retry.log"
    log.write_text("verdict: UNCHANGED", encoding="utf-8")
    old = time.time() - 3 * 24 * 3600
    os.utime(log, (old, old))
    ok, detail = daily_digest._check_capture_progress(
        log_path=log, today=date(2026, 9, 10)
    )
    assert ok is False
    assert "not run in over 24h" in detail


def test_capture_check_ok_on_fresh_log(isolated: Path) -> None:
    log = isolated / "capture_retry.log"
    log.write_text("verdict: UNCHANGED", encoding="utf-8")
    ok, _ = daily_digest._check_capture_progress(log_path=log, today=date(2026, 9, 10))
    assert ok is True


# --- alert-join receipt ------------------------------------------------------


def test_alert_join_ok_when_yesterday_receipt_exists(isolated: Path) -> None:
    runs = isolated / "runs"
    runs.mkdir()
    (runs / "alert-join-20260909.md").write_text("# receipt", encoding="utf-8")
    ok, _ = daily_digest._check_alert_join_receipt(
        docs_runs=runs, today=date(2026, 9, 10)
    )
    assert ok is True


def test_alert_join_flags_missing_yesterday_receipt(isolated: Path) -> None:
    runs = isolated / "runs"
    runs.mkdir()
    # Today's receipt exists; yesterday's (the checked one) does not.
    (runs / "alert-join-20260910.md").write_text("# receipt", encoding="utf-8")
    ok, detail = daily_digest._check_alert_join_receipt(
        docs_runs=runs, today=date(2026, 9, 10)
    )
    assert ok is False
    assert "alert-join-20260909.md" in detail


def test_battery_trend_renders_slope(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two+ days of snapshots render a capacity slope and cycle delta."""
    win = tmp_path / "windows"
    win.mkdir()
    monkeypatch.setattr(daily_digest, "__file__", str(tmp_path / "daily_digest.py"))
    # _battery_trend resolves the CSV relative to the script dir; place it.
    real_windows = Path(daily_digest.__file__).parent / "windows"
    real_windows.mkdir(exist_ok=True)
    csv_path = real_windows / "battery_health.csv"
    backup = csv_path.read_text() if csv_path.exists() else None
    try:
        csv_path.write_text(
            "date,timestamp,design_mwh,full_mwh,health_pct,cycle_count,charge_pct\n"
            "2026-09-01,x,59007,60600,102.70,17,85\n"
            "2026-09-06,x,59007,60528,102.58,19,79\n",
            encoding="ascii",
        )
        out = "\n".join(daily_digest._battery_trend())
        assert "## Battery health (collector host)" in out
        assert "102.6%" in out
        assert "-0.1 pp" in out
        assert "cycles 19" in out
    finally:
        if backup is not None:
            csv_path.write_text(backup, encoding="ascii")
        else:
            csv_path.unlink(missing_ok=True)


def test_battery_trend_silent_below_two_days(tmp_path) -> None:
    """A single snapshot has no slope; the section must not render."""
    from pathlib import Path as _P

    real_windows = _P(daily_digest.__file__).parent / "windows"
    real_windows.mkdir(exist_ok=True)
    csv_path = real_windows / "battery_health.csv"
    backup = csv_path.read_text() if csv_path.exists() else None
    try:
        csv_path.write_text(
            "date,timestamp,design_mwh,full_mwh,health_pct,cycle_count,charge_pct\n"
            "2026-09-06,x,59007,60528,102.58,19,79\n",
            encoding="ascii",
        )
        assert daily_digest._battery_trend() == []
    finally:
        if backup is not None:
            csv_path.write_text(backup, encoding="ascii")
        else:
            csv_path.unlink(missing_ok=True)
