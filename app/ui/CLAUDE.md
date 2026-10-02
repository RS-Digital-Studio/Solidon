# `app/ui/` — die Oberfläche

PySide6. Darf `app.core` benutzen, die Gegenrichtung ist verboten (§8). Die
Oberfläche rechnet keine Geometrie und ändert keine — **sie ruft Ops auf**
(Regel 2). Ausführliche Abläufe, Messwerte und Anlässe stehen in
`konzepte/begruendungen/karte-app-ui.md`, nach denselben Überschriften
gegliedert.

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
Wer an ihr vorbei rechnet, bricht Regel 2. Was länger dauert als ein
Lidschlag, rechnet nicht im Qt-Hauptthread (§2.8, `wartezeit.md`). Die
Einstiege:

- **Operation** — Menü, Palette, Auswahlfeld und Kürzel gehen durch
  `MainWindow.launch_operation`, damit Gesten-Editoren und Undo erhalten
  bleiben → `OperationDialog` oder Platzierung → `Session.apply` →
  `evaluate_async` → `Viewport`.
- **Vorschau** — `Session.preview_async` rechnet auf einem `_Snapshot`
  (Dokumentkopie, Szene davor, Profil) im `_PreviewWorker`; `explained`,
  `progressed` und `coarse` melden Grund, Fortschritt und grobe Stufe →
  `MainWindow._show_preview`, Band `PreviewBanner`.
- **Import** — `import_model_async` → `_ReadWorker`, Plan im Arbeiter →
  `pictureChanged` (das Modell vor seiner Erkennung), `importConfirmed`,
  `importRejected`, `importFailed`; STEP-Baugruppen über
  `stepImportRequested`, Konturen über `outlineImportRequested`.
  `_SourceReadWorker` liest Quellen als Bytes; `_source_read` schreibt
  sie im Hauptthread per `Session.embed_model_payload`/`import_image_payload`.
- **Merkmal** — Baum oder Pick → `FeaturePanel.show_feature`, `show_edge`,
  `show_part` → `operationRequested` (Dialog), `inViewRequested` (Maße im
  Bild über `QuietHost`), `stepChangeRequested` (Baustein).
- **Verlauf** — `HistoryPanel` meldet nur Wünsche →
  `MainWindow._wire_history_revisions` → `Session.revise_history` im
  `_RevisionWorker`.
- **Export und Slicer** — `_ExportWorker` prüft zuerst (`checked`),
  `dialogs.confirm_export` fragt, der zweite Lauf schreibt mit demselben
  Bericht; Export und `_PlateJob` tragen Szene und Dokument (§29).
- **Agent** — `ChatPanel` → `ensure_ai_disclosure` → `Session.propose_async`
  (auf einem `_Snapshot` wie die Vorschau); ein Vorschlag ist eine
  Transaktion (Regel 16).
- **Prüfbericht** — nach jeder Auswertung `print_findings_flow` im Arbeiter →
  `ReportPanel`; Handlungen aus `handlers_of`.

## Die Regeln dieses Gebiets

Sie laden über ihr `paths:`-Frontmatter; das ist maßgeblich. Hier steht die
Karte, dort das Gesetz.

