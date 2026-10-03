"""Tests for scripts/record_ride.py (ground-truth headcount collector)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schedule_padding import classify_hold
from scripts import record_ride

STOPS = [
    {"stop_id": "1", "name": "Derry Rd At Syntex Dr", "lat": 43.605, "lon": -79.755},
    {
        "stop_id": "2",
        "name": "Erin Mills Pky At Derry Rd",
        "lat": 43.610,
        "lon": -79.760,
    },
]


def test_find_stop_fragment_exact():
    hits = record_ride.find_stop_fragment(STOPS, "Syntex")
    assert [s["stop_id"] for s in hits] == ["1"]


def test_find_stop_fragment_fuzzy_words():
    # "at" is filler; both stops contain "derry", but only stop 1 has "syntex"
    hits = record_ride.find_stop_fragment(STOPS, "Derry At Syntex")
    assert [s["stop_id"] for s in hits] == ["1"]


def test_find_stop_fragment_no_hits():
    assert record_ride.find_stop_fragment(STOPS, "zzz nowhere") == []


def test_haversine_m_known_distance():
    # ~1 degree of latitude is ~111 km
    d = record_ride.haversine_m(43.6, -79.7, 43.7, -79.7)
    assert 11_000 < d < 11_300


def test_buses_near_filters_and_sorts():
    buses = [
        {"vehicle_id": "far", "lat": 43.60, "lon": -79.80},  # ~3.9 km away
        {"vehicle_id": "near", "lat": 43.6051, "lon": -79.7550},  # ~12 m away
    ]
    near = record_ride.buses_near(STOPS, buses, STOPS[0])
    assert [b["vehicle_id"] for b in near] == ["near"]
    assert near[0]["dist_m"] < 50


def test_append_row_creates_file_and_appends(tmp_path: Path):
    out = tmp_path / "ground_truth.csv"
    record_ride.OUT = out
    row = {
        "ts": "2026-08-18 12:20:00",
        "service_date": "20260818",
        "vehicle_id": "9999",
        "trip_id": "T1",
        "route": "42",
        "location": "Test",
        "reported_pct": 20,
        "reported_status": 1,
        "counted_pax": 15,
        "vehicle_note": "test",
        "model_pax_at_65": 13,
        "notes": "unit test",
    }
    record_ride.append_row(row)
    record_ride.append_row({**row, "vehicle_id": "8888", "counted_pax": 30})

    with open(out, newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert rows[1]["vehicle_id"] == "8888"
    assert rows[1]["counted_pax"] == "30"


def test_build_hold_note_bare():
    """A bare --hold still emits canonical padding language."""
    note = record_ride._build_hold_note(None, None, False)
    assert "holding for time at timepoint" in note
    assert classify_hold(note)[0] is True


def test_build_hold_note_full():
    """Flags produce a note the schedule-padding parser fully classifies."""
    note = record_ride._build_hold_note(3.0, 2.0, True)
    assert "~3 min early" in note
    assert "held ~2 min" in note
    assert "no passengers waiting" in note
    is_pad, zero_wait, hold_min, early_min = classify_hold(note)
    assert is_pad is True
    assert zero_wait is True
    assert hold_min == 2.0
    assert early_min == 3.0
