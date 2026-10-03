"""Unit tests for GTFS parsing kit functions."""

import pytest

from app.gtfs_kit import (
    time_to_min,
    norm_stop_id,
    headsign_variant,
    street_of,
    street_fingerprint,
    service_ids_on,
    latest_vintage_services,
    Feed,
    load_feed,
)


def test_time_to_min_basic():
    """Test time_to_min with basic HH:MM:SS format."""
    assert time_to_min("12:30:45") == 750.75  # 12*60 + 30 + 45/60
    assert time_to_min("00:00:00") == 0.0
    assert time_to_min("23:59:59") == 23 * 60 + 59 + 59 / 60


def test_time_to_min_over_24_hours():
    """Test time_to_min with times exceeding 24 hours (yesterday's service)."""
    assert time_to_min("25:00:00") == 25 * 60  # Next day 1:00 AM
    assert time_to_min("30:15:30") == 30 * 60 + 15 + 30 / 60


def test_time_to_min_edge_cases():
    """Test time_to_min with edge cases."""
    assert time_to_min(None) is None
    assert time_to_min("invalid") is None
    assert time_to_min("12:30") is None  # Missing seconds
    assert time_to_min("12:30:45:60") is None  # Too many parts
    assert time_to_min("ab:cd:ef") is None  # Non-numeric


def test_norm_stop_id_strips_zeros():
    """Test norm_stop_id strips leading zeros."""
    assert norm_stop_id("0264") == "264"
    assert norm_stop_id("000123") == "123"
    assert norm_stop_id("0") == "0"  # Edge case: all zeros
    # All-zeros passthrough: lstrip would produce '', and the module
    # deliberately never returns an empty id (join key must stay non-empty).
    assert norm_stop_id("0000") == "0000"


def test_norm_stop_id_non_numeric():
    """Test norm_stop_id with non-numeric IDs."""
    assert norm_stop_id("A1B2") == "A1B2"
    assert norm_stop_id("STOP_123") == "STOP_123"
    assert norm_stop_id("") == ""


def test_norm_stop_id_with_spaces():
    """Test norm_stop_id handles whitespace."""
    assert norm_stop_id("  0264  ") == "264"
    assert norm_stop_id("\t0264\n") == "264"


def test_headsign_variant_extracts_letter():
    """Test headsign_variant extracts branch letter."""
    assert headsign_variant("49A E Mcdowell To...", "49") == "A"
    assert headsign_variant("16B To Downtown", "16") == "B"
    assert headsign_variant("99Z Express", "99") == "Z"


def test_headsign_variant_returns_empty_when_no_match():
    """Test headsign_variant returns empty string when no branch letter."""
    assert headsign_variant("49 E Mcdowell To...", "49") == ""
    assert headsign_variant("16 To Downtown", "16") == ""
    assert headsign_variant("49A E Mcdowell", "50") == ""  # Wrong route


def test_headsign_variant_handles_none():
    """Test headsign_variant handles None inputs."""
    assert headsign_variant(None, "49") == ""
    assert headsign_variant("49A", None) == ""
    assert headsign_variant(None, None) == ""


def test_street_of_basic():
    """Test street_of extracts street names from stop names."""
    assert street_of("Main St At Oak Ave") == ("Main St", "Oak Ave")
    assert street_of("First Street At Second Street") == (
        "First Street",
        "Second Street",
    )
    assert street_of("Hwy 401 At Dixie Rd") == ("Hwy 401", "Dixie Rd")


def test_street_of_terminus_fallback():
    """Test street_of falls back for terminus/platform names."""
    assert street_of("Square One Terminal") == ("Square One Terminal", None)
    assert street_of("City Centre Platform 1") == ("City Centre", None)


def test_street_of_single_word():
    """Test street_of with single word names."""
    assert street_of("Terminal") == ("Terminal", None)
    assert street_of("Platform") == ("Platform", None)


def test_street_fingerprint_basic():
    """Test street_fingerprint determines main streets."""
    # Simple case: one street dominates. Oak Ave still clears the default
    # min_share=0.15 floor (1/3 of stops), so it is kept too.
    stops = ["Main St At 1st", "Main St At 2nd", "Oak Ave At Main"]
    assert street_fingerprint(stops) == "Main St → Oak Ave"


