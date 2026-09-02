# Antworten auf die Fragen an die Kanzlei (Recherche vom 02.09.2026)

Recherchiert an den Primärquellen, Stand 02.09.2026: Gesetzestexte auf
gesetze-im-internet.de, Verordnungen aus dem Amtsblatt über den Cellar-Dienst
des Amts für Veröffentlichungen, Kommissionsleitlinien, Paddles eigene
Vertrags- und Preisseiten. Keine Rechtsberatung. Jede Antwort nennt, wie sicher
sie ist und was die Kanzlei noch bestätigen muss. Umgesetzt ist, was sich ohne
Anwalt umsetzen lässt; der Rest steht als Frage oder Entscheidung dabei.

Sachverhalt: RS Digital, Robert Schneider, Einzelunternehmer in Bamberg.
Solidon3D, Desktop-Anwendung zum Zeichnen, Ändern und Optimieren von
3D-Modellen mit Übergabe an den Slicer. Heute die kostenlose, befristete Demo
0.3.0 (bis 30.10.2026) mit freiwilligem Spendenknopf, Verkauf ab 01.11.2026.

## 1. CRA-Meldeweg ab dem 11.09.2026

**Rechtsgrundlage.** Verordnung (EU) 2024/2847. Art. 3 Nr. 22: „Bereitstellung
auf dem Markt" ist „die entgeltliche oder unentgeltliche Abgabe eines Produkts
mit digitalen Elementen zum Vertrieb oder zur Verwendung auf dem Unionsmarkt
im Rahmen einer Geschäftstätigkeit". Art. 3 Nr. 13: Hersteller ist, wer das
Produkt unter seinem Namen vermarktet, „sei es gegen Bezahlung, zur
Monetarisierung oder unentgeltlich". Erwägungsgrund 15: Spenden ohne
Gewinnabsicht sind keine Geschäftstätigkeit, Gewinnerzielungsabsicht schon.
Die Privilegierung für freie und quelloffene Software (Erwägungsgründe 18, 19,
Art. 3 Nr. 48) gilt nicht: Solidon3D ist keine FOSS.

Art. 14: Aktiv ausgenutzte Schwachstellen und schwerwiegende Sicherheits-
vorfälle werden „gleichzeitig dem CSIRT und der ENISA" über die einheitliche
Meldeplattform gemeldet. Frühwarnung innerhalb von 24 Stunden, Meldung
innerhalb von 72 Stunden, Abschlussbericht spätestens 14 Tage nach
Bereitstellung der Korrektur (bei Vorfällen ein Monat nach der 72-Stunden-
Meldung), jeweils ab Kenntnis. Zuständig ist der CSIRT des Mitgliedstaats der
Hauptniederlassung, also das BSI (Art. 14 Abs. 7). Nutzer sind unverzüglich zu
informieren (Abs. 8). Art. 71 Abs. 2: Art. 14 gilt ab dem 11.09.2026; Art. 69
Abs. 3: auch für Produkte, die vor dem 11.12.2027 in Verkehr gebracht wurden.
Art. 18: ein Bevollmächtigter ist eine Kann-Regelung für EU-Hersteller.

