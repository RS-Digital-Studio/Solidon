---
name: commit-msg-hook-verlangt-echte-umlaute
description: ".githooks/commit-msg lehnt „ae/oe/ue/ss\" in Commit-Meldungen ab; Meldungen mit dem Write-Werkzeug in eine Datei schreiben und per -F übergeben, Heredocs übertragen Umlaute sauber"
metadata: 
  node_type: memory
  type: project
  originSessionId: f205bb02-89f3-41d7-a514-397ddd2fe07b
  modified: 2026-09-05T12:12:20.141Z
---

Der `commit-msg`-Hook dieses Projekts prüft die Meldung auf Ersatzschreibungen
(`fuer`, `ueber`, `liess`, `naechste` …) und bricht den Commit ab. Ein
Commit-Skript, das aus Vorsicht ASCII tippt, scheitert deshalb an jedem Commit,
der eine solche Silbe enthält (05.09.2026: 16 von 17 Commits eines Skripts).

**Why:** AGENTS.md verlangt echte Umlaute überall, auch in Meldungen; der Hook
setzt es durch. Bash-Heredocs und `printf` in einer per Write-Werkzeug
geschriebenen Skriptdatei übertragen Umlaute gemessen sauber.

**How to apply:** Commit-Meldungen immer mit echten Umlauten schreiben, Skripte
mit dem Write-Werkzeug anlegen (UTF-8), nie „zur Sicherheit" auf ASCII
ausweichen. Bei privatem Index (`GIT_INDEX_FILE`) außerdem: Ausgaben eines
Python-Helfers unter Windows enden auf `\r` — vor `git update-index
--cacheinfo` abstreifen, sonst heißt der Pfad `en.json?`.
