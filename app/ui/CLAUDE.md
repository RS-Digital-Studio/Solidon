# `app/ui/` — die Oberfläche

PySide6 → `app.core`, nie umgekehrt (§8). Geometrie nur über Ops (Regel 2).
Abläufe/Messwerte/Anlässe: `konzepte/begruendungen/karte-app-ui.md`, gleiche Gliederung.

## Gebundene Platzierung

Vor Arbeiterstart: `surface_object_for_worker` liefert Netzen die geteilte
Arbeitskopie unter `on_the_copy`, exakten Körpern eigene Kopien mit gleicher
Dreiecksfolge/nativer Flächenzuordnung.

`PlacementFlow` übernimmt Lage, Flächenbezug und Kantenabstände gemeinsam aus
`scene.placement.bound_surface_values`. `placement_fields` trennt Lagefelder von
gleichnamigen Bausteinmaßen. `bind_surface` öffnet am historischen Eingang mit
vorbereiteter Fläche, gewählten Kanten und Trägerkennung wieder; Ausdrücke bleiben
erhalten. Neue Weltkoordinaten lösen den Bezug ausdrücklich. Abbruch, Neuwahl und
Projektwechsel sperren verspätete Antworten.

Ein Grundkörper an einer ausgewählten Fläche bietet vorn Ansatzpunkt und
Verbinden. Flächenvorbereitung läuft über `Session.placement_async`; bis zur
Antwort bleibt Übernehmen unabhängig von einer älteren Vorschau gesperrt.
Erzeugen und Vereinigung stehen in derselben `_PreviewOrder` und Transaktion.
`ContainerWizardParams`/`plan_container`: benannte Maße, optionale Einlage und
Passung als Vorschauauftrag. `plan_container_edit` liefert historisch
`ContainerEdit.values` und `document_change` gemeinsam für Vorschau/Übernahme.
`promote_values=False` hält historische Schemaplätze; Ausdrücke holen keine
Rückseitenfelder nach vorn.

## Der Weg durch die Schicht

Modelldownloads binden Fortschritt/Ergebnis an Arbeiteridentität und
Projektgeneration. Nachfolger brechen Vorgänger ab; Projektwechsel,
Fensterende und Abbruch verwerfen Antworten. Vor dem Einlesen Gesteneditoren
erneut prüfen. Modellseiten bleiben als Zwischenablage-Vorbelegung erhalten
und führen über die Browserhandlung zum Download; Archive zur Importauswahl.

`main_window.py` bindet Menüs/Auswahl, `session.py` Stapel/Auswertung/Arbeiter
(§2.8, `wartezeit.md`); `viewport.py` zeigt das `EvaluationResult`. Einstiege:

- **Operation** — Menü, Palette, Auswahlfeld und Kürzel gehen durch
  `MainWindow.launch_operation`, damit Gesten-Editoren und Undo erhalten
  bleiben → `OperationDialog` oder Platzierung → `Session.apply` →
  `evaluate_async` → `Viewport`.
- **Vorschau** — `Session.preview_async` rechnet auf einem `_Snapshot`
  (Dokumentkopie, Szene davor, Profil) im `_PreviewWorker`; `explained`,
  `progressed` und `coarse` melden Grund, Fortschritt und grobe Stufe →
  `MainWindow._show_preview`, Band `PreviewBanner`.
- **Mehrfachimport** — `import_models_async` liest alle Quellen mit
  `_BatchReadWorker`, erhält ihre Koordinaten und übernimmt genau eine
  Transaktion. Einheiten ohne Metadaten werden einmal für die Auswahl erfragt;
  Lese-/Geometriefehler entfernen den ganzen Auftrag samt Quellen.
