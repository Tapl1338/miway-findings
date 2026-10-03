"""Tests for the collection-coverage router (``app/routers/coverage.py``).

The endpoint is a dumb reader of the collector's per-window records, so the
pure ``build_payload`` helper is tested directly against synthetic coverage
directories — no GTFS feed, no app, fast.
"""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.routers import coverage

TS = "%Y-%m-%d %H:%M:%S"
# UTC-aware fixed clock. Production coverage STAMPS (window_end etc.) are
# America/Toronto wall clock (parsed with ZoneInfo since the 2026-09-09 TZ
# fix), while production mtimes compare against UTC — so FUTURE/PAST below
# are built as offsets from a UTC clock but interpreted in Toronto by the
# code under test. For the between-windows test to truly exercise "window
# already over", its end stamp must be PAST IN TORONTO: PAST_TOR_END is
# constructed to read as 08:00 Toronto = 12:00 UTC (04:00 EDT in August),
# i.e. genuinely ended relative to NOW rather than 3h in Toronto's future
# (the trap the UTC misreading used to hide).
NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
FUTURE = (NOW + timedelta(hours=3)).strftime(TS)
PAST = (NOW - timedelta(hours=3)).strftime(TS)
# A wall-clock stamp that, read as Toronto time, is already over at NOW
# (12:00 UTC = 08:00 Toronto UTC-4 in August): 07:00 Toronto.
PAST_TOR_END = "2026-08-30 07:00:00"


