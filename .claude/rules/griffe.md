---
description: "Griffe: Zeigervorfahrt, eigene Bewegen-/Skaliergriffe, Merkmal-/Bausteingriffe, Langlochform statt Lage, Merkmalmaße/Platzierung und ASCII-Beschriftung"

paths:
  - "app/ui/slot_handle.py"
  - "app/ui/viewport.py"
  - "app/ui/transform_bar.py"
  - "app/ui/render/gizmo.py"
  - "app/ui/scale_widget.py"
  - "app/ui/placement_flow.py"
  - "app/ui/measure_field_places.py"
---

# Regeln für die Griffe in der Szene

Was der Nutzer unmittelbar am Modell anfasst: Bewegen-, Skalier- und
Langlochgriff, die Maße daran, ihre Beschriftung. `ansicht.md` und `kamera.md`
laden am Viewport mit. Anlässe und Messwerte:
`konzepte/begruendungen/regel-griffe.md`.

## Ein Griff steht vor allem, was über der Ansicht liegt

`Viewport._dispatch_pointer`: **beanspruchter Griff → `CLICK_SLACK` bei
ungeklärtem Linksdruck in gemeinsam gewählter Senkbohrung → laufende
Platzierung → allgemeiner Zeiger → Kamera**. Die Sonderprüfung trennt Klick
und Zug: Klicks gehen zur normalen Auswahl, nicht unterstützte Züge enden
vor Platzierung/Zeiger/Kamera, zulässige kehren unverändert in die normale
Vorfahrt zurück. Platzierung vor Griffen würde Bewegungen als Zielversuch
verbrauchen und sichtbare Griffe stilllegen.

* **Verschluckt wird nichts**: `move` nimmt ein Griff nur gedrückt, `press` nur
  über einem getroffenen Teil.
* **Bei gedrückter Taste nur den ziehenden Griff fragen** (`pressing`):
  Kamera/Körper führen, unnötiges `pick_item` entfällt. Der ziehende Griff
  erhält weiter Bewegungen (`test_a_held_button_leaves_the_grips_out_of_the_way`);
  freies Schweben ohne Taste hebt weiter hervor.

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
* **Bewegungsgriff, Langlochgriff und Auswahl teilen ihren Sichtstrahl**
  (`render.gizmo.display_ray`): nahe und ferne Kameraebene, Richtung ohne
  Normierung, kein Strahl bei fehlender Projektion oder Länge bis `EPS_GEOM`.
* **Beim Ziehen ist alles Vorschau** (Regel 2): `set_matrix` am Element, beim
  Loslassen Operationen (`_on_gizmo_released`) oder nichts unter der
  Fangschwelle.
* **Nach jedem Zug neu bauen:** Bezugsbasis ist die Matrix beim Greifen;
  Wiederverwendung würde den Zug doppeln oder am verschwundenen Element hängen.
  `Viewport.grip_placement` hat zwei Ausnahmen: laufender Zug (`grip.pressing`,
  sonst würde daraus ein Kameraschwenk) und `Gizmo.fits` (gleiches Ziel/Ringe,
  Maßstab auf `SCALE_TOLERANCE`, Matrix per `np.array_equal`).

* **Platzierungsgriff am Werkzeugansatz:** Ursprung/Größenmessung lesen die
  Verschiebung der Platzierungsmatrix. Die Werkzeugmitte könnte tief unter der
  gewählten Fläche liegen und den Griff vom Arbeitsort trennen. Geometrie und
  Matrix des Werkzeugs bleiben unverändert.

* **Erzeugervorschau räumt ihre Zahl selbst ab:** `_end_preview_drag` beim
  Loslassen und Dialogende im Zug; `_end_drag` hinge den Auswahlgriff an.
  Sonst blieb „Y 60,62 mm“ nach dem Einsetzen stehen (RM-558).
  `_preview_dragging`: Getippte Zahlen gehen mit Enter über `previewDragged`
  nur an die Vorschau; beim Loslassen bleibt die Leiste während des Tippens.
  Esc/Enter setzen zuerst die Lage vor dem Zug zurück (`_put_the_preview_back`),
  sonst rechnet der neue Griff den Weg mit.

