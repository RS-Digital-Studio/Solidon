---
description: "Die Griffe in der Szene — der Langlochgriff zieht die Form und nicht die Lage, der Bewegen-Griff ist eigener Code, und was an einem Griff steht, ist ASCII"
paths:
  - "app/ui/slot_handle.py"
  - "app/ui/viewport.py"
  - "app/ui/transform_bar.py"
---

# Regeln für die Griffe in der Szene

Was der Nutzer unmittelbar am Modell anfasst: der Griff am Langloch, der
Bewegen-Griff, die Beschriftung daran. **Ausgegliedert aus `ansicht.md` am
18.09.2026** — die übrigen Ansichtsregeln gelten weiter und laden zusätzlich,
sobald jemand am Viewport arbeitet. Der Grund für den Schnitt: Diese vierzig
Kilobyte gelten für zwei Dateien, luden aber für dreiundzwanzig.

## Der Langlochgriff zieht die Form, nicht die Lage (10.09.2026)

Der Bewegungsgriff schiebt und dreht, der Würfel skaliert den Körper — und aus
einer Bohrung wird damit nie ein Langloch. Der Weg dorthin war ein Dialog mit
zwei Zahlen, und Robert hat ihn am gefahrenen Weg abgelehnt: „das langloch soll
auch über den viewport einstellbar/erstellbar/änderbar von bohrung zu langloch
sein". `app/ui/slot_handle.py` ist die Antwort — zwei Knöpfe an den Enden des
Lochs, gezogen wird in der Ebene seiner Mündung.

Vier Sachen daran sind Entscheidungen und keine Bequemlichkeit:

* **Der Winkel kommt aus einer Quelle.** Gezählt wird gegen die x-Achse von
  `sketch.planes.frame_of` — dieselbe, gegen die `prepare.slot_profile`
  schneidet und `prepare_ops.slot_angle_of` ein erkanntes Langloch nachmisst.
  Eine eigene Achse in der Ansicht wäre ein Loch, das um einen Winkel neben dem
  Umriss liegt, den der Kunde beim Ziehen gesehen hat — und kein Test über
  Zahlen allein sähe es. `tests/test_slot_handle.py` schneidet deshalb wirklich
  und misst die Richtung am erkannten Ergebnis nach.
* **Der Umriss im Bild ist der Umriss des Schnitts.** `slot_outline` baut ihn
  aus `slot_profile` und tastet dessen Bögen über `profile.arc_through` ab. Eine
  zweite Konstruktion daneben liefe beim nächsten Zuwachs auseinander.
* **Das Loch wächst um seine Mitte.** Sie ist der eine Wert, den `slot_hole`
  **nicht** mitbekommt — die Operation liest ihn aus dem Merkmal. Ein Zug, der
  sie verschöbe, verspräche etwas, das der Schnitt nicht einlöst; deshalb
  spiegelt der gegenüberliegende Knopf den gegriffenen.
