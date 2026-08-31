from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import statistics
import threading
import urllib.parse
from typing import Any, Iterable


MERGE_GAP_MINUTES = 90
SHORT_USAGE_MINUTES = 20
LOCAL_WINDOW_HOURS = 24
FRAGMENT_GAP_MINUTES = 180

AHI_TYPES = ("OA", "CA", "H", "UA")
ALL_EVENT_TYPES = ("OA", "CA", "H", "UA", "RERA", "CSR", "OTHER")
VALID_OVERRIDE_TYPES = {"main", "nap", "short"}


@dataclass
class SleepBlock:
    block_id: str
    start: datetime
    end: datetime
    therapy_seconds: float
    wall_seconds: float
    session_count: int
    source_days: list[str]
    session_starts: list[str]
    counts: dict[str, int] = field(default_factory=dict)
    ahi: float = 0.0
    automatic_type: str = "nap"
    final_type: str = "nap"
    manual: bool = False
    anchor_id: str | None = None
    confidence: float = 0.0

    @property
    def center(self) -> datetime:
        return self.start + (self.end - self.start) / 2

    def json(self) -> dict[str, Any]:
        return {
            "id": self.block_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "therapy_seconds": round(self.therapy_seconds, 3),
            "wall_seconds": round(self.wall_seconds, 3),
            "session_count": self.session_count,
            "source_days": list(self.source_days),
            "session_starts": list(self.session_starts),
            "counts": dict(self.counts),
            "ahi": round(self.ahi, 3),
            "automatic_type": self.automatic_type,
            "type": self.final_type,
            "manual": self.manual,
            "anchor_id": self.anchor_id,
            "confidence": round(self.confidence, 3),
        }


def _median(values: Iterable[float]) -> float | None:
    vals = [float(v) for v in values if float(v) > 0]
    return float(statistics.median(vals)) if vals else None


def _block_id(first_start: datetime) -> str:
    raw = first_start.isoformat(timespec="seconds").encode("utf-8")
    return "slp-" + hashlib.sha1(raw).hexdigest()[:14]


def _gap_seconds(a: SleepBlock, b: SleepBlock) -> float:
    if b.start >= a.end:
        return (b.start - a.end).total_seconds()
    if a.start >= b.end:
        return (a.start - b.end).total_seconds()
    return 0.0


def _nearest_anchor(block: SleepBlock, anchors: list[SleepBlock]) -> SleepBlock | None:
    if not anchors:
        return None
    return min(
        anchors,
        key=lambda a: (abs((block.center - a.center).total_seconds()), -a.therapy_seconds),
    )


