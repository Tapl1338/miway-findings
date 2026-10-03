"""Tests for /api/collector/instrument (2026-09-25).

The endpoint wraps demo_stats.py — the single owner of the README
instrument-line derivation — so the demo intro card and the README can
never disagree again. Contract under test:

  * available home  -> {"available": true, windows, polls_attempted,
                        polls_succeeded, success_pct, unique_departures};
  * missing home    -> {"available": false, reason} (explicit, never a
                        fabricated number and never a 500);
  * the cache       -> a filled cache is served without re-deriving
                        (the derivation scans 5.8M CSV rows; it must run
                        once per TTL window, not per request);
  * pre-warm        -> startup warms the cache so the first real request
                        never pays the ~19s cold derivation.

demo_stats is monkeypatched at its import site in the router module, the
same seam the gate tests use.
"""

from __future__ import annotations

import types
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.routers import instrument as instrument_router


@pytest.fixture()
def patch_demo_stats(monkeypatch):
    """Install controllable demo_stats stand-ins into the router module and
    reset the module-level cache before/after each test."""
    fake = types.ModuleType("demo_stats")
    fake.data_home = lambda: Path("C:/fake/home")
    fake.coverage_stats = lambda home: (259, 85169, 84467)
    fake.unique_departures = lambda home: 5_795_382
    monkeypatch.setattr(instrument_router, "demo_stats", fake)
    instrument_router._CACHE["data"] = None
    instrument_router._CACHE["ts"] = 0.0
    yield fake
    instrument_router._CACHE["data"] = None
    instrument_router._CACHE["ts"] = 0.0


@pytest.fixture()
def client(patch_demo_stats):
    """Function-scoped TestClient, lifespan DISABLED (portal fixture style).

    The app's real startup pre-warm (start_prewarm) derives from the REAL
    machine data home on a daemon thread and writes into the same module
    _CACHE the per-test fakes use — a genuine race that flaked these tests.
    The pre-warm thread itself is covered by test_prewarm_*; boot-with-
    lifespan is covered by test_app_boot.py. Here we only exercise routing
    + the endpoint contract, so no lifespan is needed."""
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_available_home_returns_floors(client, patch_demo_stats):
    instrument_router._CACHE["data"] = None
    instrument_router._CACHE["ts"] = 0.0
    r = client.get("/api/collector/instrument")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["windows"] == 259
    assert body["polls_attempted"] == 85169
    assert body["polls_succeeded"] == 84467
    assert body["success_pct"] == 99.18
    assert body["unique_departures"] == 5_795_382


def test_missing_home_is_explicit_unavailable_not_a_500(client, patch_demo_stats):
    """The data home is machine-local; the endpoint must say so explicitly
    rather than invent numbers or blowing up."""

    def boom():
        raise SystemExit("MIWAY_DATA_DIR and LOCALAPPDATA both unset")

    patch_demo_stats.data_home = boom
    instrument_router._CACHE["data"] = None
    instrument_router._CACHE["ts"] = 0.0

    r = client.get("/api/collector/instrument")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert "reason" in body
    assert "not readable" in body["reason"] or "data home" in body["reason"]


def test_partial_home_with_no_polls_is_handled(client, patch_demo_stats):
    """att=0 must not ZeroDivisionError; success_pct is None, still available."""
    patch_demo_stats.coverage_stats = lambda home: (0, 0, 0)
    patch_demo_stats.unique_departures = lambda home: 0
    instrument_router._CACHE["data"] = None
    instrument_router._CACHE["ts"] = 0.0

    r = client.get("/api/collector/instrument")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["success_pct"] is None
    assert body["unique_departures"] == 0


def test_cache_serves_without_rederiving(client, patch_demo_stats):
    """Second call must hit the TTL cache: the derivation function is not
    invoked again within the TTL window."""
    calls = {"n": 0}
    real_derive = instrument_router._derived

    def counting_derive():
        calls["n"] += 1
        return real_derive()

    # Fill the cache through the real path once.
    instrument_router._CACHE["data"] = {
        "windows": 259,
        "polls_attempted": 85169,
        "polls_succeeded": 84467,
        "success_pct": 99.18,
        "unique_departures": 5_795_382,
    }
    import time

    instrument_router._CACHE["ts"] = time.time()

    first = client.get("/api/collector/instrument")
    second = client.get("/api/collector/instrument")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert calls["n"] == 0  # served entirely from the warm cache


def test_prewarm_warms_the_cache(patch_demo_stats):
    """start_prewarm() must fill _CACHE (derivation ran, cache populated)."""
    assert instrument_router._CACHE["data"] is None
    instrument_router.start_prewarm()
    import time

    deadline = time.time() + 5
    while instrument_router._CACHE["data"] is None and time.time() < deadline:
        time.sleep(0.05)
    assert instrument_router._CACHE["data"] is not None
    body = instrument_router._CACHE["data"]
    assert body["polls_attempted"] == 85169


def test_prewarm_failure_leaves_cache_empty_and_does_not_raise(
    patch_demo_stats,
):
    """A failed pre-warm (no data home) must not crash startup and must
    leave the cache empty so the endpoint still answers available=false."""

    def boom():
        raise SystemExit("no data home")

    patch_demo_stats.data_home = boom
    instrument_router._CACHE["data"] = None
    instrument_router._CACHE["ts"] = 0.0

    instrument_router.start_prewarm()  # must not raise
    import time

    time.sleep(0.5)  # give the daemon thread its chance to fail
    assert instrument_router._CACHE["data"] is None
