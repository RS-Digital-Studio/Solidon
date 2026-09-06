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

Die Regel ist keine neue, sondern die aus §35 an ein Widget gerichtet:
**Was man nicht angesehen hat, ist ungeprüft.** Ein Dialog wird deshalb einmal
gerendert und angesehen, bevor er als fertig gilt — vier Fehler kamen an einem
Tag durch eine grüne Suite und waren im gerenderten Fenster sofort zu sehen
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

**Und angesehen wird unter der echten Plattform.** Unter
`QT_QPA_PLATFORM=offscreen` hat Qt auf dieser Maschine null Schriftfamilien:
Jede Beschriftung wird ein leeres Kästchen, und **jede Breitenmessung ist
damit falsch** (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).
Dieselbe Falle steht bei den erzeugten Bildern (`/erzeugen`) — sie gilt
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
aus, weil er sechs Dateien schreibt und sechs Zeilen ausgibt
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).
**Die Gegenprobe kostet nichts: Sind zwei Bilder gleich groß,
zeigen sie dasselbe.**

Dazu `install_qt_translations(app, sprache)` (`app/ui/app.py`) — Qts eigene
Standardknöpfe kommen aus seinem Katalog, nicht aus unserem, und ohne den
Aufruf steht auf jedem Bild „Cancel", wo die Anwendung „Abbrechen" zeigt. Wer
das für einen Fund hält, sucht einen Fehler, den es nicht gibt.

**Für den Viewport gilt genau diese Zeile nicht.** `widget.grab()` malt den
Qt-Widgetbaum ab und weiß nichts von dem, was der Renderer auf der
Grafikkarte in den Viewport gezeichnet hat — das Bild kommt mit einer
**schwarzen Mitte** zurück, und schlimmer als kein Bild ist eines, das eine
leere Ansicht behauptet. Was die Grafikkarte zeigt, holt nur der Bildschirm:

```python
window.show()  # wirklich zeigen, nicht offscreen
QApplication.primaryScreen().grabWindow(window.winId()).save("bild.png")
```

Vier weitere Dinge tragen einen solchen Prüfstand, alle vier am 24.08.2026
einmal gefehlt:

* **`bootstrap.load_operations()` vor dem ersten Registerzugriff**, sonst
  endet der erste Import in `unknown operation 'load'`.
* **Kein `QT_QPA_PLATFORM`.** Offscreen hat Qt hier null Schriftfamilien und
  die Ansicht baut keinen Renderer — beides ist genau das, was geprüft werden
  soll.
* **Die Schritte an einer `QTimer.singleShot`-Kette**, nicht in einer
  Warteschleife: die hängt bei sichtbarem Fenster. Und
  `faulthandler.dump_traceback_later`, damit ein Hänger sich meldet, statt zu
  schweigen. `window.start()` wird **nicht** gerufen — es öffnet beim ersten
  Start einen modalen Dialog, und der Prüfstand stünde.
* **`app.processEvents()` unmittelbar vor jedem Schuss.** `render()` zeichnet
  die Ansicht sofort, die Qt-Widgets malen erst im nächsten
  Ereignisdurchlauf: Ohne das zeigte ein Bild
  eine Skizze in der Szene und daneben „Leere Skizze" in der Statuszeile —
  zwei Zustände in einem Bild, und beide echt. Wer dem geglaubt hätte, hätte
  einen Fehler gesucht, den es nicht gibt.

**Ob der Renderer überhaupt starten darf, entscheidet die wirksame
Qt-Plattform.** Sie steht beim Aufbau der `QGuiApplication` fest. Ein später
gestartetes Werkzeug kann `QT_QPA_PLATFORM` aus der Umgebung entfernen, macht
aus einer laufenden Offscreen-Anwendung aber keine Windows- oder
XCB-Anwendung. Wer danach nur die Variable liest, baut ein natives
Renderfenster ohne passenden Qt-Kontext — mit VTK starb der Prozess so beim
nächsten Fensteraufbau in `render_window_interactor.initialize`, und ein
wgpu-Renderer ohne Grafikfläche stirbt nicht höflicher. Deshalb fragt
`viewport._available()` zuerst `QGuiApplication.platformName()`, nimmt die
Umgebungsvariable nur vor dem Anwendungsaufbau als Rückfall und fragt erst
danach `factory.available()` nach dem wgpu-Adapter.

