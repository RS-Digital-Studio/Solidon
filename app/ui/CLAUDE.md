# `app/ui/` — die Oberfläche

PySide6. Darf `app.core` benutzen, die Gegenrichtung ist verboten (§8). Die
Oberfläche rechnet keine Geometrie und ändert keine — **sie ruft Ops auf.**

Die Regeln dieses Gebiets stehen in `.claude/rules/` und laden sich selbst —
**vier Dateien, je nachdem, was man anfasst:**

| Regeldatei | Lädt bei |
|---|---|
| `oberflaeche.md` | jeder Datei hier — Texte, Zahlen, Grenzen, Barrierefreiheit |
| `ansicht.md` | `viewport.py`, `overlay.py`, `cursors.py` und den Leisten |
| `wartezeit.md` | `session.py`, `loading.py`, `leash.py`, `splash.py`, `main_window.py` |
| `zeichenflaeche.md` | `sketch_editor.py` |

Hier steht die Karte, dort das Gesetz.

## Der Weg durch die Schicht

```
main_window.py   Menüs, Auswahl, Zustand
      │  ruft eine Operation auf
      ▼
session.py       die Brücke zum Kern: Stapel, Auswertung, Threads
      │  wertet aus (im Arbeiter-Thread)
      ▼
app.core         rechnet
      │  EvaluationResult
      ▼
viewport.py      zeigt an
```

`session.py` ist die einzige Stelle, an der die Oberfläche den Kern anfasst.
Wer an ihr vorbei rechnet, bricht Regel 2.

## Die fünf Dinge, die an `session.py` überraschen

Ende zu Ende gemessen am 27.08.2026 — vier Anläufe gingen daran verloren,
bevor es jemand wusste:

- **`session.last_result` ist die ausgewertete Szene.** Ein
  `session.scene` gibt es nicht.
- **`evaluate_now()` ist der synchrone Weg** — für Kommandozeile, Tests und
  Export. Er gibt das Ergebnis zurück, statt es nur anzustoßen.
- **`session.apply()` endet mit `evaluate_async()`.** Nach dem Aufruf steht
  das Ergebnis noch **nicht**. Und es wirft nicht: Fehler kommen über das
  Signal `failed`. Ein `try` um den Aufruf läuft ins Leere — nach dem
  Ergebnis fragen, nicht nach dem Grund.
- **`Scene.objects` ist ein Wörterbuch.** Darüber zu iterieren gibt die
  Kennungen. Die Folgemeldung `'str' object has no attribute 'mesh'` sieht
  aus wie ein leerer Import und ist keiner.

- **Das Fenster liest über `import_model_async`, nicht über `import_model`.**
  Der synchrone Weg steht daneben und bleibt — Kommandozeile und Tests
  brauchen einen, der wirft. Das Fenster braucht einen, der meldet: Bei einer
  3MF zählt `import_plan` die ganze Baugruppe, bevor eine Operation entsteht,
  und das dauert bei 63 MB vierzehn Sekunden. Oberhalb von
  `PLAN_IN_WORKER_ABOVE` läuft das im Arbeiter, der Fehler kommt über
  `importFailed`. Wer in einem Test `session.import_model` patcht, patcht
  damit einen Weg, den das Fenster nicht mehr geht — fünf Tests in
  `test_ui.py` hingen daran (03.09.2026).

## Die Karte

**Rahmen und Einstieg**

`app.py` (Einstiegspunkt, §38) · `qt_platform.py` (welche Qt-Plattform die
3D-Ansicht braucht — entschieden vor der `QGuiApplication`, ohne Qt-Import;
Qt 6 nähme in einer Wayland-Sitzung sonst Wayland, und dort hat VTK kein
Fenster) · `main_window.py` (**rund 8 900 Zeilen** — das
Hauptfenster, §2.5) · `splash.py` · `first_run.py` (der erste Start) ·
`start_screen.py` (die ersten fünf Minuten, §2.3) · `header.py`

**Brücke zum Kern**

`session.py` (§7, §15.6) · `leash.py` (die Halteleine für Arbeiter-Threads — und für Ereignisfilter,
die ihr überwachtes Objekt überleben: `stop_watching_the_dying`)

**Ansicht**

