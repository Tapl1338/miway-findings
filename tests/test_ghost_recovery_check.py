"""Unit tests for ``scripts/ghost_recovery_check.py`` (block-continuity class).

Pure helpers only: per-trip classification windows, consecutive-ghost
episode grouping, recovery classification, service-hours math. No network.
Template cases mirror the 2026-08-26 live findings: the route-51 block that
RECOVERED and the route-66 block that stayed PERSISTENT.
"""

import pandas as pd
import pytest
from scripts.ghost_recovery_check import (
    build_episodes,
    classify_trips,
    day_input_state,
)
from scripts.ghost_trips import _local_epoch

DATE = "20260826"


def _scheduled(rows):
    return pd.DataFrame(
        rows, columns=["trip_id", "route_short_name", "start_min", "duration_min"]
    )


def _epoch(minute: float) -> float:
    return _local_epoch(DATE, minute)


def _obs(trip_minutes):
    """[(trip_id, start_min)] -> observations broadcast right at each start."""
    return [(tid, _epoch(m)) for tid, m in trip_minutes]


def _polls(minutes):
    return [_epoch(m) for m in minutes]


def test_classify_observed_ghost_uncovered():
    sched = _scheduled(
        [
            ("T1", "51", 14 * 60 + 20, 71),  # broadcast at start -> observed
            ("T2", "51", 15 * 60 + 40, 60),  # never broadcast, polls cover -> ghost
            ("T3", "51", 4 * 60 + 30, 60),  # polls start 09:00 -> uncovered
        ]
    )
    block_map = {"T1": ("B51", "51"), "T2": ("B51", "51"), "T3": ("B51", "51")}
    obs = _obs([("T1", 14 * 60 + 20)])
    polls = _polls([9 * 60 + 5, 14 * 60 + 20, 15 * 60 + 40])
    v = classify_trips(DATE, sched, obs, polls, block_map)
    assert v["T1"][0] == "observed"
    assert v["T2"][0] == "ghost"
    assert v["T3"][0] == "uncovered"


def test_episode_recovered_like_route51_template():
    # 51-template: single ghost, then the next trip runs -> RECOVERED
    trips = [
        (14 * 60 + 20, "T1", "ghost", 71, "51"),
        (15 * 60 + 42, "T2", "observed", 60, "51"),
    ]
    verdicts = {t[1]: (t[2], t[0], t[3], "B51", t[4]) for t in trips}
    eps = build_episodes(verdicts)
    assert len(eps) == 1
    assert eps[0]["ghosted_trips"] == 1
    assert eps[0]["recovery_status"] == "RECOVERED"
    assert eps[0]["recovery_trip"] == "T2"
    assert eps[0]["service_hours"] == pytest.approx(round(71 / 60, 1), abs=0.01)


def test_episode_persistent_like_route66_template():
    # 66-template: consecutive ghosts to the end of the block -> PERSISTENT
    trips = [
        (12 * 60 + 48, "G1", "ghost", 55, "66"),
        (13 * 60 + 30, "G2", "ghost", 55, "66"),
        (14 * 60 + 18, "G3", "ghost", 55, "66"),
    ]
    verdicts = {t[1]: (t[2], t[0], t[3], "B66", t[4]) for t in trips}
    eps = build_episodes(verdicts)
    assert len(eps) == 1
    assert eps[0]["ghosted_trips"] == 3
    assert eps[0]["recovery_status"] == "PERSISTENT"
    assert eps[0]["service_hours"] == pytest.approx(round(3 * 55 / 60, 1), abs=0.01)


def test_ghost_then_later_ghost_gap_is_persistent():
    # observed trip breaks the run; later ghosts still mean the block is dark
    trips = [
        (10 * 60, "G1", "ghost", 40, "66"),
        (11 * 60, "O1", "observed", 40, "66"),
        (12 * 60, "G2", "ghost", 40, "66"),
        (13 * 60, "G3", "ghost", 40, "66"),
    ]
    verdicts = {t[1]: (t[2], t[0], t[3], "B", t[4]) for t in trips}
    eps = build_episodes(verdicts)
    assert len(eps) == 2
    assert eps[0]["recovery_status"] == "RECOVERED"  # G1 recovered by O1
    assert eps[1]["recovery_status"] == "PERSISTENT"  # G2/G3 never recover
    assert eps[1]["ghosted_trips"] == 2


