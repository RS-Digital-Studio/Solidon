# Meldung: Handbuch fertig (RM-283, 0.5.1)

Von der Handbuch-Sitzung an die Release-Sitzung „Release 0.5.1“,
28.09.2026 früh. Zur Übernahme, keine Freigabe von irgendetwas. Robert:
„alle punkte davon sollen noch in 0.5.1“; der Tag v0.5.1 wartet auf diese
Meldung.

## Zu mergen

- **Endcommit `8d83c1c32fe1bb5998246934b550ccc740c451e9`** auf
  `handbuch-umbau` (Arbeitsbaum `F:\3D Druck.handbuch`, liegt auf origin).
  `main` ist bis `f1cfff619` hineingemergt und Vorfahr des Zweigs;
  `git merge-tree --write-tree origin/main handbuch-umbau` ergibt den Baum
  des Zweigs (`0e3e2d86f`), der Merge ist also konfliktfrei, solange `main`
  nicht weiterläuft. Läuft es weiter und stoßen sich die Kataloge, dann
  schlüsselweise zusammenführen (Basis, HEAD, MERGE_HEAD je Schlüssel).
- **Tor** auf `73666bb80`: Sammelgruppe 18 166 passed, 59 skipped, Läufe mit
  Fehler 0, Exit 0; ruff, format und mypy sauber. Danach nur noch
  `8d83c1c32` (ein Erzeugnistest liest die Seite entschlüsselt):
  `test_manual` ohne Erzeugnisse 99 passed, ruff und format sauber.
- **Kataloge:** Der Einsammler findet keinen fehlenden und keinen verwaisten
  Text; nach jedem Merge von `main` schlüsselweise gegen die drei Stände
  geprüft.

## Was der Merge bringt (seit Teil 1, `6a952cf81`)

- **HB-5** „Wo fange ich an?“ als erste Seite; das Handbuchfenster zeigt die
  Teile als Überschriften; Startbildschirm und Hilfe-Menü führen dorthin.
- **HB-7** F1 im Operationsdialog schlägt die Anleitung auf, die die
  Operation lehrt (`Guide.teaches`), sonst ihren Referenzeintrag.
- **HB-8** zehn weitere Anleitungen, fünfzehn insgesamt; jede Erklärseite
  endet mit „Schritt für Schritt:“ und den Anleitungen zu ihrem Thema.
- **HB-9** (Strang B) Erklärseiten ein Drittel kürzer und neu übersetzt,
  Italienisch durchgehend „tu“; **HB-11** der Wächter für Wege im Text.
- **HB-10** (Strang C) Website und PDF nach Teilen gegliedert, Referenz am
  Ende, PDF mit Lesezeichen, Schrittbilder als JPEG; Kopf- und Fußzeile
  beginnen beim ersten Kapitel, wie lang das Verzeichnis auch wird.
- **HB-12** `tools/make_guide_video.py`: je Sprache zwei Filme mit
  Kapitelmarken.
- Französisch setzt im Handbuch vor „:“ ein Leerzeichen, auch in der
  Referenz und in der Zeile „Wann nicht“, die Dialog, Menü-Tooltip und
  Auswahlfenster zeigen (`afc251ae4`).
- Nachzug zu texte-051 und dem Oberflächenpaket (`8b65092bd`,
  `ce36836dc`): Namen, Nummerierung ab drei Stücken, Grenzsatz, gerader
  Apostroph in fr und it, `Échap`, „passaggio“, Eingabetaste.
- Website: Beschreibung und Vorspann der Handbuchseite, Hinweis nach der
  Installation und Funktionsseite sprechen von „Wo fange ich an?“ (sechs
  Sprachen).

## Changelog 0.5.1

Gruppe *Handbuch und Website*: sieben Punkte statt vier, der Abschnitt hat
also drei mehr. Die Presseentwürfe ziehst du beim Merge nach
(`test_the_press_drafts_count_the_same_changes`). Eine PDF-Größe verspricht
kein Punkt: Mit zehn Anleitungen mehr wird das PDF schwerer als in 0.5.0.

## Beim Release (`/erzeugen`)

1. Nach dem Versionssprung `make_guides.py` in allen Sprachen. Gemessen
   hier: Deutsch rund 15 Minuten, die fünf übrigen zusammen rund 35.
2. Danach `make_manual.py`, dann `make_seo.py` (`llms.txt` nimmt die neuen
   Beschreibungen).
3. `make_guide_video.py` für die Filme (`marketing/video/guides/`, Upload
   von Hand).
4. Die Erzeugnistests von `test_manual` und `test_guides` gehören ins
   Release-Tor.

## Probe auf dem Endstand

- `make_guides.py` auf `ce36836dc`: fünfzehn Anleitungen in sechs Sprachen,
  je 85 Bilder, Exit 0. Die Commits danach ändern keinen Anleitungssatz und
  kein Ziel. Bilder unter
  `F:\3D Druck\output\review\handbuch-hb8-hb12-2026-09-28\nach-main-f74c\<sprache>`;
  die deutschen vollständig angesehen (Bögen unter `…\nach-main-f74c\boegen`),
  je Sprache sechs Bilder mit übersetzten Namen, Menüs und Befunden als
  Stichprobe (`…\nach-main-f74c\stichprobe`).
- `make_manual.py` im Wegwerfbaum auf `73666bb80` mit diesen Bildern: sechs
  Sprachen, Exit 0. PDFs 233 bis 264 Seiten, 22,9 bis 24,5 MB, je 94
  Bilder. Das Verzeichnis hat zwei Seiten, das erste Kapitel beginnt auf
  Seite 4; die Seiten 1 bis 3 tragen keine Kopf- und Fußzeile, ab Seite 4
  jede. Lesezeichen: 5 Teile, 65 Kapitel.
- Erzeugnistests von `test_manual` und `test_guides` dort: 78 passed, einer
  davon erst nach `8d83c1c32`.

## Bekannt, nach 0.5.1 (Register RM-283)

- Die Feldabnahme aus §11 des Konzepts.
- Die Nummer eines Schritts liegt in *Ein Gehäuse mit Deckel* 3 und *Ein
  Teil beschriften* 3 auf Text im Auswahlfenster, in fr *Ein Teil
  beschriften* 3 über dem Drehfeld von „Position Y“.
- `print_settings_dialog.py:6767` setzt „Gilt für“ mit festem Doppelpunkt
  zusammen; das gehört zu deinem Registerpunkt der festen Doppelpunkte.

## Nachtrag nach dem Code-Review (28.09.2026)

Neuer Endcommit `559412ac4faea9377206752ff42d2fec6f19e6fe`, main bis
`eee5140ac` hereingemergt und Vorfahr des Zweigs, konfliktfrei. B1 (F1 bei
53 Operationen auf der Erklärseite), B3 (F1 setzt eine offene Anleitung auf
den Anfang) und B4 (vier Zuordnungen in `teaches`) sind behoben, mit
Gegenprobe am Stand davor. Tor: 18 262 passed, 59 skipped, Läufe mit Fehler
0; ruff, format sauber; mypy win32, linux und darwin ohne Befund.
