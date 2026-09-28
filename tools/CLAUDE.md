# `tools/` — Hilfsprogramme

Nicht Teil der Anwendung: **Was hier liegt, reist nicht im gebauten Paket
mit** — was der Nutzer aus der laufenden Anwendung heraus tun können soll,
steht im Kern (etwa `app/core/backends/comfy_setup.py`). Einzuhalten sind
`.claude/rules/auslieferung.md` (lädt für `tools/**/*.py`) und `AGENTS.md`;
die Sprachregel gilt wie in `app/`, denn `tools/` baut das Paket. Aufrufe und
Reihenfolge des Erzeugens stehen im Skill `/erzeugen`, die Testbefehle in
`CLAUDE.md` („Befehle“) und `/pruefen`. Das Warum und die ausführlichen
Fassungen: `konzepte/begruendungen/karte-tools.md`.

## Zwei Grundsätze

> **Was erzeugt wird, wird nicht getippt — und was getippt bleibt, bekommt
> einen Wächter.**

`stamp_assets.py` schreibt die Inhaltsstempel,
`test_every_reference_carries_the_stamp_of_the_file_it_points_at` liest nach;
`make_download.py` trägt die Paketgrößen ein,
`test_the_technical_requirements_name_the_sizes_the_packages_have` hält sie
gegen `version.json`; `sync_agents.py` erzeugt die Codex-Seite,
`test_agent_mirror.py` fährt sein `--check`.

**Ein Suchwerkzeug prüft sich zuerst an einem Fall mit bekanntem Ausgang**
(`tests/test_twin_scan.py`, `tests/test_docs_scan.py`): Wer zu wenig findet,
schweigt, und Schweigen sieht aus wie ein sauberes Ergebnis.

## Umgebung, Git, Erinnerungen

| Werkzeug | Tut |
|---|---|
| `check_env.py` | Prüft die Umgebung gegen den festgeschriebenen Stand und stellt ihn her; `--freeze` schreibt `constraints.txt` |
| `sync_agents.py` | Codex-Agenten und Skills aus `.claude/agents/` und `.claude/skills/`; prüft alle Eingaben vor dem Schreiben, übersetzt Skillaufrufe und `disable-model-invocation`, meldet Dateien ohne Quelle, statt sie zu löschen. Ein neues Frontmatter-Feld braucht eine bewusste Übersetzung |
| `link_memory.py` | Hängt die Erinnerungen einmal je Maschine ein, fasst `MEMORY.md` nie an; prüft vor dem Entfernen des lokalen Bestands jede Datei am Ziel bytegenau |
| `memory_index.py` | Schreibt genau eine Zeile in `MEMORY.md`: Sperrdatei daneben, Index **unter** der Sperre gelesen, vor dem Schreiben nachgezählt |
| `check_message.py` | `commit-msg`-Hook: Ersatzschreibung statt Umlaut |
| `check_new_texts.py` | `pre-commit`-Hook: Stehen die **neuen** `tr()`-Texte des Commits in jedem Katalog? Liest Quelltext und Kataloge, nie die pytest-Ausgabe |
| `check_part_ranges.py` | Bereichsnachweis der Bausteine (§24.3): je Baustein ein Prozess, schreibt `app/core/knowledge/data/part_ranges.toml`; `--check` vergleicht nur |

## Prüfen und messen — keines davon ist ein Testlauf

