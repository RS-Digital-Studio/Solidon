---
paths:
  - "app/ui/**/*.py"
---

# Regeln für die Oberfläche

PySide6. Die Oberfläche darf `core` benutzen, nie umgekehrt. Sie rechnet keine
Geometrie und ändert keine — sie ruft Ops auf.

## Das Versprechen

**Nichts ist endgültig.** Jede Handlung ist eine Op, jede Op rücknehmbar, jeder
Wert nachträglich änderbar. Praktisch heißt das: **keine Bestätigungsdialoge
vor rücknehmbaren Handlungen**, kein „Möchten Sie wirklich", keine Sackgassen
(Regel 19).

## Texte

Keine feste Zeichenkette in der Oberfläche — alles über `tr()`, deutsch und
englisch. **Das gilt auch für Auswahlwerte**: `raised`, `flat`, `linear` sind
Schlüssel und keine Beschriftungen. Der Name steht in `_CHOICE_NAMES`
(`app/ui/labels.py`), und `tests/test_translations.py` lässt nur durch, was
sein eigener Name ist — M4, 6x3, mm, x, DejaVu Sans, gyroid. Bilder statt
Wörter, wo ein Wort nichts zeigt: die Texturmuster tragen ihre Kachel aus
`figures.texture_tile`, erkannt an den Werten des Feldes und nicht an seinem
Namen. Ein Fehler endet nie mit „fehlgeschlagen": erst was nicht ging, dann
warum, dann was jetzt möglich ist, als anklickbare Handlungen (§2.7). Kein
Stapelabzug im Nutzerdialog.

## Fenster

Höchstens drei sichtbare Zonen: links Objektbaum, Parameter und Verlauf als
einklappbare Abschnitte; Mitte der Viewport; rechts **entweder** Chat **oder**
Prüfbericht, umschaltbar und ganz ausblendbar. Die Umschaltung springt zum
Bericht, wenn eine Warnung entsteht.

Solange ein Beispielprojekt offen ist, hat die rechte Spalte einen dritten
Reiter: die Tour (`app/ui/tour.py`, Schritte in `app/core/tour.py`). Sie
erkennt getane Schritte über `projectChanged` am Dokument und Verlauf, „Weiter"
schaltet jeden Schritt auch ohne Erkennung — Angebot, keine Sperre. Der
Warnungssprung zum Bericht lässt der aktiven Tour den Reiter; jedes andere
Projekt räumt ihn weg. Die Erkennungswerte müssen zu `tools/make_examples.py`
passen — driftet beides, wird `tests/test_tour.py` rot.

**Keine Betriebsarten.** Kein Umschalten zwischen „Bearbeiten" und
„Konstruieren" — es gibt einen Zustand, und der ist die Szene.

## Der Hauptknopf

**Ein Hauptknopf entsteht über `style.make_primary()`, nie über
`setDefault(True)`.** Das Stylesheet zeichnet `QPushButton:default` halbfett;
Qt rechnet die bevorzugte Breite aus der **normalen** Schrift des Widgets. Wo
ein Layout dem Knopf genau diese Breite gibt — in einer engen Leiste tut es
das —, wird die Beschriftung abgeschnitten: Auf dem Hauptknopf des
Trennwerkzeugs stand „etzt trenne", 89 Bildpunkte Text in 104 minus
Innenabstand. `make_primary` setzt die Schrift am Widget, damit die Rechnung
sie kennt; das Fett bleibt, denn es ist neben der Akzentfarbe die zweite
Kodierung (Regel 18). `tests/test_style.py` misst gegen die Schrift, mit der
wirklich gezeichnet wird, und verbietet `setDefault(True)` außerhalb von
`style.py`.

**Und er heißt nicht wie sein Werkzeug.** Der Umschalter der Werkzeugzeile
nennt das Werkzeug, der Knopf darin seine Handlung — „Trennen" oben, „Jetzt
trennen" unten. `tests/test_interface_limits.py` hält das fest.

## Gestufte Tiefe