| Regeldatei | Gebiet | Lädt bei |
|---|---|---|
| `oberflaeche.md` | Texte, Zahlen, gestufte Tiefe, Barrierefreiheit, Tests am Fenster | jeder Datei hier |
| `zwillinge.md` | doppelte Stellen und Zwillinge | jeder Datei unter `app/` |
| `fenster.md` | Zonen, Hauptknopf, Sicherung, Dialoggröße, Aufräumen | `main_window`, `app`, `*dialog*`, `style`, `filament_picker`, `start_screen`, `first_run`, `manual_window`, `overlay`, `panels` |
| `grenzen.md` | Menüs, Werkzeuge, Felder vorn | `main_window`, `panels`, `op_dialog`, `tool_strip`, `command_palette`, `catalog`, `selection_operations` |
| `ansicht.md` | Picks, Messen, Bildpunkte, Zeiger, wann gemalt wird, Druckplatten | `viewport`, `render/`, `qt_platform`, `placement_flow`, `overlay`, `cursors`, `analysis_bar`, `section_bar`, `split_bar`, `transform_bar`, `explode_bar`, `scale_widget`, `snapshots` |
| `griffe.md` | Zeigervorfahrt, Bewegen, Skalieren, Langloch, Maße am Merkmal | `slot_handle`, `viewport`, `transform_bar`, `render/gizmo`, `scale_widget`, `placement_flow` |
| `kamera.md` | Navigation, Drehpunkt, Einpassen, 3D-Maus | `spacemouse`, `viewport`, `render/navigator`, `render/api`, `settings`, `settings_dialog` |
| `wartezeit.md` | Fortschritt, Abbruch, Arbeiter, Qt-Abbau | `session`, `loading`, `leash`, `splash`, `main_window`, `outline_dialog`, `step_dialog`, `organizer_dialog`, `local_recognition`, `local_recognition_flow`, `print_findings_flow`, `app_events`, `placement_flow`, `comfy_dialog` |
| `zeichenflaeche.md` | der Skizzeneditor | `sketch_editor` |

## Module

`__init__.py` trägt nur den Paketdocstring.

### Rahmen und Einstieg

| Datei | Zweck |
|---|---|
| `app.py` | Einstiegspunkt (§38); richtet vor dem ersten Qt-Import den lokalen Absturzschutz ein (ein bloßer Import installiert nichts, `main()` ergänzt idempotent) und zieht die Adapterfrage des Renderers vor |
| `qt_platform.py` | welche Qt-Plattform die 3D-Ansicht braucht — entschieden vor der `QGuiApplication`, ohne Qt-Import |
| `main_window.py` | Menüs (`_reason_locked`), Auswahl, Vorschau, Export, Quittungen (`announce`), Panel-/Flussverdrahtung; Griff-/Panelwinkel löschen `measured_frame` nur bei Richtungsänderung |
| `splash.py` | Ladebildschirm beim Start (§2.8) |
| `first_run.py` | Erstlauf (§38); `_PrinterSurvey`, `PrinterComboBox` mit fester Live-Suche; Druckerlisten gemeinsam gruppiert |
| `start_screen.py` | die ersten fünf Minuten (§2.3) |
| `header.py` | Kopfzeile: Projektname, Druckerwechsel, die tatsächlich belegten Filamente (`mesh.slot_indices`) |

### Brücke zum Kern

| Datei | Zweck |
|---|---|
| `session.py` | die Brücke (§7, §15.6): Stapel, Auswertung, Vorschau, Import, Einfügemarke, Fragen des Kerns (`AskRequest`), `one_step` (mehrere `apply` als eine Transaktion); `evaluation_profile` ist das Profil der Auswertung samt wirksamer Stützschwelle des Fensters (Entscheidung L), `evaluation_follows` sagt, ob eine spät gelesene Grundlage neu auswerten lässt |
| `leash.py` | die Halteleine: `Worker`, `WorkerLeash`, `wait_for_all`, `weak_slot`; GC-Zähler mit Zustandswahrung; `stop_watching_the_dying` für Ereignisfilter, die ihr Objekt überleben; `configure_gil_switching` (Umschaltintervall beim Start), `Worker.run` mit 1 ms Zeitgeberauflösung unter Windows |
| `app_events.py` | der eine Ereignisfilter an der Anwendung; Zuhörer melden dort ihre Ereignisarten an (`listen`), wer es tut, sagt der Modul-Docstring |
| `loading.py` | Ladeanzeige über der Ansicht (§2.8); `ProgressTiming` führt je Auswertung eine Uhr und einen Zeittext für Statuszeile und Schleier |

### Ansicht

