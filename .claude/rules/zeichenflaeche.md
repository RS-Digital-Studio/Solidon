---
description: "Das Aufziehen in der Ansicht (drei Klicks, Richtung entscheidet) und der Skizzeneditor — Vorschau und Fang am Zeiger, Raster und Maßstab, gezogene Punkte und Zwangsbedingungen, Maßkarten, Form- und Lochwerkzeuge, die Karte unten, Ebenen und Flächenkontur, Ellipse und Kurvenbedingungen, der Zielkörper"
paths:
  - "app/ui/sketch_editor.py"
  - "app/ui/draw_*.py"
---

# Regeln für die Zeichenfläche

Das Aufziehen (`app/ui/draw_tool.py`, `draw_flow.py`, `draw_bar.py`) und der
Skizzenmodus (`app/ui/sketch_editor.py`, gezeigt im Viewport). Texte,
Barrierefreiheit und Zeiger regelt `oberflaeche.md`, die Ansicht `ansicht.md`,
das Warten `wartezeit.md`; sie gelten mit. Anlässe, Messwerte und die Mechanik
im Einzelnen stehen unter denselben Überschriften in
`konzepte/begruendungen/regel-zeichenflaeche.md`.

## Körper aufziehen: drei Klicks, ein Schritt

*Zeichnen* oben (Strg+Umschalt+E, Fusion E) ist das Aufziehen (RM-559,
RM-561; Bauplan §30.1). Warum: `konzepte/begruendungen/regel-zeichenflaeche.md`.

* **Die Bedeutung jedes Klicks steht in `draw_tool.py`** (`DrawDraft`,
  `lifted`, `picture`) und wird ohne Fenster geprüft; `DrawFlow` übersetzt
  nur Mausstellen in `take`/`aim`/`place`/`lift_to`/`settle`.
* **Kein Moduswechsel:** Ansicht, Projektion und Nachbarn bleiben; die
  linke Taste gehört dem Entwurf über `set_placement_pointer`, Rad und
  rechte Taste der Kamera. Die Werkzeugzeile weicht der `DrawBar`.
* **Die Richtung des dritten Klicks entscheidet**, kein Schalter: auf dem
  Bett `sketch_extrude`, aus einer Fläche heraus `sketch_join`, hinein
  `sketch_pocket`, an der Gegenwand `through` (`reach_inside`). Ziel ist der
  Körper der angeklickten Fläche, auf dem Bett ein neuer.
* **Kein Dialog, ein Einmalwerkzeug:** Klick 3 legt den Schritt an, das
  Werkzeug schließt, der Körper wird gewählt. Überdeckung (F-g) und Zerfall
  (F-h) sagen es mit Knöpfen in der Statuszeile, nichts geschieht von selbst.
  Eine Absage beim Anlegen lässt den Entwurf stehen.
* **Überdeckung ist echtes Volumen:** Die Hüllquader filtern vor, die
  Schnittmenge rechnet `_OverlapWorker` an Arbeiterkopien; der Satz kommt
  erst mit ihr, eine Tasche wartet auf ihr neues Ergebnis (`_before_step`).
* **Escape nimmt nur Unfertiges** (das offene Maßfeld, dann den Entwurf),
  **Strg+Z im Entwurf den letzten Klick** (`DrawDraft.back`), danach den
  Schritt; ohne Klick sagt es den Weg. Ein Umriss aus dem Editor ist kein
  Unfertiges: Strg+Z führt in den Editor zurück, Escape, *Schließen* und ein
  verschwundenes Ziel (F-k) legen ihn als verworfene Zeichnung ab
  (`return_the_outline`). Ungesichert ist nur er, nicht ein Klick.
* **Andere Handlungen warten** (`_quiet_command_allowed`,
  `_drawing_refuses`) und sagen es im Tooltip (`_DRAWING_FIRST`); *Zeichnen*
  steht gedrückt, ein zweiter Druck schließt.
* **Aufgezogen heißt bemaßt** (`shapes.rectangle_between`, `circle_around`):
  beide Maße als Bedingung, die erste Ecke fest — anders als im Editor. Ein
  Maß im Schrittdialog wächst um diesen Punkt (`shapes.held_point`).
* **Die Art wechselt am Schritt** (`_kind_choice`, `History.change_kind`
  über `change_kernel`): alle Arten der Zeichnungsfamilie, eine ohne Körper
  gesperrt mit Grund. Ersetzt wird in einer Transaktion.
