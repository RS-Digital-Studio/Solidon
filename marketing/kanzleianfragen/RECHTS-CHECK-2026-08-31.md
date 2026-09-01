# Rechts- und Kostencheck für Solidon3D

**Stand:** 31.08.2026

**Zweck:** Arbeits- und Übergabeunterlage für die anwaltliche Prüfung. Diese
Unterlage ist keine anwaltliche Freigabe und ersetzt keine Rechtsberatung.

## 1. Verbindlicher Produktumfang

Solidon3D ist eine lokal installierte Desktopanwendung für Hobbyanwender,
Maker und Menschen ohne klassische CAD-Vorkenntnisse. Die Anwendung wird für
Windows, macOS und Linux angeboten. Projekte bleiben grundsätzlich lokal;
nach der Freischaltung funktionieren alle Konstruktionsfunktionen ohne Konto
und ohne Netz. Gewerbliche Nutzung ist möglich, bestimmt aber weder Zielgruppe
noch Zwecksetzung.

Nicht vorgesehen sind eine medizinische oder dentale Zweckbestimmung,
medizinische Bewertung, patientenbezogene Freigabe, ein eigener Slicer,
Projekt-Cloud, Mehrbenutzerbetrieb oder ein SaaS-/Enterprise-Angebot. Anfragen
aus Dental- und Kunststoffunternehmen ändern diese Grenze nicht.

Eine öffentliche Tauschstelle oder sonstige von RS-Digital betriebene
Plattform für Nutzerinhalte wird nicht umgesetzt. Erhalten bleibt nur der
lokale, offline mögliche und verlustfreie Export und Import von
Bausteinrezepten. Nutzer teilen solche Dateien auf eigenen Wegen. RS-Digital
nimmt sie nicht zum öffentlichen Abruf entgegen, hostet, veröffentlicht und
moderiert sie nicht. Herkunft, Rechtehinweis, Fremdkennzeichnung und sicherer
Import bleiben Teil der Anwendung.

## 2. Aktueller Freigabestatus

Die internen Rechtstexte, Prozessakten, Sicherheitsprüfungen und
Lizenzunterlagen sind weit fortgeschritten. Sie sind jedoch nicht anwaltlich
freigegeben. Der kostenpflichtige Verkaufsstart bleibt bis zur Prüfung der
tatsächlichen Abläufe gesperrt. Die frühere öffentliche Tauschstelle ist aus
dem Produktumfang gestrichen.

Die kostenlose 0.x-Demophase ist bereits öffentlich; 0.2.2 ist nur die
aktuell veröffentlichte Fassung und weitere kostenlose 0.x-Versionen können
bis zum Wechsel auf 1.x folgen. Rund 3.300 Website-Besucher und etwa 1.000
Downloads in der ersten Woche sind keine Verkaufs-, Umsatz- oder
Nutzerzahlen, erhöhen aber die Dringlichkeit der Prüfung. Die
Gewerbeanmeldung als Nebenerwerb wurde am 24.08.2026 eingereicht; als Beginn
der Tätigkeit ist ebenfalls der 24.08.2026 angegeben. Die behördliche
Empfangsbescheinigung steht noch aus.

## 3. Priorisierte Risikobewertung

Bewertung: Schwere 1–5 × Eintrittswahrscheinlichkeit 1–5. 1–4 niedrig,
5–9 mittel, 10–15 hoch, 16–25 kritisch.

