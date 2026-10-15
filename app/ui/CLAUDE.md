# `app/ui/` — die Oberfläche

PySide6 → `app.core`, nie umgekehrt (§8). Geometrie nur über Ops (Regel 2).
Abläufe/Messwerte/Anlässe: `konzepte/begruendungen/karte-app-ui.md`, gleiche Gliederung.

## Gebundene Platzierung

`PlacementFlow` und Containerentwürfe: Werte, Wiederöffnen und Arbeiterbindung
stehen in `karte-app-ui.md`, „Gebundene Platzierung“.

## Der Weg durch die Schicht

Modelldownloads und historische Ansichten: Ablauf und Bindung an den
Projektstand in `karte-app-ui.md`, „Der Weg durch die Schicht“.

`main_window.py` bindet Menüs/Auswahl, `session.py` Stapel/Auswertung/Arbeiter
(§2.8, `wartezeit.md`); `viewport.py` zeigt das `EvaluationResult`. Einstiege:

- **Operation** — Menü, Suche, Auswahlfeld und Kürzel gehen durch
  `MainWindow.launch_operation`, damit Gesten-Editoren und Undo erhalten
  bleiben → `OperationDialog` oder Platzierung → `Session.apply` →
  `evaluate_async` → `Viewport`.
- **Vorschau** — `Session.preview_async` rechnet auf einem `_Snapshot`
  (Dokumentkopie, Szene davor, Profil) im `_PreviewWorker`; `explained`,
  `progressed` und `coarse` melden Grund, Fortschritt und grobe Stufe →
  `MainWindow._show_preview`, Band `PreviewBanner`.
- **Mehrfachimport** — `import_models_async`: alle Quellen in einer Transaktion; Ablauf in `karte-app-ui.md`.
- **Historische Ansicht** — `history_preview_async`: Vergleich auf einer Dokumentkopie, Rückweg ohne Dokumentänderung; Bindung und Einfügemarke in `karte-app-ui.md`.
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
- **Import** — `import_model_async`: Arbeiter, Einheiten-/Baugruppenauswahl und Quellenablage; Ablauf in `karte-app-ui.md`.
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
  Transaktion (Regel 16). Ein Abbruch kommt als `agentCancelled`, nie als
  `failed`; ein Projektwechsel hält den Zug an.
- **Prüfbericht** — nach jeder Auswertung `print_findings_flow` im Arbeiter →
  `ReportPanel`; Handlungen aus `handlers_of`.

## Die Regeln dieses Gebiets

Maßgeblich sind die `paths:` in `.claude/rules/`; welche Regel welches Thema
trägt, sagt der Kopf von `oberflaeche.md`.

## Module

### Rahmen und Einstieg

| Datei | Zweck |
|---|---|
| `app.py` | Einstieg (§38): lokaler Absturzschutz vor Qt nur in `main()`, idempotent; Rendereradapter früh abfragen |
| `qt_platform.py` | Qt-Plattform der 3D-Ansicht und Eingabemodul — vor der `QGuiApplication`, ohne Qt-Import |
| `main_window.py` | Menüs, Auswahl, Vorschau, Export, Quittungen, Panel-/Flussverdrahtung (§2.5); Einzelheiten in `karte-app-ui.md` |
| `splash.py` | Ladebildschirm beim Start (§2.8) |
| `start_check.py` | Starttest des Pakets (`auslieferung.md`), ohne Qt auf Modulebene |
| `first_run.py` | Erstlauf (§38); `_PrinterSurvey`, `PrinterComboBox` mit fester Live-Suche; Druckerlisten je Modell gruppiert |
| `start_screen.py` | die ersten fünf Minuten (§2.3) |
| `header.py` | Kopfzeile: Projektname, `printer_button_text`, Knopf *Filamente* (Kurzhilfe aus `FilamentPanel.rows`) |

### Brücke zum Kern

