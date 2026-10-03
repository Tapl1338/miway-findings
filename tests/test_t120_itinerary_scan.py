"""Tests for ``scripts/t120_itinerary_scan.py`` — T120 Stream 1.

Covers the timetable sub-graph load (weekday service resolution, route
filter), transfer options (same curb / opposite curb / terminal cluster),
and the two-strategy anchor comparison that produces the P-T120-1 verdict,
all on a synthetic mini-feed — no network, no real-data dependence.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts import t120_itinerary_scan as sc

WED = date(2026, 9, 16)


@pytest.fixture
def feed(tmp_path) -> Path:
    """Minimal two-route feed.

    Geography: origin 1597/2661 (opposite curbs, same street) served by
    the 38; the 38 winds to the SJSS stop 3023 in 80 min; the 44 runs a
    direct line from the terminal cluster (MDVT-A/MDVT-B platforms) to
    Argentia 2301/2315 (opposite curbs) in 15 min, where the 38's short
    final leg reaches SJSS in 5 min. The 38 also stops at the terminal.
    """
    root = tmp_path / "miway"
    files = {
        "routes.txt": (
            "route_id,route_short_name,route_long_name\n"
            "r38,38,Creditview\n"
            "r44,44,Mississauga Road\n"
        ),
        "trips.txt": (
            "route_id,service_id,trip_id\n"
            "r38,wd,w38a\n"
            "r38,wd,w38b\n"
            "r38,wd,w38c\n"
            "r44,wd,w44a\n"
        ),
        "stops.txt": (
            "stop_id,stop_name\n"
            "1597,Winston Churchill Blvd At Dalehurst Dr\n"
            "2661,Winston Churchill Blvd At Tradewind Dr\n"
            "9001,Meadowvale Town Centre Bus Terminal Platform A\n"
            "9002,Meadowvale Town Centre Bus Terminal Platform C\n"
            "2301,Argentia Rd At Mississauga Rd\n"
            "2315,Argentia Rd At Mississauga Rd\n"
            "3023,Creditview Rd At St Joseph Secondary School\n"
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "wd,1,1,1,1,1,0,0,20260101,20261231\n"
        ),
        "stop_times.txt": (
            "trip_id,stop_sequence,stop_id,arrival_time,departure_time\n"
            # all-38 winding ride: leaves Dalehurst 07:00, reaches SJSS 08:20
            "w38a,1,1597,07:00:00,07:00:00\n"
            "w38a,2,9001,07:20:00,07:20:00\n"
            "w38a,3,3023,08:20:00,08:20:00\n"
            # 38 short hop to the terminal (for the two-transfer chain)
            "w38b,1,1597,07:00:00,07:00:00\n"
            "w38b,2,9001,07:10:00,07:10:00\n"
            # 44 direct from the terminal to Argentia
            "w44a,1,9002,07:20:00,07:20:00\n"
            "w44a,2,2315,07:35:00,07:35:00\n"
            # 38 final leg from Argentia to SJSS
            "w38c,1,2301,07:45:00,07:45:00\n"
            "w38c,2,3023,07:50:00,07:50:00\n"
        ),
    }
    root.mkdir(parents=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def test_load_keeps_only_subgraph_routes(feed):
    tt = sc._load_timetable(feed, WED)
    assert set(tt["trips"]) == {"w38a", "w38b", "w38c", "w44a"}


def test_transfer_options_same_curb_and_terminal(feed):
    tt = sc._load_timetable(feed, WED)
    names = tt["names"]
    same = dict(sc._transfer_options("2301", names))
    assert same["2301"] == 0.0
    assert same["2315"] == sc.SAME_NAME_WALK_MIN  # opposite curb, same name
    assert "2661" not in same  # differently-named origin curbs are not auto-paired
    term = dict(sc._transfer_options("9001", names))
    assert term["9002"] == sc.TERMINAL_WALK_MIN  # terminal platform cluster


def test_origin_starts_stagger_the_crosswalk():
    starts = dict(sc._origin_starts(7 * 3600))
    assert starts["1597"] == 7 * 3600  # first curb at the anchor
    assert starts["2661"] == 7 * 3600 + int(sc.ORIGIN_WALK_MIN * 60)  # after the walk


def test_two_transfer_beats_all38_in_anchor_scan(feed):
    tt = sc._load_timetable(feed, WED)
    anchor = 7 * 3600  # 07:00, rider ready at Dalehurst
    best: dict[str, tuple[int, list[dict]] | None] = {}
    for origin in sc.ORIGIN_STOPS:
        for strategy, routes, rides in (
            ("all38", ("38",), 2),
            ("twoxfer", ("38", "44"), 3),
        ):
            r = sc.earliest_arrival(tt, origin, anchor, routes, rides)
            if r and (best.get(strategy) is None or r[0] < best[strategy][0]):
                best[strategy] = r
    # all-38: 07:00 -> 08:20 (80 min winding ride)
    assert best["all38"][0] == 8 * 3600 + 20 * 60
    # two-transfer: 38 hop 07:00->07:10, terminal walk 5, 44 07:20->07:35,
    # 2-min opposite-curb walk, 38 07:45->07:50 = 07:50 (50 min)
    assert best["twoxfer"][0] == 7 * 3600 + 50 * 60
    assert best["all38"][0] - best["twoxfer"][0] == 30 * 60


def test_rides_budget_limits_strategy(feed):
    tt = sc._load_timetable(feed, WED)
    # With max_rides=1 the all-38 strategy can still ride w38a (1 ride).
    r = sc.earliest_arrival(tt, "1597", 7 * 3600, ("38",), 1)
    assert r is not None and r[0] == 8 * 3600 + 20 * 60
    # With 0 rides allowed, no itinerary exists.
    assert sc.earliest_arrival(tt, "1597", 7 * 3600, ("38",), 0) is None


def test_holiday_service_resolution(tmp_path, feed):
    (feed / "calendar_dates.txt").write_text(
        "service_id,date,exception_type\nwd,20260916,2\n", encoding="utf-8"
    )
    tt = sc._load_timetable(feed, WED)
    assert tt["trips"] == {}  # wd removed -> no trips that day
