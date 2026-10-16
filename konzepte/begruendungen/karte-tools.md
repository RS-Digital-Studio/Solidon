# Begründungen zu `tools/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Werkzeuge, Einstiege
> und Fallen verdichtet wurde. Die Karte steht dort; hier stehen die
> ausführlichen Beschreibungen, das Warum und die Messwerte und Anlässe ihres
> Tages — wörtlich, gegliedert nach den Überschriften der Karte. *Früher unter …*
> nennt die Stelle der alten Karte; *HEAD-Fassung* heißt: aus dem letzten
> Commit, weil die ungesicherte Zwischenfassung den Absatz gekürzt oder
> gestrichen hatte.

## Zwei Grundsätze

*HEAD-Fassung, früher unter „Das Prinzip, das die meisten dieser Werkzeuge erklärt“.*

Vier Werkzeuge, drei Wächter, ein Thema: `stamp_assets.py` schreibt die
Inhaltsstempel, `test_every_reference_carries_the_stamp_of_the_file_it_points_at`
liest nach; `make_download.py` trägt die Paketgrößen ein, und
`test_the_technical_requirements_name_the_sizes_the_packages_have` hält sie
gegen `version.json`; `sync_agents.py` erzeugt die Codex-Agentenprofile und
Skills aus den Claude-Quelldateien, und `test_agent_mirror.py` fährt sein `--check`. Eine
getippte Zahl auf der Website ist ein Fehler, der auf sein Datum wartet.

*Früher unter „Das Prinzip, das die meisten dieser Werkzeuge erklärt“.*

**Und was hier sucht, sucht zuerst einen Fall, dessen Ausgang bekannt ist.**
`twin_scan.py` hat seinen Selbsttest (`tests/test_twin_scan.py`), und der hat
sich am ersten Tag bezahlt: Die Mindestgröße stand auf vier Anweisungen, und
der Zwilling, für den das Werkzeug gebaut wurde, besteht aus drei. Ein
Suchwerkzeug, das zu wenig findet, **schweigt** — und Schweigen sieht aus wie
ein sauberes Ergebnis.

## Umgebung, Git, Erinnerungen

*HEAD-Fassung, früher unter „Das Prinzip, das die meisten dieser Werkzeuge erklärt“.*

`sync_agents.py` liest ausschließlich `.claude/agents/` und `.claude/skills/`
als Quellen. Es prüft alle Eingaben vor dem Schreiben, übersetzt Skillaufrufe
und erzeugt Codex-Aufrufregeln aus `disable-model-invocation`. Referenzen
reisen mit; Zeilenenden von Git gelten nicht als Drift. Dateien ohne Quelle
werden gemeldet und nicht gelöscht. Ein neues Agenten-Frontmatter-Feld braucht eine
bewusste Übersetzung, damit eine Claude-Regel nicht unbemerkt bei Codex fehlt.

*HEAD-Fassung, früher unter „Die Familien“.*

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

*Früher unter „Die Familien“.*

`link_memory.py` reserviert bei Konflikten
freie Sicherungsnamen exklusiv; vor dem Entfernen des lokalen Bestands wird
jede Datei am tatsächlich gewählten Ziel bytegenau geprüft.

## Prüfen und messen — keines davon ist ein Testlauf

### Funktionsdurchgang: Ablauf, Messung und Urteil

Der einzige Einstieg am Fenster ist `file_acceptance.py`; `function_bench`
stellt den Fall zusammen, `function_machine`/`function_walk` führen ihn,
`function_setup`/`function_start` bereiten ihn vor (`place_window` belässt
maximierte Clientmaße ohne Ziel- oder Größenwechsel), `function_protocol` schreibt
das Protokoll und `function_language` prüft die Sprache. `function_gestures`
fährt Zeigen und Ziehen, `function_switch` den Projektwechsel. Die Schritte
gehen über echte Eingabeereignisse und `guide_targets.next_click`; die
Ereignisschleife läuft dabei weiter. `until_step` wartet auf eine Bedingung,
`still_step` auf Stillstand vor dem Messen; `settle_ms` bestimmt die zusätzliche
Beruhigungszeit. Bleibt eine Fläche unruhig, werden ihre Größen ausdrücklich
ungemessen protokolliert, auch eine leere Rollleistenliste ist dann kein Beleg.

`function_surface` bestimmt die Fläche der Zeile, ihren Zustand und Wartehinweis,
Sperrgründe (`grey_reason`) sowie Befunde (`shown_findings`, `require_findings`)
und Absagen (`fault_messages`). Ein fremdes modales Frage- oder Fehlerfenster
wird nicht als die Fläche der Zeile vermessen. `op_in_view` liest
`FeaturePanel.measure_op`: Gleichnamige Maßfelder allein beweisen nicht, dass
die richtige Handlung im Bild steht. `function_scenes.row_scenes` liefert die
Startszenen eines Falls einschließlich Fehlfall; zugesagte Befunde müssen vor
der Handlung angekommen sein. Fehlfallszene und Hauptszene dürfen keine
widersprüchlichen Vorbedingungen einführen.

