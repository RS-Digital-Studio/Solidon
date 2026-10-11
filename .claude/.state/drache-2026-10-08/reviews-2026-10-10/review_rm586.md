# Review RM-586 — Feine Schichten nach Detail (abgeschlossen 21:45)

Gegenstand: Worktree `F:\sl-schichten`, Zweig `einstellungen/schichten-rm586`, Stand `ff4e31e47`,
eigener Diff `git diff origin/welle4...ff4e31e47` (40 Dateien, +2028/−46). Basis `e734a0b44`
(= origin/welle4 = origin/main). Kein Tag `v0.6.0` vorhanden (`git tag -l "v0.6*"` leer).
Scratch: `scratchpad\rv586\`. Beginn 20:53 (Vorgänger abgebrochen), Neubeginn rv586 21:03.

## Urteil

**Nicht** — kann so nicht landen. Der Kern (Messung, Bereiche, Kurve, Übergabe, Gegenprobe)
arbeitet in allen lesenden Familien wie beschrieben und ist ohne feine Schichten druckgleich
(Übergabedateien bitgleich gegen `e734a0b44`). Aber ein eigener Vorschlag lässt PrusaSlicer
an Druckern mit Werkzeugwechsler oder MMU die ganze Platte verweigern (F1, schwer), die
Turmsperre trifft genau die mehrfarbigen Einzelkörper, die sie nicht bräuchten, mit einem Rat,
der nicht hinausführt (F2), und die Grenze hängt an der letzten Stelle von `math` (F7, Regel
`kern.md`). Nach den Fixes ist eine **Nachprüfung nötig** (ein schwerer und zwei mittlere
Funde; F1/F2 brauchen Slicerläufe am XL 2T und an Bambu/Elegoo mit Turm).

| Fund | Schwere | Kurz |
|---|---|---|
| F1 | schwer | PrusaSlicer (XL 2T, MK4S MMU3) verweigert jede Platte mit zwei Teilen, sobald eines feine Schichten hat — auch einfarbig |
| F2 | mittel | Turmsperre auch am Einzelkörper; Befund rät „eigene Platte“, das ändert nichts; Rat fehlt |
| F7 | mittel | Grenzwinkel über `math.atan2`/`math.cos`: Keil 1:2 bei 0,2/0,4 kippt mit einem ULP (670 mm² ↔ 0) |
| F3 | leicht | Slicertest sichert Bambus fehlende Lagenzählung zu (`counted is None`) |
| F4 | leicht | Zeitanteil gilt dem Teil, klingt nach dem Druck (12 % gegen +7–8 % der Platte) |
| F5 | leicht | Messskript nur im Scratch, Testkommentar zeigt dorthin |
| F6 | leicht | Prüfanleitung „an der Modellbahn“ aus der Regel gefallen (Wissen in der Begründung erhalten) |
| F8 | leicht | Wirksame Grenze Kuppe ab R ≈ 9 mm, nicht 4,1; Changelog „kleine Formen“ |
| F9 | leicht | 262 MB Spitze in `_shallow_faces` am Drachen (volle Felder vor der Auswahl) |
| F10 | leicht | es: „rejilla“ und „cuadrícula“ für dieselbe Stützart |

## Läufe

- Diffs neu gezogen (`n_*.txt`): Die Dateien des Vorgängers hatten einen anderen Zuschnitt, nur
  `diff_tests.txt` war gleich; gelesen wurde der neue Stand.
- Betroffene Tests, gepinnt, ohne Fenster/Renderer/Leistung/Slicer (`tests_lauf.sh`, 16 Dateien:
  `test_slice`, `test_advise`, `test_estimate`, `test_export`, `test_print_settings`,
  `test_slicer_part_settings`, `test_slicer_placement_writer`, `test_translations`,
  `test_wording`, `test_text_length`, `test_directory_docs`, `test_roadmap`, `test_changelog`,
  `test_shared_constants`, `test_language_rules`, `test_registry_consistency`):
  3958 passed, 28 skipped, EXIT=0.
- Sonden (alle gepinnt `FFFFF0FF`, Exit im Ausgabefile, alle `EXIT=0`): `run_r1.sh` (vier
  Familien, Kuppe + Klotz), `run_turm.sh` (Einzelkörper mit Turm, Bambu/Elegoo), `run_xl.sh`,
  `run_xl1.sh`, `run_mmu.sh` (PrusaSlicer mit Werkzeugen), `run_mehr.sh` (einfarbige Platte im
  mehrfarbigen Auftrag), `run_leistung.sh`, `run_gleich.sh` + `run_cura2.sh` (Basis gegen
  Zweig, Lauf gegen Lauf), `run_zeit.sh`, `run_ab.sh`; ungepinnt in-process `kuppen.py`,
  `rauschen.py`, `korpus.py` (Exit 0). Quellen der Slicer (`Print.cpp` Orca/Bambu/Prusa,
  `bbs_3mf.cpp`, `Slicing.cpp`) unter `scratchpad\rv586\src\`.
- Probemerge: `origin/welle4` ist Vorfahre von `ff4e31e47`; `git merge-tree --write-tree
  origin/welle4 ff4e31e47` ohne Konflikt, Baum = Baum des Zweigs (`c282c7d3a`). Gegen die
  übrigen offenen Zweige (nur zur Planung des Landens, keine Funde): Konflikte im Block mit
  `einstellungen/naht-rm588` (manufacturer, slicer_keys, print_fields, advise, types,
  Changelogs, Karte slice), `einstellungen/boegen-rm585` (Register, Archiv, Karte slice),
  `einstellungen/schacht-rm629` (Archiv, Karte slice), `paket/e-oertliche-erkennung`
  (Changelogs), `paket/gew-zollgewinde` und `claude/lauf-f` (Archiv); konfliktfrei mit
  `stuetzstil-nachtrag`, `paket/sparen`, `fix/ci-mapfile`.

## Funde

### F1 — schwer: PrusaSlicer mit mehreren Werkzeugen rechnet die Platte nicht mehr

`app/core/export/writer.py:3031–3120` (`_layer_heights`, Turmprüfung Z. 3082),
`writer.py:2590` (`towers`), `handover.py:3498–3543` (`_native_process`/`tower_cause` nur
Orca-Familie), `advise.py:2040–2044` (`whole_layers`).

Die Turmsperre kennt nur die Orca-Familie (`_native_process` gibt für `prusa` `{}`), also
schreibt die Übergabe an PrusaSlicer die Kurve auch dann, wenn die Platte mehrere Objekte mit
mehreren Werkzeugen trägt — und PrusaSlicer verlangt dann dieselbe Kurve an allen Objekten
(`Print::validate`, `WipeTowerDifferentObjectsVariableHeight`, Quelle `Print.cpp` Z. 870–940
in `scratchpad\rv586\src\prusa_Print.cpp`). Der Rat bietet die feinen Schichten dort auch an
(`whole_layers` ist für PrusaSlicer nie wahr).

Beleg (`scratchpad\rv586\prusa_xl.py`, Weg des Druckdialogs über `matrix_unit.plate_run`,
gepinnt): PrusaSlicer 2.9.6, „Original Prusa XL - 2T 0.4 nozzle“ (`wipe_tower = 1`,
`nozzle_diameter = 0.4,0.4`), Kuppe und Klotz aus `paar.3mf`, feine Schichten 0,1 (Kurve nur
an `object_id=2`).
- Zwei Spulen (`xl.txt`): Kontrolle ohne feine Schichten mit Turm (201 `;TYPE:Wipe tower`),
  T0/T1, 100 Lagen, 51,6 min. Mit feinen Schichten **kein G-Code**: `ExternalToolError`
  „Der Slicer hat den Auftrag nicht gerechnet.“, Ausgabe des Slicers „The Wipe tower is only
  supported if all objects have the same variable layer height“.
- **Eine Spule** (`xl1.txt`, `SONDE_EINE_SPULE=1`): Kontrolle einfarbig, kein Turm gedruckt,
  nur T0, 32,6 min. Mit feinen Schichten **derselbe Abbruch** — 2.9.6 prüft schon, wenn die
  Maschine mehrere Werkzeuge hat. Jede Platte mit zwei Teilen an einem XL mit Werkzeugwechsler
  scheitert also, sobald nur ein Teil feine Schichten bekommt, auch einfarbig.
- **MK4S MMU3, eine Spule** (`mmu.txt`, `SONDE_DRUCKER="Original Prusa MK4S MMU3 0.4
  nozzle"`): Kontrolle 18,4 min; mit feinen Schichten derselbe Abbruch, dieselbe Ausgabe.

