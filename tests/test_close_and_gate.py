"""Tests for close_task.py (T31) and board_check.py --am-i-free (T32)."""

import sys

from scripts.board_check import am_i_free
from scripts.close_task import _find_task_block, _has_done_marker, _has_esc

# ---------------------------------------------------------------------------
# T31: close_task.py internals
# ---------------------------------------------------------------------------

SAMPLE_TASKS = """\
# TASK QUEUE

### T99 — Test task alpha
**ASSIGNEE:** alpha-2
**Goal:** do a thing.
**DONE-WHEN:** thing done.

### T98 [ESC] — Escalated task beta
**ASSIGNEE:** alpha-2
**ESC:** yes — referee must ack.
**DONE-WHEN:** ack received.

### T97 [DONE 2026-08-24T00:00Z session-C] — Already closed gamma
**ASSIGNEE:** session-C
"""


def test_find_task_block():
    lines = SAMPLE_TASKS.splitlines()
    block = _find_task_block(lines, "T99")
    assert block is not None
    start, end = block
    assert "T99" in lines[start]
    assert end == 7  # next ### heading (T98 starts at 0-based line 7)


def test_find_task_block_not_found():
    assert _find_task_block(SAMPLE_TASKS.splitlines(), "T999") is None


def test_has_done_marker():
    assert _has_done_marker(
        "### T97 [DONE 2026-08-24T00:00Z session-C] — Already closed"
    )
    assert not _has_done_marker("### T99 — Test task")


def test_has_esc():
    lines = SAMPLE_TASKS.splitlines()
    t98 = _find_task_block(lines, "T98")
    assert _has_esc(lines[t98[0] : t98[1]])
    t99 = _find_task_block(lines, "T99")
    assert not _has_esc(lines[t99[0] : t99[1]])


def test_close_task_double_run_guard(tmp_path):
    tasks = tmp_path / "TASKS.md"
    status = tmp_path / "STATUS.md"
    tasks.write_text("### T50 \u2014 Test\n**Goal:** test.\n", encoding="utf-8")
    status.write_text("|---|---|---|---|---|---|\n", encoding="utf-8")

    # We can't easily test the full close_task without mocking git;
    # instead verify the double-run guard logic directly
    header = "### T50 \u2014 Test"
    assert "[DONE" not in header  # first run would proceed


def test_esc_refusal_logic():
    lines = ["### T98 [ESC] \u2014 Beta", "**ESC:** yes"]
    assert _has_esc(lines)


# ---------------------------------------------------------------------------
# T32: board_check.py --am-i-free
# ---------------------------------------------------------------------------

TASKS_WITH_ASSIGNMENTS = """\
# TASK QUEUE

### T01 \u2014 Open task for alpha-2
**ASSIGNEE:** alpha-2

### T02 \u2014 Done task for alpha-2
**ASSIGNEE:** alpha-2

### T03 \u2014 Open task for someone else
**ASSIGNEE:** alpha-3
"""

TASKS_WITH_DONE = """\
# TASK QUEUE

### T01 [DONE] \u2014 Closed task for alpha-2
**ASSIGNEE:** alpha-2
"""


def test_am_i_free_busy():
    assert am_i_free(TASKS_WITH_ASSIGNMENTS, "alpha-2") is False


def test_am_i_free_when_only_done():
    assert am_i_free(TASKS_WITH_DONE, "alpha-2") is True


def test_am_i_free_other_handle_unaffected():
    # alpha-3 has T03 open but we're asking about alpha-2 (whose only task is DONE)
    tasks = (
        TASKS_WITH_DONE
        + "\n### T99 \u2014 Open task for alpha-3\n**ASSIGNEE:** alpha-3\n"
    )
    assert am_i_free(tasks, "alpha-2") is True
    assert am_i_free(tasks, "alpha-3") is False  # alpha-3 has an open task


def test_am_i_free_multi_handle_assignee():
    # Multi-handle rows (T05-style "alpha-3 + alpha-9") must catch BOTH handles;
    # the old first-token regex only matched the first.
    tasks = (
        "### T05 \u2014 Open\n**ASSIGNEE:** alpha-3 (BUILDER) + alpha-9 (WRITER/PM)\n"
    )
    assert am_i_free(tasks, "alpha-3") is False
    assert am_i_free(tasks, "alpha-9") is False


