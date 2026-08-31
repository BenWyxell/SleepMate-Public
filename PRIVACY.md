# SleepMate – Adatvédelmi és Adatkezelési Tájékoztató

**Hatályos:** 2026. augusztus 31.
**Verzió:** 1.0

## 1. A tájékoztató célja

Jelen Adatvédelmi és Adatkezelési Tájékoztató a SleepMate alkalmazás („SleepMate”, „Alkalmazás”, „Szoftver”) működésével kapcsolatos adatkezelési folyamatokat ismerteti.

A SleepMate alapvető működési elve a **helyi, felhasználó által ellenőrzött adattárolás**. Az alkalmazás használatához nem szükséges SleepMate-felhasználói fiók létrehozása, és a SleepMate nem működtet olyan központi felhőszolgáltatást vagy központi egészségügyi adatbázist, amelybe a felhasználó terápiás vagy egészségügyi adatai automatikusan feltöltésre kerülnének.

A SleepMate letöltése, telepítése és normál helyi használata során a felhasználó által az alkalmazásban tárolt egészségügyi és terápiás adatok **nem kerülnek továbbításra a SleepMate fejlesztőjének vagy kiadójának**.

A Szoftver egyes opcionális funkciói – például Google Drive biztonsági mentés, mesterséges intelligencián alapuló kiértékelés, Tailscale vagy Cloudflare alapú távoli hozzáférés – külső szolgáltatók igénybevételével működhetnek. Ezek használata nem kötelező, azokat a felhasználó saját döntése alapján, külön beállítással aktiválhatja.

---

# 2. A SleepMate kiadója / kapcsolattartó

**Kiadó / fejlesztő:** SleepMate projekt – BenWyxell – Kovács Lóránd E.V.
**Kapcsolattartási e-mail:** hello@mysleepmate.hu

A jelen tájékoztatóban „Fejlesztő” alatt a SleepMate fenti kiadója értendő.

---

# 3. A SleepMate alapvető adatvédelmi működése

A SleepMate úgy került kialakításra, hogy a felhasználó CPAP/PAP terápiával és egészségi állapotával kapcsolatos adatai alapértelmezetten a felhasználó saját számítógépén maradjanak.

A SleepMate normál helyi használata során:

- nincs központi SleepMate-felhasználói fiók;
- nincs központi SleepMate egészségügyi adatbázis;
- nincs automatikus felhasználói adatszinkron a Fejlesztő rendszerével;
- nincs olyan SleepMate felhő, amelybe a terápiás adatok automatikusan feltöltődnének;
- a Fejlesztő nem kapja meg a felhasználó CPAP/PAP terápiás adatait;
- a Fejlesztő nem kapja meg a felhasználó diagnózisait, gyógyszereit, terápiás előírásait vagy egyéb egészségügyi nyilvántartását;
- a Fejlesztő nem látja a felhasználó SleepMate Dashboardját;
- a Fejlesztő nem fér hozzá távolról a SleepMate adatbázisához;
- a Fejlesztő nem kap automatikus másolatot az elkészített jelentésekről, exportokról vagy biztonsági mentésekről;
- nincs beépített kötelező egészségügyi telemetria vagy használati analitika, amely a terápiás adatokat a Fejlesztőnek továbbítaná.

**A SleepMate használatából származó egészségügyi adatok a Fejlesztőhöz automatikusan nem jutnak el.**

---

# 4. A helyileg kezelt adatok köre

A felhasználó által igénybe vett funkcióktól függően a SleepMate a felhasználó saját számítógépén többek között az alábbi adatokat kezelheti.

## 4.1. Személyes és egészségügyi profiladatok

Ilyenek lehetnek például:

- név;
- születési dátum;
- életkor;
- terápia kezdő időpontja;
- diagnózis típusa;
- diagnózis időpontja;
- diagnosztikai AHI;
- ODI;
- véroxigénszinttel kapcsolatos adatok;
- titrálási adatok;
- terápiás előírások;
- fix vagy automatikus terápiás nyomástartomány;
- gyógyszerek;
- testsúly és egyéb kézzel rögzített adatok;
- kontrollok;
- megjegyzések.

## 4.2. CPAP/PAP terápiás adatok

A SleepMate kezelheti többek között:

