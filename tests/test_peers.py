"""Tests for the /api/peers endpoint (TransLink demo vs MiWay)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_peers_endpoint_shape():
    resp = client.get("/api/peers")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) >= {"translink", "miway", "note"}
    assert data["miway"]["agency"].startswith("MiWay")


def test_peers_translink_demo_numbers():
    """The demo datasets, when present, must satisfy the loader contracts."""
    resp = client.get("/api/peers")
    data = resp.json()
    t = data.get("translink")
    if t is None:
        # Datasets not generated on this checkout; endpoint must still work.
        return
    assert t["published_stop_level"] is True
    assert t["routes"] > 100
    assert t["stops_measured"] > 1000
    assert 0 < t["top10_stop_share"] < 1
    assert 0 < t["multiline_stop_share"] < 1
    assert t["is_estimate"] is False
    assert len(t["top_lines"]) == 5
    assert all(line["boardings"] > 0 for line in t["top_lines"])
    assert len(t["busiest_stops"]) == 5
    assert all(s["boardings"] > 0 for s in t["busiest_stops"])
    # Recovery trend: all four published years, 2019 anchored at 100%, and
    # the headline-year numbers must come from the pinned year only.
    trend = t.get("recovery_trend") or []
    assert [p["year"] for p in trend] == [2019, 2022, 2023, 2024]
    by_year = {p["year"]: p for p in trend}
    assert by_year[2019]["pct_of_2019"] == 100.0
    assert by_year[2024]["pct_of_2019"] < 100  # still below baseline
    assert by_year[2024]["weekday_boardings"] == t["total_boardings"]
    # Journey stats: TransLink's boardings-per-journey pair, with the
    # corroborating 2020 weekday pair cited.
    js = t.get("journey_stats") or {}
    assert 1.5 < js["boardings_per_journey"] < 1.8
    assert js["journeys_2024"] == 240_900_000
    assert "1.73" in js["corroborating_pair"]


def test_peers_miway_honest_unavailability():
    """MiWay's stop-level fields must say 'unavailable', never fake data."""
    resp = client.get("/api/peers")
    data = resp.json()
    m = data["miway"]
    assert m["published_stop_level"] is False
    assert m["stops_measured"] is None
    assert m["routes_published"] > 0
    assert m["routes_estimated"] > 0
    assert m["routes_published"] < m["routes"]  # most routes are estimates
    assert m["stop_load_observations"] >= 0
    assert (
        "not published" in data["note"].lower() or "collector" in data["note"].lower()
    )
    # Journey count for MiWay: null with the identifiability reason attached —
    # the whole point is that it's not merely unpublished, but underivable.
    mjs = m.get("journey_stats") or {}
    assert mjs["boardings_per_journey"] is None
    assert "deriv" in mjs["source"].lower()


def test_peers_miway_annual_series_honest_gaps():
    """The annual series must show 2019 as unpublished, not imputed."""
    resp = client.get("/api/peers")
    data = resp.json()
    series = data["miway_annual_series"]
    by_year = {p["year"]: p for p in series}
    assert by_year[2019]["boardings_millions"] is None
    assert "published" in by_year[2019]["source"].lower()
    assert by_year[2024]["boardings_millions"] == 58.4
    # The metric label must travel with each point, because it differs
    # between source documents (boardings vs revenue ridership).
    assert all(p["metric"] or p["boardings_millions"] is None for p in series)
    assert all(p["source"] for p in series)
    assert data["trend_note"]  # the assembling-four-documents story is told


def test_peers_translink_missing_degrades_cleanly(monkeypatch, tmp_path):
    """Without the demo datasets the endpoint still serves MiWay's side."""
    from app.routers import peers as peers_mod

    monkeypatch.setattr(peers_mod, "_TL_RIDERSHIP", tmp_path / "no.csv")
    monkeypatch.setattr(peers_mod, "_TL_STOPS", tmp_path / "no2.csv")
    resp = client.get("/api/peers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["translink"] is None
    assert data["miway"]["agency"].startswith("MiWay")
