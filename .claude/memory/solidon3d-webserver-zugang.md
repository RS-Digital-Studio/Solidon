---
name: solidon3d-webserver-zugang
description: "solidon3d.de liegt auf netcup-Webhosting; Dokumentenstamm ist solidon3d.de/httpdocs (je Domain einer). Systembenutzer hosting245877, Upload per paramiko-SFTP oder ftplib-FTPS. Scheitert SFTP, ist meist der SSH-Schalter schuld; ein 530 über FTPS ist dagegen wirklich das Passwort."
metadata:
  type: project
---

Die Website liegt seit dem 08.08.2026 auf dem netcup-Webhosting:
Host `188.68.47.33`, Systembenutzer `hosting245877`.

**Seit dem 20.08.2026 gibt es ein Werkzeug dafuer**: `tools/upload_website.py`
laedt genannte Dateien, `--geaendert` oder `--seit <commit>` per FTPS hoch und
liest den Zugang aus `.webserver.json` im Repository-Wurzelverzeichnis. Die
Datei ist in `.gitignore` und traegt das Passwort; sie liegt nur auf dieser
Maschine. Fehlt sie auf einer anderen, schreibt `--vorlage` sie an, und das
Passwort setzt Robert bei Bedarf in Plesk neu.

**Der Dokumentenstamm liegt je Domain**, nicht an der Wurzel des Zugangs:
`solidon3d.de/httpdocs`. Daneben liegt `rs-3dware.de` mit eigenem
`httpdocs` auf demselben Paket.

## Der Nutzername war nie das Problem — der SSH-Schalter war es

Am 19.08.2026 lehnte der Server `hosting245877` mit mehreren Passwörtern ab,
und der Verdacht fiel auf den Nutzernamen. Falsch. Im Plesk-Dialog
*Informationen zur Verbindung* steht der Grund:

> „Zugriff via FTP ist immer aktiviert, Zugriff über SSH oder
> Remotedesktop jedoch nur, wenn die Berechtigung gegeben wird."

Stand SSH-Zugriff auf *kein Zugriff*, scheitert **paramiko grundsätzlich** —
es fährt SFTP über SSH. Die `AuthenticationException` liest sich wie ein
falsches Passwort und ist eine fehlende Berechtigung. Seit dem 20.08.2026
steht der Schalter unter *Hosting-Einstellungen → SSH-Zugriff* auf
`/bin/bash (chrooted)`, und beide Wege gehen: SFTP und FTPS.

**Why:** Wer den SSH-Fehlschlag dem Passwort zuschreibt, erfragt ein neues
nach dem anderen und kommt nie an. Der Dienst antwortet ja normal. Und drei
Fehlversuche in Folge sind bei fail2ban der Weg zu einer gesperrten IP.

**Am 20.08.2026 hat sich das bewährt.** `--fehlend` scheiterte mit
`ftplib.error_perm: 530 Login incorrect` — also FTPS, also das Passwort und
nicht der Schalter. Nach **einem** Versuch angehalten und gefragt; Robert
setzte es in Plesk neu, der nächste Versuch lud die elf Dateien hoch. Ohne
die Trennung oben wären es drei Fehlversuche und eine gesperrte IP geworden.

**How to apply:** Erst **einen** Anmeldeversuch, nicht den ganzen Upload.
Scheitert er, trennt ein zweiter über FTPS (`ftplib.FTP_TLS`,
Standardbibliothek, kein Lizenzthema) die beiden Ursachen: FTP läuft
*immer* — kommt dort ein `530`, ist es wirklich das Passwort; geht FTP und
SSH nicht, ist es der Schalter. Danach anhalten und fragen, nie Namen oder
Passwörter durchprobieren.

Upload über `scratchpad/upload_website.py` (paramiko, liest
`SOLIDON3D_SFTP_PASS`) mit einer eigenen kleinen venv im Scratchpad — nie
paramiko in die Projekt-.venv, das bricht die Lizenzprüfung der Suite.
`website/` ohne `README.md`, Ordnerstruktur beibehalten; das Skript meldet
zum Schluss, was auf dem Server liegt und lokal fehlt.

**Was dabei liegen bleiben darf:** `.well-known/acme-challenge/*` gehört
Let's Encrypt, und `favicon.ico` erzeugt `tools/make_icon.py` — beides ist
nicht im Repo und wird nicht mit hochgeladen. Nicht löschen.

Notweg ohne beides: der Dateimanager in Plesk.

