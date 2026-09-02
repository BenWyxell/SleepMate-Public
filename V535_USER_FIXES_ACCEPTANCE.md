# SleepMate v5.3.5 – 15 pontos felhasználói javítási acceptance

A v5.3.5 javítási kör kizárólag akkor tekinthető késznek, ha ugyanazon exact commiton a source contractok, a Windows portable build, a magyar MSI, a valódi install/API/uninstall smoke, a VERIFIED release-set és a valódi Microsoft Edge acceptance is sikeres.

1. Dashboard → Részletes napi nézet: a SpO₂ és Pulzus kártya a CPAP-idővel átfedő O2Ring adatok mediánját mutatja. Magyar formátum: például `96,4%` és `64,0`.
2. Fókusznézet: pontosan két normál mini O₂ kártya van (SpO₂, Pulzus); nincs külön nagy SpO₂+Pulzus blokk.
3. Oximetriás grafikonokon a húzás közbeni kijelölés látható, a normál chart-viselkedéssel megegyezően.
4. A Fókusznézet SpO₂/Pulzus mini kártyái a normál közös hero nagy grafikonra nyílnak.
5. Az oximetriás vonalak vastagsága megegyezik a normál grafikonokéval.
6. Összes grafikon nézetben az O₂ overlay jobb oldali SpO₂/HR tengelyskálát mutat, a hover felirat pedig pontos időponttal a felhasználói megnevezéseket és aktuális értékeket írja ki: `SpO₂ …%` és `Pulzus … bpm`.
7. Az overlay kikapcsolt állapotának neve `Alapnézet`.
8. Dashboard → Legutóbbi alvás: a kártya teljes alvás-/terápiás időt mutat, nem státuszszöveget; a szakaszszám másodlagos információ.
9. Dashboard → Oximetriai összegzés stabilan megjelenik és tényleges adatot rajzol, PWA-n is.
10. Jelentések → A kiválasztott időszak napjai: kompakt, arányos fejléc és sormagasság.
11. Jelentések → Napi statisztika: SpO₂ és Pulzus minimum, medián és maximum értékek; SleepSync/invalidation után mindig az aktuálisan frissített, CPAP-idővel illesztett O2Ring summary értékeit kell mutatnia, nem korábbi cache/fixture értéket.
12. Oximetria: Dashboard, Kapcsolódás, Szinkron, Élő O₂ monitor, Felvételek, Trendek egyetlen felső gombsorban, ebben a sorrendben.
13. Oximetria: nincs külön nagy Állapot kártya; az állapot kompaktan a keresés/kapcsolat rész alatt jelenik meg.
14. Éjszaka értékelése Oximetria kártya: csak SpO₂ és Pulzus medián; nincs Minimum, T90, ODI3 vagy ODI4.
15. PC-n az Éjszaka értékelése Oximetria kártya a normál grid-kártyákkal azonos méretű, nem teljes szélességű.

A korábbi v5.3.4 stabilitási követelmények továbbra is kötelezőek: first-load/stale-cache PWA stabilitás, Live O₂ láthatósági lifecycle és bounded refill, SleepSync invalidáció, gap-helyes vonalrajzolás, crosshair/zoom/pinch/touch-pan, listener-stabilitás és exact-SHA artifact identity.
