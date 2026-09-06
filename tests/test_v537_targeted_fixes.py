from __future__ import annotations

import hashlib
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
    shell = read("web/index.html")
    frontend = read("web/sleepmate-v530.js")

    assert 'name="sleepmate-o2ring-enabled" content="unknown"' in shell
    assert "UNKNOWN:'unknown',ENABLED:'enabled',DISABLED:'disabled'" in frontend
    assert "function activeO2(){return o2State===O2_STATE.ENABLED}" in frontend
    assert "o2State===O2_STATE.DISABLED" in frontend
    assert "o2State!==O2_STATE.DISABLED" in frontend
    assert "e.indeterminate=id==='smO2Enabled'&&loading" in frontend
    assert "e.disabled=loading" in frontend
    assert "const o2Request=refreshO2State().catch(()=>{})" in frontend


def test_late_o2ring_config_reconciles_all_feature_surfaces() -> None:
    frontend = read("web/sleepmate-v530.js")
    apply_start = frontend.index("async function applyO2Status(next)")
    apply_end = frontend.index("async function refreshO2State()", apply_start)
    apply_body = frontend[apply_start:apply_end]

    for required in (
        "setO2FeatureState()",
        "hydrateO2Master()",
        "ensureO2Modules()",
        "disableO2Ui()",
        "renderBottomNav()",
        "renderPwaEditor()",
        "sleepmate-o2-config-ready",
    ):
        assert required in apply_body


def test_service_worker_never_mixes_generations_in_an_active_page() -> None:
    for relative in ("web/service-worker.js", "web/service-worker-v508-base.js"):
        worker = read(relative)
        assert "sleepmate-shell-v5.3.22" in worker
        assert "await self.skipWaiting()" in worker
        assert "await self.clients.claim()" in worker
        assert "navigationFallback" in worker
        assert "currentCodeAsset" in worker


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
        "signature_mode": "verified-unsigned",
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

    bad_manifest["requires_installer"] = True
    bad_manifest["asset"] = ""
    manifest.write_text(json.dumps(bad_manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="kötelező MSI asset"):
        manager.prepare_install({}, data, 8895)

    bad_manifest["asset"] = msi.name
    bad_manifest["sha256"] = "not-a-sha256"
    manifest.write_text(json.dumps(bad_manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="érvényes SHA-256"):
        manager.prepare_install({}, data, 8895)

    bad_manifest["sha256"] = "0" * 64
    manifest.write_text(json.dumps(bad_manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="SHA-256 ellenőrzése sikertelen"):
        manager.prepare_install({}, data, 8895)

    bad_manifest["sha256"] = digest
    bad_manifest["min_version"] = "latest"
    manifest.write_text(json.dumps(bad_manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="min_version"):
        manager.prepare_install({}, data, 8895)


def test_updater_msi_lifecycle_launches_only_system_msiexec(tmp_path: Path, monkeypatch) -> None:
    import cpap.maintenance as maintenance
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
        "format": "sleepmate-update-plan",
        "install_kind": "msi",
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
    manager = maintenance.GitHubUpdateManager(app_dir)
    monkeypatch.setattr(maintenance.os, "name", "nt")
    calls: list[list[str]] = []
    monkeypatch.setattr(maintenance.subprocess, "Popen", lambda command, **kwargs: (calls.append(command) or SimpleNamespace(pid=1234)))

    result = manager.launch_worker(str(plan_path))
    assert result["installer_pid"] == 1234
    assert len(calls) == 1
    command = calls[0]
    assert command[:3] == [str(msiexec.resolve()), "/i", str(installer.resolve())]
    assert "/passive" in command and "/norestart" in command and "REBOOT=ReallySuppress" in command
    assert "SLEEPMATE_AUTOLAUNCH=1" in command
    assert "/L*v" in command
    assert (app_dir / "private" / "quit_tray.request").is_file()


def test_official_build_uses_no_coordinator_and_an_msi_manifest() -> None:
    release_build = read("build/windows/build_release.ps1")
    workflow = read(".github/workflows/windows-release.yml")
    maintenance = read("cpap/maintenance.py")

    assert not (ROOT / "build/windows/SleepMateUpdater.spec").exists()
    assert "StableUpdater" not in release_build
    assert "dist\\SleepMate\\Updater" not in release_build
    assert "build_msi_update_manifest.py" in workflow
    assert "'package_type': manifest.get('package_type') == 'windows-msi-x64'" in workflow
    assert "'requires_installer': manifest.get('requires_installer') is True" in workflow
    assert 'system_root / "System32" / "msiexec.exe"' in maintenance
    assert "update_worker.py" not in maintenance


def test_update_button_is_single_action_and_installer_handover_is_graceful() -> None:
    frontend = read("web/app-core.js")
    start = frontend.index("async function installAvailableUpdate()")
    end = frontend.index("function renderSelfCheck", start)
    action = frontend[start:end]
    maintenance = read("cpap/maintenance.py")

    assert "confirmAction(" not in action
    assert "apiWrite('/api/update/install', 'POST', {})" in action
    assert "waitForSleepMateRestart(expected)" in action
    assert maintenance.index('quit_request.write_text') < maintenance.index('subprocess.Popen(command')
    assert '"SLEEPMATE_AUTOLAUNCH=1"' in maintenance
