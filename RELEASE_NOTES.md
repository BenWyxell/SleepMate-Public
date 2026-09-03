# SleepMate 5.3.7

Release build: **5.3.7**.
Kiadási csatorna: **stable**.

A 5.3.7 a PWA stabilitására, az AI-elemzés használhatóságára és az O2Ring megjelenítés/export finomítására fókuszáló hibajavító kiadás.

## AI elemzés és külső prompt

- A külső AI-hoz másolt prompt most kifejezetten közérthető, magyar nyelvű, jól tagolt felhasználói kiértékelést kér JSON/kód jellegű válasz helyett.
- Ha több elemzési mód érhető el, az **Elemzés indítása** választóból külön indítható Luna, Milo vagy a külső AI-hoz készülő prompt.
- A Luna/Milo és a promptolás továbbra is egymástól függetlenül kapcsolható.

## PWA stabilitás és mobil UX

- Stabilabb cold-start és shell/cache kezelés: a service worker aktiválása nem navigálja újra a PWA-t betöltés közben.
- Javult a SleepSync és az Oximetria első betöltésének/hidratálásának megbízhatósága.
- Az alsó navigáció nevének szerkesztése mobilon nem okoz zavaró automatikus nagyítást.
- Az oximetriás grafikonok mobil érintési feliratai olvashatóbb pozícióba kerülnek, a zoomolt X tengely sűrűbben és dinamikusabban skálázódik, a dupla koppintás pedig visszaállítja a teljes nézetet.

## Oximetria a napi nézetben

- A részletes napi nézet SpO₂- és pulzuskártyái nem mutatnak téves „nincs adat” állapotot betöltés közben.
- Az O2Ring napi értékek bekerülnek a Szekciók táblázatába.
- A PWA napi megosztás képi/szöveges összegzése O2Ring-adat esetén SpO₂- és pulzusinformációkat is tartalmaz.

## O2Ring export és OSCAR

- Az eredeti nyers `.vld` fájl változatlanul megmarad az exportban.
- Minden nyers O2Ring felvétel mellé byte-azonos `.dat` példány is készül az OSCAR-kompatibilis importhoz.
- Az export OSCAR/VLD és OSCAR/DAT almappákba rendezi a két változatot.

## Backup

- A teljes és automatikus SleepMate backup továbbra is megőrzi az O2Ring recordingokat, nyers VLD-ket, O2Ring-beállításokat, valamint az AI- és PWA-beállításokat.

Ez a kiadás nem változtatja meg a SleepSync hosszú távú kompatibilitási markereit, és nem módosítja a felhasználó eredeti O2Ring nyers fájljait.

---
# SleepMate 5.3.6

A SleepMate 5.3.6 a v5.3.5 stabil alapjára épülő funkcionális frissítés, amely főként az O2Ring automatikus adatkezelését, az exportot, a mobil PWA használhatóságát és az AI-kezelést bővíti.

## O2Ring

- Új teljes O2Ring export készült az összes helyben tárolt lezárt méréshez.
- Minden export külön időbélyeges mappába készül `OSCAR`, `CSV` és `Excel` alkönyvtárral.
- Az OSCAR könyvtár az eredeti nyers felvételek másolatát kapja, a CSV és az egyszerű XLSX pedig az összes mintát egy közös időrendi adatkészletben tartalmazza.
- Az exportálási alapmappa kiválasztható és megmarad újraindítás után is.
- Export előtt a SleepMate megpróbálja a meglévő O2Ring szinkronmechanizmussal letölteni az új lezárt méréseket, aktív mérés megszakítása nélkül.
- A gyűrű levétele utáni automatikus szinkron kontrollált retry mechanizmust kapott, amely kezeli a késve megjelenő VLD fájlt és a rövid BLE reconnectet is.
- A periodikus fallback automatikusan felismerheti az új, korábban még nem letöltött lezárt fájlokat, miközben a meglévő deduplikáció megmarad.

## Mobil PWA és felület

- Az Oximetria mobil grafikonjain ritkább és reszponzívabb X-tengely feliratok csökkentik az időpontok egymásra csúszását kis kijelzőn.
- A mobil navigáció és safe-area kezelés finomodott; az alsó PWA navigáció nem takarja a használható felületet.
- Az alsó PWA navigáció megjelenített feliratai személyre szabhatók és alapértékre visszaállíthatók a belső route-ok megváltoztatása nélkül.
- Telefonos PWA-ban a háttér szaggatásának elkerülésére a költséges díszítő SVG/aurora mozgás statikussá válhat, desktopon az animáció megmarad.
- A `prefers-reduced-motion` beállítás tiszteletben marad.

