# `tests/` — die Suite

Mehr als 150 Python-Dateien und weit über 80 000 Zeilen. Eine Datei je Testart; `data/` ist der
Referenzkorpus.

Die Regeln stehen in `.claude/rules/tests.md` — dort auch die Messfallen, die
schon einmal zugeschnappt sind. Hier steht, **wie sie gefahren wird** und
**was wo geprüft wird**.

`test_matching_lifecycle.py` führt ein Raster mit 1056 wirklichen Flächen als
STL und STEP durch Import, Änderung, Cache, Speichern und Undo/Redo. Nur die
Merkmalszahlgrenze wird im Test freigegeben; Erkennung und Zuordnung laufen
über die Anwendung. Der Nachweis gilt den IDs, Maßen und Flächenträgern,
nicht einer höheren Produktionsgrenze oder einem Leistungsbudget.

`test_matching_competition.py` prüft konkurrierende alte Identitäten gegen
unabhängig aufgezählte globale Zuordnungen und den geometrischen Kostenweg.
`test_match_decisions.py` prüft vollständige Gruppen, geometrische
Wiedererkennung, Nichtfortführung und widersprüchliche Ansprüche.
`test_matching_answers.py` verbindet diese Antworten mit tatsächlichen
Bohrungen, körperbezogenen Gruppen, Operationsabbruch und Wiederöffnung.
Die Prüfung des Fragekontexts benötigt keine Oberfläche; die Anzeige- und
Tastaturfälle in `test_ui.py` bleiben Fensterprüfungen für das Release.

Der Crash-Wächter in `test_leash.py` verfolgt auch Arbeiter, die eine Fabrik
zurückgibt oder an einen Helfer übergibt. Nur die Verbindung des entsprechenden
Parameters zählt; ein verbundenes anderes Signal im Helfer deckt den Arbeiter
nicht ab. Kleine positive und negative Quelltextfälle prüfen diese Grenze.

Die Prüfserver aus `test_activation_server.py` und `test_public_php_security.py`
beziehen ihre Befehlsbasis aus `php_probe.php_command()`.
Benötigte Erweiterungen werden je Test benannt, bei vorhandenen lokalen
Bibliotheken ausschließlich im Prüfprozess geladen und vor dem Serverstart
tatsächlich geprüft. Die globale `php.ini` bleibt unverändert; eine fehlende
Erweiterung behält die gemeinsame Skip-/CI-Fehlerregel.
`test_website.py` unterscheidet freigegebene Außenlinks von eingebundenen
Ressourcen und prüft diese Grenze mit Gegenfällen einschließlich Vorladen und
Vorabverbindungen. Der Tageszähler der Aktivierung zählt neue Geräteplätze;
abgewiesene und wiederholte Anfragen bleiben außerhalb dieses Zählers.

`test_filament_inventory.py` prüft Migration und atomare Mehrspulenbuchungen
einschließlich echter Prozesskonkurrenz. `test_filament_usage.py` verbindet
Projektbindung, Ausgabeumfang und werkzeugweise Mengen. Die getrennten
Fensterdateien `test_filament_inventory_ui.py`, `test_filament_assignment.py`,
`test_filament_usage_ui.py` und `test_filament_workflow.py` decken Regal,
Zuweisung, Buchungsdialog und erfolgreiche beziehungsweise abgebrochene
Ausgaben ab; sie benutzen isolierte Lagerdateien, nie den Nutzerbestand.
Die Workflowfälle prüfen auch echte 3MF-Profilwerte, die wiederholte
Spulenprüfung vor Bestätigung und Filamentabwahl mit Undo. Die Projektfälle
unterscheiden bei Herstellerprofilbindungen alte Positionslisten (`None`)
von ausdrücklich leeren Identitätsbindungen (`()`).

`test_geometry_review_regressions.py` verbindet kleine analytische
Geometriefälle mit den registrierten Kundenwegen: Skizzenringe und Splines,
Flächentaschen und Normalen, Merkmalsbearbeitung sowie Auswertung mit frischem
Plattencache. Speichergrenzen werden vor jeder großen Allokation abgefangen.

`test_surface_placement.py` prüft Originalflächen, gedrehte Maßrahmen,
Aussparungen, Schnittansichten und den identischen Werkzeugkörper in
Vorschau und Operation. Gestufte Bohrungen werden nach dem echten Schnitt
als zusammenhängende Kette erkannt; Merkmale werden mit ihren verwandten
Formen und Kennungen versetzt oder kopiert. Kreisfacetten benötigen belegte
Rundungsmerkmale, während echte regelmäßige Vielecke Bezugskanten behalten.

