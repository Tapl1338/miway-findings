"""T-SB5 acceptance gate — shared contract test for the 5-builder stress run.

The module under test is chosen by env var HUB_STATS_MODULE (default
hub_stats_1). All five builders must pass this gate against their own module.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "scripts"))

MODULE = os.environ.get("HUB_STATS_MODULE", "hub_stats_1")
# The hub_stats_<i> builders were produced in the T-SB5 stress-run worktrees
# and never committed (tests/tsb5_charter.py is the exercise record). With no
# module present the gate has nothing to test — skip by default instead of
# erroring at collection, which would fail the whole CI backend job
# (the ImportError surfaced on the first green-lint CI run, 2026-10-03).
# Setting HUB_STATS_MODULE with the module on sys.path runs the full gate.
mod = pytest.importorskip(MODULE)


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "stops.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["stop_id", "stop_name", "boardings"])
        w.writeheader()
        w.writerows(rows)
    return p


def _sample() -> list[dict]:
    return [
        {"stop_id": "1103", "stop_name": "City Centre", "boardings": "4100"},
        {"stop_id": "0427", "stop_name": "Meadowvale", "boardings": "2700"},
        {"stop_id": "902", "stop_name": "Sheridan", "boardings": "4100"},
        {"stop_id": "315", "stop_name": "Dundas", "boardings": "1000"},
        {"stop_id": "6671", "stop_name": "Lakeshore", "boardings": "850"},
        {"stop_id": "0119", "stop_name": "Erin Mills", "boardings": "500"},
    ]


class TestLoad:
    def test_loads_and_types(self, tmp_path):
        rows = mod.load_stops(_write(tmp_path, _sample()))
        assert len(rows) == 6
        assert all(isinstance(r["boardings"], int) for r in rows)
        assert rows[0]["stop_id"] == "1103"

    def test_leading_zeros(self, tmp_path):
        p = _write(tmp_path, [{"stop_id": "0427", "stop_name": "X", "boardings": "9"}])
        assert mod.load_stops(p)[0]["stop_id"] == "0427"


class TestTotal:
    def test_total(self, tmp_path):
        rows = mod.load_stops(_write(tmp_path, _sample()))
        assert mod.total_boardings(rows) == 4100 + 2700 + 4100 + 1000 + 850 + 500

    def test_empty(self):
        assert mod.total_boardings([]) == 0


class TestRanking:
    def test_top_tie_integer_break(self, tmp_path):
        rows = mod.load_stops(_write(tmp_path, _sample()))
        ids = [r["stop_id"] for r in mod.top_stops(rows, n=3)]
        # 1103 and 902 tie at 4100 -> integer asc: 902 first
        assert ids[0] == "902" and ids[1] == "1103" and ids[2] == "0427"

    def test_worst(self, tmp_path):
        rows = mod.load_stops(_write(tmp_path, _sample()))
        assert [r["stop_id"] for r in mod.worst_stops(rows, n=2)] == ["0119", "6671"]

    def test_n_gt_rows(self, tmp_path):
        rows = mod.load_stops(_write(tmp_path, _sample()))
        assert len(mod.top_stops(rows, n=99)) == 6

    def test_n_zero(self, tmp_path):
        rows = mod.load_stops(_write(tmp_path, _sample()))
        assert mod.top_stops(rows, n=0) == []
        assert mod.worst_stops(rows, n=-1) == []


class TestSummary:
    def test_shape(self, tmp_path):
        rows = mod.load_stops(_write(tmp_path, _sample()))
        s = mod.summary(rows)
        assert s["total"] == 13250
        assert s["stops_count"] == 6
        assert s["top"][0] == "902"
