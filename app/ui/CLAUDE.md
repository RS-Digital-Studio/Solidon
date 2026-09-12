# `app/ui/` — die Oberfläche

PySide6. Darf `app.core` benutzen, die Gegenrichtung ist verboten (§8). Die
Oberfläche rechnet keine Geometrie und ändert keine — **sie ruft Ops auf.**

Die Regeln dieses Gebiets stehen in `.claude/rules/` und laden sich selbst —
**vier Dateien, je nachdem, was man anfasst:**

| Regeldatei | Lädt bei |
|---|---|
| `oberflaeche.md` | jeder Datei hier — Texte, Zahlen, Grenzen, Barrierefreiheit |
| `ansicht.md` | `viewport.py`, `overlay.py`, `cursors.py` und den Leisten |
| `wartezeit.md` | `session.py`, `loading.py`, `leash.py`, `splash.py`, `main_window.py` |
| `zeichenflaeche.md` | `sketch_editor.py` |

Hier steht die Karte, dort das Gesetz.

## Filamente und lokales Lager

`filament_inventory.py` zeigt und verwaltet Spulen ohne Renderer; `filament_picker.py`
enthält den gemeinsamen Spulendialog und die Übernahme konfigurierter Slicerfilamente.
`filament_assignment.py` zeigt die Schnellauswahl. Beide Auswahlwege melden
`spoolChosen`, ohne lokale Kennungen in Geometrieparameter zu schreiben.
`main_window.py` führt die Zuweisungsoperationen aus und speichert die Bindung
getrennt in den Druckeinstellungen. Ein Katalogwechsel aktualisiert Wahlangebote,
nicht die eingebetteten Filamente einer geöffneten Szene.
Die Bestätigung prüft die angezeigte Druckidentität erneut gegen das Lager;
eine reine Bestandsänderung bleibt zulässig. Bei geänderten oder archivierten
Spulen zeigt die Auswahl einen bleibenden Hinweis und lädt ihre Angebote neu.
`spoolChosen(None)` verwirft eine vorgemerkte Lagerbindung. Von Hand veränderte
Filamentangaben werden nur als ausdrücklich ungebundene Projektwerte übernommen.
Schnellauswahl und Projektübersicht lesen tatsächlich verwendete Mesh-Slots;
verwaiste Definitionen werden nicht als belegte Filamente dargestellt.
Eine gemischte Auswahl benennt ganze Körper und einzelne Flächen getrennt.
„Filament entfernen“ benutzt denselben Umfang. Die ausgewählten Körper und
Flächen werden als `clear_filament`-Operationen in einer Transaktion abgelegt;
Strg+Z nimmt den gesamten Zug zurück. Neutrale Flächen bieten keine Abwahl an.
Der gemeinsame Editor für `kind="features"` zeigt eine Checkliste und eine
ausdrückliche Ganzkörperwahl. Alte Einzelwerte werden übernommen; ein leerer
Zwischenzustand sperrt Anwenden und vergrößert keine laufende Vorschau.
Die Hauptaktionen der Auswahl wechseln bei schmaler Spalte in eine Spalte,
statt die Karte horizontal aufzuweiten. Journalzeiten werden mit
`labels.local_timestamp` im lokalen Gebietsschema dargestellt.
Die Filamentübersicht lässt Qt das Beiwerk ihrer Liste bei der tatsächlichen
Breite messen (`totalHeightForWidth`). Wunsch, Mindesthöhe und Zuteilung
enthalten denselben umbrochenen Hinweis und nur sichtbare Bedienelemente.
Breite, Schrift, Stil und Sichtbarkeit erneuern diesen Höhenvertrag.

Spulenkarten zeichnen die Restmenge zusätzlich zur Farbe als Zahl und
Füllstand; unbekannter und archivierter Bestand tragen sichtbare Texte.
Nennfüllung, Restmenge und Lagerort stehen im Spulendialog vorn. Kurze
Kennungen unterscheiden gleiche Etiketten; Details und zugängliche
Beschreibungen bewahren die Kennung unabhängig von dieser Verkürzung.

`filament_usage.py` hält Angebote erfolgreicher Ausgaben ohne Zeitlimit bereit.
Ein Dialogwechsel übernimmt sie mit `auto_book=False`, damit der Transfer keinen
neuen Buchungsanlass schafft. Lagerzugriff und atomare Journaländerungen laufen
über Arbeiter; Aufteilung, Wiederholungsdruck und manuelle Korrektur sind
ausdrückliche Handlungen. Jede Menge nennt ihre Herkunft, jeder belegbare Preis
die gespeicherte Währung. Druckvorbereitung und Bestandswarnung bleiben getrennt
von der Buchung. Die Einstellung liegt lokal, die Vorbereitungskennung im Projekt.
Die erste automatische Buchung benutzt eine aus dem Fingerabdruck abgeleitete
Vorgangskennung, damit gleichzeitige Zustellungen denselben Abzug treffen.
Beim Schließen zählen laufende und eingereihte Lagerhandlungen mit.
Der Buchungsstatus folgt dem ausgewählten Ausgabe-Fingerabdruck. Manuelle
Korrekturen übergeben den gelesenen Vorgangsstand, damit ein älterer Dialog
keine jüngere Aufteilung überschreibt. Der Auswahl-Export ordnet gespeicherte
Herstellerprofile anhand der Druckfilamentidentität seiner tatsächlichen
Teilmenge zu; deren neue Werkzeugnummern sind kein Index in die Gesamtszene.
Die Sitzung bindet alte positionsgebundene Herstellerprofile an der letzten
vollständigen Szene. Der Druckdialog schreibt neue Wahlen nach dieser
Identität und erhält sie beim Qualitätswechsel. Die Umstellung der Darstellung
ändert keine Druckwerte; Undo und Redo finden weiterhin dieselben Filamente.
Ein nicht verfügbares gebundenes Profil bleibt mit Originalnamen als ungelöst
sichtbar. Befüllen der Liste wählt kein anderes Profil. Ein ausdrücklich
geändertes Herstellerprofil erhält die gewählte physische Spule; automatische
Buchung prüft deren Eignung weiterhin gesondert.
Für die ausdrückliche Wertübernahme hält der Druckdialog das gewählte
`SlicerProfile` einschließlich seines Prusa-Abschnitts fest. Der Dateipfad
allein beschreibt bei Herstellerbündeln noch kein bestimmtes Filament.

## Der Weg durch die Schicht

```
main_window.py   Menüs, Auswahl, Zustand
      │  ruft eine Operation auf
      ▼
session.py       die Brücke zum Kern: Stapel, Auswertung, Threads
      │  wertet aus (im Arbeiter-Thread)
      ▼
app.core         rechnet
      │  EvaluationResult
      ▼
viewport.py      zeigt an
```

`session.py` ist die einzige Stelle, an der die Oberfläche den Kern anfasst.
Wer an ihr vorbei rechnet, bricht Regel 2.

## Die fünf Dinge, die an `session.py` überraschen

Ende zu Ende gemessen am 27.08.2026 — vier Anläufe gingen daran verloren,
bevor es jemand wusste:

- **`session.last_result` ist die ausgewertete Szene.** Ein
  `session.scene` gibt es nicht.
- **`evaluate_now()` ist der synchrone Weg** — für Kommandozeile, Tests und
  Export. Er gibt das Ergebnis zurück, statt es nur anzustoßen.
- **`session.apply()` endet mit `evaluate_async()`.** Nach dem Aufruf steht
  das Ergebnis noch **nicht**. Und es wirft nicht: Fehler kommen über das
  Signal `failed`. Ein `try` um den Aufruf läuft ins Leere — nach dem
  Ergebnis fragen, nicht nach dem Grund.
- **Und hinter einen Halt nimmt es keinen Schritt an.** Solange
  `last_result.stopped_at` steht, schreibt `apply` mit Entwürfen nichts und
  meldet über `failed` die Absage aus `halt_in_the_way` — mit den Handlungen
  des Halts; `halted_step()` nennt Kennung und Titel des Schritts. Ein Test,
  der nach einem Halt weiterbauen will, löst ihn erst (Undo, `change_params`,
  `recount_and_retry`). Die Regel steht in `oberflaeche.md`.
- **`Scene.objects` ist ein Wörterbuch.** Darüber zu iterieren gibt die
  Kennungen. Die Folgemeldung `'str' object has no attribute 'mesh'` sieht
  aus wie ein leerer Import und ist keiner.

- **Das Fenster liest über `import_model_async`, nicht über `import_model`.**
  Der synchrone Weg steht daneben und bleibt — Kommandozeile und Tests
  brauchen einen, der wirft. Das Fenster braucht einen, der meldet: Bei einer
  3MF zählt `import_plan` die ganze Baugruppe, bevor eine Operation entsteht,
  und das dauert bei 63 MB vierzehn Sekunden. Oberhalb von
  `PLAN_IN_WORKER_ABOVE` läuft das im Arbeiter, der Fehler kommt über
  `importFailed`. Wer in einem Test `session.import_model` patcht, patcht
  damit einen Weg, den das Fenster nicht mehr geht — fünf Tests in
  `test_ui.py` hingen daran (03.09.2026).

  Einleseplan und Auswertung teilen sich `busy` und `busyChanged`. Erst die
  zugestellten Endsignale beider Arbeiter beenden den Fortschritt; weder die
  leere Startauswertung noch ein Importfehler dürfen den noch laufenden
  anderen Arbeiter ausblenden. So bleibt auch Abbrechen bis zum Ende erreichbar.

## Die Karte

Zwei benannte Merkmale verschiedener Körper werden im Objektbaum gemeinsam
gewählt. Das Merkmalpanel zeigt beide Körper und Merkmale, die vom Kern
geeigneten Passungsarten und deren materialfolgendes Sollmaß. Erst
„Passung anlegen“ ruft einmal `Session.add_fit` auf; ein Undo entfernt die
Beziehung. Vor dem Schreiben werden Projekt, Ergebnisstand, Auswahl und
Eignung erneut geprüft. Bestehende ungeordnete Paare werden angezeigt statt
doppelt angelegt. Rohrmaße liest das Panel aus `relations.sleeve_at`; es
speichert dafür keine zusätzliche Beziehung. Nach einem Baumneuaufbau werden
Auswahl, Tastaturzeile und Sichtbarkeit anhand der heutigen Kennungen
wiederhergestellt; ein verzögerter Scroll-Aufruf hält keine alten Baumzeiger.

