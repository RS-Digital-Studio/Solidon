# `website/` — die öffentlichen Seiten

**Die Dokumentation dieses Ordners ist `website/README.md`** — die ausführliche
Karte zu Dateien, Gestaltung, Bewegung, SEO, Aktivierung und der Zusage
„nichts von außen". Sie wird
hier nicht wiederholt.

Hier steht nur, was beim **Arbeiten** daran zusätzlich gilt.

## Erzeugt oder von Hand — die Frage vor jeder Änderung

| Erzeugt (nie von Hand ändern) | Werkzeug |
|---|---|
| `handbuch.html`, `<sprache>/manual.html`, `handbuch/` | `tools/make_manual.py` |
| `changelog.html`, `<sprache>/changelog.html` | `tools/make_changelog.py`, automatisch aus `make_download.py` |
| `eula.html`, `agb.html`, `widerruf.html` | `tools/make_legal.py` |
| `robots.txt`, `sitemap.xml`, `llms.txt` | `tools/make_seo.py` |
| `icon.svg` | `tools/make_icon.py` |
| `bilder/beleg-*.png` | `tools/make_web_images.py` |
| `dl/` | `tools/make_download.py` |

Von Hand: `index.html`, `funktionen.html`, `ki-modelle.html`, `style.css`,
`site.js`, `.htaccess`, die Rechtstext-**Quellen** im Wurzelverzeichnis
(`EULA.md`, `AGB.md`, `WIDERRUF.md`) und die Schaustücke in `bilder/`.

Eine Änderung an einer erzeugten Datei ist beim nächsten Lauf weg. Wer sie
ändern will, ändert das Werkzeug oder die Quelle.

## Vier Dinge, die beim Ausliefern schiefgehen

- **`api/support.php` muss nach `httpdocs/api/`.** Fehlt es dort, scheitert
  das Senden aus der Anwendung — und zwar erst beim Kunden.
- **Die Aktivierungs-Endpunkte brauchen ihren Zustand außerhalb von
  `httpdocs`.** Privater Startwert, Betreiber-Token und SQLite-Datenbank werden mit
  `tools/setup_activation_server.py` vorbereitet und mit
  `tools/check_activation.py` über HTTPS abgenommen.
- **Große Dateien reißen die Verbindung.** Rund 1,8 MB/s, und mehrere Pakete
  am Stück gehen schief. **Ein halbes Paket sieht ganz aus** — deshalb am Ende
  `--nachpruefen`.
- **`stamp_assets.py` läuft als Letztes**, nach allen Bilder- und
  Seitenläufen.
- **Der Download-Kasten zeigt ab der nächsten Version fünf Pakete**, obwohl der
  Baulauf acht liefert: Windows, zwei macOS-Pakete sowie für Linux AppImage und
  Flatpak. Das Archiv bleibt ein Bauartefakt und wird nicht hochgeladen. Die
  aktuelle Seite bleibt bis zu diesem Release unverändert.

## Eine Falle beim Suchen

**Ein Tag kann einen Namen zerteilen.** Steht die Marke als
`<span>Solid</span>on`, entkommt sie jeder Volltextsuche — nach einer
Umbenennung bleibt der alte Name genau dort stehen, wo niemand ihn findet.
Wer umbenennt, sucht auch nach Teilstücken.

## Prüfen

`tests/test_website.py` ist der Wächter über allem hier: tote Verweise,
Inhaltsstempel, Paketgrößen, „nichts von außen", die Sprachfassungen. Er läuft
im normalen Tor mit.

Ansehen im Browser geht mit QtWebEngine; heller Modus und reduzierte Bewegung
nur über Chromium-Flags.
