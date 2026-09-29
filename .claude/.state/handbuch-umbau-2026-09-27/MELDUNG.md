# Meldung: Handbuchumbau für 0.5.1 (RM-283)

Von der Sitzung „Tutorial-Anfrage mit Antwortemail“ [ed0284] an die
Release-Sitzung, 27.09.2026 abends. Zur Kenntnis und Übernahme, keine
Freigabe von irgendetwas.

Robert, 27.09.2026: „handbuch kommt noch vor 0.5.1 … also mit 0.5.1 wird es
hochgeladen“. Der Zweig kommt also vor dem Tag v0.5.1 nach `main`.

## Zu mergen

- **Endcommit `db9c350f6c1f73ce0b02c5004eb986b5054f2f4d`** auf dem Zweig `handbuch-umbau` (Arbeitsbaum
  `F:\3D Druck.handbuch`, liegt auf origin). `main` ist bis `ab25add59`
  hineingemergt; `git merge-tree --write-tree ab25add59 db9c350f6c1f73ce0b02c5004eb986b5054f2f4d` ergibt den Baum
  des Zweigs, also keine Konflikte.
- **Tor auf diesem Stand grün:** `suite-getrennt.sh` 17 903 bestanden,
  59 übersprungen, 0 Läufe mit Fehler; ruff, format, mypy sauber. Danach kam
  nur noch Prosa in `ROADMAP.md` und im Konzept dazu; die Tests, die sie
  lesen, sind danach grün (1 249 bestanden, 12 übersprungen), am Konzept hängt keiner.
- **Handbuch einmal voll erzeugt:** `make_manual.py` auf dem Endcommit in
  einem Wegwerfbaum, mit den englischen Schrittbildern in allen sechs
  Sprachen. Seiten und PDFs aller Sprachen entstehen ohne Fehler, jede Seite
  trägt die 33 Schrittbilder, das PDF 42 Bilder statt 9; die Prüfungen
  `rendered` von `test_manual` und `test_guides` sind darauf grün (78).
- **16 Commits, 46 Dateien** gegenüber `ab25add59`. Keine davon
  trägt im Hauptbaum ungesicherte Arbeit (`comm -12` gegen `git status`), die
  vier Doctor-Docstrings berührt der Zweig nicht. `git merge --no-ff
  --no-commit handbuch-umbau` im Hauptbaum sollte also ohne Umweg gehen.
- Kataloge: Der Zweig ergänzt Schlüssel in allen fünf Katalogen
  (Anleitungssätze, Suchwörter, Texte des Auswahlfensters). Der Einsammler
  findet auf dem Zweig keinen fehlenden und keinen verwaisten Text.

## Was der Merge bringt

- Fünf Bildanleitungen, aufgenommen am echten Fenster mit Nummern, Pfeilen und
  Ringen: *Das Fenster auf einen Blick*, *Ein Modell prüfen und drucken*,
  *Ein Loch bohren*, *Das erste eigene Teil*, *Ein Gehäuse mit Deckel*
  (`app/core/guides.py`, `app/ui/guide_targets.py`, `tools/make_guides.py`).
  Auf Deutsch und Englisch komplett aufgenommen und angesehen.
- Das Handbuch in fünf Teilen (`manual.OUTLINE`), Suche mit Rangfolge und
  Fundstelle auf den Kundenwörtern der Befehlspalette
  (`app/core/manual_search.py`), je Operation ihr Ort in der Referenz,
  keine toten `file:`-Verweise im PDF.
- Auswahlfenster: Die Handlungen für alle Körper (*Druckoptimal ausrichten*,
  *Auf dem Bett anordnen*, *Überschneidungen prüfen*) stehen, wenn nichts
  gewählt ist, und nicht mehr am gewählten Körper (Robert, 27.09.2026;
  `.claude/rules/grenzen.md`).
- `/erzeugen` mit dem Schritt „Bildanleitungen“, Codex-Spiegel nachgezogen.

## Changelog — schon im Zweig

Sechs Sprachen, fünf Punkte, je Sprache danach 118:

- neue Gruppe „Handbuch und Website“ am Ende des Abschnitts 0.5.1
  (vier Punkte: Anleitungen in Bildern, Übersichtsbild, Suche, Ort je
  Operation);
- unter „Bedienung und System“, hinter „Zuletzt geöffnete Projekte …“, der
  Punkt zum Auswahlfenster ohne Auswahl.

