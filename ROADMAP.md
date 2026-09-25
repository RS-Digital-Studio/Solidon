# ROADMAP — Arbeitsliste

Der ursprüngliche Bauplan-Abgleich vom 08.09.2026 und seine Fortschreibungen stehen im
[Archiv](ROADMAP-ARCHIV.md). Der Veröffentlichungsstand ist **0.5.0**, veröffentlicht
am **24.09.2026** (`website/version.json`). Windows-Anwendung und Setup sind digital
signiert und mit Zeitstempeln geprüft; beide Mac-Pakete sind signiert und notarisiert.
Alle fünf Kundenpakete sind öffentlich vollständig per HTTPS geprüft. Die gebundenen
Nachweise stehen unter `Releases/0.5.0/Nachweise/`; die offenen Aufgaben darunter
führen ihre verbleibende Arbeit oder Abnahme.

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
Auflagen werden daneben rechtzeitig bearbeitet. **Als Nächstes:** die
Mac-/Linux-Nachweise und die Absicherung der Releaseakte, außerdem die
CRA-Betriebsvorbereitung — deren Frist ist am 11.09.2026 **abgelaufen**, die
Meldepflicht aus Art. 14 gilt seither (RM-091). Eine zurückgestellte
Produktentscheidung oder ein kostenpflichtiger Lauf wird durch diesen
Abgleich nicht freigegeben.

## Was offen ist

Jede Zeile führt zu genau einem offenen Punkt. Die letzte Spalte nennt den nächsten Schritt; Begründung und Abnahme stehen am Punkt.

