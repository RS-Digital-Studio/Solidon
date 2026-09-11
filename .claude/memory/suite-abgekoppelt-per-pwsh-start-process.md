---
name: suite-abgekoppelt-per-pwsh-start-process
description: "Wie das geteilte Tor die Sitzung überlebt: pwsh -File <skript.ps1> über Start-Process -WindowStyle Hidden, darin Git-Bash mit vollem Pfad, Ausgabe und Exit in Dateien; `bash` ohne Pfad trifft in pwsh WSL und schreibt nichts"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 9445bc01-20af-4b3c-9e8f-c80a1769a381
  modified: 2026-09-11T15:34:38.485Z
---

Gemessen am 11.09.2026: Ein mit `run_in_background` gestartetes
`suite-getrennt.sh` starb mit dem Neuaufsetzen der Sitzung; die gekillte
Kette schrieb dazu noch Stunden in ihre alte Datei weiter
([[gekillter-lauf-schreibt-weiter]]). Was hält:

```
Set-Location 'F:\3D Druck'
$env:PYTHONUTF8 = '1'
& 'C:\Program Files\Git\bin\bash.exe' .claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh > '<scratch>\suiteN.txt' 2>&1
"Exit: $LASTEXITCODE" | Out-File '<scratch>\suiteN-exit.txt'
```

als `suiteN.ps1` im Scratchpad, gestartet mit
`Start-Process pwsh -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File",$skript -WindowStyle Hidden -PassThru`.
Die Prozesskennung merken; **beenden** heißt Wurzel zuerst, dann alle
Nachkommen (`Win32_Process` nach `ParentProcessId` durchgehen), sonst läuft die
Kette weiter ([[kette-mit-semikolon-laeuft-nach-dem-kill-weiter]]).

**Why:** Der erste Versuch mit `-Command` und nacktem `bash` schrieb eine
leere Exit-Datei und keine Ausgabe — in einer pwsh ohne Profil ist `bash` das
WSL-Bash aus System32, das ohne Distribution sofort endet. Der volle Pfad zur
Git-Bash ist der Unterschied.

**How to apply:** Fertig heißt `suiteN-exit.txt` existiert und ist nicht leer;
dann `grep -E "Läufe mit Fehler|^FAILED" suiteN.txt`. Warten über einen
Hintergrund-Bash mit `until [ -s exit-datei ]; do sleep 5; done`, nicht durch
Polling im Vordergrund. Vor dem Start prüfen, ob noch eine ältere Kette läuft
— zwei Suiten gleichzeitig messen beide unter Fremdlast
([[leistungstests-fremdlast]]).
