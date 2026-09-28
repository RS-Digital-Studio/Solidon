---
description: "Die Griffe in der Szene — Vorfahrt der Zeigerereignisse, Bewegen- und Skaliergriff als eigener Code, der Griff am gewählten Merkmal und am Baustein, der Langlochgriff zieht die Form und nicht die Lage, Maße und Platzierung am Merkmal, und was an einem Griff steht, ist ASCII"
paths:
  - "app/ui/slot_handle.py"
  - "app/ui/viewport.py"
  - "app/ui/transform_bar.py"
  - "app/ui/render/gizmo.py"
  - "app/ui/scale_widget.py"
  - "app/ui/placement_flow.py"
---

# Regeln für die Griffe in der Szene

Was der Nutzer unmittelbar am Modell anfasst: Bewegen-, Skalier- und
Langlochgriff, die Maße daran, ihre Beschriftung. `ansicht.md` und `kamera.md`
laden am Viewport mit. Anlässe und Messwerte:
`konzepte/begruendungen/regel-griffe.md`.

## Ein Griff steht vor allem, was über der Ansicht liegt

`Viewport._dispatch_pointer` hat eine feste Vorfahrt: **Griffe, dann eine
laufende Platzierung, dann der Zeiger, zuletzt die Kamera.** Stünde die
Platzierung vorn, nähme sie jede Bewegung als Zielversuch, und die Griffe wären
sichtbar und tot.

* **Verschluckt wird nichts**: `move` nimmt ein Griff nur gedrückt, `press` nur
  über einem getroffenen Teil.
* **Mit gedrückter Taste wird kein Griff gefragt, der nicht selbst zieht**
  (`pressing`) — wer hält, führt Kamera oder Körper, und jede Frage kostet ein
  `pick_item`. Der ziehende Griff bekommt seine Bewegungen weiter
  (`test_a_held_button_leaves_the_grips_out_of_the_way`); freies Schweben ohne
  Taste hebt weiter hervor.
* **Die zweite Ebene ist Qt**: Ein Widget über der Renderfläche bekommt die
  Ereignisse zuerst. Wer etwas darüberlegt, hält `Viewport.gizmo_reach()` frei,
  wie `PlacementFlow` für seine Maßfelder.
* **Betätigt ist ein Griff mit dem Weg, nicht mit dem Druck**: `CLICK_SLACK` wie
  im Navigator (`kamera.md`, „Ein Klick ist ein Klick, auch mit Zittern“);
  jenseits davon rechnet der Zug vom Druckpunkt.
* `test_viewport_decisions.py` liest die Vorfahrt im Quelltext nach der Bauart
  der Griff-Felder (`Gizmo` oder `…Handle`), nicht nach Namen.

## Der Bewegen-Griff ist eigener Code, kein fremdes Widget

`app/ui/render/gizmo.py` zeichnet Pfeile, Ringe und Würfel über den Vertrag.

* **Er pickt über den Vertrag, nie mit eigenem Picker** (`pick_item`: erst
  `keep_in_front`, dann der Rest, Toleranz `PICK_SLACK_PIXELS`) — ein eigener
  Picker trifft auf der einen Maschine und auf der anderen nicht.
* **Beim Ziehen ist alles Vorschau** (Regel 2): `set_matrix` am Element, beim
  Loslassen Operationen (`_on_gizmo_released`) oder nichts unter der
  Fangschwelle.
* **Nach jedem Zug frisch gebaut** — er rechnet gegen die Matrix beim Greifen;
  ein stehen gelassener wendete den Zug doppelt an und hinge an einem
  verschwundenen Element. **Zwei Ausnahmen** in `Viewport.grip_placement`, wo ein
  frischer Griff dasselbe ergäbe: im Zug (`grip.pressing` — neu gebaut würde der
  Zug ein Kameraschwenk) und wenn er passt (`Gizmo.fits`: gleiches Ziel, gleiche
  Ringe, Maßstab auf `SCALE_TOLERANCE`, Matrix per `np.array_equal`).
