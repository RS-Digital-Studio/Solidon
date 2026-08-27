# Gebietsbericht: Oberfläche — Fenster, Sitzung, Start

Gebiet: `main_window.py`, `session.py`, `app.py`, `start_screen.py`, `first_run.py`, `tour.py`, `command_palette.py`, `analysis_bar.py`, `tool_strip.py`, `overlay.py`, `loading.py`, `leash.py`. Offscreen gemessen, Skripte unter `review-ui1\`.

## Hoch

### 1 [hoch] Geändertes Projekt geht beim Einfügen vom Startbildschirm ohne Frage verloren — VERIFIZIERT
`main_window.py:2930-2933` (`open_path`), `:3016-3023` (`action_import`), `:3108-3111` (`_downloaded`) — `open_path` fragt `_may_discard()` nur für `.p3d`. Für ein Modell ruft der Startbildschirm-Weg `session.start_new(...)` → ersetzt Dokument + History, Undo holt nichts zurück. Weg: *Datei → Neu* zeigt nur den Startbildschirm (verwirft bewusst nichts), das Projekt bleibt offen; STL ziehen/Einfügen verliert die Arbeit stumm. Gemessen: `action_new()` dann `open_path(stl)` → keine Frage, `ops` = `['load']`. **Fix:** vor `start_new` überall `if not self._may_discard(): return`, in einer Hilfsmethode.

### 2 [hoch] Sprachwechsel fragt nach ungesicherten Änderungen und missachtet „Abbrechen" — VERIFIZIERT
`app.py:216-224` (`rebuild_for_language`), `main_window.py:7980-7986` (`closeEvent`) — `rebuild_for_language` ruft `window.close()`; `closeEvent` fragt `_may_discard()`, obwohl beim Sprachwechsel nichts verworfen wird (Sitzung wandert mit). Folgen: *Verwerfen* löscht Autosave, *Speichern* öffnet Dateidialog, *Abbrechen* wird ignoriert (Rückgabewert nicht gelesen, `deleteLater()` läuft trotzdem) — dann entfällt auch `wait_for_workers()`, ein Arbeiter überlebt sein Fenster und greift ins zerstörte C++-Objekt. Gemessen: `['Caja (sin guardar)']`, 2 Fenster, geteilte Sitzung. **Fix:** Merker `_closing_for_rebuild`, den `closeEvent` vor `_may_discard` prüft; oder `release()+hide()+deleteLater()` statt `close()`.

### 3 [hoch] `_exporting` wird nie gesetzt: Balken verschwindet, während der Export noch schreibt — VERIFIZIERT
`main_window.py:827`, `:3147`, fehlend in `_start_export` (`:3695-3711`), `_export_done`/`_export_failed` — die Flagge existiert nur als `False`-Zuweisung und Abfrage in `_anything_running()`. Ihr Docstring beschreibt genau den Fehler, den sie verhindern soll (Balken weg, während die Datei noch geschrieben wird → Kunde schließt das Fenster). `_downloading` daneben wird korrekt gesetzt. Gemessen: `_anything_running()` bei laufendem Export = False. **Fix:** `_exporting=True` in `_start_export`, `False` in `_export_done`/`_export_failed`; oder `_anything_running` auf `_export_worker is not None`. Test bei gleichzeitiger Auswertung + Export.

## Mittel

### 4 [mittel] Befehlspalette führt gesperrte Fensterbefehle aus — Zwilling zum behobenen Fall — VERIFIZIERT
`main_window.py:4181-4183` gegen `:5186-5200` — `_run_palette_choice` fängt seit `cc40aaa4` gesperrte Einträge ab; eine Zeile darüber (Fensterbefehle) fehlt die Prüfung: `commands[name][2]()` ohne `_extra_availability`. *Automatisch teilen* endet in der modalen Sackgasse. Menübefehle (`action.trigger`) sind sicher. **Fix:** vor dem Aufruf `_extra_availability(name)`, bei `not available` `announce` + zurück.

### 5 [mittel] Nachzügler eines Agentenzugs löscht das Feld seines Nachfolgers und meldet Ruhe — VERIFIZIERT
`session.py:1290`, `:1494-1498` — `_on_thread_done`/`_on_split_done` haben einen Absender (`finished=`), `_on_agent_done` nicht. Kommt das `finished` eines beendeten Zuges nach dem Start eines neuen, meldet der Nachzügler `agentBusyChanged(False)` und leert `self._agent` → `wait_for_idle` sieht den laufenden Thread nicht. **Fix:** `partial(self._on_agent_done, finished=worker)` + Wache `finished is self._agent`.

### 6 [mittel] Zwilling im Erstinbetriebnahme-Dialog: `wait_for_survey()` lügt — VERIFIZIERT
`first_run.py:277`, `:350-354` — `_survey_done` kennt seinen Absender nicht, leert `self._survey` bedingungslos; danach gibt `wait_for_survey()` True, obwohl eine Erhebung läuft → Thread überlebt den Dialog. **Fix:** Absenderprüfung wie oben.

### 7 [mittel] Automatische Sicherung friert das Fenster 1,3 s ein, ohne ein Zeichen — VERIFIZIERT
`main_window.py:990-993`, `session.py:522-525` — `_autosave.timeout.connect(self.session.autosave)` schreibt alle zwei Minuten das ganze Projekt im Hauptthread; `_save_to` begründet für denselben Vorgang Wartezeiger + Statuszeile, der Autosave hat beides nicht. Gemessen (65,5 MB Quelle): 1328 ms. **Fix:** `waiting()` + Statuszeile, besser in einen `leash.Worker` (liest nur).

### 8 [mittel] Verschwundene Modelldatei bricht den Slot ab, statt etwas zu sagen — VERIFIZIERT
`main_window.py:2920-2942`, `session.py:824-827` — `import_model` ruft `path.read_bytes()`, `OSError` läuft ungefangen in Qts Verteiler: kein Dialog, „der Doppelklick tut nichts". `action_check_gcode` behandelt genau das schon. Gemessen: `open_path` mit fehlender `.stl` → `FileNotFoundError` bis oben. **Fix:** `except OSError`-Block + `UserError` (Regel 17); alternativ Lesen als `FileReadError` in `import_model` (deckt Fenster/CLI/Fernaufruf).

### 9 [mittel] *Hilfe → Erste Schritte* verspricht sofortigen Sprachwechsel und meldet ihn nicht — VERIFIZIERT
`main_window.py:7347-7363`, `first_run.py:191` — Text seit `d8e0ca8a` „stellt sich gleich darauf um", eingelöst nur im Erststart-Pfad. `action_first_run` schreibt `settings.language`, emittiert kein `languageChanged`. Gemessen: de→es, `languageChanged` = 0. **Fix:** wie `action_settings` vergleichen und `languageChanged.emit()`.

### 10 [mittel] Nach Ablauf des Testzeitraums bleibt die Werkzeugzeile bedienbar — zwei ihrer acht schreiben — VERIFIZIERT
`main_window.py:2390-2393` — `tools.set_usable` bekommt nur `objects>0 and not gesturing`, nicht `locked`. *Trennen* und *Bemalen* schreiben; Klick landet in der Absage nach der Handlung statt vorher (§2.6). Gemessen (gesperrt): alle acht Umschalter True. **Fix:** `not locked` mit Sperrgrund, oder die zwei schreibenden einzeln.

### 11 [mittel] Zwei Referenzringe an eigenen Kindern — die vorhandene Prüfung sieht sie nicht — VERIFIZIERT
`tool_strip.py:201`, `overlay.py:579-585` — `ToolStrip.add` verbindet Lambda mit `self.toggle`; `OverlayHost._move` hängt drei Lambdas an eine `QPropertyAnimation` mit Elternteil `self`. Gemessen (A/B): leer 0/10 überleben, nach `add(...)` bzw. animierter Bewegung 10/10. `test_widget_lifetime.py:148,173` baut beide **leer**. **Fix:** `weak_slot` mit benannten Methoden, Animation `DeleteWhenStopped`; Tests gefüllt bauen.

### 12 [mittel] *Datei → Neu* ist eine Einbahnstraße, „Zuletzt geöffnet" hinkt hinterher — VERIFIZIERT
`main_window.py:2835-2847`, `:995`, `:2998-2999` — `action_new` zeigt den Startbildschirm, lässt das Projekt offen, kein Eintrag führt zurück. `show_recent` wird nur beim Aufbau/Vergessen gerufen, nicht nach `_save_to`/`open_path`. Gemessen: nach `_save_to` steht der Pfad in `settings.recent`, der Startbildschirm zeigt `[]`. **Fix:** `show_recent` nachziehen; Eintrag *Zurück zum Projekt*, solange `document.ops` nicht leer.

## Gering
- **13** macOS-Dateiöffner zeigt nach Sprachwechsel auf ein gelöschtes Fenster (`app.py:111-130`, `:245-249`) — `FileOpenListener` behält das entsorgte Fenster. PLAUSIBEL (nur macOS). Fix: Listener am Halter führen.
- **14** Beim Schließen wird die Live-Vorschau nicht abgebrochen (`session.py:1229-1242`, `main_window.py:7923-7924`) — Vorschau-Token erreicht nur `cancel_previews()`, nicht `cancel()`. Fix: `cancel()` um `cancel_previews()` ergänzen.
- **15** Update-Abfrage beim zweiten Start nicht zurückgestellt (`main_window.py:7403-7415`, `:7426-7429`) — `_update_worker` ohne `_retire`, `_update_worker_done` ohne Absender. Kein Absturz (`leash._alive`), Buchführung falsch.
- **16** Docstrings hängen am falschen Feld (`tour.py:89-96`, `main_window.py` sieben Stellen) — Zeichenketten dem Nachbarsignal/-feld zugeordnet. Zuordnen.

## Geprüft und in Ordnung
Oberflächengrenzen §19 (9 Menüs, ≤12 Zeilen, 8 Umschalter; das 13-Zeilen-Flächenmenü ist Kontextmenü, nicht hier); Kürzel keine Doppelbelegung; Signal-Slot-Stelligkeit (AST über 141 connect, eine gewollte Auffälligkeit); Arbeit im Hauptthread (`_update_actions` 0,5 ms usw. — kein §2.8-Kandidat); alle Langläufer in `leash.Worker` mit `crashed`; Kerntrennung (kein Qt unter ui/, keine Geometrieänderung außerhalb einer Op); Regel 19 (drei Rückfragen begründet); Regel 20 (keine feste Zeichenkette).

**Kann das so rein: nein** — die drei hohen Funde (stiller Datenverlust beim Einfügen, Sprachwechsel über close(), tote `_exporting`-Flagge) zusammen unter dreißig Zeilen.
