# RM298(c): Prozessfehler durch geometrische Fänge weitergeben

Stand: 02.10.2026. Eigenständig geprüfte und unabhängig freigegebene
Ausnahmeweitergabe; mit getrenntem frischem Nachlauf auf der finalen Basis.

## Befund und Änderung

Sieben geometrische Fänge behandelten einen verlorenen Hilfsprozess oder einen
verweigerten Prozessstopp wie eine geometrische Absage. Dadurch konnte der
öffentliche Aufruf eine Ersatzwarnung liefern, eine weitere Vergleichsrechnung
oder Entlüftung versuchen oder ein negatives 3MF-Teil auslassen.

Die Fänge geben jetzt die vorhandene Familie
`kernel_process.NOT_A_KERNEL_FAILURE` unverändert weiter. Sie umfasst
`OperationCancelled`, `KernelHelperLostError` und `KernelHelperStopError`.
Die bisherigen `PROGRAMMING_ERRORS` bleiben geschützt; die normalen
Geometrieauswege bleiben bestehen. Neue Fehlerklassen, Texte, Maße und
Geometrieverfahren wurden nicht eingeführt.

| Datei | Eigener Anschluss |
|---|---|
| `app/core/geom/prepare.py` | `_really_overlap`, nur der Fang der Abstandsfrage |
| `app/core/geom/difference.py` | `_clipped_to_the_change`, `_cut_parts`, `_cut` |
| `app/core/geom/hollow.py` | `_vent`, nur der Fang der einzelnen Entlüftung |
| `app/core/geom/repair.py` | `resolve_self_intersections`, vorhandenen Abbruchfang erweitern |
| `app/core/ingest/threemf.py` | `_carved`, lokaler Kernelimport bleibt lokal |

Hinzu kommen nur die notwendigen Kernelimporte. Nach der Ersetzung des
einzigen direkten `OperationCancelled`-Fangs wurde dessen unbenutzter Import
aus `repair.py` entfernt. Die fremden RM327-Hunks bleiben erhalten.

## Öffentliche Regressionen

Sieben Testfunktionen prüfen je zwei Fehlerklassen; der gemeinsame
Differenzbeobachter delegiert die tatsächliche Boolesche Rechnung.

- `tests/test_prepare.py::test_a_clearance_check_forwards_the_original_kernel_process_error`: `lost` und `stop`.
- `tests/test_difference.py::test_clipping_a_local_comparison_forwards_the_original_kernel_process_error`: `lost` und `stop`.
- `tests/test_difference.py::test_uniting_changed_comparison_parts_forwards_the_original_kernel_process_error`: `lost` und `stop`.
- `tests/test_difference.py::test_cutting_a_comparison_forwards_the_original_kernel_process_error`: `lost` und `stop`.
- `tests/test_missing_ops.py::test_the_first_hollowing_vent_forwards_the_original_kernel_process_error`: `lost` und `stop`.
- `tests/test_repair.py::test_resolving_self_intersections_forwards_the_original_kernel_process_error`: `lost` und `stop`.
- `tests/test_threemf_native_materials.py::test_a_native_negative_part_forwards_the_original_kernel_process_error`: `lost` und `stop`.

Die Zielhelfer werden nicht durch Attrappen ersetzt. Die Tests durchlaufen
`check_collisions`, `compare`, `hollow`, `repair` und `read_objects` bis zum
echten Kerneladapter. Genau dort wird eine bekannte Prozessausnahme injiziert.
Vorbereitende Volumen-, Bohr- und Hohlraumrechnungen bleiben echt. Die
`finally`-Zusicherungen verlangen den erreichten Auftrag und seine Operanden.
Ein weiterer Rechenversuch löst einen eigenen Wächter-TypeError aus; die
ursprüngliche Ausnahme wird nicht erneut injiziert. Erfolgreich ist nur die
identische Ausnahme ohne Ersatzresultat, Folgeversuch oder geänderte Eingaben.

## Tatsächlich ausgeführte Entwicklungsläufe

