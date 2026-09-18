---
description: "Doppelte Stellen und Zwillinge — vier Klassen mit je einer Pflicht, wie man vor einer Änderung alle Stellen findet, und warum ein Skript die gefährlichen nicht sieht"
paths:
  - "app/**/*.py"
---

# Zwillinge: dieselbe Auskunft an zwei Stellen

Dies ist die Datei, die die projektübergreifende Arbeitsanweisung als
„parallele Code-Pfade" führt. Hier heißt die Sache **Zwilling**, weil das
Werkzeug (`tools/twin_scan.py`), das Konzept
(`konzepte/konzept-zwillinge-2026-09.md`) und die ROADMAP den Begriff tragen.

**Ein Zwilling ist eine Auskunft, die an mehr als einer Stelle hergeleitet
wird** — eine Zahl, eine Regel, ein Satz, eine Rechnung. Nicht jede
Wiederholung von Code ist gemeint, sondern jede zweite Herleitung derselben
Sache: die, bei der ein Nachbessern an der einen Stelle die andere nicht
erreicht.

## Die Regel

**Vor einer Änderung an einer Logik wird nach allen Stellen gesucht, die
dieselbe Auskunft herleiten. Gefunden wird geprüft — geändert wird, was
geändert werden muss.** Nicht „alle anpassen": Zwei Stellen dürfen
auseinandergehen, wenn jemand entschieden hat, dass sie verschiedene Fragen
beantworten. Unentschieden dürfen sie nicht bleiben.

## Vier Klassen, und jede hat eine Pflicht

| Klasse | Was es ist | Was zu tun ist |
|---|---|---|
| **gewollt** | Dieselbe Handlung in zwei Rechenkernen oder zwei bewusst getrennten Fassungen | Ein **Kriterium**, das sagt, wann er entsteht, und ein **Test**, der beide auf dieselbe Frage gleich antworten lässt. Das Kriterium steht in `konzepte/entscheidungen-2026-08-22.md`: *Ein Zwilling entsteht dort, wo der Zweig ohne ihn endet — nicht dort, wo er möglich wäre* |
| **gehalten** | Eine Kopie, die aus einem **am Code belegten** Grund nicht zusammengelegt werden kann | Eintrag in einer kuratierten Liste mit dem Grund, dazu ein Wächter über die Wortgleichheit. Der Grund muss am Code stimmen — ein Docstring, der einen Test behauptet, ist kein Wächter |
| **ungewollt** | Dieselbe Auskunft zweimal hergeleitet, ohne Kriterium und ohne Grund | **Zusammenlegen.** Geht es in diesem Schritt nicht, wird es ein Punkt im Register — nicht ein Kommentar in beiden Dateien |
| **Namenszwilling** | Ein Name, zwei Sachen | **Umbenennen**, wenn beide öffentlich sind. Modulprivat und verschieden ist erlaubt |

Zwei Nachbarn sind **keine** Zwillinge und werden trotzdem gefunden:
**Musterwiederholung** — drei Zeilen, die drei Dialoge gleich tun; nur
auflösen, wenn eine Abstraktion ohnehin entsteht, ein Mixin für drei Zeilen
kostet mehr als es spart. Und der **fachliche Zwilling** — dieselbe Rechnung
in zwei Formen, mit verschiedenen Rückgaben; maschinell unsichtbar, nur beim
Anfassen der Stelle zusammenzulegen.

## Vor der Änderung: messen, dann lesen

```
.venv\Scripts\python.exe tools/twin_scan.py app
.venv\Scripts\python.exe tools/twin_scan.py tests --frage 2 --frage 3
```

Das Werkzeug ist eingecheckt, weil es dreimal neu gebaut wurde (24.08., 27.08.
und 07.09.2026), und jedes Mal hatte niemand die Zeilen von vorher. Es ist
**kein Test** und steht nicht im Tor: Ein Wächter über Wortgleichheit meldete
ein Dutzend Dreizeiler und übersähe die Fälle, die zählen.

**Denn die gefährlichen Zwillinge sind die, die schon auseinandergelaufen
sind.** Die zwei schlimmsten Funde des Laufs vom 07.09.2026 — zwei Antworten
darauf, was ein UTC-Zeitpunkt ist, und zwei Wege zum Pfad eines offenen
Handles — waren beide gedriftet und damit für jede Suche nach Gleichheit
unsichtbar. Und die **Zwillingsregel der Oberfläche** stand in zwei
Formulierungen, einer bedingten und einer unbedingten: keine der sieben Fragen
des Werkzeugs zeigt darauf, weil zwei Fassungen derselben Regel weder wort-
noch strukturgleich sind. Gefunden hat sie jemand, der den Code kannte.

