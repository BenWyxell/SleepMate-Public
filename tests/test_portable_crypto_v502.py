from __future__ import annotations

from contextlib import closing
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import zipfile

from cpap.patient_store import LocalProtector, PatientStore
from cpap.services import create_full_backup


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    buf = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf


def _legacy_encrypt(private: Path, payload: bytes) -> bytes:
    if os.name == "nt":
        in_blob, in_buf = _blob(payload)
        out_blob = _DataBlob()
        ok = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(in_blob), "SleepMate legacy test", None, None, None, 0,
            ctypes.byref(out_blob),
        )
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key_path = private / ".patient.key"
    if key_path.exists():
        key = key_path.read_bytes()
    else:
        key = os.urandom(32)
        key_path.write_bytes(key)
    nonce = os.urandom(12)
    return b"AG1" + nonce + AESGCM(key).encrypt(nonce, payload, b"CPAP-Elemzo-patient-v1")


def _make_legacy_patient_db(private: Path, encrypted_payload: bytes) -> None:
    db = private / "patient.db"
    with closing(sqlite3.connect(db)) as con:
        con.executescript(
            """
            CREATE TABLE private_entities (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                payload BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE private_assets (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                mime TEXT NOT NULL,
                payload BLOB NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        con.execute(
            "INSERT INTO private_entities(id,kind,payload,created_at,updated_at) VALUES(?,?,?,?,?)",
            ("profile", "profile", encrypted_payload, "2026-08-27T00:00:00", "2026-08-27T00:00:00"),
        )
        con.commit()


def test_legacy_private_state_migrates_and_survives_machine_copy():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "source"
        private = source / "private"
        private.mkdir(parents=True)

        secret_obj = {"github_token": "github_pat_PORTABLE_TEST_123", "cloudflare_token": "cf-test-token"}
        secret_plain = json.dumps(secret_obj, separators=(",", ":")).encode("utf-8")
        legacy_secret = _legacy_encrypt(private, secret_plain)
        for name in ("update_secrets.bin", "remote_secrets.bin"):
            (private / name).write_bytes(legacy_secret)

        profile_plain = json.dumps({"id": "profile", "name": "Hordozható teszt"}, ensure_ascii=False).encode("utf-8")
        legacy_profile = _legacy_encrypt(private, profile_plain)
        _make_legacy_patient_db(private, legacy_profile)

        protector = LocalProtector(private)
        assert protector.mode == "portable-aes-gcm-v2"
        assert (private / ".sleepmate.key").is_file()
        assert (private / ".sleepmate.key").stat().st_size == 32
        assert not protector.migration_errors

        for name in ("update_secrets.bin", "remote_secrets.bin"):
            raw = (private / name).read_bytes()
            assert raw.startswith(b"SM2")
            restored = json.loads(protector.unprotect(raw).decode("utf-8"))
            assert restored == secret_obj

        with closing(sqlite3.connect(private / "patient.db")) as con:
            migrated_payload = bytes(con.execute("SELECT payload FROM private_entities WHERE id='profile'").fetchone()[0])
        assert migrated_payload.startswith(b"SM2")

        moved = root / "moved-to-another-machine"
        shutil.copytree(source, moved)
        moved_store = PatientStore(moved)
        assert moved_store.get_profile()["name"] == "Hordozható teszt"
        moved_protector = LocalProtector(moved / "private")
        moved_secret = json.loads(moved_protector.unprotect((moved / "private" / "update_secrets.bin").read_bytes()).decode("utf-8"))
        assert moved_secret["github_token"] == "github_pat_PORTABLE_TEST_123"


def test_full_backup_contains_portable_key_and_restored_key_is_not_cached():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = root / "state"
        private = base / "private"
        private.mkdir(parents=True)
        p1 = LocalProtector(private)
        blob1 = p1.protect(b"first")
        assert p1.unprotect(blob1) == b"first"

        other_private = root / "other" / "private"
        other_private.mkdir(parents=True)
        p2 = LocalProtector(other_private)
        blob2 = p2.protect(b"second")

        # Simulate full-restore replacing the portable key while a protector object
        # already exists. LocalProtector must re-read the current key on every use.
        shutil.copy2(other_private / ".sleepmate.key", private / ".sleepmate.key")
        assert p1.unprotect(blob2) == b"second"

        measurement = base / "private" / "measurement"
        (measurement / "DATALOG").mkdir(parents=True)
        out = root / "full-backup.zip"
        create_full_backup(base, measurement, {}, out)
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
            assert "private/.sleepmate.key" in names
            assert len(zf.read("private/.sleepmate.key")) == 32
