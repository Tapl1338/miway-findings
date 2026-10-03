"""Tests for the holiday validation (app.statutory_calendar + CLI script)."""

from datetime import date


from app import statutory_calendar as vh


def _write_feed(tmp_path, lines: list[str]) -> None:
    (tmp_path / "calendar_dates.txt").write_text(
        "service_id,date,exception_type\n" + "".join(lines),
        encoding="utf-8",
    )


def test_easter_computus_known_years():
    assert vh._easter(2026) == date(2026, 4, 5)
    assert vh._easter(2024) == date(2024, 3, 31)
    assert vh._easter(2025) == date(2025, 4, 20)


def test_ontario_2026_calendar():
    cal = vh.ontario_statutory_holidays(2026)
    assert cal["Labour Day"] == date(2026, 9, 7)
    assert cal["Thanksgiving"] == date(2026, 10, 12)
    assert cal["Family Day"] == date(2026, 2, 16)
    assert cal["Victoria Day"] == date(2026, 5, 18)  # Monday preceding May 25
    assert cal["Good Friday"] == date(2026, 4, 3)


def test_victoria_day_never_may_25():
    # May 25 2026 IS a Monday; Victoria Day must still be the 18th.
    for year, expect in [
        (2024, date(2024, 5, 20)),
        (2025, date(2025, 5, 19)),
        (2026, date(2026, 5, 18)),
    ]:
        assert vh.ontario_statutory_holidays(year)["Victoria Day"] == expect
        assert vh.ontario_statutory_holidays(year)["Victoria Day"] < date(year, 5, 25)


def test_clean_feed_matches(tmp_path):
    # Feed covers Aug 5 - Oct 25 2026; both in-window holidays present.
    rows = [("20260907", 1), ("20261012", 1)] + [
        (d2, 1) for d2 in ("20260805", "20260908", "20261025")
    ]
    _write_feed(
        tmp_path,
        [
            f"{svc},{d},{e}\n"
            for d, e in rows
            for svc in (
                ["26SE07-CPBlock-Holiday1-14"]
                if d in ("20260907", "20261012")
                else ["26SE07-CPBlock-Weekday-11"]
            )
        ],
    )
    assert vh.check(tmp_path) == []


def test_missing_in_window_statutory_is_mismatch(tmp_path):
    # Feed covers the week around Labour Day but marks no holiday service.
    _write_feed(
        tmp_path,
        [
            "26SE07-CPBlock-Weekday-11,20260904,1\n",
            "26SE07-CPBlock-Weekday-11,20260908,1\n",
        ],
    )
    warnings = vh.check(tmp_path)
    assert any("Labour Day 2026-09-07" in w and "MISMATCH" in w for w in warnings)


def test_feed_holiday_with_no_statutory_within_3_days_is_mismatch(tmp_path):
    # Mid-September is nowhere near Labour Day (Sep 7) or any statutory date.
    # (Sep 8 would be accepted as a Labour Day observed-shift — the ±3-day
    # tolerance exists for those.)
    _write_feed(
        tmp_path,
        [
            "26SE07-CPBlock-Holiday1-14,20260915,1\n",
            "26SE07-CPBlock-Weekday-11,20260916,1\n",
        ],
    )
    warnings = vh.check(tmp_path)
    assert any(
        "2026-09-15" in w and "no Ontario statutory holiday" in w for w in warnings
    )


def test_out_of_window_holidays_not_demanded(tmp_path):
    """A 3-week feed cannot carry Christmas — no false alarm."""
    _write_feed(
        tmp_path,
        [
            "26SE07-CPBlock-Weekday-11,20260901,1\n",
            "26SE07-CPBlock-Holiday1-14,20260907,1\n",
            "26SE07-CPBlock-Weekday-11,20260921,1\n",
        ],
    )
    assert vh.check(tmp_path) == []


def test_year_filter_intersects_window(tmp_path):
    _write_feed(tmp_path, ["26SE07-CPBlock-Weekday-11,20260908,1\n"])
    # Restricting to 2027 shrinks the covered window to nothing checkable.
    assert vh.check(tmp_path, years=[2027]) == []


def test_civic_holiday_is_note_not_mismatch(tmp_path):
    # Feed covering only the civic-holiday week, no holiday service.
    _write_feed(
        tmp_path,
        [
            "26AU03-CPBlock-Weekday-11,20260731,1\n",
            "26AU03-CPBlock-Weekday-11,20260805,1\n",
        ],
    )
    warnings = vh.check(tmp_path)
    assert any("Civic Holiday" in w and w.strip().startswith("note:") for w in warnings)
    assert not any("MISMATCH" in w for w in warnings)


def test_empty_feed_reported(tmp_path):
    _write_feed(tmp_path, [])
    assert vh.check(tmp_path) == [
        "  feed has no calendar_dates rows — nothing to check"
    ]


def test_real_feed_check_is_clean():
    """The shipped feed's holiday markings match the statutory calendar."""
    from app import config as app_config

    assert vh.check(app_config.LOCAL_GTFS_DIR) == []


def test_cli_script_clean_exit(tmp_path, monkeypatch):
    """The validate_holidays.py CLI wrapper: exit 0 on a clean feed."""
    import sys

    _write_feed(
        tmp_path,
        [
            "26SE07-CPBlock-Weekday-11,20260901,1\n",
            "26SE07-CPBlock-Holiday1-14,20260907,1\n",
            "26SE07-CPBlock-Weekday-11,20260921,1\n",
        ],
    )
    from scripts import validate_holidays as cli

    monkeypatch.setattr(
        sys, "argv", ["validate_holidays.py", "--gtfs-dir", str(tmp_path)]
    )
    assert cli.main() == 0


def test_cli_script_mismatch_exit(tmp_path, monkeypatch):
    """--fail-on-error must exit 1 when a statutory holiday is missing."""
    import sys

    _write_feed(
        tmp_path,
        [
            "26SE07-CPBlock-Weekday-11,20260904,1\n",
            "26SE07-CPBlock-Weekday-11,20260908,1\n",
        ],
    )
    from scripts import validate_holidays as cli

    monkeypatch.setattr(
        sys,
        "argv",
        ["validate_holidays.py", "--gtfs-dir", str(tmp_path), "--fail-on-error"],
    )
    assert cli.main() == 1
