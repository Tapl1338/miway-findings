"""Tests for scripts/check_doc_quotes.py (prose-vs-artifact quote gate).

The FQ8 audit (docs/runs/FQ8-montecarlo-verdict-20260830.md) found prose docs
quoting retired artifact vintages for a week after being formally flagged.
This checker is the mechanical closure of that loop; these tests pin both
failure modes (forbidden vintage fired, dropped claim fired), the
historical-context exemption, the digit guard against substring false
positives, and — against the real repo — that the live docs are consistent.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

_spec = importlib.util.spec_from_file_location(
    "check_doc_quotes", BACKEND / "scripts" / "check_doc_quotes.py"
)
cdq = importlib.util.module_from_spec(_spec)
# dataclasses' @dataclass resolves the module's globals via sys.modules;
# without registration the decorator crashes under importlib loading.
sys.modules[_spec.name] = cdq
_spec.loader.exec_module(cdq)


def _tmp_repo() -> tuple[Path, Path]:
    """A full copy of docs/ plus a stand-in README, for negative tests."""
    tmp = Path(tempfile.mkdtemp())
    docs = tmp / "docs"
    docs.mkdir()
    for f in (REPO / "docs").glob("*.md"):
        shutil.copy(f, docs / f.name)
    for f in (REPO / "docs").glob("*.json"):
        shutil.copy(f, docs / f.name)
    readme = tmp / "README.md"
    readme.write_text("# stand-in\n", encoding="utf-8")
    return tmp, docs


def _violations_by(docs: Path, root: Path, needle: str) -> list[str]:
    return [v for v in cdq.collect_violations(docs, root) if needle in v]


def test_forbidden_vintage_fires():
    tmp, docs = _tmp_repo()
    try:
        target = docs / "councillor-brief.md"
        target.write_text(
            target.read_text("utf-8")
            + "\nLine: the plan wins on 74% of simulated days.\n",
            encoding="utf-8",
        )
        hits = _violations_by(docs, tmp, "74% Monte Carlo")
        assert hits, "74% vintage quote must fail the gate"
        assert "councillor-brief.md" in hits[0]
    finally:
        shutil.rmtree(tmp)


def test_dropped_claim_fires():
    """Scrubbing the headline from every live doc must fail the required-
    claim engine."""
    tmp, docs = _tmp_repo()
    try:
        scrub = [
            "9,714.6",
            "9714.6",
            "9,715",
            "9715",
            "9,714",
            "9714",
            "≈9,700",
            "≈ 9,700",
            "roughly 9,700",
            "~9,700",
            "9,700",
            "9700",
        ]
        for f in [*list(docs.glob("*.md")), tmp / "README.md"]:
            t = f.read_text("utf-8")
            for bad in scrub:
                t = t.replace(bad, "X")
            f.write_text(t, "utf-8")
        hits = _violations_by(docs, tmp, "weekday all-period headline")
        assert hits, "dropping the headline figure everywhere must fail"
        assert "9,714.6" in hits[0]  # message re-derives the expected value
    finally:
        shutil.rmtree(tmp)


def test_dropped_flip_threshold_fires():
    """On the no-flip basis (flip_threshold = None, the desired outcome), the
    claim verifies via its sanctioned prose form; scrubbing that prose from
    every live doc must fail the required-claim engine."""
    tmp, docs = _tmp_repo()
    try:
        for f in [*list(docs.glob("*.md")), tmp / "README.md"]:
            t = f.read_text("utf-8").replace("even at 12", "even at X")
            f.write_text(t, "utf-8")
        hits = _violations_by(docs, tmp, "break-even")
        assert hits, "dropping the no-flip prose everywhere must fail"
    finally:
        shutil.rmtree(tmp)


def test_historical_context_exempt():
    """The kept-as-history ~3,400 footnote must not trip the 3,400 fossil."""
    tmp, docs = _tmp_repo()
    try:
        target = docs / "councillor-brief.md"
        target.write_text(
            target.read_text("utf-8")
            + "\na ~3,400/day figure briefly circulated from an uncapped run.\n",
            encoding="utf-8",
        )
        assert not _violations_by(docs, tmp, "3,400"), (
            "documented history must stay exempt"
        )
    finally:
        shutil.rmtree(tmp)


def test_digit_guard_no_substring_false_positive():
    tmp, docs = _tmp_repo()
    try:
        target = docs / "one-pager.md"
        # The corrected count (982) contains "82" — the digit guard must
        # keep "82 passing" from matching inside it.
        assert "982 passing" in target.read_text("utf-8")
        assert not _violations_by(docs, tmp, "82 passing")
    finally:
        shutil.rmtree(tmp)


def test_live_repo_is_consistent():
    """The real docs must pass right now — this is the gate's nightly job,
    pinned here so a stale quote can never sneak through a test run."""
    violations = cdq.collect_violations(REPO / "docs", REPO)
    assert not violations, "\n".join(violations)


def test_artifact_paths_resolve():
    """Every registry claim's dotted path must exist in its artifact, so a
    renamed JSON key fails loudly here instead of silently at night.
    An explicitly-None value is a real value when the claim declares
    none_regex_ok (e.g. flip_threshold = None = the no-break-even outcome)."""
    for claim in cdq.CLAIMS:
        artifact = json.loads(
            (REPO / "docs" / claim.artifact).read_text(encoding="utf-8")
        )
        found, value = cdq._dig(artifact, claim.path)
        assert found, f"{claim.artifact}:{claim.path} missing ({claim.description})"
        assert value is not None or claim.none_regex_ok, (
            f"{claim.artifact}:{claim.path} missing ({claim.description})"
        )
