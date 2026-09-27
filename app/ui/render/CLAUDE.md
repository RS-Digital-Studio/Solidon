# `app/ui/render/` — der Renderer hinter der 3D-Ansicht

Der Viewport (§18) beschreibt, was im Bild steht; der Renderer entscheidet,
wie es auf den Schirm kommt. Er steht hinter einem Vertrag (`api.py`), und
hinter dem Vertrag steht **einer**: pygfx über wgpu — Vulkan, DX12 und
Metal, in virtuellen Maschinen WARP oder lavapipe (Entscheidung Robert, nach
einer Abnahme mit zwei Renderern). VTK direkt war die Messlatte und ist
ausgebaut, PyVista ebenso; das Paket `vtk` ist ganz aus der Anwendung. Wer
einen zweiten Renderer braucht, baut ihn hinter `api.py` und misst ihn mit
`tests/test_render_contract.py`.

Die Regeln stehen in `.claude/rules/ansicht.md` (lädt für alles hier),
`kamera.md` (`navigator.py`, `api.py`) und `griffe.md` (`gizmo.py`).
Messwerte, Anlässe und die Begründung der Renderer-Wahl stehen in
`konzepte/begruendungen/karte-app-ui-render.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `api.py` | Der Vertrag: `Renderer`, `Item`, `LabelsItem`, die Stile (`SurfaceStyle`, `CellColours`, `LabelStyle`, `AxesMarkerStyle`), `CameraPose`, `PointerEvent`, `Pick`; Farben als Hexwert (`rgb`, `hex_of`). `add_lines`/`add_surface` nehmen eine `capacity`, dann tauscht `Item.update_points` nur Zahlen in den Puffern (die Maßtinte). Was Viewport, Skizzeneditor, Griffe und Werkzeuge vom Bild wissen, wissen sie von hier |
| `factory.py` | Die eine Baustelle: `make_renderer()` baut den Renderer mit Qt-Widget oder ohne Fenster (Agentenbilder, Tests). `available()` fragt **vorher** den wgpu-Adapter, denn ein Renderer ohne Adapter stirbt mit dem Prozess; `probe()` stellt die Frage einmal je Prozess beim Start im Arbeiter, `available()` wartet mit Frist (`ADAPTER_TIMEOUT_SECONDS`). Viewport, `snapshots.py` und der Fensterprüfstand gehen hindurch; keine Einstellung in der Oberfläche |
| `gfx_renderer.py` | pygfx über wgpu: Netze mit Flächenfarben, Körperkanten als Drahtgitter-Mesh über derselben Geometrie (`depth_compare="<="`, keine Kantenliste auf der CPU), Linien mit NaN-Brüchen, Punkte, Text im Bildraum mit Feld; Picking aus dem Bildpuffer; `weighted_blend`, `force_opaque` über `solid`, `LIGHT_KIT`, das Achsenkreuz als zweites Teilbild. Qt-Einbettung über `rendercanvas.qt.QRenderWidget` (`present_method="screen"`), ohne Fenster über `rendercanvas.offscreen`. pygfx' Ereignissystem ist aus (`enable_events=False`); abgeräumte Überlagerungen warten je Bauart auf ihre Wiederkehr (`_recycle`, `_reused`, `RECYCLE_PER_KIND`) |
| `gfx_occlusion.py` | Umgebungsverdeckung in zwei `EffectPass`-Durchgängen: acht Richtungen in vier Abständen, im Zug vier in zwei (`apply(light=True)`, über `set_interacting`); nur der Faktor geht auf die Farbe — Farbkanten, Alpha, Tiefe und Picks bleiben |
| `gfx_lines.py` | Linienmaterialien gegen koplanare Rasterlücken: die Rastertiefe um einen Bildpunkt im Kameraraum versetzt, Verdeckung und Weltkoordinaten bleiben |
| `gfx_surfaces.py` | `SurfaceStyle.coplanar_overlay`: ein Achtel Gerätebildpunkt Tiefenversatz; Beleuchtung, Verdeckung und Pickkoordinaten bleiben |
| `shapes.py` | die kleinen Netze der Ansicht (Scheibe, Zylinder, Kegel, Pfeil, Würfel, Fläche, Raster, Ringlinie): Viewport, Griffe und Achsenkreuz zeichnen dieselben Körper, `tests/test_render_shapes.py` misst sie ohne Fenster |
| `gizmo.py` | Der Bewegungsgriff (§18.11): drei Pfeile, drei Ringe, Hover über `pick_item`. `handle(event)` sagt mit `True`, dass die Geste ihm gehört; `interact_callback` darf die Matrix berichtigen (der Magnet auf 45°); gezogen wird erst jenseits von `navigator.CLICK_SLACK` (`dragging`), ein Klick ohne Weg bewegt nichts. `Gizmo(rotation=False)` baut nur die Pfeile. Der Skalierwürfel liegt in `app/ui/scale_widget.py` und ist genauso gebaut |
| `navigator.py` | Die Kameraführung: `_NAVIGATION` (welche Taste in welchem Schema was tut), `turntable_camera`, `is_click`, und der `Navigator` übersetzt `PointerEvent`s in Drehen, Kippen, Schieben, Radzoom, Körperzug und Malen (`NavigatorCallbacks`); `tests/test_navigator.py` misst ihn mit einem Renderer-Doppel |
| `edges.py` | Kanten ohne Renderer: `feature_edges`, `outline_edges` (nach Ort gezählt, damit auch eine Suppe ihren Umriss hat) für Maßlinien und Konturen am dezimierten Netz; `nearest_polyline` misst gegen die **Strecken**, bei gleichem Abstand entscheidet die Tiefe (`SAME_DISTANCE`) — so pickt der Viewport einzelne B-Rep-Kanten |

`__init__.py` trägt nur den Paketdocstring.

## Festlegungen, die der Viewport voraussetzt

* **Bildpunkte zählen wie Qt** — Ursprung oben links, y nach unten, in
  Gerätepixeln; `world_to_display`, `display_to_world` und die Picks rechnen
  so. `device_ratio()` steht am Vertrag mit einer Vorgabe (ohne Fenster 1,0),
  damit jedes Doppel es erbt; der `Navigator` reicht es an `is_click` weiter.
  Punktgrößen und Linienbreiten rechnet pygfx selbst um (`ansicht.md`).
* **Zeichnen an einer Stelle.** Kein Aufruf hier zeichnet von selbst;
  `render()` ruft der Viewport in `_draw`. `render()` bestellt, `render_now()`
  zeichnet sofort (`ansicht.md`). Wer Bilder zählt, zählt `render_now` oder
  die Malereignisse, nicht die Bestellungen; ohne Fenster zeichnen beide
  sofort, und `screenshot()` zeichnet selbst.
* **Kein Interaktionsstil des Renderers.** Zeigergesten kommen als
  `PointerEvent` beim Viewport an (`_on_pointer`, Vorfahrt in
  `_dispatch_pointer`: Griffe, Platzierung, Zeiger, Navigator); die Kamera
  führt der Navigator über den Vertrag (`set_camera_pose`, `dolly`).
  Qt-Mausereignisse außerhalb der Renderfläche kommen über `deliver_pointer`
  in denselben Pfad. Das Rad reist als Bruchteil einer Raste
  (`PointerEvent.delta`, Winkel durch 120, ungerundet) und ist im Navigator
  der Exponent des Zoomfaktors. Verlassen des Bildes nimmt eine
  Griffhervorhebung zurück und zeichnet sofort; ein laufender Zug behält sie.
* **pygfx' Ereignissystem ist aus** (`enable_events=False`): Es läse für jedes
  Zeigerereignis den Pickpuffer zurück, und niemand hört darauf.
  `disable_events` wirkt nachträglich nicht — rendercanvas vergleicht die
  gebundene Methode mit `is`.
* **Ein abgeräumtes Element kommt mit seinen Objekten wieder.** `remove` hebt
  ein Element auf, dessen Bauart feststeht (`recycle_key`) und das nicht
  umgestellt wurde (`restyled`); das nächste `add_*` gleicher Bauart füllt
  dessen Puffer (`_fill`, `filled`), Pipeline und Bindungen bleiben, das alte
  behält eine leere Gruppe (`retired`), den Hüllquader rechnet
  `_filled_bounds`, Beschriftungen übernehmen ihre Paare (`GfxLabels.adopt`).
  Höchstens drei je Bauart, zusammen 32 MB; `close` leert den Vorrat.
* **Ein Zug darf leichter zeichnen, sein letztes Bild nicht** (`ansicht.md`);
  `set_interacting` und `frame_was_reduced` sind am Vertrag Vorgaben, die
  nichts tun.
* **Licht.** Der Lichtsatz ist `LIGHT_KIT` (Werte und Herkunft am
  Konstantenkommentar); `set_headlight` stellt nur das Frontlicht, und die
  Themenwerte des Viewports (`HEADLIGHT`) sind dafür kalibriert.
  `HEADLIGHT_GAIN` gleicht aus, dass pygfx in linearem Licht schattiert. Ein
  gerichtetes Licht dreht sich nicht je Bild (`_directional_light` schreibt
  nur die Richtung — hier wirft kein Licht Schatten). Deckende Körper
  reflektieren schwach und breit, damit auch schwarzes Filament Form zeigt;
  `SurfaceStyle.specular` überschreibt das, auch mit null. Quelldaten,
  Materialslots und exportierte Farben bleiben.
* **Vorbauen.** `warm_glyphs(text)` legt Zeichen in pygfx' Atlas, ohne etwas
  ins Bild zu stellen (die Ansicht ruft es im Leerlauf); `surface_normals`
  ist eine reine Rechnung, die ein Arbeiter stellt, und
  `add_surface(normals=…)` übernimmt sie, wenn die Form passt.
* **Das Achsenkreuz hat eine orthografische Kamera** (`AXES_VIEW_SPAN`):
  `_place_axes` zieht den Ausschnitt je Blickrichtung auf den längsten
  sichtbaren Pfeil zusammen, die Buchstaben sitzen auf den Spitzen
  (`AXES_LABEL_REACH`). Wo das Feld liegt und wie groß es ist, entscheidet
  der Viewport (`orientation_corner`, `ORIENTATION_SIZE`).
* **Picks trennen Treffer und Maß.** Der GPU-Puffer nennt das Dreieck, der
  Weltpunkt entsteht aus Sichtstrahl und ursprünglichen Float64-Ecken. Die
  Toleranz von `pick_surface` ist ein Anteil der Fensterdiagonale, die von
  `pick_item` eine Zahl in Logikpunkten (`PICK_SLACK_PIXELS`). Der
  Pickdurchgang wird bei gleicher Kamera, Größe, Auswahl und Szene
  wiederverwendet; eine Fläche ohne Breite oder Höhe liefert ohne GPU-Aufruf
  keinen Treffer. `_scene_bounds` rechnet je Geometriestand einmal, ohne
  Beschriftungen und ohne, was vorn gezeichnet wird.
* **Was vorn gezeichnet wird, wird vorn gepickt** (`keep_in_front`: ohne
  Tiefentest, nach dem Material) und zählt nicht in den Hüllquader
  (`GfxItem.in_front`, `ansicht.md`).
* **Ein Item hält seinen tatsächlichen Zustand**: Rückseiten und Kanten folgen
  der Deckkraft des Körpers; Beschriftungen behalten Paare, Felder und Punkte
  und verschieben sie bei neuen Ankern, ausgeschiedene Paare ruhen verborgen
  (`IDLE_LABEL_LIMIT`). Überlagerungen zeichnen in fester Folge: Linien und
  Punkte, Beschriftungsfelder, Schrift.
* **Umgebungsverdeckung bleibt eine Darstellung** — nur deckende Netze, vor
  der Kantenglättung (`ppaa`), ohne Bildkopie zur CPU; ihre Texturen gehören
  pygfx.
* **Durchscheinendes mischt sich reihenfolgeunabhängig** (`weighted_blend`);
  `set_draw_order` legt keine eigene Reihenfolge darüber (`ansicht.md`).

## Prüfen und messen

`tests/test_render_contract.py` liest Bildpunkte und Picks ohne Fenster,
`test_render_gizmo.py` die Griffe darauf; fehlt ein wgpu-Adapter, fallen
beide als Skip mit Grund aus, und `tests/test_render_factory.py` hält fest,
dass `factory.available()` das vorher sagt, die Adapterfrage einmal je Prozess
fällt und `app/ui/app.py` sie vorzieht. In der CI ist ein fehlender Adapter
ein Fehler, und ein eigener Prozess prüft den nativen Qt-Fensterweg samt
Freigabe. `tests/test_render_gfx_regressions.py` hält die Fehlerpfade aus
echten Importmodellen fest, an tatsächlichen Bildern und Treffern.
`tests/test_window_memory.py` prüft den Abbau: Beim Fensterende und
Sprachwechsel wird der Renderer geschlossen, bevor Qt sein Fenster abbaut; die
Widgetklasse hält ihn nur schwach, und sein Abbau stört keinen anderen
Renderer im Prozess (`tools/window_memory.py` misst dasselbe am Fenster).

**Am echten Fenster** misst `tools/window_bench.py` (Fensterbau, Auswertung
bis zum ruhigen Bild, Zug je Kamerastellung, Bild im Stand, Speicher). Drei
Fallen gelten dabei weiter: rendercanvas zeigt ein Qt-Widget von sich aus über
eine Bitmap (deshalb `present_method="screen"`); gezählt werden Bilder, nicht
Bestellungen (`render_now`); und das erste Bild eines Netzes übersetzt die
Shader — am 3,15-Millionen-Baum vier Sekunden, jedes weitere Bild 4 ms. Der
Bildtakt von rendercanvas (`max_fps=30`) bremst nichts (`ansicht.md`).
