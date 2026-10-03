"""Tests for ``scripts/daily_alert_join.py`` (scheduled EXPECTED-join wrapper)."""

import datetime
from pathlib import Path

from scripts.daily_alert_join import date_stem


def test_date_stem_yields_dated_no_suffix_path():
    stem = date_stem(Path("docs/runs"), datetime.date(2026, 8, 31))
    assert stem == Path("docs/runs/alert-join-20260831")
    assert stem.suffix == ""  # --out must be a bare stem; .py tags .csv/.md on


def test_date_stem_pads_month_and_day():
    stem = date_stem(Path("r"), datetime.date(2026, 1, 7))
    assert stem.name == "alert-join-20260107"
    assert str(stem).endswith("20260107")  # single-digit day/month zero-padded


def test_dated_stems_are_unique_and_monotonic():
    d1 = date_stem(Path("r"), datetime.date(2026, 8, 31)).name
    d2 = date_stem(Path("r"), datetime.date(2026, 9, 1)).name
    assert d1 != d2
    assert d1 < d2  # lexical order == chronological order
