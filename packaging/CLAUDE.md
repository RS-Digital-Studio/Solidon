# `packaging/` — was das Paket zusammenhält

Die Vorlagen und Beschreibungen, aus denen die Installationsdateien entstehen.
Gebaut wird nicht von hier, sondern über `tools/` und den Skill `/erzeugen`.

## Die Karte

| Datei | Für |
|---|---|
| `solidon3d.spec` | PyInstaller — **die Quelle für alle Plattformen** |
| `solidon3d.iss` | Inno Setup, der Windows-Installer |
| `de.rsdigital.solidon3d.yml` | Flatpak |
| `de.rsdigital.solidon3d.xml` | AppStream-Zuordnung |
| `de.rsdigital.solidon3d.metainfo.xml` | Was der Software-Katalog unter Linux zeigt |
| `solidon3d.desktop` | Startmenü-Eintrag unter Linux |
| `macos-distribution.xml`, `macos-conclusion.txt` | Das macOS-Paket |
| `install.sh` | Linux von Hand |
| `solidon3d.ico`, `solidon3d.icns` | Symbole je Plattform — **erzeugt** von `tools/make_icon.py` |
| `eula.txt` | Die Fassung, die der Installer zeigt — **erzeugt** von `tools/make_legal.py` aus `EULA.md` |
| `DATENSCHUTZ.md` | Lokale, mitgelieferte Fassung für den KI-Hinweis; ohne Webabruf im Fenster gelesen |

## Die Symbolquelle liegt woanders

`app/images/icon/solidon3d.svg` (und `-small.svg`) ist die Quelle.
`tools/make_icon.py` rastert daraus die `.ico` und die `.icns` **hierher** und
legt zusätzlich `website/icon.svg` als Kopie ab. Was die exe zeigt und was das
Fenster zeigt, ist damit dasselbe.

Zwei Dateien hier sind also Ergebnisse, keine Quellen — sie werden nicht von
Hand bearbeitet.

## Der Installer wird zweimal gerufen, und nicht gleich

Von Hand doppelgeklickt zeigt `solidon3d.iss` seine Seiten und am Ende ein
Häkchen zum Starten. **Aus der Anwendung heraus läuft er still** — Solidon
übergibt `/SILENT /NORESTART /RESTARTAPP=1` (`updates.SETUP_ARGUMENTS`), und der
letzte Schalter ist keiner von Inno Setup, sondern unserer: Ein zweiter
`[Run]`-Eintrag liest ihn über `Check: WantsRestart` und holt das Fenster zurück.

Der vorhandene Eintrag kann das nicht — er trägt `skipifsilent` und greift beim
stillen Lauf gerade nicht. Wer an einem der beiden dreht, dreht am anderen mit;
`tests/test_updates.py` hält Argumentliste und Skript zusammen.

**Auf den anderen beiden Plattformen sieht es anders aus, und das ist
entschieden:** macOS bleibt beim `.pkg` und zeigt Apples Installer (Robert,
28.08.2026). Linux liefert **ab der nächsten Version** zwei Dateien aus:
AppImage zum direkten Start und Flatpak zur verwalteten Installation. Das
AppImage wird nicht installiert; nach dem einmaligen Setzen des Ausführrechts
startet es per Doppelklick. Werkzeug 1.9.1 und der eingebettete
Type-2-Laufzeitkern 20251108 kommen aus festen Veröffentlichungen, werden vor
dem Lauf gegen ihre SHA-256-Prüfsummen geprüft und über
`APPIMAGETOOL_RUNTIME_FILE` ausdrücklich verbunden. Das Flatpak-Bundle spielt die Anwendung mit
`flatpak install` ein und kommt mit `flatpak run` zurück — **ohne Repo**, weil
`flatpak install` eine Bundle-Datei unmittelbar nimmt. Das tar.gz bleibt ein
Bauartefakt und wird nicht hochgeladen.

Die macOS-Pipeline trennt drei Vertrauensräume. Der Paketjob bindet den
vollständigen App-Baum als `ditto`-Archiv samt SHA-256. Ein geschützter Job ohne
Checkout oder Python prüft Archiv, Produktkennung, Architektur und interne
Symlinks, importiert die Developer-ID nur für den festen `codesign`-Aufruf und
löscht den Schlüsselbund noch im selben Schritt. Danach baut ein
**ungeschützter** Job mit `make_macos_package.py` das `.pkg`; erst ein zweiter
geschützter Job signiert es mit `productsign`. Die nicht geheime Repository-
Variable `MACOS_SIGNING_MODE` wählt `unsigned`, `signed` oder `notarized`.
Nur wenn die Apple-Angaben vollständig sind und `notarytool`, `stapler` und
`spctl` grün bleiben, nennt der Schlusstext das Paket geprüft. Der unsignierte
Weg betritt keinen geschützten Job und behält den Gatekeeper-Hinweis.

