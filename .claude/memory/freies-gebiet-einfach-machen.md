---
name: freies-gebiet-einfach-machen
description: "Ist ein Gebiet oder eine Datei frei, wird nicht gefragt, sondern gemacht — auch CLAUDE.md, AGENTS.md und .claude/"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1aa9a73f-e260-47a2-9ee8-f8e112744402
  modified: 2026-08-22T15:02:19.297Z
---

Am 22.08.2026 hatte ich zwei fertige Änderungen zurückgehalten und Robert
vorgelegt, obwohl niemand die Dateien hielt: eine Zeile für die Fallenliste in
`CLAUDE.md` und eine Behebung in `.claude/.state/.../suite-getrennt.sh`,
nachdem die parallele Sitzung `solidon-c1` beendet war. Seine Antwort: „immer
machen wenn es frei ist."

**Warum:** Vorlegen ist nur dort richtig, wo jemand anders die Datei hält oder
wo eine Entscheidung fällt, die nicht meine ist. Eine freie Datei und ein
belegter Fund sind keine Entscheidung — das Vorlegen kostet einen Umlauf und
bringt nichts. Ich hatte die Hausordnungsdateien (`CLAUDE.md`, `AGENTS.md`,
`.claude/**`) für grundsätzlich vorlagepflichtig gehalten; das gilt nur, solange
eine andere Sitzung sie im Brett führt.

**How to apply:**

- **Frei heißt frei.** `python tools/session_board.py list` sagt, wer was hält.
  Steht die Datei bei niemandem, wird gearbeitet — auch `CLAUDE.md`, `AGENTS.md`
  und `.claude/**`.
- **Gefragt wird weiter bei echten Entscheidungen**: was gebaut wird, welcher
  von zwei Wegen, ob etwas in den Verkauf geht. Nicht bei einem Fund mit Beleg
  und einer freien Datei.
- **Endet eine Sitzung, wird ihr Gebiet frei** — nicht reserviert. Nach dem Ende
  von `solidon-c1` war `.claude/**` verfügbar, und ich habe trotzdem gewartet.
- Die Absprache mit laufenden Sitzungen bleibt unberührt: vorher sagen, privater
  Index, danach `git reset`. Siehe [[parallele-sitzung-im-arbeitsbaum]].
