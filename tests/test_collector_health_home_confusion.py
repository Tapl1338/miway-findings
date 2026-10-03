"""Tests for collector_health's home-confusion warning.

Sept 6 2026: the data-home migration flipped the config default, so a bare
`collector_health.py` silently checked the EMPTY new home and reported
"collector not running" while the real collector polled away in the old
home — and a launcher doing the same would have started a second collector
into the empty one. The warning makes an empty-home check unmistakable
whenever a known alternate home holds real data.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "collector_health_mod", BACKEND / "scripts" / "collector_health.py"
)
ch = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ch
_spec.loader.exec_module(ch)


def _make_home(root: Path, name: str, with_data: bool) -> Path:
    home = root / name
    home.mkdir(parents=True)
    if with_data:
        # Over the 1 MB "has real history" threshold
        (home / "obs_lateness.csv").write_bytes(b"x" * 1_100_000)
    else:
        (home / "obs_lateness.csv").write_bytes(b"route,stop\n")
    return home / "collector.pid"


def test_warns_when_checked_home_empty_and_alternate_has_data(tmp_path, capsys):
    checked = _make_home(tmp_path, "empty_home", with_data=False)
    alt = _make_home(tmp_path, "real_home", with_data=True)
    ch._warn_home_confusion(checked, sys.stderr, _alternates=[alt])
    err = capsys.readouterr().err
    assert "HOME CONFUSION" in err
    assert "real_home" in err
    assert "WRONG home" in err


def test_silent_when_checked_home_has_data(tmp_path, capsys):
    checked = _make_home(tmp_path, "real_home", with_data=True)
    alt = _make_home(tmp_path, "other_home", with_data=True)
    ch._warn_home_confusion(checked, sys.stderr, _alternates=[alt])
    assert "HOME CONFUSION" not in capsys.readouterr().err


def test_silent_when_no_home_has_data(tmp_path, capsys):
    """A genuinely fresh install (both homes tiny) must not warn."""
    checked = _make_home(tmp_path, "home_a", with_data=False)
    alt = _make_home(tmp_path, "home_b", with_data=False)
    ch._warn_home_confusion(checked, sys.stderr, _alternates=[alt])
    assert "HOME CONFUSION" not in capsys.readouterr().err


def test_silent_when_no_alternates(tmp_path, capsys):
    checked = _make_home(tmp_path, "lone_home", with_data=False)
    ch._warn_home_confusion(checked, sys.stderr, _alternates=[])
    assert "HOME CONFUSION" not in capsys.readouterr().err
