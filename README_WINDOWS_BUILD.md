# SleepMate Windows build és kiadási folyamat

## Célarchitektúra

A jelenlegi production-cél:

- program: `%LOCALAPPDATA%\Programs\SleepMate`
- felhasználói állapot: `%LOCALAPPDATA%\SleepMate`
- normál telepítés/frissítés: per-user, admin jog nélkül
- hordozható letöltési programfa: ZIP
- elsődleges Windows telepítő: **MSI**
- production kódaláírás: **SignPath Foundation / Authenticode**
- build origin: kizárólag GitHub-hosted GitHub Actions runner

A programfájl és a felhasználói állapot külön marad. Az MSI eltávolítása a programot távolítja el; a `%LOCALAPPDATA%\SleepMate` terápiás/páciens állapot szándékosan megmarad.

## Miért MSI?

A korábbi Inno Setup alapú `SleepMate_Setup_vX.Y.Z.exe` telepítő legacy megoldás.

A production MSI irány előnyei:

- a Windows Installer (`msiexec.exe`) végzi a telepítést és eltávolítást;
- nincs saját `unins*.exe`, amely külön SleepMate-aláírást igényelne;
- a teljes `.msi` Authenticode-aláírható;
- SignPath képes MSI deep signingra, vagyis a SleepMate saját PE fájljai és maga az MSI ugyanabban az ellenőrzött signing requestben kezelhetők;
- a telepítés per-user maradhat;
- a telepítési és eltávolítási folyamat CI-ben közvetlenül tesztelhető `msiexec` segítségével.

## MSI build tool

A public build a rögzített **WiX Toolset 3.14.1** verziót használja.

A build tool GitHub-hosted Windows Actions környezetben fut; a felhasználó gépére nem kerül telepítésre és nem része a SleepMate csomagnak.

## GitHub Actions felépítés

`.github/workflows/windows-release.yml` egymásra épülő build-, telepítési próba-, integritás-, SignPath-aláírási és publikálási jobokat használ.

### 1. `build-windows-x64`

GitHub-hosted `windows-latest` runner:

1. checkout;
2. Python 3.13;
3. public-source gate;
4. integration/contract tesztek;
5. PyInstaller `SleepMate.exe`;
6. teljes `dist\SleepMate` programfa;
7. hordozható `SleepMate_vX.Y.Z_windows_x64.zip`;
8. rövid életű program-tree artifact feltöltése.

A Windows job **nem** épít Inno Setup telepítőt és **nem** használ PFX certificate secretet.

### 2. `build-msi`

GitHub-hosted `windows-latest` runner:

1. checkoutolja ugyanazt a commitot;
2. telepíti a rögzített WiX Toolsetet;
3. letölti az előző job által készített Windows programfát;
4. `scripts/generate_msi_wxs.py` determinisztikusan előállítja a WiX-v3-kompatibilis WXS forrást;
5. `candle.exe` és `light.exe` elkészíti a `SleepMate_Setup_vX.Y.Z.msi` fájlt;
6. SHA-256 készül;
7. adminisztratív MSI-kibontással ellenőrzi, hogy a `SleepMate.exe` és `SleepMate.ico` benne van, a megszüntetett `SleepMateUpdater.exe` pedig nincs benne;
8. az MSI és inventory rövid életű CI artifactként kerül feltöltésre.

### 3. `smoke-test-msi`

GitHub-hosted `windows-latest` runner:

1. letölti az MSI-t;
2. `msiexec /i` segítségével egy izolált per-user tesztmappába telepíti;
3. ellenőrzi az EXE verzióját;
4. elindítja a telepített SleepMate backendet;
5. ellenőrzi `/api/version`, SleepSync, Google Drive és Web Push alapállapotát;
6. leállítja a programot;
7. `msiexec /x` segítségével eltávolítja;
8. ellenőrzi, hogy a programfájl eltűnt;
9. ellenőrzi, hogy a külön felhasználói state megmaradt;
10. összeállítja a teljes, még aláíratlan CI release-jelöltet.

Az ellenőrzött jelöltet a tagelt stabil kiadás SignPath trusted-build kérésbe küldi. A publikálás csak akkor indulhat el, ha az MSI és a mindkét konténerben lévő `SleepMate.exe` Authenticode-aláírása érvényes. A végső `sleepmate-update.json` és SHA-256 fájlok kizárólag ezután, az aláírt MSI-ből készülnek.

