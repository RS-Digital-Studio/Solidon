# Durchsicht RM-212 — Hilfsprozess für große manifold3d-Aufrufe

Geprüft: Zweig `origin/rm-212-hilfsprozess`, Endstand `48f5231c3`, Basis `aa82afdff`
(33 Dateien, +2715/−399), jede geänderte Zeile gelesen. Eigener Arbeitsbaum
`F:\3D Druck.review-051\wt-revhp` (detached auf `48f5231c3`, nach der Durchsicht
entfernt). Alle Läufe gebunden (`FFFFF0FF`), Protokolle unter
`F:\3D Druck.review-051\laeufe\rev-hp-*.txt`. Sonden und ihre Ergebnisse gesichert unter
`F:\3D Druck.review-051\sonden\review-hilfsprozess\` (`test_review_hp_probe.py` ist ein
Testmodul für einen Arbeitsbaum auf `48f5231c3`, nicht zum Einchecken).

## Urteil

**Mergebar: ja.** Nichts davon macht `main` für den normalen Gebrauch schlechter als
die Basis: Bitgleichheit, echtes Abbrechen, Jobobjekt und die niedrigere Priorität halten
unter Windows, auch im gebauten Paket. **Vor dem Tag sind B1 bis B4 zu beheben.**
**Der Tag-Lauf braucht einen Rauchtest des Hilfsprozesses** (B1): Kein CI-Schritt startet
das gebaute Paket, auf macOS und Linux ist der Hilfsprozess im Paket nie gelaufen.

**Stand nach dem Nachtrag `2e832f605`: B1 bis B4 behoben** — siehe Abschnitt
„Nachtrag 2e832f605“ am Ende.

## Ausgeführt

| Lauf | Ergebnis |
|---|---|
| `rev-hp-1` — `tests/test_kernel_process.py` ohne Fenster | 30 passed, 1 deselected (Fenstertest) |
| `rev-hp-skipcount` — Sammlung `tests/test_slice_core.py` | 23 Tests |
| `rev-hp-probe-1` bis `-4` — Sonden (`test_review_hp_probe.py`) | siehe Befunde |
| `rev-hp-frozen-temp` — gebautes `Solidon3D.exe` des Pakets (`sonden/hilfsprozess/eingefroren/voll/dist`) dreimal als Hilfsprozess | je Start ein Temp-Ordner, alle drei bleiben liegen, Ausgang −15 |
| `rev-hp-shm-commit` — gemeinsamer Speicher über der Zusage | `OSError` WinError 1455 bzw. 8, kein `MemoryError` |
| `rev-hp-start-imports`, `rev-hp-start-window2` — Start, Basis gegen Endstand, im Wechsel | siehe N6 |
| `rev-hp-mut-*` — Gegenproben | siehe Abschnitt Testqualität |

`rev-hp-start-window` ist ungültig und nur der Vollständigkeit halber erwähnt: Der Treiber
lag im Scratchpad, `import app` kam dort über die editierbare Installation aus dem
Hauptbaum (siehe Nebenbefund).

## Befunde, die vor dem Tag behoben werden

### B1 — Der Hilfsprozess im gebauten Paket ist auf macOS und Linux nie gelaufen, und kein CI-Schritt startet das Paket

- **Beleg:** `.github/workflows/build.yml`, Job `package` (Zeilen 333–662): PyInstaller,
  Stückliste, Lizenzbeilage, Bundle-Struktur (`test -x`, `plutil -lint`), Pakete — gestartet
  wird das gebaute Programm nirgends. `linux-release-check` (664–762) packt das AppImage nur
  für die Stückliste aus. Der Paketbericht schreibt dagegen „Erst der CI-Paketlauf belegt
  macOS (`.app`) und Linux (AppImage, Flatpak)“ (`hilfsprozess.md` §4,
  `hilfsprozess-schluss.md` §7) — diesen Beleg gibt es nicht.
- **Was belegt ist:** Windows, zweifach — ein Minimalpaket mit dem Kopf von `app/ui/app.py`
  (eingefrorener Eltern- und Kindprozess, `einstieg.py`) und das echte Paket als Kind
  (`voll_treiber.py`, `voll-bericht.json`: Prozessbild `Solidon3D.exe`, bitgleich, keiner übrig).
- **Warum es trotzdem gehen sollte:** PyInstaller 6.22.2 ersetzt `multiprocessing.freeze_support`
  unabhängig von der Startmethode (`pyi_rth_multiprocessing.py`, auch bei Linux' Vorgabe
  `forkserver`) und leitet den `resource_tracker`-Start über die Interpreter-Flags um, die
  Eltern- und Kindprozess desselben Binärs teilen; die Anwendung fasst weder
  `sys.warnoptions` noch `sys._xoptions` an. `sys.executable` ist in der `.app`
  `Contents/MacOS/Solidon3D`, im AppImage der Pfad im eingehängten Abbild, im Flatpak der
  Pfad im Sandkasten — alle drei startbar, solange der Elternprozess lebt. Die Signatur
  (`codesign --deep --options runtime`, ohne `--entitlements`, also ohne App Sandbox) deckt
  dasselbe Binär; `shm_open` ist erlaubt.
- **Warum ein Rauchtest nötig ist:** Scheitert der Weg dort doch (Bundle-Layout, fehlendes
  Modul im PYZ, Laufzeithaken), wartet der erste große Schritt bis zu 30 s und rechnet danach
  wie vor RM-212; im schlechtesten Fall — ein Kind, das `freeze_support` nicht umleitet —
  startet es eine zweite Anwendung samt Fenster, bis es nach 30 s beendet wird.
- **Fix (klein):** `tools/check_frozen_helper.py <dist>` nach dem Muster von
  `sonden/hilfsprozess/eingefroren/voll_treiber.py`, portabel:
  1. Programm und Paketpfade suchen: Windows `dist/Solidon3D/Solidon3D.exe` + `_internal`,
     Linux `dist/Solidon3D/Solidon3D` + `_internal`, macOS
     `dist/Solidon3D.app/Contents/MacOS/Solidon3D` + `Contents/Frameworks`.
  2. Unter POSIX zuerst `multiprocessing.resource_tracker.ensure_running()` — der
     Aufräumprozess muss aus dem Python der CI kommen, sonst stimmen die Flags für die
     Umleitung im Paket nicht.
  3. `kernel_process._CONTEXT.set_executable(exe)`, während `warm_up()` `sys.frozen = True`
     und `sys.path` = Paketpfade, `STARTUP_SECONDS = 60`, `TEMP`/`TMPDIR` auf einen leeren Ordner.
  4. Verlangen: bereit; ein `boolean` aus einem Nebenfaden mit `OFFLOAD_ABOVE = 0`, Bytes
     gleich der Rechnung im Prozess; `shutdown()`, Hilfsprozess beendet, keiner übrig; der
     Temp-Ordner danach leer (hält B4).
  5. Schritt „Hilfsprozess im Paket starten“ im Job `package` direkt nach „Bauen“, auf allen
     vier Runnern, `timeout-minutes: 5`; ein Wächter in `tests/test_packaging.py`, dass der
     Schritt da ist.
  Grenze: Das belegt die Kind-Seite des Pakets (Einstieg, `freeze_support`, Laufzeithaken,
  PYZ, Bundle-Layout), nicht den eingefrorenen Elternprozess unter POSIX und nicht den
  Flatpak-Sandkasten. Die Eltern-Seite ist unter Windows durch das Minimalpaket belegt.

### B2 — Kann der Hilfsprozess eine Rechnung nicht annehmen, fällt sie nicht zurück; Speichermangel kommt als roher `OSError` statt als Speicherhinweis

- **Beleg im Code:** `app/core/geom/kernel_process.py:208` — `kernel_jobs.pack(arrays)` steht
  vor dem `try`; `:210` — `connection.send` ungeschützt; `:220–223` — eine Fehlerantwort des
  Hilfsprozesses *vor* „accepted“ (er konnte den Speicher nicht öffnen) wird als dessen
  Ausnahme geworfen. Alle drei heißen „der Hilfsprozess hat die Rechnung nicht“; `run()`
  (`:477`) reicht sie über `except BaseException` roh durch. `app/core/geom/kernel_jobs.py:655`
  — `pack(result)` im Hilfsprozess steht außerhalb jedes `try`.
- **Nachgestellt** (`rev-hp-probe-1`, `-4`, `rev-hp-shm-commit`):
  - Speicher im Elternprozess nicht anlegbar → roher `OSError` statt Rechnung im Prozess.
  - Hilfsprozess kann den Speicher nicht öffnen → roher `PermissionError`.
  - Untätiger Hilfsprozess zwischen `alive`-Blick und Senden gestorben → roher
    `BrokenPipeError: [WinError 232]`.
  - Windows sagt einen gemeinsamen Speicher nicht zu → `OSError` WinError 1455 bzw. 8,
    **kein `MemoryError`**. Damit greifen `except MemoryError` in `mesh_ops.remesh` (`:1243`),
    `uniform` (`:1469`) und `subdivided` (`:1509`) auf dem Hilfsprozess-Weg nicht:
    `uniform` bringt roh `OSError: [WinError 1455] …` statt `_out_of_memory` mit Vorschlag;
    die Auswertung macht daraus „Im Programm ist ein unerwarteter Fehler aufgetreten“ mit
    technischem Detail. Genau der Fall, für den RM-212 gebaut ist: große Netze, knapper Speicher.
  - Kein Platz für das Ergebnis im Hilfsprozess → er stirbt an einer unbehandelten Ausnahme
    aus `serve`, der Kunde liest `KernelHelperLostError` statt des Speicherhinweises.
- **Im Windows-Paket zusätzlich (abgeleitet, nicht am Paket nachgestellt — es hätte ein
  Fenster auf dem Arbeitsplatz geöffnet):** Ein Kind einer Fensteranwendung ohne
  Standardgriffe hat `sys.stderr = None`; `multiprocessing.process.BaseProcess._bootstrap`
  (Python 3.14.7) schreibt eine unbehandelte Ausnahme ungeschützt nach `sys.stderr`, der
  `AttributeError` läuft aus `spawn_main` bis in den Einstieg, und PyInstallers
  Fensterstarter zeigt dann seinen Traceback-Dialog (`disable_windowed_traceback` ist in der
  Spec nicht gesetzt). Neben der Meldung der Anwendung stünde ein Python-Traceback auf dem
  Schirm.
- **Fix:** (a) `kernel_jobs.pack`: ein `OSError` beim Anlegen mit WinError 1455/8 oder
  `errno` ENOMEM/ENOSPC als `MemoryError` weitergeben (`raise MemoryError(...) from problem`);
  (b) `_Helper.call`: `pack` und `send` in den `try`; ein `OSError` dort oder eine
  Fehlerantwort vor „accepted“ ist ein eigener Fall (etwa `_HelperRefusedError`), den `run()`
  wie `_HelperSilentError` behandelt — beenden, `fallback` zählen, hier rechnen; bei
  Speicherfehlern des gemeinsamen Speichers den Vorrat für die Sitzung abschalten;
  (c) `serve`: `pack(result)` und jedes `send` fangen, einen tragbaren `MemoryError`
  zurückmelden, und nichts aus `serve` entweichen lassen (äußerstes
  `except BaseException: os._exit(1)`); (d) die vier Sonden als Tests übernehmen.

### B3 — Die Boolesche Kette verschluckt `KernelHelperLostError` und startet den Hilfsprozess noch zweimal

- **Beleg:** `app/core/geom/boolean.py:223` — `except Exception` je Stufe lässt nur
  `OperationCancelled` (`:212`) und `PROGRAMMING_ERRORS` durch. Sonde
  `test_probe_the_boolean_chain_stops_at_a_lost_helper` (`rev-hp-probe-2`): Hilfsprozess stirbt
  in jeder `boolean`-Rechnung → „verloren 3, gestartet 3“, Ergebnis aus der Stufe **voxel**,
  keine Meldung. In der Vorschau (`DRAFT_CHAIN`, zwei Stufen) endet derselbe Fall mit
  `BooleanFailedError` „Häufig ist das Modell an einer Stelle offen — dann hilft Reparieren“.
- **Warum es zählt:** Der Docstring von `KernelHelperLostError` und die Regel in `kern.md`
  („Ein toter Hilfsprozess ist `KernelHelperLostError` (Regel 17)“) versprechen, dass der
  Schritt mit diesem Satz anhält; der Schlussbericht verspricht dem Kunden „Stürzt der Kern …
  ab, bleibt Solidon offen und sagt es“. Für die häufigste große Rechnung — jede Bohrung,
  jeder Schnitt — stimmt das nicht: Stirbt der Hilfsprozess am Speicher (Linux-OOM), bekommt
  er dieselbe Last noch zweimal, danach rechnet die Voxelstufe im Prozess der Anwendung.
- **Fix:** in `boolean.boolean` neben `OperationCancelled` auch
  `kernel_process.KernelHelperLostError` durchreichen; in `kern.md` den Satz über breites
  Fangen um `KernelHelperLostError` ergänzen; die Sonde als Test.

### B4 — Jeder Hilfsprozess des Pakets lässt einen Ordner in `%TEMP%` zurück

- **Beleg:** Das Paket trägt den Laufzeithaken `pyi_rth_mplconfig`
  (`sonden/hilfsprozess/eingefroren/voll/build/solidon3d/PKG-00.toc`); er legt beim Start
  jedes Prozesses mit `secure_mkdtemp` einen Ordner an und räumt ihn in `atexit` weg.
  `_Helper.stop` (`kernel_process.py:278`) beendet jeden Hilfsprozess hart — auch einen
  untätigen beim Beenden der Anwendung (Sonde `test_probe_shutdown_lets_an_idle_helper_end_by_itself`:
  Ausgang −15). `rev-hp-frozen-temp` mit dem gebauten `Solidon3D.exe`: drei Starts, drei Ordner
  `tmp…`, alle bleiben.
- **Warum es zählt:** Je Sitzung mindestens einer, dazu einer je abgebrochener Vorschau
  (Abbrechen beendet den Hilfsprozess) und je verworfenem zweiten Hilfsprozess — auf Dauer
  Hunderte leere Ordner im Profil des Kunden.
- **Fix:** Am Anfang von `serve` im eingefrorenen Paket den eigenen `MPLCONFIGDIR` entfernen
  (der Hilfsprozess lädt nie matplotlib; der Wert ist der des Kindes, der Haken überschreibt
  den geerbten); zusätzlich in `stop` einem untätigen Hilfsprozess nach dem Schließen der
  Leitung eine halbe Sekunde zum eigenen Ende geben. Nachweis im Rauchtest (B1, Temp-Ordner leer).

## Befunde nach 0.5.1

### N1 — `MOST_HELPERS` hält nicht

`kernel_process.py:336–348`: Die Prüfung `len(self._busy) < MOST_HELPERS` und das Eintragen
liegen auf zwei Seiten eines freigegebenen Schlosses, dazwischen startet `_Helper()` den
Prozess. Sonde `test_probe_at_most_three_helpers_live_at_once` (sechs Fäden, Start 0,5 s):
**sechs Hilfsprozesse zugleich** bei einem Deckel von drei. Jeder hält eine Kopie des Netzes
und seinen Arbeitsspeicher. **Fix:** einen Startplatz unter dem Schloss reservieren
(Zähler `_starting` in der Deckelprüfung, nach dem Eintragen oder Scheitern zurück); die
Sonde als Test.

### N2 — Unter Linux und macOS bleibt gemeinsamer Speicher nach einem Absturz oder Abbruch liegen

`track=False` (`kernel_jobs.py:486`) nimmt den Aufräumprozess heraus; aufgeräumt wird nur
auf den glatten Wegen. Nicht gedeckt: (1) Absturz des Elternprozesses — den Eingang gibt nur
sein `finally` frei (`kernel_process.py:216–219`); der Hilfsprozess rechnet zu Ende, packt
das Ergebnis, `connection.send(("done", …))` (`kernel_jobs.py:657`) wirft `BrokenPipeError`
ohne Fang, der Ergebnisspeicher bleibt ebenfalls — beides in `/dev/shm` bis zum Neustart;
(2) Abbrechen, während der Hilfsprozess sein Ergebnis schon angelegt hat — er wird beendet,
der Name ist dem Elternprozess unbekannt. Die Docstrings von `pack` (`:470–473`, „der
Empfänger nimmt unter POSIX den Namen weg, sobald er ihn geöffnet hat“ — der Hilfsprozess tut
das mit dem Eingang nie) und `copied` (`:512–515`, „stirbt einer von beiden, bleibt kein
Speicher liegen“) sagen anderes. Ein rechnender Hilfsprozess überlebt unter AppImage und deb
einen Absturz, bis sein Kernaufruf endet (so dokumentiert); im Flatpak nimmt der
PID-Namensraum ihn mit. Unter Windows kein Befund (Griffe, Jobobjekt). **Fix:** Eingang
gleich nach „accepted“ freigeben; Ergebnisnamen vom Elternprozess vorgeben, damit er nach
einem Abbruch aufräumen kann; in `serve` fehlgeschlagenes Senden fangen und `out.unlink()`;
unter Linux im Hilfsprozess `prctl(PR_SET_PDEATHSIG, SIGKILL)`; Docstrings nachziehen.
Prüfbar in der Linux-Suite der CI (Elternprozess im Rechnen töten, `/dev/shm/psm_*` leer).

### N3 — Die Umgebung wird im laufenden, mehrfädigen Elternprozess umgeschrieben

`kernel_process.py:141–159` setzt und entfernt `OPENBLAS_NUM_THREADS` in `os.environ` um
jeden Start, während Qt-, Render- und Arbeiterfäden laufen. Unter glibc und macOS sind
`setenv`/`unsetenv` gegen gleichzeitiges `getenv` in nativen Fäden nicht fadensicher; das
Schloss schützt nur zwei Starts voreinander. Windows ist nicht betroffen. **Fix:** den Wert im
Hilfsprozess setzen, bevor `numpy` lädt — ein kleines Zielmodul, das die Variable setzt und
dann `kernel_jobs` importiert; im Paket lädt vor dem Entpacken des Ziels nichts `numpy`
(nur `app.ui` und `app.core.log`).

### N4 — Rückfall: bis zu 30 s ab Start, nicht überall abbrechbar; „nimmt nicht an“ schaltet nicht ab

Die Aussage stimmt so: Kommt der Hilfsprozess gar nicht hoch (Startfehler, Tod vor „ready“),
fällt die Rechnung sofort zurück und die Sitzung rechnet ohne ihn; hängt er, wartet jeder
große Schritt, der in dieser Zeit kommt, bis `started + STARTUP_SECONDS` (30 s ab dem Start
des Hilfsprozesses, nicht je Aufruf), dann rechnet er hier. Der Kunde sieht in dieser Zeit
den laufenden Schritt, ab 2 s Balken und *Abbrechen*, ohne Fortschritt. Abbrechen wirkt nur,
wo ein Token hineinreicht (Auswertung, Vorschau, Verringern, Angleichen, Unterteilen,
Boolesche), nicht bei `face_components` (Laden, Erkennung), `surface_gap`, `refined`,
`_without_scars` und der Anzeige-Dezimierung. Für einen Fehlerfall vertretbar. Dazu:
`_HelperSilentError` (keine Annahme in 10 s, `:458`) schaltet den Vorrat nicht ab — jede
weitere große Rechnung kann dann 10 s plus Start warten. **Vorschlag:** auf einen nicht
bereiten Hilfsprozess höchstens wenige Sekunden warten und hier rechnen, während er
weiterstartet; „nimmt nicht an“ wie einen Fehlstart zählen.

### N5 — `shutdown` während einer laufenden Rechnung wirft im wartenden Faden einen rohen `OSError`

`kernel_process.py:262`: `multiprocessing.connection.wait` steht außerhalb des
`try … except (EOFError, OSError)`. Schließt `shutdown()` die Leitung aus einem anderen
Faden, wirft `wait` unter Windows „handle is closed“ (kein `winerror`, also neu geworfen).
Nur beim Beenden der Anwendung. **Fix:** `wait` in denselben `try`.

### N6 — Der Ladebildschirm erscheint rund 0,24 s später

`app/ui/app.py:54` importiert `kernel_process` auf Modulebene; `kernel_jobs` zieht `numpy` und
`manifold3d` nach — vor `main()` und damit vor dem Ladebildschirm. Im Wechsel gemessen, unter
Last: `import app.ui.app` 0,80 s (Basis, Median aus 5) → 1,05 s (Endstand), Basis ohne,
Endstand mit `numpy`/`manifold3d` (`rev-hp-start-imports`). Die Zeit bis zum bedienbaren
Fenster bleibt im Rauschen (Median 3,63 → 3,75 s aus je 8, `rev-hp-start-window2`), weil beide
Bibliotheken auch in der Basis vor dem Fenster geladen werden. **Fix:** `kernel_process` erst in
`_ImportWarmup.work` und unmittelbar vor `aboutToQuit.connect` importieren.

### N7 — Testqualität: drei Zusagen ohne Wächter, eine Karte sagt zu viel

- `test_a_helper_ends_with_a_parent_that_is_killed` (`tests/test_kernel_process.py:574`) bleibt
  **grün mit abgeschaltetem Jobobjekt** (`rev-hp-mut-job`): Ein untätiger Hilfsprozess endet
  schon am Ende der Leitung. Die Sonde mit einem *rechnenden* Hilfsprozess ist ohne Jobobjekt
  rot (`rev-hp-mut-job2`), mit grün (`rev-hp-mut-job3`) — sie gehört in die Suite; der
  Paketbericht nennt den alten Test als Träger von `process.py`.
- Die niedrigere Priorität hat keinen Test: `_yield_to_the_window` abgeschaltet, die Datei
  bleibt grün (`rev-hp-mut-4`). Sie wirkt (Sonde `GetPriorityClass == 0x4000`, `rev-hp-probe-3`);
  ein Test fragt unter Windows `GetPriorityClass`, unter POSIX `os.getpriority`.
- `warm_up` in `_ImportWarmup` und `shutdown` an `aboutToQuit` sind nur in `app.py`
  eingelöst und nirgends geprüft (Regel „Anschluss“).
- Die Leistungsprüfungen aus §31 (`tests/test_performance.py`) rechnen alle im Hauptfaden,
  also nie im Hilfsprozess — der Weg des Kunden an großen Netzen hat seit RM-212 kein Budget.
  Eine Marke gehört über einen Nebenfaden gerechnet (etwa die grobe Vorschau der Lochplatte);
  die Dauer auf ruhiger Maschine ist laut Schlussbericht ungemessen.
- `tests/CLAUDE.md:64` verspricht „bei einem harten Ende des Elternprozesses und im
  eingefrorenen Paket richtig“; der Test prüft einen untätigen Hilfsprozess und den Quelltext
  von `app.py` und Spec, nicht das Paket.

### N8 — Begründungen, die der Code oder die eigene Messung nicht tragen

- `app/core/scene/hashing.py:137–151` (`_index_bytes`): „`np.asarray` prüft jede Zahl einer
  Liste einzeln … am Stück und unter dem GIL“ — `array("q", liste)` tut dasselbe in einer
  C-Schleife unter dem GIL; die eigene Tabelle des Pakets zeigt 107 → 115 ms Stillstand. Die
  Bytes sind dieselben (Sonde `test_probe_the_bookkeeping_helpers_are_equivalent`). Docstring
  auf „dieselben Bytes, kein Stillstandsgewinn“ zurückführen oder zur einfachen Form zurück.
- `kernel_jobs.pack`/`copied` (siehe N2), Paketbericht zur CI (siehe B1), `kern.md` zu
  `KernelHelperLostError` (siehe B3).
- Der Preis der niedrigeren Priorität ist nur unter Windows gemessen; auf Apple Silicon
  (Effizienzkerne) und Linux ist er offen.

## Regeln (Durchgang `/regelcheck`)

- **Regel 1:** `kernel_jobs`, `kernel_process`, `process.bind_helper` ohne Qt; der
  Hilfsprozess lädt aus dem Kern nur `app.core`, `app.core.geom`, `kernel_jobs` (Test). Kein Verstoß.
- **Regel 3:** Eingangsfelder werden nur gelesen (`np.asarray`, `np.copyto` in den Speicher,
  `Mesh64` kopiert). Kein Verstoß.
- **Regel 6:** `Mesh64`, `float64`, Vergleich Byte für Byte. Kein Verstoß.
- **Regel 10/11:** Kein `eval`; `JOBS` ist die Liste des Ausführbaren; `pickle` nur zwischen
  eigenen Prozessen über eine Leitung, die kein Dritter erreicht (Windows: benannte Leitung
  mit einer einzigen, sofort belegten Instanz; POSIX: `socketpair`); Netzdaten aus Dateien
  reisen nur als rohe Zahlen durch den gemeinsamen Speicher, nie durch `pickle`. Kein Verstoß.
- **Regel 17:** `KernelHelperLostError` trägt Detail und die Vorschläge von `InternalError`.
  Verstöße in der Sache: rohe `OSError`/`PermissionError`/`BrokenPipeError` (B2, formal von der
  Auswertung in `InternalError` mit technischem Detail gefasst) und der verschluckte Satz in
  der Booleschen Kette (B3).
- **Regel 20:** neuer Text über `_()`, in allen fünf Katalogen, Begriff „Fehlerbericht“ wie im
  Bestand übersetzt. Kein Verstoß.
- **Regel 22:** keine neue Abhängigkeit (`multiprocessing` ist Standardbibliothek).
- Regeln 2, 4, 5, 7–9, 12–16, 18, 19, 21: vom Paket nicht berührt, nicht geprüft.

## Richtigkeit — geprüft ohne Befund

- **Bitgleich je Rechnung:** Jede der elf Rechnungen in `JOBS` bildet den alten Code Schritt
  für Schritt nach (gelesen gegen `aa82afdff`: Anzeige-Dezimierung samt Splittern, `simplify(0)`,
  Bisektion, konformes Teilen samt `too_many` und Herkunft, `refined`, `uniform`, `subdivided`,
  Boolesche samt `native_contact`, Narben, Abstand, Zusammenhang); einzige Abweichung
  `np.require(…, ("C", "W"))` statt `np.asarray` — gleiche Werte, nur ohne den alten
  `TypeError` an schreibgeschützten Feldern. Die Suite verlangt je Rechnung dieselben Bytes hier
  und im Hilfsprozess; `face_components` auch ohne jede Nachbarschaft gleich trimesh (Sonde).
- **Die Buchhaltung:** `_in_order` = `tuple(sorted(…))`, `python_values` = `tolist()`,
  `fsum` gleich, `_index_bytes` = alte Bytes, `_fed` gibt 16 verschiedenen Werten 16 Abdrücke
  (Sonde über Stückgrenzen, Duplikate, unsortiert); `_numbered` sortiert nach demselben
  Schlüssel; `_mesh_key` gestreamt, dieselben Bytes.
- **Cache-Schlüssel und Kette:** `feature_digest` hasht dieselben Bytes; die Stufe steht wie
  vorher in `solver`; ein Abbruch in einer Stufe beendet die Kette (`:212`).
- **Einstieg:** `freeze_support()` ist der erste Aufruf; davor laufen nur `import app.ui`
  (Umgebungsvariable), der Import von `app.core.log` und die PyInstaller-Haken. Kein zweites
  Fenster, kein Eintrag in „Zuletzt geöffnet“, keine Freischaltprüfung, kein Autosave im Kind.
  Aus dem Quellbaum lädt `spawn` `app.ui.app` als `__mp_main__` (nur Entwicklung, benannt).
- **Jobobjekt:** beendet unter Windows auch einen rechnenden Hilfsprozess mit dem
  Elternprozess (Sonde grün, ohne Jobobjekt rot).
- **Abbrechen** beendet den rechnenden Hilfsprozess (Gegenprobe rot, siehe unten).
- **Zurückgenommen:** Die Vermutung, ein `MemoryError` beim Kopieren in `copied` werde von
  einem `BufferError` aus `segment.close()` verdeckt, ist widerlegt — numpy gibt den Puffer
  gleich beim Anlegen der Sicht frei (Sonde grün).

## Testqualität — Gegenproben

| Mutation (je im Arbeitsbaum, danach zurückgenommen) | Tragender Test | Ergebnis |
|---|---|---|
| `bind_helper` tut nichts | `test_a_helper_ends_with_a_parent_that_is_killed` | **grün** — bewacht das Jobobjekt nicht (N7) |
| dasselbe | Sonde mit rechnendem Hilfsprozess | rot; ohne Mutation grün |
| `install_crash_logging()` vor `freeze_support()` | `test_the_entry_point_hands_a_helper_start_to_freeze_support_first` | rot |
| Abbruch gibt den Hilfsprozess zurück statt ihn zu beenden | beide Abbruchtests | rot |
| `STARTS_BEFORE_GIVING_UP = 2` | `test_a_helper_that_never_starts_falls_back_to_this_process` | rot |
| `_yield_to_the_window` tut nichts | ganze Datei | **grün** — ungeprüft (N7) |

Die übrigen Tests prüfen Wirkung mit Sollwert von außen (trimesh als Referenz des
Zusammenhangs, Rechnung im Prozess als Referenz der Bytes, echte Prozesse für Tod, Stille,
Abbruch). `test_cancelling_a_real_kernel_call_in_the_helper` hängt an der Zeit (Abbruch nach
1 s, 32 `simplify`-Läufe an 327 680 Dreiecken) — auf einer sehr schnellen Maschine könnte die
Bisektion vorher fertig sein.

## 36 statt 59 übersprungen — geklärt

Die 23 Tests von `tests/test_slice_core.py` überspringen sich, wenn der kompilierte
Schichtkern fehlt (`pytestmark = skipif(analysis._chain is None …)`). `wt-hilfsprozess` und
`wt-bohren` tragen `app/core/slice/_chain.cp314-win_amd64.pyd` (für den PyInstaller-Bau aus dem
Hauptbaum kopiert) und melden 36; `wt-3mf`, `wt-stapel` u. a. tragen ihn nicht und melden 59.
Kein Befund am Paket — sein Tor lief vollständiger.

## Kundensicht

Vorher stand das Fenster an großen Modellen, Abbrechen kam erst nach dem Kern an. Nachher
bleibt es bedienbar, Abbrechen wirkt sofort, die Ergebnisse sind dieselben Bytes; im
Task-Manager steht ein zweiter Solidon-Prozess mit niedriger Priorität. Der neue Satz spricht
Kundenwörter. Offen aus Kundensicht: der Speicherfall kommt als „unerwarteter Fehler“ mit
`OSError`-Text (B2), eine Bohrung nach einem Hilfsprozess-Absturz rät zum Reparieren oder
rechnet still in Voxeln (B3), und jede Sitzung hinterlässt Ordner in `%TEMP%` (B4).

## Nebenbefund für die Release-Sitzung (nicht Teil des Pakets)

`tests/test_performance.py::test_the_application_is_usable_quickly` schreibt seinen Treiber
nach `tmp_path` und startet ihn mit `cwd=root`. Für ein Skript ist `sys.path[0]` dessen Ordner,
nicht `cwd`; `import app` findet dann die editierbare Installation
(`__editable___solidon3d_0_5_0_finder`) — in einem Arbeitsbaum misst die §31-Startmarke also
den Hauptbaum `F:\3D Druck`, nicht den geprüften Stand (nachgestellt mit `rev-hp-start-window`).
Im Hauptbaum und in der CI stimmt sie. Ein Release-Tor in einem Arbeitsbaum sollte das wissen;
Fix: `sys.path.insert(0, root)` im Treiber.

---

## Nachtrag 2e832f605

Geprüft: Zweig `origin/rm-212-hilfsprozess-nachtrag`, `git diff 33f0888b6 2e832f605`
(15 Dateien, +1083/−38; Commits `35dff6278` B2–B4, `2e832f605` B1), dazu der Merge
`33f0888b6` des Pakets über `f74ce7f81` (Paketdateien gegenüber `48f5231c3` nur
`it.json` — „Riprova/crea“ — und der stabilisierte Test). Jede geänderte Zeile
gelesen. Eigener Arbeitsbaum `wt-revhp2` (detached auf `2e832f605`, danach entfernt),
Läufe gebunden, Protokolle `laeufe/rev-hp2-*.txt`, Sonden in
`sonden/review-hilfsprozess/` (`frozen_graceful.py`, `broad_catches.py`).

### Urteil

**Mergebar: ja. B1 bis B4 sind behoben**, jeder Fix hat einen Test, der ohne ihn rot
ist (Gegenproben unten). Der Rauchtest besteht am neu gebauten Windows-Paket und fällt
am alten durch — genau an B4. **Einen Handstart der CI auf dem Zweig vor dem Tag
empfehle ich:** Der Schritt ist auf macOS (beide) und Linux noch nie gelaufen, und der
Tag-Lauf wäre sonst sein erster Lauf dort. Keiner der Reste blockiert den Tag.

### Ausgeführt

| Lauf | Ergebnis |
|---|---|
| `rev-hp2-1` — `test_kernel_process.py` + `test_packaging.py` ohne Fenster | 201 passed, 1 deselected |
| `rev-hp2-probe` — meine Sonden der ersten Durchsicht gegen den neuen Stand | 10 grün; 3 rot, alle erklärt (siehe unten) |
| `rev-hp2-mut-a/-b/-c` — Gegenproben | siehe Tabelle |
| `rev-hp2-rauch-neu` — `tools/check_frozen_helper.py` gegen `eingefroren/nachtrag/dist` | grün: bereit nach 0,22 s, bitgleich, hart beendet und beim Schließen nichts übrig |
| `rev-hp2-rauch-alt` — dasselbe gegen `eingefroren/voll/dist` (vor dem Nachtrag) | rot: „Im Temp-Verzeichnis … blieb etwas liegen (hart beendet): `tmpguq45tyu`“ |
| `rev-hp2-graceful` — untätiger Hilfsprozess des neuen Pakets, Zeit bis zum eigenen Ende, je 10 Runden | Median 20 ms, höchstens 23 ms; nach einer Rechnung Median 21 ms; Ausgang immer 0 |
| `rev-hp2-fänge` — breite Fänge um Aufrufe, die im Hilfsprozess rechnen können | 8 Stellen (siehe Reste) |

### B1 bis B4 — nachgeprüft

- **B1 behoben.** Schritt „Hilfsprozess im Paket starten“ (`build.yml:455–465`) direkt
  nach „Bauen“, ohne `if:`, ohne `continue-on-error`, `timeout-minutes: 5`; der Wächter
  `test_the_package_job_starts_the_kernel_helper_from_the_package` samt fünf eingebauten
  Gegenproben hält das. Das Werkzeug setzt die Punkte aus meinem Vorschlag um, auch die
  heiklen: unter POSIX den Aufräumprozess vorher aus dem CI-Python, unter Windows
  `sys.executable` nicht umbiegen (sonst leitete `spawn` im venv auf dessen Python um),
  Suchpfad und Hauptmodul aus den Startdaten genommen wie beim eingefrorenen
  Elternprozess, `sys.path.insert(0, ROOT)` gegen die editierbare Installation.
- **B2 behoben.** `kernel_jobs._opened` macht aus WinError 8/14/1450/1455 und
  ENOMEM/ENOSPC einen `MemoryError`; `_Helper.call` (`kernel_process.py:230`) fasst ein
  nicht anlegbares Segment, gescheitertes Senden und einen Tod vor der Annahme als
  `_HelperRefusedError` → hier gerechnet; die neue Antwort `refused` trägt einen
  `MemoryError` durch oder führt zum Rückfall; `serve` fängt jedes Senden und
  `pack(result)` und lässt nichts entweichen. Meine Sonden „Hilfsprozess kann den Speicher
  nicht öffnen“, „vor dem Senden gestorben“ und „`uniform` bei WinError 1455“ sind jetzt grün
  (Rückfall bzw. `ValidationError` mit Vorschlag).
- **B3 behoben.** `NOT_A_KERNEL_FAILURE = (OperationCancelled, KernelHelperLostError)`,
  durchgelassen in der Kette, in `shared_volume` (antwortete sonst still „nichts
  gemeinsam“ — ein Zwilling, den der Nachtrag selbst fand) und in `_without_scars`. Meine
  Kettensonde ist grün.
- **B4 behoben.** `_without_a_temp_folder` räumt im Paket den leeren Ordner des Hakens beim
  Start weg (nur direkt im Temp-Verzeichnis, nur leer); `stop(graceful=True)` lässt einen
  untätigen Hilfsprozess nach dem Schließen der Leitung selbst enden (`GRACEFUL_SECONDS`
  0,5 s). Am gebauten Paket belegt (`rev-hp2-rauch-neu/-alt`).

### Gegenproben

| Mutation (danach zurückgenommen) | rot |
|---|---|
| A1 `pack` in `call` wieder ungeschützt | `test_a_shared_memory_this_process_cannot_make_is_computed_here` |
| A2 `NOT_A_KERNEL_FAILURE = (OperationCancelled,)` | Kette, `shared_volume`, `_without_scars` (3) |
| A3 `_without_a_temp_folder` tut nichts | `test_a_frozen_helper_leaves_no_temp_folder` |
| B1 `_opened` ohne Umsetzung in `MemoryError` | Zusagegrenze (Attrappe und echtes Windows), `…cannot_open_the_input[speicher]`, `…result_without_room[speicher]` |
| B2 `pack(result)` in `_serve` ungeschützt | `test_a_result_without_room_is_no_lost_helper[anderes]` |
| B3 `stop` ohne sanftes Ende | `test_shutdown_lets_an_idle_helper_end_by_itself` |
| C  äußerster Fang in `serve` entfernt | **keiner** — zweite Sicherung ohne eigenen Test; die bekannten Stellen (Senden, `pack`) sind einzeln gedeckt |

`test_applying_a_large_refinement_refines_in_the_helper` (Merge) fragt jetzt den Faden der
eigenen Auswertung, verlangt `fallback == 0` und Bitgleichheit; `== 1` → `>= 1` ist wegen
des Import-Arbeiters richtig. Schlüssig.

### Der CI-Schritt auf den vier Runnern — was er wirklich prüft

- **Alle vier:** die Kind-Seite des eingefrorenen Pakets — Einstieg bis `freeze_support`,
  PyInstaller-Haken, `kernel_jobs` und `manifold3d` im Archiv, eine Boolesche bitgleich zur
  Rechnung im CI-Python, hart beendet und beim Schließen kein Prozess und kein Temp-Rest,
  beim Schließen Ausgang 0. **Ohne Fenster:** Das Kind endet vor Qt, eine Anzeige braucht es
  nicht (auch der Linux-Runner hat im Paketjob keine). Das Paket bleibt unverändert
  (`sys.dont_write_bytecode` im Paket, keine Schreibvorgänge), Stückliste und
  Signierübergabe sehen dasselbe Artefakt.
- **Windows:** `dist/Solidon3D/Solidon3D.exe`, derselbe Baum wie die Signierübergabe,
  unsigniert. Hier nachgestellt.
- **macOS (Intel und arm64):** das Bündel `dist/Solidon3D.app/Contents/MacOS/Solidon3D`
  nach BUNDLE, mit der Ad-hoc-Signatur von PyInstaller, **vor** `codesign --options
  runtime` und Notarisierung (eigene Jobs) — das signierte Bündel prüft er nicht.
- **Linux:** der COLLECT-Ordner `dist/Solidon3D/Solidon3D` (= Inhalt des tar.gz), dazu
  kein Rest in `/dev/shm`. **AppImage und Flatpak entstehen erst danach**
  (`make_linux_packages.py --appimage --flatpak`) aus demselben Ordner: dasselbe Binär,
  aber weder der FUSE-Pfad als `sys.executable` noch der Flatpak-Sandkasten (bwrap,
  `/app`, eigenes `/dev/shm`, Laufzeitbibliotheken) werden gestartet.
- **Nicht gedeckt, überall:** der eingefrorene *Elternprozess* — unter POSIX startet die
  echte Anwendung ihren Aufräumprozess aus dem Paket selbst, und nur PyInstallers Haken
  leitet ihn um. Das Werkzeug startet ihn bewusst aus dem CI-Python. Unter Windows belegt
  das Minimalpaket der ersten Runde die Eltern-Seite.

### Kann er einen Tag-Lauf aus fremdem Grund rot machen?

Kaum. Die Proben hängen an nichts außerhalb des Pakets außer diesen drei Stellen, alle
klein:

1. **Sanftes Ende in 0,5 s** (`check_frozen_helper.py:270`): Der Schritt verlangt Ausgang
   0 unter der Produktfrist `GRACEFUL_SECONDS`; die Suite lockert dieselbe Probe auf 30 s
   („geprüft wird, dass er selbst endet, nicht wie schnell“). Gemessen am Paket 20–23 ms,
   also rund das Zwanzigfache an Luft; auf einem langsamen macOS-Runner bleibt ein kleines
   Wackelrisiko. Fix: im Werkzeug `GRACEFUL_SECONDS` hochsetzen wie `STARTUP_SECONDS`.
2. **Fristen:** innen 120 s Start + 120 s Rechnung + bis zu 120 s zweiter Start gegen 5 min
   außen — nur im Fehlerfall zu knapp, dann rot durch den Abbruch des Schritts statt mit
   dem eigenen Satz. Fix: innen 60 s je Stufe.
3. **`/dev/shm`-Vergleich** zählt jedes neue `psm_*` des Runners; ein fremder
   `multiprocessing`-Nutzer läuft im Paketjob nicht. Vernachlässigbar.

### Reste (nach 0.5.1, keiner blockiert)

- **Zwillinge von B3:** breite Fänge, die `KernelHelperLostError` weiter schlucken —
  `prepare.py:3466` (`surface_gap` in `_really_overlap`, zwei Zeilen unter dem behobenen
  `shared_volume`, gibt „nicht entscheidbar“), `difference.py:239/426/721`, `hollow.py:1213`
  (Entlüftung; schluckt auch `OperationCancelled`, das schon vorher), `repair.py:4114`,
  `ingest/threemf.py:1100`. Meist gewollter Verzicht mit Befund; `kern.md` formuliert die
  Regel aber ausnahmslos. Entweder die Regel um „ausdrücklich verzichtbarer Schritt, mit
  Befund“ ergänzen oder die Stellen nachziehen.
- **ENOSPC als `MemoryError`** (`kernel_jobs.py:478`): Ein volles `/dev/shm` ist kein
  fehlender Arbeitsspeicher; im Prozess ginge die Rechnung, der Kunde liest aber „reicht
  der Arbeitsspeicher nicht“. Besser `_HelperRefusedError(lasting=True)`. Dazu der
  eigentliche Linux-Fall: Ein fast volles tmpfs meldet sich nicht beim Anlegen, sondern
  mit `SIGBUS` beim Beschreiben in `pack` — der Elternprozess stürzt. Gegenmittel:
  `os.posix_fallocate` auf das Segment direkt nach dem Anlegen.
- Unverändert aus der ersten Runde: **N1** (Deckel `MOST_HELPERS`, Sonde weiter 6 statt 3),
  **N2** (`/dev/shm` nach Absturz des Elternprozesses bzw. im Abbruch-Wettlauf; der
  Docstring von `pack`, `kernel_jobs.py:510–511`, und von `copied`, `:552`, sagt weiter
  anderes; behoben ist nur das fehlgeschlagene Senden von `done`), **N3**, **N4**
  (`_HelperSilentError` schaltet nicht ab), **N5** (`kernel_process.py:316`), **N6**, **N7**
  ohne den Kartenpunkt (Jobobjekt-Test mit rechnendem Hilfsprozess, Prioritätstest,
  Anschluss von `warm_up`/`shutdown`, Leistungsbudget über den Hilfsprozess), **N8**
  (`_index_bytes`).
- Die Sonde „Speicher im Elternprozess nicht anlegbar“ ist rot, weil sie ENOSPC benutzt
  (jetzt `MemoryError`, siehe oben); „kein Platz für das Ergebnis“ ist rot, weil sie hinter
  `_opened` einspeist und damit den Rückfall statt des `MemoryError` trifft — beides
  folgt dem neuen Entwurf, kein Befund.

### Handstart

Empfohlen: `gh workflow run build.yml --ref rm-212-hilfsprozess-nachtrag` (Vorgabe
`tests_only=false` fährt Suite auf drei Systemen, Fensterverträge und den Paketjob auf
allen vier Runnern). **Achtung:** Mit `MACOS_SIGNING_MODE=notarized` laufen danach auch
`macos-app-sign`/`macos-installer-sign` in der Umgebung `production-signing` an; für den
Beleg reicht der Paketjob, die Signierjobs danach nicht freigeben bzw. abbrechen.
Veröffentlicht wird auf diesem Weg nichts: Kein Workflow legt ein Release an, es entstehen
nur Artefakte.
