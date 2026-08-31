# SleepMate Windows build és kiadási folyamat

## Célarchitektúra

SleepMate 5.0-tól:

- program: `%LOCALAPPDATA%\Programs\SleepMate`
- felhasználói állapot: `%LOCALAPPDATA%\SleepMate`
- nincs szükség admin jogra a normál használathoz vagy frissítéshez;
- az adatállapot nincs összekeverve a cserélhető programfákkal.

## 4.2.1 → 4.2.2 → 5.0.0

A 4.2.2 kompatibilitási híd. A meglévő forrásos 4.x telepítést még a régi módon futtatja, de már képes a teljes, bináris 5.x programfára történő biztonságos átmenetre.

Az átmenet során a régi állapot csak másolódik. Az eredeti mappából nem törlünk adatot.

## Windows build

A GitHub Actions `windows-latest` runneren futó `.github/workflows/windows-release.yml`:

1. checkoutolja a teljes forrást;
2. telepíti a Python buildfüggőségeket és az Inno Setupot;
3. lefuttatja a teszteket és szintaxisellenőrzéseket;
4. PyInstallerrel elkészíti a `SleepMate.exe` és `SleepMateUpdater.exe` binárisokat;
5. elkészíti a teljes programfa ZIP-et és SHA-256 manifestet;
6. Inno Setup segítségével elkészíti a `SleepMate_Setup_vX.Y.Z.exe` telepítőt;
7. tag esetén GitHub Release assetként publikálja őket.

## Kódaláírás

Opcionális GitHub Secrets:

- `WINDOWS_CERT_PFX_BASE64`
- `WINDOWS_CERT_PASSWORD`

Ha meg vannak adva, a build Authenticode aláírást tesz az EXE-kre és a telepítőre. A tanúsítvány soha nem kerül a repositoryba.

A digitális aláírás jelentősen javítja a Windows/SmartScreen bizalmi láncot, de egyetlen szoftver sem garantálhatja, hogy minden antivírus minden környezetben soha nem ad téves riasztást.

## Távoli elérés

A telepítő opcionálisan megkísérli telepíteni:

- Tailscale (`Tailscale.Tailscale`)
- cloudflared (`Cloudflare.cloudflared`)

A SleepMate felületén is van külön telepítés/állapotkezelés. Ha `winget` nem érhető el, a program a hivatalos letöltési oldalra irányít.

## Release kontraktus

A bináris kiadás mellé `sleepmate-update.json` készül, benne legalább:

- verzió;
- minimum kompatibilis verzió;
- teljes csomag neve;
- SHA-256;
- package type;
- build ID;
- Git commit.

Az updater csak hash-ellenőrzött teljes programfát telepít, frissítés előtti backup és rollback-pont után.

## GitHub fejlesztői eszközök

A normál SleepMate frissítéshez **nem szükséges** Git vagy GitHub CLI: az alkalmazás a GitHub Releases/API felől HTTPS-en ellenőriz és tölt le frissítést.

A Windows telepítőben külön, alapból kikapcsolt opcionális komponens telepítheti:

- Git for Windows (`Git.Git`)
- GitHub CLI (`GitHub.cli`)

Ez csak fejlesztéshez, a kanonikus forrás repository kezeléséhez és kézi release/bootstrap műveletekhez kell. A GitHub-bejelentkezést nem kényszeríti rá a normál felhasználóra.

## Tesztadatok es GitHub CI

Nyers CPAP/EDF terapias fajl **soha nem kerul a repositoryba**. A GitHub Actions a teljes szemelyes-adat-mentes tesztkort futtatja. A regi regresszios tesztek, amelyek a privat helyi `testdata/DATALOG` fixture pontos ertekeire epulnek, csak lokalisan/release elott futnak, amikor ez a fixture rendelkezesre all.
