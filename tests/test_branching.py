"""Tests for ``app.branching`` — the T157 trip-alternation engine.

Covers pattern edits (skip spans, extension interpolation), span
measurement, the alternation planner's fleet-neutral shares, trunk-headway
verification, and rider-impact classification, all on synthetic trips — no
feed dependence.
"""

from __future__ import annotations

import pytest

from app.branching import (
    BranchVariant,
    Extension,
    SkipSpan,
    apply_variant,
    assign_round_robin,
    cycle_compatibility,
    interleave_check,
    measure_span_savings,
    plan_alternation,
    rider_impact,
    summarize_impact,
    trip_runtime,
    trunk_headway_check,
)


def _trip(dep: int, names: list[str], runtime: int, dir_: str = "0") -> list[dict]:
    """A synthetic trip departing at ``dep`` through ``names`` in ``runtime``."""
    step = runtime / (len(names) - 1)
    return [
        {
            "seq": i,
            "name": n,
            "arr": round(dep + i * step),
            "dep": round(dep + i * step),
            "dir": dir_,
        }
        for i, n in enumerate(names)
    ]


BASE_NAMES = ["A", "B", "C", "D", "E"]  # C..E is the "loop"


# --------------------------------------------------------------------------
# apply_variant


def test_skip_span_drops_intermediate_stops():
    trip = _trip(480, BASE_NAMES, 60)
    v = BranchVariant(name="s", skip_spans=(SkipSpan("B", "E", 15.0),))
    new, dropped = apply_variant(trip, v)
    assert [r["name"] for r in new] == ["A", "B", "E"]
    assert dropped == ["C", "D"]


def test_extension_appends_interpolated_times():
    trip = _trip(480, ["A", "B"], 30)
    v = BranchVariant(
        name="e",
        extension=Extension(
            from_stop="B", new_terminal="X", minutes=10, via_stops=("M",)
        ),
    )
    new, _dropped = apply_variant(trip, v)
    assert [r["name"] for r in new] == ["A", "B", "M", "X"]
    # 10 min over two legs -> 5 min each (pure interpolation from B)
    assert new[-1]["arr"] - new[1]["dep"] == 10


def test_skip_span_out_of_order_raises():
    trip = _trip(480, BASE_NAMES, 60)
    v = BranchVariant(name="s", skip_spans=(SkipSpan("E", "B", 5.0),))
    with pytest.raises(ValueError):
        apply_variant(trip, v)


# --------------------------------------------------------------------------
# span measurement


def test_measure_span_savings_median():
    trips = [
        _trip(480, ["A", "L1", "L2", "E"], 30),
        _trip(540, ["A", "L1", "L2", "E"], 40),
        _trip(600, ["A", "L1", "L2", "E"], 20),
    ]
    m = measure_span_savings(trips, "A", "E")
    assert m["n"] == 3
    assert m["median"] == 30
    assert m["min"] == 20 and m["max"] == 40


def test_measure_span_no_service_raises():
    with pytest.raises(ValueError):
        measure_span_savings([_trip(480, ["A", "B"], 10)], "A", "Z")


# --------------------------------------------------------------------------
# alternation planner


def test_plan_equal_cycles_splits_evenly():
    trips = [_trip(480 + i * 10, BASE_NAMES, 60) for i in range(10)]
    plan = plan_alternation(
        trips,
        {"base": BranchVariant(name="base"), "alt": BranchVariant(name="alt")},
    )
    assert plan["n_trips"] == 10
    assert plan["trip_counts"] == {"base": 5, "alt": 5}
    assert abs(plan["shares"]["base"] - 0.5) < 1e-9


def test_plan_longer_cycle_gets_fewer_trips():
    trips = [_trip(480 + i * 10, BASE_NAMES, 60) for i in range(12)]
    # lisgar skips 15 min but adds 30 min of extension => longer cycle
    lisgar = BranchVariant(
        name="lisgar",
        skip_spans=(SkipSpan("B", "E", 15.0),),
        extension=Extension(from_stop="E", new_terminal="X", minutes=15),
    )
    plan = plan_alternation(
        trips, {"base": BranchVariant(name="base"), "lisgar": lisgar}
    )
    c_base = plan["variant_cycles"]["base"]
    c_lis = plan["variant_cycles"]["lisgar"]
    assert c_lis > c_base
    assert plan["trip_counts"]["lisgar"] < plan["trip_counts"]["base"]
    # counts sum preserved
    assert sum(plan["trip_counts"].values()) == 12


