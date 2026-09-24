# `tools/` — Hilfsprogramme

Nicht Teil der Anwendung. **Was hier liegt, reist nicht im gebauten Paket
mit** — deshalb steht alles, was der Nutzer aus der laufenden Anwendung heraus
tun können soll, im Kern (etwa `app/core/backends/comfy_setup.py`).

Es gibt hier **keine** eigene Regeldatei in `.claude/rules/`. Was gilt, ist
`AGENTS.md` — und die Sprachregel gilt hier wie in `app/`: englische
Bezeichner, deutsche Docstrings, weil `tools/` das Paket baut und jemand das
liest, der das Projekt nicht kennt.

## Das Prinzip, das die meisten dieser Werkzeuge erklärt

> **Was erzeugt wird, wird nicht getippt — und was getippt bleibt, bekommt
> einen Wächter.**

Vier Werkzeuge, drei Wächter, ein Thema: `stamp_assets.py` schreibt die
Inhaltsstempel, `test_every_reference_carries_the_stamp_of_the_file_it_points_at`
liest nach; `make_download.py` trägt die Paketgrößen ein, und
`test_the_technical_requirements_name_the_sizes_the_packages_have` hält sie
gegen `version.json`; `sync_agents.py` erzeugt die Codex-Agentenprofile und
Skills aus den Claude-Quelldateien, und `test_agent_mirror.py` fährt sein `--check`. Eine
getippte Zahl auf der Website ist ein Fehler, der auf sein Datum wartet.

`sync_agents.py` liest ausschließlich `.claude/agents/` und `.claude/skills/`
als Quellen. Es prüft alle Eingaben vor dem Schreiben, übersetzt Skillaufrufe
und erzeugt Codex-Aufrufregeln aus `disable-model-invocation`. Referenzen
reisen mit; Zeilenenden von Git gelten nicht als Drift. Dateien ohne Quelle
werden gemeldet und nicht gelöscht. Ein neues Agenten-Frontmatter-Feld braucht eine
bewusste Übersetzung, damit eine Claude-Regel nicht unbemerkt bei Codex fehlt.

**Und was hier sucht, sucht zuerst einen Fall, dessen Ausgang bekannt ist.**
`twin_scan.py` hat seinen Selbsttest (`tests/test_twin_scan.py`), und der hat
sich am ersten Tag bezahlt: Die Mindestgröße stand auf vier Anweisungen, und
der Zwilling, für den das Werkzeug gebaut wurde, besteht aus drei. Ein
Suchwerkzeug, das zu wenig findet, **schweigt** — und Schweigen sieht aus wie
ein sauberes Ergebnis.

## Die Familien

Aufnahmewerkzeuge reichen ihre feste Merkmalskennung als Argument bis zur
Auswahl und Beschriftung durch; sie ergänzen keine Attribute an `Session`.
Kreisflug-Loops warten zusätzlich auf den eigenen Arbeiter der Druckanalyse
im Fenster, damit Standbild und Film denselben vollständigen Prüfbericht zeigen.
Nach Abschluss einer bewusst verworfenen Aufnahme räumt `Session.forget_changes()`
deren Änderungsmarkierung und eigene Wiederherstellung. Die Quelldatei bleibt
dabei ungeschrieben; das anschließende Schließen läuft durch den normalen
Fenster- und Arbeiterabbau.

**Umgebung und Git**

| Werkzeug | Tut |
|---|---|
| `check_env.py` | Prüft die Umgebung gegen den festgeschriebenen Stand — **und stellt ihn her** |
| `sync_agents.py` | Erzeugt Codex-Agenten und Skills aus `.claude/agents/` und `.claude/skills/` (`--check` im Tor) |
| `link_memory.py` | Die Erinnerungen ins Repository hängen — einmal je Maschine |
| `memory_index.py` | Eine Zeile in `MEMORY.md` einfügen — unter Sperre, atomar, mit Nachzählen |
| `check_message.py` | Der `commit-msg`-Hook: Ersatzschreibung statt Umlaut in einer Commit-Meldung |
| `check_part_ranges.py` | Der Bereichsnachweis der Bausteine (§24.3): fährt je Baustein den Bereichstest in einem eigenen Prozess und schreibt `data/part_ranges.toml`; `--check` vergleicht nur |

