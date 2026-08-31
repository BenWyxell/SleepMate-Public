from __future__ import annotations

import time
from pathlib import Path


_installed = False


def install_v511_features() -> None:
    """Install deliberately small 5.1.1 compatibility patches.

    The 5.1 line keeps the proven report implementation intact. This hook fixes
    PDF branding and adds release-level hardening around the optional Drive
    mirror without rewriting the stable SleepMate core.
    """
    global _installed
    if _installed:
        return

    from . import report_pdf
    from . import google_drive_integration as drive

    report_cls = report_pdf.SleepMateReport
    original_init = report_cls.__init__
    original_page = report_cls._page

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        base = Path(self.ctx.base_dir)
        candidates = (
            base / "web" / "assets" / "sleepmate-icon-v410.webp",
            base / "web" / "assets" / "pwa-512.png",
            base / "web" / "assets" / "pwa-192.png",
        )
        for candidate in candidates:
            if candidate.is_file():
                self.logo_path = candidate
                break

    def patched_page(self, canvas, doc):
        # The logo itself already contains the SleepMate name. Suppress only the
        # large redundant wordmark on page 1; the normal report header/footer on
        # subsequent pages is intentionally untouched.
        if int(getattr(doc, "page", 0) or 0) != 1:
            return original_page(self, canvas, doc)

        original_draw_string = canvas.drawString

        def cover_draw_string(x, y, text, *args, **kwargs):
            if str(text).strip() == "SleepMate":
                return None
            return original_draw_string(x, y, text, *args, **kwargs)

        canvas.drawString = cover_draw_string
        try:
            return original_page(self, canvas, doc)
        finally:
            canvas.drawString = original_draw_string

    report_cls.__init__ = patched_init
    report_cls._page = patched_page

    # Changing the cloud target must not leave an old folder id or an old OAuth
    # client secret attached to the new configuration.
    drive_cls = drive.GoogleDriveService
    original_drive_save = drive_cls.save_settings

    def patched_drive_save(self, data):
        old_client = str(self._settings.get("client_id") or "")
        old_folder = str(self._settings.get("folder_name") or drive.DEFAULT_FOLDER)
        result = original_drive_save(self, data)
        new_client = str(self._settings.get("client_id") or "")
        new_folder = str(self._settings.get("folder_name") or drive.DEFAULT_FOLDER)
        if new_client != old_client and not str(data.get("client_secret") or "").strip():
            secrets_payload = self.secrets.read()
            secrets_payload.pop("client_secret", None)
            self.secrets.write(secrets_payload)
        if new_folder != old_folder:
            state = self._state()
            state.pop("folder_id", None)
            state["uploaded"] = {}
            drive._json_write_atomic(self.state_file, state)
            self.log("A Google Drive célmappa megváltozott; a felhős tükör újraellenőrzése indul.")
        return result

    def patched_auto_upload_loop(self):
        # Mirror every pending automatic backup, oldest first. If the PC was
        # offline for several backup cycles, none of those completed local ZIPs
        # are silently skipped when internet returns.
        while not self._stop.wait(25):
            try:
                with self._settings_lock:
                    enabled = bool(self._settings.get("auto_upload"))
                if not enabled or not self.secrets.read().get("refresh_token"):
                    continue
                rows = self._local_backups()
                if not rows:
                    continue
                state = self._state()
                uploaded = state.get("uploaded") if isinstance(state.get("uploaded"), dict) else {}
                pending = None
                for path in reversed(rows):
                    signature = f"{path.stat().st_size}:{path.stat().st_mtime_ns}"
                    if uploaded.get(path.name) != signature:
                        pending = path
                        break
                if pending is None:
                    continue
                if not self._operation_lock.acquire(blocking=False):
                    continue
                try:
                    self.upload_backup(pending)
                finally:
                    self._operation_lock.release()
            except Exception as exc:
                self._save_state(last_error=str(exc))
                self.log(f"Google Drive automatikus backup feltöltés később újrapróbálva: {exc}", "WARN")

    drive_cls.save_settings = patched_drive_save
    drive_cls._auto_upload_loop = patched_auto_upload_loop
    _installed = True
