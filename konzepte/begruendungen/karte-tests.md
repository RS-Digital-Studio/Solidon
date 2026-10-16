# Begründungen zu `tests/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf die Frage „was wird
> wo geprüft“, die Helfer und die Stolperfallen verdichtet wurde. Die Karte steht
> dort; hier stehen die ausführlichen Fassungen, das Warum und die Messwerte
> ihres Tages — wörtlich, gegliedert nach den Überschriften der Karte. *Früher
> unter …* nennt die Stelle der alten Karte; *HEAD-Fassung* heißt: aus dem
> letzten Commit, weil die ungesicherte Zwischenfassung den Absatz gekürzt oder
> gestrichen hatte.

## Kopf

Der Absatz verwies auf einen Abschnitt „Befehle“ mit drei Fallen in der
Wurzel-`CLAUDE.md`; die Fallen stehen dort nicht mehr. Wie gefahren und ein
Lauf gelesen wird, steht in `/pruefen` und `.claude/rules/tests.md`.

*HEAD-Fassung, früher unter „Die Fahrweise steht einmal — in `CLAUDE.md`“.*

Wie die Suite gefahren wird — alle Tests ohne Fenster vor dem Commit, Fenstertests
und Leistungsprüfungen ausschließlich beim Release, `/pruefen` für beide Umfänge und
`tools/affected_tests.py` je Schritt — steht mit Befehlen und den drei Fallen
beim Lesen des Ergebnisses im Abschnitt **Befehle** von `CLAUDE.md` im
Projekt-Root. Bis zum 14.09.2026 stand derselbe Text hier ein zweites Mal,
und von zwei Fassungen desselben Satzes veraltet immer eine (RM-098).

## Was wo geprüft wird

### Begriffe, Absagewege und Agentenorte

Hier statt in der Karte, weil sie an ihrem Budget steht.

| Vertrag | Zuständige Testdatei |
|---|---|
| Beginnt jede Merkmalsart groß, und fallen *Überstand* und *Überhang* in keiner Sprache zusammen? | `test_catalog_terms.py` |
| Bietet eine Kanten- oder Rundungsabsage *Andere Kanten wählen* statt *Andere Objekte wählen*? | `test_edge_refusal_ways.py` |
| Bietet eine Flächenabsage (Formschräge, Fläche versetzen, Aushöhlen, Dichtnut, Muster bis zum Rand) *Andere Flächen wählen* statt *Andere Objekte wählen*, in beiden Kernen? | `test_face_refusal_ways.py` |
| Bietet eine Absage an einem gewählten Merkmal (Bohrung, Gewinde, Kammer, Verschluss, Ring, Merkmalsoperationen) *Anderes Merkmal wählen* statt *Andere Objekte wählen*? | `test_feature_refusal_ways.py` |
| Richtet sich eine Auswahlhandlung nach dem Schritt, der die Absage auslöst, mit einem Feld aus seinem Schema, im ganzen Register, bei einzeln gewählten Kanten die gewählten; gehen Halt und Ausgabebefund (*Aushöhlen* ohne Hohlraum) beide durch die Anpassung? | `test_choice_ways.py` |
| Öffnet *Anderes Merkmal/Andere Kanten/Andere Flächen wählen* den Schritt mit dem Feld sichtbar und im Fokus, auch *Einzelne Kanten*, *Eingabe korrigieren* daneben den Wert? (Fenster) | `test_choice_ways_ui.py` |
| Nennt eine Absage ohne Schrittkennung (*Gegenstück zum Gewinde*, nichts zum Slicen) ihren Weg als Satz statt eines Knopfs ohne Wirkung, und nicht noch einmal neben seinem Knopf (`left_out`)? Stehen Merkmal und Längen lesbar darunter? | `test_stepless_advice.py` |
| Steht jedes Maß unter einer Absage oder einem Befund mit Einheit und Längen in der Anzeigeeinheit, auch ein Schlüssel ohne Endung, den Agent oder Handler lesen; schlägt der Wächter über alle `values` in `app/core` an? | `test_value_measures.py` |
| Nennt *In Einzelteile aufteilen* Splitter und bietet *Splitter behalten* an? | `test_split_splinters.py` |
| Nennen die Zusatzwerkzeuge des Agenten ihren Fensterort, und steht er in der gebauten Menüleiste? | `test_agent_tool_places.py` |

### Dialog-, Karten- und Vorschaugrößen

