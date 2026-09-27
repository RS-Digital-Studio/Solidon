---
description: "Wartezeit und Nebenläufigkeit — was das Fenster beim Rechnen zeigt (Stufen, Ladeanzeige, grobe Vorschau), Arbeiter und ihr Qt-Abbau (leash.Worker, WorkerLeash, release, DeferredDelete), Rückrufe, die nicht festhalten; ausgegliedert aus oberflaeche.md"
paths:
  - "app/ui/session.py"
  - "app/ui/loading.py"
  - "app/ui/leash.py"
  - "app/ui/splash.py"
  - "app/ui/main_window.py"
  - "app/ui/outline_dialog.py"
  - "app/ui/step_dialog.py"
  - "app/ui/organizer_dialog.py"
  - "app/ui/local_recognition.py"
  - "app/ui/local_recognition_flow.py"
  - "app/ui/print_findings_flow.py"
  - "app/ui/app_events.py"
  - "app/ui/placement_flow.py"
---

# Regeln für Wartezeit und Nebenläufigkeit

Was geschieht, während gerechnet wird (§2.8); die allgemeinen Regeln aus
`oberflaeche.md` gelten zusätzlich. Messreihen, Anlässe und die Mechanik im
Einzelnen stehen unter denselben Überschriften in
`konzepte/begruendungen/regel-wartezeit.md`.

## Wartezeit

| Dauer | Anzeige |
|---|---|
| unter 0,2 s | nichts |
| bis 2 s | Mauszeiger und Statusleiste |
| darüber | Fortschritt mit **Abbrechen**, Oberfläche bedienbar |
| über 10 s | zusätzlich eine Schätzung, wenn möglich |

Die letzte gültige Darstellung bleibt sichtbar — nie ein leerer Viewport, nie
ein blockierendes Fenster; lange Rechnungen laufen nicht im Qt-Hauptthread.

* **Verstrichene Zeit ist keine Restschätzung** (`loading.ProgressTiming`): Die
  Uhr taktet jede Sekunde, auch bei stehendem Anteil und ohne Animationen, bis
  Ergebnis, Abbruch, Fehler oder Fensterabbau. Während einer Kernfrage ruht die
  Restschätzung, und ihre Antwortzeit zählt weder als Rechenzeit noch als
  Stillstand; steht der Anteil über der Schwelle still, rechnet die Uhr nichts
  hoch (`ProgressTiming.remaining`).
* Animationen melden Bildschirmlesern keine Zeitänderung. Eine leere
  Fortschrittsmeldung beendet nur eine Teilrechnung; Uhr und Statusanzeige
  bleiben, solange `Session.busy` gilt.
* **Eine bestätigte Vollerkennung zeigt ihre Spanne, keinen Anteil** (§21.1),
  dieselbe wie in der Frage davor (`perceive.local.recognition_minutes`),
  skaliert durch eine abbrechbare Rechenprobe je Prozess
  (`perceive.recognition_time`, `check_cancelled`) in der Wartezeit der Frage,
  nie in der Erkennung (§15.1). Nach ihrem Abbruch bietet die Statuszeile
  *Ohne Merkmalserkennung laden*, auch unter gespeicherter Zustimmung, bis ein
  fertiger Lauf den Knopf wegnimmt.

### Wo nichts steht, steht die Ladeanzeige