| Punkt | steht unter | wartet auf |
|---|---|---|
| [CI-Testlaufzeiten — vollständige Prüfungen früher abschließen](#ci-testlaufzeiten) | Tests und Entwicklungswerkzeuge | Konzept CI-01 bis CI-08 beauftragt; unabhängige Jobs, Kern und Fenster in je drei Teilen, Berichte, Testaufteilung, gemeinsame Vorbereitung und behobener Ausreißer umgesetzt; reale Fenster-/CI-Zeitabnahme beim Release |
| [RM-184 — Dateiaudit vollständig umsetzen](#rm-184) | Geometrie, Erkennung und Druckvorbereitung | Nativer Ablauf der Dichtnut am Fenster; die übrigen Familien und die Einzeldateiabnahme aller 187 Fälle sind zurückgestellt |
| [RM-011 — Erstinstallation auf einem fremden Rechner abnehmen](#rm-011) | Plattformen, Pakete und Grafik | Fremdrechner ohne Entwicklungsumgebung von Download bis Export prüfen |
| [RM-021 — Native Fensterlebensdauer am aktuellen Renderer abnehmen](#rm-021) | Plattformen, Pakete und Grafik | Der Riss in `test_ui.py` Teil 4 ist bis auf `processEvents` im Teardown eingegrenzt und trifft die Anwendung nicht; offen ist der Ereignistyp dahinter und die Gegenprobe auf Linux und Mac |
| [RM-050 — Kopierkosten messen und verbleibende VTK-Geometrie ablösen](#rm-050) | Plattformen, Pakete und Grafik | VTK ist ausgebaut (`5a57e261`), die Wandmessung verwendet den eigenen Strahltest. Matplotlib ist seit `9bb1542b` wieder Laufzeitabhängigkeit; die Windows-Lizenzbeilage enthält 50 Komponenten. Offen bleiben die kopierten Bytes und Pufferkosten je großer Szene, gemessen am Fenster; Bereichsprüfungsreste stehen unter RM-214 |
| [RM-051 — Renderer und Grafiklaufzeit in Linux- und Mac-Paketen abnehmen](#rm-051) | Plattformen, Pakete und Grafik | Grafik und Eingabe der veröffentlichten 0.4.0-Pakete für Linux und Mac abnehmen |
| [RM-055 — Neue Paketwerkzeuge im installierten Kundenpaket abnehmen](#rm-055) | Plattformen, Pakete und Grafik | Die CI protokolliert jetzt die echte Inno-Setup-Fassung (`920c609a`); offen sind der Flatpak-Lauf auf echter Linux-Grafik und der Feldlauf Installieren/Aktualisieren/Deinstallieren auf fremdem Windows |
| [RM-104 — Verbleibende Mac- und Unix-Befunde mit aktueller CI-Abdeckung abnehmen](#rm-104) | Plattformen, Pakete und Grafik | Intel-Hänger und übrige Unix-Fenster-/Export-/Chatfälle abnehmen |
| [RM-107 — Ubuntu-Workerabbruch mit aktuellem Testbestand zuordnen](#rm-107) | Plattformen, Pakete und Grafik | Auslöser mit aktueller Testreihenfolge und Widget-/Worker-Lebensdauer eingrenzen |
| [RM-114 — Vereinfachungsziele auf Apple Silicon vermessen](#rm-114) | Plattformen, Pakete und Grafik | Der Test überspringt nicht mehr, ein sicher offener Ausgang löst die Warnung auf jeder Plattform aus (`a559e947`); offen bleibt die Zielreihe der Hohlkugel auf einem Mac |
| [RM-187 — Dieselbe Geometrie auf jeder Plattform](#rm-187) | Plattformen, Pakete und Grafik | Der Änderungsweg ist an der Wurzel plattformgleich (`a559e947`: `units.plane_fit`, `units.dot3`, neun Wege bitgleich unter ULP-Rauschen); offen sind die Fingerabdrücke auf den drei Runnern und die Einpassungen in `perceive` sowie `shapes.thread_body` (Liste am Punkt) |
| [RM-017 — Nutfedermaße an realen Aluminiumprofilen prüfen](#rm-017) | Geometrie, Erkennung und Druckvorbereitung | Zwei benannte Aluminiumprofile nachmessen und Passung prüfen; dabei die Zeile „Nut 8 wie 3030“ gegen den dickeren Steg vieler 4040-Profile (4,3 statt 2,0–2,2 mm) prüfen |
| [RM-022 — Nachbau als Operationsfolge](#rm-022) | Geometrie, Erkennung und Druckvorbereitung | P4.0 steht (`596bcb64`, „In Flächen und Kanten umwandeln“); P4.1–P4.3 folgen in 0.5.x: Nachbaukandidaten aus Grundvolumen, Aufträgen und Abzügen, dann der geprüfte Nachbau hinter dem Import (CAD-Konzept §§8, 13.5) |
| [RM-188 — CAD-Ausbau, Bedienung und Resin für 0.5.x](#rm-188) | Geometrie, Erkennung und Druckvorbereitung | 0.5.0 trägt nach Roberts Entscheidung vom 23.09. P3.2–P3.5, P4.0, P6.1–P6.7, P7.1–P7.4 und Zeichnen Z0/Z1 — implementiert, die Fensterabnahme gehört zum Release (RM-213); Paketstände in der Tabelle am Punkt. In 0.5.x danach: P4.1–P4.3 (RM-022), P8.1–P8.5, P9.1–P9.4, P0.8, P5.1–P5.3, Zeichnen Z2–Z6 und die exakten Erzeuger ohne Eingang (P2.8, Mechanismus bei Robert). Abschluss erst nach P5.3 |
| [RM-191 — PrusaSlicer verbraucht für dieselbe Übergabe ein Drittel mehr Material](#rm-191) | Geometrie, Erkennung und Druckvorbereitung | Nachgemessen am Gewürzregal (`56f70000`): Material innerhalb von 3 %, Zeit Prusa 1,93× Orca — behoben bis 1,19× (volle Füllung und Lückenfüllung für Prusa und Orca, Bahnbreite je Orca-Rolle, `machine_limits_usage = ignore`); der Rest ist die Bauweise des Slicers (Füllanker, Zusatzwände) — ob Solidon dort Vorgaben setzt, entscheidet Robert |
| [RM-209 — Die Rundform-Einpassung an Gittermodellen](#rm-209) | Geometrie, Erkennung und Druckvorbereitung | Gebaut am 22.09.2026: drei Regeln gegen Läufe, die nur am Limit noch antworten. Die Zeitzahlen sind zurückgezogen (unter Fremdlast gemessen) und werden ruhig neu erhoben; die Merkmalsbilanz steht. Kumiko-Schale in der Durchsicht 0.5.0 unverändert (40,9 gegen 41,1 s unter Fremdlast); die Kosten liegen im Kegellöser |
| [RM-210 — Die Erkennung hängt von der Lage des Körpers ab](#rm-210) | Geometrie, Erkennung und Druckvorbereitung | Mindestbogen nach Roberts Entscheidung gebaut (5 Grad, beide Kerne, `3fa7d719`), die Kippstellen der Verrundungen behoben — lageabhängig 17 statt 27 von 101 Körpern; offen sind Einpassungen an ihrer Kippe (deckungsgleiche Kegel am Budget, Flächen aus zwei Dreiecken, Langlöcher der CC2-Box, Freiformurteil, Torus gegen Langloch) oder die dokumentierte Grenze der Zusage ‚drehfest‘ — zwischen beidem entscheidet Robert |
| [RM-132 — Freiformerkennung am Ein-Sekunden-Ziel messen](#rm-132) | Geometrie, Erkennung und Druckvorbereitung | 1,400 auf 1,004 s gebracht; offen ist die Entscheidung zwischen Stapelumbau der Einpassungen und einem neu gefassten Ziel. Durchsicht 0.5.0: an der Freiform aus den Leistungstests 6 % langsamer als vorher (unter Fremdlast), am Drachen gleich; der Aufschlag ist der Kantenleser der Gewinde (je Achse 0,12 s an 233 330 Kanten). Die Schiffskörper aus RM-181 liegen bei 7,9–18,3 s je 200 000 Dreiecke |
| [RM-164 — Creality Print: Erkennung steht, der Konsolenlauf ist ungeprüft](#rm-164) | Geometrie, Erkennung und Druckvorbereitung | Solidons Anteil erledigt (`56f70000`: der Fensterweg bekommt die einplattige Mehrfarbdatei, Abstürze heißen Absturz); offen allein die Abnahme des Konsolenwegs — Creality Print einmal einrichten (Modus und Drucker, Robert), dann drei Platten mit mehreren Spulen über *Slicen* |
| [RM-166 — Ergebnisnetze aus Mesh-Ops an einer STL überstehen keinen Weld](#rm-166) | Geometrie, Erkennung und Druckvorbereitung | Auf Windows mit 1 728 Reihenfolgen, Rauschen je Funktion und 24 Hash-Startwerten nicht nachzustellen; Vermutung: gemischte Ubuntu-Runner (AVX-512/AVX2). Nächster Schritt: die Eckkette in `edges.py` auf die plattformgleichen Werkzeuge umstellen und die Ecke in `test_platform_identity._WAYS` aufnehmen; das Beispielarchiv der Werkstattfilme bleibt offen |
| [RM-193 — Die Erkennung an einer glatten Generator-Freiform kostet Minuten für null Merkmale](#rm-193) | Geometrie, Erkennung und Druckvorbereitung | Entschieden und gebaut am 22.09.2026: Die Haut — der Fleck über der halben Oberfläche, der keine Grundform ist und in Splitter zerfällt — wird nicht mehr Splitter für Splitter eingepasst, ihre Stücke von Gewicht schon (Zapfen, Verrundung bleiben); das Freiformurteil kommt aus der Haut. Drache 482 → 37,7 → 4,2 s, Schüssel 7,3 → 3,0 s (unter Fremdlast, gleiche Merkmale). Vierte Fassung nach einem Korpusfund: Das Urteil zählt nur Flecken **ohne** Grundform — drei Bowlingkugeln verloren sonst ihre Kugel (Rückstand 0,0 über 65 024 Dreiecke), und schon im alten Stand hing es an der Fleckreihenfolge. Zwei Runden statt einer, Drache 4,02 → 3,83 s. Offen: §31 verlangt 1 s je 200 000, gemessen sind 3,83 — es bleibt `_large_facet_faces` (1,2 s am Drachen) und der Löser selbst (RM-209). Zwei Abkürzungen sind gemessen und verworfen: nur den Zylinder fragen (kostet die Bowlingkugel) und die Stichprobe an Riesenflecken (ändert die Erkennung). Durchsicht 0.5.0: an der Freiform aus den Leistungstests 6 % langsamer als vorher (unter Fremdlast), am Drachen gleich; der Aufschlag ist der Kantenleser der Gewinde (je Achse 0,12 s an 233 330 Kanten). Die Schiffskörper aus RM-181 liegen bei 7,9–18,3 s je 200 000 Dreiecke. Stapelumbau oder neu gefasstes Ziel entscheidet Robert (wie RM-132) |
| [RM-201 — Ein hohler Körper hält die 300 ms der Schichtanalyse nicht](#rm-201) | Geometrie, Erkennung und Druckvorbereitung | `slice_body` an der Hohlkugel 40 % schneller (`546eff16`: Stapelung, Inselzertifikat, Säulen auf Arbeitern, direkte Ringe), hochgerechnet rund 0,65 s auf der Referenzmaschine — 300 ms nicht erreicht; der Rest ist die Breitensuche mit sieben Öffnungen je Schicht. Robert gibt C++ frei (23.09.): native Breitensuche als eigener Bauauftrag; womit (eigene Mitre-Offsetfunktion in `_chain.pyx` oder Clipper2 über Cython), entscheidet Robert |
| [RM-212 — Die Vorschau großer Teile hält den Hauptthread und rechnet vergeblich](#rm-212) | Geometrie, Erkennung und Druckvorbereitung | GIL beim ersten Verkleinern (0,57–2,0 s), sechs vergebliche Kernschritte vor dem Raster (bis 4,8 s), genaue Vorschau großer Teile 8–37 s — Raster vorziehen, simplify aus dem Hauptthread, lokaler Tausch des Hohlraums |
| [RM-216 — Ein erzeugtes Flächenmerkmal behält nach einer Änderung seine alte Fläche](#rm-216) | Geometrie, Erkennung und Druckvorbereitung | Nach einer Bohrung trägt face_top weiter 2 400 statt 2 349,878 mm² — Kennzahlen gebauter Merkmale aus den nachgeführten Dreiecken neu messen (Sonde s35_stale_area) |
| [RM-217 — Die Zuordnung meldet doppelt und fragt ohne Bild](#rm-217) | Geometrie, Erkennung und Druckvorbereitung | Formen-Beispiel auf acht Hinweise gebündelt, alle Kennungen und Zahlen bleiben erhalten. Offen: remove_feature.gone und perceive.orphaned doppelt, orphaned nach Teilen, Frage unter der Deckfläche, altes Merkmal ohne Markierung — _with_features filtert, question_context trägt das alte Merkmal |
| [RM-218 — Am exakten Körper heißen Bohrungen nach ihrer Lage, und der Verlauf lässt sich dort nicht umbauen](#rm-218) | Geometrie, Erkennung und Druckvorbereitung | drill_brep_hole nummeriert nach Lage; Verschieben und Einfügen sagen an build_tray_v3.step ab — eindeutige geometrische Zuordnung behält den Namen wie am Netz |
| [RM-222 — Die Erkennung einer Durchbohrung am Netz hängt an der Vorgeschichte](#rm-222) | Geometrie, Erkennung und Druckvorbereitung | Besenhalter: gleiche Geometrie, mit vorherigem Vergrößern eine Bohrung weniger — beide Stände als Korpusfall, Stelle eingrenzen |
| [RM-225 — Das Muster eines echten Schraubdeckels lässt sich nicht sauber ändern oder entfernen](#rm-225) | Geometrie, Erkennung und Druckvorbereitung | Gewürzdeckel: nach Teilung ändern 124 Flächen und kein Muster, nach Entfernen 31 Zusatzflächen und 1,7 mm³ Überlappung — Feld begrenzen, Stirnkappen verschmelzen |
| [RM-226 — Netz und exakter Kern nennen dieselbe Fläche verschieden](#rm-226) | Geometrie, Erkennung und Druckvorbereitung | Gewölbte Oberseite exakt Verrundung, am Netz gekrümmte Fläche; Fläche versetzen lässt exakt eine koplanare Scheibe stehen — replaces_an_edge an den exakten Kern, gleiche Domäne vereinigen |
| [RM-227 — Eine Tasche am Teppichclip gibt einen ungültigen exakten Körper mit 0 mm³ Abtrag still zurück](#rm-227) | Geometrie, Erkennung und Druckvorbereitung | sketch_pocket Ø 11 an carpet-corner-clip.step: ungültig, 0 mm³, kein Befund — nach dem Schnitt mit profiles.is_sound prüfen und absagen, dann die Ursache |
| [RM-228 — Die Slicer-Übergabe lässt Lüfter und Spulen beim Hersteller](#rm-228) | Geometrie, Erkennung und Druckvorbereitung | Lüfterkurve gebaut; offen PLA-Vorgabe je Drucker, Hilfs- und Kammerlüfter, unbemalte Spulen aus alten Projekten — merge_slots nur benutzte, je Lüfterschlüssel entscheiden |
| [RM-229 — Anordnen legt ein zu großes Teil über die Kante, und geteilte Stücke heißen nach einem Buchstabenpfad](#rm-229) | Geometrie, Erkennung und Druckvorbereitung | 108,5 bei freigegebenen 108 statt einer Mitte mit kleinerem Rand; „B A · Stifte" für ein Stück mit Stiften und Löchern — Rand zuerst verkleinern, Nummerierung entscheiden |
| [RM-230 — Variable Verrundung und Formschräge: fünf Grenzen, die der Kunde merkt](#rm-230) | Geometrie, Erkennung und Druckvorbereitung | Anfang auf Ringen fest, gemischte Ecken exakt ungeprüft, Zwischenstellen nicht bindbar, Schräge an allen Wänden des Trays abgesagt — je Grenze bauen oder benennen |
| [RM-239 — Verschweißen entscheidet für das ganze Netz, nicht je Punktgruppe](#rm-239) | Geometrie, Erkennung und Druckvorbereitung | Siebhalter-Ring mit Riss: die Heilung überwiegt, 12 Eckpaare zu 0,015 µm werden zusammengelegt, 24 Dreiecke fallen — Gruppen nach Flächenblatt trennen, ohne Dreieckssuppen aufzureißen; Import- und Reparaturregel zusammenlegen |
| [RM-240 — Eine halbe Bohrungswand kommt als flacher Deckel zurück](#rm-240) | Geometrie, Erkennung und Druckvorbereitung | Lochplatte: Viertelwand kommt zurück, die halbe Wand schließt flach (4 → 3 Bohrungen, +25,9 mm³) — die Restwand als Zylinder fortsetzen, wo die Erkennung sie belegt |
| [RM-243 — Splinestücke von Schriftzügen und Streben werden als Verrundungen eingepasst](#rm-243) | Geometrie, Erkennung und Druckvorbereitung | Screen-Cover: 23 bis 25 Verrundungen mit wandernden Radien an den Buchstaben — Stücke eines Flecks mit stetig wanderndem Radius als Umriss erkennen, die Flaschentaschen des Flaschenhalters als Gegenfall |
| [RM-244 — Die Schnittsuche endet an Nadeldreiecken am Budget](#rm-244) | Geometrie, Erkennung und Druckvorbereitung | Besenhalter: 35 648 von 59 740 Dreiecken in 6,4 s geprüft — messen, welche Paare das Budget verbrauchen, dann vollständig unter dem Budget |
| [RM-238 — Lokale Formenerkennung aus dem Bericht und mit der Tastatur bedienen](#rm-238) | Bedienung und Darstellung | Berichtseinstieg und Tastatur-Fadenkreuz umgesetzt; native Release-Abnahme von Fokus, Treffern, Abbruch und Undo noch offen |
| [RM-070 — SpaceMouse auf macOS und Linux am echten Gerät abnehmen](#rm-070) | Bedienung und Darstellung | Die Rampe ist stetig und getestet, die Bildrate an 815 104 Dreiecken gemessen (`7ff34c67`: 16,7 → 8,7 ms im Median); offen bleiben Linux, die 3DxWare-Mausemulation, das Gerät selbst und die Rampe im Skizzenmodus (aus RM-183) |
| [RM-204 — Ein Merkmalklick baut alle Handlungen des Fensters neu](#rm-204) | Bedienung und Darstellung | Gebaut (`85dec7cb`): Zeilen je Signatur wiederverwendet (`_ActionRow`, `configure_feature_field`), Kernauskunft je Merkmal und Auswertung gemerkt; `show_feature` 41 → 12 ms, Wiederklick 8 ms, Klick bis Ruhe 391 → 140 ms (offscreen). Offen: Abnahme am echten Fenster beim Release (RM-213) |
| [RM-205 — Escape in der dritten Stufe der Platzierung springt in den Dialog](#rm-205) | Bedienung und Darstellung | Gebaut (`7ff34c67`, `29dcefa4`): Escape geht je Stufe genau eine zurück (Tiefe → Maße → Zielen → Dialog), ein Klick ins Modell und der Knopf „Stelle im Bild wählen“ führen aus dem Dialog zurück, `surfaceRequested` hat seinen Sender; getestet je Stufe. Offen: Abnahme am Fenster beim Release (RM-213) |
| [RM-183 — Zeichenmodus am Fenster abnehmen](#rm-183) | Bedienung und Darstellung | Führen mit gezeichneter Bahn und Überblenden mit gezeichnetem Umriss am Fenster gefahren (`f19a7b4b`, sechs Fehler behoben), Tabulatorfolge, Bildschirmleser und Trennstriche im dunklen Thema (2,30:1) gemessen; offen allein die Rampe der 3D-Maus am echten Gerät — ob dieser Rest in RM-070 aufgeht (dasselbe Gerät) und der Punkt damit schließt, entscheidet Robert |
| [RM-084 — Kundentexte gegen die vereinbarte Sprache prüfen](#rm-084) | Bedienung und Darstellung | Welle 2 (`9145aedc`) und die Gebietsdurchsichten haben die in der Sollliste benannten Stellen, Preise, Generatoraussage, Sicherheit, Agentenquote und Sprachkonsistenz nachgezogen; offen ist der erschöpfende Durchgang durch jeden Anwendungs- und Websitetext, dazu Presse A16/A23 und die C12-Namen |
| [RM-088 — Verständlichkeit für Laien im Regelwerk verankern](#rm-088) | Bedienung und Darstellung | Die Regel steht in `oberflaeche.md`, mit den Slicer-Ausnahmen; 23 Konstrukteurswörter außerhalb der Sitzung gefunden (`face_ops.py` 10× „Normale“, `mesh_ops.py`, `range_check.py`, `viewport.py:726`, englische Werte vertices/watertight/boolean/facets/voxel) — Robert gibt die Formulierung frei, dann tauschen und die Prüfung als Test mit Ausnahmeliste einchecken |
| [RM-090 — Serie zum Übergabestatus entscheiden](#rm-090) | Bedienung und Darstellung | Nächsten Umfang aus den fünf Vorschlägen des Produktkompasses entscheiden |
| [RM-131 — Zurückgestellten Mehrfachimport entscheiden](#rm-131) | Bedienung und Darstellung | Zurückgestellt; mehrere gezogene Dateien werden seit 0.5.0 angesagt statt still verworfen (`84185f4d`), geöffnet wird weiter nur die erste |
| [RM-135 — Zugewiesene Höhe der Filamentkarte vollständig nutzen](#rm-135) | Bedienung und Darstellung | Windows-Stand nachgemessen am 23.09.2026 (Overlay- und Kartentests grün); offen nur der macOS-Prüflauf |
| [RM-136 — Gezeichnetes Fensterschema und Bildbeschreibungen aktualisieren](#rm-136) | Bedienung und Darstellung | Quelle nachgezogen (`84185f4d`: Kopfzeile, Fenster „Auswahl“ mit Handlungen, Alt-Text in allen Sprachen); Erzeugung und Sichtprüfung je Sprache beim Release |
| [RM-174 — Der Geist beim Zug an einem Bausteinmerkmal zeigt nur dieses Merkmal](#rm-174) | Bedienung und Darstellung | Gebaut (`7ff34c67`): Beim Zug an einem Bausteinmerkmal wandert der ganze Baustein, neben der Fläche wird er rot, und das Zugfeld sagt ‚neben der Fläche‘; offscreen getestet. Offen: Abnahme am echten Fenster beim Release (RM-213) |
| [RM-175 — Bauplan §30.1 um Winkel, gleich, Mittelpunkt, Vieleck und Langloch nachtragen](#rm-175) | Bedienung und Darstellung | Nachtragstext für §9 und §30.1 liegt im Bericht skizze der Durchsicht 0.5.0 bereit (neu geschrieben, der Wortlaut W2 lag nicht mehr vor), dazu die Vorschläge aus p66 (Ellipse, drei Bedingungsarten), p6c (drei Schnitte), zeichnenbau und p7verlauf. Robert sagt den Nachtrag an und entscheidet dabei, ob eine neue Bedingungsart die Formatversion hebt (p66 hat sie mit Format 31 gehoben, Satz 5 des Nachtrags sagt nein) |
| [RM-197 — Maßeditor im Bild: kein Bezugswechsel am Etikett, Beschriftungen mit Abstand zum Modell](#rm-197) | Bedienung und Darstellung | Umgesetzt und im Review vom 21./22.09.2026 nachgezogen (Griff überlebt ein Bild mitten im Zug, Radraste über einem Maßfeld zoomt, erstes Escape nimmt nur die Bezugswahl zurück); die Fensterdateien der Ansicht liefen dabei grün (456 Fälle). Offen bleibt allein die Abnahme am echten Fenster beim Release 0.5.0 |
| [RM-198 — Eine feine Fenstermaske über der Vulkan-Fläche verliert das Gerät](#rm-198) | Bedienung und Darstellung | Behoben an der Wurzel: Die Maßtinte liegt seit `ad3deadd` im Renderer, seit dem Review mit fester Kapazität (sieben Elemente, nur die Punkte wechseln) und unter `draw_order` vor dem Material; die Maske ist weg. Offen: die Probe über den echten Startweg beim Release 0.5.0 noch einmal fahren, und ob Windows D3D12 als Backend bekommt, bleibt eine eigene Entscheidung |
| [RM-199 — Der Durchmesser steht doppelt: im Bild und rechts im Auswahlfenster](#rm-199) | Bedienung und Darstellung | Eingelöst in `b25167fd`, und im Review ganz: Auch der Block des historischen Bohrschritts weicht, solange die Maße im Bild stehen (`offer_bore_step` trägt `_blocks`). Abnahme beim Release 0.5.0: Bohrung an Weg 1 wählen, rechts kein Durchmesser, keine Koordinaten; endet die Maßgruppe, stehen sie wieder (Escape wählt seit dem 25.09.2026 ab); auch für die nächste Bohrung und Escape offscreen belegt (`85dec7cb`) |
| [RM-200 — Ein Zug am Griff soll flüssig sein](#rm-200) | Bedienung und Darstellung | Roberts Geste nachgestellt und verlegt (`7ff34c67`: je Bewegung 13,6 → 8,8 ms, das Loslassen 89–134 → 25–57 ms, Griff und Maße nach dem Klick 9–21 s → 1–2,4 s, leichte Verdeckung im Zug 4 × 2); offen ist allein, ob es sich am echten Fenster flüssig anfühlt (Release, RM-213) |
| [RM-213 — Fensterabnahme 0.5.0 und die Kundenwege am echten Fenster](#rm-213) | Bedienung und Darstellung | Beim Release: die offscreen belegten Änderungen am echten Fenster, die Kundenwege C14/A13/A4/C5/C1 und die vier Hauptwege mit Zeiten; vorher Release-Tor mit allen neuen Fensterdateien und frischem Bereichsnachweis |
| [RM-215 — 276 Befundstellen enden ohne Handlung](#rm-215) | Bedienung und Darstellung | Sollliste C1: 97 Warnungen und sieben Fehler ohne Weg, darunter fit.violated, gcode.spool_left_out, join.blocked, orient.support_likely — Test für alle, dann gebietsweise nachziehen |
| [RM-232 — Die Klickkette an einem Merkmal rechnet noch im Hauptfaden](#rm-232) | Bedienung und Darstellung | Erster Klick: Kernauskünfte im Arbeiter, Hauptfaden 172 → 36 ms, längste Lücke 171 → 52 ms; keine Zwischenbilder mehr (Ansicht bestellt ihr Bild, Maßkarte wartet auf ihren Platz). Am echten Fenster bleibt Bohrung zu Bohrung bei 350 ms: 140 native Widgets über der Grafikfläche, die Maßgruppe baut je Klick neu |
| [RM-233 — Fünf Kleinigkeiten aus den Durchsichten, am Code bestätigt](#rm-233) | Bedienung und Darstellung | autosave wirft im Zeitgeber, Skizzen-Kontextmenü wird nie freigegeben, Objektnamen in der Sprache des Augenblicks, „Schwerpunkt" statt Hüllquadermitte, Rückfragekarte fest 520 Punkte |
| [RM-003 — Lizenzkette der gepinnten TripoSG-Bestandteile klären](#rm-003) | KI und Generatoren | Lizenzkette der eingesetzten Modellrevisionen klären; die Startseite sagt seit `9145aedc` wie die KI-Seite, dass Solidon TripoSG und SDXL auf Wunsch einrichtet und die Kette geprüft wird, die README ‚wird derzeit geprüft‘ statt ‚MIT, Quelltext wie Gewichte‘ (Robert, 23.09.2026) |
| [RM-004 — Echte Text- und Bildgenerierung über alle Zielplattformen abnehmen](#rm-004) | KI und Generatoren | Echte Text-/Bildläufe auf Windows, macOS und Linux dokumentieren |
| [RM-014 — Zusätzliche Formenregel und zugehörige Suite-Abnahme entscheiden](#rm-014) | KI und Generatoren | Zusätzliche Formenregel entscheiden; bei Änderung Suite vorher/nachher |
| [RM-016 — Agenten-Suite gegen das aktuelle Vorgabemodell messen](#rm-016) | KI und Generatoren | Suite mit festgehaltenem aktuellem Modell und vergleichbarer Referenz messen; lokal gemessen am 23.09.2026 (dienste, qwen3:14b, Regelversion der Durchsicht): 21/39, gefragt 3/3, schemagültig 75 %, Baustein 4/13; der gehostete Vorgabeweg ist nicht gefahren (Geld) |
| [RM-081 — Ollama-Laufzeit und verbleibende Optimierungen abnehmen](#rm-081) | KI und Generatoren | Latenz auf ruhiger Karte gemessen (19,8 s kalt, 2,5 s warm, 100 % VRAM bei `num_ctx` 32 768), der Lauf ohne Denkblock gemessen und verworfen (14/39 statt 21/39); offen sind Warmhalten zwischen den Zügen (Hardwarerisiko, Robert), `q8_0` (nur als Dienstvariable) und die gestufte Werkzeugauswahl als Entscheidung |
| [RM-173 — Der Platz im Kontextfenster des lokalen Modells geht aus](#rm-173) | KI und Generatoren | Denkmodus entschieden (bleibt an), Flächenliste im Steckbrief gebaut, großer Steckbrief verdichtet (`736d4a46`); offen: Warmhalten und `q8_0` bei RM-081, der CC2-Werkzeugkasten (fünf Körper) passt verdichtet mit 18 077 Zeichen noch nicht mit Verlauf ins Fenster, und die Neumessung von `PROMPT_TOKENS` auf dem Weg zu 0.5.1 (RM-185) |
| [RM-185 — Das kompakte Werkzeugschema passt nicht mehr ins Fenster des lokalen Modells](#rm-185) | KI und Generatoren | Seit `736d4a46` 27 293 Token bei 147 Werkzeugen, `num_ctx` wieder 32 768, 100 % VRAM, Quote gehalten; seither sind Werkzeuge dazugekommen (zuletzt 28 040 bei 148 gezählt). Nach Roberts Entscheidung vom 23.09. nicht vor 0.5.0, sondern vor 0.5.1: neu messen mit `tools/measure_local_model.py --count-tokens --model qwen3:14b` auf ruhiger Karte, `PROMPT_TOKENS` und `PROMPT_TOOL_COUNT` (mit `agentenschicht.md`) fortschreiben und die nicht strenge xfail-Marke des Zählvergleichs entfernen; dazu das Schema unter 28 000 Token kürzen |
| [RM-020 — Sicherung der eigenständigen Druckprojekte belegen](#rm-020) | Tests und Entwicklungswerkzeuge | Sicherungsweg entscheiden und Wiederherstellung belegen |
| [RM-099 — Konzeptbestand und veraltete Verweise ordnen](#rm-099) | Tests und Entwicklungswerkzeuge | Verweise sind vollständig gültig; offen ist nur noch das Umräumen — Umfang entscheidet Robert |
| [RM-103 — Große Kernfunktionen nach konkretem Wartungsbedarf aufteilen](#rm-103) | Tests und Entwicklungswerkzeuge | Auswertung und weitere große Funktionen nach Wartungsbedarf priorisieren |
| [RM-113 — Besitzerprüfung der Tokendatei auf dem Windows-Runner belegen](#rm-113) | Tests und Entwicklungswerkzeuge | Diagnose gebaut (`736d4a46`: SIDs genannt, Prozessnutzer angenommen); offen der Beleg auf dem CI-Runner (das Repository ist nur beim Release öffentlich) |
| [RM-134 — Zusammenführung duplizierter Testhilfen entscheiden](#rm-134) | Tests und Entwicklungswerkzeuge | 41 wortgleiche Gruppen gemessen, vier nach `tests/helpers.py` zusammengeführt (`920c609a`); offen die Fensterfixtures (`window`, `with_a_body`, `on_the_bore_wall`) — Robert entscheidet über die großen |
| [RM-137 — Sitzungsende im tatsächlichen Editorbetrieb abnehmen](#rm-137) | Tests und Entwicklungswerkzeuge | Echtes SessionEnd und Freigabe des Sitzungsgebiets nach Neustart beobachten |
| [RM-214 — Die Bereichsprüfung ohne VTK hat keinen Index und keinen Wächter](#rm-214) | Tests und Entwicklungswerkzeuge | Wandmessung O(n²) für große eigene Bausteine, kein Test gegen vtk-Importe, vtk noch in der .venv — Index wie intersections.py, Wächter über sys.modules |
| [RM-234 — Linux-Fensterabnahme und macOS-Gegenprobe nachweisen](#rm-234) | Tests und Entwicklungswerkzeuge | Gepinnter Ubuntu-Releasejob 107485122706 erreicht die Fensterverträge und besteht; „Neueste Versionen" enthält heute nur Kerntests. Der vollständige macOS-Taglauf 35982366247 ist grün; offen bleibt die unabhängige Ergebnismeldung der Fensterverträge bei rotem Kernschritt |
| [RM-002 — netcup-AVV und Freigabe der Rechtstexte belegen](#rm-002) | Veröffentlichung, Betrieb und Vertrieb | netcup-AVV belegen und zugehörige Rechtstexte fachlich abgleichen |
| [RM-006 — Nächsten messbaren Schritt für die Sichtbarkeit festlegen](#rm-006) | Veröffentlichung, Betrieb und Vertrieb | Plan bis 01.11. mit Takt und Messpunkten liegt vor (`marketing/reichweite/analyse-und-plan.md`, `36487f9b`); drei Facebook-Beiträge für 24., 26. und 28.09. in der Meta Business Suite eingeplant; YouTube-Änderungen (14) freigegeben, in Studio nicht umgesetzt; Video V3 freigegeben, nicht gedreht. Offen: Roberts Fragen im Bericht Reichweite und die erste Montagsmessung; der Punkt schließt, wenn Robert den Plan bestätigt |
| [RM-008 — DMARC-Eintrag öffentlich prüfen und gegebenenfalls einrichten](#rm-008) | Veröffentlichung, Betrieb und Vertrieb | DMARC einrichten und legitimen Mailversand prüfen |
| [RM-030 — Impressum nach Vergabe einer USt-IdNr. oder W-IdNr. ergänzen](#rm-030) | Veröffentlichung, Betrieb und Vertrieb | Bereits vergebene USt-IdNr./W-IdNr. klären; gegebenenfalls Impressum ergänzen |
| [RM-034 — Versicherungsschutz für Software und Produktschäden klären](#rm-034) | Veröffentlichung, Betrieb und Vertrieb | Versicherungsangebote gegen die tatsächlichen Risiken prüfen lassen |
| [RM-035 — EULA wirksam in den Bestellvorgang einbeziehen](#rm-035) | Veröffentlichung, Betrieb und Vertrieb | Produktgrenzen und EULA im vollständigen Bestellweg rechtlich prüfen |
| [RM-036 — Vertrag und Freistellungen des Zahlungsdienstleisters prüfen](#rm-036) | Veröffentlichung, Betrieb und Vertrieb | Konkreten Anbietervertrag und Haftungsübernahme entscheiden |
| [RM-061 — Verkaufsbereitschaft und Ende der Demo vorbereiten](#rm-061) | Veröffentlichung, Betrieb und Vertrieb | Kandidat bis 25.10.; letzte Optimierungen 31.10.; Start 01.11.2026 um 10:00 Uhr deutscher Zeit — gebaut in 0.5.0: Abschied mit Pause und Start, ‚heute letzter Tag‘, Hinweis ab 24.10. (`29dcefa4`); offen täglicher Ablaufwächter und Bestell-Webhook |
| [RM-091 — CRA-Meldebereitschaft herstellen, die Frist ist abgelaufen](#rm-091) | Veröffentlichung, Betrieb und Vertrieb | Meldeweg entschieden (Robert, 23.09.2026: über die Support-Adresse, Antwortfrist zwei Arbeitstage, keine Belohnung, kein PGP; `SECURITY.md`, `SECURITY-INCIDENT.md` und `security.html` sind konform); offen EU-Login, Vertretung, Alarmierung und Probelauf — Roberts Konten |
| [RM-092 — Verkaufskonzept für den geplanten Start abschließen](#rm-092) | Veröffentlichung, Betrieb und Vertrieb | Preis bestätigt am 23.09.: zwei Lizenzarten, privat 69 € bis Ende Januar, ab Februar 99 €, gewerblich 199 €, ab Februar 249 €; ‚drei Stufen‘ ist aus Presse und Texten gestrichen (`9145aedc`). Offen: Anbieter, Bestellstrecke, Lieferung, Widerruf und Signierung bis 15.10. |
| [RM-093 — Noch fehlende Angaben und Prüfungen der Rechtstexte klären](#rm-093) | Veröffentlichung, Betrieb und Vertrieb | Fehlende Anbieter-/Rechtsentscheidungen und Sprachfassungen fachlich prüfen |
| [RM-095 — Automatischen Löschlauf auf dem Server belegen](#rm-095) | Veröffentlichung, Betrieb und Vertrieb | Server-Löschlauf, Sicherungen und Ausfallalarm tatsächlich nachweisen |
| [RM-116 — Historische Statistikreste auf dem Server behandeln](#rm-116) | Veröffentlichung, Betrieb und Vertrieb | Öffentlichen Altbestand prüfen und Umgang mit alten Statistikzeilen entscheiden |
| [RM-145 — CRA-Konformitätsakte zum gesetzlichen Anwendungszeitpunkt vorbereiten](#rm-145) | Veröffentlichung, Betrieb und Vertrieb | Produktklassifizierung, technische Akte und Konformitätsverfahren für 2027 vorbereiten |
| [RM-038 — Mailrückfall ohne prozentkodierten Berichtstext prüfen](#rm-038) | Kundenrückmeldungen | mailto-Weg gebaut, Rückfall ohne Mailprogramm sagt, was jetzt geht, lange Berichte werden gekürzt (`29dcefa4`, `736d4a46`); offen der Portalweg im ausgelieferten Flatpak |
| [RM-040 — Kundenfehler mit Traceback und betroffener Datei zuordnen](#rm-040) | Kundenrückmeldungen | Aktuellen Kundenbericht mit Traceback und betroffener Datei reproduzieren |
| [RM-062 — Eingabemethode im aktuellen Flatpak bestätigen](#rm-062) | Kundenrückmeldungen | Start, Fokus und IME am aktuellen Flatpak bestätigen |
| [RM-064 — Slicerübergabe zwischen zwei echten Flatpaks abnehmen](#rm-064) | Kundenrückmeldungen | Modell zwischen installiertem Solidon- und Slicer-Flatpak übergeben |
| [RM-072 — Zusagen an den Dental-Kunden zum Verkaufsstart erfüllen](#rm-072) | Kundenrückmeldungen | Kaufweg und belastbare 3D-Maus-Unterstützung zum zugesagten Anlass mitteilen |
| [RM-231 — Der Fehlerbericht aus dem Fenster geht ohne Schwärzung hinaus](#rm-231) | Kundenrückmeldungen | report_error nimmt format_exception ungeschwärzt (main_window.py:19698) — über log.exception_text, Test mit Benutzerpfad |

## Filamentlager

Löschen ist im Regal per Rechtsklick und im Spulendetail sowie Filamentpanel
über einen Mülleimerknopf erreichbar; Wiederherstellen läuft über das Archiv.
Hinzufügen trägt ein Plus-SVG. „Erste Schritte“ führt über Slicer und passende
Drucker zum Filamentlager; eigene Drucker lassen sich mit Name, Bauraum und
Düse direkt anlegen.

Physische Spulen, Regal, bewusster Import, Schnellauswahl und rücknehmbare
Verbrauchsbuchungen sind angeschlossen. [Review und Nachweis zu RM-146](ROADMAP-ARCHIV.md#rm-146).
Das anschließende [Gestaltungs- und Gesamtreview](konzepte/review-filamente-2026-09.md)
behandelt Abwahl, Herstellerprofile, Buchungskorrekturen und die weiteren Anschlüsse.
Eine Spule trägt bis zu vier Farben. Die Durchsicht vom 19.09.2026 (vier
Fehler, vier Regelverstöße, neun Bedienmängel, sieben Textmängel) ist
vollständig behoben: Eine Bearbeitung der Angaben zählt nicht mehr als
Bestandsfeststellung, eine automatische Buchung nach einer Rücknahme bucht
wirklich, eine abgewiesene Spule kommt in den Dialog zurück, die Übernahme aus
dem Slicer überschreibt keine Handspule, Rücknahmen sind rücknehmbar, das Lager
sichert seinen letzten lesbaren Stand selbst, Datumsfelder haben einen Kalender.

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

Windows, Flatpak, AppImage und beide Mac-Architekturen sind als 0.5.0 veröffentlicht.
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

Der optionale exakte Kern und STEP-Austausch sind umgesetzt. Das ist keine allgemeine Rückgewinnung exakter CAD-Flächen aus beliebigen Netzen. Der Nachbau als Operationsfolge ist seit dem 17.09.2026 beschlossen; Umfang und Abnahme stehen in RM-022, die Umsetzung startet nach 0.4.4 als Teil des CAD-Plans (RM-188).

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

<a id="rm-001"></a>

RM-001 ist mit der Auslieferung von 0.5.0 abgeschlossen.
[Nachweis und bisheriger Verlauf](ROADMAP-ARCHIV.md#rm-001-abschluss-050).

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
  sichtbar wird er beim Herunterfahren ([[absturz-frame-ist-die-naechste-allokation]]).

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
  Nachweis: `F:\3D Druck\Releases\0.5.0\Nachweise\review-050\reports\codex-ci-notices-fix.md` (67 Lizenztests,
  Generatorprüfung und Umgebungsprüfung jeweils Exit 0). Die Folgen des VTK-Ausbaus (Wandmessung ohne
  räumlichen Index, fehlender Wächter gegen VTK-Importe) stehen als RM-214.
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
  inzwischen das **0.4.0**-Flatpak, Laufzeit unverändert 26.08; offen bleibt der reale
  Linux-Lauf mit Grafik, Qt, Dateizugriff und Offline-Start.

  **Zur Compilerfassung, nachgemessen am 10.09.2026:** Die CI sucht ISCC auf dem PATH und
  nimmt 7 vor 6 — der Kommentar daneben hält fest, dass das Runner-Image heute **6** trägt.
  Gebaut wird also mit Inno Setup 6, und die Fassung wird **nirgends protokolliert**: kein
  Versionsaufruf vor dem Bau, kein Eintrag in der Releaseakte. Der Punkt sagte „für Inno Setup
  7" und meinte damit eine Fassung, die dort gar nicht läuft. Ein `ISCC`-Versionsaufruf vor dem
  Bau wäre der Beleg, der fehlt. Dazu Installieren, Aktualisieren und Deinstallieren auf einem
  fremden Windows. Abnahme mit Paket-/Compilerfassung und Feldprotokoll.

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

## Geometrie, Erkennung und Druckvorbereitung

<a id="rm-017"></a>

- [ ] **RM-017 — Nutfedermaße an realen Aluminiumprofilen prüfen.** Stegdicke und Kammertiefe an je
  einem konkret benannten 2020-/Nut-6- und 3030-/Nut-8-Profil nachmessen und die Nutfeder daran
  prüfen. Abnahme: Hersteller/Profil und beide Messwerte samt Passungsprobe dokumentiert;
  Abweichungen herstellerspezifisch einordnen, nicht aus zwei Proben allgemeine Normmaße ableiten.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-nutfeder-und-zwei-fehler-auf-dem-weg-dorthin-20082026).

<a id="rm-022"></a>

- [ ] **RM-022 — Nachbau als Operationsfolge.** Robert hat den Umfang am
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

<a id="rm-209"></a>

- [ ] **RM-209 — Die Rundform-Einpassung an Gittermodellen: der Löser ist nicht zu langsam,
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

<a id="rm-210"></a>

- [ ] **RM-210 — Dasselbe Modell, anders im Raum gelegt, ergibt andere Merkmale.** Gemessen am
  22.09.2026: `Elegoo_erster_Druck.3mf` (227 244 Dreiecke) liefert 166 Merkmale. Derselbe Körper
  um 13,7 mm verschoben — keine Drehung, keine Skalierung — liefert 164: ein Kegel und eine
  Verrundung fehlen. Um 90 Grad um die Z-Achse gedreht ebenfalls 164, um 37 Grad um (1,2,3)
  dagegen 171, also fünf Verrundungen und ein Kegel mehr. An der Kumiko-Schale sind es 7 325
  gegen 7 320 (gedreht um 90 Grad) und 7 327 (gedreht um 37 Grad). `countercleaner.3mf` bleibt
  bei 60 Merkmalen, aber seine Verrundungsradien wandern in der vierten Nachkommastelle
  (1,199937 → 1,199869 mm).

  **Die Gegenprobe ist gefahren und sie ist sauber:** Zweimal hintereinander am unveränderten
  Körper erkannt, kommen beide Male dieselben Merkmale heraus. Die Erkennung ist deterministisch;
  was sie nicht ist, ist unabhängig von der Lage.

  **Die Kippstelle ist bis auf den einzelnen Fleck eingegrenzt.** Bei der Verschiebung um 13,7 mm
  zerfällt der Körper in exakt dieselben Flecken, und von 202 Kegelfits antwortet genau **einer**
  anders — ein Fleck mit 32 Dreiecken, hier ein Kegel von 53,501825 Grad mit Rückstand 4,957·10⁻⁴,
  dort keiner. Sein Startwert ist in beiden Lagen Bit für Bit derselbe, denn `_fit_cone_read`
  zentriert auf den Schwerpunkt und normiert auf die Fleckausdehnung; die Verschiebung fällt also
  heraus. Was bleibt, ist die Rundung in `support.points - origin`: Bei großen Koordinaten ist
  diese Differenz nicht exakt. Und beide Läufe brauchen hundert Auswertungen — der Fleck stand
  ohnehin an der Kippe.

  **Daraus folgt der Vorschlag, und er ist fachlich begründet statt numerisch: Ein Fit, der sein
  Auswertungsbudget ausschöpft, hat nicht konvergiert.** Ob am Ende trotzdem ein Ergebnis
  dasteht, entscheidet dann die Lage des Körpers — es ist keine Aussage über die Geometrie. Wer
  ihn verwirft, verliert keine Erkenntnis, sondern einen Zufall. Über die 71 Korpusdateien
  gemessen trifft die Regel sehr wenig: Von 173 Läufen an `Elegoo_erster_Druck.3mf` enden 49 am
  Limit, aber nur **einer** davon mit Ergebnis; an `countercleaner.3mf` sind es 6 von 167, an
  `garden-hose-holder.3mf` 14 von 1 276. Vier Dateien ändern sich, und an der ersten sind es
  **genau die beiden Merkmale, die beim Verschieben ohnehin verschwinden** — `cone_7` und
  `fillet_21`. Die Regel trifft also, was sie treffen soll. Zeit spart sie kaum (14,5 → 13,0 s an
  `countercleaner.3mf`), denn der Lauf läuft trotzdem; sie macht das Kriterium scharf, an dem
  RM-209 und RM-208 messen.

  Offen bleibt die Mehrzahl der Abweichungen: Die Verrundungen stellen sie, und die kommen nicht
  aus `fit_cone`.

  Was daran wiegt: Ein Kunde, der sein Teil auf der Platte anders ablegt, bekommt einen anderen
  Steckbrief. Und da ARM anders rundet als x86, kann dasselbe Modell auf zwei Rechnern
  verschieden gelesen werden — die Zusage „Plattformen funktionieren gleich" ist damit nicht
  eingelöst.

  **Die Regel ist seit dem 22.09.2026 gebaut (RM-209), und sie trägt genau so weit, wie sie
  kann.** Gemessen an 39 echten Modellen, beide Stände als fester Commit in eigenen Bäumen
  (`4fa4d38f` gegen `6c3b1e5c`), jedes Modell dreimal bewegt:

  | Bewegung | vorher | nachher |
  |---|---|---|
  | ungleichmäßig verschoben | 1 | 1 |
  | gleichmäßig verschoben | 3 | **0** |
  | gedreht | 16 | 16 |
  | betroffene Bewegungen | 20 | **17** |

  **Die Zahl der betroffenen Modelle bleibt 16 — dieselben sechzehn.** Was sinkt, ist die Zahl
  der Bewegungen, unter denen sie kippen: Die gleichmäßige Verschiebung ist vollständig
  behoben, `Elegoo_erster_Druck.3mf` und `elegoo_grease_tool.3mf` wackeln nur noch beim Drehen,
  am Gartenschlauchhalter fällt eine von drei Bewegungen weg. Das passt zur Ursache: Ein Lauf
  am Auswertungslimit kippt, wenn sich die Koordinaten leicht verschieben; eine Drehung ändert
  mehr und trifft andere Schwellen — vor allem die der Verrundungen, und die kennen keinen
  Löser.

  Ein früherer Zwischenstand meldete an `countercleaner.3mf` und `bottom-double.stl` **neue**
  Lageabhängigkeit. Das war ein Messfehler derselben Familie: Der Vorher-Lauf lief, während die
  Nachbarsitzung ihren Umbau noch ungestaged im Baum hatte. Gegen feste Commits gemessen
  verschlechtert sich kein Modell.

  **Die Entscheidung, die offen ist: ein Mindestbogen für Rundformen.** Sie ist keine
  Numerikfrage, sondern eine über das Erzeugnis, und deshalb steht sie hier und wird nicht
  nebenbei gebaut. Was heute passiert: Ein Fleck aus acht Dreiecken mit 0,03 Millimetern
  Wölbung zeigt 2,8 Grad eines Kreises, und daraus extrapoliert die Einpassung einen Radius von
  99 Millimetern. Die Grenze dafür ist `FLAT_ANGLE` = 0,5 Grad, und daran kommt so ein Fleck
  bequem vorbei. Für einen Drucker ist das keine Rundung, sondern eine Kante.

  Gemessen, wieviel Kreis eine Verrundung zeigt:

  | Herkunft | überstrichener Bogen |
  |---|---|
  | `block_with_rounded_edge.stl` (konstruiert) | 86,25° |
  | `desk-organizer-v3`, die zwei echten | 82,7° bis 85,9° |
  | `drill-holder.3mf`, 26 gemeldete | median 151,5°, kleinste 4,6° |
  | die wackelnden Flecken | 2,0° bis 18,3° |

  Drei Wege, und jeder kostet etwas anderes:

  * **Nichts ändern.** Die Artefakte bleiben, und mit ihnen die Drehabhängigkeit an sechzehn
    von 39 Modellen.
  * **Konservativ, etwa 5 Grad.** Trifft am Organizer alle sechs wackelnden Flecken und keine
    der zwei echten Verrundungen. An `drill-holder.3mf` kostet es vier der 26 gemeldeten, an
    `Blessed+Family+–+Heart+Script+Decor.3mf` — einem Zierschild mit Schriftzug — sechs von 29.
  * **Streng, etwa 30 Grad.** Dann bleiben nur konstruierte Verrundungen übrig. Am Zierschild
    fielen 18 der 29 weg; ob das ein Verlust ist oder eine Bereinigung, hängt daran, ob seine
    Verrundungen mit median 15 Grad überhaupt gewollt sind.

  Eine feste Schranke trennt **nicht überall**: Am Zierschild überlappen die Bereiche
  vollständig (gemeldet ab 2,0 Grad, wackelig bis 18,3). Wer sie einführt, entscheidet also
  auch, dass an solchen Körpern weniger gemeldet wird.

  Abnahme: Entscheidung über den Mindestbogen; danach die Verrundungen ebenso eingegrenzt wie
  die Kegel — die Kippstelle ist bekannt (`_cylinder_contour`, `hull.geom_type`) —, und
  entweder die Erkennung gegen starre Bewegungen abgesichert oder die Grenze der Zusage
  dokumentiert. Ein Test, der einen Korpuskörper verschoben und gedreht einliest und
  dieselbe Merkmalsmenge verlangt, steht seit dem 22.09.2026 in
  `tests/test_fit_stability.py` — **er ist heute grün und bleibt stumpf**, solange kein
  eingecheckter Körper den Fall trägt: Alle 34 Korpuskörper sind stabil, weil sie analytisch
  gebaut sind. Zwei Versuche, einen wackelnden zu konstruieren (ein Feld gefaster Sechsecke,
  ein Feld verrundeter Bohrungsmündungen, beide auch durch eine STL geschickt), sind
  gescheitert: Der Effekt ist statistisch und braucht tausende Flecken an der Kippe.

  **Entschieden und gebaut am 23.09.2026** (erkennung B13–B16, `3fa7d719`):
  Unter `MIN_ROUND_ARC` = 5 Grad ist eine Rundform eine Kante, am Netz wie am
  exakten Kern (dort der native Umfang). Kosten: `drill-holder.3mf` vier von 26
  Verrundungen (alle 4,2 Grad), `garden-hose-holder.3mf` 67 von 293 (flache
  Streifen mit 1,6 bis 4,9 Grad) — teurer als geschätzt. Die Kippstelle der
  Verrundungen lag nicht an `hull.geom_type`, sondern an der Vereinfachung der
  Kontur (Douglas-Peucker hielt den Ringanfang fest, und der folgt der Lage) und
  an der Folge der Zusammenlegung; die Erkennung fragt ihre Flecken jetzt nach
  Größe statt nach Koordinaten. Lageprobe an 101 Körpern mit festen Ständen:
  vorher 27 lageabhängig (verschoben 1, 90° um Z 5, 37° um (1,2,3) 24), jetzt 17
  (0, 2, 17); umgekehrte Dreiecksfolge 101 von 101 gleich. Die Aussage oben, die
  Kippstelle sei bekannt (`_cylinder_contour`, `hull.geom_type`), ist damit
  berichtigt. Ob die übrigen Kippen weiter eingegrenzt werden oder das Handbuch
  die Grenze der Zusage „drehfest“ nennt, entscheidet Robert.

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

<a id="rm-164"></a>

- [~] **RM-164 — Creality Print: Erkennung steht, der Konsolenlauf ist ungeprüft.** Das
  Programm war installiert und wurde von Solidon gar nicht erkannt — `flavour_of` gab `None`,
  und damit war es im Druckdialog nicht wählbar. Es ist ab Version 6 ein Orca-Abkömmling:
  derselbe Profilbaum mit `machine_list`/`sub_path`, dieselben Schlüsselnamen; als `orca`
  behandelt findet Solidon in Version 7.2 **4234 Profile** (459 Maschinen, 1240 Prozesse,
  2535 Filamente). Seit dem 12.09.2026 steht es in `FLAVOUR_BY_NAME`, mit Fall in
  `tests/test_print_settings.py`.

  **Der Konsolenlauf ließ sich nicht abnehmen**: dreimal `0xC0000005` mitten im eigenen Start,
  vor jeder Modellverarbeitung. Das Programm war auf dieser Maschine allerdings **nie
  eingerichtet** — es stand im Dialog „Bitte wählen Sie den Softwaremodus" —, und ein Urteil
  über seine Kommandozeile auf dieser Grundlage wäre voreilig. Ein Absturz wird seither als
  Absturz gemeldet statt als „keine Druckdatei geschrieben" (`handover.crashed`), mit dem Rat,
  den Slicer einmal von Hand zu starten.

  Abnahme: Creality Print einrichten (Modus und Drucker wählen), dann drei Platten mit
  mehreren Spulen übergeben — einmal über *Im Slicer öffnen*, einmal über *Slicen*. Läuft der
  Konsolenweg auch dann nicht, gehört die Einschränkung benannt, statt sie den Kunden am
  Absturz erfahren zu lassen.

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

<a id="rm-184"></a>

- [~] **RM-184 — Dateiaudit vollständig umsetzen.** Grundlage sind 187 einzelne
  Modell-, Projekt- und Zeichnungsfälle aus `F:\3D Dateien` sowie ihre Begleitdateien.
  Die lokalen Nachweise liegen unter `ui-audit/2026-09-15-files/`.
  Robert hat den Umfang am 16.09.2026 auf den Abschluss der begonnenen Einheiten
  begrenzt und anschließend die vollständige Veröffentlichung von 0.4.3 beauftragt.
  Die übrigen Familien und die vollständige Einzeldateiabnahme bleiben zurückgestellt.

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

  **Für die Fortsetzung vorgemerkt, jetzt nicht beginnen:**

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

<a id="rm-186"></a>

RM-186 ist mit dem unbedingten Gewindebolzen-Kerntest im vollständigen grünen
Ubuntu-Lauf nachgewiesen; der zuvor behauptete Linux-Unterschied war nicht gemessen.
[Befund und Abschluss](ROADMAP-ARCHIV.md#rm-186).

<a id="rm-188"></a>

- [ ] **RM-188 — CAD-Ausbau, Bedienung und Resin für 0.5.x.** Beschlossener
  Gesamtumfang vom 17.09.2026 plus voller Ausbau vom 18.09.2026 („alles“),
  ergänzt am **23.09.2026** um Montageorganisation, Maßblätter und die
  vollständige Zuordnung aller vier von Robert übergebenen Konzepte.

  **Was in 0.5.0 steht und was danach kommt** (Robert, 22. und 23.09.2026): Die
  Entscheidung vom 22.09., P6 und P7 erst im Lauf der 0.5.x-Reihe zu liefern,
  ist am 23.09. ersetzt — **0.5.0 enthält die Durchsicht der ganzen 0.4er-Reihe,
  P4.0, P6.1 bis P6.7 und P7.1 bis P7.4**, dazu P3.2 bis P3.5 und die erste
  Etappe des Zeichenumbaus (Z0/Z1). **P8 (Montage und Maßblätter), P9
  (Resin-Stufe 2) und die Gesamtabnahme P5.3 folgen in 0.5.x**, wie seit
  `7c9f032b` eingetragen (Robert, 23.09.). Geprüfte Teilstände erscheinen in
  einzelnen 0.5.x-Versionen, ohne RM-188 vorzeitig zu schließen; der Punkt
  bleibt einer, bis P5.3 grün ist.

  **Nach 0.5.0: Auflösung der Netz-Kugel nach Größe.** Am Handschmeichler
  zeigte die Durchsicht formen, dass `create_sphere` mit der Vorgabe
  `segments=32` unabhängig vom Durchmesser nur 320 Facetten erzeugt. Bei
  70 mm Durchmesser liegt die Sehnenabweichung bei etwa 0,3–0,4 mm statt
  `units.MAX_FACET_SAG = 0,05 mm`; *Gleichmäßig vernetzen* erhält diese
  Facetten. Robert hat die Änderung ausdrücklich auf nach 0.5.0 verschoben,
  weil sie jede Netz-Kugel in bestehenden Projekten betrifft. Im Anschluss
  an P2.8 die Unterteilung aus Größe und zulässiger Abweichung herleiten,
  gespeicherte Schritte, Beispiele und Korpus mitprüfen. Abnahme: die
  Abweichungsgrenze über den Größenbereich belegen und Folgen für bestehende
  Projekte erklären. Die gebündelten Hinweise aus RM-217 ändern die
  Kugelgeometrie nicht.

  Die Pakete stehen am Ende dieses Eintrags als Liste mit Stand, in der
  Reihenfolge aus Konzept §13.10; die Paketstände für 0.5.0 stehen in der
  Tabelle darunter.
  Fachliche Quelle und Pakete P0–P9 (Pakete dieses Vorhabens, nicht die gleichnamigen Projektphasen):
  [CAD-Konzept](konzepte/konzept-vollwertiges-cad-2026-09.md) §§13–14,
  insbesondere §§13.11/14.4 für die Ergänzungen;
  [vertiefte Prüfung](konzepte/recherche-cad-paritaet-2026-09.md) vom 18.09.
  Es gelten dieselben Handlungen und Bedeutungen für Netz und B-Rep,
  verständliche Maßherkunft und erklärte Grenzen, ohne Kernwahl in der
  Oberfläche. Alle 31 bisher konvertierenden Bausteinpfade gehören dazu.
  Nachbau wird ausschließlich unter RM-022 geführt; RM-181, RM-183, RM-186
  und RM-187 behalten ihre speziellen Leistungs-/Fenster-/Plattformnachweise.

  **Verbindliche Quellen und ihre vollständige Abdeckung:**

  | Konzept | Umfang unter RM-188 | Abschlussnachweis |
  |---|---|---|
  | [Vollwertiges CAD](konzepte/konzept-vollwertiges-cad-2026-09.md) | Alle beschlossenen Pakete P0–P8, einschließlich bisherigem P6/P7-Ausbau, Montageorganisation und Maßblättern | Handlungsmatrizen, Fachabnahmen und installierte Kundenwege in P5.3 |
  | [Bedienung, Gestaltung und Zeichnen](konzepte/konzept-bedienung.md) | Gesamtes Dokument samt Nachträgen in P0.8 zuordnen; P0.7 führt die vier aufgegriffenen Reste, P0.3/P0.4/P5.1 die direkten Eingabewege | Alle noch geltenden Bedienanforderungen in P5.2/P5.3 prüfen, nicht nur die vier alten Restpunkte |
  | [Durchsicht der CAD-Konzepte](konzepte/durchsicht-cad-konzepte-2026-09.md) | Sämtliche geltenden Korrekturen, Empfehlungen und Nachträge zuordnen; §§3/7 bereits über CAD-Konzept §14.3 in P0.0/P0.7/P1.6/P2.1/P4.0 und Reihenfolge übernommen | P0.8 belegt die vollständige Zuordnung; Nachweise in den Fachpaketen, keine zweite Implementierung derselben Befunde |
  | [Vorstufe vor dem Resin-Slicer](konzepte/konzept-resin-2026-08.md) | Beide Stufen: Stufe 1 aus [RM-071](ROADMAP-ARCHIV.md#rm-071) erhalten, vollständige Stufe 2 aus §§5/9 in P9.1–P9.4 | Resin- und FDM-Gegenfälle, Orientierung/Öffnungen/Regeln/Übergabe, Agenten- und Release-Nachweise; Gesamtabnahme P5.3 |

  P0.8 hält je Anforderung Quellabschnitt, gültige Entscheidung, Paket oder
  vorhandenen RM-/Archivnachweis und verbleibende Abnahme fest. Historische
  Fehlerbeschreibungen werden am heutigen Code geprüft; bereits Erledigtes
  wird nicht neu gebaut. Ersetzte oder verworfene Vorschläge benötigen einen
  Entscheidungsbeleg. Keine geltende Anforderung darf ohne Zuordnung bleiben.
  **P5.3 schließt erst, wenn diese Abdeckung für alle vier Dokumente belegt
  ist**, einschließlich Bedienkonzept und Resin-Stufe 2.

  Auf `2148ddfa` zusätzlich reproduziert: exakte Spiegelung verliert sechs
  Merkmale; Skalieren erzeugt auf beiden Eingangsarten doppelte Flächen mit
  alten Flächeninhalten; eine gültige NURBS-Platte mit Bohrung bleibt auch nach
  STEP-Rundreise ohne Merkmale; Projektion an den sechs Außenflächen der
  Korpusplatte scheitert. Keine dieser Lücken wurde durch die Dokumentprüfung
  behoben. 907 zusätzliche Tests bestanden; native STL-Auswahl teilweise
  gefahren, komplette Änderung/Undo/STEP-Parität und Erstnutzerprüfung offen.

  Abnahme: die im Konzept beschlossenen Handlungsmatrizen, sämtliche 35
  Bausteine mit dokumentierter Anwendbarkeit, korrekte Maße und Referenzen
  nach Änderung/Cache/Undo/Wiederöffnung sowie die zehn Kundenwege aus der
  Recherche. Keine stillen Formänderungen bei Erkennung; die vier Kernwahl-
  Haken fallen erst im benannten Umschaltpaket mit erhaltener Fachwirkung.
  Sämtliche Ausbauideen aus Recherche §6 sind durch die anschließende
  Entscheidung „alles“ ausdrücklich beauftragt (Konzept §14.2).

  **Zusatzumfang P6/P7:** variable Verrundungen, Fasen mit getrennten
  Abständen/Winkel, gewählte Öffnungs-/Entformungsflächen, abtragende
  Dreh-/Pfad-/Überblendwege, zusätzliche Skizzenkurven und Bedingungen,
  Merkmalsmuster, Einfügen/Umsortieren/Unterdrücken/Reaktivieren im Verlauf
  und Mehrkörper-STEP mit Namen, Farben und Instanzlagen. Konzept §13.9
  ergänzt unabhängige Sollwerte, Kundenwege, Migrations- und Rückfallverträge.
  P5 nimmt auch diese Funktionen direkt am Modell ab; P5.3 schließt erst nach
  P6–P9 mit installierten Paketen auf allen Zielplattformen. Die präzisierten
  Nicht-Ziele aus Konzept §15 bleiben ausgenommen.

  **Montage und Maßblätter, Entscheidung 23.09.:** P8.1–P8.3 ergänzen
  benannte Gruppen, gemeinsame Auswahl/Sichtbarkeit/Bewegung und getrennt
  gespeicherte Montage- und Drucklagen. Ersetzen, Teilen und Löschen von
  Mitgliedern, Passungsbezüge, Undo und Wiederöffnung gehören zum Vertrag.
  Vorhandenes Ausrichten, Kollisions- und Fügewegprüfen wird angeschlossen;
  die Ansichtsexplosion bleibt reine Darstellung. P8.4/P8.5 liefern ein
  PDF-Maßblatt aus gewählten Ansichten und Maßen mit Teilnamen, Einheit und
  eindeutiger Modellstandkennung; Vorschau, lesbare Bezüge und ausgewiesene
  Näherungen sind Abnahmekriterien. Keine Gelenke/Bewegungssimulation,
  kein allgemeiner Baugruppenlöser und keine assoziative Zeichnungsverwaltung.
  Fachliche Verträge, Kundenwege und Rückfall: Konzept §13.11.

  **Resin vollständig:** P9.1 klärt die technischen Restentscheidungen und
  belegt Stufe 1; P9.2 ergänzt Saugglocken samt Orientierungssuche, P9.3
  Abfluss-/Belüftungsöffnungen nach Drucklage und P9.4 verfahrensbezogene
  Regeln samt durchgehendem Kundenweg. Die fachliche Quelle bleibt das
  Resin-Konzept §§5–11. FDM-Verhalten, externe Slicer-Übergabe und vorhandene
  Aushöhlen-Wege werden mitgeprüft; eigener Slicer, Stützenerzeugung und
  Belichtungsprofile bleiben ausgeschlossen.

  **Bedienergänzung Robert, 18.09.:** Maße direkt im Viewport bearbeiten,
  Eingabefeld von der Maßlinie absetzen, ✓/× daneben; dieselbe Vorschau und
  Übernahme bei Bohrung, Bewegen und weiteren geeigneten Operationen.
  „Auf alle N gleichartigen“ unter dem Feld mit vollständiger Zielvorschau.
  Keine doppelten Maßfelder im Panel und kein vorgelagerter Dialog für diese
  Hauptwege. Konzept §10.2/§14.1, Pakete P0.3/P5.1/P5.2; bestehende
  Platzierungs- und Zugfelder zusammenführen. Enter genau einmal, Escape
  ohne Änderung, Fokusverlust ohne Übernahme, ein Undo für alle Ziele.
  Zusätzlich P0.4 / Konzept §10.3: sinnvolle, markierte und direkt wechselbare
  Kanten-/Merkmalsbezüge zum Ausrichten. Reproduziert: unerkanntes Ø0,5-mm-
  Kreisloch liefert zwei 0,032702-mm-Facetten als Bezugsgeraden. Echte kleine
  Ausschnittkanten erhalten; Referenzen während der Eingabe festhalten,
  Mitte-/Randabstand unterscheiden und instabile Kantenpaare abweisen.

  **Bibliotheksvertiefung 18.09.:** Vorhandene
  `ShapeAnalysis_CanonicalRecognition` erkennt im NURBS-STEP-Gegenbeispiel
  sechs Ebenen und den Ø6-Zylinder; P2.3 beginnt mit diesem Anschluss.
  Analysis Situs nur für belegte Restlücken evaluieren. Recherche §§5.1–5.6
  enthält Versions-/Alternativenvergleich und begrenzte Eigenentwicklung
  in Python, Cython oder C++ mit Plattform- und Genauigkeitsnachweis.
  P0.5 ordnet jede benötigte Fähigkeit einer vorhandenen Funktion,
  Eigenentwicklung oder begründet gewählten Ergänzung zu; P0.6 baut bei Bedarf
  die native Schnittstelle. P1.5 schließt gemeinsame Merkmalssemantik und
  zusammengesetzte Erkennung an beide Kerne an. Konzept §13.8 bindet sämtliche
  technischen Entscheidungen an Fachpakete und P5.3 an den Auslieferungsnachweis.
  Konkrete neue Abhängigkeiten bleiben auszuwählen; kein pauschaler Einbau
  aller Alternativen und keine Sprachenmigration beschlossen. Die alten
  Tageswerte sind als Planungsgrundlage zurückgezogen (Konzept §12).

  **Durchsicht 19.09.:** Die
  [Durchsicht](konzepte/durchsicht-cad-konzepte-2026-09.md) hat alle
  Messungen am Stand `87273de06` wiederholt; sie halten. Neu aufgenommen
  (Konzept §14.3): P0.0 (Spiegelung führt Merkmale nach, keine
  Doppelmerkmale nach Skalieren — beides Kundenfehler von heute, deshalb
  zuerst), P0.7 (die vier Reste des Bedienprotokolls vom 04.08.), P1.6
  (Analysekarte „Formabweichung“), P4.0 (Netz → exakter Körper ohne
  Verlauf), die Bauart-Matrix über alle 132 Ops als Test in P2.1 (57
  konvertieren, nicht 56) und die Regel, dass kein P6-Paket vor dem
  Umschaltpaket P2.8 beginnt. Präzisierung vom 20.09.: Open3D 0.20.0 wird
  derzeit nicht aufgenommen; fertiger Intel-macOS-Paketweg und Korpusvorteil
  fehlen. Ein eigener Python-3.14-Bau ist nicht als unmöglich erwiesen,
  aber einschließlich Auslieferungsweg unbelegt. Analysis Situs bleibt
  eine mögliche Quelltextportierung für eine konkret nachgewiesene Lücke.

  **Erster Entwicklungsstand 20.09.:** `77223ccb` erhält exakte Körper bei affinen
  Transformationen, führt native Flächen und Merkmale nach und benennt
  tatsächliche Konvertierungen. `064e3095` verbindet die Eingabewege mit der
  Freigabe ihrer aktuellen dargestellten Vorschau. Gemeinsames
  Entwicklungstor: **11.591 bestanden, 26 übersprungen**, Prozessausgang 0;
  Ruff, Format und mypy jeweils 0. Der erste Lauf mit fünf Fehlern wurde
  behoben und vollständig wiederholt. Fensterdateien und Leistungsprüfungen
  bleiben gemäß `69f956e76` ausschließlich dem Release vorbehalten; die
  ergänzten Fensterregressionen sind noch nicht ausgeführt. Das ist kein
  Abschluss von RM-188 und keine Release-Abnahme.

  **Weiterer Entwicklungsstand 20.09.:** `3bdaa788` schließt
  kanonische NURBS-Träger an den durchgehenden Bearbeitungsweg an.
  `7aaa993d` ergänzt gemeinsames Aufsetzen von Importgruppen,
  `b9b96a91` den lokalen Absturzschutz und `47023b53`
  die Rückmeldung am Handlungsort. Gemeinsames Entwicklungstor:
  **11.750 bestanden, 26 übersprungen**, Prozessausgang 0; Ruff,
  Format und mypy jeweils 0. Der erste Lauf dieses Blocks meldete vier
  Kernfehler und einen Formatbefund; nach ihren Korrekturen bestanden
  11.745 Kerntests. Der zusätzliche Hook-Abgleich erforderte fünf neue
  Gegenproben und den hier genannten abschließenden Gesamtlauf.
  `5b5b0ef5` ergänzt die Release-Regel aus `69f956e76` im
  Commit-Hook und in den verbleibenden Agentenanleitungen: neue Texte
  werden statisch geprüft; sämtliche Fensterdateien und Leistungsprüfungen
  bleiben beim Release. Die Agenten-Werkzeugliste umfasst 144 Einträge;
  der funktionale Zählaufruf von qwen3:14b belegt dafür 36.826 Prompt-Token
  bei `num_ctx=40960`, ohne eine Leistungsprüfung auszuführen.

  **Maß- und Innenraumstand 20.09.:** `3e4ea79c` schützt die
  Release-Grenze ganzer Fensterdateien auch vor Namens- und Markerfiltern.
  `a85cc872` erkennt vollständige Innenräume in beiden Kernen;
  `852de666` belegt ursprüngliche Bohrungsschritte und ihren
  gemeinsamen Flächensitz. `1fc131a6` verbindet Fachfelder,
  Platzierungsgriffe und dargestellte Vorschau im ersten gemeinsamen
  Maßeditor. Entwicklungstor: **11.880 bestanden, 26 übersprungen**,
  Suite und übergeordneter Prozess mit Exit 0; Ruff, Format und mypy jeweils 0.
  Der erste Gesamtversuch meldete einen Fehler bei 11.874 bestandenen
  Kerntests: Sein als Sacklangloch bezeichneter Testkörper enthielt tatsächlich
  einen geschlossenen Innenraum. Native Schalen, Materialpunkte und unabhängiges
  Luftvolumen belegten den falschen Testaufbau. Die korrigierte offene Mündung
  und der eingeschlossene Gegenfall sind jetzt für beide Kerne geprüft;
  die Produkterkennung wurde dafür nicht abgeschwächt. Der rote Lauf bleibt
  erhalten. Fenster- und Leistungsabnahme bleiben ausdrücklich beim Release.

  **Konturmaße und native Filamente 20.09.:** `db7d1a5c`
  misst Zylinder und Langlöcher an belegten Konturen, führt Fehler und echte
  Netzgrenzen durch Transformationen und reicht Passungsbefunde an Oberfläche,
  Steckbrief und Agent weiter. `93979914` ergänzt native und
  vollständig geprüfte rationale Ringträger sowie gerundete Restflächen.
  `3df89b8e` bindet Filamente an native Flächen und erhält sie
  beim Vernetzen, Kopieren, Weiterbearbeiten, Wiederöffnen und Undo/Redo.
  `102d4bf7` verbindet Maßfelder mit den belegten Kanten,
  Mitten und Langlochachsen der gewählten Oberfläche.
  Entwicklungstor: **12.063 bestanden, 26 übersprungen**, Suite und
  übergeordneter Prozess Exit 0; Ruff, Format und mypy jeweils 0. Der
  eingefrorene Stand und die Protokolle liegen unter `C:/Users/rober/AppData/Local/Temp/solidon-cad-contours-final-159a498a403749578038656a0b5eb8ba`.
  Rote Vorläufe bleiben als Nachweis erhalten: Der doppelte Langloch-Kreisfit
  und ein um gerade Flanken vergrößerter Mantelfit wurden behoben, ohne
  Konturtoleranzen zu lockern. Neue Fensterfälle sind vorbereitet und bleiben
  wie Leistung und installierte Plattformen der Release-Abnahme vorbehalten.

  **Rundflächen und Körperproben 20.09.:** `851f913a` ergänzt
  Kegel-, Kugel- und Torusfits aus belegten Stützpunkten sowie native und
  vollständig geprüfte rationale Kugelträger. Originalauswahl, ungerundete
  Maße und deren Herkunft bleiben durch Transformation, Cache, Wiederöffnung
  und Undo/Redo bis in Oberfläche und Steckbrief erhalten. STEP schreibt eine
  private Formkopie; auch native Prüfkennzeichen des Originals bleiben gleich.
  `eeadc09b` ergänzt die unabhängige Passungsprobe ganzer Körper in belegter
  radialer Einbaulage, die Übernahme beider Gegenstücke in die Passungskarte
  und den abbrechbaren Exportvorlauf. Getrennte Drucklagen werden in Beispielen
  und Tour als noch ungeprüfte Einbaulage benannt. Entwicklungstor:
  **12.308 bestanden, 26 übersprungen**, Suite und übergeordneter Prozess
  Exit 0; Ruff, Format und mypy jeweils 0. Protokolle und eingefrorener Stand:
  `C:/Users/rober/AppData/Local/Temp/solidon-cad-round-final-2a4b7e6982954e0ab0f6f88c56812d6f`.
  Der erste Gesamtlauf mit fünf Fehlern bleibt erhalten: echte Kollision der
  historischen Korpusbaugruppe, bisher zu weit gehende Beispielaussagen,
  veraltetes lokales Lizenzmanifest und ein im Nachlauf nicht reproduzierter
  PHP-Verbindungsabbruch. Fenster- und Leistungsabnahme bleiben beim Release;
  die bündige Ebenenpassung erhält ihre unabhängige Körperprobe im nächsten
  P1.3-Schritt. Beide Produktcommits sind nach origin/main gepusht.

  **Bündige Passung und Formabweichung 20.09.:** `912789f7` ergänzt die
  unabhängige vollständige Körperprobe für bündige Ebenenpaare. Die
  bestehende Ebenenregel verlangt weiterhin keinen Flächenkontakt.
  `5d451fe7` führt belegte analytische Teilträger über Originaldreiecke,
  Transformation, warmen/kalten Cache und Historie bis zur neuen
  Analysekarte. Ganze Dreiecke werden mit numerischer Klammer begrenzt;
  unbekannte Bereiche, Herkunft und wirkliche Zeugen bleiben ausgewiesen.
  Berichtsklick, Fortschritt, Abbruch, Ortsmarke und gerichtete
  Anzeigerundung teilen denselben Kartenweg in allen Sprachen.
  Vollständige Kernsammlung: **12.682 bestanden, 26 übersprungen**,
  Exit 0. mypy ist grün; Ruff und Format sind ohne den ausdrücklich
  getrennten parallelen P2.7-Nachweisordner ebenfalls grün. Der erste
  unbeschränkte Torprozess bleibt wegen vier Ruff-Befunden und eines
  Formatbefunds in dessen fremder Sonde korrekt Exit 1. Eigene
  Commitprüfung und Originalergebnis sind getrennt festgehalten unter
  `C:/Users/rober/AppData/Local/Temp/solidon-cad-deviation-final-eff89030f7fd4ec1b1096048184d26e7`.
  Die unabhängige Gegenprüfung sichert Quellenverlust, Abbruchübergaben,
  numerischen Überlauf und native Kegelnappen einschließlich echter
  Spitzentopologie ab. Zusätzliche Modellsonden treffen analytische
  Facettierungsabstände, erhalten ein polygonales Loch und weisen den
  nach einem Ausreißer verworfenen Rundfit als unbekannten Mantel aus.
  Produktcommits sind nach origin/main gepusht. Fensterdateien und
  Leistungsabnahme bleiben ausdrücklich beim Release.

  **Die Pakete in dieser Folge** (Umfang und Abnahme je Paket in Konzept
  §13.2, Voraussetzungen §13.6; jedes Paket endet mit dem Tor vor seinem
  Commit). Der Stand steht als Wort vorn — **offen**, **läuft**,
  **implementiert, Release-Abnahme offen** oder **erledigt TT.MM.** —,
  weil jedes Kästchen für den Registertest ein eigener Punkt
  wäre; RM-188 bleibt der eine Punkt, bis P5.3 grün ist:

  * **erledigt 19.09.** P0.0 — Merkmale werden bei Spiegelung, Skalierung und Mustern gemeinsam nachgeführt; keine alten Doppelmerkmale, gerichtete Gewindeangaben bleiben korrekt. Kern-, Cache-, Passungs- und Undo-Regressionen sowie zwei native Kundenwege sind belegt; Commit `cfc5e303`. Die nativen Kundenwege wurden vor der neuen Regel geprüft; weitere Fenster- und Leistungsprüfungen gehören zum Release (`69f956e76`). Exakte Skalierung folgt in P2.1.
  * **implementiert, Release-Abnahme offen** P2.1 — `77223ccb`: affine Transformationen erhalten exakte Körper und führen ihre nativen Flächen zur neuen Tessellierung nach. Die explizite Matrix erfasst alle 132 Operationen mit 226 gültigen Darstellungsfällen: 227 Prüfungen bestanden, Exit 0. Gemischte und mehrfache Boolesche Eingänge, leere Ergebnisse, Cache, Wiederöffnung und Undo sind gedeckt. Getrimmte NURBS liefern geprüfte Flächen-/Volumenintegrale einschließlich Abbruch; die private Rundungszwischenform wird vor Veröffentlichung orientiert. Entwicklungstor siehe oben; installierte Plattformen und Fensterabnahme bleiben offen.
  * **läuft** P2.3 — `3bdaa788`: erster Anschluss für analytische Ebenen und Kreiszylinder aus NURBS: gemeinsame Trägerauskunft für Erkennung und Bearbeitung, echte Trimgrenzen und Materialseite, zusätzliche Koeffizientenprüfung, durchgereichter Abbruch und Cacheentwertung. Der STEP-Kernweg erkennt sechs Flächen und eine Bohrung, ändert Ø6 auf Ø8, speichert, öffnet und nimmt zurück; Quelle und exakter Körper bleiben erhalten. Die unabhängige Gegenprüfung ergänzt periodische Nahttrimmungen und unveränderte Originalflächen bei Defeaturing. Acht weitere Maßfälle sichern wiederholte Radialänderungen sowie schräge Originalränder über enge NURBS-Knoten in beiden Richtungen, auch unter Offset- und Trimmhüllen. `a85cc872` erkennt geschlossene Innenräume einschließlich getrennter Materialinseln, bindet ihre tatsächlichen Quellflächen und erhält die Auswahl bei lokaler Suche. `93979914` ergänzt native Ringe, rationale Ringträger mit vollständigem Koeffizientennachweis und gerundete Restflächen. Angrenzende gleiche Ringstücke werden vereint, getrennte bleiben getrennt; vollständige native Flächen behalten exakte Integrale und Originalauswahl. `851f913a` ergänzt native und rationale Kugelträger mit vollständigem Koeffizientennachweis, beschnittene Kugelflächen und unveränderte Originalbytes über STEP und Historie. Die vollständige Semantik-/Teilflächenparität und weiteren Trägerfamilien bleiben offen.
  * **implementiert, Release-Abnahme offen** P1.1 — `db7d1a5c`: belegte Konturecken statt Schwerpunkte, zentrierte Achsrechnung, wirkliche axiale Grenzen und radiale Dreiecksabstände. Unterteilung, schiefe Schnitte, Teilbögen, große Koordinaten, Spiegelung, bewusste Gegenformen und Abbruch sind geprüft. Offene und geschlossene Langlöcher erhalten die volle Maßgenauigkeit; der zweite offene Kreisfit entfällt. Fitfehler und Netzband bleiben getrennt von Fertigungsspiel. Entwicklungstor grün; Fenster und Leistung bleiben beim Release.
  * **erledigt 20.09., Werkzeugauswahl** P0.5 — vollständige Zuordnung in Konzept §13.8.1; fachliche Machbarkeit, Vorversuche und Paketnachweise bleiben den jeweiligen Fachpaketen zugeordnet. P0.6 benötigt derzeit keine zusätzliche Infrastruktur: vorhandener Cythonweg bleibt Ausgangspunkt, neue native Ergänzungen nur bei belegtem Bedarf. P5.3 bleibt offen.
  * **offen** P0.8 — vollständiger Abgleich aller vier Konzepte samt Nachträgen: je geltender Anforderung aktueller Code-/Abnahmebeleg oder verbindliches Arbeitspaket; historische und ersetzte Aussagen ausdrücklich kennzeichnen. Quellenübersicht oben, Abnahmekriterium in Konzept §13.2.
  * **implementiert, Release-Abnahme offen** P0.1 — `064e3095`: Positions-Dreier, Einzahltexte, Gründe gesperrter Knöpfe und Rückmeldung zur leeren Skizze sind umgesetzt. Entwicklungstor grün; die ergänzten Fensterfälle laufen erst beim Release.
  * **implementiert, Release-Abnahme offen** P0.2 — `77223ccb`/`064e3095`: Vorschau und Befund nennen Operation, betroffenen Körper und Rückweg einer Konvertierung; beide Körperarten erhalten gleichwertige Baumtexte. Der Agent prüft auch reine Projektparameteränderungen und übernimmt Konvertierungen nicht automatisch. Menü, Merkmalkarte, Gruppen, Platzierung, historische Zwillinge, Filament, Formen und Chat teilen die Prüfung von Auftrag, Dokumentstand, Auswahl und tatsächlich gezeichneter Vorschau. Entwicklungstor grün; Fensterregressionen und reale Kundenabnahme bleiben dem Release vorbehalten.
  * **implementiert, Release-Abnahme offen** P0.7 — `7aaa993d` / `b9b96a91` / `47023b53`: früher UI-/CLI-Absturzschutz mit lokalen Python-/Thread-/nativen Berichten und redigierten festen Supportanhängen. `announce()` hat eine passive Klartextquittung am Maus-/Tastaturort; Abbruch und Dokumentwechsel verwenden dieselbe Meldungsquelle. Die Hoverbeschriftung bestand bereits; `always_visible` betrifft Tiefensichtbarkeit. Der vorhandene Fensterfall prüft zusätzlich Wegfahren mit und ohne Auswahl. Weitere Importe behalten ihre Dateilage (§17.1); der Bericht bietet ihrer unveränderten vollständigen Gruppe gemeinsames Aufsetzen als eigene Undo-Transaktion an. Steht die Gruppe schon auf dem Bett, bleibt am schwebenden Mitglied die wirksame Einzelhandlung. Zwölf Gruppen-Kernfälle grün; die Bauartmatrix erfasst jetzt alle 133 Operationen in 229 bestandenen Prüfungen. Neue Fensterfälle sind vorbereitet, werden aber ausschließlich beim Release ausgeführt; Sichtbarkeit, DPI, Tastatur und Bildschirmleser bleiben offen.
  * **läuft** P0.3 — gemeinsamer Maßeditor im Viewport: erster Bohrungsweg für beide Zwillinge mit passiver Maßanzeige, gebundenem Entwurf, gemeinsamem Abschluss, zwingend dargestellter Vorschau und geschützter Auswahl. Eindeutig belegte Bohrungsschritte zeigen ihre Originalwerte einschließlich Tiefe und rechnen Folgeschritte mit. `852de666` / `1fc131a6`: Kernnachweise und Entwicklungstor grün; Fensterfälle werden ausschließlich beim Release ausgeführt. Historische Hilfen gehören zur Prefixanzeige, werden über der Gesamtvorschau ausgeblendet und nach Tiefenänderung neu geprüft. Vollständige Feld-/Griff-/Gruppen- und Merkmalsabnahme bleibt offen.
  * **läuft** P0.4 — `102d4bf7`: Bezugswechsel über Auswahlfeld und Modellklick, echte Außen-/Innenkanten, belegte Mitten und Langlochachsen. Zug, Mittenversatz und erneute historische Vorschau erhalten gültige Bezüge. Fast parallele Referenzen und falsche Originalflächen werden abgewiesen; die Bediengrenze ist von geometrischer Toleranz getrennt. Gespeichert werden Operationswerte, keine flüchtigen Kantenbindungen. Vollständige Achsen-/Symmetrieparität folgt mit P1.5, dauerhafte Bezüge mit P3.2; Fensterabnahme bleibt beim Release.
  * **implementiert, Release-Abnahme offen** P1.2 — `851f913a`: Kegel, Kugeln und Tori werden an wirklichen Stützpunkten eingepasst; Teilflächen, Unterteilung, schiefe Lage, Originalauswahl, Gegenformen und Abbruch sind geprüft. Echte native und Netz-Zwillinge treffen unabhängig vorgegebene Maße in beiden Qualitätsstufen. Native und rationale Kugelträger erhalten Trimgrenzen und Materialseite; große Koordinaten werden vor Flächenintegralen lokal zentriert. Warmer und kalter Cache, STEP-/Projekt-Rundreise sowie Undo/Redo tragen dieselben Maße und ihre Quellen. Entwicklungstor grün; Fenster und Leistung bleiben beim Release. **Leistung 21.09. rot, zur Hälfte behoben:** Die Erkennung am glatten 327-680-Dreieck-Korpus brauchte seit diesem Commit 22,8 s statt unter 10 (Ziel 1 s, am Tag 0.4.4 0,84), und `e39dca21` ließ die Freiform eine Fläche von 0,22 mm² veröffentlichen — beides gemessen in der Fensterabnahme (`f0e61621`). **`e66c246d`:** Die Fächer aller Netzecken werden auf einmal geprüft (`_connected_fans`) und an einem geschlossenen Netz nur am Rand des Flecks, die Stützpunktlesung wird je Netz und Fleck gemerkt (`_SUPPORT_CACHE`, Identität statt Datenhash), die Punkte kommen aus den Ecken des Netzes; und eine Naht zu einem Dreieck ohne Fleck ist kein Beleg für eine kleine Fläche (`_facets_standing_apart`). Gemessen: Ikosphäre 22,8 → 2,2 s, Freiform 5,9 s und keine erfundene Fläche mehr. **`e5ac389a`:** Je Fleck wird jeder Fit und jeder Nachweis einmal gerechnet (`_remembered`, das Löserbudget im Schlüssel, ein abgebrochener Auftrag ohne gemerkte Antwort), und Kegel, Kugel und Ring bringen die Ableitung ihres Residuums geschlossen mit (`jacobian` an `_refined_fit`; am Korpus gegen Differenzen bis 10⁻⁹, dieselben Minima bis auf flache Täler, 874 Kern- und Messtests grün). Gemessen: Ikosphäre 2,0 s, Freiform 4,5 s, Lochplatte mit 204 000 Dreiecken 1,2 s. Ein lineares Sieb vor der Lesung ist **gemessen unsicher** — an echten kleinen Kugeln liegt der lineare Vorfit bis zum 10⁹-Fachen neben dem Endmaß, das die Verfeinerung findet — und `method="lm"` landet öfter in anderen Minima (158 von 4 031 Läufen uneins) für 4,5 → 3,8 s; beides verworfen. Die Marken der 0.4.4 (0,84 / 1,25 / 0,80 s) galten den linearen Fits, die P1.2 bewusst ersetzt hat, und fallen mit dieser Begründung, wie `test_performance.measure` es vorsieht. **`385f9c31` erreicht das Ziel aus §31 an den mechanischen Körpern:** je Frage ein eigener Merker mit passender Größe und Merker je Körper (gerundete Dreiecke, Flecken, kleine Flächen, deckungsgleiche Ecken), der Abdruck einer Flächenliste am Listenobjekt, der Fächer über die Bogenzahl aus dem Nachbarindex (`_fan_arcs`), Masken und Halbierung statt `np.unique`, Punkte ohne Sortierung, die Flächenträger blockweise als Feld. Gemessen allein: Lochplatte mit 204 000 Dreiecken 1,0 s (war 1,4), Taschenplatte 0,95 (1,3), Ikosphäre 1,4 (2,0), Freiform 4,3 (4,5); 1 254 Erkennungs- und Messtests unverändert grün. **Offen bleibt die Freiform:** je Fleck ein begrenzter Löser, 5 400 Flecken, angenommene Kegel brauchen am Korpus bis zu 78 Auswertungen (ein kleineres Budget kostete echte Formen), und das Anfangsresiduum sagt beim Kegel und Ring nichts über das Ende (bis 10¹⁴ darüber) — der Weg darunter führt über weniger Flecken, und das ist eine Entscheidung an der Freiformregel, nicht am Löser. Release-Tor am Arbeitsbaum mit nur diesen Dateien: Sammelgruppe 13.425 bestanden, 48 übersprungen; Fensterdateien 18.491 bestanden, 18 rot — genau die Handbuchfälle; Leistung 40 bestanden, allein nach dem Tor Lochplatte 986 ms, Taschenplatte 965, Ikosphäre 1 422, Freiform 4 248; Ruff, Format und mypy je 0.
  * **implementiert, Release-Abnahme offen** P1.3 — `db7d1a5c` / `851f913a` / `eeadc09b`: tatsächliche Konturgrenzen und Maßquellen kennzeichnen Schätzungen in Oberfläche, Steckbrief und Agent. Die unabhängige Körperprobe prüft alle Flächen radialer Paare in belegter Einbaulage, einschließlich Boden und Schulter; native Originale bleiben unverändert, gemischte Zwillinge werden als Näherung benannt. Unsichere Maße, Pressverformung und Montageweg werden nicht durch eine starre Nullverschneidung freigegeben. Die Passungskarte unterscheidet offene Prüfung und Verletzung; Exportvorprüfung und Auswertungsabschluss reichen Abbruch weiter. Beispiele und Tour behalten ehrliche Aussagen zur getrennten Drucklage. `912789f7` ergänzt die unabhängige Körperprobe der bündigen Ebenenpassung; deren bestehende Ebenenregel verlangt weiterhin keinen Flächenkontakt. Verschiedene Platten und zwei Merkmale desselben Körpers bleiben ungeklärte Einbaulagen, kein gemessenes Nullvolumen. Fensterabnahme bleibt beim Release.
  * **implementiert, Release-Abnahme offen** P1.6 — `5d451fe7`: Analysekarte „Formabweichung“ aus den bereits belegten Ebenen-, Zylinder-, Kugel-, Kegel- und Torusträgern. Originaldreiecke, Teilflächen, tatsächliche Fitwerte und Quellen reisen durch lokale Auswahl, Zusammenfassung, Transformation und Cache. Ganze ausgefüllte Dreiecke erhalten numerische Unter-/Obergrenzen und einen wirklichen baryzentrischen Zeugen; mehrdeutige oder nicht endlich begrenzbare Bereiche bleiben unbekannt. Keine erneute Einpassung. Bericht, asynchroner Fortschritt, Abbruch, bekannte Abdeckung, numerische Breite, Millimeter/Zoll und Ortsmarke sind angeschlossen. Gerichtete native Kegelnappen folgen der wirklichen Trimmung; beide Nappen werden nicht zu einer falschen vereint. Kern- und getrennte Commitprüfung siehe oben; Fenster und Leistung bleiben beim Release.
  * **läuft** P1.4 — `d483e1477` trägt die räumliche Vorauswahl und durchgehenden Abbruch; `fe17cd3bc` schließt **P1.4b** im Entwicklungsumfang an: konkurrierende Ansprüche und gleichwertige globale Zuordnungen bleiben gemeinsam offen; vollständige körperbezogene Entscheidungen übernehmen jeden Nachfolger höchstens einmal und speichern auch die ausdrückliche Nichtfortführung. Antworten werden über alle Ausgaben einer Operation atomar veröffentlicht. Format 27 erhält alte Antworten und die jeweilige Maßfassung bei Undo/Redo; tatsächlich gebundene Merkmale entwerten den Folgecache. Die Rückfrage zeigt echte Ausgabegeometrie und wartet auf die aufgebaute Ansicht; dieser Fensteranschluss ist statisch geprüft, seine Ausführung bleibt Release-Abnahme. Echte STL-/STEP-Projekte mit 1056 Flächen prüfen Identität, Maßquellen, Originalträger, Änderung, Cache, Wiederöffnung und Undo/Redo. Entwicklungstor: 12.971 bestanden, 26 übersprungen; Ruff, Format und mypy jeweils 0. Fachlich offen bleibt **P1.4c**: native Flächen- und Kantenbezüge ausdrücklich neu wählen und die gewählte aktuelle Topologie bis zur Operation erhalten. Referenzierte native Konkurrenz hält bereits an; Netzantworten geben sie nicht frei. Die Produktionsgrenze bleibt bei 1000; ihre Anhebung sowie Fenster- und Leistungsabnahme folgen erst mit dem Release-Nachweis. **P1.4c.1 (`875c40334`) ist im Entwicklungsumfang abgeschlossen:** Fläche versetzen und Rundung entfernen übernehmen aktuelle vollständige Originalflächen durch die private Kopierabbildung; ungültige Auswahl wechselt nicht zur Mittelpunkt-Suche. Auch Abbruch nach der letzten Ergebniskopie ist geprüft. Endtor: 13.025 bestanden, 26 übersprungen, Suite/Ruff/Format/mypy je 0. Native historische Fortführung, Gruppen-/Kantenneuwahl und Radiuswechsel bleiben offen. Die [vollständige Übergabe](konzepte/uebergabe-cad-2026-09-20.md) hält Anschlussverträge, Belege und die getrennte P2.5-/P2.7-Arbeit fest. **P1.4c.2 (`7b1a5ae3d`) ist im Entwicklungsumfang abgeschlossen:** Nach jedem nativen Übergang, auch nach Cachetreffern und ohne `touches_features`, ist ein alter Flächenbezug, den ein späterer Schritt oder eine aktive Passung noch braucht, nur mit Beleg gültig: durchgereicht, von der Operation als `FeatureContinuation` ausgestellt (heute `resize_hole` für Bohrung und Boden, im Ergebniscache Format 21) oder eindeutig auf denselben Namen zugeordnet. Sonst hält die Kette atomar an (`NativeReferenceLost`, nennt den Verbraucher), und `orphans.check(blocked=...)` heilt den Bezug weder über den Namen noch gegen die alte Szene. Gezählt werden nur spätere Verbraucher, nicht der eigene Eingang. Endtor: 13.064 bestanden, 26 übersprungen, Suite/Ruff/Format/mypy je 0. **P1.4c.3 (`edf247fab`) schließt die native Gruppenneuwahl an:** Was die Zuordnung nach einem nativen Umbau nicht belegt, wählt der Kunde am neu gebauten Körper über denselben Frageweg wie am Netz; die Wahl wird als Alias unter dem alten Namen veröffentlicht und liegt in `Operation.matches` in der Domäne `native-group:` mit Erzeugerscope (Projektformat 28, Migration 27→28 ohne Datenumschreibung, `example_v28.p3d`). Netzantworten geben native Konkurrenz nicht frei, ein anderer Scope fragt neu, „Nicht weiterführen“ bleibt ein Halt; ohne Frageweg trägt der Halt die Kandidaten als Vorschläge. Endtor: 13.072 bestanden, 26 übersprungen, Suite/Ruff/Format/mypy je 0. **P1.4c.4a (`4dfeb8dd8`) belegt den Radiuswechsel:** `reround` nimmt die gewählte Rundungsfläche wie `unround` als `selected_faces` an, und die scharfe Ersatzkante kommt aus der Historie des Defeaturing-Builders — die zwei ebenen Wände quer zur Achse teilen sich im Ergebnis genau eine Kante (`_sharp_edge_after`); ohne genau zwei Wände sagt der Weg mit `NOT_BETWEEN_TWO_PLANES` ab statt die nächste Kante an der alten Mitte zu nehmen. `fillet`/`chamfer` nehmen dafür `selected_edges` (Indizes am aktuellen Eigentümer, vor der Kopie geprüft, über `Solid._copied_edges` nachgeführt); `copy_shape` liefert die Kantenabbildung aus derselben Kopierprimitive, bijektiv geprüft und mit rückwärts eingehängten Teilkörpern gegengeprüft. Von vier gleichen Rundungen bekommt genau die gewählte den neuen Radius. Endtor: 13093 bestanden, 26 übersprungen, Suite/Ruff/Format/mypy je 0. **P1.4c.4b (`c49747238`) bindet Kanten vor dem Verbrauchercache:** Die Auswertung löst jedes aktive `edges`-Feld am ersten Eingang auf, in dem Kern, den die Operation gleich benutzt (`edges_in_kernel`, `OperationSpec.edges_on_mesh` für den Wulst), **vor** `cache.get`; der Fingerabdruck der gebundenen Kanten geht in den Operationsschlüssel des Verbrauchers, die Auswahl erreicht Netz- und exakten Kern als `selected_edges` über `OpContext.bound_edges`, und kein Schlüssel wird ein zweites Mal aufgelöst. Zwei Kanten mit demselben Schlüssel fragen über denselben `ask`-Weg mit typisierten Kantenzielen (`EdgeTarget`: Token, Körper, Zug; Dialogzeile über `edge_label`, Linie vor dem Material im Viewport, Betonung über das Token — dabei fiel auf, dass die Betonung der markierten Zeile bis dahin nie ankam: `weak_slot` verwirft Signalargumente ohne `forward=True`). Die Antwort liegt als `edge-answer:` in `Operation.matches` am Eingang, Feld und Schlüsselbündel mit dem Objekthash des Eingangs als Scope (Projektformat 29, Migration 28→29 ohne Datenumschreibung, `example_v29.p3d`; History filtert nach Eingang, der Projektleser prüft gegen `in`); der Aliasfall wird zum Parameter über `answered`; ohne Frageweg trägt der Halt die Token als `choose:`-Vorschläge. Endtor: 13141 bestanden, 26 übersprungen, Suite/Ruff/Format/mypy je 0; die drei neuen Fenstertests einmal allein gefahren, die Release-Abnahme steht aus. Damit ist P1.4c vollständig; als Nächstes P1.5.
  * **implementiert, Release-Abnahme offen** P1.5 — `e39dca21a` schließt die drei Gegenfallfamilien der Durchsichten an beiden Kernen an, geprüft je Fall auf Art, Maße, Herkunft, Träger, Rolle und Handlung, nicht auf Anzahl oder Volumen: (1) Ein 1-mm-Nocken auf einer Platte hat am Netz dieselben fünf Flächen wie am exakten Körper — `MIN_FACE_AREA` bleibt, aber ein Fleck darunter zählt, wenn jeder Rand zu fremden Dreiecken ein scharfer Knick ist, nichts auf einer Rundung liegt und er kein Streifen ist (`_facets_standing_apart`); Kugelfacetten und Mantelstreifen bleiben verworfen. (2) Die Mündungsfase eines durchgehenden Langlochs gehört an beiden Kernen zum Langloch, Teilkegel und schräge Flanken mit erhaltenen Trägern (`brep.features._mouth_chamfers_folded`, `perceive.features._mouth_flanks_folded`), die Maße bleiben Nennmaße; ein Kegelstück zwischen zwei Langlöchern bleibt unentschieden. (3) Zwei Bohrungen mit je 315 Grad Restmantel sind an beiden Kernen zwei angeschnittene Bohrungen (`partial`), durchgehend, Ø 6: `FULL_TURN` ist dieselbe Zahl wie `FULL_TURN_SPAN` (300 Grad, ein Test hält sie zusammen), von der Naht geteilte Mäntel werden vorher zusammengeführt (`_seam_split_cylinders_joined`, mit Vereinigung von Winkel und Achsspanne — drei kollineare Viertelmäntel des verrundeten T aus `test_brep` sind seither ein Mantel von 34 mm, 22 Verrundungen und 2 Kehlen statt 26), am Netz erkennt der Rand den Anschnitt (zwei Linien längs der Achse über die ganze Tiefe, kein Querloch). Grenzt der Mantel an eine andere Höhlung, sind beide berührt (`relations._cut_open_neighbours`): keine Kette, kein eigener Körper (`NO_OWN_BODY`), „Angeschnittene Bohrung“ im Objektbaum, „angeschnitten“ im Steckbrief; die Randöffnung ohne Nachbar bleibt unberührt. Neue Tests: `tests/test_partial_bores.py`, sechs Fälle in `tests/test_features.py`. Endtor: 13155 bestanden, 26 übersprungen, Suite/Ruff/Format/mypy je 0. **`2127d3241` schließt den ersten offenen Punkt:** `cavity_chain_state_at` liefert einen `CavityState` — Kette, „nicht sicher einzeln“ und den Grund mit dem Wort des Gruppenwegs (`ambiguous_cavity_chain`, `cavity_topology_unavailable`); `prepare_ops.cavity_refusal` wählt daraus `NO_OWN_BODY` oder den neuen Satz `CAVITY_TOPOLOGY_UNKNOWN`, dieselbe Wahl treffen `no_own_body` und `_shares_its_cavity`, das Merkmalfenster reicht den Grund an `actions_for` durch, und ein erzeugtes Merkmal ohne Flächennummern bleibt einzeln. Unlesbare Ränder fielen im Einzelweg bis dahin auf „steht allein“. Test: `test_a_cavity_whose_rings_cannot_be_read_is_not_alone`. Endtor: 13133 bestanden, 48 übersprungen (22 mehr als im Hauptbaum, nicht aufgeschlüsselt), Suite/Ruff/Format/mypy je 0 (im Arbeitsbaum am HEAD mit nur diesen Dateien, weil eine zweite Sitzung im Hauptbaum an `types.py` und `slice/` schrieb); `test_feature_panel.py` einmal allein gefahren, dabei sieben Fenstertests am HEAD rot — RM-192. **`c849c5c31` schließt den Steckbrief an:** Unter der Auswahlzeile stehen die Hohlraumkette oder der Grund „nicht sicher einzeln“ und je Mitgliedschaft eine Zeile der Handlungsgruppen — gleiche Merkmale mit Umfang, unsichere mit Grund (`digest._selection_lines`, dieselben Quellen wie das Panel: `cavity_chain_state_at`, `actions_for`, `alike_for_actions`); die Sätze zu Nachweis und Grund stehen einmal im Kern (`relations.group_evidence_texts`, `group_reason_texts`), das Panel liest sie von dort. Tests: `test_the_digest_tells_the_selected_feature_its_chain_and_its_alikes`, `test_the_digest_names_the_reason_when_a_bore_is_not_certainly_alone`. Endtor: 13135 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`adf01505a` macht den Vollformvergleich vernetzungsunabhängig:** `_same_surface_patch` misst den Abstand jeder Ecke des einen Ausschnitts zu den Dreiecken des anderen und umgekehrt, innerhalb von `units.MAX_FACET_SAG` (Kandidaten aus den `NEAREST_CORNERS` nächsten Ecken und der Nachbarschaft Ecke → Dreiecke, `_distance_to_surface`, ein Suchbaum je Ausschnitt statt zwei); eine in vier geteilte Außenbohrung des Gartenmusters bleibt in der Gruppe der acht, die Kalotte bleibt draußen — gegen den alten Vergleich ist der Test rot (`test_a_finer_subdivided_copy_is_still_the_same_complete_shape`). Endtor: 13145 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`db3e284b2` entscheidet die Trefferwahl am Kern:** `relations.cell_owner_table` gibt ein Dreieck, das zwei Merkmale beanspruchen, dem innersten (Verschachtelung) oder niemandem (`CONTESTED`), der Viewport liest die Tabelle für den Klick im Bild, und sein Ortsfang nimmt bei gleichem Abstand das kleinere Merkmal und dann den Namen statt des zuerst vorbereiteten. Am Korpus teilt heute kein Dreieck zwei Merkmale (32 Dateien gemessen); Kerntest `test_a_shared_triangle_belongs_to_the_inner_feature_or_to_nobody`, `test_selection.py` einmal allein grün (70), Fensterabnahme beim Release. Endtor: 13146 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`7f4587267` schließt die letzten zwei Punkte:** Die 1-mm²-Flächen des Nockens findet auch die lokale Erkennung (Klick auf Spitze und Seite wählt genau diese Fläche, `test_a_one_millimetre_stud_face_is_found_locally`), und die Zuordnung hält ihre Namen über eine Verschiebung (`test_the_stud_faces_keep_their_names_after_a_translation`); ein offenes Langloch des exakten Kerns trägt, was seine nativen Träger belegen — Durchmesser, Achse, Bogenmitte aus dem nativen Zylinder, Richtung aus den nativen Flanken, Quelle `native`; Mündung, Weg, Länge bleiben `fit` (`slots.native_open_slot_measures`, gelesen von `brep.features_of` an den endgültigen Trägern; am Netz ändert sich nichts; `test_an_open_slot_on_the_exact_core_carries_native_measures_where_it_can`). Endtor: 13149 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **Damit ist P1.5 im Entwicklungsumfang abgeschlossen**: alle Punkte der drei Durchsichten (`p15-entry-plan.md`, `p15-consumer-review.md`, `p15-geometry-review.md`) sind angeschlossen und getestet; Fenster- und Leistungsabnahme folgen beim Release, `FEATURE_LIMIT_COUNT` bleibt 1000 bis zum Release-Leistungsnachweis (aufgehoben am 22.09.2026: fünftausend, siehe RM-197). Als Nächstes P2.4.
  * **implementiert, Release-Abnahme offen** P2.2 — `3df89b8e`: `assign_slot`, `paint_slot` und `clear_filament` erhalten B-Rep. Native Flächen tragen unveränderliche Slots, jede Tessellation folgt ihrer belegten Flächenkarte; reine Attribute erhalten aktuelle Merkmalsdreiecke. Builder-Herkunft führt Farben durch Folgeschritte, verschiedenfarbige Teilungsgrenzen bleiben erhalten. Warmer Cache, bewusster Mesh-Diskcache, Quellen plus Operationsverlauf, Wiederöffnung und Undo/Redo sind geprüft. Fensterfall auf B-Rep-Erhalt umgestellt, ausschließlich zum Release auszuführen.
  * **implementiert, Release-Abnahme offen** P2.4 — `7718fa356` lässt Versetzen, Verdoppeln, Drehen und Entfernen einer Bohrung oder eines Langlochs ohne Kette am exakten Körper exakt (`EXACT_CAVITY_KINDS`, `_exact_move_cavity` und Geschwister in `geom/prepare_ops.py`): schließen über `brep.edit.fill_bore`, schneiden über `cut_bore`/`slot_bore`, nativ erkennen, Kennung belegt fortführen (`_exact_features_after`, `FeatureContinuation`), Durchgang und Kantenbefund wie am Netz; `edit.unified` legt die Nähte der Booleschen zusammen (ein gefülltes Loch ließ zehn Flächen an einer Platte, die sechs hat). Gemessen an einer Platte 60 × 40 × 10: Versetzen, Drehen um 90° und Entfernen treffen das analytische Volumen auf die neunte Stelle, Verdoppeln zählt `hole_2`, ein STEP-Umlauf verliert nichts (`tests/test_exact_feature_ops.py`); die Paritätstabelle (`test_exact_body_parity.py`) führt die vier Handlungen am exakten Körper als exakt. Endtor: 13155 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`525605afb` nimmt die Kette dazu:** Eine gesenkte Bohrung liest ihren Einlauf wie `resize_hole` (`bore_entrance`), Stopfen und Werkzeug sind Rotationskörper derselben Profile (`_entrance_tools`, `_exact_chain_solid`) an den wirklichen Randebenen — verschoben beim Versetzen und Verdoppeln, beim Kippen gedreht und an den Mündungen um den Überstand der Neigung nach außen gerückt (`_plane_turned`, `_reach_past_a_tilted_face`, `_cone_past_a_tilted_face`); gewählt werden darf Bohrung oder Senkung, alle Abschnitte werden belegt fortgeführt. Gemessen: Versetzen lässt das Volumen auf die neunte Stelle, Verdoppeln zählt `hole_2`/`cone_2`, Entfernen lässt sechs Flächen, die um 30° gekippte Kette trifft den Netzweg auf ein halbes Prozent, ein gekippter Kegel hält durch STEP die siebte Stelle. Endtor: 13160 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`7aef7ab4` nimmt die Materialmerkmale dazu:** `brep.edit.solid_from_faces` baut den Körper eines Zapfens, einer Kuppe oder eines Kegelstumpfs aus den nativen Flächen (Randkanten zu Drähten, je Ring ein ebener Deckel, genäht aus privaten Kopien, geschlossen heißt ohne freie Kante — das `Closed()`-Flag setzt Sewing nicht); Versetzen trägt ab und vereinigt, Verdoppeln vereinigt, Entfernen trägt ab, der gekippte Zapfen reicht unter seine Mitte so weit, wie `_reach_past_a_tilted_face` verlangt, und wird an der Mitte des sichtbaren Mantels wiedergesucht. Gemessen: Zapfen versetzt, verdoppelt, entfernt, gekippt (ein Stück), Kuppe versetzt, Kegelstumpf entfernt und verdoppelt — jedes Volumen auf die neunte Stelle (`tests/test_exact_feature_ops.py`). Endtor: 13167 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`7c590765` nimmt „nur das gewählte Merkmal“ einer Kette dazu** (`_exact_remove_section`), in der Reihenfolge des Netzwegs: Liegt etwas hinter dem Abschnitt, geht erst der ganze Hohlraum zu, und `_exact_chain_cut_kept` schneidet die übrigen Abschnitte frisch — die hinteren bis zur Mündung durch, die vorderen ab ihrer eigenen Randebene; der innerste wird aus seinen Flächen gefüllt, die Senkung darüber bleibt als Kegelstumpf mit ebenem Boden. Und der Körper aus den Flächen gilt jetzt für Material und Hohlraum (`EXACT_FACE_KINDS`, `_exact_move_by_faces` und Geschwister): eine allein stehende Senkung oder Pfanne wird gefüllt und geschnitten, wie ein Zapfen abgetragen und angesetzt wird. Gemessen: nur die Senkung entfernt — Bohrung durch alle 10 mm, sieben Flächen; nur die Bohrung entfernt — acht Flächen, Senkung belegt, danach allein entfernt, versetzt und verdoppelt (`cone_2`); jedes Volumen auf die neunte Stelle, STEP-Umlauf verlustfrei (`tests/test_exact_feature_ops.py`). Endtor: 13170 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`368abc38` kippt Kegelstumpf und Senkung exakt** (`_exact_rotate_cone`): gedreht um die Mitte des weiten Endes, über das der Kegel mit derselben Flanke so weit weitergeführt wird, wie `_cone_past_a_tilted_face` verlangt — ins Material beim Stumpf, ins Freie bei der Senkung; Höhe und schmalen Radius liest `edit.cone_extent` aus der nativen Fläche, `_oriented_cone` baut den Kegel an freier Achse, und die Erkennung beschreibt ihn danach am Ende der Weiterführung. Gemessen, 30° um X: der Stumpf bleibt ein Stück, unter der Oberseite fehlt nichts, über ihr steht genau der Teil eines unabhängig aus den Maßen gebauten Kegels; die Senkung bleibt offen, acht Flächen, das Fehlende ist der Teil desselben Kegels in der Platte — neunte Stelle, STEP-Umlauf siebte (`tests/test_exact_feature_ops.py`). Endtor: 13172 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`2455cb1c` lässt Senken und Verschließen exakt** (`_exact_countersink`, `_exact_plug`): Mündung, Materialseite und die Mitte eines Stopfens aus Zahlen fragt für beide Kerne derselbe Helfer (`prepare.sink_placement`, `prepare.plug_placement`, aus `countersink` und `plug` herausgelöst); der Kegel trägt seinen Durchmesser exakt an der Mündung und geht um `FEATURE_OVERLAP` mit derselben Flanke darüber hinaus, der Stopfen am Merkmal ist `_exact_cavity_filled` mit belegter Kennung, der aus Zahlen wird an `edit.convex_hull` beschnitten — die Hülle des Netz-Zwillings, exakt genäht. Gemessen: gesenkt an der Mündung ist der Hohlraum der des exakten Bohrens mit Senkung (acht Flächen, dieselbe Bohrungskennung), mitten im Material kommt der Befund und der Kegel ist ein Einschluss, verschlossen am Merkmal und aus Zahlen bleiben sechs Flächen, zur Hälfte verschlossen ein Sackloch von unten — neunte Stelle (`tests/test_exact_feature_ops.py`); die Paritätstabelle führt beide als exakt. Endtor: 13176 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 — im ersten Lauf riss ein xdist-Arbeiter nativ in test_sketch_ops (Gewinde-STL M6) ab, der Test allein dreimal grün, rtree nicht installiert; der zweite Lauf ist der Nachweis (Arbeitsbaum am HEAD mit nur diesen Dateien). **`5f5ab636` nimmt den Einschluss dazu, und damit ist P2.4 abgeschlossen:** `edit.void_body` schließt die ganz gewählten Schalen eines Einschlusses als private Kopien zum Körper und zieht die Inseln ab — dieselbe Bauart wie in der Erkennung —, und der Einschluss geht den Weg der übrigen Hohlräume aus Flächen (`EXACT_FACE_KINDS`): Entfernen füllt, Versetzen füllt und schneidet die verschobene Luft um die Insel herum. Gemessen am Block 40 × 30 × 20 mit Ø 6 × 8 Luft, ohne und mit Kugel darin: gefüllt sechs Flächen, versetzt Volumen und Luftvolumen auf die neunte Stelle, die Insel bleibt ein Körper, STEP-Umlauf verlustfrei (`tests/test_exact_feature_ops.py`, `test_brep_voids.py` verlangt jetzt den exakten Weg). **Am exakten Körper vernetzt keine Merkmalshandlung mehr**; `evaluate.exact_became_mesh` bleibt der Befund der Netzwerkzeuge in der Paritätstabelle. Endtor: 13180 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). Release-Abnahme (Fensterdateien, Leistung) offen wie für P1.5.
  * **implementiert, Release-Abnahme offen** P2.5 — **`067026d4` liest importierte Gewinde am exakten Körper** (`app/core/brep/thread.py`, aus dem Prototyp `thread_probe.py` übernommen): Kantenzüge nach Bogenlänge, Achse eingepasst und von einem Kernzylinder bestätigt, Vorschub und Händigkeit aus der Wendelregression, Gangzahl aus der Periodizität aller Wendeln, Materialseite aus den orientierten Normalen, Gangtiefe gegen `helix.GROOVE_RANGE`; `features_of` veröffentlicht `thread_1` mit `lead`, `starts`, `handedness`, `crest_radius`, `root_radius`, `depth`, `turns`, `uncertainty` (alle `native`) und verdrängt die Phantome auf der Wendel mit derselben Regel wie am Netz (`perceive.features.without_phantoms_on`, für beide Kerne herausgelöst). Die Fallmatrix läuft als `tests/test_thread_import.py`: vier Basiskörper aus `tests/data/threads/` (`make_thread_corpus.py`, aus Konstruktionsmaßen; als Datei, weil ein Bolzen zwanzig Sekunden und ein Innengewinde eine Minute kostet), alles Abgeleitete in unter einer Sekunde aus M6 — links, gedreht, angeschnitten, 2,5 Umläufe, beschädigt, geteilt, NURBS —, sechs Gegenformen mit Grund, Eingabe unverändert, Abbruch an jeder Schleife, Netzweg im Raster gleich; Toleranzen wie im Bericht. Endtor: 13208 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 — der erste Lauf fand einen öffentlichen Namen für zwei Werte (AXIS_TOLERANCE, jetzt SAME_AXIS_TOLERANCE), der zweite ist der Nachweis (Arbeitsbaum am HEAD mit nur diesen Dateien). **`d319fd80` schließt die Abnahmekriterien 3–7 an:** der Netzweg misst beide Vorzeichen (`helix._best_pitch`, `Helix.handedness`, am erkannten Gewinde als Maß mit Quelle `fit`; die Spiegelung eines Bolzens ist jetzt links statt nichts); eine Spiegelung führt die gemessene Händigkeit exakt nach (`matching.transformed_features`), das Netz misst nach der nächsten Erkennung neu; `fits._pitch_uncertainty` vergleicht Steigungen mit der Unsicherheit beider Seiten (Wendelabweichung, `PITCH_STEP`, null beim Erzeuger) und sagt ohne Händigkeit weiter „nicht gemessen“; `threaded_rod` verlangt an jeder Stufe ein Volumen über dem Kern (B3) — M6 × 1 mit Länge 2,5 und M8 × 1,25 mit Länge 8 sagen jetzt ab, M10 × 1,5 mit Länge 4 bekommt seinen Gang über eine gröbere Stufe (94 s), und die Fixture der exakten Gewindetests war selbst fünf Wochen lang ein glatter Bolzen (3,52 Umläufe; jetzt 4,0 mm mit Gang); Steckbrief, Beschriftung und Merkmalkarte nennen Händigkeit und Gangzahl (Steckbrief immer, mit Quelle; Beschriftung nur, was vom Üblichen abweicht) in sechs Sprachen; der Ergebniscache trägt die neuen Maße (Format 22). Endtor: 13210 bestanden, 48 übersprungen, Suite/Ruff/Format/mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **Offen in P2.5:** dreigängig und mehr, Innengewinde links/mehrgängig, konische und kantenlos modellierte Gewinde und ein fremdes Hersteller-STEP bleiben ohne Referenzkörper (Grenzen des Berichts, §8.1); die Release-Abnahme (Fensterdateien, Leistung) steht wie für P1.5 und P2.4 aus. `bbb0e6bfd` legt die Nachweise in `konzepte/nachweise-cad-p2-5/` ab (Bericht, Prototyp `thread_probe.py`, 17 STEP-Referenzkörper aus drei unabhängigen Konstruktionen, vier Sonden mit 274 Zusicherungen, alle Prozesse Exit 0 am Stand `ee16040e7`; Ruff und Format je 0 für den Ordner, kein eigener Torlauf neben dem der Hauptaufgabe). Gemessen ohne Erzeugerwissen: Achse, Vorschub je Umdrehung, Händigkeit, Gangzahl (aus der Periodizität aller Wendeln), Teilung, Innen/Außen, Kamm- und Fußradius, Gangtiefe — rechts und links, innen, zweigängig, gedreht, angeschnitten, kurz (2,5 Umläufe), beschädigt, geteilte Träger und NURBS-Neuparametrisierung auf 1e-4/1e-6; sechs Gegenfälle mit Grund abgelehnt, nie eine geratene Steigung. Der Kurvenparameter wird nirgends als Winkel gelesen. Netz gegen nativ: Teilung im Raster 0,01, Kammradius im Facettenband; Händigkeit, Gangzahl, Vorschub kennt das Netz nicht. Befunde für die Integration: der Netzweg findet kein Linksgewinde und nichts unter fünf Umläufen; **`threaded_rod` verliert an neun von 23 Längen den Gang still** (M8 × 1,25 mit Länge 8 darunter) — ein Kundenweg ohne Meldung; der Netzweg misst die Gangtiefe je nach Tessellation um −18 % bis +46 % falsch; die Gewindepassung vergleicht Steigungen auf `EPS_GEOM` und verlangt Händigkeit; `thread` steht nicht in `DETECTABLE_KINDS`; der Nenn-Ø eines Innengewindes ist der Grund-Ø. Übergabematrix, minimale Integrationsdateien und Abnahmekriterien stehen im Bericht; offen bleiben dreigängig und mehr, Innengewinde links/mehrgängig, konische und kantenlos modellierte Gewinde, ein fremdes Hersteller-STEP und der Produktionsanschluss. P2.6 bleibt getrennt.
  * **läuft** P2.6 — Torus- und Gewindehandlungen, Gewinde verschließen, Filament, Gegenstück. **`071cfe18` gibt Wulst und Kehle die fünf Merkmalshandlungen in beiden Kernen** (Konzept §13.2, P2.6 erster Teil): Versetzen, Verdoppeln, Drehen, Ändern und Entfernen eines Torusmerkmals — bis dahin stand an jedem Ring jede Zeile grau („hat nichts, woran sich einzeln etwas ändern ließe“). Das Werkzeug ist in beiden Kernen der volle Ring aus den Kennzahlen (`brep.edit.torus`, `prepare_ops._torus_ring_mesh`): vereinigt der Wulst, abgezogen die Kehle; was vom Ring im Schaft liegt, ist dort ohnehin Material oder wird ohnehin weggenommen. Nur das Schließen an der alten Stelle braucht mehr: exakt nimmt `brep.edit.defeatured` (`BRepAlgoAPI_Defeaturing`, dasselbe wie `unround`) die Ringfläche weg und lässt den Schaft weiterlaufen — gemessen am Schaft Ø 20 × 40 mit Wulst und Kehle R 10 / r 3: der Zylinder auf 10⁻¹⁶; am Netz deckt sich kein parametrischer Ring mit der vorhandenen Ringfläche (der erste Versuch hinterließ 679 Splitter), deshalb ist der Wulst der Körper aus den eigenen Dreiecken der Ringfläche (`_body_from_faces`) ohne den Schaftkern zwischen den Randringen, die Kehle der Kern ohne diesen Körper, und der Kern ein Reißverschlussband zwischen den zwei Umläufen mit denselben Deckeln (`_torus_shaft_core`). `resize_feature` bekommt das Feld `tube_diameter` (Rohrdurchmesser, nur am Ring wirksam, mit dem gemessenen Wert vorbelegt); ein Rohr, das nicht in den Ring passt, ist eine Absage mit Vorschlag. Ein Ring, der der ganze Körper ist (Ringfläche ohne Rand, Defeaturing ohne Wirkung), sagt es statt zu raten — auch im Merkmalfenster (`actions.torus_is_the_body`); um seine eigene Achse gedreht bleibt ein Ring, was er ist (Konzept §13.4); ein quer gestellter Wulst zerfällt exakt in zwei Lappen, und dann meldet `feature_lost`, dass die Kennung nicht weiterlief, statt einen still zu wählen. Gemessen (`tests/test_torus_feature_ops.py`, 32 Tests, beide Kerne × Wulst und Kehle) gegen die Analytik π²r²R ± 4πr³/3 (Pappus über die Halbscheiben): Entfernen trifft den Schaft exakt auf 10⁻⁹ und am Netz auf 0,6 % (Tessellierung), Versetzen um −8 hält das Volumen und die unabhängige Erkennung findet den Ring an der neuen Stelle, Verdoppeln legt den zweiten Ring an, die Rohrdicke 6 → 4 trifft die Analytik, der quer gestellte Ring trägt die gedrehte Achse, STEP-Rundreise, und Netz gegen exakt unter 0,6 %. Die Paritätstabelle bleibt (ein Fall je Operation). Endtor: 13.327 bestanden, 48 übersprungen, Ruff, Format und mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`3c1317a9` gibt dem Gewinde Ändern und Verschließen** (P2.6 zweiter Teil): Bis dahin sagte das Fenster an jedem Gewinde „trägt kein einzelnes Maß, das sich ändern ließe“ und schickte zu *Bohrung verschließen* von Hand. `resize_feature` bekommt das Feld `pitch` (Steigung, nur am Gewinde wirksam, mit dem gemessenen Wert vorbelegt) und setzt Durchmesser und Steigung mit demselben Bausteingewinde wie beim Einsetzen neu (`build.threaded`, je Kern): außen die bewendelte Strecke als Hüllzylinder weg und das neue Gewinde auf derselben Achse dazu, innen ein Zylinder über dem Kammradius hinein und das neue Innenwerkzeug hindurch; `remove_feature` nimmt außen den Gang bis auf den Kern und schließt innen die Bohrung („Gewinde verschließen“). **Die Enden fragen die Nachbarschaft** (`_thread_span`, `_material_at` je Kern — am Netz über `mesh.on_surface`, nicht `trimesh.contains`, das durch `rtree` führt): Hinter Material endet nur ein eingesunkenes aufgesetztes Bausteingewinde um `BOOLEAN_OVERLAP` früher — sonst bliebe im Sockel ein Ring von einem Hundertstel —, ein Stopfen greift dort hinein, in der Luft reicht das abtragende Werkzeug hinaus und der Stopfen nicht (die Lehre von `fill_bore`). **Innen nennt ein Merkmal die Gewindebezeichnung**, den Grund-Ø der Gänge, und das Werkzeug rechnet in der Bohrung darunter (`_tool_diameter`); ein **erkanntes** Gewinde am Netz misst Grenzen und Strecke an seinen eigenen Ecken (`_thread_corners`), weil der Fit über Dreiecksmitten radial innerhalb der Kammecken und axial neben der Stange liegt, und sein Kern bleibt um den Überlapp unter dem gemessenen Fuß; ist das Gewinde der ganze Körper, nimmt die Hülle alles und das neue Gewinde ist danach allein der Körper. Das neue Gewinde ist aus seinen Zahlen bekannt, die Erkennung sucht es an seiner Stelle und belegt den Bezug (`_exact_features_after` mit `expected`). Absagen mit Vorschlag: belegt linksgängig (`types.thread_is_left_handed` — gesetzt oder nativ gelesen; der Netzleser rät die Händigkeit am gedruckten Profil, gemessen an `build.threaded(6, 1, 8)`: Netz „left“, exakt „right“), mehrgängig (das Bausteingewinde hat einen Gang), eine Steigung ohne Kern, ein Gewinde ohne Strecke; Versetzen, Drehen und Verdoppeln sagen, dass der Körper oder die Bohrung das tut. Die Deckelgewinde (`lid.py`) nennen jetzt ihre Strecke, die Beschreibungen beider Operationen nennen das Gewinde, und ein Feld, das nur eine Merkmalsart trägt (Rohrdicke, Steigung), steht nur an ihr (`actions._carried_by`). **Gemessen** an einer Platte 40 × 40 × 10 mit einem M6 × 1 darauf und darin und am Gewindekorpus (`tests/test_thread_feature_ops.py`, 29 Tests, beide Kerne): Gang weg, Loch zu, M8 × 1,25 gesetzt und geschnitten — exakt gegen Pappus über das Gangprofil auf 10⁻⁵ des Gewindes (der genähte Körper trifft die Analytik auf 2 · 10⁻⁷), am Netz gegen das facettierte Bausteingewinde selbst auf 2 · 10⁻³ (48-Eck und Sehnenzug liegen 1,4 Prozent unter der Analytik; was die Operation zusammensetzt, ist die Frage hier); der eingesunkene Anteil ist der Anteil des ganzen Gewindes, nicht des Kerns (0,4303 statt 0,3447 mm³); `m6_rechts` verliert seinen Gang bis auf den Kern in beiden Kernen, `m8_innen` schließt zum Block, das neu geschnittene Gewinde steht allein und als gesetztes da, ein gespiegelter Bolzen und `zweigaengig` sagen ab, ein Sackgewinde schließt ohne Hohlraum, und beide Kerne erkennen das neue Gewinde danach mit 8,0 / 1,25. `BRepAlgoAPI_Defeaturing` taugt dafür nicht (gemessen: gibt den Bolzen unverändert zurück — die Gangflächen haben keine Nachbarn, die sich zum Kern schließen). Das Review vor dem Commit fand elf Punkte, darunter drei schwere — die falsche Durchmesserbedeutung innen, der Stopfen, der um den Überlapp vor dem Material endete (0,28 mm³ Hohlraum), und die Linksgänger-Absage, die am Netz jedes gedruckte Gewinde traf —, alle behoben und je mit einem Test aus dem Korpus belegt; zwei Funde des Testlaufs am Netz: ein Stopfen bündig mit dem Kamm zerfiel in 454 Splitter (greift jetzt um den Überlapp ins Material), und ein Kernwerkzeug auf dem gemessenen Kamm ließ 51 Kammsplitter stehen (jetzt die Ecken). Endtor: 13.356 bestanden, 48 übersprungen, Ruff, Format und mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`d93c09e5` gibt Wulst, Kehle und Gewinde ein Filament** (P2.6 dritter Teil): `paint_slot` und `clear_filament` tragen `torus` und `thread` in `applies_to`, in beiden Kernen. Der Ring und ein erkanntes Gewinde nennen ihre Dreiecke selbst; ein **erzeugtes** Gewinde nennt keine (der Baustein sagt nur Achse, Mitte, Durchmesser, Steigung und Länge, §24.1), und `paint.feature_triangles` nimmt dann alle Dreiecke in seiner Hülle — radial bis zum Kamm, axial über die bewendelte Strecke — ohne die Deckel quer zur Achse: die Spitze bleibt, der Sockel bleibt, an einem Gewindeloch die Stirnflächen der Platte. Am exakten Körper sind das ganze native Flächen, `validate_full_faces` prüft es weiter davor. **Gemessen** (`tests/test_filament_on_rings_and_threads.py`, 9 Tests an den Körpern der Torus- und Gewindetests): Der Ring färbt genau seine Dreiecke und gibt sie zurück, das aufgesetzte M6 färbt Flanken über der Platte und nichts quer zur Achse, das Gewindeloch lässt die Stirnflächen frei, und der exakte Ring behält sein Filament durch eine feinere Vernetzung (Deflection 0,005). Endtor: 13.365 bestanden, 48 übersprungen, Ruff, Format und mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`d92f33dd` gibt einem vorhandenen Gewinde sein Gegenstück** (P2.6 vierter Teil, Entscheidung 15): Die drei Paare in `counterpart.PAIRS` setzen beide Hälften neu; ein eingelesener Bolzen oder ein gedrucktes Gewinde hat seine schon. Ist eine der zwei markierten Stellen ein Gewinde, bleibt der Dialog zu (`MainWindow._thread_among`) — `thread_counterpart_draft` macht daraus den einen Schritt, das gegengleiche Bausteingewinde am anderen Teil im **Tabellenmaß** (`thread_size_for`, `THREAD_SIZE_REACH` = 0,2 mm im Durchmesser und 0,02 in der Steigung — unter dem halben Abstand je zweier Nachbargrößen, `test_the_reach_never_lets_one_thread_match_two_table_sizes` hält das gegen die Tabelle), `apply_thread_counterpart` legt ihn an, `attach_thread_fit` hängt die Gewindepassung an dieselbe Transaktion (`Session.create_thread_counterpart`); ein Undo nimmt beides. Absagen mit Vorschlag: kein Tabellenmaß (nennt die nächste Größe — Ø 6,4 × 1,1 wird nicht still zu M6), kein Gewinde als Ausgang, belegt linksgängig (`types.thread_is_left_handed`), dasselbe Teil. Zwei Funde daneben: `_made_feature` nimmt das **erzeugte** Merkmal des Schritts, nicht das daneben erkannte — am Netz liest die Erkennung über den Gängen eines gedruckten Gewindes ein zweites, gemessenes mit demselben Stamm (Ø 6,57 statt 6,0); und eine synchrone Auswertung (`Session.evaluate_now`) wurde von einem Arbeiter überschrieben, der noch am Stand davor rechnete — der Fenstertest hing im Dialog „zwei Stellen markieren“, weil das Gewinde im Baum des alten Stands nicht stand; ein beim synchronen Lauf noch laufender Arbeiter gilt seither als überholt (`_superseded`, `_outdated`). **Gemessen** (`tests/test_thread_counterpart.py`, 11 Tests, Netz und exakt; `test_counterpart_ui.py` das Fenster ohne Dialog): Bolzen M6 auf der ersten Platte, Gewinde M6 in der zweiten, Passung `thread` zwischen beiden erzeugten Merkmalen, ohne „nicht messbar“ im Bericht; Gewindeloch bekommt den Bolzen; Undo nimmt Schritt und Passung; ein geänderter Verlauf lässt die Passung aus und sagt es. Endtor: 13.380 bestanden, 48 übersprungen, Ruff, Format und mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **P2.6 ist damit umgesetzt; die Release-Abnahme (Fensterdateien, Leistung) steht wie für P2.4, P2.5 und P2.7 aus.** **Offen daneben:** Der Netzleser misst die Händigkeit an einem gedruckten, abgeflachten Profil falsch (`perceive/helix.py`; `test_thread_import.py` sagt „fehlt ihm“, `perceive/features.py` liefert sie als `fit`) — bis das gemessen ist, zählt nur eine belegte Händigkeit.
  * **implementiert, Release-Abnahme offen** P2.7 — Produktionsanschluss: jeder mitgelieferte Baustein baut am exakten Träger exakt, in sechs Einheiten von den Verbindungen bis zur Kalibrierung. **`f08500aa` stellt die Bausteine auf eine Formbeschreibung mit zwei Auswertern** (Bericht §7, Bauart B): `shapes.building(kernel)` wählt den Kern je Bau, jede Grundform in `shapes` hat in `parts/exact.py` einen Zwilling mit demselben Rahmen (Bounds gleich bis 1e-6, Volumen 1,0 für Prismen und `polygon_ratio(48)` für Rundes, das Langloch endet exakt bei ±L/2), `build` vereinigt, zieht ab, schneidet und verbindet je Kern; die 40 Netzstellen der übrigen Gruppen stehen hinter `shapes.mesh_only` (Programmfehler statt Absturz unter dem exakten Kern), und `ops.EXACT_PARTS` lässt nur die sechs Verbindungen dorthin — `_insert_at_exact` platziert mit derselben `_matrix` über `edit.transformed`, vereinigt und schneidet mit `edit.boolean` plus `unified`, hängt ein lösbares Teil als Verbund an (B9), zählt die Teilezahl topologisch (`boolean._pieces`), prüft Volumen und Geschlossenheit nach dem Schnitt und führt die Merkmale über denselben Helfer wie am Netz fort (`_merged_features`, B3); ein Netzträger geht unverändert den alten Weg, `create_*` bleibt am Netz, bis P2.8 die Kernwahl regelt. **Das Gewinde ist exakt ein genähter Körper:** Die Vereinigung eines gesweepten Gangs mit dem Kern verschluckt den Gang still (B1), und die Rasterfahrt vom 21.09.2026 über sechs Größen und drei Längen fand die rettende Fuzzy-Stufe je Fall woanders (M3 × 0,5: 1e-2, 1e-3, 3e-3 bei L6/L8/L12), für M5 × 0,8 L8 und M6 × 1 L8 gar keine, je Stufe 7 bis 24 s; `profiles.helical_thread` näht Kern und Gang aus Regelflächen zwischen geteilten Helixkanten mit Rampen von der Achse als Enden — 44 Flächen in 30 ms, gültig, Volumen gegen Pappus auf 2,4·10⁻⁷, STEP-Rundreise 10⁻¹⁴ (Sonde `probe_sewn.py`), `build.threaded` liefert Kern und Gang auf Länge je Kern, der nackte Gang bleibt Netzform. Der Senkkopf bleibt ein Verbund aus Kegel und Gang (B2); am Träger sind es drei Körper, und der Verbund trägt Filamentzuweisung und Vernetzungsfeinheit seiner Teile weiter (`exact.compound`, §20). Der Review-Durchgang (13 Befunde) ist eingearbeitet: Das Gewinde entsteht gleich an seiner Höhe (`build.threaded(bottom=)`) statt danach bewegt zu werden, `exact.union` fragt Körperzahl und Geschlossenheit statt eines Volumenintegrals und meldet eine gebrauchte Nahttoleranz als Befund (`shapes.note`, `parts.fuzzy_union`) oder sagt mit Vorschlag ab, das Gangprofil steht einmal (`shapes.ridge_profile`, `RIDGE_START`) und der Test rechnet Pappus daraus, die Kernfrage geht überall über `types.BRepBody` (mit `solid_count` im Protokoll), `_place_solid` ist abbrechbar. Gemessen am Einsetzen an einem exakten Träger, Netzträger in Klammern: Schraubenloch 0,02 s (0,01), Gewinde 8,2 s (0,04), Schraube 13,1 s (0,07), Mutter 9,0 s (0,04) — vor dem Review 11, 29 und 22 s. Was bleibt, steckt nicht im Bau (Gewinde 0,3 s), sondern in `edit.transformed` (zwei konvergierte Volumenintegrale je Bewegung, an BSpline-Flanken je fünf Sekunden) und im Volumen des Ergebnisses für `without_effect`: RM-196, gegen §31 (unter 2 s) offen. `tests/test_exact_parts.py` (77 Tests): Zwillinge je Grundform, je Baustein Volumen, Richtung, Merkmale und STEP-Rundreise, der Einsetzweg am exakten Träger mit Verbund, `without_effect` und `hanging_loose`, der Netzträger unverändert; die sechs `insert_`-Zeilen der Paritätstabelle tragen `KEEP`. Endtor: 13.247 bestanden, 48 übersprungen, Ruff, Format und mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`6bf141e4` schließt die Gruppe Mechanik an** (acht Bausteine, Bericht Abschnitt 4.2): Der Seitenriss des Schnapphakens und der gerundete Schwalbenschwanz des Passstifts bauten bis dahin direkt mit trimesh — jetzt sind sie Formen mit zwei Auswertern (`shapes.prism_across`, das auch die Rampe trägt, und `shapes.rounded_dovetail` mit echtem 300-Grad-Bogen exakt, `DOVETAIL_START`/`DOVETAIL_ARC` einmal); die Facettenkorrektur der Augenwand gilt nur noch dem Netz (Abschnitt 5.2: exakt ist die Wand genau `wall`, gemessen); das Bolzenscharnier sagt seine zwei Körper über `build.compound` (am Netz dieselbe Vereinigung, exakt ein Verbund) statt über eine Vereinigung, die nichts vereinigt; die übrigen acht Netzstellen der Gruppe waren nur Typgrenzen. Je Baustein gegen unabhängige Analytik auf 10⁻⁹: Lagersitz, runder Stift mit Fase (Zylinder minus Ring = Kegelstumpf oben), Bohrung mit Einführung, Scharnierauge (halber Zylinder auf der Lasche minus Bohrung), Rastnase, Filmscharnier, Schnappverbinder-Tasche, Schnapphaken (Breite mal Seitenriss); Sechskant- und Schwalbenschwanzstift, Bolzenscharnier gegen das Netz (Facettierung, Umkreis, zwei Körper, gleiche Hüllen), alle mit STEP-Rundreise; Schnapphaken und Lagersitz auch am exakten Träger. Die acht `insert_`-Zeilen der Gruppe tragen `KEEP`. Endtor: 13.257 bestanden, 48 übersprungen, Ruff, Format und mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`4fe0b1f5` schließt die Befestigung ohne die Profilklemmen an** (fünf Bausteine, Bericht Abschnitt 4.3): Der Fuß und seine Tasche sind ein Drehkörper mit zwei Auswertern (`shapes.revolved`: `lathe.revolve` am Netz, `profiles.revolve` exakt), Schlüsselloch, Magnettasche und Wandhalter brauchten nur ihre Typgrenzen, und der Lochwand-Einhänger vereinigt je Haken und sagt ohne Platte seine getrennten Haken über `build.compound` (`joined_by_host`: erst der Träger verbindet sie). Je Baustein gegen Analytik auf 10⁻⁹: Fuß (Säule plus Kegelstumpf am Standende) und Tasche (voller Sitz, Einführung weitet die Mündung), Magnettasche (Tasche, Lippe, Haut), Wandhalter (Platte, Auflage, zwei Löcher längs Y); Schlüsselloch und Einhänger gegen das Netz — die Langlochenden sind exakt Halbkreise, das Netz endet um den Sag früher (0,0056), und das Facettenverhältnis liegt je nach Form über oder unter eins (ein 48-Eck-Loch nimmt weniger weg als ein rundes); alle mit STEP-Rundreise, Magnettasche und Wandhalter auch am exakten Träger. Die fünf `insert_`-Zeilen tragen `KEEP`. Endtor: 13.263 bestanden, 48 übersprungen, Ruff, Format und mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`f7aaddc8` schließt die Profilklemmen an** (Bericht Abschnitt 4.3): Schale und Einlage entstehen aus Querschnitten — Sitz, Normalversatz, Differenz, Ohren, Hälfte, Prisma —, und `parts/section.py` trägt je Querschnitt beide Auswerter zugleich: den `manifold3d.CrossSection` für die Prüfungen (Bounds, ein Materialintervall je Schnitt, keine Löcher, ein Stück) und unter dem exakten Kern die ebene Fläche für die Geometrie. `brep/profiles.py` bekommt dafür `face_of`, `rectangle_face`, `offset_face` (`BRepOffsetAPI_MakeOffset` mit `GeomAbs_Arc`; ein Versatz, der zerfällt, ist eine Absage), `face_boolean`, `face_rotated` und `prism(…, bottom=)`, das den Boden vor dem Einpacken verschiebt statt den fertigen Körper (RM-196). Gemessen: Der Versatz eines Kreises Ø 20,25 um 4 ist exakt ein Kreis Ø 28,25, das Prisma darüber ein Zylinder mit dem Volumen der Analytik auf 10⁻⁹, der Ring aus beiden ebenso; die untere Schalenhälfte endet exakt bei y = −0,5, ihre Ohren reichen um `ear_width − wall` über den Sitz hinaus, beide Stirnflächen tragen Dreiecksindizes ihrer Tessellierung, Netz gegen exakt innerhalb eines Prozents (Sitz nach `CONTOUR_SAG`, Löcher 48-Eck), Hüllen bis 0,02; die Einlage beginnt bei null und endet bei 39,5 (Bund vorn, Freiraum hinten), beide mit STEP-Rundreise, die Schale auch am exakten Träger. Am Netz ändert sich nichts: dieselben Querschnitte, dieselbe Rückfallkette mit gemeldeter Stufe, das Klemmenpaar und die Ersetzung unverändert (`test_profile_clamps.py` grün). Die zwei `insert_`-Zeilen der Klemmen tragen `KEEP`. Endtor: 13.272 bestanden, 48 übersprungen, Ruff, Format und mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **`1d6393b4` schließt Struktur, Kabel und Organizer an** (neun Bausteine, Bericht Abschnitt 4.4 ohne die Dichtungen): Rippe, Eckwinkel, Nutfeder und Kabeldurchführung brauchten nur ihre Typgrenzen; drei Stellen rechneten am Netz vorbei an der Beschreibung. Der gerundete Quader der Organizer-Wanne war eine eigene manifold3d-Konstruktion und ist jetzt `shapes.rounded_box` mit zwei Auswertern — Sehnen nach `MAX_FACET_SAG` am Netz (derselbe Code, dieselben Dreiecke), vier echte Viertelkreise exakt, die Eckmitten für beide aus `shapes.rounded_corners`, ein voller Radius ohne entartete Kante. Die Flächenmaße `base`/`floor`/`rim`/`seat` zählten Dreiecke nach Normalen; exakt sind sie das Integral über die ebenen Flächen einer Höhe (`brep.canonical.horizontal_area`, Richtung aus Ebenenachse und Flächenorientierung, keine Innenprobe), und `measure_sources` sagt `native` statt `facets`. Die Facettenkorrektur der Kabelclip-Bügelwand gilt nur noch dem Netz (Abschnitt 5.2). Gemessen je Baustein gegen unabhängige Analytik auf 10⁻⁹: Rippe (Riegel plus zwei Rampen, Netz = exakt), Eckwinkel (fünf Flächen), Nutfeder aus den Tabellenmaßen 2020 (Hals plus zulaufender Kopf), Kabeldurchführung (Bohrung, Kanal, gemeinsamer Streifen; Netz nur an der Bohrung facettiert, `polygon_ratio(48)` auf 10⁻³), Kabelclip (Sockel, Ring, Öffnungssegment, eingetauchtes Kreissegment; Wand exakt `wall`, Scheitel ist der Rand der Öffnung), Wanne (19 Flächen, Volumen, drei Flächenmaße nativ, Netz auf 10⁻³), Trennwand, Rand (Ursprung auf dem Rand, Hülle −28,5 bis 1,5), Steckfuß (Flansch plus Zapfen, Ringflächen nativ, Netz `polygon_ratio(48)` auf 10⁻⁹); alle mit STEP-Rundreise. Am exakten Träger: Rippe mit dem eingesunkenen Überlappungsanteil (Riegel voll, Rampen verjüngt) auf 10⁻⁹, Kabelclip, und die Kabeldurchführung mit ihrem Klemmblock über den bestehenden `host_add`-Weg an einer Wand von 3 mm — Block, Bohrung, Kanal und gemeinsamer Streifen gegen die Analytik auf 10⁻⁹. Der Organizer als Ganzes (`organizer/build.py`) bleibt am Netz und sagt es an seinen zwei Stellen (`shapes.mesh_only`); er geht mit P2.8 auf den exakten Kern. Die neun `insert_`-Zeilen tragen `KEEP`. Endtor: 13.286 bestanden, 48 übersprungen, Ruff, Format und mypy je 0 im zweiten Sammellauf am Commit; der erste Sammellauf hatte bei denselben Dateien zwei Umgebungsrisse — die lokale PHP-Gegenstelle setzte die Verbindung zurück, und scipys Quadratur im Bolzentest brach mit einem `TypeError` in `range` —, beide einzeln dreimal grün (Arbeitsbaum am HEAD mit nur diesen Dateien). **`62f30c81` schließt die Dichtungen und die Kalibrierung an — damit baut jeder mitgelieferte Baustein am exakten Träger exakt** (Bericht Abschnitte 4.4 und 4.5). Dichtnut und rechteckige Dichtung sind ein Band um den gezeichneten Weg (Versatz nach außen und innen, Differenz, Prisma) und bauen jetzt aus demselben `Section`-Querschnitt wie die Profilklemmen; die Sehnengrenze der Dichtungen (`_SEAL_SAG`) war Wert für Wert die der Klemmen (`CONTOUR_SAG`) und kommt aus einer Quelle. Die runde Schnur ist exakt die Minkowski-Summe des Wegs mit der Kugel aus Stücken (`brep.profiles.round_cord`): je Strecke ein Zylinder, je Kreisbogen ein Torusstück, je Ecke eine Kugel, vereinigt; ein Kreisweg ein ganzer Torus, ein Spline sein Rohr. **Gemessen und verworfen:** `BRepOffsetAPI_MakePipeShell` mit `BRepBuilderAPI_RoundCorner` baute dieselbe Form gültig und auf 10⁻¹⁰ genau (Rechteckweg vier Zylinder und vier Eckflächen, Kreisweg ein Torus, versetzter Rechteckweg vier Zylinder und vier Tori), kam aber aus STEP um zehn Prozent leichter zurück — seine Eckflächen sind keine Kugeln. Die ebenen Flächen der Dichtungen (`groove_mouth`, `groove_floor`, `gasket_contact`, `gasket_bottom`) bekommen ihr Maß exakt aus `canonical.horizontal_area` (`native`), Mantel und runde Schnur bleiben Dreiecke der Tessellierung (`facets`). Die Toleranzleiter sagt ihre zwei Leisten als Verbund (`build.compound`) statt über eine Vereinigung, die nichts vereinigt, ihr Strichcode ebenso (ein Verbund aus einem Teil ist das Teil), und die Rampen des Überhangfächers sind ein Seitenriss (`shapes.prism_across`) statt acht von Hand vernähter Dreiecke. Gemessen gegen unabhängige Analytik auf 10⁻⁹: Nut (Band außen gerundet, innen scharf, 14 Flächen, unter der Mündung), rechteckige Dichtung (steht auf der Fläche), runde Dichtung am Rechteckweg (vier Zylinder, vier Kugeln; Steinmetz-Viertel und Viertelkugel je Ecke) und am Kreisweg (ein Torus, 2π²Rr²), Toleranzleiter (zwei Körper, Leisten, Zapfen, gestaffelte Bohrungen, gravierte Striche), Wandleiter, Überhangfächer (Rampen mit ihrem Überlappungsanteil); Netz gegen exakt innerhalb 0,2 % am Band, 1,5 % an der Schnur (Bahn und Kugeln facettiert, Bericht Abschnitt 5), 0,5 % an der Leiter; alle mit STEP-Rundreise. Am exakten Träger: Die Nut schneidet, die Schnur liegt lose daneben (zwei Körper), die Leiter wächst als ein Körper — eingesunken um die Überlappung ohne die Bohrungen, die der Träger wieder füllt. `tests/test_exact_parts.py` hält `EXACT_PARTS` jetzt mit dem ganzen Register gleich; alle fünf `insert_`-Zeilen tragen `KEEP`. Der Dichtungserzeuger (`create_seal`) rechnet weiter am Netz und sagt es (`mesh_only`), wie der Organizer und alle `create_*`. Endtor: 13.295 bestanden, 48 übersprungen, Ruff, Format und mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **Bereichsläufe von Hand** (`bausteine.md`) über die neunzehn Bausteine, deren Netzbau P2.7 umgestellt hat — Rippe, Eckwinkel, Nutfeder, Kabeldurchführung, Kabelclip, die vier Organizer-Teile, Schnapphaken, Passstift, Fuß, Dichtnut und Dichtung, beide Profilklemmen, Toleranzleiter, Wandleiter, Überhangfächer: alle bestanden bis auf die Rippe, die an sechs Ecken (Länge 2, Anlauf 20) Selbstdurchdringung meldete — **vorbestehend** (am Stand `5126e46c` dieselben sechs) und **behoben in `f3423a81`:** Die um 180 Grad gedrehte Rampe lag mit ihrer Rückseite um 1,2 · 10⁻¹⁶ neben der Stirnfläche der Rippe (`math.sin(math.radians(180))`), die Vereinigung ließ beide Flächen als Doppelwand ohne Dicke stehen; `transform.rotation_about` rechnet jetzt aus den exakten Winkelfunktionen (RM-187), `shapes.turned` nimmt dieselbe Matrix wie `exact.turned`, die Rippe besteht ihre 32 Ecken, und ihr Körper hat 28 statt 34 Dreiecke (Endtor für den Fix: 13.295 bestanden, 48 übersprungen, Ruff, Format und mypy je 0). Dabei mitgemessen, fürs Release-Tor: Die Fensterdatei `test_pose_session.py` hat am Stand vor P2.7e (`5126e46c`) und danach denselben roten Test (`test_exact_armature_gestures_reach_the_guarded_operation_dialog`: die Vorschaufreigabe des Operationsdialogs wird nicht angezeigt) — nicht diese Einheit, aber vor dem Release zu beheben. **P2.7 ist damit abgeschlossen; offen daraus:** `create_*` exakt mit P2.8; RM-195 für den Gewindebolzen, RM-196 für die Sekunden des exakten Gewindes; Fenster und Leistung beim Release. Machbarkeit belegt: `69efc1cdf` legt die Nachweise in `konzepte/nachweise-cad-p2-7/` ab (Bericht, Prüfkörper, elf Sonden, 568 Zusicherungen, alle Prozesse Exit 0 am Stand `1cf405496`; Kernsammlung 12.682 bestanden, 26 übersprungen, Ruff, Format und mypy je 0 für genau diesen Stand). Gemessen: es konvertieren **alle 35** `insert_`-Pfade und die zehn `create_`-Pfade, nicht 31 — die vier angehaltenen scheiterten nur am Pflicht-Skizzenparameter. Jede Bausteinform entsteht mit `brep.edit`, `brep.profiles` und `Profile`; als Sonde belegt sind der Konturversatz (`BRepOffsetAPI_MakeOffset`) für Klemmen und Dichtungen und der Helix-Gang mit dem Gangprofil des Netzwegs, keine neue Abhängigkeit. Der Einsetzweg ist am exakten Träger mit derselben `_anchor`/`_matrix`-Lage nachgestellt, einschließlich geneigter Fläche, zwei Zielen, lösbarem Teil und dem Kundenweg aus Konzept §5.1; Netz und exakt unterscheiden sich bis auf drei benannte Fälle nur durch Facettierung. Vier Befunde für die Integration: Kern + Gang ohne Fuzzy-Toleranz verliert den Gang still; der Senkkopf wird mit Fuzzy ein Körper, kommt aber aus STEP ungültig zurück und bleibt Compound; Fuzzy-Stufen auf denselben Eingaben reißen den Prozess (Exit 139, 3/3), private Kopien nicht; nach einem exakten Schnitt werden Trägermerkmale fortgeführt, nicht neu erkannt. Gangprofil und Bauart folgen aus Konzept §13.1/§13.2 und `zwillinge.md`: Bausteinmaß bleibt, eine Formbeschreibung mit zwei Auswertern. Übergabematrix, Integrationsdateien und Abnahmekriterien je Bausteingruppe stehen im Bericht; Fenster, Leistung, Bereichsläufe und ein integrierter Kundenweg bleiben offen.
  * **implementiert, Release-Abnahme offen** P2.8 — Umschalten: die vier Kernwahl-Haken fallen, Aushöhlen nach Entscheidungstabelle, alte Projekte unverändert. **`6a4918b5`** (Konzept §10.1, Entscheidung 4 vom 17.09.2026): `registry.MENU_TWINS` wird beim Laden nach der Verfügbarkeit des exakten Kerns gebaut — faul, beim ersten Zugriff über `menu_twins()`, denn die Antwort lädt OpenCASCADE (334 Module, 0,43 s je Import des Registers); `exact_kernel_present` ohne Paketkante — die fünf Grundkörper aus `PRIMITIVE_TWINS` sichtbar exakt und versteckt als Netz, ohne Kern umgekehrt; Kegel, Kugel und Ring bekommen ihre exakten Erzeuger (`create_brep_cone`, `_sphere`, `_torus` über `edit.cone`, `edit.sphere`, `edit.torus`), der exakte Quader den Bezugspunkt `anchor`, `ANCHORS` und `tube_fits_the_ring` stehen einmal in `primitive_ops`. *Bohrung setzen* und *Aushöhlen* fragen die Körperart ihres Eingangs (`drill_hole` ruft `drill_brep_hole`, `hollow_object` ruft `shell_exact` nach der Tabelle aus §10.1 — `exactly_hollowable`: Oberseite offen, keine andere Öffnung, keine Entlüftung; sonst der Netzweg mit `evaluate.exact_became_mesh`); ihre exakten Zwillinge bleiben für alte Projekte und den Verlauf registriert und versteckt. `TWIN_TOGGLES`, `_EXACT_TOGGLE`, `_HOLLOW_TOGGLE`, `_lock_twin_toggle` und `_twin_toggle_hint` sind weg, vier Sätze aus sechs Katalogen mit ihnen; der Menüweg eines versteckten Zwillings nennt den Weg (`twin_way`). Der Kernwechsel eines gespeicherten Schritts steht im Kontextmenü des Verlaufs (`HistoryPanel.kernelSwitchRequested`, `MainWindow.switch_kernel`, Sätze aus `registry.kernel_switch_label` — Nutzen, nie Rechenkern; nur an den fünf Grundkörpern, denn Bohren und Aushöhlen entscheidet der Körper selbst, und in den exakten Kern nur, wenn er da ist — sonst kein Eintrag) und `History.change_kernel` wirft `needs_exact` mit der Zahl der Schritte, die sonst anhielten; `exact_names()` ist die eine Antwort dafür in Verlauf und Fenster. Aus dem Review vom 21.09.2026 dazu: `create_brep_cone` mit gleichen Radien baut einen Zylinder statt einer Absage aus OpenCASCADE; die Vorschau am Körper (`placement._creation_tool`) kennt die exakten Erzeuger über ihren Netz-Zwilling; die Palette findet alle zehn unter „exakt“; der Agent liest am versteckten Zwilling „Zweite Wahl“ mit dem Eintrag im Menü; fünf Kundentexte und der Handbuchabsatz zu STEP zeigen auf den Verlauf statt auf den Haken, und `kind_requirement` nennt am Netz-Werkzeug *Flächenbearbeitung beenden* statt der fehlenden Kurven. **Gemessen** (`tests/test_kernel_switch.py`, 18 Tests): Richtung der Paare mit und ohne Kern, alte `create_box`-Schritte bleiben Netz, Bohrung am exakten Körper exakt ohne Haken (Volumen auf 10⁻⁶), Aushöhlen nach den drei Zeilen der Tabelle, Kegel, Kugel und Ring gegen die Analytik auf 10⁻⁶ und gegen ihre Netz-Zwillinge auf zwei Prozent an derselben Stelle, Anker und Drehung des Quaders gegen den Netz-Zwilling auf 10⁻⁶, der Kegel mit gleichen Radien, die Vorschau der fünf exakten Erzeuger, der Wechsel im Verlauf mit der Sperre des Kerns und nur an Grundkörpern, das Register ohne OpenCASCADE im Import; im Fenster (`test_ui.py`) der Eintrag am Quaderschritt, nicht an der Bohrung, hin und zurück mit Undo; die Paritätstabelle führt `drill_hole` und `hollow_object` am exakten Körper als `KEEP`, drei Regeldateien zählen 136 Operationen und 1231 Parameter. Endtor: 13421 bestanden, 48 übersprungen, Ruff, Format und mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **Offen aus P2.8:** die übrigen Erzeuger (`create_seal`, Organizer, Skizze, Text) rechnen weiter am Netz und sagen es (`shapes.mesh_only`); die Fenstertests laufen mit dem Release-Tor.
  * **Fensterabnahme 21.09. (`f0e61621`)** — der erste Release-Lauf seit dem 20.09.2026, und er war rot: 110 Fensterfälle in fünfzehn Dateien (74 im ersten Lauf, 36 in `test_ui` und den Viewport-Dateien, hinter denen der Lauf stand). Gemessen am Stand vor P2.8 (`2c70d9a7`, zweiter Arbeitsbaum, beide `FAILED`-Listen mit `comm` verglichen): sechs kamen von P2.8, der Rest aus den Commits des 20.09. (`064e3095`, `1fc131a6`, `102d4bf7`, `5d451fe7`, `851f913a`, `db7d1a5c`), deren Fenstertests nie mit ihrem eigenen Code gefahren worden waren. **Elf Funde in der Anwendung**, alle behoben: Tippen in ein Maßfeld im Bild verzehnfachte die Zahl (zwei Rückwege schrieben während des Lesens formatiert zurück, `reading` in `_place_from_feature_panel`); die Freigabe der Vorschau kam nie, wo ein exakter Körper vernetzt wurde, ein Körper erst im Vorschlag entstand, keine 3D-Ansicht da war oder die Antwort während der Auswertung verfiel (`shown`, `_resume_preview_after_idle`, `differenceApplied` ohne Renderer); *Flächenbearbeitung beenden* galt der Vorschau als leer und ging als Absage hinaus (`_preview_outcome`); ein Quader aus der Befehlspalette über dem Startbildschirm hatte einen freien Übernehmen-Knopf, der nichts tat — die Sitzung war nie ausgewertet (`_begin_from_the_start_screen`: der Anfang ersetzt das offene Projekt, wie beim Einfügen von dort); eine Koordinate senkrecht zur Fläche aus der Maßgruppe verlor ihre Zahl beim Ende der Platzierung (`_hand_quiet_placement_to_panel`); ein Einheitenwechsel rechnete die Analysekarte neu und ein Abbruch hielt nicht (`_map_cancelled_for`); Enter im Fragedialog verwarf die Frage (Fokus auf Abbrechen, `make_primary`); ein Feld ohne Wert im Schritt wanderte mit seiner Vorgabe hinein (`untouched_defaults`); Tabulator, Langlochzug bei stehenden Knöpfen und `DeferredDelete` im Ereignisfilter; und der Absturzbericht als modaler Dialog hielt die Suite offscreen ohne rotes Wort an — der Hänger, den `CLAUDE.md` seit dem 16.08. als nativen Abriss führt, war zur Hälfte das (`report_error` geht offscreen ins Protokoll); und ein freigegebener Objektbaum fing noch an zu zeichnen — der zurückgestellte Start seines Zeichners feuerte nach dem Warten, der Thread überlebte den Prozess (Exit 127 nach „60 passed“; `ObjectTree.release` leert den Vorrat, `MainWindow.release` ruft es). Dazu ein nativer Abriss über dreizehn Portionen (`test_placement_dimensions`, Exit 139, seit `102d4bf7`): Der Aufbau setzte `_surface` ohne `_prepared`, was die Anwendung nie tut, und aus dem `AttributeError` im Ereignisfilter beim Anzeigen wurde unter PySide ein Abriss ohne Traceback — gefunden mit `git bisect` und `sys.settrace`. Dazu dreizehn Wertbeschriftungen, die Tour mit drei Hinweisen und dem Sprung in den Prüfbericht. Die übrigen Tests hielten überholte Stände fest und stehen auf der geltenden Regel mit Datum und Grund (Übernehmen erst nach der dargestellten Vorschau, auch in der Maßgruppe; gestellte Merkmale mit `measure_sources`; der Hinweis auf die Formabweichung in der Kopfzeile des Prüfberichts; drei Knöpfe unten im Merkmalfenster). Release-Tor: Sammelgruppe 13.421 bestanden, 48 übersprungen; Fensterdateien in getrennten Prozessen 18.482 bestanden, 18 rot — genau die Handbuchfälle; Ruff, Format und mypy je 0 (Arbeitsbaum am HEAD mit nur diesen Dateien). **Offen:** `test_manual` und die Handbuchabsätze in `test_wording` (18 Fälle) bis zum nächsten Paketbau. **Entschieden und umgesetzt (`e5ac389a`):** Das Abbrechen des Merkmalfensters hat wieder eine Aufgabe — es steht, solange eine Feldvorschau aus dem Panel wartet, und verwirft sie ohne Schritt und ohne Rückfrage (`offer_cancel`, `_cancel_from_feature_panel`); und der Hinweis auf die Formabweichung ist ein Befund mit Maß geworden (`evaluate.check_form_deviation`: `fit_error` über `units.MAX_FACET_SAG`, am schlimmsten Merkmal, als Weg in die Karte nach §18.4) statt eines Satzes an jedem Körper — ein Quader erreicht wieder „Keine Befunde. Das Teil ist druckbereit.“, die erste Tour nennt wieder zwei Hinweise, die Karte selbst bleibt in der Analyseleiste für jeden. **Und die Leistung ist rot** (`pytest -m performance` im Torbaum, ohne Fremdlast: 38 bestanden, 2 rot), beide seit dem 20.09.: `test_smooth_feature_detection_keeps_its_existing_regression_mark` misst 22,8 s statt unter 10 (Ziel 1 s; `git bisect` mit beiden Tests als Sonde: erster roter Stand `851f913a`, am Tag 0.4.4 noch 3,5 s für beide zusammen), und `test_feature_detection_on_a_freeform_tracks_the_real_customer_path` findet an der Freiform eine Fläche von 0,22 mm², wo keine sein darf (rot zwischen `5d451fe7` und `38e11e09`). Beides gehört zu P1.2 und ist dort vermerkt.
  * **Review über alle Änderungen seit 0.4.4 (21./22.09.2026), eingearbeitet und mit 0.5.0 draußen** — zehn Prüfer nach Gebiet, 148 Befunde, sechs Pakete, jeder Leistungsfund gemessen, jeder Test am Stand davor rot. Exakter Kern: Volumen und Fläche nativ aus dem knotenzerlegten Verbund (STEP-Körper 7–16 s → 0,2 s), starre Bewegungen ohne Integral, Merkmale und Flächenkennzahlen je Körper gemerkt (`features_of` am NURBS-M6 19,6 → 0,9 s), der Gewindeleser mit grober und feiner Abtastung (749 → 97 ms), Gewindebolzen genäht (RM-195), Gewinde einsetzen unter einer halben Sekunde (RM-196), die Aufweitung über einer Durchgangsbohrung an beiden Kernen `through=False`. Netzkern und Szene: die Passung meldet nur Gemessenes (keine `pose_unknown`-Warnung mehr), die Formabweichung gestapelt (Dose mit Deckel 11,8 s → 98 ms), Hash und Cache (Format 23, Kanten je Netz gemerkt, Weg 1 warm 25 → 7 ms), das Schließen an der alten Stelle ohne Narben (796 statt 1852 Dreiecke), eine vergrabene Senkung ohne Volumenverlust, ein Ring ohne Achse sagt ab, Selbstdurchdringung als Feld (5,3 s → 185 ms), Einlesen zählt Kennzahlen einmal, unlesbare Einschlüsse als Warnung. Erkennung: Antworten hängen am Körper und sterben mit ihm (369 MiB tot gehalten → 0), Einschlüsse per Strahltest (1,18 → 0,13 s), ein Kegel zwischen zwei Langlöchern bleibt Kegel, Flächenrollen blockweise, ein Fleck fragt nur seine Ringe (Drache 54,5 → 37,7 s), Bohrungsklick an der 360k-Platte 1,0 → 0,25 s. Fenster und Start: Regel 19 auch feldlos, Gegenstücke asynchron, kein Dialog vor einer exakten Vereinigung, `exact_kernel_present` ohne Import, Start 2,85 → 1,42 s, Hinweise ohne Blase, ein Zug am Modell hält den Vorschlag, der Sitzungsstand rollt nach einem angehaltenen Zug zurück (`halted`). Ansicht: RM-197 bis RM-200. Schichtanalyse und Orientierung: die Suche dreht nur die äußersten Ecken (1,3 M Dreiecke 35 → 5,4 s), `ring_area` einmal, der Keil an jeder fünften Schicht, drei neue Leistungsmarken, `test_parts` 160 → 83 s, `tests.helpers.exact_kernel` mit CI-Wächter, die Paritätstabelle gegen das Register geprüft. Dazu 36 Kundentexte in der Sie-Form und sechs Kataloge nachgezogen. Was offen blieb, steht als RM-201 bis RM-206 im Register; RM-192 und RM-194 sind mit `f0e61621` zu.
  * **implementiert, Release-Abnahme offen** P3.1 — `02b93253`: Der Ebenenvertrag steht.
    `offset:<basis>:<abstand>` liegt parallel zur Basis, `tilt:<basis>:<achse>:<winkel>` ist um
    deren erste oder zweite Achse gekippt, `through:<p>;<p>;<p>` geht durch drei Punkte. Die
    Basis darf selbst abgeleitet sein (bis `MAX_PLANE_DEPTH`), Abstand und Winkel dürfen
    Maßausdrücke aus §13 tragen. **Die Basis steht vorn und der Zusatz hinten**, weil eine
    Flächenebene selbst Doppelpunkte trägt; das Maß prüft schon der Parser, sonst läse
    `offset:plane:xy` als Basis „plane" mit dem Abstand „xy". Beim Kippen dreht die Zeichnung
    mit, bei drei Punkten zeigt die erste Achse vom ersten zum zweiten. `frame_for_plane`
    schweigt, wenn sich eine Ebene nicht auflösen lässt (eine Ansicht ohne Parameter ist kein
    Fehlerfall), `frame_for_sketch` sagt warum. Bauplan §30.1 nennt die drei Formen;
    38 Fälle in `tests/test_sketch_planes.py`, Rundreise durch die Projektdatei eingeschlossen,
    alte Angaben unverändert lesbar. Oberfläche folgt mit P3.3.
  * **teilweise umgesetzt** P3.2 — `a1b9b735` schließt die zwei Lücken, die der Vertrag
    aufgerissen hatte: Ein Projektparameter im Abstand einer Ebene zählt jetzt zu den
    Abhängigkeiten der Skizze (ohne ihn bliebe nach einer Parameteränderung das alte Ergebnis
    im Cache und die Zeichnung auf der alten Höhe), und `standing_on_feature` geht durch alle
    Ableitungen bis zur Fläche — die Verwaisungsprüfung fragte nur `is_feature_plane` und hätte
    eine Skizze auf einer Versatzebene ihre Fläche verlieren lassen, ohne es zu melden. Offen
    bleiben Rahmen und Referenzauflösung über die **übrigen** Verbraucher (`up_to`,
    Feldschnitt, Dichtungswege) sowie dauerhafte Bezüge.
  * **offen** P3.3 — „Neue Ebene …“ mit Art-Auswahl, Menüort vorher benannt
  * **offen** P3.4 — Flächenkontur als eigene Handlung, Außen- und Innenränder
  * **offen** P3.5 — exakter Ebenenschnitt über `BRepAlgoAPI_Section`
  * **offen** P4.0 — Netz → exakter Körper ohne Verlauf: Segmentierung, Fits, Nähen, Formabweichung, STEP-Rundreise
  * **offen** P4.1 — Nachbaukandidaten aus Grundvolumen, Aufträgen und Abzügen
  * **offen** P4.2 — Nachbau mit exakter Ausgabe und unabhängiger Formprüfung, ohne Fertigungskompensation
  * **offen** P4.3 — geprüften Nachbau hinter dem Import atomar übernehmen
  * **offen** P6.1 — variable Verrundung
  * **offen** P6.2 — Fasen mit zwei Abständen oder Abstand/Winkel
  * **implementiert, Release-Abnahme offen** P6.3 — Aushöhlen mit gewählten Öffnungsflächen. `hollow_object` bekommt `openings` (Flächen, `ParamSpec.feature_kinds` = Fläche; ein Klick trägt eine Fläche dort ein, eine Bohrung nirgends), `wall_side` (innen/außen) und `exact_fallback` (nachfragen/Raster/Teil lassen); `open_at` bleibt als Achsöffnung für gespeicherte Schritte, nach hinten, und mit `openings` zusammen eine Absage. Exakt über `brep.profiles.shell_open_at` (`MakeThickSolidByJoin`, Ergebnis nur als gültiger, geschlossener, veränderter Körper — die Bibliothek gibt bei zu dicker Wand und an konkaven Formen den Eingang unverändert zurück), Merkmale über `_exact_features_after` (ungewählte Flächen behalten Namen und Fläche). Am Netz das Raster mit einem Öffnungswerkzeug je ebener Fläche (`geom/hollow._opening_tool`), außen mit derselben Kugel gewachsen und bündigem Rand; `hollow.opening_misses`, und an allen Netzwegen `hollow.closed_cavities` für Hohlräume, die trotz Öffnung oder Entlüftung geschlossen bleiben. Scheitert OpenCASCADE, entscheidet das Raster zwischen `too_thin` und dem erfragten Rückfall (Regel 21, Antwort im Schritt). Semantik für P9.3: Öffnung = fehlende Fläche, Entlüftung = Loch in einen geschlossenen Hohlraum; P9.3 erweitert `vents`. `tests/test_hollow_faces.py` (27): Sollvolumina auf 1e-9 (Quader oben+vorn, außen mit Minkowski-Summe, Zylinder, schräge Keilfläche), Netz im Rasterband mit Punktproben je Fläche, Gegenfälle, Kundenweg §13.9 je Kern (Verlauf, Wand ändern, Datei, Undo/Redo, Abbruch), fünf goldene Volumina alter Schritte; 14 Mutationen rot. **Befund an echten STEPs:** `MakeThickSolidByJoin` scheitert an allen drei verrundeten Kunden-STEPs in jeder Einstellung; dort trägt der erfragte Rasterweg. Offen: ein exakter Weg für solche Körper (§13.8, Alternative prüfen), Entlüftung je getrenntem Hohlraum (P9.3), Fenster beim Release.
  * **offen** P6.4 — Formschräge an gewählten Flächen
  * **implementiert, Release-Abnahme offen** P6.5a–c — Schnitt durch Drehen, entlang einer Bahn, durch Überblenden: `sketch_revolve_cut`, `sketch_sweep_cut`, `sketch_loft_cut` als eigene Operationen mit einem Eingang (Erzeugen und Schneiden sind zwei Handlungen, `consumes` steht je Operation fest), ohne eigenen Menüeintrag in der Variantengruppe *Aus Skizze erzeugen …* direkt hinter ihrem Erzeuger (Konzept §10). Werkzeug aus denselben Helfern wie der Erzeuger (`_revolve_section`, `_swept`, `_loft_outlines`), Lage am Zielkörper über einen geprüften Starrkörperzug, Differenz exakt (`brep.edit.boolean`) oder über die Rückfallkette gegen die Tessellierung (`MAX_FACET_SAG`), Stufe in `solver`, `without_effect` mit Vorschlag. Nut: Achse aus Richtung und Punkt oder aus Bohrung/Zapfen (`axis_feature`), Teilwinkel mit Beginn. Kanal: Anfang an Ober- oder Unterseite (eine schon so gezeichnete Bahn bleibt, sonst Drehung um die Querachse ihrer Ebene), Drehung um die Senkrechte; Bahnprüfung für Erzeuger und Schnitt (Kreuzung, Biegung enger als der Querschnitt, Selbstschnitt über `brep.profiles.intersects_itself` — `BRepCheck_Analyzer` lässt ihn durch). Übergang: nächste Ecken um die Mitten, Gleichstand fragt über `ctx.ask` (`twist`), unvereinbare Umrisse mit Satz. Ein ungültiges exaktes Ergebnis geht nicht hinaus (`brep.profiles.is_sound`, Netzrückweg mit `sketch.exact_cut_unsound`). Nebenbei behoben: Nach *Fertig* landete der gezeichnete Umriss bei *Entlang eines Bogens führen* und *Zwischen zwei Umrissen aufspannen* in Bahn bzw. oberem Umriss (`main_window._sketch_param`). `tests/test_sketch_cuts.py` (38): Pappus, Teilwinkel, Achsschnitt, Innennut mit Merkmalsachse, Kanalquerschnitte und Endlagen, Pyramidenstumpf mit End- und Zwischenquerschnitt, Formabweichung Netz gegen exakt unter `MAX_FACET_SAG`, Gleichstand fragt, Spiegelbilder, Absagen, Stapel mit Parameteränderung, Undo und Projektdatei; Gegenprobe ohne Umsetzung 33 rot. Echte Modelle: `broomholdervcd_d35mm.stl` (Innennut in der Bohrung Ø34, Rasterzählung bestätigt), `carpet-corner-clip.step` (exakte Nut ungültig → Netzrückweg, Rasterzählung bestätigt). Werkzeuglast neu gemessen: 39 987 Token bei 150 Werkzeugen, 97,6 % des Fensters (RM-185). **Offen:** Fenstertests und Leistung beim Release; *Tasche schneiden* gibt an derselben STEP-Stelle einen ungültigen Körper still zurück (kein Teil von P6.5, einzutragen); der Erzeuger `sketch_loft` ordnet weiter über OpenCASCADE zu (alte Projekte); Bauplan §30.1 zählt die Skizzen-Operationen einzeln auf und nennt die Schnitte noch nicht (nur mit Ansage)
  * **offen** P6.6a — Ellipse, Ellipsenbogen, Splines bearbeiten; P6.6b — zusätzliche Bedingungen
  * **implementiert, Release-Abnahme offen** P6.7 — Merkmalsmuster: `pattern_feature` („Merkmal vervielfachen", Kategorie `holes`, ein Körper hinein, einer heraus — nicht `pattern`, das Körper kopiert). Linear, kreisförmig, gespiegelt; Anzahl, Abstand, Winkel, Richtung, Punkt, ausgelassene Plätze; mehrere Quellen, eine Kette als Ganzes. Jede Instanz ist das Werkzeug der Quelle, bewegt (Netz: `_placing_tool`/`_chain_copy_tool`; exakt: `_exact_cavity_tool`, `_exact_chain_tool_placed`, `edit.transformed` des Flächenkörpers, Ring aus Kennzahlen), Merkmale über `transformed_features`. Überschneidung und fehlendes Material je Platz erklärt (`pattern_feature.overlap`/`.no_target`), erkannte Quellen brauchen belegte Flächen (`not_evidenced`). Die Quelle bleibt maßgebend durch die Bauart (der Schritt liest sie bei jeder Auswertung). In `QUICK_FEATURES` an jeder angenommenen Art. `tests/test_feature_patterns.py` (24) mit exakten Sollvolumina, radialen Achsen, gespiegeltem Sackloch, Langlochrichtung, Kette, Korpus-Senkplatte, Kundenweg §13.9 je Kern (Quelle Ø5→Ø8, Datei, Undo/Redo, Abbruch); 13 Mutationen rot; Fenstertest neu (Release). **Frage an Robert offen:** Eine spätere Maßänderung an einer **eingelesenen** Quelle hängt sich hinter das Muster; heute trägt „Auf alle N gleichartigen anwenden", sauber wäre P7.1 oder eine vorbelegte Gruppe.
  * **implementiert, Release-Abnahme offen** P7.1 — Verlaufsschritt einfügen; P7.2 — umsortieren; P7.3 — unterdrücken und reaktivieren. Kern (`History.plan_*`, `scene/revision.py`: isoliert rechnen, Verweise folgen ihrem Merkmal, fragen oder absagen), Format 32 (`suppressed`, `revision`, `example_v32.p3d`; die 31 gehört P6.6), Kommandozeile (`move`, `suppress`, `reactivate`, `run … --before`), Verlaufsfeld mit Kontextmenü, Ziehen und Tastatur, Einfügemarke, Steckbrief mit „aus“/„ruht“. Belegt am Korpus und an zwei Modellen aus `F:\3D Dateien` (Besenhalter als Netz, Druckschale als STEP). Offen daraus: **(a)** ein Agentenwerkzeug `edit_history` — gezählt 120 Token gebündelt gegen 224 für drei getrennte, bei 38 318 von 40 960 im Fenster und RM-185 über seinem Ziel; Entscheidung Robert. **(b)** Am exakten Körper sagen Verschieben und Einfügen von Bohrungen ab, sobald eine neue links von einer vorhandenen landet: `drill_brep_hole` nummeriert nach Lage, und ein späterer Verweis hält mit `NativeReferenceLost` an — genauso, wenn man in dieser Reihenfolge von Hand baut; es fehlt der Namenserhalt am exakten Körper. **(c)** Am Netz hängt die Erkennung einer Durchbohrung an der Vorgeschichte: am Besenhalter dieselbe Geometrie, aber eine erkannte Bohrung mehr, wenn vor der Bohrung kein anderer Schritt lag (Durchbohrung Ø 4 in y bei x = −25 durch drei Wände, einmal direkt nach dem Import, einmal nach *Bohrung vergrößern* an `hole_3`: Volumen gleich, die Wand bei y = 0 nur im ersten Fall als Bohrung erkannt). Die Fenstertests `test_history_revision_ui.py` laufen erst beim Release.
  * **implementiert, Release-Abnahme offen** P7.4 — Paket p7step (`reports/p7step.md`): STEP-Baugruppen über XCAF (`brep.step.read_assembly`) — jede Komponenteninstanz ein unabhängiger exakter Körper mit Weltlage, Namen (Instanz → Referenz → Form) und Flächenfarben (Instanz → Referenz → Form, sRGB), gespiegelte Instanzen als Spiegelbild, Flächenmodelle und reine Kantenteile gemeldet; Importauswahl vor dem ersten Schritt (`ui/step_dialog.py`), gespeichert als `load_step.bodies` (Format 31; ältere Schritte bleiben ein Körper), Farben → Filamentslots nach der 3MF-Regel, STEP-Export mit Namen und Farben. Korpus `tests/data/step/` mit Erzeuger, 55 Kerntests und 7 Fenstertests; echte Dateien `build_tray_v3.step` (5 Körper) und `carpet-corner-clip.step` (2 Körper, 2 Farben). Offen: Fensterabnahme der Auswahl beim Release; bei Robert Farbvorrang, Mehrkörper-Export in eine Datei und die Leistung ab etwa 1000 Instanzen (70 s)
  * **offen** P8.1 — benannte Gruppen, stabile Mitgliedschaft und Regeln für Ersetzen/Teilen/Löschen, Speicherung und Undo
  * **offen** P8.2 — Montage- und Drucklagen derselben Körper speichern; Prüfungen, Cache, Druckplatten und Export auf explizite Lage beziehen
  * **offen** P8.3 — Gruppen-/Lagenbedienung und vorhandene Montageprüfungen; vollständiger Gehäuse-/Deckel-/Schrauben-Kundenweg
  * **offen** P8.4 — Maßblattvertrag: Ansichten, Maße, Referenzen, Herkunft, Einheit und eindeutiger eingefrorener Modellstand
  * **offen** P8.5 — PDF-Maßblatt mit Vorschau, lesbarer Bemaßung und visueller Ausgabeprüfung
  * **offen** P9.1 — Resin-Stufe 1 belegen, technische Restentscheidungen und analytische Sollkörper für Stufe 2 festlegen
  * **offen** P9.2 — Saugglocken mit Ort/Volumen und orientierungsabhängiger Suche
  * **offen** P9.3 — Abfluss-/Belüftungsöffnungen nach Drucklage am vorhandenen Aushöhlen-Weg
  * **offen** P9.4 — Resin-Regeln und vollständige Abnahme aus Resin-Konzept §9, einschließlich FDM-Gegenproben und Slicer-Übergabe
  * **offen** P5.1 — Maßoperationen familienweise auf den Viewport-Editor, Panel-Doppel entfällt
  * **offen** P5.2 — vollständige geltende Bedienanforderungen aus P0.8, Auswahlmatrix am Fenster, kleines Fenster, HiDPI, Themen, Tastatur; Gruppen/Lagen, Maßblätter und Resin eingeschlossen
  * **offen** P5.3 — gemeinsame Gesamtabnahme aller vier Konzepte auf Windows/macOS/Linux mit installierten Paketen; Abschluss von RM-188 innerhalb 0.5.x erst mit allen Fach- und Abdeckungsnachweisen

  **Paketstände für 0.5.0** (Durchsicht vor 0.5.0 und ihre Bauaufträge,
  22./23.09.2026). Je geändertem Paket der Stand nach der Übernahme; wo ein
  Statuswort der Liste darüber älter ist, gilt diese Tabelle. Die Fensterabnahme
  aller hier als implementiert geführten Pakete gehört zum Release (RM-213).

  | Paket | Stand für 0.5.0 | Beleg |
  |---|---|---|
  | P1.3 | **implementiert, Release-Abnahme offen** — Zusatz: jedes Maß sagt seine Herkunft mit einem Wort aus einer Tabelle (`native` → „aus der Konstruktion“, `parameter` → „aus dem Schritt“, `facets` → „gemessen“, `fit` → „eingepasst“); an Marken in der Ansicht nur das warnende Wort | `f64e17c7` (beziehungen B14/B24) |
  | P1.4 | **läuft** — Nachtrag **P1.4c.3**: Die native Neuwahl nimmt ihre Antwort an, wenn die Geometrie den alten Bezug eindeutig einem Merkmal unter anderem Namen zuordnet (der Nachfolger steht als erste Antwort da); eine bis auf Rechenrauschen unveränderte Fläche belegt ihren alten Namen (`_unchanged_continuations`), am Teppichclip fragt *Fläche versetzen* nicht mehr nach unberührten Passungsflächen. Dateiseite: Antworten der Formate 27–29 überstehen Öffnen, Speichern und Wiederöffnen an allen 39 Beispielprojekten, auch in den Undo-Fassungen | `f64e17c7` (beziehungen B23/B25), `28cddadf` (bez2, Tests dazu), `56f70000` (szene) |
  | P2.1 | **implementiert, Release-Abnahme offen** — Zusatz: die affine Abbildung schreibt nicht mehr in ihren Eingang, eine Verschiebung reicht den Hüllquader weiter, große gespiegelte NURBS-Quader behalten ihre sechs Ebenen. Rest am Netz: RM-216 | `3355dbf5` (exakt E-02/E-17/E-20) |
  | P2.2 | **implementiert, Release-Abnahme offen** — Zusatz: an `build_tray_v3.step` und `Cat_1.stp` nachgemessen, exakt erhalten, genau die Fläche gefärbt | `54f922e0` (formops) |
  | P2.3 | **läuft** — Kegel aus NURBS mit Beweis über alle Bézier-Koeffizienten, gespiegelte NURBS-Ebenen über die Polebene, dichte STEP-Schalen ohne Körper werden Körper und offene melden sich, die Integrationsleiter teilt Extrusionen und Drehflächen vollständig; Merkmale aller fünf echten STEP-Dateien gleich. Offen: die vollständige Semantik- und Teilflächenparität | `3355dbf5` (exakt E-16/E-17/E-18/E-24) |
  | P2.4 | **implementiert, Release-Abnahme offen** — Zusatz: `resize_feature` bleibt an Zapfen, Kegel und Kugel exakt (`_exact_resize_by_faces`) — die Aussage „am exakten Körper vernetzt keine Merkmalshandlung“ war bis dahin falsch | `00b09a2d` (merkmalsops 6) |
  | P2.5 | **implementiert, Release-Abnahme offen** — Zusatz: kegelige, dreigängige, innen zweigängige und Linksgewinde gelesen und gebaut; Gegenstück, Ändern und Entfernen sagen dort mit Grund ab; ein zweigängiges Innengewinde galt nicht als Gewinde. Der **Netzleser** misst Händigkeit, Vorschub, Gangzahl, Kamm und Grund an den Kanten (Gewindebank 35 von 35 statt 27, Gegenlauf über 172 Dateien ohne Fehlalarm) | `3355dbf5` (exakt E-08–E-11), `3fa7d719` (erkennung B3) |
  | P2.6 | **implementiert, Release-Abnahme offen** (vorher läuft) — `test_torus_feature_ops` und `test_thread_feature_ops` grün, keine weitere Lücke gefunden; das Ringwerkzeug kommt plattformgleich aus `ring_of_revolution` | `00b09a2d` (merkmalsops 12) |
  | P2.8 | **implementiert, Release-Abnahme offen** — Zusatz: Text, Dichtung, Deckel und Drehdeckel fragen die Körperart ihres Eingangs und bleiben am exakten Körper exakt; der Kragen folgt in beiden Kernen der engsten Öffnung. **Offen: die Erzeuger ohne Eingang** (Organizer, Text, Zeichnung, zehn eigenständige Bausteine, Klemmensatz) — den Mechanismus entscheidet Robert, empfohlen ist ein beim Anlegen gesetzter Kernparameter | `3355dbf5` (exakt E-23/E-25/E-27/E-28/E-29) |
  | P3.2 | **teilweise umgesetzt** — Feldschnitt, Dichtweg, Dichtnut und Projizieren lösen abgeleitete Ebenen mit Projektparametern auf, Maßänderung, Verschieben und Drehen sind an beiden Kernen als Test belegt. Offen: Flächen, die eine spätere Operation teilt (Zuordnung §21), und dauerhafte Bezüge beim Neuverknüpfen (`scene/orphans.py`) | `f19a7b4b` (skizze B15/B16), `56f70000` (szene 34/35) |
  | P3.3 | **implementiert, Release-Abnahme offen** — „Neue Ebene …“ als letzter Eintrag im Ebenenfeld der Skizzenleiste und als vierte Karte im Ebenenwähler, kein Menüeintrag; Dialog mit Art, Basis, Abstand/Winkel als Projektparameter, Vorschau, ein Schritt | `f19a7b4b` (skizze) |
  | P3.4 | **implementiert, Release-Abnahme offen** — Knopf *Flächenkontur* neben *Projizieren*: die Ränder der Fläche unter der Zeichnung als feste Hilfsgeometrie, am exakten Körper aus seinen Kurven, am Netz mit Kreisen aus belegten Merkmalen | `f19a7b4b` (skizze) |
  | P3.5 | **implementiert, Release-Abnahme offen** — `brep.section.plane_section` schneidet exakt (Kreise, Bögen, Strecken, sonst Kurven durch Punkte der echten Schnittlinie); am Netz holt die Projektion auf einer Fläche deren Rand | `3355dbf5` (exakt E-12/E-31) |
  | P4.0 | **implementiert, Release-Abnahme offen** — `mesh_to_exact` „In Flächen und Kanten umwandeln“: analytische Flächen aus den Trägern der Erkennung, Rest ebene Dreiecke mit Anteil, Absage bei Freiform über 20 000 Dreiecken, beidseitige Abweichung als Befund und in der Formabweichungskarte, danach STEP und *Bohrung ändern* exakt; Exportdialog und Absagen nennen den Weg. Offen daraus: Handkorrektur der Bereiche und exakte Körper im Plattencache (beides Entscheidungen Roberts), Rundungen aus Facetten langsam (Besenhalter 150 s, RM-219), Nachbau-Tests für zwei Nähbefunde, Paketprobe mit `OCP.GeomAPI`/`OCP.GeomAdaptor`. Bauplan §30 und §42 sind nach Roberts Entscheidung vom 23.09. im selben Commit nachgezogen | `596bcb64` (p40) |
  | P6.1 | **implementiert, Release-Abnahme offen** — variable Verrundung an beiden Kernen; Grenzen unter RM-230 | `e1616285` (p6a) |
  | P6.2 | **implementiert, Release-Abnahme offen** — `chamfer_edges` mit gleich / zwei Abständen / Abstand und Winkel und `flip_sides` an beiden Kernen; die Bezugsseite steht im Bild und lässt sich tauschen, die Kantenzeile im Merkmalfenster trägt Art, zweiten Abstand und Winkel; der exakte Kern lehnte eine Fase mit zwei Abständen an einer Kreiskante immer ab (behoben) | `00b09a2d` (merkmalsops), `cf2fe7d3` (p62) |
  | P6.3 | **implementiert, Release-Abnahme offen** — *Aushöhlen* mit gewählten Öffnungsflächen, Befund `hollow.closed_cavities`. Offen: exakter Weg für verrundete Kunden-STEPs (`MakeThickSolidByJoin` scheitert an allen drei gemessenen Teilen, bedienbar über den erfragten Rasterweg), am Netz nur ebene Öffnungen | `edf07816` (p6b) |
  | P6.4 | **implementiert, Release-Abnahme offen** — Formschräge an gewählten Flächen, beide Kerne; Grenzen unter RM-230 | `e1616285` (p6a) |
  | P6.5a–c | **implementiert, Release-Abnahme offen** — Zusatz offen: Einstieg am Merkmal (die Nut hat kein `applies_to`, gehört zu P5.1) und `sketch_loft` entscheidet Gleichstand weiter still über OpenCASCADE | `8d8925cd` (p6c) |
  | P6.6a/b | **implementiert, Release-Abnahme offen** — Ellipse und Ellipsenbogen in Löser, Profil, Netzweg, exaktem Kern und allen Skizzen-Operationen, Splines direkt bearbeiten; *Punkt auf Kurve*, *Tangential* über alle Kurvenpaare außer zwei Linien, *glatt* und *krümmungsstetig*; Format 31 | `11c429cc` (p66) |
  | P6.7 | **implementiert, Release-Abnahme offen** — `pattern_feature` linear, kreisförmig, gespiegelt; die Quelle bewegt sich, ein neues Muster entsteht nicht als Kopie | `edf07816` (p6b) |
  | P7.1–P7.3 | **implementiert, Release-Abnahme offen** — Entwicklungstor im Arbeitsbaum ohne eigenen roten Fall (15 973 bestanden; rot nur Bereichsnachweis und drei Lizenzprüfungen der geteilten `.venv`); Einfügen, Umsortieren, Unterdrücken und Reaktivieren als Transaktion über einem Stapel, Verweise folgen ihrem Merkmal oder der Umbau sagt ab; Kommandozeile `suppress`/`reactivate`; Format 32. Offen: Agentenwerkzeug `edit_history` (Entscheidung Robert, zusammen mit einer Kürzung nach RM-185) und der Namenserhalt am exakten Körper (RM-218) | `677923e5` (p7verlauf) |
  | P7.4 | **implementiert, Release-Abnahme offen** — STEP-Mehrkörperimport über XCAF mit Namen, Flächenfarben und Instanzlagen, Auswahl vor der Übernahme, `load_step` legt das erste Modell aufs Bett; der STEP-Export schreibt Namen wörtlich und Umlaute nach ISO 10303-21; Format 33. Offen: Farbvorrang, Name eines einzelnen Körpers, Export mehrerer Körper als eine Baugruppe, Leistung großer Baugruppen und Filamentvorschlag je Farbe — Entscheidungen Roberts | `896622bd` (p7step) |
  | Zeichnen Z0/Z1 | **implementiert, Release-Abnahme offen** — aus der Bedienabnahme „Zeichnen“ (Robert, 23.09.2026, Bericht zeichnen-bedienung): Hochziehen auf einer gewählten Fläche geht und wird Teil des Körpers (`sketch_join`), eine Tasche außerhalb des Ursprungs schneidet dort, wo gezeichnet, Verrunden und Fase lassen das bemaßte Rechteck stehen, *Fertig* hat eine Bedeutung (die übrigen Arten unter *Mehr*), Escape verwirft keine Zeichnung, Zeichnen gilt einem Körper (Nachbarn ausgeblendet, *Nachbarn zeigen* mit N), *Hier zeichnen* und *Loch oder Aussparung zeichnen …* im Auswahlfenster, *Zeichnung weiterverwenden* im Verlauf | `4406137f` (zeichnenbau) |
  | Zeichnen Z2–Z6 | **offen** — Z2 Erstellen im Bild (Palette am Umriss statt Dialog, Drehachse gemeinsam mit P6.5), Z3 Bemaßen und Fang, Z4 Auswählen/Verschieben/Drehen (Links-Ziehen zeichnet), Z5 Werkzeuge mit P6.6a (900-Punkte-Grenze der Leiste), Z6 Ansicht und Texte, danach die Handbuchseite „Zeichnen“ einmal neu. Dazu die sechs Hinweise aus P6.6 für den Umbau: Werkzeugzeile mit 872 von 900 Bildpunkten voll, Entf löscht bei einem gewählten Splinepunkt das ganze Element, der Hilfspunkt einer Tangente ohne Stoß bleibt sichtbar, Ellipsenachsen nur als Punktabstand bemaßbar, Laufrichtung des Ellipsenbogens beim Zug unsichtbar, lange Bedingungszeile bei zwei Kurven | Reihenfolge und Abnahme je Etappe: Bericht zeichnen-bedienung §8, zeichnenbau „Vorschlag Etappe 2“, p66 „Für den Zeichnen-Umbau“ |

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


<a id="rm-201"></a>

- [ ] **RM-201 — Ein hohler Körper hält die 300 ms der Schichtanalyse nicht.**
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

<a id="rm-212"></a>

- [ ] **RM-212 — Die Vorschau großer Teile hält den Hauptthread und rechnet vergeblich.**
  Was nach der vierten Runde von RM-208 bleibt (Bericht vorschau, Ansicht
  B18/B19, fenster). Drei Posten, jeder gemessen: `manifold3d.simplify` hält den
  GIL, die erste grobe Vorschau steht deshalb einmal je Körper im Hauptthread
  (Platte 0,57 s, Voronoi-Spiderman 2,0 s); derselbe Stillstand trifft
  `decimate_for_display` im Arbeiter des Viewports. Der Anzeigeweg fährt an
  Netzen, die der Kern nicht unter das Ziel bringt, sechs vergebliche
  Kernschritte, bevor das Raster drankommt (Spiderman 4,1 s, Piratenschiff
  4,8 s). Und die genaue Vorschau großer Teile bleibt langsam (Senkplatte mit
  311 296 Dreiecken 8–15 s, davon Boolesche Stufe 4,8 s, `compare_scenes` 4 s,
  Erkennung 1,8 s; Piratenschiff 20–37 s); sie hat seit `a4f2428c` Balken und
  *Abbrechen*, schneller wird sie erst mit einem Tausch des Hohlraums am lokalen
  Ausschnitt statt am ganzen Körper. Bewusst nicht gebaut: ein Merker „grobe
  Stufe scheitert hier" (an den drei Rückweg-Modellen versucht jede Zahl erst
  grob, 0,1–0,5 s). Weg: das Raster vorziehen, sobald die Kernkurve flach wird;
  `simplify` in einen Unterprozess oder vor die erste Vorschau ziehen; den
  lokalen Tausch als eigene Stufe der genauen Vorschau. Abnahme: keine grobe
  Vorschau über 0,2 s im Hauptthread, Spiderman und Piratenschiff unter 1 s bis
  zum Raster, Senkplatte genau unter 3 s — gemessen mit
  `sonden/vorschau/probe_preview.py` auf ruhiger Maschine.

<a id="rm-216"></a>

- [ ] **RM-216 — Ein erzeugtes Flächenmerkmal behält nach einer Änderung seine alte Fläche.**
  Gefunden in der Durchsicht 0.5.0 (Paket exakt, Rest der Lücke 2 aus RM-188,
  Sonde `sonden/exakt/s35_stale_area.py`): `face_top` aus `create_box` trägt
  nach einer Durchgangsbohrung weiter 2 400 mm², die frische Erkennung misst
  2 349,878 mm². Die Dreiecke des Merkmals sind nachgeführt, seine Maße nicht,
  denn `evaluate._with_features` reicht Merkmale, die ein Baustein oder
  Grundkörper mitgebracht hat, ohne Neuerkennung weiter. Am exakten Körper
  stimmt es (native Neuerkennung). Wirkung beim Kunden: Steckbrief, Agent und
  Merkmalfenster nennen eine Fläche, die es so nicht mehr gibt. Weg: Test zuerst
  mit der Sonde als Fall; die Kennzahlen gebauter Merkmale nach einer formenden
  Operation aus ihren nachgeführten Dreiecken neu messen, ohne die Kennung zu
  verlieren. Abnahme: Fläche, Normale und Mitte gebauter Merkmale stimmen nach
  jeder Operation mit der frischen Erkennung überein, am Netz wie am exakten
  Körper.

<a id="rm-217"></a>

- [ ] **RM-217 — Die Zuordnung meldet doppelt und fragt ohne Bild.**
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

<a id="rm-218"></a>

- [ ] **RM-218 — Am exakten Körper heißen Bohrungen nach ihrer Lage, und der Verlauf lässt sich dort nicht umbauen.**
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
  Passungen folgen ihrem Merkmal, Strg+Z stellt den Stand bitgleich her.

<a id="rm-222"></a>

- [ ] **RM-222 — Die Erkennung einer Durchbohrung am Netz hängt an der Vorgeschichte.**
  Gemessen beim Bau von P7 (Bericht p7verlauf, Abschnitt 7) am Besenhalter
  (`broomholdervcd_d35mm.stl`): Dieselbe Geometrie, einmal mit vorherigem
  *Bohrung vergrößern* und einmal ohne gebaut, erkennt einmal eine Bohrung mehr
  (die Wand bei y = 0). Die Gegenprobe ist sauber — dieselbe Folge von Hand
  gebaut ergibt bitgleich dasselbe Netz und dieselben Merkmale wie der Umbau —;
  die Erkennung hängt also nicht am Umbau, sondern an der Vorgeschichte. Das
  macht „reproduzierbarer Endstand" an Merkmalsnamen fest, die von der
  Reihenfolge abhängen, und ist dieselbe Familie wie RM-210. Weg: die zwei
  Stände als Korpusfall einchecken, die Stelle eingrenzen (vermutlich das
  Mitführen gebauter Merkmale gegen die frische Erkennung, `carry_detection`).
  Abnahme: beide Wege liefern dieselben Merkmale.

<a id="rm-225"></a>

- [ ] **RM-225 — Das Muster eines echten Schraubdeckels lässt sich nicht sauber ändern oder entfernen.**
  Seit der Durchsicht 0.5.0 (erkennung B9) ist die Riffelung der
  Gewürzregal-Deckel ein Muster (24 Mulden um Ø 40, Teilung 5,237). Zwei Wege
  scheitern daran (erkennung, „Für andere Gebiete"): *Teilung ändern* zeichnet
  dicht und mit plausiblem Volumen neu, danach ist der Rand aber kein Stift mehr
  (124 Flächen), und das neue Muster wird nicht wieder gelesen — vermutlich
  reicht das Feld des Neuzeichnens durch das Band unter den Mulden, sodass die
  Stege nicht mehr zusammenhängen; am synthetischen Griff mit oben offenen
  Rillen geht derselbe Weg. *Entfernen* von Mulden, die durch eine Stirnfläche
  laufen, schließt die Kerben dort mit je einer eigenen Fläche (31 zusätzliche
  Flächen am Griff) und bringt 1,7 mm³ Überlappung mit. Weg: Test zuerst mit dem
  Deckel aus `F:\3D Dateien` als nachgebautem Korpusfall; das Feld auf die Tiefe
  der Mulden begrenzen, die Stirnkappen mit der Stirnfläche verschmelzen.
  Abnahme: Teilung ändern am Deckel liefert einen Stift mit wieder gelesenem
  Muster, Entfernen eine Stirnfläche ohne Zusatzflächen und ohne Überlappung.

<a id="rm-226"></a>

- [ ] **RM-226 — Netz und exakter Kern nennen dieselbe Fläche verschieden.**
  Zwei Zwillingsbrüche aus der Durchsicht 0.5.0: Der exakte Kern nennt jeden
  Zylinderausschnitt unter 300 Grad eine Verrundung, das Netz nur einen, der die
  Kante zwischen zwei Ebenen ersetzt (`replaces_an_edge`) — am Quader mit
  gewölbter Oberseite bei 6, 12 und 30 Grad exakt „Verrundung R 382 / 191 / 77",
  am Netzzwilling „gekrümmte Fläche" (erkennung, `zwilling_bogen.py`, am alten
  Stand genauso). Und *Fläche versetzen* an einer Quaderseite lässt am exakten
  Körper die angesetzte Scheibe als eigene koplanare Flächen stehen (Deckfläche
  1 200 + 30 mm² statt 1 230), worauf die native Erkennung unberührte Flächen
  neu nummeriert (beziehungen; die Neuwahl fragt seit B25 nicht mehr, die
  Topologie bleibt). Weg: die Regel des Netzes an den exakten Kern
  (`replaces_an_edge`), koplanare Flächen nach dem Versetzen vereinigen
  (`ShapeUpgrade_UnifySameDomain`). Abnahme: beide Fälle in
  `test_exact_body_parity` als KEEP mit gleicher Merkmalsart und Flächenzahl.

<a id="rm-227"></a>

- [ ] **RM-227 — Eine Tasche am Teppichclip gibt einen ungültigen exakten Körper mit 0 mm³ Abtrag still zurück.**
  Nebenbefund beim Bau von P6.5 (Bericht p6c, „Bewusst offen" 3), am Stand davor
  genauso: `sketch_pocket` mit Ø 11 um die Bohrung von `carpet-corner-clip.step`
  liefert einen ungültigen exakten Körper und trägt nichts ab — ohne Befund. Das
  ist ein falsches Ergebnis, das der Kunde erst am Teil sieht.
  `profiles.is_sound` steht seit P6.5 bereit. Weg: Test zuerst am Clip; nach dem
  Schnitt Gültigkeit und abgetragenes Volumen prüfen und mit Satz und Weg
  absagen, statt das Ergebnis weiterzugeben; dann die Ursache (Tasche auf
  gewölbtem Rand, Tangentialberührung?) eingrenzen. Abnahme: am Clip entweder
  das richtige Volumen oder eine Absage nach Regel 17.

<a id="rm-228"></a>

- [ ] **RM-228 — Die Slicer-Übergabe lässt Lüfter und Spulen beim Hersteller.**
  Aus Roberts Befund „Modelllüfter immer 100 %" (Bericht luefter, 23.09.2026):
  Die Kurve aus Mindest- und Höchstwert mit Schichtzeitschwelle ist gebaut, alte
  Projekte lesen den gespeicherten Wert als Höchstwert und bekommen Mindestwert
  und Schwelle aus dem Materialprofil (luefter, `6a53f0a9`). Offen bleibt:
  Solidons PLA-Vorgabe 50…100 % folgt Elegoos Profil für den CC2, während Orca
  Generic PLA und PrusaResearch fest 100 % fahren — die Materialprofile sind
  druckerunabhängig, und ob die Vorgabe so bleibt, entscheidet Robert; nicht in
  Solidon und damit beim Herstellerprofil bleiben Überhangschwelle,
  Lüfterhochlauf, Innenbrücken-, Stützschnittstellen- und Bügellüfter, der
  **Hilfslüfter des Centauri** (`additional_cooling_fan_speed`, im Lauf
  `M106 P2 S0`) und der Kammerlüfter aus Elegoos Filament-Startcode;
  PETG-Brückenlüfter 100 % gegen Elegoos 90 % meldet `slicer.filament_differs`.
  Daneben (formops): Eine deklarierte, aber unbemalte Spule geht aus älteren
  Projekten über `threemf.assembly_slots` weiter als Filament in die Baugruppe;
  neue Projekte erzeugen keine mehr. Weg: `merge_slots` nimmt nur benutzte Slots
  (`tools_in_use` weiß es); je Lüfterschlüssel entscheiden, ob Solidon ihn
  schreibt, und die Gegenprobe darauf ansetzen. Abnahme: am CC2 und an einem
  Prusa je ein Lauf, Lüfterwerte im G-Code wie im Dialog, keine unbemalte Spule
  in der Übergabe.

<a id="rm-229"></a>

- [ ] **RM-229 — Anordnen legt ein zu großes Teil über die Kante, und geteilte Stücke heißen nach einem Buchstabenpfad.**
  Aus der Durchsicht 0.5.0 (trennen): Ein Körper, der mit dem Anordnungsrand
  nicht auf die Platte passt, wird trotzdem an die Kante gelegt und steht über
  (gemessen: x bis 108,5 bei freigegebenen 108); das Ergebnis meldet es richtig
  als `arrange.out_of_build_volume`, eine Lage in der Mitte mit kleinerem Rand
  wäre die freundlichere Antwort — Auto Split umgeht es seit `0367d202` über
  `bed_margin`. Und mehrfach geteilte Stücke heißen „Wandleiste B A · Stifte";
  das mittlere Stück trägt Stifte **und** Löcher, heißt aber nur „· Stifte"
  (`prepare_ops.half_names`, bewusst so entschieden). Weg: in
  `prepare.arrange_on_bed` den Rand vor dem Überstand verkleinern; für Auto
  Split mit drei und mehr Stücken eine Nummerierung („Wandleiste 1 von 3") —
  Entscheidung bei Robert. Abnahme: kein Überstand, wo die Mitte passt; Namen,
  die Stifte und Löcher richtig nennen.

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

<a id="rm-239"></a>

- [ ] **RM-239 — Verschweißen entscheidet für das ganze Netz, nicht je Punktgruppe.**
  Aus der Durchsicht der Dreieckserkennung und Reparatur (24.09.2026, Befund
  B8 der Erkennung, B16 der Reparatur). Der Ring aus `Siebhalter+X1C.3mf`
  (7 996 Dreiecke, Schweißtoleranz 0,092 µm) trägt 12 Eckpaare im Abstand
  0,015 µm auf zwei Blättern derselben Fläche. Unbeschädigt bleibt er
  unverschweißt (`repair.weld_skipped`, sonst 18 verzweigte Kanten); mit einem
  Riss daneben (74 offene Kanten) überwiegt die Heilung in der Summe
  (`repair._tears_it_further`), die Paare werden zusammengelegt, 24 Dreiecke
  fallen, und aus 16 Flächen werden 28. Der Import fragt dieselbe Sache anders
  — er nimmt nur ein Verschweißen zurück, das einen dichten Eingang aufreißt
  (`ingest.loader.normalise`, Schritt 2) —, und die Karte behauptete bis heute,
  beides sei dasselbe. **Warum es nicht in dieser Durchsicht behoben ist:** Eine
  Gruppe, deren Zusammenlegen ein Dreieck plattdrückt oder eine Kante verzweigt,
  einfach getrennt zu lassen, reißt jede Dreieckssuppe auf — dort ist jede
  Gruppe ein Zusammenlegen aller Kopien einer Ecke, und eine gehaltene Gruppe
  hinterließe um diese Ecke einen offenen Kranz. Die Gruppe muss nach dem
  Flächenblatt getrennt werden, zu dem ihre Kopien gehören, und das ist eine
  Frage an die Nachbarschaft, die erst das Verschweißen herstellt. Abnahme:
  Würfel mit zwei 10⁻⁸ mm getrennten Ecken auf zwei Blättern plus Riss →
  Riss geschlossen, Ecken getrennt, Dreieckszahl gleich; jede STL des Korpus
  kommt so dicht heraus wie heute; Import und Reparatur fragen dieselbe
  Funktion.

<a id="rm-240"></a>

- [ ] **RM-240 — Eine halbe Bohrungswand kommt als flacher Deckel zurück.**
  Aus derselben Durchsicht (Befund B4 der Erkennung). Fehlt ein Teil einer
  Bohrungswand, ist der Rand ein einziger Ring aus zwei Bögen und zwei
  Mantellinien. Seit dem 24.09.2026 füllt die Reparatur Ringe bis 32 Ecken
  über alle Triangulierungen (`repair._smoothest_fill`): Ein Viertel der Wand
  an `plate_holes.stl` (26 Ecken) kommt als Wand zurück, die Platte behält
  vier Bohrungen und ihr Volumen. Die halbe Wand (50 Ecken) schließt weiter
  flach — dort ist die flache Schließung aus zwei Halbkreisen und einem
  Rechteck kleiner als der halbe Mantel (62,8 gegen 65,3 mm²), und der Knick
  gegen die Nachbarn ist in beiden Fällen ein rechter Winkel; die Platte hat
  danach drei Bohrungen, eine gerundete Seite und 25,9 mm³ mehr. Welche
  Schließung gemeint war, sagt nur die Form der Restwand. Weg: Wo die
  Erkennung am beschädigten Netz die Restwand als Zylinder (oder Kegel) belegt,
  setzt die Füllung sie mit denselben Teilungen fort, statt nach Knick und
  Fläche zu wählen. Abnahme: halbe und Dreiviertelwand an `plate_holes.stl`
  und der Senkungskegel an `plate_countersunk.stl` kommen mit vier Bohrungen
  und dem Volumen der unbeschädigten Platte zurück; eine gerade Wand mit
  fehlendem Stück bleibt eben.

<a id="rm-243"></a>

- [ ] **RM-243 — Splinestücke von Schriftzügen und Streben werden als Verrundungen eingepasst.**
  Gefunden beim Abschluss von RM-219 (25.09.2026). Die Nachtrennung
  (`CURVATURE_JUMP`) zerlegt einen Umriss mit verrauschtem Radius je Dreieck
  in kurze Stücke, und ein Stück von vier bis acht Streifen trifft einen
  Kreis auf Mikrometer — `fit_cylinder` nimmt es an. Am Screen-Cover
  (`Screen-Cover_RS.stl`, `…_Basis.stl`, `…_RS.3mf`) werden so die Buchstaben
  „RS" zu 23 bis 25 Verrundungen mit wandernden Radien (11,05 · 11,21 ·
  11,34 · 11,46 … mm, 2 bis 10 µm neben dem Kreis); bis RM-219 verwarf sie die
  fehlerhafte Gewinderegel, und die Seiten trugen gar kein Merkmal. Dieselbe
  Klasse am Eiffelturm (sechs neue Strebenstücke für zwei alte). Die am
  Prisma bewährten Größen trennen in der normalen Runde nicht: Die echten,
  aber µm-rauen Flaschentaschen R 49 des Flaschenhalters haben dieselbe
  Kreisabweichung und ein ebenso lautes Radiusfeld. Weg: an den Stücken eines Flecks prüfen, ob
  sie zusammen einen Umriss mit stetig wanderndem Radius bilden (benachbart,
  tangential, Radius und Mitte wandern ohne Sprung) — dann ist der Fleck eine
  gerundete Seite; die Flaschentaschen als Gegenfall. Abnahme: Screen-Cover
  ohne Verrundungen an den Buchstaben, Flaschenhalter, Besenhalter und die
  übrigen Korpuskörper Merkmal für Merkmal gleich.

<a id="rm-244"></a>

- [ ] **RM-244 — Die Schnittsuche endet an Nadeldreiecken am Budget.**
  Aus RM-219 (Nebenbemerkung, Befund B15 der Bausteine) und am 25.09.2026
  nachgemessen: `repair.crossings_of` am Besenhalter (59 740 Dreiecke,
  Median-Seitenverhältnis 131) prüft in 6,4 s 35 648 der 59 740 Dreiecke und
  endet am Budget von zwei Millionen Paaren (`complete=False`). Die
  Netzfehlerkarte zeigt den Rest als unbekannt, und *Überschneidungen
  auflösen* weiß nicht, ob der Körper sauber ist. Lange Nadeln haben große
  Hüllquader, und Nachbardreiecke teilen fast immer eine Ecke. Weg: messen,
  welche Paare das Budget verbrauchen, und sie billiger ausschließen, ohne
  eine Durchdringung zu übersehen. Abnahme: Besenhalter vollständig geprüft
  unter dem Budget, dieselben Paare wie der skalare Weg
  (`tests/test_self_intersections.py`).

## Bedienung und Darstellung

<a id="rm-238"></a>

- [~] **RM-238 — Lokale Formenerkennung aus dem Bericht und mit der Tastatur bedienen.**
  Die Großmodellbefunde bieten die lokale Erkennung direkt an. Der nächste
  Oberflächentreffer bestimmt einen der vom Befund betroffenen Netz-Körper;
  eine zufällige Baumauswahl ersetzt das Ziel nicht. Eine ungültige Stelle
  kann erneut gewählt werden, ohne die Erkundung ins Dokument zu übernehmen.

  Menü, Palette und Bericht verwenden `LocalRecognitionFlow.arm`. Während
  dieser Auswahl bewegt die Tastatur ein sichtbares Fadenkreuz; Enter folgt
  demselben Originaltreffer wie die Maus, Umschalt ermöglicht Feinschritte.
  Abbruch, Projektwechsel und Beginn der Erkennung entfernen die Auswahlhilfe.
  Fensterfälle sind ergänzt. **Offen bleibt ihre native Release-Abnahme**:
  Bericht → Körper → Stelle → erkannte Form → Änderung und Undo, vollständig
  mit Tastatur, einschließlich Fokus, Abbruch und Rückkehr bei mehreren DPI-Stufen.

  Nachgezogen am 24.09.2026 aus der Bedienweg-Durchsicht (E1–E7): Der
  Kartenbefund `ingest.very_large` trägt die lokale Erkennung nicht mehr, der
  Befund `perceive.too_large` am Ladeschritt dafür *Alle Merkmale erkennen*;
  jeder Fehlergrund der lokalen Suche bietet die Wege, die sein Satz nennt, als
  Knöpfe (Suchradius vergrößern oder verkleinern mit sofortiger neuer Suche,
  andere Stelle, Dreiecke verringern, Netz reparieren); eine Auswahl, die nicht
  beginnen kann, sagt den Grund; „Suchradius" und „gefunden" statt „Radius" und
  „vollständig". Die Fensterfälle dazu gehören zur Abnahme oben.

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
  echten Fenster beim Release 0.5.0 — dazu die Stufe an der Grenze „ganz
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
  Rechtecke, nicht betroffen. Die Probe über den echten Startweg beim Release
  0.5.0 noch einmal fahren. Ob Windows D3D12 als Backend bekommt, wo es da
  ist (unter D3D12 gab es den Fall nie), ist eine eigene Entscheidung und
  kein Muss mehr.

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
  beim Release 0.5.0: Bohrung an Weg 1 wählen, rechts kein Durchmesser, keine
  Koordinaten; endet die Maßgruppe, stehen sie wieder. Escape und Abbrechen
  wählen dabei seit dem 25.09.2026 ab (Entscheidung Robert), rechts steht
  danach nichts mehr.

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

<a id="rm-205"></a>

- [ ] **RM-205 — Escape in der dritten Stufe der Platzierung springt in den
  Dialog.** Gefunden am 21.09.2026 im Review (Ansicht #11):
  `placement_flow.py` sendet `surfaceRequested` ohne Sender; Escape in Stufe 3
  überspringt Stufe 2 und landet im Dialog, und aus dem Dialog führt kein Weg
  zurück in Stufe 1. Das ist eine Bedienfrage nach §2 und §19, keine
  Codefrage: Welche Stufe ein Escape verlässt und wohin es führt, entscheidet
  der Ablauf, nicht die Signalverdrahtung. Weg: `bedienlogik` entwirft den
  Rückweg Klick für Klick, dann die Umsetzung mit einem Test je Stufe.
  Abnahme: ein Escape je Stufe geht genau eine Stufe zurück, der Dialog hat
  einen Rückweg in die erste, und kein Zustand bleibt ohne Sender.

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

<a id="rm-084"></a>

- [ ] **RM-084 — Kundentexte gegen die vereinbarte Sprache prüfen.** Website, Handbuch und sichtbare
  Anwendungstexte systematisch auf Roberts persönlichen, natürlichen Ton prüfen und verbleibende
  Stellen überarbeiten. Abnahme: vollständige Liste der geprüften Bereiche, konkrete Textänderungen
  ohne Bedeutungsverlust und vollständige Sprachkataloge.

  **Stand 23.09.2026 (Paket „texte", `reports/texte.md`):** Preise, Generatoraussage, README-Version,
  Sicherheitstexte, Agentenquote, Slicer-Begriff es/fr/pt, Du/Lei-Bestand it, portugiesische
  Anführungszeichen und die in `sollliste*.md` benannten Einzelstellen (B13/B12, B11c, B32, B23, B26,
  B27, B34, B16, B3, C2/C9/C10/C12, A16 und Nachbarn) geprüft und korrigiert, alle fünf Kataloge
  nachgezogen. Keine erschöpfende Zeile-für-Zeile-Prüfung jedes Anwendungstexts — offen bleibt der
  Rest der Oberflächentexte außerhalb der benannten Fundstellen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#rückmeldung-und-freiwillige-unterstützung-gehören-in-die-app-startfläche-31082026).

<a id="rm-088"></a>

- [ ] **RM-088 — Verständlichkeit für Laien im Regelwerk verankern.** Die vorgeschlagene
  Verständlichkeitsregel für Kundentexte entscheiden und ihren Geltungsbereich festlegen. Abnahme:
  freigegebene Formulierung, begründete Ausnahmen für Slicer-Begriffe und gegebenenfalls eine
  kuratierte, sprachübergreifende Prüfung.

  **Stand 23.09.2026:** Die Slicer-Begriffsausnahme ist in der Praxis bereits gesetzt — „slicer" ist
  jetzt in allen sechs Sprachen einheitlich der Fachbegriff (Paket „texte", RM-084). Was fehlt, ist
  Roberts Freigabe der Verständlichkeitsregel selbst und ihres Geltungsbereichs darüber hinaus — das
  ist eine Regelentscheidung und wird hier nicht unterstellt.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-090"></a>

- [ ] **RM-090 — Serie zum Übergabestatus entscheiden.** Entscheiden, welche der fünf Erlebnisse des
  Produktkompasses als nächster Produktumfang gelten: Druckziel, Übergabestatus, Befundkarte,
  Änderungsvorschau und Übergabebeleg. Abnahme: abgegrenzter Auftrag mit Kundennutzen und Kriterien;
  vorhandene Druckerprofile, Vorschau und Slicer-Übergabe als Ausgangspunkt berücksichtigen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-131"></a>

- [ ] **RM-131 — Zurückgestellten Mehrfachimport entscheiden.** Mehrfachimport bewusst
  zurückgestellt lassen. Bei Wiederaufnahme: mehrere Dateien in einem Vorgang übernehmen, die
  gemeinsame Baugruppenlage erhalten und gleichartige Importbefunde bündeln. Abnahme:
  Piratenschiff-Ordner ohne siebzehn Dialoge, ohne still verworfene Dateien und mit
  nachvollziehbarer Platzierung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#neunzehn-kundendateien-durch-die-oberfläche-gefahren-04092026).

<a id="rm-135"></a>

- [~] **RM-135 — Zugewiesene Höhe der Filamentkarte vollständig nutzen.** Qt berechnet Hinweis,
  sichtbare Knöpfe und Abstände bei der tatsächlichen Breite; leere Listen erzwingen keine
  überzähligen Mindestzeilen. Acht Regressionen und die native Windows-Abnahme mit knappen/freien
  Höhen, langen Hinweisen, großer Schrift und voller Liste sind grün. Nachbarkarten behalten ihren
  Raum; der Mac-xfail ist entfernt. Offen bleibt der plattformübergreifende Prüflauf auf macOS.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#ein-ort-für-die-auswahl-07092026).

<a id="rm-136"></a>

- [ ] **RM-136 — Gezeichnetes Fensterschema und Bildbeschreibungen aktualisieren.** Das gezeichnete
  Fensterschema an Projektkopfzeile, Operationsbereich und aktuelle Auswahlspalte anpassen; Bild,
  Bildunterschrift und Alternativtext müssen dasselbe erklären. Abnahme: alle sechs Sprachen, danach
  beim nächsten betroffenen Release nur erforderliche Abbildungen/Handbücher/PDFs neu erzeugen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-durchsicht-des-07092026).

<a id="rm-174"></a>

- [ ] **RM-174 — Der Geist beim Zug an einem Bausteinmerkmal zeigt nur dieses Merkmal.** Seit dem
  14.09.2026 versetzt der Griff an einem Merkmal, das aus einem Baustein kam, den ganzen Baustein
  (`MainWindow._move_the_part`): Die Tasche eines Schlüssellochs nimmt Schlitz und zehn
  Verrundungen mit, der Schritt behält seine Kennung. Während des Zugs zeigt die Ansicht aber
  weiter, was sie für jedes Merkmal zeigt — die Marke des angefassten Merkmals wandert, der
  blasse Geist steht an seiner Ausgangsstelle (`Viewport._show_ghost`, `_feature_shape`), und
  die übrigen elf Merkmale rücken erst beim Loslassen nach. Für eine Bohrung ist das die ganze
  Wahrheit, für einen Baustein die Hälfte. Abnahme: Während des Zugs wandert der Umriss des
  ganzen Bausteins (die Dreiecke seiner Merkmale, oder der Werkzeugkörper aus
  `placement_tools` an der neuen Stelle), und ein Zug neben die Fläche zeigt schon vor dem
  Loslassen, dass er dort nicht landet.

  [Befund](ROADMAP-ARCHIV.md#bausteine-vorschau-griff-und-werte--die-sonde-über-alle-27-14092026).

<a id="rm-175"></a>

- [ ] **RM-175 — Bauplan §30.1 um Winkel, gleich, Mittelpunkt, Vieleck und Langloch nachtragen.**
  Seit dem 14.09.2026 kennt der Löser fünfzehn Bedingungsarten statt zwölf (`angle` in
  Grad, `equal` für Länge oder Radius, `midpoint`), „konzentrisch" ist bewusst keine Art,
  und der Editor zeichnet Vieleck und Langloch aus zwei Klicks — frei gezeichnet, bemaßt
  getippt. §30.1 nennt noch die zwölf Arten; der Bauplan wird nur mit Ansage geändert.
  Abnahme: sechs Sätze nachtragen (Liste der Arten, Wertebereich des Winkelmaßes 0 bis 180
  Grad und Speicherung in Grad, „konzentrisch" als Oberflächenname, die zwei Werkzeuge,
  die Regel „gezeichnet heißt frei, getippt heißt bemaßt" samt Ausnahme für Felder der
  Leiste, und nach §16.2 der Satz, dass eine neue Bedingungsart `format_version` nicht
  erhöht). Der Wortlaut steht im Paketbericht W2 der Sitzung vom 14.09.2026.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#sechs-pakete-aus-der-einschätzung-zur-einfachen-bedienung-14092026).

<a id="rm-213"></a>

- [ ] **RM-213 — Fensterabnahme 0.5.0 und die Kundenwege am echten Fenster.**
  Die Paketnachweise der Durchsicht 0.5.0 stammen überwiegend aus
  Offscreen-Läufen oder Fenstern mit `WA_DontShowOnScreen`. Die späteren
  Website-Aufnahmen und Skizzenlabel-Sonden zeigen echte maximierte Fenster;
  sie belegen ihre Motive und die jeweiligen Reparaturen. Die vollständige
  Welle 2 „kundenwege" mit allen folgenden Abnahmekriterien ist damit noch
  nicht gefahren. Was nur das echte Fenster zeigt (Schrift, Vulkan-Fläche, Fokus,
  Bildschirmleser, gefühlte Wartezeit): die Punkte RM-174, RM-197 bis RM-200,
  RM-204 und RM-205 (sie bleiben je eigene Punkte und schließen in diesem Lauf);
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

<a id="rm-215"></a>

- [ ] **RM-215 — 276 Befundstellen enden ohne Handlung.**
  Aus der Sollliste der Durchsicht 0.5.0 (C1): 276 Befundstellen im Kern tragen
  weder `suggestions` noch einen Eintrag in `panels.FINDING_ACTIONS`, darunter
  97 Warnungen und sieben Fehler. Stichprobe am Code (`main`): `fit.violated`
  (`scene/fits.py:382`), `gcode.spool_left_out` (`export/handover.py:2720`),
  `join.blocked` (`geom/prepare.py:2819`) und `orient.support_likely`
  (`geom/orient.py:685`) bauen ihren `Finding` ohne `suggestions`, und keiner
  steht in `FINDING_ACTIONS`. Regel 17 verlangt mindestens einen
  Handlungsvorschlag je Ausnahme; für Befunde gilt dieselbe Haltung (§2.7). Der
  geplante Querschnitt „befunde" (Welle 2/3) ist nicht begonnen worden. Weg: ein
  Test, der für jede Warnung und jeden Fehler einen Weg verlangt (Ausnahmeliste
  mit Begründung für reine Auskünfte), dann die Stellen gebietsweise nachziehen
  — Fehler zuerst. Abnahme: der Test grün, jede Ausnahme begründet.

<a id="rm-232"></a>

- [ ] **RM-232 — Die Klickkette an einem Merkmal rechnet noch im Hauptfaden.**
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

<a id="rm-233"></a>

- [ ] **RM-233 — Fünf Kleinigkeiten aus den Durchsichten, am Code bestätigt.**
  Jede für sich klein, alle am Stand `5a57e261` nachgelesen: `Session.autosave`
  hängt ungeschützt am Zeitgeber (`main_window.py:2274`, `write_autosave` ohne
  `try`) — ein voller Datenträger wirft in einem Slot, und das erreicht keinen
  Kunden (szene); das Kontextmenü des Skizzeneditors
  (`sketch_editor._context_menu`) baut je Rechtsklick ein `QMenu(self)` und gibt
  es nie frei (fenster); *Drehdeckel* und *Prüfstück* vergeben Objektnamen in
  der Sprache des Augenblicks (`lid.py:1470`, `prepare_ops.py:12557`,
  `unused_name(_(…))`) — derselbe Schritt heißt nach einem Sprachwechsel anders
  (szene); *Drehen*, *Skalieren* und *Spiegeln* nennen ihren Anker
  „Schwerpunkt", gerechnet wird mit der Hüllquadermitte
  (`geom/ops.py:339/447/596`, `transform.anchor_point`, `pivot_for_transform`,
  `_on_scale_dragged`; Text in allen Katalogen auf „Mitte des Objekts") (szene);
  und die Rückfragekarte hat feste 520 Punkte und steht in einem sehr schmalen
  Fenster oben mittig unter Karten (foerderung, bestehend). Weg: je Stelle der
  kleinste Fix mit Test. Abnahme: fünf Tests, der Sprachwechseltest benennt den
  Namen einmal.

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

<a id="rm-016"></a>

- [ ] **RM-016 — Agenten-Suite gegen das aktuelle Vorgabemodell messen.** Die Agenten-Suite gegen
  das tatsächlich konfigurierte Vorgabemodell auf einer festgehaltenen Regelversion messen und mit
  einem vergleichbaren Referenzlauf bewerten. Abnahme: Fallresultate, Modellkennung, Regelversion
  und Quote sind belegt; mehrschrittige Werkzeugaufrufe berücksichtigen den Umgang mit
  Thinking-Blöcken. Die Behandlung von Modellablehnungen ist bereits gebaut.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-konzepte-nachrecherchiert-19082026).

<a id="rm-081"></a>

- [ ] **RM-081 — Ollama-Laufzeit und verbleibende Optimierungen abnehmen.** Die lokale Modellserie
  auf die noch offenen Messungen begrenzen: Warm-/Kaltstart und Antwortqualität mit aktuellem
  Werkzeugschema erfassen, weitere Schemakürzungen gegen dieselben Referenzanfragen prüfen und die
  gestufte Werkzeugauswahl als Bedienentscheidung vorbereiten. Abnahme: Quote und Latenz aus
  demselben ruhigen Lauf samt GPU-Zustand; keine Qualitätsverschlechterung durch Kürzungen.

  **Stand 15.09.2026, aus RM-173:** Die Quote ist zweimal gemessen (20/39 → 24/39 mit der
  Kürzung), und die Kürzung hat nicht geschadet — aber unter Fremdlast, mit Modellstarts
  zwischen 56 und 314 s, also ohne brauchbare Latenz. Ruhig gemessen (14.09., RM-054/RM-173):
  22,9 s kalt und 2,3 s warm für den vollen Prompt, 18,7 s kalt für den gekürzten. Was
  bleibt: ein ruhiger Lauf für Latenz und GPU-Zustand, das Ergebnis des Laufs ohne Denkblock
  (484 und 847 Token Ausgabe je Schritt sind zum größten Teil Denkblock, bei 33 Token/s eine
  halbe Minute), und die gestufte Werkzeugauswahl — die bleibt, was `AGENTS.md` sagt: eine
  Auswahl, die Operationen aussortiert, wäre eine Betriebsart mit anderem Namen, und ob es
  eine geben soll, entscheidet Robert.

  **Warum der Modellstart Minuten kostet — beobachtet am 15.09.2026, 00:53 bis 01:00, alle
  vier Sekunden `nvidia-smi` und der Arbeitssatz von `llama-server`:** Nach dem Entladen
  belegt der Desktop 1,6 GB der 16 GB (dwm 945 MB, Claude 200, Explorer 185, Chrome). Die
  Gewichte (8,6 GB) sind in acht Sekunden auf der Karte; dann kriecht die Belegung von 10,4 auf
  15,7 GB mit etwa 60 MB/s — zweieinhalb Minuten, ein Kern beschäftigt, Platte und Grafikkarte
  im Leerlauf. Das ist der KV-Cache (5 120 MiB bei 32 768 Token in f16) und die Rechenpuffer,
  angelegt am Rand des Speichers: `ollama ps` meldet 14,4 GB für das Modell, frei waren 14,7.
  **Die Kante ist es aber nicht** — das sagte um 03:07 dieselbe Messung mit leerem Desktop
  (1,4 GB belegt): 188 s Kaltstart, und `llama3.1:8b` mit 7 GB Luft brauchte für 4 GB KV-Cache
  23 s gegen 4,4 s bei 4 096 Token; `qwen3:14b` mit 4 096 Token 26 s, mit 32 768 Token 188 s.
  Die Zeit hängt an der **Größe des KV-Caches**, nicht am freien Speicher, und sie hat einen
  Anfang: Bis 17:55 lud dasselbe Modell mit demselben Fenster in **3 bis 4,5 s** (elf Starts
  im Serverlog), um 17:58 waren es 83 s, seither nie unter 40 — die Zeit, zu der die
  Torläufe der anderen Sitzungen mit ihren Fenster- und Renderer-Tests begannen. Der
  Grafiktreiber lagert seither bei jeder großen Zuweisung um, und zwar Stunden nach dem
  letzten Test noch. Was das zurücksetzt, ist nicht gemessen — ein Neustart ist die Probe,
  und die gehört Robert. Bis dahin gilt: Latenz nur nach frischem Start und **vor** einem
  Torlauf messen; die 22,9 s vom Nachmittag sind der Bezugswert, und jede Sitzung mit
  `keep_alive: 0` zahlt den Start je Zug neu.

  Zwei Hebel, beide eine Entscheidung: **Warmhalten zwischen den Zügen** (siehe RM-173) — und
  der **KV-Cache in `q8_0`**: Ollama nimmt das nur als Umgebungsvariable des Dienstes
  (`OLLAMA_KV_CACHE_TYPE=q8_0` mit `OLLAMA_FLASH_ATTENTION=1`), halbiert damit die 5 GB, und
  mit 3,2 GB bei 40 960 Token passte sogar das volle Trainingsfenster von qwen3 auf die Karte
  (8,6 + 3,2 + Puffer ≈ 12,5 GB) — ein Viertel mehr Platz für RM-173. Solidon kann die
  Variable nicht setzen, aber messen, ob sie gesetzt ist: Die vorhandene Probe
  (`model_state`, Karte gegen Prozessor) sagt nach einem Ladeversuch mit 40 960, ob das Modell
  ganz im VRAM liegt. Ein Fenster, das sich nach dieser Probe richtet, statt fest 32 768 zu
  nehmen, ist der Vorschlag; gebaut wird er auf Roberts Wort.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#ollama-bis-zum-anschlag-31082026).

<a id="rm-173"></a>

- [ ] **RM-173 — Der Platz im Kontextfenster des lokalen Modells geht aus.** Gemessen am
  14.09.2026 beim Abschluss von RM-054: Auftrag und die 121 kompakten Werkzeugschemata kosten
  **31 465 Token**, das Fenster hat 32 768 (`OLLAMA_CONTEXT_TOKENS`) — 96,0 %. Für Steckbrief,
  Prüfbericht, Verlauf und die Frage selbst bleiben 1 303 Token, und Ollama schneidet einen
  Prompt über dem Fenster **vorn** ab: Das Erste, was fehlte, wäre der Auftrag — und niemand
  sähe es (Regel 21 in ihrer stillsten Form; am 03.09. fiel die Bausteinquote aus genau diesem
  Grund von 3/3 auf 0/3, siehe `test_backends`). Seit dem 08.09. sind es 3 184 Token mehr bei
  zwei Werkzeugen mehr; jede weitere Operation kostet in dieser Größenordnung.

  **Das Fenster lässt sich auf der Karte nicht heben:** Mit `num_ctx` 40 960 meldet `ollama ps`
  für qwen3:14b 16 GB und `10 %/90 % CPU/GPU` — das Modell läuft von der RTX 4080 über, und der
  Prozessorweg ist 72-mal langsamer (Messreihe vom 31.08.). Eine Auswahl, die Operationen
  aussortiert, wäre eine Betriebsart mit anderem Namen und ist ausgeschlossen (`AGENTS.md`).
  Bleibt: **weniger Text je Werkzeug.** Kandidaten, jeder zu messen: die `doc`-Sätze der
  Parameter im kompakten Schema noch einmal kürzen oder in den Systemprompt heben, wo sie
  einmal statt je Werkzeug stehen (das Muster von `objects` und den sechs Platzierungsangaben,
  das am 31.08. 4 520 Token brachte); Enumerationen und Vorgabewerte nur dort ausschreiben, wo
  das Modell sie ohne Beispiel verfehlt; die `caveat`-Zeile nur bei Operationen, deren Grenze
  im Register steht.

  **Und ein Wächter, der den Überlauf sagt statt schweigt:** Vor dem Absenden die Nutzlast
  gegen `OLLAMA_CONTEXT_TOKENS` rechnen (die Zählung liefert `prompt_eval_count` des ersten
  Zugs; eine Näherung aus der Zeichenzahl reicht als Vorwarnung) und im Chat melden, wenn
  Steckbrief oder Verlauf gekürzt werden mussten — nicht still einen halben Auftrag schicken.

  Abnahme: `tools/measure_local_model.py` unter 85 % des Fensters mit vollem Werkzeugbestand,
  die Agenten-Suite vorher und nachher ohne Quotenverlust (§39), und ein Test, der einen zu
  langen Prompt als Befund im Chat zeigt.

  **Stand vom Abend des 14.09.2026.** Der Wächter steht (`e4856ff6`): Ollama kürzt einen Prompt
  über dem Fenster still auf etwa die Hälfte (4 098 Token gegen 2 048 kamen als 1 026 zurück),
  und `OllamaBackend` wirft seither `BackendPromptTruncated`, wenn eine Antwort mit vollem
  Werkzeugsatz weniger als sechzig Prozent der gemessenen Werkzeuglast meldet. Beim ersten Lauf
  fand er `tools/check_local_model.py`, das über Wochen das volle Schema geschickt und ein
  halbiertes gemessen hatte. **Was Ollama sieht, ist gemessen:** `pattern`, `minimum`,
  `maximum` und `default` verwirft es vor dem Rendern — der Bindungs-Regex an 618 Feldern kam
  nie an, das Modell wusste nie, dass ein Feld `@name` nimmt; das sagt jetzt der kompakte
  Systemprompt. Ein echter Zug mit **einer** Platte kostet 32 132 Token (98,1 %).

  Die Anteile: Parameterbeschreibungen 11,7k, Gerüst aus Namen und Typen 12,4k,
  Werkzeugbeschreibungen 4,7k, Systemprompt 1,4k, Enums 1,2k. Gemessene Kürzungen ohne
  Fähigkeitsverlust: Konventionstexte einmal im Prompt statt je Feld („— siehe Position X",
  `name`, `play`, `angle`; die eigenen Sätze von `x` und `nx` bleiben) und Zahlenfelder als
  `number` statt `["number", "string"]` — zusammen **28 440 Token** (86,8 %, Kaltstart 18,7 s
  statt 22,9). Im Fünf-Fälle-Check kippt das „Nimm die letzte Änderung zurück" von
  `undo_transaction` zu `ask_user`, deterministisch, und zwar bei jeder der beiden Kürzungen
  allein — eine Kippstelle des Modells, keine verlorene Information. Deshalb läuft die
  Agenten-Suite (39 Fälle) am Abend zweimal im Worktree: Basis `e4856ff6` und dieselbe mit
  Kürzung; der Commit folgt dem Ergebnis. Weitere gemessene Wege, beide eine Entscheidung:
  Rückseitenparameter (`placement="advanced"`, 550 von 884) ohne Text 25 797 Token; ganz weg
  20 311 — **ausgeschlossen**, weil bei *Bohrung* `x`, `y`, `z` hinten liegen und das Modell
  dann kein Loch mehr setzen könnte.

  **Die zweite Gestalt der Kürzung, aus dem Protokoll des Suitelaufs (14.09.2026, 19:30):**
  Der erste Schritt eines Zugs endete bei 32 680 von 32 768 Token; der zweite begann mit
  32 300, erzeugte 847 — und llama.cpp schrieb `stop processing: n_tokens = 16765, truncated =
  1`: Kontext geschoben, die Mitte des Auftrags verworfen, die Antwort auf dem Rest gerechnet.
  Die Antwort trägt kein Zeichen davon; `prompt_eval_count` zählt den ganzen Prompt, und der
  erste Wächter sieht nichts. Mit dem heutigen Prompt bleiben nach dem ersten Schritt rund
  600 Token — jede denkende Antwort ist länger. **Der zweite Wächter** rechnet deshalb Eingabe
  plus Ausgabe gegen das Fenster (`BackendContextShifted`, mit Test); die Kürzung auf 28 440
  ist damit keine Kür mehr, sondern das, was den zweiten Schritt wieder in das Fenster bringt.
  Dazu gehört die Frage, ob qwen3 im Chat denken soll: 484 und 847 Token Ausgabe je Schritt
  sind zum größten Teil Denkblock, bei 33 Token/s eine halbe Minute je Schritt — `think:
  false` ist eine Anfrageoption, und ob die Quote es überlebt, sagt die Suite (nach den zwei
  laufenden Läufen).

  Und was das Protokoll außerdem sagt: `llama-server started in 146.25 seconds` — der
  Modellstart, nicht der Prompt, kostet nach jedem entladenen Zug die Minuten, sobald der
  Rechner unter Last steht (die Suite lief neben den Torläufen dreier anderer Sitzungen);
  ruhig gemessen waren es 18,7 s für alles. Das Warmhalten zwischen den Zügen — 16 s je Zug
  gespart, entladen erst vor einem Weg-3-Lauf — bleibt eine Entscheidung für Robert, weil
  der Vertrag aus dem Absturz vom 01.09. lautet: nach dem Zug entladen.

  **Das Suiteergebnis (Nacht auf den 15.09.2026), beide Läufe im Worktree unter derselben
  Fremdlast:** Basis `e4856ff6` (31 465 Token) **20/39** gut beantwortet, gefragt 3/3,
  schemagültig im ersten Versuch 74/148 = 50 %, Baustein statt eigener Geometrie 1/13,
  Hauptmaße als Parameter 2/3, 3,1 Schritte im Mittel — 3 h 24 min. Mit der Kürzung
  (28 440 Token, endgültige Fassung: `play` und die vier Geschwisterachsen ohne Feldtext,
  Zahlenfelder als Zahl, Konventionen und Bindung einmal im Prompt) **24/39**, gefragt 2/3,
  schemagültig 117/162 = 72 %, Baustein 7/13, Hauptmaße 1/3, 3,3 Schritte — 2 h 43 min.
  Was kippte: *Mach das Teil dünner* fragte in der Basis nach dem Wert und riet mit der
  Kürzung (`fit_to_size`, `scale_object`, zweimal `hollow_object`) — dieselbe Kippstelle wie
  beim Zurücknehmen im Fünf-Fälle-Check; und *Wo finde ich das Aushöhlen* lief in der Basis in
  den ersten Wächter (Ollama kürzte 32 881 auf 16 386) und führte mit der Kürzung das Aushöhlen
  aus, statt den Ort zu nennen. Beides steht gegen vier Fälle mehr, 22 Punkte Schemagültigkeit
  und sechs Bausteine, die vorher eigene Geometrie waren. **Die Kürzung ist drin**, mit dem
  Wächtertest, der `CONVENTION_SENTENCES` am Register hält und jedes Feld ohne Text im Prompt
  wiederfindet. Ohne Bewertung bleibt die Zeit: Unter Fremdlast schwankte allein der
  Modellstart zwischen 56 und 314 s je Zug, beide Läufe hatten je zwei Zeitüberschreitungen.

  **Der dritte Lauf, dieselbe Kürzung ohne Denkblock** (`think: false` in jeder Anfrage,
  00:40 bis 03:10): **23/39** gut, gefragt 2/3, schemagültig 95/132 = 72 %, Baustein 5/13,
  Hauptmaße 3/3, 3,6 Schritte — keine Zeitüberschreitung, 37 statt 45 ungültige Aufrufe. Die
  Quote ist dieselbe wie mit Denkblock (ein Fall, im Rauschen); was sich ändert, ist die Zeit:
  Der zweite Schritt eines Zugs antwortet in 0,7 bis 1,5 s statt 7 bis 36 s, der erste erzeugt
  rund 100 statt 400 bis 850 Token — je Zug eine halbe Minute Modellzeit weniger, und der
  Kontextschub aus dem Denkblock entfällt. **Der Vorschlag:** `think: false` an jedes Modell
  schicken, dessen `/api/show` die Fähigkeit `thinking` nennt (Ollama lehnt die Option bei
  anderen ab). Das ist eine Verhaltensänderung des lokalen Chats, keine Kürzung — Robert
  entscheidet; gebaut ist es ein Nachmittag mit Test.

  **`PROMPT_TOKENS` ist gemessen:** 28 616 Token für die eingebaute Fassung (03:07, drei warme
  Züge 2,3 bis 7,1 s), 87,3 % des Fensters, 4 152 Token Rest. Der Kaltstart derselben Messung
  — 188 s — steht bei RM-081, denn er ist keine Eigenschaft des Prompts.

  **Offen sind Entscheidungen, keine Messungen:** Denkmodus (oben), Warmhalten zwischen den
  Zügen (RM-081), Flächenliste im Steckbrief (die 111 Merkmale von *Drucker kalibrieren* sind
  36 Flächenzeilen je Körper; die zwölf größten plus Zähler wären die Hälfte des Steckbriefs)
  und der KV-Cache in `q8_0` am Dienst, der das Fenster auf 40 960 heben könnte (RM-081).

<a id="rm-185"></a>

- [ ] **RM-185 — Das kompakte Werkzeugschema passt nicht mehr ins Fenster des
  lokalen Modells.** Am 16.09.2026 mit 142 Werkzeugen gemessen: **36 546 Token**
  gegen `num_ctx` 32 768 (111,5 %). Die erste Messung mit dem Fenster selbst
  meldete 16 386 — die Hälfte plus zwei, also Ollamas stille Kürzung, keine
  Ersparnis; ungekürzt gezählt mit 65 536. Mit 40 960 liegt qwen3:14b noch zu
  89 % im VRAM (warm 4,3 bis 4,5 s statt 2,4), aber Steckbrief, Prüfbericht und
  Verlauf kommen obendrauf, und auch dieses Fenster wäre voll. Die 21 Werkzeuge
  seit dem 15.09.2026 (Organizer, Felder, Lochbilder, Profilklemme, Dichtnut)
  haben das Schema über das Fenster geschoben. **Wirkung beim Kunden:** Wer mit
  dem Vorgabemodell chattet, bekommt bei jedem Zug die Kürzungsmeldung mit
  ihren Handlungen (`BackendPromptTruncated`); der gehostete Weg ist nicht
  betroffen. `PROMPT_TOKENS` und `PROMPT_TOOL_COUNT` tragen die Messung,
  `test_the_local_backend_opens_a_window_big_enough_for_the_tools` steht als
  striktes xfail. Der Platz muss aus dem Schema kommen (Fortsetzung von
  RM-173): kürzere Beschreibungen, Parameter ohne Wiederholung, oder eine
  Entscheidung Roberts über eine gestufte Werkzeugauswahl (RM-081). Abnahme:
  eine ungekürzte Messung unter 32 768 mit Platz für 4 000 Token Kontext, und
  das xfail fällt.

  **Gemessen am 16.09.2026, abends, mit 143 Werkzeugen (36 731 Token):**
  Bei `num_ctx` 32 768 mit passendem Prompt (100 Werkzeuge, 29 042 Token)
  antwortet qwen3:14b mit 41 Token/s, ein warmer Zug dauert 6,3 s. Bei
  40 960 mit allen 143 liegen 11 % des Modells auf dem Prozessor: 11 Token/s,
  18 s je Zug — **3,8-mal langsamer**. Das Fenster zu heben ist also ein
  Preis, keine Lösung. Die risikofreien Kürzungen im kompakten Schema
  (Werkzeugbeschreibung auf den ersten Satz, ohne „Wann nicht") bringen rund
  3 500 Token — nicht genug. Der Hebel ist die Zahl der Parameter: 1 293,
  davon rund 550 Ortsfelder (x, y, z, nx, ny, nz, axis, angle) an 60
  Werkzeugen. Sie zu einem Ortsfeld zu bündeln oder eine gestufte
  Werkzeugauswahl (RM-081) sind Änderungen an der Werkzeugschnittstelle und
  brauchen die Agenten-Suite vorher und nachher — eine Entscheidung Roberts.

  **Entschieden am 16.09.2026, abends:** Das Fenster steht auf 40 960
  (Robert: „18 s sind in Ordnung, bis 30 alles ok"). Die Kürzungsmeldung ist
  damit beim Vorgabemodell weg, das xfail ist gefallen, und die Prüfung des
  Schiebefalls rechnet relativ zum Fenster. Was bleibt, ist der Preis: 11 %
  des Modells auf dem Prozessor, 18 s je warmer Zug statt 6,3. Abnahme jetzt:
  eine ungekürzte Messung des Schemas unter 28 000 Token — dann kommt 32 768
  zurück, und der Vorgabeweg ist wieder so schnell wie am 14.09.2026.

  **Gemessen am 23.09.2026** (dienste B1): Werkzeugschema 37 836 → 27 293 Token,
  Fenster wieder 32 768, Modell 100 % auf der Karte, Kaltstart 19,8 s, warmer
  Zug 2,5 s; Suite 21/39 gehalten, gefragt 3/3. Die Abnahme „unter 28 000“ war
  damit erfüllt — bis die Operationen der Pakete P4.0, P6 und P7 dazukamen. Die
  Kosten je Werkzeug liegen bei 120 bis 750 Token (p7verlauf, zeichnenbau).
  **Entscheidung 23.09.2026** (Robert): Die Neumessung mit qwen3:14b findet
  nicht vor 0.5.0 statt, sondern auf dem Weg zu 0.5.1. Bis dahin führt ein
  eigener Test den Vergleich von `PROMPT_TOOL_COUNT` mit der Werkzeugzahl mit
  nicht strenger xfail-Marke (Grund: RM-185, 0.5.1). Die Zahlen der KI-Seite
  (`ki-modelle.html`, Absatz „Lokaler Chat“) ziehen mit der Neumessung nach.

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


<a id="rm-020"></a>

- [ ] **RM-020 — Sicherung der eigenständigen Druckprojekte belegen.** Den Sicherungsweg für das
  eigenständige Repository 3D Drucker festlegen und belegen. Es hat weiterhin kein Git-Remote; ob
  eine andere Sicherung existiert, ist hier nicht nachgewiesen. Abnahme: Robert entscheidet über
  Remote oder anderen Sicherungsweg, und eine Wiederherstellungsprobe bestätigt den gesicherten
  Stand. Einen externen Upload erst aus dieser Entscheidung ableiten.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#vier-wege-von-hand-während-die-suite-grün-war-23082026).

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

<a id="rm-113"></a>

- [ ] **RM-113 — Besitzerprüfung der Tokendatei auf dem Windows-Runner belegen.** Den Besitzer einer
  frisch angelegten privaten Tokendatei auf dem Windows-Runner ermitteln und die Prüfung mit einer
  tatsächlich nutzereigenen Datei fahren. Abnahme: SID und ACL dokumentiert, Test ohne bedingten
  Skip grün; eine breitere Besitzfreigabe nur nach Sicherheitsprüfung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-134"></a>

- [ ] **RM-134 — Zusammenführung duplizierter Testhilfen entscheiden.** Roberts Entscheidung zum
  Umfang der Zusammenführung einholen. Belegt sind doppelte Freiformhilfen für Kegel/Torus und
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

<a id="rm-137"></a>

- [ ] **RM-137 — Sitzungsende im tatsächlichen Editorbetrieb abnehmen.** Das tatsächliche SessionEnd
  beim Ende einer echten Editor-Sitzung beobachten und die Freigabe des Sitzungsgebiets belegen.
  Abnahme: sichtbarer echter Sitzungsablauf samt wirksamem Benutzer-PATH nach Neustart; eine
  konfigurierte Terminal-Statuszeile nicht als Desktop-Darstellungsnachweis behandeln.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#zwei-werkzeuge-zwei-wahrheiten-08092026).

<a id="rm-214"></a>

- [ ] **RM-214 — Die Bereichsprüfung ohne VTK hat keinen Index und keinen Wächter.**
  Folgen des VTK-Ausbaus (`5a57e261`, Bericht vtk): Die neue Wandmessung
  (`range_check.local_wall_thickness` über `mesh.ray_hits_batch`) prüft Strahlen
  gegen alle Dreiecke — O(n²) statt O(n log n). Die Stichprobe im Bericht vtk
  maß nur die erste Bereichsecke je Baustein; ihre höchstens 4 316 Dreiecke
  sind keine Grenze für alle Ecken. Auch die dort behauptete Sekundengrenze
  gilt nicht allgemein. Der vollständige Hauptbaum-Lauf am 23.09.2026 bestand
  für alle 35 Bausteine (Exit 0); `seal_gasket` brauchte für seinen gesamten
  Bereich mit 16 Ecken 719,5 s. Das ist keine Einzelmessung der Wandprüfung
  und kein Nachweis einer allgemeinen Laufzeitregression der Anwendung.
  Fortschritt, ältere VTK-Läufe und die Messgrenzen stehen in
  `F:\3D Druck\Releases\0.5.0\Nachweise\review-050\reports\codex-bausteinlauf.md`. Größere eigene
  `.py`-Bausteine bleiben wegen der quadratischen Wandmessung ebenfalls
  betroffen. Ein Test, der VTK-Importe unter `app/` und
  `tools/` verbietet, fehlt (der Nachweis war ein `grep`); `vtk` liegt weiter in
  der `.venv`, und nur `check_env` könnte es melden. Weg: ein räumlicher Index
  (Sweep-and-Prune wie in `geom/intersections.py`, oder `cKDTree` mit wachsendem
  Radius); ein Wächter nach dem Muster von `test_core_isolation.py` über
  `sys.modules` nach einem vollen Start; `check_env` meldet nicht mehr geführte
  Pakete. Abnahme: ein eigener Baustein mit 50 000 Dreiecken prüft seine Wand
  unter 5 s, der Wächter ist gegen einen eingefügten Import rot.

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
  `F:\3D Druck\Releases\0.5.0\Nachweise\review-050\reports\codex-ci-35952849083-unix-packages.md`.

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

<a id="rm-149"></a>

RM-149 ist mit der Auslieferung von 0.5.0 abgeschlossen.
[Nachweis und bisheriger Verlauf](ROADMAP-ARCHIV.md#rm-149-abschluss-050).

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

<a id="rm-182"></a>

RM-182 ist mit der Auslieferung von 0.5.0 abgeschlossen.
[Nachweis und bisheriger Verlauf](ROADMAP-ARCHIV.md#rm-182-abschluss-050).

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

<a id="rm-095"></a>

- [ ] **RM-095 — Automatischen Löschlauf auf dem Server belegen.** Den geplanten Server-Löschlauf
  einschließlich Ratelimits und Backups belegen: tatsächliche Pfade und Zeitplan prüfen, Lauf und
  Ausfallalarm dokumentieren. Abnahme: ausgefüllte Freigabepunkte in PRIVACY-COMPLIANCE.md; die
  Codefrist allein ist kein Betriebsnachweis.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-096"></a>

RM-096 ist nach gebautem Rotationsweg und erfolgreichem Serverupload abgeschlossen.
[Abschluss und Servernachweis](ROADMAP-ARCHIV.md#rm-096).

<a id="rm-115"></a>

RM-115 ist mit der Auslieferung von 0.5.0 abgeschlossen.
[Nachweis und bisheriger Verlauf](ROADMAP-ARCHIV.md#rm-115-abschluss-050).

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

<a id="rm-162"></a>

RM-162 ist mit der Auslieferung von 0.5.0 abgeschlossen.
[Nachweis und bisheriger Verlauf](ROADMAP-ARCHIV.md#rm-162-abschluss-050).

## Kundenrückmeldungen

<a id="rm-038"></a>

- [ ] **RM-038 — Mailrückfall ohne prozentkodierten Berichtstext prüfen.** `SupportDialog` übergibt
  Betreff und Nachricht inzwischen direkt als Klartext an `ComposeEmail`; die alte Forderung nach
  gekürztem mailto-Text ist überholt. Abnahme im ausgelieferten Paket: Umlaute, Satzzeichen und
  Zeilenumbrüche kommen unverändert im Mailentwurf an; fehlendes Portal liefert eine Rückmeldung und
  den gespeicherten Ordner als Rückweg.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-erste-linux-kunde-und-was-sein-protokoll-trug-06092026).

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

<a id="rm-064"></a>

- [ ] **RM-064 — Slicerübergabe zwischen zwei echten Flatpaks abnehmen.** Erkennung, Hostpfade und
  Austauschordner sind repariert. Abnahme auf Linux: Modell aus dem ausgelieferten Solidon-Flatpak
  an ein installiertes Slicer-Flatpak übergeben, dort öffnen und den erreichbaren Austauschpfad
  dokumentieren.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-erste-kundenbericht-aus-dem-feld-27082026).

<a id="rm-072"></a>

- [ ] **RM-072 — Zusagen an den Dental-Kunden zum Verkaufsstart erfüllen.** Den Dental-Kunden
  spätestens zum Verkaufsstart über den Kaufweg und nach belastbarer 3D-Maus-Verfügbarkeit über die
  Unterstützung informieren. Abnahme: beide Anlässe mit tatsächlichem Versandstatus dokumentiert;
  bereits versandte Nachrichten bei der Bearbeitung zuerst prüfen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#eine-kundenanfrage-aus-dem-dentalbereich-30082026).

<a id="rm-231"></a>

- [ ] **RM-231 — Der Fehlerbericht aus dem Fenster geht ohne Schwärzung hinaus.**
  Gemeldet aus der Durchsicht 0.5.0 (dienste, für das Paket fenster):
  `main_window.report_error` nimmt `traceback.format_exception` ungekürzt und
  ohne die Schwärzung von `log.exception_text` — Quellzeilen und Pfade gehen in
  den Bericht (Stichprobe: `main_window.py:19698`). Der Nutzer sieht den Text
  vor dem Senden (§37.2), die Länge fängt seit `736d4a46` die Kürzung ab; ein
  Pfad mit dem Benutzernamen steht trotzdem darin. Weg: denselben Weg wie der
  Absturzschutz (`log.exception_text`), Test mit einem Pfad unter dem
  Nutzerordner. Abnahme: kein Benutzerpfad im gesendeten Text, die Fehlerstelle
  bleibt lesbar.