| Werkzeug | Tut |
|---|---|
| `affected_tests.py` | Betroffene Testdateien aus dem Importgraphen über `app/`, `tools/`, `tests/` (gelöschte Module bleiben Knoten), dazu Tests, die eine geänderte Textdatei nennen. `--why` nennt alle; `--split`/`--run` fahren ohne Fenster, Fenstertests nur mit `--release`, Leistung nie |
| `list_windowed_tests.py` | Dateien mit Fenstertests aus dem aufgelösten Fixture-Graphen oder dem Marker `windowed` (Fenster außerhalb von `qt_app`, etwa im Kindprozess); als Laufplugin wählt `--window-group` je Test |
| `run_suite_isolated.py` | Je Testdatei ein Prozess; Fenster nur mit `--release`, Leistung getrennt. CI: `--release --ci-group contracts\|windowed`, `--plan-only` plant ohne Lauf. Fehler, leere Auswahl und fehlende Berichte bleiben rot |
| `ci_shards.py` | Die Verteilung für Läufer und `tests/conftest.py` (`--ci-shard I/N`): je Datei, längste zuerst in die leichteste Gruppe; als Befehl schreibt es eine Laufzeittabelle (`core`/`windows`) aus JUnit-Berichten neu |
| `qt_trace.py` | pytest-Erweiterung für die Jagd auf den Absturz beim Aufräumen |
| `run_agent_suite.py` | 39 Referenzanfragen an den Agenten — **kostet Geld**, das Ergebnis ist eine Quote |
| `run_model_suite.py` · `run_ui_audit.py` | Die Kette über einen Ordner echter Modelle · der ganze Bestand durch die laufende Oberfläche |
| `check_local_model.py` · `measure_local_model.py` | Ruft ein lokales Modell die Werkzeuge wirklich auf? · Wie lange (kalt/warm getrennt, Median und Spanne, am Ende `keep_alive: 0`); `--count-tokens` zählt genau einen Auftrag ohne Geschwindigkeit |
| `window_bench.py` · `window_memory.py` | Beispiel im **echten** Fenster, Wartezeit in Posten (`--drag-frames`, `--shot`) · was Fenster- und Sprachwechsel liegen lassen: Steigung des Arbeitssatzes über die **zweite** Hälfte der Runden |
| `count_new_windows.py` | Welche Fenster während eines Befehls aufgehen (`EnumWindows`); Exit 1 bei einem neuen Konsolenfenster |
| `twin_scan.py` · `docs_scan.py` | Zwillinge (die Klasse eines Funds entscheidet der Code, vier Klassen in `konzepte/konzept-zwillinge-2026-09.md`) · Ladelast, doppelte Absätze, tote Verweise und leere `paths:` der Unterlagen. Beide **nicht** im Tor — dort halten `test_shared_constants.py` und `test_directory_docs.py` |
| `check_support.py` · `check_activation.py` | Kommt die Rückmeldung an? · Ist der Aktivierungsdienst über HTTPS bereit? |
| `licence_admin.py` | Private Support-Oberfläche: Käufe Vorratsschlüsseln zuordnen, Käufer finden, Geräteplätze verwalten. Deutsch und ohne Kundenkatalog; Anlass und Handlung über feste Servercodes, nie über Beschriftungen |

## Erzeugen

