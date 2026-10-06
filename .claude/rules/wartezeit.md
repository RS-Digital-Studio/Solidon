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
  - "app/ui/comfy_dialog.py"
---

# Regeln für Wartezeit und Nebenläufigkeit

**Große Formsitzungen halten die inkrementelle Vorschau im Arbeiter.** Ab
der gemeinsamen Sofortgrenze `placement_flow.AT_ONCE_BELOW` besitzt genau
ein `_SculptPreviewWorker` die `SculptPreview`; Folgeklicks warten geordnet,
während die letzte gültige Fläche sichtbar bleibt. Neues Werkzeug,
Symmetrie, Abbruch und Projektwechsel entwerten die Antwort über Nummer und
Arbeiteridentität. Die Wand-/Überhangprüfung liest eine Kopie der bereits
gezeigten Fläche und rechnet keine Gesten erneut. Prüfstände warten über
`wait_for_sculpt_preview` auf die zugestellten Antworten.

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

**Der Prüfbericht sagt, wenn seine Zeilen zum vorigen Stand gehören** (RM-534):
Rechnet es länger als 200 ms und gehört das Gezeigte nicht zum Dokument
(`MainWindow._follow_the_run_in_the_report`), steht im Kopf „Wird neu berechnet
…“ mit Uhr, vor jeder Zeile „Voriger Stand:“, ihre Handlungen gesperrt
(`ReportPanel.set_running`); die Reiterzahl bleibt, ein alter Fehler blinkt
nicht als neuer, und die Haltansage weicht dem Lauf. Ein Bild vor der
Erkennung ist kein voriger Stand.

Die Wartezeit einer historischen Vorschau beginnt bereits beim Vorbereiten
ihres Eingangszustands. Die folgende Änderung setzt weder Uhr noch Hinweis
zurück; Abbruch und Fehler beenden beide Phasen gemeinsam.

* **Verstrichene Zeit ist keine Restschätzung** (`loading.ProgressTiming`): Die
  Uhr taktet jede Sekunde, auch bei stehendem Anteil und ohne Animationen, bis
  Ergebnis, Abbruch, Fehler oder Fensterabbau. Während einer Kernfrage ruht die
  Restschätzung, und ihre Antwortzeit zählt weder als Rechenzeit noch als
  Stillstand; steht der Anteil über der Schwelle still, rechnet die Uhr nichts
  hoch (`ProgressTiming.remaining`).
