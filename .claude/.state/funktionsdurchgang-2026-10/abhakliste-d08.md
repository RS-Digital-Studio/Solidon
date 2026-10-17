# Abhakliste D8

Erzeugt von `tools/function_report.py` (Konzept Funktionsdurchgang §7); nicht von Hand bearbeiten — die Prüfsumme merkt es.

| | |
|---|---|
| Paket | D8 |
| Prüfsumme | 96deb6428e8b7bf7cb4ffc3e617ee34688bc000a295a058ff9a93ccb4841b0d6 |
| Commit | d9f7a81f9436165c8b2e58cb3013ecf2e07d6602 |
| Datum | 2026-10-17 |
| Laufordner | `schlusslauf-d9f7a81f/L4-d0` |
| Zeilen | 77 |
| gut | 0 |
| gut nach Fix | 0 |
| offen mit RM | 77 |
| nicht geprüft | 0 |

## Funktionen

`ja` erfüllt · `FD-n` Fund · `—` entfällt · `B` Urteil der Stufe B steht aus · `C` nur Stufe C · `?` nicht gelaufen · `n.p.` nicht prüfbar

| Kennung | Art | Szene | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | Urteil | Funde |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| arrange_bed | operation | zwei_koerper.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-737, RM-745 | FD-101 |
| check_collisions | operation | zwei_koerper.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-737, RM-745 | FD-101 |
| check_join_path | operation | zwei_koerper.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-745 |  |
| compensate_first_layer | operation | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-745 |  |
| create_seal | operation | merkmal.face.exakt | offen | offen | offen | FD-287 | offen | offen | offen | offen | FD-251 | offen | ja | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-745 | FD-251, FD-287 |
| cut_away | operation | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-745 |  |
| delete_object | operation | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-737, RM-745 | FD-115, FD-243 |
| duplicate_object | operation | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-745 |  |
| hollow_object | operation | merkmal.face.exakt | offen | offen | offen | offen | offen | offen | FD-297 | offen | FD-251 | FD-288 | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-745 | FD-251, FD-264, FD-288, FD-297 |
| orient_for_print | operation | zwei_koerper.exakt | offen | offen | offen | offen | offen | offen | offen | offen | FD-218 | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-737, RM-745 | FD-101, FD-218 |
| rename_object | operation | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-745 | FD-51, FD-114, FD-116, FD-182, FD-241 |
| set_material | operation | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-745 | FD-116 |
| split_bodies | operation | mehrteilig.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | FD-242 | offen RM-745 | FD-95, FD-113, FD-242 |
| split_line | operation | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | FD-251 | offen | FD-303 | offen | offen | offen | offen | offen | offen | offen | FD-242 | offen RM-745 | FD-242, FD-251, FD-264, FD-303 |
| split_pinned | operation | quader.exakt | offen | offen | offen | offen | offen | FD-229 | offen | offen | offen | offen | offen | offen | offen | FD-229 | offen | offen | offen | offen | offen | offen RM-745 | FD-229 |
| test_piece | operation | merkmal.hole.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen RM-745 | FD-119 |
| command:edit.auto_split | fensterbefehl | zu_gross.netz | offen | offen | offen | offen | offen | offen | offen | offen | FD-251 | offen | FD-286 | offen | offen | offen | offen | offen | — | offen | FD-242 | offen RM-737, RM-745 | FD-56, FD-151, FD-241, FD-242, FD-243, FD-251, FD-286 |
| dialog:body_choice_dialog | bedienflaeche | zwei_unter_dem_bett.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-101 |
| dialog:seal_path_dialog | bedienflaeche | merkmal.face.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-101 |
| dialog:step_values_dialog | bedienflaeche | alter_farbschritt.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-101 |
| finding.action:adopt_printer | bedienflaeche | fremder_drucker.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 |  |
| finding.action:arrange_on_bed | bedienflaeche | deckungsgleich.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 |  |
| finding.action:calibrate_material | bedienflaeche | passung.netz | offen | offen | offen | offen | offen | offen | offen | offen | FD-251 | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-105, FD-251 |
| finding.action:change_creating_step | bedienflaeche | gewinde_zu_kurz.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-99, FD-227 |
| finding.action:change_selection | bedienflaeche | ohne_farbe.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-123, FD-254 |
| finding.action:change_step | bedienflaeche | halt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-253 |
| finding.action:check_updates | bedienflaeche | baustein_fehlt.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-108 |
| finding.action:choose_another_file | bedienflaeche | step_ohne_geometrie.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-122 |
| finding.action:choose_printer | bedienflaeche | zu_gross.netz | offen | offen | offen | offen | offen | offen | offen | FD-244 | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-745 | FD-78, FD-121, FD-244, FD-292 |
| finding.action:correct_input | bedienflaeche | halt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-95, FD-255 |
| finding.action:decimate_and_retry | bedienflaeche | duenner_stab.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-108, FD-252 |
| finding.action:decimate_mesh | bedienflaeche | ueber_erkennungsgrenze | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-107, FD-124 |
| finding.action:export_as_mesh | bedienflaeche | export_gemischt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-53, FD-55, FD-122 |
| finding.action:generate_again | bedienflaeche | erzeugte_haut.netz | offen | offen | offen | offen | offen | offen | offen | FD-245 | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-745 | FD-78, FD-117, FD-245 |
| finding.action:give_thickness | bedienflaeche | offen_gelassen.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-112, FD-256 |
| finding.action:install | bedienflaeche | ohne_opencascade.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-101, FD-257 |
| finding.action:keep_saved_parts | bedienflaeche | baustein_geaendert.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-101, FD-212 |
| finding.action:leave_open | bedienflaeche | offen_repariert.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 |  |
| finding.action:mesh_and_retry | bedienflaeche | kasten_runden.exakt | offen | offen | offen | offen | offen | offen | offen | offen | FD-251 | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-251, FD-258 |
| finding.action:mesh_to_exact | bedienflaeche | schale_am_netz.netz | offen | offen | offen | offen | offen | offen | FD-259 | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-104, FD-259 |
| finding.action:open_print_settings | bedienflaeche | geglaettet.netz | offen | offen | offen | offen | offen | offen | offen | FD-244 | FD-251 | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-745 | FD-78, FD-121, FD-244, FD-251 |
| finding.action:orient_for_print | bedienflaeche | kreuzend.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-97, FD-104, FD-294 |
| finding.action:place_on_bed | bedienflaeche | unter_dem_bett.netz | FD-17 | offen | offen | ja | offen | FD-250 | FD-249 | FD-35 | offen | offen | ja | — | offen | offen | offen | — | — | offen | offen | offen RM-737, RM-745 | FD-4, FD-5, FD-17, FD-18, FD-21, FD-23, FD-25, FD-27, FD-30, FD-35, FD-37, FD-38, FD-40, FD-100, FD-109, FD-128, FD-139, FD-140, FD-147, FD-149, FD-249, FD-250, FD-282 |
| finding.action:reactivate_step | bedienflaeche | ausgeschaltet.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 |  |
| finding.action:recognize_fully | bedienflaeche | ueber_erkennungsgrenze | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-101, FD-252, FD-260 |
| finding.action:recognize_local | bedienflaeche | ueber_erkennungsgrenze | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-111 |
| finding.action:recount_and_retry | bedienflaeche | kreuzend.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 |  |
| finding.action:release_protection | bedienflaeche | geschuetzte_leiste.netz | offen | offen | offen | FD-293 | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-106, FD-252, FD-293 |
| finding.action:remesh_and_retry | bedienflaeche | geglaettet.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-108, FD-111, FD-294 |
| finding.action:remove_small_parts | bedienflaeche | mehrteilig.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-109 |
| finding.action:repair_and_retry | bedienflaeche | offen.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-107 |
| finding.action:repair_before_and_retry | bedienflaeche | zu_fein.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-111 |
| finding.action:resize_the_widening | bedienflaeche | senkung_vergroessern.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-256 |
| finding.action:resolve_intersections | bedienflaeche | kreuzend.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-104, FD-107, FD-108 |
| finding.action:scale_to_fit | bedienflaeche | zu_gross.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-20, FD-111 |
| finding.action:show_details | bedienflaeche | duenne_huelse.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-105 |
| finding.action:show_feature | bedienflaeche | passung_pla.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 |  |
| finding.action:show_history | bedienflaeche | duenne_huelse.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-261 |
| finding.action:show_layers | bedienflaeche | kammer_unlesbar.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-109 |
| finding.action:show_location | bedienflaeche | offen_repariert.netz | offen | FD-295 | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-295 |
| finding.action:show_locations | bedienflaeche | offen.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-262 |
| finding.action:show_step_values | bedienflaeche | alter_farbschritt.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-105, FD-118 |
| finding.action:show_support_need | bedienflaeche | kreuzend.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-108, FD-263 |
| finding.action:sketch.pick_plane | bedienflaeche | ebene_durch_linie.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-745 | FD-44, FD-78, FD-95, FD-182, FD-190 |
| finding.action:split_along_line | bedienflaeche | geschuetzte_leiste.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-106 |
| finding.action:split_and_retry | bedienflaeche | lose_teile.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 |  |
| finding.action:split_bodies | bedienflaeche | kreuzend.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-104 |
| finding.action:split_model | bedienflaeche | zu_gross.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-111, FD-252 |
| finding.action:stop_inserting | bedienflaeche | einfuegen.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 |  |
| finding.action:suppress_step | bedienflaeche | ruhender_eingang.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-108 |
| finding.action:take_back_stroke | bedienflaeche | durchstochen.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 |  |
| finding.action:use_reachable | bedienflaeche | zu_fein.netz | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-108, FD-252 |
| report | bedienflaeche | quader.exakt | offen | offen | offen | offen | offen | offen | FD-206 | offen | FD-221 | FD-209 | FD-289 | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745, RM-812 | FD-177, FD-196, FD-206, FD-209, FD-221, FD-224, FD-231, FD-248, FD-251, FD-289 |
| report.action | bedienflaeche | unter_dem_bett.netz | offen | offen | offen | offen | offen | offen | offen | offen | FD-251 | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-115, FD-185, FD-251 |
| tool:analysis | bedienflaeche | quader.exakt | offen | offen | offen | offen | offen | offen | offen | FD-246 | FD-246 | offen | FD-289 | offen | offen | offen | offen | offen | — | offen | offen | offen RM-745, RM-812 | FD-78, FD-246, FD-247, FD-251, FD-289 |
| tool:layers | bedienflaeche | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | FD-251 | offen | FD-289 | offen | offen | offen | offen | offen | — | offen | offen | offen RM-737, RM-745 | FD-247, FD-251, FD-289, FD-290, FD-300 |
| tool:split | bedienflaeche | quader.exakt | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | offen | — | offen | offen | offen RM-745 | FD-78, FD-120 |

