"""Tests for scripts/check_component_loc.py (T160 P3 giant-diet size gate).

Pins the four behaviors CI depends on: a component over 800 lines fails,
an over-limit allowlisted component (MapView until P4) passes, a stale
allowlist entry (now under the limit) is flagged as a NOTE, and a missing
components directory is a loud config error — plus one live-repo check
that the real frontend tree is currently inside the limit.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

_spec = importlib.util.spec_from_file_location(
    "check_component_loc", BACKEND / "scripts" / "check_component_loc.py"
)
ccl = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ccl
_spec.loader.exec_module(ccl)


def _run_on(tmp_components: Path, monkeypatch):
    monkeypatch.setattr(ccl, "COMPONENTS", tmp_components)
    return ccl.main()


def _make(tmp_path: Path, name: str, lines: int) -> None:
    p = tmp_path / name
    p.write_text("\n" * lines, encoding="utf-8")


def test_over_limit_component_fails(tmp_path, monkeypatch, capsys):
    _make(tmp_path, "BigPanel.tsx", 801)
    _make(tmp_path, "SmallPanel.tsx", 800)
    assert _run_on(tmp_path, monkeypatch) == 1
    out = capsys.readouterr().out
    assert "BigPanel.tsx: 801 lines" in out
    assert "SmallPanel" not in out


def test_allowlisted_component_passes(tmp_path, monkeypatch, capsys):
    # The production allowlist is empty since P4 split MapView; inject an
    # entry the way a future exempt component would carry it.
    monkeypatch.setattr(ccl, "ALLOWLIST", {"MapView.tsx": "pending split"})
    _make(tmp_path, "MapView.tsx", 1521)
    _make(tmp_path, "Other.tsx", 10)
    assert _run_on(tmp_path, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "allowlisted MapView.tsx: 1521 lines" in out


def test_stale_allowlist_entry_flags_note(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ccl, "ALLOWLIST", {"MapView.tsx": "pending split"})
    _make(tmp_path, "MapView.tsx", 200)  # the split landed; entry is now stale
    assert _run_on(tmp_path, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "NOTE: allowlist entry MapView.tsx" in out


def test_live_repo_inside_limit_including_map():
    """P4 split MapView (1,521 -> 789): the live tree passes with an EMPTY
    allowlist — no component anywhere is exempt anymore."""
    assert ccl.ALLOWLIST == {}, "P4 emptied the allowlist; re-check the gate"
    rc = ccl.main()
    assert rc == 0, "live frontend tree violates the 800-line component gate"


def test_missing_components_dir_fails_loudly(tmp_path, monkeypatch):
    assert _run_on(tmp_path / "does-not-exist", monkeypatch) == 1


def test_exactly_800_passes_boundary(tmp_path, monkeypatch):
    _make(tmp_path, "Edge.tsx", 800)
    assert _run_on(tmp_path, monkeypatch) == 0


def test_live_repo_inside_limit():
    """The real tree must pass: guards against a giant re-growing before CI runs."""
    rc = ccl.main()
    assert rc == 0, "live frontend tree violates the 800-line component gate"