| Vertrag | Zuständige Testdatei |
|---|---|
| Dialoginhalt, Klappen und Aktionsleisten erreichbar, Fenster im Bildschirm; Einstellungen mit eigenem Bedienablauf | `test_dialog_layout.py`, `test_dialog_layout_regressions.py`; Einstellungen in `test_ui_settings.py` |
| Merkmalmenge leer/ein/sechs/viele, Modell- und Textwechsel, Schrift und Stil, Querleiste, dynamische Ergänzung im offenen Dialog, letzte hohe Zeile mit Tastatur erreichbar | `test_feature_list_ui.py` |
| Erklärung der ungültigen Drei-Punkte-Ebene in jeder Sprache, spätes Fehlerangebot bei automatischer/manueller Größe, wirklicher Anwendungsschriftwechsel | `test_operation_refusal_layout_ui.py` |
| Kurzer natürlicher Anfangsbedarf, langer Inhalt mit Rollweg, gewählte Außenhöhe bei wachsender Aktionsleiste oberhalb des physischen Mindestmaßes | `test_short_dialog_ui.py` |
| Vollständige Einleitung und Knöpfe in sechs Sprachen, echter Schriftwechsel, senkrechte/waagrechte Knopfleiste, Einzelknopfumbruch und zugänglicher Originalname, Return/Escape samt fokussiertem Abbrechen, physische Mindesthöhe bei erhaltener Nutzerbreite | `test_operation_font_layout_ui.py` |
| Sichtbare Auswahlseite, echte Schrift, Zeilenhöhe und Handlungsspalten, natürlicher XYZ-Bedarf nach schmalem Start, Feldbreite/-höhe bei Schriftwechsel hin und zurück, gleichbleibender Querbedarf bei vorübergehendem senkrechtem Überlauf, ganzzeiliger Knopfumbruch auch beim Rasterwechsel, abgelöster Reiter samt gespeicherter Größe | `test_card_content_width.py` |
| Schema-Vorderseite aller Paare und Sprachen, Klappe/Werte/Tabfolge, Paarhilfe, Rollen ohne Fokus, fokussierte Radbedienung, Abbruch und Dokumenterhalt, eigene Fenstergröße | `test_counterpart_front.py` |
| Natürlicher Anfang und Wiederzuklappen mit gleichem Inhalt, echte Inhaltsschrift, Paarwechsel, manuelle Maße, passives Wachstum sowie dauernde/benötigte/vorläufige Rollleisten | `test_counterpart_initial_height_ui.py` |
| Maßgruppe und rechte Zeile teilen Vorderseite und Hilfe; Sammelhakenbudget, Einlauf, Ausdruck/Ablehnung, Radius, Fokus/Wiederverwendung, Hauptaktionspriorität, Einzel-/Sammelübernahme mit Undo, registrierter Befehl/Suche und örtliche Erkennung; konsistente Themenfixture | `test_feature_front_contract.py` |
| Layoutitem-Hüllen vor verzögertem Widgetabbau entwerten, verschachtelte Layouts und externe Hosts; Nachbarn und zurückgegebene Maßfelder erhalten | `test_feature_layout_lifetime.py` |
| Lesen eines Layouts hinterlässt keine Elementhülle: Breite messen und `removeRow`, Prüfstand am umbrechenden `DialogFooter`, eigene Abstandhalter und innere Layouts bleiben gültig; kein Index-`itemAt` außerhalb von `layout_lifetime` (FD-201) | `test_layout_item_wrappers.py` |
| Echte Lage-/Abstandsbefunde und warme Daten bei mm/in/mm, sechs Sprachen, Auswahl/Einzelheiten/Nachschub, rohe Gruppenidentität samt vorigem Stand, gelesener Reiter und offene/geschlossene Körperknoten; Slicerwerte und Freitext als Gegenfälle | `test_finding_display_units.py` |
| Nach Absage wieder sichtbare Vorschaulegende, kurze und lange Texte in sechs Sprachen und zwei tatsächlichen Anwendungsschriften | `test_preview_banner_layout.py` |
| Vorschaulegende nur über einer Differenz, die Volumen oder Körper hinzufügt oder wegnimmt (nicht beim Umbenennen, nicht vor der Differenz) | `test_preview_legend.py` |
| Maßgruppe nach Auf-/Zuklappen neu bemessen, ohne Layoutschleife; vorgemerkte Antwort bei Gruppentausch und Abschluss | `test_measure_group_layout.py` |
| Maßkarte an Titel/freiem Grund ziehen; Felder, Knöpfe und Klappen bedienbar; Nutzerort bei Größenwechsel, Grenzen, Abbruch und Rückrufabbau; am gemeinsamen Verteiler (`app_events`) nur während des Zugs angemeldet, QWindow-Maustransport durchgelassen, damit Qt beim Release seinen impliziten Druckempfänger löst; Bewegungszeiger am Druckempfänger, dessen eigener oder geerbter Zeiger auf jedem Ausgang zurück (Escape, Verbergen, Reset, Abbau, Fokus- und Fensterverlust, erster Bewegungsfehler); ein fremder Override bleibt unberührt, auch im Fehlerweg; Verlust des Druckempfängers (gelöscht, umgehängt) und Abbau des Helfers beenden die Anmeldung | `test_measure_card_drag_ui.py` |
| Echter Maßfluss: Nutzerort bei Klappen, Werten und fehlender Fläche; Gruppenwechsel/Abbruch, Seiten-/Bodenkarten und freie Maßfelder auch im Rückfall | `test_measure_card_placement.py` |
| Bettrasterfarbe und Hauptlinien getrennt von Bauraum/Zeichnung; Hauptlinien an den gezeichneten Maßzahlen auf jeder Platte, mm und Zoll, Tiefe, Themenwechsel und Sichtbarkeit; Bettmaßzahlen aus der Textrolle, Bauraumfarbe unverändert | `test_bed_grid_visibility.py` |
| Bettraster ohne Fenster: Hauptlinien genau an den Zahlen von `bed_scale`, Nebenschritt ab der Mitte (10 mm, halber Zoll), Rand schließt ohne Doppelstrich | `test_bed_grid_at_scale.py` |
| Nur direkte gewöhnliche Werkzeugknöpfe in Ruhe ohne Rahmenfarbe; Geometrie und Hover/Fokus/Wahl sowie fremde Eingaben und Hauptaktion erhalten | `test_toolbar_rest_style.py` |
| Ruhende Knöpfe durchscheinend, geschlossene Hilfsflächen verborgen; bestehendes Neuzeichnen wertet Vorschlag/held/waiting aus (held-Fall ruft es selbst auf); bewegter Zug/Feldentwurf und wartender Entwurf sichtbar, Abbruch/Wiederaufbau ohne Entwurf verborgen; Hover, Halten, Leave/Release und direkter Lochdruck bei gleichen Bounds/Geometrie/Picks; Griffbuchstaben/Maße: Text/Fensterpaar, Anker, Schrift und Pickauftrag bei Themenwechsel, Update/Neuaufbau; L-Felder außerhalb projizierter Knopfhüllen bei Aufbau, Kamera/Zoom, DPR und Maßänderung; vollständige endliche Anker ohne Projektion/Nahplatz, kein Update bei gleichen Punkten/Texten und kein Rücksetzen der Gizmo-Zugmatrix durch den Kameratimer | `test_feature_grip_readability.py` |
| Raum-/Vordergrundmischung bei Erstellung und set_opacity für Vorder-/Rückseite/Kanten, wirksame Deckkraft 0/1/teiltransparent und force_opaque, Tiefentest/Queue; leere Beschriftungsfelder bei Textwechsel, Sichtbarkeit, _wake und adopt/build mit erhaltenen Nachbarpaaren/Listenplätzen; Materialzustände ohne Qt/GPU | `test_front_overlay_alpha.py` |

Diese Dateien prüfen die jeweiligen Zusagen; ihre Nennung ist kein Bericht
über einen bestandenen Lauf oder eine native Darstellung. Die Schriftfälle
binden Anwendungsschrift und Stylesheet zusammen und lesen die wirksamen
Schriften der Inhaltswidgets, statt nur den Dialogcontainer umzustellen.

### Messvertrag des Funktionsdurchgangs

| Vertrag | Zuständige Testdatei |
|---|---|
| Vorfläche vor Befundklick, Fehlerbild vor Escape, gemessene Auswege und unveränderter Treffertest | `test_function_surface_timing.py` |
| Eigene Maßgruppe/Merkmalszeile, zugehörige sichtbare Klappbeschriftung, richtiger übernommener Schritt | `test_function_feature_measurement.py` |
| Wirkliche native Bildquelle, lokale Pixelkoordinaten und Skalierung, fehlende Pixel bleiben ungemessen | `test_function_capture_native_image.py` |
| Zustandsfarbe echter Hauptknöpfe, absichtlich falsche Farben, Symbolausschluss und fehlende Bild-/Schriftpixel | `test_function_contrast_roles.py` |
| Tatsächliche Hauptknopfrolle mit halbfetter Grundschrift, fremde Größen/Familien, strikte optionale Messwerttypen und lesbare Altprotokolle | `test_function_primary_fonts.py` |
| Offene eigene Fenster per Escape vor dem nächsten Sprachprojekt abbauen | `test_function_language_cleanup.py` |
| Sofortige/spätere Vorschau desselben Auftrags, getrennte Vor-/Dialogfläche bis zum Bericht, fehlende Pixel ohne Palettenersatz, echte neue Revisionseingabe, eigener nichtmodaler Generator | `test_function_review_connections.py` |
| Markierter Wertträger statt unmarkiertem inneren Zahlenfeld | `test_function_revision_fields.py` |
| Bereitschaftsfehler, Fund und Timeout erreichen den begrenzten modalen Abbau | `test_function_machine_cleanup.py` |
| Ganze Prozessgruppe des Dateiprüfstands: normaler und nicht erfolgreicher Ausgang, Timeout und Ausnahme in echten Windows-Prozessketten | `test_file_acceptance_process_tree.py` |
| Szenenexport löst vorherige Auswahl über den Kundenweg; nur unbelegte Teilmenge wird abgewiesen | `test_function_export_preparation.py` |
| Stabile lebende Qt-Hülle am C++-Dateidialog; echte Geometrie- und Flächenwechsel starten die Ruhezeit neu | `test_function_surface_identity.py` |
| Qt-Fensterdispatcher: ignorierendes Kind, Annahme und verschachtelte Rollbereiche, Richtungen/Modifier/Koordinaten, klarer Rückweg bei fehlender API | `test_function_wheel_dispatch.py` |
| Zweiphasige Knopfbereitschaft: öffentliche Zeigerfahrt vor frischer Ziel-/Rechteck-/Freigabe-/Trefferprüfung; Tooltip weicht durch Bewegung, bleibende Überdeckung bleibt Fund; Zieltausch/Verschieben/Verbergen/Sperren/Abbau und letzter Direktklick-Guard; Fensterplatzierung: Wiederholung am maximierten Zielschirm ohne neue Clientgeometrie, Ziel-/Größenwechsel normalisiert vor Geometrie/Resize; echte Qt-Client-/Fensterhüllengröße und bestehende Mindestgröße | `test_function_bench_window.py`, `test_function_setup.py` |

Schema, Urteil und Gegenbeispiele bleiben bei `function_checks`,
`function_points`/`function_judges` und `function_samples`; die zugehörigen
Inventar-/Urteilstests stehen im folgenden Überblick.

Die Schriftfälle laden wirkliche gebündelte Schriftdateien und prüfen den
aufgelösten Familiennamen sowie unterschiedliche Glyphenbreiten. Leere
Offscreen-Familien werden nicht durch eine erfundene Ersatzfamilie geheilt.

