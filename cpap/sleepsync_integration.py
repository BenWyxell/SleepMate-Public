from __future__ import annotations

import hashlib
import threading
import time
import urllib.parse
from typing import Any

from .sleepsync_engine_v2 import (
    SleepSyncService,
    get_service,
    install_sleepsync_integration as _install_engine,
)
from .sleepsync_wifi_v5215 import install_sleepsync_wifi_v5215


# Install the Windows/ez Share acquisition layer before the singleton service is
# ever created. This keeps the v2 scan/backup/scheduler engine unchanged while
# replacing only WLAN acquisition, HTTP readiness and retry persistence.
install_sleepsync_wifi_v5215()

# The 2026-08-29 field log also captured a card-side failure mode: after a strong
# successful association the ez Share HTTP endpoint can stop answering and the
# SSID itself can disappear while other WLANs remain visible. Install presence
# gating over the active v5.2.15 recovery engine, but *under* the automatic grace
# layer below. That preserves the field-proven clean 12-second Windows association
# window as the very first strategy; only after it fails do we scan to decide
# whether active WLAN recovery is meaningful at all.
from .sleepsync_wifi_presence_v5216 import install_sleepsync_wifi_presence_v5216

install_sleepsync_wifi_presence_v5216()

# Field log 2026-08-29 showed Windows can associate to ez Share reliably on its
# own immediately after competing autoconnect profiles are suspended. Give that
# path a clean grace window before issuing an explicit connect command; only then
# fall back to the presence-aware v5.2.16 gate and, when the AP is actually
# visible, the escalating v5.2.15 recovery engine.
from .sleepsync_wifi_autograce_v5215 import install_sleepsync_wifi_autograce_v5215

install_sleepsync_wifi_autograce_v5215()


# Schedule saving must not depend on unrelated path text boxes being populated.
# The UI posts the whole settings form, so an empty/unhydrated path field used to
# make an otherwise valid schedule save fail. Empty values now mean "keep the
# current value". If an old/corrupt config has no backup path at all, restore the
# engine's default backup directory; the legacy saver creates it automatically.
_engine_save_settings = SleepSyncService.save_settings


