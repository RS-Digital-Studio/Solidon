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

Noch leer. Der Korpus aus §34 (`cube_clean.stl`, `plate_holes.stl`,
`bracket_inch.stl`, `broken_open.stl`, `degenerate.stl`, `oversized.stl`,
`island_tower.stl`, `dense_1m.stl`, `colored.3mf` …) entsteht mit der
Eingangsstufe, weil die Dateien dort zum ersten Mal gelesen werden.