Jeder Dialog hat eine kurze Vorderseite und einen aufklappbaren Bereich
„Weitere Einstellungen". Vorn die zwei bis drei Werte, die man ändert; hinten
Toleranzen, Auflösungen, Rückfallverhalten. Die Vorgaben kommen aus dem
Drucker- und Materialprofil. **Eine gute Vorgabe ist mehr wert als eine gute
Einstellmöglichkeit.**

## Die Oberfläche wächst nicht mit

Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche (§2). Die Zahlen
dazu stehen in `tests/test_interface_limits.py` und werden rot, wenn sie
gerissen werden:

| Grenze | Wert |
|---|---|
| Menüs in der Leiste | ≤ 9 |
| Zeilen in einem Menü (ein Untermenü zählt als eine) | ≤ 12 |
| Umschalter in der Werkzeugzeile | ≤ 8 — **erreicht**: Schnitt, Messen, Bewegen, Analyse, Schichten, Explosion, Trennen, Bemalen — auf `Alt+1` bis `Alt+8` |
| Felder auf der Vorderseite eines Operationsdialogs | ≤ 8 |
| Menüeinträge je Operation | höchstens 1 — zusammengelegte Zwillinge (`MENU_TWINS`) haben 0 und leben im Dialog ihres Partners, erreichbar über Palette und Verlauf |

Wer eine Zahl erhöhen will, tut das mit Absicht und begründet es im Commit.
Die Werkzeugzeile ist voll: Ein neuntes Werkzeug heißt, dass eines der acht
kein Werkzeug mehr ist.

**Ein Zeichen darf allein stehen, wenn es entweder ein geeinigtes Bild ist
oder die Zahl klein und die Stelle fest bleibt.** Der Skizzeneditor lebt vom
ersten Fall: Linie, Kreis und Bogen sehen in jedem CAD gleich aus. Die obere
Werkzeugleiste vom zweiten — Blatt, Ordner und Diskette sind geeinigt, „Modell
einfügen", „Zeichnen", „Formen" und „Skelett" nicht; was sie trägt, sind
sieben Knöpfe an unveränderlicher Position mit einem Tooltip, der Namen,
Kürzel und Zweck in einem Satz nennt. Die Werkzeugzeile unter dem Viewport
bleibt beschriftet: acht Umschalter, die mit dem Zustand wechseln, und für
„Schnitt" und „Explosion" gibt es kein Bild. Regel 18 verlangt eine zweite
Kodierung neben der **Farbe**, nicht eine Beschriftung neben jedem Zeichen.

Wo das Wort vom Knopf verschwindet, muss es an drei Stellen weiterstehen: am
`QAction` (Barrierefreiheitsbaum), im Tooltip und im `statusTip`. Den Satz
dafür holt `_button_tip` aus dem Menüeintrag derselben Handlung, samt Kürzel —
zwei eigene Erklärungen für einen Knopf driften auseinander. Der `statusTip`
ist dabei nicht nur Anzeige: `_lock_hint` und `_pick_hint` stellen den eigenen
Hinweis daraus wieder her, und ein ungesetzter macht den Knopf nach dem
Freischalten stumm. Beide Helfer ersetzen den Hinweis vollständig; damit am
unbeschrifteten Knopf nicht ein Bild und ein zusammenhangloser Satz übrig
bleiben, stellt `_with_name` den Namen voran (Merkmal `wordless` am `QAction`).
Getrennt wird mit dem Zeichen, das der Satz dahinter **nicht** schon führt:
Gedankenstrich vor dem Zweck, Doppelpunkt vor einem Grund, der selbst einen
Gedankenstrich hat.

**Wer eine Beschriftung ausblendet, zieht die Anleitungstexte mit.** Handbuch
(`app/core/manual.py`) und Tour (`app/core/tour.py`) verweisen auf Knöpfe beim
Namen; steht der Name nicht mehr am Knopf, sucht der Leser. Die Tour wiegt
schwerer als das Handbuch — ihre Schritte haben `done=`-Bedingungen und rücken
nicht weiter.

