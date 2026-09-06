---
name: scratchpad-ist-nicht-dauerhaft
description: "Der Scratchpad-Ordner unter %TEMP%\\claude\\… kann mitten in der Arbeit verschwinden (C:-Aufräumen einer anderen Sitzung, Neustart) — Übergabedateien, Patches und Berichte gehören nach output/review/<datum>/ auf F:."
metadata:
  type: project
  originSessionId: 604362f2-7546-4f58-8ac6-a717d093adc0
  modified: 2026-09-06T10:41:29.216Z
---

Am 06.09.2026 lagen in meinem Scratchpad vier Agentenberichte, fünf
geprüfte Patches für andere Sitzungen und zwei Hilfsskripte. Gegen 11:44
räumte eine andere Sitzung ihre volle C:-Platte auf, und danach war der
gesamte Ordner `%TEMP%\claude\F--3D-Druck\<sitzung>\scratchpad` weg — die
Pfade, die ich zwei Sitzungen per Nachricht gegeben hatte, zeigten ins Leere.

**Why:** `%TEMP%` ist benutzerweit und liegt auf C:, der knappsten Platte
dieser Maschine ([[temp-dateien-sind-maschinenweit]]). Wer dort aufräumt,
räumt fremde Scratchpads mit auf, und ein Neustart der Sitzung legt den
Ordner nicht wieder an. Das Scratchpad ist für Zwischenergebnisse einer
einzigen Sitzung gedacht, nicht für Übergaben.

**How to apply:** Alles, was eine andere Sitzung lesen soll oder nach einem
Neustart noch gebraucht wird — Patches, Berichte, Prüfläufer, Messlisten —
liegt unter `F:\3D Druck\output\review\<thema>-<datum>\` (gitignoriert, auf
F:, dort liegen auch die Reviews selbst). Im Scratchpad bleiben nur
Sonden und Logs, deren Verlust nichts kostet.
