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
grep -n "^## " "3d-agent-bauplan.md"
```

## Vorgehen

Ist ein Paragraph genannt (`§22`, `22`, `22.3`), lies ihn vollständig aus
`3d-agent-bauplan.md` — von seiner Überschrift bis zur nächsten. Ist ein
Stichwort genannt, suche zuerst in der Gliederung oben, dann im Volltext, und
lies die Fundstelle im Zusammenhang statt einzelner Zeilen.

Prüfe danach die beiden anderen Quellen:

- `AGENTS.md` — gibt es dazu eine harte Regel mit Test?
- `ROADMAP.md` — steht der Punkt noch offen, oder wurde er umgesetzt, und was
  wurde dabei gelernt? Die Abschnitte am Ende der Roadmap enthalten die Funde
  aus den Durchsichten und weichen manchmal vom ursprünglichen Text ab.

## Antwort

Kurz zusammenfassen, was verbindlich ist, mit §-Nummer. Dann: was daraus für
die aktuelle Frage folgt. Wenn Bauplan und Umsetzung auseinanderlaufen, sag
welche Stelle — das ist ein Fund, kein Detail. Wenn der Bauplan die Frage
**nicht** beantwortet, sag genau das, statt eine Antwort zu konstruieren.