Az alkalmazáson belüli frissítés a letöltött MSI hash-ellenőrzése után közvetlenül a Windows rendszer `msiexec.exe` folyamatát indítja. Saját frissítő EXE nem készül és nem kerül a csomagba.

## MSI telepítési modell

Alapértelmezett telepítési könyvtár:

`%LOCALAPPDATA%\Programs\SleepMate`

Az MSI:

- per-user;
- x64;
- Start menü SleepMate parancsikont készít;
- Windows Installer alapú uninstall parancsikont készít;
- a `HKCU\Software\SleepMate` alatt nyilvántartja az install path/state path/version adatokat;
- a program eltávolításakor nem törli `%LOCALAPPDATA%\SleepMate` tartalmát.

Opcionális public MSI property-k:

- `DESKTOP_SHORTCUT=1`
- `START_WITH_WINDOWS=1`

Példa:

```powershell
msiexec /i SleepMate_Setup_v5.2.16.msi DESKTOP_SHORTCUT=1 START_WITH_WINDOWS=1
```

Az alapérték mindkettőnél kikapcsolt.

## Legacy Inno Setup átmenet

Az MSI ellenőrzi a korábbi Inno Setup SleepMate uninstall-regisztrációját. Ha legacy Inno telepítés még aktív, az MSI nem próbálja azt csendben felülírni vagy egy másik installerből eltávolítani.

A biztonságos átmenet:

1. régi SleepMate Inno telepítés eltávolítása;
2. `%LOCALAPPDATA%\SleepMate` állapot megmarad;
3. MSI telepítése;
4. SleepMate ugyanazt a helyi state-et használja tovább.

A régi `C:\CPAP-EzShare\SleepMate` forrásos korszakhoz a programban továbbra is rendelkezésre áll a copy-only `--migrate-from` mechanizmus.

## Opcionális Tailscale / Cloudflare / fejlesztői eszközök

A production MSI **nem bootstrapol automatikusan wingetet és nem futtat telepítés közben külső package-manager telepítéseket**.

Ez szándékos biztonsági egyszerűsítés: az MSI a SleepMate-et telepíti. Tailscale/cloudflared opcionális, felhasználó által vezérelt integráció marad, és a SleepMate felülete külön kezeli/ellenőrzi az elérhetőségüket.

Git és GitHub CLI normál SleepMate használathoz nem szükséges.

## Frissítés

A SleepMate alkalmazáson belüli frissítésének egyetlen elfogadott telepítési formátuma:

`SleepMate_Setup_vX.Y.Z.msi`

A `sleepmate-update.json` az MSI pontos nevét, verzióját, méretét és SHA-256 értékét rögzíti. A SleepMate letöltés után ezeket, az MSI konténerazonosítóját és a Windows Authenticode-aláírást is ellenőrzi, teljes adatmentést készít, majd a rendszer saját `msiexec.exe` folyamatának adja át a telepítést. Saját updater EXE, ZIP-kicsomagoló vagy programfát felülíró rollback folyamat nincs.

A hordozható ZIP továbbra is kézi, telepítés nélküli használatra készül, de az alkalmazás nem használja önfrissítésre.

## Production kódaláírás

A public CI artifactok jelenleg **unsigned** fájlok.

A production buildben nem használunk repository PFX secretet és nem írunk alá fejlesztői workstationről.

A tervezett sorrend:

1. GitHub Actions felépíti az unsigned programfát és MSI-t;
2. GitHub Actions artifactként rögzíti a signing inputot;
3. SignPath Trusted Build ellenőrzi a repository/commit/workflow origint;
4. manuális approval;
5. SignPath deep signing aláírja a SleepMate saját PE fájljait és az MSI-t;
6. Authenticode verification;
7. csak ezután készülnek a végleges release hash-ek és manifest;
8. csak a végleges signed artifact publikálható.

Részletes szabály: `CODE_SIGNING_POLICY.md`.

## Tesztadatok

Nyers CPAP/EDF terápiás fájl nem kerülhet a repositoryba. A publikus GitHub CI csak személyes adatot nem tartalmazó tesztfixture-öket használ.