**Rahmen und Einstieg**

`app.py` (Einstiegspunkt, §38) · `qt_platform.py` (welche Qt-Plattform die
3D-Ansicht braucht — entschieden vor der `QGuiApplication`, ohne Qt-Import;
Qt 6 nähme in einer Wayland-Sitzung sonst Wayland, und der wgpu-Fensterweg ist
nur unter X11 und Xwayland geprüft — nativer Wayland-Betrieb von rendercanvas
ist ein offener Punkt) · `main_window.py` (**rund 8 900 Zeilen** — das
Hauptfenster, §2.5) · `splash.py` · `first_run.py` (der erste Start) ·
`start_screen.py` (die ersten fünf Minuten, §2.3) · `header.py` (Projektname,
Druckerwechsel und die tatsächlich in der Szene verwendeten Filamente)

**Brücke zum Kern**

`session.py` (§7, §15.6) · `leash.py` (die Halteleine für Arbeiter-Threads — und für Ereignisfilter,
die ihr überwachtes Objekt überleben: `stop_watching_the_dying`)

**Ansicht**

`viewport.py` (**rund 8 200 Zeilen** — §18, §2.9) · `render/` (der Renderer
hinter der Ansicht, eigene `CLAUDE.md`: der Vertrag `api.py`, pygfx über wgpu
in `gfx_renderer.py`, gebaut über `factory.py`, Kameraführung, Formen,
Bewegungsgriff) · `overlay.py` (Zonen über der
Ansicht statt neben ihr) · `loading.py` (Ladeanzeige, §2.8) · `cursors.py` ·
`placement_flow.py` (Oberflächenplatzierung aus dem Operationsdialog, §18.5) ·
`spacemouse.py` (die 3D-Maus als zweite Hand an derselben Kamera: HID-Leser
über hidapi, auf dem Mac der Treiberweg über das 3Dconnexion-Framework des
Kunden, die Abbildung als reine Funktion — Regel in `ansicht.md`).
**`camera_step` hat drei Aufrufer, nicht einen:** die Kappe, das Kippen mit
dem gedrückten Rad und die Flugtasten. Wer dort an einer Achse dreht, dreht
an allen dreien

**Wer eine Fläche braucht, kommt gleich hin — wer keine braucht, behält
seinen Dialog.** `placement_flow.starts_by_itself(spec)` zieht die Grenze an
`consumes`: Baustein, Beschriftung und Bohrung sitzen auf etwas und gehen
sofort in die Platzierung; die fünf Grundkörper entstehen aus eigenen Maßen an
eigenen Koordinaten und bleiben beim Dialog. Dort zeigt die Live-Vorschau den
Körper, sobald der Dialog offen ist — `Session.preview_async` rechnet ihn
ohnehin, und `request()` überspringt sie nur, solange die Platzierung läuft.
`start()` versteckt den Dialog, und Breite, Tiefe und Höhe stehen nirgends
sonst; wer die Maße ändern wollte, musste sonst Escape drücken, tippen und neu
platzieren. Der Knopf bleibt für den, der doch auf eine Fläche will.

**Und diese Vorschau lässt sich anfassen.** `Viewport.set_preview_gizmo`
hängt denselben Bewegungsgriff an den `added:`-Aktor der Vorschau, den
`set_gizmo` sonst an die Auswahl hängt — ohne Skalierwürfel, denn Breite,
Tiefe und Höhe stehen im Dialog daneben. Der Zug meldet sich über
`previewDragged` als **Matrix** und nicht als `TransformSteps`: Er wird keine
Operation, sondern Zahlen, und `primitive_ops.placement_values_of` rechnet
daraus Ort, Richtung und Winkel — die Umkehrung von `placement_transform`,
gegen ihn geprüft. `_grips_its_preview` entscheidet, wer ihn bekommt: wer
seinen Dialog behält und die Felder dafür hat — heute zwölf Operationen,
die sieben Grundkörper samt dem Gewindebolzen und die vier freistehenden
Bausteine.

**Und die Maßfelder lassen ihm seinen Platz.** Sie sind Qt-Widgets über der
Renderfläche, und was dort liegt, nimmt die Zeigerereignisse an — der Griff
wäre sichtbar und tot. `Viewport.gizmo_reach()` nennt Ursprung und Reichweite,
`PlacementFlow` hält daraus ein eigenes gesperrtes Rechteck frei (als zweites
und nicht als größerer Radius: Der Griff sitzt an der Bohrungsmitte, der
Setzpunkt an ihrer Mündung).

**Und er kommt nie neben den Griff der Auswahl.** Der hängt am zuletzt
gewählten Körper und trägt einen Skalierwürfel; die Vorschau daneben zeigt
den Körper, den der Dialog gerade anlegt. Wer den Würfel anfasste, änderte
die Maße eines fremden Teils, während die des neuen im offenen Dialog
stehen. `set_preview_gizmo(True)` nimmt ihn deshalb ab und
`set_preview_gizmo(False)` baut ihn wieder auf — `_detach_gizmo` lässt den
Schalterzustand in Ruhe, die Entscheidung bleibt also stehen.

**Ein Griff, der nicht in `_on_pointer` steht, ist sichtbar und tot.** Er
wird gezeichnet, nimmt aber kein Zeigerereignis an, und jede Geste fällt
durch zur Kameraführung — wer den Quader in seiner Vorschau verschieben
wollte, schwenkte die Ansicht. Die Vorfahrt dort ist die eine Stelle, an
der ein neuer Griff eingetragen wird; `tests/test_viewport_decisions.py`
liest sie im Quelltext gegen die Griff-Felder des Aufbaus. Der Griff wird nach jedem
Neuzeichnen der Vorschau frisch angehängt; er rechnet gegen die Matrix seines
Ziels beim Anhängen, und die Vorschau kommt bei jeder Wertänderung neu.

**Ein Loch hat eine Länge, und die ist eine Geste.** `slot_handle.py` hängt
zwei Knöpfe an ein gewähltes Loch (`hole` oder `slot` — welche Arten, sagt
`slot_feature_kinds()` aus dem `applies_to` von *Zum Langloch ziehen*), gezogen
wird in der Ebene seiner Mündung. Der Zug gibt beides zugleich: die **Länge**
aus dem Abstand zur Mitte, die **Richtung** aus dem Winkel dazu — gegen
dieselbe Rahmenachse gezählt, gegen die `prepare.slot_profile` schneidet und
`prepare_ops.slot_angle_of` misst. Der Umriss im Bild kommt aus derselben
Funktion wie der Schnitt; beim Loslassen meldet `slotDragged` Kennung, Länge
und Winkel, und `MainWindow._on_slot_dragged` macht daraus **einen** Schritt.

Er sitzt genau dort, wo der Skalierwürfel nicht sitzt: Der gilt dem ganzen
Körper, ein Merkmal hat keine Größe, die er ändern könnte — ein Loch aber hat
eine. Die Form trägt die Bedeutung (Regel 18): Pfeil schiebt, Ring dreht,
Würfel skaliert, **Knopf zieht in die Länge**; das `L` daneben ist dieselbe
Schreibweise wie das `S` am Würfel.

**Und er hängt an einer eigenen Artenmenge.** `slot_handle_feature()` fragt
`slot_hole`, `gizmo_feature()` fragt `move_feature` — ein Langloch trägt heute
die eine Fähigkeit und die andere nicht, und über einen Kamm geschoren
verlöre es beide. An einem Langloch steht deshalb der Knopf **ohne**
Bewegungsgriff; drei Pfeile, die keine Operation einlöst, wären schlimmer als
keine.

**Der Zug endet im Merkmalfenster, nicht im Verlauf** (Robert, 10.09.2026):
Wohin etwas gehört, sagt die Stelle, an der man loslässt; wie **lang** es ist,
sagt eine Zahl, und zwanzig Millimeter trifft niemand mit der Maus. Nach dem
Loslassen bleibt der Umriss stehen, und `Viewport.slotProposed` schreibt Länge
und Richtung in die Felder unter *Zum Langloch ziehen*; erst das Übernehmen
dort macht daraus die Operation. Die Eingabetaste an der Zugleiste ist der
kurze Weg dorthin, Escape verwirft.