**Die beiden Erinnerungswerkzeuge tun Verschiedenes**, und die Namen sagen es
nicht von selbst: `link_memory.py` hängt das Verzeichnis einmal je Maschine
ein und fasst `MEMORY.md` nie an; `memory_index.py` schreibt genau eine Zeile
hinein. Es hält dafür eine Sperrdatei daneben, liest den Index **unter** der
Sperre und zählt vor dem Schreiben nach — ohne das gehen bei zwei gleichzeitig
schreibenden Sitzungen Einträge verloren, gemessen 17 bis 20 von 40
(`tests/test_memory_index.py`, mit zwei echten Prozessen).

`link_memory.py` reserviert bei Konflikten
freie Sicherungsnamen exklusiv; vor dem Entfernen des lokalen Bestands wird
jede Datei am tatsächlich gewählten Ziel bytegenau geprüft.

**Messen und Prüfen** (keines davon ist ein Testlauf)

`run_suite_isolated.py` (je Testdatei ein Prozess; Fenstertests nur mit
`--release`, Leistung stets getrennt beim Release) · `run_agent_suite.py`
(39 Referenzanfragen, **kostet Geld**) · `run_model_suite.py` (die Kette über
echte Modelle) · `run_ui_audit.py` (der ganze Bestand durch die laufende
Oberfläche) · `check_local_model.py` (ruft ein lokales Modell die Werkzeuge
wirklich auf?) · `measure_local_model.py` (**wie lange** braucht es dafür — kalt gegen warm getrennt, Median **und** Spanne, die Lage aus `api/ps` in jeder Zeile, und am Ende ein `keep_alive: 0`, weil 15 GB nach dem Messen den Rechner zäh machen;
`--count-tokens` zählt dagegen genau einen vollständigen Auftrag ohne
Geschwindigkeitsmessung und belegt Modell, Kontext, Werkzeugzahl und
Anfrage-SHA-256) · `check_support.py` (kommt die Rückmeldung an?) ·
`check_activation.py` (ist der öffentliche Aktivierungsdienst bereit?) ·
`licence_admin.py` (private Support-Oberfläche: MoR-Transaktion einem
Vorratsschlüssel zuordnen, Käufer im externen Schlüsselarchiv finden,
Serverzustand lesen und Geräteplätze verwalten) ·
`qt_trace.py` (pytest-Erweiterung für die Jagd auf den Abriss beim Aufräumen) ·
`list_windowed_tests.py` (Dateien mit Fenstertests aus Pytests aufgelöstem
Fixture-Graphen oder dem Marker `windowed` für Fenster außerhalb der
`qt_app`-Fixture, insbesondere in Kindprozessen; setzt den Marker für
`tests/conftest.py`, und `--window-group` wählt als Laufplugin je Test) ·
`twin_scan.py` (doppelte Stellen und Zwillinge in einem Baum: sieben Fragen von
Konstanten über wortgleiche und strukturgleiche Körper bis zu Kommentaren, die
eine Kopie zugeben — **welche Klasse ein Fund hat, entscheidet der Code**, die
vier Klassen stehen in `konzepte/konzept-zwillinge-2026-09.md`; es steht
ausdrücklich **nicht** im Tor, dort halten `tests/test_shared_constants.py` die
Konstanten) ·
`docs_scan.py` (was die Unterlagen kosten und wo sie sich wiederholen: die
Ladelast je Quelldatei aus Karte und passenden Regeln, derselbe Absatz in zwei
Unterlagen, Verweise auf Quelldateien, die es nicht gibt, und `paths:`-Muster
ohne Treffer — ebenfalls **nicht** im Tor, dort hält `test_directory_docs.py`
die Vollständigkeit der Karten; die Durchsichten liegen in `.claude/audits/`) ·
`affected_tests.py` (welche Testdateien eine Änderung berührt — aus dem
Importgraphen über `app/`, `tools/` und `tests/`, dazu die Baumleser und die
Tests, die eine geänderte Textdatei beim Namen nennen; `--why`, `--split`,
`--run`; reine Auswahl und `--why` nennen alle betroffenen Dateien,
`--split` und `--run` fahren die Tests ohne Fenster, nehmen Fenstertests erst mit
`--release` auf und lassen
Leistung stets draußen. `list_windowed_tests` liefert aus derselben Sammlung
die Dateien mit Fenstertests und die Dateien mit Tests ohne Fenster — eine
Datei kann in beiden stehen; reine Leistungsdateien lösen keinen leeren
pytest-Lauf aus. Die Einteilung liest jeden aufgelösten Fall vor der Abwahl:
`-k`, `-m`, `--deselect` und Filter aus `PYTEST_ADDOPTS` oder der
Pytest-Konfiguration ändern nicht die Gruppen; ein Fensterfall mit
`performance` zählt zu keiner. Der eigentliche betroffene Lauf behält die
Filter; `-k` und `-m` lassen sich auch direkt am Werkzeug angeben. Das
ausdrücklich geladene Laufplugin in `list_windowed_tests` verknüpft den
wirksamen Markerfilter mit `not performance` und mit der Gruppe aus
`--window-group`, statt ihn zu überschreiben) ·
`count_new_windows.py` (welche Fenster während eines Befehls aufgehen — Klasse,
Titel, Prozess; die Sichtprüfung aus RM-100 als Messung, zwanzig Abtastungen je
Sekunde über `EnumWindows`, Exit 1 bei einem neuen Konsolenfenster) ·
`window_bench.py` (Beispiel im **echten** Fenster öffnen und die Wartezeit in
Posten zerlegen — misst, was offscreen unsichtbar ist: Renderer und
Aktoraufbau, danach Arbeitsspeicher, `--drag-frames` Kamerastellungen je mit
Bild und `--shot` eine Bildschirmaufnahme dessen, was der Kunde sieht)

