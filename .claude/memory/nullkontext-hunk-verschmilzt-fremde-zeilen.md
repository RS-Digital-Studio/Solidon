---
name: nullkontext-hunk-verschmilzt-fremde-zeilen
description: "Beim Commit über Hunk-Auswahl aus git diff -U0 im geteilten Baum: angrenzende Einfügungen zweier Sitzungen kommen als EIN Hunk — Marker-Auswahl nimmt die fremden Zeilen mit; und git apply --unidiff-zero setzt reine Einfügungen nach der NEUEN Zeilennummer, also neben fremde Hunks — Hunks nach der alten Nummer auf HEAD setzen"
metadata:
  node_type: memory
  type: feedback
  originSessionId: eda33e4f-279c-48e3-bf58-acf625bcf116
  modified: 2026-09-25T11:16:58.915Z
---

Am 25.09.2026 habe ich die Arbeit der Reparatursitzung und meine über einen
Worktree in drei Commits gebaut: HEAD plus ausgewählte Hunks aus
`git diff -U0` des geteilten Baums. Drei Fehler, alle drei erst durch
Nachmessen gefunden:

- **Zwei Einfügungen, die aneinanderstoßen, sind ein Hunk.** Mausoleum hatte
  an den RM-238-Eintrag Zeilen angehängt, die Reparatursitzung direkt danach
  RM-239/240 eingefügt. `-U0` meldete eine einzige Einfügung von 61 Zeilen;
  meine Auswahl „Hunk enthält RM-239" nahm Mausoleums Absatz mit. Gefunden,
  weil der Schnappschuss der nächsten Stufe an genau dieser Stelle anders war.
- **Eine Datei, die ich für fremd hielt, war der Rest der Reparatur.**
  `tests/test_geometry_review.py` stand in meiner Liste als Mausoleums Datei;
  das Tor wurde mit zwei Fehlern rot, die genau ihre Hunks erwarteten.
- **Wer Funktionen aus einer Einfügung schneidet, verliert die Leerzeilen
  davor**, wenn der Hunk mit ihnen beginnt — `ruff format --check` wurde rot.
- **`git apply --unidiff-zero` setzt eine reine Einfügung nach der
  Zeilennummer der neuen Seite** (am selben Tag, RM-224 Schritt 3). Über
  meinem `wait_for_idle` in `tests/test_ui.py` standen 320 fremde Zeilen; die
  Einfügung landete in einem fremden Test, und das Tor brach mit einem
  Syntaxfehler. Hunks mit alten Zeilen findet `apply` am Inhalt und setzt sie
  richtig. Sicher ist, HEAD zu nehmen und die gewählten Hunks nach ihrer
  **alten** Nummer von unten nach oben zu setzen, mit Prüfung der alten
  Zeilen (Skript `eigene_hunks.py` im Scratchpad der Sitzung).

**Why:** Hunk-Auswahl nach Inhaltsmarkern prüft, ob ein Hunk *eigene* Zeilen
enthält, nicht ob er *nur* eigene enthält.

**How to apply:** Reine Einfügungen am eigenen Anker schneiden (ab
`<a id="rm-…">`, je Funktion), nie ganze Hunks nach einem Wort nehmen; jede
Stufe im Worktree gegen die Arbeitskopie des Hauptbaums diffen und je Datei
die Zeilenzahl der Abweichung gegen die eigene Änderung halten; Kataloge und
Regeldateien, in die andere schreiben, aus dem Stand der Vorstufe plus dem
eigenen Eintrag bauen, nicht aus der Arbeitskopie. Siehe
[[datei-die-vor-dem-patch-modifiziert-war-geht-nur-als-blob]],
[[geteilter-index-nach-fremdem-commit-veraltet]] und
[[patchuebernahme-in-den-geteilten-baum]].
