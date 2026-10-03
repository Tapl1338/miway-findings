"""Regression tests for ``app.main.health`` (the /api/health handler).

Bug (2026-09-02): ``health()``'s ``try:`` had its ``except`` tail lost, so the
module failed to import at all (SyntaxError on the dangling ``}``) and the
backend could not start. Even with the handler restored, the inner
``filter_school_routes(load_feed())`` raises on a feed failure and the handler
must degrade rather than propagate (a health probe must never 500).

These call the handler function directly with a monkeypatched loader -- no GTFS
fetch, no optimizer, fast -- and assert the contract: an exception inside the
loader yields ``status: degraded``, not a raised exception.
"""

import pytest

from app.main import health


@pytest.fixture(autouse=True)
def _restore_health_cache(monkeypatch):
    """Reset the module-level cache so meta/timestamp do not leak between tests."""
    import app.main as m

    monkeypatch.setattr(m, "_health_cache", {"meta": None, "ts": 0.0})


@pytest.mark.parametrize(
    "exc", [RuntimeError("feed fetch failed"), ValueError("bad zip")]
)
def test_health_degrades_when_loader_raises(monkeypatch, exc):
    """The loader blowing up must not propagate out of /api/health.

    Before the fix, this raised out of the handler (the truncated `except`)
    and the health probe returned a 500 -- exactly the failure that made the
    Service Quality page report "Could not load service quality: HTTP 500"
    when the feed was genuinely broken.
    """

    def boom(*_a, **_k):
        raise exc

    monkeypatch.setattr("app.main.filter_school_routes", boom)
    out = health()
    assert out["status"] == "degraded"
    assert out["feed"] is None
    assert out["app"] == "MiWay Transit Optimizer"


def test_health_ok_path_present(monkeypatch):
    """Sanity: with no failure the handler still returns a proper 'ok' shape
    (the feed values are loader-dependent, so only assert the shape)."""
    out = health()
    assert out["status"] in ("ok", "degraded")
    assert "app" in out
    assert "feed" in out


def test_health_feed_vintage_from_feed_info(monkeypatch, tmp_path):
    """A feed_info.txt validity window is surfaced so a user can tell the
    schedule era from feed_info. The header renders an "archived YYYY feed"
    chip when the start year != this year."""
    import app.main as m

    fi = tmp_path / "feed_info.txt"
    fi.write_text(
        "feed_publisher_name,feed_start_date,feed_end_date,feed_version\n"
        "MiWay,20170130,20170402,1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(m.config, "LOCAL_GTFS_DIR", tmp_path)
    v = m._feed_vintage()
    assert v["start_date"] == "2017-01-30"
    assert v["end_date"] == "2017-04-02"
    assert v["version"] == "1"
    # A non-current vintage is the one worth flagging in the UI.
    assert v["start_date"][:4] != str(__import__("datetime").date.today().year)


def test_feed_vintage_missing_file_returns_none(monkeypatch, tmp_path):
    """No feed_info.txt (or malformed) must not raise — vintage is optional."""
    import app.main as m

    monkeypatch.setattr(m.config, "LOCAL_GTFS_DIR", tmp_path)
    assert m._feed_vintage() is None
