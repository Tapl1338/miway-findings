import pytest
from app.file_cache import mtime_cached
from pathlib import Path
from unittest.mock import Mock
import threading
import time


def _join_refresh_threads() -> None:
    """Wait for any mtime-refresh background threads this test spawned."""
    threads = [t for t in threading.enumerate() if t.name.startswith("mtime-refresh-")]
    for thread in threads:
        thread.join(timeout=2.0)


def test_mtime_cached_basic_functionality(tmp_path: Path) -> None:
    # Arrange
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    fn = Mock(return_value="result")
    cached_fn = mtime_cached(test_file, min_interval=0.0)(fn)

    # Act - First call
    result1 = cached_fn()
    fn.assert_called_once()

    # Act - Second call (should use cache)
    result2 = cached_fn()
    fn.assert_called_once()  # Still only one call

    # Assert
    assert result1 == "result"
    assert result2 == "result"


def test_mtime_cached_file_change(tmp_path: Path) -> None:
    # Arrange. The module is stale-while-revalidate: after a key change the
    # caller still gets the previous snapshot (never waits on a rebuild);
    # the fresh value lands on a later call once the background refresh
    # finishes. min_interval=0 removes the debounce, so the first call after
    # the change starts the refresh immediately.
    test_file = tmp_path / "test.txt"
    test_file.write_text("content1")

    call_count = 0

    def fn() -> str:
        nonlocal call_count
        call_count += 1
        return f"result{call_count}"

    cached_fn = mtime_cached(test_file, min_interval=0.0)(fn)

    # First call - builds synchronously (no snapshot yet)
    result1 = cached_fn()
    assert result1 == "result1"

    # Change file (different byte length so the mtime+size key MUST change,
    # even if both writes land in the same filesystem timestamp tick)
    test_file.write_text("content2-longer")

    # Second call - serves stale, refreshes in background
    result2 = cached_fn()
    assert result2 == "result1"

    # Wait for the background thread, then call again
    _join_refresh_threads()
    result3 = cached_fn()
    assert result3 == "result2"
    assert call_count == 2


def test_mtime_cached_file_not_found(tmp_path: Path) -> None:
    # Arrange
    test_file = tmp_path / "nonexistent.txt"

    fn = Mock(return_value="result")
    cached_fn = mtime_cached(test_file, min_interval=0.0)(fn)

    # Act - First call
    result1 = cached_fn()
    fn.assert_called_once()

    # Act - Second call
    result2 = cached_fn()
    fn.assert_called_once()  # Still only one call

    # Assert
    assert result1 == "result"
    assert result2 == "result"


def test_mtime_cached_with_min_interval(tmp_path: Path) -> None:
    # Arrange
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    fn = Mock(return_value="result")
    cached_fn = mtime_cached(test_file, min_interval=0.1)(fn)

    # First call
    result1 = cached_fn()
    fn.assert_called_once()

    # Immediately call again (should use cached result due to min_interval)
    result2 = cached_fn()
    fn.assert_called_once()

    # Change file after min_interval
    time.sleep(0.11)
    test_file.write_text("new content")

    result3 = cached_fn()

    # Assert
    assert result1 == "result"
    assert result2 == "result"
    assert result3 == "result"


def test_mtime_cached_with_min_interval_and_thread(tmp_path: Path) -> None:
    # Arrange
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    fn = Mock(return_value="result")
    cached_fn = mtime_cached(test_file, min_interval=0.05)(fn)

    # First call
    result1 = cached_fn()
    fn.assert_called_once()

    # Change file
    test_file.write_text("new content")

    # Immediately call again (should trigger background refresh)
    result2 = cached_fn()

    # Wait a bit for background thread to finish
    time.sleep(0.1)

    # Call again to see if background refresh worked
    result3 = cached_fn()

    # Allow threads to finish
    threads = [t for t in threading.enumerate() if t.name.startswith("mtime-refresh-")]
    for thread in threads:
        thread.join(timeout=1.0)

    # Assert
    assert result1 == "result"
    assert result2 == "result"
    assert result3 == "result"


def test_mtime_cached_exception_handling(tmp_path: Path) -> None:
    # The module never caches a failed rebuild: _bg_rebuild swallows the
    # exception and keeps the previous snapshot. With NO previous snapshot,
    # the synchronous build path runs and the exception propagates to the
    # caller (there is nothing stale to serve).
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    fn = Mock(side_effect=Exception("test error"))
    cached_fn = mtime_cached(test_file, min_interval=0.0)(fn)

    with pytest.raises(Exception, match="test error"):
        cached_fn()


def test_mtime_cached_stale_while_revalidate(tmp_path: Path) -> None:
    # Arrange
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    call_count = 0

    def fn() -> str:
        nonlocal call_count
        call_count += 1
        return f"result{call_count}"

    cached_fn = mtime_cached(test_file, min_interval=0.1)(fn)

    # First call
    result1 = cached_fn()

    # Change file
    test_file.write_text("new content")

    # Immediately call again (should return cached result)
    result2 = cached_fn()

    # Assert
    assert result1 == "result1"
    assert result2 == "result1"
    assert call_count == 1


def test_mtime_cached_multiple_threads(tmp_path: Path) -> None:
    # Arrange. Concurrent callers after a key change share one background
    # rebuild (no stampede) and each gets a consistent snapshot value.
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    call_count = 0

    def fn() -> str:
        nonlocal call_count
        call_count += 1
        return f"result{call_count}"

    cached_fn = mtime_cached(test_file, min_interval=0.0)(fn)

    # First call - builds synchronously
    result1 = cached_fn()
    assert result1 == "result1"

    # Change file
    test_file.write_text("new content")
    # Start multiple threads calling cached_fn simultaneously
    threads = []
    results = []

    def worker():
        results.append(cached_fn())

    for _ in range(5):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    # Wait for the shared background rebuild
    _join_refresh_threads()

    # All results must be SOME valid snapshot value (old or new), never a
    # torn read or None - the exact guarantee the lock protects.
    assert set(results) <= {"result1", "result2"}
    assert "result2" in results  # the background refresh completed