## Die Fahrweise steht einmal — in `CLAUDE.md`

Wie die Suite gefahren wird — alle Tests ohne Fenster vor dem Commit, Fenstertests
und Leistungsprüfungen ausschließlich beim Release, `/pruefen` für beide Umfänge und
`tools/affected_tests.py` je Schritt — steht mit Befehlen und den drei Fallen
beim Lesen des Ergebnisses im Abschnitt **Befehle** von `CLAUDE.md` im
Projekt-Root. Bis zum 14.09.2026 stand derselbe Text hier ein zweites Mal,
und von zwei Fassungen desselben Satzes veraltet immer eine (RM-098).

Was nur diese Datei weiß:

- `test_widget_lifetime.py` ordnet `installEventFilter(self)` seiner
  umgebenden Klasse zu und prüft deren eigenen `eventFilter` auf den
  Abmeldegriff. Ein anderer Filter in derselben Datei erfüllt diesen Vertrag
  nicht.
- `test_suite_script.py` prüft die Halbierung des geteilten Laufs mit echten
  Shell-Prozessausgängen und simulierten pytest-Aufrufen, einschließlich 256
  gezählter Fehler: Erfolgreiche kleinere Teilstücke löschen den
  ursprünglichen Prozessabbruch nicht, der Gesamtlauf endet mit Exit 1.

## Was wo geprüft wird

