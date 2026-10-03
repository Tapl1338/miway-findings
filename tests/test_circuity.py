"""
Unit tests for the circuity analyzer (GeoPandas / Shapely).

Verifies the circuity index math, the >1.4 flagging rule and the split-branch
geometry proposals against the real MiWay GTFS feed.
"""

import hashlib
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from app import circuity_analyzer, config
from app.cache import cached_compute
from app.circuity_analyzer import (
    _corridor_splice,
    _endpoint_label,
    _junction_label,
    _network_graph,
    _split_part_metrics,
    build_route_geometries,
    circuity_geojson,
    find_split_vertex,
    nearest_stop_name,
    propose_split,
    split_geometry,
    split_geometry_multi,
)
from app.geometry import haversine_km
from shapely.geometry import LineString


@pytest.fixture(scope="module")
def gdf():
    return build_route_geometries()


@pytest.fixture(scope="module")
def window_gdf():
    """Geometries for the all-day time window (the split-regression set)."""
    return build_route_geometries(*config.TIME_PERIODS["all_day"][1:])


# ``propose_split`` over the full network costs ~15-35 s cold and is
# deterministic for a given geometry set, so the proposal fixtures persist it
# to the analysis cache. ``cached_compute`` appends the GTFS fingerprint
# automatically; the source digest pins the analyzer/config code so an engine
# change never serves stale proposals.
_SRC_DIGEST = hashlib.sha1(
    Path(circuity_analyzer.__file__).read_bytes() + Path(config.__file__).read_bytes()
).hexdigest()[:12]


@pytest.fixture(scope="module")
def default_proposals(gdf):
    """Split proposals over the default geometry set, computed once.

    The split tests each used to re-run ``propose_split`` over the whole
    network (~15-25 s each); the proposals are read-only in every test, so
    one module-scoped build serves them all. The build is disk-cached so
    repeated runs do not re-pay it.
    """
    return cached_compute(
        key=f"test_split_proposals|v{_SRC_DIGEST}|default",
        compute=lambda: propose_split(gdf),
    )


@pytest.fixture(scope="module")
def window_proposals(window_gdf):
    """Split proposals over the all-day-window geometry set, computed once."""
    _label, ws, we = config.TIME_PERIODS["all_day"]
    return cached_compute(
        key=f"test_split_proposals|v{_SRC_DIGEST}|window_{ws}_{we}",
        compute=lambda: propose_split(window_gdf),
    )


def test_haversine_known_distance():
    # Toronto -> Mississauga roughly 20-25 km.
    d = haversine_km(43.6532, -79.3832, 43.5890, -79.6441)
    assert 15 < d < 35


def test_geometries_are_valid(gdf):
    assert len(gdf) > 20
    assert gdf.crs is not None
    assert (gdf.geometry.type == "LineString").all()
    assert gdf["circuity"].dropna().between(1.0, 10.0).all()


def test_circuity_never_below_one(gdf):
    """A route cannot be shorter than its endpoint straight line (c < 1)."""
    assert (gdf["circuity"] >= 1.0).all()


def test_flag_threshold(gdf):
    flagged = gdf[gdf["flagged"]]
    unflagged = gdf[~gdf["flagged"]]
    assert (flagged["circuity"] >= config.CIRCUITY_FLAG).all()
    assert (unflagged["circuity"] < config.CIRCUITY_FLAG).all()


def test_flagged_routes_exist(gdf):
    """The real feed should contain at least one flagged meandering route."""
    assert gdf["flagged"].sum() >= 1


def test_split_geometry_returns_two_branches(gdf):
    flagged = gdf[gdf["flagged"]]
    if flagged.empty:
        pytest.skip("No flagged routes to split")
    # Not every flagged route passes near a terminal (the split point must sit
    # at a hub), so find one that does.
    parts = None
    for _, row in flagged.iterrows():
        parts = split_geometry(row["geometry"])
        if parts is not None:
            break
    assert parts is not None, "expected at least one terminal-anchored split"
    assert set(parts.keys()) == {"trunk", "branch"}
    # The split branches share the split vertex.
    assert parts["trunk"].coords[-1] == parts["branch"].coords[0]


def test_loop_route_split_is_skipped():
    """A loop (start == end) has a ~0 endpoint chord, so no split proposal.

    Before the fix, loop routes produced a degenerate "trunk" from a terminal
    back to the *same* terminal (e.g. Route 16's "Malton GO -> Malton GO").
    """
    loop = LineString([(0, 0), (5, 5), (10, 0), (0, 0)])
    assert split_geometry(loop) is None


def test_same_terminal_trunk_is_rejected(monkeypatch):
    """A trunk whose two ends snap to the same terminal is meaningless.

    With a single terminal in the table every endpoint snaps to it, so any
    non-loop geometry must be rejected rather than proposing "Hub A -> Hub A".
    """
    monkeypatch.setattr(config, "TERMINALS", {"Hub A": (43.60, -79.60)})
    # Non-loop C-shape (~6.8 km endpoint separation, apex off the chord).
    geom = LineString([(-79.65, 43.55), (-79.62, 43.60), (-79.60, 43.60)])
    assert split_geometry(geom) is None


def test_endpoints_far_from_any_terminal_rejected(monkeypatch):
    """A split is rejected when no endpoint is near a designated hub.

    With two hubs but a route whose endpoints and meander are all kilometers
    away from both, _snap_to_terminal leaves them raw and the new distance
    validation rejects the proposal -- no trunk/feeder should stop in the
    middle of nowhere.
    """
    monkeypatch.setattr(
        config,
        "TERMINALS",
        {"Hub A": (43.60, -79.60), "Hub B": (43.55, -79.55)},
    )
    # C-shape: start (-79.70, 43.50), apex (-79.65, 43.65), end (-79.70, 43.60)
    # Nearest of the two hubs is ~5 km from every vertex -- well outside the
    # 0.6 km snap radius, so nothing snaps and the split is forbidden.
    geom = LineString([(-79.70, 43.50), (-79.65, 43.65), (-79.70, 43.60)])
    assert split_geometry(geom) is None


