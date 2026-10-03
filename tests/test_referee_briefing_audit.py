"""T19 auditor-fix regression tests (alpha-3).

Covers the two alpha-6 BREAKS against referee_briefing.py:
1. DONE-marker scoping -- one task's [DONE] must not silence another task's
   MARKER-MISSING / ORPHAN-BRANCH finding.
2. ASSIGNEE capture -- body-line '**ASSIGNEE:** <handle>' rows must register,
   so assigned-but-never-started tasks fire NOT-STARTED.
"""

from scripts import referee_briefing as rb


def _tasks() -> list[str]:
    return [
        "## Queue",
        "### T90 - Alpha task with done marker",
        "**ASSIGNEE:** alpha-9",
        "body text",
        "### T91 - Beta task, no marker, no assignee",
        "body text",
        "### T92 - Gamma task, body-line assignee",
        "**ASSIGNEE:** alpha-8",
        "body text",
    ]


def test_done_marker_is_scoped_to_its_own_task():
    """T90's [DONE] must not mark T91/T92 done (BREAK-1 regression)."""
    issues = rb.audit_board(
        _tasks(),
        [
            "| 2026-08-24T00:00Z | x | T91 | b | DONE evidence | e |",
            "| 2026-08-24T00:00Z | x | T92 | b | DONE evidence | e |",
        ],
    )
    joined = "\n".join(issues)
    assert "MARKER-MISSING T91" in joined
    assert "MARKER-MISSING T92" in joined
    # The genuinely-done task stays quiet.
    assert "MARKER-MISSING T90" not in joined


def test_body_line_assignee_fires_not_started():
    """Body-line ASSIGNEE rows must register (BREAK-2 regression)."""
    issues = rb.audit_board(_tasks(), [])
    joined = "\n".join(issues)
    assert "NOT-STARTED T90: assigned to alpha-9" in joined
    assert "NOT-STARTED T92: assigned to alpha-8" in joined


def test_in_progress_suppresses_not_started_for_assigned_task():
    lines = [
        *_tasks(),
        "",
        "## In progress",
        "| 2026-08-24T00:00Z | y | T92 | b | started | e |",
    ]
    issues = rb.audit_board(lines, [])
    joined = "\n".join(issues)
    assert "NOT-STARTED T92" not in joined
    assert "NOT-STARTED T90: assigned to alpha-9" in joined


def test_orphan_branch_scoped_by_section(monkeypatch):
    """A branch for an unmarked task fires even when other tasks are DONE;
    a branch whose task carries its own [DONE] stays silent (BREAK-1)."""
    tasks = [
        "### T80 - done task",
        "[DONE 2026-08-24] finished",
        "### T81 - open task",
        "body",
    ]
    monkeypatch.setattr(
        rb,
        "_run",
        lambda cmd, cwd=None: (
            "alpha-3/VERIFY-T80\nalpha-4/T81-x" if cmd[0] == "git" else None
        ),
    )
    issues = rb._orphan_branches(tasks)
    assert any("ORPHAN-BRANCH" in i and "T81" in i for i in issues)
    assert not any("ORPHAN-BRANCH" in i and "T80" in i for i in issues)
