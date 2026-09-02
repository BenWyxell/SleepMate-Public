# SleepMate 5.3.4

A 5.3.4 a Dashboard, Oximetria, O2Ring és PWA frontend teljes stabilitási és interakciós refaktorja. A kiadás nem új, párhuzamos Oximetria-rendszert épít: a meglévő O2Ring adatforrást, BLE-kezelést, CPAP adatkészletet és SleepSync folyamatot használja, miközben a hibás frontend/state/chart/adatkapcsolási réteget egységesíti.

## Kritikus stabilitás

- Egyetlen aktív O2 frontend owner: a korábbi v5.3.2/v5.3.3 overlay kontrollerek nem kerülnek az aktív shellbe.
- A Dashboard napi részletes nézetében a `Fókusz nézet | Összes grafikon | Oximetria` három állandó mód marad; egyik sem változik vissza gombbá.
- Nézetváltáskor a CPAP- és O2 pointer/drag/pinch állapot kontrolláltan lezárul, a grafikonok újraméreteződnek.
- Az Oximetria oldalsó navigáció egyetlen capture-owned route-tal működik, nincs dupla handler/anchor ugrás.
- A PWA aktív HTML/JS/CSS/service-worker generációja 5.3.4; régi v5.3.2/v5.3.3 O2 bundle nem aktív.

## O2 grafikonok

- SpO₂, pulzus és kombinált SpO₂ + pulzus grafikon a napi Oximetria, Fókusz és Összes grafikon nézetben.
- Élő, lezárt session, napi, fókusz-, összes-grafikon-, trend- és Dashboard O2 grafikonokon közös interakciós motor.
- Egér/touch crosshair, másodperc pontos idő és a legközelebbi timestamp valós SpO₂/pulzus értéke.
- Szinkronizált SpO₂/pulzus chartokon közös crosshair és közös zoomablak.
- Desktop drag-zoom, Shift+drag pan, kerék zoom, dupla katt reset; mobilon drag pan és kétujjas pinch zoom, vertikális oldal-scroll megőrzésével.
- A nagy adathiányokat a grafikon nem köti össze hamis vonallal.

## Élő O₂ monitor és teljesítmény

- Az O2Ring backend adatgyűjtése és rövid live buffer futhat tovább, de az élő frontend chart stream csak látható Oximetria / Élő O₂ monitor nézetben aktív.
- Más oldalon az SSE live stream lezárul, nincs folyamatos chart redraw.
- Visszatéréskor a kimaradt adatok a `/api/o2ring/live-buffer` végpontról egy batch-ben töltődnek vissza, majd innen folytatódik az élő stream; nincs backlog-lejátszás.
- A chart redraw requestAnimationFrame-batch-elt, a hidden canvasok nem rajzolódnak újra.

## CPAP ↔ O2Ring automatikus illesztés

- Időbélyeg-alapú session matching, nem fájlnév vagy tömbindex szerint.
- A legnagyobb időbeli átfedés determinisztikusan elsőbbséget élvez.
- Nem átfedő O2 töredékek ugyanahhoz az éjszakához együtt is felhasználhatók.
- Azonos timestampből nem keletkezik duplikált adatpont.
- Új O2Ring felvétel automatikus célzott invalidation eventet generál.
- Sikeres SleepSync után event-driven `sleepsync-completed` invalidation történik; az import `changed_days` adatai alapján a módosult meglévő éjszakák is automatikusan újraillesztődnek.
- A Dashboard, napi részletes nézet, Fókusz/Oximetria, Éjszaka értékelése, riport és overlay cache-ek kontrolláltan frissülnek kézi Refresh nélkül.

## CPAP grafikon O2 réteg

- Grafikononként külön kompakt `+ O₂` választó: Nincs / SpO₂ / Pulzus / SpO₂ + Pulzus.
- A választás grafikononként helyben megjegyezhető.
- Timestamp-alapú illesztés és gap-aware vonaltörés.
- A CPAP elsődleges Y tengelyét nem módosítja; az O₂/HR külön, kompakt jobb oldali skálajelölést használ.
- Hover esetén a CPAP kurzor idejéhez tartozó pontos O₂/HR érték jelenik meg.

## Dashboard és jelentések

- Visszaállított Dashboard fő Oximetriai összegzés SpO₂/pulzus mini trendekkel.
- Éjszaka értékelése O2Ring kártya: átlag/minimum SpO₂, átlag pulzus, T90, ODI3/ODI4.
- Jelentéstábla: SpO₂ átlag, minimum, pulzus átlag, T90 és ODI3/ODI4.
- Az alsó oszlopdiagramokból kikerült a blur/glow; egységes Aurora-palettát használ a bar, legend és tooltip is.
- Az Alvások kártya nem villant fel ideiglenes `Befejezve` értéket; betöltés közben `—` jelenik meg.

## Beállítások és PWA

- A felhasználói `PWA` és `PWA értesítések` egyetlen PWA kategória; a PWA alsó navigáció szerkesztője ezen belül jelenik meg.
- A korábbi `Megjelenés` O2 beállítási kategória felhasználói neve `O2Ring`.
- Az O2Ring master/BLE/automatikus csatlakozás/szinkron kapcsolói sorosított mentéssel első változtatásra mentődnek és visszatöltődnek.
- Az automatikus CPAP-illesztés kapcsoló azonnal ment.
- A részletes O2Ring beállítások explicit reszponzív gridet használnak; mobilon egy oszloposak.
- A Beállításvarázsló egyetlen példányban, a Rendszer beállítási panelen jelenik meg.
- A PWA alsó navigációban az O2Ring engedélyezésekor választható az `Élő O₂ monitor`.

## Release gate

A 5.3.4 csak akkor publikálható, ha a külön v5.3.4 elfogadási contractok, a teljes publikus pytest-készlet, a Windows program-tree build, a magyar WiX MSI build, az MSI payload-ellenőrzés, a valódi `msiexec` telepítés/backend API smoke, az uninstall és a VERIFIED release-set hash/manifest ellenőrzése ugyanazon exact commiton sikeres.

A Windows kiadás továbbra is Authenticode-aláírás nélkül készül. A fizikai O2Ring BLE rádiós/firmware validációt automatizált CI nem helyettesíti.
