"""Unit tests for the ground-truth calibration registry builder.

Exercises ``build_registry`` (pure) against tmp frames: per-vehicle and
per-route bias/trust, bucket ranges from counted pax, bus-type pooling, the
bucket map and floor threshold, and the missing-column guard.
"""

import pandas as pd
import pytest
from scripts.ground_truth_calibration import build_registry

ROUTES = {"42": "articulated", "109": "articulated"}  # everything else standard


def _frame(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "ts",
            "vehicle_id",
            "trip_id",
            "route",
            "reported_pct",
            "counted_pax",
            "model_pax_at_65",
        ],
    )


def test_missing_columns_raise():
    with pytest.raises(ValueError, match="missing column"):
        build_registry(
            pd.DataFrame({"ts": [], "vehicle_id": []}), route_bus_type=ROUTES
        )


def test_floor_threshold_and_bucket_map():
    df = _frame(
        [
            ["t", 1, "A", 42, 20.0, 12, 13.0],
            ["t", 1, "A", 42, 20.0, 15, 13.0],
            ["t", 1, "A", 42, 40.0, 28, 26.0],
            ["t", 2, "B", 10, 20.0, 5, 13.0],
            ["t", 2, "B", 10, 60.0, 30, 39.0],
        ]
    )
    reg = build_registry(df, route_bus_type=ROUTES)
    assert reg["floor_threshold_pct"] == 20
    assert reg["pct_buckets"] == {"20": 3, "40": 1, "60": 1}


def test_per_vehicle_bias_trust_and_buckets():
    # Route 42 vehicle: counted consistently ~9 pax above the 65-model.
    rows = [["t", 2459, "A", 42, 20.0, 22, 13.0] for _ in range(20)]
    df = _frame(rows)
    reg = build_registry(df, route_bus_type=ROUTES)
    v = reg["per_vehicle"]["2459"]
    assert v["n"] == 20
    assert v["bias_pax"] == pytest.approx(9.0)
    assert v["trust"] == "biased"
    assert v["routes"] == ["42"]
    assert v["buckets"]["20"] == {
        "n": 20,
        "pax_lo": 22.0,
        "pax_hi": 22.0,
        "mid": 22.0,
    }


def test_per_route_aggregates_vehicles_and_validated_trust():
    # Two standard vehicles, sensor accurate to ±1 pax -> validated.
    rows = []
    for vid, counted in ((100, 13), (101, 12)):
        rows += [["t", vid, f"T{vid}", 57, 20.0, counted, 13.0] for _ in range(10)]
    reg = build_registry(_frame(rows), route_bus_type=ROUTES)
    r = reg["per_route"]["57"]
    assert r["n"] == 20
    assert r["vehicles"] == 2
    assert r["trust"] == "validated"
    assert abs(r["bias_pax"]) <= 1.0


def test_bus_type_buckets_pool_across_routes():
    df = _frame(
        [
            ["t", 1, "A", 3, 20.0, 8, 13.0],  # standard
            ["t", 2, "B", 10, 20.0, 12, 13.0],  # standard
            ["t", 3, "C", 42, 20.0, 25, 13.0],  # articulated
            ["t", 4, "D", 109, 20.0, 22, 13.0],  # articulated
        ]
    )
    reg = build_registry(df, route_bus_type=ROUTES)
    assert reg["standard"]["20"]["n"] == 2
    assert reg["standard"]["20"]["mid"] == pytest.approx(10.0)
    assert reg["articulated"]["20"]["n"] == 2
    assert reg["articulated"]["20"]["mid"] == pytest.approx(23.5)


def test_small_n_trust_insufficient():
    df = _frame([["t", 1, "A", 23, 40.0, 12, 26.0] for _ in range(5)])
    reg = build_registry(df, route_bus_type=ROUTES)
    assert reg["per_route"]["23"]["trust"] == "insufficient"


def test_missing_model_column_falls_back_to_65_conversion():
    df = pd.DataFrame(
        [
            ["t", 1, "A", 10, 20.0, 10],
        ],
        columns=["ts", "vehicle_id", "trip_id", "route", "reported_pct", "counted_pax"],
    )
    reg = build_registry(df, route_bus_type=ROUTES)
    # No model_pax_at_65 column: sensor pax falls back to 20% of 65 = 13.
    assert reg["per_route"]["10"]["bias_pax"] == pytest.approx(10 - 13)
    assert reg["per_route"]["10"]["trust"] == "insufficient"