`window_bench.py` beendet seinen einzigen Lauf in Besitzreihenfolge: erst
Arbeiter und Sitzungsverbindungen lösen, dann über
`Viewport.release_renderer()` den Renderer bei noch lebendem
Qt-Elternfenster schließen, zuletzt das Fenster. Derselbe terminale Weg liegt
am akzeptierten `MainWindow.closeEvent`; `MainWindow.release()` bleibt für
mehrere Fenster in einem Prozess bewusst ohne Viewport-Abbau.

`window_memory.py` stellt die andere Frage am selben Fenster: **was ein
Fenster- und ein Sprachwechsel liegen lassen.** Es baut nacheinander Fenster
auf und ab und wechselt danach über `app.ui.app.rebuild_for_language` die
Sprache, misst je Runde den Arbeitssatz und meldet die **Steigung über die
zweite Hälfte** — die erste trägt den einmaligen Aufbau, und wer sie
mitrechnet, findet ein Leck, das keines ist. Es teilt Messprofil,
Arbeitssatzmessung und Abbaureihenfolge mit `window_bench.py`, statt sie zu
wiederholen. Ohne Bildschirm und wgpu-Adapter misst es nichts und sagt es.

**Erzeugen** — alles hierunter läuft über den Skill `/erzeugen`

Der Importgraph von `affected_tests.py` behält auch nicht mehr vorhandene
Importziele als Knoten, damit gelöschte Module ihre direkten und indirekten
Testabhängigkeiten behalten.

