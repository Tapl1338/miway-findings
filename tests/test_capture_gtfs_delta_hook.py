"""T163: a CHANGED capture prints the route/stop identity delta vs the prior
archive, so the receipt answers WHAT changed, not just THAT the feed changed.

Contract: best-effort and strictly report-only — a delta failure must never
fail the capture itself (the zip and MANIFEST row are already safe by then).
"""

import zipfile
from pathlib import Path

from scripts import capture_gtfs_feed as cap


def _feed_zip(
    path: Path, route_ids: list[str], stop_ids: list[str], payload: str = "A"
) -> Path:
    """Minimal feed zip with controllable route/stop identity."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "routes.txt",
            "route_id,agency_id,route_short_name,route_long_name,route_type\n"
            + "\n".join(f"{r},1,{r},Route {r},3" for r in route_ids),
        )
        zf.writestr(
            "stops.txt",
            "stop_id,stop_name,stop_lat,stop_lon\n"
            + "\n".join(f"{s},Stop {s},43.5,-79.6" for s in stop_ids),
        )
        zf.writestr("calendar.txt", "service_id,monday,tuesday\nS1,1,1\n")
        zf.writestr(
            "stop_times.txt",
            f"trip_id,stop_id,stop_sequence,departure_time\ntrip1,stop1,1,08:00:00  # {payload}\n",
        )
        zf.writestr(
            "calendar_dates.txt",
            f"service_id,date,exception_type\nS1,20260823,1  # {payload}\n",
        )
    return path


def test_identity_delta_summary_diffs_two_zips(tmp_path):
    old = _feed_zip(tmp_path / "old.zip", ["1", "2"], ["s1", "s2"])
    new = _feed_zip(tmp_path / "new.zip", ["2", "3"], ["s2", "s3"], payload="B")
    out = cap.identity_delta_summary(old, new)
    assert out == "routes +1/-1, stops +1/-1"


def test_identity_delta_summary_identical(tmp_path):
    z = _feed_zip(tmp_path / "same.zip", ["1"], ["s1"])
    assert cap.identity_delta_summary(z, z) == "no route or stop identity changes"


def test_identity_delta_summary_never_raises_on_garbage(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    good = _feed_zip(tmp_path / "good.zip", ["1"], ["s1"])
    assert cap.identity_delta_summary(bad, good) is None
    assert cap.identity_delta_summary(good, bad) is None
    assert cap.identity_delta_summary(tmp_path / "missing.zip", good) is None
