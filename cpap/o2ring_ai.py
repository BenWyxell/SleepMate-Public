"""Privacy-safe O2Ring enrichment for SleepMate AI payloads.

The v5.2.20 AI payload builder remains untouched. This v5.3 layer wraps the
already-sanitized payload and adds only reproducible CPAP-overlap oximetry
aggregates. Raw samples, VLD bytes, device identifiers and source filenames are
never added to Luna/Milo requests.
"""
from __future__ import annotations

import hashlib
from statistics import mean
from typing import Any

from .ai_payload import validate_safe_payload
from .o2ring_integration import get_service


_installed = False

_SAFE_METRICS = (
    "coverage_percent",
    "spo2_average",
    "spo2_median",
    "spo2_minimum",
    "t90_seconds",
    "t90_percent",
    "odi3",
    "odi4",
    "heart_rate_average",
    "heart_rate_median",
    "heart_rate_minimum",
    "heart_rate_maximum",
)


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_daily_oximetry(daily: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(daily, dict) or not daily.get("available"):
        return None
    summary = daily.get("summary") if isinstance(daily.get("summary"), dict) else {}
    result: dict[str, Any] = {"available": True, "source_kind": "o2ring_cpap_overlap"}
    for key in _SAFE_METRICS:
        value = _number(summary.get(key))
        if value is not None:
            result[key] = value
    matches = daily.get("matches") if isinstance(daily.get("matches"), list) else []
    result["matched_cpap_sessions"] = len({
        int(m.get("session_index"))
        for m in matches
        if isinstance(m, dict) and m.get("session_index") is not None
    })
    return result


def _avg(values: list[float]) -> float | None:
    return round(mean(values), 3) if values else None


def _period_aggregate(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    rows = [row for row in items if isinstance(row, dict) and row.get("available")]
    if not rows:
        return None

    def values(key: str) -> list[float]:
        out = []
        for row in rows:
            value = _number(row.get(key))
            if value is not None:
                out.append(float(value))
        return out

    minima = values("spo2_minimum")
    t90 = values("t90_seconds")
    result = {
        "available": True,
        "source_kind": "o2ring_cpap_overlap",
        "days_with_oximetry": len(rows),
        "spo2_average_daily_mean": _avg(values("spo2_average")),
        "spo2_minimum": min(minima) if minima else None,
        "t90_seconds_total": round(sum(t90), 1) if t90 else None,
        "t90_percent_daily_mean": _avg(values("t90_percent")),
        "odi3_daily_mean": _avg(values("odi3")),
        "odi4_daily_mean": _avg(values("odi4")),
        "heart_rate_average_daily_mean": _avg(values("heart_rate_average")),
        "coverage_percent_daily_mean": _avg(values("coverage_percent")),
    }
    return {key: value for key, value in result.items() if value is not None}


def _day_key(value: Any) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else ""


def _enrich_standard_payload(payload: dict[str, Any], service) -> dict[str, Any]:
    if not service.settings().get("o2ring_enabled"):
        return payload

    o2_rows: list[dict[str, Any]] = []
    for row in payload.get("days") or []:
        if not isinstance(row, dict):
            continue
        day = _day_key(row.get("date"))
        if not day:
            continue
        try:
            safe = _safe_daily_oximetry(service.daily(day, max_points=1))
        except Exception:
            safe = None
        if safe:
            # Prefer the canonical v5.3 O2Ring CPAP-overlap summary over any
            # preparatory/legacy oximetry field returned by the CPAP dataset.
            row["oximetry"] = safe
            o2_rows.append(safe)

    aggregate = _period_aggregate(o2_rows)
    if aggregate:
        payload.setdefault("aggregate", {})["oximetry"] = aggregate
    validate_safe_payload(payload)
    return payload


def _period_days(dataset, start: Any, end: Any) -> list[str]:
    lo, hi = _day_key(start), _day_key(end)
    if not lo or not hi:
        return []
    if lo > hi:
        lo, hi = hi, lo
    result = []
    for value in dataset.days():
        day = _day_key(value)
        if day and lo <= day <= hi:
            result.append(day)
    return sorted(set(result))


def _comparison_period_aggregate(service, dataset, start: Any, end: Any) -> dict[str, Any] | None:
    rows = []
    for day in _period_days(dataset, start, end):
        try:
            safe = _safe_daily_oximetry(service.daily(day, max_points=1))
        except Exception:
            safe = None
        if safe:
            rows.append(safe)
    return _period_aggregate(rows)


def _enrich_comparison_payload(payload: dict[str, Any], service, dataset, comparison: dict[str, Any]) -> dict[str, Any]:
    if not service.settings().get("o2ring_enabled"):
        return payload

    period_a = _comparison_period_aggregate(service, dataset, comparison.get("a_start"), comparison.get("a_end"))
    period_b = _comparison_period_aggregate(service, dataset, comparison.get("b_start"), comparison.get("b_end"))
    if period_a or period_b:
        payload["oximetry_comparison"] = {"period_a": period_a, "period_b": period_b}
    validate_safe_payload(payload)
    return payload


def _o2_manifest_fingerprint(service) -> str:
    """Cheap local fingerprint for AI cache invalidation; never leaves SleepMate."""
    cfg = service.settings()
    if not cfg.get("o2ring_enabled"):
        return ""
    h = hashlib.sha256()
    h.update(b"sleepmate-o2-ai-signature-v1\0")
    h.update(f"clock_offset={float(cfg.get('o2ring_clock_offset_seconds') or 0.0):.3f}".encode("ascii"))
    paths = []
    try:
        paths.extend(service.store.recordings_dir.glob("*.json"))
    except Exception:
        pass
    try:
        tombstone = service.store.root / "oximetry" / "deleted_sources.json"
        if tombstone.is_file():
            paths.append(tombstone)
    except Exception:
        pass
    for path in sorted(paths, key=lambda p: str(p.name)):
        try:
            stat = path.stat()
            h.update(f"|{path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8"))
        except OSError:
            h.update(f"|{path.name}:missing".encode("utf-8"))
    return h.hexdigest()


def _extend_dataset_signature(base_signature: str, service) -> str:
    o2 = _o2_manifest_fingerprint(service)
    if not o2:
        return base_signature
    h = hashlib.sha256()
    h.update(str(base_signature).encode("ascii", errors="ignore"))
    h.update(b"|o2ring|")
    h.update(o2.encode("ascii"))
    return h.hexdigest()


def install_o2ring_ai(app_module) -> None:
    """Wrap app.py's imported AI builders/signature without changing v5.2.20."""
    global _installed
    if _installed:
        return

    service = get_service(app_module)
    original_safe = app_module.build_safe_payload
    original_comparison = app_module.build_comparison_payload
    handler_cls = app_module.Handler
    original_signature = handler_cls._ai_dataset_signature

    def build_safe_payload(dataset, patient_store, analysis_type: str, month: str = ""):
        payload, meta = original_safe(dataset, patient_store, analysis_type, month)
        return _enrich_standard_payload(payload, service), meta

    def build_comparison_payload(dataset, patient_store, comparison: dict[str, Any]):
        payload, meta = original_comparison(dataset, patient_store, comparison)
        return _enrich_comparison_payload(payload, service, dataset, comparison), meta

    def _ai_dataset_signature(self):
        return _extend_dataset_signature(original_signature(self), service)

    app_module.build_safe_payload = build_safe_payload
    app_module.build_comparison_payload = build_comparison_payload
    handler_cls._ai_dataset_signature = _ai_dataset_signature
    _installed = True


__all__ = [
    "install_o2ring_ai",
    "_safe_daily_oximetry",
    "_period_aggregate",
    "_enrich_standard_payload",
    "_enrich_comparison_payload",
    "_o2_manifest_fingerprint",
    "_extend_dataset_signature",
]
