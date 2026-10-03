"""T154: the miss-model switch (window vs july) and the downstream GO check.

* ``app.miss_model`` — the two cost curves and their effective-wait shape.
* ``solve_transfer_sync`` — the july model's floor changes the reported
  effective waits on deep-early misses and is stamped on the result.
* ``app.go_downstream`` — shifted-arrival-to-next-train math, service-valley
  flag, staleness stamping, and the silent no-op contract.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.go_downstream import (
    MIWAY_GO_STATIONS,
    _largest_gap_minutes,
    _next_train,
    _station_for_stop_name,
    check_downstream_connections,
)
from app.miss_model import MISS_MODELS, get_miss_model
from app.solver_core import solve_transfer_sync
from app.transfer_types import TransferConnection, TransferNode


# ---------------------------------------------------------------------------
# miss_model — the two cost curves
# ---------------------------------------------------------------------------


def test_unknown_miss_model_rejected():
    with pytest.raises(ValueError):
        get_miss_model("flat")


def test_miss_models_registry():
    assert MISS_MODELS == ("window", "july")


@pytest.mark.parametrize(
    "name,wait,missed,expected",
    [
        # Kept connections: both models bill the wait itself.
        ("window", 5, False, 5),
        ("july", 5, False, 5),
        # Late miss (wait past T_MAX): window double-counts headway on the
        # long wait; july caps the standing component at one headway total.
        ("window", 14, True, 14 + 15),
        ("july", 14, True, 14 + 15),
        # Deep-early miss (bus left 20 min before the rider arrived): the
        # window model bills NEGATIVE standing time; july floors it at zero.
        ("window", -20, True, -20 + 15),
        ("july", -20, True, 0 + 15),
        # Moderately-early miss (wait still negative): window bills the raw
        # wait; july floors the standing component at zero.
        ("window", -4, True, -4 + 15),
        ("july", -4, True, 0 + 15),
    ],
)
def test_effective_wait_semantics(name, wait, missed, expected):
    mm = get_miss_model(name)
    assert mm.effective_wait(wait, 15, missed) == expected


# ---------------------------------------------------------------------------
# solver integration — the floor changes reported waits and is stamped
# ---------------------------------------------------------------------------


def _node_with_deep_early_miss() -> list[TransferNode]:
    """One connection whose arrival is 20 min AFTER its departure left:
    base = -20. Route 9 departs at 08:00, route 1 arrives at 08:20."""
    node = TransferNode(
        stop_id="deep-stop",
        stop_name="Deep Stop",
        stop_lat=0.0,
        stop_lon=0.0,
        routes=["1", "9"],
    )
    node.connections = [
        TransferConnection(
            node_k="deep-stop",
            route_i="1",
            route_j="9",
            arr_time=500.0,
            dep_time=480.0,
            base=-20.0,
            weight=1.0,
        ),
    ]
    return [node]


def test_window_model_bills_negative_wait_on_deep_early_miss():
    result = solve_transfer_sync(
        _node_with_deep_early_miss(),
        headways={"1": 15.0, "9": 15.0},
        time_limit_seconds=10,
        miss_model_name="window",
    )
    # miss_cost_minutes(15.0 headway) = 15 under both models. The window
    # model makes deep-early waits CHEAP (objective = wait + 15 on the miss
    # branch), so the solver drives route 9 five minutes further early:
    # wait -20 -> -25, eff -25 + 15 = -10 -- and books the change as 5
    # passenger-minutes SAVED. Rewarding a worse miss is precisely the
    # pathology the july model removes.
    assert result.optimized_missed == 1
    assert result.optimized_avg_wait == pytest.approx(-10.0)
    assert result.passenger_minutes_saved == pytest.approx(5.0)


def test_july_model_floors_deep_early_miss_at_zero():
    result = solve_transfer_sync(
        _node_with_deep_early_miss(),
        headways={"1": 15.0, "9": 15.0},
        time_limit_seconds=10,
        miss_model_name="july",
    )
    # The july model never bills negative standing time: the as-scheduled
    # miss costs 0 + 15 = 15 and no shift can beat it, so nothing moves.
    assert result.optimized_missed == 1
    assert result.optimized_avg_wait == pytest.approx(15.0)


def test_miss_model_defaults_to_july_and_is_stamped():
    # Default since 2026-09-19 (docs/runs/t154 receipt): the dashboard and
    # every downstream consumer quote the july basis; window stays available
    # for reproducing historical receipts.
    result = solve_transfer_sync(
        _node_with_deep_early_miss(),
        headways={"1": 15.0, "9": 15.0},
        time_limit_seconds=10,
    )
    assert result.miss_model_name == "july"
    assert result.optimized_avg_wait == pytest.approx(15.0)  # never negative


# ---------------------------------------------------------------------------
# go_downstream — next-train math, valleys, staleness, no-op contract
# ---------------------------------------------------------------------------


def test_next_train_before_first_departure():
    assert _next_train(300.0, [368, 398]) == 68.0


def test_next_train_after_last_departure_is_none():
    assert _next_train(1300.0, [368, 398]) is None


def test_largest_gap_is_interior_only():
    # Departures at 400/420 inside [360, 1320]: the tail past 420 is
    # end-of-service, not a valley — interior gaps only.
    assert _largest_gap_minutes([400, 420], 360, 1320) == 20.0


def test_station_name_mapping_matches_platforms_not_street_stops():
    # The fragments match MiWay's platform-stop naming, not bare street
    # stops that merely mention the station.
    assert _station_for_stop_name("Lisgar GO Station Platform 7") == "Lisgar"
    assert _station_for_stop_name("Cooksville GO Station Platform 4") == "Cooksville"
    assert _station_for_stop_name("Burnhamthorpe Rd At Erindale Go Station") is None
    assert _station_for_stop_name("Winston Churchill Blvd At Tradewind Dr") is None
    assert "Lisgar" in MIWAY_GO_STATIONS


# --- GTFS-shaped fixtures for the stop_times-based check --------------------

LISGAR_DEPARTURES = [368, 398, 413, 428, 443, 458, 473, 488, 503, 518]


def _gtfs_frames(arrivals_at_lisgar):
    """Minimal weekday feed: route 38 arrives at Lisgar's platform, one
    street stop that merely mentions a GO station (must never match), and
    one ordinary stop."""
    stops = pd.DataFrame(
        {
            "stop_id": ["3298", "9999", "1234"],
            "stop_name": [
                "Lisgar GO Station Platform 7",
                "Burnhamthorpe Rd At Erindale Go Station",
                "Ordinary Corner",
            ],
        }
    )
    trips = pd.DataFrame(
        {
            "trip_id": [f"T{i}" for i in range(len(arrivals_at_lisgar) + 1)],
            "route_short_name": ["38"] * len(arrivals_at_lisgar) + ["10"],
        }
    )
    st_rows = [
        {"trip_id": f"T{i}", "stop_id": "3298", "arr_min": float(arr)}
        for i, arr in enumerate(arrivals_at_lisgar)
    ]
    st_rows.append(
        {"trip_id": f"T{len(arrivals_at_lisgar)}", "stop_id": "9999", "arr_min": 480.0}
    )
    return stops, trips, pd.DataFrame(st_rows)


def _reference_doc(departures, valid_through):
    return {
        "feed_version": "test",
        "valid_through": valid_through,
        "stations": {"Lisgar": {"all_departures": departures}},
    }


def test_check_is_silent_without_reference_file(tmp_path):
    stops, trips, stop_times = _gtfs_frames([480.0])
    assert (
        check_downstream_connections(
            trips,
            stop_times,
            stops,
            {},
            360,
            1320,
            reference_path=tmp_path / "missing.json",
        )
        == []
    )


def test_check_measures_shifted_arrivals_against_departures(tmp_path):
    # Scheduled arrivals 06:14 (374), 06:48 (408), 08:45 (525), 09:20 (560).
    stops, trips, stop_times = _gtfs_frames([374.0, 408.0, 525.0, 560.0])
    path = tmp_path / "go.json"
    path.write_text(
        json.dumps(_reference_doc(LISGAR_DEPARTURES, "20991231")), encoding="utf-8"
    )

    # Offsets shift route 38 by +5: arrivals become 379, 413, 530, 565.
    rows = check_downstream_connections(
        trips, stop_times, stops, {"38": 5}, 360, 1320, reference_path=path
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["station"] == "Lisgar"
    assert row["stop_ids"] == ["3298"]
    assert row["service_valley"] is False
    assert row["reference_stale"] is False
    route = row["routes"][0]
    assert route["route"] == "38"
    assert route["arrivals"] == 4
    # Gaps from 379/413/530/565 to the next departure of 368..518:
    # 19, 0, and two past-the-last (no train in service).
    assert route["no_train_in_service"] == 2
    assert route["median_minutes_to_train"] == 9.5  # sorted gaps 0, 19


def test_service_valley_flag_and_staleness_stamp(tmp_path):
    # Real T120 shape: dense AM, then 16:31 (991) — a 473-minute interior gap.
    doc = _reference_doc([*LISGAR_DEPARTURES, 991], "2000-01-01")
    stops, trips, stop_times = _gtfs_frames([374.0, 408.0, 525.0, 560.0])
    path = tmp_path / "go.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    rows = check_downstream_connections(
        trips, stop_times, stops, {}, 360, 1320, reference_path=path
    )
    row = rows[0]
    assert row["service_valley"] is True
    assert row["largest_gap_minutes"] == 473.0  # 518 -> 991, interior
    assert row["reference_stale"] is True
    assert row["reference_valid_through"] == "2000-01-01"


def test_staleness_compare_is_compact_on_both_sides(tmp_path):
    # valid_through in dashed ISO (20260904-equivalent) must still flag as
    # stale against today's compact YYYYMMDD — the dashed-vs-compact bug.
    doc = _reference_doc(LISGAR_DEPARTURES, "2026-09-04")
    stops, trips, stop_times = _gtfs_frames([480.0])
    path = tmp_path / "go.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    rows = check_downstream_connections(
        trips, stop_times, stops, {}, 360, 1320, reference_path=path
    )
    assert rows[0]["reference_stale"] is True  # today (Sept 2026) > 2026-09-04


def test_street_and_ordinary_stops_never_enter_the_check(tmp_path):
    doc = _reference_doc(LISGAR_DEPARTURES, "20991231")
    stops, trips, stop_times = _gtfs_frames([])  # no arrivals at the platform
    path = tmp_path / "go.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    # Only the street/ordinary stops have arrivals; no GO platform match.
    rows = check_downstream_connections(
        trips, stop_times, stops, {}, 360, 1320, reference_path=path
    )
    assert rows == []
