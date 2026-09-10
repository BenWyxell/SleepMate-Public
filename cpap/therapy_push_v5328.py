from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
from typing import Any

from .sleep_analysis import get_sleep_analysis_service


_CHANGED_SESSION_RE = re.compile(
    r"(?:^|/)DATALOG/(\d{8})/(\d{8}_\d{6})_[A-Za-z0-9]+\.edf$",
    re.IGNORECASE,
)
_MATCH_TOLERANCE_SECONDS = 90.0
_installed = False


def _changed_files(result: dict[str, Any] | None) -> list[str]:
    if not isinstance(result, dict):
        return []
    raw = result.get("changed_files") or []
    if not isinstance(raw, (list, tuple, set)):
        return []
    return [str(value).replace("\\", "/") for value in raw if str(value).strip()]


def _changed_count(result: dict[str, Any] | None) -> int:
    if not isinstance(result, dict):
        return 0
    total = 0
    for key in ("changed_files", "copied_files", "new_files"):
        value = result.get(key)
        if isinstance(value, (list, tuple, set, dict)):
            total += len(value)
        elif isinstance(value, (int, float)):
            total += int(value)
    return total


def _changed_session_times(result: dict[str, Any]) -> tuple[list[datetime], set[str]]:
    starts: list[datetime] = []
    days: set[str] = set()
    for path in _changed_files(result):
        match = _CHANGED_SESSION_RE.search(path)
        if not match:
            continue
        days.add(match.group(1))
        try:
            starts.append(datetime.strptime(match.group(2), "%Y%m%d_%H%M%S"))
        except ValueError:
            continue
    return starts, days


def _parse_dt(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _all_sleep_blocks(app_module, dataset) -> list[dict[str, Any]]:
    service = get_sleep_analysis_service(app_module)
    payload = service.analyze(dataset, "all")
    blocks: list[dict[str, Any]] = []
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        for block in row.get("blocks") or []:
            if isinstance(block, dict):
                blocks.append(block)
    return blocks


def _block_end(block: dict[str, Any]) -> datetime:
    return _parse_dt(block.get("end")) or _parse_dt(block.get("start")) or datetime.min


def choose_impacted_block(app_module, dataset, result: dict[str, Any]) -> dict[str, Any] | None:
    """Return the newest physical therapy block actually touched by this import.

    The import result names the changed EDF files. Their filename timestamps are
    matched against the SleepMate sleep-analysis block's constituent session
    starts, so a daytime nap is not accidentally replaced by the whole ResMed
    therapy-day total. Cross-noon blocks remain whole because the existing sleep
    analysis already reconstructs them from their source sessions.
    """
    changed_starts, changed_days = _changed_session_times(result)
    if not changed_starts and not changed_days:
        return None

    blocks = _all_sleep_blocks(app_module, dataset)
    exact: list[dict[str, Any]] = []
    day_fallback: list[dict[str, Any]] = []
    for block in blocks:
        session_starts = [
            parsed for parsed in (_parse_dt(value) for value in (block.get("session_starts") or []))
            if parsed is not None
        ]
        if changed_starts and session_starts:
            matched = any(
                abs((session_start - changed_start).total_seconds()) <= _MATCH_TOLERANCE_SECONDS
                for session_start in session_starts
                for changed_start in changed_starts
            )
            if matched:
                exact.append(block)
                continue
        source_days = {str(value) for value in (block.get("source_days") or [])}
        if source_days & changed_days:
            day_fallback.append(block)

    candidates = exact or day_fallback
    return max(candidates, key=_block_end) if candidates else None


def _session_starts(block: dict[str, Any]) -> list[datetime]:
    return [
        parsed for parsed in (_parse_dt(value) for value in (block.get("session_starts") or []))
        if parsed is not None
    ]


def _block_sessions(dataset, block: dict[str, Any]):
    wanted = _session_starts(block)
    if not wanted:
        return []
    found = []
    seen: set[tuple[str, str]] = set()
    for day in block.get("source_days") or []:
        day_text = str(day)
        try:
            sessions = dataset.sessions(day_text)
        except Exception:
            continue
        for session in sessions:
            if not any(abs((session.start - start).total_seconds()) <= _MATCH_TOLERANCE_SECONDS for start in wanted):
                continue
            key = (day_text, session.start.isoformat())
            if key in seen:
                continue
            seen.add(key)
            found.append(session)
    return found


def _percentile95(values: list[float]) -> float | None:
    vals = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * 0.95
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    fraction = pos - lo
    return vals[lo] + (vals[hi] - vals[lo]) * fraction


def leak_p95_for_block(dataset, block: dict[str, Any]) -> float | None:
    values: list[float] = []
    for session in _block_sessions(dataset, block):
        file_info = session.files.get("PLD")
        if not file_info:
            continue
        idx = file_info.edf.find_signal("Leak")
        if idx is None:
            continue
        factor = 60.0 if file_info.edf.signals[idx].phys_dim == "L/s" else 1.0
        try:
            values.extend(
                float(value) * factor
                for value in file_info.edf.read_signal(idx)
                if math.isfinite(float(value)) and float(value) >= 0
            )
        except Exception:
            continue
    value = _percentile95(values)
    return round(value, 1) if value is not None else None


def _format_usage(seconds: Any) -> str:
    try:
        total_minutes = max(0, int(round(float(seconds) / 60.0)))
    except (TypeError, ValueError):
        return "—"
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}:{minutes:02d}"