**Eine Operation je Handlung, nicht je Variante.** Neun Texturmuster sind ein
Menüeintrag mit einem Auswahlparameter, nicht neun Einträge. Rechteck aus zwei
Ecken oder aus Mitte und Maß ist dasselbe Werkzeug mit einem Umschalter. Die
Mesh/B-Rep-Zwillinge (Quader, Zylinder) sind dieselbe Handlung in zwei
Rechenkernen: ein Eintrag, „Exakt (B-Rep)" ist ein Umschalter hinten im
Dialog, und `MENU_TWINS` im Register hält die Zuordnung — auch für den
Menüort, den der Agent nennt (§2.6).

**Nicht jeder Zwilling braucht einen Umschalter.** Die Beschriftung liegt in
`TWIN_TOGGLES`, nicht als Zeichenkette in der Oberfläche; wer dort fehlt, hat
seinen Umschalter als **Wert** im Dialog des Partners. *An Ebene teilen* ist
*Teilen* mit `pins = 0` — ein Haken „Exakter Körper (B-Rep)" wäre dort eine
Wegbeschreibung zu etwas, das es nicht gibt. Solange das fest verdrahtet war,
taugte die ganze Zusammenlegung für nichts als die zwei Rechenkerne.

**Ein Umschalter zwischen Varianten schaltet den ganzen Dialog um**, nicht nur
die Rechnung: `OperationDialog.switch_variant` blendet aus, was die gewählte
Variante nicht kennt, und tauscht die Beschreibung. Die Werte beim Anwenden zu
filtern genügt nicht — was stehen bleibt, verspricht eine Wirkung. Der
Bezugspunkt des Netz-Quaders stand in derselben aufgeklappten Gruppe wie der
Umschalter selbst, also genau dort, wo jeder vorbeikommt; auf „Ecke" gestellt
kam ein mittiger Quader und kein Ton dazu.

**Ein Feld ohne Wirkung sagt es.** Eine Nummer kleiner als der Umschalter:
*Fläche* in „Relief auflegen" gilt nur, solange *Auflegen* auf „Auf eine
Fläche" steht, und die Operation übergeht den Wert sonst wortlos. Solche
Abhängigkeiten stehen in `DEPENDENT_FIELDS` (`app/ui/op_dialog.py`), nicht als
Sonderfall im Aufbau. Das Feld wird **grau und begründet**, nicht unsichtbar —
verschwinden darf nur, was die gewählte Variante gar nicht kennt; wer eine
Zeile vermisst, sucht sie.

**Ein Sammelparameter bekommt seinen Editor, nicht sein Speicherformat.** Der
Skizzentext hat ihn seit je, die Stellung eines Skeletts bekam ihn spät:
`kind="armature"` fiel auf ein Textfeld durch, und der kürzeste Weg zu einem
gebeugten Arm ging über getipptes JSON. `ArmatureField` baut je Knochen eine
Zeile mit drei Winkeln — sobald der Dialog ein Skelett hat (aus dem Editor
oder aus dem Wert der Operation), sonst bleibt das Textfeld als Rückfall. Die
Winkel sind `ValueField`, denn §13 gilt für einen Winkel wie für eine Länge.
Im **Schema** bleibt der Sammelparameter hinten (`tests/test_gesture_ops.py`);
im Dialog steht er vorn, wenn er der Grund ist, aus dem der Dialog aufgeht.

**Jede neue Funktion nennt ihren Hauptweg** (§2.2), bevor sie einen Platz
bekommt:

| Weg | Ort an der Oberfläche |
|---|---|
| Weg 1 — fremdes Modell anpassen | Kontextmenü am Merkmal, Vorschlag im Prüfbericht, Werkzeugzeile (*Trennen*: zwei Klicks legen die Ebene, Verbinder vorgewählt) |
| Weg 2 — neu konstruieren | obere Werkzeugleiste („Zeichnen": erst skizzieren, die Erzeugungsart fragt der Dialog bei „Fertig"), Menü *Erzeugen* / *Ändern* |
| Weg 3 — generieren | Chat und Generierungsdialog |
| Weg 4 — organisch formen | obere Werkzeugleiste (*Formen*, *Skelett* — beide brauchen einen gewählten Körper und sagen das, bevor man klickt), Menü *Ändern* |
| keiner der vier | Untermenü und Befehlspalette, sonst nichts |

