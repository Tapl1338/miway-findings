"""Tests for structured proposal ingestion from brainstorm answers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts import swarm_brainstorm as brainstorm


def _block(*, evidence: str = "evidence.md") -> str:
    return f"""BEGIN_PROPOSAL
---
id: IDEA-20260924-grounded
title: "Grounded improvement"
status: proposed
confidence: high
review_state: pending
source: swarm-brainstorm
created_utc: "2026-09-24T12:00:00Z"
approval_required: true
evidence:
  - {evidence}
affected_paths:
  - backend/scripts/example.py
done_when:
  - "pytest passes"
risks:
  - "none identified"
---

# Grounded improvement
## Problem
A bounded problem.
## Proposal
A bounded proposal.
## Scope
One file.
## Done when
The test passes.
## Risks and non-goals
No production behavior outside the named file.
END_PROPOSAL"""


def test_stage_proposal_dossier_refreshes_from_brief(tmp_path: Path) -> None:
    source = tmp_path / "brief.md"
    source.write_text("Improve backend/scripts/existing.py safely.\n", encoding="utf-8")
    target = tmp_path / "backend" / "scripts" / "existing.py"
    target.parent.mkdir(parents=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")

    dossier, result = brainstorm.stage_proposal_dossier(
        source, tmp_path / "docs" / "scout", tmp_path, "fresh", 7000
    )

    assert result == 0
    assert dossier.is_file()
    assert "backend/scripts/existing.py" in dossier.read_text(encoding="utf-8")


def test_ingest_proposals_writes_only_valid_block(tmp_path: Path) -> None:
    (tmp_path / "evidence.md").write_text("evidence\n", encoding="utf-8")
    inbox = tmp_path / "inbox"

    accepted, rejected = brainstorm.ingest_proposals(
        {"agent-01": _block()}, inbox, tmp_path
    )

    assert len(accepted) == 1
    assert accepted[0].name == "IDEA-20260924-grounded.md"
    assert rejected == []
    assert "Grounded improvement" in accepted[0].read_text(encoding="utf-8")


def test_ingest_proposals_rejects_unstructured_or_ungrounded_output(
    tmp_path: Path,
) -> None:
    inbox = tmp_path / "inbox"

    accepted, rejected = brainstorm.ingest_proposals(
        {
            "agent-01": "A good idea without evidence.",
            "agent-02": _block(evidence="missing.md"),
        },
        inbox,
        tmp_path,
    )

    assert accepted == []
    assert len(rejected) == 2
    assert not list(inbox.glob("*.md"))


def test_direct_checkpoint_preserves_partial_answers_and_pending_agents(
    tmp_path: Path,
) -> None:
    record = tmp_path / "round.md"
    args = SimpleNamespace(n=3, topic="checkpoint test")

    json_path, markdown_path = brainstorm._write_direct_checkpoint(
        record_path=record,
        args=args,
        lenses=["first", "second", "third"],
        answers={0: "A" * 70, 1: "ERROR: empty completion"},
        lats=[1.0, 2.0],
        latencies={0: 1.0, 1: 2.0},
        served={0: "test/combo:free"},
        tried={0: ["test/combo:free"], 1: ["test/null:free"]},
        attempt_events=[
            {
                "agent_id": 1,
                "attempt": 1,
                "combo": "test/combo:free",
                "outcome": "ok",
                "latency_seconds": 1.0,
            },
            {
                "agent_id": 2,
                "attempt": 1,
                "combo": "test/null:free",
                "outcome": "empty",
                "latency_seconds": 2.0,
            },
        ],
        started_utc="2026-09-24T12:00:00+00:00",
        elapsed=3.0,
        wave=1,
        complete=False,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["complete"] is False
    assert payload["collected_agents"] == 2
    assert payload["successful_agents"] == 1
    assert payload["failed_agent_ids"] == [2]
    assert payload["pending_agent_ids"] == [3]
    assert len(payload["attempt_events"]) == 2
    assert brainstorm._direct_attempt_succeeded("too short") is False
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "partial checkpoint" in markdown
    assert "agent-03" in markdown
    assert "ERROR: empty completion" in markdown


def test_direct_run_writes_final_checkpoint_atomically(
    tmp_path: Path, monkeypatch
) -> None:
    class FakeResponse:
        headers = {"X-Swarm-Combo": "test/combo:free"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "A grounded answer with enough detail to pass the minimum output length gate."
                            }
                        }
                    ]
                }
            ).encode()

    monkeypatch.setattr(
        brainstorm.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse()
    )
    record = tmp_path / "round.md"
    args = SimpleNamespace(
        n=2,
        topic="checkpoint test",
        dossier="",
        lenses="",
        lenses_set="improve",
        readonly=True,
        words=100,
        wave=2,
        record=str(record),
    )

    assert brainstorm.cmd_run_direct(args) == 0

    payload = json.loads(
        (tmp_path / "round-checkpoint.json").read_text(encoding="utf-8")
    )
    assert payload["complete"] is True
    assert payload["successful_agents"] == 2
    assert payload["pending_agent_ids"] == []
    assert len(payload["attempt_events"]) == 2
    assert record.is_file()
    assert record.with_suffix(".json").is_file()
    assert "complete" in (tmp_path / "round-checkpoint.md").read_text(encoding="utf-8")
    assert not list(tmp_path.glob(".*.tmp"))


def test_checkpoint_summary_reports_themes_warnings_and_providers(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "backend" / "scripts").mkdir(parents=True)
    (repo / "backend" / "scripts" / "service_quality.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    (repo / "backend" / "scripts" / "swarm_brainstorm.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    (repo / "backend" / "scripts" / "swarm_fanout.py").write_text(
        "def existing_call():\n    pass\n", encoding="utf-8"
    )
    checkpoint = tmp_path / "round-checkpoint.json"
    checkpoint.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "topic": "summary test",
                "expected_agents": 3,
                "collected_agents": 3,
                "successful_agents": 3,
                "pending_agent_ids": [],
                "complete": False,
                "waves_started": 2,
                "elapsed_seconds": 12.5,
                "answers": {
                    "0": "WHAT: Automate service quality duplicate-warning checks. WHERE: backend/scripts/service_quality.py Calls swarm_fanout.missing_call().",
                    "1": "WHAT: Add a service-quality evidence panel and reduce 30% review time. WHERE: backend/scripts/missing.py",
                    "2": "WHAT: Add swarm retry checkpoint recovery. WHERE: backend/scripts/swarm_brainstorm.py",
                },
                "served": {
                    "0": "fast/model:free",
                    "1": "null/model:free",
                    "2": "fast/model:free",
                },
                "tried": {
                    "0": ["fast/model:free"],
                    "1": ["null/model:free", "null/model:free"],
                    "2": ["fast/model:free"],
                },
                "attempt_events": [
                    {
                        "agent_id": 1,
                        "attempt": 1,
                        "combo": "fast/model:free",
                        "outcome": "ok",
                        "latency_seconds": 5.0,
                    },
                    {
                        "agent_id": 2,
                        "attempt": 1,
                        "combo": "null/model:free",
                        "outcome": "empty",
                        "latency_seconds": 20.0,
                    },
                    {
                        "agent_id": 2,
                        "attempt": 2,
                        "combo": "null/model:free",
                        "outcome": "ok",
                        "latency_seconds": 8.0,
                    },
                    {
                        "agent_id": 3,
                        "attempt": 1,
                        "combo": "fast/model:free",
                        "outcome": "ok",
                        "latency_seconds": 6.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = brainstorm.summarize_checkpoint(checkpoint, repo=repo)
    rendered = brainstorm.render_checkpoint_summary(summary)

    theme_names = {theme["theme"] for theme in summary["themes"]}
    assert theme_names == {
        "service-quality cleanup and diagnostics",
        "swarm automation and prewarm",
    }
    service_theme = next(
        theme
        for theme in summary["themes"]
        if theme["theme"] == "service-quality cleanup and diagnostics"
    )
    assert service_theme["agent_ids"] == [1, 2]
    assert {warning["kind"] for warning in summary["suspicious_claims"]} == {
        "missing_path",
        "unanchored_number",
        "unverified_symbol",
    }
    fast = next(
        row
        for row in summary["provider_attribution"]
        if row["combo"] == "fast/model:free"
    )
    null = next(
        row
        for row in summary["provider_attribution"]
        if row["combo"] == "null/model:free"
    )
    assert fast["attempts"] == 2
    assert fast["successful_final_answers"] == 2
    assert null["empty_attempts"] == 1
    assert null["ok_attempts"] == 1
    assert "Provider attribution" in rendered
    assert "backend/scripts/missing.py" in rendered
