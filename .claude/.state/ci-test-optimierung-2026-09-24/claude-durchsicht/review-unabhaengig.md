# Review: Strahlvorauswahl, CI-Verteilung, isolierter Läufer, Workflow

Stand: abgeschlossen, 24.09.2026. Nur lesend, keine Datei im Arbeitsbaum
geändert; Sonden, Protokolle und mypy-Cache liegen im Scratchpad. Gefahren:
nur Kerntests ohne Fenster (Exit 0 in allen Läufen: Strahltests, CI-Tests,
statische Tests, `test_ci_runner.py` unter xdist, drei Teilläufe), `ruff check`
und `ruff format --check` mit `--no-cache` (Exit 0), mypy auf `mesh.py`
(Exit 0). Am Rand: Im Repository liegt ein leeres `reports/` (`core/`,
`latest/`) von 22:22 Uhr, also vor dem ersten Lauf dieser Durchsicht — der
Rest des Tests, den der Diff in `test_packaging.py` mit `cwd=tmp_path`
behebt; meine Läufe haben ihn nicht erneuert. Nicht angefasst.

## Übersicht nach Schwere

| Nr. | Schwere | Ort | Kurz |
|---|---|---|---|
| 3.1 | Fehler | `tools/run_suite_isolated.py:250–280` | Nachfrist greift nicht: `Popen.__exit__` wartet am Leser, bis der Nachfahre endet (gemessen 40,1 s statt ~15 s) |
| 1.1 | Risiko | `app/core/geom/mesh.py:1208–1211, 1275, 1385–1435` | Vorauswahl an Vollkörpern 1,5- bis 2-mal langsamer als der Vollvergleich, mehr Paare |
| 1.2 | Risiko (latent) | `app/core/geom/mesh.py:1232, 1399–1421` | Negatives `minimum_travel` verliert Treffer hinter dem Ursprung (belegt) |
| 3.2 | Risiko | `tools/run_suite_isolated.py:206–222` | Konsolen- oder Protokollfehler beendet das Leeren der Leitung, Datei fällt erst nach 900 s |
| 1.3 | Hinweis | `mesh.py:1257–1261`, `range_check.py:182`, `geom/CLAUDE.md` | Öffentliche Zusage „bitgleich" ohne die eingeräumte Ausnahme |
| 1.4 | Hinweis | `tests/test_geometry_review.py` | Rückfall nach Rundengrenze und Abbruch der Vorauswahl ungeprüft |
| 1.5 | Hinweis | `mesh.py:1437–1448` | Strahlen ohne Richtung kosten je einen Vollvergleich, der nie trifft |
| 2.1 | Hinweis | `tests/data/ci_core_durations.json` | Von Hand nachgetragen, gegen die eigene Regel |
| 2.2 | Hinweis | `tests/data/ci_window_durations.json` | Nicht aus dem Werkzeug; `test_ui.py` nach der Teilung veraltet gewichtet |
| 3.3 | Hinweis | `tools/run_suite_isolated.py:218–220` | Kindausgabe kann Workflow-Befehle auslösen |
| 3.4 | Hinweis | `tools/run_suite_isolated.py:289–292` | Abbaufehler erscheint als „mehr Fälle als gesammelt" |
| 4.1 | Hinweis | `build.yml:161–183` | mypy-Fehler verschweigt Teil 0 der Kerntests |
| 4.2 | Vermutung | `build.yml` Test-Uploads | Wiederholungsstart eines roten Jobs könnte am Artefaktnamen scheitern |
| 4.3 | Hinweis | `tools/windows_signed_installer.py:191–193` | Berichtsartefakte zählen gegen `per_page=100` |
| 5.1 | Hinweis | `tests/workflow_helpers.py:23–25` | Schrittende nur an `name`/`uses` |
| 6.1 | Hinweis | `test_translations.py:186`, `test_parts.py:1616–1623` | Zusammengelegte Tests melden nur den ersten Befund |
| 7.1 | Hinweis | Konzept Zeile 61 | mypy „in jedem Kernjob" gegen „einmal je Plattform" |
| 7.2 | Hinweis | Karten, `ci_shards.py:3–4` | Herkunft der Tabellen, Aufrufbeispiel mit falschem Pfad |

Die Behauptung „bitgleich zum Vollvergleich außer bei numerisch entarteten,
fast streifenden Treffern" hält der Prüfung stand (Abschnitt 1, „Was trägt");
die CI-Teilung ist vollständig und disjunkt (auch unter xdist gegengeprüft:
drei Teile 52 + 392 + 21 = 465 = ungeteilte Sammlung); `package` kann ohne
grüne Pflichtjobs nicht starten.

## 1. Kern: räumliche Vorauswahl in `ray_hits_batch` (`app/core/geom/mesh.py`)

