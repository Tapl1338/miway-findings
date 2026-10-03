"""Unit tests for scripts/sept7_after.py (one-command Sept-7 after-study)."""

import zipfile
from pathlib import Path

import pandas as pd
import pytest
from scripts.archive import sept7_after as sa

BASELINE = sa.BASELINE_SHA16


def _fake_files(tmp_path: Path, names: list[str]) -> dict[str, Path]:
    out = {}
    for n in names:
        p = tmp_path / n
        p.write_text("dummy", encoding="utf-8")
        out[n] = p
    return out


def test_hash_gate_verdict():
    ok, reason = sa.hash_gate_verdict(BASELINE, "deadbeef00000000", False)
    assert ok
    assert "old sha16" in reason and "new sha16" in reason
    # old is not the archived baseline -> fail
    assert (
        sa.hash_gate_verdict("0000000000000000", "deadbeef00000000", False)[0] is False
    )
    # identical feeds fail unless rehearsing
    assert sa.hash_gate_verdict(BASELINE, BASELINE, False)[0] is False
    assert sa.hash_gate_verdict(BASELINE, BASELINE, True)[0] is True


def test_hash_gate_failure_exits_before_any_work(tmp_path, monkeypatch):
    files = _fake_files(tmp_path, ["old.zip", "new.zip", "pre.csv.gz"])
    monkeypatch.setattr(sa, "sha16", lambda _p: "0000000000000000")
    with pytest.raises(SystemExit) as exc:
        sa.main(
            [
                "--old-zip",
                str(files["old.zip"]),
                "--new-zip",
                str(files["new.zip"]),
                "--pre-lateness",
                str(files["pre.csv.gz"]),
            ]
        )
    assert "HASH GATE FAILED" in str(exc.value)


def test_hash_gate_skippable_with_skip_gate(tmp_path, monkeypatch):
    """--skip-gate must let a diagnostic run proceed past the hash check."""
    files = _fake_files(tmp_path, ["old.zip", "new.zip", "pre.csv.gz"])
    monkeypatch.setattr(sa, "sha16", lambda _p: "0000000000000000")
    # Extraction of dummy zips is the next failure point; assert we get past
    # the hash gate (BadZipFile from the dummy file, NOT a gate SystemExit).
    with pytest.raises(zipfile.BadZipFile):
        sa.main(
            [
                "--old-zip",
                str(files["old.zip"]),
                "--new-zip",
                str(files["new.zip"]),
                "--pre-lateness",
                str(files["pre.csv.gz"]),
                "--skip-gate",
            ]
        )


def test_cell_summary_formatting():
    merged = pd.DataFrame(
        {
            "from_route": ["8", "8", "43", "66"],
            "to_route": ["43", "66", "10", "45"],
            "realized_mean_min_old": [5.0, 10.0, 18.0, 4.0],
            "realized_mean_min_new": [3.0, 10.0, 12.0, 4.0],
            "realized_delta_min": [-2.0, 0.0, -6.0, 0.0],
            "realized_missed_share_old": [0.1, 0.2, 0.6, 0.01],
            "realized_missed_share_new": [0.05, 0.2, 0.3, 0.01],
            "abs_sort": [2.0, 0.0, 6.0, 0.0],
        }
    )
    flagged = {"8", "66", "43"}
    out = sa.cell_summary(merged, flagged)
    assert "Flagged pairs:" in out
    assert "Summary: 4 pairs · 2 with |delta|>0.05 · max |delta| 6.00 min" in out
    # non-flagged pair (66->45 with 0.0 delta) is not in the flagged block;
    # flagged rows (8->43, 8->66, 43->10) all are.
    flagged_block = out.split("Summary:")[0]
    assert "66 | 45" not in flagged_block
    assert "43" in flagged_block and "8" in flagged_block


def test_cell_summary_empty():
    assert sa.cell_summary(pd.DataFrame(), {"8"}) == "_(no pairs)_\n"
