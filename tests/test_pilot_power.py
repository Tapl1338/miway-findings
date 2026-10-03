"""Unit tests for scripts/pilot_power.py (Monte Carlo pilot sample sizes)."""

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scripts import pilot_power as pp
from scripts.pilot_power import (
    after_population_rescue,
    after_population_shift,
    power_curve,
    realized_population,
)


def _events_df() -> pd.DataFrame:
    """Meadowvale-like events: 3 arrivals of route 10, 4 departures of 43."""
    return pd.DataFrame(
        {
            "route": ["10", "10", "10", "43", "43", "43", "43"],
            "dep_sec": [
                8 * 3600 + 5 * 60,
                8 * 3600 + 35 * 60,
                9 * 3600 + 35 * 60,
                8 * 3600,
                8 * 3600 + 30 * 60,
                9 * 3600,
                9 * 3600 + 30 * 60,
            ],
            "platform": ["P1", "P1", "P1", "P2", "P2", "P2", "P2"],
        }
    )


def test_realized_population_waits_and_misses():
    events = _events_df()
    rng = np.random.default_rng(7)
    pools, fallback = {}, np.array([0.0])  # no lateness: realized == scheduled
    routes, waits, missed = realized_population(
        events,
        pools,
        fallback,
        rng,
        iterations=3,
        to_route="43",
        buffer_min=2.0,
        horizon_min=60.0,
    )
    # 3 arrivals x 3 iterations
    assert len(waits) == 9
    assert set(routes) == {"10"}
    # 08:05 -> 08:30 (23 min net of buffer), 08:35 -> 09:00 (23), 09:35 -> miss
    assert missed.sum() == 3
    assert set(np.round(waits[~missed.astype(bool)], 1)) == {23.0}
    assert len(pools) == 0  # untouched input


def test_realized_population_no_to_route_fails():
    events = _events_df()
    rng = np.random.default_rng(1)
    with pytest.raises(SystemExit) as exc:
        realized_population(
            events,
            {},
            np.array([0.0]),
            rng,
            iterations=1,
            to_route="99",
            buffer_min=2.0,
            horizon_min=60.0,
        )
    assert "no departures" in str(exc.value)


def test_rescue_drops_share_by_delta():
    rng = np.random.default_rng(11)
    n = 4000
    waits = np.full(n, 15.0)
    missed = np.zeros(n, dtype=int)
    missed[:2000] = 1  # 50% miss rate
    after_waits, after_missed = after_population_rescue(
        waits, missed, delta_pts=15.0, rng=rng
    )
    # 50% -> 35%: q = 0.15/0.50 = 0.30, so ~30% of misses rescued.
    assert abs(after_missed.mean() - 0.35) < 0.02
    assert abs(after_missed.sum() - 1400) < 60  # ~70% of the 2000 misses remain
    # Rescued misses carry a wait (15.0), matching the successful population.
    assert float(after_waits[~after_missed.astype(bool)].mean()) == 15.0
    # Deterministic for a fixed seed.
    a2, m2 = after_population_rescue(
        waits, missed, delta_pts=15.0, rng=np.random.default_rng(11)
    )
    assert np.array_equal(after_waits, a2) and np.array_equal(after_missed, m2)


def test_shift_shortens_successful_waits_floored_at_zero():
    waits = np.array([10.0, 4.0, 2.0, 30.0])
    missed = np.array([0, 0, 1, 0])  # the 2.0 row is a miss: untouched
    out = after_population_shift(waits, missed, delta_min=3.0)
    assert np.array_equal(out, [7.0, 1.0, 2.0, 27.0])
    out2 = after_population_shift(np.array([1.0]), np.array([0]), 3.0)
    assert out2[0] == 0.0  # floored


def test_power_curve_detects_large_effect_and_controls_fp():
    rng = np.random.default_rng(3)
    before_missed = rng.random(20000) < 0.50
    before_waits = rng.normal(10, 3, 20000)
    after_missed = rng.random(20000) < 0.20
    after_waits = rng.normal(7, 3, 20000)
    curve = power_curve(
        before_waits,
        before_missed.astype(int),
        after_waits,
        after_missed.astype(int),
        n_grid=[100, 300],
        experiments=80,
        seed=5,
    )
    for row in curve:
        assert row["power_share"] > 0.9
        assert row["power_mean"] > 0.9
        assert row["fp_share"] < 0.15  # null control near 5%


def test_z_and_welch_identity():
    assert pp._z_share(10, 100, 10, 100) == 0.0
    a = np.array([1.0, 2.0, 3.0])
    assert pp._welch(a, a.copy()) == 0.0


def _minimal_gtfs_zip(path: Path) -> Path:
    """A GTFS zip just rich enough for load_events(service_date=...)."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "stops.txt",
            "stop_id,stop_name\nP1,Meadowvale Town Centre Bus Terminal Platform 1\n",
        )
        zf.writestr("routes.txt", "route_id,route_short_name\nR10,10\nR43,43\n")
        zf.writestr(
            "trips.txt",
            "trip_id,route_id,service_id\n"
            "t10a,R10,S1\nt10b,R10,S1\nt43a,R43,S1\nt43b,R43,S1\n",
        )
        zf.writestr(
            "stop_times.txt",
            "stop_id,trip_id,departure_time\n"
            "P1,t10a,08:05:00\nP1,t10b,08:35:00\n"
            "P1,t43a,08:00:00\nP1,t43b,08:30:00\n",
        )
        zf.writestr(
            "calendar_dates.txt", "service_id,date,exception_type\nS1,20260818,1\n"
        )
    return path


def test_main_smoke_on_synthetic_feed(tmp_path):
    feed = _minimal_gtfs_zip(tmp_path / "feed.zip")
    obs = tmp_path / "obs.csv"
    obs.write_text(
        "route_short_name,lateness_minutes,horizon_minutes\n", encoding="utf-8"
    )
    out = tmp_path / "power.md"
    pp.main(
        [
            "--feed-zip",
            str(feed),
            "--obs",
            str(obs),
            "--service-date",
            "2026-08-18",
            "--to-route",
            "43",
            "--n-grid",
            "5,10",
            "--experiments",
            "10",
            "--iterations",
            "2",
            "--seed",
            "1",
            "--out",
            str(out),
        ]
    )
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "## Verdict" in text
    assert "missed-transfer share" in text
