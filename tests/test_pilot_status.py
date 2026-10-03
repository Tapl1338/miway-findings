"""Unit tests for scripts/pilot_status.py (on-demand pilot KPI table)."""

from datetime import date, timedelta

from scripts import pilot_status as ps

# ---------------------------------------------------------------------------
# Field ledger -> realized waits
# ---------------------------------------------------------------------------


def _ledger_rows():
    """Hub stop (Meadowvale) + one corridor-B stop with known departures.

    Hub: route 10 deps at 100/150/300, route 43 deps at 95/145/200.
    Buffer 2 min: 10@100 -> 43@145 (wait 43), 10@150 -> 43@200 (wait 48),
    10@300 -> no 43 in 60 min (miss). 43->10: waits 3 and 3, one miss.
    """
    return [
        {
            "date": "2026-08-28",
            "stop_name": "Meadowvale Town Centre Bus Terminal",
            "route": "10",
            "dep_time_min": "100",
        },
        {
            "date": "2026-08-28",
            "stop_name": "Meadowvale Town Centre Bus Terminal",
            "route": "10",
            "dep_time_min": "150",
        },
        {
            "date": "2026-08-28",
            "stop_name": "Meadowvale Town Centre Bus Terminal",
            "route": "10",
            "dep_time_min": "300",
        },
        {
            "date": "2026-08-28",
            "stop_name": "Meadowvale Town Centre Bus Terminal",
            "route": "43",
            "dep_time_min": "95",
        },
        {
            "date": "2026-08-28",
            "stop_name": "Meadowvale Town Centre Bus Terminal",
            "route": "43",
            "dep_time_min": "145",
        },
        {
            "date": "2026-08-28",
            "stop_name": "Meadowvale Town Centre Bus Terminal",
            "route": "43",
            "dep_time_min": "200",
        },
        {
            "date": "2026-08-28",
            "stop_name": "Eglinton & Dixie",
            "route": "35",
            "dep_time_min": "400",
        },
        {
            "date": "2026-08-28",
            "stop_name": "Eglinton & Dixie",
            "route": "35",
            "dep_time_min": "500",
        },
        {
            "date": "2026-08-28",
            "stop_name": "Eglinton & Dixie",
            "route": "7",
            "dep_time_min": "405",
        },
        {
            "date": "2026-08-28",
            "stop_name": "Eglinton & Dixie",
            "route": "7",
            "dep_time_min": "505",
        },
    ]


def test_ledger_pair_waits_math():
    stats = ps.ledger_pair_waits(_ledger_rows())
    hub = stats["Meadowvale Town Centre Bus Terminal"]
    by_key = {(p["from_route"], p["to_route"]): p for p in hub}
    # 10 -> 43: waits 43 and 48, one miss (300 -> nothing within 60).
    p1043 = by_key[("10", "43")]
    assert p1043["n_a"] == 3
    assert p1043["missed"] == 1
    assert sorted(p1043["waits"]) == [43.0, 48.0]
    # 43 -> 10: waits 3 and 3, one miss (200 -> nothing).
    p4310 = by_key[("43", "10")]
    assert p4310["n_a"] == 3
    assert p4310["missed"] == 1
    assert p4310["waits"] == [3.0, 3.0]


def test_pooled_stats_into_route_43():
    stats = ps.ledger_pair_waits(_ledger_rows())
    pairs = stats["Meadowvale Town Centre Bus Terminal"]
    pooled = ps.pooled_stats(pairs, to_route="43")
    assert pooled["n_a"] == 3  # only 10 -> 43 qualifies
    assert pooled["missed"] == 1
    assert round(pooled["missed_share"], 4) == round(1 / 3, 4)
    assert pooled["p90_min"] == 47.5
    # Without the filter, the 43 -> 10 pairings join the pool.
    all_pooled = ps.pooled_stats(pairs)
    assert all_pooled["n_a"] == 6


