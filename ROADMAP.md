# ROADMAP — Arbeitsliste

Der ursprüngliche Bauplan-Abgleich vom 08.09.2026 und seine Fortschreibungen stehen im
[Archiv](ROADMAP-ARCHIV.md). Der Veröffentlichungsstand ist **0.5.1**, veröffentlicht
am **28.09.2026** (`website/version.json`, `1f5dc9f43`). Der Tag `v0.5.1` zeigt auf
`585869a2c`; der [Taglauf 36454861126](https://github.com/RS-Digital-Studio/Solidon/actions/runs/36454861126)
ist erfolgreich abgeschlossen. Die Website bietet Windows-Setup, Linux-AppImage,
Linux-Flatpak und die beiden Mac-Pakete an. Die offenen Aufgaben darunter führen ihre verbleibende
Arbeit oder Abnahme; ein veröffentlichter Build ersetzt keinen Feldnachweis.

Legende: `[ ]` offen · `[~]` teilweise umgesetzt, Abnahme oder Restarbeit offen ·
`[x]` mit dokumentiertem Nachweis abgeschlossen. Ein historischer Haken ist
kein Nachweis für ein grünes Tor auf dem heutigen Stand.

Die Phasen zeigen den erreichten Umfang; die Aufgaben darunter nennen den
heutigen Rest. Jede Aufgabe hat eine feste Kennung. Register und Punkt werden
gemeinsam gepflegt; abgeschlossene Aufgaben wandern mit ihrem Nachweis ins
Archiv. Fehlende Feldabnahmen bleiben offen, auch wenn der Code bereits steht.
Der [vollständige Bauplan-Abgleich](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026)
schließt RM-089 ab; seine acht neu zugeordneten Restverträge stehen bei RM-138 bis RM-145.

Priorität: Kundenabstürze und blockierte Hauptwege, danach falsche Ergebnisse
und Bedienfehler, danach Ausbau und interne Verbesserungen. Fristgebundene
Auflagen werden daneben rechtzeitig bearbeitet. **Als Nächstes:** die nach 0.5.1
zurückgestellten Kundenfehler, zuerst die blockierten Modell- und Slicerwege.
Daneben bleiben die Mac-/Linux-Nachweise, die Absicherung der Releaseakte und die
CRA-Betriebsvorbereitung offen — deren Frist ist am 11.09.2026 **abgelaufen**, die
Meldepflicht aus Art. 14 gilt seither (RM-091). Eine zurückgestellte
Produktentscheidung oder ein kostenpflichtiger Lauf wird durch diesen
Abgleich nicht freigegeben.

## Was offen ist

Jede Zeile führt zu genau einem offenen Punkt. Die letzte Spalte nennt den nächsten Schritt; Begründung und Abnahme stehen am Punkt.

| Punkt | steht unter | wartet auf |
|---|---|---|
| [CI-Testlaufzeiten — vollständige Prüfungen früher abschließen](#ci-testlaufzeiten) | Tests und Entwicklungswerkzeuge | CI-01 bis CI-07 im Code belegt; die neue Aufteilung ist im erfolgreichen Taglauf 36454861126 von 0.5.1 gelaufen. Offen bleiben CI-08 mit vergleichbarer Vorher-/Nachher-Auswertung des Testbestands und der Laufzeiten sowie das Blättern in `tools/windows_signed_installer.py` |
| [RM-184 — Dateiaudit vollständig umsetzen](#rm-184) | Geometrie, Erkennung und Druckvorbereitung | Acht Bausteine und sieben Abläufe aus dem Audit gebaut (04.10.); offen: funktionale Gruppen, Projektmaße und das Werkzeug für die native Einzeldateiabnahme (in Arbeit), danach die Abnahme der 187 Fälle und die Fensterabnahme beim Release |
| [RM-011 — Erstinstallation auf einem fremden Rechner abnehmen](#rm-011) | Plattformen, Pakete und Grafik | Fremdrechner ohne Entwicklungsumgebung von Download bis Export prüfen |
| [RM-021 — Native Fensterlebensdauer am aktuellen Renderer abnehmen](#rm-021) | Plattformen, Pakete und Grafik | Der Riss in `test_ui.py` Teil 4 ist bis auf `processEvents` im Teardown eingegrenzt und trifft die Anwendung nicht; offen ist der Ereignistyp dahinter und die Gegenprobe auf Linux und Mac |
| [RM-050 — Kopierkosten messen und verbleibende VTK-Geometrie ablösen](#rm-050) | Plattformen, Pakete und Grafik | VTK ist ausgebaut (`5a57e261`), die Wandmessung verwendet den eigenen Strahltest. Matplotlib ist seit `9bb1542b` wieder Laufzeitabhängigkeit; die Windows-Lizenzbeilage enthält 50 Komponenten. Offen bleiben die kopierten Bytes und Pufferkosten je großer Szene, gemessen am Fenster; die Bereichsprüfungsreste sind mit RM-214 geschlossen (Durchsicht 0.5.1) |
| [RM-051 — Renderer und Grafiklaufzeit in Linux- und Mac-Paketen abnehmen](#rm-051) | Plattformen, Pakete und Grafik | Grafik und Eingabe der veröffentlichten 0.4.0-Pakete für Linux und Mac abnehmen |
| [RM-055 — Neue Paketwerkzeuge im installierten Kundenpaket abnehmen](#rm-055) | Plattformen, Pakete und Grafik | Installerlauf 36467614477 von 0.5.1 belegt Inno Setup 7.1.0 und den Signierprüfschritt bei abweichendem Commit (188 Tests). Offen bleiben der Flatpak-Lauf auf echter Linux-Grafik und Installieren/Aktualisieren/Deinstallieren auf fremdem Windows |
| [RM-104 — Verbleibende Mac- und Unix-Befunde mit aktueller CI-Abdeckung abnehmen](#rm-104) | Plattformen, Pakete und Grafik | Intel-Hänger auf dem Runner zugeordnet (Symboldienst stürzt in Metal ab, Befund am Punkt); offen Intel-Fenster am echten Gerät und die übrigen Unix-Fenster-/Export-/Chatfälle |
| [RM-107 — Ubuntu-Workerabbruch mit aktuellem Testbestand zuordnen](#rm-107) | Plattformen, Pakete und Grafik | Auslöser mit aktueller Testreihenfolge und Widget-/Worker-Lebensdauer eingrenzen |
| [RM-114 — Vereinfachungsziele auf Apple Silicon vermessen](#rm-114) | Plattformen, Pakete und Grafik | Der Test überspringt nicht mehr, ein sicher offener Ausgang löst die Warnung auf jeder Plattform aus (`a559e947`); offen bleibt die Zielreihe der Hohlkugel auf einem Mac |
| [RM-187 — Dieselbe Geometrie auf jeder Plattform](#rm-187) | Plattformen, Pakete und Grafik | Fingerabdrücke auf den drei Runnern; plattformgleich machen: Einpassungen in `perceive`, `shapes.thread_body`, den Teilungsweg über BLAS, die Drehwege von *Merkmal drehen* und das Einsetzen eines Bausteins (Liste am Punkt) |
| [RM-468 — CPython 3.14.8 bringt Sicherheitskorrekturen in die ausgelieferte Laufzeit](#rm-468) | Plattformen, Pakete und Grafik | CI baut mit 3.14.8, Lizenzbeilage nachgezogen, Kernsuite auf drei Systemen wie main; offen der Paketbau auf vier Plattformen (wartet auf grüne Fensterjobs) und die drei Arbeitsplätze |
| [RM-469 — rubicon-objc 0.5.7 wartet auf den Mac-Paketbau](#rm-469) | Plattformen, Pakete und Grafik | Pin gehoben, Kernsuite auf macOS wie main; offen beide Mac-Paketjobs und die Ansicht im gebauten Paket |
| [RM-017 — Nutfedermaße an realen Aluminiumprofilen prüfen](#rm-017) | Geometrie, Erkennung und Druckvorbereitung | Robert 04.10.: Der STEP-Nachweis genügt, eine gedruckte Probe entfällt; Suche nach Nutenstein und T-Nut gebaut. Offen allein das Wiederöffnen am Fenster beim Release (RM-213) |
| [RM-022 — Nachbau als Operationsfolge](#rm-022) | Geometrie, Erkennung und Druckvorbereitung | Zapfen mit Kehle am Netz, Winkel mit Querbohrungen, Kehlen, runde Ecken und Senkungen als Skizze plus Extrusion und Bohrung nachgebaut, Formvergleich je Teilung sieben statt sechzehn Punkte (Lochplatte 13,2 → 5,7 s); offen allein die Fensterabnahme beim Release (RM-213) |
| [RM-188 — CAD-Ausbau, Bedienung und Resin für 0.5.x](#rm-188) | Geometrie, Erkennung und Druckvorbereitung | Nächster Schritt P0.8: die vier Konzepte je Anforderung dem Code oder einem Paket zuordnen; daneben P4.1 unter RM-022, P8.1, P9.1 und Zeichnen Z2. Reste der gebauten Pakete und Fragen an Robert stehen am Punkt; Abschluss mit P5.3 |
| [RM-191 — PrusaSlicer verbraucht für dieselbe Übergabe ein Drittel mehr Material](#rm-191) | Geometrie, Erkennung und Druckvorbereitung | Nachgemessen am Gewürzregal (`56f70000`): Material innerhalb von 3 %, Zeit Prusa 1,93× Orca — behoben bis 1,19× (volle Füllung und Lückenfüllung für Prusa und Orca, Bahnbreite je Orca-Rolle, `machine_limits_usage = ignore`); der Rest ist die Bauweise des Slicers (Füllanker, Zusatzwände) — ob Solidon dort Vorgaben setzt, entscheidet Robert |
| [RM-209 — Die Rundform-Einpassung an Gittermodellen](#rm-209) | Geometrie, Erkennung und Druckvorbereitung | Stapelumbau (0.5.1) und bitgleiche Vektornorm im Löser gebaut; Kumiko-Schale 18,6–20,2 s unter Last, §31 (unter 5 s) nicht erreicht; offen: Aufbereitung großer Flecken und Fits beschleunigen, danach ruhige Vergleichsläufe |
| [RM-132 — Freiformerkennung am Ein-Sekunden-Ziel messen](#rm-132) | Geometrie, Erkennung und Druckvorbereitung | Stapelumbau (0.5.1) und bitgleiche Vektornorm im Löser gebaut (3–10 % Löserzeit), an der Freiform ohne Wirkung aufs Ziel (7,2 s unter Last bei null Merkmalen); offen: anderer Hebel oder neu gefasstes Ziel |
| [RM-166 — Ergebnisnetze aus Mesh-Ops an einer STL überstehen keinen Weld](#rm-166) | Geometrie, Erkennung und Druckvorbereitung | Die Werkzeuge und der Eckanschluss rechnen plattformgleich (`9bc3d354e`, Ecke in `test_platform_identity._WAYS`); offen allein die Marke `xfail(linux)`, die nach drei grünen Linux-Läufen in Folge fällt, und das Beispielarchiv der Werkstattfilme mit der nächsten Filmrunde |
| [RM-193 — Die Erkennung an einer glatten Generator-Freiform kostet Minuten für null Merkmale](#rm-193) | Geometrie, Erkennung und Druckvorbereitung | Stapelumbau (0.5.1) und bitgleiche Vektornorm gebaut, Hautregel samt Schutz der Grundformen geprüft; der Drache braucht 6,9–9,0 s unter Last bei null Merkmalen; offen: anderer Hebel oder neu gefasstes Ziel |
| [RM-201 — Ein hohler Körper hält die 300 ms der Schichtanalyse nicht](#rm-201) | Geometrie, Erkennung und Druckvorbereitung | Unabhängige Clipper-Säulen, gerichtete Verschachtelung und `ring_nesting` gebaut, Hohlkugel bitgleich in 1,2–1,4 s; Mitre-Öffnung über Clipper und Zertifikate gemessen und verworfen; 300 ms verfehlt, ob ein weiterer Hebel kommt oder §31 für Schalen neu gefasst wird, entscheidet Robert |
| [RM-217 — Die Zuordnungsfrage zeigt das alte Merkmal nicht im Bild](#rm-217) | Geometrie, Erkennung und Druckvorbereitung | Altmerkmal und Kandidat werden gemeinsam markiert; Kern-, Ansichts- und Regressionstests grün. Offen: echter Fensterbeleg im Release unter RM-213 |
| [RM-218 — Bohrungskennungen beim Umbau des exakten Verlaufs erhalten](#rm-218) | Geometrie, Erkennung und Druckvorbereitung | Namensparser und alle sechs echten Passungs-/Umbau-/Undo-Fälle unabhängig freigegeben; zentrales Tor und Übernahme offen, Fensterabnahme im Release |
| [RM-230 — Variable Verrundung und Formschräge: fünf Grenzen, die der Kunde merkt](#rm-230) | Geometrie, Erkennung und Druckvorbereitung | Anfang auf Ringen fest, gemischte Ecken exakt ungeprüft, Zwischenstellen nicht bindbar, Schräge an allen Wänden des Trays abgesagt — je Grenze bauen oder benennen |
| [RM-253 — Am Laptop-Ständer tragen Kippen und Verdoppeln einer Bohrung falsch ab](#rm-253) | Geometrie, Erkennung und Druckvorbereitung | Sicherheitskorrektur: Eine notwendige Vorvereinigung, die an einer selbstkreuzenden Schale scheitert, hält jetzt vor dem Solver an und bindet den Fehler an den betroffenen Körper. Am Original sind 1 243 aktuelle Schnittpaare belegt. Blenders exakter Boolean verschlechtert die Topologie; der 0,2-mm-Voxelremesh überschreitet `MAX_FACET_SAG`. Geometriereparatur und ursprüngliche Abnahme bleiben offen. |
| [RM-247 — Die Waschschüssel ließ sich nach Solidons Übergabe nicht drucken](#rm-247) | Geometrie, Erkennung und Druckvorbereitung | Kanaldecken, Gitter als Gitter, Leerfahrt und Tempo vom Drucker, Kanalsperre je Slicerfamilie, Brim auf Füßen — gebaut und im ElegooSlicer und PrusaSlicer belegt; offen: Probedruck am Centauri |
| [RM-281 — Die Übergabe auf dem Herstellerprofil: Stufen C bis F](#rm-281) | Geometrie, Erkennung und Druckvorbereitung | A bis F, K und L stehen und sind im Slicer abgenommen (C `44ab90965`, E `83a8e3de1`, F `d4dd5332b`, K `f1a1fba65`, L `e0e3cf982`); offen Paket 3 und der Lauf „jedes Modell × jeder Slicer“ |
| [RM-259 — Eine Mündungsrundung in einer gekrümmten Fläche reist nicht mit ihrer Senkbohrung](#rm-259) | Geometrie, Erkennung und Druckvorbereitung | In einer ebenen Fläche gebaut (`202d5133a`: Versetzen ±0,000 mm³, Entfernen genau die Platte, beide Kerne); gekrümmt offen: am Netz die Senkung hinter einer Rollkugelrundung erkennen und eine Fläche aus mehreren Grundformen über die Öffnung fortsetzen, am exakten Kern den Prototyp `m19_exakt_band.py` samt Bandkennung übernehmen. Abnahme neu gegen den Sollwert −2,97 / +0,29 / −4,56 mm³ an gs-100 |
| [RM-262 — Die Erkennung liest eine gekippte Haltelippe nicht](#rm-262) | Geometrie, Erkennung und Druckvorbereitung | Die Absage bleibt (rest-muendung): Mit dem Drehweg liest der exakte Kern Tasche, angeschnittenen Kegel ohne Verengung und Schacht als Zylinderstück, das Netz nur eine gerundete Seite. Erst beide Erkennungen und `bore_entrance` mit schräger Mündung hinter einer Verengung, dann *Merkmal drehen* freigeben; der Drehweg liegt auf heutigem Stand als `prepare_ops_mit_drehen_heute.patch` bereit |
| [RM-292 — Laufzeitreste der Durchsicht 0.5.1](#rm-292) | Geometrie, Erkennung und Druckvorbereitung | (b) Eigenkreuzung endet beim ersten Gegenbeleg (Besenhalter 18,4 → 14,6–15,1 s, Laptop 26–28,6 → 20,1–20,9 s unter Last, Paare bitgleich), (c) ohne zweite Vereinigung gebaut; offen: (a) beim Öffnen am Fenster zuordnen, (b) lastfrei messen und mit Ziel führen |
| [RM-296 — Die genaue Vorschau großer Teile rechnet am ganzen Körper](#rm-296) | Geometrie, Erkennung und Druckvorbereitung | Bekannte Durchgangswand misst örtlich nach, die letzte Vorschau erkennt nur noch den Folgebedarf; Senkplatte im Sitzungsweg 7,6/4,6/3,5 s (Ø 6/6,5/7, unter Last); offen: unter 3 s auf ruhiger Maschine |
| [RM-298 — Hilfsprozess: Reste aus dem Review](#rm-298) | Geometrie, Erkennung und Druckvorbereitung | Pool/aktive Windows-Bindung und OS-Priorität auf origin/main; Messmarken vorbereitet und mechanisch geprüft; Release-/Plattformnachweise und b–f offen |
| [RM-307 — Auto Split: Reste aus dem Review der Vorauswahl](#rm-307) | Geometrie, Erkennung und Druckvorbereitung | Native Vorauswahl `orientation_scores` bitgleich zur NumPy-Fassung, Stützraum am Suchnetz mit Stand am Original, Stand an den Toleranzrändern geprüft; T2 im Messfenster nativ 14,7–19,7 s, ohne Kern 16,5–23,4 s unter Fremdlast; offen: lastfreie Messung beider Wege und Nachweis zu (a) |
| [RM-322 — Tragende Netzkanten am exakten Körper wiederfinden](#rm-322) | Geometrie, Erkennung und Druckvorbereitung | Zweitreview und Entwicklungstor mit 19.464/62 grün; alle 17 Pfade in `0041000a0` übernommen und unabhängig abgeglichen; Pushbeleg offen |
| [RM-327 — Der Zerfallssatz einer Bohrung verschwindet, sobald sich die Teilezahl ändert](#rm-327) | Geometrie, Erkennung und Druckvorbereitung | 155 gezielte Fachfälle grün; Code und Dokumentation unabhängig freigegeben; gemeinsames Tor und Hauptzweigübernahme offen |
| [RM-365 — *Festschreiben* einer Formsitzung friert das Entwurfsnetz ein](#rm-365) | Geometrie, Erkennung und Druckvorbereitung | In Arbeit: Claude (Worktree `F:/solidon-claude-r`). Review 02.10. (Weg 4): beim Festschreiben in feiner Qualität rechnen; Test Dreieckszahl und Volumen |
| [RM-381 — Boolesche Ops an mehrschaligen Modellen sind seit `eab5f4f47` 8- bis 15-mal langsamer und nicht abbrechbar](#rm-381) | Geometrie, Erkennung und Druckvorbereitung | In Arbeit: Claude (Worktree `F:/solidon-claude-p`). Review 02.10.: Kandidaten über räumlichen Index, Deckel mit Befund, `cancelled` durchreichen; Zeitmessung Besenhalter |
| [RM-382 — Ein Mehrschaler mit einer selbstkreuzenden Schale lässt sich seit `eab5f4f47` gar nicht mehr bearbeiten](#rm-382) | Geometrie, Erkennung und Druckvorbereitung | In Arbeit: Claude (Worktree `F:/solidon-claude-p`). Review 02.10.: Entscheidung Robert, ob nur gehalten wird, wenn das Werkzeug die kaputte Schale berührt; Kennung und Satz mit Grund |
| [RM-383 — Über 256 Schalen hält jede Boolesche, auch an getrennten Teilen](#rm-383) | Geometrie, Erkennung und Druckvorbereitung | In Arbeit: Claude (Worktree `F:/solidon-claude-p`). Review 02.10.: getrennte Teile ohne Berührung weiterrechnen, Halt mit Kennung und passendem Rat |
| [RM-385 — Reste aus dem Review von `eab5f4f47` und `a45730c79`](#rm-385) | Geometrie, Erkennung und Druckvorbereitung | In Arbeit: Claude (Worktree `F:/solidon-claude-p`). Review 02.10.: exakter Rat, `parts_united` am exakten Kern, Tests auf Wirkung, Unterlagen nachziehen |
| [RM-402 — Kreismuster um einen gewählten Körper statt um den Weltursprung](#rm-402) | Geometrie, Erkennung und Druckvorbereitung | Drehmitte für Kreismuster, Merkmalsmuster und Spiegeln aus Körper, Merkmal, Punkt oder Ursprung gebaut, im Schritt gespeichert, Altprojekte per Migration unverändert; offen: drei Modelle am Fenster beim Release (RM-213), zwölf Sollprojekte liegen bereit |
| [RM-405 — Die volle Schichtanalyse reißt §31 um Faktor 35–60; drei belegte Ursachen](#rm-405) | Geometrie, Erkennung und Druckvorbereitung | (a) `cuts_along` im Cythonkern, (b) mit RM-486 und unabhängigen Säulen, (c) Kanalfrage und Schichtansicht über den Merker gebaut; F0FF je zweimal bitgleich, Screen-Cover 0,7–0,9 statt 3,4–3,8 s, CC2-Box 5,1–5,5 statt 40,7–41,5 s; offen: Schichtansicht am Fenster beim Release (RM-213) |
| [RM-410 — Die schnelle Orientierung rechnet am vollen Netz und ist an großen Baugruppen langsamer als die gründliche](#rm-410) | Geometrie, Erkennung und Druckvorbereitung | Schnelle Ausrichtung prüft den Bauraum erst am betrachteten Kandidaten und teilt gleiche Formen, Gewinner unverändert; chufang schnell 65–68 statt 161 s, gründlich 150 s, beide unter Fremdlast; offen: lastfreie Vergleichsmessung an chufang und zwei Baugruppen |
| [RM-413 — Reste aus dem Review von `57848fa72` und `e3dff1907`](#rm-413) | Geometrie, Erkennung und Druckvorbereitung | Review 02.10.: toter Code, abgelöster Merkmalarbeiter, doppelter Builder, falscher Absagegrund, Regel nicht nachgezogen |
| [RM-434 — Das Entwurfsbudget von Weich verschmelzen übergeht die Eingangsprüfung](#rm-434) | Geometrie, Erkennung und Druckvorbereitung | Eingangsprüfung vor Bounds/Budget korrigiert; 24 Fachfälle und gezieltes Mypy grün, Code unabhängig freigegeben; Tor und Übernahme offen |
| [RM-425 — Überlappende gespiegelte Formzüge verlieren ihre Symmetrie](#rm-425) | Geometrie, Erkennung und Druckvorbereitung | S01 aus dem Review von `48106c57a`: Spiegelrichtungen gemeinsam begrenzen; alle Achsen/Pinsel, drei Körper und alter gespeicherter Verlauf |
| [RM-419 — Die neue Durchstichprüfung macht den Formschritt bis 130-mal langsamer](#rm-419) | Geometrie, Erkennung und Druckvorbereitung | In Arbeit: Claude (Worktree `F:/solidon-claude-r`). Review 02.10.: Folge zu RM-364 (archiviert); Schnittsuche nur um die bewegten Ecken, mit Fortschritt |
| [RM-428 — Spiegelzug nahe der Ebene: Kerbe, verlorene Spiegelgleichheit, doppelte Laufzeit](#rm-428) | Geometrie, Erkennung und Druckvorbereitung | In Arbeit: Claude (Worktree `F:/solidon-claude-r`). Review 02.10.: Folge zu RM-378 (archiviert); geglättete Gewichtung statt Maximum, symmetrische Entscheidung, Laufzeit |
| [RM-454 — Ein Spiegelzug kann die verformte Fläche erreichen und trotzdem wirkungslos bleiben](#rm-454) | Geometrie, Erkennung und Druckvorbereitung | In Arbeit: Claude (Worktree `F:/solidon-claude-r`). Quellenreview der parallelen Claude-Lieferung `105b2ba0d`: Etappenentscheidung berücksichtigt Spiegelorte nicht; Gegenfall noch auszuführen |
| [RM-504 — Importierte Texturen als gemeinsame Auswahl](#rm-504) | Geometrie, Erkennung und Druckvorbereitung | Zusammenfassung kleiner Felder und STEP-Muster gebaut und belegt (04.10.); offen allein die Fensterabnahme beim Release (RM-213) |
| [RM-496 — Reale Modelle laden im Prüfstand fast doppelt so lang wie in v0.5.1 — am echten Fenster nachmessen](#rm-496) | Geometrie, Erkennung und Druckvorbereitung | Versionsvergleich 02.10.: Verdacht gegenüber v0.5.1 (nachgeholte Importe 2,2 s, Erkennung 1,4 s); Startweg mit Vorwärmen messen |
| [RM-070 — SpaceMouse auf macOS und Linux am echten Gerät abnehmen](#rm-070) | Bedienung und Darstellung | Die Rampe ist stetig und getestet, die Bildrate an 815 104 Dreiecken gemessen (`7ff34c67`: 16,7 → 8,7 ms im Median); offen bleiben Linux, die 3DxWare-Mausemulation, das Gerät selbst und die Rampe im Skizzenmodus (aus RM-183) |
| [RM-204 — Ein Merkmalklick baut alle Handlungen des Fensters neu](#rm-204) | Bedienung und Darstellung | Abnahme am echten Fenster beim Release (RM-213) |
| [RM-283 — Ein Handbuch, das man ohne Ausprobieren versteht](#rm-283) | Bedienung und Darstellung | Nummernplatzierung gebaut: `make_guides` meidet Text in Fenster, Menüs und Dialogen und setzt die Nummer bei vollem Dialog in den Bildrand; offen: Feldabnahme nach §11 mit einem Kunden ohne CAD, dazu die Anleitungsbilder beim Release neu erzeugen und Schritt 3 beider Anleitungen ansehen |
| [RM-183 — Zeichenmodus am Fenster abnehmen](#rm-183) | Bedienung und Darstellung | Rampe der 3D-Maus am echten Gerät; ob dieser Rest in RM-070 aufgeht und der Punkt damit schließt, entscheidet Robert |
| [RM-084 — Kundentexte gegen die vereinbarte Sprache prüfen](#rm-084) | Bedienung und Darstellung | Kataloge EN/ES/PT/FR/IT durchgesehen (04.10.), die gemeldeten Fehler der deutschen Quelle behoben (871cc29e6); offen: Handbuch und Assetstempel beim Release, Fensterabnahme der längeren Knopfnamen (RM-213) |
| [RM-090 — Gemeinsamen Vertrag für die fünf Produkterlebnisse umsetzen](#rm-090) | Bedienung und Darstellung | Gegenprobe liest Export- und Slicerdateien zurück, Nebenfolge je Handlung aus dem Kern, Folge je Befund, Kandidatenprüfung nennt nur Neues und Behobenes, NM 1–11 ohne Fenster belegt; offen allein die Fensterabnahme beim Release (RM-213) |
| [RM-131 — Zurückgestellten Mehrfachimport entscheiden](#rm-131) | Bedienung und Darstellung | Bündel enthaltener Teile, Dialogabbruch, *Modell einfügen*, abgelehnte Erkennungsfrage und Gestensperre ohne Fenster belegt; offen allein die Fensterabnahme beim Release (RM-213) |
| [RM-135 — Zugewiesene Höhe der Filamentkarte vollständig nutzen](#rm-135) | Bedienung und Darstellung | Windows-Stand nachgemessen am 23.09.2026 (Overlay- und Kartentests grün); offen nur der macOS-Prüflauf |
| [RM-136 — Gezeichnetes Fensterschema und Bildbeschreibungen aktualisieren](#rm-136) | Bedienung und Darstellung | Fensterschema in sechs Sprachen gegen Generator und Alttexte geprüft, lange Berichtstitel brechen jetzt um (12 SVG neu); offen: Handbuchseiten und PDFs beim Release neu erzeugen |
| [RM-197 — Maßeditor im Bild: kein Bezugswechsel am Etikett, Beschriftungen mit Abstand zum Modell](#rm-197) | Bedienung und Darstellung | Große Fachkarte verdrängt die Maße nicht mehr, der Griff sitzt an der Mündung, beides am Fenster gesehen (64 Fälle); offen: der übrige Abnahmeweg am Fenster beim Release (RM-213): Langlochknöpfe, Zug mit Kamera, verschluckte Maßlinie, Stufe an der Grenze |
| [RM-198 — Eine feine Fenstermaske über der Vulkan-Fläche verliert das Gerät](#rm-198) | Bedienung und Darstellung | Probe über den echten Startweg beim nächsten Release (RM-213); D3D12 als Backend ist eine eigene Entscheidung |
| [RM-199 — Der Durchmesser steht doppelt: im Bild und rechts im Auswahlfenster](#rm-199) | Bedienung und Darstellung | Beim ursprünglichen Bohrschritt weichen auch *Bohrung ändern* und *Zum Langloch ziehen* (7 Fälle); am Fenster steht der Durchmesser nur noch in der Maßkarte; offen: Rückkehr der Felder nach dem Ende der Maßgruppe am Fenster beim Release (RM-213) |
| [RM-200 — Ein Zug am Griff soll flüssig sein](#rm-200) | Bedienung und Darstellung | Am echten Fenster prüfen, ob sich die Geste flüssig anfühlt (Release, RM-213) |
| [RM-213 — Fensterabnahme und die Kundenwege am echten Fenster](#rm-213) | Bedienung und Darstellung | Beim Release: die offscreen belegten Änderungen am echten Fenster, die Kundenwege C14/A13/A4/C5/C1 und die vier Hauptwege mit Zeiten; Fensterwache an jedem Bildgriff und C14 im Code gebaut, ihre Fensterproben gehören dazu; vorher Release-Tor mit allen neuen Fensterdateien und frischem Bereichsnachweis |
| [RM-232 — Die Klickkette an einem Merkmal rechnet noch im Hauptfaden](#rm-232) | Bedienung und Darstellung | Doppelter Rollenlauf, 96 Sichtbarkeitswechsel, ein zusätzlicher Bildauftrag und ein verspäteter Hover-Neuaufbau entfernt (139/347 Fälle); am Fenster Baumklick 87–94 ms, Bildklick vor dem Hover-Fix 105–146 ms; offen: Abnahme unter 100 ms auf ruhiger Maschine am MSI |
| [RM-258 — Zwei einmalige Stillstände beim Einlesen großer 3MF](#rm-258) | Bedienung und Darstellung | Übernommen: Claude, Thread „Bedienung und KI“. Ursache behoben (0.5.1, Paket 3mf); offen zwei einmalige Stellen über 200 ms je Import: erstes Bild der Arbeitsfläche, Rückfrage zur Vollerkennung |
| [RM-285 — Feste Doppelpunkte hinter übersetzten Teilen](#rm-285) | Bedienung und Darstellung | UI/CLI/Bereichsprüfer auf origin/main integriert; dauerhafte Nachweise und Modelltext-Restliste vorhanden. Modellabnahme offen |
| [RM-312 — Die Düsengröße im Druckdialog kommt vom Drucker und ist eine Auswahl](#rm-312) | Bedienung und Darstellung | Düsenwahl mit 8374885ae integriert; Matrix abgeschlossen: 125 Aufträge, 124 Modelle mit Varianten, 426 Variantenfehler und 149 Ausgaben mit Fehlerbefund. Fehlerklärung und Release-Fensterabnahme offen |
| [RM-366 — Die Vorschau der Formsitzung rechnet die ganze Sitzung im Oberflächen-Thread nach jedem Zug](#rm-366) | Bedienung und Darstellung | Vorschau je Klick nur mit dem neuen Zug auf main (`8440db6f7`), große Netze rechnen im Arbeiter; die 40. Vorschau ist nicht länger als die erste, UI-Aufruf 0,6 ms; offen: Messung am echten Fenster auf ruhiger Maschine beim Release (RM-213) |
| [RM-368 — Schieberegler über den Verlauf (§18.7)](#rm-368) | Bedienung und Darstellung | „vor Schritt 3“ und alle Schrittsätze sprechen in sichtbaren Stellen statt Kennungen (Absage beim Verschieben, Löschnachfrage, Löschtitel, Umbauabsagen, Merkmalsfrage); offen allein die Fensterabnahme beim Release (RM-213) |
| [RM-375 — Eine Formsitzung lässt sich wieder öffnen](#rm-375) | Bedienung und Darstellung | Formen, Skelett und Zeichnen öffnen ihren Schritt wieder, ein Zug ist eine ganze Geste mit lokalem Undo; an Figur und Pilz am Fenster geprüft; offen: drittes Modell (Drache), Themen, schmale Fenster und Projektwechsel am Fenster beim Release (RM-213) |
| [RM-377 — Überhangkarte, Bauraum und Druckbefund laufen in der Formsitzung mit](#rm-377) | Bedienung und Darstellung | Wand- und Überhangkarte mit Legende, Bauraumhinweis und Druckbefund nach dem Posieren in beiden Gestenleisten gebaut, Überhangkarte an der Figur am Fenster gesehen; offen: drittes Modell (Drache) und die Einschnürung am Fenster beim Release (RM-213) |
| [RM-395 — Nachbau: kleine Lücken beim Konstruieren ohne CAD](#rm-395) | Bedienung und Darstellung | Alle sechs Lücken gebaut, je mit Test: Sperrgrund im Dialog, Projektmaterial in der Profilklemme, *Aus Skizze erzeugen* zeichnet sofort, Vereinigen meldet zugedeckte Bohrungen, Langlochrichtung erklärt, Nullring auf der Zeichenebene; offen: Fensterabnahme beim Release (RM-213) |
| [RM-396 — Grundkörper „an die gewählte Fläche ansetzen und verbinden“ in einem Schritt](#rm-396) | Bedienung und Darstellung | Umwandlungshinweis nennt keine Kennung mehr, auch nicht über `values["object"]`; offen allein die Fensterabnahme beim Release (RM-213): 45°-Schräge, gekrümmte Fläche, drittes Modell und Wiederöffnen |
| [RM-397 — Assistent „Dose mit Schraubdeckel“](#rm-397) | Bedienung und Darstellung | Parametertab und unveränderte Vorschau nach ihren Fixes als Test belegt; offen allein die Fensterabnahme beim Release (RM-213) |
| [RM-401 — Verschieben auf eine absolute Lage](#rm-401) | Bedienung und Darstellung | Verschieben und Drehen „nach“ gebaut: Bodenmitte, Mitte, acht Ecken oder Merkmal als Bezug, Gruppen starr, Rahmen `SceneObject.frame` ab Import, Griff im selben Bezug; offen: die Matrix an drei Baugruppen (Wasserfall, Sieb, Auffangrinne) am Fenster beim Release (RM-213) |
| [RM-403 — Flächenbausteine frei auf der Fläche platzieren statt immer mittig](#rm-403) | Bedienung und Darstellung | Flächenbausteine sitzen am Klickpunkt, zwei Kantenabstände werden gespeichert und bleiben bei Trägeränderungen, Wiederöffnen bindet dieselben Kanten; offen: Schlüsselloch und zwei weitere Bausteine an drei Modellen am Fenster beim Release (RM-213) |
| [RM-502 — Dialog-Durchsicht vom 29.09.: spätere Korrekturen abnehmen und verbliebene Hinweisorte klären](#rm-502) | Bedienung und Darstellung | Ziffernweg und Rückweg „Unbekannt“ in sechs Sprachen über den Spulendialog belegt, Speicherfehler und kleines Spulenfenster durch bestehende Fälle; offen allein die Fensterabnahme auf allen Plattformen beim Release (RM-213) |
| [RM-003 — Lizenzkette der gepinnten TripoSG-Bestandteile klären](#rm-003) | KI und Generatoren | Lizenzkette der eingesetzten Modellrevisionen klären |
| [RM-004 — Echte Text- und Bildgenerierung über alle Zielplattformen abnehmen](#rm-004) | KI und Generatoren | Echte Text-/Bildläufe auf Windows, macOS und Linux dokumentieren |
| [RM-014 — Zusätzliche Formenregel und zugehörige Suite-Abnahme entscheiden](#rm-014) | KI und Generatoren | Zusätzliche Formenregel entscheiden; bei Änderung Suite vorher/nachher |
| [RM-251 — Mehrteilige Aufträge enden lokal am Schrittlimit](#rm-251) | KI und Generatoren | Übernommen: Claude, Thread „Bedienung und KI“. (a) entschieden und gebaut: lokal 12 Schritte (`MAX_STEPS_LOCAL`, `steps_for`), gehostet 8; offen (b) der Satz im Prompt für gebündelte Aufrufe — braucht einen Suitelauf mit qwen3:14b vorher und nachher auf freier Karte |
| [RM-016 — Agenten-Suite gegen das aktuelle Vorgabemodell messen](#rm-016) | KI und Generatoren | Lokal abgeschlossen am 26.09.2026 (qwen3:14b 22/39 mit Angebot, ohne 14, mit großem Fenster ohne Angebot 24 in dreifacher Zeit; Modellvergleich am Punkt); offen ist nur der gehostete Vorgabeweg — ein kostenpflichtiger Lauf, der Roberts Freigabe braucht |
| [RM-441 — Reste aus RM-372 und RM-374: `hollow.done` ohne Knopf, Beispielprojekt mit alten Transaktionen](#rm-441) | KI und Generatoren | Übernommen: Claude, Thread „Bedienung und KI“. (a) erledigt: `hollow.done` trägt *Diesen Schritt ändern*; offen (b) `weg3-generiert-aufbereiten.p3d` beim Release mit `make_examples.py` neu |
| [RM-020 — Sicherung der eigenständigen Druckprojekte belegen](#rm-020) | Tests und Entwicklungswerkzeuge | Sicherungsweg entscheiden und Wiederherstellung belegen |
| [RM-099 — Konzeptbestand und veraltete Verweise ordnen](#rm-099) | Tests und Entwicklungswerkzeuge | Verweise sind vollständig gültig; offen ist nur noch das Umräumen — Umfang entscheidet Robert |
| [RM-103 — Große Kernfunktionen nach konkretem Wartungsbedarf aufteilen](#rm-103) | Tests und Entwicklungswerkzeuge | Auswertung und weitere große Funktionen nach Wartungsbedarf priorisieren |
| [RM-113 — Besitzerprüfung der Tokendatei auf dem Windows-Runner belegen](#rm-113) | Tests und Entwicklungswerkzeuge | Diagnose gebaut (`736d4a46`: SIDs genannt, Prozessnutzer angenommen); offen der Beleg auf dem CI-Runner (das Repository ist nur beim Release öffentlich) |
| [RM-134 — Zusammenführung duplizierter Testhilfen entscheiden](#rm-134) | Tests und Entwicklungswerkzeuge | 41 wortgleiche Gruppen gemessen, vier nach `tests/helpers.py` zusammengeführt (`920c609a`); offen die Fensterfixtures (`window`, `with_a_body`, `on_the_bore_wall`) — Robert entscheidet über die großen |
| [RM-137 — Sitzungsende im tatsächlichen Editorbetrieb abnehmen](#rm-137) | Tests und Entwicklungswerkzeuge | Echtes SessionEnd und Freigabe des Sitzungsgebiets nach Neustart beobachten |
| [RM-234 — Linux-Fensterabnahme und macOS-Gegenprobe nachweisen](#rm-234) | Tests und Entwicklungswerkzeuge | Gepinnter Ubuntu-Releasejob 107485122706 erreicht die Fensterverträge und besteht; „Neueste Versionen" enthält heute nur Kerntests. Der vollständige macOS-Taglauf 35982366247 ist grün; die unabhängige Ergebnismeldung der Fensterverträge bei rotem Kernschritt ist im Workflow gebaut (`0a0e4eef0`, `78e151e85`), offen ihr Nachweis an einem echten Lauf |
| [RM-272 — Die Entwicklungsmaschine rechnet zeitweise falsch](#rm-272) | Tests und Entwicklungswerkzeuge | Entscheidung Robert: CPU-Tausch über Intels verlängerte Garantie; bis dahin Intel Default Settings, einmal MemTest86, Release-Pakete in der CI bauen oder doppelt bauen und bitweise vergleichen |
| [RM-288 — Ein Einzelprozess über die ganze Suite hängt im Sammler](#rm-288) | Tests und Entwicklungswerkzeuge | Nachstellversuch als Einzelprozess lief ohne Hänger durch (3:33 h); offen: Ursache, und ob die Anwendung betroffen ist |
| [RM-313 — Der Wächter „Neueste Versionen“ liefert im privaten Repository nichts](#rm-313) | Tests und Entwicklungswerkzeuge | Lauf nur auf Release-Tag oder öffentlichen Handstart; erster echter Ergebnisbericht steht aus |
| [RM-316 — Zwillinge und Nur-Test-Wege: der Rest aus dem Code-Bericht des Aufräumens](#rm-316) | Tests und Entwicklungswerkzeuge | Die gesperrten Zwillinge nachziehen, die dünnen Hüllen auf ihren Produktionsweg umstellen, die Nur-Test-Kernfunktionen einzeln entscheiden |
| [RM-344 — Renderertests laufen in der CI nur noch unter Windows](#rm-344) | Tests und Entwicklungswerkzeuge | Review seit 0.5.1: `rendering`-Fälle in der Release-CI auf Linux und macOS und in `latest` fahren — oder Roberts Entscheidung festhalten und Wächter nachziehen |
| [RM-349 — Werkzeuge und Unterlagen: Reste aus dem Review seit 0.5.1](#rm-349) | Tests und Entwicklungswerkzeuge | Review seit 0.5.1: Textwächter ohne Katalog, OCP ohne Wächter, Regel mit Datum, veraltete Regeln und Registerzellen |
| [RM-350 — Ein roter Versionswächter am Release-Tag sperrt die Windows-Signierung](#rm-350) | Tests und Entwicklungswerkzeuge | Review seit 0.5.1: `continue-on-error: true` am Job `latest` oder eigener Workflow; Wächter in `test_packaging.py` |
| [RM-380 — `test_the_workers_of_the_window_use_the_helper` scheitert nach dem Vorschautest derselben Datei](#rm-380) | Tests und Entwicklungswerkzeuge | Review 02.10.: Zustand zwischen den Tests zurücksetzen (Zählung bzw. Vorschau-Cache); Datei am Stück grün |
| [RM-387 — Deutsche Bezeichner rutschen am Sprachwächter vorbei; englische Passungszeichnung veraltet](#rm-387) | Tests und Entwicklungswerkzeuge | Review 02.10.: umbenennen und Stämme in `GERMAN_STEMS`; `fit.svg` beim nächsten Release neu erzeugen |
| [RM-433 — Die Rückfrage vor Geld- und Veröffentlichungswerkzeugen lässt Umhüllungen und Unterschalen durch](#rm-433) | Tests und Entwicklungswerkzeuge | Review 02.10.: Folge zu RM-346 (archiviert); `timeout`, `exec`, `( )`, `$( )`, `then`/`do`, `cmd /c`, Start-Process-Argumente |
| [RM-467 — Bibliotheken alle drei Tage auf neue Versionen prüfen und aktualisieren](#rm-467) | Tests und Entwicklungswerkzeuge | übernommen: Bibliotheken alle 3 Tage aktualisieren — erster Lauf 02.10. im Archiv, nächster am 05.10.; Paketbeleg der neuen Bauplattform unter RM-468 und RM-469 |
| [RM-002 — netcup-AVV und Freigabe der Rechtstexte belegen](#rm-002) | Veröffentlichung, Betrieb und Vertrieb | netcup-AVV belegen und zugehörige Rechtstexte fachlich abgleichen |
| [RM-006 — Nächsten messbaren Schritt für die Sichtbarkeit festlegen](#rm-006) | Veröffentlichung, Betrieb und Vertrieb | Roberts Fragen im Bericht Reichweite und die erste Montagsmessung; der Punkt schließt, wenn Robert den Plan bestätigt |
| [RM-008 — DMARC-Eintrag öffentlich prüfen und gegebenenfalls einrichten](#rm-008) | Veröffentlichung, Betrieb und Vertrieb | DMARC einrichten und legitimen Mailversand prüfen |
| [RM-030 — Impressum nach Vergabe einer USt-IdNr. oder W-IdNr. ergänzen](#rm-030) | Veröffentlichung, Betrieb und Vertrieb | Bereits vergebene USt-IdNr./W-IdNr. klären; gegebenenfalls Impressum ergänzen |
| [RM-034 — Versicherungsschutz für Software und Produktschäden klären](#rm-034) | Veröffentlichung, Betrieb und Vertrieb | Versicherungsangebote gegen die tatsächlichen Risiken prüfen lassen |
| [RM-035 — EULA wirksam in den Bestellvorgang einbeziehen](#rm-035) | Veröffentlichung, Betrieb und Vertrieb | Produktgrenzen und EULA im vollständigen Bestellweg rechtlich prüfen |
| [RM-036 — Vertrag und Freistellungen des Zahlungsdienstleisters prüfen](#rm-036) | Veröffentlichung, Betrieb und Vertrieb | Konkreten Anbietervertrag und Haftungsübernahme entscheiden |
| [RM-061 — Verkaufsbereitschaft und Ende der Demo vorbereiten](#rm-061) | Veröffentlichung, Betrieb und Vertrieb | Kandidat bis 25.10.; letzte Optimierungen 31.10.; Start 01.11.2026 um 10:00 Uhr deutscher Zeit — gebaut in 0.5.0: Abschied mit Pause und Start, ‚heute letzter Tag‘, Hinweis ab 24.10. (`29dcefa4`); offen täglicher Ablaufwächter und Bestell-Webhook |
| [RM-091 — CRA-Meldebereitschaft herstellen, die Frist ist abgelaufen](#rm-091) | Veröffentlichung, Betrieb und Vertrieb | Meldeweg entschieden (Robert, 23.09.2026: über die Support-Adresse, Antwortfrist zwei Arbeitstage, keine Belohnung, kein PGP; `SECURITY.md`, `SECURITY-INCIDENT.md` und `security.html` sind konform); offen EU-Login, Vertretung, Alarmierung und Probelauf — Roberts Konten |
| [RM-092 — Verkaufskonzept für den geplanten Start abschließen](#rm-092) | Veröffentlichung, Betrieb und Vertrieb | Anbieter, Bestellstrecke, Lieferung, Widerruf und Signierung bis 15.10. |
| [RM-093 — Noch fehlende Angaben und Prüfungen der Rechtstexte klären](#rm-093) | Veröffentlichung, Betrieb und Vertrieb | Fehlende Anbieter-/Rechtsentscheidungen und Sprachfassungen fachlich prüfen |
| [RM-095 — Automatischen Löschlauf auf dem Server belegen](#rm-095) | Veröffentlichung, Betrieb und Vertrieb | Server-Löschlauf, Sicherungen und Ausfallalarm tatsächlich nachweisen |
| [RM-116 — Historische Statistikreste auf dem Server behandeln](#rm-116) | Veröffentlichung, Betrieb und Vertrieb | Öffentlichen Altbestand prüfen und Umgang mit alten Statistikzeilen entscheiden |
| [RM-145 — CRA-Konformitätsakte zum gesetzlichen Anwendungszeitpunkt vorbereiten](#rm-145) | Veröffentlichung, Betrieb und Vertrieb | Produktklassifizierung, technische Akte und Konformitätsverfahren für 2027 vorbereiten |
| [RM-242 — Testphase der Vollversion nachreichen](#rm-242) | Veröffentlichung, Betrieb und Vertrieb | Robert 25.09.2026: 1.0 startet ohne Testphase, sie kommt später — Januar (Unentschlossene noch zu 69 €) oder Februar 2027 mit dem Preissprung. Offen: Termin, ob frühere Demo-Geräte sie bekommen (heute T15: nein), Release mit gesetztem `TRIAL_FROM` |
| [RM-351 — Die Website bietet 0.5.1 an und nennt im Downloadhinweis 0.5.0 als signierte Fassung](#rm-351) | Veröffentlichung, Betrieb und Vertrieb | Review seit 0.5.1: Hinweis versionsneutral oder aus `make_download.py` gegen `version.json`; sechs Sprachen |
| [RM-038 — Mailrückfall ohne prozentkodierten Berichtstext prüfen](#rm-038) | Kundenrückmeldungen | mailto-Weg gebaut, Rückfall ohne Mailprogramm sagt, was jetzt geht, lange Berichte werden gekürzt (`29dcefa4`, `736d4a46`); offen der Portalweg im ausgelieferten Flatpak |
| [RM-040 — Kundenfehler mit Traceback und betroffener Datei zuordnen](#rm-040) | Kundenrückmeldungen | Aktuellen Kundenbericht mit Traceback und betroffener Datei reproduzieren |
| [RM-062 — Eingabemethode im aktuellen Flatpak bestätigen](#rm-062) | Kundenrückmeldungen | Start, Fokus und IME am aktuellen Flatpak bestätigen |
| [RM-064 — Slicerübergabe zwischen zwei echten Flatpaks abnehmen](#rm-064) | Kundenrückmeldungen | Modell zwischen installiertem Solidon- und Slicer-Flatpak übergeben |
| [RM-072 — Zusagen an den Dental-Kunden zum Verkaufsstart erfüllen](#rm-072) | Kundenrückmeldungen | Kaufweg und belastbare 3D-Maus-Unterstützung zum zugesagten Anlass mitteilen |

## Filamentlager

Physische Spulen mit bis zu vier Farben, Regal, bewusster Import, Schnellauswahl
und rücknehmbare Verbrauchsbuchungen sind angeschlossen; „Erste Schritte“ führt
über Slicer und Drucker zum Lager. Das [Gestaltungs- und Gesamtreview](konzepte/review-filamente-2026-09.md)
begründet Abwahl, Herstellerprofile und Buchungskorrekturen.

[Review und Nachweis zu RM-146](ROADMAP-ARCHIV.md#rm-146).

## P0 — Skelett

Grundgerüst, Register, Projektdatei, Parameter, Undo/Redo und Eingangsstufe sind umgesetzt. Laufende Fehler und Abnahmen stehen in den Aufgaben unten; die ursprünglichen Abnahmeschritte bleiben im Archiv.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p0--skelett).

## P1 — Sehen und Messen

Ansicht, Messen, Navigation und Manipulation sind umgesetzt. Seit dem 06.09.2026 zeichnet `GfxRenderer` mit pygfx/wgpu; die alten VTK-Bildraten und Zerstörungsdiagnosen gelten nicht als Nachweis für diesen Renderer. Die Plattformabnahme bleibt bei den Grafikaufgaben.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p1--sehen-und-messen).

## P2 — Operationen manuell

Manuelle Operationen, Rückfallketten, Export und Weg 1 sind umgesetzt. Bekannte Einschränkungen beim Reduzieren, bei Schnittflächen und der Druckbarkeit werden unten einzeln geführt.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p2--operationen-manuell).

## P3 — Wahrnehmung und Schichtanalyse

Merkmalserkennung, Zuordnung, Analysekarten und Schichtanalyse sind umgesetzt. Offen bleiben konkrete Qualitäts- und Leistungsfälle sowie die Endabnahme der gespeicherten Zuordnungsantworten; eine schnelle Kugelprobe belegt keine schnelle Freiformerkennung.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p3--wahrnehmung-und-schichtanalyse).

## P4 — Agent auf Säule C

Agentensteuerung über dieselben Operationen, Rückfragen und Vorschläge als Transaktion sind umgesetzt. Historische Suitequoten gelten für ihr damaliges Modell und ihren Prompt; aktuelle Modell-/Schemaabnahmen stehen unter KI.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p4--agent-auf-säule-c).

## P5 — Bausteinbibliothek

Bibliothek, Normteile, Versionierung, Vorschauen und Rezeptweg sind umgesetzt. Die noch fehlende Wahl eines alten Bausteinstands steht bei RM-138. Bereichsprüfungen werden bei Änderungen an Baustein oder Grenzen gezielt gefahren; der automatische Komplettlauf über sämtliche Bausteine ist gemäß AGENTS.md entfallen. `to_scad()` bleibt ein reiner Dateiexport.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p5--bausteinbibliothek).

## P6 — Säule A

Konstruktion aus registrierten Operationen und Bausteinen ist umgesetzt. OpenSCAD als Ausführungsweg ist seit `bc92469a` ausgebaut; ein Rückfall auf ausgeführten Quelltext gehört nicht mehr zum Umfang. Die Sicherheitsgrenze aus §32 bleibt verbindlich.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p6--säule-a).

## P7 — Slicer-Rückkopplung und Kalibrierung

G-Code-Rücklesen, Profilabgleich und Kalibrierung sind umgesetzt. Interne Schätzung und Slicerwerte behalten ihre Herkunft. Feldabnahmen der Paket-/Slicerübergabe werden unten separat geführt.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p7--slicer-rückkopplung-und-kalibrierung).

## P8 — Erste Veröffentlichung

Windows, Flatpak, AppImage und beide Mac-Architekturen sind seit 0.5.0 veröffentlicht.
Signatur-, Notarisierungs- und Releaseaktennachweise sowie der öffentliche Bytevergleich
gehören zu dieser Auslieferung. Fremdrechnerabnahme und noch fehlende Betriebsnachweise
bleiben eigene Aufgaben; siehe RM-011 und RM-002.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p8--erste-veröffentlichung).

## P9 — Säule B und Farbe

Backend-Grenze, ComfyUI-/TripoSG-Weg und Farbzuweisung stehen. Commit-/Gewichte-Pinning ist implementiert; offen bleiben die dokumentierte Lizenzkette und der vollständige plattformübergreifende Generatorlauf (RM-003, RM-004). Vorhandene Generatoren und Medien bleiben erhalten.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p9--säule-b-und-farbe).

## P10 — Auto Split mit Verstiftung

Automatisches Teilen und Verbinder sind umgesetzt. Die konkrete Wahl der Stiftseite und die weitergehende Trennen-Serie werden als aktuelle Restarbeit geführt. Der Umfang aus §40 ist vom später beauftragten Ausbau zu unterscheiden.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p10--auto-split-mit-verstiftung).

## P11 — Gehosteter Backend

Zurückgestellt; kein laufendes Bauvorhaben. Ein gehosteter Generierungsdienst käme nur nach Nachfrage und ausdrücklicher Produktentscheidung infrage. Gehostete Bearbeitung bleibt nach AGENTS.md ausgeschlossen.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p11--gehosteter-backend).

## P12 — B-Rep-Kern

Der optionale exakte Kern und STEP-Austausch sind umgesetzt. Das ist keine allgemeine Rückgewinnung exakter CAD-Flächen aus beliebigen Netzen. Der Nachbau als Operationsfolge ist seit dem 17.09.2026 beschlossen; Umfang und Abnahme stehen in RM-022, die Umsetzung läuft als Teil des CAD-Plans (RM-188).

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p12--b-rep-kern).

## P13 — Skizzen und tiefere Konstruktion

Skizzen, Bedingungen und Formgebungsoperationen sind umgesetzt. Die aktuellen Plattformbefunde des Lösers und die Gewindeabnahme bleiben ausdrücklich bei den offenen Aufgaben.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p13--skizzen-und-tiefere-konstruktion).

## P13.1 — Der Skizzeneditor zieht in den Viewport

Der Skizzeneditor arbeitet in der Ansicht. Die damaligen Umbauschritte sind abgeschlossen; verbleibende Bedien- und Darstellungsfragen stehen in den aktuellen Aufgaben.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p131--der-skizzeneditor-zieht-in-den-viewport).

## P14 — Die Oberfläche einlösen

Die damaligen Transaktions-, Undo- und Bedienkorrekturen sind umgesetzt. Neue Kundenbefunde werden einzeln verfolgt; die historische Phasenabnahme ersetzt ihre Behebung nicht.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p14--die-oberfläche-einlösen).

## P15 — Konstruieren und zeigen

Der beauftragte Ausbau ist umgesetzt. Die vier im Konzept begründet ausgeschlossenen Erweiterungen bleiben ausgeschlossen. Frühere Darstellungswerte unter VTK sind im Archiv datiert und gelten nicht als Messung des neuen Renderers.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p15--konstruieren-und-zeigen).

## P16 — Organische Modellierung

Formen, Posing, Weg 4, Beispiel und Handbuch sind umgesetzt. Der verbleibende Vorschlag für die Regelsammlung samt kostenpflichtigem Vorher-/Nachher-Suitelauf steht in RM-014. Er ist keine fehlende Umsetzung des Formwerkzeugs.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p16--organische-modellierung).

## Plattformen, Pakete und Grafik

<a id="rm-011"></a>

- [ ] **RM-011 — Erstinstallation auf einem fremden Rechner abnehmen.** Den veröffentlichten
  Installer auf einem fremden Rechner ohne Entwicklungsumgebung von Download bis erstem Modell
  prüfen. Abnahme: Installation, Start, Gerätefreischaltung beziehungsweise Dateiweg, Import,
  Speichern/Wiederöffnen und Export funktionieren ohne Python, venv, Ollama oder ComfyUI; Plattform,
  Paketversion und Ergebnis sind festgehalten.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-demo-bis-30102026-12082026).

<a id="rm-021"></a>

- [ ] **RM-021 — Native Fensterlebensdauer am aktuellen Renderer abnehmen.** Der vollständige geteilte
  Windows-Lauf vom 08.09.2026 ist inzwischen grün: 11.791 bestandene Tests, 34 Leistungstests und
  übergeordneter Exit 0. Die früheren sporadischen Abrisse, Hänger und Abbaufehler sind damit noch
  nicht ursächlich zugeordnet. Offen bleibt ihre gezielte Lebensdauerprüfung am heutigen Qt-/pygfx-
  Stand. Abnahme: betroffene Fenster- und Abbauszenarien wiederholt auf festgehaltenem ruhigem Stand
  mit sauberem Prozessabschluss; bei einem erneuten Riss oder Hänger aktuellen Stack, Test, Exit-Code
  beziehungsweise Timeout und Renderer/Laufzeit festhalten. Die historischen Signaturen getrennt
  halten; ein einzelner erfolgreicher Lauf ersetzt bei sporadischen Fehlern keine Vergleichsreihe.

  **Fortschreibung 15.09.2026 — eine Ursache ist gemessen, für zwei Risse.** Der Tag-Lauf
  `v0.4.2` riss auf Windows in `tests/test_filament_picker.py` (Exit 127, `0xc0000374` im
  `gc.collect` des Teardowns), lokal deterministisch, drei von drei. Bisektiert über 76 Commits
  auf `98bf029e`, darin auf `panels.py`, darin auf den Namen `QSpinBox` im
  `from PySide6.QtWidgets import (...)`: Import ohne Nutzung rot, Nutzung über
  `QtWidgets.QSpinBox` ohne Import grün. Also nicht der Name, sondern **wann** PySide 6.11.2 den
  Typ anlegt — mit der Vorgabe erst beim ersten Zugriff (`len(vars(PySide6.QtWidgets))` 15 statt
  206). Mit `PYSIDE6_OPTION_LAZY=0` läuft der HEAD durch, **und der Stand vom 14.09. mit dem
  `QMouseEvent`-Import ebenfalls** — derselbe Fehler, damals als Symbol gelesen. Gesetzt in
  `app/ui/__init__.py`, `app.py` und `tests/conftest.py`, gehalten von
  `test_the_interface_loads_qt_types_before_the_first_window`; Preis 60 ms und 6 MB. **Was das
  über die sporadischen Risse der Fensterdateien sagt, ist offen**: Beide bisektierten Fälle
  hatten dieselbe Gestalt wie die Familie vom August (Heap im Sammlerlauf nach dem Fensterabbau),
  gemessen ist die Ursache nur für die zwei deterministischen. Die Abnahme dieses Punkts bleibt
  die Vergleichsreihe — jetzt mit der Vorgabe.

  **Fortschreibung 17.09.2026 — der dritte Riss ist eingegrenzt, und er ist keiner der Anwendung.**
  Im Tor vom 17.09. endete `tests/test_ui.py` Teil 4 mit Exit 127 über **sechzig grünen Tests**;
  der native Code ist `0xC0000409`, dreimal von drei, und derselbe letzte Test allein ebenso.
  Halbiert über die Portion: Auslöser ist `test_a_stopped_step_is_one_click_from_its_own_dialog`,
  und zwar nicht sein Inhalt — eine Stufensonde zeigte, dass schon das bloße Öffnen von
  `plate_holes.stl` in einem Fenster genügt. Ein Fenster ohne Modell, ein Fenster mit *Quader*
  und das Einlesen derselben STL **ohne** Fenster laufen alle drei sauber durch.

  Weiter halbiert über `tests/conftest.py` (31 Schnittstellen, Kopf gegen Ganzes): Der Kopf bis
  Zeile 717 ist sauber, den Riss bringt `_no_worker_outlives_its_window` — und darin, in Stufen
  gemessen, allein das `application.processEvents()` im Teardown. `release` allein, die Leine
  allein und beide zusammen sind sauber; das Zustellen der Ereignisse ist es. Vier
  Sitzungsabschlüsse dagegen — sammeln, Ereignisse zustellen, die QApplication löschen, alle
  Fenster schließen und löschen — fangen ihn **nicht** auf: Der Schaden entsteht beim Zustellen,
  sichtbar wird er beim Herunterfahren.

  **Die Anwendung ist nachweislich nicht betroffen.** Der Kundenweg — `build_application`, STL
  öffnen, `close()`, `quit()`, Prozessende — endet offscreen wie auf der echten Plattform mit
  Exit 0, und zwar in allen drei Abbauvarianten (`close`, `release`, gar keine). Auch ohne
  Ereignisschleife, also genau wie die Suite fährt, bleibt derselbe Ablauf außerhalb von pytest
  sauber. Es ist ein Befund der **Testinfrastruktur** unter Windows — und zwar der hiesigen
  Portionierung, nicht der Plattform: Der Tag-Lauf vom 17.09.2026 fährt `Suite (windows-latest)`
  grün. Dort läuft jede Fensterdatei in einem eigenen Prozess, hier laufen sie in Portionen zu
  sechzig; getroffen wird nur die Portion, deren letzter Test ein Fenster mit eingelesenem STL
  hinterlässt.

  Was offen bleibt, ist die Ursache hinter `processEvents` — welcher zugestellte Ereignistyp den
  Speicher verletzt. Nächster Schritt: die Zustellung je Ereignistyp einzeln fahren
  (`sendPostedEvents` mit gesetztem `event_type`) und den ersten finden, der reißt; dazu derselbe
  Lauf auf einer Linux- und einer Mac-Maschine, um die Plattformbindung zu belegen. Ein
  Abschluss, der den Riss nur verdeckt, gehört ausdrücklich **nicht** dazu — er machte das Tor
  grün, ohne dass jemand etwas gemessen hätte.

  **Dazu aus `.claude/rules/wartezeit.md`:** `weak_slot` je Knopf an einer Knopfgruppe
  riss `test_widget_lifetime` mit einer Zugriffsverletzung; die Regel verlangt deshalb den
  gebundenen Empfänger an `QButtonGroup.buttonClicked`. Die Ursache ist nicht zugeordnet.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-ein-kunde-beim-öffnen-der-beispiele-sieht-23082026).

<a id="rm-050"></a>

- [~] **RM-050 — Kopierkosten messen und verbleibende VTK-Geometrie ablösen.** pygfx ist der einzige
  Renderer; die mehrfachen Normalenläufe und das Halten alter Renderer beim Sprachwechsel sind
  behoben. Offen bleiben die kopierten Bytes und Pufferkosten je großer Szene. Abnahme:
  reproduzierbare Zeit-/Speichermessung am großen Netz. Der beschlossene Ersatz von VTK in der
  Baustein-Bereichsprüfung ist nachgewiesen; Plattformfenster werden separat abgenommen.

  **VTK ausgebaut am 23.09.2026** (`5a57e261`):
  `range_check.local_wall_thickness` misst mit `mesh.ray_hits_batch`
  (Möller-Trumbore als Feld, mit `ray_hits` auf eine Rechnung zusammengelegt)
  statt `vtkStaticCellLocator`, alle 35 Bausteine mit unveränderten Ergebnissen;
  `THIRD-PARTY-NOTICES.md` hatte danach 42 Komponenten. **Aktueller Stand:** Matplotlib
  ist seit `9bb1542b` wieder ausdrücklich Laufzeitabhängigkeit. Nach Erneuerung der lokalen
  Projektmetadaten enthält die Windows-Entwicklungsvorschau der Lizenzbeilage 50 Komponenten;
  die Kundenbeilage entsteht weiterhin je Plattform aus deren Endartefakt-SBOM.
  Nachweis: `konzepte/nachweise-release-0.5.0/reports/codex-ci-notices-fix.md` (67 Lizenztests,
  Generatorprüfung und Umgebungsprüfung jeweils Exit 0). Die Folgen des VTK-Ausbaus (Wandmessung ohne
  räumlichen Index, fehlender Wächter gegen VTK-Importe) standen als RM-214 und sind
  in der Durchsicht v0.5.1 geschlossen ([Archiv](ROADMAP-ARCHIV.md#rm-214): Baum aus
  Hüllquadern `7e3442623`, VTK-Wächter `a0db3edeb`).
  Offen hier nur die Kopier- und Pufferkosten am Fenster.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-der-gesamtreview-liegen-ließ-05092026).

<a id="rm-051"></a>

- [ ] **RM-051 — Renderer und Grafiklaufzeit in Linux- und Mac-Paketen abnehmen.** Gebaut und
  veröffentlicht ist inzwischen **0.4.0** für alle vier Ziele (Stand 10.09.2026); die
  0.3.5-Dateien sind vom Server geräumt. Die expliziten wgpu-Bibliotheken stecken weiter in der
  Paket-Spec. Offen sind der tatsächliche Grafik-/Eingabeweg samt Vulkan beziehungsweise
  Metal und die Unix-Fenstergruppe: Die CI führt sie aktuell nur auf Windows aus, weil Linux und
  macOS konkrete Befunde zeigen. Abnahme je Plattform: sichtbares Modell, Auswahl/Navigation,
  Schließen, dokumentierte Treiber-/Paketumgebung und erfolgreiche vollständige Fenstergruppe ohne
  stilles Überspringen fehlender Adapter.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-der-gesamtreview-liegen-ließ-05092026).

<a id="rm-055"></a>

- [ ] **RM-055 — Neue Paketwerkzeuge im installierten Kundenpaket abnehmen.** Veröffentlicht ist
  inzwischen das **0.5.1**-Flatpak; offen bleibt der reale
  Linux-Lauf mit Grafik, Qt, Dateizugriff und Offline-Start.

  **Historischer Compilerbefund vom 10.09.2026:** Die CI suchte ISCC auf dem PATH und
  nahm 7 vor 6 — der Kommentar daneben hielt fest, dass das Runner-Image damals **6** trug.
  Gebaut wurde mit Inno Setup 6, und die Fassung wurde **nirgends protokolliert**: kein
  Versionsaufruf vor dem Bau, kein Eintrag in der Releaseakte. Der Punkt sagte „für Inno Setup
  7" und meinte damit eine Fassung, die dort gar nicht lief. Dieser Nachweis liegt seit 0.5.1
  vor (unten). Weiter offen sind Installieren, Aktualisieren und Deinstallieren auf einem
  fremden Windows. Abnahme mit Paket-/Compilerfassung und Feldprotokoll.

  **Durchsicht v0.5.1 (26.09.2026, werkzeuge):** Seit `0c58a7837` durfte der Installer auf
  einem späteren Commit mit geänderten Signierskripten bauen, ohne dass für diesen Stand
  ein Test lief. Weicht der Installercommit vom Produktcommit ab, installiert der
  Installer-Workflow jetzt die volle Prüfumgebung und fährt `tests/test_sign_release.py`
  und `tests/test_windows_signed_installer.py` vor Herkunftsprüfung und Bau; rot endet
  vor dem Bau (`73692bfbc`, Wächter in `test_packaging.py` mit acht Gegenproben). Unter
  nachgestellter CI-Umgebung grün (188).

  **Am Windows-Runner belegt mit 0.5.1:** Der erfolgreiche
  [Installerlauf 36467614477](https://github.com/RS-Digital-Studio/Solidon/actions/runs/36467614477)
  vom 28.09.2026 rechnet auf `637f79825`, abweichend vom Produktcommit `585869a2c`.
  „Prüfumgebung der geänderten Orchestrierung“ und „Tests der geänderten Orchestrierung“
  liefen vor Herkunftsprüfung und Bau erfolgreich; **188 bestanden in 42,46 s**.
  Der Bau protokolliert **Inno Setup 7.1.0**. Das schließt die beiden CI-Nachweise,
  nicht die Linux-Grafikabnahme oder den Installationsweg auf fremdem Windows.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-der-gesamtreview-liegen-ließ-05092026).

<a id="rm-104"></a>

- [ ] **RM-104 — Verbleibende Mac- und Unix-Befunde mit aktueller CI-Abdeckung abnehmen.** Die
  verbleibenden macOS-/Unix-Befunde schließen: Intel-Hänger beim ersten Ereignisdurchlauf mit
  Adapter- und Lebensdauerbeleg diagnostizieren; Fensterlayouts, Gewinde-/Exportpfade und Chatablauf
  auf den betroffenen Architekturen prüfen. Der aktuelle CI-Testjob enthält keinen Intel-Mac; die
  Fenstergruppe läuft nur auf Windows. Beide Einschränkungen ersetzen keine Fehlerbehebung. Abnahme:
  die im bisherigen Befund genannten Fälle auf macOS und Linux reproduzieren und schließen, mit
  sichtbaren Pixeln, bedienbarem Fenster und sauberem Prozessabschluss; anschließend die
  Testabdeckung entsprechend nachziehen. Bereits reparierte Skizzen-/B-Rep-/Dialogbefunde bleiben
  abgeschlossen.

  **Zwei sporadische Befunde aus den Tag-Läufen von v0.4.1 (13.09.2026), beide
  mit nicht strenger `xfail`-Marke im Test — der Bau läuft, der Fall steht
  hier, und ein grüner Runner-Lauf gilt nicht als Nachweis:** Auf **macOS**
  kommt der Abbruch eines lokalen Ollama-Aufrufs nicht sicher in einer
  Sekunde an — der Weg schließt den Socket aus dem wartenden Thread
  (`shutdown`, `detach`); in drei Läufen waren drei, zwei und dann eine Stufe
  rot — jede der vier einmal, auch die mit Verbindungsende
  (`test_backends.py`). Ein Umbau auf einen
  Leser mit kurzem Socket-Timeout, der das Token selbst prüft, ist der
  naheliegende Weg; gemessen wird er auf einem Mac. Auf **Linux (Xvfb)** reißt
  der Renderer-Kindprozess des HiDPI-Grifftests sporadisch mit Exit -11 —
  erst bei `QT_SCALE_FACTOR=2`, dann bei beiden Werten grün, dann bei 1
  (`test_render_factory.py`) — ob Softwarerenderer des Runners oder
  Anwendung, sagt nur ein Linux mit Bildschirm. Abnahme beider: dreimal in Folge auf der Plattform
  grün ohne Marke. Der Changelog-Punkt zum Abbruch während der Antwort ist für
  0.4.1 gestrichen, bis er auf allen drei Plattformen belegt ist.

  **Befund 03.10.2026, Intel-Runner (`macos-26-intel`, Lauf 37150755506):** Das
  veröffentlichte Intel-Paket 0.5.1 hängt dort beim ersten Zeigen des Fensters im
  Hauptthread in `-[NSWorkspace iconForContentType:]` → `ISIconManager` (synchrones XPC),
  weil der Symboldienst des Systems (`iconservicesagent`) auf der paravirtualisierten Grafik
  in Metal abstürzt (`MTLReportFailure` in `RenderBox`); Spotlight und Dock stürzen daneben
  ab. Das ist sehr wahrscheinlich derselbe „Hänger beim ersten Ereignisdurchlauf“ und eine
  Eigenheit des Runners, keines Kunden-Macs. Der Starttest des Release-Laufs fährt den
  Intel-Mac deshalb ohne Bildschirm (`auslieferung.md`); Fenster und Metal-Ansicht auf Intel
  belegt nur ein echtes Gerät — offen bleibt die Rückmeldung des Kunden nach 0.5.2 (RM-505).

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-erste-vier-plattform-lauf-seit-dem-06092026-08092026).

<a id="rm-107"></a>

- [ ] **RM-107 — Ubuntu-Workerabbruch mit aktuellem Testbestand zuordnen.** Die verbleibenden
  Qt-Abstürze im Linux-Sammellauf und beim späteren Speicherbereinigen mit heutiger
  Worker-/Widget-Lebensdauer erneut eingrenzen. Abnahme: protokollierte Testreihenfolge pro Worker,
  reproduzierbarer Auslöser und saubere Prozessabschlüsse; getrennte Fensterdateien bleiben bis
  dahin Teil des Prüfverfahrens.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-114"></a>

- [ ] **RM-114 — Vereinfachungsziele auf Apple Silicon vermessen.** Die Vereinfachungs-Zielreihe der
  dünnwandigen Hohlkugel auf Apple Silicon messen und den Warnungsnachweis dort zuverlässig
  auslösen. Abnahme: dokumentiertes Ziel mit dichtem Eingang/offenem Ausgang und tatsächlicher
  Warnung; kein Skip als Erfolg.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-187"></a>

- [~] **RM-187 — Dieselbe Geometrie auf jeder Plattform.** Am 17.09.2026 lieferte dasselbe
  Verkleinern einer Bohrung mit Senkung ein anderes Netz auf jeder Plattform, und eine
  Bohrungskette, die Solidon auf Windows erkennt, war auf dem Mac nicht mehr da. Drei
  Reparaturen liefen in die Merkmalserkennung, wo kein Fehler war.

  **Die Ursache, gemessen statt vermutet** (Läufe 35262208955 und 35265459662, drei
  Plattformen): Sie liegt **vor** dem Booleschen Kern. Der Kontrollversuch ist eindeutig — ein
  Klotz, der ohne eine einzige transzendente Funktion entsteht, trägt auf allen drei Plattformen
  denselben Fingerabdruck; Hohlraum und Nachbar, beide aus `cos`/`sin`, auf allen drei einen
  anderen. `np.cos` und `np.sin` wählen ihre Implementierung nach den Fähigkeiten der CPU:
  AVX-512 auf Ubuntu, AVX2 auf Windows, NEON auf macOS, und die drei runden die letzte Stelle
  verschieden. Drei Zehntel eines Billiardstels Millimeter, und nach einer Booleschen Operation
  sind es zwei Dreiecke.

  **Zwei Annahmen sind damit widerlegt, und beide waren meine.** Es ist nicht ARM gegen x86 —
  Windows lieferte 1226 Dreiecke und Ubuntu 1224, beide x86_64. Und ein exakter Boolescher Kern
  hätte nichts geholfen: Geogram und trueform rechnen exakt *mit* ihrer Eingabe, und zwei
  verschiedene Eingaben geben auch exakt gerechnet zwei verschiedene Ergebnisse. Die Anfrage an
  Polydera ist deshalb zurückgezogen, das Geogram-Konzept erledigt.

  **Und der Satz, auf den es ankommt: manifold3d ist plattformgleich.** Nachdem die
  Eingangskörper über `units.circle_point` entstehen, liefert die Boolesche Operation auf
  Windows, Ubuntu und macOS denselben Fingerabdruck — 1222 Dreiecke, `8c1169913b6ac670`. Der
  Kern, den wir haben, kann, was wir brauchen.

  **Gebaut:** `units.circle_point` rechnet die Ecken eines regelmäßigen Vielecks über `decimal`,
  aus Ganzzahlen und nicht aus einem schon gerundeten `float`; ein Viertelumlauf wird gerechnet,
  der Rest entsteht durch Vorzeichen und Tausch, was kein Bit ändert. Dazu `inscribed_ratio`
  (`cos(π/n)` als Ecke eines `2n`-Ecks, bitgenau derselbe Wert wie bisher) und
  `exact_cos_degrees`, das die Gradumrechnung innerhalb der genauen Arithmetik hält.
  `geom.lathe` setzt es an den Drehkörpern durch — ohne eigenen Drehalgorithmus: `trimesh`
  erzeugt die Topologie weiter, ersetzt werden nur die Ecken, und ob die Struktur dafür passt,
  prüft es bei **jedem** Aufruf nach. Umgestellt sind 23 Drehkörperaufrufe und alle
  Winkelrechnungen der Geometrie samt der Schwellen in `perceive`.

  **Der Nachweis** ist `tests/test_platform_identity.py`: festgeschriebene Bits für Kreisecken,
  Zylinder, Rohr, gedrehte Kontur und ebenen Umriss. Regel 6 gilt dort ausdrücklich nicht — die
  Zusage *ist* die bitgenaue Gleichheit, und ein Vergleich mit Toleranz verschluckt genau den
  Unterschied, um den es geht. Genau deshalb hat ihn jahrelang niemand gesehen.

  **Was erreicht ist, gemessen über drei Runner:** Alle Eingangskörper sind bitgleich. Die
  Boolesche Operation, die daraus das Netz macht, ebenfalls — 1222 Dreiecke, `8c1169913b6ac670`
  auf Windows, Ubuntu und macOS. Im Änderungsweg sind die ersten drei von vier Booleschen
  Schritten bitgleich, und das Ergebnis hat auf allen drei **dieselbe Topologie**: 1182 Dreiecke,
  593 Ecken. Die Bohrungskette, wegen der die Sache anfing, wird überall gefunden.

  **Was offen bleibt:** Die Koordinaten des Endergebnisses unterscheiden sich noch in der letzten
  Stelle. Aufgezeichnet wurde der ganze Weg (`weg_aufzeichnen.py` legt sich vor jede Boolesche
  Operation und schreibt Ein- und Ausgabe), und die Stelle ist eingegrenzt: `prepare.resize_bore`
  dreht das ganze Netz über `apply_transform` in ein lokales System, schneidet dort und dreht
  zurück. Eine Matrixmultiplikation über alle Punkte geht durch BLAS, und dessen Gruppierung und
  FMA-Nutzung hängen von der CPU ab. `np.linalg.norm` und `np.linalg.inv` in derselben Kette sind
  bereits ersetzt (`math.hypot`, `lathe.rigid_inverse`) — gemessen ohne Wirkung, es ist die
  Transformation selbst.

  Zwei Wege stehen dafür offen und sind noch nicht entschieden: die Multiplikation elementweise
  selbst rechnen (billig, aber NumPy darf dort weiterhin FMA verwenden), oder **das Werkzeug in
  die Weltlage drehen statt das Netz in die lokale** — ein paar hundert Punkte statt
  Zehntausenden, was zugleich schneller wäre. Der zweite Weg ändert die Logik der Operation und
  gehört deshalb gemessen, bevor er gebaut wird.

  **Erledigt 28.09.2026 (Release 0.5.1, Paket bohren, `94aa590eb`):** entschieden für den
  zweiten Weg — das Werkzeug liegt in der Welt, für `drill`, `resize_bore`, `slot_bore` und
  die gemischte Ecke ([RM-274](ROADMAP-ARCHIV.md#rm-274)); das Netz außerhalb des Schnitts
  bleibt Bit für Bit. Neu offen aus demselben Paket: Die Bögen eines Langlochs tastet
  `sketch_solid._arc_points` über `math.atan2`, `math.cos` und `math.sin` ab (betrifft jeden
  abgetasteten Skizzenbogen; der Langlochfall des Wegs `drill_hole` änderte unter Rauschen
  seinen Abdruck), und die übrigen `math.tan` in Werkzeugmaßen (*Senkung*) sind gemessen,
  nicht ersetzt. Vorschlag des Pakets: `_without_scars` legt nach dem Schließen koplanare
  Dreiecke im ganzen Körper zusammen und nimmt ferne Ecken weg — auf das Umfeld der
  Änderung begrenzen (`konzepte/nachweise-release-0.5.1/reports/bohren-schluss.md` §6–7).

  Abnahme: `tests/test_platform_identity.py` grün auf allen drei Runnern, und der Bohrungstest
  ebenfalls.

  **Durchsicht 0.5.0:** `a559e947` stellt Drehen, Druckoptimal ausrichten, An
  Merkmal ausrichten, Stellung geben, den schrägen Schnitt, Offene Fläche
  schließen, die Importreparatur, Stufe 3 der Rückfallkette und den runden
  Konturversatz um; `test_platform_identity` verrauscht jede plattformabhängige
  Rechnung um ein ULP und tauscht den BLAS-Kern. Offen in `perceive`: Achsen aus
  `eigh` (`_fit_cylinder_read`, `fit_stadium`, `_fit_cone_read`), Kreis und
  Kugel aus `lstsq`, Ebenen aus `svd`, der Löser `least_squares` (größter
  Posten, noch ohne plattformgleichen Ersatz) und das Nachführen bewegter
  Merkmale; dazu `knowledge/parts/shapes.thread_body` mit `math.cos`/`math.sin`,
  die Platzierung in `knowledge/parts/ops.py` über `@` statt
  `transform.composed` (Stichprobe: Zeilen 1872–1953) und `texture_ops._noise`
  mit GEOS-`buffer` (Bogenpunkte aus der Mathematikbibliothek der Plattform,
  Stichprobe: Zeile 291).

  **Durchsicht v0.5.1 (26./27.09.2026):** Drei weitere Wege rechnen plattformgleich und
  stehen im Rauschtest (`test_platform_identity._WAYS`): Verrunden und Fase an der
  schiefen Tetraederecke (`corner_fillet`, `corner_chamfer` — Längen über `math.hypot`,
  Winkel über `mesh.stable_arccos`, kleine Gleichungssysteme nach Cramer statt LAPACK;
  vorher beide rot, `9bc3d354e`) und der Deckel einer gekrümmten Mündung
  (`curved_mouth`, Polynom in Grundrechenarten; mit `np.linalg.lstsq` wird der Weg rot,
  `1880cb13d`). Die offenen Posten oben sind unverändert.

  **Durchsicht v0.5.1, dritte Runde (27.09.2026):** Gebaut ist eine Summe, die an der Zahl
  der Arbeiter hing: Die Stützsäulen der Schichtanalyse rechneten in Gruppen je
  Startschicht, und ein Prüfkörper aus drei Decken ergab bei ein, zwei und drei Arbeitern
  108 243,12043751762, …759 und …76 mm³. Seit `1d8dd68aa` teilen sich die Arbeiter die
  Stücke einer Schicht, und die Summe entsteht in einer festen Folge
  (`test_slice.py::test_the_support_volume_comes_out_the_same_on_any_number_of_workers`,
  Regel in `.claude/rules/kern.md`). Die Hubhöhe eines schräg gesetzten Bausteins rechnet
  komponentenweise über `mesh.stable_normals` (`bba2c6ea7`). Neu offen sind drei Wege:

  - **Der Teilungsweg rechnet Naht- und Stiftlagen über BLAS** (rest-teilen,
    REST-TEILEN-06, vor 0.5.0 entstanden): `autosplit` (`_reflected`, `cuts_through`,
    `_gaps`, `_tilted` mit den Lagen schiefer Nähte, `_notch_depth`, `_judge`,
    `upright_normal`), `symmetry.mirror_plane` und `pins` (Stiftlage über
    `np.linalg.inv(...) @`, `np.dot`, `np.linalg.norm`). Nicht mit RM-266 gebaut, weil der
    Ersatz Naht- und Stiftlagen in der letzten Stelle verschiebt und über `pins.py` und
    `symmetry.py` hinausreicht. Weg: auf die Werkzeuge aus `geom/CLAUDE.md`
    („Plattformgleich gerechnet“) umstellen (`transform.along`, `units.dot3`, `math.hypot`,
    `transform.turned`); Wächter ein Weg `split_seam` in `_WAYS` (schiefe Naht am Z aus
    `test_autosplit`, Spiegelebene, Stiftlagen) — `@` fängt dort nur der Kerntausch-Test.
    Abnahme: Korpus `konzepte/nachweise-release-0.5.1/sonden/rest-teilen/korpus.sh` vorher und
    nachher, Unterschiede nur in der letzten Stelle schiefer Nähte, Spiegelebenen und
    Stiftlagen, dort begründet.
  - **Die Drehwege von *Merkmal drehen* rechnen Achse und Mitte über `matrix[:3, :3] @`**
    (am Code nachgelesen, Stand `e1b897ca2`): elf Stellen in `geom/prepare_ops.py`, in
    `_rotate_cavity_chain`, `_turned_open_cone`, `_turned_vector`, `_plane_turned`,
    `_exact_chain_tool_turned` und `_exact_rotate_chain`, dazu neu mit `2e496575b` in
    `_blind_reach`, `_turned_blind_bore` und `_exact_turned_blind_tool`. *Merkmal drehen*
    steht nicht in `_WAYS`.
  - **Das Einsetzen eines Bausteins** (die Platzierung über `@` aus der Liste oben): Ein
    Weg `slanted_part` in `_WAYS` fiel bei der Übernahme von rest-schraube unter dem
    Rauschen (Fingerabdruck `368/74a9b93560d2bc38` gegen `368/f86deed651efc05c`,
    `konzepte/nachweise-release-0.5.1/reports/tor-rest-schraube/weg.txt`) und ist vor dem Commit
    wieder herausgenommen; laut Übergabe der Durchsicht hängt schon das gerade Einsetzen an
    der Plattform. Weg: die Platzierung über `transform.composed`, danach den Weg einchecken.
  Review 02.10. (`7f0de659d`): Restposten plattformabhängiger Rechnung neben der neuen Ausrichtung: `app/core/geom/patterns.py:1405` (`np.linalg.norm` ohne Achse), `:1491` und `:1534` (`np.cos`/`np.sin`).

<a id="rm-468"></a>

- [~] **RM-468 — CPython 3.14.8 bringt Sicherheitskorrekturen in die ausgelieferte Laufzeit.**
  Aus RM-467, erster Lauf 02.10.2026. 3.14.8 (30.09.2026) begrenzt in `zipfile` das Entpacken
  auch für bzip2, LZMA und Zstandard (eine fremde 3MF ist ein ZIP-Archiv), schließt einen
  Pfadausbruch in `tarfile`, bringt unter Windows und macOS OpenSSL 3.5.9, libexpat 2.8.5 und die
  Korrektur zu CVE-2026-15806. Jedes Paket trägt den Interpreter seines CI-Baus. Die drei
  Workflows bauen seit `d84ff9695` mit 3.14.8, die Lizenzbeilage kennt 3.14.8 und OpenSSL 3.5.9
  (belegt an `PCbuild/python.props` und `Mac/BuildScript/build-installer.py` zum Tag; libffi bleibt
  3.4.4), Linux läuft fest auf `ubuntu-24.04`. Die Kernsuite zeigte damit auf Windows, Linux und
  macOS dieselben Ergebnisse wie main (Handstart 37060439101 gegen 37058800949).
  **Offen:** der Paketbau auf allen vier Plattformen samt Releaseakte — die Paketjobs warten auf
  die Fensterjobs, die auf main rot sind —, danach die drei Arbeitsplätze. Deren Installation
  ersetzt `python314.dll` unter jeder laufenden Umgebung und geht nur, wenn keine Sitzung rechnet.
  **Abnahme:** Taglauf oder Vollstart mit allen Paketen grün, die Releaseakte nennt 3.14.8;
  `check_env` meldet auf jedem Arbeitsplatz 3.14.8.

<a id="rm-469"></a>

- [~] **RM-469 — rubicon-objc 0.5.7 wartet auf den Mac-Paketbau.** Aus RM-467, erster Lauf
  02.10.2026. rubicon-objc kommt nur auf macOS über wgpu in den Baum, für die Metal-Oberfläche der
  Ansicht. 0.5.7 (30.09.2026) wirft für unbekannte C-Typen `ValueError` statt `AttributeError` und
  verlangt ein funktionierendes `platform.processor()`. Der Pin steht seit `3c21802b9` auf 0.5.7;
  die Kernsuite auf macos-latest lief damit wie main, die Fensterverträge auf macOS zeigen dieselben
  Fehler wie auf Windows und Linux (Handstart 37060439101).
  **Offen:** beide Mac-Paketjobs (Apple Silicon und `macos-26-intel`, das nur paketiert wird) und
  ein Blick auf die Ansicht im gebauten Paket; sie laufen, sobald die Fensterjobs grün sind.
  **Abnahme:** beide Mac-Pakete gebaut, die Ansicht des Mac-Pakets zeichnet.

## Geometrie, Erkennung und Druckvorbereitung

<a id="rm-504"></a>

- [~] **RM-504 — Importierte Texturen als gemeinsame Auswahl.**
  Getrennte Rippen-, Waben- und Noppenfelder werden nach Lage und Richtung
  erkannt; die örtliche Suche lässt die vollständig enthaltenen früheren
  Einzelmerkmale im Muster aufgehen. Alte Zellbezüge bleiben reserviert und
  werden nicht auf das gesamte Muster umgedeutet. Speichern, leerer Cache,
  Plattencache, Undo/Redo und vier Wiederöffnungen in einem frischen Prozess
  sind geprüft (`tests/test_pattern_features.py`, `tests/test_local_detection.py`,
  [Importnachweis](konzepte/begruendungen/regel-schichtanalyse.md#importierte-texturen-als-getrennte-felder-rm-504)). Reale Gegenmodelle umfassen
  Gewürzdeckel, Wabenhalter, Magnetschaber, Schrift und Ornament.

  **Offen:** Kleine Felder unter den belegten Erkennungsschwellen und
  uneindeutige Ornamente brauchen eine ausdrückliche Nutzerzuordnung über
  die Oberfläche, bevor aus Einzelmerkmalen eine bearbeitbare Textur wird.
  Der native STEP-Leser bildet bisher keine Muster; der bestehende Weg ist
  *Flächenbearbeitung beenden* und danach die Netzerkennung. Eine direkte
  STEP-Erkennung und der Umfang der ausdrücklichen Zuordnung sind noch zu
  entwerfen. Keine pauschale Schwellenabsenkung: Funktionsbohrungen,
  Magnettaschen und Beschriftungen bleiben eigenständig. Fensterabnahme
  ausschließlich beim Release unter RM-213; das Entwicklungstor des
  gemeinsamen Arbeitsbaums muss vor der Übernahme grün sein.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Nachweiszahlen zum Stand am Punkt:
  örtliche Erkennung 89, Musterbestand 188 und 48 Fälle grün, darunter 18 STL-Rundläufe getrennter
  Felder; vier Projekte im frischen Prozess mit leerem Cache unverändert. Neun reale Modelle neu
  importiert: Gewürzdeckel ein Rillenmuster mit 24 Zellen, Wabenhalter 196 Waben, Bohrungen,
  Magnetschaber, Schrift und Gewinde bleiben eigenständig; an der Kumiko-Schale zwei fremde Muster
  statt falscher Wellen, die Grenze von 5 000 Merkmalen greift nicht mehr. Unabhängige Durchsicht
  ohne P1/P2. Belege unter `F:\solidon-review-reports\codex-2026-10-03\texture-import\`:
  `pruefbericht.md`, `review\README.md`.

  **Teilstand 04.10.2026 (Claude, Zweig `claude/rm-texturen-zuordnung`):** Beide offenen Teile
  sind gebaut, die Erkennungsschwellen bleiben. *Als Muster zusammenfassen*
  (`perceive.ops.group_pattern`) fasst markierte Einzelmerkmale als Schritt ohne
  Geometrieänderung zusammen, mit derselben Zellenlesung wie die Erkennung
  (`patterns._read_cells`, `grouped_pattern`): gewählte Merkmale sind Zellmaterial, ungewählte
  Wände einer gewählten Zelle gehören dazu, ab zwei Zellen; deckungsgleiche Zellen im Gitter
  bekommen Stil und Teilung, sonst `other`. Durchgehende und tiefe Bohrungen (`_a_bore`), zwei
  Träger, erhabene neben vertieften Zellen, eine einzelne Zelle und Merkmale ohne Zelle sagen mit
  Weg ab (`group_refusal`). Das Muster heißt `grouped_<Schritt>` (`evaluate._named_after_the_step`,
  beide Kerne) und bindet sich in jedem Folgeschritt wie eine Textur
  (`patterns.bound_to_its_surface`); die Zellnamen bleiben reserviert, ein alter Zellbezug hält mit
  Rückweg an. *Merkmal ändern* bindet die neu gezeichneten Zellen, eine reine Tiefenänderung behält
  die Umrisse. Vorn in der Auswahlkarte bei mehreren markierten Merkmalszeilen
  (`QUICK_SEVERAL_FEATURES`); der Dialog übernimmt die markierten Zeilen. Der exakte Körper fragt
  dieselbe Mustersuche an seiner Tessellierung (`brep.features.features_of`): Eine Wabenplatte
  aus STEP war 90 Flächen und ist jetzt dasselbe Muster wie ihr STL-Zwilling; Entfernen bleibt
  exakt; `CACHE_FORMAT_VERSION` 43. Tests: `tests/test_pattern_grouping.py` 13,
  `tests/test_exact_patterns.py` 7, `tests/test_exact_body_parity.py` +2 (beide Kerne),
  `tests/test_selection_operations.py` +1. Vorher rot, nachher grün: ohne Oberflächenbindung
  Verlaufs- und Schnittfall (2/2), ohne STEP-Suche alle vier Zwillingsfälle (4/4), ohne Neubindung
  in `_resize_pattern` die Tiefenänderung („die Teilung passt nicht ins Feld“). Entwicklungstor
  23 089 bestanden, 122 übersprungen, Exit 0; ruff, Format, mypy (342 Dateien) grün. Korpus:
  13 Netzkörper (Gewürzdeckel, Wabenhalter, Magnetschaber, Schriftdekor, Kumiko-Schale und
  -Organizer, Carcassonne-Gitter, Topfdeckel, Würfel, `plate_holes.stl`, M6-STEP) und 14 STEP-Körper
  aus `F:\3D Dateien` behalten jeden Merkmalsabdruck; gewählt werden die fünf Magnettaschen des
  Schabers ein fremdes Muster, die Pips zweier Würfelseiten Muster ihrer Seite, Bohrungen sagen ab.
  Prompt neu gezählt: 7 825 Token bei 169 Werkzeugen. Belege:
  `F:\solidon-review-reports\claude-2026-10-04\texturen-zuordnung\`.

<a id="rm-017"></a>

- [~] **RM-017 — Nutfedermaße an realen Aluminiumprofilen prüfen.** Stegdicke und Kammertiefe an je
  einem konkret benannten 2020-/Nut-6- und 3030-/Nut-8-Profil nachmessen und die Nutfeder daran
  prüfen. Abnahme: Hersteller/Profil und beide Messwerte samt Passungsprobe dokumentiert;
  Abweichungen herstellerspezifisch einordnen, nicht aus zwei Proben allgemeine Normmaße ableiten.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-nutfeder-und-zwei-fehler-auf-dem-weg-dorthin-20082026).

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Die Normteiltabelle führt Motedis
  20×20 B-Typ Nut 6 (Steg 1,5 mm, Kammer 4 mm) und 30×30 B-Typ Nut 8 (2,2/6,8 mm); der Kopf folgt
  der sich verengenden Kammer, `taper_to_slot` ist als Wahrheitswert geprüft, die drei alten Größen
  bleiben als ältere Maße. Bibliotheksversion 23; die Migration 43→44 trägt `size=2020` nur nach, wo
  es fehlt. 53 Fälle an beiden Kernen, 360 Einschubfälle gegen die Hersteller-STEP mit 0,0 mm³
  Überschneidung (alte 2020-Kontur 115,4 mm³), Bereichsnachweis 41/41. Am Fenster eingefügt,
  2020→3030, Undo/Redo, Speichern. „Nut 8 wie 3030“ ist gestrichen, 40×40 I-Typ hat 4,5 mm Steg.
  Offen: gedruckte Probe, Wiederöffnen; die Suche „Profilzunge“ findet den Baustein nicht. Beleg:
  `konzepte/nachweise-release-0.5.1/reports/rm017-herstellerprofile-2026-10-03.md`.

  **Teilstand 04.10.2026:** Robert entschied, dass der Nachweis gegen die Hersteller-STEP
  (360 Einschubfälle ohne Überschneidung) als Passungsprobe genügt; eine gedruckte Probe entfällt.
  Die Bausteinsuche findet die Nutfeder jetzt unter „Nutenstein“, „T-Nut“, „Aluprofil“ und in den
  fünf Sprachen unter der Mutter in T-Form; der `doc`-Satz nennt den Unterschied zum Nutenstein
  (`registry.PartRegistry.search` zählt Wörter mit Bindestrich auch als Ganzes, 18 Fälle in
  `tests/test_parts.py`). „Profilzunge“ ist kein Kundenwort. Offen allein das Wiederöffnen eines
  gespeicherten 30×30-Projekts am Fenster beim Release.

<a id="rm-022"></a>

- [~] **RM-022 — Nachbau als Operationsfolge.** Robert hat den Umfang am
  17.09.2026 entschieden: hinter dem Importschritt eine bearbeitbare Folge
  registrierter Operationen aufbauen. 0.4.3 ist am 18.09. veröffentlicht;
  die Umsetzung gehört seit 0.4.4 zum CAD-Plan und wird nach der ergänzten
  Entscheidung vom 23.09. innerhalb 0.5.x abgeschlossen (RM-188). Dem Nachbau geht seit der
  Durchsicht vom 19.09. **P4.0** voraus: der exakte Körper **ohne** Verlauf
  aus Segmentierung, Flächenfits und Nähen — das, was Fusion und SolidWorks
  liefern — als Kandidatenquelle und eigener Kundenweg (STL als STEP
  weitergeben). Keine Zusage für jede STL. Zielkörper,
  Restflächen, Form-/Maßbudget und Abnahme stehen im
  [CAD-Konzept](konzepte/konzept-vollwertiges-cad-2026-09.md) §§8 und 13.5,
  Pakete P4.0–P4.3. Volumen allein genügt nicht: lokale Formabweichung,
  Öffnungen, dünne Wände, Topologie, Vergleichsvorschau und Undo prüfen;
  Fertigungskompensation beim Nachbau ausschalten. Die Umsetzbarkeit der
  vollständigen Kette ist noch nicht durch einen Prototyp belegt.

  **P4.0 gebaut** (23.09.2026, `596bcb64`), Stand und Reste unter RM-188. Die
  Vorbereitung für P4.1 ist gemessen (Bericht p40, `s35_candidates.py`): Jede
  gekrümmte Fläche eines umgewandelten Körpers trägt ein Merkmal und lässt sich
  direkt in eine Operation übersetzen; offen ist die ebene Grundform — der
  Quader der Stützebenen trifft nur Platten mit Bohrungen (+0,00 % bis +0,59 %),
  Stufen und Absätze brauchen eine Zerlegung in Skizze plus Extrusion je Höhe
  (Wedge-Lock +261 %). Das ist die eigentliche Arbeit von P4.1.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#neun-heruntergeladene-modelle-durch-die-ganze-kette-21082026).
  Registerabgleich 02.10.: Bericht p40, `s35_candidates.py`, zeichnenbau und p66 liegen nur im gitignorierten `Releases/0.5.0/Nachweise/` auf einer Maschine — ins Repository holen oder als Aussage in den Punkt.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `scene/rebuild.py` schlägt Folgen
  aus Grundvolumen, Aufträgen und Abzügen vor; `difference.surface_distance_bound` prüft beidseitig
  gegen die gewählte Grenze, jede Ebene und Rundform muss erklärt sein. Prüfbericht → *Modell
  nachbauen* öffnet einen nichtmodalen Vergleich mit Verlustannahme, Übernehmen ist eine
  Transaktion. Claude: `Session.commit_rebuild` reicht die Quellen durch
  (`test_the_session_takes_a_rebuild_of_an_unchanged_linked_source`); kugelige Rundungsecken und
  eine fehlende Tasche sind mit den Sonden der Durchsicht als behoben belegt. 136 Kern-, 23
  Fenster-, 65 Formfälle, zwei Ende-zu-Ende-Wege in 7,2 s. Belege:
  `konzepte/nachweise-release-0.5.1/reports/rm022-nachbau-2026-10-03.md`; unter
  `F:\solidon-review-reports\codex-2026-10-03\`: `bedienung\rebuild-ui.md`,
  `geometrie\erkennung\rm022-review.md`.

  **Teilstand 04.10.2026 (Claude, Zweig `claude/rm-exakt-nachbau`, zusammengeführt in
  `2323082b2`):** *Zapfen mit Kehle:* Mit der tangentialen Trennung aus RM-226 liest das Netz Zapfen
  und Kehle, und der Nachbau nimmt aus der STL dieselbe Folge wie aus STEP
  (`test_a_post_with_a_cove_from_a_mesh_is_rebuilt_like_the_exact_one`; vorher las das Netz eine
  gekrümmte Fläche, Kehle R 2, 3 und 4 angenommen). *Weitere Grundformen:* `scene/rebuild._layered`
  stellt Rundungen und Zapfen längs der Stufenrichtung als Bögen in den Querschnitt; Bohrungen und
  Langlöcher quer dazu und jede Bohrung mit Senkung werden danach ohne Kompensation gebohrt
  (`_drilled`), geschnitten wird der Körper ohne diese Löcher (`_without_holes`).
  `test_rebuild.py::test_steps_and_shoulders_from_a_mesh_are_rebuilt_as_sketches_and_extrusions`,
  neun Formen als binäre STL: vorher 4 von 9 rot (Winkel mit Bohrungen in beiden Schenkeln, Winkel
  mit Kehle und Bohrungen, Stufenplatte mit runden Ecken, Stufenplatte mit Senkung). *Laufzeit:* Das
  Konzept verlangt „abbrechbar und mit Fortschritt“ (§13.5), keine Sekundenzahl.
  `geom.difference.surface_distance_bound` gibt Tochterzellen die Eckwerte der Mutter mit und fragt
  je Teilung sieben statt sechzehn Punkte, an 27 Läufen bitgleich; Lochplatte bei 0,1 mm: Vergleich
  12,8 → 5,1 s, Vorschlag 13,2 → 5,7 s, längste Lücke zwischen zwei Abbruchfragen 0,09 s, unter
  Fremdlast im Wechsel gemessen; `test_difference.py::test_a_divided_cell_asks_only_its_new_points`
  zählt 9 917 statt 20 960 Fragen. Keine Zusage für jede STL: Der Wedge-Lock bleibt eine Ablehnung
  mit Grund. Commits `3c8cd7480`, `84a0d496e`. Belege unter
  `F:\solidon-review-reports\claude-2026-10-04\exakt-nachbau\` (`p6a_kopf.txt`, `p6a_jetzt.txt`,
  `p12a_vorher.txt`, `p12a_nachher.txt`, `p11b_ab.txt`, `p11e_luecken.txt`). Offen allein die
  Fensterabnahme beim Release (RM-213): die acht Fensterschritte, darunter Lochplatte mit
  *Abbrechen* während der Prüfung, Winkel mit Bohrungen in beiden Schenkeln mit Strg+Z nach der
  Übernahme und Stufenplatte mit Senkung Ø 8 ohne Kompensation. Changelog: ja, im vorhandenen Punkt
  zu *Modell nachbauen* ergänzt.

<a id="rm-209"></a>

- [~] **RM-209 — Die Rundform-Einpassung an Gittermodellen: der Löser ist nicht zu langsam,
  sondern wird zu oft gefragt.** An der Kumiko-Schale (94 990 Dreiecke, 7 325 Merkmale, 19,0 s)
  kostet `fit_cone` 12,47 s und damit zwei Drittel der Erkennung; `fit_sphere` 1,69 s,
  `fit_cylinder` 1,30 s, `fit_torus` 0,38 s. Von 1 127 Kegelläufen schöpfen **1 093 die hundert
  Auswertungen exakt aus** und liefern danach `None` — je Lauf 10,07 ms. Die 34 Läufe mit
  Ergebnis brauchen median vierzig Auswertungen und zusammen 0,23 s. Der Aufbau davor ist
  unschuldig: `_surface_support` 0,65 s, `_cone_support_points` 0,22 s, `_ridge_endpoints` 0,17 s.

  **Neun Hebel sind gemessen und verworfen, und das ist der eigentliche Befund.** Alle neun
  ändern die Erkennung oder sparen nichts:

  | Hebel | Wirkung | Warum verworfen |
  |---|---|---|
  | Sieb aus Fleckmerkmalen vor dem Fit | 0,07 s | trifft 7 von 1 093 |
  | `x_scale="jac"` | keine | 300 Läufe anders |
  | Lockere Toleranzen (`eps**0.5`) | 0,66 s von 28 | 243 Läufe anders |
  | Eigener Levenberg-Marquardt in NumPy | 2,4× | 2 045 von 2 272 Läufen anders |
  | Schranke auf den Startwinkel | keine | gültige Kegel starten bei 88,4° |
  | Budget 40 statt 100 | 1,2–2,1× | 10 von 71 Korpusdateien anders |
  | Merker auf `_ridge_endpoints` | 0,9 % | der Abschnitt ist zu billig |
  | Schranke auf die Spitzenwanderung | 0,4 % | vergebliche Läufe bleiben bei Weite 2,66 |
  | Sieb über Residuenzeilen oder Startkondition | 0,0–1,8 % verlustfrei | gültige Kegel haben dieselbe Untergrenze sechs |
  | Sieb über die Normalenspreizung des Flecks | 93 % bei 5° | nimmt 1 217 von 1 302 Formen mit |

  Zwei ältere Sätze gehören richtiggestellt. **Die Kegelspitze wandert nicht ins Unendliche:**
  Gemessen liegt sie in den vergeblichen Läufen bei Weite 2,66 (90 % unter 3,38), in den
  gelungenen bei 0,98 — der Löser divergiert nicht, er kriecht. Und die Unbestimmtheit entsteht
  nicht aus zu wenigen Stützpunkten: Ein Lauf **mit** Ergebnis hat an drei von vier Modellen
  minimal sechs Residuenzeilen, genau so viele wie ein vergeblicher; die Schranke steht in
  `_fit_cone_read` bereits dort, wo sie hingehört.

  **Der zehnte Hebel trägt, und er setzt an der Zahl der Läufe an statt an ihrer Dauer.** Ein
  Gitter besteht aus wiederholten Zellen: An der Kumiko-Schale sind von 1 990 eingepassten
  Flecken nur 445 verschieden, gemessen an der sortierten Menge aller paarweisen Punktabstände —
  **77,3 Prozent sind Wiederholungen**, und 1 515 von ihnen gehören zu einer Klasse, deren
  Vertreter keinen Kegel liefert. Die Kennzahl kostet 0,06 ms je Fleck gegen 10,07 ms je
  vergeblichem Lauf, und sie ist nicht einmal unscharf: Bei einem Nanometer Gitterweite entstehen
  dieselben 445 Klassen wie bei einem Mikrometer, das Muster ist also exakt kopiert. Wer nichts
  geliefert hat, liefert auch am deckungsgleichen Nachbarn nichts — geteilt wird nur das Nein,
  die 34 gelungenen Läufe rechnen weiter einzeln, und damit bleibt jedes gefundene Merkmal Zahl
  für Zahl, wie es ist.

  **Gemessen bringt er 35,6 Prozent, nicht 77.** Von den 21,66 Sekunden der Schale entfallen
  14,56 auf Kegelfits; überspringbar sind 1 325 Flecken mit zusammen 7,71 Sekunden, und die
  Kennzahl kostet 0,26. Bleiben 14,2 Sekunden — ein Faktor 1,53, und damit ist die Abnahme
  „unter fünf Sekunden" **nicht** erreicht. Die Zahl 77 Prozent zählte Flecken, nicht Zeit: Die
  Wiederholungen sind zum Teil billige Flecken, die teuren stehen einzeln.

  Geteilt wird dabei ausschließlich die **Kegelantwort**, und nur wenn sie leer war. Das ist
  nicht Sparsamkeit, sondern Notwendigkeit: `classify` legt auch dann Kandidaten ab, wenn es
  `False` zurückgibt — eine Kugel mit gutem Rückstand landet in `spheres`, ein Ring in `tori`,
  und beide tragen später die Freiformauskunft. Wer den ganzen Fleck überspringt, nimmt sie mit.
  Verlangt man dagegen, dass **kein** Fit etwas geliefert hat, schrumpft die Ersparnis auf 3,6
  Prozent. Mit der leeren Kegelantwort allein geht `classify` in denselben Zylinderzweig wie
  heute, und alles Weitere läuft unverändert.

  Der Preis ist an Körpern ohne Wiederholung zu messen und nicht zu verschweigen:
  `garden-hose-holder.3mf` hat bei 2 744 Flecken **acht** Geschwister (0,3 Prozent),
  `countercleaner.3mf` 13 von 293 — dort kostet die Kennzahl 0,29 s und spart nichts. Sie wird
  deshalb je Fleck gerechnet, wenn `classify` ihn in der Hand hat, und nur für Flecken bis 96
  Punkte — ein Riesenfleck bezahlt sie nie, denn alle paarweisen Abstände kosten quadratisch. Für
  Riesenflecken greift stattdessen die Hautregel aus RM-193.

  **Ein zwölfter Hebel ist verlustfrei und ungleich verteilt.** `classify` fragt den Kegel zuerst
  nicht wegen seines Rückstands, sondern wegen seines Winkels: Liegt er unter `CONE_MIN_ANGLE`,
  geht es in den Zylinderzweig. Der Winkel aber steht **vor** dem Löser fest — `_fit_cone_read`
  liest ihn aus den Normalen und übergibt ihn als sechste Startgröße. Wo der Startwinkel klein
  genug ist, darf der Löser entfallen. Gemessen an `Elegoo_erster_Druck.3mf`: Läufe, die im
  Zylinderzweig enden, starten bei median 0,241 Grad, solche mit Kegelzweig frühestens bei 6,28 —
  eine Schranke bei 5 Grad spart dort **45,6 Prozent verlustfrei**. An `garden-hose-holder.3mf`
  liegt die verlustfreie Schranke bei 0,88 Grad (4,7 Prozent), an der Kumiko-Schale hilft sie
  nicht: Dort starten beide Seiten bei median 87,5 beziehungsweise 88,3 Grad, weil die Schale aus
  fast ebenen Splitterflecken besteht — eine Schranke von unten trifft 21 von 1 127 Läufen (2,8
  Prozent). Eine feste Schranke von 0,5 Grad ist überall verlustfrei und spart 2,7 / 2,7 / 40,6
  Prozent.

  **Der dreizehnte Hebel wäre der schönste gewesen und ist der klarste Fehlschlag.** Die Schale
  besteht aus fast ebenen Splittern: 98 Prozent ihrer Flecken haben weniger als fünf Grad
  Normalenspreizung, median 3,7 — an `Elegoo_erster_Druck.3mf` sind es median 58,4 Grad. Das Maß
  steht vor allen vier Fits fest und kostet 0,02 ms je Fleck. Es trennt trotzdem nicht: Die
  Flecken **mit** Form haben an der Schale median 4,23 Grad, die ohne median 2,63 — die Formen
  liegen also im *oberen* Teil derselben engen Verteilung, und ihre Untergrenze (1,22 Grad) liegt
  unter der der stummen (1,60). Eine Schranke bei fünf Grad spart 93 Prozent und nimmt 1 217 von
  1 302 Formen mit. Der Grund ist die Tessellierung: Wie weit die Normalen eines Verrundungs-
  splitters streuen, sagt etwas über die Zahl seiner Segmente und nichts über seine Form.

  **Eine Einschränkung, die zuerst geklärt werden muss:** Drei der 445 Klassen gehen
  uneinheitlich aus — deckungsgleiche Flecken, bei denen der eine einen Kegel von 45,20 Grad
  liefert und der andere keinen. Eine stärkere Kennzahl trennt sie nicht (gleiche Abstandsmenge,
  gleiche Kantenlängen je Dreieck, gleiche Windung), der Unterschied liegt also nicht im Fleck,
  sondern in seiner Lage im Raum. Das ist RM-210, und solange es offen ist, ist auch das
  Abnahmekriterium dieses Punktes nicht scharf.

  **Gebaut am 22.09.2026, Freigabe Robert („alles abarbeiten"): drei Hebel.** Ein Lauf, der sein
  Auswertungsbudget ausschöpft, gibt nichts zurück; ein Fleck unter `CONE_START_ANGLE` = 0,5 Grad
  bekommt keinen Kegellöser; und deckungsgleiche Flecken teilen die leere Kegelantwort
  (`_rigid_key`). Gemessen an **37 echten Modellen** aus `F:\3D Dateien`, jedes einmal vorher und
  einmal nachher:

  **Die Zeitzahlen dieses Punktes sind zurückgezogen und werden neu gemessen** (22.09.2026).
  Der erste Vorher-Lauf lief von 18:46 bis 18:51 und damit mitten im Korpuslauf der
  Nachbarsitzung, die auf derselben Maschine zwei Unterprozesse über 176 Dateien fuhr. Alle
  Vorher-Zeiten sind dadurch zu hoch, und der gemeldete Median von 1,73× ist nicht falsch,
  sondern **unbekannt**. Aufgefallen ist es an einem Ausreißer: `1x1-bin.stl` stand mit 2,10 s
  vorher und 0,08 s nachher, und derselbe Körper braucht in beiden Ständen ruhig gemessen 0,086
  beziehungsweise 0,078 Sekunden. Die Lehre daraus ist nicht „unter Fremdlast messen ist
  schlecht" — das stand schon fest —, sondern: Eine zu schöne Zahl, für die es auch noch eine
  plausible Erklärung gibt („das ist der Umbau des Kollegen"), wird erst recht nicht
  hinterfragt. Die Erklärung hat den Fehler stabilisiert statt ihn aufzudecken.

  **Die Merkmalsbilanz ist davon unberührt**, denn sie vergleicht Antworten und keine Zeiten.
  Vier der 37 Modelle ändern Merkmale, und zwar nach oben: An
  `Elegoo_erster_Druck.3mf` fallen zwei Verrundungen (R4,2) und ein Kegel weg, dafür kommt eine
  Verrundung mit R2,98 und Rückstand 0,0 dazu; am Gartenschlauchhalter fällt ein Kegel mit
  Rückstand 0,0137 und es kommen eine Verrundung (R7,24) und ein Kegel mit Rückstand 0,0047 dazu;
  an der Kumiko-Schale fällt ein Kegel. Die neuen Merkmale haben durchweg kleinere Rückstände als
  die verlorenen — was wegfällt, stand an der Kippe.

  **Das §31-Ziel bleibt offen.** Die Schale steht bei 12,6 Sekunden, verlangt sind unter fünf.
  1 127 Kegelfits an 1 412 Splitterflecken sind die Aufgabe selbst; wer die fünf Sekunden will,
  muss die Flecken loswerden — also fragen, warum ein Gitter aus 95 000 Dreiecken überhaupt
  1 412 gekrümmte Flecken von median sieben Dreiecken hat. Das ist ein anderer Punkt als dieser.

  Abnahme: das §31-Ziel für 200 000 Dreiecke belegt oder begründet angepasst. Gehört zum
  Leistungsstrang RM-208.

  **Durchsicht v0.5.1 (26.09.2026, erkennung R2):** `_coincident_vertices` merkt sich
  seine Antwort am Netz, `_connected_patches` fragt kleine Flecken sortiert,
  `_circle_pairs` wählt die Kreispaare vor — Kumiko-Schale 24,6 → 14,1 s,
  Meshy-Murmelbrett 349,5 → 342,8 s (unter Last, gleiche Ergebnisse; `6217c57f9`). Zwei
  Hautregeln gemessen und verworfen: die Splitterfläche an der gekrümmten statt der
  ganzen Oberfläche (17 Körper würden Haut, darunter konstruierte Teile mit 16
  Senkungen) und nur Stücke von Gewicht einpassen (33 von 85 Körpern anders, 400 → 944
  s). Was bleibt, sind 42 000 Löserläufe an 167 000 Stücken, 94 davon mit Gewicht.

  **Stand 28.09.2026 (Release 0.5.1, Paket stapel, `53813ec61`, `8e1afee29`, Nachtrag
  `3a83c04af`, Merge `c3636d210`):** Sicher vergebliche Kegel- und Ringläufe rechnet ein
  Stapel vorher (`perceive/refine.py`: SciPys `trf` Zweig für Zweig in NumPy; übernommen
  wird nur das sichere Nein mit Abstand und Schattenlauf, alles andere rechnet der echte
  Löser; `least_squares` ohne SciPys Hülle bitgleich nachgebaut). Korpus 553/553 bitgleich.
  CPU unter Last: Kumiko-Schale 37,6 → 24,9 s, Meshy-Murmelbrett 603 → 472 s; Freiform der
  Leistungstests 13,9 → 13,8 s, Drache 12,8 → 13,3 s, Schiff obj_3 19,4 → 20,9 s (im
  Rauschen) — dort stehen die vergeblichen Läufe in zu kleinen Gruppen für den Stapel. §31
  ist an keinem der fünf Modelle erreicht; den nächsten Hebel je Modell nennt
  `konzepte/nachweise-release-0.5.1/reports/stapel-schluss.md` (Abschnitt „Nicht behoben“).
  Registerabgleich 02.10.: Hebel und Stapel sind gebaut, nach der Legende wäre `[~]` richtig; `f8a42f602` ist am Punkt nicht erwähnt.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `refine._vector_norm` spart die
  allgemeine Normprüfung; 2 539 echte Löseraufgaben aus Kumiko, Drache und Freiform bleiben
  bitgleich in Parametern, Residuen, Jacobi-Matrix, Status und Auswertungszahl, die Löserzeit sinkt
  um 3 bis 10 %, 40/40 Lösertests grün. Die Kumiko-Schale braucht drei kalte Läufe 18,59–20,16 s
  unter Last, verlangt sind unter 5 s. Gemessen und verworfen: kompilierte Schleifenhülle (1–3 %),
  geteilte leere Kugel- und Zylinderfits (Kumiko 12,07/10,18 gegen 11,90/10,33 s). Keine Schwelle
  abgesenkt. Beleg: `F:\solidon-review-reports\codex-2026-10-03\geometrie\erkennung\bericht.md`
  (RM-209/132/193, `baseline.json`).

<a id="rm-132"></a>

- [~] **RM-132 — Freiformerkennung am Ein-Sekunden-Ziel messen.** Am 12.09.2026 gemessen und
  beschleunigt. **Die Zeit lag nicht in den Einpassungen allein, sondern in der Arbeit an
  Flecken, die niemand liest.** Der 200 000-Dreiecke-Freiformkörper zerfällt in **120 610**
  Flecken — eine verrauschte Oberfläche hat sie —, von denen **1 650** die
  `MIN_PATCH_FACES`-Schwelle erreichen. Die Nachtrennung nach Krümmung gruppierte trotzdem
  jeden einzelnen.

  Zwei Änderungen, beide ohne eine andere Antwort:

  * `_fitted` sagt der Nachtrennung über `worth_splitting`, welche Flecken groß genug sind.
    Ein Stück ist nie größer als sein Fleck, ein zu kleiner Fleck kommt an `classify` also
    ohnehin nicht vorbei. **1,400 → 1,075 s.**
  * `_connected_patches` wählt die Nachbarpaare über zwei Felder statt Zeile für Zeile und gibt
    die Gruppen über `tolist()` statt `int()` je Dreieck zurück — 20 und 84 Millisekunden gegen
    4 und 14, hundertzwanzigtausendfach. **1,075 → 1,004 s.**

  | Körper | vorher | nachher | Merkmale |
  |---|---|---|---|
  | Freiform 200 000 Dreiecke (organisch) | 1,400 s | **1,004 s** | 0 |
  | Lochplatte 203 776 Dreiecke (mechanisch) | 0,649 s | **0,508 s** | 10 |

  Stand 22.09.2026 (RM-208): Die Marken gelten den linearen Fits; mit der Verfeinerung an
  Stützpunkten (P1.2) kostet die Lochplatte 1,1 s und die Freiform 3,9 s. Am organischen
  Kundenmodell „washing bowl" (215 073 Dreiecke) ging die Erkennung von 21 auf 9,6 s, als die
  Fächerfrage der zerrissenen Ecken auf einmal statt je Ecke gestellt wurde
  (`_fans_connected`) und deckungsgleiche Ecken einmal je Körper zusammenfielen
  (`_canonical_vertices`); was bleibt, sind die 372 Kegel-, 352 Ring- und 325 Kugelfits.

  Merkmale und IDs an sieben Körpern zeichengleich — die beiden Referenzfälle, `plate_holes`,
  `post_with_fillet`, `plate_countersunk`, `plate_chamfer_and_taper` und `torus_ring`. Nachweis:
  vier Fälle in `tests/test_curvature_split_components.py` und `tests/test_features.py`, vier
  Gegenproben einzeln rot (ohne die Maske, die Regel fest verdrahtet statt über den Parameter,
  mit umgedrehter Fleckenreihenfolge, ohne den leeren Rückweg). Keine Schranke wurde
  aufgeweicht.

  **Und das Ziel ist damit nicht erreicht, sondern angekommen:** 1,004 s sind vier Millisekunden
  über der Sekunde, und das gilt für den **synthetischen** Körper auf dieser Maschine. Der
  organische 197k-Kundenfall stand am 10.09.2026 bei 1,52 s; um denselben Anteil schneller wären
  es 1,09. Was noch darin steckt, ist gemessen: 55 Prozent der verbliebenen Sekunde sind die
  Einpassungen selbst (`fit_torus` 0,33 s, `fit_cone` 0,21, `fit_sphere` 0,10 — über 1 650
  Flecken mit im Mittel sechs Dreiecken), 14 Prozent `body.facets` von trimesh. Beide sind keine
  verschenkte Arbeit: Die Zahl der abgelehnten Kugel- und Ringkandidaten **ist** die
  Freiformentscheidung (`unpublished_round_shapes`), sie lässt sich nicht überspringen. Wer
  weiter will, verarbeitet die Flecken im Stapel statt einzeln — ein Umbau der drei `fit_*`,
  kein Feilen.

  **Zur Entscheidung für Robert:** weiter mit dem Stapelumbau, oder §31 neu fassen. Das Ziel
  nennt heute keine Referenzmaschine und stützt sich auf eine Kugel, die keine Bohrungen hat;
  ein Ziel je Körperart (mechanisch unter 1 s, organisch unter 2 s) wäre die ehrlichere Zusage.
  Eine Bauplanänderung steht nicht ohne Ansage an.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-die-erkennung-wirklich-kostet-04092026).

  **Stand 28.09.2026 (Release 0.5.1, Paket stapel, `53813ec61`, `8e1afee29`, Nachtrag
  `3a83c04af`, Merge `c3636d210`):** Sicher vergebliche Kegel- und Ringläufe rechnet ein
  Stapel vorher (`perceive/refine.py`: SciPys `trf` Zweig für Zweig in NumPy; übernommen
  wird nur das sichere Nein mit Abstand und Schattenlauf, alles andere rechnet der echte
  Löser; `least_squares` ohne SciPys Hülle bitgleich nachgebaut). Korpus 553/553 bitgleich.
  CPU unter Last: Kumiko-Schale 37,6 → 24,9 s, Meshy-Murmelbrett 603 → 472 s; Freiform der
  Leistungstests 13,9 → 13,8 s, Drache 12,8 → 13,3 s, Schiff obj_3 19,4 → 20,9 s (im
  Rauschen) — dort stehen die vergeblichen Läufe in zu kleinen Gruppen für den Stapel. §31
  ist an keinem der fünf Modelle erreicht; den nächsten Hebel je Modell nennt
  `konzepte/nachweise-release-0.5.1/reports/stapel-schluss.md` (Abschnitt „Nicht behoben“).
  An der Freiform: 65 von 274 Läufen sind vergeblich, 27 bis 38 davon erkennt der Stapel;
  der Rest der Zeit liegt woanders.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `refine._vector_norm` spart die
  allgemeine Normprüfung an reellen eindimensionalen Feldern; 2 539 echte Löseraufgaben aus Kumiko,
  Drache und Freiform sind vorher/nachher bitgleich, die Löserzeit sinkt um 3 bis 10 %, 40/40
  Lösertests grün. Gemessen und verworfen: kompilierte Schleifenhülle (1–3 %), geteilte leere Kugel-
  und Zylinderfits (kein wiederholbarer Gewinn). Die 200 000-Dreiecke-Freiform braucht 7,17–7,22 s
  unter Last bei null Merkmalen, das Ein-Sekunden-Ziel ist verfehlt; an den Schwellen wurde nichts
  abgeschnitten. Beleg: `F:\solidon-review-reports\codex-2026-10-03\geometrie\erkennung\bericht.md`
  (RM-209/132/193, `norm-solve-probe.json`).

<a id="rm-166"></a>

- [~] **RM-166 — Ergebnisnetze aus Mesh-Ops an einer STL überstehen keinen Weld.** Gefunden am
  13.09.2026 beim Prüfen der Werkstattfilme: Die exportierte STL nach `resize_hole` (versetzt),
  `move_feature`, `fillet_edges` und `chamfer_edges` gegen ein **eingelesenes** STL war per Index
  dicht, nach dem Verschweißen aber nicht mehr — Solidons eigener Import derselben Datei meldete
  „Das Modell ist nicht geschlossen" (`ingest.not_watertight`, bei `resize_hole` dazu
  `degenerate_removed`); jeder Slicer verschweißt genauso. Dieselbe Platte in float64 gebaut
  blieb durch alle vier Operationen sauber; nach einer STL-Runde (float32) nicht mehr.

  **Der Weld ist behoben (14.09.2026), an zwei Stellen und mit einer dritten, die die zweite
  nach sich zog.** (1) `boolean._tidied` verschweißt die Kernausgabe mit der Schweißtoleranz der
  Diagonale, streicht Dreiecke mit doppeltem Index und unreferenzierte Ecken — übernommen nur,
  wenn das Netz dicht bleibt und das Volumen sich nicht ändert (die Zusicherung von `repair()`).
  (2) `edges.rounding_tool` gibt abziehenden Keilen `flank_overlap=BOOLEAN_OVERLAP`: Die
  Schnittkurve bleibt, die Flanken schneiden Luft statt der fast koplanaren Körperfläche. (3) Mit
  dem Überstand vereinigen sich die zwölf Keilstücke eines Bohrkreises zu einem Werkzeug mit
  Nadeln an den Stoßstellen — roh dicht, und Stufe 2 der Rückfallkette strich sie und riss das
  Werkzeug auf: An `plate_countersunk.stl` (nur verschweißt, dünne Knoten) lief die Kette bis in
  die Voxel, in der Vorschau brach sie ab. `boolean._welded_input` hat seither dieselbe
  Zusicherung wie der Import: Entnadeln reißt kein dichtes Netz auf.

  Gemessen nach dem Fix, Korpus `plate_holes.stl` und die gebohrte Filmplatte (100 x 55 x 8,
  zwei 6-mm-Bohrungen, über eine STL-Runde): alle vier Operationen nach Export und Import
  geschlossen, Volumen unverändert (Korpus 30982,096 / 31322,350 / 31257,969 / 31217,928 mm³),
  die Fase ohne die 29 mm² Haut an den Bohrungsrändern. Was der Import an Nadeln mit drei
  verschiedenen Ecken noch findet, hält er (`ingest.degenerate_kept`) — sie zu streichen risse
  Löcher, und `manifold.simplify` vernetzt ebene Flächen neu. Nachweis:
  `tests/test_export.py::test_a_mesh_op_result_on_an_stl_survives_the_weld` (vier Operationen
  mal zwei Quellen; ohne `_tidied` vier rot, ohne den Überstand die Fase rot) und
  `tests/test_boolean.py::test_the_welded_stage_keeps_a_needle_that_holds_a_closed_tool_together`
  (ohne die Zusicherung rot). Docstring von `BOOLEAN_OVERLAP`, `operationen.md` und
  `geom/CLAUDE.md` sagen seither, dass „robust" nur für exakt koplanare float64-Geometrie gilt.

  **Offen bleiben zwei Dinge, beide außerhalb dieses Rechners.** Das **Flackern derselben Kette
  auf dem Linux-Runner** (Tag-Läufe von v0.4.1, 13.09.2026):
  `test_a_nonorthogonal_trihedral_corner_has_the_tangent_sphere` war dort in einem von vier
  Läufen rot — die Kugelhaube stimmte (jede Distanz 2,99 bis 3,0), ein einzelner Punkt im
  Normalenkegel lag bei 6,526. Lokal zwölf von zwölf grün, macOS und Windows in jedem Lauf grün.
  Ein Geometrietest, der flackert, verletzt Regel 9; die nicht strenge Marke auf Linux hält den
  Bau nicht auf und verschweigt den Fall nicht. Abnahme: Ursache auf einem Linux messen
  (Reihenfolge der Hüllendreiecke, Threading des Booleschen Kerns, Restdreieck der Flanke) und
  den Test dreimal in Folge ohne Marke grün — mit dem Weld-Fix noch einmal von vorn, denn
  `_tidied` ändert die Dreiecksfolge der Ausgabe. Und das **Beispielarchiv der Werkstattfilme**
  (`marketing/video/workshop-2026-09/build_examples.py`, nicht im Repository): Die beigelegten
  STLs stammen aus den Aufnahmen vom 13.09. und tragen den alten Fehler; sie neu zu erzeugen
  heißt, die Aufnahmen mit dem gefixten Code zu fahren und das ZIP neu zu verpacken — ein
  Produktionsschritt, der zusammen mit der nächsten Filmrunde läuft.

  **Durchsicht v0.5.1 (26.09.2026):** Werkzeuge und Eckanschluss rechnen plattformgleich
  — Längen über `math.hypot`, Skalarprodukte über `units.dot3`, Winkel über
  `mesh.stable_arccos`, kleine Gleichungssysteme nach Cramer statt LAPACK, die Kugel
  über `_icosphere`; `test_platform_identity` fährt Verrunden und Fase an der schiefen
  Tetraederecke mit ULP-Rauschen und getauschtem BLAS-Kern (`9bc3d354e`). Offen bleiben
  die Marke `xfail(linux)` (fällt nach drei grünen Linux-Läufen in Folge) und das
  Beispielarchiv.

<a id="rm-184"></a>

- [~] **RM-184 — Dateiaudit vollständig umsetzen.** Grundlage sind 187 einzelne
  Modell-, Projekt- und Zeichnungsfälle aus `F:\3D Dateien` sowie ihre Begleitdateien.
  Die lokalen Nachweise liegen unter `ui-audit/2026-09-15-files/`.
  Robert hat den Umfang am 16.09.2026 auf den Abschluss der begonnenen Einheiten
  begrenzt und anschließend die vollständige Veröffentlichung von 0.4.3 beauftragt.
  Der vollständige Auftrag vom 03.10.2026 umfasst jetzt auch die übrigen Familien
  und die vollständige Einzeldateiabnahme. Die damalige Zurückstellung gilt
  dafür nicht mehr; offene Abnahmen bleiben bis zum Nachweis offen.

  **Abgeschlossen mit 0.4.3** (ein Punkt der Roadmap ist ein Kästchen — die
  Einheiten darunter tragen keines):

  - Bohrung mit Senkung/Einlauf maßhaltig bearbeiten, Sackbodenkennung erhalten,
    vollständige Vorschau und eindeutige Auswahl; gezielte Original- und UI-Gegenproben.
  - Flache Sackbohrungen, kleine Kontaktflächen und kurze Gewinde erkennen;
    örtliche Erkennung großer Netze mit anschließender Bearbeitung in einer Transaktion.
  - ZIP-Doppeleinträge, SVG-Vorgaben und sichtbare SVG-/DXF-Konturauswahl;
    versionierte GLB-/GLTF-Einheiten und Aufrichtung.
  - Projektparameter bis in Bausteinskizzen und Platzierungsvorschauen verfolgen;
    Organizer mit gebundenen Fachmaßen, einzelnen Trennwänden und vier Bausteinen.
  - Loch-, Langloch- und Wabenfelder mit gezeichnetem Bereich, Ausschlüssen,
    Randabstand und Mindeststeg; Einstieg aus freier Zeichnung in der Oberfläche.
  - Profilklemme aus zwei Schalen und zwei Einlagen, ausdrückliche Materialwahl,
    runde/ovale/gezeichnete Gegenkontur und Austausch bei unveränderten Schalen;
    Bereichsprüfung und nativer Erzeugen-/Ersatz-/Undo-/Redo-Weg. Die Schale
    allein sitzt seit dem 16.09.2026 bei null; den Bundfreiraum setzt das Paar.
  - Dichtnut mit separater Dichtung aus Zeichnung oder bestätigter Öffnung,
    Materialrollen, Restwand und optionale Gegenfläche.
  - Anschlussprüfungen, Übersetzungen, Dokumentation und Auslieferung 0.4.3.
    Das vollständige lokale Tor entfiel auf Roberts ausdrücklichen Wunsch; die
    Suite lief in der CI auf allen Plattformen vor dem Paketbau.

  **Noch offen:** der abschließende native Ablauf der Dichtnut am Fenster
  (Zeichnen, Öffnung wählen, Gegenfläche, Übernehmen, Undo) mit Bildnachweis.

  **Durchsicht v0.5.1 (26.09.2026, reparatur):** Kern und Verlauf nachgemessen, wie der
  Dialog mit gewählter Öffnung sie anlegt (Träger PETG, Dichtung TPU 95A): An
  `Side kit rest 3 Ø36.stl` entstehen auf der Oberseite (Öffnung 597,6 mm², Versatz
  4 mm, Nut 1,6 × 1,2 mm) in 1,4 s Nut und getrennte Dichtung, beide dicht
  (183 662,75 → 183 213,76 mm³, Dichtung 327,39 mm³); Strg+Z stellt den einen Körper
  her, Wiederherstellen dieselben zwei. Sieben weitere Körper aus `F:\3D Dateien` lehnen
  zu Recht mit Satz und Feld ab (Dosenränder von 1,3 mm, Töpfchen, Gitter, Keil).
  Offen bleibt der Ablauf am sichtbaren Fenster mit Bildern; er braucht einen
  gerenderten Lauf und gehört in die Release-Abnahme (RM-213).

  **Im laufenden vollständigen Auftrag ebenfalls abzuarbeiten:**

  - Native Einzeldateiabnahme aller 187 Fälle einschließlich aller 29
    Drillholder-Bohrungen: Import, Erkennung, Maßänderung, Vorschau, Ergebnis,
    Undo/Redo und je eigener Bildnachweis. Kernläufe ersetzen diese Abnahme nicht.
  - Einheitliche abschließende Leistungsreihe, erstes sichtbares Modell und
    getrennte Stufenmessung.
  - Puppenhaus-/Schrankparameter sowie Mehrdateien und Plattengruppen.
  - Weitere funktionale Gruppen: Kammer, Gewinde/Einlauf, Bajonett/Rastung,
    Dichtweg/Kanal, Scharnier, Schrift/Einlage und Steckaufnahme/Anschlag.
  - Bausteine: Bajonettpaar, Rastdrehscheibe/Federnabe, Steckhülse und
    Zwei-/Drei-/Vierwegeverbinder, Schlauchtülle, Kanalnaht/Rampe, Raum-/Plattenvorlage.
  - Abläufe: Konturdeckel mit Scharnier/Stift, bündige Schrifteinlage,
    Gegenformeinsatz, Passungsprüfausschnitt, importiertes Gewinde ersetzen,
    Schrift auf Fläche/Bahn sowie drehender und kombinierter Fügeweg.
  Registerabgleich 02.10.: Der Punkt verweist auf das gitignorierte `ui-audit/`, das es nur auf einer Maschine gibt — Belege ins Repository holen oder als Aussage in den Punkt.

  **Teilstand 04.10.2026 (Claude, Zweig `claude/rm184-bausteine`, zusammengeführt in `8dd42e47c`),
  Teil Bausteine:** Die sieben Bausteinfamilien des Punkts stehen als acht geprüfte Bausteine im
  Katalog, in vier neuen Modulen unter `app/core/knowledge/parts/`: `closures.py`
  (Bajonettverschluss `bayonet` und Rastdrehscheibe `detent_disc`, je ein Paar über `kind`),
  `rods.py` (Steckhülse und Zwei- bis Vierwegeverbinder `rod_connector`), `channels.py`
  (Schlauchtülle `hose_barb` mit Durchgang durch die Trägerwand, Kanalnaht `channel_joint` als Hülse
  außen oder Einlage innen mit Verengungsbefund) und `panels.py` (Raumboden, Raumwand,
  Fensterscheibe als Nut-und-Feder-Platten). Jeder baut in beiden Kernen (`ops.EXACT_PARTS`,
  Paritätstabelle, `test_exact_parts.py` mit Analytik, Netzvergleich und STEP-Rundreise) und wird in
  Einbaulage über seinen Weg geprüft (`tests/test_parts.py`): Bajonett ein und gedreht ohne
  Durchdringung, danach Anschlag und Halt gegen Zug; Rastscheibe in jeder Stellung frei, Stellung k
  gibt genau Öffnung k frei; Stangen bis zum Anschlag ohne Berührung (der Quell-Eckverbinder
  überdeckt sich um 23,4 mm³); Rinnensegmente bis zum Steg, Kanal durchgehend frei; Raum aus Boden,
  Rückwand und zwei Seitenwänden ohne Durchdringung. Projektmaße koppeln die Familie: Stab 16 → 20
  mm dreht alle Aufnahmen zweier Verbinder, Raumlänge 240 → 300 mm Boden, Rückwand und Nuten; Strg+Z
  nimmt Maß und Schritte zurück. Bereichsnachweis 49 von 49, nach den Merges in `7b3d8057e` neu
  gefahren; zwei rote Erstläufe behoben (Federarmring am Netz 0,798 < 0,800 mm, Selbstdurchdringung
  der breiten Einlage). Bibliotheksversion bleibt 23, kein bestehender Baustein ändert ein Maß.
  Tests: `test_parts.py` 763 grün (25 neue), `test_parts_catalog.py` 89 (6 neue),
  `test_exact_parts.py` 22 neue, Paritätstabelle 23 neue, `test_platform_identity.py` ein neuer Weg;
  Entwicklungstor nach der Zusammenführung 23 342 grün, Exit 0. Commits `af7c66c19`, `65b37a4a3`.
  Belege, Vergleich mit den Auditdateien und Vorschaubilder unter
  `F:\solidon-review-reports\claude-2026-10-04\rm184-bausteine\`. Damit ist die Zeile „Bausteine“
  der Liste oben erledigt. Offen: die Abläufe, die funktionalen Gruppen, Puppenhaus- und
  Schrankparameter samt Mehrdateien und Plattengruppen, die Leistungsreihe, die native
  Dichtnutabnahme und die Einzeldateiabnahme aller 187 Fälle (eigene Aufträge laufen); für die acht
  Bausteine die Fensterabnahme beim Release (RM-213) je Sprache: Katalogtexte und Vorschaubilder,
  Bajonett- und Rastscheibenpaar mit Undo/Redo, Stangenverbinder mit Projektparameter 16 → 20, Tülle
  mit offenem Durchgang im Schnitt, Kanalnaht-Einlage mit Verengungssatz, Raumplatten mit Raumlänge
  und *Auf dem Bett anordnen*. Changelog: ja, zwei Punkte unter den neuen Bausteinen.

  **Teilstand 04.10.2026 (Claude, R2 Abläufe, `claude/rm184-ablaeufe`):** Sieben Abläufe aus
  `bericht.md` §9 und `ancillary-analysis.md` §§3, 6, 9, 10 sind umgesetzt, wo möglich als
  Erweiterung vorhandener Operationen: *Fügeweg prüfen* (`motion`: geschoben, gedreht, geschoben und
  gedreht; Drehmitte wie bei Muster und Spiegeln), *Prüfstück erzeugen* (nimmt jedes gewählte Teil,
  Fenster an der genannten oder engsten Stelle, Spiel im Ausschnitt gemessen, Stücke nebeneinander
  auf dem Bett, `cache_version` 2 → 3), *Text aufbringen* (Bogen `arc_radius`, Rundung `wrap` mit
  Radius aus dem Merkmal), *Merkmal ändern* am Gewinde (Wandmessung, Absage `thread_wall`, Befund
  `thread.thin_wall`, `cache_version` 16 → 17; Gegengewinde einer Gewindepassung geht in derselben
  Transaktion mit, an Fenster, Kommandozeile und Agent über `counterpart.with_coupled_threads`),
  *Deckel erzeugen* (`hinge`: ohne, mitgedruckt, mit Stift; Kragenbeschnitt für freies Öffnen). Neu,
  weil keine vorhandene Operation passt: *Schrift einlegen* (`inlay_text`), *Gegenform einlassen*
  (`cut_counter_form`), *Stift für Bohrung* (`pin_for_bore`). Nebenbei behoben: `History` vergab
  nach einem Entwurf mit eigenen Ausgangskennungen dieselbe Kennung ein zweites Mal (gefunden am
  Deckel mit Stift, Test `test_history.py::test_a_named_new_body_moves_the_numbering_past_it`). Neue
  Tests: `tests/test_join_motion.py`, `test_fit_test_piece.py`, `test_label_layout.py`,
  `test_counter_form.py`, `test_thread_replace.py`, `test_hinged_lid.py`, dazu Fälle in
  `test_exact_body_parity.py` (`inlay_text`, `cut_counter_form`, `pin_for_bore`),
  `test_platform_identity.py` (Wege `bent_lettering`, `fit_pieces`, `counter_form`, `hinged_lid`),
  `test_history.py`, `test_operation_ui.py` (Fenstertest, Release). **Vorher rot / nachher grün:**
  Am Basisstand `7b3d8057e` (Schnappschuss per `git archive`, neue Testdateien hineinkopiert) sind
  29 Tests rot und zwei Testmodule scheitern am Import (`rot-am-basisstand.txt`); die Wand- und
  Scharniertests einzeln ohne die neuen Importe: 22 rot, 3 grün (`rot-am-basisstand-2.txt`) — die
  drei grünen sind gewollte Gegenschutztests (kein Wandbefund am massiven Bolzen, Deckel ohne
  Scharnier unverändert). Am Stand `1e85ac079` sind alle grün (Läufe unten). Belegpfade:
  `F:\solidon-review-reports\claude-2026-10-04\rm184-ablaeufe\rot-am-basisstand.txt`,
  `…\rot-am-basisstand-2.txt`, `…\f_run2.txt` (3231 passed), `…\g_run3.txt` (3729 passed vor zwei
  behobenen Zuordnungen), `…\g_run4.txt`, `…\g_run5.txt`, `…\tor-1.txt` (Entwicklungstor),
  `…\vergleich-gewinde.txt`, `…\vergleich-konturdeckel.txt`, `…\probe-keep.txt`,
  `…\probe-nokeep.txt`, `…\probe-brep.txt`, `…\prompt-tokens-3.txt`.

  **Nachtrag Gewindepaar:** Ein gespeicherter Gewindeschritt koppelt beim Ändern sein Gegengewinde
  in derselben Transaktion (`counterpart.coupled_step_change`, `482fd788a`). Das gedruckte
  Gewindepaar aus *Gegenstück zum Gewinde* meldete seine Passung beim Anlegen als verletzt, weil
  beide Merkmale das Nennmaß nannten (seit `d92f33ddf`, v0.5.0 und v0.5.1); gedruckte Gewinde nennen
  jetzt das gebaute Maß samt `nominal`, die Gewindepassung erwartet das Spiel beider Hälften (PETG
  gemessen 0,50 = Soll 0,50 mm; `72f68db6b`, Regel in `.claude/rules/kern.md`). Belege unter
  `F:\solidon-review-reports\claude-2026-10-04\rm184-ablaeufe\`.

<a id="rm-188"></a>

- [ ] **RM-188 — CAD-Ausbau, Bedienung und Resin für 0.5.x.** Netz und exakter
  Körper sollen gleich bearbeitbar und erkennbar sein, ohne Kernwahl in der
  Oberfläche (Robert, 17.09.2026); dazu der volle Ausbau („alles“, 18.09.) und
  seit dem 23.09. Montageorganisation, Maßblätter und die vollständige Zuordnung
  von vier Konzepten. Verbindlich sind Pakete, Voraussetzungen, Reihenfolge und
  Entscheidungen im [CAD-Konzept](konzepte/konzept-vollwertiges-cad-2026-09.md)
  §§13.2, 13.6, 13.10 und 14; Anschlussverträge und Belege der ersten
  Entwicklungswoche stehen in der [Übergabe](konzepte/uebergabe-cad-2026-09-20.md).
  Die vier Quellen: das CAD-Konzept (P0–P8), das
  [Bedienkonzept](konzepte/konzept-bedienung.md) (P0.7, P0.3/P0.4/P5.1 und alle
  geltenden Anforderungen in P5.2/P5.3), die
  [CAD-Durchsicht](konzepte/durchsicht-cad-konzepte-2026-09.md) (über Konzept
  §14.3 und P0.8) und das [Resin-Konzept](konzepte/konzept-resin-2026-08.md)
  (Stufe 1 aus [RM-071](ROADMAP-ARCHIV.md#rm-071), Stufe 2 in P9). Der Nachbau
  steht unter [RM-022](#rm-022), die Fenster- und Plattformnachweise unter
  [RM-183](#rm-183) und [RM-187](#rm-187). Teilstände erscheinen in einzelnen
  0.5.x-Versionen; der Punkt bleibt einer, bis P5.3 grün ist. Tagesstände,
  Testzahlen, die Fensterabnahme vom 21.09., das Review seit 0.4.4 und die
  Tabelle der Paketstände für 0.5.0 stehen im
  [Archiv](ROADMAP-ARCHIV.md#cad-ausbau-bis-051-der-weg-von-rm-188-29092026).

  **Stand mit 0.5.1.** Die gebauten Pakete sind mit 0.5.0 veröffentlicht
  (`v0.5.0`); 0.5.1 hat Befunde an ihnen behoben, aber keinen Paketstand
  geändert. *Implementiert* heißt: Kern, Eingabewege, Texte und Entwicklungstor
  grün, offen ist die Release-Abnahme mit Fensterdateien, Leistung und
  installierten Plattformen ([RM-213](#rm-213), am Ende P5.3). *Erledigt* heißt
  ein Paket erst nach seiner Abnahme (Konzept §13.10).

  | Paket | Stand | Beleg |
  |---|---|---|
  | P0.0 Merkmale beim Spiegeln, Skalieren und Mustern | erledigt 19.09., mit zwei nativen Kundenwegen abgenommen | `cfc5e303` |
  | P0.1 Positions-Dreier, Einzahltexte, Gründe gesperrter Knöpfe | implementiert | `064e3095` |
  | P0.2 Konvertierung vor der Übernahme benannt | implementiert | `77223ccb`, `064e3095` |
  | P0.3 Maßeditor im Bild | läuft: Bohrungsweg beider Kerne | `852de666`, `1fc131a6` |
  | P0.4 Bezüge zum Ausrichten | läuft: Kanten, Mitten, Langlochachsen | `102d4bf7` |
  | P0.5 Werkzeugauswahl · P0.6 native Schnittstelle | erledigt 20.09. · derzeit ohne Bedarf (Konzept §13.8.1) | — |
  | P0.7 Absturzschutz, Quittung am Handlungsort, gemeinsames Aufsetzen | implementiert | `7aaa993d`, `b9b96a91`, `47023b53` |
  | P0.8 Abgleich der vier Konzepte | offen | — |
  | P1.1 Zylinder- und Langlochmaß an der Kontur | implementiert | `db7d1a5c` |
  | P1.2 Kegel, Kugel und Ring an Stützpunkten | implementiert; die Laufzeit an der Freiform steht unter [RM-132](#rm-132) | `851f913a`, `e66c246d`, `e5ac389a`, `385f9c31` |
  | P1.3 Passung mit Körperprobe, Maßherkunft | implementiert | `db7d1a5c`, `851f913a`, `eeadc09b`, `912789f7`, `f64e17c7` |
  | P1.4 räumliche Zuordnung, Merkmalsgrenze, native Neuwahl | implementiert: P1.4a–c, Grenze 5 000 | `d483e1477`, `fe17cd3bc`, `875c40334` bis `c49747238`, `d3e7fc30` |
  | P1.5 gemeinsamer Merkmalsvertrag beider Kerne | implementiert | `e39dca21a` bis `7f4587267` |
  | P1.6 Analysekarte „Formabweichung“ | implementiert | `5d451fe7` |
  | P2.1 affine Transformationen exakt | implementiert | `77223ccb`, `3355dbf5` |
  | P2.2 Filament am exakten Körper | implementiert | `3df89b8e`, `54f922e0` |
  | P2.3 kanonische Träger aus NURBS | läuft: Ebene, Zylinder, Kegel, Kugel, Ring, Innenraum | `3bdaa788`, `a85cc872`, `93979914`, `851f913a`, `3355dbf5` |
  | P2.4 Merkmalshandlungen am exakten Körper | implementiert | `7718fa356` bis `5f5ab636`, `00b09a2d` |
  | P2.5 importierte Gewinde lesen, beide Kerne | implementiert | `067026d4`, `d319fd80`, `3355dbf5`, `3fa7d719` |
  | P2.6 Ring und Gewinde ändern, Filament, Gegenstück | implementiert | `071cfe18`, `3c1317a9`, `d93c09e5`, `d92f33dd`, `00b09a2d` |
  | P2.7 alle 35 Bausteine am exakten Träger exakt | implementiert | `f08500aa` bis `62f30c81`, `f3423a81` |
  | P2.8 Kernwahl-Haken entfernt | implementiert | `6a4918b5`, `3355dbf5` |
  | P3.1 Ebenenvertrag | implementiert | `02b93253` |
  | P3.2 abgeleitete Ebenen in allen Verbrauchern | teilweise | `a1b9b735`, `f19a7b4b`, `56f70000` |
  | P3.3 „Neue Ebene …“ · P3.4 Flächenkontur | implementiert | `f19a7b4b` |
  | P3.5 exakter Ebenenschnitt | implementiert | `3355dbf5` |
  | P4.0 Netz → exakter Körper ohne Verlauf | implementiert | `596bcb64` |
  | P4.1–P4.3 Nachbau | offen, unter RM-022 | — |
  | P5.1–P5.3 Maßeditor überall, Bedienabnahme, Gesamtabnahme | offen | — |
  | P6.1 variable Verrundung · P6.4 Formschräge | implementiert; Grenzen unter [RM-230](#rm-230) | `e1616285` |
  | P6.2 Fase mit zwei Abständen oder Abstand und Winkel | implementiert | `00b09a2d`, `cf2fe7d3` |
  | P6.3 Aushöhlen mit gewählten Öffnungsflächen | implementiert | `edf07816` |
  | P6.5a–c Schnitt durch Drehen, entlang einer Bahn, durch Überblenden | implementiert | `8d8925cd` |
  | P6.6a/b Ellipse, Splines, zusätzliche Bedingungen | implementiert | `11c429cc` |
  | P6.7 Merkmalsmuster | implementiert | `edf07816` |
  | P7.1–P7.3 Verlauf: einfügen, umsortieren, unterdrücken | implementiert | `677923e5` |
  | P7.4 STEP-Baugruppen mit Namen, Farben und Lagen | implementiert | `896622bd` |
  | P8.1–P8.5 Gruppen, Lagen, Maßblatt | offen | — |
  | P9.1–P9.4 Resin-Stufe 2 | offen | — |
  | Zeichnen Z0/Z1 | implementiert | `4406137f` |
  | Zeichnen Z2–Z6 | offen | — |

  **Offen, mit dem nächsten Schritt** (Reihenfolge nach Konzept §13.10):

  * **P0.8** — je geltender Anforderung der vier Quellen samt Nachträgen den
    Code- oder Abnahmebeleg oder das zuständige Paket festhalten, ersetzte
    Aussagen mit Entscheidungsbeleg kennzeichnen; kein geltender Punkt bleibt
    ohne Zuordnung (Abnahme Konzept §13.2). P5.2 und P5.3 hängen daran. Nächster
    Schritt: die Matrix mit Quellabschnitt, Entscheidung, Paket oder
    RM-/Archivbeleg und verbleibender Abnahme anlegen, zuerst für das
    Bedienkonzept samt Nachträgen, weil P5.2 es abnimmt.
  * **P0.3 und P0.4** — offen: die Abnahme des Maßeditors über Felder, Griffe,
    Gruppen und Merkmale, die Achsen- und Symmetriebezüge gegen den
    Merkmalsvertrag aus P1.5 und dauerhafte Bezüge mit P3.2. Die Bedienreste am
    Etikett stehen unter [RM-197](#rm-197), [RM-199](#rm-199) und
    [RM-200](#rm-200). Nächster Schritt: diese Abnahme am Bohrungsweg als Tests je
    Kern; danach führt P5.1 die übrigen Maßfamilien auf denselben Editor.
  * **P2.3** — offen: die vollständige Semantik- und Teilflächenparität gegen die
    Netz-Zwillinge (Nähte, Teilflächen, zusammengesetzte Merkmale). Nächster
    Schritt: die Gegenfälle aus P1.5 an NURBS-Zwillingen der Korpuskörper fahren
    und jede Abweichung als Test festhalten.
  * **P2.5** — ohne Referenzkörper bleiben Gewinde, deren Flanken ohne scharfe
    Kanten modelliert sind (die Wendel müsste aus Flächenisolinien gelesen
    werden), und ein fremdes Hersteller-STEP mit modelliertem Gewinde
    ([Nachweise](konzepte/nachweise-cad-p2-5/README.md) §8.1). Nächster Schritt:
    ein solches Hersteller-STEP beschaffen und in `tests/data/threads/` aufnehmen.
  * **P2.8** — die Erzeuger ohne Eingang rechnen weiter am Netz und sagen es
    (`shapes.mesh_only`): Organizer, Text, Zeichnung, zehn eigenständige
    Bausteine und der Klemmensatz. Wartet auf Robert: den Mechanismus; empfohlen
    ist ein beim Anlegen gesetzter Kernparameter.
  * **Netz-Kugel nach Größe** — `create_sphere` erzeugt mit `segments=32`
    unabhängig vom Durchmesser 320 Facetten, bei 70 mm Durchmesser etwa
    0,3–0,4 mm Sehnenabweichung statt `units.MAX_FACET_SAG = 0,05 mm`
    (Durchsicht formen am Handschmeichler). Robert hat die Änderung auf nach
    0.5.0 gelegt, weil sie jede Netz-Kugel in bestehenden Projekten betrifft; ihre
    Voraussetzung P2.8 steht. Nächster Schritt: die Unterteilung aus Größe und
    zulässiger Abweichung herleiten, gespeicherte Schritte, Beispiele und Korpus
    mitprüfen. Abnahme: die Abweichungsgrenze über den Größenbereich belegen und
    die Folgen für bestehende Projekte erklären.
  * **P3.2** — offen: Flächen, die eine spätere Operation teilt (Zuordnung
    §21), und dauerhafte Bezüge beim Neuverknüpfen (`scene/orphans.py`). Nächster
    Schritt: eine Skizze auf einer Versatzebene über einer Fläche, die ein
    späterer Schritt teilt, als Test an beiden Kernen.
  * **P4.0** — offen: Nachbau-Tests für die zwei Nähbefunde aus dem Bau
    (Bericht p40 in `Releases/0.5.0/Nachweise/`) und die Paketprobe, dass die
    Umwandlung im gebauten Paket läuft — `brep/from_mesh.py` und
    `brep/canonical.py` laden `OCP.GeomAPI` und `OCP.GeomAdaptor`, die
    ausdrückliche OCP-Liste in `packaging/solidon3d.spec` nennt beide nicht.
    Wartet auf Robert: Handkorrektur der Bereiche am Modell und exakte Körper im
    Plattencache.
  * **P6.3** — offen: ein exakter Weg für verrundete Kunden-STEPs
    (`MakeThickSolidByJoin` scheitert an allen drei gemessenen Teilen, bedienbar
    über den erfragten Rasterweg), Öffnungen am Netz nur an ebenen Flächen,
    Entlüftung je getrenntem Hohlraum mit P9.3. Nächster Schritt: eine Alternative
    nach Konzept §13.8 an den drei Teilen messen.
  * **P6.5a–c** — offen: der Einstieg am Merkmal (die Nut hat kein `applies_to`,
    gehört zu P5.1); der Erzeuger `sketch_loft` entscheidet einen Gleichstand
    weiter still über OpenCASCADE, wo `sketch_loft_cut` fragt; Bauplan §30.1 nennt
    die drei Schnitte noch nicht (nur mit Ansage Roberts).
  * **P6.7** — Frage an Robert: Eine spätere Maßänderung an einer
    **eingelesenen** Quelle hängt sich hinter das Muster; heute trägt „Auf alle N
    gleichartigen anwenden“, sauber wäre P7.1 oder eine vorbelegte Gruppe.
  * **P7.1–P7.3** — offen: der Namenserhalt am exakten Körper
    ([RM-218](#rm-218)) und am Netz eine Erkennung, die an der Vorgeschichte
    hängt: Am Besenhalter ist eine Durchbohrung Ø 4 in y bei x = −25 durch drei
    Wände direkt nach dem Import eine erkannte Bohrung mehr als nach *Bohrung
    vergrößern* an `hole_3`, bei gleichem Volumen; die Wand bei y = 0 gilt nur im
    ersten Fall als Bohrung. Nächster Schritt: diesen Fall als Test. Wartet auf
    Robert: ein Agentenwerkzeug `edit_history` (gezählt 120 Token gebündelt gegen
    224 für drei getrennte).
  * **P7.4** — wartet auf Robert: Farbvorrang, Name eines einzelnen Körpers,
    Export mehrerer Körper als eine Baugruppe, Leistung großer Baugruppen (ab
    etwa 1000 Instanzen 70 s) und Filamentvorschlag je Farbe.
  * **P4.1–P4.3** — unter [RM-022](#rm-022); nächster Schritt P4.1: die ebene
    Grundform eines umgewandelten Körpers in Skizze und Extrusion je Höhe zerlegen.
  * **P8.1–P8.5** — benannte Gruppen mit stabiler Mitgliedschaft (Ersetzen,
    Teilen, Löschen, Passungsbezüge, Undo, Wiederöffnung), getrennt gespeicherte
    Montage- und Drucklagen, ihre Bedienung mit dem vorhandenen Ausrichten,
    Kollisions- und Fügewegprüfen, dann Maßblattvertrag und PDF-Maßblatt mit
    Vorschau, Teilnamen, Einheit und eindeutiger Modellstandkennung (Konzept
    §13.11). Keine Gelenke, kein allgemeiner Baugruppenlöser, keine assoziative
    Zeichnungsverwaltung; die Ansichtsexplosion bleibt Darstellung. Nächster
    Schritt: P8.1, der Gruppenvertrag nach §13.11 A.
  * **P9.1–P9.4** — Resin-Stufe 2 nach Resin-Konzept §§5–11: Stufe 1 belegen und
    die technischen Restentscheidungen festlegen, Saugglocken samt
    Orientierungssuche, Abfluss- und Belüftungsöffnungen nach Drucklage am
    vorhandenen Aushöhlen-Weg, verfahrensbezogene Regeln mit durchgehendem
    Kundenweg; FDM-Verhalten, Slicer-Übergabe und Aushöhlen werden mitgeprüft.
    Kein eigener Slicer, keine Stützenerzeugung, keine Belichtungsprofile.
    Nächster Schritt: P9.1.
  * **Zeichnen Z2–Z6** — Z2 Erstellen im Bild (Palette am Umriss statt Dialog,
    Drehachse gemeinsam mit P6.5), Z3 Bemaßen und Fang, Z4 Auswählen, Verschieben
    und Drehen (Links-Ziehen zeichnet), Z5 Werkzeuge mit P6.6a (900-Punkte-Grenze
    der Leiste), Z6 Ansicht und Texte, danach die Handbuchseite „Zeichnen“ einmal
    neu. In den Umbau gehören die sechs Hinweise aus P6.6: Werkzeugzeile mit 872
    von 900 Bildpunkten voll, Entf löscht bei einem gewählten Splinepunkt das
    ganze Element, der Hilfspunkt einer Tangente ohne Stoß bleibt sichtbar,
    Ellipsenachsen nur als Punktabstand bemaßbar, Laufrichtung des Ellipsenbogens
    beim Zug unsichtbar, lange Bedingungszeile bei zwei Kurven. Reihenfolge und
    Abnahme je Etappe:
    [Bedienabnahme Zeichnen](konzepte/nachweise-release-0.5.0/reports/zeichnen-bedienung.md)
    §8, dazu die Berichte zeichnenbau („Vorschlag Etappe 2“) und p66 („Für den
    Zeichnen-Umbau“) in `Releases/0.5.0/Nachweise/`. Nächster Schritt: Z2.
  * **P5.1–P5.3** — P5.1 stellt die Maßoperationen familienweise auf den
    Maßeditor im Bild um (Bohrung und Platzierung, dann Bewegen, Drehen und
    Skalieren, dann die übrigen Merkmals-, Form- und Bausteinmaße) und nimmt
    danach die Doppel in Panel und Dialog heraus: Eingabefeld von der Maßlinie
    abgesetzt, ✓/× daneben, „Auf alle N gleichartigen“ unter dem Feld mit
    vollständiger Zielvorschau, Enter genau einmal, Escape ohne Änderung,
    Fokusverlust ohne Übernahme, ein Undo für alle Ziele (Robert, 18.09.; Konzept
    §10.2 und §14.1); der wählbare Anfang einer variablen Verrundung gehört dazu.
    P5.2 nimmt die geltenden Bedienanforderungen aus P0.8 am Fenster ab —
    Auswahlmatrix, kleines Fenster, HiDPI, Themen, Tastatur, Gruppen und Lagen,
    Maßblattvorschau, Resin-Befunde, dazu Sichtbarkeit, DPI, Tastatur und
    Bildschirmleser aus P0.7. P5.3 ist die Abnahme darunter.

  **Abnahme:** Zuerst das Release-Tor mit allen Fensterdateien der Pakete,
  frischem Bereichsnachweis der 35 Bausteine und den Kundenwegen am echten
  Fenster ([RM-213](#rm-213)). Den Punkt schließt P5.3: der installierte Umfang
  auf Windows, macOS und Linux (neue OCP-Aufrufe, gewählte Bibliotheken,
  Lizenzen, Datenrundreise, Fehlermeldungen); die Handlungsmatrizen des Konzepts;
  alle 35 Bausteine mit dokumentierter Anwendbarkeit; korrekte Maße und
  Referenzen nach Änderung, Cache, Undo und Wiederöffnung; die zehn Kundenwege
  aus der [Recherche](konzepte/recherche-cad-paritaet-2026-09.md) §4.3 und die
  Zusatzwege aus Konzept §§13.9 und 13.11 und Resin-Konzept §9; jede geltende
  Anforderung aus P0.8 mit Nachweis und die Erstnutzerprüfung. Keine stille
  Formänderung bei der Erkennung; die Nicht-Ziele aus Konzept §15 bleiben
  ausgenommen.
  Registerabgleich 02.10.: Die tragenden Belege liegen nur im gitignorierten `Releases/0.5.0/Nachweise/` auf einer Maschine — ins Repository holen oder als Aussage in den Punkt (wie RM-347).

<a id="rm-191"></a>

- [ ] **RM-191 — PrusaSlicer verbraucht für dieselbe Übergabe ein Drittel mehr
  Material.** Gemessen am 19.09.2026 an den neun Platten von Roberts Regal
  (Elegoo Centauri Carbon 2, PLA): ElegooSlicer 26 h und 408 g, OrcaSlicer
  404 g, PrusaSlicer 52 h und 555 g — mit denselben Solidon-Werten für Wände,
  Füllung, Stützen und Temperaturen (`slicer_keys.py` übersetzt sie je
  Slicer). Alle drei liefen durch; der Unterschied ist kein Fehler des
  Laufs, aber einer, den ein Kunde am Drucker merkt.

  Offen ist die Ursache: Stützen (Prusa erzeugt sie anders und dichter),
  eine Prusa-Vorgabe, die Solidon nicht überschreibt (Wandzahl je Schicht,
  Deckschichten, Stützdichte, Schürze), oder ein Schlüssel, den die
  Übersetzung für den Prusa-Zweig nicht kennt.

  Nächster Schritt: eine Platte je Slicer schneiden und die G-Code-Kennzahlen
  nebeneinanderlegen (Stützvolumen, Wandlänge, Füllung aus den
  Slicer-Kommentaren); jeden Prusa-Schlüssel, der den Unterschied trägt, in
  `slicer_keys.py` ergänzen und die Gegenprobe (`slicer.filament_differs`)
  darauf ansetzen. Abnahme: Prusa liegt bei Zeit und Material innerhalb von
  zehn Prozent der Orca-Familie für dieselbe Platte.

  **Durchsicht 0.5.0** (`56f70000`): Am Gewürzregal liegt das Material innerhalb
  von 3 %, die Zeit war bei Prusa 1,93-mal so lang wie bei Orca und ist mit
  voller Füllung und Lückenfüllung für beide, Bahnbreite je Orca-Rolle und
  `machine_limits_usage = ignore` auf 1,19 gebracht. Der Rest ist die Bauweise
  des Slicers (Füllanker, Zusatzwände). Das Drittel mehr Material vom 19.09. war
  an einer Platte nicht nachzustellen; der neunplattige Auftrag liegt nicht vor.
  Die Abnahme „innerhalb von zehn Prozent“ ist nur zu erreichen, wenn Solidon
  dort Vorgaben setzt — das entscheidet Robert.

<a id="rm-193"></a>

- [~] **RM-193 — Die Erkennung an einer glatten Generator-Freiform kostet Minuten für null
  Merkmale.** Roberts Drache aus ComfyUI/TripoSG (20.09.2026; 325 244 Dreiecke, wasserdicht,
  eine Komponente, als GLB importiert): `detect` brauchte 482 s und fand kein Merkmal, die
  Anwendung stand so lange bei „Merkmale erkennen“. 264 s davon war die Kerbenschließung vom
  17.09. (`4666e730`), die je Kandidatenmenge über den ganzen Fleck und alle Paare des Netzes
  lief; sie liest jetzt Rand und Nachbarindex (`_rim_of`, `_closes`, `_neighbour_index`), und
  `_connected_patches` je Splitstück fiel von 320 auf 11 s. Was bleibt — 151 s unter Fremdlast
  (18 fremde Python-Prozesse), Ergebnis unverändert null Merkmale: Der Drache ist bei der
  30-Grad-Trennung **ein** Fleck (611 Flecken, einer mit 307 063 Dreiecken), die Nachtrennung
  nach Krümmung macht daraus 27 690 Stücke, und jedes geht durch Zylinder, Kegel, Kugel und
  Torus (`classify` 97 s, davon `_refined_fit` 63 s); `_surface_support` 56 s (1 987 374
  Aufrufe von `_one_vertex_fan`, eine Python-Schleife je Knoten); `_large_facet_faces` 26 s
  (vier `_surface_support`-Läufe über den ganzen Körper und je eine Kegel-, Kugel-, Torus- und
  Zylindereinpassung an 300 000 Dreiecken). Am Ende verwirft `_shapes_on_a_freeform` ohnehin
  alles. Der Freiformkorpus von RM-132 ist **verrauscht** (120 610 Flecken) und deckt die
  glatte Gestalt nicht.

  **Stand nach dem Review (22.09.2026):** `_surface_support` liest die Fächer aller Ecken auf
  einmal (`e66c246d`), die Splitstücke fragen nur die Ringe, an die sie grenzen
  (`_TorusCandidates`), die Flächenrollen prüfen blockweise mit frühem Ende (`_face_roles`),
  und jeder Fit und Nachweis wird je Fleck einmal gerechnet (`remembered`). Der Drache: 482 →
  37,7 s bei gleichem Ergebnis; das Kumiko-Gitter 22 → 19,4 s. Was bleibt, sind 2 275
  Kegelverfeinerungen an Stücken mit 7 bis 50 Dreiecken und 3° Normalenspreizung, deren Achse
  aus den Normalen nicht bestimmbar ist — 12,5 s im Löser für `None`. Ein lineares Sieb davor
  ist gemessen unsicher (Erinnerung „Lineares Sieb vor der Verfeinerung ist unsicher"), ein
  Anfangsrang-Test wäre dasselbe Sieb.

  **Entschieden und gebaut (22.09.2026, Robert: „mach das beste für alle draußen, auch für
  den Zahntechniker").** Nicht die Fassung „kein Split", sondern eine, die den Zapfen behält.
  Das Urteil fällt einmal je Körper, direkt nach `_split_patches_by_curvature` und bevor ein
  Splitstück gelesen ist: Welcher Anteil der Oberfläche liegt in Flecken, die in hundert oder
  mehr Stücke unter einem Tausendstel der Oberfläche zerfallen (`FREEFORM_SPLINTERS`,
  `FREEFORM_PIECE_SHARE`)? Über zwei Dritteln (`FREEFORM_SKIN_SHARE`) ist der Körper eine
  Figur, ein Scan, ein erzeugtes Netz (`Fitted.freeform_skin`, `recognised_as_freeform`) —
  dann werden von diesen Flecken nur die Stücke von Gewicht eingepasst: Zapfen, Verrundung,
  Kugelecke. Darunter bleibt alles, wie es war.

  **Drei Fassungen, jede am Korpus gemessen und die ersten beiden dort gescheitert** — die
  Zahlen stehen in `.claude/rules/schichtanalyse.md`: „der größte Fleck über der Hälfte"
  verpasste die Zauberturm-Figuren (Haut in zwei Flecken zu 44 und 32 Prozent, 93 statt 11 s)
  und machte einen konstruierten Wandhalter zur Freiform (16 → 9 Merkmale); „alle Flecken
  zusammen über der Hälfte, mit Zurückstellen" nahm einem Pool-Rohr mit Gewinde seine sieben
  Verrundungen und zwei Ringe (57 Prozent zerfallende Fläche) und verschob durch die geänderte
  Fleckenreihenfolge die Zylindersuche (zwei Kegel mehr am Gartenschlauchhalter, zwei
  Verrundungen mehr am Beckenreiniger). Die dritte fällt das Urteil vor der Schleife und
  setzt die Schwelle in die gemessene Lücke: Konstruiertes null bis 60 Prozent, Figuren 71 bis
  94.

  Gemessen: Drache 27 577 Stücke, 23 mit Gewicht, 27 554 Splitter; Schüssel 2 683/13/2 670;
  Scan-Körper der Tests 1 712/72/1 640 — gegen Kapsel, Ellipsoid, Buchstabe „S",
  `generated_figure.stl` mit null bis einem Splitter, die keine Haut sind und ihre gerundeten
  Seiten behalten. Der Befund `perceive.freeform` kommt auch mit null weggelassenen Formen,
  und sein Satz behauptet keine Suche mehr, die nicht stattfand (Kataloge in sechs Sprachen
  nachgezogen).

  **Zahlen, alle unter Fremdlast (Release-Lauf der Nachbarsitzung):** Drache 37,7 → 4,2 s
  bei null Merkmalen wie zuvor; Schüssel 7,3 → 3,0 s bei 65 Merkmalen wie zuvor; Korpus
  (`tests/data/meshes`, `_scan_like_blob`, Buchstaben, Kapsel) Merkmal für Merkmal gleich.
  Nachweise: `test_features.py` (`test_a_skin_of_splinters_is_not_fitted_piece_by_piece`,
  `test_a_smooth_body_over_half_its_surface_is_no_skin_without_splinters`),
  `test_evaluation.py` (Befund ohne weggelassene Formen). Regel in
  `.claude/rules/schichtanalyse.md`.

  **Vierte Fassung, am selben Tag, und sie kam aus dem Korpus: erst der Fit, dann das
  Urteil.** Drei Bowlingkugeln aus `BowlingGame.3mf` verloren ihr einziges Merkmal — eine
  Kugel Ø 17,5 über 65 024 Dreiecke, Rückstand 0,0. Eine Bowlingkugel ist **ein** Fleck über
  die ganze Oberfläche, und sie zerfällt nach Krümmung in 662 Stücke, 659 davon Splitter:
  Wer diese Stücke fürs Hauturteil zählt, erklärt eine mathematisch perfekte Kugel zur Haut
  einer Figur, und `is_a_freeform(skin=True)` nimmt sie anschließend weg. Ein Donut, ein
  Kegel, ein Ball — jede Grundform, die ein ganzes Modell ist, zerfällt wie eine Figur. **Nur
  der Fit trennt sie.**

  Der Fehler lag nicht erst in der Beschleunigung, sondern schon in der dritten Fassung, und
  er war reihenfolgeabhängig: Das Urteil fiel beim *ersten* Fleck ohne Form und zählte dabei
  jeden zerfallenden Fleck mit, auch einen, der längst eine Grundform ergeben hatte. Bei der
  Bowlingkugel fiel es nie, weil ihr einziger Fleck sofort eine Kugel ergab — ein Körper mit
  derselben Kugel und einem kleinen unlesbaren Fleck daneben wäre zur Freiform geworden, wenn
  der kleine Fleck zufällig vorne stand. Nachgestellt an einer Kugel auf einem Sockel: glatt
  `sphere`, `pin`, `face`; mit 0,02 mm Rauschen auf 15 mm Radius nur noch `face`.

  `_fitted` läuft deshalb in **zwei Runden** statt einer: erst `classify` über alle Flecken,
  dann die Nachtrennung über die gescheiterten — und **nur deren Fläche** entscheidet über
  die Haut. Das ist dieselbe Regel wie zuvor, nur mit dem Zusatz, der schon in
  `.claude/rules/schichtanalyse.md` stand und im Code fehlte: *Flecken ohne Grundform.* Das
  Urteil hängt jetzt an keiner Reihenfolge mehr, und `worth_splitting` trennt enger nach als
  vorher (nur die gescheiterten statt aller Flecken ab `MIN_PATCH_FACES`).

  Ruhig gemessen, drei Läufe, Median: Bowlingkugel 0,19 → 0,20 s mit ihrer Kugel zurück;
  Drache 4,02 → 3,83 s; gähnende Katze 8,62 → 8,17 s. Entwicklungstor grün (13 681 bestanden,
  26 übersprungen). Nachweise: `test_features.py`
  (`test_a_ball_that_is_the_whole_body_stays_a_ball` an Kugel **und** Torus,
  `test_the_skin_judgement_only_counts_patches_without_a_shape`).

  **Die Breitenabnahme ist gefahren** — `cb157bf4` gegen `4fa4d38f`, beide als eigener
  Worktree (ein erster Lauf war wertlos, weil er den Arbeitsbaum als „neu" nahm und ein
  fremder Commit mitten hineinlief): **489 Körper, 479 zeichengleich, zehn abweichend, kein
  Fehler**, Erkennung 1 107,6 gegen 1 127,3 s. Die zehn sind der Effekt, den die Regel
  vorhergesagt hatte — die Stücke eines gescheiterten Flecks kommen jetzt nach *allen* ganzen
  Flecken, also sieht `_cylinder_beside_a_torus` eine vollständigere Kandidatenliste:

  * **Vier Clips (1 656 Dreiecke): nur die Nummerierung.** Dieselben sechzehn Merkmale mit
    denselben Werten, andere Namen. Die Ursache ist **kein** Fehler dieses Umbaus, sondern
    einer im Bestand, den er sichtbar macht — siehe RM-211.
  * **Ein Kegel mehr** am Gartenschlauchhalter (152 Dreiecke, halber Winkel 71°, 409 → 410).
  * **Verrundungsgrenzen verschieben sich** an drei Körpern: Beckenreiniger 60 → 62
    (drei Verrundungen werden fünf kleinere), Flaschenhalter 444 → 445, Kumiko-Schale
    7 325 → 7 322. Dieselben Rundungen, anders geschnitten; welche der beiden Fassungen die
    bessere Grenze zieht, ist an der Geometrie nicht entschieden und wäre eine eigene
    Messung.

  Die Bilanz bleibt: Ein Korrektheitsfehler an drei Kugeln ist behoben, zehn von 489 Körpern
  verschieben Merkmalsgrenzen, und keiner verliert eines ohne Ersatz.

  **Und ein Weg dorthin ist gemessen und wieder ausgebaut.** „Auf der Haut wird nur der
  Zylinder gefragt" — Kegel, Kugel und Ring verwirft `_shapes_on_a_freeform` dort ohnehin,
  und am Riesenfleck des Drachen kosten alle vier Fits 1 332 ms gegen 255 für den Zylinder
  allein. Das brachte 0,6 s am Drachen und **kostete die Bowlingkugel ihre Kugel**: Um zu
  wissen, ob ein Riesenfleck Haut ist oder selbst eine Grundform, muss man ihn einpassen.
  Die Abkürzung setzt genau das voraus, was sie sparen will. Zurückgebaut; 0,6 s sind kein
  Merkmal wert, das einem Kunden verschwindet.

  **Zwei weitere Wege, gemessen und verworfen.** Die Fits an Riesenflecken auf eine
  gleichmäßige Stichprobe zu stützen — `FIT_SOLVER_POINTS` eine Stufe früher, schon bei der
  Datenaufbereitung — ist zeitlich verlockend (1 108 → 157 ms am selben Fleck) und **ändert
  die Erkennung**: An der Waschschüssel gibt ein Fleck mit 89 230 Dreiecken ganz gerechnet
  einen Ring und mit 4 096 Stützpunkten keinen; einer mit 86 761 gibt ganz gerechnet keinen
  Kegel, mit 16 384 aber einen. Dieselbe Familie wie die neun Hebel aus RM-209.

  **Offen bleibt §31.** Eine Sekunde je 200 000 Dreiecke hieße 1,6 s am Drachen; gemessen
  sind 4,2 auf ruhiger Maschine. Was bleibt, mit Zahlen — alle aus demselben belasteten Lauf,
  in dem die Erkennung 8,4 → 7,4 s ging: `_large_facet_faces` 2,2 s, denn es fittet dieselben
  Formen über seine eigenen Kandidatenflecken, und dort ist das Hauturteil noch nicht gefällt;
  `_fitted` 5,2 s (52 `classify`, `fit_cone` 1,7 s, `_surface_support` 0,8 s, `find_helices`
  0,7 s, `_curvature_jumps` 0,3 s). Der nächste Schritt wäre, `_large_facet_faces` dieselbe
  Auskunft zu geben — und danach bleibt der Löser selbst (RM-209).

  [Befund](ROADMAP-ARCHIV.md#ein-drache-aus-triposg-19-meter-acht-minuten-kein-merkmal-20092026).

  **Stand 28.09.2026 (Release 0.5.1, Paket stapel, `53813ec61`, `8e1afee29`, Nachtrag
  `3a83c04af`, Merge `c3636d210`):** Sicher vergebliche Kegel- und Ringläufe rechnet ein
  Stapel vorher (`perceive/refine.py`: SciPys `trf` Zweig für Zweig in NumPy; übernommen
  wird nur das sichere Nein mit Abstand und Schattenlauf, alles andere rechnet der echte
  Löser; `least_squares` ohne SciPys Hülle bitgleich nachgebaut). Korpus 553/553 bitgleich.
  CPU unter Last: Kumiko-Schale 37,6 → 24,9 s, Meshy-Murmelbrett 603 → 472 s; Freiform der
  Leistungstests 13,9 → 13,8 s, Drache 12,8 → 13,3 s, Schiff obj_3 19,4 → 20,9 s (im
  Rauschen) — dort stehen die vergeblichen Läufe in zu kleinen Gruppen für den Stapel. §31
  ist an keinem der fünf Modelle erreicht; den nächsten Hebel je Modell nennt
  `konzepte/nachweise-release-0.5.1/reports/stapel-schluss.md` (Abschnitt „Nicht behoben“).
  Am Drachen sind 12 von 98 Läufen vergeblich, in Gruppen zu klein für den Stapel.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Hautregel und Schutz analytischer
  Grundformen am heutigen Stand geprüft; der Drache (325 244 Dreiecke) liefert unverändert null
  Merkmale in 6,88–8,98 s unter Last, das Ziel von rund 1,6 s ist verfehlt. `refine._vector_norm`
  ist bitgleich an 2 539 echten Löseraufgaben und spart 3 bis 10 % Löserzeit (40/40 Lösertests).
  Verworfen: geteilte leere Kugel- und Zylinderfits (Drache 5,20/4,33 gegen 4,44/4,34 s, kein
  wiederholbarer Gewinn) und eine kompilierte Schleifenhülle. Offen bleiben die Aufbereitung großer
  Flecken und die tatsächlich konvergierenden Fits. Beleg:
  `F:\solidon-review-reports\codex-2026-10-03\geometrie\erkennung\bericht.md` (RM-209/132/193).

<a id="rm-201"></a>

- [~] **RM-201 — Ein hohler Körper hält die 300 ms der Schichtanalyse nicht.**
  Gefunden am 21.09.2026 im Review (Paket F): Die Leistungsmarke
  `slice_medium` maß nur den massiven Körper, und ein massiver Körper hat je
  Schicht eine Kontur. Die neue Marke `slice_medium_hollow`
  (`test_the_layer_analysis_of_a_hollow_body_is_watched_too`: 200 000
  Dreiecke, Wand 1,5 mm, 400 Schichten) misst 1,49 bis 1,62 s, wo §31
  „300 ms" sagt — 3 658 Puffer, 796 Differenzen und 718 STRtree-Anfragen je
  Lauf, je Schicht einzeln. Die Marke wacht über die Regression, nicht über
  das Ziel. Weg: die Pufferung und die Differenzen aller Schichten einer
  Höhe stapeln, wie die Formabweichung es seit dem Review je Trägerart tut,
  oder das Ziel für Schalen mit Begründung neu fassen. Abnahme: die Marke
  unter 300 ms auf der Referenzmaschine ohne Fremdlast, oder ein Satz in §31,
  der Schalen ausnimmt und sagt, warum.

  **Durchsicht 0.5.0:** Schnitt 0,5 s, Messen 0,8 s (davon die Breitensuche),
  Säulen 0,6 s unter Last. Der nächste Hebel ist eine native Mitre-Öffnung —
  Clipper2 über Cython (BSL-1.0, gehört vorher in die Freigabeliste) oder eine
  eigene Offsetfunktion im vorhandenen `_chain.pyx`. An Gittern (Kumiko) kostet
  die genaue Nachfrage der Breite so viel wie vorher (12,7 → 11,1 s), aber mit
  richtigen Zahlen. Die Marke `slice_medium_hollow` bleibt Regressionswächter.

  **Stand laut Register bis 29.09.2026:** `slice_body` an der Hohlkugel 40 % schneller
  (`546eff16`: Stapelung, Inselzertifikat, Säulen auf Arbeitern, direkte Ringe), hochgerechnet
  rund 0,65 s auf der Referenzmaschine — 300 ms nicht erreicht; der Rest ist die Breitensuche mit
  sieben Öffnungen je Schicht. Robert gibt C++ frei (23.09.): native Breitensuche als eigener
  Bauauftrag; womit (eigene Mitre-Offsetfunktion in `_chain.pyx` oder Clipper2 über Cython),
  entscheidet Robert

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Die gerichtete
  Clipper-Gesamtvereinigung aus RM-486 kostete an der Hohlkugel 57–72 s; jetzt steigen die Säulen
  unabhängig ab (höchstens sechs Arbeiter), Differenz nur bei belegtem Kontakt. Dazu gerichtete
  Verschachtelung, `_chain.ring_nesting` und die gemerkte Absage des Volumenkerns. Schichtkennzahlen
  an Screen-Cover, CC2-Box und eigenem Beispiel bitgleich, Stützraum der Hohlkugel 73 360,800 mm³,
  282 Schicht- und Konturfälle grün. Im Messfenster 14:53 mit angehaltener eigener Arbeit:
  1,20/1,27/1,41 s statt 0,3 s. Verworfen: Mitre-Öffnung über den Clipperkern (26 andere
  Breitenentscheidungen, nicht schneller), Zertifikate ohne belastbaren Vorteil. Der Hauptklon
  braucht einen Neubau von `_chain`. Beleg:
  `F:\solidon-review-reports\codex-2026-10-03\geometrie\druckvorbereitung\bericht.md` (RM-201).

<a id="rm-217"></a>

- [~] **RM-217 — Die Zuordnungsfrage zeigt das alte Merkmal nicht im Bild.**
  Vier verbleibende Beobachtungen aus der Durchsicht 0.5.0, alle an `evaluate._with_features`
  und der Zuordnungsfrage: Nach *Merkmal entfernen* stehen `remove_feature.gone`
  **und** `perceive.orphaned` für dasselbe Merkmal (merkmalsops, Sonde
  `scars3.py`: `cone_1` zweimal); nach jedem *Teilen* erscheint
  `perceive.orphaned` für die erkannten Flächen des Ausgangskörpers (fünfmal im
  Schaustück, trennen); ein Feldschnitt von einer Versatzebene **unter** der
  Deckfläche (`@d` < 0) hält mit „Welches Merkmal entspricht face_2?" an, ohne
  dass klar ist, ob die Frage eine Antwort hat (szene); und die Frage nennt
  das alte Merkmal nur als Kennung — die
  Kandidaten leuchten seit B9 der Durchsicht beziehungen, das alte nicht. Weg:
  `_with_features` lässt Namen aus, die die Operation selbst in
  `reserved_feature_ids` neu reserviert oder als verbraucht erklärt; der Kern
  gibt das alte Merkmal über `question_context` mit, damit die Ansicht seine
  Lage markiert; den Feldschnittfall als Test nachstellen und entscheiden, ob er
  fragen darf. Abnahme: je Merkmal höchstens ein Befund je Schritt, nach Teilen
  keiner für Flächen, die das Teilen verbraucht, und die Frage zeigt alt und neu
  im Bild.

  **Formen-Beispiel korrigiert (Paket formen):** Der Handschmeichler meldet
  acht statt 55 Hinweise. Verluste ohne Verweis werden einmal je Körper und
  Schritt zusammengefasst; die 51 Merkmalskennungen und ihre Anzahl bleiben
  in den Details und für den Agenten erhalten. Verluste mit Verweis bleiben
  einzelne Warnungen. Der Gegenlauf mit v0.4.4 meldete dieselben 55 Hinweise,
  es war keine Regression der Durchsicht. Der neue Test in
  `test_orphans.py` war vor der Umsetzung rot und danach grün; die
  Kernkorrektur liegt im Hauptbaum. Die sechs Formen-Aufnahmen sind erneuert
  und nach vollständiger Druckanalyse geprüft: durchgehend null Fehler, zwei
  Warnungen und zehn Hinweise (acht aus der Auswertung, zwei aus der
  Druckanalyse). Der Medienabschluss steht unter RM-237 im Archiv; das
  vollständige Tor bleibt unter RM-213 offen. Eine pauschale
  Unterdrückung der Hinweise an Formwerkzeugen ist nicht beschlossen;
  die Bündelung bleibt der geltende Weg. Die größenabhängige Kugelauflösung
  folgt nach 0.5.0 unter RM-188.

  **Durchsicht v0.5.1 (26.09.2026):** *Merkmal entfernen* meldet das Entfernte einmal
  (`REMOVAL_CODES`), nach *Teilen* schweigt ein Verlust ohne Verweis (`QUIET_LOSSES`),
  eine geteilte Fläche gilt nicht als verloren (`_divided_in_place`, auch für die zweite
  Hälfte), und der Feldschnitt gibt am Netz nur seine benannten Bohrungen aus — unter
  der Deckfläche keine Frage mehr, auf ihr behält sie `face_top` (`1afc1852d`,
  `5948a79a5`).

  **Umsetzung und Review (30.09.2026):** `EvaluationResult.question_reference` trägt
  das bisherige Merkmal samt Körper nur im Rückfragekontext. Die nötigen
  Ansichtsdreiecke eines exakten Körpers entstehen im Auswertungsarbeiter; das
  Fenster zeichnet nur noch. Der Viewport zeigt die alte Fläche mit eigener
  Kontur und dem übersetzten Text „Bisher“, dazu wie bisher die neuen
  Kandidaten. Antwort, Abbruch und neue Auswertung räumen beide Markierungen ab.
  Der Feldschnitt bei `@d = -2 mm` fragt nicht nach und behält den Namen der
  Deckfläche; dieser Fall ist mit dem schon vorhandenen Test ausdrücklich
  nachgeprüft.

  **Nachweis:** 373 Tests in `test_native_references.py`,
  `test_matching_answers.py`, `test_viewport_decisions.py` sowie den gezielten
  Feldschnitt-, Teilungs- und Entfernungsfällen bestanden; zusätzlich 572
  Sprach- und Übersetzungstests. Ruff, Format und mypy für `evaluate.py` grün.
  Der breitere mypy-Aufruf hält an `app/ui/filament_picker.py:870`, einer schon
  zu Beginn geänderten, hier nicht angefassten Datei. Review-Fund:
  B-Rep-Vernetzung durfte nicht in den Fensterthread gelangen; sie wurde in
  den Auswertungsarbeiter verschoben. Der anschließende UI-Aufruf bleibt mit
  Rückfragen ohne Altmerkmal zweiparametrig.

  **Offen:** der echte Fensterbeleg gehört gemäß Projektregel zu RM-213.
  Registerabgleich 02.10. (Stand `3fd3b1ace`): Die Umsetzung vom 30.09. (`question_reference`) liegt nur ungesichert im Arbeitsbaum, nicht in HEAD; die Registerzelle sagt das nicht.

<a id="rm-218"></a>

- [~] **RM-218 — Am exakten Körper heißen Bohrungen nach ihrer Lage, und der Verlauf lässt sich dort nicht umbauen.**
  Gemessen beim Bau von P7.1–P7.3 (Bericht p7verlauf, Abschnitte 3 und 7) an
  `build_tray_v3.step`: `drill_brep_hole` nummeriert Bohrungen nach Lage. Wer
  eine Bohrung vor eine andere schiebt oder eine dritte dazwischen einfügt,
  bekommt „Das würde die Kette anhalten — geändert wurde nichts", weil ein
  Flächenbezug am exakten Körper nicht mehr belegt ist. Die Gegenprobe ohne
  Umbau hält an derselben Stelle (`NativeReferenceLost`): Der Umbau rechnet
  genau in den Halt, den dieselbe Reihenfolge von Hand hat, und schreibt nichts
  — richtig, aber der Kunde kann am exakten Körper nicht umsortieren, was am
  Netz geht. Weg (Empfehlung des Berichts): Eine eindeutige geometrische
  Zuordnung behält den alten Namen, wie am Netz — dieselbe Regel, die P1.4c.3
  für unveränderte Flächen eingeführt hat. Abnahme: an `build_tray_v3.step`
  Bohrung B vor A, Einfügen zwischen und rechts rechnen durch, Namen und
  Passungen folgen ihrem Merkmal, Strg+Z stellt Projektinhalt und Objekt-Hashes
  wieder her; ein monotoner interner Verlaufszähler darf weiterlaufen.
  **Umgesetzt und teilweise geprüft 30.09.2026:** Feature-einführende exakte Schritte behalten alle
  eindeutig zugeordneten Vorgänger, deren Geometrie innerhalb `EPS_GEOM`
  unverändert ist; geänderte oder mehrdeutige Merkmale bleiben im bestehenden
  Frage-/Haltweg. An `F:\3D Dateien\build_tray_v3.step`, Körper `1#1`, rechneten
  B vor A sowie Einfügen bei x = 0 und x = 80 mm zwischen A bei x = −50 mm und
  B bei x = 50 mm. Eine spätere Vergrößerung blieb bei B (Ø 8 mm), eine
  Passung folgte derselben Kennung. Die drei Umbauten meldeten
  `history.reference_followed`; Strg+Z stellte den serialisierten
  Projektinhalt (ohne monotonen Zähler) und alle Objekt-Hashes wieder her.
  Regressionen: 357 Tests in den nativen Verweis-, Verlaufs-, Zuordnungs-,
  B-Rep- und exakten Merkmalsoperationstests bestanden; Ruff, Format und mypy
  für `evaluate.py` grün. Der vollständige Entwicklungslauf und die
  Fensterabnahme sind damit nicht behauptet.
  Nachprüfung (Review 02.10., Arbeitsbaum ungesichert): am echten `build_tray_v3.step` behoben — B vor A, Einfügen bei x = 0 und x = 80 rechnen durch, Strg+Z stellt Inhalt und Hashes her (main hält x = 80 noch an). Die Passung ist nur über den Test belegt, nicht am echten Modell. Belege `F:\solidon-review-reports\verif-E.md`.
  **Abgeglichener Stand 02.10.:** Der notwendige begrenzte RM218-Anschluss wurde mit
  `57848fa72c4ca229f5dc9bcdd2cca2baf6945987` nach `main` und `origin/main` übernommen.
  Der [RM284-Abschluss](konzepte/nachweise-release-0.5.1/reports/rm284-rundungsgruppen-2026-10-02.md#abschluss-auf-dem-hauptzweig)
  nennt dessen Entwicklungsprüfung und schließt RM218 insgesamt ausdrücklich nicht ab.
  Die vorstehende Nachprüfung beschreibt ihren früheren Hauptzweigstand; ihre offene
  Gegenprobe zur Passung am echten Kundenteil wird dadurch nicht nachträglich grün.
  **Weiterer Abschlussstand 02.10.:** Die unveränderte Kundensonde mit echtem Pin und
  gültigem Passungsnamen `RM218: Bohrung B und Prüfpin` besteht alle sechs Fälle
  (drei Umbauten × Entwurf/Fein, 96,79 s, Exit 0). Ein gemeinsamer Parser erhält
  jetzt den vollständigen Namen zwischen Präfix und letztem Seitenmarker, auch
  in Abhängigkeiten und beiden Revisionsvergleichen. Code-/Test-/Kartenreview
  und unabhängiger Kundenbelegreview sind ohne Befund freigegeben. 36 neue
  Gegenfälle und der überlappende Nachgang mit 531 Fällen sind grün, ebenso
  Ruff, Format und mypy auf den betroffenen Pfaden.
  Der Kundenlauf belegt echte Passungsbezüge, die angeforderte Operationsfolge,
  Warmcachetreffer je Schritt und genau ein Undo mit direkter Wiederherstellung
  aller sechs Körper, eingebetteter Quellen und Projektinhalte ohne monotonen Zähler.
  Alle 260 erfassten Quellen und das Original bleiben unverändert.
  [Fachnachweis und tatsächliche Grenzen](konzepte/nachweise-release-0.5.1/reports/rm218-kundenpassung-2026-10-02.md).
  **Offen:** zentrales Entwicklungstor und Übernahme. Die Fensterabnahme bleibt
  beim Release unter RM-213.

<a id="rm-230"></a>

- [ ] **RM-230 — Variable Verrundung und Formschräge: fünf Grenzen, die der Kunde merkt.**
  Aus dem Bau von P6.1/P6.4 (Bericht p6a, „Grenzen — bewusst offen"): Der Anfang
  einer variablen Verrundung auf einem Ring ist eine Konvention (links, vorn,
  unten) und nicht wählbar — dafür braucht es den Maßeditor im Bild (P0.3/P5.1).
  Gemischte Ecken (zweite Kante mit anderem Radius) sagt das Netz mit Satz ab,
  der exakte Kern überlässt sie OpenCASCADE ungeprüft. Zwischenstellen als Text
  („50:4 80:3") sind nicht an Projektparameter bindbar, Anfangs- und Endradius
  schon. Die Formschräge an allen Wänden von `build_tray_v3.step` sagt
  OpenCASCADE ab (einzelne Wände gehen); gekrümmte Flächen außer Zylindern in
  Zugrichtung sind nicht anstellbar. Die Netzschräge ist am einfachen Quader
  2,3-mal langsamer als der alte Weg (0,41 gegen 0,18 s, weit unter §31). Weg:
  gemischte Ecken am exakten Kern als Test; Zwischenstellen als Liste von
  Maßausdrücken (§13); die Formschräge vieler Wände in Gruppen rechnen. Der
  wählbare Anfang gehört zu P5.1. Abnahme: je Grenze entweder gebaut oder mit
  Satz und Weg in der Oberfläche und im Handbuch benannt.
  Registerabgleich 02.10. (Stand `3fd3b1ace`): Die gemischte Ecke sagt der exakte Kern inzwischen mit Satz ab (`check_varying_radius`) — „ungeprüft“ ist veraltet, ein Test am exakten Kern fehlt. Die Formschräge an allen Wänden von `build_tray_v3.step` wird weiter abgesagt.

<a id="rm-253"></a>

- [~] **RM-253 — Am Laptop-Ständer tragen Kippen und Verdoppeln einer Bohrung falsch ab.**
  Gefunden beim Abschluss von RM-246 (26.09.2026) an
  `F:\3D Dateien\parametric-laptop-riser.stl`, das seitdem geschlossen aus
  dem Import kommt (21 Teile, `repair.part_inside`) und genau rechnet. Die
  Sonde der meldenden Sitzung (`.claude/.state/rm-246-laptop-staender-2026-09-25/probe_real.py`,
  `PROBE_TREE=<baum> python probe_real.py "<datei>" 15`) zeigt an 18 Ketten
  mit Senkung und sechs einzelnen Durchgängen drei Dinge, die nicht zum
  Werkzeug passen: *Merkmal drehen* von `hole_11`+`cone_51` um 15° um x trägt
  1 444,47 mm³ vor den alten Mündungen ab (`hole_1`+`cone_5`: 19,59 mm³, die
  übrigen null); *Merkmal verdoppeln* 6,3 bis 11,1 mm daneben lässt an jeder
  geprüften Bohrung das Volumen stehen (`boolean.without_effect`, an
  `hole_11` dazu `duplicate_feature.no_longer_through`); *Merkmal versetzen*
  um 1,5 mm meldet an `hole_1`, `hole_3` und `hole_11`
  `move_feature.no_longer_through`. Zu klären, ob das an den 21
  ineinandersteckenden Teilen liegt (eine Bohrung durch mehrere Teile, eine
  Kopie im Hohlraum eines anderen) oder an den Handlungen. Abnahme: Kippen
  trägt vor den Mündungen nur ab, was das gekippte Werkzeug überstreicht;
  eine Kopie im Material trägt ab oder sagt, warum nicht; „nicht mehr
  durchgehend" nur, wo die versetzte Bohrung wirklich endet.

  **Durchsicht v0.5.1 (27.09.2026, bohrung):** Es liegt an den Teilen. Die 21 Teile
  lassen sich nicht vereinigen: Teil 10 (9 166 Dreiecke) kreuzt sich 1 121-mal selbst,
  `resolve_self_intersections` lehnt deshalb ab, und eine erzwungene Vereinigung aller
  Teile gab 136 Teile mit 605 verbleibenden Eigenkreuzungen. Gebaut ist die Auskunft:
  `boolean.parts_not_united` sagt, dass Teile ineinanderstecken und sich nicht
  vereinigen ließen, weil sich eine Oberfläche selbst kreuzt, mit *Stelle zeigen*
  (`ae178de8c`, Test `test_boolean.py::test_parts_that_cannot_be_united_say_so`).
  Nachgemessen am neuen Stand (`konzepte/nachweise-release-0.5.1/sonden/bohrung/rm253_focus_out.txt`):
  `hole_11`+`cone_51` um 15° gekippt trägt 32,6 mm³ jenseits der oberen alten Kappe
  ab, Verdoppeln bleibt ohne Wirkung (jetzt mit Satz), Versetzen meldet weiter
  `no_longer_through`. Am selben Modell (massbild): 13 von 28 Bohrungen gelten als „In
  dieser Bohrung steht Material“ (`prepare_ops.hole_is_clear`), und ein Langloch aus
  *Bohrung 2* (Ø 3,33, 43 mm durch mehrere Wände) wird schon ohne Versatz nicht wieder
  erkannt — vermutlich dieselbe Ursache, eine Bohrung durch mehrere ineinandersteckende
  Teile; nicht geprüft. Weg: die Eigenkreuzung innerhalb einer Schale auflösen, dann
  vereinigen und die drei Handlungen neu messen.

  **Sicherheitskorrektur 01.10.2026:** Scheitert die notwendige Vorvereinigung, hält
  `boolean()` jetzt mit einem Handlungstext vor jeder Solverstufe an. Zuvor rechnete die
  Kette mit den unveränderten, ineinanderliegenden Teilen weiter und konnte ein falsches
  Ergebnis liefern. Die Zuordnungsliste `object_ids` trägt den betroffenen Op-Eingang in
  den Prüfbericht; die Regression prüft auch, dass *Stellen zeigen* bei einer mehrteiligen
  Vereinigung am fehlerhaften und nicht am ersten Körper landet. Der Test nutzt eine
  geschlossene Schale, die sich selbst kreuzt, und einen zweiten überlappenden Körper.

  Am Originalmodell `F:\3D Dateien\parametric-laptop-riser.stl` (8,67 MB) wurde der
  vollständige Import- und Auswertungsweg erneut geprüft. *Merkmal versetzen* für
  `hole_11` um 1,5 mm quer zur Achse hält mit `GeometryError`, `object_id=obj_1` und den
  Handlungen `show_locations` und `cancel` an; es gibt kein unzuverlässiges Ergebnis aus.
  Der Lauf belegt auch den Kettenzweig, der `_closed_at` umgeht. Eine Regression mit einer
  erkannten Senkbohrung prüft die Objektkennung an genau dieser Verschlussvereinigung. Der
  Detailtext empfiehlt die Reparatur im CAD- oder Netzprogramm. Das löst die Eigenkreuzung
  nicht und führt die ursprünglichen Abnahmeschritte Kippen, Versetzen und Verdoppeln noch
  nicht erfolgreich aus. RM-253 bleibt daher teilweise offen.

  Die anschließende Diagnose am unveränderten Original bestätigt in der geschlossenen
  9 166-Dreieck-Schale 1 243 Schnittpaare an 631 Flächen; darunter liegt ein echter
  Schnitt schon in der STL. Blenders exakter Boolean machte die Kopie nicht wasserdicht.
  Der 0,2-mm-Voxelremesh schloss sie zwar, verschob die Außenfläche aber bis 0,083878 mm
  und die Höhe um 0,143410 mm; damit liegt er über `MAX_FACET_SAG = 0,05 mm`. Auch die
  Kreuzungsfreiheit ließ sich wegen des Zeitlimits nicht belegen. Beide Reparaturkandidaten
  sind verworfen. `hole_11` und `cone_51` werden lokal noch mit ihren ursprünglichen
  Maßen erkannt, liegen aber in anderen, unveränderten Schalen. Es wurde weder die Kopie
  weiterbearbeitet noch am Original eine neue Bearbeitung ausgeführt; die angefragte
  Reparatur samt Kippen/Versetzen/Verdoppeln ist weiterhin nicht abgenommen.

  **Gezielte Verifikation:** `test_boolean.py`, `test_profile_clamps.py` und
  `test_finding_actions.py`, `test_errors.py`, `test_translations.py` und
  `test_language_rules.py`: 1 051 Tests bestanden. Ruff und Formatprüfung der geänderten
  Booleschen Geometriedatei und ihrer Regressionstests sind grün. Das unabhängige
  Nachreview bestätigte die bedingte Handlung nach einem behobenen P2-Hinweis; das
  vollständige Entwicklungstor und die Geometriereparatur stehen weiter aus. Der gezielte
  Mypy-Aufruf meldete drei Unreachable-Befunde in der parallel geänderten
  `app/core/perceive/refine.py`; für diesen Stand liegt daher kein grüner Mypy-Nachweis vor.
  Nachprüfung (Review 02.10., Arbeitsbaum ungesichert): Sicherheitskorrektur unvollständig. `union_objects` und `subtract_objects` halten mit dem richtigen Objekt; `drill_hole` hält ohne `object_id`, auch im Prüfbericht, und ein selbstkreuzender Körper als Werkzeug rechnet weiter still. Belege `verif-E.md`, `sonden\v_e\`.
  Registerabgleich 02.10. (Stand `3fd3b1ace`): Die Registerzeile ist zu optimistisch — `drill_hole` ruft `boolean` am HEAD weiter ohne `object_ids` auf.
  Nachprüfung am Stand `3fd3b1ace` (nach `eab5f4f47`): unvollständig. `drill_hole` hält weiter mit `object_id=None` und `correct_input`/`cancel`, auch im Prüfbericht; ein kaputter Körper als Werkzeug rechnet still (`subtract_objects [gut, kaputt]` → 118,5 mm³ ohne Befund, `boolean.py:412–414`); erfüllt ist nur der Fall mit dem kaputten Körper als erstem Eingang. Der neue generelle Halt kehrt die hier dokumentierte Entscheidung um (RM-382). Belege `review-3fd3b1ace.md`, Sonden `r_rm253_*.txt`.

<a id="rm-247"></a>

- [~] **RM-247 — Die Waschschüssel ließ sich nach Solidons Übergabe nicht drucken.**
  Robert, 25.09.2026, an `F:\3D Dateien\HydroBowl+–+Smart+Fruit+&+Veggie+Washer (1)\washing bowl v1.stl`
  auf dem Centauri Carbon 2 mit ElegooSlicer: „schon bei 1-2 schichten
  ziehen wir fäden, verschieben die Stützen, die Stützen die der Slicer macht
  sind auch sinnlos und gehen durch das Modell" — und dazu: „sowas sollten
  wir dann aber immer für jedes Modell und Slicer/Drucker richtig
  einstellen". Die Übergabe (`open-in-slicer\solidon.3mf`) trug Gitterstützen
  „überall", Elegoos Muster `rectilinear` und 150 mm/s Leerfahrt. Im
  ElegooSlicer nachgeschnitten: Schicht 1 aus 55 m Stütze gegen 3 m Modell,
  ab Schicht 2 lose Einzellinien im Abstand von 2,8 mm, 530 Leerfahrten je
  Schicht, und 22,9 m Stütze im Wasserkanal vom Becher zur Düse, die niemand
  mehr herausbekommt. Sonden und Varianten:
  `.claude/.state/rm-247-waschschuessel-2026-09-25/`.

  **Gebaut**, jeweils mit Test:
  - `analysis.model_support` trennt Säulen, die außen auf dem Modell
    aufsetzen, von Kanaldecken (freier Raum unter der Decke fasst keinen
    Kreis von 30 mm); Kanalstücke fallen aus Stützbedarf und „überall". Die
    Schüssel bekommt damit „Gitter, nur vom Bett" mit dem Kanal als Grund.
    Im Slicer mit diesen Werten: 0,3 m statt 22,9 m im Kanal, Kanaldecke als
    Brücke.
  - „Gitter" geht als `rectilinear-grid` an Orca und PrusaSlicer, als `grid`
    an Cura (Linienabstand mal zwei); Bäume behalten das Herstellermuster.
  - `PrinterProfile.travel_speed` aus dem Standardprozess der
    Herstellerprofile (CC2 500, A1 700, MK4S 300 …); ein älteres Projekt
    bekommt sie als Vorschlag.
  - Die falsche Decke von 258 mm im Bericht: ein 45-Grad-Streifen entlang der
    Außenwand, fast überall schmaler als zwei Bahnen, mit 0,65 mm² Kern —
    ohne getragene Richtung galt seine Diagonale. `_bridge_width` misst jetzt
    nur, was breiter als zwei Bahnen ist. Die größte Brücke der Schüssel ist
    danach 176,6 mm bei z = 7,55, und die ist echt: Der Boden liegt dort
    7,5 mm über dem Bett auf zwölf Füßen.
  - Eine Stützsperre für Kanäle (26.09.2026), als Vorschlag
    `support.block_channels` — ohne „Vorschläge übernehmen" gehen die
    Standardeinstellungen hinaus (Robert). Gebaut aus dem freien Kanalraum
    innerhalb der Hülle des Teils, eine Scheibe in die Decke hinein
    (`analysis.channel_space`). **Die erste Fassung druckte der ElegooSlicer
    als Kunststoff**: Sie hing als Prusa-Bereich im Netz, und die Orca-Familie
    liest ihre eigene Beilage — im Kanal 161,8 statt 49,5 m Modellbahn, 22,8 g
    mehr; die damals gemessenen „22,9 → 0,5 m" waren der Pfropfen. Jetzt je
    Familie die eigene Schreibweise (`slicer_keys.helpers_as_parts`): für die
    Orca-Familie ein eigenes Teil `support_blocker`, für PrusaSlicer der
    Bereich samt `slic3rpe:Version3mf`. Stütze im Sperrkörper, Modellbahn
    unverändert: ElegooSlicer „Gitter überall" 87,8 → 0,0 m, „Baum nur vom
    Bett" 22,5 → 1,7 m; PrusaSlicer „Gitter überall" 91,0 → 6,5 m. Cura
    bekommt ein STL und keine Sperre. Keine Ausgabe trug die fehlerhafte
    Fassung (v0.5.0 liegt davor).
  - Inseln: Eine Insel auf dem Modell verlangt „überall", eine über dem Bett
    nicht mehr — vorher bekam jedes Teil mit einer Insel „überall", und der
    Kanal füllte sich wieder.

  - **Tempo je Drucker** (26.09.2026): `PrinterProfile.speed_*`, die
    Beschleunigungen und `flow_factor` aus dem Standardprozess und dem
    allgemeinen PLA des Herstellers, für „Standard"; die übrigen Stufen im
    Verhältnis. Danach deckelt die Auflösung jedes Tempo auf den Volumenstrom
    (`print_settings.flow_speed_limit`) — sonst meldete die Beratung an Bambu,
    Prusa, K1 und Kobra an jedem Teil vier Warnungen. Schüssel am Centauri im
    ElegooSlicer: 30 h 41 min → 18 h 29 min.
  - **Brim auf vielen kleinen Füßen** (26.09.2026), als Vorschlag: mehrere
    Aufstandsinseln, keine mit `SMALL_FOOTPRINT`. Die Schüssel steht auf zwölf
    zu je rund 108 mm²; im Korpus trifft die Regel sonst 6 von 447 Körpern.
    Am Eiffelturm legt der Brim 1001 mm um jedes Bein.
  - **Die Kanalfrage selbst war zu langsam** (26.09.2026): je Säule gefragt am
    Eiffelturm hochgerechnet 30 Minuten für die Druckvorschläge; jetzt je
    Schicht und auf Arbeitern 2,8 s, an der Schüssel dieselben Antworten.
  - **Eine Stützsperre kam beim Einlesen als Material an** (26.09.2026):
    Prusa-Bereiche, die kein Modellteil sind, fallen jetzt aus dem Körper,
    eine Aussparung wird abgezogen — wie die Teilarten der Orca-Familie.

  **Offen:** der Probedruck der Schüssel am Centauri Carbon 2 mit
  übernommenen Vorschlägen. Die Frage zum Brim je Teil beim Export ist mit
  [RM-250](ROADMAP-ARCHIV.md#rm-250) erledigt.

<a id="rm-281"></a>

- [~] **RM-281 — Die Übergabe auf dem Herstellerprofil: Stufen C bis F.** Beauftragt am
  27.09.2026 nach Roberts Minigolf-Druck am Centauri Carbon 2
  ([Konzept](konzepte/konzept-herstellerprofil-als-grundlage-2026-09.md), Abschnitt 4).
  **A und B stehen** (`aed31c787`): Herkunft je Wert, Grundlage aus dem Herstellerprofil,
  Format 36, die Orca-Familie bekommt nur die Abweichung samt Druckplatte, „automatisch“
  für Stützen und Haftung, der Druckdialog zeigt, was gedruckt wird. Abgenommen im
  ElegooSlicer (Minigolf-Platte, Waschschüssel, Wedge-Lock: Konfiguration, Rand, Zeit und
  Stütze gleich dem Herstellerlauf) und in Bambu Studio (dieselben drei gegen die
  Herstellerkette: 0 von 429 Schlüsseln verschieden). Ein unabhängiges Review vor dem
  Commit (sieben Fehler, acht Risiken, fünfzehn Hinweise;
  `konzepte/nachweise-release-0.5.1/review/herstellerprofil-2026-09-27/review-a-b.md`) ist eingearbeitet, bis auf
  die Punkte unten bei C und L. Dazu `efd4686c2`: Das Tempo der
  ersten Schicht gilt auch für ihre Füllung.

  - **C steht** (`44ab90965`, dazu `575e5ef83` und `6fc852fb0`): PrusaSlicer bekommt
    Drucker, Prozess und Filament seines Bündels, aufgelöst in `solidon.ini` und die
    Beilage der 3MF (`handover.prusa_values`), darüber nur die Abweichung; die Grundlage
    liest sie zurück (`manufacturer.prusa_chain`, `PRUSA_PROCESS`, eingebaute Vorgaben
    gemessen). Der Druckdialog bietet dieselbe Profilwahl wie für die Orca-Familie,
    verlangt sie aber nicht; ohne Drucker im Bündel bleibt Solidons Satz samt
    `filament_type`, und `slicer.printer_unknown` sagt es. Gemessen am Minigolf-Auftrag in
    PrusaSlicer 2.9.6: MK4S HF0.4 und XL IS ohne Vorschläge in allen 259 und 260
    Schlüsseln gleich der Kette, `G29`-Vermessung und Spüllinie im G-Code; der MINI lehnt
    ab, weil ein Teil 200 mm hoch ist (Bauraum 180). Die automatische Stützschwelle
    rechnet plattformgleich (`units.exact_atan_degrees`, RM-187). Angeboten werden nur
    Profile des eigenen Herstellers, wie in PrusaSlicer (`SlicerProfile.vendor`); bis
    dahin standen am MK4S Prozesse von BIBO2, LulzBot, Trimaker und Zonestar zur Wahl.
    Schließt RM-255 für PrusaSlicer. Mit C erledigt: H12 (übernommene Filamentwerte gehen
    mit ihrem Filament) und H15 (eine Spule schreibt nur, was sie ändert).
  - **D steht:** CuraEngine bekommt die Maschine des Druckers (neun Commits im Zweig
    `cura-maschine`, mit A+B zusammengeführt in `c667d7dd5`; Bericht
    `konzepte/nachweise-release-0.5.1/review/cura-paket-2026-09-27/bericht.md`). Die Messung in CuraEngine 5.13 an
    Minigolf-Körper und Waschschüssel über acht Drucker ist vor und nach dem Merge gleich.
    Offen daraus: Curas Fenster bekommt die Stützsperre nicht (gehört zu E). Der Startcode
    der Gemeinschaftsdefinition des SV06 setzt `M201 X500 Y500` und `M204 P500`, das
    kennt Curas Zeitschätzung nicht, der Druck dauert länger als angezeigt. Die Tempi des
    MINI+ in `printers.toml` stammen aus zwei verschiedenen Prozessen (mit C nachziehen).
  - **F steht** (`d4dd5332b`): Die Qualität wählt den Prozess des Herstellers
    (`manufacturer.for_stage`, `slicer_profiles.stage_process`). Abgenommen im Slicer an
    Centauri Carbon 2 (ElegooSlicer: „0.12mm Fine“, „0.28mm Extra Draft“, „0.20mm
    Strength“), P1S (Bambu Studio, dieselben Namen) und MK4S HF0.4 (PrusaSlicer: „0.10mm
    FAST DETAIL“, „0.28mm DRAFT“, „0.20mm STRUCTURAL“): zwölf Läufe mit Schichthöhe und
    Werten des Herstellerprozesses, Umschalten hin und zurück verlustfrei
    (`konzepte/nachweise-release-0.5.1/review/gesamt-2026-09-27/stufe-f/`). Im Dialog stellt die Qualität das
    Prozessfeld und eine Wahl im Prozessfeld die Qualität, sonst „Eigener Prozess“.
    Creality Print nennt jeden Prozess „Standard“; dort liegt die Stufe weiter über dem
    Standardprozess.
  - **L steht** (`e0e3cf982`): Prüfbericht, Analysekarten, Druckbefunde, Ratgeber,
    Agent-Analyse und die Kanalsperre der Übergabe rechnen mit der wirksamen
    Stützschwelle (`Session.evaluation_profile`, `profiles.for_process(...,
    effective=True)`); die Schwelle eines gespeicherten Satzes gilt nur als eigene Wahl.
    Kommt die Grundlage erst nach dem Lauf, wertet das Fenster neu aus. Der
    Schwellenvorschlag am SV06 aus der Gesamtprüfung fällt damit weg.
  - Nebenbei aus der Gesamtprüfung behoben: Rand über den Bettrand und zu hohe Teile
    (`5063fc9f5`), Bambu Studio, das nach der fertigen Druckdatei nicht endet
    (`64a0e4677`, drei von rund hundert Läufen), abstürzende PHP-Prüfserver unter
    Last (OPcache, `f333bd008`), der Hinweis zur Kalibrierung ohne Passung
    (`a97ee3d2e`).
  - **Schrägnaht steht**, aus Roberts Druck des Minigolf-Satzes mit 50 mm/s in der
    ersten Schicht: Die Naht an den vier Schäften (Ø 25,7, 200 mm) kam aus Elegoos Profil
    („aligned“, keine Schrägnaht, Rampenlänge 0), am Ende jeder Außenschleife liefen 0,73
    von 0,8 mm Rückzug im Stillstand. Solidon schlägt für runde Außenwände je Teil die
    Schrägnaht vor (`shell.scarf_seam`, `analysis.smooth_outline_height`) und schreibt
    sie in jeder Familie mit Länge, nur an der Außenwand (Robert: „bei allen Slicern“).
    Abgenommen am Rohr neben einem Klotz: ElegooSlicer, OrcaSlicer, Bambu Studio,
    PrusaSlicer und CuraEngine rampen je 199 von 200 Außenschleifen nur am Rohr, bei
    2 bis 4 % mehr Druckzeit (`konzepte/nachweise-release-0.5.1/review/gesamt-2026-09-27/naht/`); Bambu braucht
    dazu `override_filament_scarf_seam_setting`. Creality Print rechnet 3MF nur im
    Fenster (RM-164), sein Kern kennt dieselben Schlüssel. Der Knick zählt über Arme der
    Düsenbreite wie im Slicer: Am Minigolf-Satz bekommen die vier Schäfte die Schrägnaht,
    der Rumpf mit seinen engen Rundungen nicht, in Solidon wie in ElegooSlicer; die Druckdatei
    zum Vergleich braucht 9:49 statt 9:18 h (G-Code der Gesamtprüfung, nicht versioniert).

  - **E steht** (`2cf02ad2d`, `074364017`, `6daf7ee39`): `for_part` fragt mit Profil jede
    Regel für die geometrischen Pfade (`advise.PART_PATHS`), `handover.split_for_parts`
    setzt die Platte dort auf die Grundlage, Orca und Prusa bekommen Objektwerte, Cura je
    Netz die Rücknahme (`CURA_PER_MESH`); Haftungsprüfung und Stützsperre fragen den Wert
    je Teil, der Konsolenlauf dieselbe Platte. Die Zeile im Druckdialog nennt die Teile
    ([RM-250](ROADMAP-ARCHIV.md#rm-250)); sie und der Export fragen denselben Rat je Teil und Spule
    (`writer.part_advice`) — vorher las der Export nur das Material von Slot 0, und ein
    Griff aus TPU auf einem Teil aus PETG verlor seine langsame Außenwand. Curas Fenster
    bekommt Sperre und Werte je Teil als 3MF (RM-257). Abgenommen am Minigolf-Satz mit
    einem Pilz, der ohne Stütze in die Luft druckt (`je_teil_abnahme`,
    `konzepte/nachweise-release-0.5.1/review/gesamt-2026-09-27/stufe-e*`): ElegooSlicer, PrusaSlicer 2.9.6 und
    CuraEngine stützen nur den Pilz, die Ränder der übrigen Teile bleiben geschlossen.
    PrusaSlicer stützte den Pilz zuerst gar nicht: Der Objektwert setzte
    `support_material` ohne `support_material_auto`, und Prusas Grundlage stützt nur an
    Verstärkern (Entscheidung J, `36ca07053`). Über Orcas Auto-Brim schlägt Solidon
    keinen Brim mehr vor (`83a8e3de1`): Er rechnet aus Höhe und Grundfläche und hielt
    mehr als die feste Breite des Profils (Schäfte 0,9 statt 1,9 m Randbahn).
  - **K steht:** Die Gegenprobe prüft die Grundlage an einer Stichprobe, bei PrusaSlicer
    Modell, Drucker und Startcode (C, `44ab90965`), bei CuraEngine den Namen der Maschine
    und den Startcode vor der ersten Schicht (`f1a1fba65`); an den Druckdateien der
    Abnahme (SV06) still.
  - Aus Roberts Befunden am Abend des 27.09.2026 behoben: Die Erstinbetriebnahme schlägt
    den Drucker des gemerkten Slicers gleich beim Öffnen vor, *Fertig* wartet auf diese
    Suche. Im Druckdialog steht die Slicerwahl über dem zugeklappten Abschnitt, eine
    Druckerwahl dort wird die Vorgabe neuer Projekte, eine gemerkte Maschine gilt nur für
    ihren Drucker und Slicer, und steht der Slicer auf einem anderen Drucker, bietet der
    Dialog ihn an („… übernehmen“; `75bdc1914`, `67f42c99a`). Ein gemessener
    Überhangwinkel gilt nur auf dem Raster seiner Probe (`manufacturer.measured_on`,
    `b50d94d1d`); mit anderer Bahnbreite oder der Stufe „Fein“ stützten Analyse und
    Slicer sonst nach der Probe weiter.

  **Offen, in dieser Reihenfolge:**
  - Danach Paket 3 (Mindestschichtzeit, Keilspitzen, Stützbedarf gegen das Urteil des
    Herstellers, Brückenregel, Inseln an Schrauben) und der Lauf „jedes Modell × jeder
    Slicer“ als Gesamtabnahme.

  Aus Roberts Probedruck am 27.09.2026 (Minigolf-Platte, Elegoos Standard): An den
  schmalen Stegen zwischen Loch 3, Loch 4 und dem inneren Bogen rissen kurze
  Bodenbahnen der ersten beiden Schichten (105 mm/s in Schicht 1, bis 250 mm/s in
  Schicht 2). Der zweite Druck mit der ganzen ersten Schicht auf 50 mm/s lief sauber, die
  Stege geschlossen (Fotos bis Schicht 4; Roberts Urteil: die Einstellungen passen).
  Geändert waren dabei zwei Dinge, das Tempo und die frisch gereinigte Platte.
  `efd4686c2` sorgt dafür, dass das Feld „Erste Schicht“ auch die Füllung trifft. An
  schmalen Stegen schlägt Solidon von sich aus 50 mm/s vor (`advise.NARROW_WEB_*`), nach
  Anteil der ersten Schicht oder nach Fläche: Der Rumpf der Platte trägt 195 mm² Stege,
  aber nur 8,6 % — gegen den Anteil allein blieb die Regel dort stumm. Die Fläche ist an
  186 Körpern des Korpus geeicht (`NARROW_WEB_AREA`).
  Registerabgleich 02.10.: Der Offen-Block beginnt mit „Danach“; es fehlen die offenen Befunde der abgeschlossenen Slicer-Matrix (`konzepte/nachweise-release-0.5.1/reports/rm312-slicer-matrix-2026-10-02.md`, 125 Aufträge, 124 Modelle mit Varianten; Restarbeit RM-312) und die Reste unter D (SV06-Startcode, Tempi des MINI+).

<a id="rm-259"></a>

- [ ] **RM-259 — Eine Mündungsrundung in einer gekrümmten Fläche reist nicht mit ihrer
  Senkbohrung.** Aus der Durchsicht v0.5.1 (rest-bohrung, Rest von
  [RM-248](ROADMAP-ARCHIV.md#rm-248)). An der Lochplatte
  `pegboard-gs-100-v2` liegt zwischen der Zylindersenkung Ø 10 der `hole_3`-Kette und der
  Rundung R 13 des Hakens eine Mündungsrundung R ≈ 1 mm (am STEP vier Spline-Flächen, ein
  Band von 1,7 mm; am 3MF nur zum Teil als `fillet_5` erkannt). Sie gehört nicht zur
  Kette: Beim Versetzen bleibt sie stehen, und die alte Stelle schließt ein Fächer auf
  der mittleren Höhe ihres inneren Rands — je Millimeter −2,5 bis −3,5 mm³ am 3MF und
  −2,9 bis −4,1 mm³ am STEP. Der fortgesetzte Deckel aus RM-248 greift dort bewusst
  nicht: Eine Fläche, die die Rundung fortsetzte, liefe als Trichter ins Loch (am exakten
  Kern in der Durchsicht kurz so gebaut, −7,8 statt −4,1 mm³, vor der Übernahme behoben). Im Nachbau
  (Platte 44 × 24 × 12, Unterseite Zylinder R 20/40, Mündungskante R 1/2 gerundet) fehlen
  am exakten Kern beim Versetzen um 5 mm 13,6 bis 38,7 mm³; am Netz gehört die Senkung
  hinter der Rundung gar nicht zur Kette (Versetzen lässt sie stehen, Entfernen gibt 179
  statt rund 630 mm³ zurück), und bei R 13 sagt der exakte Kern ab. Weg: die Rundung als
  Glied der Kette erkennen (`relations._blended_cavity_faces` soll gerundete Eintritte
  ergänzen und erreicht sie an diesen Netzen nicht); dann ist ihr äußerer Rand die
  Mündung, und Stopfen und Werkzeug kommen aus ebenen oder fortgesetzten Flächen. Sonden:
  `konzepte/nachweise-release-0.5.1/sonden/rest-bohrung/` (`t1_verify`, `t11_rounded_mouth_*`).
  Die erste Abnahme (gs-100 `hole_3` um 1 mm unter 1 mm³) setzte den Sollwert null voraus;
  sie ist unten neu gefasst.

  **Durchsicht v0.5.1, dritte Runde (27.09.2026, rest-muendung):** In einer **ebenen**
  Fläche gebaut (REST-MUENDUNG-02, `202d5133a`). `_blended_cavity_faces` erreichte die
  Rundung, verwarf sie aber, weil es genau zwei Randringe verlangte und der Hohlraum vor
  seinen Schultern vier hat. Mit `relations.cavity_surface_indices(…, mouth_blends=True)`
  verlangt es so viele wie vorher, und der Übergang muss nah an der Wand bleiben
  (`_near_the_wall`) — nur auf den Wegen, auf denen der ganze Hohlraum reist oder geht:
  Versetzen, Verdoppeln, Muster, Entfernen der Kette, am exakten Kern über
  `_exact_chain_own_cavity`. Nachbau Platte 44 × 24 × 12 mit gerundeter Mündungskante r 1
  und r 2: Versetzen um 5 mm ±0,000 mm³ an beiden Kernen (vorher eine Mulde an der alten
  Stelle, eine Haut über der neuen und `move_feature.no_longer_through`), Entfernen genau
  die Platte (vorher −85,35 mm³); am Korpus (225 Dateien, 201 Ketten) keine Kette
  geändert. *Bohrung ändern* und *Merkmal drehen* schneiden weiter aus Profilen und lassen
  die Rundung stehen.

  In einer **gekrümmten** Fläche offen (REST-MUENDUNG-03). Das Band an gs-100 ist gefast
  (rund 1 mm unter 45 bis 57°, kein R 1) und grenzt an den Zylinder R 13, zwei Tori und
  einen Kegel. Derselbe Bau wie seit RM-248 (Stopfen bis zur fortgesetzten Fläche,
  Werkzeug samt Band, starr versetzt) ergibt dort **−2,97 (−z), +0,29 (+z) und
  −4,56 (+x) mm³**, exakt nachgerechnet (`m19_exakt_band.txt`); heute 3MF −3,478 /
  −2,901 / −2,505, STEP −4,072 / −3,108 / −2,911 mm³. Was fehlt: (a) am Netz findet die
  Erkennung die Zylindersenkung hinter einer Rollkugelrundung nicht (Nachbau R 40 / r 1:
  ein Torus mit Rohrradius 80 und eine Kugel R 5,5 statt des Zylinders;
  `features._cylinder_beside_a_torus` trennt nur neben einem belegten Torus); (b) um den
  äußeren Rand kann die Fläche aus mehreren Grundformen bestehen, und ein Polynom trägt das
  nicht (gegen die Fortsetzung von OpenCASCADE: `mouth_cap` mit Randfehler 0,11 bis
  0,23 mm, RBF +10 bis +15 mm³, Polynom mit Randkorrektur +7 bis +18 mm³); (c) am exakten
  Kern trägt der Prototyp `konzepte/nachweise-release-0.5.1/sonden/rest-muendung/m19_exakt_band.py`
  (Stopfen `edit.defeatured`, Werkzeug als Säule über dem Randumriss minus Körper; Nachbau
  R 40 und R 20: +0,0014 bis +0,0023 mm³), braucht aber eine Bandkennung über die nativen
  Flächen am Zwilling und scheitert an gs-100 entlang ±z, wo der versetzte Rand des Bands
  wieder auf dem Zylinder liegt. Weg: am Netz eine Erkennung der Senkung neben einer
  Rollkugelrundung (mit Korpuslauf) und eine Fortsetzung zusammengesetzter Flächen über
  eine Öffnung (je Nachbarfläche die erkannte Grundform verlängern und schneiden, das
  Netzgegenstück zu `BRepAlgoAPI_Defeaturing`); am exakten Kern der Prototyp samt
  Bandkennung und einem Werkzeug, das an der Berührung hält. Abnahme: gs-100 `hole_3` um
  1 mm in drei Richtungen je unter 1 mm³ neben dem Sollwert derselben Bauart (−2,97 /
  +0,29 / −4,56 mm³); Nachbau R 40 / r 1 an beiden Kernen dieselbe Kette und unter
  0,5 mm³ — heute exakt −13,26 mm³, am Netz fehlt die Senkung in der Kette.

<a id="rm-262"></a>

- [ ] **RM-262 — Die Erkennung liest eine gekippte Haltelippe nicht.** Aus der Durchsicht
  v0.5.1 (rest-lippe, REST-LIPPE-04). *Merkmal drehen* an einer Magnettasche sagt seit
  `8e1e3aca5` an beiden Kernen gleich ab, weil keine Erkennung die gekippte Lippe wieder
  liest: Auf der hohen Seite schneidet die Fläche die Lippe weg — der Kegel ist ein
  Teilstück (`partial`, von `narrowings_marked` ausgenommen) —, auf der tiefen führt die
  Öffnung als Schacht zur Fläche, und ein Zylinder mit der engen Weite gilt nach
  `_open_at_the_narrow_end` als Stufe. Am Netz fällt die ganze Tasche in eine gerundete
  Seite (1 077 Nähte unter 1°, 109 Knicke um 20°); dieselbe Tasche ohne Lippe liest es
  als Bohrung. Probeweise zugelassen rechnete jede folgende Handlung ohne die Lippe (am
  Netz still ohne sie oder mit Material in der Öffnung, am exakten Körper ein undichter
  Körper). Unterscheidung von der Stufe im Siebring: Eine gekippte Lippe grenzt auf
  einem Teil ihres Umfangs direkt an die Außenfläche, die Stufe nie. Erst wenn beide
  Erkennungen das lesen (Korpuslauf, kein neu markierter Kegel außer Lippen), wird das
  Drehen freigegeben; der gebaute Drehweg liegt als
  `konzepte/nachweise-release-0.5.1/sonden/rest-lippe/prepare_ops_mit_drehen.patch` bereit, die
  Sonden `r5_nach_dem_kippen.py`, `r6_lippe_messen.py` und `r7_erkennung_gekippt.py`
  daneben. Aus derselben Familie: Nach *Nur Bohrungsdurchmesser* Ø 8,0 setzt die Lippe
  0,33 mm höher an und ist 0,025 mm breit — der exakte Kern liest sie, das Netz nicht
  (Mindestbreite einer Facettenreihe; für den Magneten unkritisch). Abnahme: 10° und 30°
  an beiden Kernen, danach *Bohrung ändern* in beiden Umfängen, Versetzen, Verdoppeln und
  ein zweites Kippen mit Lippe.

  **Durchsicht v0.5.1, dritte Runde (27.09.2026, rest-muendung, REST-MUENDUNG-04): Die
  Absage bleibt.** Der Drehweg aus rest-lippe ist auf den heutigen Stand gebracht und mit
  abgeschalteter Absage an beiden Kernen gekippt worden (Quader 40 × 40 × 10, Magnettasche
  8x3 mittig, `konzepte/nachweise-release-0.5.1/sonden/rest-muendung/m20_lippe_kippen.txt`). Exakt
  sind 10° und 30° dicht (160,255 und 169,053 mm³ abgetragen), und die Erkennung liest
  danach `hole` Ø 8,25, einen angeschnittenen `cone` Ø 8,25 **ohne** `narrowing` und den
  Schacht der Öffnung als Zylinderstück (`fillet` Ø 7,95). Ein angeschnittenes Stück grenzt
  an eine andere Höhlung (`relations._cut_open_neighbours`): keine Kette, und jede
  Körperhandlung danach sagt „kein eigener Körper“. Am Netz (10° und 30°, dicht) steht nur
  `curve_1` da, Tasche, Lippe und Schacht in einem Fleck: Der Lippenkegel steht 20,6° gegen
  die Wand, unter der Knickgrenze von 30°, und zwischen Radien von 3,98 und 4,13 mm gibt es
  keinen Krümmungssprung. Die Unterscheidung oben setzt voraus, dass beide Erkennungen
  Tasche, Lippe und Schacht als Stücke einer Kette lesen. Voraussetzungen damit: am Netz
  Tasche und Lippe getrennt erkennen, am exakten Kern ein angeschnittener Verengungskegel
  samt Schacht als Kette, und `bore_entrance` mit schräger Mündung hinter einer Verengung.
  Der Drehweg liegt auf den heutigen Stand gebracht als
  `konzepte/nachweise-release-0.5.1/sonden/rest-muendung/prepare_ops_mit_drehen_heute.patch`
  (8 Hunks, gegen den Stand mit `2e496575b` und `202d5133a`). Ohne Lippe kippt die Tasche
  seit `2e496575b` an beiden Kernen offen. Die schräg **gesetzte** Tasche aus dem Baustein
  zeigt dieselbe Lücke von der anderen Seite ([RM-277](ROADMAP-ARCHIV.md#rm-277)). Abnahme unverändert.

<a id="rm-273"></a>

- [x] **RM-273 — Das Übernehmen rechnet die Operation noch einmal.** Aus der Durchsicht
  v0.5.1 (rest-merker, Abschnitt 7). Der damalige Profilbefund am Gartenschlauchhalter
  lag bei 16 bis 17,5 s je Übernahme unter Last, davon 9 bis 10 s für *Merkmal verschieben*
  und rund 5 s für dessen örtliche Nachmessung. Die alte Annahme einer erneuten
  Vollqualitätsrechnung gilt im normalen Dialogpfad nicht mehr: `run_operation` erstellt
  einen Auftrag mit festem Dialog-Seed; Vorschau und *Übernehmen* verwenden denselben
  Auftrag, dieselbe Entwurfsqualität und denselben Sitzungscache. Die Erkennung eines
  referenzierten Merkmals bleibt auch in der Vorschau als Abhängigkeit verfügbar.

  **Nachweis 01.10.2026:** Am Gartenschlauchhalter mit 392 532 Dreiecken und 289 Merkmalen
  dauerte der Import 25,52 s, die Vorschau des Versetzens von `hole_10` 18,73 s und das
  anschließende Übernehmen 0,22 s. Beim Übernehmen gab es zwei Cache-Treffer, keinen
  Fehl-Treffer und das Ergebnis war aktuell. Die Abnahme „Übernehmen unter 10 s auf ruhiger
  Maschine“ ist damit erfüllt. Der Dialog-Regressionstest auf `plate_holes.stl` prüft
  zusätzlich, dass derselbe Seed verwendet wird und die Annahme keinen neuen Cache-Miss
  auslöst. Die Vorschau selbst bleibt eine eigene Wartezeit; Bauplan §21.1 und die
  Vollerkennung nach dem Schritt wurden nicht verändert.
  Nachprüfung (Review 02.10., Arbeitsbaum ungesichert): auf Kernebene bestätigt — Übernehmen am Gartenschlauchhalter 0,06 s, keine Fehl-Treffer. Nachweis am echten Fenster steht aus.
  Registerabgleich 02.10.: steht als `[x]` noch im Abschnitt statt im Archiv.

<a id="rm-292"></a>

- [~] **RM-292 — Laufzeitreste der Durchsicht 0.5.1.** Aus der Durchsicht v0.5.1 (Inventar 1.5, 1.7, 1.8,
  `konzepte/nachweise-release-0.5.1/RESTE-INVENTAR.md`). (a) `carpet-corner-clip.step` braucht bis
  „geöffnet“ 201 s (unter Last, nebenbei beobachtet, nicht gegen HEAD gemessen; Vermutung:
  exaktes Volumen im UV-Rückfall wie REST-BOHRUNG-01, `b0d344e5c`). (b) Die
  Eigenkreuzungs- und Überschneidungssuche kostet 7,5 bis 8,3 s (Besenhalter:
  `intersections._candidates` 5,8 von 6,4 s, darin `_separated` 2,9 s; große Hälfte des
  Laptop-Ständers 8,3 s einmal je Modell beim ersten Booleschen Schritt). (c) Die
  Schichtanalyse ineinandersteckender Teile schneidet über `polygonize` und `unary_union`
  (60 % der Schnitte, je Schicht rund 5 ms, hält den GIL). Die Größenänderung einer großen
  Bohrung (rund 26 s, Inventar 1.6) gehört zu [RM-132](#rm-132) und [RM-193](#rm-193).
  Abnahme: je Punkt am HEAD nachgemessen; bleibt es langsam, eingegrenzt und mit Ziel
  geführt.
  Registerabgleich 02.10. (Stand `3fd3b1ace`): (a) am Kernweg Import 4 s, Auswertung 5 s statt 201 s; (b) Besenhalter weiter 10,4 s, davon `_candidates` 5,8 s und neu `crossing_pairs` 4,5 s seit `eae249d2d` — die Zahlen im Eintrag sind überholt; (c) nicht gemessen.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** (b) Bereits belegte gemeinsame
  Kanten scheiden vor der Kollinearitätsfrage aus, die vier Punktfragen enden beim ersten
  Gegenbeleg; koplanare Überlagerungen bleiben vollständig geprüft. Vorher ein roter
  Verbrauchernachweis, danach 38 Fälle grün. Am Original zweimal vorher/nachher: Besenhalter
  18,44/18,44 → 15,13/14,62 s, Laptopständer 28,61/26,00 → 20,13/20,89 s, alle 41 309 Paare
  bitgleich, unter Fremdlast. (c) Schon vereinigte gültige Clipper-Ringe werden nicht erneut
  vereinigt; ma-mi-ya und Greasetool je Schicht ohne Flächendifferenz, 214 Schnittfälle grün. (a)
  lag bei der Import-/Erkennungslinie, dazu gibt es keinen Bericht. Beleg:
  `F:\solidon-review-reports\codex-2026-10-03\geometrie\druckvorbereitung\bericht.md` (RM-292).

<a id="rm-296"></a>

- [~] **RM-296 — Die genaue Vorschau großer Teile rechnet am ganzen Körper.** Aus dem Release 0.5.1 (Paket hilfsprozess, Rest von
  [RM-212](ROADMAP-ARCHIV.md#rm-212)). Seit 0.5.1 steht der Hauptfaden dabei nicht mehr
  still, die Dauer bleibt: Senkplatte 4,3 bis 5,7 s auf ruhiger Maschine statt unter 3 s.
  Profil (Ø 6,5, unter Last, 16,3 s): Auswertung von *Bohrung ändern* 11,2 s — vier
  Boolesche 6,0 s, `_detect_resized_bores` 3,4 s, `resize_bore` 2,7 s,
  `_neighbour_bore_findings` 1,8 s — und `compare_scenes` 5,1 s (`_cut` 2,8 s,
  `_clipped_to_the_change` 1,8 s). Weg: den Hohlraum am örtlichen Ausschnitt tauschen statt
  am ganzen Körper (`prepare_ops.resize_hole`, `difference.compare`). Abnahme: Senkplatte
  genau unter 3 s auf ruhiger Maschine.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):**
  `perceive/local.py::_known_through_wall` lässt allein eine bekannte Durchgangswand samt
  Nachbarring unter dem Budget von 50 000 Dreiecken nachmessen; ohne positiven Nachweis bleibt der
  Rückfall. `_with_features` in `scene/evaluate.py` entscheidet über `needed` statt über das globale
  `referenced`, die letzte Ausgabe wird nicht mehr voll erkannt. 148 lokale und 199 Auswertungsfälle
  grün; Durchmesser, Tiefe und Durchgang gleich der Vollerkennung, auch um 37° gedreht. Sitzungsweg
  Ø 6/6,5/7: vorher 10,0/5,8/5,8 s, jetzt 7,59/4,59/3,47 s unter Last, die Quelle kommt aus dem
  Cache. Beleg: `F:\solidon-review-reports\codex-2026-10-03\geometrie\erkennung\bericht.md`
  (RM-296).

<a id="rm-298"></a>

- [~] **RM-298 — Hilfsprozess: Reste aus dem Review.** Aus dem Release 0.5.1 (Review des Pakets hilfsprozess,
  `konzepte/nachweise-release-0.5.1/reports/review-hilfsprozess.md`). (a) Der Deckel
  `MOST_HELPERS` hält nicht: nachgestellt liefen 6 statt 3 Hilfsprozesse zugleich. (b) Unter
  Linux und macOS bleibt nach Absturz oder Abbruch gemeinsamer Speicher in `/dev/shm`
  liegen, anders als die Docstrings sagen; ein volles `/dev/shm` meldet `ENOSPC` als
  `MemoryError`, und beim Beschreiben eines fast vollen kann `SIGBUS` den Elternprozess
  reißen. (c) Sieben breite Fänge im Anwendungscode schlucken einen verlorenen
  Hilfsprozess noch, etwa `prepare.py` unter `shared_volume`; `kern.md` formuliert die Regel
  ausnahmslos — Regel ergänzen oder die Stellen nachziehen. (d) Testlücken: Der Test zum hart
  beendeten Elternprozess bleibt auch ohne Jobobjekt grün, die niedrigere Priorität hat
  keinen Test, die §31-Leistungsmarken rechnen nie über den Hilfsprozess. (e)
  `Session.evaluate_now` erklärt einen laufenden Arbeiter für überholt, bricht ihn aber nicht
  ab (Kommandozeile, Tests, Export). (f) Der Rauchtest im Paketjob verlangt das eigene Ende
  in der Produktfrist von 0,5 s; auf einem langsamen Mac-Runner bleibt ein kleines
  Wackelrisiko. Abnahme: je Punkt behoben oder mit Grund begrenzt.

  **Teilstand 02.10.2026, (a):** Der heutige Code bestätigte den alten Deckelfehler
  auch während offener Starts und Stopversuche. Reservierte Starts und der gesamte
  Besitzbestand zählen bis zum bestätigten Prozessende; fehlgeschlagene Stopversuche
  behalten ihren Platz und einen erneuten Aufräumweg. Shutdown nimmt offene Starts
  mit, gibt seine Schließsperre auch bei Fehler frei und trennt alte Rückgaben sowie
  bleibende Absagen vom neuen Bestand. Auch ein beim Konstruktor-Aufräumen noch
  lebendes Kind bleibt erfasst. Ein nicht beendbarer Helfer meldet einen übersetzten
  KernelHelperStopError mit tatsächlichen Fehlerbericht-Handlungen; seine technische
  PID steht im Protokoll, nicht als unbeschrifteter Kundenwert. Nach einem gescheiterten
  Vorabstart meldet auch die nächste öffentliche run-Anfrage den noch offenen Stopfehler
  vor dem lokalen Rückfall; auch bei wartender Platzsuche, stummer Antwort und
  bleibender Absage eines anderen Helfers. Ein erfolgreicher Aufräumversuch hebt die Sperre auf;
  harmlose Vorabimport-/Startfehler behalten ihren lokalen Rückfall.
  Zehn ursprüngliche und sechs zusätzliche Reviewgegenproben scheiterten vor den
  jeweiligen Korrekturen an den echten Kontrollflüssen. Die zentrale Anschlussprüfung
  fand danach zwei weitere Fehler: PID-Kundenwert und vom Warmup verschluckter
  Neustartbedarf. Die jeweiligen Gegenläufe waren tatsächlich 4 rot; beim Warmup
  zusätzlich 2 bereits grüne Kontrollfälle. Keine Setupfehler dieser Gegenläufe.
  Die eigene reine Pool-/Faden-/Sprach-/Warmupgruppe umfasst jetzt 33 Fälle. Frisch
  bestehen 79 Kernel-Entwicklungsfälle mit echten Prozesswegen sowie der unveränderte
  Beschriftungswächter, zusammen 80 grün (1 Fenstertest abgewählt, Exit 0);
  Quell-/Testhashes vor/nach identisch. Ruff, Format und Diffcheck sind grün.
  Eigenreview und erneutes unabhängiges Quell-/Nachweisreview der Nachgänge
  ohne offene Befunde abgeschlossen. Das vollständige zentrale Entwicklungstor
  bestand mit 19.033 Tests und 62 Überspringungen; Kernsammlung, Ruff, Format
  und mypy jeweils Exit 0. Teilkorrektur a45730c79f1d7ad6416d2bd1b6b68b5a0f24f311
  ist auf origin/main; [fortsetzbare Pool-/Anschlussbelege](konzepte/nachweise-release-0.5.1/reports/rm298-poolnachweise-2026-10-02.md).
  (b)–(f) bleiben offen; der vorhandene Eltern-Endetest prüft ein
  untätiges Kind und ersetzt keine aktive Jobobjekt-, Prioritäts-, Paket-,
  Linux-/macOS- oder Release-Leistungsabnahme.
  Registerabgleich 02.10. (Stand `3fd3b1ace`): (a) ist mit `a45730c79` in HEAD und `origin/main`; der Satz „Commit/origin/main stehen aus“ und die Registerzelle sind damit veraltet, offen sind (b)–(f). Neu dabei: `test_the_workers_of_the_window_use_the_helper` hängt von der Reihenfolge ab (RM-380). Beleg `F:\solidon-review-reports\register-geometrie.md`.
  Review 02.10. von `a45730c79`: Ein Hilfsprozess, der erst nach der 5-s-Frist endet, sperrt alle Kernrechnungen bis zum Neustart — eigener Punkt RM-384.

  **Anschlussnachtrag 02.10.2026, (a)/RM384:** Die im Stand
  `a45730c79` noch vorhandene Dauersperre nach einem erst später beendeten
  Helfer ist durch `686abf9e63ed8708d15fdc642add170cb1d2c14f` auf dem tatsächlichen
  `origin/main` behoben. Nach bestätigtem Ende sammelt die nächste öffentliche
  `run`-/`take`-Anfrage den Rest ein, ohne vorheriges `shutdown`; lebende
  Stoppreste und bleibende Start-/Helferabsagen sperren weiterhin angemessen.
  [Datierter RM384-Abschluss](ROADMAP-ARCHIV.md#rm-384) und
  [portabler Anschlussbeleg](konzepte/nachweise-release-0.5.1/reports/rm384-spaetes-helferende-2026-10-02.md).
  Native Windows-Killlatenz, POSIX-, Paket-, Fenster-/Renderer- und
  Leistungsabnahmen bleiben offen; RM298 als Gesamtpunkt bleibt `[~]`.

  **Teilstand 02.10.2026, (d), Windows-Prozesswächter:** Neue getrennte Kernfälle
  prüfen den Helfer während einer wirklichen öffentlichen run-Rechnung und lesen
  seine Priorität nach dem normalen serve-Start beim Betriebssystem. Endstand
  2/2 grün, auch unter Konsolenwächter; je abgeschalteter Elternbindung/Priorität
  genau 1 beabsichtigtes Assert rot, keine Setupfehler und bestätigter Abbau.
  Gehaltene wirkliche Griffe unterscheiden auch den .venv-Launcher vom
  Python-Elternprozess; der äußere Aufräumjob bleibt bis nach der Zusicherung
  geöffnet. Eigenprüfung und unabhängiger Quell-/Nachweisreview ohne Befunde.
  [Dauerhafter Prozess-/Prioritätsbeleg](konzepte/nachweise-release-0.5.1/reports/rm298-lifecycle-2026-10-02.md).
  Diese getrennte Testeinheit ist mit d9f830aec41ae0531784406b75ad4a0fb549b4a6
  auf dem tatsächlichen origin/main. Das unveränderte zentrale Entwicklungstor
  bestand mit 19.059 Tests, 62 Überspringungen und Suite/Ruff/Format/mypy jeweils
  Exit 0. Der bestehende untätige Test bleibt erhalten. Tatsächliche
  §31-Hilfsprozessmarken, Linux/macOS und Paketnachweise bleiben offen.

  **Teilstand 02.10.2026, (c), geometrische Fänge:** Alle sieben benannten
  Fänge geben Abbruch, verlorenen Helfer und Stopfehler unverändert
  weiter, bevor normale Geometrieauswege greifen. Tatsächlich zuvor
  14 Testkörperfehler, danach 14 neue und 19 bestehende Kontrollen grün,
  keine Aufbau-/Abbaufehler oder Skips. Nach finaler Importbereinigung
  und abgestimmter RM327-/RM434-Basis erneut 14+19 grün, jeweils Exit 0
  und 16 stabile Quell-/Test-/Korpusdateien; historische Hashstände
  bleiben getrennt erhalten. Ruff, 26 eigene Formatbereiche und
  unabhängiger Quell-/Testreview sind grün. Der tatsächliche Session-/
  CLI-Cacheanschluss trennt Altresultate beim normalen Neustart/Update
  über Quellstand bzw. Releaseversion; keine zusätzliche Format-/Opzahl.
  [Portabler Weitergabe-/Cachebeleg](konzepte/nachweise-release-0.5.1/reports/rm298-weitergabe-2026-10-02.md).
  Eigenständiges vollständiges Tor und tatsächliche Integration dieser
  Einheit stehen aus; native Prozess-/Plattform-/Paket-/Releaseabnahmen
  bleiben gesondert offen. RM298 bleibt `[~]`.

  **Teilstand 02.10.2026, (d), Vergleichsmarken:** Zwei zusätzliche öffentliche
  Arbeiterwege für Boolesche Rechnung und Anzeigeausdünnung sind vorbereitet:
  warmer Helfer, Produktionsschwelle, API samt Übertragung/Nacharbeit und
  getrennte Eingangscaches. Pfad-, Ergebnis- und Eingangsprüfung erfolgt
  außerhalb der Uhr und vor jedem Markenzugriff. Der Abbruch erreicht vor
  dem Executor-Beitritt den Helfer; danach werden verspätete Starts gesammelt.
  Frisch bestehen 14 reine Markenmechanikfälle. Sieben Gegenfälle mit
  nachgestellten Prüfablehnungen scheitern bei absichtlich verspäteter
  Prüfung an denselben Marken-Zusicherungen
  (jeweils keine Setupfehler/Skips, Exit 0 beziehungsweise 1). Der damalige
  Importgraph-Nachlauf hatte neun fremde RM-320-Gegenfälle rot; er wird nicht
  als grüner Gesamtlauf ausgegeben. Eigenreview und unabhängiges Quell-/
  Mechanikreview sind abgeschlossen; der unabhängige Dokumentnachgang
  präzisierte die nachgestellten Prüfablehnungen ohne weitere Funde.
  Die Quellen-/Mechanikeinheit ist mit 7f0de659d2c8fc1e35bd1067e738bcaef7f1ec72
  auf dem tatsächlichen origin/main. Zentrales Entwicklungstor: 19.066 bestanden,
  62 übersprungen, Suite/Ruff/Format/mypy jeweils Exit 0, keine Quelldrift.
  [Fortsetzbarer Messanschluss](konzepte/nachweise-release-0.5.1/reports/rm298-hilfsprozessmarken-2026-10-02.md).
  Keine performance-Fälle gesammelt/ausgeführt, keine Laufzeitabnahme.
  Referenzmaschine, übrige §31-Marken, farbige Slots und Plattform-/Paketwege
  bleiben im Release zu prüfen; RM-298 bleibt offen.
  Review 02.10. (`7f0de659d`): Der neue Bericht `rm298-poolnachweise-2026-10-02.md` (Z. 22, 26, 61) erklärt (a) für geschlossen, ohne zu sagen, dass nur `shutdown` die Sperre nach einem späten Prozessende aufhebt (RM-384).

  **Teilstand 02.10.2026, (f), Rauchtest-Endebudget:** Das Prüfwerkzeug
  übernimmt vor den Paketphasen sein eigenes freiwilliges Endebudget von
  30 s. Die Herkunft ist der bestehende unabhängige Endetest; die
  Produktfrist bleibt 0,5 s. Tatsächlich zuvor 1 Testkörperfehler und
  2 grüne Kontrollen, danach 4 reine Prozessattrappen-/Anschlussfälle
  grün, jeweils ohne Aufbau-/Abbaufehler oder Skips und mit fünf stabilen
  Hashes. Erzwungener Tod bleibt rot, weiterlebende Kinder behalten
  Besitz und Stopfehler; Rücksetzen nur des Werkzeugbudgets erzeugt den
  alten Fehler erneut. Ruff, eigene Formatbereiche und unabhängiger
  Quell-/Nachweisreview sind grün.
  [Portabler Werkzeug-/Gegenlaufbeleg](konzepte/nachweise-release-0.5.1/reports/rm298-rauchtest-2026-10-02.md).
  Zentrales Tor und tatsächliche Git-Integration dieser Einheit stehen
  aus. Wirklicher Paketlauf, langsamer macOS-Runner und native
  Ende-/Killlatenz sind weiter Releaseabnahmen; RM298 bleibt `[~]`.

  **Teilstand 02.10.2026, (b), Transfermangel:** ENOSPC bleibt als
  `OSError` vom tatsächlichen Speichermangel getrennt; ein abgewiesener
  Eltern-Eingangs- oder Helfer-Eingangs-/Ergebnistransfer nimmt den bestehenden
  lokalen Rückfall. ENOMEM, Windows 8/14/1450/1455 und ein ursprünglicher
  `MemoryError` bleiben Speichermangel, ohne lokale Zweitrechnung.
  35 kleine direkte und öffentliche Anschlussfälle: zuvor 5 ENOSPC-Fälle
  im Testkörper rot und 30 Kontrollen grün, danach 35 grün; keine Aufbau-/
  Abbaufehler oder Skips. Das ganze Kernel-Entwicklungsmodul besteht mit
  141 Fällen, 1 Fenstertest abgewählt, Exit 0; drei Quell-/Testhashes stabil.
  [Portabler Transfer-/Ursachenbeleg](konzepte/nachweise-release-0.5.1/reports/rm298-enospc-2026-10-02.md).
  Vollständiges Tor und Integration dieser Teileinheit stehen noch aus.
  Wirklicher POSIX-Speicherbesitz, SIGBUS, Crashbereinigung, Linux/macOS,
  Paket- und Release-Abnahmen bleiben offen; RM298(b) ist damit nur teilweise
  bearbeitet, RM298 als Gesamtpunkt bleibt `[~]`.

  **Teilstand 02.10.2026, (e), synchrones Ersetzen:** Die Session fordert
  das alte Arbeiterende an und bestätigt es vor Reset und neuem feinen
  Lauf. Ein unbestätigtes Ende hält Arbeiter/Abbruch/Ergebnis und sagt
  die neue Rechnung über UserError mit Abbrechen ab. Wartende alte
  Kernfragen erkennen Verfall ohne Antwortempfänger; nach Reset oder
  später Antwort bleiben sie ungültig. Zuvor sechs Testkörperfehler,
  danach sechs reine Namespace-/Ereignis-/Fadenfälle grün. Der konkrete
  Fehlerklassenfund wurde vorwärts korrigiert; frisch bestehen sieben
  Fälle einschließlich unverändertem Wächter, das Auswertungsmodul mit
  190 Fällen und die Sprachgruppe nach beiden neuen Schlüsseln mit
  628 Fällen (je Exit 0, keine Fehler/Skips, Hashes stabil). Finales
  Ruff/Format/Diffcheck und erneuter unabhängiger Produktreview sind grün.
  [Portabler Session-/Fragenbeleg](konzepte/nachweise-release-0.5.1/reports/rm298-sitzungsabbruch-2026-10-02.md).
  Der historische Modulgegenlauf mit einem fremden RM327-Fehler bleibt
  erhalten. Zentrales Tor und tatsächliche Integration dieser Einheit
  stehen aus; native Qt-/Fenster-/Abbruchlatenz bleibt Releaseabnahme.
  B01-Export-/Sliceranschlüsse sind separat abgestimmt; RM298 bleibt `[~]`.

<a id="rm-307"></a>

- [~] **RM-307 — Auto Split: Reste aus dem Review der Vorauswahl.** Aus dem Release 0.5.1 (Fix `autosplit-lagen-051`,
  `konzepte/nachweise-release-0.5.1/reports/review-autosplit-lagen.md`). Seit 0.5.1 hält die
  Vorauswahl für Auto Split ihren letzten Platz für die billigste stehende Lage frei, wenn
  keine der drei vorderen steht. (a) Steht eine der vorderen, aber teuer, bleibt ihr Preis zu
  hoch (ma-mi-ya mit Stiften an A 1 679 711 statt 63 010 mm³; an 3 von 114 Modellen fielen
  Nahtentscheidungen auf solchen Zahlen, jedes Mal mit gleich viel oder weniger Stütze als
  vorher). (b) Für das schnellere `_contact` fehlt ein bleibender Gegentest gegen eine
  Auswahl nach Brute Force an den Toleranzrändern (belegt ist die Gleichheit nur in der
  Review-Sonde). (c) Ohne übersetzten Schnittkern (`_chain`) braucht der Leistungstest
  23,6 s statt 20; das Paket liefert den Kern aus, der Test misst dann den Rückfallweg.
  Abnahme: je Punkt behoben oder begründet belassen.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `orientation_scores` im optionalen
  Cythonkern rechnet dieselben Projektionen und `IntegerGrid`-Summen, die NumPy-Fassung summiert nur
  gewählte Flächen (`IntegerGrid.of(count=)`); vier Gegenfälle mit verschiedenen Überhanggrenzen
  bitgleich. `best_face_candidate` misst den Stützraum am `search_proxy`, Stand und Kandidaten
  bleiben am Original; an 20 echten Körpern gleiche Richtung, Standfläche und Stabilität. 209 bzw.
  217 Orientierungs- und Auto-Split-Fälle grün, Stand an Toleranzrändern, beide Stiftseiten, drei
  Nahtlagen. Messfenster 14:53: T2 nativ 16,0/14,7/19,7 s, ohne beide Kerne 16,7/16,5/23,4 s bei
  31–183 fremden CPU-Sekunden, alle Nähte gleich. Beleg:
  `F:\solidon-review-reports\codex-2026-10-03\geometrie\druckvorbereitung\bericht.md` (RM-307).

<a id="rm-322"></a>

- [~] **RM-322 — Tragende Netzkanten am exakten Körper wiederfinden.** Rest aus RM-284.
  **Präzisierte Diagnose am 02.10.2026:** Am unveränderten `pegboard-gs-100-v2.step`
  haben vier der zehn gewählten Netzzüge einen nativen Partner; dort muss das Maß unter
  0,8535533905932737 mm bleiben. Die übrigen sechs liegen innerhalb nativer Flächen und
  haben keine eigene Topologiekante. Die frühere Aussage über sechs passende exakte
  Rundungen war zu weitgehend; der historische Netzversuch in
  `konzepte/nachweise-release-0.5.1/laeufe/kanten-gruppe-brep2.txt` bleibt unverändert.
  **Umgesetzt:** Herkunft, vollständiger Kurvenverlauf und eindeutiger Partner belegen
  die Zuordnung. Teilwahl, fehlende Herkunft oder leere Gruppen erweitern die Auswahl
  nicht auf alle nativen Kanten. Nach Bandfilterung wird die Restabdeckung erneut geprüft;
  Abbruch, vollständige Ortskonturen und Berichtanschluss bleiben erhalten. Beide
  Operationscaches stehen auf 14. Zwei unabhängige P1-Befunde und ein Toleranz-P2 sind mit
  echten roten/grünen Gegenfällen korrigiert und im Nachreview freigegeben.
  **Fachnachweise:** 57 direkte Fälle einschließlich vier analytischer Verlaufs-/Cache-/
  Folgefälle, sechs Kundenfälle in beiden Güten sowie Fehlerort- und Übersetzungsprüfungen
  grün. R0,3 bearbeitet vier Kanten und nennt sechs ausgelassene Stellen. R1/R2 sagen begründet ab,
  erhalten den Körper und nennen alle zehn Stellen. Quelle und Dateihash bleiben gleich.
  Beleg: [Zuordnung, Gegenproben und Kundenmodell](konzepte/nachweise-release-0.5.1/reports/rm322-native-edge-binding-2026-10-02.md).
  Die gezielte Statikprüfung und alle 32 Dokumentwächter sind ebenfalls grün.
  **Zentrale Übernahme:** Zweitreview freigegeben; Entwicklungstor mit 19.464
  bestandenen und 62 übersprungenen Tests, Ruff/Format/mypy je Exit 0, ohne
  Quellenabweichung. Commit `0041000a0` enthält alle 17 Pfade; 38 unabhängige
  Inhaltsvergleiche passen. Der Push nach `origin/main` ist noch nachzuweisen.
  Fenster-, Renderer- und Leistungsabnahme gehören weiterhin zum Release.

<a id="rm-327"></a>

- [~] **RM-327 — Der Zerfallssatz einer Bohrung verschwindet, sobald sich die Teilezahl ändert.**
  Review seit 0.5.1, Befund A-M2, Commit `55515ca03` (Claude); schwächt die Zusage von
  `23a0eb8fa` („bleibt zerfallen → Satz bleibt“).
  `app/core/scene/evaluate.py:1548` (`"bore.splits_the_body": "count"` in `COUNTED_PARTS`) mit
  `:1850–1852` in `_without_outdated`: Jede abweichende Zahl streicht den ganzen Befund.
  **Fehlerfall (beide Kerne):** Würfel 20 mm, Langloch A quer (2 Teile), Langloch B quer dazu
  (4 Teile), dann ein Quader vereinigt, der zwei Viertel überbrückt → Endstand 3 lose Teile, im
  Prüfbericht kein Zerfallssatz. Der Kunde druckt drei lose Teile ohne Hinweis.
  **Fix:** Zahl am Endstand nachführen wie bei `ingest.small_components` (`dataclasses.replace`
  im Zweig von `_without_outdated`); gestrichen wird nur, wenn der Körper ein Stück ist.
  Zugleich die Gegenrichtung aus `23a0eb8fa` vervollständigen: In `ONE_PIECE_CODES`
  (`evaluate.py:1528–1537`) fehlen `label.fell_apart` (`geom/label_ops.py:675`),
  `texture.fell_apart` (`geom/texture_ops.py:758`), `parts.hanging_loose`
  (`knowledge/parts/ops.py:569`), `blend.still_apart` (`geom/blend.py:403`) und
  `sketch.join_apart` (`sketch/ops.py:665`) — Fehlerfall: Schrift neben einem Quader („liegt in
  2 losen Stücken“), danach Grundplatte unter beidem vereinigt → ein Stück, der Satz bleibt.
  **Abnahme:** Test der Brückenfolge an beiden Kernen (Satz mit Zahl 3) und je Code ein Test,
  dass der Satz am einteiligen Endstand fällt. Bauplan §17.3, §15.
  Beleg: `bericht-A.md` (M2, N2), Sonden `a_zerfall_teilezahl.py`, `a_schrift_lose_dann_vereint.py`.
  Nachprüfung am Stand `6ce767031`: besteht noch, beide Teile. Nach der Brückenfolge an beiden Kernen 3 Teile ohne Zerfallssatz; `label.fell_apart` bleibt nach der Vereinigung zu einem Teil stehen. Die fünf Codes fehlen weiter in `ONE_PIECE_CODES` (`evaluate.py:1528–1537`).
  **Umsetzung und Fachnachweise 02.10.:** Die sechs beauftragten Codes verwenden eine
  nachgewiesene Materialzahl; die übrige Schalen-/Komponentenzählung bleibt getrennt.
  Der Bohrungshinweis erhält am dreiteiligen Endstand die Zahl 3. Ein belegter
  einteiliger Körper entfernt den Hinweis; ein unbewiesener Zustand erhält ihn.
  Die tatsächliche Brückenfolge an beiden Kernen und in beiden Qualitätsstufen,
  alle fünf registrierten Ausgeber, warme Cachetreffer, Undo/Redo sowie Abbruch
  sind geprüft. 56 direkte Fälle und der überlappende Nachgang mit 155 gezielten
  Fachfällen sind grün; ebenso 14 Karten- und 610 Sprach-/Werteprüfungen.
  [Portabler Beleg](konzepte/nachweise-release-0.5.1/reports/rm327-final-report-parts-2026-10-02.md)
  mit Rotnachweisen und genauer Abnahmegrenze. Code und Dokumentation sind unabhängig
  freigegeben; 32 Dokumentprüfungen sind grün. Zwei spätere Wächter des gemeinsamen
  Baums melden fremde Stellen, die ihre Bearbeiter korrigiert haben; deren Gegenläufe,
  das vollständige Entwicklungstor und der Commit-/Pushbeleg bleiben offen.

<a id="rm-365"></a>

- [ ] **RM-365 — *Festschreiben* einer Formsitzung friert das Entwurfsnetz ein.**
  Review 02.10.2026, Gebietsprüfung Weg 4 (W4-5), am HEAD `6ce767031`.
  `app/ui/session.py:2737–2743` schreibt das im Fenster gerechnete Netz fest — das ist die
  Entwurfsstufe.
  **Fehlerfall:** Fein vor dem Festschreiben 9 974 Dreiecke, 14 433,6 mm³; nach dem
  Festschreiben 6 964 Dreiecke, 14 056,4 mm³ (−2,6 %), Form bis 0,94 mm verschoben (Median
  0,03 mm). Der Export wird schlechter als ohne Festschreiben.
  **Fix:** beim Festschreiben mit `quality="fine"` rechnen.
  **Abnahme:** Test: Festschreiben ändert Dreieckszahl und Volumen der feinen Auswertung nicht.
  Bauplan §31, §2.2.
  Belege: `gebiet-weg4.md`, Sonde `w4_einbacken_entwurf.py`.

<a id="rm-381"></a>

- [ ] **RM-381 — Boolesche Ops an mehrschaligen Modellen sind seit `eab5f4f47` 8- bis 15-mal langsamer und nicht abbrechbar.**
  Review 02.10.2026 der Commits bis `3fd3b1ace`, Fund 1. Die Berührungsvorfrage läuft jetzt ohne
  Paarbudget (`app/core/geom/boolean.py:490–496`); damit entfällt der Frühabbruch in
  `repair.py:1459–1462`, und die Schleife `:1466–1485` zählt jeden Kandidaten ab (Zeit fast ganz
  in der Kandidatenaufzählung: 4,59 s gesamt, davon 0,04 s in `crossing_pairs`). In `drill`,
  `slot_bore` und `resize_bore` kommt kein `cancelled` an (`prepare.py:892`, `:1086`, `:1858`,
  `:1934`).
  **Fehlerfall:** `drill_hole` am Besenhalter (`broomholdervcd_d35mm.stl`): vorher 0,29–0,35 s,
  jetzt 4,33–4,95 s; Mini Golf v17: 0,46–0,56 s → 3,94–4,32 s; Ergebnisse gleich (zwei Runden im
  Wechsel gegen den Stand `3739d46af`). Im Korpus 2 von 65 mehrschaligen Körpern betroffen. Die
  4 s lassen sich nicht abbrechen (§2.8).
  **Fix:** Kandidaten über ein räumliches Raster bzw. einen Hüllquaderindex statt über die
  Achsenüberdeckung erzeugen; bis dahin ein Deckel, der „unbekannt“ weiterrechnet und es als
  Befund sagt; `cancelled` bis in die Vorfrage durchreichen.
  **Abnahme:** Messung `drill_hole` am Besenhalter wieder ≤ 0,5 s (Budget §31, Regressionsschwelle
  25 %), Abbrechen während der Vorfrage wirkt; Ergebnisse unverändert.
  Belege: `F:\solidon-review-reports\review-3fd3b1ace.md`, Sonden `r_besenhalter_zeit.txt`,
  `r_besenhalter_paare.txt`, `r_korpus_vorfrage.txt`.
  Review 02.10. (`e3dff1907`): Der neue Trennbeleg (`prepare_ops.py:3716–3724`) ruft die ungebremste Berührungssuche bei jedem Merkmalklick (`app/core/perceive/actions.py:740–748`) und vor `slot_hole` ein zweites Mal — Besenhalter, Bohrung `hole_5`: Merkmalklick 4,75–5,50 s statt 0,01–0,07 s, `slot_hole` 15,2–16,6 s statt 10,8–12,5 s; so lange zeigt das Merkmalfenster keine Handlung. Bis zum Fix den Beleg erst bei *Zum Langloch ziehen* rechnen und das Kontaktergebnis je Netz merken (`sonden\r3_besenhalter_*.txt`).
  Ergänzung Bibliotheksprüfung 02.10.2026: Ein übersetzter Hüllquader-Sweep braucht am Besenhalter 0,5–0,8 s statt 8,6–19,2 s, an Mini Golf v17 0,3–0,4 statt 8–13 s, bei gleichem Ergebnis; manifold3d (Schnittvolumen je Paar) 0,06–0,47 s, aber nur für gültige Teile und ohne bloße Flächenberührung — als Vorweg, der Sweep als allgemeiner Weg. Beleg `bibliotheken\befunde.md`.

<a id="rm-382"></a>

- [ ] **RM-382 — Ein Mehrschaler mit einer selbstkreuzenden Schale lässt sich seit `eab5f4f47` gar nicht mehr bearbeiten.**
  Review 02.10.2026 der Commits bis `3fd3b1ace`, Fund 2. `app/core/geom/boolean.py:214–225` hält
  vor Stufe 1, gleich wo das Werkzeug ansetzt; der Satz „Dieser Schritt ließ sich mit diesen
  Körpern nicht zuverlässig berechnen.“ nennt keinen Grund und keinen Ausweg. Nur 14 von 114
  Aufrufen der Netz-`boolean()` übergeben `object_ids`. Das kehrt die im Register dokumentierte
  RM-253-Entscheidung um (Registerzeile RM-253 und Eintrag; ein dort genannter Test wurde
  entfernt).
  **Fehlerfall:** Echter Laptop-Ständer (21 Teile, 173 592 Dreiecke): `drill_hole` hält an jeder
  Stelle mit `object_id=None` und `correct_input`/`cancel`, auch wo die Bohrung nichts trifft;
  vor `eab5f4f47` rechnete derselbe Schritt mit `boolean.parts_not_united` (Warnung).
  **Offen für Robert:** Halten nur, wenn das Werkzeug die kaputten Schalen berührt, oder immer?
  **Fix (unabhängig davon):** Kennung an allen Aufrufen durchreichen und als Pflicht in die Regel
  (`.claude/rules/operationen.md`); Satz mit Grund und Ausweg (*Stellen zeigen*, *Zerlegen*);
  §17.2 bzw. die Regel nennen den Halt.
  **Abnahme:** Test am Laptop-Ständer bzw. einem kleinen Zwilling: Bohrung abseits der kaputten
  Schale rechnet (oder hält nach Roberts Entscheidung) — in jedem Fall mit `object_id` und einem
  Satz mit Grund und Handlung. Bauplan §2.7, Regel 17.
  Belege: `review-3fd3b1ace.md`, Sonde `r_laptopstaender.txt`.
  **Entscheidung Robert 02.10.2026:** „Das Beste für Kunden, damit sie bearbeiten können.“ Umgesetzt heißt das: Gehalten wird nur, wenn das Werkzeug eine selbstkreuzende Schale tatsächlich berührt (Hüllquader- und dann Schnittprüfung gegen die kaputten Schalen). Trifft es nur intakte Schalen, rechnet der Schritt wie vor `eab5f4f47` und meldet die kaputte Schale als Warnung mit *Stellen zeigen* und *Reparieren*. Hält er doch, nennt der Satz die Schale und bietet *Reparieren*, *Stellen zeigen*, *Abbrechen* an, mit `object_id`. Abnahme damit: Bohrung abseits der kaputten Schale am Laptop-Ständer rechnet mit Warnung; Bohrung durch die kaputte Schale hält mit Kennung, Grund und Handlungen.

<a id="rm-383"></a>

- [ ] **RM-383 — Über 256 Schalen hält jede Boolesche, auch an getrennten Teilen.**
  Review 02.10.2026 der Commits bis `3fd3b1ace`, Fund 4. `app/core/geom/repair.py:1364` wirft bei
  mehr als `CROSSING_PARTS_MAX` (256) Teilen sofort `GeometryError` mit dem Rat „vereinigen Sie sie
  in Ihrem CAD- oder Netzprogramm“, ohne `object_id`.
  **Fehlerfall:** 300 getrennte Würfel: `drill_hole`, `subtract_objects` und `union_objects`
  halten; vor `eab5f4f47` richtig gerechnet; 200 Würfel rechnen weiter.
  **Fix:** Die Teilezahl allein ist kein Grund zu halten — die Vorfrage über den räumlichen Index
  (RM-381) auch für viele Teile; wo sie wirklich nicht reicht, Halt mit Kennung und einem Rat, der
  zum Fall passt.
  **Abnahme:** Test 300 getrennte Würfel: Bohren durch einen Würfel rechnet, Volumen stimmt.
  Bauplan §2.7, Regel 17. Beleg: Sonde `r_vielteile_bohren.txt`.

<a id="rm-385"></a>

- [ ] **RM-385 — Reste aus dem Review von `eab5f4f47` und `a45730c79`.**
  Review 02.10.2026 der Commits bis `3fd3b1ace`, Funde 7–11.
  - **Exakte Boolesche ohne konkreten Rat:** `app/core/brep/edit.py:1386` hat ihren konkreten Rat
    verloren; `tests/test_brep.py:1385` vergleicht nur noch die Konstante.
  - **`boolean.parts_united` nur am Netz:** Der exakte Kern vereinigt still (Kerne sagen
    Verschiedenes, `operationen.md`).
  - **Tests:** `tests/test_geometry_review_regressions.py:607` sichert etwas zu, das nicht mehr
    eintreten kann; drei neue Tests prüfen Aufrufargumente statt Wirkung (siehe Bericht).
  - **Unterlagen:** RM-253, RM-319 und RM-298 sind veraltet; der neue Halt steht weder in
    `.claude/rules/operationen.md` noch in §17.2; „vorübergehend“ in den Karten stimmt nicht; die
    Karte `app/core/geom/CLAUDE.md` trägt Implementierungsdetails, die in den Docstring gehören;
    in `app/ui/CLAUDE.md` (`3739d46af`) zwei schiefe Formulierungen (Wahldialoge, „in einer
    Transaktion“).
  **Abnahme:** je Rest ein Test bzw. die berichtigte Unterlage; `tests/test_directory_docs.py`
  grün. Beleg: `F:\solidon-review-reports\review-3fd3b1ace.md`.
  Review 02.10. (`7f0de659d`): Wiederholt sich — `ROADMAP.md` sagt im integrierenden Commit selbst „Zentrales Tor und Integration stehen aus“; der neue Absatz in `app/core/geom/CLAUDE.md` trägt wieder Implementierungsdetails. Dazu `ROADMAP-ARCHIV.md:34158–34160` (aus `0eccbe952`): ein „weiterhin“ offener Solverfehler bei Weltverschiebung 1e7 ohne Registerpunkt; ein Nachbau rechnet richtig (`sonden\r2_boolean_weltversatz.txt`) — Fall benennen und registrieren oder die Aussage streichen.

<a id="rm-402"></a>

- [~] **RM-402 — Kreismuster um einen gewählten Körper statt um den Weltursprung.**
  Umfangsentscheidung Robert 02.10.2026 („Alle“, Nachbau-Vorschlag Nr. 7).
  Das Kreismuster (`pattern`, `app/core/scene/ops.py:245`; am Merkmal `pattern_feature`,
  `app/core/geom/prepare_ops.py:4542`) dreht immer um den Weltursprung; die Laschen am Deckel
  trafen im Nachbau nur, weil der Deckel dort stand (`nachbau\sonden\v1_kreismuster_klemme.txt`).
  **Ablauf:** Feld *Drehmitte*: *Körper ‹…›* (Vorgabe: der gewählte bzw. einzige Körper),
  *Merkmal ‹…›* (z. B. Bohrungsachse) oder *Ursprung*; gespeichert wird die aufgelöste Mitte
  reproduzierbar (Regel 2), alte Projekte behalten den Ursprung.
  **Abnahme:** Test: Körper versetzt, Kreismuster mit *Drehmitte Körper* → Kopien um dessen Achse;
  altes Projekt unverändert. Bauplan §2.4, Regel 2.
  **Vorgabe Robert 02.10.2026 — allgemein, nicht für ein Modell:** Drehmitte für alle Muster (Kreis an Körper und Merkmal, Spiegeln) aus Körper, Merkmal oder Punkt, überall dieselbe Auswahl. Nutzen: in `F:\3D Dateien` nach Dateinamen rund 15 Teile mit Lochkreisen oder Rundmustern (Deckel mit Streulöchern, Filterball, Sieb, Düsen, Wabenhalter). Abnahme an mindestens drei unterschiedlichen Fällen.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `pattern`, `pattern_feature` und
  `mirror_object` tragen `cx`, `cy` und `cz`: drei leere Felder speichern die Körpermitte einmal als
  Antwort, drei Zahlen bleiben fest, Teilangaben werden mit Vorschlag abgelehnt;
  `follow_anchor=True` erhält alte Spiegel. Die Migration 43→44 setzt alte Kreise auf den Ursprung.
  Analytisch: Platte 60 × 40 × 10, Bohrung bei (65, 20), nach 180° um die Körpermitte bei (35, 20).
  448 Kernfälle, 12 Lebensläufe beider Kerne und Güten; der Dialog hat den Drehmittenwähler (14, 10
  und 6 Fälle, sechs Sprachen), dabei behoben: halbe Anzeigestellen wie 9,125 mm rundeten beim
  Wiederöffnen. Belege unter `F:\solidon-review-reports\codex-2026-10-03\`:
  `geometrie\druckvorbereitung\bericht.md` (RM-402), `bedienung\import-history-move.md`.

<a id="rm-405"></a>

- [~] **RM-405 — Die volle Schichtanalyse reißt §31 um Faktor 35–60; drei belegte Ursachen.**
  Review 02.10.2026, Modelltest über `F:\3D Dateien` (367 Dateien, 151 von 327 über §31), am HEAD
  `4449e3370`. Ziel §31: 0,3 s. Verwandt: RM-201 (Breitensuche, Säulen).
  - **a) Brückenspannweite:** `_bridge_width` → `_supported_span` → `_cuts_along`
    (`app/core/slice/analysis.py:2091–2249`): je Deckenschicht 500–700 Richtungen, rund 1 000
    Aufrufe mit Python-Schleife je Abtastlage. Screen-Cover `full` 10,5–10,7 s gegen `support`
    0,02 s; CC2-Box 14,9 s gegen 0,1 s; nur 4 bzw. 7 Schichten tragen die Zeit. Vektorisierte
    Fassung von `_cuts_along` bitgleich: 10,8 → 4,4 s und 15,1 → 7,8 s. Gröbere Richtungsbündel
    verfälschen die Spannweite um bis zu 49 % — nicht nehmen.
  - **b) Säulenkontur über Hohlräumen:** `_support_volume` → `_above_material`
    (`analysis.py:601–645`) — die Kontur wächst auf 497 238 Punkte, weil sie nach den Differenzen
    nie vereinfacht wird (dieselbe Bauart `analysis.py:2991`, `app/core/slice/findings.py:257`).
    Vereinfachen nach der Differenz: 18,2 → 0,46 s, Stützraum auf sechs Nachkommastellen gleich
    (`aushoehlen-und-teilen.p3d`).
  - **c) Doppelte Messung in der Anwendung:** Die Schichtansicht (`app/ui/main_window.py:1577`) misst
    ein zweites Mal, ohne den Merker zu fragen; die Kanalfrage von `overhang_findings`
    (`findings.py:305`) wird nicht gemerkt — ein zweiter `print_findings`-Aufruf kostet noch 8,2 s.
  **Fix:** a) `_cuts_along` in Feldern; b) Kontur nach jeder Differenz vereinfachen (Toleranz aus
  `units`, Regel 7); c) Schichtansicht und Kanalfrage über den Merker.
  **Abnahme:** Messung an Screen-Cover, CC2-Box und `aushoehlen-und-teilen.p3d` (Affinität F0FF,
  zweimal): Ergebnisse bitgleich bzw. Stützraum gleich, Zeiten mindestens um die gemessenen Faktoren
  besser; zweiter `print_findings`-Aufruf aus dem Merker. Bauplan §31, §22.
  Belege: `F:\solidon-review-reports\modelle\diagnose.md` (Befund 1), Sonden `d1_*`.
  Ergänzung Bibliotheksprüfung 02.10.2026: Für a ist `_cuts_along` als Cython-Schleife neben `_chain.pyx` 3,4–3,9-mal schneller als die vektorisierte NumPy-Fassung und bitgleich (Screen-Cover 1,8 s statt 6,7 s, CC2-Box 5,7 statt 19,8 s). Den Fix für b ersetzt RM-486 (Clipper2, 0,06 s ohne Toleranz). Beleg `bibliotheken\befunde.md`.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `cuts_along` besucht je Kante nur
  die gekreuzten Abtastlagen, Formeln und Reihenfolge bleiben, alte Kerne fallen auf NumPy zurück.
  Vergleich mit Affinität F0FF, je zweimal: Screen-Cover 0,72/0,87 gegen 3,84/3,40 s, CC2-Box
  5,07/5,48 gegen 40,74/41,47 s, Aushöhlbeispiel 0,89/0,77 gegen 0,76/1,40 s, jedes `SliceResult`
  bitgleich. Die Kanalfrage im Prüfbericht nutzt den begrenzten Merker; zweimal `print_findings`
  rechnet einmal (Screen-Cover kalt 3,08 s, warm 0,003 s). `_SliceWorker` ruft `findings.analysed`
  mit den wirksamen Einstellungen, Cacheschlüssel und Abbruch (32 Fälle). Der Hauptklon braucht
  einen Neubau von `_chain`. Belege unter `F:\solidon-review-reports\codex-2026-10-03\`:
  `geometrie\druckvorbereitung\bericht.md` (RM-405), `bedienung\construction-ui.md`.

<a id="rm-410"></a>

- [~] **RM-410 — Die schnelle Orientierung rechnet am vollen Netz und ist an großen Baugruppen langsamer als die gründliche.**
  Review 02.10.2026, Modelltest, am HEAD `4449e3370`.
  **Fehlerfall:** `chufang.3mf`: schnell 37,8–38,7 s gegen gründlich 29,5–29,6 s (warm, F0FF).
  `ranked_orientations`/`evaluate_directions` rechnen am vollen Netz
  (`app/core/geom/orient.py:272`, `:403`); die gründliche Suche nimmt das Ersatznetz und teilt
  gleiche Körper (`app/core/geom/prepare_ops.py:17427`). Kein einzelner Körper überschreitet 20 s.
  **Fix:** Die schnelle Suche nutzt dasselbe Ersatznetz und dieselbe Teilung gleicher Körper.
  **Abnahme:** Messung an `chufang.3mf` und zwei weiteren Baugruppen: schnell nicht langsamer als
  gründlich, Ergebnisse gleich. Bauplan §31. Beleg: `modelle\diagnose.md` (Befund 6).

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Die Rangfolge bleibt am
  Originalnetz; die Bauraumpassung wird erst am tatsächlich betrachteten Kandidaten gerechnet,
  gleiche Formen und Überhanggrenzen teilen ihre Suche, jeder Körper bekommt seine eigene Bewegung,
  Fortschritt und Abbruch gelten zwischen allen Körpern. Ein Ersatznetz ist verworfen, weil 14 von
  32 Gewinnern an chufang wechselten. Zwei warme Läufe: chufang (32 Körper, 5,6 Mio. Dreiecke) 161,3
  → 68,0/64,7 s, gründlich 149,8 s; ma-mi-ya 1,20 → 0,78/0,85 gegen 4,31/2,95 s; Greasetool 2,18 →
  0,87/0,91 gegen 2,59/2,56 s. Alle Ausgabegeometrien gleich der bisherigen schnellen Suche. Beleg:
  `F:\solidon-review-reports\codex-2026-10-03\geometrie\druckvorbereitung\bericht.md` (RM-410).

<a id="rm-413"></a>

- [ ] **RM-413 — Reste aus dem Review von `57848fa72` und `e3dff1907`.**
  Review 02.10.2026, Funde F7–F11.
  - **Toter Code:** `repair.has_nested_parts` (`app/core/geom/repair.py:1270–1286`) hat keinen
    Aufrufer, obwohl Karte, Bericht und zwei Tests ihn als Teil der Freigabe führen; in `_closed_at`
    (`prepare_ops.py:2227–2238`) wird ein Werkzeug gebaut und immer überschrieben.
  - **Abgelöster Merkmalarbeiter verwirft seine fertige Antwort** (`app/ui/main_window.py:15366–15368`);
    Docstring von `_answers_arrived` (`:15380–15383`) und `tests/test_ui.py:336` sagen das Gegenteil.
  - **Doppelter Builder:** `app/core/brep/edit.py:3203–3216` baut die Rundung ein zweites Mal statt
    über `_build_constant_fillet`; die Gegenprobe „Achsprüfung immer wahr“ in
    `_same_cylinder_axis` lässt alle 57 Fälle grün; Docstring von `fillet_group` (`:810–816`) nennt
    die Reihenfolge falsch.
  - **Falscher Absagegrund:** Berühren sich zwei andere Teile der Baugruppe, sagt der Langlochzug am
    freien Stift „sie ist eine Wand, keine Bohrung …“ — Grund falsch, Weg fehlt
    (`sonden\r3_kontakt_anderswo.txt`).
  - **Regel:** `.claude/rules/operationen.md` ist für drei Entscheidungen der Commits nicht
    nachgezogen; das Verhalten steht stattdessen in den Karten.
  **Abnahme:** je Rest ein Test bzw. die berichtigte Unterlage (Gegenprobe `_same_cylinder_axis`
  rot). Beleg: `F:\solidon-review-reports\review-e3dff1907.md`.

<a id="rm-434"></a>

- [~] **RM-434 — Das Entwurfsbudget von Weich verschmelzen übergeht die Eingangsprüfung.**
  Nachgang zu RM-379, Befund B02 des Reviews am festen Stand `48106c57a`.
  Zunächst lokal als RM424 vorbereitet; nach dem zentralen Nummernabgleich
  RM434, weil RM424 auf `origin/main` bereits den Orca-/Prusa-Bettursprung führt.
  **Fehler:** Der registrierte `blend_union`-Aufruf liest im Entwurf über
  `draft_grid`/`_grid` die Bounds, bevor die bisherige Volumen-/Dichtheitsprüfung
  in `blend_bodies` greift. Ein leeres Eingangsnetz führt zu `TypeError` ohne
  Handlung; derselbe Eingang in `fine` zu `NotManifoldError` mit Reparaturweg.
  Ein häufiger nativer Kundenweg mit einem leeren Szenenobjekt ist damit nicht belegt.
  **Fix:** Die bestehende Eingangsprüfung gemeinsam vor Bounds und Budgetentscheidung
  ausführen; keine zweite Validierungsregel. Gültige Rasterentscheidungen erhalten.
  **Abnahme:** Tatsächliche registrierte Op, leeres erstes/zweites/beide Netze,
  offene und volumenlose Eingänge in beiden Güten: fachliche Absage mit Handlung,
  kein Abstandsfeld. Gesunde Gegenfälle unter und über dem Entwurfsbudget unverändert.
  Bauplan §31, Regel 17.
  **Umgesetzt und fachlich freigegeben 02.10.:** Drei tatsächliche leere
  Entwurfseingänge rot, nach dem Fix alle 18 neuen Fälle und der überlappende
  Nachgang mit sechs Bestandsfällen grün. Dieselbe bestehende Prüfung steht
  jetzt vor `_grid`-Bounds und Budget; Cacheversion `blend_union` 4.
  Ruff/Format/Diffprüfung grün. Der gezielte Mypy-Nachlauf ist nach der Korrektur
  der fremden Handover-Stelle grün. Vollständiges Tor und Hauptzweigübernahme offen.
  [Aktueller Fachnachweis](konzepte/nachweise-release-0.5.1/reports/rm434-blend-inputs-2026-10-02.md).
  [Historischer Review mit Eingaben und Abnahmegrenzen](konzepte/nachweise-release-0.5.1/reports/remote-48106-geometrie.md),
  [Messdaten B02](konzepte/nachweise-release-0.5.1/reports/remote-48106-geometrie-proben.json).

<a id="rm-425"></a>

- [ ] **RM-425 — Überlappende gespiegelte Formzüge verlieren ihre Symmetrie.**
  Nachgang zu RM-378, Befund S01 des Reviews am festen Stand `48106c57a`.
  `_strongest_copy` wählt bei gleichen Gewichten die zuerst zugeordnete Kopie.
  Bei schräger Strichrichtung gewinnt dadurch auch auf der Spiegelebene eine
  Seite, statt dass sich die entgegengesetzten Richtungsanteile aufheben.
  **Historischer Nachweis:** Kugel R20, 1280 Dreiecke, wirklicher `stroke_at`-Zug
  mit Radius 16 mm und Stärke 1 mm, anschließend registriertes `sculpt_strokes`:
  Spiegelabweichung 0,341167593 mm, Ebenenaustritt 0,170583797 mm. Kein Hinweis auf
  ein zu grobes Netz; die alte Semantik sowie `front_only` ohne den neuen Selektor
  bleiben symmetrisch. Die Werte sind kein Nachlauf am späteren Hauptzweig.
  **Fix:** Überlappende Wirkungen unter Erhalt der gespiegelten Richtungen auf
  die vorgesehene Stärke begrenzen; die Reihenfolge darf keine Seite bevorzugen.
  **Abnahme:** Frischer Rot-/Grünfall mit schrägem Zug neben der Ebene; alle
  Achsen und Pinsel an mindestens drei Körpern, verschobene Spiegelmitte,
  Vorschau und echte Op, Cache/Undo/Redo. Gespeicherte alte Züge behalten ihre
  bisherige Semantik. Bauplan §25, Regel 2; Fensterabnahme beim Release.
  [Historischer Review](konzepte/nachweise-release-0.5.1/reports/remote-48106-geometrie.md),
  [maßgeblicher Radius-16-Nachlauf](konzepte/nachweise-release-0.5.1/reports/remote-48106-spiegel-probe.json).

<a id="rm-419"></a>

- [ ] **RM-419 — Die neue Durchstichprüfung macht den Formschritt bis 130-mal langsamer.**
  Review 02.10.2026 am Stand `4cf460e87`; Folgepunkt zu RM-364 (archiviert). Die Befunde
  `pierced` und `thin_wall` kommen jetzt richtig (auch an Zwillingen).
  **Fehlerfall:** `crossing_face_pairs` läuft über den Hüllquader aller bewegten Punkte
  (`app/core/geom/sculpt.py:768`, `:836`) ohne Fortschritt. Kugel 328 k Dreiecke, sechs Züge R 5:
  0,22 → 28,7–31,8 s; ein Zug R 25: 0,3 → 9–10 s; Korpusfigur 268 k Dreiecke: 0,23 → 2,66 s. Jede
  Auswertung des Formschritts zahlt es (§31).
  **Weitere Reste:** Als Handlung gibt es nur *Stelle zeigen* (*Zug zurücknehmen* fehlt); die
  Exportprüfung meldet den Durchstich weiterhin nicht.
  **Fix:** Paare nur zwischen bewegten Dreiecken und ihrer Umgebung prüfen (je Zug, nicht über den
  Gesamthüllquader), Ergebnis merken, `ctx.progress`; Handlung *Zug zurücknehmen*; Durchstich auch
  in der Exportprüfung.
  **Abnahme:** Messung an Kugel (sechs Züge R 5) und der Korpusfigur: höchstens 25 % über dem Stand
  vor `cd4875450`; Befunde unverändert. Bauplan §31, §17.3, §2.7.
  Belege: `F:\solidon-review-reports\verif-4cf460e87-geometrie.md`, Sonden `v4g_rm364_*`.

<a id="rm-428"></a>

- [ ] **RM-428 — Spiegelzug nahe der Ebene: Kerbe, verlorene Spiegelgleichheit, doppelte Laufzeit.**
  Review 02.10.2026 am Stand `70e9b3145`; Folgepunkt zu RM-378 (archiviert). Ein Zug genau auf der
  Ebene wirkt jetzt wie der Einzelzug (5 Körper × 3 Achsen × 6 Pinsel).
  - **Kerbe:** Ein Einzelzug 1 mm neben der Ebene hinterlässt eine 0,148 mm tiefe Kerbe mit Knick
    (Steigung ±0,263), ein gezogener Strich mit bis zu 2 mm Versatz 0,093 mm. Ursache:
    `_strongest_copy` nimmt das Maximum der Kopien (`app/core/geom/sculpt.py:265–290`); verlangt war
    eine zur Ebene hin ausgeblendete, glatte Gewichtung.
  - **Spiegelgleichheit verloren:** Ecken genau auf der Ebene wandern zur Seite des Originalzugs
    (Kneifen 0,426 mm, Auftragen 0,043 mm, vorher 0) — bei gleichem Gewicht gewinnt immer Kopie 0
    (`sculpt.py:279`).
  - **Laufzeit im Qt-Hauptthread:** Der Formeditor rechnet je Klick alle Züge neu (`_on_sculpt` →
    `apply_strokes`, `app/ui/main_window.py:11544`); am §31-Netz mit 1000 Zügen Symmetrie X 0,277 →
    0,509 s, xyz 0,836 → 2,176 s (verbindet sich mit RM-366).
  - **Tests:** Der neue Test fährt nur Auftragen; „weit weg doppelt“ fehlt darin.
  **Abnahme:** Zug 1 mm und 2 mm neben der Ebene ohne Kerbe (Profil stetig); Ecken auf der Ebene
  bleiben auf der Ebene; Laufzeit nicht über dem Stand vor `a3213c72c` + 25 %; Tests für alle Pinsel.
  Belege: `verif-70e9b3145-geometrie.md`, Sonden `v5g_rm378_*`.

<a id="rm-454"></a>

- [ ] **RM-454 — Ein Spiegelzug kann die verformte Fläche erreichen und trotzdem wirkungslos bleiben.**
  Quellenreview der parallelen Claude-Lieferung `105b2ba0d` am Stand
  `18c76d96b`: Die neue zweite Trefferprüfung in `sculpt._surface_for`
  berücksichtigt nur den Originalpunkt, die Auswertung dagegen auch
  Spiegelpunkte. Erreicht ausschließlich eine Spiegelkopie einen bereits
  verschobenen Eckpunkt, kann die erforderliche neue Etappe entfallen.
  Der genaue asymmetrische Prismengegenfall und die Korrekturrichtung stehen
  in `konzepte/nachweise-release-0.5.1/reports/remote-18c76-sculpt.md`.
  **Offen:** Gegenfall ausführen, Etappenentscheidung und Auswertung an
  dieselben Spiegelorte binden und den tatsächlichen Zug nachprüfen.
  Dies ist ein quellenbelegter, noch nicht ausgeführter Gegenfall; die
  Archivierung von RM-442 belegt seine Freigabe nicht. Keine neue Umsetzung
  im begrenzten Codex-Abschluss; als Folgeprüfung für Claude dokumentiert.
  Review 02.10.: bestätigt über die Oberfläche — mit X-Symmetrie wirkt ein Zug nicht, wenn nur seine Spiegelkopie die eben verformte Fläche greift, der Bericht nennt ihn verfehlt (gleich wie in v0.5.1). Beleg Fall C in `F:\solidon-review-reports\sonden\v8k_rm442_ui.py`.

<a id="rm-496"></a>

- [ ] **RM-496 — Reale Modelle laden im Prüfstand fast doppelt so lang wie in v0.5.1 — am echten Fenster nachmessen.**
  Versionsvergleich 0.5.2 (02.10.2026), Weg 1, unter Vorbehalt. Laden bis Ruhe: Rucksack-Halter
  2,9–3,3 s (v0.5.1) → 5,3–6,1 s, pegboard-STEP ähnlich. Im Profil sind 2,2 s davon nachgeholte
  Importe von trimesh/networkx und 1,4 s Merkmalserkennung. Der Prüfstand läuft ohne das
  Vorwärmen beim Programmstart; ob der Kunde die Importzeit sieht, ist offen.
  **Stellen:** Ladeweg `app/core/ingest/`, Vorwärmen in `app/ui/app.py`; Profil
  `weg1\sonden\ladeprof.py`.
  **Fix (allgemein):** am echten Fenster über den Startweg messen; sieht der Kunde die Importe,
  gehören sie ins Vorwärmen, und die Erkennung darf das Bild nicht aufhalten (vgl. RM-492).
  **Abnahme:** drei reale Modelle (Rucksack-Halter, pegboard-STEP, ein drittes) am echten Fenster
  nicht langsamer als v0.5.1. Bauplan §31.
  Belege: `F:\solidon-review-reports\regression-0.5.2\weg1\befunde.md` (W1-5), Rohwerte in `weg1\ergebnisse\`.

## Bedienung und Darstellung

<a id="rm-283"></a>

- [~] **RM-283 — Ein Handbuch, das man ohne Ausprobieren versteht.** Ein
  Interessent schrieb am 27.09.2026, aus dem Handbuch sei alles schwer zu
  lernen und Ausprobieren führe nicht zum Ziel; Robert beauftragte ein Handbuch,
  das an Bildern der echten Oberfläche erklärt, zu jeder Version aktuell ist und
  nur dann erzeugt wird. Konzept, Befund und Pakete HB-0 bis HB-13:
  [`konzepte/konzept-handbuch-2026-09.md`](konzepte/konzept-handbuch-2026-09.md),
  §0 sagt, wie man weitermacht. **Mit 0.5.1 veröffentlicht:** fünfteilige
  Gliederung mit „Wo fange ich an?“, fünfzehn Bildanleitungen in sechs Sprachen,
  Suche mit Rangfolge (38 von 38 Kundensuchen unter den ersten drei, vorher 25),
  F1 im Zusammenhang, der Ort je Operation in der Referenz und zwei
  Anleitungsfilme je Sprache. Beim Release laufen `make_guides.py`,
  `make_manual.py` und `make_guide_video.py` (`/erzeugen`). Der Weg dorthin steht
  im [Archiv](ROADMAP-ARCHIV.md#handbuch-bis-051-der-weg-von-rm-283-29092026).
  **Offen nach 0.5.1:** die Feldabnahme aus §11 (ein Kunde ohne CAD geht
  *Das erste eigene Teil* ohne Hilfe durch) und die Nummernplatzierung der
  Bildanleitungen, die in *Ein Gehäuse mit Deckel* 3 und *Ein Teil
  beschriften* 3 auf Text im Auswahlfenster liegt; `tools/make_guides.py`
  wählt den Platz nach der Unruhe im Bild und kennt die Textflächen der
  Oberfläche nicht, und wo ringsum alles unruhig ist, landet die Nummer auf
  Text.
  **Abnahme:** §11 des Konzepts.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `tools/make_guides.py` sperrt für
  Nummernscheiben die sichtbaren Textträger und Listen im Fenster, in Menüs und Dialogen; ist ein
  Dialog voll belegt, steht die Nummer im zusätzlichen Bildrand mit Verbindung zum Ziel. Tests:
  dichter Dialog, acht Nummern ohne Überschneidung, echte Rechtecke aus Dialog und Listen (Lauf mit
  222 grünen Fällen). Folgefund am Fenster: Die Weg-1-Tour blieb nach Neu → Modell öffnen stehen;
  der echte Projektwechsel beendet sie jetzt (12 Fälle). Die Bildfingerprints von
  `housing-with-lid`, `split-a-large-part` und `repair-a-model` werden beim Release neu erzeugt, von
  Hand ist keiner geändert. Belege unter `F:\solidon-review-reports\codex-2026-10-03\bedienung\`:
  `import-history-move.md` (RM-283/299), `construction-ui.md`.

<a id="rm-197"></a>

- [~] **RM-197 — Maßeditor im Bild: kein Bezugswechsel am Etikett,
  Beschriftungen mit Abstand zum Modell.** Robert, 21.09.2026, nach dem Klick
  auf eine Bohrung an Weg 1 mit dem Maßeditor aus P0.3/P0.4 (RM-188): „das
  wollte ich übersichtlicher, also das mit bezug ändern hintendran brauche ich
  garnicht, außerdem wollte ich von den ganzen anzeigen einen weiteren abstand
  zum modell und linien haben, damit es nicht stört und ich auch weiß wo etwas
  hingeht."

  Zwei Entscheidungen daraus:

  1. **Das Auswahlfeld *Bezug ändern* hinter jeder Maßbeschriftung fällt
     weg.** Der Bezugswechsel aus P0.4 bleibt über den Modellklick erreichbar;
     ein Feld je Etikett verdoppelt die Breite jeder Beschriftung und steht
     im Bild, wo das Modell steht.
  2. **Die Beschriftungen rücken vom Modell und von den Maßlinien ab** und
     zeigen eindeutig, zu welcher Linie und Kante sie gehören — Abstand zum
     Körper und eine erkennbare Zuordnung, keine Etiketten quer über der
     Platte und übereinander (am 21.09. lagen *Außenkante 2* und *Mitte 2*
     auf der Kante und aufeinander, *Bohrung 4 – Abstand* auf der Platte).

  **Umgesetzt in `ebba075e`** (21.09.2026): Das Auswahlfeld ist weg, der
  Bezugswechsel hängt als Kontextmenü am Maß (Rechtsklick oder Menütaste,
  `PlacementFlow._reference_menu`), und die projizierte Hülle des Trägers
  zählt beim Verteilen der Felder als belegt (`_body_on_screen`) — die
  Felder rücken daneben, die Verbindungslinie bleibt. Entwicklungstor im
  Arbeitsbaum am HEAD mit nur diesen Dateien grün (13.421 bestanden, 48
  übersprungen, Ruff, Format und mypy je 0); `test_surface_placement_ui`
  und `test_placement_dimensions` grün, der neue Test wird ohne die
  Körpersperre rot.

  **Und `ebba075e` riss an Weg 1 beim Wählen einer Bohrung** — nicht die
  Commits der CAD-Sitzung, wie zuerst gemeldet: Die Felder neben dem Körper
  machen die Verbindungslinien lang, die Fenstermaske der Maßfläche bekommt
  1682 Rechtecke, und der Vulkan-Treiber verliert das Gerät (RM-198, dort
  die Messung). Ein gerasterter Deckel darüber kostete graue Treppen an
  jeder schrägen Linie und je Bild vier Durchläufe über alle Rechtecke
  (Robert: „performancetechnisch auch ganz schlecht") und ist nicht
  eingecheckt. `ad3deadd` zieht die Maßtinte in den Renderer
  (`_Dimensions` ohne Widget und Maske) und führt die Verbindung zur
  **Mitte** der Maßlinie (Robert, 21.09.2026: „schöner wäre noch wenn die
  linien von den maßen zu den mittellinien jeweils gehen"); die Probe über
  den echten Startweg (Weg 1 laden, Bohrung über den Baum wählen) überlebt
  seither, vorher riss sie dreimal von drei.

  **Zwei Nachträge vom selben Nachmittag:** Die Zuordnungslinien kreuzen sich
  nicht mehr (Robert: „aufpassen dass sich die maßlinien nicht kreuzen") —
  `_untangle` tauscht paarweise die Plätze zweier Felder, solange das
  Kreuzungen spart und beide an den fremden Plätzen frei stehen. Und die
  **Langlochknöpfe stehen wieder am gewählten Loch** (Robert: „wo sind
  eigentlich die markierungen um es zum langloch zu ziehen?"): Seit dem
  Maßeditor sperrte die stille Platzierung den Merkmalsgriff und nahm die
  Knöpfe mit — am Stand `89a0de3a` fehlten sie genauso, geprüft mit zwei
  Bildern derselben Lage. Seit `bd310fa5` lässt `Viewport.set_gizmo` in diesen Lagen nur
  Pfeile, Ringe und Würfel weg (`only_knobs`); Flächenscheibe und Knöpfe
  bleiben, und `grip_placement` baut sie nach dem ersten Griff wieder auf.
  Dazu zeichnet der Langlochknopf während des Zugs nicht mehr selbst
  (RM-200).

  Abnahme: Weg 1 öffnen, eine Bohrung anklicken — kein *Bezug ändern* im
  Bild; jede Beschriftung steht frei neben dem Körper, ihre Verbindung endet
  in der Mitte der Maßlinie, Verbindungen kreuzen sich nicht, soweit ein
  Tausch es löst, und am
  Loch stehen die zwei Knöpfe zum Langloch; nach einem Zug zum Langloch
  bleiben Maße und Felder stehen und folgen der Kamera (Robert, 21.09.2026
  abends: „wenn wir das langloch ziehen und dann die ansicht drehen sind die
  maße weg" — der wartende Zug blendete die gebundene Maßgruppe beim nächsten
  Aufbau aus; `test_the_measures_stay_in_the_view_while_a_pulled_slot_waits`),
  und eine Maßlinie, die ganz in der Aussparung des Griffs läge, kommt ganz
  („manche maßlinien fehlen aber": Nach dem Zug greift der Griff über Knöpfe
  und Umriss hinaus, die 10 mm zur Außenkante lagen ganz darin;
  `test_a_dimension_line_swallowed_by_the_grip_is_drawn_whole`).
  **Review der fünf Commits am Abend des 21.09.2026** (elf Befunde, alle
  eingearbeitet): ein Stück Maßlinie kürzer als ein Pfeil zählt wie
  verschluckt (`LEAST_PIECE`, sonst ein Stummel ohne Pfeil bei anderem Zoom);
  die Kreuzungsprüfung kommt aus dem Kern (`profile.strictly_crossing`, der
  Zwilling in der Oberfläche rechnete ohne Toleranz); das Geräteverhältnis vom
  Renderer statt vom Widget, und `placement_flow.py` lädt seither
  `ansicht.md`; die Langlochknöpfe stehen bei gesperrtem Griff nur, wo der
  Aufrufer es sagt (`set_feature_gizmo_blocked(..., knobs=True)` — der
  Erkennungsdialog und die Ganzflächentextur sperren denselben Griff und
  bekamen sonst Knöpfe, deren Zug im Merkmalfenster endete); die Tinte liegt
  über `draw_order` unter Griff und Knöpfen, statt dass der Weltursprung
  entscheidet (Vertrag `SurfaceStyle.draw_order`, `add_lines(draw_order=)`,
  am echten Renderer gemessen: ohne Ordnung kippt die ferne Lage); je Aufbau
  drei `display_to_world`-Aufrufe statt 1760 (affin in fester Tiefe, am
  Renderer geprüft; vorher 15 ms je Radraste); der Anker der Verbindungslinie
  steht einmal in `pending`; der Rand der Marke kommt nach den Linien; ein
  toter Zweig in `set_gizmo`, das wirkungslose `area`, ein Test mit
  Selbstvergleich und zwei deutsche Bezeichner (`platz`, `unten`, seit dem
  09.09. in der Notlage der Platzsuche) sind weg; `gizmo_reach` kennt den
  Platzierungsgriff.

  **Review vom 21./22.09.2026 (Paket E), eingearbeitet:** Ein Bild mitten im
  Zug — Radraste, Vorschau, Overlay — nahm den Griff weg, und aus dem Zug
  wurde ein Kameraschwenk (`grip_placement` hält einen Griff mit `pressing`);
  eine Radraste über einem schwebenden Maßfeld zoomte nicht, sie verstellte
  das Maß und band den Entwurf (`wheel_needs_focus`); ein Druck zwischen die
  Knöpfe des gewählten Lochs zog ein Langloch statt den Baustein zu setzen;
  bei gewählter Bohrung fehlte der Tooltip, und der Merkmalstext der Auswahl
  verdrängte die Statuszeile; ein Zug am Bausteingriff verschob auch den
  stillen Bohrungsfluss; das erste Escape in der Bezugswahl nimmt nur den
  Pickmodus zurück, der Entwurf bleibt („Bezugswahl abgebrochen; der bisherige
  Bezug bleibt."); ein Abschlussklick vor der fertigen Vorschau wartet auf sie
  und übernimmt einmal (`preview_defer`). Die Fensterdateien der Ansicht
  liefen dabei grün (456 Fälle), jeder neue Test am Stand davor rot.

  **Der Halter, 22.09.2026** (`d3e7fc30`, `85f7f86b`, `5c315044`,
  `c93b918d`): Roberts Schraubendreherhalter mit Wabenmuster — 1 213
  Merkmale, und die Auswertung hängte nichts ein: `FEATURE_LIMIT_COUNT` steht
  seither bei fünftausend (gemessen: Zuordnung 5 000 Merkmale 0,9 s). Am
  Maßeditor: Versetzen mit „Senkung und Stufen mitnehmen" ist ein Schritt
  (`_moved_after_resizing`); der Grund des Kerns steht über der Vorschau
  statt „konnte nicht berechnet werden"; die Felder bleiben stehen
  (`_field_slots`); sie stehen an ihrer Maßlinie, sobald der Körper über das
  Bild ragt, und nie unter dem Vorschauband; das Maß mit dem Fokus leuchtet;
  und Übernehmen der Maßgruppe zieht das Langloch, wenn ein Zug wartet.
  **Review der vier Commits am selben Tag (zwei Prüfer, Kern und
  Oberfläche), eingearbeitet:** Der Doppelschritt bewegt um die Differenz zur
  alten Mitte (die schräge Mündung ließ die Kette 0,245 mm wandern), verlangt
  die ganze Kette, misst die Nachbarwand am neuen Ort und reicht die
  Übergänge des exakten Kerns durch — der Einlauf-Neuschnitt belegt sie
  jetzt selbst (`NativeReferenceLost` bei jedem späteren Bezug auf die
  Bohrung); die Rohrpaarung wählt ihre Kandidaten über einen Baum vor (halb
  Hohlraum, halb Materie bei 5 000: 22 s → 0,03 s); die Stehregel entscheidet
  je Feld (ein getroffener Platz löste alle, +1,2 mm am Setzpunkt sprangen
  zwei Felder 391 und 409 Punkte); gemieden werden fremde Maßlinien und
  Verbindungen, nicht Bezugskanten, und nur bis `STICKY_FIELDS` Feldhöhen
  weiter (208 und 336 Punkte vom Maß, um einen Strich nicht zu decken); ein
  Körper, der gerade so ins Bild passt, schickt die Felder nicht mehr in die
  Notreihe; die Langlochroute filtert ihre Werte auf die Parameter der
  Operation (`nx`/`ny`/`nz` ließen den Schritt am Kern scheitern), das
  Fenster beantwortet „meint Übernehmen das Langloch" an einer Stelle
  (`slot_drag_takes_the_accept`, mit der Durchmesserfrage des Kerns
  `bore_is_unchanged`), und bei neuem Durchmesser sagt die Statuszeile die
  Wahrheit — der Zug ist danach zu wiederholen, der Szenenaufbau verwirft
  ihn; das Tiefenfeld leuchtet mit; Portugiesisch sagt „furo oblongo" wie
  am Knopf — auch im Changelog. Zwei Nebenbefunde außerhalb der vier
  Commits, beide behoben: Nach dem Einlauf-Neuschnitt am exakten Körper
  fehlten die Flächen des Körpers im Baum (`_exact_rest_carried`), und eine
  ohne Einlauf versetzte Bohrung meldete die aufgerissene Nachbarwand nicht
  (`drill` gibt sein Werkzeug heraus; am Halter und am Bohrerhalter aus
  `F:\3D Dateien` nachgestellt — ein STEP mit Senkbohrung liegt dort nicht,
  der exakte Fall bleibt am gebauten Körper geprüft). Jeder neue Test am
  Stand davor rot. Offen: die Abnahme am
  echten Fenster beim nächsten Release (RM-213) — dazu die Stufe an der Grenze „ganz
  sichtbar" (ein Punkt über den Maßraum, und die Felder wechseln die Seite).
  **Zug und Durchmesser sind ein Schritt** (Entscheidung Robert am selben
  Tag: „Ja eine transaktion"): `slot_hole` nimmt die Breite selbst
  (`diameter`, `compensate`), die stille Platzierung baut daraus den einen
  Auftrag (`_slot_with_width`); zwei Schritte in einer Transaktion gingen
  nicht, weil das Langloch nach dem Zug neu heißt und der zweite Schritt
  seinen Namen erst nach der Auswertung kennte. Tests an beiden Kernen,
  breiter und schmaler, und im Fenster mit Strg+Z. Gehört zur laufenden
  Arbeit an P0.3/P0.4.

  **Langlochzug und Maßpanel nachgezogen, 24.09.2026:** Auch eingelesene
  Langlöcher öffnen ihre Längen-, Breiten- und Lagefelder im Bild. Beim Zug
  an einer Bohrung wechseln diese Felder gemeinsam zum Langloch; eingetragene
  Breite und Zielmitte bleiben erhalten. Eine noch offene Tiefenänderung
  bleibt beim Bohrungsentwurf und verlangt zuerst dessen Abschluss.
  Umriss, Schnittvorschau und Griff lesen dieselbe wirksame Breite;
  *Abbrechen* im Merkmalfenster stellt die Istwerte wieder her. Bestehende Langlöcher lassen
  sich an beiden Kernen verkürzen, auch mit neuer Breite und Richtung:
  Die Operation schließt die alte Öffnung vor dem neuen Schnitt. Die
  Mindestlänge bleibt an die neue Breite gebunden. Geometrie, Vorschau und
  Signalanschlüsse sind ohne Fenster geprüft; die ergänzten Fensterfälle
  für Auswahl, Übernahme und Undo gehören zur nächsten Release-Abnahme.

  **Gemeinsame Bedienwege im Code geprüft:** Berichtsklicks, direkte Einstiege
  in Skizze, Formen und Skelett, Trennen sowie lokale Erkennung respektieren denselben
  begonnenen Maßentwurf wie Menüoperationen. Dokument-Undo/Redo greift erst
  nach dessen Übernahme oder Abbruch; lokales Gesten-Undo behält Vorrang.
  Ein abgelehnter Drehring aktiviert keine fremde Panelhandlung mehr.
  Ungültige Außen- oder Mittenabstände zeigen den Grund an der sichtbaren
  Maßgruppe und sperren Übernehmen sofort; die Korrektur macht den Weg frei.
  Nach Roberts Vorgabe erfolgt dieser Nachweis über Code und fensterlose
  Zustandsregressionen; eine durchgängige native Bedienabnahme ist damit
  nicht behauptet.

  **Review des Langlochzugs, 24.09.2026** (Robert: „noch ein bisschen buggy
  vor allem mit dem merkmalpanel nebenan und dass man es nicht kleiner
  schieben kann, die maße fehlen auch beim langloch"). Ein Druck in das Ende
  eines Langlochs trifft das Langloch — die Zielhilfe rechnet gegen seinen
  Umriss (`bore_span` mit `travel`/`heading`, `_feature_inside` gegen die
  Mittellinie); vorher fiel er in der Draufsicht durch das Loch, und die
  linke Taste zog den Körper. Der Knopf wandert um den Weg der Hand
  (`SlotHandle._grab`); am Wedge-Lock drehte ein Griff neben der Knopfmitte
  das Langloch vor der ersten Bewegung um 16 Grad. **Unter der kürzesten
  Länge rastet der Zug auf die runde Bohrung** (Entscheidung Robert am selben
  Tag: „sollte es kurz einrasten"): `settled_length`, Kreis im Umriss,
  „Bohrung" am Zeiger; `slot_hole` mit Länge = Breite
  (`prepare.is_round_length`) schneidet an beiden Kernen wieder eine runde
  Bohrung (`slot_hole.round_again`), eine runde Bohrung auf ihre eigene
  Breite bleibt unangetastet (`slot_hole.already_round`), dazwischen nennt
  `NEITHER_ROUND_NOR_SLOT` beide Auswege. Übernehmen ist danach nicht mehr
  grau (`placement.prepare_tool`), und ein aus einem Schritt gezogenes
  Langloch, das auf genau seine Bohrung zurückrastet, nimmt den Schritt
  heraus, statt einen ohne Wirkung stehen zu lassen (`_commit_slot_change`).
  Ein Klick ins Zwillingsfeld rechts wechselt die Maßgruppe, statt sie zu
  schließen (`_hand_the_measures_over`), und der Zwilling zeigt nur, was er
  allein hat (`FeaturePanel._in_the_view`: an einer Bohrung Länge und
  Richtung, an einem Langloch Tiefe und Änderungsumfang). Eine gefaste
  Mündung findet ihre Trägerfläche (`seat_of`, `mouth_reach`, Korpus
  `plate_chamfered_mouths.stl`) — vorher hatte ein solches Loch keine Maße
  im Bild. *Abbrechen* in der Maßgruppe verwirft den Entwurf und hebt die
  Auswahl auf (Entscheidung Robert: „abbrechen = deselektieren"); vorher
  blieb das Merkmal ohne Maße und Knöpfe gewählt, und rechts stand die
  Handlung des verworfenen Entwurfs scharf. Ein Review derselben Nacht
  (20 Befunde) ist eingearbeitet: der linke Knopf dreht beim Einrasten nicht
  mehr um 180 Grad, was an einer runden Bohrung rund endet, schlägt nichts
  vor, eine eingetragene Zahl rastet nicht, der Netzkern meldet die
  Materialtoleranz wie der exakte, rund und breiter prüft die Nachbarwand wie
  *Bohrung ändern*, der exakte Kern misst „nichts abgetragen" am gefüllten
  Körper, der Schritt fällt nicht, wenn ein späterer sein Langloch nennt, Tab
  bleibt im Merkmalfenster, und `make_corpus.py` baut die neue Korpusdatei.
  Escape tut seit dem 25.09.2026 dasselbe wie *Abbrechen* (Robert: „wie
  abbrechen zurücknehmen und abwählen") — vorher blieb der verworfene
  Entwurf im Merkmalfenster scharf —, und beim Übernehmen liest die
  Maßgruppe nur die getippten Felder neu: Das Zurücklesen einer feineren
  Zahl, als das Feld zeigt, baute das Werkzeug neu, und der Klick verfiel
  still. Die Mündungskorrektur in `surface_values` gilt seit dem
  25.09.2026 nur der eigenen Fläche (G5): Der Fluss reicht die eigene
  Mündung mit — vom Sitz, oder nach einem Zielen von `placement.mouth_on` an
  der frisch vorbereiteten Fläche —, und eine fremde parallele Fläche im
  Radius setzt die Mündung auf sich, statt die Mitte in der Höhe zu halten.
  Im Fenster tritt der Fall nur auf, wo gezielt wird (im Dialog an einem
  Loch ohne Sitz); am gewählten Merkmal gehört ein Klick der Auswahl.
  Dabei gefunden: Wer in der Maßgruppe eine Koordinate tippte, verlor die
  Gruppe nach der zweiten Ziffer — die Mitte wanderte an der um Rauschen
  schiefen Achse mit dem Versatz in der Höhe (Schaber: 2,9 µm auf 43 mm),
  und `move_to` las das als getippte Tiefe. Gemessen wird seither an der
  Mündung; am Schaber hält die Gruppe über „-47,00“, und Enter übernimmt
  mit unveränderter Höhe. Am echten Fenster gefahren an `plate_coarse_slots`,
  `plate_holes` und aus `F:\3D Dateien` an Scraper und Wedge-Lock:
  Einrasten, Übernehmen, Rücknahme des Schritts, Zwillingsfelder in beiden
  Richtungen. Die neuen Tests ohne Fenster waren am Stand davor rot; die
  neuen Fenstertests (`test_slot_handle.py`, `test_feature_panel.py`) laufen
  mit der Release-Abnahme.
  Registerabgleich 02.10.: offen, nur am Fenster; „Release 0.5.0“ in der Registerzeile ist veraltet, der Rest „Stufe an der Grenze ganz sichtbar“ steht nur im Eintrag, nicht im Register.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Am Fenster reproduziert: Eine
  große Fachkarte drängte alle Abstandsmaße in eine Notreihe mit gekreuzten Linien. Jetzt darf nur
  die Fachkarte den Körper überdecken; Maße, Setzpunkt, Griff und andere Felder bleiben frei,
  `_untangle` prüft beim Tausch erneut. Folgefund: Der Platzierungsgriff saß an der Mitte des langen
  Bohrwerkzeugs, jetzt an der Mündung aus der Matrix. 64 Fälle in `test_placement_dimensions.py`,
  drei Grifffälle, unabhängige Durchsicht ohne Befund. Am Fenster nach Neustart (Weg 1, mittlere
  Bohrung): Karte über dem Modell, Maße verteilt, Zug am Griff um 6,44 mm, Strg+Z und Strg+Y. Belege
  unter `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `root-evidence.md` (RM-197),
  `root-independent-review.md`.

<a id="rm-198"></a>

- [~] **RM-198 — Eine feine Fenstermaske über der Vulkan-Fläche verliert das
  Gerät.** Gefunden am 21.09.2026 beim Nachstellen von RM-197: Beim Wählen
  einer Bohrung an Weg 1 riss die Anwendung mit „Error in wgpuQueueSubmit:
  Validation Error — Parent device is lost", ohne Validierungsfehler oder
  Verlustmeldung davor, auch mit wgpu-Protokoll auf Debug. Eingegrenzt über
  eine Probe auf dem echten Startweg (`main()`, Weg 1 als Datei, Bohrung
  über den Baum gewählt), je Schritt dreimal: Ohne die Fenstermaske der
  Maßfläche (`_Dimensions.setMask`) lebt der Prozess; mit derselben Maske
  unter D3D12 (`WGPU_BACKEND_TYPE=D3D12`) lebt er; unter Vulkan reißt er
  bei 1682 Rechtecken in der Maske und lebt bei 1380 und bei 415. Jede
  schräge Linie liefert ein Rechteck je Bildzeile — mit Feldern neben dem
  Körper sind die Verbindungslinien lang, und die Zahl kippt.

  **Behoben an der Wurzel:** Die Maßtinte zieht in den Renderer, wie die
  Merkmalslinien — `_Dimensions` ist kein Widget mehr und trägt keine Maske;
  Unterlage, Striche, Pfeile und Marken gehen über `add_lines` und
  `add_surface` mit `keep_in_front` ins Bild. Ein gerasterter Deckel über der
  Maske war zuerst gebaut und ist verworfen: graue Treppen an jeder schrägen
  Linie und je Bild vier Durchläufe über alle Rechtecke (Robert:
  „performancetechnisch auch ganz schlecht"). Die Probe über den echten
  Startweg überlebt seither (zweimal), das Bild ist sauber
  (`test_dimension_ink_lives_in_the_renderer_and_leaves_with_the_surface`).

  **Und die Tinte legte je Kamerageste zehn Renderer-Objekte neu an**
  (Review 21.09.2026, Paket E): Seither hält sie sieben Elemente mit fester
  Kapazität und tauscht nur die Punkte (`Item.update_points`,
  `GfxItem._refill`), liegt über `draw_order` vor dem Material statt über
  einen geweiteten Tiefenbereich, und `cameraMoved` kommt vor dem Bild — ein
  Radzoom zeichnet ein Bild statt zwei (22 → 7,7 ms je Aufbau).

  **Was bleibt:** Die Overlaykarten tragen Masken mit runden Ecken — wenige
  Rechtecke, nicht betroffen. Die Probe über den echten Startweg beim nächsten
  Release (RM-213) noch einmal fahren. Ob Windows D3D12 als Backend bekommt, wo es da
  ist (unter D3D12 gab es den Fall nie), ist eine eigene Entscheidung und
  kein Muss mehr.

  **Stand laut Register bis 29.09.2026:** Behoben an der Wurzel: Die Maßtinte liegt seit
  `ad3deadd` im Renderer, seit dem Review mit fester Kapazität (sieben Elemente, nur die Punkte
  wechseln) und unter `draw_order` vor dem Material; die Maske ist weg. Offen: die Probe über den
  echten Startweg beim nächsten Release noch einmal fahren, und ob Windows D3D12 als Backend
  bekommt, bleibt eine eigene Entscheidung

<a id="rm-199"></a>

- [~] **RM-199 — Der Durchmesser steht doppelt: im Bild und rechts im
  Auswahlfenster.** Robert, 21.09.2026, mit dem Maßeditor an Weg 1:
  „durchmesser ist ja im viewport kann im merkmalpanel/auswahlpanel entfernt
  werden". Die Maßgruppe im Bild trägt Durchmesser, Änderungsumfang, X, Y, Z
  und Materialtoleranz; rechts im Auswahlfenster stehen dieselben Felder als
  gesperrte Zwillinge (`FeaturePanel`, „Panelgegenstücke sind gesperrt"). Was
  im Bild steht, fällt rechts weg, solange die Maße im Bild stehen; kommt der
  Editor zu, kommen die Felder zurück. `panels.py` und `main_window.py` liegen
  bei der CAD-Sitzung (P0.3, RM-188) — dort eingelöst, in `b25167fd`: Das
  Merkmalfenster merkt sich je Handlung ihren Block aus Strich und Zeile
  (`FeaturePanel._blocks`); `set_measuring(True, op=…)` nimmt den Block der
  Handlung weg, deren Maße im Bild stehen, `set_measuring(False)` bringt ihn
  zurück, die übrigen Handlungen des Merkmals bleiben. Gemessen an Weg 1 mit
  `plate_holes.stl`: nach dem Wählen der Bohrung steht rechts kein Feld von
  *Bohrung ändern* mehr, *Merkmal verschieben* schon; nach
  `end_quiet_placement` stehen Durchmesser und Koordinaten wieder
  (`test_ui.py::test_the_measures_in_the_view_take_their_twins_out_of_the_panel`).
  Das Review vom 21.09.2026 fand den Rest: Der Block des historischen
  Bohrschritts (`offer_bore_step`) blieb neben der Maßgruppe stehen; er trägt
  sich seither in `_blocks` ein und weicht mit den übrigen. Abnahme, offen
  beim nächsten Release (RM-213): Bohrung an Weg 1 wählen, rechts kein Durchmesser, keine
  Koordinaten; endet die Maßgruppe, stehen sie wieder. Escape und Abbrechen
  wählen dabei seit dem 25.09.2026 ab (Entscheidung Robert), rechts steht
  danach nichts mehr.

  **Stand laut Register bis 29.09.2026:** Eingelöst in `b25167fd`, und im Review ganz: Auch der
  Block des historischen Bohrschritts weicht, solange die Maße im Bild stehen (`offer_bore_step`
  trägt `_blocks`). Abnahme beim nächsten Release: Bohrung an Weg 1 wählen, rechts kein
  Durchmesser, keine Koordinaten; endet die Maßgruppe, stehen sie wieder (Escape wählt seit dem
  25.09.2026 ab); auch für die nächste Bohrung und Escape offscreen belegt (`85dec7cb`)

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Am Fenster gefunden: Beim
  ursprünglichen Bohrschritt standen Ø 4,20 im Bild und der gemessene Ø 4,35 rechts zugleich als
  Eingabe. `FeaturePanel.set_measuring` verbirgt nun auch die beiden alternativen Maßhandlungen samt
  Feldern und bringt sie beim Ende zurück; Operationen und gespeicherte Werte bleiben unberührt.
  Beide Kerne, Test erst rot, dann sieben Fälle grün, unabhängige Durchsicht ohne Befund. Am Fenster
  nach Neustart: Durchmesser nur in der Maßkarte, Verschieben, Drehen und Verdoppeln bleiben rechts.
  Belege unter `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `root-evidence.md` (RM-199),
  `root-independent-review.md`.

<a id="rm-200"></a>

- [ ] **RM-200 — Ein Zug am Griff soll flüssig sein.** Robert, 21.09.2026:
  „das verschieben über gizmo ist auch noch nicht flüssig". Gemessen am
  21.09.2026 im echten Fenster an Weg 1 (`cProfile` im Prozess, echte Maus,
  je 118 Bewegungen): ein Zug am **Platzierungsgriff** kostet 13 ms je
  Bewegung, davon 12 ms das Bild (`_draw_with_occlusion`); ein Zug am
  **Langlochknopf** kostete 32 ms, weil Knopf und Merkmalsmarke je ein eigenes
  Bild anforderten — seit `bd310fa5` eines (21 ms). Was bleibt,
  ist der Durchgang mit Umgebungsverdeckung: 12 bis 17 ms je Bild bei 3163 ×
  1259 Bildpunkten, also 60 Bilder je Sekunde und nicht mehr.

  **Review vom 21./22.09.2026 (Paket E):** Ein Radzoom zeichnete zwei Bilder,
  weil die Maßtinte je Kamerageste neu entstand — jetzt eines (22 → 7,7 ms je
  Aufbau, `cameraMoved` vor dem Bild); der Bewegungsgriff der Platzierung
  bleibt über `Gizmo.fits` erhalten, statt je Kamerageste neu zu entstehen;
  `_on_pointer` meldet nur bei geändertem Zustand. Was der Prüfer außerdem
  maß und was noch nicht gefahren ist: die Umgebungsverdeckung im Zug auf
  4 × 2 zurücknehmen, wie sie unter einer Analysekarte schon weicht
  (`ansicht.md`). Offen: Roberts Geste nachstellen (welcher Griff, und ob das
  Loslassen hängt — der Werkzeugkörper wird danach im Arbeiter neu gebaut) und
  die Verdeckung im Zug aussetzen, gemessen am echten Renderer.

  **Stand laut Register bis 29.09.2026:** Roberts Geste nachgestellt und verlegt (`7ff34c67`: je
  Bewegung 13,6 → 8,8 ms, das Loslassen 89–134 → 25–57 ms, Griff und Maße nach dem Klick 9–21 s →
  1–2,4 s, leichte Verdeckung im Zug 4 × 2); offen ist allein, ob es sich am echten Fenster
  flüssig anfühlt (Release, RM-213)
  Registerabgleich 02.10.: teilweise erledigt (`7ff34c67`); Statuszeichen wäre `[~]`, „Offen: Geste nachstellen / Verdeckung aussetzen“ ist überholt; Rest nur am Fenster.

<a id="rm-204"></a>

- [ ] **RM-204 — Ein Merkmalklick baut alle Handlungen des Fensters neu.**
  Gemessen am 21.09.2026 im Review (Leistung A5): `_on_feature_selected` 47
  bis 60 ms und `_show_feature_fields` 42 bis 53 ms je Merkmalauswahl, weil
  `show_feature` das Fenster leert und alle Handlungen neu baut
  (`_build_action`, achtzehn Widgets, `request_in_view` synchron). Das Review
  nahm `findChildren` aus `_settle_lock` (13 ms je Wechsel); der Widget-Cache
  je Merkmalsart ist nicht gebaut, weil `_build_action` neun Closures an
  `action`, `fields`, `widgets` und `fixed` bindet, dazu Gruppen-Nachweise,
  `elsewhere`-Knöpfe, Katalogknopf und Schutzumschalter. Weg: `_Handling`
  mutabel mit `entries`, `widgets` und `fixed`, die Closures lesen aus dem
  Objekt, Wiederverwendung je (Operation, Feldnamen und -arten, Schritt oder
  nicht, Gruppengröße über eins), Werte über `refresh_feature_fields`.
  Abnahme: ein Merkmalklick unter 20 ms im Fenster, `test_feature_panel.py`
  und `test_ui.py` unverändert grün.

  **Stand laut Register bis 29.09.2026:** Gebaut (`85dec7cb`): Zeilen je Signatur wiederverwendet
  (`_ActionRow`, `configure_feature_field`), Kernauskunft je Merkmal und Auswertung gemerkt;
  `show_feature` 41 → 12 ms, Wiederklick 8 ms, Klick bis Ruhe 391 → 140 ms (offscreen). Offen:
  Abnahme am echten Fenster beim Release (RM-213)
  Registerabgleich 02.10.: teilweise erledigt (`_ActionRow`, `configure_feature_field`); Statuszeichen wäre `[~]`; Rest nur am Fenster.

<a id="rm-070"></a>

- [~] **RM-070 — SpaceMouse auf macOS und Linux am echten Gerät abnehmen.** HID-Anbindung und
  Kameraabbildung sind gebaut und von Robert mit SpaceMouse Compact gefahren; macOS nutzt inzwischen
  den 3Dconnexion-Treiber.

  **Der Mac ist gefahren** (Robert, 12.09.2026: „die spacemaus und update auf dem mac funktionieren
  jetzt problemlos"). Das ist ein Feldnachweis und kein Testlauf — er zählt für die Plattform, auf
  der er stattfand, und für nichts sonst.

  **Der Zoom hakte (Robert, 16.09.2026).** Am Korpus gemessen war die Ursache der harte
  Übersprech-Schnitt bei einem Viertel der stärksten Achse: Er schaltete die Zoomachse beim Ziehen
  zur Person dreimal in vier Sekunden an und aus, beim Kippen der Vorderkante sechsmal. Seit dem
  16.09. dämpft `quiet_crosstalk` als Rampe zwischen 15 % und 35 % der stärksten Achse, mit dem
  alten Viertel als Mitte; das Zoom-Leck beim Schieben bleibt unter einem Zehntel, beim Drehen
  bleiben zwei Drittel, und das ist der Sensor. Zum Vergleich: Blender und PrusaSlicer filtern
  Nebenachsen gar nicht, FreeCAD bietet den strengen Dominant-Modus nur als Option, 3Dconnexion
  empfiehlt Anwendungen den Treiberweg navlib mit eigenem Bewegungsmodell. Offen: die Rampe am
  Gerät fahren und die Bildzeit je Takt messen, denn jeder Takt setzt Kamera, Schnittebenen und
  ein synchrones Bild.

  Offen bleiben damit: **Linux** (Rechte und Gerätetest), das Verhalten bei paralleler
  3DxWare-Mausemulation und die Bildrate an einem Netz mit 1 Mio. Dreiecken. Abnahme je Plattform
  mit benanntem Gerät, Treiber und reproduzierbarer Navigation; eine automatische Änderung der
  Treiberkonfiguration vorher entscheiden.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#eine-kundenanfrage-aus-dem-dentalbereich-30082026).
  Registerabgleich 02.10.: offen, nur am Gerät; der Eintrag führt Bildrate und Bildzeit je Takt noch als offen, obwohl die Registerzeile die Messung (815 104 Dreiecke) schon meldet.

<a id="rm-183"></a>

- [ ] **RM-183 — Zeichenmodus am Fenster abnehmen.** Die
  [Durchsicht](konzepte/durchsicht-zeichenmodus-2026-09.md) vom 16.09. hat zehn Befunde. Acht
  sind am selben Tag gebaut: Gestensatz nur im Bild, vier Werkzeuggruppen mit Trennstrichen, der
  Bedingungshinweis geht nach dem ersten Sehen — und die fünf, die Robert delegiert hat („mach
  das beste für kunden daraus, weniger ist manchmal mehr"): *Fertig* klappt die sechs Arten
  direkt auf statt eines Zwischendialogs, die Zeile der Karte sagt nur, was sonst nirgends
  steht, der Rasterhaken „Auto" fällt, ein Zeichnen-Knopf je Skizzenfeld, keine Kürzel für die
  Lochbilder. **Offen ist die Abnahme am laufenden Fenster**, denn nichts davon wurde dort
  gefahren: Rohrbogen mit gezeichneter Bahn und Trichter mit gezeichnetem oberen Umriss (Z8),
  die Tastaturfolge durch die Karte, die drei Trennstriche im dunklen Thema — und aus dem selben
  Tag das Rollen im Merkmalfenster und die Rampe der 3D-Maus. Abnahme: je Fall ein gebauter
  Körper oder ein Satz von Robert, was hakt.

  **Stand laut Register bis 29.09.2026:** Führen mit gezeichneter Bahn und Überblenden mit
  gezeichnetem Umriss am Fenster gefahren (`f19a7b4b`, sechs Fehler behoben), Tabulatorfolge,
  Bildschirmleser und Trennstriche im dunklen Thema (2,30:1) gemessen; offen allein die Rampe der
  3D-Maus am echten Gerät — ob dieser Rest in RM-070 aufgeht (dasselbe Gerät) und der Punkt damit
  schließt, entscheidet Robert
  Registerabgleich 02.10.: teilweise erledigt; Statuszeichen wäre `[~]`, „nichts davon wurde dort gefahren“ ist überholt; Rest nur am Gerät (deckt sich mit RM-070).

<a id="rm-084"></a>

- [~] **RM-084 — Kundentexte gegen die vereinbarte Sprache prüfen.** Website, Handbuch und sichtbare
  Anwendungstexte systematisch auf Roberts persönlichen, natürlichen Ton prüfen und verbleibende
  Stellen überarbeiten. Abnahme: vollständige Liste der geprüften Bereiche, konkrete Textänderungen
  ohne Bedeutungsverlust und vollständige Sprachkataloge.

  **Stand 23.09.2026 (Paket „texte", `konzepte/nachweise-release-0.5.0/reports/texte.md`):** Preise, Generatoraussage, README-Version,
  Sicherheitstexte, Agentenquote, Slicer-Begriff es/fr/pt, Du/Lei-Bestand it, portugiesische
  Anführungszeichen und die in `sollliste*.md` benannten Einzelstellen (B13/B12, B11c, B32, B23, B26,
  B27, B34, B16, B3, C2/C9/C10/C12, A16 und Nachbarn) geprüft und korrigiert, alle fünf Kataloge
  nachgezogen. Keine erschöpfende Zeile-für-Zeile-Prüfung jedes Anwendungstexts — offen bleibt der
  Rest der Oberflächentexte außerhalb der benannten Fundstellen.

  **Durchsicht v0.5.1 (26.09.2026, texte):** Alles seit 0.5.0 gelesen — 154 neue
  Katalogschlüssel in sechs Sprachen, 41 neue Befundstellen, 56 Changelog-Punkte und die
  neuen Website-Texte; 20 Katalogtexte neu gefasst, Anrede es/it vereinheitlicht,
  Changelog-Punkte in Entwicklersprache umgeschrieben. Zwei Wächter halten den Stand über
  alle Kataloge: `test_wording::test_no_customer_text_uses_a_designer_word` (RM-088) und
  `test_wording::test_a_quoted_control_is_named_as_the_control_says` — von 51 abweichenden
  Knopfzitaten im Bestand 37 berichtigt, der Rest begründete Ausnahmen (`e8f9f574d`).
  Offen bleibt der Zeile-für-Zeile-Durchgang durch den Bestand vor 0.5.0 in Anwendung und
  Website.

  **Dazu, bisher nur im Register und in den Regeln:** aus der Sollliste der Durchsicht
  0.5.0 A16 (das Presseversprechen „STL wird exakter Körper, STEP heraus“ gegen den Stand
  von P4.0 halten), A23 (Leistungszahlen der Presse gegen eigene Messungen) und C12 (Namen
  der Slicer-Übernahme); dazu *Extrusionsbreite* (Wandstärkenleiter, Handbuch-Glossar)
  gegen *Bahnbreite* (Druckeinstellungen) vereinheitlichen
  (`.claude/rules/oberflaeche.md`).

  [Bisheriger Befund](ROADMAP-ARCHIV.md#rückmeldung-und-freiwillige-unterstützung-gehören-in-die-app-startfläche-31082026).

  **Stand laut Register bis 29.09.2026:** Welle 2 (`9145aedc`) und die Gebietsdurchsichten haben
  die in der Sollliste benannten Stellen, Preise, Generatoraussage, Sicherheit, Agentenquote und
  Sprachkonsistenz nachgezogen; die Durchsicht 0.5.1 hat jeden Text seit 0.5.0 gelesen und
  Wächter gegen Konstrukteurswörter und falsch zitierte Knöpfe eingecheckt (`e8f9f574d`); offen
  ist der erschöpfende Durchgang durch den Bestand vor 0.5.0 in Anwendung und Website, dazu
  Presse A16/A23 und die C12-Namen
  Registerabgleich 02.10.: offen, *Extrusionsbreite* neben *Bahnbreite* am Code bestätigt; die `sollliste*.md` liegen nur unter `Releases/0.5.0/…` und sind nicht versioniert; Statuszeichen wäre `[~]`.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Inventar über 237 Quellmodule,
  fünf Kataloge und 43 Website-Seiten; 154 Quellenstände mit SHA256 gelesen
  (`wording-read-coverage.json`). 14 Schlüssel auf *Bahnbreite*, *Version* und Ich-Form; unbelegte
  Zusagen der Website in allen Sprachen entfernt; Kanalsperre, Druckhinweis 1.2 und
  Kalibrierungssatz folgen dem Code. A16: 22 Presseentwürfe ohne offenes Versprechen. A23: zehn
  Zahlen gegen das Archiv geprüft, drei im Changelog berichtigt. C12: ungestützte Fläche je Schicht.
  Claude stellte den Text zum kleinen Ollama-Modell auf die belegte Fassung zurück und erzeugte die
  Changelog-Seiten neu. Katalog 216, Changelog 48, Website 442 Fälle grün. Belege unter
  `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `construction-ui.md`,
  `rm084-website-four-languages.md`, `construction-wording-a23.md`.

  **Teilstand 04.10.2026 (Claude, H1 texte-quelle):** Gelesen wurden alle
  Kundentexte der 135 Quellmodule, die die Codex-Abdeckung nicht führt
  (3304 Texte, darunter Kern, Bausteine, Kommandozeile, Erzeuger in `tools/`),
  dazu 657 seit v0.5.1 neue Texte in 31 gelesenen, inzwischen geänderten
  Modulen, die deutsche und englische Start- und Funktionsseite (Code gegen
  Aussage) und das Impressum. 33 Schlüssel neu gefasst und in allen fünf
  Katalogen neu übersetzt, drei englische Übersetzungen auf *line width*
  gezogen: Entwicklersprache (Stapel, Container, Löser, Budget, Kern,
  gestörte Eingangsgeometrie, Entwicklungsumgebung) durch Kundenwörter ersetzt,
  `**im**` aus einem Feldtooltip, ein Datum aus einem Bausteinhinweis, zwei
  Grammatikfehler. *Extrusionsbahnen* steht in keinem Kundentext mehr (vier
  Quelltexte, drei englische Übersetzungen, drei Website-Stellen DE/EN). Die
  Bausteinsuche zählt Wörter mit Bindestrich auch als Ganzes, die Nutfeder nennt
  den Unterschied zum Nutenstein (`registry.PartRegistry.search`,
  `structure.profile_tongue`); `tests/test_parts.py` 18 neue Fälle, vorher 7
  der Wörter ohne Treffer (`suche-vorher.txt`). Website: Signaturhinweis in
  sechs Sprachen „ab 0.5.0“ statt „0.5.0“, Merkmalsfenster → Auswahlfenster,
  englische Bausteinnamen wie im Katalog (*nut trap*, *screw hole with
  countersink*, *dowel pin*), Changelog-Sätze („vorher kostete …“) aus der
  Funktionsseite. `tools/check_part_ranges.py` prüfte im Worktree den
  Hauptklon (Editierinstallation), berichtigt; Bereichsnachweis für 26
  Bausteine neu gefahren, alle bestanden. Belege unter
  `F:\solidon-review-reports\claude-2026-10-04\texte-quelle\`.

  **Teilstand 04.10.2026 (Claude, Katalogdurchsichten H2–H4, zusammengeführt in `f1f8fe59e`,
  `3338c1059`, `e40bd6df6`, Waisen bereinigt in `cef201878`):** Jeder der fünf Kataloge ist Eintrag
  für Eintrag gegen die deutsche Quelle gelesen (je 7 839 Einträge), kein Schlüssel geändert. EN 582
  Werte (`e8fc54c99`): ein deutscher Begriff, eine englische Übersetzung (Bahn line, Prüfbericht
  report, Baustein part, Übergabe handover, Teilung spacing, Zeichenebene drawing plane, Skelett
  armature, Versuch attempt, festschreiben lock in), Bedienelemente in Anführung wie ihr Eintrag,
  britische Schreibung. ES 708 und PT 674 Werte (`15a44c165`): Merkmal → característica, Slicer →
  slicer, Druckplatte/Bett → placa bzw. mesa, Bahn → línea/linha, Langloch → ranura/furo oblongo,
  Anrede durchgehend Sie, europäisches Portugiesisch, drei Sinnfehler aus v0.5.1 behoben;
  ES/PT-Startseite und Funktionsseite nachgezogen und im Browser bei 390 und 1440 px abgenommen. FR
  602 und IT 791 Werte (`c3cb25d0e`, `0d1219b44`): Merkmal → caractéristique/caratteristica samt
  neun Knopfnamen, Baustein → bloc/blocco, Überhang → surplomb, Prüfbericht → rapporto di verifica,
  Zurücksetzen → Réinitialiser/Reimposta, Italienisch durchgehend „tu“, *Slicen* → „Esegui slicing“;
  FR/IT-Seiten nachgezogen und bei 390 und 1440 px ohne Überlauf abgenommen. Text-, Wortlaut-,
  Website- und Changelogtests je Zweig grün. Belege mit Änderungstabellen unter
  `F:\solidon-review-reports\claude-2026-10-04\katalog-en\`,
  `F:\solidon-review-reports\claude-2026-10-04\katalog-es-pt\` und
  `F:\solidon-review-reports\claude-2026-10-04\katalog-fr-it\`.

  Offen: Handbuchseiten, Bildschirmfotos und Assetstempel je Sprache beim Release
  (`tools/make_manual.py`, `make_web_images.py`; bis dahin sind die `rendered`-Fälle von
  `test_wording` rot); Fensterabnahme beim Release (RM-213) der längeren Knopfnamen (EN *Reverse
  selected entry*, *Even out the triangles now*; FR *Supprimer la caractéristique* und Verwandte, IT
  *Esegui slicing*, ES/PT Druckeinstellungen) auf 1280 px. Gemeldete Fehler der deutschen Quelle,
  nicht geändert:

  1. `Abziehen` ist ein Schlüssel für die Boolesche Operation und den Knopf im Filamentverbrauch
     (`app/ui/filament_usage.py`); der Knopf braucht einen Kontext.
  2. `Bereich` ist ein Schlüssel für das Feld der Texturfläche (`geom/texture_ops.py`) und die
     Spalte „Wertebereich“ im Handbuch (`registry/surfaces.py`); braucht einen Kontext.
  3. „… für den Fall, dass sie noch nicht auf dem Bett liegt“ (`ui/main_window.py`, Modell aus dem
     Netz): gemeint ist der Rechner, nicht das Druckbett.
  4. „Zug zurückgenommen — Strg+Z holt ihn wieder.“ (`ui/main_window.py`): Wiederholen ist Strg+Y.
  5. „Auswahl als Baustein speichern“ … „der ganze Stapel“: „Stapel“ ist der alte Name des Verlaufs.
  6. „… der Kern rechnet mit der Kurve selbst“ (Plattenumriss): Entwicklersprache.
  7. Die Schlüsselloch-Meldung nennt „Kopfspiel“; die Felder heißen Einhängeweg, Kopftiefe und
     Spiel.
  8. Meldungen sagen „erst gleichmäßig vernetzen“, die Operation heißt *Dreiecke angleichen*.
  9. Der Doc „Nenndurchmesser der Bohrung“ nennt *Schraubenloch*, der Baustein heißt *Schraubenloch
     mit Senkung*.
  10. `app/core/figures.py`: Die Titel der vier Wege weichen von den Kapitelüberschriften im
      Handbuch ab.
  11. Die Texte zu `boolean.jittered` sind Entwicklersprache.
  12. „Wählen Sie die Flächen für Ihr Teil.“ und Verwandte mischen Konturflächen und Körperflächen
      unter „Fläche“.
  13. „Alle acht Filamentplätze bleiben belegt. Wählen Sie sämtliche Flächen eines Filaments oder
      den ganzen Körper ab, …“ ist mehrdeutig („ab“ als abwählen oder auswählen).

  Changelog: ja — die Sinnfehler in ES/PT und die uneinheitlichen Knopfnamen in FR/IT (seit
  `6949b869d`, v0.3.1 bis v0.5.1) lagen in Tags; im Abschnitt 0.5.2 ist der Punkt zu Englisch und
  Spanisch auf alle Übersetzungen erweitert, ein Punkt zu Anrede und Sinnfehlern kommt dazu.

  **Teilstand 04.10.2026 (Claude, Q quelltexte-de, `871cc29e6`):** Die zwölf offenen Fehler der
  deutschen Quelle sind behoben, der dreizehnte (`boolean.jittered`) war es schon. Zwei Schlüssel
  mit zwei Bedeutungen tragen einen Übersetzungskontext: *Abziehen* im Filamentverbrauch
  (`Lagerbestand`, EN *Deduct* statt *Subtract*, samt dem Satz, der den Knopf zitiert) und
  *Bereich* an der Texturfläche (`Musterfeld`, EN *Area* statt *Range*; die Handbuchspalte bleibt
  *Range*). Dazu: Modell aus dem Netz ohne „Bett“, die Quittung nach *Zug zurücknehmen* („Zug
  entfernt. Strg+Z holt ihn zurück.“; Strg+Z ist dort richtig, weil das Entfernen eine
  Parameteränderung ist), Bildbeschreibung ohne „Stapel“, Kreis-Tour ohne „Kern“, Schlüsselloch
  nennt das Feld *Spiel*, Bohrungshilfe den Baustein *Schraubenloch mit Senkung*, die Abbildung
  der vier Wege die Überschriften ihres Handbuchkapitels, „Erst gleichmäßig vernetzen“ wird „Erst
  die Dreiecke angleichen“ (Relief, Formen, Tour, Knopf *Dreiecke jetzt angleichen*), das Glätten
  verweist auf *Kanten verfeinern* wie sein Knopf, im Zeichnungsimport und am Lochfeld heißt eine
  gezeichnete Fläche *Kontur* bzw. *Umriss*, *Filament entfernen* sagt „Entfernen Sie …“ statt des
  zweideutigen „wählen Sie … ab“. 27 Quellschlüssel ersetzt, 29 neue Schlüssel und ein
  berichtigter Wert je Katalog (numstat je Sprache 30/28, keine fremde Zeile entfernt), alle fünf
  Sprachen neu übersetzt (es Sie-Form, it „tu“, fr Imperativ, pt europäisch). `test_wording`
  kennt Zitate eines Knopfs mit Kontext (`ZITAT_KONTEXT`); Gegenprobe mit «Sustraer» im
  spanischen Satz rot, mit «Descontar» grün. Der Bereichsnachweis der elf Bausteine aus
  `mounting.py` ist neu gefahren, alle bestanden. Text-, Wortlaut- und Sprachtests 666 grün;
  betroffene Tests (402 von 423 Dateien, ohne Fenster und Renderer) 22 655 grün, 115 übersprungen,
  die vier Roten erklärt und einzeln grün (`F:\solidon-review-reports\claude-2026-10-04\quelltexte-de\`).

<a id="rm-090"></a>

- [~] **RM-090 — Gemeinsamen Vertrag für die fünf Produkterlebnisse umsetzen.**
  **Entscheidung Robert, 03.10.2026: „Alle fünf als gemeinsamen Vertrag festhalten“.**
  Druckziel, Übergabestatus, Befundkarte, Änderungsvorschau und Übergabebeleg gelten
  gemeinsam für die vier Hauptwege. Der versionierte Vertrag steht im
  [Produktkompass §§4.1–4.6](konzepte/konzept-produktkompass-2026-08.md#46-gemeinsamer-daten--und-abnahmevertrag-rm-090):
  Kundennutzen, gemeinsame Grundlage und Prüfzustände, bestehende Einstiege,
  Zuständigkeiten, Wechsel-/Abbruch-/Undo-/Fehlerfolgen und konkrete Abnahme.
  Der Beschluss belegt noch keine vollständige Umsetzung. Offen sind:

  - sichtbare Vollständigkeit des Druckziels und fachlicher Umgang mit fehlenden oder
    ersetzten Profilen gemeinsam mit der Profilschicht;
  - gemeinsamer Übergabestatus aus Zielgrundlage, Prüfzuständen und Befunden;
  - sichtbare Folge/Grundlage sowie zugängliche Einzelheiten und Nebenfolgen je Befund;
  - einheitlicher Vorher-/Nachher-Vergleich für Maße, Körperzahl, Befunde und Verluste
    an Menü-, Bericht- und Chatvorschauen;
  - Beleg des tatsächlich ausgeführten Export-/Slicerauftrags mit Risiken,
    Formateigenschaften und nachgewiesener oder ausdrücklich nicht durchgeführter
    Gegenprobe aus dem zuständigen Kern;
  - gemeinsame Abnahme aller fünf Erlebnisse auf den vier Hauptwegen, einschließlich
    Fehler-/Wechselfällen, sechs Sprachen und echter Oberfläche gemäß Vertrag.

  Vorhandene Druckerprofile, Bericht, Vorschau, Export und Slicer-Übergabe bleiben die
  Ausgangspunkte. Fachliche Geometrie-/Schicht-/G-Code-Prüfungen liefern ihre Ergebnisse;
  die Oberfläche erfindet keine Ersatzanalyse. Keine Archivierung vor dem Nachweis.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Kern: `types.CheckState`,
  `EvaluationResult.check_states`, `check_status` und `missing_basis` an `evaluate` und
  `print_findings`; leere Befunde heißen nicht geprüft (52 Schicht-, 205 Auswertungs-, 243
  Passungsfälle). Oberfläche `ui/print_contract.py`: Druckziel streng aus dem Profilbestand, vier
  Zustände mit Symbol, Befundkarte mit Grundlage und Ort, Erklärung aus denselben
  Vorher-/Nachher-Szenen, Beleg für Export und Slicer mit „Gegenprobe nicht durchgeführt“ (36, 68,
  39, 207 Fälle). Am Fenster: Zustandswechsel am Piratenschiff, begrenzter Prüfumfang, Haltfolge v8.
  Offen: Kandidatenszene neu bewerten, `write_plan`-Gegenprobe, Nebenfolgen je Handlung aus dem
  Kern, NM 1–11. Belege unter `F:\solidon-review-reports\codex-2026-10-03\bedienung\`:
  `import-history-move.md`, `import-history-native-matrix.md`, `root-review-rm090.md`.

  **Teilstand 04.10.2026 (Claude, Zweig `claude/rm-druckvertrag-oberflaeche`, zusammengeführt in
  `b94f899e9`):** Gegenprobe: `core/export/readback.py` liest jede geschriebene Datei mit den Lesern
  des Imports zurück und vergleicht je Körper Dreieckszahl, Volumen und sortierte Außenmaße (Grenzen
  aus `EPS_DISPLAY`, lageunabhängig für Bettkoordinaten, Plattenraster und GLB-Achsen). Menüexport,
  *Im Slicer öffnen* und `cli export` tragen das Ergebnis in Beleg bzw. Ausgabe; eine Abweichung
  macht den Beleg zur Warnung, ohne Sollwerte heißt es „nicht durchgeführt: Grund“, die
  Kommandozeile endet dann mit Exit 1. Vorher stand fest „nicht durchgeführt“. Nebenfolgen:
  `core/action_effects.py` nennt für jede der 115 Handlungskennungen des Kerns, was sie zusätzlich
  verändert oder dass sie das Modell nicht ändert; die Befundkarte zeigt sie unter dem Hauptknopf
  und in Kurzhilfe und Beschreibung jedes Knopfs, dazu die Folge je Schweregrad. Kandidatenszene:
  Die genaue Neubewertung beider Stände ist am zu breiten Quader mit *Skalieren* 0,5 belegt; die
  Erklärung nennt nur Neues und Weggefallenes, je höchstens vier Zeilen (vorher am Piratenschiff 2 ×
  32 Zeilen). Tests: `test_export_readback.py` 15, `test_action_effects.py` 2,
  `test_print_contract.py` 25, `test_print_contract_ui.py` 35 (NM 1 bis 11 ohne Fenster),
  `test_cli.py::test_export_reads_back_what_it_wrote`; Gegenproben: vorher fest „nicht
  durchgeführt“, vorher 2 × N Zeilen. Commits `87d2cb69f`, `9dc2842e5`. Belege unter
  `F:\solidon-review-reports\claude-2026-10-04\druckvertrag-oberflaeche\`. Offen allein die
  Fensterabnahme beim Release (RM-213): Teilmengenexport als STL und 3MF mit Gegenprobe im Beleg,
  *Im Slicer öffnen* mit 2 von 2 Körpern, Befundkarte mit Folge, Ort und Grundlage samt Tab-Weg in
  sechs Sprachen, Vorschauband beim *Skalieren* eines zu breiten Quaders, Piratenschiff-Reparatur,
  unbekanntes Druckerprofil mit Strg+Z, Behälterschritt unverändert und mit Steckdeckel. Changelog:
  ja, der vorhandene Beleg-Punkt ist neu gefasst, ein Punkt zur Folge je Befund kommt dazu (alles
  neu seit v0.5.1).

<a id="rm-131"></a>

- [~] **RM-131 — Zurückgestellten Mehrfachimport entscheiden.** Mehrfachimport bewusst
  zurückgestellt lassen. Bei Wiederaufnahme: mehrere Dateien in einem Vorgang übernehmen, die
  gemeinsame Baugruppenlage erhalten und gleichartige Importbefunde bündeln. Abnahme:
  Piratenschiff-Ordner ohne siebzehn Dialoge, ohne still verworfene Dateien und mit
  nachvollziehbarer Platzierung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#neunzehn-kundendateien-durch-die-oberfläche-gefahren-04092026).

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `Session.import_models_async`
  liest im abbrechbaren `_BatchReadWorker`; alle Dateien kommen als eine Transaktion in ihrer
  Dateilage, eine Einheiten- und eine Erkennungsfrage gelten für die ganze Auswahl, ein Abbruch
  zieht alle Quellen zurück. Gleiche Importbefunde bündelt der Prüfbericht je Transaktion, die
  Details behalten jede Originalmeldung. Am Fenster: 17 STL des Piratenschiffs,
  373,15 × 351,07 × 115 mm wie die Quellen, ein Verlaufseintrag, Erkennungsabbruch, Undo/Redo,
  Speichern und Öffnen mit gleichen SHA256, vier Lochreparaturen gebündelt. Nach dem Fix nicht mehr
  am Fenster gesehen: das Bündel `ingest.multiple_components` und NM 1–4. Belege unter
  `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `root-evidence.md`,
  `import-history-native-matrix.md`.

  **Teilstand 04.10.2026 (Claude, Zweig `claude/rm-druckvertrag-oberflaeche`, zusammengeführt in
  `b94f899e9`):** NM 1–4 als Tests ohne Codeänderung grün:
  `test_print_contract_ui.py::test_nested_part_notes_bundle_per_wording_and_select_exactly_their_bodies`
  (je Wortlaut ein Bündel, Aufklappen nennt jeden Körpernamen, Klick wählt genau die Gruppe, keine
  Originalmeldung geht verloren); `test_batch_import_ui.py` 6 Fälle: Dateidialog abbrechen auf
  Startseite und im Projekt, abgelehnte Vollerkennungsfrage lädt alle drei Dateien mit einer Frage
  und einer Transaktion, *Modell einfügen* erhält den vorhandenen Körper und die Lage zueinander,
  Undo nimmt nur die Gruppe, Speichern/Öffnen gleich, offene Form- und Skelettsitzung weist den
  Import mit Rückweg ab. Späte Antworten belegen
  `test_ui.py::test_batch_import_discards_late_reads[cancel/project]`. Commit `25a9484f7`. Belege
  unter `F:\solidon-review-reports\claude-2026-10-04\druckvertrag-oberflaeche\`. Offen allein die
  Fensterabnahme beim Release (RM-213) am Piratenschiff: Bündel und Auswahl, 17 STL mit
  Dialogabbruch und geschlossener Erkennungsfrage, *Modell einfügen* mit Strg+Z/Strg+Y und
  Speichern, Abbruch während des Lesens. Changelog: nein, nur Nachweis.

<a id="rm-135"></a>

- [~] **RM-135 — Zugewiesene Höhe der Filamentkarte vollständig nutzen.** Qt berechnet Hinweis,
  sichtbare Knöpfe und Abstände bei der tatsächlichen Breite; leere Listen erzwingen keine
  überzähligen Mindestzeilen. Acht Regressionen und die native Windows-Abnahme mit knappen/freien
  Höhen, langen Hinweisen, großer Schrift und voller Liste sind grün. Nachbarkarten behalten ihren
  Raum; der Mac-xfail ist entfernt. Offen bleibt der plattformübergreifende Prüflauf auf macOS.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#ein-ort-für-die-auswahl-07092026).

<a id="rm-136"></a>

- [~] **RM-136 — Gezeichnetes Fensterschema und Bildbeschreibungen aktualisieren.** Das gezeichnete
  Fensterschema an Projektkopfzeile, Operationsbereich und aktuelle Auswahlspalte anpassen; Bild,
  Bildunterschrift und Alternativtext müssen dasselbe erklären. Abnahme: alle sechs Sprachen, danach
  beim nächsten betroffenen Release nur erforderliche Abbildungen/Handbücher/PDFs neu erzeugen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-durchsicht-des-07092026).
  Registerabgleich 02.10.: teilweise erledigt — Quelle nachgezogen, Erzeugung lief (`window.svg` gleicht in allen sechs Sprachen dem Code, `401d35299`); Statuszeichen wäre `[~]`, „Erzeugung beim Release“ in der Registerzeile ist veraltet.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Die 12 Fenster-SVGs (sechs
  Sprachen, hell und dunkel) gleichen dem Generator in `core/figures.py`, alle sechs HTML-Alttexte
  dem vollständigen `Figure.alt`; der Kontaktbogen ist angesehen. Gefunden: Lange Berichtstitel
  liefen in Spanisch und Portugiesisch aus der Spalte, `_window` bricht sie jetzt um. Nur die 12
  Fenster-SVGs sind neu erzeugt, `stamp_page` hat je Seite zwei Bildverweise erneuert. Bestand 18/18
  Bedingungsarten, 12/12 SVG, 6/6 Alttexte. Belege unter
  `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `construction-ui.md` (RM-136),
  `construction-docs.json`, `window-six-languages.png`.

<a id="rm-213"></a>

- [~] **RM-213 — Fensterabnahme und die Kundenwege am echten Fenster.**
  Die Paketnachweise der Durchsicht 0.5.0 stammen überwiegend aus
  Offscreen-Läufen oder Fenstern mit `WA_DontShowOnScreen`. Die späteren
  Website-Aufnahmen und Skizzenlabel-Sonden zeigen echte maximierte Fenster;
  sie belegen ihre Motive und die jeweiligen Reparaturen. Die vollständige
  Welle 2 „kundenwege" mit allen folgenden Abnahmekriterien ist damit noch
  nicht gefahren. Was nur das echte Fenster zeigt (Schrift, Vulkan-Fläche, Fokus,
  Bildschirmleser, gefühlte Wartezeit, Navigation mit Drehpunkt nach Änderungen an
  `_NAVIGATION` oder `camera_step`): die Punkte RM-197 bis RM-200 und RM-204
  (sie bleiben je eigene Punkte und schließen in diesem Lauf; RM-174 und RM-205
  sind ohne ihn geschlossen, siehe Archiv);
  dazu ohne eigenen Punkt die Einladungszeile und Rückfragekarte über der
  pygfx-Fläche (foerderung), Marken und Beschriftung der Fase auf hellem und
  dunklem Thema (P6.2), die neuen Bedienelemente der Dialoge mit Maus und
  Bildschirmleser („Stelle im Bild wählen", Stückzahl-fx, Schichthöhe,
  Übergabefrage), Balken und *Abbrechen* der Vorschau (RM-208), der
  Mehrkörperdialog (P7.4), die Deckkraft der Nachbarn im Zeichenmodus (8 %/16 %,
  Robert sieht sie am eigenen Schirm an), Klickgefühl und Tab-Reihenfolge des
  Merkmalfensters. Die Kundenwege aus der Sollliste: Weg 1 mit einem
  Printables-Seitenlink (C14), eine Rändel-STL aus dem Netz (A13), eine
  M5-Durchgangsbohrung in einer fremden STL (A4), PETG-Teilung mit
  anschließendem Materialwechsel (C5), Befunde am Mehrfarbauftrag (C1) — und die
  vier Hauptwege Ende zu Ende mit Modellen aus `F:\3D Dateien` und
  Reaktionszeiten auf ruhiger Maschine. Vorbedingungen: alle Fenstertests der
  Pakete laufen im Release-Tor (neu u. a. `test_feature_pattern_ui.py`,
  `test_hollow_opening_ui.py`, `test_step_assembly_ui.py`,
  `test_history_revision_ui.py`, `test_mesh_to_exact_ui.py`), dazu die beiden am
  alten Stand roten Fälle
  `test_pose_session.py::test_exact_armature_gestures_reach_the_guarded_operation_dialog`
  und
  `test_operation_ui.py::test_aligning_without_a_target_invites_instead_of_teaching_syntax`;
  der Bereichsnachweis aller 35 Bausteine ist frisch (sonst zeigt der Katalog
  35-mal die Warnung); `make_figures.shoot` (Handbuch) und die übrigen
  Aufnahmewerkzeuge fragen die Fensterwache `foreign_window_over` wie
  `make_video.record` und `make_web_images.grab` (website, `6759555d`:
  parallele Aufnahmen zerstörten Bilder anderer Sitzungen). Abnahme: ein
  Protokoll je Weg mit Klicks, Zeiten und Bildern nach dem Bildstandard vom
  23.09.2026, jeder Befund behoben oder als Punkt geführt.

  **Aus der dritten Runde der Durchsicht v0.5.1 (27.09.2026)** kommen Fenstertests, die
  das Release-Tor tragen muss; die Abschlüsse von RM-231 und RM-269 stützen sich auf sie
  (Nachweis bisher an Sonden am gebauten Fenster):
  `test_start_screen.py::test_one_click_opens_a_recent_project_once`,
  `test_feature_panel.py::test_a_chosen_edge_or_pair_is_not_called_nothing_chosen` und
  `::test_a_returned_measure_group_shows_what_a_fresh_one_would`,
  `test_viewport_decisions.py::test_a_fresh_split_is_framed_once_with_all_its_parts`,
  `test_analysis_ui.py::test_a_fresh_split_asks_the_view_to_frame_all_parts`,
  `test_surface_placement_ui.py::test_a_released_measure_group_goes_back_only_without_a_parent`
  und `::test_a_click_on_the_grip_leaves_the_next_hole_free`, dazu der Bericht aus
  `report_error` in `test_first_run.py`. Ein Fall ist schon am Stand davor rot, in einer
  Sonde außerhalb von pytest an `0273b8d23` und `c2bff45f1`:
  `test_surface_placement_ui.py::test_the_measures_stay_in_the_view_while_a_pulled_slot_waits`
  — nach dem Zug zum Langloch stehen keine Maße im Bild, erwartet sind zwei Felder und kein
  runder Umriss (`konzepte/nachweise-release-0.5.1/sonden/rest-auswahl/out/fenster-vor.txt`). Ob das
  der Testaufbau außerhalb von pytest ist oder ein Produktbefund, sagt erst der
  Release-Lauf.
  Registerabgleich 02.10.: offen; die Vorbedingung „Bereichsnachweis frisch“ ist erfüllt (Test grün), weiter offen ist, dass `make_figures.shoot` die Fensterwache nicht fragt.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `make_figures.grab_uncovered`
  prüft vor und nach jedem nativen Bildgriff auf fremde Fenster und verwirft ein verdecktes Bild;
  höchstens zehn Griffe in 30 s, ein leeres Bild endet mit Handlungsvorschlag. Angeschlossen an
  Handbuch, Galerie, Funktionsbilder, Video, Longform, Werkstattfilme und Website-Ausschnitt; 21
  neue Schutzfälle, `test_toolchain.py` 149 grün, Mypy der sieben Werkzeuge ohne neue Meldung (56
  Bestand). C14: Die Zwischenablage behält Modellseiten in *Modell aus dem Netz*, Downloads hängen
  an Arbeiter und Projektgeneration (23 Fenster-, 32 Abruffälle). Offen: native Überdeckungsprobe,
  C14-Schritte 1–6, Raster nur unter Windows. Belege unter
  `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `rm213-capture-review.md`,
  `import-history-move.md` (C14).

<a id="rm-232"></a>

- [~] **RM-232 — Die Klickkette an einem Merkmal rechnet noch im Hauptfaden.**
  Gemessen in der Durchsicht 0.5.0 (sitzung, fenster), offscreen: Je
  Bohrungsklick ruft `_place_from_feature_panel` dreimal `PlacementFlow.redraw`
  synchron und dreimal nach dem Arbeiter; `done` → `_settle` ruft
  `placement.prepare_surface` im Hauptfaden (33 ms am Wabenhalter, an der
  dichten Platte 1–2 s). Der erste Klick an einem Körper zahlt
  `prepare_ops.bore_entrance` (Netzkopie mit `merge_vertices` und ein `cKDTree`
  je Aufruf; am Besenhalter rund 200 ms) und `relations._shoulder_connections`
  (Siebhalter 184 ms, 133 Aufrufe `_face_boundary_rings`); danach gemerkt. Die
  app-weiten Ereignisfilter (`shortcut_schemes.eventFilter`,
  `NavigationKeys.eventFilter`) sehen jedes Ereignis, rund 20 000 Aufrufe je
  acht Klicks. Weg: am Stand nach `f64e17c7` nachmessen (beziehungen hat
  Oberflächenindex und Randringe je Körper gemerkt), dann `redraw` einmal je
  Klick, `prepare_surface` in den Arbeiter, die Filter auf die Widgets
  beschränken, die sie brauchen. Abnahme: Klick bis Ruhe unter 100 ms am
  Wabenhalter und unter 300 ms an der dichten Platte, gemessen mit
  `click_probe --ab`.

  **Nachgemessen am 25.09.2026** (Stand `1fc5ecc5`, eigene Sonde mit Zeit bis
  Ruhe und längster Lücke im Hauptfaden): `prepare_surface` lief schon im
  Arbeiter, aber an einer **frischen Kopie je Fluss** — und jeder
  Merkmalklick baut einen Fluss. Offscreen kostete der Arbeiter an der
  dichten Platte 250–520 ms je Bohrungsklick für dieselbe Oberseite. Gebaut:
  `for_a_worker` behält die Kopie je Szenennetz (zwei Netze, mit Schloss,
  `on_the_copy`), `prepare_surface` merkt seine Antwort am Netz, und die
  Feldanordnung prüft Striche erst, wenn ihr Hüllrechteck das Feld erreicht
  (24 000 Schnittproben je Klick am echten Fenster, fast alle gegen ferne
  Striche). Bohrung zu Bohrung bis zur Fläche am echten Fenster, abwechselnd
  gemessen: Wabenhalter 375–434 → 296–308 ms, dichte Platte 522–524 →
  349–356 ms; offscreen bis Ruhe an der Platte 307 → 133 ms. **Offen:** Der
  erste Klick an einem Körper (Wabenhalter ~500 ms, Platte ~850 ms) zahlt im
  Hauptfaden die Kernauskünfte (`FeaturePanel._answers_for`, 78–150 ms) und
  die Markierung (`_redraw_feature_patch`, 44–140 ms), und die kalte
  Trägerfläche im Arbeiter hält den GIL (bis 600 ms Lücke); am echten
  Fenster kosten dazu Sichtbarkeitswechsel im Merkmalfenster und die Bilder
  je Klick. Die drei `redraw` in `_place_from_feature_panel` sind billig
  (um 2 ms) — die Maßgruppe bestellt ihr Bild ohnehin gebündelt.

  **Weitergebaut am 25.09.2026** (Sonden und Messungen unter
  `.claude/.state/rm-232-erster-klick-2026-09-25/`). Die Kernauskünfte des
  Merkmalfensters rechnet an einem Körper ab 20 000 Dreiecken der Arbeiter
  (`MainWindow._answer_in_worker`, `panels.feature_answers`), an der
  Arbeiterkopie, die jetzt die trimesh-Merker des Originals mitnimmt; die
  Nachbarschaft der Platzierung liest den Eckenrang des Körpers
  (`features.vertex_rank`, 114 → 30 ms), die Übergänge einer Bohrung werden
  ab ihrer Wand gesucht statt im ganzen Netz (an 277 Bohrungen dieselbe
  Antwort, 404 → 100 ms). Erster Bohrungsklick an der dichten Platte, offscreen:
  172 → 36 ms im Hauptfaden, längste Lücke 171 → 52 ms, bis Ruhe 850 → 334 ms;
  Bohrung zu Bohrung 72–89 ms. **Und die Zwischenbilder sind weg** (Robert:
  „das panel von der bohrung in dem viewport an einer anderen stelle
  gezeigt"): Die Ansicht bestellt ihr Bild für Qts Malrunde statt `repaint()`
  (das malte das ganze Fenster samt halb gelegtem Auswahlfenster, sechsmal je
  Klick), die Maßkarte wartet verborgen auf ihre Trägerfläche statt oben
  rechts, das Merkmalfenster stellt vor dem Start der Maßgruppe um und legt
  seine Layouts sofort, und die Operationsliste meldet ihre echte Höhe (der
  Rollbalken sprang an). Gemessen an den Malereignissen: vorher zwei bis sechs
  gequetschte Bilder je Klick, nachher keines, an Platte und Wabenhalter.
  **Offen:** Am echten Fenster bleibt Bohrung zu Bohrung bei rund 350 ms an
  beiden Körpern (Abnahme: Wabenhalter unter 100, Platte unter 300). 140 der
  854 Widgets sind native Fenster — ohne `AA_DontCreateNativeWidgetSiblings`
  macht Qt alle Geschwister der wgpu-Fläche nativ, damit die Karten darüber
  liegen —, und jedes Ein- und Ausblenden kostet dort 1,3 ms und malt sofort;
  dazu baut die Maßgruppe je Klick neu (`end_quiet_placement` → `dispose`,
  fünf `redraw`), und `seat_of` rechnet seine Öffnungen und Kanten je Klick
  neu (39 ms im Arbeiter).

  **Weitergebaut am Abend** (Regel in `ansicht.md`, „Nur was über der
  Grafikfläche liegt, hat ein eigenes Fenster"). Die Ansicht setzt
  `AA_DontCreateNativeWidgetSiblings`, bevor ihre Fläche entsteht, und macht
  nur die direkten Kinder von Ansicht und Überlagerung nativ — 140 → 20 native
  Widgets, das Merkmalfenster ohne ein einziges. Schwebende Widgets und
  Maßtinte gehen von Fluss zu Fluss, statt je Klick neu zu entstehen; `start`
  baut einmal auf; `end_quiet_placement` räumt den Rücklauf aus dem eigenen
  Abbau nicht doppelt; die Platzsuche der Felder fragt der Nähe nach (952
  Proben je Klick → wenige, an drei Körpern dieselben Plätze). Gemessen
  abwechselnd bei gleicher Last, Bohrung zu Bohrung bis zur Fläche: Wabenhalter
  200–208 → 127–128 ms, dichte Platte 310 → 163 ms — die Platte unter ihrer
  Schwelle. `seat_of` war kein Posten: allein 18 ms am ersten Loch einer
  Fläche, 1,4 danach (der Merker an `prepare_surface`); die 39 ms im Profil
  waren Warten auf den GIL. Der Bildtakt von rendercanvas (`max_fps=30`) bremst
  nichts (`render/CLAUDE.md`). **Offen:** der Wabenhalter unter 100 ms. Ohne
  jedes native Überlagerungsfenster wären es 100–103 ms; was bleibt, liegt im
  Hauptfaden: Das Merkmalfenster schaltet beim Wechsel der Bohrung zweimal um
  (`set_measuring` aus und an, 87 Sichtbarkeitswechsel, rund 10 ms), das
  Werkzeug der neuen Bohrung kommt neu in den Renderer (rund 10 ms),
  `_redraw_features` 14 ms, zwei Bilder je Klick, Zeigen und Bewegen der neun
  nativen Felder (rund 20 ms). Gemessen wird mit `ab.sh` und
  `scenario_zeitleiste.py`, und nur bei ruhiger Maschine — unter Fremdlast
  schwankt schon der synchrone Teil zwischen 58 und 97 ms.

  **Weitergebaut am 26.09.2026.** Eine Zeile, die Bohrung und Senkung
  bündelt, meldet der Baum in derselben Runde als ein Merkmal und als zwei;
  die Ansicht baute ihre Markierung erst für die Bohrung und gleich danach für
  beide. `_on_feature_selected` zeigt das Bündel jetzt gleich ganz
  (`select_feature_refs`), ein Aufbau je Klick weniger. Für Messungen unter
  Fremdlast liest `ab_cpu.sh` mit `scenario_cpuzeit.py` die Takte des
  Hauptfadens (`QueryThreadCycleTime`) statt der Wandzeit. **Offen bleibt die
  Abnahme am Wabenhalter unter 100 ms**, am echten Fenster mit `ab.sh` zu
  belegen, sobald die Maschine ruhig ist; am 26.09.2026 teilten sie sich sechs
  Sitzungen.

  **Durchsicht v0.5.1 (26.09.2026, massbild):** Wabenhalter Bohrung zu Bohrung 124–148
  ms bis die Maße stehen, Ruhe 135–158 ms (vorher 223–249 / 304–337 ms, unter Last,
  abwechselnd im selben Lauf). Rest je Klick: Merkmalfenster und Maßgruppe aufbauen,
  `PlacementFlow._settle`, zwei bis drei Bilder. Die zweite Runde der Durchsicht
  arbeitet an den letzten Millisekunden; die Abnahme misst auf ruhiger Maschine.

  **Durchsicht v0.5.1, zweite Runde (27.09.2026, rest-leistung):** Drei Posten weg. Eine
  Arbeiterkopie liest, was ihr Original schon weiß (`features.copy_with_answers`,
  Abstammung statt `id(body)`; Hohlraumfläche an der Kopie des Laptop-Ständers
  1 038–1 111 → 65 ms, gleiche Antworten, `69426aae9`); an der Anwendung hängt ein
  Ereignisfilter mit Anmeldung je Ereignisart statt fünf (`app_events.py`, 17 ms je
  Klick, `d8b48f569`); unter 20 000 Dreiecken kommen Werkzeug und Fläche beim Start
  gleich im Hauptfaden statt 16 ms später aus dem Arbeiter (`f01f8b622`). Gemessen mit
  `ab.sh zeit` auf dem zweiten Monitor, abwechselnd gegen den Stand davor, je drei Runden
  mit acht warmen Klicks, unter Last: bis zum ersten Bild mit Maßen 102,9 / 127,6 /
  102,6 ms (Median je Runde; vorher 120,8 / 133,6 / 121,9), in den ruhigen Runden
  98–108 ms je Klick, der erste kalte Klick 195 statt 526 ms, bis zur Ruhe ein Bild
  statt zwei. Was im Hauptfaden bleibt, ist Umbau statt Rechnung: je Klick 16 neue
  Renderer-Elemente mit eigener Pipeline (rund 8 ms im ersten Bild), die neu gebaute
  Maßgruppe (17 Widgets erzeugt und gelöscht, rund 2 400 Ereignisse) und der neu gebaute
  Bewegungsgriff (drei Renderer-Objekte). Der Weg darunter, nach Gewinn: die
  Renderer-Elemente mit fester Kapazität behalten und nachfüllen wie die Maßtinte, den
  Griff an ein neues Ziel versetzen statt neu bauen, die Maßgruppe derselben Operation
  über den Fluss hinaus behalten. Daran arbeitet die dritte Runde der Durchsicht
  (rest-klick); die Abnahme unter 100 ms misst danach auf ruhiger Maschine.

  **Durchsicht v0.5.1, dritte Runde (27.09.2026, rest-klick):** Zwei der drei Wege gebaut,
  einer gemessen und nicht behalten, dazu ein vierter Posten. (1) Der Renderer hebt ein
  abgeräumtes Element gleicher Bauart auf und gibt dessen pygfx-Objekte, Materialien und
  Puffer dem nächsten gleichartigen `add_*` mit; nur die Zahlen in den Puffern wechseln
  (`RECYCLE_PER_KIND = 3`, höchstens 32 MB, Vertrag und Ansicht unverändert). Das erste
  Bild nach dem Klick kostet 4,8 statt 11,3 ms (`0273b8d23`). In der Ansicht mit fester
  Kapazität wie die Maßtinte ging es nicht, weil die Markierung mit jedem Merkmal Ecken-
  und Dreieckszahl wechselt. (2) Den Bewegungsgriff versetzen statt neu bauen brachte nach
  (1) nichts (84,0 gegen 84,7 ms im selben Prozess) und ist nicht behalten; der Stand liegt
  unter `konzepte/nachweise-release-0.5.1/sonden/rest-klick/weg2/`. (3) Die Maßgruppe geht ohne
  Elternteil an das Merkmalfenster zurück und kommt je Signatur für die nächste
  gleichartige Handlung wieder, 2 bis 5 ms (`c2bff45f1`). (4) pygfx las für jedes
  Zeigerereignis den Pickpuffer von der Grafikkarte zurück, 1,2 ms im Hauptfaden je
  Bewegung, ohne dass jemand darauf hörte; der Renderer startet jetzt mit
  `enable_events=False` (`0273b8d23`). Gemessen mit `ab.sh zeit`, das Fenster 2560 × 1392
  groß in der Fläche des MSI auf dem einzigen gemeldeten Bildschirm (`NV-Failsafe`, die
  Monitore waren aus), abwechselnd gegen den Stand davor, vier Runden mit je acht warmen
  Klicks, CPU-Last 10 bis 12 %: bis zum ersten Bild mit Maßen 77,1 / 77,2 / 74,2 /
  79,4 ms (Median je Runde; vorher 104,3 / 96,9 / 98,3 / 102,1 ms), 30 von 32 Klicks unter
  100 ms — die zwei anderen mit 102,4 und 102,6 ms in der Runde, in der auch der alte Stand
  bis 107,9 ms streute. Eine Gleichheitssonde, frisch gebaut gegen wiederverwendet, zeigt
  an Wabenhalter und Scraper in 43 Schritten (Muster, Fläche, Langloch-Maße, Escape, andere
  Größe, Strg+Z, Sprachwechsel) dieselben Zustände und keinen anderen Bildpunkt. Kein
  Posten, der im Hauptfaden bleibt, ist allein größer als 5 ms. **Offen ist allein die
  Abnahme auf ruhiger Maschine am eingeschalteten zweiten Monitor:** Schrift, Skalierung
  und das Zusammenspiel mit dem echten Bildschirm sind mit dem Ersatzbildschirm nicht
  belegt. In derselben Runde behoben (rest-auswahl, `962c63cf0`): Ein Klick ohne Weg auf
  den Bewegungsgriff oder ins gewählte Loch band den Maßentwurf, und danach hielt die
  Ansicht jede andere Bohrung fest; ein Zug beginnt jetzt erst jenseits der Klickschwelle.
  Registerabgleich 02.10.: teilweise erledigt, Statuszeichen wäre `[~]`. Das genannte Messwerkzeug `click_probe --ab` gibt es nicht; gemessen wird mit `ab.sh zeit` aus dem versionierten Zustandsordner von RM-232. Rest nur am Gerät.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `_on_feature_picked` aktualisiert
  die Rollen nicht ein zweites Mal (16 → 8 Läufe je acht Klicks); `_settle_lock` zeigt Im-Bild-Knopf
  und Gruppenhaken während des Messens nicht mehr kurz an; `PlacementFlow.flush_frame` nimmt den
  fälligen Bildauftrag in dieselbe Bestellung; ein Hover zwischen gewählten Merkmalen baut die
  Beschriftungen nicht neu. Keine Kernrechnung geändert. Am Fenster v8 (MSI aktiv, nicht ruhig):
  Baumklicks 86,9–93,6 ms bis zum letzten Bild, Bildklicks 105–146 ms durch den späten Hover; dessen
  Fix ist nur offscreen belegt (347 Fälle). Belege unter
  `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `rm232-ui.md`, `root-evidence.md` (RM232
  v6).

<a id="rm-258"></a>

- [~] **RM-258 — Zwei einmalige Stillstände beim Einlesen großer 3MF.** Aus der Durchsicht
  v0.5.1 (fenster, Rest von FENSTER-03). Die Ursache ist mit Release 0.5.1 behoben (Paket
  3mf, `5a6f0bfa3`, Merge `1d13f09bb`): Der Hauptfaden wartete bei jedem Python-Einstieg
  eines Neuzeichnens auf den GIL, unter Windows bis zum nächsten Takt des
  Systemzeitgebers (15,6 ms je Griff, rund hundert Griffe je Bild). Kleinere Stücke im
  3MF-Leser, Umschaltintervall 1 ms (`leash.GIL_SWITCH_S`), 1 ms Zeitgeberauflösung,
  solange ein Arbeiter läuft, der Sekundentakt der Ladeanzeige malt nur ihren Block, die
  Suche nach der 3D-Maus läuft im Nebenfaden. Längste Lücke im Qt-Takt am
  Mausoleum-Drachen vorher 2,5 bis 2,7 s, nachher 0,16 bis 0,31 s (gebunden, im Wechsel,
  unter Last). Offen stehen einmal je Import über 200 ms: das erste Bild der
  Arbeitsfläche (0,15 bis 0,31 s) und der Aufbau der Rückfrage zur Vollerkennung (0,14
  bis 0,55 s; zweimal länger als vorher gemessen, unter 90 bis 100 % Last — auf ruhiger
  Maschine nachmessen). Hebel: weniger Griffe des Hauptfadens je Bild, vor allem der
  Anwendungsfilter `ApplicationEvents`, der für jedes Ereignis in Python läuft. Nebenbei:
  `threemf._outside_meshes` läuft in Python über alles außerhalb der Netze, bei sehr
  großen `texture2dgroup` oder `colorgroup` spürbar. Messung
  `konzepte/nachweise-release-0.5.1/sonden/3mf/` (Reihen `abt`, `ab4` in `out/`), Bericht
  `konzepte/nachweise-release-0.5.1/reports/3mf-schluss.md`. Abnahme: das Fenster bleibt während großer Importe flüssig,
  längste Lücke im Qt-Takt unter 200 ms, auch beim ersten Bild und bei der Rückfrage.

<a id="rm-285"></a>

- [~] **RM-285 — Feste Doppelpunkte hinter übersetzten Teilen.** Aus dem Release 0.5.1 (Handbuch-Sitzung, Wächter aus
  `afc251ae4`; Sprachreview U6). An 108 Stellen verbindet der Code einen übersetzten Teil
  mit einem festen „: “ (f-String mit `{tr(…)}` oder `{_(…)}` direkt vor `": "`): 40 in
  `app/ui`, für Kunden sichtbar — Druckeinstellungen („Druckzeit: …“, „Material: …“),
  Statusmeldungen („Exportiert: …“, „Geslicet: …“, „Geteilt: …“), Prüfbericht
  („Herkunft: …“), Tour, Support-Dialog und die Kurzhilfe im Verlauf
  (`panels._changed_parameters`) —, 5 in `app/core` ohne Agent und Wahrnehmung, 22 in
  `app/cli`, 41 in `app/core/agent` und `perceive/digest.py` (nur fürs Sprachmodell). Im
  Französischen fehlt damit das Leerzeichen vor dem Doppelpunkt, das der Katalog sonst
  setzt (`.claude/rules/uebersetzung.md`). Das Handbuch ist seit `afc251ae4` frei davon,
  sein Wächter liest nur das Handbuch. Weg: den Doppelpunkt in den übersetzten Satz
  (`_("Druckzeit: {value}", value=…)`), zuerst die 40 Oberflächenstellen, dazu ein Wächter
  über die Oberfläche; CLI und Agententexte danach oder bewusst ausnehmen. Abnahme: kein
  fester Doppelpunkt hinter einem übersetzten Teil in `app/ui`, der Wächter ist am Stand
  davor rot.

  **Nachtrag 28.09.2026:** Dazu `print_settings_dialog.py` mit „Gilt für“
  (`f"{tr('Gilt für')}: …"`, Vorschläge je Teil) und im Französischen die
  Werkzeugbeschreibungen des Agenten, vor denen „Où:“ ohne Leerzeichen fest steht
  (Code-Review Handbuch, B7).

  **Arbeitsstand:** Die erneute Oberflächensuche umfasst auch dynamische Titel,
  Namen und zugängliche Beschriftungen: 79 Textausdrücke in 18 UI-Dateien verwenden
  jetzt vollständige Übersetzungsrahmen. Alle fünf Kataloge erhalten dieselben
  50 neuen Schlüssel; 24 nun unbenutzte Schlüssel sind entfernt. Zahlenformat,
  Einheiten, Dateinamen und technische Kennungen bleiben bei ihren bisherigen
  Quellen. Der neue AST-Wächter trägt Gegenproben für f-Strings, Addition,
  Formatierung, Platzhalter und technische Syntax. Reale reine Textfälle decken
  sechs Sprachen sowie Verlauf, Maße, Warnungen und teilbezogene Druckvorschläge
  ab. Der unabhängige lesende Review fand zusätzlich den Sicherheitskontakt im
  Über-Dialog und ein dynamisches Maßpräfix der Platzierung; beide sind vorwärts
  korrigiert, der Präfixwächter und Nummern-/Seitentextfälle ergänzt. Im
  abgestimmten engen Slot bestehen alle 31 neuen reinen Fälle (155 abgewählt,
  Exit 0). Derselbe Oberflächenwächter scheitert am gesicherten Ausgangsstand
  mit den tatsächlichen festen Doppelpunkten (erwarteter Exit 1). Der erste
  Lauf mit drei falsch erwarteten Nachkommastellen bleibt als Historie erhalten;
  nur die Erwartungen wurden an die bestehende zweistellige Millimeteranzeige
  angepasst. Ruff und Format auf den 19 betroffenen Pythonpfaden sind grün.
  Eigenreview, unabhängiger Quellreview und zentraler Paketreview sind
  abgeschlossen. Die UI-Einheit ist mit `b1d5381ce` auf main/origin/main
  integriert; das exakt ausgewählte gemeinsame Entwicklungstor bestand
  18.850 Tests, 62 übersprungen, Suite/Ruff/Format/mypy jeweils Exit 0,
  ohne Quelldrift. Dauerhafte Nachweise:
  `konzepte/nachweise-release-0.5.1/reports/rm285-textnachweise-2026-10-02.md`.

  **Zweite Gruppe:** 29 vollständige Rahmen in `cli/main.py`, `core/install.py`,
  `core/log.py` und `core/support.py`; alle fünf Kataloge erhalten exakt
  22 neue und entfernen 18 global unbenutzte Schlüssel. Rohwerte, Befehle,
  Zeilenumbrüche, Eingabeschlussleerzeichen und Betreffkürzung bleiben erhalten.
  Alle 17 neuen reinen Fälle bestehen (393 abgewählt, Exit 0); derselbe
  erweiterte Wächter scheitert an den vier alten Quellen mit 25 tatsächlichen
  Fundstellen (1 erwarteter Fehler, Exit 1). Eigenreview und unabhängiger
  lesender Quellreview sind ohne offene Befunde abgeschlossen; der zentrale
  Quellreview bestätigt die Freigabe. Diese Gruppe ist mit
  `cb20e107b3b4f81cad6cda95c7aa61ca774ba43e` auf origin/main integriert;
  das vollständige zentrale Entwicklungstor bestand 18.867 Tests, 62 übersprungen,
  Suite/Ruff/Format/mypy jeweils Exit 0. Die dauerhaften Nachweise stehen im
  oben genannten Textbericht. Auch die Bereichsprüferzeile ist nach tatsächlicher
  Neuerzeugung der 35 Bausteinnachweise mit `eae249d2d` integriert (18.908/62,
  sämtliche Entwicklungstor-Prüfungen Exit 0).

  **Offene Grenzen:** 43 feste Doppelpunkte in 42 Ausdrücken der sieben
  Agenten-/Steckbriefdateien betreffen tatsächlich Modellkontext, Antworten oder
  Werkzeugbeschreibungen. Eine Änderung erfordert die vorgeschriebene
  Modellabnahme; diese Quellen bleiben unverändert. Die vollständige Fundstellen-
  und Abnahmeliste steht dauerhaft unter
  `konzepte/nachweise-release-0.5.1/reports/rm285-modelltexte-2026-10-02.md`.
  RM-285 ist insgesamt nicht abgeschlossen. Fenster-,
  Render- und Leistungsabnahme bleibt dem Release vorbehalten.
  Registerabgleich 02.10. (Stand `4449e3370`): Oberfläche und Kommandozeile erledigt, beide Doppelpunkt-Wächter grün; offen nur die Modelltexte (Abnahme kostet Geld, nicht gefahren).

<a id="rm-312"></a>

- [~] **RM-312 — Die Düsengröße im Druckdialog kommt vom Drucker und ist eine Auswahl.**
  Auftrag Robert, 29.09.2026: Die Düsen und damit die Düsengröße sollen vom Drucker kommen
  oder als Auswahlliste wählbar sein. Ausgangsbefund: `Düse ⌀` ist ein freies Zahlenfeld (0,1 bis
  2,0 mm, `print_settings_dialog.nozzle`), vorbelegt mit 0,4 aus `printers.toml`; wer eine
  andere Düse aufschraubt, tippt sie ein, und die Maschinenvariante im Slicer folgt über
  `slicer_profiles.machine_with_nozzle`. Plan: im Kern die Düsengrößen, die der gewählte
  Slicer für dieses Gerät als Maschinenvarianten führt (`printer_model` gleich, je
  `nozzle`), sonst die üblichen Größen; im Dialog eine Auswahl dieser Größen mit „Andere …“,
  vorgewählt die Variante, die im Slicer eingestellt ist; ein Zustandssatz zur Düse steht an
  der Düsenzeile statt in der Zustandszeile. Die Kopfzeile ist ein `QFormLayout` in der
  Folge der Abhängigkeiten (Wächter
  `test_the_print_dialog_asks_in_the_order_its_answers_depend_on`); vor dem Bau mit der
  Sitzung abstimmen, die den Dialog umgebaut hat (`4d955a9e7`). Abnahme: Elegoo CC2 bietet
  0,2/0,4/0,6/0,8 an, eine Wahl stellt Bahnbreite und Maschinenprofil, eine eigene Größe
  bleibt möglich.

  **Arbeitsstand:** Düsenauswahl, „Andere …“, Zustandssatz und Profilanschluss
  sind mit `8374885aeb61da8becb9c2c8d2f3643568d27a93` auf main/origin/main
  integriert. Eigenreview, unabhängige Quell- und zentrale Paketreviews schließen
  die bestätigten UI-/Profilbefunde. Native Cura-Identität hat Vorrang; Orca-
  Geschwisterreferenzen bleiben bis zur tatsächlichen Herstellerunterlage
  eindeutig, auch bei gleichen Anzeigenamen. Der Ausgabeanschluss bestand
  83 gezielte Kernfälle und prüft die tatsächlich geschriebene 3MF sowie die
  alte falsche Profilkennung als Gegenprobe. Das vollständige zentrale
  Entwicklungstor bestand 18.771 Tests, 62 übersprungen; Suite/Ruff/Format/mypy
  jeweils Exit 0. Dauerhafter Bericht mit unabhängig nachgezähltem Laufabschluss:
  `konzepte/nachweise-release-0.5.1/reports/rm312-slicer-matrix-2026-10-02.md`
  (SHA-256 `2df035122e4419d434ddbf9cf7350d85aa1d971214280f7fbfae6b4388326c86`).
  Abschluss 02.10., 17:21 CEST: 125 beendete Modellaufträge, aber nur 124
  Modelle mit Varianten; 2.296 Ergebniszeilen, davon 1.870 mit Druckdateipfad
  und 426 fehlgeschlagen. 149 technisch erfolgreiche Zeilen tragen zusätzlich
  Fehlerbefunde. Der Lauf prüft den eingefrorenen Stand `129f8ca11`, keine
  späteren Korrekturen. Laufabschluss ist keine fachliche Freigabe.

  **Verbleibende Arbeit:**
  - Die 426 Variantenfehler am aktuellen Hauptzweig einordnen und bestätigte
    Produktfehler beheben: 184 ohne Druckdatei, 110 als Absturz gemeldet
    (108 SuperSlicer, 2 Orca), 74 nicht vollständig auf der Druckplatte,
    56 außerhalb des Slicerbauraums, 2 zu hoch. Eingabe, tatsächlich gewähltes
    Profil, Übergabe und Slicerantwort unterscheiden; danach gezielt nachprüfen.
  - `image_00001_.glb`: Lade-Mehrdeutigkeit, null Körper und sieben leere
    Variantenlisten klären; leere Ergebnisse nicht als fachlich geprüft zählen.
    `carpet-corner-clip.step`: Ausrichtungsfehler vor weiterlaufenden Varianten
    prüfen und die Fortsetzungsentscheidung korrekt behandeln.
  - Die 149 Ausgaben mit Fehlerbefund prüfen: 103-mal `gcode.off_the_bed`,
    52-mal `gcode.shorter_than_model`, 5-mal `gcode.spool_left_out`
    (Überschneidungen). 52 dieser Zeilen fehlen im Markierungsfilter;
    vollständige Befunde müssen neben den Markierungen in die Abnahme eingehen.
  - Die 770 technisch erfolgreichen Zeilen mit bedeutsamen Markierungen
    fachlich einordnen: Herstellerabweichung, Stützen in Schicht 1,
    unterbrochener Rand, Zeitabweichung, Lage und Tempo schmaler Stege.
    Hinweise am Kundenweg prüfen; sie sind nicht pauschal Produktfehler.
  - Die verbleibenden 1.353,128 s der Creality-Zeitabweichung mit identischen
    Profilen zuordnen; die tatsächliche Druckdauer ist noch nicht gemessen.
    Der isolierte Ladezeitanteil von 11.900 s erklärt bereits 89,8 % der
    historischen Differenz, nicht den gesamten Versionsunterschied.
  - Native Fensterabnahme der Düsenwahl beim Release durchführen.

  Historischer Registerabgleich am Stand `4449e3370`: Kern erledigt, CC2-Auswahl
  0,2/0,4/0,6/0,8 aus ElegooSlicer und OrcaSlicer belegt
  (`F:\solidon-review-reports\register-bedienung.md`). Der erste rote Torlauf
  bleibt ein Altbefund. Die obigen Restarbeiten halten RM-312 offen.

  **Teilstand 03.10.2026 — mehrere Druckdateien einer Platte:** Bambu Studio
  verteilte sieben Objekte einer Eingabeplatte auf zwei Druckdateien (vier
  Teile mit Werkzeug 0–2, drei mit 3–5); Solidon übernahm still die jüngste
  Datei als vollständiges Ergebnis. `handover._find_gcode` zählt jetzt nur die
  Dateien des jeweiligen Versuchs (eigener Vorbestand je Start, auch beim
  Wiederholen ohne Anordnung und ohne `--cli`), liest `result.json` mit
  `sliced_plates` und hält bei mehr als einer neuen Druckdatei oder Platte mit
  *Auf dem Bett anordnen*, *Nur exportieren* und *Abbrechen* an. Reste einer
  Absage und fremde Dateien im Zielordner zählen weder als Erfolg noch als
  weitere Platte. Gegenprobe: `tests/test_slicer_output_completeness.py`
  (Codex-Linie B, Worktree slicer-mehrplatten), dazu die echte Bambu-Ausgabe
  durch den Rückgabeweg wiedergegeben (`rm312/replay_output.py` gegen den
  integrierten Stand: abgewiesen, drei Handlungen, vorhandene fremde Datei
  bytegleich). Ursache: die jüngste Datei als Rückfall stammt aus der Zeit vor
  v0.5.1; ein Kundenpunkt in allen sechs Sprachen.

<a id="rm-366"></a>

- [~] **RM-366 — Die Vorschau der Formsitzung rechnet die ganze Sitzung im Oberflächen-Thread nach jedem Zug.**
  Review 02.10.2026, Gebietsprüfung Weg 4 (W4-4), am HEAD `6ce767031`.
  `app/ui/main_window.py:11504–11531` rechnet nach jedem Klick und Ziehschritt alle Etappen der
  Sitzung neu, im Oberflächen-Thread.
  **Fehlerfall:** Netz mit 145 742 Ecken: 0,03 / 1,3 / 2,9 / 5,8 s Vorschau bei 1 / 10 / 20 / 40
  Etappen, ohne Fortschritt und ohne Abbrechen — die Oberfläche steht, je länger geformt wird.
  **Fix:** Die Vorschau wendet nur den neuen Zug auf das zuletzt gezeigte Netz an (das Ergebnis
  entsteht weiter erst bei der Auswertung, Regel 2) oder rechnet im Arbeiter mit Fortschritt und
  *Abbrechen*.
  **Abnahme:** Messung: Vorschau nach dem 40. Zug höchstens so lang wie nach dem ersten (Budget
  §31), Oberfläche bleibt bedienbar. Bauplan §2.8, §31.
  Belege: `gebiet-weg4.md`, Sonde `w4_vorschau_hauptfaden.py`.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Auf main setzt `SculptPreview`
  seit `8440db6f7` nur den neuen Zug auf (Kugel mit 145 742 Ecken, F0FF: Vorschau nach Klick 1/39 je
  0,011 s, nach 2/40 0,161/0,145 s). Der Hauptbaum rechnet Netze über 20 000 Dreiecke in
  `_SculptPreviewWorker` weiter; schnelle Klicks kommen in Reihenfolge, frühes *Fertig* wartet auf
  den letzten Zug, Projektwechsel und Abbruch entwerten alte Antworten. Offscreen an echten Netzen
  (325 244 und 452 316 Flächen) über 40 Etappen: UI-Aufruf median 0,57 ms, Ereignislücke höchstens
  23 ms; mit *Glätten* erste/40. Vorschau 0,396/0,369 und 0,546/0,497 s. 101 und 230 Fensterfälle
  grün. Beleg: `F:\solidon-review-reports\codex-2026-10-03\bedienung\sculpt-session.md`.

<a id="rm-368"></a>

- [~] **RM-368 — Schieberegler über den Verlauf (§18.7).**
  Umfangsentscheidung Robert 02.10.2026 („Alles“ auf die Ideenliste der Gebietsprüfung Weg 1, I-1).
  §18.7 verlangt „Schieberegler über den Verlauf. Bezugsgröße ist die Transaktion, nicht die
  Einzel-Op.“ In `app/ui` gibt es keinen (`QSlider` nur in Filament, Einstellungen, Stil);
  vorhanden ist die Einfügemarke im Verlauf.
  **Ablauf:** In der Vorher/Nachher-Ansicht (bzw. über dem Verlauf) ein Regler mit einer Raste je
  Transaktion; Ziehen zeigt den Stand nach dieser Transaktion als Vorschau (Geist + Differenz,
  §18.7), ohne das Dokument zu ändern (Kamera/Darstellung, §2.1); Loslassen lässt den aktuellen
  Stand stehen, ein eigener Knopf setzt bei Bedarf die Einfügemarke dorthin.
  **Stellen:** Verlaufsleiste und Einfügemarke in `app/ui/panels.py` (Verlauf) und
  `app/ui/main_window.py`; Vorschau über den vorhandenen Auswertungs-Cache (`scene/cache.py`),
  Differenzdarstellung `Viewport._redraw_difference` (trägt seit RM-358 W1-3 ihr Muster, `_add_body`).
  **Abnahme:** Test: Regler hat so viele Rasten wie Transaktionen; Ziehen ändert weder Dokument
  noch Verlauf; jede Raste zeigt die Objekt-Hashes des Stands nach dieser Transaktion; Tastatur
  (Pfeile) bedient ihn, zugänglicher Name gesetzt. Bauplan §18.7, §2.1, §2.8 (Vorschau aus dem
  Cache, sonst Fortschritt).
  **Vorgabe Robert 02.10.2026 — allgemein:** Regler für jedes Projekt mit beliebig vielen Transaktionen, auch bei Mehrkörper-Szenen; Abnahme an mindestens drei unterschiedlichen Projekten (Beispiele aus `app/examples` und `F:\3D Dateien\*.p3d`).

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** *Vorher/Nachher* über dem Verlauf
  trägt einen Regler mit einer Raste je Transaktion, Pfeiltasten und zugänglichem Namen; historische
  Stände rechnet der Vorschauarbeiter auf einer Dokumentkopie, die Kamera bleibt. *Hier
  weiterarbeiten* setzt die Einfügemarke. Format 45 speichert `Transaction.renumbered` (Claude:
  Schritt 44→45 statt 43→44), sichtbare Nummern sind von Kennungen getrennt. 452 Kern-, 30
  Verlaufs-, 36 Texturfälle grün. Am Fenster an `native-sculpt-grouped.p3d`: Stand 1 behält die
  Kamera, Einfügen vor *Kopf* erhält alle Namen nach Speichern und Öffnen. Die Prüfprojekte des
  Hauptbaums tragen noch die alte Formatnummer 44. Belege unter
  `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `import-history-move.md`,
  `root-evidence.md`.

  **Teilstand 04.10.2026 (Claude, Zweig `claude/rm-druckvertrag-oberflaeche`, zusammengeführt in
  `b94f899e9`):** Die Rückprüfung „vor Schritt 3“ ist belegt
  (`test_history_revision_ui.py::test_inserted_history_uses_positions_in_report_status_and_dependency_tips`).
  Gefunden und behoben: Nach einem Einfügen nannten weitere Sätze die internen Kennungen statt der
  sichtbaren Nummern — die Absage beim Verschieben (`history._order_problem`), die Absage beim
  Einfügen, die Nachfrage vor dem Löschen (`named_steps`), die Titel von Löschen, Verschieben, Aus-
  und Einschalten und die Umbauabsagen und Merkmalsfrage in `scene/revision.py`.
  `history.step_position` ist die eine Quelle, `ui.labels.step_number` fragt dort (vorher ein
  Zwilling); Werte und Klickziele behalten die Kennungen. Test
  `test_sentences_about_steps_name_positions_after_an_early_insert`, vorher rot („8 Verschieben“
  statt „4 Verschieben“). Commit `9dc2842e5`. Belege unter
  `F:\solidon-review-reports\claude-2026-10-04\druckvertrag-oberflaeche\`. Offen allein die
  Fensterabnahme beim Release (RM-213): „vor Schritt 3“ an `native-sculpt-grouped.p3d`,
  Verschiebeabsage und Löschnachfrage mit sichtbaren Nummern, Regler über zwei weitere Projekte.
  Changelog: nein — die getrennten Kennungen kamen mit `27c7a29e9`, in keinem Tag.

<a id="rm-375"></a>

- [~] **RM-375 — Eine Formsitzung lässt sich wieder öffnen.**
  Entscheidung Robert 02.10.2026 („Alles“ auf die Ideenliste der Gebietsprüfung Weg 4).
  Doppelklick auf einen Schritt *Formen* öffnet heute den Rohdialog mit dem JSON-Feld *Striche*
  (Eingang zu RM-367 W4-3); das Skelett macht es vor (`app/ui/main_window.py:11811`,
  `_armature_of`: ein wieder geöffnetes Skelett ändert seinen Schritt).
  **Ablauf:** Doppelklick bzw. *Diesen Schritt ändern* auf *Formen* öffnet dieselbe Formsitzung
  mit ihren Zügen; Züge lassen sich zurücknehmen oder ergänzen; *Fertig* ändert denselben Schritt
  (eine Transaktion). Im Rohdialog steht statt des Textfelds eine Zusammenfassung („12 Züge,
  Symmetrie X“).
  **Stellen:** `main_window.py` (Formsitzung, Vorschau `:11504–11531`, `edit_operation`
  `:17835ff.`), `app/core/geom/sculpt.py` (Strichtext `:294ff.`), Parameterschema des Feldes
  *Striche* (Darstellung statt Texteingabe).
  **Abnahme:** Test: Sitzung mit drei Zügen fertig → wieder öffnen → ein Zug zurück, *Fertig* →
  derselbe Schritt hat zwei Züge, Verlauf hat keinen zweiten *Formen*-Schritt; Strg+Z stellt drei
  Züge her. Bauplan §2.2 (Weg 4), §2.1, Regel 2.
  **Vorgabe Robert 02.10.2026 — allgemein:** Wiederöffnen für jede Sitzung, die Gesten sammelt (Formen, Skelett, Zeichnen), gleich bedient; Abnahme an mindestens drei unterschiedlichen Modellen aus `F:\3D Dateien` (z. B. Figur, Pilz, Drache).

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Doppelklick oder *Diesen Schritt
  ändern* lädt den Eingang vor genau diesem Schritt im Hintergrund und zeigt dieselbe Leiste mit den
  gespeicherten Zügen; *Fertig* ändert denselben Schritt. Ein Zug ist eine Geste (`Stroke.gesture`),
  Strg+Z nimmt sie ganz zurück, alte Werte ohne Kennung bleiben einzeln rücknehmbar. Eine Zeichnung
  öffnet direkt im Zeichenmodus, `_DiscardedSketch` holt Verworfenes nur ins eigene Projekt zurück.
  Der Rohdialog zeigt eine Zusammenfassung statt JSON. Test 3 → 2 Züge, Undo 3, ein Schritt; 230
  Fensterfälle grün. Am Fenster: Figur mit drei Zügen, Undo/Redo, Speichern und Öffnen, dazu der
  Pilz. Belege unter `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `sculpt-session.md`,
  `construction-ui.md` (RM-375), `root-evidence.md`.

<a id="rm-377"></a>

- [~] **RM-377 — Überhangkarte, Bauraum und Druckbefund laufen in der Formsitzung mit.**
  Umfangsentscheidung Robert 02.10.2026 („Alles“ auf die Ideenliste der Gebietsprüfung Weg 4).
  In der Formsitzung läuft nur die Wandstärkenkarte; Überhangkarte und Bauraumprüfung nicht
  (Formkonzept §12). Nach dem Posieren soll laut Konzept §7.5 „in der Leiste stehen, was der
  Druck davon hält“ — es gibt keinen Befund in der Posierleiste (`app/ui/pose_bar.py`).
  **Ablauf:** In der Formsitzung umschaltbar Wandstärke/Überhang (vorhandene Analysekarten,
  verzögert im Hintergrund, §18.9); ein Hinweis, sobald der Körper den Bauraum verlässt; nach
  *Fertig* beim Skelett eine Zeile in der Leiste mit dem Druckbefund (Überhang, Einschnürung
  `pose.pinched`).
  **Stellen:** `app/ui/sculpt_bar.py`, `app/ui/pose_bar.py`, Formsitzung in
  `main_window.py:11504ff.`/`:11755ff.`, Analysekarten aus `app/core/perceive/`.
  **Abnahme:** Test: Kartenwahl in der Sitzung wechselt die Karte; ein Zug über den Bauraum hinaus
  meldet; Posieren mit Einschnürung zeigt die Zeile in der Leiste. Bauplan §2.2 (Weg 4), §18.9,
  §2.8.
  **Vorgabe Robert 02.10.2026 — allgemein:** dieselben Karten und Befunde in jeder Gestensitzung (Formen, Skelett); Abnahme an mindestens drei unterschiedlichen organischen Modellen aus `F:\3D Dateien`.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Beide Gestenleisten tragen in der
  zweiten Zeile dieselbe Kartenwahl (keine, Wandstärke, Überhang) mit `MapLegend`; die Analyse
  rechnet nach Ruhe im Hintergrund, ein Wechsel räumt den alten Wartehinweis ab, eine verspätete
  Antwort ändert die gewählte Karte nicht. Ein Zug über den Bauraum meldet sich in der Leiste; nach
  dem Skelett steht der Kernbefund, etwa `pose.pinched`, mit Kartenwahl und Schließen. Gegenproben
  für Bauraum, Abbruch, späte Antwort und Kartenwechsel grün, Formsitzung und Skelett mit 230
  Fällen. Am Fenster: Überhangkarte 0–90° mit Richtwert 45° und Herkunft „intern geschätzt“ an Weg
  4. Belege unter `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `sculpt-session.md`,
  `root-evidence.md`.

<a id="rm-395"></a>

- [~] **RM-395 — Nachbau: kleine Lücken beim Konstruieren ohne CAD.**
  Review 02.10.2026, Nachbau-Test (b), am HEAD `4449e3370`. Je Rest ein Test.
  - **Sperrgrund nur im Vorschauband:** Bei *Drehdeckel* („massiv“), *Profilklemme mit Einlagen*
    („Wählen Sie das Material …“) und *Verrunden* („Radius zu groß“) ist *Einsetzen* grau,
    `_refusal` im Dialog leer. Der Satz gehört auch in den Dialog. §2.7.
  - **Profilklemme ohne Materialvorgabe:** beide Materialfelder leer und sperrend; Vorgabe aus dem
    Projektmaterial. §2.4.
  - **Menü *Aus Skizze erzeugen …* zeichnet nicht:** öffnet *Grundform hochziehen* mit Rechteck
    40 × 20 × 10; gezeichnet wird erst über „Zeichnen …“. Der Eintrag soll die Zeichnung starten.
  - **Vereinigen deckt eine Bohrung still zu:** Steg über die halbe Bohrung Ø 9, nach *Vereinigen*
    ist das Merkmal weg, kein Satz. Hinweis „Bohrung ‹…› wurde verschlossen“. §17.3.
  - **„Richtung des Langlochs“ in Grad ohne Bezug:** welche Achse 0° ist, sagt weder Feld noch
    Kurzhilfe. §2.6.
  - **Skizzenursprung auf einer Fläche** liegt unsichtbar in deren Mitte; Ursprung im Zeichenmodus
    anzeigen. §30.1.
  Beleg: `F:\solidon-review-reports\nachbau\bericht.md` (Liste b) mit den dort genannten Läufen
  und Sonden.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `OperationDialog.show_refusal`
  zeigt den Grund bei den Feldern; leere Materialrollen übernehmen das Projektmaterial; *Aus Skizze
  erzeugen* startet über `launch_operation` sofort die Zeichnung; jede Zeichenebene trägt Nullring
  und 0. `union_objects` meldet `union.bore_filled`, `_partial`, `_blind`, `_enclosed` und
  `_unchecked` mit Ursprungskörper und Ort, gemessen an exakten bzw. verschweißten Differenzen
  (Cache 2). `slot_angle` sagt: „Dreht die Längsrichtung um die Bohrachse.“ 186 Boolean-, 4 Dialog-,
  12 Ursprungs-, 4 Fensterfälle grün; Teppichclip ganz gefüllt 0 mm³, halb 174,96/175,28 mm³
  (Netz/exakt), 16 Projekte. Belege unter `F:\solidon-review-reports\codex-2026-10-03\`:
  `bedienung\construction-ui.md`, `geometrie\geometrie\RM395.md`.

<a id="rm-396"></a>

- [~] **RM-396 — Grundkörper „an die gewählte Fläche ansetzen und verbinden“ in einem Schritt.**
  Umfangsentscheidung Robert 02.10.2026 („Alle“ auf die Vorschläge aus dem Nachbau-Test, Nr. 1).
  Im Nachbau kam in 8 von 12 Modellen ein zweiter Körper dazu; je 5–15 Klicks und 2–6 Zahlen ohne
  Bezug (Grundkörper anlegen, Weg ausrechnen, *Verschieben*, *Vereinigen*). Die Bausteine dafür
  gibt es (`sketch_join`, `app/core/sketch/ops.py:598`; `align_to_feature`,
  `app/core/geom/ops.py:1167`), aber nicht am Weg aus *Quader anlegen*.
  **Ablauf:** Ist eine Fläche gewählt, bietet der Grundkörper-Dialog vorn die Wahl *frei auf dem
  Bett* oder *an ‹Fläche› ansetzen* (bündig, mittig, *verbinden* an); Übernehmen legt Grundkörper,
  Ausrichtung und Vereinigung als **eine** Transaktion an (Regel 16 sinngemäß, §15.5). Ohne
  Flächenwahl unverändert auf dem Bett.
  **Stellen:** `app/core/geom/primitive_ops.py:294` (`create_box`), `:347` (`create_cylinder`)
  und Geschwister, Vorbelegung `app/ui/main_window.py:17254`/`:19575`, Dialog `app/ui/op_dialog.py`.
  Zusammen mit RM-390 umsetzen (dort die stille Vorbelegung abschaffen).
  **Abnahme:** Test: Quader, Seitenfläche gewählt, *Zylinder anlegen* mit *an Fläche ansetzen* →
  ein Körper, Zylinder bündig und mittig auf der Fläche, eine Transaktion, Strg+Z nimmt alles
  zurück. Bauplan §2.2 (Weg 2), §2.4, §2.6. Beleg: `F:\solidon-review-reports\nachbau\bericht.md` (c1).
  **Vorgabe Robert 02.10.2026 — allgemein, nicht für ein Modell:** Ansetzen gilt für jeden Grundkörper, jeden Baustein und jede gewählte Fläche (eben, schräg, gekrümmt über die Tangentialebene), an Netz und exaktem Kern. Nutzen: alle Teile aus mehreren Körpern — im Nachbau 8 von 12, in `F:\3D Dateien` nach Dateinamen geschätzt rund 60 Funktionsteile (Halter, Behälter, Verbinder, Adapter). Abnahme an mindestens drei unterschiedlichen Fällen aus `F:\3D Dateien` (etwa Rankenclip, Rohrschelle, Wandhalterung), nicht nur am Nachbau-Fall.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Kern: `surface_at_feature` liefert
  die Lage auf ebenen, schrägen und gekrümmten Originalflächen, `bound_surface_values` speichert
  Ziel, Anker und zwei Kantenabstände, `surface_seat` kennt `point_on_surface` und `centred`; der
  Arbeiter erhält mit `surface_object_for_worker` eine Kopie samt nativer Flächen. Erzeugen und
  `union_objects` sind eine Vorschau und eine Transaktion, *Verbinden* aus lässt zwei Körper. 433
  Kern-, 157 Fenster-, 7 Folgefälle grün. Am Fenster an `1x1-tray.stl`: Quader 8 × 12 × 20 an der
  Innenfläche, ein Körper mit 12,9 cm³, ein Undo nimmt alles samt drei Parametern zurück. Claude:
  `panels._line_for` hängt `obj_1` nicht mehr an. Belege unter
  `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `construction-ui.md`,
  `geometry-contracts.md`, `root-evidence.md`.

  **Teilstand 04.10.2026 (Claude, Zweig `claude/rm-druckvertrag-oberflaeche`, zusammengeführt in
  `b94f899e9`):** Die Berichtszeile des Umwandlungsbefunds hängte über `values["object"]` die
  Kennung der Ausgabe an („… wieder her. — obj_0“, Sonde `sonde-rm396-vorher.txt`).
  `panels._line_for` löst sie jetzt über die Körpernamen auf oder lässt sie weg; Test
  `test_the_conversion_note_names_no_identifier`, vorher rot. Commit `87d2cb69f`. Belege unter
  `F:\solidon-review-reports\claude-2026-10-04\druckvertrag-oberflaeche\`. Offen allein die
  Fensterabnahme beim Release (RM-213): `1x1-tray.stl` mit Quader *An Oberseite ansetzen* und
  *Verbinden* ohne „obj_…“ im Prüfbericht, danach 45°-Schräge eines Keils und eine
  Zylindermantelfläche, je mit Strg+Z, Speichern und Wiederöffnen. Changelog: nein — Ursprung
  `27c7a29e9`, in keinem Tag.

<a id="rm-397"></a>

- [~] **RM-397 — Assistent „Dose mit Schraubdeckel“.**
  Umfangsentscheidung Robert 02.10.2026 („Alle“, Nachbau-Vorschlag Nr. 2).
  Zwei der zwölf Nachbauten (Nozzle-Box, Gewürzset) sind genau das; heute kostet der Weg drei
  Operationen (*Zylinder anlegen*, *Aushöhlen*, *Drehdeckel erzeugen*), eine Sackgasse (RM-388)
  und eine Fehlwarnung (RM-393). Der Docstring von `screw_lid` (`app/core/geom/lid.py:1286ff.`,
  Beispiele um `:1309`) nennt genau diese Paare.
  **Ablauf:** Ein Eintrag *Dose mit Schraubdeckel …* fragt vorn Durchmesser, Höhe, Wandstärke;
  hinten Gewinde, Deckelhöhe, Streulöcher ja/nein. Übernehmen legt Dose, Hals, Deckel und Passung
  als eine Transaktion an; alle Maße als Projektparameter (§13), damit die Parameterleiste sie
  dreht.
  **Abnahme:** Test: Assistent mit Vorgaben → zwei Körper, dicht, Passung ohne Warnung, Spiel aus
  dem Materialprofil (Regel 7); Durchmesser in der Leiste ändern → Deckel folgt. Nach RM-388 und
  RM-393 umsetzen. Bauplan §2.2, §13, §25.
  **Vorgabe Robert 02.10.2026 — allgemein, nicht für ein Modell:** Aus dem Punkt wird ein parametrischer Assistent **„Behälter mit Deckel“**: Grundform rund oder eckig, Deckel als Schraub-, Steck- oder Klappdeckel, optional Fächer/Einsätze und Streulöcher, jede Größe im Bauraum; Gewinde- und Passungsmaße aus Normteiltabelle und Materialprofil, alle Hauptmaße als Projektparameter. Nutzen: in `F:\3D Dateien` nach Dateinamen rund 35 Dateien (Deckel rund/eckig, Gewürzset, Filterball, Wasserfall, Nozzle-Box, Kartusche, Mini-Pot, Taschentuchbox, Werkzeugbox). Abnahme an mindestens drei unterschiedlichen Behältern (rund mit Schraubdeckel, eckig mit Steckdeckel, mit Klappdeckel).

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `create_container` und
  `add_container_insert` (`geom/container_ops.py`) mit `lid_flow.plan_container` und
  `plan_container_edit`: benannte aktive Hauptmaße, Passung, fester Startwert und Kern in einer
  Transaktion; der Deckelwechsel im Verlauf führt Passung und Einsatz mit. Behoben: breite
  Schraubdeckel überschnitten den Hals (0,44 mm³ bei Ø 100), die Scharnierlasche drang in den
  Einsatz (119,9 mm³), `_swap_operations` verwarf Passungen, Plattformrauschen. 397 Kern-, 84
  Behälter-, 39 Fensterfälle grün, 24 Prüfprojekte. Am Fenster: rund mit Schraubdeckel 60→70 mm,
  Steckdeckel, Rechteck mit Fächern, Klappdeckel, Haltkarte bei Wand 40, Reload v8. Belege unter
  `F:\solidon-review-reports\codex-2026-10-03\`: `geometrie\geometrie\RM397.md`,
  `bedienung\root-evidence.md`.

  **Teilstand 04.10.2026 (Claude, Zweig `claude/rm-druckvertrag-oberflaeche`, zusammengeführt in
  `b94f899e9`):** Parametertab:
  `test_ui.py::test_parameter_tab_keeps_titles_and_details_inside_the_scroll_area` (bestehend,
  grün). Unveränderte Vorschau neu über den echten Weg aus Vorschauauftrag, Arbeiter und Band:
  `test_print_contract_ui.py::test_reopened_container_step_previews_unchanged_or_the_new_lid` —
  unverändert geöffnet „ändert sich nichts“ statt „Keine Vorschau“, mit Steckdeckel „Körperzahl: 2 →
  2“ und beide Außenmaße; das Dokument bleibt. Belege unter
  `F:\solidon-review-reports\claude-2026-10-04\druckvertrag-oberflaeche\`. Offen allein die
  Fensterabnahme beim Release (RM-213): Behälterschritt doppelklicken ohne Änderung und mit
  Steckdeckel, Wandstärke 3 → 40 über die Parameterleiste mit sichtbaren Beschriftungen. Changelog:
  nein.

<a id="rm-401"></a>

- [~] **RM-401 — Verschieben auf eine absolute Lage.**
  Umfangsentscheidung Robert 02.10.2026 („Alle“, Nachbau-Vorschlag Nr. 6).
  *Verschieben* (`translate_object`, `app/core/geom/ops.py:314`) geht nur relativ; für jeden
  Anbauteil rechnete der Kunde die Differenz aus der heutigen Lage (Modelle 2, 4, 6–10, je ein bis
  drei Zahlen ohne Bezug).
  **Ablauf:** Umschalter *um* / *nach*: bei *nach* stehen „Mitte bei X/Y“ und „Boden auf Z“ (bzw.
  Bezugspunkt wählbar) mit der aktuellen Lage vorbelegt; gespeichert wird der reproduzierbare
  Zielwert (Regel 2), alte Schritte bleiben relativ.
  **Abnahme:** Test: Körper per *nach* auf Mitte (0, 0), Boden 0 → Lage stimmt, auch nach einer
  Maßänderung davor; Strg+Z. Bauplan §2.4, §18.5.
  **Vorgabe Robert 02.10.2026 — allgemein, nicht für ein Modell:** Absolute Lage für jeden Körper, mehrere gewählte Körper und jeden Bezugspunkt (Mitte, Boden, Ecke, Merkmal); dieselbe Logik in *Drehen* und im Bewegungsgriff. Nutzen: jede Baugruppe — in `F:\3D Dateien` nach Dateinamen rund 40 Dateien aus mehreren Teilen (Screen-Cover, Gewürzset, Wasserfall, Organizer, Besteckkorb, Rinnensegmente). Abnahme an mindestens drei unterschiedlichen Baugruppen.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Kern: `SceneObject.frame` und
  `IDENTITY_FRAME`; `moved_object` führt den Rahmen mit der echten Matrix fort, Spiegelung und
  Skalierung bleiben sichtbar, Unbekanntes bleibt unbekannt; Kopien, Muster und beide Booleschen
  Kerne tragen ihn, Altprojekte rekonstruieren ihn aus dem Stack (456 Fälle, drei Altprojekte aus
  Format 6/18/41). Oberfläche: Verschieben und Drehen mit *um* und *nach*, absolute Ziele gelten
  auch nach vorgelagerten Maßänderungen, unklare Rahmen bieten nur relatives Drehen an;
  `translate_object` mit `minimum_inputs=1`. 115 Register-, 38 Leisten-, 35 Lagefälle grün. Belege
  unter `F:\solidon-review-reports\codex-2026-10-03\`: `bedienung\import-history-move.md`,
  `bedienung\import-history-native-matrix.md` (RM401), `geometrie\erkennung\bericht.md`.

<a id="rm-403"></a>

- [~] **RM-403 — Flächenbausteine frei auf der Fläche platzieren statt immer mittig.**
  Umfangsentscheidung Robert 02.10.2026 („Alle“, Nachbau-Vorschlag Nr. 8).
  Schlüsselloch und andere Flächenbausteine sitzen immer in der Flächenmitte; höher oder seitlich
  nur über Position X/Y/Z in Weltkoordinaten hinter *Weitere Einstellungen* (Nachbau Modell 1;
  Schlüsselloch `keyhole`, `app/core/knowledge/parts/mounting.py:584`).
  **Ablauf:** Beim Einsetzen an einer Fläche setzt der Klickpunkt die Lage; vorn stehen „Abstand
  zur oberen/linken Kante“ in Flächenkoordinaten, gespeichert reproduzierbar relativ zur Fläche
  (Regel 2); die Vorschau zeigt, ob der Baustein ganz auf der Fläche liegt (verbindet sich mit
  RM-392).
  **Abnahme:** Test: Schlüsselloch per Klick 10 mm unter der Oberkante → Lage stimmt, liegt ganz
  in der Fläche, nach einer Maßänderung der Fläche bleibt der Kantenabstand. Bauplan §2.6, §24.3.
  **Vorgabe Robert 02.10.2026 — allgemein, nicht für ein Modell:** Freie Lage für alle Bausteine an einer Fläche (Schlüsselloch, Einpressbuchse, Mutternfalle, Schraubloch, Wandhalter …) auf ebenen und einfach gekrümmten Flächen, Kantenabstände in Flächenkoordinaten. Nutzen: in `F:\3D Dateien` nach Dateinamen rund 25 Teile mit Befestigungen (Wandhalterungen, Lochwand, Filamenthalter M6, Screen-Cover). Abnahme an mindestens drei unterschiedlichen Bausteinen und Modellen.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `PlacementFlow._set_values`
  übernimmt `bound_surface_values` mit qualifiziertem Ziel, Anker und beiden Kantenabständen; eine
  Maßänderung ohne Geste bewahrt Ausdrücke, ein freier Zug oder eine eigene Weltkoordinate löst den
  Bezug. Wiederöffnen bindet über `bind_surface` am historischen Eingang dieselben Kanten. Kern:
  acht Maßänderungsfälle (Grundkörper und Magnettasche, beide Kerne und Güten) halten die
  Kantenabstände. Fenster: 18 Dialogfälle, drei Rundreisen mit Magnettasche, Schraubloch und
  Einpressbuchse samt Speichern, Undo/Redo und Wiederöffnen, 157 Platzierungs- und Dialogfälle grün.
  Das Schlüsselloch der Abnahme ist nicht eigens nachgestellt. Belege unter
  `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `construction-ui.md` (RM-403),
  `geometry-contracts.md`.

<a id="rm-502"></a>

- [~] **RM-502 — Dialog-Durchsicht vom 29.09.: spätere Korrekturen abnehmen und verbliebene Hinweisorte klären.**
  Die Restliste der Durchsicht vom 29.09.2026 (Commits `4d955a9e7`, `d80e1ce8e`, `e969f88ce`,
  `42253ae03`, `72281a33e`) wurde am 03.10. gegen Code und Historie von `187b5bbd3` geprüft.
  Ihre damaligen Fehler sind keine Aussage über den heutigen Stand. Die folgenden Stellen,
  Commits und Prüfwege ersetzen die Abhängigkeit von der örtlichen Sicherung.
  **Im Code bereits umgesetzt:**
  - **Einstellungen und Ersteinrichtung:** `88bb41ed8`, `c59ed62ca`, `97369c2f1`, `93018dd56`
    und `3fcd402a9` berücksichtigen verborgene Formulare und nachgereichten Inhalt über
    `style.expanded_width` und `ContentHeight`. Der alte Breitensprung 547 → 573 sowie die
    Querrollwerte 382/418 sind historische Befunde. RM-342 D-N5 ist im Archiv, ebenso die
    Inhaltsangabe eingeklappter Einstellungen unter RM-491.
  - **Druckeinstellungen:** `print_settings.GROUPS` führt Filament vor Temperaturen und
    Geschwindigkeit; `_update_inactive_setting_rows` blendet ausgeschaltete Stütz- und
    Haftungsdetails aus. `_build_head` hält Düsenstatus und Ablehnungen am Düsenfeld. Die Mitgabe
    steht bei den Übergabeknöpfen (`_build_state`); ihr verbliebener Fehlerhinweis steht unten.
  - **Neues Filament und Slicerfilamente:** `ba8c08b14` gleicht die Formulare über `align_forms`
    an und ersetzt den doppelten Datumstext durch eine benannte Löschtaste. Der Leertext in
    `filament_picker.SlicerFilamentDialog._refill` unterscheidet fehlenden Bestand vom Filter.
    `tests/test_filament_picker.py::test_spool_form_columns_align_and_unknown_dates_have_one_label`
    sichert die Spalten und Datumsfelder; die Lage der Prüfzeile bleibt gesondert zu klären.
  - **Chat, ComfyUI, Lager und Erststart:** Seit `ba8c08b14` enthält
    `dialogs.KeyDialog._cloud_model_section` Schlüsselzustand und Löschen; ComfyUIs Ordnerwahl
    und Eingabe stoßen `_refresh_folder_state` bzw. `_folder_edited` an. Die Warnschwelle steht
    außerhalb der Lagerklappe, `reverse_hint` direkt unter der Rücknahme. Der Namenshinweis
    steht unter `FirstRunDialog.printer_name`. Befehlspalette und Ausdrucksdialog wurden in
    derselben Dialogreihe nachgezogen (`tests/test_dialog_layout_regressions.py`).
  - **Raster:** `ba8c08b14`, `a5e698c78` und `9b84722ad` setzen Abstände aus `style.py` an den
    bearbeiteten Formularen und Knopfleisten. Die alten Zahlen 6/11 belegen keinen verbliebenen
    Fehler an diesen Stellen; Abweichungen erst am aktuellen Fenster benennen.
  **Offen:**
  - **Fensterabnahme des späteren Stands:** Der nachgelesene
    [CI-Lauf 37086153737](https://github.com/RS-Digital-Studio/Solidon/actions/runs/37086153737)
    am Stand `4c172d8ee` meldet im Windows-Fensterjob für
    `tests/test_first_run_setup.py::test_custom_printer_natural_width_and_manual_height_survive_toggling`
    `[fdm-fr]` und `[resin-fr]` jeweils `assert 42 == 0`; beide italienischen Fälle bestehen.
    Dieser Lauf enthält `93018dd56` noch nicht. Die spätere Rechnung in sechs Sprachen und
    FDM/Resin beim Release auf allen Plattformen abnehmen; auf ausreichend breitem Bildschirm
    kein Querrollen, auf schmalem höchstens der abgeschnittene Teil der natürlichen Breite.
    Die übrigen bearbeiteten Dialoge mit ihren vorhandenen Fensterfällen und Bildern abnehmen.
    Paketfreigabe und Laufzeitwechsel bleiben unter RM-468.
  - **Prüfzeile der Spule:** `filament_picker.NewFilamentDialog` setzt `validation` weiter im
    äußeren Layout über die Knöpfe; der oben genannte Test verlangt genau diesen festen Ort.
    Den alten Wunsch nach Feldnähe am gezeigten Dialog mit ungültigem Datum nachstellen und
    gegen die Erreichbarkeit bei kleiner Höhe entscheiden. Einen feststehenden Fehlerhinweis
    nicht allein wegen des alten Listenwortlauts in den Rollbereich verschieben.
  - **Hinweis zur Mitgabe:** `PrintSettingsDialog._share_toggled` schreibt einen Speicherfehler
    noch in `self.state`. Bei fehlenden Schreibrechten die Zuordnung zu „Werte mitgeben“ im
    gezeigten Dialog prüfen und den Hinweis, falls nötig, direkt am Schalter platzieren.
  **Abnahme:** je verbliebenem Fall ein nachvollziehbarer Prüfweg und beim Release ein Bild am
  echten Fenster; die bestehenden Fälle in `test_first_run_setup.py`,
  `test_dialog_layout_regressions.py`, `test_print_settings_ui.py`, `test_filament_picker.py`,
  `test_filament_inventory_ui.py`, `test_chat_ui.py` und `test_generate_ui.py` grün. Diese
  Registerpflege führt keine Fensterprüfung aus und behauptet keine neue Abnahme. Bauplan §2, §2.7.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):**
  `PrintSettingsDialog._share_toggled` schreibt einen Speicherfehler direkt unter *Werte mitgeben*
  samt zugänglicher Beschreibung, ein erfolgreicher Versuch löscht ihn, der Slicerstatus bleibt
  getrennt. Der feste Prüfhinweis der Spule bleibt auch bei halber Höhe erreichbar;
  `NewFilamentDialog.focus_field` rollte beim ersten Aufruf mit alten Layoutmaßen und folgt jetzt
  dem Layout (sechs Sprachen, 7 Fälle). Sieben Dialogdateien je in eigenem Prozess: 54, 31, 321, 89,
  71, 83 und 97 Fälle grün. Am Fenster: Spule von Hand anlegen, fehlende Währung sperrt, Hinweis
  über den Knöpfen, Abbrechen lässt das Lager leer. Offen am Fenster: Ziffern-Tastaturweg, Rückweg
  „Unbekannt“, Speicherfehler, kleines Spulenfenster. Belege unter
  `F:\solidon-review-reports\codex-2026-10-03\bedienung\`: `root-evidence.md`,
  `import-history-move.md` (RM-502).

  **Teilstand 04.10.2026 (Claude, Zweig `claude/rm-druckvertrag-oberflaeche`, zusammengeführt in
  `b94f899e9`):** `tests/test_date_field.py` 18 Fälle über den echten `NewFilamentDialog` bis in
  seinen Eintrag, je Sprache: zwei Ziffern je Abschnitt in der Reihenfolge des Sprachformats ergeben
  das ISO-Datum, einzelne Ziffern mit Trennzeichen ebenso, *Unbekannt* setzt zurück und danach tippt
  es sich neu. Speicherfehler an *Werte mitgeben*:
  `test_print_settings_ui.py::test_share_failure_stays_with_the_choice_and_a_successful_retry_clears_it`;
  kleines Spulenfenster:
  `test_filament_picker.py::test_spool_validation_stays_reachable_above_the_buttons_when_short`
  (sechs Sprachen). Kein Fehler gefunden. Commit `25a9484f7`. Belege unter
  `F:\solidon-review-reports\claude-2026-10-04\druckvertrag-oberflaeche\`. Offen allein die
  Fensterabnahme beim Release (RM-213): Kaufdatum „05092026“ tippen und *Unbekannt*, Spulenfenster
  auf halber Höhe, *Werte mitgeben* mit schreibgeschütztem Nutzerordner. Changelog: nein.

## KI und Generatoren

<a id="rm-003"></a>

- [ ] **RM-003 — Lizenzkette der gepinnten TripoSG-Bestandteile klären.** Die LICENSE-/NOTICE-Kette
  des konkret eingesetzten TripoSG-Modellstands vollständig dokumentieren und die im NOTICE
  genannten HunyuanDiT-/FlashVDM-Bedingungen gezielt fachlich beziehungsweise mit VAST klären.
  Git-Commit, TripoSG-Gewichte und BiRefNet-Revision sind bereits gepinnt; LICENSE und NOTICE werden
  übernommen. Seit dem 21.09.2026 holt die Einrichtung auf Wunsch auch das Bildmodell für den
  Weg aus Text (`sd_xl_base_1.0.safetensors`, Revision `46216598`, CreativeML Open RAIL++-M von
  Stability AI; die Nutzungsausschlüsse des Anhangs gelten dem Nutzer, das Handbuch nennt sie) —
  es gehört mit in dieselbe Kanzleifrage. Abnahme: nachvollziehbare Zuordnung jedes eingesetzten
  Bestandteils zu Revision, Lizenz und geklärten Bedingungen. Der bestehende Weg bleibt erhalten.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#p9--säule-b-und-farbe).

  **Stand laut Register bis 29.09.2026:** Lizenzkette der eingesetzten Modellrevisionen klären;
  die Startseite sagt seit `9145aedc` wie die KI-Seite, dass Solidon TripoSG und SDXL auf Wunsch
  einrichtet und die Kette geprüft wird, die README ‚wird derzeit geprüft‘ statt ‚MIT, Quelltext
  wie Gewichte‘ (Robert, 23.09.2026)
  Registerabgleich 02.10.: offen und stimmig; Beifund: der Kommentar in `licences.toml:50` sagt weiter ohne Vorbehalt „TripoSG MIT“.

<a id="rm-004"></a>

- [ ] **RM-004 — Echte Text- und Bildgenerierung über alle Zielplattformen abnehmen.** Den
  tatsächlichen Text- und Bildweg mit der dokumentierten Generatorenkette auf Windows, macOS und
  Linux belegen: Erzeugen, automatische Reparatur, Prüfbericht, Speichern/Wiederöffnen und Export.
  `tests/test_way_three.py` deckt den Anwendungsweg bereits mit einem geskripteten Generator.
  Abnahme: dokumentierter realer Lauf beider Eingangswege je Plattform mit festgehaltenen
  Modellrevisionen und verwendbaren Exportdateien. Die Lizenzkettenklärung bleibt in RM-003;
  bestehende Generatoren und Medien bleiben erhalten.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#p9--säule-b-und-farbe).

<a id="rm-014"></a>

- [~] **RM-014 — Zusätzliche Formenregel und zugehörige Suite-Abnahme entscheiden.** Entscheiden, ob
  zusätzlich zur bestehenden Sperre für geratene Skizzen, Pinselzüge und Skelettdaten eine
  erklärende Agentenregel gebraucht wird. Abnahme: Entscheidung dokumentiert; bei einer
  Regeländerung Sammlungsversion sowie vergleichbare Agenten-Suite-Läufe davor und danach. Weg 4,
  Beispiel, Handbuch und Website sind bereits umgesetzt.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#p16--organische-modellierung).

<a id="rm-251"></a>

- [ ] **RM-251 — Mehrteilige Aufträge enden lokal am Schrittlimit.** Gefunden am
  26.09.2026 beim Suitevergleich (RM-016): Mit Werkzeugangebot endet qwen3:14b in
  zehn von 39 Fällen bei `MAX_STEPS` = 8 (which_hole, join_what, magnet_lid,
  wall_holder, cable_exit, spacer, snap_box, dowels, inserts, free_shape), mit
  vollem Werkzeugsatz und Fenster 40 960 in keinem — dort höchstens vier
  Schritte. Der Unterschied liegt nicht an den Nachforderungen (0 bis 1 je
  Fall), sondern an der Bündelung: Mit vollem Satz ruft das Modell mehrere
  Werkzeuge in einem Schritt (magnet_lid neun Aufrufe in vier Schritten), mit
  Angebot meist eines je Schritt. Das erklärt die zwei Fälle, die das Angebot
  gegen den vollen Satz verliert (22 gegen 24). Zwei Hebel, beide zu messen:
  **(a)** ein eigenes Schrittlimit für den lokalen Weg — §26.5 nennt das
  Iterationslimit hart, lokal kostet ein Schritt kein Geld, aber 15 bis 20
  Sekunden; eine Entscheidung Roberts. **(b)** ein Satz im Prompt, der
  gebündelte Aufrufe nahelegt; `_OFFER_HINT` sagt heute „im nächsten Schritt …
  danach rufst du es mit Werten auf" und legt damit das Nacheinander nahe.
  Abnahme: Suite mit qwen3:14b vorher und nachher auf freier Karte, keine
  Verschlechterung der Quote, weniger Fälle am Limit. Rohdaten:
  `.claude/.state/lokale-ki-2026-09-25/messung/`.

  **Durchsicht v0.5.1 (26.09.2026, ki):** (a) gemessen mit qwen3:14b, Schnappschuss
  `aeb562ede`, unter Last: Schrittgrenze 12 löst 23 von 39 gegen 22 im Endstand,
  mehrteilig 4 gegen 2 von 10, am Limit 8 statt 10 Fälle, dafür hängen hinge und stiffen
  an 12 — im Rauschen, keine Verschlechterung. (b) nicht gemessen. magnet_lid endet
  nicht am Bündeln, sondern an `pattern_feature`, das die eigene Magnettasche am exakten
  Körper ablehnt. Die Rohdaten dieses Suitelaufs sind nicht versioniert. Entscheidung
  Robert: Grenze 12 für den lokalen Weg ja/nein.

  **Nachtrag (27.09.2026, bohrung, BOHRUNG-13):** Eine Magnettasche aus dem Baustein lässt
  sich jetzt an beiden Kernen vervielfachen, verdoppeln, versetzen und entfernen, samt
  Haltelippe (`51c17b7a6`) — der Grund, an dem magnet_lid endete, ist weg. Die Suite ist
  danach nicht neu gefahren; die Zahlen oben gelten für den Stand davor.

  **(a) entschieden und gebaut (02.10.2026, Claude, Thread „Bedienung und KI“):** Robert
  hat die Vorschläge freigegeben („alles ja“). Ein Zug mit einem lokalen Modell
  (`OllamaBackend`) hat 12 Schritte, gehostet bleibt es bei 8 (`agent/session.py`,
  `MAX_STEPS_LOCAL`, `steps_for`; eine ausdrücklich gesetzte Grenze gilt weiter). Test
  `test_agent.py::test_a_local_model_gets_twelve_steps_and_a_hosted_one_eight`. Offen bleibt
  (b); er ändert den Prompt und wird erst mit Suite vorher und nachher gebaut.

<a id="rm-016"></a>

- [ ] **RM-016 — Agenten-Suite gegen das aktuelle Vorgabemodell messen.** Die Agenten-Suite gegen
  das tatsächlich konfigurierte Vorgabemodell auf einer festgehaltenen Regelversion messen und mit
  einem vergleichbaren Referenzlauf bewerten. Abnahme: Fallresultate, Modellkennung, Regelversion
  und Quote sind belegt; mehrschrittige Werkzeugaufrufe berücksichtigen den Umgang mit
  Thinking-Blöcken. Die Behandlung von Modellablehnungen ist bereits gebaut.

  **Lokal abgeschlossen am 26.09.2026** — Prompt-Version 8, Regelsammlung
  unverändert, RTX 4080 mit freier Karte (Belegung je Fall im Rohdatensatz),
  Ollama 0.34.3, `num_ctx` 32 768 außer wo genannt:

  | Stand | Modell | gut | gefragt | schemagültig | Baustein | Zeit |
  |---|---|---|---|---|---|---|
  | ohne Angebot (`75aaf46e`) | qwen3:14b | 14 | 1/3 | 76 % | 3/13 | 46 min, 9 Fensterabbrüche |
  | ohne Angebot, Fenster 40 960 | qwen3:14b | 24 | 2/3 | 83 % | 5/13 | 149 min, 10 % auf dem Prozessor |
  | mit Angebot (`a00f5053`) | qwen3:14b | 24 | 2/3 | 82 % | 5/13 | 44 min |
  | dazu Zwilling als Kurzform (`2c34c2a7`) | qwen3:14b | 22 | 2/3 | 81 % | 3/13 | 47 min |
  | dazu Zwilling als Kurzform | qwen3.5:9b | 21 | 1/3 | 88 % | 4/13 | 15 min |
  | dazu Zwilling als Kurzform | gpt-oss:20b | 10 | 2/3 | 88 % | 0/13 | 21 min, zweimal an der Antwortgrenze, keine Kurzform angefordert |

  Das Vorgabemodell bleibt qwen3:14b. Die Wo-Fälle verlangten bis 7064a646 das
  Wort „Menü“, das es für Aushöhlen und Bohrung ändern seit dem 11.09. nicht
  mehr gibt, und neun Bausteinfälle den Netz-Quader, den das Menü seit P2.8
  nicht mehr anbietet; alle Zahlen oben sind mit der Bewertung aus a989a099
  gezählt (ein Zwilling ist dieselbe Handlung, Wo-Fälle mit „Handlungen“).
  Zwei Läufe desselben Stands kippten bis zu sieben Fälle in jede Richtung. Zehn Fälle
  enden mit Angebot am Schrittlimit, ohne keiner — das ist der nächste Hebel
  (RM-251), kein Messfehler. **Offen bleibt der gehostete Vorgabeweg:**
  ein kostenpflichtiger Lauf, nur mit Roberts Freigabe. Werkzeuge und Rohdaten:
  `.claude/.state/lokale-ki-2026-09-25/`.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-konzepte-nachrecherchiert-19082026).
  Registerabgleich 02.10.: Statuszeichen wäre nach der Legende `[~]`.

<a id="rm-441"></a>

- [ ] **RM-441 — Reste aus RM-372 und RM-374: `hollow.done` ohne Knopf, Beispielprojekt mit alten Transaktionen.**
  Fund 02.10.2026 beim Abschluss von RM-372/RM-374 (Claude). (a) Der Befund `hollow.done`
  (`app/core/geom/hollow.py`) meint einen änderbaren Schritt und trägt noch nicht
  *Diesen Schritt ändern* — Vorgabe Robert zu RM-374, ausgelassen, weil `hollow.py` bei Codex
  offen lag; danach `MEINT_DEN_SCHRITT` in `tests/test_finding_ways.py` nachziehen.
  (b) `weg3-generiert-aufbereiten.p3d` trägt noch die früheren getrennten Transaktionen; beim
  Release mit `tools/make_examples.py` neu erzeugen. **Abnahme:** Test für (a); (b) im
  Release-Lauf. Bauplan §2.7, §15.5.
  Review 02.10. (`73d83b55b`, RM-374 archiviert mit `9983e9923`): Die Vorgabe „jeder Befund, der einen änderbaren Schritt meint, bekommt den Knopf“ ist nicht erfüllt — ohne Knopf bleiben `mesh.already_below_target` (`app/core/geom/mesh_ops.py:2219`, im Fenster geprüft), `rotate_feature.unchanged`, `resize_feature.unchanged`, `move_feature.unchanged`, `{operation}.unchanged` (`prepare_ops.py`) und `bore.resize_unchanged` (`prepare.py`, `prepare_ops.py`); dieser Punkt nennt bisher nur `hollow.done`. Beleg `F:\solidon-review-reports\verif-73d83b55b-claude.md`.
  **Stand 02.10.2026 abends:** (a) erledigt (Claude, Thread „Bedienung und KI“): Beide `hollow.done` tragen *Diesen Schritt ändern* mit `field: wall`, `MEINT_DEN_SCHRITT` nennt sie. Offen (b).

## Tests und Entwicklungswerkzeuge

<a id="ci-testlaufzeiten"></a>

- [~] **CI-Testlaufzeiten — vollständige Prüfungen früher abschließen.**
  Verbindliches [Konzept](konzepte/konzept-ci-testlaufzeiten-2026-09.md), vor
  Umsetzung erstellt: CI-01 bis CI-08 schützen Auswahl, Prozessisolation,
  Plattformumfang, Paketfreigabe und Berichte. Umsetzung: unabhängige Kern- und
  Fensterjobs, Versionswächter als Handstart-Opt-in, gebündelte Quellprüfungen
  und Bausteinvorbereitung sowie thematische UI-Tests. Durchsicht 24.09.2026:
  Kernsuite in drei Teilen je Plattform (`--ci-shard`, `tools/ci_shards.py`,
  Kerntabelle aus einem lokalen JUnit-Lauf), drei Windows-Fenstergruppen,
  Prüfausgabe wieder im CI-Protokoll und Schrittbericht, und der längste
  Kernfall behoben: `test_seal_geometry[12.0]` 319 s → 24–34 s über die
  räumliche Vorauswahl der Wandmessung (Konzept §4.4). Fensterabnahme,
  gemessener CI-Zeitgewinn und die erste Kerntabelle aus CI-Berichten
  (`tools/ci_shards.py core …`) bleiben dem nächsten Release vorbehalten —
  ebenso die erste erzeugte Fenstertabelle: Die heutige stammt aus den
  Protokollzeilen des Ausgangslaufs und gewichtet `test_ui.py` noch mit den
  665 s von vor seiner Aufteilung. Offen außerdem: ein echter räumlicher
  Index für die Wandmessung an Vollkörpern (die Vorauswahl kostet dort bis
  etwa die Hälfte mehr als der Vollvergleich, `geom/CLAUDE.md`) und das
  Blättern in `tools/windows_signed_installer.py`, bevor ein Lauf 100
  Artefakte erreicht (heute rund 45). Nächste Kandidaten nach Dauer:
  `test_bore_mouth_resize` und `test_bore_floor_resize` mit je einem Fall
  über 75 s, `test_pattern_features` mit 249 s über 115 Fälle.

  **Durchsicht v0.5.1 (26.09.2026, werkzeuge):** Der räumliche Index steht — ein Baum
  aus Hüllquadern in `mesh.ray_hits_batch`, bitgleich zum Vollvergleich, Vollkugel mit
  12 800 Dreiecken 31 → 0,5 s (`7e3442623`). Die beiden langsamsten Kernfälle liefen
  über doppelte Mantelpunkte in `features._distinct_points` (134 Mio. Punktpaare):
  `test_bore_mouth_resize…` 83,2 → 28,4 s, `test_bore_floor_resize…` 61,4 → 26,3 s
  (`68cd2ef6f`). Das lokale Tor verteilt wie die CI mit `--dist worksteal`, 850 → 587 s
  im Median, dieselben 17 166 Fälle (`c28e02c86`). CI-01 bis CI-07 sind im Code und an
  der echten Sammlung erfüllt (die drei Kernteile sammeln zusammen 17 191 Fälle, keiner
  doppelt, keine Datei in zwei Teilen).

  **Releaselauf 0.5.1:** Der erfolgreiche
  [Taglauf 36454861126](https://github.com/RS-Digital-Studio/Solidon/actions/runs/36454861126)
  vom 28.09.2026 enthält die neue Aufteilung: neun Kernjobs auf drei Plattformen,
  drei plattformübergreifende Fensterverträge und drei Windows-Fenstergruppen.
  Letztere liefen 18:36, 17:59 und 18:32 Minuten (Gruppen 0, 1, 2).
  **CI-08 bleibt offen:** Den Gewinn gegenüber einem vergleichbaren Ausgangslauf
  anhand der Testbestände, Berichte und Laufzeiten auswerten; ein grüner Lauf allein
  belegt ihn nicht. Offen bleibt das Blättern in `tools/windows_signed_installer.py`.

<a id="rm-020"></a>

- [ ] **RM-020 — Sicherung der eigenständigen Druckprojekte belegen.** Den Sicherungsweg für das
  eigenständige Repository 3D Drucker festlegen und belegen. Es hat weiterhin kein Git-Remote; ob
  eine andere Sicherung existiert, ist hier nicht nachgewiesen. Abnahme: Robert entscheidet über
  Remote oder anderen Sicherungsweg, und eine Wiederherstellungsprobe bestätigt den gesicherten
  Stand. Einen externen Upload erst aus dieser Entscheidung ableiten.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#vier-wege-von-hand-während-die-suite-grün-war-23082026).
  Registerabgleich 02.10.: Das Druckprojekt-Repository liegt unter `F:\3D Dateien\3D Drucker` (HEAD `8bce3d8`, ohne Remote); die OneDrive-Kopie ist älter (HEAD `47321dd`, 29.08.) und weicht ab, ist also keine Sicherung.
  Robert 02.10.2026: Das Repository in der OneDrive-Kopie wird nicht benutzt und bleibt, wie es ist. Als Sicherung zählt es damit nicht; RM-020 braucht eine eigene Sicherung von `F:\3D Dateien\3D Drucker`.

<a id="rm-099"></a>

- [~] **RM-099 — Konzeptbestand und veraltete Verweise ordnen.** **Die Hälfte der Abnahme ist
  erreicht** (nachgezählt 10.09.2026): `konzepte/README.md` führt 45 Verweise, und **keiner**
  geht ins Leere; der Mengenvergleich gegen `konzepte/*.md` ergibt in beide Richtungen keine
  Differenz — kein Dokument fehlt in der Tabelle, kein Eintrag ohne Datei. Auch der einzige
  Konzeptverweis aus `ROADMAP.md` löst auf. „Alle Verweise gültig" ist damit eingelöst und
  gehört nicht mehr beauftragt.

  Offen bleibt das **Umräumen**: Als überholt gekennzeichnet sind genau zwei Konzepte; einen
  Ordner `konzepte/archiv/` gibt es nicht, eine eigene Notiz zur Weg-3-Lizenzentscheidung auch
  nicht (sie steht nur als Fließtext in sechs Konzepten), und die beiden Bedienkonzepte unter
  `.claude/` sind unarchiviert. Wie viel davon Robert archiviert haben will, ist eine
  Entscheidung und keine Fleißarbeit — historische Begründungen bleiben in jedem Fall erhalten.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).
  Registerabgleich 02.10.: `konzepte/README.md` führt 62 statt 45 Verweise, alle lösen auf; ROADMAP.md verlinkt 18 Konzeptziele, nicht eines.

<a id="rm-103"></a>

- [ ] **RM-103 — Große Kernfunktionen nach konkretem Wartungsbedarf aufteilen.** Die großen
  Kernfunktionen anhand ihres heutigen Aufbaus priorisieren; zuerst die Verantwortlichkeiten der
  Auswertung prüfen. Nur begründete Aufteilungen durchführen. Abnahme: gleiche Geometrie, IDs,
  Befunde und Laufzeit vor/nach dem Umbau sowie die vier Hauptwege; alte Zeilenzahlen nicht als
  aktuellen Befund weiterführen.

  **Gemessen am 13.09.2026**, damit die Größenordnung nicht aus einer alten Notiz kommt:
  `evaluate` hat 571 Zeilen, `_with_features` 607. Gegen die Archivstände (521/580 und 472/520)
  sind beide gewachsen, gegen die Messung vom 10.09.2026 (597/596) hat sich die Last zwischen
  ihnen verschoben. Das begründet die Aufteilung nicht von selbst, es sagt nur, dass der Punkt
  nicht kleiner wird, während er wartet.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#architektur-durchsicht-02092026).
  Registerabgleich 02.10.: Zahlen veraltet — `evaluate` ist eine Hülle mit 46 Zeilen, `_evaluate` hat 934, `_with_features` 1185 Zeilen (Eintrag: 571/607).

<a id="rm-113"></a>

- [ ] **RM-113 — Besitzerprüfung der Tokendatei auf dem Windows-Runner belegen.** Den Besitzer einer
  frisch angelegten privaten Tokendatei auf dem Windows-Runner ermitteln und die Prüfung mit einer
  tatsächlich nutzereigenen Datei fahren. Abnahme: SID und ACL dokumentiert, Test ohne bedingten
  Skip grün; eine breitere Besitzfreigabe nur nach Sicherheitsprüfung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).
  Registerabgleich 02.10.: Der Skip-Grund mit der Runner-SID ist nicht belegt; Statuszeichen wäre `[~]`.

<a id="rm-134"></a>

- [ ] **RM-134 — Zusammenführung duplizierter Testhilfen entscheiden.** Roberts Entscheidung zum
  Umfang der Zusammenführung einholen (genehmight, alles gründlich). Belegt sind doppelte Freiformhilfen für Kegel/Torus und
  Bohrungswand-Klickhilfen; die historische Zahl von 21 Gruppen ist kein aktueller Messwert. Bei
  Freigabe gemeinsame Verträge klären und die betroffenen Hilfen an einem Pflegeort führen. Abnahme:
  gleiche fachliche Testfälle ohne doppelte Pflege; eine vollständige Testdurchsicht bleibt eine
  eigene Umfangsentscheidung.

  **Der aktuelle Messwert** (`tools/twin_scan.py tests --frage 2 --frage 3`, 14.09.2026, 272 Dateien,
  11 421 Funktionen): **28 wortgleiche Gruppen** ab drei Anweisungen, davon 13 über Dateien hinweg
  und 15 innerhalb einer Datei; dazu 11 strukturgleiche ab fünf. Groß sind sechs: `window`
  (`test_header`/`test_overlay`, 9 Anweisungen), `with_a_body` (`test_pose_session`/
  `test_sculpt_session`, 8), `project` (`test_agent`, `test_agent_suite`, `test_licence_boundary`,
  `test_parts`, 5), `on_the_bore_wall` (`test_analysis_ui`/`test_selection`, 5), `_placed`
  (`test_cone_fit_quality`/`test_torus_fit_quality`, 5) und `counted` (fünf Dateien, 3). Der Rest
  sind Drei- und Vierzeiler, die ein gemeinsamer Ort nicht kürzer machte. Entscheidung: die sechs
  nach `tests/helpers/` (oder `conftest.py`-Fixtures) — oder nichts, weil jede Datei für sich
  lesbar bleiben soll.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#doppelte-stellen-und-zwillinge-gemessen-07092026).
  Registerabgleich 02.10.: teilweise erledigt — `window` und `with_a_body` liegen seit `95fd36d35` in `tests/ui_helpers.py`; offen bleiben `on_the_bore_wall`, `project`, `counted`, `FakeCodec`, `a_foreign_slot`. Statuszeichen wäre `[~]`.

<a id="rm-137"></a>

- [ ] **RM-137 — Sitzungsende im tatsächlichen Editorbetrieb abnehmen.** Das tatsächliche SessionEnd
  beim Ende einer echten Editor-Sitzung beobachten und die Freigabe des Sitzungsgebiets belegen.
  Abnahme: sichtbarer echter Sitzungsablauf samt wirksamem Benutzer-PATH nach Neustart; eine
  konfigurierte Terminal-Statuszeile nicht als Desktop-Darstellungsnachweis behandeln.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#zwei-werkzeuge-zwei-wahrheiten-08092026).
  Registerabgleich 02.10. (Stand `4449e3370`): gegenstandslos — den SessionEnd-Hook gibt es nicht mehr; `22a2d6e29` (09.09., Robert: „alles raus, was mit mehreren Sitzungen zu tun hat“) hat ihn samt Sitzungsbrett entfernt. Als entfallen ins Archiv. Beleg `F:\solidon-review-reports\register-rest.md`.

<a id="rm-234"></a>

- [~] **RM-234 — Linux-Fensterabnahme und macOS-Gegenprobe nachweisen.**
  **Historischer Befund bei RM-186** (Durchsicht 0.5.0, erkennung): Die Fensterdateien
  laufen seit dem 08.09.2026 nur auf Windows und nur beim Release; der einzige
  Ubuntu-Job, der sie fährt („Neueste Versionen", nur `schedule` und
  `workflow_dispatch`), brach am 14.09. vor den Tests ab und blieb am 22.09. an
  den Kerntests hängen („8 failed"). Wegen `set -euo pipefail` kommt er bei
  einem roten Kernschritt nie an die Fensterdateien. Ein Befund aus einer
  Fensterdatei kann damit auf Linux nie gemessen sein — daran hing RM-186. Dazu
  die offene Gegenprobe auf macOS: Lauf 35775952291 schlug in
  `test_prepare.py::test_a_widened_countersink_over_the_edge_says_so` fehl,
  vermutlich der mit `9307a844` behobene Fall. Weg: Kern- und Fensterschritt im
  Job getrennt laufen lassen und beide Ergebnisse melden; Zusagen, die auf allen
  Plattformen gelten sollen, als Kerntest (wie der neue RM-186-Test).

  **Nachweis vom 24.09.2026:** Im Lauf `35952849083` besteht der gepinnte
  Ubuntu-Releasejob `107485122706` die Kernsammlung, 210 Fensterverträge
  (16 abgewählt) und den Renderer-Schritt. „Neueste Versionen" ist heute ausdrücklich
  auf die Kernsammlung begrenzt und enthält keinen Fensterschritt; dessen früher
  geforderte Erreichbarkeit dort passt nicht mehr zum Workflow. Der neue macOS-Kernjob
  `107485122874` bricht beim Poolhalter durch einen nativen Workerabbruch ab,
  nicht mit einer Assertion des genannten Senkungstests. **Offen bleiben** die
  unabhängige Ergebnismeldung der Fensterverträge auch bei rotem Kernschritt und
  ein vollständig grüner macOS-Lauf mit dem Senkungstest. **Nachtrag 24.09.:** Der tatsächliche
  Taglauf `35982366247` besteht auch auf macOS mit 16.947 Kerntests, 210 Fensterverträgen
  und drei Renderertests. Der vorherige native GEOS-Absturz ist behoben (`fb53de3c`).
  Die unabhängige Ergebnismeldung bei rotem Kern bleibt als eigener Rest offen. Kein Gesamtabschluss
  aus dem grünen Ubuntu-Kern allein. Belege und Grenzen:
  `konzepte/nachweise-release-0.5.0/reports/codex-ci-35952849083-unix-packages.md`.

  **Durchsicht v0.5.1 (26.09.2026, werkzeuge):** Der Rest ist im Workflow gebaut:
  `window-contracts` ist seit `0a0e4eef0` ein eigener Job ohne `needs`, ein roter
  Kernteil hält ihn nicht an, und `78e151e85` schreibt Sammel- und Fensterfehler ins
  Protokoll. Offen ist allein der Nachweis an einem echten Lauf, in dem der Kern rot und
  die Fensterverträge trotzdem gemeldet sind.

<a id="rm-272"></a>

- [ ] **RM-272 — Die Entwicklungsmaschine rechnet zeitweise falsch.** Aus der Durchsicht
  v0.5.1 (ast-flake). `test_language_rules` fiel sporadisch mit Fehlern, die reiner
  Python-Code nicht erzeugen kann: `node._fields` liefert ein `Load`, ein Tupeliterator
  ist ein `str`, dazu Zugriffsverletzungen, einmal im C-Parser. Gemessen, je Lauf ein
  Prozess: am 27.09.2026 zwischen 02:34 und 03:04 19 von 147 Läufen rot — mit, ohne und
  mit leer geschalteter `conftest`, auch ohne jede fremde native Bibliothek im Prozess —,
  danach 120 Läufe ohne Fehler bei gleichem Code; `PYTHONMALLOC=debug` zeigte keine
  Heap-Spur. Ursache nach Ausschluss: der Prozessor (Intel Core i9-13900K, Raptor Lake,
  Microcode 0x133, Intels „Vmin Shift Instability“). Dieselbe Familie wie die
  nativen Abrisse vom 07.08.2026 und der AST-Lauf, der im Tor riss, dazu Windows-Absturzprotokolle vom 23. und 24.09.2026
  mit verfälschten Befehlszeigern. Zwei Beobachtungen derselben Durchsicht haben dasselbe
  Bild und ließen sich isoliert nicht nachstellen: ein `NameError: name 'type' is not
  defined` in `perceive/local._plain` (RESTVORSCHAU-08) und Zugriffsverletzungen beim
  Laden des Gartenschlauchhalters in `threemf._native_tools_of` (drei von rund zwanzig
  Sondenprozessen in rest-bohrung, einer von 19 in rest-erkennung2). In der dritten Runde
  ein weiterer Einzelfall: Ein Korpuslauf der Nahtsuche am Laptop-Ständer (rest-teilen)
  endete nach 27 s mit Exit 139 ohne Ausgabe; fünf Wiederholungen mit `-X faulthandler`
  und drei Paare im Wechsel liefen sauber und mit derselben Teilung. Kunden trifft es
  nicht, außer auf ebenso geschädigten Prozessoren; das Risiko sind Release-Artefakte, die
  auf dieser Maschine entstehen (Pakete, `_chain.pyd`, Handbuch, Bilder, Signaturen) —
  ein Rechenfehler kann still bleiben. Bis zur Behebung ist ein einzelner unerklärlicher
  Abriss zuerst ein Verdacht auf die Maschine: die Rate verschränkt gegen eine
  Kontrollvariante messen, bevor sich Code ändert. Warum Robert: Hardware, Garantie und
  BIOS. Empfehlungen, nicht umgesetzt: (1) CPU-Tausch über Intels verlängerte Garantie
  (13./14. Generation, fünf Jahre ab Kauf) — der einzige Schritt, der die Ursache
  beseitigt; (2) bis dahin im BIOS die Intel Default Settings setzen und prüfen, ob MSI
  Center Takt- oder Leistungsgrenzen anhebt, als Übergang den Höchstmultiplikator der
  P-Kerne um ein bis zwei Stufen senken; (3) einmal MemTest86 über Nacht, um den
  Arbeitsspeicher auszuschließen; (4) Release-Pakete in der CI bauen oder doppelt bauen
  und bitweise vergleichen, bevor sie hochgeladen werden. Bericht:
  `konzepte/nachweise-release-0.5.1/reports/ast-flake.md`. Abnahme: nach dem Tausch keine
  sporadischen Abrisse dieser Familie mehr, belegt mit einer verschränkten Reihe der
  Sprachprüfung unter Last wie in ast-flake, und MemTest86 ohne Befund.
  Registerabgleich 02.10.: Die Registerzeile „Entscheidung Robert:“ liest sich wie entschieden, der Eintrag sagt „Empfehlungen, nicht umgesetzt“.

<a id="rm-288"></a>

- [ ] **RM-288 — Ein Einzelprozess über die ganze Suite hängt im Sammler.** Aus dem Release 0.5.1. Zweimal blieb
  `tools/affected_tests.py --run` über fast die ganze Suite (Gruppe `plain`, ein Prozess)
  stundenlang stehen, beide Male in `tests/conftest.py` im `gc.collect()` von
  `_collect_released_ui` beim Aufbau von `_windows_live_until_their_test_ends`, fast ohne
  CPU — gestartet am 28.09.2026 gegen 00:53 und 01:06 in zwei Arbeitsbäumen mit
  verschiedenen Änderungen. `py-spy dump --native`: der Hauptfaden mit GIL im Sammler,
  daneben der Poller-Faden von wgpu im `Condition.wait`; welcher Finalizer wartet, zeigt
  der Stapel ohne Symbole nicht. Das Tor mit `-n 8` traf es nie; ein Nachstellversuch als
  Einzelprozess mit `faulthandler_timeout=300` lief ohne Hänger durch die ganze Suite
  (3:33 h, 17 946 bestanden; die 69 roten sind Erzeugnisvergleiche, ohne Marker gefahren)
  (Protokoll des Nachstellversuchs nicht versioniert). Zu klären ist auch, ob derselbe
  Sammlerlauf die Anwendung hängen kann (Finalizer eines wgpu-Objekts gegen den Poller) —
  dort läuft der Sammler von selbst. Bis dahin wählen Sitzungen betroffene Tests gezielt
  oder fahren das Tor. Abnahme: der Einzelprozess läuft durch, oder die Ursache ist
  benannt und behoben.

<a id="rm-313"></a>

- [~] **RM-313 — Der Wächter „Neueste Versionen“ liefert im privaten Repository nichts.** Aus
  dem Aufräumen vom 29.09.2026 (Bericht Werkzeuge 6.1). Der Montagsjob `latest` lief seit
  dem 07.09.2026 ohne Ergebnis: zweimal mit null Schritten (Abrechnungsablehnung im privaten
  Repository), einmal abgebrochen. Der Wochenplan ist entfernt; `latest` läuft jetzt an
  `v*`-Release-Tags oder bei ausdrücklich gesetztem `check_latest`-Handstart und bleibt ohne
  Abhängigkeit von den Pflichtjobs. Die Vertragssicherung in
  `test_latest_dependencies_run_for_release_tags_or_an_explicit_manual_build` prüft, dass
  kein Zeitplan mehr existiert und beide Auslöser erhalten bleiben. Ein echter Ergebnisbericht
  folgt beim nächsten öffentlichen Release; dafür wurde kein Release gestartet.

<a id="rm-314"></a>

- [x] **RM-314 — Rechtenachweis der Stimme für die englischen Werkstattfilme.** Die Stimme
  `en_US-ljspeech-high` und ihr lokaler ONNX- und Konfigurationsstand sind in
  `app/core/knowledge/data/licences.toml` mit Prüfsummen dokumentiert. Die Rechteangabe
  stützt sich auf die Public-Domain-Erklärung und Uploadfreigabe des Modellautors sowie die
  Public-Domain-Angabe der LJ-Speech-Quelle; die MIT-Markierung bei Hugging Face gilt nur auf
  Repository-Ebene, und die Modellkarte widerspricht dem Autor bei Trainingsangaben. Die
  Lizenztests sind grün. Das ist kein pauschaler Nachweis einer gesonderten Einwilligung der
  Sprecherin in Stimmnachahmung oder Werbung; die Quellen belegen eine solche Einwilligung
  nicht.
  Nachprüfung (Review 02.10., Arbeitsbaum ungesichert): unvollständig. Eintrag in `licences.toml` und SHA-256 stimmen mit den Dateien; ein `/legal-review` ist nirgends belegt, `ASSET-RIGHTS.toml` hat keinen Eintrag für die Stimme, die Einwilligungsfrage zur Werbenutzung ist im Eintrag ausdrücklich offen und trotzdem `[x]`; die angeführten Lizenztests prüfen die Stimme nicht.
  Registerabgleich 02.10.: steht als `[x]` im Abschnitt, die eigene Nachprüfung nennt ihn unvollständig — Statuszeichen und Lage passen nicht zusammen.

<a id="rm-316"></a>

- [ ] **RM-316 — Zwillinge und Nur-Test-Wege: der Rest aus dem Code-Bericht des Aufräumens.**
  Aus dem Aufräumen vom 29./30.09.2026; die Durchgänge 1 und 2 stehen in `d8855f20e` und
  `5369bdc5d`. (a) Zwillinge in Dateien, die an dem Tag in fremder Arbeit waren:
  `print_settings_dialog.py` trägt zwei Kopien der Höhenregel und `_select_data` (künftig
  `style.ContentHeight`, `style.select_data`), `manual_window._svg_pixmap` eine Kopie von
  `icons.svg_pixmap`; `ai_disclosure._fit_content_height` ist eine Höhenvariante ohne
  Untergrenze, an der die Freigabe über den Rollstand hängt — nur mit Fenstertest ändern.
  Die Karte `app/ui/CLAUDE.md` nennt `ContentHeight`, `select_data` und `svg_pixmap` noch
  nicht. (b) Dünne Hüllen, deren Produktionsweg anders heißt; Tests auf den echten Weg
  umstellen, Hülle entfernen: `draft_vertical` (`brep/profiles.py`, `geom/faces.py`),
  `placement.placement_tool`, die `_shadow_*`-Hüllen in `viewport.py`,
  `perceive.features.detect_faces`, `slice.analysis._islands`, `slice.gcode.parse`,
  `extrudes`, `printed_extent`, `stated_bed`, `generate.from_image`, `mesh_ops.decimate`,
  `Session.embed_model`/`import_image`, `set_pickable`/`remove_pointer_listener` der
  Renderer-API, `faces._upright_faces`, `autosplit.sections_along`. (c) Kernfunktionen ohne
  Produktionsaufrufer, einzeln als Referenzweg behalten oder entfernen (etwa
  `autosplit.find_plane`, `orient.evaluate_direction`, `section.section_volume`,
  `repair.fill_holes`, `matching._cost_matrix` als Referenzmatrix). (d) `key.device_limit`
  hat keinen Aufrufer; entfernen zieht den Grenznachweis der Lizenzgrenze nach. Abnahme:
  kein Name der Listen ohne Produktionsaufrufer, es sei denn, sein Docstring nennt ihn
  als Referenz- oder Prüfweg.
  Registerabgleich 02.10.: Höhenregel im Druckdialog mit `b837a73f8` erledigt; die Kopie `_select_data` steht weiter in `print_settings_dialog.py:1101`; ein `manual_window._svg_pixmap` gibt es nicht (Entsprechung `_rendered`, `:613`, eine Variante); alle Namen aus (b)–(d) bestehen ohne Produktionsaufrufer (Sonde `k_rm316_aufrufer.py`).

<a id="rm-344"></a>

- [ ] **RM-344 — Renderertests laufen in der CI nur noch unter Windows.**
  Review seit 0.5.1, Befund E-M1, Commit `6f0be89df` (Codex).
  Der Marker `rendering` wird in der Kernmatrix (`.github/workflows/build.yml:185`) und im Job
  `latest` (`:1515`) abgewählt und nur noch von der Gruppe `windowed` (Job `windows`) und
  `window-contracts` getragen (`tools/run_suite_isolated.py:75–76`).
  `pytest --collect-only -m "rendering and not windowed and not performance and not rendered"`
  am HEAD: 110 Fälle (`test_render_gfx_regressions` 68, `test_render_contract` 23,
  `test_render_gizmo` 14, `test_render_factory` 3, `test_feature_label_layout` 2), vorher in der
  Kernmatrix auf drei Plattformen; 107 laufen jetzt nur noch auf Windows beim Release. Linux-
  und Mac-Pakete zeichnen über Vulkan/Metal, RM-051 ist offen, neue pygfx-/wgpu-Fassungen prüft
  `latest` nicht mehr. Widerspricht CI-03/CI-04 aus `konzepte/konzept-ci-testlaufzeiten-2026-09.md`;
  eine Entscheidung Roberts dafür ist nicht festgehalten.
  Hohl geworden: `test_every_linux_ci_path_that_uses_pygfx_has_a_vulkan_adapter`
  (`tests/test_packaging.py:832–845`) bleibt grün über Jobs ohne Bildtest; veraltet
  `build.yml:111–117` und `README.md:170–178`.
  **Fix:** Die `rendering`-Fälle in der Release-CI zusätzlich auf Linux und macOS fahren (etwa in
  `window-contracts` mit `-m "rendering and not windowed …"`) und in `latest` wieder mitnehmen —
  oder, wenn Robert die Windows-Grenze will, die Entscheidung im Konzept festhalten.
  **Abnahme:** Wächter in `test_packaging.py`, dass jeder `rendering`-Fall auf jeder Plattform in
  mindestens einem Releasejob läuft; Vulkan-Wächter, Kommentar und README auf dem Stand.
  Bauplan §35, §38. Beleg: `bericht-E.md` (M1), `sonden\e_collect_rendering_only.txt`,
  `e_collect_render_core.txt`.
  Nachprüfung am Stand `6ce767031`: besteht noch. Von 110 Renderfällen laufen 107 nur in der Windows-Release-CI; Wächter fehlt, Kommentar und README veraltet. Belege `F:\solidon-review-reports\verif-E.md`.

<a id="rm-349"></a>

- [ ] **RM-349 — Werkzeuge und Unterlagen: Reste aus dem Review seit 0.5.1.**
  Niedrige Befunde aus dem Review seit 0.5.1 (`bericht-D.md`, `bericht-E.md`, `bericht-F.md`),
  je einzeln abnehmbar. Registerzellen anderer Punkte werden hier nur gemeldet, geändert werden
  sie von dem, der den Punkt bearbeitet:
  - **E-N2, `c96f60a18` (Codex):** `tools/check_new_texts.py:171–195` (`missing()`) scheitert
    nicht, wenn im Index kein Katalog liegt — `main() = 0` bei neuem unübersetztem Text
    (Sonde `sonden\textwaechter\sonde_leere_kataloge.py`). Fix: leere Katalogliste als Fehler
    mit Handlungsvorschlag, Test (`tests.md`: zuerst zählen).
  - **F-N5, `337697db9`, `8cb4eae96` (Codex), Lücken älter:** `tests/CLAUDE.md:91` und der
    RM-315-Abschluss behaupten `exact_kernel()` vor jedem OCP-Import;
    `tests/test_feature_moves_keep_shape.py:1381ff` und
    `tests/test_geometry_review_regressions.py:911ff` importieren OCP ohne Wächter (ohne OCP ein
    `ImportError` statt Skip). Fix: `exact_kernel()` als erste Zeile, AST-Wächter in
    `test_toolchain.py`.
  - **F-N3, `72281a33e` (Claude):** `.claude/rules/fenster.md:398–399` trägt als einzige Regel ein
    Datum („Entscheidung Robert, 29.09.2026“). Fix: Datum streichen, Anlass nach
    `konzepte/begruendungen/regel-fenster.md`.
  - **F-N4, `bcaac7b53` (Claude):** `tests/test_manual.py:34` behält `importorskip("PySide6")`,
    das die Commitmeldung zu entfernen verspricht. Fix: entfernen, sobald die Datei frei ist.
  - **D-N4:** `.claude/rules/oberflaeche.md:188` („gebaut an drei Orten“) und `:202–203`
    („Noch nicht umgestellt …: die Druckeinstellungen“) sind seit `d8e37581a` falsch (im
    Arbeitsbaum liegt dazu eine fremde ungesicherte Korrektur); `.claude/rules/grenzen.md:194`
    („`adjustSize` läuft nur, wenn sich eine Zeile bewegt hat“) seit `b837a73f8`.
  - **Registerstände (F-N2, D-N4):** RM-134 führt `window` und
    `with_a_body` als offen, beide liegen seit `95fd36d35` in `tests/ui_helpers.py`; die echten
    Reste (`on_the_bore_wall`, `counted`, `FakeCodec`, `a_foreign_slot`) stehen nur im Docstring
    von `tests/helpers.py:13`. RM-286 nennt die Druckeinstellungen noch als offen, sie sind seit
    `d8e37581a` umgestellt.
  - **Beifund:** `.claude/README.md:16` sagt über `memory/` „eine Datei je Fakt“,
    `CLAUDE.md:200` „Eine Datei je Thema“.
  Abnahme: je Spiegelstrich Test oder korrigierte Stelle mit Commit. Beleg: Berichte unter
  `F:\solidon-review-reports`.
  Nachprüfung am Stand `6ce767031`: alle sieben Reste offen (E-N2, F-N5, F-N3, F-N4, D-N4, Registerstände, Beifund memory); nur `oberflaeche.md:202–203` ist im Arbeitsbaum ungesichert korrigiert.

<a id="rm-350"></a>

- [ ] **RM-350 — Ein roter Versionswächter am Release-Tag sperrt die Windows-Signierung.**
  Review seit 0.5.1, Befund E-H1, Commit `36f13c9ee` (Codex).
  Der Job `latest` (freie Auflösung ohne `constraints.txt`) läuft seitdem an jedem Release-Tag im
  selben Lauf wie Kernmatrix und Paketbau (`.github/workflows/build.yml:1444–1453`) und hat kein
  `continue-on-error`. Wird er rot, endet der Lauf mit `conclusion: failure`.
  `tools/sign_release.verify_ci_run` verlangt `success` (`tools/sign_release.py:805–806`) und wird
  in beiden Signierphasen (`:1023`, `:1084`) und in `tools/windows_signed_installer.py:96`
  gerufen. Der Jobkommentar `build.yml:1451` sagt „blockiert nichts — er meldet“.
  **Fehlerfall:** Zum nächsten Tag bringt eine neue Fremdversion eine `DeprecationWarning`
  (unter `filterwarnings = ["error"]` rot) oder eine neue ruff-/mypy-Regel → Lauf „failure“,
  obwohl Kern, Fenster und Pakete grün sind → `sign_release.py --phase application --run <lauf>`
  bricht mit „CI-Lauf … ist kein erfolgreich abgeschlossener Lauf“ ab; das Windows-Setup lässt
  sich für diesen Tag nicht signieren.
  **Fix:** `continue-on-error: true` am Job `latest` (der Job zeigt rot, der Lauf bleibt
  `success`) oder den Wächter in einen eigenen Workflow legen.
  **Abnahme:** Wächter in `tests/test_packaging.py`, dass `latest` den Laufausgang nicht bestimmen
  kann; vor dem nächsten Release-Tag. Bauplan §37.2. Beleg: `bericht-E.md` (H1),
  `sonden\e_sign_conclusion.txt`.
  Nachprüfung am Stand `6ce767031`: besteht noch. Im Arbeitsbaum nur entschärft, solange das Repository privat ist; `continue-on-error` fehlt weiter.

<a id="rm-380"></a>

- [ ] **RM-380 — `test_the_workers_of_the_window_use_the_helper` scheitert nach dem Vorschautest derselben Datei.**
  Review 02.10.2026, Registerabgleich Geometrie, am HEAD `3fd3b1ace`. Beide Tests stammen aus
  `a55e844ad`.
  **Fehlerfall:** `pytest tests/test_kernel_process.py` am Stück: 1 failed, 79 passed, Exit 1 —
  `KeyError: 'helper:display_simplify'` (`tests/test_kernel_process.py:1309`). Allein gefahren ist
  der Test grün (Exit 0); direkt nach `test_the_coarse_preview_reduces_and_drills_in_the_helper`
  (`:1183`) rot (1 failed, 1 passed, Exit 1). Der Vorschautest ruft `kernel_process.shutdown()`
  und rechnet danach dieselbe Vorschau im Prozess (`:1216–1218`); der Fenstertest findet
  anschließend keine `display_simplify`-Zählung — vermutlich weil die verkleinerte Vorschau aus
  einem prozessweiten Speicher kommt oder die Zählung nach `shutdown` nicht neu angelegt wird.
  Weil der Fenstertest (`qt_app`) nur beim Release läuft, fällt das im Entwicklungstor nicht auf.
  **Fix:** Ursache am Zustand festmachen (Vorschau-Cache bzw. `statistics()` nach `shutdown`) und
  im Fixture `offloaded` zurücksetzen; nicht die Zusicherung lockern. `.get(...)` statt `[...]`
  allein wäre keine Behebung.
  **Abnahme:** `tests/test_kernel_process.py` am Stück und in umgekehrter Reihenfolge grün; die
  Zusicherung `>= 1` bleibt. Belege: `F:\solidon-review-reports\kp_order.txt`, `kp_file.txt`,
  `register-geometrie.md`.

<a id="rm-387"></a>

- [ ] **RM-387 — Deutsche Bezeichner rutschen am Sprachwächter vorbei; englische Passungszeichnung veraltet.**
  Review 02.10.2026, Registerabgleich „Bedienung und Darstellung“, am HEAD `4449e3370`.
  - **Bezeichner:** `app/ui/main_window.py:19865–19887` (`_on_import_finished`,
    `_on_import_confirmed`) benutzt die Variablen `eingelesen` und `geladen` — Verstoß gegen die
    Sprachregel (`AGENTS.md`, Bezeichner englisch). `tests/test_language_rules.py` findet sie
    nicht, weil die kuratierte Liste nur `gelesen` als ganzes Wort kennt. Fix: umbenennen (etwa
    `imported`, `downloaded`) und die Stämme `eingelesen`/`geladen` (bzw. `lesen`, `laden`, wo
    das ohne Fehltreffer geht) in `GERMAN_STEMS` eintragen; der Wächter muss mit der alten
    Schreibweise rot werden.
  - **Abbildung:** `website/handbuch/en/fit.svg` und `fit-dark.svg` (Stand 05.09.) zeigen noch
    „Play 0.25 mm“; der Katalog übersetzt seit 0.5.1 „Clearance“.
    `tests/test_manual.py::test_the_drawn_figures_are_the_ones_the_code_draws[en]` (Marker
    `rendered`, nur beim Release) wird dadurch rot. Fix: beim nächsten Release die geänderten
    Abbildungen mit `tools/make_manual.py` neu erzeugen (Weg in `/erzeugen`).
  **Abnahme:** Sprachwächter rot gegen die alte Schreibweise, grün nach dem Umbenennen; der
  Abbildungstest `[en]` grün beim Release. Beleg:
  `F:\solidon-review-reports\register-bedienung.md`.
  Teil Bezeichner erledigt mit `bd7f11180` (02.10.2026): `eingelesen`/`geladen` in `app/ui/main_window.py` heißen `imported`/`downloaded`, die Stämme stehen in `GERMAN_STEMS`; Gegenprobe rot an genau den drei alten Stellen. Offen bleibt der Teil `fit.svg` (Erzeugung beim nächsten Release).

<a id="rm-433"></a>

- [ ] **RM-433 — Die Rückfrage vor Geld- und Veröffentlichungswerkzeugen lässt Umhüllungen und Unterschalen durch.**
  Review 02.10.2026 am Stand `70e9b3145`; Folgepunkt zu RM-346 (archiviert). Die fünf Abnahmeformen
  und viele weitere (PowerShell, `&`, `cd tools`, `bash -c`, `pwsh -Command`, `env`, `"$PY"`) fragen
  jetzt; 143 Tests grün, Mutationen rot.
  **Ungefragt durch:** Umhüllungen `timeout 1800 "$PY" tools/upload_website.py`, `time`, `nohup`,
  `exec`; Unterschale und Befehlsersetzung `( … )`, `$( … )`; zusammengesetzte Befehle `then …`,
  `do …`; `cmd /c`; `Start-Process … -ArgumentList "tools/x.py --dry-run"` sowie mit `@(…)`.
  Ursache: `_werkzeug_aufruf` (`.claude/hooks/solidon3d_hooks.py:722`). „Jede Schreibweise“ aus Commit
  und Archiv stimmt damit nicht. (Deutscher Bezeichner `_werkzeug_aufruf` im Hook — die
  Bezeichnerregel gilt für `app/` und `tools/`; prüfen, ob das gewollt ist.)
  **Fix:** Werkzeugnamen im ganzen Befehl suchen (Token nach Umhüllungen, in Unterschalen und
  Argumentlisten), im Zweifel fragen.
  **Abnahme:** Test je genannter Form → Rückfrage; Lesen/Prüfen bleibt still. Beleg:
  `verif-70e9b3145-oberflaeche.md`, Sonden `v5u_rm346_*`.

<a id="rm-467"></a>

- [~] **RM-467 — Bibliotheken alle drei Tage auf neue Versionen prüfen und aktualisieren.**
  Auftrag Robert 02.10.2026, übernommen: Bibliotheken alle 3 Tage aktualisieren. Je Lauf werden die
  festen Versionen aus `constraints.txt` (Laufzeit und Entwicklung, mit den Plattformpins), die
  Werkzeuge in `.github/workflows/` und die Paketlaufzeiten gegen ihre neueste Fassung abgefragt;
  eine neue Fassung zählt nur mit cp314-Rädern für Windows x64, Linux x86_64 und beide Macs.
  Reihenfolge: Sicherheitsmeldungen, dann Patch und Minor, dann Hauptversionen. Jede Aktualisierung
  geht einzeln durch das Entwicklungstor und, wo sie die Oberfläche oder den Renderer berührt,
  durch die echte Anwendung; danach `tools/check_env.py --freeze`. Was den 0.5.2-Stand gefährdet,
  bleibt festgelegt und bekommt einen eigenen Punkt mit dem nötigen Umbau. Ergänzt RM-313: Der
  CI-Wächter „Neueste Versionen“ läuft nur öffentlich, dieser Lauf lokal und regelmäßig.
  **Abnahme je Lauf:** geprüft, übernommen und zurückgestellt mit Commit im Archiv; der Punkt
  bleibt offen, solange der Auftrag gilt.
  Erster Lauf: [02.10.2026](ROADMAP-ARCHIV.md#rm-467-erster-bibliothekslauf-achtzehn-bibliotheken-und-die-bauplattform-02102026).

## Veröffentlichung, Betrieb und Vertrieb

<a id="rm-002"></a>

- [~] **RM-002 — netcup-AVV und Freigabe der Rechtstexte belegen.** Den Abschluss und Umfang des
  netcup-Auftragsverarbeitungsvertrags im CCP belegen; Hosting, Mail, Support, Aktivierung,
  Protokolle/Statistik und Sicherungen berücksichtigen. Die Vertrags- und Datenschutzaussagen
  anschließend fachlich abgleichen. Das Postfach `support@solidon3d.de` existiert; es wird nicht
  erneut angelegt. DMARC steht separat in RM-008, weitere Verkaufsrechtstexte in RM-093. Abnahme:
  gesicherter Vertragsbeleg und dazu passende freigegebene Texte.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#p8--erste-veröffentlichung).

<a id="rm-006"></a>

- [ ] **RM-006 — Nächsten messbaren Schritt für die Sichtbarkeit festlegen.** Sichtbarkeit als
  konkrete Marketingentscheidung planen: Zielgruppe, Kanal, gewünschte Rückmeldung und messbares
  Ziel festlegen; vorhandene Veröffentlichungen und Kontaktentwürfe dabei berücksichtigen. Abnahme:
  ein beschlossener nächster Außenauftritt mit Ziel und Verantwortlichem. Aus dem pauschalen Befund
  entsteht noch kein Versandauftrag.

  **23.09.2026** (Robert: YouTube und Facebook optimieren, Videos zuerst als
  Konzepttext, Beiträge sofort oder geplant, jede Veröffentlichung vorher mit
  Text und Bild im Chat): 98 % der YouTube-Aufrufe kommen aus Shorts, englische
  erreichen viermal so viele wie deutsche, ein Aufruf dauert im Schnitt 3,6 s.
  Gebaut sind vierzehn Änderungen für YouTube Studio mit fertigen Texten
  (`youtube-optimierung.md`, ein lokales Umsetzungspaket liegt unter
  `youtube-umsetzung/` und ist nicht eingecheckt), sieben Videokonzepte (V3
  freigegeben), dreizehn Beiträge mit Bildern nach dem Bildstandard. Die
  Beiträge vom 24.09. 19:00, 26.09. 10:00 und 28.09. 19:00 sind öffentlich und
  ohne Bewerbung eingeplant, Text zeichengleich mit `posts/*.md` geprüft.
  **GoFundMe** (Robert selbst, 23.09. abends): Titel „Solidon3D: STL anpassen
  ohne CAD – ein Ein-Personen-Projekt“, neue Geschichte in Deutsch und Englisch,
  Ziel 500 € als Etappe bei weiter 5 000 € Gesamtbedarf (automatische Anpassung
  aus), Standard-Spendenart einmalig, Titelbild und fünf Galeriebilder als
  Vollbildausschnitte, Update 1 gesendet; die Galeriefolge 4/5 steht vertauscht,
  GoFundMe bietet kein Umsortieren. Der Spendenweg in der App ist mit foerderung
  (`b1e2a6dd`) gebaut. Messpunkte montags je Kanal. Offen: Roberts Fragen aus
  beiden Berichten (Plan, Stimme und Gesicht der Videos, Kosten der Kampagne,
  Termine) und das Foto für Platz 1 der Kampagne. Die Abnahme „ein beschlossener
  nächster Außenauftritt mit Ziel und Verantwortlichem“ ist mit den eingeplanten
  Beiträgen und den Messpunkten im Kern erfüllt; der Punkt schließt, wenn Robert
  den Plan bestätigt.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#gegen-das-wettbewerbsfeld-gehalten-11082026).

  **Stand laut Register bis 29.09.2026:** Plan bis 01.11. mit Takt und Messpunkten liegt vor
  (`marketing/reichweite/analyse-und-plan.md`, `36487f9b`); drei Facebook-Beiträge für 24., 26.
  und 28.09. in der Meta Business Suite eingeplant; YouTube-Änderungen (14) freigegeben, in
  Studio nicht umgesetzt; Video V3 freigegeben, nicht gedreht. Offen: Roberts Fragen im Bericht
  Reichweite und die erste Montagsmessung; der Punkt schließt, wenn Robert den Plan bestätigt
  Registerabgleich 02.10.: Die zitierten `marketing/`-Dateien sind seit `01eea2225` nicht mehr versioniert.

<a id="rm-008"></a>

- [ ] **RM-008 — DMARC-Eintrag öffentlich prüfen und gegebenenfalls einrichten.** Am 08.09.2026
  lieferte die TXT-Abfrage für `_dmarc.solidon3d.de` sowohl über den lokalen Resolver als auch über
  1.1.1.1 nur den SOA-Eintrag der Zone, keinen DMARC-TXT-Eintrag. Eine zum tatsächlich genutzten
  Mailversand passende Richtlinie im CCP einrichten. Abnahme: öffentlich auflösbarer DMARC-Eintrag
  und geprüfter legitimer Versand.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-demo-bis-30102026-12082026).

<a id="rm-030"></a>

- [ ] **RM-030 — Impressum nach Vergabe einer USt-IdNr. oder W-IdNr. ergänzen.** Prüfen, ob Robert
  eine Umsatzsteuer-Identifikationsnummer oder Wirtschafts-Identifikationsnummer erhalten hat; falls
  vorhanden, Impressum und Erzeugungsquelle damit ergänzen. § 5 Abs. 1 Nr. 6 DDG nennt diese
  Nummern, keine allgemeine Steuernummer. Die frühere TMG-/Steuernummer-Angabe war falsch. Abnahme:
  vorhandene Nummer korrekt in den erzeugten Fassungen; keine Veröffentlichung einer gewöhnlichen
  Steuernummer. Quelle: [§ 5 DDG](https://www.gesetze-im-internet.de/ddg/__5.html).

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-erst-am-verkaufsstart-fällig-wird-24082026).

<a id="rm-034"></a>

- [ ] **RM-034 — Versicherungsschutz für Software und Produktschäden klären.** Angebote und
  Vertragsbedingungen für die tatsächlichen Software-, KI- und Druckvorbereitungsrisiken fachlich
  prüfen lassen; Personen-, Sach- und Vermögensschäden, Ausschlüsse und Deckungsgrenzen ausdrücklich
  abgleichen. Abnahme: geeignete Deckung oder eine dokumentierte neue Risikoentscheidung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-haftungsgrundlagen-des-geschäftsmodells-nachkontrolliert-24082026).

<a id="rm-035"></a>

- [ ] **RM-035 — EULA wirksam in den Bestellvorgang einbeziehen.** Mit der Rechtsprüfung klären,
  welche Produktgrenzen wie vor dem Kauf dargestellt und gegebenenfalls gesondert vereinbart werden
  müssen. Abnahme: freigegebene Texte und ein geprüfter vollständiger Bestellablauf; der Spendenweg
  bleibt ohne Gegenleistungsversprechen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-haftungsgrundlagen-des-geschäftsmodells-nachkontrolliert-24082026).

<a id="rm-036"></a>

- [ ] **RM-036 — Vertrag und Freistellungen des Zahlungsdienstleisters prüfen.** Leistungsumfang,
  Haftungsfreistellung, Grenzen, anwendbares Recht und Gerichtsstand mit Geschäftsmodell und
  Versicherung abgleichen. Abnahme: konkrete Vertragsfassung fachlich geprüft und die
  Haftungsübernahme ausdrücklich entschieden.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-haftungsgrundlagen-des-geschäftsmodells-nachkontrolliert-24082026).

<a id="rm-061"></a>

- [ ] **RM-061 — Verkaufsbereitschaft und Ende der Demo vorbereiten.** Bei geklärter Anmeldung,
  Zahlung und Rechtstexten bis 25.10. einen Verkaufskandidaten vorbereiten. Der **31.10. bleibt
  für letzte Optimierungen reserviert**; Verkaufsstart ist am **01.11.2026 um 10:00 Uhr
  Europe/Berlin** (Robert, 16.09.). Grundlage ist das
  [Übergangskonzept](konzepte/konzept-demo-zu-1.0-2026-09.md): Ablauf alter Demos und laufender
  Sitzungen, Aktualisierung und Projektübernahme, Kaufzustellung, Geräteaktivierung und
  Veröffentlichung nach §§5–13 umsetzen; Abnahmefälle T01–T32 und Freigabekriterien §§15–16
  erfüllen. Der Ist-Zustand vom 16.09. hat noch keinen täglichen Ablaufwächter und keinen
  Bestell-Webhook im Repository. **Uhr-Rückstellfehler I03a am 16.09. lokal behoben:**
  Erkannter Ablauf bleibt erhalten, auch über den Umweg einer falschen Zukunftsuhr und bei
  Verlust eines Markers; 130 Aktivierungs-/Grenztests bestanden, zwei übersprungen.
  Noch offen: laufender Zustands-Cache sowie Grenzen bei eingefrorener Uhr, fehlenden
  Markern und vollständiger Systemrücksetzung nach §7.1/T10. Die Demo endet unverändert
  einschließlich 30.10.; die
  geplante Pause bis zum Verkaufsstart wird vorab erklärt. Fehlen Voraussetzungen,
  Verkauf geschlossen halten und Verschiebung kommunizieren; eine andere Demo-Frist
  benötigt eine ausdrückliche neue Entscheidung und einen neuen Bau. Abnahme: nach dem
  letzten Optimierungsstand geprüfte Pakete sowie ein kaufbarer, zustellbarer und
  aktivierbarer Weg zum bestätigten Start; andernfalls dokumentierter Verschiebungsablauf.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-robert-am-26082026-aufgetragen-hat).

  **Aus dem Lizenzarten-Konzept (§6, P7):** Handbuch und Regeln nennen die Lizenzart
  (privat oder gewerblich, Platzzahl) noch nicht; die Karte `app/core/activation/CLAUDE.md`
  und der Über-Dialog tun es. Vor dem Verkaufsstart nachziehen.
  Registerabgleich 02.10.: Dem Eintrag fehlt der Bau aus 0.5.0 (`29dcefa4`), den die Registerzeile nennt; „Handbuch nennt die Lizenzart nicht“ stimmt seit `334f73b73` nicht mehr (`app/core/manual.py:1480`, dieselbe Altaussage in `konzepte/konzept-lizenzarten-2026-09.md:376`); Webhook und täglicher Ablaufwächter fehlen weiter. Statuszeichen wäre `[~]`.

<a id="rm-091"></a>

- [ ] **RM-091 — CRA-Meldebereitschaft herstellen, die Frist ist abgelaufen.** Die in
  SECURITY-INCIDENT.md
  festgelegte Meldebereitschaft praktisch nachweisen: EU-Login und Plattformzugang, Vertretung,
  CSIRT-Zuordnung und Alarmierung prüfen; den Probelauf bis vor dem Absenden durchführen und privat
  protokollieren. Keine fingierte Meldung senden. **Die Meldepflicht aus Art. 14 gilt seit dem
  11.09.2026** — der Punkt stand als Vorbereitung vor dieser Frist, und die ist vorbei; die vier
  Bereitschaftspunkte in SECURITY-INCIDENT.md sind bis heute alle offen.
  Konten- und Betriebsbereitschaft sind durch Texte im Repository nicht belegt. Abnahme: sämtliche
  bereits festgelegten Bereitschaftspunkte mit tatsächlichen Ergebnissen geschlossen. Quelle:
  [EU-Kommission zu
  CRA-Meldepflichten](https://digital-strategy.ec.europa.eu/de/policies/cra-reporting).

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).
  Registerabgleich 02.10.: `SECURITY-INCIDENT.md` hat fünf offene Bereitschaftspunkte, nicht vier.

<a id="rm-092"></a>

- [ ] **RM-092 — Verkaufskonzept für den geplanten Start abschließen.** Das Verkaufskonzept bis zum
  15.10.2026 aktualisieren; der beschlossene Verkaufsstart ist der **01.11.2026 um 10:00 Uhr
  Europe/Berlin**. Kauf, Zustellung und Freigabe sind im
  [Übergangskonzept](konzepte/konzept-demo-zu-1.0-2026-09.md) §§9, 11 und 13 ausgearbeitet.
  Preis, tatsächlichen Anbieter und Vertragspartner, Bestell-/Zustimmungsstrecke,
  Lieferung, Widerruf und Signierung
  festlegen. Abnahme: freigegebener Ablauf, Testkauf einschließlich Storno und passende Rechtstexte;
  überholte Konzepte eindeutig kennzeichnen. **Der Preis ist seit dem 15.09.2026 entschieden**
  (Robert: privat 69 € ab 01.11.2026 und 99 € ab 01.02.2027, gewerblich 199 € und 249 € an
  denselben Tagen, beide als Einmalkauf mit allen 1.x-Updates) — er steht in
  [konzept-lizenzarten-2026-09.md](konzepte/konzept-lizenzarten-2026-09.md) §3, und der Bau der
  zweiten Lizenzart läuft unter RM-182. Was hier offen bleibt, sind Anbieter, Bestellstrecke,
  Lieferung, Widerruf und Signierung.

  **Bestätigt am 23.09.2026** (Robert): zwei Lizenzarten, keine dritte Stufe.
  Die Presseentwürfe 05, 22 und `VERSAND.html` sind nachgezogen; die Website
  bleibt preisfrei, bis das Angebot steht.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

  **Stand laut Register bis 29.09.2026:** Preis bestätigt am 23.09.: zwei Lizenzarten, privat 69
  € bis Ende Januar, ab Februar 99 €, gewerblich 199 €, ab Februar 249 €; ‚drei Stufen‘ ist aus
  Presse und Texten gestrichen (`9145aedc`). Offen: Anbieter, Bestellstrecke, Lieferung, Widerruf
  und Signierung bis 15.10.

<a id="rm-093"></a>

- [ ] **RM-093 — Noch fehlende Angaben und Prüfungen der Rechtstexte klären.** Die offenen Rechts-
  und Anbieterentscheidungen vor dem Verkauf fachlich abschließen: Kontakt-/Steuerangaben,
  tatsächlicher Zahlungsanbieter samt Bestellbestätigung und Widerruf, Datenschutzrollen sowie
  Markenrecherche. Für Chat und Generatoren zusätzlich die eigene KI-Systemrolle sowie die
  einschlägigen Transparenzpflichten aus Art. 50 Abs. 1 und 2 der KI-Verordnung fachlich einordnen
  und am angebotenen Einstieg prüfen. Abnahme: dokumentierte Entscheidungen und geprüfte Verträge/Sprachfassungen;
  bereits berichtigte Widerrufszitate und EULA-Sanktionsklausel nicht erneut beauftragen.

  **Zwei Fragen kommen aus der Website-Durchsicht vom 15.09.2026 dazu**, beide erst zum Verkauf
  fällig und beide keine Textkorrektur, sondern eine Einordnung:

  1. **Sprache der Rechtstexte beim Verkauf ins Ausland.** `tools/make_legal.py` erzeugt EULA,
     AGB, Widerruf und Datenschutz **nur auf Deutsch** (`DOCUMENTS`), und die fünf
     fremdsprachigen Startseiten verlinken genau diese deutschen Fassungen; den Hinweis auf die
     Vertragssprache trägt der Erzeuger selbst (`LANGUAGE_NOTE`). Für die unentgeltliche Demo
     ohne Bestellung ist das vertretbar — ob es für einen Verkauf an Verbraucher in Spanien,
     Frankreich, Italien oder Portugal trägt, ist die offene Frage (Informationspflichten nach
     Art. 246a EGBGB „klar und verständlich"). AGB und Widerruf sind auf den fremdsprachigen
     Seiten heute **nicht** verlinkt, und das ist richtig, solange nichts angeboten wird
     (`test_legal.SALE_LINKS`).
  2. **Ist die Aktivierung eine automatisierte Entscheidung nach Art. 22 DSGVO?** Der Dienst
     entscheidet ohne menschliches Zutun über Sperrstatus, Geräteplatzgrenze und die fünf
     Aktivierungen je Kalendertag; eine Ablehnung verhindert die Nutzung gekaufter Software, hat
     also Wirkung. Die Datenschutzerklärung beschreibt den Vorgang vollständig, ordnet ihn aber
     nicht ein — Art. 13 Abs. 2 f verlangt die Information nur, wenn Art. 22 greift. Gegen
     Art. 22 spricht, dass keine persönlichen Aspekte bewertet werden (kein Profiling); dafür
     spricht die Rechtswirkung. Ein Satz „automatisierte Entscheidungen nach Art. 22 finden nicht
     statt" wäre die einfache Auflösung, wenn die Einordnung das hergibt.

  **Was die Durchsicht dagegen nicht gefunden hat**, und das gehört zum Ergebnis: Impressum nach
  § 5 DDG vollständig (bis auf die USt-IdNr. aus RM-030), § 36 VSBG korrekt, **kein veralteter
  Verweis auf die 2025 abgeschaltete EU-Streitbeilegungsplattform**, Widerrufsbelehrung mit
  Muster-Formular und richtig zitiertem § 356 Abs. 6 Nr. 2 BGB, dreizehn der Pflichtangaben aus
  Art. 13 DSGVO belegt, und **kein Cookie-Banner nötig** — gemessen, nicht behauptet: keine
  `document.cookie`, kein `localStorage`, keine externe Ressource auf irgendeiner Seite, damit
  greift § 25 TDDDG nicht. Der Hinweis auf den Widerruf einer Einwilligung fehlt zu Recht, weil
  keine Verarbeitung auf einer Einwilligung beruht.

  **Und eine Spannung zum Vormerken:** Die Startseite sagt unter „Kein Team" zu, es gebe „keine
  Hotline, keine Antwort um drei Uhr nachts". Die gewerbliche Lizenz sagt seit dem 15.09.2026
  eine Antwort binnen zwei Werktagen zu. Beides verträgt sich, aber wenn die Preise auf die Seite
  kommen, gehört dieser Absatz mitgelesen.

  **Durchsicht 0.5.0:** Zur Freigabe kommen die vier sachlichen Korrekturen aus
  `9145aedc` hinzu (`DATENSCHUTZ.md` Menüpfad und Fragebogen „einmal je
  Version“, `EULA.md` §9 Häufigkeit und zwei fehlende Netzwege), dazu der Satz
  zur Einladung je Version für den Unterstützungshinweis der App (foerderung,
  nicht eingebaut) und der Absatz zum GoFundMe-Widget mit Zwei-Klick (website,
  Vorschlag). Die Texte ändern keinen Datenfluss; Robert gibt sie frei.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).
  Registerabgleich 02.10.: Das Zitat „drei Uhr nachts“ steht seit `fede439a5` nicht mehr auf der Startseite.

<a id="rm-095"></a>

- [ ] **RM-095 — Automatischen Löschlauf auf dem Server belegen.** Den geplanten Server-Löschlauf
  einschließlich Ratelimits und Backups belegen: tatsächliche Pfade und Zeitplan prüfen, Lauf und
  Ausfallalarm dokumentieren. Abnahme: ausgefüllte Freigabepunkte in PRIVACY-COMPLIANCE.md; die
  Codefrist allein ist kein Betriebsnachweis.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-116"></a>

- [ ] **RM-116 — Historische Statistikreste auf dem Server behandeln.** Den alten öffentlichen
  Statistikordner auf dem Server erneut prüfen und die historischen Zählzeilen nach Roberts
  Entscheidung entfernen. Abnahme: kein pseudonymer Altbestand mehr im Dokumentenstamm und der
  aktuelle Zähler schreibt ausschließlich in den privaten Ort.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#030-ist-draußen-03092026).

<a id="rm-145"></a>

- [ ] **RM-145 — CRA-Konformitätsakte zum gesetzlichen Anwendungszeitpunkt vorbereiten.** Bauplan §37.3 führt die allgemeinen CRA-Pflichten ab dem 11.12.2027.
  RM-091 behandelt Meldebereitschaft und RM-115 die Releaseakte; beide ersetzen keine vollständige
  Konformitätsakte. Zum konkret rechtlich erforderlichen Zeitpunkt Produktklassifizierung,
  Risikoanalyse, technische Dokumentation und nachgewiesene Anhang-I-Pflichten zusammenführen;
  Konformitätsverfahren, EU-Konformitätserklärung, Kennzeichnung und Unterstützungsdauer fachlich
  prüfen. Vorhandene SBOM- und Sicherheitsunterlagen nutzen; daraus keine vorzeitige
  Konformitätsfreigabe ableiten.

  [Bauplan-Abgleich und Nachweis](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026).

<a id="rm-242"></a>

- [ ] **RM-242 — Testphase der Vollversion nachreichen.** Entscheidung Robert vom 25.09.2026:
  Die Verkaufsversion startet am 01.11.2026 wie geplant ohne Testphase
  ([Übergangskonzept](konzepte/konzept-demo-zu-1.0-2026-09.md) H, I09); eine Testphase wird
  später integriert. Im Gespräch sind **Januar 2027**, damit Unentschlossene noch zum
  Einstiegspreis von 69 € ausprobieren und kaufen, oder **Februar 2027** zusammen mit dem
  Preissprung auf 99 €/249 €. Der Unterbau steht: `TRIAL_DAYS = 14` und `TRIAL_FROM` in
  `app/core/activation/store.py`; ein Angebot braucht einen bewusst gebauten Release mit
  gesetztem `TRIAL_FROM`. Die EULA lässt eine spätere Testphase ausdrücklich zu (§4a).
  Zu entscheiden: der Termin; ob Geräte mit altem Demo-Marker die Testphase ebenfalls bekommen
  (heute schließt T15 im Übergangskonzept das aus — damit erreichte ein Januar-Termin die
  Unentschlossenen aus der Demo gerade nicht); welcher Release sie trägt und wann er vor dem
  Termin draußen sein muss. Abnahme: 1.x-Build mit gesetztem `TRIAL_FROM`, Frist je Gerät von
  14 Tagen, danach derselbe lesende Zustand wie ohne Testphase (I09), Tests analog
  `test_a_sale_version_carries_no_deadline`, Website, Kauftexte und Changelog nennen sie.
  Registerabgleich 02.10.: Die Testphasen-Klausel steht in EULA §4, nicht in §4a.

<a id="rm-351"></a>

- [ ] **RM-351 — Die Website bietet 0.5.1 an und nennt im Downloadhinweis 0.5.0 als signierte Fassung.**
  Review seit 0.5.1, Befund E-N1, Commit `1f5dc9f43` (Claude).
  Der Hinweis im Windows-Reiter sagt in allen sechs Sprachen „Die Windows-Version 0.5.0 ist
  digital signiert.“ (`website/index.html:360`, `website/en/index.html:350`,
  `website/{es,fr,it,pt}/index.html:348`), direkt unter „Version 0.5.1, erschienen am
  28.09.2026“. Ein Kunde liest daraus, die angebotene 0.5.1 sei nicht signiert. Der Text ist von
  Hand geschrieben und hat keinen Wächter.
  **Fix:** Versionsneutral formulieren („Windows-Anwendung und Setup sind digital signiert“) oder
  die Version von `tools/make_download.py` schreiben lassen und gegen `website/version.json`
  prüfen; Upload nur mit Auftrag (`/erzeugen`).
  **Abnahme:** Test in `tests/test_website.py`, dass kein Signaturhinweis eine andere Version als
  `version.json` nennt. Bauplan §37.2. Beleg: `bericht-E.md` (N1).
  Nachprüfung am Stand `6ce767031`: besteht im Repository und live auf solidon3d.de („0.5.0 ist digital signiert“ neben „Version 0.5.1“).

## Kundenrückmeldungen

<a id="rm-038"></a>

- [ ] **RM-038 — Mailrückfall ohne prozentkodierten Berichtstext prüfen.** `SupportDialog` übergibt
  Betreff und Nachricht inzwischen direkt als Klartext an `ComposeEmail`; die alte Forderung nach
  gekürztem mailto-Text ist überholt. Abnahme im ausgelieferten Paket: Umlaute, Satzzeichen und
  Zeilenumbrüche kommen unverändert im Mailentwurf an; fehlendes Portal liefert eine Rückmeldung und
  den gespeicherten Ordner als Rückweg.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-erste-linux-kunde-und-was-sein-protokoll-trug-06092026).
  Registerabgleich 02.10.: Code und Tests grün; Abnahme im Flatpak nur am Gerät; Statuszeichen wäre `[~]`.

<a id="rm-040"></a>

- [ ] **RM-040 — Kundenfehler mit Traceback und betroffener Datei zuordnen.**
  Traceback-Protokollierung und Übergabe in den Fehlerbericht sind gebaut. Abnahme: neuer Bericht
  aus einer aktuellen Fassung nennt die konkrete Ausnahme und betroffene Datei; Ursache nachgestellt
  und erforderlicher Fix geprüft.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-erste-kundenbericht-aus-034-06092026).

<a id="rm-062"></a>

- [ ] **RM-062 — Eingabemethode im aktuellen Flatpak bestätigen.** Die Fcitx-Berechtigungen und der
  X11/XWayland-Startweg sind gebaut. Auf der aktuellen ausgelieferten Fassung Start ohne
  Zusatzschalter, Fokus sowie Tastatur/IME in Eingabefeldern prüfen; Paket, Desktop, Qt-Plattform
  und Eingabemethode dokumentieren. Abnahme durch aktuellen Kundenbericht oder reproduzierbaren
  Linux-Lauf; nativer Wayland ist davon getrennt.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-erste-kundenbericht-aus-dem-feld-27082026).
  Registerabgleich 02.10.: Statuszeichen wäre nach der Legende `[~]`.

<a id="rm-064"></a>

- [ ] **RM-064 — Slicerübergabe zwischen zwei echten Flatpaks abnehmen.** Erkennung, Hostpfade und
  Austauschordner sind repariert. Abnahme auf Linux: Modell aus dem ausgelieferten Solidon-Flatpak
  an ein installiertes Slicer-Flatpak übergeben, dort öffnen und den erreichbaren Austauschpfad
  dokumentieren.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-erste-kundenbericht-aus-dem-feld-27082026).
  Registerabgleich 02.10.: Statuszeichen wäre nach der Legende `[~]`.

<a id="rm-072"></a>

- [ ] **RM-072 — Zusagen an den Dental-Kunden zum Verkaufsstart erfüllen.** Den Dental-Kunden
  spätestens zum Verkaufsstart über den Kaufweg und nach belastbarer 3D-Maus-Verfügbarkeit über die
  Unterstützung informieren. Abnahme: beide Anlässe mit tatsächlichem Versandstatus dokumentiert;
  bereits versandte Nachrichten bei der Bearbeitung zuerst prüfen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#eine-kundenanfrage-aus-dem-dentalbereich-30082026).
