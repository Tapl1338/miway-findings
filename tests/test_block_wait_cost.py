"""Unit tests for ``scripts/block_wait_cost.py`` (D-16 wait-cost, gate-tested).

Pure helpers only: OBSERVED-RAN index construction, per-departure wait math,
the NO-LATER-SERVICE coverage guard, and the three alpha-6 falsifier gates
(2026-08-26T21:52Z). No network.
"""

import pandas as pd
import pytest
from scripts.block_wait_cost import (
    build_stop_index,
    compute_wait_cost,
    next_ran_wait,
    trip_stops,
)
from scripts.ghost_recovery_check import build_episodes


def _stops(rows):
    """[(trip_id, stop_id, dep 'HH:MM:SS', pickup)] -> stop_times frame."""
    return pd.DataFrame(
        rows,
        columns=[
            "trip_id",
            "stop_id",
            "departure_time",
            "pickup_type",
            "stop_sequence",
        ],
    )


def _verdicts(trips):
    """[(trip_id, verdict, start_min, dur, block, route)] -> verdicts dict."""
    return {
        tid: (verdict, start, dur, block, route)
        for tid, verdict, start, dur, block, route in trips
    }


def test_gate1_scheduled_ghosted_trip_never_counts_as_next_bus():
    # The next SCHEDULED trip at the stop also ghosted -> wait must skip it
    # and land on the following OBSERVED trip (alpha-6 gate 1).
    st = _stops(
        [
            ("G1", "S1", "12:48:00", "0", 1),
            ("G2", "S1", "13:30:00", "0", 1),  # scheduled but ghosted
            ("R1", "S1", "14:10:00", "0", 1),  # actually ran
        ]
    )
    index = build_stop_index(
        ran_trips={"R1"},  # G2 did NOT run
        stop_times=st,
        route_of={"G1": "66", "G2": "66", "R1": "66"},
    )
    wait = next_ran_wait(index, "66", "S1", 12 * 60 + 48)
    assert wait is not None
    assert wait[1] == "R1"  # next bus is R1, NOT G2
    assert wait[0] == pytest.approx((14 * 60 + 10) - (12 * 60 + 48), abs=0.01)


def test_gate2_per_departure_anchor():
    # Each ghosted departure gets its OWN wait (origin-anchored), and a
    # fully-dead run of ghosts spans multiple headways (alpha-6 gate 2).
    st = _stops(
        [
            ("G1", "S1", "12:48:00", "0", 1),
            ("G2", "S1", "13:30:00", "0", 1),
            ("R1", "S1", "14:10:00", "0", 1),
        ]
    )
    index = build_stop_index({"R1"}, st, {"G1": "66", "G2": "66", "R1": "66"})
    w1 = next_ran_wait(index, "66", "S1", 12 * 60 + 48)
    w2 = next_ran_wait(index, "66", "S1", 13 * 60 + 30)
    assert w1[0] == pytest.approx(82, abs=0.01)  # 12:48 -> 14:10
    assert w2[0] == pytest.approx(40, abs=0.01)  # 13:30 -> 14:10


def test_nolater_service_guard_excluded_from_totals():
    # Last trip of the day ghosts with no later ran trip -> NO-LATER-SERVICE,
    # never a fabricated wait (coverage guard).
    st = _stops([("G1", "S1", "23:36:00", "0", 1)])
    index = build_stop_index(set(), st, {"G1": "66"})
    assert next_ran_wait(index, "66", "S1", 23 * 60 + 36) is None


def test_wait_ignores_other_routes():
    # Next bus on a DIFFERENT route at the same stop is not a candidate.
    st = _stops([("G1", "S1", "12:48:00", "0", 1), ("R9", "S1", "12:50:00", "0", 1)])
    index = build_stop_index({"R9"}, st, {"G1": "66", "R9": "9"})
    assert next_ran_wait(index, "66", "S1", 12 * 60 + 48) is None


def test_trip_stops_filters_no_pickup():
    st = _stops(
        [
            ("G1", "S1", "12:48:00", "0", 1),
            ("G1", "S2", "12:50:00", "1", 2),  # no pickup -> not boarding
            ("G1", "S3", "12:52:00", "0", 3),
        ]
    )
    stops = trip_stops(st, "G1")
    assert [s["stop_id"] for s in stops] == ["S1", "S3"]


def test_compute_wait_cost_episode_totals():
    # End-to-end: a RECOVERED episode (ghost -> next ran) accumulates the
    # origin wait into the episode total; NO-LATER is counted separately.
    verdicts = _verdicts(
        [
            ("G1", "ghost", 12 * 60 + 48, 55, "B66", "66"),
            ("G2", "ghost", 13 * 60 + 30, 55, "B66", "66"),
            ("R1", "observed", 14 * 60 + 10, 55, "B66", "66"),
            ("G3", "ghost", 23 * 60 + 36, 30, "B66", "66"),
        ]
    )
    # G1/G2 ghost consecutively; R1 observed breaks the run; G3 alone.
    episodes = build_episodes(verdicts)
    assert len(episodes) == 2

    st = _stops(
        [
            ("G1", "S1", "12:48:00", "0", 1),
            ("G2", "S1", "13:30:00", "0", 1),
            ("R1", "S1", "14:10:00", "0", 1),
            ("G3", "S1", "23:36:00", "0", 1),
        ]
    )
    route_of = {"G1": "66", "G2": "66", "R1": "66", "G3": "66"}
    compute_wait_cost(episodes, verdicts, st, route_of)

    ep1 = episodes[0]  # G1/G2
    assert ep1["wait_covered"] == 2
    assert ep1["wait_nolater"] == 0
    assert ep1["wait_min_total"] == pytest.approx(82 + 40, abs=0.01)

    ep2 = episodes[1]  # G3 alone, last of day
    assert ep2["wait_covered"] == 0
    assert ep2["wait_nolater"] == 1
    assert ep2["wait_min_total"] == 0.0