def test_split_point_far_from_terminal_accepted(monkeypatch):
    """A split can be accepted even when the split point is far from a hub,
    as long as the route endpoints anchor to hubs.

    The split point (the meander apex) is an interior cut, not a route
    endpoint. Requiring it to be at a hub would reject almost every
    meandering route, since the apex is by definition the point farthest from
    the endpoint chord. The honest endpoint label (nearest stop name) is what
    keeps the panel truthful there, not a rejection.
    """
    monkeypatch.setattr(
        config,
        "TERMINALS",
        {
            "Hub A": (43.55, -79.652),  # ~0.2 km from route start
            "Hub B": (43.55, -79.552),  # ~0.2 km from route end
        },
    )
    # Start/end are 0.2 km from hubs; apex is ~5 km from either hub.
    geom = LineString([(-79.652, 43.551), (-79.600, 43.600), (-79.552, 43.551)])
    result = split_geometry(geom)
    assert result is not None
    assert set(result.keys()) == {"trunk", "branch"}


def test_endpoint_label_is_honest(monkeypatch):
    """Endpoint labels must match what the map draws, not the nearest hub.

    Regression: the interior split point (trunk end / feeder start) is the
    meander apex and can sit kilometers from any hub. The old code reported
    the nearest terminal's name there regardless of distance, so Route 36's
    panel claimed the trunk reached Winston Churchill Transitway while the
    map showed it ending at Ridgeway & Laird. Labels now qualify by distance:
    plain hub name when snapped, "Hub (d km)" when short of it, and the
    nearest GTFS stop name when there is no hub nearby.
    """
    monkeypatch.setattr(config, "TERMINALS", {"Hub A": (43.60, -79.60)})
    # 1) Right at the hub (within the 0.6 km snap radius) -> plain name.
    assert _endpoint_label(43.60005, -79.60005) == "Hub A"
    # 2) Near the hub (0.6-1.5 km) -> distance-qualified, never a bare claim.
    near = _endpoint_label(43.6070, -79.6000)  # ~0.78 km north of the hub
    assert near.startswith("Hub A (") and near.endswith(" km)")
    # 3) Far from any hub -> nearest stop name (monkeypatched so the test does
    #    not need the real feed), never the name of a distant hub.
    from app import circuity_geo

    monkeypatch.setattr(
        circuity_geo,
        "nearest_stop_name",
        lambda lat, lon: "Ridgeway Dr At Laird Rd",
    )
    assert _endpoint_label(43.6300, -79.6000) == "Ridgeway Dr At Laird Rd"


def test_find_split_vertex_on_bowtie():
    # A C-shape should split at the far apex.
    geom = LineString([(0, 0), (10, 0), (10, 10), (0, 10)])
    found = find_split_vertex(geom)
    assert found is not None
    idx, _pt = found
    assert idx in (1, 2)


def test_circuity_geojson_structure():
    fc = circuity_geojson()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) > 0
    assert "circuity" in fc["features"][0]["properties"]
    assert fc["metadata"]["flag_threshold"] == config.CIRCUITY_FLAG
    assert fc["metadata"]["flagged_count"] >= 1


@pytest.mark.slow
def test_proposed_split_contains_geometry_and_score(gdf, default_proposals):
    proposals = default_proposals
    flagged_count = int(gdf["flagged"].sum())
    assert len(proposals) <= flagged_count
    if proposals:
        p = proposals[0]
        assert "trunk_geometry" in p
        assert "trunk_circuity" in p and "trunk_length_km" in p
        assert "branches" in p and len(p["branches"]) >= 1
        b = p["branches"][0]
        for key in (
            "geometry",
            "circuity",
            "length_km",
            "start_terminal",
            "end_terminal",
        ):
            assert key in b


@pytest.mark.slow
def test_some_routes_propose_multiple_branches(window_proposals):
    """A route may decompose into a trunk + several feeders when each further
    split keeps meeting the quality bar (the winding part is itself re-split).

    Route 10 / 57 are the canonical examples today; the invariant is that at
    least one flagged route proposes multiple branches and every branch is a
    real, finite segment.
    """
    proposals = window_proposals
    multi = [p for p in proposals if len(p["branches"]) >= 2]
    assert multi, "expected at least one route to propose multiple branches"
    # Every branch must be a real segment with finite, sane circuity.
    for p in proposals:
        for b in p["branches"]:
            assert b["circuity"] >= 1.0
            assert b["length_km"] >= config.MIN_BRANCH_KM - 1e-6


@pytest.mark.slow
def test_corridor_route_38_borrows_route_44_alignment(window_gdf, window_proposals):
    """Route 38 is the canonical corridor-splice case: it leaves Argentia Rd
    for the Lisgar GO / Meadowpine wander and rejoins the corridor near the
    end. Its proposal must borrow Route 44's direct Argentia Rd alignment for
    the trunk -- the merge-point design -- and keep the dropped span as a
    branch, never cutting at a random meander apex or inventing street
    geometry.
    """
    proposals = window_proposals
    p38 = next((p for p in proposals if p["route_short_name"] == "38"), None)
    assert p38 is not None, "Route 38 should be proposed"
    # The trunk borrows Route 44's direct corridor (the user's merge point:
    # 38 stops serving the Lisgar wander and rides the 44's Argentia routing).
    assert p38["donor_route"] == "44"
    # The trunk runs end-to-end between real terminals.
    assert p38["trunk_start_terminal"] in config.TERMINALS
    assert p38["trunk_end_terminal"] in config.TERMINALS
    # The trunk is meaningfully more direct than the full route.
    full = float(window_gdf.set_index("route_id").loc["38", "circuity"])
    assert full - p38["trunk_circuity"] >= config.MIN_TRUNK_IMPROVEMENT
    # The branch keeps the dropped service: real, finite, long enough to be
    # its own run. (It stays winding -- that is the point: the winding is
    # local service, not the arterial trunk.)
    assert len(p38["branches"]) == 1
    b = p38["branches"][0]
    assert b["length_km"] >= config.MIN_BRANCH_KM - 1e-6
    assert b["circuity"] >= 1.0