def classify_blocks(
    blocks: list[SleepBlock],
    overrides: dict[str, str] | None = None,
) -> tuple[list[SleepBlock], dict[str, Any]]:
    """Classify CPAP blocks without using clock-time-of-day as evidence.

    The algorithm intentionally does not contain an "evening" or "night" window.
    It finds locally dominant sleep blocks in a rolling 24-hour neighbourhood,
    learns the user's typical dominant-block duration from the available history,
    then uses that history only to recognise split/fragmented main sleep. A lone
    short night can therefore still be the main sleep, while a daytime nap next to
    a much longer block remains a nap regardless of the wall-clock start time.
    """
    overrides = {str(k): str(v) for k, v in (overrides or {}).items() if str(v) in VALID_OVERRIDE_TYPES}
    if not blocks:
        return blocks, {
            "history_blocks": 0,
            "dominant_blocks": 0,
            "typical_main_seconds": None,
            "typical_nap_seconds": None,
            "median_main_interval_hours": None,
            "clock_time_used": False,
        }

    blocks.sort(key=lambda b: b.start)
    short_limit = SHORT_USAGE_MINUTES * 60.0
    half_window = LOCAL_WINDOW_HOURS * 3600.0 / 2.0

    for b in blocks:
        b.manual = b.block_id in overrides
        manual = overrides.get(b.block_id)
        if manual:
            b.final_type = manual
            b.automatic_type = "short" if b.therapy_seconds < short_limit else "nap"
        elif b.therapy_seconds < short_limit:
            b.automatic_type = b.final_type = "short"
            b.confidence = 0.99
        else:
            b.automatic_type = b.final_type = "nap"

    # Main-sleep candidates are local duration maxima. Manual nap/short blocks
    # cannot become anchors; manual main blocks always can.
    eligible = [
        b for b in blocks
        if b.therapy_seconds >= short_limit and overrides.get(b.block_id) not in {"nap", "short"}
    ]
    anchors: list[SleepBlock] = []
    for b in eligible:
        if overrides.get(b.block_id) == "main":
            anchors.append(b)
            continue
        neighbours = [
            x for x in eligible
            if abs((x.center - b.center).total_seconds()) <= half_window
        ]
        if not neighbours:
            anchors.append(b)
            continue
        best = max(neighbours, key=lambda x: (x.therapy_seconds, -x.start.timestamp()))
        if best.block_id == b.block_id:
            anchors.append(b)

    # Remove accidental duplicate automatic anchors that are extremely close.
    anchors = sorted({a.block_id: a for a in anchors}.values(), key=lambda b: b.start)
    compact: list[SleepBlock] = []
    for a in anchors:
        if not compact:
            compact.append(a)
            continue
        prev = compact[-1]
        center_gap = abs((a.center - prev.center).total_seconds())
        if center_gap < 8 * 3600 and not (a.manual or prev.manual):
            if a.therapy_seconds > prev.therapy_seconds:
                compact[-1] = a
        else:
            compact.append(a)
    anchors = compact

    # Every history, even a lone 2.5-hour sleep, must still have a main sleep.
    if not anchors:
        candidates = [b for b in blocks if overrides.get(b.block_id) not in {"nap", "short"} and b.final_type != "short"]
        if candidates:
            anchors = [max(candidates, key=lambda b: b.therapy_seconds)]

    anchor_ids = {a.block_id for a in anchors}
    typical_main = _median(a.therapy_seconds for a in anchors)

    # Learn typical main-to-main interval only for diagnostics/transparency.
    anchor_intervals = [
        (b.center - a.center).total_seconds() / 3600.0
        for a, b in zip(anchors, anchors[1:])
        if b.center > a.center
    ]
    median_interval = _median(anchor_intervals)

    # First pass: mark anchors as main, respecting explicit user corrections.
    for b in blocks:
        manual = overrides.get(b.block_id)
        if manual:
            b.final_type = manual
            b.confidence = 1.0
            if manual == "main":
                b.automatic_type = "main" if b.block_id in anchor_ids else b.automatic_type
            continue
        if b.block_id in anchor_ids:
            b.automatic_type = b.final_type = "main"
            ratio = (b.therapy_seconds / typical_main) if typical_main else 1.0
            b.confidence = 0.96 if ratio >= 0.70 else 0.82

    # Historical duration is useful for recognising a split main sleep. This is
    # deliberately conservative so a normal 1-2 hour nap after a complete main
    # sleep does not get absorbed merely because it is close in time.
    fragment_gap_s = FRAGMENT_GAP_MINUTES * 60.0
    if anchors and typical_main:
        for b in blocks:
            if b.block_id in anchor_ids or b.manual or b.final_type == "short":
                continue
            nearest = _nearest_anchor(b, anchors)
            if nearest is None:
                continue
            gap = _gap_seconds(b, nearest)
            anchor_incomplete = nearest.therapy_seconds < typical_main * 0.85
            fragment_is_large = b.therapy_seconds >= max(3600.0, typical_main * 0.35)
            combined_is_mainlike = (nearest.therapy_seconds + b.therapy_seconds) >= typical_main * 0.78
            if gap <= fragment_gap_s and fragment_is_large and combined_is_mainlike and anchor_incomplete:
                b.automatic_type = b.final_type = "main"
                b.anchor_id = nearest.block_id
                b.confidence = 0.88

    # Remaining real blocks are naps. A nap must have a dominant main block in
    # its local neighbourhood; if it does not, promote it to main rather than
    # inventing a nap from clock time or duration alone.
    current_main = [b for b in blocks if b.final_type == "main"]
    for b in blocks:
        if b.manual or b.final_type in {"main", "short"}:
            continue
        nearby_main = [
            a for a in current_main
            if abs((a.center - b.center).total_seconds()) <= half_window
        ]
        if nearby_main:
            nearest = _nearest_anchor(b, nearby_main)
            b.automatic_type = b.final_type = "nap"
            b.anchor_id = nearest.block_id if nearest else None
            dominance = (nearest.therapy_seconds / max(1.0, b.therapy_seconds)) if nearest else 1.0
            b.confidence = min(0.97, 0.72 + max(0.0, dominance - 1.0) * 0.08)
        else:
            b.automatic_type = b.final_type = "main"
            b.anchor_id = None
            b.confidence = 0.78
            current_main.append(b)

    nap_durations = [b.therapy_seconds for b in blocks if b.final_type == "nap"]
    learned = {
        "history_blocks": len(blocks),
        "dominant_blocks": len([b for b in blocks if b.final_type == "main"]),
        "typical_main_seconds": round(typical_main, 3) if typical_main else None,
        "typical_nap_seconds": round(_median(nap_durations), 3) if nap_durations else None,
        "median_main_interval_hours": round(median_interval, 2) if median_interval else None,
        "clock_time_used": False,
        "merge_gap_minutes": MERGE_GAP_MINUTES,
        "short_usage_minutes": SHORT_USAGE_MINUTES,
        "local_window_hours": LOCAL_WINDOW_HOURS,
        "fragment_gap_minutes": FRAGMENT_GAP_MINUTES,
    }
    return blocks, learned


