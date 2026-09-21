---
name: agentenberichte-sofort-sichern
description: "Der Schlussbericht eines Agenten steht nur im Gespräch; die Kompaktierung frisst ihn — sofort als Datei sichern, nicht als Kurzfassung"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7708995f-8153-4da1-9385-1fa5f014d252
  modified: 2026-09-21T22:55:40.749Z
---

Am 22.09.2026 lagen die Schlussberichte von sechs Fix-Paketen (je 12–27 KB,
mit Registersätzen, Katalogschlüsseln, offenen Wünschen) nur in der
Sitzung. Ich sicherte Kurzfassungen; nach der Kompaktierung fehlten genau
die Sätze, die ins Register mussten, und ich holte sie aus dem
Transkript-JSONL (`task-notification`-Zeilen mit `<result>`).

**Why:** Die Ausgabedatei unter `tasks/<id>.output` ist bei Inline-Berichten
0 Byte; der Bericht existiert nur im Gesprächsverlauf, und der wird gekürzt.

**How to apply:** Sobald ein Agent seinen Bericht abgibt, den Text
**vollständig** unter `scratchpad/<thema>-reports/<paket>.md` schreiben
(Write-Tool), dann erst die Kurzfassung. Falls verloren: das Transkript
`~/.claude/projects/<slug>/<sitzung>.jsonl` nach `<task-id>` durchsuchen.
Siehe [[parallele-reviewer-kollidieren-an-den-raendern]].
