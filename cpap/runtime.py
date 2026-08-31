from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


APP_DIR_NAME = "SleepMate"
INSTALLED_MARKER = "installed.marker"
MIGRATION_MARKER = "migration-v5.json"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Directory containing the installed/portable SleepMate program tree."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_root() -> Path:
    """Read-only bundled resources (web, JSON catalogs, build metadata)."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle).resolve()
    return app_root()


def installed_mode(root: Path | None = None) -> bool:
    root = (root or app_root()).resolve()
    return is_frozen() or (root / INSTALLED_MARKER).exists() or os.environ.get("SLEEPMATE_INSTALLED") == "1"


def state_root(root: Path | None = None) -> Path:
    """Writable SleepMate state.

    Portable/source builds keep their historical in-folder state. Installed
    Windows builds use a separate per-user LocalAppData state directory, while
    binaries live under LocalAppData\\Programs. This keeps updates non-admin and
    separates therapy/patient state from replaceable program files.
    """
    override = str(os.environ.get("SLEEPMATE_STATE_DIR") or "").strip()
    if override:
        return Path(os.path.expandvars(override)).expanduser().resolve()

    root = (root or app_root()).resolve()
    if not installed_mode(root):
        return root

    if os.name == "nt":
        # Per-user state matches Windows DPAPI protection and allows the app and
        # updater to run without administrator rights. The installer itself is a
        # per-user install under %LOCALAPPDATA%\Programs\SleepMate.
        local = str(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")).strip()
        return (Path(local) / APP_DIR_NAME).resolve()

    # Non-Windows frozen builds are development-only today. Keep writable state
    # in the standard local state location where possible.
    xdg = str(os.environ.get("XDG_STATE_HOME") or "").strip()
    if xdg:
        return (Path(xdg).expanduser() / APP_DIR_NAME).resolve()
    return (Path.home() / ".local" / "state" / APP_DIR_NAME).resolve()


def config_path(root: Path | None = None) -> Path:
    return state_root(root) / "config.json"


def private_root(root: Path | None = None) -> Path:
    return state_root(root) / "private"


def ensure_state_layout(root: Path | None = None) -> Path:
    state = state_root(root)
    state.mkdir(parents=True, exist_ok=True)
    (state / "private").mkdir(parents=True, exist_ok=True)
    return state



def migrate_from_path(source_root: Path | str, root: Path | None = None) -> dict[str, Any]:
    """Copy an explicitly selected legacy SleepMate state into installed state."""
    app = (root or app_root()).resolve()
    state = ensure_state_layout(app)
    source = Path(source_root).expanduser().resolve()
    if source == state:
        return {"needed": False, "migrated": False, "source": str(source), "destination": str(state), "copied_files": 0, "copied_bytes": 0, "errors": []}
    legacy_private = source / "private"
    legacy_config = source / "config.json"
    copied_files = 0
    copied_bytes = 0
    errors: list[str] = []
    try:
        if legacy_config.is_file() and not (state / "config.json").exists():
            shutil.copy2(legacy_config, state / "config.json")
            copied_files += 1
            copied_bytes += legacy_config.stat().st_size
    except Exception as exc:
        errors.append(f"config.json: {exc}")
    if legacy_private.is_dir():
        for src in legacy_private.rglob("*"):
            try:
                rel = src.relative_to(legacy_private)
                dst = state / "private" / rel
                if src.is_dir():
                    dst.mkdir(parents=True, exist_ok=True)
                elif src.is_file() and not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    copied_files += 1
                    copied_bytes += src.stat().st_size
            except Exception as exc:
                errors.append(f"{src}: {exc}")
                if len(errors) >= 20:
                    break
    result = {
        "format": "sleepmate-state-migration", "version": 1,
        "migrated": copied_files > 0, "completed_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(source), "destination": str(state), "copied_files": copied_files,
        "copied_bytes": copied_bytes, "errors": errors,
    }
    return result

def migrate_legacy_state(root: Path | None = None) -> dict[str, Any]:
    """Safely seed installed state from an in-place legacy portable tree."""
    app = (root or app_root()).resolve()
    state = ensure_state_layout(app)
    if state == app:
        return {"needed": False, "migrated": False, "mode": "portable", "state_root": str(state)}
    marker = state / MIGRATION_MARKER
    if marker.exists():
        try:
            info = json.loads(marker.read_text(encoding="utf-8"))
            if isinstance(info, dict):
                return {**info, "needed": False, "state_root": str(state)}
        except Exception:
            pass
    result = migrate_from_path(app, app)
    if not result.get("errors"):
        marker.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**result, "needed": bool(result.get("errors")), "state_root": str(state)}

