# Konzept — Ein Handbuch, das man ohne Ausprobieren versteht

> **Stand:** 29.09.2026. In `main` zusammengeführt und mit 0.5.1 veröffentlicht;
> Weiterarbeit im Hauptbaum, Registerpunkt [RM-283](../ROADMAP.md#rm-283).
> **Anlass:** Ein Interessent (Elektronikbetrieb) schrieb am 27.09.2026, es sei
> schwierig, alles aus dem Handbuch zu lernen, und Ausprobieren führe nicht
> zum Ziel. Er fragte nach einem Video-Tutorial. Die Antwort sagt ein Tutorial
> zu, sobald die meisten Änderungen an der Bedienung abgeschlossen sind.
> **Auftrag Robert, wörtlich, 27.09.2026:**
>
> 1. „anscheinend ist das Handbuch zu umständlich/unübersichtlich nicht
>    verständlich, suche optimierungen arbeite ein konzept aus und leg los"
> 2. „so, dass wir jederzeit mit einer anderen session weiter machen können"
> 3. „daran denken dass alles auch immer aktuell gehalten werden sollte wenn
>    sich etwas ändert wenn wir eine neue version erstellen zwischendrin
>    brauchen wir es nicht"
> 4. „am besten auch an bildern live von der oberfläche erklären als durch
>    wörter mit kommentaren/pfeilen usw"

## §0 Weitermachen

Wer diese Arbeit übernimmt, liest zuerst diesen Abschnitt und die
Statustabelle in §9. Mehr braucht es nicht; die Nachweise liegen unter
`konzepte/nachweise-handbuch-2026-09/`.

- **Ort:** Weiterarbeit in `F:\3D Druck` auf `main`. Der Handbuchumbau bis
  `559412ac4` ist im Tag `v0.5.1` enthalten. Die früheren Handbuchzweige und
  Arbeitsbäume sind entfernt; sie werden zum Fortsetzen nicht neu angelegt.
- **Releaseanschluss:** Der Aufnahmeschritt in `/erzeugen` ist enthalten:
  Beim Release entstehen die Anleitungsbilder vor dem Handbuch. Für die
  nächste Arbeit gelten die offenen Kriterien von RM-283, kein Warten auf
  den bereits veröffentlichten Tag 0.5.1.
- **Tests im Hauptbaum:** `cd "F:\3D Druck"` und dann
  `& "F:\3D Druck\.venv\Scripts\python.exe" -m pytest …`. Mit `-m` steht das
  Arbeitsverzeichnis vorn im Suchpfad. Ein Skript außerhalb von pytest setzt
  selbst `sys.path.insert(0, r"F:\3D Druck")`, damit es denselben Stand lädt.
- **Bilder während der Entwicklung:** Das Aufnahmewerkzeug schreibt mit
  `--ziel <ordner>` in einen Ordner außerhalb des Baums. In
  `app/images/manual/` schreibt es nur beim Release (§6).
- **Commit:** je abgeschlossenem Paket, mit Push von `main` (der
  `post-commit`-Hook pusht den aktuellen Zweig).
- **Probelauf einer Anleitung**, eine Sprache, in einen fremden Ordner, auf
  dem zweiten Monitor:
  `& "F:\3D Druck\.venv\Scripts\python.exe" tools/make_guides.py de --nur <anleitung> --ziel <ordner> --schirm 1`.
  Das Werkzeug öffnet ein echtes Fenster; die Bilder danach ansehen, erst
  dann gilt ein Schritt als gebaut.

### Stand und nächster Schritt

Diese Liste wird nach jedem Schritt fortgeschrieben, damit eine Sitzung, die
am Nutzungslimit endet, keine Arbeit mitnimmt (Robert, 27.09.2026).

**Releaseabschluss:** Der Stand bis `559412ac4` liegt auf `main` und in
`v0.5.1`; die folgenden Einträge dokumentieren die Entwicklung davor.
Für die Weiterarbeit gelten der Arbeitsort oben und die offenen Kriterien
in [RM-283](../ROADMAP.md#rm-283).

- **Committet und gepusht:** HB-0 (`daadc88fe`), HB-1 (`54e83a72e`), HB-2
  und HB-3 (`0f28f4368`), die toten PDF-Verweise aus HB-10 (`6af8fb5c7`),
  HB-13 — der Ort je Operation in der Referenz, `**Ort:** <menu_path>` an
  allen 142 Einträgen (Commit „Die Referenz sagt jetzt bei jeder Operation,
  wo man sie findet").
- **HB-4 fertig, vier Anleitungen** am Fenster auf Deutsch aufgenommen und
  angesehen: *Das Fenster auf einen Blick*, *Ein Modell prüfen und drucken*
  (`d36503d57`, an `tests/data/meshes/broken_open.stl`), *Ein Loch bohren*
  (`3d2af85fd`, an `plate_holes.stl`) und *Das erste eigene Teil* (neun
  Schritte: neues Projekt, Quader über das aufgeklappte Menü, Maße, Oberseite
  wählen, *Bausteine*, Doppelklick auf *Schraubenloch mit Senkung*, M4,
  fertige Platte mit Ring um die Senkung). Alle Sätze in sechs Sprachen.
- **HB-6, Suche mit Rangfolge, gebaut** (`6bf35e5cb`, §7):
  `app/core/manual_search.py` auf Faltung, Trefferstärke und Kundenwörtern
  der Befehlspalette; das Fenster zeigt die Treffer in Rangfolge und schlägt
  jede Seite an ihrer Fundstelle auf.
- **HB-8, erste Anleitung gebaut:** *Ein Gehäuse mit Deckel* (zehn
  Schritte: Quader, *Aushöhlen* mit *Oben öffnen*, *Deckel erzeugen* aus dem
  Menü, Klick ins Leere, *Druckoptimal ausrichten* im Auswahlfenster und im
  Dialog, Dose und Deckel druckfertig nebeneinander). Dafür stehen die
  Handlungen für alle Körper jetzt im Auswahlfenster, wenn nichts gewählt
  ist, und nicht mehr am gewählten Körper (Robert, 27.09.2026;
  `.claude/rules/grenzen.md`, „Die Karte der Handlungen").
- **`main` hereingeholt** (Stand 27.09.2026, 50 Commits) und der
  Aufnahmeschritt in `/erzeugen` eingetragen: `make_guides.py` bei jedem
  Release in allen Sprachen, nach dem Versionssprung, vor `make_manual.py`.
  Das Tor heißt jetzt `bash .claude/scripts/suite-getrennt.sh`.
- **Zweite Sprache belegt:** Alle fünf Anleitungen sind auf Englisch am
  Fenster aufgenommen und angesehen, ohne eine Änderung an den Geschichten.
  Jeder hervorgehobene Name im Satz (Knopf, Feld, Baustein, Titel) ist in
  jeder Sprache gegen den Katalog geprüft
  (`test_a_name_in_a_step_is_the_one_the_interface_shows`).
- **Teil 1 ist auf `main`:** Die Release-Sitzung hat den gemeldeten Stand
  `db9c350f6` gemergt (`6a952cf81`), samt den Punkten im Changelog 0.5.1
  (Gruppe *Handbuch und Website*, dazu unter *Bedienung und System* das
  Auswahlfenster ohne Auswahl). Die Meldung liegt im Hauptbaum unter
  `.claude/.state/handbuch-umbau-2026-09-27/MELDUNG.md`; jede weitere kommt
  dorthin. Beim Release läuft `make_guides.py` in allen Sprachen vor
  `make_manual.py`.
- **Alles Offene kommt in 0.5.1** (Robert, 27.09.2026 abends: „alle punkte
  davon sollen noch in 0.5.1“): HB-5, HB-7, der Rest von HB-8, HB-9, der
  Rest von HB-10, HB-11 und HB-12. **Der Tag v0.5.1 wartet auf die Meldung
  „Handbuch fertig“** an die Release-Sitzung; so steht es auch in ihrer
  Übergabe (`F:\3D Druck\.claude\.state\release-0.5.1\UEBERGABE.md`, „JETZT“).
- **Grundlage dafür gebaut:** Verweise zwischen Seiten,
  `[Text](manual:schlüssel)` (`markup.MANUAL_LINK`). Das Fenster schlägt die
  Seite auf, Website und PDF springen zum Anker, Text und Suche behalten nur
  den Text; `test_manual` prüft, dass jeder Verweis in jeder Sprache auf eine
  Seite führt und keine Übersetzung einen verliert.
- **Stränge B und C laufen** (27.09.2026 abends): Arbeitsbäume
  `F:\3D Druck.handbuch-texte` (`handbuch-texte`) und `F:\3D Druck.handbuch-pdf`
  (`handbuch-pdf`), beide vom Stand `8fa13081f`, die Agenten mit den Aufträgen
  aus §12.2 und §12.3. Ihre Berichte kommen nach
  `F:\3D Druck\.claude\.state\handbuch-umbau-2026-09-27\strang-b-bericht.md` und
  `strang-c-bericht.md`. Die Probebilder für Strang C (alle Anleitungen, sechs
  Sprachen) liegen unter `F:\3D Druck\output\review\handbuch-probe-2026-09-27\`.
  Die Release-Sitzung heißt „Release 0.5.1“ und prüft jede Lieferung, auch B
  und C vor dem Merge.
- **Aufnahme auf einem belegten Schirm:** `make_guides.py` legt sein Fenster
  für die Dauer des Laufs in die oberste Ebene. Liegt auf dem Aufnahmeschirm
  ein Fenster des Nutzers, brach der Lauf sonst nach 300 s ab.
- **HB-5 und HB-7 gebaut:** „Wo fange ich an?“ ersetzt *Die ersten fünfzehn
  Minuten* (Schlüssel bleibt `start`, Konstante `manual.WHERE_TO_START`); die
  Listen der Anleitungen entstehen aus `guides.GUIDES`, und die vier
  Bildschirmfotos der alten Seite stehen jetzt dort (`main-window` ist auch
  das Vorschaubild der Website). Das Handbuchfenster
  zeigt die Teile als Überschriften, die Suche nicht. F1 im Hauptfenster öffnet
  „Wo fange ich an?“, im Operationsdialog die Anleitung (`Guide.teaches`) oder
  den Eintrag in der Referenz (`manual.help_for`). Dazu die drei Befunde der
  Release-Sitzung zu Teil 1: Legende der Werkzeugleiste mit allen sieben
  Knöpfen, *Ein Loch bohren* zeigt das Verschieben als Schritt 8, Verweise in
  Schrittsätzen sind echte Seitenverweise, Alt-Texte ohne Auszeichnung.
- **HB-8 fertig, fünfzehn Anleitungen:** dazu *Ein zu großes Teil teilen* in
  den Ersten Schritten und neun Aufgaben (verschieben und drehen, ein Maß
  ändern, einen Schritt zurücknehmen, Gewinde, Kanten, Beschriftung, zeichnen
  und hochziehen, zweifarbig, reparieren). Alle fünfzehn sind auf Deutsch mit
  dem fertigen Werkzeug aufgenommen und angesehen. Die Aufnahme legt nach dem
  Anheben ihres Fensters die eigenen Menüs wieder darüber; sonst fehlten sie
  im Bild. Jede Erklärseite endet mit „Schritt für Schritt:“ und den
  Anleitungen zu ihrem Thema, erzeugt aus `Guide.topics` (etwa `trouble` →
  *Ein Modell reparieren*); die Seitentexte selbst bleiben unberührt.
- **HB-12 fertig:** `tools/make_guide_video.py` schneidet aus denselben Bildern
  und Sätzen je Sprache zwei Filme, *Vom Start bis zum Druck* und *Einzelne
  Aufgaben*, mit Kapitelmarken. Er läuft beim Release nach `make_guides.py`
  (`/erzeugen`); die Filme liegen unter `marketing/` und werden von Hand
  hochgeladen.
- **B und C zusammengeführt,** beide nach der Durchsicht der
  Release-Sitzung (`F:\3D Druck\.claude\.state\release-0.5.1\reports\strang-b-uebersetzung.md`
  mit 42 Befunden, vor dem Merge behoben), die Kataloge schlüsselweise. Ohne
  Kopf- und Fußzeile bleibt im PDF jede Seite vor dem ersten Kapitelziel,
  nicht eine feste Zahl von Seiten: Das Verzeichnis wächst mit den
  Anleitungen und je Sprache. Beschreibung und Vorspann der Handbuchseite,
  Start- und Funktionsseiten der Website und der Changelog 0.5.1 sprechen
  vom neuen Anfang und den fünfzehn Anleitungen.
- **`main` mit texte-051 und dem Oberflächenpaket hereingeholt** und das
  Handbuch nachgezogen: Werkzeug *Trennen* und Operation *Teilen* heißen je
  Sprache wie im Fenster, *Senkung, Stufen und Verengung mitnehmen*, der
  Grenzsatz zum Parameterfeld, fr `Échap` und gerader Apostroph in fr und it,
  it „passaggio“ für den Schritt im Verlauf, die Nummerierung ab drei
  Stücken. Französisch setzt im Handbuch vor „:“ ein Leerzeichen, auch wo der
  Code einen Satz zusammensetzt (Regel in `.claude/rules/uebersetzung.md`).
- **Probe für 0.5.1:** alle fünfzehn Anleitungen in sechs Sprachen am
  Fenster aufgenommen (nicht eingecheckt; die Bilder entstehen beim Release),
  die deutschen angesehen; das Handbuch im Wegwerfbaum vollständig erzeugt,
  Erzeugnistests grün. Das Verzeichnis des PDF hat jetzt zwei Seiten, das
  erste Kapitel beginnt auf Seite 4.
- **Für 0.5.1 fertig,** gemeldet an die Release-Sitzung
  (`F:\3D Druck\.claude\.state\handbuch-umbau-2026-09-27\MELDUNG-fertig.md`).
  Beim Release: `make_guides.py` in allen Sprachen nach dem Versionssprung,
  dann `make_manual.py`, dann `make_guide_video.py` (`/erzeugen`).
- **Code-Review der Release-Sitzung**
  (`F:\3D Druck\.claude\.state\release-0.5.1\reports\review-handbuch.md`): B1, B3 und B4 vor
  dem Tag behoben. F1 fand bei 53 Operationen die Erklärseite statt des
  Eintrags, stellte eine offene Anleitung auf ihren Anfang und führte bei
  vier Operationen in eine Anleitung, die sie nicht zeigt. B2 (mehr als 120
  Punkte im Changelog) übernimmt die Release-Sitzung, B5 bis B7 stehen im
  Register.
- **Offen nach 0.5.1** (Register RM-283): die Feldabnahme aus §11 und die
  Nummernplatzierung, die in zwei Bildern auf Text liegt.

## §1 Befund

Gemessen am Stand `228a05572` (27.09.2026). Die ausführlichen Messungen
stehen in `nachweise-handbuch-2026-09/leserblick.md` (die geschriebenen
Seiten mit den Augen des Kunden) und `findbarkeit.md` (Suche, Einstiege,
Ausgabewege, Referenz).

### §1.1 Umfang

| | Seiten | Wörter | Anteil |
|---|---|---|---|
| Geschriebene Seiten (`manual.INTRODUCTION`, 3D-Maus-Seite) | 30 | 16 331 | 37 % |
| Erzeugte Wissensseiten (`knowledge_pages`) | 5 | 5 509 | 12 % |
| Erzeugte Referenz, eine Seite je Registerkategorie | 15 | 22 580 | 51 % |
| **Zusammen** | **50** | **44 420** | |

Gezählt sind Wörter mit mindestens einem Buchstaben oder einer Ziffer. Die
erste Zählung dieses Konzepts (53 310) zählte die Tabellenstriche der
Referenz mit; die Referenz hat 143 Tabellen mit 1 114 Zeilen, und 75 Prozent
ihrer Wörter stehen in Parametertabellen. **Zwei Drittel des Handbuchs sind
erzeugt.** Das PDF hat 197 Blätter, davon 129 Referenz. Die längsten Seiten
sind erzeugt: Bausteine 6 483 Wörter, Die Werkzeuge der Fernsteuerung 3 547,
Skizze 3 170, Merkmale 2 737, Grundformen 2 392; die längste geschriebene ist
*Was Solidon im Modell erkennt* mit 2 029.

Bilder: neun Bildschirmfotos je Sprache, dazu gezeichnete Schemata und
gerenderte Bausteine. **Kein Bild trägt eine Markierung**, kein Pfeil, keine
Nummer, kein Rahmen. 15 der 30 geschriebenen Seiten haben kein einziges
Bild, darunter *Was Solidon im Modell erkennt* (2 087 Wörter) und *Bewegen
und Färben* (841), die beide ausführlich beschreiben, was im Auswahlfenster
passiert.

### §1.2 Aufbau

- Die Seiten stehen als **flache Liste von 50 Titeln** im Handbuchfenster
  (`app/ui/manual_window.py`), ohne Gruppen. Lernseiten, Erklärungen und
  Nachschlagewerk stehen gleichrangig untereinander.
- Die Reihenfolge folgt den Bereichen des Programms, nicht den Aufgaben des
  Kunden. *Die vier Wege*, der eigentliche Aufbau des Programms, steht an
  achter Stelle, hinter 2 087 Wörtern über die Merkmalserkennung.
- Der einzige geführte Einstieg, *Die ersten fünfzehn Minuten*, zeigt einen
  Fall (Loch in ein heruntergeladenes Modell), in 580 Wörtern Fließtext mit
  fünf Bildern ohne Markierung. Wer ein eigenes Teil bauen will, etwa ein
  Gehäuse, findet keinen Anfang.
- Das Hilfe-Menü beschreibt das Handbuch als „Jede Operation mit ihren
  Werten, nach Bereichen sortiert" (`main_window.py`). Es verspricht ein
  Nachschlagewerk, keinen Lernweg.
- **Kein Weg führt aus der Arbeit ins passende Kapitel.** F1 öffnet im
  Hauptfenster und im Skizzenmodus immer dieselbe Seite; im offenen
  Operationsdialog löst F1 nichts aus (am Qt-Nachbau gemessen: null
  Auslösungen). `manual.find` hat keinen einzigen Aufrufer. Nur 2 der 142
  Referenzeinträge sagen, wo man die Operation in der Oberfläche findet.
- **Die Suche** filtert per Teilzeichenfolge in Titel und Text, ohne
  Rangfolge und ohne Fundstelle. Gemessen an 38 typischen Kundensuchen
  (`findbarkeit.md`): Die richtige Seite steht nur bei **19 (50 %)** unter
  den ersten drei, sofort angezeigt wird sie bei **11 (29 %)**, und **4
  (11 %)** finden gar nichts, weil das Handbuch ein anderes Wort benutzt
  (*abrunden* statt *Verrunden*, *zweifarbig*, *größer machen*, *Loch
  schließen*). Im Mittel stehen 8,9 Treffer in Handbuchreihenfolge da; die
  Seite *Die Werkzeuge der Fernsteuerung* ist bei 30 der 38 Suchen darunter.
- **Die Website** ist eine einzige Seite von 188 Bildschirmhöhen auf Full HD,
  442 auf dem Telefon; 9 von 41 Bildern zeigen die Oberfläche.
- **Das PDF** hat 197 Blätter ohne Lesezeichen, und jedes Bildschirmfoto
  trägt einen toten Verweis auf `file:///F:/3D%20Druck/…`: `_staged` in
  `tools/make_manual.py` verlinkt das Bild mit sich selbst, was auf der
  Website richtig ist, und der Druck macht daraus den Pfad des Bau-Rechners.
  Neun je Sprache, 54 insgesamt, auch in den ausgelieferten 0.5.0-PDFs.
- *Die Werkzeuge der Fernsteuerung* (3 547 Wörter) wiederholt alle 142
  Operationsbeschreibungen wörtlich für Leute, die ein Programm per MCP
  anbinden, und widerspricht der Seite *Fernsteuerung*, die sagt, eine solche
  Liste gebe es nicht.

### §1.3 Was daraus für den Kunden folgt

Der Kunde aus dem Anlass kommt vom Slicer und will ein Ergebnis: ein Loch,
ein Halter, ein Gehäuse. Er findet eine Liste von 50 Kapiteln, die nach
Programmbereichen geordnet ist. Der Weg zum Ergebnis steht verteilt über
mehrere Seiten, und wo er steht, steht er als Satz: „links oben", „rechts im
Bericht", *Datei → Modell aus dem Netz*. Welcher Knopf gemeint ist, muss er
im Fenster suchen. Genau das nennt er Ausprobieren.

### §1.4 Was der Kundenblick fand

Aus `leserblick.md`, die dreißig geschriebenen Seiten mit den Augen eines
Kunden, der vom Slicer kommt:

- **18 Klickwege stehen in Worten**, jeder mit dem Bedienelement, auf das ein
  Pfeil zeigen müsste (Tabelle im Bericht). Sie sind die Vorlage für die
  Bildanleitungen.
- **Rund 127 Sätze über 25 Wörter**, 45 davon in *Zeichnen*, *Was Solidon
  im Modell erkennt* und *Bewegen und Färben*. Sechs Seiten über 800 Wörter.
- **Entwicklerblick im Kundentext:** Bauplan-Paragraphen in *Der Chat*
  (§26.4) und *Ein Modell erzeugen lassen* (§2.2), eine Versionsgeschichte
  („bis zur Fassung 0.3.5 …") und interne Messzahlen („296 von 1130
  Einträgen") in *Was Solidon im Modell erkennt*.
- **Es fehlen die Aufgaben, mit denen Kunden kommen:** das erste eigene Teil
  von Null, ein Gehäuse mit passendem Deckel, ein Maß nachträglich ändern,
  ein fremdes Modell passend machen. Die Bausteine dafür stehen über drei bis
  vier Seiten verteilt.
- *Material, Toleranzen, Passungen* stand an zwölfter Stelle, obwohl das
  Spiel darüber entscheidet, ob ein Deckel passt.
- *Die Bausteine* (777 Wörter, zehn Bilder) ist das Vorbild: Wo Bilder
  stehen, trägt der Text.

## §2 Ziel und Maßstab

Ein Kunde ohne CAD-Kenntnisse lernt die Grundwege, ohne zu raten: Er sieht
auf einem Bild der echten Oberfläche, wohin er klicken soll, und liest dazu
einen kurzen Satz. Nachschlagen bleibt möglich, steht aber nicht mehr im Weg.

Maßstab ist der Kunde, nicht die Vollständigkeit: Eine Aufgabe, die er
sucht, ist nach höchstens zwei Klicks erreichbar, und jede Anleitung passt
auf wenige Bildschirmhöhen.

## §3 Leitlinien

1. **Bild vor Wort.** Wo ein Bedienelement gemeint ist, zeigt ein
   Bildschirmfoto darauf: Nummer, Rahmen und bei kleinen Zielen ein Pfeil.
   Der Text sagt, was zu tun ist, nicht wo es liegt.
2. **Aus der echten Oberfläche.** Jedes Bild entsteht durch das Programm
   selbst, im selben Fenster, das der Kunde sieht, in seiner Sprache. Keine
   nachgestellten Bilder, keine Montage.
3. **Ein Schritt, ein Bild, ein Satz.** Eine Anleitung hat drei bis zehn
   Schritte, jeder Schritt höchstens zwanzig Wörter.
4. **Aufgabe vor Bereich.** Gegliedert wird nach dem, was der Kunde vorhat
   („Ein Loch bohren"), nicht nach dem Bereich, in dem es liegt.
5. **Lernen und Nachschlagen getrennt.** Die erzeugte Referenz bleibt
   vollständig, steht aber am Ende und wird aus dem Dialog heraus gezielt
   geöffnet.
6. **Zur Version aktuell, dazwischen nichts.** Bilder und Seiten entstehen
   beim Release. Kann eine Anleitung dort nicht mehr ausgeführt werden, weil
   ein Knopf fehlt oder ein Weg sich geändert hat, hält das den Release an.
   Zwischen zwei Versionen läuft kein Erzeuger.
7. **Kurz.** Kundensprache, Sätze unter 20 Wörtern, keine Begründungen aus
   Entwicklersicht.

## §4 Neue Gliederung

Fünf Teile, in dieser Reihenfolge, im Handbuchfenster als Gruppen sichtbar:

| Teil | Inhalt | Form |
|---|---|---|
| **Erste Schritte** | *Was Solidon ist*, *Das Fenster auf einen Blick*, *Die vier Wege*; je ein Weg vom Start bis zum Druck: vorhandenes Modell prüfen und drucken, ein Loch in ein heruntergeladenes Modell, das erste eigene Teil, ein Gehäuse mit Deckel, ein Teil, das nicht auf das Bett passt | Bildanleitungen und zwei kurze Seiten |
| **Anleitungen** | Einzelne Aufgaben: verschieben und drehen, ein Maß nachträglich ändern, einen Schritt zurücknehmen oder ändern, Bohrung und Gewinde, Kanten abrunden oder anfasen, Baustein einsetzen, beschriften, aushöhlen und Deckel, zeichnen und herausziehen, zweifarbig drucken, reparieren, an den Slicer übergeben | Bildanleitungen, je drei bis acht Schritte |
| **Funktionen** | Die bestehenden Erklärseiten je Bereich, nach Häufigkeit geordnet: das Fenster im Einzelnen, der Verlauf, Bewegen, Material und Passungen, Bausteine, Zeichnen, Hinsehen, Erkennen, Parameter, Drucken und Ausgeben, dann das Seltene | Erklärseiten, in HB-9 gekürzt und bebildert |
| **Hilfe bei Problemen** | Wenn etwas nicht geht, die 3D-Maus | bestehende Seiten |
| **Nachschlagen** | Wörterbuch, dann alles Erzeugte: Modelle, Regeln, Material, Drucker, Normteile, Fernsteuerung, Meldungen, alle Operationen | am Ende |

Der dritte Teil hieß im Entwurf „Verstehen"; die Seiten darin erklären aber
Bereiche des Programms, und ein Kunde sucht „Zeichnen", nicht „Verstehen".
Der vierte heißt nicht wie die Seite *Wenn etwas nicht geht*, die in ihm
steht.

Die Gliederung steht an **einer** Stelle, `manual.OUTLINE`: je Teil die
Seiten in Lesereihenfolge. Die erzeugten Seiten folgen am Ende von
„Nachschlagen" wie bisher. Die erste Seite heißt künftig „Wo fange ich an?"
und verweist auf die Erste-Schritte-Anleitungen; der Handbuchknopf des
Startbildschirms öffnet sie (HB-5).

## §5 Bildanleitungen — wie sie entstehen

Eine Bildanleitung hat drei Teile, und jeder liegt dort, wo er hingehört:

| Teil | Ort | Warum dort |
|---|---|---|
| **Beschreibung:** Titel, Kurzfassung, Schritte mit Satz und Zielen | `app/core/guides.py` | Ohne Qt prüfbar, übersetzbar über `_()`, dieselbe Quelle für Fenster, Website, PDF und Kommandozeile |
| **Ziele:** welches Bedienelement ein Name meint | Vokabular in `app/core/guides.py`, Auflösung in `app/ui/guide_targets.py` | Der Kern kennt die Namen, die Oberfläche kennt die Widgets; die Tour teilt dieselbe Auflösung |
| **Aufnahme:** Weg durch die echte Oberfläche, Markierung, Ausschnitt | `tools/make_guides.py` | Braucht ein sichtbares Fenster und reist nicht zum Kunden |

### §5.1 Beschreibung im Kern

`Guide` trägt Schlüssel, Titel, Kurzfassung, Teil (§4) und Schritte.
`GuideStep` trägt den Satz und die Namen der Ziele, auf die das Bild zeigt.
Die Anleitung weiß nicht, **wie** der Zustand entsteht; das weiß das
Aufnahmewerkzeug. Sie weiß, **was** der Kunde tut und **wohin** er sieht.

Aus jeder Anleitung wird eine Handbuchseite: Kurzfassung, dann die Schritte
als nummerierte Folge aus Bild und Satz. Die Bilder sind gewöhnliche
Abbildungen des Katalogs (`figures.py`, Art `shot`, Schlüssel
`guide-<anleitung>-<nummer>`), ihr Alt-Text ist der Satz des Schritts. Fehlt
ein Bild, zeigt das Handbuch wie heute den Satz allein und bleibt lesbar.

### §5.2 Benannte Ziele

Ein Ziel ist ein Name aus einem festen Vokabular im Kern:

- Bereiche des Hauptfensters: `tree`, `parameters`, `history`, `report`,
  `viewport`, `toolbar`, `tools` (heute schon die Tour-Ziele) und weitere wie
  `menubar`, `statusbar`;
- Startbildschirm: `start.drop`, `start.new`, `start.open`, `start.manual`;
- Befehle über ihre bestehende Kennung aus `MainWindow.window_commands`:
  `command:file.open`, `command:file.print_settings`;
- Operationen über ihren Registernamen: `operation:drill_hole` (der
  Menüeintrag);
- im offenen Operationsdialog: `field:<parameter>`, dazu `dialog` (der Dialog
  als Ganzes) und `dialog.accept`, sein Hauptknopf. Der heißt nicht
  „Übernehmen", sondern wie die Operation („Bohrung setzen"), bei Bausteinen
  „Einsetzen"; *Übernehmen* steht im Auswahlfenster und in der
  Platzierungsleiste;
- im Prüfbericht: `report.action` (die erste angebotene Handlung); im
  Verlauf: `history.last` (der letzte Schritt);
- im Auswahlfenster: `selection.parts`, der Knopf *Bausteine*; im offenen
  Bausteinkatalog: `part:<name>`, die Kachel eines Bausteins über seinen
  Registernamen (`part:screw_hole`).

Ein Menüeintrag hat nur einen Ort, solange sein Menü offen ist. Die
Aufnahme klappt deshalb das Menü bis zum Eintrag auf
(`guide_targets.action_for` nennt die Aktion), und das offene Menü steht
samt Titel im Menübalken ganz im Bild.

Die Auflösung in ein Rechteck geschieht in der Oberfläche. Ein Name, den sie
nicht kennt, ist ein Fehler, keine leere Markierung. `MainWindow._flash_area`
(Tour) benutzt dieselbe Auflösung; heute steht dort eine zweite Zuordnung
derselben sieben Namen.

### §5.3 Aufnahme

`tools/make_guides.py` baut das Hauptfenster wie die Anwendung, auf dem
gewählten Bildschirm und nicht offscreen (dieselben Gründe wie bei
`make_figures.py`: Schriften, OpenGL). Je Sprache ein Kindprozess mit
umgebogenen Nutzerverzeichnissen (Muster `make_web_images.py`), denn die
Anleitungen öffnen Dateien, legen Spulen an und merken sich Einstellungen.

Je Anleitung gibt es im Werkzeug eine **Geschichte**: eine Funktion, die den
Weg durch die Oberfläche geht, jeden Schritt abwartet und nach jedem Schritt
`aufnehmen(n)` ruft. Das Werkzeug prüft, dass die Geschichte genau so viele
Bilder liefert, wie die Anleitung Schritte hat. Die Bausteine dafür gibt es
schon: `make_longform_video.Recorder` greift echte Fensterzustände,
`_menu_path` und `_show_action_path` öffnen Menüwege, `make_video._paint_pointer`
zeichnet den Zeiger, `make_figures.settle`/`await_result` warten die
Auswertung ab.

**Markierung.** Je Ziel ein Rahmen mit abgerundeten Ecken in der
Akzentfarbe, außen hell abgesetzt, damit er auf hellem und dunklem Grund
trägt; am Rahmen eine runde Nummer. Ist das Ziel klein (Menüeintrag, Knopf
unter 48 Bildpunkten), zeigt zusätzlich ein Pfeil darauf. Der Rest des Bildes
wird leicht abgedunkelt, damit das Ziel ohne Suchen auffällt. Die Nummer ist
die zweite Kodierung neben der Farbe (Regel 18).

**Erst das Bild, dann der Satz.** Ein Satz, der eine Bedienung beschreibt,
ist eine Vermutung, bis sein Bild vorliegt. Zweimal hat der Probelauf den
Entwurf widerlegt: Unter einem Befund stand kein Knopf „beheben", sondern
*Stelle zeigen* und *Offen lassen*, weil Solidon beim Einlesen schon
repariert; und die Vorschau eines Lochs war im Bild neben dem Dialog nicht
zu sehen, weil das Werkzeugkreuz der gewählten Fläche darüber lag. Beim
ersten eigenen Teil kamen drei Korrekturen dazu: Kachel und *Einfügen* in
einem Bild machten den Ausschnitt zum ganzen Katalog, also fügt ein
Doppelklick ein; das Datei-Menü war ein Umweg, denn an der gewählten Fläche
steht rechts der Knopf *Bausteine*; und ein Klickpunkt mitten auf dem
Werkzeugkreuz sah aus wie ein Griff daran. Deshalb wird eine Anleitung erst
aufgenommen und angesehen, dann werden Sätze und Übersetzungen
festgeschrieben.

**Ringe für Stellen im Modell.** Wo geklickt wird, steht der Mauszeiger mit
Klickring; wo etwas zu sehen ist, ein Ring ohne Zeiger, bei einem Loch aus
seinem echten Durchmesser auf den Schirm projiziert.

**Ausschnitt.** Ein Schritt zeigt, was er braucht: den Umkreis seiner Ziele
mit genug Rand, damit der Kunde erkennt, wo im Fenster er ist. *Das Fenster
auf einen Blick* zeigt das ganze Fenster.

**Format und Größe.** Die Bilder reisen mit der Anwendung, und bei rund
sechzig Schritten in sechs Sprachen zählt jedes Kilobyte. Ziel ist ein Budget
von höchstens 15 MB für alle Anleitungsbilder aller Sprachen zusammen.
Festgelegt ist WebP mit Qualität 86, höchstens 1600 Punkte breit; das
Qt-Bildformat dafür liegt im Paket (`qwebp.dll` unter
`_internal/PySide6/plugins/imageformats/` im Windows-Bau). Gemessen, als die
vier Anleitungen aus HB-4 standen: 23 Bilder wiegen 0,69 MB je Sprache, im
Mittel 30 KB je Bild. Sechzig Schritte in sechs Sprachen kämen damit auf rund
11 MB, unter dem Budget. Zum Vergleich: Die bisherigen Handbuchbilder wiegen
1,3 MB je Sprache.

### §5.4 Anzeige

- **Handbuchfenster:** Gruppen statt flacher Liste (§4); Verweise zwischen
  Seiten über `manual:<schlüssel>`, die das Fenster selbst auflöst.
- **Website und PDF:** `tools/make_manual.py` gliedert das Inhaltsverzeichnis
  nach denselben fünf Teilen; die Schrittbilder kopiert es wie die übrigen
  Bildschirmfotos.

## §6 Immer aktuell zur Version, und nur dann

- **Beim Release** läuft `make_guides.py` im Skill `/erzeugen`, vor
  `make_manual.py`, in allen Sprachen. Jede Geschichte geht ihren Weg in der
  echten Oberfläche. Fehlt ein Ziel, scheitert ein Schritt oder wird eine
  Auswertung nicht fertig, endet das Werkzeug mit einem Fehler und nennt
  Anleitung und Schritt. **Ein roter Lauf hält den Release an**, genau wie ein
  roter Bausteinnachweis.
- **Ein Stempel je Sprache** (`app/images/manual/<sprache>/guides.json`) hält
  Version und Abdruck der Anleitungen fest. Ein Test mit Marker `rendered`
  vergleicht ihn mit `branding.APP_VERSION` und dem heutigen Abdruck. Zwischen
  zwei Releases ist er rot, und das ist Zustand, kein Fund (wie heute
  `test_manual`).
- **Die Referenz** entsteht wie bisher aus dem Register und kann nicht
  veralten.
- **Die geschriebenen Seiten** bekommen einen Wächter für Menüwege: Jeder Weg
  der Form *A → B* im Text muss aus Texten bestehen, die die Oberfläche
  wirklich zeigt (Einsammler, `app/i18n/extract.py`). Ein umbenannter
  Menüeintrag macht die Suite rot statt das Handbuch still falsch.
- **Zwischendrin** läuft kein Erzeuger. Wer eine Anleitung ändert, prüft sie
  mit `make_guides.py --ziel <ordner> --nur <anleitung>` in einer Sprache und
  checkt keine Bilder ein.

**Warum laut scheitern die Pflicht ist:** Zwei der drei Geschichten von
`tools/make_longform_video.py` enden heute mit `AttributeError`, weil der
Skizzenknopf `panel.shapes_button` nicht mehr existiert
(`aufnahmetechnik.md` §1). Aufgefallen wäre es erst beim nächsten Filmen.
Dazu kommen Stellen, die ein fehlendes Ziel still überspringen:
`_menu_path` gibt eine leere Liste zurück, `_show_operation` fällt auf den
Ok-Knopf zurück, `_flash_area` kehrt bei einem unbekannten Namen zurück.
`make_guides.py` übernimmt die Bausteine, aber keine dieser stillen Stellen.

## §7 Finden

- **Gruppen** im Handbuchfenster (§4).
- **Suche mit Rangfolge** (`app/core/manual_search.py`, gebaut): Titel vor
  Kurzfassung vor Stichwort (Überschriften, Fettdruck) vor Fließtext, das
  ganze Wort vor dem Wortanfang, Anleitungen vor Referenz, und jede Seite
  schlägt an ihrer Fundstelle auf, markiert. **Kein eigenes Wörterbuch:**
  Faltung, Trefferstärke und Kundenwörter kommen aus der Befehlspalette
  (`registry/search.py`). „abrunden" führt so auf *Verrunden*, „größer
  machen" auf *Skalieren*, in jeder Sprache, und eine Ergänzung dort wirkt an
  beiden Stellen. Gemessen an den 50 Kundensuchen aus
  `nachweise-handbuch-2026-09/findbarkeit.md`: von den 38 aus dem Auftrag
  stehen jetzt alle unter den ersten drei (vorher 25) und 35 ganz oben
  (vorher 7). Keine Suche bleibt ohne Treffer (vorher 4). Messung, Tabelle und
  jede Gewichtung mit ihrem Grund: `nachweise-handbuch-2026-09/suche.md`.
- **F1 im Zusammenhang:** im Operationsdialog die Anleitung zu dieser
  Operation oder, wo es keine gibt, ihr Referenzeintrag; sonst „Wo fange ich
  an?".
- **Das Hilfe-Menü** beschreibt das Handbuch als Lernweg.

## §8 Texte

Die Erklärseiten werden gekürzt: Klickwege wandern in Bildanleitungen,
Begründungen aus Entwicklersicht fallen weg, Sätze werden kurz. Gekürzt wird
seitenweise, und jede gekürzte Seite wird in allen fünf Katalogen **neu**
übersetzt statt geflickt. Welche Seite was braucht, steht in
`nachweise-handbuch-2026-09/leserblick.md`.

## §9 Arbeitspakete

Legende wie im Register: `[ ]` offen · `[~]` begonnen · `[x]` fertig mit
Nachweis.

| Paket | Inhalt | Abnahme | Stand |
|---|---|---|---|
| HB-0 | Konzept, Registerpunkt, Nachweise, Übergabe | Dieses Dokument, RM-283, §0 | [x] |
| HB-1 | `app/core/guides.py`: Anleitungen, Schritte, Zielvokabular; Handbuchseiten aus Anleitungen; Gliederung `manual.OUTLINE` und Feld `Page.part`; Abbildungen der Schritte im Katalog; nummerierte Listen in `markup.py` | Kerntests: jede Anleitung vollständig, Schritte kurz, Ziele aus dem Vokabular, Seiten in Teilreihenfolge; Übersetzungen vollständig | [x] `54e83a72e`; `tests/test_guides.py` (14 Tests), betroffene Kerntests grün; rot nur die `rendered`-Vergleiche gegen die Website, davon vier schon am Ausgangsstand und der fünfte, weil die neue Seite erst beim Release in die Website kommt |
| HB-2 | `app/ui/guide_targets.py`: Namen → Widget/Rechteck; `_flash_area` benutzt sie | Test: jedes Wort des Vokabulars wird aufgelöst (Fenstertest, läuft beim Release) | [x] Auflösung und Tour gebaut; Kerntest: Wortschatz und Auflösung decken sich. Der Fenstertest über alle festen Namen läuft beim Release |
| HB-3 | `tools/make_guides.py`: Geschichten, Markierung, Ausschnitt, Format, Kindprozess je Sprache, `--ziel`, `--nur`, Stempel; Schritt in `/erzeugen` | Ein Lauf in einer Sprache in einen fremden Ordner; Bildbudget gemessen; Fehler bei fehlendem Ziel belegt | [~] Werkzeug gebaut: Rahmen, Nummern, Pfeile, Abdunkeln, Rand, Ausschnitt, WebP (Übersichtsbild 82 KB statt 408 KB als PNG), Kindprozess je Sprache, Stempel. Deutsch in einen fremden Ordner gelaufen; ein fehlendes Ziel beendet den Lauf mit Exit 1 und nennt Anleitung und Schritt. Bildbudget gemessen (§5.3): 30 KB je Bild, rund 11 MB für sechzig Schritte in sechs Sprachen. `/erzeugen` nimmt die Anleitungen bei jedem Release in allen Sprachen auf, nach dem Versionssprung und vor `make_manual.py`; `test_guides` steht bei den Wächtern vor dem Tag. [x] |
| HB-4 | Erste Anleitungen: *Das Fenster auf einen Blick*, *Ein Modell prüfen und drucken*, *Ein Loch in ein heruntergeladenes Modell*, *Das erste eigene Teil* | Bilder in einer Sprache gesichtet; Texte in sechs Sprachen | [x] alle vier gebaut, auf Deutsch aufgenommen und gesichtet, Sätze in sechs Sprachen; der Menüweg im Satz ist gegen das Menü geprüft, jeder andere hervorgehobene Name gegen den Katalog, in jeder Sprache (`test_a_menu_path_in_a_step_is_the_one_the_menu_shows`, `test_a_name_in_a_step_is_the_one_the_interface_shows`); auf Englisch aufgenommen und gesichtet |
| HB-5 | Gliederung im Handbuchfenster, „Wo fange ich an?", Verweise `manual:`, Hilfe-Menü, Startbildschirmknopf | Fenstertests (Release), Kerntests für Reihenfolge und Verweise | [x] „Wo fange ich an?“ als erste Seite, Listen aus `guides.GUIDES`; Teilüberschriften im Fenster, gesperrt und von den Pfeiltasten übersprungen, in voller Schriftfarbe; Hilfe-Menü und Startknopf sprechen vom Lernweg. Kerntests `test_the_manual_begins_where_to_start`, `test_where_to_start_leads_to_every_guide_by_its_title` (sechs Sprachen); Fenstertests für Gruppen und Startknopf laufen beim Release, das Verhalten ist per Sonde am Stand belegt |
| HB-6 | Suche mit Rangfolge, Fundstelle, Kundenwörtern | Anteil der Suchen mit richtiger Seite unter den ersten drei, vorher und nachher gemessen | [x] 38 von 38 unter den ersten drei (vorher 25), 35 ganz oben (vorher 7), keine ohne Treffer (vorher 4); `tests/test_manual_search.py`, Nachweis `suche.md`. Der Fenstertest über Rangfolge und Fundstelle läuft beim Release |
| HB-7 | F1 im Zusammenhang | Fenstertest (Release) | [x] F1 im Operationsdialog meldet `manual.help_for` (Anleitung aus `Guide.teaches`, sonst Referenzeintrag an seiner Überschrift, markiert); verdrahtet in `_open_operation_dialog` und im Bearbeitungsdialog der lokalen Suche. F1 im Hauptfenster: neu geöffnet „Wo fange ich an?“, offen bleibt die Leseseite, minimiert kommt es zurück. Kerntest über alle 142 Operationen, Fenstertests beim Release. Das Code-Review fand F1 bei 53 Operationen aus `parts` und `sketch` oben auf der Erklärseite, weil sie ihren Schlüssel mit dem Referenzkapitel teilte; seitdem heißen die Referenzkapitel `ref-<kategorie>`, ein Test hält jeden Seitenschlüssel einmalig, und F1 lässt eine offene Anleitung stehen |
| HB-8 | Weitere Anleitungen (Liste in §4) | je Anleitung wie HB-4 | [x] Fünfzehn Anleitungen. Zu den fünf aus HB-4 und *Ein Gehäuse mit Deckel* kommen *Ein zu großes Teil teilen* (Erste Schritte) sowie *Ein Teil verschieben und drehen*, *Ein Maß nachträglich ändern*, *Einen Schritt zurücknehmen oder ändern*, *Ein Gewinde in eine Bohrung*, *Kanten abrunden oder anfasen*, *Ein Teil beschriften*, *Eine Form zeichnen und hochziehen*, *Zweifarbig drucken* und *Ein Modell reparieren*. Je Aufgabe drei bis sieben Schritte, alle fünfzehn auf Deutsch mit dem fertigen Werkzeug aufgenommen und gesichtet. Sätze in sechs Sprachen, jeder hervorgehobene Name gegen den Katalog; F1 lehrt über `Guide.teaches`, „Wo fange ich an?“ führt zu allen, die Kundensuchen finden sie (`test_manual_search`), und jede steht am Ende ihrer Erklärseite unter „Schritt für Schritt:“ (`Guide.topics`). Neue Ziele: `dialog.naming`, `transform.values`, `parameters.first`, `toolbar.draw`, `sketch.*`, `history:*`, `tool:`, `transform:`, `section:` |
| HB-9 | Erklärseiten kürzen und neu übersetzen | Wortzahl der Erklärseiten um mindestens ein Drittel kleiner, kein Wissen verloren (verschoben in Anleitungen oder Referenz) | [x] 27 Seiten (alle aus `INTRODUCTION` außer `start` und `glossary`): 9 861 statt 14 827 Wörter, −33,5 %; jede Seite in fünf Sprachen als Ganzes neu übersetzt. Weggefallen sind Wiederholungen, Entwicklersicht (Bauplan-Verweise, Versionsgeschichte, Messzahlen) und Klickwege, die eine Anleitung zeigt; dort stehen Verweise `manual:`. `remote` widerspricht `remote-tools` nicht mehr. Aussagen berichtigt (Auswahlfenster ohne Auswahl, Abstandsanzeige, Knopf *Filament abziehen …*, offene Modelle in `trouble` nach den echten Befunden, Rückfrage im Verlauf). Suche: ganz oben 42 von 50 wie vorher, unter den ersten drei 50 statt 49. Nachweis `nachweise-handbuch-2026-09/kuerzung.md` |
| HB-10 | Website und PDF nach Teilen gegliedert, Referenz am Ende; PDF mit Lesezeichen und **ohne tote Verweise auf den Bau-Rechner** | Seiten erzeugt beim Release, Tests `rendered` grün, im PDF kein Verweis mit `file:` | [x] Die Verweise um die Bildschirmfotos fallen vor dem Druck weg; `test_the_pdf_links_nowhere_outside_itself_but_the_website` hält es beim Release. **Gliederung** (`8abf2ba87`): Verzeichnis und Text von Website und PDF nach den Teilen aus `Page.part`, vor dem ersten Kapitel eines Teils eine Teilüberschrift, ein Teil ohne Seiten erscheint nicht. Die erzeugten Kapitel stehen am Ende von *Nachschlagen* mit Wörterbuch und Wissensseiten, so gruppiert auch das Fenster; der alte Zwischentitel „Referenz — jede Operation mit ihren Werten“ stand auch über den Wissensseiten. Im Druck beginnt jeder Teil auf einem neuen Blatt, das Verzeichnis passt auf eines statt zwei. **Lesezeichen** (`7ac97c6a5`): Teile oben, Kapitel darunter, beim Stempeln aus den benannten Zielen; das PDF öffnet mit ihnen. **JPEG** (`febba2f4d`): Ein Bildschirmfoto geht als JPEG (Qualität 92) in den Druck, wo es leichter ist als verlustfrei, also die 33 Schrittbilder; die 9 PNG-Bildschirmfotos packen sich verlustfrei kleiner und bleiben. Ein Druck gilt erst, wenn das PDF jedes Bildschirmfoto trägt. Gemessen mit dem Probelauf aller Anleitungen, vorher `8fa13081f`, nachher `febba2f4d`: de 21,9 → 18,1 MB, en 20,9 → 17,4, es 22,2 → 18,5, fr 22,7 → 18,9, it 22,1 → 18,3, pt 22,1 → 18,3; je Sprache 42 Rasterbilder vorher und nachher; die Bilder im deutschen PDF 8,5 → 4,8 MB, der Rest ist Vektorinhalt. Schrift am gerenderten PDF bei 400 und 500 dpi so scharf wie verlustfrei. Ein Probeverweis auf *Die vier Wege* springt auf der Website zu `#ways` und im PDF auf die erste Seite des Kapitels. Im Wegwerfbaum `rendered` von `test_manual` und `test_guides`: 78 passed. Die PDFs liegen nur im Repository, nicht im Paket und nicht auf der Website |
| HB-11 | Wächter für Menüwege im Text (§6) | Test in der Suite | [x] `test_manual::test_a_way_in_a_written_page_is_the_one_the_interface_shows`, je Sprache: jeder Weg einer geschriebenen Seite ausgezeichnet, beginnt an einem Menü der Leiste, besteht aus Katalogtexten, heißt Glied für Glied wie der Katalog das Deutsche übersetzt, und endet er auf einer Operation, ist er ihr `menu_path`. Gegenprobe mit fünf Mutationen, alle rot. Gefunden und behoben: *Material kalibrieren* stand auf Italienisch und Portugiesisch anders als im Menü. Ob ein Eintrag ohne Operation unter genau diesem Menü steht, weiß nur das Fenster (`test_wording`, beim Release) |
| HB-12 | Video-Tutorial aus denselben Geschichten (die Zusage an den Kunden) | erst, wenn HB-4 und HB-8 stehen und die Bedienung ruhiger ist | [x] `tools/make_guide_video.py`: je Sprache *Vom Start bis zum Druck* (sechs Anleitungen, auf Deutsch 5:19) und *Einzelne Aufgaben* (neun, 6:20), `--nur` je Anleitung ein Film. 1920 × 1080, 30 Bilder je Sekunde, H.264 und AAC, von ffprobe geprüft; Kapitelmarken nach den Regeln von YouTube, Titelbild, Ablauf als JSON. Der Satz steht unter dem Bild, die Namen in der Farbe der Markierung; die Standzeit folgt der Wortzahl, dazwischen Überblendungen, darunter das Musikbett aus `make_longform_video`. Passen Bilder und Anleitungen nicht zusammen, bricht es ab. Die Einblendungen passen in allen sechs Sprachen, deutsch geschnitten und angesehen; `/erzeugen` nach `make_guides.py` |
| HB-13 | Die Referenz nennt je Operation ihren Weg in der Oberfläche (Menü oder Auswahlfenster), erzeugt aus dem Menüaufbau | Kerntest: jede Operation mit Weg; heute 2 von 142 | [x] 142 von 142 aus `registry.menu_path`; `test_every_operation_names_where_it_is_found`. Die Website zeigt es nach dem nächsten Handbuchlauf |

## §10 Risiken und offene Entscheidungen

- **Die Bedienung ändert sich weiter.** Jede Änderung an einem Weg, den eine
  Anleitung geht, zeigt sich beim Release als roter Lauf. Das ist gewollt:
  Es ist der Nachweis, dass das Handbuch stimmt. Der Preis ist Pflegearbeit
  am Release, und die ist kleiner als ein Handbuch, das still veraltet.
- **Paketgröße.** Gemessen (§5.3): hochgerechnet rund 11 MB für sechzig
  Schritte in sechs Sprachen, unter dem Budget von 15 MB. Ein Bild über
  100 KB ist ein Zeichen für einen zu großen Ausschnitt, nicht für ein
  falsches Format.
- **Sechs Sprachen.** Jeder neue Satz braucht fünf Übersetzungen, bevor er
  eingecheckt werden kann (`pre-commit`).
- **Fenstertests nur beim Release.** HB-2, HB-5 und HB-7 sind erst beim
  nächsten Release-Tor vollständig abgenommen.
- **Beispielprojekte und Touren** bleiben vorerst unberührt (Robert,
  27.09.2026: „die beispielprojekte erstmal ignorieren", gesagt zu einer
  Kundenmail). Die Anleitungen hängen nicht an ihnen.
- **Entschieden (27.09.2026, nach Kundensicht):** *Die Werkzeuge der
  Fernsteuerung* bleibt als erzeugte Seite unter *Nachschlagen*. Wer ein
  Programm per MCP anbindet, ist auch Kunde, und die Seite ist die Liste, die
  er dafür braucht; die Suche stellt sie seit HB-6 nachrangig (ihre Wertung
  wird geviertelt), in keiner der 50 Kundensuchen steht sie vor der richtigen
  Seite. Den Widerspruch zur Seite *Fernsteuerung* löst Strang B auf (§12.2).
- **Die Gruppe *Anleitungen* verweist nicht mit eigenen Zeilen** auf Aufgaben,
  die schon eine Anleitung der Ersten Schritte zeigt (Baustein einsetzen,
  aushöhlen mit Deckel, bohren, an den Slicer übergeben). Eine Verweiszeile in
  der Seitenliste risse die Pfeiltasten in den anderen Teil. Diese Aufgaben
  nennt die Kurzfassung ihrer Anleitung, und „Wo fange ich an?“ listet alle
  Anleitungen beider Teile mit Kurzfassung: jede Aufgabe in zwei Klicks vom
  Startbildschirm (§11).

## §11 Abnahme des Ganzen

- Jede Aufgabe aus §4 ist vom Startbildschirm aus in höchstens zwei Klicks
  erreichbar.
- Jeder Schritt einer Anleitung: ein Bild mit mindestens einer Markierung,
  höchstens zwanzig Wörter.
- Suche: Die richtige Seite steht bei mindestens 80 Prozent der gemessenen
  Kundensuchen unter den ersten drei.
- Release: `make_guides.py` läuft in allen sechs Sprachen grün, der
  Stempeltest ist grün.
- Feldabnahme: Ein Kunde ohne CAD-Kenntnisse geht *Das erste eigene Teil*
  ohne Hilfe durch. Der Interessent aus dem Anlass ist dafür der natürliche
  erste Leser.

## §12 Plan bis 0.5.1

Robert, 27.09.2026 abends: „alle punkte davon sollen noch in 0.5.1“ — alle
offenen Pakete aus §9. Weil das viel ist, laufen drei Stränge nebeneinander.
Nur Strang A braucht den echten Bildschirm; zwei Aufnahmen gleichzeitig
stören sich, deshalb liegen alle Aufnahmen in einem Strang.

| Strang | Pakete | Arbeitsbaum, Zweig | Wer |
|---|---|---|---|
| A | HB-5, HB-7, HB-8, HB-12 | `F:\3D Druck.handbuch`, `handbuch-umbau` | die Handbuch-Sitzung selbst |
| B | HB-11, dann HB-9 | `F:\3D Druck.handbuch-texte`, `handbuch-texte` | Agent `oberflaechentexte` |
| C | Rest von HB-10 | `F:\3D Druck.handbuch-pdf`, `handbuch-pdf` | allgemeiner Agent |

**Anlegen,** nachdem `main` im Zweig ist:
`git worktree add -b handbuch-texte "F:/3D Druck.handbuch-texte" handbuch-umbau`,
ebenso `handbuch-pdf`. Jeder Agent bekommt seinen Auftrag aus §12.2 oder
§12.3 wörtlich und legt seinen Bericht als Datei ab.

**Zusammenführen:** B und C per Merge in `handbuch-umbau`, die Kataloge
schlüsselweise vereinigt; dann das Tor, dann eine Meldung an die
Release-Sitzung wie die erste (Endcommit, Tor, Changelog-Sätze in sechs
Sprachen, was beim Release zu tun ist). Die letzte Meldung heißt
ausdrücklich „Handbuch fertig“.

**Regeln für alle Stränge:** Tor vor jedem Commit, keine Fenstertests und
keine Erzeuger außer im Wegwerf-Arbeitsbaum, erzeugte Dateien nie
einchecken, kein Revert, kein Rebase. Jeder neue Oberflächentext in allen
sechs Sprachen.

### §12.1 Strang A — Reihenfolge und Entwurf

1. **HB-5.** „Wo fange ich an?“ ersetzt die Seite `start` („Die ersten
   fünfzehn Minuten“) als erste Seite: wenige Sätze, dann Verweise auf die
   Anleitungen der Ersten Schritte und auf die Teile. Was die alte Seite
   allein weiß, wandert in eine Anleitung oder bleibt kurz. Der
   Handbuchknopf des Startbildschirms öffnet sie; Knopftext und Seitentitel
   hält `test_the_start_screen_button_opens_the_chapter_it_names`
   zusammen. Das Handbuchfenster zeigt je Teil eine Gruppenzeile, die sich
   nicht wählen lässt; bei einer Suche bleibt die Rangliste ohne Gruppen.
   Das Hilfe-Menü beschreibt das Handbuch als Lernweg statt als
   „Jede Operation mit ihren Werten“.
2. **HB-7.** F1 im Operationsdialog öffnet die Anleitung, die diese
   Operation lehrt, sonst ihren Eintrag in der Referenz an der Fundstelle;
   F1 im Hauptfenster öffnet „Wo fange ich an?“. Welche Anleitung eine
   Operation lehrt, steht als Feld an `Guide` und wird nicht aus den
   Markierungen geraten.
3. **HB-8.** *Ein Teil, das nicht auf das Bett passt* (Erste Schritte) und
   die Aufgaben aus §4: verschieben und drehen, ein Maß nachträglich ändern,
   einen Schritt zurücknehmen oder ändern, ein Gewinde in eine Bohrung,
   Kanten abrunden oder anfasen, beschriften, zeichnen und herausziehen,
   zweifarbig drucken, reparieren. Baustein einsetzen, aushöhlen mit Deckel,
   bohren und an den Slicer übergeben zeigen die vorhandenen Anleitungen;
   „Wo fange ich an?“ führt zu ihnen, statt sie zu doppeln (§10). Je
   Anleitung erst aufnehmen und ansehen, dann Sätze und Übersetzungen
   festschreiben (§5.3); drei bis sechs Schritte je Aufgabe, damit das
   Bildbudget hält. Die Namen im Satz prüft `test_guides` in jeder Sprache.
   Jede neue Anleitung kommt als Verweis in „Wo fange ich an?“ oder in die
   Gruppe *Anleitungen*.
4. **HB-12.** Das Video-Tutorial aus denselben Geschichten, wenn HB-8 steht.

### §12.2 Strang B — Auftrag (HB-11, HB-9)

Arbeitsbaum `F:\3D Druck.handbuch-texte`, nur dort. Lesen: §1 bis §4, §6,
§8, §10 dieses Konzepts, `nachweise-handbuch-2026-09/leserblick.md` und den
Teil über die geschriebenen Seiten in `findbarkeit.md`; `AGENTS.md`,
`CLAUDE.md`, die Karte `app/core/CLAUDE.md`, die Regeln `kern.md`,
`uebersetzung.md` (Glossare verbindlich), `oberflaeche.md` („Texte, die der
Kunde liest“), `tests.md`; Roberts Vorgaben zum Ton in der Erinnerung
`kundentexte-und-uebersetzung` (kurz, nicht nach KI, „Version“, neu
übersetzen statt flicken, Genus).

1. **HB-11:** Ein Test in `tests/test_manual.py`, je Sprache: Jeder Weg
   *A → B → …* in einer geschriebenen Seite besteht aus Texten, die die
   Oberfläche in dieser Sprache zeigt; endet er auf einer Operation, ist er
   ihr Menüweg (`registry.surfaces.menu_path`). Vorbilder in
   `tests/test_guides.py`. Gegenprobe mit einem umbenannten Menüteil und
   einem falschen Weg; was der Test heute findet, in allen Sprachen beheben.
2. **HB-9:** Alle Seiten aus `manual.INTRODUCTION` außer `start` und
   `glossary`. Die deutsche Wortzahl (Kurzfassung und Text, gezählt wie in
   §1.1) sinkt insgesamt um mindestens ein Drittel, ohne Wissen zu
   verlieren: Wegfallen dürfen Wiederholung, Entwicklersicht und Klickwege,
   die eine Anleitung zeigt — dann steht dort ein Verweis
   `[Titel](manual:schlüssel)`, nur auf Schlüssel, die es im Zweig gibt.
   Den Widerspruch zwischen `remote` und `remote-tools` in der Seite
   `remote` auflösen; `remote-tools` bleibt, wo es ist. Jede gekürzte Seite
   in allen fünf Katalogen neu übersetzen, als ganze Seite; alte Schlüssel
   hinaus (`python -m app.i18n.extract`). `test_manual_search` bleibt grün;
   fällt ein Kundenwort aus dem Text, gehört es zurück oder in
   `CUSTOMER_WORDS`. Kein Test wird gelockert, der eine Aussage prüft.
   Nachweis `nachweise-handbuch-2026-09/kuerzung.md` (Wörter je Seite vorher
   und nachher, was wohin wanderte), HB-9 und HB-11 in §9 fortschreiben.
3. Nicht anfassen: `guides.py`, `make_guides.py`, `make_manual.py`,
   `app/ui/`, `manual.OUTLINE`, die Seite `start`, die Anleitungen.

### §12.3 Strang C — Auftrag (Rest von HB-10)

Arbeitsbaum `F:\3D Druck.handbuch-pdf`, nur dort. Lesen: §4, §5.4, §9
(HB-10) und §10 dieses Konzepts, `AGENTS.md`, `CLAUDE.md`, die Karte
`tools/CLAUDE.md`, die Regeln `auslieferung.md` und `tests.md`.

1. **Gliederung:** Das Inhaltsverzeichnis von Website und PDF
   (`tools/make_manual.py`, `contents`) zeigt die fünf Teile aus
   `manual.pages()` (`Page.part`, Titel aus `manual.PART_TITLES`), und vor
   dem ersten Kapitel eines Teils steht im Text eine Teilüberschrift. Die
   erzeugten Kapitel bleiben am Ende; ob sie mit Wörterbuch und Wissensseiten
   unter „Nachschlagen“ zusammengehören, begründet entscheiden. Keine zweite
   Liste der Zuordnung. Anker und Verzeichnis dürfen nicht brechen
   (`test_the_contents_lead_to_the_chapter_they_name`,
   `test_no_manual_page_promises_a_chapter_it_cannot_reach`).
2. **Lesezeichen im PDF:** Teile oben, Kapitel darunter, jedes springt auf
   seine erste Seite; gebaut aus den benannten Zielen, die
   `_chapter_of_each_page` schon liest, im selben Schritt wie `_stamp`.
3. **Leichteres PDF:** Den Druck die Bildschirmfotos als JPEG einbetten
   lassen, die Website behält ihre Dateien. Qualität so, dass die Schrift im
   Bild scharf bleibt, am gerenderten PDF angesehen. Vorher und nachher
   messen: Größe je Sprache und Zahl der eingebetteten Bilder; die Zahl darf
   nicht sinken.
4. **Seitenverweise** springen im Ergebnis zum Anker (gebaut, im
   Erzeugnis mit einem Probeverweis nachsehen, der nicht eingecheckt wird).

Prüfen: Kerntests für alles, was ohne Erzeuger prüfbar ist, Tests mit
Marker `rendered` für die erzeugten Dateien. Den Erzeuger nur in einem
Wegwerf-Arbeitsbaum fahren, mit Schrittbildern aus einem Probelauf von
`make_guides.py` (`--ziel`) in allen sechs Sprachordnern; danach dort
`-m "rendered and not windowed"` von `test_manual` und `test_guides`,
den Wegwerfbaum wieder entfernen. Nicht anfassen: die Texte der Seiten,
`manual.OUTLINE`, `app/ui/`, Anleitungen.
