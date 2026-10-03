"""Tests for ``scripts/promotion_drift_alert.py`` — the nightly drift email.

Covers the verifier-result parsing, the email/cooldown/recovery decision
(the dead-man's proven state-machine shape), the channel-off path, and the
verifier-crash path. The verifier subprocess itself is faked; the real one
is exercised by the live daily chain and the showcase CI gate.
"""

import json
import time

import pytest
from scripts import cloud_deadman as dm
from scripts import promotion_drift_alert as pa


_EMAIL_CFG = {
    "to": "me@example.com",
    "smtp_user": "me@example.com",
    "smtp_pass": "secret",
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
}

# Verifier table shape: "{name}  {STATUS:10}  {detail}"
_CLEAN = "alpha.md   OK          matches docs/alpha.md\n20 docs checked, 0 DRIFT"
_DRIFT_ONE = (
    "alpha.md   OK          matches docs/alpha.md\n"
    "beta.md    DRIFT       3 source number(s) absent from public copy: 12, 47\n"
    "20 docs checked, 1 DRIFT"
)


@pytest.fixture
def home(tmp_path, monkeypatch):
    d = tmp_path / "home"
    d.mkdir()
    monkeypatch.setenv("MIWAY_DATA_DIR", str(d))
    return d


@pytest.fixture
def sent(home, monkeypatch):
    out = []
    monkeypatch.setattr(
        dm,
        "_send_email",
        lambda cfg, subject, body, log: out.append((subject, body)) or True,
    )
    monkeypatch.setattr(dm, "_email_config", lambda data_home: dict(_EMAIL_CFG))
    return out


def _state(home: dict, docs: list[str], age_s: float = 0.0) -> None:
    (home / "promotion_drift_state.json").write_text(
        json.dumps({"docs": docs, "last_alert_epoch": time.time() - age_s}),
        encoding="utf-8",
    )


def test_clean_run_is_silent(home, sent, monkeypatch):
    monkeypatch.setattr(pa, "_run_verifier", lambda: (0, _CLEAN))
    assert pa.main([]) == 0
    assert sent == []
    assert not (home / "promotion_drift_state.json").exists()


def test_drift_emails_and_saves_state(home, sent, monkeypatch):
    monkeypatch.setattr(pa, "_run_verifier", lambda: (1, _DRIFT_ONE))
    assert pa.main([]) == 1
    assert len(sent) == 1
    subject, body = sent[0]
    assert "DRIFT (1 doc)" in subject
    assert "beta.md" in body
    state = json.loads((home / "promotion_drift_state.json").read_text())
    assert state["docs"] == ["beta.md (DRIFT)"]


def test_drift_parses_multiple_docs(home, sent, monkeypatch):
    table = (
        _DRIFT_ONE.replace("beta.md", "beta.md", 1)
        + "\ngamma.md  DRIFT       1 source..."
    )
    monkeypatch.setattr(pa, "_run_verifier", lambda: (1, table))
    assert pa.main([]) == 1
    assert "DRIFT (2 docs)" in sent[0][0]


def test_channel_off_still_exits_1(home, monkeypatch):
    monkeypatch.setattr(dm, "_email_config", lambda data_home: None)
    monkeypatch.setattr(pa, "_run_verifier", lambda: (1, _DRIFT_ONE))
    assert pa.main([]) == 1  # verdict surfaces even without email


def test_unchanged_drift_holds_cooldown(home, sent, monkeypatch):
    _state(home, ["beta.md (DRIFT)"], age_s=3600.0)  # 1h ago, default 24h cooldown
    monkeypatch.setattr(pa, "_run_verifier", lambda: (1, _DRIFT_ONE))
    assert pa.main([]) == 1
    assert sent == []  # same episode, inside cooldown


def test_unchanged_drift_reemails_after_cooldown(home, sent, monkeypatch):
    _state(home, ["beta.md (DRIFT)"], age_s=25 * 3600.0)
    monkeypatch.setattr(pa, "_run_verifier", lambda: (1, _DRIFT_ONE))
    assert pa.main([]) == 1
    assert len(sent) == 1


def test_changed_docset_reemails_immediately(home, sent, monkeypatch):
    _state(home, ["beta.md (DRIFT)"], age_s=60.0)
    monkeypatch.setattr(
        pa, "_run_verifier", lambda: (1, _DRIFT_ONE.replace("beta.md", "gamma.md"))
    )
    assert pa.main([]) == 1
    assert len(sent) == 1
    state = json.loads((home / "promotion_drift_state.json").read_text())
    assert state["docs"] == ["gamma.md (DRIFT)"]


def test_recovery_sends_one_allclear_and_clears_state(home, sent, monkeypatch):
    _state(home, ["beta.md (DRIFT)"], age_s=60.0)
    monkeypatch.setattr(pa, "_run_verifier", lambda: (0, _CLEAN))
    assert pa.main([]) == 0
    assert len(sent) == 1
    assert "RECOVERED" in sent[0][0]
    assert not (home / "promotion_drift_state.json").exists()
    # A second clean run stays silent.
    sent.clear()
    assert pa.main([]) == 0
    assert sent == []


def test_verifier_crash_emails_error_and_exits_2(home, sent, monkeypatch):
    monkeypatch.setattr(pa, "_run_verifier", lambda: (2, "OSError: disk full"))
    assert pa.main([]) == 2
    assert len(sent) == 1
    assert "ERROR" in sent[0][0]
    assert "disk full" in sent[0][1]


def test_problem_docs_parser_ignores_ok_lines():
    out = (
        "alpha.md   OK          fine\n"
        "beta.md    DRIFT       3 source(s): 12\n"
        "\n"
        "20 docs checked, 1 DRIFT"
    )
    assert pa._problem_docs(out) == ["beta.md (DRIFT)"]


def test_problem_docs_catches_identity_verdicts():
    out = (
        "alpha.md   OK          fine\n"
        "gamma.md   IDENTITY    given name: ...A. Student built...\n"
        "\n"
        "2 docs checked, 0 DRIFT, 1 IDENTITY"
    )
    assert pa._problem_docs(out) == ["gamma.md (IDENTITY)"]
