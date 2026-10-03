"""Unit tests for ``scripts/reconstruct_boardings.py`` (boardings-from-load).

Covers the coverage accounting (per route/period/date) and the cross-day gap
fill that repairs route-period-days whose buses carried no occupancy
percentage (the broken-APC case). Pure helpers only; no network, no feed.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from scripts.reconstruct_boardings import (
    _drop_carryover_first,
    _fill_daily_gaps,
    _materialize_capacity_pax,
    _never_reporting_vehicles,
    _route_coverage,
)

# Epochs landing in the Toronto-local AM/PM windows (period_for_epoch buckets
# observations by America/Toronto time, not the machine's clock).
_TS_AM = datetime(2026, 8, 18, 7, 0, tzinfo=ZoneInfo("America/Toronto")).timestamp()
_TS_PM = datetime(2026, 8, 18, 16, 0, tzinfo=ZoneInfo("America/Toronto")).timestamp()


def _daily(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "route_short_name",
            "period",
            "service_date",
            "n_trips",
            "n_observations",
            "n_stops_observed",
            "peak_load_pct",
            "boardings_lower_pct",
            "boardings_lower_pax",
        ],
    )


def test_materialize_capacity_pax_reads_each_trip_own_capacity():
    """Canonical boardings_lower_pax (plus lo/hi) must come from each trip's
    own capacity column. A standard trip (cap65) and an articulated trip
    (cap110) carry the same figure under different-suffixed columns; the helper
    must put each under the plain column so summaries sum the right amount
    (this is the regression that zeroed articulated routes 42/109)."""
    trips = pd.DataFrame(
        [
            {
                "route_short_name": "10",
                "capacity_used": 65.0,
                "boardings_lower_pax_cap65": 40.0,
                "boardings_lower_pax_lo_cap65": 27.0,
                "boardings_lower_pax_hi_cap65": 53.0,
                "boardings_lower_pax_cap110": float("nan"),
                "boardings_lower_pax_lo_cap110": float("nan"),
                "boardings_lower_pax_hi_cap110": float("nan"),
            },
            {
                "route_short_name": "42",
                "capacity_used": 110.0,
                "boardings_lower_pax_cap65": float("nan"),
                "boardings_lower_pax_lo_cap65": float("nan"),
                "boardings_lower_pax_hi_cap65": float("nan"),
                "boardings_lower_pax_cap110": 120.0,
                "boardings_lower_pax_lo_cap110": 78.0,
                "boardings_lower_pax_hi_cap110": 162.0,
            },
        ]
    )
    out = _materialize_capacity_pax(trips.copy())
    assert out.loc[0, "boardings_lower_pax"] == 40.0
    assert out.loc[0, "boardings_lower_pax_lo"] == 27.0
    assert out.loc[1, "boardings_lower_pax"] == 120.0
    assert out.loc[1, "boardings_lower_pax_hi"] == 162.0
    # Route 42's cap65 columns stay NaN -> a bad global-cap sum would be 0.
    assert pd.isna(out.loc[1, "boardings_lower_pax_cap65"])


def test_materialize_capacity_pax_does_not_clobber_existing():
    trips = pd.DataFrame(
        [
            {
                "route_short_name": "1",
                "capacity_used": 65.0,
                "boardings_lower_pax_cap65": 9.5,
                "boardings_lower_pax_lo_cap65": 5.0,
                "boardings_lower_pax_hi_cap65": 14.0,
                "boardings_lower_pax_cap110": float("nan"),
                "boardings_lower_pax_lo_cap110": float("nan"),
                "boardings_lower_pax_hi_cap110": float("nan"),
            }
        ]
    )
    out = _materialize_capacity_pax(trips)
    assert out.loc[0, "boardings_lower_pax"] == 9.5
    assert out.loc[0, "boardings_lower_pax_hi"] == 14.0


def test_drop_carryover_first_removes_terminal_holdover():
    # Route 22 ground truth: sensor read 40% at the terminal (previous trip's
    # load), corrected to 20% once rolling. A first stop a full bucket above
    # the next is that signature -> drop it.
    medians, dropped = _drop_carryover_first([(1, 40.0), (2, 20.0), (3, 20.0)])
    assert dropped is True
    assert medians == [(2, 20.0), (3, 20.0)]


def test_drop_carryover_first_keeps_normal_profiles():
    # Normal rising profile: first stop is NOT above the next -> keep.
    medians, dropped = _drop_carryover_first([(1, 20.0), (2, 40.0), (3, 40.0)])
    assert dropped is False
    assert medians == [(1, 20.0), (2, 40.0), (3, 40.0)]
    # A partial drop (less than a full 20-point bucket) is not the carryover
    # signature either -- keep it.
    medians, dropped = _drop_carryover_first([(1, 40.0), (2, 30.0)])
    assert dropped is False
    assert medians == [(1, 40.0), (2, 30.0)]


def test_drop_carryover_first_single_stop_untouched():
    medians, dropped = _drop_carryover_first([(1, 40.0)])
    assert dropped is False
    assert medians == [(1, 40.0)]


def test_never_reporting_vehicles_requires_sample_size():
    # Vehicle 2: 40 observations, status only -> status-estimated, NOT broken.
    buses = [
        {"vehicle_id": "1", "trip_id": f"a{i}", "occupancy_percentage": 20}
        for i in range(40)
    ]
    buses += [
        {"vehicle_id": "2", "trip_id": f"c{i}", "occupancy_status": 1}
        for i in range(40)
    ]
    # Vehicle 3: observed 5 times (below the floor), status only: NOT
    # flagged -- a working bus caught briefly while empty looks identical.
    buses += [
        {"vehicle_id": "3", "trip_id": f"d{i}", "occupancy_status": 1} for i in range(5)
    ]
    # Vehicle 4: 40 observations, NO fields at all -> genuinely broken APC.
    buses += [{"vehicle_id": "4", "trip_id": f"e{i}"} for i in range(40)]
    assert _never_reporting_vehicles(buses) == ["4"]


def test_never_reporting_vehicles_skips_pre_apc_rows():
    # Pre-APC captures with neither status nor percentage: they ARE genuinely
    # broken-APC (no data at all), so they are flagged. A pre-APC capture
    # that carries occupancy_status is a valid status-estimated source and is
    # NOT flagged.
    buses = [
        {"vehicle_id": "9", "trip_id": "x", "lat": 1.0, "lon": 1.0} for _ in range(40)
    ]
    assert _never_reporting_vehicles(buses) == ["9"]
    # With occupancy_status present, the vehicle has estimated data -> not broken.
    buses_with_status = [
        {
            "vehicle_id": "9",
            "trip_id": "x",
            "lat": 1.0,
            "lon": 1.0,
            "occupancy_status": 1,
        }
        for _ in range(40)
    ]
    assert _never_reporting_vehicles(buses_with_status) == []


def test_route_coverage_keys_by_route_period_date():
    trip_route = {"a": "1", "b": "1", "c": "2"}
    buses = [
        {
            "trip_id": "a",
            "service_date": "2026-08-17",
            "timestamp": _TS_PM,  # -> pm_rush
            "occupancy_status": 2,
            "occupancy_percentage": 20,
        },
        {
            "trip_id": "b",
            "service_date": "2026-08-17",
            "timestamp": _TS_PM + 1,  # pm, empty bus: no percentage
            "occupancy_status": 1,
        },
        {
            "trip_id": "c",
            "service_date": "2026-08-18",
            "timestamp": _TS_AM,  # -> am_rush
            "occupancy_status": 2,
            "occupancy_percentage": 40,
        },
    ]
    cov = _route_coverage(buses, trip_route)
    assert cov[("1", "pm_rush", "2026-08-17")] == (2, 2)  # bus b has status fallback
    assert cov[("2", "am_rush", "2026-08-18")] == (1, 1)
    assert len(cov) == 2


def test_fill_daily_gaps_uses_route_median():
    daily = _daily(
        [
            ["1", "pm_rush", "2026-08-17", 3, 60, 30, 80.0, 40.0, 100.0],
            ["1", "pm_rush", "2026-08-18", 4, 80, 40, 100.0, 56.0, 140.0],
            ["2", "pm_rush", "2026-08-17", 2, 40, 20, 60.0, 20.0, 50.0],
            ["4", "pm_rush", "2026-08-17", 1, 20, 10, 40.0, 12.0, 30.0],
        ]
    )
    cov = {
        ("1", "pm_rush", "2026-08-17"): (10, 12),
        ("1", "pm_rush", "2026-08-18"): (8, 10),
        ("1", "pm_rush", "2026-08-19"): (0, 40),  # broken-APC day -> filled
        ("2", "pm_rush", "2026-08-17"): (4, 5),
        ("2", "pm_rush", "2026-08-18"): (0, 35),  # gap, other day exists -> filled
        ("3", "pm_rush", "2026-08-17"): (0, 50),  # ONLY gap days -> no_data
        ("3", "pm_rush", "2026-08-18"): (0, 45),
        ("4", "pm_rush", "2026-08-17"): (10, 12),
        ("4", "pm_rush", "2026-08-18"): (0, 5),  # under-sampled -> insufficient
    }
    out = (
        _fill_daily_gaps(daily, cov)
        .sort_values(["route_short_name", "service_date"])
        .reset_index(drop=True)
    )

    assert list(out["service_date"]) == [
        "2026-08-17",
        "2026-08-18",
        "2026-08-19",
        "2026-08-17",
        "2026-08-18",
        "2026-08-17",
        "2026-08-18",
        "2026-08-17",
        "2026-08-18",
    ]
    assert list(out["data_status"]) == [
        "observed",
        "observed",
        "filled",
        "observed",
        "filled",
        "no_data",
        "no_data",
        "observed",
        "insufficient",
    ]

    filled = out[out["data_status"] == "filled"]
    assert list(filled["boardings_lower_pax"]) == [120.0, 50.0]
    assert list(filled["n_bus_obs"]) == [40, 35]
    assert list(filled["n_bus_obs_with_pct"]) == [0, 0]
    assert list(filled["coverage_pct"]) == [0.0, 0.0]
    assert list(filled["n_trips"]) == [0, 0]
    # Route 3 (only gap days) and route 4's tiny sample are listed but never
    # filled: their boardings stay None.
    flagged = out[out["data_status"].isin(["no_data", "insufficient"])]
    assert set(flagged["route_short_name"]) == {"3", "4"}
    assert flagged["boardings_lower_pax"].isna().all()
    assert set(flagged["data_status"]) == {"no_data", "insufficient"}

    # Observed cells carry coverage from the bus-level counts, not the trips.
    first = out.iloc[0]
    assert first["n_bus_obs"] == 12
    assert first["coverage_pct"] == round(100.0 * 10 / 12, 1)


def test_fill_daily_gaps_noop_without_gaps():
    daily = _daily(
        [
            ["1", "pm_rush", "2026-08-17", 3, 60, 30, 80.0, 40.0, 100.0],
            ["1", "pm_rush", "2026-08-18", 4, 80, 40, 100.0, 56.0, 140.0],
        ]
    )
    cov = {
        ("1", "pm_rush", "2026-08-17"): (10, 12),
        ("1", "pm_rush", "2026-08-18"): (8, 10),
    }
    out = _fill_daily_gaps(daily, cov)
    assert len(out) == 2
    assert list(out["data_status"]) == ["observed", "observed"]


def test_fill_daily_gaps_single_day_stays_observed():
    """With only one day of data there is nothing to borrow: no fills."""
    daily = _daily([["1", "pm_rush", "2026-08-17", 3, 60, 30, 80.0, 40.0, 100.0]])
    cov = {("1", "pm_rush", "2026-08-17"): (10, 12)}
    out = _fill_daily_gaps(daily, cov)
    assert len(out) == 1
    assert out.iloc[0]["data_status"] == "observed"