def _window(
    name: str,
    status: str,
    date: str = "2026-08-30",
    scheduled: str = "09:00-15:00",
    polls_succeeded: int = 60,
    polls_attempted: int = 60,
    polls_failed: int = 0,
    observations: int = 100,
    vp_snapshots: int = 50,
    longest_gap_min: float = 0.0,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict:
    return {
        "name": name,
        "date": date,
        "window_start": window_start or f"{date} 09:00:00",
        "window_end": window_end or f"{date} 15:00:00",
        "scheduled": scheduled,
        "status": status,
        "polls_attempted": polls_attempted,
        "polls_succeeded": polls_succeeded,
        "polls_failed": polls_failed,
        "first_poll_at": f"{date} 09:00:05",
        "last_poll_at": f"{date} 14:59:30",
        "observations": observations,
        "vp_snapshots": vp_snapshots,
        "longest_gap_min": longest_gap_min,
        "polls_timeout": 0,
    }


def _write_dir(tmp_path: Path, windows: list[dict]) -> Path:
    cov = tmp_path / "coverage"
    cov.mkdir(exist_ok=True)
    for w in windows:
        (cov / f"{w['name']}.json").write_text(
            json.dumps(w, indent=2), encoding="utf-8"
        )
    return cov


# ---------------------------------------------------------------------------
# build_payload: empty / missing data
# ---------------------------------------------------------------------------


def test_build_payload_empty_dir(tmp_path):
    payload = coverage.build_payload(
        tmp_path / "coverage", tmp_path / "collector.pid", NOW
    )
    assert payload["available"] is False
    assert payload["summary"]["windows"] == 0
    assert payload["issues"] == []
    assert payload["recent"] == []
    assert payload["collector"]["running"] is False
    assert payload["collector"]["status"] == "stopped"


def test_build_payload_garbage_json_skipped(tmp_path):
    cov = tmp_path / "coverage"
    cov.mkdir()
    (cov / "window_bad.json").write_text("{not json", encoding="utf-8")
    (cov / "window_empty.json").write_text("{}", encoding="utf-8")
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert payload["available"] is False  # nothing parseable -> no data


# ---------------------------------------------------------------------------
# build_payload: summary + issues + ordering
# ---------------------------------------------------------------------------


def test_build_payload_mixed_statuses(tmp_path):
    cov = _write_dir(
        tmp_path,
        [
            _window("window_20260830_0900", "completed", date="2026-08-30"),
            _window(
                "window_20260829_0900",
                "partial",
                date="2026-08-29",
                polls_succeeded=40,
                polls_attempted=60,
                polls_failed=20,
            ),
            _window(
                "window_20260828_0900",
                "missed",
                date="2026-08-28",
                polls_succeeded=0,
                polls_attempted=60,
                polls_failed=60,
                observations=0,
                vp_snapshots=0,
            ),
            _window(
                "window_20260827_0900",
                "interrupted",
                date="2026-08-27",
                polls_succeeded=10,
                polls_attempted=30,
                observations=5,
                vp_snapshots=2,
            ),
            _window(
                "window_20260830_1500",
                "collecting",
                date="2026-08-30",
                scheduled="15:00-19:00",
                window_start="2026-08-30 15:00:00",
                window_end=FUTURE,
                polls_succeeded=3,
                polls_attempted=4,
                observations=0,
                vp_snapshots=0,
            ),
        ],
    )
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert payload["available"] is True

    s = payload["summary"]
    assert s["windows"] == 5
    assert s["days"] == 4  # 30th appears twice (09:00 + live 15:00)
    assert s["first_date"] == "2026-08-27"
    assert s["last_date"] == "2026-08-30"
    assert s["by_status"] == {
        "completed": 1,
        "partial": 1,
        "missed": 1,
        "interrupted": 1,
        "collecting": 1,
    }
    # completed / (completed+partial) shares over all recorded windows
    assert s["completed_share_pct"] == 20.0
    assert s["ok_share_pct"] == 40.0
    # polls: 60+60+60+30+4 attempted, 60+40+0+10+3 succeeded
    assert s["poll_success_rate_pct"] == round(113 / 214 * 100, 1)
    assert s["observations"] == 100 + 100 + 0 + 5 + 0
    assert s["vp_snapshots"] == 50 + 50 + 0 + 2 + 0

    # Hard issues: missed + interrupted only (partial stays in the table),
    # newest window first like the recent list.
    assert [i["status"] for i in payload["issues"]] == ["missed", "interrupted"]
    miss = next(i for i in payload["issues"] if i["status"] == "missed")
    assert "silent gap" in miss["note"]

    # Newest window first — the live collecting window leads the list.
    assert payload["recent"][0]["status"] == "collecting"
    assert payload["recent"][0]["window_start"] == "2026-08-30 15:00:00"
    assert payload["recent"][-1]["status"] == "interrupted"


def test_build_payload_recent_capped(tmp_path):
    windows = [
        _window(
            f"window_202608{day:02d}_0900",
            "completed",
            date=f"2026-08-{day:02d}",
            window_start=f"2026-08-{day:02d} 09:00:00",
        )
        for day in range(10, 31)
    ]
    cov = _write_dir(tmp_path, windows)
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert len(payload["recent"]) == 14
    assert payload["summary"]["windows"] == 21


def test_build_payload_no_gaps_longest_none(tmp_path):
    cov = _write_dir(tmp_path, [_window("window_20260830_0900", "completed")])
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert payload["summary"]["longest_gap_min"] is None


def test_build_payload_longest_gap_taken(tmp_path):
    cov = _write_dir(
        tmp_path,
        [
            _window("window_a", "completed", longest_gap_min=1.0),
            _window("window_b", "partial", longest_gap_min=37.4),
        ],
    )
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert payload["summary"]["longest_gap_min"] == 37.4


# ---------------------------------------------------------------------------
# scheduled-window merge (mid-window restart writes duplicate records)
# ---------------------------------------------------------------------------


def test_merge_windows_collapses_restart_into_one_unit(tmp_path):
    """A mid-window restart writes two records for one scheduled window;
    they must collapse into a single window (one (date, scheduled) unit)."""
    cov = _write_dir(
        tmp_path,
        [
            _window(
                "window_20260830_0910",
                "interrupted",
                date="2026-08-30",
                scheduled="09:00-15:00",
                window_start="2026-08-30 09:10:00",
                window_end=FUTURE,
                polls_succeeded=40,
                polls_attempted=40,
                observations=800,
                vp_snapshots=40,
            ),
            _window(
                "window_20260830_1052",
                "collecting",
                date="2026-08-30",
                scheduled="09:00-15:00",
                window_start="2026-08-30 10:52:00",
                window_end=FUTURE,
                polls_succeeded=3,
                polls_attempted=4,
                observations=4,
                vp_snapshots=3,
            ),
        ],
    )
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    s = payload["summary"]
    assert s["windows"] == 1  # ONE scheduled window, not two
    assert s["days"] == 1
    # A live window still reads as collecting, and polls/obs sum across the
    # two run segments.
    assert s["by_status"] == {"collecting": 1}
    assert s["observations"] == 804
    assert s["vp_snapshots"] == 43

    # recent shows the merged window only, with an n_segments field.
    assert len(payload["recent"]) == 1
    ro = payload["recent"][0]
    assert ro["scheduled"] == "09:00-15:00"
    assert ro["n_segments"] == 2
    assert ro["polls_attempted"] == 44


def test_merge_windows_recovered_completed_wins(tmp_path):
    """A window interrupted once but resumed and completed is COMPLETED in
    the merged view (it did eventually finish), not penalized as interrupted."""
    cov = _write_dir(
        tmp_path,
        [
            _window(
                "window_20260830_0910",
                "interrupted",
                date="2026-08-30",
                scheduled="09:00-15:00",
                window_start="2026-08-30 09:10:00",
                window_end="2026-08-30 15:00:00",
            ),
            _window(
                "window_20260830_1052",
                "completed",
                date="2026-08-30",
                scheduled="09:00-15:00",
                window_start="2026-08-30 10:52:00",
                window_end="2026-08-30 15:00:00",
                polls_succeeded=200,
                polls_attempted=200,
                observations=2000,
                vp_snapshots=200,
            ),
        ],
    )
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    s = payload["summary"]
    assert s["windows"] == 1
    assert s["by_status"] == {"completed": 1}
    assert s["completed_share_pct"] == 100.0
    assert payload["recent"][0]["n_segments"] == 2
    assert payload["issues"] == []  # no gap: the window finished


def test_merge_windows_never_recovered_stays_interrupted(tmp_path):
    """A window whose segments were ALL interrupted (never recovered) must
    still surface as an interruption in the summary, summed across segments."""
    cov = _write_dir(
        tmp_path,
        [
            _window(
                "window_20260830_0910",
                "interrupted",
                date="2026-08-30",
                scheduled="09:00-15:00",
                window_start="2026-08-30 09:10:00",
                window_end="2026-08-30 10:00:00",
                polls_succeeded=10,
                polls_attempted=15,
                observations=50,
            ),
            _window(
                "window_20260830_1010",
                "interrupted",
                date="2026-08-30",
                scheduled="09:00-15:00",
                window_start="2026-08-30 10:10:00",
                window_end="2026-08-30 10:30:00",
                polls_succeeded=5,
                polls_attempted=8,
                observations=20,
            ),
        ],
    )
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    s = payload["summary"]
    assert s["windows"] == 1
    assert s["by_status"] == {"interrupted": 1}
    assert s["observations"] == 70
    assert len(payload["issues"]) == 1
    assert payload["issues"][0]["status"] == "interrupted"


# ---------------------------------------------------------------------------
# CSV fallback (old deployments without per-window JSONs)
# ---------------------------------------------------------------------------


def test_build_payload_csv_fallback(tmp_path):
    cov = tmp_path / "coverage"
    cov.mkdir()
    (cov / "collection_windows.csv").write_text(
        "date,window_start,window_end,scheduled,status,polls_attempted,"
        "polls_succeeded,polls_failed,first_poll_at,last_poll_at,observations,"
        "vp_snapshots,longest_gap_min,polls_timeout\n"
        "2026-08-28,2026-08-28 09:00:00,2026-08-28 15:00:00,09:00-15:00,missed,"
        "60,0,60,,,0,0,0,0\n",
        encoding="utf-8",
    )
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert payload["available"] is True
    assert payload["summary"]["windows"] == 1
    assert payload["summary"]["by_status"] == {"missed": 1}
    assert len(payload["issues"]) == 1


# ---------------------------------------------------------------------------
# collector liveness / freshness
# ---------------------------------------------------------------------------


def test_collector_stopped_no_pid(tmp_path):
    cov = _write_dir(tmp_path, [_window("window_a", "completed")])
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert payload["collector"]["running"] is False
    assert payload["collector"]["status"] == "stopped"
    assert payload["collector"]["pid"] is None


def test_collector_stopped_dead_pid(tmp_path, monkeypatch):
    cov = _write_dir(tmp_path, [_window("window_a", "completed")])
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr(coverage, "_pid_alive", lambda pid: False)
    payload = coverage.build_payload(cov, pid_file, NOW)
    assert payload["collector"]["running"] is False
    assert payload["collector"]["status"] == "stopped"
    assert payload["collector"]["pid"] == 4242


def test_collector_running_fresh(tmp_path, monkeypatch):
    cov = _write_dir(tmp_path, [_window("window_a", "collecting", window_end=FUTURE)])
    # Make the heartbeat fresh: mtime = now.
    os.utime(cov / "window_a.json", (NOW.timestamp(), NOW.timestamp()))
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr(coverage, "_pid_alive", lambda pid: True)
    payload = coverage.build_payload(cov, pid_file, NOW)
    assert payload["collector"]["running"] is True
    assert payload["collector"]["status"] == "running"
    assert payload["collector"]["stale"] is False


def test_collector_stale_quiet_heartbeat(tmp_path, monkeypatch):
    cov = _write_dir(tmp_path, [_window("window_a", "collecting", window_end=FUTURE)])
    # Heartbeat went quiet 20 min ago (relative to the fixed test clock)
    # while the window is still active.
    old = NOW.timestamp() - 20 * 60
    os.utime(cov / "window_a.json", (old, old))
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr(coverage, "_pid_alive", lambda pid: True)
    payload = coverage.build_payload(cov, pid_file, NOW)
    assert payload["collector"]["running"] is True
    assert payload["collector"]["status"] == "stale"
    assert payload["collector"]["stale"] is True


def test_collector_stale_detected_during_toronto_evening(tmp_path, monkeypatch):
    """Regression (2026-09-09 playtest): window_end stamps are Toronto wall
    clock but were parsed as UTC, so a live 19:00-24:00 Toronto window read
    as ending 19:00 UTC = *earlier* than the Toronto evening it was running
    in — the hung-collector check silently never applied during exactly the
    hours that matter. NOW is 20:00 Toronto (00:00 UTC next day); the window
    ends 24:00 Toronto (04:00 UTC), genuinely in the future. The heartbeat
    is quiet >15 min, so the window must read stale."""
    end_tor_evening = "2026-09-10 00:00:00"  # midnight Toronto wall clock
    now_utc = datetime(2026, 9, 10, 0, 0, 0, tzinfo=UTC)  # 20:00 Toronto
    cov = _write_dir(
        tmp_path, [_window("window_a", "collecting", window_end=end_tor_evening)]
    )
    old = now_utc.timestamp() - 20 * 60
    os.utime(cov / "window_a.json", (old, old))
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr(coverage, "_pid_alive", lambda pid: True)
    payload = coverage.build_payload(cov, pid_file, now_utc)
    assert payload["collector"]["stale"] is True
    assert payload["collector"]["status"] == "stale"


def test_collector_naive_now_does_not_crash_and_matches_aware(tmp_path, monkeypatch):
    """Regression (2026-09-02): ``build_payload`` accepts a ``now`` datetime
    from both callers and tests. When a NAIVE clock was passed, the stale-
    check compared it against the tz-aware ``window_end`` stamp and raised
    ``TypeError: can't compare offset-naive and offset-aware datetimes`` --
    which failed 12 coverage tests. The naive clock must be normalized to UTC
    and the verdict must be identical to passing the tz-aware equivalent.
    """
    cov = _write_dir(tmp_path, [_window("window_a", "collecting", window_end=FUTURE)])
    old = NOW.timestamp() - 20 * 60
    os.utime(cov / "window_a.json", (old, old))
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr(coverage, "_pid_alive", lambda pid: True)

    naive = datetime(2026, 8, 30, 12, 0, 0)
    aware = naive.replace(tzinfo=UTC)
    p_naive = coverage.build_payload(cov, pid_file, naive)  # must not raise
    p_aware = coverage.build_payload(cov, pid_file, aware)

    assert p_naive["collector"]["status"] == "stale"
    assert p_naive["collector"]["stale"] is True
    assert p_naive["collector"] == p_aware["collector"]


def test_collector_naive_now_default_realtime_no_crash(tmp_path, monkeypatch):
    """``now=None`` falls back to the real clock; it must not crash and must
    return a well-formed payload."""
    cov = _write_dir(tmp_path, [_window("window_a", "collecting", window_end=FUTURE)])
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr(coverage, "_pid_alive", lambda pid: True)
    payload = coverage.build_payload(cov, pid_file, None)
    assert "status" in payload["collector"]
    assert "running" in payload["collector"]


def test_collector_between_windows_never_stale(tmp_path, monkeypatch):
    """A window that already ended must not read as stale: the collector is
    meant to sleep between windows and stops rewriting coverage files.

    Regression guard for the TZ fix: the end stamp is genuinely past when
    parsed in America/Toronto (07:00 TO = 11:00 UTC < NOW 12:00 UTC) even
    though its raw string looks ambiguous. Under the old UTC-as-stamp
    misreading this fixture read as future and masked the bug.
    """
    cov = _write_dir(
        tmp_path, [_window("window_a", "completed", window_end=PAST_TOR_END)]
    )
    old = NOW.timestamp() - 60 * 60
    os.utime(cov / "window_a.json", (old, old))
    pid_file = tmp_path / "collector.pid"
    pid_file.write_text("4242\n999999999\n", encoding="utf-8")
    monkeypatch.setattr(coverage, "_pid_alive", lambda pid: True)
    payload = coverage.build_payload(cov, pid_file, NOW)
    assert payload["collector"]["status"] == "running"
    assert payload["collector"]["stale"] is False


# ---------------------------------------------------------------------------
# demo-data flag (seed_demo_data.py integration)
# ---------------------------------------------------------------------------


def test_build_payload_demo_sentinel_file(tmp_path):
    """The DEMO sentinel file makes the payload report demo even when the
    ledger itself carries no demo markers."""
    cov = _write_dir(tmp_path, [_window("window_a", "completed")])
    (tmp_path / "DEMO").write_text("MIWAY_DEMO_DATA\n", encoding="utf-8")
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert payload["demo"] is True


def test_build_payload_demo_window_marker(tmp_path):
    """A window JSON stamped demo:true flags the payload without the sentinel."""
    cov = _write_dir(tmp_path, [_window("window_demo_a", "completed")])
    raw = json.loads((cov / "window_demo_a.json").read_text(encoding="utf-8"))
    raw["demo"] = True
    (cov / "window_demo_a.json").write_text(json.dumps(raw), encoding="utf-8")
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert payload["demo"] is True
    assert payload["recent"][0]["demo"] is True


def test_build_payload_real_collection_not_demo(tmp_path):
    """No sentinel, no markers: a real campaign reads demo:false."""
    cov = _write_dir(tmp_path, [_window("window_a", "completed")])
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert payload["demo"] is False
    assert payload["recent"][0]["demo"] is False


def test_build_payload_demo_flag_with_empty_ledger(tmp_path):
    """A demo install whose JSONs fail to parse still reports demo honestly
    via the sentinel (the trust view must never look like a real campaign)."""
    cov = tmp_path / "coverage"
    cov.mkdir()
    (cov / "window_bad.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "DEMO").write_text("MIWAY_DEMO_DATA\n", encoding="utf-8")
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert payload["demo"] is True


# ---------------------------------------------------------------------------
# Ledger audit: CSV rows must never understate their window JSON
# (the duplicate-collector overwrite bug, live on Aug 20/21/23, Sep 1/2/3)
# ---------------------------------------------------------------------------


def test_audit_finds_underreported_row(tmp_path):
    """A CSV row with fewer polls than its JSON is flagged for repair."""
    import json
    from scripts.audit_coverage_ledger import audit

    cov = tmp_path / "coverage"
    cov.mkdir()
    (cov / "window_20260901_2000.json").write_text(
        json.dumps(
            {
                "date": "2026-09-01",
                "window_start": "2026-09-01 20:00:02",
                "window_end": "2026-09-02 00:00:00",
                "status": "completed",
                "polls_attempted": 440,
                "observations": 1633961,
            }
        )
    )
    (cov / "collection_windows.csv").write_text(
        "date,window_start,window_end,scheduled,status,polls_attempted,"
        "polls_succeeded,polls_failed,first_poll_at,last_poll_at,"
        "observations,vp_snapshots,alerts,longest_gap_min,polls_timeout\n"
        "2026-09-01,2026-09-01 20:00:02,2026-09-02 00:00:00,19:00-24:00,"
        "interrupted,7,7,0,x,y,35259,7,0,0,0\n",
        encoding="utf-8",
    )
    problems = audit(cov, cov / "collection_windows.csv")
    assert len(problems) == 1
    stats, row = problems[0]
    assert stats["polls_attempted"] == 440
    assert row["polls_attempted"] == "7"


def test_audit_repair_rewrites_row_from_json_truth(tmp_path):
    """--repair replaces the stub row's stats with the JSON's complete record."""
    import json
    from scripts.audit_coverage_ledger import repair

    cov = tmp_path / "coverage"
    cov.mkdir()
    (cov / "window_20260901_2000.json").write_text(
        json.dumps(
            {
                "date": "2026-09-01",
                "window_start": "2026-09-01 20:00:02",
                "window_end": "2026-09-02 00:00:00",
                "status": "completed",
                "polls_attempted": 440,
                "polls_succeeded": 440,
                "polls_failed": 0,
                "first_poll_at": "2026-09-01 20:00:22",
                "last_poll_at": "2026-09-01 23:59:30",
                "observations": 1633961,
                "vp_snapshots": 440,
                "alerts": 76,
                "longest_gap_min": 1.4,
                "polls_timeout": 0,
            }
        )
    )
    (cov / "collection_windows.csv").write_text(
        "date,window_start,window_end,scheduled,status,polls_attempted,"
        "polls_succeeded,polls_failed,first_poll_at,last_poll_at,"
        "observations,vp_snapshots,alerts,longest_gap_min,polls_timeout\n"
        "2026-09-01,2026-09-01 20:00:02,2026-09-02 00:00:00,19:00-24:00,"
        "interrupted,7,7,0,x,y,35259,7,0,0,0\n",
        encoding="utf-8",
    )
    n = repair(cov, cov / "collection_windows.csv")
    assert n == 1
    rows = (cov / "collection_windows.csv").read_text().strip().splitlines()
    assert len(rows) == 2  # header + the repaired row, position kept
    assert "440" in rows[1] and "completed" in rows[1]
    assert "1633961" in rows[1]


def test_audit_repair_downgrades_stale_collecting_status(tmp_path):
    """A JSON frozen mid-window by a dead process repairs to 'interrupted'."""
    import json
    from scripts.audit_coverage_ledger import repair

    cov = tmp_path / "coverage"
    cov.mkdir()
    # window_end far in the past relative to now
    (cov / "window_20260801_0600.json").write_text(
        json.dumps(
            {
                "date": "2026-08-01",
                "window_start": "2026-08-01 06:00:00",
                "window_end": "2026-08-01 09:00:00",
                "status": "collecting",
                "polls_attempted": 38,
                "observations": 246538,
            }
        )
    )
    (cov / "collection_windows.csv").write_text(
        "date,window_start,window_end,scheduled,status,polls_attempted,"
        "polls_succeeded,polls_failed,first_poll_at,last_poll_at,"
        "observations,vp_snapshots,alerts,longest_gap_min,polls_timeout\n"
        "2026-08-01,2026-08-01 06:00:00,2026-08-01 09:00:00,06:00-09:00,"
        "interrupted,2,2,0,x,y,100,2,0,0,0\n",
        encoding="utf-8",
    )
    repair(cov, cov / "collection_windows.csv")
    repaired = (cov / "collection_windows.csv").read_text().strip().splitlines()[1]
    assert "interrupted" in repaired and "38" in repaired


def test_audit_passes_when_ledger_is_consistent(tmp_path):
    """Matching rows produce no findings and repair is a no-op."""
    import json
    from scripts.audit_coverage_ledger import audit, repair

    cov = tmp_path / "coverage"
    cov.mkdir()
    (cov / "window_20260901_2000.json").write_text(
        json.dumps(
            {
                "date": "2026-09-01",
                "window_start": "2026-09-01 20:00:02",
                "status": "completed",
                "polls_attempted": 440,
                "observations": 1633961,
            }
        )
    )
    (cov / "collection_windows.csv").write_text(
        "date,window_start,window_end,scheduled,status,polls_attempted,"
        "polls_succeeded,polls_failed,first_poll_at,last_poll_at,"
        "observations,vp_snapshots,alerts,longest_gap_min,polls_timeout\n"
        "2026-09-01,2026-09-01 20:00:02,2026-09-02 00:00:00,19:00-24:00,"
        "completed,440,440,0,x,y,1633961,440,76,1.4,0\n",
        encoding="utf-8",
    )
    assert audit(cov, cov / "collection_windows.csv") == []
    assert repair(cov, cov / "collection_windows.csv") == 0


# ---------------------------------------------------------------------------
# Data vintages: headline numbers must carry their data's age
# ---------------------------------------------------------------------------


def test_vintages_reports_existing_file(tmp_path, monkeypatch):
    """A present file reports its mtime and age; no lag without a feeds_from."""
    from app import data_vintage

    f = tmp_path / "obs_lateness.csv"
    f.write_text("route_short_name\n5\n")
    monkeypatch.setattr(data_vintage.config, "DATA_DIR", tmp_path)
    v = data_vintage.vintages()
    lat = v["lateness"]
    assert lat["exists"] is True
    assert lat["mtime"] is not None
    assert lat["age_minutes"] is not None and lat["age_minutes"] < 5
    assert "feeds_from" not in lat  # raw source has no upstream to lag


def test_vintages_reports_missing_file(tmp_path, monkeypatch):
    """A missing output is reported as absent, not fabricated."""
    from app import data_vintage

    monkeypatch.setattr(data_vintage.config, "DATA_DIR", tmp_path)
    v = data_vintage.vintages()
    assert v["occupancy"]["exists"] is False
    assert v["occupancy"]["mtime"] is None
    assert v["occupancy"]["age_minutes"] is None


def test_vintages_flags_stale_analysis_output(tmp_path, monkeypatch):
    """An output older than its input reports the lag (the Sep 2 signature)."""
    import os
    from app import data_vintage

    raw = tmp_path / "obs_lateness.csv"
    out = tmp_path / "occupancy_stats.csv"
    raw.write_text("x\n")
    out.write_text("x\n")
    # Make the output look 2 h older than the input.
    old = __import__("time").time() - 2 * 3600
    os.utime(out, (old, old))
    monkeypatch.setattr(data_vintage.config, "DATA_DIR", tmp_path)
    v = data_vintage.vintages()
    occ = v["occupancy"]
    assert occ["feeds_from"] == "obs_lateness.csv"
    assert occ["input_lag_minutes"] is not None
    assert occ["input_lag_minutes"] >= 110


# ---------------------------------------------------------------------------
# Audit-repair surfacing: .last_audit.json flows into /api/coverage
# ---------------------------------------------------------------------------


def test_last_audit_reports_repair_count(tmp_path):
    """A mass-repair (like Aug 21's 4-row clobbering) is visible in the payload."""
    import json

    cov = tmp_path / "coverage"
    cov.mkdir()
    (cov / ".last_audit.json").write_text(
        json.dumps(
            {
                "checked_at": "2026-09-03 14:00:00",
                "underreported_found": 4,
                "rows_repaired": 4,
            }
        )
    )
    state = coverage._last_audit(cov)
    assert state == {
        "checked_at": "2026-09-03 14:00:00",
        "rows_repaired": 4,
        "underreported_found": 4,
    }


def test_last_audit_missing_or_corrupt_is_none(tmp_path):
    """No state file (or a broken one) means no audit line, never a crash."""
    cov = tmp_path / "coverage"
    cov.mkdir()
    assert coverage._last_audit(cov) is None
    (cov / ".last_audit.json").write_text("{not json")
    assert coverage._last_audit(cov) is None


def test_build_payload_carries_last_audit(tmp_path):
    """build_payload passes the audit state through untouched."""
    import json

    cov = tmp_path / "coverage"
    cov.mkdir()
    (cov / ".last_audit.json").write_text(
        json.dumps({"checked_at": "2026-09-03 14:00:00", "rows_repaired": 7})
    )
    payload = coverage.build_payload(cov, tmp_path / "collector.pid", NOW)
    assert payload["last_audit"]["rows_repaired"] == 7
    assert payload["last_audit"]["underreported_found"] == 0


def test_audit_main_records_state(tmp_path, capsys, monkeypatch):
    """A main() run writes .last_audit.json even when the ledger is clean."""
    import json
    import sys

    from scripts import audit_coverage_ledger

    cov = tmp_path / "coverage"
    cov.mkdir()
    (cov / "collection_windows.csv").write_text("window_start\n")
    monkeypatch.setattr(sys, "argv", ["audit_coverage_ledger.py"])
    monkeypatch.setattr(audit_coverage_ledger.config, "DATA_DIR", tmp_path)
    assert audit_coverage_ledger.main() == 0
    state = json.loads((cov / ".last_audit.json").read_text())
    assert state["rows_repaired"] == 0
    assert state["checked_at"]
