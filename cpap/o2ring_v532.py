from __future__ import annotations

import urllib.parse
from typing import Any

from .o2ring_integration import get_service


_installed = False


def _normalize_days(raw: str, *, max_days: int = 120) -> list[str]:
    result: list[str] = []
    for part in str(raw or "").split(","):
        day = part.strip().replace("-", "")[:8]
        if len(day) != 8 or not day.isdigit() or day in result:
            continue
        result.append(day)
        if len(result) >= max_days:
            break
    return result


def install_o2ring_v532(app_module) -> None:
    """Install lightweight aggregate endpoints used by the v5.3.2 UI.

    The browser previously made one full O2 request per Dashboard/report row.
    This batch endpoint keeps the UI responsive and still computes every value
    from the existing CPAP-overlap-aware daily service contract.
    """
    global _installed
    if _installed:
        return

    service = get_service(app_module)
    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/o2ring/day-batch":
            query = urllib.parse.parse_qs(parsed.query)
            days = _normalize_days(str(query.get("days", [""])[0]))
            if not days:
                return self._json({"rows": [], "count": 0})

            rows: list[dict[str, Any]] = []
            for day in days:
                payload = service.daily(day, max_points=1)
                rows.append(
                    {
                        "day": day,
                        "available": bool(payload.get("available")),
                        "summary": payload.get("summary"),
                        "matches": payload.get("matches") or [],
                    }
                )
            return self._json({"rows": rows, "count": len(rows)})
        return original_get(self)

    handler_cls.do_GET = do_GET
    _installed = True


__all__ = ["install_o2ring_v532", "_normalize_days"]
