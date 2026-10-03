import os
import tempfile
import pytest
from unittest.mock import patch
import sys

# Add the backend directory to the path so we can import the app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.routers.public_leaderboard as pl
from app.routers.public_leaderboard import compute_leaderboard


@pytest.fixture(autouse=True)
def _reset_leaderboard_cache():
    """Clear the ROUTER's leaderboard cache before each test.

    P0.3: the old pattern (`global _leaderboard_cache; _leaderboard_cache =
    None` on a from-imported name) rebound the TEST module's global and never
    cleared the router's cache — the second test could read the first test's
    CSV. It only "passed" under xdist because each worker process starts with
    a fresh cache (worker-assignment roulette). Resetting the module attribute
    is the actual fix; no production change.
    """
    pl._leaderboard_cache = None
    yield
    pl._leaderboard_cache = None


def test_public_leaderboard_endpoint():
    """Test the public leaderboard endpoint with a tiny synthetic CSV."""

    # Create a tiny synthetic CSV with known values
    # We want to test:
    # 1. A route that is clearly worst (high early share)
    # 2. A route with n<1000 (should go to small_n list)
    # 3. The network row calculation
    # 4. Early boundary -2 exclusive (lateness_minutes = -2 should NOT be early)

    csv_content = "route_short_name,lateness_minutes\n"

    csv_content += """51,-5
51,-5
51,-5
51,-5
51,-5
51,0
51,0
51,0
51,0
51,0
52,-1
52,-1
52,-1
52,-1
52,-1
52,0
52,0
52,0
52,0
52,0
99,-10
99,-10
"""

    # Write to a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_csv_path = f.name

    try:
        # Cache reset happens in the autouse fixture (the old inline
        # `global _leaderboard_cache` was a no-op on the router's cache).

        # Mock the environment variable to point to our test CSV
        with patch.dict(os.environ, {"MIWAY_LEADERBOARD_SAMPLE": temp_csv_path}):
            # Compute the leaderboard
            result = compute_leaderboard()

            # Check the structure
            assert "generated_at" in result
            assert "basis" in result
            assert "routes" in result
            assert "network" in result
            assert "small_n" in result

            # Check basis
            assert (
                result["basis"]["source"]
                == "lateness-sample-250k.csv (Zenodo DOI 10.5281/zenodo.22820448)"
            )
            assert result["basis"]["n"] == 250000  # This is hardcoded in the basis
            assert result["basis"]["window"] == "2026-08-23..2026-09-15"
            assert result["basis"]["definition"] == "early = lateness_minutes < -2"

            # Check routes (should be sorted worst-first by early_share among routes with n>=1000)
            # In our test data:
            # Route 51: 5 early out of 10 total = 0.5 early share (but wait, we have 10 rows for 51: 5 at -5, 5 at 0 -> 5 early)
            # Actually, let's recount: 51 has 5 rows at -5 (early) and 5 rows at 0 (not early) = 5/10 = 0.5
            # Route 52: 5 rows at -1 (NOT early because -1 >= -2) and 5 rows at 0 = 0/10 = 0.0
            # Route 99: 2 rows at -10 (early) and 0 rows at other values = 2/2 = 1.0 early share
            #
            # But wait, we only have 2 rows for route 99, so n=2 which is < 1000, so it should go to small_n
            # Route 51: n=10, early=5, share=0.5
            # Route 52: n=10, early=0, share=0.0
            #
            # So routes should have only route 51 (since 52 also has n=10 >= 1000, but we need to check)
            # Actually both 51 and 52 have n=10 which is < 1000? No, 10 is less than 1000, so both should go to small_n
            # Let me adjust the test data to have more rows for some routes...

            # Let me recalculate with the actual data:
            # Route 51: 5 rows at -5 (early), 5 rows at 0 (not early) -> 5 early, 5 not early -> n=10, early_share=0.5
            # Route 52: 5 rows at -1 (NOT early because early = lateness_minutes < -2, so -1 is NOT < -2), 5 rows at 0 -> 0 early, 10 not early -> n=10, early_share=0.0
            # Route 99: 2 rows at -10 (early), 0 rows at other values -> 2 early, 0 not early -> n=2, early_share=1.0
            #
            # Since n=10 and n=2 are both < 1000, ALL routes should go to small_n list
            # The routes array should be empty for n>=1000 routes

            # Actually, let me check the requirement again:
            # "sorted worst-first by early_share among routes with n>=1000, plus a "network" row and a "small_n" list of routes with n<1000"
            #
            # So if no routes have n>=1000, the routes array should be empty
            # And small_n should contain all routes

            # With our current test data, all routes have n<1000, so:
            assert len(result["routes"]) == 0  # No routes with n>=1000
            assert set(result["small_n"]) == {
                "51",
                "52",
                "99",
            }  # All routes go to small_n

            # Check network row (overall early share)
            # Total trips: 10 + 10 + 2 = 22
            # Total early: 5 + 0 + 2 = 7
            # Network early share: 7/22 ≈ 0.318
            assert abs(result["network"]["early_share"] - 7 / 22) < 0.001
            assert result["network"]["n"] == 22

    finally:
        # Clean up the temporary file
        os.unlink(temp_csv_path)


