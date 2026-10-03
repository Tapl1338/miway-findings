"""Unit tests for the T52 EXPECTED reclassification guard in
``scripts/ghost_corridor_forensics.py`` (construction stop-relocation join).

The guard must be conservative: it only moves off-corridor pins into EXPECTED
when an alert names a displaced stop on the same route inside the pin's
corridor during the pin's window. No network, no data writes.
"""

from scripts.ghost_corridor_forensics import (
    _period_overlaps_window,
    relocation_explains,
)

EDT = -4 * 3600  # beat the module constant's convention; epochs are absolute here

# A corridor bbox near the origin; relocated stop "1950" sits inside it.
_LAT0, _LAT1 = 43.580, 43.600
_LON0, _LON1 = -79.640, -79.620
_PIN_START = (
    2_000_000_000  # placeholder; not used for epoch-overlap tests that set their own
)
_PIN_END = _PIN_START + 3600


def _alert(**over):
    base = {
        "routes": ["103"],
        "effect": 9,  # STOP_MOVED
        "cause": 10,  # CONSTRUCTION
        "active_periods": [{"start_epoch": _PIN_START, "end_epoch": _PIN_END}],
        "relocated_stop": "1950",
    }
    base.update(over)
    return base


# Bbox-consistent stops: relocated stop 1950 inside, 9999 outside.
_STOPS = {
    "1950": (_LAT0 + 0.002, _LON0 + 0.002),
    "9999": (_LAT0 + 0.2, _LON0 + 0.2),
}


def test_all_conditions_hold_reclassifies():
    assert relocation_explains(
        "103", _PIN_START, _PIN_END, _LAT0, _LAT1, _LON0, _LON1, [_alert()], _STOPS
    )


def test_route_mismatch_refuses():
    assert not relocation_explains(
        "17", _PIN_START, _PIN_END, _LAT0, _LAT1, _LON0, _LON1, [_alert()], _STOPS
    )


def test_stop_outside_corridor_refuses():
    a = _alert(relocated_stop="9999")
    assert not relocation_explains(
        "103", _PIN_START, _PIN_END, _LAT0, _LAT1, _LON0, _LON1, [a], _STOPS
    )


def test_not_relocation_family_refuses():
    # same route/stop but DETOUR (effect 4) or no CONSTRUCTION cause
    assert not relocation_explains(
        "103",
        _PIN_START,
        _PIN_END,
        _LAT0,
        _LAT1,
        _LON0,
        _LON1,
        [_alert(effect=4, cause=10)],
        _STOPS,
    )
    assert not relocation_explains(
        "103",
        _PIN_START,
        _PIN_END,
        _LAT0,
        _LAT1,
        _LON0,
        _LON1,
        [_alert(effect=9, cause=7)],
        _STOPS,
    )


def test_missing_named_stop_refuses():
    assert not relocation_explains(
        "103",
        _PIN_START,
        _PIN_END,
        _LAT0,
        _LAT1,
        _LON0,
        _LON1,
        [_alert(relocated_stop=None)],
        _STOPS,
    )


def test_period_overlap_bound_pin_before_alert_start():
    assert not _period_overlaps_window(
        [{"start_epoch": 1000, "end_epoch": 2000}], pin_start=0, pin_end=500
    )
    assert _period_overlaps_window(
        [{"start_epoch": 1000, "end_epoch": 2000}], pin_start=1500, pin_end=2500
    )


def test_period_open_ended_matches():
    assert _period_overlaps_window(
        [{"start_epoch": 1000, "end_epoch": None}], pin_start=9000, pin_end=9500
    )
    assert _period_overlaps_window(
        [{"start_epoch": None, "end_epoch": 10_000}], pin_start=0, pin_end=500
    )
