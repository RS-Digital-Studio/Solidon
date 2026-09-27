---
name: bauplan
description: >
  Schlägt einen Abschnitt im Bauplan nach und fasst zusammen, was dort
  verbindlich festgelegt ist — per §-Nummer oder Stichwort. Benutzen, bevor
  eine Behauptung über das Sollverhalten von Solidon aufgestellt wird.
argument-hint: "[§-Nummer oder Stichwort]"
allowed-tools: Read, Grep, Bash
---

# Bauplan nachschlagen: Angaben aus der aktuellen Anfrage

Der Bauplan sagt, **was** gebaut wird. Bei Widerspruch gewinnt er. Eine
Aussage über das Sollverhalten ohne §-Beleg ist eine Vermutung.

## Gliederung

```!
grep -n "^## " 3d-agent-bauplan.md
```

## Vorgehen

Ist ein Paragraph genannt (`§22`, `22`, `22.3`), lies ihn vollständig aus
`3d-agent-bauplan.md` — von seiner Überschrift bis zur nächsten gleicher
Ebene. Ist ein Stichwort genannt, suche zuerst in der Gliederung, dann im
Volltext, und lies die Fundstelle im Zusammenhang statt einzelner Zeilen.

Danach die ergänzenden Quellen:

- `AGENTS.md` — gibt es dazu eine harte Regel mit Test?
- `ROADMAP.md` — welcher Rest und welche Abnahme stehen bei der zugehörigen
  RM-Kennung? Das Register führt nur aktuelle Arbeit.
- `ROADMAP-ARCHIV.md` — welcher Befund oder welche Entscheidung erklärt den
  heutigen Vertrag? Historische Ist-Aussagen gelten für ihren damaligen Stand.

Betrifft die Frage den tatsächlichen Stand, die im Bauplan genannte Umsetzung
und ihre Prüfungen lesen. Eine vorhandene Implementierung belegt noch keine
Plattform- oder Feldabnahme. Eine Abweichung im Code hebt die Anforderung
nicht auf: Entweder ersetzt eine belegte Produktentscheidung den alten
Vertrag, oder die Lücke steht in der Roadmap.

Bei einem vollständigen Abgleich alle nummerierten Abschnitte erfassen,
Kernverträge und Dateibeispiele gegen ihre ausführbaren Quellen prüfen und
§-Nummern für bestehende Verweise erhalten. Historische Messungen gehören ins
Archiv; aktive Anforderungen werden nicht als Aufräumarbeit gestrichen. Den
Bauplan selbst ändert nur eine Ansage von Robert.

## Antwort

Kurz, was verbindlich ist, mit §-Nummer; dann, was daraus für die Frage folgt.
Laufen Bauplan und Umsetzung auseinander, die Stelle nennen — das ist ein
Fund, kein Detail. Beantwortet der Bauplan die Frage **nicht**, genau das
sagen, statt eine Antwort zu konstruieren.
