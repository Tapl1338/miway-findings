"""Unit tests for ``scripts/weekly_charts.py`` (weekly trend charts).

Pure helpers only: hourly occupancy bucketing, boardings/ghost/lateness
aggregation, and the inline-SVG chart renderers. No network, no matplotlib.
"""

import json

from scripts.weekly_charts import (
    bar_chart,
    boardings_by_period,
    crowded_routes,
    ghosts_by_hour,
    hourly_occupancy,
    hourly_occupancy_by_route,
    lateness_by_hour,
    line_chart,
)

_TORONTO_EPOCH = 1770000000  # any epoch; bucketing is hour-of-day only


def _snapshot(polls):
    return {"polls": polls}


def _poll(ts, buses):
    return {"fetched_at": ts, "buses": buses}


def _bus(pct=None, status=3):
    b = {"trip_id": "t1", "vehicle_id": "v1", "service_date": "20260818"}
    if pct is not None:
        b["occupancy_percentage"] = pct
    b["occupancy_status"] = status
    return b


def test_hourly_occupancy_buckets_by_toronto_hour(monkeypatch, tmp_path):
    # Two polls at different hours; third poll missing occupancy (skipped).
    import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Toronto")
    ts_8 = datetime.datetime(2026, 8, 18, 8, 15, tzinfo=tz).timestamp()
    ts_9 = datetime.datetime(2026, 8, 18, 9, 5, tzinfo=tz).timestamp()
    ts_10 = datetime.datetime(2026, 8, 18, 10, 0, tzinfo=tz).timestamp()

    snaps = [
        _snapshot(
            [
                _poll(ts_8, [_bus(40), _bus(60)]),
                _poll(ts_9, [_bus(50), _bus(80)]),
                _poll(ts_10, [_bus()]),  # no percentage -> excluded
            ]
        )
    ]

    # Write into a temp collections dir and point the module at it.
    cdir = tmp_path / "collections"
    cdir.mkdir()
    (cdir / "vp_20260818_0800.json").write_text(json.dumps(snaps[0]), encoding="utf-8")
    monkeypatch.setattr("scripts.weekly_charts.COLLECTIONS_DIR", cdir)

    occ = hourly_occupancy("2026-08-18", "2026-08-18")
    assert occ[8]["mean"] == 50.0  # (40 + 60) / 2
    assert occ[8]["p90"] == 58.0  # quantile 0.9 of [40, 60]
    assert occ[9]["mean"] == 65.0
    assert occ[9]["n"] == 2
    assert 10 not in occ  # only the empty-bus poll -> no valid pct


def test_hourly_occupancy_filters_span(monkeypatch, tmp_path):
    import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Toronto")
    ts = datetime.datetime(2026, 8, 17, 15, 0, tzinfo=tz).timestamp()
    cdir = tmp_path / "collections"
    cdir.mkdir()
    (cdir / "vp_20260817_1500.json").write_text(
        json.dumps(_snapshot([_poll(ts, [_bus(40)])])), encoding="utf-8"
    )
    monkeypatch.setattr("scripts.weekly_charts.COLLECTIONS_DIR", cdir)

    # Outside the span -> nothing.
    assert hourly_occupancy("2026-08-18", "2026-08-18") == {}
    # Inside the span -> bucketed.
    occ = hourly_occupancy("2026-08-17", "2026-08-17")
    assert occ[15]["mean"] == 40.0


def test_boardings_by_period_handles_nan(monkeypatch, tmp_path):
    csv = tmp_path / "boardings_daily.csv"
    csv.write_text(
        "route_short_name,period,service_date,boardings_lower_pax,data_status\n"
        "1,am_rush,20260817,100.0,observed\n"
        "2,am_rush,20260817,50.5,observed\n"
        "3,midday,20260817,nan,insufficient\n"  # missing value -> treated as 0
        "4,pm_rush,20260818,25.0,observed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.weekly_charts.BOARDINGS_DAILY_CSV", csv)
    board = boardings_by_period("2026-08-17", "2026-08-18")
    assert board["am_rush"]["2026-08-17"] == 150.5
    assert board["midday"]["2026-08-17"] == 0.0  # nan -> 0, but period still listed
    assert board["pm_rush"]["2026-08-18"] == 25.0
    assert "2026-08-17" not in board["pm_rush"]


