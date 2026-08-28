# Konzept: Finanzierung der Demo-Phase über PayPal

Stand 28.08.2026. Dieses Dokument ersetzt das am 23.08.2026 entworfene und am
24./28.08.2026 fortgeschriebene Drei-Stufen-Modell vollständig.

> **Entschieden und umgesetzt:** Während der Demo-Phase gibt es genau einen
> freiwilligen Finanzierungsweg: den PayPal-Spendenknopf im Aufmacher der
> Website. Die Zahlung schaltet nichts frei, wird auf keinen späteren Kauf
> angerechnet und begründet keinen Anspruch auf Support, Vorabversionen,
> Nennung oder Mitsprache.

Der alte Entwurf wuchs auf drei Förderstufen, zwei Zahlungsanbieter, eine
Unterstützerseite, einen Werkstattbrief, einen Eintrag in der Anwendung und
eine Danksagungsliste. Nichts davon wird für die Demo-Phase gebraucht. Der
eingebaute PayPal-Weg löst den ursprünglichen Auftrag mit weniger Zusagen,
weniger Pflege und einer klareren Trennung vom späteren Verkauf.

> **Keine Rechts- oder Steuerberatung.** Die offene Steuerfrage steht in §6
> und im Arbeitsregister von `ROADMAP.md`. Sie ist
> kein Grund, wieder Gegenleistungen oder Förderstufen einzuführen.

---

## §1 Die Entscheidung

Die Demo bleibt kostenlos und vollständig. Wer die Weiterentwicklung
unterstützen möchte, kann auf der Startseite **„Mit PayPal spenden“** wählen.
Der Knopf führt zu diesem von PayPal gehosteten Zahlungsweg:

`https://www.paypal.com/donate/?hosted_button_id=D7T4A9VYU9MX4`

Der am 28.08.2026 sichtbare Ablauf ist:

1. **Einmalig** ist vorausgewählt.
2. PayPal bietet daneben **monatlich** und **jährlich** an.
3. Der Betrag ist frei wählbar.
4. Bezahlt werden kann über PayPal sowie per Debit- oder Kreditkarte.
5. Wer möchte, kann die PayPal-Gebühr zusätzlich übernehmen.

Das ist keine Förderplattform mit eigenen Stufen. Die drei Zeitmodelle sind
nur Zahlungsrhythmen desselben freiwilligen Beitrags; es gibt bei keinem davon
eine Gegenleistung.

**„Kein Abo“ bleibt wahr.** Solidon3D wird nicht auf Zeit freigeschaltet und
hört nach dem Ende einer wiederkehrenden Spende nicht auf zu funktionieren.
Die monatliche oder jährliche Wahl betrifft nur die freiwillige Zahlung, nie
den Zugang zur Anwendung.

---

## §2 Die harte Grenze zum Kauf

Die Spende ist weder Kauf noch Vorbestellung noch Anzahlung. Für jeden Betrag
und jeden Zahlungsrhythmus gilt:

- kein Lizenzschlüssel und kein Rabatt auf einen Lizenzschlüssel;
- keine Freischaltung und keine zusätzliche Funktion;
- keine Anrechnung auf den späteren Kaufpreis;
- keine Vorabversion und kein früherer Zugang;
- kein Anspruch auf Support oder eine Antwortzeit;
- keine Nennung auf der Website oder in der Anwendung;
- kein Werkstattbrief und keine Änderungsliste vorab;
- kein Einfluss auf die Reihenfolge der Entwicklung.

Damit braucht Solidon3D keinen Zustand „hat gespendet“. Die Anwendung kennt
weder die Person noch den Betrag oder den Zahlungsrhythmus. Ein späterer
Lizenzkauf läuft getrennt über den dafür vorgesehenen Merchant of Record und
zu dessen Bedingungen.

Die Formulierung auf der Website trägt diese Grenze bereits in ihrem ersten
Satz: **„Die Demo bleibt kostenlos.“** Der zweite Satz nennt den einzigen
Zweck der Zahlung: Weiterentwicklung, Tests und die nächste Version zu
finanzieren. Nirgendwo darf daraus „vorbestellen“, „früher bekommen“ oder
„jetzt unterstützen, später sparen“ werden.

---

