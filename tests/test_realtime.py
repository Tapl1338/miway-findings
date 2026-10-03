"""Unit tests for app/realtime.py (observed-lateness / AVL-GTFS-RT plumbing).

These use small synthetic DataFrames, not the real feed, so they run fast and
in isolation: the module's contract is CSV-shape parsing, per-route stats and
bootstrap sampling — all data-format logic, not solver logic.
"""

import numpy as np
import pandas as pd
import pytest
from app.realtime import (
    dedup_observations,
    filter_actuals_only,
    lateness_by_route,
    lateness_coverage,
    lateness_summary,
    load_observed_lateness,
    sample_connection_lateness,
)


@pytest.fixture
def obs_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "route_short_name": ["1", "1", "2", "2", "2"],
            "stop_id": ["a", "b", "a", "b", "c"],
            "dep_time_min": [410.0, 415.0, 420.0, 425.0, 430.0],
            "lateness_minutes": [1.0, -0.5, 2.0, 3.0, 11.0],
        }
    )


def test_load_observed_lateness_parses_and_coerces(tmp_path, obs_df):
    path = tmp_path / "obs.csv"
    obs_df.to_csv(path, index=False)
    df = load_observed_lateness(str(path))
    assert len(df) == 5
    # Route short names must be strings (GTFS ids like "001" survive the trip).
    assert all(isinstance(v, str) for v in df["route_short_name"])
    assert set(df["route_short_name"]) == {"1", "2"}
    # Latency column is numeric.
    assert df["lateness_minutes"].dtype == np.float64


def test_load_observed_lateness_drops_nan_and_requires_column(tmp_path):
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "2"],
            "lateness_minutes": [1.0, np.nan],
        }
    )
    path = tmp_path / "obs.csv"
    df.to_csv(path, index=False)
    parsed = load_observed_lateness(str(path))
    assert len(parsed) == 1  # NaN lateness row dropped

    bad = pd.DataFrame({"route_short_name": ["1"], "delay": [1.0]})
    bad_path = tmp_path / "bad.csv"
    bad.to_csv(bad_path, index=False)
    with pytest.raises(ValueError, match="lateness_minutes"):
        load_observed_lateness(str(bad_path))


def test_filter_actuals_only_keeps_recorded_departures():
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1", "1", "2", "2"],
            "lateness_minutes": [0.5, -1.0, -4.5, 2.0, 1.0],
            "horizon_minutes": [-5.0, 0.0, 12.0, -3.0, None],
        }
    )
    out = filter_actuals_only(df)
    # Keeps negative/zero horizons (recorded actuals); drops future forecasts
    # (positive horizon) and legacy rows with no horizon.
    assert len(out) == 3
    assert set(out["horizon_minutes"].tolist()) == {-5.0, 0.0, -3.0}
    # Legacy frame without the column passes through untouched.
    legacy = df.drop(columns=["horizon_minutes"])
    assert len(filter_actuals_only(legacy)) == len(legacy)


def test_load_observed_lateness_filters_to_actuals_by_default(tmp_path):
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1", "1"],
            "lateness_minutes": [0.5, -4.5, 2.0],
            "horizon_minutes": [-5.0, 12.0, -3.0],
        }
    )
    path = tmp_path / "obs.csv"
    df.to_csv(path, index=False)
    parsed = load_observed_lateness(str(path))
    assert len(parsed) == 2  # future forecast (horizon +12) dropped
    all_rows = load_observed_lateness(str(path), actuals_only=False)
    assert len(all_rows) == 3


def test_dedup_observations_keeps_most_negative_horizon_per_departure():
    # The same (route, stop, scheduled dep) reappears once per poll with an
    # advancing horizon; only the freshest reading should survive.
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1", "1", "2", "2"],
            "stop_id": ["a", "a", "a", "b", "b"],
            "dep_time_min": [410.0, 410.0, 410.0, 415.0, 415.0],
            "lateness_minutes": [1.0, 0.5, 0.0, 2.0, 1.5],
            "horizon_minutes": [-1.0, -3.0, -2.0, -4.0, None],
        }
    )
    out = dedup_observations(df)
    assert len(out) == 2  # one row per departure, not per poll
    kept = out[out["stop_id"] == "a"]
    assert len(kept) == 1
    # Route 1's kept row is the most-negative (freshest) reading.
    assert kept["horizon_minutes"].iloc[0] == -3.0
    # Route 2 keeps its only horizon-bearing row over the legacy NaN one.
    r2 = out[out["stop_id"] == "b"]
    assert r2["horizon_minutes"].iloc[0] == -4.0
    # Frames without the identity columns pass through unchanged.
    legacy = df.drop(columns=["stop_id", "dep_time_min"])
    assert len(dedup_observations(legacy)) == len(legacy)


