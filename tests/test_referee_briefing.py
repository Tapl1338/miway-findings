"""Tests for scripts.referee_briefing parsers."""

from scripts.referee_briefing import (
    empty_decisions,
    find_marker,
    in_progress,
    reply_rows,
)

STATUS_SAMPLE = [
    "| UTC | agent | TASK | branch | event | evidence |",
    "|---|---|---|---|---|---|",
    "| 2026-08-24T00:45Z | session-C | - | master | queued T07 | diff |",
    "| 2026-08-24T01:00Z | alpha-2 | T07 | branch-x | REPLY-TO: session-C wrong basis | row |",
    "| 2026-08-24T01:10Z | session-C | T07 | branch-y | resolved, artifact matches | csv:12 |",
]

TASKS_SAMPLE = [
    "## Queue",
    "### T01 - thing",
    "## In progress",
    "| 2026-08-24 | alpha-3 | T08 | claim row |",
    "## Done",
    "*(empty)*",
]

DECISIONS_SAMPLE = [
    "### DEC-01 - flag",
    "**DECIDED:**",
    "### DEC-02 - recipe",
    "**DECIDED:** majority-vote among handles",
]


def test_find_marker_hits_and_misses():
    assert find_marker(["ok", "tag ESC: here"], "ESC:") == ["tag ESC: here"]
    assert find_marker(["clean"], "ESC:") == []


def test_empty_decisions_flags_only_unfilled():
    assert empty_decisions(DECISIONS_SAMPLE) == ["DEC-01"]


def test_reply_rows_skips_header():
    rows = reply_rows(STATUS_SAMPLE)
    assert len(rows) == 1
    assert "REPLY-TO: session-C" in rows[0]


def test_in_progress_excludes_other_sections_and_empty_marker():
    assert in_progress(TASKS_SAMPLE) == ["| 2026-08-24 | alpha-3 | T08 | claim row |"]


def test_stripped_markers_still_fire_cross_task():
    """Regression: alpha-6 reported cross-task DONE suppression.
    Stripping every [DONE]/[SUPERSEDED] marker must still fire
    MARKER-MISSING for each task holding a STATUS done-row."""
    from scripts.referee_briefing import audit_board

    tasks = [
        "### T01 - open task",
        "### T02 - done task",
        "### T03 - superseded task",
        "## In progress",
        "*(empty)*",
    ]
    status = [
        "| 2026-08-24T00:01Z | x | T02 | b | DONE proof | f:1 |",
        "| 2026-08-24T00:02Z | y | T03 | b | DONE superseded by X | f:2 |",
    ]
    issues = audit_board(tasks, status)
    fired = sorted(i.split(":")[0] for i in issues if i.startswith("MARKER"))
    assert fired == ["MARKER-MISSING T02", "MARKER-MISSING T03"]
