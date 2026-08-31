---
name: eingestellter-wert-ist-nicht-das-ergebnis
description: "Was man einstellt, beschreibt die Regel; was herauskommt, ist das Ergebnis — und der Weg dazwischen ist selten eins zu eins."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 60dfe3ed-7cce-4c68-a256-9db7aac288cb
  modified: 2026-08-31T09:41:37.417Z
---

Wer eine Regel setzt und ihren eigenen Wert zurückliest, hat **die Regel**
geprüft und nicht ihre Wirkung. Gemessen wird, was herauskommt.

Am 31.08.2026 in drei Umgebungen an einem Tag, zwei Sitzungen:

* **CSS-Einheit.** `max-width: 70ch` heißt nicht siebzig Zeichen je Zeile:
  Ein `ch` ist die Breite der Ziffer Null, echte Buchstaben sind schmaler.
  Gemessen ergaben 70 ch auf Deutsch 72 Zeichen, auf Französisch 78, auf
  Italienisch 83 — und **weil der Aufschlag nicht konstant ist**, kann man
  von der Regel nicht auf das Ergebnis schließen.
* **Kaskadenwert.** `getComputedStyle` gibt, was die Kaskade errechnet hat,
  nicht was auf dem Schirm steht: Nach einer abgelaufenen Animation stand dort
  `opacity: 0`, während das Bild alles zeigte.
* **Zeichenkette.** `'<a href=…>' in label.text()` bleibt wahr, wenn die
  Darstellung kaputt ist — in einem PlainText-Label steht das Markup im
  String und wird als spitze Klammer angezeigt.
* Und im ausgelieferten Code: eine Schwelle, die den Anteil des **Eingangs**
  maß, wo der Abstand zum **Ziel** gemeint war.

**Why:** Der eingestellte Wert ist immer greifbar, das Ergebnis kostet einen
Schritt mehr — und beide sehen als Zahl gleich aus. Verwandt mit
[[text-gesetzt-heisst-nicht-gezeigt]] (dort Qt-spezifisch) und
[[am-eingang-drehen]]: Wer am Eingang dreht und das Ergebnis beobachtet,
prüft genau diese Kette.

**How to apply:** Nach dem Setzen einer Regel das Ergebnis in seiner eigenen
Einheit messen — Zeichen je Zeile, nicht `ch`; das gerenderte Bild, nicht den
Kaskadenwert; die angezeigte Zeile, nicht den String. Für eine Grenze ist
dabei nicht der Mittelwert die interessante Zahl, sondern der **Extremwert**:
Er kippt zuerst. Und wo mehrere Sprachen dieselbe Regel tragen, wird an der
längsten gemessen — sonst ist die Marke für die anderen zu weit.
