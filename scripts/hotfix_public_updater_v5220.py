from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_bytes().decode("utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_bytes(text.encode("utf-8"))


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, replacement: str, label: str, flags: int = 0) -> str:
    text, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one regex match, found {count}")
    return text


# ---------------------------------------------------------------------------
# 1) Updater backend: one official public source, no GitHub credential at all.
# ---------------------------------------------------------------------------
maintenance = read("cpap/maintenance.py")
maintenance = replace_once(
    maintenance,
    "from .version import APP_NAME, APP_VERSION, API_VERSION, BUILD_CHANNEL, UPDATE_MANIFEST_FORMAT, SUPPORT_BUNDLE_FORMAT",
    "from .version import APP_NAME, APP_VERSION, API_VERSION, BUILD_CHANNEL, UPDATE_MANIFEST_FORMAT, SUPPORT_BUNDLE_FORMAT\n\nOFFICIAL_GITHUB_REPO = \"BenWyxell/SleepMate-Public\"",
    "maintenance official repo constant",
)
maintenance = replace_once(
    maintenance,
    "        self.secrets = UpdateSecretStore(self.state_base)\n        self.log = log",
    "        self.secrets = UpdateSecretStore(self.state_base)\n        # v5.2.20+: official SleepMate releases are public. Any credential saved\n        # by an older build is obsolete and must never be reused or sent.\n        try:\n            self.secrets.path.unlink()\n        except FileNotFoundError:\n            pass\n        except OSError:\n            pass\n        self.log = log",
    "maintenance clear legacy secret",
)
maintenance = sub_once(
    maintenance,
    r"    def configure_token\(self, token: str = \"\", clear: bool = False\) -> dict\[str, Any\]:\r?\n        self\.secrets\.save_github_token\(token, clear\)\r?\n        return self\.secrets\.status\(\)",
    "    def configure_token(self, token: str = \"\", clear: bool = False) -> dict[str, Any]:\n        \"\"\"Compatibility no-op: the public updater never accepts credentials.\"\"\"\n        try:\n            self.secrets.path.unlink()\n        except FileNotFoundError:\n            pass\n        except OSError:\n            pass\n        return {\"configured\": False, \"required\": False, \"protection\": \"none\"}",
    "maintenance configure token no-op",
)
maintenance = sub_once(
    maintenance,
    r"        token = self\.secrets\.github_token\(\)\r?\n        if token:\r?\n            headers\[\"Authorization\"\] = f\"Bearer \{token\}\"\r?\n",
    "        # Official SleepMate releases are public; never attach a shared or user GitHub credential.\n",
    "maintenance remove authorization",
)
maintenance = replace_once(
    maintenance,
    "                raise RuntimeError(f\"GitHub elérés sikertelen (HTTP {exc.code}). Ellenőrizd a privát repo nevét és a GitHub tokent. {detail}\".strip()) from exc",
    "                raise RuntimeError(f\"A hivatalos SleepMate GitHub-kiadás jelenleg nem érhető el (HTTP {exc.code}). {detail}\".strip()) from exc",
    "maintenance public error copy",
)
maintenance = replace_once(
    maintenance,
    "        repo = str(cfg.get(\"update_github_repo\") or \"\").strip()",
    "        repo = OFFICIAL_GITHUB_REPO",
    "maintenance fixed status repo",
)
maintenance = replace_once(
    maintenance,
    "            \"configured\": bool(repo),",
    "            \"configured\": True,",
    "maintenance always configured",
)
maintenance = replace_once(
    maintenance,
    "            \"token\": self.secrets.status(),",
    "            \"authentication\": \"public-anonymous\",",
    "maintenance remove token status",
)
maintenance = sub_once(
    maintenance,
    r"            repo = self\.normalize_repo\(str\(config\.get\(\"update_github_repo\"\) or \"\"\)\)\r?\n            if not repo:\r?\n                result = self\._save_state\(last_check=_now\(\), update_available=False, latest_version=None, release=None, last_error=\"A GitHub frissítési repository még nincs beállítva\.\"\)\r?\n                return \{\"ok\": False, \"configured\": False, \*\*self\.status\(config\), \"message\": result\[\"last_error\"\]\}\r?\n            url = f\"https://api\.github\.com/repos/\{repo\}/releases/latest\"",
    "            repo = OFFICIAL_GITHUB_REPO\n            url = f\"https://api.github.com/repos/{repo}/releases/latest\"",
    "maintenance fixed check repo",
)
maintenance = replace_once(
    maintenance,
    "                msg = \"Új verzió érhető el.\" if update_status.get(\"update_available\") else \"A GitHub frissítési kapcsolat be van állítva.\"",
    "                msg = \"Új verzió érhető el.\" if update_status.get(\"update_available\") else \"A hivatalos SleepMate frissítési forrás elérhető.\"",
    "selfcheck updater ready copy",
)
maintenance = replace_once(
    maintenance,
    "                msg = \"A GitHub frissítési repository még nincs beállítva.\"",
    "                msg = \"A hivatalos SleepMate frissítési forrás nem érhető el.\"",
    "selfcheck updater unavailable copy",
)
write("cpap/maintenance.py", maintenance)