`viewport.py` (**rund 8 200 Zeilen** — §18, §2.9) · `render/` (die Renderer
hinter der Ansicht, eigene `CLAUDE.md`: der Vertrag `api.py`, VTK direkt,
Kameraführung, Formen, Bewegungsgriff) · `overlay.py` (Zonen über der
Ansicht statt neben ihr) · `loading.py` (Ladeanzeige, §2.8) · `cursors.py` ·
`spacemouse.py` (die 3D-Maus als zweite Hand an derselben Kamera: HID-Leser
über hidapi, auf dem Mac der Treiberweg über das 3Dconnexion-Framework des
Kunden, die Abbildung als reine Funktion — Regel in `ansicht.md`).
**`camera_step` hat drei Aufrufer, nicht einen:** die Kappe, das Kippen mit
dem gedrückten Rad und die Flugtasten. Wer dort an einer Achse dreht, dreht
an allen dreien

**Panels und Leisten**

`panels.py` (die drei Panels links, Prüfbericht rechts, §2.5) ·
`tool_strip.py` · `analysis_bar.py` · `section_bar.py` · `split_bar.py` ·
`transform_bar.py` · `explode_bar.py` · `sculpt_bar.py` · `pose_bar.py` ·
`scale_widget.py` · `facts.py` (was das Teil kostet, während man daran baut)

**Dialoge**

| Datei | Besonderheit |
|---|---|
| `op_dialog.py` | **Wird aus dem Parameterschema erzeugt** (§10, §2.4). Kein Dialog wird von Hand gebaut — wer einen tippt, hat das Register umgangen |
| `dialogs.py` | Fragen und Fehler (§2.7), Freischaltung mit Online- und Dateiweg sowie freiwillige Förderung |
| `print_settings_dialog.py` | Druckeinstellungen und Slicer-Übergabe (§29) |
| `print_disclosure.py` | Der Hinweis davor: dass diese Werte Erfahrungswerte sind und mit einer 3MF mitreisen — und die Wahl, ob sie das sollen (§29) |
| weitere | `settings_dialog` · `generate_dialog` (Weg 3) · `recipe_dialog` · `variants_dialog` · `comfy_dialog` · `install_dialog` · `support_dialog` · `update_dialog` · `changes_dialog` |

**Editor**

`sketch_editor.py` (**rund 4 800 Zeilen** — §30.1, Stufe zwei)

**Agent**

`chat.py` (§26.3, §2.5) · `snapshots.py` (Ansichten für den Agenten) ·
`remote_server.py` (MCP im Fenster)

## P0-08 — KI-Hinweis an der Sendegrenze

`ai_disclosure.py` hält den sichtbaren Informationstext, den lokalen
Anzeigenachweis und die gemeinsame Sperre zusammen. `ensure_ai_disclosure`
steht vor jedem echten LLM-Modellaufruf: im Hauptfenster unmittelbar vor
`Session.propose_async`, im Chat-Einrichtungsdialog vor den beiden echten
Aufrufen der Ollama-Werkzeugprobe. Erst ein vollständig aufgebauter,
erreichbarer und zugänglicher Dialog öffnet den genau danach angeforderten Zug;
Zurück, Escape,
Schließen, ein unbekanntes Backend sowie Darstellungs- oder Speicherfehler
senden nichts.

Der Anbietertext folgt der tatsächlichen Nutzlast aus `agent/context.py` und
`session.py`, nicht einer verkürzten Produktbeschreibung: Für Anthropic nennt
er neben der aktuellen Nachricht den textlichen Szenensteckbrief,
Prüfbericht, begrenzten Chatverlauf, Anweisungen/Regeln/Werkzeugschemata und
die bei bildfähigen Modellen automatisch gerenderten Szenenansichten. Nicht
übertragen werden die Projektdatei und die Netzgeometrie selbst.

Ollama ist nicht gleichbedeutend mit „lokal“: Der eingetragene Dienst darf auf
einem zweiten Rechner liegen. Der Hinweis zeigt deshalb die von Geheimnissen,
Pfad, Abfrage und Fragment bereinigte Zieladresse und unterscheidet Loopback
von einem entfernten Ziel. Der entfernte Text nennt denselben Arbeitskontext;
die Werkzeugprobe nennt ihren festen technischen Auftrag ohne Projekt- oder
Chatinhalt.

