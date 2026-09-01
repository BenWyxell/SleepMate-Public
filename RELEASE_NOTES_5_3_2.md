# SleepMate 5.3.2

A 5.3.2 a 5.3.1 stabil O2Ring kiadás célzott stabilitási és kezelhetőségi javítása. A fő cél a Dashboard napi nézet, az Oximetria, a PWA és az O2Ring-beállítások egységes, gyors és kiszámítható működése.

## Dashboard napi grafikonok

- A **Fókusz nézet / Összes grafikon / Oximetria** három azonos szintű nézetként működik; az Oximetria többé nem változik visszalépés gombbá.
- Megszűnik az Oximetria nézetre váltáskor tapasztalt befagyás és a Fókusz/Összes grafikon közötti nagyítás-beragadás.
- A Fókusz nézet külön SpO₂-, pulzus- és kombinált SpO₂+pulzus grafikont kap.
- Az Összes grafikon nézet ugyanezekkel az oximetriai grafikonokkal egészül ki.
- Az oximetriai grafikonok húzással nagyíthatók, dupla kattintással vagy a teljes-idő gombbal visszaállíthatók.
- A Fókusz és az Összes grafikon külön nagyítási állapotot őriz.

## O2 overlay a CPAP grafikonokon

- A Nyomás, Szivárgás, Áramláskorlátozás és Horkolás grafikonon kompakt O₂ overlay-választó jelenik meg.
- Választható: **Ki / SpO₂ / Pulzus / Mindkettő**.
- A SpO₂ és a pulzus saját értéktartományt használ; a megjelenítés nem kényszeríti őket félrevezető közös Y-skálára.
- A Légáramlás és a sűrűbb légzési csatornák nem kapnak alapértelmezett rárajzolást; mellettük a szinkronizált külön O2 grafikonok maradnak olvashatók.

## Oximetria oldal

- Az eszköz- és mérési állapot jóval kompaktabb fejlécet és élő statisztikai chipeket kap.
- Csatlakoztatott O2Ring mellett a **Kapcsolódás** gomb automatikusan eltűnik.
- Az élő SpO₂+pulzus grafikon valódi közös időtengelyt és két jól elkülönülő Y-skálát használ.
- Élő és részletes oximetriai grafikonokon is elérhető a nagyítás.
- A bal oldali Oximetria menüpont stabilan az Oximetria oldalra navigál, nem ugrál az alnézetek között.

## O2Ring beállítások

- A korábbi **Megjelenítés** beállítási lap neve **O2Ring**.
- A lap elrendezése új, reszponzív, kompakt struktúrát kap.
- A főkapcsoló és a BLE/automatikus kapcsolódás/szinkron kapcsolók sorosított mentést használnak, így gyors kattintásoknál sem indul egymással versengő mentés.
- Az eszközkeresés, kapcsolatállapot és kézi szinkron ugyanitt, kompakt kapcsolati sávban is elérhető.

## Dashboard összegzés és Éjszaka értékelése

- A Dashboard oximetriai összegzése átlag SpO₂, minimum SpO₂, átlagpulzus és T90 kártyákat, valamint mini trendeket mutat.
- Az összesítés kizárólag a tényleges CPAP-idővel átfedő O2Ring-adatokat használja.
- Az **Éjszaka értékelése** blokk külön Oximetriai összegző kártyát kap SpO₂-, pulzus-, T90-, ODI3/ODI4- és lefedettségi adatokkal.
- A Szekció/Alvás kártyán nem villan fel átmenetileg a „Befejezve” placeholder.

## Dashboard oszlopdiagramok

- A Használati idő és Események bontása oszlopokról lekerül a homályos glow/bloom effekt.
- Éles, jól elkülöníthető Aurora-kompatibilis színrendszer kerül rájuk.
- A tooltip jelölőszínei ugyanazt az új palettát használják, mint az oszlopok.

## Jelentések

A napi jelentéstáblázat új oximetriai oszlopokat kap:

- SpO₂ átlag
- SpO₂ minimum
- Pulzus átlag
- T90
- ODI3 / ODI4

A Dashboard és a Jelentések O2-összesítői új batch végpontot használnak, így nem indítanak külön teljes O2-kérést minden egyes napra.

## PWA és mobil stabilitás

- A korábbi periodikusan újratelepülő O2 UI-polish rétegek kikerülnek az aktív shellből.
- Egyetlen idempotens, eseményvezérelt v5.3.2 O2 runtime kezeli az Oximetria/Dashboard/PWA felületet.
- A service worker új cache-generációt kap, az O2Ring és v5.3 shell JavaScript/CSS fájlok network-first kódassetekké válnak.
- A PWA és PWA-megjelenés továbbra is egyetlen **PWA** beállítási részben marad.
- Az alsó PWA navigáció új választható gyorspontja: **Élő Oxi**, amely közvetlenül az élő oximetriai nézetet nyitja meg.
- A mobil Oximetria elrendezés kisebb kártyákat, egységesebb két-tengelyes grafikont és kevesebb újrarenderelést használ.

Kiadási csatorna: **stable**.  
Release build: **5.3.2**.  
API: **19**.
