"""Tests for ``scripts/analysis_staleness.py`` — the catch-up watchdog.

Covers the cursor/snapshot lag math, the fresh vs stale decision, the
battery defer, and the subprocess wiring (mocked; the real analysis chain
is exercised by run_daily_analysis.ps1 in production).
"""

import time
from pathlib import Path

import pytest
from scripts import analysis_staleness as st


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fake data home with collections/ and the cursor file."""
    d = tmp_path / "home"
    (d / "collections").mkdir(parents=True)
    (d / "logs").mkdir()
    monkeypatch.setenv("MIWAY_DATA_DIR", str(d))
    return d


def _snapshot(home: Path, age_s: float, name="vp_20260909_1900.json") -> Path:
    coll = home / "collections"
    coll.mkdir(parents=True, exist_ok=True)
    p = coll / name
    p.write_text("{}", encoding="utf-8")
    old = time.time() - age_s
    import os

    os.utime(p, (old, old))
    return p


def _cursor(home: Path, age_s: float) -> None:
    (home / ".last_analysis_ts").write_text(str(time.time() - age_s), encoding="utf-8")


def test_read_cursor_missing(tmp_path):
    assert st._read_cursor(tmp_path / "nope") is None


def test_read_cursor_garbage(tmp_path):
    p = tmp_path / "cursor"
    p.write_text("not-a-number", encoding="utf-8")
    assert st._read_cursor(p) is None


def test_newest_snapshot_none_when_empty(tmp_path):
    assert st._newest_snapshot_mtime(tmp_path) is None


def test_newest_snapshot_picks_max_mtime(tmp_path):
    _snapshot(tmp_path, 3600, "vp_a.json")
    _snapshot(tmp_path, 60, "vp_b.json")
    newest = st._newest_snapshot_mtime(tmp_path / "collections")
    assert newest is not None and time.time() - newest < 120


def test_fresh_when_lag_small(home, capsys):
    _snapshot(home, 60)
    _cursor(home, 120)
    assert st.main([]) == 0
    log = (home / "logs" / "analysis_watchdog.log").read_text(encoding="utf-8")
    assert "fresh:" in log


def test_stale_missing_cursor_triggers_catchup(home, monkeypatch):
    _snapshot(home, 60)
    monkeypatch.setattr(st, "_on_battery", lambda: False)
    calls = {}

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        out = type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        return out

    monkeypatch.setattr(st.subprocess, "run", fake_run)
    assert st.main([]) == 0
    assert any("run_daily_analysis.ps1" in c for c in calls["cmd"])
    log = (home / "logs" / "analysis_watchdog.log").read_text(encoding="utf-8")
    assert "STALE" in log and "cursor missing" in log and "catch-up OK" in log


def test_stale_triggers_catchup_passing_force(home, monkeypatch):
    _snapshot(home, 60)  # snapshot 1 min old
    _cursor(home, 30_000)  # cursor 8.3h behind the snapshot: > 6h default
    monkeypatch.setattr(st, "_on_battery", lambda: False)
    calls = {}

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(st.subprocess, "run", fake_run)
    assert st.main(["--force"]) == 0
    assert "-Force" in calls["cmd"]


def test_battery_defers_without_force(home, monkeypatch):
    _snapshot(home, 60)
    _cursor(home, 30_000)  # 8.3h behind: stale
    monkeypatch.setattr(st, "_on_battery", lambda: True)
    ran = {"called": False}

    def fake_run(cmd, **kw):
        ran["called"] = True
        raise AssertionError("must not run on battery")

    monkeypatch.setattr(st.subprocess, "run", fake_run)
    assert st.main([]) == 2
    assert ran["called"] is False
    log = (home / "logs" / "analysis_watchdog.log").read_text(encoding="utf-8")
    assert "deferring" in log


def test_battery_overridden_by_force(home, monkeypatch):
    _snapshot(home, 60)
    _cursor(home, 30_000)
    monkeypatch.setattr(st, "_on_battery", lambda: True)
    monkeypatch.setattr(
        st.subprocess,
        "run",
        lambda cmd, **kw: type(
            "R", (), {"returncode": 0, "stdout": "", "stderr": ""}
        )(),
    )
    assert st.main(["--force"]) == 0


def test_failed_catchup_returns_1(home, monkeypatch):
    _snapshot(home, 60)
    _cursor(home, 30_000)
    monkeypatch.setattr(st, "_on_battery", lambda: False)
    monkeypatch.setattr(
        st.subprocess,
        "run",
        lambda cmd, **kw: type(
            "R", (), {"returncode": 1, "stdout": "boom", "stderr": ""}
        )(),
    )
    assert st.main([]) == 1
    log = (home / "logs" / "analysis_watchdog.log").read_text(encoding="utf-8")
    assert "catch-up FAILED rc=1" in log


def test_fresh_no_snapshots_is_noop(home):
    assert st.main([]) == 0
    log = (home / "logs" / "analysis_watchdog.log").read_text(encoding="utf-8")
    assert "no synced snapshots" in log


# --- 2026-10-03: the two silences ---------------------------------------
# (1) a catch-up killed mid-run wrote no terminal line at all, so "died" and
#     "never ran" looked identical; (2) repeated battery deferrals logged
#     identically to a normal skip, so 3 days of starvation looked routine.


def test_abandoned_inflight_marker_is_reported_and_cleared(home, monkeypatch):
    """A marker surviving to the next trigger means the last run was killed."""
    _snapshot(home, 60)
    _cursor(home, 30_000)
    marker = home / "logs" / "analysis_catchup.inflight"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("2026-10-01T15:56:57 pid=1234 lag 1143 min\n", encoding="utf-8")

    # Fresh path: the reap still happens and is logged even when nothing else runs.
    _cursor(home, 0)
    assert st.main([]) == 0
    log = (home / "logs" / "analysis_watchdog.log").read_text(encoding="utf-8")
    assert "ABANDONED" in log
    assert "never terminated" in log
    assert not marker.exists(), "marker must be cleared after reporting"


def test_inflight_marker_cleared_on_success(home, monkeypatch):
    _snapshot(home, 60)
    _cursor(home, 30_000)
    monkeypatch.setattr(st, "_on_battery", lambda: False)
    monkeypatch.setattr(
        st.subprocess,
        "run",
        lambda cmd, **kw: type(
            "R", (), {"returncode": 0, "stdout": "ok", "stderr": ""}
        )(),
    )
    assert st.main([]) == 0
    assert not (home / "logs" / "analysis_catchup.inflight").exists()


def test_inflight_marker_cleared_on_failure(home, monkeypatch):
    _snapshot(home, 60)
    _cursor(home, 30_000)
    monkeypatch.setattr(st, "_on_battery", lambda: False)
    monkeypatch.setattr(
        st.subprocess,
        "run",
        lambda cmd, **kw: type(
            "R", (), {"returncode": 1, "stdout": "x", "stderr": ""}
        )(),
    )
    assert st.main([]) == 1
    assert not (home / "logs" / "analysis_catchup.inflight").exists()


def test_reap_returns_false_when_no_marker(home):
    assert (
        st._reap_abandoned(home / "logs" / "nope.inflight", home / "logs" / "l.log")
        is False
    )


def test_single_deferral_does_not_escalate(home, monkeypatch):
    _snapshot(home, 60)
    _cursor(home, 30_000)
    monkeypatch.setattr(st, "_on_battery", lambda: True)
    assert st.main([]) == 2
    log = (home / "logs" / "analysis_watchdog.log").read_text(encoding="utf-8")
    assert "deferring" in log
    assert "ESCALATION" not in log


def test_persistent_deferrals_escalate(home, monkeypatch):
    """Three consecutive deferrals (12h at the 4h cadence) must escalate."""
    _snapshot(home, 60)
    _cursor(home, 30_000)
    monkeypatch.setattr(st, "_on_battery", lambda: True)
    for _ in range(3):
        assert st.main([]) == 2
    log = (home / "logs" / "analysis_watchdog.log").read_text(encoding="utf-8")
    assert "ESCALATION" in log
    assert "consecutive battery deferrals" in log


def test_deferral_streak_resets_after_successful_run(home, monkeypatch):
    _snapshot(home, 60)
    _cursor(home, 30_000)
    monkeypatch.setattr(st, "_on_battery", lambda: True)
    st.main([])
    st.main([])
    log_path = home / "logs" / "analysis_watchdog.log"
    assert st._deferral_streak(log_path) == 2
    log_path.write_text(
        log_path.read_text(encoding="utf-8")
        + "2026-10-03 12:42:39 catch-up OK (100s): x\n",
        encoding="utf-8",
    )
    assert st._deferral_streak(log_path) == 0
