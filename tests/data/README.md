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
| `meshes/degenerate.stl` | Würfel plus Nullflächen-Dreieck, Nadel und Dublette | 15 Dreiecke roh, nach der Eingangsstufe weniger; Befund `ingest.degenerate_removed` | `test_ingest.py` |
| `meshes/broken_open.stl` | Würfel ohne drei Dreiecke | nicht wasserdicht, Befund `ingest.not_watertight` (Warnung) | `test_ingest.py` |
| `meshes/two_components.stl` | Würfel plus winziges Bruchstück daneben | zwei Komponenten, Befunde `ingest.multiple_components` und `ingest.small_components`; **nichts wird gelöscht** | `test_ingest.py` |
| `meshes/clean_figure.stl` | eine Figur ohne Fehler: Rumpf, Kopf, zwei Arme, zwei Beine aus Grundformen vereinigt — derselbe Aufbau, den P16.11 dem Käfigeditor entgegenhält | geschlossen, ein Körper, Euler-Charakteristik 2; 738 Dreiecke, 58 x 18 x 82 mm, steht auf z = 0; mittlere Kantenlänge 2,8 mm — zum Formen vorher gleichmäßig vernetzen | `test_sculpt.py` |
| `meshes/generated_figure.stl` | drei verschmolzene Kugeln mit den Fehlern eines Generators: fünf einzelne fehlende Dreiecke, ein Fünftel verdrehte Normalen, ein loser Splitter | nach der Kette aus `GENERATED_REPAIR` **geschlossen**, ein Körper; die Merkmalserkennung findet keine Flächen (alle unter `MIN_FACE_AREA`) | `test_examples.py`, `test_features.py` |
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