| Datei | Zweck |
|---|---|
| `viewport.py` | Viewport: Szene/Picks/Merkmale; Griffe (`_dispatch_pointer`), Vorschau/Differenz (`_cover_body`), Analyse, Schnitt, `PreviewBanner`; Zuordnung mit Kandidat und Vorbezug |
| `render/` | der Renderer hinter der Ansicht — eigene Karte |
| `overlay.py` | Zonen über der Ansicht statt neben ihr (§2.5): `OverlayHost`, `CardColumn`, Raumvertrag `is_room_taker`; ein natives Fenster nur für direkte Kinder (`keep_widgets_alien`, `hold_above_the_view`) |
| `cursors.py` | Mauszeiger (§19.3, Regel 18) |
| `spacemouse.py` | die 3D-Maus an derselben Kamera: HID über hidapi, auf dem Mac der Treiberweg über das 3Dconnexion-Framework; `camera_step` ist eine reine Funktion mit drei Aufrufern (Kappe, gedrücktes Rad, Flugtasten) — wer an einer Achse dreht, dreht an allen |

### Platzierung und Griffe

| Datei | Zweck |
|---|---|
| `placement_flow.py` | Flächenplatzierung (§18.5): `_settle` setzt, `_begin_depth` steuert Tiefe, Escape ruft `step_back`. `PlacementHost` verbindet Dialog/`QuietHost`, `Session.placement_async` Fläche/Werkzeug, `_Dimensions` die Maße. Mündung zuerst, `0`=Durchgang. Langloch: Flächennormale beim Setzen, positive Merkmalachse beim Ziehen/Ändern, Gegenmündung rechtshändig. Der Mündungsumriss trifft die Ebene längs der Werkzeugachse; bei fast paralleler Achse bleibt der Werkzeugkörper sichtbar. Alt-`measured_frame`: Achse im Arbeiter lösen, Ausdrücke beim Verschieben erhalten. |
| `slot_handle.py` | der Langlochgriff: zwei Knöpfe am gewählten Loch, der Zug gibt Länge und Richtung (`slotDragged`); übernommen wird im Merkmalfenster |
| `scale_widget.py` | der Skalierwürfel am Gizmo (§18.11) |
| `transform_bar.py` | die Bewegen-Leiste: drei Rollen, die Zahlen daneben (§18.11) |

### Panels und Leisten

| Datei | Zweck |
|---|---|
| `panels.py` | die Panels links und der Prüfbericht rechts (§2.5): `ObjectTree`, `ParameterPanel`, `HistoryPanel`, `ReportPanel` mit `BodyChoiceDialog`, dazu das Merkmalfenster `FeaturePanel` (Handlungen, Kanten, Bausteine, Schutz vor Trennnähten, Passung anlegen) |
| `selection_operations.py` | Operationen zur Auswahl in einer Karte unter Bericht und Chat, einmal aus dem Register gebaut (`quick_names`, `OPEN_UP_TO`, `PICKER_HANDLES`) — für Auswahlhandlungen der einzige Ort; ohne Auswahl stehen dort die Handlungen für alle Körper |
| `tool_strip.py` | Werkzeugzeile unter der Ansicht (§2.4, §2.5) |
| `analysis_bar.py` | Analysekarten, Legende und Schichtvorschau (§18.4, §18.10) |
| `section_bar.py` | Schnittebene (§18.2) |
| `split_bar.py` | Trennleiste (§25, §18.2) |
| `explode_bar.py` | Explosionsansicht (§18.8) |
| `sculpt_bar.py` | Leiste der Formsitzung (§25) |
| `pose_bar.py` | Leiste des Skeletteditors (§25) |
| `facts.py` | was das Teil kostet, während man daran baut (§22, §29) |

### Dialoge