def test_uncovered_breaks_run():
    # an uncovered trip between ghosts splits the run (not provably consecutive)
    trips = [
        (10 * 60, "G1", "ghost", 40, "66"),
        (11 * 60, "U1", "uncovered", 40, "66"),
        (12 * 60, "G2", "ghost", 40, "66"),
    ]
    verdicts = {t[1]: (t[2], t[0], t[3], "B", t[4]) for t in trips}
    eps = build_episodes(verdicts)
    assert len(eps) == 2
    assert all(e["ghosted_trips"] == 1 for e in eps)


def test_later_all_uncovered_is_undetermined():
    trips = [
        (15 * 60, "G1", "ghost", 40, "7"),
        (16 * 60, "U1", "uncovered", 40, "7"),
        (17 * 60, "U2", "uncovered", 40, "7"),
    ]
    verdicts = {t[1]: (t[2], t[0], t[3], "B", t[4]) for t in trips}
    eps = build_episodes(verdicts)
    assert len(eps) == 1
    assert eps[0]["recovery_status"] == "UNDETERMINED"


def test_single_ghost_only_block_is_persistent():
    trips = [(9 * 60, "G1", "ghost", 45, "1")]
    verdicts = {t[1]: (t[2], t[0], t[3], "B", t[4]) for t in trips}
    eps = build_episodes(verdicts)
    assert len(eps) == 1
    assert eps[0]["recovery_status"] == "PERSISTENT"


def test_day_input_state_partial_beyond_coverage():
    # a scheduled trip whose verifiable window extends past the last poll
    # makes the day PARTIAL (alpha-6 reproducibility fix)
    sched = _scheduled([("T1", "51", 14 * 60 + 20, 71), ("T2", "51", 23 * 60 + 30, 60)])
    block_map = {"T1": ("B1", "51"), "T2": ("B1", "51")}
    polls = [_epoch(9 * 60 + 5), _epoch(16 * 60 + 26)]  # coverage ends 16:26 local
    st = day_input_state(DATE, sched, block_map, polls, last_win_mtime=0.0, now=1e12)
    assert st["day_status"] == "PARTIAL"
    assert st["beyond"] == 1  # T2 (23:30) is beyond coverage
    assert st["last_local"] == "16:26"


def test_day_input_state_complete():
    sched = _scheduled([("T1", "51", 14 * 60 + 20, 71)])
    block_map = {"T1": ("B1", "51")}
    polls = [_epoch(9 * 60 + 5), _epoch(16 * 60 + 26)]  # past T1's window end (15:36)
    st = day_input_state(DATE, sched, block_map, polls, last_win_mtime=0.0, now=1e12)
    assert st["day_status"] == "COMPLETE"
    assert st["beyond"] == 0


def test_day_input_state_partial_while_writing():
    # newest window file touched within 10 min -> still being appended
    sched = _scheduled([("T1", "51", 14 * 60 + 20, 71)])
    block_map = {"T1": ("B1", "51")}
    polls = [_epoch(14 * 60 + 20)]
    now = 1e12
    st = day_input_state(
        DATE, sched, block_map, polls, last_win_mtime=now - 60, now=now
    )
    assert st["day_status"] == "PARTIAL"


def test_receipt_stamps_input_state(tmp_path, monkeypatch):
    import scripts.ghost_recovery_check as grc

    monkeypatch.setattr(grc, "RUNS_DIR", tmp_path)
    state = {
        "first_poll": 0.0,
        "last_poll": 0.0,
        "first_local": "09:09",
        "last_local": "16:26",
        "n_polls": 1328,
        "beyond": 11,
        "day_status": "PARTIAL",
        "cov_end_local": "16:26",
        "frozen_input": "0123456789abcdef",
    }
    episode = {
        "block": "B1",
        "routes": "51",
        "episode_start": 14 * 60 + 20,
        "episode_end": 15 * 60 + 31,
        "ghosted_trips": 1,
        "service_hours": 1.2,
        "recovery_status": "UNDETERMINED",
        "recovery_trip": "",
        "recovery_departure": None,
        "trip_ids": "T1",
    }
    csv_path, md_path = grc.write_receipts("20260826", [episode], state)
    md = md_path.read_text(encoding="utf-8")
    assert "Day status: **PARTIAL**" in md
    assert "16:26" in md
    assert "11 active-service trips beyond coverage" in md
    assert "Frozen input: `0123456789abcdef`" in md
    csv_txt = csv_path.read_text(encoding="utf-8")
    assert "day_status" in csv_txt
    assert "PARTIAL" in csv_txt  # the row carries the day status
    assert "frozen_input" in csv_txt
    assert "0123456789abcdef" in csv_txt  # the row carries the fingerprint