## AI és Luna/Milo

- Luna és Milo megjelenítése külön szabályozható.
- Az AI promptolás külön kapcsolót kapott, ezért a vizuális Luna/Milo jelenlét és az AI prompt használata egymástól függetlenül vezérelhető.
- Az AI összegzésből elérhető a teljes, kanonikus prompt/adatcsomag.
- A prompt modalból másolás, UTF-8 TXT mentés, valamint ChatGPT és Gemini megnyitása érhető el.
- A prompt felület mobilon is reszponzív.

## Egyéb javítások

- A legutóbbi terápia kártya állapotszöveg helyett a tényleges terápiás időt mutatja.
- A SleepSync mentett ütemezési állapota stabilabban jelenik meg a felület újratöltése után.
- Az O2Ring főkapcsoló kikapcsolt állapotában a hozzá tartozó felhasználói felület elrejthető az adatok törlése nélkül.

## Kiadási validáció

A kiadás a teljes publikus regressziós tesztkészleten, Windows program-tree builden, magyar WiX MSI builden, valódi `msiexec` telepítés/runtime/eltávolítás ellenőrzésen, release-integritás ellenőrzésen és valódi Microsoft Edge packaged acceptance teszten megy keresztül publikálás előtt.

Kiadási csatorna: **stable**.
Release build: **5.3.6**.
API: **19**.

---
# SleepMate 5.3.5

A SleepMate 5.3.5 a v5.3.4 O2Ring/PWA stabilitási körére épülő célzott felület- és adatmegjelenítési javítókiadás.

## Dashboard és napi nézet

- A SpO₂ és Pulzus kártyák a CPAP-idővel átfedő O2Ring adatok mediánját mutatják, magyar számformátummal.
- A Fókusznézetben két normál O₂ mini kártya marad; mindkettő a közös hero grafikonra nyílik.
- Az O₂ overlay jobb oldali SpO₂/HR skálát, pontos időpontú hovert és `Alapnézet` kikapcsolt állapotot használ.
- A Legutóbbi alvás kártya elsődlegesen a teljes terápiás/alvási időt mutatja, az Oximetriai összegzés pedig stabilan frissül.

## Jelentések és éjszakai értékelés

- A kiválasztott napok táblázata kompaktabb lett; a Napi statisztika SpO₂ és Pulzus minimum/medián/maximum értékeket mutat.
- SleepSync invalidáció után a Jelentések az aktuális, CPAP-idővel illesztett O2Ring summary értékeket használják.
- Az Éjszaka értékelése Oximetria kártyája csak SpO₂- és Pulzus-mediánt tartalmaz, normál grid-méretben.

## Oximetria és PWA stabilitás

- A Dashboard, Kapcsolódás, Szinkron, Élő O₂ monitor, Felvételek és Trendek egyetlen felső gombsorban jelennek meg; a külön nagy Állapot kártya megszűnt.
- Az O₂ grafikonok pontos HH:MM:SS hovert, crosshairt, zoom/pan/pinch/touch kezelést és gap-helyes vonalrajzolást használnak.
- A Live O₂ csak látható Élő nézetben dolgozik; elhagyáskor a stream lezár, visszatéréskor bounded refill után folytatódik.
- Az első PWA-megnyitás, stale-cache helyreállítás, ismételt navigáció és iPhone portrait/landscape geometria regresszióteszttel védett.

## Kiadási validáció

A v5.3.5 kiadási kapuja ugyanazon exact commiton ellenőrzi a source contractokat, a Windows x64 programfa buildet, a magyar WiX MSI-t, a valódi install/API/uninstall smoke-testet, a VERIFIED hash/manifeszt/ZIP/MSI identity-t és a valódi Microsoft Edge packaged acceptance-et.

Kiadási csatorna: **stable**.
Release build: **5.3.5**.
API: **19**.

---
# SleepMate 5.3.0

