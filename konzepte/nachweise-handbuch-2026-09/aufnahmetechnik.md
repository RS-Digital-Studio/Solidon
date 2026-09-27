# Aufnahmetechnik: worauf die Bildanleitungen bauen

Karte vom 27.09.2026 am Stand `228a05572` (Zweig `handbuch-umbau`), erstellt
für HB-2 und HB-3. Alle Zeilenangaben beziehen sich auf diesen Stand und
altern mit dem Code; wer sie benutzt, prüft die Stelle kurz nach. Nichts davon
ist ausgeführt worden, es ist aus dem Code gelesen.

## 1. Aufnahme heute

### `tools/make_figures.py`

- Konstanten: `SCREEN_INDEX = 1` (88), `WINDOW = None` = Arbeitsfläche des
  Zielschirms (102, `work_area` 138), `DIALOG = (520, 460)` (108),
  `REPORT = (620, 430)` (121), `SETTLE_MS = 50` (127), `EXAMPLE` (68),
  `REPORT_EXAMPLE` (76), `SAMPLE_OBJECT` (473) und `SAMPLE_PRINTER` (486) je
  Sprache.
- Bildschirmwahl: `target_screen()` (130) nimmt `screens()[SCREEN_INDEX]`,
  sonst Schirm 0; `chosen_screen(arguments)` (789) liest `--schirm N` und setzt
  das globale `SCREEN_INDEX`; `chosen_languages(wanted)` (806).
- `settle(app, rounds=12)` (220): echter `QEventLoop` über `rounds × 50 ms`,
  nötig für den OpenGL-Viewport.
- `await_result(app, session, seconds=30.0) -> bool` (237): fragt
  `session.last_result` ab.
- `prepared(widget, size=None, *, hidden=True, fit_height=False)` (426):
  `hidden` setzt `WA_DontShowOnScreen`; `hidden=False` macht `setScreen`,
  `move`, `showMaximized` (458–464).
- `shoot(widget, key, language, *, from_screen=False)` (383): schreibt nach
  `figures.find(key).path(language)`; `from_screen` greift über
  `screen.grabWindow(widget.winId())`, sonst `widget.grab()`. `SystemExit` bei
  unbekanntem Schlüssel oder Schreibfehler.
- Hilfen: `foreign_window_over(widget, rect=None)` (150, nur Windows,
  `WindowFromPoint` an 25 Punkten), `wait_until_uncovered(widget, rect=None,
  seconds=300.0)` (193), `release_viewport(window)` (406),
  `translate_parameter_titles(session)` (496), `recipe_dialog` (741),
  `frame_sketch(window, app)` (279).
- `take_all(app, language)` (523): Startbildschirm als eigener
  `StartScreen()` versteckt mit `grab`; Hauptfenster sichtbar maximiert mit
  `from_screen`; Skizzenbilder im selben Fenster; Prüfbericht als eigenes
  `ReportPanel(window)`; Operationsdialog frei gebaut; Katalog wächst um den
  Rollrest; Druckeinstellungen mit vorgetäuschtem `discover.remembered_path`.
- `main()` (828): Thema `dark` (848), alle Sprachen in **einer** Schleife in
  einem Prozess (850–859) — `tools/CLAUDE.md` verlangt aber einen Prozess je
  Sprache, und `/erzeugen` ruft das Werkzeug so auf.

### `tools/make_longform_video.py`

- Der Import lädt schon Operationen und `MainWindow` (54–73).
- `Recorder(app, window, folder, chapter)` (125); `Recorder.add(title,
  detail, seconds, *, dialog, target: QWidget|QPoint|None, click, title_card,
  overlays, caption_bottom)` (149) bewegt den Zeiger (183–200), malt Zeiger und
  Klickring über `make_video._paint_pointer`.
- `_capture_frame` (207) greift über `app.primaryScreen().grabWindow(...)`,
  also immer den Primärschirm, und skaliert mit `IgnoreAspectRatio` auf
  1920×1080; malt Dialog und Overlays und **immer** eine Einblendung.
- `_point_for(target)` (385): Widgetmitte über `mapToGlobal`, minus
  Fensterursprung, skaliert.
- `_paint_dialog(frame, dialog)` (348): legt `dialog.grab()` mit Schatten an
  die umgerechnete Stelle; auch für offene `QMenu`.
- `_place_dialog` (457), `_button(dialog)` (470: Ok, sonst Save/Apply, sonst
  `SystemExit`).
