from datetime import datetime
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpap.services import AutoBackupScheduler, PersistentLog

cfg = {
    'auto_backup_enabled': True,
    'auto_backup_mode': 'weekly',
    'auto_backup_time': '21:40',
    'auto_backup_weekday': 1,  # Tuesday
    'auto_backup_monthday': 1,
    'auto_backup_last_run': None,
}

def get_config():
    return dict(cfg)

def save_config(patch):
    cfg.update(patch)
    return dict(cfg)

with tempfile.TemporaryDirectory() as td:
    log = PersistentLog(Path(td))
    sched = AutoBackupScheduler(get_config, save_config, lambda reason: None, log)
    due = sched._refresh_schedule(cfg, now=datetime(2026, 8, 25, 21, 39, 50), force=True)
    assert due == datetime(2026, 8, 25, 21, 40, 0), due
    # Critical regression: after the minute boundary the due target must remain
    # today's 21:40, not jump to next Tuesday before the loop can execute it.
    still_due = sched._refresh_schedule(cfg, now=datetime(2026, 8, 25, 21, 40, 15))
    assert still_due == due, (due, still_due)

    # Changing the schedule must refresh immediately.
    cfg['auto_backup_time'] = '21:45'
    changed = sched._refresh_schedule(cfg, now=datetime(2026, 8, 25, 21, 40, 15))
    assert changed == datetime(2026, 8, 25, 21, 45, 0), changed

print('PASS: v4.0.9 auto-backup due time survives polling across scheduled minute')
