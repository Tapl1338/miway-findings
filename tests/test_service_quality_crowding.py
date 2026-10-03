"""Tests for the crowding ranking helper in the service-quality router.

The ``periods`` payload must rank routes by how crowded they are (not by how
well-polled they are): ``crowded_share_pct`` descending, tie-broken by
observation count, with an under-sampled floor.
"""

import pandas as pd
from app.routers.service_quality import _CROWD_MIN_OBS, _rank_crowding

_BASE = [
    "route_short_name",
    "n_observations",
    "crowded_share_pct",
    "mean_percentage",
    "p90_percentage",
]

_EXTRA = ["n_crowded", "n_big", "n_small", "n_empty", "n_no_data"]


def _df(rows, period="am rush"):
    return pd.DataFrame(rows, columns=_BASE + _EXTRA).assign(period=period)


def test_ranked_by_crowding_not_by_poll_count():
    # Route 10 has far more polls but is barely crowded; route 40 has far fewer
    # polls but a high crowded share. The ranked list must lead with route 40.
    df = _df(
        [
            {
                "route_short_name": "10",
                "n_observations": 90_000,
                "crowded_share_pct": 6.0,
            },
            {
                "route_short_name": "40",
                "n_observations": 5_000,
                "crowded_share_pct": 61.0,
            },
            {
                "route_short_name": "17",
                "n_observations": 7_000,
                "crowded_share_pct": 30.0,
            },
        ]
    )
    out = _rank_crowding(df, _BASE, [])
    ranked = [r["route_short_name"] for r in out["am rush"]]
    assert ranked == ["40", "17", "10"]


def test_under_sampled_routes_excluded_but_sparse_period_falls_back():
    # A route with a tiny sample but a huge crowded share must not top the list
    # when well-polled routes exist.
    df = _df(
        [
            {
                "route_short_name": "2",
                "n_observations": 60,
                "crowded_share_pct": 99.0,
            },
            {
                "route_short_name": "5",
                "n_observations": 8_000,
                "crowded_share_pct": 55.0,
            },
        ],
        period="pm rush",
    )
    out = _rank_crowding(df, _BASE, [])
    assert [r["route_short_name"] for r in out["pm rush"]] == ["5"]

    # When every route in a period is under-sampled, fall back to listing them
    # rather than an empty list.
    df_all_tiny = _df(
        [
            {
                "route_short_name": "11",
                "n_observations": 10,
                "crowded_share_pct": 40.0,
            },
            {
                "route_short_name": "12",
                "n_observations": 5,
                "crowded_share_pct": 75.0,
            },
        ],
        period="midday",
    )
    out2 = _rank_crowding(df_all_tiny, _BASE, [])
    assert [r["route_short_name"] for r in out2["midday"]] == ["12", "11"]


def test_floor_constant_used():
    assert _CROWD_MIN_OBS > 0


# ---- _crowding body via synthetic CSV (merged from the former
# test_service_quality_coverage.py; _rank_crowding internals are covered above)


def test_crowding_body_ranks_by_crowded_share(monkeypatch, tmp_path):
    from app.routers import service_quality as sq

    path = tmp_path / "occupancy_stats.csv"
    path.write_text(
        "route_short_name,period,n_observations,crowded_share_pct,"
        "mean_percentage,p90_percentage\n"
        "35,am_rush,2000,41.0,55.0,80.0\n"
        "10,am_rush,2000,63.0,60.0,88.0\n"
        "1,am_rush,10,99.0,90.0,95.0\n"  # under-sampled → dropped
        "2,pm_rush,5,50.0,50.0,60.0\n"  # sparse period → falls back, kept
    )
    monkeypatch.setattr(sq, "_OCCUPANCY_CSV", path, raising=False)
    # _crowding is wrapped in _mtime_cached whose cache key closes over the
    # ORIGINAL _OCCUPANCY_CSV path, so a warmed cache (test_api hits the real
    # endpoint first) would serve live data regardless of the monkeypatch.
    # Call the undecorated function to test the body in isolation.
    out = sq._crowding.__wrapped__()
    assert out["available"] is True
    am = out["periods"]["am_rush"]
    assert am[0]["route_short_name"] == "10"  # 63% > 41%
    assert all(r["route_short_name"] != "1" for r in am)
    assert out["periods"]["pm_rush"][0]["route_short_name"] == "2"


def test_uncalibrated_nan_becomes_null_not_nan():
    # Playtest find (2026-09-07): routes without ground-truth calibration carry
    # NaN in the calibrated columns; starlette's JSON encoder rejects NaN, so
    # the whole /api/service-quality endpoint 500ed. The ranked records must
    # carry None, and the payload must be JSON-serializable end to end.
    import json

    df = pd.DataFrame(
        [
            {
                **{c: v for c, v in zip(_BASE, ["108", 12_000, 19.5, 41.7, 80.0])},
                "period": "am rush",
                "mean_pax_raw": 27.1,
                "mean_pax_calibrated": float("nan"),
                "p90_pax_calibrated": float("nan"),
                "calibrated": False,
            },
            {
                **{c: v for c, v in zip(_BASE, ["103", 38_000, 10.7, 34.3, 100.0])},
                "period": "am rush",
                "mean_pax_raw": 22.5,
                "mean_pax_calibrated": 17.4,
                "p90_pax_calibrated": 20.0,
                "calibrated": True,
            },
        ]
    )
    out = _rank_crowding(
        df,
        [
            *_BASE,
            "mean_pax_raw",
            "mean_pax_calibrated",
            "p90_pax_calibrated",
            "calibrated",
        ],
        ["mean_pax_raw", "mean_pax_calibrated", "p90_pax_calibrated", "calibrated"],
    )
    rows = {r["route_short_name"]: r for r in out["am rush"]}
    assert rows["108"]["mean_pax_calibrated"] is None
    assert rows["103"]["mean_pax_calibrated"] == 17.4
    json.dumps(out)  # must not raise
