# Sicherheits- und Produktvorfälle — interner Ablauf

Diese Datei ist die **eine** Arbeitsanweisung für Schwachstellen,
Datenschutzverletzungen und Produktsicherheitsvorfälle in Solidon3D.
Verantwortlich ist Robert Schneider, RS Digital. Eingangskanal ist
`support@solidon3d.de`; die öffentlich zugesagte Mindestunterstützung für
Solidon 1.x endet am 31. Oktober 2031. Drei Rechtsuhren laufen gegebenenfalls
parallel und werden unter derselben Vorgangskennung nachgewiesen.

## Gemeinsamer Eingang für CRA, DSGVO und Produktsicherheit

Jede Meldung erhält `INC-JJJJ-NNN`. Die unveränderte Eingangsnachricht, die
früheste Kenntniszeit, Meldeperson, Produkt/Version, betroffene Plattform,
Länder, Komponenten/SBOM, mögliche Ausnutzung, personenbezogene Daten,
Personen-/Sachschaden, weitere Betroffene und Sofortmaßnahmen werden einmal
erfasst. Zugangsdaten, unnötige Projektdateien und besondere Daten werden
nicht vorsorglich angefordert.

Die Eingangstriage beantwortet mit Ja/Nein/Unklar und Begründung:

1. aktiv ausgenutzte Schwachstelle oder schwerer Sicherheitsvorfall (CRA),
2. Verletzung des Schutzes personenbezogener Daten (DSGVO),
3. Unfall, gefährliches Produkt oder mögliches ernstes Risiko (GPSR),
4. Sanktions-/Exportkontrolltreffer,
5. Strafverfolgung, Versicherer, Auftragsverarbeiter oder weitere Behörde
   einzubeziehen.

„Unklar“ stoppt keine Uhr. Primary eröffnet sofort die betroffenen Teilpfade,
Secondary kontrolliert Zeitnull, Fristen, Empfänger und Belege im
Vier-Augen-Prinzip. Eine spätere Neueinstufung bleibt in derselben
Vorgangskennung nachvollziehbar.

## Drei parallele Rechtsuhren

### CRA-Uhr

Für aktiv ausgenutzte Schwachstellen und schwere Sicherheitsvorfälle gelten
die 24-/72-Stunden- und Abschlussfristen im Abschnitt „Verbindliche CRA-Uhr“.
Die externen Bereitschaftspunkte vor dem 11. September 2026 bleiben
Release-Blocker.

### DSGVO-Uhr

Bei einer Verletzung des Schutzes personenbezogener Daten wird ab Kenntnis
unverzüglich das Risiko für Rechte und Freiheiten bewertet. Ist ein Risiko
nicht unwahrscheinlich, wird die zuständige Aufsichtsbehörde möglichst binnen
**72 Stunden** benachrichtigt; eine spätere Meldung enthält die Begründung der
Verzögerung. Bei voraussichtlich hohem Risiko werden Betroffene unverzüglich
in klarer Sprache informiert, soweit keine gesetzliche Ausnahme greift.

Die Akte enthält Art und Umfang, Kategorien/ungefähre Zahl Betroffener und
Datensätze, Folgen, Maßnahmen, Datenschutzkontakt, Behörden-/Betroffenenmeldung
oder die begründete Nichtmeldung. Auftragsverarbeiter werden nach dem
vertraglichen Weg einbezogen. Jede Datenschutzverletzung wird dokumentiert,
auch wenn keine externe Meldung erfolgt.

### Produktsicherheits-Uhr

Bei Unfall, gefährlichem Produkt oder möglichem ernsten Risiko werden
Bereitstellung und betroffene Fassung sofort eingegrenzt. Unfall, Risiko,
Korrektur, Rücknahme oder Rückruf werden nach `PRODUCT-SAFETY.md` entschieden.
Die zuständige Marktüberwachungsbehörde und das **Safety Business Gateway**
werden ohne unangemessene Verzögerung einbezogen, wenn die gesetzlichen
Voraussetzungen vorliegen. Nutzer erhalten verständliche Risikoinformation
und eine wirksame Abhilfe; deren Reichweite und Erfolg werden nachverfolgt.

