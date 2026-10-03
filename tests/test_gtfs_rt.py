"""Tests for the dependency-free GTFS-RT wire-format decoder."""

import struct

import pytest
from scripts.fetch_gtfs_rt import _miway_lateness_rows, MAX_PRED_DRIFT_MIN
from app.gtfs_rt import (
    decode_feed,
    decode_miway_trip_updates,
    decode_miway_vehicle_positions,
    miway_feed_timestamp,
    trip_update_rows,
    vehicle_position_rows,
)

# ---------------------------------------------------------------------------
# Minimal protobuf wire-format encoder for building test fixtures (no bindings)
# ---------------------------------------------------------------------------


def _varint(value: int) -> bytes:
    # Negative int32/int64 are sign-extended to 64-bit two's complement on the
    # wire; masking keeps the encode loop from looping forever on negatives.
    value &= 0xFFFFFFFFFFFFFFFF
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _key(field_num: int, wire: int) -> bytes:
    return _varint((field_num << 3) | wire)


def _field_str(field_num: int, text: str) -> bytes:
    data = text.encode("utf-8")
    return _key(field_num, 2) + _varint(len(data)) + data


def _field_varint(field_num: int, value: int) -> bytes:
    return _key(field_num, 0) + _varint(value)


def _field_msg(field_num: int, payload: bytes) -> bytes:
    return _key(field_num, 2) + _varint(len(payload)) + payload


def _field_float(field_num: int, value: float) -> bytes:
    return _key(field_num, 5) + struct.pack("<f", value)


def _stop_time_event(delay: int) -> bytes:
    # StopTimeEvent is a message whose field 1 is an int32 delay varint.
    return _field_varint(1, delay)


def _stop_time_update(seq: int, stop_id: str, delay: int) -> bytes:
    return _field_msg(
        3,
        _field_varint(1, seq)
        + _field_msg(3, _stop_time_event(delay))
        + _field_str(4, stop_id),
    )


def _trip_descriptor(trip_id: str) -> bytes:
    return _field_msg(1, _field_str(1, trip_id))


def _trip_update(trip_id: str, updates: list[bytes], delay: int | None = None) -> bytes:
    payload = _trip_descriptor(trip_id)
    for u in updates:
        payload += u
    if delay is not None:
        payload += _field_varint(5, delay)
    return _field_msg(2, payload)


def _entity(
    entity_id: str, trip_payload: bytes | None, vp_payload: bytes | None = None
) -> bytes:
    payload = _field_str(1, entity_id)
    if trip_payload is not None:
        payload += trip_payload
    if vp_payload is not None:
        payload += vp_payload
    return _field_msg(2, payload)


def _feed(*entities: bytes) -> bytes:
    header = _field_msg(1, _field_str(1, "2.0") + _field_varint(3, 1_700_000_000))
    return header + b"".join(entities)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_decodes_header_and_entities():
    raw = _feed(
        _entity("e1", _trip_update("T1", [_stop_time_update(1, "S1", 90)])),
        _entity("e2", _trip_update("T2", [_stop_time_update(2, "S2", -30)])),
    )
    feed = decode_feed(raw)
    assert feed["header"]["gtfs_realtime_version"] == "2.0"
    assert feed["header"]["timestamp"] == 1_700_000_000
    assert [e["id"] for e in feed["entity"]] == ["e1", "e2"]


def test_unknown_fields_are_skipped():
    # A field number we do not model (e.g. 9) must not break decoding.
    extra = _field_varint(9, 123) + _field_str(8, "unmodeled")
    raw = _feed(
        _entity("e1", _trip_update("T1", [_stop_time_update(1, "S1", 5)]) + extra)
    )
    rows = trip_update_rows(decode_feed(raw))
    assert rows == [
        {"trip_id": "T1", "stop_sequence": 1, "stop_id": "S1", "delay_seconds": 5.0}
    ]


def test_trip_update_rows_prefers_departure_delay():
    raw = _feed(
        _entity(
            "e1",
            _trip_update(
                "T1",
                [
                    _field_msg(
                        3,
                        _field_varint(1, 4)
                        + _field_msg(2, _stop_time_event(60))  # arrival delay +60s
                        + _field_msg(3, _stop_time_event(120))  # departure delay +120s
                        + _field_str(4, "S4"),
                    )
                ],
            ),
        )
    )
    rows = trip_update_rows(decode_feed(raw))
    assert rows == [
        {"trip_id": "T1", "stop_sequence": 4, "stop_id": "S4", "delay_seconds": 120.0}
    ]


