from __future__ import annotations

import json
import time
import urllib.parse

from .o2ring_integration import get_service


_installed = False


def install_o2ring_stream(app_module) -> None:
    global _installed
    if _installed:
        return
    service = get_service(app_module)
    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
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


__all__ = ["install_o2ring_stream"]