- **Historische Ansicht** — `history_preview_async` rekonstruiert den
  Transaktionsstand per Undo auf einer Kopie, mit dessen Profil. Regler und
  Differenz ändern das Dokument nicht; Projekt-/Transaktionsstempel und die
  Vorschaugeneration verwerfen verspätete Antworten. „Hier weiterarbeiten“
  setzt erst nach bewusstem Klick die vorhandene Einfügemarke. Bildwechsel
  und Rückweg erhalten die Kamera. Bearbeiten verlangt „Aktueller Stand“;
  offene Gesten-/Maßentwürfe verweigern schon den Vergleich ohne Schließen-Signal.
- **Nachbau** — `rebuild_dialog.py` bindet Kernprüfung, Grenzen und konkrete Folgen
  an einen Kandidaten. Erst `sceneApplied` gibt frei; `Session.commit_rebuild`
  übernimmt atomar. Projektwechsel verwirft Arbeiterantworten.
- **Absolute Lage** — `TransformBar` liest Bezugspunkt und Ausgangsachsen
  über `geom.transform`. „nach“ speichert absolute Zielwerte, auch beim
  Griffzug; der erste gewählte Körper liefert den Drehrahmen der Gruppe.
  Nicht belegte, gespiegelte oder gescherte Achsen bieten relatives Drehen an.
- **Drehmitte** — `OperationDialog` bietet Körper, Merkmal, Punkt und Ursprung
  für Kreis-/Spiegelmuster, Spiegeln und Fügeweg gemeinsam an. `reference_point` löst
  Körper-/Merkmalbezüge vor Vorschau und Übernahme in gespeicherte cx/cy/cz auf.
  Vorhandene Koordinaten und Ausdrücke bleiben beim Wiederöffnen unverändert.
- **Startansicht** — Die Vorwahl ersetzt kein Projekt und erhält dessen Tour.
  Erst ein wirklicher Projektwechsel beendet die alte Tour.
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

Maßgeblich sind die `paths:` in `.claude/rules/`: `oberflaeche` und
`zwillinge` allgemein; `fenster` für Dialoge/Karten, `grenzen` für Menü/Felder,
`ansicht` für Viewport/Picks/Rendering, `griffe` für Gesten, `kamera` für
Navigation, `wartezeit` für Arbeiter/Abbau, `zeichenflaeche` für den Skizzeneditor.
Die konkrete Dateizuordnung steht ausschließlich dort.

## Module

`__init__.py` trägt nur den Paketdocstring.

### Rahmen und Einstieg

| Datei | Zweck |
|---|---|
| `app.py` | Einstieg (§38): lokaler Absturzschutz vor Qt nur in `main()`, idempotent; Rendereradapter früh abfragen |
| `qt_platform.py` | Qt-Plattform der 3D-Ansicht und Eingabemodul — vor der `QGuiApplication`, ohne Qt-Import |
| `main_window.py` | Menüs (`_reason_locked`), Auswahl, Vorschau, Export, Quittungen (`announce`), Panel-/Flussverdrahtung; Griff-/Panelwinkel löschen `measured_frame` nur bei Richtungsänderung |
| `splash.py` | Ladebildschirm beim Start (§2.8) |
| `start_check.py` | Starttest des Pakets (`auslieferung.md`), ohne Qt auf Modulebene |
| `first_run.py` | Erstlauf (§38); `_PrinterSurvey`, `PrinterComboBox` mit fester Live-Suche; Druckerlisten je Modell gruppiert |
| `start_screen.py` | die ersten fünf Minuten (§2.3) |
| `header.py` | Kopfzeile: Projektname, `printer_button_text`, die belegten Filamente (`mesh.slot_indices`) |

### Brücke zum Kern