* **Die Höhe** liest `axis_hit` an der Mitte des Umrisses; steht der Blick
  innerhalb `STEEP_DEGREES` auf der Normalen, folgt sie der senkrechten
  Mausbewegung. Gefangen auf das Raster, Grenzen aus dem Schema
  (`operation_limits`). **Null bleibt null:** Unter einem halben
  Rasterschritt und in eine Richtung ohne Körper (F-e) ist die Höhe null, der
  Klick legt nichts an.
* **Getippt ist ein Betrag in der Richtung, die beim Öffnen des Felds galt**;
  danach ändert die Maus sie nicht mehr, ein Minus kehrt um. Eine gewählte
  Tasche (`inward_first`) tippt die Tiefe. Fehlt die Tiefe des Rechtecks,
  gilt die am Zeiger.
* **Höhe und Tiefe unterscheiden sich ohne Farbe** (Regel 18): außen
  durchgezogen und *Höhe*, innen gestrichelt und *Tiefe* (`_dashes`).
* **Ecken und Kantenmitten der Fläche schlagen das Raster** (`face_marks`),
  in logischen Bildpunkten (`MARK_REACH_PIXELS` mal Geräteverhältnis).
* **Ein Weg vom Umriss zum Körper** (RM-561): *Freie Form …* öffnet den
  Editor auf der Fläche mit der Linie in der Hand; *Fertig* bringt jeden
  geschlossenen freien Umriss und den für Hochziehen, Anfügen oder Tasche
  zurück in die Ansicht, es fehlt die Höhe (`_rise_from_the_sketch`). Ein
  offener bleibt im Editor mit Satz, eine Tasche ohne Ziel ebenso. Andere
  Arten, ein geänderter Schritt und gegebene Werte (`finish_sketch(given=…)`)
  öffnen ihren Dialog.

## Was entsteht, steht am Zeiger

* **Linie, Kreis und Bogen zeigen ihre Vorschau am Zeiger**, bis der Klick sie
  festmacht.
* **Gefangen wird auf das Raster, ein vorhandener Punkt schlägt es** — sonst
  risse der Fang die Deckung auf. Der Haken „Am Raster fangen" steht an der
  Ebenenzeile, an ist die Vorgabe; derselbe Fang gilt beim Ziehen eines
  Punktes.
* **Was ein Klick tut, entscheidet die Methode, die auch ein Test ruft**
  (`place`, `grab_point`); die Ereignisse übersetzen nur.
* **Ein Klick auf einen Punkt greift ihn** (`grab_point`, beim Auswählen und
  beim Punktwerkzeug), statt einen zweiten deckungsgleich daraufzusetzen. Bei
  Linie, Kreis und Bogen bleibt der Fang: Dort ist der Punkt der Anfang.
* **Was ein Klick greifen würde, leuchtet auf** (`_note_hover`, Fangradius
  acht Bildpunkte); die Auswahl unterscheidet sich nicht allein über die Farbe
  (Regel 18).
* **Der Zeiger sagt, was ein Klick tut**, auch auf der Zeichenfläche
  (`SketchCanvas.set_tool` über `cursors.cursor`; die Rolle `draw` ist die
  Systemform `CrossCursor`).
* **Jedes Zeichenwerkzeug nennt in jedem Schritt, was der nächste Klick tut**
  (`drawing_hint`), auch dass Esc den Linienzug beendet. Sobald etwas
  gezeichnet ist, hängt `status_text` „Esc wechselt zum Auswählen und Ziehen."
  an.
* **Wo der Zeiger steht, steht in der Zeile** (`pointer_target`,
  `SketchPanel._show_pointer`) — der Ort, an dem ein Klick landet, nicht die
  rohe Lage. Genaue Zahlen gibt das Kontextmenü am Punkt (`edit_point`, mit
  eigenem `_remember()`).
* **Was im Konstruktor gesetzt wird, kommt vor den Verbindungen:**
  `SketchPanel` setzt die Skizze vor `sketchChanged` und frischt am Ende des
  Konstruktors beide Anzeigen von Hand auf — ein Signal ersetzt nicht den
  ersten Aufruf.

## Raster und Maßstab

* **Eine Zahl für Raster im Bild und Fang:** `SketchPanel.follow_grid` gibt die
  Weite, die `_redraw_sketch` gezeichnet hat, an Canvas **und** Feld; was der
  Viewport zuletzt gezeichnet hat, steht in `_sketch_step`.
