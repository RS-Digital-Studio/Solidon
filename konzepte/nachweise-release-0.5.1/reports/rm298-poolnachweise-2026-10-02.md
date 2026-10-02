# RM-298(a): Besitzgrenze und Fehleranschluss der Hilfsprozesse

Stand: 02.10.2026. Dieser Bericht hält die tatsächlich integrierte Teilkorrektur fest. Die Ausgangsbefunde stehen in [review-hilfsprozess.md](review-hilfsprozess.md), der verbleibende Auftrag in [RM-298](../../../ROADMAP.md#rm-298).

## Integration

| Nachweis | Tatsächlicher Stand |
|---|---|
| Commit auf `origin/main` | `a45730c79f1d7ad6416d2bd1b6b68b5a0f24f311` |
| Ausgewählter Git-Baum | `bb7e4c4f4b43ec1d248791126330d936d38f4493` |
| Vollständiges Entwicklungstor vor der Integration | 19.033 bestanden, 62 übersprungen; Kernsammlung, Ruff, Format und mypy jeweils Exit 0 |
| Torgrenze | Keine Fenster-, Renderer-, Erzeugnis- oder Leistungsabnahme |
| Ausgewählte Flächen | `kernel_process.py`, eigene Poolfälle in `test_kernel_process.py`, Poolabsatz der Geometriekarte, eine neue Fehlermeldung je Katalog und RM-298-Teilstand |
| Unabhängige Prüfung | Eigenreview, unabhängiges Quell-/Nachweisreview und zentrales Anschlussreview; beide zentral gefundenen Nachgänge samt späteren Rückfalllücken behoben |

Nach der Integration wurden lokaler Hauptzweig, `origin/main` und der tatsächliche Remote-Hauptzweig getrennt abgefragt. Am Nachweisstand `4449e33702339b92fd8723da9b123ebf795674d3` ist der Teilcommit bereits enthalten; der Hauptindex war leer. Weitere parallele Änderungen gehören nicht zu dieser Freigabe.

## Korrektur und Kundenwirkung

Ein reservierter Start zählt schon vor dem tatsächlichen Kindprozess. Ein beendeter Auftrag gibt seinen Platz erst nach bestätigtem Prozessende frei. Auch fehlgeschlagenes Aufräumen während des Starts, noch lebende Kinder nach `join` und parallele Stopversuche behalten ihren Besitzplatz. Dadurch bleibt `MOST_HELPERS = 3` eine wirkliche Obergrenze für laufende, startende und noch nicht bestätigte Stopversuche.

Shutdown nimmt offene Starts mit, gibt seine Schließsperre auch bei einem Fehler frei und trennt alte Rückgaben und bleibende Absagen von einer neuen Generation. Ein fehlgeschlagener Stop bleibt wiederholbar. Der Windows-Jobgriff wird erst nach bestätigtem Kindende freigegeben.

Ein nicht beendbarer Helfer erzeugt `KernelHelperStopError` mit einer übersetzten Handlungsanweisung: Projekt speichern, Solidon neu starten und bei erneutem Auftreten einen Fehlerbericht erstellen. Die geerbten Handlungen sind tatsächlich vorhanden. Eine technische PID steht ausschließlich im Protokoll; sie wird nicht als unbeschrifteter Kundenwert ausgegeben.

Auch wenn der Vorabstart im echten `_ImportWarmup`-Worker den Fehler protokolliert, meldet die nächste öffentliche `run`-Anfrage den noch offenen Stopfehler vor jeder lokalen Rechnung. Dasselbe gilt nach wartender Platzsuche, stummer Antwort und bleibender Absage eines anderen Helfers. Alle vier lokalen Rückfallstellen prüfen den Besitzfehler. Erfolgreiches Aufräumen hebt die Sperre auf. Ein harmloser optionaler Import- oder sauber abgewickelter Startfehler behält den normalen lokalen Rechenweg.

## Tatsächlich ausgeführte Teilprüfung

Ausgeführt mit CPython 3.14.7 des Arbeitsbaums:

```text
.venv/Scripts/python.exe -m pytest -q tests/test_kernel_process.py tests/test_value_labels.py::test_every_value_key_has_a_label -m "not windowed and not performance" --tb=short
```

Ergebnis des abschließenden Nachgangs: **80 bestanden, 0 fehlgeschlagen, 0 Fehler, 0 übersprungen, 1 Fenstertest abgewählt, Exit 0**. Davon sind 79 Kernel-Entwicklungsfälle und der unveränderte Beschriftungswächter. Die 33 neu hinzugefügten kontrollierten Pool-/Sprach-/Warmupfälle gliedern sich wie folgt:

| Umfang | Reproduzierbare Fälle in `tests/test_kernel_process.py` |
|---|---|
| 12 ursprüngliche Pool-/Leitungsfälle | `test_pool_pending_starts_use_a_slot`, `test_pool_ending_helpers_keep_their_slot`, `test_pool_failed_starts_release_the_reservation`, `test_pool_constructor_failure_closes_the_child_and_both_pipes`, `test_pool_shutdown_collects_a_still_starting_helper`, `test_pool_shutdown_does_not_reinsert_a_late_return`, `test_pool_closed_wait_is_a_lost_helper_error` |
| 6 weitere Besitz-/Stopfälle | `test_pool_failed_stop_keeps_ownership_and_can_be_retried`, `test_pool_join_returning_with_a_live_child_does_not_free_its_slot`, `test_pool_parallel_shutdown_retries_after_a_failed_stop`, `test_pool_old_refusal_does_not_disable_a_new_generation`, `test_pool_failed_constructor_cleanup_keeps_the_live_child` |
| 6 tatsächliche Sprachfassungen | `test_pool_stop_error_has_translated_detail_and_an_action` mit installierten DE-/EN-/ES-/FR-/IT-/PT-Katalogen |
| 4 Warmup-Anschlüsse | `test_pool_warmup_stop_error_reaches_the_next_kernel_request`: Konstruktor-/Bereitfehler, danach Haupt-/Nebenfaden; keine Widget-Erzeugung |
| 2 harmlose Warmup-Kontrollen | `test_pool_harmless_warmup_failure_keeps_the_local_kernel_path`: optionaler Import und sauberer Startfehler |
| 1 wartende Platzsuche | `test_pool_waiting_kernel_request_keeps_a_new_stop_error_visible` |
| 2 Rückfälle während eines anderen Stopfehlers | `test_pool_call_fallback_keeps_another_helpers_stop_error_visible`: stumme Antwort und bleibende Absage |

Die vorhandenen echten Prozess-, Speicherübertragungs-, Abbruch- und Bitgleichheitsfälle liefen ebenfalls. Der Abschlusslauf ist kein Ersatz für die früheren negativen Gegenläufe: Vor den jeweils zugehörigen Korrekturen waren 10 ursprüngliche und 6 zusätzliche Reviewfälle rot; die PID-/Warmup-Anschlüsse zeigten jeweils 4 echte Fehler, die wartende Anfrage 1 und die beiden Antwort-Rückfälle 2. Die 2 harmlosen Warmup-Kontrollen bestanden schon vor diesem Anschlussfix. Diese benannten Gegenläufe hatten keine Setupfehler. Eine zwischenzeitliche fehlerhafte Sprach-Testvorbereitung wurde separat korrigiert und zählt nicht als Produktgegenbeweis.

Quell- und Testhashes blieben während des abschließenden Laufs identisch und stimmen am Integrationsnachweis noch:

| Datei | SHA-256 |
|---|---|
| `app/core/geom/kernel_process.py` | `9a265c6d9e087dd8626e8e9458db9233867098b5cea32c4acc1bd01e025dfbea` |
| `tests/test_kernel_process.py` | `6c4d432f1d931bd48d08d797eac703a862af2462c17869f01a5e4ad434441f1e` |

Ruff, Formatprüfung und Diffcheck waren im Nachgang jeweils Exit 0. Das zentrale Volltor prüfte anschließend den exakt montierten Stand mit allen vier Entwicklungstor-Ergebnissen.

## Grenze der Freigabe

Dieser Nachweis schließt **RM-298(a)**. Er schließt nicht den Gesamtpunkt. POSIX-Speicherbesitz/ENOSPC/SIGBUS (b), die restlichen breiten Ausnahmefänge (c), aktive Elternbindung/OS-Priorität und wirkliche Release-Leistungsmessungen (d), `evaluate_now`-Abbruch (e) sowie die Paketrauchtestfrist (f) brauchen ihre eigenen Nachweise.

Insbesondere bestätigt der alte Eltern-Endetest nur ein untätiges Kind. Er belegt keinen Jobobjekt-Abbau während laufender Arbeit. Die bestehenden Hauptfaden-Leistungsmarken belegen keine Auslagerung. Linux, macOS und das gebaute Paket wurden in dieser Entwicklungsprüfung nicht ausgeführt.
