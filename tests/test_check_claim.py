"""Tests for the claim-check CLI (scripts/check_claim.py).

The tool exists because agents asserted service claims from route *names*
and stale documents (Route 109 ≠ Meadowvale Business Park; Lisgar GO does
have a feeder). These tests pin the behaviors that make its verdicts
trustworthy: station→platform resolution (the feed's place_* rows are not
parent-linked), the serves-join math, and verdict/exit-code semantics.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_claim import Feed, _haversine, _route_sort_key, main


def _tiny_feed() -> Feed:
    """Feed with two nearby platforms + one unlinked station + one far stop.

    Layout: station `place_alpha` (location_type=1) sits ~50m from platform
    A1 (served by route 9) and ~80m from A2 (served by nothing); a decoy
    platform B1 named "Alpha Rd" sits 5km away. No parent_station links —
    matching the real feed's defect.
    """
    feed = Feed.__new__(Feed)
    feed.stops = pd.DataFrame(
        {
            "stop_id": ["A1", "A2", "B1", "place_alpha"],
            "stop_name": [
                "Alpha Terminal Platform 1",
                "Alpha Terminal Platform 2",
                "Alpha Rd At Far St",
                "Alpha Station",
            ],
            "stop_lat": [43.60000, 43.60060, 43.64500, 43.60030],
            "stop_lon": [-79.60000, -79.60000, -79.60000, -79.60000],
            "location_type": ["0", "0", "0", "1"],
        }
    )
    feed.routes = pd.DataFrame(
        {
            "route_id": ["r9"],
            "route_short_name": ["9"],
            "route_long_name": ["Alpha Line"],
        }
    )
    feed.trips = pd.DataFrame(
        {"trip_id": ["t1", "t2"], "route_id": ["r9", "r9"], "direction_id": [0, 0]}
    )
    feed.st = pd.DataFrame(
        {
            "trip_id": ["t1", "t1", "t2"],
            "route_id": ["r9"] * 3,
            "direction_id": [0] * 3,
            "stop_id": ["A1"] * 3,
            "stop_name": ["Alpha Terminal Platform 1"] * 3,
            "stop_lat": [43.6] * 3,
            "stop_lon": [-79.6] * 3,
            "route_short_name": ["9"] * 3,
            "route_long_name": ["Alpha Line"] * 3,
            "arrival_time": ["10:05:00", "10:20:00", "11:00:00"],
        }
    )
    feed.routes_by_short = {"9": feed.routes}
    return feed


def test_haversine_sane() -> None:
    # ~50 m apart vertically
    d = _haversine(43.60000, -79.6, 43.60045, -79.6)
    assert 0.03 < d < 0.07


def test_route_sort_key_numeric_first() -> None:
    assert _route_sort_key("2") < _route_sort_key("10") < _route_sort_key("109")
    assert _route_sort_key("109") < _route_sort_key("C") or _route_sort_key(
        "109"
    ) < _route_sort_key("z9")


def test_platform_resolution_for_unlinked_station() -> None:
    feed = _tiny_feed()
    row = feed.stops[feed.stops.stop_id == "place_alpha"].iloc[0]
    plats = feed._platform_ids(row)
    assert "A1" in plats and "A2" in plats
    assert "B1" not in plats, "far decoy must not join the station"
    assert "place_alpha" not in plats or plats == ["place_alpha"]  # station excluded


def test_serves_station_resolves_to_platform_trips(capsys) -> None:
    feed = _tiny_feed()
    rc = main(["serves", "9", "Alpha Station"], feed=feed)
    out = capsys.readouterr().out
    assert "2/2 trips (100%)" in out, "station must inherit platform A1's trips"
    assert "VERDICT: CONFIRMED" in out
    assert rc == 0


def test_serves_route_that_skips_the_place(capsys) -> None:
    feed = _tiny_feed()
    # Route 9 only touches A1; asking for the unserved sibling platform → refuted
    rc = main(["serves", "9", "Alpha Terminal Platform 2"], feed=feed)
    out = capsys.readouterr().out
    assert "does NOT serve" in out
    assert "VERDICT: REFUTED" in out
    assert rc == 1


def test_place_without_fuzzy_is_exact(capsys) -> None:
    feed = _tiny_feed()
    main(["place", "Alpha Station"], feed=feed)
    out = capsys.readouterr().out
    assert "Alpha Station [place_alpha]" in out
    # station resolves via nearby platforms A1/A2, so route 9 appears
    assert "9" in out


def test_ambiguity_flag_on_multi_stop_serve(capsys) -> None:
    feed = _tiny_feed()
    main(["serves", "9", "Alpha Terminal"], feed=feed)
    out = capsys.readouterr().out
    assert "AMBIGUOUS" in out, "partial serve across same-named stops must warn"


def test_unknown_route_refutes(capsys) -> None:
    feed = _tiny_feed()
    rc = main(["serves", "999", "Alpha Station"], feed=feed)
    out = capsys.readouterr().out
    assert "VERDICT: REFUTED" in out
    assert rc == 1


def test_checked_stamp_present(capsys) -> None:
    main(["route", "9"], feed=_tiny_feed())
    out = capsys.readouterr().out
    assert "CHECKED:" in out and "check_claim.py" in out


def test_lost_refutes_when_stop_is_served(capsys) -> None:
    feed = _tiny_feed()
    rc = main(["lost", "A1"], feed=feed)
    out = capsys.readouterr().out
    assert rc == 1  # REFUTED — the claim "A1 is unserved" is false
    assert "IS served" in out


def test_lost_confirms_but_reports_walking_replacement(capsys) -> None:
    feed = _tiny_feed()
    rc = main(["lost", "A2", "--radius-m", "400"], feed=feed)
    out = capsys.readouterr().out
    assert rc == 0  # CONFIRMED — A2 is genuinely unserved as an id...
    assert "unserved as a stop_id" in out
    # ...but the replacement within walking distance is surfaced, with routes
    assert "A1" in out and "'9'" in out


def test_lost_reports_nothing_within_tiny_radius(capsys) -> None:
    feed = _tiny_feed()
    rc = main(["lost", "A2", "--radius-m", "10"], feed=feed)
    out = capsys.readouterr().out
    assert rc == 0
    assert "NOTHING served within 10 m" in out


def test_lost_flags_same_name_served_elsewhere(capsys) -> None:
    feed = _tiny_feed()
    # Give A1 the same name as the unserved A2: rename/pair detection must fire.
    feed.stops.loc[feed.stops.stop_id == "A1", "stop_name"] = (
        "Alpha Terminal Platform 2"
    )
    feed.st.loc[feed.st.stop_id == "A1", "stop_name"] = "Alpha Terminal Platform 2"
    rc = main(["lost", "A2", "--radius-m", "400"], feed=feed)
    out = capsys.readouterr().out
    assert rc == 0
    assert "same name (rename/directional pair)" in out
