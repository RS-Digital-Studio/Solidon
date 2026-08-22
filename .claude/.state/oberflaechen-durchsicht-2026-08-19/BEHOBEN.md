# Behoben — mit Beleg und Gegenprobe

Jede Zeile hier ist ein Fund, der behoben und mit einem Test festgenagelt ist.
Wo eine **Gegenprobe** steht, wurde der Fix versuchsweise wieder entfernt und
geprüft, dass der neue Test dann rot wird — ein Test, der auch ohne den Fix
besteht, beweist nichts. Diese Prüfung hat unterwegs zweimal etwas gefunden:
einmal traf mein Einzeiler die falsche von drei gleichen Codestellen, einmal
war der Testfall so gebaut, dass er den Fehler nicht auslöste.

| # | Fund | Beleg vorher | Nachher |
|---|---|---|---|
| 1 | Raster der Zeichenfläche unsichtbar | Kontrast **1,02** (dunkel), 3,55 (hell) — `palette.mid()` war ungesetzt, Qts Vorgabe `#282828` in beiden Themen | **1,60/2,59** dunkel, **1,35/2,00** hell, scharfe Einzelpixel-Linien |
| 2 | Gesperrter Regler trug den Akzent | **404** bernsteinartige Punkte gesperrt | **0** |
| 3 | Gesperrter Fortschrittsbalken ebenso | **2998** (dunkel) / **3001** (hell) | **0** — Stylesheet, nicht Palette: ein Stylesheet gewinnt gegen sie |
| 4 | „0" der Plattenskala lag in der Ecke, Zahlen ohne Vorzeichen | „0" bei x = -110, „100" zehn Millimeter daneben; dieselbe „100" zweimal im Bild | je Kante eine Skala -100 … 0 … 100 |
| 5 | Kamera passte ohne Luft ein | 40er Quader berührte links und rechts den Bildrand | 12 % Luft je Achse; leere Szene passt auf den Bauraum, nicht auf „alle Aktoren" |
| 6 | Vier Werkzeuge öffneten untätig | Schnitt „Kein Schnitt", Messen „Nicht messen", Bewegen ohne Griff — während der Hinweis zum Klicken aufforderte | `Tool.start`: Schnitt → Z, Messen → Abstand, Bewegen → Gizmo an |
| 7 | Tour kürzte vier von fünf Schritten | „Öffnen Sie den letzten Schritt ‚Bohrung setze…", darunter 150 Punkte leer | alle Schritte brechen um, der Bereich rollt |
| 8 | „2 × Teile" | Malzeichen vor einem Plural | „2 Teile" |
| 9 | Handbuchbild mit 200 Punkten Totraum | `DIALOG = (520, 460)` erzwungen; echt sind 143–427 | `fit_height=True` |
| 10 | Qts Sprachkataloge fehlten im Paket | nicht in `datas` — im Bau hätte auf jedem zweiten Dialog „Cancel" gestanden | sechs `qtbase_*.qm`, Sprachen aus dem Katalogverzeichnis, `de` dazu, mit Varianten (`pt` liegt nur als `pt_BR`) |
| 11 | „Abbrechen" stand als **Ratschlag** im Text jedes Fehlerdialogs | jede Ausnahme führt `CANCEL`, keine hat einen Handler → `unhandled_advice` schrieb es hin, über dem Abbrechen-Knopf | ausgenommen. **Gegenprobe bestanden** |
| 12 | Anordnen meldete „Zwei Objekte überschneiden sich — 0 · 1" | `named_for` fehlte, und die Indizes waren je Platte gefiltert — die „1" der zweiten Platte ist nicht das zweite Objekt | Namen. **Gegenprobe bestanden** |
| 13 | `export` schrieb aus einer angehaltenen Kette und meldete Erfolg | belegt: `projekt_cube_clean.stl` entstand, Rückgabe 0 | Abbruch mit Bericht und Rückgabe 1. **Gegenprobe bestanden** (an der richtigen von drei gleichen Codestellen) |
| 14 | Prozentzahl im Fortschrittsbalken unlesbar | **1,69** Kontrast auf der Füllung; bei 45 % lag sie halb auf der Kante | Zahl aus dem Balken, Prozentwert in die Zeile daneben |
| 15 | Hauptknopf gab im dunklen Thema nicht nach | `accent_line` **ist** dort `highlight` — gedrückt = losgelassen | eigene Farbe `highlight_pressed` (#c37210): 1,78 Unterschied, dunkle Schrift 4,47 |
| 16 | Fehlertitel log in ~95 % der Fälle | „Ein Wert liegt außerhalb des zulässigen Bereichs." über „Diese Datei ist keine STEP-Datei."; von ~170 Stellen betreffen **acht** eine Spanne | Titel folgt der Beschränkung. Drei Klassen waren aus genau diesem Grund einzeln entstanden |
| 17 | Operationsdialog ragte aus dem Viewport | gerechnet mit `sizeHint` (249–318), gezeigt wird die Mindestbreite 380 → 62–131 Punkte über die Kante | Rechnung mit der Breite, die er wirklich bekommt |
| 18 | Befehlspalette zeigte 7 von 85 Einträgen | nur `setMinimumWidth` gesetzt; ohne Höhe nimmt das Layout 248 Punkte | `setMinimumSize(520, 480)` |
| 19 | Symbol des offenen Werkzeugs blieb hell auf Bernstein | **1,58** Kontrast, während die Beschriftung daneben dunkel war — zwei Zeichen derselben Aussage in Gegenfarben | umgefärbt beim Öffnen, zurück beim Schließen. **Gegenprobe bestanden** |
| 20 | Symbol in der markierten Zeile einer Liste ebenso | `QIcon.Mode.Selected` fiel auf `windowText()` durch | `_tone` nimmt dort `highlightedText` |
| 21 | **Escape war im Skizzenmodus tot** | zwei Kürzel auf derselben Taste; Qt meldete `activatedAmbiguously` und führte **keines** aus — gemessen: null Ausführungen, Skizze blieb offen | ein Besitzer, zweistufig: erst Werkzeug ablegen, dann Skizze verlassen. **Gegenprobe bestanden** |
| 22 | **Zwei Tastendrücke zerstörten das Vorzeigebeispiel** | `dose-mit-deckel.p3d` trug `create_lid` und `arrange_bed` unter Kennung 6; Strg+Z nahm beide, Strg+Y brachte einen — Deckel weg, `complete=False`, nie wieder da | alle neun Beispiele neu erzeugt (Kennungen 1–7), Wächtertest über jedes mitgelieferte Projekt |
| 23 | Kontextmenü bot am Netz-Körper die B-Rep-Operationen anklickbar an | Dialog ausfüllen, dann Absage — die Sackgasse, die die Menüleiste zwei Dateien weiter vermeidet | ausgegraut mit Grund; der Satz steht in `labels.py`, beide Menüs nehmen ihn von dort |
| 24 | Ein Befund sagte nicht, aus welchem Schritt er kommt | nach Schwere sortiert lesen sich „nicht geschlossen" und „Stelle geschlossen und fort" als Widerspruch; `op_id` war da, wurde nie gezeigt | Schritt und Transaktionstitel im Tooltip. **Gegenprobe fand den Test zu schwach** — „2" steckt auch in „2,40 mm" |

## Neue Tests

`test_the_drawing_grid_is_visible_without_shouting` ·
`test_the_grid_reaches_the_canvas_through_the_palette` ·
`test_a_locked_surface_loses_the_accent_too` ·
`test_a_locked_progress_bar_gives_up_the_accent` ·
`test_the_primary_button_gives_way_when_pressed` ·
`test_no_progress_bar_prints_its_number_over_the_moving_edge` ·
`test_the_bed_scale_signs_its_numbers_and_puts_zero_in_the_middle` ·
`test_what_is_fitted_gets_air_around_it` ·
`test_closing_is_no_advice_either` ·
`test_arranging_names_the_bodies_it_finds_touching` ·
`test_export_refuses_a_halted_chain` ·
`test_the_title_follows_the_constraint_not_the_class` ·
`test_the_package_carries_qts_own_catalogues` ·
`test_qt_has_a_catalogue_for_every_language_we_offer` ·
`test_the_open_tool_keeps_its_symbol_readable` ·
`test_the_palette_opens_big_enough_to_be_a_list` ·
`test_escape_has_exactly_one_owner_in_the_sketch_mode` ·
`test_no_example_ships_a_duplicate_operation_id` ·
`test_the_context_menu_greys_out_what_this_body_cannot_do` ·
`test_a_finding_says_which_step_reported_it` — dazu erweitert:
`test_the_dialog_keeps_out_of_the_middle_of_the_view`.

Vier davon vergleichen **gerenderte Bilder** statt Zahlen im Stylesheet, weil
genau dort die Lücke lag: Dass eine Regel dasteht, heißt nicht, dass sie etwas
ändert (Fund 15), und eine korrekte Palette hilft nicht gegen ein Stylesheet
darüber (Fund 3).

## Angepasste Tests

* `test_fitting_tells_pyvista_that_it_is_done`, `test_an_empty_scene_still_fits_on_something`,
  `test_a_new_project_puts_the_build_volume_in_the_picture` — sie prüften den
  alten Mechanismus (`bounds=None` heißt „pyvista passt auf alle Aktoren ein"),
  und genau der war der Fund.
* `test_the_bed_carries_numbers_not_just_lines` und
  `test_a_small_bed_still_gets_a_scale` — die alte Zusicherung hielt den Fehler
  fest: „der Nullpunkt gehört beiden Kanten, steht aber einmal da".

## Ein neuer Text in fünf Katalogen

„Nichts geschrieben — die Kette hält an. Der Grund steht oben; nach der
Behebung schreibt derselbe Aufruf die Dateien." — en, es, fr, it, pt.
Je eine Zeile, keine Umsortierung.


## Gefallen — Funde, die der Nachprüfung nicht standhielten

* **„Im Objektbaum bekommt die Namensspalte nur die halbe Breite"** —
  `panels.py:308` setzt Spalte 0 auf `Stretch` und Spalte 1 auf
  `ResizeToContents`, mit einem Kommentar, der genau diesen Fehler als behoben
  beschreibt.
* **„Pos1 im Skizzeneditor tut nichts"** — genau ein Kürzel, Kontext
  `WidgetWithChildrenShortcut`, und der Fokus liegt nach dem Öffnen der Skizze
  auf der Zeichenfläche (`StrongFocus`, nachgemessen). `fit_view` wirkt.
  Gegenprobe: im Skizzenmodus ist **keine** Taste doppelt belegt, seit Escape
  einen Besitzer hat.

Dazu die zwei aus `befunde/eigene-funde.md`: das rote „Bild" (Subpixel-Fransen)
und das fehlende Menü *Erzeugen* (mein Skript füllte das Register nicht).

## Was der Nachprüfung noch aussteht

Aus den 233 eindeutigen Rohfunden sind 43 als „hoch" gemeldet; 21 davon sind
oben behoben, 2 gefallen. Die übrigen stehen in
`durchsicht-teilergebnisse.json`. Die schwersten, die einen Erstnutzer treffen:

* Das Beispielprojekt `dose-mit-deckel.p3d` soll doppelte Kennungen tragen —
  ein Strg+Z lösche den Deckel unwiederbringlich. **Wenn das stimmt, ist es der
  wichtigste offene Punkt**, denn es ist das Vorzeigebeispiel.
* Der Deckel desselben Beispiels passe nicht (0,90 mm Spiel, Warnung im
  Bericht).
* `weg3-generiert-aufbereiten.p3d` begrüße mit „10 116 offene Kanten".
* Das erste Objekt, das ein Demonutzer sieht, heißt `plate_holes`.
* Die letzte Zeile der ersten Tour verspreche Reparaturbefunde, die es nicht
  gibt.
* Am Netz-Körper biete das Kontextmenü die sieben Operationen des exakten Kerns
  anklickbar an, während das Menü sie ausgraut (Regel 19).
* Die Kommandozeile könne STEP, SVG und DXF nicht, behaupte aber, das Format
  sei unlesbar; und zwei Fehlerwege endeten im Stapelabzug.

## Der CI-Blocker: gemessen, nicht geraten

Der Paketjob der CI hängt an `needs: suite`, und die Linux-Läufe fallen mit
einem Segmentierungsfehler. Die Suite gibt jeder **Fensterdatei** einen eigenen
Prozess, weil der Absturz an der Zahl der VTK-Fenster je Prozess hängt — gesucht
werden sie mit `grep -l "MainWindow" tests/test_*.py`
(`.github/workflows/build.yml:124`).

**Zwei Dateien bauen ein VTK-Fenster, ohne `MainWindow` zu erwähnen**, und
laufen deshalb im großen Stapel mit:

| Datei | Viewport-Aufbauten | Tests |
|---|---|---|
| `tests/test_cursors.py` | 8 | 18 |
| `tests/test_plates.py` | 1 | 14 |

Neun Fenster mehr im Stapel, ohne dass jemand es sieht. Die breitere Suche
`grep -lE "MainWindow|Viewport|pyvista"` fängt neun zusätzliche Dateien, aber
sieben davon **erwähnen** die Namen nur (Importe, Kommentare, die Lizenzliste in
`test_licences.py`). Genau ist `grep -lE "MainWindow|Viewport\("`: 16 statt 14
Dateien, und die zwei dazu sind die zwei, die wirklich bauen.

**Und derselbe Absturz ist hier lokal reproduziert.** Der vollständige Lauf in
*einem* Prozess brach bei 5 % mit einer Zugriffsverletzung ab — im
`window`-Fixture von `test_analysis_ui.py`, in `session.py:111`
(`QThread.__init__`), Exit 139. Dieselbe Datei allein: dreimal grün, 103 Tests.
Die Kette der sechs Dateien bis dorthin: grün, 298 Tests. Es ist die Zahl der
Fenster, nichts an einem einzelnen Test.

Nebenbei eine Falle im eigenen Vorgehen: `pytest … | tail` gibt den Exit-Code
von `tail` zurück, nicht den von pytest. Ein abgestürzter Lauf sah damit aus wie
ein bestandener — der erste Batch-2-Lauf meldete „exited with code 0" und hatte
einen faulthandler-Abzug in der Ausgabe. Das Prüfwerkzeug des Projekts
(`.claude/skills/pruefen`) ruft die vier Läufe direkt auf und hat die Falle
nicht.

## Gemessene Flatterhaftigkeit von `tests/test_ui.py`

Die Datei stürzt gelegentlich mit einer Zugriffsverletzung ab — allein, ohne
andere Dateien im Prozess. Gemessen am 20.08.2026:

| Zustand | Läufe | Abstürze |
|---|---|---|
| mit den drei neuen `start=`-Rückrufen | 7 | 1 |
| ohne sie | 3 | 0 |

Der Verdacht lag nahe: *Bewegen* schaltet beim Öffnen den Gizmo ein, und die
Oberflächenregel warnt bei pyvistas `AffineWidget3D` ausdrücklich vor dem
„Absturz ohne Zeile am Ende eines Laufs". Bei dieser Rate ist der Unterschied
zwischen 1 von 7 und 0 von 3 aber nicht messbar — **die Unschuld der Änderung
ist damit nicht bewiesen, nur ihre Schuld nicht belegt.** Wer das entscheiden
will, braucht dreißig Läufe je Zustand, nicht sieben.

Was dagegen steht: 217 Tests, und der Absturz wandert (vorher in
`test_analysis_ui.py`, in `QThread.__init__`). Genau das beschreibt der
CI-Kommentar seit dem 12.08.2026 — die Zahl der VTK-Fenster je Prozess. Auf
POSIX fängt die CI es zusätzlich mit `--forked` je Test; auf Windows gibt es
kein `fork`, und deshalb sieht man es hier.


---

## Zweite Runde, 20.08.2026 — ohne Workflow, Fund für Fund am Code

| # | Fund | Beleg vorher | Nachher |
|---|---|---|---|
| 34 | Palette und Kontextmenü sortierten nach dem internen englischen Bezeichner | „An Merkmal ausrichten", „Textur aufbringen", „Auf dem Bett anordnen", „Slot zuweisen" — während die Menüleiste daneben nach Titel sortiert | alle drei Wege über `i18n.sort_key`. **Gegenprobe bestanden**, in zwei Stufen: nach Namen sortiert rot, nach Titel *ungefaltet* rot („Überhangfächer" hinter Z) |
| 35 | Der Fehlerbericht nannte den Ablageort und schloss sich im selben Augenblick | `_write` schrieb den Pfad in die Vorschau, die nächste Zeile war `accept()`; beide Aufrufer werfen `written` weg. Der Modul-Docstring versprach obendrein, der Ordner werde geöffnet | Pfad in eigener, auswählbarer Zeile, Knopf „Ordner öffnen", Ablegen-Knopf danach fertig. **Gegenprobe bestanden** |
| 36 | Erststart nahm eine andere Sprache stumm an | der Einstellungsdialog sagt es seit je mit einem Satz, der in allen fünf Katalogen steht — an der Stelle, an der die Sprache zum ersten Mal gewählt wird, stand er nicht | derselbe Satz, derselbe Auslöser. **Gegenprobe bestanden** |
| 37 | Zehn Zeilen des Objektbaums lagen außerhalb der Karte | Baum 500 Pixel in einem Abschnitt von 121; Rollbalken meldete max=2, am Ende blieben zehn Zeilen unerreichbar — darunter der zweite Körper. Zwei Ursachen: 221 Pixel Beiwerk nicht abgezogen, und die anteilige Verteilung kannte die Böden der Karten nicht | `extra_height` + `RoomTaker.least_height`. Nachher: Baum 276 in 299, unterster Inhalt bei 604 in einer 609 hohen Zone, Rollbalken 19 statt 10 |
| 38 | Bemalen war im Bild folgenlos | `paint_slot` legt einen Slot mit `colour=None` an, die Ansicht nahm dafür die Körperfarbe → zwei bemalte Slots, zwei gleiche Farbtabelleneinträge. Dieselbe Lücke bei der Schrift und bei „Slot zuweisen" mit leerem Feld — drei von vier Stellen | `theme.SLOT_COLOURS` (Okabe/Ito, sieben Einträge, Slot 0 ohne). **Gegenprobe bestanden** |
| 39 | Die Pinselleiste nannte nur eine Nummer | „Slot 1" sagt nicht, was auf dem Teil landet; welche Farbe herauskam, erfuhr man durch Malen | Farbfeld **und** Name, „neu" für einen unbekannten Slot, „unbemalt" für Slot 0. **Gegenprobe bestanden** |
| 40 | `BaseParams.fields()` warf bei einer parameterlosen Operation | *Objekt löschen* hat keine Parameter, ihr Satz ist `BaseParams` selbst; `dataclasses.fields` wirft dort ein nacktes TypeError — kein `AppError`, kein Handlungsvorschlag | leere Liste. Test über das ganze Register. **Gegenprobe bestanden** |

Commits: `b3fd8e3`, `cadcacc`, `ba1e455`, `e1186ac` — und die Änderungen an
`viewport.py` und `main_window.py` zu Fund 38/39 liegen in `34a6b34`, dem
Commit der **parallelen Sitzung**: Sie hat sie mit eingesammelt, wie ich
vorher ihre. Nichts ist verloren, aber die Historie erzählt es anders. Zwei
Sitzungen in einem Arbeitsbaum sind der Grund; der Auftragstext für die zweite
Sitzung verlangt deshalb jetzt einen eigenen `git worktree`.

| # | Fund | Beleg vorher | Nachher |
|---|---|---|---|
| 41 | Bausteinkatalog zeigte 4 Kacheln von 19 | `resize(980, 640)` auf jedem Bildschirm; Rasterfläche 718x562 = vier je Zeile, zweieinhalb Zeilen, Rollbalken 1240 Pixel Weg. Die Kachel ist **nicht** der Grund: 164 breit wegen des Textes, 190 hoch wegen Bild plus vier Textzeilen | vier Fünftel des freien Bildschirms, 980x640 bis 1560x1000. Auf 1920x1080: sieben je Zeile, vier Zeilen. **Gegenprobe bestanden** |
| 42 | Bedingungsliste sprach in Punktindizes | „Deckung  (1, 2)" — die flache Nummerierung der Skizze | „Deckung — Linie 1 Ende, Linie 2 Anfang"; ein ganzes Element wird einmal genannt; Zahlen im Tooltip. **Gegenprobe bestanden** |
| 43 | Maße ohne Einheit | „Abstand 30,00", „Referenzmaß (4,00)" — seit die Anzeigeeinheit umschaltbar ist, eine Vermutung | mit Einheit; zwei bestehende Erwartungen mit Begründung nachgezogen |
| 44 | Prüfbericht ohne Befunde zeigte Suchfeld, Filter und leeren Kasten | drei Bedienelemente für nichts, dazwischen der Satz „Keine Befunde." | Filterzeile ab zwei Befunden, Liste nur wenn gefüllt; ein verschwindender Filter nimmt seine Wirkung mit. *(im Baum, noch nicht committet — `panels.py` liegt bei der parallelen Sitzung)* |

Commits: `3923e48` (41–43). Fund 44 wartet, weil `app/ui/panels.py` gerade von
der parallelen Sitzung bearbeitet wird — sie baut `DEPENDENT_FIELDS` ins
Parameterschema (`depends_on`), und dabei standen `types.py` und `params.py`
zeitweise auseinander: die Suite war fremd-rot, `ParamSpec.__init__() got an
unexpected keyword argument 'depends_on'`. Nicht mein Fehler und nicht meine
Datei — abgewartet statt darauf committet.

| # | Fund | Beleg vorher | Nachher |
|---|---|---|---|
| 45 | Ladebildschirm stand im Systemgrau und sprang mitten im Laden | Palette #efefef bis `build_application`, danach #343a45; dazwischen `load_operations` (2,73 s gemessen). Der erste Eindruck der Demo | `apply_theme` direkt hinter `load_settings`, vor allem, was ein Fenster ist — deckt den Abschiedsdialog einer abgelaufenen Demo mit ab. **Gegenprobe bestanden** |

**Achtung, Historie:** Fund 45 (`app/ui/app.py`, `tests/test_ui.py`) liegt in
`b85364d` — dem Commit der **parallelen Sitzung** („Zwei Sekunden schwarzer
Bildschirm vor dem Ladebildschirm"). Sie hat ihn mitgenommen, während ich ihn
committen wollte; ihr Text betrifft dieselbe Stelle, erklärt aber den Farbsprung
nicht. Das ist der **dritte** Fall dieser Art an einem Tag (vorher `34a6b34`
mit den Slotfarben, und ich selbst mit `051c4cb`). Zwei Sitzungen in einem
Arbeitsbaum tun das zuverlässig; der einzige Ausweg ist `git worktree` oder
nacheinander arbeiten.

| # | Fund | Beleg vorher | Nachher |
|---|---|---|---|
| 46 | Kürzelübersicht kannte 13 Tasten nicht | 36 Menütasten gegen 49 belegte; es fehlten `Alt+1`…`Alt+8`, `Strg+Tab`, `Strg+Umschalt+Tab`, beide Zoom-Tasten und `Esc` — ausgerechnet die acht, die ein Kommentar in `main_window` dort verortet | drei Quellen (Menüleiste, Werkzeugzeile, `WINDOW_KEYS`), 49 Zeilen, **kein** Fenster-Kürzel fehlt. Der neue Test hält sie gegen die `QShortcut`-Kinder des Fensters. **Gegenprobe bestanden** |
| 47 | Gruppen nach Bytes sortiert | „Ändern" hinter allem anderen („Ä" liegt hinter „z"), innerhalb der Gruppe Alphabet statt Menüreihenfolge — die Reihe 1…6 war verstreut | `sorted()` weg, Sammelreihenfolge = Menüreihenfolge; doppelte Gruppe („Ansicht" ist Menü **und** Werkzeugzeile) wird zusammengefasst |
| 48 | Gruppen mit vier Leerzeichen eingerückt statt als Baum | für einen Vorleser eine flache Liste, in der die Gruppe nirgends steht | echte Kinder, `setRootIsDecorated(True)`, aufgeklappt |
| 49 | Kürzelübersicht ohne Suchfeld | 49 Zeilen; Qts Tipp-Suche springt nur auf Zeilenanfänge der ersten Spalte, wer nach einer Taste sucht findet nichts | Suchfeld über Befehl **und** Taste; eine leer gefilterte Gruppe geht mit |
| 50 | Objektbaum: Name und Maß je genau die Hälfte | `stretchLastSection` (Qt-Vorgabe True) überstimmt `ResizeToContents`; 128/128 bei 258 px, beide Körper des ersten Beispiels als derselbe abgeschnittene Text | Verhältnis statt Vorrang: Maß höchstens zwei Fünftel. 258 px → 154/102, 420 → 251/167, 700 → 512/186. **Gegenprobe in beide Richtungen** — auch der Vorschlag des Funds („nur stretchLastSection abschalten") ist rot, bei 70 gegen 186 |

Commits: `51abfc4` (46–49), `c6046d1` (50).

| # | Fund | Beleg vorher | Nachher |
|---|---|---|---|
| 51 | Variantendialog rechnete bis zu zwölf Auswertungen im Qt-Hauptthread | kein Fortschritt, kein Abbrechen, stehendes Fenster — drei Zusagen aus §2.8 verletzt | `variants.build` nimmt `progress`/`cancelled` durch, Dialog rechnet im `QThread`, Abbrechen hält an statt zu schließen, Ordner wird vorher gefragt. **Drei Gegenproben** |

Commit: `735ad01`.

**Und eine Lehre, die in die Testregel gehört:** Die erste Fassung von
`tests/test_variants_ui.py` rief `_stop_or_close` von Hand und baute den
Arbeiter selbst. Sie blieb grün, als ich die Verbindung des Knopfes und das
`start()` zurückdrehte — sie prüfte drei Wege, die sie nie ging. Ein Test, der
über die Methode statt über den Knopf geht, prüft die Verbindung nicht; einer,
der sein Prüfobjekt selbst baut, prüft nicht, wie die Anwendung es baut.

## Dritte Runde, 20.08.2026

| # | Fund | Beleg vorher | Nachher |
|---|---|---|---|
| 52 | Palette schrieb „Del", das Menü „Entf" | 5 Operationen + 37 Fensterbefehle in englischer Rohform, gemessen mit geladenem Qt-Katalog | eine Stelle (`native_key`), 43 Zeilen, keine englisch. **Gegenprobe bestanden** |
| 53 | 60 Fensterbefehle der Palette nie ausgegraut | 5 von 60 sind bei leerem Projekt gesperrt; `trigger()` auf eine gesperrte Action ist ein Klick ins Leere. Vier davon stehen von Hand in `window_commands`, nicht in der Menüschleife | Verfügbarkeit aus derselben Quelle wie im Menü, dazu je ein Grund, der sagt was fehlt. **Zwei Gegenproben** |
| 54 | `view_chrome` las die Kopfhöhe, bevor der Kopf gelegt war | 30 statt 16 Pixel — der Objektbaum war immer 14 Pixel höher als seine zwölf Zeilen, und ein Test hielt es fest | Wunschhöhe statt aktueller Höhe; zwei Tests nachgezogen, einer davon rief `resizeColumnToContents` und überschrieb damit, was er prüfen sollte |
| 55 | Das erste Objekt der Demo hieß „plate_holes" | `load` nimmt den Dateinamen, und die Datei ist ein Testkorpus-Netz | `name` gesetzt; Test über alle neun Beispiele auf die **Form** (kein Unterstrich, keine Dateiendung). **Gegenprobe bestanden** |
| 56 | Erste Tour versprach Reparaturbefunde | Bericht: „An diesem Netz war nichts zu reparieren" — drei Hinweise, keine Warnung | Text nennt, was dasteht; Test hält Text und Kette über die Zahl zusammen. **Gegenprobe bestanden** |
| 57 | Pos1 im Skizzenmodus tot | zwei aktive Kürzel auf einer Taste, null Aufrufe von `fit_view`, zwei `activatedAmbiguously`; versprochen im Tooltip **und** im Handbuch | „Alles einpassen" gehört zu den Darstellungseinträgen und wird im Skizzenmodus gesperrt. **Gegenprobe bestanden** |
| 58 | „An Fläche" zeigte „hole_1" auf dem Hauptweg | `launch_operation` übergab keine Merkmalsliste; nur `edit_operation` tat es. Gemessen: „hole_1" gegen „Bohrung 1 · Ø5,2" | übergeben; der Test prüft die **Aufrufer**, nicht den Dialog. **Gegenprobe bestanden** |

Commits: `91f504a`, `281f6a6`, `8f76d38`, `5772fc3`, `3bf12fd`, `473d7dc`.
Bewusst offen und in `ROADMAP.md` eingetragen (`4e55172`): die nackten Tasten
außer Entf, und der Totraum im Trennen-Bereich (braucht die echte Plattform).

## Vierte Runde, 20.08.2026

| # | Fund | Beleg vorher | Nachher |
|---|---|---|---|
| 59 | Kontextmenü führte drei Gesten-Ops in einen Rohdialog | „Formen", „Stellung geben", „Tasche schneiden" haben `consumes == 1` und stehen am Körper; das Signal hing an `run_operation`, während Menü und Palette längst über `launch_operation` gehen | eine Zeile; Test über das **Signal** und über das Register, damit eine vierte Geste mitgeprüft ist. **Gegenprobe bestanden** |
| 60 | Weg-4-Tour sagte „vier Schritte" | im Verlauf stehen fünf (Quader, Kugel, Versetzen, Verschmelzen, Vernetzen), und „der dritte" meinte den fünften | Text nachgezogen; Test über **alle** Touren und ein Wörterbuch der Zahlwörter. **Gegenprobe bestanden** |
| 61 | „Eintragen" mit leerem Feld schloss den Freischaltdialog wortlos | `_remember` rief `reject()` — auf den einen Knopf hin, der etwas versprach | Knopf gesperrt mit Grund, Dialog bleibt. **Gegenprobe bestanden** |
| 62 | 26 Winkel trugen „grad", vier „°" | „Winkel [grad]" gegen „Winkel [°]" im selben Produkt; „grad" steht in keinem Katalog | `units.DEGREE_UNIT`, 30 Parameter; Test lässt nur zwei Einheiten durch. **Gegenprobe bestanden** |
| 63 | Zahlenfelder wuchsen auf die Dialogbreite | 366 px für einen Wunsch von 120, 366 für 48, 342 für 60 — die Zahl links, die Drehknöpfe 300 px weiter rechts | Deckel auf die Zahl (Wunsch + zwei Ziffern), Auswahl und Text wachsen weiter. Nachher 144 / 84 / 96. **Zwei Gegenproben** |
| 64 | Startbildschirm-Knopf öffnete das falsche Kapitel | „Handbuch — die ersten fünfzehn Minuten" landete auf „Was Solidon ist", dem ersten von über vierzig Einträgen; `show_page` gab es und rief niemand | `action_manual(page)`, Schlüssel im Handbuch; Test über den **Klick** und gegen den Knopftext. **Gegenprobe bestanden** |
| 65 | Neun gleiche Kacheln unter einer Überschrift | die Zweiteilung stand nur im Kommentar von `examples.py` | zwei Raster, „Wo fange ich an?" und „Was kann das noch?", geteilt nach `way`. **Gegenprobe bestanden** |
| 66 | Startbildschirm nutzte die Breite nicht | 1920x1080: Sichtfeld 956, Inhalt 1154, Rollbalken — und die Spalte 900 px breit in 1906 px Fenster | drei Kachelspalten ab 3 × `TILE_MIN_WIDTH`, Spalte bis 1360, Ränder von `WIDE*3` auf `WIDE*2`. Nachher: fünf Kachelzeilen → vier, Rollweg 198 → 16. **Gegenprobe bestanden** |

Commits: `01f1791`, `f54efed`, `01ab151`, `f1eb020`, `9a06d03`, und der
Startbildschirm noch im Baum.

**Offen geblieben und gemessen:** Auf 1600x900 bleiben 156 Pixel Rollweg. Der
Startbildschirm passt damit nicht überall ohne Rollen — was fehlt, ist eine
Entscheidung darüber, was kleiner wird (Kachelhöhe, Ablagefläche, Zuletzt
geöffnet), und die gehört nicht in einen Fehlerfix.

| # | Fund | Beleg vorher | Nachher |
|---|---|---|---|
| 67 | Überfahrt und Fokus auf den Kacheln in derselben Farbe | dunkles Thema: `highlight == accent_line == #f0a54a`, Unterschied ein Bildpunkt Rahmenbreite | Überfahrt wechselt die Fläche, Fokus den Rahmen. **Gegenprobe bestanden**. Die zweite Hälfte des Funds (1-Pixel-Sprung) **reproduziert nicht**: nachgemessen null Verschiebung, weil die Ränder aus dem Layout kommen und nicht aus dem `padding` |
| 68 | „Reparieren und erneut versuchen" an Fehlern ohne Reparatur | `GeometryError` erbt die Vorgabe; am zu großen Verrundungsradius (exakter Körper) und an „arbeitet nur auf Netzen" taten beide Knöpfe nichts | passende Vorschläge: Eingabe korrigieren bzw. Auswählen. Am **echten** Fehler gemessen. **Gegenprobe bestanden** |
| 69 | Zwei Wertschlüssel als rohes Englisch im Tooltip | `values["shared"] = …` und `values["detail"] = …` sind keine Literale — der Sammler sah sie nicht, und seine eigene Docstring-Zeile benannte die Lücke | Sammler sieht die Zuweisung, zwei Namen eingetragen. **Gegenprobe in beide Richtungen** |

Commits: `571422e`, `6e2f2fd`, `6b89a9d`, `630df0d`, `04913d6`.

## Der große Stapel hängt jetzt — und das ist die bekannte Grenze

`pytest tests/` ohne die fünf ausgeschlossenen Fensterdateien blieb zweimal bei
88 Prozent stehen, reproduzierbar an derselben Stelle:
`tests/test_style.py::test_an_icon_takes_its_colour_when_it_is_drawn`. Der Test
**allein** läuft in 0,16 s; jede Zweierkombination läuft durch
(`test_pose_session` + `test_style` 102 s, `test_operation_ui` + `test_style`
160 s, `test_split_tool` + `test_style` 100 s). Erst die Häufung reißt.

Das ist die Grenze, die `suite-getrennt.sh` und der CI-Workflow seit dem
12.08.2026 beschreiben: zu viele VTK-Fenster in einem Prozess. Seit dem
19.08. sind Fensterdateien dazugekommen (`test_variants_ui.py`), und damit ist
der große Stapel lokal nicht mehr die richtige Art zu messen. **Gefahren wird
ab jetzt `suite-getrennt.sh`.**
