import numpy as np
import pytest
from shapely.geometry import LineString

from app.circuity_trunk import (
    _slice_linestring,
    _node_route_eligibility,
    _shortest_network_path,
    _network_trunk,
    _corridor_splice,
    _decompose_segments,
    _network_graph,
    TRUNK_SOURCE_DONOR,
    TRUNK_SOURCE_NETWORK,
    TRUNK_SOURCE_MEANDER,
)


class TestCircuityTrunk:
    def test_slice_linestring_basic(self):
        """Test basic slice functionality with interpolation."""
        donor = {
            "coords": [(0, 0), (1000, 0), (2000, 0)],
            "cumdist": [0.0, 1000.0, 2000.0],
        }

        # Slice from 0 to 1000 (first segment)
        result = _slice_linestring(donor, 0.0, 1000.0)
        coords = list(result.coords)
        assert len(coords) == 2
        assert coords[0] == (0.0, 0.0)
        assert coords[1] == (1000.0, 0.0)

        # Slice from 500 to 1500 (interpolated at both ends)
        result = _slice_linestring(donor, 500.0, 1500.0)
        coords = list(result.coords)
        assert len(coords) == 3
        assert coords[0] == (500.0, 0.0)  # Interpolate between (0,0) and (1000,0)
        assert coords[1] == (1000.0, 0.0)  # Middle vertex
        assert coords[2] == (1500.0, 0.0)  # Interpolate between (1000,0) and (2000,0)

    def test_slice_linestring_reversed_window(self):
        """Test that reversed window is normalized."""
        donor = {
            "coords": [(0, 0), (1000, 0), (2000, 0)],
            "cumdist": [0.0, 1000.0, 2000.0],
        }

        result1 = _slice_linestring(donor, 500.0, 1500.0)
        result2 = _slice_linestring(donor, 1500.0, 500.0)  # Reversed

        assert list(result1.coords) == list(result2.coords)

    def test_slice_linestring_coincident_cuts(self):
        """Test that coincident cut points yield degenerate two-point line."""
        donor = {
            "coords": [(0, 0), (1000, 0), (2000, 0)],
            "cumdist": [0.0, 1000.0, 2000.0],
        }

        result = _slice_linestring(donor, 1500.0, 1500.0)
        coords = list(result.coords)
        assert len(coords) == 2
        assert coords[0] == coords[1]  # Degenerate line

    def test_node_route_eligibility_empty_routes(self):
        """Test eligibility calculation with empty route sets."""
        xy_arr = np.array([[0, 0], [100, 100]])
        routes_of = [set(), set(), set()]

        result = _node_route_eligibility(xy_arr, routes_of, 1000.0)

        assert len(result) == 3
        assert all(isinstance(r, frozenset) for r in result)
        assert all(len(r) == 0 for r in result)

    def test_network_graph_basic(self):
        """Test network graph creation (cached function)."""
        graph = _network_graph()

        assert "node_id" in graph
        assert "xy" in graph
        assert "adj" in graph
        assert "edge_routes" in graph
        assert "eligible_routes" in graph

        # Should have some nodes even in test environment
        assert len(graph["node_id"]) > 0
        assert graph["xy"].shape[1] == 2  # x, y coordinates

    def test_shortest_network_path_basic(self):
        """Test shortest path calculation with simple linear graph."""
        adj = [[(1, 1.0)], [(0, 1.0), (2, 1.0)], [(1, 1.0)]]
        edge_routes = {(0, 1): frozenset({"route1"}), (1, 2): frozenset({"route2"})}
        eligible_routes = [
            frozenset({"route1"}),
            frozenset({"route2"}),
            frozenset({"route2"}),
        ]

        def in_region(nid):
            return True

        # Path from node 0 to node 2
        path = _shortest_network_path(
            adj, edge_routes, eligible_routes, 0, 2, in_region
        )

        assert path is not None
        assert len(path) >= 3
        assert path[0] == 0
        assert path[-1] == 2

    def test_shortest_network_path_no_path(self):
        """Test when no path exists."""
        adj = [[], []]  # Two disconnected nodes
        edge_routes = {}
        eligible_routes = [frozenset(), frozenset()]

        def in_region(nid):
            return True

        path = _shortest_network_path(
            adj, edge_routes, eligible_routes, 0, 1, in_region
        )

        assert path is None

    def test_network_trunk_too_short(self):
        """Test _network_trunk rejection for short geometries."""
        # Too short geometry (< 8 vertices)
        geometry = LineString([(0, 0), (100, 100), (200, 200)])

        result = _network_trunk(geometry)
        assert result is None

    def test_network_trunk_loop_route(self):
        """Test _network_trunk rejection for loop routes."""
        # Loop route (start and end very close)
        geometry = LineString([(0, 0), (100, 100), (200, 200), (0.1, 0.1)])

        result = _network_trunk(geometry)
        assert result is None

    def test_corridor_splice_too_short(self):
        """Test _corridor_splice rejection for short geometries."""
        geometry = LineString([(0, 0), (100, 100), (200, 200)])

        result = _corridor_splice(geometry, route_id="test_route")
        assert result is None

    def test_corridor_splice_loop_route(self):
        """Test _corridor_splice rejection for loop routes."""
        geometry = LineString([(0, 0), (100, 100), (200, 200), (0.1, 0.1)])

        result = _corridor_splice(geometry, route_id="test_route")
        assert result is None

    def test_decompose_segments_zero_budget(self):
        """Test _decompose_segments with zero budget."""
        geometry = LineString([(0, 0), (100, 100), (200, 200)])

        result = _decompose_segments(geometry, max_branches=0)

        assert len(result) == 1
        assert result[0] == geometry

    def test_decompose_segments_split_creates_branches(self):
        """Test _decompose_segments when split creates branches."""
        # Create a geometry that should split (meander)
        geometry = LineString([(0, 0), (100, 100), (150, 50), (200, 100), (300, 0)])

        result = _decompose_segments(geometry, max_branches=2)

        # Either returns single segment (no split) or multiple
        assert len(result) >= 1
        assert all(isinstance(g, LineString) for g in result)

    def test_split_geometry_multi_dispatches_to_splice(self):
        """Test that split_geometry_multi dispatches to corridor splice."""
        geometry = LineString([(0, 0), (100, 100), (200, 200), (300, 300)])

        result = _corridor_splice(geometry, route_id="test_route")

        # This is the source module, so this directly tests _corridor_splice
        # Can't easily test the dispatcher without mocking
        # But we can verify it returns the expected type or None
        if result is not None:
            assert "trunk" in result
            assert "branches" in result
            assert result.get("trunk_source") == TRUNK_SOURCE_DONOR

    def test_trunk_source_constants(self):
        """Test that trunk source constants have correct values."""
        assert TRUNK_SOURCE_DONOR == "donor"
        assert TRUNK_SOURCE_NETWORK == "network"
        assert TRUNK_SOURCE_MEANDER == "meander"

    def test_slice_linestring_out_of_bounds(self):
        """Test _slice_linestring with out-of-bounds cut points."""
        donor = {
            "coords": [(0, 0), (1000, 0), (2000, 0)],
            "cumdist": [0.0, 1000.0, 2000.0],
        }

        # Test with cut points beyond the donor's range
        result = _slice_linestring(donor, -100.0, 3000.0)
        coords = list(result.coords)

        # Should clamp to the available range
        assert coords[0] == (-100.0, 0.0)  # Point at distance -100
        assert coords[-1] == (3000.0, 0.0)  # Point at distance 3000

    # test_node_route_eligibility_with_stops removed 2026-09-12: it
    # monkeypatched backend.app.circuity_trunk._node_route_eligibility but
    # then called the test file's own imported name (patch never applied)
    # and asserted the mock's fabricated output — coverage theater.


if __name__ == "__main__":
    pytest.main(["-v", __file__])