def test_ledger_skips_malformed_rows():
    rows = [
        *_ledger_rows(),
        {
            "stop_name": "Meadowvale Town Centre Bus Terminal",
            "route": "10",
            "dep_time_min": "not-a-number",
        },
        {"stop_name": "", "route": "10", "dep_time_min": "200"},
        {"stop_name": "X", "route": "", "dep_time_min": "200"},
        {"stop_name": "X", "route": "10", "dep_time_min": ""},
    ]
    stats = ps.ledger_pair_waits(rows)
    assert len(stats["Meadowvale Town Centre Bus Terminal"]) == 2  # 10->43, 43->10


def test_stop_stats_substring_match():
    stats = ps.ledger_pair_waits(_ledger_rows())
    name, pooled = ps._stop_stats(stats, "Eglinton & Dixie")
    assert name == "Eglinton & Dixie"
    assert pooled["n_a"] == 4  # 2 x 35->7 + 2 x 7->35
    # 35 -> 7 connects (3 min each); the 7 -> 35 return direction misses
    # (next 35 is 93 min later, beyond the 60 min horizon).
    assert pooled["missed"] == 2
    _, none = ps._stop_stats(stats, "Glen Erin Dr At Britannia Rd")
    assert none["n_a"] == 0


# ---------------------------------------------------------------------------
# Collector KPIs
# ---------------------------------------------------------------------------


def _lateness_csv(tmp_path, today_iso: str, lo: str, hi: str):
    p = tmp_path / "obs.csv"
    p.write_text(
        "route_short_name,stop_id,dep_time_min,lateness_minutes,horizon_minutes,date\n"
        f"43,1,100,-5.0,-30.0,{today_iso}\n"  # pilot, early
        f"43,1,120,1.0,-30.0,{today_iso}\n"  # pilot, on time
        f"10,2,130,-6.0,-30.0,{today_iso}\n"  # pilot, early
        f"1,3,140,-9.0,-30.0,{today_iso}\n"  # NOT pilot, early -> network only
        f"43,4,150,-5.0,5.0,{today_iso}\n"  # not recorded (horizon > 0)
        f"43,5,160,-5.0,-30.0,2026-01-01\n"  # outside span
        "43,6,170,-5.0,-30.0,\n",  # undated (legacy) -> excluded
        encoding="utf-8",
    )
    return p


def test_early_share_filters(tmp_path):
    today = date.today()
    lo = (today - timedelta(days=6)).isoformat()
    hi = today.isoformat()
    p = _lateness_csv(tmp_path, today.isoformat(), lo, hi)
    out = ps.early_share(p, ps.PILOT_ROUTES, lo, hi)
    assert out["read_error"] is False
    assert out["n"] == 3  # 43 early, 43 on time, 10 early
    assert out["share"] == round(100.0 * 2 / 3, 2)
    assert out["network_share"] == round(100.0 * 3 / 4, 2)  # route 1 joins network


def test_early_share_missing_file(tmp_path):
    out = ps.early_share(
        tmp_path / "nope.csv", ps.PILOT_ROUTES, "2026-08-01", "2026-08-31"
    )
    assert out["read_error"] is True
    assert out["share"] is None


def test_boardings_kpis(tmp_path):
    today = date.today()
    lo = (today - timedelta(days=6)).isoformat()
    hi = today.isoformat()
    daily = tmp_path / "daily.csv"
    daily.write_text(
        "route_short_name,period,service_date,boardings_lower_pax,data_status\n"
        f"43,midday,{today.strftime('%Y%m%d')},100.0,observed\n"
        f"43,pm_rush,{today.strftime('%Y%m%d')},50.0,observed\n"
        f"1,midday,{today.strftime('%Y%m%d')},999.0,observed\n"  # not pilot
        f"43,midday,20260101,77.0,observed\n",  # outside span
        encoding="utf-8",
    )
    routes = tmp_path / "routes.csv"
    routes.write_text(
        "route_short_name,period,boardings_lower_pax\n"
        "35,midday,7000.0\n35,am_rush,3000.0\n1,midday,9000.0\n",
        encoding="utf-8",
    )
    out = ps.boardings_kpis(
        ps._read_csv(daily), ps._read_csv(routes), ps.PILOT_ROUTES, lo, hi
    )
    assert out["r35_midday"] == 7000.0
    assert out["pilot_total"] == 150.0  # 100 + 50, route 1 and old date excluded
    assert out["pilot_route_days"] == 2