* **Eine eingetippte Weite bleibt** (`_pinned_step`), das Raster folgt ihr; die
  Null gibt sie zurück („Automatisch", `setSpecialValueText`) — eine
  Einstellung ohne Rückweg wäre eine Sackgasse (§2.1). Kein eigener Haken
  „Auto".
* **Gesetzt wird unter `QSignalBlocker`**, sonst nagelte der erste Zoomschritt
  die Weite fest. **Die Eingabe muss ins Bild:** `_snapping_changed` sendet
  `sketchChanged`.
* **`LEAST_SNAP_MM` hebt eine zu kleine Eingabe an, statt sie zu verschlucken**
  — der Sonderwert zwingt das Minimum des Feldes auf null.
* **Gemessen wird erst, wenn es ein Bild gibt** (`LEAST_VIEW_PIXELS`): Ein
  Widget ohne Layout meldet 100 × 30 Bildpunkte; `start_sketch` zieht die Weite
  über `QTimer.singleShot(0, …)` nach.
* **Raster und Beschriftung folgen dem Maßstab** (`grid_step`, Folge 1, 2, 5).
  Er kommt aus der Kamera, nicht vom unsichtbaren Canvas (§30.1):
  `Viewport.pixels_per_mm(frame)` misst über zwei projizierte Weltpunkte, in
  beiden Projektionen richtig, und beide Seiten rechnen `grid_step_for(scale)`.

## Wohin ein Klick fällt, und die Fangmarke

* **Wohin ein Klick fällt, steht im Bild** (`Viewport.show_sketch_cursor`,
  `sketch_cursor`) — der Fang versetzt ihn bis zu einem halben Schritt. Der Ort
  kommt aus `pointer_target()` über `SketchPanel.pointerMoved`, nie
  nachgerechnet; beim Auswahlwerkzeug ist er absichtlich die rohe Lage.
* **Die Größe steht in Bildpunkten** (`CURSOR_PIXELS`), nicht in Millimetern
  oder als Rasteranteil. Ein gesetzter Punkt bleibt kräftiger als die Marke
  (`SKETCH_POINT_PIXELS >= CURSOR_PIXELS`, geprüft in
  `tests/test_sketch_editor.py`): Kugel gegen Kreuz, zwei Formen.
* **Die Marke hat eigene Aktoren** (`_cursor_actors`) und verschwindet in
  `set_sketching` (nicht in `finish_sketch`) bei **jedem** Aufruf, auch beim
  Ebenenwechsel.
* **Ein Zeigerschritt, der nichts ändert, zeichnet nicht** — ein Bild ist teuer,
  und Zeigerereignisse kommen dicht. Verglichen werden gefangener Ort **und**
  Maßstab.
* Fangmarke, `pending_elements()` und der feste Klick lesen dasselbe Ziel aus
  `_placement_target`; ein Mausereignis rendert höchstens einmal.

## Zoom und Schwenk auf einer Ebene

* **Die Zeichenebene wird orthografisch gesehen** (§18.1) — perspektivisch
  wären gleich lange Strecken verschieden lang. Beim Verlassen kommt der Wert
  des Nutzers zurück; `view_on_plane` rechnet `parallel_scale` aus der
  Kameradistanz (`_fit_parallel_scale`).
* **Wer an der Kamera zoomt, geht durch `Renderer.dolly`**, das beide
  Projektionen bedient (orthografisch über den Maßstab, perspektivisch über den
  Abstand); das Rad zoomt auf den Zeiger (`Navigator._zoom_at`), die Tastatur
  über `Viewport.zoom`. Geprüft in
  `test_render_contract.py::test_camera_pose_projection_and_dolly` und
  `test_navigator.py::test_a_wheel_step_keeps_the_point_under_the_pointer`.
* **Die Kamera meldet jede Bewegung zurück** (`Viewport.cameraMoved`, verbunden
  in `start_sketch`, gelöst in `finish_sketch`), am **Ende** einer Bewegung:
  Zugende des Navigators (`on_end` in `_weak_callbacks`); Radzoom,
  Kameravorgaben, 3D-Maus (`settle_camera`) und `show_span_on_plane` melden
  selbst. Je Mausbewegung wäre das Neuzeichnen zu teuer. `_pinned_step`
  gewinnt auch hier.
* **Die Kamera hat eine Untergrenze** (`LEAST_PLANE_DISTANCE`): In der leeren
  Szene von Weg 2 gab es sonst ein Raster von 0,1 mm.
* **Gedreht wird um die Mitte der Körper**, nicht des Sichtbaren samt Platte
  und Bauraum: `rotation_centre()` aus `_object_bounds()`, wie `reset_camera`;
  ohne Körper wird nichts verschoben.

## Die Ebene steht im Bild

* **Jede Ebene trägt ihren Nullring und die Ziffer 0**, auch ohne Zeichnung
  (`Viewport.show_sketch`). Der Ring liegt vor dem Material, bleibt bei jedem
  Zoom und Geräteverhältnis gleich groß und nimmt keine Klicks an. Beim
  Ebenenwechsel wird er neu gesetzt, beim Verlassen mit der Zeichnung geräumt.
* **Benannt nach dem, was man sieht** (Draufsicht, Vorderansicht,
  Seitenansicht), die Ebene in Klammern; Achsenbuchstaben aus `PLANE_AXES`,
  auf einer angeklickten Fläche keine. Die Ziffern 1, 2, 3 gehen über
  `choose_plane`, also über das Auswahlfeld.
* **Das Ebenenfeld zeigt den Blick:** `offer_faces` nimmt zuerst
  `canvas.view_plane`; fällt dessen Fläche weg, wechseln Feld und Kamera auf
  die vorhandene Zeichenebene, sonst XY — die Zeichnung bleibt, wo sie ist.
* **„Neue Ebene …" im Ebenenfeld und als vierte Karte, nicht im Menü**
  (`NewPlaneDialog`, nicht modal über `open`): Vorschau beim Einstellen
  (`SketchCanvas.preview_plane`, kein Schritt), *Abbrechen* stellt her,
  *Übernehmen* ist **ein** Schritt. Eine vorhandene Zeichnung zieht
  ausdrücklich mit (`change_drawing_plane`), und der Dialog sagt das.
* **Welche Ebenen ein Skizzenfeld annimmt, sagt der Parameter**
  (`ParamSpec.sketch_planes`): Eine leere Zeichnung beginnt auf der ersten, das
  Feld bietet nur diese (und die eigene einer älteren Datei), keine Flächen,
  keine neue Ebene, keine Ebenenkarten.
* **Der obere Umriss beginnt auf der Ebene des unteren** (`follow_plane_of`,
  schwach gehalten); **Rückgängig bringt Ebenenfeld und Klickebene mit**
  (`planeRestored`).

## Der Umriss sagt, wie weit er ist

* **Die Zeile beantwortet zuerst „ist es zu?"** (`_outline_state()` über
  `regions_of`, denselben Kern, der später rechnet) — übernommen wird nur Ja
  oder Nein: „Noch offen" oder „Geschlossen", dahinter die Freiheitsgrade.
