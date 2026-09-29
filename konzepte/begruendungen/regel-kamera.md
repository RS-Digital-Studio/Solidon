# Begründungen zu `.claude/rules/kamera.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

## Regeln für Kamera und Navigation

Wie sich die Ansicht bewegt, und wer sie bewegen darf: die eigene Steuerung
statt eines fremden Interaktionsstils, der zweite Treiber der 3D-Maus, der
Drehpunkt und die Art des Drehens. **Ausgegliedert aus `ansicht.md` am
18.09.2026** — die übrigen Ansichtsregeln gelten weiter und laden zusätzlich.

## Die Navigation ist eigener Code am Vertrag, kein fremder Interaktionsstil

`app/ui/render/navigator.py` liest die Zeigerereignisse des Renderers
(`add_pointer_listener`) und stellt die Kamera über den Vertrag
(`camera_pose`, `set_camera_pose`, `dolly`). Der Renderer bringt keinen
eigenen Kamerastil mit (unter VTK war der Trackball abgeschaltet), und damit
ist auch die Falle verschwunden, die
diesen Abschnitt bis zum 05.09.2026 füllte: PyVista führte neben VTK einen
eigenen Stil (`_style_class`) und setzte ihn bei jeder Gelegenheit über
`update_style()` wieder durch — auch beim Doppelklick, den es immer anmeldete.
Die gestufte Auswahl (§18.5) heißt zwei Klicks auf dieselbe Stelle, und nach
dem zweiten waren Auswahl, Kontextmenü und Schema weg (Vorfall:
ROADMAP-ARCHIV.md, 04.09.2026). Der Navigator kennt keinen zweiten Halter
seines Zustands.

## Die Ansicht hat eine eigene Steuerung

Robert: „noch eine änderung zur steuerung weil sie mir nicht gefällt, aber als
eigene und standart wählen". Vier Schemata bildeten Fremdprogramme nach —
`slicer` (Cura), `orbit` (Bambu Studio, Orca, PrusaSlicer), `cad` und
`blender` —, und keines davon war Solidons eigenes. Das
fünfte heißt `solidon` und ist die Vorgabe: links verschiebt, rechts dreht um
den Mittelpunkt der Ansicht, das gedrückte Rad kippt nach oben und unten,
Scrollen zoomt. Umschalt ändert hier nichts — anders als in den vieren, die
ein Vorbild haben.

* **Links schiebt und wählt trotzdem.** `_left_up` fragt `is_click` und trennt
  Klick von Zug an der Zugschwelle des Systems; die Auswahl hängt also nicht
  daran, was `_begin` an der Kamera gestartet hat. Wer eine sechste Steuerung
  baut, darf `select` und `pan` deshalb auf dieselbe Taste legen — was sich
  ausschließt, ist `pan` und ein *gezogenes* Werkzeug, nicht `pan` und ein
  Klick. Auf dem **gewählten** Körper führt links weiter das Teil (Robert,
  03.09.2026, gegen den Vorschlag, das dem Griff allein zu lassen).
* **Und dieser Zug rechnet auf einer Ebene, er pickt nicht** (13.09.2026).
  Gepickt wird zweimal: beim Drücken (liegt dort der gewählte Körper?) und
  beim Zugbeginn (wo wurde gegriffen?). Jede Bewegung danach schneidet den
  Sichtstrahl mit der waagerechten Ebene durch den gegriffenen Punkt
  (`_plane_point` über `render.gizmo.ray_plane_hit`). Vorher stand dort ein
  `_world_at` je Mausbewegung — gemessen am echten Fenster (`drilled_v6.p3d`,
  Bild 1030 mal 710, ein Zug über 40 Ereignisse, drei Läufe): 34 Picks je Zug
  und 3,27 ms je Ereignis im Median, danach zwei Picks und 0,16 ms. **Der Pick
  beantwortete die Frage auch falsch:** Er gab den Punkt auf der getroffenen
  *Oberfläche* zurück, und davon wurden x und y genommen — über dem leeren
  Hintergrund traf er nichts (der Körper blieb stehen und sprang weiter,
  sobald der Zeiger wieder über etwas stand), und beim Wechsel von einer hohen
  auf eine tiefe Fläche versprang er um den Unterschied der Perspektive.