| Datei | Zweck |
|---|---|
| `session.py` | die Brücke (§7, §15.6): Stapel, Auswertung, Vorschau, Import, Einfügemarke, Fragen des Kerns (`AskRequest`), `one_step` (mehrere `apply` als eine Transaktion); `evaluation_profile` (Profil der Auswertung samt Stützschwelle, `druckrat.md`), `evaluation_follows` (spät gelesene Grundlage wertet neu aus) |
| `leash.py` | die Halteleine: `Worker`, `WorkerLeash`, `wait_for_all`, `weak_slot`; `collect_in_main_thread`, GC-Zähler mit Zustandswahrung; `stop_watching_the_dying` für Filter, die ihr Objekt überleben; `configure_gil_switching`, 1-ms-Takt in `Worker.run`; `RightOfWay`: Vortritt fürs Bild |
| `app_events.py` | der eine Ereignisfilter an der Anwendung; Zuhörer melden dort ihre Ereignisarten an (`listen`), wer es tut, sagt der Modul-Docstring |
| `layout_lifetime.py` | `detach_from_layout`: Widget aus seinem haltenden Layout lösen, auch verschachtelt oder an externem Host; Elternschaft und wiederverwendete Widgets bleiben erhalten |
| `change_lock.py` | ob geändert werden darf, für jeden Zugang |
| `loading.py` | Ladeanzeige über der Ansicht (§2.8); `ProgressTiming` führt je Auswertung eine Uhr und einen Zeittext für Statuszeile und Schleier |

### Ansicht

| Datei | Zweck |
|---|---|
| `viewport.py` | Szene/Picks/Merkmale; Griffe (`_dispatch_pointer`), Vorschau/Differenz (`_cover_body`), Analyse/Schnitt/`PreviewBanner`; Zuordnung mit Kandidat/Vorbezug; Bettmaßtext: `_sketch_label_colour` |
| `render/` | der Renderer hinter der Ansicht — eigene Karte |
| `overlay.py` | Zonen über der Ansicht (§2.5): `OverlayHost`, `CardColumn`, `CardGrip`, `is_room_taker`, `FittedScroller`; natives Fenster nur für direkte Kinder (`keep_widgets_alien`, `hold_above_the_view`) |
| `cursors.py` | Mauszeiger (§19.3, Regel 18) |
| `spacemouse.py` | 3D-Maus: hidapi, auf macOS 3Dconnexion; reine `camera_step` gemeinsam für Kappe, gedrücktes Rad und Flugtasten |

### Platzierung und Griffe

| Datei | Zweck |
|---|---|
| `placement_flow.py` | Flächenplatzierung und Maße im Bild (§18.5), Dialog/`QuietHost` über `PlacementHost`; Maßgruppengröße im Ereignisfilter; Ablauf in `karte-app-ui.md`, `measured_frame` in `operationen.md` |
| `measure_card_drag.py` | `MeasureCardDrag`/`CardPlace`: Auftragslage, Titel-/Freiflächenzug; Feldgesten bleiben; aktive Mausgesten nur `QWidget`, `QWindow` durchlassen; `update_room`/`placed_rect`/`reset` |
| `measure_field_places.py` | Platz der Maßfelder bei Enge |
| `slot_handle.py` | der Langlochgriff: zwei Knöpfe am gewählten Loch, der Zug gibt Länge und Richtung (`slotDragged`); übernommen wird im Merkmalfenster |
| `scale_widget.py` | der Skalierwürfel am Gizmo (§18.11) |
| `transform_bar.py` | die Bewegen-Leiste: drei Rollen, die Zahlen daneben (§18.11) |

### Panels und Leisten

