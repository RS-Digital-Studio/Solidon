# Begründungen zu `.claude/rules/wartezeit.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

Die Absätze stehen im Wortlaut der Regel vor der Verdichtung, sortiert unter
ihre heutigen Überschriften. Verweise wie „oben", „unten" oder „dieser
Abschnitt" meinen deshalb die alte Anordnung.

## Wartezeit

**Verstrichene Zeit ist keine Restschätzung.** `loading.ProgressTiming` führt
einen Sekundentakt für Schleier und Statuszeile gemeinsam; er läuft auch bei
unverändertem Fortschrittsanteil und ausgeschalteten Animationen. Eine
Kernfrage lässt die verstrichene Zeit weiterzählen, unterdrückt die
Restschätzung und zählt ihre Antwortzeit nicht als Rechenzeit. Der Takt endet
mit Ergebnis, Abbruch, Fehler oder Fensterabbau; Animationen melden keine
Zeitänderungen an Bildschirmleser.
Leere Fortschrittsmeldungen können nur eine Teilrechnung beenden, etwa das
Normalisieren vor der Erkennung. Solange `Session.busy` gilt, bleiben die
Uhr des Gesamtvorgangs und die laufende Statusanzeige bestehen.
**Eine bestätigte Vollerkennung meldet keinen Anteil, aber ihre Spanne**
(§21.1): Die Zeile heißt dann „Merkmale erkennen, geschätzt 1 bis 6 min" —
dieselbe Zahl wie die Frage davor, aus `perceive.local.recognition_minutes`
—, und die Uhr daneben zählt. **Die Spanne gilt diesem Rechner**
(`perceive.recognition_time`): Eine kurze Rechenprobe je Prozess, rund
70 ms, skaliert die Referenz. Sie gehört zur Wartezeit der Frage und prüft
`check_cancelled`; in der Erkennung läuft sie nie (§15.1).
Eine Restschätzung aus dem Anteil gibt es in
dieser Phase nicht; `detect` meldet zwischen seinen Phasen keinen Fortschritt.
**Steht der Anteil länger still als die Schwelle der Schätzung, rechnet die
Uhr nichts hoch** (`ProgressTiming.remaining`); die Antwortzeit einer Frage
zählt dabei nicht als Stillstand. Ein Abbruch während der bestätigten
Vollerkennung bekommt in der Statuszeile *Ohne Merkmalserkennung laden* —
auch unter einer gespeicherten Zustimmung beim Wiederöffnen, denn die
Auswertung meldet sie beim Start der Erkennung wie eine eben gegebene. Ein
fertiger Lauf nimmt den Knopf wieder weg.

### Wo nichts steht, steht die Ladeanzeige

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

### Vor der Auswertung: `waiting()` und der Einleseplan

**Die Ladeanzeige beginnt später, als das Warten beginnt.** Sie hängt am
Fortschritt der Auswertung; was *davor* liegt — `load()` für eine
Projektdatei —, sieht sie nicht, und ihre 200 ms kommen obendrauf. Ein Modell
liest die Sitzung seit RM-224 im Arbeiter (siehe unten), dort gibt es dieses
Loch nicht mehr. Diese Zeile der Tabelle bedient `waiting()` in `main_window.py`, ein
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
1,4 s bei acht MB) bleibt es für eine **Nutzlast ohne Pfad** — ein Download —
beim geraden Weg unter `waiting()`: Ein Arbeiter für einen Plan, der in
Mikrosekunden steht, verschöbe das Ergebnis hinter die Ereignisschleife, ohne
dass jemand darauf gewartet hätte.

**Eine Datei vom Pfad liest ein Arbeiter, und ihr Plan läuft immer im
Arbeiter** (RM-224, `_ReadWorker`). Ein Dateizugriff ist eine Netzfrage — ein
Laufwerk, das nicht antwortet, hielt das Fenster bis zum Zeitlimit des
Systems an —, und die Strukturdurchsicht einer 3MF kostete unter der Grenze
bis 0,6 s im Hauptthread. Ist schon das Lesen nachgereicht, gilt der Grund für
den geraden Weg nicht mehr; eingebettet wird dazwischen im Hauptthread. Ein
`OSError` beim Lesen ist ein Hinweis mit Weg (`loader.unreadable_file`), kein
Absturzbericht. Dasselbe gilt für den Inhalt eines Archivs, das ohnehin im
Arbeiter entpackt wurde.

**Und *Abbrechen* gilt, während das Laufwerk noch liest.** Ein `stat` oder
`read` lässt sich nicht unterbrechen; `_ReadWorker` liest deshalb in einem
Daemon-Faden (derselbe Grund wie bei „Zuletzt geöffnet“) und sieht alle 50 ms
nach seinem eigenen `CancelSignal`, das `cancel_evaluation` setzt. Abgebrochen
endet der Arbeiter sofort (`stopped` → `importFinished(False)`), die späte
Antwort des Laufwerks holt niemand ab — gemessen: frei nach 0,06 s statt nach
dem Laufwerk, Schließen des Fensters 0,07 statt 19 s (Durchsicht 0.5.1).

**Die automatische Sicherung schreibt im Arbeiter** (`Session.autosave_async`,
`_AutosaveWorker`). Im Zeitgeber des Hauptfadens stand das Fenster am
Drachen alle zwei Minuten 0,8 bis 1 s. Die Kopie des Dokuments entsteht im
Hauptfaden, geschrieben wird sie daneben; Speichern, Verwerfen und
Dokumentwechsel zählen `_autosave_epoch` hoch, und eine Sicherung, die danach
fertig wird, wird wieder geräumt. Ein Schreibfehler kommt über
`autosaveFailed` und steht einmal je Sitzung in der Statuszeile.
`Session.autosave` bleibt der gerade Weg für Tests und Werkzeuge.

**Das Modell zuerst, die Erkennung danach** (KUNDE-14, Durchsicht 0.5.1).
Ein Ladeschritt, dessen Körper noch nie im Bild standen, rechnet im selben
Arbeiter zweimal: erst ohne Erkennung (`run_evaluation(detect_features=False)`),
dann den ganzen Lauf, der die Geometrie aus dem Cache nimmt. Steht nach dem
ersten Durchgang ein Netzkörper ab `PICTURE_FIRST_TRIANGLES` da, dessen
Erkennung der Durchgang ausgelassen hat (`EvaluationResult.recognition_left_out`),
geht dieses **Bild** über `pictureChanged` ins Fenster: Es wird `last_result`,
`result_current` bleibt falsch, und alles, was ein fertiges Ergebnis verlangt,
wartet weiter. Der Schleier weicht, Uhr und *Abbrechen* bleiben. Rückfragen
des ersten Durchgangs beantwortet der zweite aus dem Gedächtnis
(`_pending.asked`/`replay`), nie ein zweites Mal am Bildschirm. Gemessen am
Piratenschiff: Modell im Bild 33 → 7,5 s, Merkmale unverändert nach rund 32 s.
Eine Änderung, die nicht lädt, rechnet wie bisher — dort bleibt das Modell ohnehin
stehen (§15.3).

**Ein Import ohne Modell wird kein Schritt** (KUNDE-12). Hält das erste Bild
oder Ergebnis nach einem Import an genau seinem Ladeschritt mit einem
`ValidationError`, nimmt `Session._settle_import` ihn zurück — ohne Redo
(`History.withdraw`), mit der Quelle — und `importRejected` sagt den Grund mit
*Andere Datei wählen*. In „Zuletzt geöffnet“ kommt eine Datei erst mit
`importConfirmed`.

**Eine STEP-Datei hat ihre eigene Grenze** (`STEP_PLAN_IN_WORKER_ABOVE`, zwei
MB, P7.4): Ihr Plan liest die ganze Baugruppe über XCAF, gemessen rund 0,6 s
je MB (0,28 s an 0,45 MB, 1,1 s an 1000 Instanzen in 2 MB). Welche Grenze
gilt, sagt `_plans_in_worker` an der Endung; ein Test, der
`PLAN_IN_WORKER_ABOVE` auf null setzt, schickt auch STEP in den Arbeiter.

Zwei Fallen dabei, beide gemessen und beide teuer:

**Der Wartezeiger des Aufrufers steht noch, wenn der Weg gerade durchläuft.**
`with waiting(): self.session.import_payload_async(…)` beim Download ist
richtig — unterhalb der Grenze steht der Zeiger, darüber kehrt der Aufruf
sofort zurück und die Ladeanzeige übernimmt. Aber ein Fehler, der aus dem
synchronen Zweig kommt, erreicht seinen Slot **innerhalb** dieses `with`, und
ein Fehlerdialog unter dem Wartezeiger ist genau das Fenster, das zugleich
fragt und bittet zu warten. `_on_import_failed` nimmt ihn deshalb selbst
zurück, bevor es `show_error` ruft. Um `import_model_async` steht kein
Wartezeiger mehr — der Aufruf kehrt immer sofort zurück.

