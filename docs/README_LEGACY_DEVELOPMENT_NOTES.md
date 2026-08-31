# SleepMate v4.2.0

## v4.2.0 – Védett elsődleges forrástükrözés

- Az **alapértelmezett/elsődleges ResMed adatforrás** most valódi, védett tükörszinkront használ: új fájl hozzáadódik, módosult fájl byte-pontosan frissül, a forrásból eltűnt korábbi elsődleges fájl pedig eltűnik a SleepMate aktív mérési adattárából.
- Törlés csak teljesen olvasható, két egymást követő azonos forráspillantkép után engedélyezett. Instabil, félkész vagy hibásan olvasható SD/EzShare/megadott forrás esetén **nincs destruktív törlés**.
- A forrásból törölt gépi fájlok nem semmisülnek meg: a SleepMate `private/sync_quarantine` könyvtárába kerülnek visszaállítható biztonsági másolatként. A karantén legfeljebb 10 köteget / 30 napot tart meg, és nem duzzasztja a normál teljes backupot.
- A SleepMate nyilvántartja, mely fájlok tartoztak az elsődleges forráshoz. Emiatt egy korábban **kézi ZIP/mappa importtal** bekerült, az elsődleges forrásban sosem szereplő terápiás napot a tükörszinkron nem töröl ki.
- ZIP, kézi mappaimport és SD-keresés továbbra is hozzáadó/frissítő módú; ezek egy részleges adathalmazból soha nem következtetnek más napok törlésére.
- A kézzel rögzített páciens-, megjegyzés-, felszerelés- és egyéb adatok külön adattárban maradnak és a mérési tükörszinkron nem érinti őket.
- A Windows mappaválasztó csak kifejezett **Tallózás** gombnyomásra nyílhat meg, és nem a TEMP mappából indul. A háttérfrissítés/backup/import nem nyit Intéző- vagy TEMP-ablakot.
- A publikus verzió- és PWA cache-nevek visszatértek a normál `4.2.0` verziózáshoz; nincsenek `TEST_*` / `mobile*` kiadásnevek.

---

## v4.1.7 – Teljes backup visszatöltés: Windows zárolt futásidejű naplók

Javítás:
- a `private/service_startup.log` visszatöltés közben többé nem kerül törlésre vagy felülírásra;
- ugyanez érvényes a futásidejű `launcher.log` és `system_log.jsonl` naplókra;
- ezek a fájlok a jelenleg futó SleepMate példányhoz tartoznak, nem a visszaállítandó felhasználói állapothoz;
- a kezelt személy, felszerelések, profilkép, AI-adatok, beállítások és CPAP/EDF mérési tár továbbra is teljesen visszaáll;
- régebbi backup ZIP-ek is visszatölthetők akkor is, ha tartalmazzák ezeket a naplókat.

A v4.1.6 trenddiagram-javításai és minden korábbi PWA/backup javítás megmaradt.

## SYNC FIX – byte-pontos ResMed frissítés

- Minden indításkor ellenőrzi az alapértelmezett ResMed forrást.
- Azonnali, ütemezett, kézi mappa/SD, SD-keresés és ZIP import ugyanazt a közös szinkronlogikát használja.
- A már meglévő fájlokat byte-ról byte-ra hasonlítja össze; a méret és a módosítási idő önmagában nem dönthet az azonosságról.
- A változott fájlok atomikusan, ellenőrzött másolással kerülnek a private/measurement tükörbe.
- Párhuzamos importok egymást kizárják.
- A kezelt személyhez kézzel rögzített adatok külön SQLite-adattárban maradnak, az EDF frissítés nem törli őket.


## v4.1.7 mobile1 – Mobil/PWA csomag
- Mobil alsó navigáció, gyorsnézet és pull-to-refresh.
- Napi nézet swipe, natív megosztás PNG összefoglalóval.
- Touch/drag kurzor a trendeken és részletes grafikonokon; kétujjas pinch zoom + dupla kopp reset.
- API 502/503/504 újrapróbálás és felhasználóbarát hibaüzenet.
- PWA offline utolsó adatok service-worker API cache-ből.
- PWA státusz és opcionális értesítések.

