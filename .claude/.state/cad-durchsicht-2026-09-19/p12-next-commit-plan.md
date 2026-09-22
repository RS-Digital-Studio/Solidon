# Nächste abgeschlossene Einheiten

Ausgangspunkt: `0094eea20b12180f90f58ff51140a210bc74eba4`, bereits gepusht.
Nächster kompletter Entwicklungsnachweis erst nach Einfrieren aller drei
Agentenpakete. Alte `current-development-gate.txt` belegt nur den Ausgangsstand.

1. Rundflächenmaße und ihre belegte Herkunft durch alle Verbraucher:
   native Kugel-/NURBS-/Integraländerungen, Mesh-Kegel/Kugel/Torus,
   Maßquellenvertrag, Erzeuger, Cache, Transformation, Digest und Oberfläche.
   Diese Änderungen hängen fachlich zusammen; der echte Zwillingstest braucht
   beide Maßwege. Ganze Fensterdateien bleiben beim Release.
2. Geometrische Passungsprobe und ihr Exportanschluss:
   `geom/measure.body_overlap`, `scene/fits`, Abschlussblock in `evaluate`,
   Exportvorprüfung und vorhandener UI-Fortschritt für Abbruch bis Schreibbeginn.
   Eigenständige Bedeutung, eigenständiger Commit nach dem Maßpaket.
3. ROADMAP mit wirklichen Commitkennungen und vollständigem Entwicklungsnachweis.

Jede Einheit mit privatem Index/ausdrücklicher Pfadliste, keine fremden
Websiteänderungen. Commit erst nach grünem gesamten Entwicklungstor für den
eingefrorenen Gesamtstand. Nach JEDEM Commit explizit pushen und Remote-Hash
prüfen. SOLIDON_KEIN_PUSH=1 unterdrückt nur den impliziten Hook-Push; der
anschließende ausdrückliche Push gehört inzwischen zum Benutzerauftrag.

## Gemeinsame Dateien für den privaten Teilindex

- `tests/test_digest_and_fits.py`: Im ersten Commit bleiben die folgenden
  elf Funktionen auf ihrem HEAD-Stand; die neuen Maßstatus-/Digestfälle
  kommen vollständig mit. Der zweite Commit stellt dann die endgültige Datei.
  - test_a_coarse_circle_measure_does_not_prove_actual_mesh_clearance
  - test_fine_contours_keep_the_existing_measurable_fit_contract
  - test_incomplete_mesh_band_does_not_fall_back_to_a_successful_circle_measure
  - test_thread_fit_accepts_either_matching_handedness
  - test_threads_need_opposite_roles_and_the_same_pitch
  - test_a_fit_that_matches_the_profile_says_nothing (aktuell umbenannt zu
    test_matching_profile_dimensions_leave_the_installation_pose_open)
  - test_a_conditional_fit_requires_its_document_without_blaming_the_step
  - test_the_tolerance_follows_the_material
  - test_a_softer_body_gets_its_own_clearance
  - test_a_named_material_stays_what_it_says
  - test_a_press_fit_takes_the_gentler_number
- `scene/CLAUDE.md`: Quellenabsatz oben gehört Maßpaket; zusammenhängender
  Absatz ab „Zusätzlich prüft `fits.check(..., cancelled=...)`“ gehört Probe.
- `geom/CLAUDE.md`: Quellenabsatz oben gehört Maßpaket; Absatz am Ende ab
  „`measure.body_overlap` misst“ gehört Probe.
- `ui/main_window.py` und UI-Karte: Maßhinweise und Export-Abbruch nicht
  vermischen. policy_review meldet nach Umsetzung genaue Methoden/Klassenteile.
- Kataloge: Maßtexte im ersten Commit, die sieben neuen Körperprobentexte
  und neuen Exportabbruchtexte im zweiten. Schlüssel aus tatsächlichen
  geänderten Aufrufern ermitteln, nichts nur nach Sprachform raten.

## Feste Zuständigkeiten

Root: `brep/canonical.py`, `brep/features.py`, `brep/properties.py`, Brepkarte,
`test_brep_surfaces.py` und ein Recognizer-Double in `test_brep_canonical_surfaces.py`.
exact_transform_kernel: `perceive/features.py`, `slots.py`, zugehörige Maß-/Fit-
und Erkennungstests/Karte. Echte Zusammensetzungsregressionen werden behoben.
policy_review: API, Quellenübernahme, Erzeuger, UI, Kataloge, genannte Tests;
danach separat Exportabbruch in MainWindow/test_ui/UI-Karte/Katalogen.
test_policy_runner: Körperprobepaket eingefroren, 250 betroffene Kerntests,
Ruff/Format/mypy grün. Danach ausschließlich lesende Diagnose der Langlochfase.

Cacheversion ist zentral von 17 auf 18 erhöht, zwei alte-Versions-
Parameterlisten in test_cache erweitert. 86 Cachefälle bestanden, Exit 0;
Protokoll p12-cache-version-18.txt. Kein Projektformatwechsel: Features sind
abgeleitete Auskünfte; Projekte speichern weiterhin Quellen/Ops.

Root ergänzt im zweiten Paket maps.py/test_maps.py: Informationsbefunde
markieren keine Passungsverletzung; offene Proben heißen „Passung prüfen“.
Eine benannte Beziehung erreicht beide Gegenstücke. 55 Kartenfälle grün,
Exit 0, p13-fit-map-consumers.txt; ursprüngliche rote Gegenprobe bleibt
als p13-fit-map-before.txt erhalten.

Neue Helfer prepare_round_gate.py und prepare_round_scope.py liegen bereit.
main_window.py/test_ui.py gehören vollständig zum zweiten Paket. Dazu kommt
der beim Gegenlesen belegte Lebensdaueranschluss: Vorprüfung beim Schließen
und Sprachwechsel abbrechen, alte Signale sicher behandeln. policy_review
behebt diesen Anschluss vor dem endgültigen Freeze; Fensterfälle bleiben
unausgeführt. Das Entwicklungstor startet erst danach und nach Mesh-Freeze.
