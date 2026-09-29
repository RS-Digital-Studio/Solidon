---
description: "Kamera und Navigation — die eigene Steuerung am Vertrag, der Drehpunkt in der Bildmitte, Drehen als Drehteller, Kameravorgaben und Einpassen, wer nach einer Kamerabewegung zeichnet, und die 3D-Maus als zweiter Treiber"
paths:
  - "app/ui/spacemouse.py"
  - "app/ui/viewport.py"
  - "app/ui/render/navigator.py"
  - "app/ui/render/api.py"
  - "app/ui/settings.py"
  - "app/ui/settings_dialog.py"
---

# Regeln für Kamera und Navigation

Wie sich die Ansicht bewegt und wer sie bewegen darf. `ansicht.md` lädt am
Viewport mit. Anlässe und Messwerte: `konzepte/begruendungen/regel-kamera.md`.

## Die Navigation ist eigener Code am Vertrag, kein fremder Interaktionsstil

`app/ui/render/navigator.py` liest die Zeigerereignisse des Renderers
(`add_pointer_listener`) und stellt die Kamera über den Vertrag (`camera_pose`,
`set_camera_pose`, `dolly`); der Renderer bringt keinen Kamerastil mit, und der
Navigator kennt keinen zweiten Halter seines Zustands. **Was ein fremdes
Programm selbst führt, lässt sich nicht von außen überschreiben** — man hängt
sich davor, oder man führt es selbst.

* **Wer ein Ereignis vor der Navigation braucht, bekommt es vor ihr** — über die
  eine Vorfahrt in `Viewport._dispatch_pointer`, nie über einen zweiten
  Beobachter. Reihenfolge und Grund: `griffe.md`.
* **Die Rückrufe des Navigators gehen über `weakref`** (`on_cursor`,
  `on_context`, `on_pick` in `_weak_callbacks` als `NavigatorCallbacks`, dazu
  der Zeiger-Zuhörer am Renderer, `_listen_to`): Stark schließen sie die
  Schleife Navigator → Viewport → Renderer → Zuhörer → Viewport, den Absturz
  ohne Zeile am Ende eines Laufs. Allgemein: `wartezeit.md`, „Ein Rückruf an ein
  eigenes Kind hält schwach“.
* **Ein Klick ist ein Klick, auch mit Zittern** (`CLICK_SLACK`, `is_click`), und
  ein Klick, der nichts wählt, lässt die Taste der Kamera
  (`test_a_wobbly_click_stays_a_click`,
  `test_where_nothing_is_chosen_the_camera_keeps_the_button`). `is_click` bleibt
  eine reine Rechnung: Den Faktor für die Gerätepixel (`ansicht.md`) reicht der
  Navigator als Argument herein — eine Qt-Frage darin wäre ohne Bildschirm
  unprüfbar.
* **Die Tabelle `_NAVIGATION` ist ohne Fenster prüfbar**: `tests/test_navigator.py`
  fährt sie gegen ein Renderer-Doppel — welches Schema auf welcher Taste was tut
  und wo die Kamera danach steht.

## Die Ansicht hat eine eigene Steuerung

Das Schema `solidon` ist die Vorgabe (Entscheidung Robert): links verschiebt,
rechts dreht um den Mittelpunkt der Ansicht, das gedrückte Rad kippt, Scrollen
zoomt; Umschalt ändert nichts. `slicer`, `orbit`, `cad` und `blender` bilden
Fremdprogramme nach.

* **Links schiebt und wählt trotzdem**: `_left_up` trennt Klick und Zug über
  `is_click`, unabhängig davon, was `_begin` gestartet hat — `select` und `pan`
  dürfen auf derselben Taste liegen, nur `pan` und ein *gezogenes* Werkzeug
  nicht. Auf dem **gewählten** Körper führt links das Teil (Entscheidung Robert).
* **Dieser Zug rechnet auf einer Ebene, er pickt nicht**: gepickt wird beim
  Drücken (liegt dort der gewählte Körper?) und beim Zugbeginn (wo gegriffen?),
  danach schneidet `_plane_point` den Sichtstrahl mit der waagerechten Ebene
  durch den Griffpunkt (`render.gizmo.ray_plane_hit`). Ein Pick je Bewegung ist
  teuer **und** falsch: über dem Hintergrund trifft er nichts, zwischen hohen und
  tiefen Flächen springt er.
* **Das Kippen ist eine eigene Rechnung**: Der Navigator meldet nur die
  senkrechte Strecke (`_tilt_at`), gerechnet wird in `spacemouse.camera_step` —
  ohne Fenster prüfbar.