* **Er kommt mit *Im Bild einstellen*, nicht mit der Auswahl** — wie der
  Bewegungsgriff an Bohrung und Langloch (Entscheidung Robert, 11.09.2026:
  „noch bevor ich auf im Bild einstellen anklicke ist das Gizmo schon da").
  Die Ansage ist der Zeiger der Platzierung (`set_placement_pointer`); mit ihm
  baut `set_gizmo` die Griffe, ohne ihn zeigt die Auswahl nur, was gewählt
  ist. Welche Arten das betrifft, sagt `placed_feature_kinds()` — dieselbe
  Quelle wie der Knopf rechts (`panels.LEADS_INTO_THE_VIEW`). An allen anderen
  Merkmalen bleibt die Auswahl die Ansage.
* **Und am Langloch stehen beide Griffe** — die Knöpfe für Länge und Richtung
  und die Pfeile und Ringe des Bewegungsgriffs, seit es sich versetzen und
  drehen lässt (RM-153). Der Ring um die Bohrachse dreht die Mittellinie.
* **Solange die Platzierung läuft, ist ein Zug am Bewegungsgriff ein
  Vorschlag** — wie am Langlochgriff. Pfeil: `featureMoveProposed`, Ring:
  `featureTurnProposed`; die Zahlen landen in *Merkmal verschieben* bzw.
  *Merkmal drehen*, der Griff bleibt an der neuen Stelle stehen
  (`_grip_shift`, `move_proposal_waits()`), die Maßlinien folgen über
  `PlacementFlow.move_to`, und erst das Übernehmen rechts macht einen Schritt
  (Regel 2). Ohne Platzierung — an einem Zapfen, Kegel, einer Kugel, die
  keinen Knopf ins Bild haben — bleibt der Zug ein Schritt wie seit dem
  03.09.2026. Anlass: Robert, 11.09.2026, „nach dem verschieben verschwindet
  das gizmo gleich ohne auf übernehmen zu klicken".
* **Nach dem Übernehmen kommen Maße und Griffe wieder** — am selben Merkmal,
  an seiner neuen Stelle (`MainWindow._measures_to_resume`, eingelöst in
  `_show_feature_fields` über denselben Weg wie der Knopf). Jede Operation
  beendet die Platzierung; wer aus ihr heraus übernommen hat, will danach
  weiter im Bild arbeiten (Konzept Merkmalbedienung §4, Abnahme 1). Wechselt
  das Merkmal dabei seinen Namen (`hole_1` → `slot_1`, zugesagt), findet
  `_reselect_the_renamed` es an der Stelle wieder, die der Schritt genannt
  hat — nach Baum **und** Ansicht, sonst geht die Nachwahl im Aufbau verloren.
* **Ein wartender Langlochzug und ein Versetzen warten zusammen.** Der Zug am
  Bewegungsgriff lässt den gezogenen Umriss stehen (`_end_drag` beendet ihn
  nicht mehr, `_detach_gizmo` leert `_slot_target` nicht mehr; der neue Griff
  trägt `_slot_waiting`), die Stelle geht in die Felder von *Zum Langloch
  ziehen*, und `slot_hole` schneidet Länge und Stelle in **einem** Schritt
  (`slotDragged` trägt die Stelle als viertes Argument). Verworfen wird der
  Zug nur, wenn er selbst endet: Übernehmen, Escape (`cancel_slot_drag`),
  Auswahlwechsel, Szenenaufbau (`drop_move_proposal`). Anlass: Robert,
  11.09.2026, „das langloch ziehe und dann das langloch nochmal über das gizmo
  verschieben will ist es wie abbrechen".
* **Am Merkmal zielt die Platzierung nie.** Bis zum Abend des 11.09.2026 war
  ein Klick neben dem Griff die Ansage, „woanders hinzuwollen": Die
  Platzierung löste sich vom Merkmal, die Bohrungsvorschau klebte am Zeiger
  wie beim Setzen einer neuen, und der Weg heraus war nicht zu finden
  (Robert: „auf einmal war ich im modus eine neue Bohrung zu setzen … er
  sollte an der stelle ja nichtmal kommen"). Wohin ein vorhandenes Loch soll,
  sagen der Griff und die Felder rechts; ein Klick ins Bild gehört der Auswahl
  (`PlacementFlow.pointer` gibt ihn im Zustand „sitzt am Merkmal" zurück).
* **Escape verlässt die Maße** (`MainWindow._leave_the_measures`) — vor der
  Auswahlstufe, wie jedes Werkzeug: Ein wartender Langlochzug und ein
  vorgeschlagenes Versetzen werden verworfen, gerechnet ist bis dahin nichts;
  die Auswahl bleibt, das nächste Escape geht die Stufe zurück.
* **Die Maßlinien weichen dem Griff.** Sie laufen alle in der Mitte des
  Merkmals zusammen, und dort sitzen Pfeile und Ringe; die Maßfläche spart
  die Griffspanne aus ihrer Maske aus (`_Dimensions.clearing`, aus
  `gizmo_reach()` wie die Felder). Der Umriss des Lochs bleibt darunter
  sichtbar. Anlass: „das verschieben ist auch schwer durch die maßlinien zu
  treffen/sehen".
* **Ein Baustein sitzt sofort, und am gesetzten Baustein hängt ein Griff.**
  Ein Baustein aus dem Katalog geht von selbst in die Platzierung — und seit
  dem 11.09.2026 sitzt er dort ohne Klick auf der gewählten Fläche, sonst auf
  der größten nach oben zeigenden (`PlacementFlow._begin_on_a_face`,
  `UPWARD_FACE`), mit Werkzeugkörper, Maßlinien und den Feldern im Dialog.
  Vorher stand mit gewähltem Körper und der Maus neben dem Teil nichts im
  Bild, und *Übernehmen* schrieb einen roten Schritt ohne Position (Robert:
  „im viewport gab es weder vorschau, noch das gizmo dazu"; gemessen an allen
  24 einsetzbaren Bausteinen). Sobald die Stelle steht, hängt am
  Werkzeugkörper der Bewegungsgriff (`viewport.grip_placement`,
  `placementDragged` → `_dragged_at_the_tool` → `move_to`); der Griff der
  Auswahl weicht ihm, weil beide an derselben Stelle säßen, und kommt mit
  Escape zurück. **Ein Klick bestätigt keine Stelle, die niemand gewählt
  hat**: Nach dem Sitz von selbst setzt er um (`_seated_by_default`), erst
  der nächste übernimmt. Nur Bausteine — die Bohrung wird gezielt gesetzt, und
  dieser Weg ist eingespielt.
* **Das gewählte Loch ist selbst der Griff.** Ein Druck der linken Taste auf
  ein gewähltes Loch (oder Langloch), solange keine Platzierung läuft, baut
  den Langlochgriff für diesen einen Zug und gibt ihm den Druck
  (`_pull_at_the_hole` → `SlotHandle.take_press`, der nähere Knopf); der Zug
  rechnet wie am Knopf, aus der Mitte heraus. Das Loslassen ist der
  gewohnte Vorschlag (`slotProposed`), und das Fenster holt dazu die Maße ins
  Bild (`_on_slot_proposed` → `request_in_view`) — ab da stehen Knöpfe,
  Umriss, Griff und Maßlinien wie nach dem Knopf. Neben dem Loch bleibt die
  linke Taste beim Körper, wie das `solidon`-Schema es sagt. Anlass: Robert,
  11.09.2026, „wenn ich jetzt eine bohrung an einer ecke zum langloch ziehen
  will verschiebe ich immer den körper" — die Knöpfe kamen erst mit dem Knopf,
  und ein Zug am Loch war bis dahin ein Zug am Körper darunter.
* **Der Ring um die Bohrachse dreht das Langloch** — nicht seine Achse.
  `_slot_turn_sign` erkennt den Ring, der parallel zur Achse des
  Langlochgriffs läuft (`SLOT_RING_ALIGNED`); während des Zugs folgen Griff,
  Marke und Beschriftung dem gerasteten Winkel (`_turn_slot_with`, Ansatz in
  `_slot_turn_base`), und das Loslassen ist derselbe Vorschlag wie ein Zug an
  den Knöpfen (`_on_slot_released` → *Zum Langloch ziehen* mit neuer
  Richtung). Die zwei anderen Ringe kippen die Achse und bleiben *Merkmal
  drehen*. Anlass: Robert, 11.09.2026, „bei gizmo vom langloch dreht sich
  die vorschau vom langloch noch nicht".
* **Die Marke folgt dem Griff, solange er steht** (`_slot_form_of`): dem
  wartenden Zug, dem Zwischenstand einer Geste an Knöpfen oder Ring, sonst
  den Maßen des Merkmals. `_repaint_preview` tauscht dabei nur die Punkte
  (`update_points`), solange die Form ihre Punktzahl behält — ein Aktor je
  Mausbewegung wäre ein Neuaufbau je Mausbewegung.
* **Ein Klick auf das Modell verlässt die Maße nicht.** Solange eine
  Platzierung läuft, nimmt `_on_left_click` einen Klick, der das Modell
  trifft, gar nicht erst an — wer den Pfeil des Griffs verfehlt, wählt nicht
  die Fläche daneben (Robert, 11.09.2026: „solange der klick auf dem modell
  ist sollte das nicht passieren"). Heraus führen drei Wege, alle über
  `MainWindow._leave_the_measures`: Escape, *Abbrechen* rechts unter
  *Übernehmen* (`FeaturePanel.cancelRequested`, sichtbar nur mit Maßen im
  Bild — `set_measuring`) und der Klick ins Leere (`_on_object_picked("")`).
  Alle drei verwerfen, was wartete; gerechnet ist nichts (Regel 2). Ein
  Auswahlwechsel über `select_features` verwirft ebenso wie `select_feature`.
* **Die Marke trägt die Langlochform, und sie geht beim Zug mit.** Ein
  wartender Langlochzug (`_slot_waiting`) und ein erkanntes Langloch werden
  als Stadion gezeigt, in die Tiefe gezogen (`_feature_shape` →
  `_slot_form_of`, `shapes.prism` über `slot_outline`) — nicht als Zylinder
  der Bohrung, aus der es kommt. Nach dem Zug an den Knöpfen und nach jeder
  getippten Zahl wird die Marke neu gezeichnet (`_repaint_preview`). Ein Zug
  am Bewegungsgriff nimmt Marke, Knöpfe **und** Umriss mit
  (`SlotHandle.shift`), und der frisch gebaute Griff danach trägt den Umriss
  von Anfang an (`outlined=`), nicht erst mit dem nächsten Zug. Anlass:
  Robert, 11.09.2026, „wenn ich die bohrung zum langloch schiebe im viewport
  und das langloch dann verschiebe fehlt die richtige vorschau".
* **Kürzer als `prepare.shortest_slot` lässt er sich nicht ziehen.** Der Kern
  lehnt das ab (`prepare.SLOT_TOO_SHORT`), und eine Geste, die in einer Absage
  endet, ist keine Bedienung. Der Rückweg zum runden Loch ist Strg+Z und nicht
  ein Zug, der unterwegs seine Bedeutung wechselt.

  **Die Zahl steht im Kern, nicht hier.** Bis zum 11.09.2026 führte der Griff
  eine eigene (`SHORTEST_SHARE = 1.05`) — und rastete damit genau dort, wo die
  Merkmalserkennung kippt: Wer bis zum Anschlag zurückzog, hatte danach im
  Objektbaum eine Bohrung statt seines Langlochs oder gar nichts mehr. Warum
  die Grenze da liegt, wo sie liegt, steht in
  `.claude/rules/operationen.md`; der Griff und die Leiste fragen.

Wo er sitzt, sagt das Register (`slot_feature_kinds()` aus dem `applies_to` von
*Zum Langloch ziehen*) — eine Aufzählung in der Ansicht wüsste beim nächsten
Zuwachs die Hälfte. Und er steht in der Vorfahrt von `_on_pointer`, wie jeder
Griff: `tests/test_viewport_decisions.py` liest sie im Quelltext gegen die
Griff-Felder und kennt seit diesem Griff keine Namensliste mehr, sondern die
Bauart (`Gizmo` oder `…Handle`).

### Ein Zug an einer Form endet in einer Leiste, nicht im Verlauf

Bei einer **Bewegung** ist die Stelle, an der man loslässt, die Aussage — dort
wird der Zug sofort ein Schritt. Bei einer **Form** nicht: Länge und Richtung
sind zwei Zahlen, und wer sie auf den Millimeter meint, trifft sie mit der Maus
nicht. Ein Schritt, der beim Loslassen entsteht, wird dann zu einer Kette aus
Korrekturen statt einer Handlung.

Zwischen Zug und Operation steht deshalb eine dritte Stufe: Der Umriss bleibt
stehen, `Viewport.slotProposed` schreibt seine zwei Maße in die Felder unter
*Zum Langloch ziehen* im Merkmalfenster, und erst das Übernehmen dort meldet
`slotDragged` (über `Viewport.apply_slot_drag`, die eine Stelle, an der aus
dem Zug ein Schritt wird). Eingabetaste übernimmt, Escape verwirft
(`_drag_kind` bleibt dafür auf `"slot"`).

**Die Stufe hatte bis zum 11.09.2026 eine eigene Leiste** (`slot_bar.py`),
unten mittig neben der Leiste der Flächenplatzierung. Das Argument dafür war,
dass zwei Leisten, die dasselbe tun, an dieselbe Stelle gehören — und es war
richtig, solange die Zahlen nirgends sonst standen. Seit sie im
Merkmalfenster stehen, waren es zwei Bedienstellen über demselben Loch, mit
zwei Übernehmen (Robert: „auch 2 mal übernehmen einmal unten und einmal
rechts … die untere leiste uns sparen und nur die rechte verwenden mit dem
was schon drin ist").

**Was von ihr bleibt, ist eine Frage und kein Widget:**
`Viewport.slot_drag_waits()` sagt, ob ein Zug auf seine Bestätigung wartet —
gemessen am gemerkten Merkmal (`_slot_target`) und nicht an `_drag_kind`,
denn jenes setzt erst die Zugbewegung, und ein ohne Bewegung losgelassener
Griff wartet genauso.

**Der Versatz eines Knopfes zählt gegen die gebaute Geometrie.**
`Item.set_position` verschiebt gegen das, was einmal in den Puffer geschrieben
wurde; gerechnet wurde er aus dem Stand beim **Drücken**. Beim ersten Zug ist
das dasselbe, ab dem zweiten wandert der Bezug mit, während der Puffer bleibt
— die Knöpfe laufen aus dem Umriss heraus, und weil ihr `reach` das Vorzeichen
tauscht, in entgegengesetzte Richtungen. `SlotHandle._built_seats` hält, wo sie
gebaut wurden.

**Gefragt wird der Zustand und nie `isVisible()`.** Das galt schon der
gefallenen Leiste (`SlotBar.active`) und gilt der Frage, die an ihre Stelle
getreten ist: Qt beantwortet die Sichtbarkeit falsch, solange nichts gezeigt
wurde — offscreen also immer. Wer eine Bedingung daran hängt, prüft die
Prüfumgebung statt der Sache.

### Ein Griff steht vor allem, was über der Ansicht liegt (11.09.2026)

`Viewport._on_pointer` hat eine feste Vorfahrt, und sie ist am 11.09.2026 um
eine Stufe gewachsen: **Griffe, dann eine laufende Platzierung, dann der
Zeiger, zuletzt die Kamera.** Die Platzierung stand davor und nahm jede
Mausbewegung als Zielversuch — ein Griff sah danach kein `move` mehr, seine
Hover-Auswahl blieb leer, und sein `press` fiel an `self._selected is None`
durch. Pfeile, Ringe und die zwei Knöpfe am Loch waren sichtbar und tot,
sobald eine Bohrung gewählt war und die Platzierung von selbst begann.

Verschluckt wird dabei nichts: Ein Griff nimmt ein `move` nur, wenn er
gedrückt gehalten wird, und ein `press` nur über einem getroffenen Pfeil.

**Und mit gedrückter Taste wird er gar nicht erst gefragt** (13.09.2026). Wer
eine Taste hält, führt die Kamera oder den Körper; die Hervorhebung unter dem
Zeiger sagt dabei nichts — dieselbe Regel, die der Zeiger seit je befolgt („Ein
Zug an der Kamera stoppt die Suche ganz"). Jeder Griff, der nicht selbst zieht,
stellte dafür einen eigenen `pick_item`, und das liest den Kennungspuffer.
Gemessen am echten Fenster (`drilled_v6.p3d`, Bild 1030 mal 710, Drehgeste über
40 Ereignisse, Median aus drei Läufen):

| | je Zeigerereignis | `pick_item` |
|---|---|---|
| ohne Griff | 0,47 ms | 0 |
| mit Bewegungsgriff und Würfel | **4,31 ms** | 80 für 40 Bewegungen |
| dieselbe Geste danach | 0,45 ms | 0 |

`_on_pointer` überspringt dafür jeden Griff, der nicht `pressing` ist, sobald
`event.buttons` belegt ist — der **ziehende** Griff bekommt seine Bewegungen
weiter, sonst bliebe der Zug am Pfeil beim ersten Bildpunkt stehen
(`tests/test_viewport_decisions.py::test_a_held_button_leaves_the_grips_out_of_the_way`).
Freies Schweben ohne Taste hebt weiter hervor; dort ist die Suche die Auskunft.

**Und die zweite Ebene ist Qt selbst.** Was als Widget über der Renderfläche
liegt, bekommt die Zeigerereignisse vor jedem `PointerEvent` — die Vorfahrt
oben kommt dann gar nicht zum Zug. Wer etwas darüberlegt, fragt
`Viewport.gizmo_reach()` und hält den Platz frei; `PlacementFlow` tut das für
seine Maßfelder.

### Ein Zug an einer Form schreibt erst, wenn er übernommen wird

Der Langlochgriff und die Flächenplatzierung meinen dasselbe Loch und etwas
Verschiedenes damit: der eine ein Langloch, die andere eine runde Bohrung.
Nebeneinander offen nahm der eine zurück, was der andere gerade getan hatte.

**Gemeldet wird deshalb das Übernehmen und nicht das Ziehen**
(`Viewport.slotStarted`). Solange die Leiste offen ist, ist nichts geschehen
(Regel 2) — und die Maße der Platzierung sollen währenddessen im Bild stehen.
Wer den Zug beim Beginn meldet, schließt genau die Maße weg, um die es geht.

### Wo etwas schon sitzt, zielt der Zeiger nicht

`PlacementFlow._seated_at_feature`: Beginnt die Platzierung an einem
vorhandenen Merkmal, gehört die Stelle ihm. Eine Mausbewegung darüber verschob
sie samt aller Maßlinien unter der Hand, und die Abstände liefen vom Zeiger
statt von der Bohrungsmitte. Ein **Klick** ist die ausdrückliche Ansage, das
Loch woanders hinzusetzen; danach zielt wieder der Zeiger. Beim Setzen einer
neuen Bohrung wird der Merker nie gesetzt.

**Geschluckt wird nur die freie Bewegung.** Ohne die Frage nach
`event.buttons` nahm die Zusage auch jeden Kamerazug mit — Drehen und Schieben
mit rechter und mittlerer Taste waren tot, solange eine Bohrung gewählt war.
Was die Platzierung nicht braucht, gehört der Kamera; das ist dieselbe Regel,
die für die linke Taste seit je gilt.

**Und der Klick, der neu zielt, ist verbraucht.** Er hebt zusätzlich den
eingefrorenen Zustand auf und kehrt sofort zurück. Ohne das fiele er in die
`confirm`-Kette und **übernähme** die Platzierung, statt sie neu auszurichten —
auch der Klick daneben, der nach §18.5 die Auswahl aufheben soll.

### Ein gewähltes Merkmal bekommt seinen Griff ohne Werkzeug (10.09.2026)

Der Schalter des Werkzeugs *Bewegen* gilt dem **ganzen Körper**: Dort trägt der
Griff einen Skalierwürfel, und der ändert auf einen Zug die Maße des Teils — er
gehört an ein Werkzeug, das man ausdrücklich öffnet. Ein angeklicktes Merkmal
ist dagegen selbst die Ansage (Robert, 10.09.2026: „über den viewport sehen wir
weder maße noch etwas zum verschieben, verlängern, drehen usw" — gewählt war
eine Bohrung, das Merkmalsfenster zeigte sechs Felder, und im Bild stand
nichts). §2.6 verspricht, dass am Merkmal alles direkt steht; der Würfel bleibt
dabei weg, und die Bedingung dafür ist dieselbe wie eh und je.

**An einer Fläche geht der Zug bis in den Verlauf durch** (Anschluss geprüft
am 14.09.2026): `gizmo_feature` sagt, wo der Griff sitzt, `gizmo_target`, was
er tut, `_face_seat` setzt ihn auf Mitte und Normale **dieser** Fläche, und
`faceDragged` meldet ihre Kennung — nicht mehr ihre Normale. Das Fenster macht
daraus `push_face` mit `face=<Kennung>`; die Richtungsfelder `nx/ny/nz` bleiben
nur für gespeicherte Schritte stehen.

**Außer die Fläche kam aus einem Baustein** (16.09.2026). Dann antwortet
`gizmo_target` mit nichts — es gibt kein Press/Pull an einer Fläche, die mit
dem Träger verschmolzen ist —, `gizmo_feature` hängt den Bewegungsgriff daran,
`_emit_feature_drag` meldet `featureMoved`, und der Zug geht in den Schritt des
Bausteins; ein Vorschlag (`proposing`) wird daraus nie, denn rechts stehen die
Handlungen des Bausteins und keine Felder von *Merkmal verschieben*. An der
Rippe, die aus nichts als Flächen besteht, stand bis dahin der Pfeil entlang
der Normalen und der Satz über Press/Pull (Robert: „bei manchen bausteinen
keine möglichkeit zum verschieben"). Die Regel selbst steht in
`fenster.md` unter „Ein Merkmal aus einem Baustein meint den Baustein".

**Und zwei weitere Lagen bekamen dort gar keinen Griff.** Beide sind
Nebenwirkungen von Bedingungen, die für ein *freies* Merkmal richtig sind:

* **Die Bohrung eines Bausteins.** `placed_feature_kinds` hält Griffe an
  Bohrung und Langloch zurück, bis *Im Bild einstellen* gedrückt ist — und
  diesen Knopf zeigt nur `show_feature`, nicht `show_part`. An einem
  Schraubenloch trug die Senkung damit einen Griff und die Bohrung daneben
  keinen. `set_gizmo` nimmt die Sperre für Bausteinmerkmale heraus und lässt
  dort die Langlochknöpfe weg: Ihr Zug schnitte ein Langloch neben den
  Schritt, und beim nächsten Verschieben bliebe es stehen.
* **Das Dach im Objektbaum.** Es wählt alle Merkmale des Bausteins, und
  `_remember_feature_refs` setzt „das gewählte Merkmal" bei mehreren auf
  nichts — der Griff fiel auf den Körper zurück, mit Skalierwürfel.
  `set_part_grip` nimmt vom Fenster entgegen, an welchem Merkmal er hängt;
  die Ansicht könnte nur je Merkmal fragen, ob es aus *irgendeinem* Baustein
  kam, und nicht, ob die ganze Auswahl **ein** Baustein ist. Vorher trug der Schritt die Richtung, und
die Operation bewegte jede Fläche, die dorthin zeigt — an einer Treppe alle
Stufen zugleich. **Die vier Stücke waren einzeln geprüft und die Kette nicht**
(`test_the_handle_of_a_chosen_face_pushes_that_face` fährt sie am Stück).

## Der Bewegen-Griff ist eigener Code, kein fremdes Widget (05.09.2026)

Bis zum 05.09.2026 war der Griff PyVistas `AffineWidget3D`, und er hatte zwei
Fehler übereinander, die einander verdeckten (Vorfall: ROADMAP-ARCHIV.md,
04.09.2026): Das Widget suchte seinen Renderer über den Interaktionsstil
(`_parent`), den Solidons eigener Stil nicht hatte — jede Mausbewegung über
dem Griff endete in einem `AttributeError`, den pyvistaqt zu einer Warnung
machte, die niemand sieht. Und sein `vtkHardwarePicker` traf in dieser
Umgebung nichts, nicht einmal den Körper in der Bildmitte. **Der Griff war
nicht greifbar**; was weiter ging, war die eigene Zuggeste am Körper.

Beides ist mit dem Widget verschwunden. `app/ui/render/gizmo.py` zeichnet
Pfeile, Ringe und Würfel über den Vertrag, pickt über `pick_item` und
bekommt die Zeigerereignisse **vor** dem Navigator (`Viewport._on_pointer`).
Was davon bleibt, sind zwei Regeln:

* **Der Griff pickt über den Vertrag, nie mit einem eigenen Picker.**
  `pick_item` fragt in zwei Stufen — erst, was vor dem Material liegt
  (`keep_in_front`), dann alles andere — mit einer Toleranz in Bildpunkten
  (`PICK_SLACK_PIXELS`). Ein Griff, der seinen eigenen Picker mitbringt,
  trifft auf der einen Maschine und auf der anderen nicht.
* **Was der Griff zeigt, solange gezogen wird, ist Vorschau** (Regel 2):
  `set_matrix` am Element des Körpers, und beim Loslassen wird die Matrix zu
  Operationen (`_on_gizmo_released`) — oder zu nichts, wenn der Zug unter der
  Fangschwelle blieb. Deshalb wird der Griff nach jedem Zug **frisch gebaut**:
  Er rechnet gegen die Matrix, mit der er anfing, und ein stehen gelassener
  Griff hinge nach der Auswertung an einem Element, das nicht mehr im Bild ist.

### Frei drehen, aber 45 Grad treffen

Der Winkelfang stand auf null, weil ein hartes Raster jeden kleinen Zug
verschluckte. Damit trifft aber niemand genau 45 Grad. Robert: „freies drehen,
aber kurzes einrasten bei allen 45 grad winkeln außer man dreht weiter."

`geom.transform.snap_near(wert, schritt, zone)` ist das Gegenstück zu
`snap_to_step`: Es zieht **nur in der Nähe** eines Vielfachen. Der Viewport
fragt es über `_settled_angle` — hat die Leiste einen Winkelfang eingestellt,
gilt der hart, sonst der Magnet (`TURN_MAGNET_STEP` 45°, `TURN_MAGNET_ZONE` 4°).

**Sichtbar wird das über den `interact_callback` des Griffs**: Er bekommt
jeden Zwischenstand und darf eine berichtigte Matrix zurückgeben, und die
wird gesetzt, nicht die rohe (`_on_gizmo_interacted`, gedreht über
`rotation_about` im Kern, denn die Ansicht rechnet keine Geometrie). Die
Rechnung des Griffs bleibt unberührt: Sie geht jedes Mal von der Matrix beim
Greifen und der Zeigerstelle aus, nicht vom letzten Ergebnis. PyVistas Widget
rief seinen Rückruf **vor** dem Setzen und übergab die alte Matrix; dafür
brauchte es einen eigenen Beobachter am `MouseMoveEvent` (`_magnetise_turn`),
und den gibt es nicht mehr (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026). Geprüft
in `tests/test_transform_ui.py::test_the_magnet_corrects_the_turn_while_it_runs`.

## Was am Griff steht, ist ASCII — und sonst nichts

Die Griffbeschriftung war ein `vtkStringArray` in PyVistas Hand, und PyVista
lehnte darin jedes Zeichen außerhalb von ASCII ab — nicht mit einer Warnung,
sondern mit `ValueError: String array contains non-ASCII characters that are
not supported by VTK`; der ganze Griffaufbau stürzte damit ab. Diese Grenze
war VTKs und ist mit ihm gegangen: Der Renderer zeichnet Beschriftungen
selbst. **Die Regel bleibt trotzdem**, denn ihr zweiter Grund steht noch:
Der Griff ist der eine Ort in der Oberfläche, an den ein übersetzter Text nicht
gehört — überall sonst zeichnet Qt, und ein Wort am Griff stünde in sechs
Sprachen an einer Stelle, die keine Prüfung sieht.

**Der Fall wäre auf Deutsch nie aufgefallen.** Deutsch ist „Oberseite",
„Unterseite", „Vorderseite" — alles ASCII. Französisch nicht: `Face
supérieure`, `Arrière`, `Côté gauche`, `Côté droit`, vier von sechs. Ein Torlauf
in deutscher Umgebung hätte geschwiegen — die Sorte Fehler, die es bis zum
Kunden schafft (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

**Wohin der Text stattdessen gehört:** in die Statusleiste. Sie zeigt bei
gewähltem Merkmal ohnehin „Platte · Oberseite", dort zeichnet Qt, und dort
darf jede Sprache stehen. Am Griff bleibt, was keine Übersetzung braucht —
`X`, `Y`, `Z`, `S` und `<->` für eine Fläche, die nur vor und zurück kennt.

Gesichert durch `tests/test_selection.py::test_nothing_on_the_gizmo_leaves_ascii`,
und zwar mit genau diesen vier französischen Namen als Eingabe. Ein Absatz
hier wird gelesen, wenn jemand ihn sucht; der Test wird rot, wenn jemand es
wieder tut.
