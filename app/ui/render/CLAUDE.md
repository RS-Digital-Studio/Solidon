# `app/ui/render/` — die Renderer hinter der 3D-Ansicht

Der Viewport (§18) beschreibt, was im Bild steht; ein Renderer entscheidet,
wie es auf den Schirm kommt. Zwei stehen dahinter, beide hinter derselben
Schnittstelle, beide werden gemessen (Entscheidung Robert, 05.09.2026: „bau
beides und mess“; Gedächtnis `viewport-zwei-renderer-messen`).

## Die Karte

| Datei | Rolle |
|---|---|
| `api.py` | Der Vertrag: `Renderer`, `Item`, `LabelsItem`, die Stile (`SurfaceStyle`, `CellColours`, `LabelStyle`, `AxesMarkerStyle`), `CameraPose`, `PointerEvent`, `Pick`. Farben als Hexwert (`rgb`, `hex_of`) |
| `vtk_renderer.py` | VTK direkt, ohne die PyVista-Hülle: `vtkPolyData` aus NumPy, Aktoren, Farbleitern, Beschriftungen über `vtkLabelPlacementMapper`, Zell-Picking, Bildaufnahme, FXAA, SSAO, Achsenkreuz. Qt-Einbettung über VTKs eigenes `QVTKRenderWindowInteractor`; ohne Fenster (`offscreen=True`) für Agentenbilder und Tests |
| `shapes.py` | Die kleinen Netze der Ansicht als NumPy-Felder — Scheibe, Zylinder, Kegel, Pfeil, Würfel, Fläche, Raster, Ringlinie —, damit beide Renderer dasselbe zeichnen und `tests/test_render_shapes.py` sie ohne Fenster nachmisst (geschlossen, nach außen, Volumen nach Formel) |
| `gizmo.py` | Der Bewegungsgriff (§18.11) auf dem Vertrag: drei Pfeile, drei Ringe, Hover über `pick_item`, Zug als Lot des Sichtstrahls auf die Achse beziehungsweise Schnitt mit der Ebene quer dazu. `handle(event)` sagt mit `True`, dass die Geste ihm gehört; `interact_callback` darf die Matrix berichtigen (der Magnet auf 45°). Der Skalierwürfel daneben liegt in `app/ui/scale_widget.py` und ist genauso gebaut |
| `navigator.py` | Die Kameraführung ohne VTK: die Tabelle `_NAVIGATION` (welche Taste in welchem Schema was tut), `turntable_camera` (der Drehteller, der die Ansicht aufrecht hält), `is_click`, und der `Navigator`, der `PointerEvent`s in Drehen, Kippen, Schieben, Radzoom am Zeiger, Körperzug, Malen und die Rückrufe an die Ansicht übersetzt (`NavigatorCallbacks`). Gemessen mit einem Renderer-Doppel in `tests/test_navigator.py` |

## Drei Festlegungen, die der Viewport voraussetzt

* **Bildpunkte zählen wie Qt** — Ursprung oben links, y nach unten, in
  Gerätepixeln. VTK zählt von unten; `VtkRenderer._flip` rechnet an der
  Grenze um, in `world_to_display`, `display_to_world` und beim Picking.
* **Kein Interaktionsstil.** VTKs Trackball ist abgeschaltet; Zeigergesten
  kommen als `PointerEvent` beim Viewport an, und der führt die Kamera über
  den Vertrag (`set_camera_pose`, `dolly`).
* **Zeichnen an einer Stelle.** Kein Aufruf hier zeichnet von selbst;
  `render()` ruft der Viewport in `_draw`.
* **Was vorn gezeichnet wird, wird vorn gepickt.** `keep_in_front` rückt
  einen Aktor per Polygonversatz vor das Material; der Zell-Picker rechnet
  geometrisch und wüsste davon nichts. `pick_item` fragt deshalb zuerst die
  Aktoren mit `in_front`, dann alle — der Skalierwürfel an einem
  würfelförmigen Körper liegt in dessen Hüllquader und wäre sonst nie zu
  greifen. Die Toleranz ist eine Zahl in Bildpunkten (`PICK_SLACK_PIXELS`),
  nicht VTKs Bruchteil der Fensterdiagonale.

## Was gemessen ist

`tests/test_render_vtk.py` liest Bildpunkte und Picks vom Renderer ohne
Fenster — Farbe, Deckkraft, Sichtbarkeit, Zellfarben, Beschriftungen,
Linien vor dem Material, Koordinatenrichtung, Kamera. Eines daraus gehört
hierher, weil es überrascht:

* **Durchscheinende Körper mischen sich reihenfolgeunabhängig** (VTK 9.6.2,
  ohne Fenster wie mit PyVista gemessen). Der Viewport hängt seine Aktoren
  trotzdem nach Tiefe um (`_order_by_depth`, nach einem Bild vom 03.09.2026);
  `set_draw_order` trägt das als Prop-Reihenfolge weiter, und der Test hält
  fest, dass sie hier nichts ändert.
