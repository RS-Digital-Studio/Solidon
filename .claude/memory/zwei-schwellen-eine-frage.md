---
name: zwei-schwellen-eine-frage
description: "Wenn zwei Konstanten dieselbe Ja-Nein-Frage entscheiden, liegt zwischen ihnen ein Bereich, in dem beide Antworten falsch sind — besonders wenn sie in verschiedenen Einheiten messen."
metadata:
  type: feedback
---

**Zwei Schwellen für eine Entscheidung ergeben drei Ergebnisse, nicht zwei.**
Am 23.08.2026 in Solidon: Ob ein Mausdruck ein Klick ist oder ein Zug, hing an
`CLICK_SLACK = 2` (Pixel) und `EPS_DRAG = 0.05` (Millimeter). Gemessen:

| Wackeln | Auswahl? | Zug? |
|---|---|---|
| 0–2 px | ja | ja, 0,3 mm — ungewollt |
| 3–9 px | **nein** | ja, 0,45 mm |
| ab 10 px | nein | ja |

Der mittlere Streifen verfehlte **beides**: keine Auswahl und ein
Verschiebeschritt im Verlauf. Drei Pixel Wandern sind beim Klicken normal, also
traf es jeden zweiten Klick. Robert meldete es als „wechseln wir auch nicht".

**Der Verstärker war die Einheit.** 0,05 mm entsprechen je nach Zoom einem
Drittel Pixel — die eine Schwelle wandert mit der Kamera, die andere nicht. Wer
zwei Zahlen in zwei Einheiten vergleicht, kann ihr Verhältnis nicht im Kopf
prüfen und merkt die Lücke nie beim Lesen.

**Why:** Jede der beiden Zahlen war für sich begründet und beide Kommentare
waren richtig — „eine Maus steht beim Drücken selten ganz still" stand seit
Monaten korrekt in der Datei. Der Fehler entsteht nicht in einer Konstante,
sondern **zwischen** ihnen, und dort sieht ihn kein Code-Review, weil man dafür
beide gleichzeitig ansehen muss.

**How to apply:**

1. **Eine Frage, eine Schwelle.** Führt kein Weg daran vorbei, leite die zweite
   aus der ersten ab, statt sie unabhängig zu setzen.
2. **Den Übergang messen, nicht die Enden.** Eine Tabelle über den ganzen
   Bereich (0, 1, 2, 3, 5, 20) zeigt den Sprung; zwei Tests an je einem Ende
   sind beide grün und sagen nichts über die Mitte.
3. **Beim Plattformwert nachsehen, bevor man selbst einen wählt.**
   `QApplication.startDragDistance()` sagt 10 — der Wert, den jedes andere
   Fenster benutzt. Wir hatten 2, und die Begründung dafür war eine Schätzung.
4. **Eine Schwelle in Weltmaß neben einer in Bildschirmmaß ist ein Warnzeichen.**
   Ihr Verhältnis hängt am Zoom, ist also nie fest.

Verwandt mit [[messwerkzeug-misst-sich-selbst]] und
[[eine-kette-endet-am-letzten-glied]].
