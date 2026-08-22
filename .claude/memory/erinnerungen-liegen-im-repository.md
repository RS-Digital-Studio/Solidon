---
name: erinnerungen-liegen-im-repository
description: Die Erinnerungen zu Solidon liegen in .claude/memory im Arbeitsbaum; der Ort im Nutzerprofil ist nur eine Verknüpfung darauf
metadata: 
  node_type: memory
  type: project
  originSessionId: 0545ae7f-0dd2-436b-aa74-3a2e2040e3ae
  modified: 2026-08-22T16:07:57.945Z
---

Seit dem 22.08.2026 liegen die Erinnerungen zu Solidon **im Repository**, unter
`.claude/memory/`. Der Ort, an dem Claude Code sie sucht
(`~/.claude/projects/<Pfadkürzel>/memory`), ist nur eine Verzeichnisverknüpfung
darauf — eine Junction auf Windows, ein Symlink auf Linux und macOS.

**Warum:** An Solidon wird auf drei Maschinen gearbeitet, und der Ort im
Nutzerprofil gilt je Maschine. Was auf der einen gelernt wurde, kannte die
andere nicht — die Git-Identität, der geteilte Index, die Pipeline, die den
Exit-Code frisst. Jede Maschine hat dieselben Fallen einzeln gefunden. Über das
Repository trägt Git sie, ohne Kopierschritt und ohne zweite Wahrheit.

**How to apply:**

- Erinnerungen wie immer schreiben. Der Pfad ist derselbe, das Ziel ein anderes.
- **Auf einer neuen Maschine einmal `python tools/link_memory.py` laufen
  lassen.** Ohne diesen Schritt schreibt die Sitzung dort in einen eigenen
  Ordner, und die Erinnerungen driften wieder auseinander. `--pruefen` sagt, wie
  es steht, ohne etwas zu ändern; ein zweiter Aufruf tut nichts.
- Was im Nutzerprofil schon lag, übernimmt das Werkzeug ins Repository. Eine
  abweichende `MEMORY.md` legt es als `MEMORY.dieser-maschine.md` daneben statt
  sie zu überschreiben — Zeilen von Hand übernehmen, Datei danach löschen.
- Eine neue Erinnerung ist damit eine Änderung am Arbeitsbaum und will
  committet werden. Sie taucht in `git status` auf.

**Die Falle beim Bauen des Werkzeugs**, weil sie wiederkommt: `Path.stat()`
folgt einer Junction und liefert die Attribute des **Ziels** — das
Reparse-Point-Bit ist dort nicht gesetzt. Gefragt wird mit `lstat()`. Das
Werkzeug meldete zuerst „noch nicht verknüpft" über einer Verknüpfung, die es
selbst angelegt hatte.

Siehe [[parallele-sitzung-im-arbeitsbaum]] und
[[weitergegebene-anweisungen-gelten]].
