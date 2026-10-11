# Review rvowand — `fix/o-waende` (f391a14d0 gegen welle5 e3f0c9dc9)

Prüfer rvowand, 11.10.2026, 12:12–12:30. Worktree `F:\sl-o-waende` nur
gelesen. Sonden, Läufe und Ausgaben: `F:\tmp-agenten\rvowand\`. Ausgangsstand
und Fix-Variante als Schnappschüsse (`git archive … app/__init__.py app/core
app/i18n app/examples`) unter `…\rvowand\base` und `…\rvowand\fix` — kein
Worktree angelegt, nichts im Prüfling geändert.

**Urteil erste Runde (f391a14d0): nicht.** S1 bricht den Bitgleich-Vertrag
örtlich = voll, den der Zweig selbst zusichert. Der Fix ist gemessen (unten),
braucht aber Umsetzung, Tests und Korpuslauf — danach kurze Nachprüfung
(Sonde A/B/C + Korpus). M2, L1, L2 sind ohne weitere Prüfung behebbar.

**Urteil Nachprüfung (b06c2b162): kann landen** — Abschnitt „Nachprüfung“ am
Ende; S1, M1, M2, L1, L2 behoben, fünf leichte Restfunde ohne weitere Prüfung
behebbar.

## Anlass der 1-%-Schwelle

- Eingeführt mit `507c2bcd4` (12.09.2026, „Ein D hatte im Baum vier ebene
  Flächen und keinen seiner zwei Bögen“): auf `generated_figure.stl` sechs
  Übergangsflecken von 4–40 mm² zwischen Kugeln. Gegentests:
  `test_a_constructed_part_leaves_no_curved_face_over` (fünf Korpusnetze),
  `test_a_freeform_gets_no_curved_face_because_its_skin_would_be_one` — beide
  grün. Die neue Ausnahme bringt diesen Fehler nicht zurück: Übergänge stoßen
  weich an (Fall C unten), `generated_figure`, `clean_figure`,
  `generated_touching` und `weg3-generiert-aufbereiten` bleiben druckgleich.
- Der „Schaber-Fall“ (25.09.2026, `b57688bad`) ist der Anlass einer zweiten
  Regel: Der Ausschnitt maß ein Hundertstel des *Ausschnitts* und lieferte
  14 Stücke, die die Vollerkennung nirgends führt. Wächter war
  `test_a_rounded_side_is_measured_against_the_whole_body`.
- Doppelte Zuordnung mit Bohrungen: keine — `detect_curved_faces` gruppiert nur
  Dreiecke, die kein Merkmal führt (Code), `plate_holes`, `drilled_v6` und
  `test_a_constructed_part_leaves_no_curved_face_over` unverändert.

## Funde

### S1 schwer — örtliche ≠ volle Erkennung, sobald zwei gerundete Flecken scharf aneinanderstoßen

`app/core/perceive/features.py:15134-15150` (`curved_sides_standing`),
wirksam über `app/core/perceive/local.py:787-789` (`side_stands` in
`is_complete`) und `local.py:1055` (`_could_be_complete`).

Die Funktion zählt jedes Dreieck aus `body.facets` als „ebene Facette“. Die
Wand einer Extrusion oder eines Drehkörpers besteht aus koplanaren
Dreieckspaaren — jedes Paar steht in `body.facets`, obwohl es gerundete Haut
ist. Die Vollerkennung fragt alle Flecken zugleich und verwirft zwei
aneinanderstoßende über `crossing`; die örtliche fragt **einen** Fleck, dann
ist der Nachbarfleck „ebene Facette“, und der Fleck gilt als Seite. Die
Antwort hängt also doch daran, welche Flecken zugleich gefragt werden — gegen
den eigenen Docstring („hängt nur an ihm und am Körper“), gegen die neue Regel
`.claude/rules/schichtanalyse.md:332-336` und gegen den Bitgleich-Vertrag
örtlich = voll (AUFTRAG.md). Das ist die Fehlerklasse des Schaber-Falls:
Stücke, die die Vollerkennung nirgends führt. Der Bericht `owand.md`
behauptet örtlich = voll; das gilt nur für den einen Testfall.

Beleg `probe_vesica.py` (gepinnt, Exit 0; `probe_new.log`, `probe_base.log`,
`fix2_vesica.log`). Platte 100 × 100 × 4, Erhebung 3 mm, `subdivide_to_size(3)`,
Treffer auf einer Wand, Radius 12:

| Fall | e3f0c9dc9 voll / örtlich | f391a14d0 voll / örtlich | Variante „jeder Fleck allein“ |
|---|---|---|---|
| A Linse aus zwei Ellipsenbögen, Ecken scharf | [] / [] | **[] / 2 × 50,13 mm²** | 2 × 50,13 / 2 × 50,13 |
| B ovale Erhebung mit 45°-Fase oben | [] / [] | **[] / 30,03 + 58,12 mm²** | beide gleich (30,03 + 58,12) |
| C ovale Erhebung, Oberkante weich verrundet | [] / [] | [] / [] | [] / [] |

Fall B ist eine gewöhnliche Konstruktionsform (ovaler Knopf mit Fase).

Erster Fixversuch verworfen (gemessen, `fix_vesica.log`): Dreiecke aus
`_curved_faces(body)` auf `-1` setzen heilt B, nicht A — nach dem Unterteilen
liegen die Dreiecke an der Ecknaht nicht an einer Rundungsnaht.

**Fix (gemessen):** jeden Fleck so prüfen, wie die örtliche Erkennung fragt —
allein gegen `body.facets`; ein anderer Fleck hinter der Naht zählt als das,
was seine Dreiecke in `body.facets` sind; der `crossing`-Block entfällt. Dann
ist voll = örtlich durch Bauart. Sonde (Schleife je Fleck im Schnappschuss
`…\rvowand\fix`, `fix2_*.log`, `pe_compare_fix.log`): A, B, C gleich (Tabelle);
O/D/0 auf dem Würfel unverändert je 2 Seiten; dazu bekommen B 1, 3 1, 8 2,
m 3 statt 0/0/0/2 Seiten (Würfel), auf der Platte B, 3, m je 4 statt 2; Korpus
gegen f391a14d0: 22 von 23 Fällen druckgleich, darunter `weg3-generiert-aufbereiten`,
`generated_figure`, `generated_touching`, `clean_figure`; nur
`schild-zweifarbig` +2 Seiten (`curve_15`, `curve_16`, Folge der Größe nach
verschoben — gegen v0.5.3 sind alle `curve_N` dort neu). Umsetzung als
Feldrechnung, nicht als Schleife: je Randkante eines Flecks ist der Beleg
„Gegenseite in `body.facets` und Knick ≥ `CURVATURE_LIMIT`“ — eine Maske über
`face_adjacency`, kein Besitzer je anderem Fleck. Tests: Fall A und B in
`tests/test_local_detection.py` (voll == örtlich, am Stand f391a14d0 rot),
Docstring und Regelsatz („Gerundete Haut hinter der Naht belegt nichts“)
nachziehen, voller Korpuslauf wie im Bericht (47 Netze, 12 Beispiele,
86 Projekte).

### M1 mittel — kein Gegentest mehr für einen nicht scharf begrenzten Fleck unter 1 %

`tests/test_local_detection.py:1955-2012`. Der Wächter des Schaber-Falls
nimmt jetzt in beiden Wegen dieselbe Wand an und prüft nur noch Gleichheit;
dass der Ausschnitt einen Fleck verwirft, den die Vollerkennung verwirft,
prüft keine Zeile mehr (der Bauagent nennt die Lücke selbst). Fall C der
Sonde ist dieser Gegentest und am Zweig grün (voll [] = örtlich []). Fix:
Fall C als Test (beide leer), mit Zusicherung, dass die Erkennung am
Ausschnitt den Fleck gefunden hat — sonst prüft er nichts
(`.claude/rules/tests.md`, Verbotstest über leerer Menge).

### M2 mittel — die örtliche Frage kostet jetzt einen Durchgang über den ganzen Körper je gerundetem Merkmal

`local.py:787-789`, `local.py:1048-1056`, `features.py:15132-15150`. Statt einer
Flächensumme baut jede Frage `_facet_table(body.facets)`, `owner` über alle
Dreiecke und zwei Felder über `face_adjacency`. Gemessen (`probe_perf.py`,
gepinnt, Caches warm, `perf.log`): 370 388 Dreiecke 16–47 ms CPU, Spitze
27,7 MiB je Frage; 4 812 960 Dreiecke **390–500 ms CPU, Spitze 359,5 MiB je
Frage**; vorher 0,00 ms. Der Bericht maß nur die Vollerkennung.
`_could_be_complete` (RM-265, Weg `alone` an großen Netzen) sagt im Docstring
weiter „ohne den ganzen Körper zu fragen“ (`local.py:1037-1041`) — das stimmt
nicht mehr. Fix: mit S1 ist die Antwort je Fleck unabhängig; dann alle
gerundeten Merkmale des Ausschnitts in **einem** Aufruf fragen, oder je Fleck
nur seine eigenen Randkanten über `_neighbour_index(body)` prüfen und die
Facettenmaske je Körper merken (`remembered`); Docstring berichtigen.

### L1 leicht — Changelog verspricht mehr, als der Zweig liefert

`changelog/de.md:181` (und fünf Sprachen): „Die runden Wände kleiner Schrift
… stehen im Objektbaum als *Gerundete Seite*.“ Am Zweig gemessen
(`letters_new.log`, `plate_new.log`; 20-mm-Würfel, 8 mm, 0,6 mm): B, 3, 8, R
ohne jede gerundete Seite, auf der Platte (12 mm, 1 mm) B und 3 nur mit 2 von
4 Wänden — Bögen, die scharf aneinanderstoßen, verwirft `crossing`. Mit dem
S1-Fix kommen B, 3, 8, m dazu; R bleibt ohne (vermutlich Wände unter
`MIN_FACE_AREA`, nicht gemessen).
Fix: nach S1 nachmessen; der Satz mit „etwa eines „O““ passt dann. Sonst
geprüft und in Ordnung: Behebung belegt (`git tag --contains 507c2bcd4` →
v0.4.1 … v0.5.3; `v0.5.3:features.py:13512` dieselbe Schwelle, `label_text`
in v0.5.3), Gruppe „Bearbeiten und Zeichnen“ passend, 159–176 Zeichen,
Op- und Artnamen wie in den Katalogen (*Put text on*/*Curved face*,
*Aplicar texto*/*Cara curva*, *Appliquer du texte*/*Face courbe*,
*Applica testo*/*Faccia curva*, *Aplicar texto*/*Face curva*).

### L2 leicht — Regelsatz unter fremder Überschrift, Begründung am falschen Ort

`.claude/rules/schichtanalyse.md:332-336`: Der Satz zu
`curved_sides_standing` steht unter „Ein Umriss mit wanderndem Radius ist eine
gerundete Seite“, einer Regel über `_wandering_outline`. Der Kopf der Datei
sagt, Anlässe stehen unter derselben Überschrift in
`konzepte/begruendungen/regel-schichtanalyse.md`; die Begründung (87
Rauschflecken, 19 gegen 24 mm²) liegt stattdessen in
`karte-app-core-perceive.md:1468-1474`. Fix: eigene Überschrift („Eine
ringsum scharf begrenzte gerundete Seite braucht keinen Anteil“), Begründung
unter derselben Überschrift nach `regel-schichtanalyse.md`.

## Ohne Befund

- Cache-Schritt 61 → 62 nötig (Erkennung liegt auf der Platte) und mit
  Eintrag; keine weitere Version berührt (`FORMAT_VERSION` 52 unverändert,
  Projektdateien nicht betroffen). Mit S1-Fix ändern sich gespeicherte
  Erkennungen erneut gegenüber f391a14d0 — solange 62 nicht ausgeliefert ist,
  genügt 62.
- Korpus selbst nachgestellt (`pe_*.sh`, `check_print_equal.py --quick`,
  e3f0c9dc9 gegen f391a14d0): 12 Beispiele, 7 Projekte aus
  `tests/data/projects` (recognition_v33, lid_top_edge_v46, drilled_v6,
  painted_v13, generated_glb_v24, sketch_v30, example_v52), 4 Netze
  (generated_figure, clean_figure, generated_touching.glb, plate_holes):
  21 von 23 druckgleich, größte Abweichung 0 µm; nur `dose-mit-deckel` (+10
  `curve_N`) und `schild-zweifarbig` (+14), kein Merkmal weg, Kennungen
  bestehender Merkmale gleich — deckt sich mit `owand.md`.
- Befund 4 aus `handbuch-c.md`: „O“, „D“, „0“ per *Text aufbringen* auf dem
  20-mm-Würfel je 2 gerundete Seiten (innen/außen, `new_letters_od0.log`),
  am Ausgangsstand je 0 (`base_letters_od0.log`); örtlich nichts zusätzlich;
  *Schriftzug als Körper* trug sie schon.
- Leistung der Vollerkennung: Bericht plausibel (Gatter
  `MIN_FACE_AREA <= area < floor`), nicht nachgemessen.
- Sollwerte der Tests mit Herkunft (Innen/außen aus der Geometrie, 33,3 mm²
  gegen 43,2 mm² begründet).

## Läufe

- Gezielt + Pflichtliste, gepinnt `-n 6`, ohne Fenster (`run1.sh`):
  test_features, test_local_detection, test_local_recognition_flow, test_cache,
  test_recognition_regressions, test_examples, test_exact_body_parity,
  test_cut_features, test_feature_groups, test_toolchain, test_finding_ways,
  test_finding_actions, test_hard_rules, test_errors, test_core_isolation,
  test_core_package_direction, test_interface_limits, test_value_labels,
  test_shared_constants, test_language_rules, test_registry_consistency,
  test_text_length, test_changelog, test_directory_docs,
  test_platform_identity, test_translations, test_wording:
  **5042 passed, 5 skipped, EXIT=0** (214,8 s).
- `ruff check .` Exit 0, `ruff format --check .` Exit 0, `mypy` Exit 0
  (378 Dateien).
- Sonden: `probe_vesica.py`, `probe_letters.py`, `probe_plate.py`,
  `probe_perf.py`, alle Exit 0; Korpus `pe_compare.log` (Exit 1 wegen der zwei
  erwarteten neuen Merkmalsmengen), `pe_compare_fix.log`.

## Nachprüfung (Spitze b06c2b162 = Fix 66cb49276 + Merge welle5 4c93c1fe2), 12:47–12:52

**Urteil: kann landen.** Restfunde N1–N5 sind leicht und ohne weitere
Prüfung behebbar.

### Erledigt

- **S1 behoben.** `_bounded_by_planes` (`features.py`) liest nur die Nähte,
  die ein Fleckdreieck berühren, und nimmt als Beleg nur `sharp &
  planar[Gegenseite]` (`body.facets`); ein anderer Fleck zählt, was seine
  Dreiecke in `body.facets` sind, `crossing` ist weg. Die Prüfung der ebenen
  Flächen (`_facets_standing_apart_read`) ist mit e3f0c9dc9 identisch (Diff
  der Funktion leer). Kantenzählung (innen 2, Rand 1, Summe 3n) gleich der alten.
  Keine neue Lücke gefunden: ein leerer Fleck kommt nicht an (Gatter über
  `MIN_FACE_AREA`), offene oder verzweigte Kanten fallen über die
  Kantenzahl. `probe_vesica.py` am neuen Stand (`probe_new.log`, Exit 0):
  A voll = örtlich 2 × 50,13 mm², B 30,03 + 58,12 mm² beide, C beide leer.
- **M1 behoben, Gegentest echt.** Spion-Sonde `probe_spy.py` (`spy.log`):
  Der Ausschnitt (7 612 Dreiecke) antwortet für den 100,4-mm²-Fleck **ja**,
  der ganze Körper **nein** — der Test fährt genau die Schaber-Richtung, und
  mit der Ausschnittsschwelle in `is_complete` wäre `alone` nicht leer (rot).
- **M2 behoben, vertretbar.** `probe_perf.py` (`perf.log`, CPU, Takt 15,6 ms):
  370 388 Dreiecke 0–15,6 ms und 9,7 MiB je Frage; 4 812 960 Dreiecke 125 ms
  (erste Frage mit Maske), dann 62,5 ms, Spitze 126,0 MiB (vorher 390–500 ms,
  359,5 MiB). §31 nennt für die örtliche Suche keinen eigenen Wert; gegen
  „Erkennung 200 000 Dreiecke unter 1 s“ ist das am Referenzmaßstab unter
  16 ms, für große Importe gilt §31 „eigener Zeitbereich“. Kein Fund.
  `planar_members` ist schreibgeschützt (`flags.writeable = False`), in
  `SHARED_ANSWERS` richtig (reine Funktion der Geometrie, Kopien
  formgleich), `remembered` rechnet außerhalb des Schlosses und legt bei
  gleichzeitiger Frage dieselbe Antwort ab, die Antwort stirbt mit der
  Familie (`test_the_shared_answers_live_as_long_as_one_of_the_family`) —
  keine Faden- oder Lebensdauerfalle. Rest siehe N1, N2.
- **L1 behoben.** „Viele runde Wände kleiner Schrift, etwa die eines „O“ oder
  „D“ …“ — ehrlich (am Würfel O, D, 0, 8 je 2, B, 3 je 1, R 0; Begründung
  nennt es). Sechs Sprachen 161–182 Zeichen, Gruppe „Bearbeiten und
  Zeichnen“, Merge-Konflikt hält beide Seiten (`test_changelog` grün). Rest N4.
- **L2 behoben.** Eigene Überschrift „Eine ringsum scharf begrenzte gerundete
  Seite braucht keinen Anteil“ in Regel und `regel-schichtanalyse.md`, Karte
  verweist dorthin. Rest N5.
- **Korpus** (`pe_n2.sh`, 12 Beispiele, 7 Projekte, 4 Netze): gegen e3f0c9dc9
  21 von 23 druckgleich bei 0 µm, neu nur `dose-mit-deckel` +10 und
  `schild-zweifarbig` +16 `curve_N`, kein Merkmal weg; `weg3`,
  `generated_figure`, `generated_touching`, `clean_figure` unverändert. Gegen
  meine Variante „jeder Fleck allein“ alle 23 druckgleich
  (`pe_compare2_fix.log`) — die Feldrechnung entscheidet wie die Schleife.

### Restfunde

- **N1 leicht — Maske teurer als nötig.** `features.py:15141`
  (`_planar_members_read`) baut über `_facet_table` Besitzer, Rundungsmaske
  und `bincount`, die niemand liest. `probe_mask.py` (`mask.log`, 4 812 960
  Dreiecke): 78,1 ms CPU, Spitze 123,9 MiB; `mask[np.concatenate(body.facets)]
  = True` (leere Facettenliste abfangen) ergibt dieselbe Maske (`gleich:
  True`) in 15,6 ms, Spitze 41,3 MiB. Fix: schlanke Fassung.
- **N2 leicht — `planar_members` fehlt in `WHOLE_BODY_ANSWERS`**
  (`features.py:8175`). Ein Wert je Dreieck wie `facet_of_face`; so gilt die
  Grenze 4 096 statt 8 je Frage, und je lebendem großem Körper bleiben
  4,8 MB gemerkt. Fix: Eintrag ergänzen (`curved_faces` fehlt dort schon
  vorher — nicht von diesem Zweig).
- **N3 leicht — Spion-Wache zu weit.** `tests/test_local_detection.py:2168`
  `assert False in asked` besteht auch, wenn schon der Ausschnitt verwirft;
  dann prüfte der Test die Ganzkörperfrage nicht mehr. Heute echt (siehe M1).
  Fix: je Frage `len(body.faces)` mitschreiben und „Ausschnitt ja, ganzer
  Körper nein“ zusichern.
- **N4 leicht — Französisch ohne Ort.** `changelog/fr.md:203` „figurent aussi
  sur un grand corps comme *Face courbe*“ — die anderen fünf nennen den
  Objektbaum. Fix: „… sur un grand corps dans l'arbre des objets comme *Face
  courbe*.“ (unter 200 Zeichen).
- **N5 leicht — Regelsatz und Messzahl.** `.claude/rules/schichtanalyse.md:336`
  „Gerundete Haut hinter der Naht belegt nichts“ widerspricht dem Linsenfall,
  in dem ein koplanares Manteldreieckspaar belegt; besser „Belegt nur ein
  Dreieck aus `body.facets` — Rauschen ohne koplanare Paare belegt nichts“.
  `regel-schichtanalyse.md:1055-1056` „rund 30 ms“: hier 62,5–125 ms CPU
  gemessen — Spanne nennen.

### Läufe Nachprüfung

- Gezielt + Pflichtliste wie oben, gepinnt `-n 6`, ohne Fenster (`run2.sh`,
  `run2.log`): **5045 passed, 5 skipped, EXIT=0** (175,9 s; drei Tests mehr:
  Linse, Fase, weich).
- `ruff check .` Exit 0, `ruff format --check .` Exit 0, `mypy` Exit 0
  (378 Dateien), je am Stand b06c2b162.
