"""Tests for scripts/archive/freeze_evidence.py (the v7 freeze-dir fix, 2026-10-02).

The regression under test: the manifest-keyed SKIP would have left
evidence-freeze-v7/ without ground_truth.csv, which derive_findings.py
loads from the freeze dir — so a byte-identical file MUST still land in a
new label's directory.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from scripts.archive import freeze_evidence as fe

NOW = "2026-10-04T21:00Z"


def _write_sources(data_dir: Path, names: list[str]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(names):
        (data_dir / name).write_bytes(f"row-{i},{name}\n".encode())


def test_freeze_writes_every_file_into_a_fresh_dir(tmp_path: Path) -> None:
    names = ["ground_truth.csv", "obs_lateness.csv"]
    _write_sources(tmp_path / "data", names)

    rows, frozen, skipped, missing, carried = fe.freeze_files(
        tmp_path / "data", tmp_path / "out", "v7", NOW, set(), names
    )

    assert (frozen, skipped, missing, carried) == (2, 0, 0, [])
    assert len(rows) == 2
    for name in names:
        arc = tmp_path / "out" / f"{name}.gz"
        assert arc.exists()
        assert (
            gzip.decompress(arc.read_bytes()) == (tmp_path / "data" / name).read_bytes()
        )


def test_byte_identical_file_still_lands_in_the_new_dir(tmp_path: Path) -> None:
    """A sha already in the manifest must NOT be skipped: the new dir needs it."""
    names = ["ground_truth.csv"]
    _write_sources(tmp_path / "data", names)
    seen = {fe.sha256_of((tmp_path / "data" / "ground_truth.csv").read_bytes())[:16]}

    rows, frozen, skipped, _missing, carried = fe.freeze_files(
        tmp_path / "data", tmp_path / "out", "v7", NOW, seen, names
    )

    assert (frozen, skipped) == (1, 0)
    assert carried == ["ground_truth.csv"]
    assert (tmp_path / "out" / "ground_truth.csv.gz").exists()
    assert "identical to an earlier window" in rows[0]


def test_manifest_parser_still_reads_the_annotated_row(tmp_path: Path) -> None:
    """The annotation must not break the seen-sha parser in main()."""
    names = ["ground_truth.csv"]
    _write_sources(tmp_path / "data", names)
    digest = fe.sha256_of((tmp_path / "data" / "ground_truth.csv").read_bytes())[:16]
    rows, *_ = fe.freeze_files(
        tmp_path / "data", tmp_path / "out", "v7", NOW, {digest}, names
    )

    line = rows[0]
    assert line.startswith("|") and "sha256:" in line
    parsed = line.split("sha256:")[1].split()[0].rstrip("*")
    assert parsed == digest


def test_second_run_is_idempotent(tmp_path: Path) -> None:
    names = ["ghost_trips.csv", "occupancy_stats.csv"]
    _write_sources(tmp_path / "data", names)
    first_rows, *_ = fe.freeze_files(
        tmp_path / "data", tmp_path / "out", "v7", NOW, set(), names
    )

    second_rows, frozen, skipped, _missing, carried = fe.freeze_files(
        tmp_path / "data", tmp_path / "out", "v7", NOW, set(), names
    )

    assert (frozen, skipped) == (0, 2)
    assert second_rows == []
    assert carried == []
    assert len(first_rows) == 2  # first run's manifest rows are the only ones


def test_refuses_to_overwrite_differing_evidence(tmp_path: Path) -> None:
    names = ["obs_lateness.csv"]
    _write_sources(tmp_path / "data", names)
    out = tmp_path / "out"
    out.mkdir()
    (out / "obs_lateness.csv.gz").write_bytes(
        gzip.compress(b"some other window's bytes\n")
    )

    with pytest.raises(fe.FreezeConflict, match="immutable"):
        fe.freeze_files(tmp_path / "data", out, "v7", NOW, set(), names)


def test_missing_file_is_counted_not_fatal(tmp_path: Path) -> None:
    names = ["realized_waits.csv", "realized_waits.md"]
    _write_sources(tmp_path / "data", names[:1])  # .md absent

    _rows, frozen, _skipped, missing, _carried = fe.freeze_files(
        tmp_path / "data", tmp_path / "out", "v7", NOW, set(), names
    )

    assert (frozen, missing) == (1, 1)


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    names = ["ground_truth.csv", "ghost_trips.csv"]
    _write_sources(tmp_path / "data", names)

    rows, frozen, _skipped, _missing, _carried = fe.freeze_files(
        tmp_path / "data", tmp_path / "out", "v7", NOW, set(), names, dry_run=True
    )

    assert frozen == 2
    assert len(rows) == 2  # the plan is still reported for review
    assert not (tmp_path / "out").exists()  # no dir, no archives