`function_capture.error_proposal` erhebt das Fehlerangebot. Die Herkunft
entscheidet, welche modalen Fragen zulässig sind (`ALLOWED_CALLERS/CLASSES`,
`ASK_CALLERS/HOSTS`), auch bei `ctx.ask`; eine passende Zeichenkette reicht
nicht. `names_a_way_out(reason, menus, buttons, *, phrases=(), fields=())` und
`way_out(window, reason, widget=None)` prüfen Auswege. `surface_field_titles`
nimmt nur offene Felder auf derselben Fläche, nicht die einer anderen Karte
oder des gesamten Hauptfensters. Ein graues Feld ist kein Ausweg.
`function_tooltips.reason_pictures` zeigt im Fehlfall die Kurzhilfe jedes
grauen Ziels wie beim Überfahren und nimmt sie als eigenes Bild auf
(`04-fehlfall-grund-<n>.png`): Ein Urteil über einen Sperrgrund stützt sich auf
den angezeigten Satz, nicht auf das Protokoll.

Lizenzläufe tragen `state` mit `angeboten`, `grau` oder `fehlt`; `reason`
stammt aus `grey_reason`, zuerst aus der Kurzhilfe, dann aus der zugänglichen
Beschreibung. Die Startauswahl und bei angebotenem Ziel der vollständige
Handlungsweg müssen erfolgreich durchgelaufen sein. Scheitert ein Schritt,
steht der Grund unter
`unmeasured.licence_runs.<zustand>`; ein beobachtetes Angebot, vorhandener Name,
Nullwert oder beschädigter Eintrag ist keine erfolgreiche Lizenzmessung.
`judge_licence` verwendet für sein Urteil und den Vergleich nur gültige
Messwerte, einschließlich booleschem `writes`, bekanntem Zustand und Textgrund.

`function_guard.BENCH_MODULES` umfasst auch `function_surface`,
`function_gestures`, `function_switch` und `function_revision`; `WindowFlow` in `file_acceptance`
wird eigens geprüft. `FORBIDDEN_CALLS` verbietet Umwege über Wertsetzer,
Signal-/Aktionsaufrufe, Kernzugriffe, Ereignismethoden und private fremde Namen,
auch als importierte Namen oder über `getattr`, `invokeMethod` und Variablen.
Sitzungs- und Methodenaliase werden in ihrer lexikalischen Bindung verfolgt:
äußere Namen bleiben innen sichtbar, Parameter und Neubelegungen verdecken sie.
Schon das Abgreifen einer gebundenen `session.apply` ist ein Umweg. Eigene
dynamische Phasen und reines Lesen bleiben zulässig. Die Grenze des Wächters
bleibt die Namensanalyse; sie beweist keine Laufzeittypen.

`function_scan.message_builders(sources)` erhebt Meldungsbauer samt transitiven
Unterklassen und festen oder weitergereichten Zielen. `raw_window_names` nimmt
diese erhobene Menge an, statt eine zweite Klassenliste zu führen.
`function_checks` hält Schema und Schwellen, `function_points` und
`function_judges` urteilen; `function_samples` liefert Gegenproben,
`function_report` Funde und Abhakliste; die Übereinstimmung der Urteile rechnet
`function_agreement` je Paket zur Auskunft und bindend über die Runde (alle
Pakete mit demselben Laufordner), Zellen ohne Gegenurteil weist es aus.
`function_verdict_rules` hält, was ein Urteil zur Zeit seiner Runde gegen
Funddatei und Vorhersage einhalten muss: *gut nach Fix* genau dort, wo ein
behobener Fund an der Zelle steht (ein Prüfpunkt umfasst seine Kriterien), und
V4 nur mit vor dem Klick gebundener Vorhersage; dazu, dass die Funddatei
nachgezogen ist (`stale_findings`, FD-153: kein offener Fund nennt einen
Commit im Laufkopf, außer mit „Rest:“). `report` prüft das, der Wächter über
die versionierten Urteile nur ihre Form. `function_promises`
findet die Fundstellen von Prüfpunkt 11 außerhalb des Registers über die
Zeilenspezifikation (`manual`, `website`, die Übersetzungen an derselben Stelle
der Gliederung) und liest Seiten samt Bildtexten und Titeln.

#### Messflächen und nachträgliche Änderung

`function_walk` hält die Fläche vor einer wirksamen Befundhandlung fest und
führt anschließend den echten Klick aus. Öffnet dieser ein Fenster, bleibt
der Vorzustand als `surfaces/*-vorher.json` erhalten; der Hauptfall misst das
geöffnete Fenster. `function_report` und `function_summary` reichen beide
Flächen getrennt durch; `file_acceptance` zählt sie als Funktionsflächen.
Ihre Texte und Feldzahlen werden nicht zu einer künstlichen Fläche vereinigt.
`function_surface.open_dialog` erfasst auch eigene sichtbare nichtmodale
Fenster; mehrere passende Fenster sind keine Erlaubnis zu raten.

`function_bench.surface_signature` hält die lebende Qt-Hülle im
Vergleichstupel. Kurzlebige Python-Hüllen eines C++-erzeugten Dateidialogs
sind keine neuen Flächen; ihre Python-Identitätszahl trägt den Vergleich
nicht. Tatsächliche Geometrie- oder Flächenwechsel starten die bestehende
Ruhezeit erneut, ohne deren Zeitbudget zu ändern.

`function_surface.surface_parts` bindet die eigene offene Merkmalszeile und
ihren sichtbaren gemeinsamen Abschluss zusammen. Eine fremde Zeile oder ein
verdeckter Abschluss zählt nicht mit. Eine vollständige eigene Maßgruppe
belegt ihre Handlung über `FeaturePanel.measure_op`; bloß gleichnamige
Felder genügen nicht. Gemessen und beruhigt wird dieselbe Teilmenge.
Ein Klapppfeil erhält seinen Namen nur durch die tatsächlich sichtbare
zugehörige Beschriftung, nicht durch irgendeinen Text daneben.

