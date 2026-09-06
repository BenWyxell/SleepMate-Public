param(
  [switch]$SkipTests,
  [switch]$SkipInstaller
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root

function Assert-LastExitCode([string]$Step) {
  if ($LASTEXITCODE -ne 0) {
    throw "$Step failed with exit code $LASTEXITCODE"
  }
}

function Normalize-VersionString($Value) {
  return ([string]$Value).Trim()
}

Write-Host '== SleepMate Windows program-tree build =='
Write-Host 'MSI packaging is performed in GitHub Actions after this verified program-tree build.'
if ($SkipInstaller) {
  Write-Host 'NOTE: -SkipInstaller is retained as a compatibility no-op; this script no longer builds an installer.'
}

python --version
Assert-LastExitCode 'python --version'

$AppVersion = (& python -c "from cpap.version import APP_VERSION; print(APP_VERSION)").Trim()
Assert-LastExitCode 'read APP_VERSION'
if ($AppVersion -notmatch '^\d+\.\d+\.\d+$') {
  throw "APP_VERSION must be semantic x.y.z, got: $AppVersion"
}
$VersionParts = $AppVersion.Split('.')
Write-Host "Release version source: cpap/version.py -> $AppVersion"

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$VersionInfoPath = Join-Path $Root 'build\windows\version_info.generated.txt'
$VersionInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($($VersionParts[0]), $($VersionParts[1]), $($VersionParts[2]), 0),
    prodvers=($($VersionParts[0]), $($VersionParts[1]), $($VersionParts[2]), 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'SleepMate'),
         StringStruct(u'FileDescription', u'SleepMate PAP therapy companion'),
         StringStruct(u'FileVersion', u'$AppVersion'),
         StringStruct(u'InternalName', u'SleepMate'),
         StringStruct(u'OriginalFilename', u'SleepMate.exe'),
         StringStruct(u'ProductName', u'SleepMate'),
         StringStruct(u'ProductVersion', u'$AppVersion')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"@
[IO.File]::WriteAllText($VersionInfoPath, $VersionInfo, $Utf8NoBom)

$GitCommit = $null
try {
  $GitCommit = (& git rev-parse HEAD).Trim()
  if ($LASTEXITCODE -ne 0) { $GitCommit = $null }
} catch {
  $GitCommit = $null
}

$BuildInfoObject = [ordered]@{
  version = $AppVersion
  build_id = "sleepmate-$AppVersion-windows"
  git_commit = $GitCommit
  channel = 'stable'
  packaging = 'windows-onedir-msi-ready'
  update_installer = 'windows-msiexec'
}
$BuildInfoJson = $BuildInfoObject | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $Root 'build_info.json'), $BuildInfoJson + [Environment]::NewLine, $Utf8NoBom)

$RuntimeLock = 'build\windows\requirements-runtime.lock'
$BuildLock = 'build\windows\requirements-build.lock'
if (-not (Test-Path $RuntimeLock)) { throw "Runtime dependency lock missing: $RuntimeLock" }
if (-not (Test-Path $BuildLock)) { throw "Build dependency lock missing: $BuildLock" }

python -m pip install --upgrade 'pip==26.2.1'
Assert-LastExitCode 'pip pin'
python -m pip install -r $RuntimeLock
Assert-LastExitCode 'locked runtime dependency installation'
python -m pip install -r $BuildLock
Assert-LastExitCode 'locked build dependency installation'

$BuildEnvironmentPath = Join-Path $Root 'build\windows\python-build-environment.txt'
$BuildEnvironment = @(& python -m pip freeze --all) | Sort-Object
Assert-LastExitCode 'pip freeze build environment'
[IO.File]::WriteAllLines($BuildEnvironmentPath, [string[]]$BuildEnvironment, $Utf8NoBom)
Write-Host "Recorded exact Python build environment: $BuildEnvironmentPath"

