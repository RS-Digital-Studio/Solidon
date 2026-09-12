# ROADMAP — Arbeitsliste

Abgleich vom **08.09.2026** gegen Bauplan §40, Quelltext, Tests, Paketmetadaten
und Git-Verlauf, **nachgeführt am 10.09.2026** — jeder offene Punkt einmal am
heutigen Code nachgemessen; was dabei erledigt, überholt oder falsch
beschrieben war, steht am Punkt. Der lokale Veröffentlichungsstand ist
**0.4.0** (`website/version.json`, seit dem 10.09.2026; die Mac-Pakete gingen
unsigniert hinaus, siehe RM-001). Die früheren Durchsichten und Messreihen stehen im
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
Mac-/Linux-Nachweise und die Absicherung der Releaseakte, außerdem die bereits
geplante CRA-Betriebsvorbereitung vor dem 11.09.2026. Eine zurückgestellte
Produktentscheidung oder ein kostenpflichtiger Lauf wird durch diesen
Abgleich nicht freigegeben.

## Was offen ist

Jede Zeile führt zu genau einem offenen Punkt. Die letzte Spalte nennt den nächsten Schritt; Begründung und Abnahme stehen am Punkt.

| Punkt | steht unter | wartet auf |
|---|---|---|
| [RM-001 — Signierung und Notarisierung der Kundenpakete belegen](#rm-001) | Plattformen, Pakete und Grafik | Die Identität kommt jetzt aus dem Schlüsselbund; offen bleiben `MACOS_SIGNING_MODE` zurück auf `notarized` und ein Bau, der es belegt |
| [RM-011 — Erstinstallation auf einem fremden Rechner abnehmen](#rm-011) | Plattformen, Pakete und Grafik | Fremdrechner ohne Entwicklungsumgebung von Download bis Export prüfen |
| [RM-021 — Native Fensterlebensdauer am aktuellen Renderer abnehmen](#rm-021) | Plattformen, Pakete und Grafik | Sporadische Riss-/Hängerfamilien gezielt wiederholt prüfen; vollständiges Tor ist grün |
| [RM-050 — Kopierkosten messen und verbleibende VTK-Geometrie ablösen](#rm-050) | Plattformen, Pakete und Grafik | Kopier-/Pufferkosten messen und VTK aus der Bereichsprüfung ablösen |
| [RM-051 — Renderer und Grafiklaufzeit in Linux- und Mac-Paketen abnehmen](#rm-051) | Plattformen, Pakete und Grafik | Grafik und Eingabe der veröffentlichten 0.4.0-Pakete für Linux und Mac abnehmen |
| [RM-055 — Neue Paketwerkzeuge im installierten Kundenpaket abnehmen](#rm-055) | Plattformen, Pakete und Grafik | Flatpak-Lauf belegen; die CI baut mit Inno Setup 6 und protokolliert die Fassung nicht |
| [RM-104 — Verbleibende Mac- und Unix-Befunde mit aktueller CI-Abdeckung abnehmen](#rm-104) | Plattformen, Pakete und Grafik | Intel-Hänger und übrige Unix-Fenster-/Export-/Chatfälle abnehmen |
| [RM-107 — Ubuntu-Workerabbruch mit aktuellem Testbestand zuordnen](#rm-107) | Plattformen, Pakete und Grafik | Auslöser mit aktueller Testreihenfolge und Widget-/Worker-Lebensdauer eingrenzen |
| [RM-114 — Vereinfachungsziele auf Apple Silicon vermessen](#rm-114) | Plattformen, Pakete und Grafik | Hohlkugel-Zielreihe samt echter Warnung auf Apple Silicon messen |
| [RM-117 — Öffentliche Downloadlinks vollständig in die Paketprüfung aufnehmen](#rm-117) | Plattformen, Pakete und Grafik | Die stille Lücke ist zu; offen bleiben die Prüfsummen-Entscheidung und der Abruf gegen den Server für 0.4.0 |
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
| [RM-080 — Restumfang der Trennen-Serie mit aktuellem Code abgleichen](#rm-080) | Geometrie, Erkennung und Druckvorbereitung | Geschützte Flächen an die Ebenensuche hängen und im Dokument speichern; schräge Ebenen, Symmetrie, Schaustück |
| [RM-086 — Achsenkonvention beim GLB-Import mit Migration klären](#rm-086) | Geometrie, Erkennung und Druckvorbereitung | GLB-Achsenkonvention mit Herkunft und Migration festlegen |
| [RM-087 — Aushöhlen mit wählbarer offener Seite planen](#rm-087) | Geometrie, Erkennung und Druckvorbereitung | Wählbare Öffnungsfläche am Puppenhaus-Fall umsetzen |
| [RM-128 — Bearbeitbarkeit erkannter Flächen entscheiden](#rm-128) | Geometrie, Erkennung und Druckvorbereitung | Entscheiden, ob eine Verrundung ohne jede Operation in der Merkmalsliste stehen soll |
| [RM-132 — Freiformerkennung am Ein-Sekunden-Ziel messen](#rm-132) | Geometrie, Erkennung und Druckvorbereitung | 1,400 auf 1,004 s gebracht; offen ist die Entscheidung zwischen Stapelumbau der Einpassungen und einem neu gefassten Ziel |
| [RM-133 — Rückmeldung zur Volumenänderung beim Merkmaldrehen entscheiden](#rm-133) | Geometrie, Erkennung und Druckvorbereitung | Kundennutzen eines Hinweises zur korrekten Volumenänderung entscheiden |
| [RM-138 — Gespeicherten Bausteinstand beim Öffnen wählbar erhalten](#rm-138) | Geometrie, Erkennung und Druckvorbereitung | Wahl zwischen aktuellem und noch verfügbarem früherem Bausteinstand ermöglichen |
| [RM-139 — Geometrische Orientierungskandidaten aus der konvexen Hülle ableiten](#rm-139) | Geometrie, Erkennung und Druckvorbereitung | Hüllnormalen sind gebaut; es fehlt die Messung gegen die vollständige Kandidatenliste |
| [RM-147 — Die acht beauftragten Konstruktionserweiterungen bauen](#rm-147) | Geometrie, Erkennung und Druckvorbereitung | Die ganze Kanten- und Flächenarbeit greift an beiden Kernen — offen bleiben Zeiger und Rechtsklick an der Kante, die Anbindung des Flächengriffs an die gewählte Fläche und fünf zugesagte Kundenwege |
| [RM-163 — Bambu Studio druckt einen Mehrfarbauftrag halb und meldet Erfolg](#rm-163) | Geometrie, Erkennung und Druckvorbereitung | Solidon meldet den Verlust; offen ist die Ursache bei Bambu — dessen eigene Mehrfarbdatei gegen Solidons stellen |
| [RM-164 — Creality Print: Erkennung steht, der Konsolenlauf ist ungeprüft](#rm-164) | Geometrie, Erkennung und Druckvorbereitung | Slicer einrichten, dann Öffnen- und Konsolenweg mit mehreren Spulen abnehmen |
| [RM-070 — SpaceMouse auf macOS und Linux am echten Gerät abnehmen](#rm-070) | Bedienung und Darstellung | Der Mac ist gefahren; offen bleiben Linux, die 3DxWare-Mausemulation und die Bildrate an 1 Mio. Dreiecken |
| [RM-074 — Verbleibenden Bildnachweis der Viewport-Serie abschließen](#rm-074) | Bedienung und Darstellung | Befundsprung und sichtbare Marke an einem echten Warnprojekt zeigen |
| [RM-079 — Zeilenlängen der Website über alle Sprachen prüfen](#rm-079) | Bedienung und Darstellung | Textbreiten in sechs Sprachen auf schmalen und breiten Fenstern prüfen |
| [RM-084 — Kundentexte gegen die vereinbarte Sprache prüfen](#rm-084) | Bedienung und Darstellung | Kundentexte systematisch prüfen und alle Sprachfassungen nachziehen |
| [RM-088 — Verständlichkeit für Laien im Regelwerk verankern](#rm-088) | Bedienung und Darstellung | Verständlichkeitsregel und begründete Ausnahmen entscheiden |
| [RM-090 — Serie zum Übergabestatus entscheiden](#rm-090) | Bedienung und Darstellung | Nächsten Umfang aus den fünf Vorschlägen des Produktkompasses entscheiden |
| [RM-108 — Abbauzeit des Schlüsseldialogs messen und begrenzen](#rm-108) | Bedienung und Darstellung | Schlüsseldialog während laufender Abfrage ohne Wartefrist schließen |
| [RM-131 — Zurückgestellten Mehrfachimport entscheiden](#rm-131) | Bedienung und Darstellung | Zurückgestellt; bei Wiederaufnahme Mehrfachimport mit gemeinsamer Lage planen |
| [RM-135 — Zugewiesene Höhe der Filamentkarte vollständig nutzen](#rm-135) | Bedienung und Darstellung | Korrigierten Höhenvertrag nach grüner Windows-Abnahme auf macOS bestätigen |
| [RM-136 — Gezeichnetes Fensterschema und Bildbeschreibungen aktualisieren](#rm-136) | Bedienung und Darstellung | Fensterschema, Bildunterschriften und Alternativtexte aller Sprachen nachziehen |
| [RM-003 — Lizenzkette der gepinnten TripoSG-Bestandteile klären](#rm-003) | KI und Generatoren | Lizenzkette der eingesetzten Modellrevisionen klären |
| [RM-004 — Echte Text- und Bildgenerierung über alle Zielplattformen abnehmen](#rm-004) | KI und Generatoren | Echte Text-/Bildläufe auf Windows, macOS und Linux dokumentieren |
| [RM-014 — Zusätzliche Formenregel und zugehörige Suite-Abnahme entscheiden](#rm-014) | KI und Generatoren | Zusätzliche Formenregel entscheiden; bei Änderung Suite vorher/nachher |
| [RM-016 — Agenten-Suite gegen das aktuelle Vorgabemodell messen](#rm-016) | KI und Generatoren | Suite mit festgehaltenem aktuellem Modell und vergleichbarer Referenz messen |
| [RM-054 — Prompt-Grundlast mit dem aktuellen Werkzeugbestand messen](#rm-054) | KI und Generatoren | Zahlen stehen auf 119/28.281; neu messen, sobald die nächste Operation dazukommt |
| [RM-069 — Verhaltensabnahme der kompakten Werkzeugschemata nachholen](#rm-069) | KI und Generatoren | Vergleichbare Suitequoten vor und nach der Schema-Verdichtung nachweisen |
| [RM-081 — Ollama-Laufzeit und verbleibende Optimierungen abnehmen](#rm-081) | KI und Generatoren | Warm-/Kaltstart, Antwortqualität und Schemakürzungen gemeinsam messen |
| [RM-144 — Orientierungsanalyse über MCP ohne blockiertes Hauptfenster ermöglichen](#rm-144) | KI und Generatoren | Gemeinsame Orientierungsanalyse an den fernbedienten Arbeiterweg anschließen |
| [RM-020 — Sicherung der eigenständigen Druckprojekte belegen](#rm-020) | Tests und Entwicklungswerkzeuge | Sicherungsweg entscheiden und Wiederherstellung belegen |
| [RM-025 — Unabhängige Sollwerte für geometrische Prüfungen absichern](#rm-025) | Tests und Entwicklungswerkzeuge | Geometrische Sollwerte aus unabhängiger Rechnung oder analytischen Größen belegen |
| [RM-098 — Restliche Regelwerk-Nachträge abgleichen](#rm-098) | Tests und Entwicklungswerkzeuge | Wächter für `paths:` und Regelnummern, `auslieferung.md`, und die vierfache Suite-Anleitung |
| [RM-099 — Konzeptbestand und veraltete Verweise ordnen](#rm-099) | Tests und Entwicklungswerkzeuge | Verweise sind vollständig gültig; offen ist nur noch das Umräumen — Umfang entscheidet Robert |
| [RM-100 — Sichtbares Terminalfenster aus dem Prozesstest vermeiden](#rm-100) | Tests und Entwicklungswerkzeuge | Flagge gesetzt; offen ist die Sichtprüfung unter Windows Terminal |
| [RM-103 — Große Kernfunktionen nach konkretem Wartungsbedarf aufteilen](#rm-103) | Tests und Entwicklungswerkzeuge | Auswertung und weitere große Funktionen nach Wartungsbedarf priorisieren |
| [RM-106 — Plattformunterschiede der Projektdateien dem richtigen Ursprung zuordnen](#rm-106) | Tests und Entwicklungswerkzeuge | Archiv- und Inhaltshashes nach gleichem Erzeugerlauf vergleichen |
| [RM-113 — Besitzerprüfung der Tokendatei auf dem Windows-Runner belegen](#rm-113) | Tests und Entwicklungswerkzeuge | Besitz und ACL einer tatsächlich nutzereigenen Runner-Datei belegen |
| [RM-134 — Zusammenführung duplizierter Testhilfen entscheiden](#rm-134) | Tests und Entwicklungswerkzeuge | Umfang der Zusammenführung belegter Testhilfen entscheiden |
| [RM-137 — Sitzungsende im tatsächlichen Editorbetrieb abnehmen](#rm-137) | Tests und Entwicklungswerkzeuge | Echtes SessionEnd und Freigabe des Sitzungsgebiets nach Neustart beobachten |
| [RM-002 — netcup-AVV und Freigabe der Rechtstexte belegen](#rm-002) | Veröffentlichung, Betrieb und Vertrieb | netcup-AVV belegen und zugehörige Rechtstexte fachlich abgleichen |
| [RM-006 — Nächsten messbaren Schritt für die Sichtbarkeit festlegen](#rm-006) | Veröffentlichung, Betrieb und Vertrieb | Zielgruppe, Kanal und messbares Ziel des nächsten Außenauftritts festlegen |
| [RM-008 — DMARC-Eintrag öffentlich prüfen und gegebenenfalls einrichten](#rm-008) | Veröffentlichung, Betrieb und Vertrieb | DMARC einrichten und legitimen Mailversand prüfen |
| [RM-030 — Impressum nach Vergabe einer USt-IdNr. oder W-IdNr. ergänzen](#rm-030) | Veröffentlichung, Betrieb und Vertrieb | Bereits vergebene USt-IdNr./W-IdNr. klären; gegebenenfalls Impressum ergänzen |
| [RM-034 — Versicherungsschutz für Software und Produktschäden klären](#rm-034) | Veröffentlichung, Betrieb und Vertrieb | Versicherungsangebote gegen die tatsächlichen Risiken prüfen lassen |
| [RM-035 — EULA wirksam in den Bestellvorgang einbeziehen](#rm-035) | Veröffentlichung, Betrieb und Vertrieb | Produktgrenzen und EULA im vollständigen Bestellweg rechtlich prüfen |
| [RM-036 — Vertrag und Freistellungen des Zahlungsdienstleisters prüfen](#rm-036) | Veröffentlichung, Betrieb und Vertrieb | Konkreten Anbietervertrag und Haftungsübernahme entscheiden |
| [RM-061 — Verkaufsbereitschaft und Ende der Demo vorbereiten](#rm-061) | Veröffentlichung, Betrieb und Vertrieb | Verkaufsbau bis 25.10. vorbereiten; Start am 01.11.2026 |
| [RM-149 — Zwei Funde aus dem Release-Lauf von 0.4.0 zuordnen](#rm-149) | Veröffentlichung, Betrieb und Vertrieb | Der Website-Fehlalarm ist behoben; offen bleibt der rote Vorwarnlauf gegen die neuesten Abhängigkeiten |
| [RM-162 — Der Hinweistext der Fassung reiste unverändert mit](#rm-162) | Veröffentlichung, Betrieb und Vertrieb | Der Riegel steht; die sechs Sätze für 0.4.1 stehen bereit und werden beim Bau eingetragen |
| [RM-091 — CRA-Meldebereitschaft vor dem 11.09.2026 herstellen](#rm-091) | Veröffentlichung, Betrieb und Vertrieb | Zugänge, Vertretung, Alarmierung und Probelauf vor dem 11.09.2026 belegen |
| [RM-092 — Verkaufskonzept für den geplanten Start abschließen](#rm-092) | Veröffentlichung, Betrieb und Vertrieb | Verkaufskonzept bis 15.10. abschließen; Start am 01.11.2026 |
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

Die Veröffentlichung ist erfolgt; der lokale Downloadstand ist 0.3.5. Windows, Flatpak, AppImage und beide Mac-Architekturen sind keine neuen Bauvorhaben mehr. Signierung, Notarisierung, Fremdrechnerabnahme und noch fehlende Betriebsnachweise bleiben offen; siehe RM-001 und RM-002.

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

  **Was offen bleibt, ist nicht Code:** `MACOS_SIGNING_MODE` steht als Repository-Variable auf
  `unsigned` und gehört vor dem Bau von 0.4.1 zurück auf `notarized`. Sie steht in keinem
  Repository-Text, nur in den Einstellungen; wer sie vergisst, liefert eine zweite unsignierte
  Fassung aus, ohne dass ein Lauf rot wird. Erst ein Bau mit `notarized` belegt, dass die
  Reparatur trägt.

  **Nebenbefund, gehört zu RM-084:** Die FAQ begründet die fehlende Notarisierung an zwei
  Stellen mit „sobald das Apple-Konto steht" (`website/index.html`). Das Konto und alle acht
  Geheimnisse stehen längst; blockiert hat allein der Identitätsname.

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

<a id="rm-065"></a>

- [x] **RM-065 — TLS und Update-Prüfung auf einem Kunden-Mac bestätigen.** Der certifi-Rückfall und
  die Vorrangregel für eine Firmen-CA sind gebaut; Paketinhalt allein genügt nicht, und deshalb
  stand der Punkt offen, obwohl der Code seit dem 27.08.2026 stand.

  **Abgenommen am 12.09.2026** (Robert: „die spacemaus und update auf dem mac funktionieren jetzt
  problemlos"). Die Aktualisierungsprüfung läuft auf dem Mac durch; ein TLS-Grund aus dem Protokoll
  wird damit nicht gebraucht.

  Was der Nachweis **nicht** deckt und auch nie sollte: die Firmen-CA. Ihre Vorrangregel ist gebaut
  und geprüft, aber ein Mac hinter einem abfangenden Firmenproxy stand nie zur Verfügung — das ist
  keine offene Arbeit, sondern eine benannte Grenze des Nachweises.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-erste-kundenbericht-aus-dem-feld-27082026).

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

<a id="rm-161"></a>

- [x] **RM-161 — Das Lizenzmanifest deckte zwei Grenzdateien nicht mehr.** Am 12.09.2026
  behoben, und zwei Annahmen des Punktes haben sich dabei erledigt.

  **Der Erzeuger läuft auf dieser Maschine**, ohne eine von Hand aktivierte Umgebung:
  `python tools/build_licence_module.py` übersetzt die sieben Freischaltmodule und signiert
  `packaging/build/licence.manifest` in einem Zug. Danach ist `tests/test_packaging.py`
  vollständig grün (91 Fälle). Die Notiz über `vswhere` stammt von einer anderen Lage und gilt
  hier nicht.

  **Und das Manifest ist nicht eingecheckt** — `.gitignore` schließt `build/` aus. Damit ist
  auch die offene Frage beantwortet: Der Test gehört **nicht** zur Marke `rendered`. Er
  überspringt sich selbst, wenn kein gebautes Prüfmodul da ist („kein gebautes Prüfmodul —
  nichts zu vergleichen"), ist auf einem frischen Klon also nie rot. Rot wird er genau dort, wo
  er es soll: auf einer Maschine, auf der gebaut **und** danach eine Grenzdatei geändert wurde.
  Das war hier der Fall, und zwar zweimal nacheinander durch eigene Arbeit an
  `core/export/writer.py` (RM-140, RM-141). Ein `rendered` daran hätte genau diese Meldung
  abgeschaltet.

  Nicht gebaut wurde ein **Paket**: Dass eines ungesperrt startet, zeigt erst der nächste
  Paketbau, und der gehört zu [RM-011](#rm-011) und [RM-055](#rm-055). Der Weg dorthin ist
  gesperrt, falls jemand den Schritt vergisst — `packaging/solidon3d.spec` bricht ohne das
  übersetzte Prüfmodul ab, `tools/make_installer.py` prüft das Manifest noch einmal, und
  `/erzeugen` nennt den Lauf an seinem Platz.

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

<a id="rm-023"></a>

- [x] **RM-023 — Verweisfilter über wechselnde Objektkennungen hinweg prüfen.** Am 12.09.2026
  gebaut. **Der Befund stand und war nachmessbar**: Zwei Klötze mit je einer Bohrung, eine
  Passung auf die rechte, danach *In Einzelteile zerlegen*. Danach hieß die rechte Bohrung
  `obj_3:hole_1`, die Passung zeigte weiter auf `obj_1:hole_2` — und statt der Frage aus §21.3
  kam eine Sackgasse: „Die Schritte ab dort zurücknehmen und vor der Passung ausführen."

  `orphans.lineage()` liest die Abstammung aus dem Stapel — `Operation.inputs` und `outputs`
  bilden den DAG (§12) —, und die Kandidaten kommen aus allen Körpern, in deren Herkunft der
  genannte steht. **Nicht aus allen überhaupt**: Zwei Platten tragen beide ein `hole_1`, und
  eine Frage nach einem fremden Loch ist schlechter als keine. Hängen die Kandidaten an
  mehreren Körpern, nennt jede Antwort ihren (`obj_3:hole_1`); sonst bleibt es bei der bloßen
  Kennung, damit der Normalfall unverändert liest. Die Antwort trägt den Körper mit — ein
  Umschreiben nur der Merkmalskennung zeigte weiter auf den falschen.

  **Ein Operationsverweis bleibt bei seinem Körper**, und das ist die Darstellung und keine
  Vorsicht: Ein `kind="feature"`-Parameter trägt nur die Kennung und wird gegen `inputs[0]`
  aufgelöst. Eine Antwort auf ein anderes Objekt ließe sich dort nicht hinschreiben; sie
  anzubieten hieße, eine Wahl zu stellen, die beim Übernehmen still verloren geht.

  Nachweis: drei Fälle in `tests/test_orphans.py` — die Frage kommt und nennt beide Körper, ein
  unbeteiligter Körper mit demselben Namen steht nicht zur Wahl, und ein Operationsverweis
  bekommt keinen fremden. Drei Gegenproben, jede einzeln rot: ohne den Stammbaum, über alle
  Körper, und ohne die Grenze für Operationsverweise. Die getrennte Paarbildung für die
  Hervorhebung (`_candidate_pairs`) ist dabei entfallen — die Kandidaten **sind** jetzt Paare.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#das-fundament-der-wahrnehmung-22082026).

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

<a id="rm-039"></a>

- [x] **RM-039 — Fehlende Schnittflächen an offenen Netzen verständlich erklären.** Der Satz
  steht seit dem 10.09.2026, der **Knopf** seit dem 12.09.2026: `split.uncapped` trägt in
  `FINDING_ACTIONS` jetzt *Reparieren und erneut versuchen* — dieselbe Handlung wie die
  anderen „nicht geschlossen"-Befunde, weil es dieselbe Ursache ist. *Stellen zeigen* steht
  nicht daneben: Der Befund trägt keinen Ort, und ein Knopf ins Leere ist schlechter als
  keiner.

  **Und der Knopf braucht seinen Körper.** Eine Berichtshandlung liest ihr Ziel aus dem Befund
  und nicht aus der Auswahl; `split_at_plane` rechnet auf einem Netz und kennt keine
  Kennungen, also verortet sie die Operation — dieselbe Aufteilung wie beim Aushöhlen.

  Nachweis: zwei Fälle in `tests/test_autosplit.py` (die Handlung steht im Bericht, der Befund
  nennt `obj_7`), Gegenprobe ohne die Verortung rot.

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

- [~] **RM-080 — Restumfang der Trennen-Serie mit aktuellem Code abgleichen.** **Geschützte
  Sichtflächen sind halb gebaut** (nachgemessen 10.09.2026): Der Kern kennt `protect` samt
  Auswertung, und der Viewport kann sie markieren und anzeigen. Was fehlt, sind die zwei Enden
  dazwischen — **kein Aufrufer reicht die geschützten Flächen an die Schnittebenensuche
  weiter**, und die Markierung ist ausdrücklich sitzungsgebunden: Sie steht in keinem Feld des
  Dokuments und übersteht kein Speichern. Ein Kunde, der Flächen schützt und die Datei
  schließt, hat seine Arbeit verloren.

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

<a id="rm-087"></a>

- [ ] **RM-087 — Aushöhlen mit wählbarer offener Seite planen.** Aushöhlen um die Auswahl der zu
  öffnenden Fläche erweitern; das Puppenhaus-Beispiel dient als Abnahmefall. Abnahme: wählbare
  Vorder-/Seitenöffnung, korrekte Wandstärke, reproduzierbarer Verlauf und anschließendes
  Deckelerzeugen an dieser Öffnung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-097"></a>

- [x] **RM-097 — Verbleibende Kernbefunde des Reviews einzeln beheben.** **Alle sechs
  Stellen sind am 12.09.2026 gefallen**, und eine davon war schon vorher weg:

  * Der `OSError` beim Lesen einer verknüpften Quelle hieß „sie ist beschädigt" und
    behauptete damit etwas über den **Inhalt**, wo das Betriebssystem über den **Zugriff**
    gesprochen hat — fehlende Rechte, ein getrenntes Netzlaufwerk, ein Wechselmedium. Der
    Satz nennt jetzt, was feststeht, und der Systemgrund reist als Wert mit. Die
    `BadZipFile`-Stelle daneben bleibt: Dort ist „beschädigt" die Wahrheit.
  * *Prüfstück* und *Drehdeckel* bekommen einen Zähler (`Scene.unused_name`). Zwei Objekte
    mit demselben Namen sind im Baum eines; die Kopie macht es seit je anders. Der Zähler
    beginnt bei zwei — der erste heißt, wie er heißt.
  * **`_fell_apart` war längst entdoppelt**: Beide Fassungen tragen je *eine* Anweisung, den
    Aufruf an `boolean.fell_apart`; was doppelt aussieht, sind die Docstrings, und die
    beschreiben verschiedene Fälle (Schrift gegen Muster). Nachgemessen am Code, nicht
    geglaubt.
  * Der Menüeintrag heißt ***Drucken vorbereiten …*** statt *Druckeinstellungen …* — ein
    Laie sucht den Weg zum Drucker nicht unter einem Wort für Einstellungen, und der Weg
    dahinter ist der Slicer-Weg. Der Dialog behält seinen Namen: Der Eintrag nennt die
    Handlung, der Dialog den Inhalt. Handbuch und Befehlspalette sind nachgezogen, die zwei
    langen Handbuchtexte in allen fünf Sprachen umgeschlüsselt.

  **Die zwei Zahlen sind am 12.09.2026 gefallen**, beide nach dem Muster von
  `overhang_angle`: Die Schichtanalyse bleibt von Profilen entkoppelt und nimmt Zahlen, und
  der Aufrufer, der einen Drucker kennt, gibt dessen Zahl herein.

  * **`BRIDGE_FROM`** (`slice/analysis.py`) wird zu `bridge_from` — ein Parameter bis
    `_bridge_width` hinunter, geprüft wie der Winkel daneben (Regel 17). Der runde Millimeter
    begründete sich mit „zwei Bahnen einer 0,4er-Düse", und die sind **0,84**; genau das ist
    `Profile.minimum_wall_thickness`. Hereingegeben wird sie an den vier Stellen, die den
    Winkel schon aus `profiles.analysis_limits` holen — die Funktion liefert beide Grenzen in
    einem Aufruf. Gemessen an zwei Pfeilern mit **1,0 mm Spalt** und einer Decke darüber: der
    Centauri meldet **0,9 mm** Brücke, eine 0,8er Düse (1,68) schweigt zu Recht, und die alte
    Codezahl schwieg für beide. Der Messwertspeicher des Druckdialogs trägt die Wand seither
    im Schlüssel neben dem Winkel — sein Geometriekontext kennt die Materialien nicht, und ein
    Ergebnis, das einen Materialwechsel überlebt, spräche über einen Drucker, den niemand mehr
    gemeint hat.
  * **`NOISE_VOLUME`** (`geom/difference.py`) bleibt als Untergrenze der **Rechnung** stehen
    und ist nicht mehr die der **Änderung**: `Difference.noise_volume` kommt aus
    `Profile.smallest_printable_volume`, dieselbe Grenze und dieselbe Begründung wie bei
    `boolean.without_effect`. Die Szene bringt das Profil mit (`compare_scenes`). Gemessen an
    einem Quader, der um zwei Zehntausendstel Millimeter wächst: **0,02 mm³**, mehr als das
    Rauschen und ein Fünfzehntel dessen, was der Centauri überhaupt hinterlässt — die
    Differenzansicht meldete das als Änderung, und im Chat stand „+0,00 cm³".

  Nachweis: zwei Fälle in `tests/test_slice.py`, drei in `tests/test_difference.py` und der
  Anschlusstest `test_the_layer_analysis_takes_both_limits_from_the_material` — nicht „der Kern
  kann es", sondern „das Fenster tut es". Dazu die Attrappe in `test_print_settings_ui.py`, die
  `bridge_from` ausdrücklich in ihrer Signatur führt und rot wird, wenn der Dialog die Zahl
  nicht mehr hereingibt. Vier Gegenproben, jede einzeln rot: die Codezahl zurück in
  `_bridge_width`, die Konstante zurück in `Difference.changed`, `compare_scenes` ohne
  Weitergabe des Profils, und das Fenster ohne die eine Zeile.

<a id="rm-109"></a>

- [x] **RM-109 — Schichtanalyse der Rändelplatte gezielt beschleunigen.** Am 12.09.2026 gebaut.
  **Die Vorprüfung war es nicht.** Der Punkt stand unter der Annahme, die vorgeschaltete Frage
  „lohnt eine Messung überhaupt" koste die Zeit; gemessen kosteten die zweiunddreißig
  Vorprüfungen der Platte zusammen **1,8 Millisekunden**. Die 4,24 Sekunden lagen in den beiden
  Schichten, die tatsächlich gemessen wurden: Die Halbierung stellt je Schicht sieben Fragen,
  und jede Frage pufferte alle 2 898 getrennten Konturen der Rändelzone auf einmal — 300
  Millisekunden für eine Ja/Nein-Antwort.

  `_survives_opening` beantwortet das Nein jetzt aus den Teilen. Der Flächenverlust ist eine
  Summe über sie, und jeder Summand ist nicht negativ: Reißt schon der dünnste Teil das Budget,
  steht die Antwort fest. Das **Ja** bleibt die ganze Form — berühren sich die Öffnungen zweier
  Teile, zählt die geteilte Fläche in der Summe doppelt, der Teileweg unterschätzt den Verlust
  also und taugt nur für die eine Richtung. `WIDTH_SCAN_PARTS = 64` deckelt, wie viel
  vergebliche Arbeit davor anfallen darf; die Vorsortierung nach mittlerer Weite (vierfache
  Fläche über dem Umfang) rechnet Fläche und Umfang aller Teile in einem Feld, weil sie einzeln
  abgefragt 15 Millisekunden je Frage kosteten — mehr als die Puffer danach.

  | Körper | vorher | nachher | kleinste Breite | Prüfsumme der Breiten |
  |---|---|---|---|---|
  | Rändelplatte (45 884 Dreiecke) | 6,98 s | **3,53 s** | 0,0277 mm | 60,0554 |
  | Rippenplatte | 0,017 s | 0,019 s | 0,3043 mm | 56,0860 |
  | Kugel | 0,072 s | 0,073 s | 2,0000 mm | 400,0000 |

  Befunde überall gleich, Schicht für Schicht — die Prüfsumme ist die Summe aller gemeldeten
  Breiten. `_survives_opening` fiel von 4,31 auf 0,86 Sekunden, von sechzig auf
  vierundzwanzig Prozent des Laufs. Die beiden kleinen Körper verlieren einen Wimpernschlag an
  die Vorsortierung; bei einer einzelnen Kontur steht sie gar nicht erst an.

  Nachweis: vier Fälle in `tests/test_slice.py` — der Teileweg antwortet über einen Bereich von
  Weiten wie die ganze Form, ein dünner Streifen unter zweihundert breiten wird weiter gefunden,
  der Deckel gilt, und der dünnste Teil steht vorn. Vier Gegenproben, jede einzeln rot: ohne den
  exakten Rückfall, ohne Rückfall und ohne Vorsortierung, ohne die Obergrenze, ohne die
  Vorsortierung. **Der Beweis der Beschleunigung ist die Messung, nicht ein Test** — ein
  Verhalten hat sich ja gerade nicht geändert; im Tor steht sie als Schranke von
  `test_the_layer_analysis_survives_a_knurled_surface`, die von zwölf auf acht Sekunden
  gezogen ist.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-127"></a>

- [x] **RM-127 — Wandstärke nach Änderungen am fertigen Modell prüfen.** Am 12.09.2026 gebaut.
  `check_thin_walls` (`scene/evaluate.py`) misst am **Endzustand**, neben `check_placement` und
  `check_bodies_in_one_place` und aus demselben Grund: Die Wand steht in keinem Merkmal, sie
  entsteht zwischen einer Bohrung und dem Mantel um sie herum (`relations.sleeve_at`) — und aus
  dem **letzten** Verhältnis. Wer Ø 19 in einen Zylinder Ø 20 bohrt, hat zwischendurch 0,5 mm
  Wand; vereinigt er danach einen Mantel Ø 30, sind es 5,5. Eine Prüfung je Schritt schriebe die
  Zwischenzahl auf, und die ist keine Aussage über das Teil, das dasteht.

  Damit fallen beide Hälften der Abnahme zusammen: Die am Ende behobene Zwischenwarnung entsteht
  gar nicht erst, und beide Reihenfolgen derselben zwei Änderungen tragen denselben Bericht — als
  Folge und nicht als zweite Zusage.

  **Die Grenze kommt aus dem Profil** (`Profile.minimum_wall_thickness`, zwei Extrusionsbreiten;
  Regel 7). Ohne Profil gibt es keine Aussage. Gemeldet wird je Körper einmal — die dünnste
  Stelle, denn ein Rohr im Rohr hat mehrere Wände und die innerste reißt zuerst —, mit beiden
  Merkmalen und dem Ort der Bohrung, damit der Klick im Prüfbericht irgendwohin führt (§2.7).
  Der Satz nennt die zwei Wege, die helfen, statt mit „zu dünn" zu enden.

  **Und sie darf nichts kosten, denn sie läuft nach jeder Auswertung.** Der erste Anlauf fragte
  `sleeve_at` je Merkmal; das liest Achse und Mitte jedes Kandidaten n-mal als Numpy-Array und
  wächst quadratisch. Gemessen: 25,8 ms bei 500 Bohrungen, 2087 ms im gebauten Extremfall aus
  500 Bohrungen und 500 koaxialen Zapfen. `relations.thinnest_sleeve` liest die Zahlen **einmal**
  je Körper und paart nur Hohlraum gegen Materie; die Regel selbst steht dabei weiterhin an
  genau einer Stelle (`_sleeve_between`), die beide Eingänge benutzen. Danach: **1,7 ms**,
  **0,2 ms** bei 234 Merkmalen, 476 ms im Extremfall — der oberhalb von
  `FEATURE_LIMIT_COUNT` ohnehin nicht entstehen kann und über den Korpus gemessen zwei
  Größenordnungen neben der Wirklichkeit liegt (höchstens 16 Merkmale je Netz).

  Nachweis: drei Fälle in `tests/test_prepare.py` — der gemeldete halbe Millimeter, die
  tragende Wand, die nicht gemeldet wird, und die drei gefahrenen Stapel für die beiden
  Reihenfolgen samt dem dünn gebliebenen als Beleg, dass überhaupt jemand hinsieht. Drei
  Gegenproben, jede einzeln rot: ohne den Aufruf in der Auswertung, ohne den Vergleich gegen
  die Profilgrenze und mit abgeschaltetem Befund. Der Umbau auf `thinnest_sleeve` ließ die
  397 Fälle aus `test_relations`, `test_slot_features`, `test_digest_and_fits`, `test_prepare`
  und `test_export` unverändert grün.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#neunzehn-kundendateien-durch-die-oberfläche-gefahren-04092026).

<a id="rm-128"></a>

- [~] **RM-128 — Bearbeitbarkeit erkannter Flächen entscheiden.** **Für die reine Fläche steht
  die begründete Anzeigegrenze** (nachgemessen 10.09.2026), samt der Faltung gleichlautender
  Absagen — am Besenhalter gemessen, statt fünfmal denselben Satz zu wiederholen —, und seit
  dem 10.09.2026 bietet ein Bausteinmerkmal seine eigenen Handlungen statt derer der Fläche
  darunter.

  **Offen bleiben zwei Dinge**: `fillet` trägt bis heute keine einzige Operation — kein
  Registereintrag nennt es in `applies_to` —, und die Merkmalsliste ist daran nicht
  ausgerichtet: Die Erkennung listet `face`, `fillet` und `edge_loop` unverändert. Ob eine
  erkannte Verrundung ohne Operation überhaupt in der Liste stehen soll, ist die Entscheidung,
  die der Punkt verlangt. Dazu die Abnahme an den Schiffsmodellen, für die es keinen Testfall
  gibt. Den separat geführten Verrundungsradius nicht doppelt planen.

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

<a id="rm-139"></a>

- [~] **RM-139 — Geometrische Orientierungskandidaten aus der konvexen Hülle ableiten.**
  **Der Satz „ist noch nicht eingelöst" stimmt seit einiger Zeit nicht mehr** (nachgemessen
  10.09.2026): `geom/orient.candidates()` baut die konvexe Hülle über sortierte Punkte, ordnet
  ihre Flächen nach Größe und nimmt die Normalen daraus; `slice/orientation.py` ruft sie als
  `face_candidates` und mischt sie mit der Ausgangsrichtung. `sample_directions` mit
  Zufallsgenerator gibt es noch als Funktion, sie steht aber nicht mehr im Kandidatenweg —
  `seed` ist dort ausdrücklich nur noch Kompatibilität.

  Offen bleibt damit **nur die Abnahme**, und die verlangt eine Messung: gleiche Eingaben ergeben gleiche Kandidaten und Lage; Vorfilter und Finalisten werden
  an mechanischen und organischen Körpern gegen die vollständige Kandidatenliste geprüft.
  Standfläche, Schwerpunkt und Haftung bleiben berücksichtigt; 200 betrachtete Kandidaten
  erfüllen das 20-Sekunden- und Abbruchziel. RM-078 misst einen anderen, konkreten Ladefall.

  [Bauplan-Abgleich und Nachweis](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026).

<a id="rm-140"></a>

- [x] **RM-140 — Exportbefunde vor dem Schreiben sichtbar machen.** Am 12.09.2026 gebaut, in
  zwei Hälften.

  **Die Prüfung war unvollständig.** §29 zählt fünf Fragen auf; zwei davon stellte
  `check_before_export` nie, und zwar aus demselben Grund: Sie stehen in keinem einzelnen Körper.
  Eine verletzte Passung steht zwischen zwei Merkmalen, eine Wand unter der Mindeststärke
  zwischen einer Bohrung und dem Mantel um sie herum — die Prüfung sah aber nur die **Auswahl**.
  Sie nimmt jetzt die Szene entgegen und fragt `scene.fits.check` und `check_thin_walls`
  (RM-127). Gefragt wird an der ganzen Szene, gemeldet über die Auswahl: Eine Passung, deren
  zweite Hälfte zu Hause bleibt, muss trotzdem aufgelöst werden, sonst käme „Merkmal verloren"
  zurück. Ohne Szene bleiben beide Fragen ungestellt (Regel 21) — die Kommandozeile und die
  Übergabe an den Slicer reichen sie deshalb ebenfalls durch.

  **Die Befunde kamen zu spät.** `_ExportWorker` prüfte und schrieb in einem Zug, mit einer
  Begründung, die stimmte und die falsche Folgerung zog: Die Prüfung ist der lange Teil und
  gehört nicht in den Hauptthread — daraus folgt nicht, dass sie mit dem Schreiben zusammen
  laufen muss. Sein erster Lauf hört jetzt an der Prüfung auf, sobald etwas ab `warning`
  dasteht; der Prüfbericht bekommt die Befunde und rückt nach vorn, `dialogs.confirm_export`
  fragt, und ein Ja startet einen zweiten Lauf mit **demselben** Bericht statt einer zweiten
  Prüfung. Weitergehen ist die Vorgabe — §29 sagt „Bericht, nicht Blockade" —, und ohne Befund
  wird gar nicht gefragt: Ein Dialog, der „alles in Ordnung" sagt, ist ein Klick ohne Auskunft.

  `export → scene` ist damit eine neue, **träge** Importkante und steht so in
  `tests/test_core_package_direction.py` (jetzt 47 eifrige und 14 träge).

  Nachweis: fünf Fälle in `tests/test_export.py` — dünne Wand und verletzte Passung vor der
  Datei, keine erfundene Aussage ohne Szene, die Passung eines nicht exportierten Körpers bleibt
  draußen, und ein übergebener Bericht wird nicht zweimal erhoben — dazu zwei in
  `tests/test_ui.py`: Der Export fragt und schreibt beim Abbrechen nichts, ein sauberer fragt
  nicht. Vier Gegenproben, jede einzeln rot: ohne die zwei neuen Prüfungen, ohne den Filter auf
  die Auswahl, ohne den `checked`-Zweig und ohne die Frage im Arbeiter.

  [Bauplan-Abgleich und Nachweis](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026).

<a id="rm-143"></a>

- [x] **RM-143 — Selbstdurchdringungen in der Netzfehlerkarte sichtbar markieren.** Am
  12.09.2026 gebaut. Bauplan §18.4 verspricht Durchdringungen; die Karte markierte offene und
  verzweigte Kanten und fand keine — beides steht in der **Kantentabelle**, eine
  Durchdringung ist dagegen **räumlich**: Zwei Wände, die einander schneiden, haben lauter
  saubere Kanten mit je zwei Flächen, und die Tabelle sagt dazu nichts.

  `repair.self_intersecting_faces` beantwortet die Frage in zwei Stufen — Sweep-and-Prune über
  x, dann Segment gegen Dreieck (Möller-Trumbore) für beide Partner. Nachbarn zählen nicht,
  und verglichen wird über die **Eckpunkte** statt über die Indizes: Ein eingelesenes STL
  trägt dieselbe Ecke oft mehrfach.

  **Die erste Fassung war zu langsam, und das Budget hat es gesagt**: 5,3 s an einer Kugel mit
  20 480 Dreiecken, wo §18.4 drei nennt. Die Paarbildung läuft jetzt vektorisiert —
  `searchsorted` liefert je Dreieck den zusammenhängenden Bereich seiner Partner, blockweise,
  damit die Indexfelder den Speicher nicht sprengen. Gemessen: **474 ms** an derselben Kugel,
  elfmal schneller. Dazu das Abbruchtoken zwischen den Blöcken und ein harter Deckel an der
  Paarzahl.

  Nachweis: `broken_selfint.stl` aus dem Korpus (zwei Quader, die durcheinanderlaufen) markiert
  8 von 24 Dreiecken, ein Würfel keines; die Stufe heißt „Durchdringung" und steht als Wort in
  der Legende (Regel 18), in allen fünf Sprachen. Gegenprobe ohne die Suche rot.

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

  **Offen bleibt der Zeiger:** Über einer Kante zeigt er weiter die Merkmalsform, weil
  `_would_pick_feature` nur nach dem Merkmal fragt. Ein Zeiger, der etwas anderes verspricht
  als der Klick tut, ist genau die Lücke, die `.claude/rules/ansicht.md` an dieser Stelle
  benennt. Ebenso offen: der **Rechtsklick** auf eine Kante — das Kontextmenü meint dort
  weiter das Merkmal darunter.

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

<a id="rm-148"></a>

- [x] **RM-148 — Zahlenparameter gegen NaN und Unendlich sichern.** **Erledigt, und zwar schon
  am 09.09.2026** — der Punkt stand einen Tag zu lange offen. Commit `5a2802ac` („Ein
  Grenzvergleich mit NaN sagt zweimal Nein, und der Wert läuft durch") fasst genau die zwei
  Dateien an, die die Abnahme verlangt.

  `math.isfinite` steht in `registry/params.py:314` — im `NUMBER_KINDS`-Zweig, **vor** der
  Ganzzahlfrage, weil `float("nan").is_integer()` sonst „hier wird eine ganze Zahl erwartet"
  ergäbe: wahr und irreführend. `NUMBER_KINDS` deckt `float`, `int` und `filament`; die
  Ablehnung trägt `constraint="not_finite"` und den Satz „Der Wert ist keine endliche Zahl.
  Tragen Sie eine Zahl ein." (Regel 17). Der Regressionstest steht in
  `tests/test_params.py:118` über `nan`, `inf` und `-inf`, dazu die Gegenprobe
  `test_the_bounds_alone_would_let_a_nan_through` — ohne sie wäre der Test auch dann grün,
  wenn die Grenzen den Fall fingen — und `int(inf)` als eigener Überlauffall.

  Nachgemessen am 10.09.2026 am Code und am Testlauf.

<a id="rm-150"></a>

- [x] **RM-150 — Langlöcher als Merkmal erkennen.** Am 10.09.2026 gebaut: `app/core/perceive/slots.py`
  setzt ein Langloch aus den zwei Zylinderausschnitten zusammen, die die Einpassung als Verrundungen
  ausweist. Entschieden wurde **gegen** die Provenienz und für die Geometrie — der häufigste Fall
  ist ein eingelesenes Netz, in das jemand anders eine Nut geschnitten hat, und dort gibt es keinen
  erzeugenden Schritt. Getragen wird die Unterscheidung topologisch: Beide Bögen hängen über einen
  Mantel quer zur Achse zusammen, und alles darin ist entweder einer der Bögen oder eine ebene
  Flanke im Abstand eines Radius von der Mittellinie. Die Merkmalsart `slot` trägt Breite, Länge,
  Mittellinienweg, Achse, Richtung, Tiefe und Durchgang; Objektbaum, Steckbrief und
  Merkmalspanel lesen sie, und `slot_hole` gilt jetzt auch an ihr (Titel dafür auf *Zum Langloch
  ziehen* geändert — „Bohrung zum Langloch" stimmte an einem Langloch nicht mehr).
  Nachweis: `tests/test_slot_features.py`, 17 Fälle, davon zwölf ohne die Erkennung rot.
  **Nicht `test_slots.py`** — die gibt es auch, und sie behandelt etwas völlig anderes:
  Material-Slots nach §20/§29. Im Deutschen heißt beides „Slot"; die neue Datei sagt das in
  ihrem eigenen Kopf, damit niemand die falsche fährt. Die tragende
  Gegenprobe ist eine Tasche mit vier verrundeten Ecken — gleiche Radien, parallele Achsen,
  verbundener Mantel und trotzdem kein Langloch. Ein eingelesenes Modell wird an einer Nut aus
  Quader und zwei Zylindern geprüft, nicht am eigenen Erzeuger.

  **Der exakte Kern ist am 11.09.2026 nachgezogen.** Er beschreibt jede Topologiefläche für
  sich, und ein Langloch hat vier: Im Objektbaum standen `fillet_1` und `fillet_2`, wo eine
  Öffnung ist, und die Handlungen eines Langlochs standen an keiner von beiden (Robert: „auf
  einem langloch 2 werden und nicht mehr wählbar"). `brep.features._slots_instead_of_half_bores`
  fragt dieselbe Sache an der Topologie: zwei angeschnittene Zylinderflächen, gleicher Radius,
  parallele Achse, beide ins Loch gewölbt, mit **genau zwei** gemeinsamen ebenen Nachbarn, die
  ihrerseits an **beide** Bögen grenzen. Nachweis: sieben Fälle in `tests/test_brep.py`, davon
  sieben ohne den Nachschritt rot; die Gegenproben — verrundete Tasche, rundum verrundeter
  Quader — bleiben in beiden Läufen grün.

<a id="rm-151"></a>

- [x] **RM-151 — Das Freiform-Urteil nennt konstruierte Teile einen Scan.** Am 12.09.2026
  behoben. Der Befund `perceive.freeform` sagte „Dieses Modell ist eine Freiform, etwa ein
  Scan" — und das liest ein Kunde als Aussage über sein Teil, nicht über eine Zählung.
  Roberts `garden-hose-holder.3mf` ist ein konstruierter Halter, dessen geschwungener Bogen
  ihn mit 0,701 gegen die Schwelle 0,700 dorthin brachte.

  Er nennt jetzt, **was gemessen wurde**: „Die Oberfläche dieses Modells ist überwiegend
  gekrümmt. Kugeln, Ringe, Kegel und Verrundungen … sind an einer solchen Fläche keine
  Merkmale und wurden weggelassen; Bohrungen, Zapfen und ebene Flächen bleiben." Die Zahl
  bleibt darin (Regel 17), die Entscheidung darunter unverändert.

  **Ein zweiter Zustand kommt nicht** — die vorab zu treffende Entscheidung. „Überwiegend
  rund" neben „Freiform" kostete eine zweite Schwelle, und die Lücke zwischen Nozzle-Box
  (59 Prozent) und Retro-Maus (77 Prozent) ist schmal; zwei Sätze, deren Grenze niemand
  nachmisst, sind schlechter als einer, der wahr ist. Der Grund steht am Befund selbst.

  Der Katalogschlüssel ist in allen fünf Sprachen getauscht, der alte hinaus. Nachweis: die
  Zusicherung in `tests/test_evaluation.py` (kein „Scan" im Satz, „gekrümmt" darin), Gegenprobe
  mit dem alten Wortlaut rot.

<a id="rm-152"></a>

- [x] **RM-152 — Die Wandstärke um ein Langloch messen.** Am 12.09.2026 gebaut. `Sleeve`
  führt den Weg der Mittellinie mit (`bore_travel`), und `thickness` zieht seine Hälfte ab:
  Die Enden eines Langlochs sitzen um `travel / 2` aus der Mitte, und dort ist die Wand am
  dünnsten. Am Zapfen Ø 20 mit einem Langloch Ø 8 auf 14 mm — den Zahlen, an denen der Punkt
  entstand — kommen **2,9996 mm** heraus statt der 6,0, die der halbe Durchmesserunterschied
  ergab.

  **Der Weg gehört der Höhlung**, nicht dem gefragten Merkmal: Von außen geklickt ist das
  Langloch der Kandidat, und eine Bohrung trägt gar keinen. Und wo daraus keine positive Wand
  mehr wird, ist es kein Rohr, sondern eine offene Flanke — bei der runden Bohrung fängt das
  der Durchmesservergleich ab, beim Langloch erst die fertige Zahl.

  `slot` stand in `is_a_cavity` bereits seit RM-153; der Kommentarblock darunter, der das
  Gegenteil behauptete, ist gefallen. Nachweis: zwei Fälle in `tests/test_relations.py`
  (Gegenprobe ohne die Wegkorrektur rot) und der Steckbriefsatz in
  `tests/test_slot_features.py` — der Test, der dort das Schweigen festschrieb, ist von der
  Zusage abgelöst, die an seine Stelle tritt.

<a id="rm-153"></a>

- [x] **RM-153 — Ein Langloch versetzen, drehen und verdoppeln.** Seit dem 10.09.2026 trägt ein
  erkanntes Langloch im Merkmalsfenster eine Zeile mit seinen zwei Maßen und im Bild zwei Knöpfe,
  an denen sich Länge und Richtung ziehen lassen. Was ihm fehlt, sind die vier übrigen Handlungen:
  `move_feature`, `rotate_feature`, `duplicate_feature` und `remove_feature` führen `slot` nicht in
  `applies_to`. Der frühere Grund im Werkzeugkörper ist im Review vom 11.09.2026 behoben:
  `_feature_solid` bildet jetzt den vollständigen Langlochumriss ab. Die Freigabe und
  Abnahme der vier allgemeinen Merkmalshandlungen stehen weiterhin aus. Der
  Kunde sieht damit fünf ausgegraute Zeilen neben einer, die geht (Robert, 10.09.2026: „das gleiche
  wäre zum bearbeiten dann von langlöchern und anderen operationen/merkmalen usw gut"). Was es
  braucht, ist derselbe Werkzeugkörper, den `slot_bore` schon baut — aus Mitte, Achse, Durchmesser,
  Länge und Richtung —, dazu die Frage, was *Verdoppeln* an einem Langloch versetzt (die Kopie
  braucht dieselbe Richtung, nicht nur dieselbe Mitte). Abnahme: Ein Langloch lässt sich im Bild
  versetzen und drehen, das Volumen des Ganzen bleibt dabei gleich, und die vier Zeilen im Panel
  tragen ihre Werte statt eines Grundes. **Und dann fällt auch der Griff zusammen:**
  `viewport.slot_handle_feature` gibt es getrennt von `gizmo_feature`, weil die zwei Mengen heute
  auseinanderliegen — mit dieser Arbeit dürfen sie es wieder gemeinsam tun.

  **Das Versetzen selbst ist seit dem 11.09.2026 draußen**, und zwar über einen anderen Weg als
  hier beschrieben: `slot_hole` und `resize_hole` nehmen eine Stelle entgegen (`x/y/z`) und
  schließen dabei die alte — am Netz über `_closed_at`, am exakten Körper über
  `brep.edit.fill_bore`. Beide Kerne können es damit gleich gut. Was offen bleibt, sind die
  **vier Handlungen** oben: `move_feature`, `rotate_feature`, `duplicate_feature` und
  `remove_feature` führen `slot` weiterhin nicht in `applies_to`, und ihr Werkzeugkörper ist
  weiter ein Zylinder.

  **Abgeschlossen am Abend des 11.09.2026 — und die Ursache war keine Geometrie.** Der
  Werkzeugkörper stand seit dem Morgen (`PARAMETRIC_KINDS`); was fehlte, war eine Antwort:
  `types.is_a_cavity` kannte das Langloch nicht und hielt es für Materie. *Merkmal verschieben*
  trug damit an der alten Stelle ab statt zu füllen und setzte an der neuen an statt zu
  schneiden — in Luft und in vollem Material, das Volumen blieb gleich, das Merkmal wanderte im
  Baum an eine Stelle ohne Loch. Mit `slot` als Hohlraum gehen Versetzen, Verdoppeln und
  Entfernen an beiden Kernen; *Drehen* brauchte dazu die mitgedrehte Mittellinie
  (`_with_turned_direction`, geschlossen mit der alten, gesetzt mit der neuen — sonst ein
  Kreuz). Die Absage in `NOT_APPLICABLE` ist gefallen, `sleeve_at` schützt sich seitdem selbst
  (RM-152 bleibt). Nachweis: `test_a_slot_takes_the_four_generic_actions`, alle vier am
  Ergebnis gemessen; ohne den Hohlraum-Eintrag rot. **Und der Griff ist damit gemeinsam**: Das
  Langloch steht in `movable_feature_kinds()`, Pfeile und Ringe hängen daran wie an einer
  Bohrung — beide seit demselben Abend erst mit *Im Bild einstellen* (Entscheidung Robert). Was
  bleibt, ist die **Breite**: RM-156.

<a id="rm-156"></a>

- [x] **RM-156 — Die Breite eines Langlochs ändern.** Am 12.09.2026 gebaut: *Bohrung ändern*
  nimmt das Langloch an (`applies_to=["hole", "slot"]`), und der Durchmesser ist dort seine
  **Breite**. Die Länge folgt aus dem gemessenen **Weg** plus der neuen Breite — Ø 6 auf 20
  wird zu Ø 8 auf 22, genau die Abnahme. Gerechnet wird über den Weg und nicht über die
  Länge: Er ist der Grund, aus dem es Langlöcher gibt, und wer ihn beim Verbreitern verlöre,
  bekäme ein anderes Bauteil.

  **Gefüllt wird immer, auch ohne Versatz.** Beim Verbreitern deckt der neue Umriss den alten
  mit ab; beim Verschmälern bliebe ohne das Füllen die alte Breite stehen, und das Maß im
  Objektbaum wäre eine Behauptung über Material, das nicht mehr da ist. Die Zugabe entfällt
  dabei — sie hält den Werkzeugkörper von der alten Bohrungswand fern, und die ist eben
  zugegangen.

  An **beiden Kernen** derselbe Weg: am Netz `_closed_at` + `prepare.slot_bore`, am exakten
  Körper `edit.fill_bore` + `edit.slot_bore`. Die Rückzuordnung brauchte nichts Eigenes; die
  Kennung bleibt in beiden Fällen. Die zwei Zeilen in `NOT_APPLICABLE_HERE`, die das als „noch
  nicht gebaut" auswiesen, sind gefallen; `resize_feature` behält seine — es gilt Materie, und
  ein Langloch ist ein Hohlraum.

  Nachweis: zwei Fälle in `tests/test_slot_features.py` (breiter mit erhaltenem Weg, schmaler
  mit mehr Material), einer in `tests/test_brep.py` und einer über `reason_against`. Gegenprobe
  gefahren: alle vier rot ohne den Eintrag in `applies_to`.

<a id="rm-154"></a>

- [x] **RM-154 — „Nicht gesagt" von „null gemeint" unterscheiden.** Der Winkelfall war am
  11.09.2026 behoben; der Rest am 12.09.2026. `ParamSpec.optional` erlaubt einer Zahl den
  Wert `None`, und `x/y/z` von `slot_hole` und `resize_hole` tragen ihn. Damit lässt sich ein
  Loch in die **Teilemitte** schieben — vorher der einzige Ort, den es nicht erreichte, und
  ausgerechnet der häufigste, weil Solidon seine Grundkörper um den Ursprung legt.

  Vier Stellen lösen es ein: `params._coerce` lässt `None` als Erstes durch (ein `None` hat
  weder Art noch Grenzen), `json_schema` nimmt `"null"` in die Typliste, der Dialog setzt den
  leeren Zustand einen Schritt unter den Mindestwert mit `setSpecialValueText`, und
  `prepare_ops._named_place` beantwortet die Frage einmal für beide Operationen. Ohne die
  dritte schöbe ein bloßes Bestätigen im Dialog jedes Loch in den Ursprung — das Drehfeld hat
  immer eine Zahl.

  **Wo die Null physisch unmöglich ist, braucht es das nicht** — eine Länge, ein Durchmesser,
  eine Anzahl. Dort ist die Null schon eindeutig „nicht gesagt", und ein zweiter Mechanismus
  daneben liefe mit dem ersten auseinander. Die Regel steht in `.claude/rules/operationen.md`
  unter „Eine Zahl, die nicht gesagt wurde".

  Nachweis: zwei Fälle in `tests/test_brep.py` (Loch in die Mitte, und die Gegenrichtung: wer
  nichts sagt, versetzt nichts) und zwei in `tests/test_operation_ui.py` (das Feld startet
  leer; eine getippte Null meint die Null). Gegenproben gefahren, alle vier rot ohne den Fix.

<a id="rm-155"></a>

- [x] **RM-155 — Ein knapp aufgezogenes Langloch in einem fremden Netz.** Gemessen am
  11.09.2026 über Ø 2 bis Ø 40 in beiden Qualitätsstufen: Liegt der Weg zwischen den
  Bogenmitten unter rund **fünf Prozent** des Durchmessers, passt die Einpassung einen
  Zylinder auf den Mantel und das Merkmal heißt **Bohrung**; in einem schmalen Streifen
  darüber passt weder Zylinder noch Bogenpaar, und dann steht **gar kein** Merkmal da —
  Ø 12 mit der Länge 12,5 ergab null Merkmale, Ø 20 mit 20,5 ebenso. Für die eigenen
  Operationen ist der Streifen seit demselben Tag unerreichbar (`prepare.shortest_slot`
  verlangt das Doppelte des gemessenen Abstands, und der Griff im Bild rastet dort). Ein
  **eingelesenes** Modell kommt trotzdem dorthin: Wer ein STL mit einem so knappen Langloch
  öffnet, findet an dieser Stelle nichts zum Anklicken. Der Fall ist selten — ein Langloch
  mit einem halben Millimeter Weg hat keine Funktion —, aber er ist echt, und er ist der
  einzige Rest des Fehlerbildes vom 11.09.2026. Was es bräuchte, ist ein Auffangweg in der
  Einpassung: ein geschlossener gekrümmter Fleck, dessen Querschnitt ein Stadion ist, statt
  des Umwegs über zwei eingepasste Verrundungen. Abnahme: Eine Platte mit einem Langloch
  Ø 12 auf 12,5 mm öffnet, und im Objektbaum steht ein Langloch.

  **Am 11.09.2026 gebaut**, genau so: `perceive.features.fit_stadium` passt einen
  unklassifizierten Fleck als Prisma über einem Stadion ein — nach Zylinder und
  Krümmungssplit, als dritte Runde —, und `slots.slots_from_stadiums` macht daraus dasselbe
  Merkmal wie aus zwei Bögen. Gemessen über Ø 5 bis Ø 40: Der Streifen ist zu, ab dem Weg, an
  dem der Zylinder nicht mehr passt, steht ein Langloch; darunter bleibt es eine Bohrung, und
  das ist auf ein bis zwei Prozent des Durchmessers auch eine. Die Mittellinie kommt aus der
  Richtung der größten Ausdehnung — die Hauptachse der Punktwolke zeigte bei Ø 40 mit 0,8 mm
  Weg quer. Gegenproben: Sechs- und Achteck-Prisma, gestrecktes Sechseck, Tasche 12 × 8 mit
  r = 3 — keines wird ein Langloch; an fünf Korpus- und Kundenmodellen kein verändertes
  Merkmal, zehn bis zwanzig Prozent mehr Erkennungszeit. Nachweis: fünf Fälle in
  `tests/test_slot_features.py`, vier davon ohne den Auffangweg rot.

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

## Bedienung und Darstellung
<a id="rm-158"></a>

- [x] **RM-158 — Plattenwähler überlappt den Druckernamen in der Kopfzeile.** Auf Roberts
  Bildschirmfoto vom 11.09.2026 stand „Alle Platten" über „Elegoo Centauri Carbon 2", beide an
  derselben x-Stelle. Nachgestellt am 11.09.2026 über den **Startweg der Anwendung** — nicht über
  Skalierung oder Schrift, sondern über die Reihenfolge: Das Fenster wird 1280 breit gebaut
  (Kopfzeile kompakt), bekommt dann seine gespeicherte Breite (breit, Wähler versteckt) und zeigt
  den Wähler erst mit den Platten des Projekts. Die Spaltendehnung stand nur, wenn der Wähler beim
  Anordnen sichtbar war, und ein `QGridLayout` gibt einer ungedehnten Spalte mit einem
  `Ignored`-Widget null Breite, Mindestmaß hin oder her. `HeaderBar._stretch_the_plate_column`
  bindet die Dehnung an die Sichtbarkeit; `_arrange` sperrt den Wiedereintritt aus dem eigenen
  `activate()`. Abgenommen am echten Fenster über `build_application` mit Roberts Geometrie und
  vier Platten (Bildschirmaufnahme: Wähler, Trennstrich, Drucker nebeneinander); Test
  `test_the_plate_filter_never_lies_over_the_printer`, Gegenprobe rot.

<a id="rm-157"></a>

- [x] **RM-157 — Ein Ort für die Handlungen an einer Auswahl.** Am 11.09.2026 auf Roberts
  Durchsicht hin umgebaut: Die Menüs *Objekt*, *Ändern* und *Vorbereiten* sind aus der Leiste
  genommen — ihre Einträge standen rechts in der Karte der Handlungen ein zweites Mal
  (`PANEL_CATEGORIES`, `in_the_menu_bar`); *Bausteine* ist ein Abschnitt von *Erzeugen* mit
  Katalog, Gegenstücken und den zwei Deckeln ohne Kachel, die jetzt auch rechts an der Fläche
  stehen. Die Aktionen bleiben am Fenster (Kürzel, Palette, Kürzelübersicht unter „Handlungen
  rechts"), nackte Tasten nur an Baum und Ansicht. Das Kontextmenü an Körper und Merkmal trägt
  keine Operationen mehr — nur Schritt, Skizze und Sichtbarkeit. Die Karte rechts faltet ihre
  Gruppen als einklappbare Abschnitte, der Knopf *Bausteine* ist ein Hauptknopf. Der Wegweiser
  des Chats sagt „Ort:" und nennt für eine Handlung rechts die Karte samt der Auswahl, die es
  braucht (Prompt-Version 6); Handbuch und Tour nennen dieselben Orte. **Dazu die Bausteine im
  Bild:** Ein Baustein aus dem Katalog sitzt sofort auf der gewählten oder der obersten Fläche,
  mit Körper, Maßlinien, Feldern und Bewegungsgriff; ein Klick setzt um, der zweite übernimmt
  (gemessen an allen 24 einsetzbaren; vorher stand mit gewähltem Körper nichts im Bild, und
  *Übernehmen* schrieb einen roten Schritt). Regeln: `.claude/rules/oberflaeche.md`,
  `.claude/rules/ansicht.md`.

<a id="rm-070"></a>

- [~] **RM-070 — SpaceMouse auf macOS und Linux am echten Gerät abnehmen.** HID-Anbindung und
  Kameraabbildung sind gebaut und von Robert mit SpaceMouse Compact gefahren; macOS nutzt inzwischen
  den 3Dconnexion-Treiber.

  **Der Mac ist gefahren** (Robert, 12.09.2026: „die spacemaus und update auf dem mac funktionieren
  jetzt problemlos"). Das ist ein Feldnachweis und kein Testlauf — er zählt für die Plattform, auf
  der er stattfand, und für nichts sonst.

  Offen bleiben damit: **Linux** (Rechte und Gerätetest), das Verhalten bei paralleler
  3DxWare-Mausemulation und die Bildrate an einem Netz mit 1 Mio. Dreiecken. Abnahme je Plattform
  mit benanntem Gerät, Treiber und reproduzierbarer Navigation; eine automatische Änderung der
  Treiberkonfiguration vorher entscheiden.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#eine-kundenanfrage-aus-dem-dentalbereich-30082026).

<a id="rm-074"></a>

- [ ] **RM-074 — Verbleibenden Bildnachweis der Viewport-Serie abschließen.** Die noch fehlende
  Live-Abnahme des Befundsprungs an einem echten Warnprojekt nachholen: Klick im Prüfbericht muss
  zum betroffenen Ort führen und dort eine sichtbare Marke zeigen. Die neun V-Pakete sind umgesetzt.
  Abnahme: reproduzierbarer Klickweg und Bildbeleg mit dem aktuellen Renderer.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-zeichenmodus-und-der-viewport-bekommen-ihre-durchsicht-30082026).

<a id="rm-079"></a>

- [ ] **RM-079 — Zeilenlängen der Website über alle Sprachen prüfen.** Die Textbreiten der Website
  als gemeinsame Regel überprüfen und verbleibende überlange Absätze begrenzen. Abnahme:
  tatsächliche Zeilenlängen in allen sechs Sprachen bei schmalen und breiten Fenstern; Karten und
  Spalten dürfen nicht durch eine pauschale Regel unnötig schmal werden.

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

<a id="rm-101"></a>

- [x] **RM-101 — Elternloser Handlungsknopf im Fensteraufbau.** Am 12.09.2026 reproduziert und
  behoben. **Die Beobachtung war echt, und der Verdacht zeigte in die richtige Richtung — nur
  eine Zeile daneben.** Am Code widerlegt war „elternlos **konstruiert**" (10.09.2026, und das
  stimmt weiter: `_show_offers` baut jeden Knopf mit `self._offers` als Elternteil). Gefunden
  wurde „elternlos **gemacht**": Beim Wegräumen der alten Knöpfe stand dort
  `widget.setParent(None)`, und Qt kennt keinen elternlosen Zustand — ein Widget ohne
  Elternteil **ist** ein Top-Level-Fenster.

  Gemessen am Fenster mit einem echten Befund (zwei Körper übereinander,
  `arrange.below_bed`): **vier** Knöpfe „Auf das Bett setzen" als eigene Fenster nach einem
  Befundwechsel, **zwei davon sichtbar** — bis `deleteLater` die nächste Runde der
  Ereignisschleife erreicht. Genau das hatte jemand gesehen.

  Weggeräumt wird jetzt mit `hide()` und `deleteLater()`: `takeAt` nimmt das Widget aus dem
  Layout, `hide` aus dem Bild, und der Elternteil trägt es bis zum Löschen. Dieselbe Stelle
  gab es ein zweites Mal in `FeaturePanel.clear`.

  **Das Wissen stand schon zweimal im Code und einmal nicht**: `MainWindow._close_sketch` nennt
  den Absturz, `SketchEditor.take_side_box` die falsch aufgelösten Tastenkürzel — und der
  Prüfbericht tat es trotzdem. Ein Kommentar an zwei Stellen ist keine Regel; sie steht jetzt
  in `.claude/rules/oberflaeche.md`.

  Nachweis: `test_no_second_window_appears_along_the_way` in `tests/test_ui.py` geht den ganzen
  Weg — aufbauen, zeigen, zwei Modelle öffnen, einen Befund mit Handlung erzeugen, die fünf
  Werkzeuge auf und zu, ein Merkmal wählen und abwählen — und zählt den **Zuwachs** an
  Top-Level-Fenstern; das Hauptfenster behält dabei den Fokus. Er war vor dem Fix rot, und
  beide Gegenproben (Prüfbericht, Merkmalleiste) sind es einzeln ebenfalls.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-102"></a>

- [x] **RM-102 — Datum im Wiederherstellungsdialog an die App-Sprache binden.** Erledigt am
  10.09.2026. `MainWindow._when` gab den Rückfall über 24 Stunden als festes
  `%d.%m.%Y %H:%M` aus — deutsche Reihenfolge in jedem Fenster, direkt neben den relativen
  Angaben („vor einer Stunde"), die seit je über `tr()` mitwanderten. `labels.local_moment`
  ist die Schwester zu `local_timestamp` für einen `datetime` und bindet das Datum an
  `get_language()`.

  **Ein Detail, das der Test gefunden hat und nicht das Lesen:** `ShortFormat` kürzt das Jahr
  je nach Sprache auf zwei Ziffern — „05.03.26". Der Kunde hätte die Sprachbindung bekommen
  und dafür zwei Ziffern verloren, ausgerechnet bei einer Sicherung, deren Alter die ganze
  Entscheidung trägt. Geändert wird deshalb nur `yy` → `yyyy` im Muster; Reihenfolge, Trenner
  und Uhrzeitform bleiben Sache der Sprache — dieselbe Bauart wie in `calendar_date`, die den
  Wochentag herausnimmt.

  Nachweis: `tests/test_ui.py::test_the_age_of_a_backup_follows_the_application_language` prüft
  die **Sprachbindung** und keinen Wortlaut — zwei Sprachen müssen zwei Schreibweisen ergeben;
  ein Vergleich gegen eine erwartete Zeichenkette prüfte nur, was QLocale in dieser Qt-Fassung
  gerade tut. Gegenprobe gefahren: mit dem festen Muster schreiben beide Sprachen
  „05.03.2026 14:30", und der Test sagt genau das.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#architektur-durchsicht-02092026).

<a id="rm-108"></a>

- [ ] **RM-108 — Abbauzeit des Schlüsseldialogs messen und begrenzen.** Das Schließen des
  Schlüsseldialogs während einer Modellabfrage ohne blockierende Wartefrist ermöglichen. Abnahme:
  Schließen reagiert sofort, ausstehende Antwort wird sicher verworfen, Arbeiter lebt kontrolliert
  bis zum Ende und Prozessabschluss bleibt sauber.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-119"></a>

- [x] **RM-119 — Schnittebene bei mehreren Druckplatten richtig darstellen.** Am 12.09.2026 am
  Bild gemessen — und das Ergebnis ist ein anderes als der Code-Befund vom 04.09.2026 vermuten
  ließ. Aufbau: zwei Bretter 200 auf 200, `arrange_bed` mit zwei Platten, Versatz 260 mm nach +X.

  **Der Schnitt selbst ist richtig, und zwar als Entscheidung.** Eine Ebene bei x = 0 schneidet
  beide Bretter in ihrer Mitte; im Bild stehen danach zwei aufgeschnittene Teile nebeneinander.
  Genau das ist die Frage, für die ein Schnitt da ist — Wandstärke, Innenraum. Eine **Bild**ebene
  wäre die schlechtere Antwort: Sie träfe immer nur eine Platte, und der Schieberweg müsste mit
  jeder weiteren um eine Bettbreite wachsen. Er kommt aus den Körpergrenzen (`section_ranges`),
  also aus der Szene — Schnitt und Bedienung stimmen damit überein, und wer das eine ändert,
  ändert beides. Ein Test nagelt die Entscheidung fest; die Gegenprobe mit der Ebene im Bild ist
  rot.

  **Falsch lag die Marke daneben.** Die Schichtkonturen (§18.10) wurden in Szenenkoordinaten
  gezeichnet, ohne den Ansichtsversatz: Das Brett auf Platte 2 steht im Bild bei x 160 bis 360,
  seine Konturen lagen bei -100 bis 100 — quer über dem **anderen** Teil. Derselbe Fehler, den
  der Kommentar an `_redraw_measurements` für die Maße als behoben beschreibt; die Rechnung war
  gepflegt, die Liste derer, die sie benutzen, nicht. `Viewport.set_layer` nimmt jetzt den
  Körper entgegen, dem die Schicht gehört, und `_layer_shift` gibt ihren Konturen denselben
  Versatz wie Maßen, Merkmalsflächen und Fangmarke. Beim Blick auf eine einzelne Platte ist er
  null, und die Konturen stehen wieder am Szenenort.

  Nachweis: drei Fälle in `tests/test_ui.py`, drei Gegenproben einzeln rot (ohne den Versatz an
  den Konturen, mit festem Plattenversatz, mit der Ebene im Bild statt in der Szene).

  [Bisheriger Befund](ROADMAP-ARCHIV.md#viewport-werkzeuge-aus-kundensicht-03092026).

<a id="rm-124"></a>

- [x] **RM-124 — Zusätzlichen Render durch show_build_volume messen.** Am 12.09.2026 gemessen
  und behoben. **Die Messung bestätigt den Aufwand**, am eigenen Renderer ohne Fenster:

  | Kulisse | vorher | nachher |
  |---|---|---|
  | ein Bett | 19,2 ms | **2,1 ms** |
  | vier Betten | 71,3 ms | **2,5 ms** |

  Das Fenster ruft `show_build_volume` bei **jeder** Auswertung — es weiß nicht, ob sich am
  Bauraum etwas geändert hat, und die Ansicht wusste es auch nicht: Vier Aktoren je Platte
  flogen weg und kamen identisch wieder, im Qt-Hauptthread. Die verbliebenen zwei Millisekunden
  sind das Anfordern des Bildes und nicht der Aufbau.

  `_bed_built` merkt sich, woraus die stehende Kulisse gebaut wurde: Renderer, Bauraum,
  Plattenzahl und die beiden Bettfarben. Jedes davon hat seinen Grund — der **Renderer**, weil
  ein Austausch dieselben Aktoren woanders braucht; die **Farben**, weil ein Themenwechsel sonst
  ein fast schwarzes Bett auf hellem Grund stehen ließe. Was an vorhandenen Aktoren hängt, wird
  weiterhin bei jedem Aufruf gesetzt: Bettsichtbarkeit und Zeichenebene über das neue
  `_apply_bed_visibility`, die Deckkraft über `_apply_bed_transparency`. Vorher galt dort die
  Reihenfolge „frisch gebaut, dann ausblenden"; die gibt es nicht mehr.

  Nachweis: drei Fälle in `tests/test_plates.py`, drei Gegenproben einzeln rot (ohne den
  Wächter, ohne die Farben im Zustand, ohne den Renderer im Zustand). **Die vierte ist grün
  geblieben und steht deshalb hier**: Mit der alten, nur ausblendenden Sichtbarkeitsregel läuft
  der dritte Test durch, weil `set_bed_visible` und das Ende des Zeichenmodus die Sichtbarkeit
  selbst wiederherstellen — ein Ablauf, in dem die alte Regel falsch liegt, ließ sich nicht
  konstruieren. Die Zusammenführung bleibt trotzdem, weil eine Stelle für eine Regel besser ist
  als zwei; als Nachweis wird sie nicht ausgegeben.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-eine-aufräum-durchsicht-offenließ-04092026).

<a id="rm-130"></a>

- [x] **RM-130 — Speicherhinweis nach reinem Import verständlich gestalten.** Am 12.09.2026
  entschieden und gebaut. **Die Entscheidung ist Regel 19, andersherum gelesen**: Sie verbietet
  die Nachfrage vor rücknehmbaren Handlungen, und ein eingelesenes Modell ist genau das — die
  Datei liegt weiter auf der Platte. Wer eine STL öffnet, dreht und schließt, wird deshalb nicht
  mehr gefragt. Was gefragt wird, ist nicht der Aufwand, sondern die **Reproduzierbarkeit**: Ein
  63-MB-Container kostet vierzehn Sekunden, aber er kostet sie ein zweites Mal genauso; was er
  nicht kostet, ist eine Entscheidung, die jemand noch einmal treffen müsste.

  `ingest.plan.is_only_imported` zählt deshalb alles mit, was eine solche Entscheidung
  festhält: jede Operation außer `load` und `load_step` (`load_outline` gehört ausdrücklich
  nicht dazu — eine Zeichnung auf eine Höhe zu ziehen ist Konstruktion), jede Quelle, die nicht
  aus einem Import stammt, Parameter, Passungen, Gesprächsbeiträge, Druckeinstellungen und jede
  Transaktion mit `changes` — Drucker- und Materialwechsel stehen nicht im Stapel, sondern dort
  (§15.5). `Session.only_imported` legt die fehlende Projektdatei dazu: Sobald es eine gibt,
  geht es um Änderungen an etwas, das der Kunde pflegt.

  **Zwei Dinge gehören dazu, sonst wäre es ein Verlust statt einer Erleichterung.** `modified`
  bleibt unangetastet, damit die automatische Sicherung (§38) weiterläuft — ein Absturz nach
  einem vierzehn Sekunden langen Import soll den Stand nicht kosten; das bewusste Schließen
  räumt sie dabei selbst weg, sonst böte der nächste Start sie an. Und ein eingelesenes Modell
  steht seither in **„Zuletzt geöffnet"**: Dort stand bisher nur, was als Projekt geöffnet
  wurde, und ohne die Frage beim Schließen wäre die Datei eine Suche im Dateidialog. Die
  Überschrift heißt „Zuletzt geöffnet" und nicht „Projekte" — sie stimmt also weiter.

  Nachweis: vier Fälle in `tests/test_ingest.py` (darunter sieben Wege, aus einem Import ein
  Dokument zu machen) und drei in `tests/test_ui.py`. Sieben Gegenproben, jede einzeln rot.
  `test_closing_with_unsaved_changes_asks` legt jetzt ausdrücklich einen Quader an, bevor es
  die Frage erwartet — ohne Arbeit gibt es keine mehr.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#neunzehn-kundendateien-durch-die-oberfläche-gefahren-04092026).

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

<a id="rm-141"></a>

- [x] **RM-141 — Exportvorgaben je Projekt und das Mehrdatei-Namensschema merken.** Am
  12.09.2026 gebaut. §29 sagt „Ordner, Format und Übergabeart werden je Projekt gemerkt" —
  gemerkt war die Übergabeart, der Rest begann bei jedem Export wieder bei 3MF und dem
  Projektstamm. Wer ein Modell für einen Dienstleister pflegt (STL) und daneben ein Gehäuse für
  den eigenen Slicer (3MF), stellte jedes Mal beides neu ein.

  **Drei Sachen werden gemerkt, und sie liegen an zwei Orten.** Format und Namensschema stehen
  im Dokument (`export_format`, `export_scheme`, Formatversion 23 mit Migration und
  `example_v23.p3d`): Sie gehören zum Teil, wie die Übergabeart daneben. Der **Ordner** steht in
  `UiSettings.export_dirs`, geschlüsselt nach Projektpfad — ein absoluter Pfad gehört nicht in
  eine Projektdatei (Regel 12), und derselbe Schnitt gilt für den Slicer-Pfad: Der zweite
  Rechner hat einen anderen Ordner, aber dieselbe Gewohnheit. Ein Ordner, den es nicht mehr
  gibt, wird beim Lesen übergangen; gedeckelt ist die Liste auf zwanzig Projekte.

  **Der Kundenweg fürs Schema ist das Namensfeld selbst.** Entstehen mehrere Dateien, steht dort
  nicht mehr `projekt.stl`, sondern `projekt_{object}_{index}von{count}.stl` — der Kunde sieht
  die Platzhalter, stellt sie um, ergänzt eigenen Text oder wirft sie weg. Was mit Klammern
  getippt wird, ist ein Muster; was ohne sie getippt wird, ist ein Name und überschreibt das
  gemerkte Muster nicht. Ein eigener Dialog dafür wäre ein zweiter Schritt vor einer Handlung,
  die ohnehin schon einen hat — und ins Datei-Menü passt kein dreizehnter Eintrag (zwölf sind
  die Grenze, `tests/test_interface_limits.py`).

  Dabei ist `default_scheme` aus `plan_export` herausgewachsen: Das Fenster zeigt jetzt dasselbe
  Muster, nach dem der Kern benennt, und zwei Stellen, die es ausrechnen, wären zwei Antworten.

  Nachweis: fünf Fälle in `tests/test_ui.py`, zwei in `tests/test_export.py`, drei in
  `tests/test_project.py` (darunter die Zusicherung, dass **kein** Ordner in der Projektdatei
  steht). Sieben Gegenproben, jede einzeln rot.

  [Bauplan-Abgleich und Nachweis](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026).

<a id="rm-142"></a>

- [x] **RM-142 — Verbindliche Projektion beim Messen einlösen.** Am 12.09.2026 gebaut. **Eine
  Produktentscheidung war nicht nötig**, der Bauplan sagt es ohne Vorbehalt: „orthografisch ist
  beim Messen Pflicht" (§18.1). Der Werkzeugweg setzte trotzdem nur den Messmodus; die
  vorhandene Umschaltung gehörte dem Skizzeneditor.

  **Die Maße waren dabei nie falsch** — sie kommen aus den Fangkoordinaten und nicht aus dem
  Bild. Falsch war, worauf der Nutzer beim Setzen zielt: Perspektivisch erscheinen zwei gleich
  lange Strecken verschieden lang, je weiter sie von der Bildmitte weg liegen, und genau dorthin
  setzt man beim Messen Punkte. Dasselbe Argument steht seit dem Skizzeneditor im Code, nur an
  der anderen Stelle.

  `MainWindow._on_measure_mode` schaltet beim Betreten um und beim Verlassen zurück. Drei
  Feinheiten gehören dazu, und jede hat ihren eigenen Fall: **nicht bei jedem Wechsel der
  Messart** (von *Abstand* auf *Wandstärke* ist kein Verlassen — ein zweites Merken machte aus
  dem Rückweg eine Einbahnstraße), **`settings.projection` bleibt unberührt** (Messen stellt
  vorübergehend um, wie der Skizzeneditor; das Häkchen im Menü zieht dagegen mit, denn es sagt,
  was gilt), und **eine ausdrückliche Wahl im Menü gewinnt** — wer währenddessen umschaltet,
  bestimmt damit das Rückkehrziel, sonst spränge die Ansicht beim Schließen auf einen Zustand,
  den er eine Minute vorher verworfen hat.

  Nachweis: vier Fälle in `tests/test_ui.py`, vier Gegenproben einzeln rot (ohne die Umschaltung,
  ohne den Rückweg, mit Merken bei jedem Wechsel, ohne die Menüwahl als Rückkehrziel).

  [Bauplan-Abgleich und Nachweis](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026).

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

<a id="rm-054"></a>

- [ ] **RM-054 — Prompt-Grundlast mit dem aktuellen Werkzeugbestand messen.** **Die beiden
  Zahlen im Punkt sind überholt** (nachgemessen 10.09.2026): `PROMPT_TOOL_COUNT` steht auf 119
  und `PROMPT_TOKENS` auf 28.281, beide seit `e71cd2ca` (09.09.2026) und gegen qwen3:14b
  gemessen. Die 114 und die 22.856 vom 03.09.2026 sind zwei Messungen alt. Was den Punkt offen
  hält, ist der nächste Zuwachs: Jede neue registrierte Operation verschiebt die Werkzeugzahl,
  und `tests/test_agent.py` hält die Konstante dagegen — der Wächter erzwingt die Neumessung,
  sobald eine dazukommt. Mit
  `tools/measure_local_model.py` gegen das dafür festgehaltene lokale Modell `prompt_eval_count`
  erfassen und Zahlen samt Modell/Schema/Datum nachziehen. Abnahme: die angezeigte Wartezeit und
  Budgetrechnung beruhen auf derselben gemessenen Nutzlast.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-der-gesamtreview-liegen-ließ-05092026).

<a id="rm-069"></a>

- [ ] **RM-069 — Verhaltensabnahme der kompakten Werkzeugschemata nachholen.** Die frühere
  Tokenmessung erreichte 24.161→19.641; der Umbau ist gebaut. Offen bleiben zwei vergleichbare
  Agenten-Suite-Läufe vor und nach der Verdichtung mit demselben erreichbaren Modell und denselben
  Referenzanfragen. Abnahme: Quote und Fehlfälle beider Läufe dokumentiert, keine ungeklärte
  Verschlechterung. Zugang wird über die Anwendung oder Umgebung eingerichtet; heutige Tokenmessung
  separat aktualisieren.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-chat-kontext-ist-nach-einem-objekt-zu-drei-vierteln-voll-30082026).

<a id="rm-081"></a>

- [ ] **RM-081 — Ollama-Laufzeit und verbleibende Optimierungen abnehmen.** Die lokale Modellserie
  auf die noch offenen Messungen begrenzen: Warm-/Kaltstart und Antwortqualität mit aktuellem
  Werkzeugschema erfassen, weitere Schemakürzungen gegen dieselben Referenzanfragen prüfen und die
  gestufte Werkzeugauswahl als Bedienentscheidung vorbereiten. Abnahme: Quote und Latenz aus
  demselben ruhigen Lauf samt GPU-Zustand; keine Qualitätsverschlechterung durch Kürzungen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#ollama-bis-zum-anschlag-31082026).

<a id="rm-144"></a>

- [ ] **RM-144 — Orientierungsanalyse über MCP ohne blockiertes Hauptfenster ermöglichen.** `read_analysis` bietet `orientation` im gemeinsamen Werkzeugschema an;
  `MainWindow.run_remote()` lehnt diesen Aufruf bis zum Arbeiteranschluss ausdrücklich ab.
  Die gemeinsame Fähigkeit nach Bauplan §26.6 über den begrenzten Fernaufruf verfügbar machen.
  Abnahme: derselbe Auftrag über Chat und MCP liefert nachvollziehbar dieselbe Analyse, das
  Fenster bleibt bedienbar und Abbruch sowie Zeitgrenze greifen. Die lesende Analyse erzeugt
  keine Geometrieänderung und keine Scheintransaktion.

  [Bauplan-Abgleich und Nachweis](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026).

## Tests und Entwicklungswerkzeuge

<a id="rm-020"></a>

- [ ] **RM-020 — Sicherung der eigenständigen Druckprojekte belegen.** Den Sicherungsweg für das
  eigenständige Repository 3D Drucker festlegen und belegen. Es hat weiterhin kein Git-Remote; ob
  eine andere Sicherung existiert, ist hier nicht nachgewiesen. Abnahme: Robert entscheidet über
  Remote oder anderen Sicherungsweg, und eine Wiederherstellungsprobe bestätigt den gesicherten
  Stand. Einen externen Upload erst aus dieser Entscheidung ableiten.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#vier-wege-von-hand-während-die-suite-grün-war-23082026).

<a id="rm-025"></a>

- [ ] **RM-025 — Unabhängige Sollwerte für geometrische Prüfungen absichern.** Krümmung,
  Durchmesser, Volumen und Achsen gezielt gegen analytische Größen oder unabhängige Rechnungen
  prüfen. Abnahme: Für jede geprüfte Kennzahl ist die Herkunft des Sollwerts dokumentiert; reine
  Wiederholungsprüfungen gelten nur als Determinismusnachweis.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#das-fundament-der-wahrnehmung-22082026).

<a id="rm-043"></a>

- [x] **RM-043 — Gemeinsame Kopfzeilenfrist an alle HTTP-Leser anschließen.** Erledigt am
  10.09.2026. **Es waren zehn Stellen, nicht vier** — gezählt am Syntaxbaum, nicht geschätzt:
  drei im Sprachbackend (`post_json`, `_get_json`, `pull_model`), eine im Mesh-Backend, dazu
  Support, Update, Aktivierung und die drei Werkzeuge `check_activation`, `licence_admin` und
  `upload_website`.

  **Was gefehlt hat, in einem Satz:** `timeout` an `OpenerDirector.open()` ist ein Zeitlimit
  **je Leseoperation**, keine Gesamtdauer. Gemessen an einer nachgestellten Gegenstelle, die
  ihre Kopfzeilen byteweise mit 20 ms Pause schickt: Statuszeile und Kopfzeilen brauchten eine
  volle Sekunde, das Zeitlimit stand auf **fünfzig Millisekunden**, und die Antwort kam mit
  200 zurück. Kein einzelner Lesevorgang hatte das Limit verletzt.

  `http.apply_header_deadline(opener, deadline)` hängt die Antwortklasse mit Frist in die
  Handler eines fertigen Öffners. **Angesetzt wird am Öffner und nicht an dem, der ihn baut**:
  Ein `deadline`-Argument an `discover.opener_for` hätte vierzehn Testattrappen gerissen, die
  ihn mit genau einem Positionsargument ersetzen; ein Objekt ohne `handlers` bleibt hier
  unangetastet. Der Öffner muss dem einzelnen Aufruf gehören — die Frist steckt in der
  erzeugten Klasse, also trüge ein geteilter nach dem ersten Aufruf für immer dessen Frist.
  Deshalb bauen `support`, `updates`, `licence_service` und die drei Werkzeuge ihren Öffner
  jetzt je Aufruf.

  **Ein Fehler auf dem Weg, und er gehört zum Nachweis:** Der erste Anlauf ersetzte
  `support._SUPPORT_OPENER` durch einen lokal gebauten Öffner — und riss damit den Testzugang,
  den eine Attrappe an dieser Konstante hatte. Der Aufruf ging danach an das **echte**
  example.org und kam mit 405 zurück; ein zweiter Test wurde durch die offen gebliebene
  Verbindung mit umgerissen. Was der Kern gewinnt, kann eine Attrappe verlieren: Wer einen
  geteilten Öffner auflöst, sieht nach, wer ihn patcht.

  Nachweis: `tests/test_http_security.py::test_an_opener_puts_its_headers_under_the_same_deadline`
  fährt beide Fälle — mit Frist ein `ResponseDeadlineError` unter 0,30 s, ohne Frist die
  gelungene Antwort nach über einer Sekunde. Dazu der Wächter
  `tests/test_hard_rules.py::test_every_network_call_puts_its_headers_under_a_deadline`: Er
  verlangt je Funktion mit einem `…open(request, timeout=…)` ein `apply_header_deadline`
  daneben und zählt zuerst, wie viele Netzaufrufe er überhaupt findet — ein Verbotstest über
  eine leere Menge wäre immer grün. **Gemessene Gegenprobe:** derselbe Lauf über `HEAD` nennt
  zehn Stellen, über den Arbeitsbaum keine.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-abnahme-des-gesamt-reviews-06092026).

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-abnahme-des-gesamt-reviews-06092026).

<a id="rm-098"></a>

- [ ] **RM-098 — Restliche Regelwerk-Nachträge abgleichen.** Die noch offenen Regelwerk-Nachträge
  gezielt entscheiden beziehungsweise prüfen: testbare Reichweite harter Regeln, Abgrenzung von
  Arbeitsverfahren und Fallgeschichte sowie passende Regeln für Auslieferungsdateien. Auch den
  Geltungsbereich der pauschalen 0,01-mm-Überlappung in `rules.toml` gegen konkrete Boolesche
  Fälle prüfen; eine inhaltliche Änderung braucht Version und vergleichbare Modell-Suiteläufe
  nach Bauplan §39. Abnahme: jede Prüfbehauptung hat einen passenden Wächter; keine doppelte
  Suite-Anleitung. Die zweistufige Testfahrweise ist bereits umgesetzt.

  **Zwei Teile sind erledigt und fallen aus dem Auftrag** (nachgeprüft 10.09.2026): Alle 13
  Dateien in `.claude/rules/` tragen ein `paths:`-Frontmatter, und **jedes** der 36 darin
  genannten Ziele existiert; die verwendeten Regelnummern sind 1, 2, 3, 7, 11–19, 21 und 22 —
  alle gibt es in `AGENTS.md`, keine zeigt ins Leere.

  **Was daran offen bleibt, ist ein Wächter für genau diesen Zustand**: Es gibt heute keinen
  Test über die `paths:`-Frontmatter und keinen über die Regelnummern; `test_agent_mirror.py`
  prüft nur `.claude/agents/`. Ein Zustand ohne Wächter ist ein Zustand auf Zeit. Dazu die
  fehlende `auslieferung.md` für `tools/` und `packaging/` und die vierfach stehende
  Suite-Anleitung (`AGENTS.md`, `CLAUDE.md`, `.claude/rules/tests.md`, `tests/CLAUDE.md`) —
  von vier Fassungen desselben Satzes veraltet immer eine.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

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

<a id="rm-100"></a>

- [~] **RM-100 — Sichtbares Terminalfenster aus dem Prozesstest vermeiden.** **Die Flagge ist
  gesetzt** (10.09.2026). `tests/test_process.py` holt die Startflaggen jetzt aus dem
  Produktivweg — `process.process_group_options(detached=True, no_window=True)` — statt
  `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` ein zweites Mal hinzuschreiben. Damit kommt
  `CREATE_NO_WINDOW` mit, das die Anwendung bei jedem losgelösten Prozess ohnehin setzt und
  das im Test fehlte; gemessen: `0x208` vorher, `0x8000208` jetzt, die Prozessgruppen-Flaggen
  unverändert. Eine Testfassung, die dieselben Flaggen selbst zusammensetzt, kann vom echten
  Startweg abweichen — diese kann es nicht mehr.

  **Offen bleibt die Sichtprüfung**, und die kann kein Test leisten: Ob unter Windows Terminal
  als Standardhost wirklich kein Fenster mehr aufgeht, sieht nur jemand, der zusieht. Der Test
  war die ganze Zeit grün — das Fenster war ein Nebeneffekt der Konsolenzuweisung und nicht
  der Prozessgruppe, die er prüft. Abnahme: Prozessbaum wird zuverlässig geschlossen, kein
  neues Terminalfenster erscheint und die Anwendung verhält sich ebenso.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-103"></a>

- [ ] **RM-103 — Große Kernfunktionen nach konkretem Wartungsbedarf aufteilen.** Die großen
  Kernfunktionen anhand ihres heutigen Aufbaus priorisieren; zuerst die Verantwortlichkeiten der
  Auswertung prüfen. Nur begründete Aufteilungen durchführen. Abnahme: gleiche Geometrie, IDs,
  Befunde und Laufzeit vor/nach dem Umbau sowie die vier Hauptwege; alte Zeilenzahlen nicht als
  aktuellen Befund weiterführen.

  **Gemessen am 10.09.2026**, damit die Größenordnung nicht aus einer alten Notiz kommt:
  `evaluate` hat 597 Zeilen, `_with_features` 596 — beide sind seit den Archivständen (521/580
  und 472/520) weiter gewachsen. Das begründet die Aufteilung nicht von selbst, es sagt nur,
  dass der Punkt nicht kleiner wird, während er wartet.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#architektur-durchsicht-02092026).

<a id="rm-106"></a>

- [ ] **RM-106 — Plattformunterschiede der Projektdateien dem richtigen Ursprung zuordnen.** Die
  plattformabhängigen Bytes erzeugter Beispielprojekte auf Inhalt und Kompression eingrenzen: nach
  demselben Erzeugerlauf Archivhash und normalisierte Hashes aller entpackten Dateien vergleichen.
  Abnahme: belegte Ursache und dokumentierter Reproduzierbarkeitsvertrag; ausgelieferte Rechtebelege
  bleiben an die eingecheckten Originalbytes gebunden.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-110"></a>

- [x] **RM-110 — Doppelten Leser offener Dateihandles zusammenführen.** Erledigt am
  10.09.2026. Die Frage steht jetzt einmal, in `app.core.paths.opened_path`;
  `scene/project._opened_file_path` und `updates._descriptor_path` sind dünne Hüllen darüber
  und tragen nur noch ihren Fehlervertrag — die eine wirft, die andere gibt `None`.

  **Die beiden Kopien waren nicht gleich, und das war der Grund, es zu tun.** Unter Windows
  nennt `GetFinalPathNameByHandleW` beim zweiten Aufruf entweder die geschriebene Länge oder,
  wenn der Puffer nicht reicht, die benötigte. Wächst der Pfad zwischen den beiden Aufrufen —
  ein umbenannter Ordner darüber genügt —, kommt der zweite Fall. `project` prüfte
  `written >= len(buffer)` und hielt an; `updates` prüfte nur gegen Null und rechnete mit
  einer **abgeschnittenen** Zeichenkette weiter, als Antwort auf eine Sicherheitsfrage. Die
  strengere Prüfung gilt jetzt für beide, ebenso die zwei POSIX-Kandidaten
  (`/proc/self/fd` **und** `/dev/fd`), die vorher nur `project` kannte.

  Gegen die Rückkehr des Zwillings steht
  `tests/test_hard_rules.py::test_the_path_behind_an_open_handle_is_asked_in_exactly_one_place`:
  Er zählt am Syntaxbaum die Dateien, die das System nach dem Pfad eines offenen Handles
  fragen, und verlangt genau eine. **Gemessene Gegenprobe:** derselbe Lauf über `HEAD` nennt
  zwei (`scene/project.py`, `updates.py`), über den Arbeitsbaum eine (`paths.py`). Die erste
  Fassung des Wächters suchte den API-Namen als Text und meldete `updates.py` weiterhin — sie
  hatte den Docstring gelesen, der dort seit der Zusammenführung erklärt, was die Datei
  **nicht** mehr tut.

  `F_GETPATH` mit genau 1024 Byte und der Wächter `test_no_fcntl_call_hands_over_more_than_python_takes`
  bleiben unverändert gültig; er greift jetzt an der gemeinsamen Stelle. Nachweis: 647 Tests
  aus `test_hard_rules`, `test_project`, `test_updates`, `test_ingest` und
  `test_scene_findings` grün, ruff, `ruff format --check` und mypy für `win32`, `linux` und
  `darwin` grün.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-113"></a>

- [ ] **RM-113 — Besitzerprüfung der Tokendatei auf dem Windows-Runner belegen.** Den Besitzer einer
  frisch angelegten privaten Tokendatei auf dem Windows-Runner ermitteln und die Prüfung mit einer
  tatsächlich nutzereigenen Datei fahren. Abnahme: SID und ACL dokumentiert, Test ohne bedingten
  Skip grün; eine breitere Besitzfreigabe nur nach Sicherheitsprüfung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-122"></a>

- [x] **RM-122 — Paralleles Einfügen in gemeinsame Dokumente absichern.** Erledigt am
  10.09.2026: `tools/memory_index.py` fügt genau eine Zeile in `MEMORY.md` ein — unter einer
  Sperrdatei daneben, mit dem Lesen **unter** der Sperre und einem Nachzählen vor dem
  Schreiben. Geschrieben wird über eine Datei daneben und `Path.replace`, also hinterlässt
  ein Abbruch den alten Index und keinen halben.

  Alle drei Teile haben ihren eigenen Grund, und der dritte ist der, den man weglassen würde:
  Die **Sperre** schützt vor der anderen Sitzung, das **Lesen unter ihr** vor dem Stand, der
  zwischen Lesen und Sperren veraltet, und das **Nachzählen** vor einem Fehler dieses
  Werkzeugs selbst — ein Muster, das zu viel trifft, ein Abschnitt, den es zweimal gibt.
  Abgewiesen wird außerdem eine Zeile ohne `[Titel](datei.md)`: Sie stünde im Index und wäre
  für `test_directory_docs` trotzdem kein Zeiger, und der meldete die Notiz dann als
  unverzeichnet.

  **Gemessene Gegenprobe**, mit zwei echten Prozessen und je zwanzig Einfügungen: Gegen eine
  ungeschützte Fassung — lesen, kurz warten, schreiben — gingen in drei Läufen **20, 17 und 20
  von 40** Einträgen verloren. Über das Werkzeug fehlte in denselben drei Läufen keiner.
  Nachweis: `tests/test_memory_index.py`, sechs Fälle; `tests/test_directory_docs.py` bleibt
  unverändert grün.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-geteilte-datei-ohne-werkzeug-03092026).

<a id="rm-134"></a>

- [ ] **RM-134 — Zusammenführung duplizierter Testhilfen entscheiden.** Roberts Entscheidung zum
  Umfang der Zusammenführung einholen. Belegt sind doppelte Freiformhilfen für Kegel/Torus und
  Bohrungswand-Klickhilfen; die historische Zahl von 21 Gruppen ist kein aktueller Messwert. Bei
  Freigabe gemeinsame Verträge klären und die betroffenen Hilfen an einem Pflegeort führen. Abnahme:
  gleiche fachliche Testfälle ohne doppelte Pflege; eine vollständige Testdurchsicht bleibt eine
  eigene Umfangsentscheidung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#doppelte-stellen-und-zwillinge-gemessen-07092026).

<a id="rm-137"></a>

- [ ] **RM-137 — Sitzungsende im tatsächlichen Editorbetrieb abnehmen.** Das tatsächliche SessionEnd
  beim Ende einer echten Editor-Sitzung beobachten und die Freigabe des Sitzungsgebiets belegen.
  Abnahme: sichtbarer echter Sitzungsablauf samt wirksamem Benutzer-PATH nach Neustart; eine
  konfigurierte Terminal-Statuszeile nicht als Desktop-Darstellungsnachweis behandeln.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#zwei-werkzeuge-zwei-wahrheiten-08092026).

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
  Zahlung und Rechtstexten folgt spätestens am 25.10. der Verkaufsbau für den beschlossenen
  01.11.2026: Demo- und Testphasenwerte, Website und Rechtstexte konsistent umstellen und den
  Aktualisierungsvorlauf prüfen. Fehlen Voraussetzungen, braucht es eine ausdrückliche neue
  Entscheidung zur auslaufenden Demo. Abnahme: kaufbarer und nutzbarer Weg oder beschlossene
  Übergangslösung vor Ablauf.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-robert-am-26082026-aufgetragen-hat).

<a id="rm-073"></a>

- [x] **RM-073 — Aufbewahrung alter Downloadpakete entscheiden.** **Entschieden am 10.09.2026
  (Robert): Die abgelöste Fassung wird geräumt, sobald die neue oben liegt.** Beim Release von
  0.4.0 so gefahren — `upload_website.py --alte-pakete` nennt zuerst, was keine angebotene Fassung
  mehr bedient (die fünf 0.3.5-Dateien), und löscht erst mit `--wirklich`; die Bedingung dafür ist
  eine `version.json` **vom Server**, die bereits die neue Fassung nennt.

  Ein gelöschtes Paket bricht dabei keinen verschickten Link: `dl/veraltet.php` leitet einen alten
  Namen auf die aktuelle Fassung **derselben Plattform** um (seit 03.09.2026). Gemessen nach dem
  Räumen — `dl/Solidon3D-Setup-0.3.5.exe` antwortet mit 200 und liefert 167 669 422 Bytes, also die
  0.4.0-Datei. **Der Statuscode ist hier die falsche Frage**; wer prüfen will, ob ein Paket wirklich
  weg ist, vergleicht die Länge.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-download-ordner-sammelt-jede-je-gebaute-fassung-30082026).

<a id="rm-149"></a>

- [ ] **RM-149 — Zwei Funde aus dem Release-Lauf von 0.4.0 zuordnen.** Beide am 10.09.2026
  gemessen, keiner blockiert eine Auslieferung.

  **Der Vorwarnlauf ist rot.** „Neueste Versionen" fährt ohne `constraints.txt` gegen die
  jeweils neuesten Abhängigkeiten und scheitert an genau einem Test:
  `test_chat_ui.py::test_a_short_chat_scrolls_its_content_without_covering_the_input[320-576-True]`.
  Ausgeliefert wird mit gepinnten Versionen, und die Suite ist dort dreimal grün — dafür gibt
  es den Lauf: Eine neuere Fassung ändert das Scrollverhalten des Chats bei kleiner
  Fensterhöhe. Abnahme: Ursache benannt und entweder behoben oder die Grenze in
  `pyproject.toml` mit Begründung eingetragen.

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

- [ ] **RM-091 — CRA-Meldebereitschaft vor dem 11.09.2026 herstellen.** Die in SECURITY-INCIDENT.md
  festgelegte Meldebereitschaft praktisch nachweisen: EU-Login und Plattformzugang, Vertretung,
  CSIRT-Zuordnung und Alarmierung prüfen; den Probelauf bis vor dem Absenden durchführen und privat
  protokollieren. Keine fingierte Meldung senden. Die CRA-Meldepflichten beginnen am 11.09.2026;
  Konten- und Betriebsbereitschaft sind durch Texte im Repository nicht belegt. Abnahme: sämtliche
  bereits festgelegten Bereitschaftspunkte mit tatsächlichen Ergebnissen geschlossen. Quelle:
  [EU-Kommission zu
  CRA-Meldepflichten](https://digital-strategy.ec.europa.eu/de/policies/cra-reporting).

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-092"></a>

- [ ] **RM-092 — Verkaufskonzept für den geplanten Start abschließen.** Das Verkaufskonzept bis zum
  15.10.2026 aktualisieren; der beschlossene Verkaufsstart ist der 01.11.2026. Preis, tatsächlichen
  Anbieter und Vertragspartner, Bestell-/Zustimmungsstrecke, Lieferung, Widerruf und Signierung
  festlegen. Abnahme: freigegebener Ablauf, Testkauf einschließlich Storno und passende Rechtstexte;
  überholte Konzepte eindeutig kennzeichnen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-093"></a>

- [ ] **RM-093 — Noch fehlende Angaben und Prüfungen der Rechtstexte klären.** Die offenen Rechts-
  und Anbieterentscheidungen vor dem Verkauf fachlich abschließen: Kontakt-/Steuerangaben,
  tatsächlicher Zahlungsanbieter samt Bestellbestätigung und Widerruf, Datenschutzrollen sowie
  Markenrecherche. Für Chat und Generatoren zusätzlich die eigene KI-Systemrolle sowie die
  einschlägigen Transparenzpflichten aus Art. 50 Abs. 1 und 2 der KI-Verordnung fachlich einordnen
  und am angebotenen Einstieg prüfen. Abnahme: dokumentierte Entscheidungen und geprüfte Verträge/Sprachfassungen;
  bereits berichtigte Widerrufszitate und EULA-Sanktionsklausel nicht erneut beauftragen.

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
