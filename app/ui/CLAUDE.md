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
| `fenster.md` | Zonen, Hauptknopf, Sicherung, Kartenhöhen, Aufräumen | `main_window`, `app`, `dialogs`, `*dialog*`, `start_screen`, `first_run`, `manual_window`, `overlay`, `panels` |
| `grenzen.md` | Menüs, Werkzeuge, Felder vorn | `main_window`, `panels`, `op_dialog`, `tool_strip`, `command_palette`, `catalog`, `selection_operations` |
| `ansicht.md` | Picks, Messen, Bildpunkte, Zeiger, wann gemalt wird, Druckplatten | `viewport`, `render/`, `qt_platform`, `placement_flow`, `overlay`, `cursors`, `analysis_bar`, `section_bar`, `split_bar`, `transform_bar`, `explode_bar`, `scale_widget`, `snapshots` |
| `griffe.md` | Zeigervorfahrt, Bewegen, Skalieren, Langloch, Maße am Merkmal | `slot_handle`, `viewport`, `transform_bar`, `render/gizmo`, `scale_widget`, `placement_flow` |
| `kamera.md` | Navigation, Drehpunkt, Einpassen, 3D-Maus | `spacemouse`, `viewport`, `render/navigator`, `render/api`, `settings`, `settings_dialog` |
| `wartezeit.md` | Fortschritt, Abbruch, Arbeiter, Qt-Abbau | `session`, `loading`, `leash`, `splash`, `main_window`, `outline_dialog`, `step_dialog`, `organizer_dialog`, `local_recognition`, `local_recognition_flow`, `print_findings_flow`, `app_events`, `placement_flow` |
| `zeichenflaeche.md` | der Skizzeneditor | `sketch_editor` |

## Module

`__init__.py` trägt nur den Paketdocstring.

### Rahmen und Einstieg

| Datei | Zweck |
|---|---|
| `app.py` | Einstiegspunkt (§38); richtet vor dem ersten Qt-Import den lokalen Absturzschutz ein (ein bloßer Import installiert nichts, `main()` ergänzt idempotent) und zieht die Adapterfrage des Renderers vor |
| `qt_platform.py` | welche Qt-Plattform die 3D-Ansicht braucht — entschieden vor der `QGuiApplication`, ohne Qt-Import |
| `main_window.py` | das Hauptfenster (§2.5): Menüs samt Sperrgrund (`_reason_locked`), Auswahl, Vorschaufreigabe, Export, Quittungen (`announce`), die Verdrahtung aller Panels und Flüsse |
| `splash.py` | Ladebildschirm beim Start (§2.8) |
| `first_run.py` | der erste Start (§38): Sprache, Slicer vor Drucker (`_PrinterSurvey` im Arbeiter), eigener Drucker; `add_printer_choices` und `group_printer_choices` bauen die Druckerliste auch für Einstellungen und Druckvorbereitung |
| `start_screen.py` | die ersten fünf Minuten (§2.3) |
| `header.py` | Kopfzeile: Projektname, Druckerwechsel, die tatsächlich belegten Filamente (`mesh.slot_indices`) |

### Brücke zum Kern

| Datei | Zweck |
|---|---|
| `session.py` | die Brücke (§7, §15.6): Stapel, Auswertung, Vorschau, Import, Einfügemarke, Fragen des Kerns (`AskRequest`); `evaluation_profile` ist das Profil der Auswertung samt wirksamer Stützschwelle des Fensters (Entscheidung L), `evaluation_follows` sagt, ob eine spät gelesene Grundlage neu auswerten lässt |
| `leash.py` | die Halteleine: `Worker`, `WorkerLeash`, `wait_for_all`, `weak_slot`; `stop_watching_the_dying` für Ereignisfilter, die ihr Objekt überleben |
| `app_events.py` | der eine Ereignisfilter an der Anwendung: Mauszeiger, Fensterchrom, Navigationstasten, Nutzungsuhr, Dateiempfang und Vorher-Vergleich melden dort ihre Ereignisarten an |
| `loading.py` | Ladeanzeige über der Ansicht (§2.8); `ProgressTiming` führt je Auswertung eine Uhr und einen Zeittext für Statuszeile und Schleier |

