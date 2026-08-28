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

Ein einziges Skript liegt dabei, `site.js`, und es kommt von hier — kein CDN,
keine Bibliothek, keine Schriftart von außen, kein Zählpixel. Es tut zwei
Dinge, und beide sind Zugabe: die Sprungliste der Funktionsseite markiert den
Block, der gerade gelesen wird, und der Download-Kasten der Startseite zählt
die Zeit bis zur Demo herunter. Ohne das Skript bleibt die Liste eine
gewöhnliche Sprungliste, und der Kasten nennt Tag und Uhrzeit im Klartext, wie
er es ohnehin tut — der Zähler steht als `hidden` daneben und wird nur
sichtbar, wenn ihn jemand füllt. `tests/test_website.py` prüft nicht mehr auf
„kein JavaScript", sondern auf den Teil, der die Zusage der Seite trägt:
**nichts von außen**.

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
| `site.js` | Markiert in der Sprungliste den gelesenen Block und zählt im Download-Kasten die Zeit bis zur Demo — das einzige Skript |
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

## Was Suchmaschinen sehen

`tools/make_seo.py` erzeugt drei Dateien und einen Auszeichnungsblock, alle
aus dem Bestand abgeleitet. Es läuft **nach** `make_manual.py` und
`make_legal.py`, denn es liest deren Ergebnis:

* **`sitemap.xml`** führt die 24 indexierbaren Seiten mit ihren
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
- Das Postfach `support@solidon3d.de` muss zustellen, bevor die Adresse
  ausgeliefert wird — sie steht auf beiden Startseiten, im Impressum, im
  Über-Dialog und im Fehlerbericht der Anwendung. Eine Adresse, die im
  Programm steht und keine Post annimmt, ist schlimmer als keine.

  **Am 20.08.2026 geprüft, und zwar der ganze Weg:** `api/support.php` liegt
  unter `httpdocs/api/` und antwortet, `tools/check_support.py` hat eine
  echte Sendung durchgebracht (Vorgang `S-20260820-589ee2`), und der
  Mailserver hat für alle vier Adressen von außen eingelieferte Post
  angenommen — eine erfundene Adresse derselben Domain lehnt er dagegen mit
  `550 User unknown` ab, die Annahme ist also echt und kein Catch-All.
  **Offen bleibt der letzte Zentimeter:** angenommen ist nicht gelesen. Das
  bestätigt erst ein Blick ins Postfach, und der ging bisher nicht, weil
  Webmail für die Domain abgeschaltet ist (`/webmail` antwortet mit 404) und
  kein Mailprogramm das Postfach erreichte. Webmail in Plesk unter
  *E-Mail-Einstellungen* der Domain auf Roundcube stellen — dann ist der
  Nachweis eine Minute Arbeit und hängt an keinem Client.
- Die ausgelieferten Dateien aus der CI in das Verzeichnis legen und den
  Download-Kasten mit `tools/make_download.py` daraus erzeugen. Ab der nächsten
  Version sind es fünf: `Solidon3D-Setup-<Version>.exe`, zwei macOS-`.pkg`,
  `Solidon3D-<Version>-x86_64.AppImage` zum direkten Start und
  `Solidon3D-<Version>-x86_64.flatpak` zur Installation. Das Linux-Archiv
  bleibt im Bau, wird aber nicht hochgeladen.
- `version.json` führen: `version` ist die veröffentlichte Version,
  `url` die Download-Seite, `notes` ein Satz zur Neuerung. Die Anwendung
  vergleicht gegen `APP_VERSION` in `app/branding.py` und zeigt nur einen
  Hinweis — sie lädt nie selbst.