def _resilient_save_settings(self: SleepSyncService, data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        return _engine_save_settings(self, data)

    payload = dict(data)
    payload["auto_sync_mode"] = "scheduled"

    if "backup_root" in payload and not str(payload.get("backup_root") or "").strip():
        current = str(getattr(self, "_settings", {}).get("backup_root") or "").strip()
        if not current:
            current = str(self._default_settings().get("backup_root") or "").strip()
        if current:
            payload["backup_root"] = current
        else:
            payload.pop("backup_root", None)

    if "therapy_data_dir" in payload and not str(payload.get("therapy_data_dir") or "").strip():
        payload.pop("therapy_data_dir", None)

    return _engine_save_settings(self, payload)


SleepSyncService.save_settings = _resilient_save_settings


# The legacy acquisition path refreshes SleepMate while the PC is still connected
# to the isolated ez Share WLAN. A Web Push attempt at that exact point has no
# internet route and therefore cannot reach Apple. Keep the proven acquisition
# sequence intact, then send the user-facing completion notification only after
# _sync_job has returned from _run_with_wifi and restored the previous internet
# connection. Notification delivery is best effort and never changes sync success.
_engine_sync_job = SleepSyncService._sync_job


def _changed_import_count(result: dict[str, Any]) -> int:
    imported = result.get("import") if isinstance(result, dict) else None
    if not isinstance(imported, dict):
        return 0
    total = 0
    for key in ("changed_files", "copied_files", "new_files"):
        value = imported.get(key)
        if isinstance(value, (list, tuple, set, dict)):
            total += len(value)
        elif isinstance(value, (int, float)):
            total += int(value)
    return total


def _post_sync_notifications(self: SleepSyncService, result: dict[str, Any]) -> None:
    # Give Windows a brief moment after WLAN restoration for the default route and
    # DNS to settle. This runs outside the SleepSync job, so UI completion is not
    # delayed by Web Push provider latency.
    time.sleep(2.0)
    ps = getattr(self.handler, "push_service", None)
    if not ps:
        return
    try:
        changed = _changed_import_count(result)
        checked = int(result.get("checked_files", 0) or 0)
        body = (
            f"A szinkron sikeresen befejeződött • {changed} új vagy módosult fájl feldolgozva."
            if changed
            else "A szinkron sikeresen befejeződött • minden naprakész."
        )
        push_result = ps.send(
            "sync_complete",
            "SleepSync szinkron kész",
            body,
            "/#sleepsync",
            {"checked_files": checked, "changed_files": changed},
        )
        if push_result.get("failed"):
            self.log(
                "SleepSync sikerértesítés nem minden feliratkozásra jutott el: "
                + "; ".join(str(x) for x in (push_result.get("errors") or [])[:2]),
                "WARN",
            )
    except Exception as exc:
        self.log(f"SleepSync sikerértesítés küldése sikertelen: {exc}", "WARN")

    # Only changed therapy data can introduce a new diagnostic condition. Run
    # this after internet restoration as well; BRP/PLD/EVE completeness details
    # are INFO from v5.3.25 and therefore do not participate in warning pushes.
    if _changed_import_count(result) <= 0:
        return
    try:
        diag = self.handler.dataset.diagnostics()
        warning_rows = [x for x in (diag.get("errors") or []) if isinstance(x, dict)]
        if not warning_rows:
            return
        normalized = [
            f"{str(x.get('title') or '').strip()}|{str(x.get('message') or '').strip()}"
            for x in warning_rows
        ]
        signature = hashlib.sha256("\n".join(sorted(normalized)).encode("utf-8")).hexdigest()
        first = warning_rows[0]
        title = str(first.get("title") or "Adatfigyelmeztetés").strip()
        message = str(first.get("message") or "Ellenőrizd a Naplók oldalt.").strip()
        body = f"{title} – {message}"
        if len(warning_rows) > 1:
            body += f" (+{len(warning_rows)-1} további figyelmeztetés)"
        ps.send_warning_once(signature, "Adatfigyelmeztetés", body, "/#logs")
    except Exception as exc:
        self.log(f"SleepSync utáni diagnosztikai push ellenőrzés sikertelen: {exc}", "WARN")


def _sync_job_with_post_push(self: SleepSyncService, jid: str, trigger: str = "manual") -> dict[str, Any]:
    result = _engine_sync_job(self, jid, trigger)
    threading.Thread(
        target=_post_sync_notifications,
        args=(self, result),
        daemon=True,
        name="SleepMate-SleepSync-Push",
    ).start()
    return result


SleepSyncService._sync_job = _sync_job_with_post_push


def _safe_boot_value(value: Any, depth: int = 0) -> Any:
    """Keep client boot diagnostics compact and free from arbitrary payloads."""
    if depth > 3:
        return "…"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:1200]
    if isinstance(value, list):
        return [_safe_boot_value(v, depth + 1) for v in value[:40]]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, val in list(value.items())[:60]:
            out[str(key)[:80]] = _safe_boot_value(val, depth + 1)
        return out
    return str(value)[:1200]


def install_sleepsync_integration(app_module) -> None:
    """Install SleepSync plus passive phone/PWA boot telemetry.

    The telemetry endpoint does not participate in application startup. It only
    receives best-effort diagnostic events from the browser so an iOS/Tailscale
    failure can be diagnosed from SleepMate's normal persistent log instead of
    by guessing at frontend timing.
    """
    _install_engine(app_module)

    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET
    original_post = handler_cls.do_POST

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/mobile-boot/logs":
            rows = [
                row for row in self.persistent_log.list(800)
                if str(row.get("kind") or "") == "mobile_boot"
            ][:250]
            return self._json({"rows": rows})
        return original_get(self)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/mobile-boot":
            try:
                data = self._read_json_body(max_bytes=120_000)
                safe = _safe_boot_value(data)
                if not isinstance(safe, dict):
                    safe = {"payload": safe}
                stage = str(safe.get("stage") or "event")[:120]
                safe["server_user_agent"] = str(self.headers.get("User-Agent") or "")[:500]
                safe["server_host"] = str(self.headers.get("Host") or "")[:300]
                level = "HIBA" if stage in {"window-error", "unhandled-rejection", "probe-failed", "script-error"} else "INFO"
                self.persistent_log.append(level, "mobile_boot", f"Mobil/PWA boot: {stage}", safe)
                return self._json({"ok": True})
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)
        return original_post(self)

    handler_cls.do_GET = do_GET
    handler_cls.do_POST = do_POST


__all__ = ["SleepSyncService", "get_service", "install_sleepsync_integration"]
