# Abgleich: konzept-organische-modellierung-2026-08.md

**Geprüft am:** 19.08.2026 gegen `main` (`b0415d6`), Arbeitsverzeichnis
`C:\Users\rober\Documents\Solidon`.
**Dokumentstand laut Datei:** 13.08.2026, mit Nachträgen vom 14.08.2026.
**Abstand:** fünf bis sechs Tage, in denen rund 45 Commits gefallen sind.

**Zählung der internen Behauptungen (15):**

| Urteil | Anzahl |
|---|---|
| stimmt | 3 |
| überholt | 10 |
| falsch | 1 |
| unprüfbar | 1 |

**Der Befund in einem Satz.** Die Substanz des Konzepts trägt — alle sechs
Operationen stehen, die Kategorie `organic` ist wie beschrieben nicht
entstanden, das Dateiformat ist 8, die Abnahme hängt weiterhin nur an der
Agenten-Regelsammlung. Was nicht mehr trägt, sind fast alle **Zahlen**: Tests,
Operationszahl, Sprachen, Millisekunden, Zeilennummern und vor allem der
Faktor-hundert-Beleg aus §7.2, der unter trimesh 5.0.0 auf 5,2 zusammengefallen
ist. Dazu vier Widersprüche, die im Dokument selbst stehen.

---

## 1 — P16.1 umgesetzt: Regel 2 neu, `test_gesture_ops.py` mit 26 Tests, B13 zurückgenommen

*Ort:* Kopfkasten, §15 P16.1, §17, §18, Übergabenotiz.

**Urteil: überholt** (Sache richtig, Zahl falsch).

**Beleg.**
- Regel 2 steht neu gefasst in `AGENTS.md:22–29` — Wortlaut identisch mit §5
  des Konzepts. ✓
- `.venv/Scripts/python.exe -m pytest tests/test_gesture_ops.py --collect-only -q`
  → **44 tests collected**, nicht 26. Die Datei hat sieben Testfunktionen
  (`tests/test_gesture_ops.py:64,71,90,100,112,124,137,144`), nicht fünf
  Eigenschaften: dazugekommen sind `test_a_gesture_operation_is_reversible`
  und `test_the_document_keeps_the_gathered_value`.
- `GESTURE_KINDS` (`tests/test_gesture_ops.py:42`) führt `sketch`, `strokes`,
  `armature` — die drei Arten sind alle abgedeckt. ✓
