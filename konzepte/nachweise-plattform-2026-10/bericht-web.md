# Web-Recherche: Solidon-Start auf Intel-Macs (macOS 26) und Plattformrisiken

Stand der Recherche: 12.10.2026. Legende Einschätzung: **ja** = trifft Solidon 0.6.0 wahrscheinlich, **vielleicht** = möglich, nicht belegt, **nein** = trifft nicht zu.
Belegt = Quelltext, offizielle Doku, reproduziertes Issue. Vermutung = Foren, unbestätigte Berichte.

**Kurzurteil zum Verdacht „0.6.0 startet auf Intel-Macs weiter nicht“:** Die Quellen stützen
die Ursachenkette von 0.5.x vollständig (Quelltext CPython, Apples libffi-Konfiguration,
Apple-Doku, drei fremde Feldberichte auf echten Intel-Macs). `allow-unsigned-executable-memory`
am Hauptprogramm ist nach Apple-Doku und Quelltext die richtige und ausreichende Ausnahme;
`allow-jit` hülfe nicht. Für einen *weiteren* Start-Hänger von 0.6.0 auf einem offiziell
unterstützten Intel-Mac mit macOS 26 wurde **keine** belegte Ursache gefunden. Die fehlende
`disable-library-validation` erzeugt nach allem Gefundenen keinen Hänger, aber stille
Funktionsausfälle (sicher: 3D-Maus über 3DxWare). Restrisiken stehen unter „Wenn 0.6.0 doch
hängt“ am Ende.

## A. libffi / ctypes / cffi unter Hardened Runtime auf x86_64-macOS

Vorab: Der Signierschritt in `build.yml` (Z. 1402–1437) signiert erst `--deep` ohne Liste, dann
das Bundle ohne `--deep` mit `allow-unsigned-executable-memory`, und liest Schlüssel und Wert
zurück. Die Reihenfolge ist richtig; die klassische Falle (ein späteres `--deep --force` streift
die Liste vom Hauptprogramm) liegt nicht vor. Das wurde nur gelesen, nicht im Repository geändert.

### A1. Welche libffi, und wie alloziert sie auf x86_64? (belegt, Quelltext)

- **actions/setup-python nimmt für 3.11+ das python.org-Paket.** `builders/macos-python-builder.psm1`
  in actions/python-versions lädt ab 3.11.0b1 (und für arm64 immer) das fertige
  `python-<ver>-macos11.pkg` von python.org, statt selbst zu bauen.
  Quelle: https://github.com/actions/python-versions/blob/main/builders/macos-python-builder.psm1
  (Stand main, Oktober 2026). Plattform: beide Mac-Architekturen.
- **python.org baut keine libffi mit.** `Mac/BuildScript/build-installer.py` (Zweig 3.14) baut
  OpenSSL 3.5.9, Tcl/Tk, XZ, NCurses, SQLite, libmpdec — keine libffi.
  Quelle: https://github.com/python/cpython/blob/3.14/Mac/BuildScript/build-installer.py
- **CPython linkt auf macOS Apples System-libffi.** `configure.ac` (3.14): im Darwin-Zweig
  `LIBFFI_CFLAGS="-I${SDKROOT}/usr/include/ffi -DUSING_APPLE_OS_LIBFFI=1"`, `LIBFFI_LIBS="-lffi"`,
  also `/usr/lib/libffi.dylib` aus dem Shared Cache.
  Quelle: https://github.com/python/cpython/blob/3.14/configure.ac
- **`Py_ffi_closure_alloc` ruft auf macOS ≥ 10.15 Apples `ffi_closure_alloc`.**
  `Modules/_ctypes/malloc_closure.c`: unter `USING_APPLE_OS_LIBFFI` und
  `__builtin_available(macos 10.15, …)` direkt `ffi_closure_alloc`; der eigene Ausweichweg
  `more_core` (anonymes `mmap` RWX, ohne `MAP_JIT`) läuft dort nicht.
  Quelle: https://github.com/python/cpython/blob/3.14/Modules/_ctypes/malloc_closure.c
- **gh-128485 (belegt):** `_ctypes_mod_exec` ruft seit dem Commit `04d4aac` (PR #131633,
  24.03.2025) ohne jede Plattformweiche `Py_ffi_closure_alloc(sizeof(void *), &codeloc)` und
  gibt sofort wieder frei; bei `NULL` setzt es `MemoryError` und das Laden von `_ctypes`
  scheitert. Anlass war ein Datenwettlauf in libffis dlmalloc unter Free-Threading, nicht macOS.
  Im Issue steht nichts zu macOS, Hardened Runtime oder einer Rücknahme.
  Quellen: https://github.com/python/cpython/issues/128485 (geöffnet 04.01.2025, geschlossen
  24.03.2025), https://github.com/python/cpython/blob/3.14/Modules/_ctypes/_ctypes.c
  (Stand 3.14-Zweig: Aufruf weiter vorhanden). Folgeissues bei CPython zu Hängern unter
  Hardened Runtime: **keine gefunden** (Suche Oktober 2026).
- **Apples libffi: x86_64 = mmap-Weg, arm64 = Trampolintabelle (belegt).** In
  apple-oss-distributions/libffi steht in `darwin/include/fficonfig_x86_64.h`
  `#define FFI_MMAP_EXEC_WRIT 1` und `#undef FFI_EXEC_TRAMPOLINE_TABLE`, in
  `fficonfig_arm64.h` umgekehrt `FFI_EXEC_TRAMPOLINE_TABLE 1` und `FFI_TRAMPOLINE_WHOLE_DYLIB 1`
  (vorgefertigte, signierte Trampolinseiten aus `/usr/lib/libffi-trampolines.dylib`, per
  `vm_remap` eingeblendet — braucht nie W+X). Upstream-`configure.ac` von libffi macht es genauso
  (`*arm*-apple-* | aarch64-apple-*` → Tabelle; übrige `*-apple-*` → `FFI_MMAP_EXEC_WRIT`);
  statische Trampoline (`FFI_EXEC_STATIC_TRAMP`) gibt es nur für Linux und Cygwin.
  Quellen: https://github.com/apple-oss-distributions/libffi/blob/main/darwin/include/fficonfig_x86_64.h,
  https://github.com/apple-oss-distributions/libffi/blob/main/darwin/include/fficonfig_arm64.h,
  https://github.com/libffi/libffi/blob/master/configure.ac
- **Ablauf in `src/closures.c` (Apple-Fork wie Upstream), Weg `FFI_MMAP_EXEC_WRIT`:**
  `ffi_closure_alloc` → dlmalloc → `dlmmap`. Erst anonymes `mmap` mit `PROT_EXEC` (also RWX);
  scheitert es mit `EPERM`/`EACCES`, folgt `dlmmap_locked`: eine Temp-Datei (Kandidaten in
  `open_temp_exec_file_opts`: `LIBFFI_TMPDIR`, `TMPDIR`, `/tmp`, `/var/tmp`, `/dev/shm`, `HOME`;
  `memfd` gibt es auf macOS nicht) wird zweimal eingeblendet, einmal schreibbar, einmal
  ausführbar. Scheitert das ausführbare `mmap` am Versatz 0, schließt der Code die Datei und
  springt mit `goto retry_open` zurück — **ohne Zähler**. Solange `open` gelingt und `mmap`
  scheitert, kreist er für immer; das ist der Hänger ohne Ausgabe und ohne Absturzbericht.
  Quellen: https://github.com/apple-oss-distributions/libffi/blob/main/src/closures.c,
  https://github.com/libffi/libffi/blob/master/src/closures.c
