"""T29 probe lock-in: statistical invariants for app/sensitivity.py and
diagnostics classification rules (REDFLAG T29 section).

These encode the CORRECTED expectations from the adversarial pass:
* A connection sitting exactly on the keep-window floor misses with
  probability 0.5 + 0.5*exp(-(upper-lower_floor_gap)/mu) -- the departing bus
  can also be far enough EARLY to blow the cap.
* Miss probability is NOT monotone in mu for waits outside the window:
  heavy two-sided tails rescue over-cap waits via very-negative differences.
"""

import numpy as np
from app import config
from app import sensitivity as S


def test_laplace_cdf_matches_density_integral():
    mu = 4.0
    grid = np.linspace(-60, 60, 240_001)
    pdf = np.where(
        grid <= 0,
        np.exp(grid / mu) / (2 * mu),
        np.exp(-(grid - 0.0) / mu) / (2 * mu),
    )
    cdf_num = np.concatenate(
        [[0.0], np.cumsum((pdf[1:] + pdf[:-1]) / 2 * np.diff(grid))]
    )
    assert np.allclose(S.laplace_cdf(grid, mu), cdf_num, atol=2e-3)


def test_laplace_cdf_symmetry():
    xs = np.array([-13.7, -3.0, -0.5, 0.0, 0.5, 3.0, 13.7])
    assert np.allclose(S.laplace_cdf(-xs, 4.0), 1 - S.laplace_cdf(xs, 4.0))


def test_floor_sitting_miss_probability_has_two_components():
    """P(miss) = 0.5 (floor breach) + 0.5*exp(-cap_gap/mu) (early departure)."""
    p = float(S.miss_probability([2.0], [2.0], [12.0], 5.0)[0])
    want = 0.5 + 0.5 * np.exp(-10.0 / 5.0)
    assert abs(p - want) < 1e-12


def test_centered_wait_closed_form():
    for m_ in (2.0, 5.0, 10.0):
        p = float(S.miss_probability([7.0], [2.0], [12.0], m_)[0])
        assert abs(p - float(np.exp(-5.0 / m_))) < 1e-12


def test_monotone_in_mu_holds_INSIDE_window_only():
    """Inside-window waits are monotone; out-of-window waits are not --
    document the model rather than asserting a false universal."""
    mus = np.linspace(0.25, 12, 47)
    low = np.full(3, 2.0)
    upp = np.full(3, 12.0)

    inside = np.array(
        [S.miss_probability([8.0], low[:1], upp[:1], float(m))[0] for m in mus]
    )
    assert np.all(np.diff(inside) >= -1e-12)

    outside = np.array(
        [S.miss_probability([20.0], low[:1], upp[:1], float(m))[0] for m in mus]
    )
    assert np.all(np.diff(outside) <= 1e-12)  # monotonically DECREASING


def test_expected_missing_bounded_by_n():
    waits = np.array([3.0, 8.0, 11.5, 20.0])
    em = S.expected_missing(waits, np.full(4, 2.0), np.full(4, 12.0), 6.0)
    assert 0 <= em <= len(waits) + 1e-9


def test_flip_threshold_semantics():
    tb = [5.0, 9.0]
    pen = [15.0, 30.0]
    lo, hi = [2.0, 2.0], [12.0, 12.0]
    # Equal schedules: 'stops winning' immediately at mu_min.
    assert S.flip_threshold(tb, tb, [1.0, 1.0], pen, lo, hi) == 0.25


def _classify(wait, gap=None, *, t_max=None, max_shift=5.0):
    if t_max is None:
        t_max = config.T_MAX
    if 2.0 <= wait <= t_max:
        return None
    reason = "too long" if wait > t_max else "too short"
    category = "modeled"
    if wait > t_max + 2 * max_shift:
        category = "hidden"
    if reason == "too long" and gap is not None and abs(gap) <= 3.0:
        category = "just_missed"
    return category, reason


def test_diagnostics_hidden_and_just_missed_precedence():
    assert _classify(12.0) is None
    assert _classify(12.01)[1] == "too long"
    assert _classify(30.0)[0] == "hidden"
    # just-missed overrides hidden (rider story dominates the bucket label)
    assert _classify(30.0, gap=1.0)[0] == "just_missed"
    # short next-wait after previous bus stays modeled/too-short
    assert _classify(1.0, gap=1.0) == ("modeled", "too short")
    # negative gap counts via abs() -- defensive, kept
    assert _classify(30.0, gap=-1.0)[0] == "just_missed"