| Werkzeug | Tut |
|---|---|
| `make_manual.py` · `site_nav.py` | Handbuch als Seite und PDF · Wege aus einem sprachneutralen Pfadschema. Sichtbare Texte und PDF-Rahmen kommen aus dem Katalog — eine neue Sprache verlangt keine Tabellenzeile |
| `make_figures.py` · `make_web_images.py` | Handbuchbilder · Website-Bilder aus dem maximierten Hauptfenster |
| `make_guides.py` | Die Bildanleitungen des Handbuchs: je Anleitung eine Geschichte durch die echte Oberfläche, Rahmen, Nummern und Pfeile an den Zielen aus `app/ui/guide_targets.py`, WebP je Schritt, ein Kindprozess je Sprache. Menüeinträge mit aufgeklapptem Menü, modale Dialoge wie der Bausteinkatalog über `make_web_images.while_open`. Läuft vor `make_manual.py`; ein fehlendes Ziel hält den Lauf an |
| `make_feature_images.py` | Textfreie Funktionsbilder aus registrierten Operationen: ein Motiv je nativem Prozess, eigene Konfigurationsverzeichnisse, der pygfx-Renderer des Viewports. `--output` nennt einen Prüfungsordner, WebP und JSON-Geometriebeleg entstehen gemeinsam; erst nach Sichtprüfung nach `website/bilder/feature-*.webp`, der Beleg bleibt intern |
| `make_showpiece.py` · `make_gallery.py` | Das Schaustück, über die Operations-API gebaut wie von einem Nutzer · Galeriebilder im Viewport mit Licht und Schatten, nie über die flache Projektion der Katalogvorschau |
| `make_video.py` · `speak_chatterbox.py` | Videos aus der laufenden Anwendung · Sprachsynthese mit `voice-reference.wav` (intern) |
| `make_longform_video.py` | Lange Tutorials, höchstens ein Dialog zugleich; `--language en` nimmt `longform_video_en.json`; `.timeline.json` neben dem MP4 trägt die Zeiten der YouTube-Kapitel |
| `make_workshop_videos.py` · `make_workshop_shorts.py` | STL-Tutorials über echte Dialoge, ein Prozess je Thema und Sprache (`--capture-only`, `--encode-only`) · Hochformat samt Titelbild aus `short_shots.json` neben dem Film |
| `make_icon.py` · `make_changelog.py` · `make_seo.py` · `make_legal.py` · `make_examples.py` | Symbol · Changelog-Seiten · SEO-Dateien · Rechtstexte und `packaging/eula.txt` · Beispielprojekte |
| `stamp_assets.py` | Inhaltsstempel — läuft als Letztes |

## Bauen, signieren, ausliefern

| Werkzeug | Tut |
|---|---|
| `bump_version.py` | Die zwei Stellen der Version, dazu drei abgeleitete |
| `build_slice_core.py` | Übersetzt Ebenenschnitt und Konturverkettung; nach jedem Python-Wechsel mit dem aktuellen Interpreter neu fahren |
| `build_licence_module.py` · `make_licence_keys.py` | Prüfmodul und Lizenzmanifest nach `packaging/build/` · Kaufcodes |
| `make_installer.py` | Windows-Installer lokal, oder `--signing-handoff`: App-Baum und Installer-Eingänge als sortierte Pfadliste mit SHA-256 |
| `windows_signed_installer.py` · `sign_release.py` | Schlüsselloser CI-Anschluss zwischen den zwei lokalen Signaturen · signiert **lokal** (`--check`, `--phase application`, `--phase installer`), Zertifikat per Fingerabdruck; eine rote Releaseakte sperrt die Ausgabe. Ablauf: `packaging/CLAUDE.md`, `Signierung/README.md` |
| `make_linux_packages.py` · `make_macos_package.py` | AppImage, Flatpak und Archiv · das `.pkg`; beide schreiben ihre Vorlagen in `packaging/` |
| `make_download.py` · `sign_version.py` | Download-Kasten und Versionsliste aus `DELIVERED` · unterschreibt `website/version.json` |
| `asset_rights.py` | Prüft `ASSET-RIGHTS.toml` fail-closed vor Kundenbau und Upload; schreibt den Bytebeleg ins Artefakt, den jeder Paketierer erneut prüft |
| `make_sbom.py` · `make_licence_notices.py` | Stückliste aus PyInstallers Analyse und dem fertigen Paket, nicht aus `pip freeze` · Lizenzbeilage aus genau dieser SBOM, `--release-check` fail-closed |
| `check_frozen_helper.py` | Rauchtest im Paketjob direkt nach dem Bauen: startet den Hilfsprozess des Kerns aus dem gebauten Paket, rechnet eine Boolesche bitgleich nach, beendet ihn hart und sanft und verlangt danach weder Prozess noch Temp-Ordner; schreibt nichts ins Paket |
| `setup_activation_server.py` · `deploy_activation_server.py` · `licence_archive.py` | Startwert, Betreiberzugang und Datenbank vorbereiten · mit Sicherung ausliefern · Dateisperre und Satzformat des Lizenzarchivs |
| `upload_website.py` · `make_stats_access.py` | Website hochladen · Zugang zur Statistik nach `appdata/stats-access.php`, nie in den öffentlichen Baum |
| `setup_comfyui.py` · `start-solidon3d.cmd` | ComfyUI für Solidon einrichten · Start per Doppelklick aus dem Arbeitsbaum |

