---
name: pruefstand-geht-den-weg-der-oberflaeche
description: "Wo ein Prüfstand den Kern direkt ruft statt über den Weg der Oberfläche, baut er einen Zustand, den es im Betrieb nicht gibt — vier Fehlbefunde an einem Tag."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4e2b249b-1d42-4020-bb0e-bdcf350ef625
  modified: 2026-08-30T05:50:08.091Z
---

Am 30.08.2026 vier Mal in einer Sitzung, jedes Mal beinahe als Befund
gemeldet:

| Prüfstand rief | übersprungen | falscher Schluss |
|---|---|---|
| `slice_model` direkt | die Profilprüfung des Dialogs | „ElegooSlicer nimmt keinen Auftrag an" |
| `readiness()` ohne Argument | `_workflow()`, das Text und Bild trennt | „die Bereitschaft prüft den falschen Ablauf" |
| `Session()` ohne `load_operations()` | den Registeraufbau | „das Beispielprojekt hat null Objekte" |
| `Project()` statt `new_project()` | das Dokument | Abbruch vor der ersten Messung |

Alle vier sahen nach einem Anwendungsfehler aus. Alle vier waren ein
Prüfstand, der einen Schritt ausließ, den die Anwendung macht.

**Why:** Der Kern ist absichtlich freizügig — er nimmt entgegen, was man ihm
gibt. Die Vorprüfungen leben in der Oberfläche, weil dort die Bedienung
entscheidet. Wer den Kern direkt ruft, umgeht sie und misst eine Lage, die
kein Klick herstellt. Zweimal stand die Antwort sogar als Kommentar an der
übersprungenen Stelle: „Der Lauf lief bis dahin los und endete in ‚Der Slicer
hat keine Druckdatei geschrieben' — ein Satz über das Ende, nicht über die
Ursache."

**How to apply:** Der Prüfstand geht denselben Weg wie der Klick — oder er
begründet, warum nicht. Vor jedem Befund die Frage: *Was tut die Oberfläche
vor diesem Aufruf?* Ein `grep` nach dem Funktionsnamen in `app/ui/` beantwortet
sie in Sekunden und zeigt die Vorprüfung, die man gerade übersprungen hat.

Und es gilt für die **Suite** genauso: Ein Test, der ein Widget ohne das
Anwendungs-Stylesheet baut, misst eine Lage, die es beim Kunden nie gibt —
derselbe Fehler, andere Richtung.

Die Schwester dazu ist [[testprojekt-trifft-den-fall-nicht]]: Dort fehlen die
Daten, die die Anwendung erzeugt; hier fehlen die Schritte, die sie geht.
Siehe auch [[messwerkzeug-misst-sich-selbst]].

---

**Nachtrag 31.08.2026 — die dritte Richtung: Wer ein Werkzeug nachbaut, erbt
seine Fallen nicht.** Ich habe einen Prüfstand gebaut, der das Hauptfenster
mit `QWidget.grab()` fotografiert, und das Bild als stärksten Beleg für einen
Befund angeführt: „Der Viewport ist danach vollständig leer."

Er war nie leer. `grab()` malt das Widget über den Qt-Painter nach, und der
weiß nichts von dem, was OpenGL in die 3D-Ansicht gezeichnet hat — der
Bereich bleibt im Bild schwarz, gleich was darin steht. Gemessen: `_actors=2`,
zehn Aktoren im Renderer, `plotter.screenshot()` liefert 766 verschiedene
Farben, und derselbe Moment über `grab()` zeigt eine leere Fläche.