Bleibt kein Modell im Bild, liegt `LoadingVeil` (`app/ui/loading.py`) über der
Ansicht: nur bei leerem Bild (`MainWindow._update_veil`), unter den Karten
(`OverlayHost.set_veil`), nach 200 ms — beim Öffnen eines Projekts mit
Schritten sofort (`begin(..., at_once=True)`) — und deckend
(`viewport_colours`), denn ein halbdurchsichtiges Widget über dem nativen
Fenster zeigt die Fensterfarbe. **Solange er steht, ist die Ansicht verborgen,
nicht nur verdeckt** (`middle_stack.setVisible`): Die Grafikfläche ist ein
natives Fenster, liegt über jedem gemalten Geschwister und zeigt bis zu ihrem
ersten Bild alte Pixel. `widget.grab()` sieht das nicht; Beweisbilder nur über
`grabWindow` (`ansicht.md`, „Was nur das Bild zeigt").

### Vor der Auswertung: `waiting()` und der Einleseplan

* **Was vor der Auswertung liegt** (`load()` einer Projektdatei), sieht die
  Ladeanzeige nicht; dort bedient `waiting()` in `main_window.py` die Zeile
  „bis 2 s", ein Kontextmanager um genau eine Rechnung — kein Wartezeiger
  bleibt an einem Fehlerausgang stehen, unter ihm wird nichts gefragt
  (`_offer_recovery` liegt außerhalb).
* **Den Einleseplan einer Nutzlast ohne Pfad (Download) rechnet ab
  `PLAN_IN_WORKER_ABOVE` (8 MB) ein Arbeiter**, bei STEP ab
  `STEP_PLAN_IN_WORKER_ABOVE` (2 MB; welche Grenze gilt, sagt
  `_plans_in_worker` an der Endung); darunter bleibt er unter `waiting()`. Wer
  im Test `PLAN_IN_WORKER_ABOVE` auf null setzt, schickt auch STEP in den
  Arbeiter.
* **Eine Datei vom Pfad liest immer ein Arbeiter** (`_ReadWorker`), und ihr
  Plan läuft dort, gleich wie groß — ein Dateizugriff ist eine Netzfrage
  (`Session.import_model_async`). Abbrechen gilt auch während des Lesens
  (Daemon-Faden, `CancelSignal`); ein `OSError` ist ein Hinweis mit Weg
  (`loader.unreadable_file`), kein Absturzbericht.
* **Die automatische Sicherung schreibt im Arbeiter** (`Session.autosave_async`);
  Speichern, Verwerfen und Dokumentwechsel verwerfen eine spätere Sicherung
  (`_autosave_epoch`), ein Schreibfehler kommt einmal je Sitzung über
  `autosaveFailed`. `Session.autosave` bleibt der gerade Weg für Tests.
* **Das Modell zuerst, die Erkennung danach:** Ein neuer Ladeschritt zeigt ab
  `PICTURE_FIRST_TRIANGLES` erst das Bild ohne Erkennung (`pictureChanged`,
  `result_current` bleibt falsch); Rückfragen stellt nur der erste Durchgang
  (`_pending.asked`/`replay`).
* **Ein Import ohne Modell wird kein Schritt:** Hält sein erstes Bild am
  Ladeschritt mit `ValidationError`, nimmt `Session._settle_import` ihn ohne
  Redo zurück (`History.withdraw`), `importRejected` bietet *Andere Datei
  wählen*; „Zuletzt geöffnet" folgt erst `importConfirmed`.
* **Falle:** Läuft `with waiting(): self.session.import_payload_async(…)`
  synchron durch, landet ein Fehler unter dem Wartezeiger —
  `_on_import_failed` nimmt ihn vor `show_error` zurück. Um
  `import_model_async`, das immer sofort zurückkehrt, steht kein Wartezeiger.
* **Falle:** `wait_for_idle` muss jeden Arbeitertyp kennen; wer einen
  dazubaut, trägt ihn ein.

### Eine verspätete Antwort meldet nichts mehr

* `Session.busy` zählt Einleseplan und Auswertung bis zur Zustellung ihres
  Endsignals; das Ende des einen schaltet die Anzeige nicht ab.
* **Eine Antwort trägt das Dokument, für das sie lief:** Jeder Arbeiter am
  Dokument bekommt den Stempel `Session._project_generation` (hochgezählt in
  `_reset_for`), `_stale_import` lässt Veraltetes fallen. Meldungen an Widgets
  gehen als Signal (`_VariantWorker.progressed`), nie als gebundene
  Widgetmethode im Rückruf.
* **Ein Nachzügler meldet weder Zustand noch Ergebnis** (`Session._outdated`
  in allen vier Abschluss-Slots; ohne Absender gilt ein Aufruf als aktuell).
  `evaluate_now` macht einen laufenden Arbeiter zu `_superseded`, dessen
  Ergebnis `_stale` verwirft, während `_on_thread_done` ihn weiter aufräumt.
* **Ein Ersetzen ist kein Aufhören:** Bei `_rerun_pending` wird kein `False`
  gemeldet, und `evaluationCancelled` meldet keinen ersetzten Lauf.

### Umbau und Export rechnen im Arbeiter

* **Ein Umbau des Verlaufs** (`_RevisionWorker`) rechnet auf einer Kopie und
  wird nur bei aktuellem Arbeiter und Projektstempel übernommen
  (`Session._on_revised`); Rückfragen über `ask_from_worker`, Abbrechen endet
  kooperativ mit `revisionCancelled`, und der Verlauf bleibt unverändert.
  `busy` und `wait_for_idle` umfassen ihn; ein zweiter Umbau währenddessen
  wird abgesagt, nicht eingereiht.
* **Ein Export bekommt Fortschritt, aber kein Abbrechen** (`_ExportWorker`) —
  eine halb geschriebene Datei ist keine; der Menüeintrag ist währenddessen
  gesperrt. **Wer einen Arbeiter ohne Abbrechen baut, begründet das im
  Docstring.**
* **Vorprüfung und Schreiben sind ein Auftrag:** Geschrieben wird genau der
  geprüfte Stand (Dokument und lokale Einstellungen beim Start kopiert), nie
  die heutige Auswahl; erst ein ausdrücklich neuer Versuch prüft neu.

### Ein Dialog, der beim Öffnen nachsieht, öffnet erst danach

Was Programme sucht, Profile liest oder einen Port fragt, gehört in einen
Arbeiter (§38) — geprüft wird **jeder** Konstruktoraufruf an Dateisystem,
Registry oder Netz, nicht nur der bekannte.

* **Kein Zustand ohne Erhebung:** „Wird nachgesehen …", nicht „fehlt", und
  kein Knopf, der auf eine Vermutung wirkt. Eine Erhebung (ein `Status`-Typ),
  nicht drei.
* **Ein nachgereichter Vorschlag überschreibt keine Wahl** (§2.4).
* **Dazu gehört eine Methode, auf die Erhebung zu warten** (`wait_for_survey`,
  `wait_for_look`), sonst prüft ein Test den leeren Zustand.
* **Druckeinstellungen:** Nur der passende Auftrag des `_AdviceWorker`
  aktualisiert die Vorschläge; beim Schließen bricht der Dialog die Analyse
  kooperativ ab und hält ihre Arbeiter bis zum Ende. Das Gemessene überlebt ihn
  (`Session.remember_analyses`); die Vorschläge lassen die Stützsäulen aus
  (`slice_body(support_volume=False)`).
* **Slicersuche** (`_SlicerWorker`): Der gemerkte Slicer gilt vorläufig
  (`_remembered_slicer`); während der Suche steht „Die Slicer werden gesucht …"
  als Zustand und als Grund an *Slicen* und *Im Slicer öffnen* (Regel 18),
  nicht „Dafür fehlt ein Slicer", und *Zusätzliche Programme* bleibt weg.
  **Kein Cache in `discover`** — `recheck_slicer` muss Neuinstalliertes
  finden. Ein zweiter Start ersetzt den ersten. Das Schließen wartet nicht auf
  sie (`_settle`); vor dem Beenden fragt das Hauptfenster über
  `leash.wait_for_all` nach jedem Arbeiter weggeräumter Dialoge.
* **Ein Dialog, der beim Schließen nicht warten darf, lässt los** (jedes
  Schließen von `KeyDialog` über `done`; `_let_go`: `_let_go_of_workers`
  setzen, Feld leeren, Signale und jede Verbindung trennen, Thread an
  `retire`) — **und jeder Ergebnis-Slot fragt zuerst das Flag**, denn ein
  eingereihtes Signal kommt trotzdem an. `release()` wartet weiter.
  Nachweis:
  `tests/test_chat_ui.py::test_closing_the_key_dialog_does_not_wait_for_the_model_survey`;
  Tests ohne Bezug zur Erhebung nehmen die Fixture `quick_survey`.

## Die grobe Vorschaustufe

Ab `session.COARSE_PREVIEW_ABOVE` Dreiecken (rund 150 000, dort fällt die
Sekunde) rechnet die Vorschau in ihrer Dokumentkopie auf `COARSE_PREVIEW_TARGET`
Dreiecke verkleinert (`_preview_outcome`, `decimate_mesh` mit `method="fast"`,
Werte in `session._coarse_params`). **Das Ziel ist die Schranke selbst**, dann
liefert der Kern ein geschlossenes Netz statt des offenen Rasters. Übernommen
wird genau gerechnet.

* **Anzeigeweg ohne Messung** (Entscheidung Robert):
  `mesh_ops.decimate_for_display`; die Vorgabe der Operation bleibt
  `"measured"` (`cache_version="2"`).
* **Beide Seiten auf demselben groben Netz** (`_coarse_before`) — zwei fast
  deckungsgleiche Häute sind der schlimmste Fall für jeden Booleschen Kern. Die
  Verkleinerung des unveränderten Eingangs wird vorab gerechnet und je Szene
  und Schritt gemerkt: `supersede_preview` lässt sie weiterlaufen,
  `cancel_preview` hält sie an. Nachweis:
  `test_evaluation.py::test_the_coarse_reduction_of_the_unchanged_input_outlives_a_superseded_preview`.
* **Das Band sagt es als Text** (Regel 18): „Grobe Vorschau — beim Übernehmen
  wird genau gerechnet", vor „am Volumen ändert sich nichts", hinter „Vorschau
  unvollständig".
* **Die Merkmale bleiben erkennbar:** Jede alte Ecke liegt höchstens
  `units.MAX_FACET_SAG` neben der neuen Fläche (`deviation(grob, genau)`),
  Geschlecht und erkannter Bohrungsdurchmesser bleiben die des genauen
  Körpers. Ein Ziel unter dem, was der Sehnenfehler allein erreicht, reißt
  beides. Braucht eine Form (Figur, Scan) bei 0,05 mm mehr Dreiecke als die
  Schranke, wird sie gröber — „grob" steht auch dann.
* **Beim Rückweg ins Netz** fallen Splitter (`kernel_jobs.without_slivers`), und
  `mesh_ops._as_mesh` verschweißt nur, wo das Netz dicht bleibt (wie
  `boolean._tidied`).
* **Auch `change_op` nimmt die Stufe** (`_coarse_steps_before`).
* **Die Dialogvorschau erkennt keine Merkmale** (`detect_features=False`),
  außer ein späterer Schritt oder eine Passung braucht eines. Der
  Agentenvorschlag (`preview_scene` ohne Rückruf) erkennt weiter und rechnet
  mit Absicht genau.
* **Gibt der Kern am groben Netz auf** (`_kernel_gave_up`: `GeometryError`)
  oder scheitert die Verkleinerung, rechnet die Vorschau genau; ein ungültiger
  Wert (`ValidationError`, `UserError`) rechnet nicht zweimal. Nachweis:
  `test_evaluation.py::test_a_coarse_preview_the_kernel_refuses_is_computed_exactly`.
* **Die Verkleinerung rechnet im Hilfsprozess** (`geom.kernel_process`, RM-212):
  `manifold3d` gibt den GIL nie her, und aus dem Vorschau-Arbeiter hielt die
  erste grobe Vorschau je Körper sonst den Hauptthread an. Das gilt nur für
  Arbeiter — aus dem Hauptthread gerufen rechnet der Kern hier, denn gewartet
  wäre dort genauso.
* **Was an der Dreieckszahl hängt, zählt das Original, nicht die Kopie**
  (`OperationSpec.expected_triangles`, `_counted_ahead`): Eine Absage ist die
  Antwort, mit den Handlungen, die der Dialog selbst einlöst
  (`OperationDialog.show_refusal`, `MainWindow._refusal_handlers`) — *Dreiecke
  verringern und erneut versuchen* ist eine Transaktion. Ändert eine Operation
  nur das Netz (`retriangulates`) und wüchse es über die Schranke, ist die
  geschätzte Zahl die Vorschau (`TriangleCounts`); sonst rechnet der Schritt
  am Original, bei `retriangulates` ohne Booleschen Vergleich
  (`compare_scenes(retriangulated=…)`). Exakte Eingänge und der Agentenweg
  werden nicht vorab gezählt.

### Die Vorschau über zwei Sekunden, und was ihr Band sagt

* **Über 2 s bekommt die Vorschau Balken und *Abbrechen*** (eigener Besitzer
  `"preview"` in `_PROGRESS_PRIORITY`); die Zeile nennt den Schritt, keine
  Prozentzahl. *Abbrechen* (`Session.cancel_preview`) hält auch die
  Vorbereitung an, das Modell bleibt, der Dialog bleibt offen, ein wartender
  Klick auf *Übernehmen* verfällt. Vor `compare_scenes`, das keinen Abbruch
  kennt, fragt `_preview_outcome` das Signal; den Besitzer beenden Antwort,
  Ablösung und Abbau. Nachweis (Release):
  `test_operation_ui.py::test_a_long_preview_offers_cancel_and_cancelling_leaves_the_model`.
* **Was die Operation nicht ändert, sagt das Band mit ihren Worten**
  (`_warning_of` reicht auch `info` durch; `OperationSpec.unchanged_effect`);
  „am Volumen ändert sich nichts" nur, wenn niemand Besseres weiß.
* **Gehört eine Handlung vor das Übernehmen, sperrt das Band den Knopf**
  (`block_apply`, bei `repair_and_retry`, `split_and_retry`,
  `recount_and_retry`) — sonst endet sie als angehaltener Schritt (Regel 19).

## Arbeiter und ihr Abbau

### Ein Arbeiter erbt von `leash.Worker` und schreibt `work`

**Niemals direkt von `QThread`:** Ein `run`, das eine Ausnahme durchlässt,
sendet sein Ergebnissignal nie.

```
class _Survey(Worker):
    done = Signal(object)

    def work(self) -> None:  # nicht run
        self.done.emit(install.statuses())
```

* **Erwartete Fehler bleiben in `work`** und kommen als Ergebnis zurück; bei
  `crashed` kommt nur das Unerwartete an.
* **`crashed` wird verbunden:** mit Fehlerpfad als `InternalError` (§33.1),
  sonst löst der Slot mindestens den Wartezustand — Balken weg, Knöpfe frei,
  ein Satz, dass etwas schiefging. Beides prüft `tests/test_leash.py`.
* Nach einem Absturz wird nicht neu erhoben — die Zusammenfassung überschriebe
  die Meldung.
* **Die Leine hält ihren Besitzer nicht:** Ein starker Rückverweis auf das
  Fenster baut einen Zyklus um ein Qt-Objekt, den ein später Sammlerlauf im
  falschen Thread abräumen kann. Die modulweite Menge hält nur Arbeiter,
  Zeitgeber hängen am Keeper, Rückrufe auf Besitzer und Leine sind schwach.

### Wer einen Arbeiter startet, hält ihn fest

Ein `QThread` hat keinen Qt-Elternteil; fällt seine letzte Python-Referenz,
während er läuft, stirbt das C++-Objekt unter ihm.

```
worker.finished.connect(lambda: setattr(self, "_worker", None))  # falsch

worker.finished.connect(lambda done=worker: self._worker_done(done))
self._worker = worker
self._leash.start(worker)  # hält ab diesem Moment, nicht ab dem Ende


def _worker_done(self, worker: Any) -> None:
    if self._worker is worker:
        self._worker = None
    self._hold_until_done(worker)
```

Die erste Zeile ist zweimal falsch: `finished` kommt, während Qt den Thread
noch abräumt, und das Lambda trifft blind das Feld — auch den Nachfolger, wenn
der Vorgänger später fertig wird.

* **Gestartet wird über `WorkerLeash.start`, nie über `worker.start()`**;
  `tests/test_leash.py` prüft das am Quelltext aller Dateien unter `app/ui/`.
* Die gehaltene Menge ist modulweit (`leash._alive`), der Zeitgeber hängt an
  `leash._keeper` — an Leine oder Widget stürben beide mit dem Dialog.
* Losgelassen wird erst, wenn `isRunning()` nein sagt (`_hold_until_done` →
  `WorkerLeash.hold_until_done`, ein ersetzter Arbeiter über `_retire` →
  `WorkerLeash.retire`); `wait_for_workers` wartet am Ende auf alle, sonst
  überlebt einer sein Fenster und reißt den Prozess mit.

### Wer eine `WorkerLeash` hält, hat ein `release()`

Jede Klasse mit Leine trägt `release()`, geprüft per `ast` in
`tests/test_widget_lifetime.py`; fachliche Namen wie `wait_for_survey` (gibt
einen Wahrheitswert zurück) bleiben daneben. **Der Parameter von `release()`
gilt der Leine** — die fachliche Methode wird ohne Argument gerufen.
`WorkerLeash.start()` nimmt den Arbeiter sofort in den Bestand (`pending()`,
`wait_all()`). `Worker.release_finished_references()` löst Rückverweise erst
nach zugestelltem eigenem `finished` und `wait(0)`, und nur die von der Klasse
deklarierten Ausgangssignale und Arbeitsfelder — nie `destroyed`, `started`
oder fremde Verbindungen.

### Loslassen allein räumt nicht auf

Der Weg, den `MainWindow` beim Schließen geht, und der einzige, der im Test
dasselbe misst:

```
release(widget)  # von der Klasse geholt, siehe unten
leash.wait_for_all()
application.processEvents()  # mehrfach: ein finished reiht selbst wieder ein
widget.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
application.processEvents()
gc.collect()  # erst nach der zugestellten nativen Löschung
```

* Ein Test-Pin fällt erst nach `sendPostedEvents(DeferredDelete)` und dem
  Ereignislauf — bis dahin bleiben die Hüllen der rekursiv gelöschten Kinder
  stark gehalten; danach sammelt der Abbau sie im Hauptthread ein.
* **Der `processEvents`-Schritt ist der, den man vergisst:** Ohne ihn hält
  `leash._alive` über das `finished`-Lambda Leine und Dialog, und man liest ein
  Leck, wo keines ist.

### Ein Rückruf an ein eigenes Kind hält schwach

Ein Rückruf, der `self` stark fängt, an einem Sender, der **Kind von `self`**
ist, schließt einen Ring über die C++-Grenze, den der Speicherbereiniger nicht
sieht — das Objekt lebt bis zum Prozessende.

```
self.timer.timeout.connect(lambda: self.rebuild())  # Ring
button = QToolButton(self)
button.clicked.connect(lambda: self.apply())  # auch ein Ring
```

Qt hält eine gebundene Methode schwach; `functools.partial` und
Vorgabeargumente halten `self` wie ein Lambda. In dieser Reihenfolge: die
gebundene Methode (`connect(self.rebuild)`); feste Werte in eine eigene
Methode; Werte aus einer Schleife über
`weak_slot(self, Editor._tool_chosen, name)` (`app/ui/leash.py`). **Haben die
Knöpfe eine Gruppe, schlägt sie `weak_slot`:** ein Empfänger an
`QButtonGroup.buttonClicked` als gebundene Methode (`ToolStrip._on_button`) —
`weak_slot` je Knopf riss `test_widget_lifetime` mit einer Zugriffsverletzung,
die Ursache ist offen.

* **Entscheidend ist, wer den Rückruf aufbewahrt:** Frei ist die gebundene
  Methode nur an einer Qt-Verbindung; in einem Python-Container
  (`ToolStrip.add(…, self._end_split)`) hält sie wie ein Lambda.
* Eine geschachtelte Funktion ist ein Lambda (`def unfold(open_now,
  inner=inner)`), die Suche nach Lambdas findet sie nicht.
* Eine gebundene Methode hält auch außerhalb von Signalen:
  `QTimer.singleShot(0, self, self._render_pending)` (`PartCatalog`, sein
  `release()` hält die Kette an); `release = getattr(widget, "release", None)`
  in einer Schleife hält das letzte Objekt — richtig ist
  `getattr(type(widget), "release", None)`, gerufen mit dem Widget.
* **Ein Empfänger an der Sitzung, der keine Methode ist, geht in
  `release()`** — `session.disconnect(self)` trennt nur gebundene Methoden, und
  die Sitzung überlebt das Fenster. Der Vorschlagswächter ist ein `weak_slot`
  (`_proposal_context_changed`); `release()` räumt `_clear_proposal()` und
  `_op_dialog.reject()`, bevor es trennt.
* Handgeschriebene `weakref.ref`-Blöcke nur, wo mehrere Rückrufe zusammen
  entstehen (`viewport._weak_callbacks`).
* **Kurzlebige Sender sind ausgenommen** (Arbeiter, Dialog, Animation): Ihr
  Ring löst sich mit dem Sender, dort ist das Vorgabeargument richtig. Wer so
  lange lebt wie `self`, hält `self` ewig.

Einen Halter findet ein Test, der eine Annahme festnagelt, und
`gc.get_referrers`, nicht die Suche nach Lambdas; überlebt reproduzierbar genau
eines von zehn, ist das genau eine Referenz, keine Streuung.

```
for holder in gc.get_referrers(widget):
    if type(holder).__name__ == "cell":  # eine Closure hält es
        for user in gc.get_referrers(holder):
            ...  # __qualname__ und __code__ nennen die Zeile
```

**Falle: Ein Fenster, das sterben kann, kann im falschen Thread sterben.**
Fällt die letzte Referenz eines Widgets während eines Sammlerlaufs in einem
Nebenthread, zerstört shiboken es dort — Stillstand bei 0,00 CPU zwischen GIL
und Qt-Mutex, bei jedem Widget. Stapelabzüge und was nicht hilft
(`gc.collect()`, `leash.undisturbed()`, `deleteLater`) stehen in
`tests/conftest.py`; vor jedem neuen Anlauf dort lesen.

### Ein Filter auf einem sterblichen Widget bestellt beim `Destroy` ab

```
def eventFilter(self, watched, event):
    if stop_watching_the_dying(self, watched, event):
        return False
    ...
```

Die Richtung entscheidet, nicht die Zählung der `installEventFilter`: Stirbt
der Filter, räumt Qt selbst auf; stirbt das *überwachte* Objekt, liefe der
Filter in dessen Abbau, und `Destroy` ist der letzte Takt davor. Auf der
`QCoreApplication` braucht es den Griff nicht;
sonst steht er an jeder sterblichen Filterstelle, als Vorsorge.
`tests/test_widget_lifetime.py` findet neue Stellen am **Filterargument**,
nicht an der Datei.

### `isValid` beantwortet nicht, was für ein Objekt das ist

Ein recycelter Zeiger trägt ein lebendes Objekt **vom falschen Typ**
(`QWidgetItem`), und `isValid` sagt ja. Wer über Nachbarn rechnet
(`overlay.rows_height`, `shortcut_schemes.py`), prüft mit `isinstance` dort,
wo der Wert angefasst wird, mit dem Rückfall wie für ein fehlendes Objekt —
eine Prüfung am Eingang gewinnt keinen Wettlauf.

### `isVisible()` und `hasFocus()` lügen in einem nie gezeigten Fenster

Offscreen melden beide falsch. Gefragt wird nach der Sache
(`self.pending_measure() > 0.0`), geprüft die Wirkung (kommt die Ziffer an?);
für echte Sichtbarkeit `isVisibleTo(eltern)`.

## Nebenläufig heißt: Der Hauptthread bleibt frei

### Ein Bild je Ereignisrunde ist kein Nebenläufigkeitsverfahren

`QTimer.singleShot(0, …)`-Ketten zerlegen Arbeit, sie verteilen sie nicht.

* **Was kein Qt braucht, gehört nicht in den Qt-Thread** (`drawing.thumbnail`
  endet in einer Zeichenkette); der Arbeiter meldet jedes Bild einzeln
  (`_ThumbnailWorker.drawn`).
* **Ein Arbeiter bekommt Arrays, kein Netz** (`drawing.thumbnail_of`) — sonst
  füllt er die trägen Caches des `Trimesh` neben dem Hauptthread; dieselbe
  Falle umgeht `placement_flow.for_a_worker` mit einer Kopie. Lesen ist
  gefahrlos, denn eine Eingabe ändert niemand (Regel 3).
* **Ein Bild wird nicht wie eine Operation dezimiert:** Anzeige ab §31,
  Beispielbilder und Orientierungssuche nehmen `mesh_ops.decimate_for_display`,
  das Baum-Vorschaubild nur das Raster (`mesh_ops.raster_for_display`).
* **Freigegeben heißt: nichts mehr anfangen** — `ObjectTree.release` leert den
  Vorrat, bevor es wartet; sonst überlebt ein nachgestarteter Zeichner den
  Prozess.

### Ein Arbeiter ist nur nebenläufig, wenn er den GIL hergibt

`manifold3d` hält den GIL in jedem Aufruf; ein solcher Arbeiter steht für die
Ereignisschleife im Hauptthread — deshalb rechnet der Kern an großen Körpern
im Hilfsprozess (`kern.md`). **Gemessen wird der Hauptthread** — die größte
Lücke eines Zeitgebers, solange der Arbeiter rechnet, zugeordnet über
`faulthandler`-Abzüge (die laufen ohne GIL), nicht über einen Python-Faden, der
in derselben Lücke steht. Für zwanzig Pixel genügt das Raster. `shapely` und
`numpy` geben ihn meist her (`_SculptWallWorker`), `pickle`, `repr` und
`tuple`/`sorted` über Millionen Python-Zahlen nicht; eine Prüfung, die nach
jeder Geste neu anläuft, bekommt einen Abbruchschalter
(`maps.wall_thickness_map`).

### Ein Blick auf eine Datei ist eine Netzfrage

`MainWindow._show_recent` prüft gemerkte Pfade in einem **Daemon-Thread**, nicht
an der Leine — ein hängendes `stat` ist nicht abbrechbar, und ein `QThread`
darin risse beim Beenden den Prozess mit. Nach 50 ms steht die ungeprüfte
Liste. Jede gemerkte Pfadliste wird so geprüft.

### Ein Zeiger, der fragt, wird gedrosselt, nicht entprellt

Die Flächenfrage der Platzierung läuft höchstens alle 16 ms, eine zur Zeit,
und ihr Ende nimmt sofort die jüngste Stelle.

* Eine überholte Antwort behält ihre Fläche (`PlacementFlow._surface_known`).
* **Eine Arbeiterkopie je Szenennetz**, nicht je Frage oder Fluss
  (`for_a_worker`, `WORKER_COPIES_KEPT`); jede Rechnung an ihr läuft unter
  ihrem Schloss (`on_the_copy`). Kopien für Nebenfäden entstehen mit
  `features.copy_with_answers`, nie mit `raw.copy(include_cache=True)` allein
  (was geteilt wird: `kern.md`); eine umgebaute Kopie (`repair`) nimmt
  `copy()` und erbt nichts.
* Unter `placement_flow.AT_ONCE_BELOW` Dreiecken rechnet der Fluss im
  Hauptfaden am Original; getippte Werte und große Körper bleiben beim
  Arbeiter. Ab `ANSWERS_IN_WORKER_FROM` fragt das Merkmalfenster im
  `_FeatureAnswersWorker`: Bis zur Antwort steht nur, was feststeht, gebaut
  wird nur, was noch gewählt ist, und ein Absturz ist ein Fehlerbericht.
* **Ein Filter an der Anwendung, nicht einer je Anliegen:** `app_events.listen`
  und `app_events.forget` (`test_app_events` prüft den Quelltext).
* **Die Vorbereitung zählt, statt zu verschneiden:** `placement._patch_area`
  baut die Fläche aus ihrem Rand und prüft sie; nur Abgelehntes geht durch
  `union_all`.