## v4.1.7 mobile2 – PWA mobilfelület + valódi Web Push

- A korábbi mobil gyorsnézet kikerült; a Dashboard nem ismétli meg ugyanazokat az adatokat kétszer.
- A normál böngészős web és a telepített PWA ugyanazt a felületet és funkciókat használja. Az alsó mobil navigáció csak telepített, standalone PWA módban jelenik meg.
- Új, teljes szélességű, a telefon aljához simuló PWA navigáció: Dashboard, Napok, Diagrammok, Luna & Milo, Egyéb; egységes SVG ikonokkal.
- A napi lapváltás látványos kártyás swipe animációt és irányjelzést kapott, hogy a napváltás egyértelmű legyen.
- A részletes napi nézet Fókusz és Összes diagram módja egységes mobil gesztusokat használ: kétujjas zoom, egyujjas vízszintes pan nagyítás után, dupla kopp visszaállítás.
- A Dashboard trenddiagramjain a függőleges görgetés elsőbbséget kap; az érintési követővonal elengedéskor, görgetéskor és oldalváltáskor eltűnik.
- A Luna & Milo AI chat mobil/PWA nézete telefonhoz igazított elrendezést, üzenetbuborékokat és beviteli sort kapott.
- Offline PWA: hálózat/szerverhiba esetén a service worker a gyorsítótárazott alkalmazást és az utolsó sikeresen betöltött adatokat próbálja megjeleníteni; ha még nincs cache, márkázott offline képernyőt ad a fehér oldal helyett.
- Valódi Web Push: a SleepMate backend első használatkor automatikusan létrehozza és helyben tárolja a VAPID kulcspárt. A privát kulcs nem kerül a böngészőbe.
- Új Beállítások → PWA értesítések rész: feliratkozás, leiratkozás, tesztküldés és külön kapcsolók az új éjszaka, adatfrissítés, diagnosztikai figyelmeztetés és backup-hiba értesítéseire.
- A push a szerverről érkezik, ezért a telepített PWA teljes bezárása mellett is kézbesíthető, ha a SleepMate backend fut és van internetkapcsolata.

### Frissítés után egyszer szükséges

Futtasd a `SleepMate_fuggosegek_telepitese.bat` fájlt, mert a valódi Web Push új Python-függőséget (`pywebpush`, illetve a VAPID kulcskezeléshez `cryptography`) használ.

### iPhone Web Push feltételei

- A SleepMate-et a Főképernyőre telepített PWA-ként kell megnyitni.
- A PWA-nak HTTPS biztonságos kapcsolaton kell futnia.
- Ezután: **Beállítások → PWA értesítések → Értesítések bekapcsolása**.
- A VAPID kulcsokat nem kell kézzel létrehozni vagy megadni; a SleepMate kezeli őket.

## v4.1.7 mobile3 – backup/push javítás + kompakt mobil UI

- **Teljes backup visszatöltés:** a Web Push `private/push/push.sqlite3` adatbázisa többé nem marad nyitott Windows fájlhandle-lel. Minden push SQLite kapcsolat explicit bezárul.
- A teljes backup most fájlkiterjesztéstől függetlenül SQLite-aláírás alapján készít konzisztens snapshotot, ezért a `.sqlite3` push-adatbázis is biztonságosan menthető/visszatölthető.
- Régebbi, még nyers `push.sqlite3` fájlt tartalmazó teljes backup is visszaállítható.
- Restore alatt a push műveletek karbantartási zárral szünetelnek, majd a PushService a visszaállított állapotból újraépül.
- **Próbaértesítés:** közvetlenül az aktuális telefon push endpointjára küld; sikertelenségnél a szerver tényleges hibáját megmutatja. A VAPID subject iOS-kompatibilis HTTPS URI.
- **Beállítások mobilon:** a hosszú felső gombsor helyett egy kompakt, lenyitható kategóriaválasztó jelenik meg.
- **Gesztusok:** a telefon bal széle kizárólag a hamburger/drawer kihúzásáé. Éjszakaváltó swipe csak a részletes napi Dashboard útvonalon működik, a diagramok saját pinch/pan gesztusait nem veszi el.
- **Luna & Milo mobilon:** a hosszú „Mit értékeljünk?” kártyalista helyett egyetlen kompakt választógomb nyit telefonos alsó választólapot. A hónap és időszak-összehasonlítás is innen indítható.
- Az AI adatkészlet-verzió jelvénye mobilon kisebb, visszafogott pill lett.
- Service-worker/cache verzió frissítve, hogy a PWA biztosan az új mobil felületet töltse be.