Geprüft: Beweis im Docstring von `_culled_ray_hits` (1331–1362), Randzugabe,
`guard`, Übernahmegrenze, Reichweitenwachstum, `complete`, Abbruch, Strahlen
ohne Richtung, Rundengrenze, Gruppierung, Plattformgleichheit. Tests
`test_the_spatial_preselection_of_ray_hits_batch_changes_no_bit`,
`test_each_safeguard_of_the_ray_preselection_decides_a_constructed_case`,
`test_ray_hits_batch_answers_like_one_ray_hits_call_per_ray`: Exit 0, 3 passed
(2,4 s). Sonden liegen im Scratchpad (`probe_rays.py`, `probe_cost.py`), sie
ändern nichts im Baum.

**Was trägt (kein Befund):**
- Randzugabe: Ein Treffer mit baryzentrisch `u, v, w >= -em` liegt je Achse
  höchstens `2·em·ext_k` außerhalb des Dreiecksquaders (Gewichte `1+2em` und
  zweimal `-em`). `3·em·max(ext)` deckt das mit Reserve; `max(edge_margin, 0)`
  ist bei negativem Rand richtig.
- `complete = diagonal + 4·slack_max + 2·guard` >= `diagonal + 2·√3·slack_max`:
  Kein echter Treffer kann weiter liegen.
- Reichweitenwachstum: Ein nicht übernommener Treffer bei `d_f` setzt
  `R_neu = d_f/0,75·(1+1e-9) > d_f`; das nächste Stück enthält den
  Trefferpunkt, das Dreieck ist wieder in `near`, und `d_f <= 0,75·R_neu` wird
  übernommen. Ohne Treffer verdoppelt sich `R`; ab `diag/32` ist `complete`
  nach spätestens sechs Verdopplungen erreicht. `RAY_CULL_ROUNDS = 24` ist
  reichlich.
- Gleichstände: `near` kommt aus `flatnonzero` (aufsteigend), `argmin` nimmt
  die erste Nummer, der Blockvergleich ersetzt nur echt kleinere Werte. Die
  Sonde zählt an den 40 Eckstrahlen des Tests 33 exakte Gleichstände — der
  Tie-Break wird tatsächlich geprüft.
- Zellen: `frexp` liefert `2^(l-1) <= R < 2^l`, Zelle `2^(l-2)` liegt in
  `(R/4, R/2]` wie beschrieben; `R >= diag/32` begrenzt die Zellnummern auf
  <= 128, kein Überlauf beim `astype(int64)`.
- Plattformgleichheit (RM-187): nur Grundrechenarten, `sqrt`, `floor`,
  `frexp`/`ldexp`, Min/Max, `lexsort` über Ganzzahlen — kein BLAS, kein
  LAPACK, keine transzendente Funktion. Selbst eine abweichende Auswahl
  änderte nach dem Beweis nur den Aufwand.
- Die drei konstruierten Fälle des zweiten Tests stimmen mit der Geometrie
  überein (von Hand nachgerechnet: Strahl 0 allein in seiner Zelle, `A` bei
  1,5R außerhalb des ersten Quaders, `B` bei 2R; `A3` bei 0,6R nur bei voller
  Stücklänge in `near`; `C` um 0,5 µm neben der Kante, Treffer über
  `edge_margin = 1e-6`, ohne Randzugabe außerhalb des Quaders).
- Rückfall nach der Rundengrenze: Sonde mit `RAY_CULL_ROUNDS = 0, 1, 2` —
  jeweils bitgleich zum Vollvergleich. Szene um 1e3, 1e5, 1e7 mm verschoben —
  bitgleich.

### Befund 1.1 — Risiko (Leistung): An kompakten Körpern rechnet die Vorauswahl mehr Paare als der Vollvergleich und ist langsamer

`app/core/geom/mesh.py:1275` entscheidet allein nach der Paarzahl
(`total * count <= RAY_CULL_PAIRS`), und der Kommentar an `RAY_CULL_PAIRS`
(1208–1210) sagt: „Darunter … kostete [die Vorauswahl] mehr, als sie spart" —
also darüber spare sie. Das gilt nur, wo die Wand dünn gegen den Körper ist.
Läuft der Strahl durch den ganzen Körper (Vollkörper, Knauf, Kugel, Zylinder),
wächst `R` über fünf, sechs Runden bis zur Diagonale, jede Runde rechnet
dieselben Strahlen erneut gegen ein immer größeres `near`, und dazu kommt je
Gruppe ein Quadertest über **alle** Dreiecke.

Gemessen (`probe_cost.py`, Strahl je Dreiecksmitte nach innen, wie
`local_wall_thickness`):

| Körper | Paare voll | Paare Auswahl | Zeit Auswahl | Zeit voll |
|---|---|---|---|---|
| Kugel r 10, 5120 Dreiecke | 26 Mio | 31 Mio | 4,2 s | 2,4 s |
| Zylinder, 1024 Dreiecke | 1 Mio | 1 Mio | 0,2 s | 0,1 s |
| Kugel r 10, 20480 Dreiecke | 419 Mio | 498 Mio | 63,0 s | 69,4 s |
| Dichtschnur R 20 r 1, 32768 Dreiecke | 1074 Mio | 19 Mio | 6,4 s | 189,2 s |

