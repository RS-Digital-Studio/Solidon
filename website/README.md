# Website — solidon3d.de

Statische Seiten, **keine externen Ressourcen beim Laden**. Alles in diesem
Ordner wird unverändert hochgeladen; einen Build-Schritt gibt es nicht. Der
Spendenknopf ist ein gewöhnlicher Verweis zu PayPal und lädt dort erst nach
einem ausdrücklichen Klick die Zahlungsseite — kein PayPal-Skript, keine
Schrift und kein Zählpixel sind in die Seite eingebunden.

Der Hinweis unmittelbar am Knopf hält die rechtliche Grenze fest: keine
Bestellung, keine Gegenleistung, keine Anrechnung auf einen späteren Kauf und
keine Spendenbescheinigung. `datenschutz.html` nennt PayPal als eigenständig
Verantwortlichen, die übermittelten Transaktionsdaten und den Umgang mit
wiederkehrenden Spenden. Diese Sätze gehören zum Zahlungsweg; sie werden nicht
aus Platzgründen aus dem Download-Kasten entfernt.

Beide Skripte kommen von hier — kein CDN, keine Bibliothek, keine Schriftart
von außen, kein Zählpixel. `site.js` markiert in der Funktionsseite den gerade
gelesenen Block und zählt auf der Startseite die Zeit bis zur Demo herunter;
beides ist Zugabe. `activation.js` gehört ausschließlich zur bewusst
aufgerufenen Offline-Aktivierungsseite und sendet erst nach einem Klick die
vom Kunden gewählte Anfragedatei. `tests/test_website.py` prüft den Teil, der
die Zusage der Seite trägt: **nichts von außen** und kein versteckter
Netzaufruf.

Bewegung entsteht ausschließlich aus CSS: Übergänge beim Zeigen und
scroll-gesteuerte Zeitachsen (`animation-timeline: view()`) beim Lesen. Der
ganze Block steht in `style.css` hinter einem `@supports` — kennt ein Browser
die Zeitachse nicht, greift keine Regel davon, und die Seite steht vollständig
da. Nichts wird über `opacity: 0` versteckt, was ohne Animation nie wieder
auftaucht. `prefers-reduced-motion: reduce` schaltet alles ab und setzt die
erklärenden Zeichnungen — vier große in den Beweiszeilen, drei Vignetten über
den Wegen — von Hand auf ihren Endzustand; ohne das lägen beide Zustände
übereinander („2,40 mm“ über „3,60 mm“).

## Dateien

| Datei | Zweck |
|---|---|
| `index.html` | Startseite deutsch |
| `en/index.html` | Startseite englisch |
| `funktionen.html`, `en/features.html` | Funktionsseite — die zwölf Blöcke mit Bildern, dazu die Sprungliste |
| `ki-modelle.html`, `en/ai-models.html` | Was ein Modell aus Meshy, Tripo oder Rodin noch braucht |
| `changelog.html`, `<sprache>/changelog.html` | Versionsverlauf mit Auswahl — erzeugt von `tools/make_changelog.py` aus derselben Quelle wie das App-Fenster |
| `site.js` | Markiert Sprungliste und Changelog-Auswahl und zählt im Download-Kasten die Zeit bis zur Demo |
| `offline-aktivierung.html`, `activation.js` | Drei-Schritt-Seite für die Aktivierung eines Rechners ohne eigenen Netzzugang; sendet dieselbe Anfragedatei an denselben Endpunkt wie die Anwendung |
| `api/activation.php`, `api/deactivation.php` | Aktiviert genau einen Geräteplatz beziehungsweise gibt ihn mit signiertem Gerätenachweis wieder frei |
| `api/operator.php` | Nicht verlinkter JSON-Endpunkt der lokalen Support-Verwaltung; nur mit externem 256-Bit-Betreiberzugang |
| `api/activation-health.php` | Passive Bereitschaftsprobe ohne Kauf- oder Gerätedaten |
| `api/activation_common.php` | Gemeinsame Protokoll-, Signatur- und SQLite-Logik; nicht direkt aufrufen |
| `handbuch.html`, `en/manual.html` | Handbuch — erzeugt von `tools/make_manual.py`, nie von Hand ändern |
| `handbuch/` | Abbildungen des Handbuchs, je Sprache ein Ordner |
| `icon.svg` | Anwendungssymbol als Favicon — erzeugt von `tools/make_icon.py` |
| `impressum.html` | Impressum — **Entwurf, Anschrift fehlt noch** |
| `datenschutz.html` | Datenschutzerklärung — **Entwurf mit Platzhaltern** |
| `eula.html`, `agb.html`, `widerruf.html` | Rechtstexte — erzeugt von `tools/make_legal.py` aus `EULA.md`, `AGB.md` und `WIDERRUF.md`, nie von Hand ändern |
| `style.css` | Gestaltung, hell und dunkel über `prefers-color-scheme` |
| `version.json` | Versionsdatei für den Update-Hinweis (`core/updates.py`) |
| `robots.txt`, `sitemap.xml`, `llms.txt` | Was Suchmaschinen zuerst holen — erzeugt von `tools/make_seo.py`, nie von Hand ändern |
| `.htaccess` | Eine Adresse je Seite, Caching, Kompression — von Hand |

