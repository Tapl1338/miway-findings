"""Tests for the on-the-fly equity computation.

Covers two accuracy regressions in ``app/routers/equity.py``:

* the endpoint must NOT 404 just because a stored ``response`` is missing —
  the node-level winners/losers come from the rebuilt graph, so a run whose
  response was never persisted (older runs, or runs saved before the response
  was stored) must still produce a report;
* ``_apply_weights`` must re-derive connection weights with exactly the same
  ``volume_mode`` dispatch the solver uses, so equity reflects the solved
  weights rather than an ad-hoc formula.
"""

from __future__ import annotations

from app import state_store
from app.routers import equity
from app.transfer_sync import TransferConnection, TransferNode


def _conn(route_i="1", route_j="2", base=5.0, weight=0.0) -> TransferConnection:
    return TransferConnection(
        node_k="NODE",
        route_i=route_i,
        route_j=route_j,
        arr_time=600.0,
        dep_time=605.0,
        base=base,
        weight=weight,
        walk_minutes=0.0,
        walk_cap_minutes=0.0,
        trip_i="t_i",
        trip_j="t_j",
    )


def _node(routes) -> TransferNode:
    return TransferNode(
        stop_id="NODE",
        stop_name="Node",
        stop_lat=43.6,
        stop_lon=-79.6,
        routes=routes,
        connections=[_conn(route_i=routes[0], route_j=routes[1])],
        hub_boost=1.0,
    )


def test_apply_weights_uniform_sets_all_to_one():
    node = _node(["1", "2"])
    headways = {"1": 30.0, "2": 15.0}
    equity._apply_weights([node], headways, {"volume_mode": "uniform"})
    assert node.connections[0].weight == 1.0


def test_apply_weights_unknown_mode_falls_back_to_frequency():
    node = _node(["1", "2"])
    headways = {"1": 30.0, "2": 15.0}
    # An unrecognised volume_mode must not zero weights; it uses the
    # frequency x hub-boost estimator (same branch the solver takes).
    equity._apply_weights([node], headways, {"volume_mode": "bogus"})
    assert node.connections[0].weight > 0.0


def test_apply_weights_measured_uses_boardings(monkeypatch):
    roadings = {"35": 10796.0, "42": 10750.0}
    monkeypatch.setattr("app.boarding.load_boardings", lambda *a, **k: roadings)
    node = _node(["35", "42"])
    equity._apply_weights(
        [node], {}, {"volume_mode": "measured"}, service_day="weekday"
    )
    # apply_measured_weights uses _strength(i) * _strength(j) * hub_boost (the
    # raw boarding product), rounded to 3 dp.
    expected = round(10796.0 * 10750.0, 3)
    assert abs(node.connections[0].weight - expected) < 1e-3


def test_equity_compute_does_not_404_when_response_missing(monkeypatch):
    """A run with no persisted response must still yield winners/losers.

    Regression: the endpoint used to gate on ``run.get("response")`` and 404
    even when a real run existed, because nothing populated response_json.
    """
    node = _node(["1", "2"])

    class _FakeRideResult:
        pass

    def _fake_build(*args, **kwargs):
        return [node]

    monkeypatch.setattr(
        state_store,
        "get_latest_run",
        lambda: {
            "params": {
                "volume_mode": "uniform",
                "service_day": "weekday",
                "window_start": 360.0,
                "window_end": 1320.0,
                "buffer_minutes": 2.0,
                "t_max": 25.0,
            },
            "offsets": {"1": 1},
            "response": None,  # older run, never persisted a response
        },
    )
    monkeypatch.setattr(equity, "build_nodes_for_window", _fake_build)
    monkeypatch.setattr(
        equity,
        "prepare_feed",
        lambda *a, **k: (None, None, None, None),
    )
    monkeypatch.setattr(equity, "compute_route_headways", lambda *a, **k: {})
    monkeypatch.setattr(equity, "load_ridership", lambda: {"1": 100.0, "2": 50.0})

    report = equity._compute_equity_from_stored()
    # The report must be produced (not a 404), with the usual shape.
    assert isinstance(report["winners"], list)
    assert isinstance(report["losers"], list)
    assert isinstance(report["route_losers"], list)
    for key in ("total_connections", "passenger_minutes_saved", "nodes_analyzed"):
        assert key in report


def test_equity_compute_caches_by_run_id_and_period(monkeypatch):
    """Revisiting the Equity tab with the same run + period must NOT re-solve
    the ~30s node-graph rebuild; a new optimization run invalidates the cache.
    """
    calls = {"n": 0}

    def fake_compute(period: str | None = None):
        calls["n"] += 1
        return {"nodes_analyzed": calls["n"], "period": period}

    monkeypatch.setattr(equity, "_compute_equity_from_stored", fake_compute)
    monkeypatch.setattr(
        state_store,
        "get_latest_run",
        lambda: {"id": 42, "params": {}, "offsets": {}, "response": {}},
    )
    equity._EQUITY_CACHE.clear()

    # First visit -> computes and caches.
    first = equity.compute_equity("all_day")
    assert calls["n"] == 1
    # Re-visiting the same run + period -> cache hit, no rebuild.
    second = equity.compute_equity("all_day")
    assert calls["n"] == 1
    assert first is second

    # A different period is a separate cache entry -> rebuild.
    equity.compute_equity("pm_rush")
    assert calls["n"] == 2

    # A brand-new optimization run (new autoincrement id) invalidates the cache.
    monkeypatch.setattr(
        state_store,
        "get_latest_run",
        lambda: {"id": 43, "params": {}, "offsets": {}, "response": {}},
    )
    equity.compute_equity("all_day")
    assert calls["n"] == 3


def test_ward_aggregate_spatial_fallback():
    """Test that _ward_aggregate assigns stops to wards via spatial fallback
    when the stop is not in ward_stops.csv but has lat/lon coordinates.

    Regression test for T61: adds KDTree-based spatial index fallback.
    """
    from app.routers.equity import _ward_aggregate

    # Node with lat/lon that IS in CSV (ward 8 from stop_id lookup)
    node_in_csv = {
        "stop_id": "0001",
        "stop_name": "Erin Mills Pky North Of Lincoln Green Way",
        "lat": "43.5678",
        "lon": "-79.6543",
        "delta_minutes": 5.0,
        "worse_off": False,
        "riders_at_stop_proxy": 100,
    }

    # Node with lat/lon that is NOT in CSV (should use spatial fallback)
    node_missing = {
        "stop_id": "99999",
        "stop_name": "Unknown Stop",
        "lat": "43.5678",
        "lon": "-79.6543",
        "delta_minutes": 3.0,
        "worse_off": True,
        "riders_at_stop_proxy": 75,
    }

    # Node without lat/lon should be unassigned
    node_no_coords = {
        "stop_id": "88888",
        "stop_name": "No Coords Stop",
        "delta_minutes": 2.0,
        "worse_off": False,
        "riders_at_stop_proxy": 25,
    }

    result = _ward_aggregate([node_in_csv, node_missing, node_no_coords])

    # Should produce a result (not None)
    assert result is not None

    # The missing-stop node should be assigned to a ward via spatial fallback,
    # not counted as unassigned (since lat/lon exists and KDTree found a match)
    # The no-coords node should be unassigned
    assert result["stops_unassigned"] == 1  # only the no-coords node

    # Should have wards assigned
    assert len(result["rows"]) >= 1
