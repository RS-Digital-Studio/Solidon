# Produktsicherheitsakte — Solidon

Stand: 31. August 2026 · Aktenfassung 1.0

**Freigabestatus: GESPERRT.** Diese Akte ist vor jeder öffentlichen Fassung
gegen das tatsächliche Kundenpaket und die zugehörige Versionsakte zu prüfen.
Eine Freigabe setzt ausgefüllte Nachweise, benannte Stellvertretung und die
fachliche Prüfung der Einordnung nach der Verordnung (EU) 2023/988 voraus.

Die Akte ist ein Risikomanagement- und Rückverfolgbarkeitsnachweis. Sie
behauptet kein besonderes Zertifizierungs- oder Konformitätsbewertungsverfahren
nach der GPSR und verleiht weder Solidon noch einer Exportdatei eine
CE-Kennzeichnung. Die fachliche Prüfung soll die Anwendbarkeit und den
konkreten Pflichtenumfang bestätigen, nicht eine gesetzlich nicht vorgesehene
Zertifizierung erfinden.

## Produktidentifikation und Zweckbestimmung

- Produkt: Solidon3D, kurz Solidon; Desktopsoftware für Windows, macOS und
  Linux.
- Hersteller und Verantwortlicher: Robert Schneider, RS Digital,
  Aufbaustraße 10, 96049 Bamberg, Deutschland.
- Gegenstand: allgemeines Werkzeug zum Konstruieren, Bearbeiten, Prüfen und
  Exportieren druckbarer 3D-Modelle.
- Zielgruppen: Maker, private und gewerbliche Anwender einschließlich Menschen
  ohne CAD-Vorkenntnisse.
- Vertriebsmodell: lokale Einmalkauflizenz ohne Pflichtkonto und ohne
  Abonnement; die Demo 0.x ist unentgeltlich.
- Nicht umfasst: medizinische oder dentale Zweckbestimmung, klinische
  Entscheidung, patientenbezogener Arbeitsablauf, Auslegung oder Freigabe
  sicherheitskritischer Bauteile, eigener G-Code-Slicer oder Zusage der Eignung
  für einen konkreten Sicherheitszweck.

„Druckbar“ bezeichnet nur die geometrische und drucktechnische Eignung zur
weiteren Verarbeitung anhand der gewählten Prüfparameter. Es ist keine Aussage
über Tragfähigkeit, Lebensmittelechtheit, medizinische Eignung, elektrische
Sicherheit, Gas- oder Druckfestigkeit, Schutzwirkung oder die Konformität des
gedruckten Gegenstands. Medizin, Fahrzeuge, Luft- und Raumfahrt,
Schutzvorrichtungen einschließlich persönlicher Schutzausrüstung,
Gas-/Druckanwendungen, elektrische Sicherheit und tragende Konstruktionen
liegen außerhalb der Zweckbestimmung.

Die Herkunft wird je Inhalt als Nutzerinhalt, Agentenausgabe oder mitgelieferter
Inhalt nachvollziehbar gehalten. Lokal importierte Bausteindateien bewahren
Herkunft, Autor und Lizenz; sie werden nicht von RS Digital gehostet oder
freigegeben. Für mitgelieferte Vorlagen und Bausteine führt RS Digital einen
eigenen Qualitäts- und Rechtenachweis. Eine Datei oder ein einzelnes STL erhält
durch Export, Prüfbericht oder Bezeichnung als „druckbar“ keine CE-Kennzeichnung
und keine Sicherheitszertifizierung.

Bringt ein Nutzer einen gedruckten Gegenstand im eigenen Namen auf den Markt,
muss er seine konkrete Hersteller- oder sonstige Wirtschaftsakteursrolle und
die Produktsicherheit des Gegenstands selbst bestimmen und erfüllen. Die bloße
Verwendung von Solidon3D macht RS Digital nicht automatisch zum Hersteller
jedes späteren Ausdrucks. Davon getrennt bleiben die gesetzlichen Pflichten von
RS Digital für die Software, mitgelieferte digitale Konstruktionsunterlagen und
eigene Produkt- oder Sicherheitszusagen bestehen.

