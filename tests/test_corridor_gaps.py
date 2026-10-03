"""Unit tests for app/corridor_gaps.py (terminal corridor seams).

The detector runs against the real bundled MiWay GTFS feed (like the circuity
tests) and verifies the structural invariants: the Meadowvale/Winston
Churchill seam the user reported is found, every seam has legs on opposite
sides with no single TRIP running through, and borderline non-seams (fork
corridors, corridors that simply end) are NOT flagged.

Connectivity is trip-level: a route whose directional trips both terminate at
the terminal (the 90W/90E loops at Meadowvale TC) may appear on BOTH legs of
one seam without any bus running through -- the test checks trips, not routes.
"""

from collections import defaultdict

import pandas as pd

from app import config
from app.corridor_gaps import corridor_of, corridor_seams
from app.gtfs_loader import load_feed


def _trip_corridor_stops() -> dict[tuple[str, str], set[str]]:
    """trip_id -> corridor key -> stop_ids served on that corridor (trip-level
    connectivity, mirroring the detector's graph)."""
    feed = load_feed()
    stop_corridor = {
        sid: corridor_of(name)
        for sid, name in zip(feed["stops"]["stop_id"], feed["stops"]["stop_name"])
    }
    out: dict[tuple[str, str], set[str]] = defaultdict(set)
    for tid, sid in zip(feed["stop_times"]["trip_id"], feed["stop_times"]["stop_id"]):
        c = stop_corridor.get(sid)
        if c:
            out[(tid, c[1])].add(sid)
    return out


def test_corridor_of_extracts_leading_street():
    assert corridor_of("Winston Churchill Blvd At Bayberry Dr") == (
        "Winston Churchill Blvd",
        "winston churchill",
    )
    # Street-type suffixes are stripped so 'Battleford' and 'Battleford Rd'
    # group together.
    assert corridor_of("Battleford At Tours Rd") == ("Battleford", "battleford")
    assert corridor_of("Battleford Rd At Edenwood Dr") == (
        "Battleford Rd",
        "battleford",
    )
    # Terminal platforms are not corridor stops.
    assert corridor_of("Meadowvale Town Centre Bus Terminal Platform E") is None
    assert corridor_of("City Centre Transit Terminal") is None


def test_headline_meadowvale_winston_churchill_seam():
    """The user's example: routes 10/45/109 end at Meadowvale from the south
    on Winston Churchill, 38/43 from the north, and no route runs through."""
    seams = corridor_seams()
    wc = [
        s
        for s in seams
        if s["terminal"] == "Meadowvale Town Centre"
        and "Winston Churchill" in s["corridor"]
    ]
    assert wc, "expected the Meadowvale / Winston Churchill seam"
    seam = wc[0]
    # Both legs terminate at the terminal.
    assert all(leg["terminates_at_terminal"] for leg in seam["legs"])
    # The user's routes are the terminating set.
    assert {"10", "45", "109"} <= set(seam["terminating_routes"])
    assert {"38", "43"} <= set(seam["terminating_routes"])
    # No route runs through: the two sides carry disjoint route sets.
    routes = [set(leg["routes"]) for leg in seam["legs"]]
    assert not (routes[0] & routes[1])
    # Legs are on opposite sides of the terminal.
    sides = [leg["side"] for leg in seam["legs"]]
    assert ("SE" in sides or "S" in sides) and ("NW" in sides or "N" in sides)


def test_all_seams_are_well_formed():
    seams = corridor_seams()
    assert seams, "expected at least one corridor seam in the real feed"
    trip_stops = _trip_corridor_stops()
    for s in seams:
        assert s["terminal"] and s["corridor"]
        assert len(s["legs"]) >= 2
        # Every leg has stops, routes, a side and a nearest stop.
        for leg in s["legs"]:
            assert leg["n_stops"] >= 1
            assert leg["routes"], s
            assert leg["side"]
            assert leg["nearest_stop"]
        # No single TRIP serves stops on two different legs: a through run
        # would chain the legs into one component (the seam's defining
        # property). A route may appear on both legs via directional trips
        # that terminate at the terminal (the 90W/90E turnaround), so the
        # check is trip-level, not route-level.
        leg_sets = [set(leg["stops"]) for leg in s["legs"]]
        for i in range(len(leg_sets)):
            for j in range(i + 1, len(leg_sets)):
                for (_tid, _ck), sids in trip_stops.items():
                    assert not (sids & leg_sets[i] and sids & leg_sets[j]), s
        # Routes die at the terminal from at least two sides.
        assert sum(1 for leg in s["legs"] if leg["terminates_at_terminal"]) >= 2, s
        assert s["terminating_routes"], s
        assert s["story"]