**Was zur Auswahl passt, steht vorn.** `applies_to` sortiert nicht nur das
Kontextmenü, sondern auch die Befehlspalette
(`palette_entries(for_feature=...)`). Es ist eine Reihenfolge, keine Auswahl —
eine Palette, die aussortiert, wäre eine Betriebsart mit anderem Namen.

## Wartezeit

| Dauer | Anzeige |
|---|---|
| unter 0,2 s | nichts |
| bis 2 s | Mauszeiger und Statusleiste |
| darüber | Fortschritt mit **Abbrechen**, Oberfläche bedienbar |
| über 10 s | zusätzlich eine Schätzung, wenn möglich |

Die letzte gültige Darstellung bleibt sichtbar — nie ein leerer Viewport, nie
ein blockierendes Fenster. Lange Rechnungen laufen nicht im Qt-Hauptthread.

**Wo nichts steht, steht die Ladeanzeige.** Der Balken in der Statusleiste ist
für die Fälle richtig, in denen ein Modell im Bild bleibt; beim Öffnen eines
Projekts bleibt keines, und dann liegt er als einzige Auskunft dort, wo beim
Warten niemand hinsieht. `LoadingVeil` (`app/ui/loading.py`) legt sich deshalb
über die Ansicht — das Anwendungssymbol wird gedruckt wie beim Start,
darunter Linie, Prozentzahl, laufender Schritt und *Abbrechen*.

Drei Bedingungen, alle drei tragend:

* **Nur bei leerem Bild.** Steht ein Körper da, bleibt er stehen; wer
  entscheidet das, ist `MainWindow._update_veil`.
* **Unter den Karten, nicht darüber** (`OverlayHost.set_veil`). Über ihnen wäre
  es ein Vorhang ohne Ausgang.
* **Erst nach 200 ms.** Ein leeres Projekt ist schneller gerechnet, und eine
  Anzeige, die dabei aufblitzt, ist Unruhe ohne Auskunft.

Deckend gezeichnet, mit dem Verlauf aus `viewport_colours` — ein
halbdurchsichtiges Qt-Widget über dem OpenGL-Fenster zeigt die Fensterfarbe,
nicht die Ansicht dahinter.

**Die Ladeanzeige beginnt später, als das Warten beginnt.** Sie hängt am
Fortschritt der Auswertung; was *davor* liegt — `load()` für eine Projektdatei,
`read_bytes()` für ein Modell —, sieht sie nicht, und ihre 200 ms kommen
obendrauf. Diese Zeile der Tabelle bedient `waiting()` in `main_window.py`, ein
Kontextmanager um genau eine Rechnung: Datei lesen, Dialog aufbauen, Slicer
suchen. Als Kontextmanager, weil ein Wartezeiger, der an einem Fehlerausgang
stehen bleibt, aussieht wie ein hängendes Programm — und eine Frage, die
darunter gestellt wird, sagt zweierlei. `_offer_recovery` liegt deshalb
außerhalb.

**Ein Export bekommt Fortschritt, aber kein Abbrechen** (`_ExportWorker`). Die
Regel darüber ist nicht aufgeweicht, sie greift hier nur anders: Ein halb
geschriebener Export ist eine halbe Datei, und der Schreiber im Kern hat keinen
Punkt, an dem er sauber aufhören könnte. Was §2.8 an dieser Stelle trägt, ist
die Bedienbarkeit — der Balken läuft, das Fenster reagiert, der Menüeintrag ist
gesperrt, solange geschrieben wird. Wer einen Arbeiter ohne Abbrechen baut,
schreibt diese Begründung in seinen Docstring; ohne sie ist es Bequemlichkeit.

