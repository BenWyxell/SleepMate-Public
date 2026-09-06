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

Az ellenőrzött jelölt tagelt stabil kiadásnál automatikusan továbbmegy publikálásra. Ha mind az öt SignPath-beállítás hiányzik, és a forrás policyje `verified-unsigned`, a workflow VERIFIED UNSIGNED módban publikálja a már ellenőrzött artifactot. Ha mind az öt beállítás megvan, a forrás policyjének `authenticode-required` értékűnek kell lennie, majd kötelezően lefut a SignPath és az Authenticode-ellenőrzés. Részleges konfiguráció, policy-eltérés vagy sikertelen signing nem eshet vissza unsigned publikálásra.

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

A `sleepmate-update.json` az MSI pontos nevét, verzióját, méretét, SHA-256 értékét és az explicit `signature_mode` értéket rögzíti. A jelenlegi `verified-unsigned` build elfogadja a canonical workflow teljes ellenőrzési láncán átment unsigned MSI-t; `authenticode` manifest esetén továbbra is ellenőrzi az aláírást. Egy későbbi, `authenticode-required` policyvel fordított build kizárólag aláírt MSI-t fogad el. A minimum policy az alkalmazásba van fordítva, ezért a manifest nem tudja lejjebb állítani.

A SleepMate minden módban megköveteli a hivatalos `BenWyxell/SleepMate-Public` GitHub Release API-t, HTTPS-t, stabil release-t, a pontos MSI-nevet, verzióegyezést, `windows-msi-x64`/`requires_installer` contractot, érvényes SHA-256 egyezést és MSI konténert. Ezután teljes adatmentést készít, majd a rendszer saját `msiexec.exe` folyamatának adja át a telepítést. Saját updater EXE, ZIP-kicsomagoló vagy programfát felülíró rollback folyamat nincs.

A hordozható ZIP továbbra is kézi, telepítés nélküli használatra készül, de az alkalmazás nem használja önfrissítésre.

### Már publikált v5.3.20 átmeneti korlát

A publikált v5.3.20 frozen Windows bináris feltétel nélkül WinVerifyTrust-ellenőrzést kér az új MSI-re. Ezt egy későbbi release-ben lévő forrásmódosítás nem tudja visszamenőleg átírni. Ezért a már telepített v5.3.20 példányok csak Authenticode-aláírt következő MSI-re tudnak automatikusan frissülni; unsigned átmeneti buildre egyszeri kézi MSI-telepítés szükséges. A kézi átmenet után a következő build már az itt dokumentált kétmódú szerződést használja. Ezt a korlátot nem oldjuk meg manifest-downgrade-dal vagy saját updater EXE visszahozásával.

## Production kódaláírás

A public CI artifactok jelenleg **unsigned** fájlok.

A production buildben nem használunk repository PFX secretet és nem írunk alá fejlesztői workstationről.

A tervezett sorrend:

1. GitHub Actions felépíti és teljesen ellenőrzi az unsigned programfát és MSI-t.
2. SignPath hiányában ezt VERIFIED UNSIGNED módban automatikusan publikálja.
3. Teljes SignPath-konfiguráció esetén artifactként rögzíti a signing inputot.
4. SignPath Trusted Build ellenőrzi a repository/commit/workflow origint, majd approval után aláír.
5. A workflow kötelező Authenticode-ellenőrzést futtat.
6. A végleges hash-eket és manifestet az aláírt bájtokból újragenerálja, majd automatikusan publikálja.

Részletes szabály: `CODE_SIGNING_POLICY.md`.

## Tesztadatok

Nyers CPAP/EDF terápiás fájl nem kerülhet a repositoryba. A publikus GitHub CI csak személyes adatot nem tartalmazó tesztfixture-öket használ.
