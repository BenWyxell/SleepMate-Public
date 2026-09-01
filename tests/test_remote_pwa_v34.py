from pathlib import Path
import json, tempfile, shutil, sys

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from cpap.remote_access import RemoteSecretStore, RemoteAccessManager

work=Path(tempfile.mkdtemp(prefix='sleepmate_remote_v34_'))
try:
    sample_value='unit-test-value-1234567890'
    store=RemoteSecretStore(work)
    store.save_token(sample_value)
    assert store.token()==sample_value
    raw=(work/'private'/'remote_secrets.bin').read_bytes()
    assert sample_value.encode() not in raw, 'A Cloudflare token plaintextben került lemezre.'
    st=store.status()
    assert st['configured'] and '••••' in st['token_hint']

    mgr=RemoteAccessManager(work,8895)
    ts=mgr.tailscale_status()
    cf=mgr.cloudflare_status('sleepmate.example.hu')
    assert isinstance(ts,dict) and 'installed' in ts and 'serve_active' in ts
    assert isinstance(cf,dict) and cf['url']=='https://sleepmate.example.hu'
    assert cf['token_configured'] is True

    manifest=json.loads((BASE/'web'/'manifest.webmanifest').read_text(encoding='utf-8'))
    assert manifest['name']=='SleepMate'
    assert manifest['display'] in ('standalone','fullscreen')
    assert any(x.get('sizes')=='192x192' for x in manifest['icons'])
    assert any(x.get('sizes')=='512x512' for x in manifest['icons'])
    sw=(BASE/'web'/'service-worker.js').read_text(encoding='utf-8')
    assert '/api/' in sw and 'fetch' in sw
    html=(BASE/'web'/'index.html').read_text(encoding='utf-8')
    js=(BASE/'web'/'app-core.js').read_text(encoding='utf-8')
    assert 'Távoli elérés' in html and 'Tailscale' in html and 'Cloudflare' in html
    assert 'installPwa' in js and 'loadRemoteStatus' in js
    assert 'További akciók' not in js and '>•••<' not in js
    app=(BASE/'app.py').read_text(encoding='utf-8')
    assert "default='127.0.0.1'" in app or 'default="127.0.0.1"' in app
    print('PASS: local-only backend + encrypted Cloudflare token + Tailscale/Cloudflare status + PWA + Szekciók action cleanup')
finally:
    shutil.rmtree(work,ignore_errors=True)
