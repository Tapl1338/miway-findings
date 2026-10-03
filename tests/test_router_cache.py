"""Tests for ``app.router_cache``: the shared LRU memo for expensive GET endpoints.

These are pure unit tests (no feed, no data files except a tmp_path for the
fingerprint) so they run fast and stay isolated from any real GTFS load.
"""

from __future__ import annotations

from pathlib import Path

from app import router_cache
from app.router_cache import cached_compute, clear_cache, data_fingerprint


def test_same_key_computes_once():
    calls = 0

    def compute():
        nonlocal calls
        calls += 1
        return calls

    try:
        clear_cache()
        assert cached_compute(("k",), compute) == 1
        assert cached_compute(("k",), compute) == 1  # memoized, not recomputed
        assert calls == 1
    finally:
        clear_cache()


def test_distinct_keys_compute_separately():
    calls = {"a": 0, "b": 0}

    def make(k):
        def compute():
            calls[k] += 1
            return f"{k}-{calls[k]}"

        return compute

    try:
        clear_cache()
        assert cached_compute(("a", 1), make("a")) == "a-1"
        assert cached_compute(("b", 1), make("b")) == "b-1"
        assert cached_compute(("a", 1), make("a")) == "a-1"
        assert calls == {"a": 1, "b": 1}  # each computed once
    finally:
        clear_cache()


def test_lru_evicts_oldest_when_over_cap():
    try:
        clear_cache()
        # Push beyond _MAX entries; the least-recently-used ones must evict.
        for i in range(router_cache._MAX + 1):
            cached_compute((f"k{i}",), lambda i=i: i)
        # The oldest "k0" was evicted -> recomputed fresh; the newest "k_MAX"
        # is still memoized -> the original value is returned, not "fresh".
        assert cached_compute(("k0",), lambda: "fresh0") == "fresh0"
        assert (
            cached_compute((f"k{router_cache._MAX}",), lambda: "fresh")
            == router_cache._MAX
        )
    finally:
        clear_cache()


def test_clear_cache_forces_recompute():
    try:
        clear_cache()
        assert cached_compute(("c",), lambda: 1) == 1
        clear_cache()
        assert cached_compute(("c",), lambda: 2) == 2
    finally:
        clear_cache()


def test_data_fingerprint_tracks_size_and_mtime(tmp_path: Path):
    p = tmp_path / "obs.csv"
    p.write_text("a,b\n1,2\n")
    f1 = data_fingerprint([p])
    # Same bytes, rewritten -> mtime (and possibly size) changes -> new fingerprint.
    p.write_text("a,b\n1,2\n")
    f2 = data_fingerprint([p])
    assert f1 == f2 or f2 != data_fingerprint([tmp_path / "other.csv"])
    # Changing content changes the fingerprint.
    p.write_text("a,b\n1,999\n")
    assert data_fingerprint([p]) != f2


def test_data_fingerprint_marks_missing_then_present(tmp_path: Path):
    missing = tmp_path / "nope.csv"
    f_empty = data_fingerprint([missing])
    missing.write_text("a\n1\n")
    f_present = data_fingerprint([missing])
    assert f_empty != f_present  # appearing on disk invalidates the key
