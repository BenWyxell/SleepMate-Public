from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
import sys
import uuid
from contextlib import contextmanager, closing
from typing import Any


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    buf = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf


class LocalProtector:
    """Portable AES-GCM protection for all SleepMate private state.

    SleepMate used Windows DPAPI (CurrentUser) before v5.0.2. DPAPI ciphertext is
    tied to one Windows user/machine and therefore cannot be restored safely on a
    different PC. v5.0.2+ uses one app-managed 256-bit AES-GCM key stored inside
    the private state directory. Full SleepMate backups already include the whole
    private directory, so the key and encrypted data travel together and remain
    readable after a machine move.

    Existing DPAPI/legacy development blobs are migrated in-place automatically
    while they are still readable on the original machine. The key is intentionally
    re-read for every operation so restoring another full backup cannot leave a
    stale encryption key cached in the running process.
    """

    MAGIC = b"SM2"
    LEGACY_DEV_MAGIC = b"AG1"
    AAD = b"SleepMate-portable-private-v2"
    LEGACY_DEV_AAD = b"CPAP-Elemzo-patient-v1"
    KEY_NAME = ".sleepmate.key"
    LEGACY_DEV_KEY_NAME = ".patient.key"
    KNOWN_BLOB_FILES = (
        "ai_secrets.bin",
        "ai_history.bin",
        "update_secrets.bin",
        "remote_secrets.bin",
    )

    def __init__(self, private_dir: Path):
        self.private_dir = private_dir
        self.private_dir.mkdir(parents=True, exist_ok=True)
        self.key_path = self.private_dir / self.KEY_NAME
        self.mode = "portable-aes-gcm-v2"
        self.migration_errors: list[str] = []
        self._ensure_portable_key()
        self.ensure_portable_state()

    def _portable_payload_exists(self) -> bool:
        for name in self.KNOWN_BLOB_FILES:
            path = self.private_dir / name
            try:
                if path.is_file() and path.read_bytes().startswith(self.MAGIC):
                    return True
            except OSError:
                pass
        db_path = self.private_dir / "patient.db"
        if not db_path.is_file():
            return False
        try:
            with closing(sqlite3.connect(db_path)) as con:
                for table in ("private_entities", "private_assets"):
                    exists = con.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    ).fetchone()
                    if not exists:
                        continue
                    row = con.execute(f"SELECT payload FROM {table} LIMIT 1").fetchone()
                    if row and bytes(row[0]).startswith(self.MAGIC):
                        return True
        except sqlite3.Error:
            pass
        return False

    def _ensure_portable_key(self) -> None:
        if self.key_path.exists():
            key = self.key_path.read_bytes()
            if len(key) != 32:
                raise RuntimeError(
                    "A SleepMate hordozható titkosítási kulcsa sérült. "
                    "A private/.sleepmate.key fájl pontosan 32 bájtos kell legyen."
                )
            return
        if self._portable_payload_exists():
            raise RuntimeError(
                "A SleepMate hordozható titkosítási kulcsa hiányzik, miközben titkosított adatok már vannak. "
                "Állítsd vissza a teljes backupból a private/.sleepmate.key fájlt is."
            )
        self.key_path.write_bytes(os.urandom(32))
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass

    def _aes(self):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise RuntimeError("A hordozható titkosításhoz a cryptography csomag szükséges.") from exc
        key = self.key_path.read_bytes()
        if len(key) != 32:
            raise RuntimeError("A SleepMate hordozható titkosítási kulcsa sérült vagy hiányos.")
        return AESGCM(key)

    @classmethod
    def is_portable(cls, data: bytes) -> bool:
        return bytes(data).startswith(cls.MAGIC)

    def protect(self, data: bytes) -> bytes:
        nonce = os.urandom(12)
        return self.MAGIC + nonce + self._aes().encrypt(nonce, data, self.AAD)

    def _legacy_windows_unprotect(self, data: bytes) -> bytes:
        if os.name != "nt":
            raise ValueError(
                "Régi Windows DPAPI-adat található. Ezt először azon a Windows-felhasználón/gépen kell "
                "SleepMate 5.0.2+-szal megnyitni, ahol eredetileg készült, hogy hordozható formátumba migrálódjon."
            )
        in_blob, in_buf = _blob(data)
        out_blob = _DataBlob()
        crypt32 = ctypes.windll.crypt32
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0,
            ctypes.byref(out_blob),
        )
        if not ok:
            error = ctypes.WinError()
            raise ValueError(
                "A régi Windows-DPAPI titkosítás ezen a gépen/felhasználóval nem oldható fel. "
                "A mentést az eredeti gépen SleepMate 5.0.2+-szal megnyitva kell egyszer hordozhatóvá migrálni."
            ) from error
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)

    def _legacy_dev_unprotect(self, data: bytes) -> bytes:
        key_path = self.private_dir / self.LEGACY_DEV_KEY_NAME
        if not key_path.is_file():
            raise ValueError("A régi fejlesztői titkosításhoz szükséges .patient.key hiányzik.")
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise RuntimeError("A régi titkosított adatok migrálásához a cryptography csomag szükséges.") from exc
        if len(data) < 15:
            raise ValueError("Sérült régi titkosított adattárolási formátum.")
        nonce = data[3:15]
        return AESGCM(key_path.read_bytes()).decrypt(nonce, data[15:], self.LEGACY_DEV_AAD)

    def unprotect(self, data: bytes) -> bytes:
        raw = bytes(data)
        if raw.startswith(self.MAGIC):
            if len(raw) < 15:
                raise ValueError("Sérült SleepMate titkosított adattárolási formátum.")
            nonce = raw[3:15]
            try:
                return self._aes().decrypt(nonce, raw[15:], self.AAD)
            except Exception as exc:
                raise ValueError(
                    "A SleepMate titkosított adat nem olvasható a jelenlegi hordozható kulccsal. "
                    "Ellenőrizd, hogy a private/.sleepmate.key ugyanabból a teljes backupból származik."
                ) from exc
        if raw.startswith(self.LEGACY_DEV_MAGIC):
            return self._legacy_dev_unprotect(raw)
        return self._legacy_windows_unprotect(raw)

    def _migrate_blob_file(self, path: Path) -> int:
        if not path.is_file():
            return 0
        raw = path.read_bytes()
        if self.is_portable(raw):
            return 0
        plain = self.unprotect(raw)
        tmp = path.with_suffix(path.suffix + ".portable.tmp")
        tmp.write_bytes(self.protect(plain))
        os.replace(tmp, path)
        return 1

    def _migrate_patient_db(self) -> int:
        db_path = self.private_dir / "patient.db"
        if not db_path.is_file():
            return 0
        migrated = 0
        with closing(sqlite3.connect(db_path)) as con:
            for table in ("private_entities", "private_assets"):
                exists = con.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if not exists:
                    continue
                rows = con.execute(f"SELECT rowid,payload FROM {table}").fetchall()
                for rowid, payload in rows:
                    raw = bytes(payload)
                    if self.is_portable(raw):
                        continue
                    plain = self.unprotect(raw)
                    con.execute(f"UPDATE {table} SET payload=? WHERE rowid=?", (self.protect(plain), rowid))
                    migrated += 1
            con.commit()
        return migrated

    def ensure_portable_state(self) -> dict[str, Any]:
        """Migrate every known legacy private payload that is currently readable."""
        migrated_files = 0
        migrated_rows = 0
        errors: list[str] = []
        for name in self.KNOWN_BLOB_FILES:
            path = self.private_dir / name
            try:
                migrated_files += self._migrate_blob_file(path)
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        try:
            migrated_rows = self._migrate_patient_db()
        except Exception as exc:
            errors.append(f"patient.db: {exc}")
        self.migration_errors = errors
        return {
            "mode": self.mode,
            "key_file": str(self.key_path),
            "migrated_files": migrated_files,
            "migrated_rows": migrated_rows,
            "errors": list(errors),
        }


