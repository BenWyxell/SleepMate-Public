from __future__ import annotations

import json
from pathlib import Path

from cpap.ai_payload import validate_safe_payload
from cpap.o2ring_ai import (
    _enrich_comparison_payload,
    _enrich_standard_payload,
    _period_aggregate,
    _safe_daily_oximetry,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeService:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.calls = []

    def settings(self):
        return {"o2ring_enabled": self.enabled}

    def daily(self, day, max_points=1):
        self.calls.append((day, max_points))
        values = {
            "20260831": (96.2, 89, 52.0, 0.9, 2.1, 1.0, 63.0, 98.0),
            "20260901": (97.1, 91, 20.0, 0.4, 1.2, 0.4, 61.0, 99.0),
            "20260902": (95.8, 87, 125.0, 2.2, 3.8, 2.4, 66.0, 96.0),
        }
        if day not in values:
            return {"available": False, "samples": []}
        avg, minimum, t90, t90pct, odi3, odi4, hr, coverage = values[day]
        return {
            "available": True,
            "device_id": "SECRET-RING-SERIAL",
            "source_name": f"{day}.vld",
            "raw_path": "C:/secret/ring.vld",
            "samples": [{"timestamp": 1, "spo2": 1, "heart_rate": 1}],
            "summary": {
                "coverage_percent": coverage,
                "spo2_average": avg,
                "spo2_median": avg,
                "spo2_minimum": minimum,
                "t90_seconds": t90,
                "t90_percent": t90pct,
                "odi3": odi3,
                "odi4": odi4,
                "heart_rate_average": hr,
                "heart_rate_median": hr,
                "heart_rate_minimum": 48,
                "heart_rate_maximum": 92,
                "device_id": "SHOULD-NOT-PASS",
            },
            "matches": [
                {"session_index": 0, "source_name": "SECRET.vld"},
                {"session_index": 0, "source_name": "SECRET.vld"},
            ],
        }


class FakeDataset:
    @staticmethod
    def days():
        return ["20260902", "20260901", "20260831"]


def test_safe_daily_oximetry_is_strict_whitelist():
    source = FakeService().daily("20260901")
    safe = _safe_daily_oximetry(source)
    assert safe["source_kind"] == "o2ring_cpap_overlap"
    assert safe["spo2_average"] == 97.1
    assert safe["t90_seconds"] == 20.0
    assert safe["odi3"] == 1.2
    assert safe["heart_rate_average"] == 61.0
    assert safe["matched_cpap_sessions"] == 1

    blob = json.dumps(safe, ensure_ascii=False).lower()
    for forbidden in ("secret", ".vld", "device_id", "source_name", "samples", "timestamp", "raw_path"):
        assert forbidden not in blob
    validate_safe_payload(safe)


def test_standard_ai_payload_gets_only_cpap_overlap_aggregates():
    service = FakeService(enabled=True)
    payload = {
        "schema": "cpap-ai-safe-payload-v1",
        "analysis_type": "week",
        "aggregate": {"therapy_days": 2},
        "days": [
            {"date": "2026-08-31", "ahi": 1.1},
            {"date": "2026-09-01", "ahi": 0.8},
        ],
    }

    out = _enrich_standard_payload(payload, service)
    assert out["days"][0]["oximetry"]["spo2_minimum"] == 89
    assert out["days"][1]["oximetry"]["spo2_average"] == 97.1
    aggregate = out["aggregate"]["oximetry"]
    assert aggregate["days_with_oximetry"] == 2
    assert aggregate["spo2_minimum"] == 89.0
    assert aggregate["t90_seconds_total"] == 72.0
    assert service.calls == [("20260831", 1), ("20260901", 1)]

    blob = json.dumps(out, ensure_ascii=False).lower()
    for forbidden in ("secret", ".vld", "device_id", "source_name", "samples", "raw_path"):
        assert forbidden not in blob
    validate_safe_payload(out)


def test_o2_master_off_removes_stale_oximetry_from_ai_payload():
    service = FakeService(enabled=False)
    payload = {
        "aggregate": {"oximetry": {"spo2_minimum": 88}},
        "days": [{"date": "2026-09-01", "ahi": 1.0, "oximetry": {"spo2_average": 96}}],
    }
    out = _enrich_standard_payload(payload, service)
    assert "oximetry" not in out["aggregate"]
    assert "oximetry" not in out["days"][0]
    assert service.calls == []


def test_comparison_ai_payload_contains_only_period_aggregates():
    service = FakeService(enabled=True)
    payload = {"schema": "cpap-ai-safe-payload-v1", "analysis_type": "comparison", "comparison": {}}
    comparison = {
        "a_start": "2026-08-31",
        "a_end": "2026-09-01",
        "b_start": "2026-09-02",
        "b_end": "2026-09-02",
    }
    out = _enrich_comparison_payload(payload, service, FakeDataset(), comparison)
    o2 = out["oximetry_comparison"]
    assert o2["period_a"]["days_with_oximetry"] == 2
    assert o2["period_b"]["days_with_oximetry"] == 1
    assert o2["period_b"]["spo2_minimum"] == 87.0
    assert "days" not in o2["period_a"]

    blob = json.dumps(out, ensure_ascii=False).lower()
    for forbidden in ("secret", ".vld", "device_id", "source_name", "samples", "raw_path"):
        assert forbidden not in blob
    validate_safe_payload(out)


def test_period_aggregate_names_make_daily_mean_semantics_explicit():
    result = _period_aggregate([
        {"available": True, "spo2_average": 95, "t90_seconds": 10, "coverage_percent": 90},
        {"available": True, "spo2_average": 99, "t90_seconds": 20, "coverage_percent": 100},
    ])
    assert result["spo2_average_daily_mean"] == 97.0
    assert result["t90_seconds_total"] == 30.0
    assert result["coverage_percent_daily_mean"] == 95.0


def test_v53_shell_installs_o2ring_ai_without_modifying_base_ai_module():
    shell = (ROOT / "cpap" / "v530_features.py").read_text(encoding="utf-8")
    base_ai = (ROOT / "cpap" / "ai_payload.py").read_text(encoding="utf-8")
    addon = (ROOT / "cpap" / "o2ring_ai.py").read_text(encoding="utf-8")

    assert "from .o2ring_ai import install_o2ring_ai" in shell
    assert "install_o2ring_ai(app_module)" in shell
    assert "o2ring_cpap_overlap" in addon
    assert "raw samples" in addon.lower()
    assert "o2ring_cpap_overlap" not in base_ai
