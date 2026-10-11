# owand — runde Wände eines aufgebrachten „O“ (Zweig `fix/o-waende`, Worktree `F:\sl-o-waende`)

Basis `e3f0c9dc9` (origin/welle5). Stand fortlaufend.

## Ursache

`detect_curved_faces` (features.py) verlangte für jede gerundete Seite
`max(MIN_FACE_AREA, body.area * CURVED_SIDE_SHARE)`. „O“ 8 mm, 0,6 mm erhaben
auf einem 20-mm-Würfel: beide Wände zusammen 19,17 mm², Schwelle 24,19 mm².
Als *Schriftzug als Körper* ist die Haut klein, die Schwelle greift nicht.
Zwilling: `local.py` rechnete dieselbe Schwelle an zwei Stellen
(`is_complete`, `_could_be_complete`) nach.

## Fix

- `features._sharply_bounded(body, owner, sizes)`: die Randprobe aus
  `_facets_standing_apart_read` herausgelöst (dort unverändert benutzt).
- `features.curved_sides_standing(body, patches)`: gerundete Seite gilt ab
  `CURVED_SIDE_SHARE` der Haut **oder** ab `MIN_FACE_AREA`, wenn jede Naht
  scharf (≥ `CURVATURE_LIMIT`) an eine **ebene Facette** (`body.facets`) stößt,
  jede Kante einen Nachbarn hat und der Fleck kein Streifen ist (`_a_sliver`).
  Antwort je Fleck unabhängig von den übrigen (ein anderer Fleck hinter der
  Naht zählt nicht). Zwischenstand mit „gerundete Haut zählt als Nachbar“
  verworfen: `weg3-generiert-aufbereiten` bekam an einem Zwischenkörper 87
  reservierte `curve_N` aus Rauschen.
- `detect_curved_faces` und beide Stellen in `local.py` fragen diese eine
  Funktion (örtlich = voll).
- `CACHE_FORMAT_VERSION` 61 → 62 (Erkennung liegt auf der Platte).
- Regel `operationen.md` (ein Satz), Begründung in
  `konzepte/begruendungen/karte-app-core-perceive.md`.
- Changelog ×6 unter 0.6.0, „Bearbeiten und Zeichnen“: Ursache im Tag
  v0.5.3 (dieselbe Schwelle, `git show v0.5.3:…features.py` Zeile 13512).

## Tests

- Neu: `test_the_round_walls_of_a_letter_on_a_cube_are_curved_faces[O|D|0]`
  (create_box + label_text über `evaluate`), am Stand e3f0c9dc9 3 rot,
  `test_the_round_walls_of_a_lettering_body_stay_curved_faces` (grün vorher
  wie nachher).
- Angepasst: `test_lettering_is_read_like_its_original_after_refining_and_a_bore`
  (RS-Platte: 2 → 3 gerundete Seiten; neu der Innenbogen des R, 33,3 mm² unter
  43,2 mm² Schwelle). Nach Verfeinern und Bohrung weiter gleich gelesen.
  `test_local_detection::test_a_rounded_side_is_measured_against_the_whole_body`:
  die Ellipsenwand (87 mm² < 216 mm²) ist jetzt Seite — Test prüft voll =
  örtlich (beide 1 Seite, 384 Dreiecke, 87,1805 mm²). Ohne die Umstellung in
  `local.py` fand die örtliche Erkennung sie nicht (gemessen, Zwischenstand).

## Läufe (Stand f391a14d0)

- Gezielt (46 Dateien: Merkmale, örtlich, Cache, Zuordnung ×7, Beispiele,
  Datei-Abnahme, Exakt-Parität, Schrift, Erkennungs-Regressionen, Arbeiter,
  dazu die ganze Pflichtliste und test_directory_docs), gepinnt, `-n 6`:
  **6495 passed, 5 skipped, EXIT=0**.
- Nach den Unterlagen: test_directory_docs, test_changelog, test_text_length,
  test_wording: 91 passed, 4 skipped, Exit 0 (vorher war operationen.md über
  30 KB — Regelsatz nach `schichtanalyse.md` verlegt).
