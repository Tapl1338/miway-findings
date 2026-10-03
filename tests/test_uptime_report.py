"""Hermetic tests for uptime_report.py — SLO bucketing, % math, cause labels.

No real data files touched: a synthetic obs_lateness.csv is written to tmp and
passed directly to build_report(). All months used are fully in the past so
days_elapsed == calendar length.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "uptime_report.py"
spec = importlib.util.spec_from_file_location("uptime_report", SCRIPT)
uptime_report = importlib.util.module_from_spec(spec)
sys.modules["uptime_report"] = uptime_report
spec.loader.exec_module(uptime_report)


def _write_obs(tmp_path: Path, per_day: dict[str, int], undated: int = 0) -> Path:
    p = tmp_path / "obs_lateness.csv"
    lines = [
        "route_short_name,stop_id,dep_time_min,lateness_minutes,horizon_minutes,date"
    ]
    for day, n in per_day.items():
        for i in range(n):
            lines.append(f"10,2405,{300 + i},1.0,-30.0,{day}")
    lines.extend("10,2405,300,1.0,-30.0," for _ in range(undated))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_bucketing_full_partial_down(tmp_path):
    obs = _write_obs(
        tmp_path,
        {"2026-05-01": 150_000, "2026-05-02": 120_000, "2026-05-03": 500},
    )
    report = uptime_report.build_report("2026-05", obs)
    # 31-day month: 2 FULL, 1 PARTIAL, 28 DOWN (absent = zero rows).
    assert "**Coverage: 6.5%** (2/31 FULL days; 1 PARTIAL; 28 DOWN)" in report
    assert "| 2026-05-01 | 150,000 | FULL |" in report
    assert "| 2026-05-03 | 500 | PARTIAL |" in report
    assert "| 2026-05-04 | 0 | DOWN |" in report


def test_slo_threshold_boundary(tmp_path):
    # Exactly at the threshold counts as FULL; one row below is PARTIAL.
    obs = _write_obs(tmp_path, {"2026-05-01": uptime_report.SLO_FULL_DAY_ROWS})
    report = uptime_report.build_report("2026-05", obs)
    assert "| 2026-05-01 | 100,000 | FULL |" in report


def test_undated_rows_counted_outside_slo(tmp_path):
    obs = _write_obs(tmp_path, {"2026-05-01": 150_000}, undated=4321)
    report = uptime_report.build_report("2026-05", obs)
    assert "Undated legacy rows" in report and "4,321" in report
    # Undated rows must not inflate the day's count.
    assert "| 2026-05-01 | 150,000 | FULL |" in report


def test_known_cause_labels_appear(tmp_path):
    # Sept 19's documented VPS-cutover cause is attached to that day only.
    obs = _write_obs(tmp_path, {"2026-09-19": 75_977})
    report = uptime_report.build_report("2026-09", obs)
    assert "VPS cutover day" in report
    assert "| 2026-09-19 | 75,977 | PARTIAL | VPS cutover day" in report


def test_from_date_narrows_partial_month(tmp_path):
    # Aug 2026 coverage started Aug 23 (first dated day): --from 2026-08-23
    # must count 9 days, not the full calendar month.
    obs = _write_obs(tmp_path, {"2026-08-01": 150_000, "2026-08-24": 150_000})
    full = uptime_report.build_report("2026-08", obs)
    partial = uptime_report.build_report("2026-08", obs, dt.date(2026, 8, 23))
    assert "(2/31 FULL days" in full  # Aug 1 AND Aug 24 FULL, 29 absent days
    assert "(1/9 FULL days" in partial  # window Aug 23-31: only Aug 24 FULL


def test_month_days_length():
    assert uptime_report.month_days("2026-02")[2] == 28
    assert uptime_report.month_days("2024-02")[2] == 29  # leap year
    assert uptime_report.month_days("2026-09")[2] == 30
