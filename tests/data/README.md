# Referenzkorpus

Feste Eingangsdaten für die Abnahmekriterien (Bauplan §34). Ohne festen
Datensatz sind sie nicht prüfbar.

**Regeln:** ausschließlich selbst erzeugte Geometrie oder eindeutig frei
lizenzierte Modelle — der Korpus wird mit veröffentlicht. Jede Datei bekommt
hier eine Zeile: was sie enthält, welche Kennzahlen erwartet werden, welcher
Test sie benutzt. Neue Fehlerbilder aus der Praxis werden als Datei
aufgenommen, nicht als Sonderfall im Code.

---

## Projektdateien

| Datei | Inhalt | Erwartung | Test |
|---|---|---|---|
| `projects/example_v1.p3d` | Format 1 mit Parametern, Ausdruck, Passung, Quelle mit Lizenz, Agenten-Transaktion, Bericht und Vorschaubild | öffnet, zwei Ops (`rename_object`, `duplicate_object`), `half` trägt `=@width/2`, Passung trägt `auto:petg` | `test_project.py::test_the_checked_in_example_still_opens` |

Je Formatversion bleibt eine Beispieldatei liegen (§16.2). Sie wird nie
nachträglich verändert — sie ist der Beweis, dass die Migrationskette
funktioniert.

Neu erzeugen (nur bei einer neuen Formatversion, die alte Datei bleibt):

```
python -c "from app.core.bootstrap import load_operations; load_operations(); from tests.test_project import build_example_project; from app.core.scene.project import save; from pathlib import Path; save(build_example_project(), Path('tests/data/projects/example_v2.p3d'))"
```

## Geometrie

Alle Dateien erzeugt `make_corpus.py` — selbst erzeugte Geometrie, keine
fremden Lizenzen. Neu erzeugen nur, wenn eine Datei sich ändern muss:

```
python tests/data/make_corpus.py
```

