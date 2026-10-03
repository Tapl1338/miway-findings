"""Tests for ``scripts/audit_ground_truth_trips.seq_decrease``.

The audit flags a ride when matched GTFS ``stop_sequence`` values go
backwards (a scrambled or mislabeled log). Between-stops observations like
``Derry Rd east of Hurontario (SENSOR FLIP)`` token-overlap with a real stop
name but are *positional anchors*, not stop visits — a weak token-only match
must never produce a SEQ-DECREASE flag or advance the sequence pointer.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config
from scripts.audit_ground_truth_trips import (
    HARD_PREFIXES,
    audit_rides,
    load_gtfs,
    seq_decrease,
)
from scripts.backfill_ground_truth_sched import (
    SCORE_PREFIX,
    SCORE_SUFFIX,
    SCORE_TOKEN,
    match_score,
    norm,
)


def test_between_stops_descriptor_is_weak() -> None:
    # "east of Hurontario" must NOT score as a strong stop-name match
    loc = norm("Derry Rd east of Hurontario (SENSOR FLIP)")
    score = match_score(loc, norm("Derry Rd At Hurontario St"))
    assert score < SCORE_PREFIX  # token-overlap only (weak)
    assert 0 < score  # it still finds *something* (the audit reports no LOC-UNMATCHED)


def test_weak_match_never_flags_decrease() -> None:
    # 2459 ride: Edwards (seq 25) -> "east of Hurontario" -> Kenderry (seq 26)
    weak = SCORE_TOKEN + 5 * 2 + 8  # 78: {derry, hurontario} overlap
    assert seq_decrease(weak, seq=24, prev_seq=25) is None
    assert seq_decrease(weak, seq=24, prev_seq=24) is None


def test_strong_match_flags_decrease() -> None:
    assert seq_decrease(SCORE_SUFFIX, seq=24, prev_seq=25) == "SEQ-DECREASE(24<25)"
    assert seq_decrease(SCORE_PREFIX, seq=24, prev_seq=25) == "SEQ-DECREASE(24<25)"


def test_strong_match_forward_is_clean() -> None:
    assert seq_decrease(SCORE_SUFFIX, seq=26, prev_seq=25) is None
    assert seq_decrease(SCORE_SUFFIX, seq=25, prev_seq=25) is None  # repeat stop OK


# Full-dataset regression contract: the *only* flags the whole audit may
# produce are the documented terminal-throng / ride-end BIG-DELTAs, keyed by
# the row's timestamp. Adding a ride that introduces any other flag (or a new
# BIG-DELTA) fails here on purpose so the change is a conscious one.
EXPECTED_NONHARD_FLAGS = sorted(
    [
        ("2026-08-21 18:07:40", "BIG-DELTA(13->25)"),  # City Centre boarding throng
        ("2026-08-21 18:43:00", "BIG-DELTA(35->23)"),  # Lakeshore 12-off
        ("2026-08-21 18:47:00", "BIG-DELTA(21->3)"),  # Port Credit ride end
        ("2026-08-21 20:04:00", "BIG-DELTA(10->0)"),  # Meadowvale ride end
        ("2026-08-27 15:01:00", "BIG-DELTA(22->32)"),  # Hurontario +14 surge
        ("2026-08-29 18:29:00", "BIG-DELTA(22->36)"),  # 109N City Centre +21 throng
        # 2026-09-12 rides (109 Kipling run + 11 Westwood run), restored
        # 2026-09-14 after the sync-stall revert deleted the laptop copy;
        # the merge was followed by a full chronological sort (entry order
        # previously produced SEQ-/TS-DECREASE artifacts — sorted away,
        # they were never bad data). One residual: an 11:50 mid-segment
        # chain-rebuild row that sorts before its 11:48/11:51 neighbors
        # by ts but carries a higher in-ride sequence.
        ("2026-09-12 11:22:00", "BIG-DELTA(13->0)"),  # Kipling ride end (all off)
        ("2026-09-12 11:50:00", "SEQ-DECREASE(10<11)"),  # mid-segment rebuild row
        ("2026-09-12 11:54:00", "BIG-DELTA(13->0)"),  # Westwood Sq ride end (all off)
    ]
)


def test_full_audit_zero_hard_anomalies() -> None:
    """The whole ground_truth dataset audits clean (regression guard).

    Runs the real audit over ``ground_truth.csv`` + GTFS static and asserts:
    * zero hard anomalies (trip missing, route mismatch, unmatched location,
      sched far/mismatch),
    * the complete set of remaining flags is exactly the documented
      BIG-DELTAs above — no SEQ-/TS-DECREASE, no SCHED-* surprises.
    """
    trips, _, routes = load_gtfs(config.LOCAL_GTFS_DIR)
    with (config.DATA_DIR / "ground_truth.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    reports = audit_rides(rows, trips, routes)

    assert sum(rep["n_rows"] for rep in reports) == len(rows)
    hard = [m for rep in reports for m in rep["hard_msgs"]]
    assert hard == [], f"hard anomalies: {hard}"

    nonhard = sorted(
        (r["ts"], issue)
        for rep in reports
        for r, issues in rep["rows"]
        for issue in issues
        if not issue.startswith(HARD_PREFIXES)
    )
    assert nonhard == EXPECTED_NONHARD_FLAGS
