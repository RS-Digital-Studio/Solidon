# Konzept: die Fassungen aktualisieren

Stand 14.08.2026. Anlass: Der festgeschriebene Satz in `constraints.txt` ist
gepflegt genug, dass nichts bricht — aber niemand hat je nachgesehen, was es
Neues gibt. `tools/check_env.py --outdated` sagt es seit heute. Dieses Konzept
sagt, was damit geschieht.

Es gilt zusammen mit `AGENTS.md` (Checkliste „neue Abhängigkeit"), `CLAUDE.md`
(Befehle) und dem Kopf von `constraints.txt` (warum es die Datei gibt).

---

## §0 Ist-Zustand, nachgesehen am 14.08.2026

Jede Aussage hier ist gemessen oder im Code belegt, nicht erinnert.

**Der Satz und seine Grenzen.** `constraints.txt` führt 91 Zeilen, davon rund
72 feste Fassungen. In `pyproject.toml` steht **genau eine Obergrenze** —
`trimesh>=4.4,<5` (Zeile 23). Alle übrigen 22 Abhängigkeiten haben offene
Untergrenzen; keine davon verbietet eine Aktualisierung.

**Was der Index neuer anbietet** (gemessen mit `--outdated`):

| Paket | jetzt | neu | Einschätzung |
|---|---|---|---|
| numpy | 2.5.1 | 2.5.2 | Fehlerbehebung |
| charset-normalizer | 3.4.9 | 3.5.0 | mittelbar, über requests |
| platformdirs | 4.11.0 | 4.11.3 | Fehlerbehebung |
| ruff | 0.16.1 | 0.16.3 | **kann neue Befunde bringen** |
| setuptools | 83.0.0 | 84.0.0 | Hauptsprung, trägt den Bau |
| pytest-forked | 1.6.0 | 1.7.5 | trägt die Suite selbst |
| ast_serialize | 0.6.0 | 0.8.0 | Fassung unter 1: alles darf sich ändern |
| librt | 0.13.0 | 0.15.0 | Fassung unter 1: dasselbe |
| fast_simplification | 0.1.13 | 0.2.0 | **Fassung unter 1, und sie dezimiert Netze** |
| trimesh | 4.12.2 | 5.0.0 | **durch `<5` ausgeschlossen** |

**Warum trimesh gesperrt ist.** Beim ersten echten CI-Lauf zog ein frisches
Environment trimesh 5.0.0. Der Sprung riss mypy — die neuen Annotationen geben
für `concatenate` den Obertyp `Geometry` statt `Trimesh` — und mehrere Tests
(ROADMAP, „Der erste echte CI-Lauf"). Die Reaktion war zweiteilig: Die
Engführung auf `Trimesh` lebt seither an **einer** Stelle
(`app/core/geom/mesh.py:255`, `concatenated`), und trimesh wurde unter 5
festgenagelt. Am 01.08.2026 ist 5.0 erschienen; der Eintrag in der ROADMAP
nennt die Voxelkette über `trimesh.voxel.ops` als empfindlichste Stelle und
drei zusätzliche rote Tests unter Windows.

**Wie groß die trimesh-Migration wirklich ist.** 37 Dateien unter `app/` mit
194 Fundstellen, dazu 47 Testdateien. Die beiden Stellen, an denen es hängt,
sind aber benannt und klein:

- `app/core/geom/mesh.py:255` — `concatenated()`, die eine Engführung
- `app/core/geom/boolean.py:256` — `trimesh.voxel.ops.matrix_to_marching_cubes`
- `app/core/geom/boolean.py:267` — `raw.voxelized(pitch).fill()`

Die Voxelstufe ist die vierte und letzte der Booleschen Rückfallkette (§17.2).
`tests/test_boolean.py:63` erzwingt jede Stufe einzeln, `:84` prüft, dass die
Voxelstufe ihre Rundung ausweist — die Migration hat also einen Wächter.

**Python.** `requires-python = ">=3.13"`. Die CI fährt an allen drei Stellen
`3.13` (Zeilen 55, 159, 390 in `build.yml`), die Arbeitsumgebung fährt 3.14.2.
Das ist erlaubt und gewollt, aber es heißt: **Was hier grün ist, ist unter der
Fassung grün, die niemand ausliefert.**

**Was schon läuft.** Der wöchentliche CI-Job „Neueste Fassungen" (montags 5 Uhr,
ohne `constraints.txt`) meldet eine Fassung, die etwas bricht. Der
Sitzungsstart-Hook meldet Abweichungen der lokalen Umgebung und erinnert nach
90 Tagen an die Pflege.

---

## §1 Ziel und Nicht-Ziele

**Ziel:** Der festgeschriebene Satz enthält die neuesten Fassungen, die
nachweislich verträglich sind — nachgewiesen durch einen grünen Volllauf, nicht
durch Zuversicht.

**Nicht-Ziele**, ausdrücklich:

- **Keine Aktualisierung ohne grüne Referenz.** Solange die Suite aus einem
  anderen Grund rot ist, wird nichts angehoben: Sonst ist nicht zu trennen, was
  die neue Fassung gebrochen hat und was vorher schon kaputt war.
- **Kein Anheben der Untergrenzen in `pyproject.toml`.** Sie sind bewusst
  offen. Fest wird in `constraints.txt`, nicht im Paketvertrag.
- **Kein Python-Sprung in der CI** als Teil dieses Vorhabens. Er ist ein
  eigenes Paket mit eigenem Risiko (§3, P5).
- **Keine externen Programme.** OpenSCAD, Slicer und Ollama werden nach §36
  aufgerufen, nie mitgeliefert; ihre Fassung ist Sache des Rechners.

---

## §2 Design-Entscheidungen

**A — In Stufen nach Risiko, nicht alles auf einmal.** Neun Pakete in einem
Zug anzuheben und dann einen roten Lauf zu sehen, heißt: neun Verdächtige, kein
Beweis. Die Reihenfolge ist deshalb nach Risiko gestaffelt, und jede Stufe
endet mit einem grünen Lauf und einem eigenen Commit.

**B — Die Fassungen unter 1.0 sind eigene Pakete.** `ast_serialize`, `librt`
und `fast_simplification` dürfen nach Semantic Versioning in einem
Minor-Sprung alles ändern. `fast_simplification` dezimiert Netze — ein
verändertes Ergebnis fällt in den Geometrietests auf, aber nur, wenn es
einzeln angehoben wird.

**C — `ruff` wird getrennt angehoben.** Ein Linter-Sprung kann neue Befunde
und ein geändertes Format bringen. Beides ist harmlos, erzeugt aber einen
Diff über viele Dateien — der gehört nicht in einen Commit mit einer
Bibliothek.

**D — trimesh 5 ist eine eigene Migration, kein Paket dieses Konzepts.** Es
bekommt hier einen Platz (P6) und eine Vorbereitung, aber der Durchgang selbst
ist umfangreicher als alles andere zusammen und wird erst begonnen, wenn P1
bis P4 stehen.

**E — Der Nachweis ist der Volllauf, nicht die Teilmenge.** Bei
Geometriebibliotheken (numpy, fast_simplification, trimesh) genügt kein
gezielter Testlauf: Die Kennzahlen hängen quer über den Korpus. Bei
Werkzeugen (ruff, setuptools, pytest-forked) genügt das Tor.

**F — `--freeze` schreibt den Satz, nicht die Hand.** Nach jedem grünen Lauf
wird `constraints.txt` mit `tools/check_env.py --freeze` neu geschrieben. Von
Hand einzelne Zeilen zu ändern, führt zu einem Satz, den niemand reproduzieren
kann.

**G — Bei Rot gilt die alte Fassung.** Nicht „schnell reparieren": Die
Aktualisierung wird zurückgenommen, der Befund wird notiert, und daraus wird
ein eigenes Paket. Eine Fassung, die Arbeit kostet, ist keine Pflege mehr.

---

## §3 Arbeitspakete

Jedes Paket endet mit grünem Tor und **einem** Commit. Die Reihenfolge ist
verbindlich; ein rotes Paket blockiert das nächste nicht, sondern wird nach §2 G
zurückgenommen.

| Paket | Inhalt | Umfang | Verifikation |
|---|---|---|---|
| **P0** | Grüne Referenz herstellen | S | Volllauf grün, **Voraussetzung für alles** |
| **P1** | Fehlerbehebungen: numpy, platformdirs, charset-normalizer | S | Volllauf |
| **P2** | Werkzeuge: pytest-forked, setuptools | S | Tor + ein Paketbau |
| **P3** | ruff 0.16.3 | S | `ruff check`, `ruff format --check`, Diff sichten |
| **P4** | Die drei unter 1.0, **einzeln**: ast_serialize, librt, fast_simplification | M | je ein Volllauf; bei fast_simplification zusätzlich die Kennzahlen der Dezimierung |
| **P5** | Python 3.14 in der CI — erst als vierter Matrixeintrag, dann als Standard | L | Volle Matrix grün auf drei Plattformen |
| **P6** | trimesh 5 | XL | eigener Durchgang, siehe §4 |

### P0 — die Referenz

Ohne sie ist jedes weitere Paket wertlos. Zum Zeitpunkt dieses Konzepts ist
die Suite **nicht** abnehmbar: `tests/test_sketch_editor.py` reißt den Prozess
in Kombination mit vorher gelaufenen Qt-Tests nativ ab (`access violation`
bzw. `stack overflow`), und die Ursache liegt in laufender Arbeit einer
zweiten Sitzung. Ohne diese eine Datei laufen dieselben 422 UI-Tests grün.

**Erst wenn ein Volllauf grün ist, beginnt P1.**

### P1 bis P3 — die einfachen

Ablauf je Paket, immer gleich:

1. `.venv\Scripts\python.exe -m pip install -U <paket>`
2. Tor: `pytest`, `ruff check`, `ruff format --check`, `mypy`
3. `python tools/check_env.py --freeze`
4. Commit: was angehoben wurde und warum, mit den gemessenen Zahlen

### P4 — die drei unter 1.0

Dasselbe, aber **je Paket ein eigener Durchlauf und ein eigener Commit**. Bei
`fast_simplification` zusätzlich: die Dezimierung gegen den Korpus messen
(`tests/test_missing_ops.py`, Abschnitt „das Netz") und die Kennzahlen im
Commit festhalten. Ändert sich das Ergebnis, ist das kein Fehler, aber eine
Aussage — und sie gehört dokumentiert.

### P5 — Python 3.14 in der CI

Die Arbeitsumgebung fährt 3.14, die CI 3.13. Solange das so ist, prüft die CI
etwas anderes, als hier entwickelt wird. Zwei Schritte:

1. 3.14 **zusätzlich** in die Matrix (`build.yml`, Job `suite`) — beide
   Fassungen grün heißt: der Code trägt beide.
2. Erst dann entscheiden, ob 3.13 der ausgelieferte Stand bleibt.

Nicht-Ziel: `requires-python` anheben. Das schlösse Nutzer aus, ohne Gewinn.

### P6 — trimesh 5

Der Durchgang, den die ROADMAP seit dem ersten CI-Lauf vor sich herschiebt.
Vorgehen:

1. Pin in `pyproject.toml` lösen, `pip install -U trimesh`
2. `mypy` — erwartet wird ein Befund an `app/core/geom/mesh.py:255`
   (`concatenate` gibt `Geometry`); die Engführung liegt dort an einer Stelle
3. Die Voxelstufe gezielt: `pytest tests/test_boolean.py -k voxel`.
   `trimesh.voxel.ops.matrix_to_marching_cubes` und `raw.voxelized().fill()`
   sind die beiden Aufrufe (`boolean.py:256`, `:267`)
4. Volllauf **unter Windows und Linux** — der erste Versuch zeigte drei rote
   Tests, die nur unter Windows auftraten
5. Erst dann `--freeze` und Commit

**Rückfalloption:** Der Pin `<5` bleibt bestehen, bis alle vier Schritte grün
sind. Wird P6 abgebrochen, kostet das nichts — der Zustand davor ist der
ausgelieferte.

---

## §4 Leitplanken

- **Ein Paket, ein Commit, ein grünes Tor.** Kein Stapeln.
- **Kein `pip install -U` ohne `--freeze` danach.** Sonst weicht der
  installierte Stand vom festgeschriebenen ab, und der Sitzungsstart-Hook
  meldet zu Recht eine Abweichung.
- **Der Volllauf zählt, nicht der Teillauf** — außer bei P2 und P3 (§2 E).
- **Zwei Sitzungen, eine Umgebung.** Das Repository wird geteilt, und eine
  Paketaktualisierung ändert die Umgebung **aller** Sitzungen mitten in ihrer
  Arbeit. Vor P1 bis P6 ist abzustimmen, dass niemand sonst darin arbeitet.
- **Erwartetes Inkonsistenzfenster:** zwischen `pip install -U` und `--freeze`
  weicht die Umgebung vom Satz ab. Es ist kurz und beabsichtigt; bricht der
  Lauf dazwischen ab, stellt `--install` den alten Stand wieder her.

## §5 Fortschritt

| Paket | Status | Commit | Gemessen |
|---|---|---|---|
| P0 Referenz | offen | — | blockiert durch fremde Baustelle |
| P1 Fehlerbehebungen | offen | — | — |
| P2 Werkzeuge | offen | — | — |
| P3 ruff | offen | — | — |
| P4 die drei unter 1.0 | offen | — | — |
| P5 Python 3.14 in der CI | offen | — | — |
| P6 trimesh 5 | offen | — | — |

Die Werkzeuge dafür stehen seit dem 14.08.2026: `tools/check_env.py` mit
`--outdated`, `--install` und `--freeze`, elf Tests in
`tests/test_toolchain.py`, und die Erinnerung im Sitzungsstart-Hook.
