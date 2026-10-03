import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, UTC
from pathlib import Path


def run_script(heartbeat_path, max_age_seconds=1800, json_output=False):
    """Run the heartbeat check script and return (exit_code, stdout, stderr)."""
    env = os.environ.copy()
    if "MIWAY_HEARTBEAT" in env:
        del env["MIWAY_HEARTBEAT"]  # Ensure we use the passed path
    cmd = [
        sys.executable,
        str(Path(__file__).parent.parent / "scripts" / "heartbeat_check.py"),
        f"--heartbeat-path={heartbeat_path}",
        f"--max-age-seconds={max_age_seconds}",
    ]
    if json_output:
        cmd.append("--json")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def test_fresh_heartbeat(tmp_path):
    """Test that a fresh heartbeat returns OK (exit 0)."""
    hb_file = tmp_path / "heartbeat.json"
    # Timestamp now (fresh)
    now = datetime.now(UTC)
    data = {"ts": now.timestamp()}
    hb_file.write_text(json.dumps(data))

    exit_code, stdout, stderr = run_script(str(hb_file))
    assert exit_code == 0
    assert "HEARTBEAT OK" in stdout
    assert stderr == ""


def test_stale_heartbeat(tmp_path):
    """Test that a stale heartbeat returns STALE (exit 2)."""
    hb_file = tmp_path / "heartbeat.json"
    # Timestamp older than max_age (1800 seconds = 30 minutes)
    stale_time = datetime.now(UTC) - timedelta(seconds=3600)  # 1 hour ago
    data = {"ts": stale_time.timestamp()}
    hb_file.write_text(json.dumps(data))

    exit_code, stdout, stderr = run_script(str(hb_file))
    assert exit_code == 2
    assert "HEARTBEAT STALE" in stderr
    assert stdout == ""


def test_malformed_heartbeat(tmp_path):
    """Test that a malformed heartbeat returns error (exit 3)."""
    hb_file = tmp_path / "heartbeat.json"
    hb_file.write_text("not valid json")

    exit_code, _stdout, stderr = run_script(str(hb_file))
    assert exit_code == 3
    if "--json" in sys.argv:  # This test doesn't use json, but we check both
        # In json mode, we expect a json output
        pass
    else:
        assert "HEARTBEAT MISSING OR MALFORMED" in stderr


def test_missing_heartbeat(tmp_path):
    """Test that a missing heartbeat returns error (exit 3)."""
    hb_file = tmp_path / "missing.json"
    # Ensure it doesn't exist
    assert not hb_file.exists()

    exit_code, _stdout, stderr = run_script(str(hb_file))
    assert exit_code == 3
    if "--json" in sys.argv:
        pass
    else:
        assert "HEARTBEAT MISSING OR MALFORMED" in stderr


def test_iso8601_timestamp(tmp_path):
    """Test that an ISO-8601 timestamp is parsed correctly."""
    hb_file = tmp_path / "heartbeat.json"
    # ISO-8601 string representing now
    now = datetime.now(UTC)
    iso_string = now.isoformat()
    data = {"ts": iso_string}
    hb_file.write_text(json.dumps(data))

    exit_code, stdout, _stderr = run_script(str(hb_file))
    assert exit_code == 0
    assert "HEARTBEAT OK" in stdout


def test_json_output_fresh(tmp_path):
    """Test JSON output for fresh heartbeat."""
    hb_file = tmp_path / "heartbeat.json"
    now = datetime.now(UTC)
    data = {"ts": now.timestamp()}
    hb_file.write_text(json.dumps(data))

    exit_code, stdout, _stderr = run_script(str(hb_file), json_output=True)
    assert exit_code == 0
    result = json.loads(stdout)
    assert result["ok"] is True
    assert result["stale"] is False
    assert isinstance(result["age_s"], (int, float))
    assert result["age_s"] >= 0


def test_json_output_stale(tmp_path):
    """Test JSON output for stale heartbeat."""
    hb_file = tmp_path / "heartbeat.json"
    stale_time = datetime.now(UTC) - timedelta(seconds=3600)
    data = {"ts": stale_time.timestamp()}
    hb_file.write_text(json.dumps(data))

    exit_code, stdout, _stderr = run_script(str(hb_file), json_output=True)
    assert exit_code == 2
    result = json.loads(stdout)
    assert result["ok"] is False
    assert result["stale"] is True
    assert isinstance(result["age_s"], (int, float))
    assert result["age_s"] > 1800


def test_json_output_missing(tmp_path):
    """Test JSON output for missing heartbeat."""
    hb_file = tmp_path / "missing.json"
    assert not hb_file.exists()

    exit_code, stdout, _stderr = run_script(str(hb_file), json_output=True)
    assert exit_code == 3
    result = json.loads(stdout)
    assert result["ok"] is False
    assert result["stale"] is True
    assert result["age_s"] is None
