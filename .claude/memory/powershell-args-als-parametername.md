---
name: powershell-args-als-parametername
description: Ein PowerShell-Funktionsparameter namens $args ist leer — pytest lief ohne Auswahl und fuhr 50 Minuten die ganze Suite
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 6535be56-54ec-49cb-8596-f35a930bf28d
  modified: 2026-09-13T15:45:49.467Z
---

Am 13.09.2026 sollte ein Nachlauf sechzehn einzelne Tests fahren:
`function Lauf($name, $args) { & $py -m pytest -q @args }`. `$args` ist in
PowerShell die **automatische** Variable für unbenannte Argumente; als
Parametername deklariert bleibt sie leer, `@args` splattet nichts, und
pytest startete **ohne Auswahl** — die ganze Suite in einem Prozess, also
genau der Lauf, der nach 22 Minuten nativ abreißt. Aufgefallen nach 52
Minuten an der Fortschrittsanzeige („40 %" mit Tausenden Punkten) und an
der Kommandozeile des Prozesses, in der die Testpfade fehlten.

**Why:** Die Kommandozeile im Prozess ist die einzige Stelle, die zeigt, was
wirklich läuft. Die Ausgabedatei sah bis dahin wie ein normaler Lauf aus.

**How to apply:** Parameter nie `$args` nennen (`$tests`, `$ziele`). Nach
dem Start eines abgekoppelten Laufs **einmal die Kommandozeile lesen**
(`Get-CimInstance Win32_Process … CommandLine`) und prüfen, dass die
Auswahl darin steht — bevor man wartet. Siehe
[[suite-abgekoppelt-per-pwsh-start-process]] und
[[eigenen-lauf-ueber-die-elternkette-beenden]].