| Datei | Zweck |
|---|---|
| `session.py` | die Brücke (§7, §15.6): Stapel, Auswertung, Vorschau, Import, Einfügemarke, Fragen des Kerns (`AskRequest`), `one_step` (mehrere `apply` als eine Transaktion); `evaluation_profile` (Profil der Auswertung samt Stützschwelle, `schichtanalyse.md`), `evaluation_follows` (spät gelesene Grundlage wertet neu aus) |
| `leash.py` | die Halteleine: `Worker`, `WorkerLeash`, `wait_for_all`, `weak_slot`; `collect_in_main_thread`, GC-Zähler mit Zustandswahrung; `stop_watching_the_dying` für Ereignisfilter, die ihr Objekt überleben; `configure_gil_switching` (Umschaltintervall), `Worker.run` mit 1-ms-Takt unter Windows |
| `app_events.py` | der eine Ereignisfilter an der Anwendung; Zuhörer melden dort ihre Ereignisarten an (`listen`), wer es tut, sagt der Modul-Docstring |
| `loading.py` | Ladeanzeige über der Ansicht (§2.8); `ProgressTiming` führt je Auswertung eine Uhr und einen Zeittext für Statuszeile und Schleier |

### Ansicht

| Datei | Zweck |
|---|---|
| `viewport.py` | Viewport: Szene/Picks/Merkmale; Griffe (`_dispatch_pointer`), Vorschau/Differenz (`_cover_body`), Analyse, Schnitt, `PreviewBanner`; Zuordnung mit Kandidat und Vorbezug |
| `render/` | der Renderer hinter der Ansicht — eigene Karte |
| `overlay.py` | Zonen über der Ansicht (§2.5): `OverlayHost`, `CardColumn`, `CardGrip`, `is_room_taker`, `FittedScroller`; natives Fenster nur für direkte Kinder (`keep_widgets_alien`, `hold_above_the_view`) |
| `cursors.py` | Mauszeiger (§19.3, Regel 18) |
| `spacemouse.py` | 3D-Maus: hidapi, auf macOS 3Dconnexion; reine `camera_step` gemeinsam für Kappe, gedrücktes Rad und Flugtasten |

### Platzierung und Griffe

| Datei | Zweck |
|---|---|
| `placement_flow.py` | Flächenplatzierung (§18.5): `_settle` setzt, `_begin_depth` steuert Tiefe, Escape ruft `step_back`. `PlacementHost` verbindet Dialog/`QuietHost`, `Session.placement_async` Fläche/Werkzeug, `_Dimensions` die Maße. Mündung zuerst, `0`=Durchgang. Langloch: Flächennormale beim Setzen, positive Merkmalachse beim Ziehen/Ändern, Gegenmündung rechtshändig. Alt-`measured_frame`: `operationen.md`. |
| `slot_handle.py` | der Langlochgriff: zwei Knöpfe am gewählten Loch, der Zug gibt Länge und Richtung (`slotDragged`); übernommen wird im Merkmalfenster |
| `scale_widget.py` | der Skalierwürfel am Gizmo (§18.11) |
| `transform_bar.py` | die Bewegen-Leiste: drei Rollen, die Zahlen daneben (§18.11) |

### Panels und Leisten

| Datei | Zweck |
|---|---|
| `panels.py` | die Panels links und der Prüfbericht rechts (§2.5): `ObjectTree`, `ParameterPanel`, `HistoryPanel`, `ReportPanel` mit `BodyChoiceDialog`, dazu das Merkmalfenster `FeaturePanel` (Handlungen, Kanten, Bausteine, Schutz vor Trennnähten, Passung anlegen) |
| `selection_operations.py` | Auswahlhandlungen im Reiter Auswahl, einmal aus Register (`quick_names`, `OPEN_UP_TO`, `PICKER_HANDLES`); ohne Auswahl: alle Körper; mehrere markierte Merkmalszeilen: `QUICK_SEVERAL_FEATURES`; `add_window_action` |
| `tool_strip.py` | Werkzeugzeile unter der Ansicht (§2.4, §2.5) |
| `analysis_bar.py` | Analysekarten, Legende und Schichtvorschau (§18.4, §18.10) |
| `section_bar.py` | Schnittebene (§18.2) |
| `split_bar.py` | Trennleiste (§25, §18.2) |
| `explode_bar.py` | Explosionsansicht (§18.8) |
| `sculpt_bar.py` | Leiste der Formsitzung (§25); `GestureAnalysis` aus `analysis_bar` teilt Kartenwahl und Druckbefund mit dem Skelett |
| `pose_bar.py` | Leiste des Skeletteditors (§25); nach Abschluss bleiben Kartenwahl, Druckbefund und Schließen erreichbar |
| `facts.py` | was das Teil kostet, während man daran baut (§22, §29) |

