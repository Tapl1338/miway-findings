"""Tests for the analytical lateness sensitivity model (app/sensitivity)."""

from __future__ import annotations

import numpy as np
import pytest
from app.sensitivity import (
    effective_waits,
    expected_missed_minutes,
    expected_missing,
    flip_threshold,
    laplace_cdf,
    miss_probability,
    sensitivity_rows,
    weighted_mean,
)


def _brute_force_miss_probability(waits, lower, upper, mu, draws: int = 200_000):
    """Monte-Carlo version: difference of two Exp(1/mu) is a Laplace variable."""
    rng = np.random.default_rng(7)
    lateness_i = rng.exponential(mu, size=(len(waits), draws))
    lateness_j = rng.exponential(mu, size=(len(waits), draws))
    diff = lateness_j - lateness_i
    achieved = waits[:, None] + diff
    missed = (achieved < lower[:, None]) | (achieved > upper)
    return missed.mean(axis=1)


def test_laplace_cdf_matches_exponential_difference():
    mu = 2.0
    xs = np.array([-5.0, -1.0, 0.0, 1.0, 5.0])
    rng = np.random.default_rng(1)
    diff = rng.exponential(mu, 400_000) - rng.exponential(mu, 400_000)
    empirical = np.array([(diff <= x).mean() for x in xs])
    assert np.allclose(laplace_cdf(xs, mu), empirical, atol=0.01)


def test_laplace_cdf_requires_positive_mu():
    with pytest.raises(ValueError):
        laplace_cdf(0.0, 0.0)


def test_miss_probability_conditional_consistency():
    waits = np.array([5.0, 5.0, 9.0])
    lower = np.array([2.0, 2.0, 2.0])
    upper = 12.0
    mu = 3.0
    p = miss_probability(waits, lower, upper, mu)
    assert np.all(p >= 0.0) and np.all(p <= 1.0)
    for w, lo, prob in zip(waits, lower, p):
        assert prob == pytest.approx(
            laplace_cdf(lo - w, mu) + (1.0 - laplace_cdf(upper - w, mu))
        )


def test_expected_missing_matches_brute_force():
    rng = np.random.default_rng(3)
    waits = rng.uniform(0.0, 15.0, 40)
    lower = np.full(40, 2.0)
    upper = 12.0
    mu = 2.5
    analytic = expected_missing(waits, lower, upper, mu)
    mc = _brute_force_miss_probability(waits, lower, upper, mu).sum()
    assert analytic == pytest.approx(mc, rel=0.05)


def test_expected_missed_minutes_weights_and_penalties():
    waits = np.array([5.0, 6.0])
    lower = np.array([2.0, 2.0])
    upper = 12.0
    weights = np.array([2.0, 100.0])
    penalties = np.array([10.0, 15.0])
    mu = 4.0
    p = miss_probability(waits, lower, upper, mu)
    expected = float(np.sum(weights * penalties * p))
    assert expected_missed_minutes(
        waits, weights, penalties, lower, upper, mu
    ) == pytest.approx(expected)


def test_effective_waits_state_misses_bill_headway():
    waits = np.array([5.0, 1.0, 13.0])
    penalties = np.array([10.0, 20.0, 30.0])
    lower = np.array([2.0, 2.0, 2.0])
    upper = 12.0
    eff = effective_waits(waits, penalties, lower, upper)
    assert eff.tolist() == [5.0, 21.0, 43.0]


def test_weighted_mean():
    assert weighted_mean(np.array([1.0, 3.0]), np.array([1.0, 1.0])) == 2.0
    assert weighted_mean(np.array([1.0, 3.0]), np.array([0.0, 0.0])) == 0.0


def test_flip_threshold_none_when_optimized_always_better():
    # Optimizer pulls the high/low waits (1, 13) into the middle (6), which
    # shortens the expected-miss curve at every mu through the 12-min cap.
    waits_base = np.array([1.0, 13.0])
    waits_opt = np.array([6.0, 6.0])
    lower = np.full(2, 2.0)
    upper = 12.0
    weights = np.ones(2)
    penalties = np.full(2, 15.0)
    assert (
        flip_threshold(waits_base, waits_opt, weights, penalties, lower, upper) is None
    )


def test_flip_threshold_found_when_optimized_waits_hug_the_floor():
    # A plan that pins waits 0.5 min above the 2-min floor is fragile: any
    # slight extra disruption makes the arriving bus too late to make the
    # transfer, so the advantage flips to baseline almost immediately. This is
    # the risk the sensitivity report is designed to surface.
    waits_base = np.array([7.0, 7.0])
    waits_opt = np.array([2.5, 2.5])
    lower = np.full(2, 2.0)
    upper = 12.0
    weights = np.ones(2)
    penalties = np.full(2, 15.0)
    flip = flip_threshold(waits_base, waits_opt, weights, penalties, lower, upper)
    assert flip is not None and flip <= 1.0


def test_sensitivity_rows_monotonic_expected_misses():
    waits_base = np.array([5.0, 13.0, 1.0])
    waits_opt = np.array([5.0, 6.0, 4.0])
    lower = np.full(3, 2.0)
    upper = 12.0
    weights = np.ones(3)
    penalties = np.full(3, 15.0)
    rows = sensitivity_rows(
        waits_base,
        waits_opt,
        weights,
        penalties,
        lower,
        upper,
        mus=[0.5, 1.0, 2.0, 4.0],
    )
    assert [r["mean_lateness_min"] for r in rows] == [0.5, 1.0, 2.0, 4.0]
    assert len(rows) == 4
    for r in rows:
        assert r["base_missed_minutes"] >= r["opt_missed_minutes"]
        assert r["saved_minutes"] >= 0
