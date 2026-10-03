"""Tests for the measured boarding weighting (``volume_mode="measured"``)."""

import pandas as pd
import pytest
from app import config
from app.boarding import apply_measured_weights, load_boardings
from app.transfer_sync import TransferConnection, TransferNode


@pytest.fixture
def boarding_csv(tmp_path, monkeypatch):
    """Point the config at a tiny measured-boarding CSV for the test session."""
    path = tmp_path / "boardings_by_route.csv"
    df = pd.DataFrame(
        {
            "route_short_name": ["1", "2", "9999-not-a-route"],
            "boardings_per_day": [50_000.0, 5_000.0, 100.0],
            "service_day": ["weekday", "weekday", "weekday"],
        }
    )
    df.to_csv(path, index=False)
    monkeypatch.setattr(config, "BOARDING_CSV", path)
    load_boardings.cache_clear()
    yield path
    load_boardings.cache_clear()


def _nodes_with_connections() -> list[TransferNode]:
    """Synthetic transfer network: route 1 (heavy) x route 2 (light) and
    route 2 x route 9 (absent from the boarding table)."""
    node = TransferNode(
        stop_id="test-stop",
        stop_name="Test Stop",
        stop_lat=0.0,
        stop_lon=0.0,
        routes=["1", "2", "9"],
    )
    node.connections = [
        TransferConnection(
            node_k="test-stop",
            route_i="1",
            route_j="2",
            arr_time=400.0,
            dep_time=404.0,
            base=4.0,
            weight=1.0,
        ),
        TransferConnection(
            node_k="test-stop",
            route_i="2",
            route_j="9",
            arr_time=420.0,
            dep_time=424.0,
            base=4.0,
            weight=1.0,
        ),
    ]
    return [node]


def test_load_boardings_reads_csv(boarding_csv):
    boardings = load_boardings("weekday")
    assert boardings == {"1": 50_000.0, "2": 5_000.0, "9999-not-a-route": 100.0}


def test_load_boardings_empty_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BOARDING_CSV", tmp_path / "missing.csv")
    load_boardings.cache_clear()
    assert load_boardings("weekday") == {}
    load_boardings.cache_clear()


def test_measured_weights_prefer_boarding_strength(boarding_csv):
    """Routes in the boarding table must out-weight missing ones.

    Route 1 (50k boardings) paired with route 2 (5k) must weigh far more
    than route 2 paired with route 9, which is absent from the table and
    falls back to the small frequency estimate.
    """
    nodes = _nodes_with_connections()
    apply_measured_weights(nodes, service_day="weekday")

    conns = {c.route_j: c.weight for c in nodes[0].connections}
    assert conns["2"] > 0
    assert conns["9"] > 0
    assert conns["2"] > conns["9"], (
        f"heavy route pair {conns['2']} must out-weight unknown-route pair {conns['9']}"
    )


def test_measured_falls_back_to_frequency_without_csv(tmp_path, monkeypatch):
    """Without a CSV, measured mode keeps every connection weighted > 0."""
    monkeypatch.setattr(config, "BOARDING_CSV", tmp_path / "missing.csv")
    load_boardings.cache_clear()
    nodes = _nodes_with_connections()
    apply_measured_weights(nodes, service_day="weekday")
    assert all(c.weight > 0 for node in nodes for c in node.connections)
    load_boardings.cache_clear()


def test_proxied_routes_reflect_real_headway(tmp_path, monkeypatch):
    """Routes missing from the boarding table must be weighted by their *actual*
    frequency, not a constant: a 10-min-headway route out-weighs a 30-min one
    (regression: the proxy clamped h to a constant 15.0 for every route)."""
    path = tmp_path / "boardings_by_route.csv"
    pd.DataFrame(
        {
            "route_short_name": ["2"],
            "boardings_per_day": [10_000.0],
            "service_day": ["weekday"],
        }
    ).to_csv(path, index=False)
    monkeypatch.setattr(config, "BOARDING_CSV", path)
    load_boardings.cache_clear()
    monkeypatch.setattr(
        "app.boarding.prepare_feed",
        lambda _service_day: (None, None, None, None),
    )
    monkeypatch.setattr(
        "app.boarding.compute_route_headways",
        lambda _trips, _stop_times: {"9": 30.0, "99": 10.0},
    )

    node = TransferNode(
        stop_id="test-stop",
        stop_name="Test Stop",
        stop_lat=0.0,
        stop_lon=0.0,
        routes=["2", "9", "99"],
    )
    node.connections = [
        TransferConnection(
            node_k="test-stop",
            route_i="2",
            route_j="9",
            arr_time=400.0,
            dep_time=404.0,
            base=4.0,
            weight=1.0,
        ),
        TransferConnection(
            node_k="test-stop",
            route_i="2",
            route_j="99",
            arr_time=420.0,
            dep_time=424.0,
            base=4.0,
            weight=1.0,
        ),
    ]
    apply_measured_weights([node], service_day="weekday")

    conns = {c.route_j: c.weight for c in node.connections}
    assert conns["99"] > conns["9"], (
        f"10-min route {conns['99']} must out-weigh 30-min route {conns['9']}"
    )
    load_boardings.cache_clear()