# ---------------------------------------------------------------------------
# 2) App config/API/background scheduler: fixed repo + 12-hour checks.
# ---------------------------------------------------------------------------
app = read("app.py")
app = replace_once(
    app,
    '        "update_github_repo": "",',
    '        "update_github_repo": "BenWyxell/SleepMate-Public",',
    "app fixed updater default",
)
app = replace_once(
    app,
    "                defaults.update(loaded)\n                # v3.5+: the web backend stays local-only; remote access is via",
    "                defaults.update(loaded)\n                # v5.2.20+: the update origin is product-owned, not a user setting.\n                defaults[\"update_github_repo\"] = \"BenWyxell/SleepMate-Public\"\n                # v3.5+: the web backend stays local-only; remote access is via",
    "app force official repo after legacy config",
)
app = sub_once(
    app,
    r"            if path == \"/api/update/config\":\r?\n.*?            if path == \"/api/update/check\":",
    "            if path == \"/api/update/config\":\n                data = self._read_json_body(max_bytes=100_000)\n                if not self.update_manager:\n                    raise RuntimeError(\"A frissítési modul nem érhető el.\")\n                allowed = {\"update_github_repo\": \"BenWyxell/SleepMate-Public\", \"update_channel\": \"stable\"}\n                if \"update_channel\" in data:\n                    channel = str(data.get(\"update_channel\") or \"stable\").strip().lower()\n                    if channel not in {\"stable\"}:\n                        raise ValueError(\"Jelenleg csak a stable frissítési csatorna támogatott.\")\n                if \"update_auto_check\" in data:\n                    allowed[\"update_auto_check\"] = bool(data.get(\"update_auto_check\"))\n                # Compatibility cleanup only: old clients may still send token fields,\n                # but v5.2.20 never stores or uses a GitHub credential.\n                self.update_manager.configure_token(clear=True)\n                save_config(allowed)\n                return self._json({\"ok\": True, **self._update_status_payload()})\n            if path == \"/api/update/check\":",
    "app update config endpoint",
    flags=re.S,
)
app = sub_once(
    app,
    r"    if bool\(load_config\(\)\.get\(\"update_auto_check\", True\)\) and str\(load_config\(\)\.get\(\"update_github_repo\"\) or \"\"\)\.strip\(\):\r?\n        def _startup_update_check\(\):\r?\n.*?        threading\.Thread\(target=_startup_update_check, name=\"sleepmate-update-check\", daemon=True\)\.start\(\)",
    "    def _background_update_check():\n        # Check immediately after startup and then twice per day. Installation is\n        # always explicit; this thread only reads the public release metadata.\n        while True:\n            try:\n                cfg = load_config()\n                if bool(cfg.get(\"update_auto_check\", True)) and Handler.update_manager:\n                    Handler.update_manager.check(cfg)\n            except Exception:\n                pass\n            time.sleep(12 * 60 * 60)\n    threading.Thread(target=_background_update_check, name=\"sleepmate-update-check\", daemon=True).start()",
    "app periodic update checker",
    flags=re.S,
)
write("app.py", app)


