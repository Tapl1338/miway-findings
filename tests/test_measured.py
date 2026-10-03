"""Unit tests for the measured-vs-modeled router readers.

Exercises `_read_realized_waits` and `_read_ride_speeds` against tmp CSVs:
missing files, empty files, derived fields (delta, departure-weighted mean),
and row ordering.
"""

from pathlib import Path

from app.routers import measured

_WAITS_HEADER = (
    "from_route,to_route,n_a_departures,sched_mean_min,sched_median_min,"
    "sched_p90_min,missed_or_beyond_share,realized_mean_min,realized_median_min,"
    "realized_p90_min,realized_missed_share\n"
)
_WAITS_ROWS = (
    "90,42,52,4.23,3.0,9.7,0.0,7.03,5.46,15.6,0.0\n"
    "10,43,39,21.12,22.5,37.0,0.59,22.1,22.1,41.22,0.585\n"
    "43,42,9,7.67,8.0,13.0,0.0,8.06,7.54,15.01,0.0\n"
)

_SPEED_HEADER = (
    "vehicle_id,trip_id,route,first,last,elapsed_min,distance_km,"
    "avg_kmh_incl_stops,avg_kmh_moving,peak_kmh,stall_segments,"
    "max_stall_kmh,ride_rows\n"
)
_SPEED_ROWS = (
    "3289,30310255,42,2026-08-18T12:15,2026-08-18T12:57,29.2,10.89,22.4,30.1,61.7,13,4.0,24\n"
    "2302,30309453,10,2026-08-20T13:57,2026-08-20T15:02,61.1,18.15,17.8,21.3,46.2,18,4.7,39\n"
)


