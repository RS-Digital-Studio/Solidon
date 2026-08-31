---
name: bestaetigung-verstaerkt-die-fehlannahme
description: Zwei unabhängige Messungen derselben falschen Frage lesen sich wie Bestätigung — die Übereinstimmung prüft die Frage nicht mit
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5f85192a-8b20-4339-ba08-13913837d58c
  modified: 2026-08-31T05:40:36.994Z
---

Am 31.08.2026 meldete eine Sitzung „39 Elemente warten unsichtbar auf ihre
Einblendung — das könnte Roberts *zu leer* erklären". Ich habe nachgemessen,
**43** gefunden und geschrieben: *„Dein Befund ist bestätigt, und die Zahl ist
höher als deine."*

Beide Zahlen waren richtig. Beide Werkzeuge waren in Ordnung. Und beide
antworteten auf die falsche Frage: Gezählt wurde „wie viele Elemente sind
gerade unsichtbar", gemeint war „wie viele bleiben unsichtbar, obwohl sie
sichtbar sein sollten". Die gezählten lagen **außerhalb des Blickfelds** —
dass sie dort auf `opacity 0` stehen, ist die Lazy-Reveal-Mechanik und nicht
ihr Fehler. Bei `scrollY = 0` sind es drei, und alle drei sind SVG in einer
Dauerschleife.

**Why:** Die Übereinstimmung war der Verstärker. Eine Einzelbeobachtung hätte
jemand hinterfragt; zwei unabhängige Messungen in derselben Größenordnung
lesen sich als Beleg. Wir haben aber nicht unabhängig **gemessen**, sondern
unabhängig **dieselbe Fehlannahme** gemessen — und meine Bestätigung hat ihr
das Gewicht gegeben, das sie allein nicht hatte.

Das unterscheidet den Fall von einem Werkzeugfehler: Dort antwortet das
Werkzeug falsch, und man kann es reparieren. Hier gibt es nichts zu
reparieren, kein Muster zu schärfen, keinen Wächter zu bauen — nur die Frage,
die vorher zu stellen war.

**How to apply:** Wer eine fremde Zahl nachmisst, prüft zuerst die **Frage**
und dann die Zahl. Und wer bestätigt, sagt dazu, was er *nicht* geprüft hat —
„43 gezählt, die Folgerung daraus nicht geprüft" ist ehrlicher als „bestätigt".

Der Griff, der es hier aufgelöst hat, war kein Nachmessen, sondern ein Satz:
**„Dein Beleg wackelt"** statt einer eigenen Gegenmessung. Das lässt den
Urheber die richtige Frage stellen, statt ihn eine fremde Antwort prüfen zu
lassen — und er kennt seine Sache besser.

Verwandt: [[gemessene-frage-ist-nicht-die-gestellte]] (dieselbe Wurzel, ohne
den Verstärker durch Bestätigung) und
[[voraussetzung-im-namen-statt-hergestellt]].