| Datei | Zweck |
|---|---|
| `panels.py` | die Panels links und der Prüfbericht rechts (§2.5): `ObjectTree`, `ParameterPanel`, `HistoryPanel`, `ReportPanel` mit `BodyChoiceDialog`, dazu das Merkmalfenster `FeaturePanel` (Handlungen, Kanten, Bausteine, Schutz vor Trennnähten, Passung anlegen) |
| `feature_editing.py` | `advanced_fields` für Maßgruppe und rechte Zeile; `configure_scope`, `explain_value_help`; panelgebundene Hauptaktionspriorität `FeatureEditPriority` |
| `card_width.py` | Natürliche Breite des eingebetteten Auswahlreiters (§2.5), Paar- und Koordinatenraster; Schnittstellen in `karte-app-ui.md` |
| `selection_operations.py` | Auswahlhandlungen aus dem Register und Suchfeld mit Trefferliste; Auswahlregeln und Schnittstellen in `karte-app-ui.md` |
| `tool_strip.py` | Werkzeugzeile unter der Ansicht (§2.4, §2.5) |
| `analysis_bar.py` | Analysekarten, Legende und Schichtvorschau (§18.4, §18.10) |
| `section_bar.py` | Schnittebene (§18.2) |
| `split_bar.py` | Trennleiste (§25, §18.2) |
| `draw_tool.py`, `draw_flow.py`, `draw_bar.py` | Aufziehen (§30.1): Klicks, Ablauf, Leiste |
| `explode_bar.py` | Explosionsansicht (§18.8) |
| `sculpt_bar.py` | Leiste der Formsitzung (§25): vier Werkzeugknöpfe, Stufe 1–10, *Spiegeln*; `GestureAnalysis` teilt Karte und Befund mit dem Skelett |
| `pose_bar.py` | Leiste des Skeletts (§25): Zustand, Hinweis, *Fertig*; danach bleiben Karte, Befund und Schließen |
| `facts.py` | was das Teil kostet, während man daran baut (§22, §29) |

### Dialoge

| Datei | Zweck |
|---|---|
| `op_dialog.py` | aus dem Parameterschema (§10, §2.4): `ValueField`, `CountField`, `offer_naming` (§13); Hauptknopf `accept_text`; vorn `lead_sentence`, `front_fields` (Einfachform) und die Lesezeile *Stelle*, hinten die Klappe mit `advanced_summary`; `show_seat` (*Auf das Bett*) |
| `feature_list.py` | `FeatureList`: Inhaltshöhe und Pixelrollweg für `FeatureSetField`; Vertrag in `karte-app-ui.md` |
| `dialog_footer.py` | `DialogFooter`: vollständige Aktionsleiste bei automatischer und manueller Breite; Vertrag in `karte-app-ui.md` |
| `dialogs.py` | Fragen und Fehler (§2.7, §21.3): `AskDialog`, `ErrorNotice`, Freischaltung, Spende, Über, `confirm_export`/`_handover`, `open_link`, `align_to_the_front` |
| `parameter_dialog.py` · `form_fields.py` · `refusal_details.py` | Projektmaß (§13) · Name und Satz je Formularfeld, Wächter `unnamed_inputs` · Absage in Fensterwörtern |
| `message_dialog.py` | Meldung und Ansage (`announce`), Quittung am Ort (`acknowledge`, `withdraw`), Knopfnamen (`name_button`) |
| `input_dialog.py` | Eingaben ohne Ort (`ask_text`, `ask_choice`) |
| `place_popup.py` | Eingabe am Ort: Farbwähler, Wertfeld (`PlacePopup`) |
| `calibration_dialog.py` | Material kalibrieren (§28.3) |
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
| `print_settings_dialog.py` | Druckeinstellungen und Slicer-Übergabe (§29, §2.4); Slicer vor Drucker, Erhebung aus `first_run`; am Resin-Drucker nur, was gilt (`_reduce_for_resin`); `PlateRun.meshes`: Netze je Platte |
| `print_disclosure.py` | der Hinweis vor der ersten Arbeit mit Druckeinstellungen (§29): Er sperrt nichts; die Wahl darunter entscheidet, ob die Erfahrungswerte mit einer 3MF mitreisen |

