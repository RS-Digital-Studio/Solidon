# Solidon auf macOS Intel, macOS ARM und Linux — Aufnahme aus Geschichte, Code und CI

Stand: 12.10.2026, main `cedc42b75`, Tag `v0.6.0` = `ed27f155c`. Nur gelesen, nichts geändert.
Die ausgewerteten Job-Logs lagen örtlich vor und sind über die genannten Job-IDs bei GitHub abrufbar, solange GitHub sie aufbewahrt.

Kennzeichnung in den Tabellen:

- **Kunde belegt** — behoben und am Kundengerät belegt
- **Runner belegt** — behoben, aber nur am GitHub-Runner belegt
- **offen** — bekannt, nicht behoben
- **vermutet** — aus Code oder Quellen gefolgert, nirgends gemessen (meine Funde sind mit *neu* markiert)

---

## 0. Kurzfazit zur Ausgangsfrage

Die Korrektur für den Intel-Hänger steckt nachweislich in 0.6.0: `995125acc` (07.10.) ist im Tag
enthalten, und der Signierjob des Tag-Laufs hat sie gefahren und zurückgelesen
(Lauf 38170638968, Job 114570963023: `entitlements … OK`, zweimal `replacing existing signature`,
`valid on disk`, Notarisierung `Accepted`, `source=Notarized Developer ID`). Dass das Paket damit
auf einem echten Intel-Mac startet, ist **nirgends gemessen**:

1. Die CI kann es grundsätzlich nicht zeigen. Auf beiden Mac-Runnern ist SIP aus
   (`csrutil status`, Lauf 37488283777). Dort greifen weder der Schutz vor ausführbarem
   Schreibspeicher noch die Bibliotheksprüfung. Das Developer-ID-Paket ohne Berechtigung startete
   dort genauso wie mit ihr.
2. Der Intel-Starttest läuft `--offscreen`, ohne Cocoa und ohne 3D-Ansicht
   (`"platform": "offscreen"`, `"renderer": {"present": false}` in Job 114568087314 und
   114573051036). Er startet das Programm direkt als Kindprozess, nicht über
   LaunchServices.
3. Die einzige Probe am Kundengerät (08.10., MacBookPro16,1, macOS 26.5) lief **ad hoc signiert mit
   `disable-library-validation`**, also mit abgeschalteter Bibliotheksprüfung, von Hand, ohne
   Stapel und ohne festgehaltenen Ablauf. Das ausgelieferte 0.6.0 läuft mit **aktiver**
   Bibliotheksprüfung. Diese Kombination (Developer ID, Hardened Runtime, Bibliotheksprüfung an,
   Berechtigung gesetzt) hat noch kein SIP-Mac gestartet.
4. Bis 0.5.3 hing der Prozess schon im PyInstaller-Bootstrap. Alles, was danach kommt (Cocoa,
   rubicon-objc, CAMetalLayer, wgpu/Metal auf x86_64, die Adapterfrage, Qt-Plugins unter
   Bibliotheksprüfung), ist auf einem Intel-Mac mit SIP **noch nie gelaufen**, auch am Runner nicht
   mit Fenster. Ein zweiter, bisher verdeckter Fehler ist deshalb möglich.

Trotzdem verspricht der Changelog 0.6.0 dem Kunden „Auf Intel-Macs mit macOS 26 startet Solidon
jetzt“ (`changelog/de.md:70`). Die Website schreibt weiter „Installation und erster Start laufen
ohne Rückfrage“ und rät für blockierte Versionen zu *Trotzdem öffnen* (`website/index.html`,
Download-Hinweise). Für den Hänger 0.4.1–0.5.3 war das kein Weg.

Dazu kommt: **Seit dem 12.10. startet die CI gar keinen Job mehr.** Beide main-Läufe von heute
(38209221698 um 05:43, 38249234288 um 12:28) sind auf jeder Plattform rot, weil GitHub keinen Job
zuteilt: „The job was not started because recent account payments have failed or your spending
limit needs to be increased“ (Annotation an Check-Run 114679430605 und 114810910907). Das
Repository ist privat (`gh repo view`: `PRIVATE`). Die 0.6.1-Stände auf main (`a615f8221`,
`e871f6062`) hat damit kein Runner gesehen, auch kein Intel-Mac.

---

## 1. Was die CI je Plattform tatsächlich prüft

Quelle: `.github/workflows/build.yml` am HEAD, Joblisten der Läufe 38170638968 (Tag v0.6.0) und
38177649985 (main nach dem Release).

