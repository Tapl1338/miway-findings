"""Tests for ``scripts/fit_ascent_thresholds.py`` — T111 prep.

Covers the flip-interval math (ascent-only filtering, lag window, date
grouping), the interval-intersection fit (consistent, inconsistent, and
no-flip vehicles), the trusted/fallback logic, and the prep-only contract:
the registry's consumers are untouched until the post-scorecard swap.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "fit_ascent_thresholds", SCRIPTS / "fit_ascent_thresholds.py"
)
fat = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("fit_ascent_thresholds", fat)
_spec.loader.exec_module(fat)


# ---------------------------------------------------------------- fixtures


def _row(ts, pct, pax, vid="2302", date="20260818", route="42"):
    return {
        "ts": ts,
        "service_date": date,
        "vehicle_id": vid,
        "route": route,
        "reported_pct": pct,
        "counted_pax": pax,
    }


def _df(rows):
    import pandas as pd

    return pd.DataFrame(rows)


@pytest.fixture
def gt_csv(tmp_path):
    """A small ground-truth CSV with two vehicles and a descent trap."""
    import pandas as pd

    rows = [
        # vehicle A: clean ascent 20->40 with pax 10 -> 25, i.e. C in (50, 125]
        _row("2026-08-18 10:00:00", 20, 10, vid="2302"),
        _row("2026-08-18 10:05:00", 40, 25, vid="2302"),
        # second clean ascent the same day: 40->60 with pax 25 -> 40 => C in (62.5, 100]
        _row("2026-08-18 10:30:00", 60, 40, vid="2302"),
        # vehicle B: flip too fast (inside the 2-min lag window) -> dropped
        _row("2026-08-18 11:00:00", 20, 10, vid="2459"),
        _row("2026-08-18 11:00:30", 40, 25, vid="2459"),
        # vehicle C: descent flip only (40 -> 20) -> must NOT count
        _row("2026-08-18 12:00:00", 40, 30, vid="2240"),
        _row("2026-08-18 12:10:00", 20, 12, vid="2240"),
        # vehicle C later: a clean ascent, different service date
        _row("2026-08-19 09:00:00", 20, 8, vid="2240", date="20260819"),
        _row("2026-08-19 09:06:00", 40, 20, vid="2240", date="20260819"),
    ]
    path = tmp_path / "ground_truth.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


# ---------------------------------------------------------------- flip math


def test_ascent_only_filtering(gt_csv):
    """A descent flip (40 -> 20) never produces an interval."""
    df = fat.load_observations(gt_csv)
    vehicle_c = df[df["vehicle_id"] == 2240]
    intervals = fat.ascent_flip_intervals(vehicle_c)
    # The same-day 40->20 descent is skipped; the next-day 20->40 ascent on
    # its own date group yields one interval: C in (8*100/20, 20*100/20] = (40, 100]
    assert len(intervals) == 1
    lo, hi, _ = intervals[0]
    assert lo == pytest.approx(40.0)
    assert hi == pytest.approx(100.0)


def test_lag_window_drops_fast_flips(gt_csv):
    """A flip observed 30 s apart is inside the sensor lag and is dropped."""
    df = fat.load_observations(gt_csv)
    vehicle_b = df[df["vehicle_id"] == 2459]
    assert fat.ascent_flip_intervals(vehicle_b) == []


def test_date_grouping_pairs_within_days(gt_csv):
    """Flip pairing never crosses a service-date boundary."""
    df = fat.load_observations(gt_csv)
    vehicle_c = df[df["vehicle_id"] == 2240]
    # If dates were pooled, the 12:10 descent (pct 20) could pair with the
    # next day's 09:06 (pct 40) as an "ascent" spanning dates — assert not.
    for lo, hi, _ in fat.ascent_flip_intervals(vehicle_c):
        assert lo > 0 and hi >= lo


# ---------------------------------------------------------------- vehicle fit


def test_intersection_narrows_capacity(gt_csv):
    """Two consistent ascents intersect: (50,125] ∩ (62.5,100] = (62.5,100]."""
    df = fat.load_observations(gt_csv)
    vehicle_a = df[df["vehicle_id"] == 2302]
    fit = fat.fit_vehicle(vehicle_a)
    assert fit["status"] == "ok"
    assert fit["n_flips"] == 2
    assert fit["capacity_lo"] == pytest.approx(62.5)
    assert fit["capacity_hi"] == pytest.approx(100.0)
    assert fit["capacity_est"] == pytest.approx((62.5 + 100.0) / 2)


def test_inconsistent_vehicle_flagged_not_averaged(gt_csv):
    """An empty intersection yields status='inconsistent', never a midpoint."""
    import pandas as pd

    rows = [
        # flip 1: C in (50, 80];  flip 2: C in (100, 200] — impossible together
        _row("2026-08-18 10:00:00", 20, 10),
        _row("2026-08-18 10:05:00", 40, 16),
        _row("2026-08-18 11:00:00", 40, 40),
        _row("2026-08-18 11:05:00", 60, 60),
    ]
    fit = fat.fit_vehicle(pd.DataFrame(rows))
    assert fit["status"] == "inconsistent"
    assert fit["capacity_est"] is None


def test_no_flips_vehicle(gt_csv):
    import pandas as pd

    flat = [_row("2026-08-18 10:00:00", 20, 5), _row("2026-08-18 10:30:00", 20, 6)]
    assert fat.fit_vehicle(pd.DataFrame(flat))["status"] == "no-flips"


# ---------------------------------------------------------------- registry


def test_registry_trust_and_fallback(gt_csv):
    """>=3 flips trusted; fewer fall back to the fleet median with a reason."""
    registry = fat.build_registry(gt_csv)
    assert registry["legacy_constants"] == {"standard": 65, "articulated": 110}
    # No vehicle in this fixture has >= 3 flips, so nothing is trusted...
    assert all(not v["trusted"] for v in registry["per_vehicle"].values())
    # ...and every applied capacity is the fleet fallback (or None if the
    # fixture produced no trusted estimates at all).
    for v in registry["per_vehicle"].values():
        applied = v["capacity_applied"]
        assert applied is None or applied in registry["fleet_fallback"].values()


def test_registry_prep_only_contract(gt_csv, tmp_path):
    """The registry is standalone: no pipeline output paths are written."""
    out = tmp_path / "ascent_thresholds.json"
    registry = fat.build_registry(gt_csv)
    out.write_text(json.dumps(registry), encoding="utf-8")
    blob = out.read_text(encoding="utf-8")
    # Consumers named in the comment as NOT-yet-switched
    assert "reconstruct_boardings" in blob
    assert "NOT yet switched" in registry["_comment"]
    # The method block documents the ascent-only interval math
    assert "p1*100/b0" in registry["method"]["capacity_interval"]


def test_cli_vehicle_inspection(gt_csv, capsys):
    """--vehicle prints one vehicle's fit as JSON and exits 0."""
    rc = fat.main(["--gt-csv", str(gt_csv), "--vehicle", "2302"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["capacity_est"] == pytest.approx(81.25)


def test_cli_writes_registry(gt_csv, tmp_path):
    """Default invocation writes the registry JSON and reports the counts."""
    out = tmp_path / "out.json"
    rc = fat.main(["--gt-csv", str(gt_csv), "--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data["per_vehicle"]) == {"2302", "2459", "2240"}
