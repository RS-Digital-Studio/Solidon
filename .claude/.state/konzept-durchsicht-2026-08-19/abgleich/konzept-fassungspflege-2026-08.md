# Abgleich: `.claude/konzept-fassungspflege-2026-08.md`

Geprüft am 19.08.2026 gegen `main` (HEAD `b0415d6`). Dokumentstand laut Kopf:
14.08.2026. Es wurde nichts im Repository geändert.

**Zählung der fünfzehn intern prüfbaren Behauptungen:**

| Urteil | Anzahl |
|---|---|
| stimmt | 10 |
| überholt | 4 |
| falsch | 1 |
| unprüfbar | 0 |

Dazu **vier Widersprüche innerhalb des Dokuments** (unten, eigener Abschnitt) —
alle vier gehen auf dieselbe Ursache zurück: §0 und §3 beschreiben den Zustand
*vor* dem Sprung vom 14.08.2026, §5 hält fest, dass der Sprung an demselben Tag
gemacht wurde. Das Dokument widerspricht sich damit auf dem eigenen Stichtag.

---

## 1 — `constraints.txt` führt 91 Zeilen, davon rund 72 feste Fassungen

**Urteil: überholt.**

Beleg:

```
$ wc -l < constraints.txt          → 93
$ grep -c '^[^#].*==' constraints.txt → 73
```

Gemessen wurde für §0 offenbar der Stand *vor* `d526a53`:

```
$ git show d526a53~1:constraints.txt | wc -l   → 91
$ git show d526a53~1:constraints.txt | grep -c '^[^#].*==' → 71
```

`d526a53` (14.08.2026) hat die Datei zuletzt angefasst; seither ist sie
unverändert (`git log --since=2026-08-14 -- constraints.txt` ist leer).

**Stattdessen:** „`constraints.txt` führt 93 Zeilen, davon 73 feste Fassungen."

---

## 2 — Genau eine Obergrenze in `pyproject.toml`: `trimesh>=4.4,<5` (Zeile 23); die übrigen 22 Abhängigkeiten haben offene Untergrenzen

**Urteil: überholt** — und in der Zahl „22" zusätzlich **falsch, schon damals**.

Beleg für die Obergrenze:

```
$ grep -n '<' pyproject.toml   → keine Treffer
$ grep -n trimesh pyproject.toml
23:  # hat er sich beim gleichmäßigen Vernetzen — dieselbe Lochplatte, dieselbe
26:  "trimesh>=5.0",
```

Das Projekt hat heute **keine** Obergrenze mehr, und das ist bewacht:
`tests/test_toolchain.py:215`, `test_the_project_currently_pins_nothing_from_above`
— „Fällt dieser Test, hat jemand eine Obergrenze gesetzt". Der Nachbartest
:193 sagt es im Docstring ausdrücklich: „Das Projekt selbst hat seit dem
trimesh-5-Sprung am 14.08.2026 **keine** Obergrenze mehr."

Beleg für die Zahl:

```
$ python -c "…tomllib über pyproject.toml, dependencies + optional-dependencies…"
gesamt 25   (heute)
damals 25   (git show d526a53~1:pyproject.toml, gleiche Zählung)
```

25 Abhängigkeiten, davon damals eine mit Obergrenze — die übrigen waren **24**,
nicht 22. Die Zahl war am 14.08.2026 bereits um zwei daneben.

**Stattdessen:** „In `pyproject.toml` steht **keine** Obergrenze mehr; alle 25
Abhängigkeiten haben offene Untergrenzen. Dass das so bleibt, prüft
`tests/test_toolchain.py::test_the_project_currently_pins_nothing_from_above`."

---

## 3 — Die Engführung auf `Trimesh` liegt an einer Stelle: `app/core/geom/mesh.py:255`, `concatenated()`

**Urteil: stimmt** (Zeilennummer verschoben).

`concatenated()` steht heute auf `app/core/geom/mesh.py:261`, der Aufruf von
`trimesh.util.concatenate` auf :269. Sie ist die **einzige** Stelle in `app/`:

```
$ grep -rn "trimesh.util.concatenate" app/
app/core/geom/mesh.py:269
```

(In `tests/` gibt es sie weiter fünfmal — dort ist die Engführung nicht nötig.)

**Stattdessen:** Zeilennummer auf 261 ziehen, sonst unverändert.

---

## 4 — Die Voxelaufrufe liegen in `app/core/geom/boolean.py:256` und `:267`

**Urteil: stimmt** (Zeilennummern verschoben).

```
app/core/geom/boolean.py:270:  body = trimesh.voxel.ops.matrix_to_marching_cubes(matrix=combined, pitch=pitch)
app/core/geom/boolean.py:281:  grid = mesh.raw.voxelized(pitch=pitch).fill()
```

