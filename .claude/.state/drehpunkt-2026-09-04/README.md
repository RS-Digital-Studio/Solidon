# Den Drehpunkt von Hand fahren

`fahre_drehpunkt.py` öffnet ein echtes Solidon-Fenster mit `plate_holes.stl`
und misst, ob die Ansicht um das dreht, was in der Bildmitte steht (§2.9).

```
.venv\Scripts\python.exe -u .claude\.state\drehpunkt-2026-09-04\fahre_drehpunkt.py
```

Exit 0 heißt: Der Drehpunkt sitzt dort, wo man hinsieht. Zu fahren nach jeder
Änderung an `_aim_rotation`, `centre_hit`, `rotation_focus`, `_world_at` oder
am `tilt`/`rotate`-Zweig des Interaktionsstils.

## Warum das kein Test ist

**Offscreen gibt es keinen Picker.** `centre_hit` fragt die Größe des
Renderers und dann `vtkCellPicker` in dessen Mitte; in der Suite bleibt
`Viewport.plotter` auf `None`, und `tests/test_viewport_decisions.py` setzt an
diese Stelle eine Attrappe. Die Tests prüfen damit die *Regel* — wer die Mitte
liefert, wer der Rückfall ist —, nicht die Kette bis in VTK. Ob der Renderer
im echten Fenster überhaupt eine brauchbare Größe meldet und ob der Picker
dort den Körper trifft, sagt keiner von ihnen.

## Was gemessen wird, und die Zahl vom 04.09.2026

| Messung | Ergebnis |
|---|---|
| der Renderer hat eine Bildmitte | 1100×650 ab (0,0), Mitte (550, 325) |
| `centre_hit` trifft den Körper | (16,98 / −1,49 / **8,0**) — die Oberkante der Platte |
| die Bildmitte hält beim Drehen | **0,00 mm** gewandert |
| die Bildmitte hält beim Kippen | **0,00 mm** gewandert |
| dasselbe nur über `rotation_centre` | **3,14 mm** — der Unterschied dieser Änderung |
| die Ansicht neigt sich nicht | **0,00 Grad** nach zwölf diagonalen Zügen |
| über dem Hintergrund | kein Treffer, Rückfall auf die Körpermitte |
| die Druckplatte zieht nicht | kein Treffer, obwohl die Mitte auf das Bett zeigt |

## Zwei Fallen, beide beim Bauen zugeschnappt

**Eine Gegenprobe, die knapp danebenzielt, prüft die Pickertoleranz.** Die
erste Fassung der Hintergrund-Probe blickte schräg am Teil vorbei und bekam
(25, −25, 0) zurück — der Zell-Picker trägt eine Toleranz als Anteil der
Bilddiagonale, und ein Strahl fünf Millimeter neben der Platte liegt darin.
Wer „Hintergrund" prüfen will, blickt in den Himmel.

**Und die Kulissenfrage braucht ihre eigene Probe.** Dass die Druckplatte den
Drehpunkt nicht an sich zieht, hängt allein an der PickList in `_world_at` —
eine Zeile, die jemand beim Aufräumen für überflüssig halten könnte. Die
letzte Messung zeigt senkrecht auf das leere Bett und muss nichts finden.

## Die Neigung, und warum dieser Prüfstand sie gefangen hat

Der erste Anlauf gegen das Neigen war eine überschriebene `Rotate`-Methode in
der Stilklasse. Sie war richtig gerechnet, ihre drei Einheitstests waren grün
— und **wirkungslos**: Am laufenden Fenster gemessen blieben 35,8 Grad
Schräglage nach zwölf Zügen, praktisch die alte Bewegung.

> **VTKs `OnMouseMove` ist C++ und ruft die Methode seiner eigenen Klasse,
> nie die einer Python-Unterklasse.**

Das ist derselbe Grund, aus dem in `viewport.py` alles über `AddObserver`
läuft. Gedreht wird deshalb im Beobachter (`_mouse_move` → `_turn`), genau wie
das Kippen daneben, und `turntable_camera` trägt nur die Rechnung.

Die Lehre für den nächsten: **Einheitstests über eine reine Funktion sagen
nichts darüber, ob jemand sie ruft.** Drei grüne Tests und ein Fenster, das
sich unverändert verhält, sind kein Widerspruch — sie prüfen verschiedene
Dinge.
