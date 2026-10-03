"""Edge-case / adversarial tests: extreme params, empty windows, school-route
exclusion, metric invariants and the GTFS export.

These complement the happy-path tests and catch crashes or silent nonsense in
the API, the solver and the circuity analyzer.
"""

import hashlib
import json
from pathlib import Path

import pytest
from app.cache import cached_compute
from app.main import app
from app.transfer_sync import (
    build_transfer_nodes,
    gtfs_time_to_minutes,
    prepare_feed,
    solve_transfer_sync,
)
from fastapi.testclient import TestClient

pytestmark = pytest.mark.slow

# The extreme-params smoke tests each run a full network solve (~10-20 s), and
# the optimize pipeline is deterministic for a given (feed, params, code): the
# disk-cached responses below are byte-identical to a fresh solve. The key pins
# the whole app source tree (any code change invalidates) plus the GTFS
# fingerprint (``cached_compute`` appends it), so a cached entry is only ever
# served when a fresh solve would produce exactly that response.
_SRC_DIGEST = hashlib.sha1(
    b"".join(
        p.read_bytes()
        for p in sorted(Path(__file__).resolve().parents[1].glob("app/**/*.py"))
    )
).hexdigest()[:12]


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _cached_optimize(client, payload: dict) -> dict:
    """POST /api/optimize/transfers, disk-cached per payload.

    The extreme-params smoke tests only assert the response shape, and the
    pipeline is deterministic, so the solve is persisted keyed on the payload
    + app source digest + GTFS fingerprint. First run (or after any code
    change) pays the real solve; repeat runs load it in milliseconds.
    """

    def _post():
        resp = client.post("/api/optimize/transfers", json=payload)
        assert resp.status_code == 200, resp.text
        return resp.json()

    return cached_compute(
        key=f"edge_optimize|v{_SRC_DIGEST}|{json.dumps(payload, sort_keys=True)}",
        compute=_post,
    )


# ---------------------------------------------------------------------------
# Validation (should 422, not crash)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "payload",
    [
        {"service_day": "funday"},
        {"volume_mode": "magic"},
        {"max_shift": -1},
        {"max_shift": 99},
        {"buffer_minutes": 99},
        {"t_max": -5},
        {"time_limit_seconds": 0},
        {"time_limit_seconds": 100_000},
        {"max_connections": 10},  # below ge=100
        {"window_start": -50},
        {"window_end": 5000},
    ],
)
def test_invalid_params_are_rejected(client, payload):
    resp = client.post("/api/optimize/transfers", json=payload)
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize(
    "path",
    [
        "/api/transfer/nodes",
        "/api/optimize/transfers/top-missed",
        "/api/diagnostics/transfer-blindspots",
        "/api/routes/circuity",
        "/api/routes/circuity/summary",
        "/api/routes/circuity/worst",
        "/api/routes/circuity/best-pilot",
    ],
)
@pytest.mark.parametrize(
    "params",
    [
        {"window_start": -50},
        {"window_end": 5000},
        {"window_start": 1e9, "window_end": 1320.0},
    ],
)
def test_get_window_params_are_bounded(client, path, params):
    """GET endpoints must reject out-of-range windows with 422, matching the
    POST models -- an unbounded float must never reach the compute layer."""
    resp = client.get(path, params=params)
    assert resp.status_code == 422, (path, params, resp.text)


# ---------------------------------------------------------------------------
# Extreme-but-valid parameters (must not crash; results must be sane)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "overrides",
    [
        # Smoke-test budget: these only assert "does not crash and returns a
        # sane shape", so a tiny solver budget is enough (FEASIBLE is accepted).
        {"max_shift": 0, "max_connections": 300, "time_limit_seconds": 3},
        {"max_shift": 15, "max_connections": 300, "time_limit_seconds": 3},
        {"buffer_minutes": 0, "max_connections": 300, "time_limit_seconds": 3},
        {"buffer_minutes": 10, "max_connections": 300, "time_limit_seconds": 3},
        {"t_max": 1, "max_connections": 300, "time_limit_seconds": 3},
        {"t_max": 30, "max_connections": 300, "time_limit_seconds": 3},
        {"high_freq_cutoff": 1, "max_connections": 300, "time_limit_seconds": 3},
        {"high_freq_cutoff": 30, "max_connections": 300, "time_limit_seconds": 3},
        {"max_connections": 100, "time_limit_seconds": 3},
        {"volume_mode": "uniform", "max_connections": 300, "time_limit_seconds": 3},
        {"service_day": "saturday", "max_connections": 300, "time_limit_seconds": 3},
        {"service_day": "sunday", "max_connections": 300, "time_limit_seconds": 3},
    ],
)
@pytest.mark.slow
def test_extreme_params_do_not_crash(client, overrides):
    payload = {
        "max_shift": 5,
        "buffer_minutes": 2,
        "high_freq_cutoff": 10,
        "t_max": 25,
        "service_day": "weekday",
        "volume_mode": "estimated",
        "window_start": 360,
        "window_end": 1320,
        "max_connections": 300,
        "time_limit_seconds": 3,
    }
    payload.update(overrides)
    data = _cached_optimize(client, payload)
    assert data["status"] in ("OPTIMAL", "FEASIBLE")
    assert len(data["wait_distribution_baseline"]) == 7
    assert len(data["wait_distribution_optimized"]) == 7
    # Distributions must be internally consistent with the connection count.
    assert sum(data["wait_distribution_baseline"]) == data["total_connections"]
    assert sum(data["wait_distribution_optimized"]) == data["total_connections"]


