# `app/ui/render/` — die Renderer hinter der 3D-Ansicht

Der Viewport (§18) beschreibt, was im Bild steht; ein Renderer entscheidet,
wie es auf den Schirm kommt. Zwei stehen dahinter, beide hinter derselben
Schnittstelle, beide werden gemessen (Entscheidung Robert, 05.09.2026: „bau
beides und mess“; Gedächtnis `viewport-zwei-renderer-messen`).

## Die Karte

| Datei | Rolle |
|---|---|
| `api.py` | Der Vertrag: `Renderer`, `Item`, `LabelsItem`, die Stile (`SurfaceStyle`, `CellColours`, `LabelStyle`, `AxesMarkerStyle`), `CameraPose`, `PointerEvent`, `Pick`. Farben als Hexwert (`rgb`, `hex_of`) |
| `vtk_renderer.py` | VTK direkt, ohne die PyVista-Hülle: `vtkPolyData` aus NumPy, Aktoren, Farbleitern, Beschriftungen über `vtkLabelPlacementMapper`, Zell-Picking, Bildaufnahme, FXAA, SSAO, Achsenkreuz, der Lichtsatz `vtkLightKit`, den PyVista aufstellte. Qt-Einbettung über VTKs eigenes `QVTKRenderWindowInteractor`; ohne Fenster (`offscreen=True`) für Agentenbilder und Tests |
| `gfx_renderer.py` | pygfx über wgpu (Vulkan, Metal, DX12), derselbe Vertrag: Netze als `gfx.Mesh` mit Flächenfarben, Linien mit NaN-Brüchen, Punkte, Text im Bildraum mit einem Feld dahinter, Picking **aus dem Bildpuffer** (pygfx schreibt je Bildpunkt Objekt und Dreieck; ein Pick zeichnet vorher nur das Pickbare), Durchscheinendes gewichtet gemischt (`weighted_blend`, reihenfolgeunabhängig), derselbe Lichtsatz wie bei VTK, das Achsenkreuz als zweites Teilbild. Qt-Einbettung über `rendercanvas.qt.QRenderWidget` als eigene Grafikfläche (`present_method="screen"`); ohne Fenster über `rendercanvas.offscreen`. Was er nicht kann, ist ein Loch: keine Umgebungsverdeckung, `force_opaque` ohne Wirkung |
| `choice.py` | Welcher Renderer zeichnet: `SOLIDON_RENDERER` (`vtk` ist Vorgabe, `gfx` der zweite), `available(kind)` als Wache des Viewports, `make_renderer()` als die eine Baustelle — Viewport, seine Bildaufnahme und die Ansichten für den Agenten gehen hindurch. Keine Einstellung in der Oberfläche: Die Entscheidung fällt einmal, im Code |
| `shapes.py` | Die kleinen Netze der Ansicht als NumPy-Felder — Scheibe, Zylinder, Kegel, Pfeil, Würfel, Fläche, Raster, Ringlinie —, damit beide Renderer dasselbe zeichnen und `tests/test_render_shapes.py` sie ohne Fenster nachmisst (geschlossen, nach außen, Volumen nach Formel) |
| `gizmo.py` | Der Bewegungsgriff (§18.11) auf dem Vertrag: drei Pfeile, drei Ringe, Hover über `pick_item`, Zug als Lot des Sichtstrahls auf die Achse beziehungsweise Schnitt mit der Ebene quer dazu. `handle(event)` sagt mit `True`, dass die Geste ihm gehört; `interact_callback` darf die Matrix berichtigen (der Magnet auf 45°). Der Skalierwürfel daneben liegt in `app/ui/scale_widget.py` und ist genauso gebaut |
| `navigator.py` | Die Kameraführung ohne VTK: die Tabelle `_NAVIGATION` (welche Taste in welchem Schema was tut), `turntable_camera` (der Drehteller, der die Ansicht aufrecht hält), `is_click`, und der `Navigator`, der `PointerEvent`s in Drehen, Kippen, Schieben, Radzoom am Zeiger, Körperzug, Malen und die Rückrufe an die Ansicht übersetzt (`NavigatorCallbacks`). Gemessen mit einem Renderer-Doppel in `tests/test_navigator.py` |
| `edges.py` | Die Kantensuche der Ansicht: `feature_edges(vertices, faces, angle)` gibt Knick- und Randkanten als Punktpaare — was `vtkFeatureEdges` tat, als NumPy, damit beide Renderer dieselben Kanten zeichnen und `tests/test_render_shapes.py` sie am Würfel, an der Platte und am Dach nachzählt |

