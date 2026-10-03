"""Tests for ``scripts/push_staleness_guard.py`` (hot-file staleness guard)."""

import json

from scripts import push_staleness_guard as pg


def _snap_args(tree, tmp_path, name="snap.json"):
    return pg.argparse.Namespace(snapshot=str(tmp_path / name))


def _build_tree(tmp_path):
    app = tmp_path / "frontend" / "src" / "App.tsx"
    app.parent.mkdir(parents=True)
    app.write_text("VIRTUAL App.tsx body\n", encoding="utf-8")
    htest = tmp_path / "frontend" / "tests" / "hashRouting.a.test.ts"
    htest.parent.mkdir(parents=True)
    htest.write_text("it('routes through hash')\n", encoding="utf-8")
    agents = tmp_path / ".agents"
    agents.mkdir()
    (agents / "STATUS.md").write_text("| row |\n", encoding="utf-8")
    return tmp_path


def test_snapshot_roundtrips_and_clean_check_exits0(tmp_path, monkeypatch):
    tree = _build_tree(tmp_path)
    monkeypatch.setattr(pg, "REPO_ROOT", tree)
    assert pg.cmd_snapshot(_snap_args(tree, tmp_path)) == 0
    snap = json.loads((tmp_path / "snap.json").read_text(encoding="utf-8"))
    assert len(snap) >= 3  # App.tsx + one hashRouting test + one .agents file
    assert pg.cmd_check(_snap_args(tree, tmp_path)) == 0


def test_check_refuses_when_hot_file_changed(tmp_path, monkeypatch, capsys):
    tree = _build_tree(tmp_path)
    monkeypatch.setattr(pg, "REPO_ROOT", tree)
    pg.cmd_snapshot(_snap_args(tree, tmp_path))
    (tree / "frontend" / "src" / "App.tsx").write_text("EDITED\n", encoding="utf-8")
    assert pg.cmd_check(_snap_args(tree, tmp_path)) == 1
    assert "CHANGED since snapshot" in capsys.readouterr().err


def test_check_refuses_new_delivery_in_hot_dir(tmp_path, monkeypatch, capsys):
    tree = _build_tree(tmp_path)
    monkeypatch.setattr(pg, "REPO_ROOT", tree)
    pg.cmd_snapshot(_snap_args(tree, tmp_path))
    (tree / ".agents" / "NEW.md").write_text("x\n", encoding="utf-8")
    assert pg.cmd_check(_snap_args(tree, tmp_path)) == 1
    assert "NEW" in capsys.readouterr().err


def test_check_refuses_when_snapshot_missing(tmp_path, monkeypatch):
    tree = _build_tree(tmp_path)
    monkeypatch.setattr(pg, "REPO_ROOT", tree)
    assert pg.cmd_check(_snap_args(tree, tmp_path, "missing.json")) == 2


def test_check_ignores_non_hot_file(tmp_path, monkeypatch):
    tree = _build_tree(tmp_path)
    monkeypatch.setattr(pg, "REPO_ROOT", tree)
    pg.cmd_snapshot(_snap_args(tree, tmp_path))
    backend = tree / "backend"
    backend.mkdir()
    (backend / "unrelated.py").write_text("# not hot\n", encoding="utf-8")
    assert pg.cmd_check(_snap_args(tree, tmp_path)) == 0