| Prüfung | Windows | Linux (ubuntu-24.04) | ARM-Mac (macos-latest = macOS 26.6.2 arm64) | Intel-Mac (macos-26-intel = 26.6.1 x86_64) |
|---|---|---|---|---|
| Kernsuite, 3 Teile, `QT_QPA_PLATFORM=offscreen` (Linux: Xvfb) | Tag + main | Tag + main | Tag + main | **nur Push nach main**, am Tag nicht (`build.yml:104-112`) |
| mypy auf der Zielplattform | Tag + main | Tag + main | Tag + main | nur main |
| Fensterverträge + Rendererfälle ohne Fenster | Tag + main | Tag + main (Xvfb, lavapipe) | Tag + main (offscreen, Metal am Runner) | Tag + main (offscreen) im Job `window-contracts-intel`; die 3 nativen Fälle von `test_render_factory` übersprungen („ein leeres cocoa-Fenster hing“, Job 114562334603) |
| volle Fenstergruppe | Tag (3 Gruppen) | nein | nein | nein |
| Fensterauswahl zum Push (betroffene Fensterdateien) | main | main (Xvfb) | main (offscreen) | main (offscreen) |
| Slicerauswahl zum Push (echte Slicer) | nein | main | main | main |
| Paketbau + Hilfsprozess aus dem Paket (`check_frozen_helper.py`) | Tag | Tag | Tag | Tag |
| Start des gebauten Pakets (`check_frozen_start.py`) | Tag, Fenster | Tag, Xvfb, Renderer present (lavapipe) | Tag, Cocoa, Renderer present, `brightest 233` | Tag, **`--offscreen`**, Renderer **nicht** da |
| AppImage-Start | – | Tag, Xvfb, **`APPIMAGE_EXTRACT_AND_RUN=1`** (kein FUSE) | – | – |
| Flatpak installiert und gestartet | – | Tag, Xvfb + `dbus-run-session`, Portale laufen nicht (`xdg-desktop-portal-gtk: cannot open display`, Job 114568087245) | – | – |
| Signieren, Notarisieren, Installer signieren | lokal bei Robert | – | Tag | Tag |
| Releaseakte: `.pkg` mit Quarantäne installiert, `spctl`, Start | Installer-Workflow | nur Belegprüfung, kein Start | Tag, Cocoa, Renderer present | Tag, **`--offscreen`** |
| Bibliotheken neuester Fassung (`latest`) | – | Tag, meldend | – | – |

Was dabei nie vorkommt, auf keiner Plattform: SIP an, Start per Doppelklick über LaunchServices,
ein echter GPU-Treiber (Mac: paravirtualisierte Grafik; Linux: lavapipe unter Xvfb), Wayland,
FUSE, ein echter Schlüsselbund (Keychain, Secret Service), macOS 14 und 15 (die Mindestversion
ist 14, `branding.MACOS_MINIMUM`).

### CI-Läufe der letzten zwei Wochen (main und Tag)

| Lauf | Stand | Ergebnis Mac/Linux | Ursache |
|---|---|---|---|
| 38249234288 (12.10. 12:28) | `e871f6062` | alle Jobs rot | Kein Job gestartet: Zahlung/Ausgabengrenze (Annotation) |
| 38209221698 (12.10. 05:43) | `a615f8221` (0.6.1) | alle Jobs rot | dieselbe Annotation |
| 38177649985, 38177727585 (11.10. 21:45) | `8c062f4a5`, `80954bfe7` (enthält den Tag) | alles grün, Intel-Suite inklusive | – |
| 38170638968 (Tag v0.6.0) | `ed27f155c` | grün außer „Neueste Versionen“ | nur `ruff` ICN001 der neuesten ruff (5 × `datetime` als `dt`); im selben Job 28 047 Tests bestanden, 174 übersprungen, Verträge und Renderer unter Linux grün |
| 38161566588 (11.10. 17:54) | `d2f8d4916` | grün | – |
| 38141018146 (11.10. 12:53) | `ee6b810fe` | Fensterauswahl Teil 2 rot auf Ubuntu, ARM, Intel | `test_tour.py::test_every_tour_line_stays_inside_the_card`: Tourzeile breiter als die Karte (12 Touren). Behoben in `b964910db`/`d0b624a0e`, Merge `55dbdbcc5` in release/0.6.0, vor dem Tag |
| 38121948735 (11.10. 07:36) | `732bde46d` | Slicerauswahl Ubuntu rot | `exit code 60` (curl, TLS-Zertifikat beim Laden eines Slicers); Zweig `fix/ci-zertifikat` |
| 38081947318 (10.10. 19:59) | `1fc9a1a5b` | Intel-Suite Teil 0 und 2 rot | 4 × `Fatal Python error: Bus error` (OCC-Ausnahmen durch die falsche Abwicklungstabelle, RM-768); Dichtungsnormale `(0,0,-0.99…)` statt `(0,0,-1)` auf Intel (`test_exact_parts.py:1738`); HTTP-Fristtest unter Last |
| 38076092209 (10.10. 18:31) | `e734a0b44` | Intel-Suite 3 Teile, ARM-Suite Teil 1, Fensterauswahl Teil 2 auf drei Plattformen, Slicerauswahl Intel | Intel: Bus error, `Fatal Python error: Aborted`, 10 × `RuntimeWarning: invalid value encountered in create_collection` (GEOS); Fensterauswahl: `test_the_3mf_export_reads_the_slicer_stock_in_one_pass`; Slicerauswahl Intel: Artefakt-Upload `ENOTFOUND` |

