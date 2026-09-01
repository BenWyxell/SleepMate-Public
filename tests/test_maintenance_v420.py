from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from cpap.maintenance import GitHubUpdateManager, SelfCheckService, SupportBundleService, OFFICIAL_GITHUB_REPO, version_newer
from cpap.services import PersistentLog
from cpap.version import APP_VERSION

_version_parts = [int(x) for x in APP_VERSION.split('.')]
NEXT_VERSION = f'{_version_parts[0]}.{_version_parts[1]}.{_version_parts[2] + 1}'
assert version_newer(NEXT_VERSION, APP_VERSION)
assert not version_newer(APP_VERSION, APP_VERSION)
assert not version_newer('4.1.9', APP_VERSION)

with tempfile.TemporaryDirectory() as td:
    base = Path(td) / 'SleepMate'
    base.mkdir()
    (base/'private'/'measurement'/'DATALOG').mkdir(parents=True)
    (base/'testdata').mkdir()
    for name, text in {
        'app.py':'print("old")\n', 'SleepMate.vbs':'Option Explicit\n', 'sleepmate_tray.pyw':'pass\n',
        'SleepMate.pyw':'pass\n', 'requirements.txt':'', 'update_worker.py':'# worker\n'
    }.items():
        (base/name).write_text(text, encoding='utf-8')
    (base/'web').mkdir(); (base/'cpap').mkdir()
    (base/'web'/'index.html').write_text('<html></html>', encoding='utf-8')
    (base/'web'/'app.js').write_text('', encoding='utf-8')
    (base/'web'/'service-worker.js').write_text('', encoding='utf-8')
    (base/'cpap'/'version.py').write_text(f'APP_VERSION = "{APP_VERSION}"\n', encoding='utf-8')

    log = PersistentLog(base)
    mgr = GitHubUpdateManager(base, log)
    sample_value = 'unit-test-value-1234567890'
    token_status = mgr.configure_token(sample_value)
    assert token_status['configured'] is False and token_status['required'] is False
    assert not (base/'private'/'update_secrets.bin').exists()
    st = mgr.status({'update_github_repo':'owner/private-repo','update_auto_check':True})
    assert st['github_repo'] == OFFICIAL_GITHUB_REPO
    assert st['configured'] is True and st['authentication'] == 'public-anonymous'
    assert 'token' not in st and sample_value not in json.dumps(st)

    # Build a fake next-version release package + manifest and feed them through
    # the real staging/backup/rollback preparation code without network access.
    release_dir = Path(td)/'release'; release_dir.mkdir()
    pkg_root = Path(td)/'pkg'/f'SleepMate_v{NEXT_VERSION}'; (pkg_root/'cpap').mkdir(parents=True)
    (pkg_root/'app.py').write_text('print("new")\n', encoding='utf-8')
    (pkg_root/'SleepMate.vbs').write_text('Option Explicit\n', encoding='utf-8')
    (pkg_root/'cpap'/'version.py').write_text(f'APP_VERSION = "{NEXT_VERSION}"\n', encoding='utf-8')
    update_zip = release_dir/f'SleepMate_v{NEXT_VERSION}.zip'
    with zipfile.ZipFile(update_zip,'w',zipfile.ZIP_DEFLATED) as z:
        for f in pkg_root.rglob('*'):
            if f.is_file(): z.write(f, Path(f'SleepMate_v{NEXT_VERSION}')/f.relative_to(pkg_root))
    sha = hashlib.sha256(update_zip.read_bytes()).hexdigest()
    manifest = {'format':'sleepmate-update','version':NEXT_VERSION,'min_version':APP_VERSION,'asset':update_zip.name,'sha256':sha}
    manifest_file = release_dir/'sleepmate-update.json'; manifest_file.write_text(json.dumps(manifest),encoding='utf-8')
    fake_release = {
        'tag':NEXT_VERSION,'name':f'SleepMate {NEXT_VERSION}','published_at':'2026-08-26T00:00:00Z','html_url':'',
        'prerelease':False,
        'assets':[{'name':'sleepmate-update.json','url':'mock://manifest','size':manifest_file.stat().st_size},{'name':update_zip.name,'url':'mock://zip','size':update_zip.stat().st_size}],
        'manifest_asset':{'name':'sleepmate-update.json','url':'mock://manifest','size':manifest_file.stat().st_size}
    }
    def fake_check(config, force=False):
        return {'ok':True,'configured':True,'current_version':APP_VERSION,'latest_version':NEXT_VERSION,'update_available':True,'release':fake_release}
    def fake_download(url, destination):
        src = manifest_file if url=='mock://manifest' else update_zip
        destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(src.read_bytes())
    mgr.check = fake_check
    mgr._download_asset = fake_download
    result = mgr.prepare_install({'update_github_repo':'ignored/legacy-value'}, base/'private'/'measurement', 8895)
    assert result['target_version']==NEXT_VERSION
    assert Path(result['backup']).is_file()
    assert Path(result['rollback']).is_dir()
    plan = json.loads(Path(result['plan']).read_text(encoding='utf-8'))
    assert plan['from_version']==APP_VERSION and plan['to_version']==NEXT_VERSION
    assert (Path(result['rollback'])/'app.py').read_text(encoding='utf-8') == 'print("old")\n'

    # Self-check and support bundle must not leak secret data or raw EDF files.
    class DS:
        root = base/'private'/'measurement'
        def diagnostics(self): return {'days':0,'edf_files':0,'errors':[]}
    checker = SelfCheckService(base, log)
    check = checker.run(dataset=DS(),config={'data_dir':str(base/'testdata'),'auto_backup_dir':str(base/'private'/'automatic_backups'),'auto_scan_enabled':False},scanner_status={},backup_status={},push_status={'available':True,'subscriptions':0},remote_status={},update_status=st)
    assert check['overall'] in {'WARN','ERROR','OK'} and check['checks']
    support = SupportBundleService(base, log)
    out = support.create(config={'github_token':'PLAIN_MUST_NOT_LEAK','data_dir':str(base/'testdata')},self_check=check,diagnostics={'errors':[]},system_status={'overall':'ok'},update_status=st,remote_status={'cloudflare_token':'SECRET_REMOTE'},push_status={'subscriptions':1,'endpoint':'SECRET_ENDPOINT'},logs=[{'details':{'token':'SECRET_LOG_TOKEN'},'message':'ok'}])
    with zipfile.ZipFile(out) as z:
        names=set(z.namelist())
        assert 'support_manifest.json' in names and 'app_inventory.json' in names
        assert not any(name.lower().endswith('.edf') for name in names)
        blob=b'\n'.join(z.read(n) for n in names)
        for secret in (b'PLAIN_MUST_NOT_LEAK',b'SECRET_REMOTE',b'SECRET_ENDPOINT',b'SECRET_LOG_TOKEN',sample_value.encode()):
            assert secret not in blob

print(f'PASS: SleepMate {APP_VERSION} public GitHub updater staging + pre-update backup + rollback point + self-check + secret-free support bundle')
