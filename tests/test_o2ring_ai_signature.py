from __future__ import annotations

import json
import os

from cpap.o2ring_ai import _extend_dataset_signature, _o2_manifest_fingerprint
from cpap.oximetry import OximetrySample, OximetryStore


class SignatureService:
    def __init__(self, root, *, enabled=True, offset=0.0):
        self.store = OximetryStore(root)
        self.enabled = enabled
        self.offset = offset

    def settings(self):
        return {
            "o2ring_enabled": self.enabled,
            "o2ring_clock_offset_seconds": self.offset,
        }


def seed(service: SignatureService, source="night.vld"):
    return service.store.save_recording(
        device_id="LOCAL-RING",
        source_name=source,
        start_ts=1000.0,
        end_ts=1008.0,
        raw_bytes=b"raw",
        samples=[
            OximetrySample(timestamp=1000.0, spo2=97, heart_rate=60),
            OximetrySample(timestamp=1004.0, spo2=96, heart_rate=61),
            OximetrySample(timestamp=1008.0, spo2=95, heart_rate=62),
        ],
    )


def test_o2_master_off_keeps_original_cpap_signature(tmp_path):
    service = SignatureService(tmp_path / "private", enabled=False)
    seed(service)
    assert _o2_manifest_fingerprint(service) == ""
    assert _extend_dataset_signature("cpap-signature", service) == "cpap-signature"


def test_new_o2_recording_changes_ai_dataset_signature(tmp_path):
    service = SignatureService(tmp_path / "private", enabled=True)
    before = _extend_dataset_signature("cpap-signature", service)
    seed(service)
    after = _extend_dataset_signature("cpap-signature", service)
    assert after != before
    assert len(after) == 64


def test_o2_recording_rewrite_changes_ai_dataset_signature(tmp_path):
    service = SignatureService(tmp_path / "private", enabled=True)
    payload = seed(service)
    before = _extend_dataset_signature("cpap-signature", service)
    path = service.store.recordings_dir / f"{payload['recording_id']}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["summary"]["spo2_average"] = 94.321
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    after = _extend_dataset_signature("cpap-signature", service)
    assert after != before


def test_clock_offset_change_invalidates_ai_signature_without_touching_files(tmp_path):
    service = SignatureService(tmp_path / "private", enabled=True, offset=0)
    seed(service)
    before = _extend_dataset_signature("cpap-signature", service)
    service.offset = 17
    after = _extend_dataset_signature("cpap-signature", service)
    assert after != before


def test_tombstone_change_invalidates_ai_signature(tmp_path):
    service = SignatureService(tmp_path / "private", enabled=True)
    before = _extend_dataset_signature("cpap-signature", service)
    tombstone = service.store.root / "oximetry" / "deleted_sources.json"
    tombstone.write_text(json.dumps({"schema": 1, "source_names": ["old.vld"]}), encoding="utf-8")
    after = _extend_dataset_signature("cpap-signature", service)
    assert after != before