`make_manual.py` · `make_figures.py` (Bildschirmfotos) · `make_web_images.py`
· `make_icon.py` · `make_changelog.py` · `make_seo.py` · `make_legal.py` · `make_examples.py` ·
`make_video.py` · `make_longform_video.py` (deutsche und englische 3-Minuten+-Tutorials:
sichtbares leeres Projekt, echte Dialoge, höchstens einer zugleich,
Katalogbausteine, Text statt Sprecher und selbst erzeugtes Musikbett;
`--language en` wählt englische Oberfläche, Einblendungen aus
`longform_video_en.json` und englische Projektmaße samt Formelverweisen.
Die `.timeline.json` neben jedem MP4 enthält die tatsächlichen Einblendungszeiten
für die YouTube-Kapitel) ·
`make_workshop_videos.py` (STL-Tutorials über tatsächlich geöffnete Dateidialoge,
Handlungen und Eingabefelder; ein Prozess je Thema und Sprache, isolierte
Nutzerverzeichnisse vor dem App-Import. `--capture-only` bewahrt die Aufnahme,
`--encode-only` kodiert einen vollständigen Beleg. Geometriebericht, Projekt,
Schnittplan und saubere Viewportbilder liegen beim Film. Ein bereits über
`exec()` geöffneter Kundendialog behält beim Filmen seine Modalität und
Fensterflags; die Aufnahme darf ihn nur ausrichten) ·
`make_workshop_shorts.py` (schneidet daraus über `short_shots.json` die
Hochformatfassung samt Titelbild; übernimmt die belegten Zustände, prüft
Textüberlauf und den fertigen MP4-Container) ·
`make_showpiece.py` (das Schaustück der Website — ein
Teil, das in einem Bild beantwortet, warum man das Programm haben will;
gebaut über die Operations-API wie von einem Nutzer) ·
`make_gallery.py` (die Galeriebilder des Beweis-Teils: ein Teil groß, im
Viewport mit Licht und Schatten, Karten weggeschnitten — **nicht** über die
flache Projektion, die für Katalogvorschauen reicht und für Qualität nicht) ·
`make_feature_images.py` (textfreie Funktionsbilder aus registrierten Operationen:
ein Motiv je nativem Prozess, eigene Konfigurationsverzeichnisse, derselbe
pygfx-Renderer wie im Viewport. `--output` nennt zuerst einen Prüfungsordner;
WebP und JSON-Geometriebeleg entstehen gemeinsam. Erst nach Sichtprüfung wird
das WebP unter `website/bilder/feature-*.webp` übernommen; der Beleg bleibt intern) ·
`stamp_assets.py` (**läuft als Letztes**, siehe unten)

`site_nav.py` erzeugt die Wege aus einem sprachneutralen Pfadschema und liest
ihre sichtbaren Texte aus dem Sprachkatalog. `make_manual.py` tut das auch für
den ganzen Seiten- und PDF-Rahmen. Eine neue Sprache darf dort keine neue
Tabellenzeile verlangen; ihr Katalog und das Pfadschema müssen genügen.

Die PDF-Kapitelköpfe lesen die tatsächlichen Seiten aus den benannten Zielen
der HTML-Kapitelanker. Beim Stempeln bleibt der ganze PDF-Dokumentkatalog
erhalten, damit auch das Inhaltsverzeichnis diese Ziele weiter erreicht.
PDF-Leser arbeiten dabei aus dem Speicher und halten die Zieldatei nicht offen.

**Bauen und Ausliefern**

Nach einem Python-Wechsel wird `build_slice_core.py` mit dem aktuellen
Interpreter erneut ausgeführt. Eine Erweiterung für eine andere Python-ABI
ist kein Leistungsnachweis; der Vergleich gegen GEOS bleibt in
`tests/test_slice_core.py`. Die Paket-Spec verlangt den passenden nativen Kern.

Die Paketmetadaten führen die bestehende proprietäre Lizenz als
`LicenseRef-Proprietary` und ihre Datei getrennt unter `license-files`.
Dieses Format benötigt mindestens setuptools 77.0.3; der Lizenztext selbst
bleibt die Quelle der Nutzungsbedingungen.