**Was nicht sofort da ist, wird nachgereicht statt erwartet.** Der
Druckeinstellungen-Dialog wartete bis zu zwei Sekunden auf die Schichtanalyse —
die schlechtere Hälfte beider Möglichkeiten: lang genug, um sich wie ein Hänger
zu lesen, und ohne Zusage, denn wer den Zeitraum riss, bekam den Dialog eben
doch ohne sie. Er geht jetzt sofort auf, `take_slice_result` trägt sie in die
Vorschlagsliste nach. Der Rückruf zeigt dabei auf ein **Feld des Fensters**
(`_settings_dialog`), nicht auf eine gebundene Methode des Dialogs: der wird
nach `exec` weggeräumt, und ein Rückruf in ein zerstörtes C++-Objekt ist der
Absturz ohne Zeile.

### Wer einen Arbeiter startet, hält ihn fest

Ein `QThread` bekommt hier keinen Qt-Elternteil; ihn hält allein die
Python-Referenz. Fällt sie weg, während der Thread noch läuft, zerstört der
Speicherbereiniger das C++-Objekt unter ihm — eine Zugriffsverletzung ohne
Zeile, irgendwann später und selten reproduzierbar.

**Nie als Lambda, das blind `None` schreibt:**

```python
worker.finished.connect(lambda: setattr(self, "_worker", None))  # falsch
```

Das geht zweimal schief. `finished` kommt, während Qt den Thread noch abräumt —
zu früh zum Loslassen. Und es trifft das Feld, nicht den Arbeiter: wird ein
Vorgänger fertig, nachdem sein Nachfolger im Feld steht, löscht er dessen
Referenz.

**Richtig** ist ein benannter Slot, der seinen *eigenen* Arbeiter erkennt und
ihn danach der gemeinsamen Halteleine übergibt:

```python
worker.finished.connect(lambda done=worker: self._worker_done(done))


def _worker_done(self, worker: Any) -> None:
    if self._worker is worker:
        self._worker = None
    self._hold_until_done(worker)
```

`_hold_until_done` legt ihn in `_retired` und lässt ihn erst los, wenn
`isRunning()` nein sagt. Ein ersetzter Arbeiter geht denselben Weg über
`_retire`. `wait_for_workers` wartet am Ende auf alle — auch auf die in
`_retired`, sonst überlebt einer sein Fenster und nimmt den Prozess mit.

## Der Mauszeiger

Zeiger kommen aus `app/ui/cursors.py`, nie als `Qt.CursorShape` an der
Aufrufstelle. `cursor(rolle, widget)` gibt entweder eine eigene Zeichnung im
Akzent oder eine Systemform zurück — welche, entscheidet das Modul und nicht
der Anrufer.

Drei Dinge, die man beim Zeichnen einer neuen Rolle wissen muss:

* **Silhouette schlägt Bildidee.** Bei 32 Punkten wird ein Zeiger nicht
  gelesen. Der Schnittzeiger trug zuerst denselben Körper wie das Symbol der
  Werkzeugzeile und war ein Fleck mit Strich; erst die grobe Form — Linie,
  darüber und darunter eine Hälfte — erzählt etwas. **Angesehen wird auf vier
  Untergründen**: Viewport dunkel, Akzent (ein gewählter Körper!), Körpergrau,
  helles Thema.
* **Jede eigene Zeichnung trägt den dunklen Saum.** Der Akzent liegt über
  einem gewählten Körper auf sich selbst und wäre ohne ihn weg. Er entsteht
  aus zwei Durchgängen über dieselben Pfade, dick dunkel und dünn im Akzent.
* **Wo das System eine bekannte Form hat, gewinnt sie** (`SYSTEM`): geschlossene
  Hand beim Schieben, Verschiebekreuz am Griff. Sie folgt der eingestellten
  Zeigergröße und dem Hochkontrastmodus, unsere täte das nicht.