- **Fremde Feldberichte (reproduziert, nicht offiziell):**
  - draftomen#905 (03.10.2026): Intel-Mac, **macOS 26.7.1**, Hänger beim `import truststore` →
    ctypes; arm64 unberührt; auf dem Runner `macos-15-intel` grün. Behoben wurde dort **nicht**
    per Entitlement, sondern durch Meiden von ctypes auf x86_64 (v0.6.2).
    https://github.com/andreagrandi/draftomen/issues/905
  - peon-ping#589 (03.09.2026): Intel, macOS 26.6.2, `osascript` (Apple-Binary ohne Liste);
    Stapel `ffi_closure_alloc` → `dlmmap` → `mmap`/`mkostemp`. **Wichtig:** Auf macOS 15.7.7
    lief derselbe Ausweichweg noch (er hinterließ nur `~/ffiXXXXXX`-Dateien), auf 26.x kreist er.
    https://github.com/PeonPing/peon-ping/issues/589
  - t3code#16714 (07.10.2026): Intel Mac mini i7-8700B, **macOS 15.7.9**, Googles
    Antigravity-Laufzeit hängt in `dlmmap_locked`; eine lokal mit
    `allow-unsigned-executable-memory` (Hardened Runtime bleibt an) neu signierte Kopie läuft.
    Das ist also nicht streng auf macOS 26 begrenzt.
    https://github.com/pingdotgg/t3code/issues/16714
  - elfensky/macos-apps-mcp PR #311 (07.10.2026): python-build-standalone, universal2. Mit
    gesetztem `TMPDIR` hängt der Import, unter `env -i` kommt `MemoryError`. Laut PR scheitern
    python.org- und BeeWare-Python auf x86_64 gleich. Lösung: `allow-unsigned-executable-memory`
    nur am x86_64-Teil, ein signierter Rauchtest legt eine ctypes-Closure an.
    https://github.com/elfensky/macos-apps-mcp/pull/311
- **Einschätzung für 0.6.0: ja, die Ursachenkette trifft 0.5.x sicher.** Für 0.6.0 deckt die
  Berechtigung den ersten Schritt von `dlmmap` (anonymes RWX) ab; der Temp-Datei-Weg wird gar
  nicht erst betreten. Mit der Berechtigung am tatsächlich laufenden Prozess sollte dieser
  Hänger weg sein.

### A2. Welche Berechtigung genügt? (belegt, Apple-Doku)

- `com.apple.security.cs.allow-jit`: Die App darf W+X-Speicher **mit dem Flag `MAP_JIT`**
  anlegen. `com.apple.security.cs.allow-unsigned-executable-memory`: W+X-Speicher **ohne die
  Einschränkungen, die `MAP_JIT` mit sich bringt**, also auch anonymes RWX ohne `MAP_JIT`.
  `disable-executable-page-protection` hebt alle Code-Signing-Schutzmaßnahmen auf (zu weit).
  Quellen: https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.allow-jit,
  https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.allow-unsigned-executable-memory,
  https://developer.apple.com/documentation/security/hardened-runtime (abgerufen 12.10.2026).
- Da Apples libffi auf x86_64 **kein** `MAP_JIT` setzt, hilft `allow-jit` allein nicht;
  `allow-unsigned-executable-memory` genügt und ist die engste passende Ausnahme. Beide
  zusammen schaden nicht, bringen hier aber nichts. Ob `allow-unsigned-executable-memory` auch
  `MAP_JIT`-Zuweisungen erlaubt: Apple formuliert es als Obermenge („without the restrictions
  imposed by using the MAP_JIT flag“); einen ausdrücklichen Satz dazu gibt es nicht.
- Entitlements wirken **nur am Hauptprogramm des Prozesses**; an Bibliotheken werden sie
  ignoriert. Jeder **weitere ausführbare Prozess** braucht seine eigene Liste. Bei Solidon
  startet der Kernhilfsprozess `sys.executable` (dasselbe Hauptprogramm), trägt also die Liste.
  Quelle: Apple DTS sinngemäß („nur an ausführbaren Programmen sinnvoll, an Bibliotheken
  eher schädlich“), laut Suchauszug aus https://developer.apple.com/forums/thread/768184;
  Repository: `.claude/rules/auslieferung.md`.
- **Einschätzung 0.6.0: nein** (für das Entitlement selbst) — die Wahl ist richtig.
  **Vielleicht**, falls Solidon irgendwann ein anderes Mach-O als eigenen Prozess startet
  (eigenes CLI-Binary, Hilfsprogramm in `Contents/MacOS` oder `Contents/Frameworks`): Das bräuchte
  dieselbe Liste.

### A3. Was setzen andere? (belegt, Doku)

- **Briefcase (BeeWare):** Jede macOS-App bekommt standardmäßig
  `allow-unsigned-executable-memory` **und** `disable-library-validation`.
  https://briefcase.beeware.org/en/stable/reference/platforms/macOS/index.html
- **PyInstaller:** Doku nennt `entitlements_file=`/`--osx-entitlements-file`, schaltet mit einer
  Signatur-Identität automatisch die Hardened Runtime ein und empfiehlt **keine** konkreten
  Ausnahmen; im Bundle-Schritt signiert es mit `--deep`.
  https://pyinstaller.org/en/stable/feature-notes.html (Stand 6.x)
- **python.org selbst:** Weder `build-installer.py` noch eine öffentliche Datei nennt
  Entitlements; der Installer signiert ohne dokumentierte Liste. Prüfbar nur am installierten
  Python mit `codesign -d --entitlements - …/Python.app`. **Nicht belegt.**
- **py2app, Nuitka:** keine offizielle Empfehlung gefunden. Ältere Praxisberichte (z. B.
  https://haim.dev/posts/2020-08-08-python-macos-app, 2020) nennen für Python-Apps genau
  `allow-unsigned-executable-memory`.
- **PyInstaller-Issues 2025/2026 zu Intel-Hängern auf macOS 26:** keine gefunden. Ältere,
  verwandte: https://github.com/pyinstaller/pyinstaller/issues/4629 (2019/2020, Abstürze mit
  Hardened Runtime, NumPy). Die Feldberichte 2026 stammen aus anderen Projekten (A1).

### A4. cffi 2.x und `ffi.callback` (belegt bis auf den Bau des Rads)

- cffi bevorzugt auf macOS libffi über pkg-config (Homebrew) und fällt auf die SDK-libffi
  zurück; im CI-Workflow der macOS-Räder wird Homebrews libffi **deinstalliert** und keine
  eigene gebaut — die Räder linken also Apples `/usr/lib/libffi.dylib` (Schluss aus dem
  Workflow, nicht ausdrücklich dokumentiert).
  Quellen: https://github.com/python-cffi/cffi/blob/main/setup.py,
  https://github.com/python-cffi/cffi/blob/main/.github/workflows/ci.yaml
- `_cffi_backend.c`: Auf Apple mit `FFI_AVAILABLE_APPLE` nimmt `ffi.callback` ab macOS 10.15
  `ffi_closure_alloc` (`CFFI_CHECK_FFI_CLOSURE_ALLOC`) — also denselben Apple-Weg wie ctypes.
  https://github.com/python-cffi/cffi/blob/main/src/c/_cffi_backend.c
- **Einschätzung 0.6.0: ja, betroffen ohne Berechtigung** (wgpu-py legt Rückrufe per
  `ffi.callback` an); **mit** der Berechtigung am Hauptprogramm gedeckt.

### A5. Scheitert auf macOS 26 etwas trotz `allow-unsigned-executable-memory`?

