# Test fixtures

A `DATALOG` könyvtár nyers PAP/EDF mérési fájljai szándékosan nincsenek verziókezelésben.

A repository és a GitHub Actions build nem tartalmaz személyes terápiás adatot. A lokális, EDF-alapú golden/regressziós tesztek csak akkor futnak, ha a fejlesztői környezetben külön rendelkezésre áll a `testdata/DATALOG` fixture.

Az `Identification.json` kizárólag szintetikus tesztazonosítókat tartalmaz.