def test_plan_counts_always_sum_to_n():
    trips = [_trip(480 + i * 7, BASE_NAMES, 61 + i) for i in range(13)]
    plan = plan_alternation(
        trips,
        {"base": BranchVariant(name="base"), "alt": BranchVariant(name="alt")},
    )
    assert sum(plan["trip_counts"].values()) == 13


# --------------------------------------------------------------------------
# trunk headway


def test_headway_check_reports_base_distribution():
    trips = [_trip(480 + i * 10, BASE_NAMES, 60) for i in range(6)]
    chk = trunk_headway_check(trips, "A")
    assert chk["departures"] == 6
    assert chk["median_headway"] == 10
    assert chk["max_headway"] == 10
    assert chk["same_departure_set_as_base"] is True


# --------------------------------------------------------------------------
# rider impact


def test_impact_classifies_partial_and_new():
    trips = [_trip(480 + i * 10, BASE_NAMES, 60) for i in range(10)]
    skip = BranchVariant(name="skip", skip_spans=(SkipSpan("B", "E", 15.0),))
    base = BranchVariant(name="base")
    plan = plan_alternation(trips, {"base": base, "skip": skip})
    impact = rider_impact(trips, {"base": base, "skip": skip}, plan["trip_counts"])
    # E (rejoin) is served by both patterns -> "all"; C, D are skip-only-dropped
    assert impact["A"]["class"] == "all"
    assert impact["E"]["class"] == "all"
    assert impact["C"]["class"] == "partial"
    # base keeps 4/10 trips... base share of *total* trips × serving variants
    assert impact["C"]["kept_share"] == pytest.approx(
        plan["trip_counts"]["base"] / 10, abs=1e-6
    )
    assert impact["C"]["headway_multiple"] == pytest.approx(
        10 / plan["trip_counts"]["base"], abs=0.01
    )


def test_summarize_impact_counts():
    trips = [_trip(480 + i * 10, BASE_NAMES, 60) for i in range(10)]
    skip = BranchVariant(name="skip", skip_spans=(SkipSpan("B", "E", 15.0),))
    plan = plan_alternation(trips, {"base": BranchVariant(name="base"), "skip": skip})
    impact = rider_impact(
        trips, {"base": BranchVariant(name="base"), "skip": skip}, plan["trip_counts"]
    )
    s = summarize_impact(impact)
    # A, B, E served by both patterns; C, D dropped by skip
    assert s["stops_all"] == 3
    assert s["stops_partial"] == 2


def test_cycle_delta_skip_minus_extension():
    v = BranchVariant(name="v", skip_spans=(SkipSpan("B", "E", 20.0),))
    assert v.cycle_delta(10.0) == -20.0
    v2 = BranchVariant(
        name="v2",
        skip_spans=(SkipSpan("B", "E", 20.0),),
        extension=Extension(from_stop="E", new_terminal="X", minutes=10),
        terminal_recovery_fraction=0.5,
    )
    # -20 + 2*10 + 0.5*10 = +5
    assert v2.cycle_delta(10.0) == pytest.approx(5.0)


def test_trip_runtime():
    assert trip_runtime(_trip(480, ["A", "B", "C"], 30)) == 30


# --------------------------------------------------------------------------
# P-T157-2: interleave blending


def _anchor_deps(trips):
    return sorted(t[0]["dep"] for t in trips)


def test_round_robin_assigns_all_and_respects_counts():
    trips = [_trip(480 + i * 10, BASE_NAMES, 60) for i in range(10)]
    variants = {"base": BranchVariant(name="base"), "alt": BranchVariant(name="alt")}
    counts = {"base": 6, "alt": 4}
    a = assign_round_robin(trips, variants, counts)
    assert len(a) == 10
    from collections import Counter

    assert Counter(a.values()) == {"base": 6, "alt": 4}