- terápiás napokat;
- használati időt;
- terápiás sessionöket;
- AHI-t;
- OA, CA, H, UA, RERA és CSR eseményeket;
- események számát és időpontját;
- apnoe-időt;
- nyomásértékeket;
- EPR-rel kapcsolatos értékeket;
- maszkon mért nyomást;
- szivárgási adatokat;
- flow limitation értékeket;
- horkolási adatokat;
- légzésszámot;
- tidal volume értékeket;
- minute ventilation értékeket;
- rendelkezésre állás esetén pulzus- és véroxigénadatokat;
- CPAP-készülék által létrehozott EDF és kapcsolódó terápiás állományokból kinyert információkat.

## 4.3. Felszereléssel kapcsolatos adatok

A SleepMate nyilvántarthatja például:

- CPAP/PAP-készülék gyártóját és típusát;
- maszk gyártóját és típusát;
- maszk kategóriáját és méretét;
- párásítót;
- csövet;
- egyéb kiegészítőket;
- felszerelés-váltásokat és azok időpontját.

## 4.4. Alkalmazásadatok

A SleepMate helyileg tárolhat továbbá:

- programbeállításokat;
- importálási és szinkronizálási beállításokat;
- helyi naplókat;
- biztonsági mentéseket;
- AI-kiértékelések eredményeit;
- AI-beszélgetési előzményeket;
- API-kulcsokat;
- Google OAuth tokeneket;
- opcionális távoli eléréshez szükséges titkos adatokat.

Ezen adatok kezelése a felhasználó saját számítógépén történik.

---

# 5. Helyi adattárolás és titkosítás

A SleepMate privát adattárolójának érzékeny részei titkosított formában tárolhatók.

A jelenlegi SleepMate verzió hordozható, 256 bites AES-GCM alapú titkosítási mechanizmust alkalmaz a privát adatok meghatározott részeinek védelméhez.

A titkosítási kulcs szintén a SleepMate helyi privát adattárának része, annak érdekében, hogy a teljes SleepMate biztonsági mentés másik számítógépen is visszaállítható legyen.

Ezért a felhasználónak különösen fontos megfelelően védenie:

- a Windows felhasználói fiókját;
- a számítógéphez történő fizikai hozzáférést;
- a SleepMate adatkönyvtárát;
- a teljes SleepMate biztonsági mentéseket;
- a Google Drive-ra vagy más külső helyre másolt biztonsági mentéseket.

A SleepMate helyi titkosítása nem helyettesíti az operációs rendszer, a meghajtótitkosítás, a megfelelő jelszóvédelem, a biztonságos mentés és az általános informatikai védelem alkalmazását.

---

# 6. Adatok megőrzése és törlése

Mivel a SleepMate alapértelmezetten helyileg tárolja az adatokat, azok megőrzési idejét elsődlegesen a felhasználó határozza meg.

A helyileg tárolt adatok addig maradhatnak a számítógépen vagy a felhasználó által készített biztonsági mentésekben, amíg azokat a felhasználó nem törli.

Az alkalmazás eltávolítása önmagában nem feltétlenül jelenti valamennyi korábban létrehozott adat, export vagy biztonsági mentés törlését.

A felhasználó felelőssége az általa készített:

- ZIP-mentések;
- teljes biztonsági mentések;
- PDF-jelentések;
- exportált fájlok;
- más számítógépre másolt adatok;
- felhőbe feltöltött mentések

kezelése és törlése.

---

# 7. CPAP-adatok importálása

A SleepMate CPAP/PAP terápiás adatokat többféle helyi forrásból képes feldolgozni, például:

- SD-kártyáról;
- helyi könyvtárból;
- korábban létrehozott másolatból;
- ZIP-állományból;
- manuálisan;
- kompatibilis ez Share Wi-Fi SD-megoldáson keresztül.

Az importált terápiás adatok feldolgozása a felhasználó saját számítógépén történik.

Az importálás önmagában nem továbbítja az adatokat a Fejlesztőnek.

---

# 8. SleepSync és ez Share

A SleepMate SleepSync funkciója kompatibilis konfiguráció esetén képes egy ez Share Wi-Fi SD adapterhez csatlakozni és arról CPAP/PAP adatokat beolvasni.

A kapcsolat a felhasználó saját:

- számítógépe;
- Wi-Fi adaptere;
- ez Share eszköze;
- CPAP/PAP SD-kártyája

között jön létre.

Az ez Share használata opcionális.

A SleepMate a SleepSync működése közben kezelheti a Windows Wi-Fi kapcsolatát, ellenőrizheti az ez Share hálózat jelenlétét, kapcsolódhat az adapterhez, majd a terápiás állományokat a felhasználó saját számítógépére másolhatja.

A SleepSync használatakor a CPAP/PAP terápiás állományok **nem kerülnek a SleepMate Fejlesztőjének szerverére**.

