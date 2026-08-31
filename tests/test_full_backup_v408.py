from pathlib import Path
from tempfile import TemporaryDirectory
import sys, zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpap.services import create_full_backup

with TemporaryDirectory() as td:
    root=Path(td); base=root/'base'; private=base/'private'; data=private/'measurement'
    private.mkdir(parents=True); data.mkdir(parents=True)
    (private/'patient.db').write_bytes(b'PATIENT')
    (private/'ai_history.bin').write_bytes(b'AI')
    (private/'system_log.jsonl').write_text('log',encoding='utf-8')
    bp=private/'browser_profile'; bp.mkdir(); (bp/'lockfile').write_bytes(b'LOCK'); (bp/'Preferences').write_text('{}')
    ab=private/'automatic_backups'; ab.mkdir(); (ab/'old.zip').write_bytes(b'OLD')
    rp=private/'reports'; rp.mkdir(); (rp/'report.pdf').write_bytes(b'PDF')
    (data/'DATALOG').mkdir(); (data/'DATALOG'/'night.edf').write_bytes(b'EDF')
    out=root/'backup.zip'
    create_full_backup(base,data,{},out)
    with zipfile.ZipFile(out) as zf:
        names=set(zf.namelist())
    assert 'private/patient.db' in names
    assert 'private/ai_history.bin' in names
    assert 'private/system_log.jsonl' in names
    assert 'measurement/DATALOG/night.edf' in names
    assert not any(n.startswith('private/browser_profile/') for n in names)
    assert not any(n.startswith('private/automatic_backups/') for n in names)
    assert not any(n.startswith('private/reports/') for n in names)
    assert not any(n.startswith('private/measurement/') for n in names)

js=(Path(__file__).resolve().parents[1]/'web'/'app.js').read_text(encoding='utf-8')
assert 'showSaveFilePicker' in js and 'createWritable' in js
assert 'SleepMate_teljes_backup_' in js
print('PASS: v4.0.9 full backup excludes runtime browser locks and uses Save As picker')
