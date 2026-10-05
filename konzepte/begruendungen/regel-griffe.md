# Begründungen zu `.claude/rules/griffe.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

## Regeln für die Griffe in der Szene

Was der Nutzer unmittelbar am Modell anfasst: der Griff am Langloch, der
Bewegen-Griff, die Beschriftung daran. **Ausgegliedert aus `ansicht.md` am
18.09.2026** — die übrigen Ansichtsregeln gelten weiter und laden zusätzlich,
sobald jemand am Viewport arbeitet. Der Grund für den Schnitt: Diese vierzig
Kilobyte gelten für zwei Dateien, luden aber für dreiundzwanzig.

## Ein Griff steht vor allem, was über der Ansicht liegt

`Viewport._dispatch_pointer` hat eine feste Vorfahrt, und sie ist am 11.09.2026 um
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

`_dispatch_pointer` überspringt dafür jeden Griff, der nicht `pressing` ist, sobald
`event.buttons` belegt ist — der **ziehende** Griff bekommt seine Bewegungen
weiter, sonst bliebe der Zug am Pfeil beim ersten Bildpunkt stehen
(`tests/test_viewport_decisions.py::test_a_held_button_leaves_the_grips_out_of_the_way`).
Freies Schweben ohne Taste hebt weiter hervor; dort ist die Suche die Auskunft.

**Und die zweite Ebene ist Qt selbst.** Was als Widget über der Renderfläche
liegt, bekommt die Zeigerereignisse vor jedem `PointerEvent` — die Vorfahrt
oben kommt dann gar nicht zum Zug. Wer etwas darüberlegt, fragt
`Viewport.gizmo_reach()` und hält den Platz frei; `PlacementFlow` tut das für
seine Maßfelder.

## Der Bewegen-Griff ist eigener Code, kein fremdes Widget

Bis zum 05.09.2026 war der Griff PyVistas `AffineWidget3D`, und er hatte zwei
Fehler übereinander, die einander verdeckten (Vorfall: ROADMAP-ARCHIV.md,
04.09.2026): Das Widget suchte seinen Renderer über den Interaktionsstil
(`_parent`), den Solidons eigener Stil nicht hatte — jede Mausbewegung über
dem Griff endete in einem `AttributeError`, den pyvistaqt zu einer Warnung
machte, die niemand sieht. Und sein `vtkHardwarePicker` traf in dieser
Umgebung nichts, nicht einmal den Körper in der Bildmitte. **Der Griff war
nicht greifbar**; was weiter ging, war die eigene Zuggeste am Körper.

* **`Gizmo.fits` sagt, wann ein frischer Griff dasselbe ergäbe.** Der
  Platzierungsfluss zeichnet je Kamerageste neu und hängte den Bewegungsgriff
  dabei jedes Mal ab und wieder an — sechs Renderer-Objekte für nichts (5,7 ms
  von 22 je `redraw`, 21.09.2026). `grip_placement` behält ihn jetzt, wenn er
  am selben Ziel hängt und entweder im Zug ist (`grip.pressing`) oder passt:
  gleiches Ziel, gleiche Ringe, gleicher Maßstab (auf ein Hundertstel,
  `SCALE_TOLERANCE` — der Maßstab hängt am Zoom und wandert in der Perspektive
  mit jeder Kameradrehung) und **gleiche Matrix** (`np.array_equal` gegen die
  gemerkte Matrix des Ziels). Beides sind genau die Fälle, in denen die Regel
  „immer frisch" nichts verlöre: Im Zug hat sich die Matrix seit dem Greifen
  nicht geändert, bei einem passenden Griff steht das Ziel unbewegt. Ein Griff
  **im Zug** neu zu bauen kostete den Zug — aus ihm wurde ein Kameraschwenk.

**Der Griff wird nie weiterbenutzt, immer frisch gebaut — mit zwei
Ausnahmen.** Er rechnet gegen die Matrix seines Ziels beim Greifen und merkt
sie sich über den Zug — ein stehen gelassener Griff wendete den vorigen Zug
beim nächsten doppelt an, und nach einer Auswertung hinge er an einem Element,
das nicht mehr im Bild ist. Das galt für PyVistas Widget und gilt für
`gizmo.Gizmo` genauso, weil die Rechnung dieselbe ist.

