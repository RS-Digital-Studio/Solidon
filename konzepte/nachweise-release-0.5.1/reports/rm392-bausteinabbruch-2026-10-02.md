# RM-392-Nachprüfung: Abbruch im Randvergleich (P2G03)

Stand: 02.10.2026. P2G03 gehört zur Nachprüfung des Randtests aus RM-392.
Die eigene Korrektur und die gezielten Läufe sind unabhängig freigegeben.
Das vollständige Entwicklungstor und die tatsächliche Git-Integration
dieser Einheit stehen aus; es entsteht keine neue RM-Nummer.

## Kundenfehler und Korrektur

Beim Einsetzen eines abtragenden Bausteins prüft Solidon, ob dessen Umriss
seitlich über die gewählte Fläche hinausragt. Sowohl der Netzweg als auch
der exakte Weg übergaben den Abbruch aus `OpContext` bisher nicht an
`_over_the_rim` und dessen `ray_hits_batch`. Ein Abbruch während dieser
Rechnung hielt den Randvergleich deshalb nicht an.

Der Strahlenhelfer liefert bei einem Abbruch ausdrücklich einen Teilstand.
Deshalb braucht der Anschluss zwei Schritte: den Token weitergeben und
ihn unmittelbar nach der Rückkehr prüfen, bevor aus dem Teilstand ein
Randbefund entsteht.

Der Produktdiff in `app/core/knowledge/parts/ops.py` enthält genau fünf
Anschlüsse:

1. `_insert_at` übergibt `ctx.cancelled` an den Randvergleich.
2. `_over_the_rim` verlangt dafür den benannten Parameter `cancelled`.
3. Der Randvergleich übergibt denselben Token an `ray_hits_batch`.
4. Direkt nach der Rückkehr folgt `cancelled.raise_if_cancelled()`.
5. `_insert_at_exact` übergibt ebenfalls `ctx.cancelled`.

Die vorhandene Geometrie, die Platzierung, der Randbefund und seine Texte
bleiben unverändert. Ein gesetzter Abbruch verlässt den Randvergleich nun
als bestehende `OperationCancelled`.

## Acht neue öffentliche Anschlussfälle

`tests/test_parts_review_regressions.py` wurde ausschließlich um
`test_a_cutting_parts_rim_check_obeys_its_context_cancellation` ergänzt:

- Träger aus `create_box` und `create_brep_box`;
- jeweils `draft` und `fine`;
- jeweils vollständige Rechnung und Abbruch während der Strahlenrechnung.

Der Träger entsteht durch den tatsächlichen `History`-/`evaluate`-Weg.
Der registrierte `insert_keyhole` wird mit einem echten `OpContext` und
`CancelSignal` aufgerufen. Kontrolliert wird die Portionierung des echten
Strahlenvergleichs; erst nach dem ersten tatsächlich gerechneten Block
wird abgebrochen. Die Tests erfinden keine Distanzen oder Treffer.

Die Abbruchfälle verlangen den exakten Typ `OperationCancelled`, genau
einen gerechneten Block, den tatsächlichen Teilstand und die Identität
des Kontexttokens an beiden Anschlüssen. Der Randbeobachter wirft selbst
keinen erwarteten Abbruch: Kehrt der Vergleich trotz gesetztem Token
regulär zurück, scheitert ein `AssertionError` vor späteren Checkpoints.

Die Erfolgskontrollen verlangen alle zwölf Trägerdreiecksblöcke, einen
kleineren Ergebniskörper im ursprünglichen Kern und genau einen
Randbefund mit Ort. Die vorhandenen Nachbarfälle wurden nicht geändert.

## Tatsächliche Läufe

Alle Läufe nutzten den Repository-Interpreter `.venv/Scripts/python.exe`,
`pytest -q`, den Markerfilter
`not windowed and not rendering and not performance` sowie `--tb=short`
und eine eigene JUnit-Datei. Es wurde keine ganze Testdatei ausgeführt.

| Lauf | Bestanden | Testfehler | Aufbau-/Abbaufehler | Skips | Nativer Exit |
|---|---:|---:|---:|---:|---:|
| Neue acht Fälle vor dem Produktfix | 4 | 4 | 0 | 0 | 1 |
| Dieselben acht Fälle nach dem Produktfix | 8 | 0 | 0 | 0 | 0 |
| Bestehende Rand- und Indexfälle | 5 | 0 | 0 | 0 | 0 |
| Isoliert ohne Weitergabe an den Strahlenhelfer | 0 | 4 | 0 | 0 | 1 |
| Isoliert ohne unmittelbaren Nachtest | 0 | 4 | 0 | 0 | 1 |

