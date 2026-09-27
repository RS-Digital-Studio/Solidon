# Konzept — Ein Handbuch, das man ohne Ausprobieren versteht

> **Stand:** 27.09.2026. Arbeitsbaum `F:\3D Druck.handbuch`, Zweig
> `handbuch-umbau`, Registerpunkt [RM-283](../ROADMAP.md#rm-283).
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

- **Ort:** Gearbeitet wird im Arbeitsbaum `F:\3D Druck.handbuch` auf dem
  Zweig `handbuch-umbau`, nicht im Hauptbaum. Der Hauptbaum bereitet
  gleichzeitig das Release 0.5.1 vor, und ein halb umgebautes Handbuch darf
  nicht in dessen Erzeugerlauf geraten. Fehlt der Arbeitsbaum auf einer
  Maschine: `git worktree add "F:/3D Druck.handbuch" handbuch-umbau`.
- **Zusammenführen:** `main` wird per Merge hereingeholt, nie per Rebase. Der
  Zweig geht nach `main`, wenn HB-1 bis HB-4 zusammen stehen und Robert es
  freigibt, frühestens nach dem Tag v0.5.1. Vorher nicht: Eine Anleitung ohne
  Aufnahmeweg bliebe beim nächsten Release ohne Bilder.
- **Tests im Arbeitsbaum:** `cd "F:\3D Druck.handbuch"` und dann
  `& "F:\3D Druck\.venv\Scripts\python.exe" -m pytest …`. Mit `-m` steht das
  Arbeitsverzeichnis vorn im Suchpfad. Ein Skript außerhalb von pytest setzt
  selbst `sys.path.insert(0, r"F:\3D Druck.handbuch")`, sonst lädt es die
  editierbar installierte `app` aus dem Hauptbaum.
- **Bilder während der Entwicklung:** Das Aufnahmewerkzeug schreibt mit
  `--ziel <ordner>` in einen Ordner außerhalb des Baums. In
  `app/images/manual/` schreibt es nur beim Release (§6).
- **Commit:** je abgeschlossenem Paket, mit Push des Zweigs (der
  `post-commit`-Hook pusht den aktuellen Zweig).
- **Probelauf einer Anleitung**, eine Sprache, in einen fremden Ordner, auf
  dem zweiten Monitor:
  `& "F:\3D Druck\.venv\Scripts\python.exe" tools/make_guides.py de --nur <anleitung> --ziel <ordner> --schirm 1`.
  Das Werkzeug öffnet ein echtes Fenster; die Bilder danach ansehen, erst
  dann gilt ein Schritt als gebaut.

### Stand und nächster Schritt

Diese Liste wird nach jedem Schritt fortgeschrieben, damit eine Sitzung, die
am Nutzungslimit endet, keine Arbeit mitnimmt (Robert, 27.09.2026).

- **Committet und gepusht:** HB-0 (`daadc88fe`), HB-1 (`54e83a72e`), HB-2
  und HB-3 (`0f28f4368`), die toten PDF-Verweise aus HB-10 (`6af8fb5c7`),
  HB-13 — der Ort je Operation in der Referenz, `**Ort:** <menu_path>` an
  allen 142 Einträgen (Commit „Die Referenz sagt jetzt bei jeder Operation,
  wo man sie findet").
- **HB-4, erste Hälfte gebaut:** *Ein Modell prüfen und drucken*
  (`print-a-model`, sechs Schritte) — Anleitung, Ziele `report.slicer` und
  `print.*`, Geschichte an `tests/data/meshes/broken_open.stl`,
  Übersetzungen; am Fenster auf Deutsch aufgenommen und angesehen. Der
  Probelauf hat einen Satz des Entwurfs widerlegt: Solidon repariert beim
  Einlesen selbst, unter einem Befund stehen *Stelle zeigen* und *Offen
  lassen*, kein Knopf „beheben".
- **Als Nächstes:** *Ein Loch bohren* (`drill-a-hole`) — Sätze, Ziele,
  Geschichte und Übersetzungen als Entwurf in
  `nachweise-handbuch-2026-09/entwurf-hb4.md`, dort auch, was am Fenster zu
  prüfen ist. Danach *Das erste eigene Teil* und *Ein Gehäuse mit Deckel*
  (Vorlage: `story_housing` in `tools/make_longform_video.py`).

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
  Verlauf: `history.last` (der letzte Schritt).

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

**Ausschnitt.** Ein Schritt zeigt, was er braucht: den Umkreis seiner Ziele
mit genug Rand, damit der Kunde erkennt, wo im Fenster er ist. *Das Fenster
auf einen Blick* zeigt das ganze Fenster.

**Format und Größe.** Die Bilder reisen mit der Anwendung, und bei rund
sechzig Schritten in sechs Sprachen zählt jedes Kilobyte. Ziel ist ein Budget
von höchstens 15 MB für alle Anleitungsbilder aller Sprachen zusammen; das
Format (WebP, falls das Qt-Bildformat im Paket liegt, sonst verkleinertes PNG)
wird beim Bau von HB-3 gemessen und festgelegt.

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
- **Suche mit Rangfolge:** Titel vor Kurzfassung vor Text, Anleitungen vor
  Referenz, mit Fundstelle. Dazu ein kleines Wörterbuch der Kundenwörter
  („abrunden" findet *Verrunden*, „größer machen" findet *Skalieren*,
  „zweifarbig" findet *Zweifarbendruck*). Gemessen wird mit den 38 Suchen aus
  `nachweise-handbuch-2026-09/findbarkeit.md`, vorher und nachher. Ausgang:
  50 Prozent unter den ersten drei, 29 Prozent auf Platz eins, 11 Prozent
  ohne Treffer.
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
| HB-3 | `tools/make_guides.py`: Geschichten, Markierung, Ausschnitt, Format, Kindprozess je Sprache, `--ziel`, `--nur`, Stempel; Schritt in `/erzeugen` | Ein Lauf in einer Sprache in einen fremden Ordner; Bildbudget gemessen; Fehler bei fehlendem Ziel belegt | [~] Werkzeug gebaut: Rahmen, Nummern, Pfeile, Abdunkeln, Rand, Ausschnitt, WebP (Übersichtsbild 82 KB statt 408 KB als PNG), Kindprozess je Sprache, Stempel. Deutsch in einen fremden Ordner gelaufen; ein fehlendes Ziel beendet den Lauf mit Exit 1 und nennt Anleitung und Schritt. **Offen:** der Schritt in `/erzeugen` — der Skill wird auf `main` gerade umgebaut, der Schritt kommt mit dem Merge; das Bildbudget, gemessen, sobald HB-4 steht |
| HB-4 | Erste Anleitungen: *Das Fenster auf einen Blick*, *Ein Modell prüfen und drucken*, *Ein Loch in ein heruntergeladenes Modell*, *Das erste eigene Teil* | Bilder in einer Sprache gesichtet; Texte in sechs Sprachen | [~] *Das Fenster auf einen Blick* und *Ein Modell prüfen und drucken* gebaut und auf Deutsch gesichtet; *Ein Loch bohren* und *Das erste eigene Teil* offen |
| HB-5 | Gliederung im Handbuchfenster, „Wo fange ich an?", Verweise `manual:`, Hilfe-Menü, Startbildschirmknopf | Fenstertests (Release), Kerntests für Reihenfolge und Verweise | [ ] |
| HB-6 | Suche mit Rangfolge, Fundstelle, Kundenwörtern | Anteil der Suchen mit richtiger Seite unter den ersten drei, vorher und nachher gemessen | [ ] |
| HB-7 | F1 im Zusammenhang | Fenstertest (Release) | [ ] |
| HB-8 | Weitere Anleitungen (Liste in §4) | je Anleitung wie HB-4 | [ ] |
| HB-9 | Erklärseiten kürzen und neu übersetzen | Wortzahl der Erklärseiten um mindestens ein Drittel kleiner, kein Wissen verloren (verschoben in Anleitungen oder Referenz) | [ ] |
| HB-10 | Website und PDF nach Teilen gegliedert, Referenz am Ende; PDF mit Lesezeichen und **ohne tote Verweise auf den Bau-Rechner** | Seiten erzeugt beim Release, Tests `rendered` grün, im PDF kein Verweis mit `file:` | [~] Die Verweise um die Bildschirmfotos fallen vor dem Druck weg; `test_the_pdf_links_nowhere_outside_itself_but_the_website` hält es beim Release. Offen: Gliederung, Lesezeichen |
| HB-11 | Wächter für Menüwege im Text (§6) | Test in der Suite | [ ] |
| HB-12 | Video-Tutorial aus denselben Geschichten (die Zusage an den Kunden) | erst, wenn HB-4 und HB-8 stehen und die Bedienung ruhiger ist | [ ] |
| HB-13 | Die Referenz nennt je Operation ihren Weg in der Oberfläche (Menü oder Auswahlfenster), erzeugt aus dem Menüaufbau | Kerntest: jede Operation mit Weg; heute 2 von 142 | [x] 142 von 142 aus `registry.menu_path`; `test_every_operation_names_where_it_is_found`. Die Website zeigt es nach dem nächsten Handbuchlauf |

## §10 Risiken und offene Entscheidungen

- **Die Bedienung ändert sich weiter.** Jede Änderung an einem Weg, den eine
  Anleitung geht, zeigt sich beim Release als roter Lauf. Das ist gewollt:
  Es ist der Nachweis, dass das Handbuch stimmt. Der Preis ist Pflegearbeit
  am Release, und die ist kleiner als ein Handbuch, das still veraltet.
- **Paketgröße.** Das Budget aus §5.3 wird gemessen, bevor die Zahl der
  Anleitungen wächst.
- **Sechs Sprachen.** Jeder neue Satz braucht fünf Übersetzungen, bevor er
  eingecheckt werden kann (`pre-commit`).
- **Fenstertests nur beim Release.** HB-2, HB-5 und HB-7 sind erst beim
  nächsten Release-Tor vollständig abgenommen.
- **Beispielprojekte und Touren** bleiben vorerst unberührt (Robert,
  27.09.2026: „die beispielprojekte erstmal ignorieren", gesagt zu einer
  Kundenmail). Die Anleitungen hängen nicht an ihnen.
- **Zu entscheiden (Robert):** ob *Die Werkzeuge der Fernsteuerung* ganz aus
  dem Kundenhandbuch in eine eigene Seite für Entwickler wandert. Heute ist
  sie bei 30 von 38 Kundensuchen ein Treffer, wiederholt 142
  Operationsbeschreibungen und widerspricht der Seite *Fernsteuerung*.
  Mindestens die Suche soll sie nachrangig behandeln (HB-6); der Widerspruch
  zur Seite *Fernsteuerung* wird in jedem Fall aufgelöst.

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