### Weitere Zuordnungen

Der Funktionsdurchgang verteilt seine Zusicherungen: `test_function_list.py`
prüft das Inventar und die Ziele, `test_function_report.py` die Berichte,
`test_function_alarms.py` die Urteile und Gegenproben,
`test_function_captures_window.py` die Erhebung am Fenster.
`test_function_guard.py` und `test_function_guard_aliases.py` halten die
erlaubten Eingabewege einschließlich lexikalischer Aliase;
`test_function_licence_measurement.py` fährt Lizenzmessungen mit `Walk`,
`StepMachine` und den Attrappen aus `bench_fakes.py`, ohne ein Qt-Fenster.
`test_process.py` hält externe Starts ohne Systemfehlerdialog, auch mit einer
defekten ausführbaren Datei. `test_in_view_arming.py` hält dieselbe Handlung
an Knopf und Maßgruppe; `test_sketch_editor_measure_field.py` wertet den
Beispielausdruck des Maßfelds in jeder Sprache aus. `test_dialog_lifetime.py`
prüft Dialogfreigaben über Klassen, Fabriken, Attribute, Hilfsaufrufe und
zeitversetzte Einstiege; `test_widget_lifetime.py` behält sein eigenes Gebiet.
`test_print_field_units.py` hält Grenzen, Schritt, Vorgabe und die Werte jedes
mitgelieferten Profils jedes Druckfelds in seiner Anzeigeeinheit, den Weg eines
Prozentwerts als Anteil in die Datei für Orca und Prusa und den Formatschritt
52 → 53 samt Hinweis beim Öffnen (FD-197); `test_bridge_flow_dialog.py` dasselbe am
Druckdialog und im Prüfbericht. `test_vendor_field_values.py` hält die Feldgrenzen gegen die
Herstellerwerte aus `data/vendor_print_values.json` und zeigt sie am gebauten Feld
ungekürzt (FD-203). `test_part_stamps.py` hält, dass der Abdruck eines eigenen Bausteins eine
Formaterhöhung übersteht, auch für Abdrücke aus 0.6.0 und 0.5.3 (FD-212);
`test_filament_usage_own_recipe_060.py`, dass eine Buchung aus 0.6.0 für einen Körper aus
eigenem Rezept derselbe Druck bleibt (FD-232).

`test_boolean_stage3.py` bindet den Jitter der dritten Stufe an die Zugabe,
axial und schräg; `test_boolean_empty_result.py` prüft leere Ergebnisse und
Meldungen für die drei Verknüpfungen an beiden Kernen.
`test_evaluation_container_chain.py` prüft die vollständige Kette beim
Behälter und ihre Qualitätswahl. Sperr- und Fokusfälle liegen in
`test_change_lock.py`, `test_licence_lock_offers.py` und
`test_finding_action_focus.py`: wechselnde Gründe, Freigabe ohne Neuauswahl,
lesender Rückweg aus der Verlaufsvorschau und Fokus im Prüfbericht.

Die ausführlichen Zuordnungen der kompakten Karte:

| Ort / Frage | Vertrag |
|---|---|
| Rechnet der Hilfsprozess des Netzkerns bitgleich, endet er beim Abbrechen und mit dem hart beendeten Elternprozess, fällt er zurück, wenn eine Rechnung nicht hinein- oder herauskommt, und sieht die Boolesche Kette seinen Tod? | `test_kernel_process.py` — echte und nachgestellte Hilfsprozesse, die Fälle einzeln in `konzepte/begruendungen/karte-tests.md` |
| Nimmt jeder unterstützte Slicer, echt installiert, Solidons Platte an und gibt eine gemessene Druckdatei zurück? Kommen Stützabstand oben und unten und die untere Trennschicht unter Gitter und Baum an, wie Solidons Tabellen sagen? Fragt ein Test die Maschine nur über `installed_slicer`? | `test_real_slicers.py` (`slicer`-Marker, beim Push nach main auf Linux und macOS; die Kontaktmessung dort auch synthetisch) · `test_slicer_selection.py` — Auswahl für die Läufer und Wächter |

Die Tabelle der HEAD-Fassung trägt zu jeder Datei ausführlich, woran sie
prüft; die Karte nennt nur noch Frage und Datei.

*Früher unter „`tests/` — die Suite“.*

`test_closure_ops.py` prüft *Verschluss ändern* an einem Rohr mit L-Wegen, einem
Plattendeckel als STL und einer Bausteinaufnahme.

`test_input_dialog.py` hält ohne Fenster, dass im Kundenweg kein `QInputDialog`
und kein `QColorDialog` mehr steht, dass `inform` nur ein Scheitern meldet und
dass die Funktionsliste die acht Eingabestellen aus FD-22 unter ihrem alten
Kennzeichen führt; am Fenster Hausstil, Tastatur, Farbwähler und Wertfeld am
Ort und die Quittungen der Freischaltung (FD-24).

`test_kernel_process_lifecycle.py` prüft am Windows-Jobobjekt, mit gehaltenen
Griffen und über eine echte OS-Abfrage, dass ein rechnender Helfer mit seinem
hart beendeten Elternprozess endet und nach normalem Start niedrigere
OS-Priorität hat; die negativen Kontrollen treffen dasselbe Assert. Er braucht
weder Fenster noch Leistungsmarken.

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
Projektbindung, Ausgabeumfang und werkzeugweise Mengen. `test_filament_usage_fingerprint_history.py` hält den Abdruck einer Buchung über Updates fest: Sollwerte aus der Codekopie von 0.5.3, Projekt und Lager von 0.5.3 selbst geschrieben, jedes spätere Einstellungsfeld gezählt (RM-705). `test_filament_usage_stored_inputs.py` schickt druckgleiche Änderungen am Ergebnis (umsortiert, verschoben, float32) am Abdruck vorbei und ändert ihn mit jeder Eingabe, Kalibrierung, Antwort und Wahl der Grundlage; der Vorabdruck kippt dabei als Gegenprobe, und ein Wächter hält die Lesarten gleich denen des Cache-Schlüssels (RM-706). Die getrennten
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

*HEAD-Fassung, früher unter „Die Fahrweise steht einmal — in `CLAUDE.md`“.*

Der CI-Prüfvertrag steht in `konzepte/konzept-ci-testlaufzeiten-2026-09.md`.
`test_ci_runner.py` prüft Partitionen, Sammlung, Prozessisolation und Berichte
des isolierten Läufers ohne echte Fenster. `test_packaging.py` prüft die
ausgeführten Workflowblöcke und die Paketfreigabe, `test_packaging_platform.py`
was die Linux- und Mac-Pakete zusätzlich halten (Linux-Grenze, Erprobung des
Fensterstarts am Intel-Mac, früh endende Leser hinter Pipes, Flatpak ohne
installierte Pakete, 3D-Maus-Modul der Spec, macOS-Paket); `workflow_helpers.py`
grenzt dafür Jobs und Schritte eindeutig ab, ohne ein allgemeiner YAML-Parser
zu sein. `data/ci_window_durations.json` und `data/ci_core_durations.json`
tragen historische Gewichte mit Herkunft; die aktuelle Sammlung bestimmt
weiterhin die vollständige Auswahl. `test_ci_runner.py` sammelt dafür echte
Testdateien zweimal mit `--ci-shard` und einmal ohne und verlangt dieselben
Fälle, keinen doppelt und keine Datei geteilt.

*Früher unter „Die Fahrweise steht einmal — in `CLAUDE.md`“.*

`test_ui.py` führt die allgemeinen Kundenwege. Fachliche Teilbereiche liegen
in `test_ui_dialogs.py`, `test_ui_export.py`, `test_ui_licensing.py` und
`test_ui_remote.py`. `ui_helpers.py` stellt deren gemeinsame Fixtures und
Hilfen bereit; jedes Fenster und jede Sitzung bleiben pro Test frisch.
Anzeige- und Schemafälle in `test_operation_ui.py` verwenden ein leeres
Fenster, soweit ihre Aussage keine importierte Geometrie benötigt.

