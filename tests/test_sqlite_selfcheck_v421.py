from pathlib import Path
import tempfile, sqlite3, sys
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cpap.maintenance import SelfCheckService

class Dataset:
    def diagnostics(self): return {'errors': [], 'edf_files': 1, 'days': 1}

def run(base):
    src=base/'source'; (src/'DATALOG').mkdir(parents=True, exist_ok=True)
    return SelfCheckService(base).run(dataset=Dataset(), config={'data_dir':str(src)}, scanner_status={}, backup_status={}, push_status=None, remote_status=None, update_status={'configured':False})

with tempfile.TemporaryDirectory() as td:
    base=Path(td); priv=base/'private'; priv.mkdir()
    with closing(sqlite3.connect(priv/'patient.db')) as c:
        c.execute('create table patient(x)'); c.commit()
    (priv/'push').mkdir()
    with closing(sqlite3.connect(priv/'push'/'push.sqlite3')) as c:
        c.execute('create table push(x)'); c.commit()
    junk=priv/'update_runtime'/'rollback'/'old'; junk.mkdir(parents=True)
    for i in range(7): (junk/f'old{i}.db').write_bytes(b'not a sqlite database')
    row=next(x for x in run(base)['checks'] if x['id']=='sqlite')
    assert row['level']=='OK', row
    assert row['message']=='2 aktív adatbázis integritása rendben.', row
    assert len(row['details']['databases'])==2, row
    (priv/'push'/'push.sqlite3').write_bytes(b'broken')
    row=next(x for x in run(base)['checks'] if x['id']=='sqlite')
    assert row['level']=='ERROR', row
    assert '2 aktív adatbázisból 1 hibás' in row['message'], row
    assert 'private/push/push.sqlite3' in row['message'].replace('\\','/'), row
    assert len(row['details']['failed'])==1, row
print('PASS: v4.2.1 self-check inspects only active SQLite stores and reports exact failures')