"""Tests for the collector freshness watchdog (``scripts/collector_health.py``).

Covers the claim-file parser, the staleness decision (coverage heartbeat),
and the launcher exit-code contract. The kill path is exercised against a
real dummy process on Windows.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from scripts.collector_health import _is_stale, _kill, _read_claim, main

TS = "%Y-%m-%d %H:%M:%S"
FUTURE = (datetime.now() + timedelta(hours=2)).strftime(TS)
PAST = (datetime.now() - timedelta(hours=2)).strftime(TS)


# ---------------------------------------------------------------------------
# _read_claim
# ---------------------------------------------------------------------------


def test_read_claim_missing(tmp_path):
    assert _read_claim(tmp_path / "nope.pid") == (None, None)


def test_read_claim_two_lines(tmp_path):
    f = tmp_path / "collector.pid"
    f.write_text("14176\n1787079129\n", encoding="utf-8")
    assert _read_claim(f) == (14176, 1787079129.0)


def test_read_claim_legacy_single_line(tmp_path):
    f = tmp_path / "collector.pid"
    f.write_text("14176\n", encoding="utf-8")
    assert _read_claim(f) == (14176, None)


def test_read_claim_garbage(tmp_path):
    f = tmp_path / "collector.pid"
    f.write_text("not-a-pid\n", encoding="utf-8")
    assert _read_claim(f) == (None, None)


# ---------------------------------------------------------------------------
# _is_stale  (the coverage-heartbeat decision)
# ---------------------------------------------------------------------------


def _write_coverage(tmp_path: Path, window_end: str, mtime_age_min: float) -> Path:
    p = tmp_path / "window_test.json"
    p.write_text(
        json.dumps({"window_end": window_end, "last_poll_at": "2026-08-18 12:00:00"}),
        encoding="utf-8",
    )
    old = time.time() - mtime_age_min * 60
    os.utime(p, (old, old))
    return p


def test_stale_none_and_missing(tmp_path):
    assert _is_stale(None, datetime.now(), 5.0) is False
    assert _is_stale(tmp_path / "missing.json", datetime.now(), 5.0) is False


def test_stale_future_window_quiet_heartbeat(tmp_path):
    p = _write_coverage(tmp_path, FUTURE, mtime_age_min=10.0)
    assert _is_stale(p, datetime.now(), 5.0) is True


def test_stale_fresh_heartbeat_ok(tmp_path):
    p = _write_coverage(tmp_path, FUTURE, mtime_age_min=0.1)
    assert _is_stale(p, datetime.now(), 5.0) is False


def test_stale_between_windows_never_stale(tmp_path):
    # Window already ended: the collector is meant to sleep, not a stall.
    p = _write_coverage(tmp_path, PAST, mtime_age_min=10.0)
    assert _is_stale(p, datetime.now(), 5.0) is False


def test_stale_malformed_json(tmp_path):
    p = tmp_path / "window_test.json"
    p.write_text("{not json", encoding="utf-8")
    assert _is_stale(p, datetime.now(), 5.0) is False


# ---------------------------------------------------------------------------
# main() exit-code contract
# ---------------------------------------------------------------------------


@pytest.fixture
def health_env(tmp_path, monkeypatch):
    pid_file = tmp_path / "collector.pid"
    coverage_dir = tmp_path / "coverage"
    coverage_dir.mkdir()
    monkeypatch.setenv("MIWAY_COLLECT_PID_FILE", str(pid_file))
    monkeypatch.setenv("MIWAY_COLLECT_COVERAGE_DIR", str(coverage_dir))
    return pid_file, coverage_dir


def test_main_not_running(health_env, monkeypatch):
    pid_file, _cov = health_env
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr("scripts.collector_health._pid_alive", lambda pid: False)
    assert main(["--kill"]) == 1


def test_main_running_fresh(health_env, monkeypatch):
    pid_file, coverage_dir = health_env
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr("scripts.collector_health._pid_alive", lambda pid: True)
    monkeypatch.setattr(
        "scripts.collector_health._pid_start_time", lambda pid: 999999999.0
    )
    _write_coverage(coverage_dir, FUTURE, mtime_age_min=0.1)
    assert main(["--kill"]) == 0


def test_main_stale_without_kill(health_env, monkeypatch):
    pid_file, coverage_dir = health_env
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr("scripts.collector_health._pid_alive", lambda pid: True)
    monkeypatch.setattr(
        "scripts.collector_health._pid_start_time", lambda pid: 999999999.0
    )
    _write_coverage(coverage_dir, FUTURE, mtime_age_min=20.0)
    assert main([]) == 2


def test_main_stale_kill_ok(health_env, monkeypatch):
    pid_file, coverage_dir = health_env
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr("scripts.collector_health._pid_alive", lambda pid: True)
    monkeypatch.setattr(
        "scripts.collector_health._pid_start_time", lambda pid: 999999999.0
    )
    monkeypatch.setattr("scripts.collector_health._kill", lambda pid: True)
    _write_coverage(coverage_dir, FUTURE, mtime_age_min=20.0)
    assert main(["--kill"]) == 2
    assert not pid_file.exists()  # stale claim removed before restart


def test_main_stale_kill_failed(health_env, monkeypatch):
    pid_file, coverage_dir = health_env
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr("scripts.collector_health._pid_alive", lambda pid: True)
    monkeypatch.setattr(
        "scripts.collector_health._pid_start_time", lambda pid: 999999999.0
    )
    monkeypatch.setattr("scripts.collector_health._kill", lambda pid: False)
    _write_coverage(coverage_dir, FUTURE, mtime_age_min=20.0)
    assert main(["--kill"]) == 3


# ---------------------------------------------------------------------------
# _kill against a real process
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name != "nt", reason="taskkill is Windows-only")
def test_kill_real_process():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert _kill(proc.pid) is True
        assert proc.poll() is not None  # terminated
    finally:
        if proc.poll() is None:
            proc.kill()


def test_pid_alive_real_process():
    """Regression (2026-09-02): the collector's ``_pid_alive`` must track a
    process's real lifecycle. On Windows it uses the WMI probe; on POSIX
    ``os.kill``. The repeated ``lambda pid: True`` mocks elsewhere never
    exercised the real function, so an ``os.kill``-reports-dead-as-alive bug
    went unnoticed in a sibling module. Spawn, assert alive, kill, assert
    dead -- portable across both OSes.
    """
    from scripts.collect_service import _pid_alive

    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.5)
        assert _pid_alive(proc.pid) is True
        proc.kill()
        proc.wait()
        time.sleep(0.4)
        assert _pid_alive(proc.pid) is False
    finally:
        if proc.poll() is None:
            proc.kill()
