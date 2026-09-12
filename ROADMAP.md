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
| [RM-065 — TLS und Update-Prüfung auf einem Kunden-Mac bestätigen](#rm-065) | Plattformen, Pakete und Grafik | Aktualisierungsprüfung aus dem aktuellen Mac-Paket erfolgreich ausführen |
| [RM-104 — Verbleibende Mac- und Unix-Befunde mit aktueller CI-Abdeckung abnehmen](#rm-104) | Plattformen, Pakete und Grafik | Intel-Hänger und übrige Unix-Fenster-/Export-/Chatfälle abnehmen |
| [RM-107 — Ubuntu-Workerabbruch mit aktuellem Testbestand zuordnen](#rm-107) | Plattformen, Pakete und Grafik | Auslöser mit aktueller Testreihenfolge und Widget-/Worker-Lebensdauer eingrenzen |
| [RM-114 — Vereinfachungsziele auf Apple Silicon vermessen](#rm-114) | Plattformen, Pakete und Grafik | Hohlkugel-Zielreihe samt echter Warnung auf Apple Silicon messen |
| [RM-117 — Öffentliche Downloadlinks vollständig in die Paketprüfung aufnehmen](#rm-117) | Plattformen, Pakete und Grafik | Die stille Lücke ist zu; offen bleiben die Prüfsummen-Entscheidung und der Abruf gegen den Server für 0.4.0 |
| [RM-005 — Wahl der Stiftseite gegen das fertige Stützvolumen prüfen](#rm-005) | Geometrie, Erkennung und Druckvorbereitung | Beide Stiftseiten am fertigen Stützvolumen vergleichen |
| [RM-017 — Nutfedermaße an realen Aluminiumprofilen prüfen](#rm-017) | Geometrie, Erkennung und Druckvorbereitung | Zwei benannte Aluminiumprofile nachmessen und Passung prüfen |
| [RM-022 — Phase zur Flächenrückgewinnung aus Netzen entscheiden](#rm-022) | Geometrie, Erkennung und Druckvorbereitung | Umfang und Genauigkeitsgrenzen einer eigenen Phase entscheiden |
| [RM-023 — Verweisfilter über wechselnde Objektkennungen hinweg prüfen](#rm-023) | Geometrie, Erkennung und Druckvorbereitung | Verweisfilter nach einem Wechsel der Objektkennung prüfen |
| [RM-024 — Gespeicherte Zuordnungsantworten im echten Konfliktfall abnehmen](#rm-024) | Geometrie, Erkennung und Druckvorbereitung | Prüfkörper steht; Abnahme über `evaluate` selbst und ein Rundlauf für `matches` fehlen |
| [RM-039 — Fehlende Schnittflächen an offenen Netzen verständlich erklären](#rm-039) | Geometrie, Erkennung und Druckvorbereitung | Der Befund erklärt es jetzt; offen ist der Knopf im Prüfbericht (`FINDING_ACTIONS`) |
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
| [RM-097 — Verbleibende Kernbefunde des Reviews einzeln beheben](#rm-097) | Geometrie, Erkennung und Druckvorbereitung | Sechs kleine Stellen: Lesefehlertext, zwei Namen ohne Zähler, ein doppeltes `_fell_apart`, zwei feste Zahlen, ein Menütext |
| [RM-109 — Schichtanalyse der Rändelplatte gezielt beschleunigen](#rm-109) | Geometrie, Erkennung und Druckvorbereitung | Mindestbreitenprüfung mit gleichem Befund gezielt beschleunigen |
| [RM-127 — Wandstärke nach Änderungen am fertigen Modell prüfen](#rm-127) | Geometrie, Erkennung und Druckvorbereitung | Dünne Wände am Endzustand in beiden Änderungsreihenfolgen prüfen |
| [RM-128 — Bearbeitbarkeit erkannter Flächen entscheiden](#rm-128) | Geometrie, Erkennung und Druckvorbereitung | Entscheiden, ob eine Verrundung ohne jede Operation in der Merkmalsliste stehen soll |
| [RM-132 — Freiformerkennung am Ein-Sekunden-Ziel messen](#rm-132) | Geometrie, Erkennung und Druckvorbereitung | Organische und mechanische 200.000-Dreiecke-Fälle gegen eine Sekunde messen |
| [RM-133 — Rückmeldung zur Volumenänderung beim Merkmaldrehen entscheiden](#rm-133) | Geometrie, Erkennung und Druckvorbereitung | Kundennutzen eines Hinweises zur korrekten Volumenänderung entscheiden |
| [RM-138 — Gespeicherten Bausteinstand beim Öffnen wählbar erhalten](#rm-138) | Geometrie, Erkennung und Druckvorbereitung | Wahl zwischen aktuellem und noch verfügbarem früherem Bausteinstand ermöglichen |
| [RM-139 — Geometrische Orientierungskandidaten aus der konvexen Hülle ableiten](#rm-139) | Geometrie, Erkennung und Druckvorbereitung | Hüllnormalen sind gebaut; es fehlt die Messung gegen die vollständige Kandidatenliste |
| [RM-140 — Exportbefunde vor dem Schreiben sichtbar machen](#rm-140) | Geometrie, Erkennung und Druckvorbereitung | Vorprüfung mit Passungen und endgültigen Wandstärken vor dem Dateischreiben anschließen |
| [RM-143 — Selbstdurchdringungen in der Netzfehlerkarte sichtbar markieren](#rm-143) | Geometrie, Erkennung und Druckvorbereitung | Markierung an einem reproduzierbaren durchdrungenen Körper anschließen |
| [RM-147 — Die acht beauftragten Konstruktionserweiterungen bauen](#rm-147) | Geometrie, Erkennung und Druckvorbereitung | Die ganze Kanten- und Flächenarbeit greift an beiden Kernen — offen bleiben Zeiger und Rechtsklick an der Kante, die Anbindung des Flächengriffs an die gewählte Fläche und fünf zugesagte Kundenwege |
| [RM-151 — Das Freiform-Urteil nennt konstruierte Teile einen Scan](#rm-151) | Geometrie, Erkennung und Druckvorbereitung | Befundtext trennen von der Entscheidung, welche Formen wegfallen |
| [RM-156 — Die Breite eines Langlochs ändern](#rm-156) | Geometrie, Erkennung und Druckvorbereitung | `resize_hole` nimmt nur die runde Bohrung; am Langloch fehlt der Weg zu einer anderen Breite |
| [RM-070 — SpaceMouse auf macOS und Linux am echten Gerät abnehmen](#rm-070) | Bedienung und Darstellung | Mac-/Linux-Gerätelauf, Treiberwechselwirkung und große Szene abnehmen |
| [RM-074 — Verbleibenden Bildnachweis der Viewport-Serie abschließen](#rm-074) | Bedienung und Darstellung | Befundsprung und sichtbare Marke an einem echten Warnprojekt zeigen |
| [RM-079 — Zeilenlängen der Website über alle Sprachen prüfen](#rm-079) | Bedienung und Darstellung | Textbreiten in sechs Sprachen auf schmalen und breiten Fenstern prüfen |
| [RM-084 — Kundentexte gegen die vereinbarte Sprache prüfen](#rm-084) | Bedienung und Darstellung | Kundentexte systematisch prüfen und alle Sprachfassungen nachziehen |
| [RM-088 — Verständlichkeit für Laien im Regelwerk verankern](#rm-088) | Bedienung und Darstellung | Verständlichkeitsregel und begründete Ausnahmen entscheiden |
| [RM-090 — Serie zum Übergabestatus entscheiden](#rm-090) | Bedienung und Darstellung | Nächsten Umfang aus den fünf Vorschlägen des Produktkompasses entscheiden |
| [RM-101 — Elternlosen Handlungsknopf im Fensteraufbau zuordnen](#rm-101) | Bedienung und Darstellung | Verdacht am Code widerlegt; das gesehene fremde Fenster bleibt unerklärt |
| [RM-108 — Abbauzeit des Schlüsseldialogs messen und begrenzen](#rm-108) | Bedienung und Darstellung | Schlüsseldialog während laufender Abfrage ohne Wartefrist schließen |
| [RM-119 — Schnittebene bei mehreren Druckplatten richtig darstellen](#rm-119) | Bedienung und Darstellung | Schnittebene auf versetzten Platten und in Explosionsdarstellung prüfen |
| [RM-124 — Zusätzlichen Render durch show_build_volume messen](#rm-124) | Bedienung und Darstellung | Bauraum-Aufwand messen; unnötigen Aufbau bei unverändertem Zustand vermeiden |
| [RM-130 — Speicherhinweis nach reinem Import verständlich gestalten](#rm-130) | Bedienung und Darstellung | Speicherhinweis nach reinem Betrachten eines Imports entscheiden |
| [RM-131 — Zurückgestellten Mehrfachimport entscheiden](#rm-131) | Bedienung und Darstellung | Zurückgestellt; bei Wiederaufnahme Mehrfachimport mit gemeinsamer Lage planen |
| [RM-135 — Zugewiesene Höhe der Filamentkarte vollständig nutzen](#rm-135) | Bedienung und Darstellung | Korrigierten Höhenvertrag nach grüner Windows-Abnahme auf macOS bestätigen |
| [RM-136 — Gezeichnetes Fensterschema und Bildbeschreibungen aktualisieren](#rm-136) | Bedienung und Darstellung | Fensterschema, Bildunterschriften und Alternativtexte aller Sprachen nachziehen |
| [RM-141 — Exportvorgaben je Projekt und das Mehrdatei-Namensschema merken](#rm-141) | Bedienung und Darstellung | Exportformat, Zielordner und gewähltes Namensschema nach Wiederöffnen erhalten |
| [RM-142 — Verbindliche Projektion beim Messen einlösen](#rm-142) | Bedienung und Darstellung | Orthografische Messansicht anschließen oder den Vertrag ausdrücklich neu entscheiden |
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

- [ ] **RM-065 — TLS und Update-Prüfung auf einem Kunden-Mac bestätigen.** Der certifi-Rückfall und
  die Vorrangregel für eine Firmen-CA sind gebaut; Paketinhalt allein genügt nicht. Abnahme:
  aktuelles `.pkg` starten und die Aktualisierungsprüfung erfolgreich ausführen, bei einem Fehler
  den konkreten TLS-Grund aus dem Protokoll festhalten.

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

- [ ] **RM-023 — Verweisfilter über wechselnde Objektkennungen hinweg prüfen.** Der Verweisfilter in
  `evaluate` hängt noch an der gespeicherten Objekt-ID. Objektidentität durch den Stapel verfolgen;
  Abnahme: ein benutztes Merkmal erreicht seine Zuordnungsfrage auch nach einem Kennungswechsel,
  gleichnamige Merkmale anderer Körper erzeugen keine zusätzlichen Fragen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#das-fundament-der-wahrnehmung-22082026).

<a id="rm-024"></a>

- [ ] **RM-024 — Gespeicherte Zuordnungsantworten im echten Konfliktfall abnehmen.**
  `Operation.matches` und Speichern/Wiederöffnen sind gebaut. **Auch der geometrisch echte Fall
  steht** (nachgemessen 10.09.2026): `tests/test_evaluation.py` führt eine Platte mit zwei nah
  beieinander liegenden Bohrungen über die echte Erkennung — einmal gefragt, aufgeschrieben,
  beim zweiten Lauf still. Was fehlt, ist zweierlei: Die Abnahme läuft dort über
  `_with_features` und nicht über `evaluate` selbst, dessen Tests die Mehrdeutigkeit noch per
  Monkeypatch erzwingen; und für `Operation.matches` gibt es keinen Speichern-/Wiederöffnen-
  Rundlauf, obwohl das Feld serialisiert wird. Abnahme über `evaluate`:
  jede nötige Entscheidung einmal, erneute Auswertung und Wiederöffnen ohne dieselbe Rückfrage;
  Abbruch liefert einen Befund. Die historische 99→7→0-Reihe nur mit dem damaligen 52-Teile-Projekt
  vergleichen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#das-fundament-der-wahrnehmung-22082026).

<a id="rm-039"></a>

- [~] **RM-039 — Fehlende Schnittflächen an offenen Netzen verständlich erklären.** **Der Befund
  nennt seit dem 10.09.2026 die Ursache**: „Die Schnittflächen bleiben offen: Das Modell hat
  schon vor dem Schnitt ein Loch. Reparieren Sie es und teilen Sie danach erneut."

  Der alte Satz — „Die Schnittflächen konnten nicht geschlossen werden" — war nicht falsch,
  aber er zeigte in die falsche Richtung: Er klang nach einem Fehler des Schnitts, also suchte
  man am Schnitt. Der Schnitt kann nichts dafür. `SectionResult.capped` ist genau
  `is_watertight` der **Eingabe** (`section._apply` liest sie und reicht sie durch), das
  Modell war also schon vorher offen — und ein offenes Netz lässt sich nicht ehrlich deckeln.
  Nachweis: `tests/test_autosplit.py::test_the_open_cut_says_why_and_what_to_do` prüft die
  Aussage und nicht den Wortlaut; Gegenprobe gefahren, mit dem alten Satz ist er rot. Die fünf
  Kataloge sind nachgezogen — der Meldungstext **ist** der Schlüssel, und ohne sie fielen
  `en`, `es`, `fr`, `it` und `pt` auf Deutsch zurück.

  **Offen bleibt der Knopf.** `split.uncapped` steht nicht in `FINDING_ACTIONS`
  (`app/ui/panels.py`), also führt der Befund im Prüfbericht zu keiner Handlung; die
  Geschwister `split.no_plane` und `split.cut_failed` haben dort welche.
  `REPAIR_AND_RETRY` gibt es bereits. Nicht gemacht, weil an `panels.py` am selben Tag eine
  zweite Sitzung arbeitete und eine Zeile in einer fremden offenen Datei verloren geht.
  Abnahme dann: offenes Netz erzeugt den verständlichen Befund **mit** anklickbarem Rückweg,
  ein sauber geschlossenes Netz bleibt unverändert.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#der-erste-linux-kunde-und-was-sein-protokoll-trug-06092026).

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

- [~] **RM-097 — Verbleibende Kernbefunde des Reviews einzeln beheben.** **Die Restliste ist
  kürzer als sie dasteht** (nachgemessen 10.09.2026). Erledigt sind: der aussagekräftige
  Lesefehler bei verknüpften Quellen (leere und ungültige Prüfsumme werden abgewiesen, eine
  fehlende Verknüpfung hat ihren eigenen Satz), die einmalige Ermittlung von
  `support_on_model` (ein Aufrufer je Analyse), die profilgebundene Schichtschwelle
  `WIDTH_INTERESTING` und der Namensparameter am Deckel.

  **Offen bleiben sechs kleine Stellen**: der übrige `OSError` beim Öffnen heißt weiterhin
  „sie ist beschädigt", obwohl er auch etwas anderes sein kann; „Prüfstück" und „Drehdeckel"
  tragen keinen Zähler und sind damit im Baum nicht unterscheidbar; `_fell_apart` steht doppelt
  (`label_ops.py` und `texture_ops.py`, die Doppelung ist im Code selbst vermerkt);
  `NOISE_VOLUME` und `BRIDGE_FROM` stehen als feste Zahlen statt am Profil (Regel 7); und der
  Menüeintrag heißt weiter „Druckeinstellungen …", während der Weg dahinter der Slicer-Weg ist.
  Abnahme je Änderung am betroffenen Kunden- und Fehlerfall.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-109"></a>

- [ ] **RM-109 — Schichtanalyse der Rändelplatte gezielt beschleunigen.** Die Vorprüfung der
  Mindestbreite optimieren, ohne dünne Rippen wieder zu übersehen. Abnahme: Rändelplatte,
  Rippenplatte und Kugel mit identischen Befunden vor/nach der Änderung, aktuelle isolierte
  Laufzeiten und keine Verschlechterung der Formprüfung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-127"></a>

- [ ] **RM-127 — Wandstärke nach Änderungen am fertigen Modell prüfen.** Druckkritisch dünne Wände
  nach Geometrieänderungen am Endzustand prüfen. Abnahme: beide Reihenfolgen von
  Außenmaß-/Bohrungsänderung erzeugen denselben Bericht; eine am Ende behobene Zwischenwarnung
  verschwindet, eine unter der Profilgrenze verbleibende Wand wird verständlich gemeldet.

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

- [ ] **RM-132 — Freiformerkennung am Ein-Sekunden-Ziel messen.** Die Merkmals-Erkennung organischer
  Freiformen auf das allgemeine Ein-Sekunden-Ziel für 200000 Dreiecke bringen oder das Ziel
  ausdrücklich neu entscheiden. Abnahme: organischer und mechanischer Referenzfall, unveränderte
  Merkmale/IDs und isolierte Laufzeitmessung; großzügigere Regressionsgrenzen nicht als
  Zielerfüllung werten.

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

- [ ] **RM-140 — Exportbefunde vor dem Schreiben sichtbar machen.** Bauplan §29 verlangt sichtbare Befunde vor dem Schreiben bei weiterhin möglichem
  Export. `_ExportWorker` prüft und schreibt derzeit in einem Lauf; Befunde kommen erst danach.
  `check_before_export()` enthält keine Passungs- oder Wandstärkenprüfung. Den Vorprüfungsweg im
  Arbeiter ausführen, aktuelle Passungen und die Endwandstärken aus RM-127 anschließen und vor dem
  Schreiben anzeigen. Abnahme: verletzte Passung und dünne Endwand sind vorher sichtbar, große
  Projekte bleiben bedienbar, ein bewusst fortgesetzter Export schreibt das gewählte Ergebnis.

  [Bauplan-Abgleich und Nachweis](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026).

<a id="rm-143"></a>

- [ ] **RM-143 — Selbstdurchdringungen in der Netzfehlerkarte sichtbar markieren.** Die Netzfehlerkarte aus Bauplan §18.4 verspricht Durchdringungen.
  `perceive/maps.py:defect_map()` markiert aktuell offene und nicht-mannigfaltige Kanten, führt
  aber keine Schnittprüfung aus. Anforderung an einem reproduzierbaren Körper anschließen;
  eine generelle Fehlermeldung ersetzt die räumliche Markierung nicht. Abnahme: betroffene
  Dreiecke sind sichtbar auffindbar, ein sauberer Gegenkörper bleibt unmarkiert und die
  Bedeutung ist zusätzlich zur Farbe erkennbar.

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

- [ ] **RM-151 — Das Freiform-Urteil nennt konstruierte Teile einen Scan.** Aufgefallen am
  10.09.2026 an Roberts `garden-hose-holder.3mf`: ein konstruierter Halter mit einem organisch
  geschwungenen Bogen, dessen 194 nicht veröffentlichte Kugel- und Ringkandidaten ihn auf einen
  Rundformanteil von 0,701 gegen die Schwelle 0,700 bringen — ein Tausendstel. Die Entscheidung,
  seine 252 erfundenen Rundformen wegzulassen, ist **richtig** und bleibt; falsch ist der Satz
  daneben: „Dieses Modell ist eine Freiform, etwa ein Scan" — und das liest ein Kunde als
  Aussage über sein Teil, nicht über eine Zählung. **Der Satz steht in
  `scene/evaluate.py` und nicht in `perceive`**, als Befund `perceive.freeform` mit der Zahl in
  `values["dropped"]`; die Schwelle daneben ist `perceive/features.FREEFORM_ROUND_SHARE`, und
  sie darf laut ihrem eigenen Kommentar ausdrücklich nicht nachgezogen werden. Wer den Satz
  ändert, ändert damit den **Katalogschlüssel** — die deutsche Quelle ist der Text selbst, und
  ohne die fünf Übersetzungen fielen `en`, `es`, `fr`, `it` und `pt` auf Deutsch zurück. Der Fund selbst
  (vier verlorene Senkungen) ist am selben Tag behoben — `features.sits_at_the_mouth_of` rettet,
  was an einer Bohrung hängt —, der Text nicht.
  Abnahme: Der Befund sagt, was gemessen wurde und was daraus folgt, ohne dem Modell eine Herkunft
  zuzuschreiben, die niemand geprüft hat; die Zahl bleibt darin (Regel 17). Vorher entscheiden, ob
  daneben ein zweiter Zustand gebraucht wird — „überwiegend rund" gegen „Freiform" —, oder ob ein
  Satz für beide Fälle reicht. Ein zweiter Zustand kostet eine Schwelle mehr, und die Lücke
  zwischen Nozzle-Box (59 Prozent) und Retro-Maus (77 Prozent) ist schmal.

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

- [ ] **RM-156 — Die Breite eines Langlochs ändern.** `resize_hole` nimmt nur die runde Bohrung
  (`applies_to=["hole"]`), `resize_feature` nur Materie; am Langloch führt heute kein Weg zu einer
  anderen Breite, und `NOT_APPLICABLE_HERE` sagt das an beiden Zeilen als „noch nicht gebaut".
  Der Werkzeugkörper ist da (`_feature_solid` mit `scale`), die Rückzuordnung von `resize_hole`
  (`_recognised_resized_feature`, `_expected_bore`) kennt aber nur den Durchmesser einer
  Bohrung — am Langloch müsste sie Länge und Richtung mitführen, und am exakten Kern baut
  `brep.edit.resize_bore` einen Zylinder. Abnahme: Ein Langloch Ø 6 auf 20 wird über das Feld
  *Durchmesser* zu Ø 8 auf 22 (der Weg bleibt, die Enden wachsen), an beiden Kernen, mit
  derselben Kennung.

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
  den 3Dconnexion-Treiber. Offen: aktueller Mac-Gerätetest, Linux-Rechte und Gerätetest, Verhalten
  bei paralleler 3DxWare-Mausemulation sowie Bildrate an einem Netz mit 1 Mio. Dreiecken. Abnahme je
  Plattform mit benanntem Gerät, Treiber und reproduzierbarer Navigation; eine automatische Änderung
  der Treiberkonfiguration vorher entscheiden.

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

- [ ] **RM-101 — Elternlosen Handlungsknopf im Fensteraufbau zuordnen.** **Der Verdacht ist am
  Code widerlegt** (10.09.2026): Der Befundknopf entsteht in `ui/panels.py` mit Elternwidget und
  wird erst danach ins Layout gehängt — und zwar seit dem 27.08.2026, also schon vor der
  Messung, die den Verdacht auslöste. Ein Suchlauf über elternlos konstruierte Knöpfe in
  `app/ui/` fand keinen im Ladeweg. Damit ist die vermutete Ursache erledigt; was der Punkt
  noch trägt, ist die **Beobachtung** selbst — es hat jemand ein fremdes Fenster gesehen, und
  woher es kam, ist offen. Am aktuellen Fenster reproduzieren, bevor weiter gesucht wird.
  Abnahme: kein fremdes Top-Level-Fenster, Hauptfenster behält Fokus und der Befundknopf
  funktioniert nach Einhängen ins Layout. Den alten Verdacht nicht als bestätigte Ursache behandeln.

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

- [ ] **RM-119 — Schnittebene bei mehreren Druckplatten richtig darstellen.** Die sichtbare
  Schnittebene bei versetzten Druckplatten und Explosionsdarstellung in den richtigen Koordinaten
  auswerten. Abnahme: senkrechte und waagerechte Ebenen treffen das im Bild gewählte Teil auf jeder
  Platte; Schnitt, Marke und Bedienung stimmen überein.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#viewport-werkzeuge-aus-kundensicht-03092026).

<a id="rm-124"></a>

- [ ] **RM-124 — Zusätzlichen Render durch show_build_volume messen.** Den unveränderten Bauraum
  beim Auswerten nicht erneut aufbauen, falls eine Messung den Aufwand bestätigt. Abnahme: aktueller
  pygfx-Aufwand vorher/nachher sowie richtige Aktualisierung bei Bauraum, Plattenzahl, Profil,
  Zeichenebene, Bettsichtbarkeit und Plattenumriss.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-eine-aufräum-durchsicht-offenließ-04092026).

<a id="rm-130"></a>

- [ ] **RM-130 — Speicherhinweis nach reinem Import verständlich gestalten.** Den
  Schließen-/Speichern-Ablauf für einen nur betrachteten Import entscheiden und an Kundendateien
  umsetzen. Abnahme: reines Öffnen/Betrachten wird verständlich behandelt, tatsächliche Bearbeitung
  bleibt vor Datenverlust geschützt, Import-/Projektzustände sind eindeutig.

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

- [ ] **RM-141 — Exportvorgaben je Projekt und das Mehrdatei-Namensschema merken.** Bauplan §29 sagt gespeicherte Exportvorgaben und ein wählbares Namensschema zu.
  `PrintSettings.handover` merkt die Übergabeart; `action_export()` startet dagegen wieder mit
  3MF und Projektstamm. Das Namensschema existiert im Kern, hat für mehrere Objekte aber keinen
  entsprechenden Kundenweg. Abnahme: zwei Projekte mit unterschiedlichen Vorgaben wieder öffnen
  und getrennt korrekt exportieren; ein selbst gewähltes Schema bleibt erhalten. Gerätepfade
  bleiben lokal oder werden projektkonform relativ behandelt (Regel 12).

  [Bauplan-Abgleich und Nachweis](ROADMAP-ARCHIV.md#bauplan-v12--vollständiger-abgleich-08092026).

<a id="rm-142"></a>

- [ ] **RM-142 — Verbindliche Projektion beim Messen einlösen.** Bauplan §18.1 verlangt orthografische Darstellung beim Messen. Der Werkzeugweg
  ruft `Viewport.set_measure_mode()` auf, setzt dabei aber keine Projektion; der vorhandene
  orthografische Wechsel gehört zum Skizzenweg. Den Messablauf einschließlich Rückweg eindeutig
  festlegen und anschließen. Falls lediglich eine Empfehlung beabsichtigt ist, diese
  Produktentscheidung ausdrücklich treffen. Abnahme: Messen aus perspektivischer Ansicht folgt
  dem festgelegten Vertrag, zeigt korrekte Maße und erhält einen verständlichen Kamera-Rückweg.

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
