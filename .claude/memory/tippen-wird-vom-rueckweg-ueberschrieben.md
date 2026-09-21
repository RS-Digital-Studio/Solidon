---
name: tippen-wird-vom-rueckweg-ueberschrieben
description: "Ein Feld, dessen Wert je Tastendruck in einen Entwurf geht, der synchron formatiert zurückschreibt, verzehnfacht die Eingabe („8,00“ → „8,00,00 mm“ → 800); offscreen verrät weder Fokus noch isModified den Tipper — nur der Aufrufer weiß, dass er liest"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-21T10:15:05.681Z
---

Gemessen am 21.09.2026 an der Maßgruppe der Bohrung: `QTest.keyClicks` tippte
„8,00“ in ein `LengthSpin` mit `keyboardTracking`; nach der „8“ feuerte
`valueChanged`, der Entwurf nahm den Wert und schrieb ihn über zwei Rückwege
(`_refresh_measure_fields` und `take_values`) formatiert als „8,00 mm“ zurück,
mit dem Cursor nach der 8 — das Komma und die Nullen landeten mitten im
formatierten Text. Zehn Fenstertests rot, je nach Feld 570 oder 800 mm.

Drei Wächter, die **nicht** griffen, alle gemessen: `editor.hasFocus()` ist
am Drehfeld falsch, weil das Zeilenfeld darin den Fokus hat;
`QApplication.focusWidget()` ist offscreen ohne aktives Fenster `None`;
`lineEdit().isModified()` bleibt nach `QTest` falsch — und wo es wahr war,
sperrte es umgekehrt jeden Zug am Griff, denn Qt setzt es nie zurück.

**Why:** Die Frage „tippt hier gerade jemand?“ lässt sich am Widget nicht
verlässlich stellen. Verlässlich weiß es nur der Aufrufer: `read_fields` läuft
wegen eines Tastendrucks, und in dieser Kette darf niemand zurückschreiben.

**How to apply:** Eine Sperre um das Lesen (`reading["fields"]` in
`_place_from_feature_panel`), die beide Rückwege abfragen. Fokus als zweite
Sicherung, `isModified` nie. Wer einen neuen Rückweg in dieselben Felder baut,
hängt ihn an dieselbe Sperre. Und im Test die Zahl mit dem Dezimalzeichen der
Sprache tippen (`QLocale().toString(wert, "f", 2)`), denn `str(5.7)` liefert
den Punkt. Siehe [[eingestellter-wert-ist-nicht-das-ergebnis]].
