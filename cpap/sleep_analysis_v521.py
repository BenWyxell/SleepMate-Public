from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
import urllib.parse

from . import sleep_analysis as sa


_installed = False


def _sleep_date(block: sa.SleepBlock) -> str:
    """Assign a sleep to the calendar day on which it finishes.

    CPAP therapy commonly starts before midnight and finishes the following
    morning. Grouping by the start date made a normal overnight sleep appear on
    the previous day and could leave only a one-minute fragment on the wake-up
    day. The wake-up date is the useful human-facing sleep date.
    """
    return block.end.date().isoformat()


def _block_json(self: sa.SleepBlock) -> dict[str, Any]:
    return {
        "id": self.block_id,
        "sleep_date": _sleep_date(self),
        "start": self.start.isoformat(),
        "end": self.end.isoformat(),
        "therapy_seconds": round(self.therapy_seconds, 3),
        "wall_seconds": round(self.wall_seconds, 3),
        "session_count": self.session_count,
        "source_days": list(self.source_days),
        "session_starts": list(self.session_starts),
        "session_details": list(getattr(self, "session_details", []) or []),
        "counts": dict(self.counts),
        "ahi": round(self.ahi, 3),
        "automatic_type": self.automatic_type,
        "type": self.final_type,
        "manual": self.manual,
        "anchor_id": self.anchor_id,
        "confidence": round(self.confidence, 3),
    }


def _build_blocks(self: sa.SleepAnalysisService, dataset) -> list[sa.SleepBlock]:
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

    # A physical CPAP session can occasionally be exposed through more than one
    # imported day folder. Keep exactly one copy before sleep-block formation.
    dedup: dict[tuple[str, str], tuple[datetime, datetime, float, str]] = {}
    for row in raw_sessions:
        key = (row[0].isoformat(), row[1].isoformat())
        if key not in dedup or row[2] > dedup[key][2]:
            dedup[key] = row
    sessions = sorted(dedup.values(), key=lambda x: x[0])
    if not sessions:
        return []

    groups: list[list[tuple[datetime, datetime, float, str]]] = []
    merge_gap = timedelta(minutes=sa.MERGE_GAP_MINUTES)
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

    blocks: list[sa.SleepBlock] = []
    for group in groups:
        start = min(x[0] for x in group)
        end = max(x[1] for x in group)
        therapy_s = sum(float(x[2]) for x in group)
        counts = {k: 0 for k in sa.ALL_EVENT_TYPES}
        for ts, kind in event_rows:
            if start <= ts <= end:
                counts[kind if kind in counts else "OTHER"] += 1
        ahi_events = sum(counts[k] for k in sa.AHI_TYPES)
        ahi = ahi_events / (therapy_s / 3600.0) if therapy_s > 0 else 0.0
        block = sa.SleepBlock(
            block_id=sa._block_id(start),
            start=start,
            end=end,
            therapy_seconds=therapy_s,
            wall_seconds=max(0.0, (end - start).total_seconds()),
            session_count=len(group),
            source_days=sorted({x[3] for x in group}),
            session_starts=[x[0].isoformat() for x in group],
            counts=counts,
            ahi=ahi,
        )
        block.session_details = [
            {
                "start": row[0].isoformat(),
                "end": row[1].isoformat(),
                "therapy_seconds": round(float(row[2]), 3),
                "source_day": row[3],
            }
            for row in sorted(group, key=lambda x: x[0])
        ]
        blocks.append(block)
    return blocks


def aggregate_rows(blocks: list[sa.SleepBlock]) -> list[dict[str, Any]]:
    grouped: dict[str, list[sa.SleepBlock]] = {}
    for block in blocks:
        grouped.setdefault(_sleep_date(block), []).append(block)

    rows: list[dict[str, Any]] = []
    for date_key in sorted(grouped):
        items = sorted(grouped[date_key], key=lambda b: b.start)
        seconds = {
            kind: sum(b.therapy_seconds for b in items if b.final_type == kind)
            for kind in ("main", "nap", "short")
        }
        counts_total = {
            k: sum(int(b.counts.get(k, 0)) for b in items)
            for k in sa.ALL_EVENT_TYPES
        }
        main_counts = {
            k: sum(int(b.counts.get(k, 0)) for b in items if b.final_type == "main")
            for k in sa.ALL_EVENT_TYPES
        }
        total_s = sum(seconds.values())
        main_s = seconds["main"]
        total_ahi_events = sum(counts_total[k] for k in sa.AHI_TYPES)
        main_ahi_events = sum(main_counts[k] for k in sa.AHI_TYPES)
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


