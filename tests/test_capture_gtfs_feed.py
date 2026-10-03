"""Unit tests for scripts/capture_gtfs_feed.py (T10 capture protocol).

T93 contract: change detection compares the CONTENT hash of the timetable
files inside the zip (stop_times/calendar/calendar_dates), not zip bytes —
a re-zipped identical feed is not a change. The baseline zip in the archive
directory is the single source of truth for "unchanged"; there is no
hardcoded baseline constant anymore.
"""

import zipfile
from pathlib import Path

import pytest
from scripts import capture_gtfs_feed as cap

# Arbitrary 16-hex-looking content hash used only where a test must force a
# value (dry-run decision path); the real-run tests derive hashes from zips.
BASELINE_CONTENT = "0123456789abcdef"


def _fake_zip(path: Path, payload: str = "A") -> Path:
    """Minimal feed zip: routes.txt drives route_sanity(); the three
    timetable files drive content_hash() (payload makes variants)."""
    routes = [str(r) for r in range(1, 68)]  # 1..67 incl. announced 8 and 66
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "routes.txt",
            "route_id,agency_id,route_short_name,route_long_name,route_type\n"
            + "\n".join(f"{r},1,{r},Route {r},3" for r in routes),
        )
        zf.writestr(
            "stop_times.txt",
            f"trip_id,stop_id,stop_sequence,departure_time\ntrip1,stop1,1,08:00:00  # {payload}\n",
        )
        zf.writestr("calendar.txt", "service_id,monday,tuesday\nS1,1,1\n")
        zf.writestr(
            "calendar_dates.txt",
            f"service_id,date,exception_type\nS1,20260823,1  # {payload}\n",
        )
    return path


def test_decide_filename_protocol():
    # Same content as the baseline -> change has NOT shipped.
    assert cap.decide_filename("aa11", "aa11", "2026-09-08") == (
        "miway_gtfs_2026-09-08_pre-change-still.zip"
    )
    # No baseline known, or different content -> treat as post-change.
    assert cap.decide_filename("aa11", None, "2026-09-08") == (
        "miway_gtfs_2026-09-08_post-sept7.zip"
    )
    assert cap.decide_filename("aa11", "bb22", "2026-09-08") == (
        "miway_gtfs_2026-09-08_post-sept7.zip"
    )


def test_decide_filename_change_id():
    # T150: a future changeover passes --change-id so automated captures
    # never label a new era with the old one's name.
    assert cap.decide_filename(
        "aa11", "bb22", "2026-10-27", change_id="post-oct26"
    ) == ("miway_gtfs_2026-10-27_post-oct26.zip")
    # The pre-change-still name is era-independent by design (it only ever
    # appears while the current era's change has not shipped).
    assert cap.decide_filename(
        "aa11", "aa11", "2026-10-27", change_id="post-oct26"
    ) == ("miway_gtfs_2026-10-27_pre-change-still.zip")


def test_manifest_row_layout():
    row = cap.manifest_row(
        "2026-09-08",
        "miway_gtfs_2026-09-08_post-sept7.zip",
        "deadbeef00000000",
        67,
        "Post-Sept-7 change",
    )
    assert row == (
        "| `miway_gtfs_2026-09-08_post-sept7.zip` | 2026-09-08 | "
        "`deadbeef00000000` | 67 | Post-Sept-7 change |"
    )


def test_route_sanity_counts_and_announced(tmp_path):
    z = _fake_zip(tmp_path / "feed.zip")
    count, present, _ = cap.route_sanity(z)
    assert count == 67
    assert set(present) == {"8", "66"}


def test_append_manifest_row_inserts_before_protocol(tmp_path):
    m = tmp_path / "MANIFEST.md"
    m.write_text(
        "| File | Captured | SHA-256 (first 16) | Routes | Why |\n"
        "|---|---|---|---|---|\n"
        "| `baseline.zip` | 2026-08-23 | `f43fb0a9de891dbd` | 67 | baseline |\n"
        "\nProtocol: capture again post-change.\n",
        encoding="utf-8",
    )
    ok = cap.append_manifest_row(
        m, "| `new.zip` | 2026-09-08 | `deadbeef00000000` | 67 | change |"
    )
    assert ok
    text = m.read_text(encoding="utf-8")
    # New row sits between the table and the Protocol note, exactly once.
    assert text.index("`new.zip`") > text.index("baseline.zip")
    assert text.index("`new.zip`") < text.index("Protocol:")
    assert text.count("`new.zip`") == 1