- Kein Bericht gefunden, dass macOS 26 die Semantik geändert hätte. Gegenbelege: t3code#16714
  (15.7.9, mit Berechtigung läuft es), macos-apps-mcp PR #311 (Rauchtest mit Berechtigung grün,
  allerdings auf einem Runner), Solidons eigene Probe am Kundengerät (26.5, mit Berechtigung
  startet es).
- Der Apple-Forumsthread https://developer.apple.com/forums/thread/129546 (2020, cx_Freeze)
  berichtet `MemoryError` trotz der Berechtigung; dort lud der Prozess aber Python aus
  Systempfaden und nicht aus dem Bundle — **keine** übertragbare Aussage.
- Verdacht, dass zusätzlich `disable-library-validation` nötig wäre: in keiner Quelle belegt
  für ctypes/cffi im ABI-Modus. Nötig wird es nur, wenn zur Laufzeit Mach-O geladen werden, die
  nicht die eigene Team-ID tragen (Abschnitt B).
- **Einschätzung 0.6.0: vielleicht, aber nicht über diesen Weg.** Dass die Kundenprobe mit
  `disable-library-validation` lief, beweist nicht, dass 0.6.0 ohne sie läuft — der
  Unterschied liegt in der Bibliotheksprüfung (B), nicht im Speicher.
- **Zusatzbefund CPython 3.14 JIT:** Die python.org-Installer 3.14 enthalten den experimentellen
  JIT, aus (nur `PYTHON_JIT=1` schaltet ihn ein). Ohne diese Variable keine Wirkung; mit ihr
  bräuchte er ausführbaren Speicher. **Nein** für Kunden.

## B. Library Validation

**Regel (belegt, Apple-Doku):** Die Hardened Runtime schaltet die Bibliotheksprüfung ein; der
Prozess lädt nur Code, der von Apple oder mit **derselben Team-ID** wie das Hauptprogramm
signiert ist. `dyld` liefert dann eine ausführliche Fehlermeldung, typisch „mapping process and
mapped file (non-platform) have different Team IDs“. `disable-library-validation` ist für
Programme gedacht, die Plug-ins **anderer Entwickler** laden; Gatekeeper prüft solche Programme
zusätzlich. Ein Provisioning-Profil braucht die Ausnahme nicht (Quinn, Apple DTS, Sept. 2025).
Quellen: https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.disable-library-validation,
https://developer.apple.com/forums/thread/799497, https://developer.apple.com/forums/thread/706437.

**Was dann passiert (belegt am Verhalten von dyld/ctypes):** Kein Hänger. `dlopen` schlägt fehl:
ctypes wirft `OSError`, ein Erweiterungsmodul `ImportError`, Qt überspringt das Plug-in mit
Warnung. Es gibt also einen Fehler oder einen stillen Rückfall, keinen Stillstand.

**Innerhalb des Bundles ist Solidon sauber.** PyInstaller signiert jede gesammelte Binärdatei
beim Bau mindestens ad hoc (frühere fremde Signaturen, etwa die der PSF an `Python.framework`,
sind damit weg); die Notarisierung hätte jede Mach-O ohne Developer ID abgelehnt. Eine Mach-O
mit **fremder** Developer-ID-Signatur bestünde Notarisierung und `--verify --deep --strict`,
scheiterte aber am Kunden-Mac — dieser Fall ist bei Solidon nicht erkennbar. Die Runner
(SIP aus) prüfen die Bibliotheksprüfung nicht, das ist im Repository schon festgehalten.

Typische Fälle außerhalb des Bundles, bewertet für Solidon:

| Fall | Was passiert unter LV | Solidon 0.6.0 |
|---|---|---|
| **3Dconnexion-Treiber** (`/Library/Frameworks/3DconnexionClient.framework`, von `app/ui/spacemouse.py` per `ctypes.CDLL` geladen) | Fremde Team-ID → `OSError`, `load_driver` gibt still `None` (nur Debug-Protokoll), Rückfall auf HID — den 3DxWare aber exklusiv hält | **ja, sicher betroffen**: Auf jedem Mac mit 3DxWare ist die 3D-Maus in 0.6.0 tot, ohne Hinweis. Apple nennt genau diesen Fall (Hardware mit Hersteller-Plug-in) als Grund für die Ausnahme: https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution. Blender signiert laut Suchauszug seines Commits c42b7f8 (2019, Fix T66986 „dylib plugins … not working in code signed release“) mit `allow-unsigned-executable-memory`, `allow-jit` **und** `disable-library-validation` (Seite selbst lieferte 403, also nicht direkt gelesen): https://projects.blender.org/blender/blender/commit/c42b7f843464a810ffd587704ab1ceaf9fee0172 |
| `ctypes.util.find_library` → Homebrew (auf Intel `/usr/local/lib`) | `macholib.dyld_find` liest `DYLD_FALLBACK_LIBRARY_PATH` selbst und sucht standardmäßig in `/usr/local/lib`; die gefundene Bibliothek hat keine passende Team-ID → `OSError` | **vielleicht**: freetype-py sucht erst `libfreetype.dylib` neben dem Paket, nur ohne sie `find_library('freetype')` (https://github.com/rougier/freetype-py/blob/master/freetype/raw.py). Fehlt die gebündelte Datei im Paket, lädt am Kunden-Mac mit Homebrew sonst die fremde — unter LV kommt `RuntimeError('Freetype library not found')`. Prüfen: liegt `freetype/libfreetype.dylib` im App-Baum? |
| `QT_PLUGIN_PATH`/fremde Qt-Plug-ins (Homebrew-Qt) | Qt meldet „not valid for use in process“ und überspringt sie | **nein** (LV schützt hier eher vor einem Absturz durch Plug-ins einer anderen Qt-Version) |
| Druckdialog: PDE-Plug-ins von Druckertreibern | werden nicht geladen, Druckerfunktionen fehlen | **vielleicht**, nur falls Solidon `QPrintDialog` nutzt |
| CoreAudio-HAL-, Eingabemethoden-, Finder-Sync-Erweiterungen | laufen seit Jahren außerhalb des Prozesses | **nein** |
| cffi im API-Modus, zur Laufzeit übersetzte Module | würden nicht laden | **nein** — wgpu-py benutzt cffi im ABI-Modus (`ffi.dlopen` auf die mitgelieferte `libwgpu_native.dylib`) |
| `wgpu-native`, `manifold3d`, OCP, Qt im Bundle | gleiche Team-ID | **nein** |
| Mach-O aus Temp-Ordner (onefile-Entpacken) | würde nicht laden, wenn fremd | **nein** (onedir) |

**Folgerung für den Verdacht „0.6.0 startet weiter nicht“:** Aus der Bibliotheksprüfung folgt
nach allem Gefundenen kein Start-Hänger, höchstens stille Funktionsausfälle (3D-Maus sicher,
Text nur bei fehlender gebündelter FreeType). Die Kundenprobe mit `disable-library-validation`
deckt diese Ausfälle zu, ist aber für den Start trotzdem aussagekräftig.

## C. macOS 26 Tahoe, Qt/PySide6

Allgemein: Ein Qt-Start-Hänger im Cocoa-Plugin auf macOS 26 ist in keiner Quelle beschrieben —
weder für Intel noch für ARM. Die Wiki-Seiten „Known Issues“ von Qt 6.10 und 6.12 nennen für
macOS nur die Liquid-Glass-Zeichenfehler (6.12: macOS- und Linux-Abschnitt leer).
Quellen: https://wiki.qt.io/Qt_6.10_Known_Issues, https://wiki.qt.io/Qt_6.12_Known_Issues
(abgerufen 12.10.2026), https://www.qt.io/blog/qt-on-macos-26-tahoe (05.09.2025).

### C1. Absturz in der Barrierefreiheitsbrücke, wenn ein AX-Client den Baum liest (belegt, offen)

- **QTBUG-149612:** SIGSEGV in `-[QMacAccessibilityElement accessibilitySelectedChildren]`
  (libqcocoa), Variante in `-[QMacAccessibilityElement dealloc]`. Auslöser ist ein Programm, das
  über die Bedienungshilfen den Fensterbaum liest, während sich Tabellen-/Baumzeilen ändern —
  reproduziert mit einem lesenden AX-Client; in den Berichten verdächtig: „Computer Use“-Helfer
  von ChatGPT/Codex, AltTab. Ursache laut Thread: Die Cocoa-Brücke löscht
  `QAccessibleInterface`-Objekte, die `QAccessibleTable` noch über ihre ID im Cache hält.
  Betroffen gemeldet: Qt 6.7.3, 6.9.3, 6.10.1, 6.10.3, 6.11.1, 6.11.2; macOS 26.5.2, 26.6.2,
  27.x; Apple Silicon (Intel nicht berichtet, aber nichts Architekturabhängiges im Fehler).
  Korrektur: Gerrit 765434 bzw. die Reihe 772484–772486, Stand 08.10.2026 **nicht gemergt**,
  keine Fix-Version.
  Quellen: https://github.com/qbittorrent/qBittorrent/issues/24909 (13.09.–08.10.2026; hängt
  danach ~25 s im Absturzdialog), https://github.com/openai/codex/issues/41374 (28.08.2026,
  Qt Creator 20 mit Qt 6.11.1, QGIS 4.0 mit Qt 6.9.3 auf 26.5.2),
  https://github.com/HexRaysSA/ida-sdk/issues/65 (ältere Verwandte QTBUG-134784, behoben 6.8.4).