**Anwendung.** Die Demo wird regelmäßig, unter Marke, über eine gewerbliche
Website und mit dem erklärten Zweck verteilt, dasselbe Produkt ab 01.11.2026 zu
verkaufen. Nach Wortlaut und Blue Guide (Abschnitt 2.2: „business related
context", Regelmäßigkeit, Absicht) ist sie damit **schon heute auf dem Markt
bereitgestellt**. Der Spendenknopf ändert daran nichts, weder zum Guten noch
zum Schlechten. Gegenlesart: eine befristete, unentgeltliche Vorstufe sei
keine Geschäftstätigkeit; die Kommissionsleitlinie (C(2026) 5252, Rn. 13 f.)
stützt das nur für unfertigen Code und Schulungsbeispiele.

**Folge.** Ab dem 11.09.2026 gilt Art. 14 für Solidon3D. Die übrigen
Herstellerpflichten (Anhang I, CE-Kennzeichnung, Unterstützungszeitraum am
Produkt) greifen erst ab dem 11.12.2027 und dann für jede neu in Verkehr
gebrachte Version.

**Umgesetzt.** `SECURITY-INCIDENT.md` trägt die CRA-Uhr mit den richtigen
Fristen und nennt das BSI als CSIRT; `SECURITY.md` und die sechs
Sicherheitsseiten der Website sagen, dass ab dem 11.09.2026 nach Art. 14
gemeldet und informiert wird. Die Zeitnull ist als „hinreichend sichere
Kenntnis der aktiven Ausnutzung" definiert.

**Offen, außerhalb des Repositorys.** EU-Login anlegen, RS Digital auf der
ENISA-Plattform registrieren (Robert als Primary, eine zweite erreichbare
Person als Secondary für die 24-Stunden-Frist), den Probelauf aus der
Checkliste in `SECURITY-INCIDENT.md` fahren. Ein förmlicher Bevollmächtigter
ist nicht nötig.

**Sicherheit.** Mittel bis hoch für „Demo ist Bereitstellung" (Wortlaut klar,
behördliche Auslegung für befristete Demos fehlt); hoch für Fristen,
Zuständigkeit und Übergang. Die Kanzlei bestätigt die Einordnung der Demo und
ob das BSI Registrierungshinweise veröffentlicht hat.

## 2. § 356 BGB: Absatz 5 oder Absatz 6

**Rechtsgrundlage.** § 356 BGB in der Fassung ab 19.06.2026 (Gesetz zur
Änderung des Verbrauchervertrags- und des Versicherungsvertragsrechts, BGBl.
2026 I Nr. 28). Absatz 5 regelt Dienstleistungen. Absatz 6 regelt „Verträge
über die Bereitstellung von nicht auf einem körperlichen Datenträger
befindlichen digitalen Inhalten" und nennt in Nummer 2 für entgeltliche
Verträge **vier** Voraussetzungen: a) der Unternehmer hat mit der Erfüllung
begonnen, b) der Verbraucher hat ausdrücklich zugestimmt, dass vor Ablauf der
Widerrufsfrist begonnen wird, c) er hat seine Kenntnis bestätigt, dass sein
Widerrufsrecht damit erlischt, d) der Unternehmer hat die Bestätigung nach
§ 312f zur Verfügung gestellt. § 312f Abs. 3: die Bestätigung hält Zustimmung
und Kenntnisbestätigung fest. Bis zum 27.05.2022 stand die Regelung in Absatz 5
mit zwei Voraussetzungen; ältere Aufsätze und das LG Karlsruhe (28.01.2022,
3 O 108/21) zitieren deshalb noch „Abs. 5".

**Antwort.** „§ 356 Abs. 6 BGB" in `AGB.md` war richtig. Falsch war die
Widerrufsbelehrung: Sie nannte drei Voraussetzungen und sprach von
„Lieferung", das Gesetz sagt „Bereitstellung" und nennt vier.

**Umgesetzt.** `WIDERRUF.md` zählt die vier Voraussetzungen in der Reihenfolge
des Gesetzes auf und zitiert § 356 Abs. 6 Nr. 2 BGB; `AGB.md` § 6 nennt alle
vier und die getrennte Abfrage; `tests/test_legal.py` hält die Zitierung fest
und dokumentiert die Fassung. Seiten neu erzeugt.

**Für den Checkout.** Kästchen, nicht vorangekreuzt, eigene Zeile, getrennt vom
AGB-Kästchen, unmittelbar über der Schaltfläche „Zahlungspflichtig bestellen"
(§ 312j Abs. 3 BGB): „Ich stimme ausdrücklich zu, dass der Verkäufer mit der
Bereitstellung des Lizenzschlüssels vor Ablauf der Widerrufsfrist beginnt. Mir
ist bekannt, dass mein Widerrufsrecht mit Beginn der Bereitstellung erlischt."
Darunter: „Ohne Häkchen erhalten Sie den Schlüssel nach Ablauf der 14-tägigen
Widerrufsfrist." Die Auftragsbestätigung wiederholt Zustimmung und Kenntnis mit
Datum und Uhrzeit (§ 312f Abs. 2 und 3). Das LG Karlsruhe hat eine Kurzform
mit einem Kästchen für beides unbeanstandet gelassen; Voraktivierung ist
unzulässig.