# ---------------------------------------------------------------------------
# 3) Maintenance UI: no repository/token controls exposed to the user.
# ---------------------------------------------------------------------------
index = read("web/index.html")
update_card = '''<article class="panel maintenance-card update-card">
              <div class="panel-head"><div><h3>Frissítések</h3><span>Hivatalos SleepMate kiadások • SHA-256 ellenőrzéssel.</span></div><span id="updateStateBadge" class="remote-status ok">Ellenőrzésre kész</span></div>
              <p>A SleepMate a hivatalos publikus kiadási csatornát használja. GitHub-fiók, repository beállítás és GitHub token nem szükséges.</p>
              <label class="setting-toggle"><input id="updateAutoCheck" type="checkbox" checked><span><b>Automatikus frissítésellenőrzés</b><small>Induláskor, majd 12 óránként ellenőrzi az új SleepMate kiadást. Telepítést nem indít el a jóváhagyásod nélkül.</small></span></label>
              <div class="update-version-grid"><div><span>Telepített</span><strong id="updateCurrentVersion">5.2.20</strong></div><div><span>Legfrissebb</span><strong id="updateLatestVersion">—</strong></div><div><span>Utolsó ellenőrzés</span><strong id="updateLastCheck">—</strong></div></div>
              <div class="settings-actions wrap"><button id="saveUpdateSettings" type="button">Beállítás mentése</button><button id="checkForUpdates" type="button">Frissítés keresése</button><button id="installUpdate" class="primary" type="button" disabled>Frissítés telepítése</button></div>
              <p id="updateStatusText" class="muted"></p>
              <div class="job-progress hidden" data-progress-card="update"><div class="progress-track"><i></i></div><strong>Frissítés előkészítése…</strong><span></span></div>
              <div class="rollback-line"><span>Előző programverzió</span><button id="rollbackUpdate" type="button" disabled>Rollback</button></div>
            </article>'''
index = sub_once(
    index,
    r'<article class="panel maintenance-card update-card">.*?</article>',
    update_card,
    "maintenance update card",
    flags=re.S,
)
write("web/index.html", index)

core = read("web/app-core.js")
core = re.sub(r"\s*if\(\$\('#updateGithubRepo'\)\).*?;\r?\n", "\n", core, count=1)
if "updateGithubRepo" in core and "function renderUpdateStatus" not in core:
    raise RuntimeError("unexpected remaining updateGithubRepo before renderer patch")
core = sub_once(
    core,
    r"function renderUpdateStatus\(r=\{\}\)\{.*?\r?\n\}\r?\nasync function loadMaintenanceStatus",
    "function renderUpdateStatus(r={}){\n  const badge=$('#updateStateBadge');if(badge){const failed=!!r.last_error;badge.className=`remote-status ${r.update_available?'warn':failed?'neutral':'ok'}`;badge.textContent=r.update_available?'Frissítés elérhető':failed?'Ellenőrzési hiba':'Naprakész'}\n  if($('#updateCurrentVersion'))$('#updateCurrentVersion').textContent=r.current_version||'—';\n  if($('#updateLatestVersion'))$('#updateLatestVersion').textContent=r.latest_version||'—';\n  if($('#updateLastCheck'))$('#updateLastCheck').textContent=r.last_check?humanDateTime(r.last_check):'—';\n  if($('#updateAutoCheck'))$('#updateAutoCheck').checked=r.auto_check!==false;\n  if($('#installUpdate'))$('#installUpdate').disabled=!r.update_available;\n  if($('#rollbackUpdate'))$('#rollbackUpdate').disabled=!r.rollback_available;\n  const status=$('#updateStatusText');if(status){status.textContent=r.last_error?`Hiba: ${r.last_error}`:r.update_available?`SleepMate ${r.latest_version} telepíthető. Telepítés előtt teljes backup és rollback-pont készül.`:'A SleepMate a hivatalos publikus kiadási csatornát használja.'}\n}\nasync function loadMaintenanceStatus",
    "app-core update renderer",
    flags=re.S,
)
core = sub_once(
    core,
    r"async function saveUpdateSettings\(\)\{.*?\r?\n\}\r?\nasync function checkForUpdates",
    "async function saveUpdateSettings(){\n  const btn=$('#saveUpdateSettings');if(!btn)return;btn.disabled=true;\n  try{const payload={update_channel:'stable',update_auto_check:$('#updateAutoCheck').checked};const r=await apiWrite('/api/update/config','POST',payload);state.settings.update_auto_check=r.auto_check!==false;renderUpdateStatus(r);addLog('INFO','Frissítési beállítás mentve.')}catch(e){showError(e)}finally{btn.disabled=false}\n}\nasync function checkForUpdates",
    "app-core save update settings",
    flags=re.S,
)
for forbidden in ("updateGithubRepo", "updateGithubToken", "updateGithubClearToken", "updateGithubTokenHint"):
    if forbidden in core:
        raise RuntimeError(f"app-core still exposes {forbidden}")