| Frage | Datei |
|---|---|
| Läuft der Kern ohne Qt? | `test_core_isolation.py` |
| Öffnet jedes angebotene Modellformat dieselbe Referenzgeometrie? | `test_import_formats.py` |
| Deutsche Stämme in Bezeichnern? | `test_language_rules.py` |
| Ist jede Op vollständig registriert? | `test_registry_consistency.py` |
| Zweimal ausgewertet = identisch? | `test_evaluation.py` |
| Lässt sich der Verlauf umbauen — einfügen, verschieben, aus- und einschalten —, folgt jeder Verweis seinem Merkmal, fragt oder sagt ab statt umzubiegen, und stellt Strg+Z die alte Folge her? | `test_history.py` (Planen, Stellen, Absagen), `test_revision.py` (an beiden Kernen, an der Platte mit Sollwerten aus den Schritten und an den Beispielprojekten), `test_cli.py` (dieselben Wege auf der Kommandozeile); das Verlaufsfeld in `test_history_revision_ui.py` — die Helfer ohne Fenster, Feld und Sitzung beim Release |
| Jede Rückfallstufe einmal erzwungen? | `test_boolean.py` |
| Sammelparameter-Ops über das Register | `test_gesture_ops.py` |
| Öffnen alte Projektdateien? | `test_project.py`, Beispiele in `data/projects/` |
| Trägt jede Ausnahme einen Vorschlag? | `test_errors.py` |
| Bedeutung allein über Farbe? | `test_theme_and_palette.py` |
| Neun Menüs, zwölf Zeilen, acht Felder | `test_interface_limits.py` |
| Sind alle Kataloge vollständig? | `test_translations.py` |
| Bleiben Käuferzuordnung und Betreiberzugang aus dem Server und arbeitet die Support-Verwaltung nur per Digest? | `test_licence_admin.py`, `test_activation_server.py` |
| Halten die PHP-Endpunkte ihre Missbrauchsgrenzen? | `test_public_php_security.py`; ohne PHP ein Skip, in der Linux-CI ein Fehler — `php_probe.py` entscheidet das für alle Endpunkttests |
| Budget §31, Schwelle 25 % | `test_performance.py` (`-m performance`) |
| Abhängigkeiten gegen die Freigabeliste | `test_licences.py` |
| Die vier Hauptwege Ende zu Ende | `test_way_one.py` … `test_way_four.py` |
| Trägt ein Resin-Drucker sein Verfahren, kommen die zwei zentralen Eigenschaften und die Exportauflösung daraus, schweigen die neun FDM-Befunde an einem Resin-Projekt, folgt das Material dem Drucker, und öffnet ein Programm ohne Familie nur? | `test_resin.py` — die acht Abnahmepunkte aus Konzept §9, Stufe 1; Weg 1 mit Resin-Profil gegen den Befundkatalog |
| 39 Referenzanfragen an den Agenten | `test_agent_suite.py`, Fälle in `agent_cases.py`, das Modell mit vorgeschriebenen Antworten in `scripted_backend.py` |
| Importiert jede Schicht nur nach unten — `core` nie `ui`/`cli`, `i18n` gar nichts? | `test_layer_direction.py` |
| Und eine Ebene tiefer: welches Kernpaket importiert welches, eifrig oder träge? | `test_core_package_direction.py` — jede eifrige und jede träge Kante eingefroren, dazu der Kreis aus acht Paketen; eine neue Kante ist eine Entscheidung, eine abgebaute verschwindet aus der Liste |
| Stimmen `_EXPORTS`, `__all__` und `TYPE_CHECKING` der Lazy-Pakete überein, und löst jeder Eintrag auf? | `test_lazy_exports.py` |
| Wählt `tools/affected_tests.py` die richtigen Tests aus dem Importgraphen? | `test_affected_tests.py` |
| Verwenden die gemeinsamen Hooks das unterstützte Protokoll und richtige Patchpfade? | `test_solidon3d_hooks.py`; echte Event-Auslösung im Editor ist zusätzlich zu prüfen |
| Stehen Codex-Agenten, Skills, Referenzen und Aufrufregeln auf dem Stand ihrer Claude-Quelle — auch im frischen Klon? | `test_agent_mirror.py`; prüft Generator, Drift und Quellenfehler sowie die erzeugten TOML-Dateien mit `tomllib` |
| Zeichnet der Renderer, was der Vertrag verspricht — Bildpunkte, Picks, Kamera, Griffe? | `test_render_contract.py`, `test_render_gizmo.py` und `test_render_gfx_regressions.py` am pygfx-Renderer ohne Fenster (ohne wgpu-Adapter ein Skip mit Grund); `test_render_factory.py` der Aufbau über `factory.py`; `test_render_shapes.py` und `test_navigator.py` ganz ohne Renderer |
| Gilt eine Zusage auch dort, wo der Code auf dieser Maschine nie läuft? | `test_hard_rules.py` — fcntl-Puffergrenze über den Quelltext, die Nutzerverzeichnisse für darwin, win32 und linux |
| Wird eine gewählte Kante vor dem Verbrauchercache gebunden, fragt eine Kollision den Kunden, und gilt die Antwort nur für ihren Eingang? | `test_edge_binding.py` — zwei Quader mit vier Tausendstel Spalt an beiden Kernen; die Fensterhälfte (Linien, Dialogzeilen, Betonung über das Token) in `test_viewport_decisions.py` und `test_ui.py` |
| Sagen beide Kerne an einer angeschnittenen Bohrung dasselbe — angeschnitten, berührt, ohne eigenen Körper — und ist die Umfangsschwelle eine Zahl? | `test_partial_bores.py` — zwei überlappende Bohrungen zu je 315 Grad, dazu die Gegenkontrollen ganze Bohrung, Querloch und Randöffnung |
| Misst die Zylindereinpassung Kreis und Facettenband getrennt, hält das Maß unter starrer Bewegung und ungleicher Vernetzung, und wird ein grobes Vieleck nie als runder Zapfen veröffentlicht? | `test_cylinder_measurements.py` — Kreis- und Polygonmaße unabhängig vom Erkenner nachgerechnet |
| Kommen die Endmaße runder Flächen aus den Originalpunkten, folgen sie dem bekannten starren Rahmen, und lässt sich die Einpassung vor und während der Vorbereitung abbrechen? | `test_round_surface_measurements.py` — Zylinder, Kegel, Torus und Kugel in beiden Kernen, Facettenunterteilung ohne Geometrieänderung |
| Erhält die räumliche Vorauswahl der Zuordnung dieselbe Antwort wie die vollständige Kostenmatrix, und erreicht ein Abbruch den Aufrufer vor jeder Antwort? | `test_spatial_matching.py` — getrennte Merkmale ohne die volle Zuteilung, Gleichstände und Rechteckordnung unverändert |
| Bleibt der exakte Körper beim Versetzen, Verdoppeln, Drehen und Entfernen einer Bohrung, eines Langlochs, einer gesenkten Bohrung (ganz oder nur ein Abschnitt), eines Zapfens, einer Kuppe, eines Kegelstumpfs einer allein stehenden Senkung oder eines Einschlusses (mit und ohne Insel) exakt, und bleibt er es beim Senken und Verschließen — Volumen analytisch, Kennungen belegt, STEP-Umlauf verlustfrei? | `test_exact_feature_ops.py` — die gekippte Kette und der gekippte Zapfen messen sich am Netzweg derselben Operation, gekippter Kegelstumpf und gekippte Senkung an einem unabhängig aus den Maßen gebauten Kegel |
| Tragen Wulst und Kehle in beiden Kernen dieselben fünf Handlungen — Entfernen trifft den Schaft, Versetzen hält das Volumen und die unabhängige Erkennung findet den Ring an der neuen Stelle, Verdoppeln legt den zweiten an, die Rohrdicke ändert sich gegen die Analytik, der quer gestellte Ring trägt die gedrehte Achse, ein Ring, der der ganze Körper ist, sagt es, und Netz und exakt weichen nur um die Tessellierung ab? | `test_torus_feature_ops.py` — die Analytik ist π²r²R ± 4πr³/3 für einen Ring R/r auf einem Schaft vom Radius R |
| Lässt sich ein Gewinde in beiden Kernen ändern und verschließen — außen bleibt beim Entfernen der Kern, innen ist die Bohrung zu, das neue Gewinde trifft Pappus über das Gangprofil und wird danach erkannt, linksgängig und eine Steigung ohne Kern sagen ab, das Fenster bietet Ändern und Entfernen und nichts Bewegendes? | `test_thread_feature_ops.py` — aufgesetztes M6 × 1 auf einer Platte und ein M6 × 1 darin, geändert auf M8 × 1,25 |
| Nehmen Wulst, Kehle und Gewinde in beiden Kernen ein Filament an und geben es zurück — der Ring genau seine Dreiecke, das erzeugte Gewinde seine Flanken ohne Spitze und Sockel, das Gewindeloch ohne die Stirnflächen der Platte, und behält der exakte Ring sein Filament durch eine feinere Vernetzung? | `test_filament_on_rings_and_threads.py` — `paint_slot` und `clear_filament` an den Körpern der Torus- und Gewindetests |
| Bekommt ein vorhandenes Gewinde sein Gegenstück am anderen Teil — im Tabellenmaß, als ein Schritt mit Gewindepassung, in beiden Kernen, mit einem Undo für beides, und sagen ein Maß ohne Normgröße, ein Nicht-Gewinde, ein belegtes Linksgewinde und dasselbe Teil ab; trifft die Erkennungsgrenze nie zwei Tabellengrößen zugleich? | `test_thread_counterpart.py` — zwei Platten, ein M6 darauf oder darin; das Fenster ohne Dialog in `test_counterpart_ui.py` |
| Sind die Kernwahl-Haken gefallen — entstehen die fünf Grundkörper exakt, wo der Kern da ist, und als Netz, wo nicht; behält ein gespeicherter Schritt seinen Kern; bleibt eine Bohrung am exakten Körper ohne Haken exakt; folgt das Aushöhlen der Tabelle aus Konzept §10.1; stehen die exakten Grundkörper dort, wo ihre Netz-Zwillinge stehen; und stellt der Verlauf einen Schritt weiter auf seinen Zwilling um, mit der Sperre des Kerns dagegen? | `test_kernel_switch.py` — Kegel, Kugel und Ring gegen die Analytik auf 10⁻⁶, ihre Netz-Zwillinge auf zwei Prozent |
| Baut jeder mitgelieferte Baustein am exakten Träger exakt — jede Grundform als Zwilling mit demselben Rahmen, jeder Baustein gültig, geschlossen, mit der erklärten Körperzahl, dem Volumen der Analytik, seinen Merkmalen und der STEP-Rundreise, und bleibt ein exakter Träger beim Einsetzen exakt, samt Verbund für das lösbare Teil und Befund, wenn der Baustein den Träger verfehlt? | `test_exact_parts.py` — alle 35 Bausteine bauen exakt; `shapes.mesh_only` ist nur noch die Sperre für einen Weg, der Dreiecke anfasst, und ein Netzträger nimmt weiter den Netzweg |
| Liest der exakte Kern ein importiertes Gewinde ohne Erzeugerwissen — Teilung, Vorschub, Gangzahl, Händigkeit, Seite, Nenn-Ø, Tiefe, Achse —, lehnt er Gegenformen mit Grund ab, lässt er die Eingabe unangetastet, reißt der Abbruch an jeder Schleife, und sagt der Netzweg dasselbe, soweit er es kennt? | `test_thread_import.py` — fünf Basiskörper aus `data/threads/`, drei davon je Lauf gegen ihren Erzeuger geprüft, alles Abgeleitete aus M6 gebaut |
| Nehmen Verrunden, Fase, Wulst und das Zurücknehmen einer Rundung beide Kerne an? | `test_mesh_edges.py` — jede Zusicherung gegen eine analytische Zahl; die Gegenproben haben dabei zweimal den Testkörper verworfen und nicht den Fix |
| Und Fläche versetzen und Formschräge? | `test_mesh_faces.py` — die Treppe ist dort der kleinste Körper, an dem „eine Fläche" von „alle einer Richtung" zu unterscheiden ist |
| Findet `tools/twin_scan.py` die Zwillinge, für die es gebaut wurde? | `test_twin_scan.py` — gepflanzte Fälle, und ein leerer Baum ist ein Fehler statt eines Ergebnisses |
| Überleben zwei Sitzungen, die gleichzeitig in `MEMORY.md` schreiben? | `test_memory_index.py` — zwei echte Prozesse; ohne Sperre gingen gemessen 17 bis 20 von 40 Einträgen verloren |
| Lässt ein Versetzen am Netz keine Narben zurück, verliert eine vergrabene Senkung kein Volumen, sagt ein Ring ohne Achse ab, und reist keine alte Dreiecksnummer mit? | `test_feature_moves_keep_shape.py` — vier Züge an der Lochplatte bleiben bei 796 Dreiecken, das Volumen der Senkung auf 10⁻⁹ |
| Findet die vektorisierte Selbstdurchdringung dieselben Paare wie der skalare Weg? | `test_self_intersections.py` — `geom.intersections` je Paar gegen die skalare Rechnung, deckungsgleiche Dreiecke derselben Ebene, zwölf Treffer zweier Quader |
| Prüft das Einlesen Dichtheit und Kennzahlen einmal und reicht sie warm weiter? | `test_ingest_figures.py` — `is_watertight` und `volume` zählen ihre Aufrufe |