* **Ein Zug am Griff lässt die Navigation in Ruhe**: Der Griff sieht die
  Zeigerereignisse vor dem Navigator und gibt frei, was er nicht braucht; kein
  Zugende baut den Navigator neu
  (`test_a_drag_leaves_the_navigation_in_place`).
* **Der Skaliergriff** (`app/ui/scale_widget.py`) folgt demselben Muster — Hover
  über `pick_item`, Zug in der Kameraebene (`ray_plane_hit`), Ergebnis beim
  Loslassen. Wer das Muster ändert, ändert beide.

### Frei drehen, aber 45 Grad treffen

Frei drehen, kurz einrasten bei jedem Vielfachen von 45 Grad (Entscheidung
Robert). `geom.transform.snap_near` zieht nur nahe einem Vielfachen;
`_settled_angle` nimmt den Winkelfang der Leiste hart, sonst den Magneten
(`TURN_MAGNET_STEP` 45°, `TURN_MAGNET_ZONE` 4°). Der `interact_callback` gibt
die berichtigte Matrix zurück, die gesetzt wird (`_on_gizmo_interacted`,
`rotation_about` im Kern); der Griff rechnet weiter von der Matrix beim Greifen
(`test_the_magnet_corrects_the_turn_while_it_runs`).

## Ein gewähltes Merkmal bekommt seinen Griff ohne Werkzeug

*Bewegen* gilt dem Körper und trägt den Skalierwürfel; ein angeklicktes Merkmal
ist selbst die Ansage (§2.6) — Griff ja, Würfel nein.

* **Gezeichnet wird nur, was ein Zug einlöst** (`viewport.gizmo_build`): an
  einer Fläche ein Pfeil entlang ihrer Richtung (`render.gizmo.normal_frame`,
  `arrows=(2,)`) und kein Ring, an einem Merkmal Ringe nur, wo
  `rotate_feature` die Art annimmt (`turnable_feature_kinds`), am Körper und
  am Baustein alles. Ein Pfeil oder Ring, dessen Zug beim Loslassen verfällt,
  ist schlimmer als keiner.

* **An einer Fläche geht der Zug bis in den Verlauf**: `gizmo_feature` (wo),
  `gizmo_target` (was), `_face_seat` (Mitte und Normale), `faceDragged` meldet die
  **Kennung**, das Fenster macht `push_face` mit `face=<Kennung>` — mit der
  Richtung bewegte die Operation jede gleich gerichtete Fläche. `nx/ny/nz` nur
  noch für gespeicherte Schritte (`test_the_handle_of_a_chosen_face_pushes_that_face`
  fährt die Kette am Stück).
* **Eine Fläche aus einem Baustein**: `gizmo_target` antwortet nichts, der Zug
  meldet `featureMoved` in den Schritt des Bausteins, nie als Vorschlag
  (`proposing`) — Regel in `fenster.md`, „Ein Merkmal aus einem Baustein meint
  den Baustein“.
* **Die Bohrung eines Bausteins** bekommt ihren Griff (`set_gizmo` hebt die
  Sperre aus `placed_feature_kinds` auf), aber ohne Langlochknöpfe — deren
  Schnitt bliebe beim nächsten Verschieben stehen.
* **Das Dach im Objektbaum**: `set_part_grip` sagt, an welchem Merkmal der Griff
  hängt; die Ansicht weiß nicht, ob die Auswahl **ein** Baustein ist.

### Am Bausteinmerkmal zieht der ganze Baustein mit

Ein Zug an einem Merkmal mit `moves_as_a_part` zeigt alle Merkmale desselben
Schritts (`created_by`) als einen Aktor (`_show_part_drag`, `_drag_part`, weg
mit `_drop_ghost`). Verlässt der Sitz die ebene Fläche (`_landing_of`), wird der
Baustein rot (`PART_OFF_FACE_COLOUR`) **und** das Zugfeld sagt „neben der
Fläche“ (Regel 18); ohne ebene Fläche keine Aussage statt einer falschen. **Die
eigene Grundfläche ist der Umriss, nicht die Böden** (`_footprint_fan`: Hülle
der eigenen Dreiecke samt Öffnung); „keine ebene Fläche“ heißt kein fremdes
Dreieck in Sitzhöhe.