**Und `wait_for_idle` muss jeden Arbeitertyp kennen.** Es kannte den neuen
nicht und kehrte zurück, bevor überhaupt eine Operation auf dem Stapel lag —
wer danach die Szene fragte, bekam eine leere. Wer einen Arbeiter dazubaut,
trägt ihn dort ein; sonst wartet die Schleife auf einen Lauf, den es noch gar
nicht gibt.

### Eine verspätete Antwort meldet nichts mehr

**Einleseplan und Auswertung besitzen denselben Beschäftigtzustand.**
`Session.busy` zählt beide bis zur Zustellung ihres Endsignals. Ein einzelnes
Ergebnis oder ein Fehler schaltet die Anzeige nicht aus, solange der andere
Arbeiter noch dazugehört. Das gilt auch für die leere Auswertung beim ersten
Import vom Startbildschirm: Sie kann lange vor dem Einleseplan enden.

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

**Und ein synchroner Lauf holt einen laufenden Arbeiter ein** (21.09.2026).
`evaluate_now` rechnet am Dokument von jetzt; ein Arbeiter, der dabei noch
läuft, rechnet am Stand seines Starts — meldete er sich danach, überschriebe
er das frische Ergebnis mit dem älteren. Gemessen an einem Bausteinschritt
mit anschließendem `evaluate_now`: Im Objektbaum stand die Szene ohne den
Baustein, und ein Fenstertest hing im Dialog „zwei Stellen markieren“, weil
die markierte Zeile im alten Baum nicht stand. `evaluate_now` merkt sich den
laufenden Arbeiter als `_superseded`, und `_stale` verwirft dessen
**Ergebnis** in `_on_finished` und `_on_failed` — nur das Ergebnis:
`_on_thread_done` räumt ihn weiter auf (Leine, Feld, `busyChanged`), sonst
bliebe die Anzeige stehen.

**Ein Ersetzen ist dabei kein Aufhören.** Steht `_rerun_pending`, folgt der
nächste Lauf sofort — dann wird kein `False` gemeldet, sonst flackert die
Anzeige beim Ziehen an einem Schieber im Sekundentakt. Dieselbe Begründung,
aus der `evaluationCancelled` einen ersetzten Lauf nicht meldet.

### Umbau und Export rechnen im Arbeiter

**Ein Umbau des Verlaufs rechnet im Arbeiter und übernimmt im Hauptfaden**
(`_RevisionWorker`, RM-188 P7). Er bekommt eine Kopie des Dokuments von
jetzt, rechnet den Grundstand, wenn keiner aktuell ist, und den Vorschlag;
übernommen wird nur, wenn Arbeiter und Projektstempel noch die aktuellen sind
(`Session._on_revised`). Rückfragen gehen über `ask_from_worker`, Abbrechen
reißt die Rechnung kooperativ ab und meldet `revisionCancelled` — am Verlauf
hat sich dann nichts geändert. `busy` umfasst ihn, `wait_for_idle` wartet auf
ihn, und ein zweiter Umbau während des ersten wird abgesagt statt eingereiht.

***Stand festschreiben* folgt demselben Muster** (`_BakeWorker`,
`Session.bake_strokes_async`) und rechnet fein, wie Export und Druck. Bis
RM-365 schrieb es das Entwurfsnetz des Fensters fest, und der Export war danach
gröber als ohne: An der Figur aus Weg 4 mit Raster 0,5 mm für *Weich
verschmelzen* 10 298 statt 22 098 Dreiecke, 14 346,6 statt 14 386,9 mm³, die
Form bis 0,35 mm verschoben. Fein gerechnet kostet das Sekunden, deshalb im
Arbeiter mit Fortschritt und *Abbrechen*. Übernommen wird nur, wenn der Schritt
noch dieselben Parameter und Eingänge hat wie beim Start
(`Session._bake_from`) — sonst stünde ein Stand fest, der zu keinem Zug mehr
passt.

**Ein Export bekommt Fortschritt, aber kein Abbrechen** (`_ExportWorker`). Die
Regel darüber ist nicht aufgeweicht, sie greift hier nur anders: Ein halb
geschriebener Export ist eine halbe Datei, und der Schreiber im Kern hat keinen
Punkt, an dem er sauber aufhören könnte. Was §2.8 an dieser Stelle trägt, ist
die Bedienbarkeit — der Balken läuft, das Fenster reagiert, der Menüeintrag ist
gesperrt, solange geschrieben wird. Wer einen Arbeiter ohne Abbrechen baut,
schreibt diese Begründung in seinen Docstring; ohne sie ist es Bequemlichkeit.

**Vorprüfung und Schreiben gehören demselben Exportauftrag.** Ein
bestätigter Bericht gibt nur die Körper, Quellen und Einstellungen frei, die
geprüft wurden. Die Fortsetzung übernimmt diesen Stand vom ersten Arbeiter;
sie liest weder die heutige Auswahl noch das inzwischen geänderte Dokument.
Dokument und lokale Einstellungen werden beim Start kopiert, ausgewertete
Netze bleiben unveränderliche Referenzen. Ein ausdrücklich neuer Versuch
darf den heutigen Stand einsammeln und prüft ihn erneut.

### Ein Dialog, der beim Öffnen nachsieht, öffnet erst danach

**Viermal** derselbe Fund an vier Stellen, jedes Mal gemessen: Die Liste der
zusätzlichen Programme brauchte 2,97 Sekunden bis auf den Bildschirm, die
Erstinbetriebnahme 1,88, der Chat-Dialog 2,98 — und die Druckeinstellungen
2,1 s warm, über 11 s kalt (13.09.2026, Abschnitt oben). Der Grund war jedes
Mal dasselbe — im Konstruktor stand, was ein Programm sucht, eine Profildatei
liest oder einen Port fragt.

**Der vierte ist der Beleg dafür, dass drei Funde keine Regel sind.** Er stand
drei Wochen nach den ersten dreien im Code, in einem Dialog, der zwei eigene
Arbeiter führte, und niemand hat die dritte Stelle gesucht. Wer den Abschnitt
hier liest, sucht in seinem Dialog **jeden** Konstruktoraufruf, der das
Dateisystem, die Registry oder ein Netz anfasst — nicht den einen, den er
schon kennt.

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

**Was nicht sofort da ist, wird nachgereicht statt erwartet.** Der
Druckeinstellungen-Dialog öffnet vor der Schichtanalyse. Sein `_AdviceWorker`
berechnet den gewählten Ausgabeumfang mit den aktuellen Druckwerten; nur der
passende Auftrag darf die Vorschlagsliste aktualisieren. Ändern sich Körper,
Plattenwahl oder Schichtraster, wird der frühere Auftrag abgelöst. Beim
Schließen bricht der Dialog seine Analyse kooperativ ab und hält ihre Arbeiter
bis zum vollständigen Ende, bevor er selbst freigegeben wird.

