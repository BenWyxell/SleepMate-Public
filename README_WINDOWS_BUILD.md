# SleepMate Windows build és kiadási folyamat

## Célarchitektúra

A jelenlegi production-cél:

- program: `%LOCALAPPDATA%\Programs\SleepMate`
- felhasználói állapot: `%LOCALAPPDATA%\SleepMate`
- normál telepítés/frissítés: per-user, admin jog nélkül
- hordozható frissítési programfa: ZIP
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

A public build **GNOME msitools / `wixl`** használatára áll át.

A build tool Linux/GitHub Actions környezetben fut; a Windows felhasználó gépére nem kerül telepítésre és nem része a SleepMate csomagnak.

Azért nem a jelenlegi WiX Toolset bináris release a default buildfüggőség, mert annak bevételtermelő használatára Open Source Maintenance Fee feltételek vonatkoznak. A `msitools` jelenlegi csomagja LGPL-2.1-or-later licencű.

## GitHub Actions felépítés

`.github/workflows/windows-release.yml` három egymásra épülő jobot használ.

### 1. `build-windows-x64`

GitHub-hosted `windows-latest` runner:

1. checkout;
2. Python 3.13;
3. public-source gate;
4. integration/contract tesztek;
5. PyInstaller `SleepMate.exe`;
6. PyInstaller `SleepMateUpdater.exe`;
7. teljes `dist\SleepMate` programfa;
8. hordozható `SleepMate_vX.Y.Z_windows_x64.zip`;
9. `sleepmate-update.json`;
10. rövid életű program-tree artifact feltöltése.

A Windows job **nem** épít Inno Setup telepítőt és **nem** használ PFX certificate secretet.

### 2. `build-msi`

GitHub-hosted `ubuntu-latest` runner:

1. checkoutolja ugyanazt a commitot;
2. telepíti a distro `msitools` csomagját;
3. letölti az előző job által készített Windows programfát;
4. `scripts/generate_msi_wxs.py` determinisztikusan előállítja a WiX-v3-kompatibilis WXS forrást;
5. `wixl` elkészíti a `SleepMate_Setup_vX.Y.Z.msi` fájlt;
6. SHA-256 készül;
7. `msiextract` visszabontja és ellenőrzi, hogy legalább a `SleepMate.exe`, `SleepMateUpdater.exe` és `SleepMate.ico` ténylegesen benne van;
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
10. összeállítja a teljes unsigned CI release artifactot.

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

A SleepMate beépített updaterének hordozható frissítési formátuma továbbra is:

`SleepMate_vX.Y.Z_windows_x64.zip`

A manifest:

`sleepmate-update.json`

Az updater hash-ellenőrzött programfát használ, backup/rollback ponttal.

Az MSI elsődlegesen tiszta telepítéshez, Windows Installer regisztrációhoz és eltávolításhoz szolgál. A hosszabb távú release policy külön döntheti el, hogy minden fő verzióhoz MSI-upgrade is kiadásra kerül-e.

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