def test_trip_update_rows_falls_back_to_arrival_and_trip_delay():
    # No departure event -> arrival delay used.
    raw = _feed(
        _entity(
            "e1",
            _trip_update(
                "T1",
                [
                    _field_msg(
                        3,
                        _field_varint(1, 2)
                        + _field_msg(2, _stop_time_event(45))
                        + _field_str(4, "S2"),
                    )
                ],
            ),
        )
    )
    rows = trip_update_rows(decode_feed(raw))
    assert rows[0]["delay_seconds"] == 45.0

    # No stop events at all -> trip-level delay used.
    raw = _feed(_entity("e2", _trip_update("T2", [], delay=75)))
    rows = trip_update_rows(decode_feed(raw))
    assert rows == [
        {"trip_id": "T2", "stop_sequence": None, "stop_id": None, "delay_seconds": 75.0}
    ]


def test_trip_update_rows_drops_entities_without_delay():
    raw = _feed(_entity("e1", _trip_update("T1", [])))  # no delay anywhere
    assert trip_update_rows(decode_feed(raw)) == []


def test_vehicle_position_rows():
    vp = (
        _field_msg(1, _field_str(1, "TRIP9"))
        + _field_msg(2, _field_str(1, "V42"))
        + _field_msg(3, _field_float(1, 43.6) + _field_float(2, -79.6))
        + _field_varint(7, 1_700_000_100)
    )
    raw = _feed(_entity("e1", None, vp_payload=_field_msg(3, vp)))
    rows = vehicle_position_rows(decode_feed(raw))
    assert len(rows) == 1
    r = rows[0]
    assert r["vehicle_id"] == "V42"
    assert r["trip_id"] == "TRIP9"
    assert abs(r["lat"] - 43.6) < 1e-3
    assert abs(r["lon"] - (-79.6)) < 1e-3
    assert r["timestamp"] == 1_700_000_100


def test_vehicle_position_rows_skips_missing_coordinates():
    vp = _field_msg(1, _field_str(1, "TRIP9"))  # no position
    raw = _feed(_entity("e1", None, vp_payload=_field_msg(3, vp)))
    assert vehicle_position_rows(decode_feed(raw)) == []


# ---------------------------------------------------------------------------
# MiWay vendor layout
# ---------------------------------------------------------------------------
# Entity: id(1 str), vehicle(3 msg). Vehicle: trip(1 msg), per-stop entry
# (2 msg, repeated). TripDescriptor: trip_id(1 str), start_time(2 str),
# service_date(3 str). Stop entry: stop_sequence(1 varint), arrival(2 msg),
# departure(3 msg), stop_id(4 str). Each event: predicted(2 varint),
# scheduled(4 varint).


def _vendor_event(predicted: int, scheduled: int) -> bytes:
    return _field_varint(2, predicted) + _field_varint(4, scheduled)


def _vendor_stop_entry(seq: int, stop_id: str, pred: int, sched: int) -> bytes:
    return _field_msg(
        2,
        _field_varint(1, seq)
        + _field_msg(3, _vendor_event(pred, sched))  # departure
        + _field_str(4, stop_id),
    )


def _vendor_trip_descriptor(trip_id: str, service_date: str) -> bytes:
    return _field_msg(1, _field_str(1, trip_id) + _field_str(3, service_date))


def _vendor_vehicle(trip_desc: bytes, *stop_entries: bytes) -> bytes:
    payload = trip_desc
    for e in stop_entries:
        payload += e
    return _field_msg(3, payload)


def _vendor_entity(entity_id: str, vehicle: bytes) -> bytes:
    return _field_msg(2, _field_str(1, entity_id) + vehicle)


def _vendor_feed(*entities: bytes, feed_ts: int = 1_700_000_000) -> bytes:
    header = _field_msg(1, _field_str(1, "2.0") + _field_varint(3, feed_ts))
    return header + b"".join(entities)


def test_miway_feed_timestamp():
    raw = _vendor_feed()
    assert miway_feed_timestamp(raw) == 1_700_000_000


