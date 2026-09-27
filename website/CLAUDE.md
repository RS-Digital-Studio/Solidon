# `website/` — die öffentlichen Seiten

**Die Dokumentation dieses Ordners ist `website/README.md`** — die
ausführliche Karte zu Dateien, Gestaltung, Bewegung, SEO, Aktivierung und der
Zusage „nichts von außen“; sie wird hier nicht wiederholt. Hier steht, was
beim **Arbeiten** daran zusätzlich gilt. Erzeugen und Hochladen: `/erzeugen`;
Anlässe dieser Karte: `konzepte/begruendungen/karte-website.md`.

## Erzeugt oder von Hand — die Frage vor jeder Änderung

| Erzeugt (nie von Hand ändern) | Werkzeug |
|---|---|
| `handbuch.html`, `<sprache>/manual.html`, `handbuch/` | `tools/make_manual.py` |
| `changelog.html`, `<sprache>/changelog.html` | `tools/make_changelog.py`, automatisch aus `make_download.py` |
| `eula.html`, `agb.html`, `widerruf.html`, `datenschutz.html` | `tools/make_legal.py` |
| `robots.txt`, `sitemap.xml`, `llms.txt` | `tools/make_seo.py` |
| `icon.svg` | `tools/make_icon.py` |
| `bilder/beleg-*.webp`, `bilder/schritt-*.webp` | `tools/make_web_images.py <sprache> --nur fenster` — ein Kindprozess je Sprache mit eigenen Nutzerverzeichnissen, ein maximiertes Hauptfenster, elf Motive als Vollbild oder Zuschnitt daraus |
| `bilder/verwandlung-*.svg` | `tools/make_web_images.py de --nur verwandlung` (ohne Fenster) |
| `bilder/feature-*.webp` | `tools/make_feature_images.py`, ein nativer Prozess je Motiv |
| `bilder/loop-anpassen*.(mp4|webm|webp)` | `tools/make_video.py <ordner> webloop anpassen <sprache>` — Bedienloop mit Anfangs- und Schlussbild |
| `bilder/weg4-formen*.(mp4|webm|webp)` | `tools/make_video.py <ordner> formen loop website/teile/weg4-stein-formen.p3d --name weg4-formen <sprache>` |
| `dl/`, `version.json` | `tools/make_download.py`; unterschrieben von `tools/sign_version.py` |

Von Hand: `index.html`, `funktionen.html`, `ki-modelle.html`,
`security.html` (je Sprache), `offline-aktivierung.html` und
`activation.js` (ausgeliefert von `tools/deploy_activation_server.py`),
`style.css`, `site.js`, `.htaccess`, `api/`, `fonts/`, die Datei zur
Bestätigung bei der Suchmaschine, die Rechtstext-**Quellen** im
Wurzelverzeichnis (`EULA.md`, `AGB.md`, `WIDERRUF.md`, `DATENSCHUTZ.md`), die
Schaustücke in `bilder/`, die gezeichnete `bilder/fernsteuerung-mcp.svg`
(textfrei, eine Datei für alle sechs Sprachen) — und **`impressum.html`**: Es
trägt Anschrift und Vertretungsangaben, die nirgendwo sonst herkommen.
`teile/` sind lokale Projektquellen und reisen nie hinaus.

**Jede Datei steht in genau einer der beiden Listen** — eine, die in keiner
steht, bekommt beim nächsten Umbau von jedem eine andere Behandlung. Eine
Änderung an einer erzeugten Datei ist beim nächsten Lauf weg; geändert wird
das Werkzeug oder die Quelle.

## Aufnahmen der Anwendung — der Bildstandard

Jedes Bild und jeder Loop aus der Anwendung zeigt **das ganze Solidon-Fenster,
maximiert auf dem 2560 × 1440-Schirm** (Entscheidung Robert), in nativen
Bildpunkten, Gerätepixelverhältnis 1. Braucht eine Karte einen anderen
Zuschnitt, schneiden ihn die Werkzeuge aus der Vollbildaufnahme — jede Leiste
ganz im Bild oder ganz draußen, nie auf einen angesetzten Grund. Die
Begründungen stehen bei `make_video.WEB_VIDEO_WIDTH` und im Modulkopf von
`make_web_images.py`.

- **Ein Prozess je Sprache und Motivgruppe.** Mehrere Hauptfenster
  nacheinander enden in einem nativen Abbruch.
