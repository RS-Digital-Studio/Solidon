# `tests/` — die Suite

Eine Datei je Testart; `data/` ist der Referenzkorpus mit eigener Karte (je
Datei eine Zeile in `data/README.md`). Einzuhalten ist
`.claude/rules/tests.md`; wie gefahren und ein Lauf gelesen wird, steht in
`/pruefen` und derselben Regel, die Befehle in `CLAUDE.md` („Befehle“). Hier
steht, **was wo geprüft wird** und welche Helfer es gibt. Ausführlichere
Fassungen: `konzepte/begruendungen/karte-tests.md`.

## Was wo geprüft wird

| Frage | Datei |
|---|---|
| Läuft der Kern ohne Qt? | `test_core_isolation.py` |
| Importiert jede Schicht nur nach unten — `core` nie `ui`/`cli`, `i18n` gar nichts? | `test_layer_direction.py` |
| Welches Kernpaket importiert welches, eifrig oder träge? | `test_core_package_direction.py` — jede Kante eingefroren; eine neue ist eine Entscheidung |
| Stimmen `_EXPORTS`, `__all__` und `TYPE_CHECKING` der Lazy-Pakete überein? | `test_lazy_exports.py` |
| Deutsche Stämme in Bezeichnern? Alle Kataloge vollständig? | `test_language_rules.py` (ein AST je Datei für alle Sprachregeln) · `test_translations.py` (einmal extrahiert für alle Kataloge) |
| Ist jede Op vollständig registriert? | `test_registry_consistency.py` |
| Werden Normteilmaße vor dem Sortieren geprüft und bleiben gültige Größen stabil geordnet? | `test_standards.py` |
| Zweimal ausgewertet = identisch? | `test_evaluation.py` |
| Jede Rückfallstufe einmal erzwungen? | `test_boolean.py` |
| Wählt die schnelle FDM-Ausrichtung eine tragfähige Lage oder hält sie mit Befund an? | `test_fast_orientation_standing.py` — Korpusring, beide Güten, Profil, Abbruch und Resin-Ausnahme |
| Sagt eine tangierende Schnittebene vor den Stiften ab, während offene Eingänge und getrennte Schalen ihre eigene Diagnose behalten? Findet Auto Split eine gültige Folgeebene? | `test_tangent_cuts.py` — Korpusplatte, beide Güten und gemeinsame Schnittwege |
| Sammelparameter-Ops über das Register | `test_gesture_ops.py` |
| Öffnen alte Projektdateien? Halten die Korpusdateien, was sie belegen? | `test_project.py` mit `data/projects/` · `test_corpus.py` (§34) |
| Trägt jede Ausnahme einen Vorschlag? | `test_errors.py` |
| Kommt eine Rückmeldung an — und geht nur am Knopf hinaus? | `test_support.py` (§37.2) |
| Bedeutung allein über Farbe? Neun Menüs, zwölf Zeilen, acht Felder? | `test_theme_and_palette.py` · `test_interface_limits.py` |
| Budget §31, Schwelle 25 % | `test_performance.py` (`-m performance`, nur beim Release) |
| Abhängigkeiten gegen die Freigabeliste | `test_licences.py` |
| Bleiben Tutorialreihenfolge, echte Gestendauer, native Ausschnitte, Dialogzustand und akustische Satzuntertitel an ihre Quellen gebunden? | `test_workshop_edit.py` — ohne Fenster, Sprachsynthese oder Filmexport |
| Die vier Hauptwege Ende zu Ende | `test_way_one.py` … `test_way_four.py` |
| 39 Referenzanfragen an den Agenten | `test_agent_suite.py`, Fälle in `agent_cases.py`, das Modell mit vorgeschriebenen Antworten in `scripted_backend.py` |
| Folgen Eigenschaften, Befunde, Material und Übergabe dem Verfahren eines Resin-Druckers? | `test_resin.py` — die acht Abnahmepunkte aus Konzept §9, Stufe 1 |
| Öffnet jedes angebotene Modellformat dieselbe Referenzgeometrie? Prüft das Einlesen Dichtheit und Kennzahlen einmal? | `test_import_formats.py` · `test_ingest_figures.py` |
| Schätzt die Frage vor einer großen Vollerkennung die Dauer, ohne halben Messwert nach einem Abbruch? | `test_recognition_time.py` — echte Rechenprobe, gesteuerte Uhr |
| Verlauf umbauen — einfügen, verschieben, aus- und einschalten, Verweise folgen ihrem Merkmal, Strg+Z stellt die Folge her? | `test_history.py`, `test_revision.py` (beide Kerne, Beispielprojekte), `test_cli.py`; das Verlaufsfeld in `test_history_revision_ui.py` |
| Hält die Merkmalszuordnung an 1056 wirklichen Flächen (STL, STEP) durch Import, Änderung, Cache, Speichern und Undo? | `test_matching_lifecycle.py` — nur die Merkmalszahlgrenze ist freigegeben; kein Leistungsbudget |
| Konkurrierende alte Identitäten, vollständige Gruppen, widersprüchliche Ansprüche — und die Antworten an echten Bohrungen? | `test_matching_competition.py`, `test_match_decisions.py`, `test_matching_answers.py` (Fragekontext ohne Oberfläche) |
| Trägt *Kanten verfeinern* die Merkmale über die Herkunft der Dreiecke weiter, nur unter Beleg? | `test_matching.py` |
| Erhält die räumliche Vorauswahl dieselbe Zuordnung wie die volle Kostenmatrix? | `test_spatial_matching.py` |
| Wird eine gewählte Kante vor dem Verbrauchercache gebunden, und fragt eine Kollision? | `test_edge_binding.py`; die Fensterhälfte in `test_viewport_decisions.py` und `test_ui.py` |
| Zylinder- und Rundflächenmaße aus den Originalpunkten, stabil unter starrer Bewegung? | `test_cylinder_measurements.py`, `test_round_surface_measurements.py` |
| Sagen beide Kerne an einer angeschnittenen Bohrung dasselbe? | `test_partial_bores.py` |
| Bleibt der exakte Körper bei Merkmalshandlungen exakt — Volumen, Kennungen, STEP-Umlauf? | `test_exact_feature_ops.py` |
| Wulst und Kehle · Gewinde ändern und verschließen · Filament an Ringen und Gewinden, jeweils in beiden Kernen | `test_torus_feature_ops.py` · `test_thread_feature_ops.py` · `test_filament_on_rings_and_threads.py` |
| Bekommt ein Gewinde sein Gegenstück am anderen Teil, im Tabellenmaß und als ein Schritt? | `test_thread_counterpart.py`; das Fenster ohne Dialog in `test_counterpart_ui.py` |
| Entstehen Grundkörper ohne Kernwahl-Haken im richtigen Kern, und wechselt der Verlauf einen Schritt? | `test_kernel_switch.py` |
| Baut jeder mitgelieferte Baustein am exakten Träger exakt? Merkmalszusagen und Determinismus? | `test_exact_parts.py` · `test_parts.py` (zwei unabhängige Bauten) |
| Liest der exakte Kern ein importiertes Gewinde ohne Erzeugerwissen? | `test_thread_import.py`, Basiskörper in `data/threads/` |
| Verrunden, Fase, Wulst, Rundung zurücknehmen · Fläche versetzen, Formschräge — an beiden Kernen? | `test_mesh_edges.py` · `test_mesh_faces.py` |
| Lassen Merkmalshandlungen den Körper ohne Narben und alte Dreiecksnummern? | `test_feature_moves_keep_shape.py` |
| Bleibt beim Bohren in freier Richtung jede Ecke außerhalb des Schnitts Bit für Bit, und öffnet sich die Mündung an einer schrägen STL-Fläche? | `test_cut_in_world.py` |
| Findet die vektorisierte Selbstdurchdringung dieselben Paare wie der skalare Weg? | `test_self_intersections.py` |
| Analytische Geometriefälle an den registrierten Kundenwegen · Flächenplatzierung mit gleichem Werkzeugkörper in Vorschau und Operation | `test_geometry_review_regressions.py` · `test_surface_placement.py` |
| Filamentlager, Buchungen und Verbrauch · im Fenster | `test_filament_inventory.py`, `test_filament_usage.py` · `test_filament_inventory_ui.py`, `test_filament_assignment.py`, `test_filament_usage_ui.py`, `test_filament_workflow.py` — isolierte Lagerdateien, nie der Nutzerbestand |
| Zeichnet der Renderer, was der Vertrag verspricht? | `test_render_contract.py`, `test_render_gizmo.py`, `test_render_gfx_regressions.py` ohne Fenster (ohne wgpu-Adapter ein Skip mit Grund); `test_render_factory.py`; `test_render_shapes.py`, `test_navigator.py` ohne Renderer |
| Deckt der Crash-Wächter auch Arbeiter aus Fabriken und Helfern? | `test_leash.py` — nur die Verbindung des übergebenen Parameters zählt |
| Kundenwege im Fenster | `test_ui.py`; Teilbereiche in `test_ui_dialogs.py`, `test_ui_export.py`, `test_ui_licensing.py`, `test_ui_remote.py`; `test_operation_ui.py` mit leerem Fenster, wo keine Geometrie nötig ist |
| Bleiben Dialoginhalt, Klappen und Aktionsleisten erreichbar und Fenster im Bildschirm? | `test_dialog_layout.py`, `test_dialog_layout_regressions.py`; die Abläufe der Einstellungen in `test_ui_settings.py` |
| Steht im Register jeder Umschalter vor den Feldern, die er schaltet, und nie hinter der Klappe eines Vorderfelds? | `test_dependency_order.py`; die Folge des Druckdialogs in `test_print_settings_ui.py` |
| Bleiben Käuferzuordnung und Betreiberzugang aus dem Server? Halten die PHP-Endpunkte ihre Missbrauchsgrenzen? | `test_licence_admin.py`, `test_activation_server.py` · `test_public_php_security.py`; ohne PHP ein Skip, in der Linux-CI ein Fehler (`php_probe.py`) |
| Website: tote Verweise, Stempel, Paketgrößen, „nichts von außen“, Sprachfassungen | `test_website.py` — Außenlinks getrennt von eingebundenen Ressourcen |
| CI: vollständige Partitionen, Sammlung mit und ohne `--ci-shard`, Prozessisolation, Berichte · Workflowblöcke und Paketfreigabe | `test_ci_runner.py` · `test_packaging.py` mit `workflow_helpers.py` |
| Wählt `tools/affected_tests.py` richtig? Findet `tools/twin_scan.py` seine Zwillinge? | `test_affected_tests.py` · `test_twin_scan.py` |
| Hooks, Codex-Spiegel, Karten | `test_solidon3d_hooks.py` (echte Auslösung im Editor zusätzlich prüfen) · `test_agent_mirror.py` · `test_directory_docs.py` |
| Überleben zwei gleichzeitig schreibende Sitzungen in `MEMORY.md`? | `test_memory_index.py` — zwei echte Prozesse |
| Gilt eine Zusage auch dort, wo der Code auf dieser Maschine nie läuft? | `test_hard_rules.py` |
| Kommt ein Backslash in einem Pfad als Backslash an? | `test_source_escapes.py` |
| Rechnet der Hilfsprozess des Netzkerns bitgleich, endet er beim Abbrechen und — untätig — mit einem hart beendeten Elternprozess, fällt er zurück, wenn eine Rechnung nicht hinein- oder herauskommt, und sieht die Boolesche Kette seinen Tod? | `test_kernel_process.py` — echte Hilfsprozesse, dazu nachgestellte stumme, sterbende und abweisende; Schwelle null, Aufruf aus einem Nebenfaden. Das gebaute Paket startet `tools/check_frozen_helper.py` im Paketjob |