* **Die Kennzahl bekommt einen Satz** (`outline_advice`): Die Zahl bleibt für
  den Könner, dahinter steht ihre Folge; der Umriss geht vor den
  Freiheitsgraden.
* **Der Zustand steht neben dem Werkzeughinweis** (`state_brief`,
  `status_shows_state`): „Noch offen · noch 3 Maße fehlen".
* **Ein Knopf, der nicht kann, sagt, was ihm fehlt:** Die zehn
  Bedingungsknöpfe folgen der Auswahl (`constraint_offers`), Hinweis und
  Meldung nach einem Kürzel kommen aus einer Quelle (`_needs_phrase`). Was eine
  Bedingung **tut**, sagt `_does_phrase` — am Knopf, im Kontextmenü, in der
  Meldung und an jedem Listeneintrag. Dass **Strg** dazunimmt, steht in der
  Zeile (`selection_hint`).
* **Die Bedingungsliste zeigt nur, was an der Auswahl hängt, dazu jeden
  Widerspruch** (RM-519); die Zählzeile darüber (`constraint_count_text`) nennt
  die Gesamtzahl. Sie folgt `selectionChanged` wie `sketchChanged`, und ihre
  Breite hängt nicht am Text, sonst zoomt der Dialog bei jedem Klick.
  Gedeckte Punkte heißen *Verbunden*.
* **Im Zeichenmodus ist der Reiter Auswahl verborgen** (`start_sketch`,
  `finish_sketch`; `_SelectionPage.reveal` holt ihn nicht). Die Einladung der
  leeren Szene weicht der Skizze (`fenster.md`, „Fenster“).
* **Die Bedingungsliste trägt die Punktnummern auch im Konflikt**; nach ihnen
  sucht, wer eine Meldung des Lösers wiederfinden will.
* **Die festen Punkte der Hilfsgeometrie sind eine Zeile der Liste**
  (`held_guides`); wer eine Zeile übersetzt, fragt `constraint_indices(row)`.
  Entf und Kontextmenü lösen die Gruppe in einem Schritt (`remove_constraints`).

## Das Maß am Zeiger

* **Das Maß beim Zeichnen steht am Zeiger** (`measure_field`, `MEASURE_GAP`
  Bildpunkte neben der Spitze): nicht darunter (es fänge die Maus), an Rand
  und Ecke auf der anderen Seite, und die erste Ziffer beginnt die Eingabe ohne
  Klick — gesendet an `lineEdit()`, nicht an das Drehfeld.
