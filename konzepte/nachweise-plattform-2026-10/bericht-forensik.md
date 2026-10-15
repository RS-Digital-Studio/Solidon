# Forensik der gebauten Pakete Solidon 0.6.0 (Tag-Lauf 38170638968)

Stand: 12.10.2026, laufend ergänzt. Messskripte in `skripte/`; die
heruntergeladenen Artefakte wurden danach gelöscht. Nichts im Repository
geändert, kein fremdes Programm ausgeführt.

Legende Schwere: **Start** = verhindert den Start, **später** = wirkt erst bei
einer Funktion, **kosmetisch**. „Gemessen" = am Artefakt belegt,
„vermutet" = Schluss ohne Gerät.

## Vorgehen

- Artefakte aus Lauf 38170638968 mit `gh run download` je in einen eigenen
  Ordner: `solidon3d-macos-app-signed-X64` / `-ARM64` (ditto-Zips der
  gestapelten App), `solidon3d-macos-final-private-X64` (.pkg),
  `solidon3d-linux` (AppImage + Flatpak). Logs der Jobs 114568087314 (Paket
  Intel), 114570963023 (Signieren Intel), 114573051036 (Releaseakte Intel)
  unter `forensik\logs\`.
- Eigene venv `forensik\venv` (capstone 5.0.7, lief 1.0.0, pyelftools,
  asn1crypto). Ausgewertet wird direkt aus dem Zip (Symlinks bleiben
  Symlinks); jedes Skript mit `python -I` aus `forensik\skripte\`.
- `skripte\macho.py`: eigener Mach-O-Leser (Fat/thin, Ladebefehle,
  SuperBlob, CodeDirectory v0x20500, Seitenhashes, Spezialslots).
  `skripte\bundle_pruefen.py` → `ergebnis\x64.json` / `arm64.json`,
  `skripte\auswerten.py` → `ergebnis\*-auswertung.txt`,
  `skripte\frameworks_pruefen.py` (verschachtelte Siegel),
  `skripte\pkg_vergleich.py` (pkg-Payload gegen App-Zip, beide
  Architekturen), `skripte\importe.py` (Systemimporte der 26er-Dateien),
  `skripte\isa_scan.py` + `isa_auswerten.py` (capstone),
  `skripte\textrelocs.py`, `skripte\elf_pruefen.py` + `elf_auswerten.py`
  (pyelftools). Ergebnisse unter `forensik\ergebnis\`.
- Zusätzlich geladen: `solidon3d-macos-final-private-ARM64` (.pkg). Nicht
  geladen: `solidon3d-linux-release-input` (enthält nur zusätzlich das nicht
  veröffentlichte Tar-Archiv) und das Paket 0.5.3 (Downloadstatistik).

## Befunde macOS X64

### M1 Signatur aller Mach-O — unauffällig (gemessen)

- 382 Mach-O im Bundle (1 MH_EXECUTE, 121 Dylibs, 260 Bundles/.so), alle
  `x86_64` (kein `x86_64h`, kein arm64, kein Fat). Erkannt an der Magic, nicht
  an der Endung; unter `Contents/Resources` liegt **kein** Mach-O als echte
  Datei, nur 393 Symlinks nach `Frameworks/`.
- Jede Datei trägt `LC_CODE_SIGNATURE`; 389 CodeDirectories (7 Dateien mit
  zusätzlicher SHA-1-CD), **alle** Version ≥ 0x20500, Flags genau `runtime`
  (0x10000), **Team-ID D6D857LWR7**, kein `adhoc`, kein `linker-signed`.
- CMS in allen 382: Kette „Developer ID Application: Robert Schneider
  (D6D857LWR7)“ → „Developer ID Certification Authority G2“ → „Apple Root CA“,
  `messageDigest` = SHA-256 der CD (gerechnet), Zeitstempel-Token vorhanden.
- **Seitenhashes: alle Seiten aller 389 CDs stimmen** mit den Dateibytes
  überein (nicht nur Stichproben: Python-Framework, `_ctypes`,
  `_cffi_backend`, QtCore, libqcocoa, wgpu-native, OCP inklusive).
  Spezialslots (Requirements, Entitlements XML/DER) stimmen in allen CDs.
  Keine Datei wurde nach dem Signieren verändert.
- `fix_unwind_info.py --codesign` läuft im Paketjob **vor** PyInstaller
  (build.yml Z. 658) und ad hoc; die Developer-ID-Signatur entsteht erst im
  Job `macos-app-sign` (Z. 1428 f.) über das ganze Bundle mit `--deep`. Die
  ad-hoc-Signatur aus dem Unwind-Fix ist im Endprodukt nirgends übrig
  (0 ad-hoc-CDs). Z. 1749 (Releaseakte) korrigiert nur die
  Prüfumgebung des Runners, nicht das Paket.
- Äußeres Siegel `Contents/_CodeSignature/CodeResources`: 931 Ressourcen-
  Hashes ok, 0 falsch; 364 verschachtelte Code-Einträge, deren `cdhash` zur
  Datei passt; 342 Symlinks ok; 17 Framework-Bundles (16 Qt, Python) mit
  passendem `cdhash`, innerem `CodeResources` und Info.plist-Slot.
  Unversiegelt sind nur die Framework-Strukturlinks (`Versions/Current`
  usw., normal) und `Contents/CodeResources` = das angeheftete
  Notarisierungsticket (Magic `s8ch`).
- Hauptprogramm: Info.plist-Slot und CodeResources-Slot ok, CD-Runtime-Version
  26.2.0, `execSegFlags` 0x1 (main binary).
- `MacOS/THIRD-PARTY-NOTICES.md` (keine Mach-O, liegt im Code-Ordner) ist als
  „verschachtelter Code“ versiegelt; seine Signatur steckt in erweiterten
  Attributen (AppleDouble `._THIRD-PARTY-NOTICES.md`, 9655 Byte). Das .pkg
  trägt dieselbe AppleDouble-Datei mit — siehe M5.
- Schwere: keine. Bibliotheksprüfung (Library Validation) und Hardened
  Runtime würden auf einem Kunden-Mac **keine** dieser Dateien ablehnen.
  Beleg: `ergebnis\x64-auswertung.txt`, `ergebnis\x64-frameworks.txt`.

### M2 Entitlements (gemessen)

Nur das Hauptprogramm `Contents/MacOS/Solidon3D` trägt Entitlements, XML
wörtlich:

```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
</dict>
</plist>
```

DER (base64): `cEICAQGwPTA7DDZjb20uYXBwbGUuc2VjdXJpdHkuY3MuYWxsb3ctdW5zaWduZWQtZXhlY3V0YWJsZS1tZW1vcnkBAf8=`
— dieselbe eine Berechtigung, Slot −7 stimmt. Keine andere der 381 Dateien
hat einen Entitlement-Blob; es gibt kein zweites ausführbares Programm im
Bundle (der Hilfsprozess RM-212 startet dasselbe Hauptprogramm und erbt die
Berechtigung).

`_ctypes.cpython-314-darwin.so` lädt `/usr/lib/libffi.dylib` (Apples libffi),
`_cffi_backend.cpython-314-darwin.so` ebenso (gemessen). Für den RM-104-Weg (anonymer
RWX-Speicher) ist damit alles da, was die Signatur liefern kann; ob Apples
libffi auf macOS 26.5/Intel mit dieser Berechtigung wirklich den RWX-Weg
nimmt, ist **vermutet**, nicht am Gerät gemessen.

### M3 Info.plist (gemessen)

`CFBundleExecutable` Solidon3D, `CFBundleIdentifier` de.rsdigital.solidon3d,
`CFBundleShortVersionString` 0.6.0, **`LSMinimumSystemVersion` 14.0**,
`NSHighResolutionCapable` true, **kein `CFBundleVersion`**, kein
`LSArchitecturePriority` (bei einer Ein-Architektur-App belanglos), kein
`NSPrincipalClass`, kein `LSApplicationCategoryType`. Copyright-Zeichen ist
korrekt kodiert (nur die Konsole zeigt es falsch). Auffällig nur das Fehlen
von `CFBundleVersion` (kosmetisch; Installer und Sparkle-artige Vergleiche
nutzen sonst diesen Schlüssel).

### M4 Mindest-macOS je Mach-O liegt über LSMinimumSystemVersion (gemessen)

Höchster Wert **26.0** (10 Dateien), dazu 39 Qt-Bibliotheken und -Plugins mit
**14.4** — 49 Mach-O liegen über `LSMinimumSystemVersion` 14.0 (die Zahl 154
in `x64-auswertung.txt` zählt wegen eines Tupelvergleichs `(14,0,0) > (14,0)`
auch die 105 Dateien mit genau 14.0 mit; richtig ist 49).

| minos | Dateien | Beispiele |
|---|---|---|
| 26.0 | 10 | `PySide6/QtCore.abi3.so`, `QtGui.abi3.so`, `QtWidgets.abi3.so`, `QtNetwork`, `QtDBus`, `QtSvg`, `QtSvgWidgets`, `libpyside6.abi3.6.12.dylib`, `shiboken6/Shiboken.abi3.so`, `libshiboken6.abi3.6.12.dylib` |
| 14.4 | 39 | alle `Qt/lib/*.framework`, `plugins/platforms/libqcocoa.dylib`, `styles/libqmacstyle.dylib`, Bildformate |
| 14.0 | 105 | numpy, scipy, Teile von skimage |
| ≤ 11.1 | 228 | OCP, Pillow, shapely, manifold3d, Python, Hauptprogramm (10.13) |

Die Räder sind als `macosx_14_0_universal2` markiert
(`pyside6_essentials-6.12.0-cp310-abi3-macosx_14_0_universal2.whl` laut
Paketjob-Log), ihre Bindungsmodule sind aber für 26.0 gebaut — auch im
ARM64-Bundle. Wirkung: Für den Kunden-Mac mit **macOS 26.5 belanglos**. Für
jeden Intel- oder Apple-Silicon-Mac mit macOS 14.x/15.x, den Installer und
`LSMinimumSystemVersion` ausdrücklich zulassen, wäre ein Abbruch beim ersten
`import PySide6.QtCore` denkbar. dyld lehnt eine Bibliothek nicht allein
wegen minos ab; scheitern würde sie an Symbolen, die es erst in macOS 26
gibt.

**M4a — Gegenprobe der Importe (gemessen, `skripte\importe.py`,
`ergebnis\x64-importe26.txt`):** Die zehn 26er-Dateien importieren aus
Systembibliotheken nur 31 libc++-Symbole, die die 14.4-Qt-Bibliotheken nicht
ziehen — alle langjährig vorhanden (`basic_string::assign/find/compare`,
`recursive_mutex`, `bad_optional_access`, `bad_function_call`, `cerr`,
Typinfos), **kein** neues Symbol wie `std::__hash_memory`; dazu
`_strdup`, `dyld_stub_binder` (klassisches Lazy-Binding, keine Chained
Fixups) und die ObjC-Klassen `AVCaptureDevice`, `CNContactStore`,
`EKEventStore`, `CBCentralManager` (Qt-Berechtigungsbehandler, Frameworks
seit macOS 10.x vorhanden). Schwere deshalb: **kosmetisch / Restrisiko**
für macOS 14.0–15.x; für den Kunden (26.5) ohne Wirkung. Sauber wäre
`LSMinimumSystemVersion` und `allowed-os-versions` auf 14.4 (Qt) zu heben
oder die Abweichung als bekannt festzuhalten.

### M5 Paket (.pkg) — Inhalt gleich, aber umziehbar (gemessen)

- Payload (gzip-cpio, 2009 Einträge) ist **bytegleich** zum signierten
  App-Zip: 1744 Dateien/Symlinks gleich, 0 Inhalts-, 0 Rechte-, 0
  Linkabweichungen; die AppleDouble-Datei mit der Signatur von
  `THIRD-PARTY-NOTICES.md` reist mit.
- `Distribution`: `hostArchitectures="x86_64"`, `allowed-os-versions min 14.0`,
  `enable_anywhere`/`enable_currentUserHome`/`enable_localSystem` alle true,
  `customize="allow"`.
- **`component.pkg/PackageInfo` enthält `<relocate><bundle
  id="de.rsdigital.solidon3d"/></relocate>`** (pkgbuild-Vorgabe
  `BundleIsRelocatable`). Der Kommentar in build.yml Z. 1798 kennt das
  bereits: Apples Installer aktualisiert ein vorhandenes Bundle mit derselben
  Kennung **dort, wo es liegt**. Auf einem Kunden-Mac, der schon eine ältere
  Kopie hat — etwa die ad hoc signierte Testkopie aus der RM-104-Diagnose,
  eine Kopie in Downloads/Schreibtisch, auf einem zweiten Volume — landet
  0.6.0 dort, und `/Applications/Solidon3D.app` bleibt 0.5.3. Der Kunde
  startet dann weiter die alte, hängende Version und meldet „0.6.0 startet
  nicht“. Am Runner unsichtbar: Der Prüfjob löscht die Prüfkopie vorher
  (`rm -rf release-app`). Schwere: **kann den Start der neuen Version
  verhindern** (der Kunde startet die alte). Gemessen: das Element. Vermutet:
  dass beim Kunden eine zweite Kopie existiert — prüfbar beim Kunden mit
  `mdfind "kMDItemCFBundleIdentifier == 'de.rsdigital.solidon3d'"` (alle
  Kopien mit dieser Kennung), `grep -i relocat /var/log/install.log` und
  `defaults read /Applications/Solidon3D.app/Contents/Info.plist
  CFBundleShortVersionString`. Abhilfe am Bau: `BundleIsRelocatable` in der
  Komponenten-Plist von pkgbuild auf `false`.
- Beleg: `pkg-x64\component.pkg\PackageInfo`, `ergebnis\pkg-x64-vergleich.txt`.

### M6 Architektur und Abhängigkeiten (gemessen)

- Alle 382 Mach-O sind thin `x86_64` (CPU-Subtyp 3); kein `x86_64h`, keine
  arm64-Scheibe, kein Fat-Binary.
- **Keine `@rpath`-/`@loader_path`-Abhängigkeit zeigt ins Leere**: Jede
  nicht-systemische `LC_LOAD_DYLIB`/`LC_LOAD_WEAK_DYLIB` aller 382 Dateien
  wurde über die eigenen `LC_RPATH`-Einträge (mit `@loader_path`/
  `@executable_path` und Symlinks im Zip) aufgelöst — 0 fehlend.
- Systemabhängigkeiten: nur `/usr/lib/{libSystem.B, libc++.1, libc++abi,
  libobjc.A, libz.1, libbz2.1.0, libffi, libiconv.2, libresolv.9}` und
  System-Frameworks (AppKit, Metal, OpenGL, IOKit, ScreenCaptureKit,
  UniformTypeIdentifiers, Accelerate, AVFoundation, Contacts, EventKit,
  CoreBluetooth u. a.). Alle gibt es auf macOS 14; keine Bibliothek, die es
  auf 14 nicht gäbe.
- Hauptprogramm (PyInstaller-Bootloader): minos 10.13, SDK 26.2, lädt nur
  Carbon, libSystem, libz, ApplicationServices, CoreFoundation, CoreServices.
- **Zusatzfund: `Contents/Frameworks/libfreetype.dylib` liegt nur im
  Intel-Bundle** (658 560 Byte, minos 14.0, SDK 14.5, `@rpath/libpng16.16`,
  `rpath @loader_path`). Es ist keine Datei aus einem Rad: freetype-py
  bringt seine eigene `freetype/libfreetype.dylib` (minos 10.9) mit,
  Pillow und OCP je eine `libfreetype.6.dylib`. Die vierte kommt nach allem
  Anschein aus Homebrew unter `/usr/local/lib` des Intel-Runners (die
  Apple-Silicon-Runner haben Homebrew unter `/opt/homebrew`, außerhalb des
  dyld-Suchwegs — deshalb fehlt sie im ARM64-Bundle) und gelangte über
  PyInstallers ctypes-Analyse von freetype-py ins Paket. Der Paketjob meldet
  selbst „FT_Library_Version der gebündelten Datei (libfreetype.dylib) ging
  nicht“ (Log 114568087314, Z. 780) — die Stückliste kennt ihre Fassung also
  nicht. Signiert und versiegelt wie alle anderen; Start: keine Wirkung
  (freetype-py findet zuerst die eigene Datei im Paketordner — vermutet,
  nicht gemessen). Schwere: **kosmetisch / Herkunft und Lizenzbeleg** (eine
  Runner-Bibliothek, deren Fassung vom Runner-Image abhängt).

### M7 Befehlssatz Intel (gemessen, `skripte\isa_scan.py`)

Alle 382 x86_64-Dateien vollständig disassembliert: 71,6 Mio. Befehle,
279 MB Code (`ergebnis\isa-x64.json`, Zusammenfassung
`ergebnis\isa-x64-auswertung.txt`). Funktionsgrenzen aus
`LC_FUNCTION_STARTS`, Namen aus der Symboltabelle. Coffee Lake (i7/i9-9xxxH)
kann AVX, AVX2, FMA3, BMI1/2, F16C, ADX, AES-NI, PCLMULQDQ (128 bit), aber
**kein** AVX-512, SHA-NI, VAES/VPCLMULQDQ-256, GFNI, AVX-VNNI, WAITPKG, XOP,
FMA4.

**Kein globales `-march`.** OCP (137 MB, 27,5 Mio. Befehle) und alle
OCCT-Bibliotheken, Python, QtWidgets/QtGui/QtQml/QtQuick, die
PySide-Bindungen, scipy, GEOS, manifold3d, freetype, harfbuzz: **null**
AVX2-, FMA- und AVX-512-Befehle. AVX2/FMA/BMI tauchen nur in SIMD-Bibliotheken
auf, dort in ≤ 9 % der Funktionen (Ausnahme libavif, s. u.); ein x86-64-v3-
oder -v4-Bau sähe anders aus (AVX/BMI quer durch fast alle Funktionen).

Befehle, die Coffee Lake nicht hat, stehen nur in neun Dateien — jede mit
eigener CPUID-Weiche:

| Datei | Fremdbefehle | Funktionen | Weiche |
|---|---|---|---|
| `libcrypto.3.dylib` (OpenSSL) | AVX-512 95 230, SHA-NI 512, VAES-256, VPCLMUL-256, XOP, AVX512-IFMA | 22 von 13 163 (`*_avx512`, `*_ifma256`, `*_shaext`, `*_xop`) | `OPENSSL_ia32_cpuid` |
| `numpy/_core/_multiarray_umath` | AVX-512 77 566 | 328 von 8 680: `*_X86_V4` und x86-simd-sort-Kerne (`zmm_vector<…>`) | `npy_cpu_init` (cpuid + xgetbv) |
| `PIL/.dylibs/libavif.16.4.2` | AVX-512 36 084, GFNI, AVX-VNNI | 1 789 von 14 998 (gestrippte Asm-Kerne der Codecs) | 19 cpuid-Stellen; alle 264 exportierten C-Funktionen ohne einen VEX/EVEX-Befehl |
| `OCP/.dylibs/libopenjph` | AVX-512 2 326 | 16 von 459 | `ojph::init_cpu_ext_level` |
| `PIL/.dylibs/libz.1.3.1.zlib-ng` | AVX-512 426, AVX-VNNI | 13 von 225 (`crc32_*vpclmulqdq`, `*_avx512`) | `x86_check_features` |
| `OCP/.dylibs/libdeflate.0` | AVX-512 215, VPCLMUL-256 | 4 von 56 | `libdeflate_init_x86_cpu_features` |
| `QtCore` | AVX-512 10, VAES-256 52 | 6 von 14 950: vier `vaesenc ymm`-Hashfunktionen (Muster des AES-`qHash`), zwei maskierte `vcvtps2ph/vcvtph2ps`-Schwänze (float16) | zwei gestrippte cpuid-Funktionen; QtCore trägt außerdem die eigene Startprüfung „Incompatible processor. This Qt build requires the following features:“, die nur bei einem höheren Bau-Mindeststand greift — QtCore enthält nur 53 AVX2-Befehle, ein solcher Mindeststand liegt nicht vor |
| `wgpu/resources/libwgpu_native-release` | FMA4 1 | 1 (`libm::…::fmaf_with_fma4`) | `libm::…::detect::load_x86_features` |
| `manifold3d` | WAITPKG 1 (`tpause`) | 1 (oneTBB-Warteschleife) | Merker aus `cpuid` Leaf 7 ECX Bit 5, unmittelbar vor `tpause` geprüft (disassembliert) |

Bewertung: AVX-512 außerhalb einer Laufzeitweiche **nicht gefunden**. Alle
Fundstellen sind die üblichen, per CPUID gewählten Kerne bekannter
Bibliotheken; ein SIGILL auf Coffee Lake vor dem Fenster ist aus dem Code
nicht abzuleiten. Grenze der Methode: Ob jede Weiche korrekt verzweigt, zeigt
nur eine Ausführung — statisch belegt ist, dass die Fremdbefehle nur in
eigenen, benannten oder gestrippten Kernfunktionen stehen und jede Datei eine
CPUID-Erkennung trägt. Die 207 KB „nicht dekodierbar“ in wgpu-native sind
Sprungtabellen (Bytes `fe ff ff ff …`) mitten in `__text`, keine
unbekannten Befehle. Schwere: **keine**.

### M8 Weitere Eigenschaften, die die Hardened Runtime anders behandelt (gemessen)

`skripte\textrelocs.py` über alle Mach-O beider Bundles
(`ergebnis\textrelocs-*.txt`): **keine** Textrelokation (keine
`LC_DYSYMTAB`-Relokationen, kein Rebase in ein nicht beschreibbares Segment),
**kein** W+X-Segment, kein `MH_ALLOW_STACK_EXECUTION`. Fixup-Art: 40 Dateien
Chained Fixups, 342 `LC_DYLD_INFO`. Nichts davon würde auf einem Kunden-Mac
anders laden als am Runner. PyInstaller-Spec ohne `argv_emulation`
(Carbon-Ereignisschleife beim Start entfällt).

### M9 Was am Runner grundsätzlich nicht geprüft wird (gemessen am Workflow, Wirkung vermutet)

- Der Intel-Starttest läuft im Paketjob **und** in der Releaseakte mit
  `--offscreen` (build.yml Z. 723 und 1807, Begründung: Symboldienst des
  Runners stürzt in Metal ab). Damit wird auf **keinem** Intel-Lauf
  `platforms/libqcocoa.dylib` geladen, kein `NSWindow`, kein Metal-Gerät für
  wgpu angelegt, keine Grafikumschaltung zwischen Intel UHD 630 und
  Radeon Pro 5300M/5500M ausgelöst. Alles, was die Signatur betrifft, ist
  statisch sauber (M1–M8); ein Hänger beim Kunden, der *nach* dem ersten
  `import ctypes` liegt, säße mit hoher Wahrscheinlichkeit in diesem
  ungetesteten Abschnitt (Cocoa-Plattform, rubicon-objc/ctypes-Rückrufe,
  wgpu-Adapterwahl auf Metal mit zwei GPUs). Das ist ein Schluss, kein Befund
  am Artefakt.
- Beleg am Lauf: Der Startbericht der Intel-Releaseakte (Job 114573051036,
  21:02:07) meldet `"platform": "offscreen"`, `"renderer": {"present":
  false}`, Fenster „Untitled — Solidon3D“, Ende nach 39,7 s mit Code 0. Die
  dort genannte `crash_file` ist das bei jedem Start angelegte
  faulthandler-Ziel (`app/core/log.py` Z. 675), kein Absturz; der Starttest
  prüft sie auf tödliche Einträge und fand keine.
- Ebenso nie geprüft: der Start mit **gespeichertem Lizenzschlüssel** — der
  Starttest beginnt mit leerem Profil. Siehe M10.
- `com.apple.security.cs.allow-unsigned-executable-memory` deckt den
  RM-104-Weg; ob Apples libffi auf x86_64/macOS 26.5 auch für cffi-Rückrufe
  (wgpu-py `ffi.callback`, `_cffi_backend` → `/usr/lib/libffi.dylib`) und
  ctypes-Rückrufe (rubicon-objc) denselben anonymen RWX-Weg nimmt, ist nicht
  gemessen. Am Kundengerät zu prüfen mit
  `codesign -d --entitlements - /Applications/Solidon3D.app` (muss die eine
  Berechtigung zeigen) und einem `sample Solidon3D 5` während des Hängers.

### M10 Schlüsselbund vor dem ersten Fenster, sobald ein Lizenzschlüssel gespeichert ist (am Code belegt; Wirkung vermutet)

`app/ui/app.py` Z. 556 ruft `activation.state()` **vor** dem
Ladebildschirm (`SplashScreen` Z. 569). `_determine()`
(`app/core/activation/__init__.py` Z. 365/375) ruft bei gespeichertem
Lizenzschlüssel `certificates.load_for(licence)`, und `load_for`
(`certificate.py` Z. 388–391) liest **zuerst** `device.public_key()` →
`keyring.get_password("de.rsdigital.solidon3d.activation",
"device-seed-v1")` — auch dann, wenn gar kein Zertifikat gespeichert ist
(`text is None` wird erst danach geprüft). Der Docstring von
`device.py` („Der Programmstart … öffnet auch keinen Schlüsselbund“)
stimmt für diesen Fall nicht.

Wirkung auf einem Kunden-Mac: Ein Schlüsselbundeintrag, den ein **anders
signierter** Bau angelegt hat — etwa die ad hoc signierte Testkopie aus der
RM-104-Diagnose, deren Zugriffsliste an ihren cdhash gebunden ist —, löst
beim Lesen durch 0.6.0 (Developer ID) die Systemabfrage „Solidon3D möchte auf
vertrauliche Informationen … zugreifen“ aus; ebenso ein gesperrter
Anmeldeschlüsselbund. Der Aufruf blockiert, bis der Nutzer antwortet — noch
ohne Fenster, nur mit springendem Dock-Symbol, was wie ein Hänger aussieht.
Zwischen 0.5.3 und 0.6.0 mit derselben Developer-ID und demselben
Identifier `de.rsdigital.solidon3d` entsteht keine Abfrage (gleiche
designierte Anforderung). Am Runner unsichtbar: leeres Profil, kein
Lizenzschlüssel, frischer Schlüsselbund. Schwere: **kann als Starthänger
erscheinen**, nur bei gespeichertem Lizenzschlüssel und fremd angelegtem
Eintrag. Prüfbar beim Kunden: `security find-generic-password -s
de.rsdigital.solidon3d.activation -a device-seed-v1` (zeigt, ob es den
Eintrag gibt) und die Frage, ob nach dem Start ein Schlüsselbund-Dialog
irgendwo hinter anderen Fenstern steht.

## Befunde macOS ARM64

### A1 Signatur, Team, Flags (gemessen)

381 Mach-O, alle thin `arm64` (kein `arm64e`, kein x86_64-Rest). 381 CDs,
**alle** Team **D6D857LWR7**, Flags genau `runtime`, kein `adhoc`, kein
`linker-signed` (die vom Linker ad hoc signierten arm64-Räder sind also alle
neu signiert). CMS-Kette Developer ID → G2 → Apple Root CA, Zeitstempel
vorhanden, `messageDigest` passt. **Alle Seitenhashes aller Dateien
stimmen**, Spezialslots stimmen, äußeres Siegel: 931 Ressourcen-Hashes ok,
363 verschachtelte cdhashes ok, 341 Symlinks ok, 17 Framework-Bundles ok.
Beleg: `ergebnis\arm64-auswertung.txt`.

### A2 Entitlements, Info.plist, minos (gemessen)

- Entitlements wörtlich wie Intel (eine Berechtigung, XML und DER gleich),
  nur am Hauptprogramm.
- Info.plist inhaltlich gleich (0.6.0, `LSMinimumSystemVersion` 14.0).
- minos: 11.0 (176), 11.1 (52), 14.0 (104), **14.4 (39, Qt)**, **26.0 (10,
  dieselben PySide6/shiboken6-Bindungen)**. Also auch auf Apple Silicon
  dieselbe Abweichung wie M4; keine Datei mit minos über 26.0.
- Keine fehlenden Abhängigkeiten, keine Textrelokationen, keine W+X-Segmente.

## Vergleich X64 / ARM64

- Dateiliste: identisch bis auf **zwei Einträge nur im Intel-Bundle**:
  `Contents/Frameworks/libfreetype.dylib` (Datei, 658 560 Byte) und der
  Symlink `Contents/Resources/libfreetype.dylib` darauf (M6).
- Nicht-Mach-O mit anderer Größe: nur erwartbare (Ticket
  `Contents/CodeResources`, `THIRD-PARTY-NOTICES.md` 917 176 gegen 910 088,
  Stückliste `Solidon3D.cdx.json` 381 396 gegen 378 543, `WHEEL`/`RECORD`
  von numpy, manifold3d, markupsafe mit dem Plattform-Tag, beide
  `CodeResources`).
- Größe: Dateien 522,5 MB (Intel) gegen 511,5 MB (ARM), davon Mach-O 462,5
  gegen 451,5 MB.
- Signatur: Intel trägt in 7 Dateien zusätzlich eine SHA-1-CD (Bibliotheken
  mit altem minos 10.9/10.13, für die codesign eine SHA-1-CD mitschreibt),
  ARM nur SHA-256. Kein Befund.
- minos-Profil: Intel hat ältere Untergrenzen (10.9–10.15), ARM ab 11.0;
  die Obergrenzen (14.4 Qt, 26.0 PySide) sind gleich.

## Befunde Linux

Untersucht: `solidon3d-linux` = `Solidon3D-0.6.0-x86_64.AppImage`
(254 MB) und `Solidon3D-0.6.0-x86_64.flatpak` (190 MB). Das Tar-Archiv
`…-linux-x86_64.tar.gz` steckt nur in `solidon3d-linux-release-input` und
wird nach dem Linux-Paketjob nicht veröffentlicht; nicht geladen.

### L1 AppImage-Laufzeit braucht kein libfuse2 (gemessen)

Das Laufzeit-ELF (944 632 Byte vor dem SquashFS) ist **statisch** (ET_DYN
ohne `PT_INTERP`, kein `DT_NEEDED`), Abschnitte `.appimage`, `.static`,
`.digest_md5`, `.sha256_sig` — die neue type2-Laufzeit mit eingebautem
libfuse3. **Kein libfuse2 nötig**; gebraucht wird nur FUSE im Kernel und
`fusermount3`/`fusermount` (auf Ubuntu 22.04/24.04 und Fedora Workstation
vorhanden). SquashFS mit zstd (Kompressions-ID 6), entpackt mit 7-Zip 26.00:
1 564 Dateien, 140 Symlinks, 486 ELF.

### L2 AppImage startet erst ab glibc 2.38 (gemessen) — Start auf Ubuntu 22.04, Debian 12, RHEL 9 unmöglich

`skripte\elf_pruefen.py` + `elf_auswerten.py`
(`ergebnis\appimage-elf-auswertung.txt`): höchste benötigte Version
**GLIBC_2.38**, u. a. in `libpython3.14.so.1.0` (`fmod@GLIBC_2.38`),
`libstdc++.so.6` (`__isoc23_strtoul`), `libxkbcommon.so.0`,
`libxcb-cursor.so.0` (`__isoc23_strtol`), `libsystemd`, `libmount`,
`libkrb5`, CPythons `math`, `_pickle`, `_decimal`, `pyexpat`. Das Programm
`usr/bin/Solidon3D` (Bootloader) selbst braucht nichts über 2.34, aber das
`dlopen` von libpython scheitert mit „version `GLIBC_2.38' not found“.

| System | glibc | Ergebnis |
|---|---|---|
| Ubuntu 22.04 LTS (Mint 21, Pop!_OS 22.04, Zorin 17) | 2.35 | **startet nicht** |
| Debian 12 | 2.36 | **startet nicht** |
| RHEL/Alma/Rocky 9 | 2.34 | **startet nicht** |
| Ubuntu 24.04, Fedora 40+, Debian 13, Arch | ≥ 2.39 | ok |

Am Runner unsichtbar, weil er selbst Ubuntu 24.04 ist (build.yml Z. 595 ff.
nennt die Runner-glibc ausdrücklich als Untergrenze). Die Website nennt bei
den Systemvoraussetzungen nur „Linux (x64, X11/Xwayland)“, keine
Mindest-glibc und keine Distribution — die AGB stellen auf diese Angabe ab.
Schwere: **verhindert den Start** auf den genannten Systemen (Flatpak nicht
betroffen, seine glibc kommt aus der Laufzeit).

### L3 Gebündelte libstdc++/libgcc_s aus Ubuntu 24.04 (gemessen; Wirkung vermutet)

`_internal/libstdc++.so.6` (bis **GLIBCXX_3.4.33**, CXXABI_1.3.15, GCC 14)
und `libgcc_s.so.1` (bis GCC_14.0.0) reisen mit, ebenso `libX11`,
`libX11-xcb`, `libfontconfig`, `libfreetype`, `libz`, `libexpat`, `libuuid`,
glib, dbus, systemd (bewusst, siehe `make_linux_packages.ORPHANED_LIBRARIES`).
Benötigt wird höchstens GLIBCXX_3.4.29 / CXXABI_1.3.13, das Paket selbst
ist also in sich stimmig. Risiko: Der Bootloader setzt `LD_LIBRARY_PATH`
auf `_internal` (Zeichenketten `LD_LIBRARY_PATH`/`LD_LIBRARY_PATH_ORIG` im
ELF), und `libQt6Core` zieht libstdc++ schon beim Import; ist die gebündelte
libstdc++ einmal
geladen, bekommt auch der Grafiktreiber des Hosts (Mesa: `libGLX_mesa` →
`libgallium`/`libLLVM`, die Qts GLX-Integration und Vulkan-ICDs nachladen)
diese ältere Fassung. Auf Systemen mit GCC 15 (GLIBCXX_3.4.34: Ubuntu
25.10/26.04, Fedora 42+, Arch/CachyOS — CachyOS ist im Code als
Kundensystem genannt) scheitert ein Treiber, der ein 3.4.34-Symbol braucht,
mit „GLIBCXX_3.4.34 not found“ → keine 3D-Ansicht oder Absturz beim ersten
GL-Kontext. Im Flatpak gilt dasselbe gegen den Mesa der
`org.freedesktop.Platform.GL.default//26.08`-Erweiterung (gebaut mit dem
GCC-15-SDK 26.08), sofern das Flatpak dieselbe `_internal`-Kopie trägt
(laut Paketlog `files/lib/solidon3d/_internal/…`, Inhalt nicht entpackt).
Am Runner unsichtbar: dort ist die Host-libstdc++ dieselbe 3.4.33. Prüfbar
beim Kunden mit `objdump -T /usr/lib*/libLLVM*.so* | grep -c GLIBCXX_3.4.34`.
Ob ein konkreter Mesa-Stand ein 3.4.34-Symbol zieht, ist hier nicht
gemessen; die Fehlerklasse ist die, für die linuxdeploys „checkrt“
gebündelte und System-libstdc++ zur Laufzeit vergleicht.
Schwere: **später** (3D-Ansicht) bis **Start**, vermutet.

### L4 xcb-Bibliotheken und Qt-Plattform-Plugins (gemessen)

- Mitgebracht: `libxcb-cursor.so.0`, `libxcb-icccm.so.4`,
  `libxcb-image.so.0`, `libxcb-keysyms.so.1`, `libxcb-render-util.so.0`,
  `libxcb-util.so.1`, `libxcb-shape`, `-xkb`, `-randr`, `-render`, `-shm`,
  `-sync`, `-xfixes`, `-glx`, `libxkbcommon(-x11)`. Alle `DT_NEEDED` von
  `platforms/libqxcb.so` und `xcbglintegrations/*` sind damit im Paket,
  außer `libxcb.so.1`, `libGL.so.1`, `libEGL.so.1` (Systemgrundbestand, absichtlich
  nicht gebündelt). Damit ist der Docstring in `app/ui/qt_platform.py`
  („Das X11-Plugin braucht neun Bibliotheken vom System, die das
  Linux-Paket nicht mitbringt — libxcb-cursor0 …“) **veraltet**: Das
  AppImage bringt sie mit (kosmetisch, aber er begründet die Liste
  `xcb;wayland`).
- Plattform-Plugins: `xcb`, `wayland`, `offscreen`, `minimal`,
  `minimalegl`, `eglfs`, `linuxfb`, `vnc`, `vkkhrdisplay`; dazu
  `xcbglintegrations` (EGL, GLX), Wayland-Shell-, Dekorations- und
  Grafikintegrationen, `platformthemes/libqxdgdesktopportal`,
  Eingabemodule `compose`, `ibus`, `qtvirtualkeyboard`.
- `app/ui/qt_platform.py`: mit `DISPLAY` → `xcb`, in einer Wayland-Sitzung
  `xcb;wayland`; ohne `DISPLAY` bleibt Qts Wahl (Wayland), 3D-Ansicht dann
  mit Hinweis. Flatpak: `QT_QPA_PLATFORM=xcb`, nur `--socket=x11`.
- Nicht im Paket und dort auch richtig: `libvulkan.so.1` (wgpu lädt den
  Loader des Hosts per `dlopen`; Ubuntu-/Fedora-Desktop haben ihn ab Werk),
  `libGL`/`libEGL` (glvnd des Hosts), `libwayland-*` (Host).
- Fehlende `DT_NEEDED`, die weder im Paket noch Systemgrundbestand sind:
  **keine**.

### L5 Befehlssatz Linux (gemessen)

Keine der 486 ELF-Dateien trägt `GNU_PROPERTY_X86_ISA_1_NEEDED`; glibc
verweigert also nirgends das Laden wegen x86-64-v2/v3/v4. 218 Dateien
tragen `FEATURE_1_AND` = 0x3 (IBT/SHSTK, harmlos), 268 keine Eigenschaft.

### L6 Flatpak-Metadaten (gemessen, Bundle-Kopf)

`runtime=org.freedesktop.Platform/x86_64/26.08`, `sdk=…Sdk/26.08`,
`sockets=x11`, `devices=dri`, `shared=network;ipc`, `filesystems=home` plus
Lesezugriff auf die Flatpak-Slicer, `QT_QPA_PLATFORM=xcb`, Session-Bus
Fcitx/IBus-Portal und `org.freedesktop.secrets`. Das OSTree-Delta selbst
nicht entpackt (Aufwand); die glibc-Untergrenze aus L2 gilt dort nicht.

## Zusammenfassung

**Gemessen unauffällig (macOS, beide Architekturen):** 382 (Intel) und 381
(ARM) Mach-O, jede mit Developer-ID-Signatur Team D6D857LWR7, Flag
`runtime`, Zeitstempel, kein ad hoc, kein linker-signed; jede Seitenhash-
Liste stimmt mit den Bytes, kein nachträglich veränderter Code; äußeres und
inneres Siegel vollständig; Entitlement `allow-unsigned-executable-memory`
(XML + DER) am Hauptprogramm; keine leeren `@rpath`-Ziele, keine
Textrelokationen, keine W+X-Segmente; .pkg-Payload bytegleich zur
notarisierten App. Befehlssatz Intel: kein globales `-march`, AVX-512/SHA/
VAES/GFNI/WAITPKG/FMA4 nur in neun Bibliotheken mit eigener CPUID-Weiche.
**Eine am Artefakt sichtbare Ursache, die die Bibliotheksprüfung oder der
Coffee-Lake-Befehlssatz am Kundengerät auslöst, gibt es nicht.**

Die drei wichtigsten Befunde:

1. **macOS: Das .pkg ist umziehbar** (`<relocate>` in `PackageInfo`, M5).
   Hat der Kunde irgendwo eine weitere Kopie mit der Kennung
   `de.rsdigital.solidon3d` (z. B. die ad hoc signierte RM-104-Testkopie),
   aktualisiert der Installer diese, und `/Applications` bleibt 0.5.3 — der
   Kunde startet weiter die hängende Version. Zusammen mit M10 (bei
   gespeichertem Lizenzschlüssel liest der Start vor dem ersten Fenster den
   Schlüsselbund; ein von einem anders signierten Bau angelegter Eintrag
   löst eine blockierende Systemabfrage aus) die naheliegendsten
   Erklärungen für „0.6.0 startet auch nicht“, beide am Runner unsichtbar.
   Dazu prüft kein Intel-Lauf Cocoa, Fenster oder Metal (`--offscreen`,
   `renderer.present: false`, M9).
2. **Linux: Das AppImage startet erst ab glibc 2.38** (L2, gemessen:
   `libpython3.14.so.1.0` braucht `fmod@GLIBC_2.38`, weitere 2.38-Symbole in
   libstdc++, libxkbcommon, libxcb-cursor u. a.). Ubuntu 22.04 mit Ablegern,
   Debian 12 und RHEL 9 scheitern beim Laden von libpython; die Website nennt
   keine Untergrenze. Daneben reist eine libstdc++ mit GLIBCXX_3.4.33 mit,
   die auf GCC-15-Systemen den Mesa-Treiber des Hosts treffen kann (L3,
   vermutet).
3. **macOS: Mindestsystem im Paket höher als zugesagt** (M4): PySide6-
   Bindungen minos 26.0, Qt minos 14.4, `LSMinimumSystemVersion` und
   Installer 14.0. Keine Importe von 26er-Symbolen gefunden (M4a), also für
   14/15 nur Restrisiko, für den Kunden mit 26.5 ohne Wirkung. Kleiner:
   eine Intel-only `Frameworks/libfreetype.dylib` vom Runner (M6), veraltete
   Docstrings in `app/ui/qt_platform.py` (L4) und
   `app/core/activation/device.py` (M10).
