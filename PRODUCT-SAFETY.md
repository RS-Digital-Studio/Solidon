# Produktsicherheitsakte — Solidon

Stand: 31. August 2026 · Aktenfassung 1.0

**Freigabestatus: GESPERRT.** Diese Akte ist vor jeder öffentlichen Fassung
gegen das tatsächliche Kundenpaket und die zugehörige Versionsakte zu prüfen.
Eine Freigabe setzt ausgefüllte Nachweise, benannte Stellvertretung und die
fachliche Prüfung der Einordnung nach der Verordnung (EU) 2023/988 voraus.

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
  Entscheidung, patientenbezogener Arbeitsablauf, Freigabe eines Druckteils,
  eigener G-Code-Slicer oder Zusage der Eignung für einen konkreten
  Sicherheitszweck.

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

- [ ] fachlich bestätigte Anwendbarkeit und Produktkategorie,
- [ ] vollständige Risikobewertung der konkreten Fassung,
- [ ] Warnungen und Zweckbestimmung in allen ausgelieferten Sprachen,
- [ ] geprüfter Beschwerde-, Unfall-, Korrektur- und Rückrufablauf,
- [ ] Zugang und Rollen für das Safety Business Gateway,
- [ ] Verantwortlicher und erreichbare Stellvertretung,
- [ ] Produkthaftpflicht und Deckungsumfang geprüft,
- [ ] Versionsakte, Kundenpakete, Hashes, SBOM und Anleitung archiviert.

Solange ein Punkt offen ist, bleibt die Verkaufsfreigabe gesperrt. Die
kostenlose Demo wird wegen ihrer bereits erfolgten öffentlichen Verbreitung
gesondert bewertet; „kostenlos“ ersetzt keine Produktsicherheitsprüfung.

## Rechtsgrundlagen und Wiedervorlage

Arbeitsgrundlage sind insbesondere die Verordnung (EU) 2023/988, die
Produktsicherheitsinformationen der EU-Kommission und das deutsche
Produktsicherheitsrecht. Zusätzlich wird die Umsetzung der Richtlinie (EU)
2024/2853 für ab 9. Dezember 2026 in Verkehr gebrachte Software und digitale
Fertigungsunterlagen vor diesem Stichtag erneut geprüft.

Wiedervorlage: vor jeder öffentlichen Fassung, nach jedem Unfall oder Rückruf,
bei neuer Zielgruppe/Funktion und spätestens jährlich.
