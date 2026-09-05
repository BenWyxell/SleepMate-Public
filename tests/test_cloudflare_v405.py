from pathlib import Path
import tempfile, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpap.remote_access import RemoteAccessManager
from unittest.mock import patch

SC_OUTPUT = '''SERVICE_NAME: cloudflared
        TYPE               : 10  WIN32_OWN_PROCESS
        STATE              : 4  RUNNING
                                (STOPPABLE, NOT_PAUSABLE, ACCEPTS_SHUTDOWN)
        WIN32_EXIT_CODE    : 0  (0x0)
'''
with tempfile.TemporaryDirectory() as td:
    rm=RemoteAccessManager(Path(td), 8895)
    rm._which=lambda names: 'cloudflared.exe'
    def fake_run(args, timeout=10):
        if args[:3]==['sc','query','cloudflared']:
            return 0, SC_OUTPUT, ''
        if args and args[0]=='tasklist':
            return 0, '', ''
        if '--version' in args:
            return 0, 'cloudflared version 2026.8.2', ''
        return 1, '', ''
    rm._run=fake_run
    with patch('cpap.remote_access.os.name','nt'):
        st=rm.cloudflare_status('sleepmate.szemedfenye.hu')
        assert st['service_running'] is True
        assert st['running'] is True
        assert st['mode']=='windows-service'
        assert st['token_required'] is False
print('PASS: v4.0.5 realistic sc query output')
