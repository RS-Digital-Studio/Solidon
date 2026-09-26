---
name: statistikseite-lokal-vorschauen
description: "Die angemeldete Statistikseite (api/stats.php) lässt sich weder auf dem Server noch im eingebauten Browser direkt prüfen; der Weg ist ein lokaler PHP-Server mit erfundenen Zählzeilen, selbst erzeugtem Token und Bildschirmfotos per Chrome headless."
metadata:
  type: reference
---

Am 24.09.2026 beim Umbau der Statistikseite gemessen. Das Passwort der
Seite kenne ich nicht und gebe auch keins ein; die angemeldete Ansicht auf
dem Server sieht nur Robert. Geprüft wird deshalb lokal:

1. **Dokumentenstamm im Scratchpad**: `website/api/` kopieren, dazu
   `version.json`, `sitemap.xml` und kleine Attrappen unter `dl/` mit den
   echten Paketnamen.
2. **Erfundene Zählzeilen über zwei Monate**, je UTC-Monat eine `.jsonl`
   (Felder `t k v r u`), mit mehreren Versionen, die einander ablösen.
3. **Token selbst erzeugen**: `signing_key()`/`make_token()` aus
   `stats.php` in `php -r` nachbauen (wie `_stats_test_access` in
   `tests/test_public_php_security.py`), Hash in eine eigene
   `stats-access.php`, Umgebung `SOLIDON_STATS_DIR` und
   `SOLIDON_STATS_ACCESS_FILE` setzen, `php -S` starten, HTML und
   `?format=json` mit `Cookie: solidon_stats=<token>` holen und als Datei
   ablegen.
4. **Ansehen**: Der eingebaute Browser zeigt `file://` nur als Standbild
   ohne Werkzeuge; ein kurzfristiger Eintrag in `.claude/launch.json`
   (`python -m http.server` auf den Vorschauordner) macht ihn bedienbar.
   Danach wieder entfernen, die Datei ist eingecheckt.
5. **Bildschirmfotos**: `C:\Program Files\Google\Chrome\Application\chrome.exe
   --headless=new --screenshot --window-size=1440,6600`. Heller und dunkler
   Modus über eine Kopie, in der `@media (prefers-color-scheme: dark)` durch
   `@media all` bzw. `@media not all` ersetzt ist.

**Falle: Chrome headless hat eine Mindestbreite von rund 500 Punkten.** Ein
Foto mit `--window-size=390,…` wird an der rechten Kante abgeschnitten und
sieht aus wie ein überlaufendes Layout. Die Handybreite misst man im
eingebauten Browser (`resize_window` mit `preset: mobile`, dann
`scrollWidth` gegen `clientWidth`).

Die Zufallsdaten hängen an „jetzt“, jeder Lauf zeigt leicht andere Zahlen —
für die Gestaltung egal, für einen Zahlenvergleich nicht. Zahlen prüfen die
Tests, nicht die Vorschau.

Beim Hochladen hält `upload_website.py` weiterhin wegen der alten,
nicht inventarisierten Bilder auf dem Server an; der Weg für eine einzelne
PHP-Datei steht in [[solidon3d-webserver-zugang]] (Serverfassung sichern,
`connect` + `upload` aus dem Werkzeug, alles in **einer** Sitzung, vor dem
Zurücklesen `cwd("/")` — `upload()` wechselt ins Zielverzeichnis, und ein
`RETR` mit vollem Pfad meldet sonst 550; zu viele Anmeldungen in Folge
laufen in einen Timeout).