Der Nachweis besteht ausschließlich aus Textfassung, Backend-Typ,
Zielklasse/Zieladresse und UTC-Zeitpunkt in `UiSettings`. Er reist nicht im
Projekt; Text-, Anbieter-, Local→Remote- und Hostwechsel schließen die Sperre
wieder, und die Einstellungen können ihn zurücksetzen. Weil `ChatPanel` vor
seinem Signal leert, hält es bis zur Entscheidung den unbearbeiteten
Eingabetext: Bei einem Abbruch kommen auch Leerraum und Zeilenumbrüche
vollständig und markiert ins Feld zurück.

## §29 — was die Datei mitnimmt

`print_disclosure.py` steht vor dem ersten Öffnen der Druckeinstellungen und
sagt dreierlei: Die Werte sind Erfahrungswerte; sie reisen mit einer
gespeicherten 3MF und mit der Übergabe an den Slicer; für Ergebnis und
Schäden gelten die Nummern 10 und 11 des Lizenzvertrags. Anders als der
KI-Hinweis sperrt er nichts — hier verlässt nichts das Gerät, und die Wahl
darunter entscheidet erst über das Speichern.

Drei Stellen tragen sie: Der Hinweis fragt einmal je Textfassung, der
Umschalter im Kopf des Druckdialogs zeigt und ändert sie, und
`settings_for_export()` beantwortet damit die Frage, was eine Datei
mitbekommt. Der Merker steht in `UiSettings` (Fassung und UTC-Zeitpunkt) und
reist nie in einer Projektdatei.

**Der Fehler dahinter, weil er die Bauart erklärt:** Bis zum 03.09.2026 trug
**jede** exportierte 3MF Solidons Werte. Der Kern konnte es anders
(`writer._plate_settings` gibt bei fehlenden Einstellungen ein leeres
Verzeichnis), aber die Anwendung löste an ihrer eigenen Stelle auf — der
Ausgang war zugemauert. Dazu schrieb schon das **bloße Öffnen** des Dialogs
die Werte ins Dokument, denn `set_print_settings` lief nach `exec()` ohne
Rückfrage, und der Dialog hat nur „Schließen". `PrintSettingsDialog.has_changes`
misst deshalb am Anfangszustand und nicht an einer Liste von Knöpfen.

**Bibliothek**

`catalog.py` (Bausteinkatalog, §24.3) · `filament_picker.py` (Farbe und Name
statt einer Zahl von 0 bis 7)

**Erscheinung**

`style.py` (Stylesheet, Typografie-Skala, Abstandsraster, §19.3) · `theme.py`
(hell und dunkel) · `window_chrome.py` (die Titelleiste trägt die Farben der
Anwendung — Windows malt sie weiter, es bekommt nur gesagt, in welcher Farbe;
ein Wächter am Ereignisstrom, damit kein Dialog vergessen wird) ·
`palette.py` (**Farbe trägt nie allein Bedeutung**,
§19.1) · `icons.py` · `motion.py` (Bewegung an einer Stelle, nicht an
zwanzig) · `labels.py` (kurze Texte, auf die sich mehrere Teile einigen)

**Hilfe und Bedienung**

`manual_window.py` · `tour.py` · `shortcuts_window.py` ·
`shortcut_schemes.py` (zwei Belegungen, eine Quelle) · `command_palette.py`

**Einstellungen** `settings.py` · `survey.py`

## Grenzen

- **Keine feste Zeichenkette** — alles über `tr()` (Regel 20).
- **Sprachabhängige Qt-Formate lesen die aktive Solidon-Sprache.**
  `QLocale()` ohne Argument folgt der Prozesssprache; für ausgeschriebene
  Datumswerte deshalb `QLocale(get_language())` verwenden und alle
  ausgelieferten Sprachen am gerenderten Fenster prüfen.
- **Berichtshandlungen lesen ihren Zielkörper aus Befund oder Dokument.** Eine
  aktuelle Auswahl ist kein Ersatz. „Reparieren und erneut versuchen“ steht
  nur am aktuell angehaltenen Netzschritt mit lebenden Eingängen oder an einem
  ausdrücklich benannten, noch vorhandenen Körper. Der Knopf wird nicht erneut
  angeboten, wenn unmittelbar davor bereits alle Eingänge in derselben aktiven
  Transaktion repariert wurden, und sperrt sich beim ersten Klick bis zum neuen
  Ergebnis. Berichtshandlungen stehen vollbreit untereinander, damit auch
  längere Übersetzungen in der schmalen Karte vollständig bleiben.
