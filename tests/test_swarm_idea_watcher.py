"""Tests for the read-only swarm proposal watcher."""

from __future__ import annotations

from pathlib import Path

from scripts import swarm_idea_watcher as watcher


def _proposal(
    tmp_path: Path,
    *,
    proposal_id: str = "IDEA-20260924-test",
    evidence: str = "evidence.md",
    approval_required: bool = True,
    create_evidence: bool = True,
) -> Path:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    if create_evidence:
        (tmp_path / evidence).write_text("evidence\n", encoding="utf-8")
    path = inbox / "proposal.md"
    path.write_text(
        f"""---
id: {proposal_id}
title: Test proposal
status: proposed
confidence: high
review_state: pending
source: swarm-brainstorm
created_utc: "2026-09-24T12:00:00Z"
approval_required: {str(approval_required).lower()}
evidence:
  - {evidence}
affected_paths:
  - backend/scripts/example.py
done_when:
  - "pytest passes"
risks:
  - "none identified"
---

# Test proposal
""",
        encoding="utf-8",
    )
    return path


def test_watcher_surfaces_high_confidence_proposal(tmp_path: Path) -> None:
    _proposal(tmp_path)

    report = watcher.scan_inbox(tmp_path / "inbox", tmp_path)

    assert len(report.eligible) == 1
    assert report.invalid == ()
    proposal = report.eligible[0]
    assert proposal.fields["id"] == "IDEA-20260924-test"
    assert "no builders launched" in watcher.render_report(report)


def test_watcher_rejects_missing_evidence_and_missing_approval(tmp_path: Path) -> None:
    _proposal(
        tmp_path,
        evidence="does-not-exist.md",
        approval_required=False,
        create_evidence=False,
    )

    report = watcher.scan_inbox(tmp_path / "inbox", tmp_path)

    assert report.eligible == ()
    errors = " ".join(report.invalid[0].errors)
    assert "evidence path does not exist" in errors
    assert "approval_required must be true" in errors


def test_watcher_strict_reports_invalid_proposals(tmp_path: Path, capsys) -> None:
    _proposal(tmp_path, proposal_id="not-an-idea")

    result = watcher.main(
        [
            "--inbox",
            str(tmp_path / "inbox"),
            "--repo",
            str(tmp_path),
            "--once",
            "--strict",
        ]
    )

    assert result == 1
    assert "invalid=1" in capsys.readouterr().out


def test_approve_freezes_proposal_and_prepares_charter(tmp_path: Path) -> None:
    proposal = _proposal(tmp_path)
    charter_dir = tmp_path / "charters"
    approvals_dir = tmp_path / "approvals"

    result = watcher.approve_proposal(
        "IDEA-20260924-test",
        tmp_path / "inbox",
        tmp_path,
        charter_dir,
        approvals_dir,
    )

    assert result == 0
    frozen = proposal.read_text(encoding="utf-8")
    assert "status: approved" in frozen
    assert "review_state: approved" in frozen
    assert "approval_source: human-explicit-command" in frozen
    charter = charter_dir / "IDEA-20260924-test-builder.md"
    receipt = approvals_dir / "IDEA-20260924-test.json"
    assert charter.is_file()
    assert receipt.is_file()
    assert "does not launch a builder" in charter.read_text(encoding="utf-8")
    report = watcher.scan_inbox(tmp_path / "inbox", tmp_path)
    assert report.eligible == ()
    assert len(report.ignored) == 1