Seit dem 21.09.2026 baut `Viewport.grip_placement` ihn trotzdem **nicht** neu,
wenn er an demselben Ziel hängt und (a) gerade im Zug ist (`grip.pressing`)
oder (b) ohnehin passte: gleiches Ziel, gleiche Ringe, gleicher Maßstab,
gleiche Matrix (`Gizmo.fits`, siehe `griffe.md`). Der Widerspruch zur Regel
ist keiner: Beide Ausnahmen sind genau die Fälle, in denen ein frischer Griff
**dasselbe** ergäbe — im Zug hat sich die Matrix seit dem Greifen nicht
geändert (der Zug rechnet ja gegen sie), und bei (b) steht das Ziel unbewegt.
Was die Regel verbietet, ist ein Griff, der einen **vergangenen** Zug noch
in sich trägt; den gibt es hier nicht. Der Fluss der Platzierung zeichnet je
Kamerageste neu und hängte den Griff dabei jedes Mal ab und wieder an — sechs
Renderer-Objekte für nichts (5,7 ms von 22 je `redraw`), und ein Griff im Zug
verlor den Zug (aus dem Zug wurde ein Kameraschwenk). `grip.pressing` und
`Gizmo.fits` heilen beides. Und die Attrappen der Suite (`tests/render_fakes.py`)
erben vom Vertrag, und der ist abstrakt: Eine Methode, die es dort nicht gibt,
gibt es auch in der Attrappe nicht. Das ist die Lehre aus dem `Off()`, das es
an PyVistas Widget nie gab — der `AttributeError` verschwand in Qts
Slot-Behandlung, und ein Fake mit `Off()` hätte den Absturz genau so versteckt
wie die Suite.

Zwei Nachbarn: **Ein Zug am Griff lässt die Navigation in Ruhe.** PyVistas
Widget schaltete beim Greifen auf seinen Trackball-Stil um und stellte beim
Loslassen *seinen* Standard wieder her, nicht unseren, und jedes Zugende
musste `set_navigation` rufen. Der eigene Griff sieht die Zeigerereignisse vor
dem Navigator und gibt frei, was er nicht braucht;
`tests/test_analysis_ui.py::test_a_drag_leaves_the_navigation_in_place` hält
fest, dass kein Zugende den Navigator neu baut. Und der Skaliergriff
(`app/ui/scale_widget.py`) folgt demselben Muster wie `gizmo.py` — Hover über
`pick_item`, Zug in der Kameraebene über `ray_plane_hit`, Ergebnis beim
Loslassen —, und wer das Interaktionsmuster an einer Stelle ändert, ändert es
an beiden.

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

## Ein gewähltes Merkmal bekommt seinen Griff ohne Werkzeug

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

### Am Bausteinmerkmal zieht der ganze Baustein mit

Ein Zug an einem Merkmal, das als Baustein zieht (`moves_as_a_part`), zeigt
die Dreiecke **aller** Merkmale desselben Schritts (`created_by`) als einen
Aktor vor dem Körper, geführt mit der Matrix des Griffs
(`_show_part_drag`, `_drag_part`) — vorher wanderte nur die Marke des
angefassten Merkmals, und der Rest rückte erst beim Loslassen nach. Führt
das Verschieben den Sitz aus der ebenen Fläche (plus der eigenen Grundfläche,
`_landing_of`), wird der Baustein rot (`PART_OFF_FACE_COLOUR`) **und** das
Zugfeld sagt „neben der Fläche" — nie die Farbe allein (Regel 18). Sitzt der
Baustein auf keiner ebenen Fläche, gibt es keine Aussage statt einer
falschen. Der Aktor gehört dem Zug und geht mit dem Geist (`_drop_ghost`).

**Die eigene Grundfläche ist der Umriss, nicht die Böden** (Durchsicht
0.5.1): die konvexe Hülle der eigenen Dreiecke in der Ebene samt der Öffnung
am Sitz (`_footprint_fan`). Der Sitz eines Schlüssellochs liegt über seiner
durchgehenden Bohrung, deren Wände die Erkennung einem Merkmal ohne Baustein
zuschlägt; nur mit den eigenen Dreiecken gab es dort keinen Grund, die
Landefläche hieß `None`, und am Wabenhalter blieb der Zug neben die Deckfläche
stumm, bis nach dem Loslassen „Der Schnitt hat nichts abgetragen“ kam. „Auf
keiner ebenen Fläche“ heißt jetzt: kein fremdes Dreieck in der Höhe des Sitzes.

