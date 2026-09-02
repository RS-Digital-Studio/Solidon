---
name: verwaiste-widgets-sterben-im-falschen-moment
description: Ein Qt-Widget ohne Parent, das ein Test dem Speicherbereiniger überlässt, stirbt in dessen nächstem Lauf — und den löst eine Allokation mitten im Bau des nächsten Widgets aus; die Portionsgröße war die falsche Achse
metadata:
  type: feedback
---

Am 02.09.2026 riss `test_print_settings_ui.py` in der CI in beiden Anläufen
derselben Fünferportion und lokal ebenso (Exit 139, deterministisch), Stapel
jedes Mal in `QLabel(...)` beim Bau eines Dialogs. Keine Zweier-, Dreier- oder
Viererkombination der fünf Tests riss — nur alle fünf. Die Portionsgröße, mit
der die CI seit dem Morgen fuhr, maß die falsche Achse: nicht *wie viele*
Dialoge ein Prozess baut, sondern *wann* ein verwaister stirbt.

**Der Schalter, der es trennte:** `gc.disable()` als Plugin (`-p gcoff`) — die
Portion war grün. Damit war der Zeitpunkt der Zerstörung die Ursache, nicht die
Zerstörung selbst; `gc.collect()` nach jedem Test machte sie sechsmal von sechs
grün, die ganze Datei in drei Sekunden.

**Zwei Wege, ein Ergebnis, ein Unterschied am Prozessende:** `deleteLater` plus
`sendPostedEvents(DeferredDelete)` zwischen den Tests heilte dieselbe Datei —
und ließ `test_generate_ui.py` mit `0xc0000409` enden statt mit 0, zweimal von
zwei, mit `close()` davor ebenso. Ein Dialog mit Arbeitern (`WorkerLeash`)
verträgt keine vorzeitige Qt-Zerstörung; der Sammler zerstört ihn erst, wenn
nichts mehr auf ihn zeigt.

**Why:** Der Absturz-Frame war die nächste Allokation
([[absturz-frame-ist-die-naechste-allokation]]); die Bisektion über Tests fand
nichts, weil kein Test die Ursache war. Erst ein Schalter, der den Mechanismus
abschaltet, statt die Zusammensetzung zu ändern, trennte Zeitpunkt von
Zerstörung — in einer Minute.

**How to apply:** Bei einem Riss beim *Bau* eines Qt-Objekts zuerst
`gc.disable()` messen, dann `gc.collect()` am Testende. Zerstörung über den
Sammler, nie vorzeitig über `deleteLater`, wenn das Widget Arbeiter hat. Und
den echten Windows-Code lesen (`subprocess.run(...).returncode`), nicht die 127
der Shell. Siehe [[vtk-qt-referenzen-halten-zu-lange]] für die Fenstermine,
die eine andere ist.
