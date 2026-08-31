# SleepMate

**Local-first ResMed PAP/CPAP therapy data viewer, analysis workstation, reporting system and ez Share / SleepSync synchronization platform for Windows and installable PWA use.**

**Current source snapshot:** SleepMate 5.2.16 · API 19 · stable channel  
**License:** GNU Affero General Public License v3.0 only (AGPL-3.0-only)  
**Publisher / developer:** SleepMate projekt – BenWyxell – Kovács Lóránd E.V.  
**Contact:** hello@mysleepmate.hu

[🇭🇺 Magyar funkcióleírás](#magyar) · [🇬🇧 English feature reference](#english)

> [!IMPORTANT]
> **SleepMate is not medical diagnostic software and does not replace a physician, sleep laboratory, PAP titration or professional medical advice.** Its calculations, visualizations, alerts and optional AI-generated texts are informational tools for reviewing the user's own PAP therapy data. It does not diagnose disease and does not automatically change therapy pressure or medication.

---

<a id="magyar"></a>
# 🇭🇺 Magyar

## 1. Mi a SleepMate?

A **SleepMate** egy Windows-központú, helyi működésre tervezett PAP/CPAP terápiás adatkezelő és elemző rendszer. Elsődleges célja, hogy a ResMed készülékek SD-kártyáján található részletes terápiás adatokat a felhasználó saját számítógépén olvassa be, rendszerezze, vizualizálja, összehasonlítsa, jelentésekbe rendezze, és – ha a felhasználó külön engedélyezi – opcionális külső szolgáltatásokkal egészítse ki.

A SleepMate nem egy egyszerű „AHI-néző”. A program egyetlen felületbe kapcsolja össze:

- a részletes ResMed EDF adatimportot;
- a napi és hosszú távú terápiás Dashboardot;
- a nagy felbontású jelgörbéket és légzési eseményeket;
- az alvásblokkok és PAP-munkamenetek külön elemzését;
- a kezelt személy egészségügyi és terápiás nyilvántartását;
- a diagnózis-, titrálás-, előírás-, gyógyszer- és terápiatörténetet;
- a PAP-készülékek, maszkok és kiegészítők nyilvántartását;
- a nyomtatható és exportálható PDF-jelentéseket;
- az opcionális, saját API-kulccsal működő Gemini/Groq AI-kiértékelést;
- az automatikus helyi backupot és teljes rendszer-visszaállítást;
- az opcionális Google Drive backup-másolatot;
- a Tailscale és Cloudflare alapú távoli PWA-hozzáférést;
- a Web Push értesítéseket;
- a diagnosztikai és támogatási naplókat;
- valamint az integrált **SleepSync** modult, amely kompatibilis **ez Share Wi-Fi SD** megoldásról képes biztonságosan letölteni és importálni a ResMed SD-kártya tartalmát.

A rendszer alapelve: **a terápiás és egészségügyi adat elsődleges helye a felhasználó saját számítógépe**.

---

## 2. Fő működési modell – local-first

A SleepMate normál helyi használatához:

- nem szükséges központi SleepMate-fiók;
- nincs központi SleepMate egészségügyi adatbázis;
- nincs kötelező SleepMate-felhő;
- nincs automatikus terápiás adatküldés a fejlesztőnek;
- nincs kötelező egészségügyi telemetria;
- a fejlesztő nem látja a felhasználó Dashboardját, EDF fájljait, diagnózisát, gyógyszereit vagy AI-előzményeit;
- a külső szolgáltatások – Google Drive, Gemini, Groq, Tailscale, Cloudflare – opcionálisak, és külön felhasználói beállítást igényelnek.

A SleepMate saját privát adattárában tárolt érzékeny konfigurációk meghatározott részei **256 bites AES-GCM** védelemmel tárolhatók. Ide tartozhatnak például API-kulcsok, OAuth tokenek és egyéb helyi titkos beállítások. A hordozhatóság érdekében a teljes rendszermentéshez szükséges kulcsanyag is a SleepMate helyi privát adattárának része, ezért maga a teljes backup érzékeny fájlnak minősül és megfelelően védendő.

A ResMed SD-kártya, az ez Share kártya és a kézzel kiválasztott importforrás **forrásként kezelendő**: a SleepMate importfolyamata nem arra épül, hogy a készülék eredeti SD-adatstruktúráját módosítsa vagy törölje.

---

## 3. Támogatott platform és alkalmazásmodell

A jelenlegi kiadási ág elsődleges célplatformja:

- **Windows x64**;
- helyi SleepMate háttérszolgáltatás;
- böngészőalapú, reszponzív felhasználói felület;
- telepíthető **PWA** ugyanazzal a felülettel és adatkészlettel;
- Windows tálcaalkalmazás és háttérben futó üzemmód;
- opcionális biztonságos távoli elérés Tailscale vagy Cloudflare segítségével.

A háttérszolgáltatás alapértelmezetten **loopback/localhost** elérésre készül, vagyis nem nyitja ki automatikusan a SleepMate-et a teljes helyi hálózat felé. A távoli elérés külön biztonsági rétegen keresztül kapcsolható be.

---

# 4. ResMed SD / EDF adatimport

## 4.1. Importálási módok

A SleepMate több útvonalon képes ugyanabba a kezelt terápiás adattárba importálni:

1. **Kézzel kiválasztott mappa** – például egy ResMed SD-kártya vagy annak másolata.
2. **Windows SD-meghajtó automatikus keresése** – a program felismeri a ResMed struktúrára utaló könyvtárakat és fájlokat.
3. **ZIP import** – korábban elmentett teljes SD-tartalom vagy kompatibilis ZIP importálható.
4. **Azonnali frissítés** – a beállított alapértelmezett forrásmappa újraellenőrzése.
5. **Ütemezett automatikus beolvasás** – a megadott forrásmappa időzítetten újraellenőrizhető.
6. **SleepSync / ez Share** – az integrált Wi-Fi SD szinkronmodul előbb biztonságos helyi SD-pillanatképet készít, majd ugyanabba a SleepMate importfolyamatba adja át.

Az importoldal a futó feladat állapotát, előrehaladását és korábbi importok rendszerállapotát is meg tudja jeleníteni.

## 4.2. ResMed könyvtárszerkezet és fájlok

A feldolgozás ResMed-specifikus. A SleepMate a részletes **DATALOG** állományokra támaszkodik, és figyelembe veszi a gyökérben található összesítő/azonosító állományokat is, például az `Identification.json` tartalmát.

A részletes EDF források szerepe többek között:

- **EVE** – terápiás/légzési események;
- **BRP** – nagyobb időfelbontású légáramlási és nyomásjellegű adatok;
- **PLD** – terápiás statisztikai és légzési csatornák, például nyomás, maszkon mért nyomás, szivárgás, flow limitation, horkolás, légzésszám, tidal volume, minute ventilation és elérhető EPR-rel kapcsolatos nyomásinformációk;
- **SA2** – ha az adott adatkészletben rendelkezésre áll, oximetriás csatornák, például SpO₂ és pulzus;
- **STR.EDF** – napi/összesítő jellegű ellenőrzési és diagnosztikai forrás, amely nem helyettesíti a részletes DATALOG-ot.

A SleepMate külön diagnosztikai figyelmeztetést tud adni, ha az STR és a részletes DATALOG között időbeli/állapotbeli eltérés látható.

## 4.3. Felismert eseménytípusok

A feldolgozás külön eseménytípusként kezeli többek között:

- **OA** – obstructive apnea;
- **CA** – central apnea;
- **H** – hypopnea;
- **UA** – unclassified apnea;
- **RERA** – respiratory effort related arousal esemény;
- **CSR** – Cheyne–Stokes respiration jelölés, amennyiben a forrásadat tartalmazza;
- egyéb/nem standard események külön kategóriában.

Az AHI számítása a részletes terápiás használati időhöz igazodik, és az OA + CA + H + UA események alapján készül. A SleepMate az eseménytípusokat a részletes elemzésben nem mossa össze egyetlen számmá: a teljes AHI mellett az egyes komponensek külön is megjelennek.

## 4.4. Importbiztonság és integritás

A SleepMate importlogikája úgy készült, hogy ne tekintsen egy félbehagyott vagy pillanatnyilag hiányos forrásállapotot „hiteles törlésnek”. A kezelt helyi másolat frissítése során:

- a forrásfájlok nem destruktív módon kerülnek feldolgozásra;
- a másolás ellenőrzött, ideiglenes/atomikus lépéseket használhat;
- a fájlok stabilitását a program ellenőrzi;
- egy átmenetileg hiányzó forrásfájl nem indokolhat automatikusan jó, korábban beolvasott terápiás adat elvesztését;
- sérült vagy csonkolt EDF-ek külön diagnosztikában jelenhetnek meg.

---

# 5. Dashboard – terápiás áttekintés

## 5.1. Fő mutatók

A Dashboard a legutóbbi vagy kiválasztott terápiás naphoz képes megjeleníteni többek között:

- használati idő;
- AHI;
- teljes felismert eseményszám;
- OA / CA / H / UA / RERA bontás;
- 95%-os szivárgás;
- nyomásstatisztikák;
- 95%-os nyomás;
- session/munkamenet információ;
- rendelkezésre állás esetén oximetriás/pulzus mutatók;
- az előző összehasonlítható naphoz viszonyított változásokat.

## 5.2. Időszaki összesítés

A hosszabb időszakos áttekintés többek között számolhat:

- terápiás napok számát;
- összes/átlagos használatot;
- súlyozott terápiás AHI-t;
- átlagos AHI-t és eseménytípus-trendeket;
- 4 órás vagy afeletti használati megfelelés arányát;
- nyomás- és szivárgástrendeket;
- időszak eleje és vége közötti változásokat.

A felhasználó nemcsak előre definiált időszakot választhat, hanem két külön periódust is összehasonlíthat. A period comparison külön mutatja például az AHI, OA/CA/H/RERA, használati idő, 95%-os nyomás és 95%-os szivárgás eltérését.

## 5.3. Trenddiagramok

A Dashboard időszaki görbéi között szerepelhet:

- AHI trend;
- használati idő;
- OA/CA/H/RERA index;
- nyomás medián és P95;
- szivárgás medián és P95;
- légzési mutatók;
- egyéb elérhető napi aggregátumok.

---

# 6. Napi részletes Dashboard és nagy felbontású görbék

Egy terápiás nap megnyitásakor a SleepMate nemcsak napi összesítést mutat, hanem a rendelkezésre álló EDF csatornák időbeli lefutását is.

A felület többek között képes:

- a teljes terápiás időablak megjelenítésére;
- a külön sessionök háttérjelölésére;
- légzési eseményjelölők rárajzolására;
- közös időtengely használatára;
- kurzorral azonos időpontra igazítani a külön görbéket;
- nagyítani/kicsinyíteni;
- görgetéssel vagy érintéssel időablakot változtatni;
- eseményre kattintva közvetlenül az esemény körüli időablakra ugrani;
- áttekintő mini-grafikonokat és részletes főgrafikont megjeleníteni;
- a látható időablakhoz igazodó nagyobb mintapont-sűrűséget kérni a backendtől.

Megjeleníthető csatornák a forrásadat rendelkezésre állásától függően például:

- Flow / légáramlás;
- Pressure / terápiás nyomás;
- Mask Pressure;
- Leak Rate;
- Flow Limitation;
- Snore;
- Respiratory Rate;
- Tidal Volume;
- Minute Ventilation;
- EPR-rel összefüggő nyomáscsatornák;
- SpO₂;
- Pulse.

A napi nézetben a felhasználó saját értékelést is rögzíthet, például alvásminőséget és megjegyzést. Ezek a SleepMate saját nyilvántartásában maradnak, és később jelentésben vagy naptárnézetben felhasználhatók.

Mobil/PWA nézetben a napi összefoglalóból megosztható képkártya is készíthető, és ahol a platform támogatja, a natív megosztási felület használható.

---

# 7. „Alvások” – alvásblokkok külön elemzése

A PAP session és a tényleges „egy alvás” nem mindig ugyanaz. Egy éjszaka állhat több sessionből, lehet hosszabb megszakítás, napközbeni szunyókálás vagy nagyon rövid maszkhasználat. A SleepMate ezért külön **alvásblokk-elemző réteget** tartalmaz.

## 7.1. Alvásblokkok képzése

Az algoritmus a közeli PAP sessionöket alvásblokkokba fűzi. A jelenlegi alapértelmezett logika többek között:

- legfeljebb kb. **90 perces** session-közi rést egy alvásblokk részeként kezelhet;
- kb. **20 perc alatti** használatot rövid használatként különíthet el;
- **24 órás gördülő környezetben** vizsgálja, mely blokk domináns;
- a felhasználó saját történetéből tanulja a jellemző fő alvás időtartamát;
- kb. **180 perces** fragmentációs határ mellett képes egy töredezett fő alvás összefüggéseit kezelni.

Fontos: **a kezdési óra önmagában nem minősít**. Az algoritmus nem abból indul ki, hogy „éjjel = fő alvás, nappal = szunyókálás”. A besorolás alapja a sessionök időbeli összetartozása, időtartama, lokális dominanciája és a rendelkezésre álló saját történet.

## 7.2. Osztályok és kézi felülbírálás

A blokkok például az alábbi kategóriákba kerülhetnek:

- fő alvás;
- szunyókálás / nap;
- rövid használat.

A felhasználó egy automatikus besorolást kézzel felülbírálhat, és később visszaállíthatja az automatikus besorolást.

## 7.3. Összesítések

Az Alvások nézet többek között mutathat:

- átlagos fő alvás időtartamot;
- átlagos teljes alvási/PAP blokkidőt;
- szunyókálások számát és időtartamát;
- rövid használatok számát és idejét;
- töredezett fő alvások számát;
- napi összetételt;
- blokk kezdő és befejező időpontját;
- PAP terápiás időt;
- teljes falióra-időablakot;
- sessionök számát;
- sessionök közötti szüneteket;
- blokkhoz tartozó AHI-t.

Az alvásnap a blokk **ébredési/befejezési dátumához** igazodik, nem vakon a ResMed forrásfájl elnevezéséhez.

Sikeres új import vagy SleepSync után az alvásanalízis cache érvényteleníthető, hogy az új terápiás állapot jelenjen meg.

---

# 8. Szekciók / terápiás napok és naptár

A terápiás naplista egy sorban foglalja össze az egyes ResMed napokat. A táblázat tartalmazhat:

- dátum;
- használati idő;
- AHI;
- eseményszám;
- OA / CA / H / RERA bontás;
- nyomás- és szivárgásmutatókat;
- opcionális oximetriás/pulzus adatokat.

A sorra kattintva a megfelelő napi Dashboard nyitható meg.

A naptárnézet napokra bontva képes kiemelni például:

- AHI kategóriát;
- használati időt;
- 95%-os szivárgást;
- saját alvásminőségi értékelést.

---

# 9. Eseménylista

A kiválasztott napon felismert légzési események külön táblázatban jelennek meg. Egy eseményhez elérhető lehet:

- pontos időpont;
- eseménytípus;
- időtartam;
- rövid magyarázat;
- ugrás a napi Dashboard megfelelő időpontjára.

Ez azért fontos, mert két azonos AHI-jú nap szerkezete teljesen eltérhet: a SleepMate külön megmutatja, ha például az események inkább OA, CA, H vagy RERA jellegűek.

---

# 10. Jelentések és PDF export

## 10.1. Időszaki statisztikai jelentés

A Jelentések oldal kiválasztott időszakra képes napi táblázatot és összesített PAP-jelentést készíteni. A statisztikai csatornáknál a rendelkezésre állástól függően megjelenhet például:

- minimum;
- medián;
- P95;
- P99,5;
- maximum.

## 10.2. PDF jelentéskészítő

A SleepMate nyomtatásra tervezett **A4 PDF** jelentést készíthet. A jelentés konfigurálható, és két vizuális irányt támogat:

- SleepMate sötét/prémium megjelenés;
- klinikai/minimál megjelenés.

A jelentésbe a felhasználó külön eldöntheti, mely beteg-/profiladatok kerüljenek be. Ide tartozhat:

- név;
- születési adat / életkor;
- TAJ, ha a felhasználó kifejezetten kéri;
- diagnózis;
- diagnózis időpontja;
- diagnosztikai AHI;
- terápia kezdete;
- orvos;
- intézmény;
- aktuális terápiás előírás;
- készülék;
- maszk;
- gyógyszerek.

Elérhető anonimizált jelentési beállítás is, amely a közvetlen azonosítókat nem teszi a dokumentumba.

A jelentés fejezetei külön kapcsolhatók; a rendszer a ténylegesen rendelkezésre álló adatok alapján képes kihagyni az üres részeket. Tipikus fejezetek:

- összefoglaló;
- használat és compliance;
- AHI és események;
- nyomás és szivárgás;
- trendek;
- saját értékelések;
- felszerelés;
- diagnózisok és titrálások;
- adatminőség/diagnosztika;
- fogalmi magyarázatok.

A PDF előnézetből elkészíthető/menthető, és PWA-kompatibilis letöltési/mentési útvonalat is használ.

## 10.3. AI-eredmény PDF

Az opcionális AI-kiértékelés külön PDF-be exportálható. A felhasználó eldöntheti, hogy csak a kiértékelés vagy az ahhoz kapcsolódó beszélgetés is bekerüljön.

---

# 11. Kezelt személy – helyi egészségügyi és terápiás nyilvántartás

A SleepMate a PAP mérési adatokat és a kezelt személy strukturált nyilvántartását külön rétegként kezeli. A profil törlése ezért nem egyenlő a már importált EDF mérési adatok törlésével.

## 11.1. Személyes profil

Rögzíthető többek között:

- név;
- születési dátum;
- TAJ, opcionális ellenőrzéssel;
- diagnózis időpontja;
- PAP terápia kezdete;
- kezelőorvos;
- intézmény;
- következő kontroll;
- megjegyzés;
- profilkép.

Az áttekintő képes ezekből és a terápiás adatokból például életkort, terápia időtartamát, legutóbbi előírást, utolsó titrálást, aktív gyógyszereket és rövid 7/30/90 napos vagy teljes terápiás mutatókat összeállítani.

## 11.2. Diagnózisok

Egy diagnózisrekord többek között tartalmazhat:

- dátum;
- OSA / CSA / Mixed / Other típus;
- diagnosztikai AHI;
- ODI;
- minimális/átlagos SpO₂;
- megjegyzés.

## 11.3. Titrálások

Titrálási eseményhez rögzíthető például:

- dátum;
- labor/home/APAP/manuális/egyéb jelleg;
- fix vagy automata terápiás mód;
- javasolt fix vagy min/max nyomás;
- titrálási AHI;
- centrális AHI;
- minimális SpO₂;
- megjegyzés.

## 11.4. Terápiás előírások

Az előírásokat a SleepMate **történetként** őrzi, nem egyszerűen felülírja az előző értéket. Egy rekord tartalmazhat:

- hatály kezdete/vége;
- fix/APAP mód;
- fix nyomás vagy min/max tartomány;
- megjegyzés.

Ez lehetővé teszi, hogy később a tényleges terápiás adatok egy beállításváltás előtti és utáni időszakkal összehasonlíthatók legyenek.

## 11.5. Gyógyszerek

Nyilvántartható például:

- gyógyszer neve;
- hatáserősség;
- adag;
- bevételi időpont;
- kezdő/befejező dátum;
- aktív státusz;
- megjegyzés.

## 11.6. Terápiatörténet

Az idővonal egy helyen képes összekapcsolni:

- PAP terápia kezdetét;
- előírásváltozásokat;
- titrálásokat;
- készülékcserét;
- maszkcserét;
- kiegészítő-változást;
- gyógyszer indítását/leállítását;
- testsúly/BMI rekordot;
- kontrollt;
- egyedi eseményt;
- életmód- vagy beállításváltozást.

---

# 12. Kezelt személy hordozható backup – `.cpapbackup`

A kezelt személy adatai külön, jelszóval védett hordozható mentésbe exportálhatók. Ez **nem ugyanaz**, mint a teljes SleepMate rendszerbackup.

A `.cpapbackup`:

- legalább 8 karakteres felhasználói jelszót igényel;
- böngészőoldali PBKDF2-SHA256 kulcsszármaztatást és AES-GCM titkosítást használ;
- tartalmazhatja a profiladatokat, diagnózisokat, titrálásokat, előírásokat, gyógyszereket, saját napi értékeléseket és a hozzárendelt felszerelési rekordokat;
- **nem tartalmazza a ResMed EDF mérési adatokat**;
- visszatöltéskor a strukturált betegadatok egyesíthetők vagy cserélhetők anélkül, hogy a CPAP mérési adattárat törölné.

---

# 13. Felszerelés

## 13.1. Automatikusan észlelt PAP-készülék

A SleepMate a ResMed `Identification.json` alapján képes észlelni a forráskészüléket, és megjelenítheti például:

- gyártó;
- termék/típus;
- termékkód;
- régió;
- adatmodell/adatverzió;
- firmware vagy egyéb rendelkezésre álló azonosító információ.

Az **észlelt készülék nem válik automatikusan betegrekorddá**. A felhasználó dönt arról, hogy hozzárendeli-e a kezelt személyhez.

## 13.2. Készüléknyilvántartás

Rögzíthető például:

- gyártó;
- modell;
- termékkód;
- opcionális sorozatszám;
- használat kezdete/vége;
- csere/felülvizsgálati intervallum;
- aktív státusz;
- megjegyzés.

## 13.3. Maszkok

Rögzíthető:

- gyártó;
- modell;
- maszktípus;
- méret;
- használat kezdete/vége;
- csereintervallum;
- aktív státusz;
- megjegyzés.

## 13.4. Kiegészítők és konfigurációk

Kiegészítőként külön kezelhető például cső, párásító vagy más komponens. Egy konfiguráció összekötheti:

- az adott készüléket;
- maszkot;
- kiegészítőket;
- érvényességi időszakot.

A beépített kompatibilitási katalógus gyorsíthatja a rögzítést, de a mezők kézzel is megadhatók; a SleepMate nem kényszeríti a felhasználót kizárólag katalógusban szereplő eszközre.

Az aktív felszereléshez csere-/felülvizsgálati követés is használható.

---

# 14. GYIK és PAP-fogalomtár

A SleepMate beépített, kereshető PAP/CPAP fogalomtárat tartalmaz. A jelenlegi forráscsomag **127 bejegyzést** tartalmaz.

A kereső képes többek között:

- névre/kifejezésre keresni;
- teljes bejegyzésszövegben keresni;
- kategória szerint szűrni;
- idézőjeles/pontos keresést kezelni.

Egy fogalomhoz tartozhat:

- rövidítés;
- angol elnevezés;
- magyar elnevezés;
- rövid jelentés;
- részletes magyarázat;
- mértékegység;
- terápiás jelentőség;
- megjegyzés.

---

# 15. Naplók, adatintegritás és diagnosztika

A Naplók oldal nemcsak debug-szöveget mutat, hanem a terápiás adatok és a SleepMate környezetének ellenőrzését is szolgálja.

## 15.1. Naplótípusok

- tartós rendszer-/importnapló;
- aktuális böngészőmunkamenet naplója;
- külön AI provider diagnosztika;
- külön SleepSync műszaki napló és futási előzmény.

## 15.2. ResMed adatintegritási ellenőrzés

A rendszer képes jelezni többek között:

- csonkolt vagy sérült EDF-et;
- EDF fejlécben megadott és tényleges rekordmennyiség eltérését;
- fájlvégi maradék byte-okat;
- sessionhöz hiányzó BRP/PLD/EVE fájlt;
- STR és DATALOG közötti állapoteltérést;
- import közbeni hibát vagy figyelmeztetést.

A hibás fájlok listája dátumot, fájlnevet és technikai integritási adatokat is tartalmazhat.

## 15.3. Önteszt

A karbantartási/diagnosztikai ellenőrzés képes vizsgálni például:

- adatforrás állapotát;
- EDF olvashatóságot;
- helyi adatbázisokat/adattárakat;
- backup állapotot;
- automatizálást;
- push rendszert;
- tárhelyet;
- updater állapotot.

## 15.4. Támogatási csomag

A SleepMate képes szerviz-/support bundle készítésére. A cél az, hogy hibakereséshez technikai információt adjon anélkül, hogy nyers terápiás adatokat vagy titkokat csomagolna be.

A csomag tartalmazhat például:

- verzió/build adatokat;
- update állapotot;
- kiválasztott fájlhash-eket;
- adatbázissémát és integritási eredményt;
- diagnosztikai összefoglalót;
- megtisztított naplókat.

Nem célja API-kulcsok, OAuth tokenek, push endpointok vagy nyers EDF terápiás fájlok automatikus elküldése.

---

# 16. Automatikus helyi adatfrissítés

A SleepMate beállítható arra, hogy egy megadott helyi/import forráskönyvtárat automatikusan újraellenőrizzen.

Az ütemezés támogatja többek között:

- időközönkénti futást;
- napi futást;
- heti futást;
- kiválasztott hétköznapot/időpontot.

Ez **külön funkció** a SleepSync ez Share időzítésétől. Az egyik helyi fájlrendszert vizsgál, a másik a Wi-Fi SD adaptert kezeli.

Windows háttérüzemben a SleepMate indulhat a rendszerrel, tálcára minimalizálva, konzolablak nélkül, és értesítést adhat sikeres automatikus frissítésről vagy fontos hibáról.

---

# 17. SleepMate és SleepSync teljes rendszerbackup

## 17.1. Egyetlen közös teljes backup

A SleepMate-ben **nincs két párhuzamos teljes rendszerbackup**. A közös rendszermentés koncepciója:

**„SleepMate és SleepSync teljes mentés”**

A SleepSync saját állapota a SleepMate privát adattárán belül található, ezért automatikusan része a SleepMate teljes rendszermentésének.

A teljes backup célja, hogy egyetlen ZIP-ben megőrizze a SleepMate működéséhez szükséges helyi állapotot, többek között:

- a SleepMate kezelt/importált PAP adattárát;
- a beteg/profil privát adattárat;
- diagnózisokat, titrálásokat, előírásokat, gyógyszereket;
- napi saját értékeléseket;
- felszerelés- és konfigurációs adatokat;
- SleepMate beállításokat;
- automatizálási állapotot;
- releváns napló-/rendszerállapotot;
- **SleepSync beállításokat, sync state-et, előzményeket és saját privát állapotát**.

A backup nem arra szolgál, hogy a felhasználó külső eredeti ResMed SD-forrását módosítsa. A külső forrásmappához a teljes visszaállítás sem nyúl.

## 17.2. Teljes visszaállítás

A **„SleepMate és SleepSync teljes visszaállítás”** ugyanahhoz a közös rendszermentéshez tartozik. A helyreállítás után a SleepMate újra betölti a visszaállított privát és mérési állapotot.

A kezelt személy önálló hordozására továbbra is a `.cpapbackup` célszerű; az egy másik, kisebb célú mentéstípus.

## 17.3. Automatikus backup

A teljes rendszerbackup automatizálható. A beállítások között szerepelhet:

- napi / heti / havi ütemezés;
- pontos időpont;
- heti nap;
- havi nap (biztonságos 1–28 tartomány);
- célmappa;
- megtartandó backupok száma / retention;
- utolsó futás;
- következő futás;
- utolsó mentési fájl.

---

# 18. Opcionális Google Drive backup

A Google Drive nem szükséges a SleepMate használatához. Ha a felhasználó bekapcsolja, a rendszer **a már sikeresen elkészült helyi automatikus backup ZIP-ek opcionális másolatát** tudja a felhasználó saját Drive-fiókjába feltölteni.

Fő tulajdonságok:

- saját Google Cloud OAuth **Desktop app** kliens használható;
- kért Drive jogosultság: `drive.file`, nem teljes Drive-hozzáférés;
- a csatlakoztatott fiók kijelzéséhez userinfo/email jogosultság használható;
- alapértelmezett célmappa: `SleepMate Backups`;
- OAuth tokenek helyileg, védett adattárban tárolódnak;
- a helyi backup sikere **nem függ** a Drive feltöltés sikerétől;
- egy Drive hiba nem érvényteleníti a már jó helyi mentést;
- a Drive-listából korábbi SleepMate backup kiválasztható;
- Drive-ról visszaállításkor ugyanaz a bevált teljes rendszer-visszaállítási útvonal fut le.

---

# 19. SleepSync – integrált ez Share Wi-Fi SD szinkron

Ez a SleepMate egyik legspecifikusabb funkciója. A **SleepSync** a SleepMate 5.1-es kiadási ágától nem különálló program, hanem a SleepMate-be beépített modul.

## 19.1. Mi az a SleepSync?

A SleepSync célja, hogy kompatibilis **legacy ez Share Wi-Fi SD** adapterről a ResMed CPAP/PAP SD-kártya tartalmát Windows alatt úgy olvassa be, hogy:

1. átvegye a szükséges Wi-Fi kapcsolat kezelését;
2. meggyőződjön arról, hogy a kártya ténylegesen elérhető;
3. ne tekintsen egy üres/hibás HTTP választ sikeres SD-nek;
4. stabilitási ellenőrzéssel töltse le a fájlokat;
5. teljes, dátumozott SD-pillanatképet és ZIP-et készítsen;
6. csak ellenőrzött pillanatképet adjon át a SleepMate importnak;
7. a művelet után állítsa vissza a normál internetes Wi-Fi kapcsolatot.

A jelenlegi integrált motor a korábban bevált standalone SleepSync 1.1.5 működésére épül, de a SleepMate saját backup-, import-, PWA-, updater- és diagnosztikai életciklusába van bekötve.

## 19.2. SleepSync felület

A modul a normál SleepMate felületen belül saját nézeteket ad:

- **Áttekintés** – Wi-Fi/SD státusz, utolsó futás, következő futás és fő állapotok;
- **Szinkron** – kézi szinkron, élő fázis, fájl- és progressz információ;
- **Előzmények** – sikeres/sikertelen futások és technikai log;
- **Beállítások** – mentési útvonal, időzítés, stabilitási és inkrementális paraméterek, ismert internetes Wi-Fi hálózatok.

## 19.3. Jelenlegi automatikus működés: kizárólag időzített

A **SleepMate 5.2.16 integrált SleepSync motorja automatikus módban kizárólag ütemezett futást használ**.

Korábbi verziókban létezett „kártya megjelenésekor” automatikus mód. A jelenlegi motor:

- a régi `card_available` beállítást automatikusan `scheduled` módra migrálja;
- a felületen elrejti a régi módválasztót;
- automatikus szinkront csak a kifejezetten beállított napokon és időpontokban indít.

Kézi szinkron természetesen bármikor indítható.

## 19.4. Windows Wi-Fi profil és internet-visszaállítás

A SleepSync a Windowsban mentett **`ez Share` Wi-Fi profilt** használja. A motor:

- lekéri az aktuális Wi-Fi kapcsolatot;
- figyeli a Windows által látott hálózatokat;
- megjegyzi a normál internetes Wi-Fi-t;
- szükség esetén kezeli a Wi-Fi profil automatikus csatlakozási módját;
- a kártyás művelet után visszaállítja a korábbi internetes kapcsolatot;
- több ismert internetes fallback hálózatot is képes figyelembe venni.

A kód külön kezeli a Windows WLAN parancsok nyelvi/OEM kódolási sajátosságait és bizonyos esetekben a WLAN AutoConfig helyreállítását is.

## 19.5. 5.2.16 – AP-jelenlét tudatos helyreállítás

A régi ez Share kártyák nem mindig viselkednek stabil hozzáférési pontként. Előfordulhat, hogy a Wi-Fi rövid ideig látható, majd eltűnik, miközben más hálózatok továbbra is működnek.

A 5.2.16 helyreállítási logikája:

1. először **12 másodpercig tiszta Windows automatikus társítást** enged – ebben az ablakban nem indít felesleges scant, explicit connectet vagy resetet;
2. ha ez nem sikerül, két rövid scan alapján ellenőrzi, hogy az `ez Share` SSID valóban sugároz-e;
3. ha az ez Share egyik scanben sem látható, miközben más hálózatok igen, külön **„ez Share nem sugároz”** állapotot állapít meg;
4. ilyenkor nem futtat felesleges `netsh connect`, profiljavítás vagy WLAN-reset hurkot;
5. visszaállítja és megtartja a normál internetet;
6. kézi futásnál kb. **30 másodperc**, automatikus futásnál kb. **45 másodperc** után kezdi újra figyelni a kártya jelenlétét;
7. ezután kb. **30 másodpercenként** kíméletes jelenlét-ellenőrzést végez;
8. csak akkor bontja újra az internetet, amikor az `ez Share` SSID ténylegesen visszatért;
9. a teljes helyreállítási ablak kézi futásnál legfeljebb kb. **25 perc**, automatikus futásnál legfeljebb kb. **45 perc**;
10. ha maga a Windows Wi-Fi scan sem ad értékelhető listát, a rendszer nem minősíti tévesen „nem sugárzó” kártyának, hanem a korábbi aktív WLAN-helyreállítási útvonalat használja.

## 19.6. Kártya HTTP/gyökérkönyvtár ellenőrzése

Az ez Share nem tekinthető késznek attól, hogy egy HTTP kérésre valamilyen oldal visszajön. A SleepSync a tényleges, parse-olható **`A:`** gyökérkönyvtárat várja.

Fontos kompatibilitási részlet:

- a canonical ez Share gyökér **`A:`**, nem `A:\`;
- a motor közvetlen IP/gateway elérést és `ezshare.card` fallbacket is támogat;
- a SleepMate integrált adapter legalább kb. **60 másodperces** tényleges gyökérkönyvtár-készenléti ablakot biztosít akkor is, ha régebbi konfiguráció ennél rövidebb HTTP timeoutot tartalmazott.

Ezzel elkerülhető, hogy egy HTTP 200-as, de üres/nem parse-olható kártyaoldalt a rendszer „0 fájl, minden kész” sikernek tekintsen.

## 19.7. Rekurzív SD-scan és kötelező ResMed ellenőrzés

A motor rekurzívan feltérképezi az SD tartalmát. A scan csak akkor tekinthető érvényesnek, ha a ResMed struktúra és kötelező sentinel fájlok ellenőrzése sikerül.

A jelenlegi motor egyik kötelező ellenőrző fájlja az **`STR.EDF`**. Ha a scan nulla fájlt ad vagy a kötelező ResMed ellenőrzés elbukik, a futás **hiba**, nem siker.

## 19.8. Inkrementális állapot

A SleepSync helyi sync state-et tart fenn a korábban látott fájlok metaadatairól. Ez alapján eldöntheti, hogy egy fájl:

- új;
- megváltozott;
- már biztonságosan ismert;
- vagy a konfigurált frissítési buffer miatt újra ellenőrizendő.

A `buffer_days` alapértéke 2 nap, és a motor a friss ResMed fájlokat tudatosan újraellenőrzi. A kötelező fájlok minden sikeres futásnál biztonságosan frissítendők.

## 19.9. Stabil fájlletöltés

Egy fájlt a SleepSync nem közvetlenül ír végleges célra. A biztonságos letöltési folyamat lényege:

1. távoli fájlmetaadat lekérése;
2. stabilitási várakozás – alapérték **4 másodperc**;
3. metaadat újraellenőrzése;
4. letöltés ideiglenes `.sleepsync.part` fájlba;
5. HTTP `Content-Length` ellenőrzés, ha rendelkezésre áll;
6. a távoli metaadat ismételt ellenőrzése a letöltés után;
7. ha a fájl közben változott, a letöltés nem tekinthető késznek;
8. csak stabil, ellenőrzött fájl kerül atomikusan a végleges helyére.

Ez különösen azért fontos, mert a CPAP készülék egy adott fájlt még írhat, amikor az ez Share már láthatóvá teszi.

## 19.10. Retry és fail-closed logika

A SleepSync nem próbál „szép zöld sikerüzenetet” adni hiányos szinkronra.

A jelenlegi elv:

- fájlonként több újrapróbálás lehetséges;
- a sikertelen fájlok külön végső retry körbe kerülnek;
- ha a végső kör után akár egy szükséges fájl sem tölthető le biztonságosan, a futás hibával leáll;
- ha kötelező ResMed fájl nem frissült, a futás hibával leáll;
- ha a scan valójában nulla ellenőrzött fájlt adott, nem lehet sikeres;
- félkész állapotból nem készül „minden naprakész” eredmény.

## 19.11. Egyetlen Wi-Fi menet: szinkron + teljes SD-pillanatkép + ZIP

A jelenlegi integrált motor egy sikeres SleepSync során **egy kártyakapcsolatból** végzi el a frissítést és a teljes SD-mentést.

A futás létrehoz:

- dátumozott futási könyvtárat;
- teljes **`SD tartalma`** tükröt;
- teljes, dátumozott **ZIP** SD-pillanatképet.

Ha egy fájl helyben már azonos és hitelesen ismert, a snapshotba helyi ellenőrzött példány is felhasználható; új vagy változott fájlt a kártyáról tölt le.

Ha bármely végleges hiba marad, **félkész ZIP nem készül**.

A létrejött SD ZIP a normál SleepMate ZIP importtal később újra beolvasható.

## 19.12. Fontos különbség: SD-pillanatkép vs. teljes rendszerbackup

A SleepSync által készített **SD biztonsági mentés** a ResMed SD-kártya teljes pillanatképe.

Ez **nem** egy második SleepMate rendszerbackup.

- **SleepSync SD backup:** ResMed kártyatartalom + ZIP archiválás.
- **SleepMate és SleepSync teljes mentés:** a teljes SleepMate helyi állapot, betegadatok, beállítások, kezelt PAP adattár és SleepSync saját state-je.

A SleepSync felület ezért nem indít külön duplikált rendszerbackupot; minden sikeres sync automatikusan elkészíti az SD-pillanatképet, míg a közös rendszerbackup a SleepMate Backup menüben található.

## 19.13. SleepMate-import a sync végén

A sikeres SD snapshot után a SleepSync ugyanazt a biztonságos SleepMate-import logikát hívja meg, mint a normál ZIP/mappa import.

Ezzel:

- az új terápiás napok azonnal megjelenhetnek;
- a már meglévő napok változásai frissülhetnek;
- a Dashboard újratölthető;
- az Alvások cache érvényteleníthető;
- konfiguráció esetén Web Push értesítés küldhető új vagy megváltozott PAP adatról.

Az import szándékosan nem tekinti a pillanatnyilag hiányos távoli scan-t autoritatív törlésnek.

## 19.14. SleepSync beállítások

A jelenlegi motor beállításai között szerepelhet:

- SD backup célgyökér – alapérték: `~/Documents/SleepSync_Backups`;
- automatikus időzítés be/ki;
- kiválasztott napok;
- egy vagy több futási időpont, alapérték `09:00`;
- kártya scan intervallum – belső támogatott tartomány 10–300 s, alapérték 30 s;
- retry szám – 1–10, alapérték 5;
- automatikus retry várakozás – 1–60 perc, alapérték 5 perc;
- ez Share readiness timeout – belső támogatott 5–120 s, az integrált kártyagyökér-várakozás legalább 60 s;
- stabilitási várakozás – 2–30 s, alapérték 4 s;
- frissítési buffer – 0–30 nap, alapérték 2 nap;
- ismert internetes Wi-Fi fallback hálózatok.

## 19.15. Élő státusz és előzmények

A SleepSync státusz képes megjeleníteni többek között:

- aktuális Wi-Fi;
- ez Share/SD láthatóság;
- kapcsolat fázisa;
- futási fázis;
- százalékos progressz;
- összes ellenőrzött fájl;
- feldolgozott fájlok;
- letöltött fájlok;
- változatlan fájlok;
- hibák;
- éppen feldolgozott fájl;
- utolsó futás;
- következő időzített futás;
- utolsó hiba.

A futási előzmény legfeljebb 250 rekordot tart meg, külön törölhető. A részletes technikai napló a SleepMate privát `sleepsync` adattárában található.

## 19.16. Frissítés és életciklus

Az integrált SleepSync:

- nem rendelkezik külön `SleepSync.exe` updaterrel;
- nem fut külön tálcaprogramként;
- ugyanazt a SleepMate verziót és updater életciklust követi;
- ugyanabba a teljes rendszerbackupba kerül;
- a PWA felületbe csak a SleepMate core indulása után kapcsolódik be, hogy ne törje meg a fő Dashboard indulását;
- nem próbál böngészőfolyamatokat agresszívan bezárni a captive-portal/Wi-Fi váltás során, mert azok a SleepMate PWA renderer részei is lehetnek.

---

# 20. AI-kiértékelés – opcionális Gemini és Groq

## 20.1. Teljesen opcionális

A SleepMate minden alapvető PAP funkciója AI nélkül is működik. AI használatához a felhasználó saját API-hozzáférést konfigurál.

A jelenlegi provider-ek:

- **Luna – Google Gemini**;
- **Milo – Groq**.

A megjelenített név és a választott modell konfigurálható. A SleepMate nem használ központi saját AI proxyt: a kérés közvetlenül a felhasználó gépéről a kiválasztott szolgáltatóhoz megy.

## 20.2. Elemzéstípusok

A program többek között képes kérni:

- legutóbbi terápiás éjszaka elemzést;
- utolsó 7 rendelkezésre álló terápiás nap elemzést;
- kiválasztott hónap elemzést;
- teljes rendelkezésre álló terápiás időszak elemzést;
- két kiválasztott időszak összehasonlítását.

## 20.3. Adatverzió és ismételt elemzés

A SleepMate az aktuális terápiás adatkészlethez **dataset signature**-t készít. Egy adott elemzéstípus ugyanahhoz az adatverzióhoz mentett eredménnyel újranyitható, ahelyett hogy feleslegesen újra elküldené ugyanazt az adatkészletet.

Amikor a terápiás adatok megváltoznak, az adatverzió is megváltozik, így az új adatokra új kiértékelés kérhető.

## 20.4. AI-chat

Egy elkészült elemzéshez további kérdések tehetők fel ugyanabban a kontextusban.

Jelenlegi UI-korlátok:

- maximum **1200 karakter** egy felhasználói kérdésben;
- **10 kérdés / nap / AI provider**;
- Gemini és Groq saját napi számlálót kap.

Az eredmény és a beszélgetés helyileg menthető és visszanézhető.

## 20.5. AI-nak nem küldött közvetlen azonosítók

A biztonságos payload-réteg kizárja többek között:

- nevet / teljes nevet;
- vezeték- és keresztnevet;
- e-mail-címet;
- telefonszámot;
- lakcímet;
- TAJ-t;
- SSN-t;
- születési dátumot;
- születési helyet;
- készülék sorozatszámát;
- felhasználónevet / Windows felhasználónevet;
- IP-címet;
- MAC-címet;
- Wi-Fi SSID-t;
- betegazonosítót;
- orvos nevét;
- intézmény nevét;
- fájlnevet és fájlútvonalat;
- szabad szöveges jegyzeteket.

## 20.6. AI-nak küldhető adatminimalizált terápiás adatok

Az elemzéshez ugyanakkor szükség szerint bekerülhet például:

- életkor;
- terápia kezdete;
- diagnózistípus;
- kiindulási AHI;
- ODI;
- SpO₂ adatok;
- terápiás előírás;
- nyomásbeállítások;
- készülék- és maszktípus;
- terápiás napok és session-idők;
- AHI és eseménytípusok;
- események időpontja/időtartama;
- nyomásstatisztikák;
- szivárgás;
- flow limitation;
- horkolás;
- légzésszám;
- tidal volume;
- minute ventilation;
- rendelkezésre álló oximetria.

Ezek **egészségügyi adatok**. A SleepMate azonosítóktól megtisztított, adatminimalizált csomagot küld, de nem állítja, hogy egy összetett egészségügyi adatkészlet minden körülmények között matematikailag visszafordíthatatlanul anonim.

## 20.7. AI rendszerutasítás biztonsági elvei

A rendszerprompt többek között előírja, hogy az AI:

- kizárólag a kapott terápiás adatból dolgozzon;
- ne találjon ki hiányzó adatot;
- külön értelmezze az OA, CA, H, RERA és UA eseményeket;
- a saját korábbi trendeket tekintse elsődleges referenciának;
- korrelációból ne állítson automatikusan okozati kapcsolatot;
- fontos következtetéseknél jelezzen bizonyossági szintet;
- ne diagnosztizáljon;
- ne adjon kötelező, konkrét terápiás nyomásmódosítási utasítást.

## 20.8. AI provider diagnosztika

A SleepMate külön provider tesztet és diagnosztikai logot tartalmaz. A log képes megmutatni például:

- providert;
- modellt;
- transport típust;
- request ID-t;
- válaszidőt;
- HTTP státuszt;
- szolgáltatói hibakódot;
- kulcs forrását és rövid, nem visszafejthető hint/fingerprint információt.

A tényleges API-kulcsot nem írja ki a diagnosztikai exportba.

---

# 21. Távoli elérés – Tailscale

A SleepMate Tailscale integrációja azért készült, hogy a helyi backend közvetlen LAN-publikálása nélkül lehessen saját eszközről távolról hozzáférni.

A funkció képes:

- Tailscale telepítés/állapot felismerésére;
- Tailscale Serve engedélyezésére és leállítására;
- HTTPS tailnet URL megjelenítésére;
- a távoli URL megnyitására;
- helyben QR-kódot generálni a telefonos megnyitáshoz;
- az aktuális SleepMate localhost portra beállítani a Serve célját;
- induláskor felismerni és javítani egy régi SleepMate portra mutató Serve konfigurációt, ha a program új automatikus portot kapott.

A Tailscale továbbra is külön külső szolgáltatás; a tailnet és a felhasználói fiók megfelelő védelme a felhasználó feladata.

---

# 22. Távoli elérés – Cloudflare Tunnel

A SleepMate opcionálisan Cloudflare Tunnel mögött is elérhetővé tehető.

A modul képes:

- `cloudflared` jelenlétét ellenőrizni;
- Tunnel állapotot vizsgálni;
- publikus hostname konfigurációt kezelni;
- a helyes aktuális localhost portra mutató origint használni;
- tunnelt indítani/leállítani/ellenőrizni;
- a távoli URL-t megnyitni.

A SleepMate felülete külön hangsúlyozza a **Cloudflare Access / Zero Trust** hozzáférésvédelmet. Egy publikus Tunnel megfelelő Access szabály nélkül érzékeny helyi egészségügyi felületet tehetne elérhetővé, ezért a biztonságos konfiguráció nem opcionális részlet.

Ha a tunnel már külön Windows szolgáltatásként fut és menedzselt, a SleepMate-nek nem szükséges feltétlenül saját tunnel tokent tárolnia. Ha a SleepMate indítja a tunnelt, a szükséges secret helyileg védett adattárban kezelhető.

---

# 23. PWA és mobilhasználat

A SleepMate ugyanazt a webes felületet PWA-ként is képes kiszolgálni. HTTPS-en – például Tailscale Serve vagy megfelelő Cloudflare konfiguráció mögött – telefonra/asztalra telepíthető webalkalmazásként használható.

PWA/mobil funkciók többek között:

- installálható alkalmazásélmény;
- saját ikon és splash;
- mobil alsó navigáció;
- érintésre optimalizált grafikonkezelés;
- natív megosztás, ahol támogatott;
- PDF fájl mentése;
- service-worker cache;
- átmeneti backend-kiesésnél korábban cache-elt felület/állapot használatának támogatása;
- Web Push értesítések.

Az offline állapot nem jelent teljes offline adatbázist: élő, új terápiás adat lekéréséhez a SleepMate backendnek elérhetőnek kell lennie.

---

# 24. Web Push értesítések

A SleepMate helyben képes VAPID kulcspárt létrehozni. A privát VAPID kulcs a backend privát adattárában marad.

A felhasználó eszközönként előfizethet értesítésekre. Beállítható értesítési kategóriák például:

- új PAP/CPAP terápiás éjszaka;
- korábban ismert EDF/adatkészlet megváltozása;
- diagnosztikai figyelmeztetés;
- backup hiba.

A felület támogatja:

- engedélykérést;
- előfizetés mentését;
- tesztértesítést;
- leiratkozást.

Megfelelő böngésző/PWA és push infrastruktúra esetén az értesítés akkor is megérkezhet, amikor a PWA nincs aktív előtérben.

---

# 25. Beállítások – helyi backend és port

A SleepMate helyi szolgáltatása választható:

- automatikus portmódban;
- fix porttal.

Automatikus módban a program a konfigurált kezdőponttól – jelenleg tipikusan **8895** – keres szabad helyi portot. A változtatás újraindítás után érvényesülhet.

A backend alapvetően `127.0.0.1` / localhost elérésre készül. A távoli publikálás külön Tailscale/Cloudflare rétegen keresztül történik.

---

# 26. Frissítés és rollback

A SleepMate saját frissítési életciklust tartalmaz.

A release updater képes:

- verzióinformáció ellenőrzésére;
- GitHub Release alapú csomagforrás használatára;
- letöltött csomag SHA-256 ellenőrzésére;
- indításkori automatikus frissítésellenőrzésre;
- felhasználói jóváhagyással telepítést indítani;
- frissítés előtt teljes backupot/rollback pontot készíteni;
- külön updater folyamatból cserélni a futó program fájljait;
- sikertelen új build esetén rollbacket végrehajtani;
- manuális rollback lehetőséget biztosítani;
- átmeneti hálózati hiba esetén reziliensebb ellenőrzést végezni.

## Code signing policy

A hivatalos kiadások kódaláírási szabályzata: [`CODE_SIGNING_POLICY.md`](CODE_SIGNING_POLICY.md).

**Kódaláírási státusz:** a repository tartalmazza a SignPath-kompatibilis code-signing policy-t, artifact konfigurációkat és release gate-eket. A SignPath Foundation által aláírt hivatalos production pipeline előkészítés alatt áll; a jelenlegi forrásból nem szabad azt állítani, hogy minden build már aláírt.

---

# 27. Windows csomagolás és futtatás

A Windows build főbb jellemzői:

- PyInstaller-alapú csomagolás;
- onedir jellegű alkalmazáscsomag;
- UPX nélküli build;
- konzolablak nélküli normál felhasználói futtatás;
- Windows tray integráció;
- helyi HTTP backend + web/PWA frontend;
- külön updater komponens;
- telepítési/release workflow külön build- és aláírási gate-ekkel.

A repositoryban lévő build- és release fájlok fejlesztői/CI használatra szolgálnak. Az aláírt hivatalos terjesztési formátumot a SignPath folyamat véglegesítése határozza meg.

---

# 28. Tesztek és regressziós kapuk

A projekt automatizált tesztjei nemcsak kis egységteszteket, hanem sok konkrét termékviselkedési regressziós szerződést is lefednek. A tesztterületek között szerepel többek között:

- ResMed EDF feldolgozás;
- import és nem destruktív frissítés;
- backup/visszaállítás;
- betegadat backup;
- PDF riport;
- AI payload adatminimalizálás;
- AI provider és history;
- PWA/service worker;
- Web Push;
- Tailscale;
- Cloudflare;
- updater/rollback;
- Windows csomagolás;
- SleepSync ez Share scan;
- SleepSync stabil fájlletöltés;
- SleepSync teljes SD snapshot;
- SleepSync Wi-Fi helyreállítás;
- 5.2.16 AP-presence aware recovery;
- alvásblokk-elemzés és kézi felülbírálás.

A public release workflow célja, hogy a stable kiadás ne tudjon csendben átcsúszni a szükséges release/signing feltételek nélkül.

---

# 29. Adatvédelem röviden

A teljes adatvédelmi dokumentum: [`PRIVACY.md`](PRIVACY.md).

A legfontosabb technikai alapelvek:

- PAP/CPAP mérési és betegadatok alapértelmezetten helyben;
- nincs központi SleepMate egészségügyi adatbázis;
- opcionális külső szolgáltatások külön felhasználói döntéssel;
- AI előtt direkt azonosítók kiszűrése;
- Google Drive csak saját fiókba és saját OAuth konfigurációval;
- Tailscale/Cloudflare csak opcionális távoli elérés;
- support csomag nem nyers EDF és nem secret dump;
- a felhasználó saját számítógépének, Windows fiókjának, backupjainak és külső szolgáltatói fiókjainak védelme továbbra is szükséges.

---

# 30. Nem orvosi diagnosztikai szoftver

**A SleepMate nem orvostechnikai diagnosztikai rendszer.**

Nem:

- állít fel diagnózist;
- helyettesít alváslabor vizsgálatot;
- helyettesít orvost;
- helyettesít PAP titrálást;
- ír elő gyógyszert;
- jogosít fel gyógyszer önálló módosítására;
- hajt végre automatikus terápiás nyomásváltoztatást;
- garantálja egy AI-válasz orvosi helyességét.

A szoftver célja a felhasználó saját adatai áttekintésének és értelmezésének támogatása. Klinikai döntéshez megfelelő egészségügyi szakember szükséges.

---

# 31. Repository struktúra

Főbb könyvtárak/fájlok:

```text
SleepMate-Public/
├─ app.py                         # helyi HTTP/API backend
├─ cpap/                          # EDF, import, backup, AI, report, remote access, SleepSync
│  ├─ resmed.py
│  ├─ edf.py
│  ├─ services.py
│  ├─ patient_store.py
│  ├─ report_pdf.py
│  ├─ ai_payload.py
│  ├─ ai_provider.py
│  ├─ ai_store.py
│  ├─ google_drive_integration.py
│  ├─ remote_access.py
│  ├─ push_service.py
│  ├─ maintenance.py
│  ├─ sleep_analysis.py
│  ├─ sleepsync_engine_v2.py
│  ├─ sleepsync_legacy.py
│  └─ ...
├─ web/                           # Dashboard, PWA, charts, SleepSync UI
├─ tests/                         # unit + regression/contract tests
├─ build/                         # Windows build/installer resources
├─ .github/workflows/             # CI / release workflows
├─ .signpath/ + signpath configs  # signing preparation
├─ PRIVACY.md
├─ SECURITY.md
├─ CODE_SIGNING_POLICY.md
├─ THIRD_PARTY_NOTICES.md
├─ TRADEMARKS.md
└─ LICENSE
```

---

# 32. Licenc, márkanév és hozzájárulás

A SleepMate forráskódja **GNU AGPL v3.0 only** licenc alatt kerül közzétételre. A részletes licencfeltételeket a [`LICENSE`](LICENSE) tartalmazza.

Harmadik féltől származó komponensek/licencek: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

A SleepMate név, vizuális arculat és kapcsolódó megjelölések használatára külön védjegy-/brand feltételek vonatkozhatnak: [`TRADEMARKS.md`](TRADEMARKS.md).

Biztonsági hibák felelős jelentése: [`SECURITY.md`](SECURITY.md).

Hozzájárulási útmutató: [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

# 33. Kapcsolat

**SleepMate projekt – BenWyxell – Kovács Lóránd E.V.**  
**E-mail:** hello@mysleepmate.hu

---

<a id="english"></a>
# 🇬🇧 English

## 1. What is SleepMate?

**SleepMate** is a Windows-first, local-first PAP/CPAP therapy data management and analysis workstation. Its primary purpose is to read detailed therapy data from ResMed SD-card datasets on the user's own computer, organize and visualize the data, compare periods, create reports, and optionally connect to external services only when the user explicitly configures them.

SleepMate is not just an “AHI viewer”. It combines in one application:

- detailed ResMed EDF import;
- daily and long-term therapy dashboards;
- high-resolution signal charts and respiratory-event navigation;
- separate sleep-block and PAP-session analysis;
- a structured local patient/treated-person record;
- diagnosis, titration, prescription, medication and therapy history;
- PAP device, mask and accessory tracking;
- printable/exportable PDF reports;
- optional Gemini/Groq AI analysis using the user's own API keys;
- automatic local backups and complete system restore;
- optional Google Drive backup copies;
- secure remote PWA access through Tailscale or Cloudflare;
- Web Push notifications;
- diagnostics and support logs;
- and the integrated **SleepSync** subsystem for safely downloading and importing ResMed SD-card contents through compatible **ez Share Wi-Fi SD** hardware.

The fundamental design principle is simple: **the primary location of therapy and health data is the user's own computer**.

---

## 2. Local-first operating model

Normal local use of SleepMate does not require:

- a central SleepMate account;
- a central SleepMate health database;
- a mandatory SleepMate cloud;
- automatic therapy-data transmission to the developer;
- mandatory health telemetry.

The developer does not automatically receive the user's dashboard data, EDF files, diagnoses, medications or AI history. External services — Google Drive, Gemini, Groq, Tailscale and Cloudflare — are optional and require separate user configuration.

Sensitive configuration stored in SleepMate's private local state can be protected with **AES-256-GCM**. This can include API keys, OAuth tokens and other local secrets. Because the design supports portable complete-system restore, key material required by that protected state is part of the local private store; therefore a complete SleepMate backup must itself be treated as sensitive data.

ResMed SD cards, ez Share cards and manually selected import folders are treated as **sources**. The import model is designed around non-destructive reading rather than modifying the original therapy card.

---

## 3. Supported platform and application model

The current release line primarily targets:

- **Windows x64**;
- a local SleepMate backend service;
- a responsive browser-based UI;
- an installable **PWA** using the same interface and dataset;
- a Windows tray/background runtime;
- optional secure remote access through Tailscale or Cloudflare.

The backend is designed to bind to **localhost/loopback** by default instead of automatically exposing sensitive therapy data to the LAN. Remote publication is handled through an explicit security layer.

---

# 4. ResMed SD / EDF import

## 4.1. Import paths

SleepMate can feed the same managed therapy dataset through several import mechanisms:

1. **Manually selected folder** — for example a ResMed SD card or a copied card tree.
2. **Automatic Windows SD-drive discovery** — looking for ResMed-style directory/file structures.
3. **ZIP import** — a previously saved complete SD snapshot or compatible ZIP.
4. **Instant refresh** — rescan the configured default source folder.
5. **Scheduled automatic scan** — periodically recheck a configured source directory.
6. **SleepSync / ez Share** — the integrated Wi-Fi SD engine first creates a verified local SD snapshot and then passes it into the same SleepMate import pipeline.

The import page tracks running jobs, progress and persistent import/system history.

## 4.2. ResMed structure and EDF sources

The parser is ResMed-focused. SleepMate uses detailed **DATALOG** files as the primary source and also evaluates root summary/identity information such as `Identification.json`.

Detailed EDF families can provide, among other things:

- **EVE** — respiratory/therapy events;
- **BRP** — higher-resolution flow and pressure-related signals;
- **PLD** — therapy and respiratory channels such as pressure, mask pressure, leak, flow limitation, snore, respiratory rate, tidal volume, minute ventilation and available EPR-related pressure information;
- **SA2** — when present, oximetry channels such as SpO₂ and pulse;
- **STR.EDF** — summary/diagnostic information used as an integrity/fallback reference rather than as a substitute for detailed DATALOG data.

SleepMate can surface a diagnostic warning if STR and DATALOG appear out of sync.

## 4.3. Respiratory event types

The parser distinguishes event classes such as:

- **OA** — obstructive apnea;
- **CA** — central apnea;
- **H** — hypopnea;
- **UA** — unclassified apnea;
- **RERA** — respiratory effort related arousal;
- **CSR** — Cheyne–Stokes respiration when represented by the source;
- other/non-standard events in a separate fallback category.

AHI is calculated against actual therapy usage and is based on OA + CA + H + UA events. SleepMate deliberately keeps individual event components visible instead of collapsing the entire night into one number.

## 4.4. Import integrity and non-destructive behavior

SleepMate is designed not to interpret a transiently incomplete source as an authoritative deletion. The managed import process can use:

- non-destructive source handling;
- verified/temporary/atomic copying;
- file-stability checks;
- retention of previously valid managed data when a source is temporarily incomplete;
- diagnostics for truncated or damaged EDF files.

---

# 5. Therapy Dashboard

## 5.1. Daily headline metrics

For the latest or selected therapy day, SleepMate can display:

- usage time;
- AHI;
- total event count;
- OA / CA / H / UA / RERA breakdown;
- 95th-percentile leak;
- pressure statistics;
- 95th-percentile pressure;
- session information;
- optional oximetry/pulse metrics;
- deltas versus the previous comparable therapy day.

## 5.2. Period summary

Longer-period summaries can include:

- number of therapy days;
- total and average usage;
- therapy-time-weighted AHI;
- average AHI and event-type trends;
- 4-hour-or-more compliance ratio;
- pressure and leak trends;
- changes between the beginning and end of the selected period.

Users can also compare two explicitly selected periods. Comparison metrics can include AHI, OA/CA/H/RERA indices, usage time, pressure P95 and leak P95.

## 5.3. Trend charts

Period charts can include:

- AHI;
- usage;
- OA/CA/H/RERA indices;
- pressure median and P95;
- leak median and P95;
- respiratory metrics;
- other available daily aggregates.

---

# 6. Detailed daily dashboard and high-resolution charts

Opening a therapy day exposes not only daily statistics but also the temporal shape of available EDF signals.

The chart system supports:

- the full therapy time window;
- separate session backgrounds;
- respiratory event markers;
- a shared time axis;
- synchronized cursor positioning;
- zooming and panning;
- wheel/touch window navigation;
- jumping directly to a respiratory event;
- overview mini charts plus a detailed hero chart;
- dynamically requesting more points from the backend as the visible time window becomes smaller.

Depending on source availability, displayed signals can include:

- Flow;
- Pressure;
- Mask Pressure;
- Leak Rate;
- Flow Limitation;
- Snore;
- Respiratory Rate;
- Tidal Volume;
- Minute Ventilation;
- EPR-related pressure signals;
- SpO₂;
- Pulse.

Users can record their own daily sleep/therapy assessment, such as sleep-quality score and notes. These remain in the local SleepMate record and can later appear in calendars or reports.

On mobile/PWA platforms, SleepMate can generate a shareable daily summary image and use native sharing where supported.

---

# 7. Sleep analysis — grouping PAP sessions into actual sleep blocks

A PAP session is not always equivalent to one real sleep period. One night may contain multiple sessions, long interruptions, daytime naps or very short mask use. SleepMate therefore includes a separate **sleep-block analysis layer**.

## 7.1. Block construction

The current default logic can:

- merge sessions separated by up to approximately **90 minutes**;
- classify usage shorter than about **20 minutes** as short use;
- evaluate local dominance inside a **24-hour rolling window**;
- learn the user's characteristic main-sleep duration from history;
- use a fragmentation threshold of approximately **180 minutes** for split main sleep.

Crucially, **clock time alone does not classify sleep**. The system does not assume “night = main sleep” and “day = nap”. Classification is driven by temporal grouping, duration, local dominance and the user's available history.

## 7.2. Classes and manual overrides

Blocks can be classified as, for example:

- main sleep;
- nap;
- short use.

A user can manually override an automatic classification and later restore automatic classification.

## 7.3. Sleep summaries

The sleep view can show:

- average main-sleep duration;
- average total sleep/PAP-block duration;
- nap count and duration;
- short-use count and duration;
- fragmented-main-sleep count;
- daily composition;
- exact block start/end;
- PAP therapy time;
- wall-clock block window;
- session count;
- gaps between sessions;
- block AHI.

Sleep-day grouping follows the block's **wake/end date**, rather than blindly trusting a source filename date.

Successful import or SleepSync can invalidate the sleep-analysis cache so new data is reflected immediately.

---

# 8. Therapy days / sessions and calendar

The therapy-day table summarizes one ResMed day per row and can include:

- date;
- usage;
- AHI;
- event count;
- OA / CA / H / RERA breakdown;
- pressure/leak metrics;
- optional oximetry/pulse data.

Selecting a row opens that day's detailed dashboard.

The calendar can visually encode:

- AHI category;
- usage time;
- leak P95;
- the user's own sleep-quality score.

---

# 9. Event browser

All recognized events for a selected day can be displayed with:

- exact time;
- event type;
- duration;
- explanatory text;
- direct navigation to the corresponding point in the daily chart.

This matters because two nights with the same total AHI can have very different OA/CA/H/RERA composition.

---

# 10. Reports and PDF export

## 10.1. Period statistics

The report view can build a daily table and aggregate PAP report for a selected date range. Signal statistics may include, where available:

- minimum;
- median;
- P95;
- P99.5;
- maximum.

## 10.2. A4 PDF report builder

SleepMate can generate print-oriented **A4 PDF** reports with two visual directions:

- SleepMate dark/premium theme;
- clinical/minimal theme.

Users can explicitly choose which patient/profile fields enter the report, including:

- name;
- birth information / age;
- national health identifier when explicitly selected;
- diagnosis;
- diagnosis date;
- diagnostic AHI;
- therapy start;
- clinician;
- institution;
- current prescription;
- device;
- mask;
- medications.

An anonymized preset can omit direct identifiers.

Report sections are independently selectable and empty sections can be skipped according to actual data availability. Typical sections include:

- overview;
- usage/compliance;
- AHI/events;
- pressure/leak;
- trends;
- user assessments;
- equipment;
- diagnoses/titrations;
- data quality;
- glossary/explanations.

Reports can be previewed and saved/downloaded through desktop or PWA flows.

## 10.3. AI-result PDF

Optional AI analyses can be exported separately. Users can choose whether to include only the analysis or also the related chat history.

---

# 11. Local patient / treated-person record

SleepMate deliberately separates PAP measurement data from the structured patient record. Deleting a patient profile is therefore not synonymous with deleting previously imported EDF measurements.

## 11.1. Profile

Locally recorded fields can include:

- name;
- date of birth;
- national health identifier with optional validation;
- diagnosis date;
- PAP therapy start;
- clinician;
- institution;
- next follow-up;
- notes;
- profile photo.

The overview can combine these records with therapy data to show age, therapy duration, current diagnosis/prescription, recent titration, active medication and 7/30/90-day or all-time therapy indicators.

## 11.2. Diagnoses

A diagnosis record can include:

- date;
- OSA / CSA / Mixed / Other;
- diagnostic AHI;
- ODI;
- minimum/average SpO₂;
- note.

## 11.3. Titrations

A titration record can include:

- date;
- lab/home/APAP/manual/other type;
- fixed or auto therapy mode;
- recommended fixed or min/max pressure;
- titration AHI;
- central AHI;
- minimum SpO₂;
- note.

## 11.4. Therapy prescriptions

Prescriptions are retained as **history**, not merely overwritten. A record can contain:

- effective start/end date;
- fixed/APAP mode;
- fixed pressure or min/max range;
- note.

This supports before/after comparisons around prescription or settings changes.

## 11.5. Medications

Medication records can include:

- name;
- strength;
- dose;
- time of administration;
- start/end date;
- active flag;
- note.

## 11.6. Therapy timeline

The timeline can combine:

- therapy start;
- prescription changes;
- titrations;
- device changes;
- mask changes;
- accessory changes;
- medication start/stop;
- weight/BMI records;
- follow-up visits;
- custom events;
- lifestyle/settings changes.

---

# 12. Portable patient backup — `.cpapbackup`

Structured patient data can be exported to a password-protected portable backup. This is **not the same thing** as a complete SleepMate system backup.

A `.cpapbackup`:

- requires a user password of at least 8 characters;
- uses browser-side PBKDF2-SHA256 key derivation and AES-GCM encryption;
- can contain profile, diagnoses, titrations, prescriptions, medication, user assessments and assigned equipment/configuration records;
- **does not contain ResMed EDF measurement files**;
- can be restored by merging or replacing structured patient metadata without deleting PAP measurement data.

---

# 13. Equipment management

## 13.1. Detected PAP device

SleepMate can read ResMed `Identification.json` and show detected source-device details such as:

- manufacturer;
- product/model;
- product code;
- region;
- data model/version;
- firmware or other available device information.

A detected device is **not automatically assigned** to the patient. Assignment is explicit.

## 13.2. Device records

Fields can include:

- manufacturer;
- model;
- product code;
- optional serial number;
- use start/end;
- replacement/review interval;
- active flag;
- note.

## 13.3. Masks

Mask records can include:

- manufacturer;
- model;
- mask type;
- size;
- start/end;
- replacement interval;
- active flag;
- note.

## 13.4. Accessories and setups

Accessories such as tubing, humidifiers and other components can be stored separately. A setup can associate:

- device;
- mask;
- accessories;
- effective date range.

A built-in compatibility catalog can speed up entry, but all fields remain manually editable. Active equipment can also be tracked for replacement/review scheduling.

---

# 14. FAQ and PAP glossary

The source currently ships with a searchable PAP/CPAP glossary containing **127 entries**.

The UI supports:

- term/name search;
- full-record search;
- category filtering;
- exact/quoted search.

Entries can include:

- abbreviation;
- English name;
- Hungarian name;
- short meaning;
- detailed explanation;
- unit;
- therapy relevance;
- notes.

---

# 15. Logs, data integrity and diagnostics

The Logs section is both a debug surface and a therapy-data integrity center.

## 15.1. Log categories

- persistent system/import log;
- current browser-session log;
- dedicated AI-provider diagnostics;
- dedicated SleepSync technical log and run history.

## 15.2. ResMed integrity diagnostics

SleepMate can identify or report:

- truncated/damaged EDF files;
- mismatches between EDF header records and actual records;
- trailing bytes;
- missing BRP/PLD/EVE files for sessions;
- STR-vs-DATALOG inconsistencies;
- import warnings and failures.

## 15.3. Self-check

Maintenance diagnostics can inspect areas such as:

- data source;
- EDF readability;
- local databases/state;
- backup status;
- automation;
- push system;
- disk space;
- updater state.

## 15.4. Sanitized support bundle

SleepMate can create a support/service ZIP intended to provide technical troubleshooting context without becoming a raw health-data dump.

It can include:

- version/build information;
- update status;
- selected file hashes;
- database schemas/integrity results;
- diagnostics;
- sanitized logs.

It is not intended to automatically include API keys, OAuth tokens, push endpoints or raw EDF therapy files.

---

# 16. Scheduled local source refresh

A configured local source directory can be rescanned automatically.

Scheduling can support:

- interval-based runs;
- daily runs;
- weekly runs;
- selected weekday/time.

This is **separate from SleepSync scheduling**. One watches a local filesystem source; the other manages a Wi-Fi SD adapter.

The Windows background runtime can start with Windows, stay in the tray without a console, and issue desktop notifications for successful automatic refreshes or important errors.

---

# 17. Unified SleepMate + SleepSync complete system backup

## 17.1. One shared complete backup

SleepMate does **not** maintain two parallel full-system backup systems. The shared concept is:

**“SleepMate and SleepSync complete backup”**

SleepSync state lives inside SleepMate's private state tree, so it is naturally included in the complete SleepMate backup.

The complete ZIP is intended to preserve the local application state required for recovery, including:

- the managed/imported PAP data store;
- encrypted/private patient state;
- diagnoses, titrations, prescriptions and medication;
- user assessments;
- equipment/configuration records;
- SleepMate settings;
- automation state;
- relevant system/log state;
- **SleepSync settings, sync state, history and private state**.

The complete backup does not modify the user's external original ResMed source directory, and full restore does not overwrite that external source.

## 17.2. Complete restore

**“SleepMate and SleepSync complete restore”** uses the same unified system backup. SleepMate reloads the restored private and managed measurement state after completion.

For transferring only a patient record, `.cpapbackup` remains the smaller purpose-built format.

## 17.3. Automatic backup schedule

Complete backup can be scheduled with:

- daily / weekly / monthly cadence;
- exact time;
- weekday;
- month day (safe 1–28 range);
- destination directory;
- retention count;
- last run;
- next run;
- last generated backup file.

---

# 18. Optional Google Drive backup copy

Google Drive is not required for SleepMate. When enabled, SleepMate can upload **copies of already completed local automatic backup ZIPs** to the user's own Google Drive.

Key properties:

- user-provided Google Cloud OAuth **Desktop app** client;
- Drive scope: `drive.file`, not full Drive access;
- userinfo/email scope can be used to display the connected account;
- default target folder: `SleepMate Backups`;
- OAuth tokens stored locally in protected state;
- local backup success is **independent** of cloud-upload success;
- a Drive failure does not invalidate an already valid local backup;
- Drive backups can be listed in the UI;
- restore from Drive uses the same established complete-system restore path.

---

# 19. SleepSync — integrated ez Share Wi-Fi SD synchronization

SleepSync is one of the most specialized parts of SleepMate. Since the SleepMate 5.1 release line, it is integrated into SleepMate rather than distributed as a separate application.

## 19.1. Purpose

With compatible **legacy ez Share Wi-Fi SD** hardware, SleepSync is designed to:

1. take temporary control of the required Wi-Fi connection;
2. verify that the card is genuinely available;
3. reject empty/broken HTTP responses as successful SD scans;
4. download files using stability validation;
5. create a complete dated SD mirror and ZIP snapshot;
6. pass only a verified snapshot into the SleepMate importer;
7. restore the normal internet Wi-Fi connection afterward.

The integrated engine is based on the proven standalone SleepSync 1.1.5 behavior, while sharing SleepMate's backup, import, PWA, updater and diagnostic lifecycle.

## 19.2. Integrated UI

SleepSync has its own panels inside the normal SleepMate shell:

- **Overview** — Wi-Fi/SD status, last run, next run and health metrics;
- **Sync** — manual run, live phase, file and progress information;
- **History** — completed/failed runs and technical log;
- **Settings** — backup location, schedule, stability/incremental parameters and known internet Wi-Fi fallbacks.

## 19.3. Current automation is schedule-only

The **SleepMate 5.2.16 integrated SleepSync engine uses scheduled automation only**.

Older versions had a “sync when card becomes available” mode. The current engine:

- migrates an old `card_available` setting to `scheduled`;
- hides the old mode selector in the UI;
- starts automatic sync only on explicitly configured days and times.

Manual sync remains available at any time.

## 19.4. Windows Wi-Fi profile management and internet restoration

SleepSync uses a saved Windows Wi-Fi profile named **`ez Share`**. The engine can:

- query the current Wi-Fi connection;
- inspect networks visible to Windows;
- remember the normal internet Wi-Fi;
- temporarily manage profile auto-connect behavior;
- restore the previous internet connection after the card operation;
- use configured fallback internet SSIDs.

The implementation also handles Windows WLAN command encoding/localization details and can recover WLAN AutoConfig in selected failure cases.

## 19.5. Version 5.2.16 AP-presence-aware recovery

Legacy ez Share cards can behave like intermittent access points: the SSID may disappear even while other Wi-Fi networks continue to work.

The 5.2.16 recovery flow:

1. gives Windows a clean **12-second automatic-association grace period** without unnecessary scans, explicit connects or resets;
2. if association does not complete, performs two short scans to determine whether `ez Share` is actually broadcasting;
3. if ez Share is missing from both scans while other networks exist, classifies the condition as **“ez Share not broadcasting”**;
4. avoids pointless `netsh connect`, profile-repair or WLAN-reset loops in that condition;
5. restores and keeps the normal internet connection;
6. starts re-checking card presence after about **30 seconds** for a manual run or **45 seconds** for an automatic run;
7. then performs gentle presence checks approximately every **30 seconds**;
8. disconnects the internet again only once the ez Share SSID has really reappeared;
9. keeps the overall recovery window at up to roughly **25 minutes** for manual runs and **45 minutes** for automatic runs;
10. if Windows itself cannot return a valid scan list, avoids falsely declaring the card absent and falls back to the established active WLAN-recovery path.

## 19.6. HTTP/root readiness

A successful HTTP response alone is not considered a ready card. SleepSync waits for the actual parseable **`A:`** root directory.

Compatibility details:

- canonical root is **`A:`**, not `A:\`;
- direct IP/gateway access plus `ezshare.card` fallback is supported;
- the integrated adapter gives the real card-root readiness process at least approximately **60 seconds**, even when older configuration contains a shorter HTTP timeout.

This prevents an HTTP-200-but-empty page from becoming a false “zero files, everything up to date” success.

## 19.7. Recursive scan and mandatory ResMed validation

The engine recursively scans the SD tree. A run is valid only if the expected ResMed structure and mandatory sentinel validation succeed.

The current implementation uses **`STR.EDF`** as a mandatory ResMed sentinel. A zero-file scan or a missing mandatory structure is a **failure**, not a success.

## 19.8. Incremental synchronization state

SleepSync stores local metadata about previously synchronized files. It can determine whether a file is:

- new;
- changed;
- already known and verified;
- or intentionally due for re-check within a recent-data buffer.

The default `buffer_days` value is 2. Mandatory files are expected to be refreshed safely on every successful run.

## 19.9. Stable download protocol

A file is never treated as complete simply because a GET request returned bytes. The stable-download flow is:

1. read remote metadata;
2. wait for the configured stability interval — default **4 seconds**;
3. read metadata again;
4. download into a temporary `.sleepsync.part` file;
5. validate HTTP `Content-Length` when available;
6. read remote metadata again after download;
7. reject the transfer if the remote file changed while being downloaded;
8. atomically replace the final local file only after successful validation.

This protects against copying a CPAP file that the device is still actively writing.

## 19.10. Retry and fail-closed behavior

SleepSync deliberately fails closed instead of turning an incomplete sync into a reassuring green state.

Rules include:

- multiple per-file retries;
- a separate final retry queue;
- any remaining final file failure makes the run fail;
- failure to safely refresh mandatory ResMed files makes the run fail;
- a zero-file/zero-checked scan cannot succeed;
- a half-complete operation cannot report “everything up to date”.

## 19.11. One Wi-Fi session: synchronization + complete SD mirror + ZIP

The current integrated engine performs refresh and full SD backup in **the same card connection**.

A successful run creates:

- a dated run folder;
- a complete **`SD tartalma` / SD contents** mirror;
- a complete dated **ZIP** snapshot.

An already-known unchanged local file can be copied into the snapshot from the verified local state; new or changed files are downloaded from the card.

If final failures remain, **no half-finished ZIP is produced**.

The generated SD ZIP can later be re-imported through SleepMate's standard safe ZIP import.

## 19.12. SD snapshot is not a second system backup

SleepSync's **SD backup** is a complete snapshot of the ResMed card.

It is **not** a parallel SleepMate system backup.

- **SleepSync SD backup:** ResMed card mirror + ZIP archive.
- **SleepMate and SleepSync complete backup:** complete SleepMate managed state, patient data, settings and SleepSync private state.

The UI therefore does not require a separate duplicate “system backup” action in SleepSync. Every successful sync creates the SD snapshot automatically, while complete system backup remains in SleepMate's Backup settings.

## 19.13. Import after sync

After a verified snapshot is created, SleepSync uses the same safe SleepMate import path used by folder/ZIP import.

As a result:

- new therapy days can appear immediately;
- changed known days can refresh;
- the Dashboard can reload;
- the Sleep analysis cache can be invalidated;
- configured Web Push can notify about new or changed PAP data.

The importer intentionally does not treat a transiently incomplete remote scan as authoritative deletion.

## 19.14. SleepSync settings

Current engine settings can include:

- SD backup root — default `~/Documents/SleepSync_Backups`;
- automatic schedule enabled/disabled;
- selected weekdays;
- one or more times, default `09:00`;
- card-scan interval — supported 10–300 s, default 30 s;
- retry count — 1–10, default 5;
- automatic retry wait — 1–60 min, default 5 min;
- ez Share readiness timeout — internal 5–120 s range, while integrated root readiness is at least 60 s;
- stability wait — 2–30 s, default 4 s;
- recent-data buffer — 0–30 days, default 2 days;
- known internet Wi-Fi fallback networks.

## 19.15. Live state and history

The UI can display:

- current Wi-Fi;
- ez Share/SD visibility;
- connection state;
- run phase;
- progress percentage;
- total files;
- processed files;
- downloaded files;
- unchanged files;
- errors;
- current file;
- last run;
- next scheduled run;
- last error.

Run history retains up to 250 entries and can be cleared separately. The detailed technical log lives in SleepMate's private `sleepsync` state.

## 19.16. Shared application lifecycle

Integrated SleepSync:

- has no separate `SleepSync.exe` updater;
- is not a separate tray application;
- follows the same SleepMate release and updater lifecycle;
- is included in the same complete-system backup;
- hydrates into the PWA only after the core SleepMate startup path is ready;
- avoids aggressively terminating browser/captive-portal processes during Wi-Fi switching because such processes can also host SleepMate PWA renderers.

---

# 20. Optional AI analysis — Gemini and Groq

## 20.1. Optional by design

All core PAP features work without AI. AI use requires user-provided API access.

Current providers are:

- **Luna — Google Gemini**;
- **Milo — Groq**.

Display name and selected model are configurable. There is no central SleepMate AI proxy: provider requests go directly from the user's computer to the selected provider.

## 20.2. Analysis types

SleepMate can request, among other things:

- latest therapy-night analysis;
- latest 7 available therapy days;
- selected month;
- full available therapy history;
- comparison of two selected date ranges.

## 20.3. Dataset signature and analysis locks

SleepMate computes a **dataset signature** for the current therapy state. A saved analysis for the same analysis type and same dataset version can be reopened instead of unnecessarily resending identical data.

When therapy data changes, the signature changes and a new analysis can be generated for the updated state.

## 20.4. Contextual AI chat

Users can ask follow-up questions inside a saved analysis context.

Current UI limits:

- maximum **1200 characters** per user question;
- **10 questions per day per AI provider**;
- Gemini and Groq maintain separate daily counters.

AI results and conversations can be stored locally and reopened later.

## 20.5. Direct identifiers excluded from the AI payload

The safe-payload layer excludes fields including:

- name / full name;
- first/last name;
- email;
- phone;
- address;
- national health identifier;
- SSN;
- date/place of birth;
- device serial number;
- username / Windows username;
- IP address;
- MAC address;
- Wi-Fi SSID;
- patient identifier;
- clinician name;
- institution name;
- filename/path;
- free-text notes.

## 20.6. Minimized therapy/health data that may be sent

Depending on the requested analysis, the minimized payload may include:

- age;
- therapy start;
- diagnosis type;
- baseline AHI;
- ODI;
- SpO₂ data;
- prescription;
- pressure settings;
- device/mask type;
- therapy days and session timestamps;
- AHI and event components;
- event timing/duration;
- pressure statistics;
- leak;
- flow limitation;
- snore;
- respiratory rate;
- tidal volume;
- minute ventilation;
- available oximetry.

These are **health data**. SleepMate removes direct identifiers and minimizes the payload, but does not claim that a rich health dataset is mathematically and legally irreversibly anonymous under every possible external correlation scenario.

## 20.7. Safety rules in the AI system prompt

The system prompt instructs the AI to:

- use only supplied therapy data;
- never invent missing values;
- interpret OA, CA, H, RERA and UA separately;
- prioritize the user's own prior trends;
- avoid turning correlation into causation;
- use explicit confidence levels for important conclusions;
- not diagnose;
- not issue mandatory concrete PAP-pressure-change instructions.

## 20.8. Provider diagnostics

SleepMate includes connection testing and provider diagnostic logs. These can expose technical metadata such as:

- provider;
- model;
- transport;
- request ID;
- response time;
- HTTP status;
- provider error code;
- non-secret key source/hint/fingerprint metadata.

The actual API key is not printed into diagnostic exports.

---

# 21. Remote access through Tailscale

Tailscale integration is designed to make the local backend reachable from the user's own devices without directly binding SleepMate to the entire LAN.

SleepMate can:

- detect Tailscale installation/status;
- enable/disable Tailscale Serve;
- display the HTTPS tailnet URL;
- open the remote URL;
- generate a local QR code for phone access;
- target the actual current SleepMate localhost port;
- repair a stale SleepMate-looking Serve target after startup when an auto-selected local port has changed.

Tailscale remains an external service; the user's tailnet and account security remain the user's responsibility.

---

# 22. Remote access through Cloudflare Tunnel

SleepMate can optionally be published behind Cloudflare Tunnel.

The module can:

- detect `cloudflared`;
- inspect tunnel status;
- handle configured public hostname information;
- target the actual current localhost port;
- start/stop/check a tunnel;
- open the remote URL.

The UI explicitly emphasizes **Cloudflare Access / Zero Trust**. Publishing a health-data application through a public Tunnel without proper Access protection would be unsafe, so secure access configuration is treated as a core requirement rather than decoration.

If a tunnel is already managed as a Windows service, SleepMate does not necessarily need to store a tunnel token. When SleepMate itself starts a token-based tunnel, the secret can be stored in protected local state.

---

# 23. PWA and mobile use

The same SleepMate UI can run as an installable PWA. Over HTTPS — for example through Tailscale Serve or a properly protected Cloudflare setup — it can be installed on supported phones/desktops.

PWA/mobile features include:

- installable app experience;
- dedicated icon/splash;
- mobile bottom navigation;
- touch-friendly chart interactions;
- native sharing where available;
- PDF file saving;
- service-worker caching;
- graceful use of previously cached UI state during temporary backend outages;
- Web Push.

Offline UI availability does not turn SleepMate into a fully offline replicated database: fresh therapy data still requires access to the SleepMate backend.

---

# 24. Web Push notifications

SleepMate can generate a local VAPID key pair; the private VAPID key remains in backend private state.

Per-device subscriptions can enable notification categories such as:

- a new PAP/CPAP therapy night;
- modification of a previously known EDF/dataset;
- a diagnostic warning;
- backup failure.

The UI supports permission request, subscription storage, test notification and unsubscribe. With a compatible browser/PWA push environment, notifications can arrive even while the PWA is not currently in the foreground.

---

# 25. Local backend and port settings

SleepMate can use:

- automatic local-port selection;
- a fixed port.

Automatic mode typically starts searching from **8895** for a free local port. Some port changes apply after restart.

The backend is designed around `127.0.0.1` / localhost. Remote access is added through an explicit Tailscale/Cloudflare layer.

---

# 26. Update and rollback

The SleepMate update lifecycle can:

- check versions;
- use GitHub Releases as a package source;
- verify downloaded package SHA-256;
- optionally check for updates at startup;
- install only through explicit user action;
- create a complete backup/rollback point before update;
- replace running files through an external updater process;
- automatically roll back after a failed new build;
- support manual rollback;
- make update checks more resilient to transient network failures.

## Code signing policy

The official release-signing rules are defined in [`CODE_SIGNING_POLICY.md`](CODE_SIGNING_POLICY.md).

**Code-signing status:** the repository includes a SignPath-oriented code-signing policy, artifact configurations and release gates. The official SignPath Foundation-signed production pipeline is still being prepared; the source repository must not imply that every current build is already signed.

---

# 27. Windows build/runtime

The Windows build path includes:

- PyInstaller packaging;
- onedir-style distribution;
- no UPX compression;
- normal no-console user execution;
- Windows tray integration;
- local HTTP backend plus web/PWA frontend;
- separate updater component;
- build/release workflows with explicit release/signing gates.

Build and installer resources in the repository are development/CI assets. The final official signed distribution format is governed by the completed SignPath release process.

---

# 28. Tests and regression gates

The project contains both unit tests and product-behavior regression/contract tests. Covered areas include:

- ResMed EDF processing;
- import and non-destructive refresh;
- backup/restore;
- patient backup;
- PDF reports;
- AI-payload minimization;
- AI providers/history;
- PWA/service worker;
- Web Push;
- Tailscale;
- Cloudflare;
- updater/rollback;
- Windows packaging;
- SleepSync ez Share scanning;
- stable SleepSync downloads;
- complete SleepSync SD snapshots;
- SleepSync Wi-Fi recovery;
- 5.2.16 AP-presence-aware recovery;
- sleep-block classification and manual overrides.

The public stable-release workflow is intended to fail closed rather than silently publish a release when required release/signing conditions are missing.

---

# 29. Privacy summary

See the complete policy in [`PRIVACY.md`](PRIVACY.md).

Core technical principles:

- PAP measurements and patient data are local by default;
- no central SleepMate health database;
- external providers are opt-in;
- direct identifiers are filtered before AI payload creation;
- Google Drive uses the user's own account/OAuth configuration;
- Tailscale/Cloudflare are optional remote-access mechanisms;
- support bundles are not raw EDF/secret dumps;
- the user still needs to protect the Windows account, computer, backups and external-service accounts.

---

# 30. Not medical diagnostic software

**SleepMate is not a medical diagnostic system.**

It does not:

- diagnose disease;
- replace a sleep study;
- replace a physician;
- replace PAP titration;
- prescribe medication;
- authorize unsupervised medication changes;
- automatically change therapy pressure;
- guarantee the medical accuracy of AI output.

Its purpose is to help users review and understand their own data. Clinical decisions require an appropriate healthcare professional.

---

# 31. Repository structure

```text
SleepMate-Public/
├─ app.py                         # local HTTP/API backend
├─ cpap/                          # EDF, import, backup, AI, reports, remote access, SleepSync
│  ├─ resmed.py
│  ├─ edf.py
│  ├─ services.py
│  ├─ patient_store.py
│  ├─ report_pdf.py
│  ├─ ai_payload.py
│  ├─ ai_provider.py
│  ├─ ai_store.py
│  ├─ google_drive_integration.py
│  ├─ remote_access.py
│  ├─ push_service.py
│  ├─ maintenance.py
│  ├─ sleep_analysis.py
│  ├─ sleepsync_engine_v2.py
│  ├─ sleepsync_legacy.py
│  └─ ...
├─ web/                           # Dashboard, PWA, charts, SleepSync UI
├─ tests/                         # unit + regression/contract tests
├─ build/                         # Windows build/installer resources
├─ .github/workflows/             # CI / release workflows
├─ .signpath/ + signpath configs  # signing preparation
├─ PRIVACY.md
├─ SECURITY.md
├─ CODE_SIGNING_POLICY.md
├─ THIRD_PARTY_NOTICES.md
├─ TRADEMARKS.md
└─ LICENSE
```

---

# 32. License, branding and contributions

SleepMate source code is published under **GNU AGPL v3.0 only**. See [`LICENSE`](LICENSE).

Third-party notices: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

SleepMate name, visual identity and related marks can be subject to separate trademark/branding conditions: [`TRADEMARKS.md`](TRADEMARKS.md).

Responsible security reporting: [`SECURITY.md`](SECURITY.md).

Contribution guide: [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

# 33. Contact

**SleepMate projekt – BenWyxell – Kovács Lóránd E.V.**  
**Email:** hello@mysleepmate.hu