## Kriterien, die nicht erfüllt sind

| Kennung | Kriterium | Messwert | Schwelle | Fund |
|---|---|---|---|---|
| arrange_bed | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| arrange_bed | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| arrange_bed | E3 | nicht gemessen | ≤ 1 | — |
| arrange_bed | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| arrange_bed | E5 | 3 Felder, 7 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| arrange_bed | E6 | nicht gemessen | 0 | — |
| arrange_bed | E7 | nicht gemessen | 0 | — |
| arrange_bed | V1 | 0 Treffer | 0 | — |
| arrange_bed | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| arrange_bed | V3 | 4 von 4 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| arrange_bed | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| arrange_bed | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| arrange_bed | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| arrange_bed | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| arrange_bed | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| check_collisions | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| check_collisions | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| check_collisions | E3 | nicht gemessen | ≤ 1 | — |
| check_collisions | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| check_collisions | E5 | 1 Felder, 8 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| check_collisions | E6 | nicht gemessen | 0 | — |
| check_collisions | E7 | nicht gemessen | 0 | — |
| check_collisions | V1 | 0 Treffer | 0 | — |
| check_collisions | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| check_collisions | V3 | 1 von 1 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| check_collisions | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| check_collisions | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| check_collisions | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| check_collisions | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| check_collisions | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| check_join_path | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| check_join_path | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| check_join_path | E3 | nicht gemessen | ≤ 1 | — |
| check_join_path | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| check_join_path | E6 | nicht gemessen | 0 | — |
| check_join_path | E7 | nicht gemessen | 0 | — |
| check_join_path | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| check_join_path | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| check_join_path | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| check_join_path | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| compensate_first_layer | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| compensate_first_layer | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| compensate_first_layer | E3 | nicht gemessen | ≤ 1 | — |
| compensate_first_layer | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| compensate_first_layer | E6 | nicht gemessen | 0 | — |
| compensate_first_layer | E7 | nicht gemessen | 0 | — |
| compensate_first_layer | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| compensate_first_layer | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| compensate_first_layer | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| compensate_first_layer | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| compensate_first_layer | Z3 | Wegklick nach der Auswahl: reiter auf operation:compensate_first_layer; Wegklick nach der Auswahl: rollen auf operation:compensate_first_layer | ja je Zeile mit Merkmals- oder Körperbezug | — |
| create_seal | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| create_seal | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| create_seal | E3 | nicht gemessen | ≤ 1 | — |
| create_seal | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| create_seal | E6 | nicht gemessen | 0 | — |
| create_seal | E7 | nicht gemessen | 0 | — |
| create_seal | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| create_seal | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| create_seal | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| create_seal | G5 | nicht gemessen | jeder unterscheidbar, zweite Kodierung, Fokus sichtbar | — |
| create_seal | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| create_seal | Z2 | nicht gemessen | kein modales Fenster außer den Ausnahmen | — |
| create_seal | Z5 | nicht gemessen | 0, außer `QFileDialog` | — |
| create_seal | Z6 | nicht gemessen | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| cut_away | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| cut_away | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| cut_away | E3 | nicht gemessen | ≤ 1 | — |
| cut_away | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| cut_away | E6 | nicht gemessen | 0 | — |
| cut_away | E7 | nicht gemessen | 0 | — |
| cut_away | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| cut_away | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| cut_away | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| cut_away | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| cut_away | Z3 | Wegklick nach der Auswahl: reiter auf operation:cut_away; Wegklick nach der Auswahl: rollen auf operation:cut_away | ja je Zeile mit Merkmals- oder Körperbezug | — |
| delete_object | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| delete_object | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| delete_object | E3 | nicht gemessen | ≤ 1 | — |
| delete_object | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| delete_object | E5 | 34 Wörter über dem ersten Feld, erlaubt 25; 38 Wörter über dem ersten Feld, erlaubt 35; 42 Wörter über dem ersten Feld, erlaubt 35; 37 Wörter über dem ersten Feld, erlaubt 35 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | FD-243 |
| delete_object | E6 | nicht gemessen | 0 | — |
| delete_object | E7 | nicht gemessen | 0 | — |
| delete_object | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| delete_object | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| delete_object | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| delete_object | Z6 | Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369 | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| duplicate_object | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| duplicate_object | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| duplicate_object | E3 | nicht gemessen | ≤ 1 | — |
| duplicate_object | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| duplicate_object | E6 | nicht gemessen | 0 | — |
| duplicate_object | E7 | nicht gemessen | 0 | — |
| duplicate_object | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| duplicate_object | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| duplicate_object | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| duplicate_object | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| hollow_object | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| hollow_object | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| hollow_object | E3 | nicht gemessen | ≤ 1 | — |
| hollow_object | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| hollow_object | E6 | nicht gemessen | 0 | — |
| hollow_object | E7 | nicht gemessen | 0 | — |
| hollow_object | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| hollow_object | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| hollow_object | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| hollow_object | G5 | nicht gemessen | jeder unterscheidbar, zweite Kodierung, Fokus sichtbar | — |
| hollow_object | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| hollow_object | Z2 | nicht gemessen | kein modales Fenster außer den Ausnahmen | — |
| hollow_object | Z5 | nicht gemessen | 0, außer `QFileDialog` | — |
| hollow_object | Z6 | nicht gemessen | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| orient_for_print | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| orient_for_print | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| orient_for_print | E3 | nicht gemessen | ≤ 1 | — |
| orient_for_print | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| orient_for_print | E5 | nicht gemessen | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| orient_for_print | E6 | nicht gemessen | 0 | — |
| orient_for_print | E7 | nicht gemessen | 0 | — |
| orient_for_print | V1 | nicht gemessen | 0 | — |
| orient_for_print | V2 | nicht gemessen | die Grenzen aus `test_text_length` | — |
| orient_for_print | V3 | nicht gemessen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| orient_for_print | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| orient_for_print | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| orient_for_print | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| orient_for_print | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| orient_for_print | Z4 | nicht gemessen | Knopf zur nächsten Handlung | — |
| rename_object | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| rename_object | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| rename_object | E3 | nicht gemessen | ≤ 1 | — |
| rename_object | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| rename_object | E6 | nicht gemessen | 0 | — |
| rename_object | E7 | nicht gemessen | 0 | — |
| rename_object | V1 | 0 Treffer | 0 | — |
| rename_object | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| rename_object | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| rename_object | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| rename_object | Z3 | Wegklick nach der Auswahl: reiter auf operation:rename_object | ja je Zeile mit Merkmals- oder Körperbezug | FD-241 |
| set_material | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| set_material | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| set_material | E3 | nicht gemessen | ≤ 1 | — |
| set_material | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| set_material | E6 | nicht gemessen | 0 | — |
| set_material | E7 | nicht gemessen | 0 | — |
| set_material | V1 | 0 Treffer | 0 | — |
| set_material | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| set_material | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| set_material | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| set_material | Z3 | Wegklick nach der Auswahl: reiter auf operation:set_material; Wegklick nach der Auswahl: rollen auf operation:set_material | ja je Zeile mit Merkmals- oder Körperbezug | — |
| split_bodies | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| split_bodies | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| split_bodies | E3 | nicht gemessen | ≤ 1 | — |
| split_bodies | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| split_bodies | E6 | nicht gemessen | 0 | — |
| split_bodies | E7 | nicht gemessen | 0 | — |
| split_bodies | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| split_bodies | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| split_bodies | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| split_bodies | Z3 | Wegklick nach der Auswahl: rollen auf operation:split_bodies | ja je Zeile mit Merkmals- oder Körperbezug | FD-242 |
| split_line | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| split_line | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| split_line | E3 | nicht gemessen | ≤ 1 | — |
| split_line | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| split_line | E6 | nicht gemessen | 0 | — |
| split_line | E7 | nicht gemessen | 0 | — |
| split_line | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| split_line | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| split_line | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| split_line | G5 | nicht gemessen | jeder unterscheidbar, zweite Kodierung, Fokus sichtbar | — |
| split_line | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| split_line | Z2 | nicht gemessen | kein modales Fenster außer den Ausnahmen | — |
| split_line | Z3 | Wegklick nach der Auswahl: rollen auf operation:split_line | ja je Zeile mit Merkmals- oder Körperbezug | FD-242 |
| split_line | Z5 | nicht gemessen | 0, außer `QFileDialog` | — |
| split_line | Z6 | nicht gemessen | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | FD-242 |
| split_pinned | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| split_pinned | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| split_pinned | E3 | nicht gemessen | ≤ 1 | — |
| split_pinned | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| split_pinned | E6 | nicht gemessen | 0 | — |
| split_pinned | E7 | nicht gemessen | 0 | — |
| split_pinned | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| split_pinned | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| split_pinned | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| split_pinned | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| test_piece | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| test_piece | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| test_piece | E3 | nicht gemessen | ≤ 1 | — |
| test_piece | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| test_piece | E6 | nicht gemessen | 0 | — |
| test_piece | E7 | nicht gemessen | 0 | — |
| test_piece | V1 | 0 Treffer | 0 | — |
| test_piece | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| test_piece | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| test_piece | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| test_piece | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| command:edit.auto_split | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| command:edit.auto_split | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| command:edit.auto_split | E3 | nicht gemessen | ≤ 1 | — |
| command:edit.auto_split | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| command:edit.auto_split | E5 | 34 Wörter über dem ersten Feld, erlaubt 25; 38 Wörter über dem ersten Feld, erlaubt 35; 42 Wörter über dem ersten Feld, erlaubt 35; 37 Wörter über dem ersten Feld, erlaubt 35 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | FD-243 |
| command:edit.auto_split | E6 | nicht gemessen | 0 | — |
| command:edit.auto_split | E7 | nicht gemessen | 0 | — |
| command:edit.auto_split | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| command:edit.auto_split | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| command:edit.auto_split | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| command:edit.auto_split | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| command:edit.auto_split | G5 | nicht gemessen | jeder unterscheidbar, zweite Kodierung, Fokus sichtbar | — |
| command:edit.auto_split | G6 | nicht gemessen | ≥ 4.5:1, große Schrift und Symbole ≥ 3:1 | — |
| command:edit.auto_split | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| command:edit.auto_split | Z2 | nicht gemessen | kein modales Fenster außer den Ausnahmen | — |
| command:edit.auto_split | Z3 | Wegklick nach der Auswahl: reiter auf command:edit.auto_split; Wegklick nach der Auswahl: rollen auf command:edit.auto_split | ja je Zeile mit Merkmals- oder Körperbezug | FD-241 |
| command:edit.auto_split | Z5 | nicht gemessen | 0, außer `QFileDialog` | — |
| command:edit.auto_split | Z6 | Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369; Rollleiste vorn in _SelectionPage bei 2560 x 1369 | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | FD-242 |
| dialog:body_choice_dialog | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| dialog:body_choice_dialog | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| dialog:body_choice_dialog | E3 | nicht gemessen | ≤ 1 | — |
| dialog:body_choice_dialog | E4 | 1 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| dialog:body_choice_dialog | E5 | 1 Felder, 6 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| dialog:body_choice_dialog | E6 | nicht gemessen | 0 | — |
| dialog:body_choice_dialog | E7 | nicht gemessen | 0 | — |
| dialog:body_choice_dialog | V1 | 0 Treffer | 0 | — |
| dialog:body_choice_dialog | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| dialog:body_choice_dialog | V3 | Feld „Alle auswählen“ ohne Kurzhilfe; Feld „Alle auswählen“ ohne Beschreibung; Feld „Select all“ ohne Kurzhilfe; Feld „Select all“ ohne Beschreibung; Feld „Seleccionar todos“ ohne Kurzhilfe; Feld „Seleccionar todos“ ohne Beschreibung; Feld „Tout sélectionner“ ohne Kurzhilfe; Feld „Tout sélectionner“ ohne Beschreibung; Feld „Seleziona tutti“ ohne Kurzhilfe; Feld „Seleziona tutti“ ohne Beschreibung; Feld „Selecionar todos“ ohne Kurzhilfe; Feld „Selecionar todos“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| dialog:body_choice_dialog | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| dialog:body_choice_dialog | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| dialog:body_choice_dialog | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| dialog:body_choice_dialog | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| dialog:body_choice_dialog | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| dialog:seal_path_dialog | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| dialog:seal_path_dialog | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| dialog:seal_path_dialog | E3 | nicht gemessen | ≤ 1 | — |
| dialog:seal_path_dialog | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| dialog:seal_path_dialog | E5 | 3 Felder, 0 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| dialog:seal_path_dialog | E6 | nicht gemessen | 0 | — |
| dialog:seal_path_dialog | E7 | nicht gemessen | 0 | — |
| dialog:seal_path_dialog | V1 | 0 Treffer | 0 | — |
| dialog:seal_path_dialog | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| dialog:seal_path_dialog | V3 | Feld „Dichtweg aus“ ohne Kurzhilfe; Feld „Dichtweg aus“ ohne Beschreibung; Feld „Trägerfläche“ ohne Kurzhilfe; Feld „Trägerfläche“ ohne Beschreibung; Feld „Gegenfläche“ ohne Kurzhilfe; Feld „Gegenfläche“ ohne Beschreibung; Feld „Seal path from“ ohne Kurzhilfe; Feld „Seal path from“ ohne Beschreibung; Feld „Supporting face“ ohne Kurzhilfe; Feld „Supporting face“ ohne Beschreibung; Feld „Mating face“ ohne Kurzhilfe; Feld „Mating face“ ohne Beschreibung; Feld „Recorrido de sellado a partir de“ ohne Kurzhilfe; Feld „Recorrido de sellado a partir de“ ohne Beschreibung; Feld „Cara de soporte“ ohne Kurzhilfe; Feld „Cara de soporte“ ohne Beschreibung; Feld „Cara opuesta“ ohne Kurzhilfe; Feld „Cara opuesta“ ohne Beschreibung; Feld „Tracé du joint à partir de“ ohne Kurzhilfe; Feld „Tracé du joint à partir de“ ohne Beschreibung; Feld „Face porteuse“ ohne Kurzhilfe; Feld „Face porteuse“ ohne Beschreibung; Feld „Face en regard“ ohne Kurzhilfe; Feld „Face en regard“ ohne Beschreibung; Feld „Percorso guarnizione da“ ohne Kurzhilfe; Feld „Percorso guarnizione da“ ohne Beschreibung; Feld „Faccia di supporto“ ohne Kurzhilfe; Feld „Faccia di supporto“ ohne Beschreibung; Feld „Faccia contrapposta“ ohne Kurzhilfe; Feld „Faccia contrapposta“ ohne Beschreibung; Feld „Percurso da vedação a partir de“ ohne Kurzhilfe; Feld „Percurso da vedação a partir de“ ohne Beschreibung; Feld „Face de suporte“ ohne Kurzhilfe; Feld „Face de suporte“ ohne Beschreibung; Feld „Face oposta“ ohne Kurzhilfe; Feld „Face oposta“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| dialog:seal_path_dialog | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| dialog:seal_path_dialog | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| dialog:seal_path_dialog | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| dialog:seal_path_dialog | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| dialog:seal_path_dialog | Z3 | 0 Wegklicks | ja je Zeile mit Merkmals- oder Körperbezug | — |
| dialog:seal_path_dialog | Z4 | 1 leere Zustände | Knopf zur nächsten Handlung | — |
| dialog:step_values_dialog | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| dialog:step_values_dialog | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| dialog:step_values_dialog | E3 | nicht gemessen | ≤ 1 | — |
| dialog:step_values_dialog | E4 | 1 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| dialog:step_values_dialog | E5 | 1 Felder, 23 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| dialog:step_values_dialog | E6 | nicht gemessen | 0 | — |
| dialog:step_values_dialog | E7 | nicht gemessen | 0 | — |
| dialog:step_values_dialog | V1 | 0 Treffer | 0 | — |
| dialog:step_values_dialog | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| dialog:step_values_dialog | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| dialog:step_values_dialog | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| dialog:step_values_dialog | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| dialog:step_values_dialog | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| dialog:step_values_dialog | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| dialog:step_values_dialog | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| finding.action:adopt_printer | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:adopt_printer | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:adopt_printer | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:adopt_printer | E6 | nicht gemessen | 0 | — |
| finding.action:adopt_printer | E7 | nicht gemessen | 0 | — |
| finding.action:adopt_printer | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:adopt_printer | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:adopt_printer | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:arrange_on_bed | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:arrange_on_bed | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:arrange_on_bed | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:arrange_on_bed | E6 | nicht gemessen | 0 | — |
| finding.action:arrange_on_bed | E7 | nicht gemessen | 0 | — |
| finding.action:arrange_on_bed | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:arrange_on_bed | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:arrange_on_bed | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:arrange_on_bed | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:calibrate_material | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:calibrate_material | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:calibrate_material | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:calibrate_material | E6 | nicht gemessen | 0 | — |
| finding.action:calibrate_material | E7 | nicht gemessen | 0 | — |
| finding.action:calibrate_material | V1 | „Startwert“ in „Die Toleranzen dieses Materials sind Startwerte. Passen Sie sie anhand eines gedruckten Toleranz-Testkörpers in der Materialkalibrierung an.“ | 0 | — |
| finding.action:calibrate_material | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:calibrate_material | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:calibrate_material | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:change_creating_step | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:change_creating_step | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:change_creating_step | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:change_creating_step | E6 | nicht gemessen | 0 | — |
| finding.action:change_creating_step | E7 | nicht gemessen | 0 | — |
| finding.action:change_creating_step | V1 | „Startwert“ in „Die Toleranzen dieses Materials sind Startwerte.“ | 0 | — |
| finding.action:change_creating_step | V3 | Feld „Distance to the first edge“: Kurzhilfe wiederholt den Titel („Distance to the first selected reference edge on the face.“); Feld „Distance to the first edge“: Beschreibung wiederholt den Titel („Distance to the first selected reference edge on the face.“); Feld „Distance to the second edge“: Kurzhilfe wiederholt den Titel („Distance to the second selected reference edge on the face.“); Feld „Distance to the second edge“: Beschreibung wiederholt den Titel („Distance to the second selected reference edge on the face.“) | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:change_creating_step | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| finding.action:change_creating_step | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:change_creating_step | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:change_creating_step | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:change_selection | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:change_selection | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:change_selection | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:change_selection | E6 | nicht gemessen | 0 | — |
| finding.action:change_selection | E7 | nicht gemessen | 0 | — |
| finding.action:change_selection | V1 | 0 Treffer | 0 | — |
| finding.action:change_selection | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:change_selection | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-254 |
| finding.action:change_selection | V5 | nicht gemessen | jede Handlung löst das Problem | FD-254 |
| finding.action:change_selection | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:change_step | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:change_step | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:change_step | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:change_step | E6 | nicht gemessen | 0 | — |
| finding.action:change_step | E7 | nicht gemessen | 0 | — |
| finding.action:change_step | V1 | 0 Treffer | 0 | — |
| finding.action:change_step | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:change_step | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-253 |
| finding.action:change_step | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:change_step | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:change_step | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:check_updates | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:check_updates | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:check_updates | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:check_updates | E6 | nicht gemessen | 0 | — |
| finding.action:check_updates | E7 | nicht gemessen | 0 | — |
| finding.action:check_updates | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:check_updates | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:check_updates | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:choose_another_file | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:choose_another_file | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:choose_another_file | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:choose_another_file | E6 | nicht gemessen | 0 | — |
| finding.action:choose_another_file | E7 | nicht gemessen | 0 | — |
| finding.action:choose_another_file | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:choose_another_file | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:choose_another_file | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:choose_printer | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:choose_printer | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:choose_printer | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:choose_printer | E5 | 6 Felder vorn, erlaubt 4 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| finding.action:choose_printer | E6 | nicht gemessen | 0 | — |
| finding.action:choose_printer | E7 | nicht gemessen | 0 | — |
| finding.action:choose_printer | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung; Feld „Platte“ ohne Kurzhilfe; Feld „Platte“ ohne Beschreibung; Feld „Qualität“ ohne Kurzhilfe; Feld „Qualität“ ohne Beschreibung; Feld „Plate“ ohne Kurzhilfe; Feld „Plate“ ohne Beschreibung; Feld „Quality“ ohne Kurzhilfe; Feld „Quality“ ohne Beschreibung; Feld „Placa“ ohne Kurzhilfe; Feld „Placa“ ohne Beschreibung; Feld „Calidad“ ohne Kurzhilfe; Feld „Calidad“ ohne Beschreibung; Feld „Plaque“ ohne Kurzhilfe; Feld „Plaque“ ohne Beschreibung; Feld „Qualité“ ohne Kurzhilfe; Feld „Qualité“ ohne Beschreibung; Feld „Piatto“ ohne Kurzhilfe; Feld „Piatto“ ohne Beschreibung; Feld „Qualità“ ohne Kurzhilfe; Feld „Qualità“ ohne Beschreibung; Feld „Qualidade“ ohne Kurzhilfe; Feld „Qualidade“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | FD-244 |
| finding.action:choose_printer | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:choose_printer | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:correct_input | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:correct_input | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:correct_input | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:correct_input | E6 | nicht gemessen | 0 | — |
| finding.action:correct_input | E7 | nicht gemessen | 0 | — |
| finding.action:correct_input | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:correct_input | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-255 |
| finding.action:correct_input | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:correct_input | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:correct_input | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:decimate_and_retry | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:decimate_and_retry | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:decimate_and_retry | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:decimate_and_retry | E6 | nicht gemessen | 0 | — |
| finding.action:decimate_and_retry | E7 | nicht gemessen | 0 | — |
| finding.action:decimate_and_retry | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:decimate_and_retry | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-252 |
| finding.action:decimate_and_retry | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:decimate_and_retry | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:decimate_mesh | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:decimate_mesh | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:decimate_mesh | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:decimate_mesh | E6 | nicht gemessen | 0 | — |
| finding.action:decimate_mesh | E7 | nicht gemessen | 0 | — |
| finding.action:decimate_mesh | V1 | 0 Treffer | 0 | — |
| finding.action:decimate_mesh | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:decimate_mesh | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:decimate_mesh | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:export_as_mesh | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:export_as_mesh | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:export_as_mesh | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:export_as_mesh | E6 | nicht gemessen | 0 | — |
| finding.action:export_as_mesh | E7 | nicht gemessen | 0 | — |
| finding.action:export_as_mesh | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:export_as_mesh | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:export_as_mesh | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:generate_again | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:generate_again | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:generate_again | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:generate_again | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| finding.action:generate_again | E6 | nicht gemessen | 0 | — |
| finding.action:generate_again | E7 | nicht gemessen | 0 | — |
| finding.action:generate_again | V1 | „Startwert“ in „Startwert und Modell“ | 0 | — |
| finding.action:generate_again | V3 | Feld „Startwert“ ohne Beschreibung; Feld „Seed“ ohne Beschreibung; Feld „Semilla“ ohne Beschreibung; Feld „Graine“ ohne Beschreibung; Feld „Seme“ ohne Beschreibung; Feld „Semente“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | FD-245 |
| finding.action:generate_again | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:generate_again | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:generate_again | G3 | Felder in GenerateDialog nicht bündig: [0.0, 80.0]; Felder in GenerateDialog nicht bündig: [0.0, 68.0]; Felder in GenerateDialog nicht bündig: [0.0, 70.0]; Felder in GenerateDialog nicht bündig: [0.0, 59.0] | bündig; Werte rechtsbündig mit Einheit | — |
| finding.action:generate_again | G8 | Übergang -1 ms an QProgressBar, erlaubt 110 bis 220 | Übergang aus `motion`, 110-220 ms, abschaltbar | — |
| finding.action:give_thickness | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:give_thickness | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:give_thickness | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:give_thickness | E6 | nicht gemessen | 0 | — |
| finding.action:give_thickness | E7 | nicht gemessen | 0 | — |
| finding.action:give_thickness | V1 | 0 Treffer | 0 | — |
| finding.action:give_thickness | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:give_thickness | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-256 |
| finding.action:give_thickness | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:give_thickness | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:give_thickness | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:install | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:install | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:install | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:install | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| finding.action:install | E5 | 0 Felder, 0 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| finding.action:install | E6 | nicht gemessen | 0 | — |
| finding.action:install | E7 | nicht gemessen | 0 | — |
| finding.action:install | V1 | 0 Treffer | 0 | — |
| finding.action:install | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| finding.action:install | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:install | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-257 |
| finding.action:install | V5 | nicht gemessen | jede Handlung löst das Problem | FD-257 |
| finding.action:install | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:install | G8 | Übergang -1 ms an QProgressBar, erlaubt 110 bis 220 | Übergang aus `motion`, 110-220 ms, abschaltbar | — |
| finding.action:install | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:install | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| finding.action:keep_saved_parts | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:keep_saved_parts | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:keep_saved_parts | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:keep_saved_parts | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| finding.action:keep_saved_parts | E5 | 0 Felder, 0 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| finding.action:keep_saved_parts | E6 | nicht gemessen | 0 | — |
| finding.action:keep_saved_parts | E7 | nicht gemessen | 0 | — |
| finding.action:keep_saved_parts | V1 | 0 Treffer | 0 | — |
| finding.action:keep_saved_parts | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| finding.action:keep_saved_parts | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:keep_saved_parts | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:keep_saved_parts | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:keep_saved_parts | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:keep_saved_parts | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| finding.action:leave_open | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:leave_open | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:leave_open | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:leave_open | E6 | nicht gemessen | 0 | — |
| finding.action:leave_open | E7 | nicht gemessen | 0 | — |
| finding.action:leave_open | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:leave_open | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:leave_open | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:mesh_and_retry | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:mesh_and_retry | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:mesh_and_retry | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:mesh_and_retry | E6 | nicht gemessen | 0 | — |
| finding.action:mesh_and_retry | E7 | nicht gemessen | 0 | — |
| finding.action:mesh_and_retry | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:mesh_and_retry | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-258 |
| finding.action:mesh_and_retry | V5 | nicht gemessen | jede Handlung löst das Problem | FD-258 |
| finding.action:mesh_and_retry | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:mesh_to_exact | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:mesh_to_exact | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:mesh_to_exact | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:mesh_to_exact | E6 | nicht gemessen | 0 | — |
| finding.action:mesh_to_exact | E7 | nicht gemessen | 0 | — |
| finding.action:mesh_to_exact | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:mesh_to_exact | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-259 |
| finding.action:mesh_to_exact | V5 | nicht gemessen | jede Handlung löst das Problem | FD-259 |
| finding.action:mesh_to_exact | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:open_print_settings | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:open_print_settings | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:open_print_settings | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:open_print_settings | E5 | 6 Felder vorn, erlaubt 4 | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| finding.action:open_print_settings | E6 | nicht gemessen | 0 | — |
| finding.action:open_print_settings | E7 | nicht gemessen | 0 | — |
| finding.action:open_print_settings | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung; Feld „Platte“ ohne Kurzhilfe; Feld „Platte“ ohne Beschreibung; Feld „Qualität“ ohne Kurzhilfe; Feld „Qualität“ ohne Beschreibung; Feld „Plate“ ohne Kurzhilfe; Feld „Plate“ ohne Beschreibung; Feld „Quality“ ohne Kurzhilfe; Feld „Quality“ ohne Beschreibung; Feld „Placa“ ohne Kurzhilfe; Feld „Placa“ ohne Beschreibung; Feld „Calidad“ ohne Kurzhilfe; Feld „Calidad“ ohne Beschreibung; Feld „Plaque“ ohne Kurzhilfe; Feld „Plaque“ ohne Beschreibung; Feld „Qualité“ ohne Kurzhilfe; Feld „Qualité“ ohne Beschreibung; Feld „Piatto“ ohne Kurzhilfe; Feld „Piatto“ ohne Beschreibung; Feld „Qualità“ ohne Kurzhilfe; Feld „Qualità“ ohne Beschreibung; Feld „Qualidade“ ohne Kurzhilfe; Feld „Qualidade“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | FD-244 |
| finding.action:open_print_settings | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:open_print_settings | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:orient_for_print | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:orient_for_print | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:orient_for_print | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:orient_for_print | E6 | nicht gemessen | 0 | — |
| finding.action:orient_for_print | E7 | nicht gemessen | 0 | — |
| finding.action:orient_for_print | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:orient_for_print | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| finding.action:orient_for_print | V5 | nicht gemessen | jede Handlung löst das Problem | FD-294 |
| finding.action:orient_for_print | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:orient_for_print | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:place_on_bed | E4 | Stelle nach dem Ergebnis außerhalb des Bildes | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| finding.action:place_on_bed | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:place_on_bed | G5 | nicht gemessen | jeder unterscheidbar, zweite Kodierung, Fokus sichtbar | — |
| finding.action:place_on_bed | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:place_on_bed | Z6 | 24 Flächen | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | FD-282 |
| finding.action:reactivate_step | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:reactivate_step | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:reactivate_step | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:reactivate_step | E6 | nicht gemessen | 0 | — |
| finding.action:reactivate_step | E7 | nicht gemessen | 0 | — |
| finding.action:reactivate_step | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:reactivate_step | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:reactivate_step | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:recognize_fully | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:recognize_fully | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:recognize_fully | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:recognize_fully | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| finding.action:recognize_fully | E5 | 0 Felder, 0 Wörter | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 | — |
| finding.action:recognize_fully | E6 | nicht gemessen | 0 | FD-260 |
| finding.action:recognize_fully | E7 | nicht gemessen | 0 | — |
| finding.action:recognize_fully | V1 | 0 Treffer | 0 | — |
| finding.action:recognize_fully | V2 | 0 zu lange Texte | die Grenzen aus `test_text_length` | — |
| finding.action:recognize_fully | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:recognize_fully | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-252 |
| finding.action:recognize_fully | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:recognize_fully | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:recognize_fully | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:recognize_fully | Z4 | kein leerer Zustand | Knopf zur nächsten Handlung | — |
| finding.action:recognize_local | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:recognize_local | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:recognize_local | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:recognize_local | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| finding.action:recognize_local | E6 | nicht gemessen | 0 | — |
| finding.action:recognize_local | E7 | nicht gemessen | 0 | — |
| finding.action:recognize_local | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:recognize_local | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:recognize_local | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:recount_and_retry | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:recount_and_retry | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:recount_and_retry | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:recount_and_retry | E6 | nicht gemessen | 0 | — |
| finding.action:recount_and_retry | E7 | nicht gemessen | 0 | — |
| finding.action:recount_and_retry | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:recount_and_retry | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| finding.action:recount_and_retry | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:recount_and_retry | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:release_protection | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:release_protection | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:release_protection | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:release_protection | E6 | nicht gemessen | 0 | — |
| finding.action:release_protection | E7 | nicht gemessen | 0 | — |
| finding.action:release_protection | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:release_protection | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-252 |
| finding.action:release_protection | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:release_protection | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:remesh_and_retry | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:remesh_and_retry | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:remesh_and_retry | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:remesh_and_retry | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| finding.action:remesh_and_retry | E6 | nicht gemessen | 0 | — |
| finding.action:remesh_and_retry | E7 | nicht gemessen | 0 | — |
| finding.action:remesh_and_retry | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:remesh_and_retry | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| finding.action:remesh_and_retry | V5 | nicht gemessen | jede Handlung löst das Problem | FD-294 |
| finding.action:remesh_and_retry | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:remove_small_parts | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:remove_small_parts | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:remove_small_parts | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:remove_small_parts | E6 | nicht gemessen | 0 | — |
| finding.action:remove_small_parts | E7 | nicht gemessen | 0 | — |
| finding.action:remove_small_parts | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:remove_small_parts | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:remove_small_parts | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:repair_and_retry | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:repair_and_retry | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:repair_and_retry | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:repair_and_retry | E6 | nicht gemessen | 0 | — |
| finding.action:repair_and_retry | E7 | nicht gemessen | 0 | — |
| finding.action:repair_and_retry | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:repair_and_retry | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:repair_and_retry | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:repair_before_and_retry | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:repair_before_and_retry | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:repair_before_and_retry | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:repair_before_and_retry | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| finding.action:repair_before_and_retry | E6 | nicht gemessen | 0 | — |
| finding.action:repair_before_and_retry | E7 | nicht gemessen | 0 | — |
| finding.action:repair_before_and_retry | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:repair_before_and_retry | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:repair_before_and_retry | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:resize_the_widening | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:resize_the_widening | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:resize_the_widening | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:resize_the_widening | E6 | nicht gemessen | 0 | — |
| finding.action:resize_the_widening | E7 | nicht gemessen | 0 | — |
| finding.action:resize_the_widening | V1 | 0 Treffer | 0 | — |
| finding.action:resize_the_widening | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:resize_the_widening | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-256 |
| finding.action:resize_the_widening | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:resize_the_widening | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:resize_the_widening | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:resolve_intersections | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:resolve_intersections | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:resolve_intersections | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:resolve_intersections | E6 | nicht gemessen | 0 | — |
| finding.action:resolve_intersections | E7 | nicht gemessen | 0 | — |
| finding.action:resolve_intersections | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:resolve_intersections | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| finding.action:resolve_intersections | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:resolve_intersections | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:scale_to_fit | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:scale_to_fit | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:scale_to_fit | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:scale_to_fit | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| finding.action:scale_to_fit | E6 | nicht gemessen | 0 | — |
| finding.action:scale_to_fit | E7 | nicht gemessen | 0 | — |
| finding.action:scale_to_fit | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:scale_to_fit | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:scale_to_fit | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:scale_to_fit | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:show_details | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:show_details | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:show_details | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:show_details | E6 | nicht gemessen | 0 | — |
| finding.action:show_details | E7 | nicht gemessen | 0 | — |
| finding.action:show_details | V1 | 0 Treffer | 0 | — |
| finding.action:show_details | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:show_details | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| finding.action:show_details | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:show_details | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:show_feature | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:show_feature | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:show_feature | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:show_feature | E6 | nicht gemessen | 0 | — |
| finding.action:show_feature | E7 | nicht gemessen | 0 | — |
| finding.action:show_feature | V1 | „Startwert“ in „Die Toleranzen dieses Materials sind Startwerte.“ | 0 | — |
| finding.action:show_feature | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:show_feature | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:show_feature | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:show_history | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:show_history | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:show_history | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:show_history | E6 | nicht gemessen | 0 | — |
| finding.action:show_history | E7 | nicht gemessen | 0 | — |
| finding.action:show_history | V1 | 0 Treffer | 0 | — |
| finding.action:show_history | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:show_history | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-261 |
| finding.action:show_history | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:show_history | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:show_layers | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:show_layers | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:show_layers | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:show_layers | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| finding.action:show_layers | E6 | nicht gemessen | 0 | — |
| finding.action:show_layers | E7 | nicht gemessen | 0 | — |
| finding.action:show_layers | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:show_layers | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:show_layers | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:show_location | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:show_location | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:show_location | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:show_location | E6 | nicht gemessen | 0 | — |
| finding.action:show_location | E7 | nicht gemessen | 0 | — |
| finding.action:show_location | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:show_location | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:show_location | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:show_locations | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:show_locations | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:show_locations | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:show_locations | E6 | nicht gemessen | 0 | — |
| finding.action:show_locations | E7 | nicht gemessen | 0 | — |
| finding.action:show_locations | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:show_locations | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-262 |
| finding.action:show_locations | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:show_locations | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:show_step_values | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:show_step_values | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:show_step_values | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:show_step_values | E6 | nicht gemessen | 0 | — |
| finding.action:show_step_values | E7 | nicht gemessen | 0 | — |
| finding.action:show_step_values | V1 | 0 Treffer | 0 | — |
| finding.action:show_step_values | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:show_step_values | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:show_step_values | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:show_support_need | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:show_support_need | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:show_support_need | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:show_support_need | E6 | nicht gemessen | 0 | — |
| finding.action:show_support_need | E7 | nicht gemessen | 0 | — |
| finding.action:show_support_need | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:show_support_need | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-263 |
| finding.action:show_support_need | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:show_support_need | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:sketch.pick_plane | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:sketch.pick_plane | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:sketch.pick_plane | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:sketch.pick_plane | E6 | nicht gemessen | 0 | — |
| finding.action:sketch.pick_plane | E7 | nicht gemessen | 0 | — |
| finding.action:sketch.pick_plane | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:sketch.pick_plane | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:sketch.pick_plane | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:split_along_line | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:split_along_line | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:split_along_line | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:split_along_line | E6 | nicht gemessen | 0 | — |
| finding.action:split_along_line | E7 | nicht gemessen | 0 | — |
| finding.action:split_along_line | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:split_along_line | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:split_along_line | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:split_along_line | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:split_and_retry | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:split_and_retry | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:split_and_retry | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:split_and_retry | E6 | nicht gemessen | 0 | — |
| finding.action:split_and_retry | E7 | nicht gemessen | 0 | — |
| finding.action:split_and_retry | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:split_and_retry | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:split_and_retry | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:split_bodies | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:split_bodies | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:split_bodies | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:split_bodies | E6 | nicht gemessen | 0 | — |
| finding.action:split_bodies | E7 | nicht gemessen | 0 | — |
| finding.action:split_bodies | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:split_bodies | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| finding.action:split_bodies | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:split_bodies | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:split_model | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:split_model | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:split_model | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:split_model | E4 | 0 Blickwechsel | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| finding.action:split_model | E6 | nicht gemessen | 0 | — |
| finding.action:split_model | E7 | nicht gemessen | 0 | — |
| finding.action:split_model | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:split_model | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-252 |
| finding.action:split_model | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:split_model | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:split_model | G9 | Gestaltungsurteil | Gestaltungsurteil, höchstens leicht | — |
| finding.action:stop_inserting | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:stop_inserting | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:stop_inserting | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:stop_inserting | E6 | nicht gemessen | 0 | — |
| finding.action:stop_inserting | E7 | nicht gemessen | 0 | — |
| finding.action:stop_inserting | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:stop_inserting | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:stop_inserting | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:suppress_step | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:suppress_step | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:suppress_step | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:suppress_step | E6 | nicht gemessen | 0 | — |
| finding.action:suppress_step | E7 | nicht gemessen | 0 | — |
| finding.action:suppress_step | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:suppress_step | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:suppress_step | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:take_back_stroke | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:take_back_stroke | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:take_back_stroke | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:take_back_stroke | E6 | nicht gemessen | 0 | — |
| finding.action:take_back_stroke | E7 | nicht gemessen | 0 | — |
| finding.action:take_back_stroke | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:take_back_stroke | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:take_back_stroke | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| finding.action:use_reachable | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| finding.action:use_reachable | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| finding.action:use_reachable | E3 | nicht gemessen | ≤ 1 | — |
| finding.action:use_reachable | E6 | nicht gemessen | 0 | — |
| finding.action:use_reachable | E7 | nicht gemessen | 0 | — |
| finding.action:use_reachable | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| finding.action:use_reachable | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | FD-252 |
| finding.action:use_reachable | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| finding.action:use_reachable | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| report | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| report | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| report | E3 | nicht gemessen | ≤ 1 | — |
| report | E6 | nicht gemessen | 0 | — |
| report | E7 | nicht gemessen | 0 | — |
| report | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| report | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| report | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| report | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| report | G4 | Schrift 9.0 pt, Gewicht 700 an An den Slicer übergeben … ist keine Stufe aus ['title', 'section', 'body', 'caption']; Schrift 9.0 pt, Gewicht 700 an Hand over to the slicer … ist keine Stufe aus ['title', 'section', 'body', 'caption']; Schrift 9.0 pt, Gewicht 700 an Entregar al slicer … ist keine Stufe aus ['title', 'section', 'body', 'caption']; Schrift 9.0 pt, Gewicht 700 an Transmettre au slicer … ist keine Stufe aus ['title', 'section', 'body', 'caption']; Schrift 9.0 pt, Gewicht 700 an Passa allo slicer … ist keine Stufe aus ['title', 'section', 'body', 'caption']; Schrift 9.0 pt, Gewicht 700 an Entregar ao slicer … ist keine Stufe aus ['title', 'section', 'body', 'caption'] | nur die Stufen aus `LEVELS`; keine Größe oder Farbe im Stylesheet | FD-248 |
| report | G5 | nicht gemessen | jeder unterscheidbar, zweite Kodierung, Fokus sichtbar | — |
| report | Z2 | nicht gemessen | kein modales Fenster außer den Ausnahmen | — |
| report | Z5 | nicht gemessen | 0, außer `QFileDialog` | — |
| report | Z6 | nicht gemessen | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| report.action | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| report.action | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| report.action | E3 | nicht gemessen | ≤ 1 | — |
| report.action | E6 | nicht gemessen | 0 | — |
| report.action | E7 | nicht gemessen | 0 | — |
| report.action | V3 | 0 von 0 Feldern mit eigenen Sätzen | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| report.action | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| report.action | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| tool:analysis | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| tool:analysis | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| tool:analysis | E3 | nicht gemessen | ≤ 1 | — |
| tool:analysis | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| tool:analysis | E6 | nicht gemessen | 0 | — |
| tool:analysis | E7 | nicht gemessen | 0 | — |
| tool:analysis | V1 | 0 Treffer | 0 | FD-246 |
| tool:analysis | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung; Feld „Accrochage à la grille“ ohne Beschreibung; Feld „Accrochage angulaire“ ohne Beschreibung; Feld „Tranche“ ohne Kurzhilfe; Feld „Tranche“ ohne Beschreibung; Feld „Aggancio alla griglia“ ohne Beschreibung; Feld „Aggancio angolare“ ohne Beschreibung; Feld „Fetta“ ohne Kurzhilfe; Feld „Fetta“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | FD-246 |
| tool:analysis | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| tool:analysis | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| tool:analysis | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| tool:analysis | G2 | Abstand [6.0] in AnalysisBar kein Vielfaches von 4; Abstand [6.0] in ToolStrip kein Vielfaches von 4 | Vielfaches von `SPACE` (4), je Gruppe einheitlich | FD-247 |
| tool:analysis | G5 | nicht gemessen | jeder unterscheidbar, zweite Kodierung, Fokus sichtbar | — |
| tool:analysis | Z2 | nicht gemessen | kein modales Fenster außer den Ausnahmen | — |
| tool:analysis | Z5 | nicht gemessen | 0, außer `QFileDialog` | — |
| tool:analysis | Z6 | nicht gemessen | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| tool:layers | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| tool:layers | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| tool:layers | E3 | nicht gemessen | ≤ 1 | — |
| tool:layers | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| tool:layers | E6 | nicht gemessen | 0 | — |
| tool:layers | E7 | nicht gemessen | 0 | — |
| tool:layers | V3 | Feld „“ ohne Kurzhilfe; Feld „“ ohne Beschreibung; Feld „Rasterfang“ ohne Beschreibung; Feld „Winkelfang“ ohne Beschreibung; Feld „Scheibe“ ohne Kurzhilfe; Feld „Scheibe“ ohne Beschreibung; Feld „Grid snap“ ohne Beschreibung; Feld „Angle snap“ ohne Beschreibung; Feld „Slice“ ohne Kurzhilfe; Feld „Slice“ ohne Beschreibung; Feld „Ajustar a la cuadrícula“ ohne Beschreibung; Feld „Ajustar al ángulo“ ohne Beschreibung; Feld „Rebanada“ ohne Kurzhilfe; Feld „Rebanada“ ohne Beschreibung; Feld „Accrochage à la grille“ ohne Beschreibung; Feld „Accrochage angulaire“ ohne Beschreibung; Feld „Tranche“ ohne Kurzhilfe; Feld „Tranche“ ohne Beschreibung; Feld „Aggancio alla griglia“ ohne Beschreibung; Feld „Aggancio angolare“ ohne Beschreibung; Feld „Fetta“ ohne Kurzhilfe; Feld „Fetta“ ohne Beschreibung; Feld „Captura à grelha“ ohne Beschreibung; Feld „Captura de ângulo“ ohne Beschreibung; Feld „Fatia“ ohne Kurzhilfe; Feld „Fatia“ ohne Beschreibung | 100%; höchstens die Hälfte der Wörter mit dem Titel geteilt | — |
| tool:layers | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| tool:layers | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| tool:layers | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |
| tool:layers | G2 | Abstand [6.0] in ToolStrip kein Vielfaches von 4 | Vielfaches von `SPACE` (4), je Gruppe einheitlich | FD-247 |
| tool:layers | G5 | nicht gemessen | jeder unterscheidbar, zweite Kodierung, Fokus sichtbar | — |
| tool:layers | Z2 | nicht gemessen | kein modales Fenster außer den Ausnahmen | — |
| tool:layers | Z5 | nicht gemessen | 0, außer `QFileDialog` | — |
| tool:layers | Z6 | nicht gemessen | 1920 x 1080 logisch (maximiert, Task- und Titelleiste ab) ohne Rollleiste vorn; Symbole scharf bei 100%, 125%, 150%, 200%, solange ≥ 1920 x 1080 logisch | — |
| tool:split | E1 | nicht gemessen | ≤ 3; am Merkmal ≤ 2 nach der Auswahl | — |
| tool:split | E2 | nicht gemessen | ≤ 1 bei 90% der Funktionen | — |
| tool:split | E3 | nicht gemessen | ≤ 1 | — |
| tool:split | E4 | nicht gemessen | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | — |
| tool:split | E6 | nicht gemessen | 0 | — |
| tool:split | E7 | nicht gemessen | 0 | — |
| tool:split | V1 | 0 Treffer | 0 | — |
| tool:split | V4 | Vorhersage im Urteil | Abweichung vom Ergebnis ist ein Fund | — |
| tool:split | V5 | nicht gemessen | jede Handlung löst das Problem | — |
| tool:split | V6 | nicht gemessen | ≤ 1; nie das Handbuch | — |

