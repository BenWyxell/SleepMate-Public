from pathlib import Path

root = Path(__file__).resolve().parents[1]
app = (root / 'app.py').read_text(encoding='utf-8')
js = (root / 'web' / 'app.js').read_text(encoding='utf-8')
html = (root / 'web' / 'index.html').read_text(encoding='utf-8')

# SleepMate must never open Windows Explorer/folders from application logic.
assert 'os.startfile(' not in app
assert '/api/backup/open-auto-folder' not in app
assert 'openAutoBackupFolder' not in js
assert 'openAutoBackupFolder' not in html
assert 'Mentési mappa megnyitása' not in html
print('PASS: no automatic or programmatic folder opening remains')