| Datei | Zweck |
|---|---|
| `op_dialog.py` | **aus dem Parameterschema erzeugt** (§10, §2.4) — kein Dialog wird von Hand gebaut; wer einen tippt, hat das Register umgangen. Feldarten (`ValueField`, `CountField`, …), `offer_naming` (§13), `aim_again` zurück in die Platzierung, `show_seat` mit *Auf das Bett* für einen Erzeuger auf gewählter Fläche |
| `dialogs.py` | Fragen und Fehler (§2.7, §21.3): `AskDialog`, `ErrorNotice`, Freischaltung online und per Datei, `DonationDialog`, `AboutDialog`, `confirm_export`, `confirm_handover`, `open_link` |
| `outline_dialog.py` | SVG-/DXF-Konturen wählen und ihre echte Extrusion sehen (§19.2); `values()` liefert nur `load_outline`-Werte |
| `step_dialog.py` | die Körper einer STEP-Baugruppe wählen; Vorschau als Hüllquader |
| `organizer_dialog.py` | Fachaufteilung eines Organizers, die Geometrie im Arbeiter (§19) |
| `seal_dialog.py` | Dichtweg als Zeichnung oder Öffnung wählen (§19.2); schreibt keine Operation |
| `seal_flow.py` | bindet die Dichtwegwahl an den normalen Operationsdialog |
| `generate_dialog.py` | Weg 3: beschreiben oder ein Bild fallen lassen (§2.2, §27) |
| `variants_dialog.py` | Variantengenerator (§28.3, §25) |
| `comfy_dialog.py` | ComfyUI einrichten (§27, §36); Dateiprüfung siehe `wartezeit.md` |
| `install_dialog.py` | was fehlt, und ein Knopf, der es holt (§36, §38); eine begonnene Installation läuft beim Schließen geordnet aus |
| `update_dialog.py`, `changes_dialog.py` | die neue Version; was neu ist (§37.2) |

### Erkennung an einer Stelle

| Datei | Zweck |
|---|---|
| `local_recognition.py` | lokale Merkmale im Arbeiter erkunden (fester Dokument-, Profil- und Quellenstand); die Wege je Grund als Knöpfe (`_LOCAL_WAYS`) |
| `local_recognition_flow.py` | Originaltreffer und Fadenkreuz; erkundet wird nur in der temporären Ansicht, erst die Annahme schreibt eine `Session.apply`-Transaktion |

### Prüfbericht, Export und Druck

| Datei | Zweck |
|---|---|
| `print_findings_flow.py` | die Befunde der Schichtanalyse nach jeder Auswertung im Arbeiter (§2.8, §22); ein neuer Stand löst den laufenden ab |
| `print_settings_dialog.py` | Druckeinstellungen und Slicer-Übergabe (§29, §2.4); Grenzablehnung direkt am Zahlenfeld; Düsenvariante nach Profilidentität, Modell und Hersteller; Cura-Übernahme nur für eine aktive Maschine und erst nach Klick; Fehlerhandlungen öffnen hier die bestehende Druckerwahl; am Resin-Drucker nur, was gilt (`_reduce_for_resin`) |
| `print_disclosure.py` | der Hinweis vor der ersten Arbeit mit Druckeinstellungen (§29): Er sperrt nichts; die Wahl darunter entscheidet, ob die Erfahrungswerte mit einer 3MF mitreisen |

**Druckfelder und Kennung:** `manufacturer.base_settings`, Feldherkunft und
Rücksetzen: `konzepte/begruendungen/karte-app-ui.md`. `_editor_changed` ändert
nur das berührte Feld; gerundete Basiswerte anderer Felder bleiben unberührt. Suchtreffer in
inaktiven Stützen-/Haftungsfeldern nennen den Umschalter, ändern keine Werte,
stellen nach dessen Wahl den Fokus am Feld wieder her; der Hinweis bleibt scrollbar.

### Filamente und Lager

| Datei | Zweck |
|---|---|
| `filament_inventory.py` | das lokale Lager ohne Renderer (`InventoryView`): Spulen, Bestand, Archiv, Rücknahme mit Rückweg (`restore_booking`) |
| `filament_picker.py` | Filamentwähler (Name, Typ, Farbe statt 0–7), gemeinsamer Spulendialog und Slicerfilamente (`_SlicerFilamentSearch` im Arbeiter); Schreiben über `CatalogueWrites`; `swatch` = Farbpunkt |
| `filament_assignment.py` | Schnellauswahl an der Auswahl (`QuickFilamentPicker`, `spoolChosen`), ohne eigene Operation |
| `filament_usage.py` | Buchungsangebote nach der Ausgabe (§20) |