Windows wird in der CI gebaut und **lokal signiert**. Der Paketjob hat nur
lesenden Repositoryzugriff und keine Windows-Geheimnisse. Er übergibt den
**vollständigen** App-Baum sowie die festen Installer-Eingänge als kanonische
relative Pfadliste mit SHA-256 (Artefakt `solidon3d-windows-signing-input`,
sieben Tage haltbar). Ein ungeschützter Job baut daraus mit ISCC den
unsignierten Installer für Demo und Releaseprüfung und nennt SmartScreen
ausdrücklich. Die Signatur entsteht auf Roberts Rechner mit
**Die Setup-Datei packt blockweise aus, nicht in einem Strom** (Entscheidung
Robert, 03.09.2026): `SolidCompression=no` und `Compression=lzma2/normal`. Das
kostet gemessene 23 MB gegenüber der kleinsten baubaren Fassung und nimmt dafür
beiden Empfindlichkeiten: Ein gekipptes Bit beschädigt eine Datei statt des
Reststroms, und das Wörterbuch belegt 8 statt 32 bis 64 MB Arbeitsspeicher. Die
Messreihe, der Anlass und die Falle mit `LZMADictionarySize` — die Direktive
wirkt nicht — stehen im Kommentar über den beiden Zeilen in `solidon3d.iss`;
`tests/test_packaging.py` hält sie fest.

`tools/sign_release.py` aus demselben Archiv: Das Certum-Zertifikat liegt in
der SimplySign-Cloud und verlangt einen Einmalcode vom Handy, den keine CI
eingeben kann und soll. Das Werkzeug prüft Archiv, Produktangaben und jede
Prüfsumme, signiert die Anwendung, bindet die Übergabe neu, baut den
Installer, signiert die Setup-Datei und schreibt die `.sha256` daneben. Einen
Azure- oder PFX-Weg gibt es nicht mehr (Entscheidung Robert, 02.09.2026):
Azure Artifact Signing verlangt eine Organisation mit drei Jahren Bestand,
und exportierbare PFX-Schlüssel geben die Zertifizierungsstellen seit 2023
nicht mehr heraus. Der Weg je Plattform steht in `Signierung/README.md`.

## Was hier hineinmuss, wenn sich etwas ändert

- **Eine neue Abhängigkeit** kann in der `.spec` fehlen und erst im gebauten
  Paket auffallen — dort, wo kein `pip` mehr hilft.
- **Ein Asset ohne Rechtefreigabe** stoppt die `.spec` vor `Analysis` über
  `tools/asset_rights.py`. Maßgeblich ist `ASSET-RIGHTS.toml`; das Tor prüft
  Schema und beigefügte Nachweise sowie die vollständige, überschneidungsfreie
  Abdeckung aller Anwendungsmedien. Website-Sperren bleiben am Website-Tor,
  Anwendungssperren gelten gleich für alle dort genannten Zielsysteme. Nach
  dem fertigen `COLLECT` beziehungsweise macOS-`BUNDLE` schreibt die Spec
  zusätzlich `Solidon3D-rights.json` in den Datenordner des Artefakts. Der
  Beleg bindet Manifest, Prüflogik, Spec, Quellbytes und die tatsächlich
  kopierten App-Medien; jeder nachfolgende Plattform-Paketierer prüft ihn
  erneut und verwirft veraltete oder nachträglich veränderte `dist`-Bäume.