* **Fliegen ist nicht Zoomen**: `camera_step(..., fly=True)` schiebt Standort
  **und** Blickpunkt, ohne den Schalter ändert `y` nur den Abstand — der Zoom
  fährt bis vor das Teil, der Flug hindurch. Das Vorzeichen folgt dem Zoom, den
  der Zweig ersetzt.
* **Die Tastatur wirkt nur in `solidon`** — in den Nachbauten gäbe es die
  Bewegung im Vorbild nicht (in Blender ist WASD belegt).
* **Der Anschlag schaltet ein, er bewegt nicht**: Geflogen wird im eigenen Takt
  (`FLIGHT_TICK_MS`) mit der wirklich vergangenen Zeit, `FLIGHT_RATE` in
  Entfernungen je Sekunde — die Wiederholung des Systems ist kein Takt. Dabei:
  `isAutoRepeat` filtern (auch Loslass-Ereignisse wiederholen sich),
  `focusOutEvent` beendet den Flug, zwei Tasten auf einer Achse heben sich auf.
* **`setFocusPolicy(StrongFocus)` gilt in allen Schemata** — ohne ihn kommt kein
  Tastendruck an; ein Klick in die Ansicht nimmt einem Eingabefeld den Fokus,
  das Feld holt ihn beim nächsten Klick zurück. Ein Test, der danach tippt,
  tippt in die Ansicht; offscreen vergibt Qt gar keinen Fokus.

Wächter ohne Fenster (`test_viewport_decisions.py`, `test_spacemouse.py`): Jedes
Schema belegt alle sechs Kombinationen aus Taste und Umschalt
(`navigation_action` liest ohne Rückfall — eine Lücke soll werfen, nicht still
auf die Vorgabe fallen); jedes trägt einen Namen im Einstellungsdialog; die sechs
Flugtasten decken drei Achsen ohne Dopplung; der Flug nimmt den Blickpunkt mit,
der Zoom nicht.

## Der Drehpunkt ist, was in der Bildmitte steht

§2.9 und Entscheidung Robert: gedreht wird um den Mittelpunkt der Ansicht, auch
in der Tiefe. `_aim_rotation` fragt zuerst `centre_hit()` — derselbe
Oberflächen-Pick wie ein Klick (`_world_at`) in der Bildmitte —, erst ohne
Treffer `rotation_centre()`.

* **Die Kulisse zieht den Drehpunkt nicht an**: `_world_at` pickt nur unter den
  Körperaktoren (`among`) — eine Zeile, die beim Aufräumen überflüssig aussieht.
* **Der Rückfall ist der Normalfall am Rand** (Hintergrund, senkrechter Blick in
  eine Durchgangsbohrung, siehe `ansicht.md`, „Ein Klick ist eine
  Blickrichtung“): die Mitte der Körper, nie „kein Drehpunkt“.
* **Das gedrückte Rad bekommt ihn auch** — der `tilt`-Zweig ruft
  `on_rotate_start` wie das Drehen.
* **Das Bild ändert sich beim Setzen nicht**: Der Fokus liegt auf dem Sichtstrahl,
  Stellung und Blickrichtung bleiben (Entscheidung Robert: die Kamera bleibt, wo
  sie ist).
* **Wer „da ist nichts“ prüft, blickt in den Himmel** — knapp am Teil vorbei misst
  man die Toleranz des Picks.

## Gedreht wird als Drehteller, nicht als Trackball

Ein Trackball führt das Oben der Kamera mit und summiert Schräglage.
`turntable_camera` dreht waagerecht um die Welt-Hochachse und senkrecht um die
Bildwaagerechte; das Oben folgt daraus. Die Hebung wird an `POLE_LIMIT_DEGREES`
**begrenzt, nicht abgeschnitten** — fast senkrecht darüber dreht man weiter
waagerecht und kommt jederzeit zurück, auch aus einer Draufsicht des Menüs. Die
Empfindlichkeit blieb die des alten VTK-Trackballs (`TURN_MOTION_FACTOR`), damit
sich die gewohnte Geschwindigkeit nicht verstellt. Es gilt für alle fünf
Schemata — ein Nachbau, der neigt, wo sein Vorbild es nicht tut, ist keiner.

## Kameravorgaben und Einpassen

* **Die Anwendung setzt ihre Startkamera selbst** (`view_from("iso")` beim
  Aufbau), sonst erbt sie die des Renderers.