### Bausteine und Gegenstücke

| Datei | Zweck |
|---|---|
| `catalog.py` | der Bausteinkatalog (§24.3, §2.6); `offer_ways` führt aus der leeren Szene zu einem ersten Körper |
| `recipe_dialog.py` | Auswahl als Baustein speichern; an einem wieder geöffneten eigenen Baustein heißt der Knopf *Baustein ersetzen* |
| `counterpart_dialog.py` | Gegenstücke: Paar und Maß; Wo sind die zwei markierten Stellen. Maße aus dem Bausteinschema, gemeinsame aus `Pair.shared` |

Was aus einem Baustein kam, meint den Baustein: `MainWindow.part_step_of`
fragt Provenienz und Kategorie des Schritts, `FeaturePanel.show_part` zeigt
dessen Handlungen (`perceive.actions.part_actions`), und die Werte gehen über
`stepChangeRequested` in den Schritt zurück.

### Editor

| Datei | Zweck |
|---|---|
| `sketch_editor.py` | der grafische Skizzeneditor (§30.1, Stufe zwei); gezeichnet wird für genau einen Körper (`MainWindow._resolve_sketch_body`) — Regeln in `.claude/rules/zeichenflaeche.md`, Abschnitt „Ein Körper, ein Ziel" |

### Agent und KI-Hinweis

| Datei | Zweck |
|---|---|
| `chat.py` | der Chat (§26.3, §2.5); bis `backend_known` steht, sucht `_BackendProbe` im Fenster das Modell im Arbeiter |
| `ai_disclosure.py` | KI-Hinweis vor dem ersten Modellaufruf: Text nach Nutzlast und Ziel (Loopback/entfernt), lokaler Nachweis, gemeinsame Sperre `ensure_ai_disclosure` |
| `snapshots.py` | zwei kleine Bilder der Szene für den Agenten (§26.3) |
| `remote_server.py` | der MCP-Server im Fenster; lesende Analysen kommen als `core.agent.remote.Deferred` zurück und rechnen im Serverthread (`WindowBridge._compute`) |

### Erscheinung

| Datei | Zweck |
|---|---|
| `style.py` | Formsprache/Typografie/Raster; `make_primary`, `rule`; `ContentHeight` nach Auslöser/Nutzermaß; `DialogScrollArea`, `form_natural_width`, Bildschirmfit, Aufmachmaß, Pfeil/Haken |
| `theme.py` | hell und dunkel (§19.3) |
| `window_chrome.py` | die Titelleiste in den Farben der Anwendung (Windows malt sie und bekommt nur die Farbe gesagt); ein idempotent angemeldeter Wächter am Ereignisstrom |
| `palette.py` | Farbe, die nie allein Bedeutung trägt (§19.1); `category_colours` färbt Bild und Legende |
| `icons.py` | Symbole als themenabhängige SVGs (§19.3, Regel 18) |
| `motion.py` | Bewegung an einer Stelle, nicht an zwanzig |
| `labels.py` | Kurztexte (`slicer_title`, `feature_measure`, `cavity_name`, `body_requirement`, `DateField`); `choice_label` mit Wert/Einheit aus `core/registry/surfaces.py`; `wheel_needs_focus` |

### Hilfe und Bedienung

