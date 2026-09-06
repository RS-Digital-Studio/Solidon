---
paths:
  - "app/ui/session.py"
  - "app/ui/loading.py"
  - "app/ui/leash.py"
  - "app/ui/splash.py"
  - "app/ui/main_window.py"
---

# Regeln für Wartezeit und Nebenläufigkeit

Was geschieht, während gerechnet wird (§2.8): Fortschritt, Abbruch, Threads,
und die Frage, wann das Fenster etwas anderes zeigen darf als das Ergebnis.
Ausgegliedert aus `oberflaeche.md` — die allgemeinen Regeln der Oberfläche
gelten weiter und laden zusätzlich.

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

Vier Bedingungen, alle vier tragend:

* **Nur bei leerem Bild.** Steht ein Körper da, bleibt er stehen; wer
  entscheidet das, ist `MainWindow._update_veil`.
* **Unter den Karten, nicht darüber** (`OverlayHost.set_veil`). Über ihnen wäre
  es ein Vorhang ohne Ausgang.
* **Erst nach 200 ms — außer die Wartezeit ist sicher.** Ein leeres Projekt
  ist schneller gerechnet, und eine Anzeige, die dabei aufblitzt, ist Unruhe
  ohne Auskunft. Beim Öffnen eines Projekts **mit Schritten** kommt sie
  dagegen sofort (`begin(..., at_once=True)`): Die Wartezeit ist dort sicher,
  und jede unbedeckte Millisekunde gehört dem Punkt darunter.
