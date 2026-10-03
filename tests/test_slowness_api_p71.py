"""API tests for the slowness card endpoints (P7.1 Phase 3)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import slowness


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Same bidirectional isolation as the unit fixtures, plus no real journeys."""
    monkeypatch.setattr(slowness, "_load_circuity_summary", lambda: {})
    monkeypatch.setattr(slowness, "_CIRCUITY_SUMMARY", None)
    yield
    slowness._CIRCUITY_SUMMARY = None


def test_manifest_endpoint_lists_routes(client, monkeypatch):
    slowness._prepared("weekday")
    manifest = slowness.route_manifest("weekday")
    resp = client.get("/api/slowness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service_day"] == "weekday"
    assert any(r["route_short_name"] for r in body["routes"])
    assert len(body["routes"]) == len(manifest)


def test_route_endpoint_returns_decomposition_and_anchor(client, monkeypatch):
    monkeypatch.setattr(
        slowness,
        "journey_anchor",
        lambda r, d="weekday": {
            "value": 21.0,
            "source": "plan_journey (baseline timetable)",
            "n": 5,
            "fingerprint": None,
            "depart_at": 720.0,
            "on_route_min": 21.0,
            "walk_min": 0.0,
            "route_share_pct": 100.0,
            "ridden_trip_id": "t",
            "anchor_endpoints": ["1049", "0931"],
            "anchor_endpoint_names": ["The Collegeway", "Ridgeway"],
            "scheduled_run_min": 24.0,
            "reference_trip_id": "t2",
        },
    )
    resp = client.get("/api/slowness/36")
    assert resp.status_code == 200
    body = resp.json()
    assert body["route_short_name"] == "36"
    comps = body["components"]
    # provenance-object contract at the API boundary too
    for name, comp in comps.items():
        assert "value" in comp, f"{name} lacks value"
        if comp["value"] is not None:
            assert "source" in comp and "n" in comp
    anchor = body["journey_anchor"]
    assert anchor["value"] == pytest.approx(21.0)
    assert anchor["on_route_min"] + anchor["walk_min"] == pytest.approx(anchor["value"])


def test_route_endpoint_unknown_route_is_404(client):
    resp = client.get("/api/slowness/999")
    assert resp.status_code == 404


def test_route_endpoint_degrades_gracefully_without_anchor(client, monkeypatch):
    """Anchor unavailable (loop-route corner cases etc.): endpoint still 200
    with a reasoned null — the card renders the decomposition honestly."""
    # Patch the CACHED entry point: the router calls journey_anchor_cached
    # (D2), and patching bare journey_anchor is bypassed whenever a sibling
    # test in this file has already warmed the route-36 disk cache.
    monkeypatch.setattr(
        slowness,
        "journey_anchor_cached",
        lambda r, d="weekday": {
            "value": None,
            "reason": "no candidate departure (13 tried) produced a journey riding route 36",
            "fingerprint": None,
        },
    )
    resp = client.get("/api/slowness/36")
    assert resp.status_code == 200
    body = resp.json()
    assert body["journey_anchor"]["value"] is None
    assert "reason" in body["journey_anchor"]