write("web/app-core.js", core)


# ---------------------------------------------------------------------------
# 4) First-run Cloudflare hostname provenance + cache generation bump.
# ---------------------------------------------------------------------------
first_run = read("web/first-run.js")
first_run = replace_once(first_run, "/first-run.css?v=3", "/first-run.css?v=4", "first-run css cache bust")
first_run = replace_once(
    first_run,
    '<div class="fr-field"><label>Publikus hostname</label><input id="frCfHost" class="fr-input" placeholder="sleepmate.pelda.hu"></div>',
    '<div class="fr-field"><label>Publikus hostname</label><input id="frCfHost" class="fr-input" placeholder="sleepmate.pelda.hu"><small id="frCfHostOrigin" class="fr-saved-origin" hidden>Korábban mentett SleepMate-beállítás.</small></div>',
    "cloudflare hostname provenance markup",
)
first_run = replace_once(
    first_run,
    "    $('#frDataDir').value=state.config.data_dir||'';$('#frAutoScan').checked=state.config.auto_scan_enabled!==false;$('#frSleepSync').checked=!!state.sleepsync.auto_sync_enabled;$('#frBackup').checked=!!state.config.auto_backup_enabled;$('#frCfHost').value=state.config.cloudflare_hostname||'';$('#frCfAccess').checked=!!state.config.cloudflare_access_confirmed;",
    "    $('#frDataDir').value=state.config.data_dir||'';$('#frAutoScan').checked=state.config.auto_scan_enabled!==false;$('#frSleepSync').checked=!!state.sleepsync.auto_sync_enabled;$('#frBackup').checked=!!state.config.auto_backup_enabled;const savedCfHost=String(state.config.cloudflare_hostname||'').trim();$('#frCfHost').value=savedCfHost;const cfOrigin=$('#frCfHostOrigin');if(cfOrigin)cfOrigin.hidden=!savedCfHost;$('#frCfAccess').checked=!!state.config.cloudflare_access_confirmed;",
    "cloudflare hostname hydrate provenance",
)
first_run = replace_once(
    first_run,
    "    $('#frTsInstall',root).onclick=()=>installRemote('tailscale');$('#frCfInstall',root).onclick=()=>installRemote('cloudflare');$('#frRemoteRefresh',root).onclick=()=>loadRemote(true);$('#frCfRefresh',root).onclick=()=>loadRemote(true);",
    "    $('#frTsInstall',root).onclick=()=>installRemote('tailscale');$('#frCfInstall',root).onclick=()=>installRemote('cloudflare');$('#frRemoteRefresh',root).onclick=()=>loadRemote(true);$('#frCfRefresh',root).onclick=()=>loadRemote(true);$('#frCfHost',root).oninput=()=>{const origin=$('#frCfHostOrigin',root);if(origin)origin.hidden=true};",
    "cloudflare provenance hide on edit",
)
write("web/first-run.js", first_run)

first_css = read("web/first-run.css")
if ".fr-saved-origin{" not in first_css:
    first_css += "\n.fr-saved-origin{display:block;margin-top:7px;color:#78d7ff;font-size:12px;line-height:1.35}\n"
write("web/first-run.css", first_css)

hydration = read("web/sleepsync-hydration-v529.js")
hydration = replace_once(hydration, "/first-run.js?v=3", "/first-run.js?v=4", "packaged first-run cache bust")
hydration = hydration.replace("távoli elérés, PWA, backup és AI alapbeállításain.", "távoli elérés, backup és AI alapbeállításain.")
write("web/sleepsync-hydration-v529.js", hydration)

