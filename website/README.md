# Website — solidon3d.de

Statische Seite, kein JavaScript, keine externen Ressourcen. Alles in diesem
Ordner wird unverändert hochgeladen; einen Build-Schritt gibt es nicht.

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
| `handbuch.html`, `en/manual.html` | Handbuch — erzeugt von `tools/make_manual.py`, nie von Hand ändern |
| `handbuch/` | Abbildungen des Handbuchs, je Sprache ein Ordner |
| `icon.svg` | Anwendungssymbol als Favicon — erzeugt von `tools/make_icon.py` |
| `impressum.html` | Impressum — **Entwurf, Anschrift fehlt noch** |
| `datenschutz.html` | Datenschutzerklärung — **Entwurf mit Platzhaltern** |
| `eula.html`, `agb.html`, `widerruf.html` | Rechtstexte — erzeugt von `tools/make_legal.py` aus `EULA.md`, `AGB.md` und `WIDERRUF.md`, nie von Hand ändern |
| `style.css` | Gestaltung, hell und dunkel über `prefers-color-scheme` |
| `version.json` | Versionsdatei für den Update-Hinweis (`core/updates.py`) |

Die drei Rechtstexte tragen ihren Entwurfshinweis automatisch, solange ein
Platzhalter darin steht — `tools/make_legal.py` setzt ihn, und er verschwindet
beim nächsten Lauf von selbst, sobald die Angabe da ist. `tests/test_legal.py`
lässt keine Seite durch, die einen Platzhalter trägt und sich nicht als
Entwurf ausweist.

## Zwei Kopplungen, die man sehen muss

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
`app/examples/` nach und verlangt, dass beide Sprachfassungen dieselben Zahlen
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
5. **Postfach `support@solidon3d.de` anlegen.** In Plesk unter *E-Mail* →
   *E-Mail-Adresse erstellen*. Die MX-Einträge setzt netcup für seine eigene
   Zone automatisch — das betrifft ausschließlich `solidon3d.de`, die
   Workspace-Mail von `rs-digital.org` bleibt davon unberührt. Dazu gehören
   in dieselbe Zone:

   ```
   TXT   @        v=spf1 include:_spf.netcup.net ~all
   TXT   _dmarc   v=DMARC1; p=quarantine; rua=mailto:support@solidon3d.de
   ```

   DKIM aktiviert Plesk auf Wunsch bei der Domain selbst. Die genaue
   SPF-Include-Kennung steht im netcup-Helpcenter — vor dem Setzen ablesen,
   nicht aus dieser Datei abschreiben.
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
- Den Installer in das Verzeichnis legen und den Download-Kasten in beiden
  `index.html` auf den echten Link umstellen. Die Dateien kommen aus der CI
  (oder lokal aus `tools/make_installer.py`) und heißen
  `Solidon3D-Setup-<Version>.exe` für Windows und
  `Solidon3D-<Version>-linux-x86_64.tar.gz` für Linux.
- `version.json` führen: `version` ist die veröffentlichte Version,
  `url` die Download-Seite, `notes` ein Satz zur Neuerung. Die Anwendung
  vergleicht gegen `APP_VERSION` in `app/branding.py` und zeigt nur einen
  Hinweis — sie lädt nie selbst.