| Thema | Bewertung | Stand und notwendige Maßnahme |
|---|---:|---|
| CRA-Meldebereitschaft ab 11.09.2026 | 5 × 4 = **20, kritisch** | Die EU-Kommission nennt für aktiv ausgenutzte Schwachstellen und schwere Sicherheitsvorfälle eine erste Meldung binnen 24 Stunden und eine Hauptmeldung binnen 72 Stunden. Die Einordnung der bereits kostenlosen Demo als Bereitstellung im geschäftlichen Zusammenhang und der konkrete Meldeweg müssen sofort bestätigt werden. |
| Produktsicherheit/GPSR | 5 × 4 = **20, kritisch** | Die Kommissionsleitlinien beziehen Apps und Software ausdrücklich ein. Die Produktakte ist angelegt, aber Zweckbestimmung, konkrete Fassungsbewertung, Warnungen, Rückverfolgbarkeit, Beschwerden, Korrekturen, Rückrufprobe, Rollen und Versicherung sind noch nicht fachlich und betrieblich freigegeben. |
| Exportkontrolle und Sanktionen | 5 × 4 = **20, kritisch** | CAD-Software ist in den einschlägigen Russland-Sanktionen ausdrücklich erfasst. Download, Aktivierung, Verkauf, Update und Support brauchen reale Länder-, Empfänger-, Eigentums-, Endverwendungs- und Dual-Use-Prüfungen sowie technische Sperren. Der Prozess ist beschrieben, aber noch nicht im Betrieb belegt. |
| Verbrauchervertrag und elektronische Widerrufsfunktion | 4 × 5 = **20, kritisch** | Vor dem Verkauf müssen Preis-, Leistungs-, Aktualisierungs-, Laufzeit-, Gewährleistungs- und Widerrufsinformationen mit dem tatsächlichen Bestell-, Liefer- und Aktivierungsweg übereinstimmen. Die elektronische Zwei-Schritt-Widerrufsfunktion ist spezifiziert, aber noch nicht mit sichtbarer Website, API, Bestellauflösung und dauerhafter Bestätigung gebaut. |
| KI-Chat/AI Act | 4 × 4 = **16, kritisch** | Vor der ersten Modellkommunikation muss erkennbar sein, dass der Nutzer mit KI interagiert. Rollen bei eigenem Anthropic-Schlüssel und lokalem Ollama, Cloud-Nutzlastvorschau, sechs Sprachen, Barrierefreiheit, Backend-Sperre und KI-Kompetenznachweis sind noch nicht vollständig bestätigt. |
| Verbraucher-Checkout und Beweisführung | 4 × 4 = **16, kritisch** | Verkäufermodell, Bestellschaltfläche, getrennte Zustimmung, Kenntnisbestätigung, Vertragsmail und Beweisprotokoll fehlen noch. Der Verkauf bleibt bis zum Ende-zu-Ende-Test gesperrt. |
| Open-Source- und Paketlizenzen | 5 × 3 = **15, hoch** | SBOM, Lizenztexte und automatisierte Prüfungen sind vorhanden und sperren bei Lücken. Die tatsächlich ausgelieferten Windows-, macOS- und Linux-Pakete müssen noch auf Hinweise, Quellcodeangebote, Relinking und native Fremdteile geprüft werden. |
| Datenschutzorganisation für Aktivierung, Support und KI | 4 × 3 = **12, hoch** | Verzeichnis der Verarbeitungstätigkeiten, Interessenabwägungen, Verträge, Drittlandtransfers, Löschung, Betroffenenrechte und technische Maßnahmen müssen nicht nur beschrieben, sondern mit realen Verträgen und Tests belegt sein. Projekt- und Chatdaten dürfen nur nach ausdrücklicher Auswahl übertragen werden. |
| Medizinische und dentale Fehlpositionierung | 5 × 2 = **10, hoch** | Keine medizinischen Leistungsversprechen, Freigaben, Referenzen oder Dentalfunktionen. Website, EULA, Handbuch und Antworten an Interessenten müssen dieselbe Hobby-Zwecksetzung nennen. Ein Haftungsausschluss allein ersetzt keine klare Produktgestaltung und Kommunikation. |
| Marke Solidon | 4 × 3 = **12, hoch** | Vor größerer Werbung Kollisionsrecherche, Waren-/Dienstleistungsklassen und Schutzgebiet festlegen. Erst danach Anmeldung in Deutschland oder der EU. |
| BFSG/Barrierefreiheit | 3 × 3 = **9, mittel** | Für Kleinstunternehmen besteht bei Dienstleistungen eine Ausnahme; Beschäftigtenzahl, Umsatz/Bilanzsumme und die Verkäuferrolle eines möglichen Merchant of Record sind aber noch nicht belegt. Barrierefreiheit bleibt unabhängig davon Qualitätsziel. |