**Offen.** Wird über einen Merchant of Record verkauft, ist dieser der
Unternehmer, der zustimmen lässt und bestätigt. `AGB.md` § 6 und `WIDERRUF.md`
sagen heute „wir"; vor dem Verkaufsstart auf den tatsächlichen Verkäufer
umstellen (siehe 3).

**Sicherheit.** Hoch für Absatz und Voraussetzungen; mittel für den
Kästchentext (kein amtliches Muster gefunden). Die Kanzlei prüft den
Zustimmungstext des gewählten Zahlungsanbieters gegen Buchstaben b bis d.

## 3. Merchant of Record

**Rechtsgrundlage und Befund.** Paddles Buyer Terms (Stand 31.03.2026):
„Paddle is an authorised reseller of Products for Suppliers, which means you
purchase the Product from Paddle." Vertragspartner für EU-Käufer ist
Paddle.com Market Limited, London. Das Produkt wird „under the terms of their
Supplier Agreement" bereitgestellt, unsere EULA gilt also als Lizenzvertrag
neben Paddles Kaufbedingungen. Paddle ist Rechnungsaussteller und
Umsatzsteuerschuldner; unsere Leistung an Paddle ist eine grenzüberschreitende
Unternehmerleistung im Reverse-Charge-Verfahren. Widerruf und Erstattung
bearbeitet Paddle (Refund Policy: 14 Tage in EU, EWR, Schweiz und UK; Ausnahme
digitale Inhalte nach Download mit Zustimmung). Gebühr: 5 % plus 0,50 US-Dollar
je Transaktion.

§ 356a BGB (elektronische Widerrufsfunktion, in Kraft seit 19.06.2026)
verpflichtet den Unternehmer eines Online-Fernabsatzvertrags zu einer ständig
verfügbaren Funktion „Vertrag widerrufen" mit Bestätigungsschritt „Widerruf
bestätigen" und Eingangsbestätigung mit Datum und Uhrzeit. Bei Paddle als
Verkäufer ist das Paddles Pflicht auf Paddles Oberfläche. Paddles Changelog
enthält dazu keinen Eintrag; „Request refund" ist keine so beschriftete
Funktion.

**Was bei RS Digital bleibt.** Lizenzvertrag (EULA), Aktivierungsserver und
Support als eigener Verantwortlicher nach der DSGVO (Paddle ist für die
Checkout-Daten selbst Verantwortlicher; `DATENSCHUTZ.md` muss den Anbieter
nennen, sobald er gewählt ist), Aktualisierungspflicht praktisch, Produkthaftung
als Hersteller.

| Anbieter | Rolle | Gebühr 2026 | Sitz |
|---|---|---|---|
| Paddle | Reseller (Merchant of Record) | 5 % + 0,50 USD | UK/USA |
| Lemon Squeezy (Stripe) | Merchant of Record | 5 % + 0,50 USD, Zuschläge international, PayPal, Abos | USA |
| FastSpring | Merchant of Record | nur auf Anfrage | USA |
| Digistore24 GmbH | Reseller, stellt Rechnung, führt USt ab | 7,9 % + 1 € bis 400 €, darüber 4,9 % | Hildesheim |

