---
name: naht-nicht-schneiden-sondern-waehlen
description: "Ein Feld, das einmal um einen Zylinder reicht, wird an der Naht nicht geschnitten, sondern je Zelle einmal gewählt — zwei an ±π·R getrennte Hälften, aufeinandergebogen, verschweißt die Boolesche Rechnung nicht zuverlässig, und die Teilung muss vorher im Umfang aufgehen"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-22T18:30:00.000Z
---

Gemessen am 22.09.2026 an `geom/texture_ops.py`, Wabenmuster um Ø 30 mit
Breite gleich Umfang: Die Zellen wurden am Feldrand bei ``±π·R`` halbiert,
die Hälften lagen nach dem Biegen exakt aufeinander — und die Differenz
ließ zwischen ihnen eine Haut von 16 mm² stehen, die den Stift in zwei
teilte. Davor, ohne gerückte Teilung, überlagerten sich an der Naht zwei
versetzte Spalten zu Klumpen, die keine Zelle mehr waren: die Erkennung
ließ sie aus, das Entfernen ließ sie stehen (62 mm² in einem Streifen).

Gelöst in zwei Schritten: `wrap_pitch` rückt die Teilung auf den nächsten
Teiler des Umfangs (31 statt 31,4 Perioden), und `_one_turn` zeichnet das
Feld über mehr als eine Runde und behält jede Zelle **ganz**, deren Mitte
in einem Fenster von einer Umfangslänge liegt — auch die über dem
Fensterende, denn ihr Gegenstück am anderen Ende fällt heraus. Die
Fensterkanten liegen eine Viertelperiode neben einer Zellmitte, damit keine
Mitte auf eine Kante fällt. Dasselbe beim Neuzeichnen eines gelesenen
Musters: der Umriss gilt periodisch (drei Kopien), und die Dreiecke des
Trägers über der Naht zählen auf beiden Seiten des Blatts — sonst fehlte
dem Umriss 0,64 mm vor der Naht, und der Steg darüber hatte ein Loch.

**Why:** Zwei Körper, die sich in einer Fläche berühren, sind für eine
Boolesche Rechnung ein Sonderfall, und der geht nicht immer gut. Was nicht
geschnitten wurde, muss nicht verschweißt werden. Und eine Naht, die nicht
aufgeht, ist kein Rundungsfehler, sondern eine Teilung, die nicht in den
Umfang passt — das entscheidet man, bevor man zeichnet.

**How to apply:** Wo etwas periodisch um eine Achse läuft, zuerst die
Periode zum Teiler des Umfangs machen und es dem Nutzer sagen; dann über
eine Runde hinaus erzeugen und je Element einmal wählen, statt am Ende zu
schneiden. Beim Zurückbiegen liegt jedes Stück von selbst, wo sein
Gegenstück gelegen hätte. Siehe [[buendig-heisst-buendig-mit-dem-netz]].