**Ein Skript findet Kopien; eine Regel in zwei Fassungen findet nur, wer die
Sache kennt.** Das Werkzeug ist der Zubringer der Durchsicht, nicht ihr
Ersatz.

## Woher sie kommen

Sechs Wege, jeder an einem Fall dieses Projekts belegt (§0.6 des Konzepts):

1. **Eine Schichtgrenze als Vorwand, die keine ist.** „Die Wahrnehmung darf
   die Geometrie nicht importieren" — sie tat es längst. Wer eine Grenze
   vermutet, statt sie nachzulesen, kopiert.
2. **Zwei Anlässe, zwei Sitzungen, ein Problem.** Wer parallel arbeitet,
   findet die Nachbarstelle nicht, weil sie noch nicht committet ist.
3. **Der Kommentar fühlt sich wie Teilen an.** „Dieselbe wie … aus demselben
   Grund" ist ehrlich und wirkungslos — er wandert beim nächsten Anfassen
   nicht mit.
4. **Der Name statt der Eigenschaft.** `== "orca"` meint jedes Mal etwas
   anderes und sieht jedes Mal gleich aus. Wo hinter dem Vergleich eine
   **Frage** steht, gehört ein Prädikat hin (`slicer_keys.py` führt sie).
5. **Das Geschwistermodul entsteht durch Kopieren** und nimmt die
   Hilfsfunktion mit, statt sie herauszuziehen.
6. **Jede Testdatei bringt ihre Fixture mit**, weil sie allein lauffähig sein
   soll.

## Was das Tor hält

`tests/test_shared_constants.py` prüft die Konstanten der Anwendung in zwei
Richtungen: **derselbe Name mit demselben Wert** an mehr als einer Stelle, und
**ein öffentlicher Name für zwei verschiedene Werte**. Beide Tests haben eine
Untergrenze, die rot wird, wenn der Suchlauf selbst kaputtgeht.

Über **Funktionskörper** wacht nichts, und das ist eine Entscheidung (§3 des
Konzepts), keine Lücke im Bau. Ein Kommentar, der einen Wächter behauptet,
wird von niemandem geprüft — wer einen Zwilling hält, hängt einen Test daran
oder legt ihn zusammen.

## Wo was steht

| Frage | Ort |
|---|---|
| Welche Klasse hat dieser Fund, und woran ist das belegt? | `konzepte/konzept-zwillinge-2026-09.md` — der Stand seiner Tabellen ist der seines Stichtags |
| Welche Zusammenlegung ist beauftragt? | Das Register in `ROADMAP.md` — **und nirgends sonst** |
| Was war schon einmal da? | `ROADMAP-ARCHIV.md`, Abschnitt „Doppelte Stellen und Zwillinge" |

**Am 18.09.2026 gegen den Code nachgemessen**, weil eine Statustabelle immer
über ihren Stichtag spricht: Von den elf ungewollten Funden des Laufs vom
07.09. sind sieben zusammengelegt — darunter die beiden gefährlichsten
(Zeitstempel, `is_a_cavity` steht heute in `core/types.py`) und die
Zwillingsregel der Oberfläche, die als `registry.shown_of_twins` in den Kern
gewandert ist. Vier stehen noch:

| Stelle | Anmerkung |
|---|---|
| `scene/project._opened_file_path` ↔ `updates._descriptor_path` | Bereits gedriftet; seit dem 02.09. im Register |
| `knowledge/calibration._literal` ↔ `knowledge/parts/scad._literal` | Wortgleich, klein |
| `viewport.ambient_occlusion` ↔ `contact_shadows` | **Nur die Bedingung** ist der Zwilling; die zwei Eigenschaften bleiben zwei — sie beantworten verschiedene Fragen, die heute dieselbe Antwort haben |
| `tools/make_licence_keys._new_keypair` ↔ `tools/sign_version.new_keypair` | Sicherheitsnah, außerhalb dieses Geltungsbereichs |

Wer eine dieser Dateien anfasst, legt die Stelle zusammen, statt sie zu
umgehen.
