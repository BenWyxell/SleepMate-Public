from __future__ import annotations

import re
import threading
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

from . import sleepsync_legacy as legacy


# Canonical ez Share root used by the proven standalone SleepSync 1.1.5.
# Important: the root is "A:", NOT "A:\\".
EZSHARE_ROOT = "A:"


class SleepSyncService(legacy.SleepSyncService):
    """SleepMate adapter around the proven SleepSync engine.

    The previous embedded build diverged from standalone in one critical detail:
    it queried the ez Share root as ``A:\\``.  The card's directory endpoint is
    the legacy ``dir=A:`` endpoint used by standalone SleepSync.  A wrong root
    can return a valid HTTP page with zero parseable SD files, which must never
    be interpreted as a successful sync.

    Automatic SleepSync is deliberately schedule-only. Card visibility may be
    displayed as status information, but it never triggers a sync by itself.

    A successful synchronization also creates the complete dated SD mirror and
    ZIP backup in the same ez Share connection. This keeps sync + backup atomic
    from the user's point of view and avoids a second Wi-Fi round-trip.
    """

    def __init__(self, app_module):
        super().__init__(app_module)
        # Portable and installed builds can start on a different auto-selected
        # local port. If a pre-existing Tailscale Serve entry still targets an
        # older SleepMate port, repair it after the HTTP server has had time to
        # bind. This also covers Serve configurations created manually rather
        # than through SleepMate's own toggle.
        threading.Thread(
            target=self._repair_stale_tailscale_serve,
            daemon=True,
            name="SleepMate-SleepSync-TailscaleRepair",
        ).start()

    def _default_settings(self) -> dict[str, Any]:
        cfg = super()._default_settings()
        cfg["auto_sync_mode"] = "scheduled"
        return cfg

    def _load_settings(self) -> dict[str, Any]:
        cfg = super()._load_settings()
        # Migrate every older "card_available" setting to schedule-only mode.
        if cfg.get("auto_sync_mode") != "scheduled":
            cfg["auto_sync_mode"] = "scheduled"
            legacy._json_write_atomic(self.settings_file, cfg)
        return cfg

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = dict(data)
            data["auto_sync_mode"] = "scheduled"
        return super().save_settings(data)

    def _repair_stale_tailscale_serve(self) -> None:
        """Rebind a stale SleepMate-looking Tailscale Serve target to this port.

        Tailscale Serve is machine-level state. A portable test build can share
        the same SleepMate data/config yet use another auto-selected port. When
        Serve still points at the old port, a phone may briefly render the cached
        PWA splash and then lose the backend. Only loopback ports close to the
        configured SleepMate port are adopted, so unrelated Serve services are
        left alone.
        """
        time.sleep(3.0)
        try:
            rm = getattr(self.handler, "remote_manager", None)
            if rm is None:
                return
            status = rm.tailscale_status()
            if not status.get("installed") or not status.get("online"):
                return
            if status.get("serve_active") and status.get("url"):
                return

            exe = rm._which(("tailscale.exe", "tailscale"))
            if not exe:
                return
            outputs: list[str] = []
            for args in ((exe, "serve", "status", "--json"), (exe, "serve", "status")):
                rc, out, err = rm._run(list(args), 8)
                if rc == 0 or out or err:
                    outputs.extend([out or "", err or ""])
            text = "\n".join(outputs)
            if not text.strip():
                return

            current_port = int(getattr(rm, "port", 0) or 0)
            current_target = f"127.0.0.1:{current_port}"
            if current_port and current_target in text:
                return

            ports = {
                int(token)
                for token in re.findall(r"(?:127\.0\.0\.1|localhost):([0-9]{4,5})", text, re.I)
            }
            try:
                preferred = int(self.app.load_config().get("port", 8895) or 8895)
            except Exception:
                preferred = 8895
            stale = sorted(
                p for p in ports
                if p != current_port and 1024 <= p <= 65435 and abs(p - preferred) <= 100
            )
            if not stale:
                return

            result = rm.tailscale_enable()
            try:
                self.app.save_config({"tailscale_auto_serve": True})
            except Exception:
                pass
            self.log(
                f"Tailscale Serve régi SleepMate célportja ({stale[0]}) "
                f"az aktuális portra ({current_port}) átállítva: {result.get('url') or 'HTTPS aktív'}"
            )
        except Exception as exc:
            self.log(f"Tailscale Serve automatikus portjavítás kihagyva: {exc}", "WARN")

    def _scheduler_loop(self) -> None:
        """Run automatic sync only at explicitly configured times."""
        last_scheduled_token: str | None = None
        while not self._scheduler_stop.is_set():
            try:
                if not self._settings.get("auto_sync_enabled"):
                    self._update_status(connection="készenlét", next_run=None)
                    self._scheduler_wakeup.wait(10)
                    self._scheduler_wakeup.clear()
                    continue

                now = datetime.now()
                days = set(self._settings.get("schedule_days") or legacy.DAY_ORDER)
                times = set(legacy._normalize_times(self._settings.get("schedule_times")))
                current_token = f"{now.date().isoformat()} {now.strftime('%H:%M')}"
                due_now = legacy.DAY_ORDER[now.weekday()] in days and now.strftime("%H:%M") in times
                next_run = self._next_scheduled_time()
                self._update_status(
                    connection="időzítés aktív",
                    next_run=next_run.isoformat(timespec="seconds") if next_run else None,
                )
                if (
                    due_now
                    and current_token != last_scheduled_token
                    and not self._status.get("running")
                    and not self._operation_lock.locked()
                ):
                    try:
                        self.start_sync("auto")
                        last_scheduled_token = current_token
                    except Exception as exc:
                        self.log(f"Időzített SleepSync indítási hiba: {exc}", "ERROR")

                self._scheduler_wakeup.wait(10)
                self._scheduler_wakeup.clear()
            except Exception as exc:
                self.log(f"SleepSync scheduler hiba: {exc}", "ERROR")
                self._scheduler_wakeup.wait(10)
                self._scheduler_wakeup.clear()

    def _scan_sd(
        self,
        sd_directory: str = EZSHARE_ROOT,
        relative_path: Path = Path(),
    ) -> tuple[list[dict[str, Any]], list[Path]]:
        return super()._scan_sd(sd_directory, relative_path)

    def _sync_connected(self, jid: str) -> dict[str, Any]:
        """Synchronize therapy data and create mirror + ZIP in one SD session."""
        self.log("Integrált szinkron indul: frissítés + teljes SD tükör + ZIP egy menetben.")
        backup = super()._backup_connected(jid)
        result = {
            "checked_files": int(backup.get("total_files", 0) or 0),
            "downloaded": int(backup.get("successful", 0) or 0),
            "unchanged": int(backup.get("skipped", 0) or 0),
            "errors": int(backup.get("failed", 0) or 0),
            "failed_files": [],
            "mandatory_seen": list(backup.get("mandatory_seen") or []),
            "mandatory_refreshed": list(backup.get("mandatory_refreshed") or []),
            "import": backup.get("import") or {},
            "days": len(self.handler.dataset.days()),
            "source": str(self.app.load_config().get("data_dir") or ""),
            "backup_created": True,
            "zip_path": str(backup.get("zip_path") or ""),
            "run_root": str(backup.get("run_root") or ""),
        }
        self._progress(
            jid,
            95,
            "Szinkron + biztonsági mentés",
            "Terápiás adatok, SD-tükör és ZIP elkészült.",
            total_files=result["checked_files"],
            work_files=result["downloaded"],
            processed_files=result["checked_files"],
            downloaded=result["downloaded"],
            unchanged=result["unchanged"],
            errors=result["errors"],
            current_file="—",
        )
        self.log(f"Integrált szinkron + SD mentés kész: {result}")
        return result

    def _close_new_captive_windows(self, before_pids: set[int]) -> None:
        # Standalone SleepSync can safely close the Windows captive-portal browser
        # because its UI is CustomTkinter. Embedded SleepSync runs inside a web
        # browser/PWA, so killing newly-created Edge/Chrome processes can also kill
        # a renderer used by SleepMate and surface as "Failed to fetch". Leave
        # the captive/login window alone; the engine talks to ezshare.card directly.
        self.log("Captive portal böngészőablak nincs bezárva az integrált web UI védelmében.")

    def _wait_http_ready(self) -> None:
        # Keep the SAME Wi-Fi connection while the old ez Share card wakes up.
        # We verify an actual parseable A: directory listing, not merely a 200 OK.
        configured = int(self._settings.get("ezshare_ready_timeout_seconds", 25) or 25)
        timeout = max(60, configured)
        deadline = time.time() + timeout
        attempt = 0
        last: Exception | None = None

        while time.time() < deadline:
            attempt += 1
            current = self.get_current_wifi_ssid()
            if not current or current.lower() != legacy.EZSHARE_WIFI_PROFILE.lower():
                last = RuntimeError(
                    f'Az aktív Wi-Fi nem "{legacy.EZSHARE_WIFI_PROFILE}", '
                    f'hanem "{current or "nincs kapcsolat"}".'
                )
            else:
                try:
                    entries = self._parse_directory(EZSHARE_ROOT)
                    if not entries:
                        raise RuntimeError(
                            'Az ez Share válaszolt, de az A: gyökérkönyvtár még '
                            'nem adott értelmezhető fájllistát.'
                        )
                    self.log(
                        f'ezShare A: könyvtár elérhető ({attempt}. próbálkozás, '
                        f'{len(entries)} gyökérelem).'
                    )
                    return
                except Exception as exc:
                    last = exc
                    self.log(
                        f'ezShare A: könyvtár még nem kész '
                        f'({attempt}. próba): {exc}',
                        "WARN",
                    )
            time.sleep(2)

        raise RuntimeError(
            'Az ez Share Wi-Fihez kapcsolódtunk, de az A: könyvtár '
            f'{timeout} másodpercen belül nem lett olvasható. '
            f'Utolsó hiba: {last}'
        )