**Und auf Wayland wird die Ansicht nicht gebaut.** Der wgpu-Fensterweg ist
nur unter X11 und Xwayland geprüft; den nativen Wayland-Betrieb von
rendercanvas hat noch niemand gefahren (Registerpunkt in `ROADMAP.md`). Die
Weiche ist älter als der Renderer: VTKs Qt-Anbindung übergab `winId()` als
X-Window, fand unter dem Wayland-Plugin kein Display und nahm den Prozess mit
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

**Wer nachgibt, verlangt weiter das Volle.** `sizeHint()` meldet die Breite
**mit** Beschriftung, auch während Symbole stehen; die gemerkte Zahl entsteht
im breiten Zustand und wird im engen nur verglichen. Damit bekommt die Leiste
den Platz, wo er da ist, und weicht nur, wo er wirklich fehlt
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

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

Die Wörter sind verschieden lang — „Verschieben", „Move", „Mettre à l'échelle" —,
und eine identische Breite kann es nur geben, wenn **kein Wort mehr da ist**.
Die Zahl war das Symptom, nicht die Entwarnung
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

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
`set_drag_cursor` (vom Navigator über `on_cursor`) und die Mausbewegung im
`eventFilter`. Verteilt auf die Aufrufer wäre jeder Pfad für sich richtig und
das Ergebnis trotzdem falsch — wer beim Loslassen den Auswahlzeiger setzt,
überschreibt damit den Pinsel. Die Rangfolge in `_resting_role` ist dieselbe
wie in `_on_picked`; laufen sie auseinander, verspricht der Zeiger etwas
anderes, als der Klick tut.

Drei Fallen an dieser Kette, alle drei schon zugeschnappt:

* **`setMouseTracking(True)`** auf dem Widget des Renderers, sonst kommt eine
  Bewegung erst mit gedrückter Taste — der Zeiger wüsste nie, worüber er
  schwebt.
* **Der Vertrag zählt Bildpunkte wie Qt** — von oben links, in Gerätepixeln.
  pygfx zählt in logischen Bildpunkten, und die Umrechnung mit dem
  Geräteverhältnis liegt **einmal** im Renderer, nicht an den Zeichenstellen.
  (VTK zählte Y von unten, und bis zum 05.09.2026 spiegelte `_note_pointer`
  selbst.) Wer die Umrechnung an einer Zeichenstelle wiederholt, rechnet
  doppelt, und das Hover-Picking sucht am falschen Ort — was bei einem
  Geräteverhältnis von 1,0 immer stimmt und deshalb lange nicht auffällt.
* **Die Rückrufe des Navigators gehen über `weakref`** — `on_cursor` wie
  `on_context` und `on_pick` daneben (alle in `_weak_callbacks`, gebündelt als
  `NavigatorCallbacks`), und der Zeiger-Zuhörer am Renderer (`_listen_to`)
  ebenso. Eine starke Referenz baut die Schleife Navigator → Viewport →
  Renderer → Zuhörer → Viewport, und die ist der Absturz ohne Zeile am Ende
  eines Laufs. Das ist **ein** Fall der allgemeinen Regel und nicht der
  einzige — sie steht oben unter „Ein Rückruf an ein eigenes Kind hält
  schwach", samt der Messung, die zeigt, dass ein Zeitgeber dasselbe anrichtet.

**Gesucht wird erst, wenn die Maus steht** (`HOVER_DELAY_MS`, einmaliger
Timer). Bei jeder Bewegung zu picken hieße, den Tiefenpuffer hunderte Male in
der Sekunde im Qt-Hauptthread zu lesen. Ein Zug an der Kamera stoppt die Suche
ganz — wer dreht, will nicht wissen, was unter dem Zeiger liegt.

**Offscreen gibt es keinen Renderer** (`_available()` meldet sich ab, und
`Viewport.renderer` bleibt `None`), und jeder Setzpfad steigt vorher aus: Ein
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

Seit dem 03.09.2026 schiebt links im Schema `solidon` **auch** die Ansicht.
Das ändert an der Stufung nichts: `_left_up` trennt Klick und Zug an der
Zugschwelle des Systems, und nur der Klick wandert (siehe unten).

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
sobald der Körper ein Merkmal hatte
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

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

