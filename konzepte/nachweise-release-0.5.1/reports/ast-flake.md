# ast-flake — unmögliche TypeErrors in `ast.walk` (test_language_rules.py)

Prüfer: ast-flake · Arbeitsbaum `F:\3D Druck.review-051\wt-ast-flake` (detached `ce8b91c7c`)
· Interpreter `F:\3D Druck\.venv\Scripts\python.exe` (CPython 3.14.7, MSC v.1944, GIL-Build, JIT aus)
· Sonden und Rohdaten: `F:\3D Druck.review-051\sonden\ast-flake\`

## Ergebnis

**Die Ursache ist der Prozessor dieser Maschine, nicht der Code.** Weder Solidon noch
`tests/conftest.py` noch eine native Bibliothek noch der Speicherbereiniger noch
CPython 3.14 ist beteiligt. Die Fehler treten in **Fenstern** auf, in denen die
Gesamtlast niedrig ist und der rechnende Prozess auf einem der beiden **bevorzugten
P-Kerne** (logisch 8–11) mit dem höchsten Turbotakt läuft; auf den übrigen P-Kernen
bleiben dieselben Läufe im selben Fenster grün. Die Maschine ist ein Intel Core
i9-13900K (Raptor Lake) — die Familie mit Intels bestätigter „Vmin Shift Instability".

Belege in einem Satz je Richtung:

- **Nicht der Code**: Eine Nachstellung ohne pytest und ohne eine Zeile Solidon-Code,
  nur Standardbibliothek, stürzt im selben Fenster ab — unter 3.14.7 **und unter
  3.13.14**.
- **Nicht der Speicherbereiniger**: Mit `gc.disable()` ab Sitzungsbeginn (am
  Sitzungsende als abgeschaltet nachgewiesen) fällt die Sprachprüfung genauso: 4 / 60
  gegen 5 / 60 der Kontrolle.
- **Der Kern**: Dieselbe Nachstellung, auf die nicht bevorzugten P-Kerne gepinnt,
  blieb in denselben Zeiträumen 0 / 204 rot (Nachstellung und Sprachprüfung), während
  frei geplante und auf die bevorzugten Kerne gepinnte Läufe 22 / 384 Mal fielen
  (exakter Test nach Fisher: p = 7 · 10⁻⁵).
- **Der Takt**: Von 559 frei geplanten Läufen mit Takt-Protokoll fielen 0,7 %, wenn der
  aktivste P-Kern höchstens 183 % des Nenntakts erreichte (≈ 5,5 GHz), aber 12,1 % bei
  184–185 % und 19,6 % ab 186 % (≈ 5,6 GHz und mehr, Mittel über zwei Sekunden).

**Geändert wurde kein Code, und kein Test wurde weicher.** Der Patch trägt nur die
Nachträge in zwei Erinnerungen unter `.claude/memory/`. Was die Ursache beseitigt, ist
eine Hardwareentscheidung Roberts (unten, „Empfehlung").

## Antworten auf die Nachfrage der Hauptsitzung

| Frage | Antwort | Beleg |
|---|---|---|
| Verschwinden die Fehler mit `gc.disable()` am Sitzungsbeginn? | **Nein.** | `gc2`: Sprachprüfung mit Plugin `sonde_plugin` (lädt vor der conftest, `gc.disable()`), 4 / 60 rot, Kontrolle 5 / 60; Nachstellung mit `gc.disable()` 4 / 60, ohne 6 / 60. In 58 von 58 nicht abgestürzten Läufen stand am Sitzungsende `gc.isenabled=False` mit über 200 000 Allokationen in Generation 0 — es lief keine einzige Sammlung. Fehlerbilder gleich: `'tuple' object is not an iterator`, `'list' object is not callable`, `'typing.Union' object is not an iterator`, Zugriffsverletzungen. |
| Hängen sie an Schwellen (`gc.set_threshold`)? | Gegenstandslos. | Sie treten ganz ohne Sammlung auf (Zeile darüber). |
| Bekanntes CPython-3.14-Issue (inkrementelle Sammlung, `gc.freeze`/`unfreeze`, AST-Knoten)? | **Keines.** 3.14.7 hat gar keinen inkrementellen Sammler: Er wurde in 3.14.5 auf den generationellen von 3.13 zurückgebaut. | Changelog und Ankündigung (Quellen unten); lokal `gc.get_threshold() == (2000, 10, 10)`, drei Generationen in `gc.get_stats()`. Die Nachstellung stürzt außerdem unter 3.13.14 ab. |
| Haben die Funde von rest-bohrung (`threemf._native_tools_of`, `NameError`, `'str' object has no attribute 'get'`) und rest-vorschau (`NameError: name 'type' is not defined` in `local._plain`, Segfault am Prozessende) dieselbe Ursache? | **Mit hoher Wahrscheinlichkeit ja**, dieselbe Familie. | Der `NameError` von rest-vorschau (`sonden/rest-vorschau/fenster-nachher-wuerfel.err`, 01:42) steht an der Zeile `isinstance(value, (float, np.floating))` — dort kommt `type` gar nicht vor; der Interpreter hat einen falschen Namen aus der Namenstabelle gelesen, ein Index daneben. Genau dieses Muster (Nachbarplatz statt richtigem Platz) zeigen alle Fehler hier. „Isoliert in 90 Läufen nicht nachstellbar" passt zu einer Rate, die außerhalb der Fenster bei null liegt. `gc.freeze` ist für diese Fehlerart nicht nötig: Die Nachstellung ruft es nie. |
| Absturzrisiko beim Kunden? | **Nein**, nicht durch diese Ursache — nur auf einer ebenso geschädigten CPU, und dort stürzt jedes Programm. | Kein Produktcode ist nötig, um den Fehler auszulösen. Das echte Kundenrisiko liegt woanders: in Paketen, die auf dieser Maschine gebaut werden (siehe „Reichweite"). |

Zu den beiden verdächtigen Stellen selbst, als Codebefund ohne Bezug zur Ursache:
`threemf._reading_trees` ruft am Ende `gc.unfreeze()` und taut damit **alles** auf, was im
Prozess je eingefroren wurde, nicht nur die eigenen Bäume — heute friert niemand sonst
ein, also folgenlos; `leash.undisturbed` stellt den vorherigen Zustand korrekt wieder
her, schützt aber nicht gegen zwei überlappende, nicht verschachtelte Verwendungen aus
verschiedenen Fäden. Beides ist Logik, keine Speichersicherheit; `gc.freeze`,
`gc.unfreeze`, `gc.disable` und `gc.enable` sind im generationellen Sammler sichere
Aufrufe.

## Messreihen

Jeder Lauf ein eigener Prozess, Ausgabe in eine Datei, Exit-Code unmittelbar nach dem
Befehl gelesen. Ab 03:30 lief daneben `messlog.py`: Gesamtlast, Takt und Belegung je
logischem P-Kern alle zwei Sekunden (PDH, englische Zählerpfade über
`PdhAddEnglishCounterW`).

### Fenster 1, 02:34–03:04 (Sprachprüfung, ohne Takt-Protokoll)

| Variante | rot / Läufe | Fehlerbilder |
|---|---|---|
| Hauptbaum, mit conftest (Vorbefund) | 2 / 12 | `'Load' object is not iterable`, `'str' object is not an iterator` |
| Hauptbaum, `--noconftest` (Vorbefund) | 0 / 12 | — |
| Arbeitsbaum, mit conftest (`basis-wt`) | 1 / 20 | `'str' object is not an iterator` |
| `PYTHONMALLOC=debug` (`malloc-debug`) | 2 / 10 | dieselben — **keine** Heap-Signatur |
| Audit-Haken ab Prozessstart (`auditlauf2`) | 1 / 1 | `'str' object is not an iterator` |
| conftest ohne alle autouse-Fixtures (`v-ohne-fixtures`) | 2 / 30 | Zugriffsverletzung, `'list' object is not an iterator` |
| conftest **leer** geschaltet (`v-leer`) | 7 / 30 | 3× Zugriffsverletzung, `'Constant' object is not iterable`, `'list' object is not callable`, 2× `'str' object is not an iterator` |
| `--noconftest` (`v-noconftest`) | 4 / 30 | 3× Zugriffsverletzung, eine davon **in `ast.parse`**, also im C-Parser |
| Einzelläufe mit Modulliste und erstem Audit (`modlauf`, `auditlauf`) | 0 / 2 | — |
| **Summe** | **19 / 147** | |

Die 12 grünen `--noconftest`-Läufe des Vorbefunds waren eine Ziehung: 0 aus 12 kommt bei
13 % Rate mit 19 % Wahrscheinlichkeit vor; 30 Läufe wenige Minuten später brachten 4 rote.

Danach, 03:05–03:29, **0 / 120**: 30 nur auf E-Kernen, 30 nur auf P-Kernen, 60 verschränkt
frei / P / E. Die Affinitätsreihen sahen zuerst wie ein Befund aus; erst die verschränkte
Reihe mit freier Planung daneben zeigte, dass das Fenster zu Ende war.

### Fenster 2, 03:50–03:53 (Kanarie, `kanarie1`)

Abwechselnd Sprachprüfung, Nachstellung 3.14.7 und Nachstellung **3.13.14**
(`ast_last.py`: parsen, zwei Durchläufe mit `ast.walk`, Umlaut-Generatorausdruck, nur
Standardbibliothek). Über 03:30–03:56: Sprachprüfung 1 / 60, Nachstellung 3.14.7 2 / 59,
Nachstellung **3.13.14 3 / 59** — alle sechs zwischen 03:50:55 und 03:52:48, also in drei
Minuten. Das Protokoll zeigt das Fenster: Gesamtlast 9–20 %, aktiver Kern 8–11, dessen
Takt 184–188 % statt vorher und nachher 181–183 %. Ab 03:54 lief eine Nachbarsitzung unter
Volllast (60–97 %, Takt 167–175 %) — kein Fehler mehr.

### Fenster 3 (`gc2`, 03:59–04:44, fünf Varianten verschränkt, 60 Zyklen; alle Fehler zwischen 04:12 und 04:43)

| Variante | rot / Läufe |
|---|---|
| Sprachprüfung, frei (Kontrolle) | 5 / 60 |
| Sprachprüfung, `gc.disable()` ab Sitzungsbeginn | 4 / 60 |
| Nachstellung 3.14.7, frei | 6 / 60 |
| Nachstellung 3.14.7, `gc.disable()` | 4 / 60 |
| Nachstellung 3.14.7, **nur nicht bevorzugte P-Kerne** (Maske `F0FF`) | **0 / 60** |

Exakter Test nach Fisher: nicht bevorzugte Kerne 0 / 60 gegen alle frei geplanten
19 / 240, p = 0,012.

### Kernreihe (`kern1`), 04:45–05:30, 72 Zyklen

| Variante | rot / Läufe |
|---|---|
| Sprachprüfung mit conftest, frei (Kontrolle) | 2 / 72 |
| Sprachprüfung mit conftest, nur nicht bevorzugte P-Kerne | **0 / 72** |
| Nachstellung, nur bevorzugte Kerne (logisch 8–11, Maske `0F00`) | 1 / 72 |
| Nachstellung, nur nicht bevorzugte P-Kerne | 0 / 72 |

Das Fenster war hier kurz: Nur zwischen 04:45 und 04:52 erreichten die bevorzugten Kerne
185–188 %, alle drei roten Läufe liegen darin; ab 04:59 blieben sie bei höchstens 183 %.
Zusammen mit `gc2`: nicht bevorzugte P-Kerne **0 / 204**, frei geplant oder auf die
bevorzugten Kerne gepinnt 22 / 384, p = 7 · 10⁻⁵.

### Takt je Lauf (`auswertung.py` über `kanarie1`, `gc2` und `kern1`)

Jedem Lauf zugeordnet: der höchste Zwei-Sekunden-Takt des am stärksten belegten P-Kerns in
seinem Zeitraum (Nenntakt 3,0 GHz = 100 %). Die auf `F0FF` gepinnten Varianten sind
ausgenommen, weil ihr eigener Kern nicht der am stärksten belegte sein muss
(`auswertung-alle.txt`).

| höchster Takt | rot / Läufe | Rate |
|---|---|---|
| ≤ 183 % (≈ 5,5 GHz) | 3 / 409 | 0,7 % |
| 184–185 % | 7 / 58 | 12,1 % |
| ≥ 186 % (≈ 5,6 GHz und mehr) | 18 / 92 | 19,6 % |

Die bevorzugten Kerne sind die mit Scheduling-Klasse 2 (`kerne.py`, logisch 8–11 = Kerne
8 und 10). Nur sie erreichen die obersten Turbostufen (Turbo Boost Max 3.0 und Thermal
Velocity Boost), und nur bei wenigen aktiven Kernen und kühlem Chip — also genau dann,
wenn die Maschine sonst wenig zu tun hat.

## Eingrenzung — was ausgeschlossen ist, und womit

- **`tests/conftest.py`**: schaltbare Kopie (`mache_conftest.py`), alle Teile aus: 7 / 30
  rot; `--noconftest`: 4 / 30 rot.
- **Native Bibliotheken**: Die Nachstellung lädt keine (nur Standardbibliothek) und fällt
  unter 3.14.7 und 3.13.14. Auch in der Sprachprüfung ohne conftest sind beim ersten Test
  nur Erweiterungen der Standardbibliothek geladen (`erster-test-noconftest.txt`).
- **Speicherbereiniger**: siehe Antworttabelle.
- **CPython**: 3.13.14 fällt genauso; kein passendes Issue; kein inkrementeller Sammler in
  3.14.7.
- **Heap-Beschädigung / Use-after-free**: `PYTHONMALLOC=debug` ändert das Bild nicht — keine
  `0xDD`-Zugriffe, keine Randverletzungen. Die falschen Werte sind **plausible Nachbarn**:
  der Feldname statt des Tupeliterators, der Iterator statt des Zeichens, der
  `ctx`-Wert statt `_fields`. Das ist die Spur eines Zeigers, der einen Stapelplatz
  (8 Byte) daneben liegt — oder weit daneben, dann Zugriffsverletzung.
- **Fäden**: außer dem Hauptfaden kein Python-Faden; nativ nur Windows' Threadpool
  (drei `ntdll`-Fäden) und, sobald NumPy geladen ist, 23 ruhende OpenBLAS-Fäden.
- **Fremde DLLs**: keine eingeschleusten Module (`dlls.txt`).
- **`_wmi`**: geladen, aber `_wmi.exec_query` wird nie gerufen (`audit2.txt`); der
  Hilfsfaden kopiert seine Daten seit gh-125315 ohnehin zuerst
  (`wmimodule-v3.14.7.cpp`, Zeilen 60–64).
- **Arbeitsspeicher**: nicht ausgeschlossen (nie eine Speicherdiagnose), aber
  unwahrscheinlich: Eine defekte Speicherzelle hinge nicht am Kern, auf dem der Prozess
  rechnet.

## Ursache

**Die bevorzugten P-Kerne des i9-13900K rechnen in ihren höchsten Turbostufen
gelegentlich falsch.** Die Hardware: Family 6 Model 183 Stepping 1, MSI MPG Z690 CARBON
WIFI, BIOS 1.O0 vom 01.04.2026, **Microcode 0x133** (im August noch 0x12F), 2 × 32 GB
DDR5 auf JEDEC 4800, keine WHEA-Einträge — der Prozessor bemerkt diese Rechenfehler
also selbst nicht. Intel hat für die
13. und 14. Generation die „Vmin Shift Instability" bestätigt: erhöhte Spannungen
schädigen den Taktbaum dauerhaft; die Microcode-Stände ab 0x12B/0x12F verhindern weitere
Schädigung, reparieren eine geschädigte CPU aber nicht. Dass die Fehler mit 0x133 bleiben
und genau an die höchsten Taktstufen der bevorzugten Kerne gebunden sind, passt dazu.

Dieselbe Maschine zeigte dieselbe Familie schon in ganz anderem Code — falsche
Ganzzahlumwandlung und eine still falsche Summe (07.08.2026), `cannot unpack
non-iterable int` in der Schichtanalyse (13.08.2026), `ast.walk` in `test_translations`
und `test_foreign` (12.09.2026) — und die Ereignisanzeige trägt passende Spuren: ein
`STATUS_ILLEGAL_INSTRUCTION` (`c000001d`) mitten in OpenBLAS (23.09.2026) und eine
Zugriffsverletzung mit einer **Heapadresse als Befehlszeiger** (24.09.2026).

## Änderung

Kein Produktcode, kein Testcode. `reports/ast-flake.patch` trägt nur:

- `.claude/memory/ast-walk-reisst-im-torlauf.md`: die Messung vom 27.09.2026 und die
  ersetzte Handlungsregel — „standalone dreimal grün" beweist bei 13 % Rate nichts
  (0 aus 3 mit 66 %), zuordnen nur verschränkt und mit Takt-Protokoll daneben.
- `.claude/memory/native-bibliotheken-speicher.md`: Microcode 0x133, das Fenster (niedrige
  Last, bevorzugte Kerne, oberste Taktstufen), die Ereignisanzeige, und die offene
  Entscheidung mit dem Risiko für Release-Pakete.

## Nachweis

- Sprachprüfung **mit conftest**, auf die nicht bevorzugten P-Kerne gepinnt, im selben
  Zeitraum wie die frei geplante Kontrolle: **72 / 72 grün**, Kontrolle 2 / 72 rot
  (`kern1`). Das ist der Nachweis, dass die Rate am Kern hängt — **keine Behebung**: Am
  Code hat sich nichts geändert, und frei geplant fällt die Prüfung auf dieser Maschine
  weiter, bis die CPU getauscht oder im BIOS begrenzt ist.
- ruff check: grün · ruff format --check: grün (1272 Dateien) · mypy: grün (324 Quelldateien) ·
  Prüfungen der Erinnerungen und Karten (`test_source_escapes`, `test_directory_docs`,
  `test_memory_index`, `test_docs_scan`): 41 grün · `git apply --check` des Patches im
  Hauptbaum: Exit 0

## Reichweite

- **Übrige Suite und Anwendung auf dieser Maschine**: ja, jede Stelle. Der Fehler braucht
  keinen bestimmten Code, nur Rechenzeit auf einem bevorzugten Kern bei hohem Takt. Die
  „wandernden" Abrisse der Fensterdateien (`0xc0000374`, Stapel im Sammler) sind
  mindestens teilweise verdächtig, ebenso die beiden Pflaster, die seit August einen
  Fehlschlag wiederholen (`geom/mesh.on_surface`, `export/threemf._numbers_from`) — sie
  helfen nur auf dieser Maschine.
- **Kunden**: nein, außer auf ebenso geschädigten CPUs.
- **Release-Artefakte, die hier entstehen** (PyInstaller-Pakete, `_chain.pyd`, Handbuch,
  Bilder, Signaturen): Das ist das eigentliche Risiko. Ein Rechenfehler kann still
  bleiben — im August stand einmal ohne jede Ausnahme eine falsche Summe da. Solange die
  CPU bleibt, Pakete in der CI bauen oder zweimal bauen und bitweise vergleichen, bevor
  sie hochgeladen werden.
- **Die anderen Prüfer**: Befunde mit unmöglichen Ausnahmen oder wandernden
  Zugriffsverletzungen gehören zuerst gegen diese Ursache geprüft — verschränkt, mit einer
  auf `F0FF` gepinnten Variante (`affin.py F0FF …`) als Gegenprobe.

## Empfehlung an Robert (Entscheidungen, nicht umgesetzt)

1. **CPU-Austausch über Intels verlängerte Garantie** (13./14. Gen Desktop i5/i7/i9, fünf
   Jahre ab Kauf) — der einzige Schritt, der die Ursache beseitigt. Die Messreihen hier
   sind als Beleg für die Reklamation brauchbar.
2. Bis dahin im BIOS die **Intel Default Settings** setzen bzw. prüfen und die obersten
   Turbostufen der bevorzugten Kerne abschalten oder begrenzen (Turbo Boost Max 3.0 /
   Thermal Velocity Boost, oder den Multiplikator der Kerne 8 und 10 auf den der übrigen
   P-Kerne setzen). Die Messung sagt voraus, dass die Fehler damit verschwinden; nachzuweisen
   mit `kern_reihe.sh` in einer ruhigen Stunde. MSI Center wechselt laut Ereignisanzeige
   das Energieschema (`MSI.CentralServer.exe`) — prüfen, ob sein Profil Leistungsgrenzen
   anhebt.
3. **Einmal MemTest86 über Nacht**, um den Arbeitsspeicher auszuschließen (offen seit
   August).
4. Release-Pakete in der CI oder doppelt bauen (siehe Reichweite).

Quellen: [Intel, Vmin Shift Instability – Latest Information](https://www.intel.com/content/www/us/en/support/articles/000102331/processors.html),
[Intel Community, Microcode 0x12F](https://community.intel.com/t5/Mobile-and-Desktop-Processors/Intel-Core-13th-and-14th-Gen-Vmin-Shift-Instabilty-Update-New/m-p/1686948),
[The Register zu 0x12B](https://www.theregister.com/2024/09/26/intel_0x12b_raptor_lake/),
[Python 3.14.5: Rückbau des inkrementellen Sammlers](https://discuss.python.org/t/python-3-14-5-is-here-with-a-new-old-garbage-collector/107304),
[Diskussion zum Rückbau](https://discuss.python.org/t/reverting-the-incremental-gc-in-python-3-14-and-3-15/107014),
[CPython-Changelog](https://docs.python.org/3/whatsnew/changelog.html).

## Dateien

- Bericht: `F:\3D Druck.review-051\reports\ast-flake.md`
- Patch: `F:\3D Druck.review-051\reports\ast-flake.patch` (nur `.claude/memory/`)
- Sonden: `F:\3D Druck.review-051\sonden\ast-flake\`
  - Reihen: `serie.sh`, `serie_cmd.sh`, `verschraenkt.sh`, `kanarie.sh`, `gc_reihe2.sh`,
    `kern_reihe.sh`; je Reihe ein Ordner mit Läufen, `exits.txt` (Variante, Nummer,
    Exit-Code, Uhrzeit) und `summe.txt`
  - Werkzeuge: `ast_last.py` (Nachstellung nur mit Standardbibliothek, läuft unter 3.13 und
    3.14, Schalter `SONDE_GC_AUS`), `affin.py` (Affinität im selben Prozess),
    `messlog.py` (Last und Takt je Kern), `auswertung.py` (Takt je Lauf), `kerne.py`
    (P/E-Kerne und Bevorzugung), `mache_conftest.py` (schaltbare conftest),
    `sonde_plugin.py` (GC-Schalter und Modulliste), `sonde_audit.py` mit
    `lauf_mit_audit.py`, `sonde_erster_test.py`
  - Protokolle: `kanarie1-mess.csv`, `gc1-mess.csv`, `kern1-mess.csv`,
    `auswertung-alle.txt`, `dlls.txt`, `audit2.txt`, `module-leer.txt`
