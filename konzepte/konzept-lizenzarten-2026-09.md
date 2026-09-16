# Konzept: Zwei Lizenzarten und die Preisstaffel zum Verkaufsstart

> **Stand 15.09.2026: Kern, Dienst, Vorratswerkzeug und Rechtstexte gebaut;
> die Website ausdrücklich zurückgenommen.** Anlass ist Roberts
> Planänderung an diesem Tag: private Lizenz 69 € ab dem 01.11.2026 und 99 €
> ab dem 01.02.2027, gewerbliche Lizenz 199 € und 249 € an denselben Tagen,
> beide als **Einmalkauf mit allen 1.x-Updates**. Damit bekommt Solidon eine
> Unterscheidung, die es bisher ausdrücklich nicht hatte — und ein Satz im
> Lizenzvertrag muss weg, der das Gegenteil verspricht.
>
> Dieses Dokument ist die fachliche Grundlage; die Arbeitspakete in §6 sind
> commit-fähig und gehören ins Register von `ROADMAP.md`, nicht hierher. Es
> ergänzt `konzept-veroeffentlichung-1.0.md` (§2 D, Rollenentscheidung Merchant
> of Record) und `konzept-aktivierungsserver-2026-08.md` (B2, der Kauffluss);
> **keines von beiden wird hier umgeworfen.**
>
> **Zwei Entscheidungen sind im Lauf des Tages gekippt**, und beide stehen
> unten als solche markiert: Entscheidung E (ein Geräteplatz → zwei für
> gewerblich, dazu die neue Entscheidung K) und die Website — Robert:
> „ganz zurücknehmen“. Die Seite bleibt preisfrei wie bisher, die
> Rechtstexte werden vorbereitet.

---

## §1 Ist-Zustand, am 15.09.2026 im Code nachgeschlagen

Sieben Befunde, jeder mit Beleg. Sie tragen die Entscheidungen in §2.

**1.1 Der Preis ist frei.** Die Website nennt keinen — sie sagt an drei
Stellen „Version 1.0 ist für den 1. November 2026 geplant. Sie ist noch kein
Angebot; Preis und Vertragsbedingungen werden vor ihrem Angebot
veröffentlicht" (`website/index.html:713`, `:318`, `:812`). Die 69 € in
`konzept-veroeffentlichung-1.0.md:274` stehen dort als „der Preis, den die
Seite heute nennt" und sind überholt; die 49/79 € weiter oben hat das Konzept
selbst als überholt markiert. **Die Preisstaffel bricht also keine
Ankündigung** — und weil noch kein Angebot draußen ist, auch keine
Preisbindung.

**1.2 Der Lizenzvertrag verspricht heute das Gegenteil.** `EULA.md:61`,
Abschnitt 3: *„Die gewerbliche Nutzung ist ausdrücklich eingeschlossen und
kostet nichts extra."* Ein Satz ohne Vorbehalt. Er ist über
`tools/make_legal.py` nach `website/eula.html:42` erzeugt — die Quelle ist das
Markdown, nicht das HTML. **Die Rechtstexte sind einsprachig deutsch**
(`DOCUMENTS` in `make_legal.py:48`: EULA, AGB, Widerruf, Datenschutz); die
sechs Sprachen betreffen die Produktseiten und die Oberflächenkataloge.

**1.3 Der Schlüssel kennt keine Lizenzart.** `Licence` trägt vier Felder —
`major`, `purchased_on`, `order`, `holder` (`app/core/activation/key.py:90`).
Die signierte Nutzlast ist dicht gepackt und in ihrer Länge streng geprüft:

| Byte | Inhalt |
|---|---|
| 0 | `FORMAT_VERSION`, heute 1 |
| 1 | Hauptversion |
| 2–3 | Tage seit dem 01.01.2026 |
| 4 | Länge der Bestellkennung |
| 5 … | Bestellkennung, ASCII |
| danach | Länge des Inhabers, dann der Inhaber, UTF-8 |

