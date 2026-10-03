import pytest
from pydantic import ValidationError
from app.models import (
    OptimizeRequest,
    OffsetInfo,
    NodeInfo,
    RidershipImpact,
    FleetFeasibility,
    RouteImpact,
    OptimizeResponse,
    OptimizeJobResponse,
    OptimizeJobStatus,
    TravelPoint,
    TravelCompareRequest,
)


class TestOptimizeRequest:
    def test_defaults(self):
        req = OptimizeRequest()
        assert req.max_shift == 5.0
        assert req.buffer_minutes == 2.0
        assert req.high_freq_cutoff == 10.0
        assert req.t_max == 12.0
        assert req.service_day == "weekday"
        assert req.volume_mode == "ridership"
        assert req.window_start == 360.0
        assert req.window_end == 1320.0
        assert req.max_connections == 6000
        assert req.time_limit_seconds == 30
        assert req.min_layover_minutes is None

    def test_window_validation(self):
        with pytest.raises(
            ValueError, match="window_end must be greater than window_start"
        ):
            OptimizeRequest(window_start=100.0, window_end=50.0)

    def test_window_validation_passes(self):
        req = OptimizeRequest(window_start=100.0, window_end=200.0)
        assert req.window_start == 100.0
        assert req.window_end == 200.0

    def test_valid_field_ranges(self):
        req = OptimizeRequest(
            max_shift=0.0,
            buffer_minutes=0.0,
            high_freq_cutoff=1.0,
            t_max=1.0,
            window_start=0.0,
            window_end=2820.0,
            max_connections=100,
            time_limit_seconds=1,
        )
        assert req.max_shift == 0.0
        assert req.buffer_minutes == 0.0
        assert req.high_freq_cutoff == 1.0
        assert req.t_max == 1.0
        assert req.window_start == 0.0
        assert req.window_end == 2820.0
        assert req.max_connections == 100
        assert req.time_limit_seconds == 1

    def test_min_layover(self):
        req = OptimizeRequest(min_layover_minutes=15.0)
        assert req.min_layover_minutes == 15.0

        req = OptimizeRequest(min_layover_minutes=0.0)
        assert req.min_layover_minutes == 0.0

    def test_invalid_service_day(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(service_day="invalid")

    def test_invalid_volume_mode(self):
        with pytest.raises(ValidationError):
            OptimizeRequest(volume_mode="invalid")

    def test_optional_period_field(self):
        req = OptimizeRequest(period=None)
        assert req.period is None

        req = OptimizeRequest(period="late_night")
        assert req.period == "late_night"


class TestOffsetInfo:
    def test_basic_creation(self):
        offset = OffsetInfo(
            route_short_name="23",
            route_long_name="University",
            offset_minutes=5,
            headway_minutes=10.0,
            movable=True,
        )
        assert offset.route_short_name == "23"
        assert offset.route_long_name == "University"
        assert offset.offset_minutes == 5
        assert offset.headway_minutes == 10.0
        assert offset.movable is True


class TestNodeInfo:
    def test_basic_creation(self):
        node = NodeInfo(
            stop_id="1234",
            stop_name="Square One Shopping Centre",
            lat=43.5,
            lon=-79.5,
            routes=["23", "66"],
            hub_boost=1.5,
            connection_count=42,
            friction_score=0.8,
        )
        assert node.stop_id == "1234"
        assert node.stop_name == "Square One Shopping Centre"
        assert node.lat == 43.5
        assert node.lon == -79.5
        assert node.routes == ["23", "66"]
        assert node.hub_boost == 1.5
        assert node.connection_count == 42
        assert node.friction_score == 0.8


class TestRidershipImpact:
    def test_basic_creation(self):
        impact = RidershipImpact(
            wait_minutes_saved=2.5,
            wait_time_premium=1.2,
            ivt_equivalent_minutes=5.0,
            avg_trip_minutes=15.0,
            travel_time_reduction_pct=5.0,
            travel_time_elasticity=0.5,
            projected_ridership_pct=8.0,
            projected_ridership_pct_min=3.0,
            projected_ridership_pct_max=15.0,
            methodology="standard formula",
        )
        assert impact.wait_minutes_saved == 2.5
        assert impact.wait_time_premium == 1.2
        assert impact.ivt_equivalent_minutes == 5.0
        assert impact.avg_trip_minutes == 15.0
        assert impact.travel_time_reduction_pct == 5.0
        assert impact.travel_time_elasticity == 0.5
        assert impact.projected_ridership_pct == 8.0
        assert impact.projected_ridership_pct_min == 3.0
        assert impact.projected_ridership_pct_max == 15.0
        assert impact.methodology == "standard formula"

    def test_default_extremes(self):
        impact = RidershipImpact(
            wait_minutes_saved=0.0,
            wait_time_premium=0.0,
            ivt_equivalent_minutes=0.0,
            avg_trip_minutes=0.0,
            travel_time_reduction_pct=0.0,
            travel_time_elasticity=0.0,
            projected_ridership_pct=0.0,
            methodology="test",
        )
        assert impact.projected_ridership_pct_min == 0.0
        assert impact.projected_ridership_pct_max == 0.0


class TestFleetFeasibility:
    def test_basic_creation(self):
        feasibility = FleetFeasibility(
            interlining_edges=3,
            baseline_violations=1,
            optimized_violations=0,
            min_layover_minutes=5.0,
            block_aware=True,
            detail="Feasible with optimization",
        )
        assert feasibility.interlining_edges == 3
        assert feasibility.baseline_violations == 1
        assert feasibility.optimized_violations == 0
        assert feasibility.min_layover_minutes == 5.0
        assert feasibility.block_aware is True
        assert feasibility.detail == "Feasible with optimization"


class TestRouteImpact:
    def test_basic_creation(self):
        impact = RouteImpact(
            route_short_name="23",
            route_long_name="University",
            connections=15,
            baseline_avg_eff_wait=8.0,
            optimized_avg_eff_wait=3.0,
            delta_minutes=-5.0,
            worse_off_connections=2,
            worse_off_max_minutes=7.0,
            worse_off=True,
        )
        assert impact.route_short_name == "23"
        assert impact.route_long_name == "University"
        assert impact.connections == 15
        assert impact.baseline_avg_eff_wait == 8.0
        assert impact.optimized_avg_eff_wait == 3.0
        assert impact.delta_minutes == -5.0
        assert impact.worse_off_connections == 2
        assert impact.worse_off_max_minutes == 7.0
        assert impact.worse_off is True

    def test_worse_off_false(self):
        impact = RouteImpact(
            route_short_name="66",
            route_long_name="Meadowvale",
            connections=10,
            baseline_avg_eff_wait=5.0,
            optimized_avg_eff_wait=5.0,
            delta_minutes=0.0,
            worse_off_connections=0,
            worse_off_max_minutes=0.0,
            worse_off=False,
        )
        assert impact.worse_off is False
        assert impact.delta_minutes == 0.0


class TestOptimizeResponse:
    def test_basic_creation(self):
        response = OptimizeResponse(
            status="OPTIMAL",
            solve_duration_seconds=12.5,
            bound_gap_pct=0.2,
            solver_variance_pct=0.5,
            offsets=[
                OffsetInfo(
                    route_short_name="23",
                    route_long_name="University",
                    offset_minutes=0,
                    headway_minutes=10.0,
                    movable=True,
                )
            ],
            baseline_avg_wait=8.5,
            optimized_avg_wait=3.2,
            baseline_missed=25,
            optimized_missed=18,
            total_connections=1000,
            total_kept=850,
            passenger_minutes_saved=425.0,
            connection_health=0.92,
            wait_distribution_baseline=[10, 20, 30, 40, 50],
            wait_distribution_optimized=[5, 10, 15, 20, 25],
            nodes=[
                NodeInfo(
                    stop_id="1234",
                    stop_name="Test Stop",
                    lat=43.5,
                    lon=-79.5,
                    routes=["23"],
                    hub_boost=1.0,
                    connection_count=10,
                    friction_score=0.5,
                )
            ],
            updated_stop_times_available=False,
            ridership_impact=None,
            fleet_feasibility=None,
            route_impacts=[],
        )
        assert response.status == "OPTIMAL"
        assert response.solve_duration_seconds == 12.5
        assert response.bound_gap_pct == 0.2
        assert response.solver_variance_pct == 0.5
        assert len(response.offsets) == 1
        assert response.offsets[0].route_short_name == "23"
        assert response.baseline_avg_wait == 8.5
        assert response.optimized_avg_wait == 3.2
        assert response.total_connections == 1000
        assert len(response.nodes) == 1


class TestOptimizeJobResponse:
    def test_basic_creation(self):
        job = OptimizeJobResponse(
            job_id="job_123",
            status="completed",
            created_at="2025-01-15T10:30:00Z",
        )
        assert job.job_id == "job_123"
        assert job.status == "completed"
        assert job.created_at == "2025-01-15T10:30:00Z"


class TestOptimizeJobStatus:
    def test_with_result(self):
        job = OptimizeJobStatus(
            job_id="job_456",
            status="completed",
            created_at="2025-01-15T10:30:00Z",
            started_at="2025-01-15T10:31:00Z",
            completed_at="2025-01-15T11:00:00Z",
            result=None,
            error=None,
            progress=1.0,
        )
        assert job.job_id == "job_456"
        assert job.status == "completed"
        assert job.created_at == "2025-01-15T10:30:00Z"
        assert job.started_at == "2025-01-15T10:31:00Z"
        assert job.completed_at == "2025-01-15T11:00:00Z"
        assert job.progress == 1.0

    def test_without_result(self):
        job = OptimizeJobStatus(
            job_id="job_789",
            status="pending",
            created_at="2025-01-15T10:30:00Z",
            result=None,
            error="Processing",
        )
        assert job.job_id == "job_789"
        assert job.status == "pending"
        assert job.error == "Processing"


class TestTravelPoint:
    def test_mode_stop(self):
        point = TravelPoint(mode="stop", stop_id="1234", name="Test Stop")
        assert point.mode == "stop"
        assert point.stop_id == "1234"
        assert point.name == "Test Stop"
        assert point.lat is None
        assert point.lon is None

    def test_mode_point(self):
        point = TravelPoint(mode="point", lat=43.5, lon=-79.5, name="Test Location")
        assert point.mode == "point"
        assert point.lat == 43.5
        assert point.lon == -79.5
        assert point.name == "Test Location"
        assert point.stop_id is None

    def test_default_name(self):
        point = TravelPoint(mode="stop", stop_id="1234")
        assert point.name == ""

    def test_invalid_mode(self):
        with pytest.raises(ValidationError):
            TravelPoint(mode="invalid")


class TestTravelCompareRequest:
    def test_defaults(self):
        origin = TravelPoint(mode="stop", stop_id="orig1234")
        destination = TravelPoint(mode="stop", stop_id="dest5678")
        req = TravelCompareRequest(origin=origin, destination=destination)
        assert req.max_transfers == 4
        assert req.service_day == "weekday"
        assert req.max_shift == 5.0
        assert req.buffer_minutes == 2.0
        assert req.high_freq_cutoff == 10.0
        assert req.t_max == 12.0
        assert req.volume_mode == "estimated"
        assert req.window_start == 360.0
        assert req.window_end == 1320.0
        assert req.max_connections == 6000
        assert req.time_limit_seconds == 60
        assert req.min_layover_minutes is None

    def test_window_validation(self):
        origin = TravelPoint(mode="stop", stop_id="orig1234")
        destination = TravelPoint(mode="stop", stop_id="dest5678")
        with pytest.raises(
            ValueError, match="window_end must be greater than window_start"
        ):
            TravelCompareRequest(
                origin=origin,
                destination=destination,
                window_start=100.0,
                window_end=50.0,
            )

    def test_window_validation_passes(self):
        origin = TravelPoint(mode="stop", stop_id="orig1234")
        destination = TravelPoint(mode="stop", stop_id="dest5678")
        req = TravelCompareRequest(
            origin=origin,
            destination=destination,
            window_start=100.0,
            window_end=200.0,
        )
        assert req.window_start == 100.0
        assert req.window_end == 200.0

    def test_empty_depart_arrive(self):
        origin = TravelPoint(mode="stop", stop_id="orig1234")
        destination = TravelPoint(mode="stop", stop_id="dest5678")
        req = TravelCompareRequest(
            origin=origin,
            destination=destination,
            depart_at=None,
            arrive_by=None,
        )
        assert req.depart_at is None
        assert req.arrive_by is None

    def test_valid_depart_arrive(self):
        origin = TravelPoint(mode="stop", stop_id="orig1234")
        destination = TravelPoint(mode="stop", stop_id="dest5678")
        req = TravelCompareRequest(
            origin=origin,
            destination=destination,
            depart_at=300.0,
            arrive_by=1500.0,
        )
        assert req.depart_at == 300.0
        assert req.arrive_by == 1500.0

    def test_optional_min_layover(self):
        origin = TravelPoint(mode="stop", stop_id="orig1234")
        destination = TravelPoint(mode="stop", stop_id="dest5678")
        req = TravelCompareRequest(
            origin=origin,
            destination=destination,
            min_layover_minutes=None,
        )
        assert req.min_layover_minutes is None

        req = TravelCompareRequest(
            origin=origin,
            destination=destination,
            min_layover_minutes=10.0,
        )
        assert req.min_layover_minutes == 10.0