Vor dem Fix scheiterten ausschließlich die vier Abbruchfälle am
Rückkehrwächter: „Der Randvergleich gab nach dem Abbruch einen Teilstand
als Befund zurück.“ Beide Kerne und beide Güten waren betroffen.

Die fünf bestehenden Fälle sind:

- `test_a_cutting_part_over_the_rim_of_its_face_says_so`: zwei Kerne;
- `test_a_cutting_part_within_its_face_stays_quiet`: zwei Kerne;
- `test_a_cancelled_ray_index_stops_inside_its_descent`: ein Fall.

Die beiden zusätzlichen Fehlvarianten änderten ausschließlich eine
geladene Funktionskopie im jeweiligen Prüfprozess. Keine Produktdatei
wurde dafür umgeschrieben. Ohne Tokenweitergabe scheiterten alle vier
Abbruchfälle an `12 == 1` gerechneten Blöcken. Ohne Nachtest scheiterten
alle vier am Rückkehrwächter. Die vier Erfolgskontrollen wurden in diesen
beiden Fehlvarianten jeweils ausdrücklich abgewählt.

Die Quell- und Testhashes vor und nach jedem einzelnen Lauf sind identisch.
Rohtext, JUnit und Ergebnis-JSON stimmen in Fällen, Fehlertypen und Zahlen
überein. Es gab keinen verworfenen oder fehlerhaften Testaufbau.

## Mechanische und eigene Quellprüfung

- Ruff über die beiden zugewiesenen Dateien: Exit 0.
- Fünf reine Ruff-Formatkontrollen über die eigenen Quellbereiche und den
  Testanhang: jeweils Exit 0; keine Datei wurde formatiert.
- Die fünf Produkt-Hunks ergeben aus der gesicherten Ausgangsdatei exakt
  die aktuelle Datei. Der Teststand ist exakt Ausgangsdatei plus Anhang.
- Produktdiff und vollständiger Testanhang wurden nach dem Lauf erneut
  gelesen. Alle tatsächlichen Aufrufer von `_over_the_rim` sind angeschlossen.
- Die vorhandene `CancelToken`-Schnittstelle wird genutzt. Es entstehen
  weder eine neue Abhängigkeit noch Qt-Import, globale Abbruchzustände,
  zusätzliche Ausnahmeart oder übersetzungsbedürftiger Kundentext.
- Die reine Importgraph-Auswahl mit `tools/affected_tests.py` und beiden
  ausdrücklich genannten Dateien endete mit Exit 0 und verlangt das
  zentrale Entwicklungstor. Diese Auswahl wurde weder gesammelt noch
  ausgeführt.

Das sind eigene Prüfung und gezielte Entwicklungsnachweise. Der
unabhängige Entwurfsreview in `REVIEW.md` gab den Testplan frei; der
unabhängige Review des ausgeführten Produktstands ist in `REVIEW_FINAL.md`
mit **JA** belegt; sein SHA256 steht im folgenden Nachtrag.

## Bereichsnachweis und Versionen

Für diesen vollständigen Diff ist keine Versionsänderung erforderlich:

- `range_proof._NOT_SHAPE` enthält ausdrücklich
  `app.core.knowledge.parts.ops`; die Datei gehört nicht zu `_SHARED`.
  Formdateien, Schema, Grenzen und Bezugsprofile sind unverändert.
- `LIBRARY_VERSION` und `PartChange` betreffen Maßänderungen gemäß
  Bauplan §24.4. Der nicht abgebrochene Baustein behält seine Maße.
- `_result_version`, die Operation-Cacheversion und
  `CACHE_FORMAT_VERSION` bleiben passend: Das vollständige Ergebnis und
  seine Daten ändern sich nicht. Der Auswerter prüft bereits vor der
  Veröffentlichung vorgemerkter Cacheeinträge den Token.

Diese Einordnung gilt für die fünf beschriebenen Anschlussänderungen.
Sie bewertet keine weiteren Änderungen an der RM-392-Geometrie.

## Identität und Nachweise

| Datei | Ausgangs-SHA256 | Abschließender SHA256 |
|---|---|---|
| `app/core/knowledge/parts/ops.py` | `a7f062431d8052fca4535999718159fe7018f3eb2d96af38b4116898d1309e3a` | `f84ef5cedb4a6c296d7e47bb0e79c3e7ffa3139a05b359683714f9737ae21f80` |
| `tests/test_parts_review_regressions.py` | `b1b7c966668893923594491e4860f95d30f518357a5bbf0e0dbda0f6cbfcaada` | `00aee0f1bae7dd81ca5c3835d83c8c1b3bb43ba119260a96f1af659b6748ac41` |

Die Testdatei hatte schon im Gegenlauf den abschließenden SHA256. Die
Datei `app/core/geom/mesh.py` blieb während aller Läufe auf
`7b3d87c4b2a130d37cfe48b33252233eb3c89c33ecd4b9fd315494f2ae02ec45`.