* **Gezeichnet heißt frei, getippt heißt bemaßt:** `_finish_rectangle` streift
  den Festpunkt und lässt nur das Maß einer Seite stehen, deren Zahl im Feld
  stand; `shapes.rectangle` bleibt für Dialog und Agent bestimmt (§30.1).
* **Maßfeld und Wertleiste heben sich beim Erscheinen an**, nicht je
  Zeigerbewegung: Alle Kinder der Ansicht sind native Fenster.
* **Genau waagerecht oder senkrecht bleibt es** (`_axis_constraint`); ein
  getipptes Maß zieht `_snapped_direction` innerhalb `AXIS_SNAP_DEGREES` auf
  die Achse, und der getippte Linienzug geht danach weiter.
* **Das Winkelmaß steht mit Gradzeichen** (`readable_angle`, `DEGREE_UNIT`) an
  der gemeinten Ecke; ein Winkel hat keine Anzeigeeinheit.

## Ein gezogener Punkt steht am Zeiger

Der Löser hat einen Zugmodus (`solve_sketch(..., dragged=, start=)`, Regel in
`app/core/sketch/CLAUDE.md`): Gezogene Punkte sind fest, alles andere folgt mit
der kleinsten Bewegung; was die Bedingungen nicht erlauben, rutscht so weit wie
möglich.

* **`_drag_solve` schreibt die ganze Lösung zurück** — die gespeicherte
  Zeichnung ist stets die gelöste, ein `fixed`-Anker wandert nie; `-0.0` wird
  null.
* **Fest heißt fest, auch gegen die Hand**; getippte Koordinaten (`edit_point`)
  setzen erst den Anker (`_anchor`).
* **Die Mitte eines Kreises oder Bogens nimmt den Rand mit** (`move_point`),
  der Rand zieht nur den Radius.
* **Was hält, wird gesagt** (`_holding`): Kommt ein Punkt nicht an, nennt die
  Zeile die Bedingungen an ihm und den Rechtsklick als Weg (Regel 17).
* **Verschieben zieht die ganze Auswahl** (`move_selected`, verschoben, nicht
  kopiert), erst ab `startDragDistance` (`_shift_selection`); der Undo-Punkt
  entsteht beim ersten wirklichen Zug, einmal.


## Keine Karte über einer anderen

`show_sketch` sammelt erst alle Maßkarten und verteilt sie gemeinsam (`place_sketch_cards`, Rechnung in
`spread_sketch_cards`): Die erste behält ihren Platz, jede weitere rückt zum
nächsten freien um ihren Anker, senkrecht vor waagerecht; weggelassen wird
keine. Gemessen mit derselben Schrift, die pygfx zeichnet
(`SKETCH_CARD_FONT_PIXELS`), plus ein Fünftel; geprüft in
`tests/test_sketch_card_layout.py`.

## Ein Doppelklick auf die Maßkarte öffnet das Maß

* `_measure_cards` ist die **eine** Quelle für Anzeige und Treffer
  (`measure_at`, `MEASURE_PICK_PX`); die Zeichenfläche meldet
  `measureEditRequested`, das Panel öffnet denselben Dialog wie die Liste.
* Im Viewport bringt der Doppelklick seine Stelle mit (Rückruf an
  `set_sketch_stroke`, `None` bei der Eingabetaste);
  `MainWindow._finish_sketch_stroke` fragt `double_click_on_plane` — erst den
  Spline, dann die Karte.
* **Was auf einer Taste liegt, steht auch im Kontextmenü**, mit dem Kürzel.
  `_context_menu` trennt **Bauen** (`context_menu_at`) und Zeigen — ein Menü,
  das sich selbst öffnet, hält eine Suite an, und `QMenu.exec` zu patchen ist
  kein Ersatz.

## Sichtbarer Skizzenmodus im Viewport

* **Jede Auskunft des Canvas reist ins sichtbare Bild:** `pending_elements()`
  gibt die unfertige Geometrie als `SketchElement`-Vorschau (über `curves_of`
  wie die feste Zeichnung), `measure_annotations()` Maßtext und Lage — beides
  ändert weder Skizze noch Undo (Regel 2).
* **Das Raster hat drei Ebenen:** leise Zwischenlinien, jede fünfte als
  Landmarke, Nullachsen mit X/Y/Z nahe am Ursprung. Skizzenkanten hinweisblau
  und breiter, Auswahl und Unfertiges bernsteinfarben und zusätzlich dicker
  oder als Vorschau kodiert; Maße in ruhigen Karten.