`_decode_payload` lehnt ab, wenn `len(payload) != holder_end`
(`key.py:190`) — **ein angehängtes Byte ist kein gültiger Schlüssel.** Ein
neues Feld geht deshalb nur über eine neue Formatversion. Die Version steht
zusätzlich im Klartext-Kopf (`SOLIDON3D-1-`), und `_normalise` verlangt genau
diesen Kopf (`key.py:110`).

**1.4 Dasselbe Layout steht ein zweites Mal in PHP.** Der Aktivierungsserver
zerlegt die Nutzlast selbst: `ord($payload[0]) !== 1`, dieselben Offsets für
`order` und `holder`, derselbe SHA-256-Digest über die Nutzlast
(`website/api/activation_common.php:583–603`). **Jeder Formatwechsel ist
zweiseitig** — Python und PHP, sonst aktiviert kein neuer Schlüssel.

**1.5 Der Vorrat entsteht offline, und das bleibt so.** Der
Lizenz-Hauptschlüssel liegt im Passwortmanager und auf Papier und betritt den
Server nie (`konzept-aktivierungsserver-2026-08.md`, Tabelle vor §B2).
`tools/make_licence_keys.py` erzeugt den Vorrat mit leerem `holder` und
Bestellkennungen der Form `POOL-XXXXXX-0001`; beim Kauf teilt `order.php`
idempotent zu. **Der Server kann nicht signieren** — also kann er eine
Lizenzart auch nicht nachträglich in einen Schlüssel schreiben.

**1.6 Ein Geräteplatz je Lizenz — und die Datenbank erzwingt ihn selbst.** `EULA.md:49` und `AGB.md`
versprachen „genau ein aktiver Geräteplatz je Lizenz“; der Dienst holte
**einen** Datensatz und verglich ihn, und ein
`UNIQUE INDEX one_active_device ON activations(licence_digest)` hielt die
Zusage eine Ebene tiefer fest. Dieser Index ist der eigentliche Fund des
Tages: Er hätte den zweiten Platz einer gewerblichen Lizenz als
`service_unavailable` scheitern lassen, obwohl die Zählung in
`activation_issue` ihn erlaubt — gefunden hat ihn der Test, nicht das Lesen
(Entscheidung E).

**1.7 Das Kaufdatum steuert schon heute Verhalten.**
`DEVICE_ACTIVATION_FROM = date(2026, 11, 1)` (`activation/__init__.py:163`);
ein Schlüssel mit `purchased_on` davor ist ein Bestandsschlüssel ohne
Geräteaktivierung, und `make_licence_keys.py` gibt ihn nur mit `--legacy`
und einzeln aus. Der Verkaufsstart und die Aktivierungspflicht sind derselbe
Tag.

---

## §2 Design-Entscheidungen

### A — Zwei Lizenzarten, **gleicher Funktionsumfang**

Die gewerbliche Lizenz kostet mehr und kann nicht mehr. Sie ist eine
Rechtsaussage, kein Funktionsschalter.

Der Grund steht auf der eigenen Website: „**Die Demo ist nicht beschnitten.**
Keine Wasserzeichen, keine gesperrten Funktionen" (`index.html:743`). Eine
beschnittene Privatversion nach diesem Versprechen wäre ein Bruch, und zwar
der sichtbarste, den dieses Projekt zur Verfügung hat. Der Fremdvorschlag
„B2B-exklusive Zusatzfunktionen" löst ein Problem, das Solidon nicht hat: Die
Trennung hält über den Vertrag, wie bei personal/commercial licences üblich.

**Was die technische Unterscheidung dann leistet** — sie ist nicht Zierde:
Ein Gewerbetreibender muss belegen können, dass sein Arbeitsplatz richtig
lizenziert ist. Steht die Art im signierten Schlüssel und im Über-Dialog, ist
der Beleg da, wo er gebraucht wird, und niemand muss eine Bestellmail suchen.

### B — Nutzlastformat 2, und Format 1 bleibt lesbar

Neue Schlüssel tragen `SOLIDON3D-2-`. Format 1 wird weiter gelesen und gilt
als **private Lizenz** — das ist die Bedeutung, die es beim Ausstellen hatte.
`_normalise` nimmt beide Köpfe an, `_decode_payload` verzweigt am ersten Byte.

