---
name: bauplan
description: >
  Schlägt einen Abschnitt im Bauplan nach und fasst zusammen, was dort verbindlich
  festgelegt ist — per §-Nummer oder Stichwort. Benutzen, bevor eine Behauptung
  über das Sollverhalten von Solidon aufgestellt wird.
argument-hint: "[§-Nummer oder Stichwort]"
allowed-tools: Read, Grep, Bash
---

# Bauplan nachschlagen: $ARGUMENTS

Der Bauplan sagt, **was** gebaut wird. Bei Widerspruch gewinnt er. Eine
Aussage über das Sollverhalten ohne §-Beleg ist eine Vermutung.

## Gliederung

```!
rg -n "^## " "3d-agent-bauplan.md"
```

## Vorgehen

Ist ein Paragraph genannt (`§22`, `22`, `22.3`), lies ihn vollständig aus
`3d-agent-bauplan.md` — von seiner Überschrift bis zur nächsten. Ist ein
Stichwort genannt, suche zuerst in der Gliederung oben, dann im Volltext, und
lies die Fundstelle im Zusammenhang statt einzelner Zeilen.

Prüfe danach die ergänzenden Quellen:

- `AGENTS.md` — gibt es dazu eine harte Regel mit Test?
- `ROADMAP.md` — welcher konkrete Rest und welche Abnahme stehen bei der
  zugehörigen RM-Kennung? Das Register führt ausschließlich aktuelle Arbeit.
- `ROADMAP-ARCHIV.md` — welcher datierte Befund oder welche Entscheidung
  erklärt den heutigen Vertrag? Historische Ist-Aussagen gelten für ihren
  damaligen Stand, nicht automatisch für den heutigen Code.

Wenn die Frage den tatsächlichen Stand betrifft, lies die im Bauplan
genannte Umsetzung und ihre Prüfungen. Eine vorhandene Implementierung
belegt noch keine Plattform- oder Feldabnahme. Eine Abweichung im Code hebt
die Anforderung nicht auf: Entweder ersetzt eine belegte Produktentscheidung
den alten Vertrag, oder die Lücke bleibt ausdrücklich in der Roadmap.

Bei einem vollständigen Abgleich alle nummerierten Abschnitte erfassen,
Kernverträge und Dateibeispiele gegen ihre ausführbaren Quellen prüfen und
§-Nummern für bestehende Verweise erhalten. Historische Messungen und
Begründungen gehören ins Archiv; aktive Anforderungen werden nicht als
Aufräumarbeit gestrichen.

## Antwort

Kurz zusammenfassen, was verbindlich ist, mit §-Nummer. Dann: was daraus für
die aktuelle Frage folgt. Wenn Bauplan und Umsetzung auseinanderlaufen, sag
welche Stelle — das ist ein Fund, kein Detail. Wenn der Bauplan die Frage
**nicht** beantwortet, sag genau das, statt eine Antwort zu konstruieren.
