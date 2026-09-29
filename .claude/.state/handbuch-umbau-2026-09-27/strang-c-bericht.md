# Strang C — Bericht (Rest von HB-10)

Arbeitsbaum `F:\3D Druck.handbuch-pdf`, Zweig `handbuch-pdf`, abgezweigt von
`handbuch-umbau` am Stand `8fa13081f`. Messungen, Protokolle, Skripte, Bilder
und Beispiel-PDFs: `F:\3D Druck\output\review\handbuch-pdf-2026-09-27\`.

## Ergebnis

Alle vier Punkte aus §12.3 sind gebaut, geprüft und gepusht; HB-10 steht in
§9 des Konzepts auf `[x]`. Arbeitsbaum sauber, Wegwerfbäume entfernt.

## Commits (Zweig `handbuch-pdf`, gepusht)

1. `8abf2ba87` Verzeichnis und Text des Handbuchs gliedern sich nach seinen Teilen
2. `7ac97c6a5` Das PDF des Handbuchs trägt Lesezeichen für Teile und Kapitel
3. `febba2f4d` Das Handbuch-PDF bettet die Schrittbilder als JPEG ein und wiegt ein Sechstel weniger
4. `ae9646a62` Das Handbuchkonzept führt HB-10 als fertig, mit Messung vorher und nachher

Geänderte Dateien: `tools/make_manual.py`, `tests/test_manual.py`,
`tools/CLAUDE.md`, `konzepte/begruendungen/karte-tools.md`, die fünf Kataloge
(je eine Zeile weg: der alte Zwischentitel), Konzept §9 Zeile HB-10.
Nicht angefasst: Texte der Seiten, `manual.OUTLINE`, `app/ui/`, Anleitungen,
die Lede-Texte in `make_manual.py` (Strang A zieht sie nach).

## Was gebaut ist

1. **Gliederung.** `contents()` zeigt je Teil aus `Page.part` (Reihenfolge
   von `manual.pages()`, Titel aus `PART_TITLES`) eine Kennzeile und darunter
   seine Kapitel; `anchored()` setzt vor das erste gefundene Kapitel eines
   Teils eine Teilüberschrift `<h2 class="part">` ohne Anker. Ein Teil ohne
   Seiten (heute *Anleitungen*) erscheint nicht; die Nummern laufen durch.
   Keine zweite Zuordnung. Im Druck beginnt jeder Teil auf einem neuen Blatt,
   das erste Kapitel steht direkt darunter (auch ein Referenzkapitel). Dazu:
   Die Verzeichniszeilen trugen im Druck den Fingermindestraum aus
   `style.css` (2,75 rem, jede Zeile 11,6 mm); im Druck aufgehoben, das
   Verzeichnis passt jetzt auf ein Blatt statt zwei.
2. **Lesezeichen.** In `_stamp`, im selben Schreibvorgang: aus den
   benannten Zielen, die schon die Kopfzeile liest (`_chapter_starts`), je
   Teil ein Lesezeichen und darunter seine Kapitel. Ein Kapitel springt an
   dieselbe Stelle wie sein Verzeichniseintrag (Ziel übernommen), ein Teil
   an den Kopf der Seite seines ersten Kapitels. Das PDF öffnet mit
   sichtbaren Lesezeichen (`/UseOutlines`).
3. **JPEG im Druck.** `write_pdf` druckt eine Kopie der Seite in einem
   Ordner auf Zeit (`_print_copy`): Verweise um die Bildschirmfotos fallen
   dort weg (vorher per Skript im geladenen Dokument), relative Adressen
   werden absolut, und ein Bildschirmfoto steht als JPEG da, wo das JPEG
   kleiner ist als das, was Chromium verlustfrei ablegte (`_printable`,
   `_flate_size`); Bilder mit Durchsicht bleiben. Die Website behält ihre
   Dateien. Ein Druck gilt erst als gelungen, wenn das PDF so viele
   Rasterbilder trägt wie die Seite Bildschirmfotos (`_raster_images`);
   sonst zweiter Anlauf, dann Fehler mit Sprache und Handlungsvorschlag.
4. **Seitenverweise.** Probeverweis `[Die vier Wege](manual:ways)` im
   Wegwerfbaum (nicht eingecheckt): Website `<a href="#ways">`, Anker da; im
   PDF führen drei Verweise auf das Ziel `ways` (Verzeichnis Seite 2, der
   zweizeilige Probeverweis Seite 3), Ziel ist Seite 23, wo *Die vier Wege*
   beginnt (`verweis-probe.log`).

## Entscheidung „Nachschlagen“

Die erzeugten Kapitel (Referenz der Operationen) stehen **mit Wörterbuch und
Wissensseiten unter „Nachschlagen“**, ohne eigenen Zwischentitel. Gründe:
`Page.part` sagt es bereits (alle erzeugten Seiten sind `reference`), das
Handbuchfenster gruppiert danach, und Website und PDF sollen dasselbe zeigen
wie das Fenster; Konzept §4 zählt „alle Operationen“ zu *Nachschlagen*; der
alte Zwischentitel „Referenz — jede Operation mit ihren Werten“ stand auch
über den fünf Wissensseiten und beschrieb sie falsch
(`findbarkeit.md`, Teil 3). Wer nachschlägt, findet die Referenzkapitel im
Druck weiter je auf einem eigenen Blatt.

## JPEG-Qualität 92, begründet

- Chromium reicht ein JPEG unverändert durch (Bildstrom im PDF = Datei, Byte
  für Byte), PNG und WebP legt es als Flate-gepackte RGB-Pixel ab. Die
  Nachrechnung (zlib 6 über die RGB-Zeilen) trifft die Ströme im gedruckten
  PDF auf 0,1 bis 3,5 %, stets knapp darunter — ein Grenzfall bleibt also
  verlustfrei.
- Für die 9 PNG-Bildschirmfotos ist JPEG größer als verlustfrei (1,07 MB
  gegen 1,83 MB bei q90, 2,84 MB bei q92), für die 33 Schrittbilder kleiner
  (7,2 MB gegen 2,8/3,6 MB). Deshalb entscheidet je Bild die Größe.
- Qt schreibt bis Qualität 90 mit halb aufgelöster Farbe (4:2:0), ab 91 mit
  voller (4:4:4). Siebenfach vergrößert verschwimmen bei 85 und 90 die
  orangen Rahmen, Pfeile und Nummern, bei 85 kommt Rauschen um die Schrift;
  ab 91 kein Unterschied zum verlustfreien Bild. 92 lässt Abstand zur
  Schwelle, 95 wiegt ein Fünftel mehr ohne sichtbaren Gewinn.
  Vergleichsbilder: `qualitaet-bohrung-4-feld.png`, `qualitaet-bohrung-4-nah.png`.

## Messung vorher/nachher

Probelauf der Handbuch-Sitzung (`handbuch-probe-2026-09-27`, 6 × 33
Schrittbilder) in Wegwerfbäumen; vorher `8fa13081f`, nachher `febba2f4d`;
`tools/make_manual.py` gepinnt, Exit 0 in beiden. Rohdaten
`messung-vorher.json`, `messung-nachher.json`.

| Sprache | PDF vorher | PDF nachher | Blätter | Rasterbilder v/n | davon JPEG | Bildbytes v/n | Lesezeichen |
|---|---:|---:|---:|---:|---:|---:|---:|
| de | 21,88 MB | 18,14 MB | 223 / 223 | 42 / 42 | 33 | 8,53 / 4,78 MB | 0 → 4 Teile, 55 Kapitel |
| en | 20,89 MB | 17,40 MB | 212 / 212 | 42 / 42 | 33 | 8,14 / 4,63 MB | 0 → 4 / 55 |
| es | 22,22 MB | 18,47 MB | 241 / 240 | 42 / 42 | 33 | 8,52 / 4,76 MB | 0 → 4 / 55 |
| fr | 22,69 MB | 18,88 MB | 238 / 237 | 42 / 42 | 33 | 8,62 / 4,80 MB | 0 → 4 / 55 |
| it | 22,08 MB | 18,35 MB | 242 / 242 | 42 / 42 | 33 | 8,51 / 4,77 MB | 0 → 4 / 55 |
| pt | 22,10 MB | 18,33 MB | 233 / 233 | 42 / 42 | 33 | 8,55 / 4,77 MB | 0 → 4 / 55 |

Alle Bildströme der Datei (mit Masken und Musterbildern): 52 vorher und
nachher, Englisch 56 und 56. Jedes PDF wird rund 17 % leichter. Der Rest
(rund 13 MB) ist Vektorinhalt der Seiten und Zeichnungen (1 448
Inhaltsströme, 12,8 MB im deutschen PDF), Schriften nur 0,09 MB.

## Sichtprüfung

- Am gerenderten PDF (QtPdf/PDFium): Schrittbild *Ein Loch bohren* 4 bei
  400 dpi und *Das Fenster auf einen Blick* bei 500 dpi, vorher
  (verlustfrei) und nachher (JPEG) nebeneinander — nicht zu unterscheiden,
  Schrift und orange Rahmen scharf (`schaerfe-final-bohrung-4.png`,
  `schaerfe-final-fenster.png`).
- Verzeichnis des PDF de und fr: vier Teile als Kennzeilen, ein Blatt
  (`bilder-nachher/…-s2-80dpi.png`); Teilanfänge *Funktionen*, *Hilfe bei
  Problemen*, *Nachschlagen* oben auf neuem Blatt, Kapitel direkt darunter
  (`bilder-probe2/teile-25-61-64.png`); Deckblatt unverändert.
- Website (Chrome headless, hell und dunkel): Verzeichnis mit Teilen, im
  Text Kennzeile mit Linie über dem ersten Kapitel
  (`web/toc-hell.png`, `web/toc-hell-ausschnitt.png`).
- Lesezeichen in de, fr, pt: vier Teile mit übersetzten Titeln, 8/24/2/21
  Kapitel darunter, Seiten richtig.
- Beispiel-PDFs zum Ansehen: `pdf/` (de vorher, de nachher, fr nachher, de
  nachher mit Probeverweis).

## Tor

- Stufe 1 (Gliederung): gepinnt, `Sammelgruppe: 1 failed, 17918 passed, 59
  skipped`, `Läufe mit Fehler: 1` — rot war
  `test_public_php_security.py::test_rate_limit_states_use_keyed_rotating_identifiers_and_purge_old_data`
  (Ursache unten, nicht mein Diff). Die Datei danach mit abgeschirmtem PHP:
  144 passed. mypy: 330 Dateien ohne Befund; ruff check und format grün.
- Stufe 2 (Lesezeichen), PHP abgeschirmt: `17920 passed, 59 skipped`,
  `Läufe mit Fehler: 0`, Exit 0; mypy 330 ohne Befund; ruff grün.
- Stufe 3 (JPEG), PHP abgeschirmt: `17922 passed, 59 skipped`,
  `Läufe mit Fehler: 0`, Exit 0; mypy 330 ohne Befund; ruff grün.
- Konzeptzeile: nur Markdown; die Tests, die `konzepte/` lesen
  (`test_directory_docs`, `test_manual_search`, `test_shared_hosting_removed`,
  `test_check_message`, `test_manual`): 130 passed, 3 skipped.
- Im Wegwerfbaum am letzten Code-Commit: `-m "rendered and not windowed"`
  von `test_manual` und `test_guides`: 78 passed (am Ausgangsstand mit
  denselben Probebildern ebenfalls 78 passed).
- Gegenprobe der neuen Tests: acht Mutationen am Erzeuger (Teilüberschrift
  fehlt, Verzeichnis ohne Teile, Teil springt an Kapitelstelle, Kapitel nicht
  unter ihrem Teil, Formularobjekte nicht durchsucht, jedes Bild JPEG,
  Durchsicht übersehen, Verweise um Bildschirmfotos bleiben) — alle rot,
  Datei danach bytegleich zurück.

## PHP-Befund (nicht mein Strang, aber im Weg)

Nach dem ersten Tor setzte der PHP-Prüfserver bei `support.php` in diesem
Arbeitsbaum jedes Mal die Verbindung zurück (PHP endet mit 0xC0000409), in
jedem anderen Baum am selben Stand nicht — auch nicht mit meinem Diff in
einem zweiten Baum und nicht mit einer Kopie der Datei an anderem Pfad. Mit
`opcache.enable=0` verschwindet es. Auf Windows teilen sich alle PHP-Prozesse
eines Nutzers den OPcache-Speicher; ein kaputter Eintrag, der am Pfad dieser
Datei hängt, bleibt, solange irgendein PHP-Prozess den Speicher hält (seit
22:37 läuft verwaist ein PHP-Server einer anderen Sitzung, Port 39417, `-t .`
im Scratchpad-Ordner `opc` jener Sitzung; nicht von mir, nicht angefasst).
Meine Tore liefen deshalb mit `PHP_INI_SCAN_DIR` auf
`output\review\handbuch-pdf-2026-09-27\php-ini\` (`opcache.enable=0`, nur
für meine Läufe). **Vorschlag:** Der Prüfserver in
`tests/test_public_php_security.py` sollte mit `-d opcache.enable=0` starten;
sonst vergiftet ein Absturz unter Last alle späteren Läufe desselben Pfads,
bis alle PHP-Prozesse weg sind.

## Offen oder zweifelhaft

- **Beim Zusammenführen:** Der Teil *Anleitungen* ist in diesem Zweig leer
  und erscheint deshalb nicht; mit den Anleitungen aus Strang A kommt er von
  selbst (Verzeichnis, Teilüberschrift, Lesezeichen, eigenes Blatt im
  Druck). Wächst das Verzeichnis dann über ein Blatt, bekommt dessen zweite
  Seite wie vor diesem Umbau Kopf- und Fußzeile mit leerem Kapitelnamen
  (`SKIP_STAMP = 2`) — Schönheitsfrage, nicht geändert.
- In den Katalogen fällt eine Zeile weg (zwischen „Rechtwinklig“ und
  „Referenzmaß“); ändert Strang B dort Nachbarzeilen, ist der Konflikt
  trivial.
- Die Lede- und Beschreibungstexte „… von den ersten fünfzehn Minuten …“ in
  `make_manual.py` zieht Strang A nach (Hinweis der Handbuch-Sitzung).
- Das PDF bleibt mit rund 18 MB groß; der Rest ist Vektorinhalt, vor allem
  die gerenderten Bausteinzeichnungen der Referenz. Nicht Teil dieses
  Auftrags.
- In meinem Scratchpad-Pfad hängt ein fremder Worktree `…\scratchpad\basis`
  (Stand `8fa13081f`), den ich nicht angelegt habe; nicht entfernt.
- Entfernt habe ich nur meine eigenen Wegwerfbäume
  (`handbuch-wurf`, `handbuch-wurf-vorher`, `handbuch-wurf-probe`,
  `handbuch-pdq`) und zwei Sondenordner (`sonde-pdf`, `sonde-pdq`).