Der Linux-Installer serialisiert gespeicherte Shellwerte mit einfachen
Anführungszeichen und gesonderter Apostrophmaskierung. Sein Desktop-Entry
maskiert zuerst das Exec-Argument, danach dessen Backslashes auf der
Desktop-Stringebene; wörtliche Prozentzeichen werden verdoppelt.

`windows_signed_installer.py` ist der schlüssellose CI-Anschluss zwischen
den beiden lokalen Windows-Signaturen. Er verlangt einen erfolgreichen
`build.yml`-Lauf, manuell auf `main` oder durch den Versions-Tag ausgelöst,
am exakt selben Commit wie sein eigener manueller Workflow auf `main`.
Der gemeinsame Prüfer bindet einen Tag-Lauf zusätzlich an das tatsächliche
GitHub-Tag `v<APP_VERSION>` und dessen aufgelösten Commit. Dazu kommen das
ursprüngliche Signierarchiv und ein unveröffentlichter,
ebenfalls commitgebundener Release-Entwurf mit signierter EXE und Herkunftsakte.
Archiv, Manifest, Zeitstempel und Herausgeber prüfen die gemeinsamen Helfer
aus `sign_release.py`. Nur die EXE wird ersetzt und die Übergabe neu gebunden.
Der feste Inno-7-Compiler baut daraus Setup, SHA-256 und `windows-installer-build.json`
für die lokale abschließende Setupsignatur; der Workflow veröffentlicht nichts.

`bump_version.py` (die zwei Stellen, die die Version tragen, plus drei
abgeleitete) · `make_installer.py` (baut lokal oder schreibt mit
`--signing-handoff` den vollständigen Windows-App-Baum und alle festen
Installer-Eingänge als sortierte relative Pfadliste samt SHA-256) ·
`sign_release.py` (signiert **lokal**, gebaut wird in der CI: `--check` liest
Werkzeuge und Zertifikatsmetadaten ohne Signatur; `--phase application` prüft
die CI-Übergabe und signiert die Anwendung, `--phase installer` prüft den
zugehörigen CI-Installer und signiert ihn samt Zeitstempel. Beide wählen das
Zertifikat eindeutig per Fingerabdruck; `verify_file` und
`verify_signature_identity` sind die gemeinsamen Prüfer für Signierweg,
Installer-CI und Downloadfreigabe. Eine rote Releaseakte sperrt die Ausgabe.
`build_installer` bleibt ein Hilfsaufruf für den CI-Bau, die lokale CLI ruft
ihn nicht. Herkunft und Prüfsummen verbinden beide Schritte; die Anleitung
steht in `Signierung/README.md`) ·
`make_linux_packages.py` (verlangt für AppImage den
bereits geprüften Laufzeitkern in `APPIMAGETOOL_RUNTIME_FILE`) ·
`make_macos_package.py` · `make_download.py` · `sign_version.py` ·
`build_licence_module.py` · `make_licence_keys.py` ·
`asset_rights.py` (prüft `ASSET-RIGHTS.toml` vor Kundenbau und Website-Upload
fail-closed: vollständiges Schema, nur beigefügte Dateinachweise, genau eine
Rechtekette je ausgeliefertem Medium und kein `distribution_blocked`; schreibt
nach PyInstaller einen Bytebeleg ins echte Kundenartefakt, den Windows-,
Linux- und macOS-Paketierer erneut gegen Manifest, Spec, Prüflogik, Quellen
und kopierte Medien prüfen) ·
`make_sbom.py` (CycloneDX-Stückliste aus PyInstallers tatsächlicher Analyse,
dem fertigen Zielpaket einschließlich jeder nativen Datei und der geprüften
Lizenzfreigabeliste, nicht aus `pip freeze`) · `make_licence_notices.py`
(menschenlesbare Beilage aus genau dieser Endartefakt-SBOM, Schema-2-Akte und
fail-closed Releaseprüfung gegen Schema-1-Evidenz) ·
`setup_activation_server.py` (privaten Startwert, Betreiberzugang und
Datenbank vorbereiten) · `deploy_activation_server.py` (diese privaten Werte
und die Endpunkte mit Sicherung ausliefern) · `licence_archive.py` (gemeinsame
Dateisperre für Generator und Support-Oberfläche)

