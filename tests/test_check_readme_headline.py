"""Tests for scripts/check_readme_headline.py — the T155 README gate.

Pins each contract the gate enforces against synthetic artifact/README
pairs (basis stamp required, model prose must match the stamp, canonical
walk flag, headline tolerance, receipt citation), plus the live repo
integration: the committed exec-summary.json and README.md must
currently agree.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

_spec = importlib.util.spec_from_file_location(
    "check_readme_headline", BACKEND / "scripts" / "check_readme_headline.py"
)
crh = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = crh
_spec.loader.exec_module(crh)


def _readme_text() -> str:
    return """# Repo

### What the optimizer finds (model results)

Numbers below are from the solver model on the current (post-Sept-7)
timetable, using the **july** missed-connection cost model (adopted
2026-09-19; see `docs/runs/t154-miss-model-godown-20260919.md`).

- **≈9,700 passenger-minutes/day saved** by re-timing existing routes.

---

## Next section
"""


def _artifact() -> dict:
    return {
        "basis": {
            "miss_model": "july",
            "service_date": "20260911",
            "same_terminal_walk": False,
            "generated_utc": "2026-09-19T23:48:19Z",
        },
        "result": {"saved_pax_minutes": 9714.6},
    }


def _violations(artifact: dict, readme_text: str) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        readme = Path(tmp) / "README.md"
        artifact_path = Path(tmp) / "exec-summary.json"
        readme.write_text(readme_text, encoding="utf-8")
        artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
        return crh.collect_violations(readme, artifact_path)


def test_valid_pair_passes():
    assert _violations(_artifact(), _readme_text()) == []


def test_basis_stamp_required():
    artifact = _artifact()
    del artifact["basis"]
    hits = _violations(artifact, _readme_text())
    assert hits and "basis" in hits[0]


def test_walk_flag_must_be_canonical():
    artifact = _artifact()
    artifact["basis"]["same_terminal_walk"] = True
    hits = _violations(artifact, _readme_text())
    assert hits and "same_terminal_walk" in hits[0]


def test_model_prose_mismatch_fires():
    text = _readme_text().replace("**july**", "**window**")
    hits = _violations(_artifact(), text)
    assert hits and "window" in hits[0] and "july" in hits[0]


def test_missing_receipt_fires():
    text = _readme_text().replace(
        "see `docs/runs/t154-miss-model-godown-20260919.md`", ""
    )
    hits = _violations(_artifact(), text)
    assert hits and "receipt" in hits[0]


def test_headline_drift_fires():
    # 12,000 vs 9,714.6 is ~23% — far beyond the 5% tolerance.
    text = _readme_text().replace("≈9,700", "≈12,000")
    hits = _violations(_artifact(), text)
    assert hits and "drift" in hits[0]


def test_headline_within_tolerance_passes():
    # 9,700 vs 9,714.6 is 0.15% — the canonical rounded quote passes.
    text = _readme_text().replace("≈9,700", "≈9,701")
    assert _violations(_artifact(), text) == []


def test_missing_headline_fires():
    text = _readme_text().replace(
        "- **≈9,700 passenger-minutes/day saved** by re-timing existing routes.\n",
        "",
    )
    hits = _violations(_artifact(), text)
    assert hits and "headline" in hits[0].lower()


def test_no_section_fires():
    hits = _violations(_artifact(), "# A repo with no model results\n")
    assert hits and "not found" in hits[0]


def test_live_repo_agrees():
    """Integration: the committed README + exec-summary.json must satisfy
    the gate right now — a stale pair fails loudly in CI, not at night."""
    violations = crh.collect_violations(
        REPO / "README.md", REPO / "docs" / "exec-summary.json"
    )
    assert not violations, "\n".join(violations)