Interpreter: `.venv/Scripts/python.exe`, Python 3.14. Alle drei Läufe wählten
ausschließlich die benannten Entwicklungstests mit
`not windowed and not rendering and not rendered and not performance`.
Jeder Lauf hat vollständigen Rohtext, JUnit und den nativen Prozessausgang;
15 Quell-, Test- und Korpusdateien wurden jeweils vorher und nachher gehasht.

| Lauf | Bestanden | Testfehler | Auf-/Abbaufehler | Übersprungen | Nativer Exit | Hashes stabil |
|---|---:|---:|---:|---:|---:|---|
| before | 0 | 14 | 0 | 0 | 1 | ja |
| after | 14 | 0 | 0 | 0 | 0 | ja |
| existing | 19 | 0 | 0 | 0 | 0 | ja |

Vorher scheiterten vier Fälle an `DID NOT RAISE` und zehn an den vorgesehenen
Wächtern für eine weitere Rechnung. Keine Routenassertion scheiterte. Dies
sind echte Testkörperfehler am unveränderten Produktcode, keine Fehler des
Prüfaufbaus. Danach bestanden dieselben 14 Fälle.

Die 19 bestehenden Kontrollen decken korrekte Abstände und offene Hüllen,
normale und unvollständige Differenzen, Aushöhlen und Entlüftung, drei
gewöhnliche Reparaturausgänge, tatsächlichen Reparaturabbruch und
Materialübertragung sowie den erfolgreichen, fehlgeschlagenen und wirkungslosen
3MF-Aussparungsschnitt ab. Die bestehende Hohlraum-Kontrolle ersetzt `_vent`
für ihre Aussage über den äußeren Hüllenfehler; sie wird nicht als Beleg für
den neuen inneren Entlüftungsfang ausgegeben. Diesen belegen die zwei neuen
öffentlichen Hohlraumfälle.

Der geprüfte Nachherstand trug in `repair.py` noch den unbenutzten Import:
SHA256 `82167393cde8eb4c56d68bde622dd33f5fb3e7a3a0275b986c059879754ae919`.
Ruff beanstandete ihn anschließend genau einmal mit F401. Nach seiner
Entfernung bestanden Ruff für alle zehn betroffenen Dateien sowie alle
26 eigenen Formatbereiche; jeweils Exit 0 und stabile Dateihashes. Während
des zentralen Tors wurde kein weiterer Testlauf gestartet. Die Importbereinigung
ist daher statisch geprüft, aber kein nachträglich behaupteter Lauf am finalen
Ganzdateihash.

Die reine Importgraph-Auswahl durch `tools/affected_tests.py` ist
dokumentiert und wurde nicht als Lauf ausgeführt oder gesammelt. Das
vollständige Entwicklungstor mit mypy bleibt bei der zentralen Sitzung.

## Cache- und Versionsentscheidung

Die alten Rückfälle konnten speicherbare Ausgaben erzeugen: `hollow_object`
übernimmt das `HollowResult` auch mit ausgelassener Entlüftung;
`repair` übernimmt das unveränderte Netz samt `repair.self_intersections_unresolved`;
`load` übernimmt eine 3MF ohne ausgeschnittenes negatives Teil;
`check_collisions` mit positiver Mindestluft übernimmt einen Ersatzbefund.
Ihre aktuellen Op-Versionen sind 2, 3, 4 und die leere Vorgabe. Die drei
Differenzfänge dienen der Vorschau und haben keinen eigenen Operationscache.

Diese Einordnung folgt den tatsächlichen Anschlüssen in
`prepare_ops.hollow_object`/`_mesh_hollow_result`, `ops.repair_object`,
`ingest.ops.load` und `prepare_ops.check_collisions_op`. `evaluate` nimmt
abgeschlossene `OpResult`-Ausgaben in `pending` auf und schreibt sie nach den
Abschlussprüfungen bei `stopped_at is None`; eine lediglich verschluckte
Prozessausnahme setzt keinen Abbruchtoken. Die Aussage „Erfolgsgeometrie
unverändert“ allein wäre deshalb keine ausreichende Cachebegründung.