Ein einzelner Vorgang kann alle drei Uhren auslösen, zum Beispiel eine
ausgenutzte Schwachstelle, die Kontaktdaten offenlegt und zugleich ein
unsicheres Druckergebnis verursacht. Dann werden CRA-, DSGVO- und
Produktsicherheitsmeldung getrennt adressiert, aber unter derselben
Vorgangskennung, Zeitlinie und Beweissammlung geführt.

## Warum dieser Zeitraum gilt

Der Verkaufsstart von Solidon 1 ist der 1. November 2026. Fünf volle Jahre
führen zum 31. Oktober 2031. Das ist die Untergrenze, nicht automatisch das
späteste rechtlich erforderliche Datum: Vor jeder später in Verkehr gebrachten
1.x-Fassung wird geprüft, ob erwartete Nutzungsdauer oder Rechtslage eine
Verlängerung verlangen. Der öffentlich genannte Termin wird nie nach vorn
verschoben.

## Release-Blocker vor dem 11. September 2026

Der Meldeweg ist **noch nicht betriebsbereit**, solange einer der folgenden
externen Punkte offen ist. In diesem Zustand darf keine Verkaufs- oder
Sicherheitsfassung freigegeben werden; ein Dokument ersetzt weder Zugang noch
Bereitschaft.

- [ ] Für Robert Schneider ist ein funktionsfähiges **EU-Login** angelegt und
  der Zugang zur ENISA Single Reporting Platform einmal vollständig geprüft.
- [ ] In der Plattform ist Robert Schneider als **Primary** zugeordnet; eine
  von Robert namentlich bestimmte, erreichbare Person ist als **Secondary**
  hinterlegt und hat ihren Zugang selbst getestet.
- [ ] Das für Deutschland zuständige **CSIRT** ist in der Plattform ausgewählt;
  die Zuordnung und der sichtbare Plattformstatus sind im privaten
  Betriebsnachweis festgehalten.
- [ ] `support@solidon3d.de` alarmiert **24 Stunden an sieben Tagen** per
  Push-Anruf oder gleichwertigem lautem Alarm sowohl Primary als auch
  Secondary. Bleibt die Annahme 15 Minuten aus, wird automatisch an die jeweils
  andere Person eskaliert. Eine bloße werktägliche Postfachprüfung genügt nicht.
- [ ] Ein Probelauf außerhalb der Arbeitszeit belegt: Testmail → Alarm an beide
  Personen in höchstens 15 Minuten → Anmeldung → Auswahl des deutschen CSIRT →
  vollständig ausgefüllte Frühwarnung bis unmittelbar vor dem Absenden. Datum,
  Zeiten und Ergebnis liegen im privaten Betriebsnachweis; es wird keine
  fingierte Meldung abgesendet.

Diese Häkchen enthalten keine Zugangsdaten. Primary und Secondary wiederholen
den Bereitschaftstest monatlich sowie vor jeder Verkaufsfassung. Fällt Zugang,
Alarmierung oder Vertretung aus, ist die Release-Sperre sofort wieder aktiv.

## Eingang und Zeitnull

1. Nachricht unverändert sichern und den gemeinsamen Vorgang
   `INC-JJJJ-NNN` anlegen.
2. Zeitnull ist der früheste Zeitpunkt, zu dem RS Digital hinreichend sichere
   Kenntnis von einer aktiv ausgenutzten Schwachstelle oder einem schweren
   Sicherheitsvorfall hat — nicht der Zeitpunkt, zu dem die technische
   Untersuchung abgeschlossen ist.
3. Produkt, Version, Plattform, Quelle, Auswirkung, bekannte Ausnutzung,
   personenbezogene Daten und betroffene Komponenten aus der SBOM festhalten.
4. Eingang spätestens innerhalb von zwei Arbeitstagen bestätigen. Keine
   Projektdatei oder geheimen Zugangsdaten anfordern, wenn ein kleinerer Beleg
   genügt.
5. Beweise nur lesend sichern: Nachricht, Protokolle, Hashes, betroffene
   Pakete und die zum ausgelieferten Zielpaket gehörende
   `Solidon3D.cdx.json`.

## Einstufung

- **Aktiv ausgenutzte Schwachstelle:** belastbarer Hinweis, dass ein böswilliger
  Akteur die Schwachstelle bereits ausnutzt.