@pytest.mark.slow
def test_corridor_splice_38_junction_on_argentia(default_proposals):
    """The 38's splice junction is the merge point on Argentia Rd -- where
    the route actually leaves the corridor -- not a random meander apex.

    The branch is the dropped span, so its first vertex is junction A: the
    point where the trunk stops following the route and the branch carries on
    serving the old stops.
    """
    proposals = default_proposals
    p38 = next((p for p in proposals if p["route_short_name"] == "38"), None)
    assert p38 is not None and p38["donor_route"] == "44"
    lon, lat = p38["branches"][0]["geometry"][0]
    assert "Argentia" in nearest_stop_name(lat, lon), (
        f"junction should sit on Argentia Rd, got {nearest_stop_name(lat, lon)}"
    )


def _route10_junction_point():
    """Route 10's junction A: where the 10 leaves the 66 corridor.

    This point is 1.3 km from Westwood Square and sits on Bristol Rd -- the
    label must say where it actually is, not the distant hub.
    """
    return 43.60486, -79.669799


def test_junction_label_names_the_stop_not_a_distant_hub():
    """A junction 1.3 km from Westwood Square must not be labelled with the
    hub name -- it is a road merge point on Bristol Rd."""
    lat, lon = _route10_junction_point()
    label = _junction_label(lat, lon)
    assert label == "Bristol Rd At Fairwind Dr", label
    assert "Westwood" not in label
    assert " km)" not in label


@pytest.mark.slow
def test_splice_junctions_are_wgs84_with_labels(window_proposals):
    """Spliced proposals surface both corridor junctions for the map dots.

    Junction A is where the route leaves the donor corridor (the branch's
    first vertex), junction B where it rejoins (the branch's last vertex).
    The coordinates must be real WGS84 lon/lat -- the first implementation
    leaked projected UTM metres here, which made the dots land in the ocean
    and the labels name random stops -- and each carries a nearest-stop name.
    """
    proposals = window_proposals
    spliced = [p for p in proposals if p.get("donor_route")]
    assert spliced, "expected at least one corridor-splice proposal"
    for p in spliced:
        j = p.get("splice_junctions")
        assert j is not None and len(j) == 2, p["route_short_name"]
        for x in j:
            assert -180 <= x["lon"] <= 180, (p["route_short_name"], x)
            assert -90 <= x["lat"] <= 90, (p["route_short_name"], x)
            assert isinstance(x["label"], str) and x["label"], (
                p["route_short_name"],
                x,
            )
            # Junctions are road merge points: a label may be a hub name only
            # when the point is genuinely at that hub, never the misleading
            # "Hub (1.3 km)" shortfall tier (Route 10's Westwood Square case).
            assert " km)" not in x["label"], (p["route_short_name"], x)
        # The junctions are exactly the branch's endpoints (rounded to 6dp).
        b = p["branches"][0]["geometry"]
        assert abs(j[0]["lon"] - b[0][0]) < 1e-5, p["route_short_name"]
        assert abs(j[0]["lat"] - b[0][1]) < 1e-5, p["route_short_name"]
        assert abs(j[1]["lon"] - b[-1][0]) < 1e-5, p["route_short_name"]
        assert abs(j[1]["lat"] - b[-1][1]) < 1e-5, p["route_short_name"]
        # The feeder row shows the same honest names as the junction dots.
        b0 = p["branches"][0]
        assert b0["start_terminal"] == j[0]["label"], p["route_short_name"]
        assert b0["end_terminal"] == j[1]["label"], p["route_short_name"]


@pytest.mark.slow
def test_splice_junctions_are_near_a_stop_the_route_serves(window_proposals):
    """Every splice junction must be reachable: a bus can only be where the
    route itself stops.

    Regression: Route 110's old 44-splice had a junction 980 m from the 110's
    own nearest stop -- it sat mid-Hwy 403 at Mississauga Rd, where there is
    no on/off ramp -- so the "borrowed corridor" was unreachable by any bus.
    The gate (``CORRIDOR_JUNCTION_STOP_KM``) rejects any candidate whose
    leave/rejoin points are not near a stop the spliced route actually serves.
    """

    from app.gtfs_loader import load_feed

    feed = load_feed()
    stops = feed["stops"]
    st = feed["stop_times"].merge(feed["trips"][["trip_id", "route_id"]], on="trip_id")
    routes = feed["routes"][["route_id", "route_short_name"]].drop_duplicates(
        "route_id"
    )
    st = st.merge(routes, on="route_id")
    own_stops = {}
    for rn, grp in st.groupby("route_short_name"):
        g2 = grp.merge(stops[["stop_id", "stop_lat", "stop_lon"]], on="stop_id")
        own_stops[rn] = (
            g2["stop_lat"].to_numpy(float),
            g2["stop_lon"].to_numpy(float),
        )

    proposals = window_proposals
    spliced = [p for p in proposals if p.get("donor_route")]
    assert spliced, "expected at least one corridor-splice proposal"
    for p in spliced:
        rn = p["route_short_name"]
        slat, slon = own_stops[rn]
        for j in p["splice_junctions"]:
            d = float(haversine_km(slat, slon, j["lat"], j["lon"]).min() * 1000.0)
            assert d <= config.CORRIDOR_JUNCTION_STOP_KM * 1000.0, (
                rn,
                j["label"],
                round(d),
            )

    # The 110 no longer borrows the 44 at an unreachable mid-403 junction; if
    # it still splices at all, its junctions are real stops it serves.
    p110 = [p for p in spliced if p["route_short_name"] == "110"]
    for p in p110:
        slat, slon = own_stops["110"]
        for j in p["splice_junctions"]:
            d = float(haversine_km(slat, slon, j["lat"], j["lon"]).min() * 1000.0)
            assert d <= config.CORRIDOR_JUNCTION_STOP_KM * 1000.0, (j, round(d))


