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
| Sicherheits-, Produkt- und Complianceakte | Beweise, Ansprechpartner, Behörden-/Versichererkommunikation, Zugriffsschutz |

Der Bausteinaustausch ist ausschließlich ein lokaler Offline-Dateiweg zwischen
Nutzern. RS Digital nimmt keine Rezepte oder Kontaktdaten entgegen, speichert
oder verteilt keine fremden Bausteine und betreibt keine Galerie, Konten,
Profile, Likes, Kommentare oder Moderation. Export, Import, Herkunft und Lizenz
werden lokal verarbeitet und erzeugen bei RS Digital keinen VVT-Eintrag. Eine
spätere gehostete Austauschfunktion wäre eine neue, ausdrücklich zu
genehmigende Produkt-, Datenschutz- und DSA-Prüfung.

Für jede Tätigkeit wird die tatsächliche Produktionskonfiguration geprüft.
Leere Anbieter-, Frist- oder Rechtsgrundlagenfelder sperren den betreffenden
Weg.

### Technischer Vertrag für Missbrauchsschutz und Reichweitenzählung

Die vier serverseitigen Ratelimits speichern die IP-Adresse nicht im Klartext
und nicht als bloßen, offline erratbaren SHA-256-Wert. Aus ihr wird mit einem
privaten, zweckgetrennten und je Zeitfenster wechselnden Schlüssel ein
HMAC-Pseudonym gebildet. Das ist **Pseudonymisierung, keine Anonymisierung**;
die Verarbeitung bleibt deshalb vollständig im Anwendungsbereich der DSGVO.

| Weg | Anwendungszustand | fachliche Frist |
|---|---|---:|
| Website-Zähler | HMAC-Pseudonym und Anforderungszeit | 60 Sekunden |
| Aktivierungsendpunkte | HMAC-Pseudonym und Anforderungszeit | 900 Sekunden |
| Anmeldung zur privaten Statistik | HMAC-Pseudonym und Anforderungszeit | 900 Sekunden |
| Supportversand | HMAC-Pseudonym und Anforderungszeit | 3.600 Sekunden |
| Tagesbesucherzählung | HMAC aus IP-Adresse, Browserkennung und privatem Tageswert | ein UTC-Tag |

Die Anwendung berücksichtigt jeweils nur das laufende und vorige Zeitfenster,
entfernt überfällige und frühere ungesalzene SHA-Schlüssel beim
nächsten Zugriff und sperrt bei beschädigtem Zustand. Diese Zugriffslöschung
beweist jedoch keine absolute physische Höchstfrist: Wenn kein PHP-Prozess
läuft, kann PHP nichts löschen. Vor Produktivfreigabe muss deshalb ein
minütlicher Server-Task unter demselben exklusiven Dateilock nachgewiesen sein.
Er kürzt die vier Ratelimitdateien nach 60, 900, 900 beziehungsweise 3.600
Sekunden und löscht den Tageswert nach 86.400 Sekunden; private dauerhafte
Schlüsseldateien werden dabei nicht gelöscht. Exportierte Taskdefinition,
absolute private Pfade, Servicekonto, erfolgreicher Probelauf, Ausfallalarm
und die Frist in Sicherungskopien gehören zum Freigabebeleg. Auf einem
laufenden Host beträgt die technische Obergrenze dann Fachfrist plus höchstens
60 Sekunden; Hostausfälle und Backups werden getrennt geregelt.

Für die monatlichen Reichweitenzeilen gilt eine kalendarische Frist: Nur der
laufende und der unmittelbar vorherige UTC-Kalendermonat werden behalten,
höchstens 62 Kalendertage. Jahresvergleiche und stille Langzeitaggregate sind
nicht vorgesehen. Unter derselben `quota.lock` wie der Zähler validiert der
Wartungslauf erst sämtliche Monatsdateien, ihre Rechte und das geschlossene
Zeilenschema; erst dann leert, synchronisiert und entfernt er ältere Monate.
Das Tageskennzeichen wird nicht tageübergreifend verknüpft. Produktivfreigabe
setzt zusätzlich den eingerichteten minütlichen Lauf, Ausfallalarm und eine
technisch gleiche Höchstfrist in Sicherungen voraus; Repository-Code allein
beweist diese externen Tatsachen nicht.

## Interessenabwägungen nach Art. 6 Abs. 1 lit. f DSGVO

Eine LIA ist vor Aktivierung mindestens nötig für Missbrauchs-/Ratelimitdaten,
notwendige Sicherheitsprotokolle, Durchsetzung von Lizenz-/Sanktionsregeln und
gegebenenfalls Betrugsabwehr. Jede LIA enthält:

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
Mail/Ticket, Aktivierung, Abrechnung, Backups und Behördenakten.
Antwort, Datenkopie, Ablehnung, Rechtsgrund und tatsächliche Löschung werden
belegt. Andere Betroffene und Geschäftsgeheimnisse werden geschützt.

Löschläufe sind automatisiert, protokolliert und mit einer Testdatenakte
nachgewiesen. Backups haben ein dokumentiertes Ablauf- und
Wiederherstellungskonzept; eine Löschzusage darf nicht nur den Primärdatensatz
erfassen. Gesetzliche Aufbewahrung wird eng getrennt von operativer Nutzung.

## Sicherheit und Datenschutz durch Technikgestaltung

- Datenminimierung und lokale Verarbeitung sind Voreinstellung.
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
- [ ] Ratelimit-Scheduler, Ausfallalarm und Backup-Löschung nachgewiesen,
- [x] Löschfrist der monatlichen Reichweitenzeilen im Code auf laufenden plus
      unmittelbar vorherigen UTC-Monat, höchstens 62 Kalendertage, erzwungen,
- [ ] DSFA-Schwellenentscheidung unterschrieben,
- [ ] Datenschutzerklärung stimmt mit Produktion und Fristen überein.

Außerhalb des Repositorys sind dafür mindestens folgende Tatsachen und Belege
beizubringen; ein Generator oder Test darf sie nicht ersetzen:

- Robert/RS Digital: tatsächliche Verarbeitungswege, Verantwortliche,
  Zugriffsberechtigungen, genehmigte Lösch- und Betroffenenprozesse sowie
  unterzeichnete VVT-, LIA- und DSFA-Schwellenentscheidung,
- netcup/Serveradministration: geltende Serverprotokollfrist,
  Produktionskonfiguration, Hosterrolle, aktueller Vertrag/AVV und
  protokollierter Lösch- sowie Backuptest,
- E-Mail-/Supportbetrieb: wirklicher Transportweg, Postfach-/Adminzugriffe,
  Anhänge, Spam-/Sicherheitskopien und nachweisbare Löschung spätestens nach
  der öffentlich genannten Frist,
- PayPal/Steuerberatung: tatsächlicher Konto- und Button-Typ, ausgezahlte
  Transaktionsfelder, wiederkehrende Zahlungen, Buchführung sowie Ertrag- und
  Umsatzsteuerbehandlung der freiwilligen Unterstützung,
- Anthropic und jeder sonstige Empfänger: Vertragspartner, Rolle,
  Speicher-/Trainingsoptionen, Unterauftragsverarbeiter, Empfängerländer,
  Transferinstrumente und ergänzende Maßnahmen,
- qualifizierte Datenschutzberatung: abschließende Prüfung der Rechtsgrundlagen,
  Informationstexte, Rollen, Transfers und Fristen gegen den realen Betrieb.

Offene Punkte sperren ausschließlich den betroffenen Verarbeitungsweg; wenn
dieser für Verkauf, Aktivierung oder Support zwingend ist, sperren sie auch
diesen Start.