A SleepMate 5.3.0 a 5.2.20 stabil publikus alapjára épülő nagy funkcionális kiadás. Bevezeti az opcionális O2Ring oximetriai integrációt, a CPAP- és oximetriai adatok közös idővonalas elemzését, valamint az Aurora/PWA felületfrissítést úgy, hogy az O2Ring funkció kikapcsolt állapotban ne változtassa meg a hagyományos SleepMate használatát.

## O2Ring – valóban opcionális integráció

- Az **O2Ring integráció alapértelmezetten ki van kapcsolva**.
- Kikapcsolt állapotban nincs Oximetria menüpont, O2/pulzus kártya, napi oximetriai mód, trend, PDF-opció, üres hely vagy BLE háttérmunka; a fő felület a 5.2.20 működését és elrendezését követi.
- A Beállításokban egyetlen integrációs kapcsolóval aktiválható a funkció.
- Kikapcsoláskor a korábban eltárolt O2Ring adatok **nem törlődnek**; újbóli engedélyezés után ismét elérhetők.
- A külön Bluetooth kapcsoló, automatikus kapcsolódás és automatikus szinkron beállítások nem felejtik el a korábban kiválasztott gyűrűt.

## Közvetlen Windows Bluetooth LE kapcsolat

- A SleepMate közvetlenül a Windows Bluetooth LE rétegén kommunikál a kompatibilis Wellue/Viatom O2Ring családdal; külön mobilalkalmazás vagy külön O2Ring CLI nem szükséges.
- A Windows build a **Bleak 3.0.2** és a szükséges **PyWinRT 3.2.1** komponenseket tartalmazza.
- A kiválasztott gyűrű megjegyezhető, az automatikus csatlakozás és a tárolt felvételek szinkronja külön szabályozható.
- A BLE életciklus közös, biztonságos stop/start kaput használ. A gyors OFF→ON váltás, eszköz elfelejtése, adat-törlés és backup-visszaállítás nem hagyhat félbehagyott háttérfolyamatot.
- Az O2Ring kikapcsolt állapotában a connect/sync útvonalak sem indíthatnak Bluetooth munkát.

## Élő oximetria, felvételek és trendek

- Élő monitor mutatja a rendelkezésre álló **SpO₂**, pulzus, akkumulátor, jelállapot és eszközállapot adatokat.
- Az élő SpO₂- és pulzusgörbék együtt követhetők.
- A gyűrűn tárolt VLD felvételek közvetlenül letölthetők és helyileg feldolgozhatók.
- Külön **Felvételek** és **Trendek** nézet készült.
- A SleepMate az oximetriai összegzésben többek között átlagos/medián/minimum SpO₂-t, pulzusstatisztikát, T90-et, ODI3/ODI4-et és lefedettséget számol.
- A felhasználói felületen a nem igazolt perfúziós index helyett a ténylegesen rendelkezésre álló **pulzus-jelerősség** megnevezés szerepel.

## CPAP + O2Ring közös éjszakai elemzés

- Az O2Ring felvételek nem pusztán dátum alapján, hanem a **valós időintervallum átfedése** alapján illeszkednek a PAP sessionökhöz.
- A napi nézet Oximetria módja csak a PAP-terápiával ténylegesen átfedő mintákat használja.
- Közös CPAP/SpO₂/pulzus idővonal segíti annak áttekintését, mi történt ugyanabban az éjszakai időszakban.
- Az óraeltolás külön beállítással korrigálható.
- A T90 számítása a mintavételi időközt veszi figyelembe, ezért az érvénytelen vagy hiányzó minták nem növelik mesterségesen a deszaturációs időt.

## PDF és AI

- A PDF-jelentés opcionális **Oximetria / Pulzus** részt kapott SpO₂-, T90-, pulzus-, ODI- és lefedettségi mutatókkal és grafikonokkal.
- Az O2 PDF-rész csak engedélyezett O2Ring integrációnál jelenik meg.
- Az AI/Luna/Milo felé **nem kerül nyers VLD, teljes oximetriai mintasor, Bluetooth-cím, eszközazonosító, recording ID vagy forrásfájlnév**.
- AI-elemzéshez kizárólag adatminimalizált, PAP-időszakra illesztett összesített oximetriai mutatók használhatók.
- Az oximetriai és AI-következtetések továbbra is tájékoztató jellegűek; a SleepMate nem orvosi diagnosztikai szoftver.