Az ez Share eszköz biztonságos konfigurálásáért, Wi-Fi-beállításaiért és fizikai hozzáférésének védelméért a felhasználó felel.

---

# 9. Google Drive biztonsági mentés

## 9.1. Opcionális funkció

A Google Drive integráció nem szükséges a SleepMate normál működéséhez.

A felhasználó saját döntése alapján konfigurálhat Google Drive kapcsolatot, ha SleepMate biztonsági mentéseit saját Google Drive-fiókjában kívánja tárolni.

A funkció használatához a felhasználó saját Google-fiókját és az ehhez szükséges OAuth-konfigurációt használja.

## 9.2. Kért Google-jogosultságok

A SleepMate jelenlegi implementációja a következő Google jogosultságokat használja:

**Google Drive** **`drive.file`** **jogosultság**

Ez lehetővé teszi a SleepMate számára, hogy a felhasználó által az alkalmazással használt vagy az alkalmazás által létrehozott konkrét Drive-fájlokat létrehozza és kezelje.

A SleepMate nem kér általános, teljes Google Drive-hozzáférést.

**Google-fiók e-mail-címe**

A SleepMate lekérheti a csatlakoztatott Google-fiók e-mail-címét azért, hogy a felületen meg tudja jeleníteni, melyik Google-fiók van csatlakoztatva.

## 9.3. Feltöltött adatok

Google Drive mentés engedélyezése esetén a SleepMate biztonsági mentési ZIP-állományt tölthet fel a felhasználó saját Google Drive tárhelyére, alapértelmezetten egy SleepMate biztonsági mentésekhez használt mappába.

A mentés a SleepMate helyi adatainak másolatát tartalmazhatja, ezért **egészségügyi és egyéb érzékeny adatok is lehetnek benne**.

## 9.4. Ki kapja meg az adatokat?

A feltöltés közvetlenül a felhasználó számítógépe és a Google szolgáltatása között történik.

A Fejlesztő:

- nem kapja meg a biztonsági mentést;
- nem tárolja annak másolatát;
- nem fér hozzá a felhasználó Google Drive-fiókjához;
- nem kapja meg a Google OAuth hozzáférési tokenjét.

A szükséges OAuth-adatok helyileg kerülnek tárolásra.

## 9.5. A kapcsolat megszüntetése

A felhasználó a Google Drive kapcsolatot kikapcsolhatja, és a Google-fiókjában is visszavonhatja a SleepMate számára korábban megadott jogosultságokat.

A Google Drive használatára a Google mindenkori adatvédelmi, biztonsági és szolgáltatási feltételei is vonatkoznak.

---

# 10. Mesterséges intelligenciával végzett kiértékelés

## 10.1. Opcionális funkció

A SleepMate mesterséges intelligencián alapuló terápiás összegző és elemző funkciója teljes mértékben opcionális.

Az alkalmazás AI-funkciók nélkül is használható.

Az AI-funkció csak akkor működik, ha a felhasználó saját API-hozzáférést konfigurál.

A jelenlegi verzió többek között az alábbi szolgáltatókat támogatja:

- Google Gemini;
- Groq.

A Fejlesztő nem biztosít központi SleepMate AI-proxyt, amelyen keresztül a felhasználók egészségügyi adatai áthaladnának.

A kérés közvetlenül a felhasználó számítógépéről a kiválasztott AI-szolgáltatóhoz kerül.

---

# 11. Milyen adatokat nem továbbít a SleepMate az AI-szolgáltatónak?

A SleepMate az AI-kiértékelés előtt adatvédelmi szűrőt alkalmaz.

A jelenlegi implementáció többek között kizárja az AI-nak továbbított strukturált adatcsomagból a következő mezőket:

- név;
- teljes név;
- vezetéknév;
- keresztnév;
- e-mail-cím;
- telefonszám;
- lakcím;
- TAJ-szám;
- SSN;
- születési dátum;
- születési hely;
- készülék sorozatszáma;
- felhasználónév;
- Windows-felhasználónév;
- IP-cím;
- MAC-cím;
- Wi-Fi SSID;
- betegazonosító;
- orvos neve;
- intézmény neve;
- fájlnév;
- fájlútvonal;
- szabad szöveges jegyzetek.

A SleepMate tehát kialakítása szerint **közvetlen személyazonosításra alkalmas adatokat nem küld az AI-szolgáltatónak**.

---

# 12. Milyen adatokat továbbíthat a SleepMate az AI-szolgáltatónak?

Az AI-elemzéshez szükséges adatminimalizált terápiás csomag ugyanakkor tartalmazhat például:

- életkort;
- terápia kezdő időpontját;
- diagnózis típusát;
- kiindulási AHI-t;
- ODI-t;
- SpO₂ értékeket;
- terápiás előírásokat;
- nyomásbeállításokat;
- készülék gyártóját és típusát;
- maszk típusát és méretét;
- terápiás napok dátumait;
- használati időket;
- session-időpontokat;
- AHI-t;
- OA, CA, H, UA, RERA és CSR eseményszámokat;
- egyes események időpontját és időtartamát;
- nyomásstatisztikát;
- szivárgási adatokat;
- flow limitation értékeket;
- horkolást;
- légzésszámot;
- tidal volume értékeket;
- minute ventilation értékeket;
- rendelkezésre állás esetén oximetriás adatokat.

Ezek az adatok önmagukban közvetlen nevet vagy azonosítót nem tartalmaznak, azonban **egészségügyi jellegű adatok**.

Bizonyos körülmények között egy megfelelően nagy vagy más információkkal összekapcsolható adatcsomag közvetett módon személyhez köthető lehet. Emiatt a SleepMate nem állítja, hogy minden körülmények között matematikailag vagy jogilag visszafordíthatatlan anonimizálás történik.

A pontos megfogalmazás ezért:

**A SleepMate az AI-szolgáltatóknak közvetlen személyazonosító adatot nem továbbít; az AI kizárólag azonosítóktól megtisztított, adatminimalizált terápiás adatcsomagot kap.**

---

# 13. Az AI számára alkalmazott konkrét rendszerprompt

A SleepMate jelenlegi AI-kiértékelése a következő rendszerutasítást alkalmazza:

> Te egy PAP/CPAP terápiás adatelemző asszisztens vagy. Magyarul válaszolj, laikus számára érthetően, de szakmailag pontosan.
>
> Kizárólag a kapott anonim terápiás JSON-ból dolgozz. Ne találj ki hiányzó adatot. Ne diagnosztizálj és ne adj kötelező, konkrét nyomásmódosítási utasítást. OA, CA, H, RERA és UA eseményeket külön értelmezd. A saját korábbi adatok és trendek legyenek az elsődleges referencia. Korrelációból ne állíts automatikusan okozati kapcsolatot. A fontosabb következtetésekhez használj high/medium/low bizonyossági szintet.
>
> Minden felhasználónak szánt szöveg magyar legyen, beleértve az overall.title és a trends[].title mezőket is. Az overall.title legyen rövid, természetes és informatív magyar cím, ne programozói/generikus cím. A címben dátumot csak akkor használj, ha tényleg szükséges; ha használsz, kizárólag ÉÉÉÉ.HH.NN. formátumban. Minden más dátumot is ÉÉÉÉ.HH.NN. formában írj ki a természetes szövegekben.
>
> A válaszod KIZÁRÓLAG érvényes JSON objektum legyen, markdown kódblokk nélkül. A JSON első mezője legyen a live\_text, amely 2–5 mondatos, természetes magyar összefoglaló, hogy a felület már generálás közben meg tudja jeleníteni.
>
> Ha egy teljes témához nincs adat, a megfelelő mező legyen null vagy röviden jelezd az adathiányt; ne gyárts értéket.

A SleepMate az elemzés típusától függően ehhez további utasítást ad.

### Egy éjszaka

> Az utolsó terápiás éjszakát elemezd részletesen. Keresd a session megszakításokat, AHI/OA/CA/H/RERA szerkezetét, nyomás- és szivárgási mintázatot, és hasonlítsd a rendelkezésre álló saját előzményekhez. Fő kérdés: mi történt ezen az éjszakán, mennyire volt eredményes és stabil a terápia, és van-e valami, amire érdemes figyelni?

### Egy hét

> Az utolsó 7 rendelkezésre álló terápiás nap mintázatait értékeld. Ne reagálj túl egyetlen rossz éjszakára; keresd az ismétlődő trendeket, compliance-et, AHI és eseménytípusok, nyomás és szivárgás változását. Fő kérdés: látható-e már ismétlődő minta vagy egyértelmű heti tendencia?

### Egy hónap

> A kiválasztott hónap terápiás fejlődését értékeld. Vizsgáld az AHI, OA/CA/H/RERA, használat, nyomás, szivárgás és légzési mutatók trendjét, valamint az időszak eleje és vége közötti változást. Fő kérdés: merre halad a terápia: stabilizálódik, javul, romlik vagy lényegében változatlan?

### Teljes időszak

