---
name: zweite-sitzung-im-selben-baum
description: "In F:\\3D Druck arbeitet oft eine zweite Sitzung gleichzeitig; vor jedem Prozess-Kill und vor jedem Torlauf prüfen, wem was gehört."
metadata: 
  node_type: memory
  type: project
  originSessionId: 9445bc01-20af-4b3c-9e8f-c80a1769a381
  modified: 2026-09-10T15:12:15.635Z
---

Am 10.09.2026 lief neben dieser Sitzung eine zweite im **selben** Arbeitsbaum
(sie baute die Merkmalsart `void`). Beide fassten `prepare_ops.py`,
`perceive/actions.py`, `ui/labels.py`, `tests/test_prepare.py`,
`test_registry_consistency.py` und die fünf Kataloge an. Drei Folgen, alle drei
kosteten Zeit:

- **Ein Prozess-Kill trifft fremde Läufe.** `Stop-Process` über alle
  `python.exe` mit `-m pytest` beendete das Tor der anderen Sitzung mit. Vor
  dem Kill die **Erzeugungszeit** und den **Testnamen** lesen: Was gerade
  entstanden ist und einen Test fährt, den man selbst nicht angestoßen hat,
  gehört jemand anderem.
- **Die eigene Suche zählt sich selbst mit.** `CommandLine -match '-m pytest'`
  trifft den PowerShell-Aufruf, der die Suche ausführt. Den Suchtext in eine
  `.ps1` im Scratchpad legen und die zusammensetzen (`'-m ' + 'pytest'`) —
  dann steht er nicht in der Kommandozeile.
- **Ein Torlauf misst einen Zeitpunkt.** Wer währenddessen schreibt — auch nur
  einen Docstring —, macht ihn wertlos: `inspect.getsource` las danach falsche
  Zeilen, und sieben Ops fielen bei `test_non_deterministic_operations_use_a_seed`
  durch, die isoliert alle grün sind. Erst fertig werden, dann fahren.
- **Und sie committet deine Zeilen mit.** Am selben Tag gingen meine
  ROADMAP-Ergänzung, meine acht Katalogeinträge und zwei umgestellte Tests in
  `test_ui.py` im Commit der **anderen** Sitzung hinaus — sie hat die Dateien
  gestaged, in denen auch meine Arbeit stand. Kein Schaden, aber die eigene
  Commit-Nachricht beschreibt danach etwas, das woanders steht.
- **Eine geteilte Datei sauber committen geht so:** die HEAD-Fassung holen, die
  **eigenen** Ersetzungen darauf anwenden, `git hash-object -w --path <datei>
  --stdin` und `git update-index --cacheinfo 100644,<sha>,<datei>`. Der
  Arbeitsbaum bleibt unberührt, im Index steht nur die eigene Zeile.
- **Die Falle daran ist HEAD selbst.** Bewegt er sich zwischen dem Bauen des
  Blobs und dem Commit — und das tut er, wenn die andere Sitzung gerade
  committet —, dann **nimmt der Blob ihre frische Arbeit zurück**: Er ist gegen
  den alten Stand gebaut. Gerettet hat mich nur die `index.lock`, an der mein
  `update-index` scheiterte. Also: `git rev-parse HEAD` unmittelbar vor dem
  Bauen und noch einmal vor dem Commit; sind sie ungleich, `git reset` und alles
  neu gegen den neuen HEAD.

**Warum:** Das Mehrsitzungs-Setup mit Schloss und eigenem Worktree ist am
09.09.2026 ausgebaut ([[mehrsitzungs-setup-ist-ausgebaut]]) — es gibt also
keine Technik, die das trennt, nur Aufmerksamkeit.

**How to apply:** Vor dem Torlauf `git status --short` lesen und fremde
Änderungen benennen; ein Tor über einem Baum mit fremder unfertiger Arbeit
misst deren Fehler mit und ist kein Abnahmenachweis. Vor einem Commit prüfen,
welche Dateien geteilt sind — ein `git add` nimmt fremde Hunks mit, und
`/liefern` wird ohnehin angesagt und nicht selbst gestartet. Siehe
[[eigenen-lauf-ueber-die-elternkette-beenden]] und
[[messwerkzeug-misst-sich-selbst]].
