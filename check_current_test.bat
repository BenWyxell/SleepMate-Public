@echo off
cd /d "%~dp0"
echo === OSCAR golden teszt ===
python tests\test_golden.py
if errorlevel 1 goto :fail
echo.
echo === Kezelt szemely / backup teszt ===
python tests\test_patient_backup.py
if errorlevel 1 goto :fail
echo.
echo === Felszereles kompatibilitasi katalogus teszt ===
python tests\test_equipment_catalog.py
if errorlevel 1 goto :fail
echo.
echo === Import / teljes backup / automata utemezes teszt ===
python tests\test_services.py
if errorlevel 1 goto :fail
echo.
echo === v1.7 UI biztonsagi teszt ===
python tests\test_ui_v17.py
if errorlevel 1 goto :fail
echo.
echo === v1.9 elo AI + elozenyek + adatvedelem teszt ===
python tests\test_ai_v19.py
if errorlevel 1 goto :fail
echo.
echo === v2.9 Windows tray + AI cim/datum + naplourites teszt ===
python tests\test_v29.py
if errorlevel 1 goto :fail
echo.
echo === v3.4 kompakt premium PDF + eltero temak teszt ===
python tests\test_report_pdf.py
if errorlevel 1 goto :fail
echo.
echo === v3.4 tavoli eleres + PWA + Szekciok action teszt ===
python tests\test_remote_pwa_v34.py
if errorlevel 1 goto :fail
echo.
echo === v4.0 layout + PDF + ResMed SW teszt ===
python tests\test_v40_layout.py
if errorlevel 1 goto :fail
echo.
echo === v4.0.1 Tailscale Serve status teszt ===
python tests\test_tailscale_v401.py
if errorlevel 1 goto :fail
echo.
echo === v4.0.2 Tailscale auto-helyreallitas + QR teszt ===
python tests\test_tailscale_v402.py
if errorlevel 1 goto :fail
echo.
echo.
echo === Windows UTF-8 hatterszolgaltatas inditasi teszt ===
python tests\test_windows_utf8_startup.py
if errorlevel 1 goto :fail
echo.
echo MINDEN TESZT PASS.
pause
exit /b 0
:fail
echo.
echo TESZT HIBA.
pause
exit /b 1
