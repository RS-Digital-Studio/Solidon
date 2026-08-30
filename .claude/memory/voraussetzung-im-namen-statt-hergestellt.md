---
name: voraussetzung-im-namen-statt-hergestellt
description: "Ein Test, der seine Voraussetzung im Namen behauptet statt sie herzustellen, ist gegen genau den Fehler blind, den er zu decken vorgibt"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5f85192a-8b20-4339-ba08-13913837d58c
  modified: 2026-08-30T23:17:00.179Z
---

`test_a_recipe_the_application_wrote_is_accepted` — „ein Rezept, das die
Anwendung geschrieben hat, wird angenommen". Das Rezept war von Hand gebaut
und sah nur so aus.

Am 31.08.2026 stellte sich heraus: Es trug `group: "Befestigung"` — den
**Anzeigenamen** dort, wo der **Schlüssel** `mounting` hingehört — und ein
leeres `features`. Damit war es eine Datei, die jede Formatprüfung besteht und
beim ersten Empfänger scheitert. Zwölf Grenzfälle prüften „kommt durch"
dagegen.

Es waren **fünf Korpusse in drei Dateien**, aus drei Sitzungen, alle formal
sauber, alle jahrelang grün.

**Why:** Der Name hält jeden Leser davon ab, die Voraussetzung zu prüfen — er
liest „das kommt aus der Anwendung" und glaubt es. Ein Test, der etwas
Falsches misst, fällt irgendwann auf; einer, der seine eigene Prämisse
erfindet, nie.

Gefunden hat es niemand durch Suchen, sondern eine Sitzung, die den Weg einmal
von einem Ende zum anderen fuhr (`for_upload` → Datei → `adopt`). Drei saubere
Dateien, die der Empfänger ablehnte — das sieht keine Suite.

**How to apply:** Behauptet ein Testname eine Herkunft („was die Anwendung
schreibt", „wie der Kunde es speichert"), dann **stelle sie her** — über
denselben Weg, den die Anwendung geht — oder benenne den Test nach dem, was er
wirklich tut. Und bei jedem Referenzdatensatz einmal fragen: Ist er
*brauchbar* oder nur *formal richtig*? Verwandt:
[[testprojekt-trifft-den-fall-nicht]] (dieselbe Wurzel, ohne die Zuspitzung
auf den Namen) und [[pruefstand-geht-den-weg-der-oberflaeche]].

Die Sammelform aus derselben Nacht, über drei Gebiete: **Anwesenheit, Form,
Wortlaut — drei Arten, an der Sache vorbeizuprüfen.** Ein Vergleich, der die
Anwesenheit eines Satzes prüft statt seines Inhalts; ein Erzeuger, der „ist
der Satz leer" fragt statt „steht er im Katalog"; ein Korpus, der die Form
einer Datei prüft und nie ihre Brauchbarkeit.