**Die Falle stand die ganze Zeit im Repository, an zwei Stellen, wörtlich:**
`support_dialog.window_shot` („die 3D-Ansicht ist ein natives Fenster und
bliebe sonst leer" — es holt sie mit `_paint_viewports` nach), und
`tools/make_figures.py` („der Qt-Painter weiß nichts von dem, was OpenGL in
den Viewport gezeichnet hat — die Bildmitte bliebe schwarz" — es hat dafür
einen `from_screen`-Schalter auf `screen.grabWindow`). Auch
`make_web_images.py` nimmt das Fenster so auf und `grab()` nur den
Startbildschirm, der keinen Viewport hat.

**Why:** Ich habe die Fallen nicht übersehen — ich bin ihnen nie begegnet,
weil ich mein eigenes Aufnahmewerkzeug im Scratchpad gebaut habe, statt das
vorhandene zu benutzen. Das ist der Unterschied zu
[[benannte-falle-schuetzt-nicht]]: Dort schützt der Kommentar den nicht, der
die Datei *liest*; hier schützt er den nicht, der sie *nie öffnet*.

**How to apply:** Bevor ein Prüfstand etwas aufnimmt, misst, öffnet oder
speichert — **suchen, ob die Anwendung dafür schon einen Weg hat**
(`grep -rn "def.*shot\|screenshot\|grab" app/ tools/`). Sie hat ihn meistens,
und wo sie ihn hat, steht daneben, warum der naive Weg nicht reicht. Ein
selbst gebautes Werkzeug beginnt bei null Erfahrung, auch wenn das Projekt
zehn Jahre alt ist.

Und die Regel für den Viewport im Besonderen: **Ein Bildschirmfoto belegt die
Ansicht nur über `plotter.screenshot()` oder `screen.grabWindow()`.**
`QWidget.grab()` taugt für Panels, Menüs und Leisten. Wer die Ansicht belegen
will, prüft vorher an einer Lage mit **bekanntem** Inhalt, ob das Werkzeug ihn
zeigt — sonst ist das Foto, das die Instanz sein soll, nur ein weiterer
blinder Zeuge.

---

**Nachtrag 04.09.2026 — die vierte Richtung: eine Schicht unter dem Widget ist
schon zu hoch.** Robert meldete, dass sich nach dem Anwählen einer Bohrung
nichts mehr auswählen und nichts mehr abwählen lässt. Zwei Sonden sagten
„alles in Ordnung":

| Sonde | Aufruf | Ergebnis |
|---|---|---|
| 1 | `viewport._on_left_click(x, y)` | Auswahl, Wechsel, Abwahl — alles grün |
| 2 | `style._left_down()` / `style._left_up()` am Interaktionsstil | ebenfalls grün |
| 3 | `QTest.mouseClick(plotter.interactor, …)` | **ab dem zweiten Klick tot** |

Die Ursache lag genau zwischen Sonde 2 und Sonde 3: pyvista meldet auf dem
**Interactor** einen Doppelklick-Rückruf an, der den Interaktionsstil
austauscht. Sonde 2 rief die Methoden des Stils direkt und ging damit an dem
Ereignis vorbei, das den Stil wegnahm — sie fuhr also den Weg der Oberfläche
bis auf die letzte Schicht und war deshalb blind für genau diese.

**Why:** „Über die Oberfläche" ist keine Ja/Nein-Frage, sondern eine Höhe. Wer
den Handler ruft, prüft den Handler; wer den Stil ruft, prüft den Stil. Alles,
was *zwischen* Widget und Handler passiert — fremde Beobachter, Doppelklick,
Fokus, Ereignisfilter —, ist unsichtbar, und dort sitzen die Fehler, die man
mit dem Debugger nicht findet, weil jeder Einzelteil funktioniert.

**How to apply:** Wenn ein gemeldeter Bedienfehler in der Sonde nicht auftritt,
ist die Sonde zu tief angesetzt. Eine Stufe höher gehen, bis beim **Widget**
angekommen: `QTest.mouseClick`, `QTest.keyClick`, `QTest.mousePress/Move/Release`
auf das Widget, das der Finger trifft. Erst wenn auch das grün ist, war die
Meldung nicht reproduzierbar — vorher heißt grün nur „an dieser Höhe nicht".
