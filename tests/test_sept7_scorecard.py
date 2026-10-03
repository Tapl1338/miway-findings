"""Tests for ``scripts/sept7_scorecard.py`` — the pre-registration scorer.

Covers the coverage-ledger weekday math, the FQ-10 early-rate recipe
(pinned comparator ``<= -2.0``, measured rows only), the era-split ghost
rate with its UNMEASURABLE fallback, verdict banding, and the Section-1
pre-change zip SHA gate.
"""

import csv
import hashlib

import pandas as pd
import pytest

from scripts import sept7_scorecard as sc


# ---------------------------------------------------------------- weekdays


def test_post_change_weekdays_counts_only_weekdays_after_cutoff(tmp_path):
    # Mon 2026-09-14 .. Sun 2026-09-20: 14,15,16,17,18 are weekdays.
    rows = [
        {"date": "2026-09-07", "status": "COMPLETE"},  # pre-cutoff: excluded
        {"date": "2026-09-08", "status": ""},  # no status: excluded
        {"date": "2026-09-13", "status": "COMPLETE"},  # Sunday
        {"date": "2026-09-14", "status": "COMPLETE"},
        {"date": "2026-09-15", "status": "PARTIAL"},
        {"date": "2026-09-16", "status": "COMPLETE"},
        {"date": "2026-09-17", "status": "COMPLETE"},
        {"date": "2026-09-18", "status": "COMPLETE"},
        {"date": "2026-09-19", "status": "COMPLETE"},  # Saturday
        {"date": "2026-09-20", "status": "COMPLETE"},  # Sunday
    ]
    p = tmp_path / "collection_windows.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "status"])
        w.writeheader()
        w.writerows(rows)

    assert sc.post_change_weekdays(p) == [
        "2026-09-14",
        "2026-09-15",
        "2026-09-16",
        "2026-09-17",
        "2026-09-18",
    ]


# ------------------------------------------------------------- FQ-10 rates


def _lat_df(rows):
    return pd.DataFrame(
        rows,
        columns=["date", "dep_time_min", "horizon_minutes", "lateness_minutes"],
    )


def test_early_rates_fq10_measured_rows_only():
    # horizon > 0 = vendor forecast: excluded. Empty date = legacy: excluded.
    # Null lateness: excluded (cannot be counted early or on-time).
    lat = _lat_df(
        [
            ("2026-09-09", 420, -1, -3.0),  # measured, early: counts
            ("2026-09-09", 430, -1, 0.0),  # measured, not early: counts
            ("2026-09-09", 440, 5, -3.0),  # forecast row: excluded
            ("", 450, -1, -3.0),  # undated legacy: excluded
            ("2026-09-09", 460, -1, None),  # null lateness: excluded
        ]
    )
    r = sc.early_rates(lat)
    assert r["early_n"] == 2
    assert r["early_rate"] == pytest.approx(50.0)
    assert r["am_n"] == 2  # both counted rows are in 07:00-09:00
    assert r["am_rate"] == pytest.approx(50.0)


def test_early_rates_comparator_is_inclusive_at_minus_two():
    # The pinned comparator is <= -2.0 (exact -2.0 counts as early).
    lat = _lat_df(
        [
            ("2026-09-09", 420, -1, -2.0),
            ("2026-09-09", 430, -1, -1.99),
        ]
    )
    r = sc.early_rates(lat)
    assert r["early_n"] == 2
    assert r["early_rate"] == pytest.approx(50.0)


def test_early_rates_empty_window_is_nan_not_crash():
    lat = _lat_df([("", 0, 5, 1.0)])
    r = sc.early_rates(lat)
    assert r["early_n"] == 0
    assert r["early_rate"] != r["early_rate"]  # NaN


# ------------------------------------------------------------------ ghosts


def test_ghost_rate_is_era_split_on_post_change_dates():
    ghost = pd.DataFrame(
        {
            "service_date": ["20260905", "20260909", "20260910"],
            "verifiable_trips": [100, 1000, 1000],
            "ghost_count": [10, 5, 15],
        }
    )
    r = sc.ghost_rate(ghost, ["2026-09-09", "2026-09-10"])
    assert r["verifiable"] == 2000
    assert r["ghosts"] == 20
    assert r["rate"] == pytest.approx(1.0)  # pre-change 20260905 rows excluded


def test_ghost_rate_no_post_change_rows_is_unmeasurable():
    ghost = pd.DataFrame(
        {
            "service_date": ["20260805"],
            "verifiable_trips": [100],
            "ghost_count": [10],
        }
    )
    r = sc.ghost_rate(ghost, ["2026-09-09"])
    assert r["verifiable"] == 0
    assert r["rate"] != r["rate"]  # NaN -> verdict path reads UNMEASURABLE
    assert sc.verdict(r["rate"], sc.BAND_GHOST) == "PENDING (no data)"


# ---------------------------------------------------------------- verdicts


def test_verdict_banding():
    assert sc.verdict(31.0, (29.0, 33.0)) == "PASS"
    assert sc.verdict(28.9, (29.0, 33.0)) == "FAIL"
    assert sc.verdict(33.1, (29.0, 33.0)) == "FAIL"


# ------------------------------------------------------- Section 1 zip gate


def test_section1_flags_sha_mismatch(tmp_path, monkeypatch):
    zip_path = tmp_path / "miway_gtfs_2026-08-23_pre-sept7.zip"
    zip_path.write_bytes(b"not-the-real-archive")
    monkeypatch.setattr(sc, "PRECHANGE_ZIP", zip_path)
    monkeypatch.setattr(sc, "PRECHANGE_SHA16", "0" * 16)
    lines: list[str] = []
    sc.section1_zip_check(lines)
    text = "\n".join(lines)
    assert "MISMATCH" in text
    assert "STOP" in text


def test_section1_accepts_matching_sha(tmp_path, monkeypatch):
    zip_path = tmp_path / "miway_gtfs_2026-08-23_pre-sept7.zip"
    payload = b"archive-bytes"
    zip_path.write_bytes(payload)
    monkeypatch.setattr(sc, "PRECHANGE_ZIP", zip_path)
    monkeypatch.setattr(sc, "PRECHANGE_SHA16", hashlib.sha256(payload).hexdigest()[:16])
    lines: list[str] = []
    sc.section1_zip_check(lines)
    assert "matches pre-registration" in "\n".join(lines)


def test_section1_missing_zip_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "PRECHANGE_ZIP", tmp_path / "absent.zip")
    lines: list[str] = []
    sc.section1_zip_check(lines)
    assert "NOT FOUND" in "\n".join(lines)


# --------------------------------------------------- constants sanity gate


def test_frozen_bands_match_pre_registration():
    # If the pre-registration file changes its bands, this test forces the
    # scorer's frozen constants to be revisited deliberately.
    assert sc.BAND_EARLY == (29.0, 33.0)
    assert sc.BAND_AM_EARLY == (35.0, 39.0)
    assert sc.BAND_GHOST == (2.5, 3.5)
    assert sc.BAND_109_PM == (38.0, 42.0)
    assert sc.BAND_2_MIDNIGHT == (40.0, 44.0)
    assert sc.CUTOFF_DATE == "2026-09-08"
