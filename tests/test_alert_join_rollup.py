"""Tests for ``scripts/alert_join_rollup.py`` (receipt -> EXPECTED trend)."""

import datetime
from pathlib import Path

from scripts.alert_join_rollup import parse_receipt, receipt_date, trend_rows

EMPTY_RECEIPT = """
# T46b — Ghost corridor forensics

Ghosts classified: 718 (from ghost_trips.csv corrected cut)

| classification | count |
|---|---|
| CORRIDOR-EMPTY | 20 |
| VEHICLES-PRESENT-NO-MATCH | 698 |

## T52 EXPECTED reclassifications (construction stop relocations)

0 ghost(s) reassigned out of the off-corridor buckets
because a STOP_MOVED+CONSTRUCTION alert named a displaced stop on the
same route. Snapshot receipts exist only for windows collected after.

| route | date | trip | window | first stop |
|---|---|---|---|---|

## Top-10 CORRIDOR-EMPTY field sheet
| 74 | 20260821 | 30312051 | 14:17–14:35 | 3225 |
"""

POPULATED_RECEIPT = """
Ghosts classified: 718

| classification | count |
|---|---|
| CORRIDOR-EMPTY | 19 |
| CORRIDOR-EMPTY-QUIET | 1 |
| AMBIGUOUS-NO-SCHEDULE | 4 |
| AMBIGUOUS-UNCOVERED | 2 |
| EXPECTED | 2 |

## T52 EXPECTED reclassifications (construction stop relocations)

2 ghost(s) reassigned out of the off-corridor buckets.

| route | date | trip | window | first stop |
|---|---|---|---|---|
| 49 | 20260830 | 90001 | 10:20–10:38 | 4902 |
| 49 | 20260831 | 90002 | 07:05–07:22 | 4902 |
"""


def test_parse_empty_receipt():
    p = parse_receipt(EMPTY_RECEIPT)
    assert p["total"] == 718
    assert p["counts"]["CORRIDOR-EMPTY"] == 20
    assert p["expected"] == 0
    assert p["expected_rows"] == []


def test_parse_populated_receipt_captures_expected_pins():
    p = parse_receipt(POPULATED_RECEIPT)
    assert p["expected"] == 2
    assert p["counts"]["CORRIDOR-EMPTY"] == 19
    assert p["counts"]["CORRIDOR-EMPTY-QUIET"] == 1
    assert p["expected_rows"] == [
        ("49", "20260830", "90001", "10:20–10:38", "4902"),
        ("49", "20260831", "90002", "07:05–07:22", "4902"),
    ]


def test_receipt_date_from_filename():
    assert receipt_date(Path("alert-join-20260831.md")) == datetime.date(2026, 8, 31)
    assert receipt_date(Path("alert-join-20260107.md")) == datetime.date(2026, 1, 7)
    assert receipt_date(Path("alert-join-bad.md")) is None


def test_trend_rows_sorted_and_zeroes_missing_classes():
    rows = trend_rows(
        [
            (datetime.date(2026, 8, 31), parse_receipt(EMPTY_RECEIPT)),
            (datetime.date(2026, 9, 1), parse_receipt(POPULATED_RECEIPT)),
        ]
    )
    assert [r["date"] for r in rows] == ["2026-08-31", "2026-09-01"]
    # the empty receipt has no QUIET row; the trend must still emit a 0
    assert rows[0]["CORRIDOR-EMPTY-QUIET"] == 0
    assert rows[0]["VEHICLES-PRESENT-NO-MATCH"] == 698  # from the empty receipt tally
    assert rows[0]["EXPECTED"] == 0
    # empty receipt omits the AMBIGUOUS family -> zero-filled
    assert rows[0]["AMBIGUOUS-UNCOVERED"] == 0
    assert rows[0]["AMBIGUOUS-NO-SCHEDULE"] == 0
    # populated receipt omits VEHICLES-PRESENT-NO-MATCH -> zero-filled
    assert rows[1]["VEHICLES-PRESENT-NO-MATCH"] == 0
    assert rows[1]["AMBIGUOUS-UNCOVERED"] == 2
    assert rows[1]["AMBIGUOUS-NO-SCHEDULE"] == 4
    assert rows[1]["EXPECTED"] == 2
    assert rows[1]["CORRIDOR-EMPTY"] == 19