## Aktivierungsdienst vor dem Verkaufsbau

Die PHP-Dateien brauchen PHP 7.4 oder neuer mit `sodium` und `PDO_SQLite`.
Private Dateien liegen standardmäßig im Verzeichnis `solidon3d.de/appdata/`
neben `httpdocs` und sind damit über HTTP nicht erreichbar:

> **Produktionsprobe, 28.08.2026:**
> `python tools/check_activation.py` erhält öffentlich HTTP 200 und Protokoll
> 1; ein absichtlich unvollständiger POST wird als JSON mit HTTP 400 und
> `invalid_request` abgelehnt. FTPS prüft den Zertifikatsnamen über
> `a2f21.netcup.net`. Das Deployment hat vorhandene Dateien bytegenau unter
> `solidon3d.de/backups/activation/20260828-203613/` gesichert und wieder
> gelesen; private Dateien liegen in `solidon3d.de/appdata/`.

```powershell
python tools/setup_activation_server.py `
  --private "$env:LOCALAPPDATA\Solidon3D\server\activation.seed" `
  --database "$env:LOCALAPPDATA\Solidon3D\server\activation.sqlite" `
  --operator-token "$env:LOCALAPPDATA\Solidon3D\server\operator.token"
```

Das Werkzeug verweigert jedes Ziel im Repository und überschreibt einen
vorhandenen Startwert nur mit `--replace`. Sein Inhalt wird weder eingecheckt
noch ausgegeben; der öffentliche Teil muss mit `ACTIVATION_PUBLIC_KEY` in
Anwendung und PHP übereinstimmen. Danach kommen Startwert, Betreiber-Token und
Datenbank per FTPS nach `solidon3d.de/appdata/`; das Verzeichnis muss für PHP
beschreibbar bleiben.

Nur bei einem abweichenden Ablageort sind Servervariablen nötig:

```text
SOLIDON_ACTIVATION_SEED_FILE=/absoluter/pfad/activation.seed
SOLIDON_ACTIVATION_DB=/absoluter/pfad/activation.sqlite
SOLIDON_ACTIVATION_OPERATOR_TOKEN_FILE=/absoluter/pfad/operator.token
SOLIDON_ACTIVATION_MAJOR=1
```

Die Bereitschaftsprobe öffnet die Datenbank nur lesend und legt weder Datei
noch Tabellen an. Gültig signierte Aktivierungsversuche sind je Schlüssel auf
fünf pro UTC-Tag begrenzt; IP-Adressen werden dafür nicht gespeichert. Beim
nächsten gültigen Aktivierungsversuch verschwinden alle Zähler älterer
UTC-Tage. Die Datenschutzerklärung nennt auch den Fall ohne weiteren Zugriff
ausdrücklich, statt eine sofortige zeitgesteuerte Löschung zu behaupten.

`tools/deploy_activation_server.py --apply` verlangt Startwert, Datenbank und
Betreiber-Token, prüft vor dem Upload PHP-Syntax, Schlüsselpaar und
SQLite-Integrität, sichert jede vorhandene Ziel- und Privatdatei außerhalb des
Webroots und liest Sicherung und Upload bytegenau zurück. Bei einer laufenden
SQLite-WAL werden Hauptdatei und WAL zweimal stabil gelesen und über die
SQLite-Sicherungs-API zu einer geprüften Ein-Datei-Sicherung vereinigt; ein
bloßes Kopieren von `activation.sqlite` wäre keine vollständige Sicherung.
Die bisherige Produktivdatenbank mit den drei Aktivierungstabellen bleibt dabei
zulässig: Nach ihrer Sicherung legt der neue gemeinsame Endpunkt beim ersten
Aktivierungs- oder Supportaufruf die zusätzliche Audit-Tabelle idempotent an.
Die Produktivdatenbank wird für diese Migration nicht über FTPS ersetzt.
Ein abweichender Betreiber-Token wird ebenso wenig still ersetzt wie der
Signaturschlüssel.

```powershell
python tools/deploy_activation_server.py --apply `
  --seed "$env:LOCALAPPDATA\Solidon3D\server\activation.seed" `
  --database "$env:LOCALAPPDATA\Solidon3D\server\activation.sqlite" `
  --operator-token "$env:LOCALAPPDATA\Solidon3D\server\operator.token"
python tools/check_activation.py
```

