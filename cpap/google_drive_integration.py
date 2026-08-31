from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from .patient_store import LocalProtector


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"
OAUTH_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN = "https://oauth2.googleapis.com/token"
DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
DEFAULT_FOLDER = "SleepMate Backups"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_read(path: Path, fallback: Any) -> Any:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj
    except Exception:
        return fallback


def _json_write_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class GoogleDriveSecretStore:
    """Encrypted Google OAuth state stored inside the normal SleepMate private tree."""

    def __init__(self, private_dir: Path):
        self.private_dir = private_dir
        self.private_dir.mkdir(parents=True, exist_ok=True)
        self.path = private_dir / "google_drive_secrets.bin"
        self.protector = LocalProtector(private_dir)
        self._lock = threading.RLock()

    def read(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.is_file():
                return {}
            try:
                raw = self.protector.unprotect(self.path.read_bytes())
                obj = json.loads(raw.decode("utf-8"))
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}

    def write(self, payload: dict[str, Any]) -> None:
        with self._lock:
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            tmp = self.path.with_suffix(".tmp")
            tmp.write_bytes(self.protector.protect(raw))
            os.replace(tmp, self.path)

    def update(self, **values: Any) -> dict[str, Any]:
        data = self.read()
        data.update(values)
        self.write(data)
        return data

    def clear_tokens(self) -> None:
        data = self.read()
        for key in ("access_token", "refresh_token", "expires_at", "account_email"):
            data.pop(key, None)
        self.write(data)


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    server_version = "SleepMateGoogleOAuth/1.0"

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self.server.oauth_query = query  # type: ignore[attr-defined]
        ok = bool(query.get("code")) and not query.get("error")
        title = "Google Drive csatlakoztatva" if ok else "Google Drive csatlakoztatás sikertelen"
        detail = "Visszatérhetsz a SleepMate alkalmazásba." if ok else "A Google nem adott engedélyt. Visszatérhetsz a SleepMate alkalmazásba."
        body = f"""<!doctype html><html lang='hu'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title><body style='margin:0;background:#08111f;color:#edf4fb;font:16px system-ui;display:grid;place-items:center;min-height:100vh'><main style='max-width:520px;padding:32px;text-align:center'><div style='font-size:46px'>☾</div><h1>{title}</h1><p style='color:#9db1c3'>{detail}</p></main></body></html>""".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class GoogleDriveService:
    def __init__(self, app_module):
        self.app = app_module
        self.handler = app_module.Handler
        self.state_base = Path(app_module.STATE_BASE)
        self.private_dir = self.state_base / "private"
        self.drive_dir = self.private_dir / "google_drive"
        self.settings_file = self.drive_dir / "settings.json"
        self.state_file = self.drive_dir / "state.json"
        self.drive_dir.mkdir(parents=True, exist_ok=True)
        self.secrets = GoogleDriveSecretStore(self.private_dir)
        self._settings_lock = threading.RLock()
        self._operation_lock = threading.Lock()
        self._stop = threading.Event()
        self._settings = self._load_settings()
        threading.Thread(target=self._auto_upload_loop, daemon=True, name="SleepMate-GoogleDrive-Backup").start()
        self.log("Google Drive backup modul inicializálva.")

    def log(self, message: str, level: str = "INFO") -> None:
        try:
            self.handler.persistent_log.append(level, "google_drive", message)
        except Exception:
            pass

    def _default_settings(self) -> dict[str, Any]:
        return {
            "client_id": "",
            "folder_name": DEFAULT_FOLDER,
            "auto_upload": False,
        }

    def _load_settings(self) -> dict[str, Any]:
        cfg = self._default_settings()
        loaded = _json_read(self.settings_file, {})
        if isinstance(loaded, dict):
            cfg.update(loaded)
        cfg["client_id"] = str(cfg.get("client_id") or "").strip()
        cfg["folder_name"] = str(cfg.get("folder_name") or DEFAULT_FOLDER).strip() or DEFAULT_FOLDER
        cfg["auto_upload"] = bool(cfg.get("auto_upload"))
        _json_write_atomic(self.settings_file, cfg)
        return cfg

    def reload_from_disk(self) -> None:
        with self._settings_lock:
            self._settings = self._load_settings()
        self.log("Google Drive beállítások újratöltve.")

    def settings(self) -> dict[str, Any]:
        with self._settings_lock:
            cfg = dict(self._settings)
        secret = self.secrets.read()
        return {
            **cfg,
            "client_secret_configured": bool(secret.get("client_secret")),
            "connected": bool(secret.get("refresh_token")),
            "account_email": str(secret.get("account_email") or ""),
        }

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("Érvénytelen Google Drive beállításcsomag.")
        with self._settings_lock:
            old_client = str(self._settings.get("client_id") or "")
            cfg = dict(self._settings)
            if "client_id" in data:
                cfg["client_id"] = str(data.get("client_id") or "").strip()
            if "folder_name" in data:
                cfg["folder_name"] = str(data.get("folder_name") or DEFAULT_FOLDER).strip() or DEFAULT_FOLDER
            if "auto_upload" in data:
                cfg["auto_upload"] = bool(data.get("auto_upload"))
            self._settings = cfg
            _json_write_atomic(self.settings_file, cfg)

        secret_value = str(data.get("client_secret") or "").strip() if "client_secret" in data else ""
        if secret_value:
            self.secrets.update(client_secret=secret_value)
        if old_client and cfg["client_id"] != old_client:
            self.secrets.clear_tokens()
            state = self._state()
            state.pop("folder_id", None)
            _json_write_atomic(self.state_file, state)
            self.log("A Google OAuth Client ID megváltozott; újracsatlakozás szükséges.", "WARN")
        return self.settings()

    def _state(self) -> dict[str, Any]:
        obj = _json_read(self.state_file, {})
        return obj if isinstance(obj, dict) else {}

    def _save_state(self, **values: Any) -> dict[str, Any]:
        state = self._state()
        state.update(values)
        state["updated_at"] = _now()
        _json_write_atomic(self.state_file, state)
        return state

    def _local_backup_dir(self) -> Path:
        cfg = self.app.load_config()
        return Path(str(cfg.get("auto_backup_dir") or (self.private_dir / "automatic_backups"))).expanduser().resolve()

    def _local_backups(self) -> list[Path]:
        root = self._local_backup_dir()
        if not root.is_dir():
            return []
        rows = [p for p in root.glob("SleepMate_auto_backup_*.zip") if p.is_file()]
        return sorted(rows, key=lambda p: p.stat().st_mtime, reverse=True)

    def status(self) -> dict[str, Any]:
        cfg = self.settings()
        state = self._state()
        local = self._local_backups()
        return {
            "available": True,
            "configured": bool(cfg.get("client_id")),
            "connected": bool(cfg.get("connected")),
            "account_email": cfg.get("account_email") or "",
            "folder_name": cfg.get("folder_name") or DEFAULT_FOLDER,
            "auto_upload": bool(cfg.get("auto_upload")),
            "last_upload": state.get("last_upload"),
            "last_upload_file": state.get("last_upload_file"),
            "last_error": state.get("last_error"),
            "local_backup_count": len(local),
            "latest_local_backup": local[0].name if local else None,
            "oauth_browser": "server",
        }

    @staticmethod
    def _form_request(url: str, data: dict[str, Any], timeout: float = 30) -> dict[str, Any]:
        body = urllib.parse.urlencode({k: v for k, v in data.items() if v not in (None, "")}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            raise RuntimeError(f"Google OAuth hiba (HTTP {exc.code}): {detail}") from exc
        obj = json.loads(raw.decode("utf-8"))
        if not isinstance(obj, dict):
            raise RuntimeError("A Google OAuth váratlan választ adott.")
        return obj

    def _token_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        secret = self.secrets.read()
        if secret.get("client_secret"):
            payload = dict(payload)
            payload["client_secret"] = secret["client_secret"]
        return self._form_request(OAUTH_TOKEN, payload)

    def _access_token(self) -> str:
        secret = self.secrets.read()
        token = str(secret.get("access_token") or "")
        try:
            expires = float(secret.get("expires_at") or 0)
        except Exception:
            expires = 0
        if token and expires > time.time() + 60:
            return token
        refresh = str(secret.get("refresh_token") or "")
        client_id = str(self._settings.get("client_id") or "")
        if not refresh or not client_id:
            raise RuntimeError("A Google Drive nincs csatlakoztatva.")
        obj = self._token_request({"client_id": client_id, "refresh_token": refresh, "grant_type": "refresh_token"})
        token = str(obj.get("access_token") or "")
        if not token:
            raise RuntimeError("A Google nem adott új hozzáférési tokent.")
        ttl = int(obj.get("expires_in") or 3600)
        self.secrets.update(access_token=token, expires_at=time.time() + ttl)
        return token

    def _request_json(self, url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 45) -> dict[str, Any]:
        token = self._access_token()
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            raise RuntimeError(f"Google Drive API hiba (HTTP {exc.code}): {detail}") from exc
        if not raw:
            return {}
        obj = json.loads(raw.decode("utf-8"))
        if not isinstance(obj, dict):
            raise RuntimeError("A Google Drive API váratlan választ adott.")
        return obj

    def _account_email(self, access_token: str) -> str:
        req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                obj = json.loads(response.read().decode("utf-8"))
            return str(obj.get("email") or "") if isinstance(obj, dict) else ""
        except Exception:
            return ""

    def connect_job(self, jid: str) -> dict[str, Any]:
        client_id = str(self._settings.get("client_id") or "").strip()
        if not client_id:
            raise RuntimeError("Előbb add meg a Google OAuth Desktop Client ID-t.")
        self.handler.jobs.update(jid, progress=8, phase="Google OAuth", message="Bejelentkezési munkamenet előkészítése…")
        callback_server = HTTPServer(("127.0.0.1", 0), _OAuthCallbackHandler)
        callback_server.timeout = 1.0
        callback_server.oauth_query = {}  # type: ignore[attr-defined]
        redirect_uri = f"http://127.0.0.1:{callback_server.server_port}/callback"
        state = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": f"openid {EMAIL_SCOPE} {DRIVE_SCOPE}",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        auth_url = OAUTH_AUTHORIZE + "?" + urllib.parse.urlencode(params)
        opened = webbrowser.open(auth_url, new=1, autoraise=True)
        self.handler.jobs.update(
            jid, progress=20, phase="Google bejelentkezés",
            message="A Google engedélykérés megnyílt a SleepMate gép böngészőjében. Engedélyezd a Drive hozzáférést.",
        )
        if not opened:
            self.log("A Google OAuth böngésző automatikus megnyitása nem volt visszaigazolható.", "WARN")
        deadline = time.time() + 300
        try:
            while time.time() < deadline:
                callback_server.handle_request()
                query = getattr(callback_server, "oauth_query", {})
                if query:
                    break
            else:
                raise RuntimeError("A Google bejelentkezés 5 percen belül nem fejeződött be.")
        finally:
            callback_server.server_close()
        query = getattr(callback_server, "oauth_query", {})
        if query.get("error"):
            raise RuntimeError(f"A Google engedélykérés sikertelen: {query.get('error_description', query.get('error'))[0]}")
        returned_state = str((query.get("state") or [""])[0])
        if returned_state != state:
            raise RuntimeError("A Google OAuth biztonsági state ellenőrzése sikertelen.")
        code = str((query.get("code") or [""])[0])
        if not code:
            raise RuntimeError("A Google nem adott engedélyezési kódot.")
        self.handler.jobs.update(jid, progress=65, phase="Google OAuth", message="Hozzáférés véglegesítése…")
        token = self._token_request({
            "client_id": client_id,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        access = str(token.get("access_token") or "")
        refresh = str(token.get("refresh_token") or "")
        if not access or not refresh:
            raise RuntimeError("A Google nem adott tartós Drive hozzáférést. Válaszd le, majd engedélyezd újra a kapcsolatot.")
        ttl = int(token.get("expires_in") or 3600)
        email = self._account_email(access)
        self.secrets.update(access_token=access, refresh_token=refresh, expires_at=time.time() + ttl, account_email=email)
        folder = self._ensure_folder(force=True)
        self._save_state(last_error=None)
        self.handler.jobs.update(jid, progress=95, phase="Google Drive", message="A SleepMate Backup mappa elérhető.")
        self.log(f"Google Drive csatlakoztatva: {email or 'Google-fiók'} • mappa={folder}")
        return {"connected": True, "account_email": email, "folder_id": folder}

    def disconnect(self) -> dict[str, Any]:
        self.secrets.clear_tokens()
        self._save_state(last_error=None)
        self.log("Google Drive kapcsolat leválasztva.")
        return self.status()

    def _ensure_folder(self, force: bool = False) -> str:
        state = self._state()
        existing = str(state.get("folder_id") or "")
        if existing and not force:
            return existing
        name = str(self._settings.get("folder_name") or DEFAULT_FOLDER)
        q = f"mimeType='application/vnd.google-apps.folder' and name='{name.replace(chr(39), chr(92)+chr(39))}' and trashed=false"
        url = DRIVE_API + "/files?" + urllib.parse.urlencode({"q": q, "spaces": "drive", "pageSize": "10", "fields": "files(id,name)"})
        rows = self._request_json(url).get("files") or []
        if rows:
            folder_id = str(rows[0].get("id") or "")
        else:
            created = self._request_json(DRIVE_API + "/files?fields=id,name", method="POST", payload={"name": name, "mimeType": "application/vnd.google-apps.folder", "appProperties": {"sleepmate": "backup-root"}})
            folder_id = str(created.get("id") or "")
        if not folder_id:
            raise RuntimeError("A Google Drive Backup mappa nem hozható létre.")
        self._save_state(folder_id=folder_id)
        return folder_id

    def list_backups(self) -> list[dict[str, Any]]:
        folder = self._ensure_folder()
        q = f"'{folder}' in parents and trashed=false"
        fields = "files(id,name,size,createdTime,modifiedTime,md5Checksum),nextPageToken"
        url = DRIVE_API + "/files?" + urllib.parse.urlencode({"q": q, "spaces": "drive", "pageSize": "100", "orderBy": "createdTime desc", "fields": fields})
        files = self._request_json(url).get("files") or []
        out = []
        for row in files:
            name = str(row.get("name") or "")
            if not name.lower().endswith(".zip"):
                continue
            out.append({
                "id": str(row.get("id") or ""),
                "name": name,
                "size": int(row.get("size") or 0),
                "created_at": row.get("createdTime"),
                "modified_at": row.get("modifiedTime"),
                "md5": row.get("md5Checksum"),
            })
        return out

    def _existing_name(self, folder: str, name: str) -> str | None:
        escaped = name.replace("'", "\\'")
        q = f"'{folder}' in parents and name='{escaped}' and trashed=false"
        url = DRIVE_API + "/files?" + urllib.parse.urlencode({"q": q, "spaces": "drive", "pageSize": "1", "fields": "files(id,name,size)"})
        rows = self._request_json(url).get("files") or []
        return str(rows[0].get("id") or "") if rows else None

    def _begin_resumable_upload(self, path: Path, folder: str) -> str:
        token = self._access_token()
        metadata = json.dumps({"name": path.name, "parents": [folder], "appProperties": {"sleepmateBackup": "true"}}, ensure_ascii=False).encode("utf-8")
        url = DRIVE_UPLOAD_API + "/files?uploadType=resumable&fields=id,name,size,createdTime,modifiedTime"
        req = urllib.request.Request(url, data=metadata, method="POST", headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "X-Upload-Content-Type": "application/zip",
            "X-Upload-Content-Length": str(path.stat().st_size),
        })
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                location = str(response.headers.get("Location") or "")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            raise RuntimeError(f"Google Drive feltöltés előkészítési hiba (HTTP {exc.code}): {detail}") from exc
        if not location:
            raise RuntimeError("A Google Drive nem adott resumable upload URL-t.")
        return location

    @staticmethod
    def _stream_upload(session_url: str, path: Path) -> dict[str, Any]:
        parsed = urllib.parse.urlsplit(session_url)
        conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=180)
        target = parsed.path + (("?" + parsed.query) if parsed.query else "")
        size = path.stat().st_size
        try:
            conn.putrequest("PUT", target)
            conn.putheader("Content-Type", "application/zip")
            conn.putheader("Content-Length", str(size))
            conn.endheaders()
            with path.open("rb") as fh:
                while True:
                    chunk = fh.read(1024 * 1024)
                    if not chunk:
                        break
                    conn.send(chunk)
            response = conn.getresponse()
            raw = response.read()
            if response.status not in (200, 201):
                raise RuntimeError(f"Google Drive feltöltési hiba (HTTP {response.status}): {raw.decode('utf-8', errors='replace')[:1200]}")
            obj = json.loads(raw.decode("utf-8")) if raw else {}
            return obj if isinstance(obj, dict) else {}
        finally:
            conn.close()

    def upload_backup(self, path: Path) -> dict[str, Any]:
        path = path.expanduser().resolve()
        if not path.is_file() or not zipfile.is_zipfile(path):
            raise RuntimeError(f"Nem érvényes SleepMate backup ZIP: {path}")
        folder = self._ensure_folder()
        existing = self._existing_name(folder, path.name)
        if existing:
            result = {"id": existing, "name": path.name, "size": path.stat().st_size, "skipped": True}
        else:
            session = self._begin_resumable_upload(path, folder)
            result = self._stream_upload(session, path)
            result["skipped"] = False
        signature = f"{path.stat().st_size}:{path.stat().st_mtime_ns}"
        state = self._state()
        uploaded = state.get("uploaded") if isinstance(state.get("uploaded"), dict) else {}
        uploaded[path.name] = signature
        if len(uploaded) > 250:
            uploaded = dict(list(uploaded.items())[-250:])
        self._save_state(uploaded=uploaded, last_upload=_now(), last_upload_file=path.name, last_error=None)
        self.log(f"Google Drive backup {'már létezett' if result.get('skipped') else 'feltöltve'}: {path.name}")
        return result

    def upload_latest_job(self, jid: str) -> dict[str, Any]:
        if not self._operation_lock.acquire(blocking=False):
            raise RuntimeError("Már fut Google Drive művelet.")
        try:
            rows = self._local_backups()
            if not rows:
                raise RuntimeError("Még nincs feltölthető automatikus SleepMate backup.")
            self.handler.jobs.update(jid, progress=15, phase="Google Drive", message=f"{rows[0].name} előkészítése…")
            result = self.upload_backup(rows[0])
            self.handler.jobs.update(jid, progress=95, phase="Google Drive", message="A legutóbbi backup a Drive-on van.")
            return result
        finally:
            self._operation_lock.release()

    def _download_file(self, file_id: str, destination: Path, jid: str | None = None) -> Path:
        if not file_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in file_id):
            raise ValueError("Érvénytelen Google Drive fájlazonosító.")
        token = self._access_token()
        url = DRIVE_API + "/files/" + urllib.parse.quote(file_id, safe="") + "?alt=media"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp = destination.with_suffix(destination.suffix + ".part")
        try:
            with urllib.request.urlopen(req, timeout=120) as response, tmp.open("wb") as out:
                total = int(response.headers.get("Content-Length") or 0)
                received = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    received += len(chunk)
                    if jid and total:
                        self.handler.jobs.update(jid, progress=min(35, 5 + int(received * 30 / total)), phase="Google Drive letöltés", message=f"{received/1024/1024:.1f} / {total/1024/1024:.1f} MB")
            os.replace(tmp, destination)
        except Exception:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        if not zipfile.is_zipfile(destination):
            destination.unlink(missing_ok=True)
            raise RuntimeError("A Drive-ról letöltött fájl nem érvényes ZIP backup.")
        return destination

    def restore_job(self, jid: str, request_handler, file_id: str) -> dict[str, Any]:
        if not self._operation_lock.acquire(blocking=False):
            raise RuntimeError("Már fut Google Drive művelet.")
        temp = self.private_dir / "uploads" / f"drive_restore_{jid}.zip"
        try:
            self.handler.jobs.update(jid, progress=3, phase="Google Drive", message="Backup letöltése…")
            self._download_file(file_id, temp, jid)
            self.handler.jobs.update(jid, progress=38, phase="Backup ellenőrzése", message="A letöltött teljes mentés ellenőrzése…")
            # Reuse the single proven SleepMate full-restore path.  Because this
            # integration is installed after SleepSync, the method also keeps the
            # existing SleepSync restore coordination intact.
            result = request_handler._restore_backup_job(jid, str(temp))
            self.reload_from_disk()
            self.log("Teljes SleepMate visszaállítás elkészült Google Drive backupból.")
            return {"source": "google_drive", **(result if isinstance(result, dict) else {})}
        finally:
            try:
                temp.unlink()
            except OSError:
                pass
            self._operation_lock.release()

    def _auto_upload_loop(self) -> None:
        # Local backup success is never coupled to cloud success.  This watcher
        # only mirrors completed ZIPs after the fact; failures remain retryable.
        while not self._stop.wait(25):
            try:
                with self._settings_lock:
                    enabled = bool(self._settings.get("auto_upload"))
                if not enabled or not self.secrets.read().get("refresh_token"):
                    continue
                rows = self._local_backups()
                if not rows:
                    continue
                path = rows[0]
                signature = f"{path.stat().st_size}:{path.stat().st_mtime_ns}"
                state = self._state()
                uploaded = state.get("uploaded") if isinstance(state.get("uploaded"), dict) else {}
                if uploaded.get(path.name) == signature:
                    continue
                if not self._operation_lock.acquire(blocking=False):
                    continue
                try:
                    self.upload_backup(path)
                finally:
                    self._operation_lock.release()
            except Exception as exc:
                self._save_state(last_error=str(exc))
                self.log(f"Google Drive automatikus backup feltöltés később újrapróbálva: {exc}", "WARN")

    def start_connect(self) -> str:
        jid = self.handler.jobs.create("google_drive_connect", "Google Drive csatlakoztatása")
        self.handler.jobs.start(jid, self.connect_job)
        return jid

    def start_upload_latest(self) -> str:
        jid = self.handler.jobs.create("google_drive_upload", "Backup feltöltése Google Drive-ra")
        self.handler.jobs.start(jid, self.upload_latest_job)
        return jid