@pytest.mark.slow
def test_splice_junctions_sit_on_the_donor_alignment(window_proposals):
    """Every splice junction is where the two alignments actually MEET.

    Regression: the old junction pick (the touch-radius run's outer ends)
    let a junction sit far from the donor whenever the donor merely ran
    parallel a street or two away -- Route 10's trunk left Bristol Rd 238 m
    after the 66 alignment had already diverged and rejoined 138 m before
    its end, so the trunk was stitched with invented straight-line
    connectors: the doubled-back kink the map drew at Bristol Rd & Fairwind
    Dr. Junctions now come from the run vertices that lie ON the donor
    (within ``CORRIDOR_MERGE_TOL_KM``), so the stitch is a real
    street-to-street hop and every drawn line follows streets some MiWay
    bus drives.
    """
    from app.circuity_analyzer import (
        _all_route_shape_geometries,
        _to_projected,
    )
    from app.gtfs_loader import load_feed
    from shapely.geometry import LineString, Point

    feed = load_feed()
    id_to_name = dict(
        zip(
            feed["routes"]["route_id"].astype(str),
            feed["routes"]["route_short_name"].astype(str),
        )
    )
    shapes = _all_route_shape_geometries()
    donor_geoms: dict[str, list] = {}
    for rid, grp in shapes.groupby("route_id"):
        donor_geoms.setdefault(id_to_name.get(str(rid), ""), []).extend(
            _to_projected(g) for g in grp["geometry"]
        )

    proposals = window_proposals
    spliced = [p for p in proposals if p.get("donor_route")]
    assert spliced, "expected at least one corridor-splice proposal"
    tol_m = config.CORRIDOR_MERGE_TOL_KM * 1000.0 + 1.0  # + rounding slack
    for p in spliced:
        geoms = donor_geoms.get(p["donor_route"], [])
        assert geoms, (p["route_short_name"], p["donor_route"])
        for j in p["splice_junctions"]:
            putm = _to_projected(LineString([(j["lon"], j["lat"])] * 2))
            d = min(g.distance(Point(list(putm.coords)[0])) for g in geoms)
            assert d <= tol_m, (
                p["route_short_name"],
                p["donor_route"],
                j["label"],
                round(d),
            )

    # Route 10 keeps its honest 66-splice: both junctions sit on the 66
    # alignment itself (the shared Bristol Rd crossing and the shared
    # City Centre crossing), so the trunk never walks back over road it
    # already covered nor jumps cross-country to the terminal.
    p10 = next((p for p in spliced if p["route_short_name"] == "10"), None)
    assert p10 is not None, "Route 10 should still propose a splice"
    assert p10["donor_route"] == "66"
    for j in p10["splice_junctions"]:
        putm = _to_projected(LineString([(j["lon"], j["lat"])] * 2))
        d = min(g.distance(Point(list(putm.coords)[0])) for g in donor_geoms["66"])
        assert d <= tol_m, (j, round(d))


def test_corridor_splice_whole_route_detour_rejected(gdf):
    """A splice whose 'detour' is most of the route is rejected.

    Regression: before the ``CORRIDOR_MAX_DETOUR_SHARE`` gate, Route 16 -- a
    whole-route zigzag that merely touches a donor corridor at its two ends --
    got a bogus splice replacing most of its length with a fragment of another
    route's shape. A detour off an arterial is a minority of the route; when
    it is not, the route has no main line to shorten and the meander strategy
    is the honest answer.
    """
    row = gdf[gdf["route_short_name"] == "16"].iloc[0]
    assert _corridor_splice(row["geometry"], route_id=row["route_id"]) is None


def test_corridor_splice_improvement_gate_is_exact(gdf):
    """The improvement gate measures the REAL trunk geometry, not the O(1)
    "full minus saving" estimate.

    Regression: the estimate ignores the short connector segments between the
    route's junction vertices and their projections on the donor corridor, so
    a candidate can pass the estimate at ~0.20x while its drawn trunk only
    improves ~0.17x -- below the bar. Whatever wins, the numbers the
    dashboard shows must clear ``MIN_TRUNK_IMPROVEMENT``.

    Route 108 is the standing example: its best candidate estimates ~0.20x
    but measures below the bar, so it is rejected even though the estimate
    says otherwise. Route 7 used to be the second example, but once the
    structural gates were relaxed (ratio 1.5 -> 1.35) it finds a genuinely
    better candidate (donor 107) that measures ~0.31x -- the exact gate must
    hold for it too.
    """
    row = gdf[gdf["route_short_name"] == "108"].iloc[0]
    assert _corridor_splice(row["geometry"], route_id=row["route_id"]) is None

    row7 = gdf[gdf["route_short_name"] == "7"].iloc[0]
    parts = _corridor_splice(row7["geometry"], route_id=row7["route_id"])
    if parts is not None:
        full_c = circuity_analyzer._split_part_metrics(row7["geometry"])["circuity"]
        trunk_c = circuity_analyzer._split_part_metrics(parts["trunk"])["circuity"]
        assert full_c - trunk_c >= config.MIN_TRUNK_IMPROVEMENT - 1e-6, (
            "Route 7's served splice must clear the bar by its measured geometry"
        )


