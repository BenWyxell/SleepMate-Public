from pathlib import Path
import tempfile
import time
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpap.patient_store import PatientStore

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT/'web'/'index.html').read_text(encoding='utf-8')
css = (ROOT/'web'/'style.css').read_text(encoding='utf-8')
js = (ROOT/'web'/'app.js').read_text(encoding='utf-8')
sw = (ROOT/'web'/'service-worker.js').read_text(encoding='utf-8')
app = (ROOT/'app.py').read_text(encoding='utf-8')

assert 'sleepmate-splash-v410.webp' in html and 'sleepmate-icon-v410.webp' in html
assert (ROOT/'web'/'assets'/'sleepmate-splash-v410.webp').stat().st_size < 100_000
assert (ROOT/'web'/'assets'/'sleepmate-icon-v410.webp').stat().st_size < 80_000
assert 'mobileMenuToggle' in html and 'sidebarScrim' in html and 'mobileMenuClose' in html
assert '.sidebar.mobile-open' in css and 'width:288px!important' in css
assert 'function setMobileSidebar(open)' in js and 'closeMobileSidebar()' in js
assert 'patientPhotoUrl' in js and 'photo_version' in js
assert 'sleepmate-shell-v5.0.0' in sw and 'sleepmate-splash-v410.webp' in sw
assert 'APP_VERSION' in app and 'from cpap.version import APP_NAME, APP_VERSION' in app

with tempfile.TemporaryDirectory() as td:
    st = PatientStore(Path(td))
    st.set_photo(b'first-photo', 'image/webp')
    v1 = st.get_photo_version()
    time.sleep(0.002)
    st.set_photo(b'second-photo', 'image/webp')
    v2 = st.get_photo_version()
    assert v1 and v2 and v1 != v2
    assert st.all_data()['photo_version'] == v2

print('PASS: v4.1.0 PWA drawer + compact WEBP shell + versioned profile-photo cache')
