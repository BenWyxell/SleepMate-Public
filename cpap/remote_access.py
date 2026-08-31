from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .patient_store import LocalProtector

CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


class RemoteSecretStore:
    """DPAPI-protected secrets for remote-access helpers."""
    def __init__(self, base: Path):
        self.private = base / 'private'
        self.private.mkdir(parents=True, exist_ok=True)
        self.path = self.private / 'remote_secrets.bin'
        self.protector = LocalProtector(self.private)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            raw = self.protector.unprotect(self.path.read_bytes())
            obj = json.loads(raw.decode('utf-8'))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _write(self, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.path.write_bytes(self.protector.protect(raw))

    @staticmethod
    def mask(value: str) -> str:
        value = (value or '').strip()
        if not value:
            return ''
        if len(value) <= 10:
            return '••••••••'
        return f'{value[:4]}••••••••{value[-4:]}'

    def token(self) -> str:
        return str(self._read().get('cloudflare_token') or '').strip()

    def save_token(self, value: str | None = None, clear: bool = False) -> None:
        obj = self._read()
        if clear:
            obj.pop('cloudflare_token', None)
        elif value and value.strip():
            obj['cloudflare_token'] = value.strip()
        self._write(obj)

    def status(self) -> dict[str, Any]:
        token = self.token()
        return {
            'configured': bool(token),
            'token_hint': self.mask(token),
            'protection': self.protector.mode,
        }


class RemoteAccessManager:
    """Local Tailscale Serve and Cloudflare Tunnel helper.

    The SleepMate backend itself stays bound to 127.0.0.1. Both remote systems
    reverse-proxy that local-only service, so no LAN/inbound port exposure is
    required.
    """
    def __init__(self, base: Path, port: int, log=None):
        self.base = base
        self.port = int(port)
        self.log = log
        self.secrets = RemoteSecretStore(base)
        self._lock = threading.RLock()
        self.cloudflare_proc: subprocess.Popen | None = None
        self.pid_file = base / 'private' / 'cloudflared_sleepmate.pid'

    def _append(self, level: str, message: str, details: dict | None = None):
        try:
            if self.log:
                self.log.append(level, 'remote', message, details or {})
        except Exception:
            pass

    def _run(self, args: list[str], timeout: float = 15) -> tuple[int, str, str]:
        try:
            p = subprocess.run(args, cwd=str(self.base), capture_output=True, text=True,
                               timeout=timeout, creationflags=CREATE_NO_WINDOW)
            return p.returncode, (p.stdout or '').strip(), (p.stderr or '').strip()
        except FileNotFoundError:
            return 127, '', 'A parancs nem található.'
        except subprocess.TimeoutExpired as exc:
            return 124, (exc.stdout or '') if isinstance(exc.stdout, str) else '', 'Időtúllépés.'
        except Exception as exc:
            return 1, '', str(exc)

    @staticmethod
    def _which(names: tuple[str, ...]) -> str | None:
        for name in names:
            p = shutil.which(name)
            if p:
                return p
        return None

    @staticmethod
    def _tailscale_proxy_from_json(obj: Any, proxy_target: str) -> tuple[bool, str]:
        """Find the SleepMate proxy and its HTTPS hostname in Serve status JSON.

        Tailscale has changed the human-readable ``serve status`` output multiple
        times. The JSON shape can also be wrapped in ``Services`` on newer
        clients, therefore this walks the object recursively instead of assuming
        a single schema.
        """
        wanted = {proxy_target, f'http://{proxy_target}', f'http://{proxy_target}/'}
        active = False
        hostname = ''

        def walk(node: Any, key_path: list[str]):
            nonlocal active, hostname
            if isinstance(node, dict):
                proxy = node.get('Proxy')
                if isinstance(proxy, str):
                    normalized = proxy.rstrip('/')
                    if normalized in {x.rstrip('/') for x in wanted}:
                        active = True
                        for key in reversed(key_path):
                            # Web map keys look like node.tailnet.ts.net:443.
                            m = re.match(r'([^/\s:]+(?:\.[^/\s:]+)+):443$', key)
                            if m and '.ts.net' in m.group(1):
                                hostname = m.group(1)
                                break
                for k, v in node.items():
                    walk(v, key_path + [str(k)])
            elif isinstance(node, list):
                for item in node:
                    walk(item, key_path)

        walk(obj, [])
        return active, hostname

    @staticmethod
    def _first_setup_url(text: str) -> str:
        # If Serve needs one-time HTTPS/tailnet consent, Tailscale prints an URL.
        urls = re.findall(r'https://[^\s|<>]+', text or '')
        for url in urls:
            clean = url.rstrip(').,;')
            if 'tailscale.com' in clean and '.ts.net' not in clean:
                return clean
        return ''

    def tailscale_status(self) -> dict[str, Any]:
        exe = self._which(('tailscale.exe', 'tailscale'))
        if not exe:
            return {'installed': False, 'online': False, 'serve_active': False, 'url': '', 'message': 'A Tailscale nincs telepítve.'}

        rc, out, err = self._run([exe, 'status', '--json'], 8)
        online = False
        dns = ''
        tailnet = ''
        status_message = ''
        if rc == 0:
            try:
                obj = json.loads(out)
                self_row = obj.get('Self') or {}
                online = bool(self_row.get('Online', True))
                dns = str(self_row.get('DNSName') or '').rstrip('.')
                tailnet = str((obj.get('CurrentTailnet') or {}).get('Name') or '')
            except Exception as exc:
                online = True
                status_message = f'Tailscale státusz feldolgozási hiba: {exc}'
        else:
            status_message = err or out or 'A Tailscale állapota nem kérdezhető le.'

        proxy_target = f'127.0.0.1:{self.port}'
        active = False
        serve_host = ''
        setup_url = ''
        serve_message = ''

        # Prefer machine-readable Serve status. Newer clients may wrap the same
        # information in a Services object; the recursive parser handles both.
        rcj, jout, jerr = self._run([exe, 'serve', 'status', '--json'], 8)
        if rcj == 0 and jout.strip():
            try:
                serve_obj = json.loads(jout)
                active, serve_host = self._tailscale_proxy_from_json(serve_obj, proxy_target)
            except Exception as exc:
                serve_message = f'Serve JSON feldolgozási hiba: {exc}'
        elif rcj != 0:
            serve_message = jerr or jout

        # Human-readable fallback, also useful for older Tailscale versions.
        rct, tout, terr = self._run([exe, 'serve', 'status'], 8)
        combined = '\n'.join(x for x in (tout, terr, jout if rcj != 0 else '', jerr) if x)
        if not active and proxy_target in combined:
            active = True
        urls = re.findall(r'https://[^\s|<>]+', combined)
        serve_url = ''
        for candidate in urls:
            clean = candidate.rstrip('/).,;')
            if '.ts.net' in clean:
                serve_url = clean.rstrip('/')
                break
        setup_url = self._first_setup_url(combined)

        host = serve_host or dns
        url = serve_url or (f'https://{host}' if active and host else '')
        message = serve_message or status_message
        if not message and online and not active:
            message = 'A Tailscale kapcsolódik, de a Serve még nem aktív.'
        if active and not url:
            message = 'A Serve aktívnak látszik, de a Tailscale HTTPS neve még nem olvasható ki. Frissítsd az állapotot pár másodperc múlva.'

        return {
            'installed': True, 'online': online, 'serve_active': active, 'url': url,
            'dns_name': dns, 'tailnet': tailnet, 'setup_url': setup_url,
            'message': (message or '')[:1000],
        }

    def tailscale_enable(self) -> dict[str, Any]:
        exe = self._which(('tailscale.exe', 'tailscale'))
        if not exe:
            raise FileNotFoundError('A Tailscale nincs telepítve ezen a gépen.')
        target = f'http://127.0.0.1:{self.port}'
        rc, out, err = self._run([exe, 'serve', '--bg', '--yes', target], 30)
        if rc != 0:
            details = '\n'.join(x for x in (err, out) if x).strip()
            raise RuntimeError(details or 'A Tailscale Serve bekapcsolása nem sikerült.')
        self._append('INFO', 'Tailscale Serve bekapcsolva.', {'port': self.port})

        # Serve configuration can take a short moment to appear in status. Do
        # not return an empty address just because the first status read is stale.
        last = self.tailscale_status()
        for _ in range(8):
            if last.get('serve_active') and last.get('url'):
                break
            time.sleep(0.5)
            last = self.tailscale_status()
        return last

    def tailscale_disable(self) -> dict[str, Any]:
        exe = self._which(('tailscale.exe', 'tailscale'))
        if not exe:
            raise FileNotFoundError('A Tailscale nincs telepítve ezen a gépen.')
        # Disable only the default HTTPS listener used by SleepMate rather than reset all Serve config.
        rc, out, err = self._run([exe, 'serve', '--https=443', 'off'], 15)
        if rc != 0:
            raise RuntimeError(err or out or 'A Tailscale Serve kikapcsolása nem sikerült.')
        self._append('INFO', 'Tailscale Serve kikapcsolva.', {})
        return self.tailscale_status()

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _remember_pid(self, pid: int | None):
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        if pid:
            self.pid_file.write_text(str(pid), encoding='ascii')
        else:
            try: self.pid_file.unlink()
            except FileNotFoundError: pass

    def _known_pid(self) -> int | None:
        if self.cloudflare_proc and self.cloudflare_proc.poll() is None:
            return int(self.cloudflare_proc.pid)
        try:
            pid = int(self.pid_file.read_text(encoding='ascii').strip())
            return pid if self._pid_alive(pid) else None
        except Exception:
            return None

    def _cloudflared_service_status(self) -> dict[str, Any]:
        """Detect the standard Windows cloudflared service installed by Cloudflare.

        ``cloudflared service install <TOKEN>`` installs a Windows service. When
        that service already owns the tunnel, SleepMate must not require or store
        another tunnel token just to show the status/open the hostname.
        """
        if os.name != 'nt':
            return {'installed': False, 'running': False, 'state': '', 'name': ''}
        # The official installer uses the service name ``cloudflared``.
        rc, out, err = self._run(['sc', 'query', 'cloudflared'], 6)
        text = '\n'.join(x for x in (out, err) if x)
        if rc != 0:
            return {'installed': False, 'running': False, 'state': '', 'name': ''}
        # `sc query` contains several numeric fields. The first is normally
        # TYPE (for example `TYPE : 10 WIN32_OWN_PROCESS`), not SERVICE_STATE.
        # Accept only a valid Windows service-state code/token pair.
        known_states = {
            1: 'STOPPED', 2: 'START_PENDING', 3: 'STOP_PENDING',
            4: 'RUNNING', 5: 'CONTINUE_PENDING', 6: 'PAUSE_PENDING', 7: 'PAUSED',
        }
        code = 0
        state = 'UNKNOWN'
        for raw_code, raw_state in re.findall(r':\s*(\d+)\s+([A-Z_]+)', text, re.I):
            candidate = int(raw_code)
            token = raw_state.upper()
            if candidate in known_states and token == known_states[candidate]:
                code, state = candidate, token
                break
        return {'installed': True, 'running': code == 4, 'state': state, 'name': 'cloudflared'}

    def _cloudflared_process_running(self) -> bool:
        if os.name != 'nt':
            return False
        rc, out, _ = self._run(['tasklist', '/FI', 'IMAGENAME eq cloudflared.exe', '/FO', 'CSV', '/NH'], 6)
        if rc != 0:
            return False
        return 'cloudflared.exe' in (out or '').lower()

    def cloudflare_status(self, hostname: str = '') -> dict[str, Any]:
        exe = self._which(('cloudflared.exe', 'cloudflared'))
        secret = self.secrets.status()
        managed_pid = self._known_pid()
        service = self._cloudflared_service_status()
        process_seen = self._cloudflared_process_running()
        external_running = bool(service.get('running') or (process_seen and not managed_pid))
        running = bool(managed_pid or external_running)
        version = ''
        if exe:
            rc, out, _ = self._run([exe, '--version'], 6)
            if rc == 0:
                version = out.splitlines()[0] if out else ''
        host = (hostname or '').strip().lower()
        if managed_pid:
            mode = 'sleepmate-managed'
            mode_label = 'SleepMate által indítva'
        elif service.get('running'):
            mode = 'windows-service'
            mode_label = 'Windows szolgáltatás'
        elif process_seen:
            mode = 'external-process'
            mode_label = 'Külső cloudflared folyamat'
        elif service.get('installed'):
            mode = 'windows-service-stopped'
            mode_label = 'Windows szolgáltatás (leállítva)'
        else:
            mode = 'not-running'
            mode_label = 'Nincs futó tunnel'
        token_required = not external_running
        message = ''
        if service.get('running'):
            message = 'A Cloudflare Tunnel Windows-szolgáltatásként fut. A SleepMate-nek ehhez nem kell Tunnel token.'
        elif external_running:
            message = 'A cloudflared már külső folyamatként fut. A SleepMate nem kéri újra a Tunnel tokent.'
        elif service.get('installed') and not service.get('running'):
            message = 'A cloudflared Windows-szolgáltatás telepítve van, de jelenleg nem fut.'
        elif secret['configured']:
            message = 'A SleepMate saját indításához van mentett Tunnel token.'
        else:
            message = 'Nincs futó külső tunnel. Token csak akkor kell, ha a SleepMate-tel akarod elindítani a cloudflared folyamatot.'
        return {
            'installed': bool(exe) or bool(service.get('installed')),
            'version': version,
            'token_configured': secret['configured'], 'token_hint': secret['token_hint'],
            'token_required': token_required,
            'running': running,
            'managed_running': bool(managed_pid),
            'external_running': external_running,
            'service_installed': bool(service.get('installed')),
            'service_running': bool(service.get('running')),
            'service_state': str(service.get('state') or ''),
            'mode': mode, 'mode_label': mode_label,
            'pid': managed_pid,
            'hostname': host, 'url': f'https://{host}' if host else '',
            'message': message,
        }

    def save_cloudflare_token(self, token: str = '', clear: bool = False):
        self.secrets.save_token(token, clear)
        return self.secrets.status()

    def cloudflare_start(self, hostname: str = '') -> dict[str, Any]:
        with self._lock:
            exe = self._which(('cloudflared.exe', 'cloudflared'))
            if not exe:
                raise FileNotFoundError('A cloudflared nincs telepítve ezen a gépen.')
            status = self.cloudflare_status(hostname)
            # If cloudflared is already managed by the official Windows service
            # (or another external process), do not start a duplicate tunnel and
            # do not require the token again.
            if status.get('external_running'):
                self._append('INFO', 'Meglévő Cloudflare Tunnel felismerve; nincs szükség tokenre.', {'mode': status.get('mode'), 'hostname': hostname})
                return status
            token = self.secrets.token()
            if not token:
                raise ValueError('A Cloudflare Tunnel nem fut külső szolgáltatásként. Token csak akkor szükséges, ha a SleepMate-tel szeretnéd elindítani.')
            current = self._known_pid()
            if current:
                return self.cloudflare_status(hostname)
            flags = CREATE_NO_WINDOW
            child_env = os.environ.copy()
            # cloudflared supports TUNNEL_TOKEN; keeping the token out of the
            # command line avoids exposing it in normal process listings.
            child_env['TUNNEL_TOKEN'] = token
            self.cloudflare_proc = subprocess.Popen(
                [exe, 'tunnel', '--no-autoupdate', 'run'],
                cwd=str(self.base), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=flags, env=child_env,
            )
            self._remember_pid(self.cloudflare_proc.pid)
            self._append('INFO', 'Cloudflare Tunnel elindítva.', {'hostname': hostname, 'pid': self.cloudflare_proc.pid})
            return self.cloudflare_status(hostname)

    def cloudflare_stop(self, hostname: str = '') -> dict[str, Any]:
        with self._lock:
            pid = self._known_pid()
            if pid:
                if self.cloudflare_proc and self.cloudflare_proc.poll() is None:
                    try:
                        self.cloudflare_proc.terminate(); self.cloudflare_proc.wait(timeout=5)
                    except Exception:
                        try: self.cloudflare_proc.kill()
                        except Exception: pass
                elif os.name == 'nt':
                    self._run(['taskkill', '/PID', str(pid), '/T', '/F'], 8)
                else:
                    try: os.kill(pid, signal.SIGTERM)
                    except Exception: pass
            self.cloudflare_proc = None
            self._remember_pid(None)
            self._append('INFO', 'Cloudflare Tunnel leállítva.', {'hostname': hostname})
            return self.cloudflare_status(hostname)


    def _winget_install(self, package_id: str, label: str, manual_url: str) -> dict[str, Any]:
        if os.name != 'nt':
            raise RuntimeError(f'{label} automatikus telepítése csak Windows alatt érhető el.')
        winget = self._which(('winget.exe', 'winget'))
        if not winget:
            return {
                'ok': False, 'installed': False, 'manual_required': True,
                'message': 'A Windows Package Manager (winget) nem található. Nyisd meg a hivatalos letöltési oldalt.',
                'url': manual_url,
            }
        self._append('INFO', f'{label} automatikus telepítése elindult.', {'package_id': package_id})
        args = [winget, 'install', '--id', package_id, '--exact', '--silent',
                '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity']
        rc, out, err = self._run(args, 300)
        text = '\n'.join(x for x in (out, err) if x).strip()
        # winget may return an "already installed" success-ish code/message.
        success = rc == 0 or 'already installed' in text.lower() or 'már telepítve' in text.lower()
        if not success:
            self._append('WARN', f'{label} automatikus telepítése sikertelen.', {'package_id': package_id, 'code': rc, 'message': text[:1200]})
            return {'ok': False, 'installed': False, 'manual_required': True, 'code': rc,
                    'message': text or f'{label} telepítése nem sikerült.', 'url': manual_url}
        self._append('INFO', f'{label} automatikus telepítése befejeződött.', {'package_id': package_id})
        return {'ok': True, 'installed': True, 'manual_required': False, 'message': f'{label} telepítése kész.'}

    def install_tailscale(self) -> dict[str, Any]:
        current = self.tailscale_status()
        if current.get('installed'):
            return {'ok': True, 'installed': True, 'already_installed': True, 'status': current, 'message': 'A Tailscale már telepítve van.'}
        result = self._winget_install('Tailscale.Tailscale', 'Tailscale', 'https://tailscale.com/download')
        result['status'] = self.tailscale_status()
        result['installed'] = bool(result['status'].get('installed'))
        return result

    def install_cloudflared(self) -> dict[str, Any]:
        current = self.cloudflare_status('')
        if current.get('installed'):
            return {'ok': True, 'installed': True, 'already_installed': True, 'status': current, 'message': 'A cloudflared már telepítve van.'}
        result = self._winget_install('Cloudflare.cloudflared', 'cloudflared', 'https://developers.cloudflare.com/tunnel/downloads/')
        result['status'] = self.cloudflare_status('')
        result['installed'] = bool(result['status'].get('installed'))
        return result

    def stop_managed_processes(self):
        # Only stop the cloudflared instance that SleepMate itself launched.
        if self.cloudflare_proc and self.cloudflare_proc.poll() is None:
            try: self.cloudflare_proc.terminate()
            except Exception: pass
            self.cloudflare_proc = None
            self._remember_pid(None)