- **Einschätzung 0.6.0: vielleicht.** Solidon hat mit `ObjectTree`, Verlauf und Prüfbericht
  genau die Ansichten mit wechselnden Zeilen; Qt 6.12.0 trägt die Korrektur nach Stand der
  Quellen nicht. Es wäre ein **Absturz**, kein stiller Start-Hänger, und tritt nur auf, wenn ein
  AX-Client läuft (VoiceOver nicht belegt). Für den Kundenbefund unwahrscheinlich, als
  Absturzquelle auf Macs mit solchen Helfern real.

### C2. Absturz beim Beenden im Pasteboard-Abbau (Einzelbericht)

- Qt 6.11.1 (conda-forge), macOS 26.6, Apple Silicon: `malloc: pointer being freed was not
  allocated` in `QMacMimeRegistry::destroyMimeTypes()` aus `~QCocoaIntegration`, einmal,
  ~85 s nach Start, nicht reproduziert; Verdacht Zwischenablage. Kein QTBUG.
  https://github.com/JamesOBrien2/penzene/issues/481 (28./29.09.2026)
- **Einschätzung: vielleicht** (Absturz beim Beenden, nicht beim Start; Solidon kopiert in die
  Zwischenablage, etwa bei `open_link`). Für den Starttest relevant: Der verlangt „Ende mit 0“.

### C3. Liquid Glass (belegt, Doku)

- Gebaut gegen das macOS-26-SDK schaltet AppKit Liquid Glass ein; Qts Widget-Stile können
  Zeichenfehler zeigen. Auswege: mit Xcode 16 bauen oder `UIDesignRequiresCompatibility = YES`
  in die `Info.plist`. Apple koppelt das Verhalten an die **SDK-Version des gelinkten
  Hauptprogramms** (Forum, iOS-Fall).
  https://wiki.qt.io/Qt_6.10_Known_Issues, https://www.qt.io/blog/qt-on-macos-26-tahoe,
  https://developer.apple.com/forums/thread/832710
- Bei Solidon ist das Hauptprogramm PyInstallers vorgebauter Bootloader; sein SDK entscheidet.
  Nachsehen mit `vtool -show-build Contents/MacOS/<name>`. **Einschätzung: nein** für einen
  Start-Hänger, **vielleicht** für Zeichenfehler; kein Startrisiko.

### C4. Weitere macOS-26-Befunde mit Qt-Bezug

- Qt 6.10.2 behob u. a. QTBUG-141689 (Tahoe: `Qt::WindowModal` sperrt Klicks auf
  `QMessageBox`) und QTBUG-137435 (Absturz in Cocoa-QPA beim Anstecken eines externen
  Bildschirms). https://github.com/qt/qtreleasenotes/blob/dev/qt/6.10.2/release-note.md —
  in 6.12.0 enthalten, **nein**.
- Native Dateidialoge erscheinen nicht (Qt 6.9.2, Tahoe, Ursache CMake-Bau ohne
  `qt_add_executable`, QTBUG-135882 geschlossen): https://forum.qt.io/topic/162825 — **nein**
  (PySide6-Räder).
- PySide6-Menüleistensymbol fehlt auf macOS 26.1, Ursache war ein `exec`-Trampolin des
  Startprogramms, Apple-Fehler FB21015611, kein Ausweg:
  https://developer.apple.com/forums/thread/806691 (Nov. 2025) — **nein** (Solidon hat keinen
  `exec`-Umweg; PyInstaller onedir startet im selben Prozess).
- **`-[NSWorkspace iconForContentType:]`-Hänger:** Bestätigt als **Runner-Eigenheit**:
  `iconservicesagent` stürzt auf der paravirtualisierten GPU des Intel-Images `macos-26-intel`
  in `+[MTLLoader sliceIDForDevice:…]` ab, jede synchrone IconServices-Anfrage hängt; das
  arm64-Image ist nicht betroffen (Icon in 0,02 s), auf echten Macs mit 26.6 laut Melder schnell.
  Ausweg dort: Agent per `launchctl bootout`/`disable` abschalten, dann kommt sofort ein
  Ersatzsymbol. https://github.com/actions/runner-images/issues/14751 (18.09.2026, offen),
  https://github.com/actions/runner-images/issues/14773 (22.–23.09.2026). Das deckt sich mit
  Solidons Befund vom 03.10. **Einschätzung: nein** für Kunden-Macs; für den Runner ließe sich
  mit dem `launchctl`-Ausweg vielleicht doch ein Start **mit** Fenster auf Intel fahren (der
  Schutz der Hardened Runtime fehlt dort trotzdem, SIP aus).
- Zu Barrierefreiheit allgemein (Qt 6.9): Audacity meldet Fehler im Accessibility-Modul nach
  dem Wechsel auf 6.9: https://github.com/audacity/audacity/issues/9429 — Hintergrund, keine
  Startfrage.

## D. Metal / wgpu / pygfx auf Macs

Gelesen im Repository: `app/ui/render/factory.py` fragt
`wgpu.gpu.request_adapter_sync(power_preference="high-performance")`, die Ansicht ist ein
rendercanvas-Qt-Widget mit `present_method="screen"` (natives Fenster, `WA_PaintOnScreen`), die
`Info.plist` trägt `NSHighResolutionCapable` und `LSMinimumSystemVersion`, aber kein
`NSSupportsAutomaticGraphicsSwitching`.

### D1. Welche MSL-Version wgpu wählt — nach OS, nicht nach GPU (belegt, Quelltext)

