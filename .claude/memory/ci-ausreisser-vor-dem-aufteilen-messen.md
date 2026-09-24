---
name: ci-ausreisser-vor-dem-aufteilen-messen
description: Vor jeder CI-Aufteilung die Dauer je Test messen — ein einzelner Fall von 319 s war ein quadratischer Produktweg und bestimmte das Ende jedes Kernjobs
metadata:
  node_type: memory
  type: project
  originSessionId: eda33e4f-279c-48e3-bf58-acf625bcf116
  modified: 2026-09-24T20:26:37.061Z
---

Am 24.09.2026 zeigte ein lokaler Kernlauf mit `--durations=0` und JUnit
(16 575 Fälle, 3036 s Rechenzeit): **ein** Fall trug 319 s,
`test_seal_geometry[12.0]`. Ursache war kein Test, sondern der Kern — die
Wandmessung (`geom/mesh.ray_hits_batch`) rechnete seit dem VTK-Ausbau am
Vortag (RM-050) jeden Strahl gegen jedes Dreieck, 2 Mrd. Paare. Behoben mit
einer exakten räumlichen Vorauswahl: 319 s → 24–34 s, Bausteinnachweis
unverändert.

**Why:** Mehr Runner oder Teile helfen nicht gegen einen Einzelfall — er ist
die Untergrenze des Jobs, in dem er landet. Codex hatte die Fensterdateien
aufgeteilt, ohne die Kernsuite je Test zu messen; der Kern war danach der
kritische Pfad, und sein Ende hing an diesem einen Fall.

**How to apply:**
- Vor einer Aufteilung oder Worker-Änderung einmal
  `pytest -n 8 -m "not performance and not windowed and not rendered" --junitxml=… --durations=0`
  fahren und die JUnit je Datei und je Fall auswerten; die Kern-CI schreibt
  seither selbst JUnit (`reports/core/junit.xml` je Teil).
- Ein Fall über etwa einer Minute ist zuerst eine Frage an den Produktcode —
  derselbe Weg wartet beim Kunden. Den Test nicht verkleinern.
- Die Laufzeittabellen erzeugt `tools/ci_shards.py` aus JUnit, nie von Hand.
- Ein Docstring in `knowledge/parts/range_check.py` (und den anderen Dateien
  in `range_proof._SHARED`) macht `part_ranges.toml` veraltet — danach
  `tools/check_part_ranges.py --all` fahren (am 24.09.2026: 199 s, 4 Prozesse).

Siehe [[heredoc-frisst-den-backslash]] — dreimal an diesem Tag: Python-Umbauten
mit `\n` oder `\\` gehören in eine Skriptdatei, nicht in einen Heredoc.
