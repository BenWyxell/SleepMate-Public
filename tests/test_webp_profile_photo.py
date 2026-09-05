from pathlib import Path
import tempfile
from io import BytesIO
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
from cpap.patient_store import PatientStore
from app import _normalize_profile_photo

# server-side normalization to WEBP
img = Image.new("RGB", (1200, 900), (120, 160, 200))
buf = BytesIO()
img.save(buf, format="JPEG", quality=95)
raw = buf.getvalue()
conv, mime = _normalize_profile_photo(raw, "image/jpeg")
assert mime == "image/webp"
assert conv[:4] == b'RIFF' and b'WEBP' in conv[:16]
with Image.open(BytesIO(conv)) as out:
    assert max(out.size) <= 512

# patient store accepts/stores WEBP as-is and backup preserves mime
with tempfile.TemporaryDirectory() as td:
    st = PatientStore(Path(td))
    st.save_profile({"name": "WEBP Teszt"})
    st.set_photo(conv, mime)
    got = st.get_photo()
    assert got is not None and got[0] == 'image/webp'
    bundle = st.export_bundle()
    assert bundle['photo']['mime'] == 'image/webp'
print('PASS: WEBP profile-photo normalization + backup persistence')
