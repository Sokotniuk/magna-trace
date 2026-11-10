# MAGNA TRACE — návrh približne trojminútového vystúpenia

**D7.1: pripravený scenár; meranie času a nahrávka PENDING.** Časy sú plán,
nie výsledok skúšky. Počítajú aj s kliknutím a krátkou pauzou na obrazovke.
Hovorí Student D, druhý člen tímu môže obsluhovať pripravený terminál.

Táto verzia opisuje aktuálny lokálny dashboard s dátami **SYNTHETIC**.
Nenahrádza povinnú živú cestu cez Copilot a Oracle podľa
[product.md §§6/9–10](../docs/product.md). Pred prezentáciou otvor prípravu
v [záložnom pláne](demo_backup_plan.md). Syntetickú odpoveď odošli až po otvorení
prípadu; nevydávaj tento krok za automatické volanie Copilotu.

## 0:00–0:25 — Problém

**Akcia:** Zobraz názov MAGNA TRACE a nechaj viditeľné označenie SYNTHETIC ONLY.

„Keď sa vo výrobe objaví neobvyklý výsledok testu, technik potrebuje zistiť,
čo bolo namerané, odkiaľ údaj pochádza a čo ešte treba overiť. Samotná tabuľka
nevysvetlí príčinu. Ani presvedčivá odpoveď asistenta nestačí, ak si jej údaje
nevieme skontrolovať. Na tento problém reagujeme v hackathonovej úlohe číslo deväť.“

## 0:25–0:50 — Riešenie MAGNA TRACE

**Akcia:** Ukáž nadpis Diagnostic Dashboard a upozorni na stav integrácie.

„MAGNA TRACE má spojiť vyšetrovanie problému s dohľadateľnými dôkazmi.
Oddeľujeme pozorovania, výpočty, hlásenia technika a neoverené hypotézy.
Cieľovým rozhraním je Microsoft Copilot Studio. Dnes ukazujeme lokálny React
dashboard so syntetickým mock API. Živé prepojenie na Oracle, backend a Copilot
v tomto repozitári zatiaľ nie je overené.“

## 0:50–1:10 — Ako to funguje

**Akcia:** Stručne ukáž dve cesty v README, potom sa vráť do dashboardu.

„V cieľovej architektúre vedie Copilot rozhovor. Python backend má čítať Oracle
iba cez SELECT a počítať pomocou Decimal. Dashboard výsledky iba zobrazuje.
Aktuálna ukážka cez lokálny proxy server prehráva pevné príklady z pripnutého
kandidáta zmluvy B2. Výpočty tu neprebiehajú.“

## 1:10–1:50 — Živá lokálna ukážka dashboardu

**Akcia:** Vyber SYNTHETIC-STATION a klikni Open diagnostic case. Ukáž tri riadky
a samostatné stĺpce Range status, Quality flags a Raw fail code.

„Otvorím syntetický prípad. Vidíme hodnotu, jednotku, zaznamenané hranice
a vrátenú odchýlku. Prvý riadok je nad hornou hranicou. Druhý je v zaznamenaných
hraniciach, hoci má kód tisícjeden. Význam kódu nepoznáme, preto z neho
nerobíme verdikt PASS ani FAIL. Ani null neznamená úspešný test.
Tretí riadok sa nedá vyhodnotiť: obsahuje nečíselnú hodnotu a chýba jednotka.
Upozornenia zostávajú viditeľné.“

## 1:50–2:25 — Dôkazy a odovzdanie prípadu

**Akcia:** Otvor Observed a Calculated odkaz prvého riadka. Druhý člen tímu
odošle pripravenú fixture odpoveď podľa záložného plánu. Klikni Load handover,
ukáž Technician reports a Assessment. Prípad už znovu neotváraj.

„Odkaz otvorí zachytené zdrojové polia. Ďalší ukáže pravidlo výpočtu
a odkazy na vstupy. Aj tieto dôkazy sú syntetické.
Teraz odošleme vopred pripravenú syntetickú odpoveď cez API; dashboard nemá
formulár odpovede. Súhrn oddeľuje pozorovania od hlásenia technika, uvádza
neznáme skutočnosti, obmedzenia a ďalšie overenie. Posúdenie zostáva
UNDETERMINED. Príčinu nemáme potvrdenú.“

## 2:25–2:50 — Prínos a obmedzenia

**Akcia:** Ukáž Unknowns, Gaps and warnings a Next action. Hodnoty neprepočítavaj.

„Prínosom návrhu je kontrolovateľná cesta od údaja k ďalšej otázke
a prehľadné odovzdanie kolegovi. Úsporu času ani presnosť diagnózy sme
nemerali. Výpadok sa má zobraziť ako chyba, bez náhradných meraní.
Povinným ďalším dôkazom MVP zostávajú dva celé priechody v reálnom Copilote
s Oracle a overenými zdrojmi.“

## 2:50–3:00 — Záver

**Akcia:** Zostaň na súhrne s viditeľným SYNTHETIC a UNDETERMINED.

„MAGNA TRACE: od neobvyklého výsledku k overiteľnému ďalšiemu kroku.
Ukazujeme dôkazy aj hranice toho, čo vieme. Ďakujeme.“
