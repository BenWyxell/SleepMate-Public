from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
import re
import threading
import time
import types
import urllib.parse
from typing import Any, Iterable

from .o2ring_integration import O2RingService, get_service
from .oximetry import OximetrySample, match_recording_to_cpap, summarize_samples


_installed = False


class _EventHub:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._seq = 0
        self._last: dict[str, Any] = {"seq": 0, "type": "boot", "days": [], "source": "runtime"}

    def publish(self, event_type: str, *, days: Iterable[str] = (), source: str = "runtime", details: dict[str, Any] | None = None) -> dict[str, Any]:
        clean = sorted({str(day).replace("-", "")[:8] for day in days if str(day).replace("-", "")[:8].isdigit()})
        with self._cond:
            self._seq += 1
            self._last = {
                "seq": self._seq,
                "type": str(event_type),
                "days": clean,
                "source": str(source),
                "details": details or {},
                "timestamp": time.time(),
            }
            self._cond.notify_all()
            return dict(self._last)

    def snapshot(self) -> dict[str, Any]:
        with self._cond:
            return dict(self._last)

    def wait(self, after: int, timeout: float = 15.0) -> dict[str, Any] | None:
        deadline = time.monotonic() + max(0.1, timeout)
        with self._cond:
            while self._seq <= after:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cond.wait(remaining)
            return dict(self._last)


HUB = _EventHub()


def _day_codes_from_range(start_ts: float, end_ts: float) -> set[str]:
    if not start_ts or not end_ts:
        return set()
    start = datetime.fromtimestamp(float(start_ts))
    end = datetime.fromtimestamp(float(end_ts))
    days = {start.strftime("%Y%m%d"), end.strftime("%Y%m%d")}
    # CPAP therapy days can cross midnight. Including the previous local date
    # makes the invalidation robust without scanning the complete data store.
    days.add(datetime.fromtimestamp(max(0.0, float(start_ts) - 12 * 3600)).strftime("%Y%m%d"))
    return days