def test_round_robin_count_mismatch_raises():
    trips = [_trip(480 + i * 10, BASE_NAMES, 60) for i in range(10)]
    with pytest.raises(ValueError):
        assign_round_robin(trips, {"base": BranchVariant(name="base")}, {"base": 9})


def test_interleave_no_variant_matches_base_exactly():
    trips = [_trip(480 + i * 21, BASE_NAMES, 60) for i in range(8)]
    variants = {"base": BranchVariant(name="base"), "alt": BranchVariant(name="alt")}
    counts = {"base": 4, "alt": 4}
    a = assign_round_robin(trips, variants, counts)
    chk = interleave_check(trips, variants, a, split_stop="A", merge_stop="E")
    # no skip savings -> blended arrival set identical to base
    assert chk["new_bunches"] == 0
    assert chk["gyrate_delta"] == 0.0
    assert chk["base"]["median_gap"] == chk["blended"]["median_gap"]


def test_interleave_detects_new_bunches_from_skip():
    # base: uniform 20-min gaps; skip variant arrives 15 min early at merge,
    # so a skip trip can land right behind (or ahead of) a base trip.
    trips = []
    for i in range(10):
        dep = 480 + i * 20
        t = _trip(dep, BASE_NAMES, 60)
        trips.append(t)
    skip = BranchVariant(name="skip", skip_spans=(SkipSpan("B", "E", 15.0),))
    base = BranchVariant(name="base")
    variants = {"base": base, "skip": skip}
    counts = {"base": 5, "skip": 5}
    a = assign_round_robin(trips, variants, counts, anchor_stop="A")
    chk = interleave_check(trips, variants, a, split_stop="A", merge_stop="E")
    # the skip shifts every other arrival 15 min earlier; uniform 20s become
    # 5/35 alternating (or bunches) — either way the stats must MOVE
    assert (
        chk["new_bunches"] != 0
        or chk["gyrate_delta"] != 0.0
        or chk["gap_stdev_delta"] != 0.0
    )


def test_interleave_oscillation_visible_in_stdev():
    # construct the exact oscillation: uniform 21-min base, skip saves 10,
    # perfect alternation -> gaps alternate 11/31, stdev explodes, no bunches
    trips = [_trip(480 + i * 21, BASE_NAMES, 60) for i in range(10)]
    skip = BranchVariant(name="skip", skip_spans=(SkipSpan("B", "E", 10.0),))
    variants = {"base": BranchVariant(name="base"), "skip": skip}
    counts = {"base": 5, "skip": 5}
    a = assign_round_robin(trips, variants, counts, anchor_stop="A")
    chk = interleave_check(trips, variants, a, split_stop="A", merge_stop="E")
    assert chk["base"]["bunches"] == chk["blended"]["bunches"]  # no bunching
    assert chk["gap_stdev_delta"] > 0  # but oscillation is visible


def test_cycle_compatibility_residuals():
    plan = {
        "variant_cycles": {"base": 54.0, "lisgar": 74.5},
    }
    out = cycle_compatibility(plan, 21.0)
    assert out["base"]["ratio"] == pytest.approx(54.0 / 21.0, abs=1e-3)
    assert out["base"]["nearest_integer_multiple"] == 3
    assert out["base"]["residual_min"] == pytest.approx(54.0 - 63.0, abs=1e-6)
    assert out["lisgar"]["nearest_integer_multiple"] == 4
    assert out["lisgar"]["residual_min"] == pytest.approx(74.5 - 84.0, abs=1e-6)


def test_apply_variant_tolerates_missing_span():
    # the 45A lesson: trips without the loop pattern must pass through intact
    trip = _trip(480, ["A", "B", "C"], 30)
    v = BranchVariant(name="s", skip_spans=(SkipSpan("X", "Z", 5.0),))
    new, dropped = apply_variant(trip, v)
    assert [r["name"] for r in new] == ["A", "B", "C"]
    assert dropped == []
