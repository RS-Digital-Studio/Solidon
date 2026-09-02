---
paths:
  - "app/ui/viewport.py"
  - "app/ui/qt_platform.py"
  - "app/ui/overlay.py"
  - "app/ui/cursors.py"
  - "app/ui/analysis_bar.py"
  - "app/ui/section_bar.py"
  - "app/ui/split_bar.py"
  - "app/ui/transform_bar.py"
  - "app/ui/explode_bar.py"
  - "app/ui/scale_widget.py"
  - "app/ui/snapshots.py"
---

# Regeln für die Ansicht

Alles, was im Viewport geschieht: was das Bild zeigt, was der Zeiger sagt, wie
die Platten liegen. Ausgegliedert aus `oberflaeche.md` — die allgemeinen
Regeln der Oberfläche gelten weiter und laden zusätzlich.

## Was nur das Bild zeigt

Vier Fehler am selben Tag, alle vier durch eine grüne Suite gekommen, alle vier
im gerenderten Fenster sofort zu sehen:

| Fehler | Warum kein Test ihn fand |
|---|---|
| Hauptknopf ohne Beschriftung | `click()` funktioniert auf einem leeren Knopf |
| Skala in vier von sechs Sprachen abgeschnitten | die Werte stimmten, nur die Breite nicht |
| Nebenfeld doppelt so hoch wie die Hauptfrage | ein Layout hat kein Richtig und Falsch |
| Aufklappmenü als erste Zeile über einer Frage | es tat genau das, was es sollte |

Die Regel dazu ist keine neue, sondern die aus §35 an ein Widget gerichtet:
**Was man nicht angesehen hat, ist ungeprüft.** Ein Dialog wird deshalb einmal
gerendert und angesehen, bevor er als fertig gilt.

**Und angesehen wird unter der echten Plattform.** Unter
`QT_QPA_PLATFORM=offscreen` hat Qt auf dieser Maschine null Schriftfamilien:
Jede Beschriftung wird ein leeres Kästchen, und **jede Breitenmessung ist
damit falsch**. Der erste Blick auf den Bogen sagte „die Skala passt"; unter
der echten Plattform brauchte sie in Portugiesisch 635 Punkte, wo 598 da
waren. Dieselbe Falle steht bei den erzeugten Bildern (`/erzeugen`) — sie gilt
für jede Messung an einem Widget, nicht nur für Bildschirmfotos.

Der Aufruf dafür ist drei Zeilen und braucht kein Fenster auf dem Schirm:

```python
app = QApplication([])
apply_style(app, "dark")
dialog = SupportDialog(kind=KIND_SURVEY)
dialog.show()
app.processEvents()
dialog.grab().save("bogen.png")
```

**Und wer ihn in mehreren Sprachen ansieht, installiert die Kataloge.**
`set_language` setzt eine Variable und sonst nichts; geladen wird über
`install_catalog(sprache, read_catalog(sprache))`, so wie `make_figures.py` es
tut. Ohne diese Zeile ist jedes Bild deutsch — und der Lauf sieht vollständig
aus, weil er sechs Dateien schreibt und sechs Zeilen ausgibt. Der
Rezeptdialog wurde am 25.08.2026 so „in sechs Sprachen geprüft"; aufgefallen
ist es erst am portugiesischen Bild, auf dem „Welche Maße soll man einstellen
können?" stand. **Die Gegenprobe kostet nichts: Sind zwei Bilder gleich groß,
zeigen sie dasselbe.**

Dazu `install_qt_translations(app, sprache)` (`app/ui/app.py`) — Qts eigene
Standardknöpfe kommen aus seinem Katalog, nicht aus unserem, und ohne den
Aufruf steht auf jedem Bild „Cancel", wo die Anwendung „Abbrechen" zeigt. Wer
das für einen Fund hält, sucht einen Fehler, den es nicht gibt.

**Für den Viewport gilt genau diese Zeile nicht.** `widget.grab()` malt den
Qt-Widgetbaum ab und weiß nichts von dem, was OpenGL in den Viewport
gezeichnet hat — das Bild kommt mit einer **schwarzen Mitte** zurück, und
schlimmer als kein Bild ist eines, das eine leere Ansicht behauptet. Was
OpenGL zeigt, holt nur der Bildschirm:

```python
window.show()  # wirklich zeigen, nicht offscreen
QApplication.primaryScreen().grabWindow(window.winId()).save("bild.png")
```

Vier weitere Dinge tragen einen solchen Prüfstand, alle vier am 24.08.2026
einmal gefehlt:

* **`bootstrap.load_operations()` vor dem ersten Registerzugriff**, sonst
  endet der erste Import in `unknown operation 'load'`.
* **Kein `QT_QPA_PLATFORM`.** Offscreen hat Qt hier null Schriftfamilien und
  VTK zeichnet gar nicht — beides ist genau das, was geprüft werden soll.
* **Die Schritte an einer `QTimer.singleShot`-Kette**, nicht in einer
  Warteschleife: die hängt bei sichtbarem Fenster. Und
  `faulthandler.dump_traceback_later`, damit ein Hänger sich meldet, statt zu
  schweigen. `window.start()` wird **nicht** gerufen — es öffnet beim ersten
  Start einen modalen Dialog, und der Prüfstand stünde.