`function_capture` liest Texte nach dem Textformat ihres Trägers: Rich Text
über `QTextDocument`, Kürzelmarken (`&`) nur an Trägern, die sie haben, und
`&&` bleibt ein Zeichen (FD-76). Für nativen Kontrast liest es die wirklichen
Fensterpixel.
Ein leeres Bild oder fehlende Bildpunkte bleiben ungemessen; eine gute Palette
ersetzt sie nicht. Fehlerbild und Fehlerangebot gehören zum selben offenen
Zustand, vor Escape. Sperr- und Grenzfälle erhalten nur aus ausdrücklich
erhobenen Auswegen ein positives Urteil, nicht aus einem allgemeinen
Meldungskennzeichen. `field_values` liest markierte `ValueField`-Träger über
deren öffentlichen Wert und Auswahlfelder über ihre tatsächlichen Daten.

Beim Hauptknopf liest die Schriftmessung die aktuelle zustandsabhängige
Qt-Beschriftung. Nur eindeutig voll gedeckte Textpixel belegen eine Farbe;
Symbolpixel zählen nicht mit. Fehlende oder mehrdeutige Schriftpixel bleiben
ungemessen. Der Hintergrund stammt weiterhin aus dem wirklichen Fensterbild.
`fonts.primary` hält die öffentliche Hauptknopfrolle fest; `family` und
`base_family` nennen die tatsächlich aufgelösten Schriftfamilien. Das Schema
prüft vorhandene Rollen als bool und Familien als str. Die halbfette
Grundschrift ist nur mit belegter Hauptknopfrolle und passender Anwendungsfamilie
erlaubt; fremde Größe oder Familie bleiben Befunde. Alte Protokolle ohne die
optionalen Schlüssel bleiben lesbar und erhalten keine erfundene Primärrolle.

`function_revision.RevisionPhase` trägt die abgeschlossene Verlaufsphase von
`FunctionFlow`; die Rückrichtung bleibt ein Typimport. Beide Bedienwege,
Kontextmenü und Doppelklick, erfassen `revise.typed_values` und
`revise.params_after`. Prüfpunkt 12 verlangt eine wirkliche Eingabe am
richtigen Feld, den neuen Wert nach der Auswertung und gleich lange Historie.
Alte Protokolle ohne diese Felder bleiben lesbar, aber ohne diesen Nachweis.
`preview_steps` nimmt die auslösenden Schritte mit: Ausgangsstand vor Öffnen
oder Eingabe, danach die sofortige oder spätere Vorschau desselben Auftrags.
Ein künstliches Warten ersetzt keinen Auftragsbezug.

`function_language` räumt eigene offene Fenster mit wirklichen Escape-
Ereignissen über den Automaten, bevor es das nächste Sprachprojekt lädt.
Der begrenzte Rückweg verwendet `MOST_UNSTICKS`; ein verbleibendes Fenster
meldet `bench.surface_cleanup_failed` und hält den Wechsel an. Direkter
Dialogabschluss und nachträgliches Herausfiltern sind kein Bediennachweis.
`function_machine` erhält Bereitschaftsfehler, Timeout und Fund und plant
den begrenzten normalen Abbau weiter, auch aus verschachtelten modalen
Handlungen. Ein Prozessausgang allein ersetzt kein Urteil über den Fall.

`file_acceptance.run` beendet bei Timeout oder Ausnahme seine ganze gestartete
Prozessgruppe über `terminate_process_tree`, damit hinter dem Launcher kein
Interpreter weiterläuft.