Alle Funde vom 10./11.10. sind vor dem Tag behoben (`9904af944` GEOS-Flag auf Intel, `7768d8e33`
Normale ebener Flächen auf Intel, `883472842` + Werkzeug `fix_unwind_info.py` für RM-768,
`9eb2e5f32` HTTP-Fristtests, Tour-Fix). Die Intel-Suite war am Tag selbst nicht dabei; grün lief
sie auf `8c062f4a5`, das den Tag-Commit enthält (`git merge-base --is-ancestor`).

### Paketjobs: Warnungen und Quelltextbauten

- **pip baut nichts aus dem Quelltext.** Einziges „Building wheel“ ist das editierbare
  `solidon3d` (Jobs 114568087314, 114568087313, 114568087245). Alle Abhängigkeiten kommen als Rad.
- **Selbst übersetzt werden zwei Teile**, beide auf dem Runner: der Schichtkern `_chain` und das
  Prüfmodul `app.core.activation` (Cython). Auf beiden Macs mit
  `clang … -O3 -arch arm64 -arch x86_64 … -ffp-contract=off`, unter Linux mit
  `gcc … -O3 -fPIC … -ffp-contract=off`. Kein `-march`, kein `-mavx`; die Flags kommen aus der
  sysconfig des python.org-Interpreters (Universal2-Framework). Ein Befehlssatz, den eine
  Kunden-CPU nicht hat, entsteht hier also nicht.
- PyInstaller 6.22.3 meldet auf allen drei: `Hidden import "rendercanvas.async" not found`,
  `pycparser.lextab/yacctab`, `scipy.special._cdflib`, `Library shell32/ole32 required via ctypes
  not found` (Windows-Bibliotheken). Der ARM- und Linux-Start zeichnen trotzdem; folgenlos, aber
  `rendercanvas.async` steht als Hidden Import in der Spec und existiert in rendercanvas 2.7.2 nicht.
- Intel: `Hinweis: FT_Library_Version der gebündelten Datei (libfreetype.dylib) ging nicht —
  dlopen(Contents/Frameworks/libfreetype.dylib) … no such file` beim Schreiben der Stückliste
  (relativer Pfad); nur die Fassungsangabe, nicht die Laufzeit.
- Intel: `fix_unwind_info.py --check --package dist` meldet 309 korrigierte Einträge in 20
  OCC-Bibliotheken, alle schon korrigiert.
- Linux: `WARNING: AppStream upstream metadata is missing`; im Flatpak-Start lauter
  `xdg-desktop-portal`-Fehler (siehe oben).
- Signier- und Installerjobs: keine Warnung außer Node-Abkündigungen.

---

## 2. Intel-Mac (x86_64)

