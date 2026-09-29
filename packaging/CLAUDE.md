# `packaging/` — was das Paket zusammenhält

Die Vorlagen, aus denen die Installationsdateien entstehen. Gebaut wird über
`tools/` und den Skill `/erzeugen`, und zwar in einem **eigenen Arbeitsbaum**,
nicht im Entwicklungsbaum — sonst wandert hinein, was gerade offen ist
(Reihenfolge und die Falle mit den fehlenden Schriften: `/erzeugen`).
Einzuhalten ist `.claude/rules/auslieferung.md` (lädt für `packaging/**`); das
Warum und die Messwerte: `konzepte/begruendungen/karte-packaging.md`.

Die Python-Installation verwendet daneben `pyproject.toml`: Dessen
`package-data` nimmt die Anwendungsressourcen ausdrücklich mit, auch ohne
editierbare Installation. `tests/test_packaging.py` vergleicht die echte
Setuptools-Dateiauswahl mit den versionierten Ressourcen; lokale
`egg-info`-Listen dürfen fehlende Einträge nicht verdecken.

## Die Karte

| Datei | Für | Quelle |
|---|---|---|
| `solidon3d.spec` | PyInstaller — **die Quelle für alle Plattformen** | von Hand |
| `solidon3d.iss` | Inno Setup, der Windows-Installer; eigene Werte trägt er nicht, `tools/make_installer.py` übergibt sie | von Hand |
| `de.rsdigital.solidon3d.yml` | Flatpak-Manifest | `tools/make_linux_packages.py` |
| `de.rsdigital.solidon3d.metainfo.xml` | Was der Software-Katalog unter Linux zeigt | `tools/make_linux_packages.py` |
| `de.rsdigital.solidon3d.xml` | Die Dateitypen für Linux (shared-mime-info) | `tools/make_linux_packages.py` |
| `solidon3d.desktop` | Startmenü-Eintrag unter Linux | `tools/make_linux_packages.py` |
| `install.sh` | Linux-Installation von Hand aus dem Archiv | `tools/make_linux_packages.py` |
| `macos-distribution.xml`, `macos-conclusion.txt` | Das macOS-Paket | `tools/make_macos_package.py` |
| `solidon3d.ico`, `solidon3d.icns` | Symbole je Plattform | `tools/make_icon.py` |
| `eula.txt` | Die Fassung, die der Installer zeigt | `tools/make_legal.py` aus `EULA.md` |
| `build/` | Prüfmodul, Lizenzmanifest, Signierübergabe — nicht versioniert | `tools/build_licence_module.py`, `make_installer.py` |

**Nur `.spec` und `.iss` sind Quelle**; alles andere ist Ergebnis, trägt seine
Werte aus `app/branding.py` und wird nicht von Hand bearbeitet — der nächste
Lauf überschreibt es. **Die Symbolquelle** ist
`app/images/icon/solidon3d.svg` (und `-small.svg`): `make_icon.py` rastert
`.ico` und `.icns` hierher und legt `website/icon.svg` ab — exe und Fenster
zeigen dasselbe. `DATENSCHUTZ.md` aus der Wurzel reist über die `.spec` mit:
die lokale Fassung für den KI-Hinweis, ohne Webabruf gelesen.

## Wie jede Plattform installiert

- **Windows, zweimal gerufen und nicht gleich**: doppelgeklickt zeigt
  `solidon3d.iss` seine Seiten und ein Häkchen zum Starten; **aus der
  Anwendung läuft er still** mit `/SILENT /NORESTART /RESTARTAPP=1`
  (`updates.SETUP_ARGUMENTS`). Der letzte Schalter ist unserer: Ein zweiter
  `[Run]`-Eintrag liest ihn über `Check: WantsRestart`, weil der erste
  `skipifsilent` trägt. Wer an einem dreht, dreht am anderen mit;
  `tests/test_updates.py` hält beide zusammen.
- **Das Setup packt blockweise aus** (Entscheidung Robert):
  `SolidCompression=no`, `Compression=lzma2/normal` — ein gekipptes Bit trifft
  eine Datei statt des Reststroms, das Wörterbuch belegt 8 statt 32 bis 64 MB.
  `LZMADictionarySize` wirkt nicht; Messreihe und Anlass stehen im Kommentar
  über den beiden Zeilen, `tests/test_packaging.py` hält sie.