def test_decode_miway_trip_updates_lateness():
    raw = _vendor_feed(
        _vendor_entity(
            "e1",
            _vendor_vehicle(
                _vendor_trip_descriptor("T1", "20260814"),
                _vendor_stop_entry(1, "S1", 1_700_000_000 + 90, 1_700_000_000),
                _vendor_stop_entry(2, "S2", 1_700_000_000 + 180, 1_700_000_000 + 60),
            ),
        )
    )
    rows = decode_miway_trip_updates(raw)
    assert len(rows) == 2
    r0 = rows[0]
    assert r0["trip_id"] == "T1"
    assert r0["service_date"] == "20260814"
    assert r0["stop_sequence"] == 1
    assert r0["stop_id"] == "S1"
    assert r0["scheduled_epoch"] == 1_700_000_000
    assert r0["predicted_epoch"] == 1_700_000_090
    assert r0["lateness_minutes"] == 1.5
    assert rows[1]["lateness_minutes"] == 2.0


def test_decode_miway_trip_updates_negative_lateness():
    raw = _vendor_feed(
        _vendor_entity(
            "e1",
            _vendor_vehicle(
                _vendor_trip_descriptor("T2", "20260814"),
                _vendor_stop_entry(1, "S1", 1_700_000_000 - 120, 1_700_000_000),
            ),
        )
    )
    rows = decode_miway_trip_updates(raw)
    assert rows[0]["lateness_minutes"] == -2.0  # running early


# ---------------------------------------------------------------------------
# Zombie-epoch guard (MAX_PRED_DRIFT_MIN) — fixture is the Sept 6 2026
# route 3/6 pattern: one on-time trip whose prediction never expired, so
# every poll re-recorded it drifting to +217 min while sibling headways
# ran on time (86 trip-stops, 421 polls on the worst, whole-history scan).
# ---------------------------------------------------------------------------


def _sept6_style_feed(lateness_min: float, horizon_min: float = 5.0) -> bytes:
    """One poll of trip 'Z' (the Sept 6 zombie shape): its scheduled time is
    long past, but the vendor still predicts it `horizon_min` ahead — so
    `lateness_min` of pure drift sits inside the collector's ±30-min
    recording window and would be re-recorded every poll."""
    feed_ts = 1_700_000_000
    pred = feed_ts + int(horizon_min * 60)
    sched = pred - int(lateness_min * 60)
    return _vendor_feed(
        _vendor_entity(
            "e1",
            _vendor_vehicle(
                _vendor_trip_descriptor("Z", "20260906"),
                _vendor_stop_entry(1, "1106", pred, sched),
            ),
        )
    )


def _static_lookup() -> tuple[dict, tuple[dict, dict]]:
    trip_to_short = {"Z": "6"}
    by_seq = {("Z", 1): ("1106", 929.0)}  # 15:29 scheduled dep
    by_stop = {("Z", "1106"): 929.0}
    return trip_to_short, (by_seq, by_stop)


def test_zombie_guard_drops_drifted_prediction():
    """A prediction 150 min past scheduled (the Sept 6 signature) is a dead
    epoch, not a bus: dropped, not recorded as a lateness observation."""
    raw = _sept6_style_feed(lateness_min=150.0)
    rows = _miway_lateness_rows(raw, *_static_lookup(), window_s=1800)
    assert rows == []


def test_zombie_guard_keeps_normal_lateness():
    """Ordinary lateness under the cutoff records exactly as before — the
    guard must not eat real observations (e.g. the 101's early-running
    work sits well under it, and real incident delays reach 30-60 min)."""
    raw = _sept6_style_feed(lateness_min=42.0, horizon_min=1.0)
    rows = _miway_lateness_rows(raw, *_static_lookup(), window_s=1800)
    assert len(rows) == 1
    assert rows[0]["lateness_minutes"] == 42.0
    assert rows[0]["route_short_name"] == "6"


def test_zombie_guard_boundary_is_strictly_over():
    """Drop is strictly-over the cutoff ("drifted more than 90 minutes"):
    exactly 90.0 still records, anything over drops. (Fixture times are
    whole seconds, so the smallest expressible step over the cutoff is
    +1 min.) The Sept 6 episode's rows began at +120.02 min — far past
    either side of this boundary."""
    at_cut = _miway_lateness_rows(
        _sept6_style_feed(lateness_min=MAX_PRED_DRIFT_MIN, horizon_min=1.0),
        *_static_lookup(),
        window_s=1800,
    )
    just_over = _miway_lateness_rows(
        _sept6_style_feed(lateness_min=MAX_PRED_DRIFT_MIN + 1, horizon_min=1.0),
        *_static_lookup(),
        window_s=1800,
    )
    assert len(at_cut) == 1
    assert just_over == []


