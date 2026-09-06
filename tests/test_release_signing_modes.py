from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import cpap.maintenance as maintenance


ROOT = Path(__file__).resolve().parents[1]


def _manifest(mode: str) -> dict[str, object]:
    return {
        "package_type": "windows-msi-x64",
        "requires_installer": True,
        "signature_mode": mode,
    }


def test_transitional_policy_accepts_verified_unsigned_and_checks_signed(monkeypatch) -> None:
    monkeypatch.setattr(maintenance, "UPDATE_SIGNATURE_POLICY", "verified-unsigned")
    assert maintenance.GitHubUpdateManager._requires_authenticode(_manifest("verified-unsigned")) is False
    assert maintenance.GitHubUpdateManager._requires_authenticode(_manifest("authenticode")) is True


def test_signed_policy_cannot_be_downgraded_by_manifest(monkeypatch) -> None:
    monkeypatch.setattr(maintenance, "UPDATE_SIGNATURE_POLICY", "authenticode-required")
    with pytest.raises(RuntimeError, match="kizárólag Authenticode"):
        maintenance.GitHubUpdateManager._requires_authenticode(_manifest("verified-unsigned"))
    assert maintenance.GitHubUpdateManager._requires_authenticode(_manifest("authenticode")) is True


def test_unknown_or_missing_manifest_signature_mode_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(maintenance, "UPDATE_SIGNATURE_POLICY", "verified-unsigned")
    for mode in ("", "manifest-selected", "unsigned"):
        with pytest.raises(RuntimeError, match="aláírási módja"):
            maintenance.GitHubUpdateManager._requires_authenticode(_manifest(mode))


def test_official_release_asset_url_is_enforced(tmp_path: Path, monkeypatch) -> None:
    manager = maintenance.GitHubUpdateManager(tmp_path)
    for url in (
        "http://api.github.com/repos/BenWyxell/SleepMate-Public/releases/assets/1",
        "https://example.com/repos/BenWyxell/SleepMate-Public/releases/assets/1",
        "https://api.github.com/repos/attacker/SleepMate-Public/releases/assets/1",
        "https://api.github.com/repos/BenWyxell/SleepMate-Public/releases/assets/not-an-id",
    ):
        with pytest.raises(RuntimeError):
            manager._download_asset(url, tmp_path / "rejected.msi")

    monkeypatch.setattr(manager, "_request", lambda url, **kwargs: b"official-release-asset")
    accepted = tmp_path / "accepted.msi"
    manager._download_asset(
        "https://api.github.com/repos/BenWyxell/SleepMate-Public/releases/assets/12345",
        accepted,
    )
    assert accepted.read_bytes() == b"official-release-asset"


def test_manifest_builder_requires_and_records_signature_mode(tmp_path: Path) -> None:
    msi = tmp_path / f"SleepMate_Setup_v{maintenance.APP_VERSION}.msi"
    msi.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"release-contract-test")
    output = tmp_path / "sleepmate-update.json"
    script = ROOT / "tools/build_msi_update_manifest.py"

    missing = subprocess.run(
        [sys.executable, str(script), "--msi", str(msi), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0

    invalid_minimum = subprocess.run(
        [
            sys.executable,
            str(script),
            "--msi",
            str(msi),
            "--output",
            str(output),
            "--signature-mode",
            "verified-unsigned",
            "--min-version",
            "latest",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert invalid_minimum.returncode != 0

    for mode in ("verified-unsigned", "authenticode"):
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--msi",
                str(msi),
                "--output",
                str(output),
                "--signature-mode",
                mode,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        manifest = json.loads(output.read_text(encoding="utf-8"))
        assert manifest["signature_mode"] == mode
        assert manifest["asset"] == msi.name
        assert manifest["sha256"] == hashlib.sha256(msi.read_bytes()).hexdigest()


def test_canonical_workflow_has_optional_but_non_fallback_signing_gate() -> None:
    workflow = (ROOT / ".github/workflows/windows-release.yml").read_text(encoding="utf-8")
    assert "signing_configured: ${{ steps.signing-mode.outputs.configured }}" in workflow
    assert "SignPath is not configured; verified unsigned publication mode selected." in workflow
    assert "SignPath configuration is partial." in workflow
    assert "Signed production publication requires UPDATE_SIGNATURE_POLICY=authenticode-required" in workflow
    assert "Unsigned publication requires UPDATE_SIGNATURE_POLICY=verified-unsigned" in workflow
    assert "needs.verify-release-set.outputs.signing_configured == 'true'" in workflow
    assert "needs.sign-release-set.result == 'success'" in workflow
    assert "needs.sign-release-set.result == 'skipped'" in workflow
    assert "SleepMate-Windows-x64-VERIFIED-RELEASE' }}" in workflow
    assert "SleepMate-Windows-x64-SIGNED-RELEASE' ||" in workflow
    assert "test \"$(jq -r '.signature_mode' sleepmate-update.json)\" = \"$EXPECTED_MODE\"" in workflow
    publish = workflow.split("publish-github-release:", 1)[1]
    assert "contents: write" in publish
    assert "gh release create" in publish
    assert "gh release upload" in publish
    assert "--draft=false" in publish


def test_no_custom_updater_executable_returns() -> None:
    maintenance_source = (ROOT / "cpap/maintenance.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/windows-release.yml").read_text(encoding="utf-8")
    assert "update_worker.py" not in maintenance_source
    assert "SleepMateUpdater.exe must not be present" in workflow
    assert 'system_root / "System32" / "msiexec.exe"' in maintenance_source
