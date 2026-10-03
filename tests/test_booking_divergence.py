"""Tests for ``scripts/booking_divergence.py`` — booked-vs-realized audit.

Synthetic fixture: two routes sharing two ordered links; route A booked
+2 min/link over B (pattern effect sums to +4), realized segments EQUAL
(A's slack burned as cumulative earliness) -> BOOKED-ONLY.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts import booking_divergence as bd

STOPS = ["X", "Y", "Z"]


@pytest.fixture
def mini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(bd, "MIN_SHARED_LINKS", 2)  # tiny fixture
    gtfs = tmp_path / "downloads"
    gtfs.mkdir()
    trips = ["route_id,trip_id,direction_id"]
    stop_times = ["trip_id,stop_id,arrival_time,departure_time"]
    for rt, step in (("A", 4), ("B", 2)):
        for k in range(6):
            tid = f"t{rt}{k}"
            trips.append(f"{rt}-1,{tid},0")
            t = 8 * 60 + k
            for s in STOPS:
                stop_times.append(f"{tid},{s},08:00:00,{t // 60:02d}:{t % 60:02d}:00")
                t += step
    (gtfs / "trips.txt").write_text("\n".join(trips) + "\n", encoding="utf-8")
    (gtfs / "stop_times.txt").write_text("\n".join(stop_times) + "\n", encoding="utf-8")
    (gtfs / "stops.txt").write_text(
        "stop_id,stop_name\nX,Stop X\nY,Stop Y\nZ,Stop Z\n", encoding="utf-8"
    )
    monkeypatch.setattr(bd, "GTFS", gtfs)
    return gtfs


def _lat(path: Path, rows: list[tuple[str, str, int, float]]) -> None:
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
        for rt, stop, minute, latv in rows:
            w.writerow([rt, stop, f"{minute}.0", f"{latv}", "-1.0", "2026-09-08"])


def _links() -> dict:
    links = bd.load_links(6, 8)
    links.update(bd.load_links(14, 18))
    return links


def test_candidate_pairs(mini: Path) -> None:
    cand = bd.candidate_pairs(_links())
    assert ("A", "B") in cand
    assert set(cand[("A", "B")]) == {("X", "Y"), ("Y", "Z")}


def test_booked_rows_pattern_sum(mini: Path) -> None:
    links = _links()
    rows = bd.booked_rows(links, bd.candidate_pairs(links))
    assert rows
    r = rows[0]
    assert r["route_a"] == "A" and r["route_b"] == "B"
    assert r["n_links"] == 2
    assert r["booked_diff_total"] == pytest.approx(4.0)  # +2/link summed


def test_attach_realized_booked_only(mini: Path, tmp_path: Path) -> None:
    links = _links()
    cand = bd.candidate_pairs(links)
    rows = bd.booked_rows(links, cand)
    # A's slack burned as earliness: cumulative -2 min per link
    # (X: 0, Y: -2, Z: -4) -> realized segment 4 + (-2 - 0) = 2 == B's.
    rows_lat = []
    for k in range(6):
        base = 8 * 60 + k
        rows_lat += [
            ("A", "X", base, 0.0),
            ("A", "Y", base + 4, -2.0),
            ("A", "Z", base + 8, -4.0),
            ("B", "X", base, 0.0),
            ("B", "Y", base + 2, 0.0),
            ("B", "Z", base + 4, 0.0),
        ]
    lat = tmp_path / "lat.csv"
    _lat(lat, rows_lat)
    bd.attach_realized(rows, links, cand, lat)
    r = rows[0]
    assert r["class"] == "BOOKED-ONLY"
    assert r["realized_more"] == pytest.approx(r["realized_less"], abs=0.01)
    assert r["realized_more"] == pytest.approx(2.0, abs=0.01)


def test_attach_realized_genuine_gap(mini: Path, tmp_path: Path) -> None:
    links = _links()
    cand = bd.candidate_pairs(links)
    rows = bd.booked_rows(links, cand)
    # A actually runs at booked time (all-zero lateness), B on time too:
    # realized gap = 2/link >= MIN_DIFF -> BOOKED+REALIZED
    rows_lat = []
    for k in range(6):
        base = 8 * 60 + k
        rows_lat += [
            ("A", "X", base, 0.0),
            ("A", "Y", base + 4, 0.0),
            ("A", "Z", base + 8, 0.0),
            ("B", "X", base, 0.0),
            ("B", "Y", base + 2, 0.0),
            ("B", "Z", base + 4, 0.0),
        ]
    lat = tmp_path / "lat.csv"
    _lat(lat, rows_lat)
    bd.attach_realized(rows, links, cand, lat)
    assert rows[0]["class"] == "BOOKED+REALIZED"