def test_ghost_kpis():
    rows = [
        # baseline window (Aug 17-26)
        {
            "service_date": "20260820",
            "route_short_name": "1",
            "verifiable_trips": "100",
            "ghost_count": "5",
        },
        {
            "service_date": "20260825",
            "route_short_name": "1",
            "verifiable_trips": "100",
            "ghost_count": "0",
        },
        # current span
        {
            "service_date": "20260828",
            "route_short_name": "1",
            "verifiable_trips": "100",
            "ghost_count": "2",
        },
    ]
    base, cur = ps.ghost_kpis(rows, "2026-08-27", "2026-08-29")
    assert base["rate"] == 2.5
    assert base["verifiable"] == 200
    assert cur["rate"] == 2.0
    assert cur["verifiable"] == 100


def test_checkin_counts():
    rows = [
        {
            "service_date": "20260818",
            "trip_id": "t1",
            "vehicle_id": "101",
            "route": "43",
        },
        {
            "service_date": "20260818",
            "trip_id": "t1",
            "vehicle_id": "101",
            "route": "43",
        },
        {
            "service_date": "20260818",
            "trip_id": "t2",
            "vehicle_id": "202",
            "route": "10",
        },
        {
            "service_date": "20260818",
            "trip_id": "t3",
            "vehicle_id": "303",
            "route": "1",
        },
    ]
    out = ps.checkin_counts(rows, ps.PILOT_ROUTES)
    assert out["checkins"] == 3
    assert out["trips"] == 2
    assert out["vehicles"] == 2
    # per_route counts distinct trips, not rows: both 43 rows are trip t1.
    assert out["per_route"] == {"43": 1, "10": 1}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _empty_kpis():
    return {
        "hub": ps.pooled_stats([]),
        "early": {"share": None, "n": 0, "network_share": None, "read_error": False},
        "board": {"r35_midday": None, "pilot_total": 0.0, "pilot_route_days": 0},
        "ghost_base": {"rate": None, "ghosts": 0, "verifiable": 0},
        "ghost_cur": {"rate": None, "ghosts": 0, "verifiable": 0},
        "checkins": {"checkins": 0, "trips": 0, "vehicles": 0, "per_route": {}},
        "cover": {"total_windows": 0, "completed_windows": 0},
    }


def test_render_no_ledger():
    k = _empty_kpis()
    text = ps.render_md(
        ("2026-08-23", "2026-08-29"),
        k["hub"],
        k["early"],
        k["board"],
        k["ghost_base"],
        k["ghost_cur"],
        k["checkins"],
        {},
        k["cover"],
    )
    assert "# Pilot KPI status" in text
    assert "| KPI | Baseline (frozen, pre-Sept-7) | Target | Now | Status |" in text
    assert "No field ledger rows yet" in text
    assert "NO DATA" in text
    assert "no field data yet" in text
    assert "## Worse-off stops watch" in text
    assert "Windwood Dr At Glen Erin Dr" in text