Die Aussage „vierte und letzte Stufe der Rückfallkette" stimmt ebenfalls:
`boolean.py:42`, `FULL_CHAIN = ("direct", "welded", "jittered", "voxel")`.

**Stattdessen:** `:270` und `:281`.

---

## 5 — trimesh-Bestand: 37 Dateien unter `app/` mit 194 Fundstellen, dazu 47 Testdateien

**Urteil: stimmt** (im Rahmen der Messgenauigkeit).

```
$ grep -rl --include=*.py trimesh app/ | wc -l          → 36
$ grep -r --include=*.py -c trimesh app/ | summe        → 191
$ grep -rl --include=*.py trimesh tests/ | wc -l        → 50
```

Abweichung 36/37, 191/194, 50/47 — Größenordnung unverändert. Der Satz trägt
weiter.

---

## 6 — `tests/test_boolean.py:63` erzwingt jede Stufe einzeln, `:84` prüft die Rundungs-Ausweisung

**Urteil: stimmt**, auf die Zeile genau.

```
63: @pytest.mark.parametrize("stage", ["welded", "jittered", "voxel"])
64: def test_every_stage_can_carry_the_operation_alone(stage: str) -> None:
84: def test_the_voxel_stage_says_that_it_rounded() -> None:
```

---

## 7 — `requires-python = ">=3.13"`; die CI fährt an drei Stellen 3.13 (Zeilen 55, 159, 390)

**Urteil: stimmt** (Zeilennummern verschoben).

```
pyproject.toml:9:  requires-python = ">=3.13"
.github/workflows/build.yml:55:   python-version: "3.13"
.github/workflows/build.yml:166:  python-version: "3.13"
.github/workflows/build.yml:397:  python-version: "3.13"
```

Kein einziger `3.14`-Eintrag in `build.yml`. Die Aussage „was hier grün ist,
ist unter der Fassung grün, die niemand ausliefert" gilt unverändert.

**Stattdessen:** Zeilen 55, 166, 397.

---

## 8 — Wöchentlicher CI-Job läuft montags 5 Uhr ohne `constraints.txt`; der Sitzungsstart-Hook erinnert nach 90 Tagen

**Urteil: falsch** — die erste Hälfte stimmt, die zweite nicht.

**CI-Job: stimmt.** `.github/workflows/build.yml:37-40` — `schedule:` mit
`cron: "0 5 * * 1"`; Job `latest` ab :382, Name „Neueste Fassungen", Kommentar
„ohne `constraints.txt`, also alles frisch aufgelöst".

**Hook: erinnert nicht — und meldet auch keine Abweichung.** Die 90-Tage-Regel
existiert, aber in `tools/check_env.py`:

```
tools/check_env.py:48:  DAYS_UNTIL_MAINTENANCE: Final = 90
tools/check_env.py:355: f"Der festgeschriebene Satz ist seit {days} Tagen unverändert. …"
```

Sie sitzt in `check()`. Der Hook ruft aber einen Namen, den es nicht mehr gibt:

```
.claude/hooks/solidon3d_hooks.py:102:  from tools.check_env import pruefen

$ python -c "from tools.check_env import pruefen"
ImportError: cannot import name 'pruefen' from 'tools.check_env'
```

