"""Tests for ``scripts/backtest_layers_ac.py`` — Sept-7 backtest Layers A & C.

Hermetic: synthetic inputs only, except
``test_committed_artifact_selfconsistent`` which reads the committed
``docs/runs/backtest-sept7-layers-AC.json`` (repo data — guards that the
emitted verdict counts stay consistent with the emitted rows).
"""

from __future__ import annotations

import csv
import importlib
import json
from pathlib import Path

import pytest
from scripts import backtest_layers_ac as bac


# ---------------------------------------------------------------- verdict()
@pytest.mark.parametrize(
    ("band", "x", "expected"),
    [
        ((1.0, 2.0), 1.5, "PASS"),
        ((1.0, 2.0), 1.0, "PASS"),  # band edges are inclusive
        ((1.0, 2.0), 2.0, "PASS"),
        ((1.0, 2.0), 2.5, "FAIL-HIGH"),
        ((1.0, 2.0), 0.5, "FAIL-LOW"),
        ((1.0, 2.0), None, "UNSCOREABLE"),
        (None, 1.5, "UNSCOREABLE"),
    ],
)
def test_verdict_band_logic(band, x, expected):
    assert bac.verdict(band, x) == expected


# -------------------------------------------------------------- earliness()
def _write_obs(path: Path, rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "route_short_name",
                "stop_id",
                "dep_time_min",
                "lateness_minutes",
                "horizon_minutes",
                "date",
            ]
        )
        w.writerows(rows)


def test_earliness_windows_and_am_peak(tmp_path, monkeypatch):
    """W1/W2 windows filter first; AM peak is dep in [420, 540); early = lateness <= -2."""
    obs = tmp_path / "obs_lateness.csv"
    _write_obs(
        obs,
        [
            # W1, AM peak, early
            ["10", "1", 430, -3.0, 2.0, "2026-09-08"],
            # W1, AM peak, NOT early
            ["10", "1", 450, 1.5, 2.0, "2026-09-08"],
            # W1, outside AM peak -> counts for W1 only
            ["10", "1", 700, -5.0, 2.0, "2026-09-09"],
            # W2, AM peak, exactly -2.0 (boundary counts as early)
            ["10", "1", 425, -2.0, 2.0, "2026-09-15"],
            # outside both windows -> excluded entirely
            ["10", "1", 430, -9.0, 2.0, "2026-09-21"],
            ["10", "1", 430, -9.0, 2.0, "2026-09-06"],
        ],
    )
    monkeypatch.setenv("MIWAY_OBS_LATENESS", str(obs))
    importlib.reload(bac)  # OBS is resolved at import time
    try:
        out = bac.earliness()
    finally:
        monkeypatch.undo()
        importlib.reload(bac)  # restore module state for other tests
    assert out["W1"] == {"early_share_pct": 66.67, "n": 3}
    assert out["W1_am"] == {"early_share_pct": 50.0, "n": 2}
    assert out["W2"] == {"early_share_pct": 100.0, "n": 1}
    assert out["W2_am"] == {"early_share_pct": 100.0, "n": 1}


def test_earliness_no_rows_in_window(tmp_path, monkeypatch):
    obs = tmp_path / "obs_lateness.csv"
    _write_obs(obs, [["10", "1", 430, -9.0, 2.0, "2026-01-01"]])
    monkeypatch.setenv("MIWAY_OBS_LATENESS", str(obs))
    importlib.reload(bac)
    try:
        out = bac.earliness()
    finally:
        monkeypatch.undo()
        importlib.reload(bac)
    # n=0 must yield None, never a ZeroDivisionError or a fake 0.0
    assert out["W1"] == {"early_share_pct": None, "n": 0}


# ------------------------------------------------------------- _crowd_row()
def test_crowd_row_match_and_missing(tmp_path):
    p = tmp_path / "crowd.csv"
    p.write_text(
        "route_short_name,period,mean_percentage,n_observations\n"
        "2,late_night,44.8,100\n"
        "109,pm_rush,41.7,50\n",
        encoding="utf-8",
    )
    row = bac._crowd_row(p, "2", "late_night")
    assert row is not None and row["mean_percentage"] == "44.8"
    assert bac._crowd_row(p, "2", "am_rush") is None  # route exists, period doesn't
    assert bac._crowd_row(tmp_path / "nope.csv", "2", "late_night") is None  # no file


# ---------------------------------------------------------- parse_compare()
def test_parse_compare_nan_delta_and_rows(tmp_path, monkeypatch):
    md = tmp_path / "compare.md"
    md.write_text(
        "# harness output\n\n"
        "```\n"
        "from to old new delta m_old m_new pad pad\n"
        "col col col col col col col col col\n"
        "43 109 NaN 1.5 NaN 0.9 0.4 x y\n"
        "109 43 18.65 15.0 -3.65 0.8 0.3 x y\n"
        "```\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bac, "COMPARE", md)
    rows = bac.parse_compare()
    assert set(rows) == {("43", "109"), ("109", "43")}
    # the vintage trap: NaN old-side must parse to None, never a crash
    assert rows[("43", "109")]["delta"] is None
    assert rows[("43", "109")]["realized_old"] is None
    assert rows[("109", "43")]["delta"] == -3.65
    assert rows[("109", "43")]["missed_old"] == 0.8


# -------------------------------------------------- committed artifact check
def test_committed_artifact_selfconsistent():
    p = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "runs"
        / "backtest-sept7-layers-AC.json"
    )
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data["rows"]
    assert len(rows) == 20  # 9 Layer A + 11 Layer C rows
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    assert counts == data["verdict_counts"]
    # the reconciliation against the emailed headline is part of the contract
    assert "0 passed / 4 failed" in data["reconciliation_note"]
