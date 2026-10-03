"""Unit tests for ``aggregate_occupancy._calibrate_frame``.

Checks the raw (pct*capacity) vs calibrated (ground-truth bucket) pax
columns, per-vehicle override, and the uncalibrated fallback (NaN when the
registry has no bucket for a reading).
"""

import json

import pandas as pd
from scripts import aggregate_occupancy


def _cal(tmp_path, registry):
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    from app import calibration

    calibration.CALIBRATION_PATH = path
    # Bump the mtime-keyed cache so the fresh file is read.
    calibration._load_state["key"] = None


def _frame(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "route_short_name",
            "period",
            "occupancy_status",
            "occupancy_percentage",
            "vehicle_id",
            "crowded",
        ],
    )


def test_calibrate_frame_standard_bucket(tmp_path):
    _cal(
        tmp_path,
        {
            "standard": {"20": {"n": 1, "pax_lo": 0, "pax_hi": 17, "mid": 8.5}},
            "articulated": {"20": {"n": 1, "pax_lo": 0, "pax_hi": 28, "mid": 14.0}},
        },
    )
    df = _calibrate(_frame([["10", "pm_rush", 1, 20.0, 2302, False]]))
    # raw = 20% of 65 = 13; calibrated = standard 20-bucket mid 8.5.
    assert df.iloc[0]["pax_raw"] == 13.0
    assert df.iloc[0]["pax_cal"] == 8.5


def test_calibrate_frame_per_vehicle_override(tmp_path):
    _cal(
        tmp_path,
        {
            "standard": {"20": {"mid": 8.5}},
            "per_vehicle": {"2302": {"20": {"pax_lo": 2, "pax_hi": 16, "mid": 9.0}}},
        },
    )
    df = _calibrate(_frame([["10", "am_rush", 1, 20.0, 2302, False]]))
    assert df.iloc[0]["pax_cal"] == 9.0


def test_calibrate_frame_articulated_capacity(tmp_path):
    _cal(tmp_path, {"articulated": {"20": {"mid": 18.1}}})
    df = _calibrate(_frame([["42", "am_rush", 1, 20.0, 2459, False]]))
    # raw uses the articulated capacity (110) => 20% * 110 = 22.
    assert df.iloc[0]["pax_raw"] == 22.0
    assert df.iloc[0]["pax_cal"] == 18.1


def test_calibrate_frame_uncalibrated_bucket_is_nan(tmp_path):
    _cal(tmp_path, {"standard": {"20": {"mid": 8.5}}})
    df = _calibrate(_frame([["57", "pm_rush", 3, 60.0, 4455, True]]))
    # No 60-bucket in the registry: calibrated stays NaN, raw still computed.
    assert pd.isna(df.iloc[0]["pax_cal"])
    assert df.iloc[0]["pax_raw"] == pytest_approx(60.0 / 100 * 65)


def test_calibrate_frame_empty(tmp_path):
    _cal(tmp_path, {})
    out = aggregate_occupancy._calibrate_frame(pd.DataFrame())
    assert out.empty


def _calibrate(df):
    return aggregate_occupancy._calibrate_frame(df)


def test_bucket_key_maps_band_midpoints_into_their_band():
    """20-point bucket keys must be stable for both raw band upper bounds
    (20/40/60...) and the band midpoints (10/30/50...) reconstruction feeds in.
    A naive ``round()`` (banker's rounding) maps 50->40, 90->80, 10->0 and
    flattens load deltas; ``ceil`` keeps every value in (k-20, k] in bucket k.
    """
    from app import calibration

    expect = {
        10: "20",
        20: "20",
        30: "40",
        40: "40",
        50: "60",
        60: "60",
        70: "80",
        80: "80",
        90: "100",
        100: "100",
        110: "120",
        120: "120",
    }
    for pct, key in expect.items():
        assert calibration._bucket_key(float(pct)) == key, f"pct={pct}"


def test_bucket_key_is_bankers_rounding_safe():
    """The midpoints (10/30/50/70) that `round()` misround must not collapse
    into the wrong or a missing bucket (the root cause of zero boardings on
    articulated routes 42/109)."""
    from app import calibration

    assert calibration._bucket_key(50) == "60"  # not 40
    assert calibration._bucket_key(90) == "100"  # not 80
    assert calibration._bucket_key(10) == "20"  # not 0


def pytest_approx(v):
    import pytest

    return pytest.approx(v, rel=1e-3)