if (-not $SkipTests) {
  $pytestArgs = @('-m','pytest','-q','tests','--ignore=tests/test_v29.py')
  if (-not (Test-Path 'testdata\DATALOG')) {
    Write-Host 'Private EDF regression fixtures are not present; fixture-dependent tests are skipped in repository CI.'
    $fixtureTests = @(
      'tests/test_ai_v19.py',
      'tests/test_golden.py',
      'tests/test_report_pdf.py',
      'tests/test_services.py',
      'tests/test_verified_refresh_sync_fix.py'
    )
    foreach ($t in $fixtureTests) { $pytestArgs += "--ignore=$t" }
  }
  python @pytestArgs
  Assert-LastExitCode 'pytest'
}

python -m compileall -q app.py sleepmate_main.py sleepmate_tray.pyw cpap
Assert-LastExitCode 'compileall'

Remove-Item -Recurse -Force build\windows\pyi-build, dist, release -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force build\windows\pyi-build, release | Out-Null

pyinstaller --noconfirm --clean --distpath dist --workpath build\windows\pyi-build build\windows\SleepMate.spec
Assert-LastExitCode 'SleepMate PyInstaller build'

$BuiltExe = Get-Item 'dist\SleepMate\SleepMate.exe'
$BuiltExeProductVersion = Normalize-VersionString $BuiltExe.VersionInfo.ProductVersion
$BuiltExeFileVersion = Normalize-VersionString $BuiltExe.VersionInfo.FileVersion
if ($BuiltExeProductVersion -ne $AppVersion) {
  throw "SleepMate.exe ProductVersion mismatch: expected $AppVersion, got $BuiltExeProductVersion"
}
if ($BuiltExeFileVersion -notlike "$AppVersion*") {
  throw "SleepMate.exe FileVersion mismatch: expected $AppVersion.x, got $BuiltExeFileVersion"
}

