---
paths:
  - "app/ui/sketch_editor.py"
---

# Regeln für die Zeichenfläche

Der Skizzenmodus. Die übrigen Oberflächenregeln — Texte, Wartezeit,
Barrierefreiheit, der Mauszeiger, die Ansicht — stehen in `oberflaeche.md`
und gelten hier unverändert mit.

Der Skizzeneditor (`app/ui/sketch_editor.py`) ist die zweite Ansicht, in der
gezeigt werden muss, was gleich passiert. Vier Zusagen, alle vier hatten
gefehlt:

**Was entsteht, hängt am Zeiger.** Linie, Kreis und Bogen zeigen ihre Vorschau,
bis der Klick sie festmacht. Ohne sie setzt ein Klick einen gestrichelten
Kreis, dann geschieht nichts, und beim zweiten steht plötzlich eine Linie da.

**Gefangen wird auf das Raster, ein vorhandener Punkt schlägt es.** Sonst risse
der Fang die Deckung auf, für die er da ist. Der Haken steht an der
Ebenenzeile, an ist die Vorgabe; ein Kreuz am Zeiger zeigt, wohin ein Klick
fiele. Derselbe Fang gilt beim Ziehen eines Punktes, sonst wäre er eine Zusage
bis zum ersten Nachbessern.

