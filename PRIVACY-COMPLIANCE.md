# Datenschutzorganisation — Verzeichnis, Interessenabwägung und Nachweise

Stand: 31. August 2026 · Organisationsfassung 1.0

**Freigabestatus: GESPERRT.** `DATENSCHUTZ.md` informiert Betroffene; diese
interne Akte weist Rechenschaft, Verträge, Löschung, Betroffenenrechte und
Sicherheitsmaßnahmen nach. Eine öffentliche Erklärung ersetzt diese Akte
nicht.

Verantwortlicher ist Robert Schneider, RS Digital, Aufbaustraße 10,
96049 Bamberg, support@solidon3d.de. Eine Auftragsverarbeitung oder gemeinsame
Verantwortlichkeit wird nicht allein aus einer Anbieterbezeichnung abgeleitet,
sondern vertraglich geprüft.

## Verzeichnis der Verarbeitungstätigkeiten

Für jeden folgenden Weg führt die private Anlage die Felder Zweck,
Betroffenen-/Datenkategorien, Rechtsgrundlage, Empfänger, Drittland,
Aufbewahrung, Löschung, technische/organisatorische Maßnahmen,
Verantwortlicher und Stand:

| Verarbeitung | Mindestinhalt der Einzelakte |
|---|---|
| Website-/Downloadbetrieb | Serverprotokolle, Downloadzähler, Hoster, Missbrauchsschutz, konkrete Fristen |
| Kauf, Rechnung und Merchant of Record | Vertrags-/Steuerdaten, Verkäuferrolle, Zahlungsdienstleister, gesetzliche Aufbewahrung |
| Online- und Offlineaktivierung | Lizenz-/Gerätekennungen, Aktivierungsbeleg, Betrugsabwehr, keine regelmäßige Kontoprüfung |
| Updateprüfung | Version, Plattform, minimal erforderliche Netzmetadaten, keine Projektdaten |
| Support und Sicherheitsmeldungen | freiwillig ausgewählte Anhänge, Protokolle, Projekt-/Chatinhalt nur nach Vorschau, Tickets und Löschung |
| Anthropic mit eigenem API-Schlüssel | direkte Nutzlast, Anbieterrolle, Empfängerland, Transfergrundlage, Speicher-/Trainingseinstellung |
| Lokales Ollama | grundsätzlich lokale Verarbeitung; Netz-/Installationswege und Protokolle gesondert abgrenzen |
| Tauschbörse | Upload, Autor/Lizenz, verschlüsselte Kontaktadresse, Bestätigung, Kommentar/Like, Meldung/Moderation, Fristen |
| Sicherheits-, Produkt- und Complianceakte | Beweise, Ansprechpartner, Behörden-/Versichererkommunikation, Zugriffsschutz |

Für jede Tätigkeit wird die tatsächliche Produktionskonfiguration geprüft.
Leere Anbieter-, Frist- oder Rechtsgrundlagenfelder sperren den betreffenden
Weg.

## Interessenabwägungen nach Art. 6 Abs. 1 lit. f DSGVO

Eine LIA ist vor Aktivierung mindestens nötig für Missbrauchs-/Ratelimitdaten,
notwendige Sicherheitsprotokolle, die zufällige Like-Kennung, Durchsetzung von
Lizenz-/Sanktionsregeln und gegebenenfalls Betrugsabwehr. Jede LIA enthält:

1. konkretes berechtigtes Interesse und Verantwortlichen,
2. Erforderlichkeit und geprüfte mildere Mittel,
3. Datenmenge, Erwartungen der Betroffenen und besondere Schutzbedürftigkeit,
4. Risiken, Widerspruchs-/Löschweg und Schutzmaßnahmen,
5. Ergebnis, Gültigkeitsdauer, Trigger und Genehmigung.

„Sicherheit“ oder „Missbrauch“ ohne konkreten Zweck und Frist genügt nicht.
Ein berechtigtes Interesse ersetzt keine Einwilligung, wenn eine solche für
den tatsächlichen Zugriff auf ein Endgerät nach § 25 TDDDG erforderlich ist.

