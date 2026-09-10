---
name: make-manual-kennt-kein-help
description: "Kein Erzeuger unter tools/ wertet Argumente aus: --help startet den vollen Lauf — make_manual das Handbuch, make_examples alle 18 Beispieldateien"
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

**Und es ist nicht nur `make_manual`.** `tools/make_examples.py --help` baut
alle achtzehn Beispieldateien neu (10.09.2026). Der Lauf selbst ist
deterministisch — zweimal gefahren, byteweise gleich —, aber er misst den
**heutigen** Code, und der ist seit dem letzten Erzeugerlauf weiter: eine SVG
bekam eine andere Triangulierungsdiagonale (193 statt 197 Konturen), was
`test_slots` rot machte, und ein Byte-Nachweis in `ASSET-RIGHTS.toml` band ein
Website-Video an die alte Fassung von `weg3-generiert-aufbereiten.p3d` —
vorwärts hätte das einen Videobau bedeutet. Zurückgenommen wurde es über
`git checkout -- app/examples/`; das ist hier kein Revert fremder Arbeit,
sondern die Rücknahme des eigenen Werkzeuglaufs an erzeugten Dateien, und HEAD
war nachweislich sauber.

**How to apply:** Vor jedem Aufruf eines Erzeugers unter `tools/` den
`/erzeugen`-Skill lesen statt `--help` zu probieren. Ist es passiert: erst
`stamp_assets.py`, dann entscheiden, was davon committet wird — SVG und HTML
sind klein, die PDFs nicht. Siehe [[erzeugtes-laeuft-nicht-in-der-ci]].