## 4. Unmittelbar abzuarbeiten

### Vor weiterer öffentlicher Verbreitung der Demo

1. CRA-Anwendbarkeit der kostenlosen Demo und Meldebereitschaft vor dem
   11.09.2026 schriftlich klären.
2. KI-Offenlegung vor jedem ersten Anthropic- oder Ollama-Aufruf technisch
   erzwingen und in allen sechs Sprachen prüfen.
3. Demo, Website und Kommunikation auf eine einheitliche Hobby-Zwecksetzung
   ohne medizinische oder dentale Eignungsaussage prüfen.
4. Datenschutzinformationen für Aktivierung, Support, Serverprotokolle und
   freiwillige Übertragungen mit der Produktion abgleichen.
5. Ansprechpartner, Stellvertretung und Eingang für Sicherheits- und
   Produktsicherheitsvorfälle festlegen.

### Spätestens vor dem kostenpflichtigen Verkaufsstart

1. Verkäufermodell festlegen: eigener Verkauf oder Merchant of Record.
2. Checkout, Vertragsschluss, Rechnungsstellung, Lizenzlieferung,
   Aktivierung, Widerruf, Erstattung und Sperrfolgen Ende zu Ende prüfen.
3. AGB, EULA, Datenschutz, Widerrufsbelehrung, Impressum,
   Produktbeschreibung und Handbuch anwaltlich gegen den echten Ablauf
   freigeben.
4. GPSR-Produktakte, Risikobewertung, Warnungen, Rückverfolgbarkeit,
   Beschwerde-, Korrektur- und Rückrufweg abschließen.
5. Pakete aller drei Betriebssysteme auf Open-Source-Pflichten prüfen.
6. Umsatzsteuer, Leistungsort, Schweiz-Vertrieb, Exportkontrolle und
   Sanktionen mit Rechts- und Steuerberatung abstimmen.
7. Produkthaftpflicht und Cyberdeckung passend zu 3D-Konstruktionssoftware
   anbieten lassen.

### Für den lokalen Austausch von Rezeptdateien

1. Import nur über das registrierte, nicht ausführbare Rezeptformat zulassen.
2. Herkunft, Rechtehinweis und Fremdstatus sichtbar und dauerhaft erhalten.
3. Nutzer vor dem Import fremder Dateien verständlich über Verantwortung und
   notwendige Prüfung informieren.
4. Keine Galerie, Suche, Upload-API oder sonstige öffentliche Verteilung
   durch RS-Digital bereitstellen.

## 5. Kanzleiwahl

### Giesel Rechtsanwälte, Bamberg

Die Kanzlei nennt IT-Recht, Softwareverträge, AGB, Lizenzen, Datenschutz,
gewerblichen Rechtsschutz und Marken ausdrücklich als Schwerpunkte. Sie ist
für eine örtliche, pragmatische Federführung voraussichtlich die passendere
und günstigere erste Anfrage. Vor Mandatierung muss geklärt werden, ob CRA,
GPSR, Produktsicherheit, Exportkontrolle und internationale
Verbraucherverträge selbst oder über feste Spezialisten abgedeckt werden.

### RÖDL, Ansprechpartner Johannes Marco Holz

RÖDL kann die breitere Kombination aus IT-, Datenschutz-, Produkt-,
Außenwirtschafts-, Steuer- und internationalen Fragen eher innerhalb einer
größeren Organisation koordinieren. Das ist für ein Gesamtmandat fachlich
attraktiv, wird aber voraussichtlich deutlich teurer. Die Anfrage verlangt
deshalb ausdrücklich eine abgegrenzte erste Phase und einen Kostendeckel.

