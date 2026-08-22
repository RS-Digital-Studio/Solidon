# Sondierung: .claude/konzept-fassungspflege-2026-08.md

**Titel:** Konzept: die Fassungen aktualisieren
**Stand laut Dokument:** Stand 14.08.2026
**Zweck:** Legt fest, wie der festgeschriebene Fassungssatz in constraints.txt auf neuere Paketfassungen gehoben wird — gestaffelt nach Risiko, je Paket ein grünes Tor und ein Commit — und hält den Fortschritt fest.

**Alterung:** 5/5 — Das Dokument besteht überwiegend aus Fassungsnummern eines lebenden Python-Ökosystems (zehn Pakete mit jetzt/neu-Zahlen), einer Momentaufnahme von pip --outdated und einer Fortschrittstabelle, die sich mit jedem Commit ändert. Sechs von sieben Arbeitspaketen sind bereits erledigt, die Ist-Zustandstabelle in §0 ist damit schon jetzt historisch; die trimesh-<5-Sperre, die mehrere Abschnitte trägt, dürfte nicht mehr bestehen. Nur die Leitplanken in §2 und §4 sind zeitlos.

## Gliederung

- §0 Ist-Zustand, nachgesehen am 14.08.2026
- §1 Ziel und Nicht-Ziele
- §2 Design-Entscheidungen
- §3 Arbeitspakete
- §4 Leitplanken
- §5 Fortschritt

## Extern prüfbare Behauptungen (16)

- **[hoch/fassung] numpy (PyPI)** — numpy: installiert 2.5.1, neuer verfügbar 2.5.2 (Fehlerbehebung); später angehoben auf 2.5.2  
  _Ort:_ §0 Tabelle „Was der Index neuer anbietet"; §5
- **[mittel/fassung] charset-normalizer (PyPI)** — charset-normalizer: 3.4.9 → 3.5.0, mittelbar über requests  
  _Ort:_ §0 Tabelle; §5
- **[mittel/fassung] platformdirs (PyPI)** — platformdirs: 4.11.0 → 4.11.3 (Fehlerbehebung)  
  _Ort:_ §0 Tabelle; §5
- **[hoch/fassung] ruff (Astral, PyPI)** — ruff: 0.16.1 → 0.16.3, kann neue Befunde bringen; gemessen keine neuen Befunde, kein Formatdiff  
  _Ort:_ §0 Tabelle; §3 P3; §5
- **[hoch/fassung] setuptools (PyPI)** — setuptools: 83.0.0 → 84.0.0, Hauptsprung, trägt den Bau  
  _Ort:_ §0 Tabelle; §5
- **[mittel/fassung] pytest-forked (PyPI)** — pytest-forked: 1.6.0 → 1.7.5  
  _Ort:_ §0 Tabelle; §5
- **[mittel/fassung] ast_serialize (PyPI)** — ast_serialize: 0.6.0 → 0.8.0, Fassung unter 1, daher darf sich alles ändern  
  _Ort:_ §0 Tabelle; §2 B; §5
- **[mittel/fassung] librt (PyPI)** — librt: 0.13.0 → 0.15.0, Fassung unter 1  
  _Ort:_ §0 Tabelle; §2 B; §5
- **[hoch/fassung] fast_simplification (PyPI)** — fast_simplification: 0.1.13 → 0.2.0, Fassung unter 1 und dezimiert Netze  
  _Ort:_ §0 Tabelle; §2 B; §3 P4; §5
- **[hoch/datum] trimesh (PyPI)** — trimesh: 4.12.2 → 5.0.0; trimesh 5.0 ist am 01.08.2026 erschienen  
  _Ort:_ §0 Tabelle und Absatz „Warum trimesh gesperrt ist"
- **[hoch/api] trimesh (API concatenate)** — trimesh 5 gibt für trimesh.util.concatenate den Obertyp Geometry statt Trimesh zurück (geänderte Typannotationen)  
  _Ort:_ §0 „Warum trimesh gesperrt ist"; §3 P6 Schritt 2
- **[hoch/api] trimesh (API trimesh.voxel.ops)** — trimesh.voxel.ops.matrix_to_marching_cubes und mesh.voxelized(pitch).fill() existieren in trimesh 5 unverändert und liefen ohne Änderung durch  
  _Ort:_ §0; §3 P6 Schritt 3; §5 „Was P6 wirklich kostete"
- **[mittel/fassung] CPython 3.13/3.14** — Python 3.14.2 ist die in der Arbeitsumgebung gefahrene Fassung; 3.13 die der CI  
  _Ort:_ §0 „Python"; §3 P5
- **[niedrig/sonstiges] Semantic Versioning (semver.org)** — Pakete unter Fassung 1.0 dürfen nach Semantic Versioning in einem Minor-Sprung alles ändern  
  _Ort:_ §2 B
- **[mittel/funktionsumfang] pip (--upgrade-strategy)** — pip lässt ohne --upgrade-strategy eager alles stehen, was offene Untergrenzen bereits erfüllen  
  _Ort:_ Schlussabsatz §5
- **[niedrig/funktionsumfang] OpenSCAD / Slicer / Ollama** — OpenSCAD, Slicer und Ollama werden nur extern aufgerufen; ihre Fassung ist Sache des Rechners  
  _Ort:_ §1 Nicht-Ziele

