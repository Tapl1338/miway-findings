"""T33 DONE-WHEN: two parallel SolverLock acquisitions demonstrate
one success + one clean SolverBusyError refusal."""

from pathlib import Path

import pytest
from scripts.solver_lock import SolverBusyError, SolverLock


@pytest.fixture
def lock_path(tmp_path):
    """Override the lock file path for test isolation."""
    return tmp_path / ".solver.lock"


def test_parallel_one_success_one_refusal(lock_path, monkeypatch):
    monkeypatch.setattr(
        __import__("scripts.solver_lock", fromlist=["LOCK_FILE"]),
        "LOCK_FILE",
        lock_path,
    )
    # First acquisition succeeds
    lock1 = SolverLock("test_first")
    lock1.__enter__()

    # Second acquisition is refused
    lock2 = SolverLock("test_second")
    with pytest.raises(SolverBusyError, match="Solver busy"):
        lock2.__enter__()

    # Release first; second now succeeds
    lock1.__exit__(None, None, None)
    lock2.__enter__()
    lock2.__exit__(None, None, None)


def test_experimental_knob_refuses_unconditionally(lock_path, monkeypatch):
    """Incident guard (T48, 2026-08-26; alpha-6 finding B): DET_TIME is
    refused OUTRIGHT. There is deliberately no SCRATCH_OUT escape hatch --
    one with zero consumers would pass a contaminated run through to the
    canonical JSONs, which is the exact T48 mechanism.
    """
    from scripts import solver_lock as sl

    monkeypatch.setenv("MIWAY_SOLVER_DET_TIME", "60")
    monkeypatch.setattr(sl, "LOCK_FILE", lock_path)
    # Refused with the knob alone...
    with pytest.raises(SystemExit, match="MIWAY_SOLVER_DET_TIME"):
        sl.SolverLock("exp_guard").__enter__()
    # ...and refused even with a scratch-out env var set (no escape hatch).
    monkeypatch.setenv("MIWAY_SOLVER_SCRATCH_OUT", "/tmp/scratch")
    with pytest.raises(SystemExit, match="MIWAY_SOLVER_DET_TIME"):
        sl.SolverLock("exp_guard").__enter__()
    assert not lock_path.exists()

    # No knob: acquisition proceeds normally.
    monkeypatch.delenv("MIWAY_SOLVER_DET_TIME", raising=False)
    lock = sl.SolverLock("exp_guard")
    lock.__enter__()
    assert lock_path.exists()
    lock.__exit__(None, None, None)


def test_systemexit_refusal_does_not_deadlock_later_acquire(lock_path, monkeypatch):
    """Regression (2026-09-02): the DET_TIME incident guard raises SystemExit,
    which is a ``BaseException``. ``__enter__`` released the local guard via
    ``except Exception`` -- which does NOT catch ``SystemExit`` -- so the guard
    was leaked on every refused acquisition. Any later ``SolverLock`` in the
    same process then blocked/hung forever (the local lock was held and
    ``acquire(blocking=False)`` returned False -> perpetual SolverBusyError).

    This test refuses with the guard, then acquires again and asserts it
    SUCCEEDS -- proving the guard was released. It would deadlock or throw
    SolverBusyError under the old code.
    """
    from scripts import solver_lock as sl

    monkeypatch.setattr(sl, "LOCK_FILE", lock_path)

    # The critical assertion: refuse with the guard, then acquire again in the
    # SAME process. Run in a timed subprocess so a leaked guard manifests as
    # a hang we can fail rather than hang the whole suite.
    import subprocess
    import sys

    code = (
        "import sys\n"
        "import os\n"
        "import pathlib\n"
        "from scripts import solver_lock as sl\n"
        f"sl.LOCK_FILE = pathlib.Path({str(lock_path)!r})\n"
        "os.environ['MIWAY_SOLVER_DET_TIME'] = '60'\n"
        "try:\n"
        "    sl.SolverLock('refusal').__enter__()\n"
        "except SystemExit:\n"
        "    pass\n"
        "del os.environ['MIWAY_SOLVER_DET_TIME']\n"
        "lk = sl.SolverLock('later')\n"
        "lk.__enter__()\n"
        "lk.__exit__(None, None, None)\n"
        "print('acquired-ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert "acquired-ok" in (result.stdout or ""), (
        "post-SystemExit acquire failed (leaked guard deadlock?)\n"
        + result.stdout
        + result.stderr
    )