def aggregate_rows(blocks: list[SleepBlock]) -> list[dict[str, Any]]:
    grouped: dict[str, list[SleepBlock]] = {}
    for b in blocks:
        grouped.setdefault(b.start.date().isoformat(), []).append(b)

    rows: list[dict[str, Any]] = []
    for date_key in sorted(grouped):
        items = sorted(grouped[date_key], key=lambda b: b.start)
        seconds = {kind: sum(b.therapy_seconds for b in items if b.final_type == kind) for kind in ("main", "nap", "short")}
        counts_total = {k: sum(int(b.counts.get(k, 0)) for b in items) for k in ALL_EVENT_TYPES}
        main_counts = {k: sum(int(b.counts.get(k, 0)) for b in items if b.final_type == "main") for k in ALL_EVENT_TYPES}
        total_s = sum(seconds.values())
        main_s = seconds["main"]
        total_ahi_events = sum(counts_total[k] for k in AHI_TYPES)
        main_ahi_events = sum(main_counts[k] for k in AHI_TYPES)
        rows.append({
            "date": date_key,
            "main_seconds": round(main_s, 3),
            "nap_seconds": round(seconds["nap"], 3),
            "short_seconds": round(seconds["short"], 3),
            "total_seconds": round(total_s, 3),
            "main_ahi": round(main_ahi_events / (main_s / 3600.0), 3) if main_s > 0 else None,
            "total_ahi": round(total_ahi_events / (total_s / 3600.0), 3) if total_s > 0 else None,
            "main_parts": sum(1 for b in items if b.final_type == "main"),
            "nap_count": sum(1 for b in items if b.final_type == "nap"),
            "short_count": sum(1 for b in items if b.final_type == "short"),
            "counts": counts_total,
            "blocks": [b.json() for b in items],
        })
    return rows


