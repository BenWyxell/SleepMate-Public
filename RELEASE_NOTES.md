# SleepMate 5.2.17

A SleepMate 5.2.17 a korábbi, SignPath-kompatibilis MSI candidate helyett már valódi felhasználói Windows-telepítőt és első-indítási beállítóvarázslót ad.

## Magyar Windows MSI telepítő

- A telepítő nyelve **magyar (`hu-HU`, Windows Installer Language 1038)**.
- Valódi WiX telepítővarázsló kezeli a telepítési helyet, a komponensválasztást és a telepítés összegzését.
- A Start menü integráció a SleepMate alaptelepítés része.
- Az **asztali parancsikon** választható Windows-integrációs komponens.
- Az **automatikus Windows-indítás** külön opcionális komponens; friss telepítésnél a SleepMate átveszi ezt a választást, frissítésnél nem írja felül a meglévő beállítást.
- A telepítés végén a **SleepMate indítása** opcióval az alkalmazás azonnal elindítható.

## Licencfeltételek és adatvédelem

- A telepítő egy közös, görgethető **„Licencfeltételek és adatvédelem”** oldalon jeleníti meg a repository `LICENSE` és `PRIVACY.md` dokumentumának tartalmát.
- A két forrásdokumentum továbbra is külön fájl marad; csak az MSI-ben jelennek meg egy közös elfogadó oldalon.
- A telepítés csak a licencfeltételek és az Adatvédelmi tájékoztató együttes elfogadása után folytatható.

## SleepMate első beállítása

Az első indításkor hatlépéses, újra megnyitható setup wizard indul:

1. üdvözlés és helyi adatkezelési alapelv;
2. CPAP / ResMed adatforrás és automatikus változásellenőrzés;
3. SleepSync automatikus ez Share szinkron;
4. helyi használat, Tailscale vagy Cloudflare Tunnel;
5. PWA, Web Push, automatikus backup, opcionális Gemini és Groq API;
6. összegzés és befejezés.

Vadonatúj telepítésnél a SleepMate nem tekinti automatikusan érvényes adatforrásnak a `Documents\CPAP_mentes` útvonalat: a felhasználó választja ki a tényleges forrást. Meglévő telepítés frissítésekor az addigi adatforrás és beállítások megmaradnak.

## Távoli elérés és opcionális szolgáltatások

- A Tailscale és a cloudflared telepítése a SleepMate meglévő backendjén keresztül, a hivatalos winget csomagokkal történik.
- A SleepMate backend továbbra is helyi (`127.0.0.1`); Tailscale és Cloudflare reverse proxyval biztosít távoli HTTPS-elérést.
- Cloudflare Tunnel indításához a SleepMate megköveteli a Cloudflare Access / Zero Trust védelem felhasználói visszaigazolását.
- A Cloudflare token és a Gemini/Groq API-kulcsok a meglévő Windows DPAPI-védett helyi titoktárolókba kerülnek; az onboarding állapotfájl nem tárol credentialt.
- A PWA telepítése és a böngészős értesítési engedély biztonsági okból továbbra is kifejezett felhasználói művelet; a wizard ezeket közvetlen gombokkal indítja.

## Kiadási lánc

- Az MSI a GitHub Actions Windows runnerén, rögzített **WiX Toolset 3.14.1** toolchainnel készül.
- A CI ellenőrzi a publikus forrás tisztaságát, Python/JavaScript szintaxist, a csomagolási contractokat, a teljes Windows program-tree buildet, az MSI payloadot, a telepített backend API-kat, SleepSyncet, Google Drive státuszt, onboardingot, Web Push-t és az eltávolítást.
- A CI továbbra sem publikál automatikusan GitHub Release-t és nem végez production aláírást; a SignPath aláírás a trusted build láncra kerül majd.

Kiadási csatorna: **stable**.
Release build: **5.2.17**.
API: **19**.
Release validation: **Windows program-tree + magyar MSI + telepített EXE/backend smoke-test**.

---

# SleepMate 5.2.16

A SleepMate 5.2.16 az ez Share időszakosan eltűnő Wi-Fi-jét kezeli kulturáltabban. A 2026-08-29-i terepi logban a kártya 85–87%-os jelerősséggel sikeresen csatlakozott, majd a webfelülete nem válaszolt, végül maga az `ez Share` SSID is eltűnt, miközben más Wi-Fi hálózatok továbbra is láthatók maradtak. Ilyenkor nincs értelme újra és újra a Windows WLAN-t resetelni vagy ugyanarra a nem sugárzó hálózatra connect parancsot küldeni.

## SleepSync – az eltűnt ez Share felismerése

- A v5.2.15-ben bevált **12 másodperces tiszta Windows automatikus társítási ablak változatlanul az első lépés**: nincs scan, explicit connect vagy reset.
- Ha ez nem sikerül, a SleepSync két rövid, egymást követő scan alapján ellenőrzi, hogy az `ez Share` ténylegesen sugároz-e.
- Ha az `ez Share` egyik scan-ben sem látható, de más hálózatok igen, ezt külön **„ez Share nem sugároz”** állapotként kezeli.
- Ebben az állapotban nem indulnak felesleges `netsh connect`, profil-újraélesztési vagy WLAN-reset körök.
- Ha a Windows egyáltalán nem ad értékelhető scan-listát, a helyzet nem minősül tévesen kártyahibának; ilyenkor a korábbi v5.2.15 önhelyreállító WLAN-motor veszi át a próbát.

## Internet megtartása várakozás közben

- Ha az ez Share AP eltűnt, a SleepSync visszaállítja és **megtartja a normál internetes Wi-Fi kapcsolatot**.
- Kézi szinkronnál 30 másodperc, automatikus szinkronnál 45 másodperc múlva nézi meg először, hogy visszatért-e az ez Share.
- Ezután 30 másodpercenként végez kíméletes jelenlét-ellenőrzést.
- Csak akkor bontja újra az internetet és próbál kapcsolódni az ez Share-hez, amikor az SSID ténylegesen újra megjelent.
- A meglévő teljes helyreállítási ablak változatlan: kézi futásnál legfeljebb 25 perc, automatikus futásnál legfeljebb 45 perc.

## Ami változatlan maradt

- Ha az ez Share látható, de a Windows társítása hibázik vagy `associating` állapotban ragad, továbbra is a v5.2.15 fokozatos WLAN-helyreállítása fut.
- A közvetlen IP/gateway elérés és az `ezshare.card` fallback változatlan.
- A nem destruktív ResMed-import, a teljes SD-tükör és ZIP biztonsági mentés változatlanul megmaradt.
- Az Alvások cache sikeres SleepSync után továbbra is érvénytelenítésre kerül.
- Külön regresszióteszt ellenőrzi, hogy nem sugárzó ez Share esetén az aktív WLAN-helyreállítás ne induljon el, és hogy a passzív várakozás alatt az internetkapcsolat megmaradjon.

Kiadási csatorna: **stable**.
Release build: **5.2.16**.
API: **19**.
Release validation: **Windows csomag + telepített EXE smoke-test**.
Release regression contract: **ez Share AP-presence aware recovery**.
