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
| `bilder/beleg-*.webp`, `bilder/schritt-*.webp` | `tools/make_web_images.py <sprache> --nur fenster` — ein Kindprozess je Sprache mit eigenen Nutzerverzeichnissen, ein maximiertes Hauptfenster, elf Motive als Vollbild oder Zuschnitt daraus |
| `bilder/verwandlung-*.svg` | `tools/make_web_images.py de --nur verwandlung` (ohne Fenster) |
| `bilder/feature-*.webp` | `tools/make_feature_images.py`, ein nativer Prozess je Motiv |
| `bilder/loop-anpassen*.(mp4|webm|webp)` | `tools/make_video.py <ordner> webloop anpassen <sprache>` — Bedienloop mit Anfangs- und Schlussbild |
| `bilder/weg4-formen*.(mp4|webm|webp)` | `tools/make_video.py <ordner> formen loop website/teile/weg4-stein-formen.p3d --name weg4-formen <sprache>` |
| `dl/` | `tools/make_download.py` |

Von Hand: `index.html`, `funktionen.html`, `ki-modelle.html`, `style.css`,
`site.js`, `.htaccess`, die Rechtstext-**Quellen** im Wurzelverzeichnis
(`EULA.md`, `AGB.md`, `WIDERRUF.md`, `DATENSCHUTZ.md`), die Schaustücke in
`bilder/`, die gezeichnete `bilder/fernsteuerung-mcp.svg` (textfrei, eine
Datei für alle sechs Sprachen) — und **`impressum.html`**.

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

## Aufnahmen der Anwendung — der Bildstandard

Jedes Bild und jeder Loop aus der Anwendung zeigt **das ganze Solidon-Fenster,
maximiert auf dem 2560 × 1440-Schirm** (Robert, 23.09.2026: „dass der ganze
Bildschirm verwendet wird und wir nicht nur so eine kleine Szene haben"), in
nativen Bildpunkten, Gerätepixelverhältnis 1. Braucht eine Karte einen anderen
Zuschnitt, schneiden ihn die Werkzeuge aus der Vollbildaufnahme — so, dass
jede Leiste ganz im Bild steht oder ganz draußen, nie auf einen angesetzten
Grund. Die Begründungen stehen bei `make_video.WEB_VIDEO_WIDTH` und im
Modulkopf von `make_web_images.py`.

- **Ein Prozess je Sprache und Motivgruppe.** Mehrere Hauptfenster
  nacheinander enden in einem nativen Abbruch.
- **Nicht parallel zu einer anderen Sitzung aufnehmen, die denselben Schirm
  benutzt** — oder es der Wache überlassen: `make_figures.foreign_window_over`
  lässt jedes Werkzeug warten, solange ein fremdes Fenster über der Aufnahme
  liegt.
- **Der Bausteinkatalog braucht einen gültigen Bereichsnachweis**
  (`tools/check_part_ranges.py`); sonst steht unter jeder Kachel die Warnung,
  dass der Bereichstest nicht mehr passt — und genau so im Bild.
- **Angesehen wird jedes Bild** in voller Größe und in Handybreite, bevor es
  auf die Seite kommt. Die Maße in den `<img>`- und `<video>`-Angaben kommen
  aus den Dateien (`test_every_picture_states_the_size_it_actually_has`).

Die sechs Handbuchseiten lesen Inhalt **und sichtbaren Seitenrahmen** aus den
Katalogen unter `app/i18n/locales/`. Titel, Navigation, Sprunglinks,
Inhaltsverzeichnis und PDF-Ränder werden nicht in `make_manual.py` je Sprache
abgeschrieben. Damit erzeugt eine weitere vollständige Katalogdatei auch ihre
vollständige Handbuchseite ohne deutschen Mischrahmen.
Die Handbuch-Fußzeile hält Impressum und Datenschutz bei einem direkten
Seitenaufruf erreichbar; ihre Texte kommen ebenfalls aus den Katalogen.

## Vier Dinge, die beim Ausliefern schiefgehen

- **`api/support.php` muss nach `httpdocs/api/`.** Fehlt es dort, scheitert
  das Senden aus der Anwendung — und zwar erst beim Kunden.
- **Die Aktivierungs-Endpunkte brauchen ihren Zustand außerhalb von
  `httpdocs`.** Privater Startwert, Betreiber-Token und SQLite-Datenbank werden mit
  `tools/setup_activation_server.py` vorbereitet und mit
  `tools/check_activation.py` über HTTPS abgenommen.
- **Große Dateien reißen die Verbindung.** Rund 1,8 MB/s, und mehrere Pakete
  am Stück gehen schief. **Ein halbes Paket sieht ganz aus** — deshalb am Ende
  `--nachpruefen`, vor der Freigabe mit `--mit-pruefsumme`: Die Länge fängt
  den Abbruch, erst die Prüfsumme eine vollständige, aber falsche Datei.
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

Das Scrollpolster für Sprungziele berücksichtigt unter 30rem die zweizeilige
Kopfzeile; die Zielüberschrift bleibt beim direkten Anspringen darunter sichtbar.

## Eine Falle beim Suchen

**Ein Tag kann einen Namen zerteilen.** Steht die Marke als
`<span>Solid</span>on`, entkommt sie jeder Volltextsuche — nach einer
Umbenennung bleibt der alte Name genau dort stehen, wo niemand ihn findet.
Wer umbenennt, sucht auch nach Teilstücken.

## Prüfen

Die Startseite erklärt den Nutzen mit eigenständig verständlichen Beispielen.
Die Funktionsseite vertieft nach Kundenaufgaben; zusätzliche Werkzeuggruppen
stehen in nativen `details`-Elementen. Bilder zeigen echte Operationsergebnisse,
ohne eingebrannte Sprache. Überschriften, Alternativtexte und Beschreibungen
werden in allen sechs Fassungen gepflegt. Bildbelege und
Geometriemesswerte bleiben außerhalb des öffentlichen Website-Ordners.

Die Funktionsseite ordnet Beschreibungsgruppen über `data-operations` den
Operationsnamen zu. Alle Sprachfassungen führen dieselben Gruppen. Jede
veröffentlichte Operation muss beschrieben sein. Die überarbeiteten Seiten
gehen gemeinsam mit der nächsten Demo online: Neue, bereits implementierte
Funktionen werden deshalb als normaler Funktionsumfang beschrieben, ohne
Entwicklungsvorbehalte. Vor dem gemeinsamen Upload müssen Paket, Handbuch,
Funktionsumfang und Downloadangaben zusammenpassen. Die neue Website wird
nicht vorab allein veröffentlicht. Der bestehende Anker `#entwicklung` bleibt
für alte Sprunglinks erhalten; seine Beschriftung nennt den Kundennutzen.

Operations- und Bausteinzahlen beziehen sich auf die angebotene Downloadversion.
Die beim Paketbau erzeugte Handbuchreferenz ist dafür der Registerbeleg; ihr
Versionsstempel muss zu `version.json` passen. Der laufende Entwicklungsstand
darf diese Zahlen nicht vorzeitig erhöhen. Die Zuordnung prüft Vollständigkeit
und Sprachgleichheit, die redaktionelle Prüfung weiterhin Inhalt und Nutzen.

`tests/test_website.py` ist der Wächter über allem hier: tote Verweise,
Inhaltsstempel, Paketgrößen, „nichts von außen", die Sprachfassungen. Er läuft
im normalen Tor mit.

Ansehen im Browser geht mit QtWebEngine; heller Modus und reduzierte Bewegung
nur über Chromium-Flags.
