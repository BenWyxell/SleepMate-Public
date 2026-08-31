from __future__ import annotations

import os
from urllib.parse import urlparse


_installed = False


def _installer_defaults() -> dict:
    """Read choices written by the MSI without making MSI own application state."""
    defaults = {"setup_language": "hu", "setup_start_with_windows": True}
    if os.name != "nt":
        return defaults
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\SleepMate\Installer") as key:
            try:
                value, _ = winreg.QueryValueEx(key, "SetupLanguage")
                defaults["setup_language"] = "en" if str(value).lower() == "en" else "hu"
            except OSError:
                pass
            try:
                value, _ = winreg.QueryValueEx(key, "StartWithWindows")
                defaults["setup_start_with_windows"] = bool(int(value))
            except (OSError, ValueError, TypeError):
                pass
    except OSError:
        pass
    return defaults


def install_setup_v5217(app_module) -> None:
    """Install the v5.2.17 first-run setup contract."""
    global _installed
    if _installed:
        return

    original_load_config = app_module.load_config
    original_get = app_module.Handler.do_GET
    original_post = app_module.Handler.do_POST
    installer = _installer_defaults()

    def load_config():
        cfg = original_load_config()
        fresh_setup = "setup_complete" not in cfg
        if "setup_language" not in cfg:
            cfg["setup_language"] = installer["setup_language"]
        cfg["setup_language"] = "en" if str(cfg.get("setup_language") or "hu").lower() == "en" else "hu"
        if fresh_setup:
            # Honour the choice made in the MSI immediately. The tray monitor
            # consumes /api/config and applies the matching HKCU Run entry.
            cfg["start_with_windows"] = bool(installer["setup_start_with_windows"])
            cfg["setup_complete"] = False
        if "setup_start_with_windows" not in cfg:
            cfg["setup_start_with_windows"] = bool(installer["setup_start_with_windows"])
        return cfg

    app_module.load_config = load_config

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/setup/status":
            cfg = app_module.load_config()
            return self._json({
                "required": not bool(cfg.get("setup_complete", False)),
                "complete": bool(cfg.get("setup_complete", False)),
                "language": str(cfg.get("setup_language") or "hu"),
                "start_with_windows_default": bool(cfg.get("setup_start_with_windows", True)),
                "version": app_module.APP_VERSION,
            })
        return original_get(self)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/setup/config":
            data = self._read_json_body(max_bytes=50_000)
            update = {}
            if "language" in data:
                value = str(data.get("language") or "hu").strip().lower()
                if value not in {"hu", "en"}:
                    raise ValueError("Unsupported setup language. / Nem támogatott telepítési nyelv.")
                update["setup_language"] = value
            if "complete" in data:
                update["setup_complete"] = bool(data.get("complete"))
            if "start_with_windows_default" in data:
                update["setup_start_with_windows"] = bool(data.get("start_with_windows_default"))
            cfg = app_module.save_config(update)
            return self._json({
                "ok": True,
                "required": not bool(cfg.get("setup_complete", False)),
                "complete": bool(cfg.get("setup_complete", False)),
                "language": str(cfg.get("setup_language") or "hu"),
                "start_with_windows_default": bool(cfg.get("setup_start_with_windows", True)),
            })
        return original_post(self)

    app_module.Handler.do_GET = do_GET
    app_module.Handler.do_POST = do_POST
    _installed = True


__all__ = ["install_setup_v5217"]