- **macOS** bleibt beim `.pkg` mit Apples Installer (Entscheidung Robert).
- **Linux: AppImage und Flatpak.** Das AppImage wird nicht installiert, nach
  einmaligem Ausführrecht startet es per Doppelklick; `appimagetool` 1.9.1 und
  der Type-2-Laufzeitkern 20251108 kommen aus festen Veröffentlichungen, gegen
  SHA-256 geprüft und über `APPIMAGETOOL_RUNTIME_FILE` verbunden. Das
  Flatpak-Bundle nimmt `flatpak install` unmittelbar, **ohne Repo**, und
  `flatpak run` startet es. Das tar.gz bleibt ein Bauartefakt.

## Signieren

- **macOS in drei Vertrauensräumen**: Der Paketjob bindet den App-Baum als
  `ditto`-Archiv mit SHA-256; ein geschützter Job ohne Checkout oder Python
  prüft Archiv, Produktkennung, Architektur und Symlinks, importiert die
  Developer-ID nur für `codesign` und löscht den Schlüsselbund im selben
  Schritt; ein **ungeschützter** Job baut mit `make_macos_package.py` das
  `.pkg`, ein zweiter geschützter signiert mit `productsign`.
  `MACOS_SIGNING_MODE` wählt `unsigned`, `signed` oder `notarized`; „geprüft“
  heißt es nur mit grünem `notarytool`, `stapler` und `spctl`.
- **Windows: zwei CI-Schritte, dazwischen und danach lokal signiert** — kein
  Job bekommt ein Signiergeheimnis, der Anwendungsbau liest nur.
  1. `build.yml` übergibt den **vollständigen** App-Baum und die festen
     Installer-Eingänge als kanonische Pfadliste mit SHA-256 (Artefakt
     `solidon3d-windows-signing-input`, sieben Tage); der daneben gebaute
     unsignierte Installer dient nur der Releaseprüfung.
  2. `tools/sign_release.py --phase application` prüft lokal Herkunft,
     Archiv, Produktangaben und jede Prüfsumme, signiert nur die Anwendung und
     legt EXE und Herkunftsakte in einen unveröffentlichten Release-Entwurf.
  3. `windows-signed-installer.yml` (manuell auf `main`) nimmt die Eingänge
     eines grünen Anwendungslaufs (manuell auf `main` oder am Versions-Tag)
     und die signierte EXE, prüft Herkunft, Hash, Zeitstempel und
     Herausgeber, ersetzt nur die EXE und baut mit Inno Setup 7 Setup,
     `.sha256` und
     `windows-installer-build.json` (Installercommit und Lauf). Ein
     abweichender Commit ist nur erlaubt, wenn die Git-Bäume außerhalb der
     Signierablauf-Dateien gleich sind (vor der lokalen Setupsignatur erneut
     geprüft); dann laufen vorher `test_sign_release.py` und
     `test_windows_signed_installer.py`. Der Job braucht `contents: write` für
     den Entwurf und veröffentlicht nichts.
  4. `tools/sign_release.py --phase installer` prüft den Rückweg, signiert das
     Setup und schreibt Prüfsumme und Releaseakte. Lokal wird kein Installer
     gebaut.
- Das Certum-Zertifikat liegt in der SimplySign-Cloud und verlangt einen
  Einmalcode vom Handy; einen Azure- oder PFX-Weg gibt es nicht (Entscheidung
  Robert). Aufruf und Übergabevertrag: `Signierung/README.md`.

## Was hier hineinmuss, wenn sich etwas ändert

- **Geänderte Projektanforderungen**: Eine alte `solidon3d.egg-info` im
  Wurzelordner kann die frische `.dist-info` überdecken; mit
  `python -c "from setuptools import setup; setup(script_args=['egg_info'])"`
  angleichen, dann müssen Laufzeitbaum und `tools/check_env.py` die
  Anforderungen bestätigen, bevor `make_licence_notices.py` die Beilage baut.
- **Eine neue Abhängigkeit** kann in der `.spec` fehlen und erst im gebauten
  Paket auffallen. Die Ansicht braucht einen wgpu-Adapter (Direct3D 12,
  Vulkan, Metal; WARP unter Windows, unter Linux ein Vulkan-Softwareadapter
  wie lavapipe) — wgpu liefert keinen mit. VTK, PyVista, PyVistaQt und QtPy
  reisen nicht mit; die Wandstärke der Bereichsprüfung rechnet
  `core/geom/mesh.ray_hits_batch`. Den Schichtkern wählt
  `build_slice_core.current_extensions()` — eine fremde ABI oder Architektur
  wird nicht eingesammelt. Die Vorschau der Lizenzbeilage entsteht mit dem
  Interpreter des neuen Versionssatzes und ersetzt keinen nativen Nachweis.
