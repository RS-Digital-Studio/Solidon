# Konzept: lokaler Bausteinaustausch ohne öffentliche Tauschstelle

**Stand:** verbindlich entschieden am 31.08.2026

**Anlass:** Rechts-, Betriebs- und Produktscope für Solidon3D 1.x begrenzen

**Bauplan:** §24.5

Diese Fassung ersetzt alle früheren Varianten einer von RS Digital
betriebenen Community-Tauschstelle. Die öffentliche Galerie mit Upload,
Download, Suche, Kommentaren, Likes oder Moderation wird nicht veröffentlicht
und gehört nicht mehr zum Produktumfang.

## 1. Verbindliche Entscheidung

Solidon3D unterstützt ausschließlich den lokalen, verlustfreien Export und
Import von Bausteindateien. Nutzer können solche Dateien selbst über einen
von ihnen gewählten Weg weitergeben. RS Digital stellt dafür keinen
öffentlichen Speicher-, Galerie-, Vermittlungs- oder Moderationsdienst bereit.

Damit gibt es bei RS Digital insbesondere:

- keine öffentliche Bausteingalerie;
- keine Nutzer-Uploads oder von RS Digital bereitgestellten Community-
  Downloads;
- keine Konten, Profile, Likes, Kommentare oder Direktnachrichten;
- keine Verkäufe, Zahlungen, Provisionen oder Verträge zwischen Nutzern;
- keine E-Mail-Bestätigung oder Kontaktdatei für Community-Beiträge;
- keine öffentliche Auswahl oder Durchsetzung von CC-Lizenzen;
- keinen Melde-, Moderations- oder DSA-Plattformbetrieb für Nutzerinhalte.

Die kostenlose 0.x-Demophase und die kostenpflichtige 1.x-Kauflizenz sind
davon unabhängig. Der lokale Bausteinaustausch ist eine Funktion der
Anwendung und kein separates Onlineangebot.

## 2. Lokaler Export

Ein eigener Baustein wird als Datenrezept exportiert. Die Datei enthält nur
das, was zur vollständigen Wiederherstellung erforderlich ist:

- registrierte Operationen und Parameterwerte;
- exponierte Parameter und benannte Merkmale;
- Format- und Kompatibilitätsangaben;
- Herkunft und Lizenzinformationen;
- gegebenenfalls eingebettete Modelldaten oder andere erforderliche Payloads.

Der Export bleibt verlustfrei. Eine lokale Datei darf Payloads enthalten,
weil sie nicht automatisch veröffentlicht oder an RS Digital übertragen
wird. Ausführbarer Quelltext reist nie mit. Ein Baustein als `.py` bleibt auf
dem Rechner, auf dem er installiert ist.

## 3. Lokaler Import

Der Import arbeitet vollständig offline und benötigt weder Konto noch
Netzverbindung. Vor der Übernahme prüft Solidon3D:

- gültiges und bekanntes Dateiformat;
- bekannte Operationsnamen und Parameterschemata;
- Größen-, Struktur- und Komplexitätsgrenzen;
- Integrität eingebetteter Daten;
- Herkunft, Autor und Lizenzangaben;
- Namenskollisionen und fehlende Operationen.

Ein fremder Baustein bleibt als fremd gekennzeichnet. Importieren, Bearbeiten,
Speichern oder erneutes Exportieren ändert seine Herkunft nicht. Ein fremder
Baustein darf nicht allein durch Speichern als eigener erscheinen.

Bei einer Namenskollision gewinnt der vorhandene lokale Baustein. Die
Anwendung bietet einen anderen Namen an und zeigt einen Befund mit
Handlungsvorschlag. Fehlt eine benötigte Operation, hält die Auswertung an und
nennt die erforderliche Solidon3D-Fassung.

## 4. Rechte und Verantwortung

Solidon3D beansprucht keine Rechte an einem vom Nutzer erstellten Baustein.
Die Anwendung überträgt aber auch keine Rechte an importierten Inhalten. Beim
Export eines fremden oder darauf aufbauenden Bausteins bleiben Herkunft,
Lizenz und Namensnennungspflichten erhalten.

Die Oberfläche weist verständlich darauf hin:

- nur eigene oder rechtmäßig nutzbare Inhalte weiterzugeben;
- Lizenz- und Namensnennungspflichten zu beachten;
- eingebettete Modelldaten auf fremde Rechte zu prüfen;
- fremde Dateien vor Verwendung fachlich und sicherheitstechnisch zu prüfen.

Das ist eine Information über den lokalen Dateiaustausch und keine
Community-Nutzungsordnung. Eigene Tauschbörsenbedingungen werden nicht
benötigt, weil RS Digital keinen solchen Dienst betreibt.

## 5. Produkt- und Netzgrenze

Der lokale Bausteinaustausch löst keinen Hintergrundkontakt aus. Insbesondere
werden beim Öffnen, Importieren, Speichern oder Exportieren keine Bausteine,
Metadaten, E-Mail-Adressen oder Nutzungsdaten an RS Digital übertragen.

Eine spätere öffentliche Tauschstelle ist nicht vorgemerkt. Sie wäre eine
neue Produktentscheidung und dürfte erst nach erneuter rechtlicher,
technischer, datenschutzrechtlicher und betrieblicher Prüfung entstehen.

## 6. Umsetzung

Die Umstellung umfasst:

1. öffentliche Galerie-, Upload-, Download- und Moderationswege entfernen
   oder bis zur Entfernung hart deaktiviert lassen;
2. Website-Navigation, Sitemap, Handbuch und Rechtstexte bereinigen;
3. öffentliche API- und Serverpfade nicht ausliefern;
4. App-Einstiege zur öffentlichen Tauschstelle entfernen;
5. lokale Import-/Exportdialoge und Provenienz erhalten;
6. veraltete Bauplan-, ROADMAP-, Konzept-, Memory- und Regeltexte nachziehen;
7. Tests für öffentliche Pfade entfernen oder in Negativtests auf
   Nichtvorhandensein umwandeln;
8. Offline-, Format-, Herkunfts-, Lizenz- und Sicherheitstests beibehalten.

## 7. Abnahme

Die Entscheidung ist umgesetzt, wenn:

- die ausgelieferte Anwendung keinen öffentlichen Tauschstellenzugang hat;
- die ausgelieferte Website keine Galerie, Uploadseite oder Community-API
  mehr anbietet;
- keine Tauschstellenkontakte oder Community-Beiträge verarbeitet werden;
- Rechtstexte keinen nicht vorhandenen Dienst beschreiben;
- Bauplan, ROADMAP, Konzepte, Erinnerungen und Regeln denselben Umfang nennen;
- lokaler Export und Import ohne Netz vollständig funktionieren;
- Herkunft, Lizenz und Fremdstatus einen Neustart und erneuten Export
  überstehen;
- Projekt- und Paketprüfungen keine verwaisten öffentlichen Verweise finden.