class PatientStore:
    KINDS = {"diagnosis", "titration", "prescription", "medication", "control", "weight", "device", "mask", "accessory", "setup", "note", "daily_assessment", "timeline_event"}
    EQUIPMENT_KINDS = {"device", "mask", "accessory", "setup"}
    EQUIPMENT_PLURALS = {"devices", "masks", "accessories", "setups"}

    def __init__(self, base: Path):
        self.private_dir = base / "private"
        self.private_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.private_dir / "patient.db"
        self.protector = LocalProtector(self.private_dir)
        self._init_db()

    @contextmanager
    def _db(self):
        """Yield a SQLite connection and always close the Windows file handle.

        sqlite3.Connection's built-in context manager only commits/rolls back;
        it does not close the connection. That leaves patient.db locked on
        Windows and can break backup/restore, updates and temporary test cleanup.
        """
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _init_db(self):
        with self._db() as con:
            con.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS private_entities (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_private_entities_kind ON private_entities(kind);
                CREATE TABLE IF NOT EXISTS private_assets (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    mime TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

    def _encode(self, obj: dict[str, Any]) -> bytes:
        raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self.protector.protect(raw)

    def _decode(self, data: bytes) -> dict[str, Any]:
        return json.loads(self.protector.unprotect(bytes(data)).decode("utf-8"))

    def security_info(self) -> dict[str, Any]:
        return {
            "database": str(self.db_path),
            "encrypted_at_rest": True,
            "protection": self.protector.mode,
            "portable_between_machines": True,
            "portable_key_file": str(self.protector.key_path),
            "migration_errors": list(self.protector.migration_errors),
            "measurement_data_separate": True,
        }

    def get_profile(self) -> dict[str, Any] | None:
        with self._db() as con:
            row = con.execute("SELECT payload FROM private_entities WHERE id='profile' AND kind='profile'").fetchone()
        return self._decode(row["payload"]) if row else None

    def save_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        payload = dict(data)
        payload["id"] = "profile"
        with self._db() as con:
            old = con.execute("SELECT created_at FROM private_entities WHERE id='profile'").fetchone()
            created = old["created_at"] if old else now
            con.execute("""INSERT INTO private_entities(id,kind,payload,created_at,updated_at)
                           VALUES('profile','profile',?,?,?)
                           ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at""",
                        (self._encode(payload), created, now))
        return payload

    def list_records(self, kind: str) -> list[dict[str, Any]]:
        if kind not in self.KINDS:
            raise ValueError(f"Ismeretlen rekordtípus: {kind}")
        with self._db() as con:
            rows = con.execute("SELECT id,payload,created_at,updated_at FROM private_entities WHERE kind=? ORDER BY created_at DESC", (kind,)).fetchall()
        out = []
        for row in rows:
            obj = self._decode(row["payload"])
            obj["id"] = row["id"]
            obj["created_at"] = row["created_at"]
            obj["updated_at"] = row["updated_at"]
            out.append(obj)
        return out

    def save_record(self, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        if kind not in self.KINDS:
            raise ValueError(f"Ismeretlen rekordtípus: {kind}")
        rid = str(data.get("id") or uuid.uuid4())
        now = datetime.now().isoformat(timespec="seconds")
        payload = {k: v for k, v in data.items() if k not in {"created_at", "updated_at"}}
        payload["id"] = rid
        if kind in {"device", "mask", "accessory", "setup", "daily_assessment", "timeline_event"}:
            payload["patient_id"] = str(payload.get("patient_id") or "profile")
        with self._db() as con:
            old = con.execute("SELECT created_at FROM private_entities WHERE id=? AND kind=?", (rid, kind)).fetchone()
            created = old["created_at"] if old else now
            con.execute("""INSERT INTO private_entities(id,kind,payload,created_at,updated_at)
                           VALUES(?,?,?,?,?)
                           ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,payload=excluded.payload,updated_at=excluded.updated_at""",
                        (rid, kind, self._encode(payload), created, now))
        payload["created_at"] = created
        payload["updated_at"] = now
        return payload

    def delete_record(self, kind: str, rid: str) -> bool:
        if kind not in self.KINDS:
            raise ValueError(f"Ismeretlen rekordtípus: {kind}")
        with self._db() as con:
            cur = con.execute("DELETE FROM private_entities WHERE id=? AND kind=?", (rid, kind))
        return cur.rowcount > 0

    def set_photo(self, data: bytes, mime: str):
        now = datetime.now().isoformat(timespec="microseconds")
        with self._db() as con:
            con.execute("""INSERT INTO private_assets(id,kind,mime,payload,updated_at) VALUES('profile-photo','profile-photo',?,?,?)
                           ON CONFLICT(id) DO UPDATE SET mime=excluded.mime,payload=excluded.payload,updated_at=excluded.updated_at""",
                        (mime, self.protector.protect(data), now))

    def get_photo(self) -> tuple[str, bytes] | None:
        with self._db() as con:
            row = con.execute("SELECT mime,payload FROM private_assets WHERE id='profile-photo'").fetchone()
        if not row:
            return None
        return row["mime"], self.protector.unprotect(bytes(row["payload"]))

    def get_photo_version(self) -> str | None:
        with self._db() as con:
            row = con.execute("SELECT updated_at FROM private_assets WHERE id='profile-photo'").fetchone()
        return str(row["updated_at"]) if row and row["updated_at"] else None

    def delete_photo(self):
        with self._db() as con:
            con.execute("DELETE FROM private_assets WHERE id='profile-photo'")

    def delete_patient_only(self):
        with self._db() as con:
            con.execute("DELETE FROM private_entities")
            con.execute("DELETE FROM private_assets")

    def delete_patient_except_equipment(self):
        placeholders = ",".join("?" for _ in self.EQUIPMENT_KINDS)
        with self._db() as con:
            con.execute(f"DELETE FROM private_entities WHERE kind NOT IN ({placeholders})", tuple(sorted(self.EQUIPMENT_KINDS)))
            con.execute("DELETE FROM private_assets")

    def export_bundle(self) -> dict[str, Any]:
        data = self.all_data()
        data.pop("security", None)
        photo = self.get_photo()
        photo_obj = None
        if photo:
            mime, binary = photo
            photo_obj = {"mime": mime, "base64": base64.b64encode(binary).decode("ascii")}
        equipment = {
            "devices": list(data.get("devices") or []),
            "masks": list(data.get("masks") or []),
            "accessories": list(data.get("accessories") or []),
            "setups": list(data.get("setups") or []),
        }
        return {
            "format": "cpap-elemzo-patient-backup",
            "version": 2,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "data": data,
            "photo": photo_obj,
            "measurement_data_included": False,
            "equipment_included": True,
            "equipment": equipment,
            "equipment_counts": {k: len(v) for k, v in equipment.items()},
        }

    def import_bundle(self, bundle: dict[str, Any], mode: str = "merge", include_equipment: bool = True) -> dict[str, Any]:
        if bundle.get("format") != "cpap-elemzo-patient-backup":
            raise ValueError("Nem támogatott kezelt-személy mentési fájl.")
        version = int(bundle.get("version") or 0)
        if version not in {1, 2}:
            raise ValueError("Nem támogatott mentési formátumverzió.")
        data = bundle.get("data")
        if not isinstance(data, dict):
            raise ValueError("A mentési csomagból hiányoznak az adatok.")
        if mode not in {"merge", "replace"}:
            raise ValueError("Ismeretlen visszatöltési mód.")

        equipment = bundle.get("equipment") if isinstance(bundle.get("equipment"), dict) else {}
        incoming = dict(data)
        if include_equipment and equipment:
            for key in self.EQUIPMENT_PLURALS:
                if isinstance(equipment.get(key), list):
                    incoming[key] = equipment.get(key)

        if mode == "replace":
            if include_equipment:
                self.delete_patient_only()
            else:
                self.delete_patient_except_equipment()

        incoming_profile = incoming.get("profile")
        if isinstance(incoming_profile, dict):
            if mode == "merge" and self.get_profile():
                merged = dict(self.get_profile() or {})
                merged.update({k: v for k, v in incoming_profile.items() if v not in (None, "")})
                self.save_profile(merged)
            else:
                self.save_profile(incoming_profile)

        mapping = {
            "diagnoses": "diagnosis", "titrations": "titration",
            "prescriptions": "prescription", "medications": "medication",
            "controls": "control", "weights": "weight", "devices": "device",
            "masks": "mask", "accessories": "accessory", "setups": "setup", "notes": "note",
            "daily_assessments": "daily_assessment", "timeline_events": "timeline_event",
        }
        imported = 0
        equipment_imported = 0
        for plural, kind in mapping.items():
            if plural in self.EQUIPMENT_PLURALS and not include_equipment:
                continue
            rows = incoming.get(plural) or []
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                self.save_record(kind, row)
                imported += 1
                if kind in self.EQUIPMENT_KINDS:
                    equipment_imported += 1

        photo = bundle.get("photo")
        if isinstance(photo, dict) and photo.get("base64"):
            try:
                binary = base64.b64decode(photo["base64"], validate=True)
                if len(binary) <= 4_000_000:
                    self.set_photo(binary, str(photo.get("mime") or "image/jpeg"))
            except Exception as exc:
                raise ValueError(f"A mentés profilképe nem olvasható: {exc}") from exc
        return {
            "mode": mode,
            "records_imported": imported,
            "equipment_imported": equipment_imported,
            "equipment_requested": bool(include_equipment),
            "profile": self.get_profile() is not None,
        }

    def all_data(self) -> dict[str, Any]:
        return {
            "profile": self.get_profile(),
            "diagnoses": self.list_records("diagnosis"),
            "titrations": self.list_records("titration"),
            "prescriptions": self.list_records("prescription"),
            "medications": self.list_records("medication"),
            "controls": self.list_records("control"),
            "weights": self.list_records("weight"),
            "devices": self.list_records("device"),
            "masks": self.list_records("mask"),
            "accessories": self.list_records("accessory"),
            "setups": self.list_records("setup"),
            "notes": self.list_records("note"),
            "daily_assessments": self.list_records("daily_assessment"),
            "timeline_events": self.list_records("timeline_event"),
            "has_photo": self.get_photo() is not None,
            "photo_version": self.get_photo_version(),
            "security": self.security_info(),
        }
