"""
Unit tests for the RAPTOR journey planner (``app.routing``).

Exercises ``plan_journey`` directly against a tiny synthetic network (no HTTP):
a same-route hop, a two-bus transfer, an infeasible request, and the walking
fallback that wins when walking beats transit.
"""

import pandas as pd
import pytest
from app.routing import plan_journey

# Stops are spread out so direct A->C / A->D walks exceed the 1500 m access
# cap (forcing transit), while A->B stays under the 800 m transfer-walk cap.
STOPS = [
    {"stop_id": "A", "stop_name": "Alpha", "stop_lat": 43.60, "stop_lon": -79.60},
    {"stop_id": "B", "stop_name": "Beta", "stop_lat": 43.605, "stop_lon": -79.605},
    {"stop_id": "C", "stop_name": "Gamma", "stop_lat": 43.615, "stop_lon": -79.615},
    {"stop_id": "D", "stop_name": "Delta", "stop_lat": 43.63, "stop_lon": -79.63},
    {"stop_id": "X", "stop_name": "Nowhere", "stop_lat": 43.90, "stop_lon": -79.90},
]

TRIPS = [
    {"trip_id": "T1", "route_short_name": "R1"},
    {"trip_id": "T2", "route_short_name": "R1"},
    {"trip_id": "T3", "route_short_name": "R1"},
    {"trip_id": "U1", "route_short_name": "R2"},
    {"trip_id": "U2", "route_short_name": "R2"},
]

# R1 runs A -> B -> C every 10 min; R2 runs C -> D at 66/76.
STOP_TIMES = [
    {
        "trip_id": "T1",
        "stop_sequence": 1,
        "stop_id": "A",
        "arr_min": 60.0,
        "dep_min": 60.0,
    },
    {
        "trip_id": "T1",
        "stop_sequence": 2,
        "stop_id": "B",
        "arr_min": 62.0,
        "dep_min": 63.0,
    },
    {
        "trip_id": "T1",
        "stop_sequence": 3,
        "stop_id": "C",
        "arr_min": 65.0,
        "dep_min": 65.0,
    },
    {
        "trip_id": "T2",
        "stop_sequence": 1,
        "stop_id": "A",
        "arr_min": 70.0,
        "dep_min": 70.0,
    },
    {
        "trip_id": "T2",
        "stop_sequence": 2,
        "stop_id": "B",
        "arr_min": 72.0,
        "dep_min": 73.0,
    },
    {
        "trip_id": "T2",
        "stop_sequence": 3,
        "stop_id": "C",
        "arr_min": 75.0,
        "dep_min": 75.0,
    },
    {
        "trip_id": "T3",
        "stop_sequence": 1,
        "stop_id": "A",
        "arr_min": 80.0,
        "dep_min": 80.0,
    },
    {
        "trip_id": "T3",
        "stop_sequence": 2,
        "stop_id": "B",
        "arr_min": 82.0,
        "dep_min": 83.0,
    },
    {
        "trip_id": "T3",
        "stop_sequence": 3,
        "stop_id": "C",
        "arr_min": 85.0,
        "dep_min": 85.0,
    },
    {
        "trip_id": "U1",
        "stop_sequence": 1,
        "stop_id": "C",
        "arr_min": 66.0,
        "dep_min": 66.0,
    },
    {
        "trip_id": "U1",
        "stop_sequence": 2,
        "stop_id": "D",
        "arr_min": 68.0,
        "dep_min": 68.0,
    },
    {
        "trip_id": "U2",
        "stop_sequence": 1,
        "stop_id": "C",
        "arr_min": 76.0,
        "dep_min": 76.0,
    },
    {
        "trip_id": "U2",
        "stop_sequence": 2,
        "stop_id": "D",
        "arr_min": 78.0,
        "dep_min": 78.0,
    },
]


@pytest.fixture(scope="module")
def feed():
    return (
        pd.DataFrame(STOP_TIMES),
        pd.DataFrame(TRIPS),
        pd.DataFrame(STOPS),
    )


def plan(feed, origin, destination, depart_at=60.0):
    stop_times, trips, stops = feed
    return plan_journey(
        stop_times,
        trips,
        stops,
        origin,
        destination,
        depart_at=depart_at,
    )


def test_same_route_journey(feed):
    """A -> C on route R1 is a single bus leg, no transfer."""
    itin = plan(feed, ("stop", "A", 0.0), ("stop", "C", 0.0))
    assert itin is not None
    bus_legs = [leg for leg in itin.legs if leg.kind == "bus"]
    assert len(bus_legs) == 1
    leg = bus_legs[0]
    assert leg.route == "R1"
    assert leg.trip_id == "T1"
    assert leg.board_stop == "A"
    assert leg.alight_stop == "C"
    assert itin.transfers == 0
    assert itin.total_minutes == pytest.approx(5.0)
    assert itin.depart_at == 60.0
    assert itin.arrive_at == pytest.approx(65.0)


def test_multi_segment_transfer(feed):
    """A -> D needs two buses: R1 to C, then R2 C -> D (waiting for U2)."""
    itin = plan(feed, ("stop", "A", 0.0), ("stop", "D", 0.0))
    assert itin is not None
    bus_legs = [leg for leg in itin.legs if leg.kind == "bus"]
    assert [leg.route for leg in bus_legs] == ["R1", "R2"]
    assert bus_legs[0].board_stop == "A"
    assert bus_legs[0].alight_stop == "C"
    assert bus_legs[1].board_stop == "C"
    assert bus_legs[1].alight_stop == "D"
    assert itin.transfers == 1
    # 5 min ride + 2 min ride; the inter-leg wait is outside the leg sum
    # (total_minutes is moving time — pinned semantics). arrive_at is the
    # CLOCK arrival and must include the wait: depart + moving + waits
    # (2026-09-24 sweep: the old pin arrived_at == depart + total, which
    # let the header report an arrival earlier than the legs' own times).
    wait = bus_legs[1].board_time - bus_legs[0].alight_time
    assert itin.total_minutes == pytest.approx(7.0)
    assert itin.arrive_at == pytest.approx(itin.depart_at + itin.total_minutes + wait)


def test_infeasible_request(feed):
    """Stop X is served by nothing and far from everything: no journey."""
    itin = plan(feed, ("stop", "X", 0.0), ("stop", "D", 0.0))
    assert itin is None


def test_walking_fallback(feed):
    """Two points ~15 m apart: walking wins over walking to the bus."""
    origin = ("point", 43.6002, -79.6002)
    destination = ("point", 43.6003, -79.6003)
    itin = plan(feed, origin, destination)
    assert itin is not None
    assert [leg.kind for leg in itin.legs] == ["walk"]
    assert itin.transfers == 0
    assert itin.total_minutes < 1.0


def test_dep_buckets_exclude_final_stop(feed):
    """A trip's FINAL stop is an arrival only -- its out-of-service departure
    must not enter the boarding index (phantom-boarding regression, mirroring
    test_boarding_a_terminating_trip_is_dropped in test_transfer_sync.py)."""
    from app.routing import build_network

    stop_times, trips, stops = feed
    net = build_network(stop_times, trips, stops)
    # C is the last stop of every R1 trip; it must not be a boardable
    # departure stop for R1 (it stays boardable via R2's first stop).
    assert ("R1", "C") not in net._dep_buckets
    # First/mid stops stay indexed.
    assert ("R1", "A") in net._dep_buckets
    assert ("R2", "C") in net._dep_buckets
