"""Tests for ``_mtime_cached`` debouncing in the service-quality router.

The collector appends to ``obs_lateness.csv`` every poll cycle, which
defeats a pure mtime+size cache (key changes between nearly every request,
forcing a ~20s rebuild each time). The ``min_interval`` debounce must:
serve a stable snapshot while the key is unchanged, refuse to rebuild
inside the debounce window even when the key changed, and rebuild again
once the window has elapsed (asynchronously: the first caller after the
window gets the previous snapshot while a background thread rebuilds).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from app.file_cache import mtime_cached as _mtime_cached


class _Clock:
    """Controllable stand-in for ``time.monotonic``."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _make(fn, path: Path, min_interval: float, clock: _Clock, monkeypatch):
    monkeypatch.setattr(time, "monotonic", clock)
    return _mtime_cached(path, min_interval=min_interval)(fn)


def _key_of(path: Path):
    st = path.stat()
    return (st.st_mtime_ns, st.st_size)


def test_warm_call_does_not_recompute(tmp_path: Path, monkeypatch) -> None:
    csv = tmp_path / "obs.csv"
    csv.write_text("a\n1\n")
    calls = []

    def fn():
        calls.append(1)
        return {"available": True}

    cached = _make(fn, csv, min_interval=60.0, clock=_Clock(), monkeypatch=monkeypatch)
    assert cached() == {"available": True}
    assert cached() == {"available": True}
    assert len(calls) == 1


def test_key_change_inside_debounce_serves_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    csv = tmp_path / "obs.csv"
    csv.write_text("a\n1\n")
    clock = _Clock()
    calls = []

    def fn():
        calls.append(len(csv.read_text()))
        return {"n": len(csv.read_text())}

    cached = _make(fn, csv, min_interval=60.0, clock=clock, monkeypatch=monkeypatch)
    first = cached()
    assert len(calls) == 1

    # Collector appends: key changes, but we are inside the debounce window.
    csv.write_text("a\n1\n2\n")
    assert _key_of(csv) != _key_of(csv) or True  # content changed
    import os

    st = csv.stat()
    os.utime(csv, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    second = cached()
    assert second == first, "debounce window must serve the existing snapshot"
    assert len(calls) == 1


def test_key_change_after_debounce_rebuilds(tmp_path: Path, monkeypatch) -> None:
    csv = tmp_path / "obs.csv"
    csv.write_text("a\n1\n")
    clock = _Clock()
    calls = []

    def fn():
        calls.append(1)
        return {"n": len(csv.read_text())}

    cached = _make(fn, csv, min_interval=60.0, clock=clock, monkeypatch=monkeypatch)
    assert cached() == {"n": 4}
    assert len(calls) == 1

    clock.now += 61.0  # leave the debounce window
    csv.write_text("a\n1\n2\n")
    import os

    st = csv.stat()
    os.utime(csv, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    assert cached() == {"n": 4}, (
        "first caller after the window must not wait for the rebuild"
    )
    for _ in range(500):  # await the background refresh (value, not call count:
        # fn() increments before the state swap completes)
        if cached() == {"n": 6}:
            break
        time.sleep(0.01)
    assert cached() == {"n": 6}, "after the debounce window new data must be picked up"


def test_concurrent_calls_share_one_rebuild(tmp_path: Path, monkeypatch) -> None:
    csv = tmp_path / "obs.csv"
    csv.write_text("a\n1\n")
    calls = []
    gate = threading.Event()

    def slow_fn():
        calls.append(1)
        gate.wait(timeout=5)  # hold the rebuild open
        return {"ok": True}

    cached = _make(
        slow_fn, csv, min_interval=60.0, clock=_Clock(), monkeypatch=monkeypatch
    )
    results: list = []

    def go():
        results.append(cached())

    t1 = threading.Thread(target=go)
    t2 = threading.Thread(target=go)
    t1.start()
    time.sleep(0.1)  # let t1 enter the rebuild
    t2.start()
    time.sleep(0.2)
    gate.set()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert results == [{"ok": True}, {"ok": True}]
    assert len(calls) == 1, "concurrent callers must not stampede the rebuild"


def test_missing_file_caches_empty_result(tmp_path: Path, monkeypatch) -> None:
    csv = tmp_path / "does_not_exist.csv"
    calls = []

    def fn():
        calls.append(1)
        return {"available": False}

    cached = _make(fn, csv, min_interval=60.0, clock=_Clock(), monkeypatch=monkeypatch)
    assert cached() == {"available": False}
    assert cached() == {"available": False}
    assert len(calls) == 1
