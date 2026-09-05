from pathlib import Path
import tempfile
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpap.remote_access import RemoteAccessManager

with tempfile.TemporaryDirectory() as td:
    rm=RemoteAccessManager(Path(td),8895)
    def fake_run(args, timeout=15):
        if args[:3]==['sc','query','cloudflared']:
            return 0, 'SERVICE_NAME: cloudflared\n        STATE              : 4  RUNNING', ''
        if args and args[0]=='tasklist':
            return 0, '"cloudflared.exe","1234","Services","0","12,000 K"', ''
        if '--version' in args:
            return 0, 'cloudflared version 2026.8.0', ''
        return 0,'',''
    rm._run=fake_run
    rm._which=lambda names: 'cloudflared.exe'
    with patch('cpap.remote_access.os.name','nt'):
        st=rm.cloudflare_status('sleepmate.example.hu')
        assert st['running'] is True
        assert st['external_running'] is True
        assert st['service_running'] is True
        assert st['token_required'] is False
        assert st['mode']=='windows-service'
        assert st['url']=='https://sleepmate.example.hu'
        started=rm.cloudflare_start('sleepmate.example.hu')
        assert started['external_running'] is True
print('PASS: v4.0.4 existing cloudflared service works without SleepMate tunnel token')