* **`app.processEvents()` unmittelbar vor jedem Schuss.** VTK rendert sofort,
  die Qt-Widgets erst im nächsten Ereignisdurchlauf: Ohne das zeigte ein Bild
  eine Skizze in der Szene und daneben „Leere Skizze" in der Statuszeile —
  zwei Zustände in einem Bild, und beide echt. Wer dem geglaubt hätte, hätte
  einen Fehler gesucht, den es nicht gibt.

**Ob VTK überhaupt starten darf, entscheidet die wirksame Qt-Plattform.** Sie
steht beim Aufbau der `QGuiApplication` fest. Ein später gestartetes Werkzeug
kann `QT_QPA_PLATFORM` aus der Umgebung entfernen, macht aus einer laufenden
Offscreen-Anwendung aber keine Windows- oder XCB-Anwendung. Wer danach nur die
Variable liest, baut einen nativen VTK-Interactor ohne passenden Qt-Kontext;
der Prozess stirbt beim nächsten Fensteraufbau in
`render_window_interactor.initialize`. Deshalb fragt `viewport._available()`
zuerst `QGuiApplication.platformName()` und nimmt die Umgebungsvariable nur
vor dem Anwendungsaufbau als Rückfall.

**Und auf Wayland darf VTK gar nicht erst starten.** Seine Qt-Anbindung
übergibt `winId()` als X-Window; unter dem Wayland-Plugin ist das keine, VTK
findet kein Display, fällt auf EGL zurück und nimmt den Prozess mit
(`std::bad_array_new_length` — Martin Donecker, CachyOS, 28.08.2026). Deshalb
wählt `app/ui/qt_platform.py` **vor** der `QGuiApplication` xcb, sobald ein
X11-Display da ist — Qt 6 nähme in einer Wayland-Sitzung sonst von sich aus
Wayland, auch neben Xwayland —, und `_available()` lehnt ab, was trotzdem als
Wayland ankommt; `unavailable_hint()` sagt dann, was fehlt. In einer
Wayland-Sitzung lautet die Wahl `xcb;wayland`, nicht `xcb`: Qt geht die Liste
durch, und das X11-Plugin braucht neun Bibliotheken vom System, die das
Linux-Paket nicht mitbringt (`libxcb-cursor0` fehlt auf einem Ubuntu-GNOME
regelmäßig). Mit `xcb` allein hieße das kein Start; mit Wayland dahinter
startet die Anwendung ohne 3D-Ansicht, und der Hinweis nennt die Bibliothek —
mit `DISPLAY` die Bibliothek, ohne `DISPLAY` Xwayland. Wer die Plattform vor dem Aufbau
liest oder setzt, geht über diese eine Funktion — die Werkzeuge in `tools/`,
die `QT_QPA_PLATFORM` entfernen, weil sie das echte Fenster wollen, bauen sie
nicht nach.

Für eine Zeile, die nicht umbrechen kann — eine Skala, eine Knopfleiste —
lohnt daneben die Zahl: `sizeHint().width()` gegen `width()`, **in jeder
Sprache**. Was gequetscht wird, meldet Qt nicht.

### Ein Widget, das nachgibt, darf nicht weniger verlangen

Eine Leiste, die bei Enge auf Symbole umschaltet, ist die richtige Antwort auf
zu wenig Platz — und sie schließt einen Kreis, wenn man sie naiv baut:

    eng → Symbole → schmaler → kleinere Wunschbreite → Container gibt weniger
        → immer noch „eng" → nie zurück

Am 30.08.2026 an der Bewegen-Leiste gemessen: Bei einem **1600 Punkte breiten**
Fenster stand sie auf 677 und zeigte kein einziges Wort. Der Platz war da; sie
hat ihn nur nicht mehr verlangt.

**Wer nachgibt, verlangt weiter das Volle.** `sizeHint()` meldet die Breite
**mit** Beschriftung, auch während Symbole stehen; die gemerkte Zahl entsteht
im breiten Zustand und wird im engen nur verglichen. Damit bekommt die Leiste
den Platz, wo er da ist, und weicht nur, wo er wirklich fehlt.