> A rendelkezésre álló teljes PAP-terápiás időszakot értékeld átfogóan. Emeld ki a hosszú távú trendeket, stabil és visszatérő problémákat, legjobb/rosszabb időszakokat, valamint a terápiás előírások vagy felszerelés-változások utáni mérhető eltéréseket. Fő kérdés: hogyan alakult a PAP-terápia a kezelés megkezdésétől mostanáig?

### Két időszak összehasonlítása

> Két külön terápiás időszakot hasonlíts össze. A B időszakot tekintsd az újabb/összehasonlítandó állapotnak. Külön értékeld az AHI, OA/CA/H/RERA index, használati idő, nyomás P95 és szivárgás P95 változását. Ne csak azt írd le, hogy eltérnek: mondd meg, melyik irány kedvező vagy kedvezőtlen, és jelezd, ha a kevés terápiás nap miatt gyenge a bizonyosság. Fő kérdés: mi változott mérhetően a két időszak között?

Az aktuális terápiás JSON kizárólag az adatvédelmi szűrés után kerül ehhez az utasításhoz hozzáfűzésre.

---

# 14. AI-chat

A már elkészült AI-kiértékeléshez kapcsolódó további kérdések esetén a SleepMate az előző, helyileg tárolt kiértékelést, az azonosítóktól megtisztított terápiás adatcsomagot és a beszélgetés szükséges részét továbbíthatja ugyanahhoz az AI-szolgáltatóhoz.

A chat rendszerutasítása külön előírja, hogy az AI:

- csak a rendelkezésre álló terápiás adatokból dolgozzon;
- ne találjon ki adatot;
- ne diagnosztizáljon;
- ne adjon kötelező konkrét nyomásmódosítási utasítást;
- adathiány esetén ezt egyértelműen jelezze.

---

# 15. Google Gemini használata

A Gemini használatához a felhasználó saját Gemini API-kulcsát adja meg.

A kulcsot a SleepMate helyileg, védett formában tárolja.

AI-kéréskor az adatminimalizált terápiás adatcsomag közvetlenül a Google Gemini API szolgáltatásához kerül továbbításra.

A Google adatkezelési feltételei az alkalmazott Gemini szolgáltatási csomagtól függhetnek.

Különösen fontos, hogy a Google Gemini API **ingyenes szolgáltatási szintjén** a Google mindenkori feltételei alapján a beküldött tartalom felhasználható lehet szolgáltatások és modellek fejlesztéséhez.

Fizetős Gemini API szolgáltatási szinten a Google eltérő adatfelhasználási szabályokat alkalmazhat, és a jelenlegi feltételek alapján a fizetős szolgáltatás tartalmát nem használja termékei fejlesztésére.

A felhasználónak ezért a Gemini használatának aktiválása előtt célszerű megismernie a saját API-fiókjára vonatkozó aktuális Google feltételeket.

---

# 16. Groq használata

A Groq használatához a felhasználó saját Groq API-kulcsát adja meg.

A SleepMate az adatminimalizált terápiás adatcsomagot közvetlenül a Groq API-nak továbbítja.

A Groq jelenlegi tájékoztatása alapján a hagyományos inference kérések bemeneti és kimeneti tartalmát alapértelmezetten nem tárolja tartósan.

Bizonyos rendszerbiztonsági, megbízhatósági vagy visszaélés-vizsgálati esetekben azonban átmeneti naplózás történhet.

A Groq egyes fiókokhoz Zero Data Retention adatkezelési lehetőséget is biztosíthat.

A mindenkori Groq-feltételek és adatkezelési beállítások megismerése a felhasználó felelőssége.

---

# 17. AI-eredmények helyi tárolása

A SleepMate az elkészült AI-kiértékeléseket és a hozzájuk tartozó beszélgetési előzményeket helyileg tárolhatja.

Az AI API-kulcsok és az AI-előzmények a SleepMate privát adattárának védett részében helyezkednek el.

A Fejlesztő ezekhez nem kap automatikus hozzáférést.

---

# 18. Tailscale távoli hozzáférés

A SleepMate opcionálisan együttműködhet a Tailscale szolgáltatással.

A Tailscale használata nem kötelező.

A SleepMate saját webes háttérszolgáltatása alapértelmezetten a helyi számítógép `127.0.0.1` címéhez kötött.

Tailscale Serve használatakor a Tailscale ezt a helyi szolgáltatást teszi elérhetővé a felhasználó saját Tailscale hálózatán keresztül.

A SleepMate nem üzemeltet ehhez közvetítő szervert.