**Ein Maß in Millimetern gehört nicht an den Zeiger.** Der Pinselradius ist der
Fall, an dem das auffällt: Ein Zeiger hat feste Punktgröße und weiß nichts von
der Kamera — beim ersten Zoom behauptet er eine Größe, die er nicht mehr hat.
Was ein Weltmaß zeigt, gehört als Ring in die Szene.

**Gesetzt wird an einer Stelle**, `Viewport._update_cursor`. Alle Auslöser
melden nur ihren Zustand: `set_painting`, `set_measure_mode`,
`set_drag_cursor` (vom Interaktionsstil) und die Mausbewegung im
`eventFilter`. Verteilt auf die Aufrufer wäre jeder Pfad für sich richtig und
das Ergebnis trotzdem falsch — wer beim Loslassen den Auswahlzeiger setzt,
überschreibt damit den Pinsel. Die Rangfolge in `_resting_role` ist dieselbe
wie in `_on_picked`; laufen sie auseinander, verspricht der Zeiger etwas
anderes, als der Klick tut.

Drei Fallen an dieser Kette, alle drei schon zugeschnappt:

* **`setMouseTracking(True)`** auf dem Interactor, sonst kommt eine Bewegung
  erst mit gedrückter Taste — der Zeiger wüsste nie, worüber er schwebt.
* **VTK zählt Y von unten, Qt von oben.** Ohne die Umrechnung in
  `_note_pointer` sucht das Hover-Picking am gespiegelten Ort, was in der
  Bildmitte oft genug stimmt, um lange nicht aufzufallen.
* **Der Rückruf aus dem Interaktionsstil geht über `weakref`**, wie
  `on_context` und `on_pick` daneben. Eine starke Referenz baut die Schleife
  Stil → Viewport → Plotter → Interactor → Stil, und die ist der Absturz ohne
  Zeile am Ende eines Laufs.

**Gesucht wird erst, wenn die Maus steht** (`HOVER_DELAY_MS`, einmaliger
Timer). Bei jeder Bewegung zu picken hieße, den Tiefenpuffer hunderte Male in
der Sekunde im Qt-Hauptthread zu lesen. Ein Zug an der Kamera stoppt die Suche
ganz — wer dreht, will nicht wissen, was unter dem Zeiger liegt.

**Offscreen gibt es keinen Plotter**, und jeder Setzpfad steigt vorher aus: Ein
Test, der nur `_cursor_role` prüft, wäre auch dann grün, wenn im Fenster nie
ein Zeiger ankommt. `tests/test_cursors.py` hält deshalb eine Attrappe mit
genau der einen Methode, die benutzt wird.

## Barrierefreiheit

- **Keine Bedeutung allein über Farbe** (Regel 18). Immer eine zweite
  Kodierung: Muster, Schraffur, Symbol, Beschriftung.
- Differenzansicht in Blau/Orange als Vorgabe, nicht Rot/Grün.
- Analysekarten mit wahrnehmungsgleicher Palette (Viridis-Art), kein
  Regenbogen — der erzeugt Kanten, wo keine sind.
- Alles über die Befehlspalette erreichbar; Kürzel stehen daneben, so lernt man
  sie nebenbei. Undo und Redo gelten überall, auch im Chat.
- HiDPI, skalierbare Schrift, Kontrast in hellem und dunklem Thema,
  Anzeigeeinheit zwischen Millimeter und Zoll umschaltbar.

## Tests

Oberflächentests laufen offscreen (`QT_QPA_PLATFORM=offscreen`, von
`tests/conftest.py` gesetzt). Eine neue Ansicht ohne Test in `tests/test_ui.py`
oder einer der spezielleren Dateien ist unfertig.

## Die Ansicht

