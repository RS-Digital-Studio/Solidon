# Durchsicht Dreieckserkennung und Reparatur (Claude, 24.09.2026)

Ausgang: HEAD 8ed5d6299, darüber Codex' unkommittierte Änderungen
(`.claude/.state/triangle-repair-review-2026-09-24/staged.patch`).
Parallel im selben Baum: Sitzungen „Langloch-Ziehen" und „Website".

| Paket | Agent | Bericht |
|---|---|---|
| Reparaturkern | aea08867c9159c980 (solidon3d-geometrie) | bericht-reparaturkern.md |
| Merkmalserkennung | a8024da69abbcf09f (solidon3d-review) | bericht-erkennung.md |
| Bedienweg | a021ca1686576359c (bedienlogik) | bericht-bedienweg.md |

Alle drei nur lesend; Fixes macht die Hauptsitzung.

## Eigene Fixes der Hauptsitzung (Stand fortlaufend)

1. `repair.stitch_t_junctions` fasst nach (`STITCH_ROUNDS`, `_stitched_once`): mehrere
   Punkte auf einer Kante wurden nur einmal geteilt, Rest als Nullflächen gefüllt.
   Test `test_every_vertex_on_one_edge_is_stitched` (Gegenprobe rot mit 1 Durchgang).
2. Toter Helfer `_slots_after_fill` (seit HEAD unbenutzt) samt `Counter`-Import entfernt.
3. B1 (Prüfer Erkennung): Achter-Ring an Sanduhr-Ecke in einer Fläche -> `_hole_rings`
   legt Kopien am selben Ort im selben Ring zusammen, `_simple_cycles` zerlegt in Lappen;
   `_ring_normal` (Newell, aus `_loop_triangles` herausgezogen) + `_folds` verwirft
   gefaltete Füllungen. Tests `test_two_holes_touching_in_one_face_close_without_a_fold`,
   `test_a_fold_is_never_taken_as_a_fill` (Gegenproben rot).

## Pause 24.09.2026 (Robert: 3 h 35 min)

Stand vor der Pause:
- Erledigt und grün: repair.py-Umbau, loader.py (Schritt 4/4b/6, mended_here), ingest/ops.py `mend`,
  errors.py (RESOLVE_INTERSECTIONS, LEAVE_OPEN, GIVE_THICKNESS), geom/ops.py RepairParams,
  Tests repair/geometry_review/maps/self_intersections/ingest/import_formats/examples/way_one/errors/value_labels.
- Werteschlüssel `tolerance` -> `tolerance_mm` (repair, loader), Beschriftung `holes` in labels.py.
- test_examples: Ausnahme weg3/repair.components_removed gestrichen (Befund ist jetzt info).
Als Nächstes:
1. Neue Regressionstests (Flosse, flache Fläche/no_thickness, Einzeldreieck, umgestülpte Schale,
   gekreuzte Kanten, Loader umgestülpt nach Füllen, Ort verschoben mit place_on_bed, mend=False).
2. Migration 34->35 `_keep_repairs_as_they_were` + tests/data/projects/repair_v34.p3d.
3. evaluate.py: SETTLED_BY + Zustandsfilter.
4. Oberfläche: Handler resolve_intersections/leave_open/give_thickness, NEEDS_OP, _LOCATED_REPAIR_FINDINGS.
5. Karte: Legende, Knopf.  6. Kataloge (ca. 47 neu, 32 verwaist).  7. Doku/Regeln/ROADMAP/Memory.
8. Agentenberichte (Teilstände in agent-*-teil.txt) einarbeiten.  9. Tor, Selbstdurchsicht, Bericht.

## Stand nach der Pause (24.09.2026, abends)

Erledigt seit der Pause, alle mit Test und Gegenprobe:
- B3 (Erkennung): glatteste Füllung (`_smoothest_fill`, Grenze 32 Ecken) — Verrundung an
  `block_with_rounded_edge.stl` bekommt ihre Dreiecke zurück, Würfelkante kommt als Kante,
  Viertel einer Bohrungswand als Wand.
- B16/B17 (Reparatur): `mesh.triple_products`, `mesh.signed_volume` (körpernah), `_shell_volumes`
  je Schale körpernah, `boolean._signed_volume` aufgelöst; Weg `repair_selfint` in `_WAYS`.
- B9-Rest: `parts_inside_parts` + `repair.part_inside` (Import und Reparatur), in `ONE_PIECE_CODES`.
- B19: `_Shells` schneidet umhüllende Schalen einmal aus — 300 Hohlräume/331 k: 7,2 → 1,2 s.
- B12: `wind_consistently` statt `trimesh.repair.fix_winding` — Katze 13,4 → 0,4 s; je Teil
  dreht die Minderheit (Gegenprobe: trimesh dreht die ganze Kuppel).
- B6 (Erkennung): gerundete Seiten schließen koplanare Facetten ein; `CACHE_FORMAT_VERSION` 28.
- Register: RM-239 (Verschweißen je Punktgruppe, B8 + Zwilling Import/Reparatur),
  RM-240 (halbe Bohrungswand flach).

Commit erst nach Mausoleums Meldung (seine 34 vor meiner 35). Codex' Hunks zur lokalen
Erkennung (perceive/local.py, ui/local_recognition*) gehören zu Mausoleum/RM-238 — vor dem
Commit klären.

## Review (review-final.md, 22 Befunde) — eingearbeitet

Behoben mit Test und, wo es geht, Gegenprobe: R1 (Grund nicht als Wert), R2 (keine Toleranz
0,00 mm), R3 (Umkehr je Verschachtelungsbaum), R4 (Teil im Teil nur im Material), R5 (Bilanz der
flachen Ringe am Endstand), R6 (thicken nur offene Teile), R7 (`moved_findings` auch für
Baugruppen), R8 (4b folgt `unify_normals`), R9 (Vorauswahl der Ringpaarungen: 78 → 0,47 s),
R10 (`normalise(cancelled=)`), R11 (`np.hypot`/`einsum` elementweise, drei `_WAYS`), R12
(Sockelbudget offen/über Kartengrenze), R13 (*In Einzelteile zerlegen* am Befund), R14
(`_enclosed_volume` körpernah), R16 (Hinweis nach Auflösen), R18 (Text des Hakens), R19
(`WOUND_STATE_CODES`), R20 (ein Körper ohne Schalenapparat), R21 (verkehrt ≠ flach, immer ein
Befund), R22 (Bandsperre, Migration Undo-Seite).
Offen mit Entscheidung Robert: R15, R17 → RM-241.

## Commit (25.09.2026)

Mausoleums Format 34 steht auf main (2c67b684e). Die Sitzung „CI-Testlaufzeiten optimieren" hat
in Roberts Auftrag die Bedienweg-Punkte (RM-241, A1, A4, A5, A6, B1, B3, C5, D4) in meinen Dateien
umgesetzt und committet meinen Stand mit ihren Punkten zusammen — ein Committer, privater Index.
Zuordnung meiner Dateien per Nachricht übergeben; Meldungsvorlagen: scratchpad commit1.txt/commit2.txt.
Letzte eigene Änderung davor: ingest/ops.py load cache_version 3 → 4.