## Fallen, die man einmal falsch macht

- **`stamp_assets.py` läuft als Letztes** vor dem Upload, sonst wird
  `test_every_reference_carries_the_stamp_of_the_file_it_points_at` beim
  nächsten Erzeugerlauf rot — und niemand weiß warum.
- **Sechs Sprachen in einem Prozess sterben** nach der ersten; ein Prozess je
  Sprache. Die Hintergrund-Hülle meldet darüber „exit code 0“.
- **Ein Motiv, das in Nutzerverzeichnisse schreibt, bekommt eigene**:
  `make_web_images.py` setzt `APPDATA`, `LOCALAPPDATA`, `HOME` und XDG im
  Kindprozess **vor** dessen erstem Import — im laufenden Prozess zu spät.
- **Zuschnitte lassen Bedienelemente ganz im Bild oder ganz draußen**
  (`make_web_images.work_rect`).
- **Aufnahmen reichen die Merkmalskennung als Argument durch**, keine
  Attribute an `Session`; Kreisflug-Loops warten auf den Arbeiter der
  Druckanalyse; eine verworfene Aufnahme räumt `Session.forget_changes()`.
  Ein über `exec()` geöffneter Kundendialog behält Modalität und Fensterflags.
- **`window_bench.py` baut in Besitzreihenfolge ab**: Arbeiter und
  Verbindungen, dann `Viewport.release_renderer()` bei lebendem Elternfenster,
  zuletzt das Fenster (wie `MainWindow.closeEvent`; `MainWindow.release()`
  baut den Viewport bewusst nicht ab).
- **Wer in den Website-Baum schreibt, schreibt mit `newline=""`** — sonst
  bekommt der Server `\r\n`, und Git verbirgt es. Betroffen: `stamp_assets`,
  `make_seo`, `make_legal`, `make_changelog`, `make_download`, `make_manual`,
  `make_web_images`, `sign_version`; `tests/test_website.py` hält beides.
- **Ein Freeze nimmt auf, was in der `.venv` liegt** (`pip install -c`
  entfernt nichts): `check_env` meldet `leftovers`, jedes wird vorher entfernt
  oder bewusst aufgenommen. Eine geänderte bedingte Kante prüft
  `PLATFORM_PINS` und die Auflösung aller drei Plattformen zusammen.
- **Erst prüfen, dann veröffentlichen**: `make_download.read_packages` prüft
  jeden Eingang vor dem Anlegen des Ordners, Windows-Pakete über
  `sign_release.verify_file` — ohne SignTool keine Downloads, keine
  Umgehungsoption. `sign_release.py` ersetzt Paket und Prüfsumme unter `dist/`
  erst aus vollständigen, geprüften Kopien.
- **Geheimnisse schreibt der 0600-Schreiber aus `make_stats_access.py`**
  (Ordner 0700, Rechtefehler halten an). `deploy_activation_server.py`
  überträgt je Datei unter Zwischennamen und benennt erst nach dem
  Bytevergleich um; Erfolg erst nach Bereitschaftsnachweis und
  Betreiberabfrage.
- **`upload_website.py` lässt aus**: `website/teile/` (Projektquellen bleiben
  lokal), Punktordner, `.jsonl` und `.lock` (der alte Zählspeicher).
  `.webserver.json` trägt das FTPS-Passwort; zu weit geöffnet hält der Lauf
  auf POSIX an.
- **Kleinigkeiten mit Folgen**: `LicenseRef-Proprietary` mit `license-files`
  braucht setuptools ≥ 77.0.3; der Linux-Installer maskiert im Desktop-Entry
  erst das Exec-Argument, dann die Backslashes; PDF-Kapitelköpfe lesen ihre
  Seiten aus den benannten Zielen der HTML-Anker, das Stempeln behält den
  Dokumentkatalog.