**Und was er gemessen hat, überlebt ihn.** Der Dialog wird bei jedem Öffnen
neu gebaut; bis zum 19.09.2026 schnitt er jeden Körper jedes Mal neu — an
einer Figur mit 2,3 Mio. Dreiecken siebeneinhalb Minuten (Befund Robert:
„Vorschläge beim Slicen dauern ewig"). Die Sitzung hält den letzten Stand
(`Session.remember_analyses`, Schlüssel ohne den Ergebniszähler, die Netze
werden dazu festgehalten); ein zweites Öffnen über dieselben Körper und
Schichten misst nichts mehr. Die Vorschläge lassen außerdem die Stützsäulen
aus (`slice_body(support_volume=False)`) — sie lesen sie nicht.

**Und die Suche nach den Slicern gehört dazu** (`_SlicerWorker`, 13.09.2026).
`discover.find_programs("slicer", …)` geht PATH, Registry, Flatpak, die
üblichen Installationsordner und AppImages ab; gemessen auf einer Maschine mit
sechs installierten Slicern **3,1 s warm und 11,2 bis 13,3 s kalt**, davon der
Löwenanteil in den Ordnerdurchgängen (`nt.scandir` über `Programme`, dazu rund
51 000 `is_file`). Der Aufruf stand im **Konstruktor** des Dialogs — wer
*Drucken* klickte, sah sekundenlang gar nichts. Nachher: 0,030 s bis zum
Fenster, die Antwort kommt nach 2,6 s.

Vier Dinge machen den Unterschied, und sie sind dieselben wie beim Abschnitt
„Ein Dialog, der beim Öffnen nachsieht" weiter unten:

* **Der gemerkte Slicer gilt vorläufig** (`_remembered_slicer`) — er steht in
  der Konfiguration, und ihn zu prüfen kostet einen Dateisystemzugriff. Die
  Profilsuche läuft damit sofort an, statt auf die Programmsuche zu warten.
* **Kein Zustand ohne Erhebung.** Solange gesucht wird, steht „Die Slicer
  werden gesucht …" in der Zustandszeile und als Grund an *Slicen* und *Im
  Slicer öffnen* (Tooltip, Statuszeile, Bildschirmleser — Regel 18); **nicht**
  „Dafür fehlt ein Slicer", und der Knopf *Zusätzliche Programme* bleibt weg.
  Alles andere im Dialog ist währenddessen bedienbar.
* **Kein Cache in `discover`.** `recheck_slicer` ist genau für den Kunden da,
  der gerade einen installiert hat — Solidon muss finden, was seit dem letzten
  Blick dazugekommen ist. Deshalb benutzt auch dieser Weg den Arbeiter und
  kehrt sofort zurück.
* **Ein zweiter Start ersetzt den ersten** (`_slicer_worker = None`, dieselbe
  Bauart wie bei `_start_profile_search`). Der Nachzügler kommt aus der Zeit
  *vor* der Installation und darf die Wahl nicht überschreiben.

**Und sie hält das Schließen nicht auf.** `_settle` wartet auf die Arbeiter,
die den Arbeitsordner brauchen; die Slicersuche braucht ihn nicht, und ihre
Antwort will nach dem Schließen niemand mehr. Mit ihr in derselben Liste
stand der Dialog nach *Abbrechen* oder *Filamente …* bis zu 13 s mit
gesperrten Knöpfen da — dieselbe Wartezeit, nur ans Ende verlegt. Was bleibt:
Die Leine hält den Thread, `release` wartet beim Abbau auf ihn, und das
Hauptfenster fragt vor dem Beenden über `leash.wait_for_all` nach jedem
Arbeiter, den ein weggeräumter Dialog hinterlassen hat — ein Thread, der den
Prozess überlebt, nimmt ihn mit.

**Dasselbe Muster am Schlüsseldialog, mit einer Zutat** (RM-108, 14.09.2026).
`KeyDialog` startet beim Aufbau die Erhebung (Werkzeugsuche, HTTP-Frage an
Ollama — 2,7 s, bei hängendem Dienst länger) und auf Klick die Modellprobe
(„Sekunden bis Minuten"). `reject` wartete dreißig Sekunden auf die
Erhebung, `closeEvent` zwei je Arbeiter: gemessen 10 s Stillstand nach
*Abbrechen* bei einer Erhebung, die 10 s braucht. Seither läuft alles
Schließen — *Speichern*, *Abbrechen*, Esc, Fensterkreuz — über `done`, und
`_let_go` tut je Arbeiter drei Dinge in dieser Reihenfolge: das Feld auf
`None`, die Ergebnissignale (`done`, `step`, `crashed`) ganz und jede
Verbindung zum Dialog (`worker.disconnect(self)`) trennen, den Thread an
`retire` geben — und davor setzt es `_let_go_of_workers`. **Die Zutat ist
das Trennen, und das Trennen allein reicht nicht.** Der Download hängt über
`weak_slot` an `_pull_done`, und das ist kein Slot des Dialogs, den Qt beim
Löschen selbst trennte — ohne den Schritt liefe `_pull_done` nach dem
Schließen weiter, riefe `look()` und startete auf einem geschlossenen Dialog
den nächsten Arbeiter. Und ein Signal, das beim Trennen schon in Qts Schlange
liegt, wird trotzdem zugestellt: Ein Arbeiter, der gerade zu Ende ging,
meldet `isRunning` nein, sein `done` ist eingereiht, und es kam an — gemessen
mit dem Trennen vor und nach der `isRunning`-Frage (Fund des Reviews vom
14.09.2026). Deshalb fragt jeder Ergebnis-Slot des Dialogs zuerst nach dem
Flag; der Test dazu schließt den Dialog genau zwischen Threadende und
Zustellung. Der Download wird dabei abgebrochen (Ollama setzt
beim nächsten Klick fort); Erhebung und Probe laufen aus, eine HTTP-Frage
bricht niemand ab. `release()` wartet weiter — das ist der Weg der Suite und
des Fensterendes. Nachweis:
`tests/test_chat_ui.py::test_closing_the_key_dialog_does_not_wait_for_the_model_survey`;
die fünf Dialogtests, die an der Erhebung nichts prüfen, nehmen dort die
Fixture `quick_survey`, sonst zahlt jeder Teardown die HTTP-Frist.

### Eine Erzeugung läuft im Hintergrund

Der Erzeugen-Dialog lief mit `exec()` anwendungsmodal, solange der Generator
rechnete — vierzig Sekunden bis viele Minuten, in denen im Fenster nichts ging
und der Fortschritt nur im Dialog stand (RM-371, Gebietsprüfung Weg 3). §2.8
verlangt darüber Fortschritt mit *Abbrechen* in der Statusleiste und eine
bedienbare Oberfläche.

* **Einer zur Zeit:** ComfyUI rechnet auf derselben Grafikkarte, an der der
  Kunde sitzt; zwei Läufe wären doppelte Wartezeit. Ein zweiter Aufruf holt
  den offenen Dialog nach vorn, auch mit einem neu abgelegten Bild.
* **Zur Seite statt zu:** Der Dialog behält Eingaben und fertige Versuche;
  ausgeblendet gibt er das Bild frei. Mit dem Ergebnis (oder einem Fehler mit
  Ausweg) kommt er wieder, ohne die Tastatur zu nehmen — wer gerade einen Wert
  tippt, tippt ihn zu Ende. Ein Abbruch ohne fertigen Versuch schließt ihn, die
  Statuszeile sagt es.
* **Kein Wartezeiger:** Der Besitzer `"generate"` steht zuletzt in
  `_PROGRESS_PRIORITY` und in `_BACKGROUND_PROGRESS`; was der Kunde
  währenddessen selbst anstößt, zeigt seinen Balken davor, und der Zeiger gilt
  nur dem, worauf er wartet. Sonst stünde nach jeder Auswertung minutenlang
  die Sanduhr.
* **Projektwechsel:** Während des Laufs bleibt das Fenster auch für ein anderes
  Projekt oder den Startbildschirm bedienbar. *Übernehmen* legt das Modell in
  das, was dann offen ist (ein Schritt mit Strg+Z, Regel 19), vom
  Startbildschirm aus über `_begin_from_the_start_screen`; der Dialog nennt
  den Wechsel vorher (`_say_generation_destination`). Die Absagen an
  Einfügemarke, Halt und Lizenz bleiben die von RM-361.
* **Schließen hält an:** `wait_for_workers` bricht den Wurf ab, `release`
  schließt den Dialog, denn sein `take` hält das Fenster.
* **Ein hängender Abbruch hält niemanden fest:** Während ein abgebrochener
  weiterer Versuch ausläuft, ist *Abbrechen* gesperrt (RM-418, sonst gingen die
  fertigen Versuche verloren); Esc und das Fensterkreuz lassen den Dialog dann
  zur Seite treten, und das Ende holt ihn mit den Versuchen zurück.
  `discard` schließt ihn trotzdem, für das Ende des Fensters.

## Die grobe Vorschaustufe

Ein großes Netz beantwortet keine Zahl in einer Sekunde. Gemessen am
14.09.2026 über `Session._preview_outcome` — eine Bohrung Ø 5, Entwurfs­qualität,
warmer Cache, eine Kugel als Körper:

| Dreiecke | zusammen | `evaluate` | `compare_scenes` |
|---:|---:|---:|---:|
| 20 480 | 0,16 s | 0,11 s | 0,05 s |
| 81 920 | 0,63 s | 0,47 s | 0,16 s |
| 327 680 | 2,16 s | 1,58 s | 0,58 s |
| 813 600 | 6,19 s | — | — |

Die Reihe ist linear, rund 6,6 µs je Dreieck, und die Sekunde aus der Tabelle
oben fällt bei etwa **150 000**. Dort steht `session.COARSE_PREVIEW_ABOVE`.
Darüber legt `_preview_outcome` vor die vorgeschauten Schritte eine
`decimate_mesh`-Operation auf `COARSE_PREVIEW_TARGET` Dreiecke — dieselbe
Zahl, die Schranke selbst (bis zum 26.09.2026 stand dort 50 000; warum nicht
mehr, steht unten unter „Und das Ziel ist die Schranke selbst") —, in der
**Dokumentkopie**, die die Vorschau ohnehin rechnet, und nur dort. Was
übernommen wird, rechnet weiterhin genau.

**Sie nimmt den Anzeigeweg** (Entscheidung Robert, 23.09.2026, RM-208):
`method="fast"` an `decimate_mesh` ruft `mesh_ops.decimate_for_display` —
Kern nach Sehnenfehler, dann Raster, ohne Messung. Die Werte stehen einmal in
`session._coarse_params`, für beide Wege (`_coarse_drafts`,
`_coarse_steps_before`). Vorgabe der Operation bleibt `"measured"`; ein
Projekt ohne den Parameter rechnet wie zuvor (`cache_version="2"`). Der
gemessene Weg war für die Vorschau doppelt falsch: An der Lochplatte mit
815 104 Dreiecken stand er 24 s im Quadrik-Solver, und sein Netz war offen —
jede Bohrung darauf lief die Boolesche Kette hinunter, die grobe Vorschau war
langsamer als die genaue (22–24 gegen 13 s je Zahl), und an drei von fünf
Kundenmodellen sagte sie eine Absage, wo die genaue ein Ergebnis hat.

* **Beide Seiten auf demselben groben Netz.** `davor` und `danach` gehen
  durch dieselbe Verkleinerung (`_coarse_before` wertet die Kopie ohne die
  Entwurfsschritte aus und merkt sich das Ergebnis, solange die Szene davor
  dieselbe ist). Getrennt verkleinert wäre es keine Abkürzung, sondern ein
  Fehler mit zwei Gesichtern — gemessen an einer Kugel aus 81 920 Dreiecken:
  16,7 mm³ Material, das niemand angefasst hat, **und** zehn bis fünfzig
  Sekunden für die Rechnung darüber, weil zwei fast deckungsgleiche Häute der
  schlimmste Fall für jeden Booleschen Kern sind. Langsamer und falsch.
* **Das Band sagt es** — „Grobe Vorschau — beim Übernehmen wird genau
  gerechnet", als Text und nicht als zweite Farbe (Regel 18). Der Satz steht
  **vor** „am Volumen ändert sich nichts": Auf einem vergröberten Netz ist
  eine leere Differenz keine Zusage. Er steht **hinter** „Vorschau
  unvollständig": Eine halb gerechnete Differenz ist der schwerere Vorbehalt,
  und sie darf nie als bloß neu vernetzt erscheinen.
* **Die Merkmale bleiben erkennbar.** Gemessen am 23.09.2026 am Anzeigeweg,
  Kugel r = 20 mm aus 327 680 Dreiecken, Ø-5-Bohrung nach der Verkleinerung
  (`konzepte/nachweise-release-0.5.0/sonden/vorschau/probe_sphere_table.py`); genau: Geschlecht 1, erkannte
  Bohrung 5,20 mm, 843,5 mm³ Abtrag:

  | Ziel | Dreiecke | Abweichung | Geschlecht | Loch | abgetragen |
  |---:|---:|---:|---:|---:|---:|
  | 100 000 | 7 556 | 0,0489 mm | 1 | 5,20 mm | 842,7 mm³ |
  | 50 000 | 7 556 | 0,0489 mm | 1 | 5,20 mm | 842,7 mm³ |
  | 20 000 | 7 556 | 0,0489 mm | 1 | 5,20 mm | 842,7 mm³ |
  | 5 000 | 1 916 | **0,1909 mm** | **3** | 5,20 mm | 838,4 mm³ |
  | 2 000 | 1 916 | **0,1909 mm** | **3** | 5,20 mm | 838,4 mm³ |

  Die Grenze ist `units.MAX_FACET_SAG` = 0,05 mm — dieselbe, mit der beide
  Kerne tessellieren, und die, mit der der Anzeigeweg beginnt. Abweichung
  heißt hier: jede alte Ecke gegen die neue Fläche (`deviation(grob, genau)`);
  die Gegenrichtung ist null, der Kern lässt Ecken weg und bewegt keine.
  Solange der Sehnenfehler allein unter das Ziel führt, bleibt er die
  Abweichung, egal wie hoch das Ziel ist. Erst ein Ziel darunter vervierfacht
  die Toleranz, und dann reißt beides — Abweichung und Geschlecht. Ein
  Körper, dessen Form bei 0,05 mm mehr als 150 000 Dreiecke braucht (eine
  Figur, ein Scan), wird gröber als die Grenze; das Band sagt „grob" auch
  dann.
* **Die Verkleinerung des unveränderten Eingangs wird gemerkt.**
  `_coarse_before` rechnet sie **vor** der Vorschau, in einem eigenen
  Durchlauf unter dem Signal der Vorbereitung (`Session._coarse_cancel`),
  und merkt die grobe Szene je Szene und Schritt (`_coarse_scene`); eine
  Sperre (`_coarse_lock`) lässt zwei Arbeiter nicht dieselbe rechnen. Der
  Grund: `evaluate` legt seine Ergebnisse **erst nach einem vollständigen
  Durchlauf** in den Cache. Stand die Verkleinerung in der Auswertung der
  Vorschau, ging sie mit jeder abgelösten Anfrage und jedem ungültigen
  Zwischenwert verloren — 27–30 s Verkleinerung **je** Loslassen des
  Platzierungsgriffs an 815 104 Dreiecken (Bericht Ansicht, 23.09.2026).
  Deshalb trennt die Sitzung zwei Wege: `supersede_preview` (eine neue
  Zahl — die Vorbereitung läuft weiter, die nächste braucht sie) und
  `cancel_preview` (Dialog zu, *Abbrechen* — sie hält mit an). Nachweis:
  `test_evaluation.py::test_the_coarse_reduction_of_the_unchanged_input_outlives_a_superseded_preview`.

Was das bringt, am 23.09.2026 an den hochgerechneten Lochplatten und an
Kundenmodellen aus `F:\3D Dateien` vorher und nachher gemessen
(`konzepte/nachweise-release-0.5.0/sonden/vorschau/probe_preview.py`, *Bohrung* Ø 5 → 6 → 7 wie der Dialog,
belastete Maschine; „danach" ist jede weitere Zahl):

| Modell | Dreiecke | grob erstmals | grob danach | genau |
|---|---:|---:|---:|---:|
| Lochplatte, viermal unterteilt | 203 776 | 14,2 → **0,23 s** | 3,4–3,9 → **0,04–0,05 s** | 1,7–1,8 s |
| Lochplatte, fünfmal unterteilt | 815 104 | 62,1 → **0,96 s** | 22,5–24,4 → **0,17–0,21 s** | 7,1–13,6 s |
| Waschschüssel (offen) | 215 072 | 3,9 → 1,2 s | 0,7–0,9 → 0,55–0,59 s | 3,8–4,9 s |
| Gartenschlauchhalter | 392 532 | Absage → 11,6 s | Absage → 1,1 s | Absage (Entwurfskette) |
| Eiffelturm | 312 938 | **falsche Absage** → genau, 13,8 s | Absage → genau, 9,6–11,1 s | 8,8–11,1 s |
| Voronoi-Spiderman | 885 570 | **falsche Absage** → genau, 20,6 s | Absage → genau, 13,7–20,9 s | 11,7–17,7 s |
| Piratenschiff-Baugruppe | 1 223 838 | **falsche Absage** → genau, 26,4 s | Absage → genau, 17,7–28,1 s | 19,6–37,5 s |

Das abgetragene Volumen der groben Vorschau gleicht an beiden Platten dem
genauen (166,2 / 237,0 / 320,3 mm³), an der offenen Schüssel liegt es 1,8 %
darüber (Raster). An den letzten drei Zeilen legt der Anzeigeweg im Raster
zusammen, die Bohrung scheitert am groben Netz, und die Vorschau rechnet genau
(`_kernel_gave_up`, unten) — so lange wie genau, aber mit einem Ergebnis statt
der Absage von vorher. Die Maschine war bei beiden Läufen unterschiedlich
belastet (Öffnen desselben Eiffelturms 55 bis 102 s); die Spannen sind
Streuung, die Größenordnungen nicht.

**Und das Ziel ist die Schranke selbst** (26.09.2026, RM-212). Mit 50 000 als
Ziel kamen die letzten drei Zeilen nie grob durch: Der Kern bringt den
Spiderman nicht unter 122 952 Dreiecke, das Piratenschiff nicht unter 64 468,
den Eiffelturm nicht unter 57 680 — jenseits dieses Minimums steigt die Zahl
mit der Toleranz wieder. Der Anzeigeweg nahm dann das Raster, dessen Netz
offen ist, und jede Zahl rechnete erst grob vergeblich und dann genau. Mit der
Schranke als Ziel nimmt er das geschlossene Kernergebnis. Zwei Fallen lagen
dahinter, beide im Rückweg ins Netz: `simplify` ließ am Piratenschiff zwölf
Splitter neben dem Rumpf stehen, im Mittel dünner als seine Toleranz
(`kernel_jobs.without_slivers` lässt sie weg), und `_as_mesh` verschweißte
Schalen, die sich an einer Kante berühren, bis vier Flächen an ihr hingen —
am Eiffelturm zwei echte Teile (seither verschweißt es nur, wo das Netz dicht
bleibt, wie `boolean._tidied`). Gemessen mit derselben Sonde, vorher und
nachher unmittelbar hintereinander, ruhige Maschine:

| Modell | grob erstmals | grob danach | genau |
|---|---:|---:|---:|
| Lochplatte, fünfmal unterteilt | 0,69 → 0,71 s | 0,12 → 0,13–0,17 s | 2,9–4,0 s |
| Waschschüssel (offen) | 0,45 → 0,69 s | 0,22 → 0,49–0,53 s | 1,2–1,4 s |
| Eiffelturm | Absage → genau, 4,3 s → **grob, 2,3 s** | 2,8–2,9 → 1,7 s | 2,4–4,5 s |
| Voronoi-Spiderman | Absage → genau, 48,2 s → **grob, 1,7 s** | 17,8–18,9 → **0,59–0,66 s** | 17–46 s |
| Piratenschiff-Baugruppe | Absage → genau, 16,0 s → **grob, 2,0 s** | 11,1–13,4 → **0,66–0,68 s** | 9,5–13,2 s |

Den Preis zahlt die Schüssel: Ihr grobes Netz bleibt beim Sehnenfehler
(69 674 statt 25 542 Dreiecke bei 0,2 mm), jede Zahl kostet eine halbe
Sekunde statt einer Viertelsekunde — und ihr Abtrag weicht um 0,1 statt 1,8 %
vom genauen ab. Am Eiffelturm, am Spiderman und am Piratenschiff liegt die
Abweichung bei 0,4, 3 und 0,04 %. Die Platte bekommt dasselbe grobe Netz wie
vorher (292 Dreiecke); ihre Zeilen sind die Streuung des Laufs.

**Was an der Dreieckszahl hängt, wird am Original gezählt, nicht an der
Kopie** (Durchsicht 0.5.1, RESTVERLAUF-04). Die verkleinerte Kopie hat eine
andere Zahl als der Körper des Kunden, und für drei Operationen ist die Zahl
die Antwort: Am Spielbrett aus `F:\3D Dateien` zählte das Original bei 1 mm
11,97 Mio. Dreiecke — zu fein —, die Kopie 7,8 Mio.; die Vorschau rechnete, und
*Übernehmen* hielt danach an. *Dreiecke verringern* sagte an der Kopie des
Spielwürfels (3 858 von 250 488 Dreiecken) „Die Fläche hat sich dabei kaum
verschoben.", ohne etwas verringert zu haben. `_preview_outcome` fragt deshalb
im Dialog zuerst `OperationSpec.expected_triangles` am Eingang des Schritts
(`_counted_ahead`; beim Ändern die Szene **vor** dem Schritt,
`_scene_before_step`), und diese Körper bekommen keine Kopie. Drei Ausgänge:

* **Die Zählung sagt ab** — dann ist das die Antwort. Das Band trägt den Satz,
  und `preview_async(refused=…)` reicht die Ausnahme ins Fenster; der Dialog
  zeigt unter den Feldern die Handlungen, die er selbst einlöst
  (`OperationDialog.show_refusal`, `MainWindow._refusal_handlers`): *Die
  kleinste Kantenlänge nehmen, die noch geht.* schreibt die Zahl ins Feld,
  *Dreiecke verringern und erneut versuchen* schreibt Verringern und Schritt
  als eine Transaktion. Derselbe Weg trägt die Absage eines Halts
  (`_stop_finding`) — etwa das umgestülpte *Glätten* mit *Kanten verfeinern
  und erneut versuchen*.
* **Die Operation ändert nur das Netz** (`retriangulates`) **und es wüchse über
  `COARSE_PREVIEW_ABOVE`** — dann ist die Zahl die Vorschau: „Vorschau — aus
  250 488 werden geschätzt 6 100 000 Dreiecke" (geteilt wurden es 5 778 968;
  am Spielbrett bei 1,53 mm 6,4 statt 4,1 Mio. — deshalb „geschätzt" und nicht
  „rund"), gerechnet wird nichts
  (`preview_async(counted=…)`, `TriangleCounts`). Am Spielwürfel bei 0,05 mm
  stand die Vorschau vorher über zehn Minuten im Booleschen Vergleich einer
  auf 4,5 Mio. geteilten Kopie, und *Übernehmen* hieß „Wird übernommen, sobald
  die Vorschau steht."; jetzt 0,07 s.
* **Sonst rechnet der Schritt am Original** — ohne Kopie, und bei
  `retriangulates` ohne Booleschen Vergleich: Die Differenz ist das neue Netz
  (`compare_scenes(retriangulated=…)`), das Band nennt die gezählte Zahl.
  *Dreiecke verringern* auf 60 000 am Spielwürfel: genau gerechnet 69 s, jetzt
  0,75 s.

Ein exakter Eingang wird nicht vorab gezählt: Seine Umwandlung muss das Band
nennen, und dafür muss der Schritt rechnen — ohne Booleschen Vergleich, wo er
nur das Netz ändert. Der Agentenweg zählt nicht vorab; er rechnet ohnehin
genau.

**Ein Weg bleibt genau, mit Absicht.** Der Agentenvorschlag geht über
`preview_scene` ohne den Rückruf — er antwortet ohnehin nicht in
Millisekunden, und sein Bild steht, bis jemand es annimmt.

**Das Ändern eines Schritts** (`change_op`) nimmt die Stufe seit dem
22.09.2026: Die Verkleinerung steht in der Dokumentkopie **vor** dem
geänderten Schritt (`_coarse_steps_before` — die Schritte danach rücken um so
viele Nummern auf, wie Verkleinerungen davor kommen; das geht nur in der
Kopie, die niemand speichert, und `evaluate` liest nur den Stapel), und
`_coarse_before` rechnet die Vorher-Seite mit demselben eingefügten Schritt
am ungeänderten Wert, gemerkt je Szene und Schritt. Gemessen am Ändern eines
Bohrdurchmessers an 204 000 Dreiecken: 1,1 s je getippter Zahl davor, 40 ms
ab der zweiten — die erste trägt die Verkleinerung selbst. Seit dem
Anzeigeweg (RM-208) kostet die erste an der Platte mit 815 104 Dreiecken
0,34 s statt 33 s, jede weitere 0,14 s.

**Der Kern hält beim ersten Mal den GIL.** `manifold3d.simplify` gibt ihn
nicht her (siehe „Ein Arbeiter ist nur nebenläufig …"); die erste grobe
Vorschau steht damit für die Dauer des Kerns auch im Hauptthread. Gemessen
mit einem 5-ms-Takt neben dem Arbeiter, längste Lücke: Lochplatte 815 104
Dreiecke 568 ms, Waschschüssel 149 ms, Eiffelturm 1,3 s, Spiderman 2,0 s —
der gemessene Weg davor 378 ms, 7,9 s und 2,2 s, und zwar **bei jeder**
Vorschau, die nicht vollständig durchlief. Jetzt einmal je Körper und
Dialog. Seit das Ziel die Schranke ist (RM-212), sucht der Kern nicht mehr
bis zum Raster weiter; dieselbe Sonde, vorher und nachher hintereinander:
Lochplatte 252 → 250 ms, Waschschüssel 60 → 89 ms, Eiffelturm 664 → 120 ms,
Spiderman 799 → 324 ms, Piratenschiff 819 → 492 ms. Ganz weg ist es erst
mit einem Kern, der den GIL hergibt — `manifold3d` gibt ihn bei keinem
Aufruf her, auch nicht beim Bauen des Körpers (RM-212).

**Weg ist es mit dem Hilfsprozess** (RM-212, Entscheidung Robert vom
27.09.2026): Die Verkleinerung und die Bohrung am groben Netz rechnen dort
(`geom.kernel_process`). Derselbe Weg, im Wechsel gemessen
(`konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/grob_stillstand.py`, 28.09.2026): Lochplatte 516 → 92 ms,
Spiderman 573 → 7 ms, Piratenschiff 874 → 6 ms, Eiffelturm 425 → 75 ms,
Waschschüssel 95 → 4 ms, derselbe Abtrag.

**Und die Vorschau des Dialogs erkennt keine Merkmale** (22.09.2026).
`preview_async` reicht `detect_features=False` bis in `evaluate`: Die
Erkennung läuft dann nur noch dort, wo ein späterer Schritt oder eine Passung
ein Merkmal des Körpers braucht; was der Merker kennt, kommt trotzdem.
Gemessen am Ändern eines Bohrdurchmessers an 204 000 Dreiecken: 2,2 s je
getippter Zahl, davon 1,1 s Erkennung am geänderten Körper — für Merkmale, die
kein Bild zeigt und die beim Übernehmen ohnehin neu entstehen. Danach 1,1 s;
was bleibt, sind die Operation (0,35 s) und `compare_scenes` (0,25 s seit dem
Beschnitt auf die Änderungsbox, `geom.difference`). Der Agentenweg über
`preview_scene` erkennt weiter, sein Steckbrief liest die Merkmale.

Scheitert das Verkleinern — zu wenige Dreiecke, ein Körper, der keiner ist —,
hält die Kette an seinem eigenen Schritt an, und `_preview_outcome` rechnet
denselben Entwurf noch einmal genau. **Dasselbe, wenn der Kern am groben
Netz aufgibt** (`_kernel_gave_up`: der Halt ist eine `GeometryError`, etwa
die erschöpfte Boolesche Kette). Wo der Kern das Netz nicht nimmt, legt der
Anzeigeweg im Raster zusammen, und das Ergebnis ist oft kein Körper mehr —
am Eiffelturm, am Voronoi-Spiderman und am Piratenschiff stand sonst
„Auch die letzte Rückfallstufe hat kein brauchbares Ergebnis geliefert",
wo die genaue Vorschau ein Ergebnis hat. Ein ungültiger Wert
(`ValidationError`, `UserError`) bleibt am groben Netz derselbe und rechnet
nicht zweimal. Der Kunde sieht davon nichts außer der längeren Wartezeit —
und die hat seit RM-208 über zwei Sekunden Balken und *Abbrechen*.
Nachweis: `test_evaluation.py::test_a_coarse_preview_the_kernel_refuses_is_computed_exactly`.

### Die Vorschau über zwei Sekunden, und was ihr Band sagt

**Über zwei Sekunden bekommt die Vorschau Balken und *Abbrechen*.** Ein
eigener Besitzer im gemeinsamen Fortschrittsbereich (`"preview"` in
`_PROGRESS_PRIORITY`), gestuft wie jeder Lauf: das Band nach 0,2 s
(`_preview_busy`), Zeiger und Zeile ebenso, Balken und *Abbrechen* nach 2 s
(`_bar_delay`). Die Zeile nennt den laufenden Schritt aus dem Fortschritt der
Auswertung (`preview_async(progressed=…)`), ohne Prozentzahl — `evaluate`
zählt Schritte, und bei einem Stapel im Cache stünde der Balken sofort bei
neun Zehnteln. *Abbrechen* (`MainWindow._cancel_preview_run`) hält die
Rechnung an (`Session.cancel_preview`, samt Vorbereitung), nimmt ein Bild
einer früheren Zahl aus der Ansicht, und das Band sagt „Vorschau abgebrochen
— das Modell bleibt, wie es war. Ein geänderter Wert rechnet sie neu." Der
Dialog bleibt offen; *Übernehmen* rechnet genau oder fordert die Vorschau neu
an, wo sie Pflicht ist, ein wartender Klick verfällt. Vor `compare_scenes`
fragt `_preview_outcome` das Abbruchsignal, weil der Vergleich keines kennt.
Den Besitzer beenden die Antwort des Arbeiters (`shown`, `explained`,
`failed`), jede Ablösung (`_set_preview_order`) und jeder Abbau
(`_forget_preview_approval`). Nachweis (Fenstertest, beim Release):
`test_operation_ui.py::test_a_long_preview_offers_cancel_and_cancelling_leaves_the_model`.

**Was die Operation gar nicht ändert, sagt das Band mit ihren Worten.** Über
einer leeren Differenz ist jeder Befund des vorgeschauten Schritts die bessere
Auskunft als der Füllsatz — `_warning_of` reicht deshalb auch `info` durch
(`mesh.already_below_target`, `repair.nothing_to_do`, `mesh.not_simplified`,
`sculpt.empty`), Warnung und Fehler behalten den Vortritt. Eine
leere Differenz bekommt „am Volumen ändert sich nichts" nur, solange weder ein
Befund noch das Register etwas Besseres weiß; `OperationSpec.unchanged_effect`
nennt sonst
die Lage (`report` für die Prüfwerkzeuge, `name` fürs Umbenennen), und
`_show_preview` übersetzt sie in einen eigenen Satz — eine Namensliste im
Fenster schwiege beim dritten Prüfwerkzeug. **Und trägt der Grund eine
Handlung, die vor das Übernehmen gehört, sperrt das Band den Knopf:**
`_stop_advice` beziehungsweise `_advice_of` schicken die Kennung der
vorrangigen Handlung über `preview_async(advised=…)` voraus, und bei
`repair_and_retry`, `split_and_retry` und `recount_and_retry` ruft
`_preview_explained` das `block_apply(grund)` des Dialogs — sonst endet „Erst
reparieren, dann aushöhlen" drei Klicks später als angehaltener Schritt im
Verlauf (Regel 19). Das nächste Bild gibt ihn über `block_apply(None)` frei.

## Arbeiter und ihr Abbau

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

**Die Leine hält ihren Besitzer nicht.** Das Fenster besitzt seine
`WorkerLeash` bereits. Ein starker Rückverweis von der Leine zum Fenster baut
einen Python-Zyklus um ein Qt-Objekt; dessen verspäteter Sammlerlauf kann die
C++-Hülle in einem Arbeiter-Thread oder mitten im Aufbau des nächsten Fensters
zerstören. Die modulweite Arbeitermenge hält nur die Arbeiter. Zeitgeber hängen
am langlebigen Keeper, und Rückrufe auf Besitzer und Leine bleiben schwach.

**Und nach einem Absturz wird nicht neu erhoben.** Der Installationsdialog tat
das und überschrieb seine eigene Meldung eine Sekunde später mit der
Zusammenfassung der Erhebung — der Kunde hatte den Satz gesehen und nicht
gelesen.

### Wer einen Arbeiter startet, hält ihn fest

Ein `QThread` bekommt hier keinen Qt-Elternteil; ihn hält allein die
Python-Referenz. Fällt sie weg, während der Thread noch läuft, zerstört der
Speicherbereiniger das C++-Objekt unter ihm — eine Zugriffsverletzung ohne
Zeile, irgendwann später und selten reproduzierbar.

Das geht zweimal schief. `finished` kommt, während Qt den Thread noch abräumt —
zu früh zum Loslassen. Und es trifft das Feld, nicht den Arbeiter: wird ein
Vorgänger fertig, nachdem sein Nachfolger im Feld steht, löscht er dessen
Referenz.

**Richtig** ist ein benannter Slot, der seinen *eigenen* Arbeiter erkennt und
ihn danach der gemeinsamen Halteleine übergibt:

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

`WorkerLeash.start()` nimmt den Arbeiter sofort in den eigenen gehaltenen
Bestand auf. Die globale Menge schützt seine Lebenszeit; `pending()` und
`wait_all()` müssen ihn ebenfalls schon vor dem Fertigsignal kennen, damit
das Aufräumen keinen aktiven Arbeiter übersieht.

Ein vollständig beendeter Arbeiter darf seinen alten Arbeitskontext ebenfalls
nicht bis zu einem späteren Sammlerlauf festhalten. Die Leine löst solche
direkten Rückverweise über `Worker.release_finished_references()` erst nach
der zugestellten eigenen `finished`-Antwort und dem zusätzlichen Nachweis
`wait(0)`. Das fachliche Ergebnis, ein Abbruch oder ein Fehler ist dann bereits
zugestellt. Der Haken trennt nur die von der Workerklasse selbst deklarierten
Ausgangssignale und ihre reinen Arbeitsfelder; `destroyed`, `started` und
fremde Verbindungen werden nie pauschal gelöst.

**Der Parameter gilt der Leine, nicht der Sache.** `release()` reichte seine
2000 ms an `wait_for_look` weiter, wo 30 000 stehen — damit bekam eine
Erhebung, die eine halbe Minute haben darf, zwei Sekunden. Gemessen an
`test_chat_ui`: 2 von 4 Läufen starben danach beim Abbau, gegen 4 von 4 nach
der Berichtigung. Die fachliche Methode wird ohne Argument gerufen.

### Loslassen allein räumt nicht auf

Ein Test-Pin fällt erst **nach** `sendPostedEvents(DeferredDelete)` und dem
anschließenden Ereignislauf. Qt löscht ein Elternfenster samt Kinddialogen
rekursiv; währenddessen müssen deren Python-Hüllen stark gehalten bleiben.
Erst wenn die C++-Löschung vollständig zugestellt ist, wird die Pin-Liste
geleert. Danach sammelt der Testabbau die jetzt ungültigen Python-Hüllen im
Hauptthread ein. Ohne diesen letzten Schritt blieben je UI-Test hunderte
zyklisch gehaltene Hüllen zurück, bis eine spätere Allokation ihren Abbau
auslöste. Die nativen Abbrüche wanderten zwischen Allokationsstellen; einen
bestimmten auslösenden Faden belegt diese Messung nicht. Direkte
Lebensdauertests beobachten die
Eltern-Weakref im `destroyed`-Signal des Kindes und einen Python-Ring zwischen
gelöschtem Eltern- und Kindwidget; nach dem gemeinsamen Abbau verschwinden
beide.

**Der `processEvents`-Schritt ist der, den man vergisst**, und ohne ihn liest
man ein Leck, wo keines ist: `leash._alive` hält einen Arbeiter modulweit, der
hält über sein `finished`-Lambda die Leine und damit den Dialog; abgeräumt
wird erst, wenn das Signal ankommt.

Historischer Messstand vor dem geordneten Qt-Abbau:

| damaliger Weg | überlebende Widgets |
|---|---|
| nur loslassen | 10 von 10 |
| `release()` | 10 von 10 |
| `release()` + Schleife | 0 von 10 |

Dass die mittlere Zeile sich nicht bewegt, ist der Grund, warum drei Klassen
zwei Monate lang als „hält, aber erklärbar" in einer Ausnahmeliste standen.

### Ein Rückruf an ein eigenes Kind hält schwach

**Die allgemeine Form, und sie ist häufiger als ihre bekannten Fälle:** Ein
Rückruf, der `self` stark fängt, an einem Sender, der ein **Kind von `self`**
ist, schließt einen Ring — `self` → Sender → Rückruf → `self`. Er läuft über
die C++-Grenze, und Pythons Speicherbereiniger sieht die mittlere Kante nicht;
er kann den Ring also nicht brechen. Das Objekt lebt bis zum Prozessende.

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

**Wo die Knöpfe einer Schleife eine Gruppe haben, ist die Gruppe besser als
die dritte Wahl:** ein Empfänger an `QButtonGroup.buttonClicked`, als gebundene
Methode, der den Knopf in seinem Wörterbuch nachschlägt
(`ToolStrip._on_button`). Gemessen am 22.09.2026: `weak_slot` je Knopf an der
Werkzeugzeile löste den Ring, riss aber `test_widget_lifetime` beim
Einsammeln drei von drei Läufen mit einer Zugriffsverletzung ab; die Gruppe
löst denselben Ring, und die Datei ist grün (zwei von zwei). Warum die eine
Form reißt und die andere nicht, ist nicht aufgeklärt — gemessen ist nur,
dass es so ist.

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

**Und ein Empfänger an der Sitzung, der keine Methode ist, geht in
`release()`.** Die Sitzung überlebt das Fenster (Sprachwechsel), und
`session.disconnect(self)` trennt nur gebundene Methoden: Eine Closure am
`sceneChanged` — der Wächter eines wartenden Vorschlags, das `changed` des
Operationsdialogs — blieb hängen und rief das nächste Ergebnis in zerstörte
Widgets (Review 21.09.2026). Der Wächter ist deshalb ein `weak_slot`
(`_proposal_context_changed`), und `release()` räumt Vorschlag und Dialog
selbst (`_clear_proposal()`, `_op_dialog.reject()`), bevor es trennt.

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

Warum die Knopfgruppe den `weak_slot` schlägt: `weak_slot` je Knopf riss
`test_widget_lifetime` mit einer Zugriffsverletzung (Ursache bei RM-021).

### Ein Filter auf einem sterblichen Widget bestellt beim `Destroy` ab

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

## Nebenläufig heißt: Der Hauptthread bleibt frei

### Ein Bild je Ereignisrunde ist kein Nebenläufigkeitsverfahren

Die Vorschaubilder des Objektbaums entstanden „eines je Aufruf", verkettet
über `QTimer.singleShot(0, …)`, mit der richtigen Begründung: Bei einem
gescannten Teil kostet ein Bild achtzig Millisekunden, und fünf am Stück sind
eine halbe Sekunde Stillstand.

**Die Rechnung stimmte, die Abhilfe nicht.** Ein `singleShot(0)` kehrt in
derselben Ereignisrunde zurück; die Arbeit wird also nicht verteilt, sondern
nur in Portionen zerlegt, die unmittelbar aufeinander folgen. Gemessen an
`1-24+scale+polebarn.3mf` (89 Körper): **4,7 s** Hauptthread nach dem Öffnen,
in Schüben von 400 bis 775 ms — davon 2,96 s im Vereinfachen der Netze für ein
Bild von zwanzig Pixeln (Robert: „bei einer auswahl oder hover effekt stockt
es auch noch sehr"). Nachher **9 ms**; die Bilder kommen nach 4,7 s an, und
das Fenster ist die ganze Zeit bedienbar.

Drei Sätze, die über diesen Fall hinausgehen:

* **Was kein Qt braucht, gehört nicht in den Qt-Thread.** `drawing.thumbnail`
  endet in einer Zeichenkette; Qt braucht erst das Malen des fertigen SVG, und
  das ist ein Zehntel der Kosten. Die Grenze verläuft an dieser Frage und
  nicht an der Zahl der Millisekunden.
* **Ein Arbeiter bekommt Arrays, kein Netz** (`drawing.thumbnail_of`). Auf
  demselben `Trimesh` zu rechnen füllt dessen träge Caches neben dem
  Hauptthread — dieselbe Falle, die `placement_flow.for_a_worker` mit einer
  Kopie umgeht. Punkte und Dreiecke zu lesen ist gefahrlos, solange niemand
  sie ändert, und eine Eingabe ändert in Solidon niemand (Regel 3).
* **Und die Portionierung bleibt trotzdem sichtbar.** Der Arbeiter meldet
  jedes Bild einzeln (`_ThumbnailWorker.drawn`), die Zeilen kommen also
  weiter nacheinander nach. Ein Signal am Ende hätte dieselbe Rechnung und
  vier Sekunden leere Zeilen.

* **Ein Bild wird nicht wie eine Operation dezimiert.** `drawing.thumbnail`
  rief `mesh_ops.decimate`, den Weg der Operation *Netz vereinfachen* — und
  der steht an CAD-Exporten mit Fächern um jede Bohrung still:
  `fast_simplification` lehnt dort jeden Kollaps ab, nach vier Sekunden
  waren an der Lochplatte mit 203 776 Dreiecken noch 197 458 da, das SVG
  daraus kostete 1,5 s und sein Rendern 0,8 s im Hauptthread (22.09.2026,
  Robert: Verschieben dauerte acht Sekunden). Die Anzeige ab der Schwelle
  aus §31, die Beispielbilder und der Stellvertreter der Orientierungssuche
  nehmen `mesh_ops.decimate_for_display`: den exakten Kern nach
  Sehnenfehler, dann das Raster. **Das Vorschaubild des Baums nimmt nur das
  Raster** (`mesh_ops.raster_for_display`) — der Grund steht im nächsten
  Abschnitt.

* **Freigegeben heißt: nichts mehr anfangen.** `show_scene` stellt den Start
  des Zeichners mit `singleShot(0)` zurück. `ObjectTree.release` leert den
  Vorrat, bevor es wartet, und `MainWindow.release` ruft es — sonst startete
  der Zeitgeber nach dem Warten einen Zeichner, auf den niemand mehr wartete,
  und der Thread überlebte den Prozess (`QThread: Destroyed while thread is
  still running`, Exit 127; gemessen am 21.09.2026 an fünf Fällen in
  `test_operation_ui`, deren Test keine Ereignisrunde durchlief).

### Ein Arbeiter ist nur nebenläufig, wenn er den GIL hergibt

Das Vorschaubild lief im Arbeiter, und trotzdem stand das Fenster nach jeder
Operation und jedem Rückgängig: `manifold3d` hält den GIL während
`simplify`. Ein Thread im Hintergrund, der den GIL nicht hergibt, ist für die
Ereignisschleife dasselbe wie Arbeit im Hauptthread. Gemessen mit einem
10-ms-Takt im Hauptthread, größte Lücke während eines Bildes:
Besenhalter (59 740 Dreiecke) 456 ms mit dem exakten Kern gegen 3,8 ms mit
dem Raster, Baum (166 400) 800 gegen 3,4 ms, Kumiko-Schale (94 990) 271
gegen 13,7 ms. Am Fenster: Übernehmen 380 → 52 ms, Rückgängig 390 → 60 ms.

Zwei Sätze daraus:

* **Wer einen Arbeiter baut, misst den Hauptthread, nicht den Arbeiter.**
  „Läuft im Hintergrund" sagt nichts darüber, ob die Oberfläche weiterläuft.
  Die Probe ist ein Zeitgeber im Hauptthread und die größte Lücke zwischen
  zwei Takten, solange der Arbeiter rechnet.
* **Für zwanzig Pixel genügt das Raster.** Der exakte Kern bleibt, wo die
  Form zählt — in der Anzeige ab §31 und der Orientierungssuche —, und er
  hält dort denselben GIL. Das war ein offener Punkt der Ansicht, kein
  Freibrief — geschlossen mit dem Hilfsprozess (RM-212): Die Anzeige ab §31
  dezimiert dort, und am Spielbrett nach *Kanten verfeinern* (4,1 Mio.
  Dreiecke) stand das Fenster beim ganzen Übernehmen höchstens 128 ms.

Die Wandprüfung der Formsitzung ist der zweite Fall derselben Woche: Sie lief
im Hauptthread mit Wartezeiger, der Kommentar rechnete mit 273 ms, gemessen
waren es an echten Modellen 2,7 bis 5,5 s nach jedem Zug. Im Arbeiter
(`_SculptWallWorker`) ist die größte Lücke im Hauptthread 143 ms am
Besenhalter — `shapely` und `numpy` geben den GIL überwiegend her. Eine
Prüfung, die nach jeder Geste neu anläuft, bekommt einen Abbruchschalter:
Die Wandkarte nimmt seither `cancelled` (`maps.wall_thickness_map`).

### Ein Blick auf eine Datei ist eine Netzfrage

„Zuletzt geöffnet" fragte beim Fensteraufbau jede gemerkte Datei nach ihrer
Existenz, im Hauptthread. Auf der eigenen Platte kostet das Mikrosekunden;
liegt ein Projekt auf einem ausgeschalteten NAS, antwortet Windows erst nach
seinem Zeitlimit — gemessen 21 s an einer nicht erreichbaren Adresse, 2,7 s
an einem unbekannten Rechnernamen. So lange startete das Fenster nicht.

`MainWindow._show_recent` fragt deshalb in einem **Daemon-Thread** und nicht
an der Leine: Ein `stat` lässt sich nicht abbrechen, und ein `QThread`, der
beim Beenden noch darin hängt, reißt den Prozess mit (0xC0000409). Er wartet
50 ms — lokal der Normalfall, ohne Zwischenbild — und zeigt sonst die
ungeprüfte Liste, die sich ausdünnt, sobald die Antwort da ist. Wer eine
gemerkte Pfadliste prüft, prüft sie so.

Auch die ComfyUI-Ordnerprüfung läuft außerhalb von Qt: `find_comfyui` und die
Modellbestände können auf einem nicht erreichbaren Netzlaufwerk in einem
Dateizugriff hängen. Höchstens zwei Daemon-Fäden prüfen systemweit; je Dialog
bleibt nur der neueste noch nicht gestartete Pfad vorgemerkt. Jede Antwort
trägt die Eingabegeneration und darf nach Pfadwechsel oder Schließen den
Dialogzustand nicht ändern. Dauert eine Prüfung fünf Sekunden, bleibt
*Einrichten* gesperrt und erklärt, dass ein anderer erreichbarer Ordner gewählt
oder die Antwort abgewartet werden muss. Eine verspätete erfolgreiche Antwort
darf freigeben; eine Fehler- oder Crashantwort derselben Generation nicht. Erst
ein neuer Prüfversuch darf einen fehlgeschlagenen Timeout ablösen. So wird der
potenziell blockierende Aufruf nach einem Timeout nicht direkt im Setup-
`QThread` wiederholt.

### Ein Zeiger, der fragt, wird gedrosselt, nicht entprellt

Die Platzierung fragt bei jeder Mausbewegung, welche Fläche unter dem Zeiger
liegt — die Antwort rechnet ein Arbeiter. **Gedrosselt** heißt: höchstens alle
16 ms eine Frage, eine zur Zeit, und ihr Ende nimmt sofort die jüngste
Stelle. Bis zum 22.09.2026 startete jede Bewegung den Zeitgeber neu
(**entprellt**): Bei einer Maus mit 125 Hz kam die Frage erst, wenn der Zeiger
ruhte, und die Stelle stand 5,5 s nach der letzten Bewegung. Danach folgt sie
dem Zeiger (27 Fragen während eines Strichs) und steht 64 ms nach seinem Ende.

Zwei Sätze, die dazugehören:

* **Eine überholte Antwort ist nicht wertlos.** Ihre Stelle gilt nicht mehr,
  die vorbereitete Fläche schon (`PlacementFlow._surface_known`); die nächste
  Frage auf derselben Fläche rechnet nur noch `at_point`.
* **Ein Arbeiter bekommt eine Kopie je Netz, nicht je Frage**
  (`_surface_mesh`). Eine frische Kopie hat leere Merker, und jede Frage baute
  Nachbarschaft und Normalen des ganzen Netzes neu. Die Fragen laufen
  nacheinander (`_surface_busy`), die Kopie teilt also niemand.

* **Und nicht je Fluss** (RM-232, 25.09.2026). Jeder Merkmalklick baut einen
  neuen Platzierungsfluss; `for_a_worker` behält die Kopie deshalb je
  Szenennetz (die letzten `WORKER_COPIES_KEPT`, sie stirbt mit ihrem Netz),
  und `placement.prepare_surface` merkt seine Antwort am Netz. Weil jetzt der
  Arbeiter eines abgelösten Flusses noch an derselben Kopie rechnen kann,
  läuft jede Rechnung an ihr unter ihrem Schloss (`on_the_copy`). Gemessen an
  der dichten Platte (204 000 Dreiecke), Bohrung zu Bohrung am echten
  Fenster: 522 → 352 ms bis zur Fläche.
* **Und mit den Merkern des Originals** (RM-232, 25.09.2026). Eine Kopie ohne
  Cache rechnete Nachbarschaft, Kanten und Normalen neu, die das Original seit
  der Erkennung hat; `copy(include_cache=True)` übernimmt sie flach, und die
  Felder darin sind schreibgeschützt. Die Kernauskünfte einer Bohrung an der
  dichten Platte kosteten an der leeren Kopie 529 ms, an der mitgenommenen
  264 — die Kopie selbst beide Male 3 ms.
* **Und mit den Antworten der Erkennung** (Durchsicht 0.5.1). Eine Kopie für
  einen Nebenfaden entsteht mit `features.copy_with_answers`, nie mit
  `raw.copy(include_cache=True)` allein: Die Merker der Erkennung galten je
  Körperobjekt, und die frische Kopie passte jeden Flächenfit neu ein — die
  Hohlraumfläche einer Bohrung am Laptop-Ständer 1,1 s statt 0,07 s. Geteilt
  werden nur Antworten aus `SHARED_ANSWERS` (Zahlen, Felder, Mengen);
  Netze, Suchbäume und vorbereitete Flächen (`BODY_BOUND_ANSWERS`) baut jede
  Kopie für sich, sie gehen nie über Fäden. Eine Kopie, die umgebaut wird
  (`repair`), nimmt `copy()` und erbt nichts.
* **Ein kleiner Körper wartet nicht auf den Arbeiter** (RM-232, Durchsicht
  0.5.1). Unter `placement_flow.AT_ONCE_BELOW` Dreiecken entstehen beim Start
  eines Flusses die Fläche am Merkmal und das Werkzeug gleich im Hauptfaden,
  am Original: Am Wabenhalter rechnete der Arbeiter beides in 5 ms, und die
  Antwort wartete danach 16 ms hinter dem Malen des halb umgebauten Fensters.
  Getippte Werte und große Körper bleiben beim Arbeiter — dort wartet ein
  früher Klick auf *Übernehmen* auf das Werkzeug.
* **An der Anwendung hängt ein Filter, nicht einer je Anliegen**
  (`app_events`, Durchsicht 0.5.1). Ein Bohrungsklick schickt rund 2 400
  Ereignisse durch die Anwendung, und jeder eigene Python-Filter an ihr kostet
  je Ereignis einen Aufruf: drei davon 17 ms je Klick. Wer an der Anwendung
  zuhören muss, meldet sich mit seinen Ereignisarten bei
  `app_events.listen` an und mit `app_events.forget` ab;
  `test_app_events` hält das am Quelltext fest.
* **Was das Merkmalfenster den Kern fragt, fragt an einem großen Körper der
  Arbeiter** (RM-232). Ab `ANSWERS_IN_WORKER_FROM` Dreiecken laufen
  Hohlraumkette, Handlungen und Gleichartige in `_FeatureAnswersWorker` an
  der Arbeiterkopie; darunter kosten sie unter 50 ms, und ein Wartezustand
  flackerte nur. Bis zur Antwort steht, was feststeht (Name, Maß, ein Satz),
  und nichts, das etwas anböte. Die Antwort gilt ihrem Merkmal und ihrer
  Auswertung — auch die eines abgelösten Arbeiters wird gemerkt, gebaut wird
  nur, was noch gewählt ist; ein Absturz ist ein Fehlerbericht und kein
  ewiges Warten. Erster Bohrungsklick an der Platte: 172 → 36 ms im
  Hauptfaden, längste Lücke 171 → 52 ms.

Und die Vorbereitung selbst zählt, statt zu verschneiden:
`placement._patch_area` baut die Fläche aus ihrem Rand (Kanten mit einem
Besitzer, gezählt nach Ort, `shapely.build_area`) und prüft das Ergebnis,
bevor sie es glaubt; nur was die Prüfung ablehnt, geht durch `union_all`.
`_welded_adjacency` liefert Paare statt eines Wörterbuchs, `_patch_faces` die
Zusammenhangskomponente (`scipy.sparse.csgraph`). An der Lochplatte mit
815 104 Dreiecken kamen Griff und Maße nach dem Klick auf eine Bohrung vorher
nach 9 bis 21 s, danach nach 1 bis 2,4 s; am Korpus sind alle 339 ebenen
Stücke und 999 Flächenwahlen dieselben wie vorher.