- wgpu-hal wählt die Metal-Shading-Language-Version **allein nach der laufenden
  OS-Version** (`available!(…)`), nicht nach `supportsFamily`. Im Tag **v29.0.0**: macOS ≥ 15 →
  `Version3_2`, ≥ 14 → 3.1, ≥ 13 → 3.0 usw.; **kein** 4.0-Zweig.
  https://github.com/gfx-rs/wgpu/blob/v29.0.0/wgpu-hal/src/metal/adapter.rs
- Auf **trunk** (und laut Fremd-PR in wgpu 30) steht davor neu:
  `if available!(macos = 26.0, …) { MTLLanguageVersion::Version4_0 }`.
  https://github.com/gfx-rs/wgpu/blob/trunk/wgpu-hal/src/metal/adapter.rs (abgerufen
  12.10.2026), https://github.com/stevepryde/sp-fidelity/pull/3
- Folge in fremden Apps (Oktober 2026): Auf Intel-/AMD-Macs, deren Treiber den gewählten
  Standard nicht kennen, scheitert schon die **Validierungs-Pipeline für indirekte Aufrufe**,
  die wgpu beim `request_device` baut: `invalid value 'metal3.2' in '-std=metal3.2'` →
  `RequestDeviceError … Device(Lost)`. Betroffen in den Berichten: Iris Pro (2015),
  Radeon R9 M295X (2014) unter **macOS 15 mit OpenCore Legacy Patcher**, also nicht offiziell
  unterstützte Macs; Ausweg `SYSTEM_VERSION_COMPAT=1` (dann meldet macOS eine alte Version).
  https://github.com/storytold/designcraft/issues/334 (10.10.2026, wgpu-hal 30.0.1),
  https://github.com/storytold/craft-launcher/issues/38 (10./11.10.2026),
  https://github.com/gfx-rs/wgpu/issues/10244 (02.09.2026, MacBook Pro 2015, macOS 12.7.6,
  wgpu 30.0.0: „Compiler encountered an internal error“ in derselben Pipeline).
- **Einschätzung 0.6.0: vielleicht, eher nein für das Kundengerät.** Die installierte
  wgpu-py 0.32.0 erwartet wgpu-native **29.0.1.1** (`wgpu/backends/wgpu_native/__init__.py` in
  der `.venv`), und dessen `Cargo.toml` pinnt wgpu-core/-hal **29.0.1**; dort endet die Kette bei
  `Version3_2` (https://github.com/gfx-rs/wgpu/blob/v29.0.1/wgpu-hal/src/metal/adapter.rs,
  https://github.com/gfx-rs/wgpu-native/blob/v29.0.1.1/Cargo.toml) — also MSL 3.2 auf macOS 26,
  kein 4.0. Der MacBookPro16,1 läuft offiziell auf macOS 26 mit Apples aktuellen Intel-/AMD-Treibern,
  die 3.2 kennen sollten (kein Fremdbericht über Fehler dort). **Aber:** Ein späteres Update auf
  wgpu-native ≥ 30 setzt auf macOS 26 MSL 4.0; ob Apples Intel-/AMD-Treiber `metal4.0`
  annehmen, ist **nirgends belegt** (Metal 4 ist Apple-Silicon-Funktion). Das wäre dann ein
  Startabbruch genau auf den Intel-Macs. Vor jedem wgpu-py-Update auf Intel/macOS 26 prüfen.
  Und: Ein Kunde mit einem per OCLP gepatchten alten Intel-Mac trifft schon heute die
  3.2-Falle — Solidon sollte dann einen lesbaren Fehler zeigen statt zu enden.

### D2. Intel-spezifische Metal-Fehler in wgpu (belegt, Issue)

- gfx-rs/wgpu#10309 (11.09.2026, offen): Auf Intel-Mac-GPUs liefert das Abtasten von
  `stencil8`-Texturen immer 0 (Mac mini 2018, macOS 14); Regression zwischen zwei Commits um
  #9553/#9763; Dawn umgeht es mit `depth32float-stencil8`.
  https://github.com/gfx-rs/wgpu/issues/10309 — **vielleicht** (nur falls pygfx/Solidon
  Stencil abtastet; Kopien gehen).
- gfx-rs/wgpu#8768 → wgpu-native#541: stetiges Speicherleck auf Metal (~0,5–1 MB je 10 s),
  Intel und Apple Silicon. https://github.com/gfx-rs/wgpu/issues/8768,
  https://github.com/gfx-rs/wgpu-native/issues/541 — **vielleicht** bei langen Sitzungen
  (Stand der Behebung in v29 nicht geprüft).
- actions/runner-images#14836 (05.10.2026, offen): `macos-15-intel`-VM: Metal-GPU-Hänger und
  falsche Ergebnisse bei frisch angelegten Multisample-Texturen; arm64-Images nicht betroffen,
  vermutlich die paravirtualisierte GPU. https://github.com/actions/runner-images/issues/14836
  — **nein** für Kunden, aber ein Grund mehr, warum der Intel-Runner kein Beleg für die
  3D-Ansicht ist (pygfx nutzt MSAA).

### D3. Zwei GPUs (UHD 630 + Radeon Pro 5300M/5500M)

- Apple: Auf Macs mit mehreren GPUs ist der Systemstandard die diskrete GPU;
  `MTLCreateSystemDefaultDevice` schaltet auf sie um. `NSSupportsAutomaticGraphicsSwitching`
  wirkt laut Forenberichten nur auf OpenGL, nicht auf Metal.
  https://developer.apple.com/documentation/metal/getting-the-default-gpu,
  https://developer.apple.com/forums/thread/127480 (Big-Sur-Bericht: Schalter ohne Wirkung).
- Ghostty und Zed wählen auf solchen Macs bewusst die **integrierte** GPU (Akku, Wärme, keine
  Umschaltung) bzw. fallen auf sie zurück, wenn `MTLCopyAllDevices` nichts liefert.
  https://git.uoc.run.place/Applied-Software/ghostty/commit/20a77123d43841fc873dc3b57d337ae6cad51868,
  https://git.secluded.site/zed/commit/bb514c158e1604916b32fc8c9bbe602a78727742
- wgpu: `PowerPreference` lässt sich per Umgebungsvariable `WGPU_POWER_PREF=low|high`
  übersteuern. https://wgpu.rs/doc/src/wgpu_types/adapter.rs.html
- VectorCraft (wgpu, Okt. 2026): Metal meldet keine PCI-IDs, beide GPUs eines Dual-GPU-Macs
  hatten den Adapterschlüssel `Metal:0000:0000`; ein Neustart nach einem Fehler der einen GPU
  verwarf beide. https://github.com/storytold/vectorcraft/pull/658 — Hinweis für jeden eigenen
  Adapterspeicher.
- Nutzerberichte zu Tahoe auf MacBook Pro 2019: Ruckeln, das mit abgeschalteter automatischer
  Umschaltung verschwand; Radeon-Bildfehler in Camera Raw. Forenvermutungen.
  https://discussions.apple.com/thread/256152069,
  https://community.adobe.com/questions-563/intermittent-black-window-in-camera-raw-on-intel-mac-182211
- **Einschätzung: vielleicht** (Akku/Wärme durch die erzwungene Radeon; kein Start-Hänger
  belegt). Für die Diagnose am Kundengerät taugt `WGPU_POWER_PREF=low` beim Start aus dem
  Terminal als Gegenprobe.

### D4. rendercanvas mit Qt