Ergebnis überall bitgleich. Bei der Schnur trägt die Vorauswahl (30-fach),
an der kleinen Kugel und am Zylinder kostet sie das 1,75- bis 2-fache.
Nachmessung an der 5120er-Kugel, zweimal hintereinander unter derselben Last
(`probe_cost2.py`): Auswahl 6,38 / 6,90 s, Vollvergleich 4,17 / 4,28 s.
Aufschlüsselung (`probe_groups.py`): 5,6 von 6,9 s stecken in
`_nearest_ray_hits`, verteilt auf 4244 Gruppen in Runde 1 (5120 Strahlen —
fast eine Gruppe je Strahl), 1448 in Runde 2, 368, 98, 26, 7; die späten
Runden rechnen gegen fast alle Dreiecke, die frühen zahlen den Festaufwand
tausender kleiner Aufrufe. Der Weg ist kundensichtbar: `ui/recipe_dialog.py:148`
fährt den Bereichstest eines eigenen Rezepts (Ausschnitt aus einem
eingelesenen Modell) je Ecke, bis zu `MAX_CORNERS = 512` (im Arbeiter, also
kein Hauptthread-Befund, aber Wartezeit).

Fix, beides exakt, weil nur entschieden wird, welche Paare laufen:
(a) späte Runden übergeben — wenn `2 * len(near) >= len(triangles)`, diese
Strahlen mit `_nearest_ray_hits(triangles, …)` rechnen, eintragen und als
erledigt markieren; (b) frühe Runden bündeln — eine Mindestgröße je Gruppe
(Nachbarzellen zusammenlegen, bis etwa 64 Strahlen beisammen sind) oder eine
gröbere erste Zelle. Mindestens aber den Kommentar an `RAY_CULL_PAIRS` und
den Satz in `geom/CLAUDE.md` („Ohne sie war die Wandstärke quadratisch") auf
„an dünnwandigen Körpern" einschränken. Als Test die Paarzählung des ersten
Tests an einer Vollkugel: Auswahl höchstens so viele Paare wie der
Vollvergleich.

### Befund 1.2 — Risiko (latent): Mit negativem `minimum_travel` verliert die Vorauswahl Treffer hinter dem Ursprung

`ray_hits_batch` nimmt `minimum_travel: float` ohne Untergrenze an
(mesh.py:1232); `_ray_triangle_parameters` zählt dann auch `t` in
`(minimum_travel, 0]`. Die Vorauswahl baut ihre Quader aber nur über
`[o, o + R·d/|d|]` (1399–1401), und `taken = distance <= 0,75·R` (1421)
übernimmt jeden negativen Abstand sofort. Sonde (`probe_rays.py`, Sonde 1):
Dreieck bei x = −3 hinter dem Ursprung, eines bei x = +20 davor, 1,6 Mio
Paare, `minimum_travel = -5`: Vollvergleich `(-3.0, Dreieck 0)`, Vorauswahl
`(20.0, Dreieck 1)`. Heute ruft nur `local_wall_thickness` mit `1e-4`; die
Zusage „bitgleich" hängt also an einer unausgesprochenen Vorbedingung.

Fix: in `ray_hits_batch`
`if total * count <= RAY_CULL_PAIRS or minimum_travel < 0.0:` auf den
Vollvergleich, dazu ein Satz im Docstring; Test mit dem Sondenaufbau.

### Befund 1.3 — Hinweis (Doku): Die öffentlichen Zusagen nennen die Ausnahme nicht

`_culled_ray_hits` (1338–1344) räumt ein, dass fast streifende, numerisch
entartete Treffer abweichen können („Dort war auch der Vollvergleich keine
geometrische Aussage mehr"). Der Docstring von `ray_hits_batch` (1257–1261:
„was die Vorauswahl nicht belegen kann, geht in den Vollvergleich"), der von
`local_wall_thickness` (`range_check.py:182`: „die Auswahl ändert keinen
Treffer, nur den Aufwand") und die Karte `geom/CLAUDE.md` sagen es
unbedingt. Der entartete Fall wird weder belegt noch übergeben. Fix: je ein
Halbsatz „außer bei numerisch entarteten, fast streifenden Treffern
(Herleitung an `_culled_ray_hits`)".

### Befund 1.4 — Hinweis (Test): Rückfallweg und Abbruch der Vorauswahl sind ungeprüft

- Nach `RAY_CULL_ROUNDS` Runden offene Strahlen gehen über
  `np.union1d(pending, …)` (1437) in den Vollvergleich. In beiden Tests
  ist jeder Strahl lange vorher erledigt; nur der Strahl ohne Richtung nimmt
  den Weg. Eine Mutation `open_rays = np.flatnonzero(length <= 0.0)` bliebe
  grün. Fix: im ersten Test zusätzlich mit
  `monkeypatch.setattr(mesh_module, "RAY_CULL_ROUNDS", 1)` bitgleich
  vergleichen (Sonde: grün).
- Die zwei Abbruchstellen in der Gruppenschleife (1396, 1418) prüft kein Test;
  `test_parts.py` ersetzt `local_wall_thickness` beim Abbruch ganz (1490).
  Fix: ein Token, das nach dem ersten `_ray_triangle_parameters` kippt, und
  die Zusage „Teilstand, Token gesetzt" prüfen.

### Befund 1.5 — Hinweis (Leistung): Strahlen ohne Richtung kosten je Strahl einen Vollvergleich, der nie trifft

`local_wall_thickness` übergibt `-face_normals`; trimesh setzt die Normale
eines Dreiecks ohne Fläche auf `[0, 0, 0]`. Diese Strahlen gehen in den
Vollvergleich (1437–1448), jeder gegen alle Dreiecke. Mit `d = 0` ist
`across = 0`, `det = ±0 < RAY_PARALLEL_EPS`, also nie ein Treffer (bei
unterlaufender Länge ebenso, `det ~ |d|·L²`). Sonde: 10 % Nullrichtungen an
20480 Dreiecken kosten +7 s. Kein Rückschritt gegenüber HEAD, aber ein
verbliebener quadratischer Term bei Netzen mit vielen Nadeldreiecken. Fix:
`best_travel/best_face` für `length <= 0` direkt auf `inf/-1` lassen und den
Grund im Kommentar nennen — bitgleich zum Vollvergleich.

## 2. CI-Verteilung: `tools/ci_shards.py`, `tests/conftest.py`, Laufzeittabellen

**Was trägt (kein Befund):**
- `balanced` ist LPT mit festem Tie-Break (Gewicht absteigend, dann Pfad,
  Gruppe über `(Summe, Index)`); bei positiven Gewichten bekommt jede Gruppe
  mindestens eine Datei, sobald es mindestens `N` Dateien gibt.
  `read_durations` lässt nur positive endliche Zahlen durch.
- `CoreShard` hängt `trylast` an `pytest_collection_modifyitems`: nach dem
  Fenstermarker des conftest (`tryfirst`) und nach der `-m`-Abwahl des
  mark-Plugins. Verteilt wird also die Menge dieses Laufs, je Datei. Unter
  xdist rechnet jeder Worker denselben Plan; xdist verlangt ohnehin gleiche
  Sammlungen.
- `pytest_addoption` im `tests/conftest.py` greift, weil `testpaths = ["tests"]`
  die Datei zur Anfangs-conftest macht; bei `pytest tests/…` ebenso.
- `test_the_core_shards_collect_every_case_exactly_once_and_whole_files` geht
  den echten Weg (frischer Prozess, echte conftest) und prüft Vollständigkeit,
  Disjunktheit und ganze Dateien.
- Gegenprobe unter xdist wie in der CI (`-n 2 --dist worksteal --ci-shard i/3`
  über vier Dateien): Teile 52, 392, 21 Fälle, Exit 0 je Teil, Summe 465 =
  ungeteilte Sammlung; kein „different tests collected". `test_ci_runner.py`
  selbst läuft unter `-n 2 --dist worksteal` grün (52 passed).

### Befund 2.1 — Hinweis (Herkunft): Die Kerntabelle ist von Hand nachgetragen, entgegen der eigenen Regel

`tests/data/ci_core_durations.json`, `source.note`: „tests/test_seal_geometry.py
nach der räumlichen Vorauswahl der Wandmessung getrennt nachgemessen und
ersetzt". Dieselbe Änderung schreibt in `.claude/rules/tests.md` (Zeile 22–24):
„eine Tabelle wird aus JUnit-Berichten neu erzeugt (`tools/ci_shards.py`),
nie von Hand nachgetragen". `source.sha256` belegt damit zwei Berichte, deren
Summe nicht mehr die Tabelle ist. Das Werkzeug kann einen Eintrag gar nicht
ersetzen: `junit_file_seconds` summiert über alle Berichte, ein Zusatzbericht
würde die Schnur doppelt zählen. Folge nur für die Verteilung, nicht für die
Vollständigkeit.

Fix: einmal vollständig neu messen und die Tabelle mit dem Werkzeug
schreiben; oder die Regel um einen belegten Ersatzweg ergänzen (etwa
`--replace <bericht>`, der die Dateien dieses Berichts überschreibt statt
aufsummiert, und die Herkunft beider im `source` nennt).

### Befund 2.2 — Hinweis (Herkunft): Die Fenstertabelle stammt nicht aus dem Werkzeug und ist für die geteilte `test_ui.py` veraltet

`tests/data/ci_window_durations.json` trägt ein anderes `source`-Schema
(`run_id`, `job_id`, `log_sha256`, „Sekunden aus den 92
pytest-Schlusszeilen") und eine andere Policy („der ursprünglichen
Dateizeiten") als `table_from` schreibt; `tools/CLAUDE.md` und `tests.md`
sagen, beide Tabellen entstünden aus JUnit über `tools/ci_shards.py`. Dazu
gewichtet sie `tests/test_ui.py` mit 665 s aus dem Lauf auf `0895c4a6`,
während dieselbe Änderung die Datei in `test_ui_dialogs.py`,
`test_ui_export.py`, `test_ui_licensing.py`, `test_ui_remote.py` teilt
(Ersatzgewicht je 49,88 s). Die Gruppen werden damit schief, nicht
unvollständig. Fix: nach dem ersten grünen CI-Lauf mit
`tools/ci_shards.py windows reports/windows-*/tests__*.xml` neu schreiben;
bis dahin in der Karte sagen, dass die Tabelle aus Protokollzeilen stammt.

## 3. Isolierter Läufer: `tools/run_suite_isolated.py`, `tools/list_windowed_tests.py`

**Was trägt (kein Befund):**
- Alter Bericht wird vor dem Start gelöscht (`junit.unlink`), ein
  Nichtnull-Exit, ein fehlender, kaputter oder zu kleiner Bericht und jedes
  `failure`/`error` machen die Datei rot; `junit_counts` prüft die Attribute
  gegen die tatsächlichen `testcase`-Elemente. Gegenprobe mit echtem pytest
  (Scratchpad `probe_junit.py`): Abbaufehler nach Grün und nach Rot ergeben
  bei pytest je ein eigenes `testcase`; Attribute und Elemente stimmen
  (4/1/2/0), `junit_counts` liest sie korrekt.
- Zeitablauf: Windows `taskkill /T /F`, POSIX eigene Sitzung plus `killpg`;
  `BaseException` räumt ebenfalls ab.
- `plan_shards` verlangt beide Vertragsdateien in der Sammlung, verbietet
  leere Gruppen und Dateien ohne Fall; `run_ci` schreibt nach jeder Datei
  `summary.json`/`summary.md`, ein Sammelfehler hinterlässt einen roten
  Bericht; Rückgabe 1 nur bei `failed`, `planned` ist 0.
- Soll-Fallzahl und Lauf passen zusammen: Die Sammlung zählt Fenster über
  `qt_app` im Fixture-Graphen oder den ausdrücklichen Marker, ohne
  `performance`/`rendered`; der Kindlauf wählt `-m "windowed and not
  performance and not rendered"`, und der conftest setzt `windowed` für
  `qt_app` vor der Abwahl.
- `annotation` maskiert `%`, CR, LF in der Meldung und zusätzlich `:`, `,`
  im Titel — nach GitHubs Regel für Eigenschaften.

### Befund 3.1 — Fehler: Die Nachfrist für einen entkommenen Nachfahren greift nicht — der Läufer wartet, bis der Nachfahre endet

`tools/run_suite_isolated.py:250–280`. Nach `copier.join(OUTPUT_DRAIN_SECONDS)`
hängt der Läufer die Notiz „das Protokoll endet mit dem Bericht" an — und
verlässt dann den `with subprocess.Popen(...)`-Block. `Popen.__exit__` ruft
`self.stdout.close()`. Der Kopierfaden steckt zu diesem Zeitpunkt in
`source.read1(...)` auf genau diesem `BufferedReader` und hält dessen
Puffersperre während des blockierenden Lesens; `close()` wartet auf dieselbe
Sperre. Der Läufer steht damit, bis der Nachfahre schreibt oder endet.

Gemessen (Scratchpad `probe_drain.py`): Kind startet einen Enkel mit
geerbtem `stdout`, der 40 s schläft, und endet sofort. `run_ci_file` kehrt
nach **40,1 s** zurück, nicht nach rund 15 s; die Notiz steht trotzdem im
Ergebnis. Lebt der Nachfahre bis zum Jobende (ein liegengebliebener
Fensterprozess aus einem Test mit Kindprozess-Fenster), steht die ganze
Gruppe bis `timeout-minutes` still, ohne Ergebnis für diese Datei und ohne
die folgenden Dateien. Fail-closed bleibt es — aber die Zusage im Kommentar
an `OUTPUT_DRAIN_SECONDS` (75–77) ist falsch, und die Diagnose geht verloren.
Kein Test fährt diesen Zweig.

Fix: bei `copier.is_alive()` nach der Nachfrist `child.stdout = None` setzen,
bevor der `with`-Block endet (dann schließt `__exit__` den Leser nicht; der
Daemonfaden hält ihn bis Prozessende), oder `Popen` ohne Kontextmanager
führen und den Leser nur schließen, wenn der Faden beendet ist. Dazu ein
Test mit genau dem Sondenaufbau: Enkel mit geerbtem `stdout`, Rückkehr nach
höchstens `OUTPUT_DRAIN_SECONDS` plus Reserve.

### Befund 3.2 — Risiko: Ein Schreibfehler an Konsole oder Protokoll beendet das Leeren der Leitung

`copy_output` (206–222) fasst Lesen, Protokollschreiben und
Konsolenschreiben in ein `try` mit `except OSError, ValueError: return`.
Scheitert nur die Konsole (geschlossene Pipe des Aufrufers, etwa lokal hinter
`| head`) oder nur das Protokoll (Platte voll — in `tests.md` ein belegter
Vorfall), endet der Faden, niemand liest die Leitung mehr, das Kind blockiert
beim nächsten Schreiben, sobald der Pipe-Puffer voll ist, und die Datei fällt
nach `BUDGET_SECONDS` = 900 s als Zeitablauf statt mit ihrem Ergebnis. Fix:
Konsole und Protokoll getrennt behandeln — beim Konsolenfehler `console = None`
und weiter, beim Protokollfehler weiter lesen und verwerfen, beides als Notiz
im Ergebnis.

### Befund 3.3 — Hinweis: Ausgabe des Prüfprozesses kann Workflow-Befehle auslösen

Die Kindausgabe geht ungefiltert in das GitHub-Protokoll (Zeile 218–220).
Eine Testausgabe, die mit `::` beginnt (`::endgroup::`, `::error::`,
`::add-mask::`), wird vom Runner als Befehl gelesen und bricht die
Gruppierung oder erzeugt Anmerkungen, die nicht vom Läufer stammen. Fix:
vor dem Kopieren `::stop-commands::<zufälliges Token>` ausgeben und danach
`::<Token>::` — GitHubs vorgesehener Weg für fremde Ausgabe.

### Befund 3.4 — Hinweis (Diagnose): Ein Abbaufehler meldet „mehr Fälle als gesammelt"

pytest schreibt für einen Fehler im Abbau ein zusätzliches `testcase`
(Sonde: 3 Tests, JUnit `tests="4"`). `run_ci_file` (289–292) meldet dann
„Berichtet: 4 von 3 gesammelten Fällen." neben dem eigentlichen Fehler, und
`summary.md` zeigt `3/4`. Rot ist richtig; die Zeile schickt aber zuerst auf
die Suche nach einem zusätzlichen Test statt nach dem Abbau. Fix: gezählt
wird je `(classname, name)` einmal, oder der Satz nennt Abbaufehler als
mögliche Ursache.

## 4. Workflow `.github/workflows/build.yml`

**Was trägt (kein Befund):**
- Push auf `main`, `pull_request`, `schedule`: `quality` und `suite` mit
  `os = ["ubuntu-latest"]` × Teil 0–2; `window-contracts`, `windows`,
  `package` und alles dahinter sind übersprungen (`if` ist dort falsch, und ein
  übersprungener Job macht den Lauf nicht rot).
- `tests_only`: Kernmatrix auf drei Plattformen, beide Fensterjobs und alles
  ab `package` übersprungen; die Beschreibung des Eingangs sagt das jetzt
  richtig (die alte versprach „beide Mac-Architekturen").
- Paketbau ohne grüne Pflichtjobs ist nicht möglich: `package` trägt
  `needs: [quality, suite, window-contracts, windows]` und ein `if` ohne
  Statusfunktion, also gilt implizit `success()`; ein fehlgeschlagener,
  abgebrochener oder übersprungener Bedarf überspringt `package`. Die
  Fensterjobs haben dieselbe Bedingung wie `package`, können also nie
  übersprungen sein, während `package` läuft. Die macOS-Folgejobs verlangen
  `needs.package.result == 'success'`, trotz `always()`.
- Artefaktnamen je Matrixzelle eindeutig: `tests-core-<os>-<teil>`,
  `tests-contracts-<os>`, `tests-windows-<teil>`, `tests-latest-ubuntu`;
  kollisionsfrei gegen die Paketartefakte.
- `run: |`-Blöcke: `set -euo pipefail`, Kommentare sind ganze
  `#`-Zeilen (Backticks darin werden nicht ausgewertet), kein `${{ }}` in
  einem Kommentar. Alle Schritte beginnen mit `- name:` oder `- uses:`.
- Teilmatrix und Aufruf passen: `shard: [0, 1, 2]` zu `--ci-shard …/3` und
  `--shard-count 3`; mypy einmal je Plattform in Teil 0 (CI-04);
  `pytest-xdist==3.8.0` kennt `worksteal`; `ruff==0.16.7` ist in
  `constraints.txt` gebunden, `-c` greift also im Stiljob.
- Keine verbliebene Referenz auf `RELEASE_CHECK` oder `list_windowed_tests.py`
  im Workflow; kein Werkzeug hängt an alten Jobnamen.

### Befund 4.1 — Hinweis: Ein Typfehler in Teil 0 verschweigt ein Drittel der Kerntests seiner Plattform

`build.yml:161–183`: „Typen auf der Zielplattform" steht vor „Tests" ohne
eigenes `if` für den Folgeschritt. Scheitert mypy, läuft Teil 0 nicht, der
Upload findet kein `reports/core/` und scheitert zusätzlich an
`if-no-files-found: error`. Gegenüber HEAD ist das besser (dort hielt mypy
alle Tests an), widerspricht aber dem Satz „Qualität, Kernmatrix … rechnen
unabhängig" (Kopf, Konzept §3). Fix: mypy als letzten Schritt von Teil 0 mit
`if: ${{ !cancelled() && matrix.shard == 0 }}`; den Wächter in
`test_only_the_requested_latest_dependencies_run_alongside_a_manual_build`
mitziehen.

### Befund 4.2 — Vermutung (Hinweis): Ein erneut gestarteter roter Testjob kann am Artefaktnamen scheitern

Die Berichte laden mit `if: always()` hoch, also auch im roten ersten
Versuch. Bei `upload-artifact` ab v4 sind Namen je Lauf eindeutig; ob ein
„Re-run failed jobs" den Namen aus dem ersten Versuch freigibt, habe ich
hier nicht belegen können. Trifft die Kollision zu, wird ein erneut
gestarteter Testjob allein am Upload rot, auch wenn seine Tests grün sind —
und `package` bleibt gesperrt. Fix, falls es sich bestätigt: `overwrite: true`
an den vier Test-Uploads oder `${{ github.run_attempt }}` im Namen (behält
beide Versuche für die Diagnose). Prüfen am ersten echten Lauf mit einem
Wiederholungsstart.

### Befund 4.3 — Hinweis: Die Berichtsartefakte zählen gegen die Seitengrenze des Windows-Signierwegs

`tools/windows_signed_installer.py:191–193` liest die Artefakte eines
`build.yml`-Laufs mit `per_page=100` und verlangt
`total_count == len(artifacts)`. Ein voller Tag-Lauf trägt jetzt 15
Testberichte zusätzlich zu den rund 12–15 Paket- und Signierartefakten —
heute unkritisch, aber wer die Teilzahl erhöht (die Regel in
`auslieferung.md` lädt ausdrücklich dazu ein, „wer Teile dazunimmt"), bricht
die Installer-Signatur mit „Artefaktliste ist unvollständig". Fix: im Werkzeug
seitenweise lesen, oder in `test_packaging.py` die Zahl der Uploads eines
Tag-Laufs unter 100 zusichern.

## 5. Tests der CI: `test_ci_runner.py`, `workflow_helpers.py`, `test_packaging.py`, `test_toolchain.py`, `test_supply_chain.py`

Gelaufen: `tests/test_ci_runner.py`, `tests/test_packaging.py`,
`tests/test_supply_chain.py`, dazu
`test_toolchain.py::test_the_ci_refuses_to_run_without_the_exact_kernel` und
`::test_no_generated_comparison_runs_in_the_ci` — Exit 0, 203 passed (53 s).

**Was trägt (kein Befund):**
- `test_ci_runner.py` prüft an echten Kleinprozessen Erfolg, Assertion,
  fehlenden, kaputten, leeren und zu kleinen Bericht, Exit 5, Absturz nach
  grüner Zeile, Zeitablauf mit Enkelprozessen (Lebendprüfung über
  `GetExitCodeProcess == STILL_ACTIVE`, nicht über ein Handle), die
  Anmerkungsmaskierung und die Konsolengruppen. `--ci-shard` wird am echten
  Weg gesammelt.
- `test_packaging.py`: `_assert_ci_dependencies` mit neun Gegenproben
  (Bedarf verkürzt, Teilmatrix fehlt oder lückenhaft, Anzahl verschoben,
  fester Teil, Serialisierung über `needs`, `continue-on-error`, Plattform
  entfernt); jede Gegenprobe prüft zuerst, dass ihr Text im Workflow steht.
  Die genaue `if`-Zeile von `package`, `window-contracts`, `windows` ist
  festgenagelt — damit fallen auch `!cancelled()` oder eine gefaltete
  `if: >-`-Form auf, die `_assert_ci_dependencies` allein nicht sähe.
  Die Upload-Regel hängt am Upload-Schritt selbst, mit Gegenprobe.
- `job_block` verlangt genau einen Treffer, `windows:` trifft nicht
  `windows-installer:`.

### Befund 5.1 — Hinweis: `step_block` endet nur an `- name:` oder `- uses:`

`tests/workflow_helpers.py:23–25`. Ein künftiger Schritt, der mit `- run:`,
`- id:` oder `- if:` beginnt, würde dem benannten Schritt davor zugeschlagen,
und `step_script` gäbe dann womöglich dessen `run: |` zurück — ein Test
prüfte still den falschen Block. Heute beginnt jeder Schritt mit `name` oder
`uses` (nachgezählt), daher kein aktueller Fehler. Fix: an jedem
`^      - ` enden lassen.

## 6. Statische Testbündelung

Gelaufen: `test_language_rules.py`, `test_translations.py`,
`test_directory_docs.py`, `test_parts.py::test_a_part_names_the_features_it_promised`,
`test_registry_consistency.py` — Exit 0, 1582 passed, 1 deselected (40 s).

**Was trägt (kein Befund):**
- `test_language_rules.py`: Stämme, Umlaute und englische Feld-Docstrings
  laufen über denselben AST; alle drei Befundlisten werden aufsummiert und
  zusammen gemeldet. Parameterliste unverändert `source_files()` (mit
  Leer-Zusicherung). Der pre-commit-Hook sucht Dateinamen in den
  `E `/`FAILED`-Zeilen — die Parameter-ID `[name.py]` und die `name:zeile`-
  Präfixe bleiben erhalten.
- `test_translations.py`: `surface_files()` ist wörtlich
  `sorted(UI_DIR.rglob("*.py"))`, also dieselbe Menge wie der aufgelöste
  Dateifiltertest; beide Befundarten gehen in eine Liste. Die Kataloge melden
  jetzt fehlende **und** verwaiste Schlüssel aller Sprachen zugleich (vorher
  verdeckte ein fehlender Schlüssel die verwaisten derselben Sprache), und
  die leere Sprachliste ist neu zugesichert.
- `test_directory_docs.py`: `Path.walk` mit Beschneiden der Kinder;
  `app/` selbst bleibt draußen wie bei `rglob`. Die neuen Tests greifen
  wirklich: `Path.walk` geht über `os.walk` und damit über `os.scandir`
  (Scratchpad-Sonde: gepatchtes `scandir` sieht den beschnittenen Ordner nie).
  Vorher schloss `EXEMPT & set(path.parts)` auch über einen gleichnamigen
  Vorfahren der Wurzel aus; das ist jetzt behoben und getestet.
- `test_parts.py`: alle Zusicherungen beider Tests stehen im
  zusammengelegten; zwei frische Bauten, `PARTS_SWEEP` in
  `test_registry_consistency.py` zeigt weiter auf den Namen.

### Befund 6.1 — Hinweis: Zwei Zusammenlegungen melden nur den ersten Befund

- `tests/test_translations.py:186`: `_assert_source_text_uses_umlauts(ids)`
  wirft vor `assert not errors`. Ist ein Quelltext falsch geschrieben
  („Groesse"), bleiben fehlende und verwaiste Katalogschlüssel ungemeldet,
  bis er behoben ist. Fix: die Umlautfunde als Liste zurückgeben und in
  `errors` aufnehmen.
- `tests/test_parts.py:1616–1623`: die Merkmalszusicherungen stehen vor dem
  Reproduzierbarkeitsvergleich; ein fehlendes `feature.params` verdeckt einen
  gleichzeitig nicht reproduzierbaren Baustein. Fix: zuerst Volumen und
  Dreieckszahl vergleichen oder beide Befunde sammeln.

Dazu: Die Testnamen sagen nicht mehr, was geprüft wird —
`test_identifiers_are_english` meldet auch Feld-Docstrings,
`test_every_text_is_translated` auch die Schreibung der deutschen Quelle,
`test_a_part_names_the_features_it_promised` auch den Determinismus.
Die Zuordnung alt → neu steht nur in
`.claude/.state/ci-test-optimierung-2026-09-24/statische-tests.md`. Fix:
jeweils ein Satz im Docstring, der die mitgeprüfte Zusage nennt (bei den
ersten beiden steht er schon halb), oder ein präziserer Name.

## 7. Doku

- `CLAUDE.md` (Befehle), `AGENTS.md` („CI-Aufteilung hat einen geprüften
  Vertrag"), `.claude/rules/auslieferung.md`, `tools/CLAUDE.md`,
  `tests/CLAUDE.md`: stimmen mit Workflow und Code überein (Paket wartet auf
  alle vier Pflichtjobs, Teilmatrix `0 … N−1`, Konsole, Anmerkung,
  Schrittbericht, drei Sammlungen im Teiltest, conftest-Punkt vier).

### Befund 7.1 — Hinweis: Das Konzept widerspricht sich bei mypy

`konzepte/konzept-ci-testlaufzeiten-2026-09.md:61`: „mypy bleibt in jedem
Kernjob"; Zeile 67 und der Workflow: „mypy läuft einmal je Plattform im
Teil 0". Ein Kernjob ist jetzt ein Teil. Fix: Zeile 61 auf „in jeder
Plattform der Kernmatrix".

### Befund 7.2 — Hinweis: Herkunftsaussagen der Tabellen

`tests/data/CLAUDE.md:20–21` und `.claude/rules/tests.md:22–24` („nie von
Hand"), `tools/CLAUDE.md` („aus JUnit-Berichten") gegen die eingecheckten
Tabellen — siehe Befunde 2.1 und 2.2. Zusätzlich nennt der Docstring von
`tools/ci_shards.py:3–4` als Aufruf `reports/**/junit.xml` bzw.
`reports/windows-*/tests__*.xml`; nach `gh run download` liegen die Berichte
aber unter den Artefaktnamen (`tests-core-*/junit.xml`,
`tests-windows-*/tests__*.xml`). Fix: den Aufruf mit dem Download-Pfad
zeigen. Der ROADMAP-Eintrag `ci-testlaufzeiten` sollte die Neuerzeugung
beider Tabellen nach dem ersten CI-Lauf ausdrücklich führen (heute nur die
Kerntabelle).

## Urteil

So wie es liegt: nein — aber knapp. Vor dem Commit gehören 3.1 (die
Nachfrist hängt nachweislich; eine Zeile `child.stdout = None` nach
abgelaufener Nachfrist plus ein Test mit dem Sondenaufbau) und die ehrliche
Einschränkung der Leistungszusage aus 1.1 (Kommentar an `RAY_CULL_PAIRS`,
Karte) nachgezogen, besser gleich die Übergaberegel. Danach ja: Bitgleichheit
der Vorauswahl, vollständige und disjunkte Teilung und die Sperre der
Paketfreigabe halten bereits; die übrigen Punkte sind Hinweise oder gehören
ins Register.