## Der Langlochgriff zieht die Form, nicht die Lage

Das Langloch wird im Bild gezogen, nicht im Dialog (Entscheidung Robert):
`app/ui/slot_handle.py`, zwei Knöpfe an den Enden, gezogen in der Ebene der
Mündung. Wo er sitzt, sagt das Register (`slot_feature_kinds()` aus dem
`applies_to` von *Zum Langloch ziehen*), nie eine Aufzählung in der Ansicht.

* **Der Winkel zählt gegen die x-Achse von `sketch.planes.frame_of`** — wie
  `prepare.slot_profile` schneidet und `prepare_ops.slot_angle_of` nachmisst;
  eine eigene Achse legte das Loch neben den gezeigten Umriss.
  `tests/test_slot_handle.py` schneidet wirklich und misst nach.
* **Der Umriss im Bild ist der des Schnitts** (`slot_outline` aus
  `slot_profile`, Bögen über `profile.arc_through`), keine zweite Konstruktion.
  Der Kreis der runden Bohrung entsteht als Langloch mit Flanken null, **mit
  derselben Punktzahl** — beim Einrasten tauscht `update_points` nur Punkte.
* **Beim Längenziehen bleibt die Mitte stehen**, der Gegenknopf spiegelt;
  Versetzen kommt vom Bewegungsgriff oder den Lagefeldern im selben Auftrag.
* **Die Grenze steht im Kern** (`prepare.shortest_slot`,
  `prepare.is_round_length` auf die halbe Anzeigestufe); Griff, Felder,
  `placement.prepare_tool` und beide Kerne fragen sie. Die Regel: `operationen.md`,
  „Ein Langloch in neuer Richtung ist ein gedrehtes Langloch“ („Die kürzeste
  Länge ist gemessen“); warum sie dort liegt, unter derselben Überschrift in
  `konzepte/begruendungen/regel-operationen.md`.
* **Darunter rastet er auf die runde Bohrung** (Entscheidung Robert) — zwischen
  Breite und kürzester Länge hält die Erkennung kein Loch: `settled_length` hält
  im oberen halben Streifen die kürzeste Länge, im unteren die Breite;
  eingerastet zeigt der Umriss einen Kreis, und die Zahl heißt „Bohrung“ statt
  „Länge“ (Regel 18). Die Richtung bleibt an beiden Knöpfen die alte; rund
  geendet an einer runden Bohrung schlägt nichts vor
  (`Viewport._on_slot_released`). **Eine eingetragene Zahl rastet nicht**
  (`shown_length`): Der Umriss zeigt die kürzeste Länge, der Grund der Absage
  steht über der Vorschau.
* **Länge = Breite macht wieder eine runde Bohrung; steht danach genau die
  Bohrung da, aus der ein Schritt das Langloch zog, fällt der Schritt**
  (`MainWindow._commit_slot_change`, `_slot_step_undone`), mit Quittung und
  Strg+Z — **außer ein späterer Schritt nennt das Langloch**
  (`_slot_named_later`), dann wird er geändert.
* **Das gewählte Loch ist selbst der Griff**: Ein Linksdruck darauf ohne laufende
  Platzierung baut den Griff für diesen Zug (`_pull_at_the_hole` →
  `SlotHandle.take_press`, der nähere Knopf); am Langloch zählt die ganze
  Öffnung samt Enden (`bore_span` mit `travel`/`heading`). **Der Knopf wandert
  um den Weg der Hand, er springt nicht auf sie** (`SlotHandle._grab`,
  `_grab_at`); nur die runde Bohrung rechnet aus der Mitte. Loslassen ist
  `slotProposed`, das Fenster holt die Maße (`_on_slot_proposed` →
  `request_in_view`). Neben dem Loch führt links den Körper.