Der bestehende Vertrag entwertet diese Altstände bereits an
`paths.results_cache_dir()` (§38): Der Ordner enthält `APP_VERSION`, im
Quellbetrieb zusätzlich `_build_stamp()` über sämtliche Pythondateien unter
`app/core`. Dessen Docstring nennt ausdrücklich die geänderte Boolesche
Rückfallstufe. Ein gebautes Paket trennt den Stand über die beim Release zu
erhöhende Anwendungsversion. Der Speichercache lebt nur in seiner Sitzung.
Die vorhandenen Wächter `test_a_changed_core_file_gets_a_folder_of_its_own`
und `test_a_built_package_needs_no_source_stamp` wurden hierzu gelesen,
in dieser Einheit aber nicht neu ausgeführt.

Eigenprüfung und unabhängiger Anschlussreview bestätigen: keine zusätzliche
manuelle Op-, Bibliotheks-,
Projektformat- oder Cacheformatzahl für diese Ausnahmeweitergabe.
`CACHE_FORMAT_VERSION` bleibt 35; seine Datenstruktur wird nicht geändert.
`REVIEW_PRODUCTION.md` verfolgt Session/CLI über `disk_backed_cache` und
`DiskCache.directory` bis `results_cache_dir`. Die Trennung gilt beim normalen
Neustart und Update; beim Release bleibt die Erhöhung der Anwendungsversion
zwingend. Kein manueller Versionshunk wurde geschrieben.

## Abgrenzung im gemeinsamen Baum

Die eigenen Änderungen sind als genaue Old/New-Hunks gesichert.

Fremde RM327-Testergänzungen kamen teilweise bereits zwischen der eigenen
Testintegration und dem Vorherlauf hinzu. `before` und `after` liefen mit
denselben nachfolgend genannten Testhashes. Zwischen diesen 14er-Läufen und
`existing` änderte sich `test_prepare.py` nochmals. Innerhalb jedes einzelnen
Laufs waren alle 15 aufgezeichneten Hashes stabil. Die frühere Formulierung
„Nach den Läufen“ war zeitlich zu pauschal und ist hier berichtigt.

| Stand | test_prepare.py | test_repair.py | test_missing_ops.py |
|---|---|---|---|
| Eigene Testintegration | `e5339e635a58831abb8e09dd4ef9b91e0e2d2f3e571f721ddbdc5a609fe7c156` | `3220a4e6007519a306cf38050b2554b272610d9d26d6f074e9da9166bf39abd6` | `f4c983c8a022b1f1da076c6db61343baff35acd3fbe716d574240238a1e554fe` |
| before und after | `a9fd3a6909fcce86351faa0be82637df52f94e717d604eb2abc03e12871ffae2` | `3e248ddbb7ab09142519c57ec6e4e6393bed63ef70bd55008170ca30b8b0aaeb` | `f4c983c8a022b1f1da076c6db61343baff35acd3fbe716d574240238a1e554fe` |
| existing und finale statische Prüfung | `d714522f2048fc07ab69bcb20bf3755ab82a99e4933d8712067945919f0a6f59` | `3e248ddbb7ab09142519c57ec6e4e6393bed63ef70bd55008170ca30b8b0aaeb` | `f4c983c8a022b1f1da076c6db61343baff35acd3fbe716d574240238a1e554fe` |
| Lesender Nachtrag 2026-10-02T15:51:52+02:00 | `d714522f2048fc07ab69bcb20bf3755ab82a99e4933d8712067945919f0a6f59` | `3e248ddbb7ab09142519c57ec6e4e6393bed63ef70bd55008170ca30b8b0aaeb` | `292d1be60b0c771a43927bea3f3aaaedfd5f8653bf5b03bd403a98bcdee5a0a7` |

Für `test_prepare.py` mit SHA256
`a9fd3a6909fcce86351faa0be82637df52f94e717d604eb2abc03e12871ffae2`
liegt in dieser Einheit keine archivierte Ganzdateikopie vor. Die tatsächlichen
Laufmetadaten belegen diesen Hash; eine ursprüngliche Integrationskopie oder
heutige Teilkombination fremder Hunks wird nicht als diese historische
Originalbasis ausgegeben. Ein neuer Lauf auf heutiger Basis bleibt ein
separater Nachweis und ersetzt keine historische Datei rückwirkend.

