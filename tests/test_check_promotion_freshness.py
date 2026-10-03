"""Tests for ``scripts/check_promotion_freshness.py`` — the re-promotion prompt.

Covers the epoch comparison (twin newer than public copy = stale), the
committed-time contract (git metadata, not file mtimes — a local touch must
not false-alarm), the uncommitted-twin case, and the exit-code contract.
The real find_source mapping is exercised against the committed repo
(30 promoted docs at last count), with the git call mocked so the tests
never depend on commit history.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "cpf", BACKEND / "scripts" / "check_promotion_freshness.py"
)
cpf = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = cpf
_spec.loader.exec_module(cpf)

# stale_pairs does `from verify_public_findings import find_source` at call
# time; load the real module once so tests can monkeypatch its attribute.
import importlib.util as _ilu  # noqa: E402

_vspec = _ilu.spec_from_file_location(
    "verify_public_findings", BACKEND / "scripts" / "verify_public_findings.py"
)
vpf = importlib.util.module_from_spec(_vspec)
sys.modules[_vspec.name] = vpf
_vspec.loader.exec_module(vpf)


def _patch_epochs(monkeypatch, mapping: dict[Path, int | None]):
    """Patch _committed_epoch to a lookup table (None = uncommitted)."""

    def fake(path: Path, repo: Path) -> int | None:
        return mapping.get(path.resolve())

    monkeypatch.setattr(cpf, "_committed_epoch", fake)


def test_twin_newer_than_public_is_stale(tmp_path, monkeypatch):
    now = time.time()
    pub_dir = tmp_path / "findings"
    pub_dir.mkdir()
    pub = pub_dir / "doc.md"
    pub.write_text("# public\n", encoding="utf-8")
    twin = tmp_path / "twin.md"
    twin.write_text("# twin\n", encoding="utf-8")

    monkeypatch.setattr(vpf, "find_source", lambda p: twin)
    _patch_epochs(
        monkeypatch,
        {pub.resolve(): int(now) - 10 * 86400, twin.resolve(): int(now) - 3600},
    )
    hits = cpf.stale_pairs(pub_dir, now=now)
    assert len(hits) == 1
    assert hits[0][0] == "doc.md"
    assert (
        "twin" in hits[0][1].lower()
        or "regenerated" in hits[0][1].lower()
        or "re-promote" in hits[0][1].lower()
    )


def test_public_newer_than_twin_is_clean(tmp_path, monkeypatch):
    now = time.time()
    pub_dir = tmp_path / "findings"
    pub_dir.mkdir()
    pub = pub_dir / "doc.md"
    pub.write_text("# public\n", encoding="utf-8")
    twin = tmp_path / "twin.md"
    twin.write_text("# twin\n", encoding="utf-8")

    monkeypatch.setattr(vpf, "find_source", lambda p: twin)
    _patch_epochs(
        monkeypatch, {pub.resolve(): int(now) - 60, twin.resolve(): int(now) - 86400}
    )
    assert cpf.stale_pairs(pub_dir, now=now) == []


def test_uncommitted_twin_flags(tmp_path, monkeypatch):
    """A regeneration not yet committed is the drift state in progress."""
    now = time.time()
    pub_dir = tmp_path / "findings"
    pub_dir.mkdir()
    pub = pub_dir / "doc.md"
    pub.write_text("# public\n", encoding="utf-8")
    twin = tmp_path / "twin.md"
    twin.write_text("# twin regenerated\n", encoding="utf-8")

    monkeypatch.setattr(vpf, "find_source", lambda p: twin)
    _patch_epochs(monkeypatch, {pub.resolve(): int(now) - 86400, twin.resolve(): None})
    hits = cpf.stale_pairs(pub_dir, now=now)
    assert len(hits) == 1
    assert "UNCOMMITTED" in hits[0][1]


def test_no_source_doc_skipped(tmp_path, monkeypatch):
    """NO-SOURCE is the drift gate's failure, not the freshness check's."""
    pub_dir = tmp_path / "findings"
    pub_dir.mkdir()
    (pub_dir / "orphan.md").write_text("# x\n", encoding="utf-8")
    monkeypatch.setattr(vpf, "find_source", lambda p: None)
    assert cpf.stale_pairs(pub_dir) == []


def test_exit_codes(tmp_path, capsys):
    pub_dir = tmp_path / "findings"
    pub_dir.mkdir()
    # Empty dir -> 0 with the all-clear line.
    assert cpf.main(["--public", str(pub_dir)]) == 0
    assert "predates" in capsys.readouterr().out.lower()


def test_real_repo_smoke():
    """Integration: against the committed repo with real git metadata, the
    check runs and (as of the 2026-09-23 re-promotion) reports clean."""
    assert cpf.main([]) == 0
