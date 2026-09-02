# SleepMate 5.3.3

## Frontend és PWA helyreállítás

A 5.3.3 a 5.3.2 után észlelt frontend/PWA regressziókat javítja úgy, hogy a terápiás adat- és SleepSync-réteg változatlan marad.

- A PWA shell, a Windows csomagolt service worker és a backend által kiszolgált UI ugyanazt a 5.3.3 frontend-generációt használja.
- Verzióváltáskor a régi shell/API cache-ek eltávolításra kerülnek, és a nyitott PWA kliens az új felületre navigál.
- A Beállításokban a PWA értesítések és az alsó navigáció egyetlen PWA részben jelenik meg.
- A Beállításvarázsló csak egyszer jelenhet meg, a Rendszer és frissítés részhez kötve.
- Az O2Ring beállításai egyetlen O2Ring részben jelennek meg.
- A Dashboard három napi nézete — Fókusz, Összes grafikon és Oximetria — egymást kizáró, determinisztikus állapotkezelést kap.
- A fő Dashboard O2Ring összegzése, a Fókusz O2 grafikonok, az Összes grafikon O2 grafikonjai, az Oximetria kombinált grafikonjai és az O2-adatokkal bővített jelentés regressziós kaput kapott.
- A Sleep/PWA 5.2.x kompatibilitási markerek megmaradnak, de az aktív shell és API cache a 5.3.3 recovery generáció.

## Kiadási ellenőrzés

A kiadás csak akkor tekinthető késznek, ha a v5.3.3 frontend recovery contract, a teljes publikus tesztkészlet, a Windows PyInstaller build, a magyar MSI build, a valódi MSI telepítés/backend smoke test és az eltávolítási teszt is sikeres.

A Windows binárisok Authenticode aláírása továbbra sincs beállítva. Valódi fizikai O2Ring BLE hardveres validációt a CI nem tud végezni.
