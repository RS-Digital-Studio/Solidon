---
name: uebersetzung-neu-statt-flicken
description: "Robert am 23.08.2026: einen Text neu übersetzen, wenn das sauberer ist als einen Zusatz an die alte Fassung zu hängen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a6e000e4-7f10-4e2d-92c3-c5df9b4a17cf
  modified: 2026-08-23T19:26:01.695Z
---

Roberts Worte: *„neu übersetzen wenn es sauberer ist merken."* Gesagt, als ich
einen ergänzten Handbuchabsatz an die vorhandenen fünf Übersetzungen anhängen
wollte, statt den Kapiteltext neu zu übersetzen.

**Why:** Ein Katalogschlüssel ist oft der **ganze** Text — ein Handbuchkapitel
sind 3000 Zeichen unter einem Schlüssel. Wer einen Absatz ergänzt, erzeugt
einen neuen Schlüssel und steht vor der Wahl: die alte Fassung kopieren und
den Zusatz anhängen, oder alles neu übersetzen. Bequemlichkeit darf das nicht
entscheiden.

**How to apply:**

- **Anhängen ist zulässig, wenn der Zusatz ein eigenständiger Absatz am Ende
  ist und die alte Fassung trägt.** Prüfen heißt: die alte Übersetzung
  ansehen, Absatzzahl und Ton vergleichen. Bei „Wenn etwas nicht geht" waren
  es elf Absätze in beiden Sprachen und ein guter Ton — dort war Anhängen
  richtig, und der neue Absatz wurde frisch übersetzt.
- **Neu übersetzen, sobald der Zusatz in den Text hineingreift** — mitten
  hinein, mit Bezug auf das Davor, oder wenn er die Aussage des Ganzen
  verschiebt. Ein geflickter Text liest sich wie zwei Handschriften.
- **Und immer neu, wenn die alte Fassung schwächer ist als das Deutsche.** Eine
  schlechte Übersetzung fortzuschreiben verlängert ihren Fehler.
- Der alte Schlüssel muss in jedem Fall **heraus** — `test_every_text_is_translated`
  prüft beide Richtungen und meldet ihn sonst als „no longer used".

Gehört zu [[aus-kundensicht-perfekt]]: Der Kunde liest den Text als Ganzes,
nicht als Diff.