### Dialoge

| Datei | Zweck |
|---|---|
| `op_dialog.py` | ausschließlich aus Parameterschema (§10, §2.4): `ValueField`, `CountField`, `offer_naming` (§13); Hauptknopf `accept_text`; vorn `lead_sentence` und die Lesezeile *Stelle* (`place_fields`, `place_text`) mit `aim_again` zurück zur Platzierung, hinten die Klappe mit `advanced_summary`; `show_seat`: *Auf das Bett* bei Erzeugern auf gewählter Fläche |
| `dialogs.py` | Fragen und Fehler (§2.7, §21.3): `AskDialog`, `ErrorNotice`, Freischaltung online und per Datei, `DonationDialog`, `AboutDialog`, `confirm_export`, `confirm_handover`, `open_link`; `align_to_the_front` für Dialoge mit Rückseite |
| `outline_dialog.py` | SVG-/DXF-Konturen wählen und ihre echte Extrusion sehen (§19.2); `values()` liefert nur `load_outline`-Werte |
| `step_dialog.py` | die Körper einer STEP-Baugruppe wählen; Vorschau als Hüllquader |
| `organizer_dialog.py` | Fachaufteilung eines Organizers, die Geometrie im Arbeiter (§19) |
| `seal_dialog.py` | Dichtweg als Zeichnung oder Öffnung wählen (§19.2); schreibt keine Operation |
| `binding_dialog.py` | feste Zahlen wählen, die an Projektmaße gebunden werden (§13) |
| `seal_flow.py` | bindet die Dichtwegwahl an den normalen Operationsdialog |
| `generate_dialog.py` | Weg 3: beschreiben oder ein Bild fallen lassen (§2.2, §27); nichtmodal, der Lauf steht in der Statusleiste |
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
| `print_settings_dialog.py` | Druckeinstellungen und Slicer-Übergabe (§29, §2.4); Düsenvariante nach Profilidentität, Modell und Hersteller; Cura-Übernahme nur für eine aktive Maschine und erst nach Klick; Fehlerhandlungen öffnen die Druckerwahl; am Resin-Drucker nur, was gilt (`_reduce_for_resin`); `PlateRun.meshes`: Netze je Platte |
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
| `catalog.py` | Bausteinkatalog (§24.3, §2.6); `show_for_feature` filtert je Merkmalsart, `offer_ways` zum ersten Körper |
| `recipe_dialog.py` | Auswahl als Baustein speichern; wieder geöffnet: *Baustein ersetzen* |
| `counterpart_dialog.py` | Gegenstücke: zwei Stellen, Paar/Maße aus Bausteinschema und `Pair.shared` |

Bausteinherkunft: `MainWindow.part_step_of` liest Provenienz/Schrittkategorie;
`FeaturePanel.show_part` zeigt `perceive.actions.part_actions`;
`stepChangeRequested` schreibt die Werte zurück.

### Editor