**Eine eigene Leiste unten hatte er bis zum 11.09.2026** (`slot_bar.py`), mit
denselben zwei Zahlen und einem zweiten Übernehmen — zwei Bedienstellen über
demselben Loch (Robert: „auch 2 mal übernehmen einmal unten und einmal
rechts"). Sie ist gefallen; was von ihr bleibt, ist die Frage
`Viewport.slot_drag_waits()`: **der Zustand und nicht ein Widget** — Umriss im
Bild, gemerktes Merkmal, noch kein Schritt.

Erst ein Zug über die gemeinsame Klickschwelle beginnt eine Vorschau;
Zurückziehen auf den Druckpunkt räumt sie wieder ab. Der Richtungsfang
entspricht dem Drehring.
Die Merkmalsfelder schalten schon beim Fokussieren ihre Handlung scharf;
deren Titel steht über *Übernehmen*. Feldlose Handlungen haben einen eigenen
Knopf. Bei Bausteinauswahl bleiben die Handlungen am erzeugenden Schritt;
sein Entfernen nutzt die Folgeauskunft des Verlaufs (§19).

Solange ein Langlochzug wartet (`slot_drag_waits`), blendet `PlacementFlow`
seine Platzierungsfelder und Vorschau aus und nimmt keine Platzierungsklicks
an. Escape stellt die bisherige Platzierungsabsicht wieder dar; das
Übernehmen verwendet weiterhin den einen Langlochschritt.

**Ein gewähltes Merkmal bekommt seinen Griff ohne Werkzeug.** Der Schalter
gehört dem Werkzeug *Bewegen* und gilt dem ganzen Körper — dort trägt der
Griff den Skalierwürfel, und der ändert auf einen Zug die Maße des Teils.
Am Merkmal ist der Klick selbst die Ansage (Robert, 10.09.2026: „über den
viewport sehen wir weder maße noch etwas zum verschieben, verlängern, drehen
usw"); der Würfel bleibt dabei weg.

**Und die Maße wie beim Setzen kommen auf Knopfdruck.** Wer ein Loch gewählt
hat, findet im Merkmalfenster *Im Bild einstellen*; der Knopf bringt die
Flächenplatzierung mitsamt Maßlinien zu den Kanten und einem Zahlenfeld je Maß
in die Szene. `FeaturePanel.inViewRequested` bleibt getrennt von
`operationRequested`, weil das eine zeigt und das andere schreibt.

**Er steht einmal je Merkmal, nicht je Handlung** (`_settle_in_view`). Die
Maßlinien zeigen die Stelle des Lochs, und die ist dieselbe, gleich ob man
gerade den Durchmesser oder die Länge ansieht; an der scharfen Handlung
aufgehängt verschwände der Knopf, sobald jemand ein Feld von *Merkmal drehen*
anfasst.

**Und die Platzierung trägt dabei kein Fenster** (`QuietHost`, 11.09.2026).
Bis dahin startete sie von selbst und hing an einem Operationsdialog, der
daneben stand und Durchmesser, X, Y und Z ein zweites Mal zeigte — dieselben
Zahlen, die rechts im Merkmalfenster stehen, nach einer Operation sogar mit
anderen Werten (Robert: „werte im dialog und in der rechten merkmalleiste
doppelt, sehr verwirrend für den Kunden"). Was der Fluss von seinem Träger
braucht, steht in `PlacementHost`; `MainWindow.end_quiet_placement` räumt ihn
ab, denn ohne Fenster meldet niemand sein Ende.

**Sie beginnt dabei dort, wo das Merkmal schon sitzt** (`_begin_at_feature`,
10.09.2026). Bis dahin fing jede Platzierung bei „Auf eine Oberfläche zeigen"
an — richtig für ein Werkzeug, das noch nirgends sitzt, falsch für eine
Bohrung, die schon da ist: Ihre Stelle steht fest, offen sind die **Maße**.
Die Fläche ohne Klick liefert `placement.seat_of`; der Rest ist derselbe Weg
wie nach einem Treffer und endet gleich in Stufe zwei. Wo es keine Trägerfläche
gibt, bleibt es beim Zeigen — kein Fehler, ein Rückfall. Welche Handlungen
das anbieten, sagt der Kern (`placement.supports_surface_placement`), nicht
eine Liste in der Oberfläche.

**Und dort zielt der Zeiger nicht** (`_seated_at_feature`, 11.09.2026). Die
Stelle gehört dem Merkmal; eine Mausbewegung darüber verschob sie samt aller
Maßlinien unter der Hand, und die Abstände liefen vom Zeiger statt von der
Bohrungsmitte (Robert: „wir wollen aber bei der bohrung das mittelloch"). Ein
**Klick** ist die ausdrückliche Ansage, das Loch woanders hinzusetzen, und
danach zielt wieder der Zeiger — beim Setzen einer neuen Bohrung ändert sich
nichts.

**Eine Geste im Bild räumt sie ab** (`_drop_stale_measures`). Was dort steht,
gilt für einen Stand, den die Geste gerade ändert: Der Zug am Bewegungsgriff
versetzt das Loch, der am Langlochgriff macht es länger. Der Knopf bringt sie
danach zurück — an derselben Stelle, mit den neuen Zahlen.

**Ein Merker (`_measured_for`) und zwei Wächter standen hier bis zum
11.09.2026** und hingen alle am Selbststart: Er sprang nach jeder Auswertung
neu an, verwarf dabei offene Dialoge und fragte bei zurückgenommenen Schritten
nach. Mit ihm sind sie gefallen. Was von der Frage bleibt, ist die Zusage von
§18.5: Ein Klick auf ein Merkmal ist eine **Eingabe**, wo ein Dialog auf eines
wartet — und das entscheidet weiterhin `_on_feature_picked`.

**Der Werkzeugkörper gehört dazu, sonst bleibt der Knopf grau.**
`PlacementFlow` gibt *Übernehmen* nur frei, wenn `placement.prepare_tool` einen
Körper geliefert hat; `_creation_tool` kennt dafür einen eigenen Zweig für
`slot_hole` und `resize_hole`, der Mitte, Achse und Tiefe aus dem **Merkmal**
liest. Wer eine weitere Operation in `supports_surface_placement` einträgt,
trägt sie auch dort ein — sonst zeigt die Oberfläche Maßlinien und eine Leiste,
die „Übernehmen" sagt, und nichts davon geht.

**Zwei Wege dürfen nicht auf dasselbe Loch schreiben.** Der Zug am
Langlochgriff macht ein Langloch, der Dialog *Bohrung ändern* eine runde
Bohrung; nebeneinander offen nahm der eine zurück, was der andere gerade getan
hatte. `Viewport.slotStarted` meldet das Übernehmen des Langlochzugs, und
das Fenster schließt daraufhin die Platzierung an derselben Stelle. **Beim
Übernehmen und nicht beim Ziehen**: Solange der Zug wartet, ist nichts
geschehen (Regel 2) — und die Maße sollen währenddessen im Bild stehen.

**Platzieren geht in drei Stufen** (Robert, 09.09.2026). Zeigen und klicken
legt die **Stelle** fest (`_settle`) — der Klick schließt nicht mehr ab, denn
er nähme jede Vorgabe mit, die daran hängt, und bei einer Bohrung heißt
`depth = 0` durch das ganze Teil. Dann stehen die **Maße** offen: die Abstände
zu den Kanten als Zahlenfelder, eintippbar. Erst das Übernehmen führt in die
**Tiefe** (`_begin_depth`), wo es eine gibt — sonst schließt Stufe 2 ab.

Wer eine Tiefe hat, sagt `deepens()`: Das Werkzeug sitzt auf etwas
(`consumes != 0`) **und** führt ein Längenfeld dafür (`parts.ops.depth_field`).
Beides ist nötig — ein Quader trägt ein Feld namens `depth`, und das ist seine
Bauteiltiefe, nicht die Eindringtiefe. **Und der Name allein entscheidet
nicht:** `depth_field` fragt zusätzlich die Abtragsrichtung, sonst zöge die
Stufe an der vorstehenden Nase von `insert_latch` oder an einer erhabenen
Beschriftung. Die Regel dazu steht in `app/core/knowledge/parts/CLAUDE.md`.

**Die Stufe beginnt mit einer Tiefe, nicht mit der Null.** Bei `depth = 0`
bohrt die Operation durch das ganze Teil; wer die Stufe betrat und ohne zu
ziehen übernahm, bekam genau das, was sie abschaffen soll. Vorbelegt wird mit
dem Material unter der Mündung, und der Zug fällt nicht unter
`LEAST_DEPTH_MM` — sonst führte ein Zug nach *oben*, der flacher machen soll,
am Ende des Wegs hindurch. Die Null bleibt über das Maßfeld erreichbar, wo sie
ausgeschrieben dasteht.

In der Tiefenstufe kehrt sich um, was Stufe 1 zeigt: Der Werkzeugkörper tritt
**vor** (der Umriss sagt nichts über die Tiefe), das Modell wird durchscheinend
und die Kamera schwenkt quer zur Werkzeugachse — bei aufrechter Achse auf
Augenhöhe der Mündung. Die Kantenmaße weichen den Bezugsmaßen der Tiefe:
Maßlinie zur Spitze, Maßlinie zur Rückseite mit der Wand, die stehen bleibt,
und eine Marke auf halber Materialstärke. Der Zug misst **absolut** — die
Spitze liegt unter dem Zeiger, gerechnet aus der Bildrichtung der Achse und dem
Maßstab an der Stelle (`_pixels_per_mm_at`) — und rastet über
`transform.snap_to_marks` kurz an Mitte und Rückseite ein. Was die Platzierung
dort **nicht** nimmt, gehört der Kamera: Drehen, Zoomen und Kippen bleiben frei.

**Beide Größen werden je Bewegung neu geholt, nicht einmal beim Betreten.**
Die Bildrichtung der Achse war es von Anfang an; der Maßstab nicht, und die
Ansicht rechnet perspektivisch — nach einem Zoom um k war die Tiefe um k
daneben. Ebenso zählt, gegen welches Material gemessen wird: `_material_below`
schießt einen Strahl und nimmt den **ersten Austritt**, nicht den fernsten
Punkt des Hüllquaders. In der 2 mm starken Decke einer Box stand sonst
„Wand: 18,0 mm" im Bild, und das Einrasten hielt an Marken im Hohlraum.

**Eine getippte Zahl hält, und ein Zug an der Kamera setzt nichts fest.**
Beides sind Sperren über dasselbe Feld (`_depth_set`): Wer die Zahl eingibt,
hat entschieden — der Zug misst absolut und überschriebe sie sonst bei der
nächsten Bewegung, und der Weg zum Knopf führt über die Renderfläche. Und wer
die linke Taste zum Schieben drückt, meint nicht die Tiefe; unterschieden wird
an der Zugschwelle des Systems (`_barely_moved`), wie überall in der Ansicht.

**Drei Fallen, alle drei einmal zugeschnappt:** Ein Feld, dessen Sichtbarkeit
gesetzt wird, aber weiter eingesammelt wird, zeigt die Platzierungsschleife
danach wieder (`place` sammelt in der Tiefenstufe nichts mehr). Die Leiste
steht unten mittig über der Werkzeugzeile, und der Raum für die Maßfelder ist
seither der **über** ihr. Und was nach der Leiste nicht selbst gehoben wird,
liegt darunter und ist nicht anklickbar — Tiefenfeld und Wandzahl stehen
deshalb in derselben Liste wie die Kantenmaße.

**Platzieren bleibt eine Operation.** Der Operationsdialog übergibt Werte an
`PlacementFlow`; der Controller zeigt nur einen temporären Werkzeugaktor und
Maßpfeile. Der Dialog **bleibt dabei stehen**: Er trägt die Maße, die man beim
Platzieren braucht, und verschwand genau dann, wenn man sie sehen wollte. `Session.placement_async()` berechnet Originalfläche und
`PlacementTool` außerhalb des Qt-Threads. Mausbewegungen und Maßänderungen
verwenden diese Kontexte; der Merkmalskörper wird dabei nicht erneut gebaut.
Der Kontext gehört zu Eingaben und Werten, verspätete Ergebnisse werden über
Generation und Laufkennung verworfen. `Position übernehmen` bestätigt den
vorhandenen Dialog und erzeugt genau dessen Transaktion; Escape behält die
Zahlen ohne neuen Verlaufsschritt. Beim Bearbeiten eines historischen Schritts
liefert `Session.placement_before()` dessen tatsächlichen Eingang. Auch ein
fehlerhafter Schritt bleibt damit korrigierbar. `result_current` und
`Viewport.is_scene_applied()` sperren Ziele bis zur aktuellen sichtbaren Szene.
Maßfelder erhalten ihre Float64-Werte und werden gemeinsam außerhalb der
tatsächlich sichtbaren `OverlayHost`-Karten angeordnet; Verbindungslinien halten
verschobene Felder ihren Maßpfeilen zugeordnet.

Die Maßfläche belegt über eine `QRegion`-Maske nur Linien, Pfeilspitzen und
Zuordnungsmarken. Dort zeichnet sie deckend neu; der übrige Bereich bleibt dem
nativen Renderer. Ein vollflächiges `WA_NoSystemBackground`-Widget ist über
der pygfx-Renderfläche ausgeschlossen.
Die Maske nimmt die tatsächlichen Rechtecke aller Zahlenfelder und
Beschriftungen aus; die native Stapelreihenfolge allein schützt deren
Lesbarkeit nicht. Die gefüllte Werkzeugvorschau zeigt ihre Oberfläche ohne
innere Dreieckskanten.
Resize eigener Maßfelder ist ein Layoutergebnis und startet keinen weiteren
Aufbau; nur Viewport und Rendererwidget verändern die verfügbare Fläche.

**Die Auswahl behält den sichtbaren Treffer.** Ein Oberflächen-Pick trägt
Körper, Weltpunkt und Dreieck bis zur Merkmalsauswahl und Messung. Nur wenn
das gezeichnete Netz das unveränderte Originalnetz ist, bestimmt seine
Dreieckskennung das Merkmal direkt; Schnitt- und vereinfachte Netze nutzen
den Ortsfang. Platten- und Explosionsversatz werden für jeden Körper getrennt
zurückgerechnet. Ein Treffer gehört seinem Körper, auch wenn ein kleinerer
Hüllquader davor liegt. Die Öffnungszielhilfe gibt Körper und Merkmal gemeinsam
zurück. Dreieckszuordnung und vorbereitete Bohrungsachsen werden pro Auswertung
gespeichert und beim Szenenaufbau verworfen; Hover projiziert dadurch nicht
wiederholt alle Bohrungsdreiecke.
Die Öffnungszielhilfe verlängert keine axialen Bohrungsgrenzen. Seitlicher
Randfang gilt nur am sichtbaren Eintritt oder bei einem belegten Treffer des
wirklichen Bohrungszylinders; eine Rückwand bleibt eine Sichtgrenze.
Nur Bohrungen, Senkungen (`cone` mit `recess`) und Innengewinde bilden axiale
Öffnungsziele. Rundungen, Ringnuten und äußere Flächen bleiben Dreieckstreffer.
Die Rückrechnung liest den beim Aktoraufbau gespeicherten Versatz und die
tatsächlich gezeichneten Körper. Während eines neuen Ansichtsauftrags und
nach dessen Fehler bleibt dieses letzte Bild die Grundlage des Picks;
angeforderte Platten- oder Explosionszustände greifen erst mit dem neuen Bild.
Auch die Durchsicht der Druckplatte liest die zuletzt aufgebaute Szene und
deren sichtbare Körpermenge. Ihre Entscheidung wird bis zu einem Wechsel
dieser beiden Eingaben behalten; Kamerabewegungen lösen keine erneute exakte
CAD-Grenzenberechnung aus. Maßgeblich bleiben die ursprünglichen Körpergrenzen,
nicht die vereinfachten oder beschnittenen Anzeigeaktoren.
Merkmalsnamen und Maße stehen auf einem Feld in den Themenfarben, wie
Skizzenmaße. Der Text bleibt damit auch über heller Geometrie lesbar;
Merkmalsfläche und Ankerpunkt tragen weiterhin die Auswahl- beziehungsweise
Merkmalsfarbe.
Beschriftungen und Markierungsflächen benutzen dieselben Schnitt- und
Schichtebenen wie die Körper. Das automatische Schichtoverlay benennt nur
Merkmale, deren Dreiecke die aktuelle Ebene schneiden; die Anker liegen im
sichtbaren Schnitt. Auswahl und Hover dürfen erhaltene Geometrie darunter
benennen. Vollständig abgeschnittene Merkmale verlieren ihre Darstellung,
ihre Auswahl bleibt bestehen. Auswahl, Hover, Schutz und Kandidaten werden
ohne zusätzliche Schnittkappen begrenzt. Beim Schließen der Schicht gilt
wieder der unveränderte Merkmalschalter.
Markierungsflächen heben gemeinsame Originaleckpunkte gemeinsam an, mit den
flächengewichteten Normalen ausschließlich ausgewählter Dreiecke. Erst danach
werden die Punkte zur Dreiecksliste expandiert und geschnitten; weder fremde
Nachbarflächen noch ein Verschweißen gleicher Koordinaten verändern den Patch.
Die Akkumulation und Kreuzprodukte bleiben auf die ausgewählten Dreiecke begrenzt.
Das normale Merkmalslayout reserviert zuerst Leseraum für Auswahl und Hover.
Automatische Namen erscheinen nur an kollisionsfreien Plätzen nahe ihrem
Anker; alle Merkmalsmarker, Flächen und Baumziele bleiben erhalten. Versetzte
Namen sind mit dem dargestellten Merkmalsanker verbunden. Die Bildraumrechnung
berücksichtigt Kartenränder, interne Leisten und Gerätepixeldichte und folgt
Kamera sowie Größenänderungen. Sie benutzt nur Projektion und Textmaße, keine
Geometriesuche oder GPU-Rücklesung. Gleiche Kamera- und Layoutdaten werden
wiederverwendet; gleiche Textlisten und Linienzahlen verschieben vorhandene
Rendererobjekte. Bei Körpervorschauen folgen Marker, Text, Verbindungslinien
sowie Auswahl- und Hoverflächen der Matrix und Position ihres Körperaktors.
`select_feature_refs` hält objektübergreifende Merkmalsauswahl als vollständige
Paare aus Körper- und Merkmalskennung; gleiche lokale Kennungen bleiben getrennt.
Das erste gültige Paar führt die Körperauswahl, mehrere Paare erzeugen kein
scheinbares Einzelmerkmal. Jede Körpergruppe behält ihre eigene Auswahlfläche,
Vorschaumatrix und Schnittbegrenzung. `select_features` bleibt der Adapter für
Merkmalskennungen am führenden Körper; Neuauswertung und Abwahl räumen alte Paare ab.
Getrennte Konturaktoren sind ebenfalls ihrem Körper zugeordnet: Freier Zug,
Gizmo und Skalierwürfel gleichen ihre Matrix und Position vor dem vorhandenen
Gestenbild ab, auch ohne Merkmalsanzeige. Unveränderte Werte werden nicht erneut
gesetzt; Rücknahme und Szenenabbau nehmen die Konturen vollständig mit.
Die gespeicherten Originalanker bleiben unverändert; Rücknahme, Kamerawechsel
und die nächste Szene lesen denselben jeweils sichtbaren Aktorstand.
Der freie Körperzug wechselt bei genau einem gewählten Körper eine Merkmalsauswahl
vor seiner Vorschau über `objectPicked` auf die Körperstufe. Eine gemischte
Mehrfachauswahl bleibt vollständig erhalten; der gemeinsame Anschluss bestätigt
dieselbe Körpermenge, die die Vorschau bewegt;
das gezielte Merkmalwerkzeug behält seine eigene Merkmalsoperation.
Verbindungen reichen bis zum Textanker und liegen unter dem deckenden
Beschriftungsfeld; die größere Kollisionsreserve begrenzt keine sichtbare Linie.
Die Schutzschraffur berücksichtigt dieselben Schnittgrenzen
auch bei ihrer zusätzlichen Anhebung gegen Flimmern.
Flächenmarker in Schnitt- und Schichtansichten wählen einen Kandidaten aus dem
sichtbaren Rest eines einzelnen Originaldreiecks. Die vektorisierte Zuordnung
verhindert Mittelpunkte im leeren Zwischenraum nichtkonvexer oder getrennter Reste.
Bohrungs- und Achsenmitten sowie die unbeschnittene Darstellung bleiben erhalten.

Ausdrückliches Einpassen zeichnet einmal über den gemeinsamen Viewport-Pfad.
Die interne Kamerarahmung zeichnet noch nicht: Szenenaufbau und Achsansicht
stellen erst ihren fertigen Zustand dar. Die Rahmung berücksichtigt die
gemeldete freie Kartenfläche und Gerätepixeldichte; perspektivisch zählen
alle acht Hüllquaderpunkte mit ihrer Tiefe. Eine Karte zu öffnen verändert
den gewählten Ausschnitt im Körpermodus nicht.

**Panels und Leisten**

`panels.py` (die drei Panels links, Prüfbericht rechts, §2.5) ·
`selection_operations.py` (Körperoperationen in einer eigenen Karte unter der
von Bericht und Chat — beide Karten stapelt `overlay.CardColumn` als eine
Zone; einmal aus dem Register aufgebaut, bei Auswahlwechseln nur
nachgeführt) ·
`tool_strip.py` · `analysis_bar.py` · `section_bar.py` · `split_bar.py` ·
`transform_bar.py` · `explode_bar.py` · `sculpt_bar.py` · `pose_bar.py` ·
`scale_widget.py` (der Würfel am Körper) · `slot_handle.py` (die zwei Knöpfe am
Loch — bestätigt wird im Merkmalfenster) ·
`facts.py` (was das Teil kostet, während man daran baut)

Die Legende in `analysis_bar.py` verteilt bei vielen benannten Kartenstufen
ihre Beispiele über den gesamten Farbbereich und nennt die Zahl ausgelassener
Stufen. Jeder Beispielname behält exakt die Farbe seiner ursprünglichen Stufe.
Bei kontinuierlichen Karten stammen Farbraum und inverse Skalenwerte aus
`AnalysisMap`: Die Krümmung verwendet eine logarithmisch abgestufte Farbrampe,
deren Legende weiterhin physische Millimeterwerte nennt und die Abstufung
ausweist. Der Viewport reicht die transformierten Werte an den Renderer;
Messwerte, Schwellwerte und Hervorhebungen bleiben unverändert.

**Dialoge**

Operationsdialoge gehören dem Projekt, in dem sie geöffnet wurden. Ein
Projektwechsel schließt sie und verwirft ihre Vorschau. Varianten wechseln
Schema, Felder und Eingänge gemeinsam; gemeinsame Werte gehen mit,
varianteneigene Werte bleiben beim Zurückwechseln erhalten.
Die alten Formularzeilen werden dabei herausgenommen und verborgen, bleiben
bis zum vollständigen Neuaufbau lebend und werden anschließend über
`deleteLater()` freigegeben. Komplettierer werden vorher von ihren Feldern gelöst.
Ganze Zahlen benutzen denselben Verweis-/Formelweg wie Maße, außer wenn die Anzahl schon
beim Planen die Ergebniskennungen bestimmt. Quellenmerkmale bleiben an ihren
Eingangskörper gebunden, Klickziele tragen Körper und Merkmal gemeinsam.
`schemaChanged` bindet neu erzeugte Skizzenfelder wieder an den Raumeditor.
Der Feldname reist durch den Raumeditor zurück; mehrere Skizzen derselben
Operation ersetzen einander nicht. Bestehende Zeichnungen behalten ihre Ebene.
Freistehende Prüfkörper benutzen im Katalog `creation_name()` und brauchen
keinen Träger. Gemischte Bausteine zeigen `PlacementTool.addition` zusätzlich
zum Schnittkörper, mit gemeinsamer Platzierung und gemeinsamem Abbau.

| Datei | Besonderheit |
|---|---|
| `op_dialog.py` | **Wird aus dem Parameterschema erzeugt** (§10, §2.4). Kein Dialog wird von Hand gebaut — wer einen tippt, hat das Register umgangen |
| `dialogs.py` | Fragen und Fehler (§2.7), Freischaltung mit Online- und Dateiweg sowie freiwillige Förderung |
| `print_settings_dialog.py` | Druckeinstellungen, Analyse des Ausgabeumfangs im tatsächlichen Schichtraster, slotbezogene Empfehlungen und Slicer-Übergabe (§29) |
| `print_disclosure.py` | Der Hinweis davor: dass diese Werte Erfahrungswerte sind und mit einer 3MF mitreisen — und die Wahl, ob sie das sollen (§29) |
| weitere | `settings_dialog` · `generate_dialog` (Weg 3) · `recipe_dialog` · `variants_dialog` · `comfy_dialog` · `install_dialog` · `support_dialog` · `update_dialog` · `changes_dialog` |

**Editor**

`sketch_editor.py` (**rund 4 800 Zeilen** — §30.1, Stufe zwei)

**Agent**

`chat.py` (§26.3, §2.5) · `snapshots.py` (Ansichten für den Agenten) ·
`remote_server.py` (MCP im Fenster)

## P0-08 — KI-Hinweis an der Sendegrenze

`ai_disclosure.py` hält den sichtbaren Informationstext, den lokalen
Anzeigenachweis und die gemeinsame Sperre zusammen. `ensure_ai_disclosure`
steht vor jedem echten LLM-Modellaufruf: im Hauptfenster unmittelbar vor
`Session.propose_async`, im Chat-Einrichtungsdialog vor den beiden echten
Aufrufen der Ollama-Werkzeugprobe. Erst ein vollständig aufgebauter,
erreichbarer und zugänglicher Dialog öffnet den genau danach angeforderten Zug;
Zurück, Escape,
Schließen, ein unbekanntes Backend sowie Darstellungs- oder Speicherfehler
senden nichts.

Der Anbietertext folgt der tatsächlichen Nutzlast aus `agent/context.py` und
`session.py`, nicht einer verkürzten Produktbeschreibung: Für Anthropic nennt
er neben der aktuellen Nachricht den textlichen Szenensteckbrief,
Prüfbericht, begrenzten Chatverlauf, Anweisungen/Regeln/Werkzeugschemata und
die bei bildfähigen Modellen automatisch gerenderten Szenenansichten. Nicht
übertragen werden die Projektdatei und die Netzgeometrie selbst.

Ollama ist nicht gleichbedeutend mit „lokal“: Der eingetragene Dienst darf auf
einem zweiten Rechner liegen. Der Hinweis zeigt deshalb die von Geheimnissen,
Pfad, Abfrage und Fragment bereinigte Zieladresse und unterscheidet Loopback
von einem entfernten Ziel. Der entfernte Text nennt denselben Arbeitskontext;
die Werkzeugprobe nennt ihren festen technischen Auftrag ohne Projekt- oder
Chatinhalt.

Der Nachweis besteht ausschließlich aus Textfassung, Backend-Typ,
Zielklasse/Zieladresse und UTC-Zeitpunkt in `UiSettings`. Er reist nicht im
Projekt; Text-, Anbieter-, Local→Remote- und Hostwechsel schließen die Sperre
wieder, und die Einstellungen können ihn zurücksetzen. Weil `ChatPanel` vor
seinem Signal leert, hält es bis zur Entscheidung den unbearbeiteten
Eingabetext: Bei einem Abbruch kommen auch Leerraum und Zeilenumbrüche
vollständig und markiert ins Feld zurück.

## §29 — der Bericht kommt vor der Datei

`_ExportWorker` hört im ersten Lauf an der Prüfung auf: Findet sie etwas ab
`warning`, meldet er es über `checked` und endet.
`MainWindow._export_checked` legt die Befunde in den Prüfbericht, rückt ihn
nach vorn und fragt über `dialogs.confirm_export`; ein Ja startet einen
zweiten Lauf mit **demselben** Bericht (`checked=`), statt ein zweites Mal zu
prüfen.

`_start_export` sammelt die Auswahl einmal und kopiert Dokument und lokale
Einstellungen für diesen Auftrag. Die Bestätigung bekommt den geprüften
Arbeiter; dessen `after_check` reicht Körper, Quellen, Profile, Ziel und
Bericht gemeinsam an den Schreibdurchgang weiter. Ein Auswahlwechsel, eine
neue Auswertung oder ein anderes Projekt im Fenster verändern diese Datei
nicht. Ein ausdrücklich neu gestarteter Export liest den heutigen Stand.

Das gemerkte Exportformat wird gegen die aktuelle Auswahl geprüft. Besteht
sie nur aus Netzen, fällt ein gemerktes STEP für den Dialog auf 3MF zurück;
Dateiendung und Namensvorschlag folgen diesem angebotenen Format. Ein
Abbruch des Dialogs lässt die Projektpräferenz stehen, sodass eine spätere
B-Rep-Auswahl weiterhin STEP vorschlägt.

Der Arbeiter des ersten Laufs ist während des Dialogs noch am Auslaufen, und
der modale Dialog dreht die Ereignisschleife weiter. `_export_worker_done`
räumt ausschließlich sein eigenes Feld; `_run_export` verbindet beide
Durchgänge mit derselben Fortschritts- und Fehlerbehandlung.

**Die Szene reist mit** (`scene=`, `document=`), weil zwei der fünf Fragen aus
§29 in keinem einzelnen Körper stehen — eine verletzte Passung und eine Wand
unter der Mindeststärke. Dasselbe gilt für die Übergabe an den Slicer:
`_PlateJob` trägt beide Felder, und ihr Bericht war bis dahin um diese zwei
Zeilen ärmer.

## §29 — was die Datei mitnimmt

`print_disclosure.py` steht vor dem ersten Öffnen der Druckeinstellungen und
sagt dreierlei: Die Werte sind Erfahrungswerte; sie reisen mit einer
gespeicherten 3MF und mit der Übergabe an den Slicer; für Ergebnis und
Schäden gelten die Nummern 10 und 11 des Lizenzvertrags. Anders als der
KI-Hinweis sperrt er nichts — hier verlässt nichts das Gerät, und die Wahl
darunter entscheidet erst über das Speichern.

Drei Stellen tragen sie: Der Hinweis fragt einmal je Textfassung, der
Umschalter im Kopf des Druckdialogs zeigt und ändert sie, und
`settings_for_export()` beantwortet damit die Frage, was eine Datei
mitbekommt. Der Merker steht in `UiSettings` (Fassung und UTC-Zeitpunkt) und
reist nie in einer Projektdatei.

**Der Fehler dahinter, weil er die Bauart erklärt:** Bis zum 03.09.2026 trug
**jede** exportierte 3MF Solidons Werte. Der Kern konnte es anders
(`writer._plate_settings` gibt bei fehlenden Einstellungen ein leeres
Verzeichnis), aber die Anwendung löste an ihrer eigenen Stelle auf — der
Ausgang war zugemauert. Dazu schrieb schon das **bloße Öffnen** des Dialogs
die Werte ins Dokument, denn `set_print_settings` lief nach `exec()` ohne
Rückfrage, und der Dialog hat nur „Schließen". `PrintSettingsDialog.has_changes`
misst deshalb am Anfangszustand und nicht an einer Liste von Knöpfen.

**Bibliothek**

`catalog.py` (Bausteinkatalog, §24.3) · `filament_picker.py` (Farbe und Name
statt einer Zahl von 0 bis 7)

**Ein eigener Baustein lässt sich wieder öffnen** (RM-147 E6): *Zum Bearbeiten
öffnen …* steht neben *Aus Bibliothek entfernen* und gilt derselben Menge —
eigene und eingelesene Rezepte, sonst ist der Knopf unsichtbar.
`MainWindow._edit_part` fragt wie beim Öffnen einer Datei, ob das offene
Projekt weg darf, und `Session.open_draft` macht daraus ein namenloses
Projekt; die Herkunft steht als `Session.draft_origin` am Dokument und fällt
mit ihm (`_reset_for`). Der Rezeptdialog belegt daraus Titel, Gruppe, Lizenz,
Autor, die freigegebenen Maße und die benannten Stellen vor — dann heißt sein
Knopf *Baustein ersetzen*, und ein anderer Titel legt einen zweiten an.

**Ein Paar ist kein Baustein, sondern zwei** (RM-147 E1): *Gegenstücke setzen …*
steht deshalb im Menü *Bausteine* neben dem Katalog und nicht darin.
`counterpart_dialog.py` fragt genau zwei Dinge — welches Paar und wie groß —,
denn das Wo steht schon fest, wenn er aufgeht: Es sind die beiden Stellen, die
im Objektbaum markiert sind (`MainWindow._counterpart_targets`). Die Maßfelder
baut er aus dem **Bausteinschema** (`PartSpec.params.spec()`); welche davon
gemeinsam sind, sagt `Pair.shared` im Kern. Ein Paarwechsel tauscht sie
vollständig — was stehenbliebe, verspräche eine Wirkung, die die andere Hälfte
nicht kennt.

`Session.create_counterpart` übernimmt beide Hälften und hängt nach der
Auswertung die Passung an dieselbe Transaktion. Erst danach läuft die
gemeinsame Änderungsnachbereitung: Das Projekt gilt als ungespeichert, die
automatische Sicherung erfasst das Paar, und die Auswertung prüft seine
Passung mit. Ein Undo nimmt beide Hälften und die Passung zusammen zurück.

**Der Menüeintrag beantwortet die Frage selbst**, statt sie nach dem Klick als
Dialog zu stellen: Ohne zwei markierte Stellen an zwei Teilen ist er gesperrt
und trägt den Grund. Beide Stellen — Riegel und Fehlerdialog für den Weg über
Palette und Kürzel — lesen ihn aus `main_window.counterpart_needs_two()`; zwei
Formulierungen derselben Auskunft laufen auseinander, und hier stünden sie
nacheinander vor demselben Kunden. Zurückgestellt wird der eigene
Erklärungssatz über `_pick_hint`, dieselbe Bauart wie bei *Formen* und
*Skelett*: Wer den Hinweis beim Freigeben auf `""` setzt, macht aus einem
bedienbaren Eintrag einen stummen.

**Und die Vorschau geht denselben Weg wie beim Operationsdialog** (§18.7):
`counterpart.drafts_for` sagt, was entstünde, `Session.preview_async` rechnet
es im Arbeiter, `_show_preview` zeigt es. Der Dialog rechnet dabei nichts — er
meldet über `valuesChanged`, dass Paar oder Maß sich bewegt haben, und der
Zeitgeber im Fenster entprellt auf 300 ms. Ein Paar ist die Lage, in der eine
Vorschau am meisten wert ist: Ob die zwei Hälften zueinander passen, sieht man
ihnen an und den Zahlen nicht. `_clear_preview` steht im `finally` — die
Vorschau gehört dem Dialog und geht mit ihm, gleich ob übernommen oder
abgebrochen.

Ein `InstallDialog` lässt eine begonnene Installation beim Schließen
geordnet auslaufen und zeigt diesen Zustand. Er beendet nur das Warten auf
einen gestarteten Fremddienst; den Dienst selbst besitzt Solidon nicht.
`MainWindow.wait_for_workers` bezieht alle eigenen Installationsdialoge ein,
damit auch das Schließen der ganzen Anwendung denselben Vertrag einhält.

**Bausteine setzt man auf eine Fläche, nicht in ein Loch.** Der Knopf
*Bausteine* am Fuß des Auswahlfensters steht nur ohne Merkmal und an einer
gewählten Fläche (`SelectionOperations.set_context`); an einer Bohrung, einer
Verrundung oder einem Zapfen führte er in einen Katalog, aus dem nichts an
diese Stelle passt — unter einer Liste, für die man erst scrollen muss.

Merkmalsanalyse und Bausteinkatalog bleiben getrennte Wege an der rechten
Seite. Das Auswahlfeld führt zu beiden und baut keines von beiden nach. Seine
Operationen stammen aus dem Operationsregister — Körperoperationen über
`body_operations`, die Merkmalshandlungen über `feature_operations` aus
demselben `applies_to`, aus dem der Doppelklick im Baum seine erste passende
Handlung nimmt. **Das Auswahlfeld ist für diese Handlungen der einzige Ort**
(`PANEL_CATEGORIES`, `.claude/rules/oberflaeche.md`): Die Menüleiste trägt
nur noch, was keine Auswahl braucht, und das Kontextmenü an Körper und Merkmal
keine Operationen. Sie verwenden dieselbe Freigabe wie Menü und Palette und
gehen ausnahmslos durch `MainWindow.launch_operation`, damit Gesten-Editoren
und Undo erhalten bleiben. Seine Gruppen sind einklappbare Abschnitte
(`panels.collapsible`), sein Knopf *Bausteine* ein Hauptknopf.

Welche Handlungen **vorn** stehen, beantwortet `quick_names(bodies,
feature_kind)`: bei mehreren Körpern die Booleschen, bei einem einzelnen
Bohren, Aushöhlen und Teilen, an einem gewählten Merkmal die seiner Art —
das Merkmal hat Vorrang vor der Menge. Die Knöpfe dieser Lagen entstehen
einmal (`all_quick_names`) und werden nur ein- und ausgehängt; was oben
stehen kann, steht nicht auch in der Suchliste darunter.

**Was aus einem Baustein kam, meint den Baustein.** Ein Schlüsselloch
bringt zwölf Merkmale mit — zwei Bohrungen, **zehn Verrundungen** und die
Fläche, auf der es sitzt. Die Verrundungen tragen für sich keine einzige
Handlung (`REGISTRY.for_feature("fillet")` ist leer), und an der Fläche
standen die Handlungen einer Fläche: Bohren, Tasche, Fläche ziehen. Wer
eine Schlitzkante anklickt, hat aber das Schlüsselloch gemeint (Befund
Robert, 10.09.2026). `MainWindow.part_step_of` fragt deshalb die
Provenienz und die Kategorie des Schritts — `parts`, nicht eine Namensliste,
die beim nächsten Baustein schwiege —, und `FeaturePanel.show_part` zeigt
statt der Merkmalszeilen die drei Handlungen des Bausteins: Maße ändern,
verschieben, entfernen (`perceive.actions.part_actions`).

**Und sie gelten dem Schritt, nicht dem einzelnen Merkmal.**
`resize_feature` auf die runde Tasche gesetzt bohrte sie auf und ließe den
Schlitz stehen. Was die Größe wirklich ändert, ist die Schraubengröße im
Schritt. Die Werte kommen von dort und gehen dorthin zurück
(`stepChangeRequested`, `stepRemoveRequested`) — **nicht** über
`operationRequested`, das bei jeder Korrektur ein zweites Schlüsselloch
über das alte legte. Aus gemessenen Maßen ließe sich ohnehin nichts
zurückschreiben: Aus zwei Durchmessern käme keine Schraubengröße zurück.

**Im Baum gilt dasselbe.** Das Bausteindach wählt seine zwölf Kinder mit
(`selected_features`), und zwölf Merkmale sind für eine Passung zehn zu
viel: Dort stand „Wählen Sie genau zwei aus", wo jemand gerade ein Ding
angeklickt hatte. `_common_part_step` fragt, ob die **ganze** Auswahl aus
einem Schritt stammt — eine Bohrung des Schlüssellochs und eine fremde
daneben sind zwei Dinge und kein Baustein.

**Und was das Merkmalsfenster darüber schon als Feld zeigt, steht hier gar
nicht.** `_shown_as_fields()` liest `perceive.actions.ACTION_ORDER` — dieselbe
Liste, aus der `FeaturePanel` seine Zeilen baut —, und `quick_names` wie
`_fits_the_level` schneiden sie heraus. An einer Bohrung standen sonst
*Bohrung ändern*, *Merkmal drehen* und *Merkmal verdoppeln* zweimal im selben
Fenster: oben mit dem gemessenen Wert und einem Knopf, darunter als Knopf, der
denselben Weg noch einmal anbietet. Der Kegel hat deshalb eine eigene Zeile in
`QUICK_FEATURES` — seine einzige verbleibende Handlung ist *Senken*, und ohne
den Eintrag stünde sie an keiner der beiden Stellen.

### Das Merkmalsfenster hat einen Knopf, nicht fünf (10.09.2026)

Vier bis fünf Handlungen stehen an einer Bohrung untereinander, und jede trug
ihren eigenen Knopf: fünf Zeilen, die fünfmal dasselbe sagten. Es ist jetzt
**einer unten**, und er führt die Handlung aus, an der zuletzt jemand einen
Wert geändert hat (`FeaturePanel._arm`, `_runs`). Vier Entscheidungen daran:

* **Er heißt „Übernehmen"** und trägt nicht den Handlungstitel — der wechselte
  sonst mit jedem Klick ins nächste Feld. Welche Handlung gemeint ist, steht
  über ihm; für den Bildschirmleser trägt er sie als zugänglichen Namen (§19.1).
* **Er steht wirklich unten.** Er entsteht beim Aufbau des Panels und liegt
  damit vor allem, was `show_feature` später einfügt; `_settle_apply` hängt ihn
  und den Haken ans Ende, nachdem alle Zeilen stehen.
* **Der Haken „Auf alle N gleichartigen anwenden" steht direkt darüber** — auch
  er einer statt vier, und die Zahl wechselt mit der scharfen Handlung, denn
  die Gruppen sind je Handlung verschieden. Ohne Geschwister ist er weg statt
  ausgegraut, und er verliert dabei seinen Haken: ausgeblendet auf „an" griffe
  er wieder, sobald eine Handlung mit Gruppe drankommt.
* **Er trägt die Akzentfarbe** (`style.make_primary`) samt der Schriftfarbe
  darauf, und halbfett daneben — Bedeutung nie allein über Farbe (Regel 18).

**Die Erklärung sitzt am „i" neben der Überschrift.** Drei Zeilen Fließtext je
Handlung füllten das Fenster; der Absatz steht jetzt im Tooltip eines kleinen
Zeichens (`_explain`, `_extend_explanation`). Drei Quellen speisen ihn in
dieser Reihenfolge: der Satz zur Lage (`note`), der Grund der Handlung, und der
`doc`-Satz aus dem Register — der letzte trägt immer, denn jede Operation hat
einen (Regel 4). **Ein `QToolButton` und kein `QLabel`**: Ein Label zeigt
seinen Tooltip nur, solange die Maus genau darauf steht, und achtzehn
Bildpunkte trifft niemand zuverlässig. Für den Bildschirmleser hängt der Text
an der **Überschrift** — ein Tooltip wird nicht vorgelesen.

**Und ein Strich trennt die Handlungen** (`style.rule`). An einer Bohrung
folgen auf drei Zahlenfelder wieder drei; wer nicht auf die Überschriften
sieht, liest sie als eine Reihe.

**Eine Beschriftung, die nicht in ihre Spalte passt, bricht um** — Qt schnitte
sie sonst zu „Bohrung versch…", und ein abgeschnittener Titel nennt seine
Handlung nicht mehr. `_wrap_label` misst gegen die Schrift, mit der wirklich
gezeichnet wird, und holt das Beiwerk des Knopfes aus der Differenz zu seinem
Wunschmaß; höchstens zwei Zeilen, darunter bleibt Qts Auslassung. Der
ungebrochene Titel steht als `operationTitle` am Knopf, weil `text()` sich
ändert und die Suche darunter den ganzen Titel braucht.

Die Kopfzeile nennt keine globale Materialzusage. Sie liest Körpermaterialien
und die über `mesh.slot_indices` tatsächlich belegten Materialslots der
aktuellen Auswertung, unterscheidet Slotname, Materialart und Farbcode und
zählt mehrere Filamente. Eine leere Zuordnung bedeutet vollständig Slot 0;
ungenutzte Definitionen zählen nach einem Übermalen nicht weiter. Kurztext und
Tooltip teilen dieselbe Erhebung, damit große Netze ihre Flächenzuordnung nur
einmal je Aktualisierung durchlaufen. Bei mehreren steht die
klare Anzahl in der knappen Leiste, die vollständige Liste im Tooltip und im
zugänglichen Namen. Der Druckerknopf öffnet die Druckeinstellungen des offenen
Projekts. Ein Wechsel
dort behält Projektmaterial, Slotprofile, Farben und SlotOverrides; Vorgaben
für neue Projekte sind ein eigener Weg in den Einstellungen.

**Erscheinung**

`style.py` (Stylesheet, Typografie-Skala, Abstandsraster, §19.3) · `theme.py`
(hell und dunkel) · `window_chrome.py` (die Titelleiste trägt die Farben der
Anwendung — Windows malt sie weiter, es bekommt nur gesagt, in welcher Farbe;
ein Wächter am Ereignisstrom, damit kein Dialog vergessen wird) ·
`palette.py` (**Farbe trägt nie allein Bedeutung**,
§19.1) · `icons.py` · `motion.py` (Bewegung an einer Stelle, nicht an
zwanzig) · `labels.py` (kurze Texte, auf die sich mehrere Teile einigen)

Beim Ablösen einer Auswahlblende übernimmt der Renderer alle noch offenen
Farbziele der vorigen Blende. Sonst bleibt bei einer schnellen
Mehrfachauswahl der zuerst gewählte Körper auf seiner Zwischenfarbe stehen.
Eine unveränderte Auswahl startet keine neue Animation.

`MainWindow.release` wartet auf Arbeiter und trennt die Sitzung. Der
pygfx-Renderer hat eine eigene Lebensdauer: Anwendung und Tests schließen ihn
ausdrücklich, solange seine Canvas lebt, und stellen erst danach Qts
aufgeschobene Fensterlöschung im Hauptthread zu. Ein Test-Pin schützt ein neu
gebautes Hauptfenster oder einen einzelnen Viewport nur bis zu genau diesem
geordneten Teardown; Fenster werden nicht über mehrere Tests angesammelt.
Eine `WorkerLeash` hält ihren Fensterbesitzer nicht zurück: Der Besitzer hält
die Leine bereits, alle Zeitgeber gehören dem langlebigen Keeper und die
Fertigrückrufe verwenden schwache Verweise. Damit entsteht um Qt-Fenster kein
Python-Zyklus, dessen Abbau in einen späteren Worker- oder Widgetaufbau fällt.

**Hilfe und Bedienung**

`manual_window.py` · `tour.py` · `shortcuts_window.py` ·
`shortcut_schemes.py` (zwei Belegungen, eine Quelle) · `command_palette.py`

**Navigationstasten gehören dem fokussierten Inhalt.** Der gemeinsame
`NavigationKeys`-Filter schützt Pos1, Ende, Bild auf und Bild ab in Listen,
Bäumen, Text- und Zahlenfeldern sowie Reglern (`QAbstractSlider`). Beim
Fokuswechsel zur Ansicht gelten wieder die Fensterbefehle; Ziffern der
Darstellungsarten bleiben auch im Inhalt Fensterbefehle.

Der Objektbaum wertet `customContextMenuRequested` in den bereits gelieferten
Viewport-Koordinaten aus. Eine zweite Umrechnung verschiebt den Treffer um die
Kopfzeilenhöhe. Text- und Zahlenfelder behalten normale Zeicheneingaben vor
fensterweiten Einzeltasten-Kürzeln; die Linux-Auslieferung verwendet dafür den
geprüften X11-/Xwayland-Pfad.

Der Selbstversand des Supportberichts verwendet im Flatpak asynchron
`Email.ComposeEmail` über QtDBus und übergibt Betreff und Inhalt unkodiert als
Portalwerte. Außerhalb des Flatpaks bleibt `QDesktopServices` mit `mailto:`.
Der Qt-6.11-Pfad über eine vorab kodierte `mailto:`-Adresse ist ausgeschlossen,
weil `PrettyDecoded` Prozentfolgen erneut auswertet.
Vor dem Methodenaufruf abonniert der Dialog `Request.Response` über seinen
`handle_token`. Erfolg, Abbruch und Fehler beenden den Ablauf; beim Schließen
trennt der Dialog die Signalverbindung und schließt den Portal-Request.

**Einstellungen** `settings.py` · `survey.py`

## Grenzen

- **Keine feste Zeichenkette** — alles über `tr()` (Regel 20).
- **Das Handbuch beantwortet fremde Ressourcen mit leeren Daten.** `None`
  würde Qts eigenen Dateileser freigeben. Nur `figure:` wird über den lokalen
  Abbildungskatalog aufgelöst; Links bleiben eine getrennte Klickentscheidung.
- **Eine Kartenbewegung endet mit ihrem Qt-Objekt.** Die Animation verwendet
  `DeleteWhenStopped`, auch beim Ersetzen einer noch laufenden Bewegung.
- **Sprachabhängige Qt-Formate lesen die aktive Solidon-Sprache.**
  `QLocale()` ohne Argument folgt der Prozesssprache; für ausgeschriebene
  Datumswerte deshalb `QLocale(get_language())` verwenden und alle
  ausgelieferten Sprachen am gerenderten Fenster prüfen.
- **Berichtshandlungen lesen ihren Zielkörper aus Befund oder Dokument.** Eine
  aktuelle Auswahl ist kein Ersatz. „Reparieren und erneut versuchen“ steht
  nur am aktuell angehaltenen Netzschritt mit lebenden Eingängen oder an einem
  ausdrücklich benannten, noch vorhandenen Körper. Der Knopf wird nicht erneut
  angeboten, wenn unmittelbar davor bereits alle Eingänge in derselben aktiven
  Transaktion repariert wurden, und sperrt sich beim ersten Klick bis zum neuen
  Ergebnis. Berichtshandlungen stehen vollbreit untereinander, damit auch
  längere Übersetzungen in der schmalen Karte vollständig bleiben.
- **Gleiche Meldungen werden eine gezählte Zeile, die Zahl davor in
  Klammern** (Robert, 11.09.2026; `REPORT_BUNDLE_FROM = 2`). Gleiche Kennung,
  Schwere, Meldung, Herkunft, Schritt und Handlungen bilden das Bündel —
  Körper, Ort, Merkmale und Werte **nicht mehr**: „(9) Ausrichtung über die
  Schichtanalyse gesucht." statt neun Zeilen. Was die Mitglieder unterscheidet,
  trägt die Zeile anders: die Körper als Liste (`_BODIES_ROLE`), Name und
  Werte je Mitglied im Tooltip, ein gemeinsamer Körper sichtbar an der Zeile.
  **Der Klickvertrag bleibt**: Eine Zeile über mehrere Körper wählt beim Klick
  alle (`bundleActivated` → `_on_bundle_activated` → `ObjectTree.select_objects`),
  nie den ersten zufälligen; ihre Handlung fragt, für welche Körper sie
  gelten soll (`BodyChoiceDialog`) — und geht dann einen von drei Wegen
  (`_run_action_for`): eine **Operation** wird ein Schritt je Körper in einer
  Transaktion (`actionOnBodies`), eine Handlung **an einem Körper**
  (`_PER_BODY_ACTIONS`) läuft je Körper mit dessen eigenem Befund
  (`_MEMBERS_ROLE`, nie mit dem des ersten), alles andere läuft einmal. Sie
  trägt keinen Ort und keine Merkmale, wo die Mitglieder verschiedene haben;
  ohne Körper (die Gegenprobe aus dem G-Code für Material und Zeit) heißen
  ihre Mitglieder im Tooltip *Einträge*, nicht *Objekte*. Der Kerntext bleibt
  kanalneutral — Agent, CLI und Datei lesen jeden Befund einzeln; nur das
  Panel zählt.
- **Und der Objektbaum bündelt nach derselben Regel wie der Prüfbericht.**
  Erkannte Merkmale mit gleichem Namen **und gleichem Maß** stehen ab
  `BUNDLE_FROM` unter einem zugeklappten Dach („Hohlkehle (17) · R13,98 mm").
  Der Name allein reichte dafür nicht: Ein Schlüsselloch bringt zehn
  Hohlkehlen mit *verschiedenen* Radien mit, und die verschwanden hinter einer
  Zeile, die Gleichartigkeit behauptete, wo keine war (Befund Robert,
  09.09.2026). Seit der Schlüssel das Maß enthält, tragen alle Kinder eines
  Dachs dasselbe — deshalb steht es jetzt in der Maßspalte, statt leer zu
  bleiben. Was aus einem Baustein kam, gruppiert
  weiter nach seinem Schritt; die zwei Dächer schließen einander nicht aus.
  Gemessen an `build_tray_v3.step`: 234 erkannte Merkmale, rund fünfzig
  sichtbare Zeilen „Hohlkehle R13,98 mm" untereinander, die die linke Spalte
  füllten und Parameter und Verlauf hinausdrückten. Der Bericht daneben zeigte
  dieselbe Menge längst als eine Zeile. `_restore` klappt das Dach auf, wenn
  das gewählte Merkmal darin liegt — sonst wäre ein Klick im Viewport auf eine
  Verrundung wieder ins Leere gegangen.
- **Ein Bausteindach über einer einzigen Zeile entfällt.** „Schraubenloch mit
  Senkung" trägt genau ein direktes Kind — die Bohrung, an der die Senkung
  schon hängt —, und die Dachzeile wiederholte damit nur, was darunter steht;
  angeklickt meinte sie den ganzen Körper, und im Auswahlfenster standen alle
  Körperoperationen. Der Weg zum Schritt geht dabei nicht verloren: Er steht in
  `Feature.created_by`, und Doppelklick wie „Diesen Schritt ändern" lesen ihn
  von dort, wenn `_STEP_ROLE` fehlt.
- **Ein zusammenhängender Bohrungshohlraum ist ein vollständiger Ast.**
  Bohrung, kegelige Übergänge und zylindrische Senkungen werden in der
  Reihenfolge von `perceive.relations.cavity_chains` ineinander gehängt; eine
  Kette mit drei Flächen darf nicht auf ein Paar gekürzt werden. Der Objektbaum
  fragt die Bulk-Auskunft genau einmal je `SceneObject`, damit die Randringe
  eines großen Netzes nicht für jedes Merkmal neu entstehen. Das
  Merkmalspanel reicht das `MeshData` optional bis `actions_for` durch:
  Aufrufer ohne Netz behalten die bisherige Paar-Auskunft, die Oberfläche mit
  Netz nennt auch bei der vollständigen Kette vorab das gemeinsame Versetzen.
- **Kurzlebige Warnungsmarken sind semantischer Ansichts-Zustand.** Ring und
  Beschriftung im nativen Renderer sind nur die Darstellung. Baut eine
  Analysekarte dieselbe Auswertung neu auf, werden beide aus Punkt, Text und
  Körper erneut gezeichnet, ohne die ursprüngliche Frist zu verlängern. Ist
  der Körper ausgeblendet oder liegt auf einer anderen gewählten Platte,
  bleibt auch seine Marke unsichtbar. Ein neues Auswertungsergebnis verwirft
  Zustand und Aktoren gemeinsam.
- **Keine Bestätigungsdialoge vor rücknehmbaren Handlungen** (Regel 19), mit
  der ausdrücklich gewünschten Ausnahme für das Löschen im Verlauf: Sie
  nennt mitbetroffene Schritte und den Rückweg über Strg+Z.
- **Keine Bedeutung allein über Farbe** — immer eine zweite Kodierung
  (Regel 18).
- **Höchstens neun Menüs, zwölf Zeilen je Menü, acht Werkzeuge, acht Felder
  vorn** — `tests/test_interface_limits.py` zählt nach.
- **Nichts rechnet im Qt-Hauptthread**, was länger dauert als ein Lidschlag
  (§2.8).
- **Der Raumvertrag schaltet keine Laufzeit-Introspektion über Qt-Typen.**
  `overlay.is_room_taker` prüft die vier aufrufbaren Methoden ausdrücklich;
  `isinstance` gegen ein `runtime_checkable Protocol` kann während eines
  Shiboken-Resize unvollständige Typdaten sehen und den Layoutlauf abbrechen.

## Zustandsbindung in asynchronen Bedienwegen

- Quellenarbeiter gehören zu genau einem Projekt und gegebenenfalls zu einem
  beim Start gewählten Zielkörper. Späte Signale dürfen weder einen später
  gewählten Körper bearbeiten noch den Zustand eines anderen Projekts melden.
- `Viewport.sceneApplied` bestätigt die tatsächlich aufgebaute Szene.
  Schnittgrenzen und Kandidatenmarkierungen werden danach synchronisiert,
  nicht schon beim Einreihen des Szenenaufbaus.
- Die Merkmals-Sammelwahl stammt aus `relations.alike_for_actions`: ein
  gemeinsamer Aufruf pro Auswahl liefert getrennte Gruppen je Handlung.
  Das Panel zeigt deren Belege und ungeklärte Zuordnungen; vor Anwendung wird
  die Gruppe am aktuellen Zustand erneut geprüft. Ein Schritt pro kanonischem
  Ziel bleibt zusammen eine Transaktion.
- Eine Normauskunft über eine Bohrungskette richtet sich nach dem engsten
  Abschnitt. Das Panel benennt Aufweitungen und verwendet im Hinweis dieselbe
  lokale Zahlenanzeige wie im Maßfeld. Unsichere Zuordnung wird erklärt, nicht
  als unbeantwortbare Frage formuliert.
- Druckergebnisse und laufende Druckaufträge tragen den Kontext aus Szene,
  Platte, Druckeinstellungen und Slicerprofilen. Änderungen entwerten die
  Ausgabe auch dann, wenn das fertige Arbeitersignal bereits eingereiht ist.
- Druckempfehlungen analysieren genau die gewählten Platten im tatsächlichen
  Schichtraster. Der kurzlebige Auftragsschnappschuss bewahrt keine Messung
  über Änderungen an Szene oder Raster hinweg. Angenommene Filamentwerte
  werden als identitätsgebundene Slotüberschreibung aus dem effektiven Profil
  aufgebaut; unberührte Herstellerwerte und ausdrückliche Abwahlen bleiben
  erhalten. Fehlende Messwerte werden nicht als passende Einstellungen gezeigt.
  Nicht übertragbare Filamentvorschläge bleiben mit Grund sichtbar, ohne
  Übernahmemöglichkeit. Fortschritt, Fehler und Abbruch prüfen dieselbe
  Anfragekennung wie der erfolgreiche Abschluss.
  Eine passende Überhangkalibrierung wird über `profiles.for_process` auf
  die tatsächlichen Druckwerte bezogen. Bei mehreren Materialien zählt für
  die gemeinsame Körperanalyse der strengste Winkel. Der Messwertspeicher
  enthält diesen Winkel und verwirft Ergebnisse bei geändertem Grenzwert.
- Die automatische G-Code-Gegenprobe vergleicht mit dem im Arbeiter
  eingefrorenen `SliceComparison` des ausgegebenen Auftrags. Sie liest dafür
  weder eine spätere Szene noch spätere Druckwerte. Ohne belegbare
  Materialaufteilung bleibt die betroffene Schätzung unbekannt.
- Analysekarten tragen eine Anfragekennung und ihre ausgewertete Szene bis
  zu Ergebnis, Größenabsage und Fehler. Ein Kartenwechsel entfernt die alten
  Farben sofort; auch ein Treffer im Cache oder „keine Karte“ entwertet
  verspätete Antworten des vorherigen Arbeiters.
- Der Wechsel aus dem modalen Druckdialog ins Filamentpanel schließt zuerst
  den Dialog; ein sichtbarer Rückweg öffnet die Druckeinstellungen wieder.
  Spulen werden über Name, Farbe, Materialprofil und Materialart unterschieden.
  Alte Werte ohne Materialbindung werden erst nach ausdrücklicher Übernahme
  und Bestätigung einer Spule zugeordnet.
- Die Kopfzeile der Druckeinstellungen bleibt auch bei 520 bis 620 Pixeln
  breit lesbar: Qualität und Mitgabe stehen zusammen, der Drucker erhält eine
  eigene volle Zeile, Filamentliste und Wechselknopf die dritte. Nur die
  Filamentliste darf umbrechen; Auswahlfelder und Handlungen werden nicht
  gekürzt oder aus dem Dialog geschoben.
- Session hält die Eigentumssperre ihrer namenlosen Wiederherstellung bis zum
  Projektwechsel oder echten Fensterschluss. Ein Oberflächen-Neuaufbau bei
  Sprachwechsel beendet dieses Eigentum nicht.

## Testen

Die Tests laufen offscreen; `tests/conftest.py` setzt `QT_QPA_PLATFORM`
selbst. Zwei Fallen, beide gemessen:

- **Qt lügt vor dem Anzeigen.** `setExpanded`, `isVisible` und `hasFocus`
  antworten falsch, solange nichts angezeigt wurde — ein Test kann grün
  bleiben gegen einen Zweig, der nie läuft.
- **Gesetzt heißt nicht gezeigt.** `QMenu` verschluckt Tooltips; ein Test über
  den Wert eines Hinweises sagt nichts über seine Sichtbarkeit.

Die Suite baut über siebenhundert Fenster mit Ansicht nacheinander auf und
reißt am Stück ab. Fensterdateien werden **je Prozess einzeln** gefahren —
siehe `CLAUDE.md` im Wurzelverzeichnis.
