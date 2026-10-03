"""Tests for scripts/telemetry_health_check.py (standing telemetry detector)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import telemetry_health_check as thc


def _cand(jump_gap_s: float, jump_km: float) -> dict:
    return {"jump_gap_s": jump_gap_s, "jump_km": jump_km}


class TestClassify:
    """Ordering: garage and terminal exclusions fire BEFORE failure classes."""

    def test_confirmed_off_corridor(self):
        # 2454 class: tight gap, impossible speed, >1 km off corridor
        c = _cand(30.0, 3.79)
        assert (
            thc.classify(
                c,
                corr_m=11233.7,
                nearest_m=1200.0,
                nearest_name="Eglinton Ave At 9th Line",
                garage_m=8053.0,
            )
            == "confirmed-off-corridor"
        )

    def test_confirmed_impossible_jump_near_corridor(self):
        # impossible speed but pin lands near the corridor (<1 km): still a
        # failure, just not the off-corridor-pin sub-class
        c = _cand(32.0, 3.54)
        assert (
            thc.classify(
                c,
                corr_m=340.0,
                nearest_m=130.0,
                nearest_name="Some St At Some Rd",
                garage_m=7086.0,
            )
            == "confirmed-impossible-jump"
        )

    def test_garage_pullin_excluded_even_if_off_corridor(self):
        # 2625/2662 class: within 500 m of a garage stop => pull-in, NOT failure
        c = _cand(3292.0, 4.51)
        assert (
            thc.classify(
                c,
                corr_m=4730.7,
                nearest_m=280.7,
                nearest_name="Derry Rd At Professional Crt",
                garage_m=446.1,
            )
            == "garage-pullin"
        )

    def test_terminal_layover_excluded(self):
        # 4317 class: near a terminal-named stop => layover
        c = _cand(880.0, 3.80)
        assert (
            thc.classify(
                c,
                corr_m=6.4,
                nearest_m=9.4,
                nearest_name="City Centre Transit Terminal Platform E",
                garage_m=2727.0,
            )
            == "terminal-layover"
        )

    def test_garage_beats_terminal(self):
        # A legal-speed reappearance near a garage stop is a pull-in
        c = _cand(3292.0, 4.51)
        assert (
            thc.classify(
                c,
                corr_m=4000.0,
                nearest_m=20.0,
                nearest_name="Malton Division Garage",
                garage_m=18.0,
            )
            == "garage-pullin"
        )

    def test_impossible_speed_at_terminal_is_still_confirmed(self):
        # 2454's 534 km/h teleport landed 170 m from a terminal stop - a
        # bus cannot TELEPORT into a terminal; impossible speed wins over
        # the layover exclusion (regression for the classify-order bug)
        c = _cand(31.0, 4.60)
        assert (
            thc.classify(
                c,
                corr_m=1200.0,
                nearest_m=170.5,
                nearest_name="Some Terminal Platform A",
                garage_m=8000.0,
            )
            == "confirmed-off-corridor"
        )

    def test_impossible_speed_at_garage_is_still_confirmed(self):
        # same rule for a garage pin: a teleport INTO the yard is a failure
        c = _cand(30.0, 4.60)
        assert (
            thc.classify(
                c,
                corr_m=2000.0,
                nearest_m=20.0,
                nearest_name="Malton Division Garage",
                garage_m=18.0,
            )
            == "confirmed-off-corridor"
        )

    def test_coverage_gap_reappearance(self):
        # long gap, legal implied speed, on-corridor => NOT a failure
        c = _cand(5374.0, 9.21)
        assert (
            thc.classify(
                c,
                corr_m=13.9,
                nearest_m=12.5,
                nearest_name="Laird Rd West Of Ridgeway Dr",
                garage_m=6238.0,
            )
            == "coverage-gap-reappearance"
        )

    def test_long_gap_impossible_speed_is_still_coverage(self):
        # even a big jump at a long gap is legal movement (the gap hides speed)
        c = _cand(14873.0, 10.40)
        assert (
            thc.classify(
                c,
                corr_m=4.4,
                nearest_m=53.7,
                nearest_name="Some St At Some Rd",
                garage_m=7409.0,
            )
            == "coverage-gap-reappearance"
        )

    def test_terminal_layover_beats_long_gap(self):
        # 2118 case: pin at Dixie Station is a layover, not a reappearance
        c = _cand(14873.0, 10.40)
        assert (
            thc.classify(
                c,
                corr_m=4.4,
                nearest_m=53.7,
                nearest_name="Dixie Station East Platform A",
                garage_m=7409.0,
            )
            == "terminal-layover"
        )


class TestCoverageGaps:
    def test_max_gap_across_windows(self):
        windows = [
            (
                "w1",
                [
                    {"vehicle_id": "a", "fetched_at": 100.0},
                    {"vehicle_id": "a", "fetched_at": 130.0},
                ],
            ),
            (
                "w2",
                [
                    {"vehicle_id": "a", "fetched_at": 500.0},
                    {"vehicle_id": "a", "fetched_at": 520.0},
                ],
            ),
        ]
        gaps = {r["vehicle_id"]: r for r in thc.coverage_gaps(windows)}
        assert gaps["a"]["max_gap_s"] == 370.0  # 130 -> 500
        assert gaps["a"]["n_polls"] == 4

    def test_single_poll_vehicle_zero_gap(self):
        windows = [("w1", [{"vehicle_id": "b", "fetched_at": 100.0}])]
        gaps = thc.coverage_gaps(windows)
        assert gaps[0]["max_gap_s"] == 0.0
        assert gaps[0]["n_polls"] == 1

    def test_no_vehicles(self):
        assert thc.coverage_gaps([]) == []


class TestTightGapJumps:
    """Vendor-ts-aware gap handling (T44-DETECTOR-REATTACK fix)."""

    def _obs(self, fetched_at, ts, lat, lon):
        return {
            "fetched_at": float(fetched_at),
            "ts": float(ts) if ts is not None else None,
            "lat": lat,
            "lon": lon,
            "trip_id": "t1",
            "vehicle_id": "v1",
        }

    def test_stale_rebroadcast_not_confirmed(self):
        # alpha-6 finding 1: a pin frozen for ~15 min then a legal move reads
        # as a "30 s jump" under fetched_at. The vendor ts gap (753-1728 s)
        # is the discriminator: long ts gap => coverage hole, NOT a teleport.
        # Pins ~4 km apart (impossible at 30 s) but 900 s apart in vendor ts.
        a = self._obs(100.0, 100.0, 43.50, -79.60)
        b = self._obs(130.0, 1000.0, 43.54, -79.65)  # 4.8 km away, fetched 30 s later
        assert thc.find_tight_gap_jumps([a, b]) == []

    def test_fresh_ts_teleport_confirmed(self):
        # 4430 class: vendor ts gap is genuinely small (28-37 s) -> real teleport
        a = self._obs(100.0, 100.0, 43.50, -79.60)
        b = self._obs(130.0, 128.0, 43.54, -79.65)
        jumps = thc.find_tight_gap_jumps([a, b])
        assert len(jumps) == 1
        assert jumps[0]["vehicle_id"] == "v1"

    def test_fetched_at_fallback_when_ts_missing(self):
        # legacy records without vendor ts fall back to fetched_at
        a = self._obs(100.0, None, 43.50, -79.60)
        b = self._obs(130.0, None, 43.54, -79.65)
        assert len(thc.find_tight_gap_jumps([a, b])) == 1


class TestNearestStop:
    def test_returns_distance_id_name(self):
        stops = pd.DataFrame(
            {
                "stop_id": ["s1", "s2"],
                "stop_lat": [43.70, 43.71],
                "stop_lon": [-79.63, -79.63],
                "stop_name": ["Near", "Far"],
            }
        )
        d, sid, name = thc.nearest_stop(43.7005, -79.63, stops)
        assert sid == "s1"
        assert name == "Near"
        assert d < 100.0
