"""Regression tests for the bounded asynchronous optimizer lifecycle."""

import asyncio
from unittest.mock import MagicMock

import pytest
from app import config, job_store
from app.models import OptimizeRequest
from app.routers import transfers
from fastapi import HTTPException


def test_job_store_rejects_late_terminal_transition(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE_DB", tmp_path / "state.db")
    job_id = job_store.create_job({"max_connections": 6000})

    assert job_store.update_job_status(job_id, "running") is True
    assert job_store.update_job_status(job_id, "failed", error="timed out") is True
    assert (
        job_store.update_job_status(
            job_id, "completed", result_json='{"status":"FEASIBLE"}'
        )
        is False
    )

    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    assert job["error"] == "timed out"
    assert job["result"] is None


def test_job_store_recovers_queued_and_running_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE_DB", tmp_path / "state.db")
    queued = job_store.create_job({})
    running = job_store.create_job({})
    assert job_store.update_job_status(running, "running") is True

    assert job_store.recover_incomplete_jobs() == 2
    for job_id in (queued, running):
        job = job_store.get_job(job_id)
        assert job["status"] == "failed"
        assert job["completed_at"] is not None
        assert job["error"] == "Job interrupted by a server restart"


def test_timed_out_job_cannot_be_completed_by_late_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE_DB", tmp_path / "state.db")
    job_id = job_store.create_job({})
    assert job_store.update_job_status(job_id, "running") is True

    # P0.4: expiry now also returns the admission slot (exactly-once), so
    # the job must be simulated as admitted — releasing a slot that was
    # never acquired is precisely the double-release the guard catches.
    assert transfers._ASYNC_SLOTS.acquire(blocking=False) is True
    transfers._expire_async_job(job_id, timeout_seconds=91)
    assert (
        job_store.update_job_status(
            job_id, "completed", result_json='{"status":"FEASIBLE"}'
        )
        is False
    )
    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    assert "91 seconds" in job["error"]


def test_async_worker_marks_post_solver_failure_and_releases_slot(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(config, "STATE_DB", tmp_path / "state.db")
    job_id = job_store.create_job({})

    def fail(*_args, **_kwargs):
        raise RuntimeError("response construction failed")

    monkeypatch.setattr(transfers, "_run_optimization_job", fail)
    assert transfers._ASYNC_SLOTS.acquire(blocking=False) is True
    transfers._run_async_job({}, job_id)

    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    assert job["error"] == "response construction failed"
    assert transfers._ASYNC_SLOTS.acquire(blocking=False) is True
    transfers._ASYNC_SLOTS.release()


def test_async_endpoint_returns_429_when_capacity_is_full(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE_DB", tmp_path / "state.db")
    acquired = []
    while transfers._ASYNC_SLOTS.acquire(blocking=False):
        acquired.append(True)

    try:
        with pytest.raises(HTTPException) as exc_info:
            mock_request = MagicMock()
            mock_request.client.host = "127.0.0.1"
            asyncio.run(
                transfers.start_optimize_transfers(OptimizeRequest(), mock_request)
            )
        assert exc_info.value.status_code == 429
    finally:
        for _ in acquired:
            transfers._ASYNC_SLOTS.release()