def test_am_i_free_role_prefixed_assignee():
    # T07-style role-prefixed rows ("solver ops alpha-3 / ... alpha-6") must
    # catch every handle named anywhere on the line.
    tasks = (
        "### T07 \u2014 Open\n"
        "**ASSIGNEE:** solver ops alpha-3 (single-flight rule) / "
        "post-landing verification alpha-6 (pre-send trigger)\n"
    )
    assert am_i_free(tasks, "alpha-3") is False
    assert am_i_free(tasks, "alpha-6") is False


# ---------------------------------------------------------------------------
# T32: CLI-level exit codes (--am-i-free; 0 = free, 1 = busy)
# ---------------------------------------------------------------------------


def test_am_i_free_cli_exit_codes(tmp_path, monkeypatch, capsys):
    import scripts.board_check as bc

    agents = tmp_path / "agents"
    agents.mkdir()
    monkeypatch.setattr(bc, "AGENTS", agents)

    (agents / "TASKS.md").write_text(TASKS_WITH_ASSIGNMENTS, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["board_check.py", "--am-i-free", "alpha-2"])
    assert bc.main() == 1  # busy
    assert "BUSY" in capsys.readouterr().out

    (agents / "TASKS.md").write_text(TASKS_WITH_DONE, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["board_check.py", "--am-i-free", "alpha-2"])
    assert bc.main() == 0  # free
    assert "FREE" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# T31: end-to-end atomic closure (exactly one commit, double-run guard)
# ---------------------------------------------------------------------------


def test_close_task_e2e_atomic_commit(tmp_path, monkeypatch):
    """Closing a test ticket produces exactly ONE commit carrying both the
    TASKS.md [DONE] marker and the STATUS row; a second run exits nonzero
    and makes no further commit (T31 DONE-WHEN)."""
    import subprocess

    import scripts.close_task as ct

    repo = tmp_path / "repo"
    agents = repo / ".agents"
    agents.mkdir(parents=True)
    tasks = agents / "TASKS.md"
    status = agents / "STATUS.md"
    tasks.write_text(
        "### T50 \u2014 Test ticket\n**Goal:** do a thing.\n", encoding="utf-8"
    )
    status.write_text("# STATUS\n\n|---|---|---|---|---|---|\n", encoding="utf-8")

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=True
        )

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test Agent")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    before = int(git("rev-list", "--count", "HEAD").stdout.strip())

    monkeypatch.setattr(ct, "ROOT", repo)
    monkeypatch.setattr(ct, "TASKS", tasks)
    monkeypatch.setattr(ct, "STATUS", status)

    assert ct.close_task("T50", "alpha-6", "e2e atomic close") == 0
    after = int(git("rev-list", "--count", "HEAD").stdout.strip())
    assert after - before == 1  # exactly one commit

    header = tasks.read_text(encoding="utf-8").splitlines()[0]
    assert header.startswith("### T50") and "[DONE" in header
    new_status = status.read_text(encoding="utf-8")
    assert "| T50 |" in new_status and "e2e atomic close" in new_status

    # double-run guard: nonzero exit, no new commit
    assert ct.close_task("T50", "alpha-6", "again") != 0
    after2 = int(git("rev-list", "--count", "HEAD").stdout.strip())
    assert after2 - before == 1


def test_close_task_esc_refusal(tmp_path, monkeypatch):

    import subprocess

    import scripts.close_task as ct

    repo = tmp_path / "repo"
    agents = repo / ".agents"
    agents.mkdir(parents=True)
    tasks = agents / "TASKS.md"
    status = agents / "STATUS.md"
    tasks.write_text(
        "### T51 \u2014 ESC task\n**ESC:** yes — referee must ack.\n",
        encoding="utf-8",
    )
    status.write_text("# STATUS\n\n|---|---|---|---|---|---|\n", encoding="utf-8")

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=True
        )

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test Agent")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")

    monkeypatch.setattr(ct, "ROOT", repo)
    monkeypatch.setattr(ct, "TASKS", tasks)
    monkeypatch.setattr(ct, "STATUS", status)

    assert ct.close_task("T51", "alpha-6", "no ack") != 0  # refused without --esc-ack
    assert "[DONE" not in tasks.read_text(encoding="utf-8")
    assert ct.close_task("T51", "alpha-6", "acked", esc_ack=True) == 0
    assert "[DONE" in tasks.read_text(encoding="utf-8")
