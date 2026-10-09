# Begründungen zu `.claude/rules/zwillinge.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

## Vor der Änderung: messen, dann lesen

Warum das Werkzeug eingecheckt ist und warum es nicht im Tor steht:

> Das Werkzeug ist eingecheckt, weil es dreimal neu gebaut wurde (24.08.,
> 27.08. und 07.09.2026), und jedes Mal hatte niemand die Zeilen von vorher.
> Es ist **kein Test** und steht nicht im Tor: Ein Wächter über Wortgleichheit
> meldete ein Dutzend Dreizeiler und übersähe die Fälle, die zählen.

Woran sich zeigte, dass die gefährlichen Zwillinge die gedrifteten sind:

> Die zwei schlimmsten Funde des Laufs vom 07.09.2026 — zwei Antworten darauf,
> was ein UTC-Zeitpunkt ist, und zwei Wege zum Pfad eines offenen Handles —
> waren beide gedriftet und damit für jede Suche nach Gleichheit unsichtbar.
> Und die **Zwillingsregel der Oberfläche** stand in zwei Formulierungen,
> einer bedingten und einer unbedingten: keine der sieben Fragen des Werkzeugs
> zeigt darauf, weil zwei Fassungen derselben Regel weder wort- noch
> strukturgleich sind. Gefunden hat sie jemand, der den Code kannte.

Die Regel sagte bis zur zweiten Kürzung dazu noch: „Ein Skript findet Kopien;
eine Regel in zwei Fassungen findet nur, wer die Sache kennt."

## Woher sie kommen

Bis zur zweiten Kürzung stand die Liste so in der Regel:

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

„Sechs Wege, jeder an einem Fall dieses Projekts belegt (§0.6 des
Konzepts)." Die Belege, die in der Regel nicht mehr stehen:

- Zur vermuteten Schichtgrenze: „„Die Wahrnehmung darf die Geometrie nicht
  importieren" — sie tat es längst."
- Zum Kommentar: „„Dieselbe wie … aus demselben Grund" ist ehrlich und
  wirkungslos — er wandert beim nächsten Anfassen nicht mit."
- Zum Namen statt der Eigenschaft: „`== "orca"` meint jedes Mal etwas anderes
  und sieht jedes Mal gleich aus."

## Was das Tor hält

Aus der Regel verschoben: Beide Tests in `tests/test_shared_constants.py`
haben eine Untergrenze gegen einen kaputten Suchlauf.

## Zwillinge, die noch stehen

Der Stand vor der Verdichtung:

> **Am 18.09.2026 gegen den Code nachgemessen**, weil eine Statustabelle immer
> über ihren Stichtag spricht: Von den elf ungewollten Funden des Laufs vom
> 07.09. sind sieben zusammengelegt — darunter die beiden gefährlichsten
> (Zeitstempel, `is_a_cavity` steht heute in `core/types.py`) und die
> Zwillingsregel der Oberfläche, die als `registry.shown_of_twins` in den Kern
> gewandert ist. Vier stehen noch:

| Stelle | Anmerkung |
|---|---|
| `scene/project._opened_file_path` ↔ `updates._descriptor_path` | Bereits gedriftet; seit dem 02.09. im Register |

*Anmerkung bei der Verdichtung (27.09.2026):* Diese Zeile ist aus der Regel
gestrichen. Beide Stellen rufen heute `app.core.paths.opened_path`; laut
Docstring von `updates._descriptor_path` seit dem 10.09.2026, und der fehlende
Windows-Pufferabgleich der älteren Kopie ist damit behoben. Die drei übrigen
Zeilen stehen am Code unverändert und bleiben in der Regel.