def test_stale_unlink_race_no_crash(lock_path, monkeypatch):
    """Alpha-6 finding C: many racers on the SAME stale lock must not crash
    on FileNotFoundError -- the unlink is missing_ok=True, and exactly one
    racer wins the O_EXCL create; the rest get a clean SolverBusyError.
    """
    import threading

    from scripts import solver_lock as sl

    monkeypatch.setattr(sl, "LOCK_FILE", lock_path)
    # Dead PID: lock is stale, every racer will try to clean it. Spawn and
    # kill a real process rather than hardcoding a PID -- on Windows PID 999999
    # can genuinely exist (PID reuse), which made every racer see the lock as
    # live and the test fail spuriously with 0 winners.
    import subprocess
    import sys
    import time

    victim = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    time.sleep(0.3)  # let it start so the PID is real before we kill it
    victim.kill()
    victim.wait()
    dead_pid = victim.pid
    lock_path.write_text(f"{dead_pid}|stale|2026-08-26T00:00Z", encoding="utf-8")
    # Sanity: the PID must read as dead, or the test would be meaningless.
    assert not sl._pid_alive(dead_pid)

    results: list = []
    errors: list = []

    def racer():
        try:
            lock = sl.SolverLock("race")
            lock.__enter__()
            results.append("won")
            lock.__exit__(None, None, None)
        except sl.SolverBusyError:
            results.append("busy")
        except Exception as exc:  # the bug class is any crash
            errors.append(exc)

    threads = [threading.Thread(target=racer) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"race crashed: {errors}"
    # Every racer must get a CLEAN outcome (won or refused) - never a crash.
    # Winners may exceed 1 because a winner releases before a later racer
    # arrives; the regression under test is the FileNotFoundError crash.
    assert results.count("won") >= 1, results
    assert len(results) == 16, results


def test_lock_file_content_survives_no_release(lock_path, monkeypatch):
    monkeypatch.setattr(
        __import__("scripts.solver_lock", fromlist=["LOCK_FILE"]),
        "LOCK_FILE",
        lock_path,
    )
    lock = SolverLock("crash_test")
    lock.__enter__()
    # No __exit__ = simulated crash; lock file persists on disk
    assert lock_path.exists()
    assert "crash_test" in lock_path.read_text(encoding="utf-8")


def test_pid_alive_flips_false_after_process_exit():
    """Regression (2026-09-02): on Windows ``_pid_alive`` used
    ``os.kill(pid, 0)``, which reported a genuinely DEAD process as alive
    (a killed child still answered kill(0)). That made every stale solver
    lock look held-by-a-live-process, so the lock was never cleaned and
    acquisitions all refused -- the all-busy / 0-winner race failure. The
    probe must track the process's real lifecycle.

    Portable across POSIX and Windows: spawn, see it alive, kill it, wait,
    see it dead.
    """
    import subprocess
    import sys
    import time

    from scripts.solver_lock import _pid_alive

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    time.sleep(0.4)  # let it spawn so the PID exists
    assert _pid_alive(child.pid) is True  # live process reads alive

    child.kill()
    child.wait()
    time.sleep(0.3)  # give the OS a beat to reap the handle

    # Dead process must read dead. The buggy os.kill-on-Windows probe
    # returned True here, defeating stale-lock cleanup entirely.
    assert _pid_alive(child.pid) is False
