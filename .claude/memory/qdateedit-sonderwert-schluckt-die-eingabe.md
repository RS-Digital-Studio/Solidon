---
name: qdateedit-sonderwert-schluckt-die-eingabe
description: "Ein QDateEdit auf seinem Sonderwert („Unbekannt“) hängt getippte Ziffern an den Text an und behält das Minimum; und ein vor dem Monat getippter Tag wird am aktuellen Monat gekappt (31.12. → 30.12.). Erst ein echtes Startdatum (1. Januar), dann tippen."
metadata: 
  node_type: memory
  type: project
  originSessionId: 30dcb733-80d9-4e45-9aed-0d6e20865d98
  modified: 2026-09-19T18:00:52.899Z
---

Gemessen am 19.09.2026 am Kalenderfeld des Spulendialogs (`DateField` in
`app/ui/labels.py`): `QTest.keyClicks(editor, "05092026")` auf einem
`QDateEdit` mit `setSpecialValueText("Unbekannt")` am Minimum ergab den Text
„Unbekannt05092026“ und das Datum 1970-01-01 — Qt hat im Sonderwert keine
Abschnitte, in die es tippen könnte. Von einem echten Datum aus tippt sich das
Feld richtig und springt nach zwei Ziffern weiter; ein getippter Punkt
zwischen den Abschnitten landet aber als Zeichen im Abschnitt, und „31.12.2024“
wurde 30.12.2024, weil der Tag vor dem Monat kommt und der September nur
dreißig Tage hat.

**Why:** Ein Feld, das „Unbekannt“ zeigt und Tippen verspricht, muss beim ersten
Zeichen selbst ein Datum setzen — und zwar eines, das jeden Tag annimmt.

**How to apply:** `keyPressEvent` überschreiben: erste Ziffer am Sonderwert →
`setDate(QDate(jahr, 1, 1))`, ersten Abschnitt wählen, dann weiterreichen;
Trennzeichen (`. , / -`) → Abschnitt wechseln, außer die zwei Ziffern davor
sind schon von selbst gesprungen (Merker), sonst springt es doppelt;
vor dem Wechsel `interpretText()`, damit eine einzelne Ziffer nicht verfällt.
Immer mit `QTest.keyClicks` in drei Sprachen nachmessen — `dd.MM.yyyy`,
`M/d/yyyy`, `dd/MM/yyyy` —, nicht mit `setDate`. Siehe auch
[[kalenderdatum-folgt-appsprache]].
