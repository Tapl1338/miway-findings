"""Tests for the ``_lateness`` and ``_boardings`` endpoint bodies.

These call the unwrapped functions (``__wrapped__``) with synthetic CSVs so
the fast suite covers the summary math without the collector's live data and
without the mtime cache leaking state between tests (the cache keys on the
*real* CSV's stat, not the monkeypatched path). Cache-key behavior itself is
covered in ``test_service_quality_cache.py``.
"""

from __future__ import annotations

from app.routers import service_quality as sq


# ---- _lateness ----------------------------------------------------------------


def test_lateness_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(sq, "_LATENESS_CSV", tmp_path / "nope.csv", raising=False)
    assert sq._lateness.__wrapped__() == {"available": False}


def test_lateness_body_computes_stats(monkeypatch, tmp_path):
    path = tmp_path / "obs_lateness.csv"
    path.write_text(
        "route_short_name,lateness_minutes,horizon_minutes\n"
        "35,1.0,0\n"
        "35,-1.0,-1\n"
        "10,3.0,0\n"
        "10,99.0,0\n"
        "35,2.0,5\n"  # future forecast → filtered out by actuals gate
    )
    monkeypatch.setattr(sq, "_LATENESS_CSV", path, raising=False)
    out = sq._lateness.__wrapped__()
    assert out["available"] is True
    assert out["n_observations"] == 4
    # on-time = |lateness| <= 2.0 → rows 1.0 and -1.0; late = > 2.0 → 3.0, 99.0
    assert out["pct_on_time"] == 50.0
    assert out["pct_late"] == 50.0
    assert out["pct_early"] == 0.0
    assert out["routes_covered"] == 2
    # No route reaches the 20-observation floor → per-route list is empty.
    # (Regression: this used to crash on NaN rows from an empty stats frame.)
    assert out["top_early_routes"] == []


# ---- _boardings -----------------------------------------------------------------


def test_boardings_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(sq, "_BOARDINGS_CSV", tmp_path / "nope.csv", raising=False)
    assert sq._boardings.__wrapped__() == {"available": False}


def test_boardings_body_uses_published_fallback(monkeypatch, tmp_path):
    boardings = tmp_path / "boardings_routes.csv"
    boardings.write_text(
        "route_short_name,period,boardings_lower_pax,n_bus_obs_with_pct\n"
        "35,am_rush,120.0,50\n"
        "10,midday,0.0,3\n"  # zero estimate → published fallback path
    )
    published = tmp_path / "ridership.csv"
    published.write_text("route_short_name,boardings\n10,900\n")
    monkeypatch.setattr(sq, "_BOARDINGS_CSV", boardings, raising=False)
    monkeypatch.setattr(sq, "_PUBLISHED_RIDERSHIP_CSV", published, raising=False)
    out = sq._boardings.__wrapped__()
    assert out["available"] is True
    midday = {r["route_short_name"]: r for r in out["periods"]["midday"]}
    am = {r["route_short_name"]: r for r in out["periods"]["am_rush"]}
    assert am["35"]["boardings_lower_pax"] == 120.0
    assert am["35"]["source"] == "live"
    # zero live estimate + published total → period-share fallback
    assert midday["10"]["boardings_lower_pax"] == round(900 * 0.28)
    assert midday["10"]["source"] == "published"


def test_boardings_daily_rows_aggregate_to_one_row_per_route(monkeypatch, tmp_path):
    """Daily CSV rows for the same route must collapse to ONE row per period.

    Regression: the old iterrows loop emitted a row per *day*, so a route
    with several zero-live days repeated with the full published fallback
    each time (duplicate routes in the dashboard table + duplicate React
    keys). Boardings sum across days; n_trips sums; coverage averages.
    """
    boardings = tmp_path / "boardings_routes.csv"
    boardings.write_text(
        "route_short_name,period,n_trips,boardings_lower_pax,coverage_pct,n_bus_obs_with_pct\n"
        "66,off,9,0.0,100.0,0\n"
        "66,off,18,0.0,80.0,0\n"  # second day, still zero live → published
        "10,off,5,40.0,90.0,4\n"
    )
    published = tmp_path / "ridership.csv"
    published.write_text("route_short_name,boardings\n66,1000\n")
    monkeypatch.setattr(sq, "_BOARDINGS_CSV", boardings, raising=False)
    monkeypatch.setattr(sq, "_PUBLISHED_RIDERSHIP_CSV", published, raising=False)
    out = sq._boardings.__wrapped__()
    rows = out["periods"]["off"]
    assert [r["route_short_name"] for r in rows].count("66") == 1
    r66 = next(r for r in rows if r["route_short_name"] == "66")
    assert r66["source"] == "published"
    assert r66["boardings_lower_pax"] == round(1000 * 0.12)  # "off" period share
    assert r66["n_trips"] == 27
    assert r66["coverage_pct"] == 90.0
    # live route unaffected, still live-sourced
    r10 = next(r for r in rows if r["route_short_name"] == "10")
    assert r10["boardings_lower_pax"] == 40.0
    assert r10["source"] == "live"