def test_render_with_ledger_met_and_flag():
    stats = ps.ledger_pair_waits(_ledger_rows())
    hub = ps.pooled_stats(stats["Meadowvale Town Centre Bus Terminal"], to_route="43")
    k = _empty_kpis()
    text = ps.render_md(
        ("2026-08-23", "2026-08-29"),
        hub,
        k["early"],
        k["board"],
        k["ghost_base"],
        k["ghost_cur"],
        k["checkins"],
        stats,
        k["cover"],
    )
    # 1/3 missed -> MET against the <= 36% target.
    assert "MET (<= 36%)" in text
    # p90 47.5 min -> above the 38.4 min baseline bound.
    assert "ABOVE BASELINE (>= 38.4 min)" in text
    assert "Eglinton & Dixie" in text
    assert "| 10 -> 43 | 3 | 1 |" in text  # per-pairing row


# ---------------------------------------------------------------------------
# main smoke
# ---------------------------------------------------------------------------


def _write_fixtures(tmp_path):
    today = date.today()
    lo = (today - timedelta(days=6)).isoformat()
    hi = today.isoformat()
    lat = _lateness_csv(tmp_path, today.isoformat(), lo, hi)

    daily = tmp_path / "daily.csv"
    daily.write_text(
        "route_short_name,period,service_date,boardings_lower_pax,data_status\n"
        f"43,midday,{today.strftime('%Y%m%d')},100.0,observed\n",
        encoding="utf-8",
    )
    routes = tmp_path / "routes.csv"
    routes.write_text(
        "route_short_name,period,boardings_lower_pax\n35,midday,7000.0\n",
        encoding="utf-8",
    )
    ghost = tmp_path / "ghost.csv"
    ghost.write_text(
        "service_date,route_short_name,scheduled_trips,verifiable_trips,"
        "observed_trips,ghost_count\n"
        f"{today.strftime('%Y%m%d')},1,10,100,98,2\n",
        encoding="utf-8",
    )
    checkins = tmp_path / "checkins.csv"
    checkins.write_text(
        "ts,service_date,vehicle_id,trip_id,route\n"
        "2026-08-18 12:00:00,20260818,101,t1,43\n",
        encoding="utf-8",
    )
    cov = tmp_path / "coverage.csv"
    cov.write_text(
        "date,scheduled,status,polls_succeeded,polls_attempted,observations\n"
        f"{today.isoformat()},06:00-09:00,completed,12,12,300\n",
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.csv"
    ledger.write_text(
        "date,stop_name,route,dep_time_min\n"
        f"{today.isoformat()},Meadowvale Town Centre Bus Terminal,10,100\n"
        f"{today.isoformat()},Meadowvale Town Centre Bus Terminal,43,145\n",
        encoding="utf-8",
    )
    return lat, daily, routes, ghost, checkins, cov, ledger


def test_main_smoke(tmp_path, capsys):
    lat, daily, routes, ghost, checkins, cov, ledger = _write_fixtures(tmp_path)
    ps.main(
        [
            "--days",
            "7",
            "--lateness-csv",
            str(lat),
            "--boardings-daily-csv",
            str(daily),
            "--boardings-routes-csv",
            str(routes),
            "--ghost-csv",
            str(ghost),
            "--checkins-csv",
            str(checkins),
            "--coverage-csv",
            str(cov),
            "--ledger",
            str(ledger),
        ]
    )
    out = capsys.readouterr().out
    assert "# Pilot KPI status" in out
    assert "MET (<= 36%)" in out  # 10@100 -> 43@145 is a clean connection
    assert "Boardings, route 35 midday (LB)" in out
    assert "Collection health (control)" in out


def test_main_with_out_writes_file(tmp_path):
    lat, daily, routes, ghost, checkins, cov, ledger = _write_fixtures(tmp_path)
    out = tmp_path / "status.md"
    ps.main(
        [
            "--days",
            "7",
            "--lateness-csv",
            str(lat),
            "--boardings-daily-csv",
            str(daily),
            "--boardings-routes-csv",
            str(routes),
            "--ghost-csv",
            str(ghost),
            "--checkins-csv",
            str(checkins),
            "--coverage-csv",
            str(cov),
            "--ledger",
            str(ledger),
            "--out",
            str(out),
        ]
    )
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "# Pilot KPI status" in text
