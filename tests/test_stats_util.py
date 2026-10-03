"""Unit tests for app.stats_util (Wilson intervals + median/IQR)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.stats_util import (
    fmt_median_iqr,
    fmt_pct_ci,
    median_iqr,
    wilson_interval,
)


def test_wilson_matches_known_values() -> None:
    # Worked example hand-derived from the closed form: 81/263, z=1.96:
    # center 0.31072, half-width 0.05546 -> [25.53%, 36.62%].
    lo, hi = wilson_interval(81, 263)
    assert 25.5 < lo < 25.6 and 36.5 < hi < 36.8
    # Symmetric at p=0.5, n large.
    lo, hi = wilson_interval(500, 1000)
    assert abs(50.0 - (lo + hi) / 2) < 0.01


def test_wilson_bounds_respect_zero_and_hundred() -> None:
    # Degenerate cases return their exact one-sided bounds.
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0
    lo, hi = wilson_interval(10, 10)
    assert hi == 100.0


def test_wilson_none_and_wide_on_tiny_n() -> None:
    assert wilson_interval(3, 0) is None
    lo, hi = wilson_interval(3, 10)  # 30% at n=10 -> roughly 10.8-60.3
    assert 10 < lo < 12 and 58 < hi < 62


def test_fmt_pct_ci_renders() -> None:
    out = fmt_pct_ci(17.1, 77_610, 453_857)
    assert out.startswith("17.1% (95% CI ")
    assert out.endswith(")")


def test_median_iqr_matches_numpy_linear_convention() -> None:
    # Odd n: quartiles land exactly on elements (k integer).
    # [0.2..1.1], n=9: k(0.25)=2 -> 0.4; k(0.5)=4 -> 0.6; k(0.75)=6 -> 0.8.
    s = median_iqr([0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.1])
    assert s is not None
    assert abs(s["q1"] - 0.4) < 1e-9
    assert abs(s["median"] - 0.6) < 1e-9
    assert abs(s["q3"] - 0.8) < 1e-9
    assert abs(s["iqr"] - 0.4) < 1e-9
    assert s["n"] == 9


def test_median_iqr_interpolates_between_elements() -> None:
    # Even n: linear interpolation (pandas 'linear' convention).
    # [0.2, 0.3, 0.4, 0.5]: k(0.25)=0.75 -> 0.275; k(0.5)=1.5 -> 0.35;
    # k(0.75)=2.25 -> 0.4 + 0.1*0.25 = 0.425.
    s = median_iqr([0.2, 0.3, 0.4, 0.5])
    assert s is not None
    assert abs(s["q1"] - 0.275) < 1e-9
    assert abs(s["median"] - 0.35) < 1e-9
    assert abs(s["q3"] - 0.425) < 1e-9


def test_median_iqr_handles_none_and_empty() -> None:
    assert median_iqr([]) is None
    assert median_iqr([None, None]) is None
    assert median_iqr([None, 1.0])["median"] == 1.0


def test_fmt_median_iqr_renders() -> None:
    out = fmt_median_iqr([0.329, 0.2, 0.5, 0.9, 0.6, 0.4, 0.8, 1.2, 0.7])
    assert out is not None
    assert "(IQR " in out
