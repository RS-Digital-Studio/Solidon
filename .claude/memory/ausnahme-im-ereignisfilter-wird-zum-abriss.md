---
name: ausnahme-im-ereignisfilter-wird-zum-abriss
description: "Ein Exit 139 mit Python-Stapel nur bis viewport.show() war keine Speicherverletzung, sondern ein AttributeError im eventFilter während des Anzeigens — PySide macht daraus einen Abriss ohne Traceback; mit sys.settrace den letzten Python-Aufruf davor finden, dann die Ausnahme selbst suchen"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-21T13:19:53.154Z
---

Gemessen am 21.09.2026: `test_placement_dimensions.py` riss im Release-Tor
dreizehn Portionen lang mit Exit 139 ab, `faulthandler` zeigte als letzten
Python-Rahmen `viewport.show()` — keine Zeile aus `app/`. Sieht aus wie ein
nativer Fehler in Qt. War es nicht: `git bisect` mit dem Einzeltest als
Sonde fand `102d4bf7`, und `sys.settrace` auf Aufrufe in `app/` zeigte den
letzten Aufruf vor dem Abriss in `PlacementFlow.redraw`, gerufen aus dem
`eventFilter` beim Show-Ereignis. Dort las der neue Code `self._prepared.edges`,
und der Testaufbau hatte `_surface` ohne `_prepared` gesetzt — ein
`AttributeError`. Aus dem Ereignisfilter heraus druckt PySide den nicht,
sondern reißt ab (mit einer künstlich geworfenen Ausnahme war es „nur" ein
Exit 1 mit vierfach verschachteltem „Error calling Python override" — der
Unterschied hing am Zeitpunkt mitten im Anzeigen).

**Why:** Ein Abriss mit einem Python-Stapel, der in Qt endet, verführt dazu,
in Qt oder im Speicher zu suchen. Die Ursache war eine gewöhnliche Ausnahme
an einer Stelle, an der PySide sie nicht mehr melden kann.

**How to apply:** Erst `git bisect` mit dem Einzeltest, dann `sys.settrace`
auf Aufrufe in `app/` bis zum Abriss — der letzte gedruckte Aufruf ist die
Stelle, die die Ausnahme wirft. Dann die Ausnahme beheben: hier den
Testaufbau auf das Paar `_prepared`/`_surface` stellen, wie `at_point` es
der Anwendung liefert. Siehe [[speicherriss-hat-keine-ausloesende-zeile]]
und [[sonde-baut-das-fenster-wie-die-anwendung]].
