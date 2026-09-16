---
name: zwei-wuensche-eine-taste-die-lage-entscheidet
description: "Robert meldete am 16.09.2026 morgens „Entf löscht den ganzen Körper\" (am Bausteindach) und abends „warum kann ich keinen Körper mehr löschen\" (an einer Fläche) — die Antwort ist nie ein Richtungswechsel, sondern eine Regel je Lage."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 337c8da1-518d-4c2c-9ac1-9020b4cc1a65
  modified: 2026-09-16T17:28:14.792Z
---

Dieselbe Taste, zwei Befunde in Gegenrichtung am selben Tag: Morgens nahm
Entf an einem gewählten Bausteindach still den ganzen Körper (Robert: „wird
der ganze körper gelöscht"). Der Fix ließ Entf an jedem Merkmal ohne eigene
Operation nichts mehr tun und verwies auf Escape. Abends am eingelesenen
Tray: „warum kann ich kein körper mehr löschen" — im Bild trifft ein Klick
immer eine Fläche, und ein Teil, das sich nicht löschen lässt, ist eine
Sackgasse.

**Why:** Der erste Fix hatte den Befund als Richtung gelesen („Entf soll nicht
den Körper nehmen") statt als Lage („an einem Baustein meint Entf den
Baustein"). Eine Regel, die nur die Richtung dreht, trifft am nächsten Ort
den nächsten Befund.

**How to apply:** Bei einem Befund an einer Taste oder Geste zuerst fragen,
**welche Lage** ihn ausgelöst hat, und die Regel je Lage schreiben: Baustein
→ sein Schritt; Merkmal mit Operation → sein Zwilling; Fläche oder Merkmal
ohne Handlung → der Körper, mit Ansage und Strg+Z (Regel 19). Den Test dazu
so benennen, dass er die Lage nennt (`test_delete_on_a_face_takes_the_body_and_says_so`
neben `test_delete_at_a_part_takes_its_step_and_never_the_body`). Siehe
[[regel-gilt-je-bedienort]] und [[beheben-statt-notieren]].