Die interne Support-Oberfläche ist deutschsprachig und verwendet keinen
Kundenkatalog. Anlass und Handlung werden über feste Servercodes geführt;
sichtbare Beschriftungen dienen nicht als Nachschlageschlüssel.

Private Statistik- und Aktivierungsdateien verwenden denselben exklusiven
0600-Schreiber aus `make_stats_access.py`. Der Elternordner wird vor dem
ersten Schreiben auf 0700 geschlossen. SQLite erhält zuerst eine leere
private Datei; eine ausdrücklich erlaubte Geheimnisrotation ersetzt den
Bestand erst nach vollständigem Schreiben. Rechtefehler werden nicht unterdrückt.

Der Aktivierungs-Deploymentweg akzeptiert nur eindeutige Serverpfade mit
Elternordner. Private Daten und Sicherungen müssen neben dem Dokumentenstamm
liegen; ein bloßes `httpdocs`, Traversierung oder eine öffentliche private
Wurzel hält vor der Verbindung an. Jede Datei wird unter einem eindeutigen
Zwischennamen übertragen und vollständig zurückgelesen; erst der Bytevergleich
erlaubt das Umbenennen auf das Ziel. Ein Abbruch nennt den Sicherungsordner
und den Rückweg per FTPS. Der Austausch ist je Datei atomar, nicht über die
gesamte Gruppe von Endpunktdateien. Private Zielordner werden vor dem ersten
Upload auf 0700 gesetzt, vorhandene Zustandsdateien und neue temporäre
Dateien auf 0600; das gilt auch für Sicherungen. Ein Rechtefehler hält an.
Erst der öffentliche Bereitschaftsnachweis und eine authentifizierte reine
Betreiberabfrage mit synthetischer Kennung erlauben die Erfolgsmeldung.

Das Signierwerkzeug prüft auch die abschließende Kopie unter `dist/` gegen
den Hash des signierten Installers. Paket und Prüfsummendatei werden in einem
eigenen temporären Ordner vorbereitet; erst vollständige Kopien ersetzen die
sichtbaren Dateien. Ein später Fehler beim Ersetzen der Prüfsummendatei
entfernt die veraltete Prüfsumme und meldet keinen Erfolg.

`make_download.read_packages` prüft alle Eingänge vor dem Anlegen des
Downloadordners und vor jeder Kopie. Windows-Pakete müssen über die gemeinsame
Funktion `sign_release.verify_file` einschließlich aller Signaturen und des
Zeitstempels bestehen. Fehlendes SignTool oder eine abgewiesene Prüfung hält
Downloads, Seiten und Manifest unverändert; eine Umgehungsoption gibt es nicht.
Der leere Aufruf zum Zurückziehen der Downloads benötigt kein SignTool.

**Website** `upload_website.py` (schließt `website/teile/` als lokalen
Projektquellordner vollständig aus; Bausteindateien werden ausschließlich
lokal ausgetauscht und nie über die Website verteilt) · `make_stats_access.py` (schreibt den
privaten Passwort-Hash ausschließlich nach `appdata/stats-access.php`, nie in
den öffentlichen Website-Baum)

Gesperrt bleibt außerdem jeder Ordner unter `website/`, dessen Name mit einem
Punkt beginnt, sowie `.jsonl` und `.lock`: Dort lag der Zählspeicher älterer
Fassungen, und seine `salt.json` ist an der Endung nicht von `version.json` zu
unterscheiden. `.webserver.json` trägt das FTPS-Passwort und wird mit demselben
exklusiven 0600-Schreiber angelegt wie die übrigen Geheimnisse; ein zu weit
geöffneter oder verknüpfter Bestand hält den Lauf auf POSIX an, statt ihn
stillschweigend zu benutzen.

