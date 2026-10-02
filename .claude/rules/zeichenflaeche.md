---
description: "Der Skizzeneditor — Vorschau und Fang am Zeiger, Raster und Maßstab, gezogene Punkte und Zwangsbedingungen, Maßkarten, der Ziehgriff der Querschau, Form- und Lochwerkzeuge, die Karte unten, Ebenen und Flächenkontur, Ellipse und Kurvenbedingungen, der Zielkörper"
paths:
  - "app/ui/sketch_editor.py"
---

# Regeln für die Zeichenfläche

Der Skizzenmodus (`app/ui/sketch_editor.py`, gezeigt im Viewport). Texte,
Barrierefreiheit und Zeiger regelt `oberflaeche.md`, die Ansicht `ansicht.md`,
das Warten `wartezeit.md`; sie gelten mit. Anlässe, Messwerte und die Mechanik
im Einzelnen stehen unter denselben Überschriften in
`konzepte/begruendungen/regel-zeichenflaeche.md`.

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
* **Ein Zeigerschritt, der nichts ändert, zeichnet nicht:** `render()` kostet
  6,9 ms, bei sechzig Ereignissen je Sekunde 41 % eines Kerns. Verglichen
  werden gefangener Ort **und** Maßstab.
* Fangmarke, `pending_elements()` und der feste Klick lesen dasselbe Ziel aus
  `_placement_target`; ein Mausereignis rendert höchstens einmal.

## Zoom und Schwenk auf einer Ebene

* **Die Zeichenebene wird orthografisch gesehen** (§18.1) — perspektivisch
  wären gleich lange Strecken verschieden lang. Beim Verlassen kommt der Wert
  des Nutzers zurück; `view_on_plane` rechnet `parallel_scale` aus der
  Kameradistanz (`_fit_parallel_scale`).
* **Wer an der Kamera zoomt, geht durch `apply_wheel_zoom`**, das beide
  Projektionen unterscheidet (ein Dolly ändert orthografisch nichts); das Rad
  zoomt auf den Zeiger. `tests/test_viewport_decisions.py` prüft beide.
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

## Der Ziehgriff der Querschau

In der Querschau zieht man am Umriss, und der Körper wächst mit
(`Viewport.set_sketch_pull`, `axis_hit`, `pull_cage`).

* **Angeboten nur in der Querschau:** `SketchCanvas.planes_are_parallel`
  vergleicht die Richtungen von Blick und Zeichenebene (gegenläufige Normalen
  sind parallel; dieselbe Prüfung gilt einer gewählten Fläche beim Einrasten
  der Kamera); in der Draufsicht führt der Hinweis zur Vorder- oder
  Seitenansicht, die freie Ansicht zählt als Querschau. Wer sich ohne
  Ebenenwahl in die Kantensicht dreht, bekommt ihn nicht — dort ist Zeichnen
  die Absicht.
* **Die Frage stellt das Fenster** (`MainWindow._sketch_pull_offer`: `"ready"`,
  ein Grund oder leer); ein Grund nur, wo die Geste gemeint war, über
  `sketchPullBlocked` an `announce` (Regel 17) — und dieselbe Quelle schreibt
  den Satz in die Leiste.
* **Angeboten wird nur, was geht** (`pull_height_at` in `sketch_pull_ready`,
  dieselbe `axis_hit`-Prüfung wie der Zug, am selben Ort `pull_base_at`).
* **Der Griff ist der Umriss selbst**, gemessen gegen die Strecken der
  projizierten Kurven (`polyline_distance`) bis `CURSOR_PIXELS`;
  Konstruktionsgeometrie zählt nicht.
* **Dieselbe Zustandsmaschine wie der Körperzug** (`on_body_drag`,
  `ready`/`start`/`move`/`end`); `_end_drag` beendet den Ziehgriff über
  `_end_pull`, **nicht** über `set_navigation`.
* **Was wächst, ist eine Drahtform** (`pull_cage`, höchstens `MOST_PULL_RIBS`
  Sprossen), keine Vorschau über `session.preview_async`.
* **Die Höhe ist gefangen und geklemmt** (`pulled_height`): auf das sichtbare
  Raster, in die Grenzen **aus dem Schema** (`main_window.pull_limits`), nie
  abgeschrieben.
* **Ein Zug in die falsche Richtung sagt es, statt einen Splitter zu bauen:**
  Geklemmt wird mit Vorzeichen, null bleibt null; die Richtung entscheiden
  `continue_sketch_pull` und `_pull_takes` an derselben geklemmten Höhe,
  geprüft nur gegen die Untergrenze — ein Zug bis zum Anschlag ist gemeint, und
  eine getippte Zahl ersetzt Zeiger samt Richtung.
