"""Tests for the T150 read-only public gate (app.public_gate).

The gate is only ACTIVE when MIWAY_DISABLE_STATE_CHANGING is set at app
import time — so the tests spawn subprocess apps (like other env-coupled
tests in this suite) rather than rebinding the shared app module.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _make_app(monkeypatch, disabled: str):
    """Import a fresh app module with the gate env set to `disabled`."""
    import app.main as main_mod
    import app.public_gate as gate

    monkeypatch.setenv("MIWAY_DISABLE_STATE_CHANGING", disabled)
    importlib.reload(gate)
    importlib.reload(main_mod)
    return main_mod.app


def _client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


def test_disabled_flag_parsing(monkeypatch):
    import app.public_gate as gate

    for v, expected in [
        ("1", True),
        ("true", True),
        ("YES", True),
        ("0", False),
        ("", False),
    ]:
        monkeypatch.setenv("MIWAY_DISABLE_STATE_CHANGING", v)
        assert gate.state_changing_disabled() is expected, v


def test_gate_blocks_regen_when_enabled(monkeypatch):
    app = _make_app(monkeypatch, "1")
    with _client(app) as c:
        r = c.post("/api/regen/route-reference")
        assert r.status_code == 403
        assert "read-only" in r.json()["detail"].lower()


def test_gate_blocks_claim_refresh_but_not_reads(monkeypatch):
    app = _make_app(monkeypatch, "1")
    with _client(app) as c:
        r = c.post("/api/claims/verdicts/refresh")
        assert r.status_code == 403
        # reads on the same router pass through
        assert c.get("/api/claims/verdicts").status_code in (200, 500)


def test_gate_inactive_by_default(monkeypatch):
    app = _make_app(monkeypatch, "0")
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as c:
        # without the gate the endpoint runs (and fails on missing data in the
        # test env) — the point is it is NOT a 403
        r = c.post("/api/regen/route-reference")
        assert r.status_code != 403
