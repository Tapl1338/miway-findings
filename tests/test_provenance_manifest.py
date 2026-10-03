import hashlib
import json

from scripts.provenance_manifest import build_manifest


def test_manifest_hashes_files_and_skips_missing(tmp_path):
    data = tmp_path / "app" / "data"
    (data / "collections").mkdir(parents=True)
    payload = b'{"polls": []}'
    snap = data / "collections" / "vp_20260823_0900.json"
    snap.write_bytes(payload)
    gt = data / "ground_truth.csv"
    gt.write_bytes(b"a,b\n1,2\n3,4\n")  # 2 data rows

    manifest = build_manifest(tmp_path)

    by_path = {f["path"]: f for f in manifest["files"]}
    assert "app/data/collections/vp_20260823_0900.json" in by_path
    assert "app/data/ground_truth.csv" in by_path

    entry = by_path["app/data/collections/vp_20260823_0900.json"]
    assert entry["sha256"] == hashlib.sha256(payload).hexdigest()
    assert entry["bytes"] == len(payload)
    assert entry["rows"] is None  # json, not csv

    gt_entry = by_path["app/data/ground_truth.csv"]
    assert gt_entry["rows"] == 2

    # Whitelisted-but-absent artifacts simply don't appear.
    assert not any("obs_lateness" in p for p in by_path)
    assert manifest["schema_version"] == 1
    assert "generated_utc" in manifest


def test_manifest_includes_collector_script_hashes(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    body = b"print('collector')\n"
    (scripts / "collect_service.py").write_bytes(body)

    manifest = build_manifest(tmp_path)

    hashed = {s["path"]: s["sha256"] for s in manifest["collector_scripts"]}
    assert hashed["scripts/collect_service.py"] == hashlib.sha256(body).hexdigest()


def test_manifest_is_json_serializable(tmp_path):
    (tmp_path / "app" / "data").mkdir(parents=True)
    manifest = build_manifest(tmp_path)
    round_trip = json.loads(json.dumps(manifest))
    assert round_trip.keys() == manifest.keys()