def test_decode_miway_trip_updates_prefers_departure_event():
    entry = _field_msg(
        2,
        _field_varint(1, 3)
        + _field_msg(
            2, _vendor_event(1_700_000_000 + 60, 1_700_000_000)
        )  # arrival +1min
        + _field_msg(
            3, _vendor_event(1_700_000_000 + 300, 1_700_000_000)
        )  # departure +5min
        + _field_str(4, "S3"),
    )
    raw = _vendor_feed(
        _vendor_entity(
            "e1", _vendor_vehicle(_vendor_trip_descriptor("T3", "20260814"), entry)
        )
    )
    rows = decode_miway_trip_updates(raw)
    assert rows[0]["lateness_minutes"] == 5.0


def test_decode_miway_trip_updates_skips_unusable_entries():
    # Entry with no event pair -> dropped; entry with trip_id missing -> dropped.
    entry = _field_msg(2, _field_varint(1, 1) + _field_str(4, "S1"))  # no times
    raw = _vendor_feed(
        _vendor_entity(
            "e1", _vendor_vehicle(_vendor_trip_descriptor("T4", "20260814"), entry)
        )
    )
    assert decode_miway_trip_updates(raw) == []


# --- MiWay vendor vehicle positions --------------------------------------
# Entity field 4: trip(1 msg: trip_id@1 str, service_date@3 str), position
# (2 msg: lat@1 float32, lon@2 float32, bearing@3 float32), timestamp(5 varint),
# vehicle(8 msg: id@1 str), occupancy_status(9 varint), occupancy_percentage
# (10 varint).


def _vendor_vp_entity(
    trip_id: str,
    lat: float,
    lon: float,
    ts: int,
    vid: str,
    occ_status: int | None = 1,
    occ_pct: int | None = 40,
) -> bytes:
    trip = _field_msg(1, _field_str(1, trip_id) + _field_str(3, "20260814"))
    pos = _field_msg(
        2, _field_float(1, lat) + _field_float(2, lon) + _field_float(3, 316.0)
    )
    veh = _field_msg(8, _field_str(1, vid))
    body = trip + pos + _field_varint(5, ts) + veh
    if occ_status is not None:
        body += _field_varint(9, occ_status)
    if occ_pct is not None:
        body += _field_varint(10, occ_pct)
    return _field_msg(2, _field_str(1, vid) + _field_msg(4, body))


def test_decode_miway_vehicle_positions():
    raw = _vendor_feed(_vendor_vp_entity("T1", 43.6, -79.6, 1_700_000_100, "2112"))
    rows = decode_miway_vehicle_positions(raw)
    assert len(rows) == 1
    r = rows[0]
    assert r["vehicle_id"] == "2112"
    assert r["trip_id"] == "T1"
    assert abs(r["lat"] - 43.6) < 1e-5
    assert abs(r["lon"] - (-79.6)) < 1e-5
    assert r["bearing"] == 316.0
    assert r["timestamp"] == 1_700_000_100


def test_decode_miway_vehicle_positions_occupancy():
    # APC-derived crowding is on the standard GTFS-RT schema: field 9 is the
    # occupancy_status enum (1 = MANY_SEATS, 2 = FEW_SEATS, 3 =
    # STANDING_ROOM_ONLY) and field 10 is occupancy_percentage (0-100).
    raw = _vendor_feed(
        _vendor_vp_entity("T2", 43.6, -79.6, 1_700_000_100, "2112", 3, 80)
    )
    r = decode_miway_vehicle_positions(raw)[0]
    assert r["occupancy_status"] == 3
    assert r["occupancy_percentage"] == 80

    # A bus that has not reported occupancy keeps both fields None rather than
    # dropping the row or fabricating a value.
    raw = _vendor_feed(
        _vendor_vp_entity("T3", 43.6, -79.6, 1_700_000_100, "2113", None, None)
    )
    r = decode_miway_vehicle_positions(raw)[0]
    assert r["occupancy_status"] is None
    assert r["occupancy_percentage"] is None
    assert r["trip_id"] == "T3"