## Der Korpus

`data/` trägt die Modelle, gegen die Geometrie gemessen wird — `meshes/` und
`projects/`. **Ein neues Fehlerbild wird eine Datei hier**, kein Sonderfall im
Code.

Was ein Skript wiederherstellt, liegt nicht darin: Das parametrische Skript
ist die Quelle, die Datei daraus ist das Ergebnis.

## Sprache in diesem Verzeichnis

**Hier gilt der Bestand der Datei, nicht die Bezeichnerregel.** `app/` und
`tools/` reisen zum Kunden, `tests/` liest nur, wer hier arbeitet — deshalb
prüft `test_language_rules.py` genau jene zwei Verzeichnisse und dieses nicht.

Gezählt am 23.08.2026: 78 deutsche Bezeichner in 27 Dateien. Sie werden
**nicht** umbenannt — eine Massenänderung in fremden Dateien kostet mehr, als
sie einbringt. Assert-Meldungen bleiben ebenfalls beim Bestand der Datei.

## `conftest.py` tut drei Dinge, die leicht zu übersehen sind

- Es setzt `QT_QPA_PLATFORM=offscreen` — Qt-Tests brauchen kein Bild.
- Es biegt **die Nutzerverzeichnisse in einen Temp-Ordner** um (§38), `HOME`
  eingeschlossen. Läuft ein Test außerhalb der Suite, fehlt ihm das, und er
  liest in Roberts echtem Profil.
