from __future__ import annotations

import hashlib
import inspect
import json
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class _ElementCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        self.tags.append(tag)


def test_sleepsync_sidebar_render_has_exactly_one_real_icon() -> None:
    engine = read("web/app-engine119.js")
    css = read("web/sleepsync-base.css")
    marker = "button.innerHTML='"
    fragment = engine.split(marker, 1)[1].split("';", 1)[0]
    parser = _ElementCounter()
    parser.feed(fragment)

    assert parser.tags.count("svg") == 1
    assert parser.tags.count("span") == 1
    assert ".sleepsync-nav-item:before" not in css
    assert ".sleepsync-nav-item::before" not in css
    assert ".sleepsync-nav-item>svg{width:19px;height:19px;flex:none}" in css


def test_o2ring_bootstrap_keeps_unknown_distinct_from_disabled() -> None:
    shell = read("cpap/v530_features.py")
    frontend = read("web/sleepmate-v530.js")

    assert 'name="sleepmate-o2ring-enabled" content="unknown"' in shell
    assert "UNKNOWN:'unknown',ENABLED:'enabled',DISABLED:'disabled'" in frontend
    assert "function activeO2(){return o2State===O2_STATE.ENABLED}" in frontend
    assert "o2State===O2_STATE.DISABLED" in frontend
    assert "o2State!==O2_STATE.DISABLED" in frontend
    assert "e.indeterminate=id==='smO2Enabled'&&loading" in frontend
    assert "e.disabled=loading" in frontend
    assert "if(!resolvedO2())refreshO2State()" in frontend


def test_late_o2ring_config_reconciles_all_feature_surfaces() -> None:
    frontend = read("web/sleepmate-v530.js")
    apply_start = frontend.index("async function applyO2Status(next)")
    apply_end = frontend.index("async function refreshO2State()", apply_start)
    apply_body = frontend[apply_start:apply_end]

    for required in (
        "setO2FeatureState()",
        "hydrateO2Master()",
        "ensureO2Modules()",
        "SleepMateO2Ring?.refresh?.()",
        "disableO2Ui()",
        "renderBottomNav()",
        "renderPwaEditor()",
        "sleepmate-o2-config-ready",
    ):
        assert required in apply_body


def test_service_worker_never_mixes_generations_in_an_active_page() -> None:
    for relative in ("web/service-worker.js", "web/service-worker-v508-base.js"):
        worker = read(relative)
        assert "sleepmate-shell-v5.3.14-o2-hydration-1" in worker
        assert "await self.skipWaiting()" in worker
        assert "clients.claim()" not in worker
        assert "navigationFallback" in worker
        assert "codeNetworkFirst" in worker