## Helfer

| Datei | Rolle |
|---|---|
| `conftest.py` | Offscreen-Qt, Nutzerverzeichnisse im Temp-Ordner (§38), Marker `windowed` für jeden `qt_app`-Test, `--ci-shard I/N` (Verteilung aus `tools/ci_shards.py`). Unter `CI` endet der Lauf in `pytest_sessionstart`, wenn der exakte Kern fehlt — lokal bleibt das ein Skip |
| `helpers.py` | Gemeinsame, nicht fenstergebundene Helfer unter öffentlichen Namen (`exact_kernel`, `FakeMesh`, `make_object`, `ridged_shaft`, `the_torus`, `CountingToken`, `stop_after`, `two_cubes`, `NavigationLog`, `SOURCE`, `rectangle`, `blind_cylinder`, `bore_seed`, `STUD_CENTRES`, `cube` für 3MF und `cube_surface` für Renderer …); keine privaten Querimporte aus `test_*.py` und nie aus `conftest`, das pytest als Plugin lädt und bei einem zweiten Import noch einmal ausgeführt wird |
| `ui_helpers.py` | Qt-gebundene gemeinsame Helfer der Fenstertests; Fenster und Sitzung je Test frisch; `shown_window` für ein gezeigtes Fenster ohne Startbildschirm, `with_a_body` für die ausgewählte Korpusfigur, `wait_until` für zugestellte Qt-Ereignisse sowie `PlacementItem`, `PlacementViewport` und `scene_with_a_hole_and_a_fillet` für Platzierungsfälle |
| `render_fakes.py` | Renderer-Doppel der Ansichtstests: schreibt Aktoren, Stile, Beschriftungen und Kamera mit, statt zu zeichnen — wer das Bild misst, nimmt den echten Renderer ohne Fenster |
| `release_signing.py` | Eigenes Schlüsselpaar der Suite für unterschriebene Versionsdateien; ob die ausgelieferte Datei gegen den echten Schlüssel trägt, prüft `test_the_published_version_file_is_signed` |
| `workflow_helpers.py` | Grenzt Jobs und Schritte der Workflows ab, ohne allgemeiner YAML-Parser zu sein |
| `php_probe.py` | Entscheidet für alle Endpunkttests über Skip oder Fehler und liefert die Befehlsbasis (`php_command()`, ohne OPcache: `WITHOUT_OPCACHE`) |
| `agent_cases.py` · `scripted_backend.py` | Fälle der Agenten-Suite · Sprach- und Mesh-Modell mit vorgeschriebenen Antworten |