@pytest.mark.slow
def test_proposed_splits_are_meaningful(window_gdf, window_proposals):
    """No garbage proposals: every kept split's trunk must be at least
    MIN_TRUNK_IMPROVEMENT more direct than the full route.

    Regression: the farthest-from-chord split vertex is noise on mildly
    winding routes, producing "trunks" as winding as (or worse than) the
    whole route (e.g. Route 26's "trunk" at 2.14x vs the route's 1.42x).
    Such proposals must be dropped, not served to the dashboard.
    """
    proposals = window_proposals
    # The quality gate must leave at least the headline splits (Route 36).
    assert len(proposals) >= 5
    full = window_gdf.set_index("route_id")["circuity"]
    for p in proposals:
        improvement = float(full[p["route_id"]]) - p["trunk_circuity"]
        assert improvement >= config.MIN_TRUNK_IMPROVEMENT - 1e-6, (
            f"Route {p['route_short_name']}: trunk only {p['trunk_circuity']}x "
            f"vs full route {float(full[p['route_id']])}x (gain {improvement:.2f})"
        )


def test_output_is_serializable_json(gdf):
    import json

    fc = circuity_geojson()
    json.dumps(fc)  # must not raise


def test_period_windows_change_route_set():
    """Rush-hour-only routes drop out of the midday / late-night views."""
    from app import config

    am = build_route_geometries(*config.TIME_PERIODS["am_rush"][1:])
    midday = build_route_geometries(*config.TIME_PERIODS["midday"][1:])
    late = build_route_geometries(*config.TIME_PERIODS["late_night"][1:])

    am_routes = set(am["route_short_name"].astype(str))
    midday_routes = set(midday["route_short_name"].astype(str))
    late_routes = set(late["route_short_name"].astype(str))

    # The network is never empty in any period…
    assert am_routes and midday_routes and late_routes
    # …but the set of running routes differs across the day.
    assert am_routes != midday_routes or midday_routes != late_routes


def test_period_windows_filter_geojson():
    """circuity_geojson honours a time window."""
    from app import config

    fc = circuity_geojson(*config.TIME_PERIODS["am_rush"][1:])
    assert fc["metadata"]["flagged_count"] >= 1


def test_network_graph_builds_and_connects(gdf):
    """The street-network graph covers the real network and every route's
    endpoints are reachable within it (via the route's own shape)."""
    graph = _network_graph()
    assert graph["xy"].shape[0] > 5000  # thousands of street vertices
    assert sum(len(a) for a in graph["adj"]) > 10000  # real edges + connectors

    node_id = graph["node_id"]
    # A representative route's endpoints must exist as graph nodes, so a
    # shortest path between them always exists (the route's own shape is in
    # the graph).
    for rid in ("36", "73", "31"):
        row = gdf[gdf["route_id"] == rid].iloc[0]
        coords = list(row["geometry"].coords)
        assert (round(coords[0][0]), round(coords[0][1])) in node_id
        assert (round(coords[-1][0]), round(coords[-1][1])) in node_id


@pytest.mark.slow
def test_network_trunk_is_more_direct_than_full_route(gdf):
    """A network-routed trunk must actually improve the route: at least
    MIN_TRUNK_IMPROVEMENT more direct and NETWORK_MIN_SAVING_KM shorter, and
    its ends must be the route's own terminals (pinned, not drifted)."""
    found = False
    for _, row in gdf[gdf["flagged"]].iterrows():
        parts = split_geometry_multi(row["geometry"], route_id=row["route_id"])
        if parts is None or parts.get("trunk_source") != "network":
            continue
        found = True
        full = _split_part_metrics(row["geometry"])
        trunk = _split_part_metrics(parts["trunk"])
        assert (
            full["circuity"] - trunk["circuity"] >= config.MIN_TRUNK_IMPROVEMENT - 1e-6
        )
        assert (
            full["length_km"] - trunk["length_km"]
            >= config.NETWORK_MIN_SAVING_KM - 1e-6
        )
        # Ends stay at the route's terminals (within a few metres of the
        # pinned start/end coordinates).
        rc = list(row["geometry"].coords)
        tc = list(parts["trunk"].coords)
        assert abs(tc[0][0] - rc[0][0]) < 5 and abs(tc[0][1] - rc[0][1]) < 5
        assert abs(tc[-1][0] - rc[-1][0]) < 5 and abs(tc[-1][1] - rc[-1][1]) < 5
        break
    assert found, "Expected at least one network-routed trunk proposal"


@pytest.mark.slow
def test_network_trunk_transfers_only_at_served_stops(gdf, default_proposals):
    """A network-routed trunk may only change corridors where a bus can
    physically board the corridor it joins.

    Regression: Route 36's trunk used to switch from Route 13's Glen Erin Dr
    shape onto Route 109's Hwy 403 shape at Glen Erin Dr -- 478 m from 109's
    nearest stop, where no on/off ramp exists -- because the graph allowed
    transferring at any shared node. The corridor-aware router gates every
    corridor change on the joined route having a stop within
    ``NETWORK_CONNECTOR_STOP_KM`` of the transfer node.

    Iterates the shared proposal set (network-sourced trunks only) instead of
    re-decomposing every flagged route -- each decomposition pays the full
    network routing, so the old loop cost ~25 s per test run.
    """
    graph = _network_graph()
    xy, adj = graph["xy"], graph["adj"]
    eligible = graph["eligible_routes"]
    edge_routes = graph["edge_routes"]
    checked = 0
    for p in default_proposals:
        if p.get("trunk_source") != "network":
            continue
        row = gdf[gdf["route_id"] == p["route_id"]].iloc[0]
        # Re-run the router between the route's terminals (same snapping the
        # trunk uses) so we can walk the *state* path with its corridor modes.
        geom = row["geometry"]
        projected = circuity_analyzer._looks_projected(geom)
        work = geom if projected else circuity_analyzer._to_projected(geom)
        coords = list(work.coords)
        start, end = coords[0], coords[-1]
        snap_m = config.NETWORK_CONNECT_KM * 1000.0 * 2.0
        d0 = np.hypot(xy[:, 0] - start[0], xy[:, 1] - start[1])
        d1 = np.hypot(xy[:, 0] - end[0], xy[:, 1] - end[1])
        if d0.min() > snap_m or d1.min() > snap_m:
            continue
        s_node = int(np.argmin(d0))
        e_node = int(np.argmin(d1))
        xs = np.array([c[0] for c in coords])
        ys = np.array([c[1] for c in coords])
        margin = config.NETWORK_SEARCH_MARGIN_KM * 1000.0
        x0, x1 = float(xs.min()) - margin, float(xs.max()) + margin
        y0, y1 = float(ys.min()) - margin, float(ys.max()) + margin

        def in_region(nid, x0=x0, x1=x1, y0=y0, y1=y1):
            px, py = xy[nid]
            return x0 <= px <= x1 and y0 <= py <= y1

        path = circuity_analyzer._shortest_network_path(
            adj, edge_routes, eligible, s_node, e_node, in_region
        )
        assert path is not None
        checked += 1
        # Walk exactly like the router's state machine: connector edges reset
        # the mode to empty; a corridor change must be gated by eligibility.
        mode = None
        for a, b in itertools.pairwise(path):
            er = edge_routes.get((a, b) if a < b else (b, a))
            if er is None or not er:
                mode = frozenset()
                continue
            if mode is None:
                mode = er
            elif er & mode:
                mode = er & mode
            else:
                assert er & eligible[a], (
                    f"Route {row['route_short_name']}: corridor change at node "
                    f"{a} where the joined route has no stop nearby"
                )
                mode = er
    assert checked >= 1, "Expected at least one network-routed trunk to check"


