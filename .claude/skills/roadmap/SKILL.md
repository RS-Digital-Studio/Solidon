---
name: roadmap
description: >
  Zeigt den Stand der Arbeitsliste und schlägt den nächsten sinnvollen Schritt vor
  — offene Punkte der aktuellen Phase, Funde aus den Durchsichten, Abnahmekriterien
  aus Bauplan §40. Benutzen bei „was als Nächstes?".
argument-hint: "[optional: Phase oder Thema]"
allowed-tools: Read, Grep, Bash, Glob
---

# Roadmap: $ARGUMENTS

## Lesen

`ROADMAP.md` ist zweigeteilt: oben die Phasen P0 bis P12 als Arbeitsliste,
unten die Abschnitte, die nach echten Durchsichten entstanden sind — Funde aus
Modellprüfungen, zurückgenommene Behauptungen, offene Punkte. **Der untere Teil
ist aktueller als der obere.** Beide lesen, bevor du etwas vorschlägst.

Dazu `git log --oneline -15`: was zuletzt passiert ist, sagt oft mehr über den
Stand als eine Liste, in der ein Haken fehlt.

## Vorschlagen

Nenne drei Dinge, nicht zwanzig:

1. **Was offen ist** — die konkreten Punkte, mit ihrer Stelle in der Roadmap.
2. **Was du als Nächstes empfiehlst**, mit Begründung: Was blockiert anderes?
   Was ist ein Fund aus einer Durchsicht und damit ein bekannter Fehler? Was
   fehlt einer Phase zur Abnahme nach Bauplan §40?
3. **Was es kostet** — grob, und was es an anderer Stelle nach sich zieht.

Ein bekannter Fehler schlägt ein neues Feature. Ein Punkt, der eine Phase
abschließt, schlägt einen, der eine neue anfängt.

## Fortschreiben

Wird ein Punkt erledigt, gehört er in der Roadmap nachgezogen — und ein neuer
Fund gehört dort ergänzt, mit dem, was er gekostet hat. Die Roadmap ist die
Stelle, an der die Geschichte dieses Projekts steht; `CLAUDE.md` und
`AGENTS.md` sind es ausdrücklich nicht.