Druckfelder, ihre Herkunft und Suchtreffer: `druckerwahl.md`.

### Filamente und Lager

| Datei | Zweck |
|---|---|
| `filament_inventory.py` | das lokale Lager ohne Renderer (`InventoryView`): Spulen, Bestand, Archiv, Rücknahme mit Rückweg (`restore_booking`) |
| `filament_picker.py` | Filamentwähler (Name, Typ, Farbe statt 0–7), gemeinsamer Spulendialog, Slicerfilamente (`_SlicerFilamentSearch`), `FilamentPopup` hinter *Filamente*; `CatalogueWrites`; `swatch` |
| `filament_assignment.py` | Schnellauswahl an der Auswahl (`QuickFilamentPicker`, `spoolChosen`), ohne eigene Operation |
| `filament_usage.py` | Buchungsangebote nach der Ausgabe (§20) |

### Bausteine und Gegenstücke

| Datei | Zweck |
|---|---|
| `catalog.py` | Bausteinkatalog (§24.3, §2.6); `show_for_feature` filtert je Merkmalsart, `offer_ways` zum ersten Körper |
| `recipe_dialog.py` | Auswahl als Baustein speichern; wieder geöffnet: *Baustein ersetzen* |
| `counterpart_dialog.py` | Gegenstücke: zwei Stellen, Paar/Maße aus Bausteinschema und `Pair.shared`; Vorderseite/Klappe nach Schemaplatz, Feldhilfe aus `Pair.doc` |

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
| `style.py` | Formsprache/Typografie/Raster; `make_primary`, `rule`; `ContentHeight` nach Auslöser/Nutzermaß; `select_data`; `DialogScrollArea`, `expanded_width`, Bildschirmfit, Aufmachmaß, Pfeil/Haken |
| `theme.py` | hell und dunkel (§19.3); eigene Bett-Rasterrolle `bed_grid`, getrennt von Bauraum und Zeichenraster |
| `window_chrome.py` | Windows malt die Titelleiste mit Anwendungsfarben; idempotenter Ereigniswächter |
| `palette.py` | Farbe, die nie allein Bedeutung trägt (§19.1); `category_colours` färbt Bild und Legende |
| `icons.py` | Symbole als themenabhängige SVGs (§19.3, Regel 18); `svg_pixmap` rastert scharf auf HiDPI |
| `motion.py` | Bewegung an einer Stelle, nicht an zwanzig |
| `tab_signal.py` | Marken und Blinken am Reiter Prüfbericht; Zuordnungen folgen `tabMoved` |
| `tab_windows.py` | Reiter mit stabiler Inhaltshülle, Umordnung, eigenen OS-Fenstern und Rückweg; lokale Anordnung über `UiSettings.tab_layout`, vorhandene Bildschirme begrenzen die Geometrie |
| `labels.py` | Befundwerte (`value_text`) und Kurztexte in Anzeigeeinheiten, `choice_label`, `wheel_needs_focus`; Liste in `karte-app-ui.md` |

### Hilfe und Bedienung

| Datei | Zweck |
|---|---|
| `manual_window.py` | Suche in `core/manual_search.py`; F1-Anker nur für geprüfte `MarkdownNoHTML`-Überschriften (`core/manual.py`) |
| `guide_targets.py` | Gemeinsame Ziele für Tour, Anleitungen und Prüfstand: `TARGET_PROPERTY`, Menü-`objectName`, `next_click`; `view.edge:<körper>`/`edge_point_for` wählt eine gepickte Kante. Fehlend: `MissingTargetError`; API in `karte-app-ui.md` |
| `tour.py` | die Tour durch ein Beispielprojekt (§37.2) |
| `shortcuts_window.py` | die Kürzelübersicht |
| `shortcut_schemes.py` | Kürzel und Plattformtasten; `nothing_to_take_back`: Strg+Z/Y ans Fenster, wenn das Feld nichts zurückzunehmen hat; weitere Helfer in `karte-app-ui.md` |

