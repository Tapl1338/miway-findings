"""Fault-injection tests for the centralized sanitized-500 handler.

Locks the contract in ``app/errors.py``: an unhandled endpoint exception
becomes a 500 whose body never echoes exception text, carries an
``X-Error-Id`` correlation header, and logs the same id server-side —
while genuine ``HTTPException`` responses (404/422) pass through untouched.

``app.main`` is imported once at module scope; the app object is shared but
each test patches a router dependency and restores it, so no test leaks
state into the rest of the suite.
"""

from __future__ import annotations

import logging

from app.main import app
from app.routers import circuity, diagnostics, equity, travel
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)

_SECRET = "SECRET-INTERNAL /Users/[redacted]/one-drive/data.db"


def _boom(*_args, **_kwargs):
    raise RuntimeError(f"escaped internals: {_SECRET}")


def test_unhandled_exception_becomes_sanitized_500(monkeypatch, caplog):
    """Force a router failure; assert nothing internal reaches the wire.

    ``/api/stops`` is the injected surface because it calls ``load_feed``
    directly per request — no disk/in-memory memo can swallow the fault.
    """
    monkeypatch.setattr(travel, "load_feed", _boom)
    with caplog.at_level(logging.ERROR, logger="miway.api.errors"):
        resp = client.get("/api/travel/stops", params={"q": "dixie"})

    assert resp.status_code == 500
    body = resp.json()
    assert resp.text.find(_SECRET) == -1, "exception text leaked into the body"
    assert "RuntimeError" not in resp.text
    # The sanitized contract, exactly.
    assert body["detail"] == "Internal server error (see server logs)"
    error_id = resp.headers.get("X-Error-Id")
    assert error_id, "missing X-Error-Id correlation header"
    # The real traceback (with the secret) went to the server log, tagged
    # with the same correlation id the client received. The message line
    # carries the id; the attached exc_info carries the traceback text.
    import traceback

    log_text = "\n".join(
        rec.getMessage()
        + "\n"
        + ("".join(traceback.format_exception(*rec.exc_info)) if rec.exc_info else "")
        for rec in caplog.records
    )
    assert error_id in log_text
    assert _SECRET in log_text


def test_http_exception_passthrough_untouched():
    """422 from endpoint validation must not be swallowed or reshaped."""
    resp = client.get("/api/routes/circuity", params={"period": "bogus_period"})
    assert resp.status_code == 422
    assert "Unknown period: bogus_period" in resp.json()["detail"]
    assert "X-Error-Id" not in resp.headers


def test_pure_endpoint_now_has_no_own_wrapper():
    """Endpoints migrated to the middleware carry no ``except Exception``.

    Reads the migrated routers' source: a re-added wrapper means someone
    reintroduced per-endpoint error policy — extend ``_PURE_ENDPOINTS``
    deliberately instead of letting wrappers accrete silently.
    """
    import inspect

    pure = [
        (circuity, "routes_circuity"),
        (diagnostics, "transfer_blindspots"),
        (travel, "search_stops"),
    ]
    for module, fn_name in pure:
        src = inspect.getsource(getattr(module, fn_name))
        assert "except Exception" not in src, f"{fn_name} re-grew a wrapper"


def test_degraded_data_file_still_serves_graceful_fallback(monkeypatch):
    """Missing-measurement fallbacks are intentional behavior — the
    middleware must not change them into 500s. Force the unavailable path
    in ``/api/equity/ward-demographics`` (no memo indirection) and require
    the graceful payload, not an error."""
    monkeypatch.setattr(
        equity,
        "_WARD_DEMOGRAPHICS_CSV",
        equity.config.DATA_DIR / "no_such_file__phase2_probe.csv",
    )
    resp = client.get("/api/equity/ward-demographics")
    assert resp.status_code == 200
    assert resp.json() == {"available": False}
