from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


MSI_HEADER = bytes.fromhex("D0CF11E0A1B11AE1")
IS_WINDOWS = os.name == "nt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {text}\n")


def wait_for_exit(pid: int, timeout: float = 60) -> bool:
    if pid <= 0:
        return True
    end = time.time() + max(0.01, timeout)
    while time.time() < end:
        try:
            if os.name == "nt":
                import ctypes
                from ctypes import wintypes

                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                SYNCHRONIZE = 0x00100000
                STILL_ACTIVE = 259
                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
                )
                if not handle:
                    return True
                try:
                    exit_code = wintypes.DWORD()
                    if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                        return True
                    if int(exit_code.value) != STILL_ACTIVE:
                        return True
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)
            else:
                os.kill(pid, 0)
        except Exception:
            return True
        time.sleep(0.15)
    return False


def stop_process_tree(pid: int, log_path: Path, label: str, timeout: float = 12) -> bool:
    """Force-stop one known process tree as the last-resort updater fallback."""
    if pid <= 0:
        return True
    if wait_for_exit(pid, 0.05):
        return True
    try:
        if os.name == "nt":
            cp = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
                timeout=10,
                check=False,
            )
            log(log_path, f"{label}: taskkill exit={cp.returncode} (PID {pid}).")
        else:
            os.kill(pid, 15)
    except Exception as exc:
        log(log_path, f"FIGYELMEZTETÉS: {label} leállítási kérés hibázott: {exc}")
    stopped = wait_for_exit(pid, timeout)
    log(log_path, f"{label}: {'leállt' if stopped else 'nem állt le időben'} (PID {pid}).")
    return stopped


def request_graceful_tray_exit(pid: int, state_dir: Path, log_path: Path, timeout: float = 8.0) -> bool:
    """Ask the running pystray instance to remove its icon before it exits.

    Force-killing the tray leaves notification-area ghost icons behind until
    Explorer redraws the overflow panel. The tray watches this request file and
    calls its normal quit() path, which executes pystray.Icon.stop(). Only if the
    request is not honoured do we fall back to taskkill.
    """
    if pid <= 0 or wait_for_exit(pid, 0.05):
        return True
    request = state_dir / "private" / "quit_tray.request"
    try:
        request.parent.mkdir(parents=True, exist_ok=True)
        request.write_text(json.dumps({"pid": pid, "time": time.time()}), encoding="utf-8")
        log(log_path, f"Régi SleepMate tálca: szabályos leállítás kérése elküldve (PID {pid}).")
    except Exception as exc:
        log(log_path, f"FIGYELMEZTETÉS: a szabályos tálcaleállítási kérés nem írható ki: {exc}")
        return False
    stopped = wait_for_exit(pid, timeout)
    if stopped:
        log(log_path, f"Régi SleepMate tálca szabályosan leállt, ikon eltávolítva (PID {pid}).")
        return True
    log(log_path, f"FIGYELMEZTETÉS: a tálca {timeout:.1f} mp alatt nem állt le szabályosan; kényszerített tartalék leállítás következik.")
    return False


def stop_sleepmate_image_processes(exe_path: Path, log_path: Path, label: str) -> None:
    """Force-stop every remaining process using the installed SleepMate image.

    Normal update flow has already shut the known tray down gracefully, so this
    is only a lock-safety fallback for orphaned backends or genuinely stale
    duplicates. The updater itself is SleepMateUpdater.exe and is unaffected.
    """
    if os.name != "nt":
        return
    image_name = Path(exe_path).name or "SleepMate.exe"
    try:
        cp = subprocess.run(
            ["taskkill", "/IM", image_name, "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
            timeout=10,
            check=False,
        )
        if cp.returncode not in (0, 128):
            log(log_path, f"FIGYELMEZTETÉS: {label}: taskkill /IM {image_name} exit={cp.returncode}.")
        elif cp.returncode == 0:
            log(log_path, f"{label}: minden megmaradt {image_name} folyamat leállítási kérése elküldve.")
    except Exception as exc:
        log(log_path, f"FIGYELMEZTETÉS: {label}: {image_name} tömeges leállítása hibázott: {exc}")
    time.sleep(0.35)


def terminate_spawned(proc: subprocess.Popen | None, log_path: Path, label: str) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
                timeout=10,
                check=False,
            )
        else:
            proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
        log(log_path, f"{label} leállítva (PID {proc.pid}).")
    except Exception as exc:
        log(log_path, f"FIGYELMEZTETÉS: {label} leállítása nem sikerült: {exc}")


