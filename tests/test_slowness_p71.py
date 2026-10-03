"""Fixtures-first tests for the corridor slowness decomposition (P7.1 Phase 1).

Implements the Phase-1 contract from
``docs/runs/p71-slowness-decomposition-session-plan.md`` (probe verdict,
2026-09-20): per-route decomposition anchored on GTFS in-vehicle time, with
measured pad, circuity geometry, and ghost-rate lenses — transfer wait stays
a separate hub lens (it depends on the rider's path, not the route).

Doctrine encoded here:

* **Zero-padding route-id normalization** — the observation pool carries
  ``'036'``-style ids that must join to GTFS ``'36'`` (the Phase-0 probe's
  join gotcha, pinned as a test).
* **Coverage holes are findings** — a route with no observations renders
  ``pad`` as ``null`` with a reason, never a fake 0.0 (P0.1 doctrine).
* **Every component is a provenance object** — value, source, n, fingerprint;
  the P1.1 shape. A bare number is a contract violation.
* **Positive-valued components** — in-vehicle, pad, ghost-rate are all >= 0
  (pad may legitimately be tiny-negative when schedules overstate; the card
  discloses that rather than clamping silently).
"""

from __future__ import annotations


import pandas as pd
import pytest

from app.services import slowness


@pytest.fixture(autouse=True)
def _isolate_circuity(monkeypatch):
    """No fixture may reach the real circuity analyzer (full feed + disk cache).

    Stubs the loader AND resets the module cache, in both directions:
    real values can't leak in (the original 2-failure bug), and fixture
    values can't leak out into later tests in the same session. The default
    environment has NO circuity artifacts — flagged routes are opt-in per
    test (see test_flagged_route_circuity_surfaces).
    """
    monkeypatch.setattr(slowness, "_load_circuity_summary", lambda: {})
    monkeypatch.setattr(slowness, "_CIRCUITY_SUMMARY", None)
    yield
    slowness._CIRCUITY_SUMMARY = None


@pytest.fixture()
def synthetic_feed(tmp_path, monkeypatch):
    """Three-route mini-GTFS: '36' (flagged), '71' (control), '16' (no obs)."""
    routes = pd.DataFrame(
        {"route_id": ["r36", "r71", "r16"], "route_short_name": ["36", "71", "16"]}
    )
    trips = pd.DataFrame(
        {
            "trip_id": [f"t{r}{i}" for r in ("36", "71", "16") for i in (1, 2)],
            "route_id": ["r36"] * 2 + ["r71"] * 2 + ["r16"] * 2,
            "route_short_name": ["36"] * 2 + ["71"] * 2 + ["16"] * 2,
            "direction_id": [0] * 6,
        }
    )
    rows = []
    # Route 36: 40 min scheduled run per trip -> 80 trip-minutes.
    # Route 71: 30 min. Route 16: 20 min.
    # Each synthetic trip: departs its first stop at 0, arrives its last at run.
    run = {"36": 40, "71": 30, "16": 20}
    for r in ("36", "71", "16"):
        for i in (1, 2):
            rows.append(
                {
                    "trip_id": f"t{r}{i}",
                    "stop_id": "s1",
                    "arr_min": run[r],
                    "dep_min": 0,
                }
            )
    stop_times = pd.DataFrame(rows)
    stops = pd.DataFrame(
        {
            "stop_id": ["s1"],
            "stop_lat": [43.5],
            "stop_lon": [-79.6],
            "stop_name": ["Stop 1"],
        }
    )

    feed = {
        "routes": routes,
        "trips": trips,
        "stop_times": stop_times,
        "stops": stops,
    }
    monkeypatch.setattr(slowness, "_prepared", lambda service_day: feed)
    return feed


@pytest.fixture()
def observations(tmp_path, monkeypatch):
    """Observation pool with zero-padded ids — 36 covered, 16 deliberately absent.

    Route 36 observes 6 trips: lateness [+2, +2, +2, +4, -2, -2] -> mean +1.0.
    """
    obs = pd.DataFrame(
        {
            "route_short_name": ["036", "036", "036", "36", "36", "36", "071"],
            "lateness_minutes": [2.0, 2.0, 2.0, 4.0, -2.0, -2.0, 1.0],
        }
    )
    csv = tmp_path / "obs_lateness.csv"
    obs.to_csv(csv, index=False)
    monkeypatch.setattr(slowness, "OBS_CSV", csv)
    return obs


def test_route_id_normalization_joins_padded_observation_ids(
    synthetic_feed, observations
):
    """'036' rows must land on GTFS route '36' — the Phase-0 probe's gotcha."""
    result = slowness.decompose_route("36")
    pad = result["components"]["pad_min"]
    assert pad is not None, "padded observation ids failed to join"
    assert pad["value"] == pytest.approx(1.0)
    assert pad["n"] == 6


