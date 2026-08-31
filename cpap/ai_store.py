from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .patient_store import LocalProtector


class AIStore:
    """Encrypted provider credentials + encrypted AI result/chat history.

    API keys and the full AI history are protected with the same Windows DPAPI
    CurrentUser mechanism used by the patient store. The small state JSON only
    contains non-sensitive counters and cache/lock identifiers.
    """

    DEFAULTS = {
        "gemini": {
            "display_name": "Luna",
            "provider_label": "Google Gemini",
            "model": "gemini-3.6-flash",
        },
        "groq": {
            "display_name": "Milo",
            "provider_label": "Groq",
            "model": "openai/gpt-oss-120b",
        },
    }

    def __init__(self, base: Path):
        self.private_dir = base / "private"
        self.private_dir.mkdir(parents=True, exist_ok=True)
        self.protector = LocalProtector(self.private_dir)
        self.secret_path = self.private_dir / "ai_secrets.bin"
        self.history_path = self.private_dir / "ai_history.bin"
        self.state_path = self.private_dir / "ai_state.json"

    # ---------- encrypted blobs ----------
    def _read_encrypted_json(self, path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return dict(fallback)
        try:
            raw = self.protector.unprotect(path.read_bytes())
            obj = json.loads(raw.decode("utf-8"))
            return obj if isinstance(obj, dict) else dict(fallback)
        except Exception:
            return dict(fallback)

    def _write_encrypted_json(self, path: Path, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        path.write_bytes(self.protector.protect(raw))

    def _read_secrets(self) -> dict[str, Any]:
        sec = self._read_encrypted_json(self.secret_path, {})
        # v1.8 migration: provider was accidentally called "grok".
        if "groq" not in sec and isinstance(sec.get("grok"), dict):
            sec["groq"] = sec.pop("grok")
            self._write_encrypted_json(self.secret_path, sec)
        return sec

    def _write_secrets(self, obj: dict[str, Any]) -> None:
        self._write_encrypted_json(self.secret_path, obj)

    def _load_history(self) -> dict[str, Any]:
        return self._read_encrypted_json(self.history_path, {"analyses": {}})

    def _save_history(self, history: dict[str, Any]) -> None:
        self._write_encrypted_json(self.history_path, history)

    # ---------- provider config ----------
    @staticmethod
    def _mask(key: str) -> str:
        key = key.strip()
        if not key:
            return ""
        if len(key) <= 8:
            return "••••••••"
        return f"{key[:4]}••••••••{key[-4:]}"

    def get_api_key(self, provider: str) -> str:
        if provider not in self.DEFAULTS:
            raise ValueError("Ismeretlen AI szolgáltató.")
        # SleepMate v2.6+: kizárólag a program titkosított beállításában
        # elmentett API-kulcs használható. Windows/környezeti változókat
        # szándékosan figyelmen kívül hagyunk, hogy mindig egyértelmű legyen
        # melyik kulccsal történt a hívás.
        sec = self._read_secrets()
        row = sec.get(provider) if isinstance(sec.get(provider), dict) else {}
        return str(row.get("api_key") or "").strip()

    def provider_model(self, provider: str) -> str:
        if provider not in self.DEFAULTS:
            raise ValueError("Ismeretlen AI szolgáltató.")
        sec = self._read_secrets()
        row = sec.get(provider) if isinstance(sec.get(provider), dict) else {}
        return str(row.get("model") or self.DEFAULTS[provider]["model"]).strip() or self.DEFAULTS[provider]["model"]

    def get_provider_config(self) -> dict[str, Any]:
        sec = self._read_secrets()
        providers = {}
        for key, default in self.DEFAULTS.items():
            p = sec.get(key) if isinstance(sec.get(key), dict) else {}
            stored_key = str(p.get("api_key") or "").strip()
            providers[key] = {
                "display_name": str(p.get("display_name") or default["display_name"]),
                "provider_label": default["provider_label"],
                "model": str(p.get("model") or default["model"]),
                "configured": bool(stored_key),
                "key_hint": self._mask(stored_key),
                "key_fingerprint": hashlib.sha256(stored_key.encode("utf-8")).hexdigest()[:12] if stored_key else "",
                "key_source": "encrypted_settings" if stored_key else "none",
            }
        return {
            "providers": providers,
            "protection": self.protector.mode,
            "encrypted_at_rest": True,
        }

    def save_provider_config(self, data: dict[str, Any]) -> dict[str, Any]:
        sec = self._read_secrets()
        for key, default in self.DEFAULTS.items():
            current = sec.get(key) if isinstance(sec.get(key), dict) else {}
            new = dict(current)
            if f"{key}_api_key" in data:
                value = str(data.get(f"{key}_api_key") or "").strip()
                if value:
                    new["api_key"] = value
            if bool(data.get(f"{key}_clear_key")):
                new.pop("api_key", None)
            if f"{key}_display_name" in data:
                new["display_name"] = str(data.get(f"{key}_display_name") or default["display_name"]).strip() or default["display_name"]
            if f"{key}_model" in data:
                new["model"] = str(data.get(f"{key}_model") or default["model"]).strip() or default["model"]
            sec[key] = new
        self._write_secrets(sec)
        return self.get_provider_config()

    # ---------- non-sensitive counters/cache locks ----------
    def _load_state(self) -> dict[str, Any]:
        default = {"chat_usage": {}, "analysis_locks": {}}
        if not self.state_path.exists():
            return default
        try:
            obj = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(obj, dict):
                return default
            # v1.8 only stored local mock-analysis locks. They must NOT block the
            # first real API analysis after upgrading to v1.9.
            if "analysis_locks" not in obj:
                obj.pop("analyses", None)
                obj["analysis_locks"] = {}
            # migrate provider counter name
            for day_row in (obj.get("chat_usage") or {}).values():
                if isinstance(day_row, dict) and "groq" not in day_row and "grok" in day_row:
                    day_row["groq"] = day_row.pop("grok")
            return obj
        except Exception:
            return default

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def usage_status(self, dataset_signature: str) -> dict[str, Any]:
        state = self._load_state()
        today = date.today().isoformat()
        usage = state.setdefault("chat_usage", {}).get(today, {})
        providers = {}
        for p in self.DEFAULTS:
            used = int((usage.get(p) or 0))
            providers[p] = {"used": used, "limit": 10, "remaining": max(0, 10 - used)}
        current = {
            k: v for k, v in state.setdefault("analysis_locks", {}).items()
            if isinstance(v, dict) and str(v.get("dataset_signature")) == dataset_signature
        }
        return {"date": today, "chat": providers, "current_dataset_analyses": current}

    def can_analyze(self, analysis_key: str, dataset_signature: str) -> tuple[bool, str]:
        state = self._load_state()
        row = state.setdefault("analysis_locks", {}).get(analysis_key)
        if isinstance(row, dict) and row.get("dataset_signature") == dataset_signature:
            return False, "Ehhez az adatverzióhoz ez a kiértékelés már elkészült. A korábbi válasz a mentett AI-előzményekből bármikor visszanézhető."
        return True, ""

    def can_chat(self, provider: str) -> tuple[bool, str, dict[str, int]]:
        if provider not in self.DEFAULTS:
            raise ValueError("Ismeretlen AI szolgáltató.")
        state = self._load_state()
        today = date.today().isoformat()
        daily = state.setdefault("chat_usage", {}).setdefault(today, {})
        used = int(daily.get(provider) or 0)
        status = {"used": used, "limit": 10, "remaining": max(0, 10 - used)}
        if used >= 10:
            return False, "A napi 10 kérdéses keret ennél az AI-nál elfogyott.", status
        return True, "", status

    def record_chat_question(self, provider: str) -> dict[str, int]:
        ok, reason, _ = self.can_chat(provider)
        if not ok:
            raise ValueError(reason)
        state = self._load_state()
        today = date.today().isoformat()
        daily = state.setdefault("chat_usage", {}).setdefault(today, {})
        used = int(daily.get(provider) or 0) + 1
        daily[provider] = used
        self._save_state(state)
        return {"used": used, "limit": 10, "remaining": 10 - used}

    # ---------- encrypted history ----------
    def save_analysis(
        self,
        provider: str,
        analysis_key: str,
        dataset_signature: str,
        result: dict[str, Any],
        safe_payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if provider not in self.DEFAULTS:
            raise ValueError("Ismeretlen AI szolgáltató.")
        history = self._load_history()
        analysis_id = str(uuid.uuid4())
        now = datetime.now().isoformat(timespec="seconds")
        row = {
            "id": analysis_id,
            "provider": provider,
            "analysis_key": analysis_key,
            "dataset_signature": dataset_signature,
            "created_at": now,
            "result": result,
            "safe_payload": safe_payload,
            "messages": [],
            **(metadata or {}),
        }
        history.setdefault("analyses", {})[analysis_id] = row
        self._save_history(history)

        state = self._load_state()
        state.setdefault("analysis_locks", {})[analysis_key] = {
            "dataset_signature": dataset_signature,
            "analysis_id": analysis_id,
            "provider": provider,
            "created_at": now,
        }
        self._save_state(state)
        return row

    def list_history(self, limit: int = 100) -> list[dict[str, Any]]:
        history = self._load_history()
        out = []
        for row in history.get("analyses", {}).values():
            if not isinstance(row, dict):
                continue
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            period = result.get("period") if isinstance(result.get("period"), dict) else {}
            overall = result.get("overall") if isinstance(result.get("overall"), dict) else {}
            out.append({
                "id": row.get("id"),
                "provider": row.get("provider"),
                "analysis_key": row.get("analysis_key"),
                "created_at": row.get("created_at"),
                "title": overall.get("title") or "AI kiértékelés",
                "summary": overall.get("summary") or "",
                "status": overall.get("status") or "acceptable",
                "period": period,
                "model": row.get("model"),
                "fallback_used": bool(row.get("fallback_used")),
                "message_count": len(row.get("messages") or []),
                "prompt_version": row.get("prompt_version"),
            })
        out.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
        return out[: max(1, min(int(limit), 500))]

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        history = self._load_history()
        row = history.get("analyses", {}).get(str(analysis_id))
        return row if isinstance(row, dict) else None

    def append_chat(self, analysis_id: str, role: str, content: str, provider: str | None = None) -> dict[str, Any]:
        history = self._load_history()
        row = history.get("analyses", {}).get(str(analysis_id))
        if not isinstance(row, dict):
            raise ValueError("A mentett AI-beszélgetés nem található.")
        msg = {
            "role": role,
            "content": str(content),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        if provider:
            msg["provider"] = provider
        row.setdefault("messages", []).append(msg)
        self._save_history(history)
        return msg

    def clear_analysis_locks(self) -> None:
        state = self._load_state()
        state["analysis_locks"] = {}
        self._save_state(state)


def dataset_signature(root: Path) -> str:
    """Fast fingerprint of the managed read-only-import copy."""
    h = hashlib.sha256()
    root = Path(root)
    if not root.exists():
        return h.hexdigest()
    for p in sorted((x for x in root.rglob("*") if x.is_file()), key=lambda x: str(x.relative_to(root)).lower()):
        try:
            st = p.stat()
            rel = str(p.relative_to(root)).replace("\\", "/")
            h.update(rel.encode("utf-8", errors="replace"))
            h.update(str(st.st_size).encode())
            h.update(str(st.st_mtime_ns).encode())
        except OSError:
            continue
    return h.hexdigest()