def _installer_owned_file(child: Path) -> bool:
    """Keep Inno Setup's uninstall registration files during ZIP self-updates."""
    name = child.name.lower()
    return child.is_file() and name.startswith("unins") and child.suffix.lower() in {".exe", ".dat", ".msg"}


def program_entries(root: Path):
    excluded = {"private", "config.json", ".git", ".pytest_cache", "__pycache__"}
    for child in list(root.iterdir()):
        if child.name in excluded or _installer_owned_file(child):
            continue
        yield child


def clear_program(root: Path) -> None:
    for child in program_entries(root):
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except FileNotFoundError:
            pass


def copy_program(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for src in source.iterdir():
        if src.name in {"private", "config.json", ".git", ".pytest_cache", "__pycache__", "rollback.json"}:
            continue
        dst = target / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        elif src.is_file():
            shutil.copy2(src, dst)


def replace_program(source: Path, target: Path, launcher_exe: Path, log_path: Path, attempts: int = 8) -> None:
    """Replace the program tree with bounded Windows-lock recovery."""
    last_exc: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        if os.name == "nt":
            stop_sleepmate_image_processes(launcher_exe, log_path, "Programfájlcsere előtti takarítás")
        try:
            clear_program(target)
            copy_program(source, target)
            return
        except (PermissionError, OSError) as exc:
            last_exc = exc
            log(log_path, f"Programfájlcsere {attempt}/{attempts} próbálkozás sikertelen: {exc}")
            if attempt < attempts:
                if os.name == "nt":
                    stop_sleepmate_image_processes(launcher_exe, log_path, "Zároló folyamatok utóellenőrzése")
                time.sleep(min(2.0, 0.35 * attempt))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("A programfájlcsere ismeretlen okból nem sikerült.")


def launch_backend(app_dir: Path, port: int, log_path: Path, launcher_exe: Path | None = None) -> subprocess.Popen:
    flags = 0x08000000 if os.name == "nt" else 0
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    if launcher_exe and launcher_exe.is_file():
        cmd = [str(launcher_exe), "--backend", "--no-browser", "--port", str(int(port))]
        cwd = app_dir
    else:
        cmd = [sys.executable, str(app_dir / "app.py"), "--no-browser", "--port", str(int(port))]
        cwd = app_dir
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        creationflags=flags,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    log(log_path, f"SleepMate backend indítás kezdeményezve a {port}-es porton (PID {proc.pid}).")
    return proc


def start_tray(vbs: Path, app_dir: Path, log_path: Path, launcher_exe: Path | None = None) -> subprocess.Popen | None:
    try:
        flags = 0x08000000 if os.name == "nt" else 0
        env = os.environ.copy()
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        if launcher_exe and launcher_exe.is_file():
            proc = subprocess.Popen(
                [str(launcher_exe)],
                cwd=str(app_dir),
                creationflags=flags,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif os.name == "nt" and vbs.is_file():
            proc = subprocess.Popen(["wscript.exe", str(vbs)], cwd=str(app_dir), creationflags=flags)
        else:
            return None
        log(log_path, f"A tálcaalkalmazás elindítva (PID {proc.pid}).")
        return proc
    except Exception as exc:
        log(log_path, f"FIGYELMEZTETÉS: a tálcaalkalmazás indítása nem sikerült: {exc}")
        return None


def restart_tray(tray_pid: int, vbs: Path, app_dir: Path, log_path: Path, launcher_exe: Path | None = None) -> subprocess.Popen | None:
    """Compatibility helper: stop a known old tray, then start the replacement."""
    if tray_pid > 0:
        stop_process_tree(tray_pid, log_path, "SleepMate tálcaalkalmazás")
    return start_tray(vbs, app_dir, log_path, launcher_exe)


def wait_health(marker: Path, version: str, started_after: float, timeout: int) -> bool:
    end = time.time() + max(5, timeout)
    while time.time() < end:
        try:
            obj = json.loads(marker.read_text(encoding="utf-8"))
            if str(obj.get("version") or "") == version and marker.stat().st_mtime >= started_after:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def cleanup_stage(plan_path: Path, log_path: Path) -> None:
    try:
        parent = plan_path.parent
        if parent.name.startswith(("stage-", "rollback-")):
            shutil.rmtree(parent, ignore_errors=True)
            log(log_path, "Ideiglenes frissítési csomag kitakarítva.")
    except Exception:
        pass


def save_result(state_path: Path, result: dict) -> None:
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        state["last_result"] = result
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def restore_previous(
    *, app_dir: Path, rollback_dir: Path, launcher_exe: Path, vbs: Path,
    port: int, log_path: Path, state_path: Path, from_version: str,
    failed_version: str, marker: Path, timeout: int, restart_tray_requested: bool,
) -> bool:
    try:
        for attempt in range(8):
            try:
                replace_program(rollback_dir, app_dir, launcher_exe, log_path, attempts=2)
                break
            except Exception:
                if attempt == 7:
                    raise
                time.sleep(1)
        try:
            marker.unlink()
        except FileNotFoundError:
            pass
        started = time.time()
        restored = launch_backend(app_dir, port, log_path, launcher_exe)
        healthy = wait_health(marker, from_version, started, min(timeout, 45))
        if not healthy:
            log(log_path, "FIGYELMEZTETÉS: a rollback backend egészségjelzése nem érkezett meg időben.")
        if restart_tray_requested:
            restart_tray(0, vbs, app_dir, log_path, launcher_exe)
        save_result(state_path, {
            "status": "rolled_back",
            "failed_version": failed_version,
            "restored_version": from_version,
            "time": datetime.now().isoformat(timespec="seconds"),
            "backend_pid": restored.pid,
        })
        log(log_path, f"Rollback kész: {from_version} újraindítva.")
        return True
    except Exception as exc:
        log(log_path, f"KRITIKUS: automatikus rollback sikertelen: {exc}")
        return False


def validate_msi_plan(plan_path: Path, plan: dict) -> tuple[Path, Path]:
    installer = Path(str(plan.get("installer_path") or "")).resolve()
    version = str(plan.get("to_version") or "").strip()
    expected_name = f"SleepMate_Setup_v{version}.msi"
    if installer.parent != plan_path.parent or installer.name != expected_name:
        raise RuntimeError("A frissítési terv nem a várt, stage-elt MSI release assetre mutat.")
    if not installer.is_file() or installer.stat().st_size < len(MSI_HEADER):
        raise RuntimeError("A stage-elt MSI frissítési csomag hiányzik vagy üres.")
    with installer.open("rb") as source:
        if source.read(len(MSI_HEADER)) != MSI_HEADER:
            raise RuntimeError("A stage-elt csomag nem MSI konténer.")
    expected_hash = str(plan.get("installer_sha256") or "").lower().strip()
    if len(expected_hash) != 64 or sha256(installer).lower() != expected_hash:
        raise RuntimeError("Az MSI SHA-256 újraellenőrzése sikertelen.")
    installer_log = Path(str(plan.get("installer_log") or (plan_path.parent / "msiexec.log"))).resolve()
    installer_log.parent.mkdir(parents=True, exist_ok=True)
    return installer, installer_log


def install_verified_msi(
    *, plan_path: Path, plan: dict, app_dir: Path, launcher_exe: Path,
    vbs: Path, marker: Path, port: int, log_path: Path, state_path: Path,
    timeout: int, restart_tray_requested: bool,
) -> int:
    try:
        installer, installer_log = validate_msi_plan(plan_path, plan)
    except Exception as exc:
        log(log_path, f"HIBA: MSI validáció sikertelen: {exc}")
        return 9

    system_root = Path(str(os.environ.get("SystemRoot") or r"C:\Windows")).resolve()
    msiexec = system_root / "System32" / "msiexec.exe"
    if not IS_WINDOWS or not msiexec.is_file():
        log(log_path, "HIBA: a szabványos Windows Installer (msiexec.exe) nem érhető el.")
        return 10

    command = [
        str(msiexec), "/i", str(installer), "/qn", "/norestart",
        "REBOOT=ReallySuppress", f"INSTALLFOLDER={app_dir}",
        "/L*v", str(installer_log),
    ]
    log(log_path, f"Windows Installer indul unattended módban: {installer.name}")
    try:
        completed = subprocess.run(
            command,
            cwd=str(plan_path.parent),
            creationflags=0x08000000,
            timeout=max(120, timeout * 4),
            check=False,
        )
    except Exception as exc:
        log(log_path, f"HIBA: a Windows Installer nem indítható: {exc}")
        completed = None

    exit_code = completed.returncode if completed is not None else -1
    if exit_code not in (0, 3010):
        log(log_path, f"HIBA: az MSI telepítés exit kódja {exit_code}; a Windows Installer tranzakció visszagörgette a programfájlokat.")
        save_result(state_path, {
            "status": "install_failed", "version": str(plan.get("to_version") or ""),
            "installer_exit_code": exit_code, "installer_log": str(installer_log),
            "time": datetime.now().isoformat(timespec="seconds"),
        })
        start_tray(vbs, app_dir, log_path, launcher_exe)
        return 11

    log(log_path, f"MSI telepítés kész, exit={exit_code}; SleepMate automatikus újraindítása következik.")
    try:
        marker.unlink()
    except FileNotFoundError:
        pass
    started = time.time()
    launched: subprocess.Popen | None
    if restart_tray_requested:
        launched = start_tray(vbs, app_dir, log_path, launcher_exe)
    else:
        launched = launch_backend(app_dir, port, log_path, launcher_exe)
    version = str(plan.get("to_version") or "")
    healthy = wait_health(marker, version, started, timeout)
    result = {
        "status": "success" if healthy else "installed_not_healthy",
        "version": version,
        "installer_exit_code": exit_code,
        "reboot_required": exit_code == 3010,
        "installer_log": str(installer_log),
        "time": datetime.now().isoformat(timespec="seconds"),
        "launcher_pid": launched.pid if launched else None,
    }
    save_result(state_path, result)
    if not healthy:
        log(log_path, f"HIBA: az MSI települt, de SleepMate {version} egészségjelzése nem érkezett meg.")
        return 12
    log(log_path, f"SIKER: SleepMate {version} MSI frissítés és automatikus újraindítás kész.")
    cleanup_stage(plan_path, log_path)
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    plan_path = Path(sys.argv[1]).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("format") != "sleepmate-update-plan":
        return 3

    install_kind = str(plan.get("install_kind") or "portable-tree")
    app_dir = Path(plan["app_dir"]).resolve()
    package_dir = Path(str(plan.get("package_dir") or app_dir)).resolve()
    rollback_dir = Path(str(plan.get("rollback_dir") or app_dir)).resolve()
    marker = Path(plan["health_marker"]).resolve()
    log_path = Path(plan["worker_log"]).resolve()
    old_pid = int(plan.get("old_pid") or 0)
    from_version = str(plan.get("from_version") or "")
    to_version = str(plan.get("to_version") or "")
    timeout = int(plan.get("timeout_seconds") or 70)
    port = int(plan.get("port") or 8895)
    tray_pid = int(plan.get("tray_pid") or 0)
    restart_tray_requested = bool(plan.get("restart_tray", tray_pid > 0))
    launcher_exe = Path(str(plan.get("launcher_exe") or (app_dir / "SleepMate.exe"))).resolve()
    vbs = Path(str(plan.get("launch_vbs") or (app_dir / "SleepMate.vbs"))).resolve()
    state_dir = Path(str(plan.get("state_dir") or app_dir)).resolve()
    state_path = state_dir / "private" / "update_runtime" / "state.json"

    log(log_path, f"Frissítés indul: {from_version} -> {to_version}")

    if not wait_for_exit(old_pid, 65):
        log(log_path, "HIBA: a régi SleepMate backend folyamat nem állt le időben.")
        return 4

    if tray_pid > 0:
        graceful = request_graceful_tray_exit(tray_pid, state_dir, log_path)
        if not graceful and not stop_process_tree(tray_pid, log_path, "Régi SleepMate tálcaalkalmazás"):
            log(log_path, "HIBA: a régi tálcaalkalmazás futva maradt; programfájlcsere nem indul el.")
            try:
                launch_backend(app_dir, port, log_path, launcher_exe)
            except Exception as exc:
                log(log_path, f"HIBA: a régi backend visszaindítása sem sikerült: {exc}")
            return 8

    if install_kind == "msi":
        return install_verified_msi(
            plan_path=plan_path, plan=plan, app_dir=app_dir, launcher_exe=launcher_exe,
            vbs=vbs, marker=marker, port=port, log_path=log_path, state_path=state_path,
            timeout=timeout, restart_tray_requested=restart_tray_requested,
        )

    # Known tray has already had a chance to remove its notification icon. This
    # remaining image-wide kill is only a lock-safety net for orphaned processes.
    stop_sleepmate_image_processes(launcher_exe, log_path, "Régi SleepMate példányok")

    try:
        replace_program(package_dir, app_dir, launcher_exe, log_path, attempts=8)
        log(log_path, "Új programfájlok telepítve.")
    except Exception as exc:
        log(log_path, f"HIBA telepítés közben: {exc}; rollback indul.")
        ok = restore_previous(
            app_dir=app_dir, rollback_dir=rollback_dir, launcher_exe=launcher_exe, vbs=vbs,
            port=port, log_path=log_path, state_path=state_path, from_version=from_version,
            failed_version=to_version, marker=marker, timeout=timeout,
            restart_tray_requested=restart_tray_requested,
        )
        return 5 if ok else 7

    started = time.time()
    new_backend: subprocess.Popen | None = None
    try:
        new_backend = launch_backend(app_dir, port, log_path, launcher_exe)
    except Exception as exc:
        log(log_path, f"HIBA az új verzió indításakor: {exc}")

    if wait_health(marker, to_version, started, timeout):
        log(log_path, f"SIKER: SleepMate {to_version} egészségjelzés megérkezett.")
        if restart_tray_requested:
            restart_tray(0, vbs, app_dir, log_path, launcher_exe)
        save_result(state_path, {
            "status": "success",
            "version": to_version,
            "time": datetime.now().isoformat(timespec="seconds"),
            "backend_pid": new_backend.pid if new_backend else None,
        })
        cleanup_stage(plan_path, log_path)
        return 0

    log(log_path, f"HIBA: SleepMate {to_version} nem adott egészségjelzést; automatikus rollback {from_version} verzióra.")
    terminate_spawned(new_backend, log_path, f"Sikertelen SleepMate {to_version} backend")
    ok = restore_previous(
        app_dir=app_dir, rollback_dir=rollback_dir, launcher_exe=launcher_exe, vbs=vbs,
        port=port, log_path=log_path, state_path=state_path, from_version=from_version,
        failed_version=to_version, marker=marker, timeout=timeout,
        restart_tray_requested=restart_tray_requested,
    )
    cleanup_stage(plan_path, log_path)
    return 6 if ok else 7


if __name__ == "__main__":
    raise SystemExit(main())