- **Ein Asset ohne Rechtefreigabe** hält die `.spec` vor `Analysis` an
  (`tools/asset_rights.py` gegen `ASSET-RIGHTS.toml`: Schema, beigefügte
  Nachweise, lückenlose Abdeckung). Nach `COLLECT` bzw. `BUNDLE` schreibt sie
  `Solidon3D-rights.json` in das Artefakt; jeder Plattform-Paketierer prüft
  diesen Beleg erneut und verwirft veränderte `dist`-Bäume.
- **Die Stückliste** (`tools/make_sbom.py`) nimmt nur Distributionen, deren
  Importpakete in der Analyse stehen, und inventarisiert CPython, Bootloader,
  Laufzeiten und jede PE-/ELF-/Mach-O-Datei aus dem fertigen Paket; sie reist
  genau einmal im Artefakt (Name: `make_sbom.ARTIFACT_SBOM_NAME`), eine
  eingecheckte Kopie gibt es nicht. Qt, OCCT und GEOS stehen als eigene
  Komponenten; libffi folgt unter Windows dem CPython-Patchstand, unter Linux
  `pkg-config`; die Microsoft-Laufzeit trägt die `FileVersion`-Menge aller
  PE-Dateien. Die CI prüft auf macOS nur die `.app`.
- **Linux nimmt Systembibliotheken nur mit Familie mit**: draußen bleiben das
  GTK-Erscheinungsbild samt Stapel (`make_linux_packages.ORPHANED_LIBRARIES`)
  und `readline`/`curses` (GPL-3, Regel 15); alles andere reist mit.
  `make_sbom.LINUX_LIBRARY_FAMILIES` ordnet jeden Soname einer Familie zu,
  `dpkg-query` liest die Fassung vom Bauserver; Symlinks zählen nicht,
  `lib-dynload` gehört CPython, `<name>.libs` seiner Distribution. Eine Datei
  ohne Familie hält `make_licence_notices --release-check` an. Kopiert wird
  mit `copytree(..., symlinks=True)` — dereferenziert entstünden Kopien
  außerhalb ihres Paketpfads.
- **Die Lizenzbeilage** (`make_licence_notices.py --sbom`):
  `THIRD-PARTY-NOTICES.md` liegt genau einmal neben der ausführbaren Datei
  (der Über-Dialog liest sie dort), die Entwicklungsfassung nimmt die `.spec`
  nicht mit, das Schema-2-JSON bleibt in der Buildakte. `--release-check`
  hält den Release an; das AppImage trägt eine eigene Stückliste mit dem
  Laufzeitkern (`make_linux_packages.embed_appimage_runtime`) und wird mit
  `--artifact-kind appimage` geprüft.
- **Windows-ICU** kommt aus dem Betriebssystem: Die `.spec` verwirft
  `icuuc.dll` und `icudt*.dll` aus dem `PATH` — eine eingesammelte
  Poppler-ICU lässt den Bau beim Import von `QtCore` stehen.
- **Ein neues Datenverzeichnis** (Kataloge, Profile, Bausteindaten) reist nur
  mit, wenn die `.spec` es kennt; **die Version** kommt aus `app/branding.py`
  über `tools/bump_version.py`.
- **Eigene Dateitypen** lesen Endung und MIME-Typ aus `app/branding.py`, auf
  allen drei Plattformen gemeinsam: `.p3d` ist der Projektcontainer,
  `.solidon-part` das JSON-Rezept eines Bausteins; `.json` wird nie Solidon
  zugeordnet.

## Prüfen

`tests/test_packaging.py` prüft, was sich ohne Bau prüfen lässt. Die CI fährt
die Fensterdateien je Prozess als Tor auf allen Plattformen; fehlende Sammlung
oder ein roter Prozess sperren die Paketierung, ein fehlender wgpu-Adapter ist
dort ein Fehler (lokal ein Skip mit Grund), und Linux installiert Vulkan-Loader
und lavapipe auch im Versionswächter. Der Handstart mit `tests_only=true`
fährt Suite und Versionswächter und sperrt alle Paket-, Signier- und
Releaseaktenjobs. `test_render_factory.py` prüft in eigenem Prozess den
nativen Qt+pygfx-Weg auf `windows`, `cocoa` und `xcb` unter Xvfb.