### Einstellungen und Rückmeldung

| Datei | Zweck |
|---|---|
| `settings.py` | Oberflächen-Einstellungen (`UiSettings`) in einer schlichten Datei (§38) |
| `settings_dialog.py` | Einstellungen als Entwurf (§19.3, §38); Slicer vor Drucker, gemeinsame Erhebung aus `first_run`; jede Zeile in der Suche (`searchable_options`) |
| `support_dialog.py` | Rückmeldung senden (§37.2): Anhänge als ein Schnappschuss (`report.diagnostic_attachments()`), vor dem Senden sichtbar; ein Absturz sendet nichts |
| `survey.py` | Bogen, Nutzungsuhr und die zwei Einladungen über der Ansicht (`SurveyNotice`, `SupportNotice` auf `ViewNotice`) |

## Muster

- **Freigabe im Hauptfenster:** früher Klick bindet an das erwartete Bild
  (`_PreviewApproval.pending_click`, `_apply_when_previewed`); ohne Bildpflicht
  nur an cachegleiche Rechnung (`Session.preview_is_the_evaluation`); läuft
  oder fehlt die Auswertung, an ihr Ende (`_WaitingClick`). Wert-/Dokumentwechsel
  entwertet jede Bindung, wartende mit Satz.
  `block_apply` sperrt bei Problemen, nicht beim Warten. Dialog, Panel und
  `QuietHost` prüfen über `preview_check`/`preview_defer`.
- **Panel und Bild:** `QuietHost`: `feature_field`/`feature_field_values`.
  `set_measuring` übergibt Abschluss an die Maßgruppe; Panelzwillinge aus
  (`_blocks`, `LEADS_INTO_THE_VIEW`, `_in_the_view`); Fußknöpfe bleiben beim
  Neuaufbau verborgen. `measure_op` nennt die Handlung der Maßgruppe;
  `request_in_view` schärft über den Knopfweg, eigene scharfe Bildwege gehen vor.
  `handlingArmed` ändert keine Werte. Feldhilfe nennt zuerst `ActionField.doc`,
  danach die Maßherkunft; Ausdrucksinnenfelder behalten Grammatik und Ablehnung.
  `editingOffered` meldet den Auftrag unabhängig von vorübergehenden Sperren.
  Maßkarten: Handlungstitel `section`, Herkunft `caption`.
  Freie Orte beziehen sich auf den Abgaberaum; Randorte bleiben angedockt.
  Raumgrenzen, Klappen und Werte ändern den Wunschort nicht. Neue Aufträge
  oder andere Gruppen setzen ihn zurück; Parken trennt `positionChanged`
  über `_links`. Die Karte bleibt Hindernis für andere Maßfelder.
- **Wiederverwendung:** `FeaturePanel` und `PlacementFlow` erhalten Zeilen,
  Maßgruppen und schwebende Bedienelemente; Signaturen, Zustandsvergleich und
  Abschluss in `karte-app-ui.md`, „Muster“.
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
  im Arbeiter.
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
- Baumzeilen über `topLevelItem`/`child` gehen; kein langlebiger
  `QTreeWidgetItemIterator` beim Qt-Abbau (Grund in `karte-app-ui.md`).
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

`print_contract`, `PrintFindingsFlow`, Befundkarte und Übergabebelege:
Ablauf und Herkunft in `karte-app-ui.md`, „Prüfbericht, Export und Druck“.

## Testen

Fenstertests (`windowed` für `qt_app`) lokal nur nach `AGENTS.md`, je Datei
in eigenem Prozess (`/pruefen`).

- Sichtbarkeit nativ prüfen (`wartezeit.md`): `QMenu` zeigt gesetzte Tooltips
  nicht zwingend. Widgetwerte allein belegen keine Darstellung.
- Handlungsknöpfe aus dem Layout lesen: Ausgebaute Kinder bleiben bis
  `deleteLater` am Elternobjekt.