# Exercise the ACTUAL frozen Windows tree with O2 enabled and BLE disabled. This
# catches the real regression class: backend starts generically, but O2 status or
# the runtime-injected O2 frontend is absent/hung. The MSI is built from this exact
# dist tree, and the later MSI smoke gate separately proves install/runtime health.
$O2SmokeState = Join-Path $env:TEMP "sleepmate-o2-smoke-$AppVersion"
Remove-Item $O2SmokeState -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $O2SmokeState | Out-Null
$O2SmokeConfig = [ordered]@{
  o2ring_enabled = $true
  o2ring_ble_enabled = $false
  o2ring_auto_connect = $false
  o2ring_auto_sync = $false
} | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $O2SmokeState 'config.json'), $O2SmokeConfig + [Environment]::NewLine, $Utf8NoBom)
$OldStateDir = $env:SLEEPMATE_STATE_DIR
$env:SLEEPMATE_STATE_DIR = $O2SmokeState
$O2SmokePort = 59919
$O2SmokeProc = $null
try {
  $O2SmokeProc = Start-Process -FilePath $BuiltExe.FullName -ArgumentList @('--backend','--host','127.0.0.1','--port',"$O2SmokePort",'--no-browser') -PassThru
  $VersionResponse = $null
  for ($i = 0; $i -lt 60; $i++) {
    if ($O2SmokeProc.HasExited) { throw "Frozen O2 acceptance backend exited early with code $($O2SmokeProc.ExitCode)." }
    try {
      $VersionResponse = Invoke-RestMethod -Uri "http://127.0.0.1:$O2SmokePort/api/version" -TimeoutSec 2
      break
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  if (-not $VersionResponse) { throw 'Frozen O2 acceptance backend did not become healthy in time.' }

  $O2Status = Invoke-RestMethod -Uri "http://127.0.0.1:$O2SmokePort/api/o2ring/status" -TimeoutSec 3
  if ($null -eq $O2Status.settings -or $O2Status.settings.o2ring_enabled -ne $true) {
    throw 'Frozen O2 acceptance: /api/o2ring/status did not preserve enabled O2 settings.'
  }
  if ($null -eq $O2Status.recordings) {
    throw 'Frozen O2 acceptance: /api/o2ring/status did not return recording count.'
  }

  $HomeResponse = Invoke-WebRequest -Uri "http://127.0.0.1:$O2SmokePort/" -TimeoutSec 3 -UseBasicParsing
  $HomeHtml = [string]$HomeResponse.Content
  if ($HomeHtml -notmatch '/frontend-v534\.js\?v=') {
    throw 'Frozen O2 acceptance: served desktop HTML lacks the canonical frontend-v534 asset.'
  }
  if ($HomeHtml -notmatch '/sleepmate-v530\.js\?v=') {
    throw 'Frozen O2 acceptance: served desktop HTML lacks the canonical O2 bootstrap asset.'
  }
  if ($HomeHtml -match 'o2ring-recovery-v5318\.js|sm-frontend-v534-inline') {
    throw 'Frozen O2 acceptance: a retired runtime injection/recovery layer is still served.'
  }
  Write-Host 'Frozen Windows O2 acceptance OK: status + canonical static O2 bootstrap.'
} finally {
  if ($O2SmokeProc -and -not $O2SmokeProc.HasExited) {
    Stop-Process -Id $O2SmokeProc.Id -Force -ErrorAction SilentlyContinue
    try { $O2SmokeProc.WaitForExit(10000) | Out-Null } catch {}
  }
  if ($null -eq $OldStateDir) { Remove-Item Env:SLEEPMATE_STATE_DIR -ErrorAction SilentlyContinue } else { $env:SLEEPMATE_STATE_DIR = $OldStateDir }
  Remove-Item $O2SmokeState -Recurse -Force -ErrorAction SilentlyContinue
}

Copy-Item SleepMate.ico dist\SleepMate\SleepMate.ico -Force
Copy-Item build_info.json dist\SleepMate\build_info.json -Force
Copy-Item build\windows\installed.marker dist\SleepMate\installed.marker -Force

$ReleaseNoticeFiles = @('LICENSE', 'THIRD_PARTY_NOTICES.md', 'PRIVACY.md')
foreach ($notice in $ReleaseNoticeFiles) {
  if (-not (Test-Path $notice)) { throw "Required release notice missing: $notice" }
  Copy-Item $notice (Join-Path 'dist\SleepMate' $notice) -Force
}

# Signing is performed only by the protected SignPath stage after this build and
# the MSI install/runtime/uninstall gates have succeeded.

python tools\build_binary_release.py --program-dir dist\SleepMate --out-dir release --min-version 4.2.2
Assert-LastExitCode 'binary release packaging'

$ExpectedZipName = "SleepMate_v${AppVersion}_windows_x64.zip"
$ExpectedZip = Join-Path 'release' $ExpectedZipName
if (-not (Test-Path $ExpectedZip)) {
  throw "Expected update ZIP missing: $ExpectedZip"
}

$UnexpectedZips = @(Get-ChildItem 'release\SleepMate_v*_windows_x64.zip' | Where-Object { $_.Name -ne $ExpectedZipName })
if ($UnexpectedZips.Count -gt 0) {
  throw "Unexpected differently-versioned update ZIP present: $($UnexpectedZips.Name -join ', ')"
}

$LegacyInstallerOutputs = @(Get-ChildItem 'release\SleepMate_Setup_v*.exe' -ErrorAction SilentlyContinue)
if ($LegacyInstallerOutputs.Count -gt 0) {
  throw "Legacy Inno Setup output must not be produced by the active build: $($LegacyInstallerOutputs.Name -join ', ')"
}

foreach ($notice in $ReleaseNoticeFiles) {
  if (-not (Test-Path (Join-Path 'dist\SleepMate' $notice))) {
    throw "Required release notice was not packaged: $notice"
  }
}

Write-Host "Program-tree release contract OK: app/EXE/portable ZIP = $AppVersion; the MSI job creates the only update manifest"
Write-Host 'MSI will be built from dist\SleepMate by the dedicated GitHub Actions MSI job.'
Write-Host 'Program-tree release artifacts:'
Get-ChildItem release | Format-Table Name,Length,LastWriteTime
