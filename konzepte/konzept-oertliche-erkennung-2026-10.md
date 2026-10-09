# Konzept: Örtliche Neuerkennung nach einem Schritt

Stand 09.10.2026, gemessen an main `0b4bdae40` (an `perceive/`, `scene/evaluate.py`,
`geom/attributes.py`, `geom/boolean.py` und `units.py` unverändert seit `190a9e1a8`).
Registerpunkt [RM-592](../ROADMAP.md#rm-592) (vom Koordinator vergeben). **In Umsetzung als
Paket E** (Zweig `paket/e-oertliche-erkennung`); Nachträge stehen am Ende, Sonden, Messbank
und Messwerte in [`nachweise-oertliche-erkennung-2026-10/`](nachweise-oertliche-erkennung-2026-10/README.md). Auftrag Robert 08.10.2026 („Ja, mit
Konzept zuerst“), Anlass Paket L, Rangliste Tempo Punkt 4 und neuer Punkt 2. Paket L liegt
noch auf `paket/l-leistung`; wo der Entwurf darauf baut, steht es dabei. Laptop-Ständer
und Riser sind dasselbe Modell (`parametric-laptop-riser.stl`, 173 592 Dreiecke).

**Ergebnis vorweg.** Bauen, aber nicht als Ausschnitt mit Rand, sondern als
**Gedächtnis je Fleck**: Die Vollerkennung läuft weiter über den ganzen Körper, in
derselben Reihenfolge; jede teure Frage an einen Fleck antwortet aus dem Gedächtnis,
wenn alles, was sie liest, Bit für Bit dasselbe ist wie an einem früheren Körper. Was
sich geändert hat, verfehlt das Gedächtnis von selbst und wird gerechnet. Gleichheit
ist damit eine Eigenschaft der Bauart, kein Nachweis je Fall, und der Bauplan bleibt,
wie er ist. Ein Wegwerf-Prototyp der ersten Stufe (Lesung und tangentiale Trennung je
Fleck) spart am Laptop-Ständer 23 %, am Eiffelturm 27 % und am Spiderman 19 % der
heutigen Erkennung nach einem Schritt, mit Bit für Bit demselben Ergebnis wie die kalte
Vollerkennung. Mit allen Stufen geschätzt, unbelastet umgerechnet: Ständer von etwa 6 auf
etwa 3,5 s, Eiffelturm von etwa 21 auf etwa 8,5 s, Spiderman von etwa 13 auf etwa 9 s. Kein
Gewinn nach einem vorangegangenen Verschieben oder Drehen und keiner beim Laden — beides
begründet in §7.

## 1. Das Problem

Wer in ein geladenes Modell eine Bohrung setzt, eine Tasche abzieht oder ein Merkmal
versetzt, wartet nach *Übernehmen* auf die Merkmalserkennung fast so lange, als wäre
das Teil neu geladen: am Laptop-Ständer rund sechs Sekunden, am Eiffelturm rund zwanzig,
nach einem Verschieben davor so lange wie beim Laden. Geändert hat sich dabei
weniger als ein Prozent der Oberfläche.

## 2. Hauptweg

Weg 1, „Operation wählen → Vorschau → übernehmen“ (§2.2): Die Vorschau rechnet ohne
Erkennung (`detect_features=False`), das Übernehmen in voller Güte mit Erkennung
(`scene/evaluate.py:4867`). An derselben Stelle wartet Weg 2 beim Einsetzen von
Bausteinen und jeder Klick auf *Merkmal ändern, versetzen, entfernen*. Weg 3 und 4
kaum: Freiformen tragen wenige Merkmale, und Umvernetzen ändert ohnehin alles.

## 3. Verortung im Bauplan

- **§21.1** „seine Folgeschritte erkennen bis 5 000 000 Dreiecken vollständig nach“
  (Z. 1567–1569). Der Entwurf hält den Satz wörtlich: Es läuft die vollständige
  Erkennung, sie antwortet nur dort aus dem Gedächtnis, wo sie dieselbe Frage schon an
  dieselben Bits gestellt hat. Ein Ausschnitt mit Rand hielte ihn nicht; RM-261 hat das
  schon als Bauplanänderung benannt (`ROADMAP-ARCHIV.md`, RM-261).
- **§21.2** Zuordnung über `match`, `settled_twins`, `apply_mapping`: unberührt, weil
  ihre Eingabe dieselbe bleibt.
- **§15.1 und §15.7** „Zweimal ausgewertet ergibt zweimal dasselbe“, auch „nach
  Speichern, Öffnen und ohne Cache“. Daraus folgt die Messlatte: **Ein Treffer ist von
  einer Rechnung nicht zu unterscheiden.** Präzedenz: Der Teilungsvermerk reist über die
  Platte, denn ohne ihn „trug dasselbe Dokument je nach Cache zwei Merkmalsstände“
  (`konzepte/begruendungen/karte-app-core-perceive.md`, Z. 333–337).
- **§31** „Parameteränderung → sichtbares Ergebnis unter 2 s, nur betroffene Zweige“
  ist die Zeile, auf die der Entwurf zielt. „Feature-Erkennung, 200 000 Dreiecke,
  mechanisch unter 1 s“ gilt dem Laden und bleibt ein eigener Punkt (Paket L,
  Rangliste Tempo 4).
- Leitprinzipien 4 (reproduzierbar) und 6 (nie raten). Regeln: `kern.md` „Über die
  Körpergrenze merkt sich nur, wer außer seiner Lesung nichts liest“, „Eine neue
  gemerkte Frage wird geteilt oder gebunden“, „Dieselbe Datei, dasselbe Teil — auf
  jeder Maschine“; `schichtanalyse.md` „Stabile IDs“.
- Verträge: `detect(mesh) -> dict[FeatureId, Feature]` (`perceive/features.py:1400`),
  `Feature`, `_SurfaceSupport` (7198). Kein neuer Vertrag nach außen, keine neue Op,
  kein neuer Baustein.

## 4. Ist-Aufnahme

### 4.1 Wo die Erkennung läuft

| Stufe | Ort | Was sie tut |
|---|---|---|
| Einstieg je Ausgabe | `scene/evaluate.py:4220` `_with_features` | über 1,5 Mio. Dreiecken `_measured_locally` (3962: bekannte Merkmale nachmessen, nicht gleich der Vollerkennung); darunter erst Übertrag, dann `detect` (4867) |
| Übertrag bewegt, fein geteilt | `evaluate.py:4791`, `4793` | `carry_detection`, `carry_refined_detection`: Merkmale des Eingangs, nur mit Beleg (`moved_twin`, `refined_twin`) |
| Ganzes Netz bitgleich | `features.py:1185` `_mesh_key`, `1115` `_FEATURE_CACHE` | Treffer nur bei denselben Ecken und Dreiecken in derselben Folge |
| Vollerkennung | `features.py:1400` `detect` | `_one_body` → `_large_facet_faces` (6071) → `_fitted` (2542) → Kugeln, Ringe → Bohrungen bis Kantenzüge → Gewinde → Langlöcher (`slots.py:284`) → Muster → `_faces_finished_in` → Einschlüsse → Kegelstücke, Eckverrundungen, Verengungen → `is_a_freeform` (2346) → gerundete Seiten |
| Merker je Körper | `features.py:7657` `remembered` | Antworten leben mit dem Körper; der nächste Körper fängt von vorn an |
| Merker über die Körpergrenze (RM-261) | `features.py:7768` `GEOMETRY_KEYED_ANSWERS`, `7791` `_by_geometry` | genau sieben Fragen — vier Einpassungen, drei Nachweise —, Schlüssel ist der Abdruck der Stützpunktlesung (`_read_surface_support` 8012, Abdruck 8186) |
| Darstellung des Eingangs | `geom/attributes.py:259` `in_source_layout` | übernommene Dreiecke behalten Eckenfolge und Eckennummern des Eingangs, die Dreiecksfolge bleibt die des Kerns: `_mesh_key` trifft deshalb nie, die Lesung je Fleck schon |
| Zuordnung | `evaluate.py:5420` `match`, `settled_twins`, `apply_mapping` | Namen nach §21.2 |

### 4.2 Was sie kostet

Zwei Sonden, beide nur lesend am Hauptbaum (Anhang A). `probe_local.py` lädt wie
`probe_core.py` aus Paket L, zieht einen senkrechten Zylinder Ø 6 durch eine nach oben
weisende Fläche ab und misst die Erkennung des Ergebnisses je Stufe, dazu Treffer und
Rechnungen jeder gemerkten Frage. `probe_floor.py` erkennt dasselbe Netz mit zwei
vertauschten Dreiecken — die kleinste denkbare Änderung, also die Untergrenze dessen,
was der heutige Merker erreicht. CPU-Sekunden auf Roberts i9-13900K **unter starker
Fremdlast** (77 % Prozessorlast, über fünfzig fremde Python-Prozesse); Kaltwerte liegen
beim 1,4- bis 2-Fachen der ruhigen Paket-L-Werte. Belastbar sind Verhältnisse und
Zählerstände, die ruhigen Absolutwerte misst P0 nach.

| Modell | Fall | neue Dreiecke | kalt | nach dem Schritt | Anteil | Einpassungen aus dem Merker |
|---|---|---|---|---|---|---|
| Laptop-Ständer 173 592 | Ø 6 bei (−87,9; −6,8) | 396 (0,2 %) | 18,1 s | 8,8 s | 49 % | 99 % |
| Laptop-Ständer | zwei Dreiecke vertauscht | 0 | 21,0 s | 12,1 s | 58 % | 100 % |
| Laptop-Ständer | Paket-L-Fall: dx 5 verschoben, Zylinder bei (0; 0) trifft nichts | 0 | 20,8 s | 20,7 s | 99 % | 0 % |
| Eiffelturm 312 938 | Ø 6 bei (−34,2; 2,1) | 2 170 (0,7 %) | 54,8 s | 36,6 s | 67 % | 96–97 % |
| Eiffelturm | zwei Dreiecke vertauscht | 0 | 54,5 s | 36,2 s | 66 % | 100 % |
| Spiderman 885 570 | zwei Dreiecke vertauscht | 0 | 24,5 s | 19,2 s | 78 % | 100 % (26 Flecken) |

Am Spiderman ließ sich kein Zylinder abziehen: an beiden versuchten Stellen „Der Schritt
trifft ein Teil, dessen Oberfläche sich selbst kreuzt“, auch nach *Reparieren* (das alle
885 570 Dreiecke unverändert ließ); am Ständer ebenso an drei von vier Stellen. Das ist die
geltende Entscheidung `CROSSING_SHELL_IN_THE_WAY` und hier kein Befund; es erklärt nur,
warum der Spiderman allein mit der Untergrenze gemessen ist.

Was daraus folgt:

1. **Die Zahlen aus Paket L waren Kaltfälle.** Die Sonde verschob jeden Körper vor dem
   Abziehen, und am Ständer traf der Zylinder bei (0; 0) gar nicht — jedes Dreieck
   bitgleich, trotzdem volle Erkennung. Gemessen war, was nach einem Verschieben
   geschieht, nicht nach einer Bohrung.
2. **Ohne Verschieben trifft der Merker aus RM-261 fast jede Einpassung**, und die
   Erkennung kostet trotzdem die Hälfte bis drei Viertel eines Kaltlaufs — auch wenn sich
   nichts geändert hat. Der Rest der Kette hat kein Gedächtnis über den Körper hinaus.
3. **Nach jeder starren Bewegung trifft nichts mehr** — Verschieben, Drehen, *Auf das
   Bett setzen* mit Weg, *Auf dem Bett anordnen*, *Druckoptimal ausrichten*: Der Schlüssel ist Bit für
   Bit, und eine Bewegung ändert jede Koordinate.
4. **Eine Boolesche ohne Wirkung erkennt voll**: Die Dreiecksfolge des Kerns ändert den
   Netzabdruck, auch wenn jedes Dreieck dasselbe ist.
5. **Ein Fleck reicht weit.** Die Bohrung am Ständer berührt 16 von 164 gekrümmten
   Flecken, aber 43 501 von 164 460 Dreiecken; am Eiffelturm 81 von 1 551 Flecken mit
   86 570 von 262 984 Dreiecken. Wer je Fleck neu rechnet, rechnet wenige Flecken, aber
   große.

Wohin die Zeit nach dem Schritt geht (CPU-s, dieselben Läufe; Posten verschachtelt,
die Summe ist nicht die Gesamtzeit):

| Posten | Ständer (Bohrung) | Eiffel (Bohrung) | Spiderman (vertauscht) | Bauart |
|---|---|---|---|---|
| `_tangential_pieces` (sechste Runde, je Ziel) | 1,6 | 8,4 | – | je Fleck |
| `_read_surface_support` | 0,95 (680 Lesungen) | 2,4 (1 989) | 5,9 (26) | je Fleck |
| übrige Einpassungsrunden in `_fitted` | ≈ 1 | ≈ 3–4 | ≈ 4 | je Fleck, liest die Hülle |
| `slots_instead_of_half_bores` | 1,7 | 5,6 | – | je Bogen und Paar, liest Schalen |
| `_faces_finished_in` | 0,05 | 4,2 | – | je Fläche, liest die Innenlage |
| `_large_facet_faces` | 0,9 | 4,1 | 6,6 | Facetten des ganzen Körpers |
| `_merged_cylinders` | 0,06 | 2,7 | – | über Flecken |
| `find_helices` | 0,8 | 1,6 | 0,3 | ganzer Körper |
| `patterns_instead_of_cells` | 0,1 | 1,3 | – | Felder |
| `curvature_jumps` | 0,5 | 1,1 | 1,1 | ganzer Körper |
| `_connected_patches` | 0,4 | 1,0 | 3,5 | ganzer Körper |
| `detect_holes` | 0,8 | 0,3 | – | Durchsicht durch ferne Wände |

### 4.3 Was am ganzen Körper hängt

Diese Stellen machen einen Ausschnitt ungleich der Vollerkennung:

- **Toleranz aus der Diagonale:** `weld_tolerance(d) = d · 1e-6` (`units.py:285`),
  gelesen in `features.py:3669, 6845, 7024, 8501, 8641, 9404, 9550, 11289–11291`. Ändert
  ein Schritt die Ausdehnung, ändert sich jede Toleranz in den letzten Stellen.
- **Gesamtoberfläche:** breite Ebene `body.area · BROAD_FACE_SHARE` (6183), gerundete
  Seite `body.area · CURVED_SIDE_SHARE` (13506), Splitter und Haut über `total_area`
  (2615–2827).
- **Hülle:** `_fits_in_the_body` → `cylinder_fits_in_the_body` (3177, 3213), auch in der
  tangentialen Trennung (11439).
- **Dichtheit und Umlauf des ganzen Netzes** in der Lesung (8126) und bei Einschlüssen
  (14376).
- **Durchsicht durch ferne Wände:** `_is_through` (9799).
- **Urteile und Ordnungen über alles:** `is_a_freeform` (2346); Fleckfolge nach Größe
  `_in_size_order` (12613) samt dem geteilten „kein Kegel“ deckungsgleicher Flecken
  (`no_cone_here`, 2628–2665); Nummernfolge `numbering_order` (13572).
- **Über Flecken hinweg:** `_merged_cylinders` (3065), `find_helices` (3088),
  Langlöcher (Schalen je Paar über das ganze Netz), Muster, Innenlage einer Fläche.

Ein Ausschnitt sieht eine andere Diagonale, Fläche und Hülle und keine fernen Wände.
`detect_local` und `detect_known` (`local.py:1181`, `1408`) zeigen, wohin Gleichheit am
Ausschnitt führt: Sie veröffentlichen nur vollständig Belegtes und halten am Suchrand
an — richtig über 1,5 Mio. Dreiecken, aber nicht gleich der Vollerkennung.

## 5. Entwurf

### 5.1 Grundsatz

Die Vollerkennung bleibt die eine Rechnung: dieselben Stufen, dieselbe Reihenfolge,
über den ganzen Körper, mit allen Ganzkörperfragen aus 4.3. Neu ist, dass weitere
Fragen je Fleck über die Körpergrenze antworten — nach dem Vertrag, den RM-261 für sieben
Fragen eingeführt hat: Der Schlüssel enthält alles, was die Frage liest, Bit für Bit,
ohne Toleranz. Ein Treffer gibt zurück, was die Rechnung zurückgäbe; ein Fehlgriff
rechnet. Es gibt keinen Bereich, keinen Rand als Längenmaß und keinen Rückfall als
Sonderweg — der Rückfall ist die Rechnung selbst, Frage für Frage.

### 5.2 Woran der geänderte Bereich erkannt wird

Am Inhalt, über einen **Fleckabdruck**, je Fleck einmal je Körper und für alle Flecken
in einem Zug gerechnet:

1. die Ecken seiner Dreiecke in Fleckfolge und Eckenfolge (float64-Bytes),
2. welche Ecken dieselben sind, als Nummern im Fleck,
3. der erste Nachbarring, wie die Fragen ihn lesen: je Dreieck und Kante die Lage des
   Nachbarn im Fleck, sonst „außen“ oder „keiner“ (`_neighbour_index`, auch an Kanten
   mit drei Dreiecken, die `_fan_arcs` anders zählt),
4. die Folge der inneren Nähte in der Kantennummerung des Körpers, denn die tangentiale
   Trennung bricht Gleichstände daran (`features.py:11287`).

Ändert sich ein Dreieck im Fleck oder in seinem Ring, ändert sich der Abdruck, und
jede Frage an diesen Fleck rechnet. Dazu gibt der Aufrufer die **Körperzahlen**, die
eine Frage liest, ausdrücklich mit in Rechnung und Schlüssel: Verschweißtoleranz,
Gesamtoberfläche wo gelesen, Dichtheit und Umlauf, deckungsgleiche Ecken.

Für Ganzkörperfragen, die eine Fleckrechnung unterwegs stellt — heute
`cylinder_fits_in_the_body(axis, radius)` —, gilt eine **Rückfrage**: Gemerkt werden mit
der Antwort die gestellten Fragen samt ihren Antworten; beim Treffer werden sie am neuen
Körper neu gestellt, und nur wenn jede gleich ausfällt, gilt die gemerkte Antwort. Die
Rückfrage ist billig (meist entscheiden schon die sechs Extrempunkte, 3227–3237) und hält die
Hülle aus dem Schlüssel; eine Bohrung im Inneren ändert sie nicht. Wo die Extrempunkte nicht
entscheiden, rechnet sie das Rechteck über alle Ecken; diese Antwort wird je Körper und
Achse gemerkt, sonst kostete die Rückfrage so viel wie heute die Frage.

Nicht über den Werkzeugkörper, ein Hüllvolumen oder eine Liste geänderter Dreiecke —
Begründung in §7. Die Dreiecksherkunft (`attributes._same_triangles`, ohnehin in
`in_source_layout` gerechnet) braucht nur die Leer-Boolesche (5.6).

### 5.3 Randbreite

Der Rand ist kein Millimetermaß, sondern das, was eine Frage liest: der Fleck und sein
erster Nachbarring. Ein Fleck ist die kleinste Einheit und wird nie teilweise erkannt.
Die Folge steht in 4.2 Punkt 5: Eine Bohrung durch eine große Mantelfläche rechnet diese
ganze Fläche neu — richtig, denn ihre Einpassung hat sich geändert.

### 5.4 Was gemerkt wird, und was nicht

| Stufe | Frage | gemerkt als | liest | heute (Ständer / Eiffel / Spiderman, CPU-s unter Last) |
|---|---|---|---|---|
| G1 Lesung bei Bedarf | `_surface_support` | Abdruck der Lesung aus dem Fleckabdruck; die Felder erst, wenn eine Frage wirklich rechnet. Auch der Stapel `_screened_fits` (8515) fragt Beantwortetes nur noch über den Abdruck | 1–3, Dichtheit, deckungsgleiche Ecken | 0,95 / 2,4 / 5,9 |
| G2 Einpassungsrunden je Fleck | Ausgang von `classify` und der Runden drei bis fünf (Stadion, Prismabögen, Naht, Zylinder neben Ring) | Form, Fit, Treffer; Stücke als Lagen im Fleck | 1–3, Toleranz, Zustand der Runde (`no_cone_here`, Ringkandidaten), Rückfrage Hülle | ≈ 1 / ≈ 3–4 / ≈ 4 |
| G3 Tangentiale Trennung je Ziel | `_tangential_pieces` | Stücke als Lagen im Fleck | 1–4, Toleranz, Rückfrage Hülle | 1,6 / 8,4 / – |
| G4 Langloch und Flächenabschluss | `_open_slot_shell` je Bogen, Schalen je Paar; `_faces_finished_in` je Fläche | nach Leseanalyse | was über den Ring hinaus liest, wird Rückfrage oder bleibt gerechnet | 1,7 / 9,8 / – |

**Gerechnet wie heute bleiben die Klebstufen**: Flecken (`_connected_patches`),
Facetten und Facettenurteil, Krümmungssprünge, Zusammenlegen, Gewinde, Muster,
Einschlüsse, Durchsicht, Freiformurteil, Nummernfolge, gerundete Seiten. In ihnen
entscheiden sich Teilen, Verschmelzen und neue Nachbarschaften; sie lesen den ganzen
Körper, und genau dort läge das Risiko einer Übernahme. Sie sind der Boden des Entwurfs
(unbelastet geschätzt: Ständer ≈ 3 s, Eiffel ≈ 8 s, Spiderman ≈ 8,5 s; Herleitung in §11).

### 5.5 Übernahme, Wiederverknüpfung, Rand

- **Antworten sind nie Dreiecksnummern.** Stücke werden als Lagen im Fleck gemerkt und
  am neuen Körper in dessen Nummern zurückgelesen; Fits und Wahrheitswerte sind
  unveränderlich (Vertrag in `kern.md`, erweitert).
- **Verknüpft wird nichts.** `detect` gibt dasselbe Wörterbuch zurück wie die
  Vollerkennung; `_with_features`, `match`, `settled_twins`, `apply_mapping` und die
  Waisenfrage sehen dieselbe Eingabe und vergeben dieselben Namen.
- **Am Rand:** Ein Merkmal, dessen Fleck oder Ring ein neues Dreieck berührt, wird als
  Ganzes neu gerechnet. Teilen und Verschmelzen entscheiden die Klebstufen, die immer
  laufen. Danach gilt §21.2 wie heute: Eine geteilte Fläche heißt am größten Stück weiter
  (`evaluate._divided_partners`), ein verschwundenes Merkmal ist verwaist und hält an,
  wenn ein Verweis daran hängt (§21.3), Zwillinge entscheidet die Lage ihrer Oberfläche.

### 5.6 Die Leer-Boolesche

Liegt jedes Ergebnisdreieck bitgleich und gleich umlaufend in demselben Eingang und ist
die Zahl gleich, gibt `in_source_layout` diesen Eingang zurück, samt seiner Dreiecksfolge
(die Bedingung prüft sie heute schon Dreieck für Dreieck, `attributes.py:303–320`). Dann trifft
`_mesh_key`, die Erkennung kostet nichts, und alle Merkmale bleiben dieselben. Der Befund
`boolean.without_effect` bleibt. Gemessen: 12,6 s Erkennung unter Last für einen
Zylinder, der den Ständer nicht berührt; ebenso ein Vereinigen mit einem Körper, der ganz
im Material liegt.

### 5.7 Was ausdrücklich unberührt bleibt

§21.1-Staffel und die Frage vor der langen Vollerkennung; `detect_known` und
`detect_local` über 1,5 Mio. Dreiecken; `carry_detection` und `carry_refined_detection`;
Zuordnung samt ihrem Merker (`matching._MATCHES`); Projektdatei und Migrationen; der
Plattencache (vom Gedächtnis geht nichts auf die Platte, `CACHE_FORMAT_VERSION` steigt nur
mit 5.6, weil dort die Ausgabe ihre Darstellung ändert); die Oberfläche; das Laden.

## 6. Was es an anderer Stelle kostet

| Stelle | Wirkung |
|---|---|
| Auswertung | keine Bedeutungsänderung; `_with_features` bleibt; 5.6 ändert nur die Darstellung der Ausgabe einer wirkungslosen Booleschen |
| Projektdatei, Migration | keine; kein `format_version`; `CACHE_FORMAT_VERSION` einmal +1 für 5.6 |
| Steckbrief, Agentenkontext, Prüfbericht | keine — dieselben Merkmale |
| Leistungsbudget §31 | neue warme Marke „Erkennung nach einem Schritt“ an einem deterministisch erzeugten Netz neben den kalten Marken, die unverändert bleiben; Regressionswächter wie immer 25 % |
| Speicher | Abdrücke 32 Byte je Fleck, Stücke als int32-Lagen (Eiffel ≈ 1 MB), Ausgänge je Fleck wenige hundert Byte: Eiffel unter 10 MB je Abstammung. Gezählt in `features.held_answers`, damit die Bytegrenze des Ergebniscaches sie sieht — beides kommt mit Paket L (`504d45af6`, `c63580ca2`, noch nicht auf main); landet P2 vorher, trägt Paket L die neue Ablage beim Zusammenführen nach. Keine Lesung wird länger gehalten als heute (`SUPPORT_CACHE_LIMIT`) |
| Fäden, Abbruch | dasselbe Schloss wie `remembered` und `_by_geometry`; gerechnet außerhalb, veröffentlicht erst nach vollständiger Antwort, ein Abbruch hinterlässt nichts; jede neue Frage steht in `SHARED_ANSWERS` oder `BODY_BOUND_ANSWERS` (Test vorhanden) |
| Oberflächengrenzen, Übersetzungen, Handbuch | keine — kein Schalter, kein Text |
| Regeln, Karten | `kern.md` „Über die Körpergrenze …“ neu gefasst (Fleckabdruck, Körperzahlen als Argument, Rückfrage, Lagen statt Nummern); `perceive/CLAUDE.md` „Der Weg durch die Erkennung“; Herleitung nach `konzepte/begruendungen/regel-kern.md` |
| Tests | je neuer Frage: Benennung, Treffer am Nachfolger, Fehlgriff bei geändertem Ring und geänderter Körperzahl, kein Eintrag nach Abbruch; eine A/B-Teilmenge der Messbank in der Suite, damit auf allen vier Plattformen |

## 7. Verworfene Alternativen

- **A — Ausschnitt mit Rand** (Teilnetz neu erkennen, Rest übernehmen; Roberts
  wörtliche Fassung). Gleichheit ist nicht beweisbar (4.3), `detect_local` und
  `detect_known` belegen die Grenze, und §21.1 müsste geändert werden (RM-261). Dazu
  entstünde ein zweiter Erkennungsweg ohne Kriterium, wann er dasselbe sagt — ein
  ungewollter Zwilling (`zwillinge.md`).
- **B — Werkzeugkörper oder Hüllvolumen als Bereich.** Verlangt je Operation eine
  Bereichsangabe (über hundert Operationen), ist falsch beim Vereinigen überlappender
  Teile vor dem Abziehen (`boolean._parts_united_first`), beim Narbenschließen
  (`prepare_ops._without_scars`), beim Versetzen (zwei Stellen) und bei der Reparatur —
  und die Klebstufen müssten trotzdem laufen.
- **C — Antworten über eine starre Bewegung mitnehmen** (Fits transformieren). Ein an
  der neuen Lage gerechneter Fit weicht in den letzten Stellen vom transformierten ab.
  Welcher gilt, hinge daran, ob das Gedächtnis gefüllt war; nach Öffnen, Verdrängen oder
  in einem anderen Lauf trüge dasselbe Dokument zwei Merkmalsstände (§15.1, §15.7).
  Sauber ginge es nur, wenn Körper in ihrem eigenen Rahmen blieben und Werkzeuge
  hineinwanderten — die Umkehr von „Werkzeuge wandern in die Welt, nie Körper in ihren
  Rahmen“ (`operationen.md`), weit größer als dieser Auftrag. In den zwölf
  Beispielprojekten folgt eine Boolesche zweimal auf eine Bewegung: Weg 4 verschiebt die
  Kugel vor dem weichen Vereinigen (danach vernetzt der nächste Schritt ohnehin neu), und
  das Gehäuse schneidet sein Probestück aus der verschobenen Kopie (ein kleines Stück,
  schnell erkannt). Weg 1 setzt das Teil vor der Bohrung *auf das Bett*; liegt es schon
  dort, bleibt jede Koordinate, und der Merker trifft.
- **D — Toleranz in Stufen statt stetig aus der Diagonale.** Ließe auch Schritte
  treffen, die die Ausdehnung ändern (*Abschneiden*, *Fläche versetzen* außen,
  Vereinigen nach außen). Ändert aber eine Schwelle der Erkennung und verlangt deren
  Messung an beiden Seiten (`schichtanalyse.md`). Erst entscheiden, wenn die Messbank
  zeigt, wie viel Wartezeit auf solche Schritte entfällt.
- **E — Geometrie sofort zeigen, Merkmale nachreichen.** Verkürzt das Gefühl, nicht die
  Rechnung, und berührt „keine halb angewandten Ops“ (§15.6) und die Bedienung.
- **F — Nur die Vollerkennung schneller machen.** Ergänzt, ersetzt nicht: Laden und
  Schritt gewinnen beide, aber ein Schritt rechnete weiter alles. Bleibt Paket L,
  Rangliste Tempo 4.

## 8. Risiken und Abhängigkeiten

- **R1 Ein Schlüssel vergisst, was die Frage liest** — ein stilles falsches Ergebnis,
  das gefährlichste Risiko. Gegenmittel: Leseanalyse je Frage im Docstring,
  Körperzahlen nur als Argument und nie im Rumpf vom Körper gelesen (wie heute die
  Toleranz), Vertragstest, Korpusvergleich mit Gegenprobe je Schlüsselteil (A1).
- **R2 Zustand der Runde.** `no_cone_here`, der Stapel `_SCREENED`, die Masken
  `wandering` und `outline` gehören in den Schlüssel, oder die Frage wird nicht auf
  dieser Ebene gemerkt. Der Stapel (`refine.exhausted`) muss je Zeile unabhängig von
  seiner Zusammensetzung antworten — schon heute Voraussetzung von RM-261, in P3 eigens
  geprüft (ein Fleck allein und im Stapel, dasselbe Urteil).
- **R3 Dreiecksfolge des Kerns.** ~~`manifold3d` behält die relative Folge unberührter
  Dreiecke.~~ Hält nicht (Nachtrag P2): Der Kern legt Unberührtes auch untereinander um,
  am Ständer verfehlten deshalb 245 von 1 574 Trennungen. Seit P2 legt
  `attributes.in_source_layout` die übernommenen Dreiecke auf die Plätze des Kerns in der
  Folge ihres Eingangs, und die Trennung liest ohnehin nicht mehr nach Nummern. Ändert
  eine neue Fassung des Kerns mehr, verfehlt das Gedächtnis — langsamer, nie falsch; die
  Messbank meldet die Trefferquote je Lauf.
- **R4 Ergebniscache.** Die Antworten gehören den Abstammungen der Körper, die sie
  fragten. Der Körper der aktuellen Szene lebt, also trifft der nächste Schritt. Ein vom
  Cache verschlanktes oder verdrängtes älteres Netz verliert seine Antworten; ein Schritt
  nach einer Rücknahme dorthin rechnet kalt — langsamer, nie falsch.
- **R5 Zuordnung.** Keine Abhängigkeit, solange A1 hält: `match` sieht dieselbe Eingabe.
- **R6 Gewinn kleiner als geschätzt.** Die Schätzung stützt sich auf Läufe unter Last
  und für G2 und G4 auf Profilanteile. P0 misst ruhig nach, jede Stufe meldet ihren
  Beitrag, das Tor vor P5 entscheidet auf Zahlen.
- **R7 Freiformen gewinnen wenig**: Am Spiderman tragen Facetten, Flecken und
  Krümmungssprünge die Zeit, und die bleiben gerechnet.
- **R8 Plattform und Determinismus.** Das Gedächtnis überschreitet weder Prozess noch
  Maschine; ein Treffer ist die Rechnung dieser Maschine, und Schlüssel sind Bytes ohne
  Arithmetik — ARM, FMA und BLAS-Fadenzahl sehen sie nicht. Was die Vollerkennung selbst
  über Plattformen gleich hält, prüfen weiter die Rauschproben in
  `tests/test_platform_identity.py`. Bedingung: `forget_cache` leert das neue Gedächtnis
  mit, denn die Proben verlassen sich darauf (`test_platform_identity.py:605–632`); sonst
  träfe der verrauschte Lauf die Antworten des ruhigen, und die Probe wäre blind.
  Reihenfolge der Fäden: Antworten sind rein, zwei Fäden rechnen höchstens doppelt.

## 9. Entscheidungen

Selbst getroffen, jeweils mit Grund:

1. **Gedächtnis je Fleck statt Ausschnitt.** Gleichheit durch Bauart statt Nachweis je
   Fall, kein zweiter Erkennungsweg, Bauplan unverändert (§3, §7 A).
2. **Gleich heißt Bit für Bit**: `feature_to_data` jedes Merkmals und die Nebentabellen
   (`freeform_dropped`, `recognised_as_freeform`, `unreadable_void_shells`), nicht
   Gleichheit auf Toleranz. Nur so ist „von einer Rechnung nicht zu unterscheiden“
   prüfbar, und nur so kippt keine Schwelle fern vom Schritt (der Anlass von RM-261).
3. **Bewegte Körper bleiben ohne Gewinn.** Reproduzierbarkeit geht vor Tempo (§7 C).
4. **Kein Schalter für Kunden.** Abschaltbar nur über einen Testhaken für Messbank und
   Suite, wie `forget_cache`. Eine Einstellung „schnelle Erkennung“ wäre eine
   Einstellmöglichkeit, wo die Vorgabe richtig sein muss.
5. **Die wirkungslose Boolesche gibt ihren Eingang zurück** (5.6).
6. **Antworten nie als Dreiecksnummern**, nur als Lagen im Fleck.
7. **Reihenfolge nach gemessenem Anteil**, die Klebstufen nur über ein Tor.

Fragen an Robert: keine. Weder Geld, Veröffentlichung, Rechte noch der Bauplan sind
berührt; die Regel in `kern.md` folgt der Umsetzung.

## 10. Abnahme

- **A1 Gleichheit am Korpus.** Die Messbank fährt jeden Netzkörper aus `tests/data`,
  aus den zwölf Beispielprojekten und aus `F:/3D Dateien` (mindestens die neun
  Paket-L-Modelle und den Gartenschlauchhalter) durch die Folge Laden → Bohrung Ø 3 an
  drei Stellen → Bohrung versetzen → Bohrung aufweiten → Merkmal entfernen → Quader an
  einer Kante abziehen → Zapfen vereinen → Abschneiden → Verschieben und erneut bohren.
  Nach jedem Schritt die Erkennung mit Gedächtnis gegen dieselbe Erkennung an einer
  Kopie ohne jedes Gedächtnis (`forget_cache`, Testhaken aus): **0 Unterschiede** in
  `feature_to_data` und Nebentabellen, und nach `_with_features` dieselben Namen und
  derselbe `object_hash(features=)`. Mindestens 1 500 Zustände (RM-261: 1 365).
  **Gegenprobe:** Jeder Schlüsselteil (Abdruckteile 1 bis 4, jede Körperzahl, jede
  Rückfrage), einmal weggelassen, erzeugt mindestens einen Unterschied — sonst ist er
  überflüssig oder die Messbank zu schwach.
- **A2 Kennungen.** Ein Verweis auf ein fernes Merkmal überlebt den Schritt mit und ohne
  Gedächtnis unter demselben Namen; Zwillinge entscheidet dieselbe Oberflächenlage; die
  Zahl der Zuordnungsfragen über den ganzen A1-Lauf ist dieselbe.
- **A3 Plattformen.** Die A1-Teilmenge aus `tests/data` läuft in der Suite grün —
  Windows im Entwicklungstor, Linux, macOS ARM und macOS Intel in der CI;
  `tests/test_platform_identity.py` bleibt grün, und ein Test belegt, dass `forget_cache`
  jede neue Ablage leert (R8).
- **A4 Tempo**, Referenzrechner, ruhig, im Wechsel mit dem Ausgangsstand gemessen und
  über die Rechenprobe umgerechnet (§31). Erkennung nach dem Schritt — Ø-6-Bohrung an
  festen Stellen, am Spiderman zwei vertauschte Dreiecke — höchstens 60 % (Ständer),
  45 % (Eiffelturm) und 75 % (Spiderman) des in P0 gemessenen Ausgangswerts, absolut
  Ständer ≤ 4 s und Eiffelturm ≤ 10 s. Gartenschlauchhalter, *Merkmal verschieben* an
  `hole_10`, `hole_4`, `hole_9` (Sonde `p08_schritte.py`): Erkennung höchstens 60 % des
  Ausgangswerts. Wirkungslose Boolesche: 0 s Erkennung, Treffer im Merkmalscache. Jedes
  Paket weist seinen Beitrag einzeln aus.
- **A5 Kein Rückschritt.** Kalterkennung der neun Paket-L-Modelle höchstens +2 % CPU
  (Median aus drei Läufen im Wechsel mit dem Ausgangsstand); Marken `detect_feature_rich_204k`, `detect_pocketed_17k`,
  `detect_freeform_200k`, `match_800` innerhalb ihrer Streuung; `features.held_answers`
  am Eiffelturm nach acht Bohrungen höchstens 20 MB über heute; die Arbeitssatzspitze der
  Paket-L-Fenstersonde (`probe_window.py`, Spiderman, acht Schritte) nicht höher.
- **A6 Suite.** Je neuer Frage ein Test für Benennung
  (`test_every_question_across_bodies_is_named_and_shared` erweitert), für den Treffer am
  Nachfolger (gezählte Rechnungen), für den Fehlgriff bei geändertem Ringdreieck, bei
  geänderter Körperzahl und bei anderer Rückfrageantwort, und dafür, dass ein Abbruch
  nichts hinterlässt — jeder am Stand davor oder unter der Mutation rot.

## 11. Umsetzungsschritte

| Paket | Inhalt | Größe |
|---|---|---|
| P0 | Messbank: die Folgen aus A1 über den Korpus, Gedächtnis an und aus, Abdrücke, CPU je Stufe, Trefferquoten je Frage; aufbauend auf `konzepte/nachweise-release-0.5.1/sonden/rest-merker/p08_schritte.py` (dessen `--pruefen` vergleicht schon Bit für Bit). Ruhige Ausgangswerte, warme Leistungsmarke | klein |
| P1 | Die wirkungslose Boolesche gibt ihren Eingang zurück (5.6), `CACHE_FORMAT_VERSION` +1, Test | klein |
| P2 | Fleckabdruck; G1 Lesung bei Bedarf, auch im Stapel `_screened_fits`; G3 tangentiale Trennung mit Rückfrage Hülle; Regeltext `kern.md` | mittel |
| P3 | G2 Einpassungsrunden je Fleck, mit Rückfrage Hülle und dem Zustand der Runde im Schlüssel; Prüfung des Stapels je Zeile | mittel bis groß |
| P4 | G4 Langloch-Teilfragen und Flächenabschluss nach Leseanalyse | mittel |
| Tor | A4 erreicht: Ende. Sonst P5 | – |
| P5 | Klebstufen über die Körpergrenze tragen (Facetten, Krümmungssprünge, Flecken) — nur mit eigenem Nachtrag zu diesem Konzept, denn ihre Nummerierung ist die des ganzen Körpers | groß |

Jedes Paket mit Tor, Review, A1 an der Teilmenge und A5; P2 bis P4 zusätzlich mit dem
ganzen A1-Lauf.

**Herleitung der Schätzung.** Anteil der Erkennung nach dem Schritt am Kaltlauf
desselben Prozesses (§4.2), mal die ruhige Kaltzeit aus Paket L (Ständer 11 s, Eiffelturm
32 s, Spiderman 17 s). Für P2 ist der Anteil am Prototyp gemessen, für P3 und P4 aus den
Profilposten geschätzt.

| Stand | Ständer | Eiffelturm | Spiderman |
|---|---|---|---|
| heute nach dem Schritt | 0,49–0,58 → ≈ 6 s | 0,66–0,67 → ≈ 21 s | 0,78 → ≈ 13 s |
| nach P2 (Prototyp gemessen) | 0,44 → ≈ 4,8 s | 0,47 → ≈ 15 s | 0,60 → ≈ 10 s |
| nach P3 (geschätzt) | ≈ 0,39 → ≈ 4,3 s | ≈ 0,41 → ≈ 13 s | ≈ 0,52 → ≈ 9 s |
| nach P4 (geschätzt) | ≈ 0,31 → ≈ 3,4 s | ≈ 0,27 → ≈ 8,5 s | wie P3 |
| Boden: nur noch Klebstufen | ≈ 0,29 → ≈ 3,2 s | ≈ 0,26 → ≈ 8,3 s | ≈ 0,50 → ≈ 8,5 s |

## 12. Bewusst nicht gebaut

- Ausschnitt-Erkennung unter 1,5 Mio. Dreiecken (§7 A).
- Übertrag von Fleckantworten über starre Bewegungen (§7 C).
- Gedächtnis auf der Platte oder über Prozesse hinweg: Beim Öffnen läuft ohnehin die
  Vollerkennung des Ladeschritts, ein weiterer gespeicherter Cache bräuchte Formatpflege
  für einen Fall, der nicht wartet.
- Ein Schalter oder eine Einstellung in der Oberfläche.
- Kennungen aus Dreiecksbelegen statt aus der Zuordnung: Sie änderten Antworten in
  mehrdeutigen Fällen und sind kein Tempoposten (`match_800` 71 ms, Paket L).
- Toleranzstufen (§7 D), bis die Messbank ihren Anteil zeigt.

## 13. Empfehlung

Bauen, P0 bis P4 in dieser Reihenfolge, P5 nur über das Tor. Der Entwurf löst Roberts
Anliegen dort, wo es entsteht: Ein Schritt rechnet nur noch, was sich geändert hat, und
die Stufen, die den ganzen Körper ansehen müssen — so, dass das Ergebnis nachweislich
dasselbe bleibt. Dieselbe Bauart hat RM-261 schon getragen, 1 365 Zustände ohne
Unterschied, und der Prototyp zeigt an drei Modellen denselben Abdruck wie die
Vollerkennung. Die wörtliche Fassung „Bereich plus Rand“ verwässert dagegen §21.1 und
§15.1: Schneller wäre sie nur um den Preis eines zweiten Erkennungswegs, der an
Diagonale, Fläche, Hülle und fernen Wänden auseinanderläuft.

Zu erwarten ist etwa die Hälfte der heutigen Wartezeit nach einem Schritt an
mechanischen Teilen und ein Drittel weniger an Freiformen. Das §31-Ziel „unter 2 s bis
zum sichtbaren Ergebnis“ erreicht auch der volle Entwurf an diesen Größen nicht; dafür
müssen die Klebstufen und die Vollerkennung selbst schneller werden (Paket L, Rangliste
Tempo 4) und die Boolesche dazu (Rangliste 5). Beide brauchen eigene Registerpunkte,
falls sie noch keine haben. Am selben Klick wartet außerdem RM-591 (die Auswertung
wächst je Verlaufsschritt, am Eiffelturm um rund 1,5 s) — getrennt zu bauen, für den
Kunden aber dieselbe Wartezeit.

## Anhang A — Sonden

Gebaut für dieses Konzept, nur lesend am Hauptbaum (`sys.path` auf `F:/3D Druck`,
Nutzerordner in ein Temp-Verzeichnis, `PYTHONDONTWRITEBYTECODE`), unverändert abgelegt samt
Protokollen unter `nachweise-oertliche-erkennung-2026-10/konzept-sonden/`; P0 baut sie als
Messbank nach.

- `probe_local.py <modell> <still|moved> [--at auto --rank k] [--cx --cy] [--repair]`:
  Laden über `import_plan` und `evaluate` mit Erkennung, auf Wunsch `translate_object`
  dx 5 oder *Reparieren* davor, dann `create_cylinder` Ø 6, Höhe 400, z −100 an der
  k-größten nach oben weisenden Dreiecksmitte, `subtract_objects`. Gemessen werden je
  Stufe die CPU (äußerste Ebene), je Frage aus `GEOMETRY_KEYED_ANSWERS` Treffer und
  Rechnungen (`_by_geometry` umwickelt), bitgleich übernommene Dreiecke
  (`attributes._same_triangles`) und berührte Flecken (Fleck mit einem neuen Dreieck oder
  dessen Eckennachbarn). Logs `riser_*.txt`, `eiffel_cut.txt`, `spider_*.txt`.
- `probe_floor.py <modell> [--proto]`: `read_mesh` und `normalise`, kalte `detect`, dann
  derselbe Körper mit vertauschten Dreiecken 0 und 1, warm erkannt. Mit `--proto` gilt
  der Wegwerf-Prototyp: Lesung gemerkt unter Ecken, Eckennummern im Fleck, Dichtheit,
  Umlauf und deckungsgleichen Ecken; tangentiale Trennung gemerkt unter Ecken,
  Nachbarlagen im Fleck, Folge der inneren Nähte und Körperausdehnung, Stücke als Lagen
  im Fleck. Danach `forget_cache`, Prototyp aus, kalte Erkennung desselben Zwillings und
  Vergleich der Abdrücke über `feature_to_data`. Ergebnis: Ständer, Eiffelturm und
  Spiderman jeweils GLEICH (Logs `floor_*.txt`). Der Prototyp hält die Lesungen ganz; P2 hält nur ihre
  Abdrücke und muss dieselbe Ersparnis ohne diesen Speicher zeigen (A5). Er prüft keine
  Hüllrückfrage, weil die Hülle beim Vertauschen gleich bleibt — das ist P2 vorbehalten.

## Nachtrag P1 und P2 (Umsetzung, 09.10.2026)

- **P1** wie 5.6. `CACHE_FORMAT_VERSION` steht nach dem Zusammenführen mit Welle 2 auf 55
  (G belegte 53, der gemeinsame Stand 54).
- **P2, Fleckabdruck**: Teile `ecken`, `eckennummern`, `ring`, `ursprung`, `normalen`,
  `flaechen`, für die Trennung dazu `winkel` (`features.PATCH_PRINT_PARTS`). Normalen,
  Flächen und Nahtwinkel stehen darin, weil eine starre Bewegung sie vom Quellnetz
  mitträgt (`geom.transform._carry_cache`) und sie dann nicht Bit für Bit den Ecken
  folgen: Ohne sie gab die Messbank am Patchstand des Vorgängers 449 von 2 282 Zuständen
  anders aus (die Lesung eines frisch gebauten Netzes bekam den Abdruck der
  mitgetragenen); das hält jetzt ein Test fest. 5.2 „Normalen und Flächen rechnet trimesh
  aus den Ecken“ gilt nur für ein frisches Netz. Körperzahlen `dicht`, `umlauf`, `deckungsgleich` für die
  Lesung, `diagonale` für die Trennung (`BODY_NUMBERS`). Die in 5.2 Punkt 4 vorgesehene
  Folge der inneren Nähte und die Folge der Dreiecksnummern stehen **nicht** im Abdruck:
  Die tangentiale Trennung las ihre Bänder und Keime nach Dreiecksnummern und hing damit
  an der Dreiecksfolge der Datei (gegen RM-210, Test mit gemischten Dreiecken); sie liest
  jetzt in der Ordnung des Körpers (`in_body_order`), gleich lange Nähte in der Folge
  ihrer Kanten, und die folgt den Eckennummern. Was die Rechnung nicht liest, gehört
  nicht in den Schlüssel.
- **G1** `_support_handle`: Kennt das Gedächtnis Fleckabdruck und Körperzahlen, steht der
  Abdruck der Lesung fest (`_SupportPrint`), die Felder liest erst, wer rechnet — auch im
  Stapel `_screened_fits`.
- **G3** `_tangential_pieces`: Stücke als Lagen im Ziel, Rückfrage an die Hülle
  (`_HULL_QUESTIONS`, das Rechteck über alle Ecken je Körper und Achse gemerkt), nichts
  gemerkt, wenn `_without_notches` über das Ziel hinaus sucht (`_Patches.beyond`).
- Testhaken `remember_across_bodies` (Konzept §9.4), `forget_cache` leert die neue
  Ablage mit (R8).
- Ein Fleck, den der Stapel nur als Abdruck hielt, fragte beim Lesen den Stapel und bekam
  sich selbst zurück (`RecursionError`, die Auswertung hielt beim Vereinigen an; Messbank
  A1). Die Lesung eines Abdrucks geht am Stapel vorbei (`_remembered_support`).

## Nachtrag P3 und P4 (Umsetzung, 09./10.10.2026)

- **G2** `classify` in `_fitted` antwortet je Fleck über die Körpergrenze
  (`PRINT_KEYED_ANSWERS` „classified“): Schlüssel Fleckabdruck, Diagonale, die Schwellen der
  Runde und als Zustand der Runde allein, ob ein deckungsgleicher Fleck schon keinen Kegel
  hatte (`no_cone_here`); gemerkt Antwort, Fits je Liste, ob der Fleck `no_cone_here`
  ergänzte, und die Rückfragen an die Hülle. Am Eiffelturm nach der Bohrung 1 095 Treffer,
  36 Rechnungen. Die Runden drei bis fünf (Stadion, Prismabögen, Naht, Zylinder neben
  Ring) fragen ihre Stücke über `classify` und gewinnen damit mit; ihr eigener Rest kostet
  am Eiffelturm unter 0,3 s und bleibt gerechnet. Der Stapel (`_screened_fits`) urteilt
  je Zeile unabhängig von seiner Zusammensetzung (R2): Test, der jeden Fleck allein und alle
  zusammen fragt (`test_the_stack_judges_each_patch_as_it_would_alone`).
- **Hülle ohne Rechteck:** Die Rückfrage an die Hülle kostete am Eiffelturm 0,9 s in fünf
  Rechteckfragen (`_rectangle_across`, je 0,18 s über 157 000 Ecken). Eine obere Schranke
  aus dem achsparallelen Rahmen der Projektion (Rechteckdiagonale unter √2 mal dessen
  Diagonale, mit 1,5 auf Abstand) verneint sie alle, mit derselben Antwort.
- **Abdrücke gestapelt** (`_patch_prints`): je Runde in einem Zug, Byte für Byte wie einzeln
  (Test); kleine Trennziele unter zwei Mindestflecken fragen weder Abdruck noch Prisma.
- **G4, Leseanalyse:** `_reaches_through` (Durchsicht, je Langloch) liest jedes Dreieck des
  Körpers im Abschnitt, `_shells_for`/`_shell_labels` die Quermaske aller Flächen,
  `_face_roles` alle parallelen Flächen derselben Schale, `_open_slot_shell` flutet über den
  Ring hinaus: Keine davon lässt sich je Fleck schlüsseln, eine Rückfrage kostete so viel
  wie die Frage. Sie bleiben gerechnet und rechnen schneller, mit denselben Antworten: die
  Durchsicht nur noch an Dreiecken, deren Kugel den Abschnitt und die Mittellinie erreichen
  kann (projiziert je Zeile über Grundrechenarten statt `@`), die Mantelstücke nur über die
  querstehenden Flächen. `planar_patch` je Fläche liest nur ihre Dreiecke, aber der
  Schlüssel kostete so viel wie die Prüfung; gerechnet.