Formulare und Absagen der Dialoge: `test_form_fields.py` hält den gemeinsamen
Weg zu Feldname und Feldsatz (`form_fields`) und wacht über die Formulare von
Parameter-, Kalibrier-, Baustein- und Chatdialog; `test_parameter_units.py`
die Länge in Anzeigeeinheit im Parameter- und Bausteindialog;
`test_refusal_details.py` Absage, *Einzelheiten* und *Werte ansehen*;
`test_dialog_texts.py` ohne Fenster, was ein Dialog vorn sagt (Lesezeile
*Stelle*, erster Satz hinter *Dicke geben*); `test_field_help_rest.py` den Satz
in Kurzhilfe und Beschreibung an Generatorbeschreibung, „Werte mitgeben“ und
*Typ*; `test_rename_dialog.py` den jetzigen Namen als Vorgabe beim Umbenennen;
`test_measure_refusal_status.py`, dass die Statusleiste keine Ablehnung
wiederholt, die am Maßfeld steht.

Aus Review 1 des Restpakets A: `test_parameter_panel_units.py` (Zoll in der
Leiste, ein Maß ohne Einheit bleibt eine Zahl), `test_parameter_unit_switch_window.py`
(Wechsel bei offener Leiste: abgeleitete Maße, Grenze, Einheitenliste),
`test_halt_ways_window.py` (Wege am haltenden Befund frei, hinter einem fremden
Halt grau), `test_history_change_rows.py` (Doppelklick auf Drucker-, Material-
und Passungsänderung), `test_step_values_copy.py` (*Kopieren* gibt gespeicherte
Werte), `test_literal_shared.py` (ein Literal für TOML und OpenSCAD),
`test_rename_dialog.py` (Vorgabe des Namens, markiert beim ersten Fokus,
Übernehmen erst nach einer Änderung) und `test_foundation_crash_window.py`
(nach einem Absturz des Grundlagenarbeiters die Tabelle, nichts Vorläufiges).
Zu FD-182: `test_refusal_field_ways_window.py` (Wächter über jeden
Operationsdialog und jedes Feld: ein Feldweg ist Knopf mit Sprung oder
kein Knopf, *Eingabe korrigieren* dann still, die Ebene als Rat; der
umbrechende Knopf) und `test_plane_refusal_field.py`
(die Ebenenabsage einer Skizzenoperation nennt `sketch`). Zu FD-185:
`test_report_offer_height_window.py` (Handlungsknöpfe im Prüfbericht eines
niedrigen Fensters bei 11 und 18 pt nie unter ihrer Mindesthöhe; ein Knopf
folgt dem Schriftwechsel in beide Richtungen). Zu FD-190:
`test_sketch_way_focus_window.py` (Knopf im Bericht → Skizzenmodus: Tastatur
in *Zeichenebene* bei unlesbarer Ebene, in der Ansicht bei einer kaputten
Zeichnung). Nach dem Merge A/B: `test_field_ways_source.py` (eine Quelle
`errors.FIELD_WAYS`) und `test_field_ways_both_paths_window.py` (FD-95,
FD-182, RB2-2 im Dialog, Ebenenweg im Fenster).

Der Operationsdialog hat je Fund eine eigene Datei:
`test_operation_dialog_names.py` öffnet jede registrierte Operation und
verlangt je Eingabefeld einen Namen, keinen doppelt;
`test_operation_dialog_first_focus.py` den markierten Vorgabetext;
`test_required_text_field.py` den leeren Pflichttext ohne Vorschau;
`test_operation_dialog_height.py` die Anfangshöhe ohne Leerstreifen,
`test_operation_dialog_flap_height.py` dasselbe für jede Operation in jeder
Sprache beim Öffnen und nach dem Aufklappen, quer gerollt nur bei schmalem
Schirm (FD-200); `test_content_height_dialogs.py` dasselbe für die übrigen
Dialoge mit Klappen, je nach Auf- und Zuklappen (FD-198, FD-199);
`test_grouped_count_field.py` Dreiergruppen im Ganzzahlfeld;
`test_operation_dialog_change.py` den Änderungsweg (*Übernehmen*, grau bis zur
ersten Änderung), `test_change_waits_for_valid_list.py` den Sperrgrund des
Feldes vor dem Satz zur ersten Änderung (D2); `test_unlisted_choices.py` Namen statt Kennungen für Werte,
die eine Liste nicht führt, `test_unlisted_names.py` dieselben Namen wie in
den Meldungen und Sätze ohne Genus (D3, D6). Ohne Fenster: `test_hole_compensation_words.py` (der Name des
Ausgleichs an jeder Bohrung, in jeder Sprache). `test_calibration_units.py`
prüft *Material kalibrieren* in Zoll. `test_wrapped_captions.py` verlangt jede
Zeile jeder umgebrochenen Beschriftung bei Grund- und großer Schrift,
`test_grouped_count_fields.py` liest den Quelltext auf Ganzzahlfelder ohne
Dreiergruppen.

Statische Quellprüfungen teilen die Vorbereitung innerhalb eines Testfalls:
`test_language_rules.py` prüft je Datei denselben AST auf alle Sprachregeln;
`test_translations.py` extrahiert die Nachrichten einmal für alle Kataloge.
Prüfungen des Extraktors selbst lesen ihre veränderlichen Quellen frisch.
`test_directory_docs.py` schneidet ausgeschlossene Verzeichnisse vor dem
Betreten ab. `test_parts.py` verbindet die Merkmalszusagen mit dem ersten
von weiterhin zwei unabhängigen Bauten für den Determinismusvergleich.

*HEAD-Fassung, früher unter „Was wo geprüft wird“.*

