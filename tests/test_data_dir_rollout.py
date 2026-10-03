"""Wave-0.5 ``--data-dir`` rollout — shared fences + per-script CLI behavior.

Covers the reproducible-mode fences spread from T43 to the top analysis
consumers (exec_summary, equity_report, realized_waits, validation_study,
check_report_drift):

* fence (a): a ``--data-dir`` without ``MANIFEST.md`` is refused.
* fence (c): canonical outputs are never written in frozen mode — an
  explicit ``--out``/``--out-prefix`` is required and must not resolve to a
  canonical path or live inside the frozen directory.
* positive path: ``--reuse`` re-renders the canonical JSON into a scratch
  ``--out`` and stamps the consumed manifest hash into the output.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

EXEC_SUMMARY = ["scripts/exec_summary.py"]
EQUITY_REPORT = ["scripts/equity_report.py"]
REALIZED_WAITS = ["scripts/realized_waits.py"]
VALIDATION_STUDY = ["scripts/validation_study.py"]
CHECK_DRIFT = ["scripts/check_report_drift.py"]


def _frozen_dir(tmp_path: Path, name: str = "frozen") -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / "MANIFEST.md").write_text(
        "# frozen cut\n| file | sha256 |\n", encoding="utf-8"
    )
    (d / "obs_lateness.csv").write_text(
        "route_short_name,stop_id,dep_time_min,lateness_minutes,horizon_minutes,date\n",
        encoding="utf-8",
    )
    return d


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=180,
    )


# ---------------------------------------------------------------------------
# data_dir_util unit tests
# ---------------------------------------------------------------------------


def test_argv_forms():
    from scripts.data_dir_util import data_dir_from_argv

    assert data_dir_from_argv(["x", "--data-dir", "a/b"]) == Path("a/b")
    assert data_dir_from_argv(["x", "--data-dir=c/d"]) == Path("c/d")
    assert data_dir_from_argv(["x", "--data-dir"]) is None  # missing value
    assert data_dir_from_argv(["x"]) is None


def test_apply_early_sets_env(monkeypatch):
    from scripts import data_dir_util

    monkeypatch.delenv("MIWAY_DATA_DIR", raising=False)
    # apply_data_dir_early mutates os.environ directly (not via monkeypatch),
    # so record the pre-test value and restore it — otherwise "Z:/frozen"
    # leaks into every later test that spawns a subprocess and the script
    # refuses to read from the nonexistent directory.
    saved = os.environ.get("MIWAY_DATA_DIR")
    try:
        data_dir_util.apply_data_dir_early(["--data-dir", "Z:/frozen"])
        # Path normalizes to the OS form (backslashes on Windows).
        assert os.environ["MIWAY_DATA_DIR"] == str(Path("Z:/frozen"))
        # No flag -> env untouched.
        data_dir_util.apply_data_dir_early([])
        assert os.environ["MIWAY_DATA_DIR"] == str(Path("Z:/frozen"))
    finally:
        if saved is None:
            os.environ.pop("MIWAY_DATA_DIR", None)
        else:
            os.environ["MIWAY_DATA_DIR"] = saved


def test_data_dir_error_fences(tmp_path):
    from scripts.data_dir_util import data_dir_error

    assert data_dir_error(None) is None  # live mode always OK

    # Not a directory.
    err = data_dir_error(tmp_path / "nope")
    assert err is not None and "not a directory" in err

    # Directory without MANIFEST.md.
    plain = tmp_path / "plain"
    plain.mkdir()
    err = data_dir_error(plain)
    assert err is not None and "MANIFEST.md" in err

    frozen = _frozen_dir(tmp_path)
    canon = tmp_path / "docs" / "out.json"

    # No canonical outputs -> manifest check only.
    assert data_dir_error(frozen) is None

    # Canonical-output writers: --out mandatory in frozen mode.
    err = data_dir_error(frozen, canonical_outputs=(canon,), out=None)
    assert err is not None and "requires an explicit --out" in err

    # --out equal to a canonical path is refused.
    err = data_dir_error(frozen, canonical_outputs=(canon,), out=canon)
    assert err is not None and "canonical path" in err

    # --out inside the frozen directory is refused.
    err = data_dir_error(frozen, canonical_outputs=(canon,), out=frozen / "x.json")
    assert err is not None and "inside the frozen data directory" in err

    # A scratch --out elsewhere is fine.
    ok = tmp_path / "scratch" / "out.json"
    assert data_dir_error(frozen, canonical_outputs=(canon,), out=ok) is None


def test_manifest_hash_stable(tmp_path):
    from scripts.data_dir_util import manifest_hash

    frozen = _frozen_dir(tmp_path)
    h = manifest_hash(frozen)
    assert len(h) == 16
    assert h == manifest_hash(frozen)


# ---------------------------------------------------------------------------
# exec_summary.py
# ---------------------------------------------------------------------------


def test_exec_summary_refuses_dir_without_manifest(tmp_path):
    d = tmp_path / "no-manifest"
    d.mkdir()
    r = _run(
        [
            *EXEC_SUMMARY,
            "--data-dir",
            str(d),
            "--reuse",
            "--out",
            str(tmp_path / "s.json"),
        ]
    )
    assert r.returncode == 1
    assert "MANIFEST.md" in r.stderr


def test_exec_summary_requires_out_in_frozen_mode(tmp_path):
    frozen = _frozen_dir(tmp_path)
    r = _run([*EXEC_SUMMARY, "--data-dir", str(frozen), "--reuse"])
    assert r.returncode == 1
    assert "--out" in r.stderr


def test_exec_summary_refuses_canonical_out(tmp_path):
    frozen = _frozen_dir(tmp_path)
    canon = REPO / "docs" / "exec-summary.json"
    r = _run([*EXEC_SUMMARY, "--data-dir", str(frozen), "--reuse", "--out", str(canon)])
    assert r.returncode == 1
    assert "canonical path" in r.stderr


def test_exec_summary_reuse_into_scratch(tmp_path):
    frozen = _frozen_dir(tmp_path)
    out = tmp_path / "scratch" / "exec-summary.json"
    r = _run([*EXEC_SUMMARY, "--data-dir", str(frozen), "--reuse", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    assert out.exists()
    assert out.with_suffix(".md").exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["input_fingerprints"]["data_dir_manifest"].startswith("sha256:")
    # Load-bearing number preserved through the re-render.
    assert data["result"]["saved_pax_minutes"] > 0


# ---------------------------------------------------------------------------
# equity_report.py
# ---------------------------------------------------------------------------


def test_equity_report_fences_and_reuse(tmp_path):
    frozen = _frozen_dir(tmp_path)
    canon = REPO / "docs" / "equity-report.json"

    r = _run(
        [*EQUITY_REPORT, "--data-dir", str(frozen), "--reuse", "--out", str(canon)]
    )
    assert r.returncode == 1
    assert "canonical path" in r.stderr

    out = tmp_path / "scratch" / "equity-report.json"
    r = _run([*EQUITY_REPORT, "--data-dir", str(frozen), "--reuse", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    assert out.exists() and out.with_suffix(".md").exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["input_fingerprints"]["data_dir_manifest"].startswith("sha256:")


# ---------------------------------------------------------------------------
# validation_study.py
# ---------------------------------------------------------------------------


def test_validation_study_fences_and_reuse(tmp_path):
    frozen = _frozen_dir(tmp_path)
    r = _run([*VALIDATION_STUDY, "--data-dir", str(frozen), "--reuse"])
    assert r.returncode == 1
    assert "--out" in r.stderr

    out = tmp_path / "scratch" / "validation-study.json"
    r = _run(
        [*VALIDATION_STUDY, "--data-dir", str(frozen), "--reuse", "--out", str(out)]
    )
    assert r.returncode == 0, r.stderr
    assert out.exists() and out.with_suffix(".md").exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["data_dir_manifest"].startswith("sha256:")


# ---------------------------------------------------------------------------
# realized_waits.py
# ---------------------------------------------------------------------------


def test_realized_waits_fences(tmp_path):
    d = tmp_path / "no-manifest"
    d.mkdir()
    r = _run([*REALIZED_WAITS, "--data-dir", str(d)])
    assert r.returncode == 1
    assert "MANIFEST.md" in r.stderr

    frozen = _frozen_dir(tmp_path)
    # Default --out-prefix resolves inside the frozen dir -> refused.
    r = _run([*REALIZED_WAITS, "--data-dir", str(frozen)])
    assert r.returncode == 1
    assert "canonical path" in r.stderr or "inside the frozen" in r.stderr

    # Explicit scratch prefix passes the fence (fails later only because the
    # synthetic dir has no GTFS feed — that is the data-error path, not the
    # fence path).
    scratch = tmp_path / "scratch" / "rw"
    r = _run(
        [
            *REALIZED_WAITS,
            "--data-dir",
            str(frozen),
            "--out-prefix",
            str(scratch),
            "--gtfs-dir",
            str(tmp_path / "no-feed"),
        ]
    )
    assert "MANIFEST.md" not in r.stderr  # fence passed
    assert r.returncode != 0  # feed missing -> dies later, not on the fence


# ---------------------------------------------------------------------------
# check_report_drift.py
# ---------------------------------------------------------------------------


def _tiny_report() -> dict:
    return {
        "result": {
            "saved_pax_minutes": 100.0,
            "movable_routes": 10,
            "total_connections": 6000,
            "base_avg_wait": 18.84,
            "opt_avg_wait": 16.82,
        },
        "solver_status": "FEASIBLE",
    }


def _write_report_dirs(tmp_path: Path) -> tuple[Path, Path]:
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    baseline.mkdir()
    current.mkdir()
    files = {
        "exec-summary.json": _tiny_report(),
        "validation-report.json": {
            "result": {
                "saved_pax_minutes": 100.0,
                "movable_routes": 10,
                "total_connections": 6000,
            },
            "solver_status": "FEASIBLE",
        },
        "validation-study.json": {
            "deterministic_savings_minutes": 100.0,
            "total_connections": 6000,
            "solver_status": "FEASIBLE",
        },
        "equity-report.json": {
            "passenger_minutes_saved": 100.0,
            "total_connections": 6000,
            "solver_status": "FEASIBLE",
        },
    }
    for name, payload in files.items():
        (baseline / name).write_text(json.dumps(payload), encoding="utf-8")
        (current / name).write_text(json.dumps(payload), encoding="utf-8")
    # Force a drift on one headline so the md summary path is exercised.
    drifted = _tiny_report()
    drifted["result"]["saved_pax_minutes"] = 120.0  # 20% > 5% tolerance
    (current / "exec-summary.json").write_text(json.dumps(drifted), encoding="utf-8")
    return baseline, current


def test_check_report_drift_fence_and_provenance(tmp_path):
    d = tmp_path / "no-manifest"
    d.mkdir()
    baseline, current = _write_report_dirs(tmp_path)
    r = _run(
        [
            *CHECK_DRIFT,
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--data-dir",
            str(d),
        ]
    )
    assert r.returncode == 1
    assert "MANIFEST.md" in r.stderr

    frozen = _frozen_dir(tmp_path)
    out_md = tmp_path / "drift.md"
    r = _run(
        [
            *CHECK_DRIFT,
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--data-dir",
            str(frozen),
            "--output",
            str(out_md),
        ]
    )
    # Drift detected (by design above) -> exit 1, but the md carries provenance.
    assert r.returncode == 1
    assert "drift detected" in r.stdout.lower()
    assert out_md.exists()
    assert "Regenerated inputs" in out_md.read_text(encoding="utf-8")