**Empfehlung.** Vor dem 01.11.2026 schriftlich mit dem gewählten Anbieter
klären: Umsetzung von § 356a auf seiner Oberfläche, deutsche Lokalisierung von
Checkout und Belegen, Zustimmungstext nach § 356 Abs. 6 Nr. 2 lit. b und c,
Bestätigungsmail nach § 312f, Auftragsverarbeitungsvertrag oder Bestätigung der
eigenen Verantwortlichkeit. `AGB.md` § 3, § 4 und § 6 sowie `WIDERRUF.md`
verkäuferneutral fassen („der Verkäufer, bei Verkauf über einen
Zahlungsanbieter dieser"). EULA-Link und Impressum im Produkt des Anbieters
hinterlegen.

**Sicherheit.** Hoch für Rollen, Steuer und Gebühren; mittel für § 356a bei
Paddle (unbelegt). Die Kanzlei prüft: UK-Verkäufer gegenüber deutschen
Verbrauchern (Rom I), §§ 327 ff. BGB im Verhältnis Paddle zu RS Digital.

## 4. Marke „Solidon3D" / „Solidon"

**Rechtsgrundlage.** § 4 MarkenG (Entstehung durch Eintragung), § 5 Abs. 2 und
3 (Unternehmenskennzeichen, Werktitel), § 12 und § 15 (ältere Rechte,
Kennzeichenschutz), § 42 (Widerspruch, drei Monate nach Veröffentlichung).
Gebühren DPMA (Merkblatt W 7731, Juli 2026): elektronische Anmeldung 290 € bis
drei Klassen, jede weitere Klasse 100 €, Widerspruch 250 €, Verlängerung 750 €.
EUIPO: 850 € für eine Klasse, 50 € für die zweite, 150 € ab der dritten;
Widerspruch 320 €.

**Befund.** Die Registerrecherche in DPMAregister, eSearch plus, TMview und
WIPO war aus dieser Umgebung nicht möglich (Browseranwendungen) und **steht
noch aus**. Über andere Wege gefunden: eine US-Marke SOLIDON (Reg. 1038144,
1975, Klasse 9, isolierter Wickeldraht, nur USA), ein niederländisches Gerüst-
und Schalungsbauunternehmen unter solidon.eu, ein erloschenes niederländisches
Kurierunternehmen; solidon.com ist geparkt. Nichts davon berührt Software in
Deutschland oder der EU. Von der Kanzlei zu bewerten bleibt die Nähe zur
„Solid"-Familie im CAD-Umfeld (SolidWorks, Solid Edge): Ähnlichkeit gering,
Inhaber klagestark.

**Schutz ohne Eintragung.** Als Unternehmenskennzeichen schwach, weil die Firma
RS Digital heißt. Tragfähiger ist der Werktitelschutz nach § 5 Abs. 3 MarkenG:
Der BGH („PowerPoint", I ZR 44/95) erkennt Programmnamen als titelschutzfähig
an, der Schutz entsteht mit Benutzungsaufnahme oder unmittelbar vorausgehender
werbender Ankündigung; „wetter.de" (I ZR 202/14) verlangt bei beschreibenden
Namen Verkehrsgeltung, „Solidon" ist ein Phantasiewort. Titelschutz seit
August 2026 ist plausibel; Belege der Benutzung sichern.

**Empfehlung.** Recherche von Hand in TMview nach „Solidon", „Solidon3D" und
phonetischen Varianten in den Klassen 9 und 42 (eine Stunde Arbeit). Ohne
Treffer: deutsche Wortmarke „Solidon" in Klassen 9 und 42 (290 €), bei
EU-Verkauf zusätzlich oder stattdessen Unionsmarke (900 €). Die Wortmarke
„Solidon" ist breiter als „Solidon3D". Preis für solidon.com erfragen.

**Sicherheit.** Hoch für Gebühren und Ablauf; mittel für den Werktitelschutz;
niedrig für das Kollisionsergebnis, weil die Register nicht durchsucht sind.

## 5. Impressum: Kontaktweg

**Rechtsgrundlage.** § 5 Abs. 1 DDG: Nr. 2 verlangt „Angaben, die eine schnelle
elektronische Kontaktaufnahme und eine unmittelbare Kommunikation mit ihnen
ermöglichen, einschließlich der Adresse für die elektronische Post"; Nr. 6 die
Umsatzsteuer-Identifikationsnummer oder Wirtschafts-Identifikationsnummer nur,
soweit vorhanden. EuGH, 16.10.2008, C-298/07 (deutsche internet versicherung):
Neben der E-Mail-Adresse sind „weitere Informationen" nötig, die eine schnelle
Kontaktaufnahme und eine unmittelbare und effiziente Kommunikation
ermöglichen; das muss „nicht notwendigerweise eine Telefonnummer" sein; eine
elektronische Anfragemaske genügt, wenn Anfragen innerhalb von 30 bis 60
Minuten beantwortet werden; wer nach elektronischer Kontaktaufnahme keinen
Netzzugang mehr hat, muss auf Wunsch einen nichtelektronischen Weg erhalten.
§ 5 DDG gilt für geschäftsmäßige Angebote; die Landesmedienanstalten lesen das
als „nachhaltig, mit oder ohne Gewinnerzielungsabsicht", die Demo mit
Produktpräsentation und Spendenknopf fällt darunter.

**Befund.** `website/impressum.html` nennt Name, Anschrift, E-Mail und den
Verantwortlichen nach § 18 Abs. 2 MStV. **Es fehlt der zweite Kontaktweg.** Ein
Kontaktformular hilft nur, wenn es binnen einer Stunde beantwortet wird; die
Sicherheitsseite verspricht zwei Arbeitstage, ein Formular gibt es bewusst
nicht. Der einfachste Weg ist eine Telefonnummer (IHK München: „am besten:
Telefonnummer und Emailadresse"). Der Kleinunternehmer-Hinweis nach § 19 UStG
gehört in Rechnungen, nicht ins Impressum. § 18 Abs. 2 MStV ist erfüllt, aber
vermutlich nicht einschlägig (Changelog und Handbuch sind Produktinformation,
kein journalistisch-redaktionelles Angebot); der Eintrag schadet nicht. Eine
Sprache schreibt kein Gesetz vor; die Fußzeilen der fünf Fremdsprachen
verlinken das deutsche Impressum. Die Angaben sind sprachneutral, eine kurze
Seite je Sprache wäre der saubere Weg, ist aber nachrangig.

**Empfehlung.** Telefonnummer ins Impressum (Entscheidung Robert: welche
Nummer, welche Erreichbarkeit). USt-IdNr. oder W-IdNr. nachtragen, sobald
erteilt. Später je Sprachordner eine Impressumsseite.

**Sicherheit.** Hoch für Kontaktweg und Pflichtangaben; mittel für die
Sprachfrage. Die Kanzlei bestätigt, dass eine Mobilnummer mit Sprechzeiten als
„unmittelbare Kommunikation" genügt.

## Nebenbefunde aus derselben Recherche, nachrangig

Diese Punkte hat die Recherche zu Frage 1 miterfasst. Sie sind keine Aufgabe,
solange die Kanzlei sie nicht anspricht; wo eine Zeile genügte, ist sie
umgesetzt.

- **Exportkontrolle.** Software für Industriedesign und Fertigung, darunter
  ausdrücklich CAD, steht in Anhang XXXIX der Verordnung (EU) Nr. 833/2014;
  Art. 5n Abs. 2b verbietet Verkauf, Lieferung und Bereitstellung an die
  Regierung Russlands und in Russland niedergelassene juristische Personen,
  einschließlich Updates (Kommissions-FAQ vom 06.02.2024). Natürliche Personen
  sind nicht Adressat, eine Geo-Sperre ist nicht vorgeschrieben, Art. 12
  verlangt Wissen oder Für-möglich-Halten. Die EULA hatte **keine**
  Sanktionsklausel; Nummer 7 trägt sie jetzt. Dual-Use: allgemein erhältliche
  Software fällt unter die Allgemeine Software-Anmerkung, keine
  Genehmigungspflicht. Ab dem Verkauf: Länder RU und BY beim Zahlungsanbieter
  und im Aktivierungsserver sperren, damit auch Updates erfasst sind.
- **GPSR.** Die Kommission bejaht in ihren FAQ die Anwendung auf eigenständige
  Software, der Verordnungstext trägt das nur über das Wort „Gegenstand",
  Gerichte haben nicht entschieden. Schutzgut ist die körperliche Sicherheit.
  Praktisch: Herstellername, Postanschrift und E-Mail „dem Produkt beigefügt"
  (Über-Dialog), eine kurze interne Risikoanalyse (`PRODUCT-SAFETY.md` führt
  sie als Kästchen), der Warnhinweis aus EULA Nr. 10 am Ort der Entscheidung.
- **KI-Verordnung.** RS Digital ist Anbieter des KI-Systems „Solidon-Chat",
  auch wenn der Nutzer seinen eigenen Schlüssel eingibt (Art. 3 Nr. 3 und
  Nr. 68). Art. 50 Abs. 1 gilt seit 02.08.2026; der Hinweis vor der ersten
  Interaktion ist für Anthropic und Ollama umgesetzt und getestet
  (`AI-COMPLIANCE.md`). Art. 4 (KI-Kompetenz) verlangt keine Schulung, eine
  interne Aufzeichnung genügt. Offen: Kennzeichnung eines aus SDXL erzeugten
  Zwischenbilds (Art. 50 Abs. 2), falls es angezeigt oder gespeichert wird.
- **Produkthaftungs-Richtlinie (EU) 2024/2853.** Software ist Produkt (Art. 4
  Nr. 1), gilt für Produkte, die nach dem 08.12.2026 in Verkehr gebracht
  werden; das deutsche Umsetzungsgesetz (BT-Drs. 21/4297) war am 02.09.2026
  noch nicht beschlossen. Vertragliche Haftungsbeschränkungen wirken gegenüber
  Geschädigten nicht (Art. 15); EULA Nr. 11 nennt das Produkthaftungsgesetz
  bereits ausdrücklich. Wichtig vor dem 01.11.2026: eine Betriebshaftpflicht
  mit Produkthaftpflicht, die Personen- und Sachschäden aus fehlerhafter
  Software einschließt (steht im Register). Mitgelieferte Bausteine und
  Beispiele sind „digitale Konstruktionsunterlagen", deren Hersteller RS
  Digital ist; sie im Handbuch als Demonstration kennzeichnen.

## Entscheidungen, die bei Robert liegen

1. Telefonnummer für das Impressum (welche, welche Zeiten).
2. Zahlungsanbieter (Paddle oder Alternative) und damit der Verkäufer in AGB
   und Widerrufsbelehrung.
3. Markenanmeldung: erst TMview-Recherche, dann deutsche Wortmarke oder
   Unionsmarke.
4. Zweite Person als Secondary für die ENISA-Plattform.

## Quellen

Die vollständigen Quellenlisten mit URLs stehen in den Recherchedateien
`kanzlei-A.md` (Fragen zu CRA, GPSR, KI-Verordnung, Exportkontrolle,
Produkthaftung) und `kanzlei-B2.md` (§ 356, Merchant of Record, Marke,
Impressum) der Sitzung vom 02.09.2026; die Kernquellen:

- BGB §§ 312f, 312j, 356, 356a auf gesetze-im-internet.de; Fassung ab
  19.06.2026 laut dejure.org und buzer.de (BGBl. 2026 I Nr. 28).
- § 5 DDG auf gesetze-im-internet.de; EuGH C-298/07 nach lexetius.com und
  medien-internet-und-recht.de; Leitfaden Impressum der Medienanstalt RLP
  (06/2024); IHK München „Impressum im Internet".
- Verordnung (EU) 2024/2847 über publications.europa.eu/resource/celex/32024R2847;
  Kommissionsleitlinie C(2026) 5252; Blue Guide 2022; ENISA-FAQ zur Single
  Reporting Platform.
- Verordnung (EU) Nr. 833/2014 konsolidiert 20.07.2025 und Verordnung (EU)
  2023/2878 über den Cellar; Kommissions-FAQ zu Art. 5n(2b) vom 06.02.2024.
- Paddle: checkout-buyer-terms, refund-policy, pricing (Stand 2026).
- DPMA Merkblatt W 7731 (Juli 2026), EUIPO Gebührenseiten; BGH I ZR 44/95
  „PowerPoint", I ZR 202/14 „wetter.de".
