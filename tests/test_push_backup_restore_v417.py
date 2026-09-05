from pathlib import Path
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpap.push_service import PushService
from cpap.services import create_full_backup, restore_full_backup

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    base = root / 'app'
    measurement = base / 'private' / 'measurement'
    (measurement / 'DATALOG').mkdir(parents=True)
    (measurement / 'DATALOG' / 'keep.edf').write_bytes(b'EDF')

    ps = PushService(base)
    ps.subscribe({
        'endpoint': 'https://example.invalid/push/device-1',
        'keys': {'p256dh': 'abc', 'auth': 'def'},
    }, origin='https://sleepmate.example.hu')

    # No PushService method may leave a SQLite handle behind. A fresh exclusive
    # connection must be obtainable immediately after status/subscribe calls.
    ps.status()
    con = sqlite3.connect(str(ps.db_path), timeout=1)
    try:
        con.execute('BEGIN EXCLUSIVE')
        con.rollback()
    finally:
        con.close()

    backup = root / 'full.zip'
    made = create_full_backup(base, measurement, {}, backup)
    assert 'private/push/push.sqlite3' in made['sqlite_snapshots'], made

    # Mutate current state, then restore the backup. This exercises a nested
    # .sqlite3 target instead of the older top-level .db-only path.
    ps.unsubscribe('https://example.invalid/push/device-1')
    assert ps.status()['subscriptions'] == 0
    restored = restore_full_backup(base, backup, measurement)
    assert restored['sqlite_databases'] >= 1

    ps2 = PushService(base)
    assert ps2.status()['subscriptions'] == 1
    assert (measurement / 'DATALOG' / 'keep.edf').read_bytes() == b'EDF'

print('PASS: push.sqlite3 handles close and full backup/restore snapshots the push database')
