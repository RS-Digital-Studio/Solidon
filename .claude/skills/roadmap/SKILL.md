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

**Erst das Register.** Gleich unter der Legende steht der Abschnitt *Was offen
ist*: jeder offene Punkt mit seinem Abschnitt und dem, worauf er wartet.
`tests/test_roadmap.py` hält ihn am Bestand — was dort steht, stimmt. Damit ist
„was ist offen" ein Blick und keine Suchrunde durch fünftausend Zeilen.

Das Register nennt aber nur *dass* etwas offen ist. **Die Begründung steht am
Punkt selbst**, und dorthin gehst du, bevor du ihn vorschlägst — dort steht auch,
was schon versucht wurde.

Der Rest der Datei ist die Geschichte des Projekts: Abschnitte, die nach echten
Durchsichten entstanden sind, mit Funden, zurückgenommenen Behauptungen und
gemessenen Irrwegen. Der weitaus größte Teil enthält keinen offenen Punkt — und
ist trotzdem das Teuerste, was die Datei hat. Wer an einer Stelle arbeitet, an
der schon jemand war, spart dort Tage. Die Phasen P0 bis P16 stehen **zwischen**
diesen Abschnitten verstreut, nicht gesammelt oben — such sie, statt sie an
einer Position zu erwarten.

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
Fund gehört dort ergänzt, mit dem, was er gekostet hat. **Beides an zwei
Stellen**: am Punkt selbst und im Register oben. Vergisst du die zweite, wird
`tests/test_roadmap.py` rot und sagt dir, welcher Abschnitt nicht mehr passt. Die Roadmap ist die
Stelle, an der die Geschichte dieses Projekts steht; `CLAUDE.md` und
`AGENTS.md` sind es ausdrücklich nicht.
