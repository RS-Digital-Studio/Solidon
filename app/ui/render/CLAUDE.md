# `app/ui/render/` — die Renderer hinter der 3D-Ansicht

Der Viewport (§18) beschreibt, was im Bild steht; ein Renderer entscheidet,
wie es auf den Schirm kommt. Zwei stehen dahinter, beide hinter derselben
Schnittstelle, beide werden gemessen (Entscheidung Robert, 05.09.2026: „bau
beides und mess“; Gedächtnis `viewport-zwei-renderer-messen`).

## Die Karte

| Datei | Rolle |
|---|---|
| `api.py` | Der Vertrag: `Renderer`, `Item`, `LabelsItem`, die Stile (`SurfaceStyle`, `CellColours`, `LabelStyle`, `AxesMarkerStyle`), `CameraPose`, `PointerEvent`, `Pick`. Farben als Hexwert (`rgb`, `hex_of`) |
| `vtk_renderer.py` | VTK direkt, ohne die PyVista-Hülle: `vtkPolyData` aus NumPy, Aktoren, Farbleitern, Beschriftungen über `vtkLabeledDataMapper` mit gemeinsamen Text-/Feldgrenzen, Zell-Picking, Bildaufnahme, FXAA, SSAO, Achsenkreuz, der Lichtsatz `vtkLightKit`, den PyVista aufstellte. Qt-Einbettung über VTKs eigenes `QVTKRenderWindowInteractor`; ohne Fenster (`offscreen=True`) für Agentenbilder und Tests |
| `gfx_renderer.py` | pygfx über wgpu (Vulkan, Metal, DX12), derselbe Vertrag: Netze als `gfx.Mesh` mit Flächenfarben, Körperkanten als Drahtgitter-Mesh über derselben Geometrie (`depth_compare="<="`, keine Kantenliste auf der CPU — die kostete am 3,15-Millionen-Dreiecke-Baum 5,8 s und 114 MB je Aufbau), Linien mit NaN-Brüchen, Punkte, Text im Bildraum mit einem Feld dahinter. Picking aus dem Bildpuffer mit genauem Sichtstrahlpunkt, wiederverwendetem Pickdurchgang und gebündelter Treffertoleranz. Durchscheinendes gewichtet gemischt (`weighted_blend`, reihenfolgeunabhängig), `force_opaque` über `solid`, derselbe Lichtsatz wie bei VTK, das Achsenkreuz als zweites Teilbild. Qt-Einbettung über `rendercanvas.qt.QRenderWidget` als eigene Grafikfläche (`present_method="screen"`); ohne Fenster über `rendercanvas.offscreen` |
| `gfx_occlusion.py` | Umgebungsverdeckung in zwei pygfx-`EffectPass`-Durchgängen: rekonstruiert Kamerapunkte aus Tiefe und inverser Projektion, tastet acht Richtungen in vier Abständen mit festem Bildortversatz ab und glättet den Verdeckungsfaktor tiefen- und normalengeführt. Radius und Bias in Millimetern. Nur der Faktor wird auf die ursprüngliche Farbe multipliziert; Farbkanten, Alpha, Tiefe und Picks bleiben erhalten. Der Renderer schattiert deckende Flächen und zeichnet erst danach Durchscheinendes, Linien, Beschriftungen und Achsen |
| `gfx_lines.py` | Eigene pygfx-Linienmaterialien gegen koplanare Rasterlücken. Der Vertexshader versetzt nur die Rastertiefe um einen Bildpunkt im Kameraraum; frühe Tiefenprüfung, Verdeckung und ursprüngliche Weltkoordinaten bleiben bestehen |
| `choice.py` | Welcher Renderer zeichnet: `gfx` ist die Vorgabe (`DEFAULT_BACKEND`, Entscheidung Robert 06.09.2026), `SOLIDON_RENDERER=vtk` wählt den zweiten; `available(kind)` als Wache des Viewports, `make_renderer()` als die eine Baustelle — Viewport, seine Bildaufnahme und die Ansichten für den Agenten gehen hindurch. Keine Einstellung in der Oberfläche: Die Entscheidung fällt einmal, im Code |
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
  Ein sichtbarer VTK-Renderer auf Windows stellt nach dem ersten Bild den
  WGL-Kontext ein einziges Mal auf `SetSwapControl(0)`, sofern verfügbar.
  Windows komponiert die Ausgabe; eine zusätzliche Bildwechselwartezeit
  gehört nicht in den Qt-Hauptthread. Bildpuffer und andere Plattformen
  behalten ihre bisherige Präsentation.