| Frage | Datei |
|---|---|
| Läuft der Kern ohne Qt? | `test_core_isolation.py` |
| Öffnet jedes angebotene Modellformat dieselbe Referenzgeometrie? | `test_import_formats.py` |
| Deutsche Stämme in Bezeichnern? | `test_language_rules.py` |
| Ist jede Op vollständig registriert? | `test_registry_consistency.py` |
| Zweimal ausgewertet = identisch? | `test_evaluation.py` |
| Schätzt die Frage vor einer großen Vollerkennung die Dauer auf diesem Rechner, lässt ein Abbruch keinen halben Messwert zurück, und startet die Erkennung selbst die Probe nie? | `test_recognition_time.py` — die echte Rechenprobe mit gesteuerter Uhr |
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
| Wählt `tools/affected_tests.py` die richtigen Tests aus dem Importgraphen? | `test_affected_tests.py`; die Kanten ohne Import (Tupel mit `*`, Muster aus Daten, Lesen über einen Pfad, verzögerter Export, was eine `conftest.py` lädt oder je Test ausführt, Leser eines Projektordners) je mit Attrappe und Fall am echten Baum in `test_affected_edges.py`; Bäume aus `selection_trees.py` |
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
| Lässt sich ein Gewinde in beiden Kernen ändern und verschließen — außen bleibt beim Entfernen der Kern, innen ist die Bohrung zu, das neue Gewinde trifft Pappus über das Gangprofil und wird danach erkannt, links-, mehrgängige, kegelige und Whitworth-Gewinde bleiben, was sie sind, eine Steigung ohne Kern sagt ab, das Fenster bietet Ändern und Entfernen und nichts Bewegendes? | `test_thread_feature_ops.py` — aufgesetztes M6 × 1 auf einer Platte und ein M6 × 1 darin, geändert auf M8 × 1,25 |
| Nehmen Wulst, Kehle und Gewinde in beiden Kernen ein Filament an und geben es zurück — der Ring genau seine Dreiecke, das erzeugte Gewinde seine Flanken ohne Spitze und Sockel, das Gewindeloch ohne die Stirnflächen der Platte, und behält der exakte Ring sein Filament durch eine feinere Vernetzung? | `test_filament_on_rings_and_threads.py` — `paint_slot` und `clear_filament` an den Körpern der Torus- und Gewindetests |
| Bekommt ein vorhandenes Gewinde sein Gegenstück am anderen Teil — im Tabellenmaß oder im eigenen Maß (Ø 66,6 × 6 aus einer Bohrung von 60 mm), als ein Schritt mit Gewindepassung, in beiden Kernen, mit einem Undo für beides, und sagen ein Maß außerhalb der Bausteingewinde, ein Nicht-Gewinde und dasselbe Teil ab; bekommt ein Links-, mehrgängiges oder kegeliges Gewinde sein Gegenstück, und wird nur gefragt, wo die Messung zwei Größen verschiedener Reihen nicht trennt? | `test_thread_counterpart.py` — zwei Platten, ein M6 darauf oder darin; das Fenster ohne Dialog in `test_counterpart_ui.py` |
| Sind die Kernwahl-Haken gefallen — entstehen die fünf Grundkörper exakt, wo der Kern da ist, und als Netz, wo nicht; behält ein gespeicherter Schritt seinen Kern; bleibt eine Bohrung am exakten Körper ohne Haken exakt; folgt das Aushöhlen der Tabelle aus Konzept §10.1; stehen die exakten Grundkörper dort, wo ihre Netz-Zwillinge stehen; und stellt der Verlauf einen Schritt weiter auf seinen Zwilling um, mit der Sperre des Kerns dagegen? | `test_kernel_switch.py` — Kegel, Kugel und Ring gegen die Analytik auf 10⁻⁶, ihre Netz-Zwillinge auf zwei Prozent |
| Baut jeder mitgelieferte Baustein am exakten Träger exakt — jede Grundform als Zwilling mit demselben Rahmen, jeder Baustein gültig, geschlossen, mit der erklärten Körperzahl, dem Volumen der Analytik, seinen Merkmalen und der STEP-Rundreise, und bleibt ein exakter Träger beim Einsetzen exakt, samt Verbund für das lösbare Teil und Befund, wenn der Baustein den Träger verfehlt? | `test_exact_parts.py` — alle 35 Bausteine bauen exakt; `shapes.mesh_only` ist nur noch die Sperre für einen Weg, der Dreiecke anfasst, und ein Netzträger nimmt weiter den Netzweg |
| Liest der exakte Kern ein importiertes Gewinde ohne Erzeugerwissen — Teilung, Vorschub, Gangzahl, Händigkeit, Seite, Nenn-Ø, Tiefe, Achse —, lehnt er Gegenformen mit Grund ab, lässt er die Eingabe unangetastet, reißt der Abbruch an jeder Schleife, und sagt der Netzweg dasselbe, soweit er es kennt? | `test_thread_import.py` — fünf Basiskörper aus `data/threads/`, drei davon je Lauf gegen ihren Erzeuger geprüft, alles Abgeleitete aus M6 gebaut |
| Nehmen Verrunden, Fase, Wulst und das Zurücknehmen einer Rundung beide Kerne an? | `test_mesh_edges.py` — jede Zusicherung gegen eine analytische Zahl; die Gegenproben haben dabei zweimal den Testkörper verworfen und nicht den Fix |
| Und Fläche versetzen und Formschräge? | `test_mesh_faces.py` — die Treppe ist dort der kleinste Körper, an dem „eine Fläche" von „alle einer Richtung" zu unterscheiden ist |
| Wartet die Schichtanalyse auf einen Export, und liest das Fenster den Slicerbestand nach dem Start, sobald keine Auswertung läuft? Kennt der nächste Export einen im Slicer angelegten Drucker? | `test_export_background.py` — Fenstermethoden an einem Namensraum; der gemerkte Bestand in `test_slicer_profiles.py` (Signatur, Schutzgriffe des Merkers, Gegenproben), `test_export.py` (echter Exportweg), Vorwahl und Bytevergleich gegen ein Lesen ohne Merker in `test_print_settings_ui.py` |
| Findet `tools/twin_scan.py` die Zwillinge, für die es gebaut wurde? | `test_twin_scan.py` — gepflanzte Fälle, und ein leerer Baum ist ein Fehler statt eines Ergebnisses |
| Überleben zwei Sitzungen, die gleichzeitig in `MEMORY.md` schreiben? | `test_memory_index.py` — zwei echte Prozesse; ohne Sperre gingen gemessen 17 bis 20 von 40 Einträgen verloren |
| Lässt ein Versetzen am Netz keine Narben zurück, verliert eine vergrabene Senkung kein Volumen, sagt ein Ring ohne Achse ab, und reist keine alte Dreiecksnummer mit? | `test_feature_moves_keep_shape.py` — vier Züge an der Lochplatte bleiben bei 796 Dreiecken, das Volumen der Senkung auf 10⁻⁹ |
| Findet die vektorisierte Selbstdurchdringung dieselben Paare wie der skalare Weg, und verwirft die Trennprüfung davor nie einen Treffer? | `test_self_intersections.py` — `geom.intersections` je Paar gegen die skalare Rechnung, deckungsgleiche Dreiecke derselben Ebene, zwölf Treffer zweier Quader; die Trennprüfung gegen die genaue an Zufall, Fächern und drei Paaren an der Toleranz (je eines für jede ihrer Sicherungen), der Fächerzylinder unter einem Budget, das der alte Weg nicht schaffte |
| Prüft das Einlesen Dichtheit und Kennzahlen einmal und reicht sie warm weiter? | `test_ingest_figures.py` — `is_watertight` und `volume` zählen ihre Aufrufe |
| Trägt *Kanten verfeinern* die Merkmale über die Herkunft der Dreiecke weiter, unter und über der Grenze der Vollerkennung, auch nach dem Wiederöffnen aus dem Plattencache, und nur unter Beleg? | `test_matching.py` — die Lochplatte mit gezählter Erkennung und gesperrter örtlicher Suche; ein fremdes Netz, eine verschobene Herkunft und ein verändertes Netz tragen nichts |
| Rechnet der Hilfsprozess des Netzkerns bitgleich und zurückgestellt ohne Nachladen, endet er beim Abbrechen und — untätig — mit einem hart beendeten Elternprozess, fällt er zurück, wenn eine Rechnung nicht hinein- oder herauskommt, und sieht die Boolesche Kette seinen Tod? | `test_kernel_process.py` — echte Hilfsprozesse, dazu nachgestellte stumme, sterbende und abweisende; verspätetes Ende, Ressourcenfreigabe, bleibende Absage, ursprüngliche Startursache, Startkontingent und Generationswechsel auch am öffentlichen Aufruf; ENOSPC gegenüber echtem Speichermangel über pack/copied und den öffentlichen Call-/Serve-Transfer; Schwelle null, Aufruf aus einem Nebenfaden. Das gebaute Paket startet `tools/check_frozen_helper.py` im Paketjob; `test_packaging.py` prüft dessen eigenes Endebudget und harte Stopfehler mit Attrappen. *Aus der Karte verschoben, als sie ihr Budget überschritt.* |
| Kommt ein Backslash in einem Pfad als Backslash an statt als Steuerzeichen? | `test_source_escapes.py` — jedes Oktal-Escape außer `\0` und jedes rohe Steuerzeichen in einer nicht rohen Zeichenkette unter `app/`, `tests/`, `tools/`, `website/`, `packaging/`; Hex-Escapes sind die gewollte Form |
| Bleiben Musteränderung und -entfernung auf STL-gerundeten Zylinderfacetten dicht und frei von Selbstschnitten? | `test_pattern_features.py` — binärer STL-Rundlauf in beiden Güten, getrennte Importfelder und deren unabhängige Bearbeitung, Schnittprüfung, Wiedererkennung, Winkelnaht, Abbruch und Attributerhalt; `test_platform_identity.py` prüft die Ausrichtung aufrecht und gekippt gegen Plattformrauschen. *Aus der Karte verschoben, als die Suche (RM-735) ihre Zeile bekam.* |
| Findet die Suche, was der Kunde tippt? | `test_search.py` — drei Runden, Güte, Vorauswahl und Kundenwörter in jeder Sprache, ohne Fenster; das Suchfeld der Karte mit Trefferliste, Tasten und Hinweiszeile in `test_selection_operations.py` |
| Verträgt jeder Fall den JUnit-Bericht der CI, und hinterlässt er die Anwendung, wie er sie fand? | `test_suite_isolation.py` — kein Fall fordert `record_property` oder `record_xml_attribute` an (im `xunit2`-Bericht von `run_suite_isolated.py` ein Setup-Fehler), mit Gegenprobe; Befunddaten legt `record_trace` aus `conftest.py` als Berichtsabschnitt ab. Ein Fallpaar stellt Thema, Stil und Schrift um und prüft im Nachfolger Stil, Palette, Stylesheet, Schrift, Themenmerker und Thema gegen den Stand davor (Rückgabe: `_the_application_look_stays_with_its_test`) |
| Ist ein Rollbereich kein namenloser Tab-Halt, und erreicht Tab im Prüfbericht die angebotene Handlung? | `test_scroll_areas.py` — kein nacktes `QScrollArea` in `app/ui` (ausstehende Dateien anderer Pakete in `PENDING`, Eintrag muss fallen), Behälter auf NoFocus, Lesebereich mit Namen, Tab im Parameterdialog; `test_report_tab_chain.py` drückt Tab ab jedem Halt vor der Handlung (FD-139, FD-140); `test_card_tab_chain.py` Tab von der Reiterleiste in die vordere Seite, Auswahl von oben nach unten (FD-177) |
| Öffnet ein Doppelklick auf eine Maßänderung im Verlauf das Maß, und behält ein geändertes Merkmal seinen Platz? | `test_history_parameter_rows.py` (Panel), `test_history_parameter_window.py` (Fenster: Doppelklick → `action_edit_parameter`), `test_feature_order.py` (Platz nach *Bohrung ändern*, neue Bohrung bei den Bohrungen) |
| Stehen Merkmalfenster und Auswahlkarte, wo das Auge sie sucht? | `test_feature_footer.py` (Knopfzeile unter der scharfen Handlung), `test_footer_in_sight.py` (im Bild mit wenig Rollweg, auch wenn die Karte danach wächst), `test_feature_footer_window.py` (dasselbe im Fenster, Kopf der Wahl sichtbar), `test_feature_footer_low_window.py` (unterste Handlung in niedriger Karte, Mutation an `keep_in_sight` rot), `test_feature_first_change.py` (*Übernehmen* wartet beim heutigen Stand auf die erste Änderung), `test_offered_unchanged.py` (ohne Fenster: welche Handlung beim heutigen Stand angeboten wird), `test_selection_card_room.py` (kein Leerraum über „Filament und Druck“), `test_print_section_place.py` (Filament oben, mit Farbfeld), `test_refusal_line.py` (Sperrzeile „Hier nicht möglich“ in sechs Sprachen), `test_info_dot.py` (Symbol statt „i“), `test_lock_reason_once.py` (Sperrgrund einmal, Gegenprobe vor `4170f587b` rot) |
| Zeigen Objektbaum, Bericht und Leisten ihre Werte ganz? | `test_object_tree_columns.py` (Maßspalte und Mindestbreite des Baums), `test_left_card_width_window.py` (die linke Karte bekommt sie im Fenster, Mutation an `_card_width` rot), `test_report_rows.py` (Messreserve der Befundzeilen), `test_finding_line_names.py` (Körper einmal), `test_split_bar_spacing.py`, `test_analysis_offer_accent.py`, `test_bar_field_sentences.py`, `test_halted_report_offers.py` (FD-104 aus F3) |
| Spricht die Parameterleiste die Anzeigeeinheit und ihr Wertfeld das Menü der Zeile? | `test_parameter_panel_units.py` (Zoll gezeigt, mm gespeichert, ohne Rundungsrest), `test_parameter_row_menu.py` (Rechtsklick → *Ändern …*), `test_parameter_empty_note.py` (Satz misst sich je Breite) |
| Trifft jeder Patch in `tests/`, was er meint (W2: Kopfkopien, ungelesene Namen, `raising=False`, Verbotspatches mit Leser)? Löst jeder Bezug auf ein eigenes Modul auf, auch spät und unter `TYPE_CHECKING` (W5)? | `test_patch_targets.py` · `test_import_resolution.py`, beide über `tools/code_index.py` |
| Fragt der Auflöser richtig? | `test_code_index.py`, `test_code_index_regressions.py`, `test_code_index_followups.py` (Bekanntfälle an Attrappen aus `code_index_helpers.py`) · `test_code_cache.py` (Datenrahmen) · `test_code_store.py` (Ergebnisspeicher je Baumstand, Stempel des geladenen Codes) · `test_code_scripts.py` (Skripte für `python -c`) · `test_code_queries.py` (`hasattr`/`getattr` mit Vorgabe, Wächter gegen Aliasse aus anderen Modulen, CS-34) |
| Liest jede Quelltextprüfung Unterpakete mit, und erreicht jede ihren Verstoß im Unterpaket (W4)? Bleibt das Prüfmodul flach? | `test_source_readers.py` (Helfer `source_tree.py`) · `test_licence_build.py` |
| Halten Dateien über 2 000 Zeilen ihre Zahl an Definitionen (W1)? Bleibt der Registerabzug gleich, und behält ein Rezeptwechsel die Folge der übrigen Einträge (W3, CS-17)? | `test_size_ratchet.py` · `test_registry_dump.py`, `test_recipe_registration_order.py` |
| Lösen Namenslisten im Code auf und trägt jeder Eintrag bei (W6 a–e, g, h; e) liest auch Skripte in Zeichenketten)? Greift der Lebensdauer-Pin nach dem Import für jede Klasse (W6 f)? Trifft das Spulenverbot der Ersteinrichtung den echten Aufruf (CS-9a)? | `test_name_lists.py` · `test_suite_pin.py` · `test_first_run_spools.py` |
| Verschiebt das Werkzeug nur, und ist jeder Mutant des Beweises rot? | `test_move_names.py`, `test_move_names_forms.py`, `test_move_names_comments.py`, `test_move_names_queries.py`, `test_move_proof.py`, `test_move_copies.py`, `test_move_component.py`, `test_move_component_qt.py`, `test_move_component_receivers.py` — an Attrappen aus `move_fixtures.py` mit Sollbäumen von Hand; die zwei Komponentendateien prüfen Lebensdauer und Qt-Verhalten in eigenem Prozess mit QtCore, ohne Fenster |