Nach der Checkliste „Dateiformat ändern" aus `AGENTS.md`: Version erhöhen,
Migration schreiben, Beispiel der alten Version einchecken, Test, **ältere
Migrationen bleiben bestehen**. Ein Bestandsschlüssel — auch ein einzelner,
der als Freiexemplar herausging — muss in einem Jahr noch freischalten.

> **Abweichung beim Bauen, 15.09.2026:** Das kostet ein Feld mehr, als dieses
> Konzept vorsah — `Licence.format_version`. Der Grund stand erst beim
> Schreiben von `encode` da: `certificate.licence_digest` hasht die Nutzlast
> aus `encode`, und ein gelesener Bestandsschlüssel muss dabei **byteweise**
> seine ursprüngliche Nutzlast ergeben. Ohne das Feld wüsste `encode` nicht,
> in welchem Format zu schreiben ist; der Digest eines Format-1-Schlüssels
> wäre nach dem Lesen ein anderer als der, den der Server aus demselben
> Schlüsseltext bildet — und ein bereits ausgestelltes Zertifikat wertlos.
> Der Nachweis ist
> `test_a_format_one_key_keeps_the_digest_the_server_computed`; die Gegenprobe
> (`encode` schreibt immer das neueste Format) macht ihn rot.
>
> Zwei kleinere Folgen: `encode` **lehnt ab**, eine gewerbliche Lizenz in
> Format 1 zu schreiben, statt sie stillschweigend als privat zu führen — dort
> gibt es kein Feld dafür. Und `format_key` nimmt die Formatnummer für den Kopf
> aus der Nutzlast statt aus `FORMAT_VERSION`, sonst trüge ein Bestandsschlüssel
> vorn eine 2 und innen eine 1.

### C — Ein **Byte** für die Art, nicht ein Bit

Byte 4, direkt hinter dem Kaufdatum: `1` privat, `2` gewerblich. Ein Bit im
Hauptversionsbyte wäre kürzer und in fünf Jahren der Grund für ein Format 3.
254 freie Werte kosten nichts und nehmen einer Bildungs-, Behörden- oder
Mehrplatzlizenz den Formatwechsel ab.

### D — Zwei getrennte Vorräte, die Art steht beim Ausstellen fest

Aus §1.5 folgt es zwingend: Der Server kann nicht signieren, also muss die
Art aus dem Werkzeug kommen. `make_licence_keys.py --kind privat|gewerblich`,
die Bestellkennung trägt sie sichtbar (`POOL-C-XXXXXX-0001` für gewerblich),
und das private Archiv führt sie als eigenes Feld. Der Kauf-Webhook wählt am
Produkt des Zahlungsanbieters den passenden Topf.

**Die Folge ist Betriebsarbeit und wird benannt:** zwei Vorräte laufen
unterschiedlich schnell leer, und ein leerer Topf ist ein Kauf ohne
Lieferung. Der Schwellenwert-Alarm aus dem Aktivierungskonzept muss je Art
zählen.

### E — ~~Es bleibt bei **einem** Geräteplatz~~ → **zwei für gewerblich**

