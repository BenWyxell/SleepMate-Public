from pathlib import Path
import sys
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from tempfile import TemporaryDirectory
from datetime import datetime
import json, zipfile

from cpap.services import import_resmed_tree, safe_extract_zip, create_full_backup, restore_full_backup, compute_next_run, delete_measurement_data
from cpap.resmed import ResMedDataset

SRC=BASE/'testdata'

with TemporaryDirectory() as td:
    root=Path(td)
    target=root/'target'
    r=import_resmed_tree(SRC,target)
    ds=ResMedDataset(target)
    s=ds.summary('20260824')
    assert s['usage']=='03:42:00' and round(s['ahi'],2)==0.54
    assert (target/'Identification.json').exists()

    z=root/'sd.zip'
    with zipfile.ZipFile(z,'w') as zz:
        for p in SRC.rglob('*'):
            if p.is_file(): zz.write(p,Path('wrapped')/p.relative_to(SRC))
    ex=root/'extract';ex.mkdir()
    safe_extract_zip(z,ex)
    target2=root/'target2'
    import_resmed_tree(ex,target2)
    assert ResMedDataset(target2).summary('20260824')['usage']=='03:42:00'

    private= root/'base'/'private';private.mkdir(parents=True)
    (private/'dummy.bin').write_bytes(b'encrypted-demo')
    backup=root/'full.zip'
    create_full_backup(root/'base',target2,{'show_spo2':False},backup)
    restore_target=root/'restore_data'
    result=restore_full_backup(root/'restore_base',backup,restore_target)
    assert result['restored']>0 and (restore_target/'DATALOG'/'20260824').exists()

cfg={'auto_scan_enabled':True,'auto_scan_mode':'interval','auto_scan_interval_minutes':30,'auto_scan_last_run':'2026-08-25T11:00:00'}
assert compute_next_run(cfg,datetime(2026,8,25,11,10,0))==datetime(2026,8,25,11,30,0)
cfg={'auto_scan_enabled':True,'auto_scan_mode':'daily','auto_scan_time':'06:00','auto_scan_last_run':'2026-08-24T06:00:01'}
assert compute_next_run(cfg,datetime(2026,8,25,11,0,0))==datetime(2026,8,25,6,0,0)
cfg={'auto_scan_enabled':True,'auto_scan_mode':'weekly','auto_scan_time':'07:30','auto_scan_days':[0,2],'auto_scan_last_run':'2026-08-24T07:31:00'}
assert compute_next_run(cfg,datetime(2026,8,25,11,0,0))==datetime(2026,8,26,7,30,0)

# Safety regression: deleting program measurement data must never touch the source tree.
with TemporaryDirectory() as td:
    root=Path(td); source=root/'source'; managed=root/'private'/'measurement'
    import shutil
    shutil.copytree(SRC,source)
    source_file=next((source/'DATALOG'/'20260824').glob('*.edf'))
    source_size=source_file.stat().st_size
    import_resmed_tree(source,managed)
    assert ResMedDataset(managed).days(), 'managed import missing'
    delete_measurement_data(managed)
    assert source_file.exists() and source_file.stat().st_size==source_size, 'SOURCE WAS MODIFIED'
    assert ResMedDataset(managed).days()==[], 'managed data not cleared'
print('PASS: external source is read-only; deletion clears only the program-managed mirror')
print('PASS: import folder/ZIP + full backup/restore + automatic scan scheduling')
