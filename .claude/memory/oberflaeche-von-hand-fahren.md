---
name: oberflaeche-von-hand-fahren
description: "Wie sich Formwerks Oberfläche wie von Hand durchfahren lässt — echte Qt-Plattform, Dialoge abfangen, sauber schließen."
metadata: 
  node_type: memory
  type: project
  originSessionId: 8b7034aa-9307-4ece-9f76-a32866e1465e
  modified: 2026-08-15T14:08:56.487Z
---

Die Oberfläche lässt sich ohne Menschen bedienen, aber nur mit drei
Vorkehrungen. Ohne sie hängt der Lauf oder fotografiert leere Kästchen.

- **Echte Qt-Plattform, kein offscreen.** `QT_QPA_PLATFORM=offscreen` hat auf
  dieser Maschine null Schriftfamilien; jede Beschriftung wird ein leeres
  Kästchen. `WA_DontShowOnScreen` hält das Fenster trotzdem vom Bildschirm.
  Der Viewport rendert dann allerdings **nicht** — OpenGL zeichnet nichts in
  ein Fenster, das nie sichtbar war (siehe `tools/make_figures.py`).
- **Modale Dialoge abfangen.** Ohne das wartet der Lauf ewig. Betroffen sind
  `_may_discard` beim Öffnen (drei Knöpfe — ohne geklickten Knopf liest
  `confirm_unsaved` „Abbrechen", und das Öffnen findet nie statt), die
  Wiederherstellungsfrage und `closeEvent`. Operationsdialoge laufen dagegen
  **nicht** über `exec()`, sondern nicht-modal: sie hängen an
  `window._op_dialog`. Bestätigt wird **über den Knopf**, nicht über
  `accept()` — siehe unten.
- **Screenshot vor dem Bestätigen.** Ein Operationsdialog trägt
  `WA_DeleteOnClose`; nach `accept()` ist sein C++-Objekt fort.

Kein `evaluate_now()` in einen laufenden asynchronen Lauf hineinrufen — das
erzeugt einen hängenden Zustand, der wie ein Fehler der Anwendung aussieht und
keiner ist. Stattdessen auf `session.busy` und `session.split_running` warten
(beides Eigenschaften, keine Methoden).

Zum Aufräumen nie pauschal `taskkill /IM python.exe` — das trifft auch
ComfyUI und andere fremde Prozesse. Gezielt über die PID.

Drei Dinge, die beim Audit vom 08.08.2026 Zeit gekostet haben:

- **`showMaximized()`, nicht `resize()` — und kein echtes Vollbild.**
  Fenstermodus, aber den ganzen Bildschirm füllend: `setGeometry` auf
  `primaryScreen().availableGeometry()`, dann `showMaximized()`. Robert hat
  das am 20.08.2026 ausdrücklich verlangt, für **jede** Aufnahme: ein auf
  1200 px zusammengepresstes Fenster zeigt nicht das Layout, sondern die
  Enge — die Werkzeugleiste bricht um, die Kopfzeile fällt weg, und beurteilt
  wird am Ende die falsche Sache.
- **Ein `QMenu.exec()` blockiert wie ein modaler Dialog, ist aber keiner.**
  `activeModalWidget()` findet es nicht — der Wachhund braucht zusätzlich
  `activePopupWidget()`. Sonst hängt der Lauf am ersten Rechtsklick.
- **Ausgabe nie durch `| tail` leiten**, sondern in eine Datei umlenken.
  `tail` sammelt bis zum Prozessende; bei einem Lauf, der hängt, sieht man
  gar nichts.

Fünf Griffe, die den Einstieg kosten (09.08.2026 wieder gebraucht):

- **`build_application([])` aus `app.ui.app`**, nicht `MainWindow()` — das
  Fenster verlangt `session` und `settings`. Vorher `load_operations()`,
  danach `window.start()` (zeigt den Erststart-Dialog, den der Wachhund
  wegräumt).
- **`PYTHONIOENCODING=utf-8`**, sonst stirbt der Lauf am ersten `→` im
  Menüort — cp1252 auf der Konsole.
- **`APPDATA`/`LOCALAPPDATA` auf einen Temp-Ordner umbiegen**, wie
  `tests/conftest.py` es tut: der Lauf hinterlässt sonst Projekte und
  Kalibrierungen in Roberts Profil.
- **„Weitere Einstellungen" ist ein `QToolButton`** (`dialog.advanced`), kein
  `QGroupBox` — `findChildren(QGroupBox)` findet nichts, und ohne Klick sind
  alle hinteren Felder `isVisibleTo() == False`.
- **Sichtbarkeit prüfen, nicht `dialog.values()`**: das gibt jedes Feld des
  Schemas zurück, auch ein weggeblendetes. Ein Fehlbefund kam genau daher.
  Die Zeichnung des Skizzenmodus holt `panel.sketch_text()`.

Geklickt wird über den VTK-Interactor: `SetEventPosition(x, y)` und
`InvokeEvent("LeftButtonPressEvent")` / `…ReleaseEvent`. Vor dem Urteil „Klick
kommt nicht an" mit `viewport._world_at(x, y)` prüfen, ob dort überhaupt
Körper liegt — ein Fehlbefund zum Messen kam genau daher.

**Stirbt oder hängt ein Lauf, zuerst gegen `HEAD` gegenmessen — im
`git worktree`, nicht per Stash.** Am 15.08.2026 blieb der
Druckeinstellungs-Dialog minutenlang stehen, mitten in einem eigenen
Änderungssatz; die Frage „meiner oder älter?" beantwortete
`git worktree add <temp> HEAD` und derselbe Ablauf mit
`sys.path.insert(0, <temp>)`. Beide Stände starben identisch, damit war der
eigene Satz aus dem Verdacht. Stash und Reset scheiden hier aus (parallele
Sitzungen, siehe unten), der Worktree kostet nichts und lässt den Arbeitsbaum
in Ruhe. Hinterher `git worktree remove --force`.

Dabei zwei Wegweiser, die Zeit sparen:

- **`faulthandler` schweigt bei einem *Hänger*.** Kein Traceback heißt nicht
  „nativer Absturz" — erst in der Prozessliste nachsehen: steigt die CPU-Zeit,
  rechnet er und hängt nicht an einem Deadlock. Danach halbieren: die
  verdächtige Funktion von Hand Schritt für Schritt nachbauen, mit Ausgabe
  zwischen jeder Zeile. Die letzte Zeile vor der Stille ist die Stelle.
- **PowerShell-Pipes puffern.** `… | Select-String` und `| Out-File` geben
  nichts heraus, solange der Prozess läuft — bei einem Hänger sieht man gar
  nichts und hält ihn für einen sofortigen Tod. Das Prüfskript schreibt
  deshalb **selbst** in eine Datei (`open(..., buffering=1)`, eigenes `print`),
  und der Aufruf leitet nach `$null`.

Am 20.08.2026 zwei Fallen, die beide wie ein Absturz aussehen und keiner sind:

- **Genau ein Wachhund — und er darf sich nicht selbst überholen.** Zwei
  gleichzeitig laufende Timer nehmen einander die Dialoge weg (unten); die
  zweite Gestalt ist ein **einzelner** Timer, dessen Bedienroutine selbst
  `processEvents()` ruft. Dann feuert er mitten in seine eigene Arbeit hinein,
  findet denselben Dialog noch offen und bedient ihn ein zweites Mal — die
  innere Instanz misst einen Zustand, den die äußere gerade herstellt.
  Gemessen am 30.08.2026: „Nach 8 s läuft der Wurf: **False**" über einem
  Zustandssatz „Modell wird erzeugt (5 s)", und der Balken angeblich
  unsichtbar. Mit einem Riegel (`schon_bedient`) stand dieselbe Messung auf
  True/True. Wer eine Bedienroutine an einen Timer hängt, riegelt sie zu.
- **Zwei Timer.** Zwei gleichzeitig laufende Timer nehmen einander die
  Dialoge weg: Was der eine wegklickt, hat der andere nie gesehen, und ein
  Dialog, der nur vom falschen beantwortet wird, bekommt die falsche Antwort.
  Die Messung wird davon nicht falsch, sondern **zufällig** — dreimal derselbe
  Ablauf gab dreimal ein anderes Ergebnis, bis der zweite Hund weg war. Wer
  einen eigenen braucht, gibt ihn dem Gerüst mit, statt einen zweiten zu
  starten.
- **`QMenu.exec` lässt sich nicht wegpatchen.** Ein Test, der die Methode auf
  der Klasse ersetzt, um das Menü einzusammeln, hängt trotzdem — PySide6 ruft
  intern nicht die Python-Bindung. Die Lösung ist keine Attrappe, sondern eine
  Trennung im Code: Menü **bauen** in eine eigene Methode
  (`SketchCanvas.context_menu_at`), Zeigen bleibt beim Ereignis. Dasselbe
  Muster wie bei `place` — was ein Klick tut, entscheidet die Methode, die
  auch ein Test ruft.
- **Ein echtes `QContextMenuEvent` hat kein `position()`.** Wer eines baut, um
  ein Kontextmenü zu prüfen, prüft den Typfehler statt das Menü; eine Attrappe
  mit `position()` und `globalPosition()` reicht und ist ehrlicher.


**Ein Prüfstand, der den echten Startweg abkürzt, misst sich selbst.** Am
25.08.2026 zwei Fehlalarme an einem Nachmittag, beide aus dieser Wurzel, und
beide sahen aus wie Fehler der Anwendung:

- **Den Knopf klicken, nicht `accept()` rufen.** Der Bausteinweg schien tot:
  Modell geladen, Objekt gewählt, Katalog, Dialog steht sauber da, bestätigt —
  und im Stapel stand danach nur `load`. Mit
  `box.button(QDialogButtonBox.StandardButton.Ok).click()` statt
  `widget.accept()` setzt dieselbe Operation zweimal hintereinander sauber.
  Der Grund ist **nicht isoliert**: `run_operation` hängt an
  `dialog.finished`, und `accept()` löst das aus; der Aufbau hatte eine
  verschachtelte Wartezeit im Timer-Callback. Was bleibt, ist die praktische
  Regel — der Klick geht, und er ist ohnehin der Weg, den ein Kunde nimmt.
- **`install_qt_translations(app, "de")` gehört in jeden Prüfstand.** Ohne sie
  steht auf jedem zweiten Dialog „Cancel" statt „Abbrechen" — Qt beschriftet
  seine Standardknöpfe aus dem eigenen Katalog. Auf einem Bildschirmfoto sieht
  das aus wie ein Regel-20-Verstoß und ist keiner: `app/ui/app.py` lädt den
  Katalog beim echten Start, `qtbase_de.qm` liegt in der `.venv`, und
  `packaging/solidon3d.spec:93` nimmt ihn ins Paket mit. Wer `QApplication([])`
  von Hand baut, überspringt genau diesen Schritt.

Beide Male war die Anwendung in Ordnung und der Prüfstand nicht. Die Probe
darauf ist billig: **Fällt der Befund, sobald der Prüfstand einen Schritt des
echten Starts nachholt, war es der Prüfstand.** Siehe
[[messwerkzeug-misst-sich-selbst]].

**Und die dritte dieser Art, am 30.08.2026: eine Warteschleife, die nicht
wartet.** `QTimer.singleShot(50, …)` **blockiert nicht** — es reiht einen
Zeitgeber ein und kehrt sofort zurück. Eine Schleife, die daneben `0,05`
addiert und `processEvents()` ruft, zählt bis 300 und wartet dabei
Millisekunden. Gemessen: zweimal „KEIN ERGEBNIS" nach einem Erzeugungslauf,
angeblich nach 300 Sekunden Geduld; mit `session.wait_for_idle()` — dem Weg,
den die Anwendung selbst nimmt — stand das Ergebnis nach 15,3 Sekunden.

Erkennbar ist es an der Gesamtlaufzeit: Wer 300 Sekunden zu warten glaubt und
nach zwölf fertig ist, hat nicht gewartet. Wer eine eigene Schleife baut, misst
mit `time.monotonic()` und nicht mit einem Zähler.

**`setCurrentIndex` ist keine Nutzergeste.** Eine QComboBox, die über
`activated` verbunden ist, reagiert auf `setCurrentIndex` gar nicht — das
Signal feuert nur bei einer echten Wahl. Am 30.08.2026 „wechselte" ein
Prüfstand so dreimal den Slicer und maß dreimal denselben: Die Anzeige stand
auf dem neuen Eintrag, die Auswahl-Logik lief nie, und nur die unveränderten
Profillisten daneben verrieten es. Wer programmatisch wählt, sendet
zusätzlich `combo.activated.emit(index)` — oder prüft vorher, an welchem
Signal die Combo hängt.

**Ein Prüfstand mit echtem Fenster endet hart, oder er wird zur unschließbaren
Anwendung.** Nach `QApplication.quit()` kehrt jedes spätere modale `exec()`
sofort und knopflos zurück: `clickedButton()` gibt `None`, `confirm_unsaved`
liest daraus „Abbrechen", `closeEvent` ruft `event.ignore()` — und das Fenster
lässt sich nicht mehr schließen, auch von Hand nicht. Am 30.08.2026 standen
so vier Prüfstands-Fenster mit dem Titel der Anwendung herum, und Robert
hielt sie für hängende Solidons. Zweierlei dagegen, beides billig: dem
Fenster einen Prüfstands-Titel geben (`setWindowTitle("PRÜFSTAND …")`), und
nach dem Protokollschreiben `os._exit(0)` — ein Prüfstand hat nichts zu
retten.

Siehe auch [[parallele-sitzungen-solidon3d]] und
[[native-bibliotheken-speicher]].