- **Gebündelte Befunde behalten nur gemeinsame Klickziele.** Gleiche Kennung,
  Schwere, Meldung, Herkunft, Körper, Schritt und Handlungen bilden eine
  gezählte Zeile; andere Handlungen trennen das Bündel. Ort, Merkmalsziele und
  Werte trennen allgemeine Befunde ebenfalls. Nur verlorene
  Formdetails werden trotz verschiedener alter Kennungen ab zwei Einträgen
  gebündelt; ihre internen Kennungen stehen ausschließlich in Tooltip und
  zugänglicher Beschreibung. Körper und Schritt stehen sichtbar an der Zeile.
  Der Klick zeigt beide, aber keine Merkmalskarte einer Stelle, die nicht mehr
  existiert. Der Kerntext bleibt kanalneutral; nur das Panel nennt den Klick.
- **Und der Objektbaum bündelt nach derselben Regel wie der Prüfbericht.**
  Gleichnamige *erkannte* Merkmale stehen ab `BUNDLE_FROM` unter einem
  zugeklappten Dach („Hohlkehle (17)"), die Maßspalte bleibt dort leer — ein
  Dach über siebzehn Radien hat kein Maß. Was aus einem Baustein kam, gruppiert
  weiter nach seinem Schritt; die zwei Dächer schließen einander nicht aus.
  Gemessen an `build_tray_v3.step`: 234 erkannte Merkmale, rund fünfzig
  sichtbare Zeilen „Hohlkehle R13,98 mm" untereinander, die die linke Spalte
  füllten und Parameter und Verlauf hinausdrückten. Der Bericht daneben zeigte
  dieselbe Menge längst als eine Zeile. `_restore` klappt das Dach auf, wenn
  das gewählte Merkmal darin liegt — sonst wäre ein Klick im Viewport auf eine
  Verrundung wieder ins Leere gegangen.
- **Kurzlebige Warnungsmarken sind semantischer Ansichts-Zustand.** Ring und
  Beschriftung im nativen Renderer sind nur die Darstellung. Baut eine
  Analysekarte dieselbe Auswertung neu auf, werden beide aus Punkt, Text und
  Körper erneut gezeichnet, ohne die ursprüngliche Frist zu verlängern. Ist
  der Körper ausgeblendet oder liegt auf einer anderen gewählten Platte,
  bleibt auch seine Marke unsichtbar. Ein neues Auswertungsergebnis verwirft
  Zustand und Aktoren gemeinsam.
- **Keine Bestätigungsdialoge vor rücknehmbaren Handlungen** (Regel 19), mit
  der ausdrücklich gewünschten Ausnahme für das Löschen im Verlauf: Sie
  nennt mitbetroffene Schritte und den Rückweg über Strg+Z.
- **Keine Bedeutung allein über Farbe** — immer eine zweite Kodierung
  (Regel 18).
- **Höchstens neun Menüs, zwölf Zeilen je Menü, acht Werkzeuge, acht Felder
  vorn** — `tests/test_interface_limits.py` zählt nach.
- **Nichts rechnet im Qt-Hauptthread**, was länger dauert als ein Lidschlag
  (§2.8).

## Testen

Die Tests laufen offscreen; `tests/conftest.py` setzt `QT_QPA_PLATFORM`
selbst. Zwei Fallen, beide gemessen:

- **Qt lügt vor dem Anzeigen.** `setExpanded`, `isVisible` und `hasFocus`
  antworten falsch, solange nichts angezeigt wurde — ein Test kann grün
  bleiben gegen einen Zweig, der nie läuft.
- **Gesetzt heißt nicht gezeigt.** `QMenu` verschluckt Tooltips; ein Test über
  den Wert eines Hinweises sagt nichts über seine Sichtbarkeit.

Die Suite baut über siebenhundert VTK-Fenster nacheinander auf und reißt am
Stück ab. Fensterdateien werden **je Prozess einzeln** gefahren — siehe
`CLAUDE.md` im Wurzelverzeichnis.