Der Kunde sieht den Abbruch ohne Hinweis, dass seine (von Solidon vorgeschlagenen) feinen
Schichten ihn auslösen. Ursache liegt im Zweig (vorher keine Kurve).

Fix: Eine Auskunft „Turm mit mehreren Objekten auf dieser Platte“ für beide Familien, die Rat
(`_fine_layers`) und Übergabe (`_layer_heights`) gemeinsam fragen: Orca-Familie wie heute
`tower_cause`; PrusaSlicer `wipe_tower = 1` im aufgelösten Prozess und mehr als ein Werkzeug
der Maschine (2.9.6; master verlangt zusätzlich mehr als eine benutzte Spule, die strengere
Bedingung von 2.9.6 gilt); in beiden Fällen nur bei mehr als einem Objekt auf der Platte.
Dort keine Kurve, Befund `export.fine_layers_tower`, kein Rat. Test: Übergabe `prusa` an XL
2T mit zwei Körpern (eine Spule) schreibt keine Kurve und meldet den Befund; Slicertest am
XL 2T.

### F2 — mittel: Ein Körper allein auf seiner Platte verliert die feinen Schichten am Turm, mit falschem Rat

`writer.py:3082–3096` (Befund `export.fine_layers_tower`), `advise.py:2040–2044`
(`whole_layers`), Katalogtext „Neben „{name}“ steht ein Reinigungsturm, und der verlangt
gleiche Schichten für alle Teile. Auf einer eigenen Platte gelten die feinen.“