- **Nicht parallel zu einer anderen Sitzung aufnehmen, die denselben Schirm
  benutzt** — oder es der Wache überlassen: `make_figures.foreign_window_over`
  lässt jedes Werkzeug warten, solange ein fremdes Fenster über der Aufnahme
  liegt.
- **Der Bausteinkatalog braucht einen gültigen Bereichsnachweis**
  (`tools/check_part_ranges.py`); sonst steht unter jeder Kachel die Warnung
  — und genau so im Bild.
- **Angesehen wird jedes Bild** in voller Größe und in Handybreite, bevor es
  auf die Seite kommt. Die Maße in `<img>` und `<video>` kommen aus den
  Dateien (`test_every_picture_states_the_size_it_actually_has`).

Die sechs Handbuchseiten lesen Inhalt **und sichtbaren Seitenrahmen** (Titel,
Navigation, Sprunglinks, Inhaltsverzeichnis, PDF-Ränder, Fußzeile mit
Impressum und Datenschutz) aus den Katalogen unter `app/i18n/locales/` —
nichts davon wird in `make_manual.py` je Sprache abgeschrieben. Eine weitere
vollständige Katalogdatei erzeugt so ihre vollständige Handbuchseite.

## Was beim Ausliefern schiefgeht

- **`api/support.php` muss nach `httpdocs/api/`.** Fehlt es dort, scheitert
  das Senden aus der Anwendung — erst beim Kunden.
- **Die Aktivierungs-Endpunkte brauchen ihren Zustand außerhalb von
  `httpdocs`**: Startwert, Betreiber-Token und SQLite-Datenbank bereitet
  `tools/setup_activation_server.py` vor, `tools/check_activation.py` nimmt sie
  über HTTPS ab.
- **Große Dateien reißen die Verbindung** (rund 1,8 MB/s; mehrere Pakete am
  Stück gehen schief). **Ein halbes Paket sieht ganz aus** — deshalb am Ende
  `--nachpruefen`, vor der Freigabe `--mit-pruefsumme`: Die Länge fängt den
  Abbruch, erst die Prüfsumme eine vollständige, aber falsche Datei.
- **`stamp_assets.py` läuft als Letztes**, nach allen Bilder- und
  Seitenläufen.
- **Ein sichtbarer Beleg braucht eine belegte Rechtekette**: Prompt oder
  Eingabe, Startwert, Erzeugerfassung, Gewichte, Lizenz und Weitergaberecht
  stehen vor der Veröffentlichung fest, sonst verschwinden Aussage, Verweis und
  Datei aus dem Auslieferungspfad; eine spätere Bearbeitung in Solidon heilt
  die Herkunft nicht. `upload_website.py` prüft jedes öffentliche Medium vor
  der ersten Netzverbindung vollständig und überschneidungsfrei gegen
  `ASSET-RIGHTS.toml`.
- **Projekt- und Geometriequellen bleiben intern**: `upload_website.py`
  schließt `website/teile/` ganz aus, gleich welcher Name oder welche Endung.
  Eine öffentliche Tauschstelle gibt es nicht; Bausteindateien bleiben im
  lokalen Dateiweg der Anwendung.
- **Der Download-Kasten zeigt die fünf Plätze aus `DELIVERED`**
  (`tools/make_download.py`): Setup, AppImage, Flatpak, beide macOS-Pakete —
  obwohl der Baulauf acht Dateien liefert. Archive werden nicht hochgeladen.
  Die Regel dazu steht in `.claude/rules/auslieferung.md`.

## Die sechs Sprachfassungen

- **Wer eine Klasse oder Struktur von Hand in eine Seite schreibt, schreibt
  sie in eine** — die anderen fünf bleiben, wie sie waren, und nichts meldet
  sich. Strukturänderungen an `index.html` (Abschnitte, Klassen, Bänder,
  Kapitel) werden deshalb **über alle sechs Fassungen gezählt**, bevor sie als
  fertig gelten.
- **Keine Stilregel hängt an einem Sprungziel.** Die Anker heißen je Sprache
  anders (`#unterstuetzen` gegen `#support`, `#generiert` gegen
  `#generated`); gestaltet wird über Klassen, ein Anker ist ein Sprungziel und
  sonst nichts.