def _fake_msi(path: Path) -> str:
    path.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"sleepmate-msi-test")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_updater_accepts_only_exact_hashed_msi_release_asset(tmp_path: Path, monkeypatch) -> None:
    import cpap.maintenance as maintenance

    current = maintenance.APP_VERSION
    parts = [int(part) for part in current.split(".")]
    target = f"{parts[0]}.{parts[1]}.{parts[2] + 1}"
    base = tmp_path / "SleepMate"
    data = base / "private" / "measurement"
    data.mkdir(parents=True)
    release = tmp_path / "release"
    release.mkdir()
    msi = release / f"SleepMate_Setup_v{target}.msi"
    digest = _fake_msi(msi)
    manifest = release / "sleepmate-update.json"
    manifest.write_text(json.dumps({
        "format": maintenance.UPDATE_MANIFEST_FORMAT,
        "version": target,
        "min_version": current,
        "asset": msi.name,
        "sha256": digest,
        "package_type": "windows-msi-x64",
        "requires_installer": True,
    }), encoding="utf-8")
    release_state = {
        "tag": target,
        "prerelease": False,
        "assets": [
            {"name": "sleepmate-update.json", "url": "mock://manifest"},
            {"name": msi.name, "url": "mock://msi"},
        ],
        "manifest_asset": {"name": "sleepmate-update.json", "url": "mock://manifest"},
    }
    manager = maintenance.GitHubUpdateManager(base)
    with pytest.raises(RuntimeError, match="HTTPS"):
        manager._download_asset("http://example.invalid/update.msi", tmp_path / "unsafe.msi")
    monkeypatch.setattr(manager, "check", lambda config, force=False: {
        "update_available": True, "release": release_state,
    })
    monkeypatch.setattr(manager, "_download_asset", lambda url, destination: destination.write_bytes(
        (manifest if url == "mock://manifest" else msi).read_bytes()
    ))
    monkeypatch.setattr(maintenance, "create_full_backup", lambda state, root, config, out: out.write_bytes(b"backup"))

    result = manager.prepare_install({}, data, 8895)
    plan = json.loads(Path(result["plan"]).read_text(encoding="utf-8"))
    assert result["install_method"] == "windows-installer"
    assert plan["install_kind"] == "msi"
    assert Path(plan["installer_path"]).name == msi.name
    assert plan["installer_sha256"] == digest
    assert Path(result["backup"]).is_file()
    assert "package_dir" not in plan and "rollback_dir" not in plan

    bad_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    bad_manifest["asset"] = "unexpected.msi"
    manifest.write_text(json.dumps(bad_manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="hiányzik"):
        manager.prepare_install({}, data, 8895)

    bad_manifest["asset"] = msi.name
    bad_manifest["requires_installer"] = False
    manifest.write_text(json.dumps(bad_manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Windows Installer"):
        manager.prepare_install({}, data, 8895)


def test_updater_msi_lifecycle_is_unattended_and_checks_exit_code(tmp_path: Path, monkeypatch) -> None:
    import update_worker

    stage = tmp_path / "stage-test"
    stage.mkdir()
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    target = "9.9.9"
    installer = stage / f"SleepMate_Setup_v{target}.msi"
    digest = _fake_msi(installer)
    plan_path = stage / "update-plan.json"
    installer_log = tmp_path / "state" / "msiexec.log"
    plan = {
        "to_version": target,
        "installer_path": str(installer),
        "installer_sha256": digest,
        "installer_log": str(installer_log),
    }
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    system_root = tmp_path / "Windows"
    msiexec = system_root / "System32" / "msiexec.exe"
    msiexec.parent.mkdir(parents=True)
    msiexec.write_bytes(b"test")
    monkeypatch.setenv("SystemRoot", str(system_root))
    monkeypatch.setattr(update_worker, "IS_WINDOWS", True)
    calls: list[list[str]] = []
    monkeypatch.setattr(update_worker.subprocess, "run", lambda command, **kwargs: (calls.append(command) or SimpleNamespace(returncode=0)))
    monkeypatch.setattr(update_worker, "start_tray", lambda *args, **kwargs: SimpleNamespace(pid=1234))
    monkeypatch.setattr(update_worker, "wait_health", lambda *args, **kwargs: True)
    monkeypatch.setattr(update_worker, "cleanup_stage", lambda *args, **kwargs: None)

    rc = update_worker.install_verified_msi(
        plan_path=plan_path, plan=plan, app_dir=app_dir,
        launcher_exe=app_dir / "SleepMate.exe", vbs=app_dir / "SleepMate.vbs",
        marker=tmp_path / "state" / "update_boot_ok.json", port=8895,
        log_path=tmp_path / "state" / "worker.log", state_path=tmp_path / "state" / "state.json",
        timeout=5, restart_tray_requested=True,
    )
    assert rc == 0
    assert len(calls) == 1
    command = calls[0]
    assert command[:3] == [str(msiexec.resolve()), "/i", str(installer.resolve())]
    assert "/qn" in command and "/norestart" in command and "REBOOT=ReallySuppress" in command
    assert "/L*v" in command
    result = json.loads((tmp_path / "state" / "state.json").read_text(encoding="utf-8"))["last_result"]
    assert result["installer_exit_code"] == 0 and result["status"] == "success"

    calls.clear()
    installer.write_bytes(installer.read_bytes() + b"tampered")
    assert update_worker.install_verified_msi(
        plan_path=plan_path, plan=plan, app_dir=app_dir,
        launcher_exe=app_dir / "SleepMate.exe", vbs=app_dir / "SleepMate.vbs",
        marker=tmp_path / "state" / "update_boot_ok.json", port=8895,
        log_path=tmp_path / "state" / "worker.log", state_path=tmp_path / "state" / "state.json",
        timeout=5, restart_tray_requested=True,
    ) == 9
    assert calls == []


def test_official_build_uses_onedir_coordinator_and_msi_manifest() -> None:
    spec = read("build/windows/SleepMateUpdater.spec")
    release_build = read("build/windows/build_release.ps1")
    workflow = read(".github/workflows/windows-release.yml")
    worker = read("update_worker.py")
    msi_path = inspect.getsource(__import__("update_worker").install_verified_msi)

    assert "exclude_binaries=True" in spec and "coll = COLLECT(" in spec
    assert "updater-dist\\SleepMateUpdater\\SleepMateUpdater.exe" in release_build
    assert "dist\\SleepMate\\Updater" in release_build
    assert "build_msi_update_manifest.py" in workflow
    assert "'package_type': manifest.get('package_type') == 'windows-msi-x64'" in workflow
    assert "'requires_installer': manifest.get('requires_installer') is True" in workflow
    assert '"msiexec.exe"' in worker
    assert "replace_program(" not in msi_path
    assert "clear_program(" not in msi_path
    assert "stop_sleepmate_image_processes(" not in msi_path


def test_update_button_is_single_action_and_worker_orders_graceful_msi_lifecycle() -> None:
    frontend = read("web/app-core.js")
    start = frontend.index("async function installAvailableUpdate()")
    end = frontend.index("async function rollbackSleepMate()", start)
    action = frontend[start:end]
    worker_main = inspect.getsource(__import__("update_worker").main)

    assert "confirmAction(" not in action
    assert "apiWrite('/api/update/install','POST',{})" in action
    assert "waitForSleepMateRestart(expected)" in action
    assert worker_main.index("wait_for_exit(old_pid") < worker_main.index("request_graceful_tray_exit(")
    assert worker_main.index("request_graceful_tray_exit(") < worker_main.index("install_verified_msi(")
