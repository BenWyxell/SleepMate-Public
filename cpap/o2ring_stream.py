from __future__ import annotations

from collections import deque
import json
import threading
import time
import urllib.parse

from .o2ring_integration import get_service


_installed = False


class _LiveBuffer:
    """Cheap backend sample buffer independent from browser visibility.

    BLE acquisition keeps running according to O2Ring settings. Browsers may
    disconnect from the live SSE while Oximetria is hidden and later restore the
    missing interval with one bounded batch request instead of replaying it.
    """

    def __init__(self, max_points: int = 43_200):
        self._rows: deque[tuple[float, int | None, int | None, int | None]] = deque(maxlen=max_points)
        self._lock = threading.RLock()
        self._last_ts: float | None = None

    def append_snapshot(self, state: dict) -> None:
        ts = state.get("last_sample_ts")
        if ts is None:
            return
        try:
            stamp = float(ts)
        except Exception:
            return
        if not state.get("measuring") and state.get("spo2") is None and state.get("heart_rate") is None:
            return
        with self._lock:
            if self._last_ts == stamp:
                return
            self._last_ts = stamp
            self._rows.append((stamp, state.get("spo2"), state.get("heart_rate"), state.get("motion")))

    def rows(self, *, since: float = 0.0, limit: int = 20_000) -> list[dict]:
        limit = max(1, min(43_200, int(limit or 20_000)))
        with self._lock:
            values = [row for row in self._rows if row[0] > since]
        if len(values) > limit:
            values = values[-limit:]
        return [
            {"timestamp": ts, "spo2": spo2, "heart_rate": hr, "motion": motion}
            for ts, spo2, hr, motion in values
        ]

    def status(self) -> dict:
        with self._lock:
            return {"points": len(self._rows), "last_timestamp": self._last_ts}


BUFFER = _LiveBuffer()


def install_o2ring_stream(app_module) -> None:
    global _installed
    if _installed:
        return
    service = get_service(app_module)
    service.manager.add_listener(BUFFER.append_snapshot)
    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/o2ring/live-buffer":
            cfg = service.settings()
            if not cfg.get("o2ring_enabled"):
                return self._json({"rows": [], "count": 0, "enabled": False})
            query = urllib.parse.parse_qs(parsed.query)
            try:
                since = float(query.get("since", ["0"])[0] or 0)
            except Exception:
                since = 0.0
            try:
                limit = int(query.get("limit", ["20000"])[0] or 20_000)
            except Exception:
                limit = 20_000
            rows = BUFFER.rows(since=since, limit=limit)
            return self._json({"rows": rows, "count": len(rows), **BUFFER.status()})

        if path != "/api/o2ring/live-stream":
            return original_get(self)

        cfg = service.settings()
        if not cfg.get("o2ring_enabled"):
            return self._json({"error": "Az O2Ring integráció nincs bekapcsolva."}, 409)
        if not cfg.get("o2ring_ble_enabled", True):
            return self._json({"error": "Az O2Ring Bluetooth funkció ki van kapcsolva."}, 409)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        last_payload = None
        last_keepalive = 0.0
        try:
            while True:
                snapshot = service.manager.snapshot()
                payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
                now = time.monotonic()
                if payload != last_payload:
                    self.wfile.write(("event: sample\ndata: " + payload + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                    last_payload = payload
                    last_keepalive = now
                elif now - last_keepalive >= 15.0:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    last_keepalive = now
                time.sleep(0.75)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return

    handler_cls.do_GET = do_GET
    _installed = True


__all__ = ["BUFFER", "install_o2ring_stream"]