### Hümmer und Huml, Bamberg

Hümmer und Huml ist für Steuerberatung, Rechtsberatung,
Unternehmensberatung und Wirtschaftsprüfung grundsätzlich interessant. Auf
der öffentlichen Darstellung sind die für Solidon3D entscheidenden
Spezialgebiete Softwarelizenzierung, CRA, GPSR und IT-Vertragsrecht aber
nicht so konkret ausgewiesen wie bei den beiden vorgenannten Adressen. Als
Steuer- und Gründungsberater kann die Kanzlei sinnvoll sein; als alleinige
rechtliche Federführung ist sie erst nach einer ausdrücklichen Bestätigung
dieser Spezialkompetenzen zu empfehlen.

## 6. Realistischer Kostenrahmen

Alle Beträge sind grobe Planwerte **netto**, weil keine der angefragten
Kanzleien verbindliche Preise veröffentlicht. Verbindlich wird nur ein
schriftliches Angebot.

Die häufig genannte gesetzliche Obergrenze von 190 € für ein erstes
Beratungsgespräch gilt nach § 34 RVG nur für Verbraucher, wenn keine andere
Vergütungsvereinbarung getroffen wurde. Das Solidon3D-Mandat ist eine
unternehmerische Beratung; auf diese Obergrenze darf deshalb nicht kalkuliert
werden.

### Finanzierbares Mindestmodell

Eine vollständige externe Begleitung ist für den Start nicht zwingend als ein
Gesamtmandat zu beauftragen. Bei sehr begrenztem Budget ist folgende
Reihenfolge fachlich sinnvoller:

1. kostenlose Gründungs- und Förderorientierung bei IHK, IGZ/LAGARDE1 und
   Wirtschaftsförderung Bamberg;
2. vor dem Bau eines eigenen Checkouts einen Merchant of Record prüfen;
3. nur die danach noch benötigten Website-/Shoptexte über einen laufend
   aktualisierten Rechtstextdienst beziehen;
4. den vorhandenen deutschen EULA-Entwurf als einzelnes IT-Rechtsdokument
   anwaltlich zum Festpreis prüfen lassen;
5. erst danach eine eng begrenzte Spezialberatung zu den verbleibenden
   Produktfragen CRA/GPSR, KI/Datenschutz und Hobby-Zwecksetzung anfragen.

| Baustein | Öffentlicher Preisstand 31.08.2026 | Einordnung |
|---|---:|---|
| IHK/Wirtschaftsförderung/IGZ-LAGARDE1 | 0 € | Gründungs-, Förder- und Verweisberatung, keine individuelle anwaltliche Produktfreigabe |
| Händlerbund Basic oder vergleichbares Rechtstextpaket | ab 9,90 € netto monatlich, regelmäßig 12 Monate | Website-/Shoptexte und Updates; Eignung für eigenen Softwareverkauf vor Buchung bestätigen lassen |
| IT-Recht Kanzlei Starter | 9,90 € netto monatlich | ein Webauftritt, Update-Service und Beratung nur zu den bereitgestellten Texten und ihrer Einbindung |
| Händlerbund VertragsCheck | 119,90 € netto je deutschem Dokument bis 30 Seiten | anwaltliche Prüfung und Auswertungsgespräch; keine umfassende Compliance-Prüfung |
| Giesel: eng begrenztes Erstgespräch | Preis nicht veröffentlicht; anzufragen mit höchstens 500 € netto | nur priorisierte Solidon3D-Sonderfragen, keine Texterstellung |
| RÖDL | kein öffentliches Mindesthonorar | bei diesem Budget zunächst nicht beauftragen |
| Paddle als Merchant of Record | 5 % + 0,50 US-Dollar je Checkout, keine Monatsgebühr | übernimmt Verkauf, Zahlung, Umsatzsteuerabwicklung und Billing-Support; Produktrecht und EULA bleiben bei RS-Digital |
| Digistore24 als Merchant of Record | Deutschland regulär 7,9 % + 1 € für den Preisanteil bis 400 €, keine Monatsgebühr | die internationale Angabe „ab 2,9 % + 1 US-Dollar“ ist keine belastbare Kalkulation für den deutschen Reseller; endgültigen Satz und Reseller vorab bestätigen lassen |