`function_walk.QtPorts.press` stellt Radereignisse über `QTest.wheelEvent` am Fenster
zu. Qt übernimmt Kindannahme und Elternweiterleitung; eine Annahme beendet
die Weiterleitung, auch bei verschachtelten Rollbereichen. Richtungen,
Modifier und lokale/globale Koordinaten bleiben Teil der Eingabe.
Die API ist ab [Qt 6.8](https://doc.qt.io/qt-6/qtest.html#wheelEvent) verfügbar
und Voraussetzung des internen Prüfwerkzeugs. Die gepinnte Prüfumgebung
steht in `constraints.txt`. Fehlt die API, nennt der Fehler
`tools/check_env.py` mit `--install` und `constraints.txt` als Rückweg.
Das allgemeine Anwendungsminimum bleibt davon unberührt.
`function_guard.ALLOWED_CALLS` erlaubt dafür genau `QTest.wheelEvent` als
öffentliche Zustellschnittstelle; die API-Vorbedingung wird statisch geprüft.

Einen Doppelklick gibt `press` über `tools/qt_clicks.double_click`: Klick,
Doppelklick, Loslassen wie beim Kunden, das Loslassen am gedrückten Widget
oder, wenn der Doppelklick es abgebaut hat, am Widget unter dem Zeiger.
`QTest.mouseDClick` allein ließ die Taste bis zum nächsten Klick gedrückt
(FD-83, FD-142). Tests und Videowerkzeuge nehmen denselben Helfer; er ist
kein Prüfstandsmodul, damit sein Nutzer nicht unter `function_guard` fällt.
`tests/conftest.py` lässt keinen `qt_app`-Fall mit gedrückter Taste enden.
`place_window` belässt maximierte Clientmaße ohne Ziel- und Größenwechsel.
Die allgemeine Ereignissperre gilt weiter: direkte Widget-Handler,
Handleraliase und dynamische `getattr`-Umwege bleiben unzulässig.
Ein Radschritt, der in derselben Richtung weiterrückte, zählt nicht als
Wegklick; nach `function_walk.STILL_ROLLS` Radschritten ohne Annäherung hält
der Weg an (FD-131). Direktes `click_button` bleibt synchron mit letztem Guard.

Vor einem Export für die ganze Szene stellt der Prüfstand eine leere Auswahl
über den Kundenweg her; `function_surface.require_full_export_scope` liest
den tatsächlichen Exportumfang öffentlich zurück. Gleiche Objektkennungen
nach einem Projektwechsel belegen keine absichtlich ausgewählte Teilmenge.
Eine erwartete Rückfrage zum Netzkörper
setzt voraus, dass dieser Körper im Exportumfang liegt.

Prüfpunkt 15 setzt die Einfügemarke vor den letzten Schritt der Startszene.
Fehlt dort ein Wegziel aus der Szene (`function_surface.SCENE_KINDS`: Baum,
Bild, Befund), wendet der Fall die Zeile einmal an und setzt die Marke vor
diesen Schritt; ein fehlendes Merkmal am früheren Stand ist kein Fund. Die
Antwort wird gegen das Ergebnis am Stand davor gelesen, und eine Meldung aus
dem Arbeiter schließt der Fall danach selbst.


*HEAD-Fassung, früher unter „Die Familien“.*

Die CI benutzt `run_suite_isolated.py --release --ci-group contracts|windowed|rendering`;
`rendering` sammelt die Rendererfälle ohne Fenster außerhalb der zwei
Vertragsdateien und läuft unter Linux und auf beiden Macs (RM-344). Mehrere
`--ci-group` teilen sich eine Sammlung und schreiben je Gruppe in einen
Unterordner von `--report-dir`; eine zweite Sammlung kostete je Läufer 10 bis
25 Sekunden.
Der Läufer sammelt die ausführbaren Fensterfälle, verteilt sie mit
`tests/data/ci_window_durations.json` deterministisch und schreibt je Datei
Prozessprotokoll und JUnit sowie `summary.json`/`summary.md` für die Gruppe.
Die Ausgabe jedes Prüfprozesses geht zugleich in die Konsole, unter GitHub je
Datei als einklappbare Gruppe und zwischen angehaltenen Workflow-Befehlen
(`::stop-commands::`), damit ein Test keine Anmerkung vortäuscht; eine rote
Datei bekommt eine echte Anmerkung am Lauf, und `summary.md` steht
zusätzlich im Schrittbericht. Ohne das stand im CI-Protokoll bei einem
Fehler nur der Dateiname. Hält ein entkommener Nachfahre die Leitung offen,
endet der Bericht nach `OUTPUT_DRAIN_SECONDS`, und der Kopierfaden leert die
Leitung weiter, ohne noch zu schreiben.
`--plan-only` sammelt und plant ohne Ausführung, auch ohne `--release`.
Die zwei plattformübergreifenden Vertragsdateien sind aus den Windows-Shards
ausgeschlossen. Neue Dateien bekommen ein Ersatzgewicht und bleiben in der
Menge. Fehler, leere Auswahl und fehlende oder widersprüchliche Berichte
bleiben rot. Der Vertrag steht in `konzepte/konzept-ci-testlaufzeiten-2026-09.md`.

`ci_shards.py` ist die Verteilung, die beide Wege teilen: je Datei, längste
zuerst in die leichteste Gruppe, Gleichstand über Pfad und Gruppennummer. Der
Läufer nimmt sie für die Fenstergruppen, `tests/conftest.py` für
`--ci-shard I/N`, mit dem jeder Kernjob seinen Teil der Suite fährt — nach der
Markerwahl, also verteilt über genau die Menge dieses Laufs, unter xdist in
jedem Worker gleich. Als Befehl schreibt es eine der zwei Laufzeittabellen aus
JUnit-Berichten neu (`core` oder `windows`); die Tabellen verteilen nur.

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
die Vollständigkeit der Karten; die Durchsichten liegen als `durchsicht-unterlagen-*.md` in `konzepte/`) ·
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

Der Importgraph von `affected_tests.py` behält auch nicht mehr vorhandene
Importziele als Knoten, damit gelöschte Module ihre direkten und indirekten
Testabhängigkeiten behalten. Die geänderten Dateien liest es aus Git
NUL-getrennt, damit Leerraum und Sonderzeichen nicht gequotet ankommen, und
ohne Umbenennungserkennung, damit eine Umbenennung am alten und am neuen Ort
zählt.

`window_memory.py` stellt die andere Frage am selben Fenster: **was ein
Fenster- und ein Sprachwechsel liegen lassen.** Es baut nacheinander Fenster
auf und ab und wechselt danach über `app.ui.app.rebuild_for_language` die
Sprache, misst je Runde den Arbeitssatz und meldet die **Steigung über die
zweite Hälfte** — die erste trägt den einmaligen Aufbau, und wer sie
mitrechnet, findet ein Leck, das keines ist. Es teilt Messprofil,
Arbeitssatzmessung und Abbaureihenfolge mit `window_bench.py`, statt sie zu
wiederholen. Ohne Bildschirm und wgpu-Adapter misst es nichts und sagt es.

`file_acceptance.py`, die Einzeldateiabnahme, geht je Fall in einem Prozess
mit eigenem Profil durch das echte Fenster: Import, Erkennung samt Gruppen,
Maßänderung (sagt die Vorschau ab, ein kleinerer Wert, dann das nächste
Merkmal), Vorschau, Übernehmen, Undo, Redo; je Schritt Bild und Netzabdruck,
am Drillholder jede Bohrung. Der Bestand kommt aus dem Audit-Manifest oder
einem Ordner. Dieselbe Hülle fährt die Fälle des Funktionsdurchgangs
(`inventory --functions` mit `--package`, `--rows`, `--variants`, `--phases`;
`run --screen`; `menubar`; `report`), die Schritte dazu kommen aus
`function_bench.py` und `function_capture.py`.

