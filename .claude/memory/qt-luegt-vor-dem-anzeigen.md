---
name: qt-luegt-vor-dem-anzeigen
description: setExpanded, isVisible und hasFocus antworten falsch, solange nichts angezeigt ist — ein Test darüber ist grün gegen eine Rechnung, die nie läuft
metadata:
  type: project
---

Qt beantwortet Zustandsfragen erst, wenn es etwas anzuzeigen gibt. Vorher
antwortet es nicht „weiß nicht", sondern **falsch** — und zwar immer mit dem
harmlos aussehenden Wert.

Drei Fälle derselben Familie, alle in diesem Projekt zugeschnappt:

| Frage | lügt, solange | meldet dann |
|---|---|---|
| `item.isExpanded()` | das Item in **keinem** `QTreeWidget` hängt | immer `False` |
| `widget.isVisible()` | das Fenster nie gezeigt wurde (offscreen) | immer `False` |
| `widget.hasFocus()` | das Fenster nie aktiviert wurde | immer `False` |

Der `setExpanded`-Fall kam am 25.08.2026 dazu, beim Test für `_visible_rows`
(Objektbaum über drei Ebenen). Der erste Entwurf baute die Knoten frei:

```python
body = QTreeWidgetItem(["Körper"])
group = QTreeWidgetItem(["Einhänger"])
body.addChild(group)
body.setExpanded(True)  # wirkungslos — body hängt in keinem Baum
group.setExpanded(True)
```

`_visible_rows(body)` gab **1** statt 8 zurück. Nicht weil die Rechnung falsch
war, sondern weil `isExpanded()` an einem freien Item immer `False` meldet: Der
rekursive Zweig lief kein einziges Mal. Ein `QTreeWidget` genügt, gezeigt
werden muss es nicht:

```python
tree = QTreeWidget()
tree.addTopLevelItem(body)  # ab hier wirkt setExpanded
```

**Why:** Der Fehler geht in die gefährliche Richtung. Hätte die Rechnung
zufällig auch ohne Rekursion gestimmt — etwa weil der Testbaum flach ist —,
wäre der Test **grün** gewesen und hätte eine Zusicherung über Code
abgegeben, der in ihm nie läuft. Genau das ist bei `_rows()` vorher passiert:
Der bestehende Höhentest baute lauter Körper ohne Kinder und konnte den
Ebenenfehler deshalb nie sehen. Ein Verbotstest über eine leere Menge ist
immer grün — hier ist es ein Zweig statt einer Menge, aber es ist dasselbe.

**How to apply:** Wer einen Qt-Zustand abfragt, fragt zuerst, **woran** dieser
Zustand hängt: `isExpanded` an der Zugehörigkeit zu einem View, `isVisible` und
`hasFocus` am gezeigten und aktiven Fenster. Im Zweifel die *Wirkung* prüfen
statt den Zustand — kommt die Ziffer im Feld an, zählt die Rechnung die
Zeilen — oder die Bedingung herstellen, die die Frage überhaupt beantwortbar
macht. Und immer die Gegenprobe fahren: Ein Test, der auch ohne den Fix grün
bleibt, prüft etwas anderes als er behauptet ([[was-die-suite-nicht-findet]],
[[messwerkzeug-misst-sich-selbst]]).

Verwandt: [[gesetzt-heisst-nicht-gezeigt]] — dort geht es um Texte, die gesetzt
sind und trotzdem nie erscheinen; hier um Zustände, die abgefragt werden und
trotzdem nie stimmen. Beide Male ist der Wert im Speicher richtig und die
Aussage über das Fenster falsch.
