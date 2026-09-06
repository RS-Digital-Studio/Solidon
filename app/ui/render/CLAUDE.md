# `app/ui/render/` — der Renderer hinter der 3D-Ansicht

Der Viewport (§18) beschreibt, was im Bild steht; der Renderer entscheidet,
wie es auf den Schirm kommt. Er steht hinter einem Vertrag (`api.py`), und
hinter dem Vertrag steht seit dem 06.09.2026 **einer**: pygfx über wgpu
(Entscheidung Robert, nach der Modellabnahme mit zwei Renderern;
Gedächtnis `viewport-zwei-renderer-messen`). Der zweite, VTK direkt, war die
Messlatte und ist ausgebaut; das Paket `vtk` bleibt als kopflose
Geometriebibliothek der Bereichsprüfung (`core/knowledge/parts/range_check.py`)
und hat mit diesem Verzeichnis nichts mehr zu tun.

## Die Karte

| Datei | Rolle |
|---|---|
| `api.py` | Der Vertrag: `Renderer`, `Item`, `LabelsItem`, die Stile (`SurfaceStyle`, `CellColours`, `LabelStyle`, `AxesMarkerStyle`), `CameraPose`, `PointerEvent`, `Pick`. Farben als Hexwert (`rgb`, `hex_of`). Was der Viewport, der Skizzeneditor, die Griffe und die Werkzeuge vom Bild wissen, wissen sie von hier |
| `factory.py` | Die eine Baustelle: `make_renderer()` baut den Renderer — mit Qt-Widget unter einem Elternfenster oder ohne Fenster für Agentenbilder und Tests —, und `available()` fragt **vor** dem Aufbau den wgpu-Adapter, weil ein Renderer ohne Adapter nicht höflich stirbt, sondern mit dem Prozess. Viewport, seine Bildaufnahme (`snapshots.py`) und der Fensterprüfstand gehen hindurch; keine Einstellung in der Oberfläche, die Entscheidung fällt einmal, im Code |
| `gfx_renderer.py` | pygfx über wgpu (Vulkan, DX12, Metal): Netze als `gfx.Mesh` mit Flächenfarben, Körperkanten als Drahtgitter-Mesh über derselben Geometrie (`depth_compare="<="`, keine Kantenliste auf der CPU — die kostete am 3,15-Millionen-Dreiecke-Baum 5,8 s und 114 MB je Aufbau), Linien mit NaN-Brüchen, Punkte, Text im Bildraum mit einem Feld dahinter. Picking aus dem Bildpuffer mit genauem Sichtstrahlpunkt, wiederverwendetem Pickdurchgang und gebündelter Treffertoleranz. Durchscheinendes gewichtet gemischt (`weighted_blend`, reihenfolgeunabhängig), `force_opaque` über `solid`, der Lichtsatz `LIGHT_KIT`, das Achsenkreuz als zweites Teilbild mit eigener orthografischer Kamera. Qt-Einbettung über `rendercanvas.qt.QRenderWidget` als eigene Grafikfläche (`present_method="screen"`); ohne Fenster über `rendercanvas.offscreen` |
| `gfx_occlusion.py` | Umgebungsverdeckung in zwei pygfx-`EffectPass`-Durchgängen: rekonstruiert Kamerapunkte aus Tiefe und inverser Projektion, tastet acht Richtungen in vier Abständen mit festem Bildortversatz ab und glättet den Verdeckungsfaktor tiefen- und normalengeführt. Radius und Bias in Millimetern. Nur der Faktor wird auf die ursprüngliche Farbe multipliziert; Farbkanten, Alpha, Tiefe und Picks bleiben erhalten. Der Renderer schattiert deckende Flächen und zeichnet erst danach Durchscheinendes, Linien, Beschriftungen und Achsen |
| `gfx_lines.py` | Eigene pygfx-Linienmaterialien gegen koplanare Rasterlücken. Der Vertexshader versetzt nur die Rastertiefe um einen Bildpunkt im Kameraraum; frühe Tiefenprüfung, Verdeckung und ursprüngliche Weltkoordinaten bleiben bestehen |
| `shapes.py` | Die kleinen Netze der Ansicht als NumPy-Felder — Scheibe, Zylinder, Kegel, Pfeil, Würfel, Fläche, Raster, Ringlinie —, damit Viewport, Griffe und Achsenkreuz dieselben Körper zeichnen und `tests/test_render_shapes.py` sie ohne Fenster nachmisst (geschlossen, nach außen, Volumen nach Formel) |
| `gizmo.py` | Der Bewegungsgriff (§18.11) auf dem Vertrag: drei Pfeile, drei Ringe, Hover über `pick_item`, Zug als Lot des Sichtstrahls auf die Achse beziehungsweise Schnitt mit der Ebene quer dazu. `handle(event)` sagt mit `True`, dass die Geste ihm gehört; `interact_callback` darf die Matrix berichtigen (der Magnet auf 45°). Der Skalierwürfel daneben liegt in `app/ui/scale_widget.py` und ist genauso gebaut |
| `navigator.py` | Die Kameraführung auf dem Vertrag: die Tabelle `_NAVIGATION` (welche Taste in welchem Schema was tut), `turntable_camera` (der Drehteller, der die Ansicht aufrecht hält), `is_click`, und der `Navigator`, der `PointerEvent`s in Drehen, Kippen, Schieben, Radzoom am Zeiger, Körperzug, Malen und die Rückrufe an die Ansicht übersetzt (`NavigatorCallbacks`). Gemessen mit einem Renderer-Doppel in `tests/test_navigator.py` |
| `edges.py` | Die Kantensuche der Ansicht: `feature_edges(vertices, faces, angle)` gibt Knick- und Randkanten als Punktpaare, in NumPy, damit `tests/test_render_shapes.py` sie am Würfel, an der Platte und am Dach nachzählt. Der Renderer zeichnet Körperkanten heute über das Drahtgitter und braucht sie dafür nicht mehr; die Ansicht braucht sie für Maßlinien und Konturen am dezimierten Netz |

