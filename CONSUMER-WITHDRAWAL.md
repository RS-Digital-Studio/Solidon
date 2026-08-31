# Prozessakte Online-Widerruf — Solidon

Stand: 31. August 2026 · Prozessfassung 1.0

**Freigabestatus: GESPERRT.** Ab dem 1. November 2026 wird ein
Verbrauchervertrag nicht online angeboten, solange die Widerrufsfunktion nach
§ 356a BGB nicht im tatsächlichen Checkout, Bestellbestand und Mailweg Ende zu
Ende abgenommen ist. `WIDERRUF.md` bleibt die Belehrung; diese Akte beschreibt
den technischen und betrieblichen Nachweis.

## Öffentlicher Zwei-Schritt-Weg

Die Website hält vom Vertragsschluss bis zum Ende der Widerrufsfrist eine
ständig verfügbare, hervorgehoben platzierte und leicht zugängliche Funktion
**„Vertrag widerrufen“** bereit. Sie ist ohne Konto und ohne Anmeldung
erreichbar und führt zu einer eigenen Seite.

Schritt 1 erfragt nur, was zur Zuordnung und Erklärung erforderlich ist:

- Name des Verbrauchers,
- eindeutige Bestell-/Vertragskennung,
- E-Mail-Adresse oder anderes bei der Bestellung verwendetes
  Kommunikationsmittel,
- eindeutige Erklärung, welcher Vertrag widerrufen wird.

Kein Pflichtfeld verlangt einen Grund, Telefon, neue Marketingeinwilligung,
Passwort oder unnötige besondere Daten. Der Weg erklärt Fehler als
Handlungsvorschlag und bewahrt Eingaben bei behebbaren Fehlern.

Schritt 2 heißt **„Widerruf bestätigen“** und zeigt die eingegebenen Angaben,
die Rechtsfolge und den eindeutig beschrifteten Bestätigungsknopf. Erst dieser
POST löst den Widerruf aus. GET, Link-Vorschau, Crawler oder Reload dürfen
keine Erklärung absenden. Ein CSRF-/Replay-Schutz darf den kontolosen Zugang
nicht in ein verstecktes Konto verwandeln.

## Serververtrag und Beweis

Der Server nimmt ausschließlich HTTPS und POST mit harter Body-/Feldgrenze an,
validiert Herkunft und Kodierung, begrenzt Versuche und schreibt atomar:

- unveränderliche Widerrufskennung,
- Empfangszeit in UTC und für den Kunden lesbare Ortszeit,
- übermittelte Erklärung und Vertragszuordnung,
- Version der angezeigten Oberfläche/Belehrung,
- Zustellstatus der Eingangsbestätigung,
- Bearbeitung, Erstattung, Zahlungsmittel und Abschlusszeit,
- Fehler-/Wiederholungsbeleg ohne Geheimnisse.

Die Bestätigung wird unverzüglich auf einem dauerhaften Datenträger an die
angegebene beziehungsweise bereits zum Vertrag bekannte Adresse gesendet. Sie
nennt Eingang, Zeitpunkt, Inhalt, Widerrufskennung und Kontaktweg. Eine
vorübergehend gescheiterte Mailzustellung verwirft den wirksam eingegangenen
Widerruf nicht; sie erzeugt Alarm und wiederholbare Zustellung.

### Verbindlicher Endpointvertrag

Der sichtbare Einstieg ist `/widerruf.html`. Er sendet per
`application/x-www-form-urlencoded` an
`POST /api/withdrawal.php?do=preview`. Erlaubte Felder sind exakt:

- `order_id`: 1–80 Zeichen,
- `name`: 1–120 Zeichen,
- `contact`: syntaktisch gültige E-Mail-Adresse bis 254 Zeichen,
- `declaration`: fester Wert `withdraw_entire_contract`,
- `language`: eine der sechs ausgelieferten Sprachkennungen.

Die Vorschau verändert keinen Vertrag. Sie antwortet mit einer
Bestätigungsseite und einem kurzlebigen, zufälligen, serverseitig nur gehasht
gespeicherten `draft_token`. Der Token bindet unveränderlich alle fünf Felder,
Ausgabeversion und Ablaufzeit; er enthält selbst weder Kontakt noch Bestellung
im Klartext.