* **Ein Zug am Griff lässt die Navigation in Ruhe**: Der Griff sieht die
  Zeigerereignisse vor dem Navigator und gibt frei, was er nicht braucht; kein
  Zugende baut den Navigator neu
  (`test_a_drag_leaves_the_navigation_in_place`).
* **Der Skaliergriff** (`app/ui/scale_widget.py`) folgt demselben Muster — Hover
  über `pick_item`, Zug in der Kameraebene (`ray_plane_hit`), Ergebnis beim
  Loslassen. Wer das Muster ändert, ändert beide.

### Frei drehen, aber 45 Grad treffen

Frei drehen mit kurzem Einrasten bei Vielfachen von 45° (Entscheidung Robert):
`geom.transform.snap_near` wirkt nur nahe einem Vielfachen. `_settled_angle`
nimmt den Leistenfang hart, sonst den Magneten (`TURN_MAGNET_STEP` 45°,
`TURN_MAGNET_ZONE` 4°). `interact_callback` liefert die zu setzende korrigierte
Matrix (`_on_gizmo_interacted`, `rotation_about` im Kern); gerechnet wird weiter
von der Greifmatrix (`test_the_magnet_corrects_the_turn_while_it_runs`).

## Ein gewähltes Merkmal bekommt seinen Griff ohne Werkzeug

*Bewegen* gilt dem Körper und trägt den Skalierwürfel; ein angeklicktes Merkmal
ist selbst die Ansage (§2.6) — Griff ja, Würfel nein.

* **Nur wirksame Griffe zeichnen** (`viewport.gizmo_build`): Fläche mit
  Richtungspfeil (`render.gizmo.normal_frame`, `arrows=(2,)`), ohne Ring;
  Merkmalsringe nur für von `rotate_feature` angenommene Arten
  (`turnable_feature_kinds`); Körper/Baustein mit allen Griffen. Kein Pfeil/Ring,
  dessen Zug beim Loslassen verfällt.

* **Gewählte Fläche: Zug als Wegvorschlag** (RM-535). `faceDragged` meldet
  die **Kennung**, das Fenster setzt *Fläche versetzen* (`take_values`,
  `preview_armed`); erst *Übernehmen* legt `push_face` mit `face=<Kennung>` an,
  wie bei der Bohrung. Ohne gewählte Fläche/Zeile wird der Zug sofort zum
  Schritt. `nx/ny/nz` nur für gespeicherte Schritte: Eine Richtung statt der
  Kennung würde alle gleich gerichteten Flächen versetzen.

* **Ein Merkmal trägt den Griff nur, wo die Karte das Versetzen anbietet**
  (`Viewport.move_refused` → `FeaturePanel.refuses`, nach dem Aufbau
  `refresh_gizmo`); an einer gesperrten Tasche endete der Zug sonst ohne Ort.
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

`moves_as_a_part` zieht alle Merkmale desselben Schritts (`created_by`) als
einen Aktor (`_show_part_drag`, `_drag_part`, Abbau `_drop_ghost`). Außerhalb
der ebenen Fläche (`_landing_of`): Rot (`PART_OFF_FACE_COLOUR`) **und** „neben
der Fläche“ im Zugfeld (Regel 18). Ohne ebene Fläche keine Aussage.
Grundfläche ist der **Umriss, nicht die Böden** (`_footprint_fan`: Hülle eigener
Dreiecke samt Öffnung); „keine ebene Fläche“ heißt kein fremdes Dreieck in Sitzhöhe.

## Der Langlochgriff zieht die Form, nicht die Lage

Das Langloch wird im Bild gezogen, nicht im Dialog (Entscheidung Robert):
`app/ui/slot_handle.py`, zwei Knöpfe an den Enden, gezogen in der Ebene der
Mündung. Wo er sitzt, sagt das Register (`slot_feature_kinds()` aus dem
`applies_to` von *Zum Langloch ziehen*), nie eine Aufzählung in der Ansicht.

