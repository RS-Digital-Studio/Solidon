# Durchsicht der Oberfläche 0.5.2: zu viel Text, gesuchte Funktionen, Gestaltung

**05.10.2026.** Anlass ist Roberts Auftrag nach der Veröffentlichung von 0.5.2:
*„in den meisten Fällen haben wir noch zu viel Text, nicht übersichtlich, sucht
Funktionen, nicht schön gestaltet nach den Vorgaben, schau dir alles mal
gründlich an und erstellen RM-Punkte dafür“*. Ergebnis sind die Registerpunkte
RM-506 bis RM-519 in `ROADMAP.md`; umgesetzt ist nichts. Dieses Dokument hält
die Belege, die Messungen und die Zuordnung fest. Was offen ist, steht nur im
Register.

## Methode und Stand

- **Stand:** `71f13266c` auf `main`, Version 0.5.2.
- **Belege:** die 95 Bildschirmfotos je Sprache unter `app/images/manual/<sprache>/`,
  beim Release von 0.5.2 am echten Fenster aufgenommen (Hauptfenster 2560 × 1369).
  Nummern, Rahmen und Pfeile in den `guide-*`-Bildern sind Handbuchmarkierungen.
  Lange Fassungen wurden an `fr/` und `pt/` verglichen.
- **Vier nur lesende Prüfer:** A Hauptfenster und Auffindbarkeit, B Prüfbericht,
  Auswahlfenster und Maße im Bild, C Dialoge, D Kundentexte. Gezählt wurde am Bild
  von Hand (rund ±10 %), am Register mit Python und an den Texten per AST über
  alle `tr()`-, `_()`- und `site_text()`-Literale unter `app/`.
- **Codebefund** heißt: nur am Code abgeleitet, weil kein Bild den Zustand zeigt
  (Erstlauf, Befehlspalette, Einstellungen, Fehlerdialog, Filamentlager, Chat,
  Tour). **Gestaltungsentscheidung** heißt: Geschmack, nicht bewiesener Fehler.
- Nicht gemessen: echtes Fenster in HiDPI, kleine Fenster unter 1280 px, helles
  Thema. Das gehört in die Abnahme der Punkte.

## Kernzahlen

| Gegenstand | Messung |
|---|---|
| Hauptfenster (main-window.png) | rund 290 sichtbare Wörter, davon 165–175 im Prüfbericht; dort nur rund 88 Wörter Befundtext |
| Prüfbericht (report.png, 620 × 430) | Kopf 268 von 430 px (62 %), Liste 45 px: einer von vier Befunden sichtbar |
| Platz für das Modell | Karten verdecken rund 22 % der Ansicht; freie Mitte 62 % der Breite (2560 px), bei 1280 px gerechnet 22 % |
| Akzentfarbe im Ruhezustand | vier Bernsteinkanten (linke Karte, Bericht, Werkzeugzeile, Reiter) und drei Akzentflächen (Bausteine, vorgewählte Zeile, „Diesen Schritt ändern“) |
| Menüs | 5 (Datei 12, Bearbeiten 10, Erzeugen 10, Ansicht, Hilfe); 7 von 12 Kernfunktionen in keinem Menü |
| Operationen | von 178 stehen 69 nur in der Auswahlkarte, 71 nur im Bausteinkatalog; die Befehlspalette ist sichtbar nur über *Bearbeiten* erreichbar |
| Vorderseite der Operationsdialoge | 104 von 177 Operationen zeigen mehr als drei Felder gleichzeitig, 42 sechs oder mehr (Bauplan §2.4: zwei bis drei) |
| Einleitung der Operationsdialoge | Beschreibung plus Grenze Median 24 Wörter, 71 über 40, 33 über 60, höchstens 118 |
| Druckdialog (print-settings.png) | 34 Bedienelemente und 62 Wörter beim Öffnen, 1248 px hoch; 5 von 5 Gründen im Druckrat abgeschnitten |
| Kundentexte gesamt | 8 553 sichtbare Texte, Median 6 Wörter, 90 % 20; 213 über 30 Wörter, 166 mit mehr als zwei Sätzen; eine Längengrenze gibt es nur für Bildanleitungen |

### Die zwölf Kernfunktionen: heutiger kürzester Weg

Startzustand: ein Modell geladen, nichts gewählt; gezählt sind Mausklicks bis
zum Übernehmen.

