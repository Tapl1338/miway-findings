"""T-SB1 acceptance tests — CSV summary module for boardings_routes.csv.

Contract the builder must satisfy (T-SB1 charter):
  module backend/scripts/boardings_summary.py exposing:
    - load_routes(csv_path) -> list[dict]  (rows as parsed, 'boardings' as int)
    - total_boardings(rows) -> int
    - top_routes(rows, n=5) -> list[dict]  (highest boardings first, tie -> route_id asc)
    - worst_routes(rows, n=3) -> list[dict] (lowest boardings first, tie -> route_id asc)
    - summary(rows) -> dict with keys total, routes_count, top (list of route_id)

Every function must be pure stdlib+pandas-free (csv module only). The builder
does NOT write these tests; they pre-exist as the DONE-WHEN gate.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "scripts"))

from boardings_summary import (  # noqa: E402
    load_routes,
    summary,
    total_boardings,
    top_routes,
    worst_routes,
)


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "routes.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["route_id", "route_name", "boardings"])
        w.writeheader()
        w.writerows(rows)
    return p


def _sample_rows() -> list[dict]:
    return [
        {"route_id": "19", "route_name": "Hurontario", "boardings": "4100"},
        {"route_id": "3", "route_name": "Bloor", "boardings": "2700"},
        {"route_id": "109", "route_name": "Meadowvale Express", "boardings": "4100"},
        {"route_id": "66", "route_name": "Sheridan", "boardings": "1000"},
        {"route_id": "23", "route_name": "Erin Mills", "boardings": "850"},
        {"route_id": "61", "route_name": "Ridgeway", "boardings": "500"},
    ]


class TestLoadRoutes:
    def test_loads_and_types(self, tmp_path):
        p = _write(tmp_path, _sample_rows())
        rows = load_routes(p)
        assert len(rows) == 6
        assert all(isinstance(r["boardings"], int) for r in rows)
        assert rows[0]["route_id"] == "19"
        assert rows[0]["boardings"] == 4100

    def test_route_id_stays_string(self, tmp_path):
        """Leading-zero ids must NOT become ints (norm_stop_id lesson)."""
        p = _write(
            tmp_path, [{"route_id": "042", "route_name": "X", "boardings": "10"}]
        )
        rows = load_routes(p)
        assert rows[0]["route_id"] == "042"


class TestTotal:
    def test_total(self, tmp_path):
        rows = load_routes(_write(tmp_path, _sample_rows()))
        assert total_boardings(rows) == 4100 + 2700 + 4100 + 1000 + 850 + 500

    def test_empty(self):
        assert total_boardings([]) == 0


class TestTopWorst:
    def test_top_desc_with_tie_route_id_asc(self, tmp_path):
        rows = load_routes(_write(tmp_path, _sample_rows()))
        top3 = top_routes(rows, n=3)
        # 19 and 109 tie at 4100 -> "19" < "109" lexicographic? NO: numeric
        # route ordering — contract says route_id asc as INTEGER.
        ids = [r["route_id"] for r in top3]
        assert ids[0] in ("19", "109")
        if ids[0] == "109":
            assert ids[1] == "19"
        else:
            assert ids[1] == "109"
        assert ids[2] == "3"

    def test_worst_asc(self, tmp_path):
        rows = load_routes(_write(tmp_path, _sample_rows()))
        worst = worst_routes(rows, n=2)
        ids = [r["route_id"] for r in worst]
        assert ids == ["61", "23"]

    def test_n_larger_than_rows(self, tmp_path):
        rows = load_routes(_write(tmp_path, _sample_rows()))
        assert len(top_routes(rows, n=99)) == 6


class TestSummary:
    def test_shape(self, tmp_path):
        rows = load_routes(_write(tmp_path, _sample_rows()))
        s = summary(rows)
        assert s["total"] == 13250
        assert s["routes_count"] == 6
        assert s["top"][0] in ("19", "109")
