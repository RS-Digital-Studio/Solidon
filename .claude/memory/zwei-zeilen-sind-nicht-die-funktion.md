---
name: zwei-zeilen-sind-nicht-die-funktion
description: "Ein Wächter meldet Zeilen; ob es ein Fehlalarm ist, entscheidet die Funktion, in der sie stehen"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5f85192a-8b20-4339-ba08-13913837d58c
  modified: 2026-08-30T21:30:20.769Z
---

Ein Testfehler nennt eine oder zwei Zeilen. Wer daraus „Fehlalarm" schließt,
hat die **Zeilen** gelesen und nicht die **Funktion** — und die Zeilen allein
sagen nie, was mit ihrem Ergebnis geschieht.

Am 30.08.2026 meldete `test_no_number_reaches_the_user_past_the_localisation`
zwei f-Strings in `panels.py`. Beide standen in `metrics.horizontalAdvance(...)`,
also in einer Breitenmessung — kein Text, der beim Kunden landet. Ich meldete
es als Fehlalarm, zwei weitere Sitzungen stimmten zu. Dann las eine die
Funktion zu Ende:

```python
widest = max(metrics.horizontalAdvance(f"{spin.minimum():.…f}"), …)  # Punkt
frame  = max(0, spin.sizeHint().width() - widest)
return metrics.horizontalAdvance(spin.text() + "0") + frame          # lokalisiert
```

Die Messung wird mit einer zweiten verrechnet, und die trägt ein anderes
Trennzeichen. Kein Fehlalarm.

**Why:** Der Unterschied zwischen „ich habe die gemeldeten Zeilen geprüft" und
„ich habe die Sache geprüft" verschwindet in der Meldung, wenn man ihn nicht
selbst hinschreibt. Drei Sitzungen haben derselben Verkürzung zugestimmt, weil
sie plausibel klang.

Die schönere Hälfte des Ausgangs gehört dazu: Die **Wirkung** war gemessen
null — Punkt und Komma sind in der Standardschrift gleich breit. Der Befund
war trotzdem echt, und die Zeile wurde geändert, weil die Rechnung von dieser
Gleichheit nicht abhängen soll. Ein Fehlalarm wäre er auch dann nicht gewesen.

**How to apply:** Vor einem „Fehlalarm" die ganze Funktion lesen, besonders
was mit dem Rückgabewert geschieht. Und wenn nur die gemeldeten Zeilen geprüft
sind, gehört genau das in die Meldung — die Grenze der eigenen Messung ist
Teil des Ergebnisses. Verwandt: [[messung-traegt-nur-am-ort-ihrer-messung]] und
[[benannte-falle-schuetzt-nicht]].
