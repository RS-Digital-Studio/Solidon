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
| `meshes/degenerate.stl` | Würfel plus Nullflächen-Dreieck, Nadel und Dublette | 15 Dreiecke roh, nach der Eingangsstufe weniger; Befund `ingest.degenerate_removed` | `test_ingest.py` |
| `meshes/broken_open.stl` | Würfel ohne drei Dreiecke | nicht wasserdicht, Befund `ingest.not_watertight` (Warnung) | `test_ingest.py` |
| `meshes/two_components.stl` | Würfel plus winziges Bruchstück daneben | zwei Komponenten, Befunde `ingest.multiple_components` und `ingest.small_components`; **nichts wird gelöscht** | `test_ingest.py` |

Noch offen aus §34 — sie brauchen Bausteine aus späteren Phasen:
`plate_holes.stl` und `plate_holes_twin.stl` (Feature-Erkennung, P3),
`broken_selfint.stl` (Rückfallkette, P2), `oversized.stl` (Auto Split, P10),
`island_tower.stl` (Schichtanalyse, P3), `dense_1m.stl` (Leistungsmessung),
`colored.3mf` (Attributerhalt, P9), `assembly_fit.p3d` (Passungsprüfung, P3).