Eine Betreiber-Tokenrotation ist ein eigener, absichtlicher Wartungsschritt:
zuerst mit `setup_activation_server.py --replace-operator-token` eine neue
lokale Tokendatei anlegen, dann denselben Deployment-Aufruf zusätzlich mit
`--rotate-operator-token` ausführen. Das Deployment sichert den bisherigen
Server-Token, bevor es den neuen hochlädt. Ohne den zweiten Schalter hält es
bei jeder Abweichung an. Der Aktivierungsstartwert wird dabei niemals rotiert;
das würde bereits ausgestellte Gerätezertifikate unbrauchbar machen.

Der Bereitschaftsendpunkt gibt nur Bereitschaft und Protokollversion preis; er
erhält keine Lizenz- oder Gerätedaten. Vor dem ersten Verkauf bleibt als
Geschäftsprozess-Abnahme ein echter Kauf mit Online-Aktivierung,
Offline-Dateiweg, Deaktivierung, Aktivierung auf einem zweiten Testrechner und
einem vollständigen Durchlauf der privaten Support-Verwaltung.

Die Support-Oberfläche läuft ausschließlich lokal:

```powershell
python tools/licence_admin.py `
  --token "$env:LOCALAPPDATA\Solidon3D\server\operator.token" `
  --archive "D:\Geheim\solidon-licences.jsonl"
```

Sie ordnet einen anonymen Vorratsschlüssel lokal der Transaktionskennung aus
dem MoR-Dashboard zu, sucht im privaten Archiv nach dieser Kennung,
Bestellkennung, Käuferkennung, vollständigem Schlüssel oder Digest und sendet
nur den Digest an den Server. Sperren wirkt auf neue Aktivierungen; ein schon
ausgestelltes Offline-Zertifikat bleibt wie vertraglich zugesagt lokal gültig.
Der Betreiber-Endpunkt protokolliert jede Änderung mit einem festen Anlass,
aber ohne Namen, E-Mail-Adresse oder Freitext.

Die Oberfläche führt in drei lesbaren Schritten durch **Lizenz finden →
Supportfall verstehen → Handlung auswählen**. `Strg+F` springt in die Suche,
`F5` lädt den gewählten Serverzustand erneut. Zustände stehen immer als Text
und Symbol da, nicht nur als Farbe. Generator und Oberfläche teilen sich eine
Betriebssystem-Dateisperre; vor jedem Schreibvorgang wird das vollständige
Archiv samt Signaturen und Käuferzuordnung geprüft. Eine MoR-Transaktion kann
dadurch nie zwei Lizenzen bezeichnen, und auch Schlüssel älterer
Hauptversionen bleiben über dasselbe Archiv auffindbar.

## Was Suchmaschinen sehen

`tools/make_seo.py` erzeugt drei Dateien und einen Auszeichnungsblock, alle
aus dem Bestand abgeleitet. Es läuft **nach** `make_manual.py` und
`make_legal.py`, denn es liest deren Ergebnis:

* **`sitemap.xml`** führt alle indexierbaren Seiten mit ihren
  Sprachversionen. Die Zuordnung kommt aus den `hreflang`-Angaben der Seiten
  selbst — eine zweite Liste liefe beim nächsten Zusatz auseinander. Die fünf
  Rechtstexte fehlen dort mit Absicht: sie tragen `noindex`, und eine Sitemap,
  die sie trotzdem anbietet, sagt das Gegenteil dessen, was auf der Seite
  steht. `tests/test_website.py` prüft beide Richtungen.
