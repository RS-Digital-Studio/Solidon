# ROADMAP — Arbeitsliste

Der ursprüngliche Bauplan-Abgleich vom 08.09.2026 und seine Fortschreibungen stehen im
[Archiv](ROADMAP-ARCHIV.md). Der Veröffentlichungsstand ist **0.5.3**, veröffentlicht
am **06.10.2026** (`website/version.json`, `d5a485a7a`). Der Tag `v0.5.3` zeigt auf
`34e1b3364`; der [Taglauf 37409338027](https://github.com/RS-Digital-Studio/Solidon/actions/runs/37409338027)
ist im zweiten Versuch abgeschlossen, rot nur im meldenden Versionswächter (RM-350); das
Windows-Setup kommt aus dem Installerlauf 37418052743 und ist lokal signiert. Die Website
bietet Windows-Setup, Linux-AppImage, Linux-Flatpak und die beiden Mac-Pakete an. Die offenen Aufgaben darunter führen ihre verbleibende
Arbeit oder Abnahme; ein veröffentlichter Build ersetzt keinen Feldnachweis.

Legende: `[ ]` offen · `[~]` teilweise umgesetzt, Abnahme oder Restarbeit offen ·
`[x]` mit dokumentiertem Nachweis abgeschlossen. Ein historischer Haken ist
kein Nachweis für ein grünes Tor auf dem heutigen Stand.

Die Phasen zeigen den erreichten Umfang; die Aufgaben darunter nennen den
heutigen Rest. Jede Aufgabe hat eine feste Kennung. Register und Punkt werden
gemeinsam gepflegt; abgeschlossene Aufgaben wandern mit ihrem Nachweis ins
Archiv. Fehlende Feldabnahmen bleiben offen, auch wenn der Code bereits steht.
Der [vollständige Bauplan-Abgleich](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026)
schließt RM-089 ab; von seinen acht Restverträgen ist nur RM-145 offen, RM-138 bis RM-144
stehen mit Nachweis im Archiv.

Priorität: Kundenabstürze und blockierte Hauptwege, danach falsche Ergebnisse
und Bedienfehler, danach Ausbau und interne Verbesserungen. Fristgebundene
Auflagen werden daneben rechtzeitig bearbeitet. **Als Nächstes:** die Kundenblocker nach
0.5.3 — das signierte Paket startet auf echten Intel-Macs nicht (RM-104; Ursache eingegrenzt,
Signierschritt korrigiert, kommt mit dem nächsten Tag), Cura unter Linux (RM-521, gebaut,
Abnahme beim Kunden mit dem nächsten Paket) — und die mit 0.5.3 fällige Antwort an den
Orca-Flatpak-Kunden (RM-522). Fristen: Verkaufskonzept bis 15.10. (RM-092),
Verkaufskandidat bis 25.10., Start am 01.11.2026 um 10:00 Uhr (RM-061). Daneben bleiben die
Mac-/Linux-Nachweise und die CRA-Betriebsvorbereitung offen — deren Frist ist am 11.09.2026
**abgelaufen**, die Meldepflicht aus Art. 14 gilt seither (RM-091). Eine zurückgestellte
Produktentscheidung oder ein kostenpflichtiger Lauf wird durch diesen
Abgleich nicht freigegeben.

## Was offen ist

Jede Zeile führt zu genau einem offenen Punkt. Die letzte Spalte nennt den nächsten Schritt; Begründung und Abnahme stehen am Punkt.

| Punkt | steht unter | wartet auf |
|---|---|---|
| [RM-184 — Dateiaudit vollständig umsetzen](#rm-184) | Geometrie, Erkennung und Druckvorbereitung | Bausteine, Abläufe, funktionale Gruppen, Projektmaße und das Abnahmewerkzeug gebaut (04.10.); offen: der echte Lauf der Einzeldateiabnahme über 187 Fälle am Fenster, die Fensterabnahmen der neuen Abläufe und Gruppen, Leistungsreihe |
| [RM-011 — Erstinstallation auf einem fremden Rechner abnehmen](#rm-011) | Plattformen, Pakete und Grafik | Fremdrechner ohne Entwicklungsumgebung von Download bis Export prüfen |
| [RM-021 — Native Fensterlebensdauer am aktuellen Renderer abnehmen](#rm-021) | Plattformen, Pakete und Grafik | Hänger durch die Speicherbereinigung im Arbeiter behoben (nur noch im Hauptfaden, 05.10.); der Riss in `test_ui.py` Teil 4 ist bis auf `processEvents` im Teardown eingegrenzt und trifft die Anwendung nicht; offen sind der Ereignistyp dahinter, die Gegenprobe auf Linux und Mac und die Vergleichsreihe |
| [RM-050 — Kopier- und Pufferkosten großer Szenen am Fenster messen](#rm-050) | Plattformen, Pakete und Grafik | VTK ausgebaut (`5a57e261`), matplotlib durch HarfBuzz ersetzt (`25d5536ee`); offen die kopierten Bytes und Pufferkosten je großer Szene am Fenster |
| [RM-051 — Renderer und Grafiklaufzeit in Linux- und Mac-Paketen abnehmen](#rm-051) | Plattformen, Pakete und Grafik | Grafik und Eingabe der 0.5.3-Pakete am echten Linux- und Mac-Bildschirm; der Release-Starttest belegt Fenster und 3D-Ansicht nur unter Xvfb und am ARM-Runner |
| [RM-055 — Neue Paketwerkzeuge im installierten Kundenpaket abnehmen](#rm-055) | Plattformen, Pakete und Grafik | Aktualisieren und Deinstallieren prüft der Installer-Workflow ab dem nächsten Release (`tools/check_windows_update.py`, am Runner von 0.5.2 auf 0.5.3 grün); offen: der Lauf im Release ohne Ausnahme für den behobenen Registerrest, Flatpak auf echter Linux-Grafik, Offline-Start |
| [RM-104 — Verbleibende Mac- und Unix-Befunde mit aktueller CI-Abdeckung abnehmen](#rm-104) | Plattformen, Pakete und Grafik | Intel-Macs mit macOS 26: Hardened Runtime ohne `allow-unsigned-executable-memory` lässt schon das `import ctypes` in PyInstallers Bootstrap in Apples libffi kreisen (Quelltext, fremde Berichte); Signierschritt korrigiert, wörtlich samt Rücklesung ad hoc am Runner gefahren (Lauf 37530339300), Developer-ID-Notarisierung im Handstart (Lauf 37530876754); offen der Start beim Kunden, Gegenprobe dafür `solidon-gegenprobe.sh`. Daneben Intel-Fenster am Gerät, `abort_active` der Fernsteuerung und die übrigen Unix-Fälle |
| [RM-107 — Ubuntu-Workerabbruch mit aktuellem Testbestand zuordnen](#rm-107) | Plattformen, Pakete und Grafik | Der Arbeiter stirbt nach dem Overlay-Ziehtest, die Overlay-Datei allein ist grün; nächster Schritt: die Testfolge des abgestürzten Arbeiters nachstellen und halbieren |
| [RM-187 — Dieselbe Geometrie auf jeder Plattform](#rm-187) | Plattformen, Pakete und Grafik | Paket A ist auf main: Bausteine, Muster, Skizzenbögen, Teilen und *Merkmal drehen* rechnen plattformgleich, der Wächter sieht durch den Merker der Erkennung; offen: Einpassungen in `perceive` (eigener Kern), Formen in `shapes.py` und Potenzen `**` im Kern (Liste am Punkt) |
| [RM-468 — CPython 3.14.8 bringt Sicherheitskorrekturen in die ausgelieferte Laufzeit](#rm-468) | Plattformen, Pakete und Grafik | Pakete 0.5.2 und 0.5.3 mit 3.14.8 gebaut, die Stückliste des Windows-Pakets 0.5.3 nennt CPython 3.14.8 und OpenSSL 3.5.9; offen die drei Arbeitsplätze |
| [RM-022 — Nachbau als Operationsfolge](#rm-022) | Geometrie, Erkennung und Druckvorbereitung | Profilkörper am Netz gebaut (05.10.), Besenhalter angenommen; offen der Korpuslauf über diesen Stand samt fünf Teilen über 600 s, die Fensterabnahme beim Release und die Wiederholung der berichtigten Zahlenanzeige am Fenster |
| [RM-188 — CAD-Ausbau, Bedienung und Resin für 0.5.x](#rm-188) | Geometrie, Erkennung und Druckvorbereitung | Nächster Schritt P0.8: die vier Konzepte je Anforderung dem Code oder einem Paket zuordnen; daneben P4.1 unter RM-022, P8.1, P9.1 und Zeichnen Z2. Reste der gebauten Pakete und Fragen an Robert stehen am Punkt; Abschluss mit P5.3 |
| [RM-191 — PrusaSlicer braucht für dieselbe Übergabe länger als die Orca-Familie](#rm-191) | Geometrie, Erkennung und Druckvorbereitung | Nachgemessen am Gewürzregal (`56f70000`): Material innerhalb von 3 %, Zeit Prusa 1,93× Orca — behoben bis 1,19× (volle Füllung und Lückenfüllung für Prusa und Orca, Bahnbreite je Orca-Rolle, `machine_limits_usage = ignore`); der Rest ist die Bauweise des Slicers (Füllanker, Zusatzwände). Messung vor RM-281 C; mit Herstellerbündel neu messen, dann entscheidet Robert über Vorgaben |
| [RM-209 — Die Rundform-Einpassung an Gittermodellen](#rm-209) | Geometrie, Erkennung und Druckvorbereitung | Stapelumbau (0.5.1) und bitgleiche Vektornorm im Löser gebaut; Kumiko-Schale 18,6–20,2 s unter Last, §31 (unter 5 s) nicht erreicht; offen: Aufbereitung großer Flecken und Fits beschleunigen, danach ruhige Vergleichsläufe |
| [RM-132 — Freiformerkennung am Ein-Sekunden-Ziel messen](#rm-132) | Geometrie, Erkennung und Druckvorbereitung | Ziel neu gefasst (Bauplan §31, Robert 06.10.: mechanisch unter 1 s, organisch unter 2 s am Referenzrechner); offen die Messung am neuen Ziel |
| [RM-166 — Ergebnisnetze aus Mesh-Ops an einer STL überstehen keinen Weld](#rm-166) | Geometrie, Erkennung und Druckvorbereitung | Die Werkzeuge und der Eckanschluss rechnen plattformgleich (`9bc3d354e`, Ecke in `test_platform_identity._WAYS`); offen allein die Marke `xfail(linux)`, die nach drei grünen Linux-Läufen in Folge fällt, und das Beispielarchiv der Werkstattfilme mit der nächsten Filmrunde |
| [RM-193 — Die Erkennung an einer glatten Generator-Freiform kostet Minuten für null Merkmale](#rm-193) | Geometrie, Erkennung und Druckvorbereitung | Ziel neu gefasst (Bauplan §31: organisch unter 2 s am Referenzrechner); der Drache braucht 6,9–9,0 s unter Last bei null Merkmalen; offen ein Hebel bis zum neuen Ziel |
| [RM-201 — Ein hohler Körper hält die 300 ms der Schichtanalyse nicht](#rm-201) | Geometrie, Erkennung und Druckvorbereitung | Unabhängige Clipper-Säulen, gerichtete Verschachtelung und `ring_nesting` gebaut, Hohlkugel bitgleich in 1,2–1,4 s; Mitre-Öffnung über Clipper und Zertifikate gemessen und verworfen; 300 ms verfehlt, ob ein weiterer Hebel kommt oder §31 für Schalen neu gefasst wird, entscheidet Robert |
| [RM-217 — Die Zuordnungsfrage zeigt das alte Merkmal nicht im Bild](#rm-217) | Geometrie, Erkennung und Druckvorbereitung | Altmerkmal und Kandidat werden gemeinsam markiert; Kern-, Ansichts- und Regressionstests grün. Offen: echter Fensterbeleg im Release unter RM-213 |
| [RM-218 — Am exakten Körper heißen Bohrungen nach ihrer Lage, und der Verlauf lässt sich dort nicht umbauen](#rm-218) | Geometrie, Erkennung und Druckvorbereitung | Code und Tor mit `d907d6036` in v0.5.2; offen allein die Fensterabnahme beim Release (RM-213) |
| [RM-230 — Variable Verrundung und Formschräge: fünf Grenzen, die der Kunde merkt](#rm-230) | Geometrie, Erkennung und Druckvorbereitung | Anfang auf Ringen fest, Außen-/Innen-Mischecke exakt ungeprüft, Zwischenstellen nicht bindbar, Schräge an allen Wänden des Trays abgesagt, Netzschräge 2,3× langsamer — je Grenze bauen oder benennen |
| [RM-253 — Am Laptop-Ständer tragen Kippen und Verdoppeln einer Bohrung falsch ab](#rm-253) | Geometrie, Erkennung und Druckvorbereitung | Seit `6d395169c` rechnen Schritte abseits der selbstkreuzenden Schale mit Warnung, am Treffer hält der Schritt (RM-382). Am Original weiter: Verdoppeln ohne Wirkung, `no_longer_through` beim Versetzen und Kippen, Volumenzunahme beim Kippen; die Sonde braucht eine Messung ohne Differenz gegen die kaputte Schale |
| [RM-247 — Die Waschschüssel ließ sich nach Solidons Übergabe nicht drucken](#rm-247) | Geometrie, Erkennung und Druckvorbereitung | Kanaldecken, Gitter als Gitter, Leerfahrt und Tempo vom Drucker, Kanalsperre je Slicerfamilie, Brim auf Füßen — gebaut und im ElegooSlicer und PrusaSlicer belegt; offen: Probedruck am Centauri |
| [RM-281 — Die Übergabe auf dem Herstellerprofil: Stufen C bis F](#rm-281) | Geometrie, Erkennung und Druckvorbereitung | Paket 3 und Reste D abgenommen, Stützvorschlag für Brücken über dem Modell und Absturz der Schichtanalyse behoben, Matrixwerkzeug auf Dialogcode umgestellt (04.10.); offen die Gesamtabnahme jedes Modell × jeder Slicer und die Zeitschätzung (ElegooSlicer −18 % an der Seitenablage, Stützmenge an gewölbten Flächen drei- bis zwölfmal unterschätzt, ihre Rechenzeit) |
| [RM-259 — Eine Mündungsrundung in einer gekrümmten Fläche reist nicht mit ihrer Senkbohrung](#rm-259) | Geometrie, Erkennung und Druckvorbereitung | In einer ebenen Fläche gebaut (`202d5133a`: Versetzen ±0,000 mm³, Entfernen genau die Platte, beide Kerne); gekrümmt offen: am Netz die Senkung hinter einer Rollkugelrundung erkennen und eine Fläche aus mehreren Grundformen über die Öffnung fortsetzen, am exakten Kern den Prototyp `m19_exakt_band.py` samt Bandkennung übernehmen. Abnahme neu gegen den Sollwert −2,97 / +0,29 / −4,56 mm³ an gs-100 |
| [RM-262 — Die Erkennung liest eine gekippte Haltelippe nicht](#rm-262) | Geometrie, Erkennung und Druckvorbereitung | Die Absage bleibt (rest-muendung): Mit dem Drehweg liest der exakte Kern Tasche, angeschnittenen Kegel ohne Verengung und Schacht als Zylinderstück, das Netz nur eine gerundete Seite. Erst beide Erkennungen und `bore_entrance` mit schräger Mündung hinter einer Verengung, dann *Merkmal drehen* freigeben; der Drehweg liegt als `prepare_ops_mit_drehen_heute.patch` gegen den Stand vom 27.09. (`2e496575b`, `202d5133a`) bei und muss vor Gebrauch auf den heutigen `prepare_ops.py` übertragen werden |
| [RM-292 — Laufzeitreste der Durchsicht 0.5.1](#rm-292) | Geometrie, Erkennung und Druckvorbereitung | (b) Eigenkreuzung endet beim ersten Gegenbeleg (Besenhalter 18,4 → 14,6–15,1 s, Laptop 26–28,6 → 20,1–20,9 s unter Last, Paare bitgleich), (c) ohne zweite Vereinigung gebaut; offen: (a) beim Öffnen am Fenster zuordnen, (b) lastfrei messen und mit Ziel führen |
| [RM-296 — Die genaue Vorschau großer Teile rechnet am ganzen Körper](#rm-296) | Geometrie, Erkennung und Druckvorbereitung | Bekannte Durchgangswand misst örtlich nach, die letzte Vorschau erkennt nur noch den Folgebedarf; Senkplatte im Sitzungsweg 7,6/4,6/3,5 s (Ø 6/6,5/7, unter Last); offen: unter 3 s auf ruhiger Maschine |
| [RM-298 — Hilfsprozess: Reste aus dem Review](#rm-298) | Geometrie, Erkennung und Druckvorbereitung | (a)–(f) im Code und in v0.5.2; offen: POSIX-Speicherbesitz und SIGBUS (b), §31-Hilfsprozessmarken auf der Referenzmaschine sowie Linux/macOS (d), native Abbruch- und Killlatenz am Fenster und auf dem Mac-Runner (e, f) — alles Release-Abnahme |
| [RM-307 — Auto Split: Reste aus dem Review der Vorauswahl](#rm-307) | Geometrie, Erkennung und Druckvorbereitung | Native Vorauswahl `orientation_scores` bitgleich zur NumPy-Fassung, Stützraum am Suchnetz mit Stand am Original, Stand an den Toleranzrändern geprüft; T2 im Messfenster nativ 14,7–19,7 s, ohne Kern 16,5–23,4 s unter Fremdlast; offen: lastfreie Messung beider Wege und Nachweis zu (a) |
| [RM-385 — Reste aus dem Review von `eab5f4f47` und `a45730c79`](#rm-385) | Geometrie, Erkennung und Druckvorbereitung | Rat, `parts_united` exakt, Regel und Testdoppel mit `6d395169c` erledigt; offen: Archivsatz zur 1e7-Verschiebung belegen oder streichen, `test_geometry_review_regressions.py:607` bewerten, §17.2 mit Ansage |
| [RM-405 — Die volle Schichtanalyse reißt §31 um Faktor 35–60; drei belegte Ursachen](#rm-405) | Geometrie, Erkennung und Druckvorbereitung | (a) `cuts_along` im Cythonkern, (b) mit RM-486 und unabhängigen Säulen, (c) Kanalfrage und Schichtansicht über den Merker gebaut; F0FF je zweimal bitgleich, Screen-Cover 0,7–0,9 statt 3,4–3,8 s, CC2-Box 5,1–5,5 statt 40,7–41,5 s; offen: Schichtansicht am Fenster beim Release (RM-213) |
| [RM-410 — Die schnelle Orientierung rechnet am vollen Netz und ist an großen Baugruppen langsamer als die gründliche](#rm-410) | Geometrie, Erkennung und Druckvorbereitung | Schnelle Ausrichtung prüft den Bauraum erst am betrachteten Kandidaten und teilt gleiche Formen, Gewinner unverändert; chufang schnell 65–68 statt 161 s, gründlich 150 s, beide unter Fremdlast; offen: lastfreie Vergleichsmessung an chufang und zwei Baugruppen |
| [RM-413 — Reste aus dem Review von `57848fa72` und `e3dff1907`](#rm-413) | Geometrie, Erkennung und Druckvorbereitung | Review 02.10.: toter Code, abgelöster Merkmalarbeiter, doppelter Builder, falscher Absagegrund, Regel nicht nachgezogen |
| [RM-425 — Überlappende gespiegelte Formzüge verlieren ihre Symmetrie](#rm-425) | Geometrie, Erkennung und Druckvorbereitung | Fehlerfall S01 seit `f77576d19` behoben (0,000 statt 0,341 mm); offen: S01 als bleibender Test, dritter Körper, Achsen Y/Z, verschobene Spiegelmitte, alte Züge |
| [RM-504 — Importierte Texturen als gemeinsame Auswahl](#rm-504) | Geometrie, Erkennung und Druckvorbereitung | Zusammenfassung kleiner Felder und STEP-Muster gebaut und belegt (04.10.); offen allein die Fensterabnahme beim Release (RM-213) |
| [RM-496 — Reale Modelle laden im Prüfstand fast doppelt so lang wie in v0.5.1 — am echten Fenster nachmessen](#rm-496) | Geometrie, Erkennung und Druckvorbereitung | Versionsvergleich 02.10.: Verdacht gegenüber v0.5.1 (nachgeholte Importe 2,2 s, Erkennung 1,4 s); Startweg mit Vorwärmen messen |
| [RM-525 — Anycubic Slicer Next über alle Drucker und den Modellkorpus verifizieren](#rm-525) | Geometrie, Erkennung und Druckvorbereitung | B1 bis B6 behoben und an 13 Fällen im Slicer belegt (05.10.); offen: Waschschüssel an 29 Druckern, die Minigolf-Platte als 3MF, der Plan `modelle` über `F:\3D Dateien` an Kobra S1 und S1 Max, vorher das Matrixwerkzeug (Blockleser, Stützmarke nach Volumen) |
| [RM-527 — An der Kanalmündung entscheidet die Sperre gegen eine verlangte Stütze](#rm-527) | Geometrie, Erkennung und Druckvorbereitung | Entschieden (Robert, 06.10.): Mündung frei halten; offen die Abnahme in Anycubic, Elegoo und Orca |
| [RM-539 — Ein Baustein mit Trägeraufbau, auf der Innenseite gesetzt, baut nach außen ohne Befund](#rm-539) | Geometrie, Erkennung und Druckvorbereitung | Gefunden am Gehäuse-Beispiel (06.10.); offen der Befund beim Einsetzen und seine Handlung |
| [RM-541 — Der Skizzenlöser landet auf dem Intel-Mac im anderen Zweig einer Winkelbedingung](#rm-541) | Geometrie, Erkennung und Druckvorbereitung | Gefunden mit RM-531 (06.10.): 135° statt 45° unter macOS Intel; offen die Rechnung in Verschiebungen und ihre Wirkung auf unterbestimmte Skizzen |
| [RM-542 — Die fünf offenen Entscheidungen der Erstkonfiguration](#rm-542) | Geometrie, Erkennung und Druckvorbereitung | Gefunden beim Umräumen der Konzepte (RM-099, 06.10.): nur im Konzept geführt; offen der Abgleich mit RM-281 und Roberts Entscheidung |
| [RM-070 — SpaceMouse auf macOS und Linux am echten Gerät abnehmen](#rm-070) | Bedienung und Darstellung | Die Rampe ist stetig und getestet, die Bildrate an 815 104 Dreiecken gemessen (`7ff34c67`: 16,7 → 8,7 ms im Median); offen bleiben Linux, die 3DxWare-Mausemulation, das Gerät selbst und die Rampe im Skizzenmodus (aus RM-183) |
| [RM-204 — Ein Merkmalklick baut alle Handlungen des Fensters neu](#rm-204) | Bedienung und Darstellung | Abnahme am echten Fenster beim Release (RM-213) |
| [RM-283 — Ein Handbuch, das man ohne Ausprobieren versteht](#rm-283) | Bedienung und Darstellung | Nummernplatzierung gebaut und in den Bildanleitungen von 0.5.3 erzeugt (`ee9a572f3`); offen allein die Feldabnahme nach §11 mit einem Kunden ohne CAD |
| [RM-084 — Kundentexte gegen die vereinbarte Sprache prüfen](#rm-084) | Bedienung und Darstellung | Kataloge und Quelltexte durchgesehen und behoben (04.10., `871cc29e6`), Handbuch und Stempel mit 0.5.3 erzeugt; offen allein die Fensterabnahme der längeren Knopfnamen auf 1280 px (RM-213) |
| [RM-090 — Gemeinsamen Vertrag für die fünf Produkterlebnisse umsetzen](#rm-090) | Bedienung und Darstellung | Gegenprobe liest Export- und Slicerdateien zurück, Nebenfolge je Handlung aus dem Kern, Folge je Befund, Kandidatenprüfung nennt nur Neues und Behobenes, NM 1–11 ohne Fenster belegt; offen allein die Fensterabnahme beim Release (RM-213) |
| [RM-135 — Zugewiesene Höhe der Filamentkarte vollständig nutzen](#rm-135) | Bedienung und Darstellung | Windows-Stand nachgemessen am 23.09.2026 (Overlay- und Kartentests grün); offen nur der macOS-Prüflauf |
| [RM-198 — Eine feine Fenstermaske über der Vulkan-Fläche verliert das Gerät](#rm-198) | Bedienung und Darstellung | Probe über den echten Startweg beim nächsten Release (RM-213); D3D12 als Backend ist eine eigene Entscheidung |
| [RM-200 — Ein Zug am Griff soll flüssig sein](#rm-200) | Bedienung und Darstellung | Am echten Fenster prüfen, ob sich die Geste flüssig anfühlt (Release, RM-213) |
| [RM-213 — Fensterabnahme und die Kundenwege am echten Fenster](#rm-213) | Bedienung und Darstellung | Beim Release: die offscreen belegten Änderungen am echten Fenster, die Kundenwege C14/A13/A4/C5/C1 und die vier Hauptwege mit Zeiten, die Fensterproben der Fensterwache und von C14. Vorbedingungen für 0.5.3 erfüllt (Taglauf 37409338027 mit allen Fensterdateien grün, Bereichsnachweis `534d69b79`), beim nächsten Release erneut; dazu die vier Handwege der Merkmalbedienung (§4) |
| [RM-232 — Die Klickkette an einem Merkmal rechnet noch im Hauptfaden](#rm-232) | Bedienung und Darstellung | Doppelter Rollenlauf, 96 Sichtbarkeitswechsel, ein zusätzlicher Bildauftrag und ein verspäteter Hover-Neuaufbau entfernt (139/347 Fälle); am Fenster Baumklick 87–94 ms, Bildklick vor dem Hover-Fix 105–146 ms; offen: Abnahme unter 100 ms auf ruhiger Maschine am MSI |
| [RM-258 — Zwei einmalige Stillstände beim Einlesen großer 3MF](#rm-258) | Bedienung und Darstellung | Übernommen: Claude, Thread „Bedienung und KI“. Ursache behoben (0.5.1, Paket 3mf); offen zwei einmalige Stellen über 200 ms je Import: erstes Bild der Arbeitsfläche, Rückfrage zur Vollerkennung |
| [RM-285 — Feste Doppelpunkte hinter übersetzten Teilen](#rm-285) | Bedienung und Darstellung | UI/CLI/Bereichsprüfer auf origin/main integriert; dauerhafte Nachweise und Modelltext-Restliste vorhanden. Modellabnahme offen |
| [RM-312 — Die Düsengröße im Druckdialog kommt vom Drucker und ist eine Auswahl](#rm-312) | Bedienung und Darstellung | Alle 575 Matrixzeilen eingeordnet, neun Übergabefehler behoben, Auto-Brim mit fester Breite und Warnung, Stützfuß und Skirt am Bettrand aus dem Profil (04.10.), Brim und Skirt um die erste Schicht statt um die Aufsicht (05.10.); Stützfuß unter den Überhängen statt unter der ganzen Aufsicht (06.10.); offen: der Gesamtlauf jedes Modell × jeder Slicer (mit RM-281) und die Fensterabnahme beim Release; die Druckdauer am K1 ist ohne Gerät nicht messbar |
| [RM-502 — Dialog-Durchsicht vom 29.09.: spätere Korrekturen abnehmen und verbliebene Hinweisorte klären](#rm-502) | Bedienung und Darstellung | Ziffernweg und Rückweg „Unbekannt“ in sechs Sprachen über den Spulendialog belegt, Speicherfehler und kleines Spulenfenster durch bestehende Fälle; offen allein die Fensterabnahme auf allen Plattformen beim Release (RM-213) |
| [RM-003 — Lizenzkette der gepinnten TripoSG-Bestandteile klären](#rm-003) | KI und Generatoren | Lizenzkette der eingesetzten Modellrevisionen klären |
| [RM-004 — Echte Text- und Bildgenerierung über alle Zielplattformen abnehmen](#rm-004) | KI und Generatoren | Echte Text-/Bildläufe auf Windows, macOS und Linux dokumentieren |
| [RM-014 — Zusätzliche Formenregel und zugehörige Suite-Abnahme entscheiden](#rm-014) | KI und Generatoren | Zusätzliche Formenregel entscheiden; bei Änderung Suite vorher/nachher |
| [RM-251 — Mehrteilige Aufträge enden lokal am Schrittlimit](#rm-251) | KI und Generatoren | Übernommen: Claude, Thread „Bedienung und KI“. (a) entschieden und gebaut: lokal 12 Schritte (`MAX_STEPS_LOCAL`, `steps_for`), gehostet 8; offen (b) der Satz im Prompt für gebündelte Aufrufe — braucht einen Suitelauf mit qwen3:14b vorher und nachher auf freier Karte |
| [RM-016 — Agenten-Suite gegen das aktuelle Vorgabemodell messen](#rm-016) | KI und Generatoren | Gehosteter Lauf freigegeben (Robert, 06.10.), wartet auf einen hinterlegten Anthropic-Schlüssel; daneben der lokale Lauf nach RM-513 gegen `1ce7eac68` |
| [RM-441 — Reste aus RM-372 und RM-374: `hollow.done` ohne Knopf, Beispielprojekt mit alten Transaktionen](#rm-441) | KI und Generatoren | (a) und (b) erledigt; offen die sechs Befunde aus dem Review 02.10., die einen Schritt meinen und *Diesen Schritt ändern* noch nicht tragen |
| [RM-529 — Der Steckbrief nennt nicht, welcher Schritt ein Merkmal erzeugt hat](#rm-529) | KI und Generatoren | `created_by` in Merkmals- und Objektzeile des Steckbriefs nachrüsten (Entscheidung Robert, 06.10.) |
| [RM-103 — Große Kernfunktionen nach konkretem Wartungsbedarf aufteilen](#rm-103) | Tests und Entwicklungswerkzeuge | Auswertung und weitere große Funktionen nach Wartungsbedarf priorisieren |
| [RM-134 — Doppelte Testhilfen zusammenführen](#rm-134) | Tests und Entwicklungswerkzeuge | Genehmigt (Robert: „alles gründlich“); neun Helfer in `helpers.py`/`ui_helpers.py` (`95fd36d35`); offen `on_the_bore_wall`, `project`, `FakeCodec`, `a_foreign_slot`; entschieden (Robert, 06.10.): auch die großen Fenster-Fixtures zusammenführen |
| [RM-272 — Die Entwicklungsmaschine rechnet zeitweise falsch](#rm-272) | Tests und Entwicklungswerkzeuge | Entscheidung Robert: CPU-Tausch über Intels verlängerte Garantie, bis dahin Intel Default Settings; offen MemTest86 über Nacht und der Tausch selbst; die Pakete von 0.5.3 kommen aus der CI, Handbuch, Bilder und Signatur entstehen weiter hier |
| [RM-288 — Ein Einzelprozess über die ganze Suite hängt im Sammler](#rm-288) | Tests und Entwicklungswerkzeuge | Nachstellversuch als Einzelprozess lief ohne Hänger durch (3:33 h); offen: Ursache, und ob die Anwendung betroffen ist |
| [RM-314 — Rechtenachweis der Stimme für die englischen Werkstattfilme](#rm-314) | Tests und Entwicklungswerkzeuge | Stimme mit Prüfsummen in `licences.toml` dokumentiert; offen: `/legal-review` zur Werbenutzung, Eintrag in `ASSET-RIGHTS.toml` und ein Test, der die Stimme prüft |
| [RM-316 — Zwillinge und Nur-Test-Wege: der Rest aus dem Code-Bericht des Aufräumens](#rm-316) | Tests und Entwicklungswerkzeuge | (d) und Teile von (b)/(c) mit `b03c0ddfe` erledigt; offen die Kopie `_select_data` samt Karte, die übrigen dünnen Hüllen aus (b), `section.section_volume` und `repair.fill_holes` (Liste am Punkt) |
| [RM-344 — Renderertests laufen in der CI nur noch unter Windows](#rm-344) | Tests und Entwicklungswerkzeuge | Entschieden (Robert, 06.10.): `rendering`-Fälle in der Release-CI auch unter Linux und macOS, dazu der Wächter in `test_packaging.py` |
| [RM-467 — Bibliotheken alle drei Tage auf neue Versionen prüfen und aktualisieren](#rm-467) | Tests und Entwicklungswerkzeuge | Erster Lauf 02.10. im Archiv; der zweite war am 05.10. fällig und steht aus (bekannt: cadquery-ocp-novtk 8.0.1.1.0); Paketbeleg der Bauplattform unter RM-468 |
| [RM-531 — Fenstertests und echte Slicer auch unter Linux und macOS in der CI](#rm-531) | Tests und Entwicklungswerkzeuge | Entschieden (Robert, 06.10.): Fenster- und Renderergruppe auf vier Plattformen am Tag, per Handstart und bei jedem Push auf main. 14 der 23 roten Fenstertests außerhalb von Windows behoben, auf allen vier grün (07.10.); offen acht Fälle, `build.yml`, die Wächter und der Slicer-Job |
| [RM-002 — netcup-AVV und Freigabe der Rechtstexte belegen](#rm-002) | Veröffentlichung, Betrieb und Vertrieb | netcup-AVV belegen und zugehörige Rechtstexte fachlich abgleichen |
| [RM-006 — Nächsten messbaren Schritt für die Sichtbarkeit festlegen](#rm-006) | Veröffentlichung, Betrieb und Vertrieb | Roberts Bestätigung des Plans bis 01.11. und die Montagsmessungen; der Punkt schließt, wenn Robert den Plan bestätigt |
| [RM-008 — DMARC-Eintrag öffentlich prüfen und gegebenenfalls einrichten](#rm-008) | Veröffentlichung, Betrieb und Vertrieb | DMARC einrichten und legitimen Mailversand prüfen |
| [RM-030 — Impressum nach Vergabe einer USt-IdNr. oder W-IdNr. ergänzen](#rm-030) | Veröffentlichung, Betrieb und Vertrieb | Bereits vergebene USt-IdNr./W-IdNr. klären; gegebenenfalls Impressum ergänzen |
| [RM-034 — Versicherungsschutz für Software und Produktschäden klären](#rm-034) | Veröffentlichung, Betrieb und Vertrieb | Versicherungsangebote gegen die tatsächlichen Risiken prüfen lassen |
| [RM-035 — EULA wirksam in den Bestellvorgang einbeziehen](#rm-035) | Veröffentlichung, Betrieb und Vertrieb | Produktgrenzen und EULA im vollständigen Bestellweg rechtlich prüfen |
| [RM-036 — Vertrag und Freistellungen des Zahlungsdienstleisters prüfen](#rm-036) | Veröffentlichung, Betrieb und Vertrieb | Konkreten Anbietervertrag und Haftungsübernahme entscheiden |
| [RM-061 — Verkaufsbereitschaft und Ende der Demo vorbereiten](#rm-061) | Veröffentlichung, Betrieb und Vertrieb | Kandidat bis 25.10.; letzte Optimierungen 31.10.; Start 01.11.2026 um 10:00 Uhr deutscher Zeit — gebaut in 0.5.0: Abschied mit Pause und Start, ‚heute letzter Tag‘, Hinweis ab 24.10. (`29dcefa4`); offen täglicher Ablaufwächter und Bestell-Webhook |
| [RM-091 — CRA-Meldebereitschaft herstellen, die Frist ist abgelaufen](#rm-091) | Veröffentlichung, Betrieb und Vertrieb | Meldeweg entschieden (Robert, 23.09.2026: über die Support-Adresse, Antwortfrist zwei Arbeitstage, keine Belohnung, kein PGP; `SECURITY.md`, `SECURITY-INCIDENT.md` und `security.html` sind konform); offen EU-Login, Vertretung, CSIRT-Zuordnung, Alarmierung und Probelauf — Roberts Konten |
| [RM-092 — Verkaufskonzept für den geplanten Start abschließen](#rm-092) | Veröffentlichung, Betrieb und Vertrieb | Anbieter, Bestellstrecke, Lieferung, Widerruf und Signierung bis 15.10. |
| [RM-093 — Noch fehlende Angaben und Prüfungen der Rechtstexte klären](#rm-093) | Veröffentlichung, Betrieb und Vertrieb | Fehlende Anbieter-/Rechtsentscheidungen und Sprachfassungen fachlich prüfen |
| [RM-095 — Automatischen Löschlauf auf dem Server belegen](#rm-095) | Veröffentlichung, Betrieb und Vertrieb | Server-Löschlauf, Sicherungen und Ausfallalarm tatsächlich nachweisen |
| [RM-116 — Historische Statistikreste auf dem Server behandeln](#rm-116) | Veröffentlichung, Betrieb und Vertrieb | Öffentlichen Altbestand prüfen und Umgang mit alten Statistikzeilen entscheiden |
| [RM-145 — CRA-Konformitätsakte zum gesetzlichen Anwendungszeitpunkt vorbereiten](#rm-145) | Veröffentlichung, Betrieb und Vertrieb | Produktklassifizierung, technische Akte und Konformitätsverfahren für 2027 vorbereiten |
| [RM-242 — Testphase der Vollversion nachreichen](#rm-242) | Veröffentlichung, Betrieb und Vertrieb | Robert 25.09.2026: 1.0 startet ohne Testphase, sie kommt später — Januar (Unentschlossene noch zu 69 €) oder Februar 2027 mit dem Preissprung. Offen: Termin, ob frühere Demo-Geräte sie bekommen (heute T15: nein), Release mit gesetztem `TRIAL_FROM` |
| [RM-351 — Die Website bietet 0.5.1 an und nennt im Downloadhinweis 0.5.0 als signierte Fassung](#rm-351) | Veröffentlichung, Betrieb und Vertrieb | Hinweis seit `1d9373efa` in sechs Sprachen versionsneutral („ab 0.5.0“), in 0.5.2 und 0.5.3; offen der Wächter aus der Abnahme — oder Roberts Verzicht, weil der Satz keine Version mehr an das Angebot bindet |
| [RM-528 — Die Installation kennt nur einen Release-Schlüssel](#rm-528) | Veröffentlichung, Betrieb und Vertrieb | Schlüsselliste in `updates.py` bauen und ausliefern, bevor der Release-Schlüssel wechselt (Entscheidung Robert, 06.10.) |
| [RM-062 — Eingabemethode im aktuellen Flatpak bestätigen](#rm-062) | Kundenrückmeldungen | Am ausgelieferten 0.5.3 gemessen: Start, Fokus und Eingabe gehen, Fcitx nur über IBus; Abhilfe gebaut (Fcitx in der Umgebung → `ibus`, außerhalb des Flatpak über das IBus-Portal), offen der Nachweis im nächsten Paket für Flatpak, AppImage und Archiv |
| [RM-521 — Cura unter Linux slicen lassen (AppImage und Flatpak)](#rm-521) | Kundenrückmeldungen | Lader-Weg und Rückfall gebaut, am Runner mit Flatpak und AppImage, draußen und im Sandkasten belegt (Lauf 37528397381); offen: Abnahme beim Kunden mit dem nächsten Paket (Ubuntu 24.04, Solidon als Flatpak) |
| [RM-522 — Dem Linux-Kunden mit Orca als Flatpak die Behebung melden](#rm-522) | Kundenrückmeldungen | Text für 0.5.3 liegt in Roberts Ablage bereit, Behebung am ausgelieferten Paket belegt (RM-064); Robert schickt, dann Versand eintragen |
| [RM-532 — Gewinde in jedem Maß: Bereichsnachweis, Tor und Zusammenführung](#rm-532) | Kundenrückmeldungen | Umgesetzt auf Zweig `gewinde-eigenes-mass` (`63d7a7826`), ruff, Format und mypy grün; offen Bereichsnachweis aller 49 Bausteine, volles Tor, Merge nach main, dann der Hash an die Sitzung „Stift für Bohrung“ |
| [RM-533 — Entf tut an der Auswahl still nichts](#rm-533) | Kundenrückmeldungen | Gebaut und an Sonde und Fenstertest belegt, nicht committet (Hunks im Arbeitsbaum des i9, Patches im Zustandsordner); offen Tor, Commit der eigenen Hunks und der Titel aus `_removal_entry` |
| [RM-534 — Der Prüfbericht zeigt während einer Neuberechnung alte Fehler als gültig](#rm-534) | Kundenrückmeldungen | Ursache an der Kundendatei gemessen; Umsetzung in vier Teilen (Laufzustand, volle Kette selbst, Halt im Entwurf nie fein, kein Hin und Her) nicht begonnen |
| [RM-535 — Merkmal verschieben: Felder an Flächen, Karte und Operation uneins, falsche Ergebnisse ohne Befund](#rm-535) | Kundenrückmeldungen | Entschieden (Robert, am Punkt); Flächenzug, Absagen, Maßgruppe, Tasche und Zapfen nach diesen Entscheidungen bauen, die drei falschen Ergebnisse beheben |
| [RM-536 — Stift für Bohrung baut das passende Gegenstück zu Gewinde und Senkung](#rm-536) | Kundenrückmeldungen | Kundenwunsch, Auftrag ausgearbeitet; gebaut wird nach dem Merge von RM-532 auf main |
| [RM-072 — Zusagen an den Dental-Kunden zum Verkaufsstart erfüllen](#rm-072) | Kundenrückmeldungen | Kaufweg und belastbare 3D-Maus-Unterstützung zum zugesagten Anlass mitteilen |

## Filamentlager

Physische Spulen mit bis zu vier Farben, Regal, bewusster Import, Schnellauswahl
und rücknehmbare Verbrauchsbuchungen sind angeschlossen; „Erste Schritte“ führt
über Slicer und Drucker zum Lager. Das [Gestaltungs- und Gesamtreview](konzepte/archiv/review-filamente-2026-09.md)
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

Merkmalserkennung, Zuordnung, Analysekarten und Schichtanalyse sind umgesetzt. Offen bleiben Qualitäts- und Leistungsfälle (RM-132, RM-193, RM-209, RM-405) und die Fensterabnahme der Zuordnungsfrage (RM-217); die gespeicherten Zuordnungsantworten sind mit RM-024 abgenommen. Eine schnelle Kugelprobe belegt keine schnelle Freiformerkennung.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p3--wahrnehmung-und-schichtanalyse).

## P4 — Agent auf Säule C

Agentensteuerung über dieselben Operationen, Rückfragen und Vorschläge als Transaktion sind umgesetzt. Historische Suitequoten gelten für ihr damaliges Modell und ihren Prompt; aktuelle Modell-/Schemaabnahmen stehen unter KI.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p4--agent-auf-säule-c).

## P5 — Bausteinbibliothek

Bibliothek, Normteile, Versionierung, Vorschauen und Rezeptweg sind umgesetzt. Ein alter Bausteinstand reist nicht mit; die Migrationsmeldung nennt je Baustein die Änderung, eigene Rezepte bieten „Gespeicherten Stand verwenden“ ([RM-138](ROADMAP-ARCHIV.md#rm-138)). Bereichsprüfungen werden bei Änderungen an Baustein oder Grenzen gezielt gefahren; der automatische Komplettlauf über sämtliche Bausteine ist gemäß AGENTS.md entfallen. `to_scad()` bleibt ein reiner Dateiexport.

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

Automatisches Teilen und Verbinder sind umgesetzt. Stiftseite (RM-005) und Trennen-Serie (RM-080) sind abgeschlossen; offen sind die Laufzeitreste der Vorauswahl (RM-307) und plattformgleiche Naht- und Stiftlagen (RM-187). Der Umfang aus §40 ist vom später beauftragten Ausbau zu unterscheiden.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p10--auto-split-mit-verstiftung).

## P11 — Gehosteter Backend

Zurückgestellt; kein laufendes Bauvorhaben. Ein gehosteter Generierungsdienst käme nur nach Nachfrage und ausdrücklicher Produktentscheidung infrage. Gehostete Bearbeitung bleibt nach AGENTS.md ausgeschlossen.

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p11--gehosteter-backend).

## P12 — B-Rep-Kern

Der optionale exakte Kern und STEP-Austausch sind umgesetzt. Das ist keine allgemeine Rückgewinnung exakter CAD-Flächen aus beliebigen Netzen. Der Nachbau als Operationsfolge ist seit dem 17.09.2026 beschlossen; Umfang und Abnahme stehen in RM-022, die Umsetzung läuft als Teil des CAD-Plans (RM-188).

[Frühere Abnahme und Umsetzung](ROADMAP-ARCHIV.md#p12--b-rep-kern).

## P13 — Skizzen und tiefere Konstruktion

Skizzen, Bedingungen und Formgebungsoperationen sind umgesetzt. Die aktuellen Plattformbefunde des Lösers bleiben bei den offenen Aufgaben; Gewinde- und Exportpfade auf macOS und Linux stehen bei RM-104.

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

- [~] **RM-021 — Native Fensterlebensdauer am aktuellen Renderer abnehmen.** Der vollständige geteilte
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

  **Teilstand 04.10.2026 (Hänger, behoben mit `35847e4db`, ausgeliefert in 0.5.3):** Die Anwendung stand
  einmal still, als der Speicherbereiniger im Arbeiter der Druckbefunde (`print_findings_flow` →
  `slice_body`) ein Qt-Objekt mit Kindern zerstörte: Dessen Destruktor hielt Qts Verbindungssperre
  und wartete auf den GIL, während der Hauptfaden mit dem GIL in `overlay._move` ein Signal
  verbinden wollte (`py-spy dump --native`, Beleg
  `F:\solidon-review-reports\claude-2026-10-04\rm184-gruppen\haenger-gc-im-arbeiter.txt`). Betrifft
  jedes Fenster mit Arbeitern; `leash.undisturbed` schützt nur einzelne Stellen.

  **Teilstand 05.10.2026 (gebaut):** Im Fensterprozess ruht die automatische Speicherbereinigung;
  `leash.collect_in_main_thread` räumt im Hauptfaden nach ihren Schwellen ab und wartet, solange
  `undisturbed` offen ist. Gerufen in `main` vor dem ersten Arbeiter, in `build_application` und
  in der Fixture `qt_app`. `test_leash.py` hält es: Ein Arbeiter weit über der Schwelle beginnt
  keine Bereinigung, der Hauptfaden räumt den im Arbeiter losgelassenen Ring mit Qt-Objekt ab;
  Gegenprobe mit eingeschalteter Automatik bereinigt im Arbeiter. Danach das Release-Tor mit
  allen Fenster- und Rendererdateien je Datei grün (Kernsammlung 24 083 bestanden, die zwei roten
  Budgetfälle der Unterlagen behoben). Offen bleibt die Vergleichsreihe oben.

<a id="rm-050"></a>

- [~] **RM-050 — Kopier- und Pufferkosten großer Szenen am Fenster messen.** pygfx ist der einzige
  Renderer; die mehrfachen Normalenläufe und das Halten alter Renderer beim Sprachwechsel sind
  behoben. Offen bleiben die kopierten Bytes und Pufferkosten je großer Szene. Abnahme:
  reproduzierbare Zeit-/Speichermessung am großen Netz. Der beschlossene Ersatz von VTK in der
  Baustein-Bereichsprüfung ist nachgewiesen; Plattformfenster werden separat abgenommen.

  **VTK ausgebaut am 23.09.2026** (`5a57e261`):
  `range_check.local_wall_thickness` misst mit `mesh.ray_hits_batch`
  (Möller-Trumbore als Feld, mit `ray_hits` auf eine Rechnung zusammengelegt)
  statt `vtkStaticCellLocator`, alle 35 Bausteine mit unveränderten Ergebnissen;
  `THIRD-PARTY-NOTICES.md` hatte danach 42 Komponenten. **Aktueller Stand:** matplotlib ist
  seit `25d5536ee` (RM-471) keine Abhängigkeit mehr, Schriftzüge setzt HarfBuzz; die
  Windows-Entwicklungsvorschau der Lizenzbeilage nennt 41 Pakete. Die Kundenbeilage entsteht
  weiterhin je Plattform aus deren Endartefakt-SBOM.
  Nachweis: `konzepte/nachweise-release-0.5.0/reports/codex-ci-notices-fix.md` (67 Lizenztests,
  Generatorprüfung und Umgebungsprüfung jeweils Exit 0). Die Folgen des VTK-Ausbaus (Wandmessung ohne
  räumlichen Index, fehlender Wächter gegen VTK-Importe) standen als RM-214 und sind
  in der Durchsicht v0.5.1 geschlossen ([Archiv](ROADMAP-ARCHIV.md#rm-214): Baum aus
  Hüllquadern `7e3442623`, VTK-Wächter `a0db3edeb`).
  Offen hier nur die Kopier- und Pufferkosten am Fenster.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-der-gesamtreview-liegen-ließ-05092026).

<a id="rm-051"></a>

- [~] **RM-051 — Renderer und Grafiklaufzeit in Linux- und Mac-Paketen abnehmen.** Gebaut und
  veröffentlicht ist **0.5.3** für alle vier Ziele. Die expliziten wgpu-Bibliotheken stecken
  weiter in der Paket-Spec. Offen sind der tatsächliche Grafik-/Eingabeweg samt Vulkan
  beziehungsweise Metal und die Unix-Fenstergruppe: Die Fensterverträge laufen auf allen drei
  Systemen (`build.yml`, Job `window-contracts`), die volle Fenster- und Renderergruppe führt die
  CI nur auf Windows aus, weil Linux und macOS konkrete Befunde zeigen. Abnahme je Plattform:
  sichtbares Modell, Auswahl/Navigation, Schließen, dokumentierte Treiber-/Paketumgebung und
  erfolgreiche vollständige Fenstergruppe ohne stilles Überspringen fehlender Adapter.

  **Seit 0.5.2 startet jeder Release jedes Paket mit Fenster und 3D-Ansicht:** Linux
  (PyInstaller, AppImage, installiertes Flatpak) unter Xvfb, macOS ARM mit Metal am Runner
  (Startbericht im Taglauf 37266459831, Job 111630453072: `"renderer": {"present": true,
  "kind": "GfxRenderer"}`), Intel nur `--offscreen`, dazu das installierte `.pkg`. Offen bleiben
  eine echte Linux-GPU statt Xvfb, Auswahl und Navigation und der Intel-Mac mit Fenster.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-der-gesamtreview-liegen-ließ-05092026).

<a id="rm-055"></a>

- [~] **RM-055 — Neue Paketwerkzeuge im installierten Kundenpaket abnehmen.** Veröffentlicht ist
  inzwischen das **0.5.3**-Flatpak; offen bleibt der reale
  Linux-Lauf mit Grafik, Qt, Dateizugriff und Offline-Start.

  **Seit 0.5.2 im Release belegt:** Jedes Release installiert das Flatpak und startet es unter
  Xvfb mit eigener Sitzungsbus-Instanz (`build.yml`). Der Installer-Workflow installiert den
  Kundeninstaller mit der signierten Anwendung still und startet ihn, Inno Setup 7.1.0 fest mit
  Prüfsumme (`windows-signed-installer.yml`); für 0.5.3 im Installerlauf 37418052743, Schritt
  „Installer still installieren und starten“ grün. Offen: Aktualisieren und Deinstallieren,
  fremdes Windows, Flatpak auf echter Linux-Grafik, Offline-Start.

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

  **Aktualisieren und Deinstallieren sind ein fester Release-Schritt (06.10.2026):** Der
  Windows-Runner gilt dafür als fremdes Windows (Entscheidung Robert). Nach dem stillen
  Installieren fährt der Installer-Workflow `tools/check_windows_update.py`: die veröffentlichte
  Version aus `website/version.json` frisch installieren (Größe und SHA-256 geprüft), eigene
  Bausteine, Einstellungen, Profile und Filamente anlegen, mit den Argumenten des Update-Wegs
  (`updates.SETUP_ARGUMENTS`) auf den neuen Installer aktualisieren, Version, Installationsort,
  Neustart und unveränderte Nutzerdaten prüfen, starten, deinstallieren und nach Resten suchen
  (Wächter in `tests/test_windows_signed_installer.py`). Ohne Versionssprung ist der Schritt
  rot, und nach jeder Installation muss jede gesuchte Spur da sein. Am Runner aktualisierte das
  Werkzeug von 0.5.2 auf 0.5.3 und deinstallierte grün (Lauf 37565369075); das 0.5.2-Setup kam
  aus dem Installerlauf 37275100665, weil die Website alte Setups räumt und unter dem alten
  Namen das aktuelle ausliefert (`website/.htaccess`, `veraltet.php`). Dabei gefunden und im
  `.iss` behoben: Die Deinstallation ließ `Software\Classes\Applications\Solidon3D.exe` mit
  `SupportedTypes` stehen; bei 0.5.2 und 0.5.3 bleibt er, der Messlauf nahm ihn deshalb aus.
  Dass ohne Ausnahme nichts zurückbleibt, belegt der Lauf im nächsten Release.

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

  **Die zwei sporadischen Befunde aus den Tag-Läufen von v0.4.1 sind geschlossen
  (06.10.2026).** Der Abbruch eines lokalen Ollama-Aufrufs kam auf macOS nicht sicher an: Der
  wartende Faden weckte das blockierte `recv` mit `shutdown`, und das wirkte dort nicht
  verlässlich. Jetzt liest und sendet der Anfragefaden an einem `llm._WatchedSocket`, der den
  Abbruch selbst in Scheiben von 50 ms bemerkt; schon Angekommenes liest er zuerst, weil Windows
  bei `shutdown` über Ungelesenem die Verbindung zurücksetzt. Ohne `xfail`-Marke grün: macOS und
  Ubuntu je 20 von 20 (Lauf 37533806573), Windows 40 von 40 am i9. Nebenbei gemessen:
  `socket.getfqdn` brauchte am macOS-Runner 35 s, auf Ubuntu 2 ms; die Testserver und der
  Fernsteuerungsserver der Anwendung, der im Hauptfaden startet, lösen ihren Namen nicht mehr auf.
  Der HiDPI-Grifftest unter Xvfb lief ohne Marke 20 von 20 grün über beide Skalen (Lauf
  37492243563); die Marke ist entfernt. Der Changelog-Punkt zum Abbruch während der Antwort ist
  damit auf allen drei Plattformen belegt. [Befund und Nachweis](ROADMAP-ARCHIV.md#rm-104-teil-abbruch-des-lokalen-modells-auf-macos-und-hidpi-test-unter-xvfb-06102026).

  **Offen aus demselben Befund:** `app/ui/remote_server.py` (`abort_active`) weckt beim Beenden
  der Fernsteuerung lesende Handler mit `shutdown` aus einem fremden Faden — der Weg, der unter
  macOS nicht sicher ankam. Begrenzt ist es durch `REQUEST_TIMEOUT`, und `stop()` wartet höchstens
  5 s. Weg: dieselbe Überwachung wie beim lokalen Modell oder ein Beleg am Mac, dass der Handler
  dort endet.

  **Befund 03.10.2026, Intel-Runner (`macos-26-intel`, Lauf 37150755506):** Das
  veröffentlichte Intel-Paket 0.5.1 hängt dort beim ersten Zeigen des Fensters im
  Hauptthread in `-[NSWorkspace iconForContentType:]` → `ISIconManager` (synchrones XPC),
  weil der Symboldienst des Systems (`iconservicesagent`) auf der paravirtualisierten Grafik
  in Metal abstürzt (`MTLReportFailure` in `RenderBox`); Spotlight und Dock stürzen daneben
  ab. Das ist sehr wahrscheinlich derselbe „Hänger beim ersten Ereignisdurchlauf“ und eine
  Eigenheit des Runners, keines Kunden-Macs. Der Starttest des Release-Laufs fährt den
  Intel-Mac deshalb ohne Bildschirm (`auslieferung.md`); Fenster und Metal-Ansicht auf Intel
  belegt nur ein echtes Gerät; die Rückmeldung des Kunden zu 0.5.2 steht unten.

  **Rückmeldung 05.10.2026, 0.5.2 auf einem zweiten Mac desselben Kunden:** Das Beenden nach
  dem Start ist weg. Gestartet hat die App aber erst nach `sudo codesign --force --deep --sign -`,
  danach stand sie zunächst nur im Dock und kam dann. Beide Macs des Kunden sind **Intel-Macs mit
  macOS 26**; im Büro stand die App eine halbe Stunde, ohne zu starten. Damit ist der erste Verdacht
  (Gatekeepers lange Erstprüfung der notarisierten App) widerlegt: Auf echten Intel-Macs startet das
  mit Developer ID signierte Paket nicht, ad hoc signiert schon. Nie geprüft ist genau dieser Fall:
  Der Intel-Starttest der Releaseakte läuft ohne Bildschirm (`--offscreen`, also ohne
  Cocoa-Plattform und ohne 3D-Ansicht, `"renderer": {"present": false}` im Tag-Lauf
  37266459831). Signiert wurde bis 0.5.3 mit Hardened Runtime und ohne Entitlements
  (`build.yml`, Job `macos-app-sign`, Schritt „App mit Developer-ID signieren und Schlüssel
  wieder sperren“); was die Ad-hoc-Signatur davon aufhob (ausführbarer
  Schreibspeicher für libffi-Rückrufe von wgpu und ctypes auf x86_64, Bibliotheksprüfung), war
  ungemessen. Erfragt waren die Terminalausgabe des direkten Starts, `codesign --verify --deep
  --strict` am installierten Paket, Absturzberichte und die genaue macOS-Version; die Antworten
  stehen unter dem 06.10. Der Messweg in `.claude/.state/mac-start-2026-10-05/` misst Zeiten und
  sichert Protokolle.

  **Gemessen am 05.10.2026 abends (Läufe 37361577881 und 37362456615, Wegwerfzweig):** Das
  veröffentlichte 0.5.2 startet über LaunchServices mit Quarantäne auf beiden Runnern
  (Intel offscreen, ARM mit Fenster und 3D-Ansicht) in rund 30 s bis zum Fenster, Developer-ID-
  wie ad-hoc-signiert gleich; Gatekeeper hält am Runner nichts auf. Ein verschiebbares
  Python 3.14.8 mit cffi 2.1.1 und wgpu 0.32.0, ad hoc mit Hardened Runtime ohne Entitlements
  signiert (`flags=0x10002(adhoc,runtime)`), erzeugte auf dem Intel-Runner cffi- und
  ctypes-Rückrufe; der daraus gezogene Schluss, der Verdacht auf Schreib-und-Ausführ-Speicher sei
  widerlegt, war **falsch**: Am Runner greift dieser Schutz nicht (unten). Messweg:
  `hardened_probe.py` und `mac-hardened-diag.yml` im selben Ordner.

  **Ursache eingegrenzt am 06.10.2026** — belegt an Quelltext und fremden Geräten, am Gerät des
  Kunden offen. Seine Angaben zu 0.5.3 (zu Hause): MacBookPro16,1 (Intel), macOS 26.5 (25F71),
  `codesign --verify --deep --strict` „valid on disk“ — die Installation ist heil. Der direkte
  Start schrieb kein Zeichen, Strg+C wirkte nicht, ein Protokoll gab es nicht. Der Stand schreibt
  sonst beim Aufbau des Hauptfensters `QWidget::setMinimumSize: (/QLabel) Negative sizes (0,-1)`
  auf stderr (`panels.fit_wrapped`; am Runner bei beiden Signaturen, hier mit
  `QT_FORCE_STDERR_LOGGING=1` nachgemessen) — der Prozess stand also früher. Das erste
  `import ctypes` liegt im Paket in PyInstallers Bootstrap (`pyiboot01_bootstrap` →
  `pyimod03_ctypes.install`, 6.22.3), vor Laufzeithaken und `app.py`; ein Hänger dort hinterlässt
  weder Absturzdatei noch Protokoll, wie beim Kunden. Umgehen lässt sich ctypes nicht (Bootstrap,
  `app/core/process.py`, numpy). CPython legt seit
  <https://github.com/python/cpython/issues/128485> beim Laden von `_ctypes` eine libffi-Closure
  an (`_ctypes_mod_exec`); Apples libffi holt dafür auf x86_64 anonymen `PROT_EXEC`-Speicher, den
  die Hardened Runtime ohne `com.apple.security.cs.allow-unsigned-executable-memory` verweigert,
  und der Ausweichweg über Temp-Dateien kreist auf macOS 26 endlos — beschrieben an echten
  Intel-Macs in <https://github.com/andreagrandi/draftomen/issues/905> (26.7.1) und
  <https://github.com/PeonPing/peon-ping/issues/589> (Apples `osascript`, 26.6.2, Stapel
  `ffi_closure_alloc` → `dlmmap` → `open_temp_exec_file_dir`). Ad hoc neu signiert fehlt die
  Hardened Runtime, deshalb lief es; ARM nimmt Apples Trampolintabelle. Am Runner nicht
  nachstellbar: `csrutil status` meldet auf beiden Mac-Runnern „disabled“ (Lauf 37488283777),
  und dort greifen weder der Schutz vor ausführbarem Schreibspeicher noch die
  Bibliotheksprüfung: Das ausgelieferte Developer-ID-Paket startet dort mit Hardened Runtime
  ohne Liste (0.5.2, Lauf 37361577881), und ad hoc signierte Bibliotheken laden unter Hardened
  Runtime (Lauf 37490502237, unten). Dass SIP der Grund ist, ist gefolgert. Widerlegt
  ist eine hängende Online-Prüfung der Zertifikate: Mit stumm verworfenen OCSP-, CRL- und
  Notarisierungsadressen startete das Developer-ID-Paket auf Intel und ARM in 8,5 bis 18,9 s bis
  zu den Profilen (Lauf 37488781413).

  **Korrektur:** `build.yml`, Job `macos-app-sign`, signiert erst tief und dann das Bundle ohne
  `--deep` mit genau dieser Berechtigung, ein Rezept für beide Architekturen, und liest Schlüssel
  und Wert zurück; `test_supply_chain.py` hält den Text (fünfzehn Abwandlungen gegengeprüft,
  darunter auskommentierte Rücklesung, zweite Ausnahme, vertauschte `case`-Zweige). Am
  veröffentlichten 0.5.3 mit dem wörtlich geschnittenen Signierteil, ad hoc statt Developer ID,
  auf Intel und ARM gefahren (Lauf 37530339300): `--verify --deep --strict` grün, Start bis zu den
  Profilen; der geschnittene Rücklesetext bricht ohne Liste und bei `<false/>` mit Exit 1 ab und
  lässt die Liste durch. Die Liste hängt nur am Hauptprogramm, nicht an `Python.framework` und
  `_cffi_backend` (Lauf 37490502237) — dass die ad hoc signierten Bibliotheken dort luden, zeigt,
  dass auch die Bibliotheksprüfung am Runner nicht greift. Developer-ID-Signatur, Zeitstempel,
  Notarisierung und Gatekeeper mit der Liste: Handstart von `build.yml` auf dem Zweig
  `ci/rm-104-signatur` (Lauf 37530876754). **Offen:** der Start auf dem Intel-Mac des Kunden.

  **Gegenprobe am Kundengerät:** `solidon-gegenprobe.sh` signiert die installierte Kopie zweimal ad
  hoc mit `--options runtime` und `com.apple.security.cs.disable-library-validation` (ohne sie
  lehnte die Bibliotheksprüfung die ad hoc signierten Bibliotheken ab), einmal ohne, einmal mit
  `allow-unsigned-executable-memory`. Es hält an, wenn Solidon schon läuft (sonst holte ein Start
  nur ein altes, hängendes nach vorn), startet beide Male mit Zeitmarke, wertet nur neue
  Protokollzeilen, beendet „ohne“ nach drei Minuten mit SIGABRT und sucht im Absturzbericht nach
  `ffi_closure_alloc`/`dlmmap`; der Rückweg zur Ad-hoc-Signatur ohne Hardened Runtime läuft über
  `trap` auch bei Strg+C, TERM und geschlossenem Fenster. Am Runner gefahren (Lauf 37530339333):
  Wächter, normal (dort startet auch „ohne“, Urteil „nicht bestätigt“), nachgestellter Hänger per
  SIGSTOP (Urteil „bestätigt“, Bericht eingesammelt), Abbruch mit Rückweg, Absage auf ARM. Die
  erste Mail vom 06.10. nannte eine Gegenprobe ohne `disable-library-validation` (sie wäre ohne
  Aussage gescheitert), der Nachtrag eine mit, aber ohne Wächter und Stapel — belastbar ist das
  Skript. Changelog: ja — notarisiert mit Hardened Runtime ohne Liste ist jedes Mac-Paket seit
  0.4.1, am Kundengerät belegt 0.5.1 bis 0.5.3.

  Messwege im selben Ordner: `mac_online_check.py` und `mac-online-check.yml`
  (Zertifikatssperre), `mac-entitlement-check.yml` (Signierteil und Rücklesung),
  `solidon-diagnose.sh` und `solidon-gegenprobe.sh` mit `mac-diagnose-skript.yml` (Startdiagnose
  und Gegenprobe für einen Kunden-Mac, samt shellcheck). Die Diagnose hält bei laufendem Solidon
  und bei einer ad hoc neu signierten Kopie an, fragt vor dem harten Beenden, ob ein Fenster zu
  sehen ist, und sammelt nach SIGABRT den Absturzbericht ein — am Intel-Runner kam er an (Lauf
  37530339333). Ob `sample` auf einem Kunden-Mac mit SIP einen Prozess mit Hardened Runtime lesen
  darf, ist offen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-erste-vier-plattform-lauf-seit-dem-06092026-08092026).

<a id="rm-107"></a>

- [ ] **RM-107 — Ubuntu-Workerabbruch mit aktuellem Testbestand zuordnen.** Die verbleibenden
  Qt-Abstürze im Linux-Sammellauf und beim späteren Speicherbereinigen mit heutiger
  Worker-/Widget-Lebensdauer erneut eingrenzen. Abnahme: protokollierte Testreihenfolge pro Worker,
  reproduzierbarer Auslöser und saubere Prozessabschlüsse; getrennte Fensterdateien bleiben bis
  dahin Teil des Prüfverfahrens.

  **Messung 06.10.2026 (Wegwerfzweig, Läufe 37491131058 und 37525358642):** Der Linux-Sammellauf
  der Fenstertests mit vier Arbeitern und Verteilung `load` verlor einen Arbeiter mit „Fatal
  Python error: Aborted“ unmittelbar nach dem bestandenen
  `test_overlay.py::test_dragging_the_window_lets_nothing_lag_behind`; derselbe Lauf mit
  Verteilung `loadfile` blieb bei 99 % stehen. Die Overlay-Datei allein ist auf Ubuntu 20 von 20
  grün, mit und ohne ausdrücklichen Fensterabbau. Der Auslöser hängt also an den Vorgängern im
  selben Arbeiter. Nächster Schritt: die Testfolge des abgestürzten Arbeiters aus seinem
  Protokoll nachstellen und halbieren.

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

  **Was bis zum 28.09.2026 offen blieb:** Die Koordinaten des Endergebnisses unterschieden sich noch in der letzten
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
  Merkmale; dazu `knowledge/parts/shapes.thread_body` mit `math.cos`/`math.sin`
  (seit `27c7a29e9` über `exact_cos`/`exact_sin`; ein Weg in `_WAYS` fehlt),
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
  komponentenweise über `mesh.stable_normals` (`bba2c6ea7`). Neu offen waren drei Wege, alle
  drei erledigt mit Paket A (unten):

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
    (am Code nachgelesen, Stand `fc4fc701c`): 13 Stellen in neun Funktionen von `geom/prepare_ops.py`, in
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
  Review 02.10. (`7f0de659d`): Restposten plattformabhängiger Rechnung neben der neuen Ausrichtung in `app/core/perceive/patterns.py`: `Frame.plane` (`np.linalg.norm` ohne Achse), `Frame.world` und `Frame._facet_radius` (`np.cos`/`np.sin`).

  **Durchsicht 0.5.3 (05.10.2026, `e5f38bf57`):** Das Bohrwerkzeug des Nachbaus
  (`rebuild._drill_tool`) dreht über `lathe.revolve` mit den Ecken aus `units.circle_point`
  statt über `trimesh.creation.revolve`; der Weg `rebuild_drill_tool` steht in `_WAYS` und war
  unter dem Plattformrauschen ohne den Fix rot.

  **Paket A (06.10.2026):** Die drei Wege oben und der Rest aus dem Review vom 02.10. rechnen
  plattformgleich: die Platzierung eines Bausteins (`parts/ops._matrix` über
  `transform.composed`), Teilen (`autosplit`, `symmetry`, `pins`), alle Drehwege von *Merkmal
  drehen* und überhaupt `prepare_ops` und `prepare` (Matrixprodukte, `np.dot`, `einsum`, Normen,
  SVD, Neigungswinkel, Flächennormalen über `stable_normals`), Muster am Zylinder und in der Ebene
  (`perceive.patterns` ganz, `texture_ops`), Skizzenbögen (`sketch_solid`, `sketch.profile`) und
  Senkungen. Neue Wege in `_WAYS`: `slanted_part`, `thread_ridge`, `wrapped_texture`,
  `face_textures`, `sketch_arcs`, `split_seam` und `read_lattices`; fünf davon waren am alten
  Stand rot. Der Wächter leert vor dem stillen und vor dem verrauschten Lauf die Merker der
  Erkennung: Vorher beantwortete der verrauschte Lauf die Erkennung aus dem stillen, und die Naht
  eines umwickelten Musters hing unbemerkt an `math.cos`. Der Teilungskorpus (sieben Modelle) ist
  vorher und nachher bitgleich bis auf ein Teil des Wabenhalters nach dem Stiftschnitt (zwei
  Dreiecke, `pins.py`). Cache-Format 52.

  **Offen nach Paket A:**

  - **Einpassungen in `perceive`:** Achsen aus `eigh`, Kreis und Kugel aus `lstsq`, Ebenen aus
    `svd` und der Löser `least_squares` in `refine.solve`. Entschieden ist ein eigener
    deterministischer Kern (Entscheidung Robert, 06.10.2026): feste Summenfolge,
    Householder-QR und Jacobi-SVD, kompiliert ohne zusammengezogene Multiplikation und
    Addition, mit bitgleichem Rückfall in NumPy. Abnahme: Erkennungskorpus und Laufzeit vorher
    und nachher, `_WAYS` grün auf drei Runnern.
  - **Formen in `knowledge/parts/shapes.py`:** `_slot_outline` rechnet mit `np.cos` und trifft
    Schlüsselloch und Lasche. Jede Änderung an `shapes.py` macht alle 49 Bereichsnachweise
    ungültig (`tools/check_part_ranges.py --all`), deshalb gebündelt mit dem nächsten Posten;
    danach Wege für Umrisse und gedrehte Bohrungen in `_WAYS`.
  - **Potenzen `**` auf Gleitkommazahlen:** 166 Stellen im Kern, 115 davon `** 2`. Pythons `**`
    ruft das `pow` der Plattform, und das rundet nicht immer korrekt: Auf Windows weicht
    `x ** 2` in 1049 von zwei Millionen Werten von `x * x` ab, `x ** 0.5` ebenso oft von
    `math.sqrt`; das Rauschen sieht beides nicht. Weg: Produkte, `math.sqrt` und Kehrwerte
    ganzzahliger Potenzen (`1.0 / 10 ** n`), dazu ein Wächter über den Syntaxbaum, der `**` mit
    Gleitkommaanteil im Kern ablehnt (die Regel steht in `kern.md`). Zuerst `units.plane_axes`:
    Jeder Skizzen- und Merkmalsrahmen hängt daran.
  - **Zwei Drehungen über BLAS**, älter als Paket A und von keinem Weg in `_WAYS` erreicht:
    `geom/hollow.py` (`body.apply_transform(back)` beim Aushöhlen) und `geom/lattice.py`
    (`plug.apply_transform(matrix)`, Drehung aus `units.plane_axes` samt Verschiebung). Weg:
    `transform.moved` und je ein Weg in `_WAYS`.
  - **Das Nachführen bewegter Merkmale** aus der Liste der Durchsicht 0.5.0 ist nicht neu
    geprüft.

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
  Der Taglauf 37266459831 (v0.5.2) ist vollständig grün, alle vier Paketjobs bauen mit
  `python-version: 3.14.8`, alle Releaseakte-Jobs sind grün; v0.5.3 (Taglauf 37409338027) baut
  wieder alle Pakete. **Nachgesehen 07.10.2026:** Die Stückliste im App-Baum des
  Windows-Pakets 0.5.3 (Artefakt `solidon3d-windows-signing-input` des Taglaufs, Prüfsumme
  stimmt) nennt CPython runtime 3.14.8, OpenSSL 3.5.9 und libffi 3.4.4; die mitgelieferte
  `python314.dll` trägt Datei- und Produktversion 3.14.8. Die Releaseakte-Prüfung liest
  dieselbe Stückliste.
  **Offen:** die drei Arbeitsplätze. Deren Installation
  ersetzt `python314.dll` unter jeder laufenden Umgebung und geht nur, wenn keine Sitzung rechnet.
  **Abnahme:** Taglauf oder Vollstart mit allen Paketen grün, die Releaseakte nennt 3.14.8;
  `check_env` meldet auf jedem Arbeitsplatz 3.14.8.

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

  **Offen:** allein die Fensterabnahme beim Release (RM-213); die ausdrückliche
  Zusammenfassung kleiner Felder und die Muster am exakten Körper sind gebaut
  (Teilstand 04.10., `d007ddf50`, in v0.5.2). Keine pauschale Schwellenabsenkung:
  Funktionsbohrungen, Magnettaschen und Beschriftungen bleiben eigenständig.

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
  Fertigungskompensation beim Nachbau ausschalten.

  **P4.0 gebaut** (23.09.2026, `596bcb64`), Stand und Reste unter RM-188. Die
  Vorbereitung für P4.1 ist gemessen (Bericht p40, `s35_candidates.py`): Jede
  gekrümmte Fläche eines umgewandelten Körpers trägt ein Merkmal und lässt sich
  direkt in eine Operation übersetzen. Für die ebene Grundform traf der Quader
  der Stützebenen nur Platten mit Bohrungen (+0,00 % bis +0,59 %), Stufen und
  Absätze brauchen eine Zerlegung in Skizze plus Extrusion je Höhe (Wedge-Lock
  +261 %). Diese Grundform ist seit 04./05.10. gebaut (`_layered`, `_prismatic`,
  Teilstände unten).

  [Bisheriger Befund](ROADMAP-ARCHIV.md#neun-heruntergeladene-modelle-durch-die-ganze-kette-21082026).
  Belege versioniert (05.10.2026): [Bericht p40](konzepte/nachweise-release-0.5.0/reports/p40.md) mit [`s35_candidates.py`](konzepte/nachweise-release-0.5.0/sonden/p40/s35_candidates.py), [zeichnenbau](konzepte/nachweise-release-0.5.0/reports/zeichnenbau.md), [p66](konzepte/nachweise-release-0.5.0/reports/p66.md).

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
  `p12a_vorher.txt`, `p12a_nachher.txt`, `p11b_ab.txt`, `p11e_luecken.txt`). Die
  Fensterabnahme folgte am 04.10. (unten): die acht Fensterschritte, darunter Lochplatte mit
  *Abbrechen* während der Prüfung, Winkel mit Bohrungen in beiden Schenkeln mit Strg+Z nach der
  Übernahme und Stufenplatte mit Senkung Ø 8 ohne Kompensation. Changelog: ja, im vorhandenen Punkt
  zu *Modell nachbauen* ergänzt.

  **Teilstand 04.10.2026:** Fensterabnahme 04.10.2026: Lochplatte mit *Abbrechen* während der Prüfung (Verlauf unverändert) und Vorschlag Quader plus vier Bohrungen; Winkel mit Bohrungen in beiden Schenkeln deckt sich mit dem Original, Übernahme und Strg+Z stellen das Netz her; Stufenplatte mit Senkung Ø 8 ohne Kompensation. Der Wert eines Ausdrucks steht seit `61baf9d2c` ohne Exponent da. Belege `F:\solidon-review-reports\claude-2026-10-04\fensterabnahme\rm022-*\`. Die Zahlenanzeige unter einem Ausdrucksfeld ist behoben, aber am Fenster noch nicht wiederholt (Bildnachweise unter `F:\solidon-review-reports\claude-2026-10-04\fensterabnahme\`).

  **Teilstand 05.10.2026 (Claude): Profilkörper am Netz.** Roberts Besenhalter aus dem Test von
  0.5.2 (Leiste mit Fasen, zwei Klemmringe, Senkbohrungen, 0,68 mm tiefe Schrift auf der
  Rückseite) bekam keinen Vorschlag. `scene/rebuild._prismatic` zieht jetzt den Umriss aller
  Schichten längs der besten Achse und nimmt je Schicht die Luft als Säule weg; was eine Schicht
  mehr hat, wird ein Prisma oder eine Senkbohrung (`_pieces_as_steps`). Querbohrungen und
  umschlossene Quertaschen stehen gefüllt in den Querschnitten und werden am Ende gebohrt oder in
  einem Zug abgezogen (`_cross_pockets`); Schichten gelten nur ohne dickes Stück dazwischen als
  gleich (`_same`). Querschnitte werden über `sketch/traced.py` Strecken, Bögen und Kreise, ohne
  gerade Wände zu kippen. Die Formprüfung schließt Zellen neben einer ebenen Facette über
  √(h² + r²) ein (`geom/difference._FacetCover`); eine Nadel der Dreiecksteilung lässt eine Ebene
  nicht mehr unerklärt (`_uncovered`). Am Besenhalter: Vorschlag aus 21 Schritten (zehn
  Extrusionen, neun Abzüge, zwei Senkbohrungen) in 247 s angenommen, gültig, dicht, Topologie aller
  drei Schalen wie die Quelle, Volumen 0,32 %, Flächenabstand höchstens 0,090 mm. Korpus
  (`F:\3D Dateien` und `tests/data`, 267 Körper) vor den letzten Schritten: 57 von 227
  Nicht-Freiform-Körpern angenommen (vorher 39), Freiform keiner. Findet der Nachbau für eine
  Form keinen Aufbau, sagt er es (`71f13266c`). **Offen:** der Korpuslauf über
  diesen Stand, fünf Teile über 600 s (darunter `pista+biglie.3mf`), die Fensterabnahme beim
  Release. Tests: `test_rebuild.py` (Wandhalter, Gravur, Schichtvergleich, Tasche),
  `test_sketch_traced.py`, `test_difference.py::test_a_cell_beside_a_facet_is_bounded_without_dividing`.

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
  sondern in seiner Lage im Raum. Das war [RM-210](ROADMAP-ARCHIV.md#rm-210) (archiviert 04.10.).

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

  **Das §31-Ziel bleibt offen.** Die Schale stand am 22.09. bei 12,6 Sekunden (Stand 03.10.
  unten: 18,59–20,16 s unter Last), verlangt sind unter fünf.
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
  `f8a42f602` (02.10.): Fortschritt und begrenzte Stapelgröße der Formerkennung.

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
  (`_canonical_vertices`, seit `0fdd18d19` `features.vertex_rank`); was bleibt, sind die 372
  Kegel-, 352 Ring- und 325 Kugelfits.

  Merkmale und IDs an sieben Körpern zeichengleich — die beiden Referenzfälle, `plate_holes`,
  `post_with_fillet`, `plate_countersunk`, `plate_chamfer_and_taper` und `torus_ring`. Nachweis:
  vier Fälle in `tests/test_curvature_split_components.py` und `tests/test_features.py`, vier
  Gegenproben einzeln rot (ohne die Maske, die Regel fest verdrahtet statt über den Parameter,
  mit umgedrehter Fleckenreihenfolge, ohne den leeren Rückweg). Keine Schranke wurde
  aufgeweicht.

  **Stand 12.09.2026, lineare Fits — das Ziel ist damit nicht erreicht, sondern angekommen:** 1,004 s sind vier Millisekunden
  über der Sekunde, und das gilt für den **synthetischen** Körper auf dieser Maschine. Der
  organische 197k-Kundenfall stand am 10.09.2026 bei 1,52 s; um denselben Anteil schneller wären
  es 1,09. Was noch darin steckt, ist gemessen: 55 Prozent der verbliebenen Sekunde sind die
  Einpassungen selbst (`fit_torus` 0,33 s, `fit_cone` 0,21, `fit_sphere` 0,10 — über 1 650
  Flecken mit im Mittel sechs Dreiecken), 14 Prozent `body.facets` von trimesh. Beide sind keine
  verschenkte Arbeit: Die Zahl der abgelehnten Kugel- und Ringkandidaten **ist** die
  Freiformentscheidung (`unpublished_round_shapes`), sie lässt sich nicht überspringen. Wer
  weiter will, verarbeitet die Flecken im Stapel statt einzeln — ein Umbau der drei `fit_*`,
  kein Feilen.

  **Zur Entscheidung für Robert:** ein anderer Hebel als der gebaute Stapel (`c3636d210`, 0.5.1;
  an der Freiform am 03.10. 7,17–7,22 s unter Last), oder §31 je Körperart neu fassen. Das Ziel
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
  **Ziel neu gefasst (Robert, 06.10.2026, Bauplan §31):** mechanische Körper unter 1 s,
  organische unter 2 s am Referenzrechner der Rechenprobe; offen ist die Messung am
  neuen Ziel.

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

  **Im laufenden vollständigen Auftrag ebenfalls abzuarbeiten** (Bausteine, Abläufe,
  funktionale Gruppen und Projektmaße an Puppenhaus und Schrank sind am 04.10. gebaut,
  Teilstände unten; dazu `tools/file_acceptance.py`):

  - Native Einzeldateiabnahme aller 187 Fälle einschließlich aller 29
    Drillholder-Bohrungen: Import, Erkennung, Maßänderung, Vorschau, Ergebnis,
    Undo/Redo und je eigener Bildnachweis. Kernläufe ersetzen diese Abnahme nicht.
  - Einheitliche abschließende Leistungsreihe, erstes sichtbares Modell und
    getrennte Stufenmessung.
  - Mehrdateien und Plattengruppen (Stand am 06.10. nicht geprüft).
  - Native Dichtnutabnahme und die Fensterabnahmen der neuen Bausteine, Abläufe und
    Gruppen beim Release (RM-213).

  Der Punkt verweist auf das gitignorierte `ui-audit/`, das es nur auf einer Maschine gibt —
  Belege ins Repository holen oder als Aussage in den Punkt.

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

  **Teilstand 04.10.2026 (Claude, R3 `claude/rm184-gruppen`):** Funktionale Gruppen aus dem Audit
  (§7) werden erkannt und stehen im Objektbaum als Gruppe — Kammer, Nut, Kanal, Bajonett, Rastung —;
  Kammern und Verschlüsse ändern sich als Ganzes (Innenmaß, Tiefe, Spiel, Drehweg), Fenster, Menü
  und Operation fragen dieselbe Prüfung. Zwei Scheinrastungen (Mini-Golf-Schläger, Besenhalter) sind
  weg, im Korpus (226 Dateien) ändert sich sonst nichts. Projektmaße steuern alle abhängigen Teile:
  feste Zahlen lassen sich mit einem Klick an ein Projektmaß binden (§4, §5).
  `tools/file_acceptance.py` fährt die native Einzeldateiabnahme (Import, Erkennung, Maßänderung,
  Vorschau, Übernehmen, Undo, Redo, Bild je Schritt; Aufruf mit `--manifest …\manifest.json`); der
  echte Lauf über die 187 Fälle am Fenster steht aus. Tor 23 887 bestanden. Beleg und Befunde
  außerhalb des Auftrags (Hänger beim Abräumen von Qt-Objekten im Befundarbeiter; *Merkmal ändern*
  an Eckwülsten bietet an, was die Operation absagt) unter
  `F:\solidon-review-reports\claude-2026-10-04\rm184-gruppen\`.

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
  [RM-183](ROADMAP-ARCHIV.md#rm-183) und [RM-187](#rm-187). Teilstände erscheinen in einzelnen
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
  | P4.1–P4.3 Nachbau | läuft: Stufen und Profilkörper am Netz, unter RM-022 | `2323082b2`, `84a0d496e`, `800f9dfb4` |
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
    Etikett stehen unter [RM-197](ROADMAP-ARCHIV.md#rm-197), [RM-199](ROADMAP-ARCHIV.md#rm-199) und
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
    ([Bericht p40](konzepte/nachweise-release-0.5.0/reports/p40.md)) und die Paketprobe, dass die
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
    weiter still über OpenCASCADE, wo `sketch_loft_cut` fragt. Bauplan §30.1
    nennt die drei Schnitte seit 06.10.2026 (Entscheidung Robert).
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
  * **P4.1–P4.3** — unter [RM-022](#rm-022); nächster Schritt: der Korpuslauf über
    den Stand vom 05.10. und die fünf Teile über 600 s.
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
    §8, dazu die Berichte [zeichnenbau](konzepte/nachweise-release-0.5.0/reports/zeichnenbau.md)
    („Vorschlag Etappe 2“) und [p66](konzepte/nachweise-release-0.5.0/reports/p66.md) („Für den
    Zeichnen-Umbau“). Nächster Schritt: Z2.
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
  frischem Bereichsnachweis aller Bausteine (heute 49) und den Kundenwegen am echten
  Fenster ([RM-213](#rm-213)). Den Punkt schließt P5.3: der installierte Umfang
  auf Windows, macOS und Linux (neue OCP-Aufrufe, gewählte Bibliotheken,
  Lizenzen, Datenrundreise, Fehlermeldungen); die Handlungsmatrizen des Konzepts;
  alle Bausteine (heute 49) mit dokumentierter Anwendbarkeit; korrekte Maße und
  Referenzen nach Änderung, Cache, Undo und Wiederöffnung; die zehn Kundenwege
  aus der [Recherche](konzepte/recherche-cad-paritaet-2026-09.md) §4.3 und die
  Zusatzwege aus Konzept §§13.9 und 13.11 und Resin-Konzept §9; jede geltende
  Anforderung aus P0.8 mit Nachweis und die Erstnutzerprüfung. Keine stille
  Formänderung bei der Erkennung; die Nicht-Ziele aus Konzept §15 bleiben
  ausgenommen.
  Die tragenden Belege aus der Durchsicht 0.5.0 sind versioniert (05.10.2026): [p40](konzepte/nachweise-release-0.5.0/reports/p40.md), [zeichnenbau](konzepte/nachweise-release-0.5.0/reports/zeichnenbau.md), [p66](konzepte/nachweise-release-0.5.0/reports/p66.md), [p7step](konzepte/nachweise-release-0.5.0/reports/p7step.md).

  **Teilstand 04.10.2026 (Zwillingsbrüche aus RM-226, nach 0.5.2):** Drei Stellen, an denen Netz und
  exakter Körper verschieden erkennen, sind gemessen und noch nicht gebaut. (1) Kegelstücke
  desselben Trägers (gleiche Achse, Spitze und Öffnung) sollen wie Ringe ein Merkmal sein; am
  exakten Kern fehlt das Gegenstück zu `_joined_tori`, das Netz legt sie schon zusammen. (2) Die
  Mündung der Bohrung Ø 9 am Teppichclip (zweiter Körper) ist eine Freiformfläche: Das Netz liest
  sie als Kegel, der exakte Kern nicht, *Merkmal verdoppeln* lehnt dort mit `NO_OWN_BODY` ab. (3) Am
  Netzzwilling der STEP-Vernetzung von gs-100 trennt die Erkennung über Krümmungssprünge: Eckkegel
  verlieren ihre Randdreiecke, die Kehle hängt mit tangentialen Freiformflächen zusammen; Wege: an
  den Flächengrenzen trennen, die die Vernetzung mitträgt (`face_sources`), oder die
  Krümmungstrennung schärfen. Beleg:
  `F:\solidon-review-reports\claude-2026-10-04\kopie-schraeg\bericht.md` (Vierter Nachtrag).

<a id="rm-191"></a>

- [~] **RM-191 — PrusaSlicer braucht für dieselbe Übergabe länger als die Orca-Familie.**
  Ursprünglicher Befund: ein Drittel mehr Material. Gemessen am 19.09.2026 an den neun Platten von Roberts Regal
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

  **Messgrundlage veraltet (06.10.2026):** Seit RM-281 C (`44ab90965`) bekommt PrusaSlicer
  sein Herstellerbündel und darüber nur die Abweichung, nicht mehr dieselben Solidon-Werte wie
  oben. Ob 1,19× heute noch gilt, ist ungemessen; zuerst mit dem Herstellerbündel neu messen,
  dann entscheidet Robert über Vorgaben.

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
  `FREEFORM_PIECE_SHARE`)? Über 65 Prozent (`FREEFORM_SKIN_SHARE`) ist der Körper eine
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
  **Ziel neu gefasst (Robert, 06.10.2026, Bauplan §31):** Der Drache ist ein organischer
  Körper und misst sich an unter 2 s am Referenzrechner.

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
  Clipper2 über Cython (BSL-1.0, seit RM-486 im Einsatz) oder eine
  eigene Offsetfunktion im vorhandenen `_chain.pyx`. An Gittern (Kumiko) kostet
  die genaue Nachfrage der Breite so viel wie vorher (12,7 → 11,1 s), aber mit
  richtigen Zahlen. Die Marke `slice_medium_hollow` bleibt Regressionswächter.

  **Stand laut Register bis 29.09.2026:** `slice_body` an der Hohlkugel 40 % schneller
  (`546eff16`: Stapelung, Inselzertifikat, Säulen auf Arbeitern, direkte Ringe), hochgerechnet
  rund 0,65 s auf der Referenzmaschine — 300 ms nicht erreicht; der Rest ist die Breitensuche mit
  sieben Öffnungen je Schicht. Robert gibt C++ frei (23.09.): native Breitensuche als eigener
  Bauauftrag; womit (eigene Mitre-Offsetfunktion in `_chain.pyx` oder Clipper2 über Cython),
  entscheidet Robert.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** Die gerichtete
  Clipper-Gesamtvereinigung aus RM-486 kostete an der Hohlkugel 57–72 s; jetzt steigen die Säulen
  unabhängig ab (höchstens sechs Arbeiter), Differenz nur bei belegtem Kontakt. Dazu gerichtete
  Verschachtelung, `_chain.ring_nesting` und die gemerkte Absage des Volumenkerns. Schichtkennzahlen
  an Screen-Cover, CC2-Box und eigenem Beispiel bitgleich, Stützraum der Hohlkugel 73 360,800 mm³,
  282 Schicht- und Konturfälle grün. Im Messfenster 14:53 mit angehaltener eigener Arbeit:
  1,20/1,27/1,41 s statt 0,3 s. Verworfen: Mitre-Öffnung über den Clipperkern (26 andere
  Breitenentscheidungen, nicht schneller), Zertifikate ohne belastbaren Vorteil. Beleg:
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
  Die Umsetzung vom 30.09. (`question_reference`) steht seit `8b102ccc2` (02.10.) in main und in v0.5.2.

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
  **Offen:** allein die Fensterabnahme beim Release (RM-213); Code und Tor mit `d907d6036`
  in v0.5.2.

<a id="rm-230"></a>

- [ ] **RM-230 — Variable Verrundung und Formschräge: fünf Grenzen, die der Kunde merkt.**
  Aus dem Bau von P6.1/P6.4 (Bericht p6a, „Grenzen — bewusst offen"): Der Anfang
  einer variablen Verrundung auf einem Ring ist eine Konvention (links, vorn,
  unten) und nicht wählbar — dafür braucht es den Maßeditor im Bild (P0.3/P5.1).
  Gemischte Ecken (zweite Kante mit anderem Radius) sagen Netz und exakter Kern
  gleich mit Satz ab (`check_varying_radius`, Test
  `test_variable_fillet.py::test_exact_refuses_what_the_mesh_refuses`); eine Ecke aus
  Außen- und Innenkante prüft nur das Netz. Zwischenstellen als Text
  („50:4 80:3") sind nicht an Projektparameter bindbar, Anfangs- und Endradius
  schon. Die Formschräge an allen Wänden von `build_tray_v3.step` sagt
  OpenCASCADE ab (einzelne Wände gehen); gekrümmte Flächen außer Zylindern in
  Zugrichtung sind nicht anstellbar. Die Netzschräge ist am einfachen Quader
  2,3-mal langsamer als der alte Weg (0,41 gegen 0,18 s, weit unter §31). Weg:
  die Ecke aus Außen- und Innenkante am exakten Kern prüfen; Zwischenstellen als Liste von
  Maßausdrücken (§13); die Formschräge vieler Wände in Gruppen rechnen. Der
  wählbare Anfang gehört zu P5.1. Abnahme: je Grenze entweder gebaut oder mit
  Satz und Weg in der Oberfläche und im Handbuch benannt.

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
  Nachprüfung am Stand `3fd3b1ace` (nach `eab5f4f47`): unvollständig. `drill_hole` hält weiter mit `object_id=None` und `correct_input`/`cancel`, auch im Prüfbericht; ein kaputter Körper als Werkzeug rechnet still (`subtract_objects [gut, kaputt]` → 118,5 mm³ ohne Befund, `boolean.py:412–414`); erfüllt ist nur der Fall mit dem kaputten Körper als erstem Eingang. Der neue generelle Halt kehrt die hier dokumentierte Entscheidung um (RM-382). Belege `review-3fd3b1ace.md`, Sonden `r_rm253_*.txt`.

  **Die beiden Nachprüfungen sind durch [RM-382](ROADMAP-ARCHIV.md#rm-382) erledigt
  (`6d395169c`, v0.5.2):** `drill_hole` reicht `object_ids` durch, ein Schritt abseits der
  selbstkreuzenden Schale rechnet mit Warnung, am Treffer hält er mit Kennung, und ein kaputter
  Szenenkörper als Werkzeug hält (`test_a_crossing_scene_tool_stops_a_difference_with_its_own_id`).
  **Am Original weiter (Sonde am 06.10.2026, Kopie mit abgefangener Messboolescher):**
  `hole_1` mit `cone_5` gekippt meldet `rotate_feature.no_longer_through` und `bore.over_the_edge`;
  `hole_1`/`hole_3` versetzt `move_feature.no_longer_through`; Verdoppeln bleibt an allen vier
  Bohrungen ohne Wirkung (`boolean.without_effect`, `duplicate_feature.feature_lost`);
  `hole_2`/`hole_4` gekippt nehmen um 53 bzw. 104 mm³ **zu**; `hole_11` hält am Treffer der
  kaputten Schale. Die Abtragsmessung „vor den Mündungen“ scheitert, weil die Messdifferenz der
  Sonde selbst die kaputte Schale trifft — die ursprüngliche Abnahme ist so weder erfüllt noch
  messbar; die Sonde braucht eine Messung ohne Differenz gegen die kaputte Schale.

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
  übernommenen Vorschlägen; er hängt an der Entscheidung zur Kanalmündung
  ([RM-527](#rm-527)). Die Slicerzahlen oben sind vor dem Deckenumbau `bcf98c1b6`
  (0.5.3) gemessen. Die Frage zum Brim je Teil beim Export ist mit
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

  **Offen:** die Gesamtabnahme jedes Modell × jeder Slicer und die Zeitschätzung
  (ElegooSlicer −18 % an der Seitenablage, Stützmenge an gewölbten Flächen drei- bis
  zwölfmal unterschätzt, ihre Rechenzeit). Paket 3 (Mindestschichtzeit, Keilspitzen,
  Stützbedarf gegen das Urteil des Herstellers, Brückenregel, Inseln an Schrauben) ist am
  04.10. abgenommen (`a69a2d2d0`, Teilstand unten); die Reste der Slicer-Matrix führt
  [RM-312](#rm-312).

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

  **Teilstand 04.10.2026 (Claude, G1 `claude/rm281-paket3`):** Paket 3 am echten Slicer (04.10.2026,
  `claude/rm281-paket3`): **Mindestschichtzeit und Keilspitzen** — der alte Vorschlag „15 s je
  Schicht“ verlängerte den Golfschlägerkopf in ElegooSlicer um 111 %, in PrusaSlicer um 87 %, ohne
  die Spitzenschichten zu ändern; seit `3018613e6` (v0.5.1) kommt er nur ohne Mindestzeit im Profil
  und heute an keinem der drei. **Inseln an Schrauben** — die Insel der liegenden Schraube „Vida“
  war eine verlorene Schnittfläche, behoben mit `206dca76d` (RM-308); heute kein Stützvorschlag, die
  Slicer stützen dort 0,1–0,8 m. **Stützbedarf gegen das Urteil des Herstellers** — in 312 von 340
  Matrixläufen mit Solidons Stützbedarf stützt auch der Slicer; die 28 übrigen sind eingeordnet
  (unverteilte Platte, Decken unter 1,1 mm, Slicer-Eigenheiten, Kobra-2-Profil ohne Brückenstütze),
  keine Schwelle geändert. **Brückenregel** — 15 mm ist milder als jedes Profil außer Kobra 2 und
  bleibt; behoben, dass eine lange Brücke über dem Modell „nur vom Bett“ bekam (`131edad7f`,
  Nachtrag `6a7cc361c`: nur die Brücke über dem offenen Stück zählt): Wedge-Lock übernommen vorher
  0,0/0,0/1,1/0,0/0,0 m Stütze in Creality Print, Kobra 2, Elegoo, Prusa, Cura, nachher
  2,9/3,0/2,6/1,8/1,8 m; die Waschschüssel hält ihren Kanal in Elegoo und Cura frei (0,0 m). Beim
  Prüfen behoben: Absturz der Schichtanalyse am Wizard Tower (`8ca9b136b`, nur nach v0.5.1). **Reste
  D** — Startcode des SV06 seit RM-482 (`c0e7eab7d`), im Druck nur noch `M204 S500`; Tempi des MINI+
  seit `884b88b0a` (v0.5.1) aus „0.20mm SPEED @MINIIS 0.4“, Pilz in PrusaSlicer 31,2 → 25,5 min,
  Cura 34,5 → 25,7 min. Das Matrixwerkzeug rechnet mit dem Code des Druckdialogs und meldet
  Stützvorschläge ohne Stütze und abweichende Druckzeiten. Tests
  `test_a_crossing_mitre_needle_is_measured_instead_of_breaking_the_analysis`,
  `test_a_long_bridge_over_the_model_lets_its_supports_start_there`,
  `test_a_long_bridge_counts_on_the_model_only_where_it_hangs_there`,
  `test_the_channel_space_leaves_a_column_on_the_model_free`,
  `test_a_part_too_tall_for_the_printer_does_not_fit_instead_of_failing`. Belege
  `F:\solidon-review-reports\claude-2026-10-04\rm281-paket3\`; Konzept Herstellerprofil, Abschnitt
  7.

  **Teilstand 04.10.2026 (Nachtrag, G1):** Rand und Drehung sind mit RM-312 zu einer Lösung vereint:
  `build_area.rim_of` (Auto-Brim, Stützfuß, Skirt) fragen Prüfung und Druckrat; gedreht wird nur,
  was ungedreht nicht passt, Creality Print bekommt zusätzlich die Randprüfung. Echte Läufe:
  Waschschüssel an OrcaSlicer/Kobra 2 schräg gerechnet, an Creality Print/K1 vorher abgesagt; Rack
  am Centauri Carbon 2 mit Auto-Brim-Warnung; garden-hose-holder am MINI mit Stützfußwarnung. Die
  Zeitgegenprobe rechnet Stützen mit (Archiv RM-465). Nach 0.5.2 offen: ElegooSlicer −18 % an der
  Seitenablage (Füllanker und senkrechte Schalen), Stützmenge an gewölbten Flächen drei- bis
  zwölfmal unterschätzt, Rechenzeit der Zeitschätzung. Belege unter
  `F:\solidon-review-reports\claude-2026-10-04\rm281-paket3\`.

<a id="rm-259"></a>

- [~] **RM-259 — Eine Mündungsrundung in einer gekrümmten Fläche reist nicht mit ihrer
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
  Der Drehweg liegt als
  `konzepte/nachweise-release-0.5.1/sonden/rest-muendung/prepare_ops_mit_drehen_heute.patch`
  bei (8 Hunks, gegen den Stand vom 27.09. mit `2e496575b` und `202d5133a`); am 06.10.2026
  greift er nicht mehr (`git apply --check`: „patch does not apply“ an
  `app/core/geom/prepare_ops.py`) und muss vor Gebrauch auf den heutigen Stand übertragen
  werden. Ohne Lippe kippt die Tasche
  seit `2e496575b` an beiden Kernen offen. Die schräg **gesetzte** Tasche aus dem Baustein
  zeigt dieselbe Lücke von der anderen Seite ([RM-277](ROADMAP-ARCHIV.md#rm-277)). Abnahme unverändert.

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
  (a) steht mit `a45730c79` und `686abf9e6` in main und in v0.5.2. Dabei gefunden:
  `test_the_workers_of_the_window_use_the_helper` hing von der Reihenfolge ab
  ([RM-380](ROADMAP-ARCHIV.md#rm-380)). Beleg `F:\solidon-review-reports\register-geometrie.md`.
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
  Integriert in v0.5.2 (`c414921a7`); native Prozess-/Plattform-/Paket-/Releaseabnahmen
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
  Review 02.10. (`7f0de659d`): Der neue Bericht `rm298-poolnachweise-2026-10-02.md` (Z. 22, 26, 61) erklärt (a) für geschlossen, ohne zu sagen, dass nur `shutdown` die Sperre nach einem späten Prozessende aufhebt (RM-384). Erledigt: Der Bericht trägt seither den RM384-Anschlussnachtrag.

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
  Integriert in v0.5.2 (`1c3cb1d99`). Wirklicher Paketlauf, langsamer macOS-Runner und native
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
  Integriert in v0.5.2 (`5230384ff`).
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
  erhalten. Integriert in v0.5.2 (`98432d244`); native Qt-/Fenster-/Abbruchlatenz bleibt
  Releaseabnahme.
  B01-Export-/Sliceranschlüsse sind separat abgestimmt; RM298 bleibt `[~]`.

  **Teilstand 06.10.2026, (d), Elternende unter Last:** Der Wächter des
  rechnenden Helfers fiel im Tor neben Agenten-Suite und Toren in einem von drei
  Läufen. Kein Zeitfenster im Jobobjekt: Das Ende war in allen 65 gebundenen
  Sondenläufen eingeleitet, sobald der Elternprozess signalisiert war; nur der
  Abschluss dauerte unter Volllast in `BELOW_NORMAL` bis 19,5 s, in 21 von 23
  Läufen über 9 s (normale Klasse unter 0,8 s, ruhige Maschine 1 bis 2 ms).
  Der Test sichert jetzt das eingeleitete Ende zu (`IsProcessDeleting`), der
  Abbau hebt vorher die Klasse, Meldedateien werden bis zur Frist gelesen.
  Verschränkt im selben Fenster: alt 6 von 8 rot, neu 8 von 8 grün; ohne
  inneres Jobobjekt bleibt der neue Test an derselben Zusicherung rot. Das löst
  die Zusage „innerhalb der Abbaufrist signalisiert“ aus
  [rm298-lifecycle-2026-10-02.md](konzepte/nachweise-release-0.5.1/reports/rm298-lifecycle-2026-10-02.md)
  ab. [Sonde und Läufe](konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/elternende.py),
  Begründung `regel-tests.md`. RM298 bleibt `[~]`.

<a id="rm-307"></a>

- [~] **RM-307 — Auto Split: Reste aus dem Review der Vorauswahl.** Aus dem Release 0.5.1 (Fix `autosplit-lagen-051`,
  `konzepte/nachweise-release-0.5.1/reports/review-autosplit-lagen.md`). Seit 0.5.1 hält die
  Vorauswahl für Auto Split ihren letzten Platz für die billigste stehende Lage frei, wenn
  keine der drei vorderen steht. (a) Steht eine der vorderen, aber teuer, bleibt ihr Preis zu
  hoch (ma-mi-ya mit Stiften an A 1 679 711 statt 63 010 mm³; an 3 von 114 Modellen fielen
  Nahtentscheidungen auf solchen Zahlen, jedes Mal mit gleich viel oder weniger Stütze als
  vorher). (b) Für das schnellere `_contact` fehlt ein bleibender Gegentest gegen eine
  Auswahl nach Brute Force an den Toleranzrändern (belegt ist die Gleichheit nur in der
  Review-Sonde) — erledigt:
  `tests/test_orientation_search.py::test_contact_selection_matches_brute_force_at_both_tolerance_edges`
  (`70f7f47cd`, v0.5.2). (c) Ohne übersetzten Schnittkern (`_chain`) braucht der Leistungstest
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

<a id="rm-385"></a>

- [~] **RM-385 — Reste aus dem Review von `eab5f4f47` und `a45730c79`.**
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

  **Stand 06.10.2026:** Mit `6d395169c` (v0.5.2) erledigt sind der erste und zweite
  Spiegelstrich und die Unterlagen bis auf §17.2: Die exakte Boolesche nennt wieder Grund und
  Weg (`BOOLEAN_REFUSED_DETAIL` in `app/core/brep/edit.py`), der exakte Kern meldet
  `boolean.parts_united` (`geom/prepare_ops.py`), Regel, Karten und Begründungen sind
  nachgezogen, die drei Testdoppel sind entfernt, und ein Wächter in `tests/test_toolchain.py`
  verhindert neue. **Offen:** der Archivsatz zur Weltverschiebung 1e7 (aus `0eccbe952`, ohne
  Registerpunkt) — belegen oder streichen; `tests/test_geometry_review_regressions.py:607` ist
  unverändert, und ob die Zusicherung nach dem Umbau wieder Sinn hat (der Befund kann seit
  `6d395169c` wieder auftreten), ist nicht geprüft; dass §17.2 den Halt nennt, geht nur mit
  Ansage an den Bauplan.

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
  mit den wirksamen Einstellungen, Cacheschlüssel und Abbruch (32 Fälle). Belege unter
  `F:\solidon-review-reports\codex-2026-10-03\`:
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

<a id="rm-425"></a>

- [~] **RM-425 — Überlappende gespiegelte Formzüge verlieren ihre Symmetrie.**
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

  **Stand 06.10.2026:** Fehlerfall S01 am HEAD `fc4fc701c` nachgestellt (Kugel R20, 1280
  Dreiecke, Zug aus dem Radius-16-Nachlauf, `apply_strokes`): Spiegelabweichung und
  Ebenenaustritt 0,000 mm; derselbe Aufruf am Stand `48106c57a` 0,341/0,171 mm — reproduziert
  und behoben. Die Ursache `_strongest_copy` ist mit `f77576d19`
  ([RM-428](ROADMAP-ARCHIV.md#rm-428)) entfallen. Die bleibenden Tests prüfen zwei Körper (Kugel,
  Platte), alle Pinsel, Achse X und Züge ohne schräge Richtung. **Offen:** S01 als bleibender
  Test, ein dritter Körper, die Achsen Y und Z, eine verschobene Spiegelmitte und alte
  gespeicherte Züge.

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

<a id="rm-525"></a>

- [ ] **RM-525 — Anycubic Slicer Next über alle Drucker und den Modellkorpus verifizieren.** Auftrag
  Robert vom 05.10.2026: den Slicer vollständig aufnehmen und über alle Modelle mit allen 39
  Druckern prüfen. Der erste Lauf (Plan `drucker`, Treiber unter
  `.claude/.state/anycubic-2026-10-05/`) rechnete Wedge-Lock und die Minigolf-Platte als STL an
  allen 39 Druckern, die Waschschüssel an 10; die Auswertung fand B1 bis B7
  (`F:\solidon-review-reports\claude-2026-10-05\anycubic-matrix\auswertung.md`). B1 bis B6
  sind für 0.5.3 behoben und an 13 gezielten Fällen im Slicer belegt, B2 gilt für die ganze
  Orca-Familie.
  **Offen:** die Waschschüssel an den übrigen 29 Druckern, die Minigolf-Platte als 3MF (der Pfad
  im Treiber zeigte auf einen gelöschten Ordner), der Plan `modelle` über den Korpus an Kobra S1
  und S1 Max. Vorher am Matrixwerkzeug den Blockleser für `; CONFIG_BLOCK_START = begin` und
  die Marke „Stützvorschlag ohne Stütze“ nach Volumen statt Metern (B7).
  **Abnahme:** jede Kombination geschnitten oder mit Absage samt Ausweg, kein Druck neben dem
  Bett, Block gleich Herstellerkette außer ausgewiesenen Abweichungen, kein Fehlalarm.

<a id="rm-527"></a>

- [~] **RM-527 — An der Kanalmündung entscheidet die Sperre gegen eine verlangte Stütze.** Seit
  0.5.3 ist eine Decke als Ganzes Kanal oder Brücke (`slice/analysis.py`, `_Ceilings`), und
  die Kanalsperre nimmt keiner Brücke mehr die Stütze. An der Waschschüssel im Raster des
  Centauri Carbon 2 spannt aber ein offenes Stück an der Mündung des Wasserkanals 16,3 mm und
  bekommt mit Sperre keine Stütze (ohne Sperre 0,47 m), obwohl der Rat dort „überall“
  verlangt. Jede Freigabe ließe Stütze in die Kanalmündung. **Entscheidung Robert:** Mündung
  frei halten oder die Brücke stützen. Daneben: Gewölbe knapp über 30 mm (Gewürzbehälter
  34 mm) liegen mit ihrer Flächenmehrheit nahe der Hälfte; im Korpus kippt keines, in einem
  anderen Raster könnte es. Belege lokal unter
  `F:\solidon-review-reports\claude-2026-10-05\release-0.5.3\fix-kanalsperre.md`.
  **Abnahme:** nach der Entscheidung die Waschschüssel in Anycubic, Elegoo und Orca mit freiem
  Kanal und der entschiedenen Mündung, der Korpus ohne neue Kanalstücke.
  **Entschieden (Robert, 06.10.2026):** Die Mündung bleibt frei, wie Solidon es seit 0.5.3
  hält; offen ist nur die Abnahme.

<a id="rm-539"></a>

- [ ] **RM-539 — Ein Baustein mit Trägeraufbau, auf der Innenseite gesetzt, baut nach außen ohne
  Befund.** Die Kabeldurchführung legt ihre Mündung an die angeklickte Fläche, die als
  Außenseite gilt, und baut den Klemmblock dahinter (`parts/structure.py`,
  `cable_relief_support` als `host_add`). Im Gehäuse-Beispiel stand sie auf der Oberseite des
  Bodens: Der Block hing 5,25 mm unter dem Bett und über zwei Ränder (im Beispiel behoben,
  `tools/make_examples.py`). Setzt ein Kunde sie so, sagt es nur `arrange.below_bed` als
  Hinweis, dessen Handlung *Auf das Bett setzen* das Gehäuse auf den Block stellt; an einer
  Seitenwand von innen kommt nichts. `parts/ops.py` vereinigt `host_add`, ohne zu prüfen, wo er
  landet. **Offen:** ein Befund beim Einsetzen, wenn der Trägeraufbau außerhalb des Trägers oder
  unter z = 0 liegt, mit einer Handlung, die die Richtung umkehrt, in allen Katalogen.
  **Abnahme:** Kabeldurchführung von innen auf einen Boden und an eine Seitenwand gesetzt, je
  ein Befund mit Handlung; danach sitzt der Block innen und der Boden auf dem Bett.

<a id="rm-541"></a>

- [ ] **RM-541 — Der Skizzenlöser landet auf dem Intel-Mac im anderen Zweig einer
  Winkelbedingung.** `test_sketch_editor.py::test_the_angle_button_asks_for_its_degrees` setzt
  45° und bekommt unter `macos-26-intel` 135°, unter Windows, Linux und macOS ARM 45° (Sonde
  zu [RM-531](#rm-531), Lauf 37495714708). `least_squares` mit `method="trf"`
  (`app/core/sketch/solver.py`) beginnt mit dem Vertrauensradius ‖x₀‖, und weil die
  Unbekannten absolute Koordinaten sind, ist das in diesem Fall rund 13 mm: Der erste Schritt
  reicht über beide Zweige, und welchen er trifft, entscheidet die Rechnung der Plattform.
  Belegt ist der Radius, nicht die Rundung, die unter Intel kippt; an einem Intel-Rechner ist
  nichts nachgerechnet. **Fix:** in Verschiebungen gegen den Ausgangsstand rechnen, damit der
  erste Schritt am Zug hängt und nicht an der Lage des Ursprungs. Das ändert die Lösung
  unterbestimmter Skizzen; deshalb vorher und nachher gegen die Skizzentests und die Budgets
  aus §31 messen. **Abnahme:** der Test auf allen vier Plattformen grün, unterbestimmte Skizzen
  bleiben am nächsten Stand zu ihrem Ausgang, die Laufzeit im Budget.

<a id="rm-542"></a>

- [ ] **RM-542 — Die fünf offenen Entscheidungen der Erstkonfiguration.** Das
  [Konzept](konzepte/konzept-erstkonfiguration-2026-09.md) ist teilweise gebaut
  (`app/ui/first_run.py`), seine Fragen an Robert standen in keinem Punkt: wie viele Schritte
  der Erststart trägt; was mit einem Projekt geschieht, das einen anderen Slicer trägt, auch
  wenn der hier fehlt; was bei leerem Filamentregal gilt; ob die Wahl am Drucker oder am
  Projekt hängt; und was aus `slicer_filament_per_material` wird. Ob das Herstellerprofil
  ([RM-281](#rm-281)) einige davon schon beantwortet, ist nicht belegt. **Zuerst** je Frage am
  Code und an RM-281 prüfen, was heute gilt; **dann** entscheidet Robert den Rest.
  **Abnahme:** je Frage eine datierte Entscheidung im Konzept und, wo sie Bau verlangt, die
  Umsetzung oder ein eigener Punkt.

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
  **Offen:** die Feldabnahme aus §11 (ein Kunde ohne CAD geht *Das erste eigene
  Teil* ohne Hilfe durch). Die Nummernplatzierung ist gebaut (Teilstand 03.10.) und
  in den Bildanleitungen von 0.5.2 und 0.5.3 erzeugt (`9b0e93975`, `ee9a572f3`); in
  *Ein Gehäuse mit Deckel* 3 und *Ein Teil beschriften* 3 steht die Nummer im Bildrand
  mit Verbindungslinie (angesehen nur auf Deutsch).
  **Abnahme:** §11 des Konzepts.

  **Teilstand 03.10.2026 (Codex-Linien, übernommen von Claude):** `tools/make_guides.py` sperrt für
  Nummernscheiben die sichtbaren Textträger und Listen im Fenster, in Menüs und Dialogen; ist ein
  Dialog voll belegt, steht die Nummer im zusätzlichen Bildrand mit Verbindung zum Ziel. Tests:
  dichter Dialog, acht Nummern ohne Überschneidung, echte Rechtecke aus Dialog und Listen (Lauf mit
  222 grünen Fällen). Folgefund am Fenster: Die Weg-1-Tour blieb nach Neu → Modell öffnen stehen;
  der echte Projektwechsel beendet sie jetzt (12 Fälle). Von Hand ist kein Bildfingerprint
  geändert. Belege unter `F:\solidon-review-reports\codex-2026-10-03\bedienung\`:
  `import-history-move.md` (RM-283/299), `construction-ui.md`.

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

<a id="rm-200"></a>

- [~] **RM-200 — Ein Zug am Griff soll flüssig sein.** Robert, 21.09.2026:
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
  `_on_pointer` meldet nur bei geändertem Zustand.

  **Gebaut (`7ff34c675`):** Roberts Geste nachgestellt und verlegt — je Bewegung 13,6 → 8,8 ms,
  das Loslassen 89–134 → 25–57 ms, Griff und Maße nach dem Klick 9–21 s → 1–2,4 s; die
  Umgebungsverdeckung weicht im Zug auf 4 × 2 (`app/ui/render/gfx_occlusion.py`, `light`: vier
  Richtungen, zwei Schritte). Offen allein, ob sich der Zug am echten Fenster flüssig anfühlt
  (Release, RM-213).

<a id="rm-204"></a>

- [~] **RM-204 — Ein Merkmalklick baut alle Handlungen des Fensters neu.**
  Gemessen am 21.09.2026 im Review (Leistung A5): `_on_feature_selected` 47
  bis 60 ms und `_show_feature_fields` 42 bis 53 ms je Merkmalauswahl, weil
  `show_feature` das Fenster leert und alle Handlungen neu baut
  (`_build_action`, achtzehn Widgets, `request_in_view` synchron). Das Review
  nahm `findChildren` aus `_settle_lock` (13 ms je Wechsel); der Widget-Cache
  je Merkmalsart ist nicht gebaut, weil `_build_action` neun Closures an
  `action`, `fields`, `widgets` und `fixed` bindet, dazu Gruppen-Nachweise,
  `elsewhere`-Knöpfe, Katalogknopf und Schutzumschalter.
  Abnahme: ein Merkmalklick unter 20 ms im Fenster, `test_feature_panel.py`
  und `test_ui.py` unverändert grün.

  **Gebaut (`85dec7cbb`):** Zeilen je Signatur wiederverwendet (`_ActionRow`,
  `configure_feature_field` in `app/ui/panels.py`), Kernauskunft je Merkmal und Auswertung
  gemerkt; `show_feature` 41 → 12 ms, Wiederklick 8 ms, Klick bis Ruhe 391 → 140 ms
  (offscreen). Offen allein die Abnahme unter 20 ms am echten Fenster (RM-213).

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
  empfiehlt Anwendungen den Treiberweg navlib mit eigenem Bewegungsmodell. Die Rampe
  (`app/ui/spacemouse.py`, `quiet_crosstalk`) prüft `tests/test_spacemouse.py`.

  Bildzeit je Takt gemessen (`7ff34c675`: 16,7 → 8,7 ms im Median an 815 104 Dreiecken; jeder
  Takt setzt Kamera, Schnittebenen und ein synchrones Bild). Offen bleiben: **Linux** (Rechte
  und Gerätetest), das Verhalten bei paralleler 3DxWare-Mausemulation und die Rampe am Gerät,
  auch im Skizzenmodus (aus RM-183). Abnahme je Plattform mit benanntem Gerät, Treiber und
  reproduzierbarer Navigation; eine automatische Änderung der Treiberkonfiguration vorher
  entscheiden.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#eine-kundenanfrage-aus-dem-dentalbereich-30082026).

<a id="rm-084"></a>

- [~] **RM-084 — Kundentexte gegen die vereinbarte Sprache prüfen.** Website, Handbuch und sichtbare
  Anwendungstexte systematisch auf Roberts persönlichen, natürlichen Ton prüfen und verbleibende
  Stellen überarbeiten. Abnahme: vollständige Liste der geprüften Bereiche, konkrete Textänderungen
  ohne Bedeutungsverlust und vollständige Sprachkataloge.

  **Stand 23.09.2026 (Paket „texte", `konzepte/nachweise-release-0.5.0/reports/texte.md`):** Preise, Generatoraussage, README-Version,
  Sicherheitstexte, Agentenquote, Slicer-Begriff es/fr/pt, Du/Lei-Bestand it, portugiesische
  Anführungszeichen und die in `sollliste*.md` benannten Einzelstellen (B13/B12, B11c, B32, B23, B26,
  B27, B34, B16, B3, C2/C9/C10/C12, A16 und Nachbarn) geprüft und korrigiert, alle fünf Kataloge
  nachgezogen. Keine erschöpfende Zeile-für-Zeile-Prüfung jedes Anwendungstexts — der Rest der
  Oberflächentexte außerhalb der benannten Fundstellen ist mit den Durchgängen vom 03./04.10.
  gelesen (unten).

  **Durchsicht v0.5.1 (26.09.2026, texte):** Alles seit 0.5.0 gelesen — 154 neue
  Katalogschlüssel in sechs Sprachen, 41 neue Befundstellen, 56 Changelog-Punkte und die
  neuen Website-Texte; 20 Katalogtexte neu gefasst, Anrede es/it vereinheitlicht,
  Changelog-Punkte in Entwicklersprache umgeschrieben. Zwei Wächter halten den Stand über
  alle Kataloge: `test_wording::test_no_customer_text_uses_a_designer_word` (RM-088) und
  `test_wording::test_a_quoted_control_is_named_as_the_control_says` — von 51 abweichenden
  Knopfzitaten im Bestand 37 berichtigt, der Rest begründete Ausnahmen (`e8f9f574d`).
  Der Zeile-für-Zeile-Durchgang durch den Bestand vor 0.5.0 in Anwendung und Website folgte
  am 03./04.10. (unten).

  **Dazu, bisher nur im Register und in den Regeln (erledigt 03./04.10., unten):** aus der Sollliste der Durchsicht
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
  Presse A16/A23 und die C12-Namen — beides mit den Teilständen vom 03./04.10. erledigt. Die
  [Sollliste 0.5.0](konzepte/nachweise-release-0.5.0/reports/sollliste.md) mit ihren Teilen A bis
  C ist versioniert (05.10.2026).

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

  Handbuchseiten, Bildschirmfotos und Assetstempel je Sprache sind mit 0.5.2 und 0.5.3 erzeugt
  (`9b0e93975`; `5a3acd3a6`, `07139539a`, `e31d6cd5d`), die `rendered`-Fälle von `test_wording`
  sind grün (06.10.2026). **Offen:** die Fensterabnahme beim Release (RM-213) der längeren
  Knopfnamen (EN *Reverse selected entry*, *Even out the triangles now*; FR *Supprimer la
  caractéristique* und Verwandte, IT *Esegui slicing*, ES/PT Druckeinstellungen) auf 1280 px.
  Gemeldete Fehler der deutschen Quelle, behoben mit `871cc29e6` (Teilstand unten):

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
  Gebaut sind Druckziel, Übergabestatus, Befundkarte mit Folge und Nebenfolgen,
  Vorher-/Nachher-Vergleich und Übergabebeleg mit Gegenprobe (03./04.10., Teilstände unten).
  **Offen:** allein die gemeinsame Abnahme aller fünf Erlebnisse auf den vier Hauptwegen am
  echten Fenster, einschließlich Fehler-/Wechselfällen und sechs Sprachen (RM-213).

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

<a id="rm-135"></a>

- [~] **RM-135 — Zugewiesene Höhe der Filamentkarte vollständig nutzen.** Qt berechnet Hinweis,
  sichtbare Knöpfe und Abstände bei der tatsächlichen Breite; leere Listen erzwingen keine
  überzähligen Mindestzeilen. Acht Regressionen und die native Windows-Abnahme mit knappen/freien
  Höhen, langen Hinweisen, großer Schrift und voller Liste sind grün. Nachbarkarten behalten ihren
  Raum; der Mac-xfail ist entfernt. Offen bleibt der plattformübergreifende Prüflauf auf macOS.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#ein-ort-für-die-auswahl-07092026).

<a id="rm-213"></a>

- [~] **RM-213 — Fensterabnahme und die Kundenwege am echten Fenster.**
  Die Paketnachweise der Durchsicht 0.5.0 stammen überwiegend aus
  Offscreen-Läufen oder Fenstern mit `WA_DontShowOnScreen`. Die späteren
  Website-Aufnahmen und Skizzenlabel-Sonden zeigen echte maximierte Fenster;
  sie belegen ihre Motive und die jeweiligen Reparaturen. Die vollständige
  Welle 2 „kundenwege" mit allen folgenden Abnahmekriterien ist damit noch
  nicht gefahren. Was nur das echte Fenster zeigt (Schrift, Vulkan-Fläche, Fokus,
  Bildschirmleser, gefühlte Wartezeit, Navigation mit Drehpunkt nach Änderungen an
  `_NAVIGATION` oder `camera_step`): die Punkte RM-198, RM-200 und RM-204
  (sie bleiben je eigene Punkte und schließen in diesem Lauf; RM-174, RM-197, RM-199 und
  RM-205 sind geschlossen, siehe Archiv);
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
  der Bereichsnachweis aller Bausteine (heute 49) ist frisch (sonst zeigt der Katalog
  je Baustein die Warnung; für 0.5.3 `534d69b79`); `make_figures.shoot` (Handbuch) und die
  übrigen Aufnahmewerkzeuge fragen die Fensterwache über `make_figures.grab_uncovered`
  (website, `6759555d`: parallele Aufnahmen zerstörten Bilder anderer Sitzungen; erfüllt seit
  dem Teilstand 03.10.). Abnahme: ein
  Protokoll je Weg mit Klicks, Zeiten und Bildern nach dem Bildstandard vom
  23.09.2026, jeder Befund behoben oder als Punkt geführt.
  Aus RM-513 und RM-518 (05.10.2026): der Operationsdialog mit Maus und
  Bildschirmleser — umgebrochene Beschriftungen hinten, die Lesezeile *Stelle*
  mit *Stelle im Bild wählen*, benannte Null („Oberkante“, „automatisch“) im
  Zahlenfeld, „Wann nicht?“, die verschachtelte Klappe unter „Anwendung“ in den
  Einstellungen; mit den neuen Bildern ihre Alttexte (der Bohrdialog in
  `funktionen.html` und den Übersetzungen nennt noch Position X, Y, Z mit fx).
  Aus RM-516 (05.10.2026): Handbuchbilder guide-thread-a-hole-1 und
  guide-drill-a-hole-8 mit 0.5.3 erzeugt (`ee9a572f3`); am Fenster die geöffneten
  „Weitere Werte“ der Maßkarte, HiDPI, helles Thema und das Vorschauband in Zoll mit echter
  Größenänderung.
  Aus RM-508 (05.10.2026): `report.png`, `main-window.png` und die
  Bildanleitungen mit 0.5.3 erzeugt (`5a3acd3a6`, `e31d6cd5d`, `ee9a572f3`); am Fenster, ob
  `make_figures` dem Berichtsbild die Grundlage des Fensters mitgibt.
  Aus RM-509 (05.10.2026): Tour, Befundkarten, Bausteinänderungen und
  KI-Hinweis tragen kürzere Texte; die Bilder, die sie zeigen, sind mit 0.5.3 erzeugt; am
  Fenster die Texte selbst.

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
  `report_error` in `test_first_run.py`. Ein Fall war am Stand davor rot, in einer
  Sonde außerhalb von pytest an `0273b8d23` und `c2bff45f1`:
  `test_surface_placement_ui.py::test_the_measures_stay_in_the_view_while_a_pulled_slot_waits`
  — nach dem Zug zum Langloch standen keine Maße im Bild, erwartet sind zwei Felder und kein
  runder Umriss (`konzepte/nachweise-release-0.5.1/sonden/rest-auswahl/out/fenster-vor.txt`).
  Im Release-Lauf 0.5.3 grün (Taglauf 37409338027, Windows-Gruppe 2), ebenso die sieben Fälle
  oben, die beiden am alten Stand roten und die fünf neuen Fensterdateien; am echten Fenster
  mit abnehmen.

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

  **Dazu (RM-099, 07.10.2026):** die vier Handwege der Merkmalbedienung aus §4 ihres
  [Konzepts](konzepte/konzept-merkmalbedienung-2026-09.md), die bisher kein Punkt führte:
  Bohrung wählen, Maße in der Szene ändern und rechts übernehmen, die Maße stehen danach
  noch; am Gizmo verschieben, die Maße stehen danach; am Langlochknopf ziehen, Länge und
  Richtung rechts übernehmen, unten keine Leiste; eine neue Bohrung über das Menü wie bisher.

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
  `ab.sh zeit` aus `.claude/.state/rm-232-erster-klick-2026-09-25/`.

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

  **Verbleibende Arbeit vom 02.10.** (426 Variantenfehler: 184 ohne Druckdatei, 110 als Absturz
  gemeldet, 74 nicht vollständig auf der Druckplatte, 56 außerhalb des Slicerbauraums, 2 zu hoch;
  `image_00001_.glb` und `carpet-corner-clip.step`; 149 Ausgaben mit Fehlerbefund; 770
  Markierungen; 1.353,128 s Creality-Zeitabweichung): abgearbeitet am 04.10. (Teilstand
  unten). Offen bleibt die native Fensterabnahme der Düsenwahl beim Release.

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

  **Teilstand 04.10.2026 (Claude, G2 `claude/rm312-matrix`):** Alle 575 auffälligen Zeilen der
  Matrix vom 02.10. (426 Variantenfehler, 149 Ausgaben mit Fehlerbefund) liefen am heutigen Stand
  noch einmal über den Kundenweg mit denselben Slicer- und Druckerpaaren: 235 drucken ohne Befund,
  276 sagt Solidon vor dem Slicerstart mit Grund ab (zu groß, zu hoch, keine Anordnung), 8 hält
  Solidon bei mehreren Druckdateien an, 6 enden mit der Meldung zur ersten Schicht; benannte
  Slicer-Eigenheiten sind `chufang.3mf` (Turm gegen Teil, −101), Creality Print 7.3 (gut 1 mm Rand
  je Seite) und ein SuperSlicer-Absturz beim Stützen. Kein Lauf endet mehr mit Absturz,
  `gcode.shorter_than_model` oder `gcode.spool_left_out`. `image_00001_.glb` war ein Fehler des
  Matrixwerkzeugs (Einheitenfrage), `carpet-corner-clip.step` war mit `783f62d2a` behoben; die 770
  Markierungen sind Artefakte des Vergleichers oder erwartbar; der Creality-Zeitunterschied ist bis
  auf 0,7 s zugeordnet (11 900 s Ladezeit, 1 357 s Reinigungsturm von 7.3). Neun Produktfehler
  behoben und im echten Slicer belegt: Höhenprobe an Schneiden und letzter Stelle (`1e112c8af`,
  `b4cdc2717`), Turm neben der Sperrfläche von P1S/P1P/X1/X1C (`f24e321f3`), schmale erste Schicht
  (`f9b861cc1`), SuperSlicer mit `--dont-arrange` (`d44e712b3`), gedrehte Übergabe an die
  Orca-Familie (`949b1bbd6`), Rand in einer Sperrfläche vor dem Export (`acab16345`), Drehung mit
  Platz für den Rand (`2f939825a`), kreuzende Bahnen −101 (`08f15274b`). Entwicklungstor vor jedem
  Commit grün. Grenze: Die tatsächliche Druckdauer am K1 lässt sich ohne Gerät nicht messen. Belege
  unter `F:\solidon-review-reports\claude-2026-10-04\rm312-matrix\`.

  Die Prüfung vor dem Export rechnet die Außenkante der ersten Schicht jetzt aus dem, was der Slicer
  tatsächlich legt (`rim_of`, Commit `9e35c0115`; heute `build_area.rim_of`): Steht der Brim beim Herstellerprofil der
  Orca-Familie auf „automatisch“, mit der größten Breite, die OrcaSlicer wählt (`ORCA_AUTO_BRIM_MAX`
  = 18 mm, belegt in `Brim.cpp`, `configBrimWidthByVolumeGroups`), und die Warnung bietet
  *Brim-Breite festlegen …* an; wählt der Kunde einen Brim oder übernimmt einen Vorschlag, schreibt
  Solidon `outer_only` mit Breite, und der Slicer wählt nichts mehr selbst. Mit Stützen zählt die
  Verbreiterung der ersten Stützschicht (`raft_first_layer_expansion` aus der Kette, sonst die
  gemessene Programmvorgabe: Orca, Elegoo, Creality 2 mm, PrusaSlicer und SuperSlicer 3 mm;
  `manufacturer.SUPPORT_FOOT_DEFAULTS`, `Foundation.support_foot`), außen darum der Skirt aus Profil
  oder Wahl; die Warnung bietet *Auf dem Bett anordnen* und *Skirt verkleinern …*. Wo das Profil die
  Verbreiterung nicht nennt (Cura; Bambu Studio schreibt `-1`), sagt `arrange.support_foot_unknown`
  das, statt eine Zahl zu schätzen. Beide Handlungen öffnen die Druckeinstellungen an ihrer Zeile
  (`MainWindow.action_print_settings(field=…)`, `PrintSettingsDialog.show_setting`). Echte Läufe
  über den Kundenweg (`‹B›\nachtrag-j\`, `nachtrag-j2\`): Rack system for Filament.3mf an
  ElegooSlicer/Centauri Carbon 2, vorher (Stand `acab16345`) Platten 9–14 mit Auto-Brim bis y =
  −1,27 mm ohne Vorwarnung, nachher dieselbe Druckdatei mit Warnung (7,70 mm) vor dem Export, und
  mit gewähltem Brim `brim_type = outer_only`, Brim 4,56 mm vom Rand, alle 14 Platten bis auf die
  zwei an der Sperrecke ohne `gcode.off_the_bed` (die zwei mit 2,00 mm vorher gewarnt);
  garden-hose-holder.3mf am MINI mit SuperSlicer vorher 0,01 mm gewarnt, Skirt 2,46 mm über dem
  Rand, nachher 3,01 mm Warnung mit beiden Handlungen, auch wenn die Stütze nur am Objekt
  eingeschaltet ist (Vorschlag je Teil); obj_15_Assembly 2,97 mm; Wizard Tower an Cura mit Stützen
  nennt die unbekannte Verbreiterung. Tests: sechs neue Fälle in `test_export.py` (Auto-Brim nur bei
  der Orca-Familie und ohne gewählten Brim, Stützfuß mit Skirt auch je Teil, unbekannter Fuß, Skirt
  neben einem Brim, Lesen der Verbreiterung), vorher rot; die Gegenprobe der Messung steht in
  `‹B›\vorgaben\` (`--save` von PrusaSlicer und SuperSlicer, Konfigurationsblöcke von ElegooSlicer,
  OrcaSlicer, Creality Print und Bambu Studio). Die Druckdauer am K1 bleibt ohne K1 eine Grenze
  (Abschnitt 1). Die Dateien des Matrixwerkzeugs liegen vollständig unter
  `‹B›\matrixwerkzeug\uebernahme\` (einheit.py, bericht.py, dazu die Diffs und `LISTE.txt` mit Ziel,
  Basis-SHA und Inhalt), eingepflegt auf den Stand von G1 (13:03) und an `image_00001_.glb` und
  `1x1-bin.stl` erprobt (`‹B›\werkzeugprobe\`).

  **Teilstand 05.10.2026 (Fehlalarm nach 0.5.2 behoben):** Die Randprüfung maß Brim und Skirt von
  der Aufsicht des ganzen Teils aus, die Slicer legen sie um die erste Schicht; Teile, die oben
  breiter sind als am Fuß, bekamen eine Warnung, obwohl der Rand auf dem Bett blieb (Beleg
  `F:\solidon-review-reports\claude-2026-10-04\rm281-paket3\bericht.md`, Nachtrag 2). Jetzt
  trägt `build_area.RimReach` zwei Reichweiten: `layer` (Brim und Skirt um den Schnitt der ersten
  Schicht, `writer._first_layer_outline`) und `top` (Stützfuß und Skirt um die Aufsicht);
  `check_adhesion_on_bed` warnt nach der weiteren, die Sperrflächenprobe misst am selben Umriss.
  Der Brimvorschlag fragt `build_area.rim_room`: der breiteste Rand um die erste Schicht, während das
  ganze Teil in einer Drehung aufs Bett passt (`advise.brim_room`). Echte Läufe über den Kundenweg
  (Matrixeinheit, Kerne `FFFFF0FF`): garden-hose-holder am MINI mit SuperSlicer und PrusaSlicer
  ohne Stützen ohne Befund, Skirt im G-Code x 32,65–164,56 mm auf 180 mm; mit Stützen weiter die
  Stützfußwarnung, im G-Code Stütze −0,22–180,22 mm, Skirt −2,46–182,46 mm (`gcode.off_the_bed`,
  zu Recht). Waschschüssel am Kobra 2 mit OrcaSlicer ohne Stützen ohne Auto-Brim-Warnung (vorher
  bei allen drei Varianten). Tests: Tisch auf einem Mittelfuß (`test_advise.py`, 85 mm Platz, Brim
  vorgeschlagen), breites Teil auf schmalem Fuß (`test_export.py`), beide vorher rot.

  **Teilstand 06.10.2026 (Stützfuß unter den Überhängen):** Bis dahin zählte der Stützfuß die ganze
  Aufsicht, die Slicer stützen nur die Überhänge; die Waschschüssel am Kobra 2 mit Stützen bekam
  die Stützfußwarnung, obwohl die erste Stützschicht im G-Code 15 mm vom Rand blieb (Nachtrag 2:
  x 15,1–196,9, y 23,1–194,4 mm auf 220 mm). Jetzt misst `check_adhesion_on_bed` den Fuß am Umriss
  der Überhänge aus der Schichtanalyse (`analysis.overhang_outline`, im Export über
  `writer._support_outline` aus denselben Schichten wie die Stützsperre); ohne Überhang gibt es
  keinen Fuß. Am Kundenmodell, schräg auf 220 × 220 mm (Sonde): Öffnung oben, Überhänge
  20,4–204,2 mm, vorher 5,61 mm Warnung, jetzt keine; Öffnung unten, Überhänge bis 0,5 mm vom Rand,
  Warnung bleibt (5,32 mm). Test `test_export.py::test_the_support_foot_stands_under_the_overhangs_only`,
  vorher rot (Platte mit Tisch in der Mitte, Teil mit Überhang bis zur Kante, Quader ohne Überhang).

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
  **Offen:** die Fensterabnahme auf allen Plattformen beim Release (RM-213): Kaufdatum
  „05092026“ tippen und *Unbekannt*, Spulenfenster auf halber Höhe, *Werte mitgeben* mit
  schreibgeschütztem Nutzerordner, Ersteinrichtung in sechs Sprachen und FDM/Resin. Die
  Fenstertests dazu sind im Taglauf 0.5.3 (37409338027) unter Windows grün, auch
  `test_first_run_setup.py::test_custom_printer_natural_width_and_manual_height_survive_toggling`
  `[fdm-fr]` und `[resin-fr]`, die im
  [CI-Lauf 37086153737](https://github.com/RS-Digital-Studio/Solidon/actions/runs/37086153737)
  am Stand `4c172d8ee` noch mit `assert 42 == 0` rot waren; Prüfzeile der Spule und Hinweis
  zur Mitgabe sind in den Teilständen 03./04.10. gebaut.
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
  Beifund: Der Kommentar in `app/core/knowledge/data/licences.toml:53` sagt weiter ohne Vorbehalt
  „TripoSG MIT“.

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

- [~] **RM-251 — Mehrteilige Aufträge enden lokal am Schrittlimit.** Gefunden am
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

- [~] **RM-016 — Agenten-Suite gegen das aktuelle Vorgabemodell messen.** Die Agenten-Suite gegen
  das tatsächlich konfigurierte Vorgabemodell auf einer festgehaltenen Regelversion messen und mit
  einem vergleichbaren Referenzlauf bewerten. Abnahme: Fallresultate, Modellkennung, Regelversion
  und Quote sind belegt; mehrschrittige Werkzeugaufrufe berücksichtigen den Umgang mit
  Thinking-Blöcken. Die Behandlung von Modellablehnungen ist bereits gebaut.
  **Neu zu messen nach RM-513 (05.10.2026):** Rund hundert Felder stehen jetzt
  hinten; für Rückseitenfelder liest der Agent die Bedingung, nicht den Satz.
  Lokal mit qwen3:14b gegen den Stand `1ce7eac68` (24 gut mit Angebot);
  verschlechtert sich die Quote, bekommen die betroffenen Felder ihren Satz
  zurück.

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
  **Freigegeben (Robert, 06.10.2026):** der gehostete Lauf. Auf dem Arbeitsrechner liegt
  kein Anthropic-Schlüssel (weder im Schlüsselbund noch in `SOLIDON3D_LLM_KEY_ANTHROPIC`);
  der Lauf startet, sobald einer hinterlegt ist.

<a id="rm-441"></a>

- [~] **RM-441 — Reste aus RM-372 und RM-374: `hollow.done` ohne Knopf, Beispielprojekt mit alten Transaktionen.**
  Fund 02.10.2026 beim Abschluss von RM-372/RM-374 (Claude). (a) Der Befund `hollow.done`
  (`app/core/geom/hollow.py`) meint einen änderbaren Schritt und trägt noch nicht
  *Diesen Schritt ändern* — Vorgabe Robert zu RM-374, ausgelassen, weil `hollow.py` bei Codex
  offen lag; danach `MEINT_DEN_SCHRITT` in `tests/test_finding_ways.py` nachziehen.
  (b) `weg3-generiert-aufbereiten.p3d` trägt noch die früheren getrennten Transaktionen; beim
  Release mit `tools/make_examples.py` neu erzeugen. **Abnahme:** Test für (a); (b) im
  Release-Lauf. Bauplan §2.7, §15.5.
  Review 02.10. (`73d83b55b`, RM-374 archiviert mit `9983e9923`): Die Vorgabe „jeder Befund, der einen änderbaren Schritt meint, bekommt den Knopf“ ist nicht erfüllt — ohne Knopf bleiben `mesh.already_below_target` (`app/core/geom/mesh_ops.py:2222`, im Fenster geprüft), `rotate_feature.unchanged`, `resize_feature.unchanged`, `move_feature.unchanged`, `{operation}.unchanged` (`prepare_ops.py`) und `bore.resize_unchanged` (`prepare.py`, `prepare_ops.py`); dieser Punkt nennt bisher nur `hollow.done`. Beleg `F:\solidon-review-reports\verif-73d83b55b-claude.md`.
  **Stand 02.10.2026 abends:** (a) erledigt (Claude, Thread „Bedienung und KI“): Beide `hollow.done` tragen *Diesen Schritt ändern* mit `field: wall`, `MEINT_DEN_SCHRITT` nennt sie. Offen (b).
  **Stand 06.10.2026:** (b) erledigt im Release-Lauf 0.5.3: `make_examples.py` hat alle
  Beispielprojekte neu erzeugt (`ac0d11486`), `weg3-generiert-aufbereiten.p3d` trägt die
  Transaktionen des heutigen Codes. Offen bleibt der Review-Fund: Die sechs Befunde oben
  (`mesh.already_below_target`, `rotate_feature.unchanged`, `resize_feature.unchanged`,
  `move_feature.unchanged`, `{operation}.unchanged`, `bore.resize_unchanged`) tragen den Knopf
  noch nicht und stehen nicht in `MEINT_DEN_SCHRITT`; je Befund mit `cache_version` der Op.

<a id="rm-529"></a>

- [ ] **RM-529 — Der Steckbrief nennt nicht, welcher Schritt ein Merkmal erzeugt hat.** Bauplan §23 zeigt im
  Steckbrief `created_by=op3`, und §21.2 macht die Provenienz zur Grundlage für „den Schritt
  ändern, der es erzeugt hat“. `app/core/perceive/digest.py` schreibt sie weder in die
  Merkmals- noch in die Objektzeile; der Agent braucht sie für Anfragen wie „ändere den Stift
  von vorhin“. **Entschieden (Robert, 06.10.2026):** nachrüsten. **Abnahme:** Der Steckbrief
  nennt bei erzeugten Merkmalen den erzeugenden Schritt, Test an einem Beispielprojekt, das
  Beispiel in Bauplan §23 ist eine echte Ausgabe, Agenten-Suite vorher und nachher.

## Tests und Entwicklungswerkzeuge

<a id="rm-103"></a>

- [ ] **RM-103 — Große Kernfunktionen nach konkretem Wartungsbedarf aufteilen.** Die großen
  Kernfunktionen anhand ihres heutigen Aufbaus priorisieren; zuerst die Verantwortlichkeiten der
  Auswertung prüfen. Nur begründete Aufteilungen durchführen. Abnahme: gleiche Geometrie, IDs,
  Befunde und Laufzeit vor/nach dem Umbau sowie die vier Hauptwege; alte Zeilenzahlen nicht als
  aktuellen Befund weiterführen.

  **Gemessen am 06.10.2026** (AST, `app/core/scene/evaluate.py`): `evaluate` ist eine Hülle
  mit 66 Zeilen, `_evaluate` hat 1046, `_with_features` 1348 (13.09.: 571/607 für `evaluate`
  und `_with_features`; 02.10.: 46/934/1185). Das begründet die Aufteilung nicht von selbst, es
  sagt nur, dass der Punkt wächst, während er wartet. Zahlen hier gelten nur mit Datum; wer den
  Punkt aufnimmt, misst neu.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#architektur-durchsicht-02092026).

<a id="rm-134"></a>

- [~] **RM-134 — Doppelte Testhilfen zusammenführen.** Robert hat die Zusammenführung
  genehmigt („alles gründlich“). Belegt sind doppelte Freiformhilfen für Kegel/Torus und
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
  sind Drei- und Vierzeiler, die ein gemeinsamer Ort nicht kürzer machte. Damals zu entscheiden:
  die sechs nach `tests/helpers.py` (oder `conftest.py`-Fixtures) — oder nichts, weil jede
  Datei für sich lesbar bleiben soll.

  **Stand 06.10.2026:** Neun wortgleiche Helfer stehen einmal in `tests/helpers.py` und
  `tests/ui_helpers.py` (`95fd36d35`), darunter `window` und `with_a_body`. **Offen:**
  `on_the_bore_wall` (`tests/test_analysis_ui.py`, `tests/test_selection.py`), `project`
  (`tests/test_agent.py`, `tests/test_agent_suite.py`), die Querimporte von `FakeCodec`
  (`tests/test_cache.py` aus `test_native_references.py`) und von `a_foreign_slot`
  (`tests/test_slot_features.py` aus `test_round_surface_measurements.py` und
  `test_surface_patches.py`). Der Docstring von `tests/helpers.py` nennt nur die letzten beiden.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#doppelte-stellen-und-zwillinge-gemessen-07092026).
  **Entschieden (Robert, 06.10.2026):** Auch die großen Fenster-Fixtures (`window`,
  `with_a_body`, `on_the_bore_wall`) werden zusammengeführt; abgenommen im nächsten
  Release-Tor.

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
  BIOS. **Entscheidung Robert:** CPU-Tausch über Intels verlängerte Garantie (13./14.
  Generation, fünf Jahre ab Kauf) — der einzige Schritt, der die Ursache beseitigt —, bis
  dahin im BIOS die Intel Default Settings (dazu prüfen, ob MSI Center Takt- oder
  Leistungsgrenzen anhebt). Offen: MemTest86 über Nacht, um den Arbeitsspeicher
  auszuschließen, und der Tausch selbst. Die Pakete von 0.5.3 kommen aus der CI; was hier
  entsteht (Handbuch, Bilder, Signatur), trägt das Risiko weiter. Ob die Default Settings
  gesetzt sind und MemTest86 lief, ist am 06.10. nicht nachgesehen. Bericht:
  `konzepte/nachweise-release-0.5.1/reports/ast-flake.md`. Abnahme: nach dem Tausch keine
  sporadischen Abrisse dieser Familie mehr, belegt mit einer verschränkten Reihe der
  Sprachprüfung unter Last wie in ast-flake, und MemTest86 ohne Befund.

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
  (Protokoll des Nachstellversuchs nicht versioniert). Zu klären ist auch, ob ein
  wgpu-Finalizer gegen den Poller die Anwendung anhalten kann: Seit `35847e4db` räumt sie nur
  noch im Hauptfaden über `leash.collect_in_main_thread` ab, also dort, wo dieser Hänger
  stand. Bis dahin wählen Sitzungen betroffene Tests gezielt
  oder fahren das Tor. Abnahme: der Einzelprozess läuft durch, oder die Ursache ist
  benannt und behoben.

<a id="rm-314"></a>

- [~] **RM-314 — Rechtenachweis der Stimme für die englischen Werkstattfilme.** Die Stimme
  `en_US-ljspeech-high` und ihr lokaler ONNX- und Konfigurationsstand sind in
  `app/core/knowledge/data/licences.toml` mit Prüfsummen dokumentiert. Die Rechteangabe
  stützt sich auf die Public-Domain-Erklärung und Uploadfreigabe des Modellautors sowie die
  Public-Domain-Angabe der LJ-Speech-Quelle; die MIT-Markierung bei Hugging Face gilt nur auf
  Repository-Ebene, und die Modellkarte widerspricht dem Autor bei Trainingsangaben. Die
  Lizenztests sind grün. Das ist kein pauschaler Nachweis einer gesonderten Einwilligung der
  Sprecherin in Stimmnachahmung oder Werbung; die Quellen belegen eine solche Einwilligung
  nicht.
  Nachprüfung (Review 02.10., Arbeitsbaum ungesichert): unvollständig. Eintrag in `licences.toml` und SHA-256 stimmen mit den Dateien; ein `/legal-review` ist nirgends belegt, `ASSET-RIGHTS.toml` hat keinen Eintrag für die Stimme, die Einwilligungsfrage zur Werbenutzung ist im Eintrag ausdrücklich offen und trotzdem `[x]`; die angeführten Lizenztests prüfen die Stimme nicht.
  **Stand 06.10.2026, deshalb `[~]`:** Am HEAD führt `ASSET-RIGHTS.toml` nur
  `tools/voice-reference.wav`, die Stimme steht allein in
  `app/core/knowledge/data/licences.toml`, und kein Test liest `ljspeech`. **Offen:**
  `/legal-review` zur Werbenutzung, ein Eintrag in `ASSET-RIGHTS.toml` und ein Test, der die
  Stimme prüft — oder Roberts Entscheidung, den Punkt mit der ausdrücklichen Grenze
  „Einwilligung der Sprecherin zur Werbenutzung nicht belegt“ zu schließen.

<a id="rm-316"></a>

- [~] **RM-316 — Zwillinge und Nur-Test-Wege: der Rest aus dem Code-Bericht des Aufräumens.**
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
  **Stand 06.10.2026:** Die Höhenregel im Druckdialog ist mit `b837a73f8` erledigt; ein
  `manual_window._svg_pixmap` gibt es nicht (Entsprechung `_rendered`, eine Variante).
  `b03c0ddfe` (02.10., Codex) hat erledigt: **(d)** `key.device_limit` ist entfernt; **(b)**
  entfernt sind `slice.gcode.parse` samt `extrudes`, `printed_extent`, `stated_bed`,
  `Session.embed_model`/`import_image` und `autosplit.sections_along`, als Prüfweg dokumentiert
  `generate.from_image` und `mesh_ops.decimate`; **(c)** als Referenz- oder Prüfweg dokumentiert
  `autosplit.find_plane`, `orient.evaluate_direction` und `matching._cost_matrix`. **Offen:**
  **(b)** `draft_vertical` (`brep/profiles.py`, `geom/faces.py`), `placement.placement_tool`,
  `perceive.features.detect_faces`, `slice.analysis._islands`,
  `set_pickable`/`remove_pointer_listener` (`render/api.py`), `faces._upright_faces` und die
  `_shadow_*` in `viewport.py` (ob dort noch dünne Hüllen sind, ist nicht geprüft); **(c)**
  `section.section_volume`, `repair.fill_holes`; **(a)** die Kopie `_select_data` in
  `app/ui/print_settings_dialog.py:320` (Original `style.select_data`); die Karte
  `app/ui/CLAUDE.md` nennt `ContentHeight`, aber weder `select_data` noch `svg_pixmap`.

<a id="rm-344"></a>

- [ ] **RM-344 — Renderertests laufen in der CI nur noch unter Windows.**
  Review seit 0.5.1, Befund E-M1, Commit `6f0be89df` (Codex).
  Der Marker `rendering` wird in der Kernmatrix (`.github/workflows/build.yml:185`) und im Job
  `latest` (am 06.10. `:1616`) abgewählt und nur noch von der Gruppe `windowed` (Job `windows`) und
  `window-contracts` getragen (`tools/run_suite_isolated.py:80–81`).
  `pytest --collect-only -m "rendering and not windowed and not performance and not rendered"`
  am 06.10.2026: 112 Fälle (`test_render_gfx_regressions` 69, `test_render_contract` 24,
  `test_render_gizmo` 14, `test_render_factory` 3, `test_feature_label_layout` 2), vorher in der
  Kernmatrix auf drei Plattformen; `test_render_factory.py` läuft über `CONTRACT_FILES` in den
  Fensterverträgen aller drei Plattformen, die übrigen 109 nur auf Windows beim Release. Linux-
  und Mac-Pakete zeichnen über Vulkan/Metal, RM-051 ist offen, neue pygfx-/wgpu-Fassungen prüft
  `latest` nicht mehr. Widerspricht CI-03/CI-04 aus `konzepte/konzept-ci-testlaufzeiten-2026-09.md`;
  eine Entscheidung Roberts dafür ist nicht festgehalten.
  Hohl geworden: `test_every_linux_ci_path_that_uses_pygfx_has_a_vulkan_adapter`
  (am 06.10. `tests/test_packaging.py:899ff.`) bleibt grün über Jobs ohne Bildtest; veraltet
  der Kommentar `build.yml:110–116`. Die damals genannte Stelle `README.md:170–178` ist
  umgeschrieben; am 06.10. nennt `README.md` „Fenster-, Renderer- und Leistungsprüfungen“ nur
  für das lokale Tor.
  **Fix:** Die `rendering`-Fälle in der Release-CI zusätzlich auf Linux und macOS fahren (etwa in
  `window-contracts` mit `-m "rendering and not windowed …"`) und in `latest` wieder mitnehmen —
  oder, wenn Robert die Windows-Grenze will, die Entscheidung im Konzept festhalten.
  **Abnahme:** Wächter in `test_packaging.py`, dass jeder `rendering`-Fall auf jeder Plattform in
  mindestens einem Releasejob läuft; Vulkan-Wächter, Kommentar und README auf dem Stand.
  Bauplan §35, §38. Beleg: `bericht-E.md` (M1), `sonden\e_collect_rendering_only.txt`,
  `e_collect_render_core.txt`.
  Nachprüfung am Stand `6ce767031`: besteht noch. Von 110 Renderfällen laufen 107 nur in der Windows-Release-CI; Wächter fehlt, Kommentar und README veraltet. Belege `F:\solidon-review-reports\verif-E.md`.
  **Entschieden (Robert, 06.10.2026):** Die Release-CI fährt die `rendering`-Fälle auch
  unter Linux und macOS.

<a id="rm-467"></a>

- [~] **RM-467 — Bibliotheken alle drei Tage auf neue Versionen prüfen und aktualisieren.**
  Auftrag Robert 02.10.2026, übernommen: Bibliotheken alle 3 Tage aktualisieren. Je Lauf werden die
  festen Versionen aus `constraints.txt` (Laufzeit und Entwicklung, mit den Plattformpins), die
  Werkzeuge in `.github/workflows/` und die Paketlaufzeiten gegen ihre neueste Fassung abgefragt;
  eine neue Fassung zählt nur mit cp314-Rädern für Windows x64, Linux x86_64 und beide Macs.
  Reihenfolge: Sicherheitsmeldungen, dann Patch und Minor, dann Hauptversionen. Jede Aktualisierung
  geht einzeln durch das Entwicklungstor und, wo sie die Oberfläche oder den Renderer berührt,
  durch die echte Anwendung; danach `tools/check_env.py --freeze`. Was den veröffentlichten Stand gefährdet,
  bleibt festgelegt und bekommt einen eigenen Punkt mit dem nötigen Umbau. Ergänzt
  [RM-313](ROADMAP-ARCHIV.md#rm-313): Der CI-Wächter „Neueste Versionen“ läuft nur an
  Release-Tags oder auf Handstart, dieser Lauf lokal und regelmäßig.
  **Abnahme je Lauf:** geprüft, übernommen und zurückgestellt mit Commit im Archiv; der Punkt
  bleibt offen, solange der Auftrag gilt.
  Erster Lauf: [02.10.2026](ROADMAP-ARCHIV.md#rm-467-erster-bibliothekslauf-achtzehn-bibliotheken-und-die-bauplattform-02102026).
  Der zweite Lauf war am 05.10. fällig und steht aus; bekannt ist seither `cadquery-ocp-novtk`
  8.0.1.1.0 (in `constraints.txt` auf 8.0.1.0.0 festgelegt, der Wächter „Neueste Versionen“
  zog am Tag v0.5.3 die neue Fassung, die Lizenzbeilage kennt sie seit `036021393`).

<a id="rm-531"></a>

- [~] **RM-531 — Fenstertests und echte Slicer auch unter Linux und macOS in der CI.** Die
  Fenstergruppe läuft in der Release-CI nur unter Windows (Job `windows` in `build.yml`), Linux
  und macOS fahren nur die Fensterverträge (`--ci-group contracts`). Echte Slicer prüft keine CI:
  Erkennung, Herstellerbestand und Slicen unter Linux und macOS belegten bisher nur
  Wegwerfzweige (`.claude/.state/slicer-sonde-2026-10-05/`,
  `.claude/.state/druckerliste-2026-10-06/`). Am 06.10.2026 liefen dort die Fensterdateien der
  drei Druckerwahlen unter Ubuntu 24.04 und macOS ARM vor und nach der Änderung grün
  (`test_print_settings_ui.py` mit 396 Tests in rund zweieinhalb Minuten), und Anycubic Slicer
  Next ließ sich unter Linux (apt-Quelle des Herstellers) und macOS ARM und Intel (DMG)
  installieren, lesen und zum Slicen bringen. Derselbe Lauf fand eine Testattrappe, die vom
  echten Code abgewichen war (`conftest._machine_stays_out_of_it`). Auftrag Robert
  (06.10.2026): solche Tests über die CI für Linux und Mac breit fahren. **Fix:** die
  Fenstergruppe der Release-CI auf allen drei Plattformen; ein Slicer-Job je Plattform, der die
  unterstützten Slicer installiert (Flatpak, AppImage und apt unter Linux, Casks und DMG unter
  macOS) und Erkennung, Druckerlisten aus Erststart, Einstellungen und Druckdialog sowie das
  Slicen eines Würfels prüft — die beiden Sonden als Grundlage, nach `tools/` gezogen (RM-530).
  Ausgelöst am Tag und per Handstart, im Vertrag der CI-Aufteilung
  (`konzepte/konzept-ci-testlaufzeiten-2026-09.md`); die Renderertests stehen in RM-344.
  **Abnahme:** Ein Tag-Lauf zeigt die Fenstergruppe auf drei Plattformen grün und je Plattform
  jeden installierbaren Slicer mit Druckerliste und Druckdatei; `test_packaging.py` hält die
  neuen Jobs im Vertrag.

  **Entschieden (Robert, 06.10.2026):** Die Fenster- und Renderergruppe läuft auf allen vier
  Paketplattformen (`windows-latest`, `ubuntu-24.04`, `macos-latest`, `macos-26-intel`) am Tag,
  per Handstart und bei jedem Push auf main; Hausordnung und `/pruefen` ziehen nach, das lokale
  Tor bleibt ohne Fenster. Die Abnahme gilt damit für vier Plattformen.

  **Stand 07.10.2026:** Eine Sonde (Lauf 37495714708, `run_suite_isolated.py --release
  --ci-group windowed`) fand außerhalb von Windows 31 rote Fälle in 23 Testfunktionen. Behoben
  und über `fenster-auswahl.yml` auf allen vier Plattformen grün (Läufe 37556091095,
  37560540258): Return öffnet am Mac den gewählten Listeneintrag (`return_opens` an
  Startfläche, Befehlspalette und Prüfbericht, Anschlusstest und Wächter in
  `test_native_keys.py`), die Befehlspalette misst ihre Kürzelspalte mit gebrochenen Metriken,
  und zwölf Tests messen die Zusage statt einer Windows-Eigenheit (Aktualisierungsweg,
  Kürzelschreibweise, Zeitgeber, Fäden, Kantenglättung, Menüeinzug). **Offen**, mit Plattform
  (U Linux, A macOS ARM, I macOS Intel): `test_widget_lifetime[KeyDialog]` (UAI, einer von
  zehn überlebt), `test_a_button_wraps_its_label_instead_of_cutting_it` (UAI, der Knopf bricht
  nicht um), `test_no_element_of_the_bar_is_squeezed` (UAI, Felder 356/364 statt 398/404 px bei
  1600 px), `test_a_long_setup_failure_stays_in_the_scroll_area` (UAI, kein Rollbalken bei 200
  Zeilen), `test_the_sketch_area_fits_a_laptop_screen` (AI, 977 statt höchstens 900 px),
  `test_the_left_column_shares_its_height_with_all_four` (AI, Objekte 104 px, Boden 182 px bei
  900 px Fensterhöhe), `test_chat_setup_follows_late_status_text…` (AI, der Text des
  Schlüsseldialogs ist 105 statt 120 px hoch und rollt nicht) und
  `test_black_lit_surfaces_still_show_their_shape` (I, Kontrast genau 10 bei verlangten mehr
  als 10; Renderer, RM-344). Jeder Fall wird zuerst am Paket seiner Plattform nachgestellt:
  ob der Test irrt oder der Kunde es sieht. Die Winkelbedingung auf dem Intel-Mac führt
  [RM-541](#rm-541). Danach die Umstellung in `build.yml`, die Wächter in
  `test_packaging.py`, der Slicer-Job und die Unterlagen.

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

  **Stand 06.10.2026:** Plan bis 01.11. mit Takt und Messpunkten
  (`marketing/reichweite/analyse-und-plan.md`, `36487f9b`) und eine Contentserie vom 28.09. bis
  15.10. (36 YouTube-, 18 Facebook-Filme; ihr README sagt „hochgeladen“) unter
  `marketing/content-2026-10/`, beide lokal und seit `01eea2225` nicht versioniert.
  Plattformstand und Messungen sind nicht nachgesehen. Offen: Roberts Bestätigung des Plans und
  die Montagsmessungen; der Punkt schließt, wenn Robert den Plan bestätigt.

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

- [~] **RM-061 — Verkaufsbereitschaft und Ende der Demo vorbereiten.** Bei geklärter Anmeldung,
  Zahlung und Rechtstexten bis 25.10. einen Verkaufskandidaten vorbereiten. Der **31.10. bleibt
  für letzte Optimierungen reserviert**; Verkaufsstart ist am **01.11.2026 um 10:00 Uhr
  Europe/Berlin** (Robert, 16.09.). Grundlage ist das
  [Übergangskonzept](konzepte/konzept-demo-zu-1.0-2026-09.md): Ablauf alter Demos und laufender
  Sitzungen, Aktualisierung und Projektübernahme, Kaufzustellung, Geräteaktivierung und
  Veröffentlichung nach §§5–13 umsetzen; Abnahmefälle T01–T32 und Freigabekriterien §§15–16
  erfüllen. Der Ist-Zustand vom 16.09. hat noch keinen täglichen Ablaufwächter und keinen
  Bestell-Webhook im Repository; am 06.10. fehlen beide in `website/api/` und `tools/`
  weiter. **Gebaut in 0.5.0 (`29dcefa4`):** Abschied mit Pause und Start, „heute letzter
  Tag“, Hinweis ab 24.10. **Uhr-Rückstellfehler I03a am 16.09. lokal behoben:**
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

  **Aus dem Lizenzarten-Konzept (§6, P7):** Handbuch (`app/core/manual.py`, seit `334f73b73`)
  und Über-Dialog nennen die Lizenzart (privat oder gewerblich, Platzzahl), ebenso die Karte
  `app/core/activation/CLAUDE.md`. Die Altaussage, das Handbuch nenne sie nicht, steht noch in
  `konzepte/konzept-lizenzarten-2026-09.md`.

<a id="rm-091"></a>

- [ ] **RM-091 — CRA-Meldebereitschaft herstellen, die Frist ist abgelaufen.** Die in
  SECURITY-INCIDENT.md
  festgelegte Meldebereitschaft praktisch nachweisen: EU-Login und Plattformzugang, Vertretung,
  CSIRT-Zuordnung und Alarmierung prüfen; den Probelauf bis vor dem Absenden durchführen und privat
  protokollieren. Keine fingierte Meldung senden. **Die Meldepflicht aus Art. 14 gilt seit dem
  11.09.2026** — der Punkt stand als Vorbereitung vor dieser Frist, und die ist vorbei; die fünf
  Bereitschaftspunkte in SECURITY-INCIDENT.md (EU-Login, Vertretung, CSIRT-Zuordnung,
  Alarmierung, Probelauf) sind am 06.10.2026 alle offen.
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
  [konzept-lizenzarten-2026-09.md](konzepte/konzept-lizenzarten-2026-09.md) §3, und die
  zweite Lizenzart ist mit [RM-182](ROADMAP-ARCHIV.md#rm-182) gebaut. Was hier offen bleibt,
  sind Anbieter, Bestellstrecke, Lieferung, Widerruf und Signierung — bis 15.10.

  **Bestätigt am 23.09.2026** (Robert): zwei Lizenzarten, keine dritte Stufe; „drei Stufen“
  ist aus Presse und Texten gestrichen (`9145aedc`). Die Presseentwürfe 05, 22 und
  `VERSAND.html` sind nachgezogen. Die Website nennt beide Preise seit 23.09. (`6759555da`).

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

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
     Art. 246a EGBGB „klar und verständlich"). Seit die Preise auf der Seite stehen, verlinken
     alle fünf fremdsprachigen Startseiten AGB und Widerruf, und zwar die deutsche Fassung
     (`tests/test_legal.py::test_sale_texts_appear_with_the_first_price`); die Frage nach der
     Vertragssprache ist damit konkret.
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

  **Und eine Spannung zum Vormerken:** Die Startseite sagte unter „Kein Team" zu, es gebe „keine
  Hotline, keine Antwort um drei Uhr nachts". Die gewerbliche Lizenz sagt seit dem 15.09.2026
  eine Antwort binnen zwei Werktagen zu. Wenn die Preise auf die Seite kommen, gehört dieser
  Absatz mitgelesen. **Stand 06.10.2026:** Die Preise stehen auf der Seite; „drei Uhr nachts“
  ist seit `fede439a5` weg, dieselbe Seite sagt „keine Hotline“ und „Antwort des Supports
  innerhalb von zwei Werktagen“. Ob beides so stehen bleibt, liest und entscheidet Robert mit
  den übrigen Rechtstexten.

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

<a id="rm-116"></a>

- [ ] **RM-116 — Historische Statistikreste auf dem Server behandeln.** Den alten öffentlichen
  Statistikordner auf dem Server erneut prüfen und die historischen Zählzeilen nach Roberts
  Entscheidung entfernen. Abnahme: kein pseudonymer Altbestand mehr im Dokumentenstamm und der
  aktuelle Zähler schreibt ausschließlich in den privaten Ort.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#030-ist-draußen-03092026).

<a id="rm-145"></a>

- [ ] **RM-145 — CRA-Konformitätsakte zum gesetzlichen Anwendungszeitpunkt vorbereiten.** Bauplan §37.3 führt die allgemeinen CRA-Pflichten ab dem 11.12.2027.
  RM-091 behandelt Meldebereitschaft, dazu kommt die mit RM-115 durchgesetzte Releaseakte; beide ersetzen keine vollständige
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
  gesetztem `TRIAL_FROM`. Die EULA lässt eine spätere Testphase ausdrücklich zu (§4).
  Zu entscheiden: der Termin; ob Geräte mit altem Demo-Marker die Testphase ebenfalls bekommen
  (heute schließt T15 im Übergangskonzept das aus — damit erreichte ein Januar-Termin die
  Unentschlossenen aus der Demo gerade nicht); welcher Release sie trägt und wann er vor dem
  Termin draußen sein muss. Abnahme: 1.x-Build mit gesetztem `TRIAL_FROM`, Frist je Gerät von
  14 Tagen, danach derselbe lesende Zustand wie ohne Testphase (I09), Tests analog
  `test_a_sale_version_carries_no_deadline`, Website, Kauftexte und Changelog nennen sie.

<a id="rm-351"></a>

- [~] **RM-351 — Die Website bietet 0.5.1 an und nennt im Downloadhinweis 0.5.0 als signierte Fassung.**
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
  **Stand 06.10.2026, deshalb `[~]`:** Der Hinweis lautet seit `1d9373efa` (04.10., in v0.5.2
  und v0.5.3) in allen sechs Sprachen versionsneutral „ab 0.5.0 digital signiert“
  (`website/index.html`, `website/en/index.html`, `website/{es,fr,it,pt}/index.html`). Der
  Wächter aus der Abnahme fehlt; in der beschriebenen Form würde er die neue Fassung („ab
  0.5.0“) ablehnen. Offen: ein Wächter, der nur die erste signierte Fassung zulässt, oder
  Roberts Verzicht, weil der Satz keine Version mehr an das Angebot bindet. Der Live-Stand ist
  nicht nachgesehen.

<a id="rm-528"></a>

- [ ] **RM-528 — Die Installation kennt nur einen Release-Schlüssel.** `app/core/updates.py` prüft die
  Versionsdatei gegen genau einen Schlüssel (`RELEASE_PUBLIC_KEY`). Bauplan §37.2 verlangt
  mehrere zulässige Schlüssel, damit ein neuer eingeführt werden kann, solange der alte noch
  unterschreibt; vor dem Verkauf ist ein neues Schlüsselpaar geplant. Wechselt der Schlüssel
  ohne diesen Umbau, verwirft jede ausgelieferte Installation die neue Versionsdatei und sieht
  keine Aktualisierung mehr. **Entschieden (Robert, 06.10.2026):** Schlüsselliste bauen und in
  einer Version ausliefern, bevor der Schlüssel wechselt. **Abnahme:** Test mit zwei
  Schlüsseln (alter und neuer unterschreiben gültig, ein fremder nicht), `sign_version.py`
  und Signierdoku nennen den Ablauf des Wechsels. Bauplan §37.2.

## Kundenrückmeldungen

<a id="rm-062"></a>

- [~] **RM-062 — Eingabemethode im aktuellen Flatpak bestätigen.** Die Fcitx-Berechtigungen und der
  X11/XWayland-Startweg sind gebaut. Auf der aktuellen ausgelieferten Fassung Start ohne
  Zusatzschalter, Fokus sowie Tastatur/IME in Eingabefeldern prüfen; Paket, Desktop, Qt-Plattform
  und Eingabemethode dokumentieren. Abnahme durch aktuellen Kundenbericht oder reproduzierbaren
  Linux-Lauf; nativer Wayland ist davon getrennt.

  Seit 0.5.2 installiert jedes Release das Flatpak und startet es ohne Zusatzschalter unter
  Xvfb mit Sitzungsbus (`build.yml`); die Fcitx-Rechte stehen im Manifest
  (`packaging/de.rsdigital.solidon3d.yml`). Das belegt den Start unter X11, nicht Fokus oder IME.

  **Gemessen am ausgelieferten Flatpak 0.5.3 (06.10.2026, Runner genügt —
  Entscheidung Robert):** Läufe
  [37507999423](https://github.com/RS-Digital-Studio/Solidon/actions/runs/37507999423)
  und [37524814548](https://github.com/RS-Digital-Studio/Solidon/actions/runs/37524814548),
  ubuntu-24.04, Xvfb, Fcitx 5.1. Das Paket startet ohne Zusatzschalter auf X11.
  Im Paket liegen die Qt-Eingabemodule `compose`, `ibus` und `qtvirtualkeyboard`,
  **kein Fcitx-Modul**. Mit `QT_IM_MODULE=fcitx` lädt Qt `compose`, und Fcitx5
  bekommt keine Eingabesitzung; mit `ibus` legt Fcitx5 über seine
  IBus-Schnittstelle eine mit Fokus an, und „Würfel ß äöü“ kommt im Textfeld an.
  **Abhilfe:** `qt_platform.prefer_an_input_method_qt_has` setzt bei Fcitx in
  der Umgebung ohne beiliegendes Fcitx-Modul vor dem Qt-Start `ibus` — auch für
  eine Liste in `QT_IM_MODULES` (GNOME, Sway) und für KDE mit nur
  `XMODIFIERS=@im=fcitx`. Außerhalb des Flatpak prüft Qt 6.11 für IBus
  `ibus-daemon` im PATH (Quelltext `qibusplatforminputcontext.cpp`), den ein
  reines Fcitx5-System nicht hat; antwortet Fcitx5 als
  `org.freedesktop.portal.IBus`, setzt die Anwendung `IBUS_USE_PORTAL=1`. Der
  Fehlerbericht nennt jeden Vorwert; der Starttest des Pakets verlangt unter
  Linux das IBus-Modul. **Offen:** am nächsten Paket (Workflow
  `.claude/.state/flatpak-abnahme-2026-10-06/abnahme-eingabe.yml` erweitern):
  Flatpak mit `QT_IM_MODULE=fcitx`; AppImage und tar.gz aus demselben Bau mit
  Fcitx5 (a) ohne `ibus`-Paket, (b) mit installiertem, nicht laufendem
  `ibus-daemon`, (c) mit `ibus-daemon`, den Fcitx5 ablöst; dazu
  `QT_IM_MODULES=wayland;fcitx` und nur `XMODIFIERS=@im=fcitx`. Je Fall
  Fcitx-Protokoll (`--verbose=ibusfrontend=5`) mit Eingabesitzung und Text im
  Feld.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-erste-kundenbericht-aus-dem-feld-27082026).

<a id="rm-521"></a>

- [~] **RM-521 — Cura unter Linux slicen lassen (AppImage und Flatpak).** Solidon findet Cura als
  Flatpak samt 642 Druckern, rechnen kann es damit nicht, als AppImage findet es weder Drucker
  noch Rechenmaschine. Gemessen am Runner (Diagnoselauf 37340935632): Cura 5.13 ist mit
  appimage-builder gepackt, `CuraEngine` nennt seinen Lader relativ (`lib64/ld-linux-x86-64.so.2`),
  der Lader liegt unter `runtime/compat` samt eigener glibc 2.35, und die Bibliothekspfade stehen
  in `AppRun.env`. Ein Aufruf über `--command` oder mit `--cwd` scheitert mit „required file not
  found“; beim AppImage steckt alles im Abbild, das nur zur Laufzeit eingehängt ist.
  **Entscheidung Robert:** CuraEngine über Curas Lader aus `runtime/compat` mit dem Pfad aus
  `AppRun.env` starten (beim AppImage nach `--appimage-mount`), oder Cura unter Linux nur im
  Fenster öffnen und das im Druckdialog sagen. Bis dahin endet ein Slicen mit „keine Druckdatei“.
  **Entschieden (Robert, 06.10.2026):** CuraEngine über Curas eigenen Lader aus
  `runtime/compat` mit dem Bibliothekspfad aus `AppRun.env` starten, beim AppImage über
  `--appimage-mount`; findet Solidon den Lader nicht, öffnet es Cura nur im Fenster und
  sagt das im Druckdialog.

  **Gebaut** (`export/cura_linux.py`, Regel in `kern.md`): Flatpak über
  `flatpak run --filesystem=<Arbeitsordner> --command=/app/cura/runtime/compat/<Lader>` mit dem
  vollständigen Pfad aus `AppRun.env`, AppImage für den Lauf eingehängt, aus Solidons Flatpak mit
  `TMPDIR` im Austauschordner und `flatpak-spawn --watch-bus`; Definitionen beider aus ihrem
  Bestand, die Drucker der AppImage-Cura aus einer Kopie je Fassung im Nutzer-Cache (am Runner
  3,3 s beim ersten Mal), angelegt von einem Arbeiter, nie im Fensterfaden; Kopien entfernter
  Fassungen werden geräumt. Kann Solidon nicht rechnen, sperrt der Druckdialog *Slicen* mit einem
  Satz ohne behauptete Ursache, das Fenster bleibt. Belegt am Runner (Lauf 37528397381, Cura 5.13.0): Würfel auf dem K1 Max aus Curas
  639 Druckern, Flatpak und AppImage, draußen und im Sandkasten mit den Manifestrechten — je
  100 Schichten, 2945 Extrusionen, 1391,5 mm Filament, gleich wie CuraEngine 5.13 unter Windows;
  keine Einhängung bleibt, auch nicht nach SIGKILL an `flatpak-spawn`.
  **Offen:** die Abnahme beim Kunden mit dem nächsten Paket (Ubuntu 24.04, Solidon als Flatpak).

<a id="rm-522"></a>

- [ ] **RM-522 — Dem Linux-Kunden mit Orca als Flatpak die Behebung melden.** Kundenmeldung
  vom 05.10.2026 zu 0.5.2 (Ubuntu 24.04, Orca 2.5 als Flatpak, keine Drucker und Profile, RM-064).
  Die erste Antwort sagt nur zu, dass nachgestellt wird. Zugesagt ist eine zweite Nachricht, sobald
  feststeht, ob die nächste Version es behebt: Ursache in zwei Sätzen, die Versionsnummer und dass
  die Flatseal-Freigabe für den Session-Bus nicht nötig ist. Entwurf in Roberts lokaler Ablage.
  Abnahme: nach dem Release versandt, Versandstatus dokumentiert.

  Text für 0.5.3 fertig (06.10.2026) in Roberts lokaler Ablage; jede Aussage darin ist am
  ausgelieferten Paket belegt (RM-064 im Archiv) oder durch einen Test aus 0.5.3
  (`test_the_portal_copy_of_a_launcher_is_remembered_as_the_launcher`). Robert
  schickt ihn; danach den Versand hier eintragen.

<a id="rm-532"></a>

- [~] **RM-532 — Gewinde in jedem Maß: Bereichsnachweis, Tor und Zusammenführung.**
  Kundenvorschlag S-20261006-c66299 (0.5.3, ohne Rückadresse): Ein Innengewinde in einem Rohr mit
  mindestens 60 mm Innendurchmesser ging nicht, *Druckbares Gewinde* endete bei M8. Robert:
  „keine Beschränkungen“.

  **Gebaut** auf dem Zweig `gewinde-eigenes-mass` (ein Commit `63d7a7826` auf `a2b7451b6`, 41
  Dateien; dieselben Änderungen liegen ungestaged im Arbeitsbaum des Rechners, auf dem sie
  entstanden):
  - Baustein: Größe *Eigenes Maß* (`fasteners.CUSTOM_SIZE`), Nenndurchmesser 2 bis 1000 mm vorn,
    Steigung hinten (null ist die Regelsteigung, `standards.regular_pitch` über die neue Tabelle
    `pitches` M10 bis M64 nach der ISO-262-Auswahl); `thread_measure`, Absage `no_core` bei einer
    Steigung ohne Kern.
  - Bohrung: Ohne Tabellengröße wählt `custom_thread_for` das Maß, dessen Kernloch die Bohrung
    ist (Ø 60 → Ø 66,6 mit Steigung 6, Ø 6,5 → Ø 7,6 × 1); der Satz über dem Dialog nennt es.
  - Gegenstück: `counterpart.thread_values_for` ersetzt `thread_size_for` — Tabellengröße oder
    eigenes Maß, Absage nur außerhalb der Grenzen (`beyond_threads`); ein geänderter Schritt
    koppelt über das ganze Maß.
  - Gemeinsame Grenzen `units.SMALLEST_THREAD`, `LARGEST_THREAD`, `COARSEST_PITCH`, auch für
    *Schraube erstellen* (war Ø 100) und *Drehdeckel erzeugen* (war Ø 400).
  - Netz: Sehnen je Umlauf nach der Facettenregel (`shapes.turn_segments`, bis Ø 46 unverändert
    48), Drehdeckel ebenso (`lid.turn_sections`, `cache_version` 7).
  - Texte in sechs Sprachen, zwei Handbuchabsätze, Website 61 → 76 hinterlegte Normmaße, Karten,
    Regel `bausteine.md`, Begründungen. Tests: Rohrfall, Paar mit eigenem Maß an beiden Kernen,
    Gegenstück Ø 66,6, Drehdeckel Ø 300, Tabellenprüfung, Sehnenregel. Sonde am echten Fenster:
    An einer 60-mm-Bohrung steht *Eigenes Maß* mit Ø 66,60 mm vorbelegt, vier Felder vorn.

  **Offen, in dieser Reihenfolge:**
  1. Bereichsnachweis: Alle 49 Bausteine sind veraltet (gemeinsame Formen und Normteiltabelle
     geändert). `tools/check_part_ranges.py` auf dem Zweig fahren und `part_ranges.toml`
     committen; `printed_thread` hat jetzt 256 Ecken bis Ø 1000 und läuft am längsten. Während
     des Laufs weder Bausteindateien noch `shapes`, `build` oder `standards` ändern, sonst ist er
     wertlos.
  2. Volles Entwicklungstor auf dem Zweig. Der letzte Lauf (auf `306ff7bf2`) hatte zehn rote
     Tests; neun sind auf dem Zweig behoben (alte Signatur von `_printed_thread` im Test,
     `beyond_threads` einsortiert, totes Wertlabel `nearest`, Eckenzahl 7306, Zeilenumbruch vor
     §13.4, Website-Zahl, Steigungssatz zu lang), der zehnte ist der Bereichsnachweis. Seitdem
     nicht neu gefahren.
  3. Merge nach main (Kataloge bei Konflikt je Schlüssel vereinigen), dann der Sitzung „Stift
     für Bohrung“ (Fragebogen S-20261006-5be329) den Hash nennen: Sie baut den Gewindebolzen
     auf `thread_values_for`, `CUSTOM_SIZE` und `thread_measure` und wartet darauf.
  4. Danach auf dem Rechner, auf dem es entstand, die ungestagten Gewindeänderungen nicht noch
     einmal übernehmen; sie sind dann über main da.
  5. Beim Release: Handbuch erzeugen (die Erzeugnisprüfung in `test_wording` meldet die zwei
     geänderten Absätze), das Bild *Ein Gewinde in eine Bohrung* nur bei Änderung.
  6. Entscheidung Robert: *Schraube*, *Gedruckte Mutter*, Schraubenloch, Mutternfalle und
     Einpressbuchse bleiben an der Normteiltabelle M2 bis M8 (Kopf, Schlüsselweite, Scheibe).
     Soll die Tabelle bis M64 wachsen, mit Herstellerdaten je Größe?

  Abnahme: Bereichsnachweis passt zu allen 49 Bausteinen, Tor grün, auf main gemergt. Eine
  Kundenantwort entfällt, der Vorschlag kam ohne Rückadresse.

<a id="rm-072"></a>

- [ ] **RM-072 — Zusagen an den Dental-Kunden zum Verkaufsstart erfüllen.** Den Dental-Kunden
  spätestens zum Verkaufsstart über den Kaufweg und nach belastbarer 3D-Maus-Verfügbarkeit über die
  Unterstützung informieren. Abnahme: beide Anlässe mit tatsächlichem Versandstatus dokumentiert;
  bereits versandte Nachrichten bei der Bearbeitung zuerst prüfen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#eine-kundenanfrage-aus-dem-dentalbereich-30082026).

<a id="rm-533"></a>

- [~] **RM-533 — Entf tut an der Auswahl still nichts (Fragebogen S-20261006-5be329).** Kunde:
  „die Entf taste löscht weder Merkmal noch Körper je nachdem was ausgewählt ist“. Am HEAD mit der
  Sitzungsdatei des Fragebogens nachgestellt (offscreen): Mit Fokus in Objektbaum oder Ansicht
  entfernt Entf Körper und Merkmal richtig. Still bleibt die Taste in zwei Lagen. Erstens liegt
  der Fokus im Reiter *Auswahl* (nach einem Maßfeld oder Knopf dort), und `_scope_shortcut` band
  Entf nur an Baum und Ansicht. Zweitens hält die Kette an einem Schritt (im Kundenprotokoll
  mehrfach: Fase, Verrunden, Merkmal entfernen) oder die Lizenz sperrt; dann sind *Objekt
  entfernen* und *Merkmal entfernen* gesperrt, und Qt führt ein gesperrtes Kürzel ohne jede
  Rückmeldung nicht aus.

  Gebaut, nicht committet (Tor abgebrochen, Robert 06.10.: Stopp): `_scope_shortcut` merkt die
  Aktionen in `_scoped_actions`, `_build_feature_dock` hängt sie an den Reiter; Text- und
  Zahlenfelder behalten Entf über `ShortcutOverride`. Ein Zuhörer `_DeleteRefusal` am Filter der
  Anwendung (`app_events`; keine zweite Aktion auf Entf, sonst `test_no_two_shortcuts_in_the_window_collide`)
  ruft `MainWindow._refuse_delete`: Mit Auswahl, Fokus in Baum, Ansicht oder Reiter und Halt
  oder Sperre sagt die Statuszeile „Objekt entfernen: Die Kette hält an Schritt 11 (Verrunden)
  an — …“; ohne Auswahl bleibt die Taste stumm (beim Messen gehört sie dem letzten Maß). Satz in
  `grenzen.md` („nackte Tasten bleiben an Objektbaum, Ansicht und Reiter *Auswahl*“).
  Fenstertest `test_delete_answers_in_the_selection_tab_and_says_why_when_it_cannot` in
  `tests/test_interface_limits.py` grün; Gegenproben ohne Fix und ohne Zuhörer rot. Die Hunks
  liegen ungesichert im Arbeitsbaum des i9 und als Patches gegen `3a5d607f3` unter
  `.claude/.state/umfrage-5be329-2026-10-06/` (`entf-*.patch`, Sonde `sonde_entf.py`).

  Aus demselben Fragebogen erledigt: `c3e68671e` (das angehängte Absturzprotokoll war eine
  überlebte COM-Ausnahme `0x8001010d`; der Bericht hängt nur noch an, was der Prozess nicht
  überlebt hat) und `306ff7bf2` (am HEAD roter Zähltest seit `d3134f3d8`).

  **Offen:** Tor über HEAD plus diese Hunks, dann Commit nur der eigenen Hunks (in
  `main_window.py` und `grenzen.md` liegen fremde daneben). Der Titel der Ansage kommt heute aus
  `feature_instead_of(...) or delete_object`; `_removal_entry()` der Rechtsklick-Arbeit
  (Fragebogen S-20261006-5c132b) gibt dieselbe Auskunft richtiger (Baustein) — sobald sie auf main
  ist, darauf umstellen, sonst bleibt ein Zwilling. **Abnahme:** Am echten Fenster entfernt Entf
  mit Fokus auf einem Knopf im Reiter die Auswahl, im Zahlenfeld ändert es die Zahl, bei Halt
  nennt es den Grund.

<a id="rm-534"></a>

- [ ] **RM-534 — Der Prüfbericht zeigt während einer Neuberechnung alte Fehler als gültig
  (Fragebogen S-20261006-5be329).** Kunde: „manchmal wird im Prüfbericht auch Fehler angezeigt und
  kurz darauf ist die Berechnung erst fertig“. Gemessen am HEAD `3a5d607f3` mit der Kundendatei
  (Bericht `pruefbericht-bericht.md` im Zustandsordner von RM-533): Beim Wechsel des Radius
  2,0 → 1,0 (Schritt 18) bleibt die Zeile „Der Radius ist für diese Kanten zu groß“ mit voller
  Schwere stehen, der Kopf sagt „Übergabe nicht empfohlen“, die Statuszeile „Die Kette hält an“ —
  3,7 s lang, bis das Ergebnis kommt. Der Hinweis „Die Bewertung läuft“ wird gerade dann
  unterdrückt (`ReportPanel`: `self._review_missing and not counts["error"]`). Widerlegt sind
  Zwischenstände aus dem Bild zuerst, `check_states` und die Vorschau eines offenen Dialogs.
  Dazu ein eigener Fehler: Ein Halt im Entwurf gilt als fein. `evaluate.py` bricht beim Halt ab,
  bevor `reads_quality` gesetzt wird, `fine_current` ist wahr, und Druckdialog und Export rechnen
  die volle Kette nie, obwohl der Satz „… sagt erst die vollständige“ sie ankündigt. Am
  Kundenschritt 6 (*Merkmal entfernen* am Stift) bestätigt die volle Kette den Fehler mit dem
  besseren Satz („das Werkzeug deckt ihn vollständig ab“); der Kunde nahm zweimal *Reparieren und
  erneut versuchen*, das dort nicht helfen konnte.

  **Fix in vier Teilen (Entscheidung aus Kundensicht):** (1) Läuft eine Auswertung länger als
  200 ms, sagt der Kopf „Wird neu berechnet …“; alte Zeilen bleiben als voriger Stand sichtbar,
  mit Text als zweiter Kodierung (Regel 18), ihre Knöpfe gesperrt, die Reitermarke zählt sie nicht
  neu, die Haltansage weicht dem Fortschritt; `print_contract.handoff_state` bekommt den
  Laufzustand als eigenen Eingang. (2) Hält der Entwurf mit `BooleanFailedError` ohne Voxelstufe
  an, rechnet die Sitzung die volle Kette einmal selbst; bis dahin steht der Laufzustand, kein
  Fehler; *Voxelstufe erzwingen* bleibt. (3) Ein Halt im Entwurf ist nie `fine_current`. (4) Das
  feine Urteil gilt für folgende Entwurfsläufe, solange Schritt und Eingang gleich sind — kein
  Hin und Her. Tests, die heute Verhalten zusichern und bleiben: `test_print_contract.py`
  (Übergabezustand ohne Lauf), `test_boolean.py` (Entwurfssatz), `test_ui.py` (`use_voxel_stage`);
  der Halt gehört neben RM-494 in `test_evaluation.py`. **Abnahme:** Während eines Laufs steht
  kein alter Fehler als gültig da; ein Export nach einem Entwurfshalt rechnet fein.

<a id="rm-535"></a>

- [ ] **RM-535 — Merkmal verschieben: Felder fehlen an Flächen, Karte und Operation sind uneins,
  drei falsche Ergebnisse ohne Befund (Fragebogen S-20261006-5be329).** Kunde: „das Verschieben
  mit Maßen bei Bohrungen ist gut, bei anderen Merkmalen fehlen sie“. Gemessen an HEAD
  `3a5d607f3`, der Kundendatei und sechs Modellen mit 734 Merkmalen (Bericht
  `verschieben-bericht.md` im Zustandsordner von RM-533): X/Y/Z stehen an Bohrung, Sackbohrung,
  Langloch, Zapfen, Senkung, Verjüngung, Kugel, Einschluss, Wulst und Kehle. Keine Zeile haben
  Verrundung, Fläche, Schrägfläche, gerundete Seite, Muster und Gewinde (Sätze in
  `perceive/actions.py`); gesperrt sind Kegelstück, Kugel oder Kegel ohne eigenen Körper und die
  Sackbohrung mit Zapfen. Am Kundenmodell haben 16 von 190 Merkmalen Felder, 174 keine (117
  Verrundungen, 42 Flächen). Ursache ist `MOVABLE_KINDS` (`prepare_ops.py`), und die Karte
  überspringt Zeilen ohne Handlung (`panels.py`, seit `fad4a15c5`, Test in
  `test_feature_panel.py`); `app/core/perceive/CLAUDE.md` und `fenster.md` beschreiben das
  Gegenteil. Der Flächenzug legt `push_face` sofort an, ohne Zahl und *Übernehmen*.

  Fehler unabhängig von den Entscheidungen: An Wulst und Kehle stehen Felder, `move_feature`
  sagt an allen vier geprüften Ringen ab (die Karte prüft nur `torus_is_the_body`, die Operation
  auch `_torus_rims`). An der Sackbohrung mit Zapfen umgekehrt: Die Karte sperrt, die Operation
  rechnet über `_air_of_the_bore`, und nach 0,5 mm erkennt Solidon zwei Sackbohrungen weniger.
  Der Griff fragt nur die Art (`viewport.py`): An gesperrten Merkmalen endet sein Zug mit „Die
  neue Stelle steht rechts unter Auswahl.“, an einer Verrundung greift er den Körper. Falsch ohne
  Befund: Zapfen im Kundenmodell 0,5 mm in die Taschenwand −189 mm³ (danach 4 statt 6 Zapfen),
  Zapfen Ø 30 im mini-pot bei 0,2/0,5/1,0 mm immer +240,65 mm³, Endfase am Stift bei 0,2 mm
  +2218 mm³.

  **Vorschlag:** Flächen bekommen *Fläche versetzen* mit dem Feld „Weg“ (erste Zeile in
  `ACTION_ORDER` als `("move_feature", "push_face")`, der Weg beginnt bei 0); Karte, Operation und
  Griff fragen dieselbe Funktion; eine zusammengelegte Absage steht wieder als Zeile.
  **Entschieden (Robert, 06.10.2026):** (a) „alles einheitlich, Bohrung Vorbild für alle
  Funktionen“ — der Flächenzug schlägt vor wie an der Bohrung, *Übernehmen* rechnet; (b)
  nicht geltende Handlungen stehen wieder als eine Zeile mit Grund; (c) *Merkmal verschieben*
  führt an Zapfen, Senkung, Verjüngung, Kugel, Ring und Einschluss ins Bild mit Maßgruppe
  (ändert die Entscheidung vom 10.09.); (d) „beides einzeln handhaben und Tasche allein
  bearbeitbar und Zapfen“ — Tasche und Zapfen je einzeln bearbeitbar. Wulst/Kehle fragen in
  Karte und Operation dieselbe Funktion (`398c7ea43` auf `kunden/rm-535`). **Abnahme:** Ein Test über echte Netze, der heute an Ring und Sackbohrung mit Zapfen
  rot ist; die drei falschen Ergebnisse rechnen richtig oder sagen mit Grund ab.

<a id="rm-536"></a>

- [ ] **RM-536 — Stift für Bohrung baut das passende Gegenstück zu Gewinde und Senkung
  (Fragebogen S-20261006-5be329).** Kundenwunsch: „… wenn man ein Gewinde bei der Bohrung oder
  Senkung hat, dass man dafür auch das passende Gegenstück mit der Funktion erzeugen könnte“.
  Heute baut `pin_for_bore` (`geom/lid_hinge.py`) einen glatten Zylinder (Bohrung minus Spiel,
  so lang wie die Bohrung). Soll: Eine Senkung an der Mündung (Kette über
  `relations.cavity_chain_state_at`) gibt einen bündigen Senkkopf im Winkel der Senkung, eine
  Ansenkung einen Zylinderkopf, ein Innengewinde auf derselben Achse ein Außengewinde derselben
  Größe und Steigung mit Spiel — über `counterpart.thread_values_for` und den Gewindebaustein in
  `fasteners.py` (Tabellenmaß, sonst `CUSTOM_SIZE`; dieselben Absagen für links-, mehrgängig und
  kegelig). Ein neuer Parameter hinter der Klappe wählt „passend zur Bohrung“ (Vorgabe) oder
  „glatter Stift“; bestehende Projekte behalten ihr Ergebnis über eine Migration (Format 46 → 47,
  Muster `_keep_slot_tools_as_they_were`). `leaves_inputs_unchanged` bleibt wahr (`outputs[0]` ist
  der unveränderte Träger, Zusage an `bbd41ff2d`); beide Kerne, `cache_version`, ein Befund nennt
  das Gebaute, Texte in allen Katalogen. Einzelheiten: `auftrag-stift.md` im Zustandsordner von
  RM-533. **Wartet auf** den Merge von RM-532 (Zweig `gewinde-eigenes-mass`) auf main — die
  Schnittstelle (`thread_values_for`, `CUSTOM_SIZE`, `thread_measure`, `size_for_thread`,
  `custom_thread_for`) ist zugesagt, gebaut wird erst darauf. **Abnahme:** Korpustests an
  `plate_countersunk.stl`, `plate_countersunk_blind.stl` und einer Bohrung mit
  `insert_printed_thread`, Sollwerte mit Herkunft, Gegenprobe; eine alte Projektdatei mit Stift
  rechnet unverändert.