| Funktion | Weg | Klicks | Problem |
|---|---|---|---|
| Bohrung | Körper → „Bohrung setzen“ → Stelle → Einsetzen | 4 | in keinem Menü; die Tour lehrt den Umweg über Bausteine |
| Verrunden | Körper → Kante → Radius, Übernehmen | 3 | dass Kanten wählbar sind, sagt niemand; in der Karte Eintrag 29 von 32 der zugeklappten Gruppe „Ändern“ |
| Teilen | Körper → „Teilen“ → Übernehmen | 3 | sieben Einträge, drei Verben, vier Orte |
| Beschriften | Körper → Fläche → „Text aufbringen“ → Stelle → Übernehmen | 5 | im Menü grau, bis eine Fläche gewählt ist |
| Gewinde | Körper → Fläche → Bausteine → „Druckbares Gewinde“ → Einfügen → Übernehmen | 6 | kein Eintrag heißt „Gewinde“; an der Bohrung fehlt der Bausteine-Knopf |
| Deckel | Körper → Öffnungsfläche → „Deckel erzeugen“ → Übernehmen | 4 | im Menü grau ohne Fläche |
| Export | Datei → Exportieren → Speichern | 3 | kein sichtbarer Knopf |
| Slicer-Übergabe | „An den Slicer übergeben …“ → Slicen | 2 | ein Dialog, drei Namen, kein Hauptknopf |
| Filament zuweisen | Körper → Schnellwähler → Spule | 3 | doppelt in der Karte; Spaltenkopf „Fila“ abgeschnitten |
| Reparieren | über Befund, offene Kante, Strg+Umschalt+R oder Palette | 2–4 | am Körper und im Menü nicht da |
| Druckoptimal ausrichten | ohne Auswahl in der Karte | 1–2 | verschwindet bei gewähltem Körper |
| Skalieren | Körper → Bewegen → Skalieren | 3 | „Auf Maß bringen“ in der zugeklappten Gruppe „Ändern“ |

### Felder vorn je Operation

| Felder vorn gleichzeitig | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| Operationen | 6 | 22 | 19 | 26 | 36 | 26 | 22 | 14 | 6 |

Acht vorn: `create_seal`, `insert_bayonet`, `insert_channel_joint`,
`insert_detent_disc`, `insert_hose_barb`, `insert_room_wall`. Sieben:
`sketch_pocket`, `apply_texture`, `sketch_loft_cut`, `insert_room_floor`,
`create_bayonet`, `create_channel_joint`, `create_detent_disc`,
`create_room_wall`, `insert_holder_shelf`, `insert_holder_u`,
`insert_pegboard_hook`, `insert_wall_mount`, `resize_hole`, `slot_hole`.
718 von 2 113 Parametern stehen vorn (34 %).

### Länge der Kundentexte nach Art

| Art (Fundort) | Anzahl | Median W | 90 % W | >2 Sätze | >30 W |
|---|---|---|---|---|---|
| Befundsätze (`Finding.message`) | 502 | 13 | 27 | 32 | 29 |
| Druckrat (`slice/advise.py`) | 45 | 16 | 26 | 4 | 3 |
| Bausteinänderung (`PartChange.effect`) | 62 | 28 | 53 | 17 | 26 |
| Fehler (`AppError`, `detail`) | 1 194 | 9 | 20 | 12 | 17 |
| `doc` von Operationen und Bausteinen | 156 | 20 | 34 | 12 | 28 |
| Vorbehalt (`caveat`) | 53 | 26 | 36 | 3 | 16 |
| Parameter-`doc` | 698 | 11 | 23 | 19 | 14 |
| Hinweise der Druckeinstellungen (`note`) | 84 | 14 | 22 | 3 | 2 |
| Tooltip und Statustipp | 152 | 9 | 16 | 1 | 1 |
| Ansagen (`announce`) | 126 | 7 | 14 | 1 | 2 |
| Startbildschirm, Erstlauf, Tour | 166 | 14 | 30 | 6 | 17 |
| Bildanleitungen (mit Wächter) | 125 | 9 | 14 | 1 | 0 |

Menü-Tooltip (`doc` plus Vorbehalt): Median 23, 90 % 64, höchstens 116 Wörter.
Übersetzungen sind in Zeichen 0,92 (en) bis 1,06 (fr) so lang wie Deutsch; eine
deutsche Grenze mit rund 10 % Zuschlag trägt alle Sprachen.