## Wo der Zugang endet: beim DNS

Der Webspace ist erreichbar, die **DNS-Zone nicht** — die liegt im netcup-CCP
hinter einem eigenen Login. Alles, was einen TXT-Eintrag verlangt, muss
deshalb Robert setzen: SPF, DMARC, DKIM und eine Domain-Property in der
Google Search Console.

Für die Search Console gibt es dafür den Weg über den Webspace: eine
**URL-Präfix-Property** statt einer Domain-Property, bestätigt durch eine
Datei wie `google<hash>.html` in `website/`. Google gibt für Datei und DNS
**verschiedene** Token aus — ein DNS-Token in eine Datei zu schreiben,
bestätigt nichts.

**Achtung:** Die Datei endet auf `.html` und ist doch keine Seite.
`tools/make_seo.py` und `tests/test_website.py` schließen sie am Namensmuster
aus; ohne das stünde sie in der Sitemap, und die Search Console meldete eine
angebotene Seite ohne Inhalt — ausgerechnet die, die man gerade einrichtet.

## Die Domain fuhr PHP 7.4, und die neue `api/` braucht 8.1

Gemessen am 02.09.2026 mit einer Wegwerf-Sonde (`<?php echo PHP_VERSION;`
hochladen, abrufen, löschen): **PHP 7.4.33**, `cgi-fcgi`,
`/var/www/vhosts/system/solidon3d.de/etc/php.ini`. `stats.php`,
`count.php`, `support.php`, `activation_common.php` und
`cleanup_private_state.php` aus dem Repository verlangen 8.1 — `stats.php`
beendet sich darunter mit einer **leeren 503** (kein Body, keine der eigenen
Kopfzeilen; das ist das Erkennungszeichen). Die Fassung stellt nur Plesk um
(*Websites & Domains → PHP-Einstellungen*), nicht FTP und nicht das Chroot.

**Die Zugangsakte der Statistik liegt seit dem 02.09.2026 dort, wo die neue
Seite sie erwartet:** `solidon3d.de/appdata/stats-access.php` mit 0600,
`appdata` und `solidon-stats` mit 0700 (`SITE CHMOD` über FTPS geht). Die alte
`httpdocs/api/.stats-zugang.php` ist am selben Tag vom Server genommen — ein
Passwort-Hash im Webroot ist unnötig, sobald ihn niemand mehr liest.
`upload_website.py` verweigert jeden Upload, solange nicht inventarisierte
Medien auf dem Server liegen (Rechtenachweis); eine einzelne PHP-Datei geht
dann direkt per `storbinary`, vorher die Serverfassung sichern.

### Ein PHP-Versionswechsel setzt `open_basedir` zurück und legt still zwei Dienste lahm

Robert stellte am 02.09.2026 in Plesk auf 8.5 um. Dabei setzt Plesk
`open_basedir` auf seinen Standard `{DOCROOT}/:{TMP}/…` — PHP sieht danach
**nur noch `httpdocs`**. Beide Datenordner liegen absichtlich daneben, und
damit standen sofort:

* `solidon-stats` → der Download-Zähler schrieb keine Zeile mehr,
* `appdata` → `activation-health.php` meldete „Der Aktivierungsdienst ist noch
  nicht vollständig eingerichtet" (503).

**Und niemand merkt es**, denn die Weiterleitung auf die Pakete funktioniert
weiter: Kunden laden herunter, nur gezählt wird nichts. Aufgefallen ist es
allein, weil die Statistikseite gleichzeitig hochgeladen wurde und mit 503
antwortete.

Behoben mit der zweiten der beiden Auswahlmöglichkeiten im Feld:
`{WEBSPACEROOT}/:{TMP}/:/:/var/lib/php/sessions`. `{WEBSPACEROOT}` ist das
Webspace-Stammverzeichnis, eine Ebene über `httpdocs` — Plesks Hilfetext
(„Dokumentenstammverzeichnis der primären Website") ist an dieser Stelle
irreführend. Die Ordner bleiben dabei aus dem Netz unerreichbar; es geht nur
um den Lesezugriff des Skripts.

**Die Probe dauert zwanzig Sekunden** und gehört nach jeder Änderung an den
PHP-Einstellungen dazu: `activation-health.php` muss 200 geben, und die
Zähldatei muss nach einem Abruf von `count.php?f=<paket>` wachsen. Steht sie
still, ist es `open_basedir` — nicht der Code.
