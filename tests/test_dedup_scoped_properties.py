"""T172 P1 test-first property suite.

Spec: ``docs/runs/t172-dedup-bounding-session-plan.md`` §4. Owner gate:
fixtures and property assertions land BEFORE any dedup code change.

GREEN today: the existing-rule contract tests (the MiWay rule already has
coverage in ``test_collect_service.py::test_dedup_csv_*``; the TTC rule had
NONE). They pin canonical semantics so P1 cannot silently change them.

SKIPPED until P1 lands: every property test is guarded on the implementation
contract below. The moment the constants exist, the guards lift and the
properties run — this file is simultaneously the red-phase spec and the
checklist.

P1 implementation contract (the guards read exactly these names):
  scripts.collect_ttc.STATE_NAME       watermark sidecar file NAME, sibling
                                       of the CSV: {"last_run": "YYYY-MM-DD"}
  scripts.collect_ttc.DROPPED_PREFIX   sidecar runs:
                                       ``<prefix><YYYYMMDDTHHMMSS>.csv.gz``
  scripts.collect_service.STATE_NAME / DROPPED_PREFIX   same semantics
  scripts.data_dir_util.atomic_write(path, write_fn)
                                       tmp + umask-mode restore + cloud sync
                                       retry + os.replace; write_fn(fh)
  dedup_csv(path) signature preserved: state file and dropped-row sidecar
                                       both live in path.parent (the data
                                       dir), derived from the CSV path alone.
  scope rule: dates >= (state last_run - 1); missing state => full run
  (today's behavior) then the state file is written.
  dropped rows (rule drops AND ``drop_malformed_rows`` drops) go to the
  sidecar with an extra ``drop_reason`` column; the canonical file keeps the
  input schema.

Properties encoded here:
  conservation   rows(input) == rows(canonical) ⊎ rows(sidecar)  (multiset,
                 values normalized numerically; sidecar read minus
                 drop_reason) — the literal "no data ever deleted" test.
  equivalence    watermark-scoped run == watermark-less full run as row
                 MULTISETS + closed-date head lines byte-preserved IN INPUT
                 ORDER. Order of the two outputs is deliberately NOT
                 compared: the full path horizon-sorts everything while the
                 scoped path leaves the closed-date head byte-verbatim (the
                 fixture writes its closed rows unsorted so that divergence
                 is real; both orders are order-insensitive to readers —
                 §3.6 reader inventory).
  fail-safe      a pathological pre-cutoff-dated pair appended after the
                 covering run survives scoped dedup (extra duplicate kept)
                 but is never dropped: full_canonical ⊆ scoped_canonical.
  catch-up       a stale watermark (outage) widens scope: dirty closed dates
                 still collapse, restoring equivalence.
  after-midnight a row with YESTERDAY's date written last in the file is
                 tail-scoped by DATE, not file position.
  crash-atomic   a mid-write failure leaves the previous file intact and
                 leaves no stray tmp behind.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import collect_service, collect_ttc, data_dir_util

TORONTO = ZoneInfo("America/Toronto")

# ---------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------


def _today() -> datetime:
    return datetime.now(TORONTO)


def _row(
    columns: list[str],
    *,
    route: str = "501",
    stop: str = "14022",
    dep: str = "480",
    lateness: str = "1.5",
    horizon: str = "-3",
    date: str = "",
    **extra: str,
) -> dict[str, str]:
    base = {
        "route_short_name": route,
        "stop_id": stop,
        "dep_time_min": dep,
        "lateness_minutes": lateness,
        "horizon_minutes": horizon,
        "date": date,
        "trip_id": "T1",
        "stop_sequence": "1",
        "schedule_relationship": "0",
    }
    base.update(extra)
    return {c: str(base.get(c, "")) for c in columns}


def _write_obs(path: Path, columns: list[str], rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _orig_lines(rows: list[dict[str, str]], columns: list[str]) -> list[str]:
    """Serialize fixture rows exactly as _write_obs did (for byte checks)."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().splitlines()


def _norm(rows: list[dict[str, str]]) -> Counter:
    """Value-normalized multiset: numeric fields compared as floats so a
    pandas round-trip ("480" -> "480.0") can't fake a conservation break.
    Keys are sorted so column ORDER differences (sidecar drop_reason aside)
    can't fake one either."""
    out: Counter = Counter()
    for row in rows:
        normed = []
        for key in sorted(row):
            value = row[key]
            try:
                normed.append((key, "n", float(value)))
            except (TypeError, ValueError):
                normed.append((key, "s", str(value)))
        out[tuple(normed)] += 1
    return out


