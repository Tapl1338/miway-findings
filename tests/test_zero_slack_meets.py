"""Tests for ``scripts/zero_slack_meets.py`` — network meet inventory.

Synthetic GTFS + lateness fixture: two routes meeting at one stop at
the same scheduled minute; covers meet discovery, both miss directions,
the tolerance band, and the day-aggregation stats.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts import zero_slack_meets as zm


@pytest.fixture
def mini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    gtfs = tmp_path / "downloads"
    gtfs.mkdir()
    (gtfs / "trips.txt").write_text(
        "route_id,trip_id,direction_id\n38-1,t38,1\n44-1,t44,1\n44-1,t44b,1\n",
        encoding="utf-8",
    )
    (gtfs / "stop_times.txt").write_text(
        "trip_id,stop_id,arrival_time,departure_time\n"
        "t38,S,08:00:00,08:00:00\n"
        "t44,S,08:00:00,08:00:00\n"
        "t44b,S,08:05:00,08:05:00\n",
        encoding="utf-8",
    )
    (gtfs / "stops.txt").write_text(
        "stop_id,stop_name\nS,Shared Stop\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(zm, "GTFS", gtfs)
    return gtfs


def _lat(path: Path, rows: list[tuple[str, str, str, int, float]]) -> None:
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
        for rt, stop, d, m, lat in rows:
            w.writerow([rt, stop, f"{m}.0", f"{lat}", "-1.0", d])


def test_load_meets_same_minute_only(mini: Path) -> None:
    meets = zm.load_meets()
    # 08:00 has both routes -> a meet; 08:05 only route 44 -> not
    assert ("S", 8 * 60) in meets
    assert ("S", 8 * 60 + 5) not in meets
    assert meets[("S", 8 * 60)] == {"38", "44"}


def test_classify_same_and_opposite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Route A continues east through S; route B continues east too (SAME);
    # route C arrives from the east and heads back west (OPPOSITE to A).
    gtfs = tmp_path / "downloads2"
    gtfs.mkdir()
    (gtfs / "trips.txt").write_text(
        "route_id,trip_id,direction_id\nA-1,ta,1\nB-1,tb,1\nC-1,tc,1\n",
        encoding="utf-8",
    )
    (gtfs / "stop_times.txt").write_text(
        "trip_id,stop_id,arrival_time,departure_time\n"
        # W -> S -> E (eastbound continuations)
        "ta,W,07:50:00,07:50:00\n"
        "ta,S,08:00:00,08:00:00\n"
        "ta,E,08:10:00,08:10:00\n"
        "tb,W2,07:55:00,07:55:00\n"
        "tb,S,08:00:00,08:00:00\n"
        "tb,E2,08:05:00,08:05:00\n"
        # C: E -> S -> W (turns back: pass-by vs A)
        "tc,E,07:58:00,07:58:00\n"
        "tc,S,08:00:00,08:00:00\n"
        "tc,W,08:12:00,08:12:00\n",
        encoding="utf-8",
    )
    (gtfs / "stops.txt").write_text(
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "S,Shared,43.5,-79.6\n"
        "W,West,43.5,-79.7\n"
        "E,East,43.5,-79.5\n"
        "W2,West2,43.51,-79.7\n"
        "E2,East2,43.51,-79.5\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(zm, "GTFS", gtfs)
    meets = zm.load_meets()
    info = zm.classify_meet_directions(meets)
    assert info[("S", "A", "B", 8 * 60)][3] == "SAME"
    assert info[("S", "A", "C", 8 * 60)][3] == "OPPOSITE"


def test_downstream_backtrack_reconverges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Route C passes S northbound-ish but loops back to a stop route A
    # also serves downstream -> opposite bearing, positive downstream
    # share (the backtrack/loop case), not a pure pass-by.
    gtfs = tmp_path / "downloads3"
    gtfs.mkdir()
    (gtfs / "trips.txt").write_text(
        "route_id,trip_id,direction_id\nA-1,ta,1\nC-1,tc,1\n",
        encoding="utf-8",
    )
    (gtfs / "stop_times.txt").write_text(
        "trip_id,stop_id,arrival_time,departure_time\n"
        "ta,W,07:50:00,07:50:00\n"
        "ta,S,08:00:00,08:00:00\n"
        "ta,E,08:06:00,08:06:00\n"
        "ta,E2,08:12:00,08:12:00\n"
        "tc,N,07:58:00,07:58:00\n"
        "tc,S,08:00:00,08:00:00\n"
        "tc,W,08:06:00,08:06:00\n"
        "tc,E2,08:14:00,08:14:00\n",
        encoding="utf-8",
    )
    (gtfs / "stops.txt").write_text(
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "S,Shared,43.5,-79.6\n"
        "W,West,43.5,-79.7\n"
        "E,East,43.5,-79.5\n"
        "N,North,43.55,-79.6\n"
        "E2,East2,43.5,-79.4\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(zm, "GTFS", gtfs)
    meets = zm.load_meets()
    assert meets[("S", 8 * 60)] == {"A", "C"}
    share = zm.classify_downstream(meets, horizon_min=20)
    assert share[("S", "A", "C", 8 * 60)] == 1  # E2 shared downstream


def test_realize_both_directions(mini: Path, tmp_path: Path) -> None:
    lat = tmp_path / "lat.csv"
    # d1: 44 leaves 2 min before 38 -> rider on 38 misses (miss_ab)
    # d2: 38 leaves 2 min before 44 -> rider on 44 misses (miss_ba)
    # d3: 38 leaves 0.2 before 44 -> inside tolerance, no miss either way
    _lat(
        lat,
        [
            ("38", "S", "2026-09-08", 480, 0.0),
            ("44", "S", "2026-09-08", 480, -2.0),
            ("38", "S", "2026-09-09", 480, -2.0),
            ("44", "S", "2026-09-09", 480, 0.0),
            ("38", "S", "2026-09-10", 480, -0.2),
            ("44", "S", "2026-09-10", 480, 0.0),
        ],
    )
    meets = zm.load_meets()
    rows = zm.realize(meets, lat, tolerance=0.5)
    assert len(rows) == 1
    r = rows[0]
    assert r["route_a"] == "38" and r["route_b"] == "44"
    assert r["n_days"] == 3
    assert r["n_miss_ab"] == 1
    assert r["n_miss_ba"] == 1
    assert r["miss_rate_max"] == pytest.approx(1 / 3)


def test_realize_earliest_row_wins(mini: Path, tmp_path: Path) -> None:
    lat = tmp_path / "lat.csv"
    # duplicate rows for the same key: earliest (most negative) wins
    _lat(
        lat,
        [
            ("38", "S", "2026-09-08", 480, 1.0),
            ("38", "S", "2026-09-08", 480, -1.0),
            ("44", "S", "2026-09-08", 480, 0.0),
        ],
    )
    rows = zm.realize(zm.load_meets(), lat, tolerance=0.5)
    # gap = 0 - (-1) = +1 > 0.5 -> one miss_ba, none on the other side
    assert rows[0]["n_miss_ba"] == 1
    assert rows[0]["n_miss_ab"] == 0
    assert rows[0]["median_gap"] == pytest.approx(1.0)
