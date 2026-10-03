"""Tests for scripts/ridership_band_lyu.py (Lyu OTP-elasticity re-derivation).

The Lyu & Yan paper (arXiv 2511.07467, archived in docs/sources/) is the
project's only direct post-pandemic on-time-rate elasticity source. This
script is how its coefficients may legitimately enter prose: re-derived from
the frozen exec-summary artifact, never hand-computed. Pins the arithmetic,
the zero-on-time guard, and artifact sanity of the real repo state.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

_spec = importlib.util.spec_from_file_location(
    "ridership_band_lyu", BACKEND / "scripts" / "ridership_band_lyu.py"
)
rbl = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = rbl
_spec.loader.exec_module(rbl)


def _fake_exec(base: int, opt: int, n: int) -> dict:
    return {
        "result": {"base_missed": base, "opt_missed": opt, "total_connections": n},
        "money": {"ridership_gain_pct": 1.94},
    }


def test_band_matches_hand_computation():
    """51.4% -> 58.9% on-time (july basis, T155) = +14.62% relative; x system 0.417 = +6.10%."""
    out = rbl.rederive(_fake_exec(2916, 2465, 6000))
    assert out["relative_otp_gain_pct"] == 14.62
    assert out["projected_ridership_pct_lyu"] == 6.1
    assert out["projected_ridership_pct_lyu_lo"] == 3.89
    assert out["projected_ridership_pct_lyu_hi"] == 8.54
    assert out["projected_ridership_pct_lyu_floor"] == 0.0


def test_band_ordering_low_central_high():
    out = rbl.rederive(_fake_exec(2789, 2456, 6000))
    assert out["projected_ridership_pct_lyu_lo"] < out["projected_ridership_pct_lyu"]
    assert out["projected_ridership_pct_lyu"] < out["projected_ridership_pct_lyu_hi"]


def test_zero_base_on_time_raises():
    """A degenerate artifact (all transfers missed) must fail loudly, not emit inf."""
    try:
        rbl.rederive(_fake_exec(6000, 3000, 6000))
    except SystemExit:
        return
    raise AssertionError("expected SystemExit for zero base on-time rate")


def test_real_artifact_still_produces_the_documented_band():
    """The doc's quoted band must always equal what the frozen artifact yields.

    If exec-summary.json is ever regenerated with new solver numbers, this
    test fails until docs/ridership-band-lyu.md is re-derived — the same
    discipline the quote gate applies to prose, applied to the method doc.
    """
    data = json.loads((REPO / "docs" / "exec-summary.json").read_text(encoding="utf-8"))
    out = rbl.rederive(data)
    assert (
        out["projected_ridership_pct_lyu"],
        out["projected_ridership_pct_lyu_lo"],
        out["projected_ridership_pct_lyu_hi"],
    ) == (6.1, 3.89, 8.54)


def test_real_doc_quotes_the_real_band():
    """The method doc's headline line must carry the artifact-derived numbers."""
    # 45353cf (2026-09-24 docs consolidation) moved the private twin to
    # docs/archive/root/ (frozen era doc; re-derived + re-pinned at 33cda71,
    # T155 july-basis). verify_public_findings.EXPLICIT_SOURCE already maps
    # the public copy there; this test kept the pre-consolidation path and
    # failed with FileNotFoundError from 2026-09-24 onward. Prefer the live
    # archive location; fall back to the pre-consolidation path for checkouts
    # pinned before 45353cf.
    doc_path = REPO / "docs" / "archive" / "root" / "ridership-band-lyu.md"
    if not doc_path.exists():
        doc_path = REPO / "docs" / "ridership-band-lyu.md"
    doc = doc_path.read_text(encoding="utf-8")
    for token in ("+6.1% central", "+3.9% to +8.5%"):
        assert token in doc, f"method doc missing {token!r}"