## Helfer

`qt_roots.py` hält die ohne Elternteil gebauten Qt-Wurzeln eines Tests.
Einbindung: `from tests import qt_roots`, danach `roots = qt_roots.roots`.
Die Fixture schließt sie, merkt `deleteLater` vor und stellt `DeferredDelete`
zu, solange die Python-Hüllen noch gehalten werden; kein Querimport aus
`conftest`, keine zusätzliche globale Fixture.

`evaluation_helpers.py` teilt `window_evaluation` und
`short_chain_finds_nothing` zwischen `test_evaluation.py` und
`test_evaluation_container_chain.py`. Der erste Helfer wertet wie Fenster,
Verlaufsumbau und Agent in Entwurfsqualität mit voller Kette bei ergebnisloser
kurzer Kette aus; Vorschauen bleiben davon getrennt. Der zweite erzwingt die
Absage der kurzen und auf Wunsch auch der vollen Kette und meldet die
aufgerufenen Stufen. Das gemeinsame Wissen liegt unter öffentlichen Namen,
nicht in einem privaten Querimport zwischen Testdateien.

Die ausführlichen Zuordnungen der kompakten Karte:

| Ort / Frage | Vertrag |
|---|---|
| `helpers.py` | Gemeinsame, nicht fenstergebundene Helfer unter öffentlichen Namen (`exact_kernel`, `FakeMesh`, `FakeCodec`, `make_object`, `ridged_shaft`, `the_torus`, `CountingToken`, `stop_after`, `two_cubes`, `NavigationLog`, `SOURCE`, `rectangle`, `blind_cylinder`, `bore_seed`, `STUD_CENTRES`, `cube` für 3MF und `cube_surface` für Renderer …) und die Fixture `project`; keine privaten Querimporte aus `test_*.py` und nie aus `conftest` |
| `ui_helpers.py` | Qt-gebundene gemeinsame Helfer der Fenstertests: die Fixtures `window` und `session`, je Test frisch, eingebunden mit `from tests.ui_helpers import window as window`; dazu `shown_window`, `with_a_body`, `wait_until`, `wait_for_export` und Platzierungsfälle — jeder mit Zweck in `karte-tests.md`, „Helfer“ |

