# Website — formwerk.rs-digital.org

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

`rs-digital.org` ist die einzige Domain und zugleich die primäre Domain des
Google Workspace. Gemessen am 07.08.2026:

| | |
|---|---|
| Registrar | **Squarespace Domains II LLC** (RDAP) — registriert 24.01.2026, läuft 24.01.2027 ab |
| Nameserver | `ns-cloud-b1..b4.googledomains.com` — Erbe der Google-Domains-Übernahme, betrieben für Squarespace |
| A-Records | `198.185.159.144/145`, `198.49.23.144/145` — Squarespace |
| MX | `smtp.google.com` — Workspace-Mail |

**Die DNS-Einträge werden bei Squarespace verwaltet, nicht im Google-Admin.**
Die Admin-Konsole führt die Domain als primäre Domain und bestätigt, bietet
aber keine Record-Verwaltung. Wer den A-Record im Google-Admin sucht, sucht
vergeblich.

**Weder Workspace noch Squarespace liefern eigene Dateien aus.** Kein SFTP,
keine beliebigen Pfade, kein `version.json` als rohes JSON, und 255 MB
Setup-Datei sind dort ohnehin kein Anhang. Der Webspace ist deshalb ein
eigenes Produkt: **netcup Webhosting 2000**.

## Einrichtung — einmalig

**Zwei Dinge, die dabei schiefgehen können, und beide kosten Mail:**

* **Die Nameserver bleiben, wo sie sind.** Nicht auf netcup umstellen — sonst
  müssen alle bestehenden Einträge dort nachgebaut werden, und ein
  vergessener MX heißt: die Workspace-Mail ist tot.
* **Von netcups DNS-Vorschlagsliste wird nur der A-Eintrag der Subdomain
  übernommen.** netcup nennt dort auch MX-Einträge für sein eigenes
  Mailsystem. Wer die überträgt, leitet die Post von `admin@rs-digital.org`
  auf einen Server um, der sie nicht kennt.

Alles andere an der Domain — die vier A-Records auf Squarespace, der MX auf
Google — bleibt unberührt. Es kommt genau *ein* Eintrag hinzu.

1. **Webhosting bestellen.** [Webhosting 2000](https://www.netcup.com/de/hosting/webhosting/webhosting-2000-nue)
   — Stand 07.08.2026: **75 GB** SSD, SSH/SFTP, unbegrenzt
   Let's-Encrypt-Zertifikate, **3 externe Domains**, **12 Monate
   Mindestlaufzeit**, rund 3–4 €/Monat je nach Aktion. netcup hat die Preise
   im Mai 2026 erhöht und die Pakete umgeschnitten — die Zahlen vor der
   Bestellung am Warenkorb gegenprüfen. Die im Tarif enthaltenen Domains
   werden nicht gebraucht; `rs-digital.org` bleibt, wo sie ist.
2. **Domain als externe Domain eintragen.** Im
   [CCP](https://www.customercontrolpanel.de/) beim Webhosting-Paket der
   Reiter *Externe Domains*. netcup nennt einen TXT-Token zur Verifizierung;
   den beim DNS-Verwalter der Domain als TXT-Record anlegen (siehe Schritt 4,
   dieselbe Oberfläche). Nach der Verifizierung die Domain dem Paket
   zuweisen. Ein Transfer findet dabei nicht statt.
3. **IP des Webservers ablesen.** Im CCP unter *Allgemeine Verwaltung und
   Konfiguration des Webhostings* stehen IPv4 und IPv6
   ([Anleitung](https://www.netcup.com/de/helpcenter/documentation/web-hosting/interface)).
4. **A-Record setzen** — bei **Squarespace**, geprüft am 07.08.2026:
   [account.squarespace.com/domains](https://account.squarespace.com/domains)
   → *DNS → DNS Settings → Custom Records*
   ([Anleitung](https://support.squarespace.com/hc/en-us/articles/360002101888-Edit-your-domain-s-DNS-records)).
   Nicht im Google-Admin suchen — dort steht die Domain zwar, aber ohne
   Record-Verwaltung. Dort:

   ```
   Typ: A     Host: formwerk     Wert: <IPv4 aus Schritt 3>
   ```

   Optional zusätzlich `AAAA` auf die IPv6. Nichts löschen, nichts ändern.
5. **Subdomain in Plesk anlegen.** Im CCP *WCP Auto-Login* öffnet Plesk. Unter
   *Websites & Domains* → *Subdomain hinzufügen*: `formwerk`, eigener
   Dokumentenstamm (etwa `/httpdocs/formwerk`). Fünf bis zehn Minuten, bis
   es greift.
6. **HTTPS einschalten.** In Plesk bei der Subdomain der Reiter *Let's
   Encrypt* → *Installieren*. Das Zertifikat erneuert sich selbst.
   `core/updates.py` fragt über `https://` an; ohne Zertifikat schlägt der
   Update-Hinweis fehl.
7. **Hochladen.** Passwort für SSH/SFTP im CCP unter *Webhosting-Zugang*
   setzen, dann den Inhalt dieses Ordners (ohne diese README) in den
   Dokumentenstamm legen. Die Ordnerstruktur beibehalten — `en/` bleibt ein
   Unterordner.
8. **Prüfen.** `https://formwerk.rs-digital.org/` zeigt die Startseite,
   `https://formwerk.rs-digital.org/version.json` liefert das rohe JSON.
   Und zur Sicherheit eine Testmail an `admin@rs-digital.org` — sie muss
   ankommen wie vorher.

## Vor der Veröffentlichung

- Platzhalter in `impressum.html` und `datenschutz.html` ersetzen
  (Anschrift, Hoster; die Kontaktadresse admin@rs-digital.org steht schon)
  und beide Texte prüfen — sie sind Entwürfe, keine Rechtsberatung.
- Das Postfach `admin@rs-digital.org` anlegen bzw. prüfen, dass es
  ankommt — es steht auf beiden Startseiten, im Impressum, im Über-Dialog
  und im Fehlerbericht der Anwendung. **Offen am 07.08.2026:** die
  Admin-Konsole bietet bei der Domain noch die Aktion *Gmail aktivieren* an,
  obwohl der MX auf `smtp.google.com` zeigt. Ob die Domain-Mail zugestellt
  wird, ist damit nicht erwiesen — vor der Bestellung des Webspace klären,
  nicht danach.
- Den Installer in das Verzeichnis legen und den Download-Kasten in beiden
  `index.html` auf den echten Link umstellen. Die Dateien kommen aus der CI
  (oder lokal aus `tools/make_installer.py`) und heißen
  `Formwerk-Setup-<Version>.exe` für Windows und
  `Formwerk-<Version>-linux-x86_64.tar.gz` für Linux.
- `version.json` führen: `version` ist die veröffentlichte Version,
  `url` die Download-Seite, `notes` ein Satz zur Neuerung. Die Anwendung
  vergleicht gegen `APP_VERSION` in `app/branding.py` und zeigt nur einen
  Hinweis — sie lädt nie selbst.