Nach der finalen statischen Prüfung änderte die fremde RM424-Arbeit außerdem
`test_missing_ops.py`. Der zeitgestempelte Lesestand ist kein neuer Ruff- oder
Pytest-Nachweis. Alle eigenen Hunks wurden darin bytegenau wiedergefunden und
im Speicher entfernt/wieder eingesetzt. `current-handoff-hunks.json` enthält
unveränderte eigene Old/New-Hunks und die zugehörigen neuen Hashes. Die so
rekonstruierte Vorwärtsbasis ist ausdrücklich keine historische Laufbasis.
Fremde Bytes werden nicht übertragen oder zurückgeschrieben.

Erstfassungen von Bericht, Übergabe und Metadaten bleiben bytegleich als
`*-before-timing-correction.*` erhalten. Historische Laufdateien und ursprüngliche
Hunkdateien bleiben unverändert. Die alten `foreign-after-test_*.patch`-Namen
bezeichnen Deltas seit Testintegration; daraus folgt keine Lage nach allen Läufen.

Die erste Eindeutigkeitsprüfung des Einfügeskripts stoppte vor jedem
Dateischreiben; danach wurde nur dessen zeilengenauer Importanker berichtigt.
Eine spätere strenge Ganzdateiprüfung stoppte vor Ruff wegen der beschriebenen
fremden Testergänzungen. Beide sind historische Werkzeugvorbereitungen,
keine Testläufe und kein Gegenbeweis. Die drei Pytest-Läufe blieben sauber.

## Grenzen und offener Abschluss

Keine Aussage über tatsächliche Prozessabstürze, OS-Killlatenz,
Speichermangel, ENOSPC, SIGBUS, native Crashbereinigung, Linux/macOS,
Fenster, Renderer, Leistung oder Paketabnahme. Kein vollständiges Tor,
Commit oder Push wurde in dieser Einheit ausgeführt. Der unabhängige
Produktreview `REVIEW_PRODUCTION.md` gibt die eigenen Source-/Testhunks frei;
die Cacheentscheidung ist oben nachgetragen. Die früher nur angekündigten
14+19 wurden inzwischen getrennt auf der finalen gemeinsamen Basis geprüft,
wie im folgenden Nachtrag belegt. Ein zentrales vollständiges Tor und
tatsächliche Git-Integration dieser Einheit stehen weiterhin aus.

## SHA256 der finalen statischen Prüfung

Die folgenden Ganzdateihashes nennen unverändert den historischen Stand der
finalen statischen Prüfung, nicht den späteren lesenden Nachtrag. Die Übergabe ist ausschließlich hunkweise; fremde Änderungen in
den ganzen Dateien sind kein Bestandteil dieser Einheit.

| Datei | SHA256 |
|---|---|
| `app/core/geom/prepare.py` | `c8b8872d9981e2dd41ac95131d57d805ffcdd1c1a86f972dd25bc71756c7c08f` |
| `app/core/geom/difference.py` | `c639c3afd0ecd3d5f7e1c0a31d60516968d9f803609ae85b2497f2ba0596e76e` |
| `app/core/geom/hollow.py` | `fd57426dfe25ef132b6772c47cd35f1aa0f713870378f7ded9431873c2adeca6` |
| `app/core/geom/repair.py` | `df17e32fffc04d62ebc054931cd104dab0c4cc3d93fa244bce73b5e61ad98c70` |
| `app/core/ingest/threemf.py` | `f7f2d3ef6846a5fe9b4dc798bc9e41d5ebe9a50f8a68e13e9a525e2a7ed1dbf5` |
| `tests/test_prepare.py` | `d714522f2048fc07ab69bcb20bf3755ab82a99e4933d8712067945919f0a6f59` |
| `tests/test_difference.py` | `37f9d5dd216ae7797d36984c5ce874bfc0199dea0033db1f48e2327974a9c807` |
| `tests/test_missing_ops.py` | `f4c983c8a022b1f1da076c6db61343baff35acd3fbe716d574240238a1e554fe` |
| `tests/test_repair.py` | `3e248ddbb7ab09142519c57ec6e4e6393bed63ef70bd55008170ca30b8b0aaeb` |
| `tests/test_threemf_native_materials.py` | `e986dbecf67d8b6b0cc00d0497b96f68a430e66d5e84e839d9f90cc4e44dabe1` |