- Menüwege: `_menu_path(window, action)` (489), `_show_action_path(...)`
  (510), `_operation_action(window, op_name)` (581).
- `_show_catalog` (825), `_show_operation` (866), `_select` (664), `_fit`
  (670), `_view(window, app, direction, zoom)` (681), `_highlight_kind` (691),
  `_verify` (709), `_apply` (722), `_add_parameter` (735), `_edit_parameter`
  (797), `_begin_video` (969: Fenster 1920×1080 bei 0,0), `_finish_video`
  (989).
- Geschichten: `story_mounting_bracket` (997), `story_housing` (1271),
  `story_skadis_holder` (1651), Liste `STORIES` (1888).
- **Zwei Skizzen-Geschichten brechen heute ab:** `_draw_rectangle` (586)
  greift auf `panel.shapes_button` zu, das es nicht mehr gibt
  (`tests/test_sketch_editor.py:6661` prüft, dass es fehlt). Heute heißt der
  Knopf `panel._tool_buttons["rectangle"]` (sketch_editor.py:6106/6179).
  `story_mounting_bracket` und `story_skadis_holder` enden mit
  `AttributeError`. Das ist der Fall, den §6 des Konzepts für die
  Anleitungen verhindern soll: Ein Werkzeug, das nur beim Filmen läuft,
  merkt erst dort, dass die Oberfläche sich geändert hat.

### `tools/make_video.py`

- `_system_pointer_image()` (1647): liest den Windows-Zeiger aus der Registry.
- `_paint_pointer(frame, (x, y, click))` (1684): Klickring 16 px in
  `#e08b4e`, 3 px Stift; darauf der Systempfeil, sonst ein Ersatzpfeil.
- `record(...)` (1757) wartet vor jedem Bild mit `wait_until_uncovered`.
- Geometrie: `_widget_centre` (2113), `_world_to_window` (3707 über
  `viewport._display_of` und `devicePixelRatioF`), `_feature_click` (2121),
  `viewport_rect` (1039), `show_panels` (1085), `hide_axis_marker` (3322).
- Zielsuche mit Abbruch: `_feature_action_row` (2006, Knopftext gleich
  Registertitel, sonst `SystemExit`), `_web_loop_diameter_field` (3720).

### `tools/make_web_images.py`

- `grab(window, rect=None)` (363): greift einen **Bildschirmbereich** über
  `grabWindow(0, x, y, w, h)` — damit sind Dialoge und Menüs als eigene Fenster
  im Bild. `SystemExit` bei Zeichenfaktor ungleich 1.
- Rechtecke: `window_rect` (404), `frame_rect` (410), `dialog_bounds` (391),
  `framed(focus, ratio, bounds, margin=40)` (416, `SystemExit`, wenn der
  Zuschnitt das Ziel nicht ganz fasst), `content_rect` (453), `free_rect`
  (520), `work_rect(window, ratio)` (481–517).
- `while_open(kind, opener, act, seconds=90.0)` (556) für Dialoge mit
  `exec()`; `open_example` (602), `select_body` (618), `fill_view` (544),
  `until_quiet` (536).
- Ausgabe `save_still` (167): WebP, Qualität 86 (136).
- **Kindprozess je Sprache** `take_screens(language)` (632–662): sechs
  Umgebungsvariablen aus `ISOLATED_VARIABLES` auf einen Temp-Ordner (204–211),
  dazu `SOLIDON_WEB_IMAGES_ROOM` (216); das Kind verweigert den Lauf ohne
  Isolation (685–690).

### Markierungen auf Bildschirmfotos

Gibt es in `tools/` nicht: keine Nummern, keine Hinweispfeile, keine Rahmen
um ein Bedienelement. Vorhanden sind Zeiger und Klickring, Einblendungskästen,
Dialogschatten, im Hochformat ein orange gerahmter Detailausschnitt
(make_video 2832–2835). In `app/ui` setzt `_flash_area` einen
Stylesheet-Rahmen für 1,2 s (main_window 22282), Farbe aus `_flash_colour`
(449–461).

### Verhalten bei fehlendem Ziel