**Die Auswahlfarbe gehört dem Genauesten, was gewählt ist.** Ein Klick auf eine
Bohrung wählt zweierlei aus, den Körper und die Stelle; gefärbt wird die Stelle.
`highlighted_object()` gibt `None` zurück, solange ein Merkmal gewählt ist, und
`highlighted_faces()` nennt dessen Dreiecke — beide als eigene Auskunft, weil es
offscreen keinen Plotter gibt. Dass der Körper trotzdem ausgewählt ist, steht im
Objektbaum und in der Statusleiste; dieselbe Ausnahme gilt für einen Körper unter
einer Analysekarte (§19.1). Das gewählte Merkmal trägt seine Beschriftung auch
bei ausgeschalteter Überlagerung — ohne sie wäre die Aussage allein die Farbe
(Regel 18).

Gerechnet wird gegen das Netz der Szene, nicht gegen das dezimierte
Anzeigenetz: `face_indices` zählt dort. Den Unterschied fängt der Versatz
entlang der Flächennormalen ab (`FEATURE_PATCH_LIFT`).

Umgebungsverdeckung und Kontaktschatten weichen, solange eine Analysekarte
läuft: beide dunkeln nach, und die Karte färbt nach Zahlen — der abgelesene
Wert wäre ein anderer als der gemeldete. Beide hängen deshalb an einer
Eigenschaft (`ambient_occlusion`, `contact_shadows`) und nicht am Zustand des
Plotters: offscreen gibt es keinen, und ein Test, der sich dort überspringt,
prüft nie etwas.

Der Kontaktschatten ist **selbst projiziert**, nicht `enable_shadows`: VTKs
Schattenwurf verschattet ganze Seitenflächen schwarz und lässt die Ränder der
Platte auslaufen. Geworfen wird schräg — senkrecht projiziert liegt der
Schatten unter dem Körper und ist von ihm verdeckt.

**Der Schatten folgt der Kamera, weil das Licht es tut.** pyvistas Lichtsatz
hängt an der Kamera: ein Körper ist in jeder Ansicht von vorn beleuchtet. Eine
feste Weltrichtung für den Schatten passt deshalb zu *keinem* Blickwinkel —
sie stand hier, mit einer Begründung, die auf eine Standardansicht verwies, die
es so nicht gab. `shadow_direction` leitet sie aus der Kamerastellung ab,
`_redraw_shadows` zieht sie bei jedem Ansichtswechsel nach. Der Beobachter
hängt am **Interactor** (`EndInteractionEvent`) und nicht am Interaktionsstil:
den tauscht jeder Schemawechsel aus, und der Orientierungswürfel dreht an ihm
vorbei.

**Die Anwendung setzt ihre Startkamera selbst.** Ohne `view_from("iso")` beim
Aufbau erbt sie pyvistas Stellung über (1, 1, 1), und die eigene Vorgabe aus
`VIEW_DIRECTIONS` sieht nur, wer „Isometrisch" im Menü wählt — ein Sprung aus
einer Ansicht in eine andere, die man zu sehen glaubte.

**Ein Schatten fällt auf die Fläche, auf der sein Körper steht.** Nicht immer
auf die Platte: `_shadow_catchers` sucht zu jedem Körper die Flächen unter ihm
— die Druckplatte und jeden Körper, dessen Oberkante nicht höher liegt als
seine Unterkante. Ohne das löst sich der Schatten eines Turms auf einer 12 mm
hohen Grundplatte von ihm ab und taucht erst daneben auf. Beide Stücke werden
gezeichnet, und das ist kein Widerspruch: Licht, das an der Grundplatte
vorbeigeht, trifft die Druckplatte, und weil jedes Stück am Umriss seiner
Fläche geschnitten wird (`clip_polygon`, Sutherland-Hodgman), verdeckt die
Grundplatte genau den Teil, der sonst doppelt läge. Dasselbe Schneiden hält den
Schatten auf der Platte: außerhalb lag er auf blankem Hintergrund und
behauptete Boden, wo keiner ist. Die Plattenkante kommt aus `_bed_extent`,
gemerkt in `show_build_volume` — ohne gezeigten Bauraum gibt es nichts zu
schneiden.