### Ansicht

| Datei | Zweck |
|---|---|
| `viewport.py` | der Viewport (§18, §2.9): Szene, Picks, Merkmalsanzeige, Griffe und ihre Vorfahrt (`_dispatch_pointer`), Vorschau und Differenz (`_cover_body`), Analysekarten, Schnitt, Band `PreviewBanner` |
| `render/` | der Renderer hinter der Ansicht — eigene Karte |
| `overlay.py` | Zonen über der Ansicht statt neben ihr (§2.5): `OverlayHost`, `CardColumn`, Raumvertrag `is_room_taker`; ein natives Fenster nur für direkte Kinder (`keep_widgets_alien`, `hold_above_the_view`) |
| `cursors.py` | Mauszeiger (§19.3, Regel 18) |
| `spacemouse.py` | die 3D-Maus an derselben Kamera: HID über hidapi, auf dem Mac der Treiberweg über das 3Dconnexion-Framework; `camera_step` ist eine reine Funktion mit drei Aufrufern (Kappe, gedrücktes Rad, Flugtasten) — wer an einer Achse dreht, dreht an allen |

### Platzierung und Griffe

| Datei | Zweck |
|---|---|
| `placement_flow.py` | Flächenplatzierung (§18.5): zielen, Stelle (`_settle`), Maße, Tiefe (`_begin_depth`), Escape je Stufe zurück (`step_back`). Träger ist ein Operationsdialog oder `QuietHost` am gewählten Merkmal (`PlacementHost`); Fläche und Werkzeug rechnet `Session.placement_async`; die Maßtinte `_Dimensions` zeichnet im Renderer. Die Tiefe beginnt mit dem Material unter der Mündung statt mit `depth = 0` (durch das ganze Teil); die Null bleibt tippbar |
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
| `op_dialog.py` | **aus dem Parameterschema erzeugt** (§10, §2.4) — kein Dialog wird von Hand gebaut; wer einen tippt, hat das Register umgangen. Feldarten (`ValueField`, `CountField`, …), `offer_naming` (§13), `aim_again` zurück in die Platzierung; F1 → `manualRequested` |
| `dialogs.py` | Fragen und Fehler (§2.7, §21.3): `AskDialog`, `ErrorNotice`, Freischaltung online und per Datei, `DonationDialog`, `AboutDialog`, `confirm_export`, `confirm_handover`, `open_link` |
| `outline_dialog.py` | SVG-/DXF-Konturen wählen und ihre echte Extrusion sehen (§19.2); `values()` liefert nur `load_outline`-Werte |
| `step_dialog.py` | die Körper einer STEP-Baugruppe wählen; Vorschau als Hüllquader |
| `organizer_dialog.py` | Fachaufteilung eines Organizers, die Geometrie im Arbeiter (§19) |
| `seal_dialog.py` | Dichtweg als Zeichnung oder Öffnung wählen (§19.2); schreibt keine Operation |
| `seal_flow.py` | bindet die Dichtwegwahl an den normalen Operationsdialog |
| `generate_dialog.py` | Weg 3: beschreiben oder ein Bild fallen lassen (§2.2, §27) |
| `variants_dialog.py` | Variantengenerator (§28.3, §25) |
| `comfy_dialog.py` | ComfyUI einrichten (§27, §36) |
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
| `print_settings_dialog.py` | Druckeinstellungen und Slicer-Übergabe (§29, §2.4); am Resin-Drucker nur, was gilt (`_reduce_for_resin`) |
| `print_disclosure.py` | der Hinweis vor der ersten Arbeit mit Druckeinstellungen (§29): Er sperrt nichts; die Wahl darunter entscheidet, ob die Erfahrungswerte mit einer 3MF mitreisen |