@pytest.mark.slow
def test_loop_routes_never_propose_identity_trunk(gdf, default_proposals):
    """Regression: loop routes (start ~= end, e.g. Route 16 around Westwood
    Square) must not come back as a "trunk" identical to the full route. The
    meander fallback returns a single segment and every strategy must drop it.

    Checks the shared proposal set (which is what the dashboard serves): an
    identity trunk cannot clear the improvement gate, so any proposal that
    reached the output must be strictly shorter than its full route. Reusing
    the proposals avoids re-decomposing every flagged route (~20 s).
    """
    full_km = gdf.set_index("route_id")["length_km"]
    for p in default_proposals:
        assert p["trunk_length_km"] < float(full_km[p["route_id"]]) - 0.1, (
            f"Route {p['route_short_name']}: trunk is the full route"
        )


# ---- pure geometry helpers (merged from the former test_circuity_coverage.py;
# the label tiers, find_split_vertex and _split_part_metrics themselves are
# already covered by the real-feed tests above) ----


def test_projection_round_trip_wgs84_local_wgs84():
    geom = LineString([(-79.64, 43.59), (-79.63, 43.60)])
    back = circuity_analyzer._to_wgs84(circuity_analyzer._to_projected(geom))
    assert back.coords[0] == pytest.approx(geom.coords[0], abs=1e-6)


def test_geodesic_length_m_positive_and_sane():
    # ~1 degree of latitude ≈ 111 km.
    geom = LineString([(-79.64, 43.50), (-79.64, 43.51)])
    assert 1_000 < circuity_analyzer._geodesic_length_m(geom) < 1_300


def test_pairwise_max_km_measures_diameter():
    lat = np.array([43.50, 43.52, 43.51])
    lon = np.array([-79.70, -79.70, -79.70])
    d = circuity_analyzer._pairwise_max_km(lat, lon)
    assert 2.0 < d < 2.5  # 0.02 deg of latitude ≈ 2.2 km


def test_route_geometry_sorts_and_dedupes():
    df = pd.DataFrame(
        {
            "shape_pt_lon": [-79.70, -79.69, -79.69, -79.68],
            "shape_pt_lat": [43.50, 43.51, 43.51, 43.52],
            "shape_pt_sequence": [1, 3, 2, 4],
        }
    )
    g = circuity_analyzer._route_geometry(df)
    # Sequence order (not row order); the duplicate middle vertex collapses.
    assert list(g.coords) == [(-79.70, 43.50), (-79.69, 43.51), (-79.68, 43.52)]


def test_route_geometry_rejects_single_point():
    with pytest.raises(ValueError):
        circuity_analyzer._route_geometry(
            pd.DataFrame(
                {
                    "shape_pt_lon": [-79.7],
                    "shape_pt_lat": [43.5],
                    "shape_pt_sequence": [1],
                }
            )
        )


def test_terminal_anchors_collapse_consecutive_same_terminal():
    lat, lon = config.TERMINALS["Cooksville GO"]
    # Three consecutive vertices near the same hub → one anchor; the far
    # vertex contributes none.
    coords = [
        (lon, lat),
        (lon + 0.0005, lat + 0.0005),
        (lon + 0.001, lat + 0.001),
        (-79.70, 43.60),
    ]
    anchors = circuity_analyzer._terminal_anchors(coords)
    assert len(anchors) == 1
    assert anchors[0][0] == 0
    assert anchors[0][1] == "Cooksville GO"


def test_decompose_segments_zero_budget_returns_input():
    geom = LineString([(-79.7, 43.5), (-79.69, 43.5)])
    assert circuity_analyzer._decompose_segments(geom, 0) == [geom]


def test_engine_digest_is_stable_12_hex():
    d1, d2 = circuity_analyzer._engine_digest(), circuity_analyzer._engine_digest()
    assert d1 == d2 and len(d1) == 12
    int(d1, 16)  # hex


def test_split_geometry_multi_dispatches_to_corridor_splice(monkeypatch):
    donor = {"trunk": LineString([(-79.7, 43.5), (-79.69, 43.51)])}
    monkeypatch.setattr(
        "app.circuity_trunk._corridor_splice", lambda g, route_id=None: donor
    )
    out = circuity_analyzer.split_geometry_multi(
        LineString([(-79.7, 43.5), (-79.68, 43.5)])
    )
    assert out is donor