* **Der Ring um die Bohrachse dreht das Langloch**, nicht seine Achse
  (`_slot_turn_sign`, `SLOT_RING_ALIGNED`): Griff, Marke und Beschriftung folgen
  dem gerasteten Winkel (`_turn_slot_with`, `_slot_turn_base`), das Loslassen
  schlägt *Zum Langloch ziehen* mit neuer Richtung vor (`_on_slot_released`);
  die anderen Ringe bleiben *Merkmal drehen*.
* **Der Versatz eines Knopfes zählt gegen die gebaute Geometrie**
  (`SlotHandle._built_seats`) — `Item.set_position` verschiebt gegen den Puffer.
* **Die Marke trägt die Langlochform und folgt dem Griff** (`_slot_form_of`,
  `shapes.prism` über `slot_outline`): wartender Zug, Zwischenstand, sonst die
  Maße; neu gezeichnet nach jedem Zug und jeder getippten Zahl
  (`_repaint_preview`, nur Punkte, solange die Punktzahl bleibt). Ein Zug am
  Bewegungsgriff nimmt Marke, Knöpfe und Umriss mit (`SlotHandle.shift`), der neue
  Griff trägt den Umriss sofort (`outlined=`).
* **Je Mausbewegung ein Bild**: `SlotHandle._drag` zeichnet nicht selbst
  (`_redraw(render=False)`); nur wenn `_repaint_preview` nichts zeichnete,
  rendert der Viewport.

### Ein Zug an einer Form endet im Merkmalfenster, nicht im Verlauf

Länge und Richtung trifft man mit der Maus nicht auf den Millimeter. Der Umriss
bleibt, `Viewport.slotProposed` schreibt in den Maßentwurf von *Zum Langloch
ziehen*, Übernehmen nimmt den ganzen Auftrag samt Breite und Zielmitte — eine
Bedienstelle rechts, keine zweite Leiste (Entscheidung Robert). Der Tastaturweg
(`apply_slot_drag` → `slotDragged`) ersetzt den Entwurf nicht; Escape verwirft
und stellt die gemessenen Werte wieder her (`_drag_kind` bleibt `"slot"`).

* **Ob ein Zug wartet, sagt `Viewport.slot_drag_waits()`** am gemerkten Merkmal
  (`_slot_target`), nicht an `_drag_kind` — auch ein ohne Bewegung losgelassener
  Griff wartet.
* **Gefragt wird der Zustand, nie `isVisible()`** — offscreen antwortet Qt immer
  falsch.
* **Gemeldet wird das Übernehmen, nicht das Ziehen** (`Viewport.slotStarted`):
  Langlochgriff und Flächenplatzierung meinen dasselbe Loch verschieden, und bis
  zum Übernehmen ist nichts geschehen (Regel 2) — die Maße bleiben im Bild.

## Maße und Platzierung am Merkmal

* **Der Maßeditor einer Bohrung erscheint mit der Auswahl**; die erste Feld- oder
  Griffbetätigung beginnt den gebundenen Entwurf (§18.11). `placementDragStarted`
  kommt erst jenseits von `CLICK_SLACK` (`Gizmo.dragging`, `SlotHandle.dragging`),
  auch beim Druck ins gewählte Loch: Ein Klick ohne Weg bewegt, meldet und bindet
  nichts (`test_a_click_on_the_placement_grip_does_not_bind_the_draft`); der Satz
  dazu geht mit dem Entwurf (`MainWindow.end_quiet_placement`).
* **`PlacementFlow` besitzt Fachfelder und Platzierungsgriffe**; der allgemeine
  Merkmalsgriff ist dann über `set_feature_gizmo_blocked` gesperrt. Reines
  Verschieben zeigt keine Drehringe; weitere Merkmalsarten gehen über *Im Bild
  einstellen*.
