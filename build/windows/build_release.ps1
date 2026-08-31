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

Write-Host '== SleepMate Windows release build =='
python --version
Assert-LastExitCode 'python --version'

$AppVersion = (& python -c "from cpap.version import APP_VERSION; print(APP_VERSION)").Trim()
Assert-LastExitCode 'read APP_VERSION'
if ($AppVersion -notmatch '^\d+\.\d+\.\d+$') {
  throw "APP_VERSION must be semantic x.y.z, got: $AppVersion"
}
$VersionParts = $AppVersion.Split('.')
$AppVersionQuad = "$AppVersion.0"
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
  packaging = 'windows-onedir-ready'
}
$BuildInfoJson = $BuildInfoObject | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $Root 'build_info.json'), $BuildInfoJson + [Environment]::NewLine, $Utf8NoBom)

python -m pip install --upgrade pip
Assert-LastExitCode 'pip upgrade'
python -m pip install -r requirements.txt
Assert-LastExitCode 'runtime dependency installation'
python -m pip install -r build\windows\requirements-build.txt
Assert-LastExitCode 'build dependency installation'

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

python -m compileall -q app.py sleepmate_main.py sleepmate_tray.pyw update_worker.py cpap
Assert-LastExitCode 'compileall'

Remove-Item -Recurse -Force build\windows\pyi-build, build\windows\pyi-build-updater, build\windows\updater-dist, dist, release -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force build\windows\pyi-build, release | Out-Null

pyinstaller --noconfirm --clean --distpath dist --workpath build\windows\pyi-build build\windows\SleepMate.spec
Assert-LastExitCode 'SleepMate PyInstaller build'
pyinstaller --noconfirm --clean --distpath build\windows\updater-dist --workpath build\windows\pyi-build-updater build\windows\SleepMateUpdater.spec
Assert-LastExitCode 'SleepMateUpdater PyInstaller build'

$BuiltExe = Get-Item 'dist\SleepMate\SleepMate.exe'
$BuiltExeProductVersion = Normalize-VersionString $BuiltExe.VersionInfo.ProductVersion
$BuiltExeFileVersion = Normalize-VersionString $BuiltExe.VersionInfo.FileVersion
if ($BuiltExeProductVersion -ne $AppVersion) {
  throw "SleepMate.exe ProductVersion mismatch: expected $AppVersion, got $BuiltExeProductVersion"
}
if ($BuiltExeFileVersion -notlike "$AppVersion*") {
  throw "SleepMate.exe FileVersion mismatch: expected $AppVersion.x, got $BuiltExeFileVersion"
}

$BuiltUpdater = Get-Item 'build\windows\updater-dist\SleepMateUpdater.exe'
$BuiltUpdaterProductVersion = Normalize-VersionString $BuiltUpdater.VersionInfo.ProductVersion
$BuiltUpdaterFileVersion = Normalize-VersionString $BuiltUpdater.VersionInfo.FileVersion
if ($BuiltUpdaterProductVersion -ne $AppVersion) {
  throw "SleepMateUpdater.exe ProductVersion mismatch: expected $AppVersion, got $BuiltUpdaterProductVersion"
}
if ($BuiltUpdaterFileVersion -notlike "$AppVersion*") {
  throw "SleepMateUpdater.exe FileVersion mismatch: expected $AppVersion.x, got $BuiltUpdaterFileVersion"
}

Copy-Item $BuiltUpdater.FullName dist\SleepMate\SleepMateUpdater.exe -Force
Copy-Item SleepMate.ico dist\SleepMate\SleepMate.ico -Force
Copy-Item build_info.json dist\SleepMate\build_info.json -Force
Copy-Item build\windows\installed.marker dist\SleepMate\installed.marker -Force

# Optional Authenticode signing. The certificate is intentionally supplied only
# at build time (local env/GitHub Actions secret) and never stored in source.
if ($env:SLEEPMATE_SIGN_PFX -and (Test-Path $env:SLEEPMATE_SIGN_PFX) -and $env:SLEEPMATE_SIGN_PASSWORD) {
  $signtool = Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
  if (-not $signtool) { throw 'signtool.exe not found' }
  & $signtool.FullName sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /f $env:SLEEPMATE_SIGN_PFX /p $env:SLEEPMATE_SIGN_PASSWORD dist\SleepMate\SleepMate.exe
  Assert-LastExitCode 'SleepMate.exe signing'
  & $signtool.FullName sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /f $env:SLEEPMATE_SIGN_PFX /p $env:SLEEPMATE_SIGN_PASSWORD dist\SleepMate\SleepMateUpdater.exe
  Assert-LastExitCode 'SleepMateUpdater.exe signing'
}