* **Die untere Karte bleibt eine Leiste:** Im Viewport-Modus zählen
  unsichtbarer Canvas, Strecklayout und Schichthinweis nicht zur Höhe (die
  Schichtauskunft ist ein Tooltip am Ebenenfeld); `OverlayHost._bottom_size`
  fragt `heightForWidth`.

## Formwerkzeuge und Lochbilder

* **Vorschau und Klick rechnen aus derselben Funktion** (`_drawn_shape`,
  `DRAWN_SHAPE_TOOLS`, `pending_elements`): Vieleck samt Hilfskreis, Langloch,
  Lochraster (erstes und gegenüberliegendes Loch, Abstände je Richtung aus dem
  Zug) und Lochkreis (Mitte, erstes Loch). Zwei Klicks am selben Fleck geben
  keine Form, die Zeile sagt es, und der erste Klick bleibt.
* **Getippt heißt bemaßt, und Einstellungen der Leiste sind Maße:** Getippt
  werden Umkreis (Ø oder R), Mittenabstand, Lochabstand und Teilkreis; die
  **Breite des Langlochs** und der **Lochdurchmesser** kommen aus der Leiste
  und stehen immer als Maß.
* **Das Lochraster hält über Bedingungen zwischen Mitten**, nicht über
  Festpunkte (`edit.hole_grid_between`: `horizontal`, `vertical`, `equal`), der
  Lochkreis über den Teilkreis als Hilfskreis (`edit.bolt_circle_at`), bei zwei
  Löchern über `midpoint` statt `equal`.
* **Ein zu großes Loch sagt es** (`hole_fits` im Kern, `_shape_error`,
  `_shape_refusal` mit Ausweg — Regel 17).
* **Kein Menü mit festen Formen** (Entscheidung Robert): Was man zeichnen kann,
  zeichnet man; die Einladung der leeren Skizze wählt das Rechteckwerkzeug
  (`_take_rectangle`). `shapes.py` bleibt für Dialog, Kommandozeile und Agent
  (§30.1).
* **Konzentrisch ist ein Wort, keine Bedingungsart** (`ConstraintAction`,
  `core_kind`); *Gleich groß* nimmt Linien und Rundungen.
* **Welche Punkte eine Bedingung nimmt, entscheidet eine Stelle**
  (`SketchCanvas.constraint_targets`): *Fest* einen Punkt, *Konzentrisch* je
  Element die Mitte, *Gleich groß* je Element zwei Punkte, *Mittelpunkt* Punkt,
  Anfang und Ende.

## Verrunden und Fase an einer Ecke

Zwei Werkzeuge (`CORNER_TOOLS`, F und K), gerechnet im Kern (`edit.fillet`,
`edit.chamfer`, `edit.corner_at`): Zeiger auf eine Ecke — zwei Linienenden am
selben Ort, gesucht über die gelösten Punkte —, dann Klick.

* **Die Vorschau hängt an der Ecke unter dem Zeiger** (`_corner_hover`, gesetzt
  in `note_pointer` **vor** `pointerChanged`); `pending_measure` liefert das
  gemerkte Maß (`corner_values`, `DEFAULT_FILLET_MM`, `DEFAULT_CHAMFER_MM`),
  eine getippte Zahl ist danach die Vorgabe.
* **Passt das Maß nicht, nennt die Zeile das größte, das passt**
  (`_corner_hint`), ohne Vorschau.
* **Die Fangmarke weicht, das Aufleuchten bleibt** (`_note_snap_mark`).
* **Die Rundung trägt `perpendicular`, nicht `tangent`** (`edit.fillet`) — die
  Tangente wäre dort ein doppelter Nullpunkt.
* **Die alte Ecke bleibt als Hilfspunkt** (`edit._held_by_the_virtual_corner`)
  auf beiden verlängerten Schenkeln, und was am Eckende hing, hängt an ihm.
* **Die Fase misst von der alten Ecke:** ein Maß und *gleich lang*.

## Die Karte unten: vier Gruppen, ein Hinweis, kein doppelter Satz

* **Werkzeuge in vier Gruppen** (`style.divider`): Auswählen — Punkt, Linie,
  Rechteck, Kreis, Bogen, Ellipse, Kurve, Vieleck, Langloch — Lochkreis,
  Lochraster — Trimmen, Verlängern, Verrunden, Fase
  (`test_the_tools_stand_in_four_groups_with_dividers`). Die Zeile bleibt unter
  900 Bildpunkten (`test_the_sketch_area_fits_a_laptop_screen`), mit dem engen
  Abstand `style.TIGHT` (Abstände auf dem Raster von vier,
  `tests/test_style.py`); Eckenzahl und Breite erscheinen nur mit ihrem
  Werkzeug.