* **GFX-Picks trennen Treffer und Maß.** Der GPU-Puffer nennt das Dreieck;
  dessen Weltpunkt entsteht aus Sichtstrahl und ursprünglichen Float64-Ecken.
  Die quantisierten baryzentrischen Werte der GPU dienen nur als Rückfall.
  Ein Treffer am Rasterrand bleibt auf dem Dreieck. Die Toleranz von
  `pick_surface` ist wie bei VTK ein Anteil der Fensterdiagonale.
  Unpickbares nimmt am Pickdurchgang nicht teil. Unveränderte Kamera, Größe,
  Auswahlfilter und Szene verwenden ihn wieder; jede Item-Änderung und jedes
  gewöhnliche Bild verwerfen ihn. Der kleine Toleranzbereich wird in einem
  Zug gelesen. Eine Grafikfläche ohne Breite oder Höhe liefert ohne
  GPU-Aufruf keinen Treffer, auch bei noch wartenden Zeigerereignissen.
  Der Zugriff auf pygfxs Texturformat ist hier bewusst begrenzt
  und durch echte Picktests gegen die festgelegte Paketversion gesichert.
  Projektionsabfragen synchronisieren die pygfx-Fenstergröße nur bei einer
  Größenänderung. So teilen sämtliche Merkmalsanker die zwischengespeicherten
  Kameramatrizen; Kamera- und Projektionsänderungen invalidiert pygfx selbst.
  Der Hüllquader der Szene (`_scene_bounds`, für Kamerastellung und
  Tiefenbereich zweimal je Bild gefragt) wird je Geometriestand einmal
  gerechnet und lässt Beschriftungen aus, wie VTK seine 2D-Aktoren: pygfx
  rechnet ihn je Objekt rekursiv, und 76 Objekte kosteten 5 ms je Aufruf.
* **Ein GFX-Item hält seinen tatsächlichen Zustand.** Deckkraft und Pickbarkeit
  beginnen beim übergebenen Stil. Geometrieupdates gelten auch für Linien und
  Punkte; Polylinien behalten ihre Trenner. Beschriftungsupdates ersetzen ihre
  Pickregistrierung bei geänderter Objektmenge vollständig. Ihr Feld wird nur bei geänderten Ankern,
  Kamera oder Transformation neu angepasst; Entfernen und Schließen lösen
  die Registrierungen. Die Feldmaße stammen aus dem tatsächlichen Textlayout
  einschließlich proportionaler Glyphen und werden in Gerätepixel umgerechnet.
  Bei sichtbarem Ankerpunkt stehen Text und Feld mit
  Abstand rechts oberhalb davon. Ein unveränderter Textsatz mit neuen Ankern
  verschiebt vorhandene Glyphen, Felder und Punkte; ein Kameralayout baut
  deshalb weder Schriftlayout noch Pickregistrierung neu auf. Die Felder
  behalten auch ihre Zweipunktgeometrie und aktualisieren deren Positionspuffer.
  Wechselt beim Drehen die sichtbare Textliste, bleiben weiterhin sichtbare
  Texte und Felder erhalten, je Textvorkommen ein eigenes Paar. Nur neue Namen
  erzeugen Glyphen; ausgeschiedene Paare werden aus Szene und Picktabellen
  entfernt — aber nicht sofort: Ausgeschiedene Paare ruhen verborgen im Baum
  (`IDLE_LABEL_LIMIT`), ohne Pickregistrierung, und kehren mit ihrem Namen
  ohne neues Glyphenlayout und ohne Shaderaufbau zurück. Beim Drehen wechselt
  die sichtbare Liste in fast jedem Bild; am Drillholder (157 Namen, 1600 ×
  1000) kostete der Neuaufbau von fünf Texten je Bild rund 25 ms — gemessen
  mit dem Profiler 66 gegen 34 ms je Kamerastellung (mit dem Hüllquader-Cache
  darunter). Reine Umordnung behält
  die Registrierung und passt die Zeichenreihenfolge an. Sichtbare Ankerpunkte
  behalten ihr Objekt auch bei geänderter Anzahl und ersetzen dann nur den Puffer.
  Überlagerungen werden in fester Folge gezeichnet: Linien und Punkte,
  Beschriftungsfelder, Schrift. Ein deckendes Feld verdeckt dadurch die bis
  zum Textanker reichende Verbindung, unabhängig von der Erzeugungsreihenfolge.
