"""Tests for the schedule-padding evidence parser (``app/schedule_padding.py``).

Synthetic: holds are classified and aggregated from hand-built CSV rows so the
detection rules (what counts as a schedule hold, what is a recount / sensor /
kindness hold to exclude) are pinned exactly.
"""

import csv
import io
from pathlib import Path

from app.schedule_padding import _norm_loc, build_schedule_padding, classify_hold

_HEADER = [
    "service_date",
    "route",
    "vehicle_id",
    "location",
    "reported_pct",
    "reported_status",
    "counted_pax",
    "vehicle_note",
    "model_pax_at_65",
    "notes",
    "sched_time",
    "actual_time",
]


def _rows(records, header=_HEADER):
    """Properly quote a list of row-lists into a comma/quote-escaped CSV file."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for rec in records:
        w.writerow(rec)
    return buf.getvalue()


def _build(records, tmp_path):
    p = tmp_path / "ground_truth.csv"
    Path(p).write_text(_rows(records), encoding="utf-8")
    return build_schedule_padding(p)


# --- classify_hold ---------------------------------------------------------


def test_hold_for_time_counts():
    is_pad, zero, _hold, early = classify_hold(
        "R42 ride; holding for time at Syntex Crt (~2 min early); no turnover"
    )
    assert is_pad is True
    assert zero is True  # "no turnover during hold" is a zero-wait signal
    assert early == 2.0


def test_explicit_zero_wait_counts():
    is_pad, zero, _, _ = classify_hold(
        "driver holding at Maxwell timepoint with NO passengers waiting"
    )
    assert is_pad is True
    assert zero is True


def test_layover_to_burn_early_counts():
    is_pad, _, _, early = classify_hold(
        "LAYOVER - driver holding to kill ~5 min early running"
    )
    assert is_pad is True
    assert early == 5.0


def test_pre_departure_dwell_counts():
    is_pad, _, hold, _ = classify_hold(
        "Bus holding at Westwood terminal pre-departure (~5 min)"
    )
    assert is_pad is True
    assert hold == 5.0


def test_kindness_hold_excluded():
    is_pad, _, _, _ = classify_hold(
        "DRIVER WAITED so 1 extra pax could run on (kindness datapoint)"
    )
    assert is_pad is False


def test_sensor_hysteresis_excluded():
    is_pad, _, _, _ = classify_hold("sensor still 40% (hysteresis holding)")
    assert is_pad is False


def test_ambiguous_hold_requires_schedule_lexicon():
    # "held" alone isn't enough to be a schedule hold.
    is_pad, _, _, _ = classify_hold("driver held at the stop briefly")
    assert is_pad is False


def test_ride_end_recap_excluded():
    is_pad, _, _, _ = classify_hold(
        "RIDE END trip 30311154. Full log: 8 (Sheridan) -> ... held for time at Vipond ..."
    )
    assert is_pad is False


def test_red_light_timewait_excluded():
    is_pad, _, _, _ = classify_hold(
        "driver left hold early and used the next red light as the time wait (schedule-neutral)"
    )
    assert is_pad is False


# --- _norm_loc dedup -------------------------------------------------------


def test_norm_loc_strips_qualifier_and_mojibake_dash():
    a = _norm_loc("Maxwell Rd (holding for time)")
    b = _norm_loc("Maxwell Rd \u2014 hold measured")
    assert a == b == "maxwell rd"


# --- build_schedule_padding aggregation ------------------------------------


def _rec(date, route, veh, loc, pct, status, pax, vnote, model, note, sched, actual):
    return [date, route, veh, loc, pct, status, pax, vnote, model, note, sched, actual]


def test_build_dedupes_hold_and_rolls_up_by_route(tmp_path):
    rows = [
        _rec(
            "20260818",
            "42",
            "3289",
            "Maxwell Rd (holding for time)",
            "20",
            "1",
            "23",
            "articulated",
            "26",
            "driver holding at Maxwell timepoint with NO passengers waiting",
            "12:41:00",
            "12:38:37",
        ),
        _rec(
            "20260818",
            "42",
            "3289",
            "Maxwell Rd \u2014 hold measured",
            "20",
            "1",
            "23",
            "articulated",
            "26",
            "~2-3 min hold at Maxwell, no passengers waiting (observed)",
            "12:41:00",
            "12:38:37",
        ),
        _rec(
            "20260827",
            "42",
            "2459",
            "Derry Rd At John Watt Blvd (time hold)",
            "20",
            "1",
            "22",
            "standard",
            "13",
            "3rd time hold of the ridership; holding for time",
            "14:54:00",
            "14:53:23",
        ),
    ]
    d = _build(rows, tmp_path)
    assert d["available"] is True
    # Maxwell (2 rows) + John Watt (1 row) -> 2 distinct holds, both R42.
    assert d["n_holds"] == 2
    assert d["n_zero_wait"] == 1
    assert len(d["by_route"]) == 1
    assert d["by_route"][0]["route"] == "42"
    assert d["by_route"][0]["n_holds"] == 2
    assert d["by_route"][0]["zero_wait_holds"] == 1
    maxw = [e for e in d["events"] if "Maxwell" in e["location"]]
    assert len(maxw) == 1
    assert maxw[0]["n_rows"] == 2
    assert maxw[0]["hold_min"] == 2.5
    assert maxw[0]["zero_wait"] is True


def test_build_empty_file_unavailable():
    d = build_schedule_padding("/nonexistent/path.csv")
    assert d["available"] is False