* **Das Kippen ist eine eigene Rechnung, keine Bewegung des Renderers.**
  (Unter VTK gab es „nur nach oben und unten" im Trackball nicht, und
  `Rotate` dafür zu überschreiben hieße, am Zustand des Interactors zu
  drehen.) Gerechnet wird
  mit `spacemouse.camera_step` — der Navigator meldet nur die senkrechte
  Strecke seit dem letzten Ereignis (`_tilt_at`), das Rechnen bleibt in der
  reinen Funktion und damit ohne Fenster prüfbar.
* **Fliegen ist nicht Zoomen, und der Unterschied ist der Blickpunkt.**
  `camera_step(..., fly=True)` schiebt Standort **und** Blickpunkt entlang der
  Blickrichtung; ohne den Schalter ändert die Achse `y` nur den Abstand. Der
  Zoom fährt bis vor das Teil, der Flug hindurch. Das Vorzeichen folgt dem
  Zoom, den der Zweig ersetzt: eine Achse, die je nach Schalter in die andere
  Richtung zieht, wäre die Falle für den Nächsten, der `fly` an ein Gerät hängt.
* **Die Tastatur wirkt nur in `solidon`.** Die vier anderen bilden
  Fremdprogramme nach; dort wäre WASD eine Bewegung, die es im Vorbild nicht
  gibt — in Blender ist sie sogar belegt.
* **Der Anschlag schaltet ein, er bewegt nicht.** Zuerst war ein Anschlag ein
  Schritt, und die Wiederholung sollte Qt liefern — das schien der Takt zu
  sein, den das System ohnehin hat. Nachgerechnet ist es keiner: rund eine
  halbe Sekunde Stillstand (die Wiederholverzögerung, die niemand hier
  einstellt), danach 31 Schritte je Sekunde und damit das Viereinhalbfache der
  Entfernung je Sekunde — der Bauraum in einer Fünftelsekunde. Gefahren wird
  deshalb in einem eigenen Takt (`FLIGHT_TICK_MS`, 16 ms wie bei der Kappe),
  solange die Taste liegt, mit der wirklich vergangenen Zeit. `FLIGHT_RATE`
  sagt die Geschwindigkeit in einer Einheit, die man lesen kann: Entfernungen
  je Sekunde, derzeit eine. **Wer daran baut, denkt an drei Dinge:** Die
  Wiederholung des Systems schickt auch *Loslass*-Ereignisse (ohne
  `isAutoRepeat` stottert der Flug), ein Fokusverlust bringt kein Loslassen
  mehr (ohne `focusOutEvent` fliegt die Ansicht weiter, während der Kunde
  tippt), und zwei Tasten auf derselben Achse heben sich auf.
* **`setFocusPolicy(StrongFocus)` wirkt in allen fünf.** Ohne ihn kommt kein
  Tastendruck an, und er ist die einzige Änderung dieses Umbaus außerhalb des
  neuen Schemas: Ein Klick in die Ansicht nimmt seither den Fokus aus einem
  Eingabefeld. Wer einen Test schreibt, der nach einem Klick in die Ansicht
  noch tippt, tippt jetzt in die Ansicht. **Für die Bedienung ist das
  unschädlich, und zwar gemessen** am echten Fenster — offscreen vergibt Qt
  gar keinen Fokus; ein Feld holt sich den Fokus beim nächsten Klick zurück,
  und die Eingabetaste wirkt
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

## Der Drehpunkt ist, was in der Bildmitte steht

Robert: „beim rotieren der ansicht wollen wir uns um den mittelpunkt des
viewports drehen." Der Bauplan sagt es seit je (§2.9, „dreht um den
Mittelpunkt der Ansicht“); umgesetzt war eine Näherung.

`_aim_rotation` setzte den Fokus auf die Projektion der **Mitte aller Körper**
auf den Sichtstrahl. Seitlich war der Drehpunkt damit schon die Bildmitte —
jeder Punkt des Sichtstrahls ist es —, in der **Tiefe** aber die Mitte des
ganzen Teils. Wer auf ein Detail zoomt, drehte um einen Punkt eine halbe
Bauhöhe dahinter, und das Detail schwenkte aus dem Bild.

Gefragt wird deshalb zuerst `centre_hit()`: derselbe Oberflächen-Pick wie bei
jedem Klick (`_world_at`), in der Mitte des Renderers. Erst wenn dort nichts
steht, gilt weiter `rotation_centre()`. Vier Dinge daran sind tragend:

* **Die Kulisse kann den Drehpunkt nicht an sich ziehen**, und zwar ohne eine
  eigene Regel: `_world_at` fragt den Pick nur unter den Körperaktoren
  (`among`).
  Das ist dieselbe Zusage, die 2026-08 als „gedreht wurde um die Kulisse"
  einmal fehlte — sie hängt jetzt an einer Zeile, die beim Aufräumen
  überflüssig aussieht.
* **Der Rückfall ist kein Sonderfall, sondern der Normalfall am Rand.** Über
  dem Hintergrund findet der Picker nichts, und beim senkrechten Blick in eine
  Durchgangsbohrung ebenfalls nicht (siehe „Ein Klick ist eine Blickrichtung").
  Beides endet bei der Mitte der Körper, nicht bei „kein Drehpunkt".
* **Das gedrückte Rad bekommt ihn auch.** `camera_step` kippt um den
  Blickpunkt, genau wie `turntable_camera` dreht; der `tilt`-Zweig des
  Navigators ruft `on_rotate_start` deshalb ebenso. Ein Drehpunkt, der
  je nach Taste ein anderer ist, lässt sich niemandem erklären.
* **Und das Bild ändert sich beim Setzen um nichts.** Der neue Fokus liegt auf
  dem Sichtstrahl, Stellung und Blickrichtung bleiben — die Bedingung von
  Robert (23.08.2026, „kamera bei aktueller position dann immer lassen") gilt
  unverändert.

**Geprüft wird das nicht in der Suite**, denn offscreen gibt es keinen Picker:
Die Tests in `tests/test_viewport_decisions.py` setzen an die Stelle des
Renderers eine Attrappe (`RecordingRenderer`) und prüfen damit die Regel,
nicht die Kette bis in den Renderer.
`.claude/.state/drehpunkt-2026-09-04/` fährt sie am echten Fenster. Gemessen,
`plate_holes.stl`, Blick schräg auf die Platte, Zug nach rechts:

| | Punkt in der Bildmitte |
|---|---|
| über `centre_hit` | **0,00 mm** gewandert |
| nur über `rotation_centre` | 3,14 mm |

**Eine Falle beim Prüfen davon**, sofort zugeschnappt: Eine Gegenprobe, die
knapp am Teil vorbeizielt, misst die Toleranz des Picks und nicht den
Hintergrund — sie bekam einen Treffer fünf Millimeter neben der Platte. Wer
„da ist nichts" prüfen will, blickt in den Himmel.

## Gedreht wird als Drehteller, nicht als Trackball

Robert: „das rotieren neigt immer noch statt den winkel zur mitte zu lassen."
Ein Trackball (bis zum 05.09.2026 VTKs `vtkInteractorStyleTrackballCamera`)
dreht um das **Oben der Kamera** und führt es dabei mit; hinterher wird es nur
wieder senkrecht zur Blickrichtung gestellt, nicht auf. Über eine Geste
summiert sich daraus eine Schräglage — nachgerechnet an zwölf diagonalen
Zügen: **62,7 Grad** gegen **0,0** beim Drehteller.

`turntable_camera` dreht waagerecht immer um die Welt-Hochachse und senkrecht
um die Bildwaagerechte; das Oben folgt daraus, statt mitgeschleift zu werden.
Die Hebung wird an `POLE_LIMIT_DEGREES` **begrenzt und nicht abgeschnitten** —
wer fast senkrecht darüber steht, dreht weiter waagerecht und kommt jederzeit
zurück; aus einer Draufsicht des Menüs führt der Weg ebenso heraus. Die
Empfindlichkeit ist die des alten VTK-Trackballs geblieben (20 Grad je
Fensterhälfte mal seinem `MotionFactor` von 10, `TURN_MOTION_FACTOR`), damit
der Umbau nicht nebenbei die gewohnte
Geschwindigkeit verstellte. Es gilt für alle fünf Schemata: Cura, Bambu Studio
und Blender bleiben alle aufrecht, und ein Nachbau, der neigt, wo sein Vorbild
es nicht tut, ist keiner.

**Der erste Anlauf war eine überschriebene `Rotate`-Methode am
VTK-Interaktionsstil, und er war wirkungslos:** Die Rechnung stimmte, drei
Einheitstests waren grün, und am laufenden Fenster blieben **35,8 Grad**
Schräglage — weil VTKs `OnMouseMove` als C++ die Methode **seiner eigenen**
Klasse rief und nie die einer Python-Unterklasse.

Seit dem 05.09.2026 gibt es diesen Stil nicht mehr: Der `Navigator` liest die
Zeigerereignisse des Renderers und stellt die Kamera selbst
(`turntable_camera`, `set_camera_pose`) — es gibt nichts Fremdes mehr, dem
man sich vorhängen müsste. Die Lehre bleibt, weil sie über VTK hinausgeht:
**Was ein fremdes Programm selbst führt, lässt sich nicht von außen
überschreiben** — man hängt sich davor, oder man führt es selbst.

**Und die Lehre über die Prüfung, die teurer war als der Fehler:**
Einheitstests über eine reine Funktion sagen nichts darüber, ob jemand sie
ruft. Drei grüne Tests und ein unverändertes Fenster sind kein Widerspruch —
sie prüfen verschiedene Dinge. Gefangen hat es `.claude/.state/drehpunkt-2026-09-04/`,
das die Kette am echten Fenster fährt.

## Kameravorgaben und Einpassen

**Die Anwendung setzt ihre Startkamera selbst.** Ohne `view_from("iso")` beim
Aufbau erbt sie die Startstellung des Renderers, und die eigene Vorgabe aus
`VIEW_DIRECTIONS` sieht nur, wer „Isometrisch" im Menü wählt — ein Sprung aus
einer Ansicht in eine andere, die man zu sehen glaubte.

**Eine Kameravorgabe dreht um den Blickpunkt, sie passt nicht ein**
(Entscheidung Robert, 07.09.2026, wie in Assist). Strg+0 bis Strg+6 und die
ViewBar lassen Fokus und Abstand stehen und wechseln allein die Richtung
(`_turn_camera_to`, derselbe Kern wie das Einrasten einer frei gedrehten
Kamera in `_settle_sketch_view`); der Iso-Vektor wird dabei genormt, sonst
wüchse der Abstand mit jedem Klick. Bis dahin stellte `view_from` die Kamera
auf den Ursprung und rahmte die Szene neu — wer in eine Bohrung gezoomt hatte
und „Oben" drückte, verlor den Zoom. Einpassen ist die Sache von Pos1, und
die erste Rahmung eines geöffneten Projekts die von `_fit_once_for`.

Entscheidung Robert, 03.09.2026. Wer ein Teil aus einer Baugruppe anklickt und
Pos1 drückt, will dieses Teil formatfüllend sehen — nicht wieder
die ganze Baugruppe. **Ohne Auswahl bleibt es beim Alten**; das war Teil der
Frage, damit nichts wegfällt, was heute funktioniert.

Der Eintrag heißt deshalb **„Einpassen"** und nicht mehr „Alles
einpassen": Ein Name, der in einem der beiden Zustände lügt, ist
schlechter als ein kürzerer, der in beiden stimmt. Was er tut, steht im
Tooltip.

Drei Dinge hängen daran, und jedes hat seinen Grund:

* **Der Versatz gehört dazu** (`_selected_bounds` über
  `_view_offset`). Ein auseinandergezogener Körper oder einer auf der
  zweiten Platte wird anderswo gezeichnet, als er in der Szene liegt; ohne ihn
  rahmte die Kamera die leere Stelle, an der er ohne Versatz stünde.
* **Was nicht im Bild ist, wird nicht gerahmt** (§18.8, §25). Ein
  ausgeblendeter oder auf einer fremden Platte liegender Ausgewählter
  fällt auf die Szene zurück — auf etwas einzupassen, das man
  nicht sieht, wäre die schlechteste der drei Antworten.
* **`_fitted_bounds` bleibt die Szene.** Es beantwortet „ist die Szene der
  Ansicht entwachsen?", und das ist eine Aussage über die Szene, nicht
  über die Kamera. Stünden dort die Grenzen des Ausgewählten,
  hielte `outgrown` jede Auswahl eines kleinen Teils für eine gewachsene
  Szene und rahmte beim nächsten Aufbau von selbst wieder alles.

**Und der automatische Weg folgt der Auswahl nicht**
(`_fit_once_for` ruft `reset_camera(follow_selection=False)`). Dort wird
gerahmt, *weil* die Szene entwachsen ist — ein neuer 400er Körper
neben einem Zwei-Millimeter-Teil, die Kamera in seinem Inneren. Ein Rahmen um
den kleinen Ausgewählten beantwortete genau das nicht.

**Eine frische Teilung rahmt einmal neu** (RM-269, KUNDE-11). Die Teile stehen
auseinandergezogen da und überdecken den alten Rahmen noch; `outgrown` sah
darin nichts, und am Organizer ×2,3 standen danach 29 % aller Teile im Bild.
`Viewport.frame_next_scene` lässt den nächsten Aufbau einmal auf alle Körper
rahmen (ohne Auswahl, mit Versatz); `MainWindow._reveal_split_result` ruft es
vor dem Auseinanderziehen. Danach gilt wieder, dass die Kamera bleibt.

Der Test dazu (heute `test_fitting_frames_the_bodies_with_air`) war in seiner ersten
Fassung **grün, als ich die Änderung wieder ausbaute**: Er maß
`_selected_bounds` und `_fit_once_for`, also die Vorarbeit, und nicht die
Kamera. Offscreen gibt es keinen Renderer, und `reset_camera` steigt an seiner
Wache aus, bevor irgendetwas gerahmt wird. Erst eine Attrappe am Vertrag
(`RecordingRenderer.reset_bounds` in `tests/render_fakes.py`) hat den
Unterschied gemessen.

## Wer die Kamera bewegt, meldet zuerst und zeichnet danach einmal

Bis zum 21.09.2026 war es umgekehrt: Der Navigator zeichnete die Radraste,
dann hörte die Maßtinte `cameraMoved` und zeichnete noch einmal; am Zugende
kamen Einrasten, Schatten und Tinte auf drei Bilder (21,7 ms je Raste
zusätzlich). Die Regel löst das an einer Stelle: Die Hörer von `cameraMoved`
legen ihre Punkte neu und zeichnen **nicht** selbst (`PlacementFlow._camera_moved`
ruft `redraw(draw=False)`), und die Ansicht zeichnet nach der Meldung das eine
Bild. `set_camera_pose(…, draw=False)`, `_redraw_shadows(draw=False)` und
`_settle_sketch_view(draw=False)` geben das Bild dem Aufrufer;
`test_surface_placement_ui.py::test_a_camera_move_with_measures_in_the_view_draws_exactly_one_frame`
hält für Radraste, Zugende, 3D-Maus und Ansichtswahl fest, dass es genau
eines bleibt.

## Die Kamera hat einen zweiten Treiber

* **Die Abbildung ist eine reine Funktion.** `camera_step` bekommt sechs
  Achsen, eine Stellung, eine Zeitspanne und drei Einstellungen und gibt eine
  Stellung zurück. Kein Qt, kein Renderer, kein HID darin — jeder Achsenfehler
  (Vorzeichen, Bezugssystem) wird dort behoben und in
  `tests/test_spacemouse.py` mit einem Test je Achse festgehalten. Wer die
  Wirkung einer Achse ändert, macht genau einen Test rot. Objektmodus ist die
  Vorgabe (die Kappe ist das Teil, alle sechs Achsen — Robert, 02.09.2026),
  „Richtung umkehren" ist der Kameramodus.
* **Die Kappe ist ein Kraftsensor, und Achsen sprechen über.** Wer dreht,
  drückt auch; wer schiebt, kippt ein wenig. Die Totzone allein fängt das
  nicht — sie misst gegen den Vollausschlag, das Übersprechen wächst mit der
  Kraft. Am Korpus gemessen (07.09.2026): Beim Drehen um die Hochachse lag der
  Zoom im Median bei einem Viertel der Drehung und in 71 von 71 Berichten über
  der Totzone; das Teil kam beim Drehen näher, ohne dass jemand gezogen hätte.
  `quiet_crosstalk` dämpft deshalb jede Nebenachse nach ihrem Anteil an der
  stärksten: null unter `CROSSTALK_SILENT`, voll ab `CROSSTALK_MEANT`,
  dazwischen eine glatte Rampe; die stärkste bleibt immer, eine aktive
  Bewegung bleibt also aktiv. **Eine Rampe, keine Klippe** (16.09.2026): Der
  harte Schnitt bei einem Viertel schaltete die Zoomachse am Korpus beim
  Ziehen zur Person dreimal in vier Sekunden an und aus, beim Kippen der
  Vorderkante sechsmal — der Zoom hakte. Die Anteile der Nebenachsen liegen
  breit um das Viertel, jede Schwelle dort schaltet ständig; das Viertel ist
  jetzt die Mitte des Bandes. **Der Preis steht daneben:** Eine bewusst
  kleine Nebenbewegung unter `CROSSTALK_SILENT` der Hauptbewegung geht
  verloren, beim Kippen der Vorderkante liest das Gerät einen guten Teil als
  Zug, und beim Drehen bleiben rund zwei Drittel des Zoom-Lecks — das ist der
  Sensor. Band und Kennlinie sind an der Aufzeichnung gewählt und **am Gerät
  noch nicht bestätigt** — wer sie ändert, misst am Korpus und nicht am
  Gefühl (die Korpus-Tests zum Übersprechen in `test_spacemouse.py`).
* **Der Viewport bekommt eine Stellung, keine Deltas.** `Viewport.set_camera_pose`
  setzt Standort, Blickpunkt und Oben und zeichnet einmal. Es ist die einzige
  Stelle, an der die 3D-Maus den Viewport anfasst; `sketch_active` sagt ihr,
  dass im Zeichenmodus nur geschoben und gezoomt wird.
* **Direkt über HID, neben dem Herstellertreiber.** `hidapi` (BSD-3 aus der
  Dreifachlizenz gewählt) öffnet die Schnittstelle *Multi-axis Controller*;
  3DxWare darf laufen und liest dieselben Berichte mit — so wie PrusaSlicer und
  Assist es tun. Raw Input war der erste Anlauf und blieb leer: 3DxWare reicht
  Rohdaten nur an Programme durch, die es kennt
  (`<Transport>RawInput</Transport>` in seiner Programmliste). Nicht
  blockierend, im Hauptthread, ein Takt für Lesen und Fahren; die Vorzeichen
  der Achsen stammen aus einer aufgezeichneten Lesung im Korpus
  (`tests/data/spacemouse/`), nicht aus einer Annahme.
* **Auf dem Mac geht es durch den Treiber, nicht neben ihm.** Dort hält
  3DxWare das Gerät exklusiv, und `hidapi` bekommt keinen Bericht (der erste
  Mac-Bericht eines Kunden, 05.09.2026). `DriverReader` lädt das
  `3DconnexionClient`-Framework des Kunden zur Laufzeit — mitgeliefert wird
  nichts, Regel 22 bleibt unberührt — und schreibt dessen Zustandsmeldungen
  in dieselben Berichte um, die das Gerät roh liefert; `decode_report` und
  alles dahinter kennen den Unterschied nicht. Angemeldet wird mit dem
  Platzhalter wie in FreeCAD und Blender, gelesen nur, was an Solidons
  Client-Kennung gerichtet ist. `default_reader` entscheidet je Rechner:
  Mac mit Treiber → Treiber (HID als Rückfall, wenn er angehalten ist),
  sonst HID. Die Plattform ist dort ein Parameter, damit der Mac-Zweig auf
  jeder Maschine prüfbar bleibt. **Am Gerät gemessen ist nur Windows**; der
  Mac-Weg wartet auf die Rückmeldung des Kunden.

## Was die Suite prüft und was nur das echte Fenster

**Was die Suite prüft, und was nur ein Werkzeug von Hand prüft.** Seit dem
05.09.2026 führt der Navigator die Kamera über den Vertrag, und
`tests/test_navigator.py` fährt die Tabelle gegen ein Renderer-Doppel — welches
Schema auf welche Taste was tut, und wo die Kamera danach steht. Was kein Test
prüft, ist die Kette davor: Qt-Ereignis → Widget des Renderers →
`PointerEvent`. Offscreen bleibt `Viewport.renderer` auf `None`, die Suite
kann das Fenster also gar nicht erst nach der Bewegung fragen.
`.claude/.state/steuerung-2026-09-03/` schloss die Lücke, solange es VTK gab (seit
der Ablösung durch pygfx lief er nicht mehr; am 29.09.2026 mit dem Drehpunkt-Prüfstand
entfernt, Stand in der Git-Historie): ein echtes Fenster,
echte Ereignisse, die Kamerastellung vorher und nachher. Zu fahren nach jeder
Änderung an `_NAVIGATION`, am Navigator oder an `camera_step` — **und vorher
umzubauen**: Der Prüfstand schickt noch VTK-Ereignisse an einen Interactor,
den es nicht mehr gibt (Registerpunkt in `ROADMAP.md`). Die
README daneben nennt die
drei Fallen, die dabei zuschnappen — Millimeter sagen nichts (jede Bewegung
skaliert mit der Entfernung), Bildpunkte hier gar nichts (das Renderfenster
bleibt 160×160), und `session.apply` blockiert den Hauptthread.
