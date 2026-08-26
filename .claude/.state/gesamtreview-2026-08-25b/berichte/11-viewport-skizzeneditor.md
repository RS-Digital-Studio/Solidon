# Gebietsbericht: Viewport und Skizzeneditor

Gebiet: `app/ui/viewport.py`, `app/ui/sketch_editor.py`, `app/ui/cursors.py`, `app/ui/scale_widget.py`, `app/ui/palette.py`. Strikt lesend; Prüfskripte unter `C:\Users\rober\AppData\Local\Temp\claude\review-ui2\`.

**Hinweis vorweg:** Befunde in `viewport.py` sind als **möglicherweise Baustelle** zu lesen — Nachbarsitzungen arbeiten dort.

---

## Schwer

### 1 [hoch] Ein Klick im Skizzenmodus endet bei drei von acht Werkzeugen in einem `KeyError` — darunter dem voreingestellten

`app/ui/sketch_editor.py:1518`

```python
needed = {"point": 1, "line": 2, "circle": 2, "arc": 3}[self.tool]
```

`place_on_plane` (Zeile 1423/1444) ruft **immer** `place()`, ohne die Werkzeugverzweigung, die `mousePressEvent` (Zeile 1336–1370) hat: dort gehen `select` nach `_hit_point`/`_hit_element`/`grab_point` und `trim`/`extend` nach `cut_or_grow`. Im Viewport-Modus gibt es diese Verzweigung nicht — `MainWindow._on_sketch_point` (`app/ui/main_window.py:4523`) reicht jeden Klick direkt an `place_on_plane` weiter.

Gemessen (`probe_place.py`, offscreen): VERIFIZIERT

```
select: KeyError: 'select'
trim:   KeyError: 'trim'
extend: KeyError: 'extend'
point:  ok, Elemente=1
line:   ok, Elemente=1
```

**Wann es den Kunden trifft:** sofort und im Normalfall. Das Startwerkzeug ist „Auswählen" (`sketch_editor.py:508`, gesetzt in `sketch_editor.py:2869`), und `start_sketch` wählt kein Zeichenwerkzeug vor. Wer auf *Zeichnen* drückt und in die Ansicht klickt, löst die Ausnahme aus; PySide6 6.11.2 druckt sie auf stderr und läuft weiter (gemessen, `probe_slot.py`) — für den Kunden passiert schlicht **nichts**. Dieselbe Lage nach jedem Escape: `SketchPanel.drop_tool` (Zeile 3450) stellt auf `select` zurück. Damit sind *Auswählen*, *Trimmen* und *Verlängern* — drei der acht Knöpfe in der Zeichenleiste — im ausgelieferten Modus tot.

Nebenwirkung: `place` hat vor dem `KeyError` schon `self._pending`/`self._pending_world` gefüllt (Zeile 1507/1508). Der Rest bleibt stehen, bis ein `set_tool` aufräumt.

Warum kein Test es fängt: `tests/test_sketch_editor.py:2686` und `tests/test_ui.py:6858` setzen vorher `set_tool("line")`. Geprüft ist, was der Code tut, nicht was er soll.

**Fix:** Die Verzweigung gehört in `place_on_plane`, damit beide Wege dieselbe Regel haben (select → `_hit_point`/…; trim/extend → `cut_or_grow`; sonst `place`). Zusätzlich in `place` ein früher Rücksprung für ein Werkzeug ohne Klickzahl — ein `KeyError` ist keine Fehlermeldung (Regel 17).

### 2 [hoch] Im Skizzenmodus zieht ein Linkszug den gewählten Körper und legt eine Operation an

`app/ui/viewport.py:6454` (`_left_down`), `app/ui/viewport.py:5976` (`can_drag_body_at`)

`_left_down` fragt `on_body_drag("ready", …)` ohne jede Rücksicht auf `self._sketch_frame`. `can_drag_body_at` prüft nur `self._selected` und `_object_at`. Der Skizzenmodus behält die Auswahl mit Absicht (`start_sketch`, `main_window.py:4385` — die gewählte Fläche gibt die Ebene), also ist genau im häufigsten Einstieg „Fläche wählen → Zeichnen" ein Körper gewählt und liegt unter dem Zeiger.

Gemessen (`probe_drag.py`): VERIFIZIERT

```
Skizzenmodus an, _sketch_frame: True
can_drag_body_at((0,0,5)): True
begin_body_drag_at((0,0,5)): True
transformDragged gesendet: [TransformSteps(offset=(12.0, 7.0, 0.0), ...)]
```

`MainWindow._on_transform_dragged` (`main_window.py:5249`) macht daraus ungefiltert `session.apply(_("Direkt bewegt"), …)`.

**Wann es den Kunden trifft:** Wer beim Zeichnen die Ansicht drehen will (in `cad`, `blender`, `orbit` dreht die linke Taste) oder aus Gewohnheit zieht, verschiebt stattdessen das Teil, auf dessen Fläche er gerade zeichnet. Rücknehmbar, aber genau die Überraschung, die §2.1 vermeiden will.

**Fix:** eine Zeile in `can_drag_body_at`: bei `self._sketch_frame is not None` → `False`.

### 3 [hoch] Solange die Explosionsansicht läuft, hebt jeder Klick die Auswahl auf

`app/ui/viewport.py:2857` (`_from_view`), `app/ui/viewport.py:2824` (`_view_offset`)

`_view_offset` ist ausdrücklich die eine Stelle für **beides** — Auseinanderziehen (§18.8) und Platte (§25). Die Umkehrung `_from_view` macht aber nur den **Plattenversatz** rückgängig; `_exploded` fehlt darin. Jeder Klickpfad (`_on_picked` 3652, `_on_right_click` 5885, `_look_under_pointer` 3585, `_aim_at` 4447) rechnet über `_from_view`.

Gemessen (`probe_explode.py`, zwei Quader, Faktor 1,0): VERIFIZIERT

```
ohne Explosion:            _object_at((60,0,0)) -> obj_b
Versatz B:                 [30. 0. 0.]
Klickpunkt im Bild:        (90.0, 0.0, 0.0)
_from_view:                (90.0, 0.0, 0.0)     <- unverändert
_object_at am gezeigten Ort: None
```

**Wann es den Kunden trifft:** *Explosion* ist einer der acht Werkzeugumschalter. Man zieht die Baugruppe auseinander und klickt auf ein Teil — der Klick trifft nichts, `objectPicked.emit("")`, die Auswahl fällt weg. Bei kleinem Faktor trifft er gelegentlich den **falschen** Körper. Ebenso betroffen: Rechtsklick-Menü, Zeigersuche, Bohrungszielen.

**Fix:** Die Umkehrung muss dieselben zwei Posten abziehen, die `_view_offset` addiert. Sauber: in `_object_at`/`_nearest_mesh` je Kandidat gegen `bounds + _view_offset(entry, result)` prüfen statt den Punkt global zurückzurechnen. Ersatzweise: Auseinanderziehen beim Picken aussetzen.

### 4 [hoch] Punkte und Elemente lassen sich im Skizzenmodus nicht ziehen — und `_dragging` bleibt für immer hängen

`app/ui/sketch_editor.py:1798` (`note_pointer`, Vorgabe `buttons=NoButton`), `:1828`, `:1919` (`mouseReleaseEvent`), `:1391` (`grab_point`)

`.claude/rules/zeichenflaeche.md` sagt zu: „Ein Klick auf einen Punkt greift ihn (`grab_point`) … und er hängt sofort am Zeiger." Im Viewport-Modus wird `hover_on_plane` → `note_pointer(position)` **ohne Tastenzustand** gerufen; die Bedingung `self._dragging is not None and buttons & Qt.MouseButton.LeftButton` (Zeile 1828) ist damit nie wahr. Der Viewport sendet ohnehin nur `sketchPointPicked` beim *Klick* (`viewport.py:6205`, hinter `is_click`), nie einen Zug. `mouseReleaseEvent` erreicht den unsichtbaren Canvas nie, also wird `_dragging` nie zurückgesetzt — auch `set_tool` (Zeile 876–879) räumt es nicht.

Gemessen (`probe_grab.py`): VERIFIZIERT

```
Undo-Tiefe vor dem Griff: 1   _dragging: None
Undo-Tiefe nach dem Griff: 2  _dragging: 1   Auswahl: [('point', (1,))]
Punkt bewegt? [(0.0, 0.0), (20.0, 0.0)]        <- nein
pointer_target: (25.0, 5.0)                     <- gerastert statt roh
nach Werkzeugwechsel _dragging: 1               <- bleibt stehen
nach einem Strg+Z: Elemente: 1, Punkte unverändert
```

Drei Folgen: Punkt nur noch über *Koordinaten …* im Kontextmenü bewegbar; Verschieben einer Auswahl mit der Hand (`_shift_selection`, `edit.move`) existiert im gefahrenen Modus gar nicht; `_dragging` bleibt dauerhaft belegt und `pointer_target()` (Zeile 671–677) nennt danach auch beim Auswählen die gerasterte statt der rohen Lage.

**Fix:** Der Viewport braucht neben `sketchPointPicked` einen Zug: Drücken/Bewegen/Loslassen auf der Zeichenebene als eigenes Signal (analog `on_body_drag`), das der Canvas über `drag_on_plane(point, held: bool)` entgegennimmt. Minimal und sofort: `set_tool` und `place_on_plane` setzen `self._dragging = None` zurück.

---

## Mittel

### 5 [mittel] Raster, Fangweite und Fangradius folgen dem Zoom im Skizzenmodus nicht

`app/ui/main_window.py:4600` (`_redraw_sketch`), `:4633`–`:4651`; `app/ui/viewport.py:6541` (`_zoom_at_pointer`), `:2056` (`_watch_camera`)

`set_view_scale`, `follow_grid` und `show_sketch(step)` hängen ausschließlich an `_redraw_sketch`, gerufen nur bei `sketchChanged`, Betreten, Ebenenwechsel. Das Rad ruft nur `plotter.render()`; `_watch_camera` zieht auf `EndInteractionEvent` allein die **Schatten** nach. Auch `_fit_sketch_view` (Zeile 4588) setzt nur die Kamera. Nach jedem Zoom gilt bis zum nächsten Klick der alte Maßstab; der Fangradius ist `SNAP_PX / _snap_scale()` (`sketch_editor.py:1292`) — nach achtfachem Hineinzoomen fängt ein Klick einen Punkt, der acht mal weiter weg liegt, als er aussieht. Der **erste** Klick nach dem Zoom rechnet noch mit dem alten Maßstab. („Zwei Schwellen, eine Frage", zeitversetzt statt räumlich.)

**Fix:** `_watch_camera` bekommt einen zweiten Empfänger oder der Viewport ein `cameraChanged`-Signal, das `MainWindow._redraw_sketch` anstößt, solange `_sketch_panel` steht; `_fit_sketch_view` ruft es danach ebenfalls.

### 6 [mittel] Bei zwei Platten springt ein Skizzenklick um eine Bettbreite

`app/ui/viewport.py:6156` (`_sketch_hit`), `:5482` (`show_sketch`), `:658` (`plate_at`)

`show_sketch` legt Raster und Kurven über `to_world(frame, …)` in die **Szene**, ohne `_view_offset`. `_sketch_hit` rechnet den Strahlursprung dagegen über `_from_view` zurück. Beide Enden derselben Umrechnung widersprechen sich, sobald zwei Betten im Bild stehen.

Gemessen (`probe_plate_sketch.py`, 220er Bett, zwei Platten): VERIFIZIERT

```
x= 129.0 -> Platte 0, _from_view (129.0, 0.0, 0.0)
x= 131.0 -> Platte 1, _from_view (-129.0, 0.0, 0.0)
x= 150.0 -> Platte 1, _from_view (-110.0, 0.0, 0.0)
```

Das Raster wird mit `SKETCH_GRID_REACH = 150.0` (`main_window.py:314`) bis ±150 mm gezeichnet — der Kunde sieht dort Linien und klickt darauf. Ab 131 mm landet der Punkt 260 mm weiter links.

**Fix:** Eine Zahl für beides — entweder zeichnet `show_sketch` mit Plattenversatz (dann ist `_from_view` richtig) oder `_sketch_hit` lässt `_from_view` weg.

### 7 [mittel] Entf ist im Skizzenmodus wirkungslos, das Kontextmenü nennt sie trotzdem

`app/ui/sketch_editor.py:2014` gegen `:1956`

`menu.addAction(tr("Löschen  (Entf)"))` verspricht das Kürzel; ausgeführt wird Entf aber in `SketchCanvas.keyPressEvent` (Zeile 1956) — auf einem Widget, das `use_viewport` unsichtbar schaltet (`sketch_editor.py:3278`) und das damit weder Fokus noch Tastenereignisse bekommt. Die Kürzelliste `_shortcuts` enthält Entf nicht; die einzige andere Entf-Bindung (`_scope_shortcut`, `main_window.py:2250`) ist im Skizzenmodus über `gesturing` gesperrt (`main_window.py:2374`). Dasselbe für die anderen Zweige: Eingabetaste beendet den Spline nicht mehr (Doppelklick auch nicht — der Viewport reicht ihn nicht weiter); übrig bleibt nur der Klick auf den letzten Punkt.

**Fix:** In `_install_shortcuts` ein `QShortcut(Delete)` auf `canvas.remove_selected` und eines für die Eingabetaste auf `canvas.finish_spline`; beide landen über `use_viewport` von selbst am Fenster.

### 8 [mittel, PLAUSIBEL] Ein Zug unter der Fangschwelle bleibt am Actor stehen und wird beim nächsten Zug mitgerechnet

`app/ui/viewport.py:4915` (`_detach_gizmo`), `:5093` (`_on_gizmo_released`)

Der Docstring von `_on_gizmo_released` nimmt an, das Neuanhängen setze die Vorschau zurück. pyvista tut das nicht — `affine_widget.py:206` übernimmt eine bestehende `user_matrix` als Basis des nächsten Zugs; `remove()` ruft `_reset()` nicht, `_detach_gizmo` setzt nichts zurück. Erreichbar mit den Vorgaben `_grid_step = 1.0`, `_angle_step = 15.0` (`viewport.py:1847/1848`): Drehung < 7,5° oder Verschiebung < 0,5 mm rastet auf null (`snap_to_step`, `app/core/geom/transform.py:144`), erzeugt keine Operation — der Körper bleibt im Bild verdreht stehen, der nächste Zug komponiert darauf. Derselbe Weg für Esc nach getippter Zahl (`_on_gizmo_released` Zeile 5110) und für `ScaleHandle` (`app/ui/scale_widget.py:216`). Nicht offscreen nachstellbar (Interactor nötig) — Beleg ist der pyvista-Quelltext plus die widersprechende Zusage im eigenen Docstring.

**Fix:** In `_detach_gizmo` die Vorschau ausdrücklich löschen (`user_matrix = eye(4)`), bevor der Griff geht; ScaleHandle ebenso.

---

## Gering

### 9 [gering] Das Maßfeld bleibt nach einem fertigen Kreis über dem Bild stehen

`app/ui/sketch_editor.py:1565`–`:1573` (`place`), `:876` (`set_tool`) — `measuringChanged` wird nur im Zweig `elif self._pending_world:` von `note_pointer` gesendet (Zeile 1837); nach fertigem Kreis kommt nie eine Null, `_place_measure_field` blendet nicht aus. VERIFIZIERT (`probe_measure.py`): Feld sichtbar True, Feldwert 20.0, pending_measure 0.0. Auch `set_tool` (räumt `_pending_world`) meldet nichts — gilt also auch nach Escape. **Fix:** in `place` nach `_apply` und in `set_tool` je ein `measuringChanged.emit(self.pending_measure())`.

### 10 [gering] `HoldToCompare` schluckt die Leertaste anwendungsweit, auch für Knöpfe

`app/ui/viewport.py:1648`–`:1660` — Filter an der `QApplication`, solange das Vorschauband steht (`mark_preview`, 4641); gibt für jedes Nicht-Textwidget `True` zurück. Fokussierter `QPushButton` per Leertaste geht im Operationsdialog mit laufender Vorschau nicht mehr (§19.2). **Fix:** vor dem Schlucken auf `QAbstractButton` prüfen, oder nur schlucken, wenn `self._viewport.difference is not None`.

### 11 [gering] Verweis auf eine Methode, die es an dieser Klasse nicht gibt

`app/ui/viewport.py:4582` — `:meth:`step_selection_out`` existiert nur als `MainWindow._step_selection_out` (`main_window.py:4289`). **Fix:** vollqualifizierter Verweis.

### 12 [gering] Jeder Punktgriff legt einen Undo-Stand an, der nichts verändert

`app/ui/sketch_editor.py:1391` — `grab_point` ruft `_remember()`; im Viewport-Modus wird nie gezogen (Befund 4), Undo-Tiefe 1 → 2, erstes Strg+Z ändert nichts Sichtbares. Auch in der Zeichenflächen-Variante bleibt der Rest, wenn jemand nur auswählt. **Fix:** Stand erst beim ersten wirklichen Zug merken, wie `_shift_selection` (1859–1865).

---

## Geprüft und in Ordnung

* Toleranzen: `SNAP_PX`, `PICK_PX`, `CURSOR_PIXELS`, `SKETCH_POINT_PIXELS`, `CLICK_SLACK`, `FEATURE_REACH_*` durchgehend in Bildpunkten bzw. Diagonalenanteil; `_snap_scale()` nimmt richtig den Kameramaßstab.
* Prioritäten beim Picken: `_resting_role` und `_on_picked` führen dieselbe Rangfolge; `_means_a_feature` liest sie statt sie zu wiederholen; `_would_pick_feature` und `_click_target` sind dieselbe Rechnung.
* Sichtbarkeitsfilter: `_in_view` in `_object_at`, `_nearest_mesh`, `_bore_aim`, `_through_aim` konsequent — Ausgeblendetes und fremde Platten kein Klickziel.
* Auswahl über Neuauswertung: `show_scene` leert `_feature_geometry`/`_object_hulls`, setzt Auswahl bei leerer Szene zurück, hängt den Griff neu auf.
* Regel 2 im Zeichenmodus: Skizze bleibt Parameterwert; `finish_sketch(keep=False)` räumt vollständig ab; `show_*` erzeugen nur Actors.
* Schwache Rückrufe: `_weak_callbacks`, `_watch_camera`, `weak_slot` halten die Ansicht nicht fest; keine VTK-Referenz über Funktionsgrenzen.
* Leistung: `show_sketch_cursor` zeichnet nur beim Wechsel; Merkmalssuche am `HOVER_DELAY_MS`-Timer; Hüllen/Merkmalsdreiecke je Auswertung einmal. Kein Szenenneuaufbau je Mausbewegung.
* `cursors.py`, `palette.py`: keine Bedeutung allein über Farbe, `readable_on` gerechnet, Zeigergröße an Zeilenhöhe.
* `scale_widget.py`: `dragged_factor` eingespannt, `ray_plane_hit` mit Parallelitätsprüfung, Beobachter in `remove()` abgemeldet — bis auf die Vorschau-Matrix aus Befund 8.
