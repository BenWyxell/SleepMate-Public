param(
  [Parameter(Mandatory = $true)]
  [string]$PackageId,

  [Parameter(Mandatory = $true)]
  [string]$DisplayName,

  [Parameter(Mandatory = $true)]
  [string]$LogPath,

  [switch]$EnsureOnly
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-InstallerLog {
  param([string]$Message)
  $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  Add-Content -Path $LogPath -Value "[$stamp] $Message" -Encoding UTF8
}

function Resolve-WinGet {
  $cmd = Get-Command winget.exe -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -and (Test-Path $cmd.Source)) {
    return $cmd.Source
  }

  $aliasPath = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\winget.exe'
  if (Test-Path $aliasPath) {
    return $aliasPath
  }

  $appInstaller = Get-AppxPackage -Name Microsoft.DesktopAppInstaller -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($appInstaller -and $appInstaller.InstallLocation) {
    $packageWinget = Join-Path $appInstaller.InstallLocation 'winget.exe'
    if (Test-Path $packageWinget) {
      return $packageWinget
    }
  }

  return $null
}

function Ensure-WinGet {
  $winget = Resolve-WinGet
  if ($winget) {
    Write-InstallerLog "WinGet már elérhető: $winget"
    return $winget
  }

  Write-InstallerLog 'winget.exe nem található; Microsoft App Installer regisztráció megkísérlése.'
  try {
    Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe -ErrorAction Stop
  }
  catch {
    Write-InstallerLog "App Installer regisztráció nem sikerült vagy nem volt szükséges: $($_.Exception.Message)"
  }

  Start-Sleep -Milliseconds 700
  $winget = Resolve-WinGet
  if ($winget) {
    Write-InstallerLog "WinGet App Installer regisztráció után elérhető: $winget"
    return $winget
  }

  Write-InstallerLog 'WinGet bootstrap indul a Microsoft.WinGet.Client PowerShell modullal.'
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Install-PackageProvider -Name NuGet -Force -Scope CurrentUser | Out-Null
    Install-Module -Name Microsoft.WinGet.Client -Force -Repository PSGallery -Scope CurrentUser -AllowClobber | Out-Null
    Import-Module Microsoft.WinGet.Client -Force
    Repair-WinGetPackageManager -Force -Latest | Out-Null
    Write-InstallerLog 'Repair-WinGetPackageManager lefutott.'
  }
  catch {
    Write-InstallerLog "ERROR WinGet bootstrap: $($_.Exception.Message)"
  }

  Start-Sleep -Milliseconds 1200
  $winget = Resolve-WinGet
  if (-not $winget) {
    Write-InstallerLog 'ERROR WinGet bootstrap után sem található winget.exe.'
    return $null
  }

  Write-InstallerLog "OK WinGet telepítve/helyreállítva: $winget"
  return $winget
}

$logDir = Split-Path -Parent $LogPath
if ($logDir) {
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}

try {
  $winget = Ensure-WinGet
  if (-not $winget) {
    exit 127
  }

  if ($EnsureOnly) {
    $versionOutput = (& $winget --version 2>&1 | Out-String).Trim()
    Write-InstallerLog "OK WinGet ellenőrzés kész. version=$versionOutput"
    exit 0
  }

  Write-InstallerLog "START $DisplayName ($PackageId) winget=$winget"

  $installArgs = @(
    'install',
    '--id', $PackageId,
    '--exact',
    '--silent',
    '--disable-interactivity',
    '--accept-package-agreements',
    '--accept-source-agreements',
    '--source', 'winget'
  )

  $output = & $winget @installArgs 2>&1
  $installExit = $LASTEXITCODE
  foreach ($line in $output) {
    Write-InstallerLog "winget: $line"
  }

  # A már telepített / naprakész csomagot is sikernek tekintjük.
  # A csomagazonosítóra keresünk, így a lokalizált winget kimenet sem probléma.
  $listOutput = (& $winget list --id $PackageId --exact --accept-source-agreements --disable-interactivity 2>&1 | Out-String)
  $installed = $listOutput -match [regex]::Escape($PackageId)

  if ($installExit -eq 0 -or $installed) {
    Write-InstallerLog "OK $DisplayName ($PackageId) installExit=$installExit installed=$installed"
    exit 0
  }

  Write-InstallerLog "ERROR $DisplayName ($PackageId) installExit=$installExit installed=$installed"
  if ($installExit -eq 0) {
    exit 1
  }
  exit $installExit
}
catch {
  try {
    Write-InstallerLog "EXCEPTION $DisplayName ($PackageId): $($_.Exception.Message)"
  }
  catch {
  }
  exit 1
}