## Befunde

Je Befund: Aussage, Beleg, Vorschlag, Registerpunkt. Zeilenangaben gelten für
`71f13266c`.

### A — Hauptfenster und Auffindbarkeit

- **A1** Sieben der zwölf Kernfunktionen stehen in keinem Menü und sind ohne Auswahl unsichtbar; die Befehlspalette ist nur über *Bearbeiten* sichtbar, die Kartensuche sucht nur in der Auswahl. `registry.py:131–144` (`PANEL_CATEGORIES`), `main_window.py:4380–4395`. → RM-506
- **A2** Die Gruppen der Auswahlkarte sind mit `str.casefold` sortiert (`selection_operations.py:513`, `:525`); auf Deutsch steht „Ändern“ (32 Einträge am Körper, zugeklappt über `OPEN_UP_TO` 12) zuletzt, auf Französisch an zweiter Stelle. Verletzt `grenzen.md` (`i18n.sort_key`). → RM-506
- **A3** Für den Export gibt es keinen sichtbaren Knopf, obwohl alle vier Hauptwege damit enden (§2.2); nur *Datei → Exportieren* oder Strg+E. → RM-508
- **A4** Die Einladung der leeren Szene liegt im Zeichenmodus über der Skizze (guide-draw-and-pull-4, -6; `main_window.py:22746`). → RM-519
- **A5** „Druckoptimal ausrichten“, „Auf dem Bett anordnen“ und „Überschneidungen prüfen“ verschwinden bei gewähltem Körper; `menu_path` nennt einen Ort, an dem sie dann fehlen (`surfaces.py:627–635`). → RM-506 (Sichtbarkeit bei Auswahl: Entscheidung Robert)
- **A6** Teilen hat sieben Einträge mit drei Verben (Teilen, Trennen, Zerlegen) an vier Orten; „Automatisch teilen“ fällt ins Menü *Bearbeiten* (`main_window.py:4518–4535`). → RM-507
- **A7** An einer gewählten Bohrung fehlt der Bausteine-Knopf, obwohl fünf Bausteine `applies_to` `hole` tragen (`selection_operations.py:815`). → RM-506 (Entscheidung Robert vom 10.09.)
- **A8** Der Prüfbericht trägt im Ruhezustand rund 175 von 290 Wörtern des Fensters. → RM-508
- **A9** Rechts stehen Berichtskarte und angedocktes Auswahlfenster nebeneinander; `fenster.md` beschreibt eine Spalte, das Bild zeigt vier Zonen. → RM-511
- **A10** Weg 3 (aus Text oder Bild erzeugen) hat nur *Datei → Modell erzeugen …*; die Einladung der leeren Szene bietet weder Modell einfügen noch Generator (`viewport.py:3487–3494`). → RM-506
- **A11** Ein Druckdialog trägt drei Namen: „An den Slicer übergeben …“, „Drucken vorbereiten …“, Kopfknopf „Drucker …“ mit zugänglichem Namen „Drucker wechseln“ (`header.py:335`, `:345`, `:467`). → RM-507
- **A12** Reparieren gilt nur offenen Kanten (`geom/ops.py:985`, `applies_to=("edge_loop",)`) und fehlt am Körper. → RM-506
- **A13** Der Leertext des Merkmalfensters nennt keine Kanten (`panels.py:7869`), obwohl Verrunden, Fase und Wulst nur an der Kante stehen. → RM-506
- **A14** Im Zeichenmodus zeigt das Auswahlfenster nichts Brauchbares (sketch-mode.png), und die Bedingungsliste spricht Fachsprache („Deckung — Linie 1 Ende, Linie 2 Anfang“, mindestens neun Zeilen). → RM-519
- **A15** Unter den Parameterfeldern steht „Eine feste Zahl passt“ / „2 feste Zahlen passen“ (`panels.py:3830–3845`); der Satz liest sich wie die Überschrift der nächsten Zeile. → RM-519
- **A16** Jede Karte trägt einen Bernsteinrand (`overlay.py:339`, `accent_line`). Gestaltungsentscheidung, gegen Produktkompass §6.1. → RM-512
- **A17** Auf dem Startbildschirm sind Feedback und Spende so groß wie die vier Einstiege; der Inhalt nutzt 53 % × 47 % der Fläche in kleiner Schrift; „Modell öffnen …“/„Projekt öffnen …“ heißen anders als in der Werkzeugleiste. → RM-515
- **A18** Im Menü *Erzeugen* stehen „Aus Skizze erzeugen …“ (Knopf „Zeichnen“) und „Modell einfügen“ doppelt, drei von zehn Zeilen sind grau. → RM-507
- **A19** *Formen* und *Skelett* bleiben grau, wenn nur ein Körper da ist; der Katalog nimmt ihn längst (`main_window.py:9695`, `_lone_body`). → RM-506
- **A20** Die Filamentspalte im Objektbaum ist abgeschnitten („Fila“, `panels.py:1913`), ihre Felder wirken wie Haken. → RM-519
- **A21** Im Verlauf springt die Nummer an einer Gruppenzeile (1, 2, ▸ Gruppe, 5); „Als Dreiecksmodell rechnen“ steht im Kontextmenü an zweiter Stelle. → RM-519
- **A22** Katalogkacheln tragen zwei bis vier Textzeilen; „– nimmt Material weg“ liest sich als Minus. → RM-517

