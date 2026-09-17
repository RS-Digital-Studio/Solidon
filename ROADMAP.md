# ROADMAP — Arbeitsliste

Abgleich vom **08.09.2026** gegen Bauplan §40, Quelltext, Tests, Paketmetadaten
und Git-Verlauf, **nachgeführt am 10.09.2026** — jeder offene Punkt einmal am
heutigen Code nachgemessen; was dabei erledigt, überholt oder falsch
beschrieben war, steht am Punkt. Der lokale Veröffentlichungsstand ist
**0.4.1** (`website/version.json`, seit dem 14.09.2026; die Mac-Pakete sind
signiert und notarisiert, das Windows-Setup nicht, siehe RM-001). Die früheren Durchsichten und Messreihen stehen im
[Archiv](ROADMAP-ARCHIV.md); dessen
[Abgleichstabelle](ROADMAP-ARCHIV.md#abgleich-der-gesamten-roadmap-mit-dem-bestand-08092026)
erklärt für jeden vorher offenen Punkt, ob er bleibt, erledigt, überholt oder
mit einem anderen Punkt zusammengeführt ist.

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
| [RM-184 — Dateiaudit vollständig umsetzen](#rm-184) | Geometrie, Erkennung und Druckvorbereitung | Nativer Ablauf der Dichtnut am Fenster; die übrigen Familien und die Einzeldateiabnahme aller 187 Fälle sind zurückgestellt |
| [RM-186 — Die Erkennung findet die Stirnfläche eines Gewindebolzens auf Windows, auf Ubuntu nicht](#rm-186) | Geometrie, Erkennung und Druckvorbereitung | Die drei Baumtests zählen seit dem 16.09.2026 die Merkmale des Schritts und sind auf beiden Plattformen wahr; offen bleibt, warum eine 22-mm²-Stirnfläche auf Ubuntu unter die Erkennungsschwelle fällt — auf einer Linux-Maschine messen |
| [RM-001 — Signierung und Notarisierung der Kundenpakete belegen](#rm-001) | Plattformen, Pakete und Grafik | Mac ist mit 0.4.1 belegt; Windows ist seit dem 14.09. ein Kundenbefund — mit Smart App Control startet Solidon auf Windows 11 nicht, Certum-Zugang und `sign_release.py` einmal fahren |
| [RM-011 — Erstinstallation auf einem fremden Rechner abnehmen](#rm-011) | Plattformen, Pakete und Grafik | Fremdrechner ohne Entwicklungsumgebung von Download bis Export prüfen |
| [RM-021 — Native Fensterlebensdauer am aktuellen Renderer abnehmen](#rm-021) | Plattformen, Pakete und Grafik | Der Riss in `test_ui.py` Teil 4 ist bis auf `processEvents` im Teardown eingegrenzt und trifft die Anwendung nicht; offen ist der Ereignistyp dahinter und die Gegenprobe auf Linux und Mac |
| [RM-050 — Kopierkosten messen und verbleibende VTK-Geometrie ablösen](#rm-050) | Plattformen, Pakete und Grafik | Kopier-/Pufferkosten messen und VTK aus der Bereichsprüfung ablösen |
| [RM-051 — Renderer und Grafiklaufzeit in Linux- und Mac-Paketen abnehmen](#rm-051) | Plattformen, Pakete und Grafik | Grafik und Eingabe der veröffentlichten 0.4.0-Pakete für Linux und Mac abnehmen |
| [RM-055 — Neue Paketwerkzeuge im installierten Kundenpaket abnehmen](#rm-055) | Plattformen, Pakete und Grafik | Flatpak-Lauf belegen; die CI baut mit Inno Setup 6 und protokolliert die Fassung nicht |
| [RM-104 — Verbleibende Mac- und Unix-Befunde mit aktueller CI-Abdeckung abnehmen](#rm-104) | Plattformen, Pakete und Grafik | Intel-Hänger und übrige Unix-Fenster-/Export-/Chatfälle abnehmen |
| [RM-107 — Ubuntu-Workerabbruch mit aktuellem Testbestand zuordnen](#rm-107) | Plattformen, Pakete und Grafik | Auslöser mit aktueller Testreihenfolge und Widget-/Worker-Lebensdauer eingrenzen |
| [RM-114 — Vereinfachungsziele auf Apple Silicon vermessen](#rm-114) | Plattformen, Pakete und Grafik | Hohlkugel-Zielreihe samt echter Warnung auf Apple Silicon messen |
| [RM-117 — Öffentliche Downloadlinks vollständig in die Paketprüfung aufnehmen](#rm-117) | Plattformen, Pakete und Grafik | Die stille Lücke ist zu; offen bleiben die Prüfsummen-Entscheidung und der Abruf gegen den Server für 0.4.0 |
| [RM-187 — Dieselbe Geometrie auf jeder Plattform](#rm-187) | Plattformen, Pakete und Grafik | Gemessen, zugeordnet und an der Wurzel behoben: Nicht manifold3d rechnete anders, sondern `np.cos`. Offen ist nur noch, ob nach der Umstellung auch die Fingerabdrücke des **Änderungswegs** auf allen drei übereinstimmen |
| [RM-005 — Wahl der Stiftseite gegen das fertige Stützvolumen prüfen](#rm-005) | Geometrie, Erkennung und Druckvorbereitung | Beide Stiftseiten am fertigen Stützvolumen vergleichen |
| [RM-017 — Nutfedermaße an realen Aluminiumprofilen prüfen](#rm-017) | Geometrie, Erkennung und Druckvorbereitung | Zwei benannte Aluminiumprofile nachmessen und Passung prüfen |
| [RM-022 — Phase zur Flächenrückgewinnung aus Netzen entscheiden](#rm-022) | Geometrie, Erkennung und Druckvorbereitung | Umfang und Genauigkeitsgrenzen einer eigenen Phase entscheiden |
| [RM-024 — Gespeicherte Zuordnungsantworten im echten Konfliktfall abnehmen](#rm-024) | Geometrie, Erkennung und Druckvorbereitung | Der Rundlauf steht; gemessen fehlt ein Korpuskörper, dessen erneute Erkennung wirklich mehrdeutig wird |
| [RM-041 — Innenraum importierter entlüfteter Hohlkörper klären](#rm-041) | Geometrie, Erkennung und Druckvorbereitung | Schätzweg oder dokumentierte Grenze des Innenraums entscheiden |
| [RM-042 — Leistungsgrenze der Merkmalserkennung bis eine Million Dreiecke klären](#rm-042) | Geometrie, Erkennung und Druckvorbereitung | Großen Korpus messen und belegte Erkennungsgrenze mit §31 abgleichen |
| [RM-045 — Drei Laufzeitkosten des Geometriereviews messen](#rm-045) | Geometrie, Erkennung und Druckvorbereitung | Aushöhlen, Formkopien und Innenraumketten getrennt vermessen |
| [RM-071 — Beschlossene Resin-Stufe 1 umsetzen](#rm-071) | Geometrie, Erkennung und Druckvorbereitung | Druckverfahren im Profil, zwei Resin-Bauräume und FDM-Regelbereiche bauen |
| [RM-076 — Topologieverlust beim Reduzieren von Eule und Spiderman beheben](#rm-076) | Geometrie, Erkennung und Druckvorbereitung | Eule und Spiderman mit Zielreihe und Topologievergleich reproduzieren |
| [RM-077 — Reduzierungsziel bei Körpern mit Durchbrüchen erreichen](#rm-077) | Geometrie, Erkennung und Druckvorbereitung | Zielreihen an Körpern mit Durchbrüchen gegen den vorhandenen Rückfall messen |
| [RM-078 — Ladezeit generierter Beispielmodelle an der Orientierung messen](#rm-078) | Geometrie, Erkennung und Druckvorbereitung | Eulenprojekt ohne Fremdlast öffnen und teure Schritte zuordnen |
| [RM-080 — Restumfang der Trennen-Serie mit aktuellem Code abgleichen](#rm-080) | Geometrie, Erkennung und Druckvorbereitung | Die Sichtflächen-Sperre ist zu Ende gebaut; offen bleiben schräge Ebenen, Symmetrie, globale Schnittfolgen und das Schaustück |
| [RM-086 — Achsenkonvention beim GLB-Import mit Migration klären](#rm-086) | Geometrie, Erkennung und Druckvorbereitung | GLB-Achsenkonvention mit Herkunft und Migration festlegen |
| [RM-128 — Bearbeitbarkeit erkannter Flächen entscheiden](#rm-128) | Geometrie, Erkennung und Druckvorbereitung | Die Verrundung hat ihre zwei Operationen; offen bleiben `face` und `edge_loop` in der Liste |
| [RM-132 — Freiformerkennung am Ein-Sekunden-Ziel messen](#rm-132) | Geometrie, Erkennung und Druckvorbereitung | 1,400 auf 1,004 s gebracht; offen ist die Entscheidung zwischen Stapelumbau der Einpassungen und einem neu gefassten Ziel |
| [RM-133 — Rückmeldung zur Volumenänderung beim Merkmaldrehen entscheiden](#rm-133) | Geometrie, Erkennung und Druckvorbereitung | Kundennutzen eines Hinweises zur korrekten Volumenänderung entscheiden |
| [RM-138 — Gespeicherten Bausteinstand beim Öffnen wählbar erhalten](#rm-138) | Geometrie, Erkennung und Druckvorbereitung | Wahl zwischen aktuellem und noch verfügbarem früherem Bausteinstand ermöglichen |
| [RM-147 — Die acht beauftragten Konstruktionserweiterungen bauen](#rm-147) | Geometrie, Erkennung und Druckvorbereitung | Die ganze Kanten- und Flächenarbeit greift an beiden Kernen; Zeiger, Rechtsklick und Flächengriff sind eingelöst und gemessen — offen bleiben fünf zugesagte Kundenwege |
| [RM-163 — Bambu Studio druckt einen Mehrfarbauftrag halb und meldet Erfolg](#rm-163) | Geometrie, Erkennung und Druckvorbereitung | Solidon meldet den Verlust; offen ist die Ursache bei Bambu — dessen eigene Mehrfarbdatei gegen Solidons stellen |
| [RM-164 — Creality Print: Erkennung steht, der Konsolenlauf ist ungeprüft](#rm-164) | Geometrie, Erkennung und Druckvorbereitung | Slicer einrichten, dann Öffnen- und Konsolenweg mit mehreren Spulen abnehmen |
| [RM-166 — Ergebnisnetze aus Mesh-Ops an einer STL überstehen keinen Weld](#rm-166) | Geometrie, Erkennung und Druckvorbereitung | Der Weld ist behoben und als Kundenweg getestet; offen bleiben das Flackern der Tetraederecke auf dem Linux-Runner und das Beispielarchiv der Werkstattfilme |
| [RM-181 — Handlungsliste und Baugruppenladen an dichten Netzen weiter vermessen](#rm-181) | Geometrie, Erkennung und Druckvorbereitung | Die Langlochsuche ist gebaut (126 s → 9 s); offen sind `actions_for` mit Netz (0,14 s je Merkmal) und die Ladezeit einer Baugruppe mit vielen Körpern |
| [RM-070 — SpaceMouse auf macOS und Linux am echten Gerät abnehmen](#rm-070) | Bedienung und Darstellung | Der Mac ist gefahren; die Zoom-Dämpfung ist seit dem 16.09. eine Rampe statt einer Klippe und am Gerät zu bestätigen; offen bleiben Linux, die 3DxWare-Mausemulation und die Bildrate an 1 Mio. Dreiecken |
| [RM-183 — Zeichenmodus am Fenster abnehmen](#rm-183) | Bedienung und Darstellung | Fünf Entscheidungen der Durchsicht sind gefallen und gebaut; offen: Führen mit gezeichneter Bahn und Überblenden mit gezeichnetem Umriss am Fenster fahren, Rollen und Rampe der 3D-Maus prüfen |
| [RM-074 — Verbleibenden Bildnachweis der Viewport-Serie abschließen](#rm-074) | Bedienung und Darstellung | Befundsprung und sichtbare Marke an einem echten Warnprojekt zeigen |
| [RM-084 — Kundentexte gegen die vereinbarte Sprache prüfen](#rm-084) | Bedienung und Darstellung | Kundentexte systematisch prüfen und alle Sprachfassungen nachziehen |
| [RM-088 — Verständlichkeit für Laien im Regelwerk verankern](#rm-088) | Bedienung und Darstellung | Verständlichkeitsregel und begründete Ausnahmen entscheiden |
| [RM-090 — Serie zum Übergabestatus entscheiden](#rm-090) | Bedienung und Darstellung | Nächsten Umfang aus den fünf Vorschlägen des Produktkompasses entscheiden |
| [RM-131 — Zurückgestellten Mehrfachimport entscheiden](#rm-131) | Bedienung und Darstellung | Zurückgestellt; bei Wiederaufnahme Mehrfachimport mit gemeinsamer Lage planen |
| [RM-135 — Zugewiesene Höhe der Filamentkarte vollständig nutzen](#rm-135) | Bedienung und Darstellung | Korrigierten Höhenvertrag nach grüner Windows-Abnahme auf macOS bestätigen |
| [RM-136 — Gezeichnetes Fensterschema und Bildbeschreibungen aktualisieren](#rm-136) | Bedienung und Darstellung | Fensterschema, Bildunterschriften und Alternativtexte aller Sprachen nachziehen |
| [RM-174 — Der Geist beim Zug an einem Bausteinmerkmal zeigt nur dieses Merkmal](#rm-174) | Bedienung und Darstellung | Der Zug bewegt den ganzen Baustein; während des Zugs wandert im Bild nur die Marke des angefassten Merkmals — der Rest folgt erst beim Loslassen |
| [RM-175 — Bauplan §30.1 um Winkel, gleich, Mittelpunkt, Vieleck und Langloch nachtragen](#rm-175) | Bedienung und Darstellung | Robert sagt den Nachtrag an; sechs Sätze liegen im Bericht W2 |
| [RM-003 — Lizenzkette der gepinnten TripoSG-Bestandteile klären](#rm-003) | KI und Generatoren | Lizenzkette der eingesetzten Modellrevisionen klären |
| [RM-004 — Echte Text- und Bildgenerierung über alle Zielplattformen abnehmen](#rm-004) | KI und Generatoren | Echte Text-/Bildläufe auf Windows, macOS und Linux dokumentieren |
| [RM-014 — Zusätzliche Formenregel und zugehörige Suite-Abnahme entscheiden](#rm-014) | KI und Generatoren | Zusätzliche Formenregel entscheiden; bei Änderung Suite vorher/nachher |
| [RM-016 — Agenten-Suite gegen das aktuelle Vorgabemodell messen](#rm-016) | KI und Generatoren | Suite mit festgehaltenem aktuellem Modell und vergleichbarer Referenz messen |
| [RM-081 — Ollama-Laufzeit und verbleibende Optimierungen abnehmen](#rm-081) | KI und Generatoren | Quote und Kürzung sind gemessen (RM-173); offen sind Latenz auf ruhiger Karte, der Lauf ohne Denkblock und die gestufte Werkzeugauswahl als Entscheidung |
| [RM-144 — Orientierungsanalyse über MCP ohne blockiertes Hauptfenster ermöglichen](#rm-144) | KI und Generatoren | Gemeinsame Orientierungsanalyse an den fernbedienten Arbeiterweg anschließen |
| [RM-173 — Der Platz im Kontextfenster des lokalen Modells geht aus](#rm-173) | KI und Generatoren | Zwei Wächter stehen, die Kürzung ist drin (Suite 20/39 → 24/39); offen sind der dritte Lauf ohne Denkblock, die Neumessung von `PROMPT_TOKENS` auf ruhiger Karte und drei Entscheidungen von Robert |
| [RM-185 — Das kompakte Werkzeugschema passt nicht mehr ins Fenster des lokalen Modells](#rm-185) | KI und Generatoren | Fenster seit dem 16.09.2026 auf 40 960 (Entscheidung Robert, Preis 11 statt 41 Token/s); offen bleibt, das Schema unter 28 000 Token zu bringen und dann 32 768 zurückzustellen |
| [RM-020 — Sicherung der eigenständigen Druckprojekte belegen](#rm-020) | Tests und Entwicklungswerkzeuge | Sicherungsweg entscheiden und Wiederherstellung belegen |
| [RM-099 — Konzeptbestand und veraltete Verweise ordnen](#rm-099) | Tests und Entwicklungswerkzeuge | Verweise sind vollständig gültig; offen ist nur noch das Umräumen — Umfang entscheidet Robert |
| [RM-103 — Große Kernfunktionen nach konkretem Wartungsbedarf aufteilen](#rm-103) | Tests und Entwicklungswerkzeuge | Auswertung und weitere große Funktionen nach Wartungsbedarf priorisieren |
| [RM-106 — Plattformunterschiede der Projektdateien dem richtigen Ursprung zuordnen](#rm-106) | Tests und Entwicklungswerkzeuge | Archiv- und Inhaltshashes nach gleichem Erzeugerlauf vergleichen |
| [RM-113 — Besitzerprüfung der Tokendatei auf dem Windows-Runner belegen](#rm-113) | Tests und Entwicklungswerkzeuge | Besitz und ACL einer tatsächlich nutzereigenen Runner-Datei belegen |
| [RM-134 — Zusammenführung duplizierter Testhilfen entscheiden](#rm-134) | Tests und Entwicklungswerkzeuge | Gemessen am 14.09.: 28 wortgleiche Gruppen, 13 davon über Dateien hinweg — Robert entscheidet, ob die sechs großen zusammenrücken |
| [RM-137 — Sitzungsende im tatsächlichen Editorbetrieb abnehmen](#rm-137) | Tests und Entwicklungswerkzeuge | Echtes SessionEnd und Freigabe des Sitzungsgebiets nach Neustart beobachten |
| [RM-165 — Über `mushroom.stl` in der Wurzel entscheiden](#rm-165) | Tests und Entwicklungswerkzeuge | Robert entscheidet, ob die unbenutzte Datei bleibt oder geht |
| [RM-002 — netcup-AVV und Freigabe der Rechtstexte belegen](#rm-002) | Veröffentlichung, Betrieb und Vertrieb | netcup-AVV belegen und zugehörige Rechtstexte fachlich abgleichen |
| [RM-006 — Nächsten messbaren Schritt für die Sichtbarkeit festlegen](#rm-006) | Veröffentlichung, Betrieb und Vertrieb | Zielgruppe, Kanal und messbares Ziel des nächsten Außenauftritts festlegen |
| [RM-008 — DMARC-Eintrag öffentlich prüfen und gegebenenfalls einrichten](#rm-008) | Veröffentlichung, Betrieb und Vertrieb | DMARC einrichten und legitimen Mailversand prüfen |
| [RM-030 — Impressum nach Vergabe einer USt-IdNr. oder W-IdNr. ergänzen](#rm-030) | Veröffentlichung, Betrieb und Vertrieb | Bereits vergebene USt-IdNr./W-IdNr. klären; gegebenenfalls Impressum ergänzen |
| [RM-034 — Versicherungsschutz für Software und Produktschäden klären](#rm-034) | Veröffentlichung, Betrieb und Vertrieb | Versicherungsangebote gegen die tatsächlichen Risiken prüfen lassen |
| [RM-035 — EULA wirksam in den Bestellvorgang einbeziehen](#rm-035) | Veröffentlichung, Betrieb und Vertrieb | Produktgrenzen und EULA im vollständigen Bestellweg rechtlich prüfen |
| [RM-036 — Vertrag und Freistellungen des Zahlungsdienstleisters prüfen](#rm-036) | Veröffentlichung, Betrieb und Vertrieb | Konkreten Anbietervertrag und Haftungsübernahme entscheiden |
| [RM-061 — Verkaufsbereitschaft und Ende der Demo vorbereiten](#rm-061) | Veröffentlichung, Betrieb und Vertrieb | Kandidat bis 25.10.; letzte Optimierungen 31.10.; Start 01.11.2026 um 10:00 Uhr deutscher Zeit |
| [RM-149 — Zwei Funde aus dem Release-Lauf von 0.4.0 zuordnen](#rm-149) | Veröffentlichung, Betrieb und Vertrieb | Beide Funde sind zugeordnet und behoben; offen bleibt nur der Abgleich gegen den Server beim nächsten Upload |
| [RM-162 — Der Hinweistext der Fassung reiste unverändert mit](#rm-162) | Veröffentlichung, Betrieb und Vertrieb | Der Riegel steht; die sechs Sätze für 0.4.1 stehen bereit und werden beim Bau eingetragen |
| [RM-091 — CRA-Meldebereitschaft herstellen, die Frist ist abgelaufen](#rm-091) | Veröffentlichung, Betrieb und Vertrieb | Zugänge, Vertretung, Alarmierung und Probelauf belegen — die Pflicht gilt seit dem 11.09.2026 |
| [RM-092 — Verkaufskonzept für den geplanten Start abschließen](#rm-092) | Veröffentlichung, Betrieb und Vertrieb | Verkaufskonzept bis 15.10. abschließen; Start am 01.11.2026 um 10:00 Uhr deutscher Zeit |
| [RM-182 — Zwei Lizenzarten bauen, privat und gewerblich](#rm-182) | Veröffentlichung, Betrieb und Vertrieb | Kern, Dienst, Vorratswerkzeug, Oberfläche und Rechtstexte am 15.09. gebaut; offen sind Website, die Art im Serverdatensatz und die Migration des laufenden Dienstes |
| [RM-093 — Noch fehlende Angaben und Prüfungen der Rechtstexte klären](#rm-093) | Veröffentlichung, Betrieb und Vertrieb | Fehlende Anbieter-/Rechtsentscheidungen und Sprachfassungen fachlich prüfen |
| [RM-095 — Automatischen Löschlauf auf dem Server belegen](#rm-095) | Veröffentlichung, Betrieb und Vertrieb | Server-Löschlauf, Sicherungen und Ausfallalarm tatsächlich nachweisen |
| [RM-096 — Eigenen Rate-Key für Aktivierungsanforderungen einführen](#rm-096) | Veröffentlichung, Betrieb und Vertrieb | Eigenen Rate-Key mit geprüftem Rollout-/Rotationsweg einführen |
| [RM-115 — Releaseakte vor Veröffentlichung verbindlich durchsetzen](#rm-115) | Veröffentlichung, Betrieb und Vertrieb | Befunde der Releaseakte beheben und Prüfung anschließend verbindlich machen |
| [RM-116 — Historische Statistikreste auf dem Server behandeln](#rm-116) | Veröffentlichung, Betrieb und Vertrieb | Öffentlichen Altbestand prüfen und Umgang mit alten Statistikzeilen entscheiden |
| [RM-145 — CRA-Konformitätsakte zum gesetzlichen Anwendungszeitpunkt vorbereiten](#rm-145) | Veröffentlichung, Betrieb und Vertrieb | Produktklassifizierung, technische Akte und Konformitätsverfahren für 2027 vorbereiten |
| [RM-038 — Mailrückfall ohne prozentkodierten Berichtstext prüfen](#rm-038) | Kundenrückmeldungen | Mailportal im Kundenpaket mit Umlauten, Zeilenumbrüchen und Rückfall prüfen |
| [RM-040 — Kundenfehler mit Traceback und betroffener Datei zuordnen](#rm-040) | Kundenrückmeldungen | Aktuellen Kundenbericht mit Traceback und betroffener Datei reproduzieren |
| [RM-062 — Eingabemethode im aktuellen Flatpak bestätigen](#rm-062) | Kundenrückmeldungen | Start, Fokus und IME am aktuellen Flatpak bestätigen |
| [RM-064 — Slicerübergabe zwischen zwei echten Flatpaks abnehmen](#rm-064) | Kundenrückmeldungen | Modell zwischen installiertem Solidon- und Slicer-Flatpak übergeben |
| [RM-072 — Zusagen an den Dental-Kunden zum Verkaufsstart erfüllen](#rm-072) | Kundenrückmeldungen | Kaufweg und belastbare 3D-Maus-Unterstützung zum zugesagten Anlass mitteilen |

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

Die Veröffentlichung ist erfolgt; der lokale Downloadstand ist 0.4.0 (`website/version.json`, seit dem 10.09.2026 — die 0.3.5-Dateien sind vom Server geräumt, siehe RM-073). Windows, Flatpak, AppImage und beide Mac-Architekturen sind keine neuen Bauvorhaben mehr. Signierung, Notarisierung, Fremdrechnerabnahme und noch fehlende Betriebsnachweise bleiben offen; siehe RM-001 und RM-002.

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

Der optionale exakte Kern und STEP-Austausch sind umgesetzt. Das ist keine allgemeine Rückgewinnung exakter CAD-Flächen aus beliebigen Netzen; dieses Konzept wartet weiterhin auf eine Entscheidung.

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

- [~] **RM-001 — Signierung und Notarisierung der Kundenpakete belegen.** Windows-Signierung mit dem
  vorhandenen Certum-Weg sowie Apple-Signierung und Notarisierung abschließen beziehungsweise
  belegen. Die CI baut die Windows-Übergabe und den unsignierten Installer; `tools/sign_release.py`
  erledigt die lokale Signierung. Ein vorhandenes Skript belegt weder den Zertifikatszugang noch
  eine Signatur am Kundenpaket. Offen sind die benötigten Zugänge und die gebundenen
  Signatur-/Notarisierungsbelege. Abnahme: veröffentlichungsfähiger Installer mit überprüfter
  Signatur und Zeitstempel beziehungsweise Gatekeeper-/Notarisierungsnachweis für beide
  Mac-Architekturen; den Fremdrechnerweg mit RM-011 abstimmen.

  **Gemessen am 10.09.2026 beim Bau von 0.4.0** (Lauf 34456150383, Tag `v0.4.0`): Der Weg
  steht vollständig — `MACOS_SIGNING_MODE` auf `notarized`, alle acht Apple-Geheimnisse
  gesetzt, und die Kette aus `codesign`, `notarytool`, `stapler` und `productsign` ist im
  Workflow angelegt, mit `spctl --assess` und `pkgutil --check-signature` als Abnahme.
  Gescheitert ist er trotzdem, auf beiden Architekturen, an derselben Stelle:

      1 identity imported.
      2 certificates imported.
      ***: no identity found

  Das Zertifikat kommt also in den Schlüsselbund; gesucht wird es unter dem Namen aus
  `APPLE_SIGN_IDENTITY`, und **dieser Name findet sich dort nicht**. Das Geheimnis führt
  den Zertifikatsnamen ein zweites Mal, und die zweite Fassung weicht ab. Alles danach —
  Notarisierung, `.pkg`, Installersignatur, Mac-Releaseakte — wurde übersprungen; Windows
  (159 MB) und Linux (459 MB) sind fertig gebaut und liegen als Artefakte des Laufs.

  **Der Vorschlag, und er macht das Geheimnis überflüssig:** Den Fingerabdruck aus dem
  Schlüsselbund lesen, den der Schritt gerade selbst angelegt hat — dort liegt genau eine
  Identität (`security find-identity -v -p codesigning "$keychain"`, erste Spalte). Beim
  Installer **ohne** `-p codesigning`, weil eine Developer-ID-Installer-Identität unter
  diesem Filter nicht auftaucht. Der Vertrauensraum bleibt unangetastet: derselbe feste
  Schritt, kein Checkout, kein Python.

  **Entscheidung Robert, 10.09.2026: 0.4.0 geht unsigniert hinaus, signiert wird ab
  0.4.1.** Die Repository-Variable `MACOS_SIGNING_MODE` steht dafür auf `unsigned`; der
  Workflow überspringt dann beide Signierjobs und baut die Paketdatei über *macOS-Installer
  ohne Signierrechte*. Das entspricht dem Stand von 0.3.5, und die Website erklärt ihn
  bereits an drei Stellen — FAQ, Prüfhinweis im Download-Kasten und Systemanforderungen
  nennen die fehlende Notarisierung samt dem Weg über *Datenschutz & Sicherheit* →
  *Trotzdem öffnen*.

  **Die Reparatur steht seit dem 10.09.2026 im Workflow.** Beide Signierschritte lesen den
  Fingerabdruck aus dem Schlüsselbund, den sie selbst angelegt haben
  (`security find-identity`, beim Installer ohne `-p codesigning`, weil eine
  Developer-ID-Installer-Identität unter dieser Richtlinie nicht auftaucht). Liegt dort nicht
  genau eine Identität, hält der Schritt an und sagt, was zu prüfen ist, statt zu raten
  (Regel 21). Die beiden Geheimnisse `APPLE_SIGN_IDENTITY` und `APPLE_INSTALLER_IDENTITY`
  werden nicht mehr gelesen — ein Name, den zwei Stellen unabhängig voneinander führen, geht
  irgendwann auseinander; der Fingerabdruck steht nur an einer Stelle. Geprüft wurden das
  Ausgabeformat von `security find-identity` gegen vier Lagen (eine, keine, zwei Identitäten,
  Installer allein) und das Verhalten unter `set -euo pipefail` — beide Fehlfälle brechen
  **mit** ihrer Meldung ab, nicht davor. Der Fingerabdruck wird dabei in Groß- **und**
  Kleinschreibung gelesen: Die erste Fassung verlangte `[0-9A-F]`, und ein klein
  geschriebener Wert hätte zu „0 Identitäten" geführt — an einer Stelle, die es hier nicht zu
  messen gibt, weil kein Mac danebensteht.

  **Was damit nicht gesagt ist:** Alles hinter dem Signieren — Notarisierung, `stapler`,
  `spctl`, `productsign`, `pkgutil` — ist bis heute **nie gelaufen**; 0.4.0 ist vorher
  abgebrochen. Der bekannte Fehler kann nicht wiederkommen, neue können auftauchen. Ein
  Probelauf mit `MACOS_SIGNING_MODE=signed` fährt nur die Signierung und lässt die
  Notarisierung aus — die kleinere Stufe, um die Kette einmal ohne Apples Gegenstelle zu
  sehen.

  **Belegt am 14.09.2026 mit 0.4.1** (Lauf 34785006709, Tag `v0.4.1` = 1a357e1a,
  `MACOS_SIGNING_MODE` = `notarized`): Beide Architekturen signiert, bei Apple notarisiert
  (arm64 `aab4b062-…`, Accepted), gestapelt, `spctl --assess` sagt „Notarized Developer ID",
  Installer mit `productsign` signiert und notarisiert, beide Mac-Releaseakten grün. Der Weg
  brauchte drei Reparaturen hinter dem Fingerabdruck: den Schlüsselbund in die **Suchliste**
  (`security list-keychains -d user -s`, sonst „no identity found" bei gefundener Identität),
  die Lizenzbeilage **aus dem Bundle-Root** nach `Contents/MacOS/` („unsealed contents present
  in the bundle root" — und dort liest die Anwendung sie ohnehin), und einen zweiten Anlauf des
  x86_64-Jobs, weil Apples Notarisierung über eine Stunde „In Progress" blieb und eine
  Statusabfrage mit HTTP-Timeout riss (`gh run rerun --failed` desselben Laufs). Die Variable
  bleibt auf `notarized`.

  **Windows bleibt offen:** Auf der Arbeitsmaschine liegen weder ein Certum-Zertifikat noch
  SimplySign Desktop; `tools/sign_release.py` war noch nie gefahren, und 0.4.1 ging wie 0.4.0
  mit unsigniertem Setup hinaus. Abnahme für Windows: Zugang einrichten, den Signiereingang von
  Lauf 34785006709 (oder dem nächsten Tag) lokal signieren und das signierte Setup hochladen.

  **Und Windows ist seit dem 14.09.2026 ein Kundenbefund.** Ralph Dietrich, 08:43: „Jetzt
  fängt WIN11 auch mit dem Käse an — ich muss Smart App Control deaktivieren, damit Solidon3D
  startet." Smart App Control (Windows 11) lässt nur signierte Anwendungen zu; das unsignierte
  Setup startet damit gar nicht, und der blaue SmartScreen-Hinweis mit *Trotzdem ausführen*
  kommt nicht mehr zum Zug. Sein Workaround — Smart App Control ausschalten — hat einen Preis,
  den ein Kunde kennen muss: Es lässt sich ohne Neuinstallation von Windows nicht wieder
  einschalten. Die Website nennt seither beides (Prüfhinweis, Systemvoraussetzungen, sechs
  Sprachen); die Antwort bleibt die Signierung.

  **Der Nebenbefund zur FAQ ist behoben (14.09.2026):** Die Website sagte an vier Stellen je
  Sprache, die Mac-Version sei „noch nicht notarisiert" und die Notarisierung komme, „sobald das
  Apple-Konto steht" — vier Tage nachdem 0.4.1 notarisiert im Download-Kasten lag. Prüfhinweis,
  Systemvoraussetzungen und die FAQ „Läuft das auf einem Mac?" sagen jetzt, dass die Pakete ab
  0.4.1 notarisiert sind; der Weg über *Trotzdem öffnen* bleibt für eine ältere Version stehen.
  `make_seo.py` hat die FAQ-Auszeichnung nachgezogen. Hochgeladen wird die Website erst mit
  dem nächsten Lauf von `upload_website.py` — bis dahin steht der alte Text online.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#p8--erste-veröffentlichung).

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
  behoben. Offen bleiben die kopierten Bytes und Pufferkosten je großer Szene sowie der beschlossene
  Ersatz von VTK in der Baustein-Bereichsprüfung. Abnahme: reproduzierbare Zeit-/Speichermessung am
  großen Netz; Ersatzprüfung über alle 27 Bausteine mit unveränderten Ergebnissen, danach Lizenz-
  und Paketbestand ohne VTK. Plattformfenster werden separat abgenommen.

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

<a id="rm-117"></a>

- [~] **RM-117 — Öffentliche Downloadlinks vollständig in die Paketprüfung aufnehmen.**
  **Der Hauptteil ist gebaut** (nachgemessen 10.09.2026): `verify_downloads()` liest neben
  `version.json` auch jede `*/index.html` und die Startseite und erfasst darüber den
  AppImage-Link, der im Update-Manifest bewusst fehlt — dieselbe Quelle sperrt schon vor dem
  Upload. Der Satz „insbesondere AppImage" ist damit eingelöst.

  **Die stille Lücke ist seit dem 10.09.2026 zu.** Sie war die schlimmere der beiden Reste:
  `expected = local.stat().st_size if local.is_file() else sizes.get(name, 0)` wurde null,
  wenn **beide** Quellen schwiegen — und genau das ist der AppImage-Fall, denn es steht mit
  Absicht nicht im Update-Manifest. Der Vergleich `if expected and length != expected` fiel
  dann in seinen Sonst-Zweig und schrieb **„ok"** für eine Datei, von der er nur wusste, dass
  der Server irgendetwas geantwortet hat. Ein abgebrochener Upload hätte dort als Erfolg
  dagestanden — bei dem einen Paket ohne Prüfsumme im Manifest.

  Bemerkenswert daran: Der Kommentar über der Stelle hat diese Falle beschrieben („eine
  beliebig kurze 200-Antwort ist sonst ein ‚ok'"), und geschlossen war sie nur für den einen
  der beiden Fälle. Jetzt sagt der Lauf `OHNE MASS`, nennt den Weg (Datei unter `website/dl/`
  ablegen) und endet mit 1 — getrennt von „nicht in Ordnung", weil das eine andere Aussage
  ist: Die Datei liegt vielleicht vollständig oben, nur weiß dieser Lauf es nicht. Nachweis:
  `tests/test_toolchain.py::test_a_promised_package_without_a_size_is_not_reported_as_fine`;
  Gegenprobe gefahren, mit dem alten Zweig meldet eine 17-Byte-Antwort Erfolg (`assert 0 == 1`).

  **Zwei Reste bleiben.** Der Abruf prüft `Content-Length` und **keine Prüfsumme** — eine
  vollständig übertragene, aber falsche Datei fiele nicht auf. Das ist keine Fleißarbeit,
  sondern eine Entscheidung: Die SHA-256 über HTTP zu prüfen heißt, rund ein Gigabyte je Lauf
  herunterzuladen. Und der Lauf selbst — `--nachpruefen` ist Handarbeit und für 0.4.0 noch
  nicht gefahren.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#030-ist-draußen-03092026).

<a id="rm-187"></a>

- [x] **RM-187 — Dieselbe Geometrie auf jeder Plattform.** Am 17.09.2026 lieferte dasselbe
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

## Geometrie, Erkennung und Druckvorbereitung

<a id="rm-005"></a>

- [ ] **RM-005 — Wahl der Stiftseite gegen das fertige Stützvolumen prüfen.** An repräsentativen
  Schnitten messen, ob vertauschte Stift- und Bohrungsseite das Stützvolumen der fertigen Hälften
  senkt. Abnahme: gleicher Schnitt und Verbinder, beide Seitenzuordnungen samt anschließender
  Orientierung vergleichen; Nutzen und geometrische Grenzen belegen, bevor eine automatische
  Seitenwahl umgesetzt wird.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#p10--auto-split-mit-verstiftung).

<a id="rm-017"></a>

- [ ] **RM-017 — Nutfedermaße an realen Aluminiumprofilen prüfen.** Stegdicke und Kammertiefe an je
  einem konkret benannten 2020-/Nut-6- und 3030-/Nut-8-Profil nachmessen und die Nutfeder daran
  prüfen. Abnahme: Hersteller/Profil und beide Messwerte samt Passungsprobe dokumentiert;
  Abweichungen herstellerspezifisch einordnen, nicht aus zwei Proben allgemeine Normmaße ableiten.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-nutfeder-und-zwei-fehler-auf-dem-weg-dorthin-20082026).

<a id="rm-022"></a>

- [ ] **RM-022 — Phase zur Flächenrückgewinnung aus Netzen entscheiden.** Über eine eigene Phase zur
  Flächenrückgewinnung für importierte Netze entscheiden. Abnahme der Entscheidung: Zielkörper,
  Umgang mit nicht analytisch erkannten Restflächen, Genauigkeitsgrenzen und Kundenwert gegenüber
  bestehenden Aufgaben festgelegt. Erst danach die Umsetzung planen; der heutige B-Rep-Editor und
  seine erklärten Mesh-Grenzen bleiben die Ausgangslage.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#neun-heruntergeladene-modelle-durch-die-ganze-kette-21082026).

<a id="rm-024"></a>

- [~] **RM-024 — Gespeicherte Zuordnungsantworten im echten Konfliktfall abnehmen.**
  `Operation.matches` und Speichern/Wiederöffnen sind gebaut. **Auch der geometrisch echte Fall
  steht** (nachgemessen 10.09.2026): `tests/test_evaluation.py` führt eine Platte mit zwei nah
  beieinander liegenden Bohrungen über die echte Erkennung — einmal gefragt, aufgeschrieben,
  beim zweiten Lauf still.

  **Der Rundlauf steht seit dem 12.09.2026.** `test_a_recorded_match_survives_saving_and_reopening`
  schreibt eine Antwort über `record_matches`, speichert, öffnet wieder und findet sie unverändert
  — ohne ihn wäre die Zusage aus §15.7 an die geöffnete Sitzung gebunden gewesen, und wer sein
  Projekt zumacht, bekäme dieselben Fenster am nächsten Tag noch einmal. Gegenprobe ohne das Lesen
  des Feldes in `serialise` rot.

  **Die Abnahme „über `evaluate`" ist am 12.09.2026 gemessen worden, und das Ergebnis ist ein
  anderes als erwartet: Aus dem Operationskatalog lässt sich kein geometrischer Konflikt bauen.**
  Acht Stapel gefahren, keiner löst die Frage aus — eine Platte mit zwei Bohrungen, ein
  einseitiger Anbau, eine Vierteldrehung, eine halbe Drehung, ein dritter Schnitt zwischen zwei
  Bohrungen, ein gestauchter Körper, ein Steg quer durch ein Langloch, ein versetztes Loch an
  einem 400er Träger. Zwei Gründe, beide am Code nachgemessen und beide **richtiges** Verhalten:

  * **Der Abgleich normiert alt und neu im selben Rahmen.** Am Vereinigungsschritt stand
    `old_centre` auf der Mitte des *gewachsenen* Körpers, und damit kosten Merkmale, die sich am
    Material nicht bewegt haben, nichts. Ein Träger, der um sechs Millimeter länger wird, behält
    seine Bohrungen eindeutig — nur ein Aufruf von Hand, der die alte Mitte einsetzt, erzeugt die
    Mehrdeutigkeit künstlich.
  * **Jede Operation, die ein Merkmal anfasst, erklärt es** (§21.2). Bei `move_feature` sah der
    Abgleich `alt={'hole_1': −10}` gegen `neu={'hole_1': −10, …}` — die verschobene Bohrung war
    schon deklariert, und der Abstand war null. Die Frage des Abgleichs gehört damit der
    **Wiedererkennung nach einer nicht erklärten Änderung**, also dem Weg über `load` und fremde
    Netze — dort kamen die 99 Fenster her, an einem Projekt aus 52 Teilen.

  Offen bleibt daher nicht mehr „die Abnahme über `evaluate`", sondern die Frage davor: ein
  **Korpuskörper**, dessen erneute Erkennung nach einer formenden Operation echt mehrdeutig wird
  (Kandidaten: ein eingelesenes Netz mit dicht benachbarten Bohrungen, danach Reparieren oder
  Dreiecke verringern). Erst mit ihm ist die Reihe „einmal gefragt, wiederöffnen ohne Rückfrage,
  Abbruch liefert einen Befund" über `evaluate` zu zeigen; bis dahin trägt sie
  `_with_features` an derselben Geometrie. Die historische 99→7→0-Reihe nur mit dem damaligen
  52-Teile-Projekt vergleichen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#das-fundament-der-wahrnehmung-22082026).

<a id="rm-041"></a>

- [ ] **RM-041 — Innenraum importierter entlüfteter Hohlkörper klären.** Der Kern lehnt den nicht
  bestimmbaren Innenraum weiterhin ab. Entweder einen nachvollziehbaren Schätzweg mit ausgewiesenem
  Befund entwickeln oder die bestehende Grenze im Handbuch erklären. Abnahme an einem entlüfteten
  Importkörper: keine unbemerkte Füllung außerhalb des Innenraums und ein verständlicher weiterer
  Weg.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-abnahme-des-gesamt-reviews-06092026).

<a id="rm-042"></a>

- [ ] **RM-042 — Leistungsgrenze der Merkmalserkennung bis eine Million Dreiecke klären.**
  `FEATURE_LIMIT_TRIANGLES` steht weiterhin auf 1.000.000. Erkennung am benannten großen Korpus auf
  ruhiger Maschine messen und §31 mit dem Ergebnis abgleichen; andernfalls Grenze auf einen
  tatsächlich belegten Wert setzen. Abnahme: dokumentierte Laufzeit und Spitzenbedarf, Grenzmeldung
  oberhalb des freigegebenen Bereichs.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-abnahme-des-gesamt-reviews-06092026).

<a id="rm-045"></a>

- [ ] **RM-045 — Drei Laufzeitkosten des Geometriereviews messen.** Zusätzliche Innenraumrechnung
  beim Aushöhlen, Formkopien in `Solid.__post_init__` und `cavity_chains` im Qt-Hauptthread jeweils
  mit einem repräsentativen Modell messen. Abnahme: Zeit und Spitzenbedarf dokumentiert, nötige
  Optimierungen geometrisch geprüft und längere UI-Arbeit außerhalb des Hauptthreads.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-abnahme-des-gesamt-reviews-06092026).

<a id="rm-071"></a>

- [ ] **RM-071 — Beschlossene Resin-Stufe 1 umsetzen.** Das Druckverfahren gehört ins Druckerprofil;
  zwei generische Resin-Bauräume und die Geltungsbereiche der FDM-Regeln gehören zur ersten Stufe.
  Abnahme: Ein Resin-Profil bekommt passende Bauraumprüfung und keine FDM-spezifischen
  Brim-/Düsenratschläge; Datei vorbereiten und an den Herstellerslicer übergeben bleibt der
  Hauptweg. Cupping und Drain-Bohrungen gehören in Stufe 2.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#eine-kundenanfrage-aus-dem-dentalbereich-30082026).

<a id="rm-076"></a>

- [ ] **RM-076 — Topologieverlust beim Reduzieren von Eule und Spiderman beheben.** Die neu
  entstehenden nicht-mannigfaltigen Kanten der generierten Eule und den Dichtheitsverlust kleiner
  Komponenten beim Spiderman am aktuellen Vereinfacher reproduzieren und beheben. Abnahme: Eule über
  150k/100k/60k/30k, Spiderman bei 120k, Eingangs-/Ausgangstopologie und Komponentenzahl
  dokumentiert; geschlossene Eingänge bleiben druckbar oder die Operation bietet einen
  nachvollziehbaren Rückweg.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#befunde-aus-dem-weg-dreh-31082026).

<a id="rm-077"></a>

- [ ] **RM-077 — Reduzierungsziel bei Körpern mit Durchbrüchen erreichen.** Den Stopp der
  Vereinfachung an Hülsen, Ringen und Gehäusen mit Durchbrüchen gegen den vorhandenen
  Manifold-Rückfall nachmessen. Der Rückfall greift bisher nur, wenn das erste Verfahren gar keine
  Dreiecke entfernt. Abnahme: dokumentierte Zielreihen für Euler-0-Körper, begrenzte Formabweichung
  und klare Meldung bei unerreichbarem Ziel; erst danach über eine Erweiterung entscheiden.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#befunde-aus-dem-weg-dreh-31082026).

<a id="rm-078"></a>

- [ ] **RM-078 — Ladezeit generierter Beispielmodelle an der Orientierung messen.** Die Öffnungszeit
  des generierten Eulenprojekts am aktuellen Stand ohne Fremdlast neu messen und die teuren
  Operationen einzeln zuordnen. Abnahme: reproduzierbare Wandzeiten samt Netzgröße und
  Schrittzeiten, durchgehende Ladeanzeige und Entscheidung über das verbleibende Wartezeitbudget.
  Alte Prozess-CPU-Zeiten und wartende Sitzungsaufträge sind keine aktuellen Befunde.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#befunde-aus-dem-weg-dreh-31082026).

<a id="rm-080"></a>

- [~] **RM-080 — Restumfang der Trennen-Serie mit aktuellem Code abgleichen.** **Die
  Sichtflächen-Sperre (T8) ist seit dem 14.09.2026 zu Ende gebaut.** Bis dahin war sie halb: Der
  Kern kannte `protect` samt Auswertung, der Viewport konnte markieren und anzeigen — aber kein
  Aufrufer reichte das eine an das andere, und die Markierung lebte nur in der Ansicht. Ein
  Kunde, der Flächen schützte und die Datei schloss, hatte seine Arbeit verloren.

  Was jetzt steht, an vier Enden: **Die Geste** ist ein Haken unter den Handlungen im
  Merkmalfenster, *Vor Trennnähten schützen* (`FeaturePanel.protectionToggled`,
  `perceive.actions.protection_of` sagt, ob ein Merkmal sich sperren lässt — geschützt wird, was
  Dreiecke hat). Kein Kontextmenü-Eintrag, und das mit Absicht: Robert hat am 11.09.2026 die
  Operationen aus dem Rechtsklick genommen („zwei Orte für dieselbe Liste sind einer zu viel");
  der Archivpunkt, der ihn noch vorsah, ist damit überholt. **Das Dokument** trägt die Sperre als
  Merkmalkennungen (`Document.protected`, Formatversion 24, `example_v24.p3d`), kein
  Verlaufsschritt — wie die Druckeinstellungen: Es entsteht keine Geometrie, der Haken ist sein
  eigener Rückweg; das Bild folgt dem Dokument über `Viewport.show_protected`, die Statuszeile
  hängt „geschützt" an (Regel 18). **Die Suche** bekommt die Punktwolken in
  `Session.split_async` über `split.protected_patches` — die eine Stelle, an der gelesen wird.
  **Und das Ende ohne Ebene** heißt nicht mehr „keine Ebene": `search_plane` zählt, was die
  Sperre gefressen hat, und `split_to_fit` meldet `split.blocked_by_protection` mit *Sperren
  aufheben und erneut teilen* als erstem Knopf (`RELEASE_PROTECTION`), *An gezeichneter Linie
  trennen* daneben — die drei Wege, die der Archivpunkt verlangte. Gemessen in
  `tests/test_protection_ui.py` (Haken → Dokument → Bild → Statuszeile; speichern und
  wiederöffnen; die Wolke kommt bei `plan_split` an; der Knopf am Befund hebt auf und teilt
  erneut) und `tests/test_autosplit.py` (Zähler, Befund, Körper am Befund, Wolken aus den
  Dreiecken); zwei Mutationen gegengeprüft — Draht zur Suche entfernt, Bildabgleich entfernt —,
  beide rot.

  Unverändert offen: schräge automatische Ebenen (die Suche bleibt achsparallel), Symmetrie,
  globale Schnittfolgen und das Schaustück. Abnahme je Teil: Korpus, Determinismus, Abbruch und
  nachvollziehbarer Kundenweg. Bereits gebaute Stützbewertung und automatische Verbinder nicht
  erneut beauftragen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#sinnvolles-trennen--die-serie-31082026).

<a id="rm-086"></a>

- [ ] **RM-086 — Achsenkonvention beim GLB-Import mit Migration klären.** GLB-/glTF-Koordinaten beim
  Import eindeutig behandeln, ohne bestehende Weg-3-Projekte zu drehen. Zuerst Herkunft und
  Lagekonvention speichern, dann Dateiformat migrieren und externe Y-up-Dateien korrekt übernehmen.
  Abnahme: fremdes GLB steht richtig; bestehende eingebettete Generatorquellen behalten nach
  Migration Lage, Maße und Auswertung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-128"></a>

- [~] **RM-128 — Bearbeitbarkeit erkannter Flächen entscheiden.** **Für die reine Fläche steht
  die begründete Anzeigegrenze** (nachgemessen 10.09.2026), samt der Faltung gleichlautender
  Absagen — am Besenhalter gemessen, statt fünfmal denselben Satz zu wiederholen —, und seit
  dem 10.09.2026 bietet ein Bausteinmerkmal seine eigenen Handlungen statt derer der Fläche
  darunter.

  **Die Hälfte davon hat sich erledigt, und zwar im Code** (nachgemessen 13.09.2026): `fillet`
  trug am 10.09.2026 keine einzige Operation — heute nennen es zwei in `applies_to`,
  `remove_feature` und `resize_feature` (`geom/prepare_ops.py`, gebaut in `2b915e1b` als Teil
  von RM-147: „Die erkannte Rundung ändern und wegnehmen"). Die Frage „soll eine Verrundung
  ohne jede Operation in der Liste stehen" stellt sich damit nicht mehr; sie hat welche.

  **Offen bleibt der Rest**: `face` und `edge_loop` stehen weiter in der Merkmalsliste, ohne
  dass eine Operation sie annimmt — dieselbe Frage, eine Merkmalsart weiter. Dazu die Abnahme
  an den Schiffsmodellen, für die es keinen Testfall gibt. Den separat geführten
  Verrundungsradius nicht doppelt planen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#neunzehn-kundendateien-durch-die-oberfläche-gefahren-04092026).

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

<a id="rm-133"></a>

- [ ] **RM-133 — Rückmeldung zur Volumenänderung beim Merkmaldrehen entscheiden.** Entscheiden, ob
  eine geometrisch erwartbare Materialvolumenänderung beim Drehen eines Merkmals zusätzliche
  Auskunft braucht. Abnahme: Kundennutzen am schrägen Bohrungsfall belegt und ein möglicher Hinweis
  zeigt nur handlungsrelevante Folgen; kein pauschaler Warnsatz für jede korrekte Volumenänderung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-die-erkennung-erklärt--und-was-nicht-04092026).

<a id="rm-138"></a>

- [ ] **RM-138 — Gespeicherten Bausteinstand beim Öffnen wählbar erhalten.** Bauplan §24.4 verspricht vor der Neuberechnung eine Wahl des Bausteinstands.
  `part_check.check()` liefert derzeit Hinweise; `Session` startet danach die Auswertung mit dem
  aktuellen Register. Inhaltsfingerabdrücke eigener Bausteine sind bereits umgesetzt. Abnahme:
  geänderten mitgelieferten und eigenen Baustein öffnen, einen verfügbaren Altstand oder den
  aktuellen Stand ausdrücklich wählen und reproduzierbare Maße erhalten. Ein nicht verfügbarer
  Altstand wird als notwendige Migration erklärt; fremder Quelltext reist weiterhin nicht mit.

  [Bauplan-Abgleich und Nachweis](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026).

<a id="rm-147"></a>

- [~] **RM-147 — Die acht beauftragten Konstruktionserweiterungen bauen.** Robert hat sie am
  08.09.2026 zusammen mit den Korrekturen der Operations- und Bausteindurchsicht beauftragt;
  die Korrekturen sind hinaus, diese acht nicht. E1: Gegenstücke gemeinsam auf zwei Körpern
  platzieren, mit gemeinsamen Maßen, Passung, Vorschau und einem Undo. E2: Loft zwischen zwei
  unabhängigen Skizzen mit geprüfter Topologie. E3: Sweep entlang einer gespeicherten
  gezeichneten Bahn. E4: einzelne exakte Kanten verrunden und fasen, mit stabilen Verweisen.
  E5: kleine Prüfstücke aus der tatsächlichen Verbindung, mit Stufen, Kennzeichnung und
  Wertübernahme. E6: ein Rezept als bearbeitbaren Entwurf öffnen, Herkunft erhalten, neu
  speichern oder bewusst ersetzen. E7: einen Baustein auf mehrere gewählte Merkmale setzen,
  mit gemeinsamer Vorschau und einem Undo. E8: SCAD-Ausgabe mit den aktuellen Werten in
  Katalog und Kommandozeile, ohne Ausführung (Regel 11). Abnahme je Erweiterung nach der
  achtteiligen Checkliste aus `AGENTS.md`; E4 verlangt zusätzlich den exakten Kern.

  **Vier sind gebaut** (09.09.2026): E8 schreibt den gewählten Baustein aus Katalog und
  Kommandozeile als OpenSCAD-Datei, mit den Werten des Verlaufs statt der Vorgaben. E7 setzt
  einen Baustein über `at_features` auf beliebig viele gewählte Merkmale, der Reihe nach auf
  demselben Körper und mit einem Undo. E5 übernimmt bei der Toleranzleiter den gemessenen
  Durchmesser der Bohrung, an der sie geöffnet wurde (`at_hole_values`) — Stufen und
  Kennzeichnung hatte sie, die Wertübernahme leistet der Kalibrierdialog, es fehlte das Maß
  aus der echten Verbindung. E6 holt ein Rezept über *Zum Bearbeiten öffnen …* als Entwurf
  ins Fenster zurück (`recipe.draft`, `Session.open_draft`): Schritte im Verlauf, Angaben im
  Rezeptdialog, ein eingelesener Baustein bleibt eingelesen, und der Knopf sagt, ob er anlegt
  oder ersetzt.

  **Und drei weitere am selben Tag**: E2 spannt den Übergang zwischen zwei unabhängigen
  Zeichnungen auf statt zwischen einer und ihrer verkleinerten Kopie — rund unten, eckig oben,
  mit geprüfter Ebene, gleicher Umrisszahl und gleicher Lochzahl je Paar. E3 führt den
  Querschnitt entlang einer gezeichneten Bahn statt nur am Kreisbogen (`profile.path_of` für
  die offene Kette, `MakePipeShell` mit Gehrung an der Ecke; `MakePipe` hörte dort auf zu
  bauen und lieferte stillschweigend das erste Segment). E4 verrundet und fast **einzelne**
  Kanten: `brep.edit.edge_key` beschreibt eine Kante über Mittelpunkt und vorzeichenfreie
  Richtung und überlebt damit eine zweite Auswertung, die Auswahl `named` sagt im Register,
  dass die genannten gelten, und der Dialog zeigt sie als Liste mit Lage und Länge.

  **Und E1 als achte** (09.09.2026): *Gegenstücke setzen …* im Menü *Bausteine* legt beide
  Hälften einer Verbindung in **einen** Schritt. `app/core/counterpart.py` führt die drei Paare
  — Passstift und Passbohrung, gedruckte Schraube und Mutter, Einpressbuchse und
  Durchgangsloch —, die gemeinsamen Maße werden einmal eingegeben und in beide Schritte
  geschrieben, und die Passung reist als `DocumentChange` in derselben Transaktion: Ein Undo
  nimmt Geometrie und Passung zusammen. Die Merkmalskennungen werden dabei **gelesen und nicht
  geraten** — sie entstehen erst bei der Auswertung (`evaluate._renamed`), und das zweite Paar
  am selben Körper heißt `dowel_pin_1_2`. Der Menüeintrag nennt vor dem Klick, was ihm fehlt,
  und gibt seinen eigenen Erklärungssatz zurück, sobald zwei Stellen markiert sind.

  **Die Bedienung im Bild steht seit dem 10.09.2026.** Eine Kante lässt sich anklicken, und
  zwar auf derselben Stufe wie ein Merkmal (Robert: „man wählt auch erst den körper, dann
  das untergeordnete"). Der Renderer musste dafür nichts lernen: `brep.edit.edge_points`
  gibt die Kante als Punktfolge, `ui.render.edges.nearest_polyline` misst im Bild gegen die
  Strecken und entscheidet bei gleichem Abstand nach der Tiefe, und `_goes_deeper` beantwortet
  die Stufenfrage für Merkmal und Kante gemeinsam. Die gewählte Kante steht danach im
  Auswahlfenster mit ihren Maßen und den zwei Handlungen, die an ihr ansetzen — *Verrunden*
  mit Radius, *Fase anbringen* mit Breite, je ein Feld und ein Knopf
  (`perceive.actions.edge_actions`, `FeaturePanel.show_edge`). `edges="named"` und der
  Schlüssel reisen als `FeatureAction.fixed` mit; der Kunde sieht keine Kennung aus sechs
  Zahlen.

  Am echten Fenster gemessen: Der Klick trifft die Kante, unter der er liegt, vierzig
  Bildpunkte daneben keine mehr. Dabei ist ein Fehler aufgefallen, den die grüne Suite nicht
  zeigen konnte — der Körper behielt die Auswahlfarbe, und die hervorgehobene Linie lag in
  derselben Farbe darauf. `highlighted_object()` gibt jetzt `None`, solange eine Kante gewählt
  ist, und der Fall steht als Zusicherung in `tests/test_selection.py`.

  **Zeiger und Rechtsklick sind seit dem 10.09.2026 nachgezogen**, der Rechtsklick seit dem
  14.09.2026 ohne Vorbedingung. Der Zeiger fragt über `_edge_under` wörtlich die Bedingungen
  des Klicks und behält dabei die Merkmalsform — eine Kante ist die zweite Stufe wie ein
  Merkmal, derselbe Handgriff hat dasselbe Bild; ein eigener Kantenzeiger behauptete einen
  Unterschied, den die Bedienung nicht macht. Der Rechtsklick ging zur Kante, stellte die
  Stufenfrage aber fest mit `direct=False`: Auf einem **noch nicht gewählten** Körper zeigte
  er weiter das Menü der Fläche darunter, auf dem gewählten das der Kante — die Zusage aus
  §18.5 hing damit an einer Vorbedingung, die niemand kennt. `_edge_click` nimmt `direct`
  jetzt entgegen wie `_click_target` daneben, sagt den Körper vor der Kante an (sonst hätte
  *Verrunden* keinen Eingang) und bekommt den Punkt aus dem **Bild**: Zurückgerechnet suchte
  der Rechtsklick die Kante auf Platte 2 eine Bettbreite neben dem gezeichneten Körper und
  fand keine. Zwei Zusicherungen in `tests/test_selection.py`, beide Mutationen gegengeprüft.

  **Und der Flächengriff hängt an der gewählten Fläche** — gemessen am 14.09.2026, nicht
  gebaut: `gizmo_feature` setzt ihn auf Mitte und Normale des gewählten Merkmals,
  `faceDragged` meldet dessen Kennung, und der Verlauf trägt `push_face` mit `face=<Kennung>`.
  Die vier Stücke waren einzeln geprüft und die Kette nicht;
  `test_the_handle_of_a_chosen_face_pushes_that_face` fährt sie jetzt am Stück (Fläche wählen,
  Sitz prüfen, ziehen, Schritt lesen), beide Enden mutiert.

  **Und seit dem 10.09.2026 greifen Verrunden und Fase auch am Netz.** Das ist der zweite
  Teil derselben Entscheidung Roberts — „alles soll immer bearbeitbar sein, egal ob
  importiert Format egal und beim selbst zeichnen". Beide Operationen sind nach
  `geom/edge_ops.py` gezogen, haben ihr `requires_kind="brep"` verloren und wählen den
  Rechenweg nach `SceneObject.kind`; die Kantenauswahl darüber kennt den Unterschied
  ohnehin nicht, weil Schlüssel (`edge_key`) und Gruppen (`choose`, `wanted`) für beide
  Kerne einmal in `geom/edges.py` stehen.

  Gemessen an einem Quader mit vier Verrundungen zu R = 3: 23845,487 mm³ exakt gegen
  23839,049 am Netz — 0,027 %, und der Unterschied steckt vollständig in den
  Kreisabschnitten unter den Sehnen. Bei der **Fase** gibt es gar keinen (23840,0000 gegen
  23840,0000): Eine Fase ist eine Ebene, und eine Ebene hat ein Netz exakt. Wie fein der
  Bogen wird, hängt am Radius statt an einer festen Stückzahl — `units.MAX_FACET_SAG` und
  `MAX_FACET_ANGLE`, dieselben zwei Grenzen, mit denen OpenCASCADE tesselliert; die Zahl
  stand vorher zweimal im Haus und steht jetzt einmal. Achtzehn Zusicherungen in
  `tests/test_mesh_edges.py`, neun Mutationen gegengeprüft. Der Eintrag „Verrundungen auf
  Mesh-Kanten vor dem B-Rep-Kern" ist damit aus `AGENTS.md` verschwunden.

  **Und am selben Tag der Rest der Liste** (Auftrag Robert: „dann los alles abarbeiten
  nichts offen lassen"):

  * **Fläche versetzen und Formschräge am Netz** — `geom/faces.py`, beide über dasselbe
    Prisma: Boden und Deckel sind die Dreiecke der Fläche, der Mantel steht auf ihren
    Randkanten, und ein Versatz **je Knoten** macht daraus das gerade Prisma des Versetzens
    oder den Keil der Formschräge. Gemessen: Versetzen exakt in beide Richtungen, Formschräge
    22561,879 gegen analytisch 22561,879 und die Standfläche unverändert. Zwei Fehler steckten
    im Keil, beide sahen nach „geht halt nicht" aus — negatives Volumen durch die gekippte
    Umlaufrichtung und Dreiecke ohne Fläche an der neutralen Kante; die Kette fiel bis auf die
    Voxelstufe durch und brauchte 4,8 s für ein Ergebnis, das 0,13 % daneben lag. Sauber sind
    es 6 ms in der ersten Stufe.
  * **`push_face` nimmt die gewählte Fläche** statt einer Richtung (Roberts Einwand vom
    10.09.2026). An einer Treppe wanderten vorher alle Stufen zugleich: 24000,0 statt 21000,0.
    Der exakte Kern hat dafür `profiles._nearest_face` bekommen — die Richtung bleibt der
    Vorfilter, die Stelle entscheidet; beide Kerne kommen jetzt auf 21000,0.
  * **Die erkannte Rundung ändern und wegnehmen** — `remove_feature` und `resize_feature`
    nehmen `fillet` an. Am Netz rechnet `edges.sharp_corner` die Kante über den **Schnitt der
    zwei Nachbarebenen** zurück (nicht über den Radius: der stammt aus einem Sehnenzug und ist
    mit 2,9772 zu klein), am exakten Körper streicht `BRepAlgoAPI_Defeaturing` die Fläche in
    18 ms. Beide stellen den Quader exakt wieder her — 24000,00000.
  * **Wulst anlegen** — `bead_edges`, die Gegenrichtung zu Verrunden und Fase: ein Rundstab
    auf der Kante, je Stück ein Zylinder und je Knick eine Kugel. **Die Kehlnaht im
    Innenwinkel ist dabei nicht die glatte Hohlkehle**; die macht *Verrunden* an einer
    konkaven Kante, und der Unterschied ist der Faktor zwischen 104,45 mm³ und 28,97. Der
    erste Docstring versprach die Hohlkehle und lieferte die Naht — die Zahl daneben hat es
    gesagt.
  * **Der Haken „Flächen und Kanten später bearbeiten" ist zurückgeschnitten.** Er zählte
    „Fasen, Verrundungen, Formschrägen, versetzte Flächen" als Dinge auf, die es ohne ihn
    nicht gäbe; seit die vier auch am Netz rechnen, war das eine Drohung, die nicht mehr
    stimmt. Übrig bleibt, was wirklich an ihm hängt: die runde Kurve statt des Sehnenzugs,
    das exakte Aushöhlen und STEP.

  Dabei sind fünf Befunde aufgefallen, die niemand gesucht hat: Die Hohlraumfrage wurde in
  `geom` ein zweites Mal beantwortet statt über `types.is_a_cavity` gestellt; `FLAT_ENOUGH`
  stand für zwei verschiedene Werte; das neue Modul zog `trimesh`, `scipy` und `networkx` in
  den Registerstart; die Website nannte 109 Operationen; und `PROMPT_TOOL_COUNT` stand seit
  einer fremden Operation auf 119 statt 120. Alle fünf behoben — die Tokenzahl daneben bleibt
  die Messung von 119 Werkzeugen und ist als solche benannt, denn eine hochgerechnete Messung
  ist keine.

  Daneben stehen aus derselben Liste noch fünf zugesagte Kundenwege offen: der parametrische
  Lochkreis mit gleichem Vertrag in Dialog, Kommandozeile und Agent, die physische
  Kennzeichnung der Varianten, RM-138, RM-087 und RM-127/RM-140.

<a id="rm-163"></a>

- [~] **RM-163 — Bambu Studio druckt einen Mehrfarbauftrag halb und meldet Erfolg.** Robert am
  12.09.2026: „teste das mit mehreren Betten und filamentübergabe usw über alle slicer die wir
  unterstützen bzw alle die installiert sind". Sechs Programme sind auf dieser Maschine
  installiert; gefahren wurden drei Platten mit bis zu vier PLA-Farben, je Platte ein eigener
  Konsolenlauf, alle mit Maschinen- **und** Prozessprofil wie im Druckdialog.

  **Mehrplattenbelegung und Filamentübergabe halten**, und zwar überall, wo der Slicer sie
  kennt: OrcaSlicer und ElegooSlicer rechnen alle drei Platten mit 2, 3 und 2 Spulen und 102,
  199 und 92 Werkzeugwechseln; die Werkzeugnummern bleiben über die Platten hinweg dieselben.
  PrusaSlicer und CuraEngine bekommen einen Filamentsatz und sagen es auch
  (`slicer.overrides_unreachable`). Der Öffnen-Weg schreibt der Orca-Familie **eine**
  Projektdatei mit drei Plattenblöcken.

  **Bambu Studio 2.3 nicht.** Derselbe Würfel einfarbig 4,31 g, zweifarbig 2,82 g — ein
  Filament statt zwei, kein Werkzeugwechsel, Exit 0, kein Wort in Ausgabe oder Protokoll. Bei
  drei Farben 28,07 + 37,95 g statt dreier Mengen; eine Platte mit zwei einfarbigen Körpern
  verschiedener Spule brach ganz ab. Dieselben Dateien laufen bei Orca und Elegoo richtig
  durch, die Übergabe ist also in Ordnung. Versuche, Bambu zu bewegen, sind gemessen und
  gescheitert: `filament_map_mode` im Plattenblock ließ es 300 Sekunden hängen.

  **Solidon sagt es jetzt** (12.09.2026): `handover.spools_left_out` vergleicht die Werkzeuge,
  die die Flächen der Platte benutzen (`threemf.tools_in_use`), mit denen, die der G-Code
  wirklich fährt, und meldet `gcode.spool_left_out` als Fehler mit dem Namen der fehlenden
  Spule. Für Familien ohne Filamentprofile je Spule schweigt die Prüfung — dort ist es die
  bekannte Bauart. Nachweis: sechs Fälle in `tests/test_print_settings.py`, Mutationsprobe
  neun rot.

  **Die Ursache liegt nicht bei Solidon**, und das ist gemessen. Eine von ElegooSlicer selbst
  gespeicherte zweifarbige Projektdatei — dieselbe, die dort ohne jedes geladene Profil mit
  `; filament: 2,1` und 66 Werkzeugwechseln durchläuft — ergibt bei Bambu Studio
  `; filament: 1` und **0,00 g**. Auch der Weg entscheidet nichts: mit `--load-filaments`
  2,82 g, ohne 0,00 g, ganz ohne geladene Profile 0,00 g. Bambus Konsolenzweig ordnet die
  Materialslots einer übergebenen 3MF nicht den Filamenten zu.

  **Offen bleibt die letzte Trennung.** Roberts Datei gilt einem Centauri Carbon 2, den Bambu
  Studio nicht kennt — das erklärt die 0,00 g dort mit. Was fehlt, ist eine von Bambu Studio
  selbst für einen Bambu-Drucker gespeicherte Mehrfarbdatei: Läuft die über die Kommandozeile
  mehrfarbig durch, ist der Unterschied in der Datei auffindbar; läuft sie es nicht, kann der
  CLI-Zweig es nicht, und die Grenze gehört vor dem Lauf benannt statt danach gemeldet.

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

<a id="rm-181"></a>

- [ ] **RM-181 — Handlungsliste und Baugruppenladen an dichten Netzen weiter vermessen.** Die
  Langlochsuche ist am 15.09.2026 auf Bogen statt Paar umgebaut (`slots._Reach`): Hemmungsrad 06
  von 124 s auf 4 s, Hemmungsrad 04 von 126 s auf 9 s — die 9 s sind 38 503 Paare mit je einer
  Flankenprüfung über 6 460 Ecken, reine NumPy-Aufrufkosten, kein Lauf über das Netz mehr. Was
  bleibt: `actions_for(feature, features, mesh=mesh)` kostet mit Netz 0,14 bis 0,17 s je Merkmal
  (die Randringkette wird je Aufruf gebildet, `cavity_chain_state_at`); das Panel ruft es einmal
  je Klick, eine Liste über alle 244 Merkmale des Organizer-Rahmens braucht 32 s. Und die
  3MF-Baugruppe der 19 Uhrenteile lud vor dem Umbau in 179 s, danach in 24 s — 19 Körper mit
  358 000 Dreiecken, jeder einzeln erkannt; §31 nennt für die Erkennung eine Sekunde je Körper
  der genannten Größe, und die größten drei liegen darüber. Abnahme: `actions_for` mit Netz
  unter 50 ms je Merkmal oder mit geteilter Ringbildung je Körper; die drei teuersten Körper der
  Baugruppe einzeln gegen §31 gestellt.

  [Befund](ROADMAP-ARCHIV.md#vierunddreißig-modelle-aus-dem-netz-erkennung-bearbeitung-leistung-15092026).

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
    getrennte Stufenmessung; Topologie beim Reduzieren bewahren (RM-076/RM-077).
  - Puppenhaus-/Schrankparameter sowie Mehrdateien und Plattengruppen.
  - Weitere funktionale Gruppen: Kammer, Gewinde/Einlauf, Bajonett/Rastung,
    Dichtweg/Kanal, Scharnier, Schrift/Einlage und Steckaufnahme/Anschlag.
  - Bausteine: Bajonettpaar, Rastdrehscheibe/Federnabe, Steckhülse und
    Zwei-/Drei-/Vierwegeverbinder, Schlauchtülle, Kanalnaht/Rampe, Raum-/Plattenvorlage.
  - Abläufe: Konturdeckel mit Scharnier/Stift, bündige Schrifteinlage,
    Gegenformeinsatz, Passungsprüfausschnitt, importiertes Gewinde ersetzen,
    Schrift auf Fläche/Bahn sowie drehender und kombinierter Fügeweg.

<a id="rm-186"></a>

- [ ] **RM-186 — Die Erkennung findet die Stirnfläche eines Gewindebolzens auf
  Windows, auf Ubuntu nicht.** `insert_printed_thread` am Quader trägt hier
  neben `printed_thread_thread_1` die Stirnfläche `face_7` (22 mm², 156
  Dreiecke, z ≈ 22) mit `created_by` des Schritts — richtig, der Baustein hat
  sie erzeugt. Die Ubuntu-CI meldete denselben Stand ohne sie: Drei Tests in
  `tests/test_analysis_ui.py`, die „genau ein Merkmal" annahmen, waren hier
  rot (nachgemessen an `93ef16e3c` im Worktree und am HEAD). Seit dem
  16.09.2026 zählen sie die Merkmale des Schritts und prüfen die Zusage in
  beide Richtungen: eines ohne Dach, mehrere unter genau einem; das Merkmal
  der Maßänderungsprobe ist das versprochene (`snap_connector_arm_1`), nicht
  die erste erkannte Fläche. Offen: warum die Fläche auf Ubuntu unter die
  Schwelle von `_large_facet_faces` fällt — gemessen wird das nur auf einer
  Linux-Maschine. Abnahme: die Ursache ist benannt, und beide Plattformen
  zählen dieselben Merkmale.

## Bedienung und Darstellung
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

<a id="rm-074"></a>

- [ ] **RM-074 — Verbleibenden Bildnachweis der Viewport-Serie abschließen.** Die noch fehlende
  Live-Abnahme des Befundsprungs an einem echten Warnprojekt nachholen: Klick im Prüfbericht muss
  zum betroffenen Ort führen und dort eine sichtbare Marke zeigen. Die neun V-Pakete sind umgesetzt.
  Abnahme: reproduzierbarer Klickweg und Bildbeleg mit dem aktuellen Renderer.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-zeichenmodus-und-der-viewport-bekommen-ihre-durchsicht-30082026).

<a id="rm-079"></a>

- [x] **RM-079 — Zeilenlängen der Website über alle Sprachen prüfen.** Die Textbreiten der Website
  als gemeinsame Regel überprüfen und verbleibende überlange Absätze begrenzen. Abnahme:
  tatsächliche Zeilenlängen in allen sechs Sprachen bei schmalen und breiten Fenstern; Karten und
  Spalten dürfen nicht durch eine pauschale Regel unnötig schmal werden.

  **Gemessen und behoben am 14.09.2026.** Drei Sonden in QtWebEngine
  (`.claude/.state/rm-079-website-320-2026-09-14/`) haben alle 42 Seiten bei 320 Punkt Breite
  geladen. `body { overflow: clip }` verhinderte das Rollen und verschluckte stumm, was nicht
  passte: vier deutsche Überschriften mit einem Wort breiter als der Schirm („Allgemeine
  Geschäftsbedingungen“ 79 Punkt über dem Rahmen, „Datenschutzerklärung“ 59,
  „Widerrufsbelehrung“ und „Systemvoraussetzungen“ je 23) und die Sprachliste, die bei 320 bis
  479 Punkt bei −21 begann, weil sie mit `right: 0` am links stehenden Griff hing. Behoben in
  `website/style.css`: Überschriften trennen nach Sprache (`hyphens: auto`, unter 40rem dazu
  `overflow-wrap: anywhere`), die Sprachliste öffnet unter 30rem nach rechts. Nachher: keine
  Überschrift über ihrem Kasten, die Liste bei 320 Punkt zwischen 78 und 230, auf jeder Seite
  `scrollWidth` gleich `clientWidth`; breite Fenster unverändert (bei 1000 Punkt bliebe `left: 0`
  acht Punkt vor dem Rand, deshalb gilt die Regel nur unter 30rem). Die übrigen Sprachen haben
  keine so langen Wörter. `tests/test_website.py` 388 grün nach `tools/stamp_assets.py`.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-zeilen-laufen-zu-lang-31082026).

<a id="rm-084"></a>

- [ ] **RM-084 — Kundentexte gegen die vereinbarte Sprache prüfen.** Website, Handbuch und sichtbare
  Anwendungstexte systematisch auf Roberts persönlichen, natürlichen Ton prüfen und verbleibende
  Stellen überarbeiten. Abnahme: vollständige Liste der geprüften Bereiche, konkrete Textänderungen
  ohne Bedeutungsverlust und vollständige Sprachkataloge.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#rückmeldung-und-freiwillige-unterstützung-gehören-in-die-app-startfläche-31082026).

<a id="rm-088"></a>

- [ ] **RM-088 — Verständlichkeit für Laien im Regelwerk verankern.** Die vorgeschlagene
  Verständlichkeitsregel für Kundentexte entscheiden und ihren Geltungsbereich festlegen. Abnahme:
  freigegebene Formulierung, begründete Ausnahmen für Slicer-Begriffe und gegebenenfalls eine
  kuratierte, sprachübergreifende Prüfung.

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

## KI und Generatoren

<a id="rm-003"></a>

- [ ] **RM-003 — Lizenzkette der gepinnten TripoSG-Bestandteile klären.** Die LICENSE-/NOTICE-Kette
  des konkret eingesetzten TripoSG-Modellstands vollständig dokumentieren und die im NOTICE
  genannten HunyuanDiT-/FlashVDM-Bedingungen gezielt fachlich beziehungsweise mit VAST klären.
  Git-Commit, TripoSG-Gewichte und BiRefNet-Revision sind bereits gepinnt; LICENSE und NOTICE werden
  übernommen. Abnahme: nachvollziehbare Zuordnung jedes eingesetzten Bestandteils zu Revision,
  Lizenz und geklärten Bedingungen. Der bestehende Weg bleibt erhalten.

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

<a id="rm-144"></a>

- [ ] **RM-144 — Orientierungsanalyse über MCP ohne blockiertes Hauptfenster ermöglichen.** `read_analysis` bietet `orientation` im gemeinsamen Werkzeugschema an;
  `MainWindow.run_remote()` lehnt diesen Aufruf bis zum Arbeiteranschluss ausdrücklich ab.
  Die gemeinsame Fähigkeit nach Bauplan §26.6 über den begrenzten Fernaufruf verfügbar machen.
  Abnahme: derselbe Auftrag über Chat und MCP liefert nachvollziehbar dieselbe Analyse, das
  Fenster bleibt bedienbar und Abbruch sowie Zeitgrenze greifen. Die lesende Analyse erzeugt
  keine Geometrieänderung und keine Scheintransaktion.

  [Bauplan-Abgleich und Nachweis](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026).

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

## Tests und Entwicklungswerkzeuge

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

<a id="rm-106"></a>

- [ ] **RM-106 — Plattformunterschiede der Projektdateien dem richtigen Ursprung zuordnen.** Die
  plattformabhängigen Bytes erzeugter Beispielprojekte auf Inhalt und Kompression eingrenzen: nach
  demselben Erzeugerlauf Archivhash und normalisierte Hashes aller entpackten Dateien vergleichen.
  Abnahme: belegte Ursache und dokumentierter Reproduzierbarkeitsvertrag; ausgelieferte Rechtebelege
  bleiben an die eingecheckten Originalbytes gebunden.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

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

<a id="rm-165"></a>

- [ ] **RM-165 — Über `mushroom.stl` in der Wurzel entscheiden.** Die Datei liegt seit dem
  25.08.2026 getrackt im Repository-Stamm (1,4 KB, hereingekommen mit `f934a422`) und wird von
  keiner Datei genannt — der gleichnamige Prüfkörper in `tests/test_slice.py` ist gebaut und
  nicht geladen. `.gitignore` nimmt sie ausdrücklich von der Sperre für `/*.stl` aus, damit sie
  sichtbar bleibt statt verdeckt zu werden. Abnahme: Robert entscheidet, ob sie bleibt — dann mit
  einer Zeile, die sagt wofür —, oder ob sie geht; die Ausnahme in `.gitignore` zieht nach. Der
  Befund stammt aus der Durchsicht vom 11.09.2026 und ist ihr letzter offener Punkt.

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

- [ ] **RM-149 — Zwei Funde aus dem Release-Lauf von 0.4.0 zuordnen.** Beide am 10.09.2026
  gemessen, keiner blockiert eine Auslieferung.

  **Der Vorwarnlauf war rot — und es war keine Version** (zugeordnet 14.09.2026). „Neueste
  Versionen" fährt ohne `constraints.txt` und scheiterte an
  `test_chat_ui.py::test_a_short_chat_scrolls_its_content_without_covering_the_input[320-576-True]`
  mit `assert (0 > 0) is True`. Das Protokoll des Laufs `34461828229` (10.09.) sagt, was sich
  bewegt hatte: **nichts, was Qt berührt** — PySide6 6.11.2 in beiden Jobs, fünf Pakete
  (contourpy, fonttools, matplotlib, pypdf, ruff) sogar älter als die heutigen Pins. Was sich
  unterschied, war das **Runner-Abbild**: der grüne Suite-Job lief auf `ubuntu-24.04`
  20260831.293.1, der rote Vorwarnlauf auf 20260907.300.1, mit anderen Schriften; der Hinweis
  brach eine Zeile kürzer um, der Inhalt passte bei 320 × 576 hinein, und ein Rollbalken, der
  nichts zu rollen hat, stand auf null. Lokal beträgt der Rollweg dort 82 Pixel — eine Zeile
  Schrift. Behoben im Test: Ob gerollt werden muss, wird gemessen (Inhalt höher als sein
  Fenster) statt für drei Fenstergrößen behauptet; das kleinste Fenster (416) muss weiterhin
  rollen, sonst prüfte der Test nichts. Keine Grenze in `pyproject.toml`, denn es gab keine
  Version zu begrenzen. Ob der Vorwarnlauf damit grün ist, sagt der nächste, der startet —
  zwischen zwei Bauten ist das Repository privat, und dann nimmt GitHub keinen an
  (RM-176 im Archiv).

  **Der Website-Abgleich meldete sechs Dateien, die nicht abweichen — behoben am 10.09.2026.**
  Die Ursache lag nicht im Vergleich, sondern in der **Adresse**: `website/.htaccess`
  beantwortet jede Anfrage nach `…/index.html` mit einer 301 auf `…/`, und der Prüfabruf lehnt
  Weiterleitungen grundsätzlich ab (`RejectRedirects`). Von dort kam ein `HTTPError` zurück,
  und `differs` liest den — richtigerweise, fail-closed — als „weicht ab". Betroffen war genau
  das, was eine solche Regel hat: die sechs `index.html`; die anderen 501 Dateien laufen unter
  ihrer eigenen Adresse und waren deshalb ruhig.

  `public_url` gibt für eine Startseite jetzt die Verzeichnisadresse zurück — sie verspricht
  die **ausgelieferte** Adresse, und für `index.html` hat sie eine genannt, die der Server so
  nicht ausliefert. Der eigene Docstring hatte den Fall dabei benannt („zwischen dem
  FTP-Verzeichnis und dem, was beim Kunden ankommt, stehen `.htaccess`, Umschreibungen und
  alles andere, was der Server tut") — richtig gedacht und an der eigenen Startseite
  übersehen. Nachweis:
  `tests/test_website.py::test_the_checked_address_of_a_start_page_is_the_one_the_server_answers`
  liest die Umschreibungsregel aus `.htaccess` und prüft, dass die erzeugte Adresse sie nicht
  auslöst — damit können die beiden Seiten nicht unabhängig voneinander altern. Gegenprobe
  gefahren: ohne den Fix ist der Test rot.

  **Offen bleibt der Abgleich gegen den Server**: dass ein zweiter `--fehlend`-Lauf jetzt null
  meldet, ist am Code belegt und nicht am Netz — das gehört an den nächsten Upload.

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

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-182"></a>

- [ ] **RM-182 — Zwei Lizenzarten bauen, privat und gewerblich.** Roberts Planänderung vom
  15.09.2026 gibt Solidon eine Unterscheidung, die es bisher ausdrücklich nicht hatte. Drei
  Befunde aus dem Ist-Code tragen die Arbeit: `EULA.md:61` verspricht heute *„Die gewerbliche
  Nutzung ist ausdrücklich eingeschlossen und kostet nichts extra"*; `Licence`
  (`app/core/activation/key.py:90`) trägt vier Felder und keine Lizenzart, und die Nutzlast ist in
  ihrer Länge streng geprüft, ein angehängtes Byte also kein gültiger Schlüssel; dasselbe Layout
  steht ein zweites Mal in PHP (`website/api/activation_common.php:583`), jeder Formatwechsel ist
  damit zweiseitig. Entschieden in
  [konzept-lizenzarten-2026-09.md](konzepte/konzept-lizenzarten-2026-09.md): gleicher
  Funktionsumfang für beide Arten (A), Nutzlastformat 2 mit weiter lesbarem Format 1 (B), ein Byte
  für die Art (C), zwei getrennte Vorräte weil der Hauptschlüssel offline liegt (D), unverändert
  ein Geräteplatz (E), kein Ablaufdatum (H). Acht Pakete P1 bis P8 stehen dort in §6; die
  Rechtstexte werden entworfen, nicht freigegeben — die fachliche Prüfung läuft unter RM-093.
  Abnahme: ein Format-1- und ein Format-2-Schlüssel schalten beide frei, Python und PHP lesen
  dieselbe Nutzlast zu demselben Digest, die Art steht im Über-Dialog, und `EULA.md` widerspricht
  dem Preis nicht mehr.

  **Stand 15.09.2026 — gebaut und nachgewiesen:** Format 2 mit weiter lesbarem Format 1 in
  `key.py` und `activation_common.php`, `--kind` als Pflicht im Vorratswerkzeug samt Archivformat 2,
  die Lizenzart im Über-Dialog, Handbuch und fünf Katalogen, und die Rechtstexte ohne den
  Widerspruch. **Die gewerbliche Lizenz hat vier Mehrwerte bekommen** (Robert, 15.09.: zwei
  Geräteplätze statt einem, Support-Antwort in zwei Werktagen, Weitergabe im Betrieb)
  — Entscheidung E des Konzepts ist damit gekippt und als
  Entscheidung K neu gefasst; der Funktionsumfang bleibt gleich. Dabei ist ein Fehler gefunden
  worden, den nur der Test zeigen konnte: Ein `UNIQUE INDEX one_active_device` erzwang den einen
  Platz auf Datenbankebene und hätte den zweiten als `service_unavailable` scheitern lassen.
  PHP 8.5.10 liegt jetzt auf dieser Maschine, die vier zuvor übersprungenen Serverfälle laufen
  (16 statt 10 bestanden), und dreizehn Mutationen über Kern, Dienst und Werkzeug wurden einzeln
  gefahren — alle rot.

  **Was offen bleibt:** die Website (auf Roberts Wunsch zurückgenommen, die Seite bleibt
  preisfrei), die Lizenzart im Aktivierungsdatensatz, und — **vor dem ersten gewerblichen
  Schlüssel** — der `DROP INDEX one_active_device` auf dem laufenden Dienst. Die Rechtstexte sind
  ein Entwurf und gehen zur fachlichen Prüfung unter RM-093. **Eine fünfte Leistung ist
  nach einer Rechtsprüfung am selben Tag gestrichen:** Sicherheitsupdates bis 2033 statt
  2031 für gewerblich. Der Cyber Resilience Act knüpft den Unterstützungszeitraum an das
  Produkt und nicht an den Vertrag (Art. 13 Abs. 8: mindestens fünf Jahre), und beide
  Lizenzarten sind dasselbe Programm — beide bleiben bei 31.10.2031, dem Bestand. Die
  Durchsicht der Website fand dabei zwei eigene Fehler: `make_legal.py` kennt nur `*`
  als Listenzeichen und keine Tabellen, und `test_legal.py` sah es nicht.

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

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-095"></a>

- [ ] **RM-095 — Automatischen Löschlauf auf dem Server belegen.** Den geplanten Server-Löschlauf
  einschließlich Ratelimits und Backups belegen: tatsächliche Pfade und Zeitplan prüfen, Lauf und
  Ausfallalarm dokumentieren. Abnahme: ausgefüllte Freigabepunkte in PRIVACY-COMPLIANCE.md; die
  Codefrist allein ist kein Betriebsnachweis.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-096"></a>

- [ ] **RM-096 — Eigenen Rate-Key für Aktivierungsanforderungen einführen.** Die Pseudonymwurzel der
  Aktivierungs-Ratenbegrenzung vom Signierschlüssel trennen und den neuen Schlüssel kontrolliert
  ausrollen. Abnahme: eigener privater Rate-Key, dokumentierter Deploy-/Rotationsweg und
  funktionierende Begrenzung ohne Nutzung von activation_seed().

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-115"></a>

- [ ] **RM-115 — Releaseakte vor Veröffentlichung verbindlich durchsetzen.** Die Warnungen der
  Releaseakte an aktuellen Kundenartefakten auswerten, alle echten Befunde beheben und anschließend
  die Prüfung als verpflichtenden Abbruch einrichten. Abnahme: erzeugte Evidence plus erfolgreicher
  Release-Check auf den unterstützten Paketwegen; Warnungsumgehungen sind entfernt.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

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

- [~] **RM-162 — Der Hinweistext der Fassung reiste unverändert mit.** Robert am 12.09.2026:
  „bei unserem changelog in der app haben wir auch immer drin stehen das bisher größte update,
  obwohl das nicht stimmt". Nachgemessen: `notes_by_language` in `website/version.json` steht
  seit **0.3.0** unverändert da und ist über 0.3.1 bis 0.4.0 mitgereist. Der Satz behauptet
  zweierlei, das nicht stimmt — „Das bisher größte Update" (0.2.0 hatte 75 Punkte, 0.4.0 hat 62)
  und eine Neuerung aus der Fassung davor („Aus Schritten im Verlauf wird ein eigener Baustein",
  Zeile 534 des Changelogs, also 0.3.0).

  **Der Riegel steht** (12.09.2026). `notes_version` sagt, für welche Fassung der Satz
  geschrieben wurde: `write_version` hält den Paketbau an, solange es eine andere nennt, und
  `_validate_remote_version` weist ein solches Manifest ab. Der Schritt steht als Nummer 2 im
  Release-Ablauf von `/erzeugen`. Nachweis:
  `test_a_note_written_for_an_older_release_is_not_accepted` und
  `test_the_download_build_stops_at_a_note_from_a_former_release`, beide mit Gegenprobe.

  **0.4.0 bleibt, wie es veröffentlicht ist** (Entscheidung Robert, 12.09.2026: „es reicht wenn
  es ab 0.4.1 passt"). Der Grund dafür ist nicht nur Aufwand: `version.json` ist
  Ed25519-unterschrieben, und die Unterschrift deckt jedes Feld außer sich selbst. Eine
  geänderte und nicht neu unterschriebene Datei verwirft **jede** ausgelieferte Installation
  ungelesen — der Kunde erführe dann von gar keinem Update mehr, und das wäre teurer als ein
  schiefer Satz. Der private Schlüssel liegt im Passwortmanager (`tools/sign_version.py`).

  **Offen bleibt der Handgriff beim 0.4.1-Bau**, und der Riegel erzwingt ihn: Die sechs Sätze
  unten in `notes_by_language` eintragen, `"notes_version": "0.4.1"` daneben, dann signieren und
  hochladen. Geschrieben sind sie aus dem 0.4.1-Abschnitt des Changelogs — Langloch, „Im Bild
  einstellen", die Handlungen an einem Ort:

  - **de** — Neu ist vor allem das Langloch: Sie setzen es beim Bohren mit einem Haken oder
    ziehen eine vorhandene Bohrung nachträglich in die Länge. Eine gewählte Bohrung stellen Sie
    mit „Im Bild einstellen" direkt im Modell ein, mit Griff und Maßlinien. Und die Handlungen
    an Körper und Merkmal stehen rechts an einem Ort statt in drei Menüs. Die Demo bleibt
    vollständig und ohne Schlüssel, bis zum 30.10.2026.
  - **en** — New above all is the slot: you tick a box while drilling, or stretch a bore that is
    already there. A selected bore you adjust right in the model with *Set in the view*, with a
    handle and dimension lines. And the actions on a body or a feature now sit in one place on
    the right instead of in three menus. The demo stays complete and needs no key, until 30
    October 2026.
  - **es** — Lo nuevo sobre todo es el agujero alargado: lo marca al taladrar, o estira uno
    redondo que ya está en la pieza. Un taladro seleccionado lo ajusta directamente en el modelo
    con «Ajustar en la vista», con tirador y líneas de cota. Y las acciones sobre un cuerpo o una
    característica están en un solo sitio a la derecha, en vez de en tres menús. La demo sigue
    completa y sin clave, hasta el 30 de octubre de 2026.
  - **fr** — Surtout, le trou oblong : vous le cochez en perçant, ou vous étirez un perçage déjà
    présent. Un perçage sélectionné se règle directement dans le modèle avec « Régler dans la
    vue », poignée et lignes de cote à l’appui. Et les actions sur un corps ou une forme tiennent
    en un seul endroit à droite, au lieu de trois menus. La démo reste complète et sans clé,
    jusqu’au 30 octobre 2026.
  - **it** — Soprattutto l’asola: la spunti mentre fori, oppure allunghi un foro che c’è già. Un
    foro selezionato lo imposti direttamente nel modello con «Imposta nella vista», con maniglia
    e linee di quota. E le azioni su un corpo o una forma stanno in un posto solo, a destra,
    invece che in tre menu. La demo resta completa e senza chiave, fino al 30 ottobre 2026.
  - **pt** — Sobretudo o furo oblongo: marca-o ao furar, ou estica um furo que já lá está. Um
    furo selecionado ajusta-o diretamente no modelo com «Ajustar na vista», com pega e linhas de
    cota. E as ações sobre um corpo ou uma característica ficam num só sítio à direita, em vez de
    em três menus. A demo continua completa e sem chave, até 30 de outubro de 2026.

  Abnahme: Der Satz im Update-Fenster von 0.4.1 nennt, was in 0.4.1 neu ist, `notes_version`
  steht auf `0.4.1`, und `tools/sign_version.py --check` bestätigt die Unterschrift.

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