def test_service_ids_on_filters_by_date(monkeypatch, tmp_path):
    """Test service_ids_on filters service IDs by date using calendar_dates.txt."""
    # Create test calendar_dates.txt
    gtfs_dir = tmp_path
    cal_content = """service_id,date,exception_type
WEEKDAY_26AU03,20260801,1
WEEKDAY_26AU03,20260802,1
WEEKDAY_26SE07,20260907,1
WEEKDAY_26SE07,20260908,1
SATURDAY,20260801,1
SUNDAY,20260802,1
"""
    cal_file = gtfs_dir / "calendar_dates.txt"
    cal_file.write_text(cal_content)

    # Patch GTFS_DIR to point to our test directory
    import app.gtfs_kit as gtfs_kit

    monkeypatch.setattr(gtfs_kit, "GTFS_DIR", gtfs_dir)

    # Test date that has entries
    result = service_ids_on("2026-08-01")
    expected = {"WEEKDAY_26AU03", "SATURDAY"}
    assert result == expected

    # Test date with different entries
    result = service_ids_on("2026-09-07")
    expected = {"WEEKDAY_26SE07"}
    assert result == expected

    # Test date with no entries
    with pytest.raises(ValueError, match="no calendar_dates entry"):
        service_ids_on("2026-01-01")


def test_latest_vintage_services_returns_latest(monkeypatch, tmp_path):
    """Test latest_vintage_services returns services with latest date prefix."""
    gtfs_dir = tmp_path
    # Create test calendar_dates.txt using the REAL feed's id convention
    # ('<vintage>-<block>-<Kind>-<n>'); the module matches ``kind``
    # case-sensitively and takes the vintage prefix before the first '-'.
    cal_content = """service_id,date,exception_type
26AU03-CPBlock-Weekday-11,20260801,1
26SE07-CPBlock-Weekday-11,20260907,1
26AU03-CPBlock-Saturday-10,20260801,1
26SE07-CPBlock-Saturday-10,20260907,1
26AU03-CPBlock-Holiday-10,20260907,1
"""
    cal_file = gtfs_dir / "calendar_dates.txt"
    cal_file.write_text(cal_content)

    # Patch GTFS_DIR to point to our test directory
    import app.gtfs_kit as gtfs_kit

    monkeypatch.setattr(gtfs_kit, "GTFS_DIR", gtfs_dir)

    # Test for Weekday services - should get the SE07 vintages (later date)
    result = latest_vintage_services("Weekday")
    expected = {"26SE07-CPBlock-Weekday-11"}
    assert result == expected

    # Test for Saturday services - should get the SE07 vintages
    result = latest_vintage_services("Saturday")
    expected = {"26SE07-CPBlock-Saturday-10"}
    assert result == expected

    # Test for Holiday services - only AU03 exists, so AU03 is the latest
    result = latest_vintage_services("Holiday")
    expected = {"26AU03-CPBlock-Holiday-10"}
    assert result == expected

    # Test with non-matching kind
    result = latest_vintage_services("Nonexistent")
    assert result == set()


