#define MyAppName "SleepMate"
#ifndef MyAppVersion
  #error MyAppVersion must be supplied by build_release.ps1
#endif
#ifndef MyAppVersionQuad
  #error MyAppVersionQuad must be supplied by build_release.ps1
#endif
#define MyAppExeName "SleepMate.exe"
#define MyAppPublisher "SleepMate"

[Setup]
AppId={{7E655DC3-62BC-4A9D-8EC2-B0CC579126E1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SleepMate
DefaultGroupName=SleepMate
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\..\release
OutputBaseFilename=SleepMate_Setup_v{#MyAppVersion}
SetupIconFile=..\..\..\SleepMate.ico
UninstallDisplayIcon={app}\SleepMate.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern dynamic
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
VersionInfoVersion={#MyAppVersionQuad}
VersionInfoProductName=SleepMate
VersionInfoDescription=SleepMate telepítő
VersionInfoProductVersion={#MyAppVersion}
AppMutex=Global\SleepMateTraySingleton_v1,Local\SleepMateTraySingleton_v1

[Languages]
Name: "hungarian"; MessagesFile: "compiler:Languages\Hungarian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Asztali SleepMate ikon létrehozása"; GroupDescription: "Parancsikonok:"; Flags: unchecked
Name: "startup"; Description: "SleepMate indítása a Windowszal"; GroupDescription: "Indítás:"; Flags: unchecked
Name: "winget"; Description: "Windows Package Manager (winget) ellenőrzése / telepítése"; GroupDescription: "Rendszerkomponensek:"
Name: "tailscale"; Description: "Tailscale telepítése (távoli PWA eléréshez)"; GroupDescription: "Opcionális távoli elérés:"; Flags: unchecked
Name: "cloudflared"; Description: "cloudflared telepítése (Cloudflare Tunnelhöz)"; GroupDescription: "Opcionális távoli elérés:"; Flags: unchecked
Name: "githubtools"; Description: "Git + GitHub CLI telepítése (csak fejlesztéshez / forráskezeléshez)"; GroupDescription: "Opcionális fejlesztői eszközök:"; Flags: unchecked

[Files]
Source: "..\..\..\dist\SleepMate\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\installed.marker"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\..\build_info.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\..\SleepMate.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "install-winget-package.ps1"; Flags: dontcopy

[Icons]
Name: "{group}\SleepMate"; Filename: "{app}\SleepMate.exe"; WorkingDir: "{app}"; IconFilename: "{app}\SleepMate.ico"
Name: "{autodesktop}\SleepMate"; Filename: "{app}\SleepMate.exe"; WorkingDir: "{app}"; IconFilename: "{app}\SleepMate.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SleepMate"; ValueData: """{app}\SleepMate.exe"""; Flags: uninsdeletevalue; Tasks: startup
Root: HKCU; Subkey: "Software\SleepMate"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\SleepMate"; ValueType: string; ValueName: "StatePath"; ValueData: "{localappdata}\SleepMate"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\SleepMate"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\SleepMate.exe"; Parameters: "--migrate-from ""{code:GetLegacyPath}"" --migrate-only"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated skipifsilent; Check: ShouldMigrate
Filename: "{app}\SleepMate.exe"; Description: "SleepMate indítása"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; A felhasználói terápiás/páciens állapot szándékosan NEM törlődik.
; %LOCALAPPDATA%\SleepMate megmarad, hogy egy újratelepítés veszteségmentes legyen.

[Code]
var
  LegacyPage: TInputQueryWizardPage;

function KnownLegacyPath(): String;
begin
  if DirExists('C:\CPAP-EzShare\SleepMate') then
    Result := 'C:\CPAP-EzShare\SleepMate'
  else
    Result := '';
end;

procedure InitializeWizard;
begin
  LegacyPage := CreateInputQueryPage(wpSelectDir,
    'Korábbi SleepMate adatok',
    'Meglévő SleepMate telepítés átvétele (opcionális)',
    'Ha már használtad a SleepMate-et, add meg a régi program mappáját. A telepítő csak MÁSOLJA az adatokat az új, külön felhasználói adattárba; a régi mappából semmit nem töröl. Ha ez egy új telepítés, hagyd üresen.');
  LegacyPage.Add('Régi SleepMate mappa:', False);
  LegacyPage.Values[0] := KnownLegacyPath();
end;

function GetLegacyPath(Param: String): String;
begin
  Result := Trim(LegacyPage.Values[0]);
end;

function ShouldMigrate(): Boolean;
var
  P: String;
begin
  P := Trim(LegacyPage.Values[0]);
  Result := (P <> '') and DirExists(P) and (FileExists(P + '\\config.json') or DirExists(P + '\\private'));
end;

procedure AddFailure(var Failures: String; Item: String);
begin
  if Failures <> '' then
    Failures := Failures + #13#10;
  Failures := Failures + '- ' + Item;
end;

function EnsureWingetAvailable(var Failures: String): Boolean;
var
  PowerShellPath: String;
  ScriptPath: String;
  LogPath: String;
  Params: String;
  ResultCode: Integer;
begin
  Result := False;
  PowerShellPath := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  ScriptPath := ExpandConstant('{tmp}\install-winget-package.ps1');
  LogPath := ExpandConstant('{localappdata}\SleepMate\logs\installer-integrations.log');

  WizardForm.StatusLabel.Caption := 'Windows Package Manager (winget) ellenőrzése / telepítése...';
  Log('WinGet előfeltétel ellenőrzése és szükség szerinti bootstrap telepítése.');

  Params := '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + ScriptPath +
    '" -PackageId "__ensure__" -DisplayName "Windows Package Manager (winget)"' +
    ' -LogPath "' + LogPath + '" -EnsureOnly';

  if not Exec(PowerShellPath, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    AddFailure(Failures, 'Windows Package Manager (winget): a PowerShell bootstrap folyamat nem indítható.');
    Log('WinGet bootstrap indítási hiba.');
    Exit;
  end;

  if ResultCode = 0 then
  begin
    Result := True;
    Log('WinGet elérhető / sikeresen telepítve vagy helyreállítva.');
    Exit;
  end;

  AddFailure(Failures, 'Windows Package Manager (winget): nem sikerült telepíteni vagy helyreállítani (hibakód ' + IntToStr(ResultCode) + ').');
  Log('WinGet bootstrap sikertelen, exit=' + IntToStr(ResultCode));
end;

function InstallWingetPackage(PackageId: String; DisplayName: String; var Failures: String): Boolean;
var
  PowerShellPath: String;
  ScriptPath: String;
  LogPath: String;
  Params: String;
  ResultCode: Integer;
begin
  Result := False;
  PowerShellPath := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  ScriptPath := ExpandConstant('{tmp}\install-winget-package.ps1');
  LogPath := ExpandConstant('{localappdata}\SleepMate\logs\installer-integrations.log');

  WizardForm.StatusLabel.Caption := DisplayName + ' telepítése...';
  Log('Opcionális integráció telepítése: ' + DisplayName + ' (' + PackageId + ')');

  Params := '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + ScriptPath +
    '" -PackageId "' + PackageId + '" -DisplayName "' + DisplayName +
    '" -LogPath "' + LogPath + '"';

  if not Exec(PowerShellPath, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    AddFailure(Failures, DisplayName + ': a PowerShell telepítési folyamat nem indítható.');
    Log('Opcionális integráció indítási hiba: ' + DisplayName);
    Exit;
  end;

  if ResultCode = 0 then
  begin
    Result := True;
    Log('Opcionális integráció sikeres: ' + DisplayName);
    Exit;
  end;

  if ResultCode = 127 then
    AddFailure(Failures, DisplayName + ': a Windows Package Manager (winget) bootstrapja sikertelen volt.')
  else
    AddFailure(Failures, DisplayName + ': a telepítés hibakóddal leállt (' + IntToStr(ResultCode) + ').');

  Log('Opcionális integráció sikertelen: ' + DisplayName + ', exit=' + IntToStr(ResultCode));
end;

procedure InstallOptionalIntegrations;
var
  Failures: String;
  AnySelected: Boolean;
  WingetReady: Boolean;
begin
  AnySelected := WizardIsTaskSelected('winget') or WizardIsTaskSelected('tailscale') or
    WizardIsTaskSelected('cloudflared') or WizardIsTaskSelected('githubtools');
  if not AnySelected then
    Exit;

  Failures := '';
  ExtractTemporaryFile('install-winget-package.ps1');

  // A winget minden külső csomag előfeltétele. Ha bármelyik csomag ki van
  // választva, akkor akkor is biztosítjuk, ha a felhasználó a külön winget pipát levette.
  WingetReady := EnsureWingetAvailable(Failures);

  if WingetReady then
  begin
    if WizardIsTaskSelected('tailscale') then
      InstallWingetPackage('Tailscale.Tailscale', 'Tailscale', Failures);

    if WizardIsTaskSelected('cloudflared') then
      InstallWingetPackage('Cloudflare.cloudflared', 'cloudflared', Failures);

    if WizardIsTaskSelected('githubtools') then
    begin
      InstallWingetPackage('Git.Git', 'Git', Failures);
      InstallWingetPackage('GitHub.cli', 'GitHub CLI', Failures);
    end;
  end;

  if Failures = '' then
  begin
    WizardForm.StatusLabel.Caption := 'A kiválasztott rendszerkomponensek és kiegészítők telepítése kész.';
    if not WizardSilent then
      MsgBox('A kiválasztott rendszerkomponensek és kiegészítők telepítése sikeresen befejeződött.', mbInformation, MB_OK);
  end
  else
  begin
    WizardForm.StatusLabel.Caption := 'Egy vagy több rendszerkomponens / kiegészítő telepítése sikertelen.';
    if not WizardSilent then
      MsgBox('A SleepMate telepítése elkészült, de az alábbi rendszerkomponenseket vagy kiegészítőket nem sikerült telepíteni:' + #13#10#13#10 +
        Failures + #13#10#13#10 +
        'Részletes napló: ' + ExpandConstant('{localappdata}\SleepMate\logs\installer-integrations.log'),
        mbError, MB_OK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    InstallOptionalIntegrations;
end;