### B — Prüfbericht, Auswahlfenster, Maße im Bild

- **B1** = A2, dazu: `MENU_GROUPS` ist nach Häufigkeit geordnet (`registry.py:117–122`), die Karte liest das nicht. → RM-506
- **B2** Die empfohlenen Handlungen haben dieselbe Füllung wie Eingabefelder (`style.py:1626–1631` gegen `:1667–1668`); die Liste darunter ist eine Wand gleicher 44-px-Kacheln, je Bildschirm zwölf. → RM-510
- **B3** Im Prüfbericht bekommt die Befundliste den wenigsten Platz: 36 Wörter Gerüst über der Liste, acht Bedienelemente, Filterzeile ab zwei Befunden (`panels.py:5427`, `:5733–5772`). → RM-508
- **B4** An einer Bohrung stehen sechs Handlungen mit allen Feldern gleichzeitig offen; Inhalt 1579 px, sichtbar 877 px bei 1600 × 1000 (`perceive/actions.py:138–157`, `main_window.py:14292–14295`). → RM-510
- **B5** Die Berichtskarte schrumpft nicht: bei „Bereit zur Übergabe“ sind 46–51 % ihrer Höhe leer. Vermutete Ursache (Codebefund): `natural_height` zieht den höchsten Reiter nur bei einer Zone ab, die selbst ein `QTabWidget` ist (`overlay.py:677`). → RM-511
- **B6** Lange Befundsätze verdrängen die Liste: guide-repair-a-model-4 belegt mit 42 Wörtern fünf Listenzeilen (`advise.py:2099`). → RM-509
- **B7** Unter jedem Befund stehen Folge, Ort und Grundlage, meist ohne eigene Aussage (`print_contract.py:167–177`, `panels.py:1097–1099`, `:5873`, `:6603`). → RM-508 (Verdichtung des Vertrags aus RM-090: Entscheidung Robert)
- **B8** Eine Bohrung zeigt ihren Durchmesser fünfmal und ihre Lage über sieben Zahlen; Bezugsnamen tragen Nummern („Außenkante 4“) (`panels.py:10071–10075`, `placement_flow.py:5348–5349`). → RM-516
- **B9** Das Vorschauband hat sieben Zeilen mit „Körperzahl: 1 → 1“ und Maßen mit drei Nachkommastellen und festem „mm“ (`print_contract.py:246–304`, `:264`). → RM-516
- **B10** Derselbe Kameraflug steht zweimal als Knopf („Betroffene Stelle zeigen“ und „Stelle zeigen“, `panels.py:5777`). → RM-508
- **B11** Die Vorauswahl legt den Hauptknopf auf einen bestätigenden Hinweis (`panels.py:6371–6395`). → RM-512
- **B12** Im Ruhezustand leuchten sechs Akzente; `test_resting_state.py:40` zählt keine Linien. → RM-512
- **B13** Filamentwähler und Nahtschutz stehen vor den Handlungen; der Platzhalter ist abgeschnitten („Filament für die gewählte Fläche wäh…“, PT „…selecion“) (`main_window.py:3591`, `filament_assignment.py:168–197`). → RM-510
- **B14** An einer Fläche führen je zwei Knöpfe zum selben Ziel: „Baustein einsetzen …“ und *Bausteine*, „Loch oder Aussparung zeichnen …“ und „Tasche schneiden“. → RM-510
- **B15** Das Dock nennt die Auswahl zweimal mit „gemessen“ (`panels.py:8332–8343`, `selection_operations.py:827–833`). → RM-510
- **B16** 67 von 109 Nebenfolge-Sätzen sind Floskeln („Ändert nichts am Modell.“) und stehen sichtbar unter dem Hauptknopf (`panels.py:5942–5953`). → RM-508
- **B17** Der Status sagt „Bewertung unvollständig“ ohne Grund und zählt „0 × Fehler“ (`panels.py:5651–5669`, `:6668–6672`). → RM-508
- **B18** Werte in Befundzeilen stehen ohne Namen („— Deckel · 0 mm³ · 100 %“, `panels.py:1326`). → RM-508
- **B19** „Modell nachbauen“ steht ohne Auswahl gesperrt im Bericht, mit einem Satz von elf Wörtern (`panels.py:5683–5689`, `6170–6187`); gegen `grenzen.md` (Auswahlhandlungen in der Karte). → RM-508
- **B20** Am gewählten Körper steht oben im Dock eine Anleitung mit 18 Wörtern (`panels.py:7867–7871`). → RM-510
- **B21** „Prüfumfang“ und „Einzelheiten“ sind gerahmte Knöpfe statt flacher Klappen; der Anfangsfokus liegt auf „Prüfumfang“. → RM-508
- **B22** Tour (Codebefund): Hauptknopf „Schritt überspringen“, Markdown-Sternchen in sieben Texten, die Einleitung bleibt stehen. → RM-509, RM-512
- **B23** Chat (Codebefund): „Übernehmen“ eines Vorschlags ist kein Hauptknopf (`chat.py:282–288`). → RM-512
- **B24** Ein Schnellknopf über zwei Spalten bricht an halber Breite um (PT „Deslocar a / face“, `selection_operations.py:664`, `:740`). → RM-510

