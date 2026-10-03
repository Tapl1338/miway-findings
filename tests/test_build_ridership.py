"""Tests for ``scripts/build_ridership_dataset.py`` (measured-uplift estimates)."""

import pandas as pd
from scripts.build_ridership_dataset import (
    ESTIMATED_PRODUCTIVITY_PER_HOUR,
    build_dataset,
    compute_per_route_capture_ratios,
    compute_route_service_hours,
    load_measured_bounds,
)


def _trips():
    return pd.DataFrame(
        {
            "trip_id": ["t1", "t2", "t3"],
            "route_short_name": ["1", "1", "2"],
        }
    )


def _stop_times():
    # t1: 06:00 -> 08:00 (2 h), t2: 08:10 -> 09:40 (1.5 h), t3: 07:00 -> 08:30 (1.5 h)
    # Endpoint stops carry equal arrival/departure (no dwell at terminals).
    return pd.DataFrame(
        {
            "trip_id": ["t1", "t1", "t2", "t2", "t3", "t3"],
            "dep_min": [360.0, 480.0, 490.0, 580.0, 420.0, 510.0],
            "arr_min": [360.0, 480.0, 490.0, 580.0, 420.0, 510.0],
        }
    )


def test_compute_route_service_hours():
    hours = compute_route_service_hours(_trips(), _stop_times())
    assert abs(hours["1"] - 3.5) < 1e-9  # 2.0 + 1.5
    assert abs(hours["2"] - 1.5) < 1e-9


def test_build_dataset_merges_published_and_fallback_estimates():
    hours = pd.Series({"1": 100.0, "2": 50.0})
    published = {"1": 5000.0}
    df = build_dataset(hours, published=published, productivity=7.0)

    assert set(df["route_short_name"]) == {"1", "2"}
    row1 = df[df["route_short_name"] == "1"].iloc[0]
    row2 = df[df["route_short_name"] == "2"].iloc[0]

    assert row1["boardings"] == 5000.0
    assert not row1["is_estimate"]
    assert row1["estimate_method"] == "published"
    assert "APC" in row1["source"]

    # No measured data at all -> conservative service-hours fallback.
    assert row2["boardings"] == 50.0 * 7.0
    assert bool(row2["is_estimate"])
    assert row2["estimate_method"] == "hours-fallback"
    assert "estimate" in row2["source"]


def test_estimate_productivity_is_conservative():
    """The fallback productivity must sit at/below the published set's floor
    (the published ten are the highest-demand routes by definition)."""
    # The published calibration set spans 6.9-14.1 boardings/hour; the
    # constant used for the rest must be <= the observed floor.
    assert ESTIMATED_PRODUCTIVITY_PER_HOUR <= 7.0


def test_compute_capture_ratio_is_calibrated_on_published():
    measured = {"1": 1000.0, "2": 500.0}
    published = {"1": 5000.0, "2": 2500.0}
    chars = pd.DataFrame(
        {
            "n_stops": [10, 10],
            "span_hours": [2.0, 2.0],
            "headway_min": [15.0, 15.0],
            "is_express": [0, 0],
        },
        index=["1", "2"],
    )
    ratios = compute_per_route_capture_ratios(measured, published, chars)
    # 1000/5000 = 0.2, 500/2500 = 0.2; global mean = 0.2
    assert abs(ratios["_global"] - 0.2) < 1e-9
    assert abs(ratios["1"] - 0.2) < 1e-9
    assert abs(ratios["2"] - 0.2) < 1e-9


def test_measured_uplift_scales_observed_routes_from_their_floor():
    hours = pd.Series({"1": 100.0, "2": 50.0})
    published = {"1": 5000.0}
    measured = {"1": 100.0, "2": 800.0}  # capture = 100/5000 = 0.02
    chars = pd.DataFrame(
        {
            "n_stops": [10],
            "span_hours": [2.0],
            "headway_min": [15.0],
            "is_express": [0],
        },
        index=["1"],
    )
    capture_ratios = compute_per_route_capture_ratios(measured, published, chars)
    df = build_dataset(
        hours,
        published=published,
        productivity=7.0,
        measured_bounds=measured,
        capture_ratios=capture_ratios,
    )

    row1 = df[df["route_short_name"] == "1"].iloc[0]
    row2 = df[df["route_short_name"] == "2"].iloc[0]

    # Published route keeps its published figure, floor recorded alongside.
    assert row1["boardings"] == 5000.0
    assert not bool(row1["is_estimate"])
    assert row1["measured_lower_bound"] == 100.0

    # Observed route is estimated from its real floor, scaled by the capture.
    assert row2["boardings"] == 800.0 / 0.02
    assert bool(row2["is_estimate"])
    assert row2["estimate_method"] == "measured-uplift"
    assert row2["measured_lower_bound"] == 800.0
    assert row2["boardings"] >= row2["measured_lower_bound"]


def test_unobserved_route_falls_back_to_service_hours():
    hours = pd.Series({"1": 100.0, "2": 50.0})
    published = {"1": 5000.0}
    measured = {"1": 100.0}  # route 2 never observed by the collector
    df = build_dataset(
        hours, published=published, productivity=7.0, measured_bounds=measured
    )

    row2 = df[df["route_short_name"] == "2"].iloc[0]
    assert row2["boardings"] == 50.0 * 7.0
    assert row2["estimate_method"] == "hours-fallback"
    assert row2["measured_lower_bound"] == 0.0


def test_capture_ratio_defaults_to_one_without_calibration():
    """No published route with a measured floor -> floor used as-is."""
    hours = pd.Series({"99": 50.0})
    measured = {"99": 100.0}
    df = build_dataset(hours, measured_bounds=measured, capture_ratios={"_global": 1.0})
    row = df[df["route_short_name"] == "99"].iloc[0]
    assert row["boardings"] == 100.0
    assert row["estimate_method"] == "measured-uplift"
    assert row["measured_lower_bound"] == 100.0


def test_load_measured_bounds_sums_periods_and_tolerates_missing_file(tmp_path):
    import pandas as pd

    csv = tmp_path / "boardings_routes.csv"
    pd.DataFrame(
        {
            "route_short_name": ["2", "2", "10"],
            "period": ["am_rush", "pm_rush", "pm_rush"],
            "boardings_lower_pax": [600.0, 800.0, 100.0],
        }
    ).to_csv(csv, index=False)
    bounds = load_measured_bounds(csv)
    assert bounds == {"2": 1400.0, "10": 100.0}

    assert load_measured_bounds(tmp_path / "missing.csv") == {}


def test_load_measured_bounds_normalizes_to_per_weekday(tmp_path):
    """Multi-day totals must be divided by observed days so the floor is a
    per-weekday figure, matching the unit of published APC boardings."""
    import pandas as pd

    csv = tmp_path / "boardings_routes.csv"
    pd.DataFrame(
        {
            "route_short_name": ["2", "2", "10"],
            "period": ["am_rush", "pm_rush", "pm_rush"],
            "boardings_lower_pax": [600.0, 800.0, 100.0],
            "n_days_with_data": [9, 9, 9],
        }
    ).to_csv(csv, index=False)
    bounds = load_measured_bounds(csv)
    assert abs(bounds["2"] - 1400.0 / 9) < 1e-9
    assert abs(bounds["10"] - 100.0 / 9) < 1e-9
