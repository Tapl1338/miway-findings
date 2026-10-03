"""Atomic writers must not create 0600 files — the mirror-freeze root cause.

``tempfile.mkstemp`` creates files mode ``0600`` **by design**. When the
analysis chain runs as root on the VPS, every atomic rewrite of a synced
file (``obs_lateness.csv``'s window-end dedup, the daily outputs) replaced
it with a root-only inode: the ubuntu-run Syncthing lost read access and
the laptop mirror silently froze (Sept 14 and Sept 16 incidents — the
second caught by the T109 freshness escalation).

The writers in ``scripts/data_dir_util.py`` (and the two inline copies in
``ride_speeds``/``realized_waits``) must restore the mode an ordinary
``open()`` under the current umask would have produced. These tests pin
exactly that, POSIX-only (the VPS is the POSIX surface; on Windows chmod
only toggles a read-only bit and the assertion is meaningless).
"""

from __future__ import annotations

import os
import stat

import pytest

from scripts.data_dir_util import atomic_write_text


def _write_under_umask(tmp_path, umask: int) -> int:
    target = tmp_path / "out.csv"
    old = os.umask(umask)
    try:
        atomic_write_text(target, "route_short_name,stop_id\n")
    finally:
        os.umask(old)
    return stat.S_IMODE(target.stat().st_mode)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits only")
def test_atomic_write_restores_umask_mode(tmp_path):
    """Default-ish umask 022 -> the world-readable 0644 an open() would give."""
    assert _write_under_umask(tmp_path, 0o022) == 0o644


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits only")
def test_atomic_write_honors_restrictive_umask(tmp_path):
    """The mode comes from the umask, not a hardcoded 0644: 077 -> 0600."""
    assert _write_under_umask(tmp_path, 0o077) == 0o600


def test_atomic_write_replaces_target(tmp_path):
    """Sanity: the replace itself still works (content lands, tmp is gone)."""
    target = tmp_path / "out.csv"
    target.write_text("old\n", encoding="utf-8")
    atomic_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"
    assert not list(tmp_path.glob("*.tmp"))