- Eine Unterseite ohne Bildspalte trägt am Aufmacher zusätzlich `hero-copy`:
  Der Text nutzt auf großen Schirmen die Mitte statt neben einer leeren
  Spalte zu stehen. Das Scrollpolster für Sprungziele berücksichtigt unter
  30rem die zweizeilige Kopfzeile.
- **Ein Tag kann einen Namen zerteilen**: Steht die Marke als
  `<span>Solid</span>on`, entkommt sie jeder Volltextsuche. Wer umbenennt,
  sucht auch nach Teilstücken.

## Die Startseite und der Weg bis 1.0

Die Startseite führt jeden Gedanken **einmal**: ein Abschnitt je Frage, was
eine Unterseite ausführt, steht als Anriss mit Verweis. Auf den Aufmacher
folgen vierzehn Abschnitte: Ablauf, Download, Kennzahlen, drei Schritte,
Kennst du das, vier Wege, Ergebnisse, Unterschied, was Solidon3D nicht ist,
Preis, Unterstützen, Voraussetzungen, Fragen, Schluss. Wer einen neuen will,
prüft zuerst, ob ein bestehender die Frage schon beantwortet.

- **Jeder Weg endet mit einem Verweis** (`.way-more`) auf die Seite, die ihn
  ausführt; Weg 3 trägt den alten Anker des Generatorabschnitts.
- **Preis als drei gleichwertige Karten**: Demo, privat, gewerblich. Nur die
  Demokarte hat einen Knopf; gekauft wird vor dem 1. November nichts.
  `<article class="licence" data-summary>` bleibt den beiden Lizenzen
  vorbehalten, denn `make_seo.py` liest daraus `llms.txt`.
- **Unterstützen**: oben „Der Weg bis 1.0“ in zwei Spalten, Geschafft und
  Geplant; darunter Person und Kosten neben dem Handlungsfeld mit beiden
  Wegen; ganz unten der Stand der Kampagne, der erst auf Klick lädt. Die
  geplanten Punkte stammen aus RM-188 und sind von Robert zur Veröffentlichung
  freigegeben: Nachbau, Montage und Maßblatt, Resin-Stufe 2, Zeichnen und
  Maße im Bild, dazu Fehlerbehebungen und Tempo — mit dem Satz „Geplant heißt
  nicht zugesagt“.
- **Bei jedem Release wandert die Zeitleiste mit**: Die neue Version kommt als
  `li.done is-now` unter Geschafft, die Markierung der vorigen fällt weg, ein
  erledigter Planpunkt verschwindet aus Geplant — in allen sechs Fassungen.
  Ein Planpunkt, den das Paket längst enthält, ist derselbe Fehler wie ein
  fehlender.

## Prüfen

Die Startseite erklärt den Nutzen mit eigenständig verständlichen Beispielen;
die Funktionsseite vertieft nach Kundenaufgaben, weitere Werkzeuggruppen in
nativen `details`-Elementen, und ordnet ihre Gruppen über `data-operations`
den Operationen zu — dieselben Gruppen in allen Fassungen, jede
veröffentlichte Operation beschrieben. Bilder zeigen echte
Operationsergebnisse ohne eingebrannte Sprache; Überschriften,
Alternativtexte und Beschreibungen werden in allen sechs Fassungen gepflegt.
Bildbelege und Geometriemesswerte bleiben außerhalb des öffentlichen Ordners.

**Website und Paket gehen zusammen online**: Paket, Handbuch,
Funktionsumfang und Downloadangaben müssen zusammenpassen, die Website wird
nicht vorab allein veröffentlicht — implementierte Funktionen stehen deshalb
ohne Entwicklungsvorbehalt da. Operations- und Bausteinzahlen beziehen sich
auf die angebotene Downloadversion; ihr Beleg ist die beim Paketbau erzeugte
Handbuchreferenz, deren Versionsstempel zu `version.json` passt. Der
Entwicklungsstand erhöht sie nicht vorzeitig. Die Zuordnung prüft
Vollständigkeit und Sprachgleichheit, Inhalt und Nutzen die redaktionelle
Prüfung. Der Anker `#entwicklung` bleibt
für alte Sprunglinks, seine Beschriftung nennt den Kundennutzen.

`tests/test_website.py` ist der Wächter über allem hier — tote Verweise,
Inhaltsstempel, Paketgrößen, „nichts von außen“, die Sprachfassungen — und
läuft im normalen Tor mit. Ansehen im Browser geht mit QtWebEngine; heller
Modus und reduzierte Bewegung nur über Chromium-Flags.