## Festlegungen, die der Viewport voraussetzt

* **Bildpunkte zählen wie Qt** — Ursprung oben links, y nach unten, in
  Gerätepixeln; `world_to_display`, `display_to_world` und die Picks rechnen
  so. pygfx zählt von sich aus wie Qt, nur in logischen Bildpunkten — der
  Renderer rechnet mit dem Geräteverhältnis um. (VTK zählte von unten, und
  `_flip` rechnete an der Grenze; das ist mit ihm gegangen.)
* **Der Lichtsatz ist `LIGHT_KIT`** — Schlüssellicht 50° über und 10° rechts
  der Kamera (0,75), Fülllicht von unten (0,25), zwei Rücklichter (0,21), dazu
  das Frontlicht; `set_headlight` stellt nur das Frontlicht, und die
  Themenwerte des Viewports (`HEADLIGHT`) sind dafür kalibriert. Die Zahlen
  sind die von VTKs `vtkLightKit`, wie PyVista sie aufstellte: Mit dem
  Frontlicht allein war ein Körper im Fenster fast schwarz (Robert,
  05.09.2026). pygfx schattiert in linearem Licht, nicht auf sRGB-Werten;
  `HEADLIGHT_GAIN` gleicht das auf rund 15 Prozent an das frühere Bild an,
  mehr geht mit einem Faktor nicht.
* **Kein Interaktionsstil des Renderers.** Zeigergesten kommen als
  `PointerEvent` beim Viewport an (`_on_pointer`), der sie erst dem Zeiger,
  dann den Griffen und zuletzt dem Navigator gibt. Die Kamera führt der
  Navigator über den Vertrag (`set_camera_pose`, `dolly`).
* **Zeichnen an einer Stelle.** Kein Aufruf hier zeichnet von selbst;
  `render()` ruft der Viewport in `_draw`. Am Widget zeichnet `render()`
  **synchron** (`force_draw`), sobald es sichtbar ist — `request_draw` allein
  stellte nur einen Wunsch in die Ereignisschleife, und eine Messung zählte
  dann Wünsche statt Bilder. Ohne Fenster zeichnet `screenshot()` selbst.
