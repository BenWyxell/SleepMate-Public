# SleepMate 5.3.1

A SleepMate 5.3.1 a 5.3.0 célzott stabilizáló és felületi patch kiadása. Nem változtatja meg az API-sémát; az O2Ring/Aurora alapfunkciók változatlanul a 5.3.0-ra épülnek, a kiadás a napi használatban látható oximetriai, jelentés- és PWA-részleteket csiszolja készre.

## Oximetria – napi nézet és navigáció

- Javítva az a helyzet, amikor az Oximetria napi fókusznézetből a Fókusz nézet / Összes grafikon váltás után a fő grafikonpanel rejtve maradhatott.
- Az Oximetria napi nézet külön „Vissza a grafikonokhoz” műveletet kapott.
- Az Összes grafikon nézet külön SpO₂-, pulzus- és kombinált SpO₂ + pulzus blokkot kap.
- A napi oximetriai összegzés továbbra is kizárólag a tényleges CPAP-idővel átfedő adatokat használja.

## Oximetriai trendek és élő monitor

- Új trendmegjelenítés dátumtengellyel, rácsozással, pontokkal, jelmagyarázattal és hover értékekkel.
- Külön trend készült SpO₂ átlag/minimum, pulzus, T90 és ODI3/ODI4 értékekhez.
- Az élő SpO₂ és pulzus közös, két skálás Aurora diagramon is követhető.
- Kevés vagy hiányzó adatnál a trendpanelek értelmes üres állapotot mutatnak.

## Dashboard és éjszakai összegzés

- A Dashboard oximetriai összegző blokkot kapott átlag SpO₂, minimum SpO₂, átlagpulzus, T90 és mini trendek megjelenítésével.
- Az „Éjszaka értékelése” oximetriai összefoglalóval egészül ki, ha az adott CPAP-időszakhoz van illesztett O2Ring adat.
- A Dashboard oximetriai mutatói nem nyers, teljes gyűrűfelvétel-átlagokat, hanem CPAP-időre illesztett adatokat használnak.

## Jelentések

- A Jelentések időszaki táblázata oximetriai oszlopokkal egészül ki: SpO₂ átlag, SpO₂ minimum, átlagpulzus, T90 és ODI3/ODI4.
- Az O2-oszlopok csak aktív O2Ring integrációnál jelennek meg, így kikapcsolt állapotban nem maradnak üres helyek.
- A PDF Oximetria és pulzus opciója változatlanul külön kapcsolható.

## PWA és O2Ring beállítások

- A PWA és PWA megjelenés beállítások egy közös PWA területre kerültek.
- Az O2Ring eszközállapot, keresés, kapcsolódás és szinkron a Megjelenés beállításokból is elérhető.
- Csatlakoztatott O2Ring esetén a felesleges „Kapcsolódás” gomb eltűnik.
- Az Oximetria felső kapcsolat/szinkron területe kompaktabb, kevesebb vertikális helyet foglal.

## Aurora vizuális finomítás

- A Használati idő oszlopdiagram Aurora cyan/teal–violet átmenetet kapott.
- Az eseménytípusok grafikus színei az Aurora rendszerhez igazodnak.
- Az új O2Ring elemek ugyanazt a mély éjszakai, cyan/teal/violet vizuális nyelvet követik, mint a 5.3.0 felület.

## Kompatibilitás és validáció

- Alap: publikus SleepMate 5.3.0, amely maga a 5.2.20 stabil alap leszármazottja.
- API verzió: 19, változatlan.
- A patch nem módosítja a SleepSync működési szerződését, CPAP importot, lokális adattár formátumát vagy az O2Ring történeti adatok megőrzési szabályait.
- Kiadás előtt kötelező a teljes publikus tesztkészlet, PyInstaller Windows build, magyar WiX MSI build, MSI payload ellenőrzés, valódi install/backend/API/uninstall smoke-test és a teljes VERIFIED artifact SHA-256 ellenőrzése.

## Hardvervalidáció

A Windows BLE csomagolás, protokoll- és UI-integráció automatizáltan ellenőrizhető, de fizikai O2Ring nélkül a különböző firmware-verziók tényleges rádiós viselkedése nem automatizálható. A release ezért nem állít fizikai hardvertesztről olyat, ami nem történt meg.

Kiadási csatorna: **stable**.  
Release build: **5.3.1**.  
API: **19**.
