"""T109: scoreboard-weighted freshness escalation in app.data_vintage.

The escalation model: each vintage lane carries a class (live / derived /
reference) that sets its age budgets and weight. A live lane escalates in
hours (a quiet lateness CSV is the Sept-10 outage class), derived lanes in
days (the analysis chain lags by design), reference lanes never by age.
The summary sorts flagged lanes by weight-then-severity — lane importance
outranks raw badness, matching what the dashboard's headline surfaces
actually depend on.
"""

from __future__ import annotations

from app import data_vintage as dv


def _entry(age_minutes: int | None, *, exists: bool = True) -> dict:
    return {
        "file": "x.csv",
        "source": "test",
        "mtime": "2026-09-16T00:00:00Z",
        "age_minutes": age_minutes,
        "exists": exists,
    }


def test_lane_classes_cover_every_real_lane():
    """Every lane vintages() emits must have a class — a typo'd key would
    silently default to `reference` and never escalate."""
    for lane in dv._LANE_CLASSES:
        assert lane in {
            "lateness",
            "occupancy",
            "boardings",
            "ghosts",
            "weekly_rollup",
            "peak_report",
            "realized_waits",
            "ride_speeds",
            "ground_truth",
            "ridership",
        }


def test_live_lane_escalates_in_hours():
    # Budgets clear the designed overnight gap (~06:00-24:00 windows): the
    # normal 6h nightly quiet stays ok; a missed morning warns; a Sept-10-class
    # outage (~10h) is stale; a full silent day+ is critical.
    assert dv._severity("lateness", _entry(6 * 60)) == "ok"
    assert dv._severity("lateness", _entry(9 * 60)) == "warn"
    assert dv._severity("lateness", _entry(15 * 60)) == "stale"
    assert dv._severity("lateness", _entry(27 * 60)) == "critical"


def test_derived_lane_tolerates_one_day():
    # The analysis chain lags by design; ~1 day is fine, 3+ days is the
    # missed-morning-runs class.
    assert dv._severity("occupancy", _entry(20 * 60)) == "ok"
    assert dv._severity("occupancy", _entry(30 * 60)) == "warn"
    assert dv._severity("occupancy", _entry(60 * 60)) == "stale"
    assert dv._severity("occupancy", _entry(80 * 60)) == "critical"


def test_reference_lane_never_escalates_by_age():
    assert dv._severity("ride_speeds", _entry(500_000 * 60)) == "ok"


def test_missing_file_is_critical_for_live_and_derived_only():
    assert dv._severity("lateness", _entry(None, exists=False)) == "critical"
    assert dv._severity("ghosts", _entry(None, exists=False)) == "critical"
    assert dv._severity("ridership", _entry(None, exists=False)) == "warn"


def test_age_of_none_is_ok_not_crash():
    assert dv._severity("lateness", _entry(None)) == "ok"


def test_escalate_summary_ranks_weight_over_severity():
    vins = {
        "lateness": _entry(30 * 60),  # live, stale   (weight 3)
        "occupancy": _entry(80 * 60),  # derived, critical (weight 2)
        "ridership": _entry(0),  # reference, ok — not flagged
        "generated_at": "2026-09-16T00:00:00Z",  # non-lane key, skipped
    }
    esc = dv._escalate(vins)
    assert vins["lateness"]["lane_class"] == "live"
    assert vins["occupancy"]["severity"] == "critical"
    assert esc["worst"] == "critical"
    assert [f["lane"] for f in esc["flagged"]] == ["lateness", "occupancy"]
    # the non-lane key must NOT gain a severity
    assert "severity" not in vins["generated_at"]


def test_escalate_all_ok_gives_empty_flaglist():
    vins = {"lateness": _entry(10), "ground_truth": _entry(500_000)}
    esc = dv._escalate(vins)
    assert esc["worst"] == "ok"
    assert esc["flagged"] == []


def test_vintages_end_to_end_carries_escalation(monkeypatch, tmp_path):
    """The real payload: vintages() must include the escalation block."""
    monkeypatch.setattr(dv.config, "DATA_DIR", tmp_path)
    out = dv.vintages()
    esc = out["escalation"]
    assert esc["worst"] == "critical"  # tmp home: no files exist at all
    lanes = [f["lane"] for f in esc["flagged"]]
    # live/derived missing = critical; reference missing = warn (still flagged,
    # deliberately — a vanished committed source is worth one line in the email)
    assert "lateness" in lanes and "ridership" in lanes
    assert [f["severity"] for f in esc["flagged"] if f["lane"] == "ridership"] == [
        "warn"
    ]
    assert out["lateness"]["lane_class"] == "live"
