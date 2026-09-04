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

Drei Werkzeuge, zwei Wächter, ein Thema: `stamp_assets.py` schreibt die
Inhaltsstempel, `test_every_reference_carries_the_stamp_of_the_file_it_points_at`
liest nach; `make_download.py` trägt die Paketgrößen ein, und
`test_the_technical_requirements_name_the_sizes_the_packages_have` hält sie
gegen `version.json`. Eine getippte Zahl auf der Website ist ein Fehler, der
auf sein Datum wartet.

## Die Familien

**Umgebung und Sitzung**

| Werkzeug | Tut |
|---|---|
| `check_env.py` | Prüft die Umgebung gegen den festgeschriebenen Stand — **und stellt ihn her** |
| `session_board.py` | Wer arbeitet gerade woran (`list` / `claim` / `release`) |
| `gate_lock.py` | Ein Schloss fürs Tor: nur ein Testlauf gleichzeitig auf dieser Maschine |
| `link_memory.py` | Die Erinnerungen ins Repository hängen — einmal je Maschine |
| `check_message.py` | Der `commit-msg`-Hook: Ersatzschreibung statt Umlaut in einer Commit-Meldung |
| `to_main.py` | Der Weg nach `main`: prüfen, was wirklich committet wird |

**Messen und Prüfen** (keines davon ist ein Testlauf)

`run_suite_isolated.py` (je Testdatei ein Prozess) · `run_agent_suite.py`
(39 Referenzanfragen, **kostet Geld**) · `run_model_suite.py` (die Kette über
echte Modelle) · `run_ui_audit.py` (der ganze Bestand durch die laufende
Oberfläche) · `check_local_model.py` (ruft ein lokales Modell die Werkzeuge
wirklich auf?) · `measure_local_model.py` (**wie lange** braucht es dafür — kalt gegen warm getrennt, Median **und** Spanne, die Lage aus `api/ps` in jeder Zeile, und am Ende ein `keep_alive: 0`, weil 15 GB nach dem Messen den Rechner zäh machen) · `check_support.py` (kommt die Rückmeldung an?) ·
`check_activation.py` (ist der öffentliche Aktivierungsdienst bereit?) ·
`licence_admin.py` (private Support-Oberfläche: MoR-Transaktion einem
Vorratsschlüssel zuordnen, Käufer im externen Schlüsselarchiv finden,
Serverzustand lesen und Geräteplätze verwalten) ·
`qt_trace.py` (pytest-Erweiterung für die Jagd auf den Abriss beim Aufräumen) ·
`list_windowed_tests.py` (Fensterdateien aus Pytests aufgelöstem Fixture-Graphen) ·
`affected_tests.py` (welche Testdateien eine Änderung berührt — aus dem
Importgraphen über `app/`, `tools/` und `tests/`, dazu die Baumleser und die
Tests, die eine geänderte Textdatei beim Namen nennen; `--why`, `--split`,
`--run`; die Fenstertrennung kommt von `list_windowed_tests`) ·
`window_bench.py` (Beispiel im **echten** Fenster öffnen und die Wartezeit in
Posten zerlegen — misst, was offscreen unsichtbar ist: VTK und Aktoraufbau)

`window_bench.py` beendet seinen einzigen Lauf in Besitzreihenfolge: erst
Arbeiter und Sitzungsverbindungen lösen, dann über
`Viewport.release_plotter()` den VTK-Plotter bei noch lebendem
Qt-Elternfenster schließen, zuletzt das Fenster. Derselbe terminale Weg liegt
am akzeptierten `MainWindow.closeEvent`; `MainWindow.release()` bleibt für
mehrere Fenster in einem Prozess bewusst ohne Viewport-Abbau.

**Erzeugen** — alles hierunter läuft über den Skill `/erzeugen`