## v4.1.7 mobile4 – AI mobil + Web Push VAPID javítás

- Web Push: a korábbi localhost VAPID subjectet a mobile5 javítás felülírja valódi HTTPS PWA-originnel.
- AI mobil: rövidebb nyitóblokk, felesleges marketing/chip sor nélkül, középre igazított kompakt napi kérdéskeret és kisebb Luna/Milo választó.
- AI chat: iOS-on 16 px-es tényleges textarea betűméret, ezért fókuszkor nincs automatikus Safari/PWA zoom. A mező egy sor magasról indul, és tartalom szerint nő legfeljebb kb. 118 px-ig.
- Service worker cache: `v4.1.7.4`, hogy az új CSS/JS biztosan lecserélje a korábbi PWA cache-t.


## v4.1.7 mobile5 – Apple Web Push + dupla PWA splash javítás

- Apple Web Push: a VAPID `sub` claim most nem localhost ál-cím. A SleepMate a feliratkozó PWA tényleges HTTPS originjét (például Tailscale/Cloudflare címet) menti és használja.
- A push-feliratkozás elmenti azt a VAPID publikus kulcsot is, amellyel készült. Ha backup/frissítés után a szerver kulcsa eltér, a PWA automatikusan újrafeliratkozik.
- Próbaértesítésnél `BadJwtToken` esetén a PWA egyszer automatikusan újraépíti a feliratkozást és újrapróbálja a küldést.
- iPhone telepített PWA-ban az iOS saját natív launch screenje marad az egyetlen betöltőképernyő; az utána következő HTML splash nem jelenik meg.
- Service worker frissítés standalone PWA-ban nem kényszerít azonnali teljes újratöltést, így abból sem keletkezik második splash.
- Service worker cache: `v4.1.7.5`.

## v4.1.7 mobile6 – egyszeri PWA betöltő + drawer/history + push duplikáció

- Telepített PWA-ban ismét a SleepMate saját animált indulóképernyője jelenik meg, egy dokumentumindítás alatt pontosan egyszer.
- Standalone PWA-ban a belső menünavigáció nem épít WebKit böngésző-előzményt, ezért a bal szélről kihúzott hamburger menü nem tud előbb egy korábbi oldalra visszalépni.
- A bal szélső 48 px vízszintes gesztus aktívan a drawerhez tartozik; a függőleges görgetés változatlan marad.
- Diagnosztikai push csak új vagy ténylegesen megváltozott CPAP-adat után mehet ki. Byte-azonos újraellenőrzés, backup készítés/visszatöltés önmagában nem küldi újra a régi figyelmeztetést.
- A diagnosztikai push szövege emberi formátumú, nem Python dict reprezentáció.
- PWA shell cache: v4.1.7.6.

## SleepMate ikon

A csomag gyökerében található `SleepMate.ico` a SleepMate Windows-ikonja. A Windows `.vbs` fájlok ikonját nem engedi fájlonként közvetlenül lecserélni, ezért a `SleepMate.vbs` első indításkor automatikusan létrehozza/frissíti a mellette lévő `SleepMate.lnk` parancsikont ezzel az ikonnal. A tálcaikon is ugyanezt a `SleepMate.ico` fájlt használja.


## 4.2.1
- Javítva az önellenőrzés SQLite téves riasztása: csak az aktív `private/patient.db` és `private/push/push.sqlite3` adatbázisok kerülnek ellenőrzésre.
- Az önellenőrzés most pontosan megadja, hány aktív adatbázisból hány hibás, és hiba esetén a fájl nevét + `PRAGMA integrity_check` eredményét is naplózza.
- A szervizcsomag SQLite-séma része sem vizsgál régi/staging/backup adatbázismásolatokat.
