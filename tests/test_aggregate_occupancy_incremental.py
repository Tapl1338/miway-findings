"""Regression: ``--since`` incremental aggregation must MERGE into the
existing occupancy_stats.csv, not replace full history with a partial
window. The overwrite bug (2026-09-02) shrank 279 route-period rows to 56
and silenced the crush-load ghost rule for ~40 minutes.

Runs the real script against a tiny synthetic snapshot set (real format:
``{"polls": [{"fetched_at", "buses": [...]}]}``, old files backdated via
mtime since that is what ``--since`` filters on): full scan -> incremental
window -> asserts nothing was lost and the new observations were added.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "aggregate_occupancy.py"


def _different_period_ts(anchor: float) -> float:
    """Return a timestamp in a different collection period than *anchor*.

    The final assertion ("the old period's row must survive untouched") is
    only meaningful when the old and new windows land in different periods;
    a fixed ``- 7200`` offset was wall-clock dependent (it failed whenever
    both fell inside pm_rush). Scan backwards until the periods differ.
    """
    sys.path.insert(0, str(REPO))
    from app.config import period_for_epoch

    anchor_period = period_for_epoch(anchor)
    ts = anchor - 1800
    while period_for_epoch(ts) == anchor_period:
        ts -= 1800
    return ts


def _write_snapshot(path: Path, buses: list[dict], mtime: float | None = None) -> None:
    """Write a snapshot file in the collector's real nested format."""
    fetched = buses[0]["_fetched_at"] if buses else time.time()
    path.write_text(json.dumps({"polls": [{"fetched_at": fetched, "buses": buses}]}))
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _run(out: Path, glob: str, since: float | None) -> None:
    cmd = [sys.executable, str(SCRIPT), "--globs", glob, "--out", str(out)]
    if since is not None:
        cmd += ["--since", str(since)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"script failed: {proc.stderr}\n{proc.stdout}"


def _bus(trip: str, vehicle: str, status: int, pct: float | None, at: float) -> dict:
    return {
        "trip_id": trip,
        "vehicle_id": vehicle,
        "occupancy_status": status,
        "occupancy_percentage": pct,
        "timestamp": at,
        "_fetched_at": at,
    }


def test_incremental_since_merges_instead_of_overwriting(tmp_path: Path) -> None:
    data = tmp_path / "collections"
    data.mkdir()
    new_t = time.time() - 300  # five minutes ago
    old_t = _different_period_ts(new_t)  # two+ hours back, different period

    # History: 3 standing-or-worse obs in the old window.
    _write_snapshot(
        data / "vp_old.json",
        [_bus("1001", "V1", 3, 70.0, old_t), _bus("1001", "V2", 4, 90.0, old_t)],
        mtime=old_t,
    )
    _write_snapshot(
        data / "vp_old2.json", [_bus("1001", "V3", 3, 65.0, old_t)], mtime=old_t
    )

    out = tmp_path / "occupancy_stats.csv"
    _run(out, str(data / "vp_*.json"), None)  # full scan

    full = pd.read_csv(out)
    n_full = int(full["n_observations"].sum())
    assert n_full == 3

    # New window: 2 more obs (one standing, one many-seats). Files keep
    # their fresh mtimes, so --since picks only these.
    _write_snapshot(
        data / "vp_new.json",
        [_bus("1001", "V4", 3, None, new_t), _bus("1001", "V5", 1, 20.0, new_t)],
    )

    _run(out, str(data / "vp_*.json"), since=new_t - 120)

    merged = pd.read_csv(out)
    n_merged = int(merged["n_observations"].sum())
    assert n_merged == n_full + 2, (
        f"incremental run must ADD to history, not replace it: "
        f"{n_full} -> {n_merged} (expected {n_full + 2})"
    )
    # Status totals must accumulate across rows (the new window may land in
    # a different collection period than the old one; that's correct).
    assert int(merged["n_standing"].sum()) == 3  # old 3=3,3 + new 3
    assert int(merged["n_crushed"].sum()) == 1  # old status 4
    assert int(merged["n_many_seats"].sum()) == 1  # new status 1
    # The old period's row must survive untouched.
    old_row = merged[merged["n_observations"] == 3]
    assert len(old_row) == 1 and int(old_row["n_standing"].iloc[0]) == 2


def test_incremental_with_no_existing_output_writes_fresh(tmp_path: Path) -> None:
    data = tmp_path / "collections"
    data.mkdir()
    _write_snapshot(
        data / "vp_a.json", [_bus("2001", "V9", 2, 40.0, time.time() - 600)]
    )
    out = tmp_path / "fresh.csv"
    _run(out, str(data / "vp_*.json"), since=time.time() - 1200)
    df = pd.read_csv(out)
    assert int(df["n_observations"].sum()) == 1
