# Erste Maßeinheit — begrenzte Prüfung des Commitumfangs

Geprüft wurde der private Index
`C:/Users/rober/AppData/Local/Temp/solidon-cad-round-final-2a4b7e6982954e0ab0f6f88c56812d6f/measures.index`
gegen `0094eea20b12180f90f58ff51140a210bc74eba4`, einschließlich
`measures-stage.diff` und der 46 Pfade aus `measures-stage.json`.
SHA-256 des gelesenen Index:
`11b45fc6b3a2febbb2fc290ac2217d29f6506bd5706b53bb901a744fb39fd4cb`.

## Ergebnis

Im beauftragten Abgrenzungsumfang keine Befunde. Die erste Einheit ist
fachlich unabhängig vom nachfolgenden Körperproben-/Exportpaket:

- `geom/measure.py`, `scene/fits.py`, `scene/evaluate.py`, `export/writer.py`,
  `perceive/maps.py`, `ui/main_window.py` sowie beide Tourmodule entsprechen
  im Index vollständig dem bisherigen HEAD. Die neuen Imports der ersten
  Einheit beziehen sich auf ihre eigenen Maßquellen-/Erkennungsverträge oder
  bereits vorhandene APIs. Die neuen Körperprobenbefunde und deren
  Export-/Kartenanschlüsse sind nicht vorgezogen.
- Der erste Cachecodec enthält die Maßquellen und die dafür erforderliche
  Formatgrenze 18. Die nachfolgende Abbruchweitergabe und das spätere
  Veröffentlichen des Auswertungscaches stehen weiterhin im zweiten Paket.
- Alle 77 unmittelbar übersetzten Quellen der beiden bestehenden Tourmodule
  stehen in sämtlichen fünf Sprachkatalogen des Index. Ihre Übersetzungen
  entsprechen dem bisherigen HEAD. Die neuen Touraussagen zur ungeprüften
  Einbaulage und die neuen Körperproben-/Exporttexte bleiben außerhalb.
- Die einzige entfernte bisherige Katalogquelle ist der Aufweitungshinweis
  mit fest angehängtem `mm`. Sein Aufrufer in `bore_advice` wird bereits in
  derselben ersten Einheit auf den vollständig formatierten Maßplatzhalter
  umgestellt; der alte Quelltext wird im Index nicht mehr aufgerufen.
- Die elf nachfolgend genannten Fit-Testfunktionen entsprechen im ersten
  Index per AST vollständig dem bisherigen HEAD. Ihre neuen Erwartungen an
  `fit.pose_unknown` bleiben zusammen mit der Körperprobe im zweiten Paket.
  Die zwölf beim Namensvergleich sichtbaren Einträge entstehen allein durch
  die eine spätere Umbenennung; es sind elf fachliche Testfunktionen.

## Zurückgestellte Fit-Testfunktionen

Alle in `tests/test_digest_and_fits.py`:

1. `test_a_coarse_circle_measure_does_not_prove_actual_mesh_clearance`
2. `test_a_conditional_fit_requires_its_document_without_blaming_the_step`
3. `test_a_fit_that_matches_the_profile_says_nothing` — im zweiten Paket
   umbenannt zu `test_matching_profile_dimensions_leave_the_installation_pose_open`
4. `test_a_named_material_stays_what_it_says`
5. `test_a_press_fit_takes_the_gentler_number`
6. `test_a_softer_body_gets_its_own_clearance`
7. `test_fine_contours_keep_the_existing_measurable_fit_contract`
8. `test_incomplete_mesh_band_does_not_fall_back_to_a_successful_circle_measure`
9. `test_the_tolerance_follows_the_material`
10. `test_thread_fit_accepts_either_matching_handedness`
11. `test_threads_need_opposite_roles_and_the_same_pitch`

Die erste Einheit ergänzt in dieser Datei nur die neuen Maßquellenfälle und
den fehlenden Volumenwert im bestehenden vollständigen Merkmalskatalogfall.
Kein bestehender Fit-Erwartungswert ist versehentlich mitgezogen.

## Nachweisgrenze

Nur lesender Index-/Diff-/AST-/Katalogvergleich, keine Produktänderungen und
keine Tests. Diese Prüfung ersetzt weder das laufende Entwicklungstor noch
die bis zum Release zurückgestellte Fensterabnahme. Kein erneuter vollständiger
Review der Maßmetadaten oder Rundflächenrechnung.

Kann als erste fachlich geschlossene Einheit rein: ja, nach bestandenem
Entwicklungstor.
