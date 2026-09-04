---
name: alexander-schneider-kunde-und-mac-tester
description: "Alexander Schneider — Kunde mit der SKÅDIS-Anfrage, hat die Lochplatte selbst nachgemessen, und sein Mac-Testbericht steht noch aus."
metadata: 
  node_type: memory
  type: project
  originSessionId: e44e7ebf-a72f-4543-a02a-0efbcc35b48d
  modified: 2026-09-03T18:29:11.798Z
---

Erster echter Kunde, der auf die Bibliothek eingewirkt hat, und derzeit der
einzige Zugang zu einem Mac.

**Die Anfrage (24.08.2026):** SKÅDIS-Haken an ein heruntergeladenes Modell
hängen, ohne es in einem CAD-Programm nachzukonstruieren. Robert hat zugesagt,
es zu bauen. Eingelöst — der Baustein heißt `pegboard_hook` und steht in
`app/core/knowledge/parts/mounting.py`; das Konzept dazu ist
`konzepte/konzept-befestigungssysteme-2026-08.md`.

**Sein Beitrag zur Geometrie (27.08.2026):** Er hat eine echte SKÅDIS-Platte
mit dem Messschieber vermessen — Schlitz 4,9 bis 5,1 breit, 14,9 bis 15,1
hoch, über zwei benachbarte Schlitze 45,0. Die Nennmaße der Zeichnung waren
damit bestätigt; **neu war die Toleranz von ±0,1 mm, die keine Zeichnung
hergibt.** Sie ist der Grund, aus dem der Zapfen sein Spiel aus dem
Materialprofil zieht statt knapp auf Nennmaß zu bauen. Steht in
`standards.toml` und wird von `tests/test_parts.py` festgehalten.

**Was offen ist:** Ein Testbericht von seinem Mac (er hat dort ein
Buchprojekt). Daran hängt der Roadmap-Punkt „Ein Gewinde auf macOS kann als
STL Löcher haben" (`- [~]`, 20.08.2026): Ob der Riss dort wirklich eine
T-Kreuzung ist, lässt sich unter Windows nicht erzeugen — jede Größe ist hier
dicht. `stitch_t_junctions` ist für den Fall gebaut und kann nichts
verschlimmern; ob es ihn trifft, sagt erst der erste Lauf auf seinem Rechner.

**Why:** Eine Zusage an einen echten Kunden und die einzige offene Frage, die
niemand hier beantworten kann. Beides altert still, wenn es nur in einer
Roadmap-Zeile steht.

Verwandt: [[bausteinbereich-ist-ein-produktionsvertrag]],
[[beispiel-masse-gegen-parameter-messen]], [[mypy-prueft-die-laufende-plattform]].