def test_split_geometry_multi_dispatches_to_network_trunk(monkeypatch):
    routed = {"trunk": LineString([(-79.7, 43.5), (-79.69, 43.5)]), "branches": []}
    monkeypatch.setattr(
        "app.circuity_trunk._corridor_splice", lambda g, route_id=None: None
    )
    monkeypatch.setattr("app.circuity_trunk._corridor_segmentation", lambda g: None)
    monkeypatch.setattr("app.circuity_trunk._network_trunk", lambda g: routed)
    out = circuity_analyzer.split_geometry_multi(
        LineString([(-79.7, 43.5), (-79.68, 43.5)])
    )
    assert out is routed


def test_split_geometry_multi_falls_back_to_meander_cut(monkeypatch):
    segs = [
        LineString([(-79.7, 43.5), (-79.695, 43.5)]),
        LineString([(-79.695, 43.5), (-79.69, 43.5)]),
    ]
    monkeypatch.setattr(
        "app.circuity_trunk._corridor_splice", lambda g, route_id=None: None
    )
    monkeypatch.setattr("app.circuity_trunk._corridor_segmentation", lambda g: None)
    monkeypatch.setattr("app.circuity_trunk._network_trunk", lambda g: None)
    monkeypatch.setattr(
        "app.circuity_trunk._decompose_segments",
        lambda g, max_branches, validate_start=True: segs,
    )
    out = circuity_analyzer.split_geometry_multi(
        LineString([(-79.7, 43.5), (-79.69, 43.5)])
    )
    assert out == {"trunk": segs[0], "branches": [segs[1]]}


def test_split_geometry_multi_single_segment_returns_none(monkeypatch):
    only = [LineString([(-79.7, 43.5), (-79.69, 43.5)])]
    monkeypatch.setattr(
        "app.circuity_trunk._corridor_splice", lambda g, route_id=None: None
    )
    monkeypatch.setattr("app.circuity_trunk._corridor_segmentation", lambda g: only)
    out = circuity_analyzer.split_geometry_multi(
        LineString([(-79.7, 43.5), (-79.69, 43.5)])
    )
    assert out is None


# ---- proposal pipeline on synthetic geometry ----


def test_slice_linestring_interpolates_window_ends():
    """_slice_linestring cuts a donor between two distances along it, with
    linear interpolation of the exact cut points (not snapped to vertices)."""
    # 4-point straight donor, 1000 m per segment (UTM metres).
    coords = [(500000.0, 4800000.0 + 1000.0 * i) for i in range(4)]
    donor = {
        "coords": coords,
        "cumdist": [0.0, 1000.0, 2000.0, 3000.0],
    }
    out = circuity_analyzer._slice_linestring(donor, 1500.0, 2500.0)
    pts = list(out.coords)
    # First point interpolated halfway between vertices 1 and 2.
    assert pts[0] == pytest.approx((500000.0, 4801500.0))
    assert pts[-1] == pytest.approx((500000.0, 4802500.0))
    # Interior vertices inside the window are kept.
    assert len(pts) == 3


def test_slice_linestring_reversed_window_is_normalized():
    coords = [(500000.0, 4800000.0 + 1000.0 * i) for i in range(4)]
    donor = {"coords": coords, "cumdist": [0.0, 1000.0, 2000.0, 3000.0]}
    a = circuity_analyzer._slice_linestring(donor, 1000.0, 2000.0)
    b = circuity_analyzer._slice_linestring(donor, 2000.0, 1000.0)  # swapped
    assert list(a.coords) == list(b.coords)


def test_slice_linestring_coincident_cuts_yield_degenerate_two_point_line():
    coords = [(500000.0, 4800000.0 + 1000.0 * i) for i in range(4)]
    donor = {"coords": coords, "cumdist": [0.0, 1000.0, 2000.0, 3000.0]}
    out = circuity_analyzer._slice_linestring(donor, 1500.0, 1500.0)
    # Degenerate line keeps two identical points so MIN_BRANCH_KM rejects it.
    assert len(list(out.coords)) == 2
    assert out.coords[0] == out.coords[1]


def _proposal_gdf(monkeypatch, parts):
    """A one-row flagged GeoDataFrame whose split_geometry_multi returns
    ``parts`` — lets propose_split be exercised without any real feed."""
    import geopandas as gpd

    # Geometry in UTM metres near the real network so _split_part_metrics
    # (which reprojects to WGS84) lands on Mississauga.
    x0, y0 = 600_000.0, 4_828_000.0
    geom = LineString([(x0, y0), (x0 + 3000.0, y0)])
    monkeypatch.setattr(
        circuity_analyzer, "split_geometry_multi", lambda g, route_id=None: parts
    )
    return gpd.GeoDataFrame(
        {
            "route_id": ["R1"],
            "route_short_name": ["1"],
            "flagged": [True],
            "geometry": [geom],
        },
        geometry="geometry",
        crs=circuity_analyzer.LOCAL_CRS,
    )


def test_propose_split_meander_labels_fall_back_to_terminals(monkeypatch):
    """A meander split's branch keeps the terminal-aware endpoint labels."""
    x0, y0 = 600_000.0, 4_828_000.0
    trunk = LineString([(x0, y0), (x0 + 2000.0, y0)])
    branch = LineString([(x0 + 2000.0, y0), (x0 + 3000.0, y0)])
    parts = {"trunk": trunk, "branches": [branch]}
    gdf = _proposal_gdf(monkeypatch, parts)
    out = circuity_analyzer.propose_split(gdf, headways={"1": 10.0})
    assert len(out) == 1
    p = out[0]
    assert p["route_short_name"] == "1"
    assert p["trunk_source"] == circuity_analyzer.TRUNK_SOURCE_MEANDER
    assert p["donor_route"] is None
    assert p["splice_junctions"] is None
    assert len(p["branches"]) == 1
    assert p["branches"][0]["headway_min"] == 10.0  # no boarding map → route headway
    assert p["headway_method"] == "route_headway"
    # Geometry exports as rounded WGS84 coords.
    assert len(p["trunk_geometry"]) >= 2
    lat, lon = p["trunk_geometry"][0][1], p["trunk_geometry"][0][0]
    assert 43.0 < lat < 44.0 and -80.0 < lon < -79.0


