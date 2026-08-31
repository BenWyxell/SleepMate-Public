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
Write-Host 'MSI packaging is performed in GitHub Actions on a GitHub-hosted Ubuntu runner using GNOME msitools/wixl.'
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
}
$BuildInfoJson = $BuildInfoObject | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $Root 'build_info.json'), $BuildInfoJson + [Environment]::NewLine, $Utf8NoBom)

$RuntimeLock = 'build\windows\requirements-runtime.lock'
$BuildLock = 'build\windows\requirements-build.lock'
if (-not (Test-Path $RuntimeLock)) { throw "Runtime dependency lock missing: $RuntimeLock" }
if (-not (Test-Path $BuildLock)) { throw "Build dependency lock missing: $BuildLock" }

# Keep the public release resolver deterministic. The exact versions below were
# captured from the successful public v5.2.16 GitHub-hosted build.
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

# License/privacy material is part of both the portable program tree and the MSI
# because the MSI is generated from this exact dist\SleepMate directory.
$ReleaseNoticeFiles = @('LICENSE', 'THIRD_PARTY_NOTICES.md', 'PRIVACY.md')
foreach ($notice in $ReleaseNoticeFiles) {
  if (-not (Test-Path $notice)) { throw "Required release notice missing: $notice" }
  Copy-Item $notice (Join-Path 'dist\SleepMate' $notice) -Force
}

# Production signing is intentionally NOT performed here.
# Official signing will be requested from SignPath by the trusted GitHub Actions
# workflow after the Foundation application and project configuration are ready.
# Developer-workstation/PFX signing is prohibited by CODE_SIGNING_POLICY.md.

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

$LegacyInstallerOutputs = @(Get-ChildItem 'release\SleepMate_Setup_v*.exe' -ErrorAction SilentlyContinue)
if ($LegacyInstallerOutputs.Count -gt 0) {
  throw "Legacy Inno Setup output must not be produced by the active build: $($LegacyInstallerOutputs.Name -join ', ')"
}

foreach ($notice in $ReleaseNoticeFiles) {
  if (-not (Test-Path (Join-Path 'dist\SleepMate' $notice))) {
    throw "Required release notice was not packaged: $notice"
  }
}

Write-Host "Program-tree release contract OK: app/EXE/updater/manifest/ZIP = $AppVersion"
Write-Host 'MSI will be built from dist\SleepMate by the dedicated GitHub Actions MSI job.'
Write-Host 'Program-tree release artifacts:'
Get-ChildItem release | Format-Table Name,Length,LastWriteTime
