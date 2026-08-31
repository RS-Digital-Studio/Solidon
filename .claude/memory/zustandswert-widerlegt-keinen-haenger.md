---
name: zustandswert-widerlegt-keinen-haenger
description: "Kumulierte CPU-Zeit, Speicher, Handles sehen bei einem stehenden Prozess aus wie bei einem arbeitenden — nur eine Differenz zweier Messungen trennt beide."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5f85192a-8b20-4339-ba08-13913837d58c
  modified: 2026-08-31T09:51:45.655Z
---

Am 31.08.2026 hing ein Lauf am gebauten Fenster. Auf den Hinweis einer
anderen Sitzung, die Maschine sei in einem Treiber-Klemmzustand, habe ich die
Prozessliste gelesen und geantwortet:

> „Der Lauf lebt und rechnet: **381 CPU-Sekunden**, 286 MB — er hängt nicht,
> er arbeitet."

Die Zahl stimmte und bewies nichts. **CPU-Zeit ist kumulativ**: Ein Prozess,
der elf Minuten lang gerechnet und dann stehengeblieben ist, zeigt dieselben
381 Sekunden wie einer, der weiterrechnet. Zwei Messungen im Abstand von zwei
Sekunden hätten es entschieden — der Zuwachs war null.

Die Maschine baute seit zwei Stunden kein VTK-Fenster mehr; der Lauf konnte
nie fertig werden. Bewiesen hat das eine andere Sitzung mit drei Zeilen:
`QApplication → QtInteractor → vtkRenderWindow()`, ohne eine Zeile
Projektcode.

**Why:** Alle bequemen Prozesskennzahlen sind kumulativ oder träge — CPU-Zeit,
Handles, Speicher, Dateigröße, Zeilenzahl einer Ausgabedatei. Jede einzelne
davon sieht bei einem stehenden Prozess genauso aus wie bei einem arbeitenden.
Das Auge sucht aber eine große Zahl als Lebenszeichen, und 381 ist eine große
Zahl.

Schlimmer als der Messfehler war der Gebrauch: Ich habe die Momentaufnahme als
**Widerlegung** eines fremden Verdachts benutzt („er hängt nicht"). Ein
Zustandswert kann einen Hänger-Verdacht nicht widerlegen — er ist mit ihm
verträglich.

**How to apply:** Bei jedem Hänger-Verdacht **zweimal messen** und die
Differenz nennen: „CPU +0,00 s in 2 s" ist eine Aussage, „381 s" ist keine.
Dasselbe gilt für eine Ausgabedatei — 0 Bytes können „hängt" heißen oder
„puffert"; wer es wissen will, fährt `python -u` und setzt Marken vor die
teuren Schritte.

Und die Umkehrung, weil sie hier zweimal auftrat: **Wer einen Hänger-Verdacht
bekommt, prüft ihn, statt ihn zu entkräften.** Die zwei Sekunden für die
zweite Messung sind billiger als jede Verteidigung.

Das ist das Prozess-Geschwister von [[am-eingang-drehen]] (antwortet die
Messung auf jede Änderung gleich, misst sie nichts) und gehört zur Familie um
[[gemessene-frage-ist-nicht-die-gestellte]]. Der Hänger selbst steht als
Signatur C im Register.