* **Gesperrt heißt ohne Pfeile, Ringe und Würfel.** Sperre und Platzierungsgriff
  am Werkzeugkörper nehmen nur den Bewegungsgriff; Flächenscheibe und
  Langlochknöpfe bleiben, wo der Aufrufer es sagt (`knobs=True`, in `set_gizmo`
  `only_knobs`: der Maßeditor an einer gewählten Bohrung — nicht
  Erkennungsdialog und Ganzflächentextur). `grip_placement` baut sie nach dem
  ersten Griff wieder auf; die Gizmo-Ansage bleibt leer.
* **Der Formwechsel behält den Entwurf**: Aus der Bohrung wird ein Langloch mit
  Länge, Richtung und Breite; geänderte Breite und Mitte gehen mit, der
  Flächenbezug beginnt an der Zielmitte. Ist eine Tiefenänderung offen, bleibt
  deren Editor zuständig, und der Langlochzug wird mit Hinweis verworfen.
* **Ein Feldwert überlebt den Neuaufbau seines Griffs**: Länge, Richtung und
  Breite werden vor dem Aufbau an das Merkmal gebunden; Panel und Maßgruppe
  teilen denselben vollständigen Auftrag, kein Griffsignal verliert die Breite.
* **Die erste Eingabe bindet die Auswahl.** Vorher ist die Maßanzeige abwählbar;
  danach halten Außenklick und Auswahltasten den Entwurf
  (`Viewport.user_selection_allowed`, `_ObjectTreeView`). Kamera und Scrollen
  bleiben frei; fremde Befehle werden nicht vorgemerkt, erst Übernehmen oder
  Abbrechen gibt sie frei. Eine echte Dokument- oder Ergebnisänderung entwertet
  den Bezug; die eigene Dokumentmeldung beim Commit wartet auf den Erfolg des
  Callbacks.
* **Abbrechen hebt die Auswahl auf** (Entscheidung Robert; `QuietHost.cancel` →
  `MainWindow._measures_cancelled`, wie ein Klick ins Leere). **Escape tut
  dasselbe** (Entscheidung Robert): `MainWindow._leave_the_measures` vor der
  Auswahlstufe, im Maßfeld `PlacementFlow.step_back`; verworfen werden ein
  wartender Langlochzug und ein vorgeschlagenes Versetzen — gerechnet ist
  nichts.
* **Am Langloch stehen beide Griffe**: Knöpfe für Länge und Richtung, Pfeile und
  Ringe zum Versetzen und Drehen.
