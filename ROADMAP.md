# ROADMAP — Arbeitsliste

Abgleich vom **08.09.2026** gegen Bauplan §40, Quelltext, Tests, Paketmetadaten
und Git-Verlauf. Der lokale Veröffentlichungsstand ist **0.3.5**
(`website/version.json`). Die früheren Durchsichten und Messreihen stehen im
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
| [RM-001 — Signierung und Notarisierung der Kundenpakete belegen](#rm-001) | Plattformen, Pakete und Grafik | Mac-Signatur scheitert an `APPLE_SIGN_IDENTITY` („no identity found", 10.09.2026); Identität aus dem Schlüsselbund lesen, dann 0.4.0 vollständig bauen |
| [RM-011 — Erstinstallation auf einem fremden Rechner abnehmen](#rm-011) | Plattformen, Pakete und Grafik | Fremdrechner ohne Entwicklungsumgebung von Download bis Export prüfen |
| [RM-021 — Native Fensterlebensdauer am aktuellen Renderer abnehmen](#rm-021) | Plattformen, Pakete und Grafik | Sporadische Riss-/Hängerfamilien gezielt wiederholt prüfen; vollständiges Tor ist grün |
| [RM-050 — Kopierkosten messen und verbleibende VTK-Geometrie ablösen](#rm-050) | Plattformen, Pakete und Grafik | Kopier-/Pufferkosten messen und VTK aus der Bereichsprüfung ablösen |
| [RM-051 — Renderer und Grafiklaufzeit in Linux- und Mac-Paketen abnehmen](#rm-051) | Plattformen, Pakete und Grafik | Grafik und Eingabe der tatsächlichen Linux-/Mac-Kundenpakete abnehmen |
| [RM-055 — Neue Paketwerkzeuge im installierten Kundenpaket abnehmen](#rm-055) | Plattformen, Pakete und Grafik | Flatpak-Lauf und tatsächlich verwendeten Inno-Compiler am Kundenpaket belegen |
| [RM-065 — TLS und Update-Prüfung auf einem Kunden-Mac bestätigen](#rm-065) | Plattformen, Pakete und Grafik | Aktualisierungsprüfung aus dem aktuellen Mac-Paket erfolgreich ausführen |
| [RM-104 — Verbleibende Mac- und Unix-Befunde mit aktueller CI-Abdeckung abnehmen](#rm-104) | Plattformen, Pakete und Grafik | Intel-Hänger und übrige Unix-Fenster-/Export-/Chatfälle abnehmen |
| [RM-107 — Ubuntu-Workerabbruch mit aktuellem Testbestand zuordnen](#rm-107) | Plattformen, Pakete und Grafik | Auslöser mit aktueller Testreihenfolge und Widget-/Worker-Lebensdauer eingrenzen |
| [RM-114 — Vereinfachungsziele auf Apple Silicon vermessen](#rm-114) | Plattformen, Pakete und Grafik | Hohlkugel-Zielreihe samt echter Warnung auf Apple Silicon messen |
| [RM-117 — Öffentliche Downloadlinks vollständig in die Paketprüfung aufnehmen](#rm-117) | Plattformen, Pakete und Grafik | Alle öffentlichen Paketlinks in die Byte-/Prüfsummenprüfung aufnehmen |
| [RM-005 — Wahl der Stiftseite gegen das fertige Stützvolumen prüfen](#rm-005) | Geometrie, Erkennung und Druckvorbereitung | Beide Stiftseiten am fertigen Stützvolumen vergleichen |
| [RM-017 — Nutfedermaße an realen Aluminiumprofilen prüfen](#rm-017) | Geometrie, Erkennung und Druckvorbereitung | Zwei benannte Aluminiumprofile nachmessen und Passung prüfen |
| [RM-022 — Phase zur Flächenrückgewinnung aus Netzen entscheiden](#rm-022) | Geometrie, Erkennung und Druckvorbereitung | Umfang und Genauigkeitsgrenzen einer eigenen Phase entscheiden |
| [RM-023 — Verweisfilter über wechselnde Objektkennungen hinweg prüfen](#rm-023) | Geometrie, Erkennung und Druckvorbereitung | Verweisfilter nach einem Wechsel der Objektkennung prüfen |
| [RM-024 — Gespeicherte Zuordnungsantworten im echten Konfliktfall abnehmen](#rm-024) | Geometrie, Erkennung und Druckvorbereitung | Echten mehrdeutigen Nachfolger über Auswertung und Wiederöffnen abnehmen |
| [RM-039 — Fehlende Schnittflächen an offenen Netzen verständlich erklären](#rm-039) | Geometrie, Erkennung und Druckvorbereitung | Offenes Eingangsnetz im Schnittbefund erklären und Reparatur anbieten |
| [RM-041 — Innenraum importierter entlüfteter Hohlkörper klären](#rm-041) | Geometrie, Erkennung und Druckvorbereitung | Schätzweg oder dokumentierte Grenze des Innenraums entscheiden |
| [RM-042 — Leistungsgrenze der Merkmalserkennung bis eine Million Dreiecke klären](#rm-042) | Geometrie, Erkennung und Druckvorbereitung | Großen Korpus messen und belegte Erkennungsgrenze mit §31 abgleichen |
| [RM-045 — Drei Laufzeitkosten des Geometriereviews messen](#rm-045) | Geometrie, Erkennung und Druckvorbereitung | Aushöhlen, Formkopien und Innenraumketten getrennt vermessen |
| [RM-071 — Beschlossene Resin-Stufe 1 umsetzen](#rm-071) | Geometrie, Erkennung und Druckvorbereitung | Druckverfahren im Profil, zwei Resin-Bauräume und FDM-Regelbereiche bauen |
| [RM-076 — Topologieverlust beim Reduzieren von Eule und Spiderman beheben](#rm-076) | Geometrie, Erkennung und Druckvorbereitung | Eule und Spiderman mit Zielreihe und Topologievergleich reproduzieren |
| [RM-077 — Reduzierungsziel bei Körpern mit Durchbrüchen erreichen](#rm-077) | Geometrie, Erkennung und Druckvorbereitung | Zielreihen an Körpern mit Durchbrüchen gegen den vorhandenen Rückfall messen |
| [RM-078 — Ladezeit generierter Beispielmodelle an der Orientierung messen](#rm-078) | Geometrie, Erkennung und Druckvorbereitung | Eulenprojekt ohne Fremdlast öffnen und teure Schritte zuordnen |
| [RM-080 — Restumfang der Trennen-Serie mit aktuellem Code abgleichen](#rm-080) | Geometrie, Erkennung und Druckvorbereitung | Übrige Trennplanung, geschützte Sichtflächen und Schaustück abschließen |
| [RM-086 — Achsenkonvention beim GLB-Import mit Migration klären](#rm-086) | Geometrie, Erkennung und Druckvorbereitung | GLB-Achsenkonvention mit Herkunft und Migration festlegen |
| [RM-087 — Aushöhlen mit wählbarer offener Seite planen](#rm-087) | Geometrie, Erkennung und Druckvorbereitung | Wählbare Öffnungsfläche am Puppenhaus-Fall umsetzen |
| [RM-097 — Verbleibende Kernbefunde des Reviews einzeln beheben](#rm-097) | Geometrie, Erkennung und Druckvorbereitung | Verbleibende Kernbefunde jeweils am Kunden- und Fehlerfall schließen |
| [RM-109 — Schichtanalyse der Rändelplatte gezielt beschleunigen](#rm-109) | Geometrie, Erkennung und Druckvorbereitung | Mindestbreitenprüfung mit gleichem Befund gezielt beschleunigen |
| [RM-127 — Wandstärke nach Änderungen am fertigen Modell prüfen](#rm-127) | Geometrie, Erkennung und Druckvorbereitung | Dünne Wände am Endzustand in beiden Änderungsreihenfolgen prüfen |
| [RM-128 — Bearbeitbarkeit erkannter Flächen entscheiden](#rm-128) | Geometrie, Erkennung und Druckvorbereitung | Nutzbaren Bearbeitungsumfang reiner erkannter Flächen entscheiden |
| [RM-132 — Freiformerkennung am Ein-Sekunden-Ziel messen](#rm-132) | Geometrie, Erkennung und Druckvorbereitung | Organische und mechanische 200.000-Dreiecke-Fälle gegen eine Sekunde messen |
| [RM-133 — Rückmeldung zur Volumenänderung beim Merkmaldrehen entscheiden](#rm-133) | Geometrie, Erkennung und Druckvorbereitung | Kundennutzen eines Hinweises zur korrekten Volumenänderung entscheiden |
| [RM-138 — Gespeicherten Bausteinstand beim Öffnen wählbar erhalten](#rm-138) | Geometrie, Erkennung und Druckvorbereitung | Wahl zwischen aktuellem und noch verfügbarem früherem Bausteinstand ermöglichen |
| [RM-139 — Geometrische Orientierungskandidaten aus der konvexen Hülle ableiten](#rm-139) | Geometrie, Erkennung und Druckvorbereitung | Hüllnormalen deterministisch erzeugen und Finalisten gegen vollständige Suche prüfen |
| [RM-140 — Exportbefunde vor dem Schreiben sichtbar machen](#rm-140) | Geometrie, Erkennung und Druckvorbereitung | Vorprüfung mit Passungen und endgültigen Wandstärken vor dem Dateischreiben anschließen |
| [RM-143 — Selbstdurchdringungen in der Netzfehlerkarte sichtbar markieren](#rm-143) | Geometrie, Erkennung und Druckvorbereitung | Markierung an einem reproduzierbaren durchdrungenen Körper anschließen |
| [RM-147 — Die acht beauftragten Konstruktionserweiterungen bauen](#rm-147) | Geometrie, Erkennung und Druckvorbereitung | Alle acht gebaut — offen bleiben das Anklicken einer Kante im Bild und fünf zugesagte Kundenwege |
| [RM-148 — Zahlenparameter gegen NaN und Unendlich sichern](#rm-148) | Geometrie, Erkennung und Druckvorbereitung | Endlichkeitsprüfung zentral in `registry.params._coerce` mit Regressionstest |
| [RM-070 — SpaceMouse auf macOS und Linux am echten Gerät abnehmen](#rm-070) | Bedienung und Darstellung | Mac-/Linux-Gerätelauf, Treiberwechselwirkung und große Szene abnehmen |
| [RM-074 — Verbleibenden Bildnachweis der Viewport-Serie abschließen](#rm-074) | Bedienung und Darstellung | Befundsprung und sichtbare Marke an einem echten Warnprojekt zeigen |
| [RM-079 — Zeilenlängen der Website über alle Sprachen prüfen](#rm-079) | Bedienung und Darstellung | Textbreiten in sechs Sprachen auf schmalen und breiten Fenstern prüfen |
| [RM-084 — Kundentexte gegen die vereinbarte Sprache prüfen](#rm-084) | Bedienung und Darstellung | Kundentexte systematisch prüfen und alle Sprachfassungen nachziehen |
| [RM-088 — Verständlichkeit für Laien im Regelwerk verankern](#rm-088) | Bedienung und Darstellung | Verständlichkeitsregel und begründete Ausnahmen entscheiden |
| [RM-090 — Serie zum Übergabestatus entscheiden](#rm-090) | Bedienung und Darstellung | Nächsten Umfang aus den fünf Vorschlägen des Produktkompasses entscheiden |
| [RM-101 — Elternlosen Handlungsknopf im Fensteraufbau zuordnen](#rm-101) | Bedienung und Darstellung | Vermuteten elternlosen Knopf am heutigen Fenster reproduzieren |
| [RM-102 — Datum im Wiederherstellungsdialog an die App-Sprache binden](#rm-102) | Bedienung und Darstellung | Sicherungsdatum an die gewählte App-Sprache binden |
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
| [RM-054 — Prompt-Grundlast mit dem aktuellen Werkzeugbestand messen](#rm-054) | KI und Generatoren | Prompt-Tokenzahl mit aktuellem Schema und festgehaltenem Modell nachmessen |
| [RM-069 — Verhaltensabnahme der kompakten Werkzeugschemata nachholen](#rm-069) | KI und Generatoren | Vergleichbare Suitequoten vor und nach der Schema-Verdichtung nachweisen |
| [RM-081 — Ollama-Laufzeit und verbleibende Optimierungen abnehmen](#rm-081) | KI und Generatoren | Warm-/Kaltstart, Antwortqualität und Schemakürzungen gemeinsam messen |
| [RM-144 — Orientierungsanalyse über MCP ohne blockiertes Hauptfenster ermöglichen](#rm-144) | KI und Generatoren | Gemeinsame Orientierungsanalyse an den fernbedienten Arbeiterweg anschließen |
| [RM-020 — Sicherung der eigenständigen Druckprojekte belegen](#rm-020) | Tests und Entwicklungswerkzeuge | Sicherungsweg entscheiden und Wiederherstellung belegen |
| [RM-025 — Unabhängige Sollwerte für geometrische Prüfungen absichern](#rm-025) | Tests und Entwicklungswerkzeuge | Geometrische Sollwerte aus unabhängiger Rechnung oder analytischen Größen belegen |
| [RM-043 — Gemeinsame Kopfzeilenfrist an alle HTTP-Leser anschließen](#rm-043) | Tests und Entwicklungswerkzeuge | Kopfzeilenfrist an die vier übrigen HTTP-Leser anschließen |
| [RM-098 — Restliche Regelwerk-Nachträge abgleichen](#rm-098) | Tests und Entwicklungswerkzeuge | Offene Regelbehauptungen mit tatsächlichen Prüfungen abgleichen |
| [RM-099 — Konzeptbestand und veraltete Verweise ordnen](#rm-099) | Tests und Entwicklungswerkzeuge | Konzeptindex und historische Verweise ohne Wissensverlust ordnen |
| [RM-100 — Sichtbares Terminalfenster aus dem Prozesstest vermeiden](#rm-100) | Tests und Entwicklungswerkzeuge | Windows-Testenkel ohne sichtbares Terminal bei gleicher Prozessprüfung starten |
| [RM-103 — Große Kernfunktionen nach konkretem Wartungsbedarf aufteilen](#rm-103) | Tests und Entwicklungswerkzeuge | Auswertung und weitere große Funktionen nach Wartungsbedarf priorisieren |
| [RM-106 — Plattformunterschiede der Projektdateien dem richtigen Ursprung zuordnen](#rm-106) | Tests und Entwicklungswerkzeuge | Archiv- und Inhaltshashes nach gleichem Erzeugerlauf vergleichen |
| [RM-110 — Doppelten Leser offener Dateihandles zusammenführen](#rm-110) | Tests und Entwicklungswerkzeuge | Gemeinsamen Handle-zu-Pfad-Leser mit allen Sicherheitsgegenproben extrahieren |
| [RM-113 — Besitzerprüfung der Tokendatei auf dem Windows-Runner belegen](#rm-113) | Tests und Entwicklungswerkzeuge | Besitz und ACL einer tatsächlich nutzereigenen Runner-Datei belegen |
| [RM-122 — Paralleles Einfügen in gemeinsame Dokumente absichern](#rm-122) | Tests und Entwicklungswerkzeuge | Atomare Indexergänzung unter Sperre mit konkurrierenden Schreibern absichern |
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
| [RM-149 — Zwei Funde aus dem Release-Lauf von 0.4.0 zuordnen](#rm-149) | Veröffentlichung, Betrieb und Vertrieb | Roten Vorwarnlauf und den Fehlalarm des Website-Abgleichs je einer Ursache zuordnen |
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

  **Vor dem Bau von 0.4.1 gehört die Variable zurück auf `notarized`** — zusammen mit der
  Reparatur oben. Sie steht in keinem Repository-Text, nur in den Einstellungen; wer sie
  vergisst, liefert eine zweite unsignierte Fassung aus, ohne dass ein Lauf rot wird.

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

- [ ] **RM-051 — Renderer und Grafiklaufzeit in Linux- und Mac-Paketen abnehmen.** Die 0.3.5-Pakete
  und expliziten wgpu-Bibliotheken sind gebaut; die alte Behauptung, seit 0.3.4 sei kein Mac-Bau
  gelaufen, ist überholt. Offen sind der tatsächliche Grafik-/Eingabeweg samt Vulkan beziehungsweise
  Metal und die Unix-Fenstergruppe: Die CI führt sie aktuell nur auf Windows aus, weil Linux und
  macOS konkrete Befunde zeigen. Abnahme je Plattform: sichtbares Modell, Auswahl/Navigation,
  Schließen, dokumentierte Treiber-/Paketumgebung und erfolgreiche vollständige Fenstergruppe ohne
  stilles Überspringen fehlender Adapter.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#was-der-gesamtreview-liegen-ließ-05092026).

<a id="rm-055"></a>

- [ ] **RM-055 — Neue Paketwerkzeuge im installierten Kundenpaket abnehmen.** Flatpak 0.3.5 ist
  gegen die eingetragene Laufzeit 26.08 gebaut und veröffentlicht; offen bleibt der reale Linux-Lauf
  mit Grafik, Qt, Dateizugriff und Offline-Start. Für Inno Setup 7 die tatsächlich benutzte
  Compilerfassung am Bauprotokoll belegen und Installieren, Aktualisieren sowie Deinstallieren auf
  einem fremden Windows prüfen. Abnahme mit Paket-/Compilerfassung und Feldprotokoll.

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

- [ ] **RM-117 — Öffentliche Downloadlinks vollständig in die Paketprüfung aufnehmen.** Die
  Veröffentlichungsprüfung um direkt auf den Sprachseiten versprochene Downloads erweitern,
  insbesondere AppImage. Abnahme: jedes verlinkte aktuelle Paket wird nach Upload auf vollständige
  Bytes/Prüfsumme geprüft, auch ohne Eintrag im Update-Manifest.

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
  `Operation.matches` und Speichern/Wiederöffnen sind gebaut. Noch fehlt ein geometrisch echter
  Fall, in dem ein altes Merkmal zwei gleichwertige Nachfolger bekommt. Abnahme über `evaluate`:
  jede nötige Entscheidung einmal, erneute Auswertung und Wiederöffnen ohne dieselbe Rückfrage;
  Abbruch liefert einen Befund. Die historische 99→7→0-Reihe nur mit dem damaligen 52-Teile-Projekt
  vergleichen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#das-fundament-der-wahrnehmung-22082026).

<a id="rm-039"></a>

- [ ] **RM-039 — Fehlende Schnittflächen an offenen Netzen verständlich erklären.** `split_at_plane`
  meldet weiterhin nur, dass die Schnittflächen nicht geschlossen werden konnten. Bei offenen
  Eingangsnetzen den Zusammenhang benennen und eine passende Reparaturhandlung anbieten. Abnahme:
  offenes Netz erzeugt den verständlichen Befund mit Rückweg, ein sauber geschlossenes Netz bleibt
  unverändert.

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

- [ ] **RM-080 — Restumfang der Trennen-Serie mit aktuellem Code abgleichen.** Die verbleibende
  Trennen-Serie abschließen: schräge automatische Ebenen, Symmetrie, globale Schnittfolgen sowie die
  vollständige Bedienung und Speicherung geschützter Sichtflächen; anschließend das Schaustück
  ergänzen. Abnahme je Teil: Korpus, Determinismus, Abbruch und nachvollziehbarer Kundenweg. Bereits
  gebaute Stützbewertung und automatische Verbinder nicht erneut beauftragen.

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

- [ ] **RM-097 — Verbleibende Kernbefunde des Reviews einzeln beheben.** Die verbleibenden Kern- und
  Übergabetexte aus dem Review einzeln schließen: aussagekräftiger Lesefehler bei verknüpften
  Quellen, unterscheidbare Deckel-/Prüfstücknamen, gemeinsame Zerfallsprüfung, profilgebundene
  Geometrie-/Schichtschwellen, einmalige Ermittlung von support_on_model und konsistente Bezeichnung
  des Druck-/Slicer-Wegs. Abnahme je Änderung am betroffenen Kunden- und Fehlerfall.

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

- [ ] **RM-128 — Bearbeitbarkeit erkannter Flächen entscheiden.** Für erkannte reine Flächen den
  nutzbaren Bearbeitungsumfang festlegen und die Merkmalsliste daran ausrichten. Abnahme:
  Besenhalter und Schiffsmodelle zeigen unmittelbar verständliche, erreichbare Handlungen oder
  begründete Anzeigegrenzen; den separat geführten Verrundungsradius nicht doppelt planen.

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

- [ ] **RM-139 — Geometrische Orientierungskandidaten aus der konvexen Hülle ableiten.** Die Auswahl aus Hüllflächennormalen nach Bauplan §28.2 ist noch nicht eingelöst:
  `geom/orient.py` und `slice/orientation.py` verwenden Flächen, Achsen und Zufallsrichtungen.
  Hüllnormalen nach Fläche mit Achsen und großen Modellflächen deterministisch verbinden.
  Abnahme: gleiche Eingaben ergeben gleiche Kandidaten und Lage; Vorfilter und Finalisten werden
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

  **Offen bleibt aus E4 die Bedienung im Bild:** Eine Kante lässt sich noch nicht
  **anklicken**; der Renderer pickt Flächen und Merkmale, keine Kanten, und das ist ein
  eigener Bau.

  Daneben stehen aus derselben Liste noch fünf zugesagte Kundenwege offen: der parametrische
  Lochkreis mit gleichem Vertrag in Dialog, Kommandozeile und Agent, die physische
  Kennzeichnung der Varianten, RM-138, RM-087 und RM-127/RM-140.

<a id="rm-148"></a>

- [ ] **RM-148 — Zahlenparameter gegen NaN und Unendlich sichern.** `registry.params._coerce`
  prüft einen Fließkommawert heute nur gegen seine Grenzen, und ein Grenzvergleich mit NaN ist
  immer falsch — der Wert läuft durch. Die Druckeinstellungen haben ihren eigenen Riegel
  bekommen (08.09.2026: „NaN, Unendlich und numerischer Überlauf gelangen weder in
  Einstellungen noch als rohe Konvertierungsfehler zum Nutzer"), die allgemeine
  Parameterannahme nicht. Die Korrektur war im Codex-Fenster vorbereitet und ist mit dessen
  Limit liegengeblieben. Abnahme: eine zentrale Endlichkeitsprüfung über `NUMBER_KINDS`, ein
  Regressionstest mit `nan`, `inf` und `-inf` je Zahlenart, und die Ablehnung trägt einen
  Handlungsvorschlag (Regel 17).

## Bedienung und Darstellung

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

- [ ] **RM-101 — Elternlosen Handlungsknopf im Fensteraufbau zuordnen.** Den vermuteten elternlosen
  Handlungsknopf beim Modellladen am aktuellen Fenster reproduzieren und seine Herkunft bestimmen.
  Abnahme: kein fremdes Top-Level-Fenster, Hauptfenster behält Fokus und der Befundknopf
  funktioniert nach Einhängen ins Layout. Den alten Verdacht nicht als bestätigte Ursache behandeln.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-102"></a>

- [ ] **RM-102 — Datum im Wiederherstellungsdialog an die App-Sprache binden.** Das Datum älterer
  Sicherungen im Wiederherstellungsdialog mit der aktuellen Anwendungssprache formatieren. Abnahme:
  deutsche und englische Anzeige folgt der gewählten Sprache, relative Zeitangaben und Zeitzone
  bleiben korrekt.

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

- [ ] **RM-054 — Prompt-Grundlast mit dem aktuellen Werkzeugbestand messen.** `PROMPT_TOOL_COUNT`
  ist inzwischen 114; `PROMPT_TOKENS` trägt weiter 22.856 aus der Messung vom 03.09.2026. Mit
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

- [ ] **RM-043 — Gemeinsame Kopfzeilenfrist an alle HTTP-Leser anschließen.** Den vorhandenen
  `DeadlineResponse` auch an die übrigen vier Aufrufwege anschließen. Abnahme: langsam eintreffende
  Statuszeile und Kopfzeilen können die Gesamtfrist auf keinem dieser Wege immer wieder verlängern.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-abnahme-des-gesamt-reviews-06092026).

<a id="rm-098"></a>

- [ ] **RM-098 — Restliche Regelwerk-Nachträge abgleichen.** Die noch offenen Regelwerk-Nachträge
  gezielt entscheiden beziehungsweise prüfen: testbare Reichweite harter Regeln, Abgrenzung von
  Arbeitsverfahren und Fallgeschichte, passende Regeln für Auslieferungsdateien sowie gültige
  Regelnummern und paths-Muster. Auch den Geltungsbereich der pauschalen 0,01-mm-Überlappung in
  `rules.toml` gegen konkrete Boolesche Fälle prüfen; eine inhaltliche Änderung braucht Version
  und vergleichbare Modell-Suiteläufe nach Bauplan §39. Abnahme: jede Prüfbehauptung hat einen passenden
  Wächter; keine doppelte Suite-Anleitung. Die zweistufige Testfahrweise ist bereits umgesetzt.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-099"></a>

- [ ] **RM-099 — Konzeptbestand und veraltete Verweise ordnen.** Die überholten Konzepte und
  Sitzungsentwürfe geordnet archivieren und den Konzeptindex auf heutige Entscheidungen ausrichten.
  Abnahme: alle Verweise gültig, historische Begründungen erhalten, Weg-3-Lizenzentscheidung
  auffindbar und Roadmap-Verweise über stabile Anker; keine ungeprüfte feste Zahl zu archivieren.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-100"></a>

- [ ] **RM-100 — Sichtbares Terminalfenster aus dem Prozesstest vermeiden.** Den losgelösten
  Windows-Testenkel unter Windows Terminal ohne sichtbares Fehlerfenster ausführen und den echten
  Startweg gegenprüfen. Abnahme: Prozessbaum wird zuverlässig geschlossen, kein neues
  Terminalfenster erscheint und die Anwendung verhält sich ebenso.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#review-vor-der-demo-030-02092026).

<a id="rm-103"></a>

- [ ] **RM-103 — Große Kernfunktionen nach konkretem Wartungsbedarf aufteilen.** Die großen
  Kernfunktionen anhand ihres heutigen Aufbaus priorisieren; zuerst die Verantwortlichkeiten der
  Auswertung prüfen. Nur begründete Aufteilungen durchführen. Abnahme: gleiche Geometrie, IDs,
  Befunde und Laufzeit vor/nach dem Umbau sowie die vier Hauptwege; alte Zeilenzahlen nicht als
  aktuellen Befund weiterführen.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#architektur-durchsicht-02092026).

<a id="rm-106"></a>

- [ ] **RM-106 — Plattformunterschiede der Projektdateien dem richtigen Ursprung zuordnen.** Die
  plattformabhängigen Bytes erzeugter Beispielprojekte auf Inhalt und Kompression eingrenzen: nach
  demselben Erzeugerlauf Archivhash und normalisierte Hashes aller entpackten Dateien vergleichen.
  Abnahme: belegte Ursache und dokumentierter Reproduzierbarkeitsvertrag; ausgelieferte Rechtebelege
  bleiben an die eingecheckten Originalbytes gebunden.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-110"></a>

- [ ] **RM-110 — Doppelten Leser offener Dateihandles zusammenführen.** Den identischen
  plattformspezifischen Handle-zu-Pfad-Weg zusammenführen. Abnahme: verknüpfte Quellen und
  Update-Deskriptoren halten dieselben Sicherheitsgrenzen auf Windows, Linux und macOS; F_GETPATH
  und die bisherigen Gegenproben bleiben erhalten.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-113"></a>

- [ ] **RM-113 — Besitzerprüfung der Tokendatei auf dem Windows-Runner belegen.** Den Besitzer einer
  frisch angelegten privaten Tokendatei auf dem Windows-Runner ermitteln und die Prüfung mit einer
  tatsächlich nutzereigenen Datei fahren. Abnahme: SID und ACL dokumentiert, Test ohne bedingten
  Skip grün; eine breitere Besitzfreigabe nur nach Sicherheitsprüfung.

  [Bisheriger Befund](ROADMAP-ARCHIV.md#die-ci-kam-zum-ersten-mal-bis-zum-ende-02092026).

<a id="rm-122"></a>

- [ ] **RM-122 — Paralleles Einfügen in gemeinsame Dokumente absichern.** Ein kleines Werkzeug für
  atomare Einzelzeilenänderungen am gemeinsamen Projekt-Memory-Index bauen: Sperre, erneutes Lesen
  unter Sperre und Kontrolle unveränderter übriger Zeilen. Abnahme: zwei konkurrierende Ergänzungen
  bleiben beide erhalten und test_directory_docs erkennt weiterhin fehlende/beidseitig verwaiste
  Verweise.

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

  **Der Website-Abgleich meldet sechs Dateien, die nicht abweichen.** `upload_website.py
  --fehlend` führt nach jedem Lauf dieselben sechs `index.html` erneut als „fehlen oder weichen
  ab", auch unmittelbar nach ihrem eigenen erfolgreichen Upload. Gegengemessen: Die Startseite
  vom Server ist **byte-identisch** mit der lokalen (63 639 Bytes, gleicher Inhalt, nennt
  0.4.0). Der Vergleich läuft über die Größe aus `mlsd`; die anderen 501 Dateien sind danach
  ruhig. Ein Abgleich, der etwas als offen meldet, das erledigt ist, kostet beim nächsten
  Release die Aufmerksamkeit, die einem echten Rest gehört. Abnahme: Ursache benannt, danach
  meldet ein zweiter Lauf null.

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