Die Slicer verlangen gleiche Kurven nur bei **mehreren** Objekten: OrcaSlicer
`Print.cpp` Z. 2343 (`if (m_objects.size() > 1)`, Abbruch Z. 2393), Bambu Studio Z. 1498/1552, PrusaSlicer Z. 870/933
(Quellen in `scratchpad\rv586\src\`). Die Übergabe lässt die Kurve aber an jedem Teil einer
Turmplatte weg, auch am einzigen, und der Rat bleibt dort ganz aus. Gerade ein mehrfarbiger
Einzelkörper (AMS, CFS) hat immer einen Turm; ihm sagt der Befund „Auf einer eigenen Platte
gelten die feinen“ — er steht schon allein, und eine eigene Platte ändert nichts, weil sein
eigener Turm bleibt. Kein Weg hinaus.

Beleg (`scratchpad\rv586\turm.py`, Halbkugel R 20 als ein Körper, obere Hälfte Spule 2,
feine Schichten 0,1, gepinnt): Bambu Studio (P1S) und ElegooSlicer (CC2) am Stand des Zweigs
je `warning:export.fine_layers_tower`, keine Kurve, 100 Lagen, 0 fein. Mit derselben Übergabe,
nur `_layer_heights` ohne Turmmenge: Kurve `object_id=1|…;17.8;0.1;20;0.1`, beide Programme
rechnen, **113 Lagen, davon 28 fein (0,1–0,176)**, der Turm bleibt (2 700 bzw. 15 130
Turmbahnen wie ohne Kurve), Werkzeugwechsel T0/T1, kein Fehler.

Fix: Die Kurve nur weglassen und den Rat nur sperren, wo auf der Turmplatte mehr als ein
Objekt steht (dieselbe Auskunft wie F1); der Satz dann „Neben „{name}“ stehen weitere Teile
und ein Reinigungsturm …“, und „auf einer eigenen Platte“ stimmt wieder. Test: ein bemalter
Körper allein mit zwei Spulen bekommt Kurve und Rat; zwei Körper auf der Turmplatte nicht.

### F7 — mittel: Die Schrägauswahl hängt an der letzten Stelle von `math`

`app/core/slice/fine_layers.py:83` (`math.atan2`/`math.degrees`), `:99` und `:151–152`
(`math.cos(math.radians(...))`). Die Grenze `steep` und `flat` entscheidet, welche Dreiecke
Stufen zählen, und daraus, welche Höhen fein werden — eine Entscheidung zwischen Flächen und
Lagen, die als Kurve in die Datei geht. `.claude/rules/kern.md`, „Dieselbe Datei, dasselbe
Teil — auf jeder Maschine“: „keine Winkel- und Exponentialfunktion aus NumPy oder `math`“.
Der Docstring von `_shallow_faces` sagt „Die Auswahl ist auf jeder Maschine dieselbe
(RM-187)“ — für die Rechnung im Feld stimmt das, für die Grenze nicht.

Beleg (`scratchpad\rv586\rauschen.py`, `platform_noise` aus `test_platform_identity.py`,
ein ULP auf `math`): Ein Keil mit Steigung 1:2 (ganzzahlige Ecken, wie aus CAD) liegt bei
Schicht 0,2 und Bahn 0,4 (oder 0,1/0,2) genau auf der Grenze `atan 0,5`. Still: Schräge
670,8 mm², Bereich 0–10,2 mm. Rauschmuster 1 und 3: **0 mm², kein Bereich** — auf einer
anderen Maschine bekäme derselbe Körper keine feinen Schichten oder umgekehrt, samt Rat und
Kurve. Bei Bahn 0,42 bleibt es gleich (kein Gleichstand). Bahn 0,4 entsteht mit jeder
Linienbreite 0,4 (Feld `layers.line_width` oder Herstellerprozess; `for_process` nimmt sie
als `extrusion_width`) — in 138 Prozessprofilen von OrcaSlicer steht `"line_width": "0.4"`,
darunter „0.20mm Standard @Anycubic Kobra“: genau 0,2/0,4.

Fix: ohne Winkel rechnen — `steep² = Bahn² / (Bahn² + h²)`, verglichen als
`lifted · (Bahn² + h²) > Bahn² · squared`; `flat` über `units.exact_cos_degrees(FLAT_SLOPE)`;
`stepped_area_worth` mit `1 − Bahn / math.sqrt(Bahn² + h²)` (`math.sqrt` ist zugelassen).
`step_slope` in Grad bleibt für Anzeige und Tests. Dazu der Weg „feine Schichten“ (Keil 1:2
bei 0,2/0,4, Kurve als Fingerabdruck) in `_WAYS` von `tests/test_platform_identity.py`, wie
die Regel es für jeden neuen Weg verlangt; der Test ist am heutigen Stand rot.

### F3 — leicht: Der Slicertest schreibt die fehlende Lagenzählung in Bambu Studio fest

`tests/test_real_slicers.py:1940–1941` (`test_fine_layers_arrive_where_solidon_says`):
`if program == "bambustudio": assert counted is None`. Das prüft den Ist-Zustand (der
G-Code-Leser zählt Bambus Modelllagen nicht, Bericht rm586 „Neue Punkte“ 4), nicht die
Zusage: Wer den Leser repariert, bekommt diesen Test rot (`.claude/rules/tests.md`, „Prüft
dieser Test eine Zusage — oder den Ist-Zustand?“). Fix: `if counted is not None:` die
Abweichungsgrenze prüfen, sonst nichts zusichern; die Lücke selbst als neuer Punkt ins
Register (Koordinator).

### F4 — leicht: Der Zeitanteil im Grund gilt dem Teil, klingt aber nach dem Druck

`advise.py:2073–2081` („Glattere Kuppen und Details, rund {share} % mehr Druckzeit.“),
`fine_layers.extra_time` rechnet über die Schichten **eines** Teils. Auf einer Platte mit
weiteren Teilen wächst der Druck um weniger. Beleg R1 (`scratchpad\rv586\r1\fein.json`,
Kuppe + Klotz, gepinnt): Grund 12 % (Elegoo, Bambu) bzw. 10 % (PrusaSlicer), Druckdatei
der Platte +8,0 % (ElegooSlicer 17,6 → 19,0 min), +6,9 % (Bambu Studio 20,3 → 21,7),
+13,1 % (PrusaSlicer 17,6 → 19,9, mit Deckschicht 0,8). Fix: „… rund {share} % mehr
Druckzeit für dieses Teil“ (sechs Kataloge, ≤ 70 Zeichen je Tabellenzeile prüft
`test_every_reason_fits_under_the_table_of_the_print_dialog`), oder den Anteil über die
Schichten der Platte rechnen.

### F5 — leicht: Messskript nur im Scratch, der Test verweist dorthin

`tests/test_slicer_part_settings.py:617` (Kommentar über `MEASURED_PART_PATHS`):
„``scratchpad/rm586/slicer_fein.py``“. Das liegt nur unter `%TEMP%` dieser Maschine; die
übrigen Messungen derselben Liste liegen versioniert unter `.claude/.state/drache-2026-10-08/`
(`kontakt_je_teil.py`, `bruecken_je_teil.py`). Auf den anderen zwei Rechnern ist das ein
Verweis ins Leere. Fix: `slicer_fein.py` nach `.claude/.state/drache-2026-10-08/` legen und
Kommentar wie Archiv darauf zeigen lassen.

### F6 — leicht: Die Regel verliert die Prüfanleitung für Sperren

`.claude/rules/dateiformat.md:226–230`. Gestrichen: „Jede Familie druckt die fremde
Schreibweise als Kunststoff — geprüft wird an der **Modellbahn** mit und ohne Sperre, nicht an
der Stütze.“ Das Wissen ist **nicht verloren**: Es steht unverändert (schon vor dem Zweig) in
`konzepte/begruendungen/regel-dateiformat.md:309–313`. Verschoben ist aber die Stolperfalle
für jeden, der eine Sperre prüft — sie lädt nicht mehr mit der Regel. Die Regel steht bei
30 682 von 30 720 Byte. Fix: den Halbsatz „geprüft an der Modellbahn, nicht an der Stütze“
behalten und dafür die neue Zeile straffen; dort ohnehin „nicht unter **organischen**
Bäumen“ (unter `tree_slim`/`tree_strong`/`tree_hybrid` nimmt OrcaSlicer die Kurve an,
Begründung Z. 388) und „am Turm“ nach F1/F2 neu fassen.

### F8 — leicht: Die hergeleitete Schwelle greift nicht, und der Changelog verspricht „kleine Formen“

`fine_layers.py:86–100` (`stepped_area_worth`: „die kleinste Kuppe, auf der zwei Stufen
liegen … 4,1 mm … Was darunter bleibt, sind einzelne kleine Dreiecke“), `:300` (Bereich
kürzer als ein Übergang fällt), Begründung `regel-druckrat.md` („Kleinste Kuppe mit zwei
Stufen … 4,12 mm“), `changelog/*.md` („Wo flache Kuppen und **kleine Formen** Stufen zeigen
würden …“).

Beleg (`scratchpad\rv586\kuppen.py`, Halbkugeln, Kurve über `profile_for`): bei 0,2 mm
Schicht bekommen R 6 und **R 8** keine Kurve, erst ab R 9; bei 0,28 ab R 8 (Herleitung:
4,12 bzw. 3,33 mm). Die Fläche reicht bei R 8 (die Kappe trägt 39 mm² in einem Übergang,
Schwelle 25,9), aber ihr Bereich ist 0,8 mm lang und fällt unter die Mindestlänge eines
Übergangs (1 mm). Die wirksame Grenze ist also die Mindestlänge, nicht die Herleitung; Augen,
Knöpfe und Schuppen unter etwa 18 mm Durchmesser bleiben gleichmäßig. Ob das gewollt ist, ist
eine Produktfrage; falsch sind heute Docstring, Begründung und der Changelog-Satz. Fix
mindestens: Docstring und Begründung nennen die wirksame Grenze (Kuppe ab R ≈ 9 mm bei
0,2 mm), der Changelog sagt „flache Kuppen und Schrägen“ statt „kleine Formen“ (sechs
Sprachen). Wer mehr will: Mindestlänge an `STEPS_SEEN · h` statt an den Übergang binden und
am Drachen neu messen.

### F10 — leicht: Zwei Wörter für „Gitter“ im spanischen Katalog

`app/i18n/locales/es.json`: Der Satz am Feld sagt „soportes de **rejilla**“, der Befund der
Übergabe „soportes en **cuadrícula**“; die Stützart selbst heißt dort „Cuadrícula“ („Gitter“).
Der Kunde liest zwei Namen für dieselbe Wahl. Fix: „Con soportes en cuadrícula valen las capas
finas.“ (fr, it, pt sind einheitlich: grille, griglia, grelha).

## Leistung (CPU, gepinnt, unter Fremdlast; `scratchpad\rv586\leistung.py`)

| Körper | Dreiecke | `slice_body` voll, CPU | `stepped_areas` CPU (3×) | Anteil | Spitze `stepped_areas` | `profile_for` | `extra_time` |
|---|---|---|---|---|---|---|---|
| Kuppe R 20 | 10 494 | 0,14 s | < 0,016 s | — | 1,3 MB | < 0,016 s | < 0,016 s |
| Eiffelturm | 312 970 | 29,3 s | 0,06/0,03/0,05 s | 0,16 % | 28,6 MB | 0,06 s | 0,31 s |
| Drache | 2 948 698 | 47,5 s | 0,52/0,45/0,56 s | 1,1 % | **262 MB** | 0,58 s | 0,11 s |

Der Schnitt selbst ist sonst unverändert (der Diff in `slice_body` ist nur der Aufruf und
ein Feld im `zip`); vorher = nachher minus `stepped_areas`. Die CPU-Kosten sind klein
(Bauagent: 1,1 s/2 %, hier 0,5 s/1,1 %). Die Spitze von 262 MB am Drachen liegt kurz über dem
Schnitt: `_shallow_faces` hält drei Koordinatenspalten (je 1,47 Mio.) und fünf Felder über alle
2,95 Mio. Dreiecke, bevor es auf die aufwärts weisenden einschränkt. Nach AUFTRAG („Sicht statt
Kopie, Zwischenstände früh freigeben“) im eigenen Gebiet umzusetzen: `ux, uy, wx, wy` gleich
nach `rise` auf `up` einschränken (die vollen Felder fallen), oder in Blöcken rechnen —
gleiche Auswahl, bitgleich prüfbar mit `test_the_shallow_faces_are_those_of_the_stable_normals`.
Als **F9 — leicht** geführt.

Bereiche am Drachen (Raster 0,2/0,2, Bahn 0,42): 2,0–15,2 · 41,6–43,8 · 70,0–78,4 ·
111,4–118,0 mm, Anteil 27,5 %, 650 → 817 Lagen — deckt sich mit dem Archiv (Bauagent mit
Elegoo-Bahn: 2,1–15,1 · 41,7–43,9 · 70,1–78,5 · 111,5–117,9). Eiffelturm 23,0–33,4 ·
37,2–39,6 · 43,0–44,0 · 161–162 mm (wie Archiv), Anteil 25,9 %.

## Grenzfälle (in-process, `leistung.py`, `kuppen.py`)

- Kleine Kuppen R 3/5/6/8: keine Kurve (siehe F8); R 20: fein ab 17,8 mm.
- Gedreht: Halbkugel R 20 um 30° gekippt fein 27,8–30 mm, auf der Seite 38–40 mm — immer der
  flache Scheitel oben, plausibel.
- Platte 0,3 mm (erste Schicht 0,2): keine Kurve. Raft: Kurve beginnt `(0, 0,2)` wie
  PrusaSlicer mit Raft (`first_object_layer_height = layer_height`, `Slicing.cpp`).
- Schwebendes Teil (Unterkante 5 mm): dieselbe Kurve wie auf dem Bett.
- Schicht nahe der Düse: `fine_height` 0,32/0,4 → 0,16; 0,3 → 0,15; 0,16 → 0,1; 0,13 und
  0,12 → keine; 0,1/0,2 → 0,05; 0,12/0,25 → 0,062; 0,4/0,6 → 0,2. Kuppe bei 0,32/0,16: fein
  15,68–19,84, das letzte Stück bis 20,0 rampt zurück — die gedruckte Oberkante liegt wie ohne
  Kurve eine Teilschicht unter der Spitze (19,87 statt 19,84), kein Fund.
- Mehrere Teile je Platte: R1 unten, Kuppe fein, Klotz gleichmäßig, `object_id` stimmt
  (Orca legt Objekte je Bauteil an, `bbs_3mf.cpp` `_create_object_instance`; Sperren als
  Komponenten zählen nicht mit).
- Korpus `tests/data/meshes` (`korpus.py`, 38 STL, 0,2/0,1, Bahn 0,42): Kurve nur an
  `clean_figure` (61,6–63,0 und 81–82 mm, Schultern/Kopf), `post_with_fillet` (5,6–6,6 mm,
  Hohlkehle am Fuß) und `torus_ring` (8,8–10 mm, Scheitel). Keine an Würfel, Platten, Fasen,
  Senkungen, Bohrungen, Zylindern — keine falsche Feinheit an technischen Teilen.
  `near_sphere_ellipsoid` (Höhe 16,6, R ≈ 8,3) bleibt gleichmäßig wie in F8.
- Einfarbige Platte in einem zweifarbigen Auftrag (`mehrplatten.py`: Platte 0 Kuppe + Klotz
  in Spule 1, Platte 1 ein Klotz in Spule 2): Bambu Studio und ElegooSlicer bekommen für
  Platte 0 nur „Solidon Weiß“, kein Turm, Kurve angenommen, 129 Lagen. Kein Fund — die
  Turmfrage je Platte stimmt dort.

## Slicerläufe (gepinnt, Weg des Druckdialogs)

R1 (`scratchpad\rv586\run_r1.sh`, `slicer_fein.py` des Bauagenten unverändert kopiert, Kuppe +
Klotz, EXIT=0): ElegooSlicer (CC2) und Bambu Studio (P1S): Kuppe 113 Lagen, 28 fein
(0,1–0,176) von 17,0 bis 20,02, Klotz 100 Lagen gleichmäßig; PrusaSlicer 2.9.6 (MK4S):
Kuppe 113 Lagen, fein 17,2–20,025, Klotz gleichmäßig, `top_solid_min_thickness = 0.8` nur an
der Kuppe, dünne Füllung bis 19,225 statt 19,325; Cura (SV06, feine Höhe erzwungen): keine
Kurve, 100 Lagen, 63,2 min wie ohne. Keine Warnung „Modellschichten weichen ab“ in der
Gegenprobe. Turmsonde und XL-Sonde: F1, F2.

## Changelog (Wortlaut)

Längen (Zeichen, Punkt 1/2): de 156/134, en 148/115, es 150/141, fr 174/149, it 148/145,
pt 151/146 — alle ≤ 200. Kein Wort der Testfamilie, Großbuchstabe am Anfang, Eigenschaft
statt Behebung (die Ursachen B2/B5 lagen nur im Zweig, kein Tag enthält sie; `v0.6*` gibt es
noch nicht). Liest sich nicht nach KI. Einziger Mangel: „kleine Formen“ (F8). Die Lage unter
`## 0.6.1` ist bekannt.

## Regeln, Karten, Register

- Harte Regeln: 1 (kein Qt in `fine_layers.py`), 6 (kein `==` auf Gleitkomma im Kern), 10,
  11, 13, 20 (alle Texte über `_()`, sechs Kataloge, `test_translations` grün), 22 (keine
  Abhängigkeit) eingehalten. Kein Op, kein Baustein, keine Ausnahme neu (4, 17). `kern.md`
  verletzt: F7.
- Projektformat: Die zwei neuen Felder reisen in `print_settings` mit; ein älterer Leser
  übergeht unbekannte Schlüssel (`serialise._group_from_data`), ein neuer füllt fehlende mit
  null — keine `format_version` nötig, wie bei den Feldern davor. Kein `cache_version`
  berührt: Kein Op ändert sich, `SliceResult` lebt nur im Merker des Netzes.
- Budgets (`test_directory_docs` grün): `dateiformat.md` 30 682/30 720 B,
  `app/core/export/CLAUDE.md` 25 369/25 600 B — jede Ergänzung durch F1/F2 braucht eine
  Verschiebung. Verschoben (nicht verloren): Curas Anzeigename nach
  `karte-app-core-export.md`, die Sperren-Prüfanleitung lag schon in der Begründung (F6).
- Register/Archiv (`test_roadmap` grün): RM-586 aus dem Register, Archiv mit Index-Zeile und
  Anker. Das Archiv verweist auf `berichte-2026-10-10/rm586.md` — im Hauptbaum noch
  unversioniert; der Koordinator muss ihn mitnehmen. Die „Neuen Punkte“ 1–6 des Bauberichts
  haben keine Nummer (richtig nach AUFTRAG) und gehören ins Register.

## Druckgleich ohne feine Schichten (Basis `e734a0b44` gegen Zweig, gepinnt)

Wegwerf-Worktree `scratchpad\rv586\basis` (detached `e734a0b44`), `gleich.py` je Baum: Weg des
Druckdialogs mit der Grundlage des Herstellers, nichts übernommen; verglichen Rat (Pfad, Wert,
Grund, Teile — ohne die zwei neuen Pfade), Befunde, Schätzung, Stützmengen und die
geschriebene Datei je Zip-Eintrag (SHA-256), dazu der G-Code.

| Modell | ElegooSlicer CC2 | Bambu P1S | PrusaSlicer MK4S | Cura SV06 |
|---|---|---|---|---|
| Kuppe + Klotz | gleich | gleich | Datei, Rat, Zeit gleich; G-Code nur Objektfolge (`M486`, `objects_info`) | STL, Netzliste gleich; G-Code ab Lage 75 anders |
| Pilz | Datei, Rat gleich; G-Code nur Objektkennung (`id:0` gegen `id:1542946248960`) | gleich | gleich | STL, Rat, Zeit gleich; G-Code anders wie Lauf gegen Lauf |

Gegenprobe Lauf gegen Lauf am **selben** Basisstand (`gleich_basis2`): PrusaSlicer 406
Zeilen (dieselbe Objektfolge), CuraEngine 21 364 Zeilen — beide Programme sind von Lauf zu
Lauf nicht gleich; die Unterschiede Basis/Zweig liegen darin, die Eingaben sind bitgleich.
Neu im Zweig ist nur der Rat (Kuppe: `layers.fine_layer_height 0.1`, bei PrusaSlicer dazu
`shell.top_thickness 0.8`). Größte Abweichung druckgleich: keine (Übergabedateien bitgleich).

Zeit Basis gegen Zweig im Wechsel (`run_zeit.sh`, je Lauf eigener Prozess, `slice_body` voll,
0,2/0,2, CPU): Eiffelturm Basis 27,27 / 22,28 s, Zweig 28,48 / 24,45 s; Drache Basis 52,17 /
47,70 s, Zweig 50,27 / 50,53 s. Die Basis allein streut um 18 % (Fremdlast vieler Agenten);
der Unterschied liegt darin. Im selben Prozess im Wechsel (`ab.py`, `stepped_areas` gegen
Nullen getauscht, Eiffelturm, 3 Runden): ohne 30,05 / 27,38 / 27,56 s, mit 28,42 / 27,33 /
28,25 s — Differenzen je Runde −1,63 / −0,05 / +0,69 s, kein gerichteter Unterschied; die
direkte Messung (0,03–0,06 s) ist die belastbare Zahl. Ergebnis: CPU-Mehrkosten des Zweigs
≤ 1,1 % des Schnitts, Speicher siehe F9. Der Wegwerf-Worktree ist wieder abgebaut
(`git worktree remove`, Exit 0).
