---
name: speicherzusage-zu-dritt
description: "Drei Sitzungen mit parallelen Suite-Läufen sprengen die Windows-Speicherzusage (78 GB): MemoryError in der xdist-Sammlung, CreateFileMapping 1455 — die Suite fährt auch aus einem Worktree nur unter gate_lock, das Schloss liegt im gemeinsamen .git."
metadata:
  type: project
  originSessionId: 604362f2-7546-4f58-8ac6-a717d093adc0
  modified: 2026-09-06T08:33:48.685Z
---

Am 06.09.2026 liefen drei Sitzungen zugleich: eine geteilte Suite mit `-n 8`
im Reparatur-Worktree, native GFX-Fensterläufe der Renderer-Sitzung und
meine eigene geteilte Suite im selben Worktree, gestartet **ohne**
`gate_lock.py`. Der große Block starb bei mir mit `MemoryError` in der
xdist-Sammlung (alle acht Worker „not properly terminated“, Exit 3); die
andere Sitzung sah dasselbe plus `CreateFileMapping … Win32 error 1455`
(Auslagerungsdatei zu klein) und `WinError 8`. Freier physischer Speicher
war dabei noch da (13–19 von 64 GB) — gerissen ist die **Speicherzusage**
(Commit-Limit, hier 78 GB), die jeder Python-Prozess mit VTK, OCP und pygfx
um rund zwei GB belastet, mal acht Worker, mal drei Sitzungen.

**Why:** Das Torschloss (`tools/gate_lock.py`) liegt in
`git rev-parse --git-common-dir`, also im gemeinsamen `.git` aller
Arbeitsbäume — es gilt maschinenweit für dieses Repository. Wer die Suite
direkt startet, umgeht es und addiert seine Worker zu denen der anderen.
Die Regel „Leistungstests unter dem Schloss“ dachte an Messgenauigkeit
([[leistungstests-fremdlast]]); die Speicherzusage ist der zweite Grund, und
er trifft auch die geteilte Suite, nicht nur die Leistungstests.

**How to apply:** Die geteilte Suite immer über
`tools/gate_lock.py run --who <Sitzung> --wait 1800 -- …` fahren, auch aus
einem Worktree und auch „nur zur Probe“. Sind mehrere Sitzungen aktiv,
`SUITE_KERNE=4` statt 8. Stirbt die Sammlung mit `MemoryError` oder
`error 1455`, ist es kein Testfehler und keine Codeänderung: erst sehen, wer
sonst gerade fährt (Sitzungsbrett, Prozessliste), dann nacheinander.