* **Das Achsenkreuz hat eine orthografische Kamera** (`AXES_VIEW_SPAN`,
  Pfeillängen von Rand zu Rand des Feldes). Mit Perspektive war ein Pfeil zur
  Kamera hin ein Viertel länger als einer quer dazu, und die Buchstaben
  wanderten je nach Blickrichtung aus dem Feld — in der Vorderansicht fehlten
  X und Z ganz (gemessen 06.09.2026). Ohne Perspektive ist eine Pfeillänge in
  jeder Richtung derselbe Anteil des Feldes, und `_place_axes` zieht den
  Ausschnitt je Blickrichtung auf den längsten sichtbaren Pfeil zusammen —
  schräg von oben sind alle drei verkürzt, und ein fester Ausschnitt ließe
  das Kreuz dort um ein Fünftel schrumpfen. Die Buchstaben sitzen auf den
  Spitzen (`AXES_LABEL_REACH`), und
  `tests/test_render_gfx_regressions.py::test_the_axes_letters_stay_inside_their_field`
  hält in sechs Blickrichtungen fest, dass keiner den Feldrand berührt und
  das Kreuz das Feld füllt. Wo
  das Feld liegt und wie groß es sein darf, entscheidet der Viewport
  (`orientation_corner`, `ORIENTATION_SIZE`).
* **Picks trennen Treffer und Maß.** Der GPU-Puffer nennt das Dreieck;
  dessen Weltpunkt entsteht aus Sichtstrahl und ursprünglichen Float64-Ecken.
  Die quantisierten baryzentrischen Werte der GPU dienen nur als Rückfall.
  Ein Treffer am Rasterrand bleibt auf dem Dreieck. Die Toleranz von
  `pick_surface` ist ein Anteil der Fensterdiagonale.
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
  gerechnet und lässt Beschriftungen aus: pygfx rechnet ihn je Objekt
  rekursiv, und 76 Objekte kosteten 5 ms je Aufruf.
* **Ein Item hält seinen tatsächlichen Zustand.** Deckkraft und Pickbarkeit
  beginnen beim übergebenen Stil. Geometrieupdates gelten auch für Linien und
  Punkte; Polylinien behalten ihre Trenner. Beschriftungsupdates ersetzen ihre
  Pickregistrierung bei geänderter Objektmenge vollständig. Ihr Feld wird nur
  bei geänderten Ankern, Kamera oder Transformation neu angepasst; Entfernen
  und Schließen lösen die Registrierungen. Die Feldmaße stammen aus dem
  tatsächlichen Textlayout einschließlich proportionaler Glyphen und werden
  in Gerätepixel umgerechnet. Bei sichtbarem Ankerpunkt stehen Text und Feld
  mit Abstand rechts oberhalb davon. Ein unveränderter Textsatz mit neuen
  Ankern verschiebt vorhandene Glyphen, Felder und Punkte; ein Kameralayout
  baut deshalb weder Schriftlayout noch Pickregistrierung neu auf. Die Felder
  behalten auch ihre Zweipunktgeometrie und aktualisieren deren
  Positionspuffer. Wechselt beim Drehen die sichtbare Textliste, bleiben
  weiterhin sichtbare Texte und Felder erhalten, je Textvorkommen ein eigenes
  Paar. Nur neue Namen erzeugen Glyphen; ausgeschiedene Paare werden aus
  Szene und Picktabellen entfernt — aber nicht sofort: Ausgeschiedene Paare
  ruhen verborgen im Baum (`IDLE_LABEL_LIMIT`), ohne Pickregistrierung, und
  kehren mit ihrem Namen ohne neues Glyphenlayout und ohne Shaderaufbau
  zurück. Beim Drehen wechselt die sichtbare Liste in fast jedem Bild; am
  Drillholder (157 Namen, 1600 × 1000) kostete der Neuaufbau von fünf Texten
  je Bild rund 25 ms — gemessen mit dem Profiler 66 gegen 34 ms je
  Kamerastellung (mit dem Hüllquader-Cache darunter). Reine Umordnung behält
  die Registrierung und passt die Zeichenreihenfolge an. Sichtbare
  Ankerpunkte behalten ihr Objekt auch bei geänderter Anzahl und ersetzen
  dann nur den Puffer. Überlagerungen werden in fester Folge gezeichnet:
  Linien und Punkte, Beschriftungsfelder, Schrift. Ein deckendes Feld
  verdeckt dadurch die bis zum Textanker reichende Verbindung, unabhängig von
  der Erzeugungsreihenfolge.