def test_corridor_seams_are_serialisable():
    import json

    seams = corridor_seams()
    json.dumps(seams)  # must not raise


def test_aquitaine_seam_is_the_90_directional_turnaround():
    """The user's case: Aquitaine across Meadowvale TC looks like one corridor
    at the route level (the 90, 44, 48 serve stops on both sides), but their
    directional trips (90W / 90E) terminate at the terminal and turn around --
    no trip crosses, so Aquitaine is a real seam and the 90 legitimately
    appears on BOTH legs."""
    seams = corridor_seams()
    aq = [
        s
        for s in seams
        if s["terminal"] == "Meadowvale Town Centre" and "Aquitaine" in s["corridor"]
    ]
    assert aq, "expected the Meadowvale / Aquitaine seam"
    seam = aq[0]
    legs = seam["legs"]
    assert len(legs) >= 2
    assert all(leg["terminates_at_terminal"] for leg in legs)
    # The 90 serves both sides (east and west Aquitaine) via separate
    # directional trips -- route-level connectivity would have hidden this seam.
    route_sets = [set(leg["routes"]) for leg in legs]
    assert "90" in set.intersection(*route_sets)
    # No trip crosses the terminal on Aquitaine.
    trip_stops = _trip_corridor_stops()
    leg_sets = [set(leg["stops"]) for leg in legs]
    for i in range(len(leg_sets)):
        for j in range(i + 1, len(leg_sets)):
            for (_tid, _ck), sids in trip_stops.items():
                assert not (sids & leg_sets[i] and sids & leg_sets[j])


def test_derry_seam_is_the_hub_spoke_split():
    """Derry Rd at Meadowvale TC: the 39/90 serve Derry west of Winston
    Churchill, the 42 serves it to the east/north, all terminating at Meadowvale
    -- the terminal sits off the corridor, so only the along-corridor-extent
    rule catches it."""
    seams = corridor_seams()
    derry = [
        s
        for s in seams
        if s["terminal"] == "Meadowvale Town Centre" and "Derry" in s["corridor"]
    ]
    assert derry, "expected the Meadowvale / Derry Rd seam"
    seam = derry[0]
    routes = [set(leg["routes"]) for leg in seam["legs"]]
    assert {"39", "90"} in routes and {"42"} in routes
    assert all(leg["terminates_at_terminal"] for leg in seam["legs"])


# ---- pure helpers (merged from the former test_corridor_gaps_coverage.py) ------


from app.corridor_gaps import (  # noqa: E402
    _bearing_label,
    _corridor_display,
    _corridor_seams_uncached,
    _merge_overlapping_chains,
    _nearest_stop_name,
    _seam_story,
    _to_local_km,
    _UnionFind,
)


def test_corridor_of_north_of_form():
    assert corridor_of("X Blvd North Of Y Dr")[0] == "X Blvd"


def test_corridor_of_slash_form():
    assert corridor_of("Battleford/Eglinton")[0] == "Battleford"


def test_corridor_of_empty_and_hub_names():
    assert corridor_of("") is None
    assert corridor_of("Westwood Mall") is None  # hub pattern
    assert corridor_of("Kipling Bus Terminal Platform 3") is None


def test_union_find_unions_and_finds():
    uf = _UnionFind(["a", "b", "c", "d"])
    uf.union("a", "b")
    uf.union("b", "c")
    assert uf.find("a") == uf.find("c")
    assert uf.find("a") != uf.find("d")
    # Union with an already-merged pair is a no-op.
    uf.union("c", "a")
    assert uf.find("b") == uf.find("c")


def test_to_local_km_projection():
    # 0.01 deg of latitude ≈ 1.11 km north of the reference.
    x, y = _to_local_km(43.6, -79.64, 43.59, -79.64)
    assert abs(x) < 0.01
    assert 1.0 < y < 1.2