* **Neben einem Lauf, an dem weitergearbeitet wird** (`_WORKED_ALONGSIDE`:
  Erzeugung, Agent), steht eine dort gesagte Ansage so lange wie ihre Blase in
  der Statuszeile, ein Hinweis, solange er gilt; danach kehrt der Fortschritt
  zurück. Ein Lauf, auf den gewartet wird, behält die Zeile.
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
**Gelesen ist nicht gezeigt:** Bereitet der Ansichtsarbeiter das erste Bild
vor (`Viewport.preparing_an_empty_view`), bleibt er mit „Das Modell wird
angezeigt …“ stehen, bis `sceneApplied` oder `sceneFailed` kommt
(`loading.veil_reason`); ohne laufende Auswertung ohne Linie und *Abbrechen*.

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
* **Datei und Slicer bekommen die feine Rechnung:** Das Fenster rechnet im
  Entwurf; Export und *Slicen*/*Im Slicer öffnen* warten auf
  `Session.fine_current` und bestellen sie über `request_fine` — der Klick
  bindet sich an das Ergebnis, der Knopf bleibt frei. Die Güte legt
  `evaluate_async` beim Start des Arbeiters fest (`_EvaluationWorker.quality`),
  nie der Lauf selbst: Sonst nimmt ein Arbeiter am Stand davor dem Nachlauf
  die bestellte Güte weg.
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
  `evaluate_now` markiert den alten Auftrag als `_superseded`, fordert
  dessen Abbruch an und bestätigt sein Ende vor dem Reset des Tokens.
  Ein unbestätigtes Ende sagt die neue Rechnung mit Handlung ab und
  behält den Arbeiter; `_on_thread_done` räumt ihn weiter auf. Kernfragen
  prüfen `_stale` während des Wartens und nach der Antwort; der Poll
  begrenzt keine aktuelle Nutzerantwort.
* **Ein Ersetzen ist kein Aufhören:** Bei `_rerun_pending` wird kein `False`
  gemeldet, und `evaluationCancelled` meldet keinen ersetzten Lauf.

### Umbau und Export rechnen im Arbeiter

* **Ein Umbau des Verlaufs** (`_RevisionWorker`, *Festschreiben* fein im
  `_BakeWorker`) rechnet auf einer Kopie und
  wird nur bei aktuellem Arbeiter und Projektstempel übernommen
  (`Session._on_revised`); Rückfragen über `ask_from_worker`, Abbrechen endet
  kooperativ mit `revisionCancelled`, und der Verlauf bleibt unverändert.
  `busy` und `wait_for_idle` umfassen ihn; ein zweiter Umbau währenddessen
  wird abgesagt, nicht eingereiht.
* **Die Exportvorbereitung ist abbrechbar** (`_ExportWorker`); erst das Schreiben
  der fertigen Nutzlast sperrt den Abbruch und den Menüeintrag. Arbeiter ohne
  Abbruch begründen die Grenze im Docstring.
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
* **Schichtansicht und Prüfbericht teilen den Netzmerker** (`findings.analysed`).
  Der Schnittarbeiter erhält das wirksame Druckraster einschließlich erster
  Schichthöhe und die Materialgrenzen. Neuer Körper, neues Raster oder neue
  Grenzen entwerten die Antwort; Ablösen und Fensterschließen brechen den
  alten Schnitt über sein `CancelSignal` ab.
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

### Eine Erzeugung läuft im Hintergrund

Weg 3 hält kein Fenster an: `GenerateDialog` ist nichtmodal, einer zur Zeit
(`MainWindow._generator`). *Erzeugen* blendet ihn aus, der Besitzer
`"generate"` zeigt Balken, Zeit und *Abbrechen* ohne Wartezeiger
(`_BACKGROUND_PROGRESS`); `runEnded` holt ihn ohne Fokus zurück.
*Übernehmen* gilt dem jetzt offenen Projekt, ein Wechsel steht vorher im
Dialog. Jeder weitere Generator nimmt diesen Weg.

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
* **Die Druckprüfung der Vorschau folgt nur einer gerechneten Antwort**
  (`Session.preview_async`, RM-090): Geschätzte Dreieckszahl und ein
  Übernehmen, das nur auf die Rechnung wartet, lassen sie aus. Einen Klick
  hält sie nur, wo das Bild Pflicht ist oder noch nicht feststeht; sonst
  entscheidet RM-493 (`_preview_can_apply`). Warum und Nachweise:
  `konzepte/begruendungen/regel-wartezeit.md`.
* **Gehört eine Handlung vor das Übernehmen, sperrt das Band den Knopf**
  (`block_apply`, bei `repair_and_retry`, `split_and_retry`,
  `recount_and_retry`) — sonst endet sie als angehaltener Schritt (Regel 19).

## Arbeiter und ihr Abbau

Ausführliche Beispiele und Fehlersuche stehen unter denselben Überschriften
in `konzepte/begruendungen/regel-wartezeit.md`.

### Ein Arbeiter erbt von `leash.Worker` und schreibt `work`

- Nie direkt `QThread.run` implementieren: Eine durchgelassene Ausnahme würde
  das Ergebnissignal auslassen. Erwartete Fehler in `work` als Ergebnis liefern;
  Unerwartetes kommt über `crashed`.
- `crashed` mit dem Fehlerpfad als `InternalError` (§33.1) verbinden; mindestens
  Wartezustand lösen, Knöpfe freigeben und Fehler erklären (`test_leash.py`).
  Nach einem Absturz keine neue Erhebung, die den Fehlertext überschreibt.
- Die Leine hält ihren Besitzer nicht stark. Modulweite Menge hält Arbeiter,
  Timer hängen am Keeper; Rückrufe auf Besitzer/Leine sind schwach. Ein
  Qt-Zyklus kann sonst beim Sammlerlauf im falschen Thread sterben.

### Wer einen Arbeiter startet, hält ihn fest

- Nur `WorkerLeash.start`, nie `worker.start` (`test_leash.py` prüft alle
  UI-Quellen). `QThread` hat keinen Qt-Elternteil: Halten beginnt beim Start.
- `finished` trifft ein, bevor Qt vollständig abgebaut hat. Der Abschluss
  erhält den konkreten Arbeiter und leert das Besitzerfeld nur bei Identität;
  ein verspäteter Vorgänger darf keinen Nachfolger entfernen.
- Erst nach `isRunning()==False` loslassen: `_hold_until_done` ruft
  `WorkerLeash.hold_until_done`, `_retire` ruft `retire`. Die Menge
  `leash._alive` und der Timer an `leash._keeper` überleben den Dialog.
  `wait_for_workers` wartet beim Ende auf alle Arbeiter.

### Wer eine `WorkerLeash` hält, hat ein `release()`

Jede Klasse mit Leine besitzt `release` (`test_widget_lifetime.py`). Fachliche
Methoden wie `wait_for_survey` bleiben daneben und werden ohne Argument
aufgerufen; der Parameter von `release` gilt der Leine.
`WorkerLeash.start` nimmt sofort in `pending`/`wait_all` auf.
`Worker.release_finished_references` löst Rückverweise erst nach zugestelltem
`finished` und `wait(0)`: nur klasseneigene Ausgangssignale/Arbeitsfelder, nie
`destroyed`, `started` oder fremde Verbindungen.

### Loslassen allein räumt nicht auf

Fenster und Tests benutzen dieselbe Reihenfolge: `release(widget)` über die
Klasse holen, `leash.wait_for_all`, mehrfach `processEvents` (ein `finished`
kann erneut einreihen), `deleteLater`, `sendPostedEvents(DeferredDelete)`,
`processEvents`, erst dann `gc.collect`. Test-Pins halten die Python-Hüllen
der rekursiv gelöschten Kinder bis zur nativen Löschung und Ereignisrunde;
dann im Hauptthread freigeben. Ohne Ereignisrunde hält das `finished`-Lambda
über `leash._alive` weiterhin Leine/Dialog und täuscht ein Leck vor.

### Die Speicherbereinigung gehört dem Hauptfaden (RM-021)

Im Fensterprozess ruht die Automatik; `leash.collect_in_main_thread` räumt im
Hauptfaden ab, gerufen in `main` vor dem ersten Arbeiter, in
`build_application` und `qt_app`.

### `undisturbed()` teilt den GC-Zustand im Prozess

`gc.disable` gilt prozessweit. Verschachtelte/überlappende Kontexte zählen
zusammen: Der erste merkt den Ausgangszustand, erst der letzte stellt ihn
wieder her. Ein früher endender Kontext darf den anderen Schutz nicht
aufheben; `test_leash.py` prüft beide Ausgangszustände mit mehreren Fäden.

### Ein Rückruf an ein eigenes Kind hält schwach

An einem Kind-Sender fängt kein Rückruf `self` stark: Lambda, geschachtelte
Funktion, `partial` und Vorgabeargument schließen denselben unsichtbaren
C++-Zyklus. Reihenfolge der Mittel: gebundene Qt-Methode, eigene Methode für
feste Werte, `weak_slot(self, Editor._tool_chosen, name)` für Schleifenwerte.
Bei gruppierten Knöpfen bevorzugt `QButtonGroup.buttonClicked` mit gebundener
Methode (`ToolStrip._on_button`).

- Die gebundene Methode ist nur in der Qt-Signalverbindung schwach; ein
  Python-Container wie `ToolStrip.add(..., self._end_split)` hält sie stark.
- Das gilt auch für `QTimer.singleShot(0, self, self._render_pending)`;
  `PartCatalog.release` beendet dessen Kette. In Schleifen `release` über
  `getattr(type(widget), "release", None)` holen und mit dem Widget aufrufen;
  `getattr(widget, ...)` hält sonst das letzte Objekt fest.
- Nichtmethodische Session-Empfänger in `release` ausdrücklich trennen:
  `session.disconnect(self)` erfasst nur gebundene Methoden. Vorschlagswächter
  nutzen `weak_slot(_proposal_context_changed)`; vor dem Trennen
  `_clear_proposal` und `_op_dialog.reject` ausführen.
- Handgeschriebene `weakref.ref`-Blöcke nur für gemeinsam erzeugte Rückrufe
  (`viewport._weak_callbacks`). Kurzlebige Sender (Arbeiter, Dialog, Animation)
  dürfen mit Vorgabeargumenten halten; ihr Ring endet mit dem Sender.
- Halter mit reproduzierbarer Lebensdauerannahme und `gc.get_referrers`
  nachweisen, nicht per Lambdasuche. Eine `cell` zeigt auf eine Closure;
  `__qualname__`/`__code__` benennen die Zeile. Genau eines von zehn erhaltenen
  Widgets spricht für eine Referenz, nicht Streuung.
- Ohne Ring zerstört der Referenzzähler sofort, auch im Nebenthread. Vor
  erneuten Versuchen Stapelabzüge und Grenzen von `gc.collect`,
  `leash.undisturbed` und `deleteLater` in `tests/conftest.py` lesen.

### Ein Filter auf einem sterblichen Widget bestellt beim `Destroy` ab

Jeder solche `eventFilter` beginnt mit `stop_watching_the_dying(self, watched,
event)` und gibt bei Erfolg `False` zurück. Nicht nötig an der
`QCoreApplication`; Begründung im verlinkten Dokument.
`test_widget_lifetime.py` prüft das Filterargument, nicht die Datei.

### `isValid` beantwortet nicht, was für ein Objekt das ist

Ein recycelter Zeiger kann ein lebendes Objekt falschen Typs (`QWidgetItem`)
tragen. In `overlay.rows_height`/`shortcut_schemes` beim Zugriff `isinstance`
prüfen und wie bei fehlendem Objekt zurückfallen; eine Eingangsprüfung
gewinnt den Wettlauf nicht.

### `isVisible()` und `hasFocus()` lügen in einem nie gezeigten Fenster

Offscreen nach dem sachlichen Zustand fragen (`pending_measure()>0`) und
Wirkung prüfen (kommt die Ziffer an?). Für tatsächliche Sichtbarkeit
`isVisibleTo(eltern)` verwenden.

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
  Prozess. Das gilt auch für den Slot eines späten Ergebnisses: Wer daraus
  etwas startet (`_foundation_found` → zweite Auswertung), fragt
  `_close_requested` wie der Start selbst — sonst läuft beim Beenden ein
  Faden, dessen Frage niemand beantwortet.

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

**Der Hauptthread greift je Bild hundertmal nach dem GIL** — jeder
Python-Filter, jede Python-Überschreibung, jeder Slot ist ein Griff, und neben
einem rechnenden Arbeiter wartet jeder. Daraus folgt:

* **Umschalten nach 1 ms, nicht kürzer** (`leash.GIL_SWITCH_S`, gesetzt in
  `main` über `configure_gil_switching`; Grund im Docstring).
* **`Worker.run` verlangt unter Windows 1 ms Zeitgeberauflösung**, solange
  `work` läuft (`_prompt_handover`). Ein Arbeiter erbt das nur über
  `leash.Worker`.
* **Kein C-Aufruf im Arbeiter hält den GIL länger als wenige Millisekunden**:
  große Listen in Blöcken, großes XML in Stücken (`threemf.XML_CHUNK`,
  `NUMBER_BLOCK`), keine Suche mit `.//` über ein ganzes Netz.
* **Was im Takt neu malt, malt nur, was sich ändert** — ein Rechteck statt
  der Fläche, ein deckendes Widget mit `WA_OpaquePaintEvent`
  (`LoadingVeil._block_rect`); sonst malt jeder Takt das Fenster darunter mit.
* **Gerätefragen laufen im Daemon-Faden** (`SpaceMouseController._search`), wie
  Dateiblicke (nächster Abschnitt).
* **Messfalle** einer Sonde am Takt: Begründung.

### Ein Blick auf eine Datei ist eine Netzfrage

`MainWindow._show_recent` prüft gemerkte Pfade in einem **Daemon-Thread**, nicht
an der Leine — ein hängendes `stat` ist nicht abbrechbar, und ein `QThread`
darin risse beim Beenden den Prozess mit. Nach 50 ms steht die ungeprüfte
Liste. Jede gemerkte Pfadliste wird so geprüft.

Auch die ComfyUI-Ordnerprüfung läuft in Daemon-Fäden (höchstens zwei
systemweit, je Dialog nur der neueste Pfad vorgemerkt); eine Antwort ändert
nach Pfadwechsel oder Schließen nichts. Nach fünf Sekunden bleibt
*Einrichten* gesperrt und sagt warum; nur eine späte erfolgreiche Antwort
derselben Generation gibt frei, einen gescheiterten Timeout löst erst ein
neuer Versuch ab.

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
  und `app_events.forget` (`test_app_events` prüft den Quelltext). Der
  Verteiler hält seine Zuhörer schwach wie `installEventFilter` — fest
  gehalten überlebte die geschlossene Ansicht samt Renderer; ein Zuhörer
  braucht deshalb einen Elternteil oder einen Besitzer.
* **Die Vorbereitung zählt, statt zu verschneiden:** `placement._patch_area`
  baut die Fläche aus ihrem Rand und prüft sie; nur Abgelehntes geht durch
  `union_all`.