## Helyi adatkezelés, törlés és backup

- A SleepMate a feldolgozott O2Ring felvételeket és az eredeti VLD állományokat a felhasználó helyi SleepMate adattárában őrzi.
- A helyi O2Ring mérési adatok külön, explicit megerősítéssel törölhetők a gyűrű elfelejtése nélkül.
- A törlés után tombstone-lista akadályozza meg, hogy a gyűrű saját memóriájában még meglévő, már törölt felvétel egy későbbi automatikus szinkronnal észrevétlenül visszakerüljön.
- A teljes SleepMate backup tartalmazza az O2Ring helyi állapotát és felvételeit is.
- Backup visszaállítás előtt a BLE worker teljesen leáll, majd a visszaállított O2-konfigurációból és fájlokból új runtime épül.
- Régi, O2Ring előtti backup visszaállítása nem örökli véletlenül az új gép gyűrűpárosítását; az O2Ring ilyenkor biztonságos alapértékekre áll vissza.
- A frissített adatvédelmi tájékoztató külön ismerteti az O2Ring helyi adattárolását, BLE-azonosítóit, backupját, távoli PWA-elérését és AI-adatminimalizálását.

## Aurora és PWA felület

- A v5.3 új **Aurora / Northern Lights** vizuális réteget kapott: mély éjszakai háttér, csillagok, fényívek és finom aurora-effektek adják a nem kártya jellegű felületek hátterét.
- A kártyák olvashatósága és az adatok kontrasztja megmaradt; a vizuális effekt a tartalom mögött dolgozik.
- A mobil/PWA navigáció dinamikusan alkalmazkodik a ténylegesen elérhető menüpontokhoz, ezért az O2Ring ki- és bekapcsolása nem hagy üres navigációs helyet.
- Safe-area és kisebb mobil szélességekhez külön reszponzív szabályok kerültek a v5.3 shellbe.

## Stabilitás és regressziós védelem

- A v5.3 forrása közvetlenül a publikus **v5.2.20** release-ből származik; a korábbi, divergált fejlesztési ágra épülő O2Ring próbaváltozat nem lett kiadási alap.
- Külön regressziótesztek védik az O2 master OFF állapotot, BLE protokollt és életciklust, VLD feldolgozást, oximetriai összegzést, eszközkonfigurációt, PDF contractot, adat-törlést/tombstone-t, AI-adatminimalizálást és backup/restore rehidratálást.
- A Windows release locked Bleak/PyWinRT függőségekkel, PyInstallerrel és rögzített WiX Toolset 3.14.1 toolchainnel készül.
- A kiadás csak publikus forrás-higiénia, teljes pytest-készlet, Windows program-tree build, magyar MSI build és payload-ellenőrzés, valódi MSI install/runtime/API/uninstall smoke-test, valamint VERIFIED hash/integritás kapu után publikálható.

## Hardvervalidáció

A CI a Windows BLE runtime csomagolását, az O2Ring protokollkeretezést, parser-logikát és alkalmazásintegrációt hardver nélkül ellenőrzi. A különböző fizikai O2Ring firmware-verziók és rádiós környezetek miatt a valódi gyűrűvel történő BLE kommunikáció továbbra is eszközspecifikus terepi validációt igényel; a release nem állítja, hogy minden gyártói firmware-variánst fizikai hardveren automatizáltan teszteltünk.

Kiadási csatorna: **stable**.
Release build: **5.3.0**.
API: **19**.
Release validation: **publikus forrás-higiénia + teljes regressziós tesztkészlet + PyInstaller Windows build + magyar WiX MSI + valódi install/runtime/O2/PWA/uninstall smoke + VERIFIED release hash/manifeszt/integritás gate + ellenőrzött GitHub publication**.

---

# SleepMate 5.2.20

A SleepMate 5.2.20 a frissítési folyamatot végleges, felhasználóbarát publikus csatornára állítja, és egyértelművé teszi a korábban mentett Cloudflare hostname eredetét.

## Hivatalos, tokenmentes frissítési csatorna