| Problem | Status | Beleg | Was am Runner unsichtbar bleibt |
|---|---|---|---|
| **Start hängt im PyInstaller-Bootstrap** (`import ctypes` → libffi-Closure → Hardened Runtime verweigert `PROT_EXEC` → Temp-Datei-Ausweg kreist auf macOS 26). Betrifft jedes notarisierte Intel-Paket 0.4.1 bis 0.5.3 | **Runner belegt** (Signierschritt, Rücklesung, Notarisierung); am Kundengerät nur eine Handprobe mit abweichender Signatur | RM-104 (`ROADMAP.md:578-733`); `build.yml:1402-1437`; `995125acc` in `v0.6.0`; Tag-Job 114570963023; Kundenprobe 08.10. (ad hoc + `disable-library-validation`) | Der Hänger selbst: SIP aus, also kein W^X-Schutz. Am Runner startet auch das Paket ohne Berechtigung |
| **0.6.0 mit aktiver Bibliotheksprüfung auf einem SIP-Mac nie gestartet** | **vermutet** (*neu als eigener Punkt*) | Die Kundenprobe hatte `disable-library-validation`, 0.6.0 nicht; Notarisierung `Accepted` spricht dafür, dass alle Mach-O-Dateien im Bündel dieselbe Team-ID tragen | Bibliotheksprüfung greift am Runner nicht (Lauf 37490502237) |
| **Alles hinter dem Bootstrap ist auf Intel nie mit Fenster gelaufen**: Cocoa-Plugin, `QRenderWidget` mit CAMetalLayer über rubicon-objc 0.5.7 (ctypes, x86_64-ABI), wgpu-native/Metal, Adapterfrage über cffi-Rückrufe, erstes Ereignis nach `show()` | **vermutet** offen | Intel-Starttest `--offscreen` (Job 114568087314, 114573051036: `present: false`); `test_render_factory` nativ übersprungen (Job 114562334603); Befund 08.09.: erster Ereignisdurchlauf hängt am Runner (`ROADMAP-ARCHIV.md:24158-24183`) | Der Runner hängt schon an einem leeren Cocoa-Fenster (`iconservicesagent` stürzt in Metal ab). Ob ein echter Intel-Mac die Ansicht zeichnet, zeigt nur ein Gerät. Der Kunde sah mit 0.5.2 ad hoc „zunächst nur im Dock, dann kam sie“ — ob die 3D-Ansicht zeichnete, ist nicht erfragt |
| Starttest ist kein Doppelklick | offen (Prüflücke) | `tools/check_frozen_start.py:87-92` startet `Contents/MacOS/Solidon3D` direkt, `HOME` umgebogen (`environment_for`) | LaunchServices, Dock-Aktivierung, Systemsymbole, TCC-Abfragen, App-Translocation |
| **Paket ist umziehbar** (`pkgbuild --component`, `BundleIsRelocatable` Vorgabe): Liegt irgendwo eine Kopie mit derselben Kennung (ad hoc neu signierte Kopie, Prüfkopie, zweite Installation), aktualisiert der Installer **diese**, und `/Applications` bleibt beim alten Stand. Der Kunde hat ad hoc neu signiert; startet er danach die alte Developer-ID-Kopie, sieht es aus wie „0.6.0 startet nicht“ | **vermutet** | `tools/make_macos_package.py:184-196`; Kommentar `build.yml:1798-1800`; Erinnerung „pkgbuild ist umziehbar“; Diagnose sammelt `mdfind` „Weitere Kopien“ (`solidon-diagnose.sh`) | Der Runner installiert auf ein leeres System |
| `codesign --force --deep --sign -` mit `sudo` beim Kunden: neue Code-Identität, Schlüsselbund-Zugriffe und TCC-Freigaben hängen an der alten | **vermutet** | RM-104 Rückmeldung 05.10. | – |
| **OCC-Ausnahme beendet Solidon mit Bus-Fehler** (falsche `__unwind_info` im x86_64-Rad von `cadquery-ocp-novtk` 7.9.3.1.1 bis 8.0.1.1.0) | **Runner belegt**; Kunde: Changelog 0.6.0 Zeile 71 | RM-768; Lauf 38083944884 (ohne Korrektur 5 Abstürze, mit ihr grün); `fix_unwind_info.py --check` im Paketjob 114568087314; offen: `ocp-build-system#67` | – (am Runner sichtbar) |
| Dieselbe Abwicklungstabelle falsch in Pillow `libavif` und PySide6_Addons FFmpeg (C-Code, nur falsche Stapel in Absturzberichten) | offen | RM-770; ob die Dateien im Intel-Paket liegen, ist nicht nachgesehen | – |
| Skizzenlöser landet im anderen Zweig einer Winkelbedingung (45° → 135°) | **Runner belegt**, Register noch offen | RM-541 (`ROADMAP.md:3264`); Merge `c7a6f853d` → main `e734a0b44`; danach Intel-Fensterauswahl grün (38161566588, 38177649985); ob genau `test_the_angle_button_asks_for_its_degrees` lief, steht wegen `pytest -q` nicht im Log | offscreen |
| GEOS setzt auf Intel an leeren Flächen das Ungültig-Flag, Kanalsperre bricht | **Runner belegt** | `9904af944`; Lauf 38076092209 rot, danach grün | – |
| Normale einer ebenen Fläche hing am ersten Dreieck (Dichtung auf Intel um 1e-16 schief) | **Runner belegt** | `7768d8e33`; Lauf 38081947318 rot, danach grün | – |
| Geometrie hängt an der Plattform (BLAS, `cos`/`sin`, `**`, LAPACK in `perceive`) | teils behoben, Rest offen | RM-187 (Paket A erledigt; offen: Einpassungen in `perceive`, `shapes.py`, `**`, `hollow.py`/`lattice.py`), RM-777 | Rauschtest findet es auf einer Maschine; echte Unterschiede zeigt nur der Vergleich der Runner |
| Fernsteuerung: `abort_active` weckt Handler mit `shutdown` aus fremdem Faden — der Weg, der auf macOS nicht sicher ankam | offen | RM-104 „Offen aus demselben Befund“ (`ROADMAP.md:606-610`) | – |
| Hilfsprozess: gemeinsamer Speicher bleibt nach Absturz in `/dev/shm`/POSIX-shm, `ENOSPC` als `MemoryError`, `SIGBUS`; Kill-Latenz auf dem Mac-Runner | offen | RM-298 (b), (e), (f); `tests/test_kernel_process_lifecycle.py:342` prüft den Todesfall nur mit Windows-Jobobjekt | – |
| Grafik und Eingabe am echten Mac (Auswahl, Navigation, Schließen) | offen | RM-051 | paravirtualisierte GPU |
| **3D-Maus über 3DxWare**: `DriverReader` lädt `/Library/Frameworks/3DconnexionClient.framework` mit `ctypes.CDLL`. Unter Hardened Runtime **ohne** `com.apple.security.cs.disable-library-validation` lehnt dyld eine Bibliothek fremder Team-ID ab; `load_driver` fängt den `OSError`, fällt auf HID zurück, und HID bekommt nichts, weil 3DxWare das Gerät exklusiv hält. Ergebnis wie im Kundenbericht vom 05.09.: „die Maus tut nichts“. Betrifft jedes notarisierte Mac-Paket seit 0.4.1, beide Architekturen | **vermutet** (*neu*) | `app/ui/spacemouse.py:191`, `:724-760`, `:822-829`; `build.yml:1416-1429` (nur eine Ausnahme); `kamera.md:218-224` und Docstring `spacemouse.py:775-777`: „Am Gerät gemessen ist dieser Weg nicht“; Changelog 0.3.5 versprach ihn (`de.md:1385`); RM-070, RM-072 (Zusage an den Dental-Kunden) | Bibliotheksprüfung greift am Runner nicht; kein Runner hat 3DxWare |
| Nur macOS 26 geprüft; Mindestversion 14 | offen (Prüflücke) | Runner-Image `macos-26` (26.6.1) und `macos-26-arm64` (26.6.2) in den Paketlogs; `branding.MACOS_MINIMUM`; Changelog 0.6.0 Zeile 69 | Ob der libffi-Weg auf Intel mit macOS 14/15 anders scheitert, ist unbekannt |
| Doppel-GPU (MacBookPro16,1: Intel UHD 630 + Radeon Pro): Adapter mit `power_preference="high-performance"`, kein `NSSupportsAutomaticGraphicsSwitching` in der Plist → die Radeon läuft, solange Solidon offen ist | **vermutet**, kein Startblocker | `app/ui/render/factory.py:80`; `packaging/solidon3d.spec:368-433` | Runner hat eine virtuelle GPU |
| Website und Changelog sagen mehr, als belegt ist | offen | `changelog/de.md:70`; `website/index.html` (Hinweise: „Installation und erster Start laufen ohne Rückfrage“, *Trotzdem öffnen*) | – |
| Ob `sample` auf einem SIP-Mac einen Prozess mit Hardened Runtime lesen darf (Diagnoseskript) | offen | RM-104 (`ROADMAP.md:730-731`) | SIP aus |