* **`FAQPage`-Auszeichnung** in den sechs Startseiten, gelesen aus dem
  `<div class="faq">`, das dort ohnehin steht. Damit können die elf Fragen als
  Rich Result erscheinen, und eine KI-Suche zitiert lieber Ausgezeichnetes als
  Erratenes. Die Sprungmarke des Abschnitts heißt je Sprache anders (`fragen`,
  `questions`) und wird abgelesen, nicht angenommen.
* **`llms.txt`** — dieselbe Übersicht für Sprachmodelle, die keine 24 Seiten
  crawlen wollen.

**Die Titel sind Suchanfragen, keine Etiketten.** „Funktionen — Solidon3D" war
zutreffend und trug nichts: nach „Funktionen" sucht niemand, und der
Markenname findet nur, wer ihn schon kennt — der ist im Umfeld von SolidWorks,
Solid Edge und SolidPrint3D ohnehin schwer zu halten. Was in den Titeln steht,
löst die jeweilige Seite auch ein; Begriffe, die auf der Seite nicht vorkommen,
bleiben draußen.

Die drei Rechtstexte tragen ihren Entwurfshinweis automatisch, solange ein
Platzhalter darin steht — `tools/make_legal.py` setzt ihn, und er verschwindet
beim nächsten Lauf von selbst, sobald die Angabe da ist. `tests/test_legal.py`
lässt keine Seite durch, die einen Platzhalter trägt und sich nicht als
Entwurf ausweist.

## Drei Kopplungen, die man sehen muss

**Die Startseite reißt an, die Unterseiten führen aus.** Funktionen und
KI-Modelle standen bis zum 14.08.2026 auf der Startseite und machten sie
vierzehn Bildschirme lang — der Preis begann erst bei Bildschirm elf. Beide
haben jetzt eigene Seiten, auf der Startseite steht je ein Anriss mit Verweis;
sie ist damit acht Bildschirme lang und der Preis beginnt bei 4,8. Wer einen
Anriss ändert, ändert die Unterseite mit: dieselbe Aussage darf nicht zweimal
verschieden dastehen. Die Angabe **39 Referenzanfragen** bleibt bewusst im
Anriss der Startseite — `tests/test_website.py` sucht sie dort.

**Die Startseite lebt von `handbuch/`.** Sie bindet fünf Abbildungen daraus
ein — `main-window.png`, `report.png`, `catalog.png`, `op-dialog.png` und
`start-screen.png`, je Sprache aus dem eigenen Ordner. Erzeugt werden sie von
`tools/make_figures.py`; wer dort einen Namen ändert, ändert ihn hier mit.
`tests/test_website.py` prüft jeden Verweis beider Seiten auf Existenz.

**Die Startseite führt Zahlen aus dem Register.** In der Leiste unter dem
Aufmacher stehen die Anzahl der Operationen, der Bausteine, der Normteilmaße,
der Druckerprofile und der Beispielprojekte. Sie sind abgelesen und werden
falsch, sobald eine Operation dazukommt. `tests/test_website.py` rechnet sie
gegen `REGISTRY`, `PARTS`, `standards.toml`, `printers.toml` und
`app/examples/` nach und verlangt, dass beide Sprachversionen dieselben Zahlen
führen. Wird der Test rot, ist nicht der Test veraltet, sondern die Seite.

## Die Ausgangslage

Das Produkt bekommt eine eigene Domain: **`solidon3d.de`**. Entschieden am
08.08.2026, zusammen mit der Support-Adresse `support@solidon3d.de`. Damit
liegen Website, Download, Update-Datei und Support-Postfach unter demselben
Namen wie die Anwendung — wer eine Setup-Datei lädt und im Programm eine
Adresse findet, sieht denselben Namen zweimal, nicht zwei fremde.

**Die eigene Domain macht die Einrichtung kurz.** Sie wird beim selben Anbieter
registriert, bei dem der Webspace liegt, und dort auch verwaltet: Registrar,
DNS, Webserver und Postfach in einer Oberfläche. Es entfällt alles, was die
vorherige Subdomain-Lösung gekostet hätte — die Verifizierung einer externen
Domain per TXT-Token, ein A-Record in einer fremden DNS-Zone, eine Subdomain
mit eigenem Dokumentenstamm in Plesk.

