"""Unit tests for the plain-text email extraction in build_councillor_email."""

from scripts.build_councillor_email import (
    _coverage_ok,
    _ghost_rate_phrase,
    latest_ghost_day,
    plain_email,
    ward9_early_stats,
)

# A duplicated stop name that spans wards: MiWay reuses "Central Pky At
# Burnhamthorpe Rd" for stop 0653 (Ward 6) and stops 3283/3284 (Ward 4). A
# name-keyed join would collapse these to one ward.
_DUP = "central pky at burnhamthorpe rd"
_WARD_ROWS_ID = [
    {"stop_id": "0653", "stop_name": _DUP, "ward": "6"},
    {"stop_id": "3283", "stop_name": _DUP, "ward": "4"},
    {"stop_id": "3284", "stop_name": _DUP, "ward": "4"},
]
_STOPS = [
    {"stop_id": "0653", "stop_name": _DUP},
    {"stop_id": "3283", "stop_name": _DUP},
    {"stop_id": "3284", "stop_name": _DUP},
]


def _lat_row(stop_id: str, lat: float) -> dict:
    return {
        "stop_id": stop_id,
        "horizon_minutes": "-1",
        "lateness_minutes": str(lat),
    }


def test_ward9_resolves_dup_name_by_stop_id_not_name() -> None:
    # Same name (_DUP) on two stops in different wards; the id-keyed file must
    # keep them distinct. Under a name-keyed join, whichever ward won the dict
    # (the last row, "4") would apply to every stop of that name.
    ward = [
        {"stop_id": "0653", "stop_name": _DUP, "ward": "9"},
        {"stop_id": "3283", "stop_name": _DUP, "ward": "4"},
        {"stop_id": "3284", "stop_name": _DUP, "ward": "4"},
    ]
    rows = [_lat_row("0653", -5) for _ in range(5200)]  # all early, id 0653
    out = ward9_early_stats(rows, ward, _STOPS)
    assert out is not None and out["w9_n"] == 5200 and out["w9_pct"] == 100.0
    # If the join had been name-keyed, 0653 would resolve to the last "4" write
    # (w9 = 0) and ward9_early_stats would return None -- the assert above guards it.


def _sample_markdown() -> str:
    return (
        "# Councillor Email Draft \u2014 Ward 9 (Martin Sample)\n"
        "\n"
        "**Regenerated:** 2026-08-22 19:31\n"
        "\n"
        "Re-run `python scripts/build_councillor_email.py` before sending.\n"
        "\n"
        "---\n"
        "\n"
        "**Subject: Test line for the send check**\n"
        "\n"
        "Hi Councillor Sample,\n"
        "\n"
        "Para one wraps here\n"
        "and continues on the next line,\n"
        "ending with a `calibration.json` mention.\n"
        "\n"
        "Thanks,\n"
        "\n"
        "[Name], Ward 9 constituent, [School]\n"
        "\n"
        "---\n"
        "\n"
        "## Key numbers\n"
        "\n"
        "| Claim | Value |\n"
    )


def test_plain_keeps_only_the_sendable_body() -> None:
    out = plain_email(_sample_markdown())
    assert out.startswith("Subject: Test line for the send check")
    assert "Hi Councillor Sample," in out
    assert out.rstrip().endswith("[Name], Ward 9 constituent, [School]")


def test_plain_drops_header_and_audit_sections() -> None:
    out = plain_email(_sample_markdown())
    assert "Regenerated" not in out
    assert "# Councillor" not in out
    assert "Key numbers" not in out


def test_plain_strips_markdown_markers() -> None:
    out = plain_email(_sample_markdown())
    assert "**" not in out
    assert "`" not in out
    assert "calibration.json" in out


def test_plain_unwraps_hard_wrapped_paragraphs() -> None:
    out = plain_email(_sample_markdown())
    assert (
        "Para one wraps here and continues on the next line, ending with "
        "a calibration.json mention."
    ) in out


def test_plain_preserves_paragraph_breaks() -> None:
    out = plain_email(_sample_markdown())
    assert "\n\n" in out
    paragraphs = [p for p in out.strip().split("\n\n")]
    assert "Thanks," in paragraphs
    assert "[Name], Ward 9 constituent, [School]" in paragraphs


def test_ghost_rate_excludes_rotation_poisoned_days() -> None:
    """Vintage policy: low-coverage days must not deflate the window rate.

    Regression for the 2026-09-11 ghost-vintage audit finding: the draft's
    'one in 169' came from mixing August rows computed over pruned snapshots
    (27-72% uncovered) into a whole-file aggregate.
    """
    rows = [
        # Healthy current-era days (high coverage).
        {
            "service_date": "2026-09-10",
            "route_short_name": "2",
            "verifiable_trips": "5564",
            "ghost_count": "22",
            "uncovered_trips": "1",
        },
        {
            "service_date": "2026-09-11",
            "route_short_name": "2",
            "verifiable_trips": "3413",
            "ghost_count": "14",
            "uncovered_trips": "0",
        },
        # Rotation-poisoned August day: 30% uncovered, must be excluded.
        {
            "service_date": "2026-08-18",
            "route_short_name": "2",
            "verifiable_trips": "3000",
            "ghost_count": "3",
            "uncovered_trips": "900",
        },
        # Under-covered day: below the 2,000-trip floor, must be excluded.
        {
            "service_date": "2026-08-19",
            "route_short_name": "2",
            "verifiable_trips": "800",
            "ghost_count": "0",
            "uncovered_trips": "5",
        },
    ]
    g = latest_ghost_day(rows)
    assert g is not None
    cov = g["_coverage"]
    assert cov["ok_days"] == 2
    assert set(cov["excluded"]) == {"2026-08-18", "2026-08-19"}
    # Window aggregate covers only the two healthy days: 36 of 8,977 = 0.40%.
    assert g["all_verifiable"] == 8977
    assert g["all_ghosts"] == 36
    assert round(g["all_pct"], 1) == 0.4
    # The ask phrase uses the filtered basis, not the raw whole-file rate.
    phrase = _ghost_rate_phrase(g)
    assert "one in 249" in phrase  # round(100 / 0.4012) = 249
    assert "169" not in phrase


def test_ghost_rate_falls_back_to_pinned_basis_without_reliable_days() -> None:
    """With <2 reliable days the ask quotes the pinned August basis, labeled."""
    rows = [
        {
            "service_date": "2026-09-11",
            "route_short_name": "2",
            "verifiable_trips": "3413",
            "ghost_count": "14",
            "uncovered_trips": "0",
        },
        {
            "service_date": "2026-08-18",
            "route_short_name": "2",
            "verifiable_trips": "3000",
            "ghost_count": "3",
            "uncovered_trips": "900",
        },
    ]
    g = latest_ghost_day(rows)
    phrase = _ghost_rate_phrase(g)
    assert "one in 63" in phrase
    assert "historical basis" in phrase


def test_coverage_ok_thresholds() -> None:
    """_coverage_ok floors: ver>=2000 and uncovered/ver<=5%."""
    ok = {"verifiable_trips": "5564", "uncovered_trips": "1"}
    edge_in = {"verifiable_trips": "2000", "uncovered_trips": "100"}  # exactly 5%
    low_ver = {"verifiable_trips": "1999", "uncovered_trips": "0"}
    high_unc = {"verifiable_trips": "5000", "uncovered_trips": "251"}
    assert _coverage_ok(ok) is True
    assert _coverage_ok(edge_in) is True
    assert _coverage_ok(low_ver) is False
    assert _coverage_ok(high_unc) is False
    assert _coverage_ok({"verifiable_trips": ""}) is False