**Was als Nächstes am Kundengerät gebraucht wird** (aus RM-104 und dem Obigen): Doppelklick auf das
installierte 0.6.0 aus `/Applications`, vorher `mdfind "kMDItemCFBundleIdentifier ==
'de.rsdigital.solidon3d'"` (eine Kopie oder mehrere?) und `codesign -d --entitlements - --xml
/Applications/Solidon3D.app` (steht die Berechtigung am installierten Bündel?). Hängt es,
`solidon-diagnose.sh` — der Stapel unterscheidet Bootstrap (`ffi_closure_alloc`) von einem Hänger
weiter hinten (Cocoa, Metal, rubicon).

---

## 3. ARM-Mac (arm64)

| Problem | Status | Beleg | Was am Runner unsichtbar bleibt |
|---|---|---|---|
| 0.5.1 beendete sich 20–40 s nach dem Start (`EXC_BREAKPOINT` im Faden `spacemouse-search`, hidapi an freigegebenem Run Loop); auf Intel `SIGSEGV` | **Runner belegt**; Kunde (Intel) bestätigte für 0.5.2 „Beenden weg“; für ARM keine Kundenrückmeldung gefunden | RM-505 (`ROADMAP-ARCHIV.md:39653-39684`); Läufe 37150755506, 37152322275; Changelog 0.5.2 Zeile 544 | – |
| libffi-Hänger | betrifft ARM nicht (Apples Trampolintabelle); die Berechtigung schadet nicht | RM-104 | – |
| Start mit Fenster und Metal-Ansicht | **Runner belegt** (SIP aus, virtuelle GPU, Direktstart) | Releaseakte arm64, Job 114573050946: `cocoa`, `GfxRenderer`, `brightest 233`, Ende nach 34,1 s mit 0; Paketjob 114568087313 | Bibliotheksprüfung, echte Apple-GPU, LaunchServices. Einen dokumentierten Feldstart eines notarisierten Pakets ab 0.4.1 auf einem echten Apple-Silicon-Mac habe ich in Register und Archiv nicht gefunden; Roberts Mac-Rückmeldung vom 12.09. („spacemaus und update … funktionieren“, RM-070) liegt vor dem ersten notarisierten Paket (0.4.1, 13.09.) und nennt die Architektur nicht |
| 3D-Maus über 3DxWare (Bibliotheksprüfung) | **vermutet** (*neu*) | wie Intel | wie Intel |
| FMA auf ARM (`einsum`, BLAS) → andere Bits, andere Erkennung | weitgehend behoben, Rest offen | RM-187, RM-777; `build_slice_core.py:88-94` (`-ffp-contract=off`, nach Tag-Lauf 0.5.2 auf macOS) | – |
| Tourzeilen breiter als die Karte (auch Linux und Intel) | **Runner belegt** | Lauf 38141018146 rot, Fix `b964910db`, `d0b624a0e`, Fensterauswahl 38146376757 grün | offscreen-Schriftmetrik ≠ echte Metrik |
| Return öffnet Einträge, Kürzelspalte, zwölf Fenstertests mit Windows-Eigenheiten | **Runner belegt** | RM-531 (Läufe 37556091095, 37560540258, 37936316061) | offscreen |
| Abbruch des lokalen Modells kam auf macOS nicht sicher an | **Runner belegt** (20/20) | RM-104 Teil, Lauf 37591775378 | – |
| `socket.getfqdn` 35 s am Mac-Runner, Fernsteuerung startet im Hauptfaden | **Runner belegt**, umgangen | RM-104 Teil; `remote_server.py:557-561` | Netz eines Kunden (Firma, VPN) kann länger brauchen; andere Stellen mit Namensauflösung nicht gesucht |
| CA-Zertifikate im macOS-Paket | Rückfall gebaut, Feldbestätigung offen | `ROADMAP-ARCHIV.md:9423`; `app/ui/app.py:497-500` | – |
| Native Fensterlebensdauer, Gegenprobe Linux/Mac | offen | RM-021 | – |
| Hilfsprozess-Reste unter POSIX, Kill-Latenz am Mac-Runner | offen | RM-298 | – |
| Echte Text- und Bildgenerierung auf macOS | offen | RM-004 | keine GPU |
| Nur macOS 26; 14 und 15 nie geprüft | offen (Prüflücke) | wie Intel | – |
| Umziehbares Paket | **vermutet** | wie Intel | – |
| Ein ARM-Kunde, der das Intel-Paket nimmt (Safari meldet auf ARM „Intel Mac OS X“), läuft unter Rosetta: langsamer, Intel-Wege, Intel-Rad von OCP mit Korrektur | **vermutet** | Download-Kasten: zwei Pakete, Wahl beim Kunden (`website/index.html`) | – |