_service: GoogleDriveService | None = None
_service_lock = threading.RLock()


def get_service(app_module) -> GoogleDriveService:
    global _service
    with _service_lock:
        if _service is None:
            _service = GoogleDriveService(app_module)
        return _service


def install_google_drive_integration(app_module) -> None:
    """Attach optional Google Drive backup APIs without changing the core app."""
    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET
    original_post = handler_cls.do_POST

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/google-drive/"):
            try:
                service = get_service(app_module)
                if path == "/api/google-drive/status":
                    return self._json(service.status())
                if path == "/api/google-drive/settings":
                    return self._json(service.settings())
                if path == "/api/google-drive/backups":
                    return self._json({"rows": service.list_backups(), "status": service.status()})
                return self._json({"error": f"Ismeretlen Google Drive API végpont: {path}"}, 404)
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        return original_get(self)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/google-drive/"):
            try:
                service = get_service(app_module)
                if path == "/api/google-drive/settings":
                    data = self._read_json_body(max_bytes=100_000)
                    return self._json({"ok": True, "settings": service.save_settings(data)})
                if path == "/api/google-drive/connect":
                    return self._json({"ok": True, "job": service.start_connect()})
                if path == "/api/google-drive/disconnect":
                    return self._json({"ok": True, "status": service.disconnect()})
                if path == "/api/google-drive/upload-latest":
                    return self._json({"ok": True, "job": service.start_upload_latest()})
                if path == "/api/google-drive/restore":
                    data = self._read_json_body(max_bytes=100_000)
                    file_id = str(data.get("file_id") or "")
                    if not file_id:
                        raise ValueError("Nincs kiválasztva Google Drive backup.")
                    jid = self.jobs.create("google_drive_restore", "Visszaállítás Google Drive backupból")
                    self.jobs.start(jid, service.restore_job, self, file_id)
                    return self._json({"ok": True, "job": jid})
                return self._json({"error": f"Ismeretlen Google Drive API végpont: {path}"}, 404)
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)
        return original_post(self)

    handler_cls.do_GET = do_GET
    handler_cls.do_POST = do_POST

    def bootstrap() -> None:
        for _ in range(120):
            if getattr(handler_cls, "jobs", None) is not None:
                get_service(app_module)
                return
            time.sleep(0.25)

    threading.Thread(target=bootstrap, daemon=True, name="SleepMate-GoogleDrive-Bootstrap").start()