> **Am 15.09.2026 gekippt, und zwar begründet.** Die erste Fassung sagte: ein
> Platz für beide, die Frage nach mehreren sei eine eigene. Roberts Frage
> danach hat die Schwäche von Entscheidung A offengelegt: Wenn beide Lizenzen
> dasselbe können, sieht ein Gewerbetreibender für den dreifachen Preis
> **nichts** außer einem Satz im Vertrag. Das ist ehrlich und als Angebot
> schwach — die naheliegende Reaktion ist, die private Lizenz zu kaufen.
>
> Die Antwort ist nicht, die private zu beschneiden (das bricht „die Demo ist
> nicht beschnitten" und ärgert die Leute, die Solidon empfehlen), sondern der
> gewerblichen **Leistung** mitzugeben, die nichts am Programm sperrt. Sie
> steht in Entscheidung K; der Geräteplatz ist ihr technischer Teil:
> **privat einer, gewerblich zwei** (Robert: „2 Geräte pro gewerbliche
> lizenz").

Was von der alten Fassung bleibt: Die Zahl ist **eine** Zahl an **einer**
Stelle — `key.DEVICE_LIMITS`, gespiegelt als `ACTIVATION_DEVICE_LIMITS` im
Dienst, und `test_the_php_service_knows_the_same_formats_and_kinds` hält
beide zusammen. Rechtstexte, Handbuch und Über-Dialog nennen dieselbe Zahl.

### K — Die gewerbliche Lizenz bekommt vier Leistungen, keine Funktionen

Entschieden am 15.09.2026, aus der Tabelle, die Robert bestätigt hat:

| Leistung | Wo sie steht | Kostet |
|---|---|---|
| **Zwei Geräteplätze für bis zu zwei gleichzeitig arbeitende Personen** statt einem Platz für eine Person | `key.DEVICE_LIMITS`, Dienst, EULA 2, AGB §2 | zwei Geräteplätze; Nutzerumfang im Vertrag |
| **Support-Antwort in zwei Werktagen** | EULA 11a (neuer Abschnitt), AGB §2 | eine Verpflichtung, keine Technik |
| **Weitergabe innerhalb des Betriebs** | EULA 6 — die Lizenz gehört dem Unternehmen, nicht der beschäftigten Person | ein Absatz |
| **Rechnung auf die Firma mit USt-IdNr.** | AGB §4 | nichts, das macht der Merchant of Record |

**Der Funktionsumfang bleibt gleich** (Entscheidung A gilt unverändert). Keine
dieser fünf Leistungen sperrt etwas in der privaten Lizenz; alle fünf geben
der gewerblichen etwas dazu — das ist der Unterschied, auf den es ankommt.

> **Am 15.09.2026 auf vier Leistungen gekürzt, und zwei Fehler dabei gefunden.**
> Die fünfte Leistung — Sicherheitsupdates bis 31.10.2033 statt 2031 — ist nach
> der Rechtsprüfung desselben Tages gestrichen (Entscheidung Robert). Der Grund
> ist nicht die Verpflichtung an sich, sondern die Norm: **Der Cyber Resilience
> Act knüpft den Unterstützungszeitraum an das Produkt, nicht an den Vertrag**
> (Art. 13 Abs. 8: „Unbeschadet Unterabsatz 2 beträgt der Unterstützungszeitraum
> mindestens fünf Jahre“), und private wie gewerbliche Lizenz sind dasselbe
> Programm. Zwei verschiedene Fristen für eine Binärdatei lassen sich daraus nicht
> herleiten; eine freiwillig längere wäre erlaubt, aber sie war die verzichtbarste
> der fünf. Beide bleiben bei 31.10.2031 — genau fünf Jahre ab Verkaufsstart, und
> das ist der Bestand, der schon öffentlich stand.
>
> **Die umgekehrte Richtung war gefährlich und ist geprüft worden:** Roberts
> Zwischenvorschlag „privat 3, gewerblich 5“ hätte die private Lizenz unter das
> Produktminimum gesetzt und eine auf vier Website-Seiten veröffentlichte Zusage
> zurückgenommen. § 327e Abs. 3 BGB hätte das vor dem ersten Vertragsschluss noch
> erlaubt (öffentliche Äußerungen dürfen bis dahin berichtigt werden) — der CRA ab
> dem 11.12.2027 nicht mehr.
>
> **Und die zwei Fehler, die dabei auffielen, waren meine eigenen:**
> `tools/make_legal.py` erkennt als Listenzeichen nur `*` (`^\*\s+`) und kennt
> **keine Tabellen**. Die Aufzählung der zwei Lizenzarten stand deshalb als
> Absatz mit Bindestrichen im veröffentlichten Lizenzvertrag und die Tabelle der
> Mehrwerte als Zeile voller Pipes. `test_legal.py` war dabei grün — der Wächter
> prüfte, dass das HTML zum Markdown passt, nicht dass das Markdown darstellbar
> ist. Beides ist behoben, und der Wächter prüft es jetzt.

**Am 16.09.2026 klargestellt (Robert): Eine gewerbliche Lizenz gilt für bis zu
zwei Personen desselben Unternehmens, die gleichzeitig auf den beiden
freigeschalteten Rechnern arbeiten dürfen.** Die Beschränkung auf eine Person
gilt für die private Lizenz. Die bisherige Deutung als ein Arbeitsplatz auf
zwei Geräten war falsch. Die Zahl der Geräteplätze bleibt unverändert:
privat einer, gewerblich zwei. Eine gewerbliche Lizenz kann ebenso eine Person
auf zwei Geräten nutzen; weitere Personen brauchen zusätzliche Lizenzen.

**Was bleibt, steht zur fachlichen Prüfung** (RM-093), wie der ganze
Rechtstext — insbesondere die Zwei-Werktage-Frist, denn sie ist die einzige
der drei, die eine laufende Verpflichtung begründet.

### F — Der Server trägt die Art mit, er urteilt nicht über sie

`activation_common.php` lernt Format 2 und gibt die Art zur Zuordnung heraus.
Die Aktivierungslogik bleibt unberührt: gleiches Zertifikat, gleicher Platz,
gleicher Weg. Ein Server, der über Lizenzarten entscheidet, wäre eine zweite
Wahrheit neben dem signierten Schlüssel.

> **Präzisierung beim Bauen, 15.09.2026:** „Urteilt nicht" heißt nicht „prüft
> nicht". Eine Art, die der Dienst **nicht kennt**, lehnt er ab (`unknown_kind`,
> HTTP 409) — genau wie eine fremde Hauptversion. Das ist Formatvalidierung und
> keine Rechteentscheidung: Ein Client, der diese Art ebenfalls nicht kennt,
> könnte mit dem Zertifikat nichts anfangen, und der eine Geräteplatz wäre
> verbraucht. **Daraus folgt eine Betriebsregel** — eine neue Lizenzart wird
> auf dem Server ausgerollt, **bevor** der erste Schlüssel dieser Art
> ausgegeben wird.
>
> Und was noch **nicht** gebaut ist: das *Ablegen* der Art im
> Aktivierungsdatensatz. Der Dienst arbeitet durchweg mit dem Digest, die
> Lizenzfelder liest er nie; die Art in die Persistenz zu schreiben wäre ein
> Eingriff in die Tabellenstruktur, und der gehört nicht in ein Paket, dessen
> PHP auf dieser Maschine nicht laufen kann (§7).

### G — Gewerblich wird benannt, nicht versteckt

Im Freischaltdialog nach der Prüfung und im Über-Dialog: „Lizenziert für
Robert Schneider — gewerbliche Lizenz". Eine private Lizenz nennt sich
ebenso, sonst ist das Fehlen der Zeile die Aussage, und das ist nach Regel 18
die schlechtere Kodierung. Sechs Kataloge ziehen nach.

### H — Kein Ablaufdatum, und das ist eine Festlegung

Roberts Wahl ist der Einmalkauf mit allen 1.x-Updates. Also **kein
Ablauffeld in der Nutzlast**, keine Verlängerungsstrecke, keine wiederkehrende
Abrechnung. Das Feld wäre in zwanzig Minuten gebaut und danach die stille
Einladung, aus der gewerblichen Lizenz ein Abo zu machen — gegen „kein Abo,
kein Konto", das die Seite verspricht. Wer später ein Abo will, braucht ein
Format 3 und eine bewusste Entscheidung.

### I — Der Code kennt keine Preise

69, 99, 199 und 249 stehen in der Website, im Shop des Zahlungsanbieters und
in den AGB — **nicht** in Python. Die Anwendung erfährt vom Preis nichts, und
die Staffel zum 01.02.2027 ist damit eine Änderung an zwei Textstellen und
einem Shop-Produkt, kein Release.

### J — Falsche Lizenzierung sperrt nichts

Solidon prüft nicht, ob jemand gewerblich arbeitet. Es könnte es nicht, es
dürfte es nicht, und der Versuch wäre Telemetrie (ausdrücklich nicht gebaut).
Wer mit einer privaten Lizenz gewerblich arbeitet, verstößt gegen den
Vertrag, nicht gegen eine Programmsperre.

---

## §3 Preise und Termine

| Lizenz | ab 01.11.2026 | ab 01.02.2027 | Art |
|---|---|---|---|
| Privat | 69 € | 99 € | Einmalkauf, alle 1.x-Updates |
| Gewerblich | 199 € | 249 € | Einmalkauf, alle 1.x-Updates |

Beide Staffeln schalten am selben Tag. Der Einführungspreis gilt drei Monate.
Ein vor dem Stichtag gekaufter Schlüssel behält seinen Preis und seine
Updates — gestaffelt wird der Neukauf, nicht der Bestand (Roberts Wahl:
„Einmalkauf, Updates 1.x inklusive").

**Was daraus für die Rechtstexte folgt.** `EULA.md` Abschnitt 3 wird
umgeschrieben: Der Umfang der erlaubten Nutzung richtet sich nach der
erworbenen Lizenzart, Abschnitt 1 nennt beide Arten, und die Zusicherung
„kostet nichts extra" verschwindet. `AGB.md` §4 bekommt die zwei Produkte.
Beides ist **rechtlicher Text vor dem Verkaufsstart** und gehört nach RM-093
zur fachlichen Prüfung — ich entwerfe, freigegeben wird außerhalb.

---

## §4 Nicht-Ziele

- **Keine Dental-Edition, keine Floating-Lizenz, keine Jahreslizenz.** Die
  Marktvorschläge von außen sind nicht entschieden; sie stehen hier nur, damit
  niemand sie für beschlossen hält.
- **Keine gewerblich-exklusive Funktion** (Entscheidung A).
- **Keine Änderung an der Zahl der Geräteplätze** (Entscheidung E).
- **Kein eigener Lizenzschlüssel-Dienst eines Anbieters.** Lemon Squeezy
  erzeugt Schlüssel nur selbst, ohne Ed25519-Signatur, und sie schalten in
  Solidon nichts frei (`konzept-aktivierungsserver-2026-08.md:229`, am
  26.08.2026 nachgeprüft). Der beschlossene Weg bleibt der Kauf-Webhook auf
  den eigenen Vorrat.

  > **Am 15.09.2026 auf Roberts Frage erneut geprüft, und der Befund hält.**
  > Die Dokumentation nennt weiterhin keinen Weg, eigene Schlüssel
  > hochzuladen oder einen externen Generator aufzurufen; dafür gibt es einen
  > **offenen Feature-Request** in Lemon Squeezys öffentlichem Wünsche-Portal
  > („Call external license key generator“). Solange der nicht umgesetzt ist,
  > bleibt der eigene Vorrat der einzige Weg zu einem Schlüssel, den Solidon
  > offline prüfen kann.
  >
  > **Und der Grund, aus dem das kein Mangel ist:** Der Lizenz-Hauptschlüssel
  > liegt offline (§1.5). Ein Server, der signieren könnte, wäre bei Diebstahl
  > eine Quelle beliebig vieler gültiger Schlüssel. Für den Käufer sieht der
  > Weg gleich aus: Checkout bei Lemon Squeezy, Schlüssel per Mail.
- **Keine wiederkehrende Lizenzabfrage.** Die Offline-Fähigkeit steht und ist
  vertraglich zugesagt; ein „Nächster Check in 30 Tagen" wäre ein Rückschritt.

---

## §5 Leitplanken

- **Additiv, dann umschalten.** Format 2 entsteht neben Format 1; der alte
  Pfad bleibt lesend funktionsfähig und wird nicht abgebaut. Es gibt kein
  Umschalt-Paket, das Bestandsschlüssel entwertet.
- **Zwei Parser, ein Layout.** Python und PHP werden im selben Paket geändert
  und mit demselben Beispielschlüssel geprüft. `tests/test_activation_server.py`
  ist die Stelle, an der beide aufeinandertreffen.
- **Erwartetes Inkonsistenzfenster:** Zwischen P2 und P4 kennt der Kern Format
  2 und der Server nicht. Solange kein Vorrat in Format 2 ausgegeben ist,
  merkt das niemand — deshalb kommt P3 (Ausstellen) **nach** P4.
- **Rückfall:** Bis zum ersten ausgegebenen Format-2-Schlüssel ist jedes Paket
  ohne Datenfolgen zurücknehmbar. Danach nicht mehr — der Tag, an dem der
  erste gewerbliche Vorrat entsteht, ist die Grenze.

---

## §6 Umsetzungsplan

Jedes Paket endet mit grünem Tor und einem Commit.

| Paket | Inhalt | Umfang | Stand |
|---|---|---|---|
| P1 | Entscheidung festschreiben: dieses Konzept, `konzepte/README.md`, RM-092 fortschreiben, Registerpunkt RM-182 | S | **erledigt 15.09.** — 120 Tests grün |
| P2 | **Beide Parser in einem Zug**: `LicenceKind`, `Licence.kind` und `.format_version`, Format 2 mit weiter lesbarem Format 1 in `key.py`, dasselbe Layout in `activation_common.php`, acht neue Tests samt Gegenprobe, fünf Sprachkataloge | XL | **erledigt 15.09.** — Kern und Dienst nachgewiesen (§7) |
| P3 | Werkzeug: `--kind` als **Pflicht** in `make_licence_keys.py`, Kennungsschema `POOL-C-…`, Archivsatzformat 2 mit der Art (gegen den Schlüssel geprüft), die Archivkonstanten in `licence_archive.py` statt zweimal, `licence_admin.py` liest beide Formate und zeigt die Art | L | **erledigt 15.09.** — fünf Mutationen gefahren, alle rot |
| P4 | Oberfläche: Art im Über-Dialog („Lizenziert für … — gewerbliche Lizenz“), Handbuchabschnitt zur Platzzahl, `device_limit`-Meldung ohne feste Zahl — alles in fünf Katalogen | M | **erledigt 15.09.** |
| P5 | Rechtstexte: `EULA.md` 1, 2, 3, 5, 6 und der neue Abschnitt 11a (Support), `AGB.md` §2, §4, §7, beide Fassungsnummern, `make_legal.py` gelaufen — **Entwurf zur Prüfung, nicht zur Veröffentlichung** | L | **erledigt 15.09.** — 32 Tests grün |
| P6 | Website: Preiskasten mit zwei Spalten und Staffeldatum, FAQ „privat oder gewerblich?“ | M | **zurückgenommen** (Robert, 15.09.) — gebaut, im Browser geprüft und wieder auf HEAD gesetzt; die Seite bleibt preisfrei, bis der Verkauf näher ist |
| P7 | Doku: `app/core/activation/CLAUDE.md`, Handbuchabschnitt zur Freischaltung, Regeldatei nachziehen | S | offen |
| P8 | Die Art im Aktivierungsdatensatz ablegen | S | offen — der Dienst arbeitet durchweg mit dem Digest; der Nutzen ist Support-Komfort, der Eingriff eine Tabellenänderung |
| P9 | **Den laufenden Dienst migrieren:** `DROP INDEX one_active_device` einspielen, **bevor** der erste gewerbliche Schlüssel ausgegeben wird | S | offen — Betrieb, nicht Code |

> **Abweichung von der ersten Fassung, 15.09.2026:** P2 und das frühere P3
> (Server) sind **ein** Paket. Die Paketliste widersprach der eigenen
> Leitplanke in §5 („Python und PHP werden im selben Paket geändert"): Getrennt
> hätte P2 die Tests in `test_activation_server.py` rot gelassen, weil ein neu
> erzeugter Schlüssel Format 2 trägt und ein PHP, das nur Format 1 kennt, ihn
> ablehnt. Ein Schritt, der seine Tests rot lässt, wird nicht auf den nächsten
> gestapelt (`AGENTS.md`). Das Inkonsistenzfenster aus §5 gibt es damit nicht
> mehr — was dort steht, war der Plan, den die Leitplanke überstimmt hat.
>
> Der Platzhalter des Freischaltfelds ist ebenfalls vorgezogen (`SOLIDON3D-1-…`
> → `SOLIDON3D-…`): Er stand in denselben fünf Katalogdateien, die P2 ohnehin
> anfasst, und hätte bis P4 einen Hinweis gegeben, der für neue Schlüssel
> falsch ist.

**Verifikation je Paket**

| Paket | Wie geprüft |
|---|---|
| P2 | erledigt: 80 Tests in `test_activation.py`, 58 in `test_device_activation.py` und `test_activation_server.py`, 142 in `test_licences.py`/`test_activation.py`/`test_licence_boundary.py`, 203 in `test_translations.py` — alle Exit 0. Fünf Mutationen einzeln gefahren, alle fünf rot |
| P3 | `pytest tests/test_licence_admin.py -q`; zwei Vorratsläufe erzeugen keine doppelte Kennung über die Arten hinweg |
| P4 | `pytest tests/test_ui.py -q` offscreen; `test_translations` grün über alle sechs Kataloge |
| P5 | `pytest tests/test_legal.py -q` — der erzeugte HTML-Stand muss zum Markdown passen |
| P6 | `pytest tests/test_website.py -q`, dazu die Sichtprüfung nach `/website-review` |
| P8 | `pytest tests/test_activation_server.py -q` auf einer Maschine **mit** PHP |
| alle | vor dem Commit `/pruefen` vollständig und `/regelcheck` |

---

## §7 Der PHP-Nachweis — nachgeholt am 15.09.2026

> **Eingelöst.** PHP 8.5.10 (NTS, x64) liegt jetzt in einem Werkzeugordner außerhalb des Repositorys; die Prüfsumme des Archivs stimmte mit der von php.net veröffentlichten SHA-256 überein. Damit laufen die vier zuvor übersprungenen Serverfälle: **16 statt 10 bestanden**, und drei eigene Mutationen am PHP (Format 2 unbekannt, beide Offsets falsch) werden gefangen. Ein Format-1- und ein Format-2-Schlüssel gehen durch denselben Dienst und ergeben denselben Digest wie Python — `test_php_reads_both_key_formats_to_the_same_digest`.
>
> **Damit der Nachweis auf einer Maschine ohne PHP nicht verschwindet**, bleibt der Konstantenvergleich daneben stehen: Er liest die PHP-Quelle und hält `ACTIVATION_LICENCE_FORMATS`, `ACTIVATION_LICENCE_KINDS` und `ACTIVATION_DEVICE_LIMITS` gegen `key.READABLE_VERSIONS`, `LicenceKind` und `DEVICE_LIMITS`. Für den Betrieb heißt das: `php` muss im `PATH` liegen, damit die Suite die Serverfälle fährt — sonst überspringt sie sie mit Grund, und in der Linux-CI ist ein fehlendes PHP ein Fehler (`tests/php_probe.py`).

**Was vor dem Nachweis hier stand:** `php` fehlt auf dieser
Maschine — `tests/php_probe.py` überspringt die vier Serverfälle mit „PHP
fehlt" —, und die CI nimmt seit dem 14.09.2026 keinen Lauf mehr an (RM-176:
Zahlung oder Ausgabenlimit). Damit ist beides zu, was die Änderung prüfen
könnte.

Was **stattdessen** geprüft ist: `test_the_php_service_knows_the_same_formats_and_kinds`
liest die PHP-Quelle und vergleicht ihre drei Konstanten gegen
`key.READABLE_VERSIONS` und `LicenceKind`. Das fängt ein Auseinanderlaufen der
beiden Parser und läuft auch ohne PHP — die Gegenprobe (Format 2 aus der
PHP-Konstante entfernen) macht ihn rot. Es ist kein Ersatz für einen echten
Lauf: Ein Syntaxfehler oder ein Offset-Fehler in der PHP-Verzweigung bliebe
unentdeckt.

**Zu tun, sobald eine Maschine mit PHP oder die CI wieder da ist:**
`pytest tests/test_activation_server.py -q` und dabei je einen Format-1- und
einen Format-2-Schlüssel durch beide Parser schicken; die Digests müssen
gleich sein.

**Übergabe-Notizen** werden hier fortgeschrieben, Commit-Hashes nachgetragen,
Abweichungen vom Konzept ausdrücklich als solche markiert.
