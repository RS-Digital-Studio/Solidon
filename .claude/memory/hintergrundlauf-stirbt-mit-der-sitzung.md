---
name: hintergrundlauf-stirbt-mit-der-sitzung
description: "Ein mit run_in_background gestarteter Lauf (Modellmatrix, 90 min) starb, als die Sitzung nach einer Kontextverdichtung neu aufsetzte — lange native Läufe abgekoppelt starten und ihren Fortschritt aus Dateien lesen"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c8bf1d70-6f46-4992-9b9e-5becddfdbd88
  modified: 2026-09-06T08:20:59.740Z
---

Am 06.09.2026 lief die GFX-Modellmatrix (`run_block.py`, 23 Fälle, rund 90
Minuten) als Hintergrund-Bash-Aufgabe. Als die Sitzung nach der
Kontextverdichtung neu aufsetzte („Continue from where you left off“), war der
Prozess weg: Fall 12 stand mitten im Lauf, kein Ergebnis, kein Fehler — nur
ein `START`-Eintrag ohne Zeile danach. Die Sitzung hatte dabei auch ihren
Namen gewechselt (3d-druck-7e → 3d-druck-f7), das Sitzungsbrett kannte den
alten Eintrag nicht mehr.

**Why:** Hintergrundaufgaben hängen am Prozess der Sitzung; ein Neustart
nimmt sie mit. Ein Lauf, der länger dauert als ein Kontextfenster trägt, muss
davon unabhängig sein.

**How to apply:** Lange native Läufe (Matrix, Leistungsreihe, Tor) so
starten, dass sie den Sitzungsprozess überleben — auf Windows etwa über
`powershell Start-Process` mit eigenem Fenster/`-WindowStyle Hidden` oder
über eine geplante Aufgabe —, und den Fortschritt aus ihren Protokolldateien
lesen (`final-v9-run.log`, `g4-exit.txt`), nie aus dem Aufgabenstatus. Nach
einem Neustart zuerst prüfen, ob die eigenen Prozesse noch leben
(`Get-CimInstance Win32_Process`), dann Brett-Eintrag und Sitzungsnamen
erneuern. Was `run_block.py` kann: Es hängt Ergebnisse an und nimmt
`--indices` — ein Neustart mit den fehlenden Nummern genügt.
Siehe [[abgebrochener-lauf-hinterlaesst-waisen]], [[gekillter-lauf-schreibt-weiter]].
