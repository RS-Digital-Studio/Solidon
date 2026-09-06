---
name: agent-edits-schreiben-crlf
description: "Das Edit-Werkzeug eines Unteragenten stellte 23 LF-Dateien auf CRLF um — git normalisiert beim Commit, aber der Arbeitsbaum trägt danach fremde Zeilenenden; nach jedem Prosa-Durchgang git diff --stat auf CRLF-Warnungen lesen und zurückstellen"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c8bf1d70-6f46-4992-9b9e-5becddfdbd88
  modified: 2026-09-06T13:28:20.446Z
---

Am 06.09.2026 schrieb ein Unteragent Docstrings und Kommentare in 35
Dateien um, nur Prosa, alles grün. `git diff --stat` warnte danach bei 23
Dateien „CRLF will be replaced by LF“: Das Edit-Werkzeug hatte die ganzen
Dateien mit CRLF zurückgeschrieben, obwohl HEAD sie mit LF führt. Im
Repository wäre nichts passiert (`text=auto` normalisiert beim Commit), aber
im geteilten Arbeitsbaum hätten andere Sitzungen und Werkzeuge fremde
Zeilenenden vorgefunden.

**Why:** Die Warnung ist die einzige Spur; `ruff`, `pytest` und der
AST-Vergleich sehen Zeilenenden nicht, und ein Diff zeigt nur die echten
Änderungen.

**How to apply:** Nach jedem Durchgang eines Unteragenten `git diff --stat`
lesen und jede CRLF-Warnung ernst nehmen; zurückstellen mit einem kleinen
Skript, das nur Dateien anfasst, deren HEAD-Stand kein CR trägt
(`data.replace(b"\r\n", b"\n")`). Die Prosa selbst prüft ein AST-Vergleich
(Docstrings entfernt) gegen HEAD: „nur Prosa“ oder „Code geändert“ je Datei.
Siehe [[der-nachbar-findet-den-fehler]], [[parallele-sitzung-im-arbeitsbaum]].