`umgebungshinweis()` fängt jede Ausnahme ab („ein Hinweis darf nie die Sitzung
kosten") und gibt `""` zurück — der Hook schweigt also **still**. Nachgefahren:

```
$ echo '{}' | .venv/Scripts/python.exe .claude/hooks/solidon3d_hooks.py sitzungsstart
{"hookSpecificOutput": {… "additionalContext": "Projekt Solidon: … im Bauplan."}}
```

Kein Umgebungshinweis, keine Erinnerung. Ursache ist die Umbenennung
`pruefen` → `check` in `8a15cbc` (16.08.2026, „Acht Fehlertexte der
Mesh-Erzeugung sprachen nur Englisch, check_env.py nur Deutsch"); der Hook
wurde nicht mitgezogen. Eingeführt hatte beides `ee4e3cb`. Kein Test bewacht
den Hook (`grep -rl solidon3d_hooks tests/` ist leer).

Dass gerade keine Abweichung besteht (`check()` gibt heute `[], []`) und der
Satz erst fünf Tage alt ist, verdeckt den Defekt zusätzlich: Es fiele auch
dann nichts auf, wenn er meldenswert wäre.

**Stattdessen:** „Der wöchentliche CI-Job läuft (`build.yml`, `cron 0 5 * * 1`,
Job `latest`). Die 90-Tage-Erinnerung ist in `tools/check_env.py` gebaut
(`DAYS_UNTIL_MAINTENANCE`), erreicht die Sitzung aber seit `8a15cbc` nicht mehr:
`.claude/hooks/solidon3d_hooks.py:102` importiert `pruefen`, die Funktion heißt
`check`. Der Hook schluckt den Fehler still."

Dieselbe falsche Zusage steht auch in `CLAUDE.md` („Steht der Satz länger als
drei Monate, erinnert der Sitzungsstart-Hook daran") und in `AGENTS.md`-Nähe —
sie gehört an beiden Stellen korrigiert oder der Hook repariert.

---

## 9 — `tools/check_env.py` bietet `--outdated`, `--install`, `--freeze`; dreizehn Tests in `tests/test_toolchain.py`

**Urteil: stimmt.**

```
tools/check_env.py:439-458:  --install, --outdated, --freeze  (dazu --quiet)
$ grep -c "^def test_" tests/test_toolchain.py → 13
```

---

## 10 — P0 nicht abnehmbar: `tests/test_sketch_editor.py` reißt den Prozess nativ ab; ohne diese Datei laufen 422 UI-Tests grün

**Urteil: überholt.** Die Zuordnung auf diese eine Datei ist widerlegt.

`ROADMAP.md`, Abschnitt „Was am 18.08.2026 dazu gemessen wurde":

> „Der Ort des Absturzes ist zufällig — er kumuliert. Vier Läufe fielen nach
> 228, 480, 3698 und 3907 Tests. […] Damit ist die Suche nach dem *einen
> schuldigen Test* erledigt: Es gibt ihn nicht, und jede Bisektion über Tests
> läuft ins Leere."

Und nachgemessen:

```
$ .venv/Scripts/python.exe -m pytest tests/test_sketch_editor.py -q
87 passed in 6.01s
```

Die Datei ist nicht mehr der benannte Übeltäter, und die Erklärung „die
Ursache liegt in laufender Arbeit einer zweiten Sitzung" ist damit ebenfalls
hinfällig — die ROADMAP hält am 19.08.2026 ausdrücklich fest, dass ein
einzelner Lauf bei rund zwanzig Prozent Rate nichts beweist.

Neu und im Konzept nicht vorhanden: `tools/run_suite_isolated.py` (je Datei ein
Prozess). ROADMAP: „130 Testdateien einzeln gefahren: 4164 Tests, **kein
einziger Absturz**, in zwölf statt siebzehn Minuten." Damit gibt es eine
benutzbare Referenz — die Voraussetzung, die §3 P0 als unerfüllbar beschreibt,
ist praktisch herstellbar.

**Stattdessen:** „Der Volllauf bricht weiterhin nativ ab, aber nicht in einer
bestimmten Datei: Der Absturz kumuliert und fällt an zufälliger Stelle
(ROADMAP, 18.08.2026). `tests/test_sketch_editor.py` läuft allein grün. Als
Referenz dient `tools/run_suite_isolated.py` — je Datei ein Prozess, 4164 Tests
ohne Absturz."

---

## 11 — Abbruch besteht weiter, fassungsunabhängig; verifiziert in Blöcken mit rund 3 900 grünen Tests

**Urteil: überholt** in der Zahl, richtig in der Aussage.

Fassungsunabhängigkeit ist im Commit `d526a53` festgehalten („Sie tritt unter
trimesh 4 genauso auf") und in der ROADMAP bis zum 19.08.2026 bestätigt (zwölf
Wechselläufe HEAD gegen Arbeitsstand: 1/6 gegen 1/6, kein Unterschied).

Die Zahl ist gewachsen:

```
$ .venv/Scripts/python.exe -m pytest --collect-only -q | tail -1
4246 tests collected in 2.00s
```

Der isolierte Lauf der ROADMAP nennt 4164 tatsächlich gefahrene Tests.

**Stattdessen:** „rund 4 200 Tests" statt „rund 3 900".

---

## 12 — P1 bis P4 und P6 erledigt, alle in `d526a53`; P5 (Python 3.14 in der CI) offen

**Urteil: stimmt.**

`git show --stat d526a53` (14.08.2026, „trimesh 5 kostete zwei Zeilen — und
schenkt 792 468 Dreiecke") führt alle neun Anhebungen in einem Commit auf und
nennt sie namentlich: numpy 2.5.2, ruff 0.16.3, setuptools 84, pytest-forked
1.7.5, fast_simplification 0.2.0, ast_serialize 0.8.0, librt 0.15.0,
platformdirs 4.11.3, charset-normalizer 3.5.0 — alle so in `constraints.txt`
belegt (Zeilen 21, 26, 33, 44, 54, 58, 69, 79, 83, 89).

P5 ist offen: `build.yml` kennt nur `3.13` (siehe Nr. 7).

---

## 13 — P6-Messwert: 22 636 statt 815 104 Dreiecke bei gleicher Kantenlänge

**Urteil: stimmt.**

```
tests/test_missing_ops.py:234-235
app/core/geom/mesh_ops.py:548-549:
  # ging unter 4.12.2 von 796 Dreiecken auf 815 104 (Faktor 1024), unter
  # 5.0.0 auf 22 636 (Faktor 28).
```

---

## 14 — P6 kostete zwei Zeilen (`export/writer.py`, `examples.py`) plus drei Tests

**Urteil: stimmt.**

`git show d526a53 -- app/core/export/writer.py app/core/examples.py` zeigt
genau zwei geänderte Aufrufzeilen (`writer.py:620`, `examples.py:207`), beide
von `trimesh.util.concatenate` auf `concatenated`. Der Commit-Text nennt die
drei angepassten Tests; im Diff sind es `tests/test_missing_ops.py` und
`tests/test_subdivision.py`.

---

## 15 — `remesh_uniform` gegen `remesh_mesh`: Faktor 5,2 (160 084 gegen 30 648), Kantenstreuung 0,555 gegen 0,410

**Urteil: stimmt.**

```
tests/test_subdivision.py:95:   trimesh 5 teilt selbst gleichmäßig und kommt auf **0,555** …
tests/test_subdivision.py:99:   … remesh_uniform liegt bei **0,410** …
tests/test_subdivision.py:133-134: plate_holes **160 084**, remesh_uniform **30 648** —
                                   Faktor 5,2 (gemessen am 14.08.2026 unter trimesh 5.0.0).
```

**Nachtrag, der ins Konzept gehört:** Der Befund ist in Test und Docstring
nachgezogen, in der ROADMAP aber nicht. `ROADMAP.md:4976 ff.` (P16.3) führt
weiter die Zahlen von vor dem Sprung: „Streuung […] 2,224 und danach 2,224",
„3 260 416 Dreiecke für 1,5 mm", „**Faktor hundert**". Wer die Begründung von
`remesh_uniform` dort nachschlägt, liest den alten Stand. Der letzte Absatz von
§5 hat also einen offenen Rest — er ist nicht bloß „festgehalten".

---

## Widersprüche innerhalb des Dokuments

Alle vier betreffen dasselbe: §0 und §3 stehen auf dem Stand *vor*
`d526a53`, §5 auf dem Stand danach — beide unter demselben Datum.

1. **§0 „Der Satz und seine Grenzen"** behauptet die Obergrenze
   `trimesh>=4.4,<5`. **§5** meldet P6 als erledigt. Beides kann nicht
   gleichzeitig gelten; `pyproject.toml` sagt heute `trimesh>=5.0`.
2. **§0 „Warum trimesh gesperrt ist"** beschreibt die Sperre im Präsens
   („trimesh wurde unter 5 festgenagelt"). Sie besteht nicht mehr.
3. **§3 P6, „Rückfalloption"**: „Der Pin `<5` bleibt bestehen, bis alle vier
   Schritte grün sind. Wird P6 abgebrochen, kostet das nichts." Der Pin ist
   gelöst, P6 ist durch — der Absatz beschreibt einen Rückweg, den es nicht
   mehr gibt.
4. **§3 P0**: „**Erst wenn ein Volllauf grün ist, beginnt P1.**" §5 führt P1
   bis P4 und P6 als erledigt, während P0 auf „teilweise" steht. Die
   Vorbedingung wurde begründet übergangen (§5 „P0 im Klartext"), aber §3
   sagt weiter das Gegenteil.

Dazu die Tabelle **§0 „Was der Index neuer anbietet"**: sie ist eine
Momentaufnahme vom Vormittag des 14.08.2026 und war am Abend desselben Tages
abgearbeitet. Der Commit hält fest: „`--outdated` sagt jetzt: nichts ist
neuer." Sie liest sich heute als offene Arbeitsliste.

---

## Was am Dokument zeitlos ist

§1 (Ziel und Nicht-Ziele), §2 A–G und §4 (Leitplanken) sind ohne Befund. Die
Regel „ein Paket, ein Commit, ein grünes Tor" wurde in dieser Runde bewusst
gebrochen und im Dokument als Abweichung ausgewiesen — das ist sauber und
bleibt gültig für die nächste Runde. Der Schlusshinweis auf
`--upgrade-strategy eager` ist weiter richtig und im Commit-Text belegt.