`make_manual.py` · `make_figures.py` (Bildschirmfotos) · `make_web_images.py`
· `make_icon.py` · `make_changelog.py` · `make_seo.py` · `make_legal.py` · `make_examples.py` ·
`make_video.py` · `make_longform_video.py` (deutsche 3-Minuten+-Tutorials:
sichtbares leeres Projekt, echte Dialoge, höchstens einer zugleich,
Katalogbausteine, Text statt Sprecher und selbst erzeugtes Musikbett) ·
`make_showpiece.py` (das Schaustück der Website — ein
Teil, das in einem Bild beantwortet, warum man das Programm haben will;
gebaut über die Operations-API wie von einem Nutzer) ·
`make_gallery.py` (die Galeriebilder des Beweis-Teils: ein Teil groß, im
Viewport mit Licht und Schatten, Karten weggeschnitten — **nicht** über die
flache Projektion, die für Katalogvorschauen reicht und für Qualität nicht) ·
`stamp_assets.py` (**läuft als Letztes**, siehe unten)

`site_nav.py` erzeugt die Wege aus einem sprachneutralen Pfadschema und liest
ihre sichtbaren Texte aus dem Sprachkatalog. `make_manual.py` tut das auch für
den ganzen Seiten- und PDF-Rahmen. Eine neue Sprache darf dort keine neue
Tabellenzeile verlangen; ihr Katalog und das Pfadschema müssen genügen.

**Bauen und Ausliefern**

`bump_version.py` (die zwei Stellen, die die Version tragen, plus drei
abgeleitete) · `make_installer.py` (baut lokal oder schreibt mit
`--signing-handoff` den vollständigen Windows-App-Baum und alle festen
Installer-Eingänge als sortierte relative Pfadliste samt SHA-256) ·
`sign_release.py` (signiert das Windows-Paket **lokal** aus genau dieser
Übergabe: Archiv und jede Prüfsumme prüfen, Anwendung mit dem
Certum-Cloud-Zertifikat über SimplySign signieren, Installer bauen,
Setup-Datei signieren, `.sha256` daneben — hält bei jeder Abweichung an,
bevor ein Zertifikat ins Spiel kommt; die CI signiert Windows nicht) ·
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

**Website** `upload_website.py` (schließt `website/teile/` als lokalen
Projektquellordner vollständig aus; Bausteindateien werden ausschließlich
lokal ausgetauscht und nie über die Website verteilt) · `make_stats_access.py` (schreibt den
privaten Passwort-Hash ausschließlich nach `appdata/stats-access.php`, nie in
den öffentlichen Website-Baum)

**Übersetzen** `build_slice_core.py` (Ebenenschnitt und Konturverkettung der
Schichtanalyse)

**Sonstiges** `setup_comfyui.py` · `speak_chatterbox.py`

## Drei Dinge, die man einmal falsch macht

- **`stamp_assets.py` läuft als Letztes** vor dem Upload. Wer die Reihenfolge
  ändert, macht `test_every_reference_carries_the_stamp_of_the_file_it_points_at`
  beim nächsten Erzeugerlauf rot — und niemand weiß warum.
- **Version vor jedem Bau erhöhen**, nicht danach und ohne zu fragen:
  `bump_version.py` fasst beide Stellen an, und zwar **vor** dem Prüfmodul.
- **Ein Lauf über sechs Sprachen in einem Prozess stirbt** (Segmentation
  fault nach der ersten Sprache). Ein Prozess je Sprache — dieselbe Antwort
  wie bei der Suite. Die Hintergrund-Hülle meldet darüber „exit code 0".

## Der Sitzungszustand ist ausgenommen

`.claude/.state/` trägt die Messskripte vergangener Durchsichten. Es sind
Wegwerfwerkzeuge — sie haben ihre Zahl geliefert und werden nicht mehr
angefasst. `ruff` lässt sie deshalb aus; ohne diese Ausnahme wäre das Tor rot,
ohne dass sich an der Anwendung etwas geändert hätte.