- A SleepMate frissítési forrása fixen a publikus **`BenWyxell/SleepMate-Public`** GitHub repository.
- A felhasználónak többé nem kell repository-nevet vagy GitHub tokent megadnia.
- A Beállításokból kikerült a GitHub repository mező, a tokenmező és a mentett token törlése.
- A kliens nem éget be közös GitHub tokent, és frissítésellenőrzéskor nem küld `Authorization` fejlécet.
- Korábbi verzióból esetleg megmaradt updater token automatikusan törlésre kerül és nem használható fel.
- Az automatikus ellenőrzés induláskor, majd **12 óránként** lefut; telepítés továbbra is csak kifejezett felhasználói jóváhagyással indul.
- A kézi **Frissítés keresése** és **Frissítés telepítése** funkció megmaradt.
- A release manifest, SHA-256 ellenőrzés, teljes frissítés előtti backup és automatikus rollback változatlanul kötelező.

## Cloudflare első beállítás

- Ha a Cloudflare hostname egy korábban mentett SleepMate konfigurációból kerül visszatöltésre, a wizard ezt külön **„Korábban mentett SleepMate-beállítás.”** jelöléssel mutatja.
- A jelölés eltűnik, amint a felhasználó szerkeszteni kezdi a hostname mezőt.
- Így egy régi domain többé nem tűnik automatikusan generált vagy a SleepMate által kitalált címnek.
- A first-run loader új cache-generációt kapott, hogy a régi wizard JavaScript/CSS ne ragadhasson bent.

## Validáció

- publikus forrás hygiene gate
- Python + JavaScript syntax/contract tesztek
- publikus updater credential-mentességi regresszióteszt
- Cloudflare hostname provenance regresszióteszt
- teljes publikus pytest-készlet
- PyInstaller Windows program-tree build
- magyar WiX MSI build + payload ellenőrzés
- valódi MSI install / backend API / uninstall smoke-test
- ZIP/manifeszt/MSI SHA-256 és VERIFIED release-set
- GitHub publikálás kizárólag minden kapu sikere után

Kiadási csatorna: **stable**.
Release build: **5.2.20**.
API: **19**.
Release validation: **teljes publikus tesztkészlet + Windows program-tree + magyar MSI + valódi install/runtime/API/uninstall smoke-test + release hash/manifeszt/integritás gate + verified GitHub publication**.

---

# SleepMate 5.2.19

A SleepMate 5.2.19 a Windows első-indítási varázsló görgetésének második, szerkezeti javítása. A v5.2.18-ban használt grid-alapú `minmax(0,1fr)` megoldás egyes tényleges desktop layout-helyzetekben továbbra is hagyta, hogy a panel min-content magassága az alsó navigáció alá nyúljon. A v5.2.19 ezért nem finomhangolja tovább ezt a modellt, hanem a teljes wizardot kényszerített flex-oszlopos felépítésre váltja.

## Első beállítás – kényszerített globális scroll

- A wizard külső shellje most `display:flex; flex-direction:column` elrendezést használ.
- A fejléc és az alsó navigáció `flex:0 0 auto`, ezért egyik sem zsugorodik és egyikre sem tud ráfolyni a tartalom.
- A középső `.fr-body` kapta a tényleges görgetési felelősséget: `flex:1 1 0`, `height:0`, `min-height:0`, `overflow-y:scroll!important`.
- A teljes overlay `overflow:hidden`, így a háttéroldal vagy a shell nem veheti át véletlenül a görgetést.
- A wizard teljes belső fája egységes `box-sizing:border-box` szabályt kapott, hogy padding vagy inputméret se növelhesse meg kiszámíthatatlanul a rendelkezésre álló magasságot/szélességet.
- A footer háttere közel teljesen fedett, így görgetés közben a tartalom vizuálisan sem látszik át a gombsor mögött.
- Tailscale, Cloudflare, adatforrás, SleepSync, backup, AI és összegzés továbbra is **ugyanazt az egy közös scrollterületet** használja; nincs lépésenkénti külön scroll.
- A `first-run.js` és `first-run.css` cache-bustja `v3` lett, a csomagolt onboarding loader is `first-run.js?v=3`-at kér.

## Regressziós védelem

- A külön onboarding teszt már nem egyszerű `overflow:auto` jelenlétet ellenőriz, hanem a teljes flex-szerződést: fix fejléc, kényszerített középső scroll, fix footer, globális box-sizing és cache-bust.
- A fő Windows packaging contract ugyanezt a struktúrát követeli meg a kiadható MSI-ben.
- A release előtt továbbra is lefut a teljes publikus tesztkészlet, a PyInstaller build, a magyar WiX MSI, a valódi MSI telepítés/backend/API/uninstall smoke-test és a VERIFIED release-integritási lánc.