- ruff check . 0, ruff format --check . 0, mypy 0 (378 Dateien).
- Commit `f391a14d0`, Push `origin/fix/o-waende`. origin/welle5 steht noch auf
  e3f0c9dc9 (fetch 12:08) — nichts zu mergen.

## Korpus vorher/nachher (`tools/check_print_equal.py`, je Baum, --quick)

47 Netze aus `tests/data/meshes` (ohne npz/wkt) + 12 Beispiele + 86 Projekte
aus `tests/data/projects`:

| Satz | Fälle | Merkmale vorher → nachher | geändert |
|---|---|---|---|
| Netze | 47 | unverändert je Datei | 0 |
| Beispiele | 12 | 1360 → 1384 (mit Netzen) | dose-mit-deckel 95 → 105, schild-zweifarbig 85 → 99 |
| Projekte | 86 | 657 → 657 | 0, druckgleich |

Neu sind nur `curved_face` an Schriftwänden (dose: 10 Wände 4,2–8,2 mm² der
Schrift am Deckel; schild: 14 Wände 5,7–13,8 mm²). Kein Merkmal weg, kein
bestehendes Merkmal in Art, Maß oder Dreiecken geändert, Kennungen gleich;
reservierte Kennungen wachsen nur um die neuen `curve_N` (dose obj_2 erbt
sie). Geometrie 0 µm. Die npz-Erkennungskorpora deckt
`test_recognition_regressions` (grün).

## Leistung (CPU-Zeit `detect`, frischer Prozess, im Wechsel, gepinnt)

| Modell | Dreiecke | vorher | nachher |
|---|---|---|---|
| dice_w6_16mm_v00.stl | 250 488 | 11,05 / 10,62 / 9,83 s | 10,39 / 10,73 / 9,59 s |
| broomholdervcd_d35mm.stl | 59 740 | 1,80 / 1,66 / 1,64 s | 1,81 / 1,61 / 1,70 s |
| obj_1_spiderman.stl (Freiform, Pfad läuft nicht) | 885 570 | 18,89 / 20,77 / 18,88 s | 19,48 / 21,67 / 18,33 s |

Gleich innerhalb der Streuung (parallel liefen andere Agenten). Spitze
Arbeitsspeicher dice: 496 → 499 MiB (der zusätzliche Kantendurchgang, nur
wenn ein Fleck zwischen `MIN_FACE_AREA` und dem Anteil liegt).

## Cache, Changelog

- `CACHE_FORMAT_VERSION` 61 → 62: ja (gespeicherte Erkennungen trügen die
  neuen Seiten nicht).
- Changelog: ja, Behebung (Schwelle schon in v0.5.3), sechs Sprachen,
  „Bearbeiten und Zeichnen“ am Ende.

## Neue Punkte (Vorschlag)

- Der Schaber-Fall (Ausschnittsschwelle, 25.09.) hat keinen eigenen
  Gegentest mehr, dessen Fleck nicht scharf begrenzt ist; der angepasste Test
  prüft nur noch voll = örtlich.
- `app/core/perceive/CLAUDE.md` liegt bei 25 567 Byte an der Grenze;
  `curved_sides_standing` steht deshalb nur in der Regel, nicht in der Karte.

## Nachtrag nach Review rvowand („nicht“, 12:28)

- **S1:** `curved_sides_standing` prüft jeden Fleck allein: `_bounded_by_planes`
  liest nur die Nähte, die ein Fleckdreieck berühren (Bitmaske über
  `face_adjacency`), Beleg hinter der Naht = Dreieck in `body.facets`
  (`_planar_members`, je Körper gemerkt, schreibgeschützt, in
  `SHARED_ANSWERS`), Knick ≥ `CURVATURE_LIMIT`, jede Kante mit Nachbar.
  `crossing` und `_sharply_bounded` entfallen, `_facets_standing_apart_read`
  wieder wie am Ausgangsstand. Sonde `probe_vesica.py`: A Linse voll 2 ×
  50,13 = örtlich, B Fase voll 30,03 + 58,12 = örtlich, C weich [] = [].
  Tests `test_sharply_bounded_sides_are_the_same_alone_and_together[lens|chamfer]`
  (am Stand f391a14d0 örtlich 2 / voll 0 laut Review).
