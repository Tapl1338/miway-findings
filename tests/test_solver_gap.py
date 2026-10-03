"""The solver's relative-gap stop (SOLVER_RELATIVE_GAP).

Measured on the real feed (2026-09-05): the Saturday objective bound stalls
at ~5.7%, so without a gap stop weekend solves burn their entire wall-clock
budget (up to 2x with the fleet retry) chasing optimality nobody reads. The
gap stop ends the solve once the incumbent is provably close enough.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ortools.sat.python import cp_model

import app.config as config
from app.solver_core import solve_transfer_sync
from app.transfer_types import TransferConnection, TransferNode


def _tiny_network() -> list[TransferNode]:
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


def test_gap_config_is_forwarded_to_solver(monkeypatch):
    """SOLVER_RELATIVE_GAP lands on the CP-SAT parameter, 0 disables it."""
    seen = {}
    real_solve = cp_model.CpSolver.Solve

    def spy(self, model):
        seen["gap"] = getattr(self.parameters, "relative_gap_limit", None)
        return real_solve(self, model)

    monkeypatch.setattr(cp_model.CpSolver, "Solve", spy)

    # Default config: the parameter is set.
    monkeypatch.setattr(config, "SOLVER_RELATIVE_GAP", 0.06)
    solve_transfer_sync(_tiny_network(), time_limit_seconds=5)
    assert seen["gap"] == 0.06

    # Opt-out (0): the parameter is left untouched.
    monkeypatch.setattr(config, "SOLVER_RELATIVE_GAP", 0)
    solve_transfer_sync(_tiny_network(), time_limit_seconds=5)
    assert seen["gap"] == 0


def test_tiny_solve_still_optimal_with_gap_active():
    """A trivial network solves to OPTIMAL with the production gap default."""
    result = solve_transfer_sync(
        _tiny_network(),
        max_shift=5.0,
        headways={"1": 15.0, "2": 20.0, "9": 30.0},
        time_limit_seconds=10,
        max_connections=100,
    )
    assert result.status == "OPTIMAL"
    assert result.total_connections == 2
    # OPTIMAL means the bound closed: no residual gap is reported.
    assert result.bound_gap_pct is None


@pytest.mark.slow
def test_time_limited_run_reports_bound_gap():
    """A deliberately starved solve (small budget, real network) ends
    FEASIBLE and reports the remaining headroom vs its best bound — the
    number the results badge renders as 'within X% of best'.

    Budget is 5 s (not 1 s): under parallel test load a 1 s solve sometimes
    finds no incumbent at all (UNKNOWN -> as-scheduled fallback, no bound to
    report), which is contention flake, not the behavior under test.

    P0.3: marked ``slow`` — a multi-second CP-SAT solve is contention-
    sensitive under xdist (``-n 4`` starves the incumbent search). The
    nightly matrix (``pytest -m slow``) is the sanctioned home for
    real-solve tests; the push gate drops it."""
    import app.transfer_sync as ts
    from app.feed_prep import prepare_feed
    from app.solver_core import build_fleet_interlining_edges

    ts.run_full_optimization(
        service_day="saturday", volume_mode="uniform", time_limit_seconds=2
    )
    _, trips, stop_times, stops = prepare_feed("saturday")
    headways = ts.cached_compute(
        key="gaptest_h", compute=lambda: ts.compute_route_headways(trips, stop_times)
    )
    fleet = ts.cached_compute(
        key="gaptest_f",
        compute=lambda: build_fleet_interlining_edges(trips, stop_times, stops),
    )
    nodes = ts.build_nodes_for_window(
        service_day="saturday", window_start=900.0, window_end=1140.0
    )
    ts.estimate_transfer_volumes(nodes, headways)
    result = solve_transfer_sync(
        nodes,
        max_shift=5.0,
        headways=headways,
        time_limit_seconds=5,
        max_connections=6000,
        fleet_edges=fleet,
        lateness_penalties=ts._precompute_lateness_penalties(
            nodes, service_day="saturday"
        ),
    )
    # PM Rush at a 5 s budget reliably saturates (measured bound gap 9-22%),
    # but under heavy parallel load the solve can either find no incumbent
    # (as-scheduled fallback) or — rarely — certify. Either way the contract
    # holds: FEASIBLE carries a positive gap, OPTIMAL carries none.
    if result.status == "FEASIBLE":
        assert result.bound_gap_pct is not None
        assert result.bound_gap_pct > 0
    else:
        assert result.status == "OPTIMAL"
        assert result.bound_gap_pct is None