*HEAD-Fassung, früher unter „`conftest.py` tut vier Dinge, die leicht zu übersehen sind“.*

- Es setzt `QT_QPA_PLATFORM=offscreen` — Qt-Tests brauchen kein Bild.
- Es biegt **die Nutzerverzeichnisse in einen Temp-Ordner** um (§38), `HOME`
  eingeschlossen. Läuft ein Test außerhalb der Suite, fehlt ihm das, und er
  liest in Roberts echtem Profil.
  Je Prozess ein `solidon-tests-*`, beim Ende abgeräumt; Reste über einen
  Tag räumt der nächste Start.
- Es setzt **einen Schlüsselbund im Speicher** (`SuiteKeyring`) vor jedem
  Fall leer ein; ein Fall, der einen bestimmten braucht, ersetzt
  `keys._keyring` oder `device._load_keyring` per `monkeypatch`.
  Kindprozesse erreicht er nicht (eigene Isolierung mit `isolate_secrets`,
  Restpaket C).
- Unter `CI` beendet es den Lauf, wenn der exakte Kern fehlt
  (`pytest_sessionstart`, Muster `php_probe.py`): `build.yml` installiert das
  Extra `brep` in jedem Testlauf, und ohne den Kern übersprängen sich die
  Dateien des exakten Kerns still. Lokal bleibt ein fehlender Kern ein Skip —
  über `tests.helpers.exact_kernel()`, das **vor** jedem `OCP`-Import einer
  Testfunktion steht; `test_toolchain.py` prüft die Zusicherung.
- Mit `--ci-shard I/N` fährt es nur den Teil der Sammlung, den
  `tools/ci_shards.py` diesem Kernjob zuteilt — ohne den Schalter ändert
  sich an der Auswahl nichts.
- Die Fixture `native_window_platform` liefert Tests mit einem Fenster auf
  der echten Plattform im Kindprozess deren Qt-Plattform, nachdem
  `native_window_probe.py` je Prozess einmal ein leeres Fenster vorgezeigt
  hat (Muster `php_probe.py`: lokal Skip, in der CI nur auf dem Intel-Mac
  Skip, sonst rot). `pytest_terminal_summary` schreibt den Grund ans Ende
  jedes Laufs, unter GitHub zusätzlich als Anmerkung.

*HEAD-Fassung, früher unter „`helpers.py` — was mehr als eine Datei braucht“.*

Prüfkörper und Wächter, die mehrere Testdateien lesen, stehen in
`tests/helpers.py` unter öffentlichem Namen (`exact_kernel`, `ridged_shaft`,
`the_torus` und die Maße des Schafts), nicht als `from tests.test_x import
_privat` beim zufällig ersten Nutzer. Geteilte Fixtures stehen ebenso einmal —
`project` in `helpers.py`, `window` und `session` in `ui_helpers.py` — und
werden mit `from … import name as name` eingebunden; eine Datei, die eine
vorbereitete Sitzung braucht, überschreibt nur `session`. Aus `conftest`
importiert kein Test: pytest lädt es als Plugin, und ein zweiter Import führte
es noch einmal aus.

Die übrigen Helfer in `ui_helpers.py`: `shown_window` für ein gezeigtes Fenster
ohne Startbildschirm, `with_a_body` für die ausgewählte Korpusfigur,
`on_the_bore_wall` für einen Klick auf eine Bohrungswand, `wait_until` für
zugestellte Qt-Ereignisse, `wait_for_export` und `wait_for_print_findings` für
Arbeiter, die `wait_for_idle` nicht sieht, sowie `PlacementItem`,
`PlacementViewport`, `placement_layout` und `scene_with_a_hole_and_a_fillet`
für Platzierungsfälle. Für Maßkarten: `send_mouse_event` (Mausereignis mit
festem Bildschirmbezug), `begin_card_drag`/`end_card_drag`,
`settle_measure_layout` (Layoutaufträge zustellen, dann warten, bis keine
Seitenkarte mehr gleitet: `wait_for_resting_cards`, `cards_at_rest`; jeder
Schritt einer gleitenden Karte setzt die Maßkarte neu und kostet ein Bild,
FD-202) und `measure_more_heading`.

`release_signing.py` hält ein eigenes Schlüsselpaar der Suite für unterschriebene
Versionsdateien (`signed`, auch mit fremdem Schlüssel); die echten Schlüssel
(`REAL_PUBLIC_KEYS`) samt Abdruck des ersten und Besitzproben (`KEY_PROOFS`)
prüfen `test_the_published_version_file_is_signed` und
`test_the_shipped_release_keys_are_proven`.

`bundled_fonts.py` ist die eine Stelle für die gebündelte Prüfschrift: `bundled_font`
lädt DejaVu Sans (auf Wunsch weitere Dateien), setzt sie als Anwendungsschrift,
prüft Familie und echte Metrik und entfernt die Dateien danach wieder; Schrift
und Thema gibt `conftest.py` zurück.

`shell_helpers.py` ist die eine Stelle, die bash und sh der Suite sucht:
`bash_executable` (der Starter aus Git, mit `keep_path` die bash selbst, nie der
Starter von WSL) und `posix_shell` für das Linux-Installationsskript, beide mit
Rückfall neben Git, unter `ProgramFiles` und in der Installation je Nutzer. Es
lädt nur die Standardbibliothek. Dass keine Testdatei selbst per `which` sucht,
hält `test_packaging_platform.py::test_only_the_shell_helpers_look_for_bash_or_sh`.

`process_helpers.py` trägt `run_bounded`: wie `subprocess.run`, aber die
Zeitgrenze beendet den ganzen Prozessbaum (`process.start_bounded`,
`terminate_process_tree`). Wer die bash aus Git mit Zeitgrenze fährt, nimmt es
— der Starter `Git\bin\bash.exe` hat die Shell als Kind, und `kill()` ließ sie
weiterlaufen; mit `capture_output` wartete `subprocess.run` danach bis zu ihrem
Ende (CS-35).

`guide_window.py` gehört allein `test_guide_targets.py`: die Fixture
`prepared_window` für den Wortschatz des Funktionsdurchgangs (Quader mit
Bohrung unter dem Bett, im Kundenthema) und `settle`, das nach festen Runden
wartet, bis keine Seitenkarte mehr gleitet (`ui_helpers.wait_for_resting_cards`,
dieselbe Bedingung wie im Einschwingen der Maßkarte) — gelesen wird die Lage,
die der Kunde nach dem Gleiten sieht, nicht eine Zwischenlage, die an der
Rechnerlast hängt (FD-157).

`licence_states.py` gehört den Fenstertests der Sperre (`test_licence_lock_offers.py`,
`test_lock_reason_once.py`): `set_licence` stellt einen Freischaltzustand über
`tools.function_setup` her. Er stand in `ui_helpers.py` und zog das
Prüfstandswerkzeug in siebzig Fenstertestdateien (RA-9).

`hole_window.py` gibt den Fenstertests der Auswahlkarte ein Fenster mit
gewählter Bohrung in einer bestimmten Größe (`hole_window`) und `settle`, das
wartet, bis die Karte nach ihrer Öffnungsbewegung steht
(`test_feature_footer_window.py`, `test_feature_footer_low_window.py`,
`test_card_tab_chain.py`).

`test_font_follow_window.py` (FD-194): Ein Wechsel der Anwendungsschrift ohne
`apply_style` erreicht Stufen, Knöpfe und einen offenen Operationsdialog,
9 → 14 → 9 pt. `test_font_height_window.py` (FD-195): Dialoge mit
`ContentHeight` passen ihre Höhe dem Wechsel an, eine Größe des Kunden bleibt.
`test_header_font_window.py` (L1): Kopfzeile und Hauptleiste wählen ihre Form
nach dem Wechsel neu. `test_left_card_empty_sentences_window.py` (D1): Im neuen
Projekt sind die leeren Sätze der linken Karte in jeder Sprache so hoch wie ihr
Text, gemessen am Hauptfenster.

