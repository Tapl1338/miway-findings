"""Tests for ``/api/collector-status`` — post-cloud-cutover delegation.

The endpoint used to read a local heartbeat file that nothing has written
since the 2026-09-09 VPS cutover, so a healthy cloud collector rendered
"heartbeat stale — age unknown". It now delegates to the coverage router's
``_collector_status`` (a cloud-stamped window within the staleness budget
IS a live collector) and derives banner age from the writer's own
``last_poll_at`` stamp instead of a synced file's mtime.
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.main import app
from app.routers import coverage

client = TestClient(app)
TOR = ZoneInfo("America/Toronto")


def _cloud_window(name: str, minutes_ago: float, status: str = "completed") -> dict:
    last = datetime.now(tz=TOR) - timedelta(minutes=minutes_ago)
    stamp = last.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "name": name,
        "date": last.strftime("%Y-%m-%d"),
        "window_start": f"{last.strftime('%Y-%m-%d')} 05:00:00",
        "window_end": f"{last.strftime('%Y-%m-%d')} 06:00:00",
        "scheduled": "05:00-06:00",
        "status": status,
        "first_poll_at": stamp,
        "last_poll_at": stamp,
        "collector_origin": "cloud",
    }


def _write_coverage(tmp_path, windows: list[dict]):
    cov = tmp_path / "coverage"
    cov.mkdir(exist_ok=True)
    for w in windows:
        (cov / f"{w['name']}.json").write_text(json.dumps(w), encoding="utf-8")
    return cov


def _patch_dirs(monkeypatch, cov, pid_file):
    monkeypatch.setattr(coverage, "COVERAGE_DIR", cov)
    monkeypatch.setattr(coverage, "PID_FILE", pid_file)


def test_cloud_collector_fresh(tmp_path, monkeypatch):
    """A cloud-stamped window polled minutes ago = running, not stale."""
    cov = _write_coverage(tmp_path, [_cloud_window("window_a", minutes_ago=2)])
    _patch_dirs(monkeypatch, cov, tmp_path / "collector.pid")

    response = client.get("/api/collector-status")
    assert response.status_code == 200
    result = response.json()

    assert result["ok"] is True
    assert result["stale"] is False
    assert result["running"] is True
    assert result["status"] == "running"
    assert result["collector_origin"] == "cloud"
    assert result["age_s"] is not None and 0 <= result["age_s"] < 600
    assert result["fresh_after_s"] == int(coverage._STALE_MINUTES * 60)
    parsed = datetime.fromisoformat(result["ts"])
    assert parsed.tzinfo is not None


def test_cloud_collector_quiet(tmp_path, monkeypatch):
    """No poll for hours = not ok, with the real age surfaced."""
    cov = _write_coverage(tmp_path, [_cloud_window("window_a", minutes_ago=120)])
    _patch_dirs(monkeypatch, cov, tmp_path / "collector.pid")

    result = client.get("/api/collector-status").json()

    assert result["ok"] is False
    assert result["running"] is False
    assert result["status"] == "stopped"
    assert result["age_s"] is not None and result["age_s"] > 3600


def test_no_windows(tmp_path, monkeypatch):
    """Empty coverage dir = unknown age, banner condition."""
    cov = _write_coverage(tmp_path, [])
    _patch_dirs(monkeypatch, cov, tmp_path / "collector.pid")

    result = client.get("/api/collector-status").json()

    # Coverage-module semantics: stopped and stale are distinct states —
    # stale means *running but quiet*; nothing at all is just "stopped".
    # The banner keys off ok=False either way.
    assert result["ok"] is False
    assert result["stale"] is False
    assert result["status"] == "stopped"
    assert result["age_s"] is None
    assert result["ts"] is None


def test_malformed_window_json(tmp_path, monkeypatch):
    """Unreadable coverage JSON must not raise — report not-ok instead."""
    cov = tmp_path / "coverage"
    cov.mkdir(exist_ok=True)
    (cov / "window_broken.json").write_text("not valid json", encoding="utf-8")
    _patch_dirs(monkeypatch, cov, tmp_path / "collector.pid")

    response = client.get("/api/collector-status")
    assert response.status_code == 200
    result = response.json()
    assert result["ok"] is False
    assert result["age_s"] is None


def test_local_pid_path_still_works(tmp_path, monkeypatch):
    """Pre-cloud topology (local pid + active window) still reads running."""
    soon = datetime.now(tz=TOR) + timedelta(minutes=30)
    window = _cloud_window("window_a", minutes_ago=1)
    window["collector_origin"] = "local"
    window["window_end"] = soon.strftime("%Y-%m-%d %H:%M:%S")
    cov = _write_coverage(tmp_path, [window])
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text("4242\n", encoding="utf-8")
    _patch_dirs(monkeypatch, cov, pid_file)
    monkeypatch.setattr(coverage, "_pid_alive", lambda pid: pid == 4242)

    result = client.get("/api/collector-status").json()

    assert result["running"] is True
    assert result["ok"] is True
    assert result["pid"] == 4242