* **Ruhende Öffnungen lesbar halten:** Bei `slot_feature_kinds()` bleiben
  geschlossene, nicht pickbare Shape-/Face-Hilfsaktoren ohne Entwurf unsichtbar.
  Wand, Umriss und zwei pickbare Knöpfe tragen die Auswahl. Ruheknöpfe sind
  durchscheinend, die Bezugsscheibe bewahrt Bounds; Hover/Halten bleibt kräftig.
  Bestehendes Neuzeichnen wertet den realen Vorschlags-/Haltezustand samt
  `held`/`waiting` aus: Form/Breite/Drehung/Versatz aus bewegtem Zug oder Feld
  sowie wartende Entwürfe zeigen kräftige Hilfsflächen. Bloßer Druck zeichnet
  nicht neu; Abbruch/Wiederaufbau ohne Entwurf verbirgt sie. Loslassen fragt
  den Treffer neu (`SlotHandle._hover`), auch nach Leave im Zug.
  Bounds/Geometrie/Picks bleiben erhalten. Bei gleicher Punktzahl aktualisiert
  `_show_preview(update=True)` Punkte, Deckkraft und Sichtbarkeit im selben
  Aktor. Wächter: `test_feature_grip_readability.py`.
* **Die gewählte Öffnung bleibt frei:** Knöpfe außen am Scheitel
  (`knob_centres`; der Zug rechnet vom Scheitel, `knob_seats`), Pfeile erst
  hinter ihnen (`Gizmo(clear=…)`), Wandtönung leise. `test_hole_grip_clearance.py`.

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
* **Kerngrenze gemeinsam nutzen:** `prepare.shortest_slot` und
  `prepare.is_round_length` (halbe Anzeigestufe) für Griff/Felder,
  `placement.prepare_tool` und beide Kerne. Regel: `operationen.md`,
  „Ein Langloch in neuer Richtung ist ein gedrehtes Langloch“ / „Die kürzeste
  Länge ist gemessen“; Begründung unter gleicher Überschrift in
  `konzepte/begruendungen/regel-operationen.md`.

* **Darunter auf die runde Bohrung rasten** (Entscheidung Robert): Zwischen
  Breite und Mindestlänge erkennt die Erkennung kein Loch. `settled_length`
  nimmt im oberen halben Streifen die kürzeste Länge, im unteren die Breite.
  Der eingerastete Umriss ist ein Kreis, die Zahl heißt „Bohrung“ statt „Länge“
  (Regel 18); beide Knöpfe behalten die Richtung. Rundes Ende an runder Bohrung
  schlägt nichts vor (`Viewport._on_slot_released`). **Getippte Zahlen rasten
  nicht** (`shown_length`): Umriss mit kürzester Länge, Absagegrund über der Vorschau.

* **Länge = Breite macht wieder eine runde Bohrung; steht danach genau die
  Bohrung da, aus der ein Schritt das Langloch zog, fällt der Schritt**
  (`MainWindow._commit_slot_change`, `_slot_step_undone`), mit Quittung und
  Strg+Z — **außer ein späterer Schritt nennt das Langloch**
  (`_slot_named_later`), dann wird er geändert.
* **Gewähltes Loch als Griff:** Linksdruck ohne laufende Platzierung baut den
  Zuggriff (`_pull_at_the_hole` → `SlotHandle.take_press`, näherer Knopf).
  Am Langloch zählt die ganze Öffnung samt Enden (`bore_span`, `travel`/`heading`).
  **Der Knopf folgt dem Handweg, springt nicht zur Hand** (`SlotHandle._grab`,
  `_grab_at`); nur die runde Bohrung rechnet aus der Mitte. Loslassen meldet
  `slotProposed`, das Fenster holt Maße (`_on_slot_proposed` → `request_in_view`).
  Neben dem Loch führt die linke Maustaste den Körper.

