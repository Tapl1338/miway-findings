"""FastAPI integration tests against the live app (TestClient)."""

from types import SimpleNamespace

import pytest
from app.main import app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["feed"]["routes"] > 20
    assert data["feed"]["stop_times"] > 100_000


def test_circuity_endpoint(client):
    resp = client.get("/api/routes/circuity")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 20
    assert data["metadata"]["flag_threshold"] == 1.4


def test_circuity_summary_endpoint(client):
    resp = client.get("/api/routes/circuity/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["threshold"] == 1.4
    assert isinstance(data["flagged"], list)


def test_transfer_nodes_endpoint(client):
    resp = client.get("/api/transfer/nodes", params={"max_nodes": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 10
    if data:
        assert "stop_name" in data[0]
        assert "friction_score" in data[0]


def test_transfer_nodes_late_night_preset(client):
    """period=late_night resolves to the late-night window (not just a label)."""
    resp = client.get(
        "/api/transfer/nodes",
        params={"max_nodes": 10, "period": "late_night"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_top_missed_late_night_preset(client):
    """period=late_night uses the preset's wider t_max (30) and window.

    All-day's search horizon is t_max + 2*max_shift = 22 min; late night widens
    the cap to 30, so a ranked wait can legitimately exceed 22 min -- something
    the all-day ranking can never show. Waits stay within the wider horizon
    (t_max 30 + 2*max_shift 5 = 40).
    """
    resp = client.get(
        "/api/optimize/transfers/top-missed",
        params={"period": "late_night", "limit": 50},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["period"] == "late_night"
    assert isinstance(data["connections"], list)
    assert all(r["wait_minutes"] <= 40.0 + 1e-6 for r in data["connections"])
    assert any(r["wait_minutes"] > 22.0 for r in data["connections"]), (
        "late-night t_max=30 must admit waits the all-day 22-min horizon cannot"
    )


def test_top_missed_unknown_period(client):
    resp = client.get(
        "/api/optimize/transfers/top-missed", params={"period": "overnight"}
    )
    assert resp.status_code == 422


def test_top_missed_shiftable_filter(client):
    """``shiftable=false`` must surface only un-fixable waits via the API.

    The Home screen's un-fixable section calls this endpoint with
    ``shiftable=false``; every returned row must be past the shift budget.
    """
    resp = client.get(
        "/api/optimize/transfers/top-missed",
        params={"period": "all_day", "limit": 5, "shiftable": "false"},
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()["connections"]
    assert rows, "the un-fixable lens must return waits past the shift budget"
    for r in rows:
        assert r["shiftable_within_max"] is False, (
            f"shiftable=false returned a rescueable row: "
            f"{r['route_i']} -> {r['route_j']} at {r['stop_name']}"
        )
        assert r["wait_minutes"] > 22.0 + 1e-6, (
            "a shiftable=false wait must exceed t_max + 2*max_shift (22)"
        )


def test_top_missed_shiftable_true(client):
    """``shiftable=true`` narrows the ranking to the rescueable waits only."""
    resp = client.get(
        "/api/optimize/transfers/top-missed",
        params={"period": "all_day", "limit": 5, "shiftable": "true"},
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()["connections"]
    assert rows
    assert all(r["shiftable_within_max"] for r in rows)


def test_optimize_unknown_period(client):
    resp = client.post(
        "/api/optimize/transfers",
        json={
            "max_shift": 5,
            "buffer_minutes": 2,
            "high_freq_cutoff": 10,
            "t_max": 25,
            "service_day": "weekday",
            "volume_mode": "uniform",
            "period": "overnight",
        },
    )
    assert resp.status_code == 422


@pytest.mark.slow
def test_optimize_endpoint_small(client):
    """POST /api/optimize/transfers returns a valid OptimizeResponse."""
    payload = {
        "max_shift": 5,
        "buffer_minutes": 2,
        "high_freq_cutoff": 10,
        "t_max": 25,
        "service_day": "weekday",
        "volume_mode": "estimated",
        "max_connections": 800,
        # Shape/consistency assertions hold for any feasible solution.
        "time_limit_seconds": 5,
    }
    resp = client.post("/api/optimize/transfers", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] in ("OPTIMAL", "FEASIBLE")
    assert data["total_connections"] == 800
    assert len(data["wait_distribution_baseline"]) == 7
    assert len(data["wait_distribution_optimized"]) == 7
    assert data["updated_stop_times_available"] is True
    assert data["ridership_impact"]["projected_ridership_pct"] >= 0.0
    assert data["ridership_impact"]["methodology"]
    # Per-route winners/losers breakdown is present and internally consistent.
    assert data["route_impacts"]
    for r in data["route_impacts"]:
        assert r["route_short_name"]
        assert r["connections"] > 0
        assert r["worse_off"] == (r["worse_off_connections"] > 0)
    deltas = [r["delta_minutes"] for r in data["route_impacts"]]
    assert deltas == sorted(deltas)


def test_optimize_validates_params(client):
    resp = client.post(
        "/api/optimize/transfers",
        json={"max_shift": 99, "service_day": "notaday"},
    )
    assert resp.status_code == 422  # pydantic validation failure


def test_optimize_defaults_match_all_day_contract():
    """Direct API requests use the same all-day window and cap as the dashboard."""
    from app.models import OptimizeRequest

    req = OptimizeRequest()
    assert req.window_start == 360.0
    assert req.window_end == 1320.0
    assert req.max_connections == 6000


def test_optimize_rejects_reversed_window(client):
    resp = client.post(
        "/api/optimize/transfers",
        json={"window_start": 1200, "window_end": 360},
    )
    assert resp.status_code == 422


def test_travel_rejects_reversed_window():
    from app.models import TravelCompareRequest, TravelPoint
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TravelCompareRequest(
            origin=TravelPoint(mode="stop", stop_id="a"),
            destination=TravelPoint(mode="stop", stop_id="b"),
            depart_at=600,
            window_start=1200,
            window_end=360,
        )


def test_export_requires_prior_run(client):
    resp = client.get("/api/optimize/transfers/export")
    # Either 400 (no run yet in this process) or 200 if a test ran first.
    assert resp.status_code in (200, 400)


def test_export_skips_noop_latest_run(client):
    """A later run that shifted nothing must not block exporting a valid plan.

    The export reads the latest run *with* offsets: a smoke solve with a tiny
    connection cap writes an empty-offsets row on top of a real plan, and the
    old "latest run wins" logic 400'd "Run an optimization first" despite a
    valid export existing.
    """
    import app.state_store as store

    store.save_run(
        service_day="weekday", params={"period": "midday"}, offsets={"42": 3}
    )
    store.save_run(
        service_day="weekday",
        params={"period": "midday", "max_connections": 300},
        offsets={},
    )
    # The store now has a valid plan followed by a no-op run; export must
    # still return the CSV, not the "run first" error.
    resp = client.get("/api/optimize/transfers/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.text.splitlines()[0].startswith("trip_id,arrival_time")


@pytest.mark.slow
def test_optimize_nondefault_export_applies_offsets(client, tmp_path, monkeypatch):
    """A real solve with non-default timing params caps every shift at max_shift,
    and the export CSV applies exactly those offsets to trip times.

    Regression: the export pipeline was verified by hand for default settings,
    but nothing automated proved that a non-default solve's offsets reach the
    CSV. With ``max_shift=3`` a 5-minute shift must never appear, and every
    shifted trip's departure must move by precisely its route's offset.
    """
    from app import config as local_config
    from app import state_store

    # Isolate the run store: this solve must not clobber the live app's
    # latest-run slot (the export endpoint reads it), and concurrent solves
    # must not clobber this test's assertion.
    monkeypatch.setattr(local_config, "STATE_DB", tmp_path / "state.db")

    payload = {
        "max_shift": 3,
        "buffer_minutes": 4,
        "high_freq_cutoff": 10,
        "t_max": 25,
        "service_day": "weekday",
        "volume_mode": "estimated",
        "window_start": 540.0,  # midday window
        "window_end": 900.0,
        "max_connections": 800,
        "time_limit_seconds": 8,
        "min_layover_minutes": 8,
    }
    resp = client.post("/api/optimize/transfers", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] in ("OPTIMAL", "FEASIBLE")

    offsets = {o["route_short_name"]: o["offset_minutes"] for o in data["offsets"]}
    assert offsets, (
        "solve must shift at least one route for the export to mean anything"
    )
    assert all(abs(v) <= 3 for v in offsets.values()), (
        "every shift must respect the non-default max_shift=3 cap"
    )

    # The persisted run must record the non-default params (buffer 4, shift 3).
    run = state_store.get_latest_run()
    assert run is not None
    assert run["params"]["max_shift"] == 3.0
    assert run["params"]["buffer_minutes"] == 4.0

    # Export must stream the CSV with exactly those offsets applied.
    resp = client.get("/api/optimize/transfers/export")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")

    import csv
    from io import StringIO

    rows = list(csv.DictReader(StringIO(resp.text)))
    assert rows, "export CSV must not be empty"
    assert rows[0]["trip_id"]  # header is trip_id,arrival_time,...
    exported_first_dep = {
        r["trip_id"]: r["departure_time"] for r in rows if r["stop_sequence"] == "1"
    }

    from app.transfer_sync import prepare_feed

    trips, stop_times = prepare_feed("weekday")[1:3]
    first = stop_times[stop_times["stop_sequence"] == 1]
    orig_first_dep = dict(zip(first["trip_id"], first["departure_time"]))

    def _dep_min(t: str) -> int:
        h, m, _ = t.split(":")
        return int(h) * 60 + int(m)

    checked = 0
    for route, delta in sorted(
        offsets.items(), key=lambda kv: abs(kv[1]), reverse=True
    ):
        if delta == 0:
            continue
        # First trip of the route whose first stop departs after 01:00, so a
        # -3 min shift can never clamp against the 00:00 boundary.
        route_trips = trips.loc[trips["route_short_name"] == route, "trip_id"]
        trip = next(
            (
                t
                for t in route_trips
                if t in orig_first_dep and _dep_min(orig_first_dep[t]) >= 60
            ),
            None,
        )
        if trip is None:
            continue
        orig = orig_first_dep[trip]
        # An integer-minute offset preserves the seconds exactly.
        expected = (
            f"{(_dep_min(orig) + delta) // 60:02d}:{(_dep_min(orig) + delta) % 60:02d}:"
            + orig.split(":")[2]
        )
        assert trip in exported_first_dep, f"trip {trip} missing from export"
        got = exported_first_dep[trip]
        assert got == expected, (
            f"route {route} offset {delta:+d}: trip {trip} departed {orig} "
            f"but export shows {got}, expected {expected}"
        )
        checked += 1
        if checked >= 3:
            break
    assert checked >= 1, "no shifted route had a usable trip to verify"


def test_equity_report_endpoint(client):
    """Serve the last generated equity report (winners/losers + wards) or a
    clear 404 telling the operator to generate it — never a crash."""
    resp = client.get("/api/equity/report")
    if resp.status_code == 404:
        assert "equity_report.py" in resp.json()["detail"]
        return
    assert resp.status_code == 200
    data = resp.json()
    for key in ("winners", "losers", "route_losers", "passenger_minutes_saved"):
        assert key in data
    for row in data["winners"]:
        assert "lat" in row and "lon" in row and "delta_minutes" in row


def _travel_req(**over):
    from app import config as _config
    from app.models import TravelCompareRequest, TravelPoint

    base = dict(
        origin=TravelPoint(mode="stop", stop_id="0001"),
        destination=TravelPoint(mode="point", lat=43.594111, lon=-79.646905),
        depart_at=600.0,
        service_day="weekday",
        max_shift=5.0,
        buffer_minutes=2.0,
        high_freq_cutoff=10.0,
        t_max=_config.T_MAX,
        volume_mode="estimated",
        window_start=360.0,
        window_end=1320.0,
        max_connections=6000,
    )
    base.update(over)
    return TravelCompareRequest(**base)


def test_travel_opt_cache_key_distinguishes_solver_params(monkeypatch):
    """Two requests that differ only in a solver param must not collide in the
    optimizer cache (regression: time_limit_seconds / min_layover_minutes were
    omitted from the key, so the first solve's result was served for the
    second request)."""
    from app.routers import travel as travel_mod

    travel_mod._OPT_CACHE.clear()
    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(travel_mod, "run_full_optimization", fake_run)

    slow = _travel_req(time_limit_seconds=30)
    fast = _travel_req(time_limit_seconds=120)
    assert travel_mod._opt_key(slow) != travel_mod._opt_key(fast)
    travel_mod._run_optimizer_cached(slow)
    travel_mod._run_optimizer_cached(fast)
    assert len(calls) == 2  # both computed; no cross-param cache hit

    with_layover = _travel_req(min_layover_minutes=8.0)
    assert travel_mod._opt_key(fast) != travel_mod._opt_key(with_layover)
    travel_mod._run_optimizer_cached(with_layover)
    assert len(calls) == 3

    # The fake was actually called with both new parameters.
    assert {"time_limit_seconds", "min_layover_minutes"}.issubset(calls[0])
    travel_mod._OPT_CACHE.clear()


def test_travel_opt_cache_lru_evicts_oldest(monkeypatch):
    """Past _OPT_CACHE_MAX the least-recently-used entry is evicted -- not a
    full cache clear, which dropped every warm result on the 17th distinct
    settings set."""
    from app.routers import travel as travel_mod

    travel_mod._OPT_CACHE.clear()

    def fake_run(**kwargs):
        return object()

    monkeypatch.setattr(travel_mod, "run_full_optimization", fake_run)

    for i in range(1, travel_mod._OPT_CACHE_MAX + 5):
        travel_mod._run_optimizer_cached(_travel_req(high_freq_cutoff=float(i)))

    assert len(travel_mod._OPT_CACHE) == travel_mod._OPT_CACHE_MAX
    assert (
        travel_mod._opt_key(_travel_req(high_freq_cutoff=1.0))
        not in travel_mod._OPT_CACHE
    )
    last = travel_mod._opt_key(
        _travel_req(high_freq_cutoff=float(travel_mod._OPT_CACHE_MAX + 4))
    )
    assert last in travel_mod._OPT_CACHE

    # Touching a surviving entry refreshes its recency: evicts the next-oldest.
    travel_mod._run_optimizer_cached(_travel_req(high_freq_cutoff=2.0))
    travel_mod._run_optimizer_cached(
        _travel_req(high_freq_cutoff=float(travel_mod._OPT_CACHE_MAX + 5))
    )
    assert len(travel_mod._OPT_CACHE) == travel_mod._OPT_CACHE_MAX
    assert (
        travel_mod._opt_key(_travel_req(high_freq_cutoff=2.0)) in travel_mod._OPT_CACHE
    )
    travel_mod._OPT_CACHE.clear()


def test_travel_headways_memoized_on_feed_frames(monkeypatch):
    """The per-request compute_route_headways recompute is memoized on the
    prepared-feed frames (warm-path fix): same frames -> one computation and
    the same dict object; a different feed recomputes."""
    from app.routers import travel as travel_mod
    from app.transfer_sync import prepare_feed

    travel_mod._HEADWAYS_MEMO.clear()
    calls = []

    def fake_headways(trips, stop_times):
        calls.append((id(trips), id(stop_times)))
        return {"1": 10.0}

    monkeypatch.setattr(travel_mod, "compute_route_headways", fake_headways)

    _r, trips, stop_times, _s = prepare_feed("weekday")
    h1 = travel_mod._compute_headways_cached(trips, stop_times)
    h2 = travel_mod._compute_headways_cached(trips, stop_times)
    assert h1 is h2
    assert len(calls) == 1  # recomputed once, then served from the memo

    _r2, trips2, stop_times2, _s2 = prepare_feed("saturday")
    h3 = travel_mod._compute_headways_cached(trips2, stop_times2)
    assert h3 is not h1
    assert len(calls) == 2  # different frames -> recompute

    # Same dict object shared across callers is safe: read-only downstream.
    assert h1 is travel_mod._compute_headways_cached(trips, stop_times)
    assert len(calls) == 2
    travel_mod._HEADWAYS_MEMO.clear()


def test_travel_compare_endpoint_warm_path_identical(client, monkeypatch):
    """Endpoint-level regression for the warm-path memoization: a repeat
    POST /api/travel/compare returns byte-identical itineraries with no
    network rebuild and no headways recompute, and a different journey on the
    same feed also serves from the memos. Also covers the arrive_by mode
    (reverse-network path -- the reversal itself is memoized, so repeats
    re-reverse nothing) and a point-mode origin (walk access) -- both must
    keep serving from the memos with zero additional builds. (No other test
    exercises the endpoint itself; the optimizer solve is stubbed to keep it
    fast.)"""
    from app import routing as routing_mod
    from app.routers import travel as travel_mod
    from app.transfer_sync import OptimizationResult

    stub = OptimizationResult(
        offsets={"1": 2, "103": -1},
        movable_routes=["1", "103"],
        frozen_routes=[],
        anchor_route=None,
        baseline_avg_wait=12.0,
        optimized_avg_wait=10.5,
        baseline_missed=100,
        optimized_missed=90,
        total_connections=6000,
        total_kept=5000,
        passenger_minutes_saved=1234.5,
        connection_health=0.9,
        wait_distribution_baseline=[1, 2, 3],
        wait_distribution_optimized=[1, 2, 3],
        nodes=[],
        status="optimal",
    )
    monkeypatch.setattr(travel_mod, "run_full_optimization", lambda **kw: stub)

    builds = []
    real_build = routing_mod.build_network

    def spy_build(stop_times, trips_df, stops, offsets=None):
        builds.append("None" if offsets is None else "offsets")
        return real_build(stop_times, trips_df, stops, offsets)

    monkeypatch.setattr(routing_mod, "build_network", spy_build)

    headway_calls = []
    real_headways = travel_mod.compute_route_headways

    def spy_headways(trips, stop_times):
        headway_calls.append(1)
        return real_headways(trips, stop_times)

    monkeypatch.setattr(travel_mod, "compute_route_headways", spy_headways)

    reversal_calls = []
    real_reverse = routing_mod._reverse_network

    def spy_reverse(net):
        reversal_calls.append(1)
        return real_reverse(net)

    monkeypatch.setattr(routing_mod, "_reverse_network", spy_reverse)

    travel_mod._OPT_CACHE.clear()
    travel_mod._HEADWAYS_MEMO.clear()
    routing_mod._BUILD_NET_MEMO.clear()
    routing_mod._REV_NET_MEMO.clear()
    try:
        payload = {
            "origin": {"mode": "stop", "stop_id": "0085", "name": "City Centre"},
            "destination": {"mode": "stop", "stop_id": "0001", "name": "Erin Mills"},
            "depart_at": 1020.0,
            "max_transfers": 4,
            "service_day": "weekday",
            "volume_mode": "estimated",
        }

        r1 = client.post("/api/travel/compare", json=payload)
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["baseline"] is not None and body1["optimized"] is not None
        assert body1["optimizer"]["status"] == "optimal"
        assert body1["optimizer"]["offsets_count"] == 2
        assert body1["savings_minutes"] is not None
        # First request: exactly one build per offset mode + one headways compute.
        assert builds == ["None", "offsets"]
        assert len(headway_calls) == 1

        # Repeat request: memoized warm path -> identical itineraries, no
        # rebuild, no recompute.
        r2 = client.post("/api/travel/compare", json=payload)
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["baseline"] == body1["baseline"]
        assert body2["optimized"] == body1["optimized"]
        assert body2["optimizer"] == body1["optimizer"]
        assert body2["savings_minutes"] == body1["savings_minutes"]
        assert len(builds) == 2
        assert len(headway_calls) == 1

        # Different journey, same feed/settings: still no rebuild or recompute.
        r3 = client.post(
            "/api/travel/compare",
            json={**payload, "destination": {"mode": "stop", "stop_id": "0364"}},
        )
        assert r3.status_code == 200
        body3 = r3.json()
        assert body3["baseline"] is not None and body3["optimized"] is not None
        assert body3["baseline"] != body1["baseline"]  # genuinely different journey
        assert len(builds) == 2
        assert len(headway_calls) == 1

        # arrive_by mode: reverse-network path on the memoized base network
        # (the reversal itself is per-call, but the base build is memoized).
        arrive_payload = {k: v for k, v in payload.items() if k != "depart_at"}
        arrive_payload["arrive_by"] = 1320.0
        r4 = client.post("/api/travel/compare", json=arrive_payload)
        assert r4.status_code == 200
        body4 = r4.json()
        assert body4["mode"] == "arrive_by"
        assert body4["baseline"] is not None and body4["optimized"] is not None
        assert len(builds) == 2
        assert len(headway_calls) == 1
        assert reversal_calls == [1, 1]  # one time-reversal per base network
        r4b = client.post("/api/travel/compare", json=arrive_payload)
        body4b = r4b.json()
        assert body4b["baseline"] == body4["baseline"]
        assert body4b["optimized"] == body4["optimized"]
        assert len(builds) == 2
        assert len(headway_calls) == 1
        assert len(reversal_calls) == 2  # memoized: no re-reversal on repeat

        # point-mode origin (walk access) on the same feed: still memoized.
        point_payload = {
            **payload,
            "origin": {
                "mode": "point",
                "lat": 43.593731,
                "lon": -79.647476,
                "name": "City Centre area",
            },
        }
        r5 = client.post("/api/travel/compare", json=point_payload)
        assert r5.status_code == 200
        body5 = r5.json()
        assert body5["baseline"] is not None and body5["optimized"] is not None
        assert len(builds) == 2
        assert len(headway_calls) == 1
        r5b = client.post("/api/travel/compare", json=point_payload)
        body5b = r5b.json()
        assert body5b["baseline"] == body5["baseline"]
        assert body5b["optimized"] == body5["optimized"]
        assert len(builds) == 2
        assert len(headway_calls) == 1
    finally:
        travel_mod._OPT_CACHE.clear()
        travel_mod._HEADWAYS_MEMO.clear()
        routing_mod._BUILD_NET_MEMO.clear()
        routing_mod._REV_NET_MEMO.clear()


def test_executive_brief_endpoint(client, tmp_path, monkeypatch):
    # Point the brief at a synthetic actuals CSV so the realtime-validation
    # stamp is deterministic (the bundled capture predates the horizon column
    # and is honestly excluded from the actuals-only analysis).
    import pandas as pd
    from app.routers import brief

    lat = pd.DataFrame(
        {
            "route_short_name": ["1", "1", "2", "2", "3"],
            "stop_id": ["a", "b", "a", "c", "d"],
            "dep_time_min": [410.0, 415.0, 420.0, 425.0, 430.0],
            "lateness_minutes": [1.0, -0.5, 2.0, 3.0, 1.5],
            "horizon_minutes": [-5.0, -2.0, -4.0, -3.0, -1.0],
        }
    )
    lat_csv = tmp_path / "obs_lateness.csv"
    lat.to_csv(lat_csv, index=False)
    monkeypatch.setattr(brief, "_LATENESS_CSV", lat_csv)

    resp = client.get("/api/report/executive-brief")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service_day"] == "weekday"
    assert isinstance(data["missed_transfers"], list)
    assert 3 <= len(data["missed_transfers"]) <= 5
    top = data["missed_transfers"][0]
    # Every row carries the councillor-facing economics.
    for key in (
        "est_riders_per_day",
        "rider_minutes_per_year",
        "fix_kind",
        "fix_net_annual_cost",
        "route_i_boardings",
        "route_j_boardings",
    ):
        assert key in top, key
    # The fix verdict must be internally honest: a zero net cost only pairs
    # with a re-phase label, and a needs-service verdict carries no cost.
    if top["fix_net_annual_cost"] == 0.0:
        assert "re-phase" in top["fix_kind"]
    else:
        assert top["fix_net_annual_cost"] is None
        assert "needs added service" in top["fix_kind"]
    assert isinstance(data["corridor_seams"], list)
    for seam in data["corridor_seams"]:
        assert seam["gap_km"] >= 0.0
        assert seam["est_annual_extension_cost"] >= 0
        assert "cost_note" in seam
    assert data["realtime_validation"]["available"] is True
    # The trust check on the feed's holiday markings rides along with the
    # brief: clean feed -> ok=true, empty warnings.
    assert data["holiday_check"]["ok"] is True
    assert data["holiday_check"]["warnings"] == []
    # Peer open-data comparison: every major Canadian agency listed must be
    # more open than MiWay's own row (that's the point of the section), and
    # each peer row carries a working-format access note.
    po = data["peer_open_data"]
    assert len(po["peers"]) >= 3
    assert all(p["granularity"] and p["format"] for p in po["peers"])
    assert "Not published" in po["miway"]["format"]
    assert "TransLink" in po["note"]


def test_executive_brief_holiday_check_warns(client, tmp_path, monkeypatch):
    """When the feed omits an in-window statutory holiday the brief must
    carry ok=false plus the mismatch lines, so the councillor-facing panel
    shows a trust warning instead of silently-blended baselines.

    The holiday warning path is what's under test; the brief's other inputs
    (crowding/ghosts/lateness/annualization) are exercised by the other
    brief tests and are stubbed here so this test runs in seconds instead
    of paying a full obs_lateness.csv re-read for logic it doesn't check.
    """
    from app.routers import brief

    bad_feed = tmp_path / "calendar_dates.txt"
    bad_feed.write_text(
        "service_id,date,exception_type\n"
        "26SE07-CPBlock-Weekday-11,20260904,1\n"
        "26SE07-CPBlock-Weekday-11,20260908,1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(brief.config, "LOCAL_GTFS_DIR", tmp_path)
    monkeypatch.setattr(
        brief,
        "_realtime_validation",
        lambda: {"available": False},
    )
    monkeypatch.setattr(
        brief,
        "_crowding",
        lambda: {"available": False},
    )
    monkeypatch.setattr(
        brief,
        "_ghost_trips",
        lambda: {"available": False},
    )

    # Minimal transfer rows: the holiday-warning path only needs the
    # annualized sums to be positive and the ward-lookup loop to run.
    def _fake_finder(service_day: str = "weekday", limit: int = 5, **_):
        return [
            {
                "route_i": "2",
                "route_j": "26",
                "stop_name": "MEADOWVALE TOWN CENTRE",
                "wait_minutes": 12.0,
                "rider_minutes_per_year": 1000.0 + i,
            }
            for i in range(min(limit, 3))
        ]

    monkeypatch.setattr(brief, "find_worst_missed_connections", _fake_finder)

    resp = client.get("/api/report/executive-brief")
    assert resp.status_code == 200
    data = resp.json()
    assert data["holiday_check"]["ok"] is False
    assert any("Labour Day" in w for w in data["holiday_check"]["warnings"])
    assert data["annualized"]["rider_minutes_per_year_top_50"] > 0
    assert "ward_caveat" in data["sources"]
    assert "delay_ward_coverage" in data["sources"]
    # The measured stream is part of the brief: crowding + ghost trips must
    # be present (available or not, never absent).
    assert "measured" in data
    assert "crowding" in data["measured"]
    assert "ghost_trips" in data["measured"]
    for section in ("crowding", "ghost_trips"):
        assert "available" in data["measured"][section]
    if data["measured"]["crowding"]["available"]:
        periods = data["measured"]["crowding"]["periods"]
        assert periods
        for rows in periods.values():
            for row in rows:
                assert "route_short_name" in row
                assert "crowded_share_pct" in row
    if data["measured"]["ghost_trips"]["available"]:
        g = data["measured"]["ghost_trips"]
        assert g["ghost_count"] >= 0
        assert "ghost_rate_pct" in g
        assert isinstance(g["worst_routes"], list)


def test_executive_brief_bad_day(client):
    resp = client.get("/api/report/executive-brief", params={"service_day": "tuesday"})
    assert resp.status_code == 422


def test_service_quality_endpoint(client):
    """The measured Stream B endpoint serves the collector's CSVs read-only."""
    resp = client.get("/api/service-quality")
    assert resp.status_code == 200
    data = resp.json()
    assert data["peak_report_file"] == "peak_report.md"
    # Lateness is real collected data on disk; the response shape must match
    # the frontend's ServiceQualityResponse regardless of availability. On a
    # fresh checkout (e.g. CI) the collector CSVs are absent, so each block
    # must degrade to {"available": False} rather than blow up.
    for block in ("lateness", "crowding", "boardings"):
        payload = data[block]
        if payload is None:
            continue
        assert "available" in payload
    lat = data["lateness"]
    if lat and lat["available"]:
        assert lat["n_observations"] > 0
        assert isinstance(lat["mean_lateness_min"], float)
        assert isinstance(lat["pct_on_time"], (int, float))
        # On time + early + late must partition every departure (sum to 100),
        # not overlap — a bus >2 min early can't also be counted as on time.
        total = lat["pct_on_time"] + lat["pct_early"] + lat.get("pct_late", 0)
        assert abs(total - 100.0) < 1.0, (
            f"on-time/early/late must sum to 100, got {total}"
        )
        assert isinstance(lat["top_early_routes"], list)
        for r in lat["top_early_routes"]:
            assert "route" in r and "mean_lateness_min" in r
    crowding = data["crowding"]
    if crowding and crowding["available"]:
        for rows in crowding["periods"].values():
            assert rows and "crowded_share_pct" in rows[0]
    boardings = data["boardings"]
    if boardings and boardings["available"]:
        for rows in boardings["periods"].values():
            assert rows and "boardings_lower_pax" in rows[0]
    ghosts = data["ghost_trips"]
    if ghosts and ghosts["available"]:
        # by_period field should be present when ghost data has timestamps
        if "by_period" in ghosts:
            assert isinstance(ghosts["by_period"], list)
            for bp in ghosts["by_period"]:
                assert "period" in bp and "ghosts" in bp


def test_equity_compute_endpoint(client):
    """POST /api/equity/compute derives equity from the latest optimizer run.

    Returns 404 when no optimization has been run, or 200 with the standard
    equity report shape when a result exists.
    """
    resp = client.post("/api/equity/compute")
    if resp.status_code == 404:
        assert "optimization" in resp.json()["detail"].lower()
        return
    assert resp.status_code == 200
    data = resp.json()
    for key in ("winners", "losers", "passenger_minutes_saved", "solver_status"):
        assert key in data
    assert isinstance(data["winners"], list)
    assert isinstance(data["losers"], list)


def test_travel_baseline_endpoint(client):
    """POST /api/travel/baseline plans a journey on today's timetable only.

    Returns the baseline itinerary without running the optimizer.
    """
    body = {
        "origin": {"mode": "stop", "stop_id": "0001"},
        "destination": {"mode": "point", "lat": 43.594, "lon": -79.647},
        "depart_at": 600.0,
        "max_transfers": 2,
        "service_day": "weekday",
        "max_shift": 5.0,
        "buffer_minutes": 2.0,
        "high_freq_cutoff": 10.0,
        "t_max": 25.0,
        "volume_mode": "estimated",
        "window_start": 360.0,
        "window_end": 1320.0,
        "max_connections": 6000,
    }
    resp = client.post("/api/travel/baseline", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert "origin" in data and "destination" in data
    # baseline endpoint should not include optimizer results
    assert "baseline" in data
    # The response should be fast (no optimizer), but we can't test timing here.


# ---- travel router unit tests (merged from test_travel_coverage.py) -----------


def test_to_pt_stop_mode():
    from app.models import TravelPoint
    from app.routers import travel as tv

    assert tv._to_pt(TravelPoint(mode="stop", stop_id="0087")) == ("stop", "0087", 0.0)


def test_to_pt_point_mode():
    from app.models import TravelPoint
    from app.routers import travel as tv

    assert tv._to_pt(TravelPoint(mode="point", lat=43.5, lon=-79.6)) == (
        "point",
        43.5,
        -79.6,
    )


def test_to_pt_invalid_modes_return_none():
    # stop mode without a stop_id, point mode without lat/lon.
    from app.models import TravelPoint
    from app.routers import travel as tv

    assert tv._to_pt(TravelPoint(mode="stop")) is None
    assert tv._to_pt(TravelPoint(mode="point")) is None


def test_opt_key_excludes_journey_fields():
    """Two requests differing only in origin/depart share one solver key."""
    from app.models import TravelPoint
    from app.routers import travel as tv

    a = tv._opt_key(_travel_req(depart_at=480.0, max_shift=7.0))
    b = tv._opt_key(
        _travel_req(
            depart_at=900.0,
            origin=TravelPoint(mode="point", lat=43.6, lon=-79.7),
            max_shift=7.0,
        )
    )
    assert a == b


def test_itin_json_none_stays_none():
    from app.routers import travel as tv

    assert tv._itin_json(None) is None


def test_itin_json_serializes_bus_and_walk_legs(bus_leg, walk_leg):
    from app.routers import travel as tv

    itin = SimpleNamespace(
        legs=[
            walk_leg(),
            bus_leg(headway={"scheduled": 10.0}),
        ],
        total_minutes=15.3,
        transfers=0,
        depart_at=600.0,
        arrive_at=615.3,
    )
    stop_names = {"0087": "Winston Churchill Blvd At X", "0001": "Origin Stop"}
    out = tv._itin_json(itin, stop_names)
    assert out["total_minutes"] == 15.3
    assert out["legs"][0]["kind"] == "walk"
    assert out["legs"][0]["distance_m"] == 240.0
    bus = out["legs"][1]
    # stop_names map raw IDs to human-readable names.
    assert bus["board_stop"] == "Winston Churchill Blvd At X"
    assert bus["alight_stop"] == "3104"  # unmapped ID passes through
    assert bus["headway"] == 15.0  # None headway → _json_headway default
    assert bus["path"] == [[43.58, -79.75], [43.59, -79.64]]


def test_itin_json_without_names_keeps_raw_ids(bus_leg):
    from app.routers import travel as tv

    out = tv._itin_json(
        SimpleNamespace(
            legs=[bus_leg()],
            total_minutes=1.0,
            transfers=0,
            depart_at=0.0,
            arrive_at=1.0,
        )
    )
    assert out["legs"][0]["board_stop"] == "0087"


def test_baseline_rejects_ambiguous_and_missing_time():
    from fastapi import HTTPException
    from app.routers import travel as tv

    with pytest.raises(HTTPException) as e:
        tv.travel_baseline(_travel_req(depart_at=600.0, arrive_by=700.0))
    assert e.value.status_code == 422
    with pytest.raises(HTTPException):
        tv.travel_baseline(_travel_req(depart_at=None))


def test_baseline_rejects_unresolvable_points():
    from fastapi import HTTPException
    from app.models import TravelPoint
    from app.routers import travel as tv

    with pytest.raises(HTTPException) as e:
        tv.travel_baseline(_travel_req(origin=TravelPoint(mode="stop")))
    assert e.value.status_code == 422


def test_compare_rejects_missing_times():
    from fastapi import HTTPException
    from app.routers import travel as tv

    with pytest.raises(HTTPException):
        tv.travel_compare(_travel_req(depart_at=None))


def test_baseline_endpoint_plans_journey(monkeypatch, fake_travel_feed, fake_itin):
    from app.routers import travel as tv

    monkeypatch.setattr(tv, "prepare_feed", lambda day: fake_travel_feed)
    monkeypatch.setattr(tv, "_compute_headways_cached", lambda t, st: {"10": 12.0})
    captured = {}

    def fake_plan(*args, **kwargs):
        captured["offsets"] = kwargs.get("offsets")
        return fake_itin(15.0)

    monkeypatch.setattr(tv, "plan_journey", fake_plan)
    out = tv.travel_baseline(_travel_req())
    assert out["mode"] == "depart_at"
    assert out["baseline"]["total_minutes"] == 15.0
    # leg stop ID 0087 isn't in the fake feed's map -> passes through raw
    # (name-mapping behavior is covered by the _itin_json tests above).
    assert out["baseline"]["legs"][0]["board_stop"] == "0087"
    # baseline always plans with no offsets.
    assert captured["offsets"] is None


def test_compare_endpoint_reports_savings(
    monkeypatch, fake_travel_feed, fake_optimization_result, fake_itin
):
    from app.routers import travel as tv

    monkeypatch.setattr(tv, "prepare_feed", lambda day: fake_travel_feed)
    monkeypatch.setattr(tv, "_compute_headways_cached", lambda t, st: {"10": 12.0})
    monkeypatch.setattr(
        tv, "_run_optimizer_cached", lambda req: fake_optimization_result
    )
    plans = [fake_itin(20.0), fake_itin(15.0)]
    monkeypatch.setattr(tv, "plan_journey", lambda *a, **k: plans.pop(0))
    out = tv.travel_compare(_travel_req())
    assert out["optimizer"]["status"] == "ok"
    assert out["optimizer"]["offsets_count"] == 1
    # Clock basis (owner-selected 2026-09-24): depart_at mode measures how
    # much EARLIER the rider arrives (stub: both depart 600, optimized arrives
    # 615 vs baseline 620).
    assert out["savings_basis"] == "earliest_arrival"
    assert out["savings_minutes"] == 5.0
    assert out["optimized"]["total_minutes"] == 15.0


def test_compare_savings_arrive_by_leaves_later(
    monkeypatch, fake_travel_feed, fake_optimization_result, fake_itin
):
    """arrive_by mode: savings = how much LATER the rider can leave with the
    same arrival deadline (clock basis)."""
    from app.routers import travel as tv

    monkeypatch.setattr(tv, "prepare_feed", lambda day: fake_travel_feed)
    monkeypatch.setattr(tv, "_compute_headways_cached", lambda t, st: {"10": 12.0})
    monkeypatch.setattr(
        tv, "_run_optimizer_cached", lambda req: fake_optimization_result
    )
    plans = [fake_itin(20.0, arrive_by=600.0), fake_itin(15.0, arrive_by=600.0)]
    monkeypatch.setattr(tv, "plan_journey", lambda *a, **k: plans.pop(0))
    out = tv.travel_compare(_travel_req(depart_at=None, arrive_by=600.0))
    assert out["savings_basis"] == "latest_departure"
    # Optimized moves 5 min faster => the rider can depart 5 min later.
    assert out["savings_minutes"] == 5.0


def test_compare_savings_none_when_a_plan_fails(
    monkeypatch, fake_travel_feed, fake_optimization_result
):
    from app.routers import travel as tv

    monkeypatch.setattr(tv, "prepare_feed", lambda day: fake_travel_feed)
    monkeypatch.setattr(tv, "_compute_headways_cached", lambda t, st: {"10": 12.0})
    monkeypatch.setattr(
        tv, "_run_optimizer_cached", lambda req: fake_optimization_result
    )
    monkeypatch.setattr(tv, "plan_journey", lambda *a, **k: None)
    out = tv.travel_compare(_travel_req())
    assert out["savings_minutes"] is None


def test_search_stops_matches_substring_and_limits():
    from app.routers.travel import search_stops

    out = search_stops(q="winston churchill", limit=5)
    assert out["results"], "expected real-feed matches"
    for r in out["results"]:
        assert "winston churchill" in r["stop_name"].lower()
        assert isinstance(r["routes"], list)
    assert len(out["results"]) <= 5


def test_search_stops_no_match_returns_empty():
    from app.routers.travel import search_stops

    assert search_stops(q="zzzqqqxx", limit=10)["results"] == []


def test_search_stops_dedupes_same_name_same_routes():
    """T159 #6: paired GTFS platform ids with an identical display name AND
    identical route set are one rider-facing choice — the dropdown must not
    list the same entry twice. Distinct platforms of one name (different
    route badges) stay separate."""
    from app.routers.travel import search_stops

    out = search_stops(q="square one", limit=20)["results"]
    keys = [(r["stop_name"], tuple(r["routes"])) for r in out]
    assert len(keys) == len(set(keys)), (
        f"duplicate name+routes entries in search results: {keys}"
    )
    # The exact live-reproduced pair (0481/0666, 'City Centre Dr At Square
    # One Dr', identical routes) collapses to one entry — the lowest id wins.
    dupes = [r for r in out if r["stop_name"] == "City Centre Dr At Square One Dr"]
    assert len(dupes) == 1, f"expected 1 folded entry, got {len(dupes)}"
    assert dupes[0]["stop_id"] == "0481"
    # Distinct platforms of the terminal remain individually listed.
    terminal = search_stops(q="City Centre Transit Terminal", limit=20)["results"]
    assert len({r["stop_id"] for r in terminal}) == len(terminal)


def test_startup_identity_logs_version_and_module_mtimes(caplog):
    """The stale-server visibility log: version line + one line per identity
    module, each reporting the file the module was loaded from and its mtime.
    A module that fails to import must log IMPORT FAILED, not raise."""
    import logging

    from app.main import log_startup_identity

    with caplog.at_level(logging.INFO, logger="miway.api"):
        log_startup_identity()  # must not raise

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "Starting MiWay Transit Optimizer API v1.1.0" in text
    for rel in (
        "app/routers/service_quality.py",
        "app/routers/equity.py",
        "scripts/collect_service.py",
    ):
        assert rel in text, f"identity module {rel} not logged"
    assert "mtime" in text or "IMPORT FAILED" in text


def test_startup_identity_reports_missing_module(caplog, monkeypatch):
    """A module that can't import is reported as IMPORT FAILED (not raised),
    so startup logging never breaks server boot."""
    import importlib
    import logging

    from app import main

    real_import_module = importlib.import_module

    def fake_import_module(name, *a, **k):
        if name == "app.routers.service_quality":
            raise ImportError("simulated missing module")
        return real_import_module(name, *a, **k)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    with caplog.at_level(logging.INFO, logger="miway.api"):
        main.log_startup_identity()

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "app/routers/service_quality.py -> IMPORT FAILED" in text
