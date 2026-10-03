"""Tests for ``scripts/sync_canary.py`` — the T104 Syncthing canary decision.

Covers beat parsing, never-seen conservatism, the 30-minute stall budget,
the recover/quiet states, re-alert cadence, and the state sub-dict shape.
"""

from __future__ import annotations

import time

from scripts import sync_canary as sc

NOW = 1_800_000_000.0


def _write_beat(tmp_path, age_s: float) -> None:
    beat = tmp_path / "sync_canary"
    beat.mkdir(exist_ok=True)
    (beat / "beat.txt").write_text(f"{NOW - age_s:.0f}\n", encoding="utf-8")


def test_parse_beat_tolerates_whitespace():
    assert sc.parse_beat(" 1800000000\n") == 1_800_000_000.0
    assert sc.parse_beat("garbage") is None
    assert sc.parse_beat("") is None


def test_never_seen_stays_quiet(tmp_path):
    _write_beat(tmp_path, 0)
    (tmp_path / "sync_canary" / "beat.txt").unlink()
    r = sc.evaluate(tmp_path / "sync_canary" / "beat.txt", {}, now=NOW)
    assert r["status"] == "never-seen" and r["line"] is None


def test_fresh_beat_is_quiet(tmp_path):
    _write_beat(tmp_path, 120)  # 2 min old
    r = sc.evaluate(tmp_path / "sync_canary" / "beat.txt", {}, now=NOW)
    assert r["status"] == "quiet" and r["line"] is None


def test_stale_beat_alerts_first(tmp_path):
    _write_beat(tmp_path, 45 * 60)  # 45 min
    r = sc.evaluate(tmp_path / "sync_canary" / "beat.txt", {}, now=NOW)
    assert r["status"] == "alert" and r["first"] and r["re_alert"]
    assert "SYNC STALL" in r["line"]
    assert r["state"]["stalled"] is True


def test_recover_clears_state(tmp_path):
    _write_beat(tmp_path, 10 * 60)  # fresh again after a stall
    stalled = {"canary": {"stalled": True, "stall_epoch": NOW - 3600}}
    r = sc.evaluate(tmp_path / "sync_canary" / "beat.txt", stalled, now=NOW)
    assert r["status"] == "recover" and "RECOVERED" in r["line"]
    assert r["state"] == {}


def test_re_alert_respects_cadence(tmp_path):
    _write_beat(tmp_path, 90 * 60)
    stalled = {
        "canary": {
            "stalled": True,
            "stall_epoch": NOW - 5400,
            "last_alert_epoch": NOW - 10 * 60,  # 10 min ago: cadence not elapsed
        }
    }
    r = sc.evaluate(tmp_path / "sync_canary" / "beat.txt", stalled, now=NOW)
    assert r["status"] == "alert" and not r["re_alert"]
    stalled["canary"]["last_alert_epoch"] = NOW - 3 * 3600  # 3h ago: due
    r = sc.evaluate(tmp_path / "sync_canary" / "beat.txt", stalled, now=NOW)
    assert r["status"] == "alert" and r["re_alert"]


def test_default_stall_budget_is_30_minutes(tmp_path):
    _write_beat(tmp_path, 29 * 60)
    p = tmp_path / "sync_canary" / "beat.txt"
    assert sc.evaluate(p, {}, now=NOW)["status"] == "quiet"
    _write_beat(tmp_path, 31 * 60)
    assert sc.evaluate(p, {}, now=NOW)["status"] == "alert"


def test_beat_age_never_negative_and_uses_real_clock(tmp_path):
    _write_beat(tmp_path, -60)  # beat 1 min in the future (clock skew)
    p = tmp_path / "sync_canary" / "beat.txt"
    age = sc.beat_age_seconds(p)
    assert age == 0.0 or 0 <= age < 120  # real-clock call clamps to 0-ish
    assert sc.beat_age_seconds(p, now=time.time()) >= 0
