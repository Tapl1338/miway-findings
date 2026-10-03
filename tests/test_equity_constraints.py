"""P2.3 equity constraints: ward caps inside the MILP + status reporting.

Synthetic fixtures only (no real feed): the solver is exercised directly via
``solve_transfer_sync`` so each test pins one behavior of the constraint or
the report, per the roadmap's acceptance check ("Solver output includes
constraint status and tradeoff explanation").
"""

from __future__ import annotations

from app.equity_constraints import EquityConstraints, WardMap, load_ward_map
from app.solver_core import solve_transfer_sync
from app.transfer_sync import (
    TransferConnection,
    TransferNode,
)


def _node(
    stop_id: str,
    name: str,
    ward: str | None,
    pairs: list[tuple[str, str, float, float]],
):
    """Build a node from (route_i, route_j, base_wait, weight) tuples."""
    conns = [
        TransferConnection(
            node_k=stop_id,
            route_i=ri,
            route_j=rj,
            arr_time=0.0,
            dep_time=base,
            base=base,
            weight=w,
        )
        for ri, rj, base, w in pairs
    ]
    return TransferNode(
        stop_id=stop_id,
        stop_name=name,
        stop_lat=43.5,
        stop_lon=-79.6,
        routes=sorted({c.route_i for c in conns} | {c.route_j for c in conns}),
        connections=conns,
    )


def _ward_map() -> WardMap:
    m = WardMap()
    m.by_name["stop a"] = "9"  # keys are casefolded, as load_ward_map stores them
    m.by_name["stop b"] = "1"
    return m


def _two_route_nodes():
    """Two stops: A (ward 9) B (ward 1); routes 2 and 16 meet at both.

    Shifting route 16 later hugely helps the heavy ward-1 connection at B
    but slightly hurts the light ward-9 connection at A — the unconstrained
    optimum takes that trade; a tight ward-9 cap must forbid it.
    """
    return [
        _node("A", "Stop A", "9", [("2", "16", 6.0, 1.0)]),
        _node("B", "Stop B", "1", [("16", "2", 14.0, 10.0)]),
    ]


HEADWAYS = {"2": 15.0, "16": 15.0}


def _solve(equity):
    return solve_transfer_sync(
        _two_route_nodes(),
        max_shift=5.0,
        buffer_minutes=2.0,
        t_max=30.0,
        headways=HEADWAYS,
        time_limit_seconds=10,
        equity=equity,
    )


def test_ward_map_lookup_by_name():
    m = _ward_map()
    assert m.ward_for("9999", "stop A") == "9"  # id miss -> name hit
    assert m.ward_for("0001", "unknown") is None
    assert bool(m)


def test_load_ward_map_from_repo_csv():
    import pathlib

    csv_path = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "data" / "ward_stops.csv"
    )
    m = load_ward_map(csv_path)
    assert len(m.by_id) > 3000
    assert m.ward_for("0001", "") == "8"


def test_unconstrained_takes_the_trade():
    r = _solve(None)
    assert r.equity_report is None
    # Without constraints the solver serves the heavy ward-1 connection and
    # accepts the small ward-9 worsening: route 16 moves (non-zero offset).
    assert any(v != 0 for v in r.offsets.values())


def test_tight_cap_binds_and_holds():
    ec = EquityConstraints(max_worsening_minutes=0.0, ward_map=_ward_map())
    r = _solve(ec)
    assert r.equity_report is not None
    assert r.equity_report["status"] == "applied"
    row9 = next(row for row in r.equity_report["rows"] if row["ward"] == "9")
    # Cap of zero: realized weighted worsening at ward 9 must be 0.
    assert row9["realized_weighted_worsening"] == 0.0
    assert row9["held"] is True


def test_per_ward_override():
    ec = EquityConstraints(
        max_worsening_minutes=0.0,
        ward_map=_ward_map(),
        ward_caps={"9": 5.0},
    )
    r = _solve(ec)
    row9 = next(row for row in r.equity_report["rows"] if row["ward"] == "9")
    assert row9["cap_weighted_minutes"] == 5.0


def test_network_wide_cap_without_ward_map():
    ec = EquityConstraints(max_worsening_minutes=100.0)  # no ward map
    r = _solve(ec)
    assert r.equity_report["status"] == "applied"
    (row,) = r.equity_report["rows"]
    assert row["ward"] is None


def test_equity_never_makes_result_worse_than_baseline():
    ec = EquityConstraints(max_worsening_minutes=0.0, ward_map=_ward_map())
    r = _solve(ec)
    # The dominated-incumbent guard guarantees the served plan is never
    # worse than as-scheduled, cap or no cap.
    assert r.optimized_avg_wait <= r.baseline_avg_wait + 1e-6


def test_worsen_report_shape():
    ec = EquityConstraints(max_worsening_minutes=50.0, ward_map=_ward_map())
    r = _solve(ec)
    rep = r.equity_report
    assert set(rep) >= {"rows", "wards_unbounded", "note", "status"}
    for row in rep["rows"]:
        assert {
            "ward",
            "cap_weighted_minutes",
            "connections",
            "realized_weighted_worsening",
            "held",
        } <= set(row)