- **M1:** `test_a_softly_rounded_side_under_the_share_is_no_side_alone_either`:
  voll [] = örtlich [], Spion auf `curved_sides_standing` während der
  örtlichen Suche sichert zu, dass ein gefundener Fleck verworfen wurde.
- **M2:** örtliche Frage (`probe_perf.py`, Fleck 87 mm²): 370 388 Dreiecke
  0 / 15,6 / 0 ms CPU, Spitze 9,7 MiB; 4 812 960 Dreiecke 93,8 (erste Frage
  mit Facettenmaske) / 46,9 / 31,2 ms, Spitze 126 MiB (über drei Fragen,
  samt Maske) — vorher am Zweig 390–500 ms und 359 MiB je Frage, am
  Ausgangsstand 0 ms (nur Flächensumme). Nur unter dem Anteil gerechnet.
  Zwischenversuch über `_neighbour_index` verworfen: erste Frage 1,4 s,
  845 MiB. Docstring `_could_be_complete` berichtigt.
- **L1:** nachgemessen (`probe_letters.py`, 20-mm-Würfel, 8 mm, 0,6 mm): O, D,
  0, 8 je 2 Seiten, B und 3 je 1, R 0, m 3; Platte (12 mm, 1 mm): B, 3, R, m
  je 4. Changelog in sechs Sprachen auf „Viele runde Wände … etwa die eines
  „O“ oder „D“ … jetzt auch auf einem großen Körper“ (161–182 Zeichen).
- **L2:** eigene Überschrift „Eine ringsum scharf begrenzte gerundete Seite
  braucht keinen Anteil“ in `schichtanalyse.md`, Begründung unter derselben
  Überschrift in `regel-schichtanalyse.md`, Karte-Begründung verweist dorthin.
- Korpus (nach4, gegen e3f0c9dc9): 47 Netze unverändert, 86 Projekte 657 → 657
  druckgleich, Beispiele nur `dose-mit-deckel` +10 und `schild-zweifarbig` +16
  `curve_N` (Schriftwände), kein Merkmal weg oder geändert, 0 µm.
- Läufe: gezielt + Pflichtliste am Fix (6498 passed, 5 skipped, EXIT=0) und
  nach dem Merge von welle5 4c93c1fe2 (6498 passed, 5 skipped, EXIT=0);
  Changelog-/Docs-Tests nach Konfliktlösung 91 passed, 4 skipped, Exit 0;
  ruff 0, format 0, mypy 0.
- Commits `66cb49276` (Fix), `b06c2b162` (Merge welle5, Konflikt in den
  sechs Changelogs: beide Seiten behalten), gepusht 12:46.

## Restfunde der Nachprüfung (N1–N5), Commit `63dcfc4ac`, gepusht 13:00

- N1: Maske direkt aus `np.concatenate(body.facets)` — `probe_mask.py` (4,8 Mio.):
  15,6 ms CPU, Spitze 41,3 MiB, gleich: True. Örtliche Frage danach
  [62,5 / 31,2 / 31,2] und [46,9 / 46,9 / 46,9] ms, Spitze 43,3 MiB.
- N2: `planar_members` in `WHOLE_BODY_ANSWERS`.
- N3: Spion schreibt je Antwort die Dreieckszahl; zugesichert: der Ausschnitt
  fand einen Fleck, der ganze Körper verwarf ihn.
- N4: fr nennt „dans l'arbre des objets“ (189 Zeichen).
- N5: Regelsatz „belegt nur ein Dreieck aus `body.facets` (auch ein koplanares
  Paar einer Nachbarwand)“, Messzahl 31–125 ms in `regel-schichtanalyse.md`.
- Läufe: gezielt + Pflichtliste 6498 passed, 5 skipped, EXIT=0; test_wording
  20 passed, Exit 0; ruff 0, format 0, mypy 0. welle5 4c93c1fe2 schon enthalten.
- Fehltritt: einmal `python -` aufgerufen (Hilfsaufruf), eigener Prozess 12532
  per PID beendet; ohne Wirkung auf den Baum.