| Datei | Zweck |
|---|---|
| `sketch_editor.py` | grafischer Editor (§30.1, Stufe zwei), genau ein Ziel über `MainWindow._resolve_sketch_body`; `zeichenflaeche.md`: „Ein Körper, ein Ziel“ |

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
| `style.py` | Formsprache/Typografie/Raster; `make_primary`, `rule`; `ContentHeight` nach Auslöser/Nutzermaß; `DialogScrollArea`, `expanded_width`, Bildschirmfit, Aufmachmaß, Pfeil/Haken |
| `theme.py` | hell und dunkel (§19.3) |
| `window_chrome.py` | Windows malt die Titelleiste mit Anwendungsfarben; idempotenter Ereigniswächter |
| `palette.py` | Farbe, die nie allein Bedeutung trägt (§19.1); `category_colours` färbt Bild und Legende |
| `icons.py` | Symbole als themenabhängige SVGs (§19.3, Regel 18) |
| `motion.py` | Bewegung an einer Stelle, nicht an zwanzig |
| `tab_signal.py` | Marken und Blinken am Reiter Prüfbericht |
| `labels.py` | Kurztexte (`slicer_title`, `feature_measure`, `cavity_name`, `group_summary`, `body_requirement`, `DateField`); `choice_label` mit Wert/Einheit aus `core/registry/surfaces.py`; `wheel_needs_focus` |

### Hilfe und Bedienung

| Datei | Zweck |
|---|---|
| `manual_window.py` | Suche in `core/manual_search.py`; F1-Anker nur für geprüfte `MarkdownNoHTML`-Überschriften (`core/manual.py`) |
| `guide_targets.py` | Ziele für Tour und `tools/make_guides.py`: `widget_for`, `area_for`, `action_for`; fehlend: `MissingTargetError` |
| `tour.py` | die Tour durch ein Beispielprojekt (§37.2) |
| `shortcuts_window.py` | die Kürzelübersicht |
| `shortcut_schemes.py` | Kürzel und Plattformtasten, eine Quelle; `NavigationKeys`: Pos1/Ende/Bild an den Fokus; `return_opens`: Return öffnet am Mac |
| `command_palette.py` | die Befehlspalette (§2.6, §19.2) |

### Einstellungen und Rückmeldung

| Datei | Zweck |
|---|---|
| `settings.py` | Oberflächen-Einstellungen (`UiSettings`) in einer schlichten Datei (§38) |
| `settings_dialog.py` | Einstellungen als Entwurf (§19.3, §38); Slicer vor Drucker, gemeinsame Erhebung aus `first_run`; jede Zeile in der Palette (`option_titles`) |
| `support_dialog.py` | Rückmeldung senden (§37.2): Anhänge als ein Schnappschuss (`report.diagnostic_attachments()`), vor dem Senden sichtbar; ein Absturz sendet nichts |
| `survey.py` | Bogen, Nutzungsuhr und die zwei Einladungen über der Ansicht (`SurveyNotice`, `SupportNotice` auf `ViewNotice`) |

## Muster

- **Freigabe im Hauptfenster:** früher Klick bindet an das erwartete Bild
  (`_PreviewApproval.pending_click`, `_apply_when_previewed`); ohne Bildpflicht
  nur an cachegleiche Rechnung (`Session.preview_is_the_evaluation`). Zahl-,
  Dokument-/Projektwechsel entwertet beides. `block_apply(reason)` sperrt bei
  Problemen, nicht beim Warten. Dialog/Panel/`QuietHost` teilen `preview_check`
  und `preview_defer`, keine eigene Vorschauverwaltung.
- **Panel und Bild:** `QuietHost`: `feature_field`/`feature_field_values`.
  `set_measuring` übergibt Abschluss an die Maßgruppe; Panelzwillinge aus
  (`_blocks`, `LEADS_INTO_THE_VIEW`, `_in_the_view`); Fußknöpfe bleiben beim
  Neuaufbau verborgen. `handlingArmed` ändert keine Werte.