Die Seite sendet ausschließlich
`POST /api/withdrawal.php?do=submit` mit `draft_token` und der festen Handlung
`confirm_withdrawal`. Der Server verbraucht den Token atomar, legt den
unveränderlichen Eingangsbeleg an und antwortet mit Widerrufskennung und
Empfangszeit. Wiederholung desselben Tokens liefert denselben Erfolg, erzeugt
aber keinen zweiten Widerruf. Andere Methoden, doppelte/fremde Felder,
abweichende Origin, ungültige Kodierung, mehr als 8 KiB Body und abgelaufene
Tokens werden mit begrenzter, handlungsfähiger Antwort abgewiesen.

Produktivbetrieb erfordert eine außerhalb des Webroots liegende Datenbank,
einen getrennten HMAC-/Verschlüsselungsschlüssel, kanonische öffentliche
HTTPS-Origin, erreichbare Mailzustellung, Betreiberempfänger und eine
Bestellauflösung. Fehlt eine Voraussetzung, antwortet der Endpoint 503 und der
Verkauf bleibt gesperrt. `HTTP_HOST`, Query-Parameter und Kundeneingaben bauen
keine Mail- oder Bestätigungslinks.

## Frist, Zuordnung und Missbrauch

Der Server nimmt eine rechtzeitig abgesendete Erklärung beweissicher entgegen;
er entscheidet nicht allein anhand einer ungenauen Browseruhr. Ein unbekannter
oder abweichender Vertrag wird als Prüffall gespeichert und mit einem
Handlungsvorschlag bestätigt, nicht still verworfen. Doppelte Sendungen werden
idempotent derselben Sache zugeordnet.

Rate-Limits, CSRF-Schutz und Zuordnungsfragen schützen vor Missbrauch, dürfen
aber eine rechtmäßige Erklärung nicht unangemessen erschweren. Protokolle
enthalten keine vollständigen Zahlungsdaten oder Aktivierungsschlüssel.

## Folgen und Betriebsablauf

1. Eingang sofort bestätigen und Frist sichern.
2. Bestellung, Zustimmung nach § 356 Abs. 6 und Vertragsbestätigung prüfen.
3. Erstattung grundsätzlich über dasselbe Zahlungsmittel ohne Zusatzentgelt
   veranlassen und Frist überwachen.
4. Aktivierung/Lizenzfolge nur auf vertraglich und gesetzlich tragfähiger
   Grundlage ausführen; Beweisdaten nicht mit operativer Nutzung vermischen.
5. Merchant of Record und RS Digital müssen Rollen, Weiterleitung,
   Bearbeitungszeit, Nachweisexport und Ausfallweg vertraglich festlegen.
6. Betroffenen- und Aufbewahrungsrechte nach `PRIVACY-COMPLIANCE.md` anwenden.

## Abnahmetest und Handoff

Der Website-/Checkout-Eigentümer setzt exakt die beiden sichtbaren Bezeichner,
sechs Sprachen und den POST-Vertrag um. Der End-to-End-Test deckt mindestens:

- [ ] anonymer Desktop-/Mobilweg und Tastatur/Screenreader,
- [ ] ständig verfügbar, hervorgehoben platziert und leicht zugänglich,
- [ ] gültiger Vertrag, unbekannte Kennung und korrigierbare Eingabe,
- [ ] GET/Crawler sendet nichts; POST sendet genau einmal,
- [ ] doppelte Sendung bleibt idempotent,
- [ ] Server-/Mailausfall verliert den Eingang nicht,
- [ ] UTC-/Ortszeit, Widerrufskennung und Inhalt in dauerhafter Bestätigung,
- [ ] Merchant-/direkter Verkäuferweg und Nachweisexport,
- [ ] Erstattungsfrist, Aktivierungsfolge und Lösch-/Aufbewahrungsregel.

Bis der reale Checkout mit echten Testbestellungen und Mailzustellung abgenommen
ist, dürfen Website und AGB keinen betriebsbereiten Verkauf behaupten.