## Drei Festlegungen, die der Viewport voraussetzt

* **Bildpunkte zählen wie Qt** — Ursprung oben links, y nach unten, in
  Gerätepixeln. VTK zählt von unten; `VtkRenderer._flip` rechnet an der
  Grenze um, in `world_to_display`, `display_to_world` und beim Picking.
  pygfx zählt von sich aus wie Qt, nur in logischen Bildpunkten — der
  Renderer rechnet mit dem Geräteverhältnis.
* **Beide stellen VTKs Lichtsatz auf** — Schlüssellicht 50° über und 10°
  rechts der Kamera (0,75), Fülllicht von unten (0,25), zwei Rücklichter
  (0,21), dazu das Frontlicht; `set_headlight` stellt nur das Frontlicht,
  und die Themenwerte des Viewports (`HEADLIGHT`) sind dafür kalibriert.
  Mit dem Frontlicht allein war ein Körper im Fenster fast schwarz (Robert,
  05.09.2026). pygfx schattiert in linearem Licht, VTK auf den sRGB-Werten;
  `HEADLIGHT_GAIN` gleicht das auf rund 15 Prozent an, mehr geht mit einem
  Faktor nicht.
* **Kein Interaktionsstil.** VTKs Trackball ist abgeschaltet; Zeigergesten
  kommen als `PointerEvent` beim Viewport an (`_on_pointer`), der sie erst
  dem Zeiger, dann den Griffen und zuletzt dem Navigator gibt. Die Kamera
  führt der Navigator über den Vertrag (`set_camera_pose`, `dolly`).
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
Linien vor dem Material, Koordinatenrichtung, Kamera — **und zwar über beide
Renderer** (`BACKENDS`, ebenso `test_render_gizmo.py`): Der Vertrag ist erst
dann einer, wenn dasselbe Bild auf beiden entsteht. Fehlt ein wgpu-Adapter,
fällt der pygfx-Zweig als Skip mit Grund aus.

**Am echten Fenster** misst `tools/window_bench.py --renderer vtk|gfx`
(`weg4-figur-formen`, maximiert 3413 x 1369, RTX 4080, 05.09.2026):

| | VTK direkt | pygfx |
|---|---|---|
| Fensterbau + Anzeigen | 2,1 + 0,7 s | 1,7 bis 3,0 + 0,4 s |
| Auswertung bis zum ruhigen Bild | 2,0 bis 5,4 s | 3,5 s (das erste Bild übersetzt die Shader) |
| Zug, je Kamerastellung mit Bild | 6,9 ms (Maximum 13) | 4,9 ms (Maximum 6) |
| Bild ohne Kameraänderung | 7,2 ms | 3,8 ms |
| Arbeitsspeicher nach Öffnen und nach dem Zug | 497 / 492 MiB | 494 / 498 MiB |

Drei Dinge daran haben je einen Lauf gekostet, bevor die Zahlen stimmten:
rendercanvas zeigt ein Qt-Widget von sich aus über eine **Bitmap** an
(zurücklesen, `QPainter`; 20 ms je Bild), `render()` am Widget muss
**synchron** zeichnen (`force_draw`), sonst zählt eine Messung Wünsche statt
Bilder, und pygfx **sortiert nach der Objektposition** — die Körper des
Viewports sitzen alle im Ursprung, deshalb mischt Durchscheinendes gewichtet
statt sortiert. Eines daraus gehört hierher, weil es überrascht:

* **Durchscheinende Körper mischen sich reihenfolgeunabhängig** (VTK 9.6.2,
  ohne Fenster wie mit PyVista gemessen). Der Viewport hängt seine Aktoren
  trotzdem nach Tiefe um (`_order_by_depth`, nach einem Bild vom 03.09.2026);
  `set_draw_order` trägt das als Prop-Reihenfolge weiter, und der Test hält
  fest, dass sie hier nichts ändert.
