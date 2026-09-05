from pathlib import Path
import tempfile
import sqlite3
import sys
from contextlib import closing

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cpap.services as services

orig_connect = services.sqlite3.connect
opened = []

class TrackingConnection(sqlite3.Connection):
    def close(self):
        self.was_closed = True
        return super().close()

def tracked_connect(*args, **kwargs):
    kwargs.setdefault('factory', TrackingConnection)
    con = orig_connect(*args, **kwargs)
    con.was_closed = False
    opened.append(con)
    return con

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    source = root / 'source.db'
    snapshot = root / 'snapshot.db'
    restored = root / 'restored.db'
    with closing(orig_connect(source)) as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('CREATE TABLE t(v TEXT)')
        con.execute("INSERT INTO t VALUES('SleepMate')")
        con.commit()

    services.sqlite3.connect = tracked_connect
    try:
        services._sqlite_snapshot(source, snapshot)
        assert opened and all(c.was_closed for c in opened), 'snapshot SQLite handle remained open'
        opened.clear()
        services._sqlite_restore(snapshot, restored)
        assert opened and all(c.was_closed for c in opened), 'restore SQLite handle remained open'
    finally:
        services.sqlite3.connect = orig_connect

    with closing(orig_connect(restored)) as con:
        assert con.execute('SELECT v FROM t').fetchone()[0] == 'SleepMate'

print('PASS: v4.1.4 SQLite snapshot/restore handles are explicitly closed')