* **Eine Kameravorgabe dreht um den Blickpunkt, sie passt nicht ein**
  (Entscheidung Robert, wie in Assist): Strg+0 bis Strg+6 und die ViewBar lassen
  Fokus und Abstand stehen (`_turn_camera_to`, derselbe Kern wie
  `_settle_sketch_view`); der Iso-Vektor wird genormt, sonst wächst der Abstand je
  Klick. Einpassen ist Pos1, die erste Rahmung eines Projekts `_fit_once_for`.
* **Einpassen nimmt den gewählten Körper, wenn einer gewählt ist**, sonst die
  Szene (Entscheidung Robert); der Eintrag heißt „Einpassen“, denn ein Name, der in
  einem Zustand lügt, ist schlechter. Der Versatz gehört dazu (`_selected_bounds`
  über `_view_offset`); was nicht im Bild ist, wird nicht gerahmt (§18.8, §25).
  `_fitted_bounds` bleibt die Szene, sonst hielte `outgrown` jede kleine Auswahl
  für eine gewachsene Szene. Im Skizzenmodus gehört Pos1 dem Blatt
  (`SketchCanvas.fit_view`), und die ViewBar rahmt nirgends.
* **Der automatische Weg folgt der Auswahl nicht**
  (`reset_camera(follow_selection=False)` in `_fit_once_for`) — er rahmt, weil die
  Szene entwachsen ist.
* **Eine frische Teilung rahmt einmal neu**: `MainWindow._reveal_split_result`
  ruft vor dem Auseinanderziehen `Viewport.frame_next_scene` (alle Körper, ohne
  Auswahl, mit Versatz); danach bleibt die Kamera.
* **Im Skizzenmodus weicht die Kamera der Werkzeugkarte**: Orthografisch
  verschiebt `occluded_view_shift` Position und Fokus um die halbe unten
  verdeckte Bildhöhe (gemeldet über `set_zone_margins`), ohne Richtung und
  Maßstab, zurückgenommen beim Verlassen. `view_on_plane` und
  `show_span_on_plane` setzen sie nach jeder Kamerastellung neu; `view_from`
  nimmt den gespeicherten Weltvektor vor dem Drehen zurück, rechnet den
  Ausgleich für die neue Richtung und meldet die neue Hauptansicht an das
  Ebenenfeld. **Ein gespeicherter Versatz wird nie von einer Kamera abgezogen,
  die ihn nicht mehr enthält, und bleibt nie in einer Richtung stehen, die sie
  nicht mehr hat.**
* **Geprüft an der Kamera, nicht an der Vorarbeit** — offscreen steigt
  `reset_camera` vor dem Rahmen aus; gemessen über `RecordingRenderer.reset_bounds`
  (`tests/render_fakes.py`).

## Wer die Kamera bewegt, meldet zuerst und zeichnet danach einmal

Eine Kamerabewegung meldet sich über `cameraMoved` (Radzoom über `on_camera`,
Zugende über `on_end`, 3D-Maus über `settle_camera`, Ansichtsknöpfe über
`view_from`). **Erst melden, dann ein Bild**: Die Hörer legen ihre Punkte neu und
zeichnen nicht selbst (`PlacementFlow._camera_moved` →
`redraw(draw=False)`); der Sender zeichnet danach genau eines.
`set_camera_pose(…, draw=False)`, `_redraw_shadows(draw=False)` und
`_settle_sketch_view(draw=False)` geben das Bild dem Aufrufer
(`test_a_camera_move_with_measures_in_the_view_draws_exactly_one_frame`).

**Wer die Kamera im Takt bewegt, sagt es vorher** (`note_camera_motion`:
Zeigerzug und Rad über `_on_pointer`, die 3D-Maus je Takt vor
`set_camera_pose`, die Flugtasten je Takt); was der Renderer daraus macht, steht
in `ansicht.md`, „Ein Zug zeichnet leichter, sein letztes Bild voll“.

## Die Kamera hat einen zweiten Treiber

Die 3D-Maus (`app/ui/spacemouse.py`, Konzept `konzept-3d-maus-2026-08`) fährt
dieselbe Kamera wie die Maus — kein eigenes Navigationsschema, kein Modus, keine
Operation.

