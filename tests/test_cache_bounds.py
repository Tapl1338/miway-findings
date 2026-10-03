"""The disk cache must be bounded.

Before this module was swept, ``app/data/cache`` grew without limit: 5,236
pickles / 80 GB, none ever deleted. Worse, cache keys embed the GTFS feed
fingerprint, so the Sept 8 feed change orphaned *every* existing entry at
once while a fresh generation accumulated on top. These tests pin the two
sweep rules: superseded-feed generations are deleted outright, and the
current generation evicts oldest-first under the size cap.
"""

from __future__ import annotations

import pickle
import time

from app import cache


def _mk(cache_dir, name: str, size: int = 10, mtime: float | None = None):
    p = cache_dir / name
    p.write_bytes(pickle.dumps("x" * size))
    if mtime is not None:
        ts = mtime
        import os

        os.utime(p, (ts, ts))
    return p


def test_sweep_deletes_superseded_feed_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    fp = cache.feed_fingerprint()
    old = _mk(tmp_path, "deadbeef-000000000000000000000000.pkl", 1000)
    _mk(tmp_path, "deadbeef-000000000000000000000000.tmp", 1000)
    keep = _mk(tmp_path, f"{fp}-aaaaaaaaaaaaaaaaaaaaaaaa.pkl", 1000)

    cache._sweep()

    assert not old.exists()
    assert keep.exists()


def test_sweep_size_cap_evicts_oldest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    # Each entry pickles to ~1 KB, so a 1.5 KB cap retains exactly one.
    monkeypatch.setattr(cache.config, "CACHE_MAX_GB", 1.5e-6)
    fp = cache.feed_fingerprint()
    old = _mk(
        tmp_path, f"{fp}-111111111111111111111111.pkl", 1000, mtime=time.time() - 500
    )
    new = _mk(tmp_path, f"{fp}-222222222222222222222222.pkl", 1000, mtime=time.time())

    cache._sweep()

    # Oldest evicted first; the newest entry survives the cap.
    assert not old.exists()
    assert new.exists()


def test_sweep_removes_stale_crashed_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    fp = cache.feed_fingerprint()
    stale = _mk(
        tmp_path, f"{fp}-333333333333333333333333.tmp", mtime=time.time() - 90000
    )
    fresh = _mk(tmp_path, f"{fp}-444444444444444444444444.pkl")

    cache._sweep()

    assert not stale.exists()
    assert fresh.exists()


def test_sweep_ignores_unrelated_files(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    fp = cache.feed_fingerprint()
    other = _mk(tmp_path, "notes.txt")
    keep = _mk(tmp_path, f"{fp}-555555555555555555555555.pkl")

    cache._sweep()

    assert other.exists()  # only .pkl/.tmp are cache-managed
    assert keep.exists()