* **Umgebungsverdeckung bleibt eine Darstellung.** Sie gilt ausschließlich
  für deckende Netze. Hintergrund und Überlagerungen werden nicht abgedunkelt;
  durchscheinende Flächen behalten ihre gewichtete Mischung und Tiefenprüfung.
  Der Effekt arbeitet vor der abschließenden Kantenglättung. Seine Texturen
  gehören pygfx und folgen dessen Fenstergröße; es gibt keine Bildkopie zur
  CPU. AO-aus hängt den eigenen Pass ab, FXAA-aus entfernt seine tatsächliche
  Stufe. Beim Schließen werden auch abgehängte Passressourcen im noch
  lebenden Kontext freigegeben. Tiefenwerte, Auswahl und Beschriftungen
  bleiben außerhalb dieser Farbkorrektur.
* **Was vorn gezeichnet wird, wird vorn gepickt.** `keep_in_front` heißt
  hier: ohne Tiefentest zeichnen, nach dem Material. Der Pick liest denselben
  Puffer, in den gezeichnet wurde, und trifft deshalb, was zu sehen ist — der
  Skalierwürfel an einem würfelförmigen Körper liegt in dessen Hüllquader und
  wäre sonst nie zu greifen. Die Toleranz von `pick_item` ist eine Zahl in
  Bildpunkten (`PICK_SLACK_PIXELS`).
* **Durchscheinende Körper mischen sich reihenfolgeunabhängig**
  (`weighted_blend`): pygfx sortiert Durchscheinendes je Bild nach dem
  Abstand der Objektposition zur Kamera, und die Körper des Viewports sitzen
  alle im Ursprung — die Sortierung entscheidet dort nichts, die gewichtete
  Mischung braucht sie nicht. `set_draw_order` legt deshalb keine eigene
  Reihenfolge darüber (gemessen: `render_order` hob pygfxs Sortierung auf,
  2304 Bildpunkte anders). Der Viewport hängt seine Körper trotzdem nach
  Tiefe um (`_order_by_depth`, nach einem Bild vom 03.09.2026), weil die
  Regel am Vertrag hängt und nicht an einem Renderer.

## Was gemessen ist

`tests/test_render_contract.py` liest Bildpunkte und Picks vom Renderer ohne
Fenster — Farbe, Deckkraft, Sichtbarkeit, Zellfarben, Beschriftungen,
Linien vor dem Material, Koordinatenrichtung, Kamera; `test_render_gizmo.py`
die Griffe darauf. Fehlt ein wgpu-Adapter, fallen beide als Skip mit Grund
aus, und `tests/test_render_factory.py` hält fest, dass `factory.available()`
das vorher sagt.

`tests/test_render_gfx_regressions.py` ergänzt die Fehlerpfade aus dem
Vergleich echter Importmodelle: unpickbare Vorderflächen, laufende Linien-
und Punktvorschauen, erneuerte Beschriftungen, Deckkraft, genaue Weltpunkte,
die Lebensdauer des Pickdurchgangs, das Achsenkreuz in sechs
Blickrichtungen. Die Prüfungen lesen tatsächliche Bilder und Treffer.

**Am echten Fenster** misst `tools/window_bench.py` (Fensterbau, Auswertung
bis zum ruhigen Bild, Zug je Kamerastellung, Bild im Stand, Arbeitsspeicher).
Die Zahlen, an denen die Entscheidung fiel — VTK gegen pygfx am 05.09.2026,
`weg4-figur-formen` maximiert auf einer RTX 4080: Zug 6,9 gegen 4,9 ms, Bild
im Stand 7,2 gegen 3,8 ms, Speicher gleich —, stehen im Gedächtnis
`viewport-zwei-renderer-messen` und in der Modellabnahme
(`.claude/.state/renderer-audit-2026-09-05-01a07353/ABNAHME.md`, 23
Kundendateien, Leistungsreihe bis 3,15 Millionen Dreiecke, Aufbauprofil).

Drei Dinge daran haben je einen Lauf gekostet, bevor die Zahlen stimmten, und
gelten weiter: rendercanvas zeigt ein Qt-Widget von sich aus über eine
**Bitmap** an (zurücklesen, `QPainter`; 20 ms je Bild — deshalb
`present_method="screen"`), `render()` am Widget muss **synchron** zeichnen
(`force_draw`), sonst zählt eine Messung Wünsche statt Bilder, und das erste
Bild eines Netzes übersetzt die Shader — am 3,15-Millionen-Baum vier
Sekunden, davon rund eine für die Pipelines, eine für die Punktnormalen, die
pygfx auf der CPU rechnet, und eine für den Pufferupload; jedes weitere Bild
kostet 4 ms.