## Auftragsverarbeitung und Drittland

Vor Produktivbetrieb liegen aktuelle Rollen-/Vertragsprüfungen vor für Hoster,
E-Mail, Merchant of Record/Zahlung, Supportwerkzeuge und sonstige Empfänger.
Bei Anthropic werden insbesondere eigener Nutzer-API-Schlüssel, unmittelbarer
Datenfluss, Nutzlast, Vertragspartner, Speicher-/Trainingsoption,
Unterauftragsverarbeiter, Empfängerland, Transferinstrument und ergänzende
Maßnahmen dokumentiert. Die sichtbare Nutzlastvorschau und Anbieterlinks stehen
vor dem ersten Senden zur Verfügung.

## Betroffenenrechte und Löschung

Ein Eingang erhält `DSR-JJJJ-NNN`, Identität wird verhältnismäßig geprüft und
Frist/Verlängerung dokumentiert. Der Suchplan umfasst produktive Datenbank,
Mail/Ticket, Aktivierung, Tauschbörse, Abrechnung, Backups und Behördenakten.
Antwort, Datenkopie, Ablehnung, Rechtsgrund und tatsächliche Löschung werden
belegt. Andere Betroffene und Geschäftsgeheimnisse werden geschützt.

Löschläufe sind automatisiert, protokolliert und mit einer Testdatenakte
nachgewiesen. Backups haben ein dokumentiertes Ablauf- und
Wiederherstellungskonzept; eine Löschzusage darf nicht nur den Primärdatensatz
erfassen. Gesetzliche Aufbewahrung wird eng getrennt von operativer Nutzung.

## Sicherheit und Datenschutz durch Technikgestaltung

- Datenminimierung und lokale Verarbeitung sind Voreinstellung.
- Kontaktadressen der Tauschbörse werden mit AES-256-GCM und getrenntem
  Schlüssel gespeichert; HMAC-Zwecke sind domänengetrennt.
- Schlüssel, Tokens und Klartextkontakte stehen weder im Repository noch in
  Protokollen oder Fehlerantworten.
- Rollen, Zugriffe, Exporte, Schlüsselwechsel und Wiederherstellung werden
  regelmäßig getestet.
- Supportanhänge werden erst nach ausdrücklicher Auswahl und vollständiger
  Vorschau übertragen.
- Datenschutzverletzungen laufen durch den gemeinsamen Intake in
  `SECURITY-INCIDENT.md`.

## DSFA-Schwellenentscheidung

Vor Verkaufsstart und vor jeder wesentlichen Änderung wird schriftlich
entschieden, ob Art, Umfang, Umstände und Zweck voraussichtlich ein hohes
Risiko erzeugen. Besonders geprüft werden große oder systematische
Überwachung, umfangreiche besondere Kategorien, neue Profilbildung,
KI-Nutzlasten, Kombination von Identitäten sowie medizinische oder
patientenbezogene Funktionen. Das aktuelle allgemeine, lokale Produktmodell
ist kein Freibrief; neue Cloud-, Konto-, Telemetrie- oder Medizinpfade öffnen
die Entscheidung erneut.

## Freigabekriterien

- [ ] VVT-Einzelakten für alle aktiven Wege ausgefüllt,
- [ ] LIA für jeden lit.-f-Weg genehmigt und terminiert,
- [ ] AVV/Rollen und Drittlandtransfer je Empfänger geprüft,
- [ ] Löschläufe einschließlich Backups nachgewiesen,
- [ ] Betroffenenprozess mit Auskunft, Löschung und Widerspruch getestet,
- [ ] Berechtigung, Schlüsselrotation und Wiederherstellung getestet,
- [ ] DSFA-Schwellenentscheidung unterschrieben,
- [ ] Datenschutzerklärung stimmt mit Produktion und Fristen überein.

Offene Punkte sperren ausschließlich den betroffenen Verarbeitungsweg; wenn
dieser für Verkauf, Aktivierung oder Börse zwingend ist, sperren sie auch
diesen Start.