- **Wiederverwendung:** `FeaturePanel`-Zeilen nach `_row_signature` über
  `_keep_rows_for_reuse`, Schlüssel/Op/Felder aus aktuellem Aufruf.
  Maßgruppen über `_release_measure_group`, `bind_measure_group`,
  `keep_measure_group`, `_measure_signature`, `SPARE_MEASURE_GROUPS`;
  `PlacementFlow` parkt Leiste/Maßkarte/Tinte über `_park_floating`/`_take_parked_floating`.
  `test_feature_panel.py` vergleicht frischen und wiederverwendeten Zustand
  (`_panel_state`, `_measure_group_state`). Abschluss: `_lay_out_now` gemäß
  `ansicht.md`, dann fertige Maßbilder mit `PlacementFlow.flush_frame` bündeln.
- **Angebote aus dem Kern:** `perceive.actions` (`ACTION_ORDER`, `edge_actions`,
  `part_actions`, `not_offered_at`, `protection_of`),
  `placement.supports_surface_placement`, `registry.kernel_switch_label`,
  `requires_body`/`labels.body_requirement`; keine UI-Zweitlisten.
- **Arbeiter:** Projektgeneration/Dokument/Anfrage/Revision binden Antworten;
  `release` wartet über Leine (`wartezeit.md`). Örtliche Erkennung reicht
  Abbruchtoken an `actions_for`, Merkmalfenster über `feature_answers`.
  Nachfolger/Fensterende brechen ab und sperren Panelantworten/Sicherheitsbelege.
- `labels.step_number` liest die Anzeige aus der Dokumentreihenfolge;
  Signal-, Befund- und Operationskennungen bleiben stabil.

## Stolperfallen

- `session.last_result` ist die ausgewertete Szene; `session.scene` gibt es
  nicht. `Scene.objects` ist ein Wörterbuch; Iteration liefert Kennungen.
- `Session.apply` startet `evaluate_async`; Ergebnis und Fehler kommen später
  über Signale (`failed`). Gegenstücke schließen erst bei `result_current`
  mit `counterpartFinished`; `evaluate_now` ist der synchrone CLI-/Test-/Exportweg.
- Fensterimporte benutzen `import_model_async` und `importFailed`;
  Tests warten mit `wait_for_idle`, ein Patch von `import_model` trifft sie nicht.
- Halt sperrt `apply`; mit Einfügemarke meint `last_result` den Stand davor
  (`fenster.md`). Tests lösen Halt durch Undo, `change_params` oder
  `recount_and_retry`, Einfügen durch `stop_inserting`, dann `wait_for_idle`.
- Kennzahlen/Hohlraumketten liest der Hauptthread nur; `_warm_metrics` wärmt
  im Arbeiter. Dialogvorschau setzt `detect_features=False`, `preview_scene`
  des Agenten erkennt Merkmale.
- Vor Zustandswechseln prüfen Nutzereinstiege `_quiet_command_allowed`,
  Werkzeugstarts `ToolStrip.activation_allowed`: Maßentwürfe behalten ihre
  Auswahl auch gegen Berichtsklicks, Gesteneditoren und lokale Erkennung.
- Jede Flächenplatzierung aus `supports_surface_placement` braucht
  `_creation_tool`. Maßgruppe erst nach `set_measuring` starten; in der
  Tiefenstufe sammelt `place` nichts. Tiefenfeld und Wandzahl gehören zu den
  angehobenen Kantenmaßen, sonst liegen sie unter der Leiste. Projektparameter
  gehören in den Werkzeugschlüssel, auch bei unverändertem Skizzentext.
- `FeaturePanel.footer` gehört zum Träger: `isHidden`, nicht `isVisibleTo(panel)`.
  Neue Layoutzeilen ausdrücklich über `_set_shown` verbergen;
  `_q_showIfNotHidden` beachtet `WA_WState_ExplicitShowHide`.
- Kontextmenü je Klick als Panel-Kind erzeugen, nach `exec` mit `deleteLater`
  räumen. `customContextMenuRequested` des Objektbaums liefert bereits
  Viewport-Koordinaten; keine zweite Umrechnung über die Kopfzeile.