app_js = read("web/app.js")
app_js = replace_once(app_js, "const HYDRATION='/sleepsync-hydration-v529.js?v=130';", "const HYDRATION='/sleepsync-hydration-v529.js?v=131';", "source hydration generation")
app_js = replace_once(app_js, "const FIRST_RUN='/first-run.js?v=1';", "const FIRST_RUN='/first-run.js?v=4';", "source first-run generation")
app_js = app_js.replace("data-sleepsync-hydration=\"130\"", "data-sleepsync-hydration=\"131\"")
app_js = app_js.replace("dataset.sleepsyncHydration='130'", "dataset.sleepsyncHydration='131'")
write("web/app.js", app_js)

polish = read("web/sleepsync-polish.js")
polish = replace_once(polish, "script.src='/sleepsync-hydration-v529.js';", "script.src='/sleepsync-hydration-v529.js?v=131';", "polish hydration generation")
write("web/sleepsync-polish.js", polish)

verify = read("scripts/verify_sleepsync_integration.py")
verify = verify.replace("/sleepsync-hydration-v529.js?v=130", "/sleepsync-hydration-v529.js?v=131")
verify = verify.replace("script.src='/sleepsync-hydration-v529.js'", "script.src='/sleepsync-hydration-v529.js?v=131'")
verify = verify.replace("# Release/PWA shell. The 5.2.19 patch", "# Release/PWA shell. The 5.2.20 patch")
verify = verify.replace('APP_VERSION = "5.2.19"', 'APP_VERSION = "5.2.20"')
verify = verify.replace("release version is not 5.2.19", "release version is not 5.2.20")
write("scripts/verify_sleepsync_integration.py", verify)


# ---------------------------------------------------------------------------
# 5) Version and regression contracts.
# ---------------------------------------------------------------------------
version = read("cpap/version.py")
version = replace_once(version, 'APP_VERSION = "5.2.19"', 'APP_VERSION = "5.2.20"', "version bump")
write("cpap/version.py", version)

sleep_test = read("tests/test_v521_sleep_analysis.py")
sleep_test = sleep_test.replace('assert APP_VERSION == "5.2.19"', 'assert APP_VERSION == "5.2.20"')
write("tests/test_v521_sleep_analysis.py", sleep_test)

wizard_test = read("tests/test_first_run_wizard_v5217_hotfix.py")
wizard_test = wizard_test.replace('/first-run.css?v=3', '/first-run.css?v=4').replace('/first-run.js?v=3', '/first-run.js?v=4')
wizard_test += '''\n\ndef test_cloudflare_prefill_is_explained_as_saved_state():\n    assert 'id="frCfHostOrigin"' in JS\n    assert 'Korábban mentett SleepMate-beállítás.' in JS\n    assert "cfOrigin.hidden=!savedCfHost" in JS\n    assert "origin.hidden=true" in JS\n'''
write("tests/test_first_run_wizard_v5217_hotfix.py", wizard_test)

windows_test = read("tests/test_windows_packaging_v500.py")
windows_test = windows_test.replace('/first-run.css?v=3', '/first-run.css?v=4').replace('/first-run.js?v=3', '/first-run.js?v=4')
write("tests/test_windows_packaging_v500.py", windows_test)

ui_test = read("tests/test_v420_ui.py")
ui_test = replace_once(
    ui_test,
    "for x in ['updateGithubRepo','saveUpdateSettings','checkForUpdates','installUpdate','rollbackUpdate','runSelfCheck','createSupportBundle']:\n    assert f'id=\"{x}\"' in html",
    "for x in ['saveUpdateSettings','checkForUpdates','installUpdate','rollbackUpdate','runSelfCheck','createSupportBundle']:\n    assert f'id=\"{x}\"' in html\nfor removed in ['updateGithubRepo','updateGithubToken','updateGithubClearToken']:\n    assert removed not in html\nassert 'Hivatalos SleepMate kiadások' in html",
    "v420 ui updater controls",
)
write("tests/test_v420_ui.py", ui_test)

