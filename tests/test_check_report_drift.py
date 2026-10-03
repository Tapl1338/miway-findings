"""Unit tests for the councillor-report drift check."""

import json
import subprocess
import sys
from pathlib import Path

from scripts.check_report_drift import _build_drift_markdown, check_reports

_REPORTS = {
    "exec-summary.json": {
        "solver_status": "FEASIBLE",
        "result": {
            "saved_pax_minutes": 6000.0,
            "movable_routes": 50,
            "total_connections": 6000,
            "base_avg_wait": 20.4,
            "opt_avg_wait": 17.1,
        },
    },
    "validation-report.json": {
        "solver_status": "FEASIBLE",
        "result": {
            "saved_pax_minutes": 6000.0,
            "movable_routes": 50,
            "total_connections": 6000,
        },
    },
    "validation-study.json": {
        "solver_status": "FEASIBLE",
        "total_connections": 6000,
        "deterministic_savings_minutes": 6000.0,
    },
    "equity-report.json": {
        "solver_status": "FEASIBLE",
        "total_connections": 6000,
        "passenger_minutes_saved": 6000.0,
    },
}


def _write(dirpath, payloads):
    for name, data in payloads.items():
        (dirpath / name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_identical_reports_pass(tmp_path):
    base = tmp_path / "base"
    cur = tmp_path / "cur"
    base.mkdir()
    cur.mkdir()
    _write(base, _REPORTS)
    _write(cur, _REPORTS)
    assert check_reports(base, cur, tolerance_pct=5.0, floor=1.0) == []


def test_percentage_drift_fails(tmp_path):
    base = tmp_path / "base"
    cur = tmp_path / "cur"
    base.mkdir()
    cur.mkdir()
    _write(base, _REPORTS)
    mutated = json.loads(json.dumps(_REPORTS))
    mutated["exec-summary.json"]["result"]["saved_pax_minutes"] = 3000.0  # -50%
    _write(cur, mutated)
    failures = check_reports(base, cur, tolerance_pct=5.0, floor=1.0)
    assert len(failures) == 1
    assert "exec-summary.json result.saved_pax_minutes" in failures[0]
    assert "50.00%" in failures[0]


def test_small_drift_within_tolerance_passes(tmp_path):
    base = tmp_path / "base"
    cur = tmp_path / "cur"
    base.mkdir()
    cur.mkdir()
    _write(base, _REPORTS)
    mutated = json.loads(json.dumps(_REPORTS))
    # 0.5% drift — CP-SAT run-to-run noise should never fail the check.
    mutated["equity-report.json"]["passenger_minutes_saved"] = 6030.0
    _write(cur, mutated)
    assert check_reports(base, cur, tolerance_pct=5.0, floor=1.0) == []


def test_solver_status_change_fails(tmp_path):
    base = tmp_path / "base"
    cur = tmp_path / "cur"
    base.mkdir()
    cur.mkdir()
    _write(base, _REPORTS)
    mutated = json.loads(json.dumps(_REPORTS))
    mutated["validation-study.json"]["solver_status"] = "OPTIMAL"
    _write(cur, mutated)
    failures = check_reports(base, cur, tolerance_pct=5.0, floor=1.0)
    assert any("validation-study.json solver_status" in f for f in failures)


def test_missing_regenerated_report_fails(tmp_path):
    base = tmp_path / "base"
    cur = tmp_path / "cur"
    base.mkdir()
    cur.mkdir()
    _write(base, _REPORTS)
    # Only two of the four reports regenerated — a structural breakage.
    subset = {k: v for k, v in _REPORTS.items() if "equity" not in k}
    _write(cur, subset)
    failures = check_reports(base, cur, tolerance_pct=5.0, floor=1.0)
    assert any("equity-report.json" in f for f in failures)


# --- _build_drift_markdown tests ---


def test_build_drift_markdown_contains_failures():
    failures = [
        "exec-summary.json result.saved_pax_minutes: 6000 -> 3000 (50.00% > 5% tolerance)",
        "solver_status: FEASIBLE -> INFEASIBLE",
    ]
    md = _build_drift_markdown(failures, Path("/tmp/base"), Path("/tmp/cur"), 5.0)
    assert "## Nightly report drift detected" in md
    assert failures[0] in md
    assert failures[1] in md
    assert "±5% tolerance" in md
    assert "Review the diff" in md


# --- CLI --output integration tests ---


def _run_drift_check(base_dir, cur_dir, output_path=None, extra_args=None):
    """Invoke check_report_drift.py as a subprocess."""
    backend_root = Path(__file__).resolve().parent.parent
    cmd = [
        sys.executable,
        str(backend_root / "scripts" / "check_report_drift.py"),
        "--baseline",
        str(base_dir),
        "--current",
        str(cur_dir),
        "--tolerance-pct",
        "5.0",
    ]
    if output_path:
        cmd += ["--output", str(output_path)]
    if extra_args:
        cmd += extra_args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(backend_root))


def test_output_flag_writes_markdown_on_drift(tmp_path):
    base = tmp_path / "base"
    cur = tmp_path / "cur"
    base.mkdir()
    cur.mkdir()
    _write(base, _REPORTS)
    mutated = json.loads(json.dumps(_REPORTS))
    mutated["exec-summary.json"]["result"]["saved_pax_minutes"] = 3000.0
    _write(cur, mutated)
    output = tmp_path / "drift.md"
    result = _run_drift_check(base, cur, output)
    assert result.returncode == 1
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "Nightly report drift detected" in content
    assert "saved_pax_minutes" in content
    assert "FAIL" not in content  # markdown uses plain text, not console prefix


def test_output_flag_not_created_on_pass(tmp_path):
    base = tmp_path / "base"
    cur = tmp_path / "cur"
    base.mkdir()
    cur.mkdir()
    _write(base, _REPORTS)
    _write(cur, _REPORTS)
    output = tmp_path / "drift.md"
    result = _run_drift_check(base, cur, output)
    assert result.returncode == 0
    assert not output.exists()