- Wahldialoge (Filament, Slicerprofil, Körper) und Katalog nach Antwort im
  `finally` löschen; Katalog zuerst `release`, damit Timer-Rückrufe die
  Hülle nicht über die native Löschung hinaus halten. `weak_slot` braucht
  `forward=True`, wenn Signalargumente ankommen sollen.
- Berichtshandlungen lesen das Ziel aus Befund/Dokument, nie aus Auswahl.
  `REPORT_BUNDLE_FROM` bündelt, `bundleActivated` wählt alle, `BodyChoiceDialog`
  fragt das Ziel. `_run_action_for` und `actionOnBodies` sammeln Schritte in
  einer `Session.one_step`-Transaktion; `_PER_BODY_ACTIONS` verwendet je Körper
  den Befund aus `_MEMBERS_ROLE`.
- Baum: Bündel nach Name/Maß (`BUNDLE_FROM`); `relations.cavity_chains` einmal
  je `SceneObject`, als vollständiger Ast. Eine einzelne Bausteinzeile trägt
  selbst den Namen statt eines zusätzlichen Dachs; eine funktionale Gruppe
  hängt unter der Zeile ihres Ankers.
- Warnungsmarken sind Zustand; Ring/Text nur Darstellung. Neuaufbau nutzt
  Punkt/Text/Körper, verlängert keine Frist. Andere Platte/verborgener Körper
  versteckt beide; ein neues Ergebnis verwirft beide.
- `ensure_ai_disclosure` vor `propose_async` und Ollama-Werkzeugprobe;
  Generierung verwendet `generation_disclosure_*`. Nur fertiger Dialog gibt
  frei; Abbruch/Fehler senden nichts. KI-/Drucknachweise gehören in `UiSettings`.
- Fremde Handbuchressourcen erhalten leere Daten, niemals `None` (Qt-Dateileser);
  ausschließlich `figure:` verwendet den Abbildungskatalog.
- Sprachabhängige Formate lesen `QLocale(get_language())`.
- Kartenbewegung endet mit `DeleteWhenStopped`, auch beim Ersetzen.
- `overlay.is_room_taker` prüft vier Methoden; kein `runtime_checkable Protocol`
  beim Shiboken-Resize mit unvollständigen Typdaten.

## Druckbewertung und Übergabe

- **Druckbewertung**: `print_contract` formatiert streng gelesene Profilgrundlagen
  und tatsächliche `CheckState`-Nachweise. Leere Befunde belegen keinen Abschluss.
  Session/`PrintFindingsFlow` verwerfen alte Aufträge; Materialslots liest der
  Auswertungsarbeiter. `PrintTarget` hält übersetzbare Texte für Sprachwechsel
  ohne Netzscan. Der Prüfumfang scrollt höhenbegrenzt, nennt sichtbare Körpernamen
  und wiederholt offene Prüfungen nicht.
- **Befundkarte**: `finding_meta` als eine Zeile; Nebenfolge `effect_worth_showing`.
- **Änderung und Übergabe**: `ExplainedDifference` sagt in einer Zeile, was
  sich ändert, `review_difference` nur Neues und Behobenes. Belege aus
  dem eingefrorenen Auftrag, Dateien und Slicerstarts getrennt, Gegenprobe
  `export.readback` im Arbeiter. Gleiche Importbefunde einer Transaktion werden
  gebündelt; Originalwerte und Körper bleiben zugänglich.

## Testen

Fenstertests (`windowed` für `qt_app`) nur beim Release, je Datei in eigenem
Prozess; Umfang/Aufruf: `/pruefen`, `.claude/rules/tests.md`.

- Sichtbarkeit nativ prüfen (`wartezeit.md`): `QMenu` zeigt gesetzte Tooltips
  nicht zwingend. Widgetwerte allein belegen keine Darstellung.
- Handlungsknöpfe aus dem Layout lesen: Ausgebaute Kinder bleiben bis
  `deleteLater` am Elternobjekt.