`function_list.py` stellt die Liste des Funktionsdurchgangs ohne Fenster auf, je
Zeile Paket, Startszene und Weg: `--paket`, `--format md|json`, `--menueleiste
<menubar.json>`, `--check` (Ausgang 1 bei Befund) und `--szenen --out <ordner>
[--schwer]`, das die Startszenen nur außerhalb des Baums ablegt.
`function_scan.py` liest den Quelltext unter `app/ui`, `function_scenes.py` liest,
baut und prüft den Szenenkatalog `tests/data/function_scenes.toml`. Beide
importieren kein anderes `function_*`-Modul; so bleibt die Liste ohne Kreis mit den
Urteilsmodulen, die aus ihr importieren.

Werkzeug für den Schlusslauf am echten Fenster (Plan Schluss, Entscheidungen
des Koordinators): Die Sätze `schrift` (14 und 18 pt, gesetzt vor dem Fenster)
und `schriftwechsel` (9 → 14 → 9 pt, schmal und groß im Wechsel), je Sprache
ein Fall (`LANGUAGE_SETS`), stellen die
Inhaltsschrift über die Schrift der Anwendung und ihren Stilweg her
(`function_fonts.py`) — die Anwendung hat keine Schriftgröße im Profil, sie
folgt der des Systems. `skalierung` kennt 125 %. Eine Spezifikation nennt mit
`drag` den Griff, den erst ihre Handlung zeigt; `phase_drag` nimmt den Zug
gehalten auf (`05-zug-gehalten`), nach dem Bild der letzten Bewegung, damit Z1
die Aufnahme nicht mitmisst. Jede aufgenommene Fläche nimmt die Kurzhilfe an
ihrem grauen Hauptknopf auf (`function_tooltips.grey_apply_pictures`,
Protokollfeld `grey_apply`), der Hauptweg dazu die Tastenkette ab
der Reiterleiste (`function_capture.bar_chain`, `tab_from_bar`); der Fehlfall
geht den Weg einer Meldung mit mehreren genannten Knöpfen zu Ende, die Knöpfe zuerst
im Fenster der Meldung, ohne zu raten; ein grauer oder fehlender steht als `reason` da
(`function_way.py`, `messages[].way`). `run --total` und `--binding` halten
Gesamtfrist und Siegel vor jedem Fall und nach dem letzten
(`acceptance_guard.py`), die Tabelle des Berichts steht in
`acceptance_summary.py`. `seal` versiegelt den Lauf für `[[run]].seal`;
`report` rechnet das Siegel nach, bevor ein Urteil an V4 gilt
(`function_verdict_rules.run_seal_problems`).

## Codestruktur: Auflöser, Wächter, Verschiebewerkzeug

Gebaut in Schritt 0 der Codestruktur (`konzept-codestruktur-2026-10.md`, 4.1;
Funde in `konzept-codestruktur-funde-2026-10.md`).

**Der Auflöser** (`code_*.py`) liest nur Quelltext und importiert nichts aus
dem Baum. Die Rollen: `code_index` die Abfragen und `shared()`, `code_facts`
den Auszug je Datei (Bindungen, Bezüge, Patch-Stellen, belegte Typen und
Kontrollfluss), `code_values` die öffentlichen Werttypen und die exakte
Faltung (Konstanten, Pfade, Folgen, Schlüsselwörter), `code_cache` den
Datenrahmen des Zwischenspeichers (Marshal ohne Codeobjekte, Stempel vor dem
Inhalt, jede Form geprüft), `code_store` den Ergebnisspeicher je Baumstand
(Sperre, ein Bau, danach von der Platte; CS-23), `code_scripts` die Skripte für
`python -c` (CS-18), `code_report` Inventar und Lesermengen als Text. Die
Zählung der nicht faltbaren Skripte steht im Inventar, nicht hier — sie altert.
Ein gelesener Index nennt die Inhaltshashes seines Stands (`index.digests`);
wer daneben die Platte liest, vergleicht damit. Beide Speicher tragen den
Stand der geladenen Quellen (`_SOURCE` je Modul), nie den der Platte (RR2-1).

**`tree_reads`** liest und parst jede Datei einmal, auch für den Graphen;
Lesestellen sind `glob`, `rglob`, `iterdir`, `walk`, `os.walk`,
`walk_packages`, `copytree` und `git ls-files`, auch über einen Helfer;
`*`-Elemente in Tupeln zählen, ein offenes Muster liest jede Tiefe.
**`data_reads`** nennt je Einheit (Funktion, Methode, Klasse, Zuweisung auf
Modulebene) unter `tests/`, wer eine Datei außerhalb des Codes erreicht:
über ihren Namen, einen Pfad, eine Lesestelle, eine angeforderte Fixture, die
Modulebene beim Import oder eine autouse-Fixture. Daraus wählt
`affected_tests` nur die Testdateien, deren Einheit die Datei erreicht, nicht
jeden Importeur von `tests/helpers.py`.