def test_bearing_label_all_octants():
    assert _bearing_label(0, 1) == "N"
    assert _bearing_label(1, 1) == "NE"
    assert _bearing_label(1, 0) == "E"
    assert _bearing_label(0, -1) == "S"
    assert _bearing_label(-1, 0) == "W"


def test_merge_overlapping_chains_merges_parallel_and_keeps_apart():
    # Corridor running north (axis = +y). Two chains on the same side with
    # overlapping extents merge; the one south of the terminal stays apart.
    near = {
        "n1": (0.0, 1.0),
        "n2": (0.01, 2.0),
        "n3": (0.0, 1.5),
        "s1": (0.0, -1.0),
        "s2": (0.01, -2.0),
    }
    ax, ay = 0.0, 1.0
    merged = _merge_overlapping_chains(
        [{"n1", "n2"}, {"n3"}, {"s1", "s2"}], near, ax, ay
    )
    assert len(merged) == 2
    assert set(merged[0]) == {"n1", "n2", "n3"}
    assert set(merged[1]) == {"s1", "s2"}


def test_merge_overlapping_chains_single_chain_unchanged():
    near = {"a": (0.0, 1.0), "b": (0.0, 2.0)}
    out = _merge_overlapping_chains([{"a", "b"}], near, 0.0, 1.0)
    assert out == [{"a", "b"}]


def _stops_df():
    return pd.DataFrame(
        {
            "stop_id": ["s1", "s2", "s3"],
            "stop_name": [
                "Winston Churchill Blvd At A",
                "Winston Churchill Blvd At B",
                "Winston Churchill Rd At C",
            ],
            "stop_lat": [43.58, 43.59, 43.60],
            "stop_lon": [-79.75, -79.75, -79.75],
        }
    )


def test_nearest_stop_name_returns_closest():
    stops = _stops_df()
    geo = {"s1": (43.58, -79.75), "s2": (43.59, -79.75), "s3": (43.60, -79.75)}
    # Terminal "at" s1 (distance 0): s1 wins.
    assert _nearest_stop_name({"s1", "s2", "s3"}, geo, stops, 43.58, -79.75) == (
        "Winston Churchill Blvd At A"
    )


def test_corridor_display_prefers_majority_spelling():
    stops = _stops_df()
    near = {"s1": (0.0, 0.0), "s2": (0.0, 1.0), "s3": (0.0, 2.0)}
    # 2 of 3 stops spell "Blvd" -> it wins over "Rd".
    assert _corridor_display(stops, near, "winston churchill") == (
        "Winston Churchill Blvd"
    )


def test_corridor_display_falls_back_to_title_case():
    stops = _stops_df()
    assert _corridor_display(stops, {}, "some other corridor") == "Some Other Corridor"


def test_seam_story_full_narrative():
    legs = [
        {"side": "S", "n_stops": 9, "routes": ["10", "45", "109"]},
        {"side": "N", "n_stops": 7, "routes": ["38", "43"]},
    ]
    story = _seam_story(
        "Meadowvale Town Centre",
        "Winston Churchill Blvd",
        legs,
        term_legs=[0, 1],
        terminating={"10", "45", "109", "38", "43"},
    )
    assert "Routes 10, 109, 45 terminate" in story
    assert "from the south" in story
    assert "no route runs through" in story


def test_seam_story_with_through_leg_beyond():
    legs = [
        {"side": "S", "n_stops": 5, "routes": ["10"]},
        {"side": "N", "n_stops": 4, "routes": ["49"]},
    ]
    story = _seam_story("T", "Corridor", legs, term_legs=[0], terminating={"10"})
    assert "Route 10 terminates at T from the south" in story
    assert "Corridor continues north (4 stops served by Route 49)" in story


# ---- _corridor_seams_uncached on a synthetic feed ----------------------------------

MM = (43.58375, -79.758634)  # Meadowvale Town Centre coordinates