**Die Felder zeigen, was gedruckt wird.** `_rebase` legt nach jeder
Profilwahl das Herstellerprofil (`manufacturer.base_settings`) unter die
eigene Wahl, `_foundation_key` spart die gleiche Rechnung. `_editor_changed(path)`
macht nur das berührte Feld zur eigenen Wahl — fette Beschriftung und
*Zurücksetzen* (`_resets`, `_mark_origins`); ein Durchgang über alle Felder
machte gerundete Grundlagewerte zur Wahl. Was Solidon nicht übersetzt, steht
am Feld (`_foreign_notes`), die Grundlage unter der Kopfzeile
(`foundation_note`, `bed_plate_choice`). `has_changes` misst an
`print_settings.own_part`: Eine neue Grundlage ist kein Tun des Kunden. Sie
entsteht im `_FoundationWorker` des Hauptfensters; die Sitzung liest sie über
`follow_print_settings`.

### Filamente und Lager

| Datei | Zweck |
|---|---|
| `filament_inventory.py` | das lokale Lager ohne Renderer (`InventoryView`): Spulen, Bestand, Archiv, Rücknahme mit Rückweg (`restore_booking`) |
| `filament_picker.py` | Filamentwähler (Name, Typ und Farbe statt einer Zahl von 0 bis 7), gemeinsamer Spulendialog, Slicerfilamente (`_SlicerFilamentSearch` im Arbeiter); geschrieben wird über `CatalogueWrites` |
| `filament_assignment.py` | Schnellauswahl an der Auswahl (`QuickFilamentPicker`, `spoolChosen`), ohne eigene Operation |
| `filament_usage.py` | Buchungsangebote nach der Ausgabe (§20) |

### Bausteine und Gegenstücke

| Datei | Zweck |
|---|---|
| `catalog.py` | der Bausteinkatalog (§24.3, §2.6) |
| `recipe_dialog.py` | Auswahl als Baustein speichern; an einem wieder geöffneten eigenen Baustein heißt der Knopf *Baustein ersetzen* |
| `counterpart_dialog.py` | Gegenstücke: welches Paar und wie groß — das Wo sind die zwei markierten Stellen; Maße aus dem Bausteinschema, die gemeinsamen aus `Pair.shared` |

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
| `ai_disclosure.py` | der KI-Hinweis vor dem ersten Modellaufruf: Text nach der tatsächlichen Nutzlast und dem Ziel (Loopback oder entfernt), lokaler Nachweis, gemeinsame Sperre `ensure_ai_disclosure` |
| `snapshots.py` | zwei kleine Bilder der Szene für den Agenten (§26.3) |
| `remote_server.py` | der MCP-Server im Fenster; lesende Analysen kommen als `core.agent.remote.Deferred` zurück und rechnen im Serverthread (`WindowBridge._compute`) |

### Erscheinung

| Datei | Zweck |
|---|---|
| `style.py` | Stylesheet, Typografie-Skala, Abstandsraster (§19.3); `make_primary`, `rule` |
| `theme.py` | hell und dunkel (§19.3) |
| `window_chrome.py` | die Titelleiste in den Farben der Anwendung (Windows malt sie und bekommt nur die Farbe gesagt); ein idempotent angemeldeter Wächter am Ereignisstrom |
| `palette.py` | Farbe, die nie allein Bedeutung trägt (§19.1); `category_colours` färbt Bild und Legende |
| `icons.py` | Symbole als themenabhängige SVGs (§19.3, Regel 18) |
| `motion.py` | Bewegung an einer Stelle, nicht an zwanzig |
| `labels.py` | kurze Texte, auf die sich mehrere Teile einigen (`slicer_title`, `feature_measure`, `cavity_name`, `body_requirement`, `DateField`); `wheel_needs_focus` |

### Hilfe und Bedienung