**Und es ist dasselbe Raster, das im Bild steht — eine Zahl für beides.** Hier
stand bis zum 24.08.2026 das Gegenteil („gefangen wird feiner, als das Raster
gezeichnet ist"), und das war nicht bloß eine Beschreibung, sondern der
Zustand: gezeichnet wurden 5 mm, gefangen wurde auf 1 mm, und gemessen landeten
vier von vier Klicks zwischen zwei sichtbaren Linien — (7,3 | −4,8) fiel auf
(7,0 | −5,0). Das Kästchen heißt „Am Raster fangen" und hat damit etwas
versprochen, das nicht eintrat.

`SketchPanel.follow_grid` nimmt deshalb die Weite, die `_redraw_sketch` gerade
gezeichnet hat, und gibt sie an Canvas **und** Feld. Zwei Dinge hängen daran:

* **Eine eingetippte Weite bleibt stehen** (`_pinned_step`). Danach folgt
  umgekehrt das Raster ihr — eine Zahl bleibt es in beiden Richtungen. Ohne
  die Unterscheidung überschriebe der nächste Zoomschritt jede Eingabe.
* **Das Setzen läuft unter `QSignalBlocker`.** `setValue` feuert
  `valueChanged`, und das hieße hier „der Nutzer hat etwas eingetippt": Der
  **erste** Zoomschritt hätte die Weite für immer festgenagelt.
* **Und die Null gibt sie wieder her.** `_pinned_step` wurde gesetzt und nie
  gelöst: Wer einmal eine Weite eintippte, sah bis zum Verlassen des Modus
  kein mitwachsendes Raster mehr — herausgezoomt eine Fläche aus Linien,
  hineingezoomt vier Linien im Bild. Das Feld beginnt deshalb bei null und
  zeigt dort „Automatisch" (`setSpecialValueText`). Eine Einstellung ohne Weg
  zurück ist eine Sackgasse, und §2.1 kennt keine.
* **Die Eingabe muss ins Bild.** `_snapping_changed` sendet `sketchChanged` —
  ohne das endete die Kette am Canvas, und der ist im Viewport-Modus
  unsichtbar. Gemeldet als „wenn ich das Raster anpasse ändert es sich im
  Viewport nicht": Feld und Fang trugen die neue Weite, das Bild die alte.
  Drei Zahlen für dieselbe Sache. Was der Viewport zuletzt **gezeichnet** hat,
  steht in `_sketch_step` — sonst wäre von außen nur zu zählen, nicht zu
  fragen.

**Wohin ein Klick fällt, muss im Bild stehen** (`Viewport.show_sketch_cursor`,
`sketch_cursor`). Gefangen wird auf das Raster, also landet ein Klick bis zu
einen halben Schritt neben dem Zeiger — bei 2 mm Raster elf Bildpunkte, bei
10 mm sechzig. Der Canvas zeigte dafür seit je ein Kreuz; seit die Zeichnung
im Viewport liegt (§30.1, P4), sieht das niemand mehr. Gemeldet als „die
Klicks sind wo anders als ich klick", und es war ausdrücklich **kein**
Koordinatenfehler: `devicePixelRatio` war 1.0, Qt- und Renderergröße des
Fensters (damals VTKs Interactor) stimmten überein, der Ereignisfilter saß auf
demselben Widget.

Drei Dinge daran, alle drei gemessen:

* **Der Ort kommt aus `pointer_target()`**, weitergereicht über
  `SketchPanel.pointerMoved`. Ihn im Viewport nachzurechnen wäre die zweite
  Zahl für dieselbe Sache — derselbe Fehler, an dem das Raster schon einmal
  auseinanderlief. Beim Auswahlwerkzeug gibt `pointer_target()` absichtlich
  die **rohe** Lage: Dort entsteht nichts, also ist die Mausstelle die
  richtige Antwort.
* **Die Größe steht in Bildpunkten** (`CURSOR_PIXELS`), nicht in Millimetern
  und nicht als Anteil der Rasterweite. Der erste Anlauf koppelte sie an das
  Raster; bei 10 mm sah das gut aus und bei 2 mm war das Kreuz zwei
  Bildpunkte breit — unsichtbar genau dort, wo man es am nötigsten hat.
  Gesehen hat das die Aufnahme, keine Rechnung.
* **Ein gesetzter Punkt bleibt kräftiger als die Marke**
  (`SKETCH_POINT_PIXELS >= CURSOR_PIXELS`, festgehalten in
  `tests/test_sketch_editor.py`). Er stand auf sechs Bildpunkten gegen zwanzig
  Spanne: Was schon existiert, sah leiser aus als das, was erst entstünde.
  Verwechseln kann man beide nicht — Kugel gegen Kreuz, zwei Formen und nicht
  zwei Farben.

Die Marke lebt in einer **eigenen** Actorliste (`_cursor_actors`): Sie hängt an
der Maus, die Zeichnung ändert sich beim Zeichnen. Zusammen geräumt flackerte
sie bei jedem Strich. Weg ist sie in `set_sketching` und nicht in
`finish_sketch`, sonst stünde dieselbe Zusage an zwei Stellen — **und zwar bei
jedem Aufruf, nicht nur bei `None`**: Ein Ebenenwechsel geht durch dieselbe
Methode mit einem neuen Rahmen, und die alte Marke blieb sonst auf der vorigen
Ebene im Raum stehen, bis die Maus sich das nächste Mal bewegte.

**Und ein Zeigerschritt, der nichts ändert, zeichnet nicht.** Das ist die
Hälfte, an der die Sache steht, und sie ist am gebauten Fenster gemessen:

| | Kosten je Aufruf |
|---|---|
| `show_sketch_cursor`, Marke wandert | 6,9 ms |
| davon `pixels_per_mm` | 0,004 ms |
| `_sketch_hit` zum Vergleich | 0,006 ms |
| Marke bleibt, wo sie ist | **0,004 ms** |

Bei sechzig Mausereignissen in der Sekunde sind 6,9 ms **41 % eines Kerns** im
Qt-Hauptthread. Teuer ist weder die Rechnung noch der Actor, sondern
`render()` — das Netz einmal anzulegen und nur seine Punkte zu tauschen brachte
gemessen nichts (6,95 gegen 6,92). Was hilft, ist die Eigenschaft der Marke
selbst: Sie sitzt am **gefangenen** Ort und ändert sich zwischen zwei
Rasterpunkten nicht. Verglichen wird Ort **und** Maßstab — beim Zoomen bleibt
der Ort gleich, und die Größe müsste sich ändern.

**Die Null im Rasterfeld kostet die Untergrenze**, wenn man sie nicht
festhält. Qt setzt den Sonderwert immer auf das Minimum, das Minimum musste
also auf null — und bei zwei Nachkommastellen nahm das Feld danach 0,01 mm an.
`LEAST_SNAP_MM` hebt beim Eintippen an, statt abzulehnen: Ein Feld, das eine
Eingabe verschluckt, ohne es zu zeigen, ist schlimmer als eines, das sie
berichtigt.

**Gemessen wird erst, wenn es ein Bild gibt** (`LEAST_VIEW_PIXELS` in
`viewport.py`). Beim Aufbau meldet Qt für ein Widget ohne fertiges Layout
100 mal 30 Bildpunkte; daran rechnete `pixels_per_mm` 0,28 aus, was ein Raster
von 100 mm ergab — und da der Fang jetzt dieselbe Zahl nimmt, landeten drei
Klicks dreimal auf (0 | 0). Deshalb zieht `start_sketch` die Weite über einen
`QTimer.singleShot(0, …)` nach, sobald das Layout steht.

**Raster und Beschriftung folgen dem Maßstab** (`grid_step`, Folge 1, 2, 5),
und das Rad zoomt auf den Zeiger. Eine feste Weite ist herausgezoomt eine
Fläche aus Linien und hineingezoomt ein Blatt mit vier Linien darauf.

**Seit dem Schnitt (§30.1, P4) kommt dieser Maßstab aus der Kamera, nicht aus
der Zeichenfläche.** Sie ist im Viewport-Modus unsichtbar, rechnet aber
weiter — und ihr eigener Maßstab steht damit auf dem Startwert 1,2, weil dort
niemand mehr zoomt. Gezeichnet wurden so 20 mm, während auf 1 mm gefangen
wurde: zwei Zahlen für dieselbe Sache, und die sichtbare war die falsche.
`Viewport.pixels_per_mm(frame)` misst über zwei projizierte Weltpunkte statt
`parallel_scale` umzukehren — damit stimmt die Zahl bei beiden Projektionen —,
und `grid_step_for(scale)` ist aus der Methode heraus, damit beide Seiten
dieselbe Folge rechnen.

**Und die Kamera meldet jede Bewegung zurück** (`Viewport.cameraMoved`,
verbunden in `start_sketch`, gelöst in `finish_sketch`). Das ist die dritte
Kante, und sie fehlte: Feld → Bild läuft über `sketchChanged`, Bild → Feld
über `follow_grid` — aber Rad, Drehzug und *Einpassen* änderten den Maßstab,
ohne dass irgendwer neu zeichnete. Das Raster zeigte die Weite vom Betreten,
und erst der nächste Strich ließ es springen (gemeldet von Robert am
26.08.2026: „die Gitterlinien sollten genau das Raster sein"). Gesendet wird
am **Ende** einer Bewegung — vom Zugende des Navigators (`on_end` in
`_weak_callbacks`) für Dreh-, Kipp- und Schiebezug; der Radzoom, die
Kameravorgaben, die 3D-Maus (`settle_camera`) und `show_span_on_plane` melden
selbst, weil sie keinen Zug haben. Ein
Neuzeichnen kostet gemessen 7,8 ms; wer
hier ein Ereignis je Mausbewegung sendet statt je Zug, bezahlt es im
Qt-Hauptthread. `_pinned_step` gilt dabei unverändert: Die Kamera-Kante ruft
`_redraw_sketch`, und dort gewinnt eine eingetippte Weite wie überall.

**Das Rad war orthografisch tot, und im Skizzenmodus ist orthografisch
immer** (`apply_wheel_zoom` in `viewport.py`). Ein Dolly teilt nur die
Distanz — in der Parallelprojektion bestimmt `parallel_scale` die Bildgröße,
und die Position ist ihr gleichgültig: acht Radschritte, Bild byteweise
unverändert (gemessen 26.08.2026 unter VTK, am echten Fenster, wo der
direkte `Dolly`-Aufruf die Fallunterscheidung nicht trug, die der Trackball
intern hatte). Wer an der Kamera zoomt, geht durch `apply_wheel_zoom`, und
das unterscheidet die beiden Projektionen; `tests/test_viewport_decisions.py`
prüft beide.

**Und die Kamera braucht dafür eine Untergrenze.** In einer leeren Szene hat
`reset_camera` nie stattgefunden; die Startkamera stand 1,62 Einheiten vor dem
Ursprung (gemessen unter PyVista), und `_plane_distance` übernahm sie treu — 918
Bildpunkte je Millimeter, ein Raster von 0,1 mm. Getroffen hätte es
ausgerechnet **Weg 2**, neu konstruieren: nur dort ist die Szene beim Betreten
leer, mit geladenem Teil ist die Kamera längst eingepasst und
`LEAST_PLANE_DISTANCE` wirkungslos.

**Die Zeichenebene wird orthografisch gesehen.** Der Grund steht seit je am
Umschalter selbst (§18.1) — Parallelprojektion ist das, was gemessene Längen
vertrauenswürdig macht —, und hier wiegt er schwerer als sonst irgendwo:
Perspektivisch erscheinen zwei gleich lange Strecken auf derselben Ebene
verschieden lang, je weiter sie von der Bildmitte weg liegen, und genau darauf
setzt man beim Zeichnen Punkte. Gesehen hat das kein Test, sondern das Bild:
Die Korpusplatte stand trapezförmig da, mit sichtbaren Seitenwänden, während
die Zeile darunter „Draufsicht (XY)" meldete.

Zwei Dinge hängen daran. Beim Verlassen wird auf den Wert des Nutzers
zurückgestellt und nicht auf „perspektivisch" — wer orthografisch arbeitet,
hat das gewählt. Und `view_on_plane` rechnet `parallel_scale` aus der
Kameradistanz (`_fit_parallel_scale`): Der Vertrag führt für beide
Projektionen getrennte Größen (`parallel_scale` neben dem Abstand), und wer
umschaltet, ohne die eine aus der anderen zu rechnen, landet auf einem
Startwert — unter VTK war es 1,0, ein sichtbarer Ausschnitt von zwei
Millimetern.

**Die Ebene ist eine Ansicht, und sie steht im Bild.** Benannt wird sie danach,
was man sieht (Draufsicht, Vorderansicht, Seitenansicht), die Ebene steht in
Klammern daneben — sie ist die Angabe, die in der Projektdatei landet. Die
Achsenbuchstaben kommen aus `PLANE_AXES` und folgen ihr; auf einer angeklickten
Fläche des Körpers bleiben sie weg, denn die kann beliebig geneigt sein. Die
Ziffern 1, 2 und 3 wechseln direkt und gehen dabei über `choose_plane`, also
über das Auswahlfeld — an ihm vorbei behaupteten zwei Stellen zweierlei.

Und jedes Zeichenwerkzeug sagt in der Statuszeile, was der nächste Klick tut
(`drawing_hint`). Der Linienzug ist der Fall, an dem es fehlte: er läuft
weiter, bis Esc ihn beendet, und das stand nirgends.

**Wo der Zeiger steht, steht in der Zeile** (`pointer_target`,
`SketchPanel._show_pointer`). Genannt wird nicht die rohe Lage, sondern der
Ort, an dem ein Klick landet — bei aktivem Fang also die Rasterweite. Eine
Anzeige, die 29,75 zeigt, wo 30 entsteht, wäre schlechter als keine. Ohne sie
ist ein gezogener Punkt eine ungefähre Lage, und „genau" geht nur über den
Umweg Nachmessen; wo es auf den Zehntel ankommt, führt das Kontextmenü am
Punkt zu Zahlen (`edit_point`) — mit eigenem `_remember()`, denn den
Undo-Punkt setzt beim Ziehen der Mausdruck.

**Der Zeiger sagt, was ein Klick tut — auch auf der Zeichenfläche.** Sie
setzte ihn nie: der Pfeil stand da, gleich ob ein Zeichenwerkzeug lief oder
nicht. Wer drei Punkte gesetzt hatte und den mittleren anklickte, um ihn zu
ziehen, setzte einen vierten genau darauf — deckungsgleich, unsichtbar, mit
Bedingung. Gesetzt wird in `SketchCanvas.set_tool`, aus derselben Quelle wie
überall (`cursors.cursor`); die Rolle `draw` ist eine **Systemform**
(`CrossCursor`), weil das Fadenkreuz die bekannteste Form für „hier entsteht
etwas" ist und der Zeigergröße des Systems folgt. Dass der Viewport seinen
Zeiger an genau einer Stelle setzt, gilt dort und aus seinem eigenen Grund —
die Zeichenfläche hat nur einen Auslöser, das Werkzeug.

**Ein Klick auf einen Punkt greift ihn** (`grab_point`) — beim Auswählen und
beim Punktwerkzeug, und er hängt sofort am Zeiger. Vorher entstand dort ein
zweiter genau auf dem ersten, deckungsgleich und unsichtbar, und um den
ersten zu bewegen, musste man erst das Werkzeug wechseln. Die Regel steht in
`place` und nicht bloß im Mausereignis: **was ein Klick tut, entscheidet die
Methode, die auch ein Test ruft** — die Ereignisse übersetzen nur. Bei Linie,
Kreis und Bogen bleibt der Fang, wie er war: dort ist der vorhandene Punkt der
Anfang des neuen Elements, und die Deckung ist die Verbindung, für die der
Fang da ist.

**Was ein Klick greifen würde, leuchtet auf** (`_note_hover`). Der Fangradius
ist acht Bildpunkte; wo er greift, gehört ein Zeichen hin — sonst klickt man,
sieht keinen Unterschied und klickt wieder. Und die Auswahl selbst muss man
sehen: 5,0 gegen 3,5 Bildpunkte Radius waren drei Bildpunkte Unterschied im
Durchmesser, die Aussage hing damit praktisch allein an der Farbe (Regel 18).

**Ein Knopf, der nicht kann, sagt was ihm fehlt.** Die zehn Bedingungsknöpfe
folgen der Auswahl (`constraint_offers`); wer sie nur sperrt, lässt raten. Der
Hinweis am Knopf und die Meldung nach einem Kürzel nennen dieselbe Auskunft
aus derselben Quelle (`_needs_phrase`) — stumm zurückzukehren ist die
schlechtere Hälfte von „fehlgeschlagen": es sagt nicht einmal, dass etwas
nicht ging. Dass **Strg** das Zweite dazunimmt, steht in der Zeile, sobald
eines ausgewählt ist (`selection_hint`) — ohne das kommt niemand auf ein Maß
zwischen zwei Punkten.

**Das Maß beim Zeichnen steht am Zeiger, nicht in der Werkzeugzeile.** Wer
eine Linie zieht, sieht auf ihre Spitze; eine Zahl am Fensterrand liest dort
niemand. Fusion legt sie an den Zeiger, und darum ist das Eintippen dort der
Normalweg — hier war es eine Funktion, die man kennen musste. Die
Zeichenfläche besitzt `measure_field` und legt es mit `MEASURE_GAP`
Bildpunkten Abstand neben die Spitze:

* **Nicht darunter** — es finge die Mausbewegungen ab, und die Linie bliebe
  beim Ziehen stehen.
* **An Rand und Ecke kippt es** auf die andere Seite des Zeigers. Die untere
  rechte Ecke ist kein Sonderfall: dorthin zieht man die letzte Linie eines
  Umrisses.
* **Die erste Ziffer beginnt die Eingabe**, ohne Klick und ohne Tabulator.
  Ein Feld, das man erst anklicken muss, verlangt genau die Handbewegung, die
  das Zeichnen unterbricht — und der Zeiger steht danach woanders, also auch
  das Maß, das er gerade zeigte. Gesendet wird an `lineEdit()`; ein `event()`
  auf dem Drehfeld landet in der Pfeiltastenbehandlung.

Nebenbei löst das den breitesten Posten der Werkzeugzeile auf. Ein erster
Schritt hatte ihn nur ausgeblendet, solange nichts gezeichnet wird — gemessen
gegen den Stand davor sprang die Zeile beim ersten Klick von 881 auf 1007
Bildpunkte zurück, also genau dann, wenn man sie am wenigsten braucht.

**Was im Konstruktor gesetzt wird, kommt vor den Verbindungen.** `SketchPanel`
setzt die Skizze, bevor `sketchChanged` verbunden ist: die Bedingungsliste
blieb bei einer geöffneten Skizze leer, bis irgendetwas geändert wurde, und
die Knöpfe standen alle bedienbar da. Ein Signal ersetzt nicht den ersten
Aufruf — beide Auffrischungen laufen am Ende des Konstruktors von Hand.

**Der Drehpunkt ist die Mitte der Körper, nicht die des Sichtbaren.**
`ComputeVisiblePropBounds` nimmt Druckplatte und Bauraumrahmen mit; bei 250 mm
Rahmen und 40 mm Teil liegt die Mitte hundert Millimeter über dem Modell, und
die Kamera rückt bei jedem Szenenaufbau dorthin. `rotation_centre()` rechnet
deshalb aus `_object_bounds()` — derselben Quelle wie `reset_camera`. Ohne
Körper wird gar nichts verschoben.

**Die Zeile beantwortet zwei Fragen, und die erste ist „ist es zu?".** Ob eine
Kontur geschlossen ist, war bis zum Bestätigen der Operation nicht zu
erfahren: Wer vier Linien zog und den letzten Klick knapp neben den ersten
Punkt setzte, sah dasselbe Bild wie einer, der getroffen hatte — die Auskunft
kam danach, als Absage. `_outline_state()` fragt `regions_of`, also denselben
Kern, der später rechnet; die Antwort ist damit dieselbe und nicht bloß eine
ähnliche. Übernommen wird aber nur das **Ja oder Nein**, nicht sein Satz: „Der
Umriss ist nicht geschlossen" ist die Absage auf eine Handlung und stünde hier
vom ersten Strich an als Warnung vor einem Zustand, den man gerade
beabsichtigt. In der Zeile steht „Noch offen" oder „Geschlossen", und dahinter
die Freiheitsgrade — keine der beiden Fragen beantwortet die andere: ein
bestimmtes Rechteck kann offen sein, ein geschlossenes darf wackeln.

**In der Querschau zieht man am Umriss, und der Körper wächst mit**
(`Viewport.set_sketch_pull`, `axis_hit`, `pull_cage`). Robert am 27.08.2026:
„schön wäre auch dass wenn ich in der skizze was in der draufsicht zeichne und
dann in die Seitenansicht oder vorderansicht gehe sie nach oben ziehen kann."
Vorher tippte man eine Höhe und sah das Ergebnis; der Unterschied ist die
Geste.

**Angeboten wird sie genau dort, wo nicht gezeichnet wird** — in der Querschau,
also wenn `view_plane` und `sketch.plane` auseinandergehen. Das ist ein
**Zustand** und keine Schwelle, und das ist Absicht: Ein Winkelmaß „wie sehr
von der Kante" läge neben der Prüfung, mit der `ray_hit` seine Stelle findet,
und zwischen zwei Schwellen für dieselbe Frage liegt immer ein Bereich, in dem
beide Antworten falsch sind. In der Draufsicht bliebe die Geste dem Zeichnen im
Weg: Ein Druck auf eine Umrisskante wäre dort mal ein Punkt, mal ein Zug.

Sechs Dinge hängen daran:

* **Die Frage stellt das Fenster, die Geste kennt die Ansicht**
  (`MainWindow._sketch_pull_offer`). Drei Antworten: `"ready"`, ein Grund, oder
  leer. Ein **Grund** kommt nur, wo die Geste gemeint war und nicht ging —
  sonst stünde bei jedem Druck irgendwo im Bild ein Satz über eine Handlung,
  die niemand versucht hat. Er geht über `sketchPullBlocked` an `announce`
  (Regel 17: ein Griff, der stumm nichts tut, sagt nicht einmal, dass etwas
  nicht ging).
* **Und dieselbe Quelle schreibt den Satz in die Leiste.** Ohne ihn findet die
  Geste niemand: Der Umriss sieht von der Kante aus wie ein Strich. Zwei Texte
  aus zwei Quellen wären zwei Gelegenheiten, einander zu widersprechen.
* **Der Griff ist der Umriss selbst**, nicht ein eigener Anfasser. Gemessen
  wird in Bildpunkten gegen die **Strecken** der projizierten Kurven
  (`polyline_distance`) und nicht gegen ihre Ecken — dieselbe Unterscheidung wie
  bei der Merkmalssuche, die gegen die Dreiecke misst. Er reicht so weit, wie
  die Fangmarke groß ist (`CURSOR_PIXELS`): Was man sieht, kann man greifen,
  und eine zweite Zahl daneben wäre ein Bereich, in dem die Marke steht und der
  Griff nicht hält. Konstruktionsgeometrie zählt nicht mit — an ihr entsteht
  kein Körper.
* **Dieselbe Zustandsmaschine wie der Körperzug** (`on_body_drag` mit
  `ready`/`start`/`move`/`end`, Weiche in `_weak_callbacks`). Eine zweite wäre
  eine zweite Klickschwelle, und das Loch zwischen zwei Schwellen hatte der
  Körperzug schon einmal. Nur der Rückweg ist ein anderer: `_end_drag` schickt
  den Ziehgriff durch `_end_pull` und **nicht** durch `set_navigation` — das
  baute den Interaktionsstil mitten in der Geste neu auf, und das Loslassen
  käme bei einem Stil an, der von seinem Drücken nichts weiß.
* **Was wächst, ist eine Drahtform und keine Fläche** (`pull_cage`). Eine echte
  Vorschau ginge über `session.preview_async`, also über einen Arbeiter-Thread
  und einen Neuaufbau der Aktoren; allein das Neuzeichnen der Skizze kostet
  gemessen 7,8 ms, und bei sechzig Mausereignissen in der Sekunde ist das der
  Qt-Hauptthread. Die Sprossen sind gedeckelt (`MOST_PULL_RIBS`): Bei einem
  Kreis mit vierundsechzig Punkten wären es vierundsechzig Striche, und das ist
  eine Wand und keine Drahtform.
* **Angeboten wird nur, was auch geht** (`pull_height_at` in
  `sketch_pull_ready`). Der Zustand oben sagt, ob Ziehen *gemeint* ist; diese
  Frage sagt, ob es *möglich* ist — von dieser Blickrichtung aus überhaupt eine
  Höhe ablesbar. Das sind zwei Fragen und nicht zwei Schwellen für eine:
  gefragt wird `axis_hit` selbst, also dieselbe Prüfung, die der Zug danach
  benutzt. Sie fehlte, und der Fall, der sie erzwang, ist eine Skizze auf einer
  **angeklickten Fläche**: Dort hat der Blick nie denselben Namen wie die
  Zeichenebene, das Angebot stand also immer — und bei frontaler Ansicht gab
  `axis_hit` nichts zurück. Der Griff nahm die linke Taste und tat stumm
  nichts.

  **Und derselbe Ort wird zweimal gefragt** (`pull_base_at`): Eine
  Bereitschaft, die eine andere Stelle prüft als der Zug danach nimmt, ist
  keine.

  **Was das ausdrücklich nicht abdeckt:** Wer sich mit der Maus in die
  Kantensicht *dreht*, ohne die Ebenenwahl anzufassen, bekommt den Griff
  weiterhin nicht — `view_plane` folgt dem Auswahlfeld und den Ziffern 1 bis 3,
  nicht dem Drehzug. Das ist die Grenze und kein Rest: Dort ist Zeichnen die
  erklärte Absicht, ein Klick setzt weiter Punkte, und ein Griff daneben wäre
  genau die Überlappung, die der Zustand vermeidet. Versprochen wird die Geste
  nur in der Querschau, und dort gilt sie.
* **Die Grenze steht an einer Stelle, und die heißt `_pull_takes`.**
  Gefragt vom Loslassen und von der Eingabetaste, über die Höhe, die auch
  angewandt würde. Vorher stand die Untergrenze an zwei Stellen und die
  Obergrenze an keiner:
  Eine getippte Höhe von 4000 mm ging bei einem Höchstwert von 1000 durch, und
  der Dialog klemmte sie danach kommentarlos.

  **Beim Tippen wird abgelehnt, beim Ziehen geklemmt**, und das ist kein
  Widerspruch: Wer zieht, meint eine Bewegung, und die darf am Anschlag stehen
  bleiben; wer tippt, meint genau diese Zahl, und sie stillschweigend zu ändern
  wäre die Antwort auf eine andere Frage. Die abgelehnte bleibt im Feld
  markiert stehen — dieselbe Zusage, die `_apply_typed` für alle Zugarten gibt.
* **Ein Zug in die falsche Richtung sagt es, statt einen Splitter zu bauen.**
  `pulled_height` klemmt ein Maß **mit erhaltenem Vorzeichen**, und ein auf
  null gefangenes Maß bleibt null — bis zum 02.09.2026 hob die Klemmung es auf
  die Untergrenze, und weil `round(-0.3)` gleich `-0.0` ist und `-0.0 < 0.0`
  nicht gilt, wurde aus einem kurzen Zug nach unten ein Aufbau von 0,1 mm nach
  oben. Die Richtung entscheidet `continue_sketch_pull` und `_pull_takes` an
  derselben geklemmten Höhe; ein Zustand daneben (`_pull_raw`) stand hier
  einmal als „einzige Auskunft über die Richtung" und hatte keine Lesestelle
  mehr — er ist weg, und die Regeldatei beschreibt den Code, der da ist.

  **Und zwar nur gegen die Untergrenze.** Die vollständige Prüfung stand hier
  einen Anlauf lang und lehnte damit zwei richtige Fälle ab: Ein Zug bis zum
  **Anschlag** hat ein rohes Maß über der Obergrenze und ist trotzdem gemeint —
  die Leiste zeigt den geklemmten Wert, und der ist die Zusage. Und wer nach
  einem Fehlzug eine Zahl **tippt**, hat die Frage nach der Richtung
  beantwortet — die getippte Höhe ersetzt den Zeiger samt Richtung.
* **Die Höhe ist gefangen und geklemmt** (`pulled_height`). Gefangen auf das
  Raster, das im Bild steht — eine aufgezogene Höhe soll eine runde Zahl sein,
  und ein Zug, der zwischen zwei Rasterpunkten nichts ändert, zeichnet nicht.
  Geklemmt auf die Grenzen **aus dem Schema** (`main_window.pull_limits`), denn
  eine Zahl, die der Griff zeigt und der Dialog danach ablehnt, ist eine
  gebrochene Zusage. Wer sie hier abschreibt, hat die zweite Wahrheit gebaut.

**Und der Griff ist ohne Attrappe nicht prüfbar** (`gripping` in
`tests/test_viewport_decisions.py`). Offscreen gibt es keinen Renderer, also
gibt `_display_of` nichts, `grip_reach` unendlich und `sketch_pull_ready`
**immer** `False` — auch mit gesetztem Angebot. Der erste Test darüber
behauptete „ohne Frage kein Griff" und wäre auch bei einem Griff grün geblieben,
der jede Frage übergeht; `sketchPullBlocked` kam in der ganzen Suite nicht ein
einziges Mal vor. Ersetzt werden genau die drei Methoden, die einen Renderer
brauchen — Reichweite im Bild, Ort auf der Ebene, Maß entlang der Achse —, alles
davor und danach ist echt. Das ist das Muster aus `ansicht.md`, und
`test_cursors.py` macht es vor.

**Und die Zahl steht am Zeiger, nicht am Fensterrand** (`DragValueBar.anchor`).
Dieselbe Entscheidung wie beim Maßfeld der Zeichenfläche, mit demselben
`MEASURE_GAP` — es wohnt seit dem Ziehgriff in `viewport.py`, weil zwei Felder
daran hängen und eine Zahl an zwei Stellen driftet. Bei den Griffen von §18.11
bleibt das Feld oben mittig: Dort zieht man an einem Gizmo, den man ansieht,
und ein Feld unter dem Zeiger verdeckte gerade ihn.

**Der Umriss trägt seine Nummern auch im Konflikt.** Der Hinweis an einem
Eintrag der Bedingungsliste nennt Art, Maß, Ort, Wirkung — und darunter die
rohen Punktnummern, weil danach sucht, wer eine Bedingung aus einer Meldung des
Lösers wiederfinden will. Der Konfliktzweig überschrieb den Hinweis vollständig
und nahm sie mit; ein Konflikt **ist** diese Meldung, also ist es der Fall, für
den die Nummern da sind.

**Der Zug kostet dabei keinen Klick weniger.** Gemessen am gebauten Fenster,
27.08.2026: Rechteck zeichnen und extrudieren sind über *Fertig* sechs Klicks
und über den Ziehgriff auch sechs. Was er einbringt, ist nicht die Zahl der
Klicks, sondern dass die Höhe **gesehen** statt geraten wird — wer 15 mm zieht,
hat keine Zahl getippt und trotzdem eine.

**Die zwei häufigsten Folgen stehen trotzdem als Wörter an der freien
Skizze.** Der Ziehgriff ist der anschauliche Direktweg, aber nur in der
Querschau sichtbar; wer „Extrusion“ nicht kennt, soll nicht erst *Fertig*
drücken und unter fünf Fachbegriffen suchen. Sobald der Umriss geschlossen
ist, führen deshalb *Hochziehen* und *Abtragen* direkt in den jeweiligen
Operationsdialog. Dort wird die genaue Höhe oder Tiefe angegeben — die
Zeichenleiste erzeugt selbst keine Geometrie (Regel 2). Solange der Umriss
offen ist, nennen beide Knöpfe im Hinweis ihre Bedingung. *Abtragen* verlangt
zusätzlich genau einen ausgewählten exakten Körper; fehlt er, steht der Grund
am gesperrten Knopf. Wurde der Skizzenmodus bereits für eine andere Operation
geöffnet, bleiben die beiden kurzen Wege verborgen und *Fertig* hält die
ursprüngliche Absicht.

**Und der Umriss beantwortet auch, was seine Kennzahl bedeutet**
(`outline_advice`). „Geschlossen · 12 Freiheitsgrade sind noch frei" sagt einem
Anfänger nichts — weder ob das gut oder schlecht ist, noch was zu tun wäre. Die
Zahl bleibt stehen, denn für den Könner ist sie richtig und die einzige
Auskunft darüber, wie weit eine Skizze bestimmt ist; dahinter steht ein Satz,
der sie in eine **Folge** übersetzt. Drei Lagen, drei Sätze, und der Umriss
gewinnt vor den Freiheitsgraden: Ohne ihn scheitert jede der fünf
Erzeugungsarten, mit ihm ist ein freier Freiheitsgrad höchstens eine
Ungenauigkeit.

**Dasselbe gilt für die zehn Bedingungsknöpfe** (`_does_phrase`). `_needs_phrase`
sagt, was ausgewählt sein muss; das ist die Bedienung und nicht die Sache.
„Tangential" ist ein Wort, das jeder aus einem CAD kennt und niemand sonst, und
wer es nicht kennt, wusste danach, was er anklicken muss, und immer noch nicht,
wozu. Der Satz steht am Knopf, im Kontextmenü, in der Meldung nach einem Kürzel
**und** an jedem Eintrag der Bedingungsliste — vier Stellen, eine Quelle.

**Verschieben ist ein eigener Griff, kein Punkt-für-Punkt.** `edit.move`
schiebt die Auswahl an Ort und Stelle — verschoben, nicht kopiert wie
`offset` und `mirror` daneben, also behalten die Elemente ihren Platz in der
Liste und jede Bedingung zeigt weiter auf dieselbe Stelle. Vorher gab es nur
`move_point`: bei einem Rechteck vier Züge, von denen die ersten drei die Form
verziehen. In der Zeichenfläche hängt die Auswahl nach dem Klick an der Hand,
aber erst **ab Qts `startDragDistance`** (`_shift_selection`) — ohne die
Schwelle säße die Form nach jedem Auswahlklick ein Zehntelmillimeter daneben.
Der Undo-Punkt entsteht beim ersten wirklichen Zug und nur einmal; `move_selected`
merkt nicht, sonst stünden im Rückgängig so viele Schritte, wie die Maus
Meldungen geschickt hat.

**Was auf einer Taste liegt, steht auch im Kontextmenü.** Löschen lag allein
auf Entf, und in der Werkzeugleiste steht es nicht — wer die Taste nicht rät,
wird ein Element nicht los. Der Eintrag nennt das Kürzel daneben, so lernt man
es nebenbei. `_context_menu` ist dafür in **Bauen** (`context_menu_at`) und
Zeigen getrennt: ein Menü, das sich selbst öffnet, hält eine Suite an —
`QMenu.exec` blockiert wie ein modaler Dialog, und `QMenu.exec` zu patchen ist
kein Ersatz, sondern der nächste Hänger.

## Sichtbarer Skizzenmodus im Viewport (29.08.2026)

Der Canvas rechnet im Viewport-Modus weiter, aber **jede Auskunft, die der
Kunde sehen muss, reist mit ins sichtbare Bild**. `pending_elements()` gibt die
unfertige Linie, den Kreis, Bogen, Spline oder die vier Rechteckkanten als
gewöhnliche `SketchElement`-Vorschau heraus; `curves_of` wandelt sie auf
demselben Weg wie die feste Zeichnung um. `measure_annotations()` liefert
Maßtext und versetzte Position. Beides ändert weder Skizze noch Undo-Stand
(Regel 2). Ein Mausereignis aktualisiert Fangkreuz und Vorschau gemeinsam und
rendert höchstens einmal.
Fangmarke, `pending_elements()` und der feste Klick lesen dasselbe Ziel aus
`_placement_target`: Ein vorhandener Punkt schlägt das Raster. Damit zeigt die
Vorschau auch bei einem Punkt auf 10,25 mm genau den Ort, an dem anschließend
die Deckungsbedingung entsteht.

Ein Raster ist kein gleichförmiger Teppich. Im Viewport gelten drei Ebenen:
leise Zwischenlinien, jede fünfte als Landmarke, Nullachsen mit X/Y/Z-Buchstaben
nahe am Ursprung. Die Buchstaben stehen absichtlich nicht am Ende des
Rasters — dessen Reichweite liegt meistens außerhalb des Ausschnitts.
Skizzenkanten sind Hinweisblau und breiter als das Raster, Auswahl und
unfertige Geometrie bernsteinfarben und zusätzlich dicker beziehungsweise als
Vorschau kodiert. Maße stehen in ruhigen Karten statt direkt auf der Kante.

Der Fusion-nahe Weg wird progressiv erklärt. Sobald ein Umriss schließt, steht
im Bild: Vorder- oder Seitenansicht wählen. In der Querschau nennt die Karte
den Pfeil und — nur bei ausgewähltem bearbeitbarem Körper — auch das Kreuz;
direkt am Griff stehen entsprechend **Hochziehen** und **Abtragen**. Das Profil
wird automatisch in der freien Fläche oberhalb der Werkzeugkarte zentriert.
Ein Griff hinter der Leiste oder ohne gültige Operation ist kein vorhandener
Griff.

Die untere Karte bleibt eine Leiste. Im Viewport-Modus gehen der unsichtbare
Canvas, sein leeres Strecklayout und der umbrechende Schichthinweis aus ihrer
Höhenrechnung. Die Schichtauskunft bleibt als Tooltip am Ebenenfeld, die
Bedingungsliste im rechten Reiter. Gemessen am gebauten Panel fiel die
Vorgabehöhe von 292 auf 142 Bildpunkte; die Bedienung verlor dabei keine
Handlung.