## Paketwerte

| Wert | Messung | Schwelle | Stand |
|---|---|---|---|
| E2-Anteil | 100% (1 von 1) | ≥ 90% | erfüllt |
| E5-Anteil | 95% (72 von 76) | ≥ 90% | erfüllt |
| I3-Anteil | 100% (3 von 3) | ≥ 80% | erfüllt |
| I4-Zahl | 38 von 394 mit Handlung, 356 Vorschläge | Zahl genannt | — |
| Zweitprüfer | 10% (8 von 77) | ≥ 10% der Zeilen | erfüllt |
| Runde | schlusslauf-d9f7a81f/L4-d0: D4, D8, D10 | — | — |
| Übereinstimmung 1 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 3 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 4 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 5 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 6 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 7 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 8 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 9 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 10 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 11 in der Runde | 92% (12 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 12 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 13 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 14 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 15 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 16 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 17 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 18 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung 19 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E1 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E3 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E4 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E5 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E6 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung E7 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V1 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V3 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V4 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V5 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung V6 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G1 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G3 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G4 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G5 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G6 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G7 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G8 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung G9 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z1 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z3 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z4 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z5 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung Z6 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung I1 in der Runde | 92% (12 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung I2 in der Runde | 100% (13 von 13) | ≥ 90% | erfüllt |
| Übereinstimmung I3 in der Runde | 90% (9 von 10) | ≥ 90% | erfüllt |
| Übereinstimmung I4 in der Runde | 100% (9 von 9) | ≥ 90% | erfüllt |
| Übereinstimmung I5 in der Runde | 100% (9 von 9) | ≥ 90% | erfüllt |
| Übereinstimmung I6 in der Runde | 100% (11 von 11) | ≥ 90% | erfüllt |
| Übereinstimmung 1 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 2 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 3 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 4 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 5 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 6 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 7 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 8 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 9 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 10 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 11 im Paket | 88% (7 von 8) | Auskunft | — |
| Übereinstimmung 12 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 13 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 14 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 15 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 16 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 17 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 18 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung 19 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung E1 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung E2 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung E3 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung E4 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung E5 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung E6 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung E7 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung V1 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung V2 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung V3 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung V4 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung V5 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung V6 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung G1 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung G2 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung G3 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung G4 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung G5 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung G6 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung G7 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung G8 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung G9 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung Z1 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung Z2 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung Z3 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung Z4 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung Z5 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung Z6 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung I1 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung I2 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung I3 im Paket | 88% (7 von 8) | Auskunft | — |
| Übereinstimmung I4 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung I5 im Paket | 100% (8 von 8) | Auskunft | — |
| Übereinstimmung I6 im Paket | 100% (8 von 8) | Auskunft | — |