| Datei | Zweck |
|---|---|
| `manual_window.py` | Suche in `core/manual_search.py`; F1-Anker nur für geprüfte `MarkdownNoHTML`-Überschriften (`core/manual.py`) |
| `guide_targets.py` | was ein Name der Bildanleitungen meint (`widget_for`, `area_for`, `action_for`), für Tour und `tools/make_guides.py`; fehlt es: `MissingTargetError` |
| `tour.py` | die Tour durch ein Beispielprojekt (§37.2) |
| `shortcuts_window.py` | die Kürzelübersicht |
| `shortcut_schemes.py` | zwei Kürzelbelegungen, eine Quelle; `NavigationKeys` lässt Pos1, Ende, Bild auf und Bild ab dem fokussierten Inhalt |
| `command_palette.py` | die Befehlspalette (§2.6, §19.2) |

### Einstellungen und Rückmeldung

| Datei | Zweck |
|---|---|
| `settings.py` | Oberflächen-Einstellungen (`UiSettings`) in einer schlichten Datei (§38) |
| `settings_dialog.py` | Einstellungen als Entwurf (§19.3, §38); Slicer vor Drucker, gemeinsame Erhebung aus `first_run` |
| `support_dialog.py` | Rückmeldung senden (§37.2): Anhänge als ein Schnappschuss (`report.diagnostic_attachments()`), vor dem Senden sichtbar; ein Absturz sendet nichts |
| `survey.py` | Bogen, Nutzungsuhr und die zwei Einladungen über der Ansicht (`SurveyNotice`, `SupportNotice` auf `ViewNotice`) |

## Muster

- **Freigabe nur im Hauptfenster.** Übernehmen gilt nach dem gesehenen Bild;
  Vorschau-Warten sperrt nicht (Robert): früher Klick bindet an die erwartete
  Freigabe (`_PreviewApproval.pending_click`, `MainWindow._apply_when_previewed`).
  Zahl-, Dokument- oder Projektwechsel entwerten beides. `block_apply(reason)`
  sperrt nur bei Problemen. Dialog, Panel und `QuietHost` verwalten Vorschau
  nicht doppelt (`preview_check` fragt, `preview_defer` bindet).
- **Panel und Bild sind Zwillinge.** `QuietHost` hält den Maßentwurf
  (`feature_field`, `feature_field_values`). Bei Bildmaßen (`set_measuring`)
  trägt die Maßgruppe Übernehmen/Abbrechen; das Panel blendet Handlungsblock
  und dort gezeigte Felder aus (`_blocks`, `LEADS_INTO_THE_VIEW`, `_in_the_view`).
  Eine andere scharfe Handlung ändert keinen Wert (`handlingArmed`).
- **Wiederverwenden statt neu bauen.** `FeaturePanel` nutzt Zeilen gleicher
  Signatur erneut (`_keep_rows_for_reuse`, `_row_signature`); Schlüssel,
  Operation und Felder liest der Aufruf. Maßgruppen kehren je Signatur zurück
  (`_release_measure_group`, `bind_measure_group`, `keep_measure_group`,
  `_measure_signature`, `SPARE_MEASURE_GROUPS`). `PlacementFlow` parkt Leiste,
  Maßkarte und Tinte zwischen Flüssen (`_park_floating`, `_take_parked_floating`).
  `test_feature_panel.py` vergleicht Wiederverwendetes und Frisches zustandsweise mit
  `_panel_state`/`_measure_group_state`. Jeder Aufbau endet in
  `MainWindow._lay_out_now` (`ansicht.md`, „Die Ansicht bestellt ihr Bild“).
- **Der Kern bestimmt Angebote**, keine UI-Liste: Merkmal/Kante/Baustein aus
  `perceive.actions` (`ACTION_ORDER`, `edge_actions`, `part_actions`,
  `not_offered_at`, `protection_of`), Flächenplatzierung aus
  `placement.supports_surface_placement`, Kernwechsel aus
  `registry.kernel_switch_label`, Körpervoraussetzungen aus `requires_body` /
  `labels.body_requirement`.
- **Späte Antworten verfallen.** Arbeiteraufträge binden `project_generation`,
  Dokument, Anfrage oder Revision; Antworten nach einem Wechsel werden
  verworfen. `release()` wartet über die Leine aufs Threadende (`wartezeit.md`).
