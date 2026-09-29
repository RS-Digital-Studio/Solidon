# Paket bohren — Schlussbericht

Arbeitsbaum `F:\3D Druck.review-051\wt-bohren`, Zweig `rm-274-bohren`, von `main`
`1163c30d7`. Commits: `33aebf566` (Kerbenregel der Erkennung), `94aa590eb` (RM-274: Werkzeug
in die Welt, Endebenen, gemischte Ecke), `913a7ef16` (`main` `9f19b44d6` mit dem Paket kanten
hereingeholt, ohne Konflikt), `2b3db2fc4` (`cache_version` von *Verrunden* und *Fase*
obendrauf). **Endcommit `2b3db2fc4`**, gepusht.
Laufender Bericht mit allen Zahlen und Sonden: `reports\bohren.md`; Sonden unter
`sonden\bohren\`, Läufe `laeufe\bohren-*.txt`.

## 1. Registerpunkte

### RM-274 — *Bohrung setzen* mit freier Richtung versetzt Ecken, die der Schnitt nicht berührt

**Gebaut** (`94aa590eb`, dazu `2b3db2fc4`): `prepare.drill` legt mit Normale das Werkzeug in die Welt
(`_in_world`), der Körper bleibt, wo er ist; die Lage entlang der Achse misst `_heights`
elementweise, `np.linalg.inv` und `_restore_drill_end_planes` sind weg. Die Endebenen
gehen mit: Ein Ende, das näher als die Schweißtoleranz in einer Körperfläche liegt, deren
Dreiecke um die Achse vom Werkzeug weg zeigen, reicht um `BOOLEAN_OVERLAP` in die Luft
(`_open_ends`); ein Blindboden im Material und eine im Material eingegebene Mündung bleiben
genau. Derselbe Umbau in `prepare.resize_bore` (Kappen auf gemessenen Randebenen legt
`_onto_planes` in der Welt genau auf die Ebene) und `prepare.slot_bore`. Die gemischte Ecke
von *Verrunden*/*Fase* (`edges._placed_edge_work`) rechnet weiter im Rahmen ihres Knotens —
Bereich und Zielkörper liegen genau in dessen Ebenen —, und jede durchgereichte Ecke bekommt
ihre Weltkoordinate zurück (`edges._back_in_place`). Die Übergangslänge der Aufweitung kommt
aus `units.exact_cos_degrees`/`exact_sin_degrees` statt `math.tan`; Weg `drill_hole` in
`test_platform_identity._WAYS`. `lathe.rigid_inverse` war damit verwaist und ist samt Test
entfernt. `cache_version`: `drill_hole` 1, `resize_hole` 12, `slot_hole` 9, nach dem
Zusammenführen mit `main` auch `fillet_edges` 12 und `chamfer_edges` 13 (auf dem Zweig allein
wäre das dieselbe Zeile gewesen, die das Paket kanten anhebt).

**Messung, Gartenschlauchhalter** (`F:\3D Dateien\garden-hose-holder.3mf`, 392 532 Dreiecke):

| Fall | vorher | nachher |
|---|---|---|
| Ø 3 × 2 mm in face_1, Normale +y: Ecken außerhalb des Schnitts an neuem Ort | 17 475 | 0 |
| — bitgleiche Dreiecke | 352 862 von 392 696 | 392 328 von 392 702 (= achsparallel, Netz Bit für Bit gleich) |
| — Merker getroffen / gerechnet in der Erkennung danach | 9 683 / 1 078 | 10 705 / 79 (= achsparallel) |
| Ø 3 × 2 mm in die schräge face_4, Normale (−0,70, 0, −0,71): an neuem Ort | 174 094 | 0 |
| — bitgleiche Dreiecke | 4 569 von 392 700 | 392 323 von 392 706 |
| — Merker getroffen / gerechnet | 0 / 10 774 | 10 705 / 79 |
| *Bohrung ändern* Ø+1 an hole_10: an neuem Ort | 99 741 | 0 |
| *Bohrung ändern* 1 mm versetzt: an neuem Ort | 93 242 | 0 |

Die Bohrung selbst: face_1 abgetragen 16,039058500435203 mm³ (vorher mit Normale
16,03905850002775, jetzt bitgleich mit achsparallel), Radius höchstens 1,6000000000000056 mm,
Mündung 0,0, Boden −2,0; face_4 15,73864714737283 statt 15,73864714987576 mm³ (2,5·10⁻⁹),
Boden −2,0000000000000027 an beiden Ständen, erkannt Ø 3,2 × 2,0. Es fehlen an beiden Wegen
dieselben 12 fernen Ecken: `boolean._tidied` verschweißt Eingangspaare unter der
Schweißtoleranz (`p24_zwoelf.py`), kein Befund des Rahmens. Zeit der Operation im Wechsel
gemessen (je fünf, unter Last): Median alt 6,87/10,16/6,46 s, neu 5,80/7,34/5,67 s.

**Korpusteile** (`p21`, neun Teile mit einfachen Bohrungen aus `F:\3D Dateien`): vorher bis
zu 407 Ecken außerhalb an neuem Ort (Wasserfall-Deckel), nachher an allen 0.

**Gemischte Ecke** (*Verrunden*/*Fase*, L-Profil mit Kugel, synthetisch,
`test_mesh_edges.py::test_a_mixed_corner_leaves_every_corner_away_from_its_edges_in_place`):
vorher 481 von 511 Ecken weiter als 4 mm von den Kanten an neuem Ort, am gedrehten Körper
alle; nachher 0, und neu ist dort nur der äußerste Rand der Fase, höchstens 3·√2 mm von
seiner Kante (`p16_eckrahmen.py`).

**Beide Kerne:** Der exakte Weg (`drill_brep_hole`) legte sein Werkzeug schon in die Welt
und ist unverändert (alt = neu, `p18_exakt.py`): Außerhalb des Schnitts bleiben alle Ecken der
Vernetzung, nur die durchbohrte Fläche vernetzt OpenCASCADE neu.

**Nebenbefund, mit behoben:** Der Weg über den Rahmen ließ an einer schrägen STL-Fläche
(float32) über jedem Sackloch, Langloch und jeder Aufweitung eine Haut in der Mündung
stehen — zwei Teile, keine Bohrung erkannt (`p5_drill_platten.py`); beim Versetzen einer
schrägen Bohrung ebenso (`p6`). Nachher überall offen.

**Abnahme: ja.**
- Alle Ecken außerhalb des Schnitts an ihrem Ort, Bit für Bit, synthetisch mit schräger
  Normale: `tests/test_cut_in_world.py::test_a_bore_along_a_tilted_normal_leaves_every_corner_outside_the_cut_in_place`
  (5 Fälle, am alten Stand rot: 698–711 versetzt), dazu die Merkmalswege und die float32-
  Mündung (15 Fälle, am alten Stand 13 rot, `laeufe\bohren-test-rot.txt`).
- Echtes Modell: Gartenschlauchhalter, Tabelle oben (`laeufe\bohren-p2-*`, `-p23-*`,
  `-p20-*`).
- Erkennung danach wie achsparallel: 10 705 / 79 an face_1 und an der schrägen face_4.
- Bohrung selbst gleich: Volumen, Tiefe, Endebenen innerhalb der Rundung (oben).
- Plattformgleichheit: Weg `drill_hole` am alten Stand rot, am neuen grün.

### RM-187 — Teil *Drehwege* von `resize_bore`

`prepare.resize_bore` dreht das Netz nicht mehr hin und zurück; das war die in RM-187
eingegrenzte letzte Stelle des Änderungswegs (Transformation über das ganze Netz). Weg
`resize_hole` in `_WAYS` bleibt grün. Der Rest von RM-187 bleibt offen (siehe 6).

### Erkennung: Kerbe über eine Kante (`33aebf566`, aus dem Umbau gefunden)

Nach dem Umbau las die Erkennung an der gedrehten schrägen Senkbohrung
(`test_bore_floor_resize`, Ø 6, `keep`) den Senkkegel als Torus. Ursache:
`_without_notches` nahm zwei ebene Dreiecke des Ringabsatzes über einen Knick von 39° als
Kerbe in den Kegelfleck. Eine Kippe an der Vernetzung, auch am alten Stand (über 17 Lagen
bei 1,1 rad). Behoben in `perceive.features._candidates_at`: nur über eine Naht unter
`CURVATURE_LIMIT`. Danach 0 von 68 Lagen verwaist, alt wie neu (`p12_kippe.py`). Test
`test_features.py::test_a_triangle_beyond_an_edge_never_closes_a_notch` (am alten Stand
rot). Korpus der Erkennung gegen den Vorstand (539 Körper aus `F:\3D Dateien` und
`tests/data`, `sonden\bohren\k41_vergleich.txt`): anders nur die zwei gleichen Teile der
Taschentuchbox, an denen ein Kegelausschnitt mit Rückstand 0,0 nicht mehr in der
Freiformfläche aufgeht (angesehen, richtig gelesen); Zeit 2 853 gegen 2 875 s unter Last.

## 2. Kundensicht

Vorher: Wer an einem eingelesenen Modell auf eine schräge Fläche klickte und bohrte, bekam
oft ein Loch mit einer hauchdünnen Haut in der Mündung — im Bild eine Bohrung, im Druck
keine, und die Erkennung fand sie nicht. Jede Bohrung mit freier Richtung, jedes *Bohrung
ändern* und *Zum Langloch ziehen* rechnete außerdem das ganze Modell unsichtbar neu; die
Erkennung danach begann an großen Modellen von vorn (am Gartenschlauchhalter 10 774 statt 79
Fragen neu gerechnet), und fern vom Loch konnte ein Merkmal kippen. Nach *Bohrung ändern* an einer
gedrehten Senkbohrung stand in manchen Lagen „Ein Formdetail ist nach diesem Schritt
verloren“. Nachher: Die Bohrung ist offen, das übrige Modell bleibt Bit für Bit, wie es war,
die Erkennung danach ist so schnell wie nach einer geraden Bohrung, und die Senkung bleibt
erkannt.

## 3. Geänderte Dateien und Tests

| Datei | getragen von |
|---|---|
| `app/core/geom/prepare.py` | `tests/test_cut_in_world.py`, `test_surface_placement.py`, `test_prepare.py`, `test_platform_identity.py` (Weg `drill_hole`, `resize_hole`) |
| `app/core/geom/prepare_ops.py`, `app/core/geom/edge_ops.py` (`cache_version`) | `test_registry_consistency.py` |
| `app/core/geom/edges.py` | `test_mesh_edges.py::test_a_mixed_corner_leaves_every_corner_away_from_its_edges_in_place` |
| `app/core/geom/lathe.py` (`rigid_inverse` entfernt) | `test_platform_identity.py` |
| `app/core/perceive/features.py` | `test_features.py::test_a_triangle_beyond_an_edge_never_closes_a_notch`, `test_bore_floor_resize.py` |
| `app/core/knowledge/data/part_ranges.toml` | `test_parts.py::test_every_shipped_part_carries_a_current_range_proof` |
| `.claude/rules/operationen.md`, `app/core/geom/CLAUDE.md`, `app/core/perceive/CLAUDE.md`, `tests/CLAUDE.md`, `konzepte/begruendungen/regel-operationen.md`, `karte-app-core-geom.md`, `karte-app-core-perceive.md` | `test_directory_docs.py` (Umfang, Verweise) |

Die Regel `operationen.md` ist gekürzt, weil das erste Tor über dem Zweig (`bohren-tor`) an
ihrem Umfang rot war (über 30 KB): jetzt 30 688 Byte, mit der Änderung des Pakets kanten
30 714 von 30 720. Was aus der Regel ging (Eckenfolge je Dreieck, Volumenbedingung von
`_tidied`), steht in `konzepte/begruendungen/regel-operationen.md`.

Tor über dem Endstand `2b3db2fc4` (zusammengeführt mit `main` `9f19b44d6`, gebunden):
`F:\3D Druck.review-051\laeufe\bohren-tor3.txt` — 17 961 bestanden, 36 übersprungen, Läufe mit
Fehler 0, `EXIT tor=0`, `ruff=0`, `format=0`, `mypy=0`. Gelaufen über genau dem Baum des
Endcommits (Zusammenführung und Anhebung im Arbeitsbaum, beide erst danach committet).
Davor über dem Zweig allein `laeufe\bohren-tor2.txt` (17 950 bestanden, alles 0). Die
zusammengeführten Dateien sind Zeile für Zeile `main` plus genau die Hunks des Zweigs
(`edges.py`, `test_mesh_edges.py`, `features.py`, `operationen.md`, `geom/CLAUDE.md`,
`regel-operationen.md` gegengeprüft; Kataloge und die übrigen Dateien aus `main`
unverändert; `edge_ops.py` gegen `main` nur die zwei Anhebungen).

## 4. Oberflächentexte

Keine neuen oder geänderten.

## 5. Changelog-Satz

„Bohrungen in schrägen Flächen eingelesener Modelle öffnen sich sauber, und das übrige
Modell bleibt beim Bohren, Ändern und Langloch-Ziehen unverändert — die Erkennung danach
ist so schnell wie nach einer geraden Bohrung.“

## 6. Registertext

- **RM-274 schließt** (Abnahme oben erfüllt). Ins Archiv mit: Werkzeug in die Welt
  (`drill`, `resize_bore`, `slot_bore`), Endebenen über `_open_ends` (Schweißtoleranz,
  Entscheidung im Paket: eine Haut unter ihr ist keine), gemischte Ecke über
  `_back_in_place`, Nebenbefund Haut an schrägen STL-Flächen behoben, Kerbenregel.
- **RM-187 fortschreiben:** Absatz „Was offen bleibt … `prepare.resize_bore` dreht das ganze
  Netz …“ ist erledigt (Werkzeug in die Welt, `94aa590eb`); „Zwei Wege stehen dafür offen“
  entschieden für den zweiten. Neu offen: die Bögen eines Langlochs (`sketch_solid._arc_points`
  über `math.atan2`/`cos`/`sin`, betrifft jeden abgetasteten Skizzenbogen, Messung: Langloch-
  Fall des Wegs `drill_hole` ändert sich unter Rauschen) und *Senkung* samt den übrigen
  `math.tan` in Werkzeugmaßen (gemessen, siehe 7).
- **Neu vorschlagen:** `_without_scars` legt nach dem Schließen koplanare Dreiecke im ganzen
  Körper zusammen und nimmt ferne Ecken weg (siehe 7).

## 7. Nicht behoben

- **Bögen eines Langlochs plattformabhängig** — `sketch_solid._arc_points` tastet über
  `math.atan2`, `math.cos`, `math.sin` ab; der Langlochfall des neuen Wegs änderte unter
  Rauschen seinen Abdruck (`p17_weg.py`, `956/5d4a02f082b190f2` gegen `956/d93530fff1ee4d0d`).
  Grund: gemeinsame Abtastung aller Skizzenbögen (Taschen, Profile), eine Änderung verschiebt
  jeden Bogenumriss in der letzten Stelle weit über die Bohrwege hinaus; gehört zu RM-187.
- **Senkung unter der Rauschprobe nicht gleich** — gemessen an *Senkung* (`countersink_hole`,
  Platte aus `_WAYS`, Ø 8,4 an (−12, 4, 8), Achse z): Der Abdruck ändert sich bei 90°, 82° und
  100° (`p30_senkung_rauschen.py`, Lauf `bohren-p30`). Einzeln verrauscht wirken `np.dot` und,
  bei 90°, `math.tan` (`p32_senkung_einzeln.py`). Das `np.dot` kommt aus
  `trimesh.apply_translation` (`prepare.py` Zeilen 1895 und 1897, homogene 4×4-Multiplikation;
  wertgleich, weil der Drehteil die Einheitsmatrix ist, was die Probe nicht unterscheidet —
  `p33_senkung_dot.py`), das `math.tan` aus der Kegeltiefe. Grund: Der Weg steht nicht in
  `_WAYS`, RM-274 hat ihn nicht berührt, und er gehört mit den zwölf übrigen `math.tan` in
  Werkzeugmaßen von `prepare_ops` (Senk- und Kegelwerkzeuge) zu RM-187.
- **Zusammenlegen nach dem Schließen nimmt ferne Ecken weg** — `prepare_ops._without_scars`
  ruft `Manifold.simplify` über den ganzen Körper: beim Versetzen und beim Langloch fehlen
  am Gartenschlauchhalter 341 von 194 817 Ecken außerhalb des Schnitts, an der Murmelbahn 112
  von 521, am Wasserfall-Deckel 15/13 — ohne neue Orte, also nur zusammengelegte ebene
  Stellen. Grund: eigene Ursache, kein Rahmen; eine örtliche Begrenzung ändert die Zusage der
  Narbenentfernung und gehört gemessen in einen eigenen Punkt.

## Unterwegs zurückgenommen

- Die erste Fassung gab der Mündung beim Mündungsanker immer `BOOLEAN_OVERLAP`. Rot an
  `test_an_entered_mouth_inside_material_keeps_its_exact_start`: Eine im Material
  eingegebene Mündung ist kein Außenanschluss. Jetzt entscheidet `_open_ends` auch dort.
- Der Kommentar in `resize_bore`, der den Weg über den Rahmen mit Keilen von 97° an einer
  schrägen eingelesenen Bohrung begründete, trägt nicht mehr:
  `test_a_slanted_imported_bore_keeps_its_axis` ist mit dem Werkzeug in der Welt grün.
- Die 12 fehlenden fernen Ecken am Gartenschlauchhalter waren zuerst eine Vermutung
  (Verschweißen); erst `p24_zwoelf.py` hat sie `boolean._tidied` zugeordnet.
- Der Entwurf der Commit-Meldung behauptete, die Operation sei schneller geworden; gestrichen,
  denn die Mediane im Wechsel unter Last (alt 6,87/10,16/6,46 s, neu 5,80/7,34/5,67 s) sind
  kein Leistungsnachweis.
