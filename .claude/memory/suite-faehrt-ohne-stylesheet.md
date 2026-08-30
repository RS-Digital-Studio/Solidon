---
name: suite-faehrt-ohne-stylesheet
description: Kein Fixture setzt Thema und Stylesheet — jeder farbmessende Test misst Windows, bis er die Betriebslage selbst herstellt
metadata:
  type: feedback
---

`apply_theme` und `apply_style` stehen in `app.py` und in **keiner** Fixture.
Ein Test, der eine Farbe, eine Einrückung oder eine Rahmenbreite misst, misst
deshalb den Windows-Standard, solange er die Betriebslage nicht selbst
herstellt — drei Zeilen, und die letzte gehört ins `finally`:

```
before = QApplication.instance().styleSheet()
apply_theme(QApplication.instance(), "dark")
apply_style(QApplication.instance(), "dark")
...
QApplication.instance().setStyleSheet(before)
```

**Why:** Am 30.08.2026 ist derselbe Fehler vier Sitzungen an vier Stellen
begegnet. Der teuerste Fall war **grün**: `test_the_open_tool_keeps_its_symbol_
readable` verglich ein Symbol, das ohne Thema schwarz herauskam, mit
`palette().highlight()`, das ohne Thema der Systemakzent ist — zwei Farben, die
es in der Anwendung nicht gibt, und ihr Verhältnis lag zufällig über der
geforderten Schwelle. Zwei falsche Werte, deren Verhältnis stimmt, sind von zwei
richtigen nicht zu unterscheiden. Daneben: eine Menü-Einrückung, die in jedem
Menü dieselbe 0 maß, und `isDefault()`, das vor `show()` überall `False` meldet
und neun von vierzehn Dialogen verdeckte.

**How to apply:** Vor jeder Messung an Farbe, Kontrast, Einrückung oder
Knopfzustand die Betriebslage herstellen und hinterher zurückstellen. Die
Gegenprobe entscheidet, ob es nötig war ([[gemessene-frage-ist-nicht-die-gestellte]]):
Macht das Entfernen der drei Zeilen nichts rot, hingen sie an nichts.
**Ausgenommen ist, was an der Schriftmetrik hängt** — offscreen gibt es keine
Schrift, und Breiten sind dort gar nicht messbar. Farben lassen sich herstellen,
Breiten nicht. Verwandt: [[qt-luegt-vor-dem-anzeigen]] (dieselbe Familie, andere
Ursache — dort fehlt das `show()`, hier das Thema).