### Was mit `rs-digital.org` geschieht: nichts

Die Firmendomain bleibt unberührt, und das ist wichtiger, als es klingt. Sie
ist die primäre Domain des Google Workspace und trägt die Geschäftspost. Ihre
Zone liegt in **Google Cloud DNS**, während **Squarespace** die Registrierung
hält und deshalb keine Record-Verwaltung anbietet — beide Häuser verweisen
für DNS-Einträge aufeinander, eine Oberfläche für einen freien Record hat
derzeit keines (geprüft am 07.08.2026). Genau diese Sackgasse war der teure
Teil des alten Wegs; mit der eigenen Domain wird sie nie betreten.

Der Bestand, aufgenommen am 07.08.2026 gegen `8.8.8.8`, bleibt so, wie er ist
— **es wird kein einziger dieser Einträge angefasst**:

```
SOA     @                   ns-cloud-b1.googledomains.com / cloud-dns-hostmaster.google.com
NS      @                   ns-cloud-b1..b4.googledomains.com
A       @                   198.185.159.144  198.185.159.145  198.49.23.144  198.49.23.145
MX      @                   1 smtp.google.com
TXT     @                   v=spf1 include:_spf.google.com ~all
A       www                 198.185.159.144/145, 198.49.23.144/145
CNAME   www                 ext-sq.squarespace.com
CNAME   _domainconnect      _domainconnect.domains.squarespace.com
TXT     _domainconnect      domains.squarespace.com
TXT     google._domainkey   v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsqpu73YCiQ0O7je2AHdEBbUKkuUtpu+qc0fph0rwIoHPBHMYJqvOkE7TmwCxh5nS48yWN+k/7lda3p/FGqPocE9u0ZGWSfWzO1SCYh5p42L/MVtVea7STIq5mQb8Hd7W7mHdQy9zR8HtkMmHvGHAy0yTq6ZiJWx4BKjnmK+L5cZ2mu4QG+IXAHjNEw/t1px/K/tpvWoUzmUgPVtxPDKbXDFUXwIxfw4ZT9mCIc7yulCo+7pcXQH7y+oGg9JpC7vykztkl6ZJj9TwhXfYzQgqHfup5fupXtZdz5yxy54Kx7UfYbcI/vNEFosqxEio3NMeY99OwWWBlqgAJ/1G5Vbo9wIDAQAB
```

`_dmarc` ist auf `rs-digital.org` **nicht gesetzt**. Das bleibt ein offener
Punkt der Firmendomain, aber es blockiert die Veröffentlichung nicht mehr:
Verkaufs- und Support-Post läuft künftig über `solidon3d.de`, und dort wird
SPF und DMARC gleich richtig gesetzt (Schritt 5).

**Weder Workspace noch Squarespace liefern eigene Dateien aus.** Kein SFTP,
keine beliebigen Pfade, kein `version.json` als rohes JSON, und 255 MB
Setup-Datei sind dort ohnehin kein Anhang. Der Webspace ist deshalb ein
eigenes Produkt: **netcup Webhosting 2000**.

## Einrichtung — einmalig

