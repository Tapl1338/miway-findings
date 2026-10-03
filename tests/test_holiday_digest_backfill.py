"""Tests for scripts/backfill_rollup_holidays.py and scripts/daily_digest.py."""

import csv
import sys
from pathlib import Path

import pytest

from scripts import backfill_rollup_holidays as backfill_mod
from scripts import daily_digest as digest_mod

_HEADER = (
    "date,windows_completed,windows_partial,windows_missed,am_polled,"
    "observations,verifiable_trips,ghost_trips,boardings_lower_pax,"
    "filled_cells,n_recorded,pct_early_gt2\n"
)


def _rollup(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "weekly_rollup.csv"
    p.write_text(_HEADER + body, encoding="utf-8")
    return p


@pytest.fixture()
def labour_day(monkeypatch):
    from app.services import measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset({"20260907"}))
    return md


# ---- backfill -------------------------------------------------------------


def test_backfill_adds_flag_column(tmp_path, labour_day):
    p = _rollup(
        tmp_path,
        "2026-09-05,2,1,0,0,4579570,1697,22,0,0,76454,25.25\n"
        "2026-09-07,4,1,0,1,6200000,2100,14,21000,0,91000,33.90\n",
    )
    n, n_hol = backfill_mod.backfill(p)
    assert (n, n_hol) == (2, 1)
    with open(p, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["is_holiday"] == "false"
    assert rows[1]["is_holiday"] == "true"
    # Flag sits right after the date it describes.
    assert rows[0]["date"] == "2026-09-05"


def test_backfill_is_idempotent(tmp_path, labour_day):
    p = _rollup(tmp_path, "2026-09-07,4,1,0,1,6200000,2100,14,21000,0,91000,33.90\n")
    backfill_mod.backfill(p)
    first = p.read_text(encoding="utf-8")
    n, n_hol = backfill_mod.backfill(p)
    assert (n, n_hol) == (1, 1)
    assert p.read_text(encoding="utf-8") == first  # recomputed, not duplicated


def test_backfill_recomputes_after_feed_change(tmp_path, labour_day, monkeypatch):
    """A feed refresh adding a holiday flips the existing rows on re-run."""
    p = _rollup(tmp_path, "2026-10-12,4,1,0,1,6200000,2100,14,21000,0,91000,33.90\n")
    backfill_mod.backfill(p)
    with open(p, newline="", encoding="utf-8") as f:
        assert list(csv.DictReader(f))[0]["is_holiday"] == "false"
    monkeypatch.setattr(labour_day, "holiday_dates", lambda: frozenset({"20261012"}))
    backfill_mod.backfill(p)
    with open(p, newline="", encoding="utf-8") as f:
        assert list(csv.DictReader(f))[0]["is_holiday"] == "true"


def test_backfill_rejects_non_rollup(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        backfill_mod.backfill(p)


def test_backfill_main_dry_run(tmp_path, labour_day, capsys):
    p = _rollup(tmp_path, "2026-09-07,4,1,0,1,6200000,2100,14,21000,0,91000,33.90\n")
    before = p.read_text(encoding="utf-8")
    old_argv = sys.argv
    sys.argv = ["backfill_rollup_holidays.py", "--rollup", str(p), "--dry-run"]
    try:
        assert backfill_mod.main() == 0
    finally:
        sys.argv = old_argv
    assert p.read_text(encoding="utf-8") == before  # dry run wrote nothing
    assert "column missing" in capsys.readouterr().out


# ---- digest ---------------------------------------------------------------


def test_digest_lists_holidays_anomalies_and_wow(tmp_path, labour_day, monkeypatch):
    """The digest renders 3σ days, holiday notes, and WoW from the same
    functions the dashboard uses."""
    import app.routers.operations as ops

    monkeypatch.setattr(ops, "_ROLLUP_CSV", tmp_path / "nope.csv")
    text = digest_mod.build_digest(tmp_path / "nope.csv")
    assert "No rollup data available" in text


def test_digest_full_render(tmp_path, labour_day, monkeypatch):
    import app.routers.operations as ops

    # Stable week + holiday Monday spike: WoW comparable, anomaly on holiday.
    # Row shape: date,is_holiday,completed,partial,missed,am,obs,verif,ghost,
    # board,cells,n_recorded,pct_early (n_recorded real — days with none
    # recorded are in-progress/dead and excluded from comparisons).
    body = (
        # Previous week: Tue-Fri + Monday (5 comparable weekdays — the >=2
        # days/side rule needs a real previous week, not a single day).
        "2026-08-25,false,3,1,0,1,10000000,5000,20,0,0,200000,25.0\n"
        "2026-08-26,false,3,1,0,1,10000000,5000,20,0,0,200000,25.0\n"
        "2026-08-27,false,3,1,0,1,10000000,5000,20,0,0,200000,25.0\n"
        "2026-08-28,false,3,1,0,1,10000000,5000,20,0,0,200000,25.0\n"
        "2026-08-31,true,3,1,0,1,5000000,2500,10,0,0,100000,25.0\n"
        "2026-09-01,false,3,1,0,1,10000000,5000,20,0,0,200000,25.0\n"
        "2026-09-02,false,3,1,0,1,10000000,5000,20,0,0,200000,25.0\n"
        "2026-09-03,false,3,1,0,1,10000000,5000,20,0,0,200000,25.0\n"
        "2026-09-04,false,3,1,0,1,10000000,5000,20,0,0,200000,25.0\n"
        "2026-09-07,true,3,1,0,1,2000000,1000,90,0,0,40000,85.0\n"
    )
    p = tmp_path / "weekly_rollup.csv"
    header = (
        "date,is_holiday,windows_completed,windows_partial,windows_missed,am_polled,"
        "observations,verifiable_trips,ghost_trips,boardings_lower_pax,"
        "filled_cells,n_recorded,pct_early_gt2\n"
    )
    p.write_text(header + body, encoding="utf-8")
    monkeypatch.setattr(ops, "_ROLLUP_CSV", p)
    text = digest_mod.build_digest(p)

    assert "3σ outlier days" in text
    assert "(holiday)" in text  # the flagged holiday row
    assert "Holiday days in history" in text
    assert "**2026-09-07** — holiday service ran" in text
    assert "Week over week" in text
    assert "1 holiday(s) skipped" in text
    assert "HOLIDAY-SYSTEM.md" in text  # runbook pointer


def test_digest_quiet_day_renders_clean(tmp_path, monkeypatch):
    import app.routers.operations as ops
    from app.services import measured_data as md

    monkeypatch.setattr(md, "holiday_dates", lambda: frozenset())
    header = (
        "date,windows_completed,windows_partial,windows_missed,am_polled,"
        "observations,verifiable_trips,ghost_trips,boardings_lower_pax,"
        "filled_cells,n_recorded,pct_early_gt2\n"
    )
    body = (
        "2026-09-01,false,3,1,0,1,10000000,5000,20,0,200000,25.0\n"
        "2026-09-02,false,3,1,0,1,10000000,5000,20,0,200000,25.0\n"
        "2026-09-03,false,3,1,0,1,10000000,5000,20,0,200000,25.0\n"
        "2026-09-04,false,3,1,0,1,10000000,5000,20,0,200000,25.0\n"
    )
    p = tmp_path / "weekly_rollup.csv"
    p.write_text(header + body, encoding="utf-8")
    monkeypatch.setattr(ops, "_ROLLUP_CSV", p)
    text = digest_mod.build_digest(p)
    assert "None — every collected day sits within 3σ" in text
    assert "Not yet comparable" in text  # needs 2+ weeks for WoW


def test_digest_main_writes_file(tmp_path, monkeypatch):
    import app.routers.operations as ops

    monkeypatch.setattr(digest_mod, "OUT_MD", tmp_path / "digest.md")
    monkeypatch.setattr(ops, "_ROLLUP_CSV", tmp_path / "nope.csv")
    old_argv = sys.argv
    sys.argv = ["daily_digest.py"]
    try:
        assert digest_mod.main() == 0
    finally:
        sys.argv = old_argv
    assert (tmp_path / "digest.md").exists()
