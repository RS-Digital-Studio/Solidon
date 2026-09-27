# Begründungen zu `website/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf das verdichtet wurde,
> was beim Arbeiten an der Website gilt. Die Karte steht dort; hier stehen die
> Anlässe und das Warum ihres Tages — wörtlich, gegliedert nach den
> Überschriften der Karte. *Früher unter …* nennt die Stelle der alten Karte.

## Erzeugt oder von Hand — die Frage vor jeder Änderung

*Früher unter „Erzeugt oder von Hand — die Frage vor jeder Änderung“.*

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

## Aufnahmen der Anwendung — der Bildstandard

*Früher unter „Aufnahmen der Anwendung — der Bildstandard“.*

Jedes Bild und jeder Loop aus der Anwendung zeigt **das ganze Solidon-Fenster,
maximiert auf dem 2560 × 1440-Schirm** (Robert, 23.09.2026: „dass der ganze
Bildschirm verwendet wird und wir nicht nur so eine kleine Szene haben"), in
nativen Bildpunkten, Gerätepixelverhältnis 1. Braucht eine Karte einen anderen
Zuschnitt, schneiden ihn die Werkzeuge aus der Vollbildaufnahme — so, dass
jede Leiste ganz im Bild steht oder ganz draußen, nie auf einen angesetzten
Grund. Die Begründungen stehen bei `make_video.WEB_VIDEO_WIDTH` und im
Modulkopf von `make_web_images.py`.

## Was beim Ausliefern schiefgeht

Der letzte Punkt der alten Liste („zeigt ab der nächsten Version fünf Pakete …
Die aktuelle Seite bleibt bis zu diesem Release unverändert“) war überholt:
Seit 0.5.0 zeigt der Kasten die fünf Plätze aus `DELIVERED`
(`tools/make_download.py`), wie `.claude/rules/auslieferung.md` und
`/erzeugen` es sagen.

*Früher unter „Vier Dinge, die beim Ausliefern schiefgehen“.*

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

## Die sechs Sprachfassungen

*Früher unter „Eine Falle bei den sechs Sprachfassungen“.*

**Wer eine Klasse oder Struktur von Hand in eine Seite schreibt, schreibt
sie in eine** — die anderen fünf sehen danach genauso aus wie vorher, und
nichts meldet sich. Am 31.08.2026 trug die deutsche Startseite eine
Band-Regel einen Tag lang allein; fünf Fassungen blieben 48 Punkte höher,
und kein Test sah es. Strukturänderungen an `index.html` (Abschnitte,
Klassen, Bänder, Kapitel) werden deshalb immer **über alle sechs Fassungen
gezählt**, bevor sie als fertig gelten — die Zählung nebeneinander fand den
Fall in Minuten.

**Und keine Stilregel hängt an einem Sprungziel.** Die Anker heißen je
Sprache anders (`#unterstuetzen` gegen `#support`, `#generiert` gegen
`#generated`), und eine Regel auf den deutschen Anker gilt nur in einer
Fassung. So stand die deutsche Unterstützung wochenlang mit anderem Abstand
und schmalerem Spendenkasten da als die fünf anderen. Gestaltet wird über
Klassen; ein Anker ist ein Sprungziel und sonst nichts.

Eine Unterseite ohne Bildspalte trägt am Aufmacher zusätzlich `hero-copy`.
Damit nutzt der Text auf großen Bildschirmen die Mitte statt links neben
einer leeren, wie ein Ladefehler wirkenden Spalte zu stehen; auf kleinen
Fenstern bleibt die normale Leserichtung erhalten.

Das Scrollpolster für Sprungziele berücksichtigt unter 30rem die zweizeilige
Kopfzeile; die Zielüberschrift bleibt beim direkten Anspringen darunter sichtbar.

## Die Startseite und der Weg bis 1.0

*Früher unter „Die Startseite und der Weg bis 1.0“.*

Die Startseite führt jeden Gedanken **einmal**: ein Abschnitt je Frage, und
was eine Unterseite ausführt, steht hier als Anriss mit einem Verweis. Auf
den Aufmacher folgen vierzehn Abschnitte in dieser Folge: Ablauf, Download,
Kennzahlen, drei Schritte, Kennst du das, vier Wege, Ergebnisse,
Unterschied, was Solidon3D nicht ist, Preis, Unterstützen, Voraussetzungen,
Fragen, Schluss. Wer einen neuen Abschnitt will, prüft
zuerst, ob ein bestehender die Frage schon beantwortet — der doppelte
Generatorabschnitt und die zweite Funktionsleiste waren genau so entstanden.

- **Jeder Weg endet mit einem Verweis** (`.way-more`) auf die Seite, die ihn
  ausführt. Weg 3 trägt den alten Anker des Generatorabschnitts.
- **Preis als drei gleichwertige Karten**: Demo, privat, gewerblich. Nur die
  Demokarte hat einen Knopf; gekauft wird vor dem 1. November nichts.
  `<article class="licence" data-summary>` bleibt den beiden Lizenzen
  vorbehalten, denn `make_seo.py` liest daraus `llms.txt`.
- **Unterstützen**: oben „Der Weg bis 1.0" in zwei Spalten, Geschafft und
  Geplant; darunter Person und Kosten neben dem Handlungsfeld mit beiden
  Wegen; ganz unten der Stand der Kampagne, der erst auf Klick lädt. Die
  geplanten Punkte stammen aus RM-188 und sind von Robert zur Veröffentlichung
  freigegeben (24.09.2026): Nachbau, Montage und Maßblatt, Resin-Stufe 2,
  Zeichnen und Maße im Bild, dazu Fehlerbehebungen und Tempo. Der Satz
  „Geplant heißt nicht zugesagt" gehört dazu.
- **Bei jedem Release wandert die Zeitleiste mit**: Die neue Version kommt als
  `li.done is-now` unter Geschafft, die Markierung der vorigen fällt weg, und
  ein erledigter Planpunkt verschwindet aus Geplant — in allen sechs
  Fassungen. Ein Planpunkt, der auf der Seite noch als geplant steht, obwohl
  das Paket ihn längst enthält, ist derselbe Fehler wie ein fehlender.

## Prüfen

*Früher unter „Prüfen“.*

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
