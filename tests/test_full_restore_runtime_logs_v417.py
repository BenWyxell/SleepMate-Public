from pathlib import Path
import json
import tempfile
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpap.services import restore_full_backup

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    base = td / 'app'
    private = base / 'private'
    measurement = private / 'measurement'
    private.mkdir(parents=True)
    measurement.mkdir(parents=True)

    # These represent the currently running instance. Restore must preserve them.
    (private / 'service_startup.log').write_text('LIVE SERVICE LOG', encoding='utf-8')
    (private / 'launcher.log').write_text('LIVE LAUNCHER LOG', encoding='utf-8')
    (private / 'system_log.jsonl').write_text('LIVE SYSTEM LOG', encoding='utf-8')
    (private / 'ordinary.txt').write_text('OLD', encoding='utf-8')

    backup = td / 'backup.zip'
    manifest = {
        'format': 'cpap-elemzo-full-backup',
        'version': 2,
        'app_version': '4.1.6',
        'config': {},
    }
    with zipfile.ZipFile(backup, 'w') as zf:
        zf.writestr('manifest.json', json.dumps(manifest))
        zf.writestr('private/service_startup.log', 'BACKUP SERVICE LOG')
        zf.writestr('private/launcher.log', 'BACKUP LAUNCHER LOG')
        zf.writestr('private/system_log.jsonl', 'BACKUP SYSTEM LOG')
        zf.writestr('private/ordinary.txt', 'RESTORED')
        zf.writestr('measurement/DATALOG/test.edf', b'EDF')

    result = restore_full_backup(base, backup, measurement)
    assert (private / 'service_startup.log').read_text(encoding='utf-8') == 'LIVE SERVICE LOG'
    assert (private / 'launcher.log').read_text(encoding='utf-8') == 'LIVE LAUNCHER LOG'
    assert (private / 'system_log.jsonl').read_text(encoding='utf-8') == 'LIVE SYSTEM LOG'
    assert (private / 'ordinary.txt').read_text(encoding='utf-8') == 'RESTORED'
    assert (measurement / 'DATALOG' / 'test.edf').read_bytes() == b'EDF'
    assert set(result['runtime_files_preserved']) == {'service_startup.log','launcher.log','system_log.jsonl'}
print('PASS: v4.2.0 full restore preserves live runtime logs and restores real state')