1. **Webhosting bestellen, Domain gleich mit.** ✓ Bestellt am 08.08.2026.
   [Webhosting 2000](https://www.netcup.com/de/hosting/webhosting/webhosting-2000-nue)
   — Stand 07.08.2026: **75 GB** SSD, SSH/SFTP, unbegrenzt
   Let's-Encrypt-Zertifikate, **12 Monate Mindestlaufzeit**, rund 3–4 €/Monat
   je nach Aktion. `solidon3d.de` dabei als **Inklusiv- oder Zusatzdomain des
   Pakets** registrieren, nicht als externe Domain: dann verwaltet netcup die
   Zone selbst, und Schritt 2 bis 4 der alten Anleitung entfallen ersatzlos.
2. **Domain dem Webhosting zuweisen.** ✓ Erledigt am 08.08.2026. Im
   [CCP](https://www.customercontrolpanel.de/) beim Paket unter *Domains*.
   Weil die Domain dort registriert ist, zeigen ihre Nameserver bereits auf
   netcup — kein TXT-Token, keine Verifizierung, kein A-Record von Hand.
3. **Als Hauptdomain in Plesk anlegen.** ✓ Erledigt am 08.08.2026. Im CCP
   öffnet *WCP Auto-Login* Plesk. **Der Dokumentenstamm liegt je Domain**,
   nicht an der Wurzel des Zugangs: `solidon3d.de/httpdocs` — auf dem Paket
   liegen mehrere Domains nebeneinander (auch `rs-3dware.de`), jede mit
   eigenem `httpdocs`.
4. **HTTPS einschalten.** In Plesk bei der Domain der Reiter *Let's Encrypt* →
   *Installieren*, dabei `www.solidon3d.de` mit einschließen. Das Zertifikat
   erneuert sich selbst. `core/updates.py` fragt über `https://` an; ohne
   Zertifikat schlägt der Update-Hinweis fehl.
5. **Postfächer anlegen.** ✓ Erledigt; am 20.08.2026 stehen vier:
   `support@`, `marketing@`, `abrechnung@` und `noreply@`. In Plesk unter
   *E-Mail* → *E-Mail-Adresse erstellen*. Die MX-Einträge setzt netcup für
   seine eigene Zone automatisch — das betrifft ausschließlich
   `solidon3d.de`, die Workspace-Mail von `rs-digital.org` bleibt davon
   unberührt. Dazu gehören in dieselbe Zone:

   ```
   TXT   @        v=spf1 mx a include:_spf.webhosting.systems ~all
   TXT   _dmarc   v=DMARC1; p=quarantine; rua=mailto:support@solidon3d.de
   ```

   **Gemessener Stand vom 20.08.2026** (gegen `8.8.8.8`): SPF steht wie
   oben, DKIM ist aktiv unter dem Selektor `key1`, und der Reverse-Eintrag
   von `188.68.47.35` zeigt sauber auf `mx2f23.netcup.net`. **`_dmarc` fehlt
   als einziges** — ohne ihn landet Post an Gmail und Outlook.com häufiger
   im Spam, was sich anfühlt wie „Senden geht nicht", obwohl die Nachricht
   längst draußen ist. Die Include-Kennung heißt bei diesem Paket
   `_spf.webhosting.systems`, nicht `_spf.netcup.net`; vor dem Setzen
   ablesen, nicht abschreiben.

   **Ein Mailprogramm einrichten — drei Fallen.** Der Server selbst ist
   unauffällig: Postfix und Dovecot auf `188.68.47.35`, die Ports 993 und
   465 offen, Anmeldung über `PLAIN` und `LOGIN`, kein OAuth. Trotzdem hat
   die Einrichtung am 20.08.2026 einen halben Tag gekostet, an drei Stellen,
   die keine Fehlermeldung benennt:

   - **Der Servername ist `mx2f23.netcup.net`, nicht `mail.solidon3d.de`.**
     Beide zeigen auf dieselbe Maschine, aber das Zertifikat lautet
     `*.netcup.net` und passt unter dem eigenen Domainnamen nicht. Der
     Client bricht ab — beim Senden eher als beim Empfangen.
   - **Outlook rät den Postausgang als `smtp.netcup.net`.** Das ist ein
     anderer Rechner (`46.38.225.170`), der die Postfächer dieses Pakets
     nicht kennt; dort scheitert jede Anmeldung, unabhängig vom Passwort.
     Ein- und Ausgang tragen denselben Namen.
   - **`autodiscover.solidon3d.de` zeigt auf den Webserver** und liefert ein
     abgelaufenes Plesk-Selbstsignat statt einer Konfiguration. Die
     automatische Einrichtung ist damit unbrauchbar — von Hand einrichten.
     Für Outlook überbrückt das eine lokale Autodiscover-Datei zusammen mit
     `PreferLocalXML`.

   Und die Ports, die Plesk unter *Link zur E-Mail-Konfiguration* in den
   blauen Kacheln zeigt (143, 110, 25), sind die **unverschlüsselten**. Die
   richtigen stehen daneben im Kleingedruckten: 993 für IMAP, 465 für SMTP,
   beide mit SSL/TLS.

   Das neue Outlook taugt für diese Postfächer nicht: Es synchronisiert
   IMAP-Konten über die Microsoft-Cloud, und weil Absender und Empfänger
   dann beide `@solidon3d.de` heißen, versucht Microsoft die Zustellung im
   eigenen Haus und weist sie ab. Der Unzustellbarkeitsbericht kommt
   erkennbar von Microsoft, nicht von Postfix — dann liegt der Fehler nie
   auf dem Server. Das klassische Outlook nehmen.
6. **Hochladen.** ✓ Erstmals erledigt am 08.08.2026 (86 Dateien per SFTP).
   Passwort für SSH/SFTP im CCP unter *Webhosting-Zugang* setzen, dann den
   Inhalt dieses Ordners (ohne diese README) nach `solidon3d.de/httpdocs`
   legen. Die Ordnerstruktur beibehalten — `en/` bleibt ein Unterordner.
   Eine früher versehentlich mit hochgeladene README lag dort öffentlich und
   wurde entfernt — sie gehört nicht auf den Server.
7. **Prüfen.** `https://solidon3d.de/` zeigt die Startseite,
   `https://solidon3d.de/version.json` liefert das rohe JSON, und eine
   Testmail an `support@solidon3d.de` kommt an. Zusätzlich eine an
   `admin@rs-digital.org` — sie muss ankommen wie vorher, sonst hat doch
   jemand die falsche Zone angefasst.

## Vor der Veröffentlichung

- Platzhalter ersetzen: Anschrift in `impressum.html` und `WIDERRUF.md`,
  Zahlungsdienstleister in `AGB.md` (die Kontaktadresse support@solidon3d.de
  steht schon; der Hoster in `datenschutz.html` ist seit der Bestellung
  eingetragen — netcup). Danach `tools/make_legal.py` laufen lassen — die
  Entwurfshinweise fallen dann von selbst weg. Der dort zugesagte Vertrag
  über Auftragsverarbeitung (Art. 28 DSGVO) wird im netcup-CCP abgeschlossen.
- **Die Rechtstexte fachlich prüfen lassen.** `EULA.md`, `AGB.md` und
  `WIDERRUF.md` sind sorgfältig geschriebene Entwürfe und keine
  Rechtsberatung. Vor dem ersten Verkauf gehören sie einem Anwalt vorgelegt,
  zusammen mit der Frage nach Kleinunternehmerregelung und Umsatzsteuer. Die
  Widerrufsbelehrung folgt dem gesetzlichen Muster; ihre Wirkung hängt aber
  daran, dass der Bestellvorgang die Zustimmung nach § 356 Abs. 5 BGB
  ausdrücklich abfragt — ohne diese Abfrage im Kaufprozess nützt der beste
  Text nichts.
- Das Postfach `support@solidon3d.de` existiert. Robert hat das am 28.08.2026
  bestätigt; die Adresse steht auf beiden Startseiten, im Impressum, im
  Über-Dialog und im Fehlerbericht der Anwendung.

  **Am 20.08.2026 geprüft, und zwar der ganze Weg:** `api/support.php` liegt
  unter `httpdocs/api/` und antwortet, `tools/check_support.py` hat eine
  echte Sendung durchgebracht (Vorgang `S-20260820-589ee2`), und der
  Mailserver hat für alle vier Adressen von außen eingelieferte Post
  angenommen — eine erfundene Adresse derselben Domain lehnt er dagegen mit
  `550 User unknown` ab, die Annahme ist also echt und kein Catch-All.
- Die ausgelieferten Dateien aus der CI in das Verzeichnis legen und den
  Download-Kasten mit `tools/make_download.py` daraus erzeugen. Ab der nächsten
  Version sind es fünf: `Solidon3D-Setup-<Version>.exe`, zwei macOS-`.pkg`,
  `Solidon3D-<Version>-x86_64.AppImage` zum direkten Start und
  `Solidon3D-<Version>-x86_64.flatpak` zur Installation. Das Linux-Archiv
  bleibt im Bau, wird aber nicht hochgeladen. Derselbe Lauf erzeugt den
  Changelog in allen Sprachen automatisch aus `changelog/` neu.
- `version.json` führen: `version` ist die veröffentlichte Version,
  `url` die Download-Seite, `notes` ein Satz zur Neuerung. Die Anwendung
  vergleicht gegen `APP_VERSION` in `app/branding.py` und zeigt nur einen
  Hinweis — sie lädt nie selbst.
