from pathlib import Path
from tempfile import TemporaryDirectory
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cpap.services as svc


def put_day(root: Path, day: str, payload: bytes = b'EDF') -> Path:
    p = root / 'DATALOG' / day / f'{day}_010000_BRP.edf'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(payload)
    return p


with TemporaryDirectory() as td:
    base = Path(td)
    source = base / 'primary'
    target = base / 'private' / 'measurement'
    source.mkdir(parents=True)

    # Initial authoritative baseline.
    put_day(source, '20260820', b'A')
    put_day(source, '20260821', b'B')
    put_day(source, '20260822', b'C')
    r1 = svc.import_resmed_tree(source, target, authoritative=True)
    assert r1['removed'] == 0
    assert (target / 'DATALOG' / '20260821').exists()

    # User/source deletion must disappear from active SleepMate data after one refresh.
    (source / 'DATALOG' / '20260821' / '20260821_010000_BRP.edf').unlink()
    (source / 'DATALOG' / '20260821').rmdir()
    r2 = svc.import_resmed_tree(source, target, authoritative=True)
    assert r2['removed'] == 1, r2
    assert '20260821' in r2['changed_days']
    assert not (target / 'DATALOG' / '20260821').exists()
    assert r2['quarantine_path'] and Path(r2['quarantine_path']).exists()
    assert Path(r2['quarantine_path'], 'DATALOG', '20260821', '20260821_010000_BRP.edf').read_bytes() == b'B'

    # A manual/import-only file is not part of the primary manifest and must survive.
    manual = base / 'manual'
    manual.mkdir()
    put_day(manual, '20260819', b'MANUAL')
    svc.import_resmed_tree(manual, target, authoritative=False)
    assert (target / 'DATALOG' / '20260819' / '20260819_010000_BRP.edf').exists()
    r3 = svc.import_resmed_tree(source, target, authoritative=True)
    assert r3['removed'] == 0
    assert (target / 'DATALOG' / '20260819' / '20260819_010000_BRP.edf').read_bytes() == b'MANUAL'

    # If the authoritative preflight says the source is unstable, no deletion is allowed.
    stale = put_day(source, '20260823', b'D')
    svc.import_resmed_tree(source, target, authoritative=True)
    stale.unlink(); stale.parent.rmdir()
    original = svc._stable_authoritative_snapshot
    try:
        items = svc._copy_candidates(source)
        svc._stable_authoritative_snapshot = lambda root, delay=0.12: (items, False, 'teszt: instabil forrás')
        r4 = svc.import_resmed_tree(source, target, authoritative=True)
        assert r4['removed'] == 0
        assert r4['mirror_deletion_safe'] is False
        assert (target / 'DATALOG' / '20260823' / '20260823_010000_BRP.edf').exists()
    finally:
        svc._stable_authoritative_snapshot = original

print('PASS: v4.2.0 protected authoritative mirror deletes source removals, quarantines them, preserves manual imports, blocks deletion on unstable source')