- Unter `CI` beendet es den Lauf, wenn der exakte Kern fehlt
  (`pytest_sessionstart`, Muster `php_probe.py`): `build.yml` installiert das
  Extra `brep` in jedem Testlauf, und ohne den Kern übersprängen sich die
  Dateien des exakten Kerns still. Lokal bleibt ein fehlender Kern ein Skip —
  über `tests.helpers.exact_kernel()`, das **vor** jedem `OCP`-Import einer
  Testfunktion steht; `test_toolchain.py` prüft die Zusicherung.

## `helpers.py` — was mehr als eine Datei braucht

Prüfkörper und Wächter, die mehrere Testdateien lesen, stehen in
`tests/helpers.py` unter öffentlichem Namen (`exact_kernel`, `ridged_shaft`,
`the_torus` und die Maße des Schafts), nicht als `from tests.test_x import
_privat` beim zufällig ersten Nutzer. Was dort noch fehlt, nennt der
Modul-Docstring — die Quelldateien gehören anderen Umbauten.

Wer `WorkerLeash.start` durch eine Testfunktion ersetzt, übernimmt den Abbau
der echten, absichtlich nicht gestarteten Worker. Ein lokaler Finalizer löst
deren `release_finished_references()`, merkt `deleteLater()` vor und stellt
`DeferredDelete` zu. Nur ein Fensterfeld zu leeren reicht nicht: Die Leine hat
diese Worker nie registriert. Der vollständige Qt-Abbauvertrag steht in
`.claude/rules/wartezeit.md` unter „Loslassen allein räumt nicht auf“.
