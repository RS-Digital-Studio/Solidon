---
name: git-identitaet-mitgeben
description: "Solidon hat keine Git-Identität konfiguriert — Commits brauchen Autor und E-Mail als -c Flags, sonst bricht git commit mit Exit 128 ab"
metadata: 
  node_type: memory
  type: project
  originSessionId: 58b322ef-8793-4b10-becc-8f7c904e69c8
  modified: 2026-08-21T14:48:45.589Z
---

`git commit` scheitert in Solidon mit „Author identity unknown" (Exit 128):
Weder lokal noch global ist `user.name`/`user.email` gesetzt. Die Identität wird
je Aufruf mitgegeben, nicht konfiguriert. Ältere Commits tragen `Claude
<noreply@anthropic.com>`, seit dem 21.08.2026 `Robert Schneider
<robert.schneider@kummert.de>` — vor dem Commit `git log -3 --format="%an <%ae>"`
lesen und den Bestand fortsetzen.

**So anwenden:**

```
git -c user.name=Claude -c user.email=noreply@anthropic.com commit -F <datei>
```

Die Meldung über `-F` aus einer Datei statt über `-m`: Umlaute und typografische
Anführungszeichen überleben den Weg über stdin nicht zuverlässig, und die
Commit-Meldungen dieses Projekts sind deutsche Sätze mit echten Umlauten. Die
Datei mit dem Write-Werkzeug schreiben, nicht per Heredoc.

**Und nicht mit `Out-File -Encoding utf8` schreiben.** PowerShell 5.1 setzt
dabei ein BOM an den Anfang, und `-F` nimmt es wörtlich: Die Betreffzeile des
Commits beginnt dann mit einem unsichtbaren U+FEFF (`git log --oneline` zeigt
`﻿Sechsundfünfzig …`). Passiert am 21.08.2026 in 31ed7c3, geheilt durch ein
neues `commit-tree` auf denselben Baum. Prüfen lässt es sich mit
`git log -1 --format=%s | python -c "import sys; print(repr(sys.stdin.read()))"`.

Nicht selbst konfigurieren — dass die Identität je Aufruf kommt, ist offenbar
Absicht der Umgebung. Siehe [[parallele-sitzung-im-arbeitsbaum]].