- rendercanvas nimmt im Qt-Backend standardmäßig `bitmap`; `screen` (Widget über `winId()`)
  „kann Probleme machen“, vor allem unter manchen Linux-Umgebungen und in einem
  `QDockWidget`; macOS wird nicht eigens genannt. Unter Wayland setzt rendercanvas Qt auf
  XWayland (`QT_QPA_PLATFORM=xcb`), wenn es das `wl_display` nicht bekommt; ein nativer
  Wayland-Weg für Qt kam erst nach 2.7.2 (PR #233).
  https://rendercanvas.readthedocs.io/latest/backends.html,
  https://github.com/pygfx/rendercanvas/pull/233
- **Einschätzung: nein** für einen Start-Hänger (kein macOS-Bericht gefunden); Solidon hat
  `screen` bewusst gewählt.

### D5. macOS 26 und Metal allgemein

- Kein wgpu-Issue zu einer Tahoe-Regression auf Intel gefunden. Bekannt sind Apple-Silicon-
  Fälle (Metal-4-Zeitstempel liefern 0: https://github.com/gfx-rs/wgpu/issues/9414; llama.cpp-
  Absturz nach 26.3) — **nein** für den Start.

## E. OCP und weitere native Räder auf macOS x86_64

- **ocp-build-system#67 (Solidons eigene Meldung, 10.10.2026, offen, ohne Antwort):** Die
  `macosx_11_0_x86_64`-Räder von `cadquery-ocp-novtk` (7.9.3.1.1, 8.0.1.0.0, 8.0.1.1.0)
  kodieren bei Funktionen mit Stapelprobe (`___chkstk_darwin` vor `sub rsp`) den Versatz der
  Rahmengröße im `STACK_IND`-Eintrag ein bis zwei Byte zu weit; jede OCCT-Ausnahme durch einen
  Rahmen > 4 KB endet mit SIGBUS in `_Unwind_RaiseException`. Vorgeschlagene Abhilfe beim Bau:
  Rahmenzeiger behalten oder `-Wl,-no_compact_unwind`. Keine Reaktion der Betreuer, keine
  Labels. https://github.com/CadQuery/ocp-build-system/issues/67 — **ja**, betrifft 0.6.0 ohne
  das eigene Werkzeug; mit `fix_unwind_info.py` laut Repository behoben. Kein Start-Hänger
  (OCC-Ausnahmen kommen erst bei Operationen).
- Allgemeiner Hintergrund zu Compact-Unwind-Fehlern durch Linker (ld64.lld, gleiche
  Fehlerklasse): https://github.com/llvm/llvm-project/issues/59070; Kodierung von
  `STACK_IND`: https://maskray.me/blog/2020-11-08-stack-unwinding. Ein Bericht, der den Fehler
  Xcode 16/ld-prime zuschreibt, wurde **nicht** gefunden.
- **NumPy ≥ 2.4: x86-64-Grundlinie ist x86-64-v2** (SSE4.2, POPCNT, CX16, LAHF); AVX2/AVX-512
  werden zur Laufzeit gewählt. Coffee Lake erfüllt v3 — **nein** für den Kunden-Mac; relevant
  für alte Linux-PCs (H). https://numpy.org/doc/stable/release/2.4.0-notes.html,
  https://numpy.org/doc/stable/reference/simd/build-options.html
- **NumPy/SciPy-Räder `macosx_14_0_x86_64` linken Accelerate (NEWLAPACK, ILP64)**; sie laufen
  erst ab macOS 14 (rotki 1.44.0 startete darunter nicht: „symbol not found“).
  https://github.com/rotki/rotki/issues/13216, https://github.com/numpy/numpy/pull/25255 —
  **nein**, Solidons Mindestversion ist 14; nur bei einer Senkung von `LSMinimumSystemVersion`
  ein Startabbruch. Ein Präzisionsunterschied von `np.matmul` mit Accelerate ist gemeldet
  (https://github.com/numpy/numpy/issues/26791, Architektur offen) — **vielleicht** für
  Bitgleichheitstests zwischen Plattformen, kein Startthema.
- manifold3d, Pillow (libavif), PySide6_Addons (FFmpeg) auf Intel-macOS 26: **keine** fremden
  Berichte gefunden. Solidons eigener Scan (RM-770) bleibt die einzige Quelle; FFmpeg/libavif
  sind C, also kein Ausnahmepfad.

## F. Gatekeeper / Installer

- **Notarisierte `.pkg` auf macOS 26.3 von `spctl --type install` abgelehnt** (März 2026):
  Developer-ID-Installer-Signatur, `notarytool` „Accepted“, Doppelklick zeigt nur „In den
  Papierkorb“. Quinn (Apple DTS) kannte den Fall nicht und verdächtigte die Warnung
  „unable to build chain to self-signed root“ bei `productbuild`/`productsign` (fehlende
  Zwischenzertifikate im Schlüsselbund). Ungelöst.
  https://developer.apple.com/forums/thread/817887 — **vielleicht**: Prüfen, ob Solidons
  `productbuild`-Lauf dieselbe Warnung schreibt; Solidons Kunden kamen allerdings bis zur
  Installation (das Problem lag beim Start).
- **Apple änderte Notarisierungstickets, Gatekeeper lehnte zeitweise ab, quarantänierte
  Binärdatei hing > 120 s in `_dyld_start`** (mitmproxy 12.2.3, Python 3.14.4, arm64, macOS
  26.5.2/26.6/26.6.2; Ticketdaten bei Apple am 06.10.2026 geändert, am 08.10. wieder
  angenommen, ohne Zutun des Projekts). Das Archiv trug **kein** gestapeltes Ticket.
  https://github.com/mitmproxy/mitmproxy/issues/8474 — **vielleicht** als Erklärung für
  einzelne lange Erststarts in genau diesem Zeitraum; Solidon stapelt App und Paket, die per
  `.pkg` installierte App trägt keine Quarantäne. Für den Intel-Befund **nein** (ad hoc lief es
  sofort, mit Quarantäne-unabhängigem Unterschied).
- **syspolicyd prüft beim Erststart große Bündel lange**, nach einem macOS-Update erneut;
  Berichte zu `syspolicyd`/`trustd`-CPU-Spitzen bei großen Apps auf macOS 26.5.1.
  https://lapcatsoftware.com/articles/2024/2/3.html,
  https://github.com/openai/codex/issues/25719 — **vielleicht** (Sekunden bis Minuten beim
  ersten Start, kein Dauerhänger; Solidon hat das am Runner mit 8,5–30 s gemessen).
- **macOS 26.5 schloss einen Gatekeeper-Umgehungsweg über Disk-Images** (CVE-2026-28954).
  https://support.apple.com/en-us/126794 bzw. Release-Notizen 26.5 — **nein** (Solidon
  liefert `.pkg`).