---

## 4. Linux

| Problem | Status | Beleg | Was am Runner unsichtbar bleibt |
|---|---|---|---|
| Linux-Sammellauf der Fenstertests verliert einen Arbeiter („Fatal Python error: Aborted“ nach `test_overlay.py::test_dragging_the_window_lets_nothing_lag_behind`) | offen, Testinfrastruktur | RM-107, Läufe 37491131058, 37525358642 | – |
| Fcitx-Nutzer tippten ins Leere (kein Fcitx-Modul im Paket) | Abhilfe gebaut, am Flatpak 0.5.3 am **Runner belegt**; AppImage, Archiv und die IBus-Fälle offen | RM-062; Läufe 37507999423, 37524814548; `qt_platform.py`; Changelog 0.6.0 Zeile 112 | echte Desktops (GNOME, KDE, Sway) |
| Cura als Flatpak/AppImage rechnet nicht | gebaut, **Runner belegt**; Kundenabnahme offen | RM-521, Lauf 37528397381; Changelog 0.6.0 Zeile 143 | – |
| Orca als Flatpak: Kunde wartet auf Nachricht | offen (Robert) | RM-522, RM-064 | – |
| Renderer am echten Linux-Bildschirm, Flatpak auf echter Grafik, Offline-Start | offen | RM-051, RM-055; alle Linux-Starts unter Xvfb mit lavapipe (`check_frozen_start` mit `xvfb-run`) | echte Treiber (NVIDIA proprietär, AMD, Intel), Vulkan-Präsentation über XWayland |
| **Nativer Wayland ohne Xwayland**: keine 3D-Ansicht (rendercanvas 2.7.2 hat den Wayland-Zweig mit `if False:` abgeschaltet). Qt fällt auf `wayland` zurück, die Ansicht nennt den Grund | bekannt, gewollt; im Register steht kein offener Punkt mehr dazu | `qt_platform.py:1-27`, `:63-97`; Flatpak `--socket=x11`, `--env=QT_QPA_PLATFORM=xcb`; `ROADMAP-ARCHIV.md:20101-20111` | Wayland gibt es in der CI nicht |
| **AppImage über FUSE nie gestartet**: CI und Starttest setzen `APPIMAGE_EXTRACT_AND_RUN=1`. Laufzeitkern ist der statische type2-runtime 20251108, er braucht `fusermount`/`fusermount3` | offen (Prüflücke) | `build.yml:845-866`; `check_frozen_start.py:148-150` | Kunden starten eingehängt, aus `/tmp/.mount_*` |
| **glibc-Untergrenze 2.39** für AppImage und Archiv (Bau auf ubuntu-24.04 mit den Systembibliotheken des Runners): Ubuntu 22.04, Debian 12, Mint 21, RHEL/Alma 9 starten das AppImage nicht; das Flatpak schon | **vermutet** (gefolgert aus dem Bauort, die höchste verlangte GLIBC-Version habe ich nicht gemessen); die Website nennt keine Distribution | `build.yml:592-599` („die glibc des Servers ist die Untergrenze“); `website/index.html` (Anforderungen: „Linux (x64, X11/Xwayland)“) | Der Runner ist selbst 24.04 |
| Vulkan-Loader liegt nicht im Paket: AppImage und Archiv brauchen `libvulkan1` und einen ICD vom System; ohne startet die Anwendung ohne 3D-Ansicht und sagt es (Changelog 0.3.0) | bekannt; auf Arch/Manjaro fehlt `vulkan-icd-loader` gern | `third_party_licenses.toml` ohne Vulkan; `make_linux_packages.py:579-583` (Flatpak über Laufzeit-Mesa) | Runner installiert `libvulkan1 mesa-vulkan-drivers` ausdrücklich |
| NVIDIA im Flatpak braucht die passende `org.freedesktop.Platform.GL.nvidia-*`-Erweiterung | **vermutet**, ungeprüft | Manifest `runtime-version: '26.08'`, `--device=dri` | – |
| **3D-Maus im Flatpak unmöglich**: `/dev/hidraw*` braucht `--device=all`, das Manifest gibt nur `--device=dri` frei. Außerhalb des Flatpak braucht es eine udev-Regel (Anleitung im Handbuch) | offen | `packaging/de.rsdigital.solidon3d.yml` (finish-args); `konzept-3d-maus-2026-08.md:175-179`; `app/core/manual.py:147-196`; RM-070 („Linux, Rechte und Gerätetest“) | kein Gerät am Runner |
| **Freischaltung braucht einen Secret Service** (`keyring`, „absichtlich kein Rückfall auf eine Datei“). Ohne gnome-keyring/KWallet-Dienst (Tiling-WM, minimal installiert, KDE ohne Wallet) endet die Gerätefreischaltung mit `DeviceIdentityError`. Kein Test und kein CI-Lauf benutzt einen echten Schlüsselbund | **vermutet**, ab 01.12. kundenwirksam | `app/core/activation/device.py:1-13`, `:66-125`; Flatpak `--talk-name=org.freedesktop.secrets`; `grep` nach `SecretService`/`set_keyring` in `tests/`: kein Treffer | – |
| AppImage und Archiv aktualisieren sich nicht selbst (`updates.REPLACEABLE` ohne `KIND_APPIMAGE`/`KIND_TARBALL`); kein Registerpunkt | offen | `app/core/updates.py:346`; Erinnerung „Plattformen und Pakete“ (Stand 27.09.) | – |
| Portale im Flatpak-Start der CI tot (`xdg-desktop-portal-gtk: cannot open display`) — Dateiwahl, OpenURI, Mail übers Portal ungeprüft | offen (Prüflücke) | Paketjob 114568087245 | – |
| Slicer als Flatpak mit Signaltod hieß „keine Druckdatei“ | **Runner belegt** (Tests) | RM-621, Changelog 0.6.0 Zeile 179 | – |
| AVX-512 gegen AVX2 auf gemischten Runnern ergab andere Bits | weitgehend behoben | RM-187, RM-166 (`xfail(linux)` gefallen, 8 Läufe grün) | – |
| Hilfsprozess-Reste in `/dev/shm`, `SIGBUS` bei vollem `/dev/shm` | offen | RM-298 (b) | – |
| Echte Text- und Bildgenerierung unter Linux | offen | RM-004 | – |