| Datei | Inhalt | Erwartung | Test |
|---|---|---|---|
| `meshes/cube_clean.stl` | Würfel 20 mm, in Millimeter gespeichert | 12 Dreiecke, roh 36 Punkte, nach dem Verschweißen 8 Punkte und wasserdicht, Volumen 8000 mm³; Einheit **eindeutig mm**, keine Rückfrage | `test_ingest.py` |
| `meshes/bracket_inch.stl` | Platte 4 × 2 × 0,25 **Zoll** | Einheit **mehrdeutig** (cm/in) → Rückfrage; mit `in` → 101,6 × 50,8 × 6,35 mm | `test_ingest.py` |
| `meshes/plate_cm.stl` | Platte 8 × 5 × 0,5 **Zentimeter** | Einheit **mehrdeutig** (cm/in) → Rückfrage; mit `cm` → 80 × 50 × 5 mm | `test_ingest.py` |
| `meshes/plate_holes.stl` | Platte 80 × 50 × 8 mm mit vier Bohrungen Ø 5,2 mm | Schnitt bleibt geschlossen trotz Löchern; ab P3 Feature-Erkennung | `test_section.py` |
| `meshes/plate_holes_twin.stl` | Platte mit zwei gleichen Bohrungen 8 mm auseinander | ab P3: wird als **mehrdeutig** gemeldet statt geraten (§21.2) | noch offen |
| `meshes/plate_countersunk.stl` | Platte 60 × 40 × 8 mm, eine Bohrung Ø 5,2 mm mit 90°-Senkung auf Ø 10 mm | die Bohrung wird erkannt, obwohl der Kegel an ihrer Wand hängt (Ø 5,19, Tiefe 5,6 mm — die des Zylinders, nicht der Platte); vor dem 22.08.2026 kam **nichts** heraus, weil Kegel- und Bohrungswand ein Fleck waren | `test_features.py` |
| `meshes/plate_countersunk_blind.stl` | dieselbe Platte, aber die Bohrung endet **vor** der Unterseite: Ø 5,2 mm auf 6 mm Tiefe, dieselbe 90°-Senkung auf Ø 10 mm | die Gegenprobe zur Datei darüber — Zylinder 3,6 mm **plus** Senkung 2,4 mm sind 6 von 8 mm, das Loch ist also **nicht** durchgehend. Ohne sie wäre jede Reparatur grün, die „Senkung dran, also geht es durch" sagt | `test_features.py` |
| `meshes/sphere_socket.stl` | Block 40 × 40 × 15 mm mit eingefräster Kalotte R 8 mm | die Kugel als **Pfanne** (§41) — Ø 15,94 (die Icosphere ist einbeschrieben), Mittelpunkt auf z = 7,5 und damit auf der Oberfläche, `recess` wahr, Rückstand 0,0003. Vor dem 22.08.2026 kamen hier nur die sechs Blockflächen heraus | `test_features.py` |
| `meshes/torus_ring.stl` | Torus, Ringradius 20 mm, Röhrenradius 5 mm | `diameter` (Ring) Ø 40, `tube_diameter` Ø 10, Achse z, Rückstand 0,005. Die Einpassung liest beide Radien aus den Rändern des Flecks und setzt damit einen **ganzen** Ring voraus — ein Torusstück, wie eine Verrundung es ist, misst sie noch nicht | `test_features.py` |
| `meshes/post_with_fillet.stl` | Säule Ø 12 auf einer Platte, der Fuß mit R 3 ausgerundet | das Alltagsteil, an dem bis zum 22.08.2026 **nichts** erkannt wurde: Eine Verrundung schließt tangential an, also trennt kein Knick sie ab, und Mantel und Kehle lagen in einem Fleck. Heraus kamen sieben ebene Flächen. Heute Zapfen Ø 12,00 und Torus mit Ring Ø 17,99 / Röhre Ø 5,99; die Krümmungskarte zeigt 3,0 mm und 6,0 nebeneinander | `test_features.py`, `test_maps.py` |
| `meshes/block_with_rounded_edge.stl` | Quader 40 × 30 × 20 mm, **eine** Kante mit R 3 ausgerundet | bis zum 23.08.2026 ein `pin` mit **Ø 28,92** — fast so breit wie das Teil. Zwei ebene Facetten von 1110 und 510 mm² galten als gekrümmt, weil sie die Rundung berühren, und hängten sich ihrem Fleck an; die Kreiseinpassung gewichtet quadratisch. Heute ein **`fillet`** mit R 2,999 und sechs Flächen — kein Zapfen mehr: §14 nennt einen Zapfen das, womit man eine Bohrung paart, und mit einer Kantenverrundung paart niemand etwas. Volumen 23942 mm³ | `test_features.py` |
| `meshes/plate_chamfer_and_taper.stl` | Platte 50 × 30 × 10 mm: links Bohrung Ø 6 mit Fase auf Ø 9, rechts ein konischer Zapfen | die zwei Kegelarten, die dem Korpus fehlten — §21.1 nennt drei, vorhanden war nur die Senkung. Fase `recess` wahr Ø 9,00, Verjüngung `recess` falsch Ø 10,00. Die **Fase** legte zwei Fehler frei: Die Bohrungswand zerfiel in vier Flecken (vier Bohrungen für ein Loch), und der Zapfen daneben machte aus der 10 mm dicken Platte eine 25 mm dicke, worauf die Bohrung als Sackloch galt | `test_features.py` |
| `meshes/degenerate.stl` | Würfel plus Nullflächen-Dreieck, Nadel und Dublette | 15 Dreiecke roh, nach der Eingangsstufe weniger; Befund `ingest.degenerate_removed` | `test_ingest.py` |
| `meshes/broken_open.stl` | Würfel ohne drei Dreiecke | nicht wasserdicht, Befund `ingest.not_watertight` (Warnung) | `test_ingest.py` |
| `meshes/partially_open.stl` | unterteilter Würfel ohne Decke und mit einem fehlenden Bodendreieck | selbst erzeugt, keine fremde Lizenz; 19 offene Kanten vor der Reparatur, 16 danach — der Bericht nennt **3 von 19 geschlossen** und den Rest, statt Vollzug zu behaupten | `test_geometry_review.py`, `test_ui.py` |
| `meshes/two_components.stl` | Würfel plus winziges Bruchstück daneben | zwei Komponenten, Befunde `ingest.multiple_components` und `ingest.small_components`; **nichts wird gelöscht** | `test_ingest.py` |
| `meshes/clean_figure.stl` | eine Figur ohne Fehler: Rumpf, Kopf, zwei Arme, zwei Beine aus Grundformen vereinigt — derselbe Aufbau, den P16.11 dem Käfigeditor entgegenhält | geschlossen, ein Körper, Euler-Charakteristik 2; 738 Dreiecke, 58 x 18 x 82 mm, steht auf z = 0; mittlere Kantenlänge 2,8 mm — zum Formen vorher gleichmäßig vernetzen; seit dem 22.08.2026 wird der **Kopf** als Kugel erkannt (Ø 17,7 auf z = 73) | `test_sculpt.py` |
| `meshes/generated_figure.stl` | drei verschmolzene Kugeln mit den Fehlern eines Generators: fünf einzelne fehlende Dreiecke, ein Fünftel verdrehte Normalen, ein loser Splitter | nach der Kette aus `GENERATED_REPAIR` **geschlossen**, ein Körper; die Merkmalserkennung findet keine Flächen (alle unter `MIN_FACE_AREA`), seit dem 22.08.2026 aber **genau die drei Kugeln**, aus denen die Datei gebaut ist — Ø 19,9, Ø 11,9 und Ø 8,0, Rückstände unter 0,0005 | `test_examples.py`, `test_features.py` |
| `meshes/broken_selfint.stl` | zwei Würfel, die sich durchdringen, ohne verschnitten zu sein | 24 Dreiecke; die Rückfallkette löst es derzeit schon auf Stufe 1 — die Datei hält fest, dass das so bleibt | `test_corpus.py` |
| `meshes/colored.3mf` | zwei Würfel in Slot 1 und 2, mit der eigenen 3MF-Hälfte geschrieben | zwei Materialgruppen „Rot" und „Schwarz", je Dreieck zugeordnet; Rundweg durch `threemf.read` | `test_corpus.py` |
| `projects/assembly_fit.p3d` | Platte mit 6-mm-Bohrung, Deckel mit 5,95-mm-Stift, dazu ein Passungspaar `auto:petg` | mit PETG hält die Passung, mit einem anderen Material meldet sie sich — die Bohrung folgt dem Druckmaterial, die Toleranz dem, was im Paar steht | `test_corpus.py` |
| `meshes/oversized.stl` | 400 × 80 × 40 mm: zwei dicke Enden, schlanke Mitte | passt auf keinen Bauraum; der Auto Split findet die Trennebene in der Mitte (Querschnitt 1200 mm², eine Kontur) und macht daraus zwei wasserdichte Teile | `test_autosplit.py` |

`meshes/dense_1m.stl` (1,31 Mio. Dreiecke, Leistungsmessung nach §31) wird
**nicht eingecheckt** — 60 MB im Repository wären unverhältnismäßig. Der
Leistungstest erzeugt sie beim ersten Lauf; die Messwerte landen in
`tests/.performance.json` und bleiben lokal, weil sie von der Maschine abhängen.

Damit ist der Korpus aus §34 vollständig, bis auf `legacy_v1.p3d` — die
Altformate liegen unter `projects/example_v1.p3d` und `example_v2.p3d` und
werden von `test_project.py` durch die Migrationskette geschickt.