def _write(path: Path, header: str, body: str):
    path.write_text(header + body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# realized waits
# ---------------------------------------------------------------------------


def test_realized_missing(tmp_path):
    got = measured._read_realized_waits(tmp_path / "nope.csv")
    assert got == {"available": False, "file": "nope.csv", "rows": []}


def test_realized_empty(tmp_path):
    got = measured._read_realized_waits(_write(tmp_path / "w.csv", _WAITS_HEADER, ""))
    assert got["available"] is False


def test_realized_rows_and_delta(tmp_path):
    got = measured._read_realized_waits(
        _write(tmp_path / "w.csv", _WAITS_HEADER, _WAITS_ROWS)
    )
    assert got["available"] is True
    assert got["file"] == "w.csv"
    assert got["venue"] == "Meadowvale Town Centre Bus Terminal"
    assert got["n_pairs"] == 3
    assert got["n_departures"] == 100

    # Rows sorted by worst measured-vs-scheduled delta first: 90→42 (+2.8) leads.
    assert got["rows"][0]["from_route"] == "90"
    assert got["rows"][0]["to_route"] == "42"
    assert got["rows"][0]["delta_min"] == 2.8

    # delta = realized_mean - sched_mean.
    by_pair = {(r["from_route"], r["to_route"]): r for r in got["rows"]}
    assert by_pair[("10", "43")]["delta_min"] == pytest_approx(22.1 - 21.12)
    assert by_pair[("43", "42")]["delta_min"] == pytest_approx(8.06 - 7.67)


def test_realized_waits_nan_counts_do_not_crash(tmp_path):
    """A NaN in a count column (a partial read from the collector's non-atomic
    rewrite) must not crash the reader — previously ``int(nan)`` raised
    ``ValueError`` → an intermittent 500 on ``/api/measured``.
    """
    got = measured._read_realized_waits(
        _write(
            tmp_path / "w.csv",
            _WAITS_HEADER,
            _WAITS_ROWS + "10,39,nan,10.0,9.0,20.0,0.0,11.5,10.0,24.0,0.0\n",
        )
    )
    assert got["available"] is True
    nan_row = next(
        r for r in got["rows"] if r["from_route"] == "10" and r["to_route"] == "39"
    )
    assert nan_row["n_a_departures"] == 0  # NaN degrades to 0, not a crash


def test_realized_departure_weighted(tmp_path):
    got = measured._read_realized_waits(
        _write(tmp_path / "w.csv", _WAITS_HEADER, _WAITS_ROWS)
    )
    dw = got["departure_weighted"]
    assert dw is not None
    # Σ(sched*n)/Σn across the three rows, n = [52, 39, 9].
    sw = (4.23 * 52 + 21.12 * 39 + 7.67 * 9) / 100
    rw = (7.03 * 52 + 22.1 * 39 + 8.06 * 9) / 100
    assert dw["sched_mean_min"] == pytest_approx(round(sw, 2))
    assert dw["realized_mean_min"] == pytest_approx(round(rw, 2))
    assert dw["delta_min"] == pytest_approx(round(rw - sw, 2))


# ---------------------------------------------------------------------------
# ride speeds
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# published APC vs measured floor
# ---------------------------------------------------------------------------

_RIDERSHIP_HEADER = (
    "route_short_name,route_long_name,boardings,day_type,period,source,"
    "is_estimate,measured_lower_bound,estimate_method\n"
)
_RIDERSHIP_ROWS = (
    "35,Eglinton,10796.0,weekday,October 2024 board period,"
    "MiWay 2024 Report to the Community (APC),False,2287.9,published\n"
    "42,Derry,10750.0,weekday,October 2024 board period,"
    "MiWay 2024 Report to the Community (APC),False,1219.0,published\n"
    "18,Derry,7750.0,weekday,October 2024 board period,"
    "calibrated estimate (scripts/build_ridership_dataset.py),True,1795.9,measured-uplift\n"
)


def test_apc_missing(tmp_path):
    got = measured._read_published_apc(tmp_path / "nope.csv")
    assert got == {"available": False, "file": "nope.csv", "rows": []}


def test_apc_filters_to_published_routes_and_capture(tmp_path):
    got = measured._read_published_apc(
        _write(tmp_path / "ridership.csv", _RIDERSHIP_HEADER, _RIDERSHIP_ROWS)
    )
    assert got["available"] is True
    assert got["file"] == "ridership.csv"
    assert got["period"] == "October 2024 board period"
    assert got["day_type"] == "weekday"
    # Route 18 is a calibrated estimate, not a published APC row -> excluded.
    assert got["n_routes"] == 2
    # Sorted by capture ascending (worst gap first): 42 (11.3%) before 35.
    assert [r["route"] for r in got["rows"]] == ["42", "35"]
    r42 = got["rows"][0]
    assert r42["long_name"] == "Derry"
    assert r42["published_boardings"] == 10750.0
    assert r42["measured_floor"] == 1219.0
    assert r42["capture_pct"] == pytest_approx(1219.0 / 10750.0 * 100, rel=1e-2)
    # Aggregate capture across the two published routes.
    tot_pub = 10750.0 + 10796.0
    tot_meas = 1219.0 + 2287.9
    assert got["total_published"] == pytest_approx(tot_pub)
    assert got["total_measured"] == pytest_approx(tot_meas)
    assert got["mean_capture_pct"] == pytest_approx(tot_meas / tot_pub * 100, rel=1e-2)
    # Network anchors: calibrated total = ALL ridership rows (incl. the route
    # 18 estimate), implied weekday anchors from the public annual figures.
    net = got["network"]
    assert net["calibrated_weekday"] == pytest_approx(10750.0 + 10796.0 + 7750.0)
    assert net["anchor_2024_weekday"] == pytest_approx(58.4e6 / 322)
    assert net["anchor_2025_weekday"] == pytest_approx(52.1e6 / 322)
    assert net["annual_2024_m"] == 58.4
    assert net["annual_2025_m"] == 52.1


def test_apc_empty_ridership(tmp_path):
    got = measured._read_published_apc(
        _write(tmp_path / "ridership.csv", _RIDERSHIP_HEADER, "")
    )
    assert got == {"available": False, "file": "ridership.csv", "rows": []}


def test_speeds_missing(tmp_path):
    got = measured._read_ride_speeds(tmp_path / "nope.csv")
    assert got == {"available": False, "file": "nope.csv", "rows": []}


def test_speeds_rows_and_order(tmp_path):
    got = measured._read_ride_speeds(
        _write(tmp_path / "sp.csv", _SPEED_HEADER, _SPEED_ROWS)
    )
    assert got["available"] is True
    assert got["file"] == "sp.csv"
    assert len(got["rows"]) == 2
    # Sorted by elapsed_min ascending (shortest ride first).
    assert got["rows"][0]["elapsed_min"] == 29.2
    assert got["rows"][1]["elapsed_min"] == 61.1
    r = got["rows"][0]
    assert r["route"] == "42"
    assert r["avg_kmh_moving"] == 30.1
    assert r["stall_segments"] == 13


def test_speeds_nan_counts_do_not_crash(tmp_path):
    """Same NaN-in-count-column guard for stall_segments/ride_rows."""
    got = measured._read_ride_speeds(
        _write(
            tmp_path / "sp.csv",
            _SPEED_HEADER,
            _SPEED_ROWS + "9999,99999999,42,x,y,25.0,9.0,20.0,28.0,55.0,nan,3.0,nan\n",
        )
    )
    assert got["available"] is True
    r = next(x for x in got["rows"] if x["vehicle_id"] == "9999")
    assert r["stall_segments"] == 0
    assert r["ride_rows"] == 0


def pytest_approx(v, rel=1e-3):
    import pytest

    return pytest.approx(v, rel=rel)