def test_load_feed_returns_feed_object(monkeypatch, tmp_path):
    """Test load_feed returns a Feed object with expected DataFrames."""
    # Create minimal GTFS files
    gtfs_dir = tmp_path

    # routes.txt
    routes_content = """route_id,route_short_name
route_1,10
route_2,20
"""
    (gtfs_dir / "routes.txt").write_text(routes_content)

    # trips.txt
    trips_content = """route_id,service_id,trip_id,trip_headsign
route_1,service_a,trip_1,10A Downtown
route_1,service_a,trip_2,10A Uptown
route_2,service_b,trip_3,20B East
"""
    (gtfs_dir / "trips.txt").write_text(trips_content)

    # stops.txt
    stops_content = """stop_id,stop_name,stop_lat,stop_lon
stop_1,Main St At 1st,43.0,-79.0
stop_2,Oak Ave At 2nd,43.1,-79.1
"""
    (gtfs_dir / "stops.txt").write_text(stops_content)

    # stop_times.txt
    stop_times_content = """trip_id,stop_id,stop_sequence,departure_time,arrival_time
trip_1,stop_1,1,08:00:00,08:00:00
trip_1,stop_2,2,08:05:00,08:05:00
trip_2,stop_1,1,08:10:00,08:10:00
trip_2,stop_2,2,08:15:00,08:15:00
trip_3,stop_1,1,09:00:00,09:00:00
trip_3,stop_2,2,09:05:00,09:05:00
"""
    (gtfs_dir / "stop_times.txt").write_text(stop_times_content)

    # Patch GTFS_DIR to point to our test directory
    import app.gtfs_kit as gtfs_kit

    monkeypatch.setattr(gtfs_kit, "GTFS_DIR", gtfs_dir)

    # Load feed
    feed = load_feed()

    # Assert it's a Feed object
    assert isinstance(feed, Feed)

    # Assert DataFrames have expected shapes/content
    assert len(feed.routes) == 2
    assert len(feed.trips) == 3
    assert len(feed.stops) == 2
    assert len(feed.stop_times) == 6

    # Check specific values
    assert feed.routes.iloc[0]["route_short_name"] == "10"
    assert feed.trips.iloc[0]["trip_headsign"] == "10A Downtown"
    assert feed.stops.iloc[0]["stop_name"] == "Main St At 1st"


def test_trip_table_computes_metrics(monkeypatch, tmp_path, request):
    """Test trip_table computes correct metrics for trips."""
    # Create minimal GTFS files. NOTE: call app.gtfs_kit.trip_table directly —
    # the conftest service_filtered_trips fixture reads the REAL feed and
    # ignores these tmp files (root cause of the old 'assert 2 == 1' failure).
    gtfs_dir = tmp_path

    # routes.txt
    routes_content = """route_id,route_short_name
route_1,10
"""
    (gtfs_dir / "routes.txt").write_text(routes_content)

    # trips.txt
    trips_content = """route_id,service_id,trip_id,trip_headsign
route_1,service_a,trip_1,10A Downtown
"""
    (gtfs_dir / "trips.txt").write_text(trips_content)

    # stops.txt
    stops_content = """stop_id,stop_name,stop_lat,stop_lon
stop_1,Main St At 1st,43.0,-79.0
stop_2,Oak Ave At 2nd,43.1,-79.1
stop_3,Elm St At 3rd,43.2,-79.2
"""
    (gtfs_dir / "stops.txt").write_text(stops_content)

    # stop_times.txt - trip with 3 stops
    stop_times_content = """trip_id,stop_id,stop_sequence,departure_time,arrival_time
trip_1,stop_1,1,08:00:00,08:00:00
trip_1,stop_2,2,08:05:00,08:05:00
trip_1,stop_3,3,08:10:00,08:10:00
"""
    (gtfs_dir / "stop_times.txt").write_text(stop_times_content)

    # calendar_dates.txt - service_a active on 2026-08-01
    cal_content = "service_id,date,exception_type\nservice_a,20260801,1\n"
    (gtfs_dir / "calendar_dates.txt").write_text(cal_content)

    # Patch GTFS_DIR AND clear load_feed's lru_cache — without the cache
    # reset the feed built from the REAL GTFS_DIR leaks into this test and
    # the table silently describes the wrong data (the old 'assert 3 == 1').
    # Clear again on teardown so the tmp feed never leaks the other way.
    import app.gtfs_kit as gtfs_kit

    monkeypatch.setattr(gtfs_kit, "GTFS_DIR", gtfs_dir)
    gtfs_kit.load_feed.cache_clear()
    request.addfinalizer(gtfs_kit.load_feed.cache_clear)

    from app.gtfs_kit import trip_table as trip_table_func

    table = trip_table_func()

    # Assert we have one row
    assert len(table) == 1
    row = table.iloc[0]

    # Check computed values
    assert row["route_short_name"] == "10"
    assert row["trip_headsign"] == "10A Downtown"
    # First departure: 08:00:00 = 8*60 = 480 minutes
    assert row["first_dep"] == 480.0
    # Runtime: 08:10:00 - 08:00:00 = 10 minutes
    assert row["runtime_min"] == 10.0
    # Number of stops: 3
    assert row["n_stops"] == 3
    # Variant: should extract 'A' from headsign
    assert row["variant"] == "A"
