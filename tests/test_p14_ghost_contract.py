"""P1.4: backend/frontend contract tests for the ghost-trips payload.

The audit of the P0 campaign found the failure mode these tests prevent: P0.6
grew the API payload (``n_holiday_skipped``, ``n_overnight_stranded``) and
nothing — test or UI — noticed. A renamed or removed field must fail CI here,
before it can silently break the panels.

Mechanism: the live ``/api/service-quality`` response's ``ghosts`` section is
checked against the TypeScript ``GhostTripsResponse``/``GhostRiderImpact``
interfaces in ``frontend/src/types/ghosts.ts`` — parsed straight from the
source file so the contract cannot drift from what the frontend compiles
against. Required (non-optional) fields must exist in every payload; payload
keys the frontend has never heard of are also flagged, so a backend addition
without a matching type update is a visible event, not a silent one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from app.main import app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.slow

_FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
_GHOSTS_TS = _FRONTEND / "src" / "types" / "ghosts.ts"


def _parse_ts_interface(name: str) -> dict[str, bool]:
    """Extract field names and requiredness from a TS interface definition.

    Returns ``{field: required}``. Handles the plain single-line
    ``field: type;`` / ``field?: type;`` members at the interface's top
    level (nested object literals like ``by_route?: { ... }[]`` are skipped
    via brace-depth tracking — their members belong to a different type).
    Good enough for a drift tripwire, and deliberately stricter than nothing.
    """
    text = _GHOSTS_TS.read_text(encoding="utf-8")
    m = re.search(rf"export interface {name} \{{(.*?)\n\}}", text, re.DOTALL)
    assert m, f"interface {name} not found in {_GHOSTS_TS}"
    fields: dict[str, bool] = {}
    depth = 0
    for line in m.group(1).splitlines():
        stripped = line.strip()
        if (
            not stripped
            or stripped.startswith("//")
            or stripped.startswith("/*")
            or stripped.startswith("*")
        ):
            continue
        if depth == 0:
            fm = re.match(r"^(\w+)(\?)?:\s", stripped)
            if fm:
                fields[fm.group(1)] = fm.group(2) is None
        depth += stripped.count("{") - stripped.count("}")
    return fields


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def ghosts_payload(client) -> dict:
    resp = client.get("/api/service-quality")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("ghost_trips"), "ghost_trips section missing"
    return payload["ghost_trips"]


def test_ghost_trips_response_required_fields_exist(ghosts_payload):
    """Every required field of the frontend's GhostTripsResponse compiles
    against a field that the backend actually emits."""
    fields = _parse_ts_interface("GhostTripsResponse")
    required = [f for f, req in fields.items() if req]
    assert required, "contract parse failed — no required fields found"
    missing = [f for f in required if f not in ghosts_payload]
    assert not missing, (
        f"contract violation: frontend-required ghost fields missing from "
        f"/api/service-quality ghosts: {missing}"
    )


def test_ghost_rider_impact_required_fields_exist(ghosts_payload):
    """Same check for the rider-impact sub-object (the P0.6 surface)."""
    impact = ghosts_payload.get("rider_impact")
    assert impact, "rider_impact missing from ghosts payload"
    fields = _parse_ts_interface("GhostRiderImpact")
    required = [f for f, req in fields.items() if req]
    missing = [f for f in required if f not in impact]
    assert not missing, (
        f"contract violation: frontend-required rider_impact fields missing: {missing}"
    )


def test_p06_fields_present_in_payload_and_typed(ghosts_payload):
    """The P0.6 fix's two counters must survive the whole trip: emitted by
    the backend AND declared on the frontend type they will render from."""
    impact = ghosts_payload["rider_impact"]
    assert "n_holiday_skipped" in impact
    assert "n_overnight_stranded" in impact
    assert isinstance(impact["n_holiday_skipped"], int)
    assert isinstance(impact["n_overnight_stranded"], int)
    # And the frontend type knows about them (rendering is the panel's job).
    fields = _parse_ts_interface("GhostRiderImpact")
    assert fields.get("n_holiday_skipped") is False  # declared optional
    assert fields.get("n_overnight_stranded") is False


def test_ghost_payload_has_no_untyped_keys(ghosts_payload):
    """Backend keys the frontend type has never heard of are contract drift
    in the other direction — visible, so the type gets updated deliberately."""
    fields = _parse_ts_interface("GhostTripsResponse")
    unknown = [k for k in ghosts_payload if k not in fields]
    assert not unknown, (
        f"backend emits keys the frontend GhostTripsResponse type lacks: {unknown}"
    )
    impact_fields = _parse_ts_interface("GhostRiderImpact")
    impact = ghosts_payload.get("rider_impact") or {}
    unknown_impact = [k for k in impact if k not in impact_fields]
    assert not unknown_impact, (
        f"backend emits rider_impact keys the frontend type lacks: {unknown_impact}"
    )
