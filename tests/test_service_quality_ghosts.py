"""Tests for the ghost-trip daily aggregation in the service-quality router.

The detector overwrites ``ghost_trips.csv`` every window close with the
current (time-windowed) detector, so the aggregation must NOT label any day a
calendar-vintage "pre-fix". Instead it exposes the real per-day trust signal
(``verifiable_share_pct``) so consumers gate comparability by coverage, and an
uncovered trip is never counted as a ghost.
"""

import pandas as pd
from app.services.ghosts import (
    _SINGLETON_CROWDED_STANDING_PCT,
    _SINGLETON_MISSING_HEADWAY_MIN,
    agg_ghost_blocks as _agg_ghost_blocks,
    agg_ghost_daily as _agg_ghost_daily,
    aggregate_rider_impact as _aggregate_rider_impact,
    annotate_missing_vehicles as _annotate_missing_vehicles,
    standing_share_map as _standing_share_map,
)


def _frame(*rows):
    df = pd.DataFrame(
        list(rows),
        columns=[
            "service_date",
            "route_short_name",
            "scheduled_trips",
            "verifiable_trips",
            "observed_trips",
            "ghost_count",
            "uncovered_trips",
        ],
    )
    for col in df.columns[2:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _row(date, route, sched, ver, obs, ghosts, uncovered):
    return (date, route, sched, ver, obs, ghosts, uncovered)


def test_vintage_uniform_even_for_pre_fix_dates():
    # 08-20 predates the detector fix, 08-28 postdates it. Both land in the
    # same regenerated file, so both must read as "fixed" vintage.
    daily = _agg_ghost_daily(
        _frame(
            _row("20260820", "35", 100, 89, 88, 3, 11),
            _row("20260828", "35", 100, 95, 94, 2, 5),
        )
    )
    by_date = {d["date"]: d for d in daily}
    assert by_date["20260820"]["detector_vintage"] == "fixed"
    assert by_date["20260828"]["detector_vintage"] == "fixed"


def test_verifiable_share_reflects_coverage():
    # Sparse early day: only 30/100 verifiable (heavily uncovered).
    # Well-covered day: 95/100 verifiable.
    daily = _agg_ghost_daily(
        _frame(
            _row("20260818", "35", 100, 30, 28, 3, 70),
            _row("20260828", "35", 100, 95, 94, 2, 5),
        )
    )
    by_date = {d["date"]: d for d in daily}
    sparse = by_date["20260818"]
    assert sparse["verifiable_share_pct"] == 30.0
    assert sparse["uncovered_share_pct"] == 70.0
    covered = by_date["20260828"]
    assert covered["verifiable_share_pct"] == 95.0
    assert covered["uncovered_share_pct"] == 5.0


def test_ghost_rate_and_no_double_count():
    # Rate = ghosts / verifiable; uncovered trips are excluded from the
    # denominator (they're not scorable, so they can't dilute or inflate rate).
    daily = _agg_ghost_daily(_frame(_row("20260828", "35", 100, 95, 94, 2, 5)))
    d = daily[0]
    assert d["ghost_rate_pct"] == round(2 / 95 * 100, 1)
    # Every scheduled trip is verifiable OR uncovered — a partition, so
    # verifiable + uncovered == scheduled and ghosts can't exceed verifiable.
    assert d["verifiable"] + d["uncovered"] == d["scheduled"]
    assert d["ghosts"] <= d["verifiable"]


def _ghost_df(*rows):
    df = pd.DataFrame(
        list(rows),
        columns=["service_date", "route_short_name", "ghosts"],
    )
    return df


def test_blocks_group_multi_trips_into_one_vehicle():
    # Ten trips all from block 2877008 (the 08-22 Route 22 pattern) should
    # collapse into a single missing-vehicle record, not ten ghosts.
    rows = []
    for i, t in enumerate(
        ("11:02", "12:07", "13:19", "15:02", "16:31", "17:18", "18:03")
    ):
        rows.append(("20260822", "22", f"3031471{i}@{t}"))
    rows.append(("20260822", "22", "30314749@11:53"))
    df = _ghost_df(*rows)
    blocks = _agg_ghost_blocks(
        df,
        {
            "30314710": "2877008",
            "30314711": "2877008",
            "30314712": "2877008",
            "30314713": "2877008",
            "30314714": "2877008",
            "30314715": "2877008",
            "30314716": "2877008",
            "30314749": "2877008",
        },
    )
    assert len(blocks) == 1
    b = blocks[0]
    assert b["block"] == "2877008"
    assert b["route_short_name"] == "22"
    assert b["n_ghosts"] == 8
    assert b["likely_missing_vehicle"] is True
    assert b["span_from_min"] == 11 * 60 + 2
    assert b["span_to_min"] == 18 * 60 + 3


def test_blocks_flag_boundary_at_min_ghosts():
    # A single isolated ghost is noise -> omitted. Two+ trips group; the
    # likely-missing-vehicle flag only flips at _MISSING_VEHICLE_MIN_GHOSTS.
    df = _ghost_df(
        ("20260822", "1", "30317000@10:10"),  # singleton on its own block
        ("20260828", "42", "30318000@09:00;30318001@09:30"),  # two, one block
    )
    trip_blocks = {"30317000": "2876000", "30318000": "2877001", "30318001": "2877001"}
    blocks = _agg_ghost_blocks(df, trip_blocks)
    by_block = {b["block"]: b for b in blocks}
    # singleton block omitted entirely
    assert "2876000" not in by_block
    # two ghosts on one block surfaces but is not flagged a missing vehicle
    b = by_block["2877001"]
    assert b["n_ghosts"] == 2
    assert b["likely_missing_vehicle"] is False


def test_annotate_missing_vehicles_counts_whole_buses_per_day():
    daily = _agg_ghost_daily(
        _frame(
            _row("20260822", "22", 100, 95, 75, 20, 0),
            _row("20260828", "35", 100, 98, 97, 1, 0),
        )
    )
    blocks = [
        {
            "date": "20260822",
            "block": "2877008",
            "n_ghosts": 20,
            "likely_missing_vehicle": True,
        },
        {
            "date": "20260822",
            "block": "2876660",
            "n_ghosts": 5,
            "likely_missing_vehicle": True,
        },
        {
            "date": "20260822",
            "block": "2876749",
            "n_ghosts": 2,
            "likely_missing_vehicle": False,
        },
    ]
    out = _annotate_missing_vehicles(daily, blocks)
    by_date = {d["date"]: d for d in out}
    # Two whole buses absent on 08-22 (20-trip + 5-trip blocks); the 2-trip
    # block isn't big enough to count as a missing vehicle.
    assert by_date["20260822"]["missing_vehicles"] == 2
    assert by_date["20260828"]["missing_vehicles"] == 0


def test_sums_across_routes_per_day():
    daily = _agg_ghost_daily(
        _frame(
            _row("20260828", "35", 60, 58, 57, 1, 2),
            _row("20260828", "42", 40, 37, 37, 1, 3),
        )
    )
    assert len(daily) == 1
    d = daily[0]
    assert d["scheduled"] == 100
    assert d["verifiable"] == 95
    assert d["ghosts"] == 2
    assert d["ghost_rate_pct"] == round(2 / 95 * 100, 1)


# ---- low-frequency singleton rule ----------------------------------------------


def test_singleton_on_low_frequency_route_surfaces():
    # One ghost on a 60-min-headway route: the next bus is an hour away, so a
    # rider at that stop is stranded — surface it as a likely absent vehicle.
    df = _ghost_df(("20260901", "51", "30319001@14:05"))
    blocks = _agg_ghost_blocks(
        df,
        {"30319001": "2878001"},
        route_headways={"51": 60.0},
    )
    assert len(blocks) == 1
    b = blocks[0]
    assert b["n_ghosts"] == 1
    assert b["likely_missing_vehicle"] is True
    assert b["route_short_name"] == "51"


def test_singleton_on_frequent_route_still_omitted():
    # One ghost on a 10-min-headway route: the next bus arrives in minutes.
    # Without headways (legacy call shape) the outcome must be the same.
    df = _ghost_df(("20260901", "19", "30319002@08:15"))
    for headways in ({"19": 10.0}, None):
        blocks = _agg_ghost_blocks(
            df,
            {"30319002": "2878002"},
            route_headways=headways,
        )
        assert blocks == [], "frequent-route singleton is noise"


def test_singleton_unknown_route_defaults_to_noise():
    # A route with no headway entry (or a multi-route bucket) must not be
    # flagged — the rule only fires on a known low-frequency route.
    df = _ghost_df(("20260901", "99", "30319003@21:40"))
    blocks = _agg_ghost_blocks(
        df,
        {"30319003": "2878003"},
        route_headways={"19": 10.0},  # some other route
    )
    assert blocks == []


def test_singleton_boundary_at_threshold():
    # Exactly at _SINGLETON_MISSING_HEADWAY_MIN counts as low-frequency
    # (>= boundary flags); just below does not.
    df_low = _ghost_df(("20260901", "35", "30319004@12:00"))
    df_fast = _ghost_df(("20260901", "35", "30319005@12:00"))
    at = _agg_ghost_blocks(
        df_low,
        {"30319004": "2878004"},
        route_headways={"35": _SINGLETON_MISSING_HEADWAY_MIN},
    )
    under = _agg_ghost_blocks(
        df_fast,
        {"30319005": "2878005"},
        route_headways={"35": _SINGLETON_MISSING_HEADWAY_MIN - 0.5},
    )
    assert len(at) == 1 and at[0]["likely_missing_vehicle"] is True
    assert under == []


def test_singleton_counts_toward_missing_vehicles():
    daily = _agg_ghost_daily(_frame(_row("20260901", "51", 40, 38, 37, 1, 0)))
    blocks = [
        {
            "date": "20260901",
            "block": "2878001",
            "n_ghosts": 1,
            "likely_missing_vehicle": True,
        }
    ]
    out = _annotate_missing_vehicles(daily, blocks)
    assert out[0]["missing_vehicles"] == 1


# ---- crush-prone route rule ----------------------------------------------------


def test_singleton_on_crowded_frequent_route_surfaces():
    # Route 61 pattern: frequent (14 min headway) but the system's most
    # crowded — a vanished bus dumps its load onto the next one. Must
    # surface even though the headway gate alone would drop it.
    df = _ghost_df(("20260901", "61", "30319006@07:42"))
    blocks = _agg_ghost_blocks(
        df,
        {"30319006": "2878006"},
        route_headways={"61": 13.9},
        route_crowding={"61": 26.4},
    )
    assert len(blocks) == 1
    b = blocks[0]
    assert b["likely_missing_vehicle"] is True
    assert b["singleton_rule"] == "crowded_route"


def test_crowding_rule_reports_low_frequency_when_both_fire():
    # A route that is both slow and crowded: the rule label prefers the
    # frequency reason (it explains the long wait) but either way the
    # singleton surfaces.
    df = _ghost_df(("20260901", "74", "30319007@06:10"))
    blocks = _agg_ghost_blocks(
        df,
        {"30319007": "2878007"},
        route_headways={"74": 44.9},
        route_crowding={"74": 12.0},
    )
    assert len(blocks) == 1
    assert blocks[0]["singleton_rule"] == "low_frequency"


def test_crowding_gate_boundary():
    # Standing share exactly at the threshold flags; just under does not.
    df_at = _ghost_df(("20260901", "70", "30319008@08:00"))
    df_under = _ghost_df(("20260901", "70", "30319009@08:00"))
    at = _agg_ghost_blocks(
        df_at,
        {"30319008": "2878008"},
        route_headways={"70": 15.9},
        route_crowding={"70": _SINGLETON_CROWDED_STANDING_PCT},
    )
    under = _agg_ghost_blocks(
        df_under,
        {"30319009": "2878009"},
        route_headways={"70": 15.9},
        route_crowding={"70": _SINGLETON_CROWDED_STANDING_PCT - 0.5},
    )
    assert len(at) == 1
    assert under == []


def test_no_crowding_data_defaults_to_headway_only():
    # route_crowding=None (occupancy CSV missing) must restore the previous
    # headway-only behavior, not flag everything.
    df = _ghost_df(("20260901", "61", "30319010@07:42"))
    blocks = _agg_ghost_blocks(
        df,
        {"30319010": "2878010"},
        route_headways={"61": 13.9},
        route_crowding=None,
    )
    assert blocks == []


def test_standing_share_map_ignores_thin_samples():
    # A 3-poll route-period reporting 3 standings would read 100% — must be
    # excluded by the min-observations floor, not sampled into the max.
    occ = pd.DataFrame(
        {
            "route_short_name": ["61", "61", "46"],
            "n_observations": [5000, 150, 3000],
            "n_standing": [1300, 150, 0],
            "n_crushed": [50, 0, 300],
            "n_full": [0, 0, 0],
        }
    )
    shares = _standing_share_map(occ)
    # route 61: only the 5000-obs period counts -> (1300+50)/5000 = 27%
    assert shares["61"] == round(1350 / 5000 * 100, 6)
    # route 46: 300/3000 = 10%
    assert shares["46"] == round(300 / 3000 * 100, 6)


def test_multi_route_bucket_never_flagged_even_if_crowded():
    df = _ghost_df(("20260901", "61", "30319011@07:42"))
    blocks = _agg_ghost_blocks(
        df,
        {"30319011": ""},  # no block mapping -> bucket never forms
        route_headways={"61": 13.9},
        route_crowding={"61": 26.4},
    )
    assert blocks == []


# ---- crush-weighted rider impact ------------------------------------------------


def _gap(route, date, minutes):
    return {
        "route": route,
        "date": date,
        "gap_minutes": minutes,
        "trip_id": "x",
        "dep_min": 0,
    }


def test_weighted_impact_scales_by_standing_share():
    # 60 min on a 26%-standing route weights to 75.6; 60 min on a 0% route
    # stays 60. Raw totals are identical for both.
    out = _aggregate_rider_impact(
        [_gap("61", "20260901", 60.0), _gap("74", "20260901", 60.0)],
        skipped_phantoms=0,
        route_crowding={"61": 26.0},
    )
    assert out["total_extra_wait_minutes"] == 120.0
    assert out["weighted_extra_wait_minutes"] == round(60 * 1.26 + 60, 1)
    by_route = {r["route_short_name"]: r for r in out["by_route"]}
    assert by_route["74"]["weighted_extra_wait_minutes"] == 60.0
    assert by_route["74"]["standing_share_pct"] == 0.0
    assert by_route["61"]["standing_share_pct"] == 26.0


def test_by_route_ranked_by_weighted_not_raw():
    # Route A has more raw wait but no crowding; route B slightly less raw
    # wait but crowded — B must rank first.
    impacts = [_gap("A", "20260901", 100.0), _gap("B", "20260901", 90.0)]
    out = _aggregate_rider_impact(
        impacts, skipped_phantoms=0, route_crowding={"B": 20.0}
    )
    routes = [r["route_short_name"] for r in out["by_route"]]
    assert routes[0] == "B", "crowded route outranks raw-gap leader"


def test_no_crowding_keeps_weights_neutral():
    out = _aggregate_rider_impact(
        [_gap("9", "20260901", 45.0)], skipped_phantoms=0, route_crowding=None
    )
    assert out["total_extra_wait_minutes"] == 45.0
    assert out["weighted_extra_wait_minutes"] == 45.0


def test_null_gaps_excluded_from_both_totals():
    out = _aggregate_rider_impact(
        [_gap("9", "20260901", None), _gap("9", "20260901", 30.0)],
        skipped_phantoms=0,
        route_crowding={"9": 50.0},
    )
    assert out["total_ghosts_with_gap"] == 1
    assert out["total_extra_wait_minutes"] == 30.0
    assert out["weighted_extra_wait_minutes"] == 45.0


# ---- _agg_ghost_blocks / _detect_phantoms edge cases (merged from the former
# test_service_quality_coverage.py) -------------------------------------------


from app.services.ghosts import detect_phantoms as _detect_phantoms  # noqa: E402


def _entries_frame(rows):
    return pd.DataFrame(rows)


def test_agg_ghost_blocks_parses_entries_and_flags_missing_vehicle():
    df = _entries_frame(
        [
            {
                "service_date": "20260901",
                "route_short_name": "35",
                "ghosts": "T1@07:10;T2@08:30;T3@09:05;T4@10:00",
                "verifiable_trips": 90,
                "observed_trips": 86,
                "ghost_count": 4,
                "scheduled_trips": 100,
                "uncovered_trips": 5,
            },
            {
                "service_date": "20260901",
                "route_short_name": "10",
                "ghosts": "T9@07:15",  # lone ghost → noise, dropped
                "verifiable_trips": 50,
                "observed_trips": 49,
                "ghost_count": 1,
                "scheduled_trips": 60,
                "uncovered_trips": 5,
            },
        ]
    )
    blocks = _agg_ghost_blocks(df, {"T1": "B1", "T2": "B1", "T3": "B1", "T4": "B1"})
    assert len(blocks) == 1
    b = blocks[0]
    assert b["block"] == "B1"
    assert b["n_ghosts"] == 4
    assert b["likely_missing_vehicle"] is True
    assert b["span_from_min"] == 7 * 60 + 10
    assert b["span_to_min"] == 10 * 60


def test_agg_ghost_blocks_skips_malformed_entries_and_unknown_blocks():
    df = _entries_frame(
        [
            {
                "service_date": "20260901",
                "route_short_name": "35",
                # T9 unmapped, "junk" has no @, T7 bad time, T8/T6 valid pair
                "ghosts": "T9@07:00;junk;T7@xx:00;T8@21:30;T6@22:05",
                "verifiable_trips": 40,
                "ghost_count": 2,
            }
        ]
    )
    blocks = _agg_ghost_blocks(df, {"T8": "B2", "T6": "B2"})
    assert len(blocks) == 1
    assert blocks[0]["n_ghosts"] == 2
    assert blocks[0]["likely_missing_vehicle"] is False


def test_agg_ghost_blocks_empty_and_nan_details():
    df = _entries_frame(
        [
            {"service_date": "d", "route_short_name": "35", "ghosts": ""},
            {"service_date": "d", "route_short_name": "10", "ghosts": float("nan")},
        ]
    )
    assert _agg_ghost_blocks(df, {"T1": "B1"}) == []


def test_detect_phantoms_threshold_and_insufficient_days():
    rows = []
    # T-PHANTOM ghosts 3 of 4 days on route 35 (rate 0.75 > 0.6)
    for i, date in enumerate(("20260901", "20260902", "20260903", "20260904")):
        ghosts = "T-PHANTOM@07:00" if i < 3 else ""
        rows.append(
            {
                "service_date": date,
                "route_short_name": "35",
                "verifiable_trips": 40,
                "ghosts": ghosts,
            }
        )
    # T-RARE ghosts 1 of 1 verifiable day → total_days < 2 → not phantom
    rows.append(
        {
            "service_date": "20260901",
            "route_short_name": "10",
            "verifiable_trips": 30,
            "ghosts": "T-RARE@08:00",
        }
    )
    out = _detect_phantoms(_entries_frame(rows))
    assert out["phantom_count"] == 1
    assert out["phantom_trip_ids"] == {"T-PHANTOM"}
    detail = out["phantom_details"][0]
    assert detail["ghost_days"] == 3
    assert detail["total_days"] == 4
    assert detail["ghost_rate"] == 0.75


def test_detect_phantoms_unverifiable_days_dont_count():
    rows = [
        # route 35 verifiable only on 2 days; T-X ghosts on both → rate 1.0
        {
            "service_date": "20260901",
            "route_short_name": "35",
            "verifiable_trips": 10,
            "ghosts": "T-X@06:00",
        },
        {
            "service_date": "20260902",
            "route_short_name": "35",
            "verifiable_trips": 10,
            "ghosts": "T-X@06:15",
        },
        {
            "service_date": "20260903",
            "route_short_name": "35",
            "verifiable_trips": 0,  # not a verifiable day
            "ghosts": "T-X@06:30",
        },
    ]
    out = _detect_phantoms(_entries_frame(rows))
    assert out["phantom_details"][0]["total_days"] == 2
