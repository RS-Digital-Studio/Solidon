---
name: eigenen-lauf-ueber-die-elternkette-beenden
description: Beim Abbrechen eines Torlaufs nur den eigenen Prozessbaum beenden — ein Kommandozeilenmuster („-m pytest") trifft im geteilten Baum fremde Läufe, und die sehen von außen gleich aus.
metadata:
  node_type: memory
  type: feedback
  modified: 2026-09-02T00:00:00.000Z
---

Am 02.09.2026 habe ich meinen eigenen Torlauf abgebrochen, damit das
Release-Tor einer anderen Sitzung das Schloss bekommt — und dabei alle
Prozesse beendet, deren Kommandozeile `-m pytest` oder den xdist-Arbeiter
(`exec(eval(sys.stdin.readline()))`) trug. Darunter war der gerade
angelaufene Release-Lauf von 85: Sammelgruppe mit acht Arbeitern und ein
Fensterlauf. Der Lauf war ungültig und musste von vorn.

Der Fehler hat zwei Hälften. Erstens: Auf dieser Maschine laufen zwei bis
vier Sitzungen, und ihre Testprozesse sind an der Kommandozeile **nicht**
unterscheidbar — dieselbe `.venv`, dieselben Argumente, dieselben Arbeiter.
Zweitens: Ich hatte die Elternkette vorher gemessen (`Get-Tree` unter meinem
`gate_lock`-Prozess) und sie ergab drei Prozesse — die pytest-Kinder hingen
nach dem Beenden der Bash verwaist daneben. Statt die Waisen über ihre
**tote** Elternnummer zu erkennen, habe ich zum Muster gegriffen.

**Why:** Ein Muster misst, was leicht zu greifen ist; die Zugehörigkeit
steht in der Elternkette, und die bleibt auf Windows auch dann lesbar, wenn
der Elternprozess schon tot ist (`ParentProcessId` wird nicht umgesetzt).

**How to apply:** Vor dem Beenden den eigenen Baum unter dem eigenen
`gate_lock`-Prozess einsammeln und **zuerst die Blätter** beenden (pytest,
Arbeiter), dann die Bash, dann `gate_lock` — so entstehen keine Waisen. Bleiben
doch welche, gehören nur die dazu, deren `ParentProcessId` auf eine Nummer
aus dem eigenen Baum zeigt. Ein pytest-Prozess mit lebendem fremdem
Elternteil ist fremd, egal wie seine Kommandozeile aussieht. Und: Wer nicht
sicher zuordnen kann, beendet nichts und fragt die andere Sitzung.
