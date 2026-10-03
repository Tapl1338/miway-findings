"""Tests for ``scripts/check_action_versions.py`` — the action-staleness gate.

Covers the workflow scan (actions-only, version-pinned refs), the audit
comparison against injectable latest-majors, and the exit-code rule. The
GitHub API call itself is never exercised — the audit takes a fetch callable,
mirroring how the drift gate keeps network out of its tests.
"""

from pathlib import Path

from scripts import check_action_versions as cav


def _write_workflow(tmp_path: Path, name: str, text: str) -> Path:
    root = tmp_path / ".github" / "workflows"
    root.mkdir(parents=True, exist_ok=True)
    p = root / name
    p.write_text(text, encoding="utf-8")
    return p


def test_scan_workflow_captures_versioned_action_pins(tmp_path):
    p = _write_workflow(
        tmp_path,
        "ci.yml",
        "\n".join(
            [
                "jobs:",
                "  build:",
                "    steps:",
                "      - uses: actions/checkout@v5",
                "      - uses: actions/setup-python@v7",
                "        with:",
                "          python-version: '3.12'",
                "      - uses: gitleaks/gitleaks-action@v3",  # third-party: ignored
                "      - uses: actions/checkout@v5",  # duplicate: deduped
            ]
        ),
    )
    assert cav.scan_workflow(p) == [
        ("actions/checkout", 5),
        ("actions/setup-python", 7),
    ]


def test_scan_workflow_skips_non_version_refs_and_non_actions(tmp_path):
    p = _write_workflow(
        tmp_path,
        "x.yml",
        "\n".join(
            [
                "- uses: actions/checkout@main",  # floating ref: not comparable
                "- uses: other/repo@v4",  # not actions/*
                "- uses: docker/build-push-action@v6",  # not actions/*
            ]
        ),
    )
    assert cav.scan_workflow(p) == []


def test_collect_pins_reads_both_repos(monkeypatch, tmp_path):
    _write_workflow(tmp_path, "private.yml", "- uses: actions/checkout@v4\n")
    showcase = tmp_path / "public-showcase" / "miway-findings"
    _write_workflow(showcase, "showcase.yml", "- uses: actions/checkout@v5\n")
    monkeypatch.setattr(cav, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cav, "SHOWCASE", showcase)

    pins = cav.collect_pins()
    assert (Path(".github/workflows/private.yml"), "actions/checkout", 4) in pins
    # Showcase pins carry the showcase repo's dir name — stable across the
    # local nested layout and CI's side-by-side checkout.
    assert (
        Path("miway-findings/.github/workflows/showcase.yml"),
        "actions/checkout",
        5,
    ) in pins


def test_audit_flags_only_stale_majors():
    pins = [
        (Path("a.yml"), "actions/checkout", 4),
        (Path("a.yml"), "actions/checkout", 5),
        (Path("b.yml"), "actions/setup-python", 7),
    ]
    latest = {"actions/checkout": 5, "actions/setup-python": 7}
    stale, n = cav.audit(pins, latest.__getitem__)
    assert n == 1
    assert "a.yml: actions/checkout@v4 (latest major: v5)" in stale[0]


def test_audit_fetches_each_action_once():
    calls = []

    def fetch(action):
        calls.append(action)
        return 9

    pins = [
        (Path("a.yml"), "actions/checkout", 5),
        (Path("b.yml"), "actions/checkout", 5),
    ]
    cav.audit(pins, fetch)
    assert calls == ["actions/checkout"]  # cached: one API call per action


def test_exit_code_fails_on_stale_only():
    assert cav.exit_code(0) == 0
    assert cav.exit_code(1) == 1
    assert cav.exit_code(4) == 1


def test_latest_majors_parses_release_tag(monkeypatch):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"tag_name": "v7.1.2"}'

    def fake_urlopen(req, timeout):
        assert (
            req.full_url
            == "https://api.github.com/repos/actions/checkout/releases/latest"
        )
        assert req.headers.get("Authorization") is None
        return FakeResp()

    monkeypatch.setattr(cav.urllib.request, "urlopen", fake_urlopen)
    assert cav.latest_majors("actions/checkout", token=None) == {"actions/checkout": 7}