Der örtliche Beweisordner ist
`tmp/review-seit-0.5.1-2026-10-01/p2g03-bausteinabbruch-20261002-7db5/`:

- `before`, `after`, `existing`, `without-forwarding`, `without-postcheck`:
  jeweils `.txt`, `.xml` und `-result.json`;
- `own-source-hunks.json`, `own-test-hunk.json`, `own-diff.patch` und
  `scope-result.json` für die exakte Änderungsgrenze;
- `owned-checks-result.json` und die sechs zugehörigen Ruff-Rohtexte;
- `affected.txt` und `affected-result.json` für die reine Importgraph-Auswahl;
- `run_cases.py`, `run_followup.py`, `p2g03_faults.py` für die Laufaufbauten.

Die historische Erstdiagnose mit 299 beziehungsweise 212 Strahlen ist
kein neuer Messwert dieses Nachgangs. Deren künstlicher späterer Stopp
wird nicht als erfolgreicher Produktabbruch ausgegeben.

## Verbleibende Grenzen

Die Fälle prüfen echte kleine Geometrie und den kooperativen Anschluss.
Sie messen keine native Abbruchlatenz und liefern keinen Fenster-,
Renderer-, Leistungs-, Paket- oder plattformübergreifenden Nachweis.
Ein Entwicklungstor mit dem integrierten Fix und die zentrale
Dokument-/Git-Integration bleiben gesonderte Schritte. Produktreview
und frischer Anschlussnachlauf sind inzwischen unabhängig mit JA
freigegeben. Der frühere Tor51-Stand enthielt diesen Fix nicht.

## Frischer Nachlauf auf gemeinsamer Basis und unabhängige Freigaben

Nach dem zentralen Merge-Tor wurden die acht neuen Varianten und fünf
bestehenden Kontrollen erneut tatsächlich zusammen ausgeführt:
**13 bestanden, Exit 0, keine Testkörper-/Aufbau-/Abbaufehler oder Skips**.
Der vollständige Filter lautete diesmal
`not windowed and not rendering and not rendered and not performance`.
Alle fünf erfassten Dateien blieben vor und nach dem Lauf bytegleich.

| Im frischen Nachlauf erfasste Datei | SHA256 |
|---|---|
| `app/core/knowledge/parts/ops.py` | `f84ef5cedb4a6c296d7e47bb0e79c3e7ffa3139a05b359683714f9737ae21f80` |
| `tests/test_parts_review_regressions.py` | `00aee0f1bae7dd81ca5c3835d83c8c1b3bb43ba119260a96f1af659b6748ac41` |
| `app/core/geom/mesh.py` | `0c4c56b6a1d8ff244c5db7f87f15ee837559bafce147f49dce86865c252ac978` |
| `app/core/knowledge/parts/range_proof.py` | `a4777c30c70b61333e758b570d5aafe4a3297a5cd968a8121394b2a256790326` |
| `tests/test_geometry_review.py` | `b0b8b21a9ab40d5c0509637f6530e7587c9562ca9c24e43204ea08911983a5c6` |

Der Nachlauf bestätigt den eigenen unveränderten Partanschluss jetzt
auch mit der `mesh.py`-0c4c/RM327-Basis. Er ersetzt den historischen
Meshstand 7b3d nicht rückwirkend und behauptet keinen Review fremder
RM327-Geometriehunks. Die fünf vorhandenen Kontrollfälle befinden sich
in `test_parts_review_regressions.py` (vier) und
`test_geometry_review.py` (Strahlindexabbruch, einer).

Örtliche Originale: `final-current-base.txt`, `.xml` und `-result.json`;
`run_final_cases.py` hält die Auswahl fest. Der unabhängige Reviewer
`/root/rm298_lifecycle_tests` hat Rohtext, JUnit, Ausgang und alle fünf
Hashes lesend abgeglichen und mit **JA** freigegeben:

| Unabhängiger Beleg | SHA256 |
|---|---|
| `REVIEW_FINAL.md` | `a5672991e81e11941ec6dd8b93855d1cda77ad5b7f60f6feec4dd1e8653e49de` |
| `REVIEW_FINAL_RUNS_2026-10-02.md` | `4ba97aaa3412905f4b1f547b7f3fc7a558fbd13ba4481f7fa8494901dbea4e5b` |

Die Freigaben betreffen die fünf Token-/Nachtestanschlüsse, die eigenen
acht öffentlichen Fälle und diesen gezielten Nachlauf. Bereichs-, Cache-,
Paket-, Fenster-, OS- und Leistungsprüfungen wurden hier nicht neu gefahren.