### C — Dialoge

- **C1** Die Vorderseite trägt im Median vier Felder; `MAX_FRONT_FIELDS = 8` (`op_dialog.py:103`) steht gegen Bauplan §2.4 („zwei bis drei“). Beispiele: Text aufbringen 6, Bohrung setzen 5, Deckel 5, Aushöhlen 5. → RM-513
- **C2** Vor dem ersten Feld stehen bis zu 118 Wörter; die Platzierungsanweisung ist die blasseste Zeile (`op_dialog.py:2000–2107`). → RM-513
- **C3** Der Druckdialog zeigt beim Öffnen 34 Bedienelemente; ohne Herstellerprofil vier leere Profilfelder und zwei gleichbedeutende Sätze. → RM-514
- **C4** „Erste Schritte“ (Codebefund): 118 Wörter beim Öffnen, Slicer zweimal, „Benutzerdefiniert …“ für zwei Dinge, eigener Drucker ohne `align_forms` (`first_run.py:335–651`). → RM-515
- **C5** *Aushöhlen* widerspricht sich vorn: „Oben öffnen“ an, „Öffnungen: Keine“ an, „Entlüftungen 1“ (guide-housing-with-lid-3; `prepare_ops.py:17704–17751`). → RM-513
- **C6** Die Spalte „Grund“ im Druckrat ist in jeder Zeile abgeschnitten, obwohl der Code Umbruch verspricht (`print_settings_dialog.py:5831–5843`). → RM-514
- **C7** Neben jedem Zahlenfeld steht „fx“, auch ohne Projektparameter (`op_dialog.py:347–364`). Gestaltungsentscheidung. → RM-513
- **C8** 104 Zahlenparameter meinen mit 0 „automatisch“ oder „keine“ und zeigen „0,00 mm“ (`lid.py:927`, `:1658`). → RM-513
- **C9** *Bohrung setzen* zeigt nach dem Flächenklick drei Koordinatenzeilen vorn (`op_dialog.py:1667–1700`); `grenzen.md` verlangt das, der eigene Kommentar (`:2089–2090`) das Gegenteil. → RM-513 (Regel ändern: Entscheidung Robert)
- **C10** Färben geht an derselben Stelle über Schnellwähler und Knopf „Filament auf eine Fläche“; `PICKER_HANDLES` fehlt `paint_slot` (`selection_operations.py:135`). → RM-510
- **C11** Die Klappe „Weitere Einstellungen“ im Operationsdialog nennt ihren Inhalt nicht (`op_dialog.py:2205–2238`). → RM-513
- **C12** *Eigener Baustein*: 21 Felder für zwei Maße, 978 px hoch, Rohschlüssel `breite`, `hoehe`, `hole_1`, `face_2` als Beschriftung (`recipe_dialog.py:186`, `:688–772`). → RM-517
- **C13** Katalogkacheln bis vier Zeilen; die Vorschaufarbe abtragender Bausteine (#E0A85C) liegt am Akzent (#F0A54A); zwei Leertexte. → RM-517
- **C14** Im Druckdialog steht „Drucker“ zweimal und „Düse“ für Durchmesser und Temperatur. → RM-514
- **C15** Über der Knopfzeile des Druckdialogs bleibt eine Lücke bis 260 px (`print_settings_dialog.py:2626`). → RM-514
- **C16** Auswahlzeilen sprechen in Datenbankbegriffen („PLA rot · PLA · Bestand unbekannt“, „· aus der Konstruktion“). → RM-513
- **C17** Ein Dialog zeigt zwei Hauptknöpfe, sobald ein Hinweis mit Handlung erscheint (`dialogs.py:3353–3359`, 57 Handlungen mit `primary`). → RM-512
- **C18** Dialoge benutzen zwei Abschnittsformen (`QGroupBox` und flache Klappen), zwei Randmaße (`ROOMY`, `WIDE`) und mehrere Beschriftungsspalten. → RM-518
- **C19** Der Hauptknopf heißt beim gleichen Vorgang „Einsetzen“ oder „Einfügen“; *Deckel erzeugen* setzt „ein“ (`op_dialog.py:2258`, `catalog.py:285`). → RM-507
- **C20** Rot (`make_danger`) tragen zwei „Abbrechen“, „Verwerfen“ ist Hauptknopf (`dialogs.py:4167–4170`). → RM-512
- **C21** Zwischen Beschriftung und Feld klaffen 120 bis 170 px, weil `align_forms` die zugeklappte Rückseite mitzählt (`op_dialog.py:2307`). Gestaltungsentscheidung. → RM-518
- **C22** Der Druckhinweis vor der ersten Nutzung hat 94 Wörter und nennt den Schalter anders als der Dialog (`print_disclosure.py:140–179`). → RM-514

### D — Kundentexte

- **D1** Die Befundkarte sagt jede Aussage zwei- bis dreimal (Ort, Schwere, Zeigen, Nebenfolge, Tooltip mit ganzem Befundsatz `panels.py:5935`). → RM-508
- **D2** = A15. → RM-519
- **D3** = C6; 40 von 45 Druckratstexten sind länger als 60 Zeichen, mit Pointen (`advise.py:795–796`, `:1306`, `:1318`, `:1330`). → RM-514
- **D4** Geänderte Bausteine erscheinen als Absatz im Prüfbericht (Median 28, höchstens 99 Wörter; `parts/check.py:319–360`). → RM-509
- **D5** Menü, Statuszeile und Dialogkopf zeigen die ganze `doc` (`main_window.py:5052–5054`, `op_dialog.py:2000–2001`); die Palette kürzt schon (`command_palette.py:253`). → RM-509
- **D6** Vorbehalte der Bausteine sind Absätze nach der Formel „Nur …: …“ (Median 26, höchstens 65 Wörter). → RM-509
- **D7** Die Tour hat keine Wortgrenze (56 von 83 Schritten über 20 Wörtern), die Bildanleitungen schon (`guides.MAX_STEP_WORDS`). → RM-509
- **D8** 128 von 502 Befundsätzen haben mehr als 20 Wörter; die Handlung steht als Prosa im Satz. → RM-509
- **D9** 108 Fehlertexte haben mehr als 20 Wörter und erklären die Technik dahinter (`backends/llm.py:671`). → RM-509
- **D10** Ein leerer Zustand wird an zwei bis drei Stellen zugleich erklärt (Dock, Statuszeile, Bericht, Katalog). → RM-508, RM-510, RM-517
- **D11** = C3; zwei Profilhinweise mit zwei Wörtern für dieselbe Sache. → RM-514
- **D12** = B18. → RM-508
- **D13** Fachwörter außerhalb der Wortliste: Mindestbahnbreite, „im Rahmen des Rasters“, Maßherkunft, Bereichstest, Startwerte, Materialtoleranz, exakter Körper, Rezept. → RM-509 (mit RM-084)
- **D14** Gedankenstriche (in 22–36 % der Texte je Art), 425 Semikolons, „Nur/Nicht …:“-Formeln, Pointen. → RM-509 (mit RM-084)
- **D15** Der Startbildschirm erzählt (rund 135 Wörter, Karten 16–19 Wörter, Formatliste in der Ablagefläche). → RM-515
- **D16** KI-Offenlegung und Modellbeschreibungen sind Absätze von 55 bis 84 Wörtern. → RM-509
- **D17** Kein Wächter misst Länge außer bei den Bildanleitungen. → RM-509
- **D18** 134 von 176 Statustipps wiederholen den Tooltip desselben Widgets. → RM-509 (Regeländerung: Entscheidung Robert)

## Was Robert entscheidet

Die Punkte nennen den Vorschlag; umgesetzt wird er erst mit seiner Antwort.

1. **Ausrichten und Anordnen bei gewähltem Körper** (A5): heute nur ohne Auswahl (Entscheidung „nur ohne Auswahl“). Vorschlag: bei Auswahl unter „Für alle Körper“ zeigen.
2. **Bausteine an einer Bohrung** (A7): Entscheidung vom 10.09., an einer Bohrung passe kein Baustein; das Register sagt fünf.
3. **Vorderseite höchstens vier Felder** (C1): `AGENTS.md` nennt „acht Felder vorn“ als Grenze, der Bauplan §2.4 zwei bis drei. Der Bauplan gilt; die Grenze in `AGENTS.md` und `tests/test_interface_limits.py` zieht nach.
4. **Befundkarte verdichten** (B7): Der Vertrag aus RM-090 verlangt Folge und Grundlage sichtbar; der Vorschlag macht daraus eine Metazeile.
5. **Stelle statt Koordinaten vorn** (C9): `grenzen.md` verlangt die vorgewählte Position vorn.
6. **Statustipp nur an Menüaktionen** (D18): `oberflaeche.md` verlangt `statusTip` an jedem Feld.
7. **Eine rechte Spalte** (A9): Das Auswahlfenster steht seit der Entscheidung vom 18.09. auch ohne Auswahl offen; der Vorschlag legt es unter die Berichtskarte.

## Zuordnung

| Punkt | Befunde |
|---|---|
| RM-506 Funktionen finden | A1, A2, A5, A7, A10, A12, A13, A19, B1 |
| RM-507 Ein Name je Funktion | A6, A11, A17 (Knopfnamen), A18, C19 |
| RM-508 Prüfbericht | A3, A8, B3, B7, B10, B16–B19, B21, D1, D10, D12 |
| RM-509 Kundentexte kürzen, Längenwächter | B6, B22 (Texte), D4–D9, D13, D14, D16–D18 |
| RM-510 Auswahlfenster | B2, B4, B13–B15, B20, B24, C10, D10 |
| RM-511 Eine rechte Spalte | A9, B5 |
| RM-512 Ein Akzent | A16, B11, B12, B22 (Knopf), B23, C17, C20 |
| RM-513 Operationsdialoge | C1, C2, C5, C7, C8, C9, C11, C16 |
| RM-514 Druckdialog | C3, C6, C14, C15, C22, D3, D11 |
| RM-515 Startbildschirm und Erste Schritte | A17, C4, D15 |
| RM-516 Maße im Bild und Vorschauband | B8, B9 |
| RM-517 Bausteinkatalog und eigener Baustein | A22, C12, C13, D10 |
| RM-518 Eine Form für alle Dialoge | C18, C21 |
| RM-519 Linke Karten und Zeichenmodus | A4, A14, A15, A20, A21, D2 |

**Reihenfolge nach Wirkung:** RM-508 und RM-506 zuerst (der erste Blick und die
Kernklage), dann RM-509 mit dem Wächter, weil RM-508, RM-513 und RM-514 ihre
Texte daran messen; danach RM-510, RM-513, RM-514, RM-512, RM-511; der Rest ist
klein und unabhängig.
