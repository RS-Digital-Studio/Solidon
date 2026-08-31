# Sanktions- und Exportkontrollprozess — Solidon

Stand: 31. August 2026 · Prozessfassung 1.0

**Freigabestatus: GESPERRT.** Öffentlicher Verkauf, Aktivierung, Support und
gezielte Bereitstellung außerhalb des festgelegten Gebiets bleiben gesperrt,
bis Empfänger-, Eigentums-, Länder- und Endverwendungsprüfung dokumentiert
sind. Eine IP-Sperre allein ist kein Prüfverfahren.

## Geltungsbereich

Der Prozess gilt für Download, Kauf, Lizenzschlüssel, Aktivierung,
Offlineaktivierung, Update, Support, individuelle Dateiübermittlung,
Tauschbörse und technische Hilfe. Er gilt für unentgeltliche und entgeltliche
Bereitstellung sowie für direkte und mittelbare Empfänger.

Solidon ist allgemeine CAD-/3D-Konstruktionssoftware mit Kryptografie für
Signaturen, sichere Speicherung und Transport. Eine medizinische,
militärische, kerntechnische oder sonst besonders regulierte Zweckbestimmung
ist nicht vorgesehen. Eine Anfrage aus einem solchen Bereich löst eine
Einzelfallprüfung aus und wird bis zu deren Abschluss nicht bedient.

## Verbindliche Sperren

CAD-Software ist im Russland-Sanktionsrecht ausdrücklich erfasst. Leistungen,
die nach Art. 5n der Verordnung (EU) Nr. 833/2014 oder dem jeweils aktuellen
Anhang XXXIX verboten sind, werden nicht an die russische Regierung oder in
Russland niedergelassene juristische Personen, Organisationen oder
Einrichtungen erbracht. Gleiches gilt für Umgehung, mittelbare Bereitstellung
und kontrollierte Empfänger, soweit der aktuelle Rechtsakt dies erfasst.

Daneben werden jeweils aktuelle EU-Sanktionslisten, Eigentum und Kontrolle,
Embargos, sektorale Verbote, Endverwendung und Catch-all-Hinweise geprüft.
Belarus, Iran, Nordkorea, Syrien und weitere Zielgebiete werden nicht aus einer
statischen Liste freigegeben; maßgeblich ist der aktuelle Rechtsstand am Tag
der Entscheidung.

Ein Treffer, unklare Identität, verschleierte Eigentumskette, widersprüchliche
Adresse, ungewöhnlicher Vermittler, VPN-/Zahlungslandkonflikt, Weitergabe an
gesperrte Empfänger oder kritische Endverwendung führt zu **HOLD**. Es gibt
keine automatische Freigabe nach Zeitablauf.

## Prüfung vor Bereitstellung

Die private Prüfakte enthält mindestens:

1. Vorgangskennung, Datum, Prüfer und Vier-Augen-Freigabe,
2. Name/Firma, Anschrift, Land, Website und soweit vorhanden Registerdaten,
3. wirtschaftlich Berechtigte sowie Eigentum und Kontrolle,
4. Zahler, Vertragspartner, Nutzer, Empfänger und Vermittler,
5. Produkt, Version, Menge, Kanal und konkrete Leistung,
6. Endverwendung, Endnutzer und Weitergabeland,
7. verwendete amtliche Listen/Quellen samt Stand und Suchbegriffen,
8. Trefferbewertung, Rechtsgrundlage, Entscheidung und Auflagen,
9. Belege für Lieferung, Aktivierung, Support und spätere Änderungen.

Geprüft werden mindestens die konsolidierte EU-Finanzsanktionsliste, die
einschlägigen Länder-/Sektorverordnungen und bei deutschem Export die
Informationen des BAFA. Namensähnlichkeit wird nicht automatisch verworfen;
Geburts-/Registerdaten, Anschrift, Eigentum und Kontrolle werden abgeglichen.

## Technische Grenze

- Verkauf und Aktivierung erhalten keine globale „alle Länder“-Vorgabe.
- Offlineaktivierung ist keine Ausnahme: Der Dateiweg erbt dieselbe
  freigegebene Bestellung und Empfängerprüfung.
- Support, Updates und Downloadlinks dürfen keine gesperrte Leistung
  fortsetzen.
- Geo-IP, E-Mail-Domain, Kartenland und Sprache sind nur Signale; sie ersetzen
  keine Identitäts- oder Eigentumsprüfung.
- Ablehnungs- und Prüflisten enthalten keine unnötigen Kundendaten im
  Quellrepository oder Anwendungsprotokoll.
- Ein Merchant of Record oder Zahlungsdienstleister entbindet RS Digital nicht
  ohne ausdrücklichen Vertrag und Nachweis von den verbleibenden Pflichten.

## Dual-Use-Klassifizierung

Vor dem Verkaufsstart wird ein Klassifizierungsblatt geführt für:

- Solidon-Anwendung und Installationspakete,
- Kryptografiefunktionen und deren konkrete Verwendung,
- PyNaCl/libsodium, OpenSSL und weitere mitgelieferte Kryptokomponenten,
- technische Dokumentation, Quelltext- oder Debug-Zugänge,
- Supportleistungen und besonders sensible Endverwendungen.

Das Blatt nennt je Gegenstand Güterlistenposition/ECCN oder die begründete
Nichtlistung, verwendete Quelle, Rechtsstand, Prüfer und Datum. Eine
Anbieter-ECCN wird nur als Beleg übernommen, nicht erraten. Bei Unklarheit,
Catch-all-Hinweis oder kritischer Endverwendung wird vor Bereitstellung das
BAFA beziehungsweise qualifizierte Beratung einbezogen.

## Aufbewahrung, Monitoring und Vorfall

Prüf- und Lieferbelege werden nach den anwendbaren export- und
sanktionsrechtlichen Fristen, mindestens jedoch für die intern festgelegte
Prüffrist von zehn Jahren, geschützt aufbewahrt; längere gesetzliche Fristen
gehen vor. Zugriffe sind rollenbeschränkt und protokolliert.

Rechtsakte und Listen werden monatlich, zusätzlich vor jeder neuen Zielregion,
vor Reseller-/Merchant-Wechsel und bei jedem Warnsignal geprüft. Ein späterer
Treffer stoppt weitere Aktivierung, Update- und Supportleistungen, soweit dies
rechtlich geboten ist, und wird nach `SECURITY-INCIDENT.md` als
Compliance-Vorfall geführt.

## Freigabekriterien

- [ ] Vertriebsgebiete und ausgeschlossene Gebiete schriftlich festgelegt,
- [ ] Sanktionslisten-/Eigentumsprüfung vertraglich und technisch verankert,
- [ ] Dual-Use-Klassifizierungsblatt fachlich bestätigt,
- [ ] Rollen, Vier-Augen-Prinzip und Eskalationskontakt benannt,
- [ ] Testfälle Treffer, Namensähnlichkeit, Offlineaktivierung, Support und
      Umgehungsverdacht bestanden,
- [ ] Merchant-/Zahlungsdienstleistervertrag auf Rollen geprüft,
- [ ] monatliches Monitoring und Aufbewahrung technisch eingerichtet.

Bis alle Punkte mit privater Evidenz geschlossen sind, darf kein globaler
Vertrieb freigegeben oder als rechtssicher behauptet werden.