Kiadási csatorna: **stable**.
Release build: **5.2.19**.
API: **19**.
Release validation: **teljes publikus tesztkészlet + Windows program-tree + magyar MSI + valódi install/runtime/API/uninstall smoke-test + release hash/manifeszt/integritás gate + verified GitHub publication**.

---

# SleepMate 5.2.18

A SleepMate 5.2.18 a Windows első-indítási beállítóvarázsló használhatósági javítása. A cél az volt, hogy a wizard ne csak a Tailscale / Cloudflare résznél, hanem **minden olyan lépésen belül görgethető legyen, ahol a tartalom ezt igényli**, miközben a fejléc és az alsó navigáció végig a helyén marad.

## Első beállítás – globális görgetés

- A teljes varázsló középső tartalmi területe közös, függőlegesen görgethető felületet kapott.
- A scroll nem egyetlen lépéshez kötött: adatforrás, SleepSync, Tailscale, Cloudflare, backup, AI és összegzés közben is működik, ha a tartalom túlnő az ablakon.
- A felső fejléc és az alsó `Vissza` / `Tovább` navigáció a görgethető tartalmon kívül marad.
- Kisebb desktop ablakmagasságnál és mobil nézetben is külön magasságkezelés biztosítja, hogy a tartalom elérhető maradjon.
- Lépésváltáskor a wizard tartalma visszaáll a tetejére.
- A wizard megnyitásakor a mögötte lévő főoldal görgetése tiltott, így nem a háttéroldal mozdul el.

## Desktop onboarding egyszerűsítés

- A hibás / villogó brand-logókép kikerült a wizard fejlécéből.
- A **PWA telepítés és Web Push / értesítési engedély** kikerült az első desktop beállításból; ezek nem részei többé a wizardnak.
- Az 5. lépés most kizárólag az opcionális **automatikus backup és AI** beállításokat kezeli.
- A `first-run.js` és `first-run.css` loader cache-bustja frissült, hogy a böngésző ne tartsa bent a korábbi wizard-verziót.

## Regressziós védelem

- Külön teszt tiltja, hogy a PWA/Web Push onboarding-elemek visszakerüljenek.
- A fő Windows packaging contract is ellenőrzi a globális scroll-szerződést és az új cache-bustot.
- A release előtt továbbra is lefut a teljes publikus tesztkészlet, a PyInstaller build, a magyar WiX MSI, a valódi MSI telepítés, backend/API smoke, eltávolítás, state-megőrzés, ZIP/MSI/manifeszt hash- és tartalomellenőrzés.

Kiadási csatorna: **stable**.
Release build: **5.2.18**.
API: **19**.
Release validation: **teljes publikus tesztkészlet + Windows program-tree + magyar MSI + valódi install/runtime/API/uninstall smoke-test + release hash/manifeszt/integritás gate + verified GitHub publication**.

---

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
- A CI ellenőrzi a publikus forrás tisztaságát, Python/JavaScript szintaxist, a csomagolási contractokat, a teljes publikus tesztkészletet, a Windows program-tree buildet, a ZIP/manifeszt hash- és tartalomkonzisztenciáját, az MSI payloadot, a valódi telepítést, a telepített backend API-kat, SleepSyncet, Google Drive státuszt, onboardingot, Web Push-t, a leállítást, az eltávolítást és a felhasználói állapot megőrzését.
- A GitHub Release publikálása kizárólag a sikeres smoke-test és a külön release-integritási kapu után, az ugyanabban a workflow-ban létrehozott **VERIFIED** artifactból történhet.
- A production Authenticode-aláírás egyelőre nincs bekapcsolva; a SignPath aláírás a trusted build láncra kerül majd. Emiatt a Windows jelenleg SmartScreen vagy vírusvédelmi reputációs figyelmeztetést jeleníthet meg.

Kiadási csatorna: **stable**.
Release build: **5.2.17**.
API: **19**.
Release validation: **teljes publikus tesztkészlet + Windows program-tree + magyar MSI + valódi install/runtime/API/uninstall smoke-test + release hash/manifeszt/integritás gate + verified GitHub publication**.

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