def test_uncovered_route_renders_null_pad_with_reason(synthetic_feed, observations):
    """Route 16 has no observations: pad is null + reason, never a fake 0."""
    result = slowness.decompose_route("16")
    pad = result["components"]["pad_min"]
    assert pad["value"] is None
    assert "no observations" in pad["reason"].lower()


def test_in_vehicle_is_gtfs_scheduled_run_time(synthetic_feed, observations):
    """In-vehicle time comes from stop_times (trip run length), not latency."""
    result = slowness.decompose_route("36")
    iv = result["components"]["in_vehicle_min"]
    assert iv["value"] == pytest.approx(40.0)
    assert iv["source"] == "gtfs_stop_times"
    assert iv["n"] == 2  # two weekday trips in the synthetic feed


def test_every_component_is_a_provenance_object(synthetic_feed, observations):
    """No bare numbers: value/source/n or value/reason, per the P1.1 shape."""
    result = slowness.decompose_route("36")
    for name, comp in result["components"].items():
        assert "value" in comp, f"{name} lacks a value field"
        if comp["value"] is not None:
            assert "source" in comp and "n" in comp, f"{name} lacks provenance"
        assert "fingerprint" in comp


def test_components_are_non_negative(synthetic_feed, observations):
    """In-vehicle and ghost components are strictly >= 0; pad discloses sign."""
    for route in ("36", "71"):
        result = slowness.decompose_route(route)
        assert result["components"]["in_vehicle_min"]["value"] >= 0
        if (g := result["components"]["ghost_rate_pct"]) and g["value"] is not None:
            assert 0 <= g["value"] <= 100


def test_control_route_decomposition_is_complete(synthetic_feed, observations):
    """The control (71) has every measured component present — boring is proof."""
    result = slowness.decompose_route("71")
    comps = result["components"]
    assert comps["in_vehicle_min"]["value"] == pytest.approx(30.0)
    assert comps["pad_min"]["value"] is not None
    assert comps["circuity_ratio"]["value"] is None  # no geometry file in fixture


def test_circuity_ratio_optional_when_geometry_missing(synthetic_feed, observations):
    """No circuity artifacts in the fixture: ratio renders null with reason."""
    result = slowness.decompose_route("36")
    ratio = result["components"]["circuity_ratio"]
    assert ratio["value"] is None
    assert "reason" in ratio


def test_flagged_route_circuity_surfaces(synthetic_feed, observations, monkeypatch):
    """When the analyzer flags a route, its ratio surfaces with provenance."""
    monkeypatch.setattr(slowness, "_load_circuity_summary", lambda: {"36": 5.7})
    monkeypatch.setattr(slowness, "_CIRCUITY_SUMMARY", None)
    result = slowness.decompose_route("36")
    ratio = result["components"]["circuity_ratio"]
    assert ratio["value"] == pytest.approx(5.7)
    assert ratio["source"] == "circuity_summary"


# ---------------------------------------------------------------------------
# P7.1 Phase 2 — the journey-anchor sum invariant
# ---------------------------------------------------------------------------


def _plan_stub(itinerary):
    """Build a plan_journey stub returning a fixed itinerary-like object."""

    class _Leg:
        def __init__(self, kind, minutes, route=None, trip_id=None):
            self.kind, self.minutes, self.route, self.trip_id = (
                kind,
                minutes,
                route,
                trip_id,
            )

    class _Itin:
        def __init__(self, legs, total):
            self.legs, self.total_minutes = legs, total

    def _plan(*args, **kwargs):
        return _Itin(
            itinerary,
            itinerary[0].minutes
            if len(itinerary) == 1
            else sum(it.minutes for it in itinerary),
        )

    return _plan


def test_anchor_rides_route_and_sums_exactly(synthetic_feed, observations, monkeypatch):
    """Sum invariant: on-route + walk == end-to-end, and on-route == segment run."""
    calls = {"n": 0}

    class _Leg:
        def __init__(self, kind, minutes, route=None, trip_id=None):
            self.kind, self.minutes, self.route, self.trip_id = (
                kind,
                minutes,
                route,
                trip_id,
            )

    class _Itin:
        def __init__(self, legs, total):
            self.legs, self.total_minutes = legs, total

    def fake_plan(
        stop_times,
        trips,
        stops,
        origin,
        dest,
        *,
        depart_at,
        offsets,
        headways,
        max_transfers,
    ):
        calls["n"] += 1
        if depart_at < 500:
            return None  # early candidates fail
        # first successful candidate walks past the stop; later one rides
        if depart_at == 500:
            return _Itin([_Leg("walk", 5.0)], 5.0)
        return _Itin([_Leg("bus", 40.0, route="36", trip_id="t361")], 40.0)

    monkeypatch.setattr(slowness, "_journey_plan", fake_plan)
    a = slowness.journey_anchor("36")
    assert a["value"] == pytest.approx(40.0)
    assert a["on_route_min"] == pytest.approx(40.0)
    assert a["walk_min"] == pytest.approx(0.0)
    assert a["route_share_pct"] == pytest.approx(100.0)
    assert a["ridden_trip_id"] == "t361"