* **Gemeinsam gewählte Senkbohrung: Klick bleibt Klick.**
  `Viewport._block_unsupported_cavity_slot_pull` merkt den Linksdruck vor;
  erst jenseits `CLICK_SLACK` prüft `_cavity_slot_pull_refusal` die Kette am
  getroffenen Körper. Verbundene/mehrdeutige Bohrung-Senkungs-Ketten enden vor
  Platzierung/Navigator; unverbundene Merkmale gehen zum normalen Zeigerweg.
  `slotPullBlocked` zeigt die passende Handlung aus `actions_for` ohne
  Quittungsstatus. Senkung/Körper bleiben unverändert.

* **Der Ring um die Bohrachse dreht das Langloch**, nicht seine Achse
  (`_slot_turn_sign`, `SLOT_RING_ALIGNED`): Griff, Marke und Beschriftung folgen
  dem gerasteten Winkel (`_turn_slot_with`, `_slot_turn_base`), das Loslassen
  schlägt *Zum Langloch ziehen* mit neuer Richtung vor (`_on_slot_released`);
  die anderen Ringe bleiben *Merkmal drehen*.
* **Der Versatz eines Knopfes zählt gegen die gebaute Geometrie**
  (`SlotHandle._built_seats`) — `Item.set_position` verschiebt gegen den Puffer.
* **Marke folgt Langlochform und Griff:** `_slot_form_of`, `shapes.prism` über
  `slot_outline`; Vorrang: wartender Zug, Zwischenstand, sonst Maße. Nach Zug
  und getippter Zahl neu zeichnen (`_repaint_preview`, bei gleicher Punktzahl
  nur Punkte). Bewegungszug nimmt Marke/Knöpfe/Umriss mit (`SlotHandle.shift`);
  neuer Griff trägt den Umriss sofort (`outlined=`).

* **Je Mausbewegung ein Bild**: `SlotHandle._drag` zeichnet nicht selbst
  (`_redraw(render=False)`); nur wenn `_repaint_preview` nichts zeichnete,
  rendert der Viewport.

### Ein Zug an einer Form endet im Merkmalfenster, nicht im Verlauf

Mausmaße für Länge/Richtung sind nicht millimetergenau. Der Umriss bleibt;
`Viewport.slotProposed` füllt den Maßentwurf *Zum Langloch ziehen*. Übernehmen
nimmt den ganzen Auftrag samt Breite/Zielmitte: eine Bedienstelle rechts,
keine zweite Leiste (Entscheidung Robert). Der Tastaturweg (`apply_slot_drag` →
`slotDragged`) ersetzt den Entwurf nicht. Escape verwirft und stellt Messwerte
wieder her (`_drag_kind` bleibt `"slot"`).

* **Ob ein Zug wartet, sagt `Viewport.slot_drag_waits()`** am gemerkten Merkmal
  (`_slot_target`), nicht an `_drag_kind` — auch ein ohne Bewegung losgelassener
  Griff wartet.
* **Gefragt wird der Zustand, nie `isVisible()`** — offscreen antwortet Qt immer
  falsch.
* **Gemeldet wird das Übernehmen, nicht das Ziehen** (`Viewport.slotStarted`):
  Langlochgriff und Flächenplatzierung meinen dasselbe Loch verschieden, und bis
  zum Übernehmen ist nichts geschehen (Regel 2) — die Maße bleiben im Bild.

## Maße und Platzierung am Merkmal

* **Bohrungsmaße erscheinen bei Auswahl; erste Feld-/Griffbetätigung bindet
  den Entwurf** (§18.11). `placementDragStarted` erst jenseits `CLICK_SLACK`
  (`Gizmo.dragging`, `SlotHandle.dragging`), auch beim Lochdruck. Klick ohne Weg
  bewegt/meldet/bindet nichts (`test_a_click_on_the_placement_grip_does_not_bind_the_draft`).
  Der Hinweissatz endet mit dem Entwurf (`MainWindow.end_quiet_placement`).