def _range_from_period(rows: list[dict[str, Any]], period_raw: str):
    if not rows:
        return None, None, "Nincs adat"

    latest = datetime.fromisoformat(rows[-1]["date"]).date()
    today = datetime.now().date()

    if period_raw == "all":
        return None, None, "Teljes időszak"
    if period_raw == "prev_week":
        this_monday = today - timedelta(days=today.weekday())
        start = this_monday - timedelta(days=7)
        end = this_monday - timedelta(days=1)
        return start, end, "Előző hét"
    if period_raw == "prev_month":
        first_this = today.replace(day=1)
        end = first_this - timedelta(days=1)
        start = end.replace(day=1)
        return start, end, "Előző hónap"
    if period_raw.startswith("range:"):
        parts = period_raw.split(":", 2)
        if len(parts) != 3:
            raise ValueError("Az egyedi dátumtartomány formátuma hibás.")
        start = datetime.fromisoformat(parts[1]).date()
        end = datetime.fromisoformat(parts[2]).date()
        if start > end:
            start, end = end, start
        return start, end, "Egyedi időszak"
    if period_raw == "day":
        return latest, latest, "Legutóbbi nap"

    try:
        days = max(1, int(period_raw))
    except ValueError:
        days = 30
    start = latest - timedelta(days=days - 1)
    return start, latest, f"Utolsó {days} nap"


def analyze(self: sa.SleepAnalysisService, dataset, period: str = "30") -> dict[str, Any]:
    full = self._full_payload(dataset)
    all_rows = list(full.get("rows") or [])
    period_raw = str(period or "30").lower().strip()
    start, end, label = _range_from_period(all_rows, period_raw)

    rows = all_rows
    if start is not None and end is not None:
        rows = [
            row for row in rows
            if start <= datetime.fromisoformat(row["date"]).date() <= end
        ]

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
        "filter": {
            "label": label,
            "start": start.isoformat() if start else (rows[0]["date"] if rows else None),
            "end": end.isoformat() if end else (rows[-1]["date"] if rows else None),
        },
        "settings": full.get("settings"),
        "learned": full.get("learned"),
        "overrides": full.get("overrides"),
        "summary": summary,
        "rows": rows,
        "latest": rows[-1] if rows else None,
    }


def _install_shell_loader(app_module) -> None:
    """Load the 5.2 sleep UI and its correction in source and packaged builds.

    Windows packaging intentionally restores the proven v5.0.8 app.js, so a
    source-only app.js change is not enough. Serving the shell with these two
    deferred scripts makes the feature deterministic for desktop, PWA and the
    service-worker navigation cache without touching the proven core bootstrap.
    """
    handler_cls = app_module.Handler
    previous_get = handler_cls.do_GET

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            try:
                index_path = app_module.WEB / "index.html"
                text = index_path.read_text(encoding="utf-8")
                scripts = []
                if "sleepmate-sleep.js" not in text:
                    scripts.append('<script src="/sleepmate-sleep.js?v=5.2.1"></script>')
                if "sleepmate-sleep-v521.js" not in text:
                    scripts.append('<script src="/sleepmate-sleep-v521.js?v=5.2.1"></script>')
                if scripts:
                    marker = "</body>"
                    inject = "\n" + "\n".join(scripts) + "\n"
                    text = text.replace(marker, inject + marker, 1) if marker in text else text + inject
                body = text.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception:
                # If shell decoration ever fails, preserve the original static
                # handler rather than making the whole SleepMate UI unavailable.
                pass
        return previous_get(self)

    handler_cls.do_GET = do_GET


def install_sleep_analysis_v521(app_module) -> None:
    global _installed
    if _installed:
        return

    # These are deliberately narrow compatibility patches over the 5.2 engine:
    # the classification model stays unchanged, while display-day semantics,
    # constituent-session details and richer period filtering are corrected.
    sa.SleepBlock.json = _block_json
    sa.SleepAnalysisService._build_blocks = _build_blocks
    sa.SleepAnalysisService.analyze = analyze
    sa.aggregate_rows = aggregate_rows
    _install_shell_loader(app_module)
    _installed = True


__all__ = ["install_sleep_analysis_v521", "aggregate_rows", "analyze"]