"""Tests for ``scripts.demo_stats`` feed scoping (2026-10-02 instrument drift).

The recursive ``obs_lateness*.csv`` glob swept the TTC feed's file into the
MiWay-basis README floor (8.38M union vs the resume gate's 6.66M). The
contract is per-feed: ``unique_departures`` = MiWay (root live + root
sync-conflict + archive/), ``unique_departures_ttc`` = ttc/ only.
"""

from __future__ import annotations

from scripts import demo_stats as ds

HDR = "route_short_name,stop_id,dep_time_min,lateness_minutes,horizon_minutes,date\n"


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HDR + "".join(rows), encoding="utf-8")


def _home(tmp_path):
    # MiWay live: 2 unique tuples
    _write(
        tmp_path / "obs_lateness.csv",
        [
            "10,2467,1198.0,1.47,1.92,2026-10-01\n",
            "10,2467,1199.0,0.50,1.92,2026-10-01\n",
        ],
    )
    # root sync-conflict copy: 1 new tuple + 1 duplicate of live (in scope!)
    _write(
        tmp_path / "obs_lateness.sync-conflict-20260925-000000-ABC.csv",
        [
            "66,9999,300.0,2.00,3.00,2026-09-25\n",
            "10,2467,1198.0,1.47,1.92,2026-10-01\n",
        ],
    )
    # pre-changeover archive: duplicate-only (contributes 0)
    _write(
        tmp_path
        / "archive"
        / "pre_changeover"
        / "split"
        / "obs_lateness.pre-20260907.csv",
        ["10,2467,1198.0,1.47,1.92,2026-10-01\n"],
    )
    # TTC feed: 3 unique tuples, disjoint from MiWay
    _write(
        tmp_path / "ttc" / "obs_lateness.csv",
        [
            "504,1001,60.0,0.10,1.00,2026-10-01\n",
            "504,1001,61.0,0.20,1.00,2026-10-01\n",
            "506,1002,62.0,0.30,1.00,2026-10-01\n",
        ],
    )
    return tmp_path


def test_miway_counter_excludes_ttc(tmp_path):
    home = _home(tmp_path)
    # live 2 + conflict-only 1 (archive duplicate adds 0, TTC excluded)
    assert ds.unique_departures(home) == 3


def test_ttc_counter_only_counts_ttc(tmp_path):
    home = _home(tmp_path)
    assert ds.unique_departures_ttc(home) == 3


def test_feeds_are_disjoint_and_sum_to_union(tmp_path):
    home = _home(tmp_path)
    total = ds.unique_departures(home) + ds.unique_departures_ttc(home)
    assert total == 6  # no key shared between the two feeds in the fixture