def test_ghosts_by_hour_parses_scheduled_times(monkeypatch, tmp_path):
    csv = tmp_path / "ghost_trips.csv"
    csv.write_text(
        "service_date,route_short_name,ghost_count,ghosts\n"
        "20260817,1,2,a@07:15;b@07:20\n"
        "20260817,2,1,c@19:05\n"
        "20260818,3,0,\n"
        "20260810,4,9,x@09:00\n",  # out of span
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.weekly_charts.GHOST_CSV", csv)
    g = ghosts_by_hour("2026-08-17", "2026-08-18")
    assert g[7] == 2
    assert g[19] == 1
    assert 9 not in g  # out-of-span day excluded
    assert sum(g.values()) == 3


def test_lateness_by_hour_aggregates(monkeypatch, tmp_path):
    csv = tmp_path / "obs_lateness.csv"
    csv.write_text(
        "route_short_name,stop_id,dep_time_min,lateness_minutes,horizon_minutes\n"
        "1,100,420.0,1.0,-30\n"  # 07:00
        "1,101,425.0,3.0,-30\n"  # 07:00
        "2,200,600.0,5.0,-30\n",  # 10:00
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.weekly_charts.LATENESS_CSV", csv)
    late = lateness_by_hour("2026-08-17", "2026-08-23")
    assert late[7]["mean"] == 2.0
    assert late[7]["n"] == 2
    assert late[10]["mean"] == 5.0


def test_crowded_routes_top_12(monkeypatch, tmp_path):
    csv = tmp_path / "occupancy_stats.csv"
    rows = [
        f"{i},pm_rush,100,100,{i}.0,{i * 2}.0,10,10.0,0,80,10,5,0,0,0"
        for i in range(1, 20)
    ]
    csv.write_text(
        "route_short_name,period,n_observations,n_with_status,n_with_percentage,"
        "mean_percentage,p90_percentage,n_crowded,crowded_share_pct,n_empty,"
        "n_many_seats,n_few_seats,n_standing,n_crushed,n_full,n_no_data\n"
        + "\n".join(rows),
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.weekly_charts.OCCUPANCY_STATS_CSV", csv)
    routes = crowded_routes()
    assert len(routes) == 12  # capped at 12
    # Highest mean percentage is first.
    assert next(iter(routes)) == "19"


def test_hourly_occupancy_by_route_maps_trip_to_route(monkeypatch, tmp_path):
    import datetime
    from zoneinfo import ZoneInfo

    # Static GTFS with two trips on different routes.
    gtfs = tmp_path / "gtfs"
    gtfs.mkdir()
    (gtfs / "trips.txt").write_text(
        "route_id,service_id,trip_id\nt1,wk,ta\nt2,wk,tb\n", encoding="utf-8"
    )
    (gtfs / "routes.txt").write_text(
        "route_id,route_short_name\nt1,1\nt2,9\n", encoding="utf-8"
    )
    monkeypatch.setattr("scripts.weekly_charts.config.LOCAL_GTFS_DIR", gtfs)

    tz = ZoneInfo("America/Toronto")
    ts = datetime.datetime(2026, 8, 18, 9, 0, tzinfo=tz).timestamp()
    cdir = tmp_path / "collections"
    cdir.mkdir()
    (cdir / "vp_x.json").write_text(
        json.dumps(
            _snapshot(
                [
                    _poll(
                        ts,
                        [
                            {
                                "trip_id": "ta",
                                "occupancy_percentage": 40,
                                "occupancy_status": 3,
                            },
                            {
                                "trip_id": "tb",
                                "occupancy_percentage": 80,
                                "occupancy_status": 3,
                            },
                        ],
                    )
                ]
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.weekly_charts.COLLECTIONS_DIR", cdir)

    by_route = hourly_occupancy_by_route("2026-08-18", "2026-08-18", top_n=2)
    assert by_route["1"][9] == 40.0
    assert by_route["9"][9] == 80.0


def test_export_pngs_writes_svgs_even_without_browser(monkeypatch, tmp_path):
    monkeypatch.setattr("scripts.weekly_charts.CHART_PNG_DIR", tmp_path / "charts")
    monkeypatch.setattr("scripts.weekly_charts._find_browser", lambda: None)
    from scripts.weekly_charts import export_pngs

    n = export_pngs([("test_chart", "<svg xmlns='x'></svg>")])
    assert n == 0  # no browser -> no PNGs
    assert (tmp_path / "charts" / "test_chart.svg").exists()  # SVG still written


def test_line_chart_renders_svg():
    svg = line_chart(
        "Test",
        [("mean", [10.0, 20.0, 30.0], "#1f77b4")],
        ["08:00", "09:00", "10:00"],
        "percent",
    )
    assert svg.startswith("<svg")
    assert "Test" in svg
    assert "M " in svg  # a path was drawn
    assert "#1f77b4" in svg


def test_bar_chart_renders_svg_and_handles_zero_max():
    # All-zero series must not divide by zero.
    svg = bar_chart(
        "Zero test",
        ["a", "b"],
        [("s", [0.0, 0.0], "#d62728")],
        "count",
    )
    assert "<svg" in svg
    assert "nan" not in svg


def test_bar_chart_grouped_series():
    svg = bar_chart(
        "Grouped",
        ["day1", "day2"],
        [("x", [1.0, 2.0], "#1f77b4"), ("y", [3.0, 4.0], "#d62728")],
        "n",
    )
    assert "day1" in svg and "day2" in svg
    assert svg.count("<rect") >= 4
    assert "nan" not in svg


def test_lateness_by_hour_survives_mixed_dtype_columns(monkeypatch, tmp_path):
    """Regression: obs_lateness.csv columns can read as object dtype (mixed
    types in the real file), which used to crash ``lateness_by_hour`` with
    ``unsupported operand type(s) for //: 'str' and 'int'``. Unparseable
    rows must be dropped, not fatal.
    """
    import pandas as pd

    csv = tmp_path / "obs_lateness.csv"
    csv.write_text(
        "route_short_name,stop_id,dep_time_min,lateness_minutes,horizon_minutes\n"
        "1,100,420.0,1.0,-30\n"  # 07:00, clean row
        "1,101,not-a-time,3.0,-30\n"  # unparseable dep_time_min -> dropped
        "2,200,600.0,late,-30\n"  # unparseable lateness -> dropped
        "2,201,610.0,5.0,-30\n",  # 10:00, clean row
        encoding="utf-8",
    )
    # Prove the mixed-type condition is actually present (pandas reads the
    # columns as a string dtype, not numeric — the exact pre-fix failure
    # condition that made ``// 60`` raise).
    raw = pd.read_csv(csv)
    assert not pd.api.types.is_numeric_dtype(raw["dep_time_min"])
    assert not pd.api.types.is_numeric_dtype(raw["lateness_minutes"])

    monkeypatch.setattr("scripts.weekly_charts.LATENESS_CSV", csv)
    late = lateness_by_hour("2026-08-17", "2026-08-23")
    assert late[7]["mean"] == 1.0
    assert late[7]["n"] == 1  # the unparseable row did not pollute the count
    assert late[10]["mean"] == 5.0
    assert late[10]["n"] == 1
    assert sum(v["n"] for v in late.values()) == 2


def test_snapshot_paths_filters_by_since(monkeypatch, tmp_path):
    """The incremental --since cut must skip snapshots older than the given
    mtime so post-window chart runs don't rescan months of files.
    """
    import os
    import time

    from scripts.weekly_charts import _snapshot_paths

    cdir = tmp_path / "collections"
    cdir.mkdir()
    old = cdir / "vp_20260801_0800.json"
    new = cdir / "vp_20260902_0900.json"
    old.write_text("{}", encoding="utf-8")
    new.write_text("{}", encoding="utf-8")

    cut = time.time() - 100
    os.utime(old, (cut - 1000, cut - 1000))  # well before the cut
    os.utime(new, (cut + 50, cut + 50))  # after the cut

    monkeypatch.setattr("scripts.weekly_charts.COLLECTIONS_DIR", cdir)

    # No cut -> everything, sorted by name.
    assert _snapshot_paths() == [old, new]
    # With the cut -> only the recent snapshot survives.
    assert _snapshot_paths(since=cut) == [new]
    # Cut before both -> everything again.
    assert _snapshot_paths(since=cut - 5000) == [old, new]
