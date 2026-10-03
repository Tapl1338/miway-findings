"""P1.4 follow-up: the parse-and-bind contract extended to the whole GET API.

Ghost scope was bound in ``test_p14_ghost_contract.py`` (parser lives there and
is imported). This module binds every other GET endpoint the frontend's
``api.ts`` client calls to the TypeScript interface it is typed as returning —
parsed straight from ``frontend/src/types/index.ts`` so the contract cannot
drift from what the frontend compiles against.

Both drift directions trip CI, per endpoint:

* a frontend-required field missing from the live payload (backend rename/remove),
* a backend key the frontend type has never heard of (silent payload growth —
  the P0.6 failure mode: fields shipped with zero consumers for a week).

Exemptions are explicit, not silent:

* POST solve/compute endpoints (async optimize, equity/compute, travel
  baseline/compare, claims refresh) are lifecycle endpoints, not stable GET
  surfaces — exempt.
* ``GET /optimize/transfers/async/{job_id}`` needs a live job id from a POST —
  exempt (its shape is small and exercised by the async lifecycle tests).
* A payload answering ``{"available": false}`` is a legitimate measurement
  state, not a contract violation — the required-field direction is skipped
  for that endpoint (the no-unknown-keys direction still applies).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from app.main import app
from fastapi.testclient import TestClient

# The ghost contract module owns the parser; reuse it so there is one
# definition of "what the TS file says".
sys.path.insert(0, str(Path(__file__).resolve().parent))

pytestmark = pytest.mark.slow

_TYPES_DIR = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types"
_INDEX_TS = _TYPES_DIR / "index.ts"

# (endpoint path, TS interface name, probe query params, payload unwrapper)
# The unwrapper pulls the bound object out of wrapper/array shapes; None
# means the response body IS the bound object.
ENDPOINTS: list[tuple[str, str, dict, str | None]] = [
    ("/api/health", "FeedHealth", {}, None),
    ("/api/public/early-departures", "PublicEarlyDepartures", {}, None),
    ("/api/forecast/scoreboard", "ForecastScoreboard", {}, None),
    ("/api/routes/circuity", "CircuityGeoJSON", {}, None),
    (
        "/api/routes/circuity/summary",
        "CircuitySummaryRoute",  # bound per flagged route element
        {},
        "flagged",
    ),
    ("/api/transfer/nodes", "TransferNode", {"max_nodes": 10}, None),
    ("/api/optimize/transfers/top-missed", "TopMissedResponse", {}, None),
    ("/api/routes/circuity/best-pilot", "BestPilotResponse", {}, None),
    ("/api/claims/verdicts", "ClaimVerdictsResponse", {}, None),
    ("/api/diagnostics/transfer-blindspots", "BlindspotsResponse", {}, None),
    ("/api/report/executive-brief", "ExecutiveBriefResponse", {}, None),
    ("/api/equity/report", "EquityReport", {}, None),
    ("/api/equity/ward-demographics", "WardDemographicsResponse", {}, None),
    ("/api/coverage", "CoverageResponse", {}, None),
    ("/api/diagnostics/data-vintage", "DataVintageResponse", {}, None),
    ("/api/measured/reliability", "ReliabilityResponse", {}, None),
    ("/api/measured/schedule-padding", "SchedulePaddingResponse", {}, None),
    ("/api/routes/corridor-gaps", "CorridorGapsResponse", {}, None),
    ("/api/operations/trends", "OperationsTrends", {}, None),
    ("/api/measured", "MeasuredResponse", {}, None),
    ("/api/travel/stops", "TravelStopResult", {"q": "square", "limit": 5}, "results"),
]
# POST / solve / job-lifecycle endpoints, exempt on purpose (see module doc):
#   /optimize/transfers/async [POST], /optimize/transfers/async/{id} [GET],
#   /optimize/transfers/export [GET csv], /equity/compute [POST],
#   /travel/baseline [POST], /travel/compare [POST],
#   /claims/verdicts/refresh [POST], /api/service-quality [bound in
#   test_p14_ghost_contract.py — ghost scope]


INDEX_SIG = "__index_signature__"


def _interface(name: str) -> dict[str, bool]:
    """Parse an interface from index.ts (brace-depth tracked like the ghost
    parser, plus two structures that interface has and ghosts.ts doesn't):

    * index signatures (``[key: string]: T``) are flagged via the INDEX_SIG
      sentinel — an open interface deliberately accepts unknown keys, so the
      unknown-keys drift check does not apply to it;
    * all-optional interfaces (no required members at all) are preserved as
      such — the caller skips the required-fields check instead of treating
      it as a parse failure (e.g. ClaimVerdictsResponse is a discriminated
      shape where every member is conditional).
    """
    import re

    text = _INDEX_TS.read_text(encoding="utf-8")
    m = re.search(rf"export interface {name} \{{(.*?)\n\}}", text, re.DOTALL)
    assert m, f"interface {name} not found in {_INDEX_TS}"
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
            elif re.match(r"^\[\w+:\s*(string|number|symbol)\]\s*:", stripped):
                fields[INDEX_SIG] = True
        depth += stripped.count("{") - stripped.count("}")
    return fields


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_early_departures_fails_soft_when_sample_missing(client, monkeypatch):
    """The 250k sample is gitignored — a fresh clone must get an honest
    available:false envelope, not a raw 500 (found live by the contract run)."""
    from app.routers import public_leaderboard as pl

    monkeypatch.setenv("MIWAY_LEADERBOARD_SAMPLE", "definitely/not/anywhere.csv")
    monkeypatch.setattr(pl, "_leaderboard_cache", None)
    resp = client.get("/api/public/early-departures")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert "not found" in body["reason"].lower()
    # The cache must stay None — a later call with the sample present recomputes
    # instead of serving the soft-fail envelope forever.
    assert pl._leaderboard_cache is None


@pytest.mark.parametrize(
    "path,ts_type,params,unwrap",
    ENDPOINTS,
    ids=[e[0] for e in ENDPOINTS],
)
def test_endpoint_matches_its_typescript_interface(
    client, path, ts_type, params, unwrap
):
    resp = client.get(path, params=params)
    assert resp.status_code == 200, f"{path} -> {resp.status_code}"
    payload = resp.json()

    bound = payload
    if unwrap:
        if isinstance(payload, dict):
            assert unwrap in payload, f"{path}: wrapper key '{unwrap}' missing"
        bound = payload.get(unwrap)
    if isinstance(bound, list):
        assert bound, f"{path}: nothing to bind — '{unwrap or 'body'}' is empty"
        bound = bound[0]
    assert isinstance(bound, dict), f"{path}: bound payload is not an object"

    # An {"available": false} answer is a measurement state, not drift:
    # the backend legitimately emits nothing else. Only the unknown-keys
    # direction still applies (the envelope must stay typed).
    available_false = bound.get("available") is False or (
        isinstance(payload, dict) and payload.get("available") is False
    )

    fields = _interface(ts_type)
    assert fields, f"{ts_type}: contract parse found no members at all"
    required = [f for f, req in fields.items() if req and f != INDEX_SIG]

    if not available_false:
        missing = [f for f in required if f not in bound]
        assert not missing, (
            f"contract violation on {path}: frontend-required fields of "
            f"{ts_type} missing from the live payload: {missing}"
        )

    if INDEX_SIG not in fields:
        unknown = [k for k in bound if k not in fields]
        assert not unknown, (
            f"contract violation on {path}: backend emits keys the frontend "
            f"{ts_type} type lacks: {unknown} — extend the type deliberately"
        )