def test_propose_split_donor_splice_labels_junctions(monkeypatch):
    """A donor splice's branch endpoints become the splice junctions, with
    nearest-stop labels rather than distant-hub labels."""
    x0, y0 = 600_000.0, 4_828_000.0
    trunk = LineString([(x0, y0), (x0 + 2000.0, y0)])
    branch = LineString([(x0 + 2000.0, y0), (x0 + 3000.0, y0)])
    parts = {
        "trunk": trunk,
        "branches": [branch],
        "donor_route": "44",
        "trunk_source": circuity_analyzer.TRUNK_SOURCE_DONOR,
    }
    gdf = _proposal_gdf(monkeypatch, parts)
    out = circuity_analyzer.propose_split(gdf, headways={"1": 10.0})
    p = out[0]
    assert p["donor_route"] == "44"
    assert p["trunk_source"] == circuity_analyzer.TRUNK_SOURCE_DONOR
    assert p["splice_junctions"] is not None
    assert len(p["splice_junctions"]) == 2
    for j in p["splice_junctions"]:
        assert 43.0 < j["lat"] < 44.0 and -80.0 < j["lon"] < -79.0
        assert j["label"]  # nearest stop or hub name, never empty
    # Branch endpoints carry the junction labels.
    assert p["branches"][0]["start_terminal"] == p["splice_junctions"][0]["label"]


def test_propose_split_network_trunk_labels_feeder_ends(monkeypatch):
    """Network-trunk feeders are labeled where they leave/rejoin the trunk."""
    x0, y0 = 600_000.0, 4_828_000.0
    trunk = LineString([(x0, y0), (x0 + 2000.0, y0)])
    branch = LineString([(x0 + 2000.0, y0), (x0 + 3000.0, y0)])
    parts = {
        "trunk": trunk,
        "branches": [branch],
        "trunk_source": circuity_analyzer.TRUNK_SOURCE_NETWORK,
    }
    gdf = _proposal_gdf(monkeypatch, parts)
    out = circuity_analyzer.propose_split(gdf, headways={"1": 10.0})
    p = out[0]
    assert p["trunk_source"] == circuity_analyzer.TRUNK_SOURCE_NETWORK
    assert p["splice_junctions"] is None  # junctions are donor-splice-only
    assert p["branches"][0]["start_terminal"]


def test_propose_split_skips_routes_with_no_split(monkeypatch):
    gdf = _proposal_gdf(monkeypatch, None)
    assert circuity_analyzer.propose_split(gdf) == []


def test_propose_split_unflagged_routes_are_ignored(monkeypatch):
    import geopandas as gpd

    x0, y0 = 600_000.0, 4_828_000.0
    geom = LineString([(x0, y0), (x0 + 3000.0, y0)])
    gdf = gpd.GeoDataFrame(
        {
            "route_id": ["R1"],
            "route_short_name": ["1"],
            "flagged": [False],
            "geometry": [geom],
        },
        geometry="geometry",
        crs=circuity_analyzer.LOCAL_CRS,
    )
    assert circuity_analyzer.propose_split(gdf) == []


def test_piece_headways_without_headway_returns_none_map():
    details = {
        "trunk_geometry": [(1.0, 2.0), (3.0, 4.0)],
        "branches": [],
    }
    method, out = circuity_analyzer._piece_headways(
        "R1", "1", details, route_headway=None, boarding_map=None
    )
    assert method == "route_headway_unavailable"
    assert out == {"Trunk": None}


def test_piece_headways_without_boardings_splits_evenly():
    details = {
        "trunk_geometry": [(1.0, 2.0), (3.0, 4.0)],
        "branches": [{"geometry": [(5.0, 6.0), (7.0, 8.0)]}],
    }
    method, out = circuity_analyzer._piece_headways(
        "R1", "1", details, route_headway=10.0, boarding_map=None
    )
    assert method == "route_headway"
    assert out == {"Trunk": 10.0, "Feeder 0": 10.0}


def test_piece_headways_weighted_allocates_by_stop_proximity(monkeypatch):
    """Boarding weight attaches to the nearest piece: stops near the trunk
    push the trunk's headway down (more service); the bound keeps the trunk
    never worse than today and feeders never more frequent than today."""
    from shapely.geometry import Point

    # Two pieces 2 km apart; all boarding weight sits on the trunk piece.
    details = {
        "trunk_geometry": [(600000.0, 4828000.0), (602000.0, 4828000.0)],
        "branches": [{"geometry": [(604000.0, 4828000.0), (606000.0, 4828000.0)]}],
    }
    stop_ids = ["s1", "s2"]
    lats = np.array([43.5837, 43.5837])
    lons = np.array([-79.7586, -79.7586])
    monkeypatch.setattr(
        circuity_analyzer,
        "_route_stop_ids_points",
        lambda route_id: (stop_ids, lats, lons),
    )
    # Weight attaches by nearest piece distance; both stops map to whichever
    # piece their UTM projection lands nearest. Just assert the invariants:
    # total is split, trunk is capped at base, feeders at least base/2.
    weights = {"1": {"s1": 5.0, "s2": 5.0}}
    method, out = circuity_analyzer._piece_headways(
        "R1", "1", details, route_headway=10.0, boarding_map=weights
    )
    assert method == "ridership_weighted"
    assert out["Trunk"] <= 10.0  # trunk never worse than today
    assert out["Feeder 0"] >= 5.0  # feeders never more frequent than base/2
    assert out["Feeder 0"] <= 20.0  # and never absurdly rare
    assert Point(0, 0)  # shapely import sanity for the geometry math above