* **Solange die Platzierung läuft, ist ein Zug am Bewegungsgriff ein
  Vorschlag**: `featureMoveProposed`/`featureTurnProposed` füllen *Merkmal
  verschieben*/*drehen*, der Griff bleibt stehen (`_grip_shift`,
  `move_proposal_waits()`), die Maßlinien folgen (`PlacementFlow.move_to`), erst
  Übernehmen macht den Schritt (Regel 2). Ohne Platzierung (Zapfen, Kegel,
  Kugel) bleibt der Zug ein Schritt.
* **Ein wartender Langlochzug und ein Versetzen warten zusammen** (`_end_drag`
  und `_detach_gizmo` lassen `_slot_target` stehen, der neue Griff trägt
  `_slot_waiting`); die Stelle geht in die Felder von *Zum Langloch ziehen*, und
  `slot_hole` schneidet Länge und Stelle in **einem** Schritt (`slotDragged` mit
  der Stelle als viertem Argument). Verworfen nur bei Übernehmen, Escape
  (`cancel_slot_drag`), Auswahlwechsel, Szenenaufbau (`drop_move_proposal`).
* **Die Maße bleiben dabei im Bild**: Die Länge wächst um die Mitte, die
  Kantenmaße gelten weiter; `PlacementFlow.redraw` hält Linien und Felder der
  gebundenen Maßgruppe, auch über Kameradrehungen, nur der runde Umriss weicht.
  Ohne Maßgruppe tritt die Platzierung zurück.
* **Nach dem Übernehmen kommen Maße und Griffe wieder**
  (`MainWindow._measures_to_resume`, eingelöst in `_show_feature_fields`;
  Konzept Merkmalbedienung, Abnahme 1); nach einer Umbenennung (`hole_1` →
  `slot_1`) findet `_reselect_the_renamed` das Merkmal an der gemeldeten Stelle
  — in Baum **und** Ansicht.
* **Die Maßlinien weichen dem Griff, soweit sie über ihn hinausreichen**
  (`_Dimensions.clearing` aus `gizmo_reach()`, Kosmetik — die Striche nehmen
  keinen Klick); bliebe außen weniger als ein Pfeil, kommt die ganze Linie, der
  Umriss des Lochs bleibt sichtbar. Gegen Griff und Knöpfe trägt die Tinte
  `draw_order` unter null, damit nicht die Lage der Platte entscheidet, was oben
  liegt.
* **Ein Klick ins Zwillingsfeld rechts gibt die Maße nicht auf**: Die Maßgruppe
  wechselt auf den Zwilling (`MainWindow._hand_the_measures_over` aus
  `_on_handling_armed`), der Fokus ins selbe Feld (`_focus_measure_field`,
  `panels.FIELD_PROPERTY`) — solange nichts begonnen ist und dasselbe Merkmal
  gemeint ist. **Der Zwilling zeigt nur, was er allein hat**
  (`FeaturePanel._in_the_view`): Breite, Durchmesser, X, Y, Z und Toleranz
  stehen schon im Bild.

### Wo etwas schon sitzt, zielt der Zeiger nicht

* **Am Merkmal zielt die Platzierung nie**: Wohin ein Loch soll, sagen Griff und
  Felder; ein Klick ins Bild gehört der Auswahl (`PlacementFlow.pointer` gibt ihn
  zurück). Die Stelle gehört dem Merkmal (`PlacementFlow._seated_at_feature`),
  eine Mausbewegung verschiebt sie nicht; beim Setzen einer neuen Bohrung wird
  der Merker nie gesetzt.
* **Auch ohne Trägerfläche** (`_no_seat_at_feature`) misst die Maßgruppe
  weiter; eine gefaste Mündung findet ihre Fläche über `placement.seat_of`,
  `mouth_reach`.
* **Geschluckt wird nur die freie Bewegung** — mit Taste gehört sie der Kamera.
* **Ein Klick, der neu zielt, ist verbraucht**, statt in die `confirm`-Kette zu
  fallen und zu übernehmen.
* **Ein Baustein sitzt sofort**: ohne Klick auf der gewählten, sonst der größten
  nach oben zeigenden Fläche (`PlacementFlow._begin_on_a_face`, `UPWARD_FACE`),
  mit Werkzeugkörper, Maßen und Feldern; daran hängt der Bewegungsgriff
  (`grip_placement`, `placementDragged` → `_dragged_at_the_tool` → `move_to`),
  der Auswahlgriff weicht bis Escape. **Ein Klick bestätigt keine Stelle, die
  niemand gewählt hat** (`_seated_by_default`: der erste setzt um, der nächste
  übernimmt). Nur Bausteine — die Bohrung wird gezielt gesetzt.

## Was am Griff steht, ist ASCII — und sonst nichts

Am Griff steht kein übersetzter Text — überall sonst zeichnet Qt, hier stünde
ein Wort in sechs Sprachen, wo keine Prüfung hinsieht. Es bleiben `X`, `Y`, `Z`,
`S` und `<->`; Namen wie „Platte · Oberseite“ gehören in die Statusleiste.
Deutsch fiele nie auf, Französisch sofort:
`tests/test_selection.py::test_nothing_on_the_gizmo_leaves_ascii` prüft mit
`Face supérieure`, `Arrière`, `Côté gauche`, `Côté droit`.