* **`PlacementFlow` besitzt Fachfelder/Platzierungsgriffe** und sperrt den
  allgemeinen Merkmalsgriff (`set_feature_gizmo_blocked`). Reines Verschieben
  ohne Drehringe; weitere Merkmalsarten über *Im Bild einstellen*.

* **Sperre entfernt Pfeile/Ringe/Würfel:** Sperre und Werkzeug-Platzierungsgriff
  nehmen nur den Bewegungsgriff. Flächenscheibe/Langlochknöpfe bleiben nach
  Aufrufer (`knobs=True`, `set_gizmo`/`only_knobs`: Bohrungsmaßeditor, nicht
  Erkennungsdialog/Ganzflächentextur). `grip_placement` baut sie nach dem ersten
  Griff wieder auf; die Gizmo-Ansage bleibt leer.

* **Formwechsel erhält den Entwurf:** Bohrung→Langloch mit Länge/Richtung/Breite;
  geänderte Breite/Mitte bleiben, Flächenbezug ab Zielmitte. Bei offener
  Tiefenänderung bleibt ihr Editor zuständig; Langlochzug mit Hinweis verwerfen.

* **Ein Langloch nimmt beim Setzen die Flächennormale**, beim Ziehen und Ändern
  die positive Merkmalachse; die Gegenmündung liegt rechtshändig
  (`placement_flow.py`).
* **Feldwerte überleben Griffneuaufbau:** Länge/Richtung/Breite vorher ans
  Merkmal binden. Panel/Maßgruppe teilen den vollständigen Auftrag; kein
  Griffsignal darf die Breite verlieren.

* **Erste Eingabe bindet die Auswahl:** Davor ist die Maßanzeige abwählbar;
  danach halten Außenklick/Auswahltasten den Entwurf
  (`Viewport.user_selection_allowed`, `_ObjectTreeView`). Kamera/Scrollen bleiben
  frei. Fremde Befehle werden nicht vorgemerkt; Übernehmen/Abbrechen gibt frei.
  Echte Dokument-/Ergebnisänderung entwertet den Bezug; die eigene Commitmeldung
  wartet auf Erfolg des Callbacks.

* **Abbrechen und Escape heben die Auswahl auf** (Entscheidung Robert), wie
  ein Leerklick: `QuietHost.cancel` → `MainWindow._measures_cancelled`;
  Escape über `MainWindow._leave_the_measures` vor der Auswahlstufe, im Maßfeld
  `PlacementFlow.step_back`. Wartender Langlochzug und vorgeschlagenes Versetzen
  werden verworfen; gerechnet ist nichts.

* **Am Langloch stehen beide Griffe**: Knöpfe für Länge und Richtung, Pfeile und
  Ringe zum Versetzen und Drehen.
