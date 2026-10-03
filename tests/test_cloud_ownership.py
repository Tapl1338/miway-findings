"""Tests for the 2026-09-09 cloud-cutover guards.

* ``collector_origin`` stamping in coverage payloads (``collect_service.py``)
* ``_check_cloud_ownership`` — a local collector refuses to start while the
  cloud heartbeat is fresh
* ``_cloud_fresh`` + main() exit codes in ``collector_health.py`` — a fresh
  cloud heartbeat reports ``0`` with no local pid, instead of "start one"
"""

import json
from datetime import datetime, timedelta

import pytest
from scripts import collect_service
from scripts.collector_health import _cloud_fresh, main

TS = "%Y-%m-%d %H:%M:%S"
NOW = datetime.now()
FUTURE = (NOW + timedelta(hours=2)).strftime(TS)


def _stamp(coverage_dir, origin, last_poll_min_ago, name="window_test.json"):
    p = coverage_dir / name
    p.write_text(
        json.dumps(
            {
                "window_end": FUTURE,
                "last_poll_at": (NOW - timedelta(minutes=last_poll_min_ago)).strftime(
                    TS
                ),
                "collector_origin": origin,
            }
        ),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def clear_cloud_env(monkeypatch):
    monkeypatch.delenv("MIWAY_CLOUD_COLLECTOR", raising=False)


# ---------------------------------------------------------------------------
# collector_origin stamping
# ---------------------------------------------------------------------------


def test_origin_local_by_default(monkeypatch):
    monkeypatch.delenv("MIWAY_CLOUD_COLLECTOR", raising=False)
    assert collect_service.collector_origin() == "local"


def test_origin_cloud_when_env_set(monkeypatch):
    monkeypatch.setenv("MIWAY_CLOUD_COLLECTOR", "1")
    assert collect_service.collector_origin() == "cloud"


def test_window_stats_carries_origin(monkeypatch):
    monkeypatch.delenv("MIWAY_CLOUD_COLLECTOR", raising=False)
    win = (6 * 60, 9 * 60)
    stats = collect_service._window_stats(NOW, NOW + timedelta(hours=3), win)
    assert stats["collector_origin"] == "local"


def test_coverage_columns_include_origin():
    assert "collector_origin" in collect_service.COVERAGE_COLUMNS


# ---------------------------------------------------------------------------
# _check_cloud_ownership (start-side guard)
# ---------------------------------------------------------------------------


def test_local_start_blocked_by_fresh_cloud_heartbeat(tmp_path, clear_cloud_env):
    _stamp(tmp_path, "cloud", last_poll_min_ago=2)
    with pytest.raises(SystemExit) as exc:
        collect_service._check_cloud_ownership(tmp_path)
    assert exc.value.code == 0


def test_local_start_allowed_when_cloud_heartbeat_stale(tmp_path, clear_cloud_env):
    _stamp(tmp_path, "cloud", last_poll_min_ago=45)
    collect_service._check_cloud_ownership(tmp_path)  # no exit


def test_local_start_allowed_when_origin_local(tmp_path, clear_cloud_env):
    _stamp(tmp_path, "local", last_poll_min_ago=1)
    collect_service._check_cloud_ownership(tmp_path)  # no exit


def test_cloud_collector_exempt_from_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("MIWAY_CLOUD_COLLECTOR", "1")
    _stamp(tmp_path, "cloud", last_poll_min_ago=0.1)
    collect_service._check_cloud_ownership(tmp_path)  # no exit


def test_guard_tolerates_missing_or_corrupt_coverage(tmp_path, clear_cloud_env):
    collect_service._check_cloud_ownership(tmp_path)  # no dir: no exit
    bad = tmp_path / "window_bad.json"
    bad.write_text("not json{", encoding="utf-8")
    collect_service._check_cloud_ownership(tmp_path)  # corrupt: no exit


# ---------------------------------------------------------------------------
# _cloud_fresh + main() (health check side)
# ---------------------------------------------------------------------------


def test_cloud_fresh_true_within_window(tmp_path):
    _stamp(tmp_path, "cloud", last_poll_min_ago=3)
    assert _cloud_fresh(tmp_path, NOW, 15.0) is True


def test_cloud_fresh_false_when_stale(tmp_path):
    _stamp(tmp_path, "cloud", last_poll_min_ago=40)
    assert _cloud_fresh(tmp_path, NOW, 15.0) is False


def test_cloud_fresh_false_for_local_origin(tmp_path):
    _stamp(tmp_path, "local", last_poll_min_ago=1)
    assert _cloud_fresh(tmp_path, NOW, 15.0) is False


def test_health_reports_cloud_when_no_local_pid(tmp_path, monkeypatch, clear_cloud_env):
    pid_file = tmp_path / "collector.pid"
    coverage_dir = tmp_path / "coverage"
    coverage_dir.mkdir()
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setenv("MIWAY_COLLECT_PID_FILE", str(pid_file))
    monkeypatch.setenv("MIWAY_COLLECT_COVERAGE_DIR", str(coverage_dir))
    monkeypatch.setattr("scripts.collector_health._pid_alive", lambda pid: False)
    _stamp(coverage_dir, "cloud", last_poll_min_ago=2)
    assert main(["--kill"]) == 0


def test_health_still_reports_start_when_no_cloud_heartbeat(
    tmp_path, monkeypatch, clear_cloud_env
):
    pid_file = tmp_path / "collector.pid"
    coverage_dir = tmp_path / "coverage"
    coverage_dir.mkdir()
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setenv("MIWAY_COLLECT_PID_FILE", str(pid_file))
    monkeypatch.setenv("MIWAY_COLLECT_COVERAGE_DIR", str(coverage_dir))
    monkeypatch.setattr("scripts.collector_health._pid_alive", lambda pid: False)
    assert main(["--kill"]) == 1
