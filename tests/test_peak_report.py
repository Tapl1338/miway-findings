"""Smoke tests for the councillor-readable peak report generator."""

import csv
from pathlib import Path

from scripts.peak_report import build_report

_OCC_HEADER = [
    "route_short_name",
    "period",
    "n_observations",
    "n_with_status",
    "n_with_percentage",
    "mean_percentage",
    "p90_percentage",
    "n_crowded",
    "crowded_share_pct",
    "n_empty",
    "n_many_seats",
    "n_few_seats",
    "n_standing",
    "n_crushed",
    "n_full",
    "n_no_data",
]
_BOARD_HEADER = [
    "route_short_name",
    "period",
    "n_trips",
    "n_observations",
    "n_stops_observed",
    "n_bus_obs",
    "n_bus_obs_with_pct",
    "coverage_pct",
    "peak_load_pct",
    "boardings_lower_pct",
    "boardings_lower_pax",
]
_LAT_HEADER = [
    "route_short_name",
    "stop_id",
    "dep_time_min",
    "lateness_minutes",
    "horizon_minutes",
    "date",
]


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_build_report_covers_all_sections(tmp_path):
    occ = tmp_path / "occupancy_stats.csv"
    board = tmp_path / "boardings_routes.csv"
    lat = tmp_path / "obs_lateness.csv"
    _write(
        occ,
        _OCC_HEADER,
        [["2", "pm_rush", 100, 100, 80, 35.0, 60.0, 20, 20.0, 0, 80, 20, 0, 0, 0, 0]],
    )
    _write(
        board,
        _BOARD_HEADER,
        [["2", "pm_rush", 5, 80, 30, 120, 80, 66.7, 100.0, 40.0, 26.0]],
    )
    _write(
        lat,
        _LAT_HEADER,
        [
            ["2", "a", 400.0, -1.5, -2.0, "2026-09-10"],
            ["2", "b", 410.0, 0.5, -3.0, "2026-09-10"],
            ["2", "c", 420.0, 4.0, 5.0, "2026-09-10"],  # future forecast -> excluded
            ["1", "d", 300.0, -2.0, -4.0, "2026-09-10"],
        ],
    )
    report = build_report(occ, board, lat)
    assert "MiWay Peak Collection Report" in report
    assert "measured polls, FQ-10 basis" in report  # canonical-basis label
    assert "PM peak (15-19)" in report
    # horizon 5.0 row excluded: exactly 3 measured polls remain.
    assert "3 measured polls" in report
    assert "lower-bound boardings" in report
    assert "Capacity" in report
    assert "equipped-fleet coverage" in report.lower() or "coverage" in report


def test_build_report_handles_missing_files(tmp_path):
    report = build_report(
        tmp_path / "none1.csv", tmp_path / "none2.csv", tmp_path / "none3.csv"
    )
    low = report.lower()
    assert "no recorded departures yet" in low
    assert "no occupancy snapshots collected yet" in low
    assert "no usable load profiles yet" in low