## Der Langlochgriff zieht die Form, nicht die Lage

Der Bewegungsgriff schiebt und dreht, der Würfel skaliert den Körper — und aus
einer Bohrung wird damit nie ein Langloch. Der Weg dorthin war ein Dialog mit
zwei Zahlen, und Robert hat ihn am gefahrenen Weg abgelehnt: „das langloch soll
auch über den viewport einstellbar/erstellbar/änderbar von bohrung zu langloch
sein". `app/ui/slot_handle.py` ist die Antwort — zwei Knöpfe an den Enden des
Lochs, gezogen wird in der Ebene seiner Mündung.

* **Der Winkel kommt aus einer Quelle.** Gezählt wird gegen die x-Achse von
  `sketch.planes.frame_of` — dieselbe, gegen die `prepare.slot_profile`
  schneidet und `prepare_ops.slot_angle_of` ein erkanntes Langloch nachmisst.
  Eine eigene Achse in der Ansicht wäre ein Loch, das um einen Winkel neben dem
  Umriss liegt, den der Kunde beim Ziehen gesehen hat — und kein Test über
  Zahlen allein sähe es. `tests/test_slot_handle.py` schneidet deshalb wirklich
  und misst die Richtung am erkannten Ergebnis nach.

* **Das gewählte Loch ist selbst der Griff.** Ein Druck der linken Taste auf
  ein gewähltes Loch (oder Langloch), solange keine Platzierung läuft, baut
  den Langlochgriff für diesen einen Zug und gibt ihm den Druck
  (`_pull_at_the_hole` → `SlotHandle.take_press`, der nähere Knopf). **Am
  Langloch zählt die ganze Öffnung** — auch ihre Enden: Die Zielhilfe rechnet
  gegen den Umriss des Langlochs und nicht gegen einen Kreis um seine Mitte
  (`bore_span` mit `travel`/`heading`, `_feature_inside` gegen die
  Mittellinie). Bis zum 24.09.2026 fiel ein Druck in das Ende eines
  Langlochs in der Draufsicht durch das Loch hindurch, und die linke Taste zog
  den Körper. **Und der Knopf wandert um den Weg der Hand, er springt nicht
  auf sie** (`SlotHandle._grab`, `_grab_at`): Wer ihn neben seiner Mitte oder
  in der Öffnung greift, verschob das Langloch sonst beim ersten Bildpunkt —
  am Wedge-Lock gemessen 16 Grad Drehung, bevor die Hand sich bewegt hatte.
  Nur an der runden Bohrung rechnet ein Druck ins Loch aus der Mitte heraus:
  Sie hat keine Richtung, die zu erhalten wäre. Das Loslassen ist der
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