`window_leftovers.py` gehört dem Wächter `_no_window_outlives_its_test` in
`conftest.py` (FD-191): Ein Fall mit `qt_app`, der ein sichtbares Fenster
offen lässt, wird an sich selbst rot, nicht am nächsten im selben Arbeiter;
`close_after(request, …)` schließt ein gezeigtes Panel auch im Fehlerfall.
Sichtbarkeit wird über die Klasse gefragt, weil Fälle `isVisible` ersetzen.
Geprüft in `test_window_leftovers.py`.

`resize_watchdog.py`: `ResizeWatchdog` zählt die Größenänderungen eines Ausschnitts und verbirgt den Dialog über `RESIZES_PER_STATUS` — eine Größenschleife wird ein roter Fall statt eines Hängers (`test_generate_ui.py`, L3).

`plane_refusals.py` gibt `sketch_plane_refusal`: die echte Ebenenabsage einer
Skizzenoperation für `test_plane_refusal_field.py` und
`test_refusal_field_ways_window.py` (FD-182), statt eines privaten Helfers aus
`test_sketch_planes.py`.

`source_tree.py` liest Quelltext für die Quelltextprüfungen rekursiv, sortiert
und nie leer (`python_files("app/ui")`), meldet Pfade über `relative` und
findet die Datei einer Definition statisch (`definition_file`). Ordner stehen
relativ zu `ROOT`, und aufgerufen wird über das Modul
(`source_tree.python_files`): Die Gegenproben von W4 setzen `ROOT` auf eine
Kopie des Baums und müssen den Helfer selbst verfälschen können. Er steht
nicht in `helpers.py`, weil diese Datei selbst in der Sperrklinke steht.

`selection_trees.py` ist die eine Quelle der kleinen Bäume für
`test_affected_tests.py` und `test_affected_edges.py`: `write`, `names` und
`small_tree` (fünf Testdateien mit bekanntem Ausgang).

`packaging_helpers.py` hält, was beide Pakettests lesen: die Orte (`ROOT`,
`SPEC`, `WORKFLOW`), `workflow_shell` und `start_report`. Jede Testdatei
bindet die Orte per Import an ihr eigenes Modul, damit ein Patch über
`sys.modules[__name__]` genau ihre Wächter trifft. Dazu, was nur
`test_packaging.py` braucht und die Sperrklinke dort nicht mehr aufnimmt:
`as_tested` mit den Linux-Läufern und `stays_in_linux_bundle` — solange die
Datei gelistet ist, gehören sie nicht zurück.

`code_index_helpers.py` baut die Attrappen der Auflöser-Gegenproben
(`build_index`, `stored_index` über einem kleinen Grundbaum); `move_fixtures.py`
die des Verschiebewerkzeugs: je Modus ein Baum mit echten Paketformen, der
Zuschnitt und der von Hand geschriebene Sollbaum, den der Beweis annehmen und
jede gezielte Abweichung davon ablehnen muss.

`conftest.py` reicht die echten Fassungen der Attrappen als Fixtures weiter
(`unpatched_find_program`, `unpatched_find_programs`, `unpatched_backends`):
Wer genau die echte Programmsuche oder Backend-Liste prüft, fordert sie an,
nie ein Attribut am Produktmodul. Der Lebensdauer-Pin hängt beim Import an die
Klasse, die `UI_PINS` dem Modul zuordnet; fehlt sie, bricht der Import ab
(`test_suite_pin.py`). Die Datei ist zugleich `tests.conftest`.

## Stolperfallen

*Früher in der Karte unter „Stolperfallen“; dort stehen seither Kurzfassungen.*

- **Ungebundene Platzierungsdialoge und Viewport-Attrappen gehören der Fixture.**
  Nach `PlacementFlow.dispose()` und `Session.release()` schließt sie beide
  Qt-Wurzeln, meldet `deleteLater` an und stellt `DeferredDelete` zu, während
  die Python-Hüllen noch gehalten werden. `close()` allein zerstört sie nicht;
  ihr nativer Abbau darf nicht dem späteren zyklischen Sammler überlassen bleiben.
- **`tests.helpers.exact_kernel()` steht vor jedem `OCP`-Import**, auch am
  Modulanfang: Lokal wird ein fehlender Kern so ein Skip, unter `CI` hält
  `conftest.py` in `pytest_sessionstart` an, statt dass sich die Dateien des exakten Kerns still
  überspringen. Es importiert das eigene Kernelmodul regulär, damit dessen
  Importfehler nicht als fehlendes Extra verschwinden;
  `test_toolchain.py` prüft beides und, dass jeder `OCP`-Import in einer
  Testdatei oder `helpers.py` lexikalisch hinter einem Aufruf steht, auch
  in Helfern, die bisher nur geschützte Tests rufen.
- **Testdateien importieren keine privaten Namen voneinander.** Gemeinsame
  Daten und Konstruktoren liegen unter öffentlichen Namen in `helpers.py`
  oder passenden kleinen Helfermodulen; der AST-Wächter samt Gegenprobe steht in
  `test_toolchain.py` und prüft auch eingebettete Python-Skripte für
  Kindprozesse.

*Früher unter „Die Fahrweise steht einmal — in `CLAUDE.md`“.*

- `test_widget_lifetime.py` ordnet `installEventFilter(self)` seiner
  umgebenden Klasse zu und prüft deren eigenen `eventFilter` auf den
  Abmeldegriff. Ein anderer Filter in derselben Datei erfüllt diesen Vertrag
  nicht.
  Bei modalen Hauptfensterdialogen prüft die Datei zuerst die native
  Kindlöschung bei weiterhin gehaltenem Elternfenster. Erst danach beendet
  der gemeinsame Qt-Abbau den Fensterbaum; schwache Verweise auf Fenster
  und Dialoge müssen anschließend sämtlich leer sein. `release()` allein
  ersetzt die native Fensterlöschung nicht.
- `test_suite_script.py` prüft die Halbierung des geteilten Laufs mit echten
  Shell-Prozessausgängen und simulierten pytest-Aufrufen, einschließlich 256
  gezählter Fehler: Erfolgreiche kleinere Teilstücke löschen den
  ursprünglichen Prozessabbruch nicht, der Gesamtlauf endet mit Exit 1.

*Früher unter „`helpers.py` — was mehr als eine Datei braucht“.*

Wer `WorkerLeash.start` durch eine Testfunktion ersetzt, übernimmt den Abbau
der echten, absichtlich nicht gestarteten Worker. Ein lokaler Finalizer löst
deren `release_finished_references()`, merkt `deleteLater()` vor und stellt
`DeferredDelete` zu. Nur ein Fensterfeld zu leeren reicht nicht: Die Leine hat
diese Worker nie registriert. Der vollständige Qt-Abbauvertrag steht in
`.claude/rules/wartezeit.md` unter „Loslassen allein räumt nicht auf“.

## Sprache in diesem Verzeichnis

Nicht mehr in der Karte: Die Regel steht in `AGENTS.md` (Sprachregelung,
„Die Bezeichnerregel gilt `app/` und `tools/`“).

*HEAD-Fassung, früher unter „Sprache in diesem Verzeichnis“.*

**Hier gilt der Bestand der Datei, nicht die Bezeichnerregel.** `app/` und
`tools/` reisen zum Kunden, `tests/` liest nur, wer hier arbeitet — deshalb
prüft `test_language_rules.py` genau jene zwei Verzeichnisse und dieses nicht.

Gezählt am 23.08.2026: 78 deutsche Bezeichner in 27 Dateien. Sie werden
**nicht** umbenannt — eine Massenänderung in fremden Dateien kostet mehr, als
sie einbringt. Assert-Meldungen bleiben ebenfalls beim Bestand der Datei.
