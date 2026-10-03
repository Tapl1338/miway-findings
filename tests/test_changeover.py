"""Tests for the Changeover Impact endpoint (Slice 1).

The endpoint's intellectual content is the pairing rule (same weekday,
holiday-clean, block-clean) and its honesty rules (never render a verdict
without 3 comparable day-pairs, never a sum where a per-day mean belongs).
These tests pin both against tmp-dir CSVs, with the feed-derived block and
holiday functions patched so no real feed is needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routers import changeover


_LAT_HEADER = (
    "route_short_name,stop_id,dep_time_min,lateness_minutes,horizon_minutes,date\n"
)


def _lat_row(
    route: str, date: str, lateness: float, horizon: float = -1.0, dep: int = 480
) -> str:
    return f"{route},S1,{dep},{lateness},{horizon},{date}\n"


@pytest.fixture()
def patched(monkeypatch, tmp_path):
    """Patch the CSV paths and the feed-derived date classifiers."""
    lat = tmp_path / "obs_lateness.csv"
    roll = tmp_path / "weekly_rollup.csv"
    monkeypatch.setattr(changeover, "_LATENESS_CSV", lat, raising=False)
    monkeypatch.setattr(changeover, "_ROLLUP_CSV", roll, raising=False)
    # cutoff 20260907: dates <= it are 'pre', after are 'post'.
    monkeypatch.setattr(changeover.md, "block_cutoff", lambda: "20260907")
    monkeypatch.setattr(
        changeover.md, "schedule_block", lambda s: "pre" if s <= "20260907" else "post"
    )
    monkeypatch.setattr(changeover.md, "is_holiday_date", lambda s: s == "20260907")
    return lat, roll


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_available_false_when_no_cutoff(patched, monkeypatch):
    lat, _ = patched
    _write(lat, _LAT_HEADER + _lat_row("10", "20260902", 1.0))
    monkeypatch.setattr(changeover.md, "block_cutoff", lambda: "")
    got = changeover.changeover()
    assert got["available"] is False
    assert "not derivable" in got["reason"]


def test_pre_side_aggregates_and_weekend_exclusion(patched):
    lat, _ = patched
    body = (
        # Two pre-block weekdays + a Saturday that must never compare.
        # Distinct dep_time = distinct departures (same identity would dedup).
        _lat_row("10", "20260902", 1.0, dep=480)
        + _lat_row("10", "20260902", 1.0, dep=540)
        + _lat_row("10", "20260903", 3.0)
        + _lat_row("10", "20260905", 0.0)  # Saturday
    )
    _write(lat, _LAT_HEADER + body)
    got = changeover.changeover()
    assert got["available"] is True
    assert got["pre"]["days"] == 2
    assert got["pre"]["n_departures"] == 3
    # On-time = |lat| <= 2 → 2 of 3.
    assert got["pre"]["pct_on_time"] == 66.7
    # Mean of daily means: (1.0 + 3.0) / 2 — the Saturday row is excluded.
    assert got["pre"]["mean_lateness_min"] == 2.0


def test_holiday_excluded_from_pre_baseline(patched):
    lat, _ = patched
    body = (
        _lat_row("10", "20260904", 1.0)
        # Labour Day: a Monday, holiday-flagged — must not enter 'pre'.
        + _lat_row("10", "20260907", 99.0)
    )
    _write(lat, _LAT_HEADER + body)
    got = changeover.changeover()
    assert got["pre"]["days"] == 1
    assert got["pre"]["mean_lateness_min"] == 1.0
    assert got["n_observations_excluded"] == 1


def test_not_yet_a_verdict_under_three_pairs(patched):
    lat, _ = patched
    body = (
        _lat_row("10", "20260902", 1.0)
        + _lat_row("10", "20260903", 1.0)
        + _lat_row("10", "20260909", 2.0)
        + _lat_row("10", "20260910", 2.0)
    )
    _write(lat, _LAT_HEADER + body)
    got = changeover.changeover()
    assert got["verdict_ready"] is False
    assert "Not yet a verdict" in got["reason"]
    # But the measured numbers still render.
    assert got["post"]["days"] == 2


def test_verdict_and_route_table_when_ready(patched, monkeypatch):
    lat, roll = patched
    # Fixture routes carry 3 obs/side; relax the floor so the table renders
    # (test_small_routes_omitted pins the default floor separately).
    monkeypatch.setattr(changeover, "_ROUTE_MIN_OBS", 2)
    body = "".join(
        _lat_row("10", d, 1.0) for d in ("20260902", "20260903", "20260904")
    ) + "".join(_lat_row("10", d, 3.0) for d in ("20260909", "20260910", "20260911"))
    # Route 20: improves post-block.
    body += "".join(
        _lat_row("20", d, 3.0) for d in ("20260902", "20260903", "20260904")
    ) + "".join(_lat_row("20", d, 1.0) for d in ("20260909", "20260910", "20260911"))
    _write(lat, _LAT_HEADER + body)
    _write(
        roll,
        (
            "date,is_holiday,windows_completed,windows_partial,windows_missed,"
            "am_polled,observations,verifiable_trips,ghost_trips,"
            "boardings_lower_pax,filled_cells,n_recorded,pct_early_gt2\n"
            "2026-09-02,false,3,0,0,1,1,100,10,0,0,1000,25.0\n"
            "2026-09-09,false,3,0,0,1,1,100,5,0,0,900,25.0\n"
        ),
    )
    got = changeover.changeover()
    assert got["verdict_ready"] is True
    assert got["reason"] is None
    # Post side mixes route 10 (late) and route 20 (on-time): 6 obs, 3 on-time.
    assert got["post"]["pct_on_time"] == 50.0
    assert got["ghost_rate"] == {"pre": 10.0, "post": 5.0}
    assert got["departures_per_day"] == {"pre": 1000.0, "post": 900.0}
    by_route = {r["route"]: r for r in got["routes"]}
    assert by_route["10"]["delta_pp"] == -100.0
    assert by_route["20"]["delta_pp"] == 100.0
    # Regressions first.
    assert got["routes"][0]["route"] == "10"


def test_small_routes_omitted(patched):
    lat, _ = patched
    body = "".join(_lat_row("99", d, 1.0) for d in ("20260902", "20260909"))
    _write(lat, _LAT_HEADER + body)
    got = changeover.changeover()
    assert got["routes"] == []  # 2 obs < 20 per side


def test_forecast_rows_dropped_before_dedup(patched):
    lat, _ = patched
    body = (
        # horizon > 0 = vendor forecast, must never count as a departure.
        _lat_row("10", "20260902", 1.0, horizon=5.0)
        + _lat_row("10", "20260902", 1.0, horizon=-1.0)
    )
    _write(lat, _LAT_HEADER + body)
    got = changeover.changeover()
    assert got["pre"]["n_departures"] == 1