**`affected_tests`** wählt zusätzlich über Kanten ohne Import: den aufgelösten
Lesebereich, Op- und Bausteinnamen (auch `insert_<baustein>`), einen Schritt,
den ein importiertes Modul anlegt, eine Projektdatei, die die Testdatei
rechnet, und jede Prüfung über das ganze Register (`REGISTRY.all()`) oder die
Beispielprojekte. Verzögerte Importe (`install`, `import_module`) sind Kanten;
eine Python-Datei, die ein Modul über seinen Pfad liest, zählt wie eine
Datendatei. Was eine `conftest.py` je Test ausführt (Haken, autouse-Fixtures,
Modulebene), wählt jede Testdatei darunter; was sie nur lädt, nur seine
Importeure (CS-37, CS-38). Ein Docstring oder Kommentar nennt nichts.
`selection()` liefert die lesenden Einheiten mit; als Skript läuft es ohne
zyklische Bereinigung.

**Das Verschiebewerkzeug** besteht aus `move_names` (Ablauf und Ausgänge) und
den Geschwistern: `move_cut` (Zuschnitt aus TOML), `move_source` (Lage,
Spannen, `symtable`), `move_edits` (Tabelle der Änderungen), `move_refs`
(Umschreiben in Lesern), `move_module`/`move_copies`/`move_component` (Planer
je Modus), `move_qt` (was Qt nach einem Komponentenschnitt anders sähe),
`move_receivers` (ob ein Empfänger nachweislich der Wirt ist; `[[accesses]]`
entscheidet nur, was der Nachweis offen lässt), `move_forms` (je eine Quelle
für Annotationen als Zeichenkette und Aufrufe mit Attributnamen;
`reported_calls`: was der Auflöser als `getattr`/`hasattr`-Bezug nennt, stellt
die Bezugsschleife um, die Aufrufsuche nur den Rest, und der Beweis
(`move_proof._queries`) nimmt es aus), `move_proof*`/`move_compare`/
`move_trees` (Beweis). Eine Zuschnittliste erklärt jede Abweichung
(`[[open_names]]` für Zugriffe mit offenem Namen); einen Schalter, der einen
Fund übergeht, gibt es nicht, und eine Erklärung, die nichts trifft, ist
selbst ein Fund.

**W1 und W3.** `size_ratchet --lower` senkt die Liste nach einer gelöschten
oder herausgelösten Definition im selben Commit; `--move ALT NEU …` trägt den
Umzug einer gelisteten Datei vor dem Commit ein; `--raise` gehört nur
Ordnungsschritten und vergleicht gegen HEAD. Bei einem Konflikt in der Liste
wird eine Fassung aus Git genommen und gesenkt, nie neu angelegt.
`registry_dump` schreibt das Register in Registrierungsreihenfolge
(`in_registration_order()`, CS-17); `Registry.all()` sortiert nach Namen.

## Erzeugen

*HEAD-Fassung, früher unter „Die Familien“.*

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

*Früher unter „Die Familien“.*

`site_nav.py` erzeugt die Wege aus einem sprachneutralen Pfadschema und liest
ihre sichtbaren Texte aus dem Sprachkatalog. `make_manual.py` tut das auch für
den ganzen Seiten- und PDF-Rahmen. Eine neue Sprache darf dort keine neue
Tabellenzeile verlangen; ihr Katalog und das Pfadschema müssen genügen.

Die PDF-Kapitelköpfe lesen die tatsächlichen Seiten aus den benannten Zielen
der HTML-Kapitelanker. Beim Stempeln bleibt der ganze PDF-Dokumentkatalog
erhalten, damit auch das Inhaltsverzeichnis diese Ziele weiter erreicht.
PDF-Leser arbeiten dabei aus dem Speicher und halten die Zieldatei nicht offen.
Die Lesezeichen entstehen im selben Schritt aus denselben Zielen: die Teile
des Handbuchs oben, ihre Kapitel darunter.

Gedruckt wird eine Kopie der Seite, in der ein Bildschirmfoto als JPEG steht,
wo das leichter ist; die Website behält ihre Dateien. Chromium reicht ein
JPEG unverändert ins PDF durch und packt jedes andere Rasterbild verlustfrei —
teuer für die Schrittbilder der Anleitungen, billig für die ruhigen
PNG-Bildschirmfotos. Die Begründung steht an `_printable`, die Wahl der
Qualität an `PDF_JPEG_QUALITY`. Trägt das PDF danach nicht jedes
Bildschirmfoto der Seite, hält der Lauf an: Auch ein PDF ohne Bilder ist
Bytes.

## Bauen, signieren, ausliefern

Die Stückliste stammt aus PyInstallers Analyse und dem fertigen Paket, nicht
aus `pip freeze`. Die Lizenzbeilage verwendet genau diese SBOM;
`--release-check` prüft fail-closed.

Die festen Laufzeitausdrücke von `make_sbom.py` und `make_licence_notices.py`
stehen in `RUNTIME_LICENCES`. Der Freigabewächter liest sie zusammen mit den
nativen Haupt-, Linux- und Radtabellen und dem AppImage-Kern.

`check_glibc_floor.py` prüft die Linux-Grenze am gebauten Baum: Es liest jede
ELF-Datei wie der Lader über Programmköpfe und `DT_VERNEED`, verlangt höchstens
`OLDEST_GLIBC` und keine `HOST_LIBRARIES` (`libstdc++`, `libgcc_s`). Es nutzt nur
die Standardbibliothek und läuft im Paketjob, in `linux-flatpak` und in der
Linux-Releaseakte. Die einzuhaltende Regel steht in `auslieferung.md`.