def _synthetic_feed():
    """A tiny feed around Meadowvale TC encoding one real seam.

    Winston Churchill corridor: stops south of the terminal served only by
    routes 10/45 (trips dying at the terminal), stops north served only by
    route 38. No trip serves stops on both sides -> two legs, no through
    service.
    """
    stops = pd.DataFrame(
        {
            "stop_id": [
                "T1",  # terminal platform
                "S1",
                "S2",  # south leg (Winston Churchill Blvd)
                "N1",
                "N2",  # north leg (Winston Churchill Blvd)
            ],
            "stop_name": [
                "Meadowvale Town Centre Bus Terminal Platform A",
                "Winston Churchill Blvd At South Stop",
                "Winston Churchill Blvd At Far South Stop",
                "Winston Churchill Blvd At North Stop",
                "Winston Churchill Blvd At Far North Stop",
            ],
            "stop_lat": [MM[0], MM[0] - 0.01, MM[0] - 0.02, MM[0] + 0.01, MM[0] + 0.02],
            "stop_lon": [MM[1], MM[1], MM[1], MM[1], MM[1]],
        }
    )
    trips = pd.DataFrame(
        {
            "trip_id": ["T10", "T45", "T38"],
            "route_id": ["R10", "R45", "R38"],
            "service_id": ["C1", "C1", "C1"],
        }
    )
    routes = pd.DataFrame(
        {
            "route_id": ["R10", "R45", "R38"],
            "route_short_name": ["10", "45", "38"],
        }
    )
    stop_times = pd.DataFrame(
        {
            "trip_id": ["T10", "T10", "T10", "T45", "T45", "T38", "T38", "T38"],
            "stop_id": ["T1", "S1", "S2", "T1", "S2", "T1", "N1", "N2"],
            "stop_sequence": [1, 2, 3, 1, 2, 1, 2, 3],
            "departure_time": ["08:00:00"] * 8,
        }
    )
    return {"stops": stops, "trips": trips, "routes": routes, "stop_times": stop_times}


def test_synthetic_feed_detects_seam(monkeypatch):
    feed = _synthetic_feed()
    monkeypatch.setattr("app.corridor_gaps.load_feed", lambda: feed, raising=False)
    monkeypatch.setattr("app.corridor_gaps.load_ridership", lambda: {"R10": 100.0})
    monkeypatch.setattr(
        config,
        "TERMINALS",
        {"Meadowvale Town Centre": MM},
    )
    seams = _corridor_seams_uncached(feed)
    assert seams, "expected the synthetic seam to be detected"
    seam = seams[0]
    assert seam["terminal"].startswith("Meadowvale Town Centre")
    assert "Winston Churchill" in seam["corridor"]
    assert len(seam["legs"]) == 2
    # Trip-level connectivity: T10 serves both south stops (one chain),
    # T38 starts at the terminal and runs north. No trip serves both sides.
    assert {"R10", "R45", "R38"} <= set(seam["terminating_routes"])
    # Boardings join by the leg routes' IDs (R10/R45/R38), mirroring the feed.
    assert seam["boardings"] == 100
    # Story names the terminal and both sides (corridor name only appears
    # when one leg is a through continuation, not when both terminate).
    assert "Meadowvale Town Centre" in seam["story"]
    assert "from the south" in seam["story"] and "from the north" in seam["story"]


def test_synthetic_feed_through_route_prevents_seam(monkeypatch):
    """One trip serving both sides merges the legs -> no seam."""
    feed = _synthetic_feed()
    through = pd.DataFrame(
        {
            "trip_id": ["T99", "T99", "T99", "T99"],
            "stop_id": ["S2", "S1", "T1", "N1"],
            "stop_sequence": [1, 2, 3, 4],
            "departure_time": ["09:00:00"] * 4,
        }
    )
    trips = pd.DataFrame(
        {
            "trip_id": ["T10", "T45", "T38", "T99"],
            "route_id": ["R10", "R45", "R38", "R99"],
            "service_id": ["C1", "C1", "C1", "C1"],
        }
    )
    routes = pd.DataFrame(
        {
            "route_id": ["R10", "R45", "R38", "R99"],
            "route_short_name": ["10", "45", "38", "99"],
        }
    )
    feed = {
        **feed,
        "trips": trips,
        "routes": routes,
        "stop_times": pd.concat([feed["stop_times"], through], ignore_index=True),
    }
    monkeypatch.setattr("app.corridor_gaps.load_feed", lambda: feed, raising=False)
    monkeypatch.setattr("app.corridor_gaps.load_ridership", lambda: {})
    monkeypatch.setattr(config, "TERMINALS", {"Meadowvale Town Centre": MM})
    # The through trip serves stops on both sides of the terminal, so the
    # corridor's stop graph becomes one connected component -> one leg -> no
    # seam is possible.
    assert _corridor_seams_uncached(feed) == []