def test_frozen_input_fingerprint_deterministic_and_order_independent(tmp_path):
    from scripts.ghost_recovery_check import frozen_input_fingerprint

    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("alpha", encoding="utf-8")
    b.write_text("bravo", encoding="utf-8")

    h1 = frozen_input_fingerprint([a, b])
    h2 = frozen_input_fingerprint([b, a])  # same files, reversed order
    assert h1 == h2
    assert len(h1) == 64  # full sha256 hex


def test_frozen_input_fingerprint_sensitive_to_bytes(tmp_path):
    from scripts.ghost_recovery_check import frozen_input_fingerprint

    f = tmp_path / "f.json"
    f.write_text('{"a": 1}', encoding="utf-8")
    h1 = frozen_input_fingerprint([f])

    f.write_text('{"a": 2}', encoding="utf-8")  # one byte changed
    h2 = frozen_input_fingerprint([f])
    assert h1 != h2


def test_frozen_input_fingerprint_sensitive_to_file_set(tmp_path):
    from scripts.ghost_recovery_check import frozen_input_fingerprint

    a = tmp_path / "a.json"
    a.write_text("x", encoding="utf-8")
    h1 = frozen_input_fingerprint([a])

    b = tmp_path / "b.json"  # an added window changes the input set
    b.write_text("y", encoding="utf-8")
    h2 = frozen_input_fingerprint([a, b])
    assert h1 != h2


def test_day_after_rolls_calendar_month():
    from scripts.ghost_recovery_check import _day_after

    assert _day_after("20260826") == "20260827"
    assert _day_after("20260831") == "20260901"
    assert _day_after("20261231") == "20270101"


def test_load_day_polls_reads_next_day_windows_bounded_by_horizon(tmp_path):
    """Midnight-rollover fix: a service day's closing polls live in the next
    calendar day's window files, and a still-live next-day window must not
    count toward this day (2026-08-27 coverage gap)."""
    import json
    import os

    from scripts.ghost_recovery_check import load_day_polls

    coll = tmp_path / "collections"
    coll.mkdir()
    sched = _scheduled([("T1", "51", 1643, 18)])  # last window ends ~03:46 + tail
    block_map = {"T1": ("B51", "51")}

    def write(name, polls):
        snap = {
            "polls": [
                {
                    "poll": i,
                    "fetched_at": float(ts),
                    "buses": [{"trip_id": "T1", "service_date": "20260826"}],
                }
                for i, ts in enumerate(polls)
            ]
        }
        p = coll / name
        p.write_text(json.dumps(snap), encoding="utf-8")
        return p

    d26 = write("vp_20260826_0900.json", [_epoch(13 * 60 + 20)])
    night = write("vp_20260827_0001.json", [_epoch(1440 + 60), _epoch(1440 + 120)])
    live = write("vp_20260827_0600.json", [_epoch(1440 + 390)])  # 06:30, past horizon
    now = 1787850000.0
    os.utime(d26, (now, now))
    os.utime(night, (now + 10, now + 10))
    os.utime(live, (now + 20, now + 20))  # newest file, but contributes no poll

    wins, _snapshots, _obs, all_polls, last_mtime = load_day_polls(
        coll, "20260826", sched, block_map
    )

    assert sorted(w.name for w in wins) == [
        "vp_20260826_0900.json",
        "vp_20260827_0001.json",
        "vp_20260827_0600.json",
    ]
    assert _epoch(13 * 60 + 20) in all_polls
    assert _epoch(1440 + 60) in all_polls  # after-midnight polls of THIS day
    assert _epoch(1440 + 120) in all_polls
    assert _epoch(1440 + 390) not in all_polls  # next service day: not evidence
    assert (
        last_mtime == now + 10
    )  # the live 06:00 window never marks this day "writing"
