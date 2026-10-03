"""Unit tests for the ground-truth ride-along calibration reader.

Exercises `_ground_truth` against tmp CSVs: missing/empty files, the 20%
floor share + bucket distribution, per-route bias, and trust labels.
"""

import pytest
from app.routers import service_quality

_HEADER = (
    "ts,service_date,vehicle_id,trip_id,route,location,reported_pct,"
    "reported_status,counted_pax,vehicle_note,model_pax_at_65,notes,"
    "sched_time,actual_time\n"
)


def _write(tmp_path, rows: list[str]):
    p = tmp_path / "ground_truth.csv"
    p.write_text(_HEADER + "".join(rows), encoding="utf-8")
    return p


def _row(route, pct, counted, model):
    return (
        f"2026-08-18 12:00:00,20260818,3289,30310255,{route},Stop,{pct},1.0,"
        f"{counted},note,{model},note,12:00:00,\n"
    )


def test_ground_truth_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(service_quality, "_GROUND_TRUTH_CSV", tmp_path / "nope.csv")
    got = service_quality._ground_truth()
    assert got == {"available": False}


def test_ground_truth_empty(tmp_path, monkeypatch):
    p = _write(tmp_path, [])
    monkeypatch.setattr(service_quality, "_GROUND_TRUTH_CSV", p)
    assert service_quality._ground_truth()["available"] is False


def test_ground_truth_floor_and_buckets(tmp_path, monkeypatch):
    p = _write(
        tmp_path,
        [
            _row(42, 20, 12, 13),  # floor reading
            _row(42, 20, 15, 13),  # floor reading
            _row(42, 40, 28, 26),
            _row(57, 20, 10, 13),
            _row(57, 40, 20, 26),
        ],
    )
    monkeypatch.setattr(service_quality, "_GROUND_TRUTH_CSV", p)
    got = service_quality._ground_truth()
    assert got["available"] is True
    assert got["n_checkins"] == 5
    # 3 of 5 check-ins sat at the 20% quantization floor.
    assert got["floor_share_pct"] == 60.0
    assert got["pct_buckets"] == {20: 3, 40: 2}


def test_ground_truth_route_bias_and_trust(tmp_path, monkeypatch):
    p = _write(
        tmp_path,
        [
            # Route 42: counted consistently ~10 pax above the 65-pax model
            # (the articulated-bus capacity mismatch) -> biased, n>=20.
            _row(42, 20, 22, 13)
            for _ in range(20)
        ]
        + [
            # Route 57: sensor matches counted closely -> validated, n>=20.
            _row(57, 20, 13, 13)
            for _ in range(20)
        ]
        + [_row(23, 40, 12, 13) for _ in range(5)],  # small n -> insufficient
    )
    monkeypatch.setattr(service_quality, "_GROUND_TRUTH_CSV", p)
    got = service_quality._ground_truth()
    by_route = {r["route"]: r for r in got["routes"]}

    r42 = by_route["42"]
    assert r42["checkins"] == 20
    assert r42["bias_pax"] == pytest.approx(9.0)
    assert r42["trust"] == "biased"

    r57 = by_route["57"]
    assert r57["bias_pax"] == pytest.approx(0.0)
    assert r57["trust"] == "validated"

    r23 = by_route["23"]
    assert r23["trust"] == "insufficient"

    # Most-checked route first.
    assert got["routes"][0]["route"] in ("42", "57")


def test_ground_truth_route_id_clean(tmp_path, monkeypatch):
    p = _write(tmp_path, [_row(109, 20, 25, 13)])
    monkeypatch.setattr(service_quality, "_GROUND_TRUTH_CSV", p)
    got = service_quality._ground_truth()
    assert got["routes"][0]["route"] == "109"


# ---- _id / _ground_truth_trust unit branches (merged from the former
# test_service_quality_coverage.py; the aggregation itself is covered above) ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("42", "42"),
        ("42.0", "42"),
        (" 109 ", "109"),
        ("42E", "42E"),
        ("nan", "nan"),
    ],
)
def test_id_coercion(raw, expected):
    assert service_quality._id(raw) == expected


def test_id_coerces_float_cell():
    # A pandas cell that arrives as an actual float, not a string.
    assert service_quality._id(42.0) == "42"


@pytest.mark.parametrize(
    ("n", "bias", "expected"),
    [
        (25, 1.0, "validated"),
        (25, 5.0, "biased"),
        (12, 9.0, "directional"),
        (3, 9.0, "insufficient"),
    ],
)
def test_ground_truth_trust_bands(n, bias, expected):
    assert service_quality._ground_truth_trust(n, bias) == expected


def test_ground_truth_missing_columns(tmp_path, monkeypatch):
    # CSV exists but lacks the counted/model columns -> unavailable.
    p = tmp_path / "gt.csv"
    p.write_text("route,counted_pax\n42,20\n")
    monkeypatch.setattr(service_quality, "_GROUND_TRUTH_CSV", p)
    assert service_quality._ground_truth() == {"available": False}