**Was je Bild neu gerechnet wird, wird je Körper vorbereitet.** Der
Schattenumriss lief als Triangulierung über jeden Punkt des Anzeigenetzes: 129
ms bei zweiundachtzigtausend Dreiecken, je Körper und Szenenaufbau, im
Qt-Hauptthread. Die konvexe Hülle steht einmal (`_shadow_hull_of`), ein
Ansichtswechsel projiziert nur noch daraus. Und sie bekommt einen Kostendeckel:
bei einer feinen Kugel liegt *jeder* Punkt auf der Hülle, und die Rechnung wäre
teurer als das, was sie ersetzt. Über `SHADOW_HULL_POINTS` genügt eine
Stichprobe — plus die äußersten Punkte in vierzehn Hauptrichtungen, sonst
verliert ein gescannter Halter seine Ecken.

Zahlen an Bildern werden **angesehen, nicht nur gerechnet**. Der Radius der
Umgebungsverdeckung stand mit plausibler Begründung auf dem schwächsten Wert
seiner Messreihe; der doppelte ViewCube fiel erst im neu aufgenommenen
Handbuchbild auf. Beim Schatten war es dieselbe Sorte Fehler: der Kommentar
beschrieb, wohin er fallen sollte, und niemand hatte nachgesehen, wohin er
fiel.

**pyvista-Widgets werden nie weiterbenutzt, immer frisch gebaut.** Das
`AffineWidget3D` rechnet gegen die `user_matrix` seines Actors und merkt sie
sich über Züge hinweg — ein stehen gelassener Griff wendet den vorigen Zug
beim nächsten doppelt an, und nach einer Auswertung hängt er an einem Actor,
der nicht mehr im Bild ist. Und die API vor dem Aufruf lesen: `Off()` gab es
dort nie (`remove()`, `disable()`, `enable()` sind die Methoden), der
AttributeError verschwand in Qts Slot-Behandlung und fiel nirgends auf. Ein
Fake im Test spiegelt deshalb die **echte** API-Oberfläche, nicht die
vermutete — ein Fake mit `Off()` hätte den Absturz genau so versteckt wie
die Suite.

Zwei Nachbarn derselben Falle: pyvistas Widget schaltet beim Greifen auf
seinen Trackball-Stil um und stellt beim Loslassen **seinen** Standard
wieder her, nicht unseren — jedes Zugende ruft deshalb `set_navigation`,
sonst sind Auswahl-Klick, Kontextmenü und Schema nach dem ersten Zug weg.
Und der Skaliergriff (`app/ui/scale_widget.py`) ist diesem Widget
absichtlich Zeile für Zeile nachgebaut — wer dort etwas am
Interaktionsmuster ändert, ändert es an beiden Stellen.

## Die Zeichenfläche

Der Skizzeneditor (`app/ui/sketch_editor.py`) ist die zweite Ansicht, in der
gezeigt werden muss, was gleich passiert. Vier Zusagen, alle vier hatten
gefehlt:

**Was entsteht, hängt am Zeiger.** Linie, Kreis und Bogen zeigen ihre Vorschau,
bis der Klick sie festmacht. Ohne sie setzt ein Klick einen gestrichelten
Kreis, dann geschieht nichts, und beim zweiten steht plötzlich eine Linie da.

**Gefangen wird auf das Raster, ein vorhandener Punkt schlägt es.** Sonst risse
der Fang die Deckung auf, für die er da ist. Der Haken steht an der
Ebenenzeile, an ist die Vorgabe, ein Millimeter die Weite; ein Kreuz am Zeiger
zeigt, wohin ein Klick fiele — gefangen wird feiner, als das Raster gezeichnet
ist. Derselbe Fang gilt beim Ziehen eines Punktes, sonst wäre er eine Zusage
bis zum ersten Nachbessern.

**Raster und Beschriftung folgen dem Maßstab** (`grid_step`, Folge 1, 2, 5),
und das Rad zoomt auf den Zeiger. Eine feste Weite ist herausgezoomt eine
Fläche aus Linien und hineingezoomt ein Blatt mit vier Linien darauf.

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