**Wer in den Website-Baum schreibt, schreibt mit `newline=""`.** Der Baum steht
auf `\n` (`.gitattributes`: `eol=lf`), hochgeladen wird der Arbeitsbaum, und
`Path.write_text` ohne diese Angabe macht unter Windows aus jedem Umbruch ein
`\r\n`. Im Diff sieht man davon nichts — Git glättet beim Einchecken zurück —,
aber der Server bekommt die Seite in einer anderen Zeilenform als ihre
Nachbarn, und der nächste Bytevergleich meldet sie als offen. Betroffen sind
`stamp_assets`, `make_seo`, `make_legal`, `make_changelog`, `make_download`,
`make_manual`, `make_web_images` und `sign_version`;
`tests/test_website.py` hält beides fest, das Werkzeug und den Baum.

**Übersetzen** `build_slice_core.py` (Ebenenschnitt und Konturverkettung der
Schichtanalyse)

**Sonstiges** `setup_comfyui.py` · `speak_chatterbox.py`

## Drei Dinge, die man einmal falsch macht

`check_env --freeze` übernimmt lokale Paketversionen und erhält ausschließlich
die in `PLATFORM_PINS` belegten Abhängigkeiten anderer Zielplattformen.
Ändert sich eine bedingte Kante im Laufzeit-/Bauwerkzeugbaum, werden diese Liste
und die vollständige Windows-/Linux-/macOS-Auflösung zusammen geprüft;
entfernte allgemeine Pakete werden nicht durch einen Freeze wieder aufgenommen.

- **`stamp_assets.py` läuft als Letztes** vor dem Upload. Wer die Reihenfolge
  ändert, macht `test_every_reference_carries_the_stamp_of_the_file_it_points_at`
  beim nächsten Erzeugerlauf rot — und niemand weiß warum.
- **Version vor jedem Bau erhöhen**, nicht danach und ohne zu fragen:
  `bump_version.py` fasst beide Stellen an, und zwar **vor** dem Prüfmodul.
- **Ein Lauf über sechs Sprachen in einem Prozess stirbt** (Segmentation
  fault nach der ersten Sprache). Ein Prozess je Sprache — dieselbe Antwort
  wie bei der Suite. Die Hintergrund-Hülle meldet darüber „exit code 0".
- **Ein Motiv, das in Nutzerverzeichnisse schreibt, bekommt eigene.**
  `make_web_images.py` legt Spulen an, bucht Verbrauch und merkt sich im
  Druckdialog den Slicer — deshalb laufen alle seine Fenstermotive in einem
  Kindprozess je Sprache mit `APPDATA`, `LOCALAPPDATA`, `HOME` und den
  XDG-Variablen auf einem Temp-Ordner, gesetzt in der Umgebung des Kindes
  **vor** seinem ersten Import; eine Umbiegung im laufenden Prozess kommt zu
  spät.
- **Zuschnitte lassen Bedienelemente vollständig im Bild oder vollständig
  draußen.** `make_web_images.work_rect` berücksichtigt die Werkzeugleiste
  und die Ansichtsleiste. Das Lagerbild begrenzt sich auf das scrollbare
  Regal samt Gruppenüberschriften, unterhalb der Such- und Filterzeile.

## Der Sitzungszustand ist ausgenommen

`.claude/.state/` trägt die Messskripte vergangener Durchsichten. Es sind
Wegwerfwerkzeuge — sie haben ihre Zahl geliefert und werden nicht mehr
angefasst. `ruff` lässt sie deshalb aus; ohne diese Ausnahme wäre das Tor rot,
ohne dass sich an der Anwendung etwas geändert hätte.