## Stolperfallen

- **`tests.helpers.exact_kernel()` steht vor jedem `OCP`-Import**, auch am
  Modulanfang: Lokal wird ein fehlender Kern so ein Skip, unter `CI` hält
  `conftest.py` an, statt dass sich die Dateien des exakten Kerns still
  überspringen. Es importiert das eigene Kernelmodul regulär, damit dessen
  Importfehler nicht als fehlendes Extra verschwinden;
  `test_toolchain.py` prüft beides.
- **Testdateien importieren keine privaten Namen voneinander.** Gemeinsame
  Daten und Konstruktoren liegen unter öffentlichen Namen in `helpers.py`
  oder `ui_helpers.py`; der AST-Wächter samt Gegenprobe steht in
  `test_toolchain.py` und prüft auch eingebettete Python-Skripte für
  Kindprozesse.
- **Wer `WorkerLeash.start` durch eine Testfunktion ersetzt, übernimmt den
  Abbau** der absichtlich nicht gestarteten Arbeiter: Ein lokaler Finalizer
  ruft `release_finished_references()`, merkt `deleteLater()` vor und stellt
  `DeferredDelete` zu — die Leine hat sie nie registriert. Der Abbauvertrag
  steht in `.claude/rules/wartezeit.md` unter „Loslassen allein räumt nicht
  auf“.
- **`test_widget_lifetime.py` ordnet `installEventFilter(self)` seiner Klasse
  zu** und verlangt dort den Abmeldegriff im eigenen `eventFilter`. Bei
  modalen Dialogen des Hauptfensters prüft es zuerst die native Kindlöschung
  bei lebendem Elternfenster; `release()` allein ersetzt sie nicht.
- **`test_suite_script.py`**: Erfolgreiche Teilstücke nach der Halbierung
  löschen den ursprünglichen Abbruch nicht, der Gesamtlauf endet mit Exit 1.
