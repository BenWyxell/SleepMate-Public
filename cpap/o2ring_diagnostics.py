"""Privacy-safe O2Ring diagnostics for SleepMate v5.3.

This module deliberately exposes technical state only. It never places BLE
addresses, serials, source filenames, recording ids, raw samples or measured
SpO2/heart-rate values into self-check/system-status/support output.
"""
from __future__ import annotations

import importlib.util
import json
import re
import urllib.parse
from typing import Any

from .o2ring_integration import get_service


_installed = False
_MAC_RE = re.compile(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")
_SENSITIVE_KEYS = {
    "source_name", "recording_id", "device_id", "device_address",
    "remembered_address", "serial_number", "o2ring_preferred_address",
}
_HEALTH_KEYS = {
    "spo2", "heart_rate", "motion", "signal_strength",
    "spo2_average", "spo2_median", "spo2_minimum",
    "heart_rate_average", "heart_rate_median", "heart_rate_minimum", "heart_rate_maximum",
    "t90_seconds", "t90_percent", "odi3", "odi4", "samples",
}


def _error_category(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if "bleak" in text or "winrt" in text or "module" in text or "import" in text:
        return "dependency"
    if "permission" in text or "hozzáfér" in text or "access denied" in text:
        return "permission"
    if "bluetooth" in text and any(x in text for x in ("off", "ki", "radio", "unavailable", "nem érhető")):
        return "bluetooth_unavailable"
    if any(x in text for x in ("connect", "kapcsol", "timeout", "időtúllép")):
        return "connection"
    if any(x in text for x in ("crc", "frame", "keret", "protocol", "protokoll")):
        return "protocol"
    return "other"


def _tombstone_count(service) -> int:
    path = service.store.root / "oximetry" / "deleted_sources.json"
    if not path.is_file():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload.get("source_names") if isinstance(payload, dict) else []
        return len({str(x or "").strip() for x in (values or []) if str(x or "").strip()})
    except Exception:
        return 0


def safe_o2ring_diagnostics(service) -> dict[str, Any]:
    """Return a strict technical whitelist suitable for support bundles."""
    cfg = service.settings()
    try:
        snap = service.manager.snapshot()
        if not isinstance(snap, dict):
            snap = {}
    except Exception:
        snap = {}

    try:
        recordings = len(service.store.list_recordings())
    except Exception:
        recordings = -1
    try:
        raw_files = sum(1 for p in service.store.raw_dir.glob("*.vld") if p.is_file())
    except Exception:
        raw_files = -1

    thread_running = False
    try:
        thread = getattr(service.manager, "_thread", None)
        thread_running = bool(thread and thread.is_alive())
    except Exception:
        pass

    feature_enabled = bool(cfg.get("o2ring_enabled"))
    ble_enabled = bool(feature_enabled and cfg.get("o2ring_ble_enabled", True))
    dependency_available = importlib.util.find_spec("bleak") is not None
    error_category = _error_category(snap.get("last_error"))

    return {
        "module_loaded": True,
        "feature_enabled": feature_enabled,
        "ble_enabled": ble_enabled,
        "ble_dependency_available": dependency_available,
        "auto_connect": bool(cfg.get("o2ring_auto_connect", True)),
        "auto_sync": bool(cfg.get("o2ring_auto_sync", True)),
        "auto_match": bool(cfg.get("o2ring_auto_match", True)),
        "remembered_device": bool(str(cfg.get("o2ring_preferred_address") or "").strip()),
        "runtime_thread_running": thread_running,
        "connected": bool(snap.get("connected")),
        "scanning": bool(snap.get("scanning")),
        "measuring": bool(snap.get("measuring")),
        "calibrating": bool(snap.get("calibrating")),
        "has_last_sample": snap.get("last_sample_ts") is not None,
        "has_completed_sync": snap.get("last_sync_ts") is not None,
        "runtime_error": bool(error_category),
        "runtime_error_category": error_category,
        "recordings_count": recordings,
        "raw_recordings_count": raw_files,
        "deleted_source_tombstones_count": _tombstone_count(service),
    }


def _diag_level(diag: dict[str, Any]) -> tuple[str, str]:
    if not diag.get("feature_enabled"):
        return "OK", "Az O2Ring integráció ki van kapcsolva."
    # In frozen Windows builds the BLE module can already be loaded even when
    # importlib cannot resolve a source spec. A running manager thread is the
    # stronger runtime signal and must not create a false support warning.
    if diag.get("ble_enabled") and not diag.get("ble_dependency_available") and not diag.get("runtime_thread_running"):
        return "WARN", "Az O2Ring aktív, de a Windows BLE-függőség nem érhető el."
    if diag.get("ble_enabled") and not diag.get("remembered_device"):
        return "WARN", "Az O2Ring aktív, de még nincs megjegyzett gyűrű."
    if diag.get("ble_enabled") and diag.get("runtime_error"):
        return "WARN", f"Az O2Ring BLE runtime technikai hibát jelzett ({diag.get('runtime_error_category') or 'other'})."
    if not diag.get("ble_enabled"):
        return "OK", "Az O2Ring integráció aktív, a Bluetooth funkció tudatosan ki van kapcsolva."
    if diag.get("connected"):
        return "OK", "Az O2Ring BLE kapcsolat aktív."
    return "OK", "Az O2Ring készen áll; a gyűrű jelenleg nincs kapcsolatban."


def _recount_self_check(payload: dict[str, Any]) -> None:
    rows = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    counts = {"OK": 0, "WARN": 0, "ERROR": 0}
    for row in rows:
        if isinstance(row, dict):
            level = str(row.get("level") or "WARN").upper()
            if level in counts:
                counts[level] += 1
    payload["counts"] = counts
    payload["overall"] = "ERROR" if counts["ERROR"] else ("WARN" if counts["WARN"] else "OK")


def _redact_support_value(obj: Any) -> Any:
    """Redact historical O2 identifiers/measurements from support-bound objects."""
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            low = str(key).lower()
            if low in _SENSITIVE_KEYS or low in _HEALTH_KEYS:
                out[key] = "<REDACTED>" if value not in (None, "", [], {}) else value
            else:
                out[key] = _redact_support_value(value)
        return out
    if isinstance(obj, list):
        return [_redact_support_value(value) for value in obj]
    if isinstance(obj, str):
        return _MAC_RE.sub("<REDACTED-BLE-ADDRESS>", obj)
    return obj


def install_o2ring_diagnostics(app_module) -> None:
    global _installed
    if _installed:
        return

    service = get_service(app_module)
    handler_cls = app_module.Handler
    original_system_status = handler_cls._system_status_payload
    original_self_check = handler_cls._self_check_payload
    original_get = handler_cls.do_GET

    def _system_status_payload(self):
        payload = original_system_status(self)
        diag = safe_o2ring_diagnostics(service)
        if diag.get("feature_enabled"):
            level, message = _diag_level(diag)
            payload.setdefault("components", {})["o2ring"] = {
                "ok": level == "OK",
                "warning": level == "WARN",
                "optional": True,
                "label": "O2Ring",
                "value": message,
            }
            payload["o2ring"] = diag
            if level == "WARN" and payload.get("overall") == "ok":
                payload["overall"] = "warning"
        return payload

    def _self_check_payload(self):
        payload = original_self_check(self)
        diag = safe_o2ring_diagnostics(service)
        if diag.get("feature_enabled"):
            level, message = _diag_level(diag)
            rows = payload.setdefault("checks", [])
            rows[:] = [row for row in rows if not (isinstance(row, dict) and row.get("id") == "o2ring")]
            rows.append({
                "id": "o2ring",
                "level": level,
                "title": "O2Ring / Windows BLE",
                "message": message,
                "details": diag,
            })
            _recount_self_check(payload)
        return payload

    def do_GET(self):
        if urllib.parse.urlparse(self.path).path == "/api/o2ring/diagnostics":
            return self._json(safe_o2ring_diagnostics(service))
        return original_get(self)

    handler_cls._system_status_payload = _system_status_payload
    handler_cls._self_check_payload = _self_check_payload
    handler_cls.do_GET = do_GET

    # Extend the existing support-bundle sanitizers from the v5.3 layer. This is
    # required for historical log entries/config written before diagnostics were
    # added: old O2 download logs may contain source_name/recording_id, while the
    # config may contain o2ring_preferred_address.
    from .maintenance import SupportBundleService
    original_mask_remote = SupportBundleService._mask_remote
    original_sanitize_config = SupportBundleService._sanitize_config

    def support_mask(obj):
        return _redact_support_value(original_mask_remote(obj))

    def sanitize_config(config):
        return _redact_support_value(original_sanitize_config(config))

    SupportBundleService._mask_remote = staticmethod(support_mask)
    SupportBundleService._sanitize_config = staticmethod(sanitize_config)
    _installed = True


__all__ = [
    "install_o2ring_diagnostics",
    "safe_o2ring_diagnostics",
    "_redact_support_value",
    "_diag_level",
]
