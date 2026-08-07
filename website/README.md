# Website — solidon3d.de

Statische Seite, kein JavaScript, keine externen Ressourcen. Alles in diesem
Ordner wird unverändert hochgeladen; einen Build-Schritt gibt es nicht.

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
| `style.css` | Gestaltung, hell und dunkel über `prefers-color-scheme` |
| `version.json` | Versionsdatei für den Update-Hinweis (`core/updates.py`) |

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

1. **Webhosting bestellen, Domain gleich mit.**
   [Webhosting 2000](https://www.netcup.com/de/hosting/webhosting/webhosting-2000-nue)
   — Stand 07.08.2026: **75 GB** SSD, SSH/SFTP, unbegrenzt
   Let's-Encrypt-Zertifikate, **12 Monate Mindestlaufzeit**, rund 3–4 €/Monat
   je nach Aktion. netcup hat die Preise im Mai 2026 erhöht und die Pakete
   umgeschnitten — die Zahlen vor der Bestellung am Warenkorb gegenprüfen.
   `solidon3d.de` dabei als **Inklusiv- oder Zusatzdomain des Pakets**
   registrieren, nicht als externe Domain: dann verwaltet netcup die Zone
   selbst, und Schritt 2 bis 4 der alten Anleitung entfallen ersatzlos.
2. **Domain dem Webhosting zuweisen.** Im
   [CCP](https://www.customercontrolpanel.de/) beim Paket unter *Domains*.
   Weil die Domain dort registriert ist, zeigen ihre Nameserver bereits auf
   netcup — kein TXT-Token, keine Verifizierung, kein A-Record von Hand.
3. **Als Hauptdomain in Plesk anlegen.** Im CCP öffnet *WCP Auto-Login* Plesk.
   Die zugewiesene Domain erscheint unter *Websites & Domains* mit dem
   Dokumentenstamm `/httpdocs`. Keine Subdomain, kein eigener Stamm. Fünf bis
   zehn Minuten, bis es greift.
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
6. **Hochladen.** Passwort für SSH/SFTP im CCP unter *Webhosting-Zugang*
   setzen, dann den Inhalt dieses Ordners (ohne diese README) nach `/httpdocs`
   legen. Die Ordnerstruktur beibehalten — `en/` bleibt ein Unterordner.
7. **Prüfen.** `https://solidon3d.de/` zeigt die Startseite,
   `https://solidon3d.de/version.json` liefert das rohe JSON, und eine
   Testmail an `support@solidon3d.de` kommt an. Zusätzlich eine an
   `admin@rs-digital.org` — sie muss ankommen wie vorher, sonst hat doch
   jemand die falsche Zone angefasst.

## Vor der Veröffentlichung

- Platzhalter in `impressum.html` und `datenschutz.html` ersetzen
  (Anschrift, Hoster; die Kontaktadresse support@solidon3d.de steht schon)
  und beide Texte prüfen — sie sind Entwürfe, keine Rechtsberatung.
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
