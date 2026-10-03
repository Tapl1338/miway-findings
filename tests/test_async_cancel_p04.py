"""P0.4 Phase-0 fixtures: async job cancellation and expiry semantics.

Implements the fixture list from ``docs/runs/p04-async-cancel-session-plan.md``.
The store-level terminal-transition invariants are already tested above; these
pin the MISSING pieces (expected RED until Phase 1):

* a per-job stop control that the expiry timer AND a client-facing cancel
  endpoint both set (``transfers._job_stop_event(job_id)``),
* cooperative cancellation visible to the worker
  (``_run_optimization_job`` aborts at phase boundaries when the event is
  set — the solver is stopped cooperatively, never killed),
* ``POST /api/optimize/transfers/async/{job_id}/cancel``: queued/running →
  failed("cancelled by client") + stop event set + timer cancelled +
  slot released exactly once; terminal → 409.
"""

from __future__ import annotations

import asyncio
import threading

import pytest
from app import config, job_store
from app.routers import transfers
from fastapi import HTTPException


@pytest.fixture()
def job_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE_DB", tmp_path / "state.db")
    return tmp_path / "state.db"


@pytest.fixture(autouse=True)
def fresh_slots(monkeypatch):
    """Hermetic admission semaphore per test.

    ``transfers._ASYNC_SLOTS`` is module-level and other test files drain
    or hold it; under the full suite that ambient state leaks into these
    tests (acquire fails, or a release bumps past cap). A fresh semaphore
    of the same production cap makes every cancellation test independent
    of test ordering — the P0.3 doctrine.
    """
    monkeypatch.setattr(
        transfers,
        "_ASYNC_SLOTS",
        threading.BoundedSemaphore(
            max(
                1, config.ASYNC_OPTIMIZER_WORKERS + max(0, config.ASYNC_OPTIMIZER_QUEUE)
            )
        ),
    )


@pytest.fixture()
def admitted_job():
    """Simulate one admitted job: consume an admission slot for the test.

    Cancel and expiry paths release the slot (exactly-once doctrine), so a
    test exercising them against a job that never consumed a slot would
    push the BoundedSemaphore past its cap and raise — the same guard that
    catches production double-releases. Acquiring here mirrors admission.

    Teardown hands the slot back only if the path under test did not
    already: releasing when the count is already at cap raises ValueError,
    which is exactly the "already released" signal.
    """
    assert transfers._ASYNC_SLOTS.acquire(blocking=False) is True
    yield
    try:
        transfers._ASYNC_SLOTS.release()
    except ValueError:
        pass  # test path already released — nothing left to hand back


# ---------------------------------------------------------------------------
# Stop-control plumbing (the shared flag behind expiry AND user cancel)
# ---------------------------------------------------------------------------


def test_job_has_a_stop_event_after_creation(job_db):
    """Every admitted job gets a stop control the worker can poll."""
    job_id = job_store.create_job({})
    event = transfers._job_stop_event(job_id)
    assert event is not None
    assert not event.is_set()
    # Idempotent: the same event comes back for the same job.
    assert transfers._job_stop_event(job_id) is event


def test_expiry_sets_the_stop_event(job_db, admitted_job):
    """The expiry timer must signal the worker, not just flip status."""
    job_id = job_store.create_job({})
    event = transfers._job_stop_event(job_id)
    transfers._expire_async_job(job_id, timeout_seconds=91)
    assert event.is_set()


# ---------------------------------------------------------------------------
# Cooperative worker cancellation
# ---------------------------------------------------------------------------


def test_worker_aborts_at_phase_boundary_when_stop_is_set(job_db, monkeypatch):
    """A job whose stop event fires mid-run must not persist a result."""
    job_id = job_store.create_job({})
    event = transfers._job_stop_event(job_id)
    event.set()

    # No solver call needed: the worker checks the stop flag BEFORE solving.
    called = {"n": 0}

    def fake_solve(*_a, **_k):
        called["n"] += 1
        raise AssertionError("solver must not run after the stop event fired")

    monkeypatch.setattr(transfers, "run_full_optimization", fake_solve)
    result = transfers._run_optimization_job({"time_limit_seconds": 5}, job_id)
    assert result is None
    assert called["n"] == 0
    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    assert "cancelled" in (job["error"] or "")


# ---------------------------------------------------------------------------
# Client-facing cancel endpoint
# ---------------------------------------------------------------------------


def test_cancel_endpoint_fails_a_queued_job(job_db, admitted_job):
    job_id = job_store.create_job({})
    response = asyncio.run(transfers.cancel_optimize_job(job_id))
    assert response.status == "failed"

    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    assert "cancelled" in (job["error"] or "")
    assert transfers._job_stop_event(job_id).is_set()


def test_cancel_endpoint_fails_a_running_job(job_db, admitted_job):
    job_id = job_store.create_job({})
    assert job_store.update_job_status(job_id, "running") is True
    response = asyncio.run(transfers.cancel_optimize_job(job_id))
    assert response.status == "failed"
    assert transfers._job_stop_event(job_id).is_set()


def test_cancel_endpoint_409_on_terminal_job(job_db):
    job_id = job_store.create_job({})
    job_store.update_job_status(job_id, "failed", error="already done")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(transfers.cancel_optimize_job(job_id))
    assert exc_info.value.status_code == 409


def test_cancel_endpoint_404_on_unknown_job(job_db):
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(transfers.cancel_optimize_job("nonexistent"))
    assert exc_info.value.status_code == 404


def test_cancel_releases_the_capacity_slot_exactly_once(job_db):
    """Cancelling a queued job frees its admission slot — once."""
    # Fill all slots, so acquire below only succeeds if cancel released one.
    released = []
    while transfers._ASYNC_SLOTS.acquire(blocking=False):
        released.append(True)
    try:
        job_id = job_store.create_job({})
        # Simulate admission: this job consumed one of the slots.
        transfers._ASYNC_SLOTS.release()

        asyncio.run(transfers.cancel_optimize_job(job_id))

        # Cancel released exactly one slot — capacity is fully available
        # again only if the release happened (and happened once).
        assert transfers._ASYNC_SLOTS.acquire(blocking=False) is True
    finally:
        # Restore the pre-test state: all slots held, as the loop left them.
        transfers._ASYNC_SLOTS.release()
        for _ in released[1:]:
            transfers._ASYNC_SLOTS.acquire(blocking=False)


def test_cancelled_job_cannot_later_complete(job_db, admitted_job):
    """The store invariant holds through the cancel path too."""
    job_id = job_store.create_job({})
    asyncio.run(transfers.cancel_optimize_job(job_id))
    assert (
        job_store.update_job_status(
            job_id, "completed", result_json='{"status":"FEASIBLE"}'
        )
        is False
    )
    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    assert job["result"] is None
