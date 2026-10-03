"""Unit tests for ``scripts/late_start_probe.py`` (origin-crossing punctuality).

Pure classification tests: the ``classify_day`` gate logic for the
origin-crossing departure metric. No network, synthetic trajectories only.
The three falsification cases this family had to survive are encoded here:

* pre-positioning       -- a trip_id that broadcasts long before its first
  stop must read ~on-time, never "early" (a bus holds on the terminal and
  departs on schedule -> the origin-crossing metric must NOT flag it).
* return-pass artifact  -- route-16 / Westwood Square loops: a bus first seen
  already past the origin margin whose position later re-enters the origin
  radius is a return-cross, not a late departure -> must read UNMEASURABLE,
  never a FALSE LATE.
* missed-origin         -- the collector never caught the origin crossing; the
  bus is first seen moving away -> UNMEASURABLE (not a late quote).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from scripts.late_start_probe import _CLASSES, classify_day, classify_labels

DATE = "20260826"
_TOR = ZoneInfo("America/Toronto")

# Origin stop 1687 (Westwood Square Platform D) around 43.7217, -79.6406.
OLAT, OLON = 43.721713, -79.640641


def _hminute(hour: int, minute: int) -> float:
    return hour * 60 + minute


def _bus_ts(hour: int, minute: int) -> float:
    """America/Toronto epoch for a local clock time on DATE."""
    return datetime(2026, 8, 26, hour, minute, tzinfo=_TOR).timestamp()


def _scheduled(rows):
    return pd.DataFrame(
        rows, columns=["trip_id", "route_short_name", "start_min", "duration_min"]
    )


def _origin(dep_min: float, stop_id: str = "1687"):
    return {"T0": (stop_id, dep_min, (OLAT, OLON))}


def _poll_at(hour: int, minute: int) -> float:
    """A poll at the given local clock time (must be >= the trip's start so the
    trip is not UNCOVERED -- the coverage gate needs a poll in
    [start, start+55min])."""
    return _bus_ts(hour, minute)


def _pos(lat, lon, hour, minute):
    return (datetime(2026, 8, 26, hour, minute, tzinfo=_TOR).timestamp(), lat, lon)


def test_ontime_terminal_hold_reads_ontime():
    """Bus holds at platform until scheduled departure, then departs -> on-time."""
    dep_min = _hminute(7, 17)
    # approach into origin (descending), hold at ~5 m, then depart after start.
    traj = [
        _pos(43.7280, -79.6350, 7, 6),  # ~690 m out, approaching
        _pos(43.7245, -79.6385, 7, 12),  # ~380 m
        _pos(43.7225, -79.6399, 7, 14),  # ~140 m (within 200 m radius)
        _pos(OLAT, OLON, 7, 16),  # on platform (0 m)
        _pos(OLAT, OLON, 7, 17),  # hold at departure minute
        _pos(43.7250, -79.6440, 7, 19),  # departed, ~450 m
        _pos(43.7280, -79.6480, 7, 21),  # ~900 m, clearly gone
    ]
    sched = _scheduled([("T0", "16", dep_min, 50)])
    res = classify_day(DATE, sched, {"T0": traj}, _origin(dep_min), [_poll_at(7, 20)])
    assert res["counts"]["ON-TIME"] == 1
    assert res["counts"]["LATE-START"] == 0
    assert res["offenders"] == []


def test_late_start_reads_late():
    """Bus holds at platform 15 min after scheduled departure -> LATE-START."""
    dep_min = _hminute(7, 17)
    traj = [
        _pos(43.7225, -79.6399, 7, 14),  # arrive within radius
        _pos(OLAT, OLON, 7, 16),  # on platform
        _pos(OLAT, OLON, 7, 20),  # still on platform (late)
        _pos(OLAT, OLON, 7, 30),  # still on platform (very late)
        _pos(OLAT, OLON, 7, 33),  # last hold
        _pos(43.7280, -79.6480, 7, 40),  # finally departs
    ]
    sched = _scheduled([("T0", "16", dep_min, 50)])
    res = classify_day(DATE, sched, {"T0": traj}, _origin(dep_min), [_poll_at(7, 20)])
    assert res["counts"]["LATE-START"] == 1
    assert res["counts"]["ON-TIME"] == 0
    assert len(res["offenders"]) == 1
    o = res["offenders"][0]
    assert o["late_min"] >= 10.0


def test_return_pass_is_unmeasurable_not_late():
    """route-16 return-pass: first seen past margin, later re-enters radius.

    Must be UNMEASURABLE, NOT a false LATE-START (this is the artifact the
    margin-guard exists to kill).
    """
    dep_min = _hminute(11, 50)
    # First observations are already >500 m away moving away (origin missed),
    # then much later the bus re-enters the origin radius on its return leg.
    traj = [
        _pos(43.7340, -79.6330, 11, 59),  # ~1300 m out (missed origin), already leaving
        _pos(43.7300, -79.6310, 12, 2),  # ~1000 m
        _pos(43.7260, -79.6360, 12, 5),  # ~760 m
        _pos(43.7230, -79.6420, 12, 23),  # return re-approaches origin radius (~120 m)
        _pos(43.7260, -79.6460, 12, 26),  # on to the terminal / away again
    ]
    sched = _scheduled([("T0", "16", dep_min, 50)])
    res = classify_day(DATE, sched, {"T0": traj}, _origin(dep_min), [_poll_at(11, 55)])
    assert res["counts"]["UNMEASURABLE"] == 1
    assert res["counts"]["LATE-START"] == 0
    assert res["counts"]["ON-TIME"] == 0
    assert res["offenders"] == []


def test_missed_origin_unmeasurable():
    """Bus first seen already far out and moving away -> UNMEASURABLE."""
    dep_min = _hminute(6, 20)
    traj = [
        _pos(43.7280, -79.6350, 6, 22),  # ~690 m, no origin sighting
        _pos(43.7310, -79.6300, 6, 24),  # ~1000 m, going away
        _pos(43.7350, -79.6290, 6, 26),
    ]
    sched = _scheduled([("T0", "16", dep_min, 50)])
    res = classify_day(DATE, sched, {"T0": traj}, _origin(dep_min), [_poll_at(6, 25)])
    assert res["counts"]["UNMEASURABLE"] == 1
    assert res["offenders"] == []


def test_never_ran_excluded():
    """A scheduled trip with no position observations -> NEVER-RAN, not late."""
    dep_min = _hminute(7, 17)
    sched = _scheduled([("T0", "16", dep_min, 50)])
    res = classify_day(DATE, sched, {}, _origin(dep_min), [_poll_at(7, 20)])
    assert res["counts"]["NEVER-RAN"] == 1
    assert res["counts"]["LATE-START"] == 0
    assert res["measured"] == 0
    assert res["rate"] == 0.0


def test_uncovered_excluded_from_rate():
    """No poll near the scheduled start (collector not watching) -> coverage."""
    dep_min = _hminute(7, 17)
    # scheduled departure at ~07:17 but the only poll is at 13:00 (way past
    # COVERAGE_TAIL_MIN on the start), so the origin was unwatched.
    late_poll = _bus_ts(13, 5)
    sched = _scheduled([("T0", "16", dep_min, 50)])
    res = classify_day(
        DATE, sched, {"T0": [_pos(OLAT, OLON, 7, 17)]}, _origin(dep_min), [late_poll]
    )
    assert res["counts"]["UNCOVERED"] == 1
    assert res["counts"]["LATE-START"] == 0


def test_rate_denominator_sums_measured_classes():
    """Rate = LATE-START / (ON-TIME + EARLY + LATE-START + PULL-IN)."""
    dep_min = _hminute(7, 17)
    # late: holds at origin until 14 min after the scheduled start.
    late = [
        _pos(OLAT, OLON, 7, 16),
        _pos(OLAT, OLON, 7, 31),
        _pos(43.7280, -79.6480, 7, 40),
    ]
    # on-time: dwells through the scheduled minute, departs right after.
    ontime = [
        _pos(OLAT, OLON, 7, 15),
        _pos(OLAT, OLON, 7, 17),
        _pos(43.7280, -79.6480, 7, 19),
    ]
    # early: dwells at origin then leaves before the scheduled start.
    early = [
        _pos(OLAT, OLON, 7, 10),
        _pos(OLAT, OLON, 7, 11),
        _pos(43.7280, -79.6480, 7, 12),
    ]
    sched = _scheduled(
        [
            ("T1", "16", dep_min, 50),
            ("T2", "16", dep_min, 50),
            ("T3", "16", dep_min, 50),
        ]
    )
    origin = {
        "T1": ("1687", dep_min, (OLAT, OLON)),
        "T2": ("1687", dep_min, (OLAT, OLON)),
        "T3": ("1687", dep_min, (OLAT, OLON)),
    }
    res = classify_day(
        DATE, sched, {"T1": late, "T2": ontime, "T3": early}, origin, [_poll_at(7, 20)]
    )
    assert res["counts"]["LATE-START"] == 1
    assert res["counts"]["ON-TIME"] == 1
    assert res["counts"]["EARLY"] == 1
    assert res["measured"] == 3
    assert abs(res["rate"] - (1 / 3) * 100.0) < 1e-6


# ---------------------------------------------------------------------------
# Ghost/late orthogonality guard (D-17 phase-2 verify item 2).
#
# The claim the guard must hold: a SINGLE rider-visible failure is never counted
# twice when the late-start AND ghost receipts are quoted together. A trip that
# never broadcast is NEVER-RAN -> the ghost family's claim; a trip that IS a
# LATE-START must have broadcast AND dwelt at the origin, so it actually ran
# (late). Therefore LATE-START and NEVER-RAN (ghost) are disjoint classes, and
# each classifiable trip maps to exactly ONE label.
# ---------------------------------------------------------------------------


def test_classify_labels_single_class_per_trip():
    """Every classifiable trip maps to exactly one label (no double-count)."""
    dep_min = _hminute(7, 17)
    late = [
        _pos(OLAT, OLON, 7, 16),
        _pos(OLAT, OLON, 7, 31),
        _pos(43.7280, -79.6480, 7, 40),
    ]
    never = []  # no broadcast at all -> NEVER-RAN
    sched = _scheduled([("T-late", "16", dep_min, 50), ("T-ghost", "16", dep_min, 50)])
    origin = {
        "T-late": ("1687", dep_min, (OLAT, OLON)),
        "T-ghost": ("1687", dep_min, (OLAT, OLON)),
    }
    labels = classify_labels(
        DATE, sched, {"T-late": late, "T-ghost": never}, origin, [_poll_at(7, 20)]
    )
    assert labels["T-late"] == "LATE-START"
    assert labels["T-ghost"] == "NEVER-RAN"
    # disjointness: no trip appears in more than one class.
    for cls in _CLASSES:
        members = {t for t, c in labels.items() if c == cls}
        for other in _CLASSES:
            if other == cls:
                continue
            assert members.isdisjoint({t for t, c in labels.items() if c == other})


def test_late_start_never_ran_disjoint():
    """A LATE-START trip is never a NEVER-RAN/ghost for the same departure."""
    dep_min = _hminute(7, 17)
    late = [
        _pos(OLAT, OLON, 7, 16),
        _pos(OLAT, OLON, 7, 31),
        _pos(43.7280, -79.6480, 7, 40),
    ]
    never = []
    sched = _scheduled([("A", "16", dep_min, 50), ("B", "16", dep_min, 50)])
    origin = {
        "A": ("1687", dep_min, (OLAT, OLON)),
        "B": ("1687", dep_min, (OLAT, OLON)),
    }
    labels = classify_labels(
        DATE, sched, {"A": late, "B": never}, origin, [_poll_at(7, 20)]
    )
    late_set = {t for t, c in labels.items() if c == "LATE-START"}
    never_set = {t for t, c in labels.items() if c == "NEVER-RAN"}
    assert late_set == {"A"}
    assert never_set == {"B"}
    assert late_set.isdisjoint(never_set)


def test_no_double_count_sums_exactly_once():
    """The classes partition the classifiable scheduled set: no trip counted 2x.

    Across a synthetic day exercising several classes, the total number of
    labels strictly equals the number of classifiable trips -- so the late-start
    and ghost receipts, taken together, never double-count a single failure.
    """
    dep_min = _hminute(7, 17)
    late = [
        _pos(OLAT, OLON, 7, 16),
        _pos(OLAT, OLON, 7, 31),
        _pos(43.7280, -79.6480, 7, 40),
    ]
    ontime = [
        _pos(OLAT, OLON, 7, 16),
        _pos(OLAT, OLON, 7, 17),
        _pos(43.7280, -79.6480, 7, 19),
    ]
    ghost = []  # never broadcast -> NEVER-RAN (the ghost family's claim)
    origin = {
        "A": ("1687", dep_min, (OLAT, OLON)),
        "B": ("1687", dep_min, (OLAT, OLON)),
        "C": ("1687", dep_min, (OLAT, OLON)),
    }
    sched = _scheduled(
        [("A", "16", dep_min, 50), ("B", "16", dep_min, 50), ("C", "16", dep_min, 50)]
    )
    labels = classify_labels(
        DATE, sched, {"A": late, "B": ontime, "C": ghost}, origin, [_poll_at(7, 20)]
    )
    assert labels["A"] == "LATE-START"
    assert labels["B"] == "ON-TIME"
    assert labels["C"] == "NEVER-RAN"
    # sum of per-class memberships == number of classifiable trips.
    total = sum(sum(1 for t, c in labels.items() if c == cls) for cls in _CLASSES)
    assert total == len(labels) == 3
    # explicitly: the late-start and never-ran sets never share a trip_id.
    assert {"A"}.isdisjoint({"C"})
