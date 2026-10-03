import numpy as np
import pandas as pd
from scripts.realized_waits import (
    hhmmss_to_sec,
    load_events,
    realized_wait_stats,
    scheduled_pair_waits,
)


def test_hhmmss_to_sec():
    assert hhmmss_to_sec("06:00:00") == 21600
    assert hhmmss_to_sec("25:30:00") == 91800  # GTFS hours may exceed 24
    assert hhmmss_to_sec("bad") is None
    assert hhmmss_to_sec(None) is None


def _events():
    # Route A departs :00 and :40; route B departs :10 (one bus, big gap).
    return pd.DataFrame(
        {
            "route": ["A", "A", "B"],
            "dep_sec": [7 * 3600, 7 * 3600 + 2400, 7 * 3600 + 600],
            "platform": ["p1", "p1", "p2"],
        }
    )


def test_scheduled_pair_waits_math():
    out = scheduled_pair_waits(_events(), buffer_min=2.0)
    ab = out[(out.from_route == "A") & (out.to_route == "B")].iloc[0]
    # A@7:00 -> B@7:10 minus 2-min buffer = 8 min wait.
    # A@7:40 -> no B left that day → missed.
    assert ab.n_a_departures == 2
    assert ab.sched_mean_min == 8.0
    assert ab.missed_or_beyond_share == 0.5
    ba = out[(out.from_route == "B") & (out.to_route == "A")].iloc[0]
    # B@7:10 -> next A is 7:40: 28 min after buffer.
    assert ba.sched_mean_min == 28.0


def test_realized_deterministic_given_seed_and_shifts_mean():
    events = _events()
    zero = {"A": np.array([0.0]), "B": np.array([0.0])}
    # Delay only route B: every A rider waits longer, none gain.
    late_b = {"A": np.array([0.0]), "B": np.array([10.0, 12.0, 14.0, 16.0, 18.0, 20.0])}

    r_zero = realized_wait_stats(
        events, zero, np.array([0.0]), np.random.default_rng(7), iterations=20
    )
    r_late = realized_wait_stats(
        events, late_b, np.array([0.0]), np.random.default_rng(7), iterations=200
    )
    r_again = realized_wait_stats(
        events, late_b, np.array([0.0]), np.random.default_rng(7), iterations=200
    )
    pd.testing.assert_frame_equal(r_late, r_again)  # seed determinism

    zero_ab = r_zero[(r_zero.from_route == "A") & (r_zero.to_route == "B")].iloc[0]
    late_ab = r_late[(r_late.from_route == "A") & (r_late.to_route == "B")].iloc[0]
    assert zero_ab.realized_mean_min == 8.0
    # B delayed 10-20 min pushes its departure away from A's riders.
    assert late_ab.realized_mean_min >= 18.0
    assert late_ab.realized_mean_min > zero_ab.realized_mean_min


def test_realized_total_connection_loss_is_nan_safe():
    events = _events()
    # A delayed past B's single departure → no wait observations survive.
    pools = {"A": np.array([30.0, 40.0]), "B": np.array([0.0])}
    out = realized_wait_stats(
        events, pools, np.array([0.0]), np.random.default_rng(3), iterations=10
    )
    ab = out[(out.from_route == "A") & (out.to_route == "B")].iloc[0]
    # Pandas renders the None stats as NaN in float columns.
    assert pd.isna(ab.realized_mean_min)
    assert ab.realized_missed_share == 1.0


def test_load_events_filters_window(tmp_path, monkeypatch):
    gtfs = tmp_path / "gtfs"
    gtfs.mkdir()
    stops = pd.DataFrame(
        {
            "stop_id": ["0665", "9999"],
            "stop_name": ["X Town Centre Bus Terminal", "Other"],
        }
    )
    stop_times = pd.DataFrame(
        {
            "stop_id": ["0665", "0665", "9999"],
            "trip_id": ["t1", "t2", "t3"],
            "departure_time": [
                "05:30:00",
                "07:15:00",
                "08:00:00",
            ],  # first outside span
        }
    )
    trips = pd.DataFrame(
        {"trip_id": ["t1", "t2", "t3"], "route_id": ["r1", "r1", "r2"]}
    )
    routes = pd.DataFrame({"route_id": ["r1", "r2"], "route_short_name": ["10", "13"]})
    for name, frame in [
        ("stops.txt", stops),
        ("stop_times.txt", stop_times),
        ("trips.txt", trips),
        ("routes.txt", routes),
    ]:
        frame.to_csv(gtfs / name, index=False)

    ev = load_events(gtfs, "Town Centre Bus Terminal")
    assert list(ev.route) == ["10"]  # 05:30 dropped by the 06:00–22:00 span
    assert ev.dep_sec.iloc[0] == 7 * 3600 + 900


def test_load_events_service_date_filter(tmp_path):
    gtfs = tmp_path / "gtfs"
    gtfs.mkdir()
    stops = pd.DataFrame(
        {
            "stop_id": ["0665"],
            "stop_name": ["X Town Centre Bus Terminal"],
        }
    )
    stop_times = pd.DataFrame(
        {
            "stop_id": ["0665", "0665", "0665"],
            "trip_id": ["t1", "t2", "t3"],
            "departure_time": ["07:00:00", "07:15:00", "07:30:00"],
        }
    )
    # t1 runs on timetable block A; t2/t3 on block B.
    trips = pd.DataFrame(
        {
            "trip_id": ["t1", "t2", "t3"],
            "route_id": ["r1", "r1", "r2"],
            "service_id": ["A", "B", "B"],
        }
    )
    routes = pd.DataFrame({"route_id": ["r1", "r2"], "route_short_name": ["10", "13"]})
    # Block A ran only on the 24th; the queried date runs block B only.
    calendar_dates = pd.DataFrame(
        {
            "service_id": ["A", "B"],
            "date": ["20260824", "20260825"],
            "exception_type": ["1", "1"],
        }
    )
    for name, frame in [
        ("stops.txt", stops),
        ("stop_times.txt", stop_times),
        ("trips.txt", trips),
        ("routes.txt", routes),
        ("calendar_dates.txt", calendar_dates),
    ]:
        frame.to_csv(gtfs / name, index=False)

    ev = load_events(gtfs, "Town Centre Bus Terminal", service_date="2026-08-25")
    assert list(ev.route) == ["10", "13"]  # block-A trip (t1) dropped
    assert list(ev.dep_sec) == [7 * 3600 + 900, 7 * 3600 + 1800]
