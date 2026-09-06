from pathlib import Path
root=Path(__file__).resolve().parents[1]
html=(root/'web'/'index.html').read_text(encoding='utf-8')
js=(root/'web'/'app-core.js').read_text(encoding='utf-8')
app=(root/'app.py').read_text(encoding='utf-8')
maintenance=(root/'cpap'/'maintenance.py').read_text(encoding='utf-8')
tray=(root/'sleepmate_tray.pyw').read_text(encoding='utf-8')
assert 'Rendszer és frissítés' in html
for x in ['saveUpdateSettings','checkForUpdates','installUpdate','rollbackUpdate','runSelfCheck','createSupportBundle']:
    assert f'id="{x}"' in html
for removed in ['updateGithubRepo','updateGithubToken','updateGithubClearToken']:
    assert removed not in html
assert 'Hivatalos SleepMate kiadások' in html
for fn in ['loadMaintenanceStatus','saveUpdateSettings','checkForUpdates','installAvailableUpdate','runSelfCheck','createSupportBundle']:
    assert f'function {fn}' in js or f'async function {fn}' in js
for route in ['/api/update/status','/api/update/config','/api/update/check','/api/update/install','/api/self-check','/api/support/create']:
    assert route in app
assert not (root/'update_worker.py').exists()
assert 'system_root / "System32" / "msiexec.exe"' in maintenance
assert '/api/update/rollback' not in app and 'rollbackSleepMate' not in js
assert 'tray_heartbeat.json' in tray and 'tray.pid' in tray
print('PASS: maintenance UI/API contract uses Windows Installer without a custom updater worker')
