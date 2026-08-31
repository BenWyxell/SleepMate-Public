# SleepMate 5.2.17

A SleepMate 5.2.17 a Windows telepítést és az első indítást teszi valódi végfelhasználói folyamattá. A korábbi 5.2.16 MSI technikailag telepíthető SignPath-kompatibilis csomag volt; az 5.2.17 már interaktív telepítő- és onboarding élményt ad.

## Kétnyelvű Windows MSI telepítő

- Első képernyőn **Magyar / English** telepítési nyelv választható.
- A kiválasztott nyelv végigviszi az MSI dialogsorozatát és átkerül a SleepMate első-indítási varázslójába is.
- Külön üdvözlő, telepítési hely, Windows-opciók, telepítésre kész és befejező képernyő készült.
- A telepítési hely szerkeszthető; alapértelmezés továbbra is a felhasználói `LocalAppData\Programs\SleepMate` terület.
- Választható asztali SleepMate parancsikon.
- A Windowszal együtt indulás alapértelmezése a telepítőből átkerül az első-indítási beállításba.
- A Befejezés gomb elindítja a SleepMate-et; silent CI telepítésnél ez a UI-akció természetesen nem fut.

## Első-indítási Setup Wizard

A SleepMate első induláskor külön, újranyitható beállítóvarázslót mutat:

- CPAP / ResMed beolvasási forrás és read-only működés.
- Automatikus teljes backup helye és alapütemezése.
- Windows automatikus indulás és helyi értesítések.
- Stable GitHub frissítések automatikus ellenőrzése a `BenWyxell/SleepMate-Public` publikus repóból.
- Távoli elérés: helyi használat, Tailscale vagy Cloudflare Tunnel.
- Tailscale hivatalos kliens telepítése/ellenőrzése és SleepMate HTTPS Serve bekapcsolása.
- cloudflared hivatalos kliens telepítése/ellenőrzése, hostname, Tunnel token, Cloudflare Access / Zero Trust megerősítés és Tunnel indítás.
- A Cloudflare Tunnel token továbbra is a meglévő helyi, DPAPI-védett secret store-ba kerül; nem a normál config fájlba és nem GitHubra.
- PWA, service worker, Web Push/VAPID állapot és telefonos telepítési lépések.
- Tailscale HTTPS cím esetén QR-kód is megjeleníthető.

## Csomagolási és biztonsági elvek

- A backend továbbra is `127.0.0.1`-re köt; a távoli elérés reverse proxyval történik.
- A PWA/Web Push komponensek a telepített programcsomag részei, de a telefonos PWA telepítés és notification permission továbbra is felhasználói művelet HTTPS originről.
- A Tailscale/cloudflared telepítés az alkalmazás meglévő Windows Package Manager integrációját használja.
- Az MSI továbbra is per-user, x64, major-upgrade kompatibilis csomag.
- A 5.2.16 publikus unsigned MSI release változatlanul megmarad a folyamatban lévő SignPath Foundation jelentkezés hivatkozott előfeltételeként.

Kiadási csatorna: **stable**.
Release build: **5.2.17**.
API: **19**.
Release validation: **GitHub-hosted Windows build + MSI build + telepített runtime/API smoke-test + uninstall contract**.

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
