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

Windows unterstützt Azure Artifact Signing über OIDC. Der normale Paketjob
hat nur lesenden Repositoryzugriff, kein OIDC und keine Windows-Geheimnisse. Er
übergibt den **vollständigen** App-Baum sowie die festen Installer-Eingänge als
kanonische relative Pfadliste mit SHA-256. Azure signiert die Anwendung in
einem über `production-signing` geschützten OIDC-Job; danach baut ein
ungeschützter Job den Installer mit ISCC, und ein zweiter geschützter OIDC-Job
signiert ausschließlich dessen fest benannte Datei. Der PFX-Weg hat dieselben
zwei Signiergrenzen, aber ausdrücklich kein OIDC; jede PFX-Datei wird im festen
Signierschritt in `finally` entfernt. Die nicht geheime Repository-Variable
`WINDOWS_SIGNING_MODE` wählt `azure`, `pfx` oder `unsigned`. Für Azure stehen
`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
`ARTIFACT_SIGNING_ENDPOINT`, `ARTIFACT_SIGNING_ACCOUNT` und
`ARTIFACT_SIGNING_PROFILE` stehen, signiert die CI Anwendung und Setup-Datei
mit der offiziellen Aktion und prüft beide Signaturen. Der bisherige
PFX-Secret-Weg bleibt als Rückfall für ein vorhandenes älteres Zertifikat;
fehlen beide Wege, nennt der Baulauf SmartScreen ausdrücklich.

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
  der tatsächlich gebündelten Systembibliothek. Die CI prüft auf macOS nur die
  `.app`, nicht zusätzlich den stehen gebliebenen COLLECT-Zwischenordner.
- **Die Lizenzbeilage** entsteht nach der SBOM mit
  `make_licence_notices.py --sbom`: `THIRD-PARTY-NOTICES.md` liegt genau einmal
  im fertigen App-Baum, das Schema-2-JSON bleibt in der CRA-/Buildakte. Vor der
  äußersten Veröffentlichung prüft `--release-check` fail-closed die
  Endartefakt-SBOM, Schema-1-Evidenz, äußeren Pakete, exakte Versionen sowie
  erforderliche Quellarchive und Relink-Materialien. Diese Prüfung läuft
  ungeschützt und erst nach der Signierung; ein Signierjob führt keinen
  Repositorycode dafür aus.
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
