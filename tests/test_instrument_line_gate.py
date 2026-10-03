"""Instrument-line gate: floor-vs-live regression tests (2026-09-25).

Pins the two failure classes fixed on 2026-09-25:

  A. Dishonest floors — the weekly refresh ROUNDED instead of FLOORED
     (5,795,382 departures -> "5.8M+", 99.18% -> "99.2%"). The gate must
     flag any claim above the live count, on any of the three numbers,
     while honest floors pass clean.

  B. Missing data home on CI — demo_stats.data_home() raises SystemExit
     (BaseException, NOT Exception), which the old bare `except Exception`
     never caught, so every CI run crashed with exit 1 and zero output.
     An empty home (exists but has no windows/departures) would brand every
     honest floor an impossible claim against live=0. Both must come out as
     report-only CANNOT-VERIFY with the gate still exiting 0 (DEC-16).

The demo_stats import inside the gate is real (module-level machinery),
so these tests monkeypatch its functions — the same seam the refresh
script exercises — rather than fabricating a data home on disk.

The gate anchors on the '**The instrument:**' LINE (a single line of the
README), so the fixture keeps the whole sentence on one line exactly like
the real showcase README does.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from scripts import verify_public_findings as v

README_LINE = (
    "**The instrument:** a platform. As of September 2026 it has logged "
    "**{polls}+ polls at {pct}% success** and captured **{deps}M+ unique "
    "scheduled bus departures** for measurement.\n"
)


def _make_public_dir(tmp_path: Path, polls: str, pct: str, deps: str) -> Path:
    """A minimal showcase layout: public_dir -> docs/findings, README two up."""
    public_dir = tmp_path / "docs" / "findings"
    public_dir.mkdir(parents=True)
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Showcase\n\n" + README_LINE.format(polls=polls, pct=pct, deps=deps),
        encoding="utf-8",
    )
    return public_dir


def _install_fake_demo_stats(monkeypatch, data_home, coverage, deps):
    fake = types.ModuleType("demo_stats")
    fake.data_home = data_home
    fake.coverage_stats = coverage
    fake.unique_departures = deps
    monkeypatch.setitem(sys.modules, "demo_stats", fake)


@pytest.fixture()
def fake_demo_stats(monkeypatch):
    """Controllable stand-ins for the demo_stats functions the gate calls,
    with the real machine's live values as defaults."""
    _install_fake_demo_stats(
        monkeypatch,
        data_home=lambda: Path("C:/nonexistent/home"),
        coverage=lambda home: (259, 85169, 84467),
        deps=lambda home: 5_795_382,
    )


def test_impossible_departure_floor_is_drift(tmp_path, fake_demo_stats):
    # Live 5,795,382 but the line claims 5.8M+: the exact rounding bug.
    public_dir = _make_public_dir(tmp_path, "85,000", "99.1", "5.8")
    hits, env = v.instrument_line_consistency(public_dir)
    assert hits and any("impossible floor" in d for _, d in hits)
    assert not env


def test_impossible_polls_floor_is_drift(tmp_path, fake_demo_stats):
    public_dir = _make_public_dir(tmp_path, "86,000", "99.1", "5.7")
    hits, _env = v.instrument_line_consistency(public_dir)
    assert hits and any("impossible floor" in d for _, d in hits)


def test_uprounded_success_rate_is_drift(tmp_path, fake_demo_stats):
    # Live 99.18% but the line claims 99.2%: up-rounded past the truth.
    public_dir = _make_public_dir(tmp_path, "85,000", "99.2", "5.7")
    hits, _env = v.instrument_line_consistency(public_dir)
    assert hits and any("up-rounded" in d for _, d in hits)


def test_honest_floors_pass_clean(tmp_path, fake_demo_stats):
    # The exact line the fixed refresh script writes for these live values.
    public_dir = _make_public_dir(tmp_path, "85,000", "99.1", "5.7")
    hits, env = v.instrument_line_consistency(public_dir)
    assert hits == []
    assert env == []


def test_stale_floor_more_than_half_million_behind_is_drift(tmp_path, fake_demo_stats):
    public_dir = _make_public_dir(tmp_path, "85,000", "99.1", "5.2")
    hits, _env = v.instrument_line_consistency(public_dir)
    assert hits and any("behind live" in d for _, d in hits)


def test_missing_data_home_systemexit_is_cannot_verify(tmp_path, monkeypatch):
    """The CI crash: data_home() raised SystemExit, except Exception never
    caught it, the gate died with exit 1 and no output. Must be an env note,
    with zero fatal hits."""

    def boom():
        raise SystemExit(
            "MIWAY_DATA_DIR and LOCALAPPDATA both unset; cannot locate data home"
        )

    _install_fake_demo_stats(
        monkeypatch,
        data_home=boom,
        coverage=lambda home: (0, 0, 0),
        deps=lambda home: 0,
    )

    public_dir = _make_public_dir(tmp_path, "85,000", "99.1", "5.7")
    hits, env = v.instrument_line_consistency(public_dir)
    assert hits == []
    assert env and "CANNOT-VERIFY" in env[0][1]


def test_empty_data_home_is_cannot_verify_not_impossible_floor(tmp_path, monkeypatch):
    """A home that exists but has nothing in it (CI runner): live=0 must not
    brand honest floors impossible — the floor-vs-live check is skipped."""
    _install_fake_demo_stats(
        monkeypatch,
        data_home=lambda: Path("C:/empty/home"),
        coverage=lambda home: (0, 0, 0),
        deps=lambda home: 0,
    )

    public_dir = _make_public_dir(tmp_path, "85,000", "99.1", "5.7")
    hits, env = v.instrument_line_consistency(public_dir)
    assert hits == []
    assert env and "CANNOT-VERIFY" in env[0][1]


def test_env_only_failures_keep_exit_zero():
    """DEC-16 end-to-end: a run whose only findings are CANNOT-VERIFY env
    notes must exit 0 (the pre-fix CI behavior was exit 1 on every run)."""
    rows = [("instrument-line", "CANNOT-VERIFY", "data home empty (CI)")]
    assert v.exit_code(rows, drift=0, identity_count=0) == 0