def test_dedup_observations_keeps_same_slot_on_different_dates():
    """The dedup key includes date: the same scheduled slot on different
    days is a DIFFERENT observation.

    Regression for the 2026-09-04 find: the reader's key omitted date, so
    the whole collected week collapsed to one row per weekly identity
    (weekday rows dropped ~10x vs the raw file; every weekday after the
    first silently vanished from per-route stats). Mirrors the collector's
    DEDUP_KEYS, which has carried date for exactly this reason.
    """
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1", "1", "1"],
            "stop_id": ["a", "a", "a", "a"],
            "dep_time_min": [410.0, 410.0, 410.0, 410.0],
            "lateness_minutes": [1.0, 2.0, 3.0, 4.0],
            "horizon_minutes": [-1.0, -1.0, -1.0, -1.0],
            "date": ["20260901", "20260902", "20260903", "20260904"],
        }
    )
    out = dedup_observations(df)
    assert len(out) == 4  # one per day, not one per weekly identity
    assert sorted(out["date"]) == ["20260901", "20260902", "20260903", "20260904"]

    # A legacy frame with no date column still dedups on the bare identity.
    legacy = df.drop(columns=["date"])
    assert len(dedup_observations(legacy)) == 1


def test_dedup_collapses_cross_format_duplicates():
    """Float-era ("1042.0", "410.0") and int-era rows of the same departure
    are one identity after normalization — and empty cells don't crash.

    The live CSV carried two format eras per column (pre-Sept-2 rows written
    through pandas as floats, raw appends as ints); without normalization
    cross-format duplicates silently survived dedup.
    """
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1", "1"],
            "stop_id": ["1042.0", "1042", "0001"],  # float era, int era, padded
            "dep_time_min": [410.0, 410, ""],  # float era, int era, empty
            "lateness_minutes": [1.0, 2.0, 3.0],
            "horizon_minutes": [-1.0, -3.0, -2.0],
            "date": ["20260901", "20260901", "20260901"],
        }
    )
    out = dedup_observations(df)
    # The two eras of the same departure collapse; the padded id is distinct.
    assert len(out) == 2
    kept = out[out["stop_id"] == "1042"]
    assert len(kept) == 1
    assert kept["horizon_minutes"].iloc[0] == -3.0  # freshest reading wins
    # "0001" survives untouched: zero padding is real identity, and only the
    # float-era ".0" suffix is stripped (a naive float() round-trip would
    # have destroyed it).
    assert (out["stop_id"] == "0001").any()
    assert not out["stop_id"].str.contains(r"\.0$").any()
    assert pd.api.types.is_numeric_dtype(out["dep_time_min"])


def test_normalize_identity_survives_empty_and_garbage_cells():
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1"],
            "stop_id": ["", "stop_abc"],  # empty, non-numeric
            "dep_time_min": [410.0, ""],
            "lateness_minutes": [1.0, 2.0],
            "horizon_minutes": [-1.0, -1.0],
        }
    )
    out = dedup_observations(df)
    # Garbage key cells stay as-is (never crash). The empty dep cell loses
    # its row only if it duplicates another identity — here it doesn't, so
    # the NaN dep row survives as its own identity.
    assert out[out["stop_id"] == "stop_abc"].shape[0] == 1
    assert len(out) == 2


def test_load_observed_lateness_dedups_multi_poll_rows(tmp_path):
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1"],
            "stop_id": ["a", "a"],
            "dep_time_min": [410.0, 410.0],
            "lateness_minutes": [0.5, 0.0],
            "horizon_minutes": [-1.0, -3.0],
        }
    )
    path = tmp_path / "obs.csv"
    df.to_csv(path, index=False)
    # Without dedup the same departure would count twice; now it counts once.
    parsed = load_observed_lateness(str(path), actuals_only=False)
    assert len(parsed) == 1
    assert parsed["horizon_minutes"].iloc[0] == -3.0


def test_lateness_by_route_and_summary(obs_df):
    by_route = lateness_by_route(obs_df)
    assert set(by_route) == {"1", "2"}
    assert len(by_route["1"]) == 2
    assert len(by_route["2"]) == 3

    summary = lateness_summary(obs_df)
    assert summary["observed_departures"] == 5
    assert summary["routes_with_data"] == 2
    # Global mean of [1, -0.5, 2, 3, 11].
    assert summary["global"]["mean_min"] == pytest.approx(3.3)
    assert summary["per_route"]["2"]["count"] == 3


def test_lateness_summary_single_observation_has_no_nan():
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "2", "2"],
            "lateness_minutes": [0.5, 1.0, 2.0],
        }
    )
    summary = lateness_summary(df)
    # A one-observation route must not produce NaN std.
    assert summary["per_route"]["1"]["std_min"] == 0.0
    assert np.isfinite(summary["per_route"]["2"]["std_min"])