maintenance_test = read("tests/test_maintenance_v420.py")
maintenance_test = maintenance_test.replace(
    "from cpap.maintenance import GitHubUpdateManager, SelfCheckService, SupportBundleService, version_newer",
    "from cpap.maintenance import GitHubUpdateManager, SelfCheckService, SupportBundleService, OFFICIAL_GITHUB_REPO, version_newer",
)
maintenance_test = sub_once(
    maintenance_test,
    r"    sample_value = 'unit-test-value-1234567890'\r?\n    mgr\.configure_token\(sample_value\)\r?\n    raw = \(base/'private'/'update_secrets\.bin'\)\.read_bytes\(\)\r?\n    assert sample_value\.encode\(\) not in raw\r?\n    st = mgr\.status\(\{'update_github_repo':'owner/private-repo','update_auto_check':True\}\)\r?\n    assert st\['token'\]\['configured'\] and sample_value not in json\.dumps\(st\)",
    "    sample_value = 'unit-test-value-1234567890'\n    token_status = mgr.configure_token(sample_value)\n    assert token_status['configured'] is False and token_status['required'] is False\n    assert not (base/'private'/'update_secrets.bin').exists()\n    st = mgr.status({'update_github_repo':'owner/private-repo','update_auto_check':True})\n    assert st['github_repo'] == OFFICIAL_GITHUB_REPO\n    assert st['configured'] is True and st['authentication'] == 'public-anonymous'\n    assert 'token' not in st and sample_value not in json.dumps(st)",
    "maintenance test public updater status",
)
maintenance_test = maintenance_test.replace(
    "result = mgr.prepare_install({'update_github_repo':'owner/private-repo'}, base/'private'/'measurement', 8895)",
    "result = mgr.prepare_install({'update_github_repo':'ignored/legacy-value'}, base/'private'/'measurement', 8895)",
)
maintenance_test = maintenance_test.replace(
    "GitHub updater staging + encrypted token + pre-update backup + rollback point + self-check + secret-free support bundle",
    "public GitHub updater staging + pre-update backup + rollback point + self-check + secret-free support bundle",
)
write("tests/test_maintenance_v420.py", maintenance_test)

public_test = '''from pathlib import Path\n\nfrom cpap.maintenance import OFFICIAL_GITHUB_REPO\nfrom cpap.version import APP_VERSION\n\nROOT = Path(__file__).resolve().parents[1]\n\n\ndef test_official_public_updater_has_no_user_credentials():\n    maintenance = (ROOT / "cpap" / "maintenance.py").read_text(encoding="utf-8")\n    app = (ROOT / "app.py").read_text(encoding="utf-8")\n    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")\n    js = (ROOT / "web" / "app-core.js").read_text(encoding="utf-8")\n\n    assert APP_VERSION == "5.2.20"\n    assert OFFICIAL_GITHUB_REPO == "BenWyxell/SleepMate-Public"\n    assert 'OFFICIAL_GITHUB_REPO = "BenWyxell/SleepMate-Public"' in maintenance\n    assert 'headers["Authorization"]' not in maintenance\n    assert 'Ellenőrizd a privát repo nevét és a GitHub tokent' not in maintenance\n    assert '"authentication": "public-anonymous"' in maintenance\n    assert 'repo = OFFICIAL_GITHUB_REPO' in maintenance\n\n    assert '"update_github_repo": "BenWyxell/SleepMate-Public"' in app\n    assert 'defaults["update_github_repo"] = "BenWyxell/SleepMate-Public"' in app\n    assert 'time.sleep(12 * 60 * 60)' in app\n    assert 'update_github_repo\") or \"\"' not in app.split('def _background_update_check',1)[1].split('try:',1)[0]\n\n    for removed in ('updateGithubRepo','updateGithubToken','updateGithubClearToken','updateGithubTokenHint'):\n        assert removed not in html\n        assert removed not in js\n    assert 'Hivatalos SleepMate kiadások' in html\n    assert 'GitHub token nem szükséges' in html\n    assert 'Frissítés keresése' in html\n    assert 'Frissítés telepítése' in html\n\n\ndef test_cloudflare_saved_hostname_provenance_and_cache_bust():\n    first = (ROOT / "web" / "first-run.js").read_text(encoding="utf-8")\n    hydration = (ROOT / "web" / "sleepsync-hydration-v529.js").read_text(encoding="utf-8")\n    source_loader = (ROOT / "web" / "app.js").read_text(encoding="utf-8")\n    assert 'id="frCfHostOrigin"' in first\n    assert 'Korábban mentett SleepMate-beállítás.' in first\n    assert "savedCfHost" in first and "origin.hidden=true" in first\n    assert '/first-run.css?v=4' in first\n    assert '/first-run.js?v=4' in hydration\n    assert "const FIRST_RUN='/first-run.js?v=4'" in source_loader\n    assert "/sleepsync-hydration-v529.js?v=131" in source_loader\n'''
write("tests/test_public_updater_v5220.py", public_test)