def _format_metric(value: Any) -> str:
    try:
        number = float(value)
        if not math.isfinite(number):
            return "—"
        return f"{number:.1f}"
    except (TypeError, ValueError):
        return "—"


def therapy_notification_payload(app_module, dataset, result: dict[str, Any]) -> dict[str, Any] | None:
    block = choose_impacted_block(app_module, dataset, result)
    if not block:
        return None
    leak_p95 = leak_p95_for_block(dataset, block)
    return {
        "event_type": "new_night",  # persisted preference key kept for backward compatibility
        "title": "CPAP terápia feldolgozva",
        "body": (
            f"Használat: {_format_usage(block.get('therapy_seconds'))} • "
            f"AHI: {_format_metric(block.get('ahi'))} • "
            f"Szivárgás P95: {_format_metric(leak_p95)} L/perc"
        ),
        "url": "/#dashboard",
        "extra": {
            "therapy_block_id": block.get("id"),
            "therapy_start": block.get("start"),
            "therapy_end": block.get("end"),
            "therapy_type": block.get("type"),
        },
    }


def send_therapy_refresh_push(handler, result: dict[str, Any], reason: str = "Adatfrissítés") -> dict[str, Any]:
    ps = getattr(handler, "push_service", None)
    if not ps:
        return {"sent": 0, "failed": 0, "removed": 0}
    payload = therapy_notification_payload(handler.__module_app__, handler.dataset, result) if hasattr(handler, "__module_app__") else None
    if payload is None:
        app_module = getattr(handler, "_therapy_push_app_module", None)
        if app_module is None:
            return {"sent": 0, "failed": 0, "removed": 0}
        payload = therapy_notification_payload(app_module, handler.dataset, result)
    if not payload:
        return {"sent": 0, "failed": 0, "removed": 0}
    extra = dict(payload["extra"])
    extra["refresh_reason"] = reason
    return ps.send(
        payload["event_type"],
        payload["title"],
        payload["body"],
        payload["url"],
        extra,
    )


def _send_diagnostic_warning(handler, result: dict[str, Any]) -> None:
    if _changed_count(result) <= 0:
        return
    ps = getattr(handler, "push_service", None)
    if not ps:
        return
    diag = handler.dataset.diagnostics()
    warning_rows = [row for row in (diag.get("errors") or []) if isinstance(row, dict)]
    if not warning_rows:
        return
    normalized = [
        f"{str(row.get('title') or '').strip()}|{str(row.get('message') or '').strip()}"
        for row in warning_rows
    ]
    signature = hashlib.sha256("\n".join(sorted(normalized)).encode("utf-8")).hexdigest()
    first = warning_rows[0]
    title = str(first.get("title") or "Adatfigyelmeztetés").strip()
    message = str(first.get("message") or "Ellenőrizd a Naplók oldalt.").strip()
    body = f"{title} – {message}"
    if len(warning_rows) > 1:
        body += f" (+{len(warning_rows) - 1} további figyelmeztetés)"
    ps.send_warning_once(signature, "Adatfigyelmeztetés", body, "/#logs")


def install_therapy_push_v5328(app_module) -> None:
    """Replace file/day-centric CPAP pushes with one therapy-centric contract.

    Every ordinary refresh path already calls Handler._push_after_refresh. We keep
    that stable integration point and only replace what the push describes. The
    integrated SleepSync path is intentionally suppressed here because it imports
    while connected to the isolated ez Share WLAN; sleepsync_integration sends the
    same therapy payload after the internet route has been restored.
    """
    global _installed
    if _installed:
        return
    handler_cls = app_module.Handler
    handler_cls._therapy_push_app_module = app_module

    @classmethod
    def _therapy_push_after_refresh(cls, before_latest: str | None, result: dict, reason: str = "Adatfrissítés") -> None:
        _ = before_latest
        if str(reason or "").startswith("SleepSync"):
            return
        try:
            send_therapy_refresh_push(cls, result, reason)
            _send_diagnostic_warning(cls, result)
        except Exception as exc:
            try:
                cls.persistent_log.append(
                    "WARN",
                    "push",
                    "A terápiafrissítés utáni Web Push feldolgozás sikertelen.",
                    {"reason": reason, "error": str(exc)},
                )
            except Exception:
                pass

    handler_cls._push_after_refresh = _therapy_push_after_refresh
    _installed = True


__all__ = [
    "choose_impacted_block",
    "leak_p95_for_block",
    "therapy_notification_payload",
    "send_therapy_refresh_push",
    "install_therapy_push_v5328",
]