Rechnerische Mindestvarianten im ersten Jahr:

- Rechtstextpaket plus eine EULA-Prüfung: **238,70 € netto / 284,05 € brutto**;
- Rechtstextpaket plus zwei Dokumentprüfungen: **358,60 € netto / 426,73 € brutto**;
- zusätzlich ein eng gedeckeltes Giesel-Gespräch bis 500 € netto:
  insgesamt höchstens **858,60 € netto / 1.021,73 € brutto**.

Hinzu kommt nur die umsatzabhängige Gebühr des Merchant of Record. Dieses
Mindestmodell ist keine vollständige anwaltliche Freigabe. Es konzentriert
das Geld auf die Punkte mit dem höchsten Schadenspotenzial und verschiebt
Markenanmeldung, internationale Einzelberatung und laufende Kanzleibegleitung,
bis reale Verkaufserlöse sie tragen können. BAFA-Beratungsförderung ist für
dieses Ziel keine verlässliche Lösung, weil Beratungen mit überwiegend Rechts-
und Versicherungsfragen ausdrücklich nicht gefördert werden.

| Stufe | Giesel/vergleichbare IT-Boutique | RÖDL/Full-Service |
|---|---:|---:|
| Kurze Konflikt- und Mandatsprüfung | häufig 0 €, sonst nach Aufwand | häufig 0 €, sonst nach Aufwand |
| Nur inhaltliches Erstgespräch, etwa 60–90 Minuten | 300–800 € | 600–1.500 € |
| Vorbereitung, falls außerhalb eines Pakets abgerechnet | 300–1.000 € | 750–2.000 € |
| Gebündelte erste Phase laut Anfrage: Gespräch, Vorbereitung, Sichtung, Lückenliste und Abschluss | Kostendeckel 2.000 € | Kostendeckel 3.000 € |
| Verbraucherrecht, AGB/EULA, Checkout und Widerruf | 3.000–7.000 € | 6.000–12.000 € |
| Datenschutz, Aktivierung, Support und KI-Rollen | 2.500–6.000 € | 5.000–10.000 € |
| GPSR, CRA, Produktsicherheit und Exportkontrolle | 4.000–10.000 € | 8.000–18.000 € |
| Open-Source-/Paketprüfung | 1.500–4.000 € | 3.000–7.000 € |
| Markenrecherche und Anmeldung, ohne Amtsgebühr | 800–2.000 € | 1.500–3.500 € |
| Laufende Begleitung nach Start | 300–500 € je Stunde oder Pauschale | 450–750 € je Stunde oder Pauschale |

Erstgespräch, Vorbereitung und erste Phase sind Alternativen beziehungsweise
Bestandteile desselben Pakets und werden nicht nebeneinander addiert. Reicht
der angefragte Kostendeckel nicht, soll die Kanzlei den Umfang vor der
Beauftragung verkleinern statt ihn ungefragt zu überschreiten.

Die Einzelposten werden bei einem sinnvoll gebündelten Mandat nicht einfach
vollständig addiert; viele Unterlagen und Prüfungen überschneiden sich. Für
Solidon3D ist bei der vorhandenen Vorbereitung für eine vollständige
Startbegleitung über eine örtliche IT-Kanzlei mit koordinierten Spezialisten
ein realistisches Gesamtbudget von **12.000–24.000 € netto** anzusetzen. Mit
19 Prozent Umsatzsteuer sind das **14.280–28.560 € brutto**. Bei vollständiger
Koordination durch eine große Full-Service-Kanzlei sollte vorsichtshalber mit
**19.000–40.000 € netto** beziehungsweise **22.610–47.600 € brutto** gerechnet
werden. Wenn nur die erste Lückenanalyse beauftragt und anschließend viel
intern umgesetzt wird, kann das untere Ende erreichbar sein. Ein sinnvoller
Planungswert ist deshalb zunächst eine Reserve von **20.000 € netto** für die
Giesel-Route beziehungsweise **30.000 € netto** für die RÖDL-Route. Erst das
schriftliche Angebot ersetzt diese Schätzung.

