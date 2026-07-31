# Website — formwerk.rsdigital.de

Statische Seite, kein JavaScript, keine externen Ressourcen. Alles in diesem
Ordner wird unverändert hochgeladen; einen Build-Schritt gibt es nicht.

## Dateien

| Datei | Zweck |
|---|---|
| `index.html` | Startseite deutsch |
| `en/index.html` | Startseite englisch |
| `impressum.html` | Impressum — **Entwurf mit Platzhaltern** |
| `datenschutz.html` | Datenschutzerklärung — **Entwurf mit Platzhaltern** |
| `style.css` | Gestaltung, hell und dunkel über `prefers-color-scheme` |
| `version.json` | Versionsdatei für den Update-Hinweis (`core/updates.py`) |

## Einrichtung — einmalig

1. **Subdomain anlegen.** Beim Hoster von rsdigital.de eine Subdomain
   `formwerk.rsdigital.de` anlegen und auf ein eigenes Verzeichnis des
   Webspace zeigen lassen (bei den meisten Hostern ein Eintrag im
   Kundenmenü; der DNS-Eintrag entsteht dabei automatisch).
2. **HTTPS aktivieren.** Ein Let's-Encrypt-Zertifikat für die Subdomain
   einschalten — bei den üblichen Hostern ein Haken im selben Menü.
   `core/updates.py` fragt über `https://` an; ohne Zertifikat schlägt der
   Update-Hinweis fehl.
3. **Hochladen.** Den Inhalt dieses Ordners (ohne diese README) per
   SFTP/FTP in das Verzeichnis der Subdomain legen. Die Ordnerstruktur
   beibehalten — `en/` bleibt ein Unterordner.
4. **Prüfen.** `https://formwerk.rsdigital.de/` zeigt die Startseite,
   `https://formwerk.rsdigital.de/version.json` liefert das rohe JSON.

## Vor der Veröffentlichung

- Platzhalter in `impressum.html` und `datenschutz.html` ersetzen
  (Anschrift, Kontaktadresse, Hoster) und beide Texte prüfen — sie sind
  Entwürfe, keine Rechtsberatung.
- Den Installer in das Verzeichnis legen und den Download-Kasten in beiden
  `index.html` auf den echten Link umstellen.
- `version.json` führen: `version` ist die veröffentlichte Version,
  `url` die Download-Seite, `notes` ein Satz zur Neuerung. Die Anwendung
  vergleicht gegen `APP_VERSION` in `app/branding.py` und zeigt nur einen
  Hinweis — sie lädt nie selbst.
