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

## Und die vierte Art: die Voraussetzung, die nur auf dieser Maschine gilt

Am 03.09.2026 nahm ein neuer Test das erstbeste Paket aus `website/dl/`
(`min(...glob("*.exe"))`). Hier liegen acht, weil hier gebaut wird — im
Repository liegt keines (`.gitignore`), und auf dem Runner existiert der
Ordner nicht einmal. Der Test war lokal grün und in der CI **auf allen drei
Plattformen** rot (`ValueError: min() iterable argument is empty`), und er
blockierte einen Release-Lauf. Der Fix ist derselbe Satz wie oben: Wer eine
Voraussetzung braucht, **stellt sie her** — zwei Zeilen, die die Datei
anlegen, und ein `finally`, das sie wegräumt. Ein `skip` wäre der falsche
Ausweg gewesen: Dann prüfte ausgerechnet dort nichts, wo der Zähler des
Kunden läuft.

**Und die Technik, die so etwas in dreißig Sekunden findet**, statt es dem
Tag-Lauf zu überlassen: den Test in einem frischen Arbeitsbaum fahren.

```
git worktree add -q --detach <pfad> HEAD
cd <pfad> && <venv>/python.exe -m pytest tests/<datei>.py -q
git worktree remove --force <pfad>
```

Dort fehlt alles, was nicht im Repository steht — `dist/`, `website/dl/`,
`packaging/build/` —, also genau das, was eine lokale Voraussetzung
ausmacht. Über vier Testdateien gefahren: 178 grün, 13 übersprungen, alle
Skips plattformbedingt und in der Linux-CI aktiv. Der Baum wird nur gelesen;
committet wird dort nie ([[probe-die-commits-erzeugt-schaltet-push-ab]]).
