"""P5.2 planner-ready exports: one run -> one complete handoff package.

The pure assemblers are tested directly with a synthetic run dict; the
endpoint is tested through TestClient against a seeded state store.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.planner_report import (
    checklist_rows,
    equity_rows,
    kpis,
    offset_rows,
    package_csv,
    package_json,
    route_impact_rows,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _run(offsets: dict | None = None, response: dict | None = None) -> dict:
    return {
        "id": 7,
        "created_at": "2026-09-20T12:00:00",
        "service_day": "weekday",
        "params": {"period": "midday"},
        "offsets": offsets if offsets is not None else {"2": 3, "16": -2, "9": 0},
        "response": response,
    }


def _response() -> dict:
    return {
        "baseline_avg_wait": 19.12,
        "optimized_avg_wait": 17.45,
        "passenger_minutes_saved": 9406.0,
        "baseline_missed": 2916,
        "optimized_missed": 2526,
        "total_connections": 6000,
        "connection_health": 95.8,
        "status": "OPTIMAL",
        "bound_gap_pct": None,
        "solve_duration_seconds": 41.2,
        "miss_model_name": "july",
        "per_route_impact": [
            {
                "route": "9",
                "connections": 84,
                "baseline_avg_eff_wait": 20.0,
                "optimized_avg_eff_wait": 5.8,
                "delta_minutes": -14.24,
                "worse_off_connections": 30,
                "worse_off_max_minutes": 4.0,
            }
        ],
        "equity_report": {
            "status": "applied",
            "rows": [
                {
                    "ward": "9",
                    "cap_weighted_minutes": 500.0,
                    "realized_weighted_worsening": 120.5,
                    "held": True,
                    "connections": 42,
                }
            ],
            "wards_unbounded": [],
            "note": "cap",
        },
    }


# ---- pure assemblers -------------------------------------------------------


def test_kpis_carry_run_provenance():
    k = kpis(_run(response=_response()))
    assert k["run_id"] == 7 and k["service_day"] == "weekday"
    assert k["wait_improvement_min"] == 1.67
    assert k["routes_shifted"] == 2  # route 9's offset is 0 -> not counted
    assert k["equity_constrained"] is True
    assert k["solver_status"] == "OPTIMAL"


def test_route_impact_rows_shape():
    rows = route_impact_rows(_run(response=_response()))
    (row,) = rows
    assert row["route"] == "9" and row["delta_minutes"] == -14.24
    assert "worse_off_connections" in row


def test_equity_rows_empty_without_report():
    assert equity_rows(_run(response={"status": "OPTIMAL"})) == []
    rows = equity_rows(_run(response=_response()))
    assert rows[0]["held"] is True


def test_offset_rows_include_zero_for_audit():
    rows = offset_rows(_run())
    assert {r["route"] for r in rows} == {"2", "16", "9"}
    assert next(r for r in rows if r["route"] == "9")["offset_minutes"] == 0


def test_checklist_adapts_to_equity_presence():
    with_eq = checklist_rows(_run(response=_response()))
    without_eq = checklist_rows(_run(response={"status": "OPTIMAL"}))
    assert any("caps were applied" in r["detail"] for r in with_eq)
    assert any("No equity caps" in r["detail"] for r in without_eq)


def test_package_json_is_valid_and_complete():
    doc = json.loads(package_json(_run(response=_response())))
    assert set(doc) == {"run", "kpis", "route_impact", "equity", "offsets", "checklist"}
    assert doc["kpis"]["passenger_minutes_saved"] == 9406.0


def test_package_csv_sections():
    csv_text = package_csv(_run(response=_response()))
    sections = [line.split(",")[0] for line in csv_text.splitlines() if line]
    for sec in ("KPI", "ROUTE_IMPACT", "EQUITY", "OFFSET", "CHECKLIST"):
        assert sec in sections
    # header row identifies the format at a glance
    assert csv_text.splitlines()[0] == "SECTION,METRIC,VALUE"


# ---- endpoint ---------------------------------------------------------------


def test_report_endpoint_run_id_pin(client):
    """A bogus run_id must fail, not silently fall back to the latest run.

    (Order-independent: the no-run-at-all case is covered by the 400 branch
    the same way the export endpoint's test accepts 200-or-400.)
    """
    resp = client.get("/api/optimize/transfers/report?run_id=999999")
    assert resp.status_code in (400, 404)


def test_report_endpoint_json_and_csv(client):
    import app.state_store as store

    store.save_run(
        service_day="weekday",
        params={"period": "midday"},
        offsets={"2": 3},
        response_json=json.dumps(_response()),
    )
    r_json = client.get("/api/optimize/transfers/report")
    assert r_json.status_code == 200
    doc = r_json.json()
    assert doc["run"]["service_day"] == "weekday"
    assert doc["kpis"]["missed_connections_optimized"] == 2526
    assert doc["equity"][0]["ward"] == "9"

    r_csv = client.get("/api/optimize/transfers/report?format=csv")
    assert r_csv.status_code == 200
    assert r_csv.headers["content-type"].startswith("text/csv")
    assert "planner_report_run" in r_csv.headers["content-disposition"]
    assert "SECTION" in r_csv.text.splitlines()[0]

    # (bogus-id pinning covered by test_report_endpoint_run_id_pin)