def _overlap_seconds(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _daily_v534(self: O2RingService, day: str, max_points: int = 8000) -> dict[str, Any]:
    """Deterministic CPAP ↔ O2 matching with split-session support.

    Candidates are matched by real timestamps. For overlapping alternative O2
    recordings only the strongest overlap is kept, while non-overlapping O2
    fragments remain eligible so a night may consist of multiple ring segments.
    """
    sessions = list(self.app.Handler.dataset.sessions(day))
    if not sessions:
        return {"day": day, "available": False, "matches": [], "samples": [], "summary": None}

    day_start = sessions[0].start.timestamp()
    cfg = self.settings()
    offset = float(cfg.get("o2ring_clock_offset_seconds") or 0.0)
    recordings = self.store.list_recordings()
    chosen: list[tuple[Any, dict[str, Any], int]] = []

    for session_index, session in enumerate(sessions):
        cpap_start, cpap_end = session.start.timestamp(), session.end.timestamp()
        candidates: list[tuple[Any, dict[str, Any]]] = []
        for rec in recordings:
            match = match_recording_to_cpap(
                rec,
                cpap_start,
                cpap_end,
                clock_offset_seconds=offset,
            )
            if match:
                candidates.append((match, rec))

        candidates.sort(
            key=lambda item: (
                -float(item[0].overlap_seconds),
                abs((float(item[1].get("start_ts") or 0) + offset) - cpap_start),
                str(item[1].get("recording_id") or ""),
            )
        )

        accepted: list[tuple[Any, dict[str, Any]]] = []
        for candidate in candidates:
            match, _rec = candidate
            conflicts = False
            for prior, _prior_rec in accepted:
                shared = _overlap_seconds(
                    match.overlap_start,
                    match.overlap_end,
                    prior.overlap_start,
                    prior.overlap_end,
                )
                # A tiny boundary overlap is tolerated for split recordings, but
                # two recordings covering the same therapy interval are alternatives.
                if shared > 30.0:
                    conflicts = True
                    break
            if not conflicts:
                accepted.append(candidate)

        for rank, (match, rec) in enumerate(accepted, start=1):
            chosen.append((match, rec, session_index))

    matches: list[dict[str, Any]] = []
    selected: dict[int, OximetrySample] = {}
    for match, rec, session_index in chosen:
        matches.append(
            {
                **asdict(match),
                "session_index": session_index,
                "source_name": rec.get("source_name"),
            }
        )
        for raw in rec.get("samples") or []:
            ts = float(raw.get("timestamp") or 0) + offset
            if not (match.overlap_start <= ts <= match.overlap_end):
                continue
            sample = OximetrySample(
                timestamp=ts,
                spo2=raw.get("spo2"),
                heart_rate=raw.get("heart_rate"),
                motion=raw.get("motion"),
                valid=bool(raw.get("valid", True)),
            )
            # Timestamp is the primary identity. This prevents duplicate points
            # when two source recordings touch at a boundary or contain the same
            # exported sample with different source names.
            key = int(round(ts * 1000.0))
            selected.setdefault(key, sample)

    full_samples = sorted(selected.values(), key=lambda item: item.timestamp)
    if not full_samples:
        return {"day": day, "available": False, "matches": matches, "samples": [], "summary": None}

    summary = summarize_samples(
        full_samples,
        start_ts=full_samples[0].timestamp,
        end_ts=full_samples[-1].timestamp,
    )
    samples = full_samples
    if max_points > 0 and len(samples) > max_points:
        step = max(1, len(samples) // max_points)
        samples = samples[::step]
        if samples[-1] is not full_samples[-1]:
            samples.append(full_samples[-1])

    return {
        "day": day,
        "available": True,
        "matches": matches,
        "summary": asdict(summary),
        "samples": [
            {
                "t": round(sample.timestamp - day_start, 3),
                "timestamp": sample.timestamp,
                "spo2": sample.spo2,
                "heart_rate": sample.heart_rate,
                "motion": sample.motion,
                "valid": sample.valid,
            }
            for sample in samples
        ],
    }


def _extract_day_codes(value: Any) -> set[str]:
    """Extract only explicit dates from a SleepSync result without DB rescans."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            found.update(_extract_day_codes(key))
            found.update(_extract_day_codes(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.update(_extract_day_codes(item))
    elif isinstance(value, str):
        for y, m, d in re.findall(r"(?<!\d)(20\d{2})[-_/]?([01]\d)[-_/]?([0-3]\d)(?!\d)", value):
            try:
                datetime(int(y), int(m), int(d))
            except ValueError:
                continue
            found.add(f"{y}{m}{d}")
    return found


def _install_recording_invalidation(service: O2RingService) -> None:
    manager = service.manager
    original = getattr(manager, "_on_file", None)
    if not original or getattr(manager, "_sm_v534_file_bridge", False):
        return

    def wrapped(name: str, raw: bytes, info: dict[str, Any]) -> None:
        original(name, raw, info)
        try:
            from .o2ring_vld import parse_vld
            parsed = parse_vld(raw)
            days = _day_codes_from_range(parsed.start_ts, parsed.end_ts)
            HUB.publish(
                "recording-added",
                days=days,
                source="o2ring",
                details={"source_name": str(name or "")[:180]},
            )
        except Exception:
            HUB.publish("recording-added", source="o2ring")

    manager._on_file = wrapped
    manager._sm_v534_file_bridge = True


def _install_sleepsync_bridge(app_module, service: O2RingService) -> None:
    try:
        from .sleepsync_integration import get_service as get_sleepsync_service
        sync = get_sleepsync_service(app_module)
    except Exception:
        return
    if getattr(sync, "_sm_v534_o2_bridge", False):
        return

    original = sync._sync_job

    def wrapped(self, jid: str, trigger: str = "manual"):
        before = list(self.handler.dataset.days())
        result = original(jid, trigger)
        days = _extract_day_codes(result)
        if not days:
            after = list(self.handler.dataset.days())
            before_set, after_set = set(before), set(after)
            days.update(before_set.symmetric_difference(after_set))
            # Modified existing EDF data may not change the day list. Use only a
            # tiny recent fallback rather than rescanning every therapy day.
            if not days:
                recent = after[-4:] if after else before[-4:]
                days.update(str(day).replace("-", "")[:8] for day in recent)
        clean = sorted(day for day in days if len(day) == 8 and day.isdigit())
        HUB.publish(
            "sleepsync-completed",
            days=clean,
            source="sleepsync",
            details={"trigger": trigger, "job": jid},
        )
        if isinstance(result, dict):
            result.setdefault("o2ring", {})["invalidated_days"] = clean
        return result

    sync._sync_job = types.MethodType(wrapped, sync)
    sync._sm_v534_o2_bridge = True


def install_o2ring_runtime_v534(app_module) -> None:
    global _installed
    if _installed:
        return

    service = get_service(app_module)
    service.daily = types.MethodType(_daily_v534, service)
    service.invalidate_days = lambda days, source="runtime", details=None: HUB.publish(
        "therapy-invalidated", days=days, source=source, details=details
    )
    _install_recording_invalidation(service)
    _install_sleepsync_bridge(app_module, service)

    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/o2ring/invalidation-state":
            return self._json(HUB.snapshot())
        if parsed.path == "/api/o2ring/events":
            cfg = service.settings()
            if not cfg.get("o2ring_enabled"):
                return self._json({"error": "Az O2Ring integráció nincs bekapcsolva."}, 409)
            query = urllib.parse.parse_qs(parsed.query)
            try:
                after = int(query.get("after", ["0"])[0])
            except Exception:
                after = 0
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            current = after
            try:
                while True:
                    event = HUB.wait(current, timeout=15.0)
                    if event is None:
                        self.wfile.write(b": keepalive\n\n")
                    else:
                        current = int(event.get("seq") or current)
                        payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                        self.wfile.write(("event: invalidation\ndata: " + payload + "\n\n").encode("utf-8"))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                return
        return original_get(self)

    handler_cls.do_GET = do_GET
    _installed = True


__all__ = ["HUB", "install_o2ring_runtime_v534", "_daily_v534", "_extract_day_codes"]