Mit `SystemExit`: `shoot`, `frame_sketch`, `take_all`, `_button`,
`_edit_parameter`, `_show_operation`, `framed`, `grab`, `while_open`. **Still**:
`_menu_path` gibt `[]` zurück, `_show_action_path` `False`, die Aufrufer
überspringen den Menüweg; `_show_catalog` zeigt ohne Ziel;
`_show_operation` fällt still auf den Ok-Knopf zurück; `dialog._editors.get`
kann `None` sein; `_flash_area` kehrt bei unbekanntem Namen still zurück.
Für die Anleitungen muss jede dieser Stellen laut scheitern.

## 2. Benannte Bereiche und Widgets

- Tour: `TourTarget` (core `tour.py:39`), `TourPanel.pointsAt` (ui
  `tour.py:92`), `MainWindow._flash_area(target)` (22248–22283) mit eigener
  Zuordnung der sieben Namen (22259–22267), holt den Prüfbericht-Reiter nach
  vorn und klappt einen zugeklappten Abschnitt auf (`open_section`,
  panels 8814). Tests: `test_ui.py:6735–6747`.

| Bereich | Attribut → Klasse (Zeile in `main_window.py`) |
|---|---|
| Links, Karte `overlay.left` | `object_tree` ObjectTree (2498) · `parameters` ParameterPanel (2502) · `history_panel` HistoryPanel (2503, `.list`) · `filaments` FilamentPanel (2510) |
| Mitte | `viewport` Viewport (2641) · `overlay` OverlayHost (2228; `.left/.right/.bottom`) · `_sketch_panel` (2872) |
| Viewport-Kinder | `.banner` PreviewBanner · `.view_bar` ViewBar · `.drag_bar` · `.plane_picker` · `.renderer` |
| Unten, Karte `overlay.bottom` | `tools` ToolStrip (2745; Knöpfe privat in `tools._buttons[key]`, Schlüssel `section`, `measure`, `transform`, `analysis`, `layers`, `explode`, `split`) · `sketch_bar` mit `sketch_finish_button` u. a. |
| Rechts | `right_column` CardColumn (3220) · `right` QTabWidget (3158) · `report` ReportPanel (3134; `.list`, `.summary`, `.to_slicer`) · `chat` (3139) · `tour` (3153) |
| Auswahlfenster | `feature_dock` _FeatureDock (12106, beim Start versteckt) · `feature_panel` FeaturePanel (2520; Fuß mit „Übernehmen", panels 6482) · `selection_operations` (3201; `._buttons` je Operation) · `quick_filament` (3206) |
| Oben | `menuBar()` · `_menus` (2352) · `toolbar` QToolBar (4461) · `header` HeaderBar (4558) |
| Statuszeile | `statusBar()` · `measurements` · `status_message` · `progress` · `alert_button` u. a. |
| Stapel | `stack` mit `start_screen` und `overlay` · `veil` · `_op_dialog` (2278) |

- `setObjectName` in `app/ui/`: 57 Aufrufe, 48 Namen, meist als
  Stylesheet-Selektor. **Ohne Namen** sind Objektbaum, Parameter, Verlauf,
  Viewport, Werkzeugleiste, Werkzeugzeile, Chat, Merkmalpanel und der
  Operationsdialog samt Feldern. `setAccessibleName` steht 240-mal.
- Rechteck eines Menüeintrags (wie `_show_action_path`): oberes Menü über
  `menuBar().actionGeometry(root.menuAction())`, dann je Ebene
  `ensurePolished`, `adjustSize`, `popup`, `setActiveAction`; der Eintrag über
  `menu.actionGeometry(action)`. Die Geometrie kennt Qt erst am gezeigten Menü;
  offene Menüs sind eigene Fenster und fehlen in `grabWindow(window.winId())`
  — dafür greift `make_web_images.grab` den Bildschirmbereich.
- QActions: Menüs Datei (3725), Bearbeiten (3847), Ansicht (4139), Hilfe
  (4370), Gruppen aus `MENU_GROUPS` (3976); gemerkt `new_action`,
  `open_action`, `save_action`, `import_action`, `_catalog_action`,
  `export_action`, `undo_action` …; je Operation `_op_actions` (2363);
  `window_commands()` (9352) liefert Titel, Kürzel, Methode, die QAction dazu
  steht in `_palette_actions` (9436). Werkzeugleiste oben: eigene QActions
  (4530), gemerkt nur `_toolbar_import`, `_toolbar_sketch`, `_toolbar_sculpt`,
  `_toolbar_armature`; `widgetForAction` wird nirgends benutzt.

## 3. Startbildschirm (`start_screen.py`)

`new_button` (866), `import_button` „Modell öffnen …" (870), `open_button`
„Projekt öffnen …" (875), `manual_button` (894), `feedback_button`,
`support_button` (909/922), `inventory_button` (939), `recent_list` (811),
`examples_area`, `more_section` (994). **Die Ablagefläche ist kein Attribut**,
sondern die lokale Variable `drop = DropArea(self)` (879), erreichbar über
`findChild(DropArea)` oder den `objectName` `dropArea` (142). Im Fenster ist
es `window.start_screen` (3308).

## 4. Dialoge

- **Operationsdialog** (`op_dialog.py:1434`): `_editors: dict[str, QWidget]`
  je Parameter (1522); hintere Felder unsichtbar, bis „Weitere Einstellungen"
  aufgeklappt ist (1832–1849); der Ok-Knopf ist `_accept_button` (1862), sein
  Text ist der Operationstitel, bei Bausteinen „Einsetzen". „Abbrechen" ohne
  Attribut. **„Übernehmen" steht nicht im Operationsdialog**, sondern im
  Merkmalfenster (`feature_panel._apply`) und in der Platzierungsleiste
  (`placement_measure_accept`). Nicht modal, `WA_DeleteOnClose`, solange offen
  in `window._op_dialog`. Vorschau-Band: `window.viewport.banner`.
- **Druckeinstellungen** (`print_settings_dialog.py:2446`), modal über
  `exec()`: `printer_choice`, `slicer_choice`, `machine_choice`,
  `process_choice`, `plate_choice`, `apply_button`, `slice_button`,
  `open_button`, `save_button`, `setup_button`; `wait_for_slicers()`,
  `_profiles_pending`, `release()`.
- **Export**: nur `QFileDialog.getSaveFileName` (unter Windows nativ);
  Felder erreichbar nur nicht-nativ (`AA_DontUseNativeDialogs`, wie
  `make_workshop_videos`).
- **Bausteinkatalog** (`catalog.py:128`), modal: `search`, `list`, `detail`,
  `_insert` „Einfügen", `save_part`, `share_part` …; Kachelrechteck über
  `list.visualItemRect(...)`.

## 5. Sprachen und Thema

| Werkzeug | Sprache | Thema | Prozess und Profil |
|---|---|---|---|
| make_figures | Schleife in einem Prozess | `dark` fest | keine Profil-Isolation |
| make_longform_video | `--language` | `dark` | ein Prozess, Primärschirm |
| make_web_images | im Kind | `dark` | Kindprozess je Sprache mit Temp-Profil |
| make_workshop_videos | `--language` | `dark` | Profil vor dem Import umgesetzt |

Kein Werkzeug erzeugt helle Bilder; die Vorgabe `UiSettings.theme` ist
`dark`. `tools/CLAUDE.md`: sechs Sprachen in einem Prozess stürzen nach der
ersten ab; wer in Nutzerverzeichnisse schreibt, läuft im Kindprozess mit
umgesetzten Variablen **vor dem ersten Import**.

## 6. Handbuch-Einbindung

- `figures.py`: `Figure.path(language)` = `app/images/manual/<sprache>/<key>.png`;
  `available()` prüft bei `shot` nur die Datei. Heute neun `shot` je Sprache,
  zusammen rund 7,9 MB; Hauptfenster 2560×1369.
- Handbuchfenster: `QImage(figure.path(...))` (manual_window 185–187), fehlt
  die Datei, steht der Alt-Text.
- `make_manual.py`: Ziel `website/handbuch/<sprache>/`; `write_figures`
  kopiert PNG **byteweise**, ohne Umwandlung oder Verkleinerung (341); im
  HTML nicht breiter als die Datei, mit sich selbst verlinkt, `lazy` außer dem
  ersten Bild; PNG ohne dunkle Variante; im Druck höchstens 9 cm hoch; PDF
  über `QWebEnginePage.printToPdf`.
- Tests: Alt-Text über 30 Zeichen (test_manual 516), jeder Verweis löst sich
  auf (522), keine Abbildung unbenutzt (529); `rendered`: jedes `<img>` liegt
  auf der Platte (249). **Nicht geprüft** werden Inhalt, Maße und Alter der
  `shot`-Bilder. Paket: `test_packaging.py:214–223` prüft
  `app/images/manual` im Paket; `ASSET-RIGHTS.toml` deckt die Bildordner.
