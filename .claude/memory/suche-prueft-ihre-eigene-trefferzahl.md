---
name: suche-prueft-ihre-eigene-trefferzahl
description: "Ein Filter, der nichts trifft, und einer, der nichts findet, sehen gleich aus — und 265 Treffer sagen so wenig wie null. Die Trefferzahl ist die Kontrolle, nicht das Ergebnis."
metadata:
  type: feedback
---

Zwei Fälle vom 30.08.2026, dieselbe Wurzel:

**Der Filter, der die Frage nie gestellt hat.** Nach einer Änderung an
`list_top` sollte geprüft werden, ob sie Tests bricht:
`pytest -k "list_top or drop"` meldete **4 passed**. Der betroffene Test heißt
`test_a_list_in_the_bottom_bar_opens_upwards_when_it_has_to` und enthält keines
der beiden Wörter. Beinahe wäre „mein Fix bricht nichts" gemeldet worden —
gegen eine Auswahl, in der der gemeinte Test gar nicht war. Richtig gefahren
fiel er sofort.

**Die Suche, die zu viel fand.** Beim Verifizieren von Changelog-Punkten sollte
`pin` belegen, dass es Passstifte gibt: **265 Dateien**, darunter
`app/branding.py`. `auseinander` gab 116. Beide Zahlen bestätigen nichts —
erst `def .*pin|Passstift|dowel` in `app/core/geom/` zeigte den echten Ort
(`autosplit.py`).

**Why:** Beide Male beantwortet die Suche eine **andere** Frage als die
gestellte, und beide Male sieht das Ergebnis nach einer Antwort aus. Null
Treffer heißen „es gibt nichts" **oder** „mein Muster passt nicht". Sehr viele
Treffer heißen „es ist überall" **oder** „mein Muster ist zu weit". In beiden
Richtungen ist die Trefferzahl selbst die Information, nicht das, was man
sucht.

**How to apply:** Vor der Auswertung die **Zahl** ansehen und fragen, ob sie
plausibel ist. Bei `pytest -k` ist die Sammelzahl die Kontrolle: Prüft man, ob
eine Änderung etwas bricht, muss der gemeinte Test in der Auswahl sein — im
Zweifel die ganze Datei fahren, das kostet Sekunden. Bei einer Codesuche gilt
dasselbe von der anderen Seite: Drei Treffer sind ein Beleg, dreihundert sind
ein zu weites Muster.

Verwandt mit [[gemessene-frage-ist-nicht-die-gestellte]] (dort antwortet jede
Suche auf ihre eigene Frage) und [[messwerkzeug-misst-sich-selbst]]. Der
Unterschied: Dort täuscht das Werkzeug, hier täuscht seine **Ausbeute**.
