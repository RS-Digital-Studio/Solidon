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
| `bilder/weg{1,2,3,4}-*.(mp4|png|webm)` | `tools/make_video.py` |
| `dl/` | `tools/make_download.py` |

Von Hand: `index.html`, `funktionen.html`, `ki-modelle.html`, `style.css`,
`site.js`, `.htaccess`, die Rechtstext-**Quellen** im Wurzelverzeichnis
(`EULA.md`, `AGB.md`, `WIDERRUF.md`, `DATENSCHUTZ.md`), die Schaustücke in
`bilder/` — und **`impressum.html`**.

`datenschutz.html` und `impressum.html` standen bis zum 30.08.2026 in
**keiner** der beiden Listen, und das Börsen-Konzept hat sich darauf
verlassen: Es nannte `make_legal.py` als den Weg, auf dem der Datenschutz
entsteht — das Werkzeug erzeugte aber nur drei Dokumente und **verlinkte** die
beiden anderen. Eine Datei, die weder als erzeugt noch als handgepflegt
geführt ist, bekommt beim nächsten Umbau von jedem eine andere Behandlung.

Der Datenschutz wird seither wirklich erzeugt (`DATENSCHUTZ.md`), das
Impressum bleibt Handarbeit: Es trägt Anschrift und Vertretungsangaben, die
nirgendwo sonst herkommen, und ein Erzeuger dafür wäre eine Vorlage mit genau
einem Verwender.

Eine Änderung an einer erzeugten Datei ist beim nächsten Lauf weg. Wer sie
ändern will, ändert das Werkzeug oder die Quelle.

Der Weg-3-Loop wird reproduzierbar aus dem mitgelieferten Beispiel erzeugt:
`.venv\Scripts\python.exe tools\make_video.py <temporärer Ordner> generieren
loop de app\examples\weg3-generiert-aufbereiten.p3d`. Seine eingebettete
Geometrie stammt ausschließlich aus `tests/data/meshes/generated_figure.stl`;
Ausgabe- und Eingangsbytes stehen zusätzlich in `ASSET-RIGHTS.toml`.

Die sechs Handbuchseiten lesen Inhalt **und sichtbaren Seitenrahmen** aus den
Katalogen unter `app/i18n/locales/`. Titel, Navigation, Sprunglinks,
Inhaltsverzeichnis und PDF-Ränder werden nicht in `make_manual.py` je Sprache
abgeschrieben. Damit erzeugt eine weitere vollständige Katalogdatei auch ihre
vollständige Handbuchseite ohne deutschen Mischrahmen.

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
- **Ein sichtbarer Beleg braucht eine belegte Rechtekette.** Prompt oder
  Eingabe, Startwert, Erzeugerfassung, Gewichte, Lizenz und Weitergaberecht
  stehen vor der Veröffentlichung fest; fehlt eines davon, verschwinden
  Aussage, Verweis und Datei aus dem Auslieferungspfad. Eine spätere
  Bearbeitung in Solidon heilt die Herkunft des Ausgangsmodells nicht.
  `upload_website.py` prüft deshalb vor der ersten Netzverbindung jedes
  öffentliche Medium vollständig und überschneidungsfrei gegen
  `ASSET-RIGHTS.toml`.
- **Projekt- und Geometriequellen unter `website/` bleiben intern.**
  `upload_website.py` schließt `website/teile/` als lokalen Quellordner
  vollständig und unabhängig von Dateiname oder Endung aus. Eine öffentliche
  Tauschstelle gibt es nicht; Bausteindateien bleiben im lokalen Dateiweg der
  Anwendung und reisen nie über die Website.
- **Der Download-Kasten zeigt ab der nächsten Version fünf Pakete**, obwohl der
  Baulauf acht liefert: Windows, zwei macOS-Pakete sowie für Linux AppImage und
  Flatpak. Das Archiv bleibt ein Bauartefakt und wird nicht hochgeladen. Die
  aktuelle Seite bleibt bis zu diesem Release unverändert.

## Eine Falle bei den sechs Sprachfassungen

**Wer eine Klasse oder Struktur von Hand in eine Seite schreibt, schreibt
sie in eine** — die anderen fünf sehen danach genauso aus wie vorher, und
nichts meldet sich. Am 31.08.2026 trug die deutsche Startseite eine
Band-Regel einen Tag lang allein; fünf Fassungen blieben 48 Punkte höher,
und kein Test sah es. Strukturänderungen an `index.html` (Abschnitte,
Klassen, Bänder, Kapitel) werden deshalb immer **über alle sechs Fassungen
gezählt**, bevor sie als fertig gelten — die Zählung nebeneinander fand den
Fall in Minuten.

Eine Unterseite ohne Bildspalte trägt am Aufmacher zusätzlich `hero-copy`.
Damit nutzt der Text auf großen Bildschirmen die Mitte statt links neben
einer leeren, wie ein Ladefehler wirkenden Spalte zu stehen; auf kleinen
Fenstern bleibt die normale Leserichtung erhalten.

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