Das ist dieselbe Lehre wie bei der Höhenverteilung der Karten
(`oberflaeche.md`, „Gerechnet wird nie mit den Höhen, die gerade gesetzt
wurden") — hier in der Breite und mit einem Zustand statt einer Zahl.

**Und zwei Nachbarn, beide am selben Tag bezahlt:**

* **`SizePolicy.Fixed` schützt nicht den Knopf, sondern lähmt die Leiste.** Es
  hebt deren Mindestbreite auf die Summe der Kinder (gemessen 1325 statt 708);
  ein enges Fenster quetscht dann trotzdem, und die Umschaltung kommt nie zum
  Zug. Was hilft, ist `layout.setSizeConstraint(SetNoConstraint)` — die Leiste
  darf schmaler werden als ihre Kinder wollen, und dann greift die Regel oben.
* **`SizePolicy.Ignored` ist keine abgeschwächte Form davon.** An den
  Zahlenfeldern gesetzt bekamen sie **null** Punkte und verschwanden ganz —
  schlimmer als die Quetschung, die es beheben sollte.

### Ein Messwert, der zu glatt ist, ist selbst der Befund

Dieselbe Leiste maß **677 in allen sechs Sprachen**, auf die Stelle genau. Die
Wörter sind verschieden lang — „Verschieben", „Move", „Mettre à l'échelle" —,
und eine identische Breite kann es nur geben, wenn **kein Wort mehr da ist**.
Die Zahl war das Symptom, nicht die Entwarnung.

Die Frage davor kostet nichts: **Sollte dieser Wert sich unterscheiden?** Wo
Sprache, Schrift oder Inhalt eingehen und trotzdem dieselbe Zahl herauskommt,
ist ein Weg abgeschnitten, den niemand abgeschnitten hat. Verwandt mit der
Gegenprobe aus `oberflaeche.md`: „Sind zwei Bilder gleich groß, zeigen sie
dasselbe" — dort als Beweis benutzt, hier als Alarm.

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
  helles Thema. (Der Schnittzeiger selbst ist seit dem 30.08.2026 wieder
  ausgebaut — er war fertig gezeichnet und wurde nie gesetzt, denn der
  Schnitt hat keine Klickgeste: seine Ebene wird an der Leiste gezogen. Die
  Lehre über die Silhouette bleibt; die Zeichnung war ihr Anlass.)
* **Eine gezeichnete Rolle braucht eine Setzstelle.** Der ausgebaute
  Schnittzeiger ist der Beleg: gezeichnet, begründet, nie gesetzt — der
  Kunde sah ihn nie, und niemand merkte es. `tests/test_cursors.py` hält
  seither beide Richtungen: Jedes gesetzte Rollen-Literal ist bekannt
  (sonst fällt es still auf den Systempfeil — „moving" statt „move" stand
  an der häufigsten Zuggeste), und jede gezeichnete Rolle wird irgendwo
  gesetzt.
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
  `on_context` und `on_pick` daneben (alle fünf in `_weak_callbacks`). Eine
  starke Referenz baut die Schleife Stil → Viewport → Plotter → Interactor →
  Stil, und die ist der Absturz ohne Zeile am Ende eines Laufs. Das ist **ein**
  Fall der allgemeinen Regel und nicht der einzige — sie steht oben unter „Ein
  Rückruf an ein eigenes Kind hält schwach", samt der Messung, die zeigt, dass
  ein Zeitgeber dasselbe anrichtet.

**Gesucht wird erst, wenn die Maus steht** (`HOVER_DELAY_MS`, einmaliger
Timer). Bei jeder Bewegung zu picken hieße, den Tiefenpuffer hunderte Male in
der Sekunde im Qt-Hauptthread zu lesen. Ein Zug an der Kamera stoppt die Suche
ganz — wer dreht, will nicht wissen, was unter dem Zeiger liegt.

**Offscreen gibt es keinen Plotter**, und jeder Setzpfad steigt vorher aus: Ein
Test, der nur `_cursor_role` prüft, wäre auch dann grün, wenn im Fenster nie
ein Zeiger ankommt. `tests/test_cursors.py` hält deshalb eine Attrappe mit
genau der einen Methode, die benutzt wird.

## Was im Skizzenmodus in dieser Datei steht

`viewport.py` trägt einen guten Teil des Skizzenmodus, und **seine Regeln
stehen nicht hier**, sondern in `zeichenflaeche.md` — dort, wo der Rest des
Editors steht. Die Datei lädt mit `sketch_editor.py` und nicht mit dieser; wer
eines der folgenden Stücke anfasst, liest sie zusätzlich:

| Was | Wo die Regel steht |
|---|---|
| `sketch_grid`, `grid_step_for`, `pixels_per_mm`, `LEAST_VIEW_PIXELS` | Raster und Maßstab |
| `show_sketch_cursor`, `sketch_cursor`, `CURSOR_PIXELS` | die Fangmarke und ihre 6,9 ms |
| `set_sketching`, `_sketch_hit`, `sketch_screen_at` | wohin ein Klick fällt |
| `set_sketch_pull`, `pull_cage`, `pulled_height`, `polyline_distance` | der Ziehgriff der Querschau |
| `MEASURE_GAP`, `DragValueBar.anchor` | die Zahl am Zeiger |
| `apply_wheel_zoom`, `view_on_plane`, `cameraMoved` | Zoom und Schwenk auf einer Ebene |

## Die Ansicht

### Die Auswahl hat eine Tiefe, und der Klick wandert durch sie

Drei Stufen: nichts, ein Körper, ein Merkmal (`Viewport.selection_depth`).
**Links wandert, rechts fragt** — und diese Aufteilung ist der Kern:

* **Der Linksklick geht eine Stufe.** Der erste wählt den Körper, der nächste
  das Merkmal unter dem Zeiger. Das Modell von Figma und Illustrator: erst die
  Gruppe, dann das Element darin. Vorher gewann sofort das Merkmal, und ein
  Körper mit erkannten Bohrungen war per Klick **überhaupt nicht auswählbar** —
  wer die Platte verschieben wollte, musste in den Objektbaum ausweichen.
* **Der Rechtsklick meint immer das Genaueste** (`_select_at(..., direct=True)`).
  Das folgt aus §18.5: Dort ist das Kontextmenü *am Merkmal* der Ort für Weg 1,
  „indem man auf die Stelle zeigt, die stört". Gestuft wäre diese Zusage an eine
  Vorbedingung geknüpft, die niemand kennt.
* **Ein offener Operationsdialog schaltet die Stufen ab**
  (`set_direct_picking`). Dann ist ein Klick eine *Antwort* und keine
  Navigation, und zwei Klicks für eine Antwort sehen aus wie ein verschluckter
  erster.
* **Escape geht zurück**, eine Stufe je Druck, hinter dem offenen Werkzeug in
  der Rangfolge von `MainWindow._escape`. Ohne ihn ist die Tiefe eine
  Einbahnstraße.

Zwei Dinge daran sind leicht falsch zu machen:

**Die Stufe wird aus der Auswahl gelesen, nicht nebenher geführt.** „Im Körper
drin" heißt genau „ein Merkmal dieses Körpers ist gewählt". Ein eigenes Feld
daneben wäre eine zweite Wahrheit — die Auswahl kommt auch aus dem Objektbaum,
und der weiß von keinem Feld im Viewport. Dazu kommt: `objectPicked` läuft
synchron durch den Baum zurück und setzt `_selected`, also muss die Stufe
**vor** dem Senden gelesen werden.

**Der Zeiger stellt dieselbe Frage mit derselben Rechnung**
(`_would_pick_feature` → `_click_target`). Das ist die schon bekannte Regel bei
`_resting_role`, einen Schritt weiter: Ein Zeiger, der die Merkmalsform über
einer Bohrung zeigt, während der Klick den Körper wählt, verspricht etwas, das
nicht eintritt. So wird die Stufe zugleich sichtbar, ohne dass ein Satz darüber
irgendwo stehen muss.

### Ein Merkmal hat eine Reichweite

`_feature_at` hatte keine, und das war der gemeldete Fehler: Es nahm das
Merkmal mit dem nächsten **Mittelpunkt**, es gab also immer einen Gewinner,
sobald der Körper ein Merkmal hatte. An der Korpusplatte wählte ein Klick auf
die Deckfläche sieben Millimeter neben einer Bohrung die Bohrung (8,1 mm zum
Bohrungsmittelpunkt gegen 36,1 mm zur Mitte der 80 mm langen Deckfläche), und
ein Klick nahe der Stirnseite wählte die Stirnfläche.

Gemessen wird gegen die **Dreiecke** des Merkmals
(`geom.mesh.distance_to_triangles`), gegen den nächsten Ort *auf* dem Dreieck
und nicht gegen den nächsten Eckpunkt — die Deckfläche der Platte hat zwei
Dreiecke, ein Klick in ihre Mitte liegt vierzig Millimeter von jedem Eckpunkt
entfernt. Die Reichweite wächst mit der Diagonale (`FEATURE_REACH_SHARE`),
weil im dezimierten Anzeigenetz gepickt wird (§18.9).

Drei Folgen davon:

* **Ein Klick trifft die Oberfläche, nie die Achse.** Der Mittelpunkt einer
  Bohrung liegt im Leeren. Drei Tests zeigten dorthin und prüften damit die
  Rechenweise statt einen Klick; wer einen neuen schreibt, nimmt die
  Bohrungswand (`on_the_bore_wall`).
* **Ein Merkmal ohne eigene Dreiecke bleibt über seinen Mittelpunkt
  erreichbar** — eine offene Kantenschleife hat keine, und sie ist der Befund,
  den man am ehesten anklicken will.
* **Vorbereitet wird je Körper und Auswertung** (`_feature_geometry`), mit dem
  Hüllquader als billiger Vorprüfung: Die Frage stellt der Zeiger bei jeder
  Ruhepause neu (90 ms), und der genaue Abstand ist nur für die ein oder zwei
  Merkmale nötig, deren Quader ihn überhaupt erreicht. Geleert wird in
  `show_scene` — die Dreiecke gehören einer Auswertung, nicht dem Viewport.

**Und jeder Klickpfad rechnet über `_from_view` in die Szene zurück** (§25).
Der Rechtsklick tat es nicht und die Zeigersuche auch nicht: Auf Platte 2
fragten beide eine Bettbreite daneben, fanden dort meist keinen Körper, und der
Rechtsklick hob die Auswahl auf, statt das Menü zu ihr zu zeigen.

### Ein Klick ist eine Blickrichtung, kein Punkt

Der Abschnitt darüber setzt voraus, dass unter dem Zeiger ein Dreieck liegt.
**Bei einer Bohrung liegt dort keines**, und das war der zweite gemeldete
Fehler an derselben Stelle: „wir erwischen oft nur die Oberfläche und kommen
nicht zur Bohrung". Gemessen am echten `vtkCellPicker` in einem sichtbaren
Fenster, Korpusplatte, Bohrung 32 Bildpunkte breit, Pixel neben der
Bohrungsmitte:

| | Draufsicht | Isometrisch | Vorderansicht |
|---|---|---|---|
| 0–8 px | **kein Treffer** | `hole_1` | `face_3` |
| 12 px | `hole_1` | **kein Treffer** | `face_3` |
| 16 px | `face_2` | `face_2` | `face_3` |

Zwei Ursachen, und beide liegen vor der Reichweite:

* **Senkrecht in eine Durchgangsbohrung trifft der Strahl nichts.** Die
  Zylinderwand liegt parallel zu ihm, dahinter kommt keine Fläche. Der Picker
  gab nichts zurück, `_on_left_click` machte daraus `objectPicked.emit("")` —
  ein Klick mitten in die Bohrung **hob die Auswahl auf**. Ausgerechnet in der
  Ansicht, in der man ein Lochbild anklickt.
* **Landet der Strahl daneben auf der Deckfläche, gewinnt sie immer.** Ihr
  Abstand ist null, der der Bohrung größer als null; die Reichweite ist eine
  Obergrenze und kein Vorrang. Gemessen gab schon ein Punkt 0,4 mm neben dem
  Bohrungsrand `face_2`, bei einer Reichweite von 0,95 mm.

Gefragt wird deshalb der **Sichtstrahl** (`_pick_ray` → `_bore_aim`, gerechnet
in `bore_span`): Welche Bohrung durchquert er, bevor er auf dem Sichtbaren
landet? Drei Eigenschaften daran sind tragend:

* **`until` ist der Auftreffpunkt, und ohne diese Grenze wird es falsch.** In
  der Vorderansicht liegt hinter der Stirnfläche jede Bohrung der Platte; was
  der Strahl erst dahinter durchquert, hat niemand gemeint. Die dritte Spalte
  oben ist die Gegenprobe und bleibt unverändert `face_3`.
* **Der Achsbereich kommt aus den Dreiecken des Merkmals**, nicht aus `depth`
  und nicht aus dem Hüllquader — der kennt die Achse nicht, und eine schräge
  Bohrung hat beides. Ohne die Begrenzung reicht der Zylinder unendlich weit
  und eine Bohrung am einen Ende fängt Klicks am anderen.
* **Zurück kommt ein Punkt auf der Achse**, nicht der Auftreffpunkt. Damit
  bleibt die ganze Kette dahinter unberührt — Stufung, Kontextmenü und Zeiger
  bekommen einen Punkt wie immer, und von einem Punkt im Loch findet
  `_feature_inside` die Bohrung. Auf der Achse und nicht in der Mitte des
  Durchtritts: Ein Punkt über der Öffnung liegt der Deckfläche näher als der
  Bohrungswand, und dann gewinnt wieder die Fläche.

Der entartete Fall ist der wichtigste und der einzige, den man leicht verliert:
**Blickt man senkrecht in die Bohrung, läuft der Strahl parallel zur Achse**,
es gibt keinen Ein- und Austritt durch den Mantel, und die quadratische
Gleichung dazu hat keinen Leitkoeffizienten. Wer dort durch null teilt,
verliert genau die Draufsicht.

**Gefragt wird an drei Stellen, und an allen drei derselbe Aufruf**
(`_aim_at`): Linksklick, Rechtsklick, Zeigersuche. Der Zeiger kostet damit
einen Zell-Pick je Ruhepause statt eines Blicks in den Tiefenpuffer — gemessen
0,16 ms, und die Zusage darunter ist es wert: Ein Zeiger, der die
Merkmalsform über einer Bohrung zeigt, wo der Klick sie nicht wählt,
verspricht etwas, das nicht eintritt. **Nicht** gefragt wird beim Messen,
Bemalen und Ziehen — dort ist eine Stelle auf der Oberfläche gemeint, und ein
Punkt in der Luft wäre falsch.

**Und die Reichweite wirkt hier als Zielhilfe**, nicht als Grenze: Gezielt wird
in Pixeln, und der Rand einer M3-Bohrung ist an einem großen Teil wenige davon
breit. Derselbe Wert wie beim Klick auf die Fläche eines Merkmals, denn es ist
dieselbe Frage — wie weit daneben meint noch dies. Bei 24 Pixeln, also weit
außerhalb der Bohrung, bleibt es die Fläche.

### Und wo kein Merkmal ist, ist trotzdem ein Körper

Der Abschnitt darüber löst die **Bohrung**, weil sie ein Merkmal ist, auf das
man zeigen kann. Ein **rechteckiger Ausschnitt** ist keines: vier Wandflächen,
von denen keine „richtiger" ist als die andere — und bei senkrechtem Blick
liegen sie parallel zum Strahl, dort ist so wenig ein Dreieck zu treffen wie an
der Bohrungswand. Der Picker gab nichts zurück, und ein Klick in den Ausschnitt
**hob die Auswahl auf**.

Entschieden wird dort deshalb nicht, welches Merkmal gemeint ist, sondern
**welcher Körper**: Wer in eine Öffnung zeigt, hat auf das Teil gezeigt.
`_through_aim` fragt dafür die **konvexe Hülle** (`geom.mesh.hull_planes` und
`ray_span_in_hull` — die Rechnung steht im Kern, in `app/ui` gibt es kein
`trimesh` und soll keines geben). Drei Eigenschaften, alle drei tragend:

* **Die Hülle und nicht der Hüllquader.** Der Quader eines L-Profils reicht
  weit ins Leere, und damit wäre die Zusage aus §18.5 weg, dass ein Klick
  daneben die Auswahl aufhebt — der einzige Weg, sie ohne den Objektbaum
  loszuwerden. Gemessen: 0 bis 30 px in einem 12×8-Ausschnitt geben jetzt den
  Körper, ab 60 px unverändert `face_2`, und 100 mm neben dem Teil nichts.
* **Die Kerbe zählt mit, und das ist gewollt.** Durch den fehlenden Quadranten
  eines L-Profils läuft der Strahl in der Hülle, ohne das Netz zu treffen. Ein
  Kriterium, das das ausnimmt, müsste „Loch" von „Einbuchtung" unterscheiden —
  eine Unterscheidung, die niemand trifft, der auf ein Teil zeigt und zwei
  Bildpunkte neben die Silhouette kommt.
* **Nur wenn sonst nichts da ist.** Gefragt wird erst, wenn weder eine Fläche
  noch eine Bohrung getroffen wurde. Damit kostet der Normalfall nichts, und
  die Hülle wird je Körper einmal gerechnet (`_object_hulls`, geleert mit den
  Merkmalsdreiecken in `show_scene`).

**Der Kostendeckel ist derselbe wie beim Schattenumriss, und aus demselben
Grund:** Die exakte Hülle von `dense_1m.stl` braucht 5084 ms, weil bei einer
feinen Kugel jeder Punkt auf ihr liegt. Über eine Stichprobe von 4096 Punkten
plus den äußersten in sechs Achsenrichtungen sind es 20 ms; an der Korpusplatte
liefern beide dasselbe, zwölf Flächen und 32 000 mm³. Gerechnet wird über
**Halbräume**, nicht über ein Hüllnetz — ein Strahl gegen 8202 Hülldreiecke
wäre wieder das, was die Stichprobe gerade vermeidet.

### Was gefärbt wird

**Die Auswahlfarbe gehört dem Genauesten, was gewählt ist.** Ein Klick auf eine
Bohrung wählt zweierlei aus, den Körper und die Stelle; gefärbt wird die Stelle.
`highlighted_object()` gibt `None` zurück, solange ein Merkmal gewählt ist, und
`highlighted_faces()` nennt dessen Dreiecke — beide als eigene Auskunft, weil es
offscreen keinen Plotter gibt. Dass der Körper trotzdem ausgewählt ist, steht im
Objektbaum und in der Statusleiste; dieselbe Ausnahme gilt für einen Körper unter
einer Analysekarte (§19.1). Das gewählte Merkmal trägt seine Beschriftung auch
bei ausgeschalteter Überlagerung — ohne sie wäre die Aussage allein die Farbe
(Regel 18).

**Schweben und Auswahl sind zwei sichtbare Zustände.** Unter dem Zeiger liegt
eine halbtransparente Flächenmarkierung samt Merkmalszeiger und Beschriftung;
die Auswahl ist deckend und bleibt im Objektbaum sowie in der Statusleiste
stehen. So kündigt Schweben an, was ein Klick wählen würde, ohne bereits eine
Auswahl zu behaupten.

**Eine Bohrungsmarkierung verschließt die Öffnung nicht.** Ihre Innenwand wird
von beiden Öffnungen durchscheinend gezeichnet. Deckend liegt die Farbe der
fernen Wand aus schrägem Blick über dem ganzen Loch und sieht wie ein Deckel
aus, obwohl geometrisch keiner da ist; nur eine Seite zu zeichnen lässt die
Markierung im Gegenblick dagegen ganz verschwinden. Andere Merkmalsflächen
bleiben deckend und beidseitig sichtbar.

**Eine Änderungsvorschau besitzt die Modellfarben.** Solange Vorher und Nachher
gleichzeitig gezeigt werden, werden Auswahl- und Schwebefläche am Modell
ausgeblendet: Orange bezeichnet dann ausschließlich entfernte, Blau
ausschließlich hinzugekommene Geometrie. Objektbaum, Statusleiste und
Beschriftung halten die Auswahl weiter fest. Beim Festhalten der Vorher-Ansicht
kehrt die Auswahlmarkierung zurück; nach dem Schließen der Vorschau ebenso.

**Nur Sichtbares trägt eine Markierung.** Ein ausgeblendeter Körper und ein
Körper auf einer gerade nicht gezeigten Druckplatte hinterlassen weder
Merkmalsfläche noch Beschriftung frei im Raum. Nach einer Neuberechnung bleibt
der Körper ausgewählt; ist das gewählte Merkmal dabei verschwunden, fällt die
Auswahl auf den Körper zurück. Ein technischer Name und eine sichtbare Fläche
sind ebenfalls keine Alternative: Wird ein erkanntes Merkmal eindeutig einem
benannten Bausteinmerkmal zugeordnet, übernimmt der bleibende Name die aktuellen
`face_indices` des Netzes.

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

### Zwei Werte hängen am Thema, und beide aus demselben Grund

Die Farben des Themas sind nicht die einzige Größe, die zwischen hell und
dunkel wechselt. **Beleuchtung und Deckkraft wirken auf verschieden hellem
Grund verschieden stark**, und wer sie als eine Zahl führt, hat sie für genau
ein Thema richtig eingestellt.

**Das Frontlicht** (`HEADLIGHT`): VTK stellt fünf Lichter auf, und nur eines —
das Headlight aus der Kamerarichtung — trifft die zum Betrachter zeigenden
Seitenwände; die vier Kameralichter stehen über und hinter dem Teil. Der Körper
ist im hellen Thema 2,45-mal dunkler als im dunklen (`#78828e` gegen
`#b9c4d0`), Schattierung multipliziert, also sind auf ihm auch alle
Helligkeitsunterschiede 2,45-mal kleiner — 0,0155 gegen 0,0380 zwischen zwei
Außenwänden. Das ist kein Beleuchtungsfehler, sondern Multiplikation, und
deshalb hilft dort nur mehr Licht: 0,45 statt 0,25.

**Die Schattendeckkraft** (`SHADOW_OPACITY`): Derselbe Wert 0,18 ergab 1,44
Kontrast auf der hellen Plattenfläche und 1,05 auf der dunklen — das
Vierundfünfzigfache an Luminanzunterschied. Ein Schatten hat auf hellem Grund
viel weiter nach unten Platz. Im hellen Thema sind es deshalb 0,03; das ergibt
1,06 und damit genau die Lautstärke des dunklen Themas („der Schatten wie im
dunklen Thema reicht", Robert, 30.08.2026).

**Zwei Wege, die vorher gemessen und verworfen wurden**, damit sie niemand
erneut geht: Ein ambienter Anteil am Körper hebt alle Flächen gleich und macht
ihn dabei *flacher* (Wandunterschied 1,19 → 1,12, Abhebung von der Platte
8,41 → 5,75). Ein Glanzanteil ändert an den Wänden fast nichts und am Deckel
gar nichts.

**Und die Falle beim Bauen solcher Paare**: Eine themenabhängige Konstante
nützt nichts, solange die Zeichenstelle weiter die Konstante liest statt den
gemerkten Wert — und ein Test, der nur die Methode prüft, bleibt dabei grün.
Gemessen: Nimmt man den Ruf aus `set_theme` heraus, fällt kein Test.
`tests/test_viewport_decisions.py` hält deshalb je Paar **drei** Zusagen: die
Richtung der Werte, dass `set_theme` sie setzt, und dass das Zeichnen sie
liest.

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
schneiden. **Und sie gehört der Platte des Körpers**, nicht der ersten
(`_bed_outline_for`): seit die Betten nebeneinander stehen, liegt der Umriss
eines Körpers auf Platte 2 eine Bettbreite weiter, und am Umriss von Platte 1
geschnitten wäre sein Schatten restlos weg.

## Was VTK beschriftet, ist ASCII — und sonst nichts

Die Griffbeschriftung ist ein `vtkStringArray`. pyvista lehnt darin jedes
Zeichen außerhalb von ASCII ab, und zwar nicht mit einer Warnung:

```
ValueError: String array contains non-ASCII characters that are not supported by VTK
```

Der ganze Griffaufbau stürzt damit ab. **Das ist der eine Ort in der
Oberfläche, an den ein übersetzter Text nicht darf** — überall sonst zeichnet
Qt, und Qt kann jede Sprache.

**Der Fall ist am 30.08.2026 passiert und wäre auf Deutsch nie aufgefallen.**
Am Griff standen kurz ein Doppelpfeil und der Name der Fläche aus
`feature_name`. Deutsch ist „Oberseite", „Unterseite", „Vorderseite" — alles
ASCII. Französisch nicht:

| | |
|---|---|
| `Oberseite` | `Face supérieure` |
| `Rückseite` | `Arrière` |
| `Linke Seite` | `Côté gauche` |
| `Rechte Seite` | `Côté droit` |

Vier von sechs. Ein Kunde auf Französisch hätte beim Klick auf eine Fläche
einen Absturz bekommen, und ein Torlauf in deutscher Umgebung hätte
geschwiegen — die Sorte Fehler, die es bis zum Kunden schafft.

**Wohin der Text stattdessen gehört:** in die Statusleiste. Sie zeigt bei
gewähltem Merkmal ohnehin „Platte · Oberseite", dort zeichnet Qt, und dort
darf jede Sprache stehen. Am Griff bleibt, was keine Übersetzung braucht —
`X`, `Y`, `Z`, `S` und `<->` für eine Fläche, die nur vor und zurück kennt.

Gesichert durch `tests/test_selection.py::test_nothing_on_the_gizmo_leaves_ascii`,
und zwar mit genau diesen vier französischen Namen als Eingabe. Ein Absatz
hier wird gelesen, wenn jemand ihn sucht; der Test wird rot, wenn jemand es
wieder tut.

## Mehrere Druckplatten

Jede Platte hat ihren eigenen Nullpunkt, und `arrange_bed` setzt Platte 2 an
denselben Ort wie Platte 1 — das ist richtig, denn beide werden einzeln
gedruckt. Ein Bett für alle zeigt davon das Falsche: zwei identische Sockel
lagen Punkt auf Punkt übereinander, und gemeldet wurde es als „bei Projekten
mit mehreren Platten sehe ich trotzdem nur eine".

`show_build_volume` zeichnet deshalb **ein Bett je Platte**, mit `PLATE_GAP`
nach +X aufgereiht (`plate_shift`); eine gewählte Einzelplatte bekommt wieder
genau eines. Drei Dinge hängen daran:

* **Die erste Platte bleibt, wo sie ist.** Nach +X und nicht um die Mitte
  verteilt: Eine Szene mit einer Platte sieht danach Bild für Bild aus wie
  vorher, und wer eine zweite dazubekommt, sieht sie kommen statt die erste
  wegrutschen zu sehen.
* **Die Actors tragen die Nummer im Namen.** pyvistas `name=` ersetzt, was
  denselben Namen hat — mit festen Namen bliebe von vier Betten eines übrig.
* **Ein Klick muss zurückgerechnet werden** (`plate_at`, `_from_view`, ganz oben
  in `_on_picked`). Was der Nutzer trifft, liegt in der Ansicht; was eine
  Operation als Ort bekommt, muss in der Szene liegen. Ohne die Umkehrung setzte
  ein Klick auf Platte 2 die Bohrung eine Bettbreite daneben — und weil dort
  meistens nichts ist, hätte sie stumm nichts getan.

Der Versatz liegt mit dem Auseinanderziehen (§18.8) zusammen in
`_view_offset`, damit jede Zeichenstelle beides bekommt oder keines. Was
**nicht** mitgeht, sind die Überlagerungen in Szenenkoordinaten — Maße,
Schnittebene, Griffe. Sie folgten schon dem Auseinanderziehen nicht; das gehört
zusammen behoben, nicht halb.

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

**Ein Layout, das nur bei der geprüften Breite stimmt, ist ungeprüft.** Drei
Fehler wurden am selben Tag sichtbar, und alle drei erst, als das Handbuch die
Fenster bildschirmfüllend aufnahm statt in einem Kasten von 1180 Punkten: Der
Bausteinkatalog legte seine Gruppen ineinander, weil der Kachelmodus seine
Zeilen beim Einfügen rechnet und ein späteres `setSizeHint` nur speichert —
`doItemsLayout()` nach einer echten Änderung. Die zehn Bedingungsknöpfe der
Skizze blieben in zwei Zeilen à fünf, weil diese Aufteilung für den
Laptopschirm gedacht war und seither überall galt. Und das Raster der
Zeichenfläche war ein halber Millimeter fein, weil `MIN_GRID_PX` auf sieben
stand — ein Wert, der bei kleinem Fenster nie auffiel. Wer eine Ansicht ändert,
sieht sie bei **beiden** Enden an: der Mindestgröße und dem vollen Bildschirm.

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

## Die Skizze ist Vordergrund, der Körper Zusammenhang (29.08.2026)

Während des Zeichnens bleibt der vorhandene Körper sichtbar, aber mit
`SKETCH_CONTEXT_OPACITY` deutlich leiser als die Arbeitsgeometrie. Die normale
Transparenz von 45 Prozent war im echten Handbuchbild lauter als die Skizze;
16 Prozent lassen Form und Lage erkennen, ohne eingeprägte Details mit dem
Umriss konkurrieren zu lassen. Kontaktschatten und orange Körperauswahl treten
in dieser Zeit ebenfalls zurück. Beim Verlassen stellt der gewählte
Darstellungsmodus seine Deckkraft wieder her.

`OverlayHost` meldet dem Viewport linke, rechte und untere Verdeckung über
`set_zone_margins`. Links und rechts bleiben Überlagerungen; nur die
Skizzenkamera liest die untere Höhe. In orthografischer Projektion verschiebt
`occluded_view_shift` Position und Fokus gemeinsam um genau die halbe verdeckte
Bildhöhe. Das verändert weder Blickrichtung noch Maßstab und wird beim
Verlassen zurückgenommen. `view_on_plane` und `show_span_on_plane` setzen die
Verschiebung nach jeder neuen Kamerastellung erneut — deshalb bleiben Umriss,
Pfeil, Kreuz und Live-Zahl auch in der Querschau oberhalb der Werkzeugkarte.
Auch `view_from` verwirft den gespeicherten Weltvektor, bevor die ViewBar eine
absolute Kamerastellung setzt, rechnet den heutigen Ausgleich neu ein und
meldet die neue Hauptansicht an das Ebenenfeld. Ein gespeicherter Versatz darf
nie von einer Kamera abgezogen werden, die ihn nicht mehr enthält.

Fangmarke und unfertige Kurve besitzen eigene Actors. Ein voller
`show_sketch`-Aufbau räumt sie nicht zwischen zwei Gesten weg; ein
Zeigerschritt aktualisiert bei gleicher Topologie nur Punkte und rendert
Fangmarke plus Vorschau gemeinsam. Maßkarten, Achsenbuchstaben und
Ziehgriff-Beschriftungen sind ungreifbar (`pickable=False`) und können deshalb
keinen Klick von Zeichenebene oder Umriss abfangen.
Der innere Schaft, das Kreuz und die Beschriftung *Abtragen* erscheinen nur,
wenn genau ein bearbeitbarer Körper gewählt ist. Ohne ihn bleibt der Pfeil
nach außen vollständig bedienbar; ein Zug nach innen zeigt weder Drahtkörper
noch Tiefe und erzeugt keine Operation.

## Die Kamera hat einen zweiten Treiber (02.09.2026)

Die 3D-Maus (`app/ui/spacemouse.py`, Konzept `konzept-3d-maus-2026-08`) fährt
dieselbe Kamera wie die Maus — kein fünftes Navigationsschema, kein Modus,
keine Operation. Drei Regeln:

* **Die Abbildung ist eine reine Funktion.** `camera_step` bekommt sechs
  Achsen, eine Stellung, eine Zeitspanne und zwei Einstellungen und gibt eine
  Stellung zurück. Kein Qt, kein VTK, kein HID darin — jeder Achsenfehler
  (Vorzeichen, Bezugssystem) wird dort behoben und in
  `tests/test_spacemouse.py` mit einem Test je Achse festgehalten. Wer die
  Wirkung einer Achse ändert, macht genau einen Test rot. Objektmodus ist die
  Vorgabe (die Kappe ist das Teil, alle sechs Achsen — Robert, 02.09.2026),
  „Richtung umkehren" ist der Kameramodus.
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

