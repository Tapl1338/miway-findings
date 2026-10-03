"""Shared pytest fixtures for the MiWay Transit Optimizer backend tests."""

import sys
from pathlib import Path
from types import SimpleNamespace

# Ensure `backend` is importable regardless of the CWD pytest runs from.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd  # noqa: E402  (after sys.path setup)
import pytest  # noqa: E402

from app.models import TravelCompareRequest, TravelPoint  # noqa: E402


# ---- synthetic travel feed / optimizer stubs (routers/travel tests) ----------


@pytest.fixture
def travel_req() -> TravelCompareRequest:
    """Minimal valid compare request (stop origin, point destination)."""
    return TravelCompareRequest(
        origin=TravelPoint(mode="stop", stop_id="0001"),
        destination=TravelPoint(mode="point", lat=43.594, lon=-79.647),
        depart_at=600.0,
    )


@pytest.fixture
def fake_travel_feed():
    """Tiny two-stop feed shaped like prepare_feed's return value."""
    stops = pd.DataFrame(
        {
            "stop_id": ["0001", "0002"],
            "stop_name": ["Origin Stop", "Dest Stop"],
            "stop_lat": [43.58, 43.59],
            "stop_lon": [-79.75, -79.64],
        }
    )
    trips = pd.DataFrame({"trip_id": ["T1"], "route_id": ["R10"]})
    stop_times = pd.DataFrame(
        {
            "trip_id": ["T1", "T1"],
            "stop_id": ["0001", "0002"],
            "departure_time": ["08:00:00", "08:12:00"],
        }
    )
    return (object(), trips, stop_times, stops)


@pytest.fixture
def fake_optimization_result() -> SimpleNamespace:
    """Optimizer result stub with the fields the compare endpoint reads."""
    return SimpleNamespace(
        status="ok",
        offsets={"R10": -2.0},
        movable_routes=["R10"],
        baseline_avg_wait=5.0,
        optimized_avg_wait=3.0,
        baseline_missed=10,
        optimized_missed=6,
        total_connections=100,
        passenger_minutes_saved=42.0,
    )


def _bus_leg(**overrides) -> SimpleNamespace:
    """Bus-leg stub matching what _itin_json reads off an itinerary."""
    leg = SimpleNamespace(
        kind="bus",
        minutes=12.3,
        route="10",
        trip_id="T1",
        board_stop="0087",
        alight_stop="3104",
        board_time=600.0,
        alight_time=612.3,
        headway=None,
        stops=[("0087", 43.58, -79.75), ("3104", 43.59, -79.64)],
    )
    for k, v in overrides.items():
        setattr(leg, k, v)
    return leg


def _walk_leg() -> SimpleNamespace:
    """Walk-leg stub matching what _itin_json reads off an itinerary."""
    return SimpleNamespace(
        kind="walk",
        minutes=3.0,
        from_name="Origin",
        to_name="Stop 0087",
        distance_m=240.0,
        path=[(43.57, -79.76), (43.58, -79.75)],
    )


def _fake_itin(total: float, arrive_by: float | None = None) -> SimpleNamespace:
    """One-bus-leg itinerary stub with the given total duration.

    Default (depart_at mode): departs 600.0, arrives 600.0 + total.
    With ``arrive_by`` (reverse-mode semantics): arrives at the deadline,
    departs deadline − total.
    """
    if arrive_by is not None:
        return SimpleNamespace(
            legs=[_bus_leg()],
            total_minutes=total,
            transfers=0,
            depart_at=arrive_by - total,
            arrive_at=arrive_by,
        )
    return SimpleNamespace(
        legs=[_bus_leg()],
        total_minutes=total,
        transfers=0,
        depart_at=600.0,
        arrive_at=600.0 + total,
    )


@pytest.fixture
def bus_leg():
    return _bus_leg


@pytest.fixture
def walk_leg():
    return _walk_leg


@pytest.fixture
def fake_itin():
    return _fake_itin


@pytest.fixture
def trip_table():
    """Return the trip_table function from app.gtfs_kit."""
    from app.gtfs_kit import trip_table as trip_table_func

    return trip_table_func


@pytest.fixture
def service_filtered_trips(trip_table):
    """Return a callable that builds a trip table filtered to services active on `date`.

    Date convention: ISO 8601 (YYYY-MM-DD). Defaults to '2026-08-01'.
    """
    from app.gtfs_kit import service_ids_on

    def _get(date: str = "2026-08-01"):
        return trip_table(service_ids_on(date))

    return _get