Nicht enthalten sind Versicherungsprämien, Steuerberatung, externe
Penetrations- oder Barrierefreiheitstests, Übersetzungen durch Fachübersetzer,
Reisekosten und amtliche Gebühren.

Der vollständige Verzicht auf die von RS-Digital betriebene Tauschstelle spart
gegenüber dem früheren Entwurf voraussichtlich etwa **3.000–7.000 € netto**
bei einer IT-Boutique beziehungsweise **5.500–12.500 € netto** bei einer
Full-Service-Kanzlei. Hinzu kommt deutlich weniger laufende Betreiberlast.
Die Grundkosten für Verbraucherrecht, Datenschutz, Produktsicherheit, CRA,
KI, Exportkontrolle und Lizenzen bleiben trotzdem bestehen. Der Digital
Services Act ist mangels geplanter Hosting- oder Plattformfunktion kein
eigenes Produktarbeitspaket mehr; diese Abgrenzung sollte die Kanzlei kurz
bestätigen.

### Zeitliche und finanzielle Staffelung

Die vollständige Begleitung ist kein einzelner Beratungstermin und muss auch
kein monatliches Dauermandat sein. Ein Verkaufsdatum wird erst nach Abschluss
aller Freigabegates festgelegt; bis dahin bietet sich folgende Beauftragung
nach Meilensteinen an:

| Zeitraum | Ergebnis | Giesel/IT-Boutique | RÖDL/Full-Service |
|---|---|---:|---:|
| Anfang September | Erstgespräch, Sichtung und priorisierte Lückenliste | Kostendeckel 2.000 € | Kostendeckel 3.000 € |
| September | Sofortmaßnahmen für laufende 0.x-Demo: CRA-Meldeweg, Produktsicherheit, KI- und Datenschutzhinweise, Zweckabgrenzung | 2.000–4.000 € | 3.000–7.000 € |
| September bis Mitte Oktober | Verkaufsgrundlage: Verkäufermodell, AGB/EULA, Datenschutz, Checkout, Widerruf, Aktivierung und Support | 4.000–8.000 € | 7.000–13.000 € |
| Oktober | Freigabeprüfung: GPSR/CRA-Akte, Exportkontrolle, OSS-Pakete, Website und End-to-End-Abläufe | 4.000–10.000 € | 7.000–17.000 € |
| Nach Verkaufsstart | Nur konkrete Änderungen, Vorfälle und jährliche Prüfung | 300–500 € je Stunde oder vereinbarte Pauschale | 450–750 € je Stunde oder vereinbarte Pauschale |

Die Phasen überschneiden sich inhaltlich; ihre Maximalwerte sind deshalb nicht
einfach zu addieren. Abgerechnet werden sollte nach Abschluss jeder Stufe oder
monatlich nur für die in diesem Monat tatsächlich freigegebenen Arbeitspakete.
Ein laufender Retainer ist vor dem Verkaufsstart nicht nötig. Der größte Teil
der Vorbereitungskosten fällt vor der Terminentscheidung an. Ergibt die erste
Lückenliste wesentliche technische Umbauten, wird ein Verkaufsstart erst nach
deren Abschluss festgelegt; der Prüfungsumfang wird nicht verkürzt.

Zusätzliche amtliche Markenanmeldegebühren:

- deutsche Marke elektronisch: 290 € einschließlich bis zu drei Klassen;
- Unionsmarke online: 850 € für eine Klasse, 50 € für die zweite und 150 € je
  weiterer Klasse ab der dritten;
- anwaltliche Recherche, Klassenwahl und Anmeldung zusätzlich typischerweise
  nach Angebot.