* **Ein Kürzel braucht einen Anlass:** V (Vieleck) und G (Lan**g**loch) nach
  dem deutschen Wort, F und K an den Ecken; Lochkreis, Lochraster und Ellipse
  haben keines.
* **„Bedingungen erscheinen, sobald …" geht, sobald die Knöpfe einmal da
  waren** (`_constraints_seen`).
* **Der Gestensatz steht einmal, als Karte im Bild**; die Zeile der
  Skizzenkarte sagt nur, was sonst nirgends steht (abweichender Blick, Fläche
  eines Körpers).
* **Ein Abschluss: *Fertig*** (RM-561) — kein Hochziehen, Abtragen oder
  *Mehr* daneben, kein Menü am Knopf. **Ein Knopf, eine Bedeutung** — mit
  Menü und `clicked` am selben Knopf entschiede die Zustellung des Loslassens.
* **Ein Zeichnen-Knopf je Skizzenfeld:** am vorhandenen Schritt ins Bild
  (`offer_space`), sonst ins Fenster, nie beides.
* **Jeder Knopf ohne Text trägt einen Namen** (`setAccessibleName`, geprüft über
  `QAccessible`).
* **Der Tabulator läuft durch die Karte** (`MainWindow._chain_sketch_card`:
  Werkzeuge, Ebene, Raster, Statuszeile, Ziel, Nachbarn, Fertig, Verwerfen,
  dann die Bedingungsliste), angeknüpft an die Statuszeile, nie über
  `nextInFocusChain` (`test_the_menus_outlive_the_sketch_mode`).

## Ebenen, Zustand und Flächenkontur

* **Eine frische Zeichnung wird nicht auf die Vorgabe gestreckt**
  (`op_dialog.follow_sketch`, `drawing_changed`).
* **Ein getipptes Maß streckt nur seine Richtung** (`edit.stretched`), sonst
  wächst die Gegenrichtung mit und die Zeichnung verlässt ihren Bezugspunkt;
  gleichmäßig nur, wo die Zeichnung es verlangt, und das Feld sagt es. Nach
  einer Zeichnung heißen die Felder *Zeichnung waagerecht/senkrecht*, weil sie
  auf jeder Ebene so liegen, und die Grundform-Zeile ist ausgeblendet.
* **Flächenkontur ist ein eigener Knopf neben Projizieren**
  (`take_face_outline`): eine feste **Kopie** des Randes; am Netz nennt die
  Zeile die erkannten Kreise und ihre größte Abweichung (`outline_phrase`),
  Merkmale über `Surroundings.objects`.
* **Wie weit ein Bogen läuft, sagt `profile.arc_sweep`** — Zeichnen,
  Treffertest und Hülle rechnen nicht selbst in Grad; ein Bogen mit
  zusammengeführten Enden ist ein Vollkreis.

## Ellipse und Kurvenbedingungen

* **Ein Knopf *Ellipse*, keiner für den Bogen** — der entsteht durch Trimmen
  (`edit.trim` → `_trimmed_ellipse`).
* **Drei Klicks: Mitte, Achsende, Breite**; vom dritten zählt nur die Höhe über
  der ersten Achse (`edit.ellipse_from_clicks`), ohne Deckung. Getippt wie am
  Kreis, gespeichert als `diameter` auf (Mitte, Achsende); ein Klick auf Mitte
  oder erste Achse zählt nicht, und die Zeile sagt warum.
* **Die Griffe tun, was ein CAD tut** (`_ellipse_drag`, `edit.carried_onto`):
  Das Achsende dreht und streckt, die zweite Achse behält ihre Länge,
  Bogenenden gleiten auf der Ellipse.
* **Bedingungen zwischen Kurven plant der Kern** (`_PLANNED`,
  `constraint_plan`, `edit.tangent_plan`): *Tangential* für jedes Kurvenpaar
  außer zwei Linien, in jeder Auswahlreihenfolge — am Stoß *glatt*, zwischen
  Linie und Kreis oder Bogen die Abstandstangente, sonst ein Hilfspunkt; an
  einem Spline ohne Stoß an einem seiner Punkte bleibt der Knopf weg.
  *Auf Kurve*, *Krümmungsstetig* (bringt *glatt* mit), *Gleich groß* für
  Ellipsen (längere zur längeren); ein zweiter Klick nimmt zurück, eine
  Tangente samt Hilfspunkt. *Waagerecht* und *Senkrecht* nehmen an der
  Ellipse die erste Achse.
* **Die Liste nennt Kurven** (`targets_phrase`): „Auf Kurve — Punkt 1,
  Ellipse 1".
