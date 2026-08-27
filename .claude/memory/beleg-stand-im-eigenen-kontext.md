---
name: beleg-stand-im-eigenen-kontext
description: "Bevor man eine Wissenslücke behauptet, sucht man im ganzen Repository — nicht nur in der Doku. Regeln stehen auch in eingecheckten Hooks, und die injizieren sie oben in den eigenen Kontext."
metadata:
  type: feedback
---

Am 27.08.2026 kürzte ich in `CLAUDE.md` einen Sprachabschnitt, der wörtlich in
`AGENTS.md` stand. Eine Nachbarsitzung las den Diff gegen und meldete eine
Lücke: „mit echten Umlauten" stehe jetzt **nirgends mehr im Projekt**, die
Regel hänge nur noch an Roberts globaler `~/.claude/CLAUDE.md` außerhalb des
Repositories — mit dem Vorschlag, eine Zeile in `AGENTS.md` zu verankern.

Gemessen war das nicht. Ein `grep` über `*.md`, `*.py` und `*.toml` findet die
Regel achtmal eingecheckt, und die tragende Stelle ist
`.claude/hooks/solidon3d_hooks.py:216`: Der SessionStart-Hook injiziert
wörtlich „Doku, Commits und Gespräch auf Deutsch mit echten Umlauten." Dazu
`liefern/SKILL.md`, fünf Agent-Definitionen und eine Erinnerungsdatei. Keine
Lücke, keine Aktion — und die vorgeschlagene `AGENTS.md`-Änderung wäre auf
falscher Prämisse erfolgt.

Die Pointe: **Der Hook hatte beiden Sitzungen die Zeile in genau diesem
Gespräch selbst injiziert, ganz oben.** Sie stand die ganze Zeit in beiden
Kontexten, während eine von uns behauptete, es gebe sie nicht.

**Why:** Zwei Fehler greifen ineinander. Erstens antwortet ein `grep` über
`*.md` auf „steht es in der **Doku**?", nicht auf „steht es im **Projekt**?" —
die Ersatzfrage, vor der [[gemessene-frage-ist-nicht-die-gestellte]] warnt.
Zweitens tragen in diesem Projekt auch Nicht-Doku-Dateien Regeln: eingecheckte
Hooks, Skills, Agent-Definitionen. Ein Hook ist dabei die *wirksamste* Stelle
und die unauffälligste — er lädt in jeder Sitzung, ein frischer Klon hat ihn,
aber keine Doku-Suche erwischt ihn. Und was per Hook in den Kontext kommt,
zählt man nicht zum Bestand, weil man es nicht gelesen, sondern bekommen hat.

Die Behauptung war das Spiegelbild von [[verweis-auf-nichtexistierendes]]: Dort
wird die Existenz von etwas behauptet, das es nie gab, hier die
Nicht-Existenz von etwas, das achtfach vorliegt. Beide lesen sich glatt, beide
kosten eine Sekunde zur Prüfung.

**How to apply:**

- **Bei jeder Kürzung und jeder Verschiebung** fragt die Doktrin, ob Wissen
  verschoben oder weggeworfen wurde. Das prüft man mit einem `grep` über
  `*.py`, `*.md`, `*.toml` und `*.json` — nicht über Markdown allein.
  `.claude/hooks/`, `.claude/skills/` und `.claude/agents/` tragen Regeln.
- **Bevor man eine Lücke behauptet, liest man den eigenen Kontextkopf.** Was
  der SessionStart-Hook injiziert, steht dort — oft genau die Zeile, deren
  Fehlen man gerade meldet.
- **Einen Fremdbefund über gelöschtes Wissen nachmessen, bevor man ihn
  einbaut.** Er kann aus einem Diff geschlossen statt gemessen sein; der Diff
  zeigt, was an *einer* Stelle verschwand, nie, was an den anderen steht.

Verwandt: [[was-die-suite-nicht-findet]] (kein Finder war pytest),
[[messung-traegt-nur-am-ort-ihrer-messung]] und
[[erinnerungen-liegen-im-repository]] — dieselbe Haltung, aus demselben Grund:
Was im Repository liegt, tragen alle drei Maschinen.
