---
name: fortschrittszeichen-zaehlen-nicht-wie-collect
description: Die Position eines F im pytest-Fortschritt trifft nicht die gleiche Zeile aus --collect-only; die Zuordnung war falsch und entlastete den falschen Test.
metadata:
  node_type: memory
  type: feedback
  originSessionId: 60dfe3ed-7cce-4c68-a256-9db7aac288cb
  modified: 2026-08-31T11:45:04.810Z
---

Ein `F` im laufenden Protokoll sagt, dass ein Test rot ist, aber nicht welcher.
Die naheliegende Antwort — die n-te Zeile aus `pytest --collect-only -q` — ist
**nicht verlässlich**: Am 31.08.2026 stand das `F` an achter Stelle, die achte
gesammelte Zeile war `test_a_non_finite_parameter_...[nan]`, und rot war in
Wahrheit `test_the_display_unit_reaches_everything_that_shows_a_length`.

Der Schaden war nicht der Irrtum, sondern die **Entlastung**: Der falsch
benannte Test lief einzeln grün, und die zehn ersten in ihrer Reihenfolge auch.
Daraus wurde „nicht meins, vermutlich Fremdlast" — und die Meldung ging so an
zwei andere Sitzungen, von denen eine daraufhin nach dem falschen Test suchte.
Der echte war einzeln rot, in 1,7 Sekunden.

**Why:** Die Zählung fühlt sich wie eine Messung an. Sie ist aber eine
Übersetzung zwischen zwei Listen, deren Übereinstimmung niemand geprüft hat —
Parametrisierung, Sortier-Plugins und Sammelreihenfolge können sie verschieben.
Verwandt mit [[gemessene-frage-ist-nicht-die-gestellte]] und
[[eigener-messfehler-widerlegt-den-befund-nicht]]: Hier war es die Gegenrichtung,
eine falsche **Entwarnung** aus einer plausiblen Zahl.

**How to apply:** Auf den Namen warten, nicht ihn ausrechnen. Der Lauf schreibt
die `FAILED`-Zeilen in der Zusammenfassung, und die trägt den vollen Node-Namen.
Wer nicht warten will, fährt die Datei mit `-x` oder in Portionen, statt die
Position zu übersetzen. Und wenn die Übersetzung doch sein muss: Sie ist eine
Vermutung, und eine Entlastung darf nie auf ihr stehen.