def test_public_leaderboard_with_larger_routes():
    """Test with some routes having n>=1000 to verify the sorting and separation logic."""

    # Create test data where:
    # Route 100: n=1500, early_share=0.6 (should be in routes, worst first)
    # Route 200: n=1200, early_share=0.4 (should be in routes)
    # Route 300: n=800, early_share=0.5 (should be in small_n despite high share)
    # Route 400: n=50, early_share=0.1 (should be in small_n)

    csv_content = "route_short_name,lateness_minutes\n"

    # Route 100: 1500 rows, 900 early (60%), 600 not early
    csv_content += "\n".join(["100,-5"] * 900)  # early
    csv_content += "\n"
    csv_content += "\n".join(["100,0"] * 600)  # not early
    csv_content += "\n"

    # Route 200: 1200 rows, 480 early (40%), 720 not early
    csv_content += "\n".join(["200,-5"] * 480)  # early
    csv_content += "\n"
    csv_content += "\n".join(["200,0"] * 720)  # not early
    csv_content += "\n"

    # Route 300: 800 rows, 400 early (50%), 400 not early (n<1000 -> small_n)
    csv_content += "\n".join(["300,-5"] * 400)  # early
    csv_content += "\n"
    csv_content += "\n".join(["300,0"] * 400)  # not early
    csv_content += "\n"

    # Route 400: 50 rows, 5 early (10%), 45 not early (n<1000 -> small_n)
    csv_content += "\n".join(["400,-5"] * 5)  # early
    csv_content += "\n"
    csv_content += "\n".join(["400,0"] * 45)  # not early
    csv_content += "\n"

    # Write to a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_csv_path = f.name

    try:
        # Cache reset happens in the autouse fixture (the old inline
        # `global _leaderboard_cache` was a no-op on the router's cache).

        # Mock the environment variable to point to our test CSV
        with patch.dict(os.environ, {"MIWAY_LEADERBOARD_SAMPLE": temp_csv_path}):
            # Compute the leaderboard
            result = compute_leaderboard()

            # Check that routes are sorted worst-first by early_share for n>=1000
            # Route 100: early_share=0.6
            # Route 200: early_share=0.4
            # So route 100 should come first, then route 200
            assert len(result["routes"]) == 2
            assert result["routes"][0]["route"] == "100"
            assert result["routes"][0]["early_share"] == 0.6
            assert result["routes"][0]["n"] == 1500
            assert result["routes"][1]["route"] == "200"
            assert result["routes"][1]["early_share"] == 0.4
            assert result["routes"][1]["n"] == 1200

            # Check small_n list (routes with n<1000)
            assert set(result["small_n"]) == {"300", "400"}

            # Check network row
            # Total trips: 1500 + 1200 + 800 + 50 = 3550
            # Total early: 900 + 480 + 400 + 5 = 1785
            # Network early share: 1785/3550 ≈ 0.5028
            expected_network_share = 1785 / 3550
            assert (
                abs(result["network"]["early_share"] - expected_network_share) < 0.001
            )
            assert result["network"]["n"] == 3550

    finally:
        # Clean up the temporary file
        os.unlink(temp_csv_path)


def test_early_boundary_exclusive():
    """Test that the early boundary is exclusive: lateness_minutes = -2 is NOT early."""

    # Create test data where:
    # Route 999:
    #   -3: early (since -3 < -2)
    #   -2: NOT early (since -2 is NOT < -2)
    #   -1: NOT early (since -1 is NOT < -2)
    #   0: NOT early

    csv_content = """route_short_name,lateness_minutes
999,-3
999,-2
999,-1
999,0
"""

    # Write to a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_csv_path = f.name

    try:
        # Cache reset happens in the autouse fixture (the old inline
        # `global _leaderboard_cache` was a no-op on the router's cache).

        # Mock the environment variable to point to our test CSV
        with patch.dict(os.environ, {"MIWAY_LEADERBOARD_SAMPLE": temp_csv_path}):
            # Compute the leaderboard
            result = compute_leaderboard()

            # Route 999 should have:
            #   n=4
            #   early=1 (only the -3 row)
            #   early_share=0.25
            assert len(result["routes"]) == 0  # n=4 < 1000
            assert result["small_n"] == ["999"]
            assert result["network"]["n"] == 4
            assert result["network"]["early_share"] == 0.25

    finally:
        # Clean up the temporary file
        os.unlink(temp_csv_path)


if __name__ == "__main__":
    # Run the tests
    test_public_leaderboard_endpoint()
    test_public_leaderboard_with_larger_routes()
    test_early_boundary_exclusive()
    print("All tests passed!")