def _dropped_rows(directory: Path, prefix: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for gz in sorted(directory.glob(f"{prefix}*.csv.gz")):
        with gzip.open(gz, "rt", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                row.pop("drop_reason", None)
                rows.append(row)
    return rows


def _write_state(directory: Path, module, last_run: datetime) -> None:
    (directory / module.STATE_NAME).write_text(
        json.dumps({"last_run": last_run.date().isoformat()}), encoding="utf-8"
    )


def _p1_ready(module) -> bool:
    return hasattr(module, "STATE_NAME") and hasattr(module, "DROPPED_PREFIX")


needs_p1_ttc = pytest.mark.skipif(
    not _p1_ready(collect_ttc),
    reason="T172 P1 not implemented yet (collect_ttc watermark + dropped sidecar)",
)
needs_p1_miway = pytest.mark.skipif(
    not _p1_ready(collect_service),
    reason="T172 P1 not implemented yet (collect_service watermark + dropped sidecar)",
)
needs_atomic_write = pytest.mark.skipif(
    not hasattr(data_dir_util, "atomic_write"),
    reason="T172 P1 not implemented yet (data_dir_util.atomic_write streaming helper)",
)


# ---------------------------------------------------------------------------
# GREEN today: existing-rule contract (pins canonical semantics for P1)
# ---------------------------------------------------------------------------


class TestExistingRuleContract:
    """The rule P1 must preserve verbatim (collect_ttc + shared with MiWay)."""

    def test_keeps_most_negative_horizon(self, tmp_path):
        today = _today().date().isoformat()
        cols = collect_ttc.CSV_COLUMNS
        rows = [
            _row(cols, horizon="-2", lateness="0.5", date=today),
            _row(cols, horizon="-5", lateness="2.5", date=today),
        ]
        out = _write_obs(tmp_path / "obs_lateness.csv", cols, rows)
        before, dropped = collect_ttc.dedup_csv(out)
        assert (before, dropped) == (2, 1)
        kept = _read_rows(out)
        assert len(kept) == 1
        assert kept[0]["horizon_minutes"] == "-5"
        assert kept[0]["lateness_minutes"] == "2.5"

    def test_date_is_part_of_the_key(self, tmp_path):
        cols = collect_ttc.CSV_COLUMNS
        yesterday = (_today().date() - timedelta(days=1)).isoformat()
        today = _today().date().isoformat()
        rows = [
            _row(cols, date=today, horizon="-3"),
            _row(cols, date=yesterday, horizon="-3"),
        ]
        out = _write_obs(tmp_path / "obs_lateness.csv", cols, rows)
        collect_ttc.dedup_csv(out)
        assert len(_read_rows(out)) == 2

    def test_idempotent(self, tmp_path):
        today = _today().date().isoformat()
        cols = collect_ttc.CSV_COLUMNS
        rows = [
            _row(cols, horizon="-1", date=today),
            _row(cols, horizon="-4", date=today),
            _row(cols, horizon="-9", date=today),
        ]
        out = _write_obs(tmp_path / "obs_lateness.csv", cols, rows)
        collect_ttc.dedup_csv(out)
        first = _read_rows(out)
        collect_ttc.dedup_csv(out)
        second = _read_rows(out)
        assert len(first) == len(second) == 1
        assert first == second

    def test_missing_file_is_zero_no_raise(self, tmp_path):
        assert collect_ttc.dedup_csv(tmp_path / "absent.csv") == (0, 0)

    def test_pair_at_file_end_collapses(self, tmp_path):
        """Today's full-file path collapses a duplicate pair no matter the
        position — the property the scoped path must keep for tail rows."""
        today = _today().date().isoformat()
        cols = collect_ttc.CSV_COLUMNS
        rows = [
            _row(cols, horizon="-3", date=today, dep="495"),
            _row(cols, horizon="-8", date=today, dep="495"),
        ]
        out = _write_obs(tmp_path / "obs_lateness.csv", cols, rows)
        collect_ttc.dedup_csv(out)
        kept = _read_rows(out)
        assert len(kept) == 1
        assert kept[0]["horizon_minutes"] == "-8"


# ---------------------------------------------------------------------------
# P1 properties: conservation — nothing is ever deleted
# ---------------------------------------------------------------------------


@needs_p1_ttc
def test_conservation_ttc(tmp_path):
    """rows(input) == rows(canonical) ⊎ rows(sidecar)."""
    today = _today().date().isoformat()
    yesterday = (_today().date() - timedelta(days=1)).isoformat()
    cols = collect_ttc.CSV_COLUMNS
    rows = [
        _row(cols, date=yesterday, horizon="-3"),
        _row(cols, date=yesterday, horizon="-7"),  # rule drop -> sidecar
        _row(cols, date=today, horizon="-2"),
        _row(cols, date=today, horizon="-6"),  # rule drop -> sidecar
    ]
    obs = _write_obs(tmp_path / "obs_lateness.csv", cols, rows)
    collect_ttc.dedup_csv(obs)
    canonical = _read_rows(obs)
    sidecar = _dropped_rows(tmp_path, collect_ttc.DROPPED_PREFIX)
    assert _norm(canonical) + _norm(sidecar) == _norm(rows), (
        "conservation broken: a row vanished or was invented"
    )
    assert len(sidecar) >= 1


@needs_p1_miway
def test_conservation_miway(tmp_path):
    """MiWay conservation — includes a malformed row that drop_malformed_rows
    must route to the sidecar instead of deleting."""
    from scripts.fetch_gtfs_rt import CSV_COLUMNS as MIWAY_COLS

    today = _today().date().isoformat()
    yesterday = (_today().date() - timedelta(days=1)).isoformat()
    rows = [
        _row(MIWAY_COLS, date=yesterday, horizon="-3"),
        _row(MIWAY_COLS, date=yesterday, horizon="-7"),  # rule drop
        _row(MIWAY_COLS, date=today, horizon="-4"),
        # corrupt append: non-numeric lateness -> drop_malformed -> sidecar
        _row(MIWAY_COLS, date=today, horizon="-1", lateness="not-a-number"),
    ]
    obs = _write_obs(tmp_path / "obs_lateness.csv", MIWAY_COLS, rows)
    collect_service.dedup_csv(obs)
    canonical = _read_rows(obs)
    sidecar = _dropped_rows(tmp_path, collect_service.DROPPED_PREFIX)
    assert _norm(canonical) + _norm(sidecar) == _norm(rows), (
        "conservation broken: a row vanished or was invented"
    )
    assert len(sidecar) >= 1


# ---------------------------------------------------------------------------
# P1 properties: equivalence — scoped == full (multiset), head byte-stable
# ---------------------------------------------------------------------------


@needs_p1_ttc
def test_equivalence_scoped_vs_full_ttc(tmp_path):
    now = _today().date()
    closed = (now - timedelta(days=3)).isoformat()
    yesterday = (now - timedelta(days=1)).isoformat()
    today = now.isoformat()
    cols = collect_ttc.CSV_COLUMNS
    # Closed dates are PRE-CLEAN (a real file's closed dates were deduped by
    # an earlier run) but written UNSORTED (-1 before -5) so the full path's
    # horizon sort and the scoped path's verbatim head genuinely diverge in
    # ORDER — the property is multiset equality + head bytes, not sequence.
    rows = [
        _row(cols, date=closed, horizon="-1", dep="610"),
        _row(cols, date=closed, horizon="-5", dep="300"),
        _row(cols, date=yesterday, horizon="-3", dep="480"),
        _row(cols, date=yesterday, horizon="-7", dep="480"),  # dup
        _row(cols, date=today, horizon="-2", dep="900"),
        _row(cols, date=today, horizon="-6", dep="900"),  # dup
    ]
    dir_a, dir_b = tmp_path / "a", tmp_path / "b"
    obs_a = _write_obs(dir_a / "obs_lateness.csv", cols, list(rows))
    obs_b = _write_obs(dir_b / "obs_lateness.csv", cols, list(rows))
    _write_state(dir_b, collect_ttc, _today())  # covers {yesterday, today}
    original_lines = _orig_lines(rows, cols)

    collect_ttc.dedup_csv(obs_a)  # unset state -> full
    collect_ttc.dedup_csv(obs_b)  # state present -> scoped

    canon_a = _norm(_read_rows(obs_a))
    canon_b = _norm(_read_rows(obs_b))
    assert canon_a == canon_b, "scoped != full row multiset"

    # Head byte-preservation: the closed-date lines appear in the scoped
    # output VERBATIM and IN INPUT ORDER (a sorted/pandas rewrite of the
    # head would reorder them and fail here).
    closed_in = [ln for ln in original_lines if closed in ln]
    closed_out = [
        ln for ln in obs_b.read_text(encoding="utf-8").splitlines() if closed in ln
    ]
    assert closed_in, "fixture lost its closed-date lines"
    assert closed_out == closed_in, "closed-date head was rewritten or reordered"


@needs_p1_ttc
def test_catchup_after_outage_ttc(tmp_path):
    """A stale watermark widens scope: dirty closed dates still collapse."""
    now = _today().date()
    closed = (now - timedelta(days=3)).isoformat()
    yesterday = (now - timedelta(days=1)).isoformat()
    today = now.isoformat()
    cols = collect_ttc.CSV_COLUMNS
    rows = [
        _row(cols, date=closed, horizon="-5", dep="300"),
        _row(cols, date=closed, horizon="-9", dep="300"),  # dirty closed dup
        _row(cols, date=yesterday, horizon="-3", dep="480"),
        _row(cols, date=yesterday, horizon="-7", dep="480"),
        _row(cols, date=today, horizon="-2", dep="900"),
    ]
    dir_a, dir_b = tmp_path / "a", tmp_path / "b"
    obs_a = _write_obs(dir_a / "obs_lateness.csv", cols, list(rows))
    obs_b = _write_obs(dir_b / "obs_lateness.csv", cols, list(rows))
    # outage: last successful run 5 days ago -> scope must reach back
    _write_state(dir_b, collect_ttc, _today() - timedelta(days=5))

    collect_ttc.dedup_csv(obs_a)
    collect_ttc.dedup_csv(obs_b)
    assert _norm(_read_rows(obs_a)) == _norm(_read_rows(obs_b)), (
        "stale watermark did not widen scope"
    )


@needs_p1_ttc
def test_fail_safe_keeps_late_appended_old_date_pair(tmp_path):
    """Boundary fails safe: a pre-cutoff-dated pair appended AFTER the
    covering run may survive scoped dedup (extra duplicate) but is never
    dropped — full_canonical ⊆ scoped_canonical."""
    now = _today().date()
    closed = (now - timedelta(days=3)).isoformat()
    today = now.isoformat()
    cols = collect_ttc.CSV_COLUMNS
    rows = [
        _row(cols, date=closed, horizon="-5", dep="300"),  # in head scope
        _row(cols, date=closed, horizon="-9", dep="300"),  # late duplicate,
        # appended after the run that already covered `closed`
        _row(cols, date=today, horizon="-2", dep="900"),
    ]
    dir_a, dir_b = tmp_path / "a", tmp_path / "b"
    obs_a = _write_obs(dir_a / "obs_lateness.csv", cols, list(rows))
    obs_b = _write_obs(dir_b / "obs_lateness.csv", cols, list(rows))
    _write_state(dir_b, collect_ttc, _today())  # scope = {yesterday, today}

    collect_ttc.dedup_csv(obs_a)
    collect_ttc.dedup_csv(obs_b)
    canon_a = _norm(_read_rows(obs_a))
    canon_b = _norm(_read_rows(obs_b))
    assert canon_a - canon_b == Counter(), (
        "scoped run dropped a row the full run keeps (not fail-safe)"
    )


@needs_p1_ttc
def test_after_midnight_row_is_date_scoped_not_position_scoped(tmp_path):
    """A yesterday-dated row written LAST in the file belongs to the active
    tail (date-based partition), so its twin collapses."""
    now = _today().date()
    yesterday = (now - timedelta(days=1)).isoformat()
    today = now.isoformat()
    cols = collect_ttc.CSV_COLUMNS
    rows = [
        _row(cols, date=yesterday, horizon="-3", dep="480"),
        _row(cols, date=today, horizon="-2", dep="900"),
        # appended last (after-midnight trip of service date `yesterday`):
        _row(cols, date=yesterday, horizon="-7", dep="480"),
    ]
    obs = _write_obs(tmp_path / "obs_lateness.csv", cols, rows)
    _write_state(tmp_path, collect_ttc, _today())
    collect_ttc.dedup_csv(obs)
    kept = [r for r in _read_rows(obs) if r["date"] == yesterday]
    assert len(kept) == 1
    assert kept[0]["horizon_minutes"] == "-7"


# ---------------------------------------------------------------------------
# P1 properties: crash-atomic writes
# ---------------------------------------------------------------------------


@needs_atomic_write
def test_atomic_write_failure_leaves_original_intact(tmp_path):
    target = tmp_path / "obs_lateness.csv"
    target.write_text("ORIGINAL\n", encoding="utf-8")

    def exploding_writer(fh):
        fh.write("PARTIAL-NEW-DATA\n")
        raise RuntimeError("simulated crash mid-dedup")

    with pytest.raises(RuntimeError, match="simulated crash"):
        data_dir_util.atomic_write(target, exploding_writer)

    assert target.read_text(encoding="utf-8") == "ORIGINAL\n"
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != target.name]
    assert leftovers == [], f"tmp litter left behind: {leftovers}"