- B13 ist in `konzept-meshy-hyper3d-2026-08.md:936` und `:1007` mit Datum
  zurückgenommen („von ‚abgelehnt, weil Kundenkreis' zu ‚offen, weil noch nicht
  gebaut'"). ✓

**Was stattdessen dastehen müsste:** „P16.1 ist umgesetzt (Regel 2 neu,
`tests/test_gesture_ops.py`, heute 44 Tests über sieben Eigenschaften)."

---

## 2 — Zeilengenaue Verweise auf den Bestand

*Ort:* §2.1, §2.2, §2.3, §3, §7.1.

**Urteil: überholt** — fünf von acht Verweisen stimmen noch, drei zeigen ins
Leere.

| Verweis im Konzept | heute |
|---|---|
| `paint.py:87` (`_walk`) | ✓ `app/core/geom/paint.py:87` ist `def _walk` |
| `paint.py:134–151` (x/y/z in Weltkoordinaten) | ✓ `app/core/geom/paint.py:134–150` |
| `registry/params.py:229` (`kind="sketch"`) | ✓ steht auf `:230` |
| `hashing.py:65` (`operation_hash`) | ✓ `app/core/scene/hashing.py:65` |
| `hashing.py:9–11` (Platten-Cache über Prozesse stabil) | ≈ steht auf `:10–12` |
| `mesh_ops.py:76` (`decimate_mesh`) | ✗ `def decimate` steht auf `:78`, die Op `decimate_mesh` auf `:412` |
| `mesh_ops.py:93` (`smooth_mesh`) | ✗ `def smooth` steht auf `:107`, die Op `smooth_mesh` auf `:446` |
| `mesh_ops.py:102–137` (`remesh_mesh`) | ✗ `def remesh` steht auf `:214`, die Op `remesh_mesh` auf `:528`; `:102–137` ist heute `_subdivided_on_demand` |
| `sketch_editor.py:1434` (`spline`) | ✗ Zeile 1434 malt heute die Auswahl; `spline` liegt auf `:734`, `:1109`, `:1208`, `:1221` |

Ursache ist absehbar: `mesh_ops.py` ist in P16.3 um `uniform`, `subdivided`,
`_as_solid`/`_as_mesh` und die beiden neuen Ops gewachsen.

**Was stattdessen dastehen müsste:** Verweise ohne Zeilennummer — Datei plus
Funktionsname (`app/core/geom/mesh_ops.py`, `decimate`/`smooth`/`remesh`).
Zeilennummern in einem Konzept sind ein Verfallsdatum.

---

## 3 — Messwerte §2.5 (Kugel 65 538 Vertices, Faktor ~60)

*Ort:* §2.5, Entscheidung C.

**Urteil: unprüfbar** — kein Test hält diese Zahlen fest.

**Beleg.** `tests/test_performance.py:419`
(`test_gathering_strokes_beats_replaying_them_one_by_one`) prüft Entscheidung C,
misst aber ausdrücklich etwas anderes: „hier wird nur das Gewichtsfeld gemessen,
ohne Manifold, und da sind es rund neun. Die Schwelle steht deshalb beim
Fünffachen." Gemessen heute: `gathered 50 ms vs. one by one 415 ms` — Faktor 8,3.
Der Faktor 60 aus §2.5 gilt für den vollen Weg mit `warp_batch` und neu gebautem
Manifold und ist einmalig gemessen worden.

**Was stattdessen dastehen müsste:** Ein Satz, der die Zahlen als Momentaufnahme
vom 13.08.2026 kennzeichnet und auf den Test zeigt, der die Aussage dauerhaft
hält („Faktor mindestens fünf am Gewichtsfeld").

---

## 4 — Leistungstabelle §10 und „fünf Tests plus einer"

*Ort:* §10.

**Urteil: überholt.**

**Beleg.** `tests/test_performance.py` enthält heute **19** Leistungstests, davon
sieben aus P16 (`:351, :375, :384, :419, :452, :480, :503`) — die §10-Tabelle hat
fünf Zeilen und nennt „fünf Tests plus einer" (= sechs).
`test_the_real_stroke_evaluation_meets_the_same_budget` (`:384`) ist der siebte
und in P16.5 dazugekommen.

Beste Läufe auf dieser Maschine (`tests/.performance.json`) gegen die
§10-Tabelle:

| §10 sagt | bester Lauf hier | Lauf vom 19.08. |
|---|---|---|
| Strichliste (1 000) 96 ms | 106 ms (`sculpt_apply_1000`) | 172 ms |
| Subdivision 1 778 ms | 2 091 ms | 4 038 ms |
| Gleichmäßig vernetzen 1 480 ms | 1 666 ms | 3 181 ms |
| Weich verschmelzen 1 607 ms | 1 204 ms | 2 354 ms |

Die Zielwerte (2 s bzw. 3 s) halten im besten Lauf. Ein frischer Lauf heute
riss die 25-%-Regressionsschwelle bei fünf von sieben Tests und lag bei
Subdivision (4,0 s) und gleichmäßigem Vernetzen (3,2 s) **über dem
3-Sekunden-Budget** — das ist Maschinenlast, aber es heißt, dass die Zahlen aus
§10 auf dieser Maschine keine Reserve mehr haben.

**Was stattdessen dastehen müsste:** Die gemessene Spalte auf den heutigen Stand
ziehen (Subdivision 2 091 ms, Vernetzen 1 666 ms, Verschmelzen 1 204 ms,
Strichliste 106 ms) und „sieben Tests" statt „fünf plus einer".

---

## 5 — R1-Messung an `dense_1m.stl`, 0,7 ms je Strich

*Ort:* §10, §14 R1, Übergabenotiz P16.2.

**Urteil: überholt.**

**Beleg.**
- Die Datei liegt unter `tests/data/meshes/dense_1m.stl`, nicht unter
  `tests/data/` — das Konzept nennt den falschen Ort.
- `test_a_brush_stroke_stays_inside_a_frame` (`tests/test_performance.py:351`)
  existiert ✓ und ist grün, misst aber über `sculpting_ground()` →
  `medium_mesh()` (`:127`, Ikosphäre mit rund **200 000** Dreiecken), **nicht**
  an `dense_1m.stl` mit 1,31 Mio. Dreiecken. Die Zahlen „10 595 von 3 932 160
  Vertices", „786 ms KD-Baum" und „28,4 ms Vollkopie" hält heute kein Test mehr.
- `dense_1m.stl` wird in `test_performance.py` nur von der Funktion in `:51`
  benutzt (Einlesen und Eingangsstufe).

**Was stattdessen dastehen müsste:** „R1 wurde in P16.2 einmalig an
`tests/data/meshes/dense_1m.stl` entwarnt; der Test, der die Zusage hält, misst
seither am §31-Prüfnetz mit 200 000 Dreiecken."

---

## 6 — `generated_figure.stl` liefert direkt ein leeres Manifold

*Ort:* Entscheidung E.

**Urteil: überholt.**

**Beleg.** Seit P16.3 ist das Verhalten ein anderes: Beide Operationen weisen
das Netz mit einem `NotManifoldError` samt Handlungsvorschlägen ab, statt ein
leeres Ergebnis zurückzugeben —
`tests/test_subdivision.py:188` (`test_a_body_without_volume_is_turned_away_with_a_way_out`)
und `:315` (`test_subdividing_a_body_without_volume_is_turned_away_too`). Der
Test prüft ausdrücklich: „Ein leeres Ergebnis wäre die schlechteste Antwort."
Die Zahlen 3 368 Dreiecke nach `GENERATED_REPAIR` und 215 552 nach `refine(8)`
hält kein Test fest; `GENERATED_REPAIR` selbst steht in `app/core/generate.py:41`.

**Was stattdessen dastehen müsste:** „Der Geometriekern nimmt kein Netz ohne
Volumen an. Seit P16.3 wird das nicht mehr als leeres Ergebnis sichtbar, sondern
als `NotManifoldError` mit dem Weg heraus (Reparieren, dann verfeinern)."

---

## 7 — P16.3-Zahlen (§7.2)

*Ort:* §7.2, Übergabenotiz P16.3.

**Urteil: überholt** — drei von vier Zahlen stehen, die tragende ist eingebrochen.

**Beleg.**
- `plate_holes` 31 322 → 25 832 mm³ mit 2 772 Nullkanten: ✓ wörtlich in
  `tests/test_subdivision.py:296`.
- Ikosaeder 29 270 → 33 436 mm³ bei 33 510 möglichen: ✓
  `tests/test_subdivision.py:247`.
- Kantenstreuung 2,224 vor und nach `remesh_mesh`: ✓
  `tests/test_subdivision.py:92`; `remesh_uniform` bei 0,410 (`:97`).
- **3 260 416 Dreiecke gegen 30 648 — falsch geworden.**
  `tests/test_subdivision.py:129–140`
  (`test_uniform_remeshing_costs_a_fraction_of_the_triangles`) sagt seit dem
  14.08.2026: „Für dieselbe Zielkantenlänge von 1,5 mm braucht `remesh_mesh` auf
  `plate_holes` **160 084** Dreiecke, `remesh_uniform` **30 648** — Faktor 5,2
  (gemessen am 14.08.2026 unter trimesh 5.0.0). Hier stand Faktor **hundert** …
  Der Abstand ist eingebrochen, weil trimesh 5 sparsamer teilt." Bestätigt:
  `constraints.txt:89` → `trimesh==5.0.0`, installiert 5.0.0.

**Das ist der Fund mit der größten Folge.** Wer §7.2 heute liest, hält den
Faktor hundert für den Grund, warum `remesh_uniform` eine eigene Operation ist.
Der Grund trägt weiter (andere Zusage, gleichmäßigere Kanten), aber die Zahl
dahinter ist ein Zwanzigstel dessen, was dort steht.

**Was stattdessen dastehen müsste:** „…bezahlt wird das mit 160 084 Dreiecken
für 1,5 mm; `remesh_uniform` kommt auf 30 648 bei einer Streuung von 0,41
(Faktor 5,2 unter trimesh 5.0.0 — unter trimesh 4 waren es 3 260 416 und Faktor
hundert)."

*Nebenbei:* `CLAUDE.md` führt weiterhin „`trimesh<5` ist eine aufgeschobene
Migration"; `pyproject.toml:26` verlangt inzwischen `trimesh>=5.0`. Nicht Teil
dieses Konzepts, aber derselbe Grund.

---

## 8 — Sechs neue Ops, Kategorie `organic` entsteht NICHT

*Ort:* Entscheidung M, §7.2, Schluss der Übergabenotiz.

**Urteil: stimmt** — mit einem Zahlenwiderspruch im Dokument.

**Beleg.**
```
.venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations; \
from app.core.registry import REGISTRY; load_operations(); \
import collections; print(collections.Counter(o.category for o in REGISTRY.all()))"
→ Counter({'parts': 19, 'transform': 9, 'mesh': 9, 'prepare': 7, 'primitive': 7,
   'scene': 5, 'shaping': 5, 'sketch': 5, 'boolean': 4, 'surface': 3,
   'colour': 3, 'holes': 3, 'import': 3, 'label': 2, 'repair': 1})
```
Keine Kategorie `organic`. Die sechs Ops liegen bei:
`blend_union` → `boolean`, `displace_image` → `surface`, `pose_armature`,
`remesh_uniform`, `sculpt_strokes`, `subdivide_surface` → `mesh`. ✓
Bestätigt in `ROADMAP.md:5259–5280`.

**Widerspruch im Dokument.** Entscheidung M und die §15-Tabelle sprechen von
**sechs** neuen Ops; der Schlussabsatz der Übergabenotiz von „den **acht**
Operationen". Der `git diff` über die P16-Commits zeigt genau sechs neue
Operationsdateien/-einträge (`sculpt.py`, `pose.py`, `displace.py`, `blend.py`
plus zwei in `mesh_ops.py`). Die „acht" ist aus `ROADMAP.md:5260` übernommen und
dort ebenfalls falsch.

**Was stattdessen dastehen müsste:** „Die sechs Operationen bleiben bei ihren
Geschwistern (`mesh`, `boolean`, `surface`)."

---

## 9 — Operationszahl auf beiden Websprachen von 77 auf 79 nachgezogen

*Ort:* Übergabenotiz P16.3.

**Urteil: überholt.**

**Beleg.** Das Register führt heute **85** Operationen. Die Website nennt
dieselbe Zahl: `website/funktionen.html:408`, `website/index.html:500`,
`website/en/features.html:402`, `website/en/index.html:498` — jeweils „85".
Und es sind längst nicht mehr „beide Websprachen": `website/` hat neben `en`
auch `es`, `fr`, `it`, `pt` (Commit `db9cf98`, „Die sechssprachige Website ist
seit dem 18.08. auch draußen").

**Was stattdessen dastehen müsste:** Die Zahl aus dem Konzept streichen — sie
gehört ins Register und in die Website, nicht in ein Konzept. Ersatzweise: „Die
Operationszahl wird auf allen sechs Websprachen mitgeführt; ein Test hält sie
zusammen."

---

## 10 — Alle Pakete P16.1–P16.11 fertig, offen einzig die Agenten-Regelsammlung

*Ort:* §15 Tabelle, Übergabenotiz „Was noch offen ist".

**Urteil: stimmt.**

**Beleg.**
- `ROADMAP.md:41`: „| P16.10 — die Regel in der Sammlung | P16 — Organische
  Modellierung | eine Entscheidung; sie kostet zwei Agenten-Suite-Läufe und Geld |"
  — der einzige offene P16-Punkt in der Übersicht.
- `ROADMAP.md:5213`: `- [~] **P16.10 …** Die Sperre steht; offen ist nur noch, ob
  eine Regel dazukommt.` Alle übrigen P16-Zeilen tragen `[x]`.
- `app/core/knowledge/data/rules.toml`: keine Sculpting-Regel
  (`grep -i "sculpt|pinsel|formen"` findet nur einen OpenSCAD-Satz auf `:287`);
  `version = "2"` unverändert.
- Die zweifache Sperre steht: `app/core/registry/params.py:241` und
  `app/core/agent/session.py:478` lesen beide `GATHERED_KINDS`.
- Alle P16-Testdateien grün:
  `pytest tests/test_gesture_ops.py tests/test_subdivision.py tests/test_blend.py
  tests/test_sculpt.py tests/test_displace.py tests/test_pose.py
  tests/test_gathered.py tests/test_base_mesh.py -q` → **176 passed**.

**Was stattdessen dastehen müsste:** unverändert. Diese Zeile hat gehalten.

---

## 11 — Abnahme §16: sieben von acht, Weg 4 in 0,24 Sekunden

*Ort:* §16, Übergabenotiz.

**Urteil: überholt.**

**Beleg.**
- `pytest tests/test_way_four.py -q -s` → `Weg 4 vollständig: 0.88 s`,
  **7 passed**. Die 0,24 s aus dem Dokument sind heute 0,88 s (dieselbe
  Maschine, andere Last — aber die Zahl im Dokument ist nicht mehr die, die
  jemand nachmisst).
- Punkt 6 hält: `MAX_MENUS = 9`, `MAX_TOOLS = 8`, `MAX_FRONT_PARAMS = 8`,
  `MAX_SUBMENU_ENTRIES = 12` (`tests/test_interface_limits.py:39–51`);
  `git log -S "MAX_TOOLS = "` zeigt genau einen Commit (`3ad3c01`) — keine
  Grenze wurde angehoben. ✓
- Punkt 8 („Handbuchseiten in **beiden** Sprachen") ist überholt: das Handbuch
  steht in sechs Sprachen (`website/handbuch.html`, `website/en/manual.html`,
  `website/es|fr|it|pt/manual.html`), das Kapitel *Formen* in
  `app/core/manual.py:448–479`.
- Punkt 7 (Agenten-Suite) offen ✓ — siehe Befund 10.

**Was stattdessen dastehen müsste:** „…und seit `tests/test_way_four.py` auch
die Punkte 3 und 4: Eine Figur läuft vom Grundkörper bis zum druckfertigen 3MF
in unter einer Sekunde." Punkt 8: „Handbuchseiten in allen sechs Sprachen".

---

## 12 — Testzahlen je Datei

*Ort:* §15 Tabelle, Übergabenotiz.

**Urteil: überholt** — sechs von zehn Zahlen sind gewachsen.

| Datei | Konzept | heute (`pytest --collect-only -q`) |
|---|---|---|
| `test_gesture_ops.py` | 26 | **44** |
| `test_subdivision.py` | 15 | 15 ✓ |
| `test_blend.py` | 10 | **11** |
| `test_sculpt.py` | 26 (+5) = 31 | 31 ✓ |
| `test_sculpt_session.py` | 19 | **28** |
| `test_displace.py` | 17 | **22** |
| `test_pose.py` | 16 | **36** |
| `test_pose_session.py` | 14 | **15** |
| `test_gathered.py` | 13 | 13 ✓ |
| `test_base_mesh.py` | 4 | 4 ✓ |

Ursachen sind an den Commits ablesbar: `9b41d10` („Eine getippte Stellung tötete
den Auswertungs-Thread"), `5b4b012` („Ein stilles Ausweichen auf ‚von oben'"),
`34685f0` (Einbacken), `4f35316` (Gewichte), `50fdc66` („Weg 4 hat jetzt eine
Tür"), `b0415d6` — alle nach dem 14.08.2026.

**Was stattdessen dastehen müsste:** Testzahlen ganz weglassen. Sie sind der
Teil des Dokuments mit der kürzesten Haltbarkeit und stehen ohnehin im Lauf.

---

## 13 — Voller Tor-Lauf: 3553 Tests, 16 Leistungstests, VTK-Absturz bei vielen Fenstern

*Ort:* Übergabenotiz.

**Urteil: falsch** — die Zahlen sind überholt, die Diagnose war schon damals
nicht richtig.

**Beleg.**
- `pytest --collect-only -q` → **4246 tests collected**, in **131** Testdateien.
  Leistungstests: **19** statt 16 (`grep -c "^def test_" tests/test_performance.py`).
- **Die Ursachenzuschreibung war falsch.** `ROADMAP.md:5732`
  („Ein Umgebungsartefakt, das keines war", 14.08.2026): Die beiden Abstürze A
  und B waren *ein* Fehler und lagen nicht an VTK, sondern an
  `os.environ.pop("QT_QPA_PLATFORM", None)` **beim Import** von
  `tools/make_manual.py`. Ab `tests/test_translations.py` galt für den ganzen
  Prozess keine Offscreen-Plattform mehr, und die nächste Datei, die ein Fenster
  baute, starb. Gemessen dort: `test_translations.py + test_ui.py` vorher
  „Zugriffsverletzung bei 22 %", nachher „300 passed".
- Behoben: `tools/make_manual.py:934` und `tools/make_figures.py:419` setzen die
  Variable jetzt in `main()` zurück, nicht beim Import.
- Was bleibt, ist ein **anderer** Absturz: `test_operation_ui.py`, etwa einmal in
  acht Läufen, `panels.py:890`, glibc `free(): invalid pointer` — offen
  (`ROADMAP.md:43`).

**Damit fällt auch die Begründung für das Aufteilen in elf Fensterdateien.**
Wer das Konzept heute liest, teilt einen Lauf auf, für den es den Grund nicht
mehr gibt.

**Was stattdessen dastehen müsste:** „Voller Tor-Lauf grün. Der Absturz, der das
Aufteilen nötig machte, war kein VTK-Problem, sondern ein
`QT_QPA_PLATFORM`-Pop beim Import in den Werkzeugen — behoben am 14.08.2026
(`ROADMAP.md`, ‚Ein Umgebungsartefakt, das keines war'). Offen bleibt ein
seltener, davon unabhängiger Absturz in `test_operation_ui.py`."

---

## 14 — Dateiformat 8, Auslagerung ab 2 000, Einbacken mit Nachfrage

*Ort:* §9, Entscheidung D, §15 P16.9, Übergabenotiz P16.9.

**Urteil: überholt** — die Sache steht, aber das Dokument widerspricht sich und
nennt die Grenze falsch.

**Beleg.**
- `app/core/scene/migrations.py:27` → `FORMAT_VERSION: Final = 8` ✓;
  `:145` → `Step(from_version=7, to_version=8, apply=carry_over)` ✓; ältere
  Migrationen alle erhalten (v1→v8) ✓.
- `tests/data/projects/example_v8.p3d` liegt ein ✓ (neben v1–v7).
- `app/core/scene/gathered.py` existiert ✓, `tests/test_gathered.py` 13 Tests ✓.
- **Die Grenze ist keine Strichzahl.** `app/core/scene/gathered.py:37` →
  `GATHERED_LIMIT: Final = 200_000` — *Zeichen*, nicht Züge. Der Modulkopf sagt
  dazu: „Zweihunderttausend sind etwa zweitausend Pinselzüge". Die Aussage des
  Konzepts („Bis 2 000 Striche im `project.json`") ist eine Näherung der
  Wirkung, nicht die Regel; für eine Skizze oder ein Skelett stimmt sie gar nicht.
- Ausgelagert wird jeder Sammelwert, nicht nur Striche ✓ — das steht im Nachtrag
  richtig.
- Einbacken: `app/core/geom/sculpt.py:316` `BAKE_STAGES = 20`, `:321`
  `BAKE_STROKES = 20_000`, `:488` die Auslösung ✓. Kette in der Oberfläche
  vollständig: `app/ui/panels.py:916` `bakeRequested = Signal(int)` →
  `app/ui/main_window.py:829` → `:2543 bake_sculpt` → `app/ui/session.py:636
  bake_strokes` ✓.

**Widerspruch im Dokument.** Die §15-Tabelle sagt zu P16.9: „**fertig** — 18
Tests; **Nachfrage in der Oberfläche offen**". Die Übergabenotiz sagt zwei
Absätze weiter: „**Die Nachfrage in der Oberfläche steht** (14.08.2026)". Der
Code gibt der Übergabenotiz recht. Das ist genau das Muster, das dieses Projekt
schon mehrfach hatte: der Nachtrag ist richtig, die Tabelle darüber ist stehen
geblieben.

**Was stattdessen dastehen müsste:** §15 P16.9 → „**fertig** — 18 Tests,
Nachfrage in der Oberfläche steht". §9 → „Ab 200 000 Zeichen — rund zweitausend
Pinselzügen — wandert ein Sammelwert in eine eigene Quelle im Container
(`GATHERED_LIMIT`)."

---

## 15 — P16.11: vier von fünf Bedingungen; offen an den Bauplan zurückgegeben

*Ort:* Entscheidung H2, §6, §15, Schluss der Übergabenotiz.

**Urteil: stimmt** — beides gilt heute unverändert, und das zweite ist die
größte stille Baustelle des Konzepts.

**Beleg — vier von fünf.** `tests/test_base_mesh.py` hat vier Testfunktionen
(`:87`, `:107`, `:120`, `:137`) für die Bedingungen 1 bis 4. Bedingung 5 steht im
Modulkopf weiterhin als „*(erst mit P16.5 prüfbar)*" (`:22`) — **obwohl P16.5
seit dem 13.08.2026 fertig ist**. Die Begründung im Konzept („Nur die fünfte
braucht P16.5 und steht offen") ist damit hinfällig: Der Pinsel steht, die
Bedingung ist prüfbar, sie wurde nur nie geprüft. Der Prüfpunkt, der die
Käfig-Entscheidung tragen soll, ist zu vier Fünfteln beantwortet und wird als
beantwortet behandelt.

**Beleg — der Bauplan.** §6 des Konzepts listet neun Änderungen am Bauplan.
Stichprobe am heutigen `3d-agent-bauplan.md`:

| §6 sieht vor | im Bauplan heute |
|---|---|
| §2.5 Satz zum Werkzeugmodus | **fehlt** — §2.5 endet unverändert mit „Keine Betriebsarten…" |
| §9 `Stroke`, `StrokeList`, `Armature`, `Bone`, `Pose` | **fehlt** — `grep "Stroke\|Armature\|Bone"` findet nichts |
| §12 `format_version` 7 → 8 | **fehlt** — das Beispiel auf `:608` steht auf `"format_version": 5` |
| §25 sechs Ops | **fehlt** — keine der sechs kommt im Bauplan vor |
| §31 drei Leistungszeilen | **fehlt** — die Tabelle `:1430–1441` ist unverändert |
| §42 zwei Zeilen zu den Grenzen | **fehlt** |
| neu §44 | **existiert nicht** — der Bauplan endet bei §43 |
| Nicht-bauen-Liste ergänzt | **fehlt** in `AGENTS.md` |

Einzig §2.2 wurde nachgezogen, und zwar erst am 19.08.2026 (Commit `216b397`,
„Der vierte Weg war gebaut, nur die Unterlagen wussten es nicht") — eine
Änderung, die §6 gar nicht vorsah.

**Und: dieser Rückstand steht in keiner Arbeitsliste.** `ROADMAP.md:26–46` führt
als offenen P16-Punkt ausschließlich die Regelsammlung. Der Bauplan-Nachtrag
kommt dort nicht vor. Die Übergabenotiz des Konzepts nennt ihn noch aus
P16.3-Sicht („§25 kennt die **zwei** neuen Operationen noch nicht") — inzwischen
sind es sechs.

**Was stattdessen dastehen müsste:** In §15 oder in der Übergabenotiz eine
eigene offene Zeile: „**Bauplan nachziehen** — §2.5, §9, §12, §25, §31, §42 und
ein neues §44 kennen P16 nicht. Sechs ausgelieferte Operationen, drei
Sammelparameter-Verträge und Formatversion 8 stehen nicht in der Spezifikation."
Und in H2: „Bedingung 5 ist seit P16.5 prüfbar und noch nicht geprüft."

---

## Zusammenstellung der Widersprüche im Dokument

1. **§7.4 gegen den Schlussabsatz der Übergabenotiz.** §7.4: „Umgesetzt in
   P16.7 mit **drei** Projektionen — von oben, um die Achse, über die Kugel.
   ‚Per Fläche' … gehört damit zu §21." Schlussabsatz: „die vierte
   Displacement-Projektion (`PROJECTIONS` führt `planar`, `cylindrical`,
   `spherical`, `face`) … seit dem 14.08.2026 erledigt."
   *Der Code gibt dem Schlussabsatz recht:* `app/core/geom/displace.py:51` →
   `PROJECTIONS = ("planar", "cylindrical", "spherical", "face")`. §7.4 muss auf
   vier Projektionen umgeschrieben werden.

2. **§15 P16.9 gegen die Übergabenotiz** (siehe Befund 14): „Nachfrage in der
   Oberfläche offen" gegen „Die Nachfrage in der Oberfläche steht". Der Code gibt
   der Übergabenotiz recht.

3. **Entscheidung M / §15 gegen den Schlussabsatz:** „sechs neue Ops" gegen „die
   acht Operationen". Das Register kennt sechs.

4. **§8 gegen den heutigen Stand der Leiste.** §8 zählt acht Bedienelemente auf
   (Werkzeug, Radius, Stärke, Symmetrie, *Neu ansetzen*, Auflösungshinweis,
   Wandstärkenwarnung, *[Fertig]*) und begründet, warum es keinen neunten geben
   darf („ein Knopf für das, was Strg+Z kann, wäre der neunte").
   `app/ui/sculpt_bar.py:134–146` legt heute **neun** Bedienelemente in die
   Leiste: dazwischen sitzt `self.refine = QPushButton(tr("Jetzt vernetzen"))`
   (`:120`), am 14.08.2026 dazugekommen (`ROADMAP.md:5266`, „behoben mit einem
   Knopf, der die Kantenlänge aus dem Pinselradius rechnet"). Die Grenze war nie
   getestet — `tests/test_interface_limits.py` prüft die Sculpting-Leiste nicht,
   `MAX_TOOLS = 8` gilt der Werkzeugzeile des Hauptfensters.
   *Zu ändern:* §8 auf neun Elemente, oder die Begründung fallen lassen. So wie
   es dasteht, verbietet §8 einen Knopf, den es gibt.

---

## Was am Dokument nicht altert

Regel 2 (§5), die Entscheidungen A–N, die Nicht-Ziele (§13), die Risiken (§14)
und die Positionierung (§17) sind fünf Tage später unverändert richtig und
werden vom Code gestützt: sechs Pinselwerkzeuge
(`app/core/types.py:1143`, `SculptTool`), `ORDERED_TOOLS` für die
reihenfolgeabhängigen drei (`:1154`), `cut` am Strich für die erzwungene Etappe
(`:1180 ff.`), Weltkoordinaten statt Vertexindex (Docstring von `Stroke`),
Sperre gegen geratene Striche an zwei Stellen. Wer das Dokument wegen dieser
Teile liest, liest es richtig.

Wer es wegen einer **Zahl** liest — Tests, Millisekunden, Dreiecke,
Operationszahl, Sprachen, Zeilennummern —, liest in zehn von elf Fällen etwas,
das nicht mehr gilt.