Die Verwendung durch ein Unternehmen oder in einer regulierten Branche ändert
die Zweckbestimmung nicht. RS Digital wirbt insbesondere nicht mit
OP-Schablonen, Implantologie, Medizinprodukteignung oder klinischer
Genauigkeit. Eine solche Funktion oder Aussage ist eine neue
Konformitätsentscheidung und sperrt die Veröffentlichung bis zur gesonderten
Prüfung.

## Version und Rückverfolgbarkeit

Für jede öffentlich bereitgestellte Fassung enthält die private Versionsakte:

1. Versionsnummer, Build-Zeit, Commit, Plattform und Paket-Hash,
2. SBOM, Lizenzakte, verwendete Material-/Druckerprofile und Formatversion,
3. veröffentlichte Anleitung, Warnungen und Rechtstexte je Sprache,
4. bekannte Fehler, Sicherheitsbefunde und verbleibende Risiken,
5. Freigabeverantwortlichen, Datum, Prüfergebnisse und Vertriebsgebiete,
6. Korrekturen, Rücknahmen, Beschwerden und zugehörige Vorgangskennungen.

Die Akte wird mindestens zehn Jahre ab dem letzten Bereitstellen der jeweiligen
Produktfassung aufbewahrt. Projekt- oder Kundendaten gehören nicht ohne
eigenständigen Zweck und Rechtsgrund in diese Akte.

## Vorhersehbare Gefährdungen

| Gefahr | Vorhersehbare Ursache | Mögliche Folge | Beherrschung und Nachweis |
|---|---|---|---|
| Falsches Maß oder falsche Einheit | Import, Profil, Rundung, Bedienfehler | unpassendes oder mechanisch unsicheres Teil | Millimeter/doppelte Genauigkeit, Maßprüfung, sichtbare Einheit, Referenzkörper, Geometrietests |
| Nicht druckbare oder beschädigte Geometrie | offene Netze, Boolescher Fehler, Selbstdurchdringung | Druckabbruch oder unerwartete Form | Wasserdichtheits-/Komponentenprüfung, Rückfallkette, Prüfbericht, Handlungsvorschlag |
| Unzureichende Wand, Passung oder Verbindung | Materialannahme, falsches Profil, ungeprüfte Last | Bruch, Lösen oder Verklemmen | Materialprofil statt Streuzahl, Passungsprüfung, Warnung vor realem Probedruck |
| Falsche Orientierung oder Stützannahme | Analysegrenze, Nutzer übernimmt Vorschlag ungeprüft | schlechter Druck, Ablösung, Kollision | Herkunft der Kennzahl, keine G-Code-Zusage, sichtbare Empfehlung statt Freigabe |
| Fehlerhafte fremde Datei oder Rezept | manipulierte, übergroße oder fremde Eingabe | Ressourcenverbrauch, falsches Ergebnis | Größen-/Komplexitätsgrenzen, keine Codeausführung, Provenienz, reproduzierbare Ops |
| Fehlgeleitete KI-Ausgabe | Modell rät, Prompt-Injection, unvollständiger Kontext | ungeeignete Konstruktion oder falsche Sicherheitserwartung | KI-Offenlegung, eine rücknehmbare Transaktion, Prüfungen nach Ops, Mehrdeutigkeit hält an |
| Veraltete oder kompromittierte Fassung | fehlendes Update, Lieferkettenfehler | bekannte Fehlfunktion oder Angriff | signierte Updates, SBOM, Sicherheitszeitraum, Incident- und Rückrufverfahren |
| Zweckentfremdung in Medizin/Sicherheit | Nutzer oder Vertrieb stellt regulierte Eignung her | Personen- oder Sachschaden | klare allgemeine Zweckbestimmung, keine entsprechenden Claims/Funktionen, Eskalationssperre |
| Unklare Herkunft oder Fremdrechte | importierte Datei oder Agentenausgabe wird wie mitgelieferter Inhalt behandelt | Rechtsverletzung oder falsches Vertrauen in eine Freigabe | sichtbare Provenienz, Lizenzangaben reisen mit, getrennter Qualitätsnachweis für mitgelieferte Inhalte |

