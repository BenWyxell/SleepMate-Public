from pathlib import Path
from tempfile import TemporaryDirectory
import os
import shutil
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from cpap.services import import_resmed_tree
from cpap.patient_store import PatientStore

SRC = BASE / "testdata"

with TemporaryDirectory() as td:
    root = Path(td)
    source = root / "source"
    managed = root / "managed"
    shutil.copytree(SRC, source)

    first = import_resmed_tree(source, managed)
    assert first["verification"] == "byte-for-byte"
    assert first["copied"] > 0

    rel = next(p.relative_to(source) for p in (source / "DATALOG" / "20260824").glob("*.edf"))
    src_file = source / rel
    dst_file = managed / rel

    # Same size + misleading timestamps must NOT fool synchronization.
    original = src_file.read_bytes()
    changed = bytearray(original)
    changed[-1] ^= 0x01
    src_file.write_bytes(bytes(changed))
    src_mtime = src_file.stat().st_mtime
    os.utime(dst_file, (src_mtime + 3600, src_mtime + 3600))
    assert src_file.stat().st_size == dst_file.stat().st_size

    second = import_resmed_tree(source, managed)
    assert second["updated"] >= 1, second
    assert dst_file.read_bytes() == src_file.read_bytes()
    assert "20260824" in second["changed_days"], second

    # A later-growing ResMed/Wi-Fi-SD file must also replace the earlier snapshot.
    with src_file.open("ab") as f:
        f.write(b"SLEEPMATE-GROWTH-TEST")
    third = import_resmed_tree(source, managed)
    assert third["updated"] >= 1, third
    assert dst_file.read_bytes() == src_file.read_bytes()

    # User-entered/private data live in a separate SQLite store and survive CPAP syncs.
    private_base = root / "appbase"
    store = PatientStore(private_base)
    store.save_record("daily_assessment", {"id": "day-20260824", "day": "20260824", "note": "kézi adat marad"})
    import_resmed_tree(source, managed)
    rows = store.list_records("daily_assessment")
    assert any(r.get("id") == "day-20260824" and r.get("note") == "kézi adat marad" for r in rows), rows

app_text = (BASE / "app.py").read_text(encoding="utf-8")
assert "if source_root and source_root.exists():" in app_text
assert "if first_managed_init and source_root" not in app_text
assert "with self._dataset_lock:" in app_text
assert "with Handler._dataset_lock:" in app_text
assert "import_resmed_tree(source, self.dataset.root" in app_text
assert "import_resmed_tree(roots[0], self.dataset.root" in app_text
assert "import_resmed_tree(tmp, self.dataset.root" in app_text

print("PASS: every CPAP refresh uses byte-for-byte verified synchronization; growing/same-size changed files update; manual patient data is preserved")
