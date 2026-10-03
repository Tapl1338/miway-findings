"""P1.4-pattern contract test: /api/slowness payload vs the TS types.

Parses ``SlownessProvenanceValue``, ``SlownessJourneyAnchor`` and
``SlownessRouteResponse`` straight out of ``frontend/src/types/index.ts``
and binds the live endpoint payload to them — drift in either direction
(backend drops a field the type requires, or emits one the type never
declared) fails here, same doctrine as test_p14_contract_all_endpoints.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FRONTEND_TYPES = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "index.ts"
)


def _parse_ts_interface(source: str, name: str) -> dict[str, bool]:
    """TS interface members -> {field: required?}, depth-aware.

    Nested object literals (``components: { ... }``) are skipped as blocks;
    only depth-1 members are returned (the P1.4 ghost-parser lesson).
    """
    m = re.search(rf"export interface {name}\b[^\{{]*\{{", source)
    assert m, f"interface {name} not found in types/index.ts"
    fields: dict[str, bool] = {}
    depth = 0
    for line in source[m.end() :].splitlines():
        stripped = line.strip()
        if depth == 0:
            if stripped.startswith("}"):
                break
            fm = re.match(r"(\w+)(\?)?:", stripped)
            if fm:
                fields[fm.group(1)] = fm.group(2) is None
        # track brace depth for nested literals on this line
        depth += line.count("{") - line.count("}")
    return fields


@pytest.fixture(scope="module")
def ts_types() -> dict[str, dict[str, bool]]:
    src = FRONTEND_TYPES.read_text(encoding="utf-8")
    return {
        "prov": _parse_ts_interface(src, "SlownessProvenanceValue"),
        "anchor": _parse_ts_interface(src, "SlownessJourneyAnchor"),
        "route": _parse_ts_interface(src, "SlownessRouteResponse"),
    }


@pytest.fixture(scope="module")
def payload() -> dict:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        resp = c.get("/api/slowness/36")
    assert resp.status_code == 200
    return resp.json()


def test_response_keys_match_ts_interface(payload, ts_types):
    """Every top-level response field exists in SlownessRouteResponse, and
    every required field of the interface is present in the payload."""
    declared = ts_types["route"]
    for key in payload:
        assert key in declared, (
            f"backend emits '{key}' but SlownessRouteResponse never declared it "
            "(add it to the TS type — this is how drift happens)"
        )
    for field, required in declared.items():
        if required:
            assert field in payload, f"required TS field '{field}' missing from payload"


def test_components_match_ts_shape(payload, ts_types):
    declared = ts_types["prov"]
    for name, comp in payload["components"].items():
        assert name in (
            "in_vehicle_min",
            "pad_min",
            "ghost_rate_pct",
            "circuity_ratio",
        ), name
        for key in comp:
            assert key in declared, (
                f"component {name} emits '{key}' not in SlownessProvenanceValue"
            )
        if comp.get("value") is not None:
            assert "source" in comp and "n" in comp


def test_anchor_matches_ts_shape(payload, ts_types):
    declared = ts_types["anchor"]
    anchor = payload["journey_anchor"]
    for key in anchor:
        assert key in declared, (
            f"journey anchor emits '{key}' not in SlownessJourneyAnchor"
        )
    if anchor.get("value") is not None:
        # the sum invariant, at the contract boundary
        assert anchor["on_route_min"] + anchor["walk_min"] == pytest.approx(
            anchor["value"], abs=0.05
        ), "sum invariant violated: on_route + walk != end-to-end"