A Tailscale tájékoztatása szerint a hálózati kapcsolat tartalma végpontok között titkosított, ugyanakkor a Tailscale a szolgáltatás működtetéséhez technikai metaadatokat – például eszköz-, IP-, kapcsolat- és forgalmi statisztikai adatokat – kezelhet.

A Tailscale-fiók és a tailnet megfelelő védelme a felhasználó felelőssége.

---

# 19. Cloudflare Tunnel

A SleepMate opcionálisan Cloudflare Tunnel használatával is elérhetővé tehető távolról.

A Cloudflare használata nem kötelező.

Cloudflare Tunnel esetén a `cloudflared` komponens kimenő kapcsolatot hoz létre a Cloudflare hálózatával, ezért a felhasználónak nem szükséges közvetlen bejövő hálózati portot megnyitnia.

A Cloudflare Tunnel használatakor a távoli forgalom a Cloudflare infrastruktúráján keresztül haladhat.

Ennek megfelelően a Cloudflare saját adatvédelmi, naplózási, biztonsági és adatfeldolgozási szabályai alkalmazandók.

Különösen fontos a Cloudflare Access vagy más megfelelő hozzáférés-védelmi mechanizmus megfelelő konfigurálása.

Egy hibásan vagy túl széles körben publikált Cloudflare Tunnel az alkalmazás illetéktelen elérésének kockázatát növelheti.

A Cloudflare konfiguráció a felhasználó döntése és felelőssége.

---

# 20. GitHub és szoftverfrissítések

A SleepMate képes GitHub-alapú szoftverfrissítés-ellenőrzésre és frissítések letöltésére.

Az ilyen ellenőrzés során a program hálózati kapcsolatot létesíthet a GitHub infrastruktúrájával.

A frissítésellenőrzéshez terápiás vagy egészségügyi adatok továbbítása nem szükséges.

A Fejlesztő saját szerverére a frissítésellenőrzés során sem kerülnek CPAP/PAP egészségügyi adatok.

A GitHub – mint külső szolgáltató – a hálózati kapcsolat során a saját szabályai alapján technikai adatokat, például IP-címet, időpontot vagy HTTP-kéréshez kapcsolódó adatokat kezelhet.

---

# 21. Automatikus adatküldés a Fejlesztő felé

A SleepMate jelenlegi működésében nincs olyan mechanizmus, amely a felhasználó:

- terápiás adatait;
- egészségügyi profilját;
- diagnózisát;
- gyógyszereit;
- készülékadatait;
- AI-elemzéseit;
- jelentéseit;
- Google Drive mentéseit

automatikusan a Fejlesztőhöz továbbítaná.

**A program egyszerű letöltésével, telepítésével vagy helyi használatával a Fejlesztő nem kapja meg a felhasználó egészségügyi adatait.**

---

# 22. Felhasználó által önkéntesen elküldött adatok

Más a helyzet, ha a felhasználó saját döntése alapján közvetlenül kapcsolatba lép a Fejlesztővel, és például:

- e-mailt küld;
- hibajegyet küld;
- képernyőképet küld;
- naplófájlt küld;
- szervizcsomagot küld;
- terápiás fájlt vagy jelentést mellékel.

Ebben az esetben kizárólag a felhasználó által önkéntesen elküldött adatok jutnak el a Fejlesztőhöz.

A SleepMate szervizcsomag létrehozása önmagában nem jelenti annak automatikus elküldését.

A felhasználó minden esetben ellenőrizze, hogy a támogatási célból elküldött fájl valóban csak olyan adatokat tartalmaz-e, amelyeket meg kíván osztani.

---

# 23. Harmadik fél által biztosított szolgáltatások

A SleepMate opcionálisan együttműködhet külső szolgáltatásokkal, többek között:

- Google Drive;
- Google Gemini;
- Groq;
- Tailscale;
- Cloudflare;
- GitHub.

E szolgáltatások önálló szolgáltatók, amelyekre saját felhasználási feltételeik, adatvédelmi tájékoztatóik, adatmegőrzési szabályaik és adott esetben nemzetközi adattovábbítási rendelkezéseik vonatkoznak.

A Fejlesztő nem vállalhat felelősséget e külső szolgáltatók saját rendszereinek adatkezelési gyakorlatáért.

A külső szolgáltatás aktiválásával a felhasználó maga dönt arról, hogy az adott szolgáltatást igénybe kívánja-e venni.

---

# 24. Nemzetközi adattovábbítás

A SleepMate helyi működése önmagában nem jár a terápiás adatok nemzetközi továbbításával.