- **Merkmalantworten tragen den Abbruch bis in den Kern.** Der örtliche
  Erkennungsarbeiter reicht seinen Token an `actions_for`; der Arbeiter des
  Merkmalfensters teilt ihn über `feature_answers` mit derselben Auskunft.
  Neuer Arbeiterauftrag und Fensterende brechen den bisherigen Antwortauftrag
  ab. Ein Abbruch liefert weder eine Antwort ans Panel noch einen neuen
  gemeinsamen Sicherheitsbeleg im Merker.

## Stolperfallen

- **`session.last_result` ist die ausgewertete Szene; `session.scene` gibt es
  nicht.** `Scene.objects` ist ein Wörterbuch, Iteration liefert Kennungen;
  `'str' object has no attribute 'mesh'` wirkt wie ein leerer Import.
- **`session.apply()` endet mit `evaluate_async()` und wirft nicht.** Direkt
  danach gibt es kein Ergebnis; Fehler kommen über `failed`.
  `create_counterpart` und `create_thread_counterpart` schließen erst mit
  aktuellem Ergebnis ab (`result_current`, `counterpartFinished`).
  `evaluate_now()` rechnet synchron — für Kommandozeile, Tests und Export.
- **Fensterimport läuft über `import_model_async`**; Fehler kommen über
  `importFailed`. Tests warten mit `wait_for_idle`; `session.import_model`
  patcht nicht den Fensterweg.
- **Halt sperrt `apply`; mit Einfügemarke ist `last_result` der Stand davor**
  (`fenster.md`). Tests lösen den Halt (Undo, `change_params`,
  `recount_and_retry`) oder beenden das Einfügen (`stop_inserting`, dann
  `wait_for_idle`).
- **Der Hauptthread liest Kennzahlen/Hohlraumketten nur**; der Arbeiter wärmt
  sie (`_warm_metrics`). Dialogvorschau nutzt `detect_features=False`, der
  Agentenweg (`preview_scene`) erkennt Merkmale.
- **Nutzereinstiege prüfen `_quiet_command_allowed` vor Zustandswechseln**;
  Maßentwürfe halten so ihre Auswahl gegen Berichtsklicks, Gesteneditoren und
  lokale Erkennung. Leisten-/Werkzeugstart prüft `ToolStrip.activation_allowed`.
- **Jeder Eintrag in `placement.supports_surface_placement` braucht auch
  `placement._creation_tool`**, sonst bleiben Maßlinien und *Übernehmen* ohne
  Freigabe.
- **Maßgruppe erst nach `set_measuring`:** `PlacementFlow.start` blendet
  Felder über der Grafik ein und malt sofort.
- **In der Tiefenstufe sammelt `place` nichts**, sonst kehrt ein verborgenes
  Feld zurück. Tiefenfeld und Wandzahl gehören zu den Kantenmaßen; nicht
  angehobene Felder liegen unter der Leiste und nehmen keinen Klick.
- **Projektparameter gehören in den Werkzeugschlüssel der Platzierungsvorschau**;
  gleicher Skizzentext darf nach Maßänderung kein altes Werkzeug zeigen.
- **Knopfzeile gehört zum Träger** (`FeaturePanel.footer`): `isHidden()` statt
  `isVisibleTo(panel)` prüfen.
- **Verborgen wird ausdrücklich** (`_set_shown`): Neue Layoutzeilen melden
  `isHidden()`; `_q_showIfNotHidden` zeigt sie, sofern nicht verborgen
  (`WA_WState_ExplicitShowHide`).
- **Kontextmenüs gehören ihrem Klick:** je Rechtsklick Panel-Kind, nach `exec`
  per `deleteLater()` räumen, sonst bleiben Menü und Rückrufe liegen.
  `customContextMenuRequested` liefert im Objektbaum Viewport-Koordinaten;
  eine zweite Umrechnung verschiebt um die Kopfzeile.
