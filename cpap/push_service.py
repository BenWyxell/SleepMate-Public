from __future__ import annotations

import base64
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


DEFAULT_PREFS = {
    "new_night": True,
    "data_update": True,
    "warning": True,
    "backup_error": True,
}


class PushService:
    def __init__(self, base: Path, logger=None):
        self.base = Path(base)
        self.root = self.base / "private" / "push"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "push.sqlite3"
        self.private_key_path = self.root / "vapid_private.pem"
        self.public_key_path = self.root / "vapid_public.txt"
        self.logger = logger
        self._lock = threading.RLock()
        self._dependency_error = None
        self._ensure_schema()
        self._ensure_vapid_keys()

    @contextmanager
    def _db(self):
        """Short-lived SQLite connection that is ALWAYS closed on Windows.

        sqlite3.Connection's own context manager commits/rolls back, but does not
        close the underlying file handle.  The push database is part of a full
        SleepMate backup, so leaving that handle open makes restore fail with
        WinError 32.  Every push DB operation therefore owns and closes its handle.
        """
        con = sqlite3.connect(str(self.db_path), timeout=20)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except Exception:
            try:
                con.rollback()
            except Exception:
                pass
            raise
        finally:
            con.close()

    @contextmanager
    def maintenance(self):
        """Block push reads/writes while full backup restore replaces private state."""
        with self._lock:
            yield

    def _ensure_schema(self):
        with self._lock, self._db() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS subscriptions(
                    endpoint TEXT PRIMARY KEY,
                    p256dh TEXT NOT NULL,
                    auth TEXT NOT NULL,
                    preferences TEXT NOT NULL,
                    user_agent TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_success_at TEXT,
                    last_error TEXT,
                    vapid_subject TEXT,
                    vapid_public_key TEXT
                )"""
            )
            # Schema migration for push stores created by earlier 4.1.7 builds.
            columns = {str(r[1]) for r in con.execute("PRAGMA table_info(subscriptions)")}
            if "vapid_subject" not in columns:
                con.execute("ALTER TABLE subscriptions ADD COLUMN vapid_subject TEXT")
            if "vapid_public_key" not in columns:
                con.execute("ALTER TABLE subscriptions ADD COLUMN vapid_public_key TEXT")
            con.execute("""CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)""")

    def _ensure_vapid_keys(self):
        if self.private_key_path.exists() and self.public_key_path.exists():
            return
        try:
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives import serialization

            key = ec.generate_private_key(ec.SECP256R1())
            priv = key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
            pub = key.public_key().public_numbers()
            raw = b"\x04" + pub.x.to_bytes(32, "big") + pub.y.to_bytes(32, "big")
            public_b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
            self.private_key_path.write_bytes(priv)
            self.public_key_path.write_text(public_b64, encoding="ascii")
        except Exception as exc:
            self._dependency_error = f"VAPID kulcs nem készíthető: {exc}"

    @property
    def public_key(self):
        try:
            return self.public_key_path.read_text(encoding="ascii").strip()
        except Exception:
            return ""

    def status(self) -> dict[str, Any]:
        dep = self._dependency_error
        if not dep:
            try:
                import pywebpush  # noqa: F401
            except Exception as exc:
                dep = f"A pywebpush függőség hiányzik: {exc}"
        with self._lock, self._db() as con:
            count = int(con.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0])
        return {
            "available": not bool(dep) and bool(self.public_key),
            "public_key": self.public_key,
            "subscriptions": count,
            "dependency_error": dep,
            "default_preferences": DEFAULT_PREFS,
        }

    @staticmethod
    def _prefs(raw):
        p = dict(DEFAULT_PREFS)
        if isinstance(raw, dict):
            for k in p:
                if k in raw:
                    p[k] = bool(raw[k])
        return p

    @staticmethod
    def _vapid_subject(origin: str | None) -> str:
        """Return an Apple-compatible VAPID contact URI.

        Apple rejects placeholder contacts such as mailto:*@localhost with
        BadJwtToken. The installed PWA already runs from a real HTTPS origin
        (Tailscale/Cloudflare), so that exact origin is the most accurate
        contact URI and requires no user-entered email address.
        """
        raw = str(origin or "").strip()
        try:
            parsed = urlparse(raw)
        except Exception:
            parsed = None
        if parsed and parsed.scheme == "https" and parsed.netloc and parsed.hostname:
            host = parsed.hostname.lower().rstrip('.')
            if host not in {"localhost", "127.0.0.1", "::1"} and "." in host:
                return f"https://{parsed.netloc}"
        raise ValueError(
            "Az Apple Web Pushhoz valós HTTPS PWA-cím szükséges VAPID azonosítóként. "
            "Nyisd meg a telepített PWA-t a Tailscale/Cloudflare HTTPS címén, majd iratkozz fel újra."
        )

    def subscribe(self, subscription, preferences=None, user_agent="", origin: str | None = None):
        endpoint = str(subscription.get("endpoint") or "").strip()
        keys = subscription.get("keys") or {}
        p256dh = str(keys.get("p256dh") or "").strip()
        auth = str(keys.get("auth") or "").strip()
        if not endpoint or not p256dh or not auth:
            raise ValueError("Hiányos Web Push subscription.")
        prefs = self._prefs(preferences)
        subject = self._vapid_subject(origin)
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock, self._db() as con:
            con.execute(
                """INSERT INTO subscriptions(
                    endpoint,p256dh,auth,preferences,user_agent,created_at,updated_at,last_success_at,last_error,vapid_subject,vapid_public_key
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(endpoint) DO UPDATE SET
                    p256dh=excluded.p256dh,
                    auth=excluded.auth,
                    preferences=excluded.preferences,
                    user_agent=excluded.user_agent,
                    updated_at=excluded.updated_at,
                    last_error=NULL,
                    vapid_subject=excluded.vapid_subject,
                    vapid_public_key=excluded.vapid_public_key""",
                (endpoint, p256dh, auth, json.dumps(prefs), str(user_agent or "")[:500], now, now, None, None, subject, self.public_key),
            )
        return {"ok": True, "preferences": prefs, "vapid_subject": subject}

    def unsubscribe(self, endpoint):
        with self._lock, self._db() as con:
            cur = con.execute("DELETE FROM subscriptions WHERE endpoint=?", (str(endpoint or ""),))
        return {"ok": True, "removed": int(cur.rowcount or 0)}

    def update_preferences(self, endpoint, preferences):
        prefs = self._prefs(preferences)
        with self._lock, self._db() as con:
            cur = con.execute(
                "UPDATE subscriptions SET preferences=?,updated_at=? WHERE endpoint=?",
                (json.dumps(prefs), datetime.now().isoformat(timespec="seconds"), str(endpoint or "")),
            )
        if not cur.rowcount:
            raise KeyError("A push feliratkozás nem található.")
        return {"ok": True, "preferences": prefs}

    def _rows(self, endpoint: str | None = None):
        with self._lock, self._db() as con:
            if endpoint:
                return list(con.execute("SELECT * FROM subscriptions WHERE endpoint=?", (endpoint,)))
            return list(con.execute("SELECT * FROM subscriptions ORDER BY updated_at DESC"))

    def _send_rows(self, rows: Iterable[sqlite3.Row], event_type, title, body, url, extra=None):
        status = self.status()
        if not status["available"]:
            return {
                "sent": 0,
                "failed": 0,
                "removed": 0,
                "errors": [status.get("dependency_error") or "A Web Push backend nem érhető el."],
            }
        try:
            from pywebpush import webpush, WebPushException
        except Exception as exc:
            return {"sent": 0, "failed": 0, "removed": 0, "errors": [str(exc)]}

        payload = {
            "title": title,
            "body": body,
            "url": url,
            "tag": f"sleepmate-{event_type}",
            "event": event_type,
            **(extra or {}),
        }
        sent = failed = removed = 0
        errors: list[str] = []
        rows = list(rows)
        if not rows:
            return {"sent": 0, "failed": 0, "removed": 0, "errors": ["A kiválasztott eszköz push-feliratkozása nincs a SleepMate szerverén."]}

        for row in rows:
            try:
                prefs = self._prefs(json.loads(row["preferences"] or "{}"))
                if event_type in prefs and not prefs[event_type]:
                    continue
                stored_key = str(row["vapid_public_key"] or "")
                if stored_key and stored_key != self.public_key:
                    raise RuntimeError(
                        "A telefon push-feliratkozása egy korábbi VAPID kulccsal készült. "
                        "A PWA automatikus újrafeliratkozása szükséges."
                    )
                webpush(
                    subscription_info={
                        "endpoint": row["endpoint"],
                        "keys": {"p256dh": row["p256dh"], "auth": row["auth"]},
                    },
                    data=json.dumps(payload, ensure_ascii=False),
                    vapid_private_key=str(self.private_key_path),
                    # Apple szigorúbb a VAPID subjectnél: localhost ál-címre
                    # BadJwtToken választ ad. A feliratkozáskor eltárolt valódi
                    # HTTPS PWA-origin (Tailscale/Cloudflare) kerül a JWT sub claimbe.
                    vapid_claims={"sub": self._vapid_subject(row["vapid_subject"])},
                    ttl=1800,
                )
                sent += 1
                with self._lock, self._db() as con:
                    con.execute(
                        "UPDATE subscriptions SET last_success_at=?,last_error=NULL WHERE endpoint=?",
                        (datetime.now().isoformat(timespec="seconds"), row["endpoint"]),
                    )
            except WebPushException as exc:
                code = getattr(getattr(exc, "response", None), "status_code", None)
                detail = f"HTTP {code}: {exc}" if code else str(exc)
                if code == 403 and "BadJwtToken" in detail:
                    detail += " • Apple VAPID-hitelesítési hiba; ellenőrizd a HTTPS origint és a feliratkozás kulcsát."
                if code in (404, 410):
                    self.unsubscribe(row["endpoint"])
                    removed += 1
                else:
                    failed += 1
                    errors.append(detail[:1000])
                    with self._lock, self._db() as con:
                        con.execute("UPDATE subscriptions SET last_error=? WHERE endpoint=?", (detail[:1000], row["endpoint"]))
            except Exception as exc:
                failed += 1
                detail = str(exc)
                errors.append(detail[:1000])
                with self._lock, self._db() as con:
                    con.execute("UPDATE subscriptions SET last_error=? WHERE endpoint=?", (detail[:1000], row["endpoint"]))

        if self.logger and (sent or failed or removed):
            try:
                self.logger.append(
                    "INFO" if not failed else "WARN",
                    "push",
                    f"Web Push: {sent} elküldve, {failed} hibás, {removed} lejárt feliratkozás törölve.",
                    {"event": event_type, "errors": errors[:3]},
                )
            except Exception:
                pass
        return {"sent": sent, "failed": failed, "removed": removed, "errors": errors}

    def send(self, event_type, title, body, url="/#dashboard", extra=None, endpoint: str | None = None):
        with self._lock:
            return self._send_rows(self._rows(endpoint), event_type, title, body, url, extra)

    def send_warning_once(self, signature, title, body, url="/#logs"):
        if not signature:
            return {"sent": 0, "failed": 0, "removed": 0}
        with self._lock, self._db() as con:
            old = con.execute("SELECT value FROM meta WHERE key='last_warning_signature'").fetchone()
            if old and old[0] == signature:
                return {"sent": 0, "failed": 0, "removed": 0}
            subscriptions = int(con.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0])
        if not subscriptions:
            return {"sent": 0, "failed": 0, "removed": 0}
        result = self.send("warning", title, body, url)
        if result.get("sent"):
            with self._lock, self._db() as con:
                con.execute(
                    "INSERT INTO meta(key,value) VALUES('last_warning_signature',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (signature,),
                )
        return result