Opcionális külső szolgáltatások használata azonban eredményezheti adatok Európai Gazdasági Térségen kívüli kezelését.

Ez különösen felmerülhet:

- AI API használatakor;
- Google-szolgáltatások használatakor;
- Groq használatakor;
- Cloudflare használatakor;
- Tailscale használatakor;
- egyéb felhőszolgáltatások igénybevételekor.

Az ilyen adattovábbításra az adott külső szolgáltató mindenkori adatvédelmi és szerződéses feltételei vonatkoznak.

---

# 25. Az érintett jogai

A SleepMate helyi adatainak jelentős része soha nem kerül a Fejlesztő birtokába.

Ezért a Fejlesztő például nem tud másolatot kiadni olyan terápiás adatokról, amelyek kizárólag a felhasználó saját számítógépén találhatók, és azok törlését sem tudja távolról végrehajtani.

A helyileg tárolt adatok felett maga a felhasználó rendelkezik.

Amennyiben a felhasználó valamely külső szolgáltatást használ, az adott szolgáltató által kezelt adatok tekintetében az érintetti jogokat az adott szolgáltatónál is lehet gyakorolni.

Amennyiben a felhasználó közvetlenül a Fejlesztőnek küld személyes adatot – például támogatási megkeresésben –, jogosult lehet többek között:

- tájékoztatást kérni;
- hozzáférést kérni;
- helyesbítést kérni;
- törlést kérni;
- az adatkezelés korlátozását kérni;
- tiltakozni az adatkezelés ellen, amennyiben ennek jogszabályi feltételei fennállnak;
- panaszt tenni a felügyeleti hatóságnál.

---

# 26. Felügyeleti hatóság

Magyarországon adatvédelmi ügyekben az illetékes felügyeleti hatóság:

**Nemzeti Adatvédelmi és Információszabadság Hatóság (NAIH)**

Székhely:
1055 Budapest, Falk Miksa utca 9–11.

Levelezési cím:
1363 Budapest, Pf. 9.

E-mail:
[ugyfelszolgalat@naih.hu](mailto\:ugyfelszolgalat@naih.hu)

Telefon:
+36 (1) 391 1400

Az érintett jogosult panaszt tenni a NAIH-nál, ha megítélése szerint személyes adatainak kezelése sérti az alkalmazandó adatvédelmi jogszabályokat.

---

# 27. A felhasználó felelőssége

Mivel a SleepMate alapvetően helyi alkalmazás, a felhasználó saját környezetének biztonsága kiemelt jelentőségű.

A felhasználó felelőssége különösen:

- számítógépének megfelelő védelme;
- Windows-fiókjának védelme;
- megfelelő jelszó vagy PIN alkalmazása;
- rendszeres biztonsági frissítések telepítése;
- kártevők elleni védelem;
- biztonsági mentések megfelelő tárolása;
- API-kulcsok bizalmas kezelése;
- Google-fiókjának védelme;
- Tailscale-fiókjának védelme;
- Cloudflare konfigurációjának védelme;
- az ez Share Wi-Fi megfelelő konfigurációja;
- az exportált PDF-ek és ZIP-ek megfelelő kezelése.

---

# 28. Nem orvosi diagnosztikai szoftver

**A SleepMate nem orvosi diagnosztikai szoftver.**

A SleepMate célja a felhasználó saját CPAP/PAP terápiás adatainak:

- megjelenítése;
- rendszerezése;
- összehasonlítása;
- könnyebb értelmezésének támogatása;
- statisztikai és információs összefoglalása.

A SleepMate által megjelenített számítások, figyelmeztetések, grafikonok, értékelések és AI által generált szövegek **nem minősülnek orvosi diagnózisnak vagy orvosi tanácsnak**.

A SleepMate:

- nem helyettesíti az orvost;
- nem helyettesíti az alvásdiagnosztikai vizsgálatot;
- nem helyettesíti a CPAP/PAP titrálást;
- nem állít fel diagnózist;
- nem jogosít fel gyógyszeres kezelés megváltoztatására;
- nem jogosít fel előírt terápiás beállítás önálló megváltoztatására;
- nem garantálja az AI-válaszok orvosi pontosságát.

A terápiával, egészségi állapottal vagy készülékbeállításokkal kapcsolatos döntések esetén megfelelő egészségügyi szakember véleményét kell kérni.

Sürgős vagy súlyos egészségügyi panasz esetén a SleepMate használata helyett megfelelő egészségügyi ellátást kell igénybe venni.

---

# 29. Mesterséges intelligencia korlátai

Az AI által létrehozott válasz:

- lehet pontatlan;
- félreértelmezhet adatokat;
- figyelmen kívül hagyhat fontos körülményeket;
- nem ismeri a felhasználó teljes kórtörténetét;
- nem helyettesíti az orvosi vizsgálatot.

A SleepMate ezért az AI-t adatelemzést segítő funkcióként, nem pedig automatizált orvosi döntéshozó rendszerként használja.

A rendszerprompt kifejezetten tiltja az AI számára a diagnózis felállítását és a kötelező konkrét nyomásmódosítási utasítás adását.

---

# 30. Automatizált döntéshozatal

A SleepMate nem hoz a felhasználóra nézve joghatással vagy hasonlóan jelentős hatással járó automatizált döntést.

Az AI által készített értékelések kizárólag tájékoztató jellegűek.

A felhasználó maga dönt arról, hogy azokat megtekinti-e, figyelembe veszi-e, vagy megosztja-e egészségügyi szakemberrel.

---

# 31. Adatbiztonság

A SleepMate fejlesztése során törekvés történik az adatminimalizálásra és az érzékeny helyi adatok megfelelő technikai védelmére.

Ugyanakkor egyetlen informatikai rendszer sem tekinthető abszolút biztonságosnak.

A Fejlesztő nem tudja kontrollálni:

- a felhasználó számítógépének biztonságát;
- a felhasználó jelszavait;
- a felhasználó Google-fiókját;
- a felhasználó Tailscale-fiókját;
- a felhasználó Cloudflare-fiókját;
- az alkalmazott AI API-fiókok biztonságát;
- a felhasználó hálózati környezetét;
- az exportált fájlok későbbi kezelését.

---

# 32. Adatvédelmi incidens

Mivel a helyi SleepMate-adatok nem kerülnek automatikusan a Fejlesztő rendszerébe, a felhasználó saját számítógépét vagy saját felhőfiókját érintő incidensről a Fejlesztő nem feltétlenül szerez tudomást.

Amennyiben egy incidens valamely külső szolgáltatást érint, az arra vonatkozó értesítési és incidenskezelési kötelezettségeket az adott szolgáltató szabályai szerint kell értékelni.

---

# 33. Weboldal és webáruház

Jelen tájékoztató elsősorban a **SleepMate alkalmazás** adatkezelésére vonatkozik.

A SleepMate weboldala, webáruháza, kapcsolatfelvételi űrlapja, vásárlási folyamata, számlázása, fizetési szolgáltatója vagy egyéb online szolgáltatása ettől eltérő személyes adatokat kezelhet.

Az ilyen webes adatkezelésekre külön weboldali/webáruházi adatkezelési tájékoztató vonatkozhat.

---

# 34. A tájékoztató módosítása

A SleepMate funkcióinak fejlődésével a jelen adatvédelmi tájékoztató is módosulhat.

Különösen indokolhatja a módosítást:

- új külső szolgáltató bevezetése;
- új AI-szolgáltató bevezetése;
- felhőszolgáltatás változása;
- új adattípus kezelése;
- adatbiztonsági mechanizmus változása;
- jogszabályi változás.

Az aktuális változat hatálybalépési dátuma a dokumentum elején található.

---

# 35. Rövid összefoglaló

A SleepMate adatvédelmi működése röviden:

**Helyi CPAP/PAP adatok:** a felhasználó saját számítógépén maradnak.

**Központi SleepMate adatbázis:** nincs.

**SleepMate-fiók és központi adatszinkron:** nincs.

**Automatikus egészségügyi adatküldés a Fejlesztőnek:** nincs.

**ez Share / SleepSync:** opcionális, helyi adatkapcsolat.

**Google Drive:** opcionális; a felhasználó saját Google-fiókjába készített biztonsági mentés.

**AI:** opcionális; a felhasználó saját API-kulcsával, közvetlenül a kiválasztott AI-szolgáltató felé.

**AI-nak küldött közvetlen személyazonosító adat:** a SleepMate adatvédelmi szűrője eltávolítja.

**AI-nak küldött terápiás adat:** igen, ha a felhasználó az AI-funkciót kifejezetten használja.

**Tailscale:** opcionális távoli hozzáférés.

**Cloudflare:** opcionális távoli hozzáférés.

**Orvosi diagnózis:** a SleepMate nem orvosi diagnosztikai szoftver és nem helyettesít egészségügyi szakembert.

**A legfontosabb alapelv:**
**a SleepMate normál, helyi használatakor a felhasználó egészségügyi adatai nem kerülnek a SleepMate Fejlesztőjéhez.**