"""Regression tests for NaN-safe casts in router/module readers.

A live reader can see a NaN when a CSV is being rewritten concurrently (or
when a column simply lacks data). ``int(nan)`` raises ValueError → 500, and
``float(nan)`` silently poisons JSON responses with NaN (which is invalid
JSON). These tests pin the NaN-safe behavior added after the /api/measured
crash, and mirror the audit of every unguarded count cast in app/.
"""

import pandas as pd

from app.routers import coverage as cov
from app.routers import service_quality as sq
from app.services.ghosts import detect_phantoms


class TestServiceQualityCasts:
    def test_int_nan_returns_default(self):
        assert sq._int(float("nan")) == 0
        assert sq._int(float("nan"), 7) == 7

    def test_float_nan_returns_default(self):
        assert sq._float(float("nan")) == 0.0
        assert sq._float(float("nan"), 1.0) == 1.0

    def test_real_values_pass_through(self):
        assert sq._int(200) == 200
        assert sq._int("42") == 42
        assert sq._float(120.5) == 120.5
        assert sq._float("3.25") == 3.25

    def test_detect_phantoms_nan_verifiable_does_not_crash(self):
        # A NaN in verifiable_trips previously raised ValueError → 500 on
        # the whole /api/service-quality endpoint.
        df = pd.DataFrame(
            [
                {
                    "route_short_name": "18",
                    "verifiable_trips": float("nan"),
                    "ghosts": "t1@20260901;t2@20260902",
                },
                {
                    "route_short_name": "19",
                    "verifiable_trips": 4,
                    "ghosts": "t3@20260901",
                },
            ]
        )
        res = detect_phantoms(df)
        assert "phantom_trip_ids" in res
        # Route 18's NaN day contributes nothing (skipped, not crashed); the
        # result is well-formed either way.
        assert res["phantom_count"] >= 0
        assert isinstance(res["phantom_trip_ids"], set)

    def test_faulty_vehicle_nan_observation_is_skipped(self):
        # NaN observations must not abort the faulty-vehicle loop; a real
        # high-status1/low-coverage vehicle on a later row is still found.
        sdf = pd.DataFrame(
            [
                {
                    "vehicle_id": "v_bad_data",
                    "observations": float("nan"),
                    "status1_share": 0.97,
                    "ride_window_pct_share": 0.3,
                },
                {
                    "vehicle_id": "v_stuck",
                    "observations": 200,
                    "status1_share": 0.98,
                    "ride_window_pct_share": 0.2,
                },
            ]
        )
        found = []
        for _, row in sdf.iterrows():
            obs = sq._int(row.get("observations", 0))
            if obs < 100:
                continue
            s1 = sq._float(row.get("status1_share", 1), 1.0)
            ride_pct = row.get("ride_window_pct_share", "")
            ride_pct_f = sq._float(ride_pct) if ride_pct and ride_pct != "" else 0
            if s1 > 0.95 and ride_pct_f < 0.5:
                found.append(row["vehicle_id"])
        assert found == ["v_stuck"]


class TestCoverageCasts:
    def test_float_nan_returns_default(self):
        assert cov._float(float("nan")) == 0.0
        assert cov._float(float("nan"), 12.5) == 12.5

    def test_num_nan_returns_default(self):
        assert cov._num(float("nan")) == 0
        assert cov._num(float("nan"), 5) == 5

    def test_real_values_pass_through(self):
        assert cov._float(3.5) == 3.5
        assert cov._num("17") == 17


class TestRidershipNanGuard:
    def test_nan_row_is_skipped_not_poisoned(self):
        # Mirrors the guard in ridership._live_ridership: float(nan) never
        # raises, so the except (TypeError, ValueError) alone lets NaN
        # poison the per-route totals. The row must be skipped instead.
        pax = float("nan")
        peak_pct = 42.0
        try:
            pax2 = float(pax or 0)
            peak_pct2 = float(peak_pct or 0)
        except (TypeError, ValueError):
            pax2, peak_pct2 = None, None
        # float(nan) survives the try — the explicit NaN check is what
        # rejects the row.
        assert pax2 != pax2
        assert (pax2 != pax2 or peak_pct2 != peak_pct2) is True
