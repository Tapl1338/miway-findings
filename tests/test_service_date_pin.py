"""T13 guard tests: MIWAY_PINNED_SERVICE_DATE overrides the heuristic and a
bad pin fails loudly (REDFLAG S12 -- silent 26AU03/26SE07 block flips)."""

import pandas as pd
import pytest
from app import transfer_sync as ts


@pytest.fixture(autouse=True)
def _fresh_feed_cache():
    """Clear the lru_cache around every test in this module.

    ``_prepare_feed_uncached`` caches on (service_day, headway) only — its
    key does not include the config it reads — so an entry an earlier test
    module computed under a monkeypatched ``LOCAL_GTFS_DIR`` would be served
    here as a cache hit and the pin guard would never even run (seen live:
    ``test_api.py`` before this module made both feed-heavy tests pass alone
    but fail in the full suite). Clearing before *and* after makes the
    module order-independent.
    """
    ts._prepare_feed_uncached.cache_clear()
    yield
    ts._prepare_feed_uncached.cache_clear()


def _cal() -> pd.DataFrame:
    rows = []
    for d in ("20260805", "20260806"):
        rows.append({"service_id": "26AU03_WD", "date": d, "exception_type": "1"})
    for d in ("20260907", "20260908"):
        rows.append({"service_id": "26SE07_WD", "date": d, "exception_type": "1"})
    return pd.DataFrame(rows)


def test_pin_env_overrides_heuristic(monkeypatch):
    monkeypatch.setenv(ts.PINNED_SERVICE_DATE_ENV, "20260908")
    assert ts._pick_service_date(_cal(), "weekday") == "20260908"
    assert ts.LAST_PICKED_SERVICE_DATE == "20260908"


def test_pin_unknown_date_raises(monkeypatch):
    monkeypatch.setenv(ts.PINNED_SERVICE_DATE_ENV, "19990101")
    with pytest.raises(ValueError, match="MIWAY_PINNED_SERVICE_DATE"):
        ts._pick_service_date(_cal(), "weekday")


def test_heuristic_unchanged_without_pin(monkeypatch):
    monkeypatch.delenv(ts.PINNED_SERVICE_DATE_ENV, raising=False)
    # Both blocks tie on per-date count; earliest-date tiebreak wins.
    assert ts._pick_service_date(_cal(), "weekday") == "20260805"
    assert ts.LAST_PICKED_SERVICE_DATE == "20260805"


def test_empty_calendar_clears_last_picked(monkeypatch):
    monkeypatch.delenv(ts.PINNED_SERVICE_DATE_ENV, raising=False)
    assert (
        ts._pick_service_date(
            pd.DataFrame(columns=["service_id", "date", "exception_type"]), "weekday"
        )
        is None
    )
    assert ts.LAST_PICKED_SERVICE_DATE is None


def test_pinned_holiday_date_fails_loudly_not_silent_full_feed(tmp_path, monkeypatch):
    """Labour Day 2026-09-07 (a Monday) pinned with service_day='weekday'
    has legitimately sparse trip coverage. Before the guard, prepare_feed
    fell through to 'use the full merged feed' — 28k trips mixing weekday,
    Saturday, and Sunday blocks — silently corrupting any pinned rerun.
    A pin is an operator assertion: sparse coverage must fail loudly."""
    monkeypatch.setenv(ts.PINNED_SERVICE_DATE_ENV, "20260907")
    # The real bundled feed has the sparse holiday date and no calendar.txt,
    # so the guard must fire before the full-feed fallback.
    with pytest.raises(ValueError, match="refusing to silently fall back"):
        ts._prepare_feed_uncached("weekday", ts.config.HIGH_FREQ_HEADWAY)
    ts._prepare_feed_uncached.cache_clear()


def test_pinned_post_block_weekday_filters_cleanly(monkeypatch):
    """Pinning Sept 8 (first 26SE07 weekday) must yield exactly the new
    block's services — the core post-boundary rerun path."""
    monkeypatch.setenv(ts.PINNED_SERVICE_DATE_ENV, "20260908")
    try:
        _routes, trips, _stop_times, _stops = ts._prepare_feed_uncached(
            "weekday", ts.config.HIGH_FREQ_HEADWAY
        )
        assert ts.LAST_PICKED_SERVICE_DATE == "20260908"
        assert set(trips["service_id"].unique()) == {
            "26SE07-CPBlock-Weekday-11",
            "26SE07-MABlock-Weekday-21",
        }
    finally:
        ts._prepare_feed_uncached.cache_clear()
