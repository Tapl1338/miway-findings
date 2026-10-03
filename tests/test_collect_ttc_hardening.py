"""Unit tests for the TTC collector's hardening logic (T169, 2026-09-29).

Network-free: covers the night-throttle band math and the static-vintage
fingerprint reader. The live cadence gate (--cadence-test) remains the
acceptance test for the bind/feed path.
"""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.collect_ttc import (
    _effective_interval,
    _flatten_trip_updates,
    _night_interval,
    load_day_stats,
    prune_vp_files,
    read_static_feed_version,
)
from scripts.ttc_deadman import main as deadman_main


def _fake_zip(tmp_path: Path, feed_version: str | None) -> Path:
    zpath = tmp_path / "gtfs_surface.zip"
    names = ["routes.txt", "feed_info.txt"]
    contents = [
        b"route_id,route_short_name\n1,36\n",
        (
            "feed_publisher_name,feed_version\n"
            + (f"TTC,{feed_version}\n" if feed_version else "TTC,\n")
        ).encode(),
    ]
    with zipfile.ZipFile(zpath, "w") as zf:
        for name, data in zip(names, contents):
            zf.writestr(name, data)
    return zpath


class TestNightThrottle:
    def test_default_is_120s(self, monkeypatch):
        monkeypatch.delenv("TTC_COLLECT_NIGHT_INTERVAL", raising=False)
        assert _night_interval() == 120

    def test_zero_disables(self, monkeypatch):
        monkeypatch.setenv("TTC_COLLECT_NIGHT_INTERVAL", "0")
        assert _night_interval() == 0

    def test_night_band_throttled(self):
        dt = datetime(2026, 9, 29, 3, 0, tzinfo=ZoneInfo("America/Toronto"))
        assert _effective_interval(dt, 30.0) == 120.0

    def test_boundaries_stay_full_rate(self):
        toronto = ZoneInfo("America/Toronto")
        # 00:30 (after-midnight service) and 05:30 (morning ramp) are full rate.
        for hour, minute in ((0, 30), (5, 30), (12, 0), (23, 59)):
            dt = datetime(2026, 9, 29, hour, minute, tzinfo=toronto)
            assert _effective_interval(dt, 30.0) == 30.0, (hour, minute)


class TestVintageFingerprint:
    def test_reads_feed_version(self, tmp_path):
        zpath = _fake_zip(tmp_path, "S1000542")
        assert read_static_feed_version(zpath) == "S1000542"

    def test_missing_version_is_none(self, tmp_path):
        zpath = _fake_zip(tmp_path, None)
        assert read_static_feed_version(zpath) is None

    def test_missing_zip_is_none(self, tmp_path):
        assert read_static_feed_version(tmp_path / "nope.zip") is None

    def test_corrupt_zip_is_none(self, tmp_path):
        zpath = tmp_path / "bad.zip"
        zpath.write_bytes(b"not a zip")
        assert read_static_feed_version(zpath) is None


class TestNonSurfaceExclusion:
    """Out-of-universe routes count separately, never as unmatched."""

    @staticmethod
    def _feed(short_name: str | None):
        return {
            "header": {"timestamp": 1_790_000_000},
            "entity": [
                {
                    "trip_update": {
                        "trip": {"trip_id": "rt-1", "route_short_name": short_name},
                        "stop_time_update": [
                            {
                                "stop_sequence": 1,
                                "stop_id": "S1",
                                "departure": {"time": 1_790_000_060},
                                "schedule_relationship": 0,
                            }
                        ],
                    }
                }
            ],
        }

    MAPS = {
        "trip_to_short": {"t1": "36"},
        "stop_time_index": {},
        "trip_stops": {},
    }

    def test_subway_style_route_counts_as_non_surface(self):
        _, stats = _flatten_trip_updates(self._feed("600"), None, self.MAPS, 1800, 120)
        assert stats["non_surface"] == 1
        assert stats["unmatched"] == 0
        assert stats["decoded"] == 1

    def test_unknown_route_counts_as_non_surface(self):
        _, stats = _flatten_trip_updates(self._feed("999"), None, self.MAPS, 1800, 120)
        assert stats["non_surface"] == 1

    def test_surface_route_without_static_trip_is_unmatched(self):
        # In-universe route (has trips in static) but no stop_time_index entry
        # for this stop -> genuine unmatched (variant), NOT non_surface.
        _, stats = _flatten_trip_updates(self._feed("36"), None, self.MAPS, 1800, 120)
        assert stats["unmatched"] == 1
        assert stats["non_surface"] == 0


class TestVpPruning:
    def _make(self, data_dir: Path, stamp: str):
        f = data_dir / f"vehicles-{stamp}.jsonl"
        f.write_text("{}\n")
        return f

    def test_deletes_only_older_than_window(self, tmp_path):
        old = self._make(tmp_path, "20260901")
        edge = self._make(tmp_path, "20260927")  # keep=3: 27/28/29 stay
        keep = self._make(tmp_path, "20260928")
        today = self._make(tmp_path, "20260929")
        removed = prune_vp_files(tmp_path, "2026-09-29")  # default keep 3
        assert removed == 1
        assert not old.exists()
        assert edge.exists() and keep.exists() and today.exists()

    def test_zero_disables(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TTC_COLLECT_VP_KEEP_DAYS", "0")
        f = self._make(tmp_path, "20260901")
        assert prune_vp_files(tmp_path, "2026-09-29") == 0
        assert f.exists()


class TestDayStatsResume:
    def test_resumes_same_day(self, tmp_path):
        import json

        (tmp_path / "day-20260929.json").write_text(
            json.dumps({"date": "2026-09-29", "obs": 123, "polls_ok": 4})
        )
        stats = load_day_stats(tmp_path, "2026-09-29")
        assert stats["obs"] == 123

    def test_rejects_stale_day(self, tmp_path):
        import json

        (tmp_path / "day-20260928.json").write_text(
            json.dumps({"date": "2026-09-28", "obs": 9})
        )
        assert load_day_stats(tmp_path, "2026-09-29") == {}

    def test_missing_file_is_fresh(self, tmp_path):
        assert load_day_stats(tmp_path, "2026-09-29") == {}


class TestDeadman:
    """Advisory-only exit contract + state machine, exercised via main()."""

    def _fresh_hb(self, data_home: Path, stale_min: float = 0.0):
        import json

        hb_dir = data_home / "ttc"
        hb_dir.mkdir(parents=True, exist_ok=True)
        payload = {"last_poll_at": "2026-09-29T12:00:00-04:00", "pid": 1}
        if stale_min == 0.0:
            payload["last_poll_at"] = datetime.now(
                ZoneInfo("America/Toronto")
            ).isoformat(timespec="seconds")
        (hb_dir / "heartbeat.json").write_text(json.dumps(payload))

    def test_missing_heartbeat_alerts_and_exits_zero(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MIWAY_DATA_DIR", str(tmp_path))
        assert deadman_main([]) == 0  # advisory: never nonzero
        state_path = tmp_path / "ttc_deadman_state.json"
        assert state_path.exists()
        assert '"ttc_collector"' in state_path.read_text(encoding="utf-8")

    def test_recovery_clears_state(self, tmp_path, monkeypatch):
        import json

        monkeypatch.setenv("MIWAY_DATA_DIR", str(tmp_path))
        deadman_main([])  # alert first
        self._fresh_hb(tmp_path)
        assert deadman_main([]) == 0
        state = json.loads(
            (tmp_path / "ttc_deadman_state.json").read_text(encoding="utf-8")
        )
        assert state.get("ttc_collector") is None