## Frischer finaler Anschlussnachlauf

Nach Ende des zentralen Merge-Tors und der abgestimmten Freigabe des
fremden RM424/B02-Testanhangs liefen beide Gruppen mit dem aktuellen
Repository-Interpreter erneut: **14 neue und 19 bestehende Fälle
bestanden, jeweils Exit 0, keine Testkörper-/Aufbau-/Abbaufehler oder
Skips**. Jede Gruppe hasht 16 Quellen, Tests und Korpusdateien vor/nach;
alle Hashes bleiben je Lauf und zwischen beiden Gruppen identisch.
Zusätzlich zum historischen Satz wird jetzt `geom/mesh.py` erfasst.

Das belegt auch die finale Entfernung des unbenutzten Reparaturimports
und die aktuelle fremde RM327-/B02-Basis. B02 hieß während der
Nachläufe vorläufig RM424; zentral wurde es wegen einer Nummerkollision
anschließend RM434 zugeordnet. Dafür änderte die fremde Sitzung danach
ausschließlich ihren B02-Testdocstring von RM424 auf RM434. Der aktuelle
Gesamthash ist `0c02e7546561024a0f7dff0d3888aea87e497bab1c41b86867264a8e7e5d64b5`.
Die lesende Rückersetzung genau dieser Kennung ergibt bytegenau den
tatsächlich gelaufenen 292d-Hash aus der Tabelle. Die eigenen c-Hunks
sind unverändert; es wurde kein neuer Geometrielauf nach dieser reinen
Docstringänderung behauptet. `b02-docstring-nachgang.json` und eine
bytegleiche örtliche Testkopie sichern den Lesestand. Historische
RM424-Bezeichnungen nennen den damaligen Stand.
Es ersetzt keine damalige
Zwischenstandskopie und schreibt deren Hashes nicht rückwirkend um.

| Im finalen Nachlauf erfasste Datei | SHA256 |
|---|---|
| `app/core/geom/repair.py` | `df17e32fffc04d62ebc054931cd104dab0c4cc3d93fa244bce73b5e61ad98c70` |
| `app/core/geom/mesh.py` | `0c4c56b6a1d8ff244c5db7f87f15ee837559bafce147f49dce86865c252ac978` |
| `tests/test_prepare.py` | `d714522f2048fc07ab69bcb20bf3755ab82a99e4933d8712067945919f0a6f59` |
| `tests/test_repair.py` | `3e248ddbb7ab09142519c57ec6e4e6393bed63ef70bd55008170ca30b8b0aaeb` |
| `tests/test_missing_ops.py` | `292d1be60b0c771a43927bea3f3aaaedfd5f8653bf5b03bd403a98bcdee5a0a7` |

Die neuen Originalbelege liegen als `final-after` und `final-existing`
jeweils mit `.txt`, `.xml` und `-result.json` im örtlichen Ordner
`tmp/review-seit-0.5.1-2026-10-01/rm298-weitergabe-20261002-7db5/`;
`run_final_cases.py` hält die genaue Auswahl fest. Die drei historischen
Läufe und die ursprünglichen Import-/Testintegrationsstände bleiben
unverändert erhalten.

Der unabhängige Produktionsreview `/root/rm298_lifecycle_tests` gibt
die sieben Fänge und die eigenen 14 Testfälle mit **JA** frei und
verfolgt den tatsächlichen Cacheanschluss bis zum versionsgebundenen
Ordner. `REVIEW_PRODUCTION.md` hat SHA256
`89565ad5bd60cc631311588cf7eb39a874b53e733304547a738f495ad00df59d`.
Auch der frische Nachlauf ist inzwischen unabhängig mit **JA**
freigegeben: `REVIEW_FINAL_RUNS_2026-10-02.md`, SHA256
`2c45cc9b12a462b1555aefc37f021fb89a5af7d51240a5f29263e615b48a862a`. Rohtext, JUnit, nativer Ausgang und alle
16 stabilen Dateien wurden lesend abgeglichen. Keine neue Cache-,
Paket- oder Betriebssystemprobe wird behauptet.
