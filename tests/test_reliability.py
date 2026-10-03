"""Tests for transfer-reliability aggregation (``app/reliability.py``).

Pure/synthetic: nodes and lateness pools are hand-built, so the realized-wait
math is checked exactly without the GTFS feed or the transfer graph.
"""

import numpy as np
import pytest
from app.reliability import (
    _weighted_percentile,
    build_nodes_reliability,
    node_reliability,
)
from app.transfer_sync import TransferConnection, TransferNode


def _node(
    connections: list[TransferConnection], name: str = "Civic Sq"
) -> TransferNode:
    return TransferNode(
        stop_id="marker_1",
        stop_name=name,
        stop_lat=43.59,
        stop_lon=-79.64,
        routes=sorted({r for c in connections for r in (c.route_i, c.route_j)}),
        connections=connections,
        hub_boost=1.0,
    )


def _conn(
    base: float,
    route_i: str = "1",
    route_j: str = "2",
    weight: float = 1.0,
    walk: float = 0.0,
) -> TransferConnection:
    return TransferConnection(
        node_k="n",
        route_i=route_i,
        route_j=route_j,
        arr_time=0.0,
        dep_time=base,
        base=base,
        weight=weight,
        walk_minutes=walk,
    )


def _pool(lateness_minutes, n: int = 40) -> np.ndarray:
    """Repeat a small empirical set to ``n`` draws for a route's lateness pool."""
    vals = np.asarray(lateness_minutes, dtype=float)
    return np.resize(vals, n)


def test_late_departing_route_lengthens_wait():
    """When the *departing* route runs late (vs an on-time arriving route),
    the departing bus keeps getting pushed back, so the real wait grows above
    the scheduled wait and the connection almost never fails."""
    by_route = {
        "1": _pool([-1, 0, 0, 1]),  # arriving, ~on time
        "2": _pool([6, 7, 8, 9]),  # departing, ~7 min late
    }
    node = _node([_conn(base=5.0, route_i="1", route_j="2")])
    stats = node_reliability(node, by_route)
    assert stats["measured_share"] == 1.0
    # realized median ~ base + median(L_j) - median(L_i) = 5 + 7.5 = 12.5
    assert stats["realized_median_min"] > stats["scheduled_median_min"]
    assert stats["realized_median_min"] > 7.0
    assert stats["delta_median_min"] > 0
    assert stats["realized_p90_min"] >= stats["realized_median_min"]
    assert stats["p_miss"] < 0.05  # the departure keeps moving later


def test_late_arriving_route_misses_connections():
    """When the *arriving* route is chronically late, the on-time departure
    leaves before riders get there: most connections fail."""
    by_route = {
        "1": _pool([8, 9, 10]),  # arriving, ~9 min late
        "2": _pool([0, 1, 2]),  # departing, ~on time
    }
    node = _node([_conn(base=5.0, route_i="1", route_j="2")])
    stats = node_reliability(node, by_route)
    assert stats["p_miss"] > 0.5
    assert stats["realized_median_min"] < stats["scheduled_median_min"]
    assert stats["realized_p90_min"] >= stats["realized_median_min"]


def test_early_departing_route_shrinks_wait():
    """An early departing route (a missed bus either way, but a shorter wait for
    those who are there) can push the realized median *below* scheduled."""
    by_route = {
        "1": _pool([0]),
        "2": _pool([-5.0]),
    }
    node = _node([_conn(base=10.0, route_i="1", route_j="2")])
    stats = node_reliability(node, by_route)
    # realized = 10 + (-5) - 0 = 5  (constant pool -> exact)
    assert abs(stats["realized_median_min"] - 5.0) <= 0.1


def test_unmeasured_pair_falls_back_to_scheduled():
    """A pair with too few observations must not claim reliability: realized ==
    scheduled, never missed, and measured_share == 0 (node reads gray)."""
    by_route = {
        "1": _pool([0], n=20),
        "2": _pool([10], n=3),  # too few (< config.MIN_LATENESS_OBS)
    }
    node = _node([_conn(base=8.0)])
    stats = node_reliability(node, by_route)
    assert stats["measured_share"] == 0.0
    assert stats["realized_median_min"] == stats["scheduled_median_min"] == 8.0
    assert stats["p_miss"] == 0.0


def test_mixed_measured_share():
    """One measured connection and one unmeasured: measured_share reflects the
    rider-weight fraction and the node median mixes scheduled fallback in."""
    by_route = {"1": _pool([0]), "2": _pool([6.0])}
    a = _conn(base=4.0, route_i="1", route_j="2", weight=1.0)  # measured
    b = _conn(base=2.0, route_i="9", route_j="8", weight=3.0)  # unmeasured routes
    node = _node([a, b])
    stats = node_reliability(node, by_route)
    # 1 measured weight of 4 -> 0.25 measured share
    assert abs(stats["measured_share"] - 0.25) < 0.01


def test_weighted_median():
    assert _weighted_percentile(np.array([0.0, 10.0]), np.array([1.0, 3.0]), 50) == 10.0
    assert _weighted_percentile(np.array([0.0, 10.0]), np.array([3.0, 1.0]), 50) == 0.0
    import math

    assert math.isnan(_weighted_percentile(np.array([]), np.array([]), 50))


def test_deterministic_reproducible():
    by_route = {"1": _pool([-1, 0, 1]), "2": _pool([5, 6, 7])}
    node = _node([_conn(base=6.0), _conn(base=8.0), _conn(base=3.0)])
    s1 = node_reliability(node, by_route)
    s2 = node_reliability(node, by_route)
    assert s1 == s2


def test_empty_node():
    assert node_reliability(TransferNode("x", "y", 0.0, 0.0, [], []), {}) == {
        "scheduled_median_min": None,
        "realized_median_min": None,
        "realized_p90_min": None,
        "delta_median_min": None,
        "p_miss": 0.0,
        "measured_share": 0.0,
        "n_connections": 0,
    }


def test_build_nodes_reliability_rejects_bad_period():
    with pytest.raises(ValueError):
        build_nodes_reliability(period="overnight")


def test_schedule_padding_endpoint_live():
    """The measured schedule-padding endpoint serves the ground-truth metric."""
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        r = client.get("/api/measured/schedule-padding")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "n_holds" in body or body.get("available") is False