* **Splinepunkte über das Kontextmenü** (`_offer_spline_point_insertion`,
  `_offer_spline_point_removal`): einfügen auf der Kurve, entfernen unter drei
  Punkten gesperrt und begründet; Entf löscht das ganze Element.

## Ein Körper, ein Ziel

* **Das Ziel folgt der Ausdrücklichkeit** (`_resolve_sketch_body`): genannter
  Körper, dann der Körper des geänderten Schritts, dann der Körper der Fläche
  (auch über Versatzebenen), dann der **eine** gewählte Körper; ohne Auswahl
  eine neue Zeichnung. **Mehrere gewählte Körper — auch eine Baugruppe — sind
  eine Frage** (Regel 21): Die Leiste nennt sie und *Neuer Körper*, bis dahin
  stehen alle leise im Bild.
* **Die übrigen Körper sind ausgeblendet** (Entscheidung Robert, gegen
  „durchscheinend"): `_in_view` lässt nur das Ziel durch — Bild, Klick, Fang,
  Kanten. *Nachbarn zeigen* (Taste N) holt sie mit `SKETCH_NEIGHBOUR_OPACITY`
  ohne Kanten und nicht anklickbar zurück (`_draw_sketch_neighbours`). Eine
  eigene Regel neben `_hidden`, die mit dem Modus endet.
* **Ebenenfeld, Projizieren und Flächenkontur sehen nur das Ziel**
  (`_sketch_scope` → `_sketch_surroundings(only=…)`), auch bei eingeblendeten
  Nachbarn; bei einer neuen Zeichnung die Grundebenen, Nachbarn erst, wenn sie
  eingeblendet sind. Das Feld nennt höchstens `MOST_PLANE_FACES` Flächen, die
  gewählte immer; die fünfte Karte bietet die Oberseite
  (`SketchPlanePicker.offer_face`, `placement.top_face`). Aufgelöst wird gegen
  die ganze Szene.
* **Das Ziel bestimmt das Ergebnis** (`_rising_surface`): nach außen am Ziel
  `sketch_join`, wenn der Umriss auf oder über ihm liegt
  (`_outline_meets_the_body`); nach innen nur mit Ziel. Das Ziel ist auch
  nachträglich im Feld *Ziel* wählbar.
* **Beim Verlassen kommt die vorige Sicht zurück** (`_view_before_sketch`,
  `_restore_the_view_before_sketch`); beim Betreten gilt die Platte des Ziels,
  und eine Explosion wird aufgehoben.
* **Verschwindet das Ziel** (Agent, Fernsteuerung), bleibt die Zeichnung, die
  Leiste sagt es, und *Fertig* legt einen neuen Körper an
  (`_sketch_body_missing`).
* **Eine Zeichnung trägt ihren Ort:** `run_operation` übernimmt aus der Auswahl
  kein „Bis zur Fläche" und keine Lage (`_carries_a_drawing`), und der Dialog
  leert ein Ziel auf der Zeichenfläche
  (`OperationDialog._release_the_drawing_face`).
* **Escape verwirft nicht** (Entscheidung Robert): Kette, Werkzeug, Auswahl —
  danach „Zum Verlassen: Fertig oder Verwerfen."; *Verwerfen* ist der eine Weg,
  mit Strg+Z zurück.
* **Eine ebene Fläche bietet *Hier zeichnen* und *Loch oder Aussparung
  zeichnen …*** (`FeaturePanel.sketchRequested`), ein Schritt mit Zeichnung
  *Zeichnung weiterverwenden* (Entscheidung Robert: eine neue, freie Kopie;
  §30.1 bleibt).
* **Ein Schritt mit Zeichnung öffnet direkt den Zeichenmodus**
  (`MainWindow.edit_operation`), mit seiner Schrittkennung und dem betroffenen
  Skizzenfeld — **außer einer Einfachform** (`shapes.simple_shape`): Ein
  Rechteck oder Kreis öffnet den Dialog mit *Breite*/*Tiefe* (Tasche:
  *Länge*) oder *Durchmesser* und der Höhe vorn (`front_fields`), *Umriss
  bearbeiten …* führt in den Editor. *Fertig* gibt die neue Zeichnung in denselben Schritt zurück;
  der Dialog zeigt davor die Erzeugungsmaße. Ein gezielter Sprung in ein
  Zahlenfeld öffnet weiterhin den Zahlendialog samt Weg zurück ins Zeichnen.
  Auch *Verwerfen → Strg+Z* bewahrt Schritt und Skizzenfeld. Das Angebot
  gehört seiner Projektidentität; gleiche Schrittanzahl eines anderen
  Projekts berechtigt nicht zum Zurückholen.
