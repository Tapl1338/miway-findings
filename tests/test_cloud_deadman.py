"""Tests for ``scripts/cloud_deadman.py`` — the cloud-collector dead-man's switch.

Covers heartbeat age math, the fresh/dead/unknown decision, toast+log on
alert, cooldown between repeats, and recovery clearing.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from scripts import cloud_deadman as dm

TOR = ZoneInfo("America/Toronto")
NOW = datetime.now(tz=TOR)
_TS = "%Y-%m-%d %H:%M:%S"


class _FrozenDatetime(datetime):
    """datetime whose now() is pinned to NOW.

    The fixtures stamp coverage windows relative to NOW, but cloud_deadman
    reads the live clock — so under a full-suite run the two drift apart by
    however long the module sat before its test executed, and an assertion
    about a 90-minute-old heartbeat saw "92 min old" (CI 2026-10-03). Pin
    the module's clock to the same instant the fixtures are built from and
    every age in this module is exact, whatever order pytest runs it in.
    """

    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz is not None else NOW.replace(tzinfo=None)


@pytest.fixture
def home(tmp_path, monkeypatch):
    d = tmp_path / "home"
    (d / "coverage").mkdir(parents=True)
    monkeypatch.setenv("MIWAY_DATA_DIR", str(d))
    monkeypatch.setattr(dm, "datetime", _FrozenDatetime)
    monkeypatch.setattr(dm, "_toast", lambda title, body: None)
    return d


def _window(home: Path, origin="cloud", poll_min_ago=2.0, name="window_test.json"):
    p = home / "coverage" / name
    stamp = (NOW - timedelta(minutes=poll_min_ago)).strftime(_TS)
    p.write_text(
        json.dumps(
            {
                "window_end": (NOW + timedelta(hours=2)).strftime(_TS),
                "last_poll_at": stamp,
                "collector_origin": origin,
            }
        ),
        encoding="utf-8",
    )
    return p


def test_heartbeat_age_cloud(home):
    _window(home, poll_min_ago=5)
    rec = dm._newest_coverage(home / "coverage")
    age = dm._heartbeat_age_min(rec, NOW)
    assert age is not None and 4 < age < 6


def test_heartbeat_age_non_cloud_is_none(home):
    _window(home, origin="local")
    age = dm._heartbeat_age_min(dm._newest_coverage(home / "coverage"), NOW)
    assert age is None


def test_heartbeat_age_missing_field_is_none(home):
    p = home / "coverage" / "window_test.json"
    p.write_text(json.dumps({"window_end": "x"}), encoding="utf-8")
    assert dm._heartbeat_age_min(dm._newest_coverage(home / "coverage"), NOW) is None


def test_fresh_heartbeat_quiet_and_logs_nothing(home, monkeypatch):
    # Vintage channel stubbed (see test_alert_sends_email): host data-home
    # staleness must not leak into a heartbeat-only assertion.
    monkeypatch.setattr(dm, "_vintage_alerts", lambda stale: [])
    _window(home, poll_min_ago=2)
    assert dm.main([]) == 0
    assert not (home / "logs" / "deadman.log").exists()


def test_dead_heartbeat_alerts_once(home, monkeypatch):
    _window(home, poll_min_ago=90)
    fired = []
    monkeypatch.setattr(dm, "_toast", lambda t, b: fired.append((t, b)))
    assert dm.main([]) == 1
    assert len(fired) == 1 and "DOWN" in fired[0][0]
    log = (home / "logs" / "deadman.log").read_text(encoding="utf-8")
    assert "ALERT" in log and "90" in log
    # Second run inside cooldown: re-alert code but NO new toast.
    fired.clear()
    assert dm.main([]) == 1
    assert fired == []


def test_realert_after_cooldown(home, monkeypatch):
    _window(home, poll_min_ago=90)
    fired = []
    monkeypatch.setattr(dm, "_toast", lambda t, b: fired.append(t))
    dm.main(["--repeat-minutes", "0"])  # cooldown instantly elapsed
    dm.main(["--repeat-minutes", "0"])
    assert len(fired) == 2


def test_recovery_clears_alert(home, monkeypatch):
    _window(home, poll_min_ago=90)
    monkeypatch.setattr(dm, "_toast", lambda t, b: None)
    assert dm.main([]) == 1
    # Heartbeat comes back.
    _window(home, poll_min_ago=1)
    assert dm.main([]) == 0
    log = (home / "logs" / "deadman.log").read_text(encoding="utf-8")
    assert "RECOVERED" in log
    state = json.loads((home / "deadman_state.json").read_text(encoding="utf-8"))
    assert state["alerting"] is False


def test_no_cloud_stamp_ever_stays_quiet(home, monkeypatch):
    # Stub the advisory vintage lane like the other heartbeat tests: it reads
    # app.config.DATA_DIR, which caches at first app import — under xdist
    # another module's import can pin the REAL data home, whose genuinely
    # stale derived files then log VINTAGE STALE lines here (machine-state
    # coupling, not the heartbeat contract under test).
    monkeypatch.setattr(dm, "_vintage_alerts", lambda stale: [])
    _window(home, origin="local", poll_min_ago=10_000)
    assert dm.main([]) == 0
    assert not (home / "logs" / "deadman.log").exists()


def test_quiet_flag_suppresses_toast(home, monkeypatch):
    _window(home, poll_min_ago=90)
    fired = []
    monkeypatch.setattr(dm, "_toast", lambda t, b: fired.append(t))
    assert dm.main(["--quiet"]) == 1
    assert fired == []
    assert "ALERT" in (home / "logs" / "deadman.log").read_text(encoding="utf-8")


def test_missing_data_home_is_config_error(tmp_path, monkeypatch):
    monkeypatch.setenv("MIWAY_DATA_DIR", str(tmp_path / "nope"))
    assert dm.main([]) == 2


# ---------------------------------------------------------------------------
# email channel
# ---------------------------------------------------------------------------


def _email_cfg(home: Path, **overrides):
    cfg = {
        "to": "collector@example.invalid",
        "smtp_user": "collector@example.invalid",
        "smtp_pass": "fake-app-password",
        **overrides,
    }
    (home / "deadman_email.json").write_text(json.dumps(cfg), encoding="utf-8")
    return cfg


def test_email_config_missing_file_is_none(home):
    assert dm._email_config(home) is None


def test_email_config_no_password_disables_channel(home):
    (home / "deadman_email.json").write_text(
        json.dumps({"to": "x@y.z"}), encoding="utf-8"
    )
    assert dm._email_config(home) is None


def test_email_config_defaults(home):
    _email_cfg(home)
    cfg = dm._email_config(home)
    assert cfg["smtp_host"] == "smtp.gmail.com"
    assert cfg["smtp_port"] == 587
    assert cfg["smtp_user"] == "collector@example.invalid"


def test_alert_sends_email(home, monkeypatch):
    _email_cfg(home)
    sent = []
    monkeypatch.setattr(dm, "_toast", lambda t, b: None)
    monkeypatch.setattr(
        dm, "_send_email", lambda cfg, subj, body, log: sent.append(subj) or True
    )
    # These tests exercise the collector-heartbeat channel only. Stub the
    # vintage channel: _vintage_alerts caches app.config.DATA_DIR at first
    # import, so under xdist another test's import can pin it to the real
    # data home — and a genuinely-stale live source would inject an extra
    # "data STALE" email here (observed 2026-09-15, -n 8). Isolate the
    # channel instead of hoping the workstation data is fresh.
    monkeypatch.setattr(dm, "_vintage_alerts", lambda stale: [])
    _window(home, poll_min_ago=90)
    assert dm.main([]) == 1
    assert len(sent) == 1 and "DOWN" in sent[0]


def test_recovery_sends_all_clear(home, monkeypatch):
    _email_cfg(home)
    sent = []
    monkeypatch.setattr(dm, "_toast", lambda t, b: None)
    monkeypatch.setattr(
        dm, "_send_email", lambda cfg, subj, body, log: sent.append(subj) or True
    )
    # Same isolation as test_alert_sends_email: vintage channel stubbed so a
    # stale live source on the host cannot leak into the heartbeat assertions.
    monkeypatch.setattr(dm, "_vintage_alerts", lambda stale: [])
    _window(home, poll_min_ago=90)
    dm.main([])
    _window(home, poll_min_ago=1)
    sent.clear()
    assert dm.main([]) == 0
    assert len(sent) == 1 and "RECOVERED" in sent[0]


def test_email_failure_never_crashes_run(home, monkeypatch):
    _email_cfg(home)
    monkeypatch.setattr(dm, "_toast", lambda t, b: None)

    def boom(cfg, subj, body, log):
        raise ConnectionError("no network")

    # _send_email catches internally; simulate that by returning False
    monkeypatch.setattr(dm, "_send_email", lambda cfg, subj, body, log: False)
    _window(home, poll_min_ago=90)
    assert dm.main([]) == 1  # alert still raised


def test_no_email_config_alerts_without_email(home, monkeypatch):
    sent = []
    monkeypatch.setattr(dm, "_toast", lambda t, b: fired_append(sent, t))
    real_send = dm._send_email

    def spy(cfg, subj, body, log):
        sent.append("EMAIL:" + subj)
        return real_send(cfg, subj, body, log)

    monkeypatch.setattr(dm, "_send_email", spy)
    _window(home, poll_min_ago=90)
    assert dm.main([]) == 1
    assert not any(s.startswith("EMAIL:") for s in sent)


def fired_append(lst, item):
    lst.append(item)
    return lst


# ---------------------------------------------------------------------------
# data-vintage staleness (2026-09-11: silent wrong-directory + sync stall)
# ---------------------------------------------------------------------------


def _fake_vintages(monkeypatch, rows: dict):
    """Patch app.data_vintage.vintages as imported by cloud_deadman."""
    import app.data_vintage as dv

    monkeypatch.setattr(dv, "vintages", lambda: rows)


def _fresh(name, source="post-window analysis"):
    return {"file": name, "source": source, "exists": True, "age_minutes": 5}


def test_vintage_alerts_ignore_fresh_and_exempt_sources(home, monkeypatch):
    _fake_vintages(
        monkeypatch,
        {
            "lateness": _fresh("obs_lateness.csv", "collector live CSV"),
            "boardings": _fresh("boardings_routes.csv"),
            "realized_waits": {
                "file": "realized_waits.csv",
                "source": "committed reference",
                "exists": True,
                "age_minutes": 999_999,
            },
            "ridership": {
                "file": "ridership.csv",
                "source": "published APC",
                "exists": True,
                "age_minutes": 999_999,
            },
        },
    )
    assert dm._vintage_alerts(stale_minutes=24 * 60) == []


def test_vintage_alerts_flag_stale_monitored_sources(home, monkeypatch):
    _fake_vintages(
        monkeypatch,
        {
            "lateness": {
                "file": "obs_lateness.csv",
                "source": "collector live CSV",
                "exists": True,
                "age_minutes": 4 * 60 + 46,
            },
            "boardings": {
                "file": "boardings_routes.csv",
                "source": "post-window analysis",
                "exists": True,
                "age_minutes": 6406,
            },
        },
    )
    alerts = dm._vintage_alerts(stale_minutes=24 * 60)
    assert len(alerts) == 1 and "boardings" in alerts[0] and "106h" in alerts[0]


def test_vintage_alerts_skip_missing_files(home, monkeypatch):
    _fake_vintages(
        monkeypatch,
        {
            "boardings": {
                "file": "boardings_routes.csv",
                "source": "post-window analysis",
                "exists": False,
                "age_minutes": None,
            }
        },
    )
    assert dm._vintage_alerts(stale_minutes=60) == []


def test_vintage_check_failure_never_raises(home, monkeypatch):
    import app.data_vintage as dv

    def boom():
        raise RuntimeError("no data home")

    monkeypatch.setattr(dv, "vintages", boom)
    assert dm._vintage_alerts(stale_minutes=60) == []


def test_stale_vintages_send_email_with_fingerprint(home, monkeypatch):
    _email_cfg(home)
    sent = []
    monkeypatch.setattr(dm, "_toast", lambda t, b: None)
    monkeypatch.setattr(
        dm, "_send_email", lambda cfg, subj, body, log: sent.append(subj) or True
    )
    _fake_vintages(
        monkeypatch,
        {
            "boardings": {
                "file": "boardings_routes.csv",
                "source": "post-window analysis",
                "exists": True,
                "age_minutes": 6406,
            }
        },
    )
    _window(home, poll_min_ago=2)  # heartbeat fresh; vintage alert standalone
    assert dm.main([]) == 0  # advisory: exit code untouched
    assert len(sent) == 1 and "STALE" in sent[0]
    state = json.loads((home / "deadman_state.json").read_text(encoding="utf-8"))
    assert state["vintage"]["fingerprints"]
    # Unchanged staleness inside cooldown: no repeat email.
    sent.clear()
    assert dm.main([]) == 0
    assert sent == []


def test_vintage_recovery_sends_all_clear(home, monkeypatch):
    _email_cfg(home)
    sent = []
    monkeypatch.setattr(dm, "_toast", lambda t, b: None)
    monkeypatch.setattr(
        dm, "_send_email", lambda cfg, subj, body, log: sent.append(subj) or True
    )
    _fake_vintages(
        monkeypatch,
        {
            "boardings": {
                "file": "boardings_routes.csv",
                "source": "post-window analysis",
                "exists": True,
                "age_minutes": 6406,
            }
        },
    )
    _window(home, poll_min_ago=2)
    dm.main([])
    _fake_vintages(monkeypatch, {"boardings": _fresh("boardings_routes.csv")})
    sent.clear()
    assert dm.main([]) == 0
    assert len(sent) == 1 and "RECOVERED" in sent[0]
    state = json.loads((home / "deadman_state.json").read_text(encoding="utf-8"))
    assert "vintage" not in state


def test_vintage_log_lines_written_even_without_email(home, monkeypatch):
    monkeypatch.setattr(dm, "_toast", lambda t, b: None)
    _fake_vintages(
        monkeypatch,
        {
            "boardings": {
                "file": "boardings_routes.csv",
                "source": "post-window analysis",
                "exists": True,
                "age_minutes": 3000,
            }
        },
    )
    _window(home, poll_min_ago=2)
    assert dm.main([]) == 0
    log = (home / "logs" / "deadman.log").read_text(encoding="utf-8")
    assert "VINTAGE STALE" in log and "boardings" in log