* **Und je Mausbewegung entsteht ein Bild, nicht zwei.** Während eines Zugs
  an den Knöpfen zeichnet `SlotHandle._drag` nicht selbst
  (`_redraw(render=False)`); die Marke folgt über `_on_slot_interacted`, und
  `_repaint_preview` sagt, ob sie gezeichnet hat — nur wenn nicht, rendert
  der Viewport nach. Gemessen am 21.09.2026 im echten Fenster mit `cProfile`:
  32 ms je Bewegung mit zwei Bildern, 21 ms mit einem; der Grundpreis je Bild
  ist der Durchgang mit Umgebungsverdeckung, 12 bis 17 ms (RM-200).

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
* **Unter `prepare.shortest_slot` rastet er auf die runde Bohrung**
  (Entscheidung Robert, 24.09.2026: „wenn man ein langloch so zieht, dass es
  wieder eine normale Bohrung wäre, sollte es kurz einrasten"). Zwischen der
  Breite und der kürzesten Länge gibt es kein Loch, das die Erkennung hält;
  `settled_length` hält im oberen halben Streifen die kürzeste Länge und
  legt den unteren auf die Breite selbst. Rund ist genau die Breite
  (`prepare.is_round_length`, auf die halbe Anzeigestufe), und dieselbe
  Funktion fragen Griff, Felder, Vorschauwerkzeug (`placement.prepare_tool`)
  und beide Kerne. Eingerastet zeigt der Umriss einen Kreis und die Zahl am
  Zeiger heißt „Bohrung" statt „Länge" — Form und Wort, nicht die Form
  allein (Regel 18). Die Richtung bleibt beim Einrasten die, die galt — an
  beiden Knöpfen, auch am gespiegelten: Ein rundes Loch hat keine, und ein
  Zug hinaus und zurück bleibt so ein Zug ohne Vorschlag; was an einer runden
  Bohrung rund endet, schlägt nichts vor (`Viewport._on_slot_released`).
  **Eine eingetragene Zahl rastet nicht** (`shown_length`): Zwischen Breite
  und kürzester Länge zeigt der Umriss die kürzeste Länge, und der Grund der
  Absage steht über der Vorschau — ein Kreis dort verspräche die runde
  Bohrung, die der Schnitt nicht macht. Übernommen macht *Zum Langloch ziehen* mit Länge = Breite wieder
  eine runde Bohrung; **war das Langloch aus einem Schritt gezogen und steht
  danach genau die Bohrung da, aus der es kam, fällt der Schritt**
  (`MainWindow._commit_slot_change`, `_slot_step_undone` liest die Bohrung aus
  der Sichtung vor dem Schritt), statt als Schritt ohne Wirkung im Verlauf zu
  stehen — Strg+Z holt ihn zurück, und die Quittung sagt es. **Außer ein
  späterer Schritt nennt das Langloch** (`_slot_named_later`): Dann wird der
  Schritt geändert, sonst verwiese eine Fase an `slot_1` auf ein Merkmal, das
  der Verlauf nie erzeugt hat. Bis zu dieser Entscheidung stand hier:
  „kürzer lässt er sich nicht ziehen, der Rückweg zum runden Loch ist
  Strg+Z".

  **Die Zahl steht im Kern, nicht hier.** Bis zum 11.09.2026 führte der Griff
  eine eigene (`SHORTEST_SHARE = 1.05`) — und rastete damit genau dort, wo die
  Merkmalserkennung kippt: Wer bis zum Anschlag zurückzog, hatte danach im
  Objektbaum eine Bohrung statt seines Langlochs oder gar nichts mehr. Warum
  die Grenze da liegt, wo sie liegt, steht in
  `.claude/rules/operationen.md`; der Griff und die Leiste fragen.

### Ein Zug an einer Form endet im Merkmalfenster, nicht im Verlauf

Bei einer **Bewegung** ist die Stelle, an der man loslässt, die Aussage — dort
wird der Zug sofort ein Schritt. Bei einer **Form** nicht: Länge und Richtung
sind zwei Zahlen, und wer sie auf den Millimeter meint, trifft sie mit der Maus
nicht. Ein Schritt, der beim Loslassen entsteht, wird dann zu einer Kette aus
Korrekturen statt einer Handlung.

Zwischen Zug und Operation steht deshalb eine dritte Stufe: Der Umriss bleibt
stehen, `Viewport.slotProposed` schreibt Länge und Richtung in den gemeinsamen
Maßentwurf von *Zum Langloch ziehen*. Übernehmen verarbeitet den vollständigen
Auftrag einschließlich Breite und Zielmitte. Der Tastaturweg über
`Viewport.apply_slot_drag` meldet `slotDragged` an denselben Abschluss; er
ersetzt den Entwurf nicht durch die zwei Griffwerte. Escape verwirft und
stellt die gemessenen Werte wieder her (`_drag_kind` bleibt dafür auf
`"slot"`).

**Die Stufe hatte bis zum 11.09.2026 eine eigene Leiste** (`slot_bar.py`),
unten mittig neben der Leiste der Flächenplatzierung. Das Argument dafür war,
dass zwei Leisten, die dasselbe tun, an dieselbe Stelle gehören — und es war
richtig, solange die Zahlen nirgends sonst standen. Seit sie im
Merkmalfenster stehen, waren es zwei Bedienstellen über demselben Loch, mit
zwei Übernehmen (Robert: „auch 2 mal übernehmen einmal unten und einmal
rechts … die untere leiste uns sparen und nur die rechte verwenden mit dem
was schon drin ist").

**Der Versatz eines Knopfes zählt gegen die gebaute Geometrie.**
`Item.set_position` verschiebt gegen das, was einmal in den Puffer geschrieben
wurde; gerechnet wurde er aus dem Stand beim **Drücken**. Beim ersten Zug ist
das dasselbe, ab dem zweiten wandert der Bezug mit, während der Puffer bleibt
— die Knöpfe laufen aus dem Umriss heraus, und weil ihr `reach` das Vorzeichen
tauscht, in entgegengesetzte Richtungen. `SlotHandle._built_seats` hält, wo sie
gebaut wurden.

Der Langlochgriff und die Flächenplatzierung meinen dasselbe Loch und etwas
Verschiedenes damit: der eine ein Langloch, die andere eine runde Bohrung.
Nebeneinander offen nahm der eine zurück, was der andere gerade getan hatte.

**Gemeldet wird deshalb das Übernehmen und nicht das Ziehen**
(`Viewport.slotStarted`). Solange die Leiste offen ist, ist nichts geschehen
(Regel 2) — und die Maße der Platzierung sollen währenddessen im Bild stehen.
Wer den Zug beim Beginn meldet, schließt genau die Maße weg, um die es geht.

## Maße und Platzierung am Merkmal

* **Der Maßeditor einer Bohrung erscheint mit der Auswahl.** Die erste
  Feld- oder Griffbetätigung beginnt den gebundenen Entwurf (§18.11).
  **Betätigt ist ein Griff mit dem Weg, nicht mit dem Druck.**
  `Viewport._dispatch_pointer` meldet `placementDragStarted` bei der ersten
  Bewegung jenseits von `CLICK_SLACK` (`Gizmo.dragging`,
  `SlotHandle.dragging`), auch für den Druck ins gewählte Loch
  (`_pull_at_the_hole`). Ein Klick ohne Weg auf Griff oder Loch bewegt
  nichts, meldet nichts und bindet nichts — die nächste Bohrung bleibt
  wählbar. Bis zum 27.09.2026 kam die Meldung beim Drücken: Am Wabenhalter
  hielt ein Klick auf die Mitte der gewählten Bohrung (dort beginnen die
  Pfeile) die Auswahl fest, und die Statuszeile verlangte, eine Änderung zu
  übernehmen, die es nicht gab (`test_render_gizmo.py`,
  `test_a_click_on_the_placement_grip_does_not_bind_the_draft`). Der Satz
  dazu geht mit dem Entwurf (`MainWindow.end_quiet_placement`).
  `PlacementFlow` besitzt die Fachfelder und seine Platzierungsgriffe; der
  allgemeine Merkmalsgriff bleibt dabei über `set_feature_gizmo_blocked`
  gesperrt. Ein reiner Verschiebungsauftrag zeigt keine Drehringe.
  Für weitere, noch nicht angeschlossene Merkmalsarten gilt der vorhandene
  ausdrückliche Einstieg über *Im Bild einstellen*.
* **Gesperrt heißt: ohne Pfeile, Ringe und Würfel — nicht ohne Knöpfe.**
  Die Sperre über `set_feature_gizmo_blocked` und der Platzierungsgriff am
  Werkzeugkörper nehmen dem Loch nur den Bewegungsgriff; Flächenscheibe und
  die zwei Langlochknöpfe bleiben (`set_gizmo`, `only_knobs`), und
  `grip_placement` baut sie nach dem ersten Griff wieder auf. Bis zum
  21.09.2026 nahm die Sperre die Knöpfe mit, und mit dem Maßeditor fehlten sie
  an jeder gewählten Bohrung (Robert: „wo sind eigentlich die markierungen um
  es zum langloch zu ziehen?") — geprüft an zwei Bildern derselben Lage, am
  Stand vor dem Editor genauso. Die Gizmo-Ansage bleibt dabei leer: Ein Satz
  über Pfeile, die nicht da sind, wäre die falsche Auskunft.

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
* **Und die Maße bleiben dabei im Bild.** Die Länge wächst um die Mitte, die
  Kantenmaße gelten ihr weiter; `PlacementFlow.redraw` hält Linien und Felder
  der gebundenen Maßgruppe, solange der Zug wartet, und zeichnet sie bei jeder
  Kameradrehung neu — nur der runde Umriss der Mündung weicht dem gezogenen
  des Griffs. Bis zum 21.09.2026 nahm sie die nächste Kameradrehung mit
  (Robert: „wenn wir das langloch ziehen und dann die ansicht drehen sind die
  maße weg"). Ohne Maßgruppe — beim Setzen eines neuen Werkzeugs aus dem
  Dialog — tritt die Platzierung weiter ganz zurück.

* **Escape verlässt die Maße** (`MainWindow._leave_the_measures`) — vor der
  Auswahlstufe, wie jedes Werkzeug: Ein wartender Langlochzug und ein
  vorgeschlagenes Versetzen werden verworfen, gerechnet ist bis dahin nichts;
  die Auswahl bleibt, das nächste Escape geht die Stufe zurück.
* **Die Maßlinien weichen dem Griff — soweit sie über ihn hinausreichen.**
  Sie laufen alle in der Mitte des Merkmals zusammen, und dort sitzen Pfeile
  und Ringe; die Maßtinte lässt das Stück in der Griffspanne weg
  (`_Dimensions.clearing`, aus `gizmo_reach()` wie die Felder — die Aussparung
  ist seit der Tinte im Renderer Kosmetik, die Striche nehmen keinen Klick
  an). Eine Linie, von der außerhalb weniger als ein Pfeil bliebe, kommt
  dagegen ganz, mit beiden Pfeilen: Nach dem Zug zum Langloch greift der
  Griff über Knöpfe und Umriss hinaus, und ein Maß ohne Linie sagt nicht,
  wohin es geht (Robert, 21.09.2026: „manche maßlinien fehlen aber"). Der
  Umriss des Lochs bleibt darunter sichtbar; gegen Griff und Knöpfe trägt
  die Tinte `draw_order` unter null, damit die Lage der Platte im Bauraum
  nicht entscheidet, was oben liegt. Anlass: „das verschieben ist auch schwer
  durch die maßlinien zu treffen/sehen".

* **Die erste Eingabe bindet die Auswahl.** Vorher bleibt die passive
  Maßanzeige abwählbar; danach erhalten Außenklick und andere Auswahltasten
  den Entwurf. `Viewport.user_selection_allowed` liegt vor der Mutation in
  Bild und Kantenwahl, `_ObjectTreeView` vor Qts Maus-/Tastaturauswahl.
  Kamera und Scrollen bleiben frei. Fremde Befehle werden nicht vorgemerkt:
  erst Übernehmen oder Abbrechen gibt sie wieder frei. Escape und das
  gemeinsame Abbrechen verwerfen den Entwurf; eine echte Dokument- oder
  Ergebnisänderung entwertet seinen Bezug. **Abbrechen hebt dazu die Auswahl
  auf** (Entscheidung Robert, 24.09.2026: „abbrechen = deselektieren";
  `QuietHost.cancel` → `MainWindow._measures_cancelled`, derselbe Weg wie ein
  Klick ins Leere). Vorher blieb das Merkmal gewählt, ohne Maße und Knöpfe
  im Bild, und rechts stand die Handlung des verworfenen Entwurfs scharf.
  **Escape tut dasselbe** (Entscheidung Robert, 25.09.2026: „wie abbrechen
  zurücknehmen und abwählen"): im Maßfeld über `PlacementFlow.step_back`,
  sonst über `MainWindow._escape`. Bis dahin verließ es nur die Maße, und
  rechts blieb der verworfene Entwurf scharf. Die eigene synchrone
  Dokumentmeldung beim Commit wartet bis zum booleschen Erfolg des Callbacks.

* **Ein Klick in das Zwillingsfeld rechts gibt die Maße im Bild nicht auf.**
  Stehen die Maße von *Bohrung ändern* im Bild, und der Kunde klickt rechts in
  ein Feld von *Zum Langloch ziehen* (oder umgekehrt), wechselt die Maßgruppe
  auf den Zwilling, statt zu verschwinden (`MainWindow._hand_the_measures_over`,
  aus `_on_handling_armed`), und der Fokus geht in dasselbe Feld der neuen
  Gruppe (`_focus_measure_field`, gefunden über die Feldkennung
  `panels.FIELD_PROPERTY`). Nur solange nichts begonnen ist und die Handlung
  demselben Merkmal gilt; ein begonnener Entwurf bleibt, wo er ist. Anlass:
  Robert, 24.09.2026, „vor allem mit dem merkmalpanel nebenan". **Und der
  Zwilling rechts zeigt nur, was er allein hat** (`FeaturePanel._in_the_view`):
  Breite, Durchmesser, X, Y, Z und Materialtoleranz stehen schon im Bild — an
  einem Langloch stand darunter *Bohrung ändern* mit demselben Wert als
  Durchmesser, zwei Felder für eine Zahl, von denen nur eines das Bild führt.

* **Im Bild steht jede Zahl einmal** (RM-516, Durchsicht der Oberfläche
  0.5.2, Befund B8). Eine gewählte Bohrung zeigte ihren Durchmesser in Marke
  („Bohrung 1 · Ø5,20 mm · eingepasst"), Maßzahl neben den Langlochknöpfen,
  Karte („Aktuell: Ø5,20 mm"), Feld und Merkmalfenster, ihre Lage über sieben
  Zahlen (zwei Kantenmaße, „Mitte 1", „Mitte 2", „Bohrung 2 · Abstand", X, Y,
  Z), und die Bezüge hießen „Außenkante 4" — beide Maßlinien liefen im Bild
  zur selben Seite, und dann blieb die Nummer. Am echten Fenster
  (Lochplatte, 1600 × 1000) standen 20 Zahlen im Bild — 13 Maße, 6 Nummern
  in Namen und die Zahl gleichartiger Bohrungen —, danach 5: Durchmesser,
  Tiefe, zwei Kantenmaße und diese Zahl. Entschieden:
  Die Bezüge heißen nach der Weltachse, wie die Flächen im Objektbaum
  („Linke Seite", „Vorderseite"), und bleiben beim Drehen stehen. Die Mitte
  eines Nachbarn fällt nur am **sitzenden** Merkmal weg; beim Setzen einer
  neuen Bohrung ist sie die Zielhilfe für den Abstand zum Nachbarloch und
  steht weiter von selbst. Das Herkunftswort („eingepasst") bleibt über dem
  Feld, weil es warnt; die Zahl steht nur im Feld. Im Merkmalfenster nennt
  der Kopf einer Bohrung nur ihren Namen — der Satz darunter („Bohrungsmaß:
  5,20 mm (eingepasst). Passt vermutlich zu M5") sagte dasselbe Maß ein
  zweites Mal. Nicht geändert: Die Felder stehen weiter neben dem Körper und
  nicht auf ihm (Entscheidung Robert, 21. und 22.09.2026).

### Wo etwas schon sitzt, zielt der Zeiger nicht

* **Am Merkmal zielt die Platzierung nie.** Bis zum Abend des 11.09.2026 war
  ein Klick neben dem Griff die Ansage, „woanders hinzuwollen": Die
  Platzierung löste sich vom Merkmal, die Bohrungsvorschau klebte am Zeiger
  wie beim Setzen einer neuen, und der Weg heraus war nicht zu finden
  (Robert: „auf einmal war ich im modus eine neue Bohrung zu setzen … er
  sollte an der stelle ja nichtmal kommen"). Wohin ein vorhandenes Loch soll,
  sagen der Griff und die Felder rechts; ein Klick ins Bild gehört der Auswahl
  (`PlacementFlow.pointer` gibt ihn im Zustand „sitzt am Merkmal" zurück).

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

**Auch wenn keine Trägerfläche gefunden wird** (`_no_seat_at_feature`): Die
gebundene Maßgruppe misst dann ohne Fläche weiter, statt in das Zielen
zurückzufallen — sonst setzte die nächste Mausbewegung das vorhandene Loch an
den Zeiger. Und wo eine gefunden wird, liegt die Mündung auch hinter einer
Fase auf ihr (`placement.seat_of`, `mouth_reach`): Eine gefaste Mündung endet
nicht in der Ebene ihrer Fläche, und ohne diese Suche hatte das Merkmal keine
Maße im Bild.

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