- **Schwerer Sicherheitsvorfall:** Beeinträchtigung von Verfügbarkeit,
  Authentizität, Integrität oder Vertraulichkeit, die zu einer schweren
  Betriebsstörung oder erheblichen materiellen beziehungsweise immateriellen
  Schäden führt oder führen kann.
- **Sonstige Schwachstelle:** koordinierte Bearbeitung und Abhilfe, aber keine
  CRA-Sofortmeldung allein aufgrund des Eingangs.

Unsicherheit verkürzt keine Frist. Bei begründetem Verdacht werden parallel
Auswirkung eingegrenzt, Abhilfe vorbereitet und der Meldeweg geprüft.

## Verbindliche CRA-Uhr

Die aktuelle Oberfläche und Anleitung der ENISA Single Reporting Platform
werden zu Beginn jedes meldepflichtigen Vorgangs über
<https://www.enisa.europa.eu/topics/product-security/single-reporting-platform-srp>
geprüft. Zugangsdaten oder eine Zieladresse werden nicht aus dieser Datei
erraten.

### Aktiv ausgenutzte Schwachstelle

1. **Binnen 24 Stunden ab Zeitnull:** Frühwarnung über die ENISA-Plattform.
2. **Binnen 72 Stunden ab Zeitnull:** Schwachstellenmeldung mit allgemeiner
   Produktbeschreibung, Art der Ausnutzung und verfügbarer Abhilfe oder
   Risikominderung.
3. **Spätestens 14 Tage nachdem eine Korrektur oder Risikominderung verfügbar
   ist:** Abschlussbericht mit Schwere, Auswirkung, Ursache, Ausnutzung,
   Korrektur und gegebenenfalls betroffenen Mitgliedstaaten.

### Schwerer Sicherheitsvorfall

1. **Binnen 24 Stunden ab Zeitnull:** Frühwarnung über die ENISA-Plattform.
2. **Binnen 72 Stunden ab Zeitnull:** Vorfallsmeldung mit erster Bewertung,
   Schwere, Auswirkung und bekannten Kompromittierungsmerkmalen.
3. **Binnen eines Monats nach der 72-Stunden-Meldung:** Abschlussbericht mit
   Verlauf, Ursache, Abhilfe und verbleibendem Risiko.

Die Fristen laufen unabhängig voneinander. Der 14-Tage-Abschluss gehört zur
ausgenutzten Schwachstelle; der Monatsabschluss gehört zum schweren Vorfall.
Trifft beides zu, werden beide Pfade erfüllt und im Vorgang getrennt
nachgewiesen.

## Abhilfe und Kommunikation

1. Betroffene Komponenten über SBOM und Paketinhalt bestimmen; alle drei
   Zielplattformen prüfen.
2. Reproduzierenden Test vor der Korrektur anlegen, dann Korrektur, vollständiges
   Tor und echten Kundenbau ausführen.
3. Paket signieren, Prüfsumme und SBOM sichern, Update-Hinweis veröffentlichen.
4. Betroffene Nutzer ohne unangemessene Verzögerung über Risiko, verfügbare
   Abhilfe und sichere Aktualisierung informieren. Keine ausnutzbaren Details
   vor der Abhilfe veröffentlichen.
5. Meldende Person über Status und geplanten Offenlegungszeitpunkt informieren.
6. Nach Abschluss Ursache, Reichweite, Zeitlinie, Entscheidungen und
   Vorbeugung dokumentieren; keine Geheimnisse oder personenbezogenen Daten in
   öffentliche Berichte übernehmen.

## Bereitschaft

- Alarmierung des Support-Postfachs rund um die Uhr aktiv halten; Primary und
  Secondary bestätigen oder eskalieren jeden Sicherheitsalarm sofort.
- ENISA-Anleitung und Kontaktdaten vor jedem Verkaufsrelease gegenlesen.
- EU-Login, Rollen, deutsches CSIRT und den dokumentierten Probelauf vor jedem
  Verkaufsrelease gegen den privaten Betriebsnachweis prüfen.
- SBOM aus jedem Zielpaket archivieren und für die gesamte Unterstützungsdauer
  auffindbar halten.
- Diesen Ablauf nach einem Vorfall und mindestens vor jeder Hauptversion
  überprüfen.