def test_append_manifest_row_bootstraps_missing_file(tmp_path):
    # T150: the headless (VPS) capture starts from an empty archive dir —
    # the first CHANGED capture must create the manifest, not crash.
    m = tmp_path / "MANIFEST.md"
    ok = cap.append_manifest_row(
        m, "| `new.zip` | 2026-09-08 | `deadbeef00000000` | 67 | change |"
    )
    assert ok
    text = m.read_text(encoding="utf-8")
    assert text.startswith("# GTFS feed archive")
    assert "| `new.zip` |" in text
    assert (
        cap.append_manifest_row(
            m, "| `new.zip` | 2026-09-08 | `deadbeef00000000` | 67 | change |"
        )
        is False
    )  # dedup still applies after bootstrap


def test_append_manifest_row_rejects_duplicate(tmp_path):
    m = tmp_path / "MANIFEST.md"
    m.write_text(
        "| File | Captured | SHA-256 (first 16) | Routes | Why |\n"
        "|---|---|---|---|---|\n"
        "\nProtocol: capture again post-change.\n",
        encoding="utf-8",
    )
    row = "| `new.zip` | 2026-09-08 | `deadbeef00000000` | 67 | change |"
    assert cap.append_manifest_row(m, row) is True
    assert cap.append_manifest_row(m, row) is False  # same filename
    row2 = "| `other.zip` | 2026-09-08 | `deadbeef00000000` | 67 | change |"
    assert cap.append_manifest_row(m, row2) is False  # same sha
    assert m.read_text(encoding="utf-8").count("new.zip") == 1


def test_existing_content_hashes_maps_hash_to_path(tmp_path):
    z = _fake_zip(tmp_path / "a.zip")
    assert cap.existing_content_hashes(tmp_path) == {cap.content_hash(z): z}


def test_baseline_content_sha_absent_returns_none(tmp_path):
    assert cap.baseline_content_sha(tmp_path) is None


def test_baseline_content_sha_reads_archived_baseline(tmp_path):
    z = _fake_zip(tmp_path / cap.BASELINE_FILENAME)
    assert cap.baseline_content_sha(tmp_path) == cap.content_hash(z)


def test_content_hash_ignores_zip_bytes_and_orders_deterministically(tmp_path):
    """Same timetable content in two differently-serialized zips -> same hash."""
    a = _fake_zip(tmp_path / "a.zip", payload="same")
    b = _fake_zip(tmp_path / "b.zip", payload="same")
    assert cap.content_hash(a) == cap.content_hash(b)
    c = _fake_zip(tmp_path / "c.zip", payload="different")
    assert cap.content_hash(a) != cap.content_hash(c)


def test_dry_run_unchanged_writes_nothing(tmp_path, monkeypatch, capsys):
    z = _fake_zip(tmp_path / "feed.zip")
    archive = tmp_path / "archive"
    archive.mkdir()
    manifest = tmp_path / "MANIFEST.md"
    manifest.write_text(
        "| File | Captured | SHA-256 (first 16) | Routes | Why |\n", encoding="utf-8"
    )
    # Force the decision inputs: every content hash equals the baseline.
    monkeypatch.setattr(cap, "content_hash", lambda _p: BASELINE_CONTENT)
    monkeypatch.setattr(cap, "baseline_content_sha", lambda _d: BASELINE_CONTENT)
    cap.main(
        [
            "--zip",
            str(z),
            "--archive-dir",
            str(archive),
            "--manifest",
            str(manifest),
            "--dry-run",
        ]
    )
    out = capsys.readouterr().out
    assert "UNCHANGED" in out
    assert "change has NOT shipped" in out
    assert (
        manifest.read_text(encoding="utf-8")
        == "| File | Captured | SHA-256 (first 16) | Routes | Why |\n"
    )
    assert not list(archive.iterdir())  # dry-run writes nothing to the real dir


def test_real_run_unchanged_saves_pre_change_still_only(tmp_path):
    """End-to-end: a feed with the baseline's timetable content is UNCHANGED."""
    archive = tmp_path / "archive"
    archive.mkdir()
    _fake_zip(archive / cap.BASELINE_FILENAME, payload="same")
    z = _fake_zip(tmp_path / "feed.zip", payload="same")
    manifest = tmp_path / "MANIFEST.md"
    original = "| File | Captured | SHA-256 (first 16) | Routes | Why |\n"
    manifest.write_text(original, encoding="utf-8")
    cap.main(
        ["--zip", str(z), "--archive-dir", str(archive), "--manifest", str(manifest)]
    )
    saved = [p for p in archive.glob("*.zip") if p.name != cap.BASELINE_FILENAME]
    assert len(saved) == 1
    assert saved[0].name.endswith("_pre-change-still.zip")
    # Protocol: no MANIFEST row for a non-change.
    assert manifest.read_text(encoding="utf-8") == original