- **XProtect/PyInstaller:** Kein macOS-Fehlalarm gegen PyInstaller-Apps 2025/2026 gefunden;
  bekannt sind Windows-Virenscanner-Fehlalarme gegen den gemeinsamen Bootloader
  (https://github.com/pyinstaller/pyinstaller/issues/8164) und vereinzelte XProtect-Fehlalarme
  anderer Software 2026 (z. B. https://github.com/civarry/lasso-app/issues/2). **Nein** für den
  Befund (XProtect verschiebt in den Papierkorb und meldet es, statt still zu hängen).
- App Translocation: betrifft nur quarantänierte Apps, die nicht verschoben wurden; per `.pkg`
  installierte Apps tragen keine Quarantäne. **Nein.**

## G. Apple Silicon

- **libffi:** Auf arm64 nimmt Apples libffi die Trampolintabelle (A1), braucht nie W+X. Die
  Berechtigung schadet dort nicht; Solidon setzt sie bewusst auf beiden Architekturen.
- **Barrierefreiheits-Absturz QTBUG-149612** ist bisher **nur** auf Apple Silicon gemeldet
  (C1) — **vielleicht**.
- **Gatekeeper-Ticketstörung Oktober 2026** traf arm64 (F) — **vielleicht** für Erststarts.
- **wgpu/Metal:** Auf macOS 26 liefern `MTLCounterSampleBuffer`-Zeitstempel nur Nullen
  (Metal 4 ersetzt sie durch `MTL4CounterHeap`); betrifft nur Zeitmessungen.
  https://github.com/gfx-rs/wgpu/issues/9414 — **nein** für den Start.
- **Ad-hoc-Pflicht:** Auf Apple Silicon muss jede Mach-O signiert sein, auch ad hoc;
  PyInstaller signiert nach dem Umschreiben der Ladebefehle neu.
  https://pyinstaller.org/en/stable/feature-notes.html — erledigt, **nein**.
- Ein falsch heruntergeladenes Intel-Paket läuft auf Apple Silicon unter Rosetta 2 und trifft
  dann denselben x86_64-libffi-Weg; mit der Berechtigung gedeckt. **Nein.**
- Keine PyInstaller-, PySide6- oder pygfx-Issues 2026 zu Start-Abstürzen auf macOS 26 arm64
  gefunden.

## H. Linux

Gelesen im Repository: Linux baut fest auf `ubuntu-24.04` und bündelt dessen
Systembibliotheken samt `libxcb-cursor0`; AppImage mit statischem Type-2-Laufzeitkern 20251108;
Flatpak auf `org.freedesktop.Platform//26.08` mit `--socket=x11`, `QT_QPA_PLATFORM=xcb`,
`--device=dri`, `--filesystem=home`, `--talk-name=org.freedesktop.Flatpak`.

| Thema | Befund (Quelle, Datum) | Solidon 0.6.0 |
|---|---|---|
| **x86-64-v2 durch Qt ≥ 6.10** | PySide6 6.10.0 bricht schon beim Import von QtCore ab: „Incompatible processor. This Qt build requires the following features: sse4.2 popcnt“; 6.9.3 lief auf derselben SSE4.1-CPU. Grund laut Moderator: Qts Linux-Binärdateien werden seit 6.11 auf RHEL 9.6 gebaut, dessen Grundlinie x86-64-v2 ist; keine offizielle Ankündigung. https://forum.qt.io/topic/165068 (07.–09.09.2026). Dazu NumPy ≥ 2.4 mit Grundlinie x86-64-v2 (E). | **ja** für PCs ohne SSE4.2/POPCNT (Core 2, Phenom II, frühe Atom/Celeron, vor ~2009/2010). Windows/macOS-Binärdateien sind im Thread nicht behandelt. Gehört in die Systemanforderungen; vor Qt passiert nichts, also kein lesbarer Fehler im Fenster |
| **glibc-Untergrenze** | Linux-Pakete erben die glibc des Bauservers; das Repository nennt das selbst (`build.yml`, Z. 592–598). PySide6-Räder: lange `manylinux_2_28`; Qt 6.11 wird auf RHEL 9.6 gebaut (glibc 2.34) — das Tag von 6.12.0 selbst wurde **nicht** nachgelesen. https://pypi.org/project/PySide6-Essentials/ | **ja, bekannt**: Mit Ubuntu-24.04-Bau (glibc 2.39) scheitern Ubuntu 22.04, Debian 12 und ältere mit „GLIBC_2.3x not found“. Prüfenswert, ob Website/Download das sagt |
| **libfuse2 für AppImages** | Ubuntu 24.04 benennt das Paket `libfuse2t64`; klassische Laufzeitkerne brauchen es. Der neue Type-2-Kern ist statisch gelinkt: „libfuse2 is no longer required“. https://github.com/AppImage/type2-runtime, https://github.com/AppImage/AppImageKit/wiki/FUSE | **nein** (statischer Kern). FUSE selbst (Kernelmodul, `fusermount3`) bleibt nötig; in Containern/WSL ohne FUSE hilft `--appimage-extract-and-run` |
| **`libxcb-cursor0`** | Seit Qt 6.5 Pflicht für das xcb-Plugin; fehlt auf manchen Ubuntu/GNOME-Installationen. Die Meldung „xcb-cursor0 … is needed“ erscheint auch, wenn gar kein Display da ist. https://pagure.io/fedora-kde/SIG/issue/480, https://obj-sys.com/blog/linux-gui-dependencies-on-libxcb-cursor-package.html | **nein** (mitgebündelt) |
| **Wayland/X11** | GNOME 50 hat die X11-Sitzung entfernt, XWayland bleibt. https://linuxiac.com/gnome-50-ends-the-x11-era-after-decades/, https://phoronix.com/news/GNOME-50-Alpha. rendercanvas legt Qt auf XWayland, wenn es kein `wl_display` bekommt; nativer Wayland-Weg erst nach 2.7.2. https://rendercanvas.readthedocs.io/latest/backends.html | **vielleicht**: Eine Sitzung ohne XWayland (selten, Kiosk/minimal) startet das xcb-Plugin nicht. Unter XWayland mit NVIDIA: Vulkan-Präsentation braucht explizite Synchronisation (Treiber ≥ 555, Xwayland mit Explicit-Sync); ältere Treiber froren in `vkQueuePresentKHR` ein (Forenanalyse). https://forums.developer.nvidia.com/t/the-possible-root-cause-of-the-vk-khr-present-wait-and-vulkan-related-freezes/328932, https://9to5linux.com/explicit-gpu-synchronization-for-xwayland-is-now-finally-merged-into-xorg-server |
| **NVIDIA im Flatpak** | Die Erweiterung `org.freedesktop.Platform.GL.nvidia-<Version>` muss exakt zur Kernelmodul-Version passen; nach einem Treiberupdate scheitert Vulkan („Could not create Vulkan instance“), bis `flatpak update` die passende holt. https://wiki.gentoo.org/wiki/Steam/Client_troubleshooting, https://github.com/flatpak/flatpak/issues/1786. Vulkan-Programme **hängen**, wenn NVIDIA- und Mesa-Rückfalltreiber zugleich sichtbar sind (Jetson/aarch64, Ausweg `FLATPAK_GL_DRIVERS=nvidia-…`): https://github.com/flatpak/flatpak/issues/5623 (offen seit 12/2023). Swapchain-Fehler mit NVIDIA 575 unter Wayland: https://github.com/flatpak/flatpak/issues/6243 (07–08/2025) | **vielleicht**: Solidon würde bei fehlendem NVIDIA-ICD auf lavapipe (CPU) fallen — startet, aber zäh; ein Hänger wie #5623 ist auf x86_64 nicht belegt |
| **Keine/alte Vulkan-GPU** | wgpu-native braucht Vulkan; ohne Hardware-Treiber bleibt der Mesa-Softwareadapter llvmpipe/lavapipe, den wgpu als Rückfall zuletzt reiht. https://wgpu-py.readthedocs.io/en/stable/start.html, https://github.com/gfx-rs/wgpu/issues/3033 | **vielleicht**: Im AppImage/Archiv hängt es an `mesa-vulkan-drivers` des Hosts; im Flatpak liefert die GL-Erweiterung Mesa mit (ob lavapipe in 26.08 enthalten ist, wurde nicht belegt) |
| **Portale für Dateidialoge** | Qt nutzt im Flatpak das FileChooser-Portal; gewählte Dateien erscheinen unter `/run/user/$UID/doc/…`, freigegeben wird nur die gewählte Datei, Nachbardateien nicht. https://github.com/flatpak/flatpak/wiki/Portals | **nein** innerhalb von `$HOME` (`--filesystem=home`), **vielleicht** für Dateien außerhalb (USB-Stick, `/mnt`), wo z. B. OBJ+MTL oder relative Verweise ins Leere gehen |

## Wenn 0.6.0 doch hängt — Restrisiken und Diagnoseweg

Belegte Restrisiken, nach Wahrscheinlichkeit für das Kundengerät geordnet:

1. **Falsche Kopie gestartet.** `pkgbuild`-Pakete sind standardmäßig umziehbar: Findet der
   Installer die App nicht am Zielort, aktualisiert er eine Kopie gleicher Bundle-ID an anderer
   Stelle. https://scriptingosx.com/2017/05/relocatable-package-installers-and-quickpkg-update/,
   https://developer.apple.com/forums/thread/743964 — Das Repository kennt das (`build.yml`
   Z. 1798). Beim Kunden liegen nach den Gegenproben womöglich ad hoc signierte Kopien herum.
   Vor dem Urteil: `mdfind "kMDItemCFBundleIdentifier == '<Bundle-ID>'"`, dann an genau der
   gestarteten Kopie `codesign -dv --entitlements - --xml /Applications/Solidon3D.app` und
   `CFBundleShortVersionString` lesen.
2. **Ein weiterer Prozess ohne Liste.** Jede andere ausführbare Mach-O, die Solidon als eigenen
   Prozess startet, bräuchte dieselbe Berechtigung (A2). Der Kernhilfsprozess ist
   `sys.executable` und damit gedeckt.
3. **Barrierefreiheits-Absturz QTBUG-149612** bei laufendem AX-Client (C1) — Absturz mit
   Bericht, kein stiller Hänger.
4. **wgpu bei späterem Update** (MSL 4.0 auf macOS 26 ab wgpu-hal 30, D1) — heute nicht.
5. **Gatekeeper-Erstprüfung/Ticketstörung** (F) — lange Erststarts, aber vorübergehend.

Diagnose ohne Rätselraten (Apple DTS: „Temporarily disable the hardened runtime and see if
the problem goes away“, dann die Stelle eingrenzen statt Ausnahmen zu stapeln):
https://developer.apple.com/forums/thread/707743. Für den Stapel eines hängenden Prozesses
mit Hardened Runtime eignet sich `sudo spindump <pid> 10 -onlyTarget` oder Aktivitätsanzeige →
„Prozess analysieren“; `task_for_pid` (also `lldb`, vermutlich auch `sample`) ist bei Hardened
Runtime ohne `get-task-allow` gesperrt — so belegt für `task_for_pid`
(https://afine.com/to-allow-or-not-to-get-task-allow-that-is-the-question); dass `spindump`
ohne Task-Port auskommt, ist aus der Manpage
(https://manp.gs/mac/8/spindump) und der Praxis der fremden Berichte geschlossen (draftomen
hat seinen Hänger per Prozessstichprobe gefunden), nicht ausdrücklich dokumentiert.

## Die fünf wichtigsten Befunde

1. **Ursache und Abhilfe sind am Quelltext belegt.** Apples libffi ist auf x86_64 mit
   `FFI_MMAP_EXEC_WRIT` gebaut (arm64: Trampolintabelle); `dlmmap` versucht erst anonymes RWX und
   kreist bei `EPERM` ohne Zähler über Temp-Dateien (`goto retry_open`). CPython 3.14 legt seit
   gh-128485 beim Laden von `_ctypes` immer eine Closure an; cffi nimmt denselben Apple-Weg.
   Apple-Doku: `allow-unsigned-executable-memory` erlaubt W+X **ohne** `MAP_JIT`, `allow-jit` nur
   **mit** — 0.6.0 hat die richtige Ausnahme, an der richtigen Stelle, in der richtigen
   Signierreihenfolge.
   https://github.com/apple-oss-distributions/libffi/blob/main/darwin/include/fficonfig_x86_64.h,
   https://github.com/apple-oss-distributions/libffi/blob/main/src/closures.c,
   https://github.com/python/cpython/issues/128485,
   https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.allow-unsigned-executable-memory
2. **Drei fremde Feldberichte bestätigen Bild und Abhilfe auf echten Intel-Macs** (Oktober
   2026): draftomen#905 (macOS 26.7.1, ctypes-Import hängt, arm64 heil, Runner grün),
   peon-ping#589 (26.6.2, Stapel `ffi_closure_alloc` → `dlmmap` → `mkostemp`; auf 15.7.7 lief
   der Ausweichweg noch), t3code#16714 (15.7.9, mit der Berechtigung neu signiert läuft es).
   https://github.com/andreagrandi/draftomen/issues/905,
   https://github.com/PeonPing/peon-ping/issues/589,
   https://github.com/pingdotgg/t3code/issues/16714
3. **Ohne `disable-library-validation` lädt der 3Dconnexion-Treiber nicht.**
   `spacemouse.load_driver` lädt `/Library/Frameworks/3DconnexionClient.framework` per
   `ctypes.CDLL`; fremde Team-ID → `OSError` → still `None`, und HID ist auf dem Mac von 3DxWare
   belegt. Apple selbst: „If your app works with this kind of hardware, be sure to declare the
   com.apple.security.cs.disable-library-validation to load the corresponding plug-ins.“ Kein
   Hänger, aber ein sicherer Funktionsausfall in 0.6.0, den die Kundenprobe (mit der Ausnahme)
   nicht zeigen konnte.
   https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
4. **wgpu wählt die MSL-Version nach OS, nicht nach GPU — heute 3.2, nach dem nächsten
   wgpu-native-Sprung 4.0 auf macOS 26.** Solidons wgpu-native 29.0.1.1 (wgpu-hal 29.0.1) endet
   bei 3.2; trunk/wgpu 30 setzt auf macOS ≥ 26 `Version4_0`. Fremde wgpu-30-Apps brechen auf
   Intel-/AMD-Treibern, die den Standard nicht kennen, schon in `request_device` ab
   (`invalid value 'metal3.2'`, OCLP-Macs). Vor jedem wgpu-py-Update auf einem Intel-Mac mit
   macOS 26 prüfen.
   https://github.com/gfx-rs/wgpu/blob/trunk/wgpu-hal/src/metal/adapter.rs,
   https://github.com/gfx-rs/wgpu/blob/v29.0.1/wgpu-hal/src/metal/adapter.rs,
   https://github.com/storytold/designcraft/issues/334
5. **Linux: Qt ≥ 6.10 und NumPy ≥ 2.4 verlangen x86-64-v2.** PySide6 6.10 bricht auf CPUs ohne
   SSE4.2/POPCNT beim Import mit „Incompatible processor … sse4.2 popcnt“ ab (laut Moderator,
   weil Qt seine Linux-Binärdateien inzwischen auf RHEL 9 baut, 6.11 auf 9.6; offiziell nicht
   angekündigt); dazu erbt das Paket die glibc von Ubuntu 24.04. Beides gehört in die
   Systemanforderungen. Auf macOS gilt das Gegenstück nicht für den Kunden-Mac (Coffee Lake).
   https://forum.qt.io/topic/165068, https://numpy.org/doc/stable/release/2.4.0-notes.html

Nebenbefunde mit Wert: QTBUG-149612 (Qt-Barrierefreiheit stürzt bei AX-Clients ab, 6.7–6.11
gemeldet, ungemergt, C1); der `iconForContentType`-Hänger ist als Eigenheit des
`macos-26-intel`-Images bestätigt (actions/runner-images#14751/#14773, mit
`launchctl bootout`-Ausweg, C4).