* **Bewegungsgriff während Platzierung = Vorschlag:**
  `featureMoveProposed`/`featureTurnProposed` füllen *Merkmal verschieben*/*drehen*.
  Der Griff bleibt (`_grip_shift`, `move_proposal_waits()`), Maßlinien folgen
  (`PlacementFlow.move_to`); erst Übernehmen erzeugt den Schritt (Regel 2).
  Ohne Platzierung (Zapfen/Kegel/Kugel) bleibt der Zug ein Schritt.

* **Langlochzug und Versetzen warten gemeinsam:** `_end_drag`/`_detach_gizmo`
  erhalten `_slot_target`, der neue Griff trägt `_slot_waiting`. Die Stelle
  geht in *Zum Langloch ziehen*; `slot_hole` schneidet Länge/Stelle in **einem**
  Schritt (`slotDragged`, Stelle als viertes Argument). Verwerfen nur bei
  Übernehmen, Escape (`cancel_slot_drag`), Auswahlwechsel oder Szenenaufbau
  (`drop_move_proposal`).

* **Maße bleiben im Bild:** Länge wächst um die Mitte, Kantenmaße gelten weiter.
  `PlacementFlow.redraw` erhält Linien/Felder der gebundenen Maßgruppe auch bei
  Kameradrehung; nur der runde Umriss weicht. Ohne Maßgruppe tritt Platzierung zurück.

* **Bei Platzmangel bleibt jedes Maßfeld im Bild** (`measure_field_places`).
  Nur die große Fachkarte darf den Rand des Körpers überdecken; die kurzen
  Maßfelder behalten ihre Plätze außerhalb, und ein Platzmangel der Karte
  schiebt nicht alle Maße in eine Notreihe. Die Karte hält so viele
  Feldzeilen frei, wie die Maße nebeneinander brauchen (`rows_height`), nicht
  fest eine. Die Notanordnung (`emergency_places`) lässt die Nutzerkarte immer
  frei, Setzpunkt, Bewegungsgriff und Vorschauband erst mit, dann ohne
  Abstand: Überdecken ist das kleinere Übel, ein Feld außerhalb des Bildes
  keines.

* **Nach Übernehmen Maße/Griffe wiederherstellen:**
  `MainWindow._measures_to_resume` → `_show_feature_fields` (Konzept
  Merkmalbedienung, Abnahme 1). Nach Umbenennung (`hole_1` → `slot_1`) findet
  `_reselect_the_renamed` das Merkmal an der gemeldeten Stelle in Baum **und** Ansicht.

* **Maßlinien räumen den überragten Griffbereich** (`_Dimensions.clearing`
  aus `gizmo_reach()`, nur Kosmetik: Striche nehmen keinen Klick). Bliebe außen
  weniger als ein Pfeil, kommt die ganze Linie; der Lochumriss bleibt sichtbar.
  Gegen Griff/Knöpfe liegt die Tinte mit `draw_order` unter null, unabhängig
  von der Plattenlage.

* **Klick ins rechte Zwillingsfeld erhält die Maße:** Ohne begonnenen Entwurf am selben
  Merkmal wechselt die Maßgruppe auf den Zwilling (`MainWindow._hand_the_measures_over`
  aus `_on_handling_armed`), Fokus ins gleiche Feld (`_focus_measure_field`,
  `panels.FIELD_PROPERTY`). Der Zwilling zeigt nur eigene Werte
  (`FeaturePanel._in_the_view`): Breite/Durchmesser/X/Y/Z/Toleranz sind schon im Bild.

* **Jede Zahl einmal im Bild** (RM-516): Bei sichtbaren Maßen keine
  Merkmalmarke (`Viewport.set_measured_feature`), an runder Bohrung keine
  Knopflänge (`_slot_length_text`); statt „Aktuell: Ø…“ nur warnende Herkunft
  (`labels.feature_source`), X/Y/Z unter „Weitere Werte“ (`panels._coordinate_fields`).
  Am sitzenden Merkmal bestimmen zwei Kantenmaße die Lage; Mitte nur über
  *Bezug ändern*, zurück über „Ohne Mitte“. Die Maßkarte ist inhaltsbreit;
  längste Auswahl separat unter ihrer Beschriftung (`_choice_widths`,
  `WrapLongRows`), Rundung wie Randkarten (`_MeasureCard`, `overlay.MEASURE_CARD`).

* **Bezüge nach Zielseite der Maßlinie benennen** (`placement_flow.reference_names`,
  Weltachsen wie Flächennamen im Baum); Mittenmaße nach Achse (`_axis_letters`).
  Keine beim Drehen wechselnde Bildseite. Nummern nur bei drei gleichartigen
  Bezügen zur selben Seite.

### Wo etwas schon sitzt, zielt der Zeiger nicht

* **Am Merkmal nie neu zielen:** Griff/Felder bestimmen die Lochstelle;
  Bildklicks gehen zur Auswahl (`PlacementFlow.pointer`). Die Merkmalstelle
  (`PlacementFlow._seated_at_feature`) folgt keiner Mausbewegung; neue Bohrungen
  setzen diesen Merker nicht.

* **Auch ohne Trägerfläche** (`_no_seat_at_feature`) misst die Maßgruppe
  weiter; eine gefaste Mündung findet ihre Fläche über `placement.seat_of`,
  `mouth_reach`.
* **Geschluckt wird nur die freie Bewegung** — mit Taste gehört sie der Kamera.
* **Ein Klick, der neu zielt, ist verbraucht**, statt in die `confirm`-Kette zu
  fallen und zu übernehmen.
* **Baustein sitzt ohne Klick** auf gewählter, sonst größter aufwärts zeigender
  Fläche (`PlacementFlow._begin_on_a_face`, `UPWARD_FACE`), samt Werkzeugkörper,
  Maßen/Feldern. Bewegungsgriff daran (`grip_placement`, `placementDragged` →
  `_dragged_at_the_tool` → `move_to`); Auswahlgriff weicht bis Escape.
  **Keine ungewählte Vorgabe per Klick bestätigen:** `_seated_by_default` setzt
  beim ersten Klick um, beim nächsten übernimmt es. Nur Bausteine; Bohrungen
  werden gezielt gesetzt. **Ohne Merkmal, Flächenbezug und Position keine
  Vorschau/Übernahme:** `OperationDialog.place_missing` fragt `parts.ops.place_missing`,
  dieselbe Sperre wie `_anchor` (RM-773).

* **Neue Platzierung bei Formänderung neu binden, nicht vergessen** (RM-774):
  Nur ein veraltetes Ergebnis zählt; `projectChanged` beim Speichern belässt
  alles. Bis zum neuen Ergebnis stoppen Vorschau/Übernehmen
  (`OperationDialog.hold_place`), damit kein alter Punkt an neuer Form hängt.
  Dann bindet `start` über `placement.bind_surface`; erst bei Fehlschlag setzt
  `_renew_the_place` neu und meldet es im Balken. Ausgenommen: Schrittänderung,
  eigenes Übernehmen (Dialog schon zu) sowie Kundenziele x/y/z vorhandener
  Merkmale (`_MOVES_A_FEATURE`); sie sind keine zurücksetzbaren Messwerte.
  Derselbe Weg gilt, wenn der Dialog während der vorigen Schrittrechnung öffnet.

## Was am Griff steht, ist ASCII — und sonst nichts

Am Griff nur `X`, `Y`, `Z`, `S` und `<->`, keine übersetzten Texte; anderswo
zeichnet Qt. Namen wie „Platte · Oberseite“ gehören in die Statusleiste.
Ungeprüfte Wörter fielen auf Deutsch kaum, auf Französisch sofort auf:
`tests/test_selection.py::test_nothing_on_the_gizmo_leaves_ascii` prüft
`Face supérieure`, `Arrière`, `Côté gauche`, `Côté droit`.

`Viewport._label_gizmo` zeichnet freistehende Buchstaben (X/Y/Z/S/L) und Maße
mit `_sketch_label_colour`/`_sketch_label_background`, `background_opacity=1`
und `margin=4` wie `finding_label`. Der gemeinsame Aktor nutzt 13 px und
Fettschrift; Ankerlogik und nicht pickbarer Beschriftungsauftrag bleiben
vom Stil unabhängig. Leere Maßtexte zeigen kein Hintergrundfeld.

`_update_slot_labels` legt beide L-Felder beim Aufbau, bei Kamera/Zoom und
Maßänderung über `layout_feature_labels` außerhalb der projizierten
Knopfhüllen: Textfeldgröße, DPR und `TIGHT` zählen mit; die Rückprojektion
behält die Tiefe. Ohne gültige Projektion, Rückprojektion oder freien Nahplatz
bleiben die endlichen Ausgangsanker vollständig erhalten. Gleiche Punkte und
Texte erzeugen kein Update. `_layout_feature_labels` lässt diese Neuberechnung
bei `Gizmo.pressing` aus: Im beanspruchten Zug führt die laufende Matrix die
Beschriftung; der Kameratimer darf XYZ nicht auf Ausgangspunkte zurücksetzen.