def test_real_run_unchanged_no_save_flag(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    _fake_zip(archive / cap.BASELINE_FILENAME, payload="same")
    z = _fake_zip(tmp_path / "feed.zip", payload="same")
    manifest = tmp_path / "MANIFEST.md"
    manifest.write_text(
        "| File | Captured | SHA-256 (first 16) | Routes | Why |\n", encoding="utf-8"
    )
    cap.main(["--zip", str(z), "--archive-dir", str(archive), "--no-save-unchanged"])
    # Only the pre-existing baseline remains; no pre-change-still copy saved.
    assert [p.name for p in archive.glob("*.zip")] == [cap.BASELINE_FILENAME]


def test_real_run_changed_appends_manifest_row(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    _fake_zip(archive / cap.BASELINE_FILENAME, payload="baseline")
    z = _fake_zip(tmp_path / "feed.zip", payload="shipped")
    manifest = tmp_path / "MANIFEST.md"
    manifest.write_text(
        "| File | Captured | SHA-256 (first 16) | Routes | Why |\n"
        "|---|---|---|---|---|\n"
        "\nProtocol: capture again post-change.\n",
        encoding="utf-8",
    )
    cap.main(
        ["--zip", str(z), "--archive-dir", str(archive), "--manifest", str(manifest)]
    )
    saved = [p for p in archive.glob("*.zip") if p.name != cap.BASELINE_FILENAME]
    assert len(saved) == 1
    assert saved[0].name.startswith("miway_gtfs_") and "post-sept7" in saved[0].name
    text = manifest.read_text(encoding="utf-8")
    feed_hash = cap.content_hash(z)
    assert text.count(feed_hash) == 1
    assert "Post-Sept-7 change" in text


def test_changed_capture_without_manifest_write_fails(tmp_path, monkeypatch):
    """A change whose row cannot be recorded must exit nonzero (no silent loss)."""
    archive = tmp_path / "archive"
    archive.mkdir()
    _fake_zip(archive / cap.BASELINE_FILENAME, payload="baseline")
    z = _fake_zip(tmp_path / "feed.zip", payload="shipped")
    manifest = tmp_path / "MANIFEST.md"
    manifest.write_text(
        "| File | Captured | SHA-256 (first 16) | Routes | Why |\n", encoding="utf-8"
    )
    monkeypatch.setattr(cap, "append_manifest_row", lambda _m, _r: False)
    with pytest.raises(SystemExit) as exc:
        cap.main(
            [
                "--zip",
                str(z),
                "--archive-dir",
                str(archive),
                "--manifest",
                str(manifest),
            ]
        )
    assert "MANIFEST row not written" in str(exc.value)


def test_known_hashes_seed_prevents_false_changed(tmp_path):
    """T151: a fresh headless archive (no baseline) seeded with the laptop's
    known sha16s must report UNCHANGED for the current era, not re-record it
    as a CHANGED duplicate vintage."""
    archive = tmp_path / "archive"
    archive.mkdir()  # empty: exactly the bootstrap-VPS state
    z = _fake_zip(tmp_path / "feed.zip", payload="shipped")
    seed = tmp_path / "known_hashes.txt"
    seed.write_text(
        f"{cap.content_hash(z)} septic-era-via-syncthing\n", encoding="utf-8"
    )
    cap.main(
        [
            "--zip",
            str(z),
            "--archive-dir",
            str(archive),
            "--no-save-unchanged",
            "--known-hashes",
            str(seed),
        ]
    )
    # Nothing captured: the era was already frozen on the laptop side.
    assert [p.name for p in archive.glob("*.zip")] == []


def test_known_hashes_seed_ignores_comments_and_blanks(tmp_path):
    """Seed parsing: blank lines and #-comments are skipped, first-token sha
    is used, rest of the line is the label."""
    archive = tmp_path / "archive"
    archive.mkdir()
    z = _fake_zip(tmp_path / "feed.zip", payload="shipped")
    seed = tmp_path / "known_hashes.txt"
    seed.write_text(
        f"# generated by capture_feed.sh\n\n{cap.content_hash(z)} era label\n",
        encoding="utf-8",
    )
    cap.main(
        [
            "--zip",
            str(z),
            "--archive-dir",
            str(archive),
            "--no-save-unchanged",
            "--known-hashes",
            str(seed),
        ]
    )
    assert [p.name for p in archive.glob("*.zip")] == []


def test_prewarm_gate_skips_when_pytest_unavailable(tmp_path, monkeypatch, capsys):
    """T151: on a headless collector box pytest is absent by design; a genuine
    content change must still complete, with the gate reported SKIPPED."""
    monkeypatch.setattr(cap, "_pytest_available", lambda: False)
    archive = tmp_path / "archive"
    archive.mkdir()
    _fake_zip(archive / cap.BASELINE_FILENAME, payload="baseline")
    z = _fake_zip(tmp_path / "feed.zip", payload="shipped")
    manifest = tmp_path / "MANIFEST.md"
    manifest.write_text(
        "| File | Captured | SHA-256 (first 16) | Routes | Why |\n"
        "|---|---|---|---|---|\n"
        "\nProtocol: capture again post-change.\n",
        encoding="utf-8",
    )
    cap.main(
        ["--zip", str(z), "--archive-dir", str(archive), "--manifest", str(manifest)]
    )
    out = capsys.readouterr().out
    assert "PREWARM GATE: SKIPPED pytest unavailable (headless box)" in out
    saved = [p for p in archive.glob("*.zip") if p.name != cap.BASELINE_FILENAME]
    assert len(saved) == 1  # the change capture itself completed


# ---------------------------------------------------------------------------
# FQ-6 midnight-boundary check
# ---------------------------------------------------------------------------

_FQ6_HEADER = (
    "date,dep_time_min,horizon_minutes,route_short_name,stop_id,lateness_minutes\n"
)
TODAY = "2026-09-09"
TOMORROW = "2026-09-10"


def _fq6_csv(path: Path, rows: list[str]) -> Path:
    path.write_text(_FQ6_HEADER + "".join(rows), encoding="utf-8")
    return path


def test_fq6_pass_when_overnight_rows_stamped_today(tmp_path):
    csv = _fq6_csv(
        tmp_path / "obs_lateness.csv",
        [
            f"{TODAY},1445,0,10,123,0.0\n",  # 24:05 departure, physically 09-09
            f"{TODAY},1500,1,10,123,-1.0\n",
            f"{TODAY},700,0,10,123,0.0\n",  # pre-midnight: out of the band
        ],
    )
    v = cap.fq6_verdict(csv, TODAY)
    assert v["pass"] is True
    assert v["band_rows"] == 2
    assert v["new_rows"] == 2
    assert v["one_day_late"] == 0
    assert v["split"] == 0
    assert v["error"] is None


def test_fq6_fails_on_one_day_late_band(tmp_path):
    csv = _fq6_csv(tmp_path / "obs_lateness.csv", [f"{TOMORROW},1445,0,10,123,0.0\n"])
    v = cap.fq6_verdict(csv, TODAY)
    assert v["pass"] is False
    assert v["new_rows"] == 0
    assert v["one_day_late"] == 1


def test_fq6_fails_on_same_key_split(tmp_path):
    csv = _fq6_csv(
        tmp_path / "obs_lateness.csv",
        [
            f"{TODAY},1445,0,10,123,0.0\n",
            f"{TOMORROW},1445,0,10,123,0.0\n",  # same key, second night
        ],
    )
    v = cap.fq6_verdict(csv, TODAY)
    assert v["pass"] is False
    assert v["split"] == 1


def test_fq6_cross_night_key_does_not_count_as_split(tmp_path):
    """Same route/stop on different service nights is not a split."""
    csv = _fq6_csv(
        tmp_path / "obs_lateness.csv",
        [
            f"{TODAY},1445,0,10,123,0.0\n",
            f"{TODAY},1200,0,10,123,0.0\n",  # same route/stop, different dep
        ],
    )
    v = cap.fq6_verdict(csv, TODAY)
    assert v["pass"] is True
    assert v["split"] == 0


def test_fq6_fails_when_no_new_rows(tmp_path):
    csv = _fq6_csv(tmp_path / "obs_lateness.csv", [])
    v = cap.fq6_verdict(csv, TODAY)
    assert v["pass"] is False
    assert v["new_rows"] == 0


def test_fq6_missing_file_fails(tmp_path):
    v = cap.fq6_verdict(tmp_path / "nope.csv", TODAY)
    assert v["pass"] is False
    assert "cannot read" in v["error"]


def test_fq6_bad_date_fails(tmp_path):
    csv = _fq6_csv(tmp_path / "obs_lateness.csv", [f"{TODAY},1445,0,10,123,0.0\n"])
    v = cap.fq6_verdict(csv, "not-a-date")
    assert v["pass"] is False
    assert "bad --date" in v["error"]


def test_fq6_main_exit_codes(tmp_path, capsys):
    good = _fq6_csv(tmp_path / "good.csv", [f"{TODAY},1445,0,10,123,0.0\n"])
    with pytest.raises(SystemExit) as exc:
        cap.main(["--fq6", "--lateness-csv", str(good), "--date", TODAY])
    assert exc.value.code == 0
    assert "PASS" in capsys.readouterr().out
    bad = _fq6_csv(tmp_path / "bad.csv", [f"{TOMORROW},1445,0,10,123,0.0\n"])
    with pytest.raises(SystemExit) as exc:
        cap.main(["--fq6", "--lateness-csv", str(bad), "--date", TODAY])
    assert exc.value.code == 1
    assert "FAIL" in capsys.readouterr().out
