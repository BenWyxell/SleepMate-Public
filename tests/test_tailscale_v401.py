from pathlib import Path
import sys
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from cpap.remote_access import RemoteAccessManager

class Fake(RemoteAccessManager):
    @staticmethod
    def _which(names): return 'tailscale.exe'
    def _run(self,args,timeout=15):
        cmd=' '.join(args[1:])
        if cmd=='status --json':
            return 0,'{"Self":{"Online":true,"DNSName":"sleep-pc.tail123.ts.net."},"CurrentTailnet":{"Name":"tail123"}}',''
        if cmd=='serve status --json':
            return 0,'{"TCP":{"443":{"HTTPS":true}},"Web":{"sleep-pc.tail123.ts.net:443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:8895"}}}}}',''
        if cmd=='serve status':
            return 0,'Available within your tailnet:\nhttps://sleep-pc.tail123.ts.net\n|-- / proxy http://127.0.0.1:8895',''
        return 0,'',''

m=Fake(BASE,8895)
s=m.tailscale_status()
assert s['installed'] and s['online'] and s['serve_active']
assert s['url']=='https://sleep-pc.tail123.ts.net', s

# Newer Services wrapper must also be recognized.
obj={"Services":{"svc:x":{"TCP":{"443":{"HTTPS":True}},"Web":{"sleep-pc.tail123.ts.net:443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:8895"}}}}}}}
a,h=m._tailscale_proxy_from_json(obj,'127.0.0.1:8895')
assert a and h=='sleep-pc.tail123.ts.net'
print('PASS: v4.0.1 robust Tailscale Serve JSON status + URL detection')