## §3 Der technische Weg

Der Spendenknopf steht auf allen sechs Startseiten im Aufmacher. Auf breiten
Bildschirmen nutzt er den Platz unter dem Produktbild rechts neben dem
Download; auf schmalen Bildschirmen folgt er dem Download und steht vor dem
Bild. Er ist ein gewöhnlicher Verweis und kein eingebettetes PayPal-Widget.

Das hat vier beabsichtigte Folgen:

1. Beim Laden der Website geht **keine Anfrage an PayPal**. Erst ein
   ausdrücklicher Klick verlässt `solidon3d.de`.
2. Die Website verarbeitet keine Zahlungs- oder Kontodaten.
3. PayPal führt Betrag, Rhythmus und Zahlungsart auf seiner Seite.
4. Die Anwendung braucht weder Konto, Webhook, Datenbank noch Aktivierungsweg.

`tests/test_website.py` hält die Anschlussstelle fest: Jede Startseite enthält
genau einmal dieselbe PayPal-Adresse, und außer dieser ausdrücklichen
Außenadresse wird beim Seitenaufbau nichts von außen geladen.

**Nicht zu bauen:**

- kein Menüeintrag „Unterstützen“ in der Anwendung;
- keine eigene Förder- oder Unterstützerseite;
- kein selbst öffnender Hinweis und keine Klickzählung;
- kein Spendenkonto im Projekt und keine Spenderkennung im Lizenzschlüssel;
- keine Verwaltung wiederkehrender Zahlungen in Solidon3D;
- keine Danksagungsliste im Über-Dialog.

---

## §4 Was aus dem alten Modell entfällt

| Alter Bestandteil | Neuer Stand |
|---|---|
| Drei Stufen zu 5 / 10 / 15 € | gestrichen; Betrag frei wählbar |
| Rückenwind, Werkbank und Fundament | gestrichen; keine Stufennamen |
| Werkstattbrief, Änderungsliste und Wunschkanal | gestrichen; keine Gegenleistung |
| Nennung auf einer Unterstützerseite | gestrichen; keine Unterstützerseite |
| Nennung im Über-Dialog | gestrichen; kein Spenderzustand in der Anwendung |
| Förderstufe mit Lizenzschlüssel | gestrichen; Spende und Kauf bleiben vollständig getrennt |
| Weg A gegen Weg B bei der Schlüsselausgabe | gegenstandslos |
| Ko-fi, Steady oder GitHub Sponsors | gestrichen; PayPal ist bereits eingebaut |
| Zweiter Anbieter neben dem Merchant of Record | für die Demo-Finanzierung gestrichen |
| Freier Monatsbetrag je Plattform prüfen | gegenstandslos; PayPal führt den freien Betrag |
| Menüeintrag unter „Hilfe“ | gestrichen; der Weg steht sichtbar beim Download |
| Vorabversionen und §-327h-Prüfung dafür | gestrichen; § 327h bleibt nur ein Thema des späteren Verkaufs |
| Eigene Kündigungsseite für ein Stufenmodell | gestrichen; zu PayPals wiederkehrenden Spenden bleibt nur §6.2 |

Die alte Rechnung über Gebühren je Stufe, eine mögliche Umgehung des
Kaufpreises und den richtigen Zeitpunkt nach der ersten Kaufrate ist ebenfalls
gegenstandslos. Ohne Gegenleistung kann eine Spende keinen Kauf ersetzen.

---

## §5 Betrieb und Buchführung

PayPal ist für die Demo-Finanzierung der Zahlungsweg, aber kein Merchant of
Record für den späteren Softwareverkauf. Beides bleibt organisatorisch
getrennt:

| Vorgang | Zahlungsweg | Gegenleistung |
|---|---|---|
| freiwillige Unterstützung während der Demo | PayPal-Spendenknopf | keine |
| späterer Lizenzkauf | gesonderter Merchant of Record | dauerhafte Lizenz der gekauften Hauptversion |

Für die laufende Arbeit genügen vier Regeln:

1. Zahlung, PayPal-Gebühr, Erstattung und Auszahlung einzeln nachvollziehbar
   ablegen.
2. Keine Zuwendungsbestätigung oder Aussage über steuerliche Absetzbarkeit
   versprechen.
