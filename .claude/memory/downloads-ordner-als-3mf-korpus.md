---
name: downloads-ordner-als-3mf-korpus
description: "Der Downloads-Ordner des jeweiligen Rechners ist der Messkorpus aus echten Kundendateien — am 15.09.2026 auf dem Arbeitsrechner 34 STL/3MF (343 Körper, 6,4 Mio. Dreiecke); die Sonden dazu liegen eingecheckt unter .claude/.state/merkmale-durchsicht-2026-09-15/"
metadata:
  node_type: memory
  type: reference
  originSessionId: 7293a802-9169-410a-a096-ea49bc8955e1
  modified: 2026-09-15T12:00:00.000Z
---

`~/Downloads/*.3mf` und `*.stl` — auf dem Rechner `rober` am 14.09.2026
sechzehn 3MF aus MakerWorld (Bambu Studio) und vom Elegoo-Slicer, darunter
`chufang.3mf` (5,5 Mio Dreiecke, 28 Modelldateien, 744 429 Bemalungscodes)
und drei Elegoo-Dateien mit `<slic3rpe:shape …/>` ohne Namensraum; auf dem
Arbeitsrechner `roschneider` am 15.09.2026 **34 Dateien**: die 19 STL der
Uhrenteile „REMONTOIRE ESCAPEMENT" samt 3MF-Baugruppe, Kartenmischer (77
Körper), Minigolf-Satz (34), Schreibtisch-Organizer (17), Scheune 1:24 (89),
Besenhalter, Handtuchhalter, Waschmaschine, Gewindeprüfer, Stifthalter.
Nicht im Repository, nicht in `tests/data/`.

**Der Ordner ist flüchtig.** Am 15.09.2026 gegen 05:42 waren die sechzehn
3MF auf `rober` verschwunden — mitten in einer Sitzung. Wer den Korpus
braucht, prüft zuerst, ob er noch da ist, und bittet Robert sonst um die
Dateien (MakerWorld gibt sie nur angemeldet heraus).

**Why:** Ein Kundenbericht ohne Anhang (S-20260914-e4b6d7) nennt nur die
Fehlerzeile; MakerWorld gibt die Datei nur angemeldet heraus. Der Ordner hat
in einer Minute vier von sechzehn Dateien als abgewiesen gezeigt und beide
Ursachen geliefert. Und am 15.09.2026 hat er an einem Tag geliefert, was der
eigene Korpus nie zeigte: eine Langlochsuche von 124 s an 531 Verrundungen,
eine Bohrung, die nach einer fremden Operation in zwei Hohlkehlen zerfiel,
50 von 52 Verrundungen, an denen das Panel anbot, was die Operation ablehnte
(Befund in `ROADMAP-ARCHIV.md`, Register RM-177 bis RM-182).

**How to apply:** Vor jeder Änderung an Erkennung, Langlochsuche oder
Merkmalsoperationen den Korpus fahren — die Sonden sind eingecheckt unter
`.claude/.state/merkmale-durchsicht-2026-09-15/` (README dort):
`run_all.py` lädt jede Datei über den Kundenweg und schreibt je Körper
Merkmale, Plausibilitätsprüfungen und Handlungsliste; `probe_ops.py` fährt
jede angebotene Operation mit Undo; `compare_detect.py` vergleicht die
Merkmale zweier Code-Stände (Arbeitsbaum gegen `git worktree add … HEAD`)
bitgenau — so wurde die Langlochsuche als ergebnisgleich belegt. Vor der
Änderung am 3MF-Leser weiter `threemf.read_objects(payload, findings)` je
Datei. Siehe [[testprojekt-trifft-den-fall-nicht]] — eine synthetische Box
prüft die Regel, der Ordner prüft die Dateien, die Kunden wirklich haben.
