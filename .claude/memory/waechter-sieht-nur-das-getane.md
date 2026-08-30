---
name: waechter-sieht-nur-das-getane
description: "Ein Wächter, der nach einem Aufruf sucht, ist blind für das, was ohne Aufruf geschieht — Frameworks tun Dinge, die in keiner Zeile stehen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 60dfe3ed-7cce-4c68-a256-9db7aac288cb
  modified: 2026-08-30T18:16:46.936Z
---

Ein Quelltext-Wächter sucht nach dem, was jemand **geschrieben** hat. Er ist
damit blind für alles, was ein Framework **von selbst** tut — und das steht in
keiner Zeile, die man greppen könnte.

Am 30.08.2026 gemessen: `test_every_default_button_of_the_surface_goes_
through_make_primary` verbietet `setDefault(True)` außerhalb von `style.py`.
Er war seit je grün. Gleichzeitig trugen **neun von vierzehn** Dialogen einen
akzentuierten Hauptknopf ohne die halbfette Zweitkodierung — weil `QDialog`
beim ersten `show()` den ersten Knopf mit `autoDefault` selbst zum Default
macht. Es rief niemand `setDefault`. Der Wächter fand nichts, weil nichts
dastand, und genau darin lag der Fehler.

**Why:** Die Grundmenge war falsch gewählt. Gesucht wurde nach *explizitem
Tun*, gefährlich war *implizites Geschehen*. Das ist nicht „der Wächter zählt
falsch" (siehe [[waechter-zaehlt-das-falsche]]) und nicht „seine Reichweite
steht nur im Kommentar" (siehe [[waechter-reichweite-nur-im-kommentar]]) —
hier zählt er richtig, in einer Menge, die den Fall nicht enthalten kann.

**How to apply:** Bei jedem Wächter, der Quelltext liest, die Gegenfrage
stellen: **Kann der Zustand, den ich verbiete, auch ohne meinen Suchbegriff
entstehen?** Setzt das Framework Vorgaben (Default-Knopf, Fokusreihenfolge,
Elternschaft, implizite Konvertierung, automatische Verbindungen)? Dann
gehört ein zweiter Wächter daneben, der am **gebauten und angezeigten**
Objekt misst, und beide Docstrings zeigen aufeinander — getrennt gelegt liest
sie in einem Monat niemand mehr als Paar.

Der Beweis kam beim ersten Lauf: Der Fenster-Wächter fand sofort einen
zehnten Fall, den die Handmessung nicht bauen konnte (ein Dialog mit
Pflichtargument fiel aus dem Prüfstand). Verwandt mit
[[gemessene-frage-ist-nicht-die-gestellte]] und
[[qt-luegt-vor-dem-anzeigen]] — letzteres ist die Bedingung, unter der der
zweite Wächter überhaupt etwas sieht: `isDefault()` meldet vor dem `show()`
überall `False`.