**Und jeder Klickpfad rechnet über `_from_view` in die Szene zurück** (§25) —
Linksklick, Rechtsklick und Zeigersuche gleichermaßen; auf Platte 2 fragt sonst
einer eine Bettbreite daneben
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

### Ein Klick ist eine Blickrichtung, kein Punkt

Der Abschnitt darüber setzt voraus, dass unter dem Zeiger ein Dreieck liegt.
**Bei einer Bohrung liegt dort keines** — in der Draufsicht trifft ein Klick in
die Bohrungsmitte nichts, und schon wenige Bildpunkte neben ihr gewinnt die
Deckfläche (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Zwei Ursachen, und beide liegen vor der Reichweite:

* **Senkrecht in eine Durchgangsbohrung trifft der Strahl nichts.** Die
  Zylinderwand liegt parallel zu ihm, dahinter kommt keine Fläche. Der Picker
  gab nichts zurück, `_on_left_click` machte daraus `objectPicked.emit("")` —
  ein Klick mitten in die Bohrung **hob die Auswahl auf**. Ausgerechnet in der
  Ansicht, in der man ein Lochbild anklickt.
* **Landet der Strahl daneben auf der Deckfläche, gewinnt sie immer.** Ihr
  Abstand ist null, der der Bohrung größer als null; die Reichweite ist eine
  Obergrenze und kein Vorrang.

Gefragt wird deshalb der **Sichtstrahl** (`_pick_ray` → `_bore_aim`, gerechnet
in `bore_span`): Welche Bohrung durchquert er, bevor er auf dem Sichtbaren
landet? Drei Eigenschaften daran sind tragend:

* **`until` ist der Auftreffpunkt, und ohne diese Grenze wird es falsch.** In
  der Vorderansicht liegt hinter der Stirnfläche jede Bohrung der Platte; was
  der Strahl erst dahinter durchquert, hat niemand gemeint; die Vorderansicht
  ist die Gegenprobe und wählt weiter die Stirnfläche.
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
einen Oberflächen-Pick je Ruhepause statt eines Blicks in den Tiefenpuffer —
gemessen 0,16 ms unter VTK, und die Zusage darunter ist es wert: Ein Zeiger, der die
Merkmalsform über einer Bohrung zeigt, wo der Klick sie nicht wählt,
verspricht etwas, das nicht eintritt. **Nicht** gefragt wird beim Messen,
Bemalen und Ziehen — dort ist eine Stelle auf der Oberfläche gemeint, und ein
Punkt in der Luft wäre falsch.

**Und die Reichweite wirkt hier als Zielhilfe**, nicht als Grenze: Gezielt wird
in Pixeln, und der Rand einer M3-Bohrung ist an einem großen Teil wenige davon
breit. Derselbe Wert wie beim Klick auf die Fläche eines Merkmals, denn es ist
dieselbe Frage — wie weit daneben meint noch dies. Bei 24 Pixeln, also weit
außerhalb der Bohrung, bleibt es die Fläche.

### Beim Messen zeigt der Zeiger, wohin der Klick fällt

Der Abschnitt darüber gilt der **Auswahl**: Dort fragt der Zeiger dieselbe
Rechnung wie der Klick, damit er nichts verspricht, was nicht eintritt. Beim
Messen gilt dasselbe, und dort fehlte es — mit demselben Ergebnis, nur
umgekehrt: Der Kern **zieht** einen Messklick auf die nächste Ecke oder Kante
(`geom.measure.snap`), und im Bild geschah das erst *nach* dem Klick. Wer zielt,
zielte blind (Robert, 03.09.2026: „bei messen ist das zielen relativ schwer").

Drei Sachen hängen daran, und jede war für sich falsch:

* **Die Fangweite gehört in Bildpunkte** (`MEASURE_SNAP_PIXELS`, 16). Der Kern
  rechnet in zwei Prozent der Modelldiagonale, weil er kein Bild hat — an einem
  200 mm langen Teil vier Millimeter. Herangezoomt sind das zweihundert
  Bildpunkte und der Fang reißt den Punkt quer über die Fläche; herausgezoomt
  sind es zwei und es gibt keinen Fang mehr. `_snap_radius_at` misst den
  Maßstab an der Stelle (`_pixels_per_mm_at`, zwei Punkte quer zur
  Blickrichtung durch dieselbe Projektion — wie `pixels_per_mm`) und gibt dem
  Kern seine Weite in Millimetern. Ohne Bild kommt `None` zurück, und dann
  bleibt es bei der Weite des Kerns.
* **Gefangen wird nur, was man sieht.** Das ist die Hälfte, die im Kern lag:
  `visible_edges` nimmt scharfe und offene Kanten, `corner_points` nur Punkte
  mit drei sichtbaren Kanten. Über alle Dreieckskanten gerechnet fing ein Klick
  zwei Millimeter neben der Ecke mit Abstand **null** auf der Diagonalen der
  Deckfläche — auf einer Linie, die es im Bild nicht gibt.
* **Und die Marke steht vor dem Klick da.** `_preview_snap` bei jeder Ruhepause
  des Zeigers, dieselbe Rechnung wie der Klick (`_snap_for_measure`, ein
  Aufruf, zwei Anrufer). Beim Winkelmessen bleibt es bei der Merkmalssuche —
  dort wählt man ebene Flächen, und deren Hervorhebung *ist* die Zielhilfe.

Die Marke ist ein Kreuz mit einem Punkt in der Mitte, **in der Bildebene**
(`_screen_axes`) und in fester Bildgröße (`SNAP_MARK_PIXELS`,
`SNAP_DOT_PIXELS`). Beides ist gemessen und nicht gewählt: Entlang der
Weltachsen gezeichnet war sie in der isometrischen Ansicht auf ein Drittel
verkürzt und im gerenderten Fenster kaum zu finden, und in Millimetern wüchse
sie beim Hineinzoomen quer über das Teil.

**Worauf gefangen wurde, sagt die Größe** — Ecke groß, Kante mittel, freie
Stelle klein — und ein Satz in der Beschreibung der Ansicht
(`snap_sentence`, gelesen von Bildschirmlesern). Nicht die Farbe (Regel 18),
und nicht die Statuszeile: Die trägt beim Messen den Fortschritt („Erster Punkt
gewählt"), und ein Satz, der bei jeder Mausbewegung wechselt, überschriebe ihn.
Der Satz gehört auch **nicht** in die Szene — ein übersetzter Text am
Renderer stünde in sechs Sprachen an einer Stelle, die keine Prüfung sieht
(siehe „Was am Griff steht, ist ASCII").

Weg ist die Marke, sobald der Zeiger das Bild verlässt, das Werkzeug wechselt
oder die Szene neu aufgebaut wird. Die Maße überleben eine Auswertung, die
Marke nicht: Sie zeigt auf eine Ecke, die dieser Schritt entfernt haben kann.

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
  loszuwerden
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).
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
offscreen keinen Renderer gibt. Dass der Körper trotzdem ausgewählt ist, steht im
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
Renderers: offscreen gibt es keinen, und ein Test, der sich dort überspringt,
prüft nie etwas.

Der Kontaktschatten ist **selbst projiziert** und hängt an keinem
Schattenwurf des Renderers: VTKs `enable_shadows` verschattete ganze
Seitenflächen schwarz und ließ die Ränder der Platte auslaufen, und die eigene
Projektion hat den Rendererwechsel unverändert überstanden. Geworfen wird
schräg — senkrecht projiziert liegt der Schatten unter dem Körper und ist von
ihm verdeckt.

**Der Schatten folgt der Kamera, weil das Licht es tut.** Das Frontlicht des
Renderers hängt an der Kamera: ein Körper ist in jeder Ansicht von vorn beleuchtet. Eine
feste Weltrichtung für den Schatten passt deshalb zu *keinem* Blickwinkel —
sie stand hier, mit einer Begründung, die auf eine Standardansicht verwies, die
es so nicht gab. `shadow_direction` leitet sie aus der Kamerastellung ab,
`_redraw_shadows` zieht sie bei jedem Ansichtswechsel nach — am Ende jeder
Kamerageste (`on_end` des Navigators), nach jedem Schritt der 3D-Maus und
nach jeder Kameravorgabe, nicht an einem Ereignis des Renderers. (Bis zum
05.09.2026 hing dafür ein Beobachter an VTKs `EndInteractionEvent`, weil der
Orientierungswürfel am Interaktionsstil vorbei drehte; das Achsenkreuz des
eigenen Renderers ist Anzeige und kein Griff, `set_axes_marker`, und niemand
bewegt die Kamera mehr an der Ansicht vorbei.)

### Zwei Werte hängen am Thema, und beide aus demselben Grund

Die Farben des Themas sind nicht die einzige Größe, die zwischen hell und
dunkel wechselt. **Beleuchtung und Deckkraft wirken auf verschieden hellem
Grund verschieden stark**, und wer sie als eine Zahl führt, hat sie für genau
ein Thema richtig eingestellt.

**Das Frontlicht** (`HEADLIGHT`): Der Renderer stellt fünf Lichter auf
(`LIGHT_KIT` in `gfx_renderer.py` — der Lichtsatz, den PyVista und VTK
aufstellten), und nur eines — das Frontlicht aus der Kamerarichtung — trifft
die zum Betrachter zeigenden Seitenwände; die vier Kameralichter stehen über
und hinter dem Teil. Der Körper
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
Aufbau erbt sie die Startstellung des Renderers, und die eigene Vorgabe aus
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

## Was die Ansicht sich merkt (03.09.2026)

**Darstellung (massiv, mit Kanten, Drahtgitter, transparent), Schattierung
und Projektion sind Einstellungen**, und ihre zwölf Menüeinträge tragen ein
Häkchen — nach dem Muster von Thema und Navigation: drei
`QActionGroup`s mit Häkchen, drei `action_`-Methoden, die setzen, merken und
speichern, und `_apply_settings` wendet sie beim Start an
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026). Der Skizzenmodus
stellt Darstellung und Projektion weiterhin **direkt am Viewport** um und
nimmt es beim Verlassen zurück — das ist eine Leihgabe und keine Entscheidung
des Nutzers, also wird sie nicht gespeichert.

### Durchsichtige Körper werden von hinten nach vorn gezeichnet

Der Fund kam aus dem Quelltext (3d-druck-85): Ohne Tiefenschälung mischt ein
Renderer halbdurchsichtige Flächen in der Reihenfolge, in der die Aktoren
angelegt wurden. Unter VTK war das zweimal gemessen nicht behebbar — Depth
Peeling meldete Erfolg und fuhr nie (`LastRenderingUsedDepthPeeling=0` bei
stimmenden Voraussetzungen), und `vtkDepthSortPolyData` sortiert nur
**innerhalb** eines Aktors; der Aufruf wurde deshalb nie eingebaut, denn ein
Aufruf, der nichts bewirkt, sieht in einem Jahr aus wie einer, der etwas
bewirkt (dieselbe Entscheidung wie bei Mica und `DWMWA_BORDER_COLOR` am
Fensterchrom). pygfx mischt Durchscheinendes gewichtet und
reihenfolgeunabhängig (`weighted_blend`) und sortiert je Bild selbst nach dem
Abstand zur Kamera — die Regel darunter bleibt dieselbe, und der Viewport
rechnet sie weiter über den Vertrag.

**Was trägt, ist die Ordnung der Aktoren selbst** (`_order_by_depth`): Sie
werden nach dem Abstand ihres Mittelpunkts zur Kamera neu eingehängt, der
fernste zuerst. Das ist der Maleralgorithmus auf Objektebene — richtig
für getrennte Körper, machtlos bei sich durchdringenden, und genau der
gemeldete Fall
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Drei Dinge daran sind tragend:

* **Sie hängt an `_draw`, nicht an ihren Anlässen.** Die Kamera ändert sich an
  einem Dutzend Stellen — `view_from`, Radzoom, Zugende, 3D-Maus,
  Skizzenkamera —, und wer sie dort einzeln nachzöge, vergäße eine. Der erste
  Anlauf tat genau das und war deshalb an `show_scene` gehängt: Dort steht die
  Kamera noch auf der alten Stellung, `view_from` kommt danach, und im Bild
  änderte sich nichts.
* **Sie merkt sich, wofür sie geordnet hat** (Kameralage und Körperliste).
  An der Zeichenstelle läuft sie sonst bei jedem Bild, auch mitten in einem
  Zug.
* **Umgehängt wird über den Vertrag** (`set_draw_order`), und der Renderer
  setzt die Reihenfolge um, ohne ein Element aufzugeben: Die Elemente
  bleiben, was sie sind — mit Namen, Sichtbarkeit und Matrix. Ein Weg über
  Entfernen und Neuanlegen verlöre all das. (pygfx sortiert Durchscheinendes
  je Bild selbst nach dem Abstand zur Kamera; sein `set_draw_order` legt
  keine eigene Reihenfolge darüber, weil die gemessen genau das aufhöbe.)

### Die Druckplatte scheint durch, wenn etwas darunter liegt

Ein Teil unter der Platte war **vollständig** unsichtbar: `culling = "back"`
wirft die Rückseite der Ebene weg, also sieht man **von unten** hindurch. Von
oben blieb sie undurchdringlich. `BED_SUNKEN_OPACITY` ist 0,45 — praktisch
alles, und dieselbe Zahl, die der Darstellungsmodus *Transparent* schon führt
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

**Und sie gilt nur, solange wirklich etwas darunter liegt** (`sunken_body`,
gefragt an der Szene und nicht am Bild). Das ist Roberts ausdrückliche
Fassung, und sie nimmt der Sache ihre einzige Abwägung: Die Fläche existiert,
damit der Kontaktschatten auf etwas fällt — über einer leeren Platte bleibt
sie deckend, und die Frage stellt sich gar nicht.

Drei Dinge hängen daran:

* **Nur die gefüllte Ebene** (`_bed_surfaces`, je Platte eine). Das Raster ist
  ohnehin ein Drahtgitter mit 0,35, der Bauraum sind Linien; verdeckt hat
  immer nur `bed_surface_<n>`.
* **Die Frage wird bei jeder Auswertung neu gestellt** (`_apply_bed_
  transparency` in `show_scene`). Die Platte steht schon, seit der Drucker
  gewählt wurde; ob etwas unter ihr liegt, ändert sich mit jedem Schritt.
* **Und sie zählt zur Tiefenordnung** (`sees_through`, `_order_by_depth`):
  Eine durchscheinende Fläche unter *allen* Körpern ist genau der Fall, den
  eine falsche Zeichenreihenfolge ruiniert — ohne sie wäre falsch dargestellt,
  was die Durchsicht zeigen soll (Hinweis 3d-druck-85).

**Ganz weg gibt es weiterhin**, und das ist etwas anderes: *Ansicht →
Druckplatte zeigen* (Strg+Umschalt+D) blendet Bett, Bauraum und Maßstab aus,
gemerkt über den Neustart. Für „das Teil einmal ganz allein sehen" ist das
direkter als Durchsichtigkeit.

### Einpassen nimmt den gewählten Körper, wenn einer gewählt ist

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

**Im Skizzenmodus gilt es nicht.** Dort ist die Skizze der Gegenstand und der Körper der Zusammenhang (siehe „Die Skizze ist Vordergrund, der Körper Zusammenhang“ weiter unten). Pos1 gehört dort ohnehin dem Blatt (`SketchCanvas.fit_view`); offen war nur die ViewBar, und die rahmt jetzt auch dort die ganze Szene.

**Und der automatische Weg folgt der Auswahl nicht**
(`_fit_once_for` ruft `reset_camera(follow_selection=False)`). Dort wird
gerahmt, *weil* die Szene entwachsen ist — ein neuer 400er Körper
neben einem Zwei-Millimeter-Teil, die Kamera in seinem Inneren. Ein Rahmen um
den kleinen Ausgewählten beantwortete genau das nicht.

Der Test dazu (heute `test_fitting_frames_the_bodies_with_air`) war in seiner ersten
Fassung **grün, als ich die Änderung wieder ausbaute**: Er maß
`_selected_bounds` und `_fit_once_for`, also die Vorarbeit, und nicht die
Kamera. Offscreen gibt es keinen Renderer, und `reset_camera` steigt an seiner
Wache aus, bevor irgendetwas gerahmt wird. Erst eine Attrappe am Vertrag
(`RecordingRenderer.reset_bounds` in `tests/render_fakes.py`) hat den
Unterschied gemessen.

### Die Kantensuche läuft einmal je Netz, nicht einmal je Aufbau

`extract_feature_edges` war der teuerste einzelne Posten eines Szenenaufbaus
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Der Kommentar bei `FEATURE_EDGE_LIMIT` rechnet mit „dreißig Millisekunden
je Körper und Szenenaufbau". Die Rechnung stimmt; ihre **Annahme** stimmt
nicht — ein Szenenaufbau ist nicht selten. `show_scene` läuft bei
jeder Auswahl eines Körpers, jedem Themenwechsel und jedem Schritt der
Schieber für Explosion, Schnitt und Schicht.

**Genau dieselbe Fehleinschätzung stand schon einmal beim Schatten** und
ist dort behoben: `_shadow_hulls_for` nennt sie in eigenen Worten („sein
Docstring nannte das ‚einmal je Szenenaufbau' und meinte damit ‚selten' —
das stimmte nicht"). Die Kanten daneben blieben zwanzig Tage stehen. Der Cache
ist deshalb **dieselbe Bauart**: `_edge_meshes` neben `_shadow_splits`,
verglichen wird die **Identität** des Netzes und nicht sein Inhalt —
ein Hash über Millionen Dreiecke wäre nicht billiger als die Suche,
die er spart. Und der Schnittschieber trifft ihn aus demselben Grund
absichtlich nicht: `cut` erzeugt dort wirklich ein neues Netz.

**Was die Messung widerlegt hat**, und das gehört dazu: Die Vermutung war
`DISPLAY_DECIMATION_ABOVE` (500 000 Dreiecke, **je Körper**) — 32
Körper mit im Mittel 171 000 kommen zusammen auf fünfeinhalb
Millionen, von denen drei über der Schwelle liegen. Der Verdacht war
falsch: `_for_display` kostet beim ersten Aufbau 1044 ms und danach **0 ms**,
weil `DISPLAY_CACHE_KEPT` (4) für diese drei reicht. Wer die Schwelle
angefasst hätte, hätte nichts gewonnen.

### Jeder Ansichts-Setter prüft auf Änderung

Sieben von acht Szenenaufbauten waren unnötig — ein Klick auf einen Körper,
ein Themenwechsel, derselbe Wert noch einmal —, und an einem großen Modell
kostet jeder drei Viertel Sekunden. Sichtbar wurde es als Fehler: Jeder
Aufbau nimmt dem Actor seine Vorschau-Matrix, und nach einem Zug am Griff
sprang der Körper an die alte Stelle zurück, bevor er an der neuen landete
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Die Prüfungen im Einzelnen:

| Setter | verglichen wird |
|---|---|
| `set_hidden` | die Menge (hatte sie seit je — die Vorlage) |
| `set_plate` | die Plattennummer |
| `set_explosion` | der **normalisierte** Wert, nicht das Argument: zweimal ein negativer Faktor meint zweimal null |
| `set_display_mode` | der Modus |
| `set_shading` | die Schattierung |
| `set_section` | Ebene **und** Dicke |
| `set_analysis_map` | Identität der Karte, Gleichheit der Kennung |
| `set_theme` | das Thema, seit es eines merkt |

**`set_theme` konnte als Einziger nicht prüfen**, und der Grund war kein
Versäumnis am Vergleich, sondern ein fehlendes Feld: Der Viewport merkte
sein Thema nirgends. `self._theme` beginnt bei `None`, damit der erste Aufruf
durchläuft — das Fenster setzt das Thema beim Start, und ein
vorbelegtes Feld ließe die Startfarben ungesetzt. Seine Prüfung steht
**ganz vorn**, vor dem Umfärben der Leisten: Ändert sich das Thema
nicht, ist jede Zeile darunter Arbeit für dasselbe Bild.

**Der Test dafür misst nicht bei allen dasselbe.** `set_theme` steigt
offscreen vor `show_scene` aus (`if self.renderer is None`); ein Test über
den Aufbau-Zähler wäre dort grün, ohne etwas zu sagen. Geprüft
wird er deshalb an seiner Wirkung (den gesetzten Farben), die anderen sieben am
Zähler. Gegenprobe: jede der acht Prüfungen **einzeln** ausgebaut,
achtmal rot — ein Lauf mit allen acht Mutationen hätte beim ersten
abgebrochen und die übrigen sieben ungeprüft gelassen.

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
* **Die Elemente tragen die Nummer im Namen.** Der Name ist die Adresse, unter
  der ein Test (`item_of`) und das Aufräumen ein Element finden — mit festen
  Namen wären vier Betten nicht auseinanderzuhalten, und unter PyVista, dessen
  `name=` Gleichnamiges ersetzte, blieb von vieren eines übrig.
* **Ein Klick muss zurückgerechnet werden** (`plate_at`, `_from_view`, ganz oben
  in `_on_picked`). Was der Nutzer trifft, liegt in der Ansicht; was eine
  Operation als Ort bekommt, muss in der Szene liegen. Ohne die Umkehrung setzte
  ein Klick auf Platte 2 die Bohrung eine Bettbreite daneben — und weil dort
  meistens nichts ist, hätte sie stumm nichts getan.

Der Versatz liegt mit dem Auseinanderziehen (§18.8) zusammen in
`_view_offset`, damit jede Zeichenstelle beides bekommt oder keines. **Maße und
Fangmarke gehen seit dem 03.09.2026 mit**; was noch nicht mitgeht, ist die
Schnittebene.

**Und das Schwierige daran ist nicht die Rechnung, sondern die Zuordnung.**
`view_point_of` braucht einen Körper, und in der Szene liegen die Platten
*übereinander* — `arrange_bed` setzt Platte 2 an denselben Nullpunkt. Ein Punkt
in Szenenkoordinaten gehört damit zu beiden, und `_object_at` kann die Frage
dort gar nicht beantworten. Beantwortbar ist sie **im Bild**, wo die Betten
nebeneinander stehen: `_object_at_view` prüft den Hüllquader **plus** Versatz
gegen einen Ansichtspunkt.

Gefragt wird deshalb beim **Klick** und nicht beim Zeichnen: Dort liegt der
Ansichtspunkt vor. Ein Maß merkt sich das Ergebnis je Punkt
(`Measurement.object_ids` — zwei Enden dürfen zu zwei Körpern gehören,
`object_id` daneben benennt das Maß als Ganzes und reicht nicht), die Vorschau
in `_snap_owner`. Ohne Kennung bleibt ein Punkt, wo er ist; ein Versatz, den
man nicht zuordnen kann, ist keiner.

**Was je Bild neu gerechnet wird, wird je Körper vorbereitet.** Der
Schattenumriss lief als Triangulierung über jeden Punkt des Anzeigenetzes: 129
ms bei zweiundachtzigtausend Dreiecken, je Körper und Szenenaufbau, im
Qt-Hauptthread. Die konvexe Hülle steht einmal (`_shadow_hull_of`), ein
Ansichtswechsel projiziert nur noch daraus. Und sie bekommt einen Kostendeckel:
bei einer feinen Kugel liegt *jeder* Punkt auf der Hülle, und die Rechnung wäre
teurer als das, was sie ersetzt. Über `SHADOW_HULL_POINTS` genügt eine
Stichprobe — plus die äußersten Punkte in vierzehn Hauptrichtungen, sonst
verliert ein gescannter Halter seine Ecken.

Zahlen an Bildern werden **angesehen, nicht nur gerechnet**
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

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

**Der Griff wird nie weiterbenutzt, immer frisch gebaut.** Er rechnet gegen
die Matrix seines Ziels beim Greifen und merkt sie sich über den Zug — ein
stehen gelassener Griff wendete den vorigen Zug beim nächsten doppelt an, und
nach einer Auswertung hinge er an einem Element, das nicht mehr im Bild ist.
Das galt für PyVistas Widget und gilt für `gizmo.Gizmo` genauso, weil die
Rechnung dieselbe ist. Und die Attrappen der Suite (`tests/render_fakes.py`)
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
  `Viewport._on_pointer` reicht jedes Ereignis erst an den Zeiger, dann an
  Griff und Skalierwürfel, zuletzt an den Navigator — eine Vorfahrt an einer
  Stelle statt dreier Beobachter am Interactor.
* **Ein Klick ist ein Klick, auch mit Zittern**, und ein Klick, der nichts
  wählt, lässt die Taste der Kamera (`tests/test_navigator.py`,
  `test_a_wobbly_click_stays_a_click` und
  `test_where_nothing_is_chosen_the_camera_keeps_the_button`).
* **Die Tabelle `_NAVIGATION` ist ohne Fenster prüfbar.** `tests/test_navigator.py`
  fährt sie gegen ein Renderer-Doppel — welches Schema auf welche Taste was
  tut, und wo die Kamera danach steht.

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