* **Solange sie steht, ist die Ansicht verborgen, nicht nur verdeckt**
  (`appeared`/`ended` → `middle_stack.setVisible`). Das Ansichtsfenster ist
  ein natives Fenster (die Grafikfläche des Renderers, an die wgpu zeichnet):
  Auf dem Bildschirm liegt es über jedem gemalten
  Geschwister, egal was die Qt-Stapelung sagt, und bis zu seinem ersten
  Render zeigt es alte Pixel — Startbildschirm oder Schwarz. Genau so sah
  Robert sechs Sekunden „Absturz", während der Schleier unsichtbar darunter
  lag. **Und `widget.grab()` sieht davon nichts:** Es malt den Qt-Baum ab
  und zeigte den Schleier, den der Bildschirm nie zeigte — Beweisbilder für
  diese Zone macht nur `grabWindow` (siehe „Was nur das Bild zeigt").

Deckend gezeichnet, mit dem Verlauf aus `viewport_colours` — ein
halbdurchsichtiges Qt-Widget über dem nativen Renderfenster zeigt die
Fensterfarbe, nicht die Ansicht dahinter.

**Die Ladeanzeige beginnt später, als das Warten beginnt.** Sie hängt am
Fortschritt der Auswertung; was *davor* liegt — `load()` für eine Projektdatei,
`read_bytes()` für ein Modell —, sieht sie nicht, und ihre 200 ms kommen
obendrauf. Diese Zeile der Tabelle bedient `waiting()` in `main_window.py`, ein
Kontextmanager um genau eine Rechnung: Datei lesen, Dialog aufbauen, Slicer
suchen. Als Kontextmanager, weil ein Wartezeiger, der an einem Fehlerausgang
stehen bleibt, aussieht wie ein hängendes Programm — und eine Frage, die
darunter gestellt wird, sagt zweierlei. `_offer_recovery` liegt deshalb
außerhalb.

**Seit dem 03.09.2026 gilt das nur noch unterhalb von acht Megabyte.** Bei
einer 3MF zählt `import_plan` die Körper und Dreiecke der ganzen Baugruppe,
bevor eine Operation entsteht (§11, §32) — gemessen an einer Datei von 63 MB
mit 32 Körpern und 5 476 596 Dreiecken sind das **14,1 s**, während das Lesen
von der Platte 0,09 s kostet. Nicht das Lesen ist teuer, sondern das Zählen.

`Session.import_model_async` schiebt deshalb den Plan in einen Arbeiter, und
die Ladeanzeige greift dort sehr wohl: Der Fortschritt läuft über die
Modelldateien des Archivs, bei einer großen Baugruppe achtundzwanzig Meldungen.
Unterhalb der Grenze (`PLAN_IN_WORKER_ABOVE`, gemessene 0,18 s je MB, also etwa
1,4 s bei acht MB) bleibt es beim geraden Weg unter `waiting()` — ein Arbeiter
für einen Plan, der in Mikrosekunden steht, verschöbe das Ergebnis hinter die
Ereignisschleife, ohne dass jemand darauf gewartet hätte.

Zwei Fallen dabei, beide gemessen und beide teuer:

**Der Wartezeiger des Aufrufers steht noch, wenn der Weg gerade durchläuft.**
`with waiting(): self.session.import_model_async(path)` ist richtig — unterhalb
der Grenze steht der Zeiger, darüber kehrt der Aufruf sofort zurück und die
Ladeanzeige übernimmt. Aber ein Fehler, der aus dem synchronen Zweig kommt,
erreicht seinen Slot **innerhalb** dieses `with`, und ein Fehlerdialog unter
dem Wartezeiger ist genau das Fenster, das zugleich fragt und bittet zu warten.
`_on_import_failed` nimmt ihn deshalb selbst zurück, bevor es `show_error`
ruft.

**Und `wait_for_idle` muss jeden Arbeitertyp kennen.** Es kannte den neuen
nicht und kehrte zurück, bevor überhaupt eine Operation auf dem Stapel lag —
wer danach die Szene fragte, bekam eine leere. Wer einen Arbeiter dazubaut,
trägt ihn dort ein; sonst wartet die Schleife auf einen Lauf, den es noch gar
nicht gibt.

**Und seine Antwort trägt das Dokument, für das er lief.** Zwischen Start und
Antwort kann ein neues Projekt offen sein, und das trägt wieder eine eigene
`src_1`: Der verspätete Fehler des alten Imports räumte sie aus dem **neuen**
Dokument, samt Nutzdaten (Gesamtreview 05.09.2026, UI-01).
`Session._project_generation` zählt bei jedem `_reset_for` hoch, der Stempel
reist in den Slots mit, und `_stale_import` lässt eine veraltete Meldung
fallen — dieselbe Frage, die `_outdated` für die Auswertung beantwortet. Wer
einen weiteren Arbeiter am Dokument baut, gibt ihm denselben Stempel mit; und
was ein Arbeiter an Widgets meldet, geht als **Signal** (`_VariantWorker.progressed`),
nie als gebundene Widgetmethode im Rückruf (UI-14).


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

### Ein Arbeiter erbt von `leash.Worker` und schreibt `work`

**Niemals direkt von `QThread`.** Ein `run`, das eine Ausnahme durchlässt,
sendet sein Ergebnissignal nie — und wer darauf wartet, wartet für immer.
Nachgestellt am Einrichtungsdialog für ComfyUI: Liegt die Installation unter
`Program Files`, wirft das Kopieren der Knoten einen `PermissionError`. Die
Ausnahme landet auf stderr, wo sie kein Kunde sieht; im Fenster steht „Wird
eingerichtet …", der Balken läuft, der Knopf sagt „Abbrechen" — und dabei
bleibt es, bis jemand das Programm beendet.

Von dreiundzwanzig Arbeitern fing genau **einer** eine unerwartete Ausnahme:
der Versand der Rückmeldung. Die anderen zweiundzwanzig konnten dasselbe
anrichten — die Ladeanzeige der Auswertung, der für den Rest der Sitzung
gesperrte Export-Menüeintrag, „Der Profilbestand wird durchgesehen …" als
Dauerzustand.

```python
class _Survey(Worker):
    done = Signal(object)

    def work(self) -> None:  # nicht run
        self.done.emit(install.statuses())
```

Zwei Pflichten hängen daran, und `tests/test_leash.py` prüft beide:

* **Erwartete Fehler bleiben in `work`** und kommen als *Ergebnis* zurück —
  `InstallResult.reason`, ein Satz von `pull_model`, ein eigenes Signal für
  `SetupFailed`. Was bei `crashed` ankommt, ist ausdrücklich das, womit niemand
  gerechnet hat.
* **`crashed` wird verbunden**, sonst ist der Fund nur verschoben. Wo ein
  Fehlerpfad existiert, geht das Unerwartete denselben Weg als `InternalError`
  — §33.1 ordnet ihm den Fehlerbericht zu, und genau der gehört dorthin. Wo
  keiner existiert, löst der Slot mindestens den Wartezustand: Balken weg,
  Knöpfe frei, ein Satz, der sagt, dass etwas schiefging.

**Und nach einem Absturz wird nicht neu erhoben.** Der Installationsdialog tat
das und überschrieb seine eigene Meldung eine Sekunde später mit der
Zusammenfassung der Erhebung — der Kunde hatte den Satz gesehen und nicht
gelesen.

### Ein Rückruf an ein eigenes Kind hält schwach

**Die allgemeine Form, und sie ist häufiger als ihre bekannten Fälle:** Ein
Rückruf, der `self` stark fängt, an einem Sender, der ein **Kind von `self`**
ist, schließt einen Ring — `self` → Sender → Rückruf → `self`. Er läuft über
die C++-Grenze, und Pythons Speicherbereiniger sieht die mittlere Kante nicht;
er kann den Ring also nicht brechen. Das Objekt lebt bis zum Prozessende.

```python
self.timer.timeout.connect(lambda: self.rebuild())  # Ring
self.button.clicked.connect(lambda: self.apply())  # Ring
button = QToolButton(self)
button.clicked.connect(lambda: self.apply())  # auch ein Ring
```

**Das Mittel ist fast immer die gebundene Methode, nicht `weakref`.** Qt hält
eine gebundene Methode von sich aus schwach; den Ring baut allein das Lambda.
Gemessen am selben Aufbau, je zehn Objekte losgelassen:

| Form | überleben |
|---|---|
| `connect(self.rebuild)` | **0 von 10** |
| `connect(lambda: self.rebuild())` | 10 von 10 |
| `connect(partial(self.rebuild, 1))` | 10 von 10 |
| `connect(lambda x=1: self.rebuild(x))` | 10 von 10 |
| `connect(lambda *_a, s=self: s.rebuild())` | 10 von 10 |

Bemerkenswert daran ist die dritte Zeile: `functools.partial` hilft **nicht**,
obwohl es wie die saubere Fassung eines Lambdas aussieht — es hält die
gebundene Methode und damit `self`. Dasselbe gilt für das Vorgabeargument, das
im Arbeiter-Abschnitt unten steht; dort ist es richtig, weil der Sender geht.

Also, in dieser Reihenfolge. **Erste Wahl, die gebundene Methode:**

```python
self.timer.timeout.connect(self.rebuild)
```

**Zweite Wahl, wo feste Werte im Spiel sind** — sie gehören in eine Methode und
nicht in ein Lambda:

```python
def _rebuild_layer(self) -> None:
    self.show_scene(self._result)
```

**Dritte Wahl, für Werte aus einer Schleife:**

```python
button.toggled.connect(weak_slot(self, Editor._tool_chosen, name))
```

`weak_slot` (`app/ui/leash.py`) bleibt für zwei Fälle, die die ersten beiden
nicht abdecken. Der eine ist ein Wert aus einer **Schleife**, der an den
Rückruf gebunden werden muss; es hält den Besitzer schwach und reicht den
Schleifenwert vor den Signalargumenten durch.

**Der andere ist ein Rückruf, der nicht an einem Signal landet.** „Die
gebundene Methode ist frei" gilt für Qt-Verbindungen — Qt hält sie schwach.
Ein gewöhnlicher Python-Container tut das nicht: `ToolStrip.add(…, self._end_split)`
legte die Methode in ein `Tool` und das in ein Wörterbuch, und damit hielt sie
das Fenster genauso fest wie ein Lambda. Der Unterschied ist nicht die Form des
Rückrufs, sondern **wer ihn aufbewahrt**.

Das war der letzte Halter des Hauptfensters, und er ist gefunden worden,
nachdem alle 27 Lambdas darin schon umgebaut waren.

Von Hand geschriebene `weakref.ref`-Blöcke braucht es nur noch, wo mehrere
Rückrufe zusammen entstehen — `viewport._weak_callbacks` ist der Fall, zehn
Stück für den Navigator (`NavigatorCallbacks`).

**Der Navigator (bis zum 05.09.2026 der VTK-Interaktionsstil) ist ein Fall
davon, nicht der Fall.** Diese Regel nannte lange allein ihn — damals
Stil → Viewport → Plotter → Interactor → Stil —, und deshalb hat
niemand nach einem Zeitgeber gesucht. Gefunden wurde einer in
`viewport.py:1428`: ein Lambda am eigenen `QTimer` der Schichtvorschau.
Gemessen, am 22.08.2026:

| | Viewports, die ihr `del` + `gc.collect()` überleben |
|---|---|
| mit dem Lambda | **20 von 20** |
| mit `weakref` | 0 von 20 |

Dieselbe Probe am reinen Qt-Muster ohne Solidon-Code, zwei `QObject` mit
eigenem `QTimer`: stark 10 von 10 überlebt, schwach 0 von 10.

**Was es kostet, am Hauptfenster gemessen** — fünf bauen, schließen, loslassen,
den Arbeitssatz des Prozesses ablesen:

| | Zuwachs je Fenster | überleben |
|---|---|---|
| vorher | +21, +28, +35, +42, +50 MB — linear | 5 von 5 |
| nachher | +17, +17, +18, +17, +18 MB — flach | 0 von 5 |

Die Kurve **sättigt**: Das erste Fenster kostet einmalig rund 17 MB für Qt und
den damaligen VTK-Renderer, jedes weitere kostet nichts mehr. Vorher wuchs sie
ungebremst, und die Suite baut über siebenhundert Fenster nacheinander auf.

**Und die Kehrseite, die erst am 23.08.2026 sichtbar wurde: Ein Fenster,
das sterben kann, kann im falschen Thread sterben.** Solange die Lambda-Ringe
die Fenster hielten, sammelte sie niemand ein. Seither tut es der
Speicherbereiniger — und der läuft in dem Thread, dessen Allokation gerade die
Schwelle reißt, nicht zwangsläufig im Hauptthread. Findet er dort ein Fenster
ohne letzte Python-Referenz, gibt er dessen **Python-Hülle** frei — und
shibokens Deallocator zieht die C++-Zerstörung nach sich, **in diesem
Thread**. Ein QWidget-Destruktor gehört nie dorthin: Er nimmt den Qt-Mutex
und braucht dann den GIL für die Hülle, während der Hauptthread den GIL hält
und auf genau diesen Mutex wartet. Das Ergebnis ist kein Absturz, sondern ein
**Stillstand** bei 0,00 CPU.

**Und es ist kein Menü-Problem, auch wenn der erste Abzug eines zeigte.**
Zweimal unabhängig gefangen, mit verschiedenen Paarungen: einmal `~QMenuBar` →
`~QMenu`, während der Hauptthread eine `QComboBox` aufbaute, einmal ein
beliebiges `~QWidget`, während er eine `QScrollArea` aufbaute. **Jedes**
Widget, dessen letzte Python-Referenz in einem Nebenthread fällt, kann es
auslösen; wer nur Menüs schützt, schützt zu wenig. Im zweiten Abzug steht
`SbkDeallocWrapper` ganz unten und benennt den Auslöser: Nicht Qt räumt auf,
sondern Pythons Speicherbereiniger.

Der vollständige Stapelabzug beider Threads steht in `tests/conftest.py`,
zusammen mit dem, was **nicht** hilft: `gc.collect()` (der Lauf im Hauptthread
ist der harmlose), `leash.undisturbed()` (es hält den gc dieser Zeile an,
während der Nebenthread weiter alloziert) und `deleteLater` (zweimal versucht,
beide Male an VTK gescheitert — ob der Weg mit pygfx offen ist, hat niemand
gemessen). Wer einen vierten Anlauf nimmt, liest zuerst diese Notiz.

Der Ring-Umbau bleibt trotzdem richtig — er hat den Speicher von linear auf
flach gebracht. Aber er ist die Ursache dafür, dass es diesen Deadlock geben
kann, und wer ihn für unbeteiligt hält, sucht an der falschen Stelle.

**Kurzlebige Sender sind ausgenommen.** Ein Arbeiter, ein Dialog, eine
Animation bauen denselben Ring, und er löst sich auf, sobald der Sender geht;
dort ist das Vorgabeargument aus dem Abschnitt unten richtig und ausreichend.
Der Unterschied ist nicht die Form, sondern die Lebensdauer: Wer so lange lebt
wie `self`, hält `self` ewig.

**Gefunden wird so etwas nicht durch Suchen, sondern durch einen Test, der
eine Annahme festnagelt.** Der Fund kam aus einem Test, der etwas *anderes*
behauptete — dass die Rückrufe an den Interaktionsstil die Ansicht nicht
festhalten. Sie taten es nicht; er wurde trotzdem rot, und
`gc.get_referrers(view)` nannte den wahren Halter. Wer einen Verdacht hat,
nimmt denselben Griff:

```python
for holder in gc.get_referrers(widget):
    if type(holder).__name__ == "cell":  # eine Closure hält es
        for user in gc.get_referrers(holder):
            ...  # __qualname__ und __code__ nennen die Zeile
```

**Eine geschachtelte Funktion ist dasselbe wie ein Lambda.** `OperationDialog`
hatte `def unfold(open_now, inner=inner)` in seinem Aufbau; die Form sieht
harmloser aus, die Zelle hält denselben Ring. Wer nach Lambdas grept, findet
sie nicht — `gc.get_referrers` schon.

**Und eine gebundene Methode hält ihr Objekt genauso.** Zwei Fälle am
23.08.2026, beide außerhalb jeder Signalverbindung:

* `QTimer.singleShot(0, self, self._render_pending)` in `PartCatalog` —
  die Kette reiht sich selbst neu ein, und jede eingereihte gebundene Methode
  hält den Katalog. Zehn losgelassene überlebten alle zehn. Sie hat jetzt ein
  `release()`, das die Kette anhält.
* `release = getattr(widget, "release", None)` in einer **Schleife** —
  nach dem letzten Durchgang steht in der Variablen das letzte Objekt.
  Betroffen waren `tests/test_widget_lifetime.py` und die Aufräum-Fixture in
  `tests/conftest.py`. Der Griff dagegen ist die ungebundene Funktion von der
  Klasse: `getattr(type(widget), "release", None)`, aufgerufen mit dem Widget
  als erstem Argument.

**Die Zahl selbst war dabei der Hinweis.** Der Test meldete „1 von 10
überlebten", dreimal reproduzierbar — nie null, nie zehn. Ein Ring hält
*jedes* Objekt; eine Eins ist ein Zeiger auf genau eine Referenz, und die
findet man, statt sie für Streuung zu halten.

### Ein Filter auf einem sterblichen Widget bestellt beim `Destroy` ab

```python
def eventFilter(self, watched, event):
    if stop_watching_the_dying(self, watched, event):
        return False
    ...
```

**Die Richtung entscheidet, nicht die Zählung.** Stirbt das *Filterobjekt*,
räumt Qt selbst auf — gemessen und haltend. Gefährlich ist die Gegenrichtung:
Stirbt das *überwachte* Objekt, läuft der Filter des Überlebenden in dessen
Abbau hinein und fragt halb abgeräumte Widgets nach ihrer Geometrie. Qt schickt
`Destroy`, **bevor** die C++-Seite weg ist; das ist der letzte Takt, in dem das
Abbestellen geht.

Deshalb war die Zählung `installEventFilter` gegen `removeEventFilter` nie eine
Aussage — sie stand zwei Tage als Registerpunkt, bevor jemand die Richtung
fragte. Wer auf der `QCoreApplication` installiert, braucht den Griff nicht: Sie
überlebt jeden Filter.

**Was er trägt, ist gemessen und kleiner als erwartet.** Ein Zähler in der
Funktion, 30.08.2026, vier Fensterdateien:

| Datei | Filteraufrufe | davon `Destroy` |
|---|---|---|
| `test_first_run` | 507 807 | 6 |
| `test_overlay` | 25 786 | 0 |
| `test_ui` | 3 489 045 | 113 |

Alle 119 in `OverlayHost` — der einen Stelle, für die der Griff gebaut wurde.
Die sechs anderen Aufrufstellen schlugen nie an, und der Grund steht in der
Lebensdauer: Wo ein Elternteil sein eigenes Kind beobachtet, sterben beide
zusammen. **Sie bleiben trotzdem** — ein Muster, das an jeder sterblichen
Filterstelle gleich aussieht, schlägt sechs Einzelbegründungen, warum gerade
diese Stelle es nicht braucht. Aber es ist Vorsorge und keine Behebung, und so
steht es im Docstring.

`tests/test_widget_lifetime.py` prüft beides: sieben Filterklassen einzeln
(`Destroy` muss abbestellen) und ein `ast`-Wächter, der eine neue Stelle ohne
Griff findet. Der Wächter fragt nach dem **Filterargument**, nicht nach der
Datei — bei `main_window.py:1552` steht `self.sketch_bar.installEventFilter(
self.overlay)`, und der Filter wohnt woanders. Seine erste Fassung wurde daran
falsch rot.

### `isValid` beantwortet nicht, was für ein Objekt das ist

Ein recycelter Zeiger trägt kein totes Objekt, sondern ein **lebendiges vom
falschen Typ**. `shiboken` liefert dann einen fremden Wrapper, und `isValid`
sagt dazu ja. Zweimal am 30.08.2026 im Torlauf gefallen, beide Male in
`overlay.rows_height`:

```
AttributeError: 'QWidgetItem' object has no attribute 'rowCount'
```

Erreicht über `LayoutRequest` → `eventFilter` → `_place`, also über eine Zone,
die **noch lebt**, hin zu einer Ansicht, die schon geht. Das `Destroy`-
Abbestellen deckt das nicht ab — es stand zu beiden Zeitpunkten bereits in der
Datei. Wer abbestellt, hört auf, ein sterbendes Objekt zu beobachten; wer über
seine **Nachbarn** rechnet, muss zusätzlich fragen, was er da vor sich hat.
Dieselbe Beobachtung steht seit dem 25.08.2026 in `shortcut_schemes.py`, wo ein
`QWidgetItem` als `watched` ankam.

Der Griff ist eine Typprüfung (`isinstance`) mit demselben Rückfall wie für ein
fehlendes Objekt. Sie ist nicht dasselbe wie die zwei `isValid`-Wachen, die am
24.08. am Eingang von `_place` standen und die Quote nicht senkten: Eine Prüfung
am Eingang gewinnt keinen Wettlauf, der **während** des Aufrufs entschieden
wird — diese hier steht an der Stelle, an der der Wert angefasst wird.

### Wer eine `WorkerLeash` hält, hat ein `release()`

Wie man einem Fenster sagt, dass Schluss ist, hieß an jeder Klasse anders —
`release`, `wait_for_workers`, `wait_for_survey`, `wait_for_look`,
`wait_for_setup`, und an vier Klassen gar nichts. Wer eine Testfixture darauf
baut, sammelt Namen: Sie kannte zwei von fünf, dann drei, dann vier, und beim
fünften starb der Prozess beim Abbau an einem Thread, der sein Fenster
überlebt hatte.

Jede Klasse mit Arbeiter trägt `release()`, und es ruft intern das, was die Klasse
schon kann. **Die fachlichen Namen bleiben daneben**: `wait_for_survey` gibt
einen Wahrheitswert zurück und steht im Produktivcode (`FirstRunDialog.reject`),
`release` räumt auf und gibt nichts zurück. Zwei Sachen, zwei Namen — nur soll
die eine überall gleich heißen. `tests/test_widget_lifetime.py` liest per
`ast`, wer eine Leine anlegt, und verlangt von jedem dasselbe Wort; ein
sechster Name kann nicht mehr unbemerkt entstehen.

**Der Parameter gilt der Leine, nicht der Sache.** `release()` reichte seine
2000 ms an `wait_for_look` weiter, wo 30 000 stehen — damit bekam eine
Erhebung, die eine halbe Minute haben darf, zwei Sekunden. Gemessen an
`test_chat_ui`: 2 von 4 Läufen starben danach beim Abbau, gegen 4 von 4 nach
der Berichtigung. Die fachliche Methode wird ohne Argument gerufen.

### Loslassen allein räumt nicht auf

Der Weg, den `MainWindow` beim Schließen geht, und der einzige, der in einem
Test dasselbe misst:

```python
release(widget)  # von der Klasse geholt, siehe oben
leash.wait_for_all()
application.processEvents()  # mehrfach: ein finished reiht selbst wieder ein
gc.collect()
```

**Der `processEvents`-Schritt ist der, den man vergisst**, und ohne ihn liest
man ein Leck, wo keines ist: `leash._alive` hält einen Arbeiter modulweit, der
hält über sein `finished`-Lambda die Leine und damit den Dialog; abgeräumt
wird erst, wenn das Signal ankommt.

| | überleben |
|---|---|
| nur loslassen | 10 von 10 |
| `release()` | 10 von 10 |
| `release()` + Schleife | 0 von 10 |

Dass die mittlere Zeile sich nicht bewegt, ist der Grund, warum drei Klassen
zwei Monate lang als „hält, aber erklärbar" in einer Ausnahmeliste standen.

### `isVisible()` und `hasFocus()` lügen in einem nie gezeigten Fenster

Beide melden falsch, solange das Fenster nie gezeigt und nie aktiviert wurde —
also in jedem Offscreen-Lauf. Zweimal am 23.08.2026 zugeschnappt, einmal im
Code und einmal im Test:

* Eine Bedingung `if self.measure_field.isVisible()` im `keyPressEvent` hätte
  in der ganzen Suite nie gegriffen. Gefragt wird stattdessen nach der Sache:
  `if self.pending_measure() > 0.0`.
* Ein Test `assert field.hasFocus()` prüft, ob die Testumgebung ein aktives
  Fenster hat. Geprüft wird stattdessen die Wirkung: kommt die Ziffer im Feld
  an?

`isVisibleTo(eltern)` ist die brauchbare Frage, wenn es wirklich um
Sichtbarkeit geht — sie beantwortet „würde es erscheinen, wenn das Fenster
erschiene".

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

**Gestartet wird über `WorkerLeash.start`, nicht über `worker.start()`.** Das
ist die wichtigere Hälfte derselben Regel, und sie fehlte: Gehalten wurde erst,
wenn ein Arbeiter *fertig* war — solange er lief, hing er allein am Feld seines
Dialogs. Ein Dialog, der vorher freigegeben wird (ein Fenster räumt ihn weg,
ein Test lässt ihn fallen), nimmt damit die letzte Referenz auf einen
**laufenden** `QThread` mit, und genau dagegen gibt es dieses Modul.

Sichtbar wurde es, als die Erstinbetriebnahme ihre Erhebung in einen Arbeiter
bekam: `tests/test_first_run.py` brach reproduzierbar an der Stelle ab, an der
ein Dialog aus einem vorigen Test einging. Betroffen war auch die
Werkzeugprobe des Chat-Dialogs, die es seit je gibt.

```python
worker.done.connect(self._show)
worker.finished.connect(lambda done=worker: self._worker_done(done))
self._worker = worker
self._leash.start(worker)  # hält ab diesem Moment, nicht ab dem Ende
```

Zwei Dinge hängen daran, und beide sind nötig: Die Menge der gehaltenen
Arbeiter ist **modulweit** (`leash._alive`) und nicht an der Leine — mit dem
Dialog stirbt sonst die Liste. Und der Zeitgeber, der nachsieht, ob ein Thread
ausgelaufen ist, hängt an einem Objekt, das die Widgets überlebt
(`leash._keeper`); an das Widget gebunden feuert er nach dessen Tod nie, und
der Arbeiter bliebe für immer gehalten.

Das Feld am Dialog bleibt — es ist danach nur noch die Antwort auf „läuft
gerade einer", nicht mehr die einzige Referenz.

**Fünfzehn Arbeiter hielten sich nicht daran, und gefunden hat sie kein
Suchen.** Ein `grep` nach `worker.start()` findet die Hälfte; die andere heißt
`self._worker.start()`. `tests/test_leash.py` liest deshalb den **Quelltext**
aller Dateien unter `app/ui/` — und zwar am Quelltext, weil das Verhalten es
nicht zeigt: Ein Arbeiter an der Leine vorbei läuft völlig normal, bis das
Fenster unter ihm weggeräumt wird. Dieselbe Bauart wie der Wächter, der jedes
`ResultCache(` ohne `disk=` findet.

Aufgefallen ist es an einer Frage zur Aufräum-Fixture der Suite: Wer über
`leash.alive()` melden will, wer einen Test überlebt hat, sieht nur, was über
`WorkerLeash.start` gestartet wurde — eine Zusicherung darüber verspricht sonst
mehr, als sie halten kann.

### Ein Dialog, der beim Öffnen nachsieht, öffnet erst danach

Dreimal derselbe Fund an drei Stellen, jedes Mal gemessen: Die Liste der
zusätzlichen Programme brauchte 2,97 Sekunden bis auf den Bildschirm, die
Erstinbetriebnahme 1,88, der Chat-Dialog 2,98. Der Grund war jedes Mal
dasselbe — im Konstruktor stand, was ein Programm sucht, eine Profildatei
liest oder einen Port fragt.

Das gehört in einen Arbeiter (§38), und der Dialog zeigt sofort seine Fragen.
Drei Dinge machen den Unterschied zwischen „geht auf" und „geht auf und lügt":

* **Kein Zustand ohne Erhebung.** Wo die Antwort fehlt, steht „Wird
  nachgesehen …" — nicht „fehlt", und kein Knopf, der auf eine Vermutung
  wirkt.
* **Eine Erhebung, nicht drei.** Die Liste fragte je Zeile dreimal dasselbe,
  bei den Diensten mit je einer Socket-Probe. Ein `Status`-Typ, der in einem
  Durchgang entsteht, ist billiger als drei Aufrufe, die sich gegenseitig nicht
  kennen.
* **Ein nachgereichter Vorschlag überschreibt keine Wahl.** Der Drucker aus
  dem Slicer-Profil kommt Sekunden später — wer in der Zwischenzeit selbst
  gewählt hat, behält seine Wahl (§2.4).

Und eine Methode, auf die Erhebung zu warten (`wait_for_survey`,
`wait_for_look`), gehört dazu: Ein Test, der sie nicht abwartet, prüft den
leeren Zustand, und ein Dialog, der mit laufender Suche zugeht, verwaist einen
Thread.

**Und er meldet auch nichts mehr.** Die Regel darüber galt als Sache der
Stabilität; sie ist genauso eine der Anzeige. Ein Nachzügler, der
`busyChanged(False)` sendet, räumt Balken, Abbrechen und Ladeanzeige eines
Laufs ab, der noch rechnet — sichtbar an der Stelle, an der jeder anfängt:
Eine Datei auf den Startbildschirm zu ziehen legt zwei Läufe hintereinander
(das leere neue Projekt, dann den Import), und bei 1,3 Millionen Dreiecken war
die Anzeige nach einer Zehntelsekunde weg und die restlichen vier Sekunden
stumm. Dasselbe gilt für sein Ergebnis: eingeblendet wurde die leere Szene des
Vorgängers über dem Modell, das gerade lud (§15.3). `Session._outdated`
beantwortet die Frage für alle vier Abschluss-Slots; ein Aufruf ohne Absender
(Tests, Kommandozeile) gilt als aktuell.

**Ein Ersetzen ist dabei kein Aufhören.** Steht `_rerun_pending`, folgt der
nächste Lauf sofort — dann wird kein `False` gemeldet, sonst flackert die
Anzeige beim Ziehen an einem Schieber im Sekundentakt. Dieselbe Begründung,
aus der `evaluationCancelled` einen ersetzten Lauf nicht meldet.
