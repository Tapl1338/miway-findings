"""Holiday detection from the GTFS feed (services.measured_data).

Labour Day 2026-09-07 falls on a Monday; the measured-stream routers must
recognize it from the feed (never a hard-coded calendar) so holiday days are
flagged in trends and excluded from weekday baselines.
"""

from app.services import measured_data as md


def _write_calendar_dates(tmp_path, rows):
    p = tmp_path / "calendar_dates.txt"
    p.write_text(
        "service_id,date,exception_type\n"
        + "".join(f"{s},{d},{e}\n" for s, d, e in rows),
        encoding="utf-8",
    )
    return p


def test_normalize_date_both_formats_and_garbage():
    assert md.normalize_date("2026-09-07") == "20260907"
    assert md.normalize_date("20260907") == "20260907"
    assert md.normalize_date(" garbage ") is None
    assert md.normalize_date("") is None
    assert md.normalize_date(None) is None
    assert md.normalize_date("2026-9-7") is None


def test_holiday_dates_from_feed(tmp_path, monkeypatch):
    _write_calendar_dates(
        tmp_path,
        [
            ("26AU03-CPBlock-Weekday-11", "20260901", 1),
            ("26SE07-CPBlock-Holiday1-14", "20260907", 1),  # Labour Day
            ("26SE07-MABlock-Weekday-21", "20260908", 1),
        ],
    )
    monkeypatch.setattr(md.config, "LOCAL_GTFS_DIR", tmp_path)
    md._holiday_dates_cached.cache_clear()
    try:
        assert md.holiday_dates() == frozenset({"20260907"})
        assert md.is_holiday_date("2026-09-07")
        assert md.is_holiday_date("20260907")
        assert not md.is_holiday_date("2026-09-08")
    finally:
        md._holiday_dates_cached.cache_clear()


def test_holiday_dates_removals_do_not_count(tmp_path, monkeypatch):
    """exception_type=2 (service removed) is not a holiday activation."""
    _write_calendar_dates(
        tmp_path,
        [
            ("26SE07-CPBlock-Holiday1-14", "20260907", 2),
            ("26SE07-CPBlock-Weekday-11", "20260908", 1),
        ],
    )
    monkeypatch.setattr(md.config, "LOCAL_GTFS_DIR", tmp_path)
    md._holiday_dates_cached.cache_clear()
    try:
        assert md.holiday_dates() == frozenset()
        assert not md.is_holiday_date("20260907")
    finally:
        md._holiday_dates_cached.cache_clear()


def test_holiday_dates_missing_feed_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(md.config, "LOCAL_GTFS_DIR", tmp_path)
    md._holiday_dates_cached.cache_clear()
    try:
        assert md.holiday_dates() == frozenset()
        assert md.is_holiday_date("20260907") is False
    finally:
        md._holiday_dates_cached.cache_clear()


def test_real_feed_marks_labour_day_and_thanksgiving():
    """The shipped feed must flag 2026-09-07 (Labour Day, a Monday) and
    2026-10-12 (Thanksgiving). Guards the whole feature against feed-path or
    column-shape regressions."""
    holidays = md.holiday_dates()
    assert "20260907" in holidays
    assert "20261012" in holidays
    assert not md.is_holiday_date("2026-09-08")


def test_mtime_cache_invalidates_on_feed_change(tmp_path, monkeypatch):
    """A feed refresh adding a holiday must be picked up without a restart."""
    import os

    _write_calendar_dates(
        tmp_path,
        [("26SE07-CPBlock-Weekday-11", "20260908", 1)],
    )
    monkeypatch.setattr(md.config, "LOCAL_GTFS_DIR", tmp_path)
    md._holiday_dates_cached.cache_clear()
    try:
        assert md.holiday_dates() == frozenset()
        _write_calendar_dates(
            tmp_path,
            [
                ("26SE07-CPBlock-Weekday-11", "20260908", 1),
                ("26SE07-CPBlock-Holiday1-14", "20260907", 1),
            ],
        )
        # Two writes can land inside one mtime tick under load; force the
        # new mtime so the (mtime, size) cache key provably changes.
        st = os.stat(tmp_path / "calendar_dates.txt")
        os.utime(
            tmp_path / "calendar_dates.txt",
            ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000),
        )
        assert "20260907" in md.holiday_dates()
    finally:
        md._holiday_dates_cached.cache_clear()


def test_block_cutoff_derived_from_feed(tmp_path, monkeypatch):
    """The service-block boundary is derived, not hardcoded: the first date the
    dominant block switches. 26AU03 (Aug) runs through Sep 6, 26SE07 (Sep)
    starts Sep 7 -> cutoff 20260907."""
    _write_calendar_dates(
        tmp_path,
        [
            # Aug block runs through Sep 6
            ("26AU03-CPBlock-Weekday-11", "20260901", 1),
            ("26AU03-CPBlock-Weekday-11", "20260902", 1),
            ("26AU03-CPBlock-Weekday-11", "20260903", 1),
            ("26AU03-CPBlock-Weekday-11", "20260904", 1),
            # Sep block: Labour Day holiday on Sep 7, then weekdays
            ("26SE07-CPBlock-Holiday1-14", "20260907", 1),
            ("26SE07-CPBlock-Weekday-11", "20260908", 1),
            ("26SE07-CPBlock-Weekday-11", "20260909", 1),
            ("26SE07-CPBlock-Weekday-11", "20260910", 1),
        ],
    )
    monkeypatch.setattr(md.config, "LOCAL_GTFS_DIR", tmp_path)
    md._block_cutoff_cached.cache_clear()
    try:
        assert md.block_cutoff() == "20260907"
        assert md.schedule_block("2026-09-04") == "pre"
        assert md.schedule_block("2026-09-08") == "post"
    finally:
        md._block_cutoff_cached.cache_clear()


def test_block_cutoff_single_block_no_boundary(tmp_path, monkeypatch):
    """A one-block feed has no timetable change -> '' (no boundary)."""
    _write_calendar_dates(
        tmp_path,
        [
            ("26SE07-CPBlock-Weekday-11", "20260908", 1),
            ("26SE07-CPBlock-Weekday-11", "20260909", 1),
        ],
    )
    monkeypatch.setattr(md.config, "LOCAL_GTFS_DIR", tmp_path)
    md._block_cutoff_cached.cache_clear()
    try:
        assert md.block_cutoff() == ""
        assert md.schedule_block("2026-09-08") is None
    finally:
        md._block_cutoff_cached.cache_clear()


def test_block_cutoff_missing_feed_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(md.config, "LOCAL_GTFS_DIR", tmp_path)
    md._block_cutoff_cached.cache_clear()
    try:
        assert md.block_cutoff() == ""
    finally:
        md._block_cutoff_cached.cache_clear()
