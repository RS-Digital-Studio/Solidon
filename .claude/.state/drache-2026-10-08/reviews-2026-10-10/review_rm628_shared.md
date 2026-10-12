# Kurzreview RM-628: `paths.read_text_shared` (Commit `1f7652520`)

Gegenstand: Worktree `F:\sl-cura`, `git diff 9d5790b8e..1f7652520` (7 Dateien, +105/−22).
Nur gelesen und gemessen, im Worktree nichts geändert. Sonden, Plugins und Ausgaben unter
`%TEMP%\claude\F--3D-Druck\b00d64ab-ed49-460e-9651-1d89ea000640\scratchpad\rv628s\`.
Interpreter `F:\3D Druck\.venv` (3.14.7), `app.__file__` = `F:\sl-cura\app\__init__.py` in jeder Sonde
geprüft. Lange Läufe gepinnt (`/affinity FFFFF0FF`), Zeiten als CPU-Zeit, A/B immer im Wechsel.

## Funde

### M1 (mittel): Jede Lesung legt `WinDLL` und den Prototyp neu an und kostet so 16–51 % mehr CPU beim kalten Lesen

`app/core/paths.py:277-287`: `read_text_shared` erzeugt bei jedem Aufruf
`WinDLL("kernel32", use_last_error=True)`, holt `CreateFileW` neu und setzt `argtypes`/`restype`.
Die Profilsuche ruft das tausendfach auf (Orca-Bestand: 3083 Lesungen je Druckersuche), und
DRUCK-14 hält fest, dass das Öffnen unter Windows der teure Teil der Suche ist
(`tests/test_slicer_profiles.py:1576-1578`).

Beleg (`mikro.py`, `mikro2.py`, `kosten2.py`, RM-670-Test mit `rv628_zeit.py`):

| Messung | wie im Commit | Prototyp einmal angelegt | `Path.read_text` (vorher) |
|---|---|---|---|
| je Aufruf, 400 echte Profile (Cura/Orca) × 5, 7 Runden, Thread-CPU | 191 µs | 137 µs / 100 µs (2. Lauf) | 118 µs / 100 µs (2. Lauf) |
| `discover_printers` OrcaSlicer kalt, Median aus 5 | 1,875 s | 1,625 s | 1,609 s |
| `discover_printers` ElegooSlicer kalt, Median aus 5 | 1,906 s | 1,484 s | 1,453 s |
| RM-670-Test, **erster** Export, orca (3 Runden) | 9,08 / 9,34 / 9,80 s | – | 7,39 / 7,41 / 7,81 s |
| RM-670-Test, **erster** Export, cura | 0,94 / 1,02 / 1,33 s | – | 0,53 / 0,67 / 0,78 s |
| RM-670-Test, zweiter Export (orca/prusa/cura) | 0,031–0,125 s | – | 0,031–0,094 s |

Ergebnisse gleich (997 Drucker, 3083 Lesungen in jeder Lesart). Der zweite Export hält die
RM-670-Grenze (< 0,5 s) weiterhin, weil er kaum liest. Teurer werden die kalte Druckersuche
(+0,27 s Orca, +0,45 s Elegoo, +16 bis 31 %) und der erste Export nach dem Start (im Median
+1,9 s CPU oder +26 % am gewachsenen Orca-Bestand des Tests, +0,34 s oder +51 % bei Cura). Mit einmal angelegtem Prototyp liegt der Aufschlag
bei +1 bis 2 %, im Rahmen der Streuung.

Fix: `kernel32` und den `CreateFileW`-Prototyp einmal anlegen, z. B. hinter
`functools.cache` (`_create_file()`), und `CloseHandle` daneben. Das ist threadsicher: Der
Prototyp ändert sich danach nicht mehr, und `use_last_error` speichert den Fehler je Thread.
Als Test eignet sich ein Zähler auf `paths._windows_ctypes.WinDLL` (nach `cache_clear()`): Zwei
Lesungen legen höchstens eine Bibliothek an. Am Stand des Commits ist er rot (zwei).

### L1 (leicht): INI- und XML-Lesestellen sperren das Löschen weiter, obwohl Karte und Begründung das Gegenteil sagen

`app/core/export/slicer_profiles.py:2752` (`_read_ini` → `ConfigParser.read` öffnet mit `open`,
13 Aufrufer), `:2770` (`_read_cura_material` → `ET.parse(path)`) und `:3063`
(`_cura_material_values` → `ET.parse(path)`) öffnen weiterhin ohne `FILE_SHARE_DELETE`. Curas
Kopie im Cache trägt genau diese Dateien: `cura_linux.RESOURCE_FOLDERS` = `definitions`,
`extruders`, `intent`, `materials`, `quality`, `variants`. `konzepte/begruendungen/karte-app-core.md:185-186`
(„`slicer_profiles` und `appimage` lesen ihre Dateien deshalb mit geteiltem Löschen") und der
Bericht („alle Lesestellen in `slicer_profiles`") sagen mehr, als der Code tut. Das ist die halbe
Regel aus `zwillinge.md`.

Beleg (`zwilling.py`, gleiche Bauart wie der neue Test, Cache geleert bei offener Datei):
`_read_ini(…/resources/quality/x.inst.cfg)` → `rmtree` scheitert mit `PermissionError: [WinError 32]`;
dasselbe für `…/resources/materials/x.xml.fdm_material` (Öffnen wie `ET.parse`: `open(source, "rb")`).
Den Fenstertest berührt das nicht, denn die Attrappe (`tests/cura_fakes.py:cura_installation`) hat
nur Definitionen. Unter Windows trifft es Curas eigene `.cfg`/`.inst.cfg`, die Cura beim Speichern
ersetzt. Bei Orcas `.conf` ist das dagegen schon behoben (`chosen_machine` liest jetzt geteilt).

Fix: eine Bytes-Variante neben `read_text_shared` (gemeinsamer Kern, ein Öffnungsweg), dann
`ET.fromstring(read_bytes_shared(path))` an beiden XML-Stellen und in `_read_ini`
`parsed.read_string(read_text_shared(path), source=str(path))`. Dabei die alte Bedeutung halten:
`ConfigParser.read` überging eine fehlende Datei still und gab einen leeren Parser zurück, nicht
`None`. Der Test geht wie der neue, nur für `.inst.cfg` und `.xml.fdm_material`. Alternativ den
Satz in Karte und Begründung auf „JSON und Prusa-INI" einschränken, aber dann bleibt die Lücke.

### L2 (leicht): Die Ausnahme verliert Dateinamen und Systemtext

`app/core/paths.py:296-297`: `WinError(code, f"{path}")` setzt den Pfad als `strerror`, und
`filename` bleibt `None`. Klasse und `errno` stimmen mit `read_text` überein, die Meldung aber
nicht. Vorher stand im Protokoll `[Errno 2] No such file or directory: '…'`, jetzt `[WinError 2] C:\…`
(Sonde `korrektheit.py`, Fälle fehlt/Ordner/Verzeichnis/ACL/Teilungsverletzung). Die Aufrufer
protokollieren `problem` nur auf Debug-Stufe. Den Grund liest dort jetzt nur noch, wer die Nummer kennt.

Fix: `raise OSError(None, _windows_ctypes.FormatError(code).strip(), str(path), code)`. Geprüft:
Das ergibt `FileNotFoundError` mit `errno 2`, `winerror 2` und `filename` sowie
`[WinError 2] Das System kann die angegebene Datei nicht finden.: '…'`; Code 32 ergibt
`PermissionError`. Test: `filename == str(missing)`, am Stand des Commits rot.

## Geprüft ohne Fund

**1. Korrektheit gegen `Path.read_text`** (`korrektheit.py`, je Fall `strict` und `replace`):
UTF-8, BOM (bleibt `\ufeff` wie vorher), CRLF und einzelnes CR (Zeilenenden werden gleich
übersetzt), Strg-Z mitten im Text (kein Ende, der Deskriptor ist binär, weil `open_osfhandle`
ohne `O_TEXT` arbeitet), leer, 20 MB, NUL, Latin-1 und kaputtes UTF-8 (gleicher
`UnicodeDecodeError` an gleicher Stelle). Inhalt überall gleich. Fehlende Datei und fehlender
Ordner ergeben `FileNotFoundError`, ein Verzeichnis, eine ACL-Sperre und eine
Teilungsverletzung `PermissionError`, jeweils Klasse und `errno` wie vorher (zum Text siehe L2).
Langer Pfad (427 Zeichen, ohne und mit `\\?\`), UNC (`\\localhost\C$…`, `\\127.0.0.1\C$…`,
`\\?\UNC\…`), relativer Pfad und Unicode-Name verhalten sich gleich. Griffe: 155 vor und nach
15 000 Aufrufen samt allen Fehlerwegen, es leckt nichts. ctypes: Die `argtypes` entsprechen der
Signatur von `CreateFileW`, und der Vergleich mit `INVALID_HANDLE_VALUE` greift unter 64 Bit
(sonst käme bei fehlender Datei `EBADF` aus `open_osfhandle` statt `FileNotFoundError`).
`CloseHandle` bekommt ein `HANDLE`-Objekt. Außerhalb von Windows läuft unverändert `read_text`.
Alle Aufrufer fangen `OSError` vor Ort.

**2. Ort und Plattformen:** `paths.py` passt. Dort liegen schon `opened_path`, `lock_file` und die
Windows-Griffe, ein Ein-/Ausgabe-Modul gibt es im Kern nicht. Es braucht kein Qt
(`test_core_isolation` grün). mypy wie das Tor (`files = app`, strict) unter win32, linux und
darwin: je „no issues in 374 source files", Exit 0.

**3. Test:** `test_a_definition_being_read_does_not_stop_the_cache_from_being_cleared` misst
wirklich das Löschen bei offenem Griff. Gegenprobe über Plugin `rv628_mutant.py`: ohne
`FILE_SHARE_DELETE` (derselbe Quelltext, nur `0x1 | 0x2`) rot, weil `rmtree` mit WinError 32
scheitert und `_load` `None` liefert; mit `Path.read_text` (Stand davor) rot, weil der Cache
stehen bleibt; mit dem Commit grün.
Fenstertest `test_after_a_cleared_cache_a_new_search_brings_curas_printers_back` **10 von 10 grün**
(8,6–10,9 s) unter Last: daneben liefen fortlaufend die acht Tor-Dateien mit `-n 6`. Gegenprobe
unter gleicher Last mit `read_text_shared` ohne `FILE_SHARE_DELETE`: **1 von 10 rot**, mit
`[WinError 32] … fdmextruder.def.json` im `rmtree`. Die Last stellt den Wettlauf also nach,
allerdings selten. Zehn grüne Läufe allein beweisen deshalb wenig, mit dem deterministischen
Einzeltest zusammen schon.

## Läufe (Exit-Codes direkt gelesen)

| Lauf | Ergebnis |
|---|---|
| `ruff check --no-cache .` / `ruff format --no-cache --check .` | 0 / 0 |
| `mypy` win32 / linux / darwin | 0 / 0 / 0 |
| Tor-Dateien ohne Fenster (`test_slicer_profiles`, `test_appimage_profiles`, `test_discover`, `test_cura_machine`, `test_first_run`, `test_first_run_setup`, `test_shared_constants`, `test_directory_docs`), `-n 6`, dreimal | 993 passed, 5 skipped (Exit 0); 1 failed (Exit 1, N1, unabhängig); 993 passed (Exit 0) |
| Fensterteile von `test_first_run*`, `test_appimage_profiles`, `test_discover`, `test_cura_machine` | 131 passed, Exit 0 |
| Regelwächter: `test_language_rules`, `test_registry_consistency`, `test_core_isolation`, `test_hard_rules`, `test_support`, `test_cache` | 2678 passed, Exit 0 |
| Fenstertest 10× unter Last / Gegenprobe 10× | 10/10 grün / 1/10 rot (WinError 32) |
| RM-670-Leistungstest orca/prusa/cura, 3 Runden je Lesart | alle Exit 0 |
| `tools/affected_tests.py` über die 7 Dateien | „448 von 451, das ist die Suite"; deshalb die gezielte Auswahl oben, das volle Tor fuhr der Bauagent (Bericht §7) |

## Neue Punkte (nicht aus diesem Commit, Vorschlag ohne Nummer)

- **N1:** `tests/test_first_run.py::test_the_official_comfy_desktop_name_is_found_in_a_program_folder`
  hängt von der Reihenfolge ab. Läuft vorher im selben Prozess
  `tests/test_discover.py::test_choices_survive_a_restart`, findet er dessen gemerkte `comfy.exe`.
  In dieser Reihenfolge ist er immer rot (`pytest -p no:randomly <beide Knoten>`: 1 failed, 1 passed),
  unter `-n 6` war er einmal von drei Läufen rot. Fix: im Test `tools.discover.remembered` bzw. die
  Auswahldatei auf `tmp_path` umbiegen.
- **N2:** `tests/test_slicer_profiles.py::test_a_new_search_forgets_the_held_stock` wackelt unter
  `-n 6`. Neu gelistet wird der Sitzungsordner `solidon-tests-…` (APPDATA), und `_settle(tmp_path)`
  altert nur `tmp_path`. Vermutlich haben andere Tests desselben Arbeiters den Sitzungsordner gerade
  berührt, sodass er jünger als `SETTLE_NS` ist. `_list_program_folders` listet ihn dann neu, und
  „gemerkt" wird rot. Mit dem Commit war er in 4 von
  6 Läufen rot, mit dem Lesen von vorher (Mutant `alt`) in 1 von 4, also unabhängig vom Commit.
  Fix: im Test auch die Nutzerwurzeln der Sitzung altern oder APPDATA auf einen gealterten
  `tmp_path`-Ordner setzen.

## Urteil

**Nicht.** Für sich ist der Commit korrekt. Inhalt, Ausnahmeklassen, Griffe, Plattformen und die
Gegenproben stimmen. Er macht aber das kalte Lesen jeder Profildatei messbar teurer (M1: +16 bis
31 % Druckersuche, +26 % erster Export am großen Bestand). Der Fix dafür sind rund zehn Zeilen und
bringt den Aufschlag auf +1 bis 2 %. Mit M1 behoben, samt L1 und L2 oder mit einer auf JSON und
Prusa-INI eingeschränkten Karte, kann er landen. Nachprüfung genügt dann für M1.