_service: SleepSyncService | None = None
_service_lock = threading.RLock()


def get_service(app_module) -> SleepSyncService:
    global _service
    with _service_lock:
        if _service is None:
            _service = SleepSyncService(app_module)
        return _service


def install_sleepsync_integration(app_module) -> None:
    """Install SleepSync APIs and shared SleepMate backup coordination."""

    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET
    original_post = handler_cls.do_POST
    original_backup = handler_cls._backup_job
    original_restore = handler_cls._restore_backup_job

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/sleepsync/"):
            try:
                service = get_service(app_module)
                if path == "/api/sleepsync/status":
                    return self._json(service.status())
                if path == "/api/sleepsync/settings":
                    return self._json(service.settings())
                if path == "/api/sleepsync/history":
                    return self._json({"rows": service.history()})
                if path == "/api/sleepsync/log":
                    return self._json({"text": service.technical_log_tail()})
                if path == "/api/sleepsync/wifi":
                    return self._json(service.wifi_options())
                return self._json({"error": f"Ismeretlen SleepSync API végpont: {path}"}, 404)
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        return original_get(self)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/sleepsync/"):
            try:
                service = get_service(app_module)
                if path == "/api/sleepsync/start":
                    return self._json({"ok": True, "job": service.start_sync("manual")})
                if path == "/api/sleepsync/backup":
                    return self._json({"ok": True, "job": service.start_sd_backup()})
                if path == "/api/sleepsync/settings":
                    data = self._read_json_body(max_bytes=200_000)
                    return self._json({"ok": True, "settings": service.save_settings(data)})
                if path == "/api/sleepsync/history/clear":
                    service.clear_history()
                    return self._json({"ok": True})
                if path == "/api/sleepsync/open-folder":
                    data = self._read_json_body(max_bytes=20_000)
                    return self._json({"ok": True, "path": service.open_folder(str(data.get("kind") or ""))})
                return self._json({"error": f"Ismeretlen SleepSync API végpont: {path}"}, 404)
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)
        return original_post(self)

    # SleepSync state is under STATE_BASE/private/sleepsync, which is already
    # inside SleepMate's single full-system backup. No duplicate backup exists.
    def backup_job(self, jid: str):
        service = get_service(app_module)
        with service.exclusive():
            service.log("SleepMate és SleepSync teljes rendszermentés indul.")
            result = original_backup(self, jid)
            service.log("SleepMate és SleepSync teljes rendszermentés elkészült.")
            return result

    def restore_job(self, jid: str, uploaded: str):
        service = get_service(app_module)
        with service.exclusive():
            service.log("SleepMate és SleepSync teljes rendszer-visszaállítás indul.")
            result = original_restore(self, jid, uploaded)
            service.reload_from_disk()
            service.log("SleepMate és SleepSync teljes rendszer-visszaállítás elkészült.")
            return result

    handler_cls.do_GET = do_GET
    handler_cls.do_POST = do_POST
    handler_cls._backup_job = backup_job
    handler_cls._restore_backup_job = restore_job

    def bootstrap() -> None:
        for _ in range(120):
            if getattr(handler_cls, "jobs", None) is not None and getattr(handler_cls, "dataset", None) is not None:
                get_service(app_module)
                return
            time.sleep(0.25)

    threading.Thread(target=bootstrap, daemon=True, name="SleepMate-SleepSync-Bootstrap").start()