---

## 5. Lücken der Prüfung

Was ein Kundengerät tut und keine CI-Prüfung abdeckt:

1. **Code-Signatur-Durchsetzung auf dem Mac.** SIP ist auf beiden Mac-Runnern aus. W^X der Hardened
   Runtime und die Bibliotheksprüfung greifen dort nicht. Ein Fehler, der nur daran hängt, ist
   in keinem Lauf sichtbar (`auslieferung.md`, letzter Punkt „Jedes Kundenpaket startet…“). Gehalten
   wird nur der **Text** des Signierschritts (`test_supply_chain.py`) und die Rücklesung im Job.
2. **Intel-Mac mit Fenster.** Kein einziger Lauf startet Solidon auf x86_64 mit Cocoa und
   3D-Ansicht. Rendererfälle laufen dort nur offscreen über `rendercanvas.offscreen`.
3. **Start wie ein Kunde.** Alle Starttests rufen die Programmdatei direkt auf, mit umgebogenem
   `HOME`/Profil. Kein Doppelklick, kein LaunchServices, kein Dock, keine TCC-Abfrage, keine
   App-Translocation, kein Update über eine bestehende (womöglich verschobene) Installation.
4. **macOS 14 und 15.** Zugesagt ab 14, geprüft nur 26.
5. **Echte GPUs.** Mac: paravirtualisiert. Linux: lavapipe unter Xvfb. Doppel-GPU-Macs, NVIDIA
   unter Linux, XWayland-Präsentation, Treiberverlust (RM-198 war Vulkan) — nur am Gerät.
6. **Wayland-Sitzungen.** Keine. Ob `prefer_x11_for_the_viewport` auf einem echten GNOME/KDE greift,
   prüfen nur die Einheitstests der Weiche.
7. **AppImage eingehängt (FUSE).** Nie; die CI packt aus.
8. **Ältere Linux-Distributionen.** Nie; Bau und Start auf 24.04.
9. **Schlüsselbund.** Keychain und Secret Service kommen in keinem Test vor; die Freischaltung (ab
   01.12. der Kaufweg) ist auf keinem echten Schlüsselbund gefahren.
10. **3D-Maus.** Kein Gerät, kein 3DxWare, keine udev-Regel am Runner; der Mac-Treiberweg ist laut
    Code nie am Gerät gemessen.
11. **Hilfsprozess nach hartem Ende des Elternprozesses** unter macOS/Linux: der Todesfall ist nur
    mit Windows-Jobobjekt geprüft.
12. **Die Intel-Kernsuite läuft am Tag nicht**, nur beim Push nach main. Seit dem 12.10. läuft beim
    Push nach main **gar nichts** mehr (Zahlung/Ausgabengrenze), also auch nicht auf Intel.
13. **Fensterauswahl beim Push** fährt nur die vom Diff berührten Fensterdateien, auf Mac und Linux
    offscreen; die volle Fenstergruppe läuft nur unter Windows.
14. **Portale im Flatpak** und der Slicer-Weg aus dem installierten Flatpak heraus sind im
    Paketstart nicht wirksam geprüft (Portale tot; Slicerauswahl läuft aus dem Quellbaum).
