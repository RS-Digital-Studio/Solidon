# Konzept: die Fassungen aktualisieren

Stand 14.08.2026, nachrecherchiert am 19.08.2026. Anlass: Der festgeschriebene Satz in `constraints.txt` ist
gepflegt genug, dass nichts bricht — aber niemand hat je nachgesehen, was es
Neues gibt. `tools/check_env.py --outdated` sagt es seit heute. Dieses Konzept
sagt, was damit geschieht.

Es gilt zusammen mit `AGENTS.md` (Checkliste „neue Abhängigkeit"), `CLAUDE.md`
(Befehle) und dem Kopf von `constraints.txt` (warum es die Datei gibt).

---

## §0 Ist-Zustand, nachgesehen am 14.08.2026

> **Dieser Abschnitt beschreibt den Vormittag des 14.08.2026 — und er war am
> Abend desselben Tages überholt.** §5 hält fest, dass der Sprung an
> demselben Tag gemacht wurde; §0 und §3 stehen weiter im Präsens davor. Das
> Dokument widerspricht sich damit auf seinem eigenen Stichtag, an vier
> Stellen. Sie sind unten einzeln vermerkt. Nachgeprüft am 19.08.2026 gegen
> `main` (`b0415d6`).

Jede Aussage hier ist gemessen oder im Code belegt, nicht erinnert.

**Der Satz und seine Grenzen.** `constraints.txt` führt 91 Zeilen, davon rund
72 feste Fassungen. In `pyproject.toml` steht **genau eine Obergrenze** —
`trimesh>=4.4,<5` (Zeile 23). Alle übrigen 22 Abhängigkeiten haben offene
Untergrenzen; keine davon verbietet eine Aktualisierung.

> **Die Obergrenze gibt es nicht mehr, und die Datei ist gewachsen.**
> `pyproject.toml:26` verlangt heute `trimesh>=5.0` — P6 ist durch, gemacht
> am Abend des 14.08. `constraints.txt` führt 93 Zeilen mit 73 festen
> Fassungen (Stand 19.08.2026). **Damit steht in `pyproject.toml` heute keine
> einzige Obergrenze mehr.**
>
> *Ein Nebenbefund außerhalb dieses Dokuments:* `CLAUDE.md:95` nennt
> `trimesh<5` weiterhin als „aufgeschobene Migration". Der Satz ist seit dem
> 14.08. falsch und führt jede Sitzung in die Irre, die ihn liest.

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

> **Diese Tabelle war am Abend desselben Tages abgearbeitet** — der Commit
> sagt es wörtlich: „`--outdated` sagt jetzt: nichts ist neuer." Sie liest
> sich als offene Arbeitsliste und ist keine.
>
> **Am 19.08.2026 ist sie wieder eine, mit drei Zeilen** (recherchiert gegen
> PyPI und die Freigabeankündigungen):
>
> | Paket | fest | neu | Einschätzung |
> |---|---|---|---|
> | PySide6 / shiboken6 | 6.11.1 | **6.11.2** (18.08.2026) | Qt 6.11.2 mit rund 400 Fehlerbehebungen; abi3-Räder für 3.10 bis 3.14 |
> | vtk | 9.6.2 | **9.7.0** (15.08.2026) | **gesperrt durch pyvista** — dessen Metadaten verlangen `vtk<9.7.0` |
> | pillow | 12.3.0 | 12.3.0 | unverändert; die festgeschriebene Fassung schließt CVE-2026-55798 bereits ein |
>
> Der VTK-Fall ist der interessante: Die neue Fassung ist da, aber pyvista
> 0.48.4 schließt sie in seinen Metadaten aus. Wer sie trotzdem zieht, bricht
> die Auflösung — hier entsteht die nächste Obergrenze, und zwar nicht in
> unserer Hand. VTK 9.7 verlangt außerdem mindestens Python 3.10 und bildet
> numpy-Typen jetzt über den zugrunde liegenden C-Typ ab.
>
> Alles andere ist auf Stand: numpy 2.5.2, scipy 1.18.0, trimesh 5.0.0,
> manifold3d 3.5.2, shapely 2.1.2, scikit-image 0.26.0, matplotlib 3.11.1,
> networkx 3.6.1, pyvistaqt 0.12.0 — jeweils die neueste Fassung.

**Warum trimesh gesperrt ist.** Beim ersten echten CI-Lauf zog ein frisches
Environment trimesh 5.0.0. Der Sprung riss mypy — die neuen Annotationen geben
für `concatenate` den Obertyp `Geometry` statt `Trimesh` — und mehrere Tests
(ROADMAP, „Der erste echte CI-Lauf"). Die Reaktion war zweiteilig: Die
Engführung auf `Trimesh` lebt seither an **einer** Stelle
(`app/core/geom/mesh.py:255`, `concatenated`), und trimesh wurde unter 5
festgenagelt. Am 01.08.2026 ist 5.0 erschienen; der Eintrag in der ROADMAP
nennt die Voxelkette über `trimesh.voxel.ops` als empfindlichste Stelle und
drei zusätzliche rote Tests unter Windows.

> **Sie ist nicht mehr gesperrt.** Der Absatz steht im Präsens und beschreibt
> einen Zustand, den derselbe Tag beendet hat: `pyproject.toml:26` verlangt
> `trimesh>=5.0`, installiert ist 5.0.0. Er bleibt als Begründung stehen,
> warum die Sperre einmal richtig war — nicht als Beschreibung von heute.
> trimesh 5.0.0 (01.08.2026) ist weiterhin die neueste Fassung; eine 6er-Reihe
> gibt es nicht (nachgesehen am 19.08.2026).

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

> **Der Satz gilt weiter, und P5 bekommt eine Frist von außen** (recherchiert
> am 19.08.2026). Die Arbeitsumgebung fährt inzwischen 3.14.7 (05.08.2026),
> die CI weiter 3.13. Neu ist der Zeitplan darüber: **Python 3.15.0rc1 ist am
> 04.08.2026 erschienen, rc2 steht für den 01.09. und die endgültige Freigabe
> für den 01.10.2026.** Damit rückt die Frage nach, ob die CI auf 3.14 geht,
> bevor 3.15 da ist — und eine Antwort gibt es schon: **PySide6 6.11.2
> deklariert `Python <3.15, >=3.10`.** Auf 3.15 gibt es also vorerst kein Qt,
> und P5 bleibt eine Entscheidung zwischen 3.13 und 3.14, nicht zwischen 3.13
> und dem Neuesten.

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

> **Diesen Rückweg gibt es nicht mehr.** P6 ist durch (`d526a53`, 14.08.2026),
> der Pin ist gelöst. Gemessen wurde dabei: 22 636 statt 815 104 Dreiecke bei
> gleicher Kantenlänge — die Voxelkette rechnet unter trimesh 5 anders, und
> das war der Grund, sie einzeln zu prüfen.

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
| P0 Referenz | **teilweise** | — | Absturz besteht, aber fassungsunabhängig (s. u.) |
| P1 Fehlerbehebungen | **erledigt** | `d526a53` | numpy 2.5.2, platformdirs 4.11.3, charset-normalizer 3.5.0 |
| P2 Werkzeuge | **erledigt** | `d526a53` | pytest-forked 1.7.5, setuptools 84.0.0 |
| P3 ruff | **erledigt** | `d526a53` | 0.16.3, keine neuen Befunde, kein Formatdiff |
| P4 die drei unter 1.0 | **erledigt** | `d526a53` | ast_serialize 0.8.0, librt 0.15.0, fast_simplification 0.2.0 |
| P5 Python 3.14 in der CI | offen | — | — |
| P6 trimesh 5 | **erledigt** | `d526a53` | 22 636 statt 815 104 Dreiecke bei gleicher Kantenlänge |

**Abweichung vom Konzept, ausdrücklich als solche.** §2 A verlangte die
Staffelung nach Risiko, ein Paket je Commit. Auf Ansage wurde stattdessen in
einem Zug aktualisiert und in einem Commit abgelegt. Das ist vertretbar, weil
jede Fassung einzeln gemessen wurde, bevor sie einzog — aber es heißt auch:
Wäre etwas rot geworden, hätte es neun Verdächtige gegeben. Für die nächste
Runde gilt §2 A wieder.

**P0 im Klartext.** Ein Volllauf bricht weiterhin nativ ab
(`access violation`), sobald genug Qt-Tests zusammen laufen. Das ist gemessen
**unabhängig von den Fassungen**: derselbe Abbruch unter trimesh 4.12.2 wie
unter 5.0.0. Deshalb blockierte er die Aktualisierung nicht. Verifiziert wurde
stattdessen in Blöcken — rund 3 900 Tests grün, kein Fehler, der nicht
zugeordnet wäre. Der Abbruch selbst bleibt offen und gehört nicht hierher.

**Was P6 wirklich kostete.** Zwei Zeilen: `export/writer.py` und
`examples.py` riefen `trimesh.util.concatenate` direkt auf, statt die
Engführung `concatenated` zu nehmen. Dazu drei Tests, die an den alten Zahlen
hingen. Der gefürchtete Teil — die Voxelstufe der Rückfallkette über
`trimesh.voxel.ops` — lief ohne eine Änderung durch.

**Eine Frage, die der Sprung aufgeworfen hat.** `remesh_uniform` existiert als
eigene Operation, weil `remesh_mesh` für dieselbe Kantenlänge das Hundertfache
an Dreiecken brauchte. Unter trimesh 5 ist daraus Faktor 5,2 geworden (160 084
gegen 30 648), bei einer Kantenstreuung von 0,555 gegen 0,410. Die Operation
bleibt die bessere, aber ihre Begründung ist schwächer geworden. Das ist keine
Aufgabe dieses Konzepts — es gehört nur festgehalten, solange die Zahlen frisch
sind.

Die Werkzeuge dafür stehen seit dem 14.08.2026: `tools/check_env.py` mit
`--outdated`, `--install` und `--freeze`, dreizehn Tests in
`tests/test_toolchain.py`, und die Erinnerung im Sitzungsstart-Hook. Wichtig
beim Anheben: `--upgrade-strategy eager`, sonst lässt pip alles stehen, was die
offenen Untergrenzen schon erfüllt — und das sind sie fast alle.

---

## Nachrecherchiert am 19.08.2026

Fünfzehn Aussagen über den eigenen Stand geprüft — **zehn stimmen, vier sind
überholt, eine ist falsch** — und der festgeschriebene Satz gegen PyPI
gehalten.

**Das Dokument widerspricht sich auf seinem eigenen Stichtag, an vier
Stellen.** §0 und §3 beschreiben den Vormittag des 14.08.2026, §5 hält fest,
dass der Sprung am Abend desselben Tages gemacht wurde. Wer §0 liest, hält
`trimesh<5` für geltendes Recht; wer §5 liest, weiß es besser. Alle vier
Stellen tragen jetzt einen Vermerk.

**In `pyproject.toml` steht heute keine einzige Obergrenze mehr.** Das ist die
Kernaussage dieses Dokuments, und sie hat sich umgedreht: Die eine Grenze,
`trimesh>=4.4,<5`, ist zu `trimesh>=5.0` geworden.

**Ein Nebenbefund außerhalb dieses Dokuments, und kein kleiner:**
`CLAUDE.md:95` nennt `trimesh<5` weiter als „aufgeschobene Migration, kein
Versehen". Der Satz ist seit fünf Tagen falsch und steht an einer Stelle, die
jede Sitzung liest.

**Was der Index heute neuer anbietet** — die Tabelle in §0 war am Abend des
14.08. leer und hat wieder drei Zeilen:

- **PySide6 und shiboken6 6.11.2** (18.08.2026), Qt 6.11.2 mit rund 400
  Fehlerbehebungen. Ein gewöhnlicher Pflegesprung.
- **vtk 9.7.0** (15.08.2026) — **nicht ziehbar**: pyvista 0.48.4 verlangt in
  seinen Metadaten `vtk<9.7.0`. Hier entsteht die nächste Obergrenze, und sie
  liegt nicht in unserer Hand. VTK 9.7 bildet numpy-Typen jetzt über den
  zugrunde liegenden C-Typ ab — ein Sprung, den man ohnehin nicht nebenbei
  macht.
- Alles andere ist auf Stand: numpy 2.5.2, scipy 1.18.0, trimesh 5.0.0,
  manifold3d 3.5.2, shapely 2.1.2, scikit-image 0.26.0, matplotlib 3.11.1,
  networkx 3.6.1, pyvistaqt 0.12.0, pillow 12.3.0 (schließt CVE-2026-55798
  ein).

**P5 bekommt eine Frist von außen.** Python 3.15.0rc1 ist am 04.08.2026
erschienen, die endgültige Freigabe steht für den 01.10.2026. Die Antwort auf
die Frage, ob man gleich auf 3.15 zielt, steht schon fest: **PySide6 6.11.2
deklariert `Python <3.15`.** P5 bleibt damit die Wahl zwischen 3.13 und 3.14.

**Nicht geprüft und deshalb offen gelassen:** ob die vier Tore heute grün sind.
Dieser Abgleich hat gelesen und gezählt, nicht `/pruefen` gefahren; und im
Arbeitsbaum liegen Änderungen einer parallelen Sitzung, die nicht zu dieser
Durchsicht gehören. P0 („der Volllauf bricht nativ ab") bleibt darum stehen,
wie es steht.
