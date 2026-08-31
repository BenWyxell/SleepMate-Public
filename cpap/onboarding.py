from __future__ import annotations

import json
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

ONBOARDING_VERSION = 1


def _path(app_module) -> Path:
    target = app_module.STATE_BASE / "private" / "onboarding.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _default() -> dict[str, Any]:
    return {
        "version": ONBOARDING_VERSION,
        "completed": False,
        "completed_at": None,
        "last_step": 1,
        "choices": {},
    }


def _load(app_module) -> dict[str, Any]:
    state = _default()
    path = _path(app_module)
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except Exception:
            pass
    state["version"] = ONBOARDING_VERSION
    state["completed"] = bool(state.get("completed"))
    try:
        state["last_step"] = max(1, min(6, int(state.get("last_step") or 1)))
    except Exception:
        state["last_step"] = 1
    if not isinstance(state.get("choices"), dict):
        state["choices"] = {}
    return state


def _write(app_module, state: dict[str, Any]) -> dict[str, Any]:
    path = _path(app_module)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return state


def _safe_choices(value: Any) -> dict[str, Any]:
    """Persist only non-secret first-run choices; never credentials or tokens."""
    if not isinstance(value, dict):
        return {}
    allowed = {
        "data_source_configured",
        "sleepsync_enabled",
        "remote_mode",
        "tailscale_installed",
        "cloudflare_installed",
        "backup_enabled",
        "gemini_configured",
        "groq_configured",
        "pwa_attempted",
        "notifications_attempted",
    }
    out: dict[str, Any] = {}
    for key in allowed:
        if key not in value:
            continue
        raw = value[key]
        if key == "remote_mode":
            mode = str(raw or "local").strip().lower()
            out[key] = mode if mode in {"local", "tailscale", "cloudflare"} else "local"
        else:
            out[key] = bool(raw)
    return out


def install_onboarding(app_module) -> None:
    """Add the persistent SleepMate first-run wizard state endpoints."""
    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET
    original_post = handler_cls.do_POST

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/onboarding/status":
            state = _load(app_module)
            return self._json({
                **state,
                "app_version": app_module.APP_VERSION,
                "state_file": "private/onboarding.json",
            })
        return original_get(self)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/onboarding/state":
            data = self._read_json_body(max_bytes=50_000)
            action = str(data.get("action") or "progress").strip().lower()
            state = _load(app_module)

            if action == "reset":
                state = _default()
            elif action in {"progress", "complete"}:
                if "step" in data:
                    try:
                        state["last_step"] = max(1, min(6, int(data.get("step") or 1)))
                    except Exception:
                        pass
                incoming = _safe_choices(data.get("choices"))
                current = state.get("choices") if isinstance(state.get("choices"), dict) else {}
                current.update(incoming)
                state["choices"] = current
                if action == "complete":
                    state["completed"] = True
                    state["completed_at"] = datetime.now().isoformat(timespec="seconds")
                    state["last_step"] = 6
            else:
                raise ValueError("Ismeretlen onboarding művelet.")

            state["version"] = ONBOARDING_VERSION
            _write(app_module, state)
            try:
                self.persistent_log.append(
                    "INFO",
                    "onboarding",
                    "SleepMate első beállítás állapota frissítve.",
                    {
                        "action": action,
                        "step": state.get("last_step"),
                        "completed": state.get("completed"),
                        "choices": state.get("choices"),
                    },
                )
            except Exception:
                pass
            return self._json({"ok": True, **state})

        return original_post(self)

    handler_cls.do_GET = do_GET
    handler_cls.do_POST = do_POST


__all__ = ["ONBOARDING_VERSION", "install_onboarding"]