- **Wahldialoge (Filament, Slicerprofil, Körper) und Bausteinkatalog** nach der
  Antwort im `finally` zur Löschung vormerken. Der Katalog stoppt vorher seine
  Zeitgeber (`release()`), sonst hält ein eingereihter gebundener Rückruf den
  nativ gelöschten Dialog am Leben.
- **`weak_slot(..., forward=True)`, wo der Empfänger die Signalargumente
  braucht** — ohne `forward` verwirft er sie.
- **Berichtshandlungen lesen den Zielkörper aus Befund/Dokument, nie aus der
  Auswahl.** Ab `REPORT_BUNDLE_FROM` bündelt der Bericht gleiche Meldungen
  (Robert); die Zeile wählt alle Körper (`bundleActivated`). `BodyChoiceDialog`
  fragt den Zielkörper. `_run_action_for` führt Operationen je Körper als
  Transaktionsschritte aus (`actionOnBodies`), Einzelhandlungen über
  `_PER_BODY_ACTIONS` mit eigenem Befund (`_MEMBERS_ROLE`), gesammelt in
  `Session.one_step` zu einer Transaktion.
- **Objektbaum bündelt nach Name und Maß** (`BUNDLE_FROM`). Eine Bohrungskette
  (`relations.cavity_chains`) bleibt ein vollständiger Ast, einmal je
  `SceneObject` gefragt. Ein Bausteindach über einer Zeile entfällt, die Zeile
  trägt seinen Namen.
- **Warnungsmarken sind semantischer Zustand**, Ring/Beschriftung nur
  Darstellung. Neuaufbau zeichnet aus Punkt, Text und Körper, ohne die Frist zu
  verlängern. Bei ausgeblendetem Körper/anderer Platte bleiben sie unsichtbar;
  ein neues Ergebnis verwirft beide.
- **`ensure_ai_disclosure` steht vor jedem echten Modellaufruf**: Hauptfenster
  vor `Session.propose_async`, Chat vor Ollama-Werkzeugprobe. Weg 3 hat den
  Nachweis `generation_disclosure_*`. Nur ein fertiger Dialog gibt frei;
  Abbruch/Fehler senden nichts. KI- und Druckhinweis-Nachweise liegen in
  `UiSettings`, nie im Projekt.
- **Das Handbuch beantwortet fremde Ressourcen mit leeren Daten**: `None` gäbe
  Qts Dateileser frei; nur `figure:` nutzt den Abbildungskatalog.
- **Sprachabhängige Qt-Formate lesen `QLocale(get_language())`**, nicht die
  Prozesssprache aus `QLocale()`.
- **Kartenbewegung endet mit dem Qt-Objekt** (`DeleteWhenStopped`), auch beim
  Ersetzen einer laufenden.
- **Raumvertrag ohne `isinstance`:** `overlay.is_room_taker` prüft vier
  Methoden; `runtime_checkable Protocol` kann beim Shiboken-Resize
  unvollständige Typdaten sehen.
- **Flatpak-Selbstversand nutzt das Portal** (`Email.ComposeEmail` via QtDBus,
  Betreff/Inhalt unkodiert), sonst `QDesktopServices` mit `mailto:`.
  Vorcodierung ist ausgeschlossen: Qt 6.11 wertet Prozentfolgen erneut aus
  (`PrettyDecoded`).

## Testen

Fenstertests (Marker `windowed`, gesetzt für jeden Test mit `qt_app`) laufen
nur beim Release, je Datei in einem eigenen Prozess; Umfang und Aufruf stehen
in `/pruefen` und `.claude/rules/tests.md`.

- **Qt lügt vor dem Anzeigen** (`wartezeit.md`), und **gesetzt heißt nicht
  gezeigt**: `QMenu` verschluckt Tooltips — ein Test über den Wert eines
  Hinweises sagt nichts über seine Sichtbarkeit.
- **Handlungsknöpfe liest man aus dem Layout, nicht aus den Kindern**:
  Ausgebaute Qt-Kinder hängen bis zur Verarbeitung von `deleteLater` noch am
  Elternobjekt.