| Datei | Zweck |
|---|---|
| `manual_window.py` | das Handbuchfenster (§2.7, §19.2), Teile als Überschriften; Rangfolge und Fundstelle aus `core/manual_search.py` |
| `guide_targets.py` | was ein Name der Bildanleitungen meint (`widget_for`, `area_for`, `action_for`) — für Tour und `tools/make_guides.py`; ein fehlendes Ziel ist `MissingTargetError` |
| `tour.py` | die Tour durch ein Beispielprojekt (§37.2) |
| `shortcuts_window.py` | die Kürzelübersicht |
| `shortcut_schemes.py` | zwei Kürzelbelegungen, eine Quelle; `NavigationKeys` lässt Pos1, Ende, Bild auf und Bild ab dem fokussierten Inhalt |
| `command_palette.py` | die Befehlspalette (§2.6, §19.2) |

### Einstellungen und Rückmeldung

| Datei | Zweck |
|---|---|
| `settings.py` | Oberflächen-Einstellungen (`UiSettings`) in einer schlichten Datei (§38) |
| `settings_dialog.py` | die Einstellungen an einem Ort (§19.3, §38); ungespeicherte Antworten stehen in einem Entwurf |
| `support_dialog.py` | Rückmeldung senden (§37.2): Anhänge als ein Schnappschuss (`report.diagnostic_attachments()`), vor dem Senden sichtbar; ein Absturz sendet nichts |
| `survey.py` | Bogen, Nutzungsuhr und die zwei Einladungen über der Ansicht (`SurveyNotice`, `SupportNotice` auf `ViewNotice`) |

## Muster

- **Eine Freigabe, und sie gehört dem Hauptfenster.** Übernehmen gilt erst
  nach dem Bild, das der Kunde gesehen hat. Warten auf die Vorschau ist
  keine Sperre (Entscheidung Robert): Ein früher Klick bindet sich an die
  erwartete Freigabe (`_PreviewApproval.pending_click`,
  `MainWindow._apply_when_previewed`); eine geänderte Zahl, ein anderes
  Dokument oder Projekt entwerten Freigabe und Klick. `block_apply(reason)`
  sperrt nur, was ein Problem hat. Dialog, Panel und `QuietHost` führen keine
  zweite Vorschauverwaltung (`preview_check` fragt, `preview_defer` bindet).
- **Panel und Bild sind Zwillinge.** `QuietHost` hält den gemeinsamen
  Maßentwurf (`feature_field`, `feature_field_values`). Stehen Maße im Bild
  (`set_measuring`), trägt die Maßgruppe Übernehmen und Abbrechen, und das
  Panel blendet den Block der Handlung und die dort schon getragenen Felder
  aus (`_blocks`, `LEADS_INTO_THE_VIEW`, `_in_the_view`). Ein Wechsel der
  scharfen Handlung ist keine Wertänderung (`handlingArmed`).