def test_anchor_prefers_highest_route_share(synthetic_feed, observations, monkeypatch):
    """Two riding candidates: the one with the biggest on-route share wins."""

    class _Leg:
        def __init__(self, kind, minutes, route=None, trip_id=None):
            self.kind, self.minutes, self.route, self.trip_id = (
                kind,
                minutes,
                route,
                trip_id,
            )

    class _Itin:
        def __init__(self, legs, total):
            self.legs, self.total_minutes = legs, total

    def fake_plan(
        stop_times,
        trips,
        stops,
        origin,
        dest,
        *,
        depart_at,
        offsets,
        headways,
        max_transfers,
    ):
        if depart_at == 480:
            # rides the route but with a long walk tail
            return _Itin(
                [_Leg("bus", 20.0, route="36", trip_id="tA"), _Leg("walk", 20.0)], 40.0
            )
        if depart_at == 540:
            return _Itin([_Leg("bus", 35.0, route="36", trip_id="tB")], 35.0)
        return None

    monkeypatch.setattr(slowness, "_journey_plan", fake_plan)
    a = slowness.journey_anchor("36")
    assert a["ridden_trip_id"] == "tB"
    assert a["route_share_pct"] == pytest.approx(100.0)
    assert a["value"] == pytest.approx(35.0)


def test_anchor_walk_only_journey_is_rejected(
    synthetic_feed, observations, monkeypatch
):
    """An itinerary that never boards the route is not an anchor (the 0.4-min
    direct-walk-vs-loop-route finding, pinned)."""

    class _Leg:
        def __init__(self, kind, minutes, route=None, trip_id=None):
            self.kind, self.minutes, self.route, self.trip_id = (
                kind,
                minutes,
                route,
                trip_id,
            )

    class _Itin:
        def __init__(self, legs, total):
            self.legs, self.total_minutes = legs, total

    def fake_plan(*args, **kwargs):
        return _Itin([_Leg("walk", 0.4)], 0.4)

    monkeypatch.setattr(slowness, "_journey_plan", fake_plan)
    a = slowness.journey_anchor("36")
    assert a["value"] is None
    assert "no candidate departure" in a["reason"]


def test_anchor_loop_route_pair_is_farthest_apart(
    synthetic_feed, observations, monkeypatch
):
    """Loop-route endpoints: the anchor pair is the farthest-apart stop pair
    (the route-16 finding), and scheduled_run_min is the SEGMENT run."""
    import pandas as pd

    pd.DataFrame(
        {
            "stop_id": ["A", "B", "C"],
            "stop_lat": [0.0, 0.0, 0.1],
            "stop_lon": [0.0, 0.1, 0.0],
        }
    )
    st = pd.DataFrame(
        {
            "trip_id": ["t1"] * 3,
            "stop_id": ["A", "B", "C"],
            "dep_min": [0.0, 10.0, 20.0],
            "arr_min": [0.0, 10.0, 20.0],
        }
    )
    coords = {"A": (0.0, 0.0), "B": (0.0, 0.1), "C": (0.1, 0.0)}
    a, b, _tid, run = slowness._longest_trip_endpoints(st, {"t1"}, coords)
    # B and C are the farthest-apart pair (B-C diagonal 0.141 deg > A-B/A-C 0.1);
    # segment run = arr(C) - dep(B) = 20 - 10 = 10
    assert (a, b) == ("B", "C")
    assert run == pytest.approx(10.0)


def test_unknown_route_raises_clean_error(synthetic_feed, observations):
    """A route that is not in the feed at all is a caller error, not nulls."""
    with pytest.raises(slowness.UnknownRouteError):
        slowness.decompose_route("999")


def test_manifest_lists_every_component_with_source(synthetic_feed, observations):
    """The route manifest names every decomposed route + component sources."""
    manifest = slowness.route_manifest()
    assert any(m["route_short_name"] == "36" for m in manifest)
    assert set(manifest[0]) >= {"route_short_name", "in_vehicle_min", "n_trips"}