# ---------------------------------------------------------------------------
# 6) Release notes + publication gate.
# ---------------------------------------------------------------------------
notes = read("RELEASE_NOTES.md")
section = '''# SleepMate 5.2.20

A SleepMate 5.2.20 a frissítési folyamatot végleges, felhasználóbarát publikus csatornára állítja, és egyértelművé teszi a korábban mentett Cloudflare hostname eredetét.

## Hivatalos, tokenmentes frissítési csatorna

- A SleepMate frissítési forrása fixen a publikus **`BenWyxell/SleepMate-Public`** GitHub repository.
- A felhasználónak többé nem kell repository-nevet vagy GitHub tokent megadnia.
- A Beállításokból kikerült a GitHub repository mező, a tokenmező és a mentett token törlése.
- A kliens nem éget be közös GitHub tokent, és frissítésellenőrzéskor nem küld `Authorization` fejlécet.
- Korábbi verzióból esetleg megmaradt updater token automatikusan törlésre kerül és nem használható fel.
- Az automatikus ellenőrzés induláskor, majd **12 óránként** lefut; telepítés továbbra is csak kifejezett felhasználói jóváhagyással indul.
- A kézi **Frissítés keresése** és **Frissítés telepítése** funkció megmaradt.
- A release manifest, SHA-256 ellenőrzés, teljes frissítés előtti backup és automatikus rollback változatlanul kötelező.

## Cloudflare első beállítás

- Ha a Cloudflare hostname egy korábban mentett SleepMate konfigurációból kerül visszatöltésre, a wizard ezt külön **„Korábban mentett SleepMate-beállítás.”** jelöléssel mutatja.
- A jelölés eltűnik, amint a felhasználó szerkeszteni kezdi a hostname mezőt.
- Így egy régi domain többé nem tűnik automatikusan generált vagy a SleepMate által kitalált címnek.
- A first-run loader új cache-generációt kapott, hogy a régi wizard JavaScript/CSS ne ragadhasson bent.

## Validáció

- publikus forrás hygiene gate
- Python + JavaScript syntax/contract tesztek
- publikus updater credential-mentességi regresszióteszt
- Cloudflare hostname provenance regresszióteszt
- teljes publikus pytest-készlet
- PyInstaller Windows program-tree build
- magyar WiX MSI build + payload ellenőrzés
- valódi MSI install / backend API / uninstall smoke-test
- ZIP/manifeszt/MSI SHA-256 és VERIFIED release-set
- GitHub publikálás kizárólag minden kapu sikere után

Kiadási csatorna: **stable**.
Release build: **5.2.20**.
API: **19**.
Release validation: **teljes publikus tesztkészlet + Windows program-tree + magyar MSI + valódi install/runtime/API/uninstall smoke-test + release hash/manifeszt/integritás gate + verified GitHub publication**.

---

'''
if not notes.startswith("# SleepMate 5.2.20"):
    notes = section + notes
write("RELEASE_NOTES.md", notes)

workflow = read(".github/workflows/windows-release.yml")
workflow = workflow.replace("$VERSION\" == '5.2.19'", "$VERSION\" == '5.2.20'")
workflow = workflow.replace("One-time 5.2.19 publication", "One-time 5.2.20 publication")
write(".github/workflows/windows-release.yml", workflow)

print("SleepMate v5.2.20 public updater + Cloudflare provenance patch applied.")
