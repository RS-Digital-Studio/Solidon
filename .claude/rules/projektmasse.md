---
description: "Feste Zahlen an Projektmaße binden — vorschlagen, nie still binden; eine Transaktion; Rechtecke einer Zeichnung behalten ihre Form; die Suche bleibt billig"
paths:
  - "app/core/scene/parameter_binding.py"
  - "app/ui/binding_dialog.py"
---

# Regeln für gebundene Projektmaße

Ein Projektmaß wirkt nur dort, wo ein Schritt es liest (Dateiaudit §4,
RM-184). `scene/parameter_binding.py` findet feste Zahlen, die genau zu Maßen
passen, `ui/binding_dialog.py` lässt wählen, `History.bind_parameters`
schreibt.

- **Die Zahl steht am Knopf, nicht unter dem Maß** (RM-519): Die
  Parameterkarte zeigt unter einer Zeile nur „Nicht verwendet“; wie viele feste
  Zahlen passen, sagt der Bindeknopf (`panels.binding_button_text`), wo sie
  stehen, die Kurzhilfe der Zeile. Ein Hinweis unter jedem wirkenden Maß las
  sich wie die Überschrift der nächsten Zeile.
- **Gebunden wird nur, was der Kunde wählt** (Regel 21): Dieselbe Zahl kann
  aus zwei Maßen kommen, und eine zufällig gleiche Zahl ist keine Absicht.
  Vorgewählt ist nur `BindingSpot.certain` — eine Größe, und genau ein Maß
  hat dieselbe Zahl. Eine Hälfte oder ein Doppeltes daneben zweifelt sie nicht
  an, ein zweites gleich großes Maß schon. **Eine Lage steht nie vor**:
  Größe heißt, das Schema lässt nichts unter null zu; x, y, z und Versätze
  fallen zu leicht auf ein Maß (Tür bei z = 30, Fenster 30 breit).
- **Der einfachste Ausdruck zuerst**: ein Maß vor zweien, zwei nur, wenn
  eines allein nicht reicht, höchstens `MOST_CHOICES`. `MATCH` ist die
  Rundung einer gespeicherten Zahl, keine Fertigungstoleranz.
- **Alle gewählten Stellen sind eine Transaktion** (`_swap_operations`,
  Regel 16): Kennung, Platz, Ein- und Ausgänge bleiben, geprüft wird vor dem
  ersten Schreiben, ein Strg+Z nimmt alles zurück.
- **In Zeichnungen nur achsparallele Rechtecke um den Ursprung, deren Linien
  frei sind**: Wer schon gemaßt hat, hat bestimmt. Gebunden bekommt ein
  Rechteck gedeckte Ecken, Waagerecht, Senkrecht und die Mitte auf einem
  festen Hilfspunkt im Ursprung, sonst verzieht der Löser es beim neuen Maß;
  der Hilfspunkt kommt hinten an, damit keine Nummer wandert.
- **Die Suche läuft nach jeder Auswertung im Arbeiter**
  (`EvaluationResult.binding_spots`): über sortierte Terme (`_Index`), nicht
  über alle Paare mit allen Faktoren — dieselben Treffer in derselben Folge
  wie die volle Suche, gehalten von
  `test_the_sorted_search_finds_what_the_full_search_finds`.
