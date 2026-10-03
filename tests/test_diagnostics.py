"""Tests for the transfer blind-spot diagnostics module."""

import pandas as pd
from unittest.mock import Mock, patch

import pytest

from app import diagnostics


def test_constants():
    """Diagnostic constants have expected values."""
    assert diagnostics.DIAG_SEARCH_HORIZON == 60.0  # minutes
    assert diagnostics.MAX_PREV_GAP == 3.0  # minutes


def test_fmt_clock_formats_minutes_correctly():
    """_fmt_clock converts minutes since midnight to HH:MM string."""
    assert diagnostics._fmt_clock(0) == "00:00"
    assert diagnostics._fmt_clock(60) == "01:00"
    assert diagnostics._fmt_clock(630) == "10:30"  # 10:30 AM
    assert diagnostics._fmt_clock(1320) == "22:00"  # 10:00 PM
    assert diagnostics._fmt_clock(1439) == "23:59"  # one minute before midnight
    assert diagnostics._fmt_clock(1440) == "24:00"  # exactly midnight next day


# NOTE: _json_headway / _direction_label / estimate_ridership_volumes tests
# removed 2026-09-12 — they targeted a module surface that never existed
# (the real diagnostics module exposes diagnose_transfer_blindspots and
# _fmt_clock only; see the playtest audit).


@patch("app.diagnostics.prepare_feed")
@patch("app.diagnostics.compute_route_headways")
@patch("app.diagnostics.build_nodes_for_window")
def test_diagnose_transfer_blindspots_basic_structure(
    mock_build_nodes_for_window,
    mock_compute_route_headways,
    mock_prepare_feed,
):
    """diagnose_transfer_blindspots returns expected structure with mocked deps.

    Uses volume_mode="uniform" so the ridership/transfer volume paths (which
    the module imports INSIDE the function body and which hit the real
    network otherwise) stay out of scope; uniform needs no extra wiring.
    """
    # Setup mocks. The trips frame must be a real DataFrame: the module
    # builds a trip_id -> headsign map from it (subscripted); the rest of
    # prepare_feed's tuple stays Mock.
    trips_df = pd.DataFrame(
        {"trip_id": ["trip1", "trip2"], "trip_headsign": ["1 North", "2 South"]}
    )
    mock_prepare_feed.return_value = (Mock(), trips_df, Mock(), Mock())
    mock_compute_route_headways.return_value = {"route1": 15.0}

    mock_node = Mock()
    mock_node.stop_id = "stop1"
    mock_node.stop_name = "Test Stop"
    mock_node.stop_lat = 43.6
    mock_node.stop_lon = -79.6

    mock_conn = Mock()
    mock_conn.route_i = "route1"
    mock_conn.route_j = "route2"
    mock_conn.base = 20.0  # wait time
    mock_conn.walk_minutes = 2.0
    mock_conn.walk_cap_minutes = 5.0
    mock_conn.trip_i = "trip1"
    mock_conn.trip_j = "trip2"
    mock_conn.prev_dep_time = 500.0
    mock_conn.arr_time = 520.0
    mock_conn.dep_time = 540.0
    mock_conn.weight = 1.5

    mock_node.connections = [mock_conn]
    mock_build_nodes_for_window.return_value = [mock_node]

    # Call function
    result = diagnostics.diagnose_transfer_blindspots(
        service_day="weekday",
        buffer_minutes=1.0,
        t_max=12.0,
        high_freq_cutoff=10.0,
        window_start=360.0,
        window_end=1320.0,
        volume_mode="uniform",
        limit=10,
    )

    # Verify structure
    assert "period" in result
    assert "t_max" in result
    assert "buffer_minutes" in result
    assert "default_window_minutes" in result
    assert "search_horizon_minutes" in result
    assert "summary" in result
    assert "connections" in result

    # Verify summary fields
    summary = result["summary"]
    assert "total_damaging" in summary
    assert "modeled" in summary
    assert "hidden" in summary
    assert "just_missed" in summary
    assert "shiftable_within_max" in summary
    assert "not_shiftable" in summary
    assert "worst_wait_minutes" in summary
    assert "worst_headway_minutes" in summary

    # The single mocked connection: wait=20 > t_max=12 -> "too long"; 20 <=
    # default_window 22 -> "modeled"; overshoot 8 min fits 2*max_shift=10 ->
    # shiftable. prev-departure gap (520-500=20) > MAX_PREV_GAP -> not a
    # just-miss. Classification values are asserted, not just key presence.
    assert summary["total_damaging"] == 1
    assert summary["modeled"] == 1
    conn = result["connections"][0]
    assert conn["wait_minutes"] == 20.0
    assert conn["reason"] == "too long"
    assert conn["category"] == "modeled"
    assert conn["shift_to_fix_minutes"] == 8.0
    assert conn["shiftable_within_max"] is True
    assert conn["arr_time"] == "08:40"
    assert conn["dep_time"] == "09:00"

    # Verify connections array structure
    expected_fields = {
        "stop_id",
        "stop_name",
        "stop_lat",
        "stop_lon",
        "route_i",
        "route_j",
        "arr_time",
        "dep_time",
        "prev_dep_time",
        "wait_minutes",
        "headway_minutes",
        "weight",
        "cost_minutes",
        "reason",
        "category",
        "shift_to_fix_minutes",
        "shiftable_within_max",
        "direction_i",
        "direction_j",
    }
    assert set(conn.keys()) == expected_fields


if __name__ == "__main__":
    pytest.main([__file__])
