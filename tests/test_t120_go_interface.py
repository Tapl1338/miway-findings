"""Tests for ``scripts/t120_go_interface.py`` — T120 Stream 3.

Covers the bus-to-train gap math (P-T120-3), window filtering, weekday
service resolution (calendar + calendar_dates), and verdict banding —
all on synthetic mini-GTFS directories, no network.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts import t120_go_interface as g


def _write_gtfs(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def go_dir(tmp_path):
    return _write_gtfs(
        tmp_path / "go",
        {
            "routes.txt": "route_id,route_short_name,route_long_name\nMI1,MI,Milton\n",
            "trips.txt": (
                "trip_id,route_id,service_id,trip_headsign\n"
                "t1,MI1,wd,Toronto\n"
                "t2,MI1,wd,Toronto\n"
                "t9,MI1,hol,Toronto\n"
            ),
            "stops.txt": "stop_id,stop_name\nLS,Lisgar GO\nLX,Lisgar GO Bus\n",
            "stop_times.txt": (
                "trip_id,stop_id,arrival_time,departure_time\n"
                "t1,LS,06:10:00,06:10:00\n"
                "t2,LS,08:40:00,08:40:00\n"
                "t9,LS,07:30:00,07:30:00\n"
            ),
            "calendar.txt": (
                "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
                "wd,1,1,1,1,1,0,0,20260101,20261231\n"
                "hol,0,0,0,0,0,0,0,20260101,20261231\n"
            ),
        },
    )


@pytest.fixture
def miway_dir(tmp_path):
    return _write_gtfs(
        tmp_path / "miway",
        {
            "routes.txt": "route_id,route_short_name,route_long_name\n38-464,38,Creditview\n",
            "trips.txt": (
                "route_id,service_id,trip_id\n"
                "38-464,wd,b1\n"
                "38-464,wd,b2\n"
                "38-464,hol,b9\n"
            ),
            "stop_times.txt": (
                "trip_id,stop_id,arrival_time,departure_time\n"
                "b1,3298,06:05:00,06:05:00\n"
                "b2,3298,08:15:00,08:15:00\n"
                "b9,3298,07:00:00,07:00:00\n"
            ),
            "calendar.txt": (
                "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
                "wd,1,1,1,1,1,0,0,20260101,20261231\n"
                "hol,0,0,0,0,0,0,0,20260101,20261231\n"
            ),
        },
    )


def test_gap_math_pairs_each_bus_to_next_train(go_dir, miway_dir):
    buses = g._route38_arrivals(miway_dir, date(2026, 9, 16))  # a Wednesday
    trains = g._milton_departures(go_dir, date(2026, 9, 16))
    assert buses == [6 * 3600 + 5 * 60, 8 * 3600 + 15 * 60]  # holiday trip excluded
    assert trains == [6 * 3600 + 10 * 60, 8 * 3600 + 40 * 60]
    gaps = g.bus_to_train_gaps(buses, trains, ("06:00", "09:30"))
    assert gaps == [5.0, 25.0]


def test_window_filters_buses_before_first_train(go_dir, miway_dir):
    buses = g._route38_arrivals(miway_dir, date(2026, 9, 16))
    trains = [6 * 3600 + 15 * 60]  # one train, 10 min after the first bus
    gaps = g.bus_to_train_gaps(buses, trains, ("06:00", "07:00"))
    assert gaps == [10.0]  # only the 06:05 bus is inside the window; 08:15 is not


def test_bus_without_later_train_is_dropped(go_dir, miway_dir):
    buses = [10 * 3600]  # after every train
    assert g.bus_to_train_gaps(buses, [8 * 3600], ("06:00", "10:00")) == []


def test_verdict_bands_at_preregistered_threshold():
    assert g.verdict([25.0, 30.0]) == "CONFIRMED"  # median 27.5 > 20
    assert g.verdict([5.0, 10.0]) == "REFUTED"  # median 7.5 <= 20
    assert g.verdict([]) == "UNMEASURABLE"


def test_calendar_dates_exception_flips_service(tmp_path, go_dir, miway_dir):
    # Wednesday 2026-09-16 with a holiday exception: wd removed, hol added.
    hol = _write_gtfs(
        go_dir.parent / "go2",
        {
            "calendar_dates.txt": (
                "service_id,date,exception_type\nwd,20260916,2\nhol,20260916,1\n"
            ),
            **{
                k: (go_dir / k).read_text(encoding="utf-8")
                for k in (
                    "routes.txt",
                    "trips.txt",
                    "stops.txt",
                    "stop_times.txt",
                    "calendar.txt",
                )
            },
        },
    )
    assert g._active_services(hol, date(2026, 9, 16)) == {"hol"}
    trains = g._milton_departures(hol, date(2026, 9, 16))
    assert trains == [7 * 3600 + 30 * 60]  # only the hol trip survives