Für die Beauftragung gilt: erste Phase schriftlich abgrenzen, Ergebnisformat
und Bearbeitungsfrist festlegen, Festpreis oder verbindlichen Kostendeckel
vereinbaren und jede weitere Stufe erst nach neuem schriftlichem Angebot
freigeben.

## 7. Amtliche Ausgangsquellen

- [Digital Services Act: Abgrenzung der Pflichten von Vermittlungsdiensten, Bundesnetzagentur](https://www.bundesnetzagentur.de/DE/Fachthemen/DSC/1_Themen/PflichtenVermittlunggsdienste/start.html)
- [§ 356 BGB: Widerruf bei digitalen Inhalten](https://www.gesetze-im-internet.de/bgb/__356.html)
- [§ 356a BGB: elektronische Widerrufsfunktion](https://www.gesetze-im-internet.de/bgb/__356a.html)
- [AI Act, Verordnung (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj?locale=de)
- [CRA-Meldepflichten ab 11.09.2026, EU-Kommission](https://digital-strategy.ec.europa.eu/en/policies/cra-reporting)
- [CRA-Zusammenfassung und Anwendungsfristen, EU-Kommission](https://digital-strategy.ec.europa.eu/en/policies/cra-summary)
- [GPSR-Leitlinien für Unternehmen, EU-Kommission](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=OJ:C_202506233)
- [Produkthaftungsrichtlinie (EU) 2024/2853](https://eur-lex.europa.eu/eli/dir/2024/2853/oj/deu)
- [BFSG und Kleinstunternehmen, Bundesfachstelle Barrierefreiheit](https://www.bundesfachstelle-barrierefreiheit.de/DE/Barrierefreiheitsstaerkungsgesetz/E-Commerce/online-shops_node)
- [Markengebühren, DPMA](https://www.dpma.de/service/gebuehren/marken/)
- [Gebühren für Unionsmarken, EUIPO](https://www.euipo.europa.eu/de/trade-marks/before-applying/fees-payments)
- [§ 34 RVG: Beratungsvergütung](https://www.gesetze-im-internet.de/rvg/__34.html)

## 8. Kostengünstige Anlaufstellen und Angebote

- [IHK für Oberfranken: Ansprechpartnerin für die Region Bamberg](https://www.ihk.de/bayreuth/hauptnavigation/service/gruendung-start-ups-nachfolge-finanzierung/ansprechpartner-unternehmenssprechtage-6414980)
- [Wirtschaftsförderung Bamberg: Existenzgründungsberatung](https://www.stadt.bamberg.de/B%C3%BCrgerservice/Rathaus-Service/Dienstleistungen/Existenzgr%C3%BCndung-Beratung-und-Informationen.php?FID=329.3442.1&ModID=10&kuo=1&sfwort=1)
- [LAGARDE1: Gründungsberatung und überwiegend kostenlose Angebote](https://lagarde1.de/startups/)
- [Händlerbund: VertragsCheck zum Festpreis](https://marketplace.haendlerbund.de/products/vertragscheck)
- [Händlerbund: Basic-Rechtstextpaket](https://www.haendlerbund.de/de/leistungen/mitgliedschaft/basic-mitgliedschaft)
- [IT-Recht Kanzlei: Rechtstextpakete](https://www.it-recht-kanzlei.de/schutzpakete.html)
- [Paddle: Merchant-of-Record-Preise](https://www.paddle.com/pricing)
- [Digistore24: Merchant-of-Record-Preise](https://www.digistore24.com/pricing/)
- [Digistore24: Kosten beim deutschen Reseller](https://help.digistore24.com/hc/de/articles/23694504392721-Kosten-bei-Digistore24-GmbH-Deutschland)
- [BAFA: Ausschluss überwiegender Rechtsberatung](https://www.bafa.de/SharedDocs/Downloads/DE/Wirtschaft/unb_flyer.pdf?__blob=publicationFile&v=2)
