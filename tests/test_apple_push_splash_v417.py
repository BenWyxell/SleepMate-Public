from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
JS=(ROOT/'web'/'app-core.js').read_text(encoding='utf-8')
CSS=(ROOT/'web'/'style.css').read_text(encoding='utf-8')
PUSH=(ROOT/'cpap'/'push_service.py').read_text(encoding='utf-8')
BASE_SW=(ROOT/'web'/'service-worker-v508-base.js').read_text(encoding='utf-8')
PUSH_FIX=(ROOT/'web'/'pwa-push-fix.js').read_text(encoding='utf-8')


def test_standalone_pwa_shows_exactly_one_custom_html_splash_per_document_boot():
    assert 'pwa-native-launch' not in HTML
    assert '@media (display-mode: standalone){#startupSplash{display:none!important}}' not in CSS
    assert 'html.pwa-standalone #startupSplash{display:grid!important}' in CSS
    assert 'window.__sleepmateBootStarted' in JS
    assert 'prepareStartupSplash();' in JS and 'init();' in JS
    # v5.3.17 intentionally allows the installed standalone PWA to move to the
    # new document generation. The duplicate-splash guard is per document boot,
    # so the old standalone exclusion must not be required anymore.
    assert 'hadController&&!standalonePwa()' not in JS


def test_push_uses_real_https_origin_and_repairs_key_drift():
    assert 'origin:location.origin' in JS
    assert 'pushSubscriptionKeyMatches' in JS
    assert 'alignPushSubscription' in JS
    assert 'force:true' in JS
    assert 'mailto:sleepmate@localhost' not in PUSH
    assert 'vapid_subject TEXT' in PUSH
    assert 'vapid_public_key TEXT' in PUSH


def test_vapid_subject_accepts_real_https_and_rejects_localhost():
    import sys
    sys.path.insert(0,str(ROOT))
    from cpap.push_service import PushService
    assert PushService._vapid_subject('https://sleepmate.example.hu/path') == 'https://sleepmate.example.hu'
    assert PushService._vapid_subject('https://host.tail123.ts.net') == 'https://host.tail123.ts.net'
    for value in ('mailto:sleepmate@localhost','http://localhost:8895','https://localhost'):
        try:
            PushService._vapid_subject(value)
        except ValueError:
            pass
        else:
            raise AssertionError(value)


def test_service_worker_install_is_tolerant_bounded_and_atomic_for_ios_push():
    assert 'c.addAll(SHELL)' not in BASE_SW
    assert 'cacheShellAsset' in BASE_SW
    assert 'AbortController' in BASE_SW
    assert 'setTimeout(()=>controller.abort(),5000)' in BASE_SW
    assert 'OPTIONAL_SHELL_ASSETS' in BASE_SW
    assert 'precacheShellAtomic' in BASE_SW
    assert 'if(!OPTIONAL_SHELL_ASSETS.has(pathname))throw error' in BASE_SW
    assert 'await precacheShellAtomic();await self.skipWaiting()' in BASE_SW
    assert "self.addEventListener('push'" in BASE_SW


def test_pwa_push_lifecycle_has_bounded_service_worker_and_pushmanager_steps():
    assert 'SW_TIMEOUT=10000' in PUSH_FIX
    assert 'SUBSCRIBE_TIMEOUT=15000' in PUSH_FIX
    assert 'getRegistrationBounded' in PUSH_FIX
    assert 'ensureActiveRegistration' in PUSH_FIX
    assert 'pushManager.getSubscription()' in PUSH_FIX
    assert 'fixedLoadPushStatus' in PUSH_FIX