* **Die Abbildung ist eine reine Funktion**: `camera_step` bekommt sechs Achsen,
  eine Stellung, eine Zeitspanne und drei Einstellungen und gibt eine Stellung
  zurück — kein Qt, kein Renderer, kein HID. Jeder Achsenfehler wird dort behoben
  und in `tests/test_spacemouse.py` mit einem Test je Achse gehalten; wer die
  Wirkung einer Achse ändert, macht genau einen Test rot. Objektmodus
  ist die Vorgabe (die Kappe ist das Teil, alle sechs Achsen; Entscheidung
  Robert), „Richtung umkehren“ der Kameramodus.
* **Die Kappe ist ein Kraftsensor, Achsen sprechen über**, und die Totzone fängt
  das nicht. `quiet_crosstalk` dämpft jede Nebenachse nach ihrem Anteil an der
  stärksten: null unter `CROSSTALK_SILENT`, voll ab `CROSSTALK_MEANT`, dazwischen
  eine **Rampe, keine Klippe** — eine harte Schwelle schaltet die Zoomachse
  ständig an und aus. Die stärkste Achse bleibt immer, eine aktive Bewegung also
  aktiv. Preis: Eine bewusst kleine Nebenbewegung geht verloren, und ein Rest
  des Übersprechens bleibt — das ist der Sensor. Band und Kennlinie sind an der
  Aufzeichnung gewählt und **am Gerät noch nicht bestätigt**; geändert wird nur
  mit Messung am Korpus (Korpus-Tests in `test_spacemouse.py`).
* **Der Viewport bekommt eine Stellung, keine Deltas**:
  `Viewport.set_camera_pose` setzt Standort, Blickpunkt und Oben und zeichnet
  einmal — die einzige Stelle, an der die 3D-Maus den Viewport anfasst;
  `sketch_active` sagt ihr, dass im Zeichenmodus nur geschoben und gezoomt wird.
* **Direkt über HID, neben dem Herstellertreiber**: `hidapi` (BSD-3 gewählt)
  öffnet *Multi-axis Controller*, 3DxWare darf mitlesen. Raw Input bleibt leer
  (3DxWare reicht Rohdaten nur an bekannte Programme). Gelesen nicht
  blockierend im Hauptthread, ein Takt für Lesen und Fahren; gesucht
  (`hid.enumerate`) im Daemon-Faden (`SpaceMouseController._search`) und
  geöffnet im Hauptthread — die Suche griff dort für jeden Gerätenamen nach dem
  GIL und hielt neben einem Arbeiter das Fenster an; die Vorzeichen stammen aus einer
  aufgezeichneten Lesung (`tests/data/spacemouse/`), nicht aus einer Annahme.
* **Auf dem Mac durch den Treiber**: 3DxWare hält das Gerät exklusiv.
  `DriverReader` lädt das `3DconnexionClient`-Framework des Kunden zur Laufzeit
  (mitgeliefert wird nichts, Regel 22) und schreibt seine Meldungen in dieselben
  Berichte um, die das Gerät roh liefert; `decode_report` und alles dahinter
  merken keinen Unterschied. Angemeldet mit dem Platzhalter wie FreeCAD und
  Blender, gelesen nur, was an Solidons Client-Kennung geht. `default_reader`:
  Mac mit Treiber → Treiber (HID als Rückfall), sonst HID; die Plattform ist ein
  Parameter, damit der Mac-Zweig überall prüfbar bleibt. **Am Gerät gemessen ist
  nur Windows**; der Mac-Weg wartet auf die Rückmeldung eines Kunden.

## Was die Suite prüft und was nur das echte Fenster

Offscreen ist `Viewport.renderer` `None`: Die Suite prüft die Regeln gegen
Attrappen (`RecordingRenderer`, Renderer-Doppel), nie die Kette Qt-Ereignis →
Widget des Renderers → `PointerEvent` → Renderer. **Einheitstests über eine
reine Funktion sagen nichts darüber, ob jemand sie ruft.** Die Kette zeigt nur
das echte Fenster, und einen lauffähigen Prüfstand dafür gibt es nicht: Die zwei
alten (Drehpunkt, Steuerung) schickten VTK-Ereignisse an `viewport.plotter` und
sind entfernt. Nach einer Änderung an `_NAVIGATION`, am Navigator oder an
`camera_step` gehört die Navigation deshalb in die Fensterabnahme (RM-213). Wer
einen Prüfstand baut, schickt `QMouseEvent` an `renderer.widget` und kennt die
Fallen: Millimeter sagen nichts (jede Bewegung skaliert mit der Entfernung),
Bildpunkte in einem kleinen Renderfenster gar nichts, und `session.apply`
blockiert den Hauptthread.