- **Wiederverwenden statt neu bauen.** `FeaturePanel` vergibt Zeilen gleicher
  Signatur neu (`_keep_rows_for_reuse`, `_row_signature`; die Zeilenwege lesen
  Schlüssel, Operation und Felder beim Aufruf, nicht beim Bau), die Maßgruppe
  kommt je Signatur zurück (`_release_measure_group`, `bind_measure_group`,
  `keep_measure_group`, `_measure_signature`, `SPARE_MEASURE_GROUPS`),
  `PlacementFlow` parkt Leiste, Maßkarte und Tinte zwischen Flüssen
  (`_park_floating`, `_take_parked_floating`). Tests vergleichen
  Wiederverwendetes mit frisch Gebautem Zustand für Zustand
  (`test_feature_panel.py`: `_panel_state`, `_measure_group_state`). Jeder
  Aufbau endet mit `MainWindow._lay_out_now` (Regel in `ansicht.md`, „Die
  Ansicht bestellt ihr Bild").
- **Was angeboten wird, sagt der Kern**, keine Liste der Oberfläche:
  Handlungen an Merkmal, Kante und Baustein aus `perceive.actions`
  (`ACTION_ORDER`, `edge_actions`, `part_actions`, `not_offered_at`,
  `protection_of`), Flächenplatzierung aus
  `placement.supports_surface_placement`, der Rechenkernwechsel aus
  `registry.kernel_switch_label`, Körpervoraussetzungen aus dem Register
  (`requires_body`, `labels.body_requirement`).
- **Späte Antworten verfallen.** Jeder Arbeiterauftrag bindet
  Projektgeneration (`project_generation`), Dokument, Anfrage oder Revision;
  eine Antwort nach einem Wechsel wird verworfen, und `release()` wartet über
  die Leine auf das Threadende (`wartezeit.md`).

## Stolperfallen

- **`session.last_result` ist die ausgewertete Szene**, ein `session.scene`
  gibt es nicht. `Scene.objects` ist ein Wörterbuch: Darüber iteriert gibt es
  Kennungen, und `'str' object has no attribute 'mesh'` sieht aus wie ein
  leerer Import.
- **`session.apply()` endet mit `evaluate_async()` und wirft nicht.** Danach
  steht noch kein Ergebnis; Fehler kommen über `failed`. `create_counterpart`
  und `create_thread_counterpart` schließen die Passung erst mit einem
  aktuellen Ergebnis ab (`result_current`, `counterpartFinished`). Synchron
  rechnet `evaluate_now()` — für Kommandozeile, Tests und Export.
- **Das Fenster importiert über `import_model_async`**, Fehler kommen über
  `importFailed`: Ein Test wartet mit `wait_for_idle`, und wer
  `session.import_model` patcht, patcht einen Weg, den das Fenster nicht geht.
- **Hinter einem Halt nimmt `apply` keinen Schritt an**, und **mit
  Einfügemarke ist `last_result` der Stand davor** (beides `fenster.md`):
  Ein Test löst den Halt erst (Undo, `change_params`, `recount_and_retry`)
  oder beendet das Einfügen (`stop_inserting`, dann `wait_for_idle`).
- **Der Hauptthread liest Kennzahlen und Hohlraumketten nur**; der
  Auswertungsarbeiter wärmt sie (`_warm_metrics`). Die Live-Vorschau eines
  Dialogs erkennt keine Merkmale (`detect_features=False`), der Agentenweg
  (`preview_scene`) schon.
- **Nutzereinstiege fragen `_quiet_command_allowed` vor dem ersten
  Zustandswechsel** — so hält ein begonnener Maßentwurf seine Auswahl gegen
  Berichtsklicks, Gesteneditoren und lokale Erkennung. Leistenwechsel und
  Werkzeugstart fragen `ToolStrip.activation_allowed`.
- **Wer eine Operation in `placement.supports_surface_placement` einträgt,
  gibt ihr auch einen Zweig in `placement._creation_tool`** — sonst stehen
  Maßlinien und ein *Übernehmen* da, das nie freigibt.
- **Die Maßgruppe startet erst nach `set_measuring`**: `PlacementFlow.start`
  blendet Felder über der Grafikfläche ein und malt sofort.
- **In der Tiefenstufe sammelt `place` nichts** — ein verborgenes, weiter
  eingesammeltes Feld käme zurück. Tiefenfeld und Wandzahl stehen in derselben
  Liste wie die Kantenmaße: Was nach der Leiste nicht gehoben wird, liegt unter
  ihr und nimmt keinen Klick.
- **Der Werkzeugschlüssel der Platzierungsvorschau enthält die
  Projektparameter**: Gleicher Skizzentext darf nach einer Maßänderung kein
  altes Werkzeug zeigen.
- **Die Knopfzeile des Merkmalfensters wohnt beim Träger**
  (`FeaturePanel.footer`): An ihren Knöpfen `isHidden()` fragen, nicht
  `isVisibleTo(panel)`.
- **Verborgen wird ausdrücklich** (`_set_shown`): Eine eben ins sichtbare
  Layout gesetzte Zeile meldet `isHidden()`, und Qt zeigt sie über
  `_q_showIfNotHidden`, solange niemand sie ausdrücklich verborgen hat
  (`WA_WState_ExplicitShowHide`).
- **Ein Kontextmenü gehört seinem Klick**: je Rechtsklick als Kind des Panels
  gebaut und nach `exec` mit `deleteLater()` geräumt, sonst bleibt jedes samt
  Rückrufen liegen. `customContextMenuRequested` liefert im Objektbaum schon
  Viewport-Koordinaten; eine zweite Umrechnung verschiebt um die Kopfzeile.
- **Modale Wahldialoge (Filament, Slicerprofil, Körper) und der
  Bausteinkatalog werden nach der Antwort im `finally` zur Löschung
  vorgemerkt**; der Katalog hält vorher seine Zeitgeberkette an (`release()`),
  sonst hält ein eingereihter gebundener Rückruf die Hülle des nativ
  gelöschten Dialogs.
- **`weak_slot(..., forward=True)`, wo der Empfänger die Signalargumente
  braucht** — ohne `forward` verwirft er sie.
- **Berichtshandlungen lesen ihren Zielkörper aus Befund oder Dokument**, nie
  aus der Auswahl. Gleiche Meldungen bündelt der Bericht ab
  `REPORT_BUNDLE_FROM` (Entscheidung Robert); eine Bündelzeile wählt beim
  Klick alle Körper (`bundleActivated`), ihre Handlung fragt
  (`BodyChoiceDialog`) und geht über `_run_action_for`: eine Operation als
  Schritt je Körper in einer Transaktion (`actionOnBodies`), eine Handlung an
  einem Körper (`_PER_BODY_ACTIONS`) mit dessen eigenem Befund
  (`_MEMBERS_ROLE`).
- **Der Objektbaum bündelt nach Name und Maß** (`BUNDLE_FROM`); eine
  Bohrungskette (`relations.cavity_chains`) bleibt ein vollständiger Ast und
  wird einmal je `SceneObject` gefragt; ein Bausteindach über einer einzigen
  Zeile entfällt, die Zeile trägt seinen Namen.
- **Warnungsmarken sind semantischer Zustand**, Ring und Beschriftung nur
  Darstellung: Ein Neuaufbau zeichnet sie aus Punkt, Text und Körper neu, ohne
  die Frist zu verlängern; am ausgeblendeten Körper oder auf einer anderen
  Platte bleibt sie unsichtbar; ein neues Ergebnis verwirft beides.
- **`ensure_ai_disclosure` steht vor jedem echten Modellaufruf**
  (Hauptfenster vor `Session.propose_async`, Chat-Einrichtung vor der
  Ollama-Werkzeugprobe); Weg 3 führt einen eigenen Nachweis
  (`generation_disclosure_*`). Nur ein vollständig aufgebauter Dialog gibt
  frei; Abbruch und Fehler senden nichts. Diese Nachweise und der des
  Druckhinweises stehen in `UiSettings`, nie im Projekt.
- **Das Handbuch beantwortet fremde Ressourcen mit leeren Daten** — `None`
  gäbe Qts eigenen Dateileser frei; nur `figure:` geht über den
  Abbildungskatalog.
- **Sprachabhängige Qt-Formate lesen `QLocale(get_language())`**;
  `QLocale()` folgt der Prozesssprache.
- **Eine Kartenbewegung endet mit ihrem Qt-Objekt** (`DeleteWhenStopped`,
  auch beim Ersetzen einer laufenden).
- **Der Raumvertrag fragt ohne `isinstance`**: `overlay.is_room_taker` prüft
  die vier Methoden ausdrücklich; gegen ein `runtime_checkable Protocol` kann
  ein Shiboken-Resize unvollständige Typdaten sehen.
- **Selbstversand im Flatpak geht über das Portal** (`Email.ComposeEmail` über
  QtDBus, Betreff und Inhalt unkodiert), außerhalb über `QDesktopServices` mit
  `mailto:`. Eine vorab kodierte `mailto:`-Adresse ist ausgeschlossen: Qt 6.11
  wertet Prozentfolgen erneut aus (`PrettyDecoded`).

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
