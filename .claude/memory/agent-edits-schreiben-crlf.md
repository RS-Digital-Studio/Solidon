---
name: agent-edits-schreiben-crlf
description: "Das Edit-Werkzeug eines Unteragenten stellte 23 LF-Dateien auf CRLF um — git normalisiert beim Commit, aber der Arbeitsbaum trägt danach fremde Zeilenenden; nach jedem Prosa-Durchgang git diff --stat auf CRLF-Warnungen lesen und zurückstellen"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c8bf1d70-6f46-4992-9b9e-5becddfdbd88
  modified: 2026-09-25T15:59:35.147Z
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
Siehe [[der-nachbar-findet-den-fehler]].

**Nachtrag 22.09.2026 — auch das eigene Patch-Skript tut es.** Ein Python-
Skript, das eine Datei mit `read_text` liest, ersetzt und mit `write_text`
zurückschreibt, wandelt unter Windows jedes LF in CRLF (`newline=None`
heißt `os.linesep`). Drei Dateien standen so vollständig auf CRLF, bevor
`git diff --stat` es sagte. Immer `write_text(..., newline="\n")`; zurück
geht es wie oben mit `data.replace(b"\r\n", b"\n")`. Und der Text dieses
Nachtrags selbst kam zweimal über ein Bash-Heredoc mit echten Zeilenumbrüchen
statt `\n` in den Backticks an — deutschen Text und Escape-Folgen schreibt das
Write-Werkzeug, nicht die Shell ([[heredoc-frisst-den-backslash]]).

**Zweiter Nachtrag 22.09.2026 — der Hauptbaum sammelt sie still an.** Vor der
Durchsicht 0.5.0 standen 309 Dateien mit `i/lf w/crlf` (`git ls-files --eol`),
und `git status` war trotzdem sauber: Die System-Gitconfig
(`C:/Program Files/Git/etc/gitconfig`) setzt `core.autocrlf=true`, und
`text=auto` normalisiert beim Vergleich. Frische Worktrees stehen dagegen auf
LF — ein Patch von dort passt nicht auf den CRLF-Hauptbaum. Umstellen: alle
Pfade mit `i/lf` und `w/crlf|w/mixed` byteweise auf LF. Danach zeigt
`git status` die 309 als `.M`, obwohl `git hash-object` gleich dem Index ist
und `git diff` leer — weder `update-index --refresh` noch `--really-refresh`
helfen; `git add --pathspec-from-file=<liste>` erneuert nur die Stat-Einträge
(gleiche Blobs, nichts gestaged), und der Baum ist sauber.

**Dritter Nachtrag 25.09.2026 — trotz dieser Notiz noch einmal.** Ein
Ersetzungsskript mit `path.write_text(text, encoding="utf-8")` stellte
`placement_flow.py` (4 900 Zeilen) auf CRLF; aufgefallen nur an der Warnung
von `git diff --stat`. Die Gewohnheit, die es nicht vergessen kann: **Bytes
lesen, Bytes schreiben** — `text = p.read_bytes().decode("utf-8")`, am Ende
`p.write_bytes(text.encode("utf-8"))` und einmal `text.count("\r")`
ausgeben. Dann trägt die Datei genau die Zeilenenden, die sie hatte.
