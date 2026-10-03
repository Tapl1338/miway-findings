"""The solver's trust fields (status + solve duration) reach the API payload.

Status already flowed through; solve_duration_seconds was added so the UI can
show how converged a run is (see SOLVER_RELATIVE_GAP in config: weekend solves
now finish early as certified-OPTIMAL instead of burning the full budget).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_run_full_optimization_stamps_duration():
    """A real (tiny) run reports a positive solve duration."""
    import app.transfer_sync as ts

    result = ts.run_full_optimization(
        service_day="weekday",
        volume_mode="uniform",
        time_limit_seconds=5,
        max_connections=50,
    )
    assert result.solve_duration_seconds is not None
    assert result.solve_duration_seconds > 0


def test_optimize_response_schema_carries_duration():
    """OptimizeResponse accepts and serializes the new field."""
    from app.models import OptimizeResponse

    resp = OptimizeResponse(
        status="OPTIMAL",
        solve_duration_seconds=12.3,
        offsets=[],
        baseline_avg_wait=10.0,
        optimized_avg_wait=9.0,
        baseline_missed=5,
        optimized_missed=3,
        total_connections=100,
        total_kept=90,
        passenger_minutes_saved=1.0,
        connection_health=90.0,
        wait_distribution_baseline=[1, 2, 3],
        wait_distribution_optimized=[1, 2, 3],
        nodes=[],
    )
    data = resp.model_dump()
    assert data["solve_duration_seconds"] == 12.3
    assert data["status"] == "OPTIMAL"


def test_duration_is_none_when_unset():
    """solve_transfer_sync alone (no facade) leaves duration unset — the UI
    treats a missing duration as 'unknown', never as 0."""
    from app.solver_core import solve_transfer_sync
    from app.transfer_types import TransferConnection, TransferNode

    node = TransferNode(
        stop_id="s",
        stop_name="S",
        stop_lat=0.0,
        stop_lon=0.0,
        routes=["1", "2"],
    )
    node.connections = [
        TransferConnection(
            node_k="s",
            route_i="1",
            route_j="2",
            arr_time=400.0,
            dep_time=404.0,
            base=4.0,
            weight=1.0,
        )
    ]
    result = solve_transfer_sync(
        [node], max_shift=5.0, headways={"1": 15.0, "2": 20.0}, time_limit_seconds=5
    )
    assert result.solve_duration_seconds is None
    assert result.status == "OPTIMAL"