15. **CPU-Basis fremder Räder** (numpy, scipy, OCP, manifold3d) ist nicht gegen die älteste
    zugesagte Kunden-CPU geprüft. Die selbst übersetzten Module sind unkritisch (kein `-march`).

---

## 6. Versionen aus `constraints.txt` und `pyproject.toml`

| Paket | Fest (`constraints.txt`) | Untergrenze (`pyproject.toml`) |
|---|---|---|
| Python | CI und Pakete 3.14.8 (`build.yml`, `actions/setup-python`); Arbeitsplätze 3.14.7 (RM-468) | `>=3.14` |
| PySide6 / Essentials / Addons / shiboken6 | 6.12.0 (Qt 6.12.0, baut für macOS ab 14) | `PySide6>=6.7` |
| PySide6_Pdf / PySide6_WebEngine | 6.12.0.140 (installiert, nicht im Paket gesammelt) | – |
| wgpu | 0.32.0 | `>=0.30.1` |
| pygfx | 0.17.0 | `>=0.17` |
| rendercanvas | 2.7.2 | `>=2.6.1` |
| rubicon-objc (nur macOS) | 0.5.7 | – |
| numpy | 2.5.3 | `>=1.26` |
| scipy | 1.18.1 | `>=1.16` |
| cffi | 2.1.1 | – |
| pycparser | 3.1 | – |
| pyinstaller / hooks-contrib | 6.22.3 / 2026.8 | `>=6.0` |
| manifold3d | 3.5.4 | `>=3.1` |
| cadquery-ocp-novtk / -proxy | 8.0.1.1.0 (OCCT 8.0.1; Intel-Rad wird nachbearbeitet, RM-768) | `brep: >=8.0.1` |
| trimesh | 5.1.1 | `>=5.0` |
| shapely | 2.2.0 (GEOS 3.14.1) | `>=2.1` (RM-714 ist damit im Code erledigt, im Register noch offen) |
| hidapi | 0.15.0 | `>=0.14` |
| keyring / SecretStorage / jeepney | 25.7.0 / 3.5.0 / 0.9.0 | `keyring>=25.0` |
| pillow | 12.3.0 | – |
| scikit-image | 0.26.0 | – |
| uharfbuzz | 0.56.3 (HarfBuzz 14.6.0) | – |
| certifi | 2026.7.22 | – |
| Cython / setuptools (nur Bau) | 3.3.0 / 84.0.0 | – |
| Flatpak-Laufzeit | `org.freedesktop.Platform` 26.08 | – |
| AppImage-Werkzeuge | appimagetool 1.9.1, type2-runtime 20251108 (`build.yml:842-845`) | – |

Herkunft der Mac-Interpreter im Bau: `actions/python-versions` 3.14.8, installiert als
`/Library/Frameworks/Python.framework` (Universal2). libffi laut RM-468 3.4.4; ob `_ctypes` auf
macOS gegen Apples libffi oder die mitgebaute linkt, ist im Repository nicht belegt — die
Berechtigung deckt beide.

---

## 7. Gemessen gegen vermutet — die neuen Punkte dieser Aufnahme

| Punkt | Art | Woran es sich prüfen ließe |
|---|---|---|
| CI startet seit 12.10. keinen Job (Zahlung/Ausgabengrenze, privates Repo) | **gemessen** (Annotationen) | Abrechnung im GitHub-Konto |
| 0.6.0 mit aktiver Bibliotheksprüfung nie auf einem SIP-Mac gestartet | **gemessen** (Lücke) | Doppelklick beim Intel-Kunden |
| Bootstrap-Hänger verdeckte alles Spätere auf Intel | gefolgert | Stapel aus `solidon-diagnose.sh`, falls 0.6.0 hängt |
| Umziehbares `.pkg` aktualisiert eine andere Kopie | vermutet | `mdfind` beim Kunden |
| 3DxWare-Framework scheitert an der Bibliotheksprüfung | vermutet, aus Apples Regel und dem Code | Mac mit 3DxWare, Protokollzeile `3D mouse driver not loaded` (Debug) bzw. `log show` mit `Library Validation` |
| 3D-Maus im Flatpak ohne `--device=all` unmöglich | gefolgert aus Manifest und Konzept | Flatpak mit SpaceMouse |
| Linux-AppImage verlangt glibc ≥ 2.39 | gefolgert aus dem Bauort | `objdump -T` über die `.so` im AppImage, höchste `GLIBC_`-Version |
| Freischaltung ohne Secret Service unmöglich | gefolgert aus `device.py` | Sitzung ohne Secret Service, *Gerät freischalten* |
| Website/Changelog versprechen den Intel-Start ohne Feldbeleg | gemessen (Text) | – |
| `rendercanvas.async` als Hidden Import existiert nicht | gemessen (PyInstaller-Warnung) | – |
| RM-714 im Code erledigt (`shapely>=2.1`), im Register offen | gemessen | – |
| Wegwerf-Workflow `mac-netz.yml` (RM-187, „Werkzeug auf Zeit“) liegt noch in `.github/workflows/` | gemessen | – |