Jeder Punkt gegen v0.5.0 geprüft: Anleitungen, Suche mit Rangfolge, Ort je
Operation und das Auswahlfenster ohne Auswahl sind alle erst nach dem Tag
entstanden. Namen aus den Katalogen, Schreibweise je Sprache wie im Rest der
Datei (kursiv, «…», « … »). `test_changelog` und `test_changelog_website`
mit `APP_VERSION = "0.5.1"` gefahren: 74 bestanden, 1 übersprungen; jeder
Punkt unter 200 Zeichen, kein Wort der Testfamilie.

## Für den Release

1. **Neuer Erzeugerschritt vor `make_manual.py`:** einmal
   `tools/make_guides.py --schirm 1` (ohne Sprache: alle sechs, je Sprache
   ein Kindprozess), nach dem Versionssprung. Er öffnet echte Fenster, braucht
   rund drei Minuten je Sprache und wartet, solange ein anderes Fenster über
   der Aufnahme liegt. Er schreibt `app/images/manual/<sprache>/guide-*.webp`
   und je Sprache den Stempel `guides.json` — neue Dateien, die mit dem
   Release eingecheckt werden. Endet er mit Exit 1, nennt er Anleitung und
   Schritt: dann bitte der Handbuch-Sitzung oder Robert Bescheid geben, den
   Schritt nicht auslassen. Die Liste in „JETZT“ Punkt 4 wird damit:
   `make_examples` (falls nötig), `make_figures`, `make_web_images`,
   **`make_guides`**, `make_manual`.
2. Die ungesicherten Handbuchdateien im Hauptbaum (PDFs, `app/images/manual`,
   `website/handbuch*`, `website/*/manual.html`) zeigen nach dem Merge
   zusätzlich das alte Handbuch ohne Anleitungen; sie entstehen ohnehin neu.
3. `tests/test_guides.py` steht bei den Wächtern vor dem Tag. Sein
   Stempeltest (`rendered`) verlangt in jeder Sprache `guides.json` mit
   Version 0.5.1 und dem heutigen Abdruck der Anleitungen.
4. **Die PDFs werden schwerer, und das ist erwartet:** deutsch 21,5 statt
   13,9 MB. Chromium bettet jedes Rasterbild verlustfrei ein, ein Schrittbild
   mit rund 210 kB, so viel wie ein bisheriges Bildschirmfoto. Leichter
   machen steht unter HB-10 im Konzept, nicht vor diesem Release.

## Registertext

RM-283 ist im Zweig fortgeschrieben (Zeile im Register und Abschnitt); mit
dem Merge steht er auf `main`. Offen bleiben HB-5 (Gruppen im
Handbuchfenster, „Wo fange ich an?“ — Robert entscheidet, ob noch in
0.5.1), HB-7, der Rest von HB-8 und HB-9 bis HB-12. Kommt davon etwas vor
dem Tag, folgt eine neue Meldung mit neuem Endcommit.

## Vorschlag für die Merge-Meldung

```text
Das Handbuch geht mit 0.5.1 in Bildern aus der Anwendung hinaus

Merge des Zweigs handbuch-umbau (RM-283). Robert, 27.09.2026: „handbuch
kommt noch vor 0.5.1 … also mit 0.5.1 wird es hochgeladen“. Der Zweig
enthält main bis ab25add59; an main ändert der Merge nur, was er mitbringt.

Das Handbuch hat fünf Bildanleitungen, aufgenommen am echten Fenster mit
Nummern, Pfeilen und Ringen: das Fenster auf einen Blick, ein Modell prüfen
und drucken, ein Loch bohren, das erste eigene Teil und ein Gehäuse mit
Deckel. Die Suche ordnet nach Rang, versteht die Kundenwörter der
Befehlspalette und schlägt die Seite an der Fundstelle auf. Die Referenz
nennt je Operation ihren Ort in Menü oder Auswahlfenster. Die Handlungen für
alle Körper stehen im Auswahlfenster, wenn nichts gewählt ist (Robert).
Die Punkte dazu im Changelog 0.5.1 kommen mit dem Zweig, in allen sechs
Sprachen.

Für den Release: /erzeugen nimmt die Bildanleitungen auf, mit
tools/make_guides.py in allen Sprachen nach dem Versionssprung und vor
make_manual.py. Handbuchbilder, PDFs und Website-Seiten, die vor diesem
Merge erzeugt wurden, zeigen das alte Handbuch und entstehen danach neu.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```