* **Umgebungsverdeckung bleibt eine Darstellung.** GFX nutzt sie ausschließlich
  für deckende Netze. Hintergrund und Überlagerungen werden nicht abgedunkelt;
  durchscheinende Flächen behalten ihre gewichtete Mischung und Tiefenprüfung.
  Der Effekt arbeitet vor der abschließenden Kantenglättung. Seine Texturen
  gehören pygfx und folgen dessen Fenstergröße; es gibt keine Bildkopie zur CPU.
  VTK verwendet seine vorhandenen Renderpässe in fester Folge: Kamerapass
  im SSAO-Farbpuffer für den Hintergrundverlauf, deckende Geometrie,
  reihenfolgeunabhängige Transparenz, optional FXAA, Volumen und Überlagerungen.
  Der SSAO-Positionspuffer ist in VTK auf RGBA16F festgelegt; der wirksame
  Bias unterschreitet deshalb keine Abstandsstufe an der Kamerafernebene.
  Kameraänderungen aktualisieren diesen Abstand vor dem Zeichnen. AO-aus
  hängt den eigenen Pass ab, FXAA-aus entfernt seine tatsächliche Stufe.
  Beim Schließen werden auch abgehängte Passressourcen im noch lebenden
  Kontext freigegeben. Tiefenwerte, Auswahl und 2D-Beschriftungen bleiben
  außerhalb dieser Farbkorrektur.
* **VTK-Beschriftungsfelder teilen die Textgrenzen.** Der direkte
  `vtkLabeledDataMapper` zeichnet jeden Eintrag genau einmal. Ein gebündelter
  `vtkPolyDataMapper2D` stellt die Felder aus echten `vtkTextRenderer`-Bounds
  plus `margin` vor die zentrierte Schrift; Rand und Mitte verwenden dieselbe
  Deckkraft. Der native FreeType-Rahmen bleibt aus, da sein Alpha immer
  deckend ist. Ein deckendes Feld verdeckt das innere Stück einer Verbindung
  zum Textanker. `always_visible=True` zeichnet sämtliche Texte; andernfalls
  filtert eine deterministische Rechteckprüfung in Eingabereihenfolge Text
  und Hintergrund gemeinsam. Punkte an den Originalankern bleiben erhalten.
  Schriftmaße hängen nur von Text, Stil und DPI ab; Anker, Kamera und
  Fenstergröße aktualisieren das Layout. Gleich große Felder behalten ihren
  Eckenpuffer. Ein Render-Start-Beobachter deckt auch native Neuzeichnung und
  Bildaufnahme ab; beim Schließen wird er entfernt. Alle zugehörigen Props
  reisen gemeinsam durch Sichtbarkeit, Zeichenreihenfolge und Entfernung.
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

`tests/test_render_gfx_regressions.py` ergänzt die GFX-spezifischen
Fehlerpfade: unpickbare Vorderflächen, laufende Linien- und Punktvorschauen,
erneuerte Beschriftungen, Deckkraft, genaue Weltpunkte und die Lebensdauer
des Pickdurchgangs. Die Prüfungen lesen tatsächliche Bilder und Treffer.

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
