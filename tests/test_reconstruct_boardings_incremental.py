"""Regression: ``--since`` incremental boardings reconstruction must MERGE
with the existing ``boardings_daily.csv``, not replace full history with a
partial window. The overwrite bug (2026-09-02) shrank boardings_daily from
17 service dates to 1 and zeroed the route summary's history.

Runs the real script against a tiny synthetic snapshot set in the
collector's real format: full scan -> incremental window -> asserts the
historical date survives and the fresh date's observations were added.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "reconstruct_boardings.py"
_TORONTO = ZoneInfo("America/Toronto")

# A real trip from the GTFS feed (route 71). Synthetic observations must sit
# on the trip's actual stops for the load-profile snapper to accept them.
# seq 1 -> seq 5 spacing is ~2 km, well inside SNAP_DISTANCE_M per stop.
_TRIP = "30309176"
_TRIP_STOPS = [  # (lat, lon) for seq 1..4 of trip 30309176
    (43.63556, -79.538267),
    (43.636908, -79.539146),
    (43.638287, -79.537958),
    (43.640071, -79.535102),
]


def _write_snapshot(path: Path, buses: list[dict], mtime: float) -> None:
    """Write a snapshot file in the collector's real nested format."""
    fetched = buses[0]["timestamp"] if buses else time.time()
    path.write_text(json.dumps({"polls": [{"fetched_at": fetched, "buses": buses}]}))
    os.utime(path, (mtime, mtime))


def _run(out: Path, glob: str, since: float | None) -> None:
    cmd = [sys.executable, str(SCRIPT), "--globs", glob, "--out", str(out)]
    if since is not None:
        cmd += ["--since", str(since)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, f"script failed: {proc.stderr}\n{proc.stdout}"


def _bus(trip: str, vehicle: str, pct: float, at: float, date: str, seq: int) -> dict:
    """A bus observation parked exactly on the trip's ``seq``-th stop."""
    lat, lon = _TRIP_STOPS[seq % len(_TRIP_STOPS)]
    return {
        "trip_id": trip,
        "vehicle_id": vehicle,
        "occupancy_percentage": pct,
        "occupancy_status": 2,
        "timestamp": at,
        "service_date": date,
        "lat": lat,
        "lon": lon,
    }


def test_incremental_since_merges_daily_history(tmp_path: Path) -> None:
    data = tmp_path / "collections"
    data.mkdir()

    # Historical day: 2026-08-20, am_rush (trip 30309176 departs 07:17
    # Toronto). Observations advance down the trip's stop sequence.
    base = datetime(2026, 8, 20, 7, 17, tzinfo=_TORONTO).timestamp()
    old_t = base - 7200  # file mtime well in the past
    _write_snapshot(
        data / "old.json",
        [
            _bus(_TRIP, "v1", 40.0, base, "20260820", seq=0),
            _bus(_TRIP, "v1", 60.0, base + 60, "20260820", seq=1),
            _bus(_TRIP, "v1", 80.0, base + 120, "20260820", seq=2),
            _bus(_TRIP, "v1", 80.0, base + 180, "20260820", seq=3),
        ],
        mtime=old_t,
    )

    out = tmp_path / "boardings"
    glob = str(data / "*.json")

    # Full scan builds real history (needs the GTFS feed for trip->route).
    _run(out, glob, None)
    daily_path = Path(f"{out}_daily.csv")
    assert daily_path.exists()
    full = pd.read_csv(daily_path, dtype={"service_date": str})
    assert (full["service_date"] == "20260820").any(), "history missing after full scan"

    # Fresh day: 2026-09-02, same trip/time-of-day. Snapshot mtime is now.
    base2 = datetime(2026, 9, 2, 7, 17, tzinfo=_TORONTO).timestamp()
    _write_snapshot(
        data / "new.json",
        [
            _bus(_TRIP, "v2", 50.0, base2, "20260902", seq=0),
            _bus(_TRIP, "v2", 70.0, base2 + 60, "20260902", seq=1),
            _bus(_TRIP, "v2", 90.0, base2 + 120, "20260902", seq=2),
            _bus(_TRIP, "v2", 90.0, base2 + 180, "20260902", seq=3),
        ],
        mtime=time.time(),
    )

    # Incremental run filtered on mtime: only new.json should be loaded...
    _run(out, glob, time.time() - 3600)

    merged = pd.read_csv(daily_path, dtype={"service_date": str})
    dates = set(merged["service_date"])
    # THE regression: the historical date must survive the incremental run.
    assert "20260820" in dates, (
        f"incremental run replaced history: dates={sorted(dates)}"
    )
    assert "20260902" in dates, "fresh date missing after incremental run"

    # Historical row content unchanged.
    old_row = merged[merged["service_date"] == "20260820"].iloc[0]
    assert int(old_row["n_trips"]) == 1