Jede Gefährdung wird je Fassung mit Schwere 1–5 und Wahrscheinlichkeit 1–5
bewertet. Ab 12 Punkten oder bei möglichem schweren Personenschaden ist eine
schriftliche Freigabeentscheidung mit zusätzlicher Schutzmaßnahme nötig. Ein
Restwert wird nicht durch einen Haftungsausschluss „behoben“.

## Beschwerden, Unfälle und Korrekturen

Jeder Eingang erhält eine gemeinsame Vorgangskennung und wird nach
`SECURITY-INCIDENT.md` triagiert. Produktsicherheitsfelder sind mindestens:
Produkt/Version, betroffene Datei oder Funktion, Nutzungszweck, Drucker,
Material, behaupteter Schaden, Land, Zeitpunkt, Schwere, weitere Betroffene,
Beweissicherung und bereits getroffene Maßnahme.

Bei einem Unfall oder möglichem ernsten Risiko wird unverzüglich geprüft:

- weitere Bereitstellung anhalten,
- reproduzieren und betroffene Fassungen bestimmen,
- Nutzer warnen und sichere Abhilfe nennen,
- Korrektur, Rücknahme oder Rückruf entscheiden,
- zuständige Marktüberwachungsbehörde und das Safety Business Gateway
  einbeziehen,
- Versicherer und qualifizierte Rechtsberatung einschalten,
- Wirksamkeit der Maßnahme nachverfolgen.

Die Verantwortliche Stelle dokumentiert auch die Entscheidung, warum ein
Vorgang nicht meldepflichtig war. Schweigen oder eine fehlende eindeutige
Klassifizierung schließt den Vorgang nicht.

## Freigabekriterien

Vor einer öffentlichen Verkaufsfassung müssen mindestens belegt sein:

- [ ] dokumentierte und fachlich geprüfte GPSR-Anwendbarkeitsentscheidung samt
      konkretem Pflichtenumfang; keine unbelegte Zertifizierungsbehauptung,
- [ ] vollständige Risikobewertung der konkreten Fassung,
- [ ] Warnungen und Zweckbestimmung in allen ausgelieferten Sprachen,
- [ ] geprüfter Beschwerde-, Unfall-, Korrektur- und Rückrufablauf,
- [ ] Zugang und Rollen für das Safety Business Gateway,
- [ ] Verantwortlicher und erreichbare Stellvertretung,
- [ ] Produkthaftpflicht und Deckungsumfang geprüft,
- [ ] Versionsakte, Kundenpakete, Hashes, SBOM und Anleitung archiviert.
- [ ] CRA-Klassifizierung, Updatezeitraum und Schwachstellenbehandlung für die
      konkrete Fassung dokumentiert und fachlich bestätigt,
- [ ] Qualitäts- und Rechteakte aller mitgelieferten Vorlagen und Bausteine
      vollständig; keine CE- oder Sicherheitszusage je Exportdatei,

Solange ein Punkt offen ist, bleibt die Verkaufsfreigabe gesperrt. Die
kostenlose Demo wird wegen ihrer bereits erfolgten öffentlichen Verbreitung
gesondert bewertet; „kostenlos“ ersetzt keine Produktsicherheitsprüfung.

## Rechtsgrundlagen und Wiedervorlage

Arbeitsgrundlage sind insbesondere die Verordnung (EU) 2023/988, die
Produktsicherheitsinformationen der EU-Kommission und das deutsche
Produktsicherheitsrecht. Zusätzlich wird die Umsetzung der Richtlinie (EU)
2024/2853 für Produkte, die nach dem 8. Dezember 2026, also ab 9. Dezember
2026, in Verkehr gebracht oder in Betrieb genommen werden, vor diesem
Stichtag erneut geprüft. Die Richtlinie
erfasst Software und digitale Konstruktionsunterlagen ausdrücklich; maßgeblich
bleibt ihre Umsetzung in deutsches Recht.

Wiedervorlage: vor jeder öffentlichen Fassung, nach jedem Unfall oder Rückruf,
bei neuer Zielgruppe/Funktion und spätestens jährlich.
