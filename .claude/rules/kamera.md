---
description: "Kamera und Navigation — der zweite Treiber neben der Maus, die eigene Steuerung der Ansicht, der Drehpunkt in der Bildmitte und das Drehen als Drehteller"
paths:
  - "app/ui/spacemouse.py"
  - "app/ui/viewport.py"
  - "app/ui/render/navigator.py"
  - "app/ui/render/api.py"
  - "app/ui/settings.py"
  - "app/ui/settings_dialog.py"
---

# Regeln für Kamera und Navigation

Wie sich die Ansicht bewegt, und wer sie bewegen darf: die eigene Steuerung
statt eines fremden Interaktionsstils, der zweite Treiber der 3D-Maus, der
Drehpunkt und die Art des Drehens. **Ausgegliedert aus `ansicht.md` am
18.09.2026** — die übrigen Ansichtsregeln gelten weiter und laden zusätzlich.

## Die Kamera hat einen zweiten Treiber (02.09.2026)

Die 3D-Maus (`app/ui/spacemouse.py`, Konzept `konzept-3d-maus-2026-08`) fährt
dieselbe Kamera wie die Maus — kein eigenes Navigationsschema, kein Modus,
keine Operation. (Bis zum 03.09.2026 stand hier „kein fünftes“; die Zahl ist
seither vergeben, die Zusage nicht.) Drei Regeln:

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

## Die Ansicht hat eine eigene Steuerung (03.09.2026)

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

**Was die Suite prüft, und was nur ein Werkzeug von Hand prüft.** Seit dem
05.09.2026 führt der Navigator die Kamera über den Vertrag, und
`tests/test_navigator.py` fährt die Tabelle gegen ein Renderer-Doppel — welches
Schema auf welche Taste was tut, und wo die Kamera danach steht. Was kein Test
prüft, ist die Kette davor: Qt-Ereignis → Widget des Renderers →
`PointerEvent`. Offscreen bleibt `Viewport.renderer` auf `None`, die Suite
kann das Fenster also gar nicht erst nach der Bewegung fragen.
`.claude/.state/steuerung-2026-09-03/` schließt die Lücke: ein echtes Fenster,
echte Ereignisse, die Kamerastellung vorher und nachher. Zu fahren nach jeder
Änderung an `_NAVIGATION`, am Navigator oder an `camera_step` — **und vorher
umzubauen**: Der Prüfstand schickt noch VTK-Ereignisse an einen Interactor,
den es nicht mehr gibt (Registerpunkt in `ROADMAP.md`). Die
README daneben nennt die
drei Fallen, die dabei zuschnappen — Millimeter sagen nichts (jede Bewegung
skaliert mit der Entfernung), Bildpunkte hier gar nichts (das Renderfenster
bleibt 160×160), und `session.apply` blockiert den Hauptthread.

Vier Wächter in `tests/test_viewport_decisions.py` und
`tests/test_spacemouse.py`, alle ohne Fenster: Jedes Schema belegt alle sechs
Kombinationen aus Taste und Umschalt (`navigation_action` liest ohne Rückfall
und würfe sonst beim Drücken — ein Rückfall wäre die schlechtere Antwort, weil
er die Lücke zur stillen Vorgabe macht); jedes trägt einen Namen im
Einstellungsdialog (sonst wäre es gebaut, geprüft und unerreichbar); die sechs
Flugtasten decken drei Achsen in beide Richtungen ohne Dopplung; und der Flug
nimmt den Blickpunkt mit, wo der Zoom ihn stehen lässt.

## Der Drehpunkt ist, was in der Bildmitte steht (04.09.2026)

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

## Gedreht wird als Drehteller, nicht als Trackball (04.09.2026)

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

## Die Navigation ist eigener Code am Vertrag, kein fremder Interaktionsstil (05.09.2026)

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

Was davon als Regel bleibt:

* **Wer ein Ereignis vor der Navigation braucht, bekommt es vor ihr.**
  `Viewport._on_pointer` reicht jedes Ereignis erst an die Griffe, dann an eine
  laufende Platzierung, dann an den Zeiger, zuletzt an den Navigator — eine
  Vorfahrt an einer Stelle statt dreier Beobachter am Interactor. (Bis zum
  10.09.2026 stand der Zeiger vorn; die heutige Reihenfolge und ihr Anlass
  stehen unter „Ein Griff steht vor allem, was über der Ansicht liegt".)
* **Ein Klick ist ein Klick, auch mit Zittern**, und ein Klick, der nichts
  wählt, lässt die Taste der Kamera (`tests/test_navigator.py`,
  `test_a_wobbly_click_stays_a_click` und
  `test_where_nothing_is_chosen_the_camera_keeps_the_button`).
* **Die Tabelle `_NAVIGATION` ist ohne Fenster prüfbar.** `tests/test_navigator.py`
  fährt sie gegen ein Renderer-Doppel — welches Schema auf welche Taste was
  tut, und wo die Kamera danach steht.
