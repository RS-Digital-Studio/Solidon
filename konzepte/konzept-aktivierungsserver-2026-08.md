# Konzept: Aktivierungsserver

> **Umsetzungsstand 28.08.2026:** Geräte-Zertifikat, genau ein aktiver
> Geräteplatz, Online- und Offline-Aktivierung, Deaktivierung sowie der
> Aktivierungsdienst sind gebaut. Die Verkaufsversion startet am 01.11.2026
> zunächst **ohne Testphase** (`TRIAL_FROM = None`). Aussagen dieses Entwurfs
> über einen gleichzeitig angebotenen Vierzehn-Tage-Test sind historische
> Planungsvarianten; der gehärtete Testpfad bleibt nur für einen später bewusst
> aktivierten Release erhalten.
>
> **Produktionsstand, gemessen am 28.08.2026:** Lokale Umsetzung, echter
> PHP-Anschlusstest und öffentlicher Bereitschaftsendpunkt sind grün (HTTPS
> 200, Protokoll 1). FTPS prüft den Hostnamen; Startwert und SQLite liegen in
> `solidon3d.de/appdata/` außerhalb des Webroots. Das Deployment sichert und
> liest vorhandene Dateien vor jedem Überschreiben bytegenau zurück. Offen
> bleiben der Kauf-Webhook des noch zu wählenden Zahlungsanbieters und der
> echte Kaufdurchlauf vor dem Verkaufsstart.

> **Stand: ENTWURF, 26.08.2026 — alle vier Teile ausgearbeitet, Abnahme offen.**
> Entschieden von Robert ist das *Ob* und die Reihenfolge; offen ist das *Wie*.
> Teil A (Kern), C (Sicherheit) und D (Bedienung) stammen aus den Sitzungen
> 46, ce und 43; Teil B (Server, Kauf, Recht) ist am 26.08.2026 nachgezogen,
> mit den Anbieter-Fähigkeiten am selben Tag gegen deren Unterlagen geprüft.
> Verbindlich wird davon nichts, bevor es Robert abgenommen und der Bauplan
> (§8/§36) nachgezogen ist. Gebaut wird **nicht vor 0.2.0** — 0.2.0 ist am
> 26.08.2026 erschienen; die Reihenfolge der Bauschritte steht in B7.

## Die Entscheidungen, von denen dieses Konzept ausgeht

Beide von Robert am 26.08.2026:

1. **Zum Verkaufsstart gibt es keine Testphase.** Die öffentliche Demo endet
   einschließlich 30.10.2026, startet am 31.10. nicht mehr, und die
   Verkaufsversion beginnt am 01.11.2026 mit `TRIAL_FROM = None`. Der
   Vierzehn-Tage-Pfad bleibt für ein späteres, bewusst neu geprüftes Angebot
   erhalten, ist aber weder Freigabe noch Schonfrist der Verkaufsversion.
2. **Es kommt ein echter Aktivierungsserver** — auf dem eigenen Webserver
   (netcup, solidon3d.de). Zuerst dieses Konzept, gemeinsam ausgearbeitet.

## Was ein Server kann, was lokal nicht geht

| Fähigkeit | lokal (heute) | mit Server |
|---|---|---|
| Marker editieren erkennen | ja (Unterschrift) | ja |
| Einen Marker-Ort löschen | ja (zweiter Ort heilt) | ja |
| Beide Testmarker löschen → neuer Test | **nein** (Restgrenze) | nicht benutzt — Verkauf startet ohne Test |
| Geteilten/geleakten Schlüssel begrenzen | nein | ja — Aktivierungen je Schlüssel zählen |
| Erstatteten Schlüssel widerrufen | nein | ja |

## Die Zusage, an der alles hängt: §2

„Ohne Netz, ohne Konto und ohne KI bleibt alles außer dem Chat benutzbar"
steht in `AGENTS.md`, auf der Website und sinngemäß in der EULA. Ein
Aktivierungsserver muss daran vorbeikommen, ohne sie zu brechen. Der Rahmen,
der auszuarbeiten ist:

- **Aktivierung braucht einmal Kontakt, Betrieb nie.** Nach der Aktivierung
  läuft alles offline weiter; keine wiederkehrende Prüfpflicht, kein
  Heartbeat, kein stilles Nach-Hause-Telefonieren (die Telemetrie-Grenze aus
  `kern.md` gilt unverändert: einen Netzzugriff löst der Kunde aus, oder es
  gibt ihn nicht — die bestehende Update-Prüfung beim Start ist deklariert
  und abschaltbar, sie ist die einzige Ausnahme und bleibt es).
- **Ein Offline-Weg existiert** für Kunden ohne Netz am Arbeitsrechner:
  Challenge-Response über einen zweiten Rechner oder E-Mail (Code hin,
  signierte Antwort zurück). Ohne diesen Weg bräche §2 wirklich.
- **Fällt der Server aus, verliert kein Kunde etwas.** Eine einmal erteilte
  Aktivierung gilt lokal weiter; der Server wird nur für *neue* Aktivierungen
  gebraucht. Für den Fall, dass es die Firma nicht mehr gibt, wird eine
  signierte Dauer-Freischaltung **vorbereitet, aber nicht ausgeliefert** —
  solange die Firma da ist, existiert sie nur offline, im Ernstfall kommt sie
  auf die Website. Warum sie nie vorab hinterlegt werden darf, begründet C6:
  Eine Datei, die auf jeder Maschine schaltet, wäre der Generalschlüssel, den
  der Offline-Weg gerade vermeidet (offene Frage 4, Roberts Ja/Nein steht aus).

## Teil A — Kern-Integration (3d-druck-46, ausgearbeitet)

**Zustandsmodell.** `Activation` kennt heute `licence`, `days_left`,
`damaged`, `deadline`. Dazu käme ein maschinengebundenes **Aktivierungs-
zertifikat**: eine vom Server signierte Aussage „Schlüssel K ist auf Maschine
M aktiviert, ausgestellt am T". Die App prüft es offline gegen einen
eingebauten öffentlichen Schlüssel — derselbe ed25519-Weg wie beim
Lizenzschlüssel selbst. `unlocked` verlangte dann Lizenz **und** Zertifikat
(mit Übergangsregel für Bestandsschlüssel, siehe unten).

**Schlüsselkette — der private Hauptschlüssel bleibt offline.** Der Server
darf **nie** den Schlüssel halten, der Lizenzen signiert: Ein gehacktes
Shared Hosting dürfte sonst Lizenzen ausstellen. Stattdessen ein eigenes
Server-Schlüsselpaar nur für Aktivierungszertifikate; sein öffentlicher Teil
reist in der App neben dem bestehenden. Kompromittierung des Servers
erlaubt dann schlimmstenfalls das Ausstellen von Aktivierungen für gültige
Schlüssel — nicht das Erfinden von Lizenzen. Widerruf des Serverschlüssels
über ein App-Update.

**Maschinen-ID.** Nötig für „Aktivierungen je Schlüssel zählen", heikel für
den Datenschutz. Vorschlag: kein Hardware-Fingerabdruck, sondern eine beim
ersten Start **zufällig erzeugte** ID im Profil (UUID). Sie identifiziert
keine Hardware und keinen Menschen; wer das Profil neu aufsetzt, ist eine
neue Maschine — und verbraucht eine Aktivierung, was das Limit trägt.
DSGVO-seitig das mildeste Modell (Pseudonym ohne Personenbezug beim
Aktivieren eines anonymen Schlüssels; Personenbezug entsteht erst über die
Bestellnummer — Teil B).

**Testphase über den Server? Nein.** Zum Verkaufsstart gibt es überhaupt
keine Testphase; deshalb registriert der Server auch keine. Ein späteres
Testangebot wäre ein eigener Release mit eigener fachlicher und rechtlicher
Abnahme, kein heute versteckter Schalter.

**Keine vorläufige Freischaltung.** Ein neuer Verkaufsschlüssel ab dem
01.11.2026 öffnet erst zusammen mit einem gültigen Geräte-Zertifikat. Eine
lokale Schonfrist ließe sich durch Entfernen und erneutes Eintragen oder durch
Kopieren des Profils zur Aktivierungsumgehung machen und würde die klare
Planänderung „keine Testphase" durch die Hintertür zurückbringen. Der Weg für
einen Arbeitsrechner ohne Internet ist stattdessen die signierte Anfrage- und
Antwortdatei über ein zweites Gerät. Nach diesem einmaligen Vorgang arbeitet
Solidon dauerhaft ohne Lizenzverbindung.

**Bestandskunden-Migration.** Bereits ausgegebene Schlüssel funktionieren
offline weiter (die App kann `purchased_on`/`major` lesen): Schlüssel mit
Kaufdatum vor `DEVICE_ACTIVATION_FROM = 01.11.2026` brauchen kein Zertifikat.
Kein Bestandskunde wird nachträglich zur Aktivierung gezwungen; der Stichtag
selbst ist durch Kern- und Grenztests belegt.

**Und der Stichtag muss vor dem Erzeugungstag des ersten Vorrats liegen**
(Fund der Durchsicht vom 26.08.2026): `purchased_on` wird beim Signieren
eingebrannt — ein Vorratsschlüssel trägt also den Tag seiner **Erzeugung**,
nicht den seines Verkaufs. Läge der Stichtag danach, wäre jeder verkaufte
Vorratsschlüssel formal ein Bestandsschlüssel, bräuchte nie ein Zertifikat,
und das Limit griffe für den gesamten Verkauf nicht — der Server stünde
umsonst da. `make_licence_keys.py --count` verweigert deshalb jeden vor dem
Stichtag liegenden Vorrat. Für den Verkaufsbestand muss der Ausstelltag mit
`--purchased-on 2026-11-01` gesetzt werden; ein Bestands-Einzelfall braucht
`--legacy` **und** eine Bestellkennung. Die Werkzeugtests belegen beide
Richtungen.