- **Die Stückliste** entsteht mit `tools/make_sbom.py` aus PyInstallers
  `Analysis` und dem anschließend fertigen Kundenartefakt: Nur Distributionen
  aus Solidons Laufzeitbaum, deren Importpakete tatsächlich im Analyseergebnis
  stehen, gelangen hinein; CPython, PyInstaller-Bootloader, Kryptografie- und
  Compilerlaufzeiten sowie jede PE-/ELF-/Mach-O-Datei werden aus dem fertigen
  Paket inventarisiert. Sie reist genau einmal im Kundenartefakt mit; eine
  eingecheckte plattformspezifische Kopie gibt es absichtlich nicht.
  PySide6-Essentials weist Qt, cadquery-ocp-novtk OCCT, Shapely GEOS und VTK
  seine nativen Bibliotheken als eigene Komponenten mit gewählter
  Lizenzgrundlage aus. Windows bindet die exakte libffi-Version an den
  festgeschriebenen CPython-Patchstand; Linux liest sie über `pkg-config` aus
  der tatsächlich gebündelten Systembibliothek. Die Microsoft-Laufzeit trägt
  die sortierte Menge der `FileVersion`-Werte aller mitgereisten PE-Dateien,
  nicht die bloße Compilerangabe. Die CI prüft auf macOS nur die `.app`, nicht
  zusätzlich den stehen gebliebenen COLLECT-Zwischenordner.
- **Das Linux-Paket nimmt Systembibliotheken nur mit Familie mit.** Die Spec
  lässt auf Linux das GTK-3-Erscheinungsbild von Qt (`platformthemes/libqgtk3`)
  und den Grundbestand jedes Linux draußen — X11-Kern, fontconfig, freetype,
  glib/dbus/systemd — nach der Liste in `make_linux_packages.HOST_PROVIDED_LIBRARIES`,
  dazu die Terminalmodule `readline`/`curses` (libreadline ist GPL-3, Regel 15).
  Was bleibt — libxcb mit den xcb-util-Bibliotheken, xkbcommon, die
  Kerberos-Familie —, ordnet `make_sbom.LINUX_LIBRARY_FAMILIES` je Soname
  einer Familie zu, und `dpkg-query` liest beim Bau die Fassung aus dem Paket
  des Bauservers. Symlinks zählen nicht als Datei, CPythons `lib-dynload`
  gehört CPython, `<name>.libs` seiner Distribution. Eine native Datei ohne
  Familie lässt `make_licence_notices --release-check` nicht durch — gemessen
  am 0.2.1-Paket waren es 135, am Windows-Paket 30, am macOS-Paket 41.
- **Die Lizenzbeilage** entsteht nach der SBOM mit
  `make_licence_notices.py --sbom`: `THIRD-PARTY-NOTICES.md` liegt genau einmal
  neben der ausführbaren Datei und wird dort auch vom Über-Dialog gelesen. Die
  PyInstaller-Spec nimmt die eingecheckte Entwicklungsfassung ausdrücklich
  nicht mit. Das Schema-2-JSON bleibt in der CRA-/Buildakte. Vor der
  äußersten Veröffentlichung prüft `--release-check` fail-closed die
  Endartefakt-SBOM, Schema-1-Evidenz, äußeren Pakete, exakte Versionen sowie
  erforderliche Quellarchive und Relink-Materialien. Diese Prüfung läuft
  ungeschützt und erst nach der Signierung; ein Signierjob führt keinen
  Repositorycode dafür aus. Auf Windows schreibt `sign_release.py` die
  Evidenz nach der lokalen Signatur neu und wiederholt die Prüfung, weil
  der äußere Installer dann ein anderer ist als der, den die CI geprüft hat.
- **Windows-ICU** kommt aus dem Betriebssystem. Die `.spec` verwirft
  `icuuc.dll` und `icudt*.dll` aus dem `PATH`; eine zufällig eingesammelte
  Poppler-ICU lässt den fertigen Bau schon beim Import von `QtCore` stehen.
- **Ein neues Datenverzeichnis** (Kataloge, Profile, Bausteindaten) reist nur
  mit, wenn die `.spec` es kennt.
- **Die Version** kommt aus `app/branding.py` über `tools/bump_version.py` —
  hier wird sie nicht getippt.
- **Eigene Dateitypen** lesen Endung und MIME-Typ aus `app/branding.py` und
  werden auf Windows, macOS und Linux gemeinsam eingetragen. `.p3d` bleibt der
  Projektcontainer; `.solidon-part` ist das portable JSON-Rezept eines
  Bausteins. Die allgemeine Endung `.json` wird nie Solidon zugeordnet.

`tests/test_packaging.py` prüft, was sich prüfen lässt, ohne zu bauen.

## Der eigene Arbeitsbaum

Paketiert wird in einem **eigenen** Arbeitsbaum, nicht im Entwicklungsbaum —
sonst wandert hinein, was gerade offen ist. Die Reihenfolge und die Falle mit
den fehlenden Schriften stehen im Skill `/erzeugen`.