*Früher unter „Die Familien“.*

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
`build.yml`-Lauf, manuell auf `main` oder durch den Versions-Tag ausgelöst.
Sein eigener manueller Workflow läuft auf `main`. Weicht dessen Commit vom
Anwendungsbau ab, vergleicht der gemeinsame Herkunftsprüfer beide vollständigen
Git-Bäume: Pfad, Typ, Dateimodus und Objekt-SHA jedes Blatteintrags müssen
übereinstimmen, ausgenommen die ausdrücklich benannten Dateien des
Signierablaufs und dessen Tests und Dokumentation. Unvollständige Baumantworten
oder andere Änderungen sperren den Installerbau und die lokale Setupsignatur.
Der gemeinsame Prüfer bindet einen Tag-Lauf zusätzlich an das tatsächliche
GitHub-Tag `v<APP_VERSION>` und dessen aufgelösten Commit. Dazu kommen das
ursprüngliche Signierarchiv und ein unveröffentlichter,
ebenfalls commitgebundener Release-Entwurf mit signierter EXE und Herkunftsakte.
Archiv, Manifest, Zeitstempel und Herausgeber prüfen die gemeinsamen Helfer
aus `sign_release.py`. Nur die EXE wird ersetzt und die Übergabe neu gebunden.
Der feste Inno-7-Compiler baut daraus Setup, SHA-256 und `windows-installer-build.json`
für die lokale abschließende Setupsignatur. Die Rückgabe nennt zusätzlich den
tatsächlichen Installercommit und Installerlauf; der lokale Prüfer bindet beide
an den vollständig erfolgreichen CI-Lauf. Weicht der Installercommit ab, fährt
der Workflow vorher `tests/test_sign_release.py` und
`tests/test_windows_signed_installer.py` gegen genau diesen Stand; ein roter
Lauf endet vor Herkunftsprüfung und Bau (Wächter in `tests/test_packaging.py`).
Der Installerjob benötigt
`contents: write`, weil GitHub unveröffentlichte Entwürfe nur mit Push-Rechten
zugänglich macht. Er veröffentlicht nichts und erhält keine Signiergeheimnisse.

*HEAD-Fassung, früher unter „Die Familien“.*

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

*Früher unter „Die Familien“.*

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
Downloadordners und vor jeder Kopie; `main` rechnet danach Startseiten
(`render_pages`) und Versionsdatei (`version_content`) fertig und schreibt erst
dann, in der Reihenfolge Pakete, Kasten, Versionsdatei. Ein Halt der
Versionsdatei lässt so weder Pakete unter `dl/` noch einen Kasten zurück. Windows-Pakete müssen über die gemeinsame
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

## Fallen, die man einmal falsch macht

Der Punkt „Version vor jedem Bau erhöhen“ steht als Regel in
`.claude/rules/auslieferung.md` („Die Version wird vor dem Bau erhöht, und nur
über das Werkzeug“).

*Früher unter „Die Familien“.*

Aufnahmewerkzeuge reichen ihre feste Merkmalskennung als Argument bis zur
Auswahl und Beschriftung durch; sie ergänzen keine Attribute an `Session`.
Kreisflug-Loops warten zusätzlich auf den eigenen Arbeiter der Druckanalyse
im Fenster, damit Standbild und Film denselben vollständigen Prüfbericht zeigen.
Nach Abschluss einer bewusst verworfenen Aufnahme räumt `Session.forget_changes()`
deren Änderungsmarkierung und eigene Wiederherstellung. Die Quelldatei bleibt
dabei ungeschrieben; das anschließende Schließen läuft durch den normalen
Fenster- und Arbeiterabbau.

`window_bench.py` beendet seinen einzigen Lauf in Besitzreihenfolge: erst
Arbeiter und Sitzungsverbindungen lösen, dann über
`Viewport.release_renderer()` den Renderer bei noch lebendem
Qt-Elternfenster schließen, zuletzt das Fenster. Derselbe terminale Weg liegt
am akzeptierten `MainWindow.closeEvent`; `MainWindow.release()` bleibt für
mehrere Fenster in einem Prozess bewusst ohne Viewport-Abbau.

*HEAD-Fassung, früher unter „Die Familien“.*

**Wer in den Website-Baum schreibt, schreibt mit `newline=""`.** Der Baum steht
auf `\n` (`.gitattributes`: `eol=lf`), hochgeladen wird der Arbeitsbaum, und
`Path.write_text` ohne diese Angabe macht unter Windows aus jedem Umbruch ein
`\r\n`. Im Diff sieht man davon nichts — Git glättet beim Einchecken zurück —,
aber der Server bekommt die Seite in einer anderen Zeilenform als ihre
Nachbarn, und der nächste Bytevergleich meldet sie als offen. Betroffen sind
`stamp_assets`, `make_seo`, `make_legal`, `make_changelog`, `make_download`,
`make_manual`, `make_web_images` und `sign_version`;
`tests/test_website.py` hält beides fest, das Werkzeug und den Baum.

*HEAD-Fassung, früher unter „Drei Dinge, die man einmal falsch macht“.*

`check_env --freeze` übernimmt lokale Paketversionen und erhält ausschließlich
die in `PLATFORM_PINS` belegten Abhängigkeiten anderer Zielplattformen.
Ändert sich eine bedingte Kante im Laufzeit-/Bauwerkzeugbaum, werden diese Liste
und die vollständige Windows-/Linux-/macOS-Auflösung zusammen geprüft;
entfernte allgemeine Pakete werden nicht durch einen Freeze wieder aufgenommen —
solange sie nicht mehr installiert sind: `pip install -c` entfernt nichts, und
`pip freeze` schreibt fest, was in der `.venv` liegt. `check_env` meldet deshalb
Pakete, die installiert sind, aber nicht im Satz stehen (`leftovers`); vor einem
Freeze wird jedes davon entfernt oder bewusst aufgenommen.

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

