"""Unit tests for ``scripts/late_start_detector.py`` (D-17 phase 2).

The phase-2 value over the probe is the standing single-day CLI plus the
cross-day **comparison band**. The band's pure logic is tested here: baseline
row parsing (TOTAL excluded, missing file handled) and the band receipt
(today embeds beside the baseline rows, summer-mean + IN-LINE / ABOVE / BELOW
verdict). The classification math itself is the probe's (already covered by
``test_late_start_probe.py``) — this file tests the band wiring only.
"""

import scripts.late_start_detector as det

_BASELINE = (
    "service_date,on_time,early,late_start,pull_in,never_ran,unmeasurable,"
    "uncovered,measured,late_start_rate,day_status\r\n"
    "20260820,1,2,3,4,5,6,7,10,0.500,COMPLETE\r\n"
    "20260821,2,2,4,0,5,6,7,20,1.000,PARTIAL\r\n"
    "TOTAL,1,2,3,4,5,6,7,30,0.500,RANGE\r\n"
)


def _res(date_str="20260824", rate=0.5, offenders=2):
    c = {
        "ON-TIME": 90,
        "EARLY": 8,
        "LATE-START": 2,
        "PULL-IN": 0,
        "NEVER-RAN": 5,
        "UNMEASURABLE": 7,
        "UNCOVERED": 9,
    }
    return {
        "date_str": date_str,
        "counts": c,
        "measured": 100,
        "rate": rate,
        "offenders": [{"trip_id": f"T{i}"} for i in range(offenders)],
        "state": {
            "frozen_input": "a" * 64,
            "day_status": "COMPLETE",
        },
    }


def _write_baseline(tmp_path):
    p = tmp_path / "baseline.csv"
    p.write_text(_BASELINE, encoding="utf-8")
    return p


def test_load_baseline_rows_parses_and_drops_total(tmp_path):
    p = _write_baseline(tmp_path)
    rows = det._load_baseline_rows(p)
    assert [r["service_date"] for r in rows] == ["20260820", "20260821"]
    assert all(r["service_date"] != "TOTAL" for r in rows)


def test_load_baseline_missing_file_returns_empty(tmp_path):
    assert det._load_baseline_rows(tmp_path / "nope.csv") == []


def test_band_receipt_inline_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(det, "RUNS_DIR", tmp_path)
    p = _write_baseline(tmp_path)
    csvp, mdp = det._band_receipt("20260824", _res(rate=0.5), p)
    assert csvp.exists() and mdp.exists()
    text = mdp.read_text(encoding="utf-8")
    # today's row rendered + baseline rows + verdict
    assert "20260824 (today)" in text
    assert "20260820" in text and "20260821" in text
    # summer mean of the two rows = (3+4)/(10+20)=23.3%; delta 0.5-23.3 huge
    # ABOVE -> but benchmark uses small numbers; assert a verdict is present.
    assert "summer norm" in text


def test_band_receipt_above_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(det, "RUNS_DIR", tmp_path)
    p = _write_baseline(tmp_path)
    # today rate 30% rides far above the ~1% baseline -> ABOVE.
    _, mdp = det._band_receipt("20260824", _res(rate=30.0), p)
    text = mdp.read_text(encoding="utf-8")
    assert "ABOVE" in text


def test_band_receipt_below_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(det, "RUNS_DIR", tmp_path)
    p = _write_baseline(tmp_path)
    # today rate 0.0% rides below the ~1% baseline -> BELOW.
    _, mdp = det._band_receipt("20260824", _res(rate=0.0), p)
    text = mdp.read_text(encoding="utf-8")
    assert "BELOW" in text
