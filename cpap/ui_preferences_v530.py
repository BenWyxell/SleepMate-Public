from __future__ import annotations

import urllib.parse
from typing import Any


_installed = False

PWA_NAV_MAX_ITEMS = 6
PWA_NAV_ALLOWED = {
    "dashboard", "patient", "sessions", "events", "reports", "ai",
    "equipment", "upload", "logs", "faq", "settings", "oximetry",
    "oximetry_live", "charts", "more",
}
PWA_NAV_DEFAULT = ["dashboard", "sessions", "charts", "ai", "more"]
PWA_NAV_LABEL_MAX_LENGTH = 18
PWA_NAV_DEFAULT_LABELS = {
    "dashboard": "Dashboard", "patient": "Kezelt személy", "sessions": "Napok",
    "events": "Események", "reports": "Jelentések", "ai": "Luna & Milo",
    "equipment": "Felszerelés", "upload": "Feltöltés", "logs": "Naplók",
    "faq": "GYIK", "settings": "Beállítások", "oximetry": "Oximetria",
    "oximetry_live": "Élő O₂ monitor", "charts": "Diagrammok", "more": "Egyéb",
}


def _normalize_nav(value: Any) -> list[str]:
    if value is None:
        return list(PWA_NAV_DEFAULT)
    if not isinstance(value, list):
        raise ValueError("A PWA alsó menü listája hibás.")
    result: list[str] = []
    for raw in value:
        item = str(raw or "").strip().lower()
        if not item or item not in PWA_NAV_ALLOWED:
            raise ValueError(f"Nem támogatott PWA menüpont: {item or 'üres'}")
        if item not in result:
            result.append(item)
    if not result:
        raise ValueError("A PWA alsó menüben legalább 1 elemnek maradnia kell.")
    if len(result) > PWA_NAV_MAX_ITEMS:
        raise ValueError(f"A PWA alsó menüben legfeljebb {PWA_NAV_MAX_ITEMS} elem lehet.")
    return result


def _normalize_labels(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("A PWA menüpontnevek formátuma hibás.")
    result: dict[str, str] = {}
    for raw_key, raw_label in value.items():
        key = str(raw_key or "").strip().lower()
        if key not in PWA_NAV_ALLOWED:
            raise ValueError(f"Nem támogatott PWA menüpont: {key or 'üres'}")
        label = " ".join(str(raw_label or "").split()).strip()
        if not label or label == PWA_NAV_DEFAULT_LABELS.get(key):
            continue
        if len(label) > PWA_NAV_LABEL_MAX_LENGTH:
            raise ValueError(f"A(z) {key} megjelenített neve legfeljebb {PWA_NAV_LABEL_MAX_LENGTH} karakter lehet.")
        result[key] = label
    return result


def _normalize_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"A(z) {field} értéke csak igaz vagy hamis lehet.")
    return value


def install_ui_preferences_v530(app_module) -> None:
    global _installed
    if _installed:
        return

    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET
    original_post = handler_cls.do_POST

    def payload() -> dict[str, Any]:
        cfg = app_module.load_config()
        try:
            nav = _normalize_nav(cfg.get("pwa_bottom_nav"))
        except Exception:
            nav = list(PWA_NAV_DEFAULT)
        try:
            labels = _normalize_labels(cfg.get("pwa_bottom_nav_labels"))
        except Exception:
            labels = {}
        return {
            "pwa_bottom_nav": nav,
            "pwa_bottom_nav_labels": labels,
            "pwa_bottom_nav_default_labels": dict(PWA_NAV_DEFAULT_LABELS),
            "pwa_bottom_nav_label_max_length": PWA_NAV_LABEL_MAX_LENGTH,
            "pwa_bottom_nav_max": PWA_NAV_MAX_ITEMS,
            "pwa_bottom_nav_allowed": sorted(PWA_NAV_ALLOWED),
            "ai_luna_visible": bool(cfg.get("ai_luna_visible", True)),
            "ai_milo_visible": bool(cfg.get("ai_milo_visible", True)),
            "ai_prompting_enabled": bool(cfg.get("ai_prompting_enabled", False)),
        }

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/ui/preferences":
            return self._json(payload())
        return original_get(self)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/ui/preferences":
            try:
                body = self._read_json_body(max_bytes=50_000)
                update: dict[str, Any] = {}
                if "pwa_bottom_nav" in body:
                    update["pwa_bottom_nav"] = _normalize_nav(body.get("pwa_bottom_nav"))
                if "pwa_bottom_nav_labels" in body:
                    update["pwa_bottom_nav_labels"] = _normalize_labels(body.get("pwa_bottom_nav_labels"))
                for key in ("ai_luna_visible", "ai_milo_visible", "ai_prompting_enabled"):
                    if key in body:
                        update[key] = _normalize_bool(body.get(key), key)
                if not update:
                    return self._json({"error": "Nincs menthető PWA-beállítás."}, 400)
                app_module.save_config(update)
                return self._json(payload())
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)
        return original_post(self)

    handler_cls.do_GET = do_GET
    handler_cls.do_POST = do_POST
    _installed = True


__all__ = [
    "install_ui_preferences_v530", "PWA_NAV_MAX_ITEMS", "PWA_NAV_ALLOWED",
    "PWA_NAV_DEFAULT", "PWA_NAV_DEFAULT_LABELS", "PWA_NAV_LABEL_MAX_LENGTH",
    "_normalize_nav", "_normalize_labels", "_normalize_bool",
]
