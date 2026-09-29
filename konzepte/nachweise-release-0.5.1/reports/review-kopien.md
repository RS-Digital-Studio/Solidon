# Review `merkmale-an-kopien` — Merkmale an starr bewegten Körpern

Zweig `origin/merkmale-an-kopien`, Endcommit `b9252ee36`, Basis `cbef27715`, ein
Commit, 13 Dateien. Geprüft am 28.09.2026 in zwei eigenen Worktrees:
`wt-revkopien` am Endcommit und `wt-revkopien-merge` als Probemerge mit
`origin/main` (`f22906b16`). Alle Läufe gebunden an `FFFFF0FF`, Protokolle unter
`laeufe/rev-ko-*.txt`. Der Hauptbaum wurde nur gelesen, committet wurde nichts.
Beide Worktrees sind am Ende entfernt.

## Urteil

**Mergebar: ja.** Kein Fund blockiert den Merge. Die Übertragung ist richtig:
Am Korpus `F:\3D Dateien` (30 Modelle, je zwei Bewegungen) tragen alle 4 386
übertragenen Merkmale dieselben Dreiecke wie ihr Ursprung, und Lage, Achse und
Normale folgen der von außen bestimmten Bewegung. Spiegeln und Skalieren werden
neu erkannt, ein gespiegeltes Gewinde ist linksgängig. Namen, Folgeverweise auf
eine Kopie, der Plattencache und zwei kalte Läufe stimmen überein.

Vor dem Tag:

1. **Beim Merge neun Einträge von `part_ranges.toml` neu fahren** (Abschnitt
   „Merge"). Im Probemerge dauerte das 154 s, alle neun haben bestanden, danach
   meldete `--check` 35 von 35.
2. **V1:** Die Live-Vorschau der Dialoge über mehrere Körper wird durch die
   Übertragung um rund die Hälfte langsamer. Der Fix mit Test liegt in
   `reports/review-kopien-fix.patch`.

Derselbe Patch behebt N1 bis N5. Jeder neue Test ist ohne seinen Fix rot
(Gegenproben G1 bis G4). Der Patch passt auf den Endcommit und auf den
Probemerge (`git apply --check`).

## Befunde

### Blockiert den Merge

Keiner.

### Vor dem Tag

**V1 — Die Dialogvorschau über mehrere Körper rechnet jetzt die Zuordnung, die
sie bisher übersprang.** `app/core/scene/evaluate.py:3769-3770`, dazu der frühe
Ausstieg in `:3775-3792`.

Die Übertragung läuft auch bei `detect_features=False`. Danach kennt der Merker
das bewegte Netz, `known_detection` antwortet, und die Vorschau geht durch
Zuordnung und Befunde, statt mit den Merkmalen der Operation auszusteigen. Der
Dialog braucht diese Merkmale nicht („Der Dialog zeigt Geometrie und Differenz,
keine Merkmale", `app/ui/session.py:3811`). Gemessen mit `sonde_vorschau.py`:
der Organizer `desk-organizer-v3…body1.stl` mit 898 Merkmalen in N
Ausfertigungen, *Auf dem Bett anordnen*, der Abstand geändert wie beim Tippen.

| | Vorschau je Zahl | Vollauswertung kalt |
|---|---|---|
| N = 8, Zweig | 3,66–3,74 s | 5,07 s |
| N = 8, ohne Vermerk (Stand davor) | 2,40–2,49 s | 9,43 s |
| N = 8, mit Fix | 2,25–2,26 s | 4,61 s |
| N = 20, Zweig | 9,08–9,21 s | 9,71 s |
| N = 20, ohne Vermerk | 6,05–6,09 s | 22,38 s |
| N = 20, mit Fix | 5,58–5,74 s | 9,35 s |

Schwere: vor dem Tag. Der Zweig führt den Rückschritt an einem Kundenweg ein,
und keine Leistungsprüfung aus §31 misst ihn. Für einen einzelnen bewegten
Körper mit gemeldeter Matrix gilt dasselbe schon seit 0.5.0; der Fix deckt
beide Fälle.

Fix: nur übertragen, wenn erkannt wird oder ein Folgeschritt die Merkmale liest,
also `and (detect_features or referenced or needed)` an der Bedingung. Der Test
`test_a_preview_of_arranged_copies_carries_nothing_nobody_reads` ist ohne Fix
rot (`rev-ko-g2.txt`). Die genaue Auswertung danach überträgt wie bisher.

### Nach 0.5.1 — im Patch schon behoben

**N1 — Die Quelle einer Bewegung wird unter allen Eingängen gesucht, nicht am
eigenen.** `evaluate.py:3308-3312` und `perceive/features.py:1815-1821`.

Gleicht ein Zwischennetz einer Operation Bit für Bit dem Eingang eines anderen
Körpers, nennt der Vermerk zuerst diesen Körper. Nachgestellt mit
`sonde_zwischennetz.py` (`rev-ko-zwischen2.txt`): Die Kopie wurde allein und
ohne Anordnen ausgerichtet, danach wurden beide mit Anordnen ausgerichtet. Für
`obj_1` belegt `_motion_of` dann `obj_2` als Quelle, und die Matrix enthält nur
die Verschiebung, nicht die Drehung.

Heute hat das keine Folgen. *Druckoptimal ausrichten* führt die Merkmale selbst
nach (`moved_object`), und diese überschreiben die falsch nachgeführten
Kandidaten: Die Mitten liegen 0,0000 mm neben dem Sollwert. Eine Operation, die
einen Körper bewegt und seine Merkmale unverändert durchreicht, bekäme sie aber
falsch verschoben. Das ist dieselbe Bauart wie der Durchreichfall, den die
Sitzung gefunden hat.

Fix: Eine Ausgabe, deren Kennung ein Eingang ist, nimmt nur diesen Eingang als
Quelle; eine neue Ausgabe (Kopie) nimmt alle Eingänge. Der Test
`test_the_motion_of_an_output_starts_at_its_own_input` ist ohne Fix rot
(`rev-ko-g1.txt`).

**N2 — `_motion_of` steht vor dem Fang.** `evaluate.py:984`, der Fang beginnt
eine Zeile tiefer.

`moved_from` vergleicht jede Ecke (`moved_twin`). Geht an einem sehr großen
Körper dabei der Speicher aus, fliegt der `MemoryError` aus `evaluate` heraus,
statt ein Befund am Schritt zu werden. Der Fang darunter wurde genau für diesen
Fall gebaut (Kommentar `:1054-1060`).

Fix: den Aufruf in den `try` ziehen. Der Test
`test_a_failing_proof_of_movement_is_a_finding_not_a_crash` ist ohne Fix rot
(`rev-ko-g3.txt`).

**N3 — Die Abdrucktabelle wird je Ausgabe über alle Eingänge gebaut.**
`features.py:1815`.

Gemessen mit `sonde_quadrat.py`: 2,3 µs je Paar aus Ausgabe und Eingang. Bei
100 Körpern kostet ein Schritt über der ganzen Szene 0,05 s, bei 1 000 Körpern
2,29 s je Auswertung, und zwar auch im warmen Lauf, weil `_motion_of` bei jedem
Cachetreffer läuft. `MAX_PROJECT_OBJECTS` ist 10 000.

Fix: mit N1 erledigt. Eine vorhandene Ausgabe fragt nur ihren eigenen Eingang,
und neue Ausgaben kommen aus Operationen mit einem Eingang.

**N4 — Der Wortlaut der Regeln.** `.claude/rules/schichtanalyse.md:294-295`
sagt „gespiegelt oder skaliert wird neu erkannt: Ein Gewinde wechselt dort die
Hand". Beim Skalieren wechselt keine Hand. Im Patch heißt es „gespiegelt (das
Gewinde wechselt die Hand) und skaliert wird neu erkannt"; das spart 5 Byte.

Offen bleibt `.claude/rules/operationen.md:494-496`: Dort ist „meldet
`transform`" entfallen. Für einen einzelnen und für einen exakten Körper gilt
das weiter (Vorschau, Gizmo, `_carried_along`), steht aber nur noch in der Karte
`geom/CLAUDE.md`. Die Regel liegt bei 30 719 von 30 720 Byte; die Zeile kommt
beim nächsten Verdichten zurück, nicht im Patch.

**N5 — Testlücken.** Für die Musterkopien, den dritten Anlass des Zweigs, gibt
es keinen Test. Der Ausrichtentest (`tests/test_matching.py:953`) prüft Mitte,
Achse und Durchmesser, aber keine Normale. Im Patch steht
`test_the_copies_of_a_pattern_keep_their_features_without_a_search`: ein Kranz
aus vier Kopien, Sollwert über Kabsch, Mitte und Normale geprüft. Ohne Vermerk
ist er rot (`rev-ko-g4.txt`).

### Nach 0.5.1 — offen

**N6 — `moved_twin` läuft je bewegter Ausgabe zwei- bis dreimal je
Auswertung**: in `moved_from`, in `carry_detection` und bei großen Körpern in
`standing`, und das bei jedem Cachetreffer. Ein Aufruf kostet an 1,3 Mio.
Dreiecken 32 ms (`sonde_warm.py`). Fix: den Beleg am bewegten Netz merken, im
Cache des Netzes wie `solidon_mesh_key`, oder in `carry_detection` zuerst den
Merker des bewegten Netzes fragen.

**N7 — Die lageabhängige Erkennung (RM-210) wird an bewegten Kopien durch die
des Ursprungs ersetzt.** Das ist kein Fehler des Zweigs, aber eine
Verhaltensänderung für bestehende Projekte.

Im Korpusvergleich (`sonde_korpus_uebertrag.py`, `korpus_uebertrag.jsonl`)
erkennt die frische Erkennung am gedrehten Netz an 9 von 30 Modellen etwas
anderes: 25 Merkmale gibt es nur frisch, 6 nur übertragen, und
Musterbeschreibungen wählen eine andere Trägerseite oder Zellweite. Seit dem
Zweig behalten ausgerichtete, angeordnete und gemusterte Kopien die Merkmale
ihres Ursprungs, was einheitlicher ist. Zeigt aber in einem 0.5.0-Projekt ein
Folgeschritt nach *Druckoptimal ausrichten* auf ein Merkmal, das nur in der
neuen Lage erkannt wurde, hält die Auswertung künftig an diesem Schritt mit
Befund an. Das gehört ins Register zu RM-210.

## Merge

- **Probemerge** `b9252ee36` + `origin/main`: Der einzige Konflikt ist
  `app/core/knowledge/data/part_ranges.toml` mit 9 Einträgen (fit_ladder,
  heatset_m4, nut_trap, overhang_fan, printed_nut, printed_screw,
  printed_thread, screw_hole, wall_ladder). main hat sie für eigene Änderungen
  neu gefahren, der Zweig wegen `geom/transform.py`; keine der beiden Seiten
  passt zum gemergten Stand. Vorgehen: mit einer Seite auflösen, dann
  `tools/check_part_ranges.py --jobs 4` fahren (es rechnet nur die veralteten).
  Im Probemerge waren das 9 von 9 bestanden (`rev-ko-merge-ranges.txt`), danach
  `--check` 35 von 35 (`rev-ko-merge-check2.txt`).
- **Regelbudget nach dem Merge:** `schichtanalyse.md` 30 543 Byte, mit Patch
  30 538. `operationen.md` 30 719 Byte, also 1 Byte Luft. Mit dem Nachtrag der
  Gesamtprüfung (+8 Byte committet, −31 Byte ungesichert im Baum) liegt
  `schichtanalyse.md` bei rund 30 520 Byte, mit Patch bei rund 30 515 Byte.
- **Tests im Probemerge**, Kern ohne Fenster: 15 Dateien mit 1 763 bestanden
  und 3 übersprungen, Exit 0 (`rev-ko-merge-tests.txt`). Mit Patch 8 Dateien
  mit 1 162 bestanden und 3 übersprungen, Exit 0 (`rev-ko-merge-fix.txt`).
- **Der Merker der Gesamtprüfung** (`orientation.turned_like` und `shape_key`,
  noch ungesichert in `F:\3D Druck.gesamtfix`) doppelt sich nicht mit diesem
  Zweig und widerspricht ihm nicht. Er teilt die *Suche* nach der Lage unter
  Kopien derselben Form, dieser Zweig teilt die *Erkennung*. `turned_like`
  rechnet die Matrix für das Netz der jeweiligen Kopie (`fitting_transform`),
  und `moved_object` bewegt jeden Körper von seinem eigenen Eingang aus, also
  stimmt der Vermerk. Gemeinsam ist beiden nur `schichtanalyse.md`, dort in
  anderen Abschnitten (Zeilen 147 und 267 gegen 294).
- **Die übrigen Zweige für 0.5.1:** `speicher-ohne-prozesswerte` ändert
  `cache.py` und `evaluate.py` an anderen Stellen (Schlüssel,
  `CACHE_FORMAT_VERSION` 32). `einfuegen-freier-platz` ändert `evaluate.py` in
  `_with_nested_context` und `geom/CLAUDE.md` einen Absatz weiter. Beide ändern
  `geom/ops.py`, `einfuegen-freier-platz` auch `geom/prepare.py`; deshalb nach
  jedem Merge `check_part_ranges.py --check`.

## Die Fragen des Auftrags

**Was als starr gilt.**

- *Verschieben und Drehen* bekommen einen Vermerk (`transform.apply`: starr und
  Determinante größer null).
- *Spiegeln* bekommt keinen. Selbst ein Vermerk würde nicht geglaubt:
  `transform.moved` dreht bei negativer Determinante den Umlaufsinn,
  `moved_twin` verlangt dieselben Dreiecke und lehnt ab. Die Gegenprobe M2 (mit
  Vermerk auch beim Spiegeln) macht zwei Tests rot. Kommt Spiegeln doch als
  gemeldete Matrix an einem Körper, dreht `matching.moved_features` die Hand des
  Gewindes selbst um. Die Sonde S4 (gespiegelter Bolzen, dupliziert,
  angeordnet) ergibt `left` und `left`, ungespiegelt `right` und `right`.
  Kegel- und Senkrichtungen sind Vektoren und folgen der Matrix; neu erkannt
  wird ohnehin.
- *Skalieren und Scheren*: `is_rigid` ist falsch, es gibt keinen Vermerk, und
  auch mit gemeldeter Matrix scheitert `moved_twin`, also wird neu erkannt.
- *Fast starr*: `is_rigid` erlaubt 1e-6 an `M·Mᵀ`, also gleichmäßige Faktoren
  mit |s − 1| ≤ 5·10⁻⁷. Solche Matrizen gelten als starr; `transformed_features`
  skaliert die Längen bei gleichmäßiger Matrix mit (`uniform`). Der Fehler
  bleibt unter 5·10⁻⁷ relativ, an Ø 10 mm unter 5 nm. Über den Vermerk kommt
  das nicht vor, weil die Operationen über mehrere Körper nur drehen und
  schieben.

**Richtigkeit der Übertragung.** Der Korpusvergleich (30 Modelle aus
`F:\3D Dateien`, Bewegungen „x 90° + Schub" und „37° um (1,2,3) + Schub", die
übertragene gegen eine ganz frische Erkennung am selben bewegten Netz) ergibt:

- Die Übertragung ist in 60 von 60 Fällen belegt.
- 4 376 von 4 386 Merkmalen sind gleich belegt, 4 ähnlich (Jaccard ≥ 0,9).
- Es gibt 19 Wertabweichungen. Sechs davon sind Vorzeichen- und
  Gitterkonventionen (Richtung eines Langlochs um 180°, Musterrichtung um 60°,
  90° oder 180°). Zwölf Werte gehören zu zwei Musterbeschreibungen, die die
  frische Erkennung in der Lage „x 90°" von der anderen Seite oder mit anderer
  Zellweite liest (RM-210, siehe N7). Dazu kommt eine Kegelmitte um 0,014 mm.
- Die Dreiecksnummern stimmen durch den Beleg `moved_twin` (dieselben Dreiecke)
  überein.

Die Sitzung hat `tests/data/meshes` verglichen; ihre Rohdaten
(`korpus-vergleich.txt`: 1 056 Merkmale, 0 Unterschiede) habe ich
nachgelesen, aber nicht neu gefahren.

**Namen und Provenienz.** Kopien behalten die Namen, die Provenienz und die
Dreiecke des Ursprungs. Belege: die Tests des Zweigs sowie die Sonde S1 (Kranz
über vier: Namen gleich, Lage und Normale höchstens 9·10⁻¹⁵ mm neben Kabsch).
Ein Folgeschritt auf eine Kopie bleibt gültig: In S2 setzt *Bohrung ändern* auf
`obj_2.hole_1` nach dem Ausrichten den Durchmesser 7,0, und die Mitte bleibt
auf 0,0 mm, wo sie war.

**Ort.** Wird nach dem Kopieren nur eine der beiden verändert, erkennt genau
diese neu: In S2 ist es ein Lauf für die geänderte Kopie, das Original behält
Ø 5,2. Ein verändertes Netz hat einen neuen Abdruck und keinen Vermerk; eine
Änderung am Netz selbst leert den trimesh-Cache und damit auch den Vermerk.
Die Durchreichsperre ist durch die Gegenprobe M1 belegt (ohne sie rot).

**Cache und Determinismus.** In S3 geben zwei kalte Läufe dieselben Merkmale
(Namen, Dreiecke und Werte über `hashing.digest`), und der Plattencache liefert
beim Wiederlesen dasselbe wie geschrieben und frisch. Der Vermerk besteht aus
höchstens vier Paaren aus Abdruck und Matrix (rund 600 Byte) und hält kein
Netz fest. Übertragene Merkmale sind neue Objekte (`replace`, eingefroren),
`params` werden kopiert. `CACHE_FORMAT_VERSION` braucht keinen Sprung: Der
Ordner des Ergebniscaches trägt Fassung und Stand des Kerns
(`paths.results_cache_dir`), einen Eintrag ohne Vermerk aus einem älteren
Stand liest kein neuerer Code. Ein beschädigter Vermerk fällt unter
`_DAMAGED_ENTRY`, der Eintrag wird neu gerechnet.

## Regelcheck (AGENTS.md)

- **Regeln 1–3:** kein Qt. Der Vermerk ist ein Merker am neu erzeugten Netz;
  der Abdruck landet wie bisher im Cache des Eingangs; keine Geometrie wird
  verändert.
- **Regel 5:** keine Signatur aus §9 geändert. Der Vertrag „ein Körper meldet
  seine Matrix, mehrere führen ihre Merkmale selbst" bleibt; die Auswertung
  leitet die Matrix je Körper her.
- **Regel 6:** kein `==` auf Fließkomma im Kern. Im Test vergleicht
  `np.array_equal` zwei Aufrufe derselben Zusammensetzung, das ist ein
  Determinismusnachweis.
- **Regel 7:** keine neue Toleranzkonstante. `MOVEMENT_NOTE_DEPTH` ist eine
  Kettenlänge.
- **Regel 17:** Die neuen `TypeError`/`ValueError` in `_movement_from_disk`
  sind intern und werden in `DiskCache.get` gefangen, wie bei
  `_refinement_from_disk`.
- **Regel 21:** Geraten wird nicht. Haben zwei Eingänge denselben Abdruck, sind
  sie geometrisch gleich.
- **Regeln 8–16, 18–20, 22:** nicht berührt.
- **Sprachregel:** Bezeichner sind englisch, deutscher Text steht mit echten
  Umlauten (Diff geprüft).
- **Unterlagen:** Karten und Regeln sind nachgezogen, die Begründung steht in
  `konzepte/begruendungen/`; Wortlaut siehe N4.

## Gelesen und gefahren

**Gelesen:** der ganze Diff; `features.py` (`_mesh_key`, `detect`,
`moved_twin`, `carry_detection`, Vermerk); `evaluate.py` (Ausgabeschleife,
`_motion_of`, `_with_features` ganz, `_shift_between`, `_carried_along`);
`transform.py` (`apply`, `_carry_cache`, `is_rigid`, `moved_object`);
`matching.moved_features` und `transformed_features`; `cache.py` (`get`, `put`,
`_DAMAGED_ENTRY`, Versionsgeschichte); die Operationen `orient_for_print`,
`arrange_bed`, `pattern`, `duplicate_object`, `check_collisions` und
`place_group_on_bed`; die Regeln `kern`, `operationen`, `schichtanalyse`,
`tests` und `zwillinge`; die Karten; der Sitzungsbericht mit seinen Rohdaten;
der Nachtrag der Gesamtprüfung (lesend).

**Gefahren** (Exit-Code jeweils im Protokoll):

| Lauf | Ergebnis |
|---|---|
| `rev-ko-1` Zweig, 17 Testdateien, Kern | 1 348 bestanden, 3 übersprungen, 15 abgewählt, Exit 0 |
| `rev-ko-mypy-win/-linux/-darwin` Zweig | je 330 Dateien ohne Befund |
| `rev-ko-ruff`, `rev-ko-format` Zweig | ohne Befund, 1 043 Dateien formatiert |
| `rev-ko-check` Zweig | Bereichsnachweis 35 von 35 |
| `rev-ko-merge-*` Probemerge | siehe „Merge" |
| `rev-ko-m1`, `rev-ko-m2` | Gegenproben der Sperren des Zweigs: rot wie erwartet |
| `rev-ko-fix-tests` mit Patch, 15 Dateien | 1 247 bestanden, 3 übersprungen, Exit 0 |
| `rev-ko-fix-final` mit Patch | 594 bestanden, 3 übersprungen, Exit 0 |
| `rev-ko-fix-mypy-*`, `-ruff2`, `-format2` mit Patch | ohne Befund |
| `rev-ko-g1` bis `rev-ko-g4` | jeder neue Test ohne seinen Fix rot |

Fenster- und Leistungstests liefen nicht (sie laufen nur beim Release); das
Tor über die ganze Suite ist nach dem Merge Sache der Release-Sitzung.

**Sonden und Rohdaten:** `reports/review-kopien-sonden/`. Der Pfad in
`sys.path` muss vor einem neuen Lauf auf einen bestehenden Baum zeigen.
`sonde_auswertung.py` (S1 Muster, S2 Ort und Folgeverweis, S3 Determinismus
und Plattencache, S4 Gewinde), `sonde_korpus_uebertrag.py` mit
`korpus_uebertrag.jsonl`, `sonde_vorschau.py`, `sonde_zwischennetz.py`,
`sonde_quadrat.py`, `sonde_warm.py`.
