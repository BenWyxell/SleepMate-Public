@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo SleepMate port ellenőrzés
echo ==========================
python -c "import json; from sleepmate_tray import load_config,candidate_ports,diagnose_port; c=load_config(); print('Mód:', 'Automatikus' if c.get('port_mode','auto')=='auto' else 'Fix'); print('Elsődleges port:', c.get('port',8895)); print(); [(lambda d: print(str(p)+': '+('SleepMate fut' if d.get('sleepmate') else ('FOGLALT' if d.get('open') else 'szabad'))))(diagnose_port(p)) for p in candidate_ports(c)[:12]]"
echo.
pause