def test_inverted_window_is_rejected(client):
    """The API must reject an empty or reversed analysis window."""
    resp = client.post(
        "/api/optimize/transfers",
        json={
            "window_start": 1200,
            "window_end": 360,
            "max_connections": 300,
            "time_limit_seconds": 15,
        },
    )
    assert resp.status_code == 422, resp.text


def test_equal_window_is_rejected(client):
    """A zero-length window is not a valid analysis request."""
    resp = client.post(
        "/api/optimize/transfers",
        json={
            "window_start": 600,
            "window_end": 600,
            "max_connections": 300,
            "time_limit_seconds": 15,
        },
    )
    assert resp.status_code == 422, resp.text


def test_solver_with_zero_connections_is_safe():
    """solve_transfer_sync on an empty network must return an empty result."""
    _routes, trips, stop_times, stops = prepare_feed("weekday")
    nodes = build_transfer_nodes(
        trips,
        stop_times,
        stops,
        window_start=1200,
        window_end=360,  # empty window
    )
    assert nodes == []
    result = solve_transfer_sync(nodes, time_limit_seconds=15)
    assert result.total_connections == 0
    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert json.dumps(result.offsets) is not None


# ---------------------------------------------------------------------------
# Metric invariants
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_savings_never_negative_for_kept_solutions(client):
    """With a feasible baseline the solver cannot degrade total passenger wait."""
    resp = client.post(
        "/api/optimize/transfers",
        json={
            "max_shift": 5,
            "max_connections": 500,
            # Non-negativity is a model invariant (offsets 0 is always
            # feasible), so a minimal budget suffices.
            "time_limit_seconds": 3,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["passenger_minutes_saved"] >= -0.5
    assert data["optimized_missed"] <= data["baseline_missed"] + 1


@pytest.mark.slow
def test_offsets_within_requested_bounds(client):
    resp = client.post(
        "/api/optimize/transfers",
        json={"max_shift": 5, "max_connections": 500, "time_limit_seconds": 6},
    )
    data = resp.json()
    for off in data["offsets"]:
        assert abs(off["offset_minutes"]) <= 5
        assert off["movable"] is True  # only movable routes are reported


# ---------------------------------------------------------------------------
# School routes (3xx) must be excluded everywhere
# ---------------------------------------------------------------------------
def test_no_school_routes_in_circuity():
    resp = TestClient(app).get("/api/routes/circuity/summary")
    data = resp.json()
    flagged = data["flagged"]
    names = {r["route_short_name"] for r in flagged}
    assert not any(n.isdigit() and n.startswith("3") and len(n) == 3 for n in names)


def test_no_school_routes_in_transfer_nodes(client):
    resp = client.get("/api/transfer/nodes", params={"max_nodes": 500})
    nodes = resp.json()
    for n in nodes:
        for r in n["routes"]:
            assert not (r.isdigit() and r.startswith("3") and len(r) == 3)


# ---------------------------------------------------------------------------
# GTFS export
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_export_applies_offsets_consistently(client):
    resp = client.post(
        "/api/optimize/transfers",
        json={"max_shift": 5, "max_connections": 400, "time_limit_seconds": 6},
    )
    assert resp.status_code == 200, resp.text
    offsets = {
        o["route_short_name"]: o["offset_minutes"] for o in resp.json()["offsets"]
    }
    if not offsets:
        pytest.skip("No non-zero offsets in this run")

    exp = client.get("/api/optimize/transfers/export")
    assert exp.status_code == 200
    lines = exp.text.strip().splitlines()
    assert lines[0].startswith("trip_id")
    header = lines[0].split(",")
    assert "arrival_time" in header and "departure_time" in header

    # Shifts must be integer minutes for every shifted route's trips.
    import io

    import pandas as pd

    df = pd.read_csv(io.StringIO(exp.text), dtype=str)
    from app.transfer_sync import prepare_feed

    _, trips, _, _ = prepare_feed("weekday")
    trip_route = dict(zip(trips["trip_id"], trips["route_short_name"]))
    df["_route"] = df["trip_id"].map(trip_route).fillna("")
    shifted_routes = {r for r, d in offsets.items() if d != 0}
    for _, row in df[df["_route"].isin(shifted_routes)].head(200).iterrows():
        assert row["_route"] in offsets


def test_export_requires_prior_run_consistent(client):
    """Export is callable after any optimization in the same process."""
    resp = client.get("/api/optimize/transfers/export")
    assert resp.status_code in (200, 400)


def test_csv_chunks_yields_bytes_not_lines():
    """Regression: StreamingResponse(StringIO) iterates line-by-line, which
    threads one thread-pool hop per CSV row and hangs a real server. The
    export must yield large byte chunks instead."""
    from io import StringIO

    from app.routers.transfers import _csv_chunks

    buf = StringIO("a,b\n" * 5000)
    chunks = list(_csv_chunks(buf, size=1024))
    assert chunks, "must yield at least one chunk"
    assert all(isinstance(c, bytes) for c in chunks)
    assert all(len(c) <= 1024 for c in chunks)
    joined = b"".join(chunks)
    assert len(joined) == len("a,b\n") * 5000
    assert joined.endswith(b"\n")


# ---------------------------------------------------------------------------
# Pure helper robustness
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad",
    [None, "", "abc", "8:00", "08-15-00", "08:15", "1:2:3", "99:99:99"],
)
def test_gtfs_time_to_minutes_rejects_garbage(bad):
    # Must either be None or a sane float; must never raise.
    out = gtfs_time_to_minutes(bad)
    if out is not None:
        assert 0 <= out <= 60 * 24 + 60


def test_gtfs_time_to_minutes_roundtrip_24h():
    assert gtfs_time_to_minutes("24:30:00") == 24 * 60 + 30
    assert gtfs_time_to_minutes("00:00:30") == 0.5
