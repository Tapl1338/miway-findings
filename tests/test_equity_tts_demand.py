"""Tests for the TTS 2022 ward-demand wiring in equity_report.py.

The equity view's ward table now carries Transportation Tomorrow Survey
zone-level transit demand (the public, downloadable demand source) next to
the stop-level impact figures, so a councillor sees both the measured change
AND the demand that experiences it. Pins: file parsing, TTS suppression
handling, the ward merge, and the transfer-share computation.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

_spec = importlib.util.spec_from_file_location(
    "equity_report_tts", BACKEND / "scripts" / "equity_report.py"
)
er = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = er
sys.path.insert(0, str(BACKEND / "scripts"))  # data_dir_util lives in scripts/
_spec.loader.exec_module(er)

REPO_TTS = Path("app/data/tts2022_mississauga_ward_transit.csv")


def test_tts_file_exists_and_parses():
    """The curated CSV must exist with all 11 wards and the expected columns."""
    assert er.TTS_WARD_CSV.exists(), f"missing {er.TTS_WARD_CSV}"
    tts = er._tts_demand()
    assert tts is not None
    assert sorted(tts.keys()) == list(range(1, 12))
    w9 = tts[9]
    assert w9["transit_trips_24h"] == 5574
    assert w9["transfer_trips_24h"] == 2779


def test_suppressions_are_null_not_imputed():
    """TTS '*' cells (<4 observations) must load as None, never zero."""
    tts = er._tts_demand()
    # Ward 1 had a suppressed 4+-routes cell; transfer trips are a sum so it
    # exists — but at least one ward must carry a None somewhere, and no
    # fabricated zeros may appear in the transfer-trips column of wards with
    # suppressed 3-route cells (wards 1, 9, 11).
    for w in (1, 9, 11):
        assert tts[w]["transit_trips_4plus_routes"] is None, (
            f"ward {w}: suppressed cell must stay None"
        )


def test_attach_enriches_ward_rows():
    """_attach_tts_demand must merge by ward number and compute share."""
    rows = [
        {"ward": "9", "delta_minutes": 2.56},
        {"ward": "7", "delta_minutes": 2.78},
        {"ward": "not-a-ward", "delta_minutes": 0.0},  # must be skipped
    ]
    data = {"wards": {"rows": rows}}
    assert er._attach_tts_demand(data) is True
    w9 = rows[0]
    assert w9["tts_transit_trips_24h"] == 5574
    assert w9["tts_transfer_trips_24h"] == 2779
    assert w9["tts_transfer_share_pct"] == 49.9
    assert rows[2].get("tts_transit_trips_24h") is None


def test_share_matches_components():
    """transfer share == transfer/trips*100 for every enriched ward."""
    tts = er._tts_demand()
    for w, t in tts.items():
        trips, transfer = t["transit_trips_24h"], t["transfer_trips_24h"]
        if trips and transfer is not None:
            share = round(transfer / trips * 100, 1)
            assert share == round(
                sum(
                    x
                    for x in (
                        t["transit_trips_2_routes"],
                        t["transit_trips_3_routes"],
                        t["transit_trips_4plus_routes"],
                    )
                    if x is not None
                )
                / trips
                * 100,
                1,
            ), f"ward {w} share inconsistent"


def test_canonical_equity_report_carries_tts():
    """The committed report must be TTS-enriched (runs on every suite pass,
    so the enrichment can't silently regress)."""
    report = json.loads(
        (REPO / "docs" / "equity-report.json").read_text(encoding="utf-8")
    )
    rows = report.get("wards", {}).get("rows", [])
    enriched = [r for r in rows if "tts_transit_trips_24h" in r]
    assert len(enriched) == len(rows) == 11, "all 11 wards must carry TTS data"
    assert any(r.get("tts_transfer_share_pct") is not None for r in rows)
    assert "tts2022_mississauga_ward_transit.csv" in str(
        report.get("input_fingerprints", {})
    )