## Intern prüfbare Behauptungen (15)

- **[hoch]** constraints.txt führt 91 Zeilen, davon rund 72 feste Fassungen  
  _Prüfen:_ Zeilen zählen in constraints.txt, nicht-Kommentarzeilen mit == zählen  
  _Ort:_ §0 „Der Satz und seine Grenzen"
- **[hoch]** In pyproject.toml steht genau eine Obergrenze: trimesh>=4.4,<5 (Zeile 23); die übrigen 22 Abhängigkeiten haben offene Untergrenzen  
  _Prüfen:_ pyproject.toml [project].dependencies durchsehen, nach '<' greppen — laut §5 ist trimesh 5 inzwischen erledigt, der Pin müsste gelöst sein (Widerspruch prüfen)  
  _Ort:_ §0; §3 P6
- **[hoch]** Die Engführung auf Trimesh liegt an einer Stelle: app/core/geom/mesh.py:255, concatenated()  
  _Prüfen:_ app/core/geom/mesh.py um Zeile 255 lesen; grep nach 'trimesh.util.concatenate' in app/  
  _Ort:_ §0; §3 P6
- **[mittel]** Die Voxelaufrufe liegen in app/core/geom/boolean.py:256 und :267  
  _Prüfen:_ boolean.py an diesen Zeilen lesen; grep 'voxel'  
  _Ort:_ §0; §3 P6
- **[mittel]** trimesh-Bestand: 37 Dateien unter app/ mit 194 Fundstellen, dazu 47 Testdateien  
  _Prüfen:_ grep -rl trimesh app/ | wc -l und grep -rc, ebenso tests/  
  _Ort:_ §0 „Wie groß die trimesh-Migration wirklich ist"
- **[mittel]** tests/test_boolean.py:63 erzwingt jede Stufe der Rückfallkette einzeln, :84 prüft die Rundungs-Ausweisung der Voxelstufe  
  _Prüfen:_ tests/test_boolean.py an diesen Zeilen lesen  
  _Ort:_ §0
- **[hoch]** requires-python = ">=3.13"; die CI fährt an drei Stellen 3.13 (build.yml Zeilen 55, 159, 390)  
  _Prüfen:_ pyproject.toml und .github/workflows/build.yml prüfen  
  _Ort:_ §0 „Python"; §3 P5
- **[mittel]** Wöchentlicher CI-Job „Neueste Fassungen" läuft montags 5 Uhr ohne constraints.txt; Sitzungsstart-Hook erinnert nach 90 Tagen  
  _Prüfen:_ Workflow-Datei mit cron-Eintrag und .claude/hooks/ Sitzungsstart-Skript prüfen  
  _Ort:_ §0 „Was schon läuft"; §5 Schluss
- **[mittel]** tools/check_env.py bietet --outdated, --install, --freeze; dreizehn Tests in tests/test_toolchain.py  
  _Prüfen:_ tools/check_env.py --help; Testfunktionen in tests/test_toolchain.py zählen  
  _Ort:_ §0; §5 Schlussabsatz
- **[hoch]** P0 nicht abnehmbar: tests/test_sketch_editor.py reißt den Prozess nativ ab (access violation / stack overflow); ohne diese Datei laufen 422 UI-Tests grün  
  _Prüfen:_ Volllauf fahren; tests/test_sketch_editor.py einzeln und zusammen mit den Qt-Tests; ROADMAP nach dem offenen Punkt durchsehen  
  _Ort:_ §3 P0; §5 „P0 im Klartext"
- **[hoch]** Abbruch besteht weiter, fassungsunabhängig; verifiziert wurde in Blöcken mit rund 3 900 grünen Tests  
  _Prüfen:_ .venv\Scripts\python.exe -m pytest -q — Gesamtzahl und Abbruchverhalten heute messen  
  _Ort:_ §5
- **[hoch]** P1 bis P4 und P6 sind erledigt, alle in Commit d526a53; P5 (Python 3.14 in der CI) ist offen  
  _Prüfen:_ git show d526a53; build.yml auf einen 3.14-Matrixeintrag prüfen  
  _Ort:_ §5 Fortschrittstabelle
- **[mittel]** P6 Messwert: 22 636 statt 815 104 Dreiecke bei gleicher Kantenlänge  
  _Prüfen:_ Dezimierungs-/Remesh-Kennzahlen erneut messen (tests/test_missing_ops.py, Abschnitt „das Netz")  
  _Ort:_ §5 Fortschrittstabelle
- **[mittel]** P6 kostete zwei Zeilen: export/writer.py und examples.py riefen trimesh.util.concatenate direkt auf; dazu drei Tests an alten Zahlen  
  _Prüfen:_ git show d526a53 -- app/core/export/writer.py; grep nach trimesh.util.concatenate  
  _Ort:_ §5 „Was P6 wirklich kostete"
- **[mittel]** remesh_uniform gegen remesh_mesh: unter trimesh 5 Faktor 5,2 (160 084 gegen 30 648) statt Hundertfaches, Kantenstreuung 0,555 gegen 0,410 — Begründung der eigenen Operation ist schwächer geworden  
  _Prüfen:_ Beide Operationen im Register prüfen und die Kennzahlen erneut messen; ROADMAP auf einen daraus entstandenen Punkt durchsehen  
  _Ort:_ §5 letzter Absatz