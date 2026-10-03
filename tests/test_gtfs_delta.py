"""Tests for scripts/gtfs_delta.py (GTFS identity delta between archived zips)."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gtfs_delta


def _make_zip(
    path: Path,
    routes: list[tuple[str, str, str]],
    stops: list[tuple[str, str]],
    *,
    bom: bool = False,
) -> Path:
    """Build a minimal GTFS zip; routes are (id, short, long)."""
    routes_csv = "route_id,route_short_name,route_long_name\n" + "\n".join(
        f"{rid},{short},{long}" for rid, short, long in routes
    )
    stops_csv = "stop_id,stop_name,stop_lat,stop_lon\n" + "\n".join(
        f"{sid},{name},43.5,-79.6" for sid, name in stops
    )
    if bom:  # real MiWay feeds carry a UTF-8 BOM
        routes_bytes = b"\xef\xbb\xbf" + routes_csv.encode("utf-8")
        stops_bytes = b"\xef\xbb\xbf" + stops_csv.encode("utf-8")
    else:
        routes_bytes = routes_csv.encode("utf-8")
        stops_bytes = stops_csv.encode("utf-8")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("routes.txt", routes_bytes)
        zf.writestr("stops.txt", stops_bytes)
    return path


@pytest.fixture()
def old_zip(tmp_path: Path) -> Path:
    return _make_zip(
        tmp_path / "old.zip",
        [("1", "1", "Dundas"), ("2", "2", "Hurontario")],
        [("S1", "Main St"), ("S2", "Elm St")],
    )


@pytest.fixture()
def new_zip(tmp_path: Path) -> Path:
    return _make_zip(
        tmp_path / "new.zip",
        [("1", "1", "Dundas"), ("3", "3", "Bloor")],
        [("S1", "Main St"), ("S3", "Oak St")],
    )


def test_delta_reports_added_and_removed(old_zip: Path, new_zip: Path) -> None:
    d = gtfs_delta.delta(old_zip, new_zip)

    assert d["routes_added"] == ["3"]
    assert d["routes_removed"] == ["2"]
    assert d["stops_added"] == ["S3"]
    assert d["stops_removed"] == ["S2"]


def test_identical_feeds_produce_empty_delta(old_zip: Path, tmp_path: Path) -> None:
    same = _make_zip(
        tmp_path / "same.zip",
        [("1", "1", "Dundas"), ("2", "2", "Hurontario")],
        [("S1", "Main St"), ("S2", "Elm St")],
    )

    assert gtfs_delta.delta(old_zip, same) == {
        "routes_added": [],
        "routes_removed": [],
        "stops_added": [],
        "stops_removed": [],
    }


def test_bom_encoded_fixture_is_read_correctly(tmp_path: Path) -> None:
    a = _make_zip(
        tmp_path / "a.zip", [("1", "1", "Dundas")], [("S1", "Main St")], bom=True
    )
    b = _make_zip(
        tmp_path / "b.zip",
        [("1", "1", "Dundas"), ("9", "9", "Lakeshore")],
        [("S1", "Main St")],
        bom=True,
    )

    # A BOM before the header must not corrupt the route_id column: if it
    # did, route 1 would surface as a phantom add+remove pair.
    d = gtfs_delta.delta(a, b)
    assert d == {
        "routes_added": ["9"],
        "routes_removed": [],
        "stops_added": [],
        "stops_removed": [],
    }


def test_real_archive_pair_is_identical_on_identity(tmp_path: Path) -> None:
    """The Sept 7 changeover was capacity-not-identity: no route/stop ID changes.

    Ground truth: 67 routes and 4085 stops in both pre-sept7 and post-sept7
    archives (measured 2026-09-24; see docs/runs/spacealpha-investigation-2026-09-24.md).
    Skipped when the local archives are absent.
    """
    archive = Path(__file__).resolve().parents[2] / "docs" / "sources" / "gtfs_archive"
    old = archive / "miway_gtfs_2026-08-23_pre-sept7.zip"
    new = archive / "miway_gtfs_2026-09-11_post-sept7.zip"
    if not (old.is_file() and new.is_file()):
        pytest.skip("real GTFS archives not present")

    assert len(gtfs_delta.route_ids(old)) == 67
    assert len(gtfs_delta.stop_ids(old)) == 4085
    assert gtfs_delta.delta(old, new) == {
        "routes_added": [],
        "routes_removed": [],
        "stops_added": [],
        "stops_removed": [],
    }


def test_route_names_prefers_short_name(tmp_path: Path) -> None:
    z = _make_zip(
        tmp_path / "n.zip", [("10", "10", "Bristol-Brampton")], [("S1", "Main St")]
    )
    assert gtfs_delta.route_names(z) == {"10": "10"}


def test_markdown_report_names_routes_and_handles_identical(
    old_zip: Path, new_zip: Path
) -> None:
    md = gtfs_delta.delta_markdown(old_zip, new_zip)
    assert "`3` 3" in md  # added route, named from the NEW zip's short name
    assert "`2` (name unavailable)" in md  # removed route: not in new zip
    assert "`S3`" in md and "`S2`" in md

    identical = gtfs_delta.delta_markdown(old_zip, old_zip)
    assert "No route or stop identity changes." in identical


def test_cli_json_and_md_to_file(old_zip: Path, new_zip: Path, tmp_path: Path) -> None:
    out = tmp_path / "delta.json"
    rc = gtfs_delta.main(
        ["--old", str(old_zip), "--new", str(new_zip), "--out", str(out)]
    )
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["routes_added"] == ["3"]

    out_md = tmp_path / "delta.md"
    rc = gtfs_delta.main(
        [
            "--old",
            str(old_zip),
            "--new",
            str(new_zip),
            "--format",
            "md",
            "--out",
            str(out_md),
        ]
    )
    assert rc == 0
    assert "GTFS identity delta" in out_md.read_text(encoding="utf-8")
