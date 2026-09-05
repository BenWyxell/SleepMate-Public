from __future__ import annotations
import json, subprocess, sys, tempfile, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKER=ROOT/'update_worker.py'
sys.path.insert(0, str(ROOT))
from update_worker import wait_for_exit


def make_base(td: Path, old_text: str):
    app=td/'app'; app.mkdir()
    (app/'private'/'update_runtime').mkdir(parents=True)
    (app/'app.py').write_text(old_text,encoding='utf-8')
    (app/'SleepMate.vbs').write_text('Option Explicit\n',encoding='utf-8')
    rb=td/'rollback'; rb.mkdir(); (rb/'app.py').write_text(old_text,encoding='utf-8'); (rb/'SleepMate.vbs').write_text('Option Explicit\n',encoding='utf-8')
    return app,rb

with tempfile.TemporaryDirectory() as raw:
    td=Path(raw); app,rb=make_base(td,"from pathlib import Path\nPath(__file__).with_name('restored.flag').write_text('old')\n")
    pkg=td/'pkg'; pkg.mkdir()
    (pkg/'app.py').write_text("import json,os,time\nfrom pathlib import Path\np=Path(__file__).parent/'private'/'update_runtime'/'update_boot_ok.json'\np.parent.mkdir(parents=True,exist_ok=True)\np.write_text(json.dumps({'version':'4.2.1','pid':os.getpid()}))\ntime.sleep(1)\n",encoding='utf-8')
    (pkg/'SleepMate.vbs').write_text('Option Explicit\n',encoding='utf-8')
    marker=app/'private'/'update_runtime'/'update_boot_ok.json'; log=app/'private'/'update_runtime'/'worker.log'
    plan={'format':'sleepmate-update-plan','from_version':'4.2.0','to_version':'4.2.1','app_dir':str(app),'package_dir':str(pkg),'rollback_dir':str(rb),'health_marker':str(marker),'old_pid':0,'port':19991,'tray_pid':0,'launch_vbs':str(app/'SleepMate.vbs'),'worker_log':str(log),'timeout_seconds':5}
    pp=td/'plan.json'; pp.write_text(json.dumps(plan),encoding='utf-8')
    rc=subprocess.run([sys.executable,str(WORKER),str(pp)],timeout=15).returncode
    assert rc==0, (rc,log.read_text(encoding='utf-8') if log.exists() else '')
    assert '4.2.1' in (app/'app.py').read_text(encoding='utf-8')
    health=json.loads(marker.read_text(encoding='utf-8'))
    assert wait_for_exit(int(health.get('pid') or 0), 5), 'new test backend did not exit'

with tempfile.TemporaryDirectory() as raw:
    td=Path(raw); old="import os\nfrom pathlib import import Path\n"
    old="import os\nfrom pathlib import Path\nPath(__file__).with_name('restored.flag').write_text(str(os.getpid()))\n"
    app,rb=make_base(td,old)
    pkg=td/'pkg'; pkg.mkdir(); (pkg/'app.py').write_text('raise SystemExit(1)\n',encoding='utf-8'); (pkg/'SleepMate.vbs').write_text('Option Explicit\n',encoding='utf-8')
    marker=app/'private'/'update_runtime'/'update_boot_ok.json'; log=app/'private'/'update_runtime'/'worker.log'
    plan={'format':'sleepmate-update-plan','from_version':'4.2.0','to_version':'9.9.9','app_dir':str(app),'package_dir':str(pkg),'rollback_dir':str(rb),'health_marker':str(marker),'old_pid':0,'port':19992,'tray_pid':0,'launch_vbs':str(app/'SleepMate.vbs'),'worker_log':str(log),'timeout_seconds':5}
    pp=td/'plan.json'; pp.write_text(json.dumps(plan),encoding='utf-8')
    rc=subprocess.run([sys.executable,str(WORKER),str(pp)],timeout=15).returncode
    assert rc==6, (rc,log.read_text(encoding='utf-8') if log.exists() else '')
    assert (app/'app.py').read_text(encoding='utf-8')==old
    for _ in range(20):
        if (app/'restored.flag').exists():break
        time.sleep(.1)
    assert (app/'restored.flag').exists()
    restored_pid=int((app/'restored.flag').read_text().strip())
    assert wait_for_exit(restored_pid, 5), 'restored test backend did not exit'

print('PASS: v4.2.0 external updater boots new build and automatically restores previous program tree on failed health check')