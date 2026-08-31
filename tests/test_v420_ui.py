from pathlib import Path
root=Path(__file__).resolve().parents[1]
html=(root/'web'/'index.html').read_text(encoding='utf-8')
js=(root/'web'/'app.js').read_text(encoding='utf-8')
app=(root/'app.py').read_text(encoding='utf-8')
worker=(root/'update_worker.py').read_text(encoding='utf-8')
tray=(root/'sleepmate_tray.pyw').read_text(encoding='utf-8')
assert 'Rendszer és frissítés' in html
for x in ['updateGithubRepo','saveUpdateSettings','checkForUpdates','installUpdate','rollbackUpdate','runSelfCheck','createSupportBundle']:
    assert f'id="{x}"' in html
for fn in ['loadMaintenanceStatus','saveUpdateSettings','checkForUpdates','installAvailableUpdate','rollbackSleepMate','runSelfCheck','createSupportBundle']:
    assert f'function {fn}' in js or f'async function {fn}' in js
for route in ['/api/update/status','/api/update/config','/api/update/check','/api/update/install','/api/update/rollback','/api/self-check','/api/support/create']:
    assert route in app
assert 'wait_health' in worker and 'automatikus rollback' in worker.lower()
assert 'launch_backend' in worker and 'restart_tray' in worker
assert 'tray_heartbeat.json' in tray and 'tray.pid' in tray
print('PASS: v4.2.0 maintenance UI/API contract')