python tools\build_binary_release.py --program-dir dist\SleepMate --out-dir release --min-version 4.2.2
Assert-LastExitCode 'binary release packaging'

$ManifestPath = 'release\sleepmate-update.json'
if (-not (Test-Path $ManifestPath)) { throw 'Update manifest was not created.' }
$Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$ManifestVersion = Normalize-VersionString $Manifest.version
if ($ManifestVersion -ne $AppVersion) {
  throw "Update manifest version mismatch: expected $AppVersion, got $ManifestVersion"
}
$ExpectedZipName = "SleepMate_v${AppVersion}_windows_x64.zip"
$ExpectedZip = Join-Path 'release' $ExpectedZipName
if (-not (Test-Path $ExpectedZip)) {
  throw "Expected update ZIP missing: $ExpectedZip"
}
$ManifestAsset = Normalize-VersionString $Manifest.asset
if ($ManifestAsset -ne $ExpectedZipName) {
  throw "Update manifest asset mismatch: expected $ExpectedZipName, got $ManifestAsset"
}
$UnexpectedZips = @(Get-ChildItem 'release\SleepMate_v*_windows_x64.zip' | Where-Object { $_.Name -ne $ExpectedZipName })
if ($UnexpectedZips.Count -gt 0) {
  throw "Unexpected differently-versioned update ZIP present: $($UnexpectedZips.Name -join ', ')"
}

if (-not $SkipInstaller) {
  $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if (-not $iscc) {
    $candidate = 'C:\Program Files\Inno Setup 7\ISCC.exe'
    if (Test-Path $candidate) { $iscc = Get-Item $candidate }
  }
  if (-not $iscc) { throw 'Inno Setup 7 (ISCC.exe) not found.' }

  & $iscc.Source "/DMyAppVersion=$AppVersion" "/DMyAppVersionQuad=$AppVersionQuad" build\windows\installer\SleepMate.iss
  Assert-LastExitCode 'Inno Setup compilation'

  $ExpectedSetupName = "SleepMate_Setup_v${AppVersion}.exe"
  $ExpectedSetupPath = Join-Path 'release' $ExpectedSetupName
  if (-not (Test-Path $ExpectedSetupPath)) {
    throw "Expected installer missing: $ExpectedSetupPath"
  }
  $UnexpectedSetups = @(Get-ChildItem 'release\SleepMate_Setup_v*.exe' | Where-Object { $_.Name -ne $ExpectedSetupName })
  if ($UnexpectedSetups.Count -gt 0) {
    throw "Unexpected differently-versioned installer present: $($UnexpectedSetups.Name -join ', ')"
  }

  $setup = Get-Item $ExpectedSetupPath
  $SetupProductVersion = Normalize-VersionString $setup.VersionInfo.ProductVersion
  $SetupFileVersion = Normalize-VersionString $setup.VersionInfo.FileVersion
  if ($SetupProductVersion -ne $AppVersion) {
    throw "Installer ProductVersion mismatch: expected $AppVersion, got $SetupProductVersion"
  }
  if ($SetupFileVersion -notlike "$AppVersion*") {
    throw "Installer FileVersion mismatch: expected $AppVersion.x, got $SetupFileVersion"
  }

  if ($env:SLEEPMATE_SIGN_PFX -and (Test-Path $env:SLEEPMATE_SIGN_PFX) -and $env:SLEEPMATE_SIGN_PASSWORD) {
    $signtool = Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe' | Sort-Object FullName -Descending | Select-Object -First 1
    & $signtool.FullName sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /f $env:SLEEPMATE_SIGN_PFX /p $env:SLEEPMATE_SIGN_PASSWORD $setup.FullName
    Assert-LastExitCode 'installer signing'
  }
}

Write-Host "Release version contract OK: app/EXE/updater/manifest/ZIP/installer = $AppVersion"
Write-Host 'Release artifacts:'
Get-ChildItem release | Format-Table Name,Length,LastWriteTime