*Früher in der Karte unter „Fallen, die man einmal falsch macht“; dort steht
seither die Kurzfassung.*

**Rohaufnahme und Schnitt sind getrennt.** Ein vollständiger `capture.json`
ist Voraussetzung für Sprache und Export. Szenen verweisen auf echte
Bildbereiche und Bildindizes; kurze Fassungen dürfen eigene Ausschnitte
verwenden. `minimum_seconds` schützt die Lesedauer von Dialogen auch bei
kurzem Sprechertext. Dateiauswahl, Einheitenfrage und Hinweise bekommen
eigene Abschnitte. Das Setup speichert die Druckerkennung als `printer_id`,
getrennt von der gleichnamigen Szene `printer`.

**Die Aufnahme greift nur das eigene Fenster ab.** Nach Kamerabewegungen
wird der Renderer vor dem Bild ausgerechnet; ein offener Dialog wird über
sein eigenes Widget ergänzt. Die Rohaufnahme aktiviert das Hauptfenster
nicht zwischen modalen Schritten. Lokale Dateipfade werden beim Schnitt
verdeckt, der gewählte Dateiname und die Handlung bleiben sichtbar.
`--screen-model` und `--screen-serial` wählen den Bildschirm anhand seiner
Identität. `--native-resolution` nimmt dessen volle Pixelgröße im eigenen
Vollbildfenster auf; `screen-evidence.json` belegt Bildschirm, Fenster und
Rohbildgröße. Der Recorder verwendet den Bildschirm des Fensters, nie
stillschweigend den Hauptbildschirm. Bereits sichtbare Kundendialoge werden
nur positioniert; ihre Modalität, Fensterflags und Größe bleiben erhalten.

**Eine Bedienhandlung ist kein Ergebnisstandbild.** `interaction.json`
hält echte Mauswege, Auswahl, Tasteneingabe und Übernehmen in getrennten
Bildbereichen fest. Der geführte Schnitt erklärt vor der Handlung und
spricht das neue Maß erst auf dem passenden Zustand. Die Gesten werden
nicht an kurze Sprachdateien angepasst. Vorher/Nachher verwendet dieselbe
native Kamera und Schattierung und trägt eindeutige Beschriftungen.
Der gemeinsame Szenenschnitt hält Ansage, Handlung und Ergebnis getrennt;
deren echte Ausschnitte dürfen sich pro Phase unterscheiden. Ein geöffnetes
Dropdown gehört vollständig in den Aktionsausschnitt. Tutorials entstehen
direkt in 2560 × 1440, Shorts in 1080 × 1920; der Exportbeleg nennt Quell-
und Ausgabegröße getrennt.
`hold_frames` kürzt nur ausdrücklich belegte Einzelbildhaltungen mit
Begründung; die umgebenden Maus- und Tastaturbilder behalten ihre Rohdauer.
Lange native Hinweiszeilen dürfen mit `wide_focus` mehr Bildbreite erhalten,
während die vollständige Karte daneben als Kontext sichtbar bleibt.

*Früher in der Karte unter „Fallen, die man einmal falsch macht“; dort steht
seither ein Satz mit Verweis hierher.*

**Sprache und Musik bleiben nachprüfbar.** Satzzeiten stammen aus den
tatsächlich erzeugten WAV-Dateien. Shorts erhalten dieselben Zeiten als
eingebrannte Untertitel; Tutorials zusätzlich als SRT. Jede Themenmusik
hat ein eigenes prozedurales Arrangement. Der Mix senkt Musik unter Sprache
ab und prüft den fertigen H.264/AAC-Film vollständig. Eine technische
Prüfung ersetzt keine Sicht- oder Hörprüfung.
Externe Musik wird nur mit Dateihash, Quelle und Lizenznachweis gemischt;
die Sprachclips werden einzeln angeglichen, die Musik wird unter Sprache
abgesenkt. Tempo und Tonhöhe der Stimmen bleiben erhalten.
Zusammenhängende Sprecherabschnitte bleiben eine WAV-Datei. Eine separate
akustische Satzzuordnung kann die Untertitel verfeinern; ihr Dateihash, der
WAV-Hash, der unveränderte Text und die Zeitgrenzen werden vor Nutzung geprüft.
Nach allen Audiofiltern wird jeder Abschnitt auf seine genaue Zahl von
48-kHz-Samples gebracht. Die absolute Platzierung und Dateihashes stehen in
`narration-placement.json`; Lautheitsfilter dürfen keine Zeitdrift ansammeln.

## Der Sitzungszustand ist ausgenommen

Nicht mehr in der Karte: Der Absatz gilt `.claude/.state/`, nicht `tools/`.
Die Ausnahme steht mit Begründung im Kommentar über `[tool.ruff]` in
`pyproject.toml`; was `.claude/.state/` ist, sagt `.claude/README.md`.

*HEAD-Fassung, früher unter „Der Sitzungszustand ist ausgenommen“.*

`.claude/.state/` trägt die Messskripte vergangener Durchsichten. Es sind
Wegwerfwerkzeuge — sie haben ihre Zahl geliefert und werden nicht mehr
angefasst. `ruff` lässt sie deshalb aus; ohne diese Ausnahme wäre das Tor rot,
ohne dass sich an der Anwendung etwas geändert hätte.
