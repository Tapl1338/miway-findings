"""Tests for ``app.warmup.warm_router_caches`` and the warm-up concurrency cap.

Checks the wiring: starting warm-up primes the cached read endpoints for every
service day -- reliability, blind-spot diagnostics and executive brief for
each of weekday/saturday/sunday, plus the export once (it has no service-day
variant) -- and that the shared semaphore caps how many warm-up computations
run at once. The handlers are swapped for cheap recording stubs so the wiring
tests never trigger a real feed load or multi-second compute.
"""

from __future__ import annotations

import logging
import threading
import time

from app import warmup


class _TARGETS:
    """Mirror of the five router modules warm_router_caches reads."""

    handlers = {
        "reliability": "measured_reliability",
        "diagnostics": "transfer_blindspots",
        "brief": "executive_brief",
        "transfers": "export_updated_stop_times",
        "service_quality": "service_quality",
    }


def _make_fake(recorder: list[tuple[str, str | None]], name: str):
    class _FakeRouter:
        pass

    # A ``def`` stored as an instance attribute gets bound (``self`` would eat
    # the first arg), so use a lambda whose ``_h`` is keyword-only (after
    # ``*_a``) to dodge the bound-method self. It records ``(handler, day)`` so
    # the test can assert both the target and the service day it was primed for.
    handler_name = _TARGETS.handlers[name]
    setattr(
        _FakeRouter,
        handler_name,
        lambda *_a, _h=handler_name, **_k: recorder.append((_h, _k.get("service_day"))),
    )
    return _FakeRouter()


def test_warm_router_caches_primes_all_views_all_days(monkeypatch):
    recorder: list[tuple[str, str | None]] = []
    fakes = {key: _make_fake(recorder, key) for key in _TARGETS.handlers}
    monkeypatch.setattr(warmup, "_reliability", fakes["reliability"])
    monkeypatch.setattr(warmup, "_diagnostics", fakes["diagnostics"])
    monkeypatch.setattr(warmup, "_brief", fakes["brief"])
    monkeypatch.setattr(warmup, "_transfers", fakes["transfers"])
    monkeypatch.setattr(warmup, "_service_quality", fakes["service_quality"])
    # Reset the semaphore so real warmup threads from app startup don't
    # starve this test's threads of the concurrency slot.
    monkeypatch.setattr(warmup, "_WARMUP_SEMAPHORE", threading.Semaphore(10))

    warmup.warm_router_caches()

    handler_names = {
        "measured_reliability",
        "transfer_blindspots",
        "executive_brief",
        "export_updated_stop_times",
        "service_quality",
    }
    day_handlers = {"measured_reliability", "transfer_blindspots", "executive_brief"}

    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        if len(recorder) == 9 + 2 and {h for h, _ in recorder} == handler_names:
            break
        time.sleep(0.02)

    # The three service-day views are primed for exactly all three days.
    assert {h for h, _ in recorder if h not in day_handlers} == {
        "export_updated_stop_times",
        "service_quality",
    }
    assert {d for h, d in recorder if h in day_handlers} == {
        "weekday",
        "saturday",
        "sunday",
    }
    # Each day-view 3x, export and service-quality 1x each (no day variant).
    for h in day_handlers:
        assert sum(1 for nh, _ in recorder if nh == h) == 3
    assert sum(1 for h, _ in recorder if h == "export_updated_stop_times") == 1
    assert sum(1 for h, _ in recorder if h == "service_quality") == 1


def test_warm_never_exceeds_concurrency_cap(monkeypatch):
    # A cap of 1 must serialize warm-up computes: however many targets spawn,
    # at most one runs its fn at the same time.
    sem = threading.Semaphore(1)
    monkeypatch.setattr(warmup, "_WARMUP_SEMAPHORE", sem)

    lock = threading.Lock()
    active = 0
    peaked = 0

    def fn():
        nonlocal active, peaked
        with lock:
            active += 1
            peaked = max(peaked, active)
        time.sleep(0.1)  # give threads a chance to overlap if the cap is broken
        with lock:
            active -= 1

    threads = [
        threading.Thread(target=warmup._warm, args=(f"target-{i}", fn))
        for i in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peaked == 1  # never > 1 concurrent despite 4 spawned


def test_warmup_respects_disable_flag(monkeypatch, caplog):
    called: list[bool] = []
    monkeypatch.setattr(warmup.config, "WARMUP_CACHE", False)
    monkeypatch.setattr(warmup, "warm_router_caches", lambda: called.append(True))

    with caplog.at_level(logging.INFO, logger="miway.warmup"):
        warmup.start_cache_warmup()

    assert called == []  # early-return before the router warmers even spawn
    assert "disabled" in caplog.text.lower()
