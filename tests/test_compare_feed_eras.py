"""Regression tests for scripts/compare_feed_eras.py (feed-era comparison).

The script compares two GTFS feeds (e.g. 2017 vs 2026). These tests build two
tiny synthetic feeds and assert the route-aligned delta and the lost-service
stop map are computed correctly, and that a retired route is honestly reported
as having no *current* measured boardings.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import scripts.compare_feed_eras as cfe

_EARLY = "20170130"
_LATE = "20260910"


def _write_feed(
    dir: Path,
    routes: list[tuple[str, str]],
    trips: list[tuple[str, str, str]],
    stop_ids: list[str],
    stop_times: list[tuple[str, str, str]],
) -> None:
    """Minimal GTFS: routes, trips, calendar_dates, stop_times, stops.

    ``trips`` = (trip_id, route_id, service_id); ``stop_times`` =
    (trip_id, stop_id, departure_time).
    """
    dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(routes, columns=["route_id", "route_short_name"]).to_csv(
        dir / "routes.txt", index=False
    )
    pd.DataFrame(trips, columns=["trip_id", "route_id", "service_id"]).to_csv(
        dir / "trips.txt", index=False
    )
    # One weekday service active on a single date -> the picker chooses it.
    pd.DataFrame(
        [("WD", _EARLY, 1), ("WD", _LATE, 1)],
        columns=["service_id", "date", "exception_type"],
    ).to_csv(dir / "calendar_dates.txt", index=False)
    pd.DataFrame(stop_times, columns=["trip_id", "stop_id", "departure_time"]).to_csv(
        dir / "stop_times.txt", index=False
    )
    pd.DataFrame({"stop_id": stop_ids}).to_csv(dir / "stops.txt", index=False)


@pytest.fixture
def two_feeds(tmp_path: Path) -> tuple[Path, Path]:
    """Old feed routes 1,2 sharing stops A,B; route 2 also serves C.\n\n    New feed drops route 2 (and its stop C), keeps route 1, adds route 3.
    So: route 2 is culled, stop C loses service, route 3 is added.
    """
    old = tmp_path / "old"
    new = tmp_path / "new"
    _write_feed(
        old,
        routes=[("r1", "1"), ("r2", "2")],
        trips=[("t1", "r1", "WD"), ("t2", "r2", "WD"), ("t3", "r2", "WD")],
        stop_ids=["A", "B", "C"],
        stop_times=[
            ("t1", "A", "08:00:00"),
            ("t1", "B", "08:30:00"),
            ("t2", "A", "08:00:00"),
            ("t2", "C", "08:20:00"),
            ("t2", "B", "08:40:00"),
            ("t3", "A", "09:00:00"),
            ("t3", "C", "09:20:00"),
            ("t3", "B", "09:40:00"),
        ],
    )
    _write_feed(
        new,
        routes=[("r1", "1"), ("r3", "3")],
        trips=[("n1", "r1", "WD"), ("n2", "r3", "WD")],
        stop_ids=["A", "B", "D"],
        stop_times=[
            ("n1", "A", "08:00:00"),
            ("n1", "B", "08:30:00"),
            ("n2", "A", "08:00:00"),
            ("n2", "D", "08:15:00"),
            ("n2", "B", "08:45:00"),
        ],
    )
    return old, new


def test_route_aligned_delta(two_feeds):
    old, new = two_feeds
    per_old, _, _ = cfe._route_service_hours(old, _EARLY)
    per_new, _, _ = cfe._route_service_hours(new, _LATE)
    # Common route 1 survives; route 2 culled; route 3 added.
    assert set(per_old["route_short_name"]) == {"1", "2"}
    assert set(per_new["route_short_name"]) == {"1", "3"}


def test_culled_and_added_routes(two_feeds, capsys):
    old, new = two_feeds
    cfe.main(
        [
            "--old",
            str(old),
            "--new",
            str(new),
            "--pinned-old",
            _EARLY,
            "--pinned-new",
            _LATE,
            "--boarding-routes",  # values below are not exercised; avoid real file
            str(Path(new).parent / "nope.csv"),
        ]
    )
    out = capsys.readouterr().out
    assert "Culled routes (1): 2" in out
    assert "Added routes (1): 3" in out
    assert "Stops losing weekday service: 1" in out  # stop C


def test_culled_stops_csv(two_feeds, tmp_path, capsys):
    old, new = two_feeds
    csv = tmp_path / "culled.csv"
    cfe.main(
        [
            "--old",
            str(old),
            "--new",
            str(new),
            "--pinned-old",
            _EARLY,
            "--pinned-new",
            _LATE,
            "--csv",
            str(csv),
        ]
    )
    df = pd.read_csv(csv, dtype=str)
    assert df["stop_id"].tolist() == ["C"]


def test_retired_route_has_no_current_boardings(two_feeds, capsys, tmp_path):
    """A culled route must be reported as lacking *measured* boardings — the
    collector only observes routes that still run, so it cannot judge a route
    retired before collection. This is the honest gap, not a fake zero."""
    old, new = two_feeds
    routes_csv = tmp_path / "boardings_routes.csv"
    # Only the surviving route 1 has measured boardings in the new era.
    pd.DataFrame(
        {
            "route_short_name": ["1", "3"],
            "period": ["all_day", "all_day"],
            "boardings_lower_pax": [500.0, 300.0],
        }
    ).to_csv(routes_csv, index=False)
    cfe.main(
        [
            "--old",
            str(old),
            "--new",
            str(new),
            "--pinned-old",
            _EARLY,
            "--pinned-new",
            _LATE,
            "--boarding-routes",
            str(routes_csv),
        ]
    )
    out = capsys.readouterr().out
    # 0/1 culled routes have a measured boarding figure; surviving median > 0.
    assert "culled routes with 2026 measured boardings: 0/1" in out
    assert "surviving-route median daily boardings: 500 pax" in out


def test_missing_pin_warns_loudly(two_feeds, capsys):
    """A pin absent from the feed's calendar must scream on stderr: the
    unpicked heuristic once quoted holiday-adjacent service (overstating
    stop-visits ~50%), so silent empty-service runs are the failure mode
    this guard exists to prevent."""
    old, new = two_feeds
    cfe.main(
        [
            "--old",
            str(old),
            "--new",
            str(new),
            "--pinned-old",
            _EARLY,
            "--pinned-new",
            "20990101",  # not in the new feed's calendar
        ]
    )
    err = capsys.readouterr().err
    assert "WARNING: new pin 20990101 is NOT in" in err
    assert "EMPTY service set" in err
    assert "--pinned-new <YYYYMMDD>" in err
    # The valid pin must NOT warn.
    assert "WARNING: old pin" not in err


def test_default_pins_are_the_frozen_school_session_dates(two_feeds):
    """The defaults must be the snapshot's pinned dates, so a bare re-run is
    byte-comparable with docs/findings/feed-era-2017-vs-2026.md."""
    assert cfe.DEFAULT_PINNED_OLD == "20170308"
    assert cfe.DEFAULT_PINNED_NEW == "20261006"
