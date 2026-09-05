---
name: make-manual-kennt-kein-help
description: "tools/make_manual.py --help erzeugt das ganze Handbuch (SVGs, 6 Seiten, 6 PDFs) und nimmt dabei die Inhaltsstempel weg; danach muss stamp_assets.py laufen"
metadata: 
  node_type: memory
  type: project
  originSessionId: f205bb02-89f3-41d7-a514-397ddd2fe07b
  modified: 2026-09-05T12:12:11.848Z
---

`tools/make_manual.py` hat keine Argumentauswertung: `--help` (und jedes andere
Argument) startet die vollständige Erzeugung — 34 Abbildungen je Sprache, sechs
Handbuchseiten, sechs PDFs unter `Releases/` (je 12 MB, versioniert). Die neu
geschriebenen Seiten tragen **keine** `?v=`-Stempel mehr; `tools/stamp_assets.py`
muss danach laufen, sonst sind die Website-Tests rot (05.09.2026, Sitzung c7:
174 geänderte Dateien durch einen Blick in die Hilfe).

**Why:** Die Optionen stehen nur im `/erzeugen`-Skill, nicht im Werkzeug; wer die
Hilfe fragt, hat schon erzeugt.

**How to apply:** Vor jedem Aufruf eines Erzeugers unter `tools/` den
`/erzeugen`-Skill lesen statt `--help` zu probieren. Ist es passiert: erst
`stamp_assets.py`, dann entscheiden, was davon committet wird — SVG und HTML
sind klein, die PDFs nicht. Siehe [[erzeugtes-laeuft-nicht-in-der-ci]].