3. Spenden und spätere Verkäufe in der Buchführung getrennt auswertbar halten.
4. Den PayPal-Knopf nicht als Ersatz für die Bestellstrecke des Verkaufs
   verwenden.

Gewerbeanmeldung, Geschäftskonto, steuerliche Erfassung,
Produkthaftpflicht und die Rechtstexte werden durch den kleinen PayPal-Weg
nicht gegenstandslos. Sie gehören aber zum Geschäfts- und Verkaufsstart und
nicht in die Gestaltung eines Förderstufenmodells. Die offenen Arbeiten stehen
deshalb ausschließlich im Register von `ROADMAP.md`.

---

## §6 Was noch geprüft werden muss

### §6.1 Steuerliche Einordnung

Bis zur Auskunft des Steuerberaters werden die PayPal-Eingänge konservativ als
betriebliche Einnahmen erfasst. Zu klären ist, ob und wie freiwillige Zahlungen
ohne Gegenleistung umsatzsteuerlich einzuordnen sind. Diese Frage ändert den
sichtbaren Ablauf nicht und rechtfertigt keine Gegenleistung.

### §6.2 Wiederkehrende Spenden

Der gehostete PayPal-Knopf bietet neben der Einmalzahlung auch monatliche und
jährliche Zahlungen an. PayPal nennt diese wiederkehrende Spenden und lässt sie
sowohl vom Empfänger als auch vom Zahlenden in den Profileinstellungen ändern
oder beenden.

Eine eigene Kündigungsschaltfläche nach § 312k BGB ist für dieses Modell nicht
erforderlich. Die Vorschrift setzt ein Dauerschuldverhältnis voraus, das den
Unternehmer zu einer **entgeltlichen Leistung** verpflichtet. Hier gibt es
ausdrücklich keine Gegenleistung; die Zahlung ist eine unentgeltliche
Zuwendung im Sinne von § 516 BGB. Genau deshalb darf keine der Grenzen aus §2
später aufgeweicht werden. Sobald Solidon3D für eine wiederkehrende Zahlung
etwas schuldet, ist diese Einordnung neu zu prüfen.

Fundstellen: [§ 312k BGB](https://www.gesetze-im-internet.de/bgb/__312k.html),
[§ 516 BGB](https://www.gesetze-im-internet.de/bgb/__516.html) und PayPals
eigene Erläuterung
[„Wie akzeptiere ich Spenden mit PayPal?“](https://www.paypal.com/de/cshelp/article/wie-akzeptiere-ich-spenden-mit-paypal-help200).

Die Website weist am Spendenknopf auf die fehlende Gegenleistung hin; die
Widerrufsseite nennt den PayPal-Weg zum Ändern oder Beenden. Einen bestimmten
Rhythmus bewirbt Solidon3D nicht.

### §6.3 PayPal-Konto

Vor jeder Veröffentlichung wird nur geprüft, dass der gehostete Knopf noch
dem Konto **RS-Digital** und dem Zweck **„Spenden zur Weiterentwicklung von
Solidon3D“** zugeordnet ist. Eine Testzahlung ist dafür nicht erforderlich;
die gehostete Seite zeigt beides vor der Zahlung.

---

## §7 Abnahme der Demo-Finanzierung

Die Finanzierung der Demo-Phase ist fertig, wenn diese Aussagen wahr bleiben:

- Die Demo ist ohne Zahlung vollständig benutzbar.
- Jede der sechs Startseiten führt genau einmal zum selben PayPal-Knopf.
- Beim Laden der Website wird keine PayPal-Ressource eingebunden.
- Einmalig ist der unaufdringliche Standard; weitere Rhythmen verwaltet
  PayPal.
- Betrag und Zahlungsart werden nicht von Solidon3D verarbeitet.
- Keine Zahlung schaltet etwas frei oder wird auf einen Kauf angerechnet.
- Anwendung und Projektdateien enthalten keinerlei Spenderzustand.
- Verkauf und Spende bleiben zwei getrennte Wege.

Diese Punkte sind am 28.08.2026 technisch erfüllt. Offen ist nur die
steuerliche Einordnung aus §6.1. Sie erweitert das Modell nicht, sondern
sichert den bereits kleinen Weg ab.