class SleepAnalysisService:
    def __init__(self, app_module):
        self.app = app_module
        self.path = Path(app_module.STATE_BASE) / "private" / "sleep_analysis_overrides.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cache_key: tuple[str, float] | None = None
        self._cache_payload: dict[str, Any] | None = None

    def _load_overrides(self) -> dict[str, str]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {}
            rows = raw.get("overrides", raw) if isinstance(raw, dict) else {}
            if not isinstance(rows, dict):
                return {}
            return {str(k): str(v) for k, v in rows.items() if str(v) in VALID_OVERRIDE_TYPES}
        except Exception:
            return {}

    def _save_overrides(self, overrides: dict[str, str]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps({
            "version": 1,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "overrides": dict(sorted(overrides.items())),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        self._cache_key = None
        self._cache_payload = None

    def set_override(self, block_id: str, kind: str) -> dict[str, Any]:
        block_id = str(block_id or "").strip()
        kind = str(kind or "auto").strip().lower()
        if not block_id.startswith("slp-"):
            raise ValueError("Érvénytelen alvásblokk-azonosító.")
        if kind != "auto" and kind not in VALID_OVERRIDE_TYPES:
            raise ValueError("A besorolás csak Fő alvás, Szundi, Rövid használat vagy Automatikus lehet.")
        with self._lock:
            overrides = self._load_overrides()
            if kind == "auto":
                overrides.pop(block_id, None)
            else:
                overrides[block_id] = kind
            self._save_overrides(overrides)
        return {"ok": True, "block_id": block_id, "type": kind, "overrides": len(overrides)}

    def _build_blocks(self, dataset) -> list[SleepBlock]:
        raw_sessions: list[tuple[datetime, datetime, float, str]] = []
        event_rows: list[tuple[datetime, str]] = []
        for day in sorted(dataset.days()):
            for sess in dataset.sessions(day):
                if float(sess.duration_s or 0) <= 0:
                    continue
                raw_sessions.append((sess.start, sess.end, float(sess.duration_s), day))
            for event in dataset.events(day):
                try:
                    event_rows.append((datetime.fromisoformat(str(event.get("time"))), str(event.get("type") or "OTHER")))
                except Exception:
                    continue

        # Defensive de-duplication in case the same physical session is visible
        # through more than one imported day folder.
        dedup: dict[tuple[str, str], tuple[datetime, datetime, float, str]] = {}
        for row in raw_sessions:
            key = (row[0].isoformat(), row[1].isoformat())
            if key not in dedup or row[2] > dedup[key][2]:
                dedup[key] = row
        sessions = sorted(dedup.values(), key=lambda x: x[0])
        if not sessions:
            return []

        groups: list[list[tuple[datetime, datetime, float, str]]] = []
        merge_gap = timedelta(minutes=MERGE_GAP_MINUTES)
        max_wall = timedelta(hours=16)
        for row in sessions:
            if not groups:
                groups.append([row])
                continue
            current = groups[-1]
            current_start = current[0][0]
            current_end = max(x[1] for x in current)
            gap = row[0] - current_end
            prospective_end = max(current_end, row[1])
            if gap <= merge_gap and prospective_end - current_start <= max_wall:
                current.append(row)
            else:
                groups.append([row])

        blocks: list[SleepBlock] = []
        for group in groups:
            start = min(x[0] for x in group)
            end = max(x[1] for x in group)
            therapy_s = sum(float(x[2]) for x in group)
            counts = {k: 0 for k in ALL_EVENT_TYPES}
            for ts, kind in event_rows:
                if start <= ts <= end:
                    counts[kind if kind in counts else "OTHER"] += 1
            ahi_events = sum(counts[k] for k in AHI_TYPES)
            ahi = ahi_events / (therapy_s / 3600.0) if therapy_s > 0 else 0.0
            blocks.append(SleepBlock(
                block_id=_block_id(start),
                start=start,
                end=end,
                therapy_seconds=therapy_s,
                wall_seconds=max(0.0, (end - start).total_seconds()),
                session_count=len(group),
                source_days=sorted({x[3] for x in group}),
                session_starts=[x[0].isoformat() for x in group],
                counts=counts,
                ahi=ahi,
            ))
        return blocks

    def _full_payload(self, dataset) -> dict[str, Any]:
        refresh_key = str(getattr(dataset, "last_refresh_at", ""))
        try:
            override_mtime = self.path.stat().st_mtime if self.path.is_file() else 0.0
        except OSError:
            override_mtime = 0.0
        cache_key = (refresh_key, override_mtime)
        with self._lock:
            if self._cache_key == cache_key and self._cache_payload is not None:
                return self._cache_payload

            overrides = self._load_overrides()
            blocks = self._build_blocks(dataset)
            blocks, learned = classify_blocks(blocks, overrides)
            rows = aggregate_rows(blocks)
            payload = {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "settings": {
                    "merge_gap_minutes": MERGE_GAP_MINUTES,
                    "short_usage_minutes": SHORT_USAGE_MINUTES,
                    "local_window_hours": LOCAL_WINDOW_HOURS,
                    "fragment_gap_minutes": FRAGMENT_GAP_MINUTES,
                    "clock_time_used": False,
                },
                "learned": learned,
                "overrides": len(overrides),
                "rows": rows,
            }
            self._cache_key = cache_key
            self._cache_payload = payload
            return payload

    def analyze(self, dataset, period: str = "30") -> dict[str, Any]:
        full = self._full_payload(dataset)
        rows = list(full.get("rows") or [])
        period_raw = str(period or "30").lower()
        if rows and period_raw != "all":
            try:
                days = max(1, int(period_raw))
            except ValueError:
                days = 30
            latest = datetime.fromisoformat(rows[-1]["date"]).date()
            cutoff = latest - timedelta(days=days - 1)
            rows = [r for r in rows if datetime.fromisoformat(r["date"]).date() >= cutoff]

        main_days = [r for r in rows if float(r.get("main_seconds") or 0) > 0]
        total_s = sum(float(r.get("total_seconds") or 0) for r in rows)
        main_s = sum(float(r.get("main_seconds") or 0) for r in rows)
        nap_s = sum(float(r.get("nap_seconds") or 0) for r in rows)
        short_s = sum(float(r.get("short_seconds") or 0) for r in rows)
        summary = {
            "days": len(rows),
            "main_days": len(main_days),
            "main_seconds": round(main_s, 3),
            "nap_seconds": round(nap_s, 3),
            "short_seconds": round(short_s, 3),
            "total_seconds": round(total_s, 3),
            "average_main_seconds": round(main_s / len(main_days), 3) if main_days else 0,
            "average_total_seconds": round(total_s / len(rows), 3) if rows else 0,
            "nap_count": sum(int(r.get("nap_count") or 0) for r in rows),
            "short_count": sum(int(r.get("short_count") or 0) for r in rows),
            "fragmented_main_days": sum(1 for r in rows if int(r.get("main_parts") or 0) > 1),
        }
        return {
            "generated_at": full.get("generated_at"),
            "period": period_raw,
            "settings": full.get("settings"),
            "learned": full.get("learned"),
            "overrides": full.get("overrides"),
            "summary": summary,
            "rows": rows,
            "latest": rows[-1] if rows else None,
        }


_service: SleepAnalysisService | None = None
_service_lock = threading.RLock()


def get_sleep_analysis_service(app_module) -> SleepAnalysisService:
    global _service
    with _service_lock:
        if _service is None:
            _service = SleepAnalysisService(app_module)
        return _service


def install_sleep_analysis(app_module) -> None:
    """Install adaptive sleep-analysis API without touching the ResMed parser."""
    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET
    original_post = handler_cls.do_POST

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/sleep-analysis":
            try:
                query = urllib.parse.parse_qs(parsed.query)
                period = str((query.get("period") or ["30"])[0])
                service = get_sleep_analysis_service(app_module)
                return self._json(service.analyze(self.dataset, period))
            except Exception as exc:
                return self._json({"error": f"Alvásfelismerési hiba: {exc}"}, 500)
        return original_get(self)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/sleep-analysis/override":
            try:
                data = self._read_json_body(max_bytes=30_000)
                service = get_sleep_analysis_service(app_module)
                result = service.set_override(str(data.get("block_id") or ""), str(data.get("type") or "auto"))
                result["analysis"] = service.analyze(self.dataset, str(data.get("period") or "30"))
                return self._json(result)
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)
        return original_post(self)

    handler_cls.do_GET = do_GET
    handler_cls.do_POST = do_POST


__all__ = [
    "SleepBlock",
    "SleepAnalysisService",
    "aggregate_rows",
    "classify_blocks",
    "get_sleep_analysis_service",
    "install_sleep_analysis",
]