def test_decode_miway_vehicle_positions_skips_missing_position():
    # Trip descriptor present, no position -> dropped, no crash on odd bytes.
    trip = _field_msg(1, _field_str(1, "T1"))
    raw = _vendor_feed(_field_msg(2, _field_str(1, "x") + _field_msg(4, trip)))
    assert decode_miway_vehicle_positions(raw) == []


# ---------------------------------------------------------------------------
# Malformed-input hardening: bad bytes must raise, never hang or truncate
# ---------------------------------------------------------------------------


def test_truncated_varint_raises():
    from app.gtfs_rt import _parse_fields

    with pytest.raises(ValueError):
        _parse_fields(b"\xff")  # continuation bit with no terminator


def test_overlong_varint_raises():
    from app.gtfs_rt import _parse_fields

    with pytest.raises(ValueError):
        _parse_fields(b"\xff" * 11)  # 11 continuation bytes: > protobuf max


def test_negative_length_raises_instead_of_crawling_backwards():
    from app.gtfs_rt import _parse_fields

    # Field 1, wire type 2 (length-delimited), length varint encoding -1.
    payload = b"\x0a" + b"\xff" * 9 + b"\x01"
    with pytest.raises(ValueError):
        _parse_fields(payload)


def test_overlong_length_raises_instead_of_silently_truncating():
    from app.gtfs_rt import _parse_fields

    # Field 1, wire type 2, claims 200 bytes but only 4 follow.
    with pytest.raises(ValueError):
        _parse_fields(b"\x0a\xc8\x01\x02\x03\x04")


def test_field_number_zero_raises():
    from app.gtfs_rt import _parse_fields

    with pytest.raises(ValueError):
        _parse_fields(b"\x00")


def test_truncated_fixed32_raises():
    from app.gtfs_rt import _parse_fields

    # Field 1, wire type 5 (fixed32), only 2 of 4 bytes present.
    with pytest.raises(ValueError):
        _parse_fields(b"\x0d\x01\x02")


# ---------------------------------------------------------------------------
# Service Alerts decoder (T24)
# ---------------------------------------------------------------------------


def _translation(text: str) -> bytes:
    """Alert TranslatedString.translation: text(1) then language(2)."""
    return _field_msg(1, _field_str(1, text) + _field_str(2, "en"))


def _alert_entity(
    route_id: str,
    cause: int,
    effect: int,
    header: str,
    description: str,
    start_epoch: int,
    end_epoch: int,
) -> bytes:
    """One FeedEntity(2) carrying an Alert(5) in the MiWay vendor layout."""
    period = _field_msg(1, _field_varint(1, start_epoch) + _field_varint(2, end_epoch))
    selector = _field_msg(5, _field_str(2, route_id))
    alert = (
        period
        + selector
        + _field_varint(6, cause)
        + _field_varint(7, effect)
        + _field_msg(10, _translation(header))
        + _field_msg(11, _translation(description))
    )
    return _field_msg(2, _field_str(1, f"alert-{route_id}") + _field_msg(5, alert))


class TestDecodeMiwayAlerts:
    def test_decodes_alert_fields(self):
        from app.gtfs_rt import decode_miway_alerts

        feed = _feed(
            _alert_entity(
                "103",
                10,
                9,
                "103 Hurontario Express",
                "Stop relocated for construction",
                1710338760,
                1798779540,
            )
        )
        rows = decode_miway_alerts(feed)
        assert len(rows) == 1
        row = rows[0]
        assert row["routes"] == ["103"]
        assert row["cause"] == 10
        assert row["effect"] == 9
        assert row["header"] == "103 Hurontario Express"
        assert row["description"] == "Stop relocated for construction"
        assert row["active_periods"] == [
            {"start_epoch": 1710338760, "end_epoch": 1798779540}
        ]

    def test_multiple_alerts_and_routes(self):
        from app.gtfs_rt import decode_miway_alerts

        feed = _feed(
            _alert_entity("2", 10, 9, "2 Hurontario", "Stop moved", 1, 2),
            _alert_entity("17", 2, 7, "17 Hurontario", "Other", 3, 4),
        )
        rows = decode_miway_alerts(feed)
        assert len(rows) == 2
        assert [r["routes"] for r in rows] == [["2"], ["17"]]
        assert [r["effect"] for r in rows] == [9, 7]

    def test_empty_feed(self):
        from app.gtfs_rt import decode_miway_alerts

        assert decode_miway_alerts(_feed()) == []
