from pathlib import Path
from tempfile import TemporaryDirectory
import sys, zipfile, json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpap.patient_store import PatientStore
from cpap.services import create_full_backup, restore_full_backup

with TemporaryDirectory() as td:
    root = Path(td)
    src = root / 'src'
    measurement = src / 'private' / 'measurement'
    (measurement / 'DATALOG').mkdir(parents=True)
    (measurement / 'DATALOG' / 'night.edf').write_bytes(b'NIGHT')

    # PatientStore now explicitly closes every SQLite connection. WAL may be
    # checkpointed/removed immediately on Windows; the regression therefore
    # verifies the logical SQLite snapshot and full restore instead of requiring
    # a deliberately leaked WAL handle.
    st = PatientStore(src)
    st.save_profile({'name': 'Teljes Backup Teszt', 'therapy_start_date': '2026-08-20'})
    device = st.save_record('device', {'manufacturer': 'ResMed', 'model': 'AirSense 11 AutoSet', 'active': True})
    mask = st.save_record('mask', {'manufacturer': 'ResMed', 'model': 'AirTouch N30i', 'size': 'SW', 'active': True})
    accessory = st.save_record('accessory', {'category': 'Fűtött gégecső', 'manufacturer': 'ResMed', 'model': 'ClimateLineAir 11', 'active': True})
    st.save_record('setup', {'device_id': device['id'], 'mask_id': mask['id'], 'accessory_ids': [accessory['id']], 'active': True})
    st.save_record('daily_assessment', {'day': '20260824', 'sleep_quality': 9})
    st.set_photo(b'WEBP-DEMO', 'image/webp')

    main_db_size = (src / 'private' / 'patient.db').stat().st_size

    out = root / 'full.zip'
    create_full_backup(src, measurement, {'cloudflare_hostname': 'sleepmate.example.hu'}, out)
    with zipfile.ZipFile(out) as zf:
        manifest = json.loads(zf.read('manifest.json'))
        assert manifest['version'] == 2
        assert 'private/patient.db' in manifest['sqlite_snapshots']
        assert zf.getinfo('private/patient.db').file_size >= main_db_size
        assert 'private/patient.db-wal' not in zf.namelist()

    dst = root / 'dst'
    dst_measurement = dst / 'private' / 'measurement'
    (dst_measurement / 'DATALOG').mkdir(parents=True)
    (dst_measurement / 'DATALOG' / 'stale.edf').write_bytes(b'STALE')
    old = PatientStore(dst)
    old.save_profile({'name': 'Régi személy'})
    old.save_record('mask', {'model': 'Régi maszk', 'size': 'M'})
    (dst / 'private' / 'stale_private.bin').write_bytes(b'OLD')
    browser = dst / 'private' / 'browser_profile'
    browser.mkdir()
    (browser / 'lockfile').write_bytes(b'LOCK')

    result = restore_full_backup(dst, out, dst_measurement)
    restored = PatientStore(dst).all_data()

    assert result['measurement_replaced'] is True
    assert restored['profile']['name'] == 'Teljes Backup Teszt'
    assert len(restored['devices']) == 1
    assert len(restored['masks']) == 1 and restored['masks'][0]['size'] == 'SW'
    assert len(restored['accessories']) == 1
    assert len(restored['setups']) == 1
    assert len(restored['daily_assessments']) == 1
    assert PatientStore(dst).get_photo()[0] == 'image/webp'
    assert not (dst / 'private' / 'stale_private.bin').exists()
    assert (browser / 'lockfile').exists(), 'runtime browser profile must be preserved, not restored/deleted'
    assert (dst_measurement / 'DATALOG' / 'night.edf').exists()
    assert not (dst_measurement / 'DATALOG' / 'stale.edf').exists(), 'measurement restore must replace, not overlay'

print('PASS: v4.1.1 full backup restores patient/equipment + exact private/measurement snapshot with closed SQLite handles')