**Vier Grenzdateien bleiben vier.** Die Zertifikatsprüfung gehört in
`activation/` (im Cython-Prüfmodul), nicht in neue Grenzstellen.

**Warnschild für den Bauer: `Session.apply` meldet, es wirft nicht.** Es
fängt jeden `AppError` und schickt ihn über `failed` an die Oberfläche — ein
`try` um den Aufruf läuft ins Leere. Genau daran ist am 26.08.2026 ein
Fixversuch gescheitert (die liegengebliebene Quelle nach abgelehntem Import,
`1dbddbb4`): Der Aufrufer bekam keine Ausnahme, es entstand keine Operation,
und von außen sah es aus wie „nichts passiert". Wer den Aktivierungspfad an
die Sitzung anschließt und annimmt, eine Ablehnung komme als Ausnahme an,
baut denselben Fehler noch einmal — dann mit einem Netzaufruf dazwischen.
Gefragt wird nach dem **Ergebnis** (ist die Operation entstanden?), nicht
nach dem Grund.

## Teil B — Server, Kauffluss, Recht (ausgearbeitet 26.08.2026)

### B1 — Was auf dem Server heute steht, und was das für die Bauart heißt

Die Website liegt auf netcup-Webhosting (Plesk), Dokumentenstamm
`solidon3d.de/httpdocs`. Das ist Shared Hosting: **kein eigener Prozess, kein
Daemon, keine Warteschlange** — was dort läuft, ist PHP hinter dem Webserver,
und genau das läuft dort nachweislich seit dem 20.08.2026:
`api/support.php` nimmt die Rückmeldungen an, `dl/count.php` zählt die
Downloads. TLS liegt an (Let's Encrypt), hochgeladen wird über FTPS
(`tools/upload_website.py`, Zugang in `.webserver.json`).

**`support.php` ist die Vorlage, nicht nur ein Nachbar.** Eine Datei je
Endpunkt, PHP-Standardmittel, kein Composer, kein Framework; das Geheimnis
(dort das Postfach, hier der Server-Signierschlüssel) liegt auf dem Server
und reist nie in der Anwendung mit; jede Antwort ist JSON mit `ok` oder
einem benannten Grund — Regel 17 endet nicht an der Netzgrenze, der Client
übersetzt die Gründe in die Handlungsvorschläge aus D2.

Drei Dinge muss das Hosting können, und alle drei sind **festzustellen, nicht
anzunehmen** (B7):

- **ed25519.** Der Server prüft Lizenzschlüssel und signiert
  Aktivierungszertifikate — beides kann die PHP-Erweiterung `sodium`
  (`sodium_crypto_sign_verify_detached` / `sodium_crypto_sign_detached`),
  die seit PHP 7.2 zum Kern gehört. Ob das konkrete Plesk sie geladen hat,
  sagt eine Wegwerf-Prüfdatei; falls nicht, bietet Plesk die Erweiterungen
  je Domain zur Auswahl an.
- **Speicher.** SQLite über PDO, als **eine Datei außerhalb des
  Dokumentenstamms** (der FTPS-Zugang sieht `solidon3d.de/`, `httpdocs/`
  liegt darunter — daneben ist Platz, den HTTP nie erreicht). Gegen MariaDB
  spricht nicht das Können, sondern der Bedarf: Die Last sind einzelne
  POSTs, ein Backup ist eine Dateikopie, und es gibt kein
  Datenbankpasswort, das im PHP-Code läge. Ein `BEGIN IMMEDIATE` als
  Schreibschloss reicht bei dieser Last.
- **Post hinaus.** Die Kaufmail (B2) geht über denselben Weg wie die
  Support-Mail: eigene Absenderdomain, SPF beachtet. Die offenen
  DNS-Punkte (DMARC, TXT im CCP — ROADMAP) werden damit Teil dieses
  Vorhabens: Eine Kaufmail im Spam-Ordner ist ein Support-Fall je Kauf.

Was die Praxis über diesen Server weiß (gemessen von a2, 26.08.2026): Die
FTPS-Verbindung reißt bei langen Übertragungen, rund 1,8 MB/s. Für den
Betrieb der Endpunkte ist das unerheblich — einzelne kleine POSTs —, für die
Erwartung an Verfügbarkeit ist es ein Argument mehr für das, was C3 ohnehin
verlangt: Der Server darf nie Betriebsvoraussetzung sein. Und
`.webserver.json` nennt heute eine **IP statt eines Hostnamens**, womit der
Zertifikatsname beim Hochladen ungeprüft bleibt — für Website-Dateien eine
Warnung, für das Deployment eines Endpunkts, der Schlüssel entgegennimmt,
ein Sperrgrund. Der Eintrag wird vor dem ersten Upload umgestellt (B7).

Damit hält das Projekt künftig **drei Schlüsselpaare**, und die Aufteilung
ist die tragende Sicherheitsentscheidung aus Teil A/C2, hier nur
vervollständigt:

| Paar | privat liegt | signiert | Werkzeug |
|---|---|---|---|
| Lizenz-Hauptschlüssel | offline bei Robert (Passwortmanager + Papier) | Lizenzschlüssel, Widerrufsliste (C3) | `tools/make_licence_keys.py` |
| Release-Schlüssel | offline bei Robert | `website/version.json` | `tools/sign_version.py` |
| Server-Aktivierungsschlüssel | **auf dem Server**, außerhalb `httpdocs` | nur Aktivierungszertifikate | neu, nach dem Muster von `sign_version.py` |

Nur das dritte Paar liegt auf dem Server, und sein Diebstahl ist der von C2
bewertete und von C3 widerrufbare Fall. Die beiden Offline-Paare betreten
den Server nie.

### B2 — Der Kauffluss: Zahlungsanbieter, Schlüsselvorrat, Auslieferung

**Die Rollenentscheidung steht und wird hier nicht neu getroffen**
(`konzept-veroeffentlichung-1.0.md` §2 D): verkauft wird über einen Merchant
of Record. Der MoR ist rechtlich selbst der Verkäufer — er schuldet und
meldet die Umsatzsteuer im Land des Käufers, stellt die Rechnung, trägt
Widerrufsbelehrung und Betrugsprüfung im Checkout. Robert liefert den
Schlüssel und die Software, sonst nichts.

**Was sich seit jenem Konzept geändert hat, ist am 26.08.2026 nachgeprüft:
den Weg „Vorrat beim Anbieter hinterlegen, keine eigene Infrastruktur" gibt
es bei den zwei empfohlenen Anbietern nicht mehr.** Paddles „License List"
(Vorrat als Textdatei, Paddle liefert je Kauf einen aus) ist ausdrücklich
nur **Paddle Classic**; Neuanmeldungen laufen auf Paddle Billing, und dort
heißt Fulfillment: Paddle ruft nach dem Kauf eine Adresse des Verkäufers
auf (`transaction.completed`-Webhook), und der Verkäufer liefert selbst.
Lemon Squeezy wiederum erzeugt Lizenzschlüssel **nur selbst** — beliebige
Zeichenketten aus seinem Generator, die keine ed25519-Signatur tragen und in
Solidon nichts freischalten; einen eigenen Vorrat hochladen sieht die
Unterlage nicht vor. Die Folge ist keine Verlegenheit, sondern eine
Vereinfachung des Gesamtbilds: **Der Kauf braucht denselben kleinen
PHP-Endpunkt, den die Aktivierung ohnehin bringt.** Ein Vorhaben, eine
Bauart, ein Betrieb — der Kauf-Webhook ist der vierte Endpunkt neben den
dreien aus C4.

Der Fluss, wenn einer zahlt:

1. **Checkout beim MoR** (Kaufknopf auf der Website führt dorthin; Preis,
   Steuer, Rechnung, Widerruf sind seine Sache).
2. **Der MoR ruft `order.php`** mit den Bestelldaten. Der Endpunkt prüft
   zuerst die **Webhook-Signatur des Anbieters** (HMAC mit einem Geheimnis,
   das wie das Postfach-Passwort nur auf dem Server liegt) — ein POST ohne
   gültige Signatur ist Lärm und wird ohne Wirkung beantwortet.
3. **Zuteilung aus dem Vorrat, idempotent.** Der Server nimmt den nächsten
   unverbrauchten Schlüssel aus der Vorratstabelle und verknüpft ihn mit der
   Transaktions-ID des MoR. Webhooks kommen doppelt — dieselbe
   Transaktions-ID bekommt denselben Schlüssel wieder, nie einen zweiten;
   ein Zähler, der je Zustellung verbraucht, verschenkt den Vorrat.
4. **Auslieferung.** Eine E-Mail vom eigenen Postfach (Muster `support.php`:
   Schlüssel, Downloadlink, Einlöseanleitung in drei Sätzen, Supportadresse)
   und — wo der Anbieter es hergibt — der Schlüssel zusätzlich auf dessen
   Bestätigungsseite. Der eigene Versand ist der Weg, der „Schlüssel
   erneut senden" später möglich macht, ohne den Anbieter zu fragen.
5. **Eintragen beim Kunden** läuft dann den Weg aus D1: lokale Prüfung,
   Aktivierung, Zertifikat.

**Der Vorrat entsteht offline und bleibt offline nachgehalten.**
`tools/make_licence_keys.py --count` erzeugt ihn mit dem Hauptschlüssel;
jeder Vorratsschlüssel lautet auf niemanden (`holder` leer) und trägt eine
POOL-Bestellkennung. Zwei Pflichten dazu, beide billig und beide später
unbezahlbar:

- **Jeder erzeugte Vorrat wird vollständig offline archiviert** (beim
  Hauptschlüssel: Passwortmanager oder verschlüsselte Ablage).
  `make_licence_keys.py` verlangt dafür `--archive` und schreibt den ganzen
  Lauf atomar als JSONL, bevor es den ersten Schlüssel ausgibt. Wer den
  Archivweg nicht nennt oder wessen Archiv beschädigt ist, bekommt keinen
  Schlüssel auf die Ausgabe — „ich habe meinen Schlüssel verloren" bleibt so
  beantwortbar.
- **Klein halten und nachfüllen** (Vorschlag: 50 Stück). Der Vorrat ist die
  eine Stelle, an der fertige Lizenzen auf dem Server liegen; seine Größe
  ist die Obergrenze des Diebstahlschadens (B3).
- **Erzeugt wird nach der Stichtag-Festlegung, nicht davor.** Ein Schlüssel
  mit Kaufdatum vor dem Stichtag braucht nie ein Zertifikat (Teil A) — er
  ist damit dauerhaft ohne Aktivierung gültig und durch kein Limit und
  keinen Widerruf der Bindung erreichbar. Entstünde bei jeder Hauptversion
  ein Vorrat vor deren Stichtag, wüchse eine nie widerrufbare Liste.
  Vor-Stichtag-Bestände (der erste: 20 Schlüssel POOL-252DB7, offline bei
  Robert, 26.08.2026) bleiben die benannte, klein gehaltene Ausnahme mit
  Offline-Archiv — brauchbar für den Übergangsweg aus Frage 10, nie für den
  Server-Vorrat.

**Und der leere Vorrat ist ein definierter Fall, kein Unfall** (Fund der
Durchsicht vom 26.08.2026 — er tritt am wahrscheinlichsten am besten
Verkaufstag ein, also genau dann, wenn er am teuersten ist). Drei Stufen:

1. **Warnschwelle:** Fällt der Rest unter zehn, schickt `order.php` bei
   jeder Zuteilung eine Mail an das Support-Postfach („Vorrat: noch N").
   Nachfüllen ist damit der Normalfall, die Stufen darunter die Ausnahme.
2. **Leer:** `order.php` beantwortet den Webhook trotzdem mit `ok` — der
   Anbieter darf den Kauf nicht als gescheitert werten oder erstatten —,
   legt die Transaktions-ID als **offene Zuteilung** in die Vorratstabelle
   und mailt Robert sofort. Der Kunde bekommt die Kaufmail in der Fassung
   „Ihr Schlüssel folgt in Kürze" statt gar keiner Post.
3. **Nachgefüllt:** Ein kleines Werkzeug (`tools/fill_pool.py`, nach dem
   Muster der übrigen) lädt den neuen Vorrat und stößt für jede offene
   Zuteilung die normale Auslieferungsmail an — dieselbe Reihenfolge, in
   der die Käufe kamen.

**Die Kette, die einen Kunden findet, ohne dass die App ihn kennt:** Der
Schlüssel nennt die POOL-Kennung; die Serverdatenbank verbindet sie mit der
Transaktions-ID; das MoR-Dashboard verbindet die Transaktion mit dem Käufer.
Erst alle drei zusammen machen aus einem anonymen Schlüssel einen Menschen —
und die Kette existiert nur bei Robert und beim MoR, nie in der Anwendung,
nie im Zertifikat (der Geist von C4). Der Freischaltdialog zeigt bei leerem
`holder` entsprechend „Freigeschaltet (Bestellung POOL-…)" statt
„Freigeschaltet für …" — ein Satz in Teil D, der mit leerem Namen leben
können muss.

**Personalisierte Schlüssel bleiben der Sonderweg**, nicht der Normalfall:
Auf Anfrage (Firmenkauf, Ersatz) stellt Robert mit `--order`/`--holder`
einen Schlüssel aus, der den Namen trägt — das ist zugleich der
Übergangsweg „Verkauf auf Anfrage", falls der Verkauf vor dem Webhook
starten soll (offene Frage 10).

**Die private Support-Oberfläche schließt die Kette für Robert.**
`tools/licence_admin.py` ordnet einem anonymen Vorratsschlüssel lokal die
Transaktionskennung aus dem MoR-Dashboard zu, durchsucht dieses externe Archiv
nach Schlüssel, Digest, Transaktion, POOL-/Bestellkennung oder Käuferkennung
und fragt den Server nur mit dem Digest. Der mit
`setup_activation_server.py` erzeugte 256-Bit-
Betreiberzugang liegt auf Arbeitsrechner und Server außerhalb des Repositorys;
`api/operator.php` nimmt ohne ihn weder Abfrage noch Änderung an. Sichtbar sind
Serverstatus, Geräteverlauf, Tageszähler und das pseudonyme Audit-Protokoll.
Möglich sind Sperren, Entsperren, Geräteplatz freigeben und Versuchslimit
zurücksetzen. Jede Änderung hat einen festen, nicht personenbezogenen Anlass.
Eine bereits ausgestellte Offline-Freischaltung bleibt technisch und
vertraglich unberührt; „Sperren" heißt deshalb ausdrücklich „keine neue
Aktivierung" und nicht „laufenden Offline-Rechner fernabschalten".

Die lokale Bedienung folgt drei Schritten: Lizenz finden, Supportfall lesen,
Handlung wählen. Schlüsselgenerator und Support-Oberfläche halten das externe
Archiv mit derselben Betriebssystem-Sperre exklusiv, prüfen vor jeder Änderung
alle Signaturen und eingebetteten Käuferdaten und ersetzen die JSONL-Datei erst
danach atomar. Transaktionskennungen sind dort eindeutig; ein zweiter Schlüssel
mit derselben MoR-Transaktion wird abgelehnt. Die Suche prüft vollständige
Schlüssel gegen die im Archiv gespeicherte Hauptversion, damit ein späteres
Solidon-Release alte Supportfälle nicht unsichtbar macht.

### B3 — Die Endpunkte, der Speicher, und wo B von C4 abweicht

Sechs PHP-Dateien unter `httpdocs/api/`, alle POST, alle JSON, alle nach der
Bauart von `support.php`:

| Datei | Wer ruft | Tut |
|---|---|---|
| `activate.php` | die App, am Knopf (D1) | C4: prüft Schlüssel, zählt, stellt Zertifikat aus |
| `deactivate.php` | die App, am Knopf (D3) | C4: gibt den Platz der genannten Maschine frei |
| `list.php` | die App, im Limit-Fall (D2) | C4: nennt die eigenen Aktivierungen |
| `order.php` | **nur der MoR** | B2: teilt einen Vorratsschlüssel zu, versendet |
| `offline.php` | die Website-Seite des Offline-Wegs | C6: nimmt den angezeigten Code, gibt die signierte Antwort |
| `operator.php` | nur Roberts lokales Support-Werkzeug | liest den pseudonymen Zustand; sperrt/freigibt, setzt Geräteplatz oder Versuchslimit zurück |

`offline.php` ist kein zweiter Aktivierungspfad, sondern **dasselbe
`activate` in anderer Verpackung** (C6: gleiche Zufalls-ID, gleiches Limit,
gleiche Zählung): Eine kleine Seite auf der Website nimmt den Code entgegen,
den die App anzeigt, und gibt die signierte Antwort zum Abtippen oder als
Datei zurück. Der E-Mail-Weg läuft über das Support-Postfach auf denselben
Endpunkt — am Anfang trägt Robert den Code von Hand ein; ein Automat dafür
lohnt erst, wenn es den Fall öfter als ein paarmal im Monat gibt.

**Der gebaute Aktivierungsdienst hat drei Tabellen in einer SQLite-Datei**
außerhalb des Dokumentenstamms:

- `licences` — ausschließlich Schlüssel-Hash, Status und erster Kontakt;
  `blocked` ist ein Status und braucht keine parallele Wahrheit.
- `activations` — Schlüssel-Hash, öffentlicher Geräteschlüssel,
  frei gewählter Rechnername, Ausstellungstag und optionale Deaktivierung.
- `activation_attempts` — Schlüssel-Hash, UTC-Tag und Zähler; höchstens fünf
  gültig signierte Aktivierungsversuche je Tag (C5). Beim nächsten gültigen
  Versuch werden alle älteren Tageszeilen global entfernt; die
  Datenschutzerklärung sagt offen, dass der letzte Stand ohne weiteren Zugriff
  bis zu diesem Bereinigungslauf bestehen bleibt.

Die spätere Kaufabwicklung ergänzt `pool` mit POOL-Kennung,
Transaktions-ID und Zuteilungstag. Unverbrauchte Schlüssel liegen dort nur
bis zur Zuteilung im Klartext; danach bleibt ihr Hash. Diese Tabelle gehört
zum noch offenen Zahlungsanbieter-Anschluss, nicht zum fertigen
Aktivierungsdienst.

**Die eine benannte Abweichung von C4:** „kein Klartext-Schlüssel (nur ein
Hash)" gilt der Aktivierungsdatenbank, und dort gilt es uneingeschränkt.
Die Vorratstabelle hält unverbrauchte Schlüssel im Klartext — anders kann
der Server nicht ausliefern, und der Hauptschlüssel, der es anders lösen
könnte, darf nicht dorthin (C2). Der Schaden eines Einbruchs ist damit
nicht mehr nur „ein gültiger Schlüssel verliert seine Bindung" (C2),
sondern zusätzlich „bis zu N fertige Lizenzen werden gestohlen". Er bleibt
gedeckelt und **exakt heilbar**: N ist klein (B2), jeder Vorratsschlüssel
ist an seiner POOL-Kennung identifizierbar, und die Widerrufsliste (B4)
nimmt genau die gestohlenen zurück, ohne einen verkauften zu berühren.
Erfinden kann der Einbrecher weiterhin nichts.

**`activate` ist idempotent je Maschine:** Dieselbe Kombination aus
Schlüssel-Hash und Zufalls-ID belegt keinen zweiten Platz, sondern stellt
das Zertifikat neu aus. Eine Neuinstallation auf derselben Maschine (Profil
bleibt, ID bleibt) kostet damit nichts — der Nachbarfall zum Replay aus C5,
und wie der: folgenlos durch Bauart, nicht durch Abwehr.

**Das Zertifikat** füllt der Server, sein Format entscheidet Teil A
(Prüfung offline im Cython-Prüfmodul): Schlüssel-Hash, Zufalls-ID,
Ausstellungstag, signiert mit dem Server-Schlüsselpaar. Der öffentliche
Lizenz-Hauptschlüssel steht dafür auch im PHP — er ist öffentlich, das darf
er; der Server prüft die Signatur eines eingereichten Schlüssels, **bevor**
er zählt oder antwortet (C5).

### B4 — Erstattung und Widerruf, Ende zu Ende

Zwei Ebenen, mit Absicht getrennt, weil sie verschieden schnell und
verschieden mächtig sind:

1. **Die Sperrtabelle auf dem Server wirkt sofort und braucht kein
   Geheimnis.** Ein Eintrag in `blocked` beendet jede *neue* Aktivierung
   dieses Schlüssels — der D2-Fall „Schlüssel widerrufen", mit Grund und
   Bestellnummer im Fehlertext. Meldet der MoR eine Erstattung über den
   Webhook, kann `order.php` den Eintrag selbst setzen; meldet er sie nur im
   Dashboard, setzt ihn Robert. Beides ist derselbe Eintrag.
2. **Die Widerrufsliste erreicht Bestandsinstallationen** — signiert mit dem
   **Hauptschlüssel**, offline (C3: der Server darf seine eigene Sperrung
   nicht aufheben können). Sie liegt als eigene Datei neben `version.json`
   und wird im selben, vom Kunden ausgelösten und abschaltbaren
   Update-Vorgang mitgelesen — **kein neuer Auslöser**, derselbe eine; die
   Telemetrie-Grenze zählt Auslöser, nicht Dateien. Das Werkzeug dazu
   (`tools/make_revocations.py`) folgt `tools/sign_version.py` bis in die
   Gewohnheiten: Gegenlesen sofort nach dem Schreiben, `--check` vor dem
   Hochladen, und `upload_website.py` verweigert eine Liste ohne gültige
   Unterschrift.

Der Ablauf bei einer Erstattung, als geübter Vorgang und nicht als Notfall
(dieselbe Doktrin wie der Schlüsselwechsel in C3): Erstattung kommt an →
`blocked` sofort (Minuten, automatisch oder von Hand) → bei Gelegenheit,
gesammelt und ohne Eile, die Widerrufsliste fortschreiben, offline
signieren, hochladen. Die Liste transportiert **nur Widerrufe, nie
Pflichten** (C3) — sie trägt Schlüssel-Hashes und, für den Serverfall aus
C3, Server-Schlüssel mit Datum.

Und die ehrliche Grenze, einmal mehr: Wer erstattet **und** die
Update-Prüfung abschaltet, behält eine laufende Kopie (C8). Der Verlust ist
genau ein zurückgezahlter Kaufpreis; jede Maßnahme dagegen hieße Heartbeat
und bräche §2. Angenommen.

### B5 — Datenschutz und Rechtstexte

**Rollen:** Der MoR ist für die Kaufdaten (Name, E-Mail, Zahlung, Rechnung)
eigener Verantwortlicher — sie entstehen bei ihm und bleiben bei ihm. Für
die Aktivierungsdaten ist Robert Verantwortlicher und netcup
Auftragsverarbeiter: **der AVV mit netcup wird im CCP abgeschlossen**. Das
Support-Postfach existiert; offen bleibt hier nur der Vertragsschritt.

**Was beim Aktivieren anfällt, vollständig:** Schlüssel-Hash (Pseudonym),
Zufalls-ID (Pseudonym ohne Hardwarebezug, Teil A), Rechnername (vom Kunden
vergeben; neutral vorbelegt nach D3, **und der Dialog sagt dazu, dass
dieser Name zum Server reist** — wer „Papas Laptop" schreibt, tut es
sehend), Ausstellungstag, Weg. IP-Adressen nur in den Serverlogs innerhalb
der Log-Rotation — deren Aufbewahrung wird in Plesk geprüft, kurz
eingestellt und die Zahl in die Datenschutzerklärung geschrieben (B7);
damit wird C4s „keine IP über die Log-Rotation hinaus" eine geprüfte
Einstellung statt eines Satzes. Personenbezug entsteht erst über die Kette
aus B2, und die liegt nicht auf dem Server.

**Rechtsgrundlage** ist die Vertragserfüllung (Art. 6 Abs. 1 lit. b DSGVO —
die Aktivierung setzt die gekaufte Lizenzbindung um; der Offline-Weg steht
dem Kunden ohne Netz offen). Zu ändern sind:

- **Datenschutzerklärung:** neuer Abschnitt „Freischaltung" — was gesendet
  wird, wohin, wie lange es liegt, dass Deaktivieren den Eintrag löscht,
  der Offline-Weg als Alternative. Der Satz „sendet von sich aus keine
  Daten" bleibt wahr und bleibt stehen — die Aktivierung löst der Kunde
  aus; die Präzisierung des §2-Satzes regelt D4.
- **EULA:** Klausel zur Aktivierung — Maschinenlimit, Selbst-Deaktivierung,
  Widerruf bei Erstattung. **Fällig mit dem Server, nicht vorher, und in
  derselben Auslieferung** wie Datenschutzerklärung, Kauftexte und die
  Software, die es durchsetzt (a2, 26.08.2026): Heute setzt Solidon keine
  Grenze durch, und ein Vertragstext, der strenger ist als das Produkt,
  wäre der falsche Fehler. Der Formulierungsvorschlag liegt vor —
  „installieren überall, freigeschaltet ein Rechner zugleich, Wechsel
  jederzeit selbst, ohne Wartezeit"; der dritte Halbsatz ist das, was die
  Grenze erträglich macht. Der Erzeugungsweg hat eine bekannte Falle:
  `EULA.md` ist die Quelle, `tools/make_legal.py` schreibt
  `website/eula.html` **und** `packaging/eula.txt`, und die zweite Hälfte
  reist im Installer — **beide erzeugten Fassungen werden mitcommittet**
  (am 26.08.2026 einmal vergessen, hat einen Release-Tag gekostet).
- **Löschung und Auskunft:** `deactivate` löscht den Aktivierungseintrag;
  ein Auskunfts- oder Löschbegehren wird über die Bestellnummer
  zugeordnet. Aufbewahrungsfristen für Kaufbelege liegen beim MoR, nicht
  bei Robert.

> ⚠️ Wie im Veröffentlichungskonzept: nach bestem Wissen, keine
> Rechtsberatung. Datenschutzerklärung und EULA-Klausel gehören vor dem
> Verkaufsstart einmal vor fachliche Augen — zusammen mit den dort schon
> genannten Punkten, ein Termin für alles.

### B6 — Betrieb: Backup, Ausfall, Monitoring, Updates

**Die Verlustrechnung zuerst, weil sie alles Weitere entspannt:** Die
Aktivierungsdatenbank ist **Betriebsbestand, kein Vertragsbestand**. Geht
sie verloren, gilt jedes ausgestellte Zertifikat lokal weiter (der Rahmen
oben) — es vergisst nur der Zähler, Limits sind vorübergehend großzügiger,
kein Kunde verliert etwas. Wirklich sichern muss das Backup nur die
Vorrats- und Zuteilungstabelle, und deren Quellen liegen ohnehin offline
(Archiv bei Robert, Dashboard beim MoR). Ein Totalverlust ist damit ein
ärgerlicher Nachmittag, keine Katastrophe — diese Eigenschaft ist gebaut,
nicht gehofft, und sie soll beim Bauen erhalten bleiben: **nie einen
Zustand einführen, den nur die Serverdatenbank kennt und der einem Kunden
fehlt, wenn sie fehlt.**

- **Backup:** eine geplante Aufgabe in Plesk kopiert die SQLite-Datei
  täglich datiert (sieben Stände vorgehalten), dazu das Plesk-Backup des
  Pakets. **Einmal vor dem Verkaufsstart wird eine Kopie wirklich
  zurückgespielt** — ein Backup, das nie einen Restore gesehen hat, ist
  eine Vermutung.
- **Ausfall:** Laufende Kunden merken nichts; ihr Zertifikat bleibt lokal
  gültig. Neue Aktivierungen warten oder nehmen den Dateiweg über ein zweites
  Gerät, sofern nur der Arbeitsrechner offline ist. Bei einem vollständigen
  Dienstausfall kann auch der Dateiweg kein Zertifikat ausstellen — deshalb
  gehören externe Bereitschaftsprüfung, Rücksicherung und ein klarer
  Supportweg zur Verkaufsbereitschaft. Eine lokale Schonfrist gibt es bewusst
  nicht: Sie wäre eine erneuerbare Umgehung der Gerätebindung.
- **Monitoring:** passiv und von außen. Ein `health.php`, das „ok" sagt,
  angefragt von einem externen Wächter oder einer wöchentlichen Handprobe
  (`tools/check_activation.py`, B8). Die Anwendung selbst überwacht nichts
  — sie hat keinen Anlass, und die Telemetrie-Grenze gilt.
- **Updates einspielen:** dieselbe Pipeline wie die Website —
  `upload_website.py` über FTPS, davor `php -l` je Datei (B8), und der
  Hostname-Eintrag aus B1 ist Voraussetzung, nicht Empfehlung. Wer
  `order.php` oder `activate.php` ändert, spielt vorher die lokale
  Gegenstelle durch (B8) — die Produktion ist kein Testsystem.

### B7 — Servervorbereitungen: was vor dem ersten Bauschritt liegt

Acht Schritte, jeder mit Prüfkriterium; keiner hängt an der Abnahme dieses
Konzepts, und die ersten sechs kosten zusammen einen Nachmittag:

1. **AVV mit netcup** im CCP abschließen. *Geprüft: das bestätigte Dokument
   liegt in Roberts Unterlagen.* Das Support-Postfach ist bereits eingerichtet.
2. **PHP-Fähigkeiten feststellen:** Wegwerfdatei `phpcheck.php` hochladen —
   PHP-Version, `extension_loaded('sodium')`, PDO-Treiberliste — ansehen,
   löschen. *Geprüft: Version ≥ 8, sodium geladen, `pdo_sqlite` da; sonst
   in Plesk je Domain nachstellen, bevor irgendetwas gebaut wird.*
3. **Ablageort außerhalb des Dokumentenstamms** anlegen
   (`solidon3d.de/appdata/`). *Geprüft: per FTPS beschreibbar, und die
   entsprechende URL antwortet mit 403/404 — nachgefragt, nicht
   angenommen.*
4. **Server-Schlüsselpaar erzeugen** (Werkzeug nach dem Muster von
   `sign_version.py --new-keypair`); privater Teil als Datei in den
   Ablageort, öffentlicher in die App (Teil A) und ins Repository.
   *Geprüft: eine Probesignatur vom Server verifiziert lokal gegen den
   eingecheckten öffentlichen Teil.*
5. **`.webserver.json` auf den Hostnamen umstellen** (B1). *Geprüft: das
   Upload-Werkzeug warnt nicht mehr.*
6. **Log-Rotation und IP-Aufbewahrung** in Plesk prüfen, kurz stellen,
   Zahl notieren. *Geprüft: die Zahl steht, und sie steht später in der
   Datenschutzerklärung (B5).*
7. **MoR-Konto anlegen** — Nachweise, Bankverbindung, Steuerangaben dauern
   Tage bis Wochen, also früh (Veröffentlichungskonzept V5 sagt dasselbe).
   **Vorbedingung, die außerhalb des Projekts läuft** (Robert, 26.08.2026):
   Gewerbeanmeldung und Steuernummer vom Finanzamt — ohne sie schaltet der
   Anbieter die Auszahlung nicht frei; die USt-IdNr. für die Abrechnung mit
   dem Auslandsanbieter mit dem Fragebogen gleich mitbeantragen. Beides
   liegt an; der Bau wartet darauf nicht, nur der Verkaufsstart.
   Webhook-Ziel `order.php` eintragen, das Webhook-Geheimnis erzeugen und
   nur auf dem Server ablegen. *Geprüft: ein Sandbox-Kauf des Anbieters
   erreicht `order.php` mit gültiger Signatur.*
8. **Postausgang für die Kaufmail:** SPF/DMARC-Einträge im CCP setzen
   (offener ROADMAP-Punkt). *Geprüft: eine Testmail an ein fremdes
   Postfach (Gmail/Outlook) landet im Posteingang, nicht im Spam.*

### B8 — Prüfbarkeit der Serverseite (Anschluss an C7)

C7 regelt die App-Seite (kein Netz in der Suite, Doppelgänger mit echter
API-Oberfläche, Anschlusstests). Die Serverseite hat seit `support.php` ein
gemessenes Muster, und es wird übernommen:

- **`php -l` je Datei vor jedem Upload** — und die lokale Gegenstelle:
  PHP 8.4 liegt auf der Maschine (winget), `php -S 127.0.0.1` fährt die
  echten Endpunktdateien, die mbstring-Falle (`extension_dir` neben der
  `php.exe` ableiten) ist bekannt und in `tests/test_support.py` gelöst.
- **`tests/test_activation_server.py`** nach genau diesem Muster: ohne
  lokales PHP übersprungen (die CI merkt davon nichts, wie heute), sonst
  der **echte Client gegen die echte PHP-Datei** — Signaturprüfung lehnt
  einen verfälschten Schlüssel ab, das Limit liefert die Liste statt eines
  Zertifikats, dieselbe Maschine belegt keinen zweiten Platz, ein
  `blocked`-Schlüssel bekommt den Widerrufsfall, `offline.php` gibt
  dieselbe Antwort wie `activate.php`. Ein Nachbau des Servers in Python
  prüfte den Nachbau — deshalb die echte Datei, wie bei `support.php`.
- **`tools/check_activation.py`** als Probe gegen die Produktion, nach dem
  Muster von `tools/check_support.py`. Damit die Probe gefahrlos bleibt,
  existiert **ein Prüfschlüssel, der nie verkauft wird und dauerhaft in
  `blocked` steht**: Die Probe aktiviert ihn, erwartet den Widerrufsfall
  und hat damit den ganzen Weg — TLS, PHP, Datenbank, Signatur — belegt,
  ohne einen echten Platz zu belegen.
- **Der Anschlusstest der ganzen Kette ist ein echter Kauf:** einmal mit
  eigener Karte kaufen, die Mail empfangen, den gelieferten Schlüssel in
  einem gebauten Paket einlösen, aktivieren, erstatten, und nachsehen,
  dass der erstattete Schlüssel serverseitig gesperrt ist. Das deckt sich
  mit der V5-Verifikation des Veröffentlichungskonzepts und ersetzt sie
  nicht — es erweitert sie um die Aktivierung.

## Teil C — Sicherheitsarchitektur (3d-druck-ce, ausgearbeitet)

### C1 — Wer der Gegner ist, und was er wert ist

Ein Schutz, der nicht sagt, gegen wen er steht, schützt gegen alles ein
bisschen. Vier Gegner, nach Häufigkeit sortiert — die Reihenfolge ist die
wichtigste Aussage dieses Abschnitts:

| Gegner | Was er tut | Was er kostet | Was ihn aufhält |
|---|---|---|---|
| **Der Vergessliche** | setzt sein Profil neu auf, will keine 14 neuen Tage | nichts — er ist Kunde | nichts soll ihn aufhalten |
| **Der Sparsame** | schummelt sich alle zwei Wochen 14 neue Tage | einen Kauf, den er nie getätigt hätte | die lokale Härtung (`3ef11e6e`) |
| **Der Teiler** | kauft einmal, gibt den Schlüssel an fünf Kollegen | vier Käufe | das Aktivierungslimit |
| **Der Knacker** | patcht die Binärdatei, verteilt sie | alle Käufe, die dieser Fassung folgen | **nichts, und das gehört gesagt** |

**Der vierte ist der wichtigste, weil er sich nicht abwehren lässt.** Eine
Anwendung, die auf dem Rechner des Angreifers läuft, kann jede Prüfung
verlieren, die auf demselben Rechner stattfindet — das gilt für jede Software
und ist keine Schwäche dieses Entwurfs. Wer dagegen baut, baut Kopierschutz
gegen einen Gegner, den er nicht erreicht, und bezahlt es mit Hürden für die
drei anderen, die er erreicht.

**Daraus folgt der Maßstab für alles Weitere:** Der Server richtet sich gegen
den **Teiler** und, in zweiter Linie, gegen den Sparsamen. Er richtet sich
ausdrücklich **nicht** gegen den Knacker. Jede Maßnahme, die den ehrlichen
Kunden etwas kostet und nur den Knacker aufhielte, ist damit abgelehnt, bevor
sie diskutiert wird.

Und der Vergessliche steht mit Absicht an erster Stelle: Er ist der häufigste
von allen, er hat bezahlt, und jede Reibung trifft ihn zuerst.

### C2 — Was ein gehackter Server anrichten darf

Der Server läuft auf Shared Hosting (Teil B). Von dort ist nichts
auszuschließen — die Frage ist nicht, ob ein Einbruch möglich ist, sondern was
er einbringt.

**Die Trennung aus Teil A ist die tragende Entscheidung**, und sie hält: Der
Server hält ein eigenes Schlüsselpaar, das nur Aktivierungszertifikate
signiert. Der Hauptschlüssel, der Lizenzen signiert, liegt offline bei Robert.
Ein Einbrecher kann damit

- **Aktivierungen ausstellen für Schlüssel, die es gibt** — also die
  Maschinenbindung eines gültigen Schlüssels aufheben,
- die Aktivierungsdatenbank lesen (Schlüssel-Hashes, Zufalls-IDs,
  Rechnernamen, Zeitstempel),

und er kann **nicht**

- Lizenzen erfinden (dafür braucht es den Hauptschlüssel),
- den Testzeitraum verlängern (der ist lokal, Teil A),
- die Anwendung eines Kunden verändern (das Manifest hängt am Hauptschlüssel).

**Der Schaden ist damit gedeckelt auf „ein gültiger Schlüssel verliert seine
Bindung".** Das ist genau der Schaden, den der Teiler ohnehin anrichtet — der
Einbruch macht ihn breiter, nicht schlimmer. Die Datenbank enthält absichtlich
nichts, was einen Menschen benennt (Teil A: Zufalls-ID statt
Hardware-Fingerabdruck, Personenbezug erst über die Bestellnummer in Teil B).

### C3 — Der Widerruf, und warum er ohne Datum nie ausgelöst wird

Ein gestohlener Server-Schlüssel muss sich zurücknehmen lassen, sonst ist der
Einbruch dauerhaft. Der Weg dorthin hat drei Fassungen, und die ersten zwei
sind Sackgassen:

**Erste Fassung — kurze Gültigkeit.** Zertifikate laufen nach N Tagen ab, die
App holt ein neues. Damit wird der Server zur **Betriebsvoraussetzung**, und
§2 ist gebrochen: Wer offline arbeitet, verliert seine Freischaltung, ohne
etwas falsch gemacht zu haben. Abgelehnt.

**Zweite Fassung — unbefristet plus Widerrufsliste.** Das Zertifikat gilt
ewig; die App liest beim ohnehin stattfindenden, deklarierten und
abschaltbaren Update-Check eine Widerrufsliste. Die Liste ist mit dem
**Hauptschlüssel** signiert, nicht mit dem Server-Schlüssel — sonst könnte der
gehackte Server seine eigene Sperrung aufheben. Sie transportiert nur
Widerrufe, nie Pflichten: kein „Zertifikat muss alle N Tage bestätigt werden"
durch die Hintertür.

Das ist richtig und trotzdem unbrauchbar, solange der Widerruf einen
**Schlüssel** trifft: Er nimmt jedem ehrlichen Kunden die Aktivierung, der
seit dem letzten Schlüsselwechsel aktiviert hat. Eine Maßnahme, die im
Ernstfall tausend Kunden sperrt, wird nicht ausgelöst — und eine Waffe, die
man nicht benutzen will, wirkt nicht.

**Dritte Fassung — der Widerruf trägt ein Datum.** Jedes Zertifikat nennt
seinen Ausstellungstag (Teil A: „ausgestellt am T"). Die Liste sagt dann nicht
„Server-Schlüssel S ist tot", sondern **„S ist tot für alles, was nach T
ausgestellt wurde"** — T ist der Einbruchsbeginn aus den Server-Logs. Damit
bleibt jedes Zertifikat vor T gültig, die große Mehrheit merkt nichts, und der
Widerruf wird klein genug, dass man ihn wirklich auslöst.

Zwei Dinge gehören dazu, sonst trägt auch die dritte Fassung nicht:

- **T wird konservativ früh gesetzt.** Wer den Einbruchsbeginn nicht kennt,
  nimmt den frühesten Verdacht. Die wenigen ehrlichen Kunden zwischen T und
  dem Wechsel — Tage, nicht Monate — reaktivieren einmal gegen den sauberen
  Schlüssel.
- **Der Schlüsselwechsel ist ein geübter Vorgang, kein Notfall.** Alte und
  neue Zertifikate gelten während einer Frist parallel, und für den, der von
  allem nichts mitbekommen hat, gibt es denselben Weg wie für jeden anderen:
  den Freischaltdialog aus Teil D. Wer den Ablauf erst im Ernstfall erfindet,
  löst ihn nicht aus.

**Und die Grenze, die bleibt und die ehrlich hingeschrieben gehört:** Die
Liste erreicht nur, wer den Update-Check anhat. Er ist abschaltbar, und das
ist richtig so (§2, `kern.md`). **Die Wirksamkeit des Widerrufs hängt damit an
einer Einstellung, die der Kunde jederzeit umlegen darf.** Wer sie als
lückenlose Abwehr beschreibt, schreibt einen Prospekt. Praktisch trägt sie
trotzdem: Die Population, die einen gestohlenen Schlüssel benutzt, ist nicht
die, die Updates abschaltet — und wer beides tut, ist der Knacker aus C1, den
dieser Entwurf ohnehin nicht erreicht.

### C4 — Drei Endpunkte, und was jeder nicht darf

So wenig Fläche wie möglich. Drei Endpunkte, alle POST, alle über TLS:

| Endpunkt | Nimmt | Gibt | Darf nicht |
|---|---|---|---|
| `activate` | Schlüssel, Zufalls-ID, Rechnername | Zertifikat oder Limit-Liste | keine Daten zurückgeben, die nicht hineingingen |
| `deactivate` | Schlüssel, Zufalls-ID der zu lösenden Maschine | Bestätigung | nicht ohne den Schlüssel arbeiten |
| `list` | Schlüssel | Rechnernamen und Daten der eigenen Aktivierungen | keine fremden Schlüssel sichtbar machen |

(Teil B zählt fünf Dateien: `order` spricht ausschließlich mit dem
Zahlungsanbieter und nimmt nie einen Kundenschlüssel entgegen (B2), und
`offline` ist dasselbe `activate` in anderer Verpackung (B3, C6). Die
Fläche, an der der Kunden-Ausweis anliegt, bleiben diese drei.)

**Der Schlüssel ist der Ausweis, und einen zweiten gibt es nicht.** Kein
Konto, kein Passwort, keine Sitzung — das ist die Entscheidung aus Teil D
(„kein Konto, keine Website-Verwaltung"), und sie hat eine Sicherheitsfolge:
Wer den Schlüssel kennt, kann alles, was der Käufer kann — allerdings nur
**innerhalb dieses einen Schlüssels**: die Rechner sehen und abmelden, die
unter genau ihm aktiviert sind. An die Aktivierungen eines anderen
Schlüssels kommt niemand, und wer seinen Schlüssel für sich behält, dessen
Rechner kann kein Fremder anfassen. Betroffen ist allein, wer ihn
weitergegeben hat — dann können die Mitwisser einander (und ihn)
hinauswerfen.

**Das ist bewertet und angenommen** — Teil D fragt ausdrücklich danach. Ein
geteilter Schlüssel führt dazu, dass die Beteiligten sich reihum gegenseitig
hinauswerfen. Das nervt genau die, die ihn teilen, und trifft einen ehrlichen
Kunden nie: Er hat den Schlüssel nur selbst. Ein Schutz dagegen bräuchte ein
Konto, und das kostet jeden ehrlichen Kunden eine Anmeldung — gegen einen
Gegner, der ohnehin schon bezahlt hat.

**Was der Server speichert, steht in Teil B; was er nicht speichert, gehört
hierher:** keine IP über die Log-Rotation hinaus, kein Hardware-Merkmal, kein
Klartext-Schlüssel (nur ein Hash), keine Dateinamen, keine Projektdaten. Ein
Einbrecher soll in der Datenbank nichts finden, was über „dieser anonyme
Schlüssel läuft auf drei anonymen Maschinen" hinausgeht.

**Eine benannte Abweichung gibt es, und sie steht mit ihrer Deckelung in
B3:** Die Vorratstabelle des Kaufflusses hält *unverbrauchte* Schlüssel im
Klartext, weil der Server sonst nicht ausliefern kann und der Hauptschlüssel
nicht dorthin darf. Der zusätzliche Einbruchsschaden ist auf die
Vorratsgröße gedeckelt und über die POOL-Kennungen exakt widerrufbar; für
die Aktivierungsdaten selbst gilt der Absatz darüber uneingeschränkt.

### C5 — Replay, Ratenbegrenzung, und der Fall, der keiner ist

**Replay ist hier fast folgenlos**, und das ist eine Eigenschaft des Entwurfs,
nicht ein Zufall: Ein abgefangenes `activate` liefert ein Zertifikat, das auf
**eine bestimmte Zufalls-ID** lautet. Wer es einspielt, schaltet die Maschine
frei, die ohnehin schon freigeschaltet war. Der einzige nutzbare Angriff ist
das Wiedereinspielen eines **alten** Zertifikats nach einem `deactivate` —
dagegen trägt die Widerrufsliste aus C3, und praktisch trägt es sich selbst:
Wer den Platz freigibt und dann das alte Zertifikat behält, hat einen Platz zu
viel und keinen Vorteil, weil das Limit ohnehin nicht bindet, wenn man
deaktivieren kann.

**Ratenbegrenzung** je Schlüssel, nicht je IP: Ein Büro hinter einer Adresse
ist der Normalfall, nicht der Angriff. Gebaut sind fünf `activate` je Schlüssel
und UTC-Tag, gezählt erst nach gültiger Signatur. Wer mehr braucht, bekommt den
Weg zu Support und nächstem Tag; IP-Adressen werden dafür nicht gespeichert.

**Schlüssel zu raten ist ohnehin kein Angriffsweg**, den die Begrenzung tragen
müsste: Ein ed25519-signierter Schlüssel lässt sich nicht erraten, und der
Server prüft die Signatur, bevor er zählt. Die Begrenzung ist gegen Lärm, nicht
gegen Kryptographie.

**Das Aktivierungslimit** ist keine Sicherheits-, sondern eine
Geschäftsentscheidung, und sie ist getroffen: **ein Rechner je Schlüssel**
(Robert, 26.08.2026, `249fb878` — „einmal zugleich, nicht einmal im Leben").
Aus Sicherheitssicht ändert die Zahl nichts; das Wander-Muster aus C4 trägt
auch bei eins, es wandert nur schneller.

**Was sich damit ändert, ist das Gewicht der Bedingung darunter.** Bei drei
Maschinen war die Selbstbedienung Komfort — wer den zweiten Platz belegt hat,
hat noch einen dritten. Bei eins ist sie die **einzige** Alternative zu einem
Support-Fall: Jeder Gerätewechsel, jede neue Festplatte, jedes neu aufgesetzte
System braucht sie. **Es muss sich vom Kunden selbst auflösen lassen**
(Teil D3), sonst wird aus jedem defekten Laptop ein Support-Fall — und
Support-Fälle werden mit Ausnahmen gelöst, und Ausnahmen
sind der Weg, auf dem jede Grenze weich wird.

### C6 — Der Offline-Weg darf weniger

Ohne ihn bräche §2 (siehe oben). Mit ihm entsteht die Gefahr, dass er zum
bequemeren Weg wird — dann ist die Bindung eine Formsache.

**Der Ablauf:** Die App zeigt einen Code, der die Zufalls-ID und den
Schlüssel-Hash trägt. Der Kunde bringt ihn an ein Gerät mit Netz (Website oder
E-Mail an den Support), bekommt eine signierte Antwort und trägt sie ein. Das
ist Challenge-Response, und es ist derselbe Vorgang wie online — nur mit dem
Menschen als Übertragungsweg.

**Drei Eigenschaften halten ihn davon ab, zur Hintertür zu werden:**

1. **Er ist an dieselbe Zufalls-ID gebunden** wie der Online-Weg. Eine
   Offline-Antwort für Maschine M schaltet keine andere frei — sie ist kein
   Generalschlüssel, sondern dasselbe Zertifikat auf einem anderen Weg.
2. **Er zählt gegen dasselbe Limit.** Der Server trägt die Aktivierung ein,
   wenn er die Antwort ausstellt; ob sie per HTTP oder per E-Mail herauskommt,
   ändert daran nichts.
3. **Der Kunde sieht, dass er ihn benutzt hat.** Im Freischaltdialog steht
   „offline freigeschaltet" — nicht als Makel, sondern damit der Zustand
   erklärbar bleibt, wenn später etwas nicht stimmt.

**Was er nicht darf: unbegrenzt gültig sein, ohne dass jemand ihn ausgestellt
hat.** Eine vorsignierte Datei, die auf jeder Maschine schaltet, wäre die
Hintertür — und genau das ist die Bauform, die für „Firma weg" (offene Frage
4) vorgeschlagen wird. **Beides zusammen geht nicht**, und die Entscheidung
gehört Robert: Eine hinterlegte Dauer-Freischaltung ist eine Zusage an Kunden
für den Fall, dass niemand mehr da ist — und zugleich ein Generalschlüssel,
sobald sie existiert. Mein Vorschlag: Sie wird **vorbereitet, aber nicht
ausgeliefert** — als signierte Datei, die im Ernstfall auf die Website kommt.
Solange die Firma da ist, existiert sie nur offline; danach braucht sie
niemand mehr zurückzunehmen.

### C7 — Wie man das prüft, ohne ans Netz zu gehen

**Die Suite darf kein Netz brauchen** (`tests.md`, Isolation). Und sie deckt
es heute nicht ab — das ist ein bekannter Fund: `llm.available()` öffnet in
`test_ui.py` eine echte Verbindung über `socket.create_connection`. Ein
Rechner mit laufendem Ollama misst dort etwas anderes als ein Bauserver. **Wer
einen zweiten Netzpfad baut, baut die Sperre mit**, sonst hat die Suite zwei
Löcher statt einem.

Geprüft wird gegen einen **Doppelgänger** mit der echten API-Oberfläche des
Serverclients — nicht gegen eine Attrappe mit erfundenen Methoden. Der Grund
steht in `oberflaeche.md` bei den pyvista-Widgets: Ein Fake mit `Off()`, das
es nie gab, versteckt den Absturz genauso gut wie die Suite ihn versteckte.

Vier Zusagen, die Tests werden sollen, und jede prüft eine Sache, die sonst
niemand prüft:

1. **Der Kern kommt ohne Netz aus.** `core` importiert und rechnet ohne jeden
   Socket — dieselbe Bauart wie `test_core_isolation.py` für Qt. Ein
   Zertifikat wird **offline** gegen den eingebauten öffentlichen Schlüssel
   geprüft; wenn dafür eine Verbindung nötig wäre, ist der Entwurf falsch.
2. **Genau ein Aufrufer je Endpunkt, und er hängt am Knopf.** Dieselbe Zählung
   wie `tests/test_support.py` sie für `support.send()` macht — was die Grenze
   zur verbotenen Telemetrie hält, ist nicht die Formulierung, sondern diese
   Zahl.
3. **Ein abgelaufenes oder widerrufenes Zertifikat sperrt, ein gültiges
   nicht** — beide Richtungen, wie bei jeder Grenzprüfung in
   `test_licence_boundary.py`. Und: Ein Zertifikat für eine **andere**
   Zufalls-ID schaltet nicht frei.
4. **Der Kein-Netz-Pfad kostet nichts.** Aus Teil D: Der Dialog geht auf, der
   Testzeitraum steht, der Schlüssel liegt abgelegt. Der Konstruktor macht
   keinen Netzaufruf — geprüft mit einem Doppelgänger, der bei Kontakt wirft.

**Und die Testart „Anschluss" ist hier die entscheidende**, nicht die
Einzelprüfung: Was nur an einer Stelle eingelöst wird, wird an dieser Stelle
geprüft — nicht „der Cache kann es", sondern „die Anwendung tut es". Für den
Aktivierungspfad heißt das: Nicht prüfen, dass der Client ein Zertifikat
verarbeiten **kann**, sondern dass die Anwendung nach einem echten
Freischaltvorgang **freigeschaltet ist** — und nach einem abgelehnten nicht.

### C8 — Was dieser Entwurf nicht leistet

Damit es niemand später als Lücke meldet:

- **Gegen einen gepatchten Client hilft nichts davon.** Siehe C1. Wer das
  ändern will, ändert das Produkt, nicht dieses Konzept.
- **Der Widerruf erreicht nur, wer Updates anhat** (C3).
- **Wer den Schlüssel hat, kann fremde Rechner deaktivieren** (C4) — bewusst
  angenommen, weil die Alternative ein Konto wäre.
- **Die Datenbank ist ein Einbruchsziel**, auch wenn wenig darin steht. Was
  darin steht, entscheidet Teil B; was nicht darin stehen soll, steht in C4.
- **Ein Ausfall des Servers verhindert neue Aktivierungen.** Kein laufender
  Kunde verliert etwas (die Zusage aus dem Rahmen oben), aber wer am
  Ausfalltag kauft, wartet. Monitoring, Backup-Rücksicherung und Support
  tragen diesen kleinen, klar benannten Verfügbarkeitsanteil; eine lokale
  Aktivierungsumgehung trägt ihn nicht.
- **Ein geklontes Plattenabbild teilt sich einen Platz.** Wer eine Maschine
  samt Profil auf N Rechner spiegelt, spiegelt die Zufalls-ID mit — alle N
  laufen unter einem Zertifikat, und der Server sieht eine Maschine. Das ist
  der Nachbar des Knackers (C1): Aufwand jenseits des Teilers, und jede
  Abwehr hieße Hardware-Fingerabdruck, den Teil A aus gutem Grund ablehnt.
  Angenommen.

## Teil D — Bedienung (3d-druck-43, ausgearbeitet)

**Grundsatz: Der Freischaltdialog bleibt der eine Ort, und das Netz wird ein
Schritt darin — kein Konto, keine Website-Verwaltung.** Der Schlüssel bleibt
das einzige Ausweisdokument; wer ihn hat, kann aktivieren, deaktivieren und
umziehen, alles im Dialog. Eine „Lizenzverwaltung" auf der Website bräuchte
eine Anmeldung, und damit wäre „ohne Konto" gelogen — der Satz steht viermal
auf der Startseite.

### D1 — Der Aktivierungsfluss, Klick für Klick

Der Dialog zeigt zwei kleine, nummerierte Schritte und trennt lokale Prüfung
und den ausdrücklich ausgelösten Netzkontakt:

1. Kunde fügt den Schlüssel ein (mehrzeiliges Feld, Bestand). *Schlüssel prüfen*
   bleibt grau mit Grund, bis Text dasteht (Bestand).
2. Klick *Schlüssel prüfen*: **lokale Prüfungen zuerst** — Format, Unterschrift,
   Hauptversion. Ein Tippfehler erreicht nie das Netz; die bestehenden
   `LicenceKeyError`-Pfade über `show_error` bleiben unverändert.
3. Braucht der Schlüssel ein Zertifikat (Kaufdatum ab Stichtag, Teil A),
   wählt der Kunde *Online aktivieren* oder *Offline aktivieren …*. Nur der
   Online-Knopf startet einen Arbeiter (`leash.Worker`, `crashed` verbunden);
   der Dateiweg speichert die signierte Anfrage und liest später die Antwort.
4. Erfolg: Das Zertifikat liegt lokal. Die Zustandszeile nennt Lizenz,
   Bestellung und frei gewählten Gerätenamen; danach bleibt der Dialog als
   nachvollziehbare Bestätigung offen.
5. **Der Dialog telefoniert nie beim Öffnen.** Kein Status-Ping, keine
   Erhebung im Konstruktor: Netzzugriff hängt an genau zwei Knöpfen
   (*Online aktivieren*, *Diesen Rechner deaktivieren*). Das hält die
   Telemetrie-Grenze messbar — wie bei `support.send()` zählt ein Test die
   Aufrufer je Endpunkt, und es ist je einer, am Knopf.
6. **Kein automatischer Neuversuch beim Start.** Ein abgelegter, noch nicht
   aktivierter Schlüssel ist ein sichtbarer Zustand („Schlüssel eingetragen,
   Aktivierung ausstehend") mit einem Knopf — nicht ein stiller Netzzugriff
   beim Programmstart, den niemand ausgelöst hat.

### D2 — Jeder Fehlerpfad als Handlungsvorschlag (Regel 17)

Alle Texte nach dem Muster des Slicen-Knopfs: `damaged` zuerst, eine
Textquelle je Auskunft, drei Kodierungen an gesperrten Knöpfen.

| Fall | Satzmuster | Handlungen |
|---|---|---|
| Kein Netz / Server weg / Zeit um | „Der Aktivierungsserver war nicht erreichbar — der Schlüssel ist gültig und bleibt eingetragen." | *Erneut versuchen* · *Offline aktivieren …* (Teil C) · *Später* |
| Limit erreicht | „Dieser Schlüssel ist schon auf {limit} Rechnern aktiv." darunter die Liste: Name, Aktivierungsdatum | *{Rechner} deaktivieren* je Zeile — danach läuft die Aktivierung ohne neuen Klick weiter; **keine Bestätigungsfrage** (rücknehmbar, Regel 19) |
| Schlüssel widerrufen | nennt Grund und Bestellnummer | *Support kontaktieren* (Rückmeldedialog) — nicht *Kaufen* als Erstes: wer erstattet hat, weiß es; wer zu Unrecht gesperrt ist, braucht den Support |
| Antwort nicht echt (kaputter Proxy, Manipulation) | „Die Antwort war nicht die des Aktivierungsservers." | *Erneut versuchen* · *Offline aktivieren …* |
| Installation beschädigt | wie heute: `damaged_line()` **vor** allem anderen, Aktivieren gar nicht erst angeboten | Bestand |

Der Kein-Netz-Fall ist der wichtigste: Der Schlüssel bleibt abgelegt, und der
Dialog bietet neben dem kurzen Online-Weg die Anfrage- und Antwortdatei an.
Ein neuer Verkaufsschlüssel ohne Zertifikat bleibt sicher gesperrt; genau
dadurch gibt es keine wiederholbare Schonfrist. Nach der einmaligen
Dateiaktivierung braucht der Arbeitsrechner dauerhaft keine Lizenzverbindung.

### D3 — Umzug und Deaktivieren

- **Beim Aktivieren vergibt der Kunde einen Rechnernamen**, vorbelegt neutral
  („Dieser Rechner"), frei änderbar — nicht der Hostname als Vorgabe, der trägt
  oft einen Personennamen und läge dann beim Server. Ohne Namen wäre die
  Limit-Liste drei Datumszeilen, und niemand weiß, welcher Eintrag der alte
  Laptop war.
- ***Schlüssel entfernen* wird bei einem Geräte-Zertifikat zu *Diesen Rechner
  deaktivieren*.** Aus
  Kundensicht ist es eine Handlung („dieser Rechner soll es nicht mehr
  sein"): Sie gibt den Platz beim Server frei **und** entfernt Schlüssel und
  Zertifikat lokal. Schlägt der Serverkontakt fehl, stellt Solidon das lokale
  Zertifikat wieder her: Der Rechner bleibt nutzbar und der Platz stimmt auf
  beiden Seiten überein. Zwei getrennte Knöpfe für die zwei Hälften wären die
  sichere Verwechslung.
- **Ist der alte Rechner verloren oder defekt**, bleibt als sichere letzte
  Stufe der Support: Mit Bestellnummer wird der belegte Platz freigegeben.
  Eine anonyme Website-Verwaltung, auf der allein der kopierte Schlüssel ein
  fremdes Gerät hinauswerfen kann, wird zum Verkaufsstart bewusst nicht
  angeboten.
- **Und hinter der Selbstbedienung steht der Support als letzte Stufe**
  (Frage Robert, 26.08.2026). Gebraucht wird er nur, wenn Schlüssel **und**
  Rechner weg sind — der Schlüssel ist ja der Ausweis für alles andere.
  Dann: Bestellnummer aus der Kaufmail oder vom Zahlungsanbieter → Robert
  findet den Schlüssel über die B2-Kette im Offline-Archiv → sendet ihn
  erneut → der Kunde deaktiviert selbst. Zusätzlich kann Robert jeden Platz
  von Hand freigeben (ein Eintrag in der Serverdatenbank) — das bleibt
  bewusst der Ausnahmeweg und wird nicht beworben: C5 warnt zu Recht, dass
  Grenzen über Support-Ausnahmen weich werden, und die Selbstbedienung
  soll der Weg bleiben, den jeder zuerst findet.
- **Bestandskunden sehen von allem nichts** (Teil A): Schlüssel vor dem
  Stichtag aktivieren nicht, ihr Dialog verhält sich wie heute.

### D4 — Welche Sätze altern (Fundliste, per Verneinungssuche gemessen)

Die Betriebszusage bleibt wahr — präzisiert wird, dass die **Freischaltung**
einmal Kontakt braucht. Vorschlag für den einen Satz, überall gleich:
„Ohne Netz, ohne Konto und ohne KI bleibt alles außer dem Chat benutzbar;
Netz braucht nur die einmalige Freischaltung (oder ihr Offline-Weg) und die
Update-Prüfung, die Sie selbst auslösen."

| Ort | Satz heute | Was zu tun ist |
|---|---|---|
| `app/core/manual.py:118` | „Ohne Netz, ohne Konto und ohne Sprachmodell …" | präzisieren; erzeugt `website/handbuch.html` und `en/manual.html` mit |
| `AGENTS.md` §2-Fünfzeiler, `README.md` | „Ohne Netz, ohne Konto und ohne KI …" | präzisieren (Doku, kein Katalog) |
| `app/core/activation/store.py` Docstring | „dass Solidon ohne Netz und ohne Konto läuft" | präzisieren, Begründung der Hürde bleibt |
| `website/index.html` (4×: meta, og, JSON-LD, Kacheln) | „ohne Konto, ohne Abo", „ohne Telemetrie" | **bleibt wahr, bleibt stehen** — die Startseite verspricht kein „ohne Netz" |
| Trial-/Demo-Texte im `ActivationDialog` | „… brauchen einen Schlüssel" | bleibt wahr (Schlüssel schließt Aktivierung ein); Handbuchseite „Freischalten" erklärt den Schritt |
| EULA / Datenschutzerklärung | — | Teil B (B5): Aktivierungsdaten benennen; beide erzeugten EULA-Fassungen mitcommitten |
| EULA §2 (seit ddee0d41) | „keine Aktivierungspflicht über das Netz … wir erfahren nicht, wann und wo" | **ändern zusammen mit der B5-Klausel, nicht vorher** — für Bestandsschlüssel wahr, mit dem Server falsch (Aktivierung meldet einmalig *dass* und *wann*); Formel wie der §2-Rahmensatz oben: Freischaltung braucht einmal Kontakt oder den Offline-Weg, im Betrieb erfahren wir nichts |

Dazu eine neue Handbuchseite „Freischalten und Umziehen": Aktivieren,
Offline-Weg Schritt für Schritt, Rechner wechseln, was bei Serverausfall gilt
(nichts — Betrieb läuft lokal weiter).

### Prüfbarkeit (Anschluss an Teil C)

Der Dialog wird gegen eine **Attrappe mit der echten API-Oberfläche** des
Serverclients getestet (die AffineWidget-Lehre: ein Fake mit erfundenen
Methoden versteckt Abstürze). Drei Zusagen als Tests: (1) genau ein Aufrufer
je Netz-Endpunkt, am Knopf — dieselbe Bauart wie `tests/test_support.py`;
(2) der Kein-Netz-Pfad endet mit stehendem Testzeitraum und abgelegtem
Schlüssel; (3) der Konstruktor des Dialogs macht keinen Netzaufruf
(Attrappe, die bei Kontakt wirft).

## Offene Entscheidungen für Robert (nach der Ausarbeitung)

1. Aktivierungslimit je Schlüssel — **entschieden (Robert, 26.08.2026):
   ein Rechner.** „Ein Schlüssel ist nur einmal aktivierbar" heißt dabei
   **einmal zugleich, nicht einmal im Leben** — die Unterscheidung trägt
   den ganzen Alltag: Neuinstallation auf derselben Maschine kostet nichts
   (idempotent je Zufalls-ID, B3), und der Wechsel auf einen neuen Rechner
   ist Selbstbedienung (D3: alten Platz deaktivieren, auch wenn der alte
   Rechner tot ist — der Limit-Fluss am neuen zeigt ihn und gibt ihn
   frei). **Teil C5 bleibt die Bedingung:** Ein Limit ohne Selbstbedienung
   erzeugt Support-Fälle, und Support-Fälle werden mit Ausnahmen gelöst;
   bei Limit 1 gilt das doppelt, weil jeder Zweitrechner (Werkstatt-PC
   neben dem Laptop) eine zweite Lizenz ist — das ist die
   Geschäftsentscheidung, und sie ist gefallen.
2. Trial lokal lassen oder serverseitig registrieren (Vorschlag: lokal).
3. Bestandsschlüssel-Stichtag. **Seit Entscheidung 1 hängt daran auch die
   EULA-Frage** (über a2 vorgelegt, 26.08.2026): Wer vor dem Stichtag
   gekauft hat, hat eine Fassung gelesen, die unbegrenzte Geräte zusagt —
   ob diese Schlüssel von der Ein-Rechner-Grenze ausgenommen bleiben (die
   Übergangsregel aus Teil A nimmt sie ohnehin von der Aktivierung aus)
   oder die neue Fassung für alle gilt, ist keine technische Frage.
4. Notfallplan „Firma weg" — **inhaltlich durch C6 beantwortet, es fehlt
   nur noch Roberts Ja/Nein:** Die Dauer-Freischaltung wird vorbereitet,
   aber nicht ausgeliefert; solange die Firma da ist, existiert sie nur
   offline, im Ernstfall kommt sie auf die Website. (Vorab hinterlegen
   ginge nicht — eine Datei, die auf jeder Maschine schaltet, wäre der
   Generalschlüssel, den der Offline-Weg gerade vermeidet.)
5. Rechnername beim Aktivieren (Vorschlag: ja, neutral vorbelegt und frei
   änderbar — sonst ist die Limit-Liste drei Datumszeilen ohne Auskunft).
6. *Schlüssel entfernen* und *Deaktivieren* als **ein** Knopf (Vorschlag:
   zusammenlegen, „Diesen Rechner deaktivieren" — ohne Netz nur lokal, mit
   Ansage).
7. Wortlaut der §2-Präzisierung (Vorschlag in Teil D4 — ein Satz, überall
   gleich).
8. **Entschieden am 28.08.2026:** keine vorläufige Freischaltung ohne
   Zertifikat. Verkauf ohne Testphase bedeutet auch keine versteckte
   Vierzehn-Tage-Schonfrist; für Offline-Rechner trägt der Dateiweg.
9. Zahlungsanbieter (dieselbe offene Frage wie
   `konzept-veroeffentlichung-1.0.md` §7, hier mit neuem Stand): Nach dem
   Befund vom 26.08.2026 (B2) liefert kein empfohlener Anbieter einen
   eigenen Schlüsselvorrat mehr nativ aus — der Kauf braucht den
   Webhook-Endpunkt in jedem Fall. Vorschlag: **Paddle Billing** mit
   `order.php`; die Gebührensätze holt, wer entscheidet, am Tag der
   Entscheidung.
10. Startreihenfolge des Verkaufs: erst Kauf-Webhook und Aktivierungsserver
    fertig, dann Verkaufsstart (Vorschlag — beides ist eine Endpunktfamilie,
    B2) — oder eine Übergangsphase „Verkauf auf Anfrage" mit von Hand
    ausgestellten, personalisierten Schlüsseln.
11. Auslieferungsweg des Schlüssels (B2): eigene Kaufmail vom eigenen
    Postfach, zusätzlich Anzeige auf der Bestätigungsseite des Anbieters,
    wo möglich (Vorschlag: beides — die eigene Mail macht „Schlüssel
    erneut senden" unabhängig vom Anbieter).
