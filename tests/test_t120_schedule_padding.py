"""Tests for ``scripts/t120_schedule_padding.py`` — T120 Stream 2b.

Covers shared-pair discovery (both routes adjacent on the same ordered
stop pair), scheduled segment medians, and the trip-continuity realized
chaining — all on a tiny synthetic GTFS + lateness fixture.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts import t120_schedule_padding as sp


@pytest.fixture
def mini_gtfs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Two routes sharing one ordered pair A->B (38: 2 min sched, 43: 3 min)."""
    gtfs = tmp_path / "downloads"
    gtfs.mkdir()
    (gtfs / "trips.txt").write_text(
        "route_id,trip_id,direction_id\n38-1,t38,1\n43-1,t43,1\n",
        encoding="utf-8",
    )
    (gtfs / "stop_times.txt").write_text(
        "trip_id,stop_id,arrival_time,departure_time\n"
        "t38,A,06:00:00,06:00:00\n"
        "t38,B,06:02:00,06:02:00\n"
        "t43,A,06:10:00,06:10:00\n"
        "t43,B,06:13:00,06:13:00\n",
        encoding="utf-8",
    )
    (gtfs / "stops.txt").write_text(
        "stop_id,stop_name,stop_lat,stop_lon\nA,Stop A,43.5,-79.7\nB,Stop B,43.6,-79.6\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sp, "GTFS", gtfs)
    return gtfs


def _write_lateness(path: Path, rows: list[tuple[str, str, str, int, float]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "route_short_name",
                "stop_id",
                "dep_time_min",
                "lateness_minutes",
                "horizon_minutes",
                "date",
            ]
        )
        for rt, stop, _date, minute, lat in rows:
            w.writerow([rt, stop, f"{minute}.0", f"{lat}", "-1.0", _date])


def test_shared_adjacent_pairs_both_routes(mini_gtfs: Path) -> None:
    triprt = sp._trip_route_map()
    trips = sp._trip_stops(triprt)
    pairs = sp.shared_adjacent_pairs(trips, triprt)
    assert ("A", "B") in pairs
    assert pairs[("A", "B")]["38"] == [2]
    assert pairs[("A", "B")]["43"] == [3]


def test_scheduled_padding_visible(mini_gtfs: Path) -> None:
    triprt = sp._trip_route_map()
    trips = sp._trip_stops(triprt)
    pairs = sp.shared_adjacent_pairs(trips, triprt)
    # 38 scheduled faster than 43 here -> ratio < 1 catches a padding gap
    assert pairs[("A", "B")]["38"][0] < pairs[("A", "B")]["43"][0]


def test_realized_by_trip_trip_continuity(mini_gtfs: Path, tmp_path: Path) -> None:
    triprt = sp._trip_route_map()
    trips = sp._trip_stops(triprt)
    pairs = sp.shared_adjacent_pairs(trips, triprt)
    lat_path = tmp_path / "lat.csv"
    # 38 trip: 1 min late at A, 3 min late at B -> realized segment 2+2=4
    _write_lateness(
        lat_path,
        [
            ("38", "A", "2026-09-08", 360, 1.0),
            ("38", "B", "2026-09-08", 362, 3.0),
            ("43", "A", "2026-09-08", 370, 0.5),
            ("43", "B", "2026-09-08", 373, 0.0),
        ],
    )
    realized = sp.realized_by_trip(trips, triprt, pairs, sp.load_lateness(lat_path))
    assert realized[("A", "B")]["38"] == [4.0]
    assert realized[("A", "B")]["43"] == [2.5]


def test_realized_requires_both_rows(mini_gtfs: Path, tmp_path: Path) -> None:
    triprt = sp._trip_route_map()
    trips = sp._trip_stops(triprt)
    pairs = sp.shared_adjacent_pairs(trips, triprt)
    lat_path = tmp_path / "lat.csv"
    _write_lateness(lat_path, [("38", "A", "2026-09-08", 360, 1.0)])  # no B row
    realized = sp.realized_by_trip(trips, triprt, pairs, sp.load_lateness(lat_path))
    assert realized.get(("A", "B"), {}).get("38", []) == []
