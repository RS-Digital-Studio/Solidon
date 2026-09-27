---
description: "Doppelte Stellen und Zwillinge — vier Klassen mit je einer Pflicht, vor einer Änderung alle Stellen finden, und warum ein Skript die gefährlichen nicht sieht"
paths:
  - "app/**/*.py"
---

# Zwillinge: dieselbe Auskunft an zwei Stellen

Das, was die projektübergreifende Arbeitsanweisung „parallele Code-Pfade"
nennt; hier heißt es **Zwilling** wie im Werkzeug (`tools/twin_scan.py`), im
Konzept (`konzepte/konzept-zwillinge-2026-09.md`) und in der ROADMAP. Das
Warum steht in `konzepte/begruendungen/regel-zwillinge.md`.

**Ein Zwilling ist eine Auskunft, die an mehr als einer Stelle hergeleitet
wird** — eine Zahl, eine Regel, ein Satz, eine Rechnung —, so dass ein
Nachbessern an der einen Stelle die andere nicht erreicht. Nicht jede
Wiederholung von Code ist gemeint.

## Die Regel

**Vor einer Änderung an einer Logik werden alle Stellen gesucht, die dieselbe
Auskunft herleiten; gefunden wird geprüft, geändert, was geändert werden
muss.** Nicht „alle anpassen": Zwei Stellen dürfen auseinandergehen, wenn
jemand entschieden hat, dass sie verschiedene Fragen beantworten.
Unentschieden dürfen sie nicht bleiben.

## Vier Klassen, und jede hat eine Pflicht

| Klasse | Was es ist | Was zu tun ist |
|---|---|---|
| **gewollt** | Dieselbe Handlung in zwei Rechenkernen oder zwei bewusst getrennten Fassungen | Ein **Kriterium**, wann er entsteht — *dort, wo der Zweig ohne ihn endet, nicht dort, wo er möglich wäre* (`konzepte/entscheidungen-2026-08-22.md`) —, und ein **Test**, der beide auf dieselbe Frage gleich antworten lässt |
| **gehalten** | Eine Kopie, die aus einem am Code belegten Grund nicht zusammengelegt werden kann | Eintrag in einer kuratierten Liste mit dem Grund, dazu ein Wächter über die Wortgleichheit; ein Docstring, der einen Test behauptet, ist kein Wächter |
| **ungewollt** | Dieselbe Auskunft zweimal hergeleitet, ohne Kriterium und ohne Grund | **Zusammenlegen**; geht es in diesem Schritt nicht, wird es ein Punkt im Register von `ROADMAP.md`, kein Kommentar in beiden Dateien |
| **Namenszwilling** | Ein Name, zwei Sachen | **Umbenennen**, wenn beide öffentlich sind; modulprivat und verschieden ist erlaubt |

Keine Zwillinge, aber mitgefunden: **Musterwiederholung** (drei Zeilen, die
drei Dialoge gleich tun) — nur auflösen, wenn ohnehin eine Abstraktion
entsteht; und der **fachliche Zwilling** (dieselbe Rechnung in zwei Formen mit
verschiedenen Rückgaben) — maschinell unsichtbar, beim Anfassen der Stelle
zusammenlegen.

## Vor der Änderung: messen, dann lesen

```
.venv\Scripts\python.exe tools/twin_scan.py app
.venv\Scripts\python.exe tools/twin_scan.py tests --frage 2 --frage 3
```

Das Werkzeug ist **kein Test** und steht nicht im Tor. **Die gefährlichen
Zwillinge sind die, die schon auseinandergelaufen sind** — für jede Suche nach
Gleichheit unsichtbar, ebenso eine Regel in zwei Fassungen, die weder wort-
noch strukturgleich ist. Ein Skript findet Kopien; eine Regel in zwei Fassungen
findet nur, wer die Sache kennt. Das Werkzeug ist der Zubringer der
Durchsicht, nicht ihr Ersatz.

## Woher sie kommen

1. **Eine vermutete Schichtgrenze** — wer eine Grenze vermutet, statt sie
   nachzulesen, kopiert.
2. **Zwei Sitzungen, ein Problem** — die Nachbarstelle ist noch nicht
   committet.
3. **Ein Kommentar „dieselbe wie …" ist kein Teilen** — er wandert beim
   nächsten Anfassen nicht mit.
4. **Der Name statt der Eigenschaft** — wo hinter `== "orca"` eine Frage
   steht, gehört ein Prädikat hin (`slicer_keys.py` führt sie).
5. **Ein Geschwistermodul entsteht durch Kopieren** und nimmt die
   Hilfsfunktion mit, statt sie herauszuziehen.
6. **Jede Testdatei bringt ihre Fixture mit**, weil sie allein lauffähig sein
   soll.

## Was das Tor hält

`tests/test_shared_constants.py` prüft die Konstanten der Anwendung in zwei
Richtungen: derselbe Name mit demselben Wert an mehr als einer Stelle, und ein
öffentlicher Name für zwei verschiedene Werte; beide Tests haben eine
Untergrenze gegen einen kaputten Suchlauf. **Über Funktionskörper wacht
nichts** — eine Entscheidung (§3 des Konzepts), keine Lücke. Wer einen
Zwilling hält, hängt einen Test daran oder legt ihn zusammen; einen Kommentar,
der einen Wächter behauptet, prüft niemand.

## Wo was steht

| Frage | Ort |
|---|---|
| Welche Klasse hat ein Fund, und woran ist das belegt? | `konzepte/konzept-zwillinge-2026-09.md` — seine Tabellen sprechen über ihren Stichtag |
| Welche Zusammenlegung ist beauftragt? | Das Register in `ROADMAP.md` — und nirgends sonst |
| Was war schon einmal da? | `ROADMAP-ARCHIV.md`, Abschnitt „Doppelte Stellen und Zwillinge" |

## Zwillinge, die noch stehen

Am Code nachgesehen; wer eine dieser Dateien anfasst, legt die Stelle
zusammen, statt sie zu umgehen:

| Stelle | Anmerkung |
|---|---|
| `knowledge/calibration._literal` ↔ `knowledge/parts/scad._literal` | Wortgleich, klein |
| `viewport.ambient_occlusion` ↔ `contact_shadows` | **Nur die Bedingung** ist der Zwilling; die zwei Eigenschaften bleiben zwei — sie beantworten verschiedene Fragen, die heute dieselbe Antwort haben |
| `tools/make_licence_keys._new_keypair` ↔ `tools/sign_version.new_keypair` | Sicherheitsnah, außerhalb dieses Geltungsbereichs |