* **Die Grenze steht an einer Stelle** (`_pull_takes`, für Loslassen und
  Eingabetaste): Beim Tippen wird abgelehnt, beim Ziehen geklemmt; die
  abgelehnte Zahl bleibt markiert im Feld (wie bei `_apply_typed`).
* **Ohne Attrappe nicht prüfbar:** Offscreen ist `sketch_pull_ready` immer
  falsch; `gripping` in `tests/test_viewport_decisions.py` ersetzt genau die
  drei Methoden, die einen Renderer brauchen (Muster aus `ansicht.md`,
  `test_cursors.py`).
* **Die freie Skizze bietet *Hochziehen* und *Abtragen* als Wörter**, sobald
  der Umriss geschlossen ist, und führt damit in den Operationsdialog — die
  Leiste erzeugt keine Geometrie (Regel 2). Offen nennen beide ihre Bedingung;
  *Abtragen* steht nur mit Zielkörper da. Wurde der Modus für eine andere
  Operation geöffnet, bleiben beide verborgen.

### Die Zahl am Zeiger

* **Die Wertleiste steht am Zeiger** (`DragValueBar.anchor`, derselbe
  `MEASURE_GAP` aus `viewport.py`); an den Griffen von §18.11 bleibt sie oben
  mittig.
* **Sie ist während des Zugs sichtbar und tippbar** — ein unsichtbares Feld
  nimmt keinen Fokus, und was über den Ausschnitt hinausgeht, ist nur tippbar.
* **Mit Vorzeichen, nicht als Betrag** (`_apply_typed` nimmt den Feldwert als
  Höhe); die Richtung steht zusätzlich im Namen (*Höhe*, *Tiefe*).
* **Maßfeld und Wertleiste heben sich beim Erscheinen an**, nicht je
  Zeigerbewegung (`_place_measure_field` läuft an jedem `measuringChanged`):
  Alle Kinder der Ansicht sind native Fenster, und die Leiste entsteht vor der
  Grafikfläche. Die Schlösser nach ihren Feldern.

## Keine Karte über einer anderen

`show_sketch` sammelt erst alle Maßkarten und Karten des Ziehgriffs und
verteilt sie gemeinsam (`place_sketch_cards`, Rechnung in
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
* **Der Weg wird progressiv erklärt:** Schließt ein Umriss, nennt das Bild die
  Vorder- oder Seitenansicht; in der Querschau Pfeil und — nur mit gewähltem
  bearbeitbarem Körper — Kreuz. Das Profil wird über der Werkzeugkarte
  zentriert; ein Griff hinter der Leiste oder ohne gültige Operation ist keiner.
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
* **Die Arten hängen an *Mehr*** (`_fill_finish_menu`): die
  Skizzen-Operationen des Registers mit ihrem `doc`-Satz als Tooltip,
  Hochziehen, Anfügen und Tasche vorn, Unmögliches gesperrt mit Grund, was
  als Knopf daneben steht, ausgeblendet (`_update_sketch_actions`); kein
  Dialog „Was soll daraus werden?", und mit festgelegter Operation kein
  *Mehr*. *Fertig* hat kein Menü und nimmt den
  wahrscheinlicheren Fall: über dem Zielkörper eine Tasche, sonst ein neuer
  Körper (Entscheidung Robert). **Ein Knopf, eine Bedeutung** — mit Menü und
  `clicked` am selben Knopf entschiede die Zustellung des Loslassens.
* **Ein Zeichnen-Knopf je Skizzenfeld:** am vorhandenen Schritt ins Bild
  (`offer_space`), sonst ins Fenster, nie beides.
* **Jeder Knopf ohne Text trägt einen Namen** (`setAccessibleName`, geprüft über
  `QAccessible`).
* **Der Tabulator läuft durch die Karte** (`MainWindow._chain_sketch_card`:
  Werkzeuge, Ebene, Raster, Statuszeile, Hochziehen, Abtragen, Fertig,
  Verwerfen, dann die Bedingungsliste), angeknüpft an die Statuszeile, nie über
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
* **Das Ziel bestimmt das Ergebnis:** *Hochziehen* heißt am Ziel *An Körper
  anfügen* (`sketch_join`), wenn der Umriss auf oder über ihm liegt
  (`_outline_meets_the_body`); *Abtragen* nur mit Ziel und nur am Ziel. Das
  Ziel ist auch nachträglich im Feld *Ziel* wählbar.
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