def test_lateness_coverage_buckets_by_period():
    # 410 min = AM Rush (06:00–09:00); 700 = Midday; 1300 = Late Night;
    # 300 = before the first named period (uncovered).
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1", "2", "2", "3"],
            "lateness_minutes": [1.0, -0.5, 2.0, 3.0, 11.0],
            "dep_time_min": [410.0, 415.0, 700.0, 1300.0, 300.0],
        }
    )
    cov = lateness_coverage(df)
    assert cov["total"] == 5
    assert cov["uncovered"] == 1
    assert cov["periods"]["am_rush"]["observed"] == 2
    assert cov["periods"]["am_rush"]["mean_min"] == pytest.approx(0.25)
    assert cov["periods"]["midday"]["observed"] == 1
    assert cov["periods"]["late_night"]["observed"] == 1
    assert cov["periods"]["pm_rush"]["observed"] == 0
    assert cov["periods"]["pm_rush"]["mean_min"] is None


def test_lateness_coverage_all_rows_uncovered_without_dep_time():
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "2"],
            "lateness_minutes": [1.0, -0.5],
        }
    )
    cov = lateness_coverage(df)
    assert cov["total"] == 2
    assert cov["uncovered"] == 2
    assert all(c["observed"] == 0 for c in cov["periods"].values())


def test_lateness_coverage_late_night_crosses_midnight():
    """After-midnight minutes (00:00-02:00) belong to late_night, matching
    config.period_for_epoch's midnight wrap -- not 'uncovered'."""
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "1", "1", "2"],
            "lateness_minutes": [1.0, 2.0, 3.0, 4.0],
            "dep_time_min": [1200.0, 30.0, 90.0, 300.0],
        }
    )
    cov = lateness_coverage(df)
    assert cov["periods"]["late_night"]["observed"] == 3
    assert cov["uncovered"] == 1  # 300 (05:00) is outside every window
    assert cov["periods"]["late_night"]["mean_min"] == pytest.approx(2.0)


def test_lateness_coverage_treats_bad_dep_times_as_uncovered():
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "2"],
            "lateness_minutes": [1.0, -0.5],
            "dep_time_min": [410.0, None],
        }
    )
    cov = lateness_coverage(df)
    assert cov["periods"]["am_rush"]["observed"] == 1
    assert cov["uncovered"] == 1


def test_sample_connection_lateness_bootstraps_observed_values_only():
    """Bootstrap draws must come from the observed pools, not outside them."""
    by_route = {
        "1": np.array([-1.0, 0.0, 1.0]),
        "2": np.array([10.0, 11.0, 12.0]),
    }
    routes_i = np.array(["1", "2"], dtype=object)
    routes_j = np.array(["2", "1"], dtype=object)
    rng = np.random.default_rng(42)
    draws = sample_connection_lateness(
        routes_i, routes_j, by_route, n_days=2000, rng=rng
    )

    assert draws.shape == (2000, 2)
    # Connection 0: diff = lateness(route 2) - lateness(route 1) in [9, 13].
    col0 = draws[:, 0]
    assert col0.min() >= 9.0 - 1e-9
    assert col0.max() <= 13.0 + 1e-9
    # Connection 1: diff = lateness(route 1) - lateness(route 2) in [-13, -9].
    col1 = draws[:, 1]
    assert col1.min() >= -13.0 - 1e-9
    assert col1.max() <= -9.0 + 1e-9


def test_sample_connection_lateness_falls_back_to_laplace():
    """Routes with no observations fall back to the parametric Laplace model.

    Connection 0 is fully unobserved on both sides (pure Laplace, zero-mean,
    symmetric); connection 1 has one observed side and one Laplace side.
    """
    by_route = {"1": np.array([0.0, 1.0, -1.0])}
    routes_i = np.array(["98", "1"], dtype=object)
    routes_j = np.array(["99", "99"], dtype=object)
    rng = np.random.default_rng(7)
    draws = sample_connection_lateness(
        routes_i, routes_j, by_route, n_days=5000, rng=rng
    )

    assert draws.shape == (5000, 2)
    assert np.isfinite(draws).all()
    # Connection 0: Laplace(mu=1) - Laplace(mu=1) -> zero-mean, spread > 0.
    assert abs(draws[:, 0].mean()) < 0.15
    assert draws[:, 0].std() > 0.5
    # Connection 1: pool(route 1) - Laplace(mu=1) -> also zero-mean, spread > 0.
    assert abs(draws[:, 1].mean()) < 0.15
    assert draws[:, 1].std() > 0.5


def test_sample_connection_lateness_is_deterministic_with_seed():
    by_route = {"1": np.array([0.0, 1.0, -1.0, 2.0])}
    routes_i = np.array(["1", "1"], dtype=object)
    routes_j = np.array(["1", "1"], dtype=object)
    a = sample_connection_lateness(
        routes_i, routes_j, by_route, 50, np.random.default_rng(3)
    )
    b = sample_connection_lateness(
        routes_i, routes_j, by_route, 50, np.random.default_rng(3)
    )
    np.testing.assert_array_equal(a, b)
