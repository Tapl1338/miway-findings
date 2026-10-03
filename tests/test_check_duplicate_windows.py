"""Duplicate-collector detection from the coverage ledger.

Regression tests for ``scripts/check_duplicate_windows.py``. Both signatures
were observed live on Sep 3-4 2026, when a second collector raced past the
single-instance check: two ``completed`` rows for one window, and near-
simultaneous ``window_start`` stamps. A legitimate restart-mid-window
(partial row, re-collected later) must NOT flag.
"""

from scripts.check_duplicate_windows import find_duplicates

HEADER = (
    "date,window_start,window_end,scheduled,status,polls_attempted,"
    "polls_succeeded,polls_failed,first_poll_at,last_poll_at,observations,"
    "vp_snapshots,alerts,longest_gap_min,polls_timeout\n"
)


def _write(tmp_path, body: str):
    p = tmp_path / "collection_windows.csv"
    p.write_text(HEADER + body, encoding="utf-8")
    return p


def test_two_completed_rows_flag(tmp_path):
    p = _write(
        tmp_path,
        "2026-09-04,2026-09-04 00:00:17,2026-09-04 06:00:00,00:00-06:00,"
        "completed,699,699,0,2026-09-04 00:00:18,2026-09-04 05:59:30,"
        "1503608,699,77,0.77,0\n"
        "2026-09-04,2026-09-04 00:03:06,2026-09-04 06:00:00,00:00-06:00,"
        "completed,695,695,0,2026-09-04 00:03:07,2026-09-04 05:59:42,"
        "1495418,695,77,0.58,0\n",
    )
    findings = find_duplicates(p)
    assert len(findings) == 1
    assert "2 'completed' rows" in findings[0]
    assert "2026-09-04" in findings[0]


def test_near_simultaneous_starts_flag(tmp_path):
    # The Sep 4 06:00 window: two collectors 2 seconds apart, one partial.
    p = _write(
        tmp_path,
        "2026-09-04,2026-09-04 06:03:26,2026-09-04 09:00:00,06:00-09:00,"
        "completed,335,335,0,2026-09-04 06:03:27,2026-09-04 08:59:41,"
        "2226468,335,77,1.15,0\n"
        "2026-09-04,2026-09-04 06:03:28,2026-09-04 09:00:00,06:00-09:00,"
        "partial,336,335,1,2026-09-04 06:03:29,2026-09-04 08:59:35,"
        "2226551,335,77,1.03,0\n",
    )
    findings = find_duplicates(p)
    assert len(findings) == 1
    assert "started 0.0 min apart" in findings[0]


def test_legit_restart_does_not_flag(tmp_path):
    # A window abandoned mid-collect (partial) and re-collected an hour
    # later is normal self-healing, not a duplicate.
    p = _write(
        tmp_path,
        "2026-09-03,2026-09-03 19:12:16,2026-09-04 00:00:00,19:00-24:00,"
        "partial,524,523,1,2026-09-03 19:12:17,2026-09-03 23:59:42,"
        "2033846,523,77,5.43,1\n"
        "2026-09-03,2026-09-03 20:15:00,2026-09-04 00:00:00,19:00-24:00,"
        "completed,300,300,0,2026-09-03 20:15:01,2026-09-03 23:59:50,"
        "1900000,300,77,1.00,0\n",
    )
    assert find_duplicates(p) == []


def test_wide_start_gap_within_threshold_flags(tmp_path):
    # Starts 14 min apart: under the 15-min restart threshold, so the race
    # signature still fires even though neither row is 'completed' twice.
    p = _write(
        tmp_path,
        "2026-09-02,2026-09-02 06:08:14,2026-09-02 09:00:00,06:00-09:00,"
        "interrupted,100,100,0,2026-09-02 06:08:15,2026-09-02 07:00:00,"
        "500000,100,0,0.5,0\n"
        "2026-09-02,2026-09-02 06:22:14,2026-09-02 09:00:00,06:00-09:00,"
        "completed,200,200,0,2026-09-02 06:22:15,2026-09-02 08:59:00,"
        "900000,200,0,0.5,0\n",
    )
    findings = find_duplicates(p, restart_gap_min=15.0)
    assert len(findings) == 1
    assert "started 14.0 min apart" in findings[0]


def test_gap_at_threshold_is_a_restart(tmp_path):
    p = _write(
        tmp_path,
        "2026-09-02,2026-09-02 06:08:14,2026-09-02 09:00:00,06:00-09:00,"
        "partial,100,100,0,2026-09-02 06:08:15,2026-09-02 07:00:00,"
        "500000,100,0,0.5,0\n"
        "2026-09-02,2026-09-02 06:23:14,2026-09-02 09:00:00,06:00-09:00,"
        "completed,200,200,0,2026-09-02 06:22:15,2026-09-02 08:59:00,"
        "900000,200,0,0.5,0\n",
    )
    assert find_duplicates(p, restart_gap_min=15.0) == []


def test_single_collector_history_is_clean(tmp_path):
    p = _write(
        tmp_path,
        "2026-09-03,2026-09-03 00:00:17,2026-09-03 06:00:00,00:00-06:00,"
        "completed,699,699,0,2026-09-03 00:00:18,2026-09-03 05:59:30,"
        "1503608,699,77,0.77,0\n"
        "2026-09-03,2026-09-03 06:03:26,2026-09-03 09:00:00,06:00-09:00,"
        "completed,335,335,0,2026-09-03 06:03:27,2026-09-03 08:59:41,"
        "2226468,335,77,1.15,0\n",
    )
    assert find_duplicates(p) == []


def test_missing_ledger_returns_no_findings(tmp_path):
    assert find_duplicates(tmp_path / "absent.csv") == []


def test_since_days_limits_scan_to_trailing_dates(tmp_path):
    p = _write(
        tmp_path,
        # Old duplicate: outside the trailing-1-day window.
        "2026-08-18,2026-08-18 10:12:16,2026-08-18 15:00:00,09:00-15:00,"
        "completed,100,100,0,2026-08-18 10:12:17,2026-08-18 14:00:00,"
        "80000,100,0,0.5,0\n"
        "2026-08-18,2026-08-18 10:20:16,2026-08-18 15:00:00,09:00-15:00,"
        "completed,100,100,0,2026-08-18 10:20:17,2026-08-18 14:00:00,"
        "80000,100,0,0.5,0\n"
        # Clean trailing day.
        "2026-09-04,2026-09-04 06:03:26,2026-09-04 09:00:00,06:00-09:00,"
        "completed,335,335,0,2026-09-04 06:03:27,2026-09-04 08:59:41,"
        "2226468,335,77,1.15,0\n",
    )
    assert find_duplicates(p, since_days=1) == []
    assert len(find_duplicates(p)) == 1


def test_corrupt_timestamp_rows_are_skipped_not_crashed(tmp_path):
    p = _write(
        tmp_path,
        "2026-09-04,not-a-timestamp,2026-09-04 09:00:00,06:00-09:00,"
        "completed,335,335,0,,,2226468,335,77,1.15,0\n"
        "2026-09-04,2026-09-04 06:03:28,2026-09-04 09:00:00,06:00-09:00,"
        "partial,336,335,1,,,2226551,335,77,1.03,0\n",
    )
    # One parsable start only: nothing to compare, no crash, no finding.
    assert find_duplicates(p) == []
