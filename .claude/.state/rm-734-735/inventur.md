# Inventur 0.6.1: Was heute nur über die Befehlspalette erreichbar ist

Stand: main `ee6b810fe`, 11.10.2026. Nur gelesen und gemessen, im Repository
nichts geändert. Gehört zu `vorbereitung-061-boolesch-und-palette.md`, Teil B.

## Messweg

Alle Zahlen stammen aus einem gebauten Hauptfenster (offscreen, `APPDATA`,
`LOCALAPPDATA`, `HOME`, `XDG_*`, `TEMP`, `TMP` auf
`F:\tmp-agenten\palette-inventur\appdata`, Demo-Frist wie in
`tests/conftest.py` neutralisiert). Skripte und Rohdaten liegen unter
`F:\tmp-agenten\palette-inventur\`:

| Datei | Was | Aufruf |
|---|---|---|
| `messen.py` → `messung.json` | Palettenzeilen, Menüleiste, Werkzeugleiste, Kürzel, Auswahlpanel je Stufe (alles freigegeben) und an echten Auswahlen, Kontextmenüs, Suchvergleich Panel ↔ Palette | `F:\3D Druck\.venv\Scripts\python.exe F:\tmp-agenten\palette-inventur\messen.py` (Exit 0) |
| `messen2.py` → `messung2.json` | Panelsuche nach *Automatisch teilen*, *Auf dem Bett anordnen* …; `_fits_the_level` der drei Szenenhandlungen | dito mit `messen2.py` (Exit 0) |
| `bericht.py` → `tabellen.md` | Einordnung jeder Palettenzeile (Anhang A) | `… python.exe bericht.py > tabellen.md` (Exit 0) |
| `tests_fund.py` → `tests_fund.txt` | Testfunktionen, die die Palette brauchen oder nennen (AST + Tokenizer) | `… python.exe tests_fund.py > tests_fund.txt` (Exit 0) |
| `fundstellen.py` | Fundstellen mit umschließender Funktion | `… python.exe fundstellen.py "F:/3D Druck/tests" "*.py"` |

Die Szene der echten Zustände: zwei Netzquader über `run_remote("create_box", …)`
(Merkmale nur `face`). Kürzel stehen in Qts Portabelschreibweise
(`Ctrl+Shift+P`), weil offscreen kein Qt-Katalog geladen ist; im deutschen
Fenster heißt dieselbe Taste „Strg+Umschalt+P“ (`app/images/manual/de/main-window.png`).

## Kurzergebnis

- Die Palette hat **273 Zeilen**: 189 Operationen und 84 Fensterbefehle.
- **Ohne Palette gar nicht erreichbar** ist eine Operation: *Überschneidungen
  prüfen* (`check_collisions`). **Nur per Kürzel** (und als Handlung an
  bestimmten Prüfberichtsbefunden) bleibt *Auf dem Bett anordnen*
  (`arrange_bed`, Strg+Umschalt+O). Die **sechs Netz-Grundkörper** (`create_box`
  … `create_tube`) entstehen ohne Palette nur noch über den Umweg
  *Verlauf → Als Dreiecksmodell rechnen*; *Zahlen an Maße binden …* steht sonst
  nur als Knopf in der Parameterkarte, und nur, solange eine feste Zahl passt.
- Die **15 Einstellungszeilen** (`settings.*`) verlieren ihren Direktsprung;
  erreichbar bleiben sie über *Bearbeiten → Einstellungen …*.
- **Im Menü, aber weder im Auswahlpanel noch in der Ansicht** stehen 11
  Operationen (alle Erzeuger aus *Erzeugen*, die nichts gewählt brauchen) und
  61 Fensterbefehle; zwei weitere Erzeuger und drei Fensterbefehle stehen in der
  Ansicht nur, solange die Szene leer ist.
- **Das Suchfeld des Auswahlpanels ist ohne Auswahl verborgen** und wertet dort
  keinen Text aus. Es findet **keinen** Fensterbefehl, keinen Erzeuger, keinen
  Baustein und keine der drei Szenenhandlungen; es rechnet dieselben drei
  Runden mit Kundenwörtern wie die Palette, aber ohne deren Rangfolge, ohne die
  Zeile „passt nur auf einzelne Wörter“ und nur über 81 von 189 Operationen.
  Strg+Umschalt+P „ins Suchfeld des Auswahlpanels“ trifft ohne Auswahl also auf
  ein Feld, das es nicht gibt (Abschnitt 4).

---

## 1. Wie die Palette ihre Einträge zusammenstellt

`MainWindow.action_command_palette` → `open_palette(query)`
(`app/ui/main_window.py:15962-15992`): Ist nichts gewählt und genau ein Körper
da, wählt sie ihn vorher (`_lone_body`, Z. 15974-15976); dann
`CommandPalette(self.palette_rows(commands), …)`.

| Quelle | Zeilen | Beleg |
|---|---|---|
| Register über `palette_entries(for_feature=self.selected_feature_kind())`, ohne `WINDOW_COMMAND_OPERATIONS` (`load` steht als Fensterbefehl `file.import`) | 189 (190 − 1) | `main_window.py:15949-15959`, `:615`; `app/core/registry/surfaces.py:833-880` |
| Fensterbefehle von Hand: `file.*` 9, `edit.*` 6, `view.*` 3, `help.manual` | 19 | `window_commands`, `main_window.py:12129-12179` |
| Jede Zeile des Einstellungsdialogs (`searchable_options`) | 15 | `main_window.py:12165-12174`; `app/ui/settings_dialog.py:164-210` |
| Werkzeuge der Werkzeugzeile (`tool.*`, „Ansicht: Schnitt“ …) | 7 | `main_window.py:12180-12185` |
| Übrige Menüzeilen (`menu.0` … `menu.42`), ohne *Beenden* und ohne *Befehlspalette …* | 43 | `_menu_commands`, `main_window.py:12193-12270` |
| **Summe** | **273** | `messung.json` → `palette_rows_empty_scene` |

- **Ohne Suchtext** blendet die Palette 17 Zeilen aus (8 versteckte Zwillinge,
  9 Variantenmitglieder; `hidden_from_the_menu`, `app/ui/command_palette.py:149-167`,
  `:226-227`); ab dem ersten Zeichen sind sie da.
- **`for_feature` ändert nur die Reihenfolge.** Gemessen für alle 13
  Merkmalsarten aus `FEATURE_KINDS` und `edge`: je 190 Einträge, dieselbe Menge
  wie ohne Merkmal (`palette_entries_by_feature.*.same_set_as_without = true`).
  Vorn stehen an `face` 54, `hole` 18, `pin` 9, `torus` 8, `cone`/`slot` je 7,
  `sphere`/`thread` je 5, `curved_face` 3, `fillet`/`void`/`pattern` je 2,
  `edge_loop` 1, an `edge` **keine** (die Kantenhandlungen tragen kein
  `applies_to`, `app/core/perceive/actions.py:2060-2076`).
- Freigabe je Zeile kommt aus `_palette_availability` (Operationen,
  `main_window.py:16027-16086`) und `_extra_availability` (Fensterbefehle,
  `:12272-12286`). Gemessen ausführbar: leere Szene 134/273, ein Körper 249,
  zwei Körper 257, eine Fläche 245.

## 2. Wo die Einträge sonst stehen

### 2.1 Auswahlpanel (Reiter *Auswahl*)

Aufbau einmal aus dem Register (`main_window.py:4283-4297`,
`SelectionOperationsPanel(REGISTRY.all())`). Was hineinkommt und was je Stufe
sichtbar ist, entscheiden diese Filter:

| Filter | Wirkung | Beleg |
|---|---|---|
| `body_operations` | Körperhandlungen: ohne Erzeuger (`consumes == 0`, außer `takes_whole_scene`), ohne Katalogoperationen, ohne reine Merkmalshandlungen (außer `also_on_body`) | `app/ui/selection_operations.py:325-352` |
| `feature_operations` | Handlungen mit `applies_to`, ohne Erzeuger und Katalog | `:355-383` |
| `shown_of_twins` | nimmt den versteckten Zwilling, wenn der Partner in der Menge ist (`drill_brep_hole`, `shell_exact`) | `app/core/registry/registry.py:385-419` |
| `catalogue_operations()` | 83 Bausteinoperationen nur über den Knopf *Bausteinkatalog …* | `app/core/registry/surfaces.py:736-763`; `selection_operations.py:687-697` |
| `_fits_the_level` | Stufe: Szene / Körper / Merkmalsart; `PICKER_HANDLES` nie in der Liste; Feldzeilen des Merkmalfensters nie in der Liste | `:1444-1478` |
| `takes_whole_scene` + `SCENE_ACTIONS_IN_THE_CARD` | nur ohne Auswahl, und dann nur `orient_for_print`; `arrange_bed` und `check_collisions` haben einen Knopf, der **auf keiner Stufe** sichtbar wird (gemessen, `messung2.json` → `fits`) | `surfaces.py:702-709`; `selection_operations.py:1464-1465` |
| `button.isEnabled()` | eine gesperrte Handlung verschwindet aus der Liste (kein grauer Knopf) | `:1222-1227` |
| `quick_names` | Schnellaktionen je Stufe; was oben steht, ist unten verborgen (`_list_twins`) | `:251-302`, `:481-487` |
| `left_out`, `OFFERED_AT_A_PART` | am Kegel ohne Senkung, an Bausteinmerkmalen | `:1105-1125` |

Im Panel stehen damit **81 Registeroperationen und *Automatisch teilen*** als
Knopf (`messung.json` → `panel_entries`, `panel_window_actions`). Dazu kommen
an derselben Stelle: das Merkmalfenster mit 8 Operationen als Feldzeilen
(`ACTION_ORDER`, `app/core/perceive/actions.py:146-165`) und den Kantenzeilen
(`EDGE_OPERATIONS`, `:2066-2076`), der Filamentwähler (`assign_slot`,
`paint_slot`, `clear_filament`, `selection_operations.py:154`; *Filamentlager
öffnen*, `app/ui/filament_assignment.py:121-122`) und der Knopf *Bausteinkatalog …*
bzw. *Passende Bausteine …*.

**Je Stufe, alles freigegeben** (`panel_state()` nach `set_context(…, all_available)`):

| Stufe | oben | Liste | Suchfeld | Katalogknopf |
|---|---|---|---|---|
| ohne Auswahl | – | 1 (`orient_for_print`), Satz „Gilt für alle Körper.“ | **verborgen** | ja |
| 1 Körper | `drill_hole`, `hollow_object`, `split_pinned` (+ *Modell nachbauen*) | 48 | ja | ja |
| ≥ 2 Körper | `union_objects`, `subtract_objects`, `intersect_objects` | 47 | ja | ja |
| mehrere Merkmalszeilen | `group_pattern` | 49 | ja | ja |
| `face` | `drill_hole`, `sketch_pocket` | 13 | ja | ja |
| `hole` | `countersink_hole`, `plug_hole`, `pattern_feature` | 4 | ja | *Passende Bausteine …* |
| `pin` | `pattern_feature` | 3 | ja | – |
| `thread` | – | 1 (`pin_for_bore`) | ja | – |
| `curved_face` | – | 1 (`hollow_object`) | ja | – |
| `edge_loop` | `repair` | 0 | verborgen | – |
| `cone` | `countersink_hole`, `pattern_feature` | 0 | verborgen | – |
| `sphere`, `torus`, `slot` | `pattern_feature` | 0 | verborgen | – |
| `fillet`, `void`, `pattern`, `edge` | – | 0 | verborgen | – |

**Echte Zustände** (Szene mit zwei Quadern, `messung.json` → `real_states`):
leere Szene — keine Liste, Satz „Wählen Sie einen Körper oder eine Fläche —
Bausteine gehen auch so.“, Katalogknopf; zwei Körper, nichts gewählt — nur
*Druckoptimal ausrichten*; ein Körper — oben 3 + *Modell nachbauen*, Liste 36;
zwei Körper — oben die drei Booleschen, Liste 43; eine Fläche — oben
*Bohrung setzen*, *Tasche schneiden*, Liste 9.

### 2.2 Ansicht

| Ort | Einträge | Beleg |
|---|---|---|
| Kontextmenü Objektbaum = Kontextmenü am Körper in der Ansicht | *Diesen Schritt ändern* (nur erzeugte Merkmale), *Auf dieser Fläche zeichnen* (Fläche), *(Körper) ausblenden*, *Alles andere ausblenden*, bei ≥ 2 Körpern *Vereinigen*, *Entfernen* (`delete_object` bzw. *Baustein entfernen*) | `app/ui/panels.py:3328-3361`, `:3449-3554`; `main_window.py:16797-16841`; gemessen: ein Körper `Ausblenden, Alles andere ausblenden, Objekt entfernen`, zwei Körper zusätzlich `Vereinigen`, Fläche `Auf dieser Fläche zeichnen, Körper ausblenden, …` |
| Kontextmenü der Ansicht, zusätzlich | `detect_region` am Netzkörper | `main_window.py:19272-19279` |
| Kantenmenü (Rechtsklick auf gewählte Kante) | `fillet_edges`, `chamfer_edges`, `bead_edges` (+ *Verrunden mit Verlauf*) | `main_window.py:19288-19326` |
| Werkzeugzeile unter der Ansicht | `tool.*`: Schnitt, Messen, Bewegen, Analyse, Schichten, Explosion, Teilen | `messung.json` → `tool_strip` |
| Kameraleiste unten rechts | die sieben Kameravorgaben (`menu.19` … `menu.25`) | `app/ui/viewport.py:3156-3230` |
| Einladung der **leeren** Szene | *Quader anlegen*, *Zylinder anlegen* (exakt, `create_brep_*`), *Zeichnen*, *Bausteinkatalog …*, *Modell einfügen …*, *Aus Text oder Bild …*, *Im Chat beschreiben* | `viewport.py:3362-3450`; `main_window.py:25344-25390` |
| Griffe | Bewegen/Drehen/Skalieren, Flächenzug, Bohrungsgriff, Langlochgriff — sie schreiben in Operationen, die ohnehin im Panel stehen | `app/ui/CLAUDE.md`, „Platzierung und Griffe“ |

### 2.3 Menüleiste und Werkzeugleiste oben

82 Menüzeilen (`messung.json` → `menu_bar`). 20 Operationen haben eine eigene
Menüzeile (Erzeugen, Grundformen, Bausteine); die 70 übrigen Operationsaktionen
hängen ohne Menü am Fenster, nur für Kürzel und Freigabe
(`main_window.py:5152-5167`). Die Werkzeugleiste oben trägt *Neues Projekt*,
*Öffnen*, *Speichern*, *Modell einfügen*, *Zeichnen*, *Formen*, *Skelett* und
*Funktion suchen …* (`messung.json` → `toolbars`).

### 2.4 Weitere Fensterstellen (keine der Klassen a–c)

Prüfbericht (*Exportieren*, *An den Slicer übergeben*, Befundhandlungen wie
*Auf dem Bett anordnen*: `panels.py:569-650`, `:6203-6207`;
`main_window.py:4206-4207`), Kopfzeile (Drucker → Druckeinstellungen,
`main_window.py:5799`), Parameterkarte (*Parameter anlegen …*, Bindeknopf:
`main_window.py:4474-4475`, `panels.py:3711-3720`, `:4176-4192`),
Verlauf-Kontextmenü (Kernwechsel *Als Dreiecksmodell rechnen*: `panels.py:5978-5986`,
`registry.py:350-375`), Katalogdialog (*Baustein aus Datei hinzufügen …*,
*Baustein als Datei weitergeben …*: `app/ui/catalog.py:552-568`),
Einstellungsdialog, Chat (*einrichten*: `main_window.py:4216`),
Startbildschirm (`main_window.py:4429-4443`).

## 3. Ergebnis je Klasse

**Einordnung:** Jede Zeile kommt in die erste zutreffende Klasse — (a)
Auswahlpanel (Schnellaktion, Liste, Merkmalfenster, Filamentwähler,
Katalog-Kachel hinter dem Panelknopf, auch indirekt über Partner/Art/Katalogdialog),
(b) Ansicht (2.2), (c) Menüleiste oder Werkzeugleiste oben, (d) nur Kürzel,
(f) nur eine andere Fensterstelle aus 2.4, (e) nirgends außer in der Palette.
Die Mehrfachzugehörigkeit steht in Anhang A.

| Klasse | alle | Operationen | Fensterbefehle |
|---|---|---|---|
| a Auswahlpanel | 172 | 167 | 5 |
| b Ansicht | 20 | 3 | 17 |
| c Menü/Werkzeugleiste | 72 | 11 | 61 |
| d nur Kürzel | 1 | 1 | 0 |
| f nur andere Fensterstelle | 7 | 6 | 1 |
| e nur Palette | 1 | 1 | 0 |
| **Summe** | **273** | **189** | **84** |

Aufgeteilt: (a) 82 direkt im Panel, 83 Katalog-Kacheln, 7 nur indirekt
(`shell_exact`, `drill_brep_hole` über ihren Partner; `sketch_revolve`,
`sketch_sweep`, `sketch_loft` über den Art-Umschalter im Schritt,
`main_window.py:22034-22068` nach `finish_sketch` `:13858`;
`file.part_adopt`, `file.part_share` im Katalogdialog). (b) davon nur in der
leeren Szene: `create_brep_box`, `create_brep_cylinder`, `file.import`,
`menu.2`, `menu.8`; `sketch_extrude` steht zusätzlich an jeder Fläche
(*Auf dieser Fläche zeichnen*, `main_window.py` `_on_sketch_on_face`).
Mehrfach gezählt: 97 Zeilen mit Menüweg (die 15 Einstellungszeilen und die
Zeichnen-Arten eingeschlossen), 52 mit Kürzel, 29 in der Ansicht, 8 in der
Werkzeugleiste, 24 an einer Stelle aus 2.4.

### 3.1 Ohne Palette unerreichbar oder nur noch über Umwege

| Kennung | Titel | Heute außer der Palette | Ohne Palette |
|---|---|---|---|
| `check_collisions` | Überschneidungen prüfen | nichts (Agent/Chat ausgenommen); Knopf im Panel existiert, ist aber auf keiner Stufe sichtbar (`selection_operations.py:1464-1465`). Die Auswertung meldet von selbst nur deckungsgleiche Körper und Bauraum, keine teilweise Überschneidung (`app/core/scene/evaluate.py:1733-1741`; `arrange.collision` nur aus `app/core/geom/prepare.py:4155-4195` über diese Operation) | **unerreichbar** |
| `arrange_bed` | Auf dem Bett anordnen | Strg+Umschalt+O (`app/core/geom/prepare_ops.py:23629`); Befundhandlung *Auf dem Bett anordnen* an `arrange.above_bed`, `arrange.off_the_plate`, `arrange.bodies_in_one_place`, `arrange.collision`, `split.symmetric`, `split.fewest_parts`, `prepare.halves_in_place`, `gcode.off_the_bed` (`panels.py:569-650`, `main_window.py:28107-28145`) | nur Kürzel oder Befund |
| `create_box`, `create_cylinder`, `create_cone`, `create_sphere`, `create_torus`, `create_tube` | Quader/Zylinder/Kegel/Kugel/Ring/Rohr anlegen (Netz) | Umweg: exakt anlegen, dann Verlauf-Kontextmenü *Als Dreiecksmodell rechnen* (`panels.py:5978-5986`) | nur Umweg; `menu_path` nennt ihn schon so (`registry.py:336-339`) |
| `edit.bind_parameters` | Zahlen an Maße binden … | Bindeknopf der Parameterkarte, nur sichtbar, wenn `binding_spots` nicht leer (`panels.py:4176-4192`) | bedingt erreichbar |
| `settings.*` (15) | Einstellungen: Sprache … Material | Funktion über *Bearbeiten → Einstellungen …* (Strg+,), die Zeile dort selbst suchen | Direktsprung entfällt (`settings_dialog.py:122-210`, `main_window.py:11947`) |

Die übrigen indirekten (a)-Zeilen bleiben ohne Palette erreichbar, verlieren
aber ihren Namen als Suchziel: Ihre Partner bzw. Sammeleinträge stehen im Panel.

### 3.2 Im Menü, aber weder im Auswahlpanel noch in der Ansicht

**Operationen (11)** — alles Erzeuger ohne Eingang, die das Panel grundsätzlich
nicht aufnimmt (`consumes == 0`, `selection_operations.py:349`, `:381`):

| Kennung | Titel | Menü |
|---|---|---|
| `create_container` | Behälter mit Deckel | Erzeugen → Grundformen |
| `create_brep_cone` | Kegel anlegen | Erzeugen → Grundformen |
| `create_brep_sphere` | Kugel anlegen | Erzeugen → Grundformen |
| `create_brep_torus` | Ring anlegen | Erzeugen → Grundformen |
| `create_brep_tube` | Rohr anlegen | Erzeugen → Grundformen |
| `create_organizer` | Organizer anlegen | Erzeugen → Grundformen |
| `create_profile_clamp_set` | Profilklemme mit Einlagen | Erzeugen → Grundformen |
| `thread_exact` | Schraube erstellen | Erzeugen → Grundformen |
| `create_label` | Schriftzug als Körper | Erzeugen |
| `load_step` | STEP laden | Erzeugen |
| `load_outline` | Zeichnung hochziehen | Erzeugen |

Dazu nur in der **leeren** Szene in der Ansicht, sonst nur im Menü:
`create_brep_box`, `create_brep_cylinder` (Erzeugen → Grundformen).

**Fensterbefehle (61)** — mit ihren übrigen Orten:

| Gruppe | Befehle | übrige Orte |
|---|---|---|
| Datei | *Neu*, *Öffnen …*, *Speichern* | Werkzeugleiste, Kürzel; *Öffnen* auch Startbildschirm |
| Datei | *Exportieren …*, *An den Slicer übergeben …* | Prüfbericht, Kürzel; Slicer auch Kopfzeile |
| Datei | *Speichern unter …* (Strg+Umschalt+S), *Modell aus dem Netz …*, *G-Code gegenprüfen …* | nur Menü/Kürzel |
| Bearbeiten | *Rückgängig*, *Wiederholen*, *Einstellungen …* | Kürzel |
| Bearbeiten | *Parameter anlegen …* | Parameterkarte |
| Bearbeiten | *Material kalibrieren …*, *Varianten erzeugen …* | nur Menü |
| Bearbeiten | *Chat einrichten …* | Chat |
| Erzeugen | *Gegenstücke setzen …* | nur Menü |
| Einstellungen | 15 Zeilen `settings.*` | indirekt über *Einstellungen …* |
| Ansicht | *Einpassen* (Pos1), *Rechten Bereich zeigen* (F9), *Druckplatte zeigen* (Strg+Umschalt+D), *Karten an ihren Platz* | Kürzel bzw. nur Menü |
| Ansicht → Darstellung | 8 Zeilen, sechs davon mit Ziffertaste 1–6 | Kürzel |
| Ansicht → Thema, Navigation | 7 Zeilen | Einstellungsdialog |
| Hilfe | *Handbuch …* (F1), *Beispiele*, *Zusätzliche Programme …*, *Tastenkürzel …* (?), *Erste Schritte …*, *Rückmeldung senden …*, *Nach einer neuen Version sehen*, *Neuerungen …*, *Solidon freischalten …*, *Solidon3D unterstützen …*, *Über Solidon* | Handbuch auch Startbildschirm und i im Merkmalfenster; Unterstützen auch Startbildschirm |

Die vollständige Liste mit Menüweg steht in Anhang A (Klasse c).

## 4. Das Suchfeld des Auswahlpanels als Ersatz

**Ohne Auswahl verborgen und taub.** `_filter` setzt den Suchtext ohne Auswahl
auf leer (`selection_operations.py:1211-1213`), `_say_there_is_nothing`
verbirgt das Feld (`:1396-1408`, `_without_a_selection` `:1345-1369`).
Gemessen: „speichern“ ohne Auswahl eingetippt → `search_hidden: true`, Liste
unverändert `orient_for_print` (`messung.json` → `empty_selection_search`).
Ebenso verborgen an `edge_loop`, `cone`, `sphere`, `torus`, `slot`, `fillet`,
`void`, `pattern` und an einer Kante (Tabelle 2.1). Die Regel dazu ist eine
Entscheidung Robert („ohne Suchfeld“, `.claude/rules/grenzen.md:157-162`) —
sie steht gegen „Strg+Umschalt+P setzt den Fokus ins Suchfeld“. Die Palette
selbst wählt ohne Auswahl den einzigen Körper (`main_window.py:15974-15976`),
das Panel nicht.

**Fensterbefehle findet es nicht.** Gesucht wird nur über `_entries`, die
Registeroperationen des Panels (`selection_operations.py:505-510`,
`_search_hits` `:1248-1269`). Gemessen bei gewähltem Körper (`messung.json` →
`search_compare_one_body`):

| Suchwort | Palette | Panel |
|---|---|---|
| speichern | `file.save`, `file.export`, `file.part_share`, `menu.0` | nichts Passendes (Treffer `slots_from_texture` über den `doc`-Satz) |
| öffnen / exportieren / handbuch / einstellungen / parameter / quader | 4 / 2 / 1 / 16 / 3 / 3 Zeilen | „Kein Treffer — versuchen Sie ein anderes Wort.“ + *In allen Funktionen suchen* |
| anordnen | `arrange_bed` | Treffer, aber unsichtbar → „Kein Treffer“ |
| Überschneidungen prüfen / Druckoptimal ausrichten | je 1 | „Kein Treffer“ (`messung2.json`) |
| Automatisch teilen | `edit.auto_split` (+ weitere) | 9 andere Zeilen aus der dritten Runde, **`auto_split` selbst nicht** (Fensteraktion ohne Eintrag in `_entries`; nur das Gruppenwort „vorbereiten“ zeigt sie) |
| verschmelzen / vereinigen / abziehen / schnittmenge | je die Boolesche | an einem Körper: Satz „… braucht zwei Objekte …“ statt Knopf (`_needs_another_choice`, `:1271-1299`) |
| boolesch | nichts | nichts |

**Dieselbe Suche, teilweise.** Gleich ist die Treffermenge je Zeile: beide
rufen `found_in_rounds` (`command_palette.py:237-264`) — genau, dann Stamm, dann
irgendein Wort — über Titel, Name, `doc` und Kundenwörter (`synonyms_for` →
`customer_phrases`, `SYNONYMS` und `CUSTOMER_WORDS` der Sprache,
`app/core/registry/search.py:319-361`). Gemessen: „verschmelzen“ →
*Vereinigen*, „ecke abrunden“ → *Verrunden*, „zu viele dreiecke“ →
*Dreiecke verringern* in beiden. Anders im Panel:

1. Suchraum 81 statt 189 Operationen und 0 statt 84 Fensterbefehlen; nur
   Treffer der aktuellen Stufe und nur freigegebene erscheinen (`:1222-1227`).
   Gemessen, je Panelzeile ihr eigener Titel als Suchwort: An einem Körper
   finden 30 der 81 sich nicht (24 Merkmalshandlungen, die drei
   Szenenhandlungen, die drei des Filamentwählers), an zwei Körpern dazu
   *Bohrung setzen* (`panel_search_own_title`).
2. Keine Rangfolge (`rank`, `LOOSE_RANK`, `rank_entries`,
   `command_palette.py:486-499`); Treffer stehen in den Menügruppen nach Titel.
3. Die dritte Runde sagt es nicht: `_search_hits` verwirft `loosened`
   (`selection_operations.py:1261`), die Palette setzt die Zeile „Kein Befehl
   passt auf alle Wörter …“ (`command_palette.py:501-510`) — die Regel verlangt
   sie (`grenzen.md:371-374`).
4. Zusätzlich trifft ein Gruppentitel alle Zeilen der Gruppe (`:1262-1268`).
5. Die Schnellaktionen oben werden nicht gefiltert, sie stehen bei jedem
   Suchwort da.
6. Ohne Treffer führt *In allen Funktionen suchen* in die Palette
   (`:604-610`, `:1191-1197`, `:1409`; verbunden `main_window.py:4287`) — dieser
   Weg fällt mit ihr.

## 5. Alle weiteren Stellen, die die Palette nennen oder brauchen

### 5.1 Code, der mit der Palette fällt oder umzieht

| Datei:Zeile | Was |
|---|---|
| `app/ui/command_palette.py` (ganz) | Dialog `CommandPalette`, `_Rows`, `rank`, `LOOSE_RANK`, `word_hits`; **gebraucht von anderen**: `found_in_rounds`, `matches`, `_haystack` (Panelsuche), `native_key` (Kontextmenü, `main_window.py:16825`), Weiterreichung `fold` (`:43`), `first_sentence` (`:44`), `hidden_from_the_menu` |
| `app/ui/main_window.py:281` | `from app.ui.command_palette import CommandPalette, fold, native_key` (`fold` genutzt `:22860`) |
| `app/ui/main_window.py:5061-5069` | Menüzeile *Befehlspalette …*, Strg+Umschalt+P, `_palette_action` |
| `app/ui/main_window.py:5770-5790`, `:29585` | Knopf *Funktion suchen …* → `action_command_palette`, Tooltip „Öffnet die Befehlspalette …“; `_fit_toolbar` |
| `app/ui/main_window.py:9240-9250` | Kürzelübersicht bekommt die Taste der Palette |
| `app/ui/main_window.py:12121-12286` | `window_commands` (auch von `app/ui/guide_targets.py:534` gebraucht), `_menu_commands` (überspringt `_palette_action`, `:12242`), `_extra_availability`, `_palette_actions` |
| `app/ui/main_window.py:15877-16025` | `palette_rows`, `action_command_palette`, `open_palette` (mit `_lone_body`), `_run_window_command`, `_run_palette_choice` |
| `app/ui/main_window.py:16027-16086` | `_palette_availability` — **bleibt**, sie speist das Panel (`:6312`) |
| `app/ui/main_window.py:4287` | `paletteRequested.connect(self.open_palette)` |
| `app/ui/selection_operations.py:53`, `:425-426`, `:604-610`, `:1191-1197`, `:1409` | Import `fold, found_in_rounds`; Signal `paletteRequested`; Knopf *In allen Funktionen suchen* |
| `app/ui/settings_dialog.py:122-210` | `option_titles`/`searchable_options` „eine Quelle für Formular und Befehlspalette“ (RM-491); `searchable_options` hat nur den Palettenaufrufer `main_window.py:12173` |
| `app/ui/shortcuts_window.py:242`, `:292` | Hinweiszeile mit der Palettentaste |
| `app/ui/tool_strip.py:463-465` | `strip_title` „was in der Befehlspalette über den Werkzeugen steht“ (auch Kürzelübersicht `shortcuts_window.py:122`) |
| `app/ui/style.py:1708-1718` | Stil `QPushButton#functionSearch` (bleibt mit dem Knopf) |
| `app/core/registry/surfaces.py:702-722` | `SCENE_ACTIONS_IN_THE_CARD`-Kommentar und `_panel_place` → „Befehlspalette“ als Ort von `arrange_bed`/`check_collisions`; fließt über `menu_path` in Handbuch (`:1184`), Agentenwerkzeuge (`app/core/agent/tools.py:476`, `:587`), Agentenangebot (`app/core/agent/offer.py:125`) |
| `app/core/registry/surfaces.py:810-880`, `app/core/registry/__init__.py:56,65,112,122,148,170` | `PaletteEntry` (auch Panel `selection_operations.py:505-510`), `palette_entries` (nur Palette und Tests) |
| `app/core/registry/registry.py:336-382` | `TWIN_WAYS`/`twin_way` — Text nennt den Verlauf, Docstring „Erzeuger über die Palette“ (`:379`) |
| `app/core/manual.py:433-435` | Handbuchtext „… und die Befehlspalette findet jede Handlung über ihren Namen“ |

### 5.2 Code-Kommentare und Docstrings, die die Palette nennen

`app/ui/selection_operations.py:99,274,330,371,511,825,1249`;
`app/ui/main_window.py` (u. a. `:3320-3332`, `:5155-5161`, `:5275-5277`,
`:12302-12309`); `app/core/registry/search.py:1,101,115,130,173,204,222,332,407,411,461,513,526,533,547,551`;
`app/core/registry/surfaces.py:7,451,812,822,844,850,864,955,974`;
`app/core/registry/registry.py:3,127,267,295,379,465`;
`app/core/manual_search.py:15,17,46,144,270`; `app/core/agent/offer.py:15`;
`app/core/bootstrap.py:125,145`; `app/core/knowledge/parts/recipe.py:341,889`;
`app/core/geom/ops.py:1284` („§19.2 nennt die Befehlspalette den Universalzugang“);
`app/core/geom/prepare_ops.py:11272`; `app/core/scene/migrations.py:191`;
`app/core/scene/history.py:2013`; `app/core/ingest/loader.py:1365`;
`app/core/brep/ops.py:4`; `app/cli/main.py:4`; `app/i18n/keys.py:6`;
`app/ui/op_dialog.py:209,2622`; `app/ui/panels.py:415,7772,9075,10142`;
`app/ui/labels.py:2294`; `app/ui/session.py:2624`; `app/ui/overlay.py:2110`;
`app/ui/local_recognition_flow.py:70`; `app/ui/draw_flow.py:328`;
`app/ui/print_settings_dialog.py:4336`; `app/ui/icons.py:403`;
`app/ui/header.py:435`; `app/ui/tool_strip.py:441`;
`app/ui/shortcuts_window.py:101`; `tools/check_new_texts.py:138`;
`tools/make_workshop_videos.py:12`. Farbpaletten (`QPalette`, `drawing.palette`,
`app/ui/palette.py`) sind nicht gemeint und nicht aufgeführt.

### 5.3 Kundentexte in den Katalogen

Je Katalog `app/i18n/locales/{en,es,fr,it,pt}.json` 13 Schlüssel (in `en.json`
Z. 678-682, 4029-4030, 4650, 4730, 4804-4805, 7755, 8616): „Befehl suchen“,
„Befehl suchen …“, „Befehle“, „Befehlspalette“, „Befehlspalette …“,
„Funktion suchen“, „Funktion suchen …“, „In allen Funktionen suchen“,
„Jede Operation über ihren Namen finden, ohne durch die Menüs zu gehen.“, die
zwei „Kein Befehl passt …“-Sätze, die Handbuchseite „Wo was steht …“ und
„Öffnet die Befehlspalette: jede Funktion mit Ort und Kürzel.“ Dazu „Ort: {place}“
(Z. 5946), nur von der Palette benutzt (`command_palette.py:537`).

### 5.4 Handbuch, Tour, Erststart, Kürzelübersicht

| Stelle | Inhalt |
|---|---|
| `app/core/manual.py:433-435` | Satz zur Befehlspalette (Seite „Was die Bereiche können“) |
| Referenzteil über `menu_path` | „Ort: Befehlspalette → Auf dem Bett anordnen“, „… → Überschneidungen prüfen“ (`surfaces.py:1184`) |
| `tools/make_manual.py` | keine eigene Fundstelle; erzeugt aus `manual.pages()` |
| Tour/Erststart (`app/core/tour.py`, `app/ui/tour.py`, `app/core/guides.py`, `app/ui/first_run.py`, `app/ui/start_screen.py`) | **keine Fundstelle** (`rg -n "Palette\|palette\|Funktion suchen\|Strg\+Umschalt\+P\|Ctrl\+Shift\+P"` trifft dort nur Farbpaletten) |
| Kürzelübersicht | `shortcuts_window.py:101` (Docstring), `:242`, `:292` (Hinweis mit Taste), Aufruf `main_window.py:9240-9250`; die Zeile *Befehlspalette …* erscheint dort, weil sie im Menü *Bearbeiten* steht |

### 5.5 Website

| Datei:Zeile | Inhalt |
|---|---|
| `website/handbuch.html:570`, `:956`, `:980` | Satz zur Befehlspalette; „Ort: Befehlspalette → Auf dem Bett anordnen / Überschneidungen prüfen“ |
| `website/en/manual.html:570,956,961`; `fr/manual.html:570,956,980`; `es/manual.html:570,961,970`; `it/manual.html:570,956,960`; `pt/manual.html:570,956,980` | dasselbe übersetzt |
| `website/changelog.html:45` und `website/{en,es,fr,it,pt}/changelog.html` | Changelog-Einträge früherer Versionen (bleiben) |
| `website/version.json:34,67,100,133,166,199,232-237,245,303,361,419,477,535` | Update-Fenster: „*Funktion suchen* (Strg+Umschalt+P)“ und Zusammenfassung |
| übrige Seiten (`funktionen.html`, `features.html` …) | keine Fundstelle |

### 5.6 Changelog (`changelog/*.md`)

`changelog/de.md:91` (0.6.0: Return öffnet den Eintrag „in *Funktion suchen*“),
`:271` (0.5.3: „*Funktion suchen* (Strg+Umschalt+P)“), `:535` (0.5.2), `:772`
(0.5.1), `:1117` (0.4.1); gleiche Zeilen in `en.md:66,246,510,747,1092`,
`es.md:67,247,511,748,1093`, `fr.md:67,247,511,748,1093`,
`it.md:66,246,747,1092`, `pt.md:66,246,510,747,1092`. Vergangene Versionen
bleiben; 0.6.1 braucht einen eigenen Eintrag.

### 5.7 Bauplan (`3d-agent-bauplan.md`)

| Zeile | Abschnitt | Text |
|---|---|---|
| 230-231 | §2.6 Entdeckbarkeit | „**Befehlspalette** über eine Taste: alles aus dem Register per Suche erreichbar, mit Kürzel daneben“ |
| 819 | §10 Tabelle | „Befehlspalette und Kürzel ← `title`, `doc`, `shortcut`“ |
| 1512-1513 | §19.2 Tastatur | „Die **Befehlspalette** ist der Universalzugang.“ |
| 3473 | §40 P0 | Abnahme „sichtbar in Menü, Palette, Auswahlfenster, CLI und Tool-Schema“ |

### 5.8 Regeln, Karten, Agenten, Skills

| Datei:Zeile | Inhalt |
|---|---|
| `.claude/rules/grenzen.md:2,9,35,52-53,75,87,105,159,163,168,192,210-216,223,323,355-358,363-366,380-386` | Ort der Palette, `paths:` auf `command_palette.py`, Zwillingsweg, Szenenhandlungen „in der Palette“, Kartensuche „wie die Palette“, *In allen Funktionen suchen*, *Funktion suchen …* in `_fit_toolbar`, drei Listen mit `return_opens`, Sortierung, Kundenwörter „gehören der Palette“ |
| `.claude/rules/oberflaeche.md:135,371` | „Menü, Statuszeile, Palette …“; „Alles über die Befehlspalette erreichbar, Kürzel daneben“ |
| `.claude/rules/fenster.md:90,179` | „Kürzel/Palette bleiben erreichbar“; „Aktion, Palette und Karte tragen den Grund“ |
| `.claude/rules/vorderseite.md:24` | „dieselbe Kürzung wie Palette und Menü“ |
| `.claude/rules/zeichenflaeche.md:48` | „… Palette nehmen das Bett nicht an“ |
| `.claude/rules/agentenschicht.md:155-156` | Wortsuche der Befehlspalette, Kundenwörter der Palette |
| `app/ui/CLAUDE.md:40,250,257` | Einstiege „Menü, Palette, Auswahlfeld und Kürzel“; Modulzeile `command_palette.py`; `settings_dialog.py` „jede Zeile in der Palette“ |
| `app/core/registry/CLAUDE.md:5,17,33` | sechs Oberflächen inkl. `palette_entries()`; `search.py` „die Palette ordnet mit beiden“ |
| `.claude/agents/solidon3d-op.md:49`, `.claude/agents/bedienlogik.md:54`, `.claude/skills/neue-op/SKILL.md:37` | Befehlspalette als Einstieg einer Operation |
| erzeugte Spiegel `.codex/agents/solidon3d-op.toml`, `.codex/agents/bedienlogik.toml`, `.agents/skills/neue-op/SKILL.md` | über `tools/sync_agents.py` nachziehen, nie von Hand |
| `konzepte/begruendungen/regel-grenzen.md:85,144,200,297,298,312,432,445,496,499,685,713,744`; `regel-fenster.md:41,202,622,955,956`; `regel-ansicht.md:115`; `regel-operationen.md:138`; `regel-oberflaeche.md:18`; `regel-agentenschicht.md:98`; `karte-app-ui.md:1101,1201,1916,2151,2155,2593`; `karte-app-core-agent.md:58,60`; `karte-app-core-registry.md:18`; `karte-app-core-ingest.md:129` | Begründungen spiegeln die Regeln; ziehen mit |
| `konzepte/konzept-bedienung.md:180,384,399,452,557,558,744,745`; `konzept-handbuch-2026-09.md:73,498`; `konzept-produktkompass-2026-08.md:324,499`; `konzept-vollwertiges-cad-2026-09.md:626,779`; `konzepte/README.md:135` | Konzepte mit Palette als Weg (Stand prüfen); `konzepte/archiv/` und `ROADMAP-ARCHIV.md` (41 Nennungen) sind Geschichte |
| `ROADMAP.md:5014,5909-5910,6477` | erledigte Punkte, die die Palette nennen (`:1867-1870` meint eine andere „Palette am Umriss“) |

### 5.9 Tests

30 Dateien; 66 Testfunktionen berühren Code, der mit der Palette fällt oder
umbenannt wird („braucht“), 37 nennen sie nur in Docstring oder Kommentar.
„braucht“ schließt Hilfen ein, die bleiben können (`window_commands`,
`_palette_availability`, `palette_entries`) — die Umsetzung entscheidet, was
davon fällt. Farbpaletten-Tests (`test_style.py`, `test_viewport_decisions.py`,
Themen-Tests in `test_theme_and_palette.py`) sind herausgenommen.

| Datei | braucht (Funktion, Zeilen) | nennt nur |
|---|---|---|
| `test_acceptance_p0.py` | Modulebene (Z. 24); test_operations_are_visible_in_every_surface (Z. 57) |  |
| `test_analysis_ui.py` |  | test_the_context_menu_follows_the_titles_like_the_menu_bar (Z. 5591) |
| `test_delivery_tools.py` |  | test_the_commit_guard_reads_a_text_with_context_under_its_catalog_key (Z. 873) |
| `test_dialog_layout_regressions.py` | test_palette_detail_has_its_own_line_without_horizontal_scrolling (Z. 74,75,78,80,87,99); test_palette_shows_a_description_for_an_available_command (Z. 109,110,112,121); test_the_palette_tooltip_names_every_line_once (Z. 586,587,589,598) |  |
| `test_draw_ui.py` |  | test_extrude_join_and_pocket_open_the_drawing_tool (Z. 282); test_a_chosen_pocket_or_join_refuses_the_bed (Z. 812) |
| `test_feature_panel.py` |  | test_a_locked_panel_says_why_before_anyone_clicks (Z. 970) |
| `test_header.py` | test_the_search_gives_way_to_the_header_and_keeps_its_name (Z. 416,417,425,426,430); test_the_search_keeps_its_word_beside_the_filament_button (Z. 674,706,734,748) |  |
| `test_ingest.py` |  | test_the_most_common_finding_says_what_helps (Z. 2064) |
| `test_interface_limits.py` | Modulebene (Z. 30,69); test_the_lead_is_the_first_sentence_and_names_the_limit_briefly (Z. 377); test_the_palette_puts_what_fits_the_selection_first (Z. 748,750,751); test_the_note_names_the_key_that_opens_the_palette (Z. 885,886,891,893,895); test_no_scheme_gives_the_same_key_to_two_things (Z. 932); test_the_palette_knows_every_line_of_the_menu_bar (Z. 1332,1344,1353,1356,1367,1368); test_the_palette_greys_out_what_the_menu_greys_out (Z. 1437,1440,1445,1453,1455,1457,1469,1472,1477,1479); test_the_palette_teaches_the_keys_of_the_active_scheme (Z. 1483,1488,1491,1498,1502,1508); test_a_part_of_the_users_own_never_reaches_the_menu_bar (Z. 1692,1693); test_the_named_path_is_the_path_the_menu_builds (Z. 2127,2141,2157,2158,2161,2177); test_the_palette_names_the_key_the_menu_really_uses (Z. 2272,2276,2282) | test_every_operation_has_exactly_one_menu_entry (Z. 795); test_the_shortcut_list_is_generated_from_the_menu_bar (Z. 845) |
| `test_local_recognition_flow.py` | test_palette_click_and_escape_share_the_local_flow (Z. 181); test_local_search_requires_a_visible_mesh_on_the_current_plate (Z. 241,245,248) |  |
| `test_locked_says_why.py` | Modulebene (Z. 39,261,263) | test_the_missing_objects_sentence_counts_and_names_the_mac_key (Z. 561) |
| `test_manual_search.py` |  | test_a_keyboard_without_umlauts_finds_the_same (Z. 194); test_a_customer_word_leads_to_the_pages_of_its_operation (Z. 207); test_a_customer_word_finds_the_chapter_of_its_operation_in_every_language (Z. 244) |
| `test_native_keys.py` | Modulebene (Z. 75,76); test_the_mac_writing_is_the_one_qt_uses_there (Z. 271,277); test_every_list_that_opens_on_activation_opens_on_return_at_the_mac (Z. 344,348,357,359,373,374) |  |
| `test_operation_ui.py` |  | test_the_sketch_menu_starts_drawing (Z. 158); test_requested_variant_is_selected_and_applied (Z. 610); test_changing_a_hole_through_the_wrong_sister_opens_the_right_one (Z. 689); test_a_body_without_the_needed_feature_says_so (Z. 1344); test_the_caveat_reaches_every_surface_that_offers_the_operation (Z. 3900) |
| `test_parts.py` |  | test_an_attachment_stands_in_the_face_menu_and_a_test_body_does_not (Z. 6846) |
| `test_print_settings_ui.py` |  | test_the_search_finds_a_setting_by_its_words (Z. 7839) |
| `test_recipes.py` |  | test_a_travelled_recipe_gets_the_same_text_limits_as_a_local_one (Z. 2064) |
| `test_registry.py` | Modulebene (Z. 18); test_every_operation_reaches_every_surface (Z. 338); test_actions_for_every_body_name_where_they_stand_without_a_selection (Z. 625,640) | test_an_action_on_body_and_feature_names_both_places (Z. 663) |
| `test_registry_consistency.py` | Modulebene (Z. 34); test_every_operation_reaches_every_surface (Z. 261) |  |
| `test_selection_operations.py` | test_the_search_finds_customer_words_and_names_what_another_choice_needs (Z. 322,343); test_no_hit_offers_to_search_every_function (Z. 1186,1195,1199,1200,1204) | test_selection_changes_update_in_place_and_explain_disabled_actions (Z. 424); test_actions_of_the_wrong_level_leave_instead_of_greying_out (Z. 477); test_actions_for_all_bodies_stand_without_a_selection_and_not_at_one (Z. 554); test_auto_split_stands_with_the_other_ways_to_split (Z. 1323) |
| `test_sketch_editor.py` |  | test_every_drawing_tool_wears_its_key (Z. 1179) |
| `test_slot_features.py` |  | test_the_slot_defaults_make_a_slot_and_not_an_error (Z. 1551) |
| `test_split_line.py` |  | test_splitting_at_a_plane_is_not_a_second_operation (Z. 379) |
| `test_split_tool.py` | test_the_palette_carries_the_tool_shortcuts (Z. 585,586); test_no_shortcut_of_the_window_is_handed_out_twice (Z. 607) |  |
| `test_theme_and_palette.py` | Modulebene (Z. 1,12); test_the_search_finds_by_title_name_and_documentation (Z. 403); test_the_card_finds_with_the_rounds_of_the_palette (Z. 412,416,417,421,424,427,434,435,437); test_the_palette_lists_every_operation_but_the_merged_twins (Z. 444,460,466); test_every_merged_twin_is_still_reachable_by_typing (Z. 483,484,486); test_the_twin_never_stands_before_its_partner (Z. 508); test_typing_exact_finds_both_twins (Z. 528,533); test_the_palette_opens_big_enough_to_be_a_list (Z. 544,551,554,557,559); test_the_palette_shows_the_shortcut_so_it_gets_learned (Z. 566); test_typing_narrows_the_list_and_picks_the_first (Z. 572); test_a_search_without_hits_says_so_and_chooses_nothing (Z. 589); _palette_entries (Z. 599,600,602); test_the_search_finds_words_typed_without_umlauts (Z. 612,614); test_the_search_falls_back_to_the_word_stem (Z. 630,632); test_a_hit_in_the_title_beats_a_hit_in_the_description (Z. 652,654); test_the_palette_is_sorted_by_what_the_reader_reads (Z. 675,689,692,693,698,705); test_the_palette_writes_the_keys_the_way_the_keyboard_does (Z. 715,723,730,732,747,748,749,751,755,764); test_the_palette_finds_what_a_customer_types (Z. 809,812,813,822,825,827); test_the_word_a_customer_types_lands_on_top (Z. 879,880,883,894); test_a_customer_finds_his_operation_in_his_language (Z. 937,940,945); test_a_word_inside_a_title_does_not_beat_the_word_that_means_it (Z. 959,960,963,966); test_an_operation_shown_as_a_window_command_hands_over_its_words (Z. 992,997,1004); test_the_palette_lines_its_shortcuts_up (Z. 1080,1082); test_the_native_palette_keeps_its_second_line_below_the_title (Z. 1109); test_enter_never_starts_a_command_that_only_the_description_matched (Z. 1177,1178,1180,1188,1194,1205,1211); test_the_palette_opens_with_a_search_text_and_names_each_place (Z. 1223,1232) | test_every_customer_word_belongs_to_a_row_of_the_palette (Z. 976) |
| `test_thread_replace.py` |  | test_every_way_through_the_window_carries_the_counterpart_in_preview_and_step (Z. 282) |
| `test_tool_offer.py` |  | test_the_request_brings_its_operation_with_its_fields (Z. 173); test_the_agent_weighs_its_curated_words_and_not_the_palette_phrases (Z. 222,227,236) |
| `test_ui.py` | test_the_menu_is_built_from_the_registry (Z. 2164,2170,2177,2186,2203,2216,2234,2239,2244); test_a_halted_chain_takes_no_new_step_and_names_the_way_on (Z. 7154,7198,7242); test_the_palette_refuses_a_locked_choice_with_the_reason (Z. 8121,8124,8128); test_an_operation_without_a_menu_entry_is_not_simply_allowed (Z. 8135,8155,8159); test_a_locked_window_command_is_refused_with_the_reason (Z. 8166,8169,8172,8173,8174,8181,8186); test_a_creation_from_the_start_screen_begins_the_empty_project (Z. 11742,11744,11766,11778,11782); test_the_palette_reaches_more_than_the_registry (Z. 11990,11998,12007); test_the_menu_path_matches_the_built_menu_for_every_operation (Z. 14652,14654,14672,14677,14679,14680); test_palette_twins_do_not_look_alike (Z. 19898,19904,19906); test_twins_differ_in_the_sentence_the_palette_shows (Z. 19924,19934); test_the_palette_finds_every_setting_behind_the_closed_section (Z. 19952,19955,19961,19964,19965,19988); test_command_palette_shows_explanations_without_repeating_window_titles (Z. 19992,19995,19997,19998,19999,20027); test_a_question_of_several_words_still_finds_something (Z. 20052,20054,20055); test_the_build_plate_hides_in_one_step (Z. 20076,20077,20089) | test_delete_removes_the_feature_not_the_body (Z. 4427); test_a_halted_chain_locks_the_feature_panel_and_lets_go_after_undo (Z. 5745); test_part_file_commands_do_not_add_a_file_menu_row (Z. 12014); test_the_toolbar_has_the_two_entries_for_way_four (Z. 14398) |
| `test_ui_settings.py` | test_the_palette_offers_every_visible_setting_under_its_row_name (Z. 687,689,691,695) | test_a_setting_from_the_palette_opens_its_row (Z. 658) |
| `test_widget_lifetime.py` | _builders (Z. 182,285); _openers.open_palette (Z. 760,761,762); _openers (Z. 768,770) |  |

Modulweite Abhängigkeiten: `test_locked_says_why.py:39,261-263` (Dialogliste
`"CommandPalette"` — betrifft jeden parametrisierten Dialogfall),
`test_widget_lifetime.py:182,285,760-770` (Bauliste und Öffner der Palette),
`test_theme_and_palette.py:12` (Import), `test_interface_limits.py:30,69`,
`test_registry.py:18`, `test_registry_consistency.py:34`,
`test_acceptance_p0.py:24` (Import `palette_entries`). `test_native_keys.py:75-76`
benutzt „Strg+Umschalt+P“ nur als Tastenbeispiel und hängt nicht an der Palette.

### 5.10 Bildschirmfotos

Ein Bild des Palettendialogs gibt es nicht (`app/images/manual/de`: 95 Dateien,
keine mit *palette*, *befehl* oder *such*). Die Werkzeugleiste mit
*Funktion suchen … Strg+Umschalt+P* steht auf `main-window.png` (angesehen, de)
und auf jedem Anleitungsbild, das die obere Leiste zeigt. Bleibt der Knopf mit
Wort und Taste, bleiben die Bilder gültig; ändert sich seine Beschriftung,
gehören sie zum nächsten Bildlauf (`tools/make_figures.py`, `/erzeugen`).

## 6. Was die Inventur für den Plan heißt

Das sind Befunde, keine Entscheidungen.

1. Bevor die Palette geht, brauchen *Überschneidungen prüfen* und *Auf dem Bett
   anordnen* einen sichtbaren Platz: Ihr Panelknopf existiert, wird aber auf
   keiner Stufe gezeigt, weil `SCENE_ACTIONS_IN_THE_CARD` nur
   `orient_for_print` trägt (Entscheidung Robert vom 05.10.2026 im Kommentar
   `surfaces.py:702-708`). Der Plan nennt beide schon; die Messung bestätigt,
   dass sonst nichts fehlt.
2. Die Netz-Grundkörper haben danach nur den Verlaufsumweg; `menu_path` nennt
   ihn bereits. Ob das genügt, ist eine Produktfrage.
3. Strg+Umschalt+P „ins Suchfeld“ trifft ohne Auswahl und an acht
   Merkmalsarten auf ein verborgenes Feld; dort widerspricht die neue
   Entscheidung der alten („ohne Suchfeld“, `grenzen.md:157-162`).
4. Das Suchfeld findet heute weder Fensterbefehle noch Erzeuger, Bausteine oder
   Einstellungen — mit der Palette fällt die Suche über 192 der 273 Zeilen
   (273 − 81 Panelzeilen; *Automatisch teilen* findet die Panelsuche nicht über
   seinen Namen). Ersatz für einzelne Gruppen gibt es an anderer Stelle (Suche
   im Bausteinkatalog, in der Kürzelübersicht, im Handbuch).
5. Die Panelsuche verschweigt die gelockerte dritte Runde (Abschnitt 4, Punkt 3);
   das verstößt schon heute gegen `grenzen.md:371-374`.
6. `found_in_rounds`, `matches`, `_haystack`, `native_key` und die
   Weiterreichung von `fold` müssen vor dem Löschen umziehen (5.1);
   `window_commands` bleibt für die Anleitungsziele (`guide_targets.py:534`).

---

## Anhang A: jede Palettenzeile

Klasse wie in Abschnitt 3. Orte: a Auswahlpanel (Stufen: „1 Körper“, „≥2 Körper“,
„ohne Auswahl“, „mehrere Merkmalszeilen“ oder Merkmalsart), b Ansicht,
c Menüleiste, w Werkzeugleiste oben, d Kürzel (Portabelschreibweise),
o andere Fensterstelle. Erzeugt mit `bericht.py` aus `messung.json`.

| # | Kennung | Titel | Klasse | Orte |
|---|---|---|---|---|
| 1 | `cut_away` | Abschneiden | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 2 | `subtract_objects` | Abziehen | a | a: oben: ≥2 Körper; a: Liste: 1 Körper, mehrere Merkmalszeilen; d: Kürzel Ctrl+Shift+A |
| 3 | `group_pattern` | Als Muster zusammenfassen | a | a: oben: mehrere Merkmalszeilen; a: Liste: 1 Körper, ≥2 Körper |
| 4 | `split_pinned` | An Ebene teilen | a | a: oben: 1 Körper; a: Liste: ≥2 Körper, mehrere Merkmalszeilen |
| 5 | `split_line` | An gezeichneter Linie teilen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 6 | `sketch_join` | An Körper anfügen | a | a: Liste: face; b: Fläche: *Auf dieser Fläche zeichnen* (Richtung entscheidet) |
| 7 | `align_to_feature` | An Merkmal ausrichten | a | a: Liste: hole, face, pin |
| 8 | `place_on_bed` | Auf das Bett setzen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; d: Kürzel Ctrl+Shift+B |
| 9 | `arrange_bed` | Auf dem Bett anordnen | d | o: Prüfbericht-Handlung an Befunden arrange.*/split.*/gcode.off_the_bed; d: Kürzel Ctrl+Shift+O |
| 10 | `fit_to_size` | Auf Maß bringen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 11 | `hollow_object` | Aushöhlen | a | a: oben: 1 Körper; a: Liste: ≥2 Körper, mehrere Merkmalszeilen, face, curved_face; d: Kürzel Ctrl+H |
| 12 | `shell_exact` | Aushöhlen | a | a: über *Aushöhlen* (Körper entscheidet) |
| 13 | `create_bayonet` | Bajonettverschluss | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 14 | `insert_bayonet` | Bajonettverschluss | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 15 | `create_container` | Behälter mit Deckel | c | c: Erzeugen → Grundformen → Behälter mit Deckel |
| 16 | `add_container_insert` | Behältereinsatz erzeugen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; c: Erzeugen → Bausteine → Behältereinsatz erzeugen |
| 17 | `resize_hole` | Bohrung ändern | a | a: Merkmalfenster (Feldzeile) |
| 18 | `drill_brep_hole` | Bohrung setzen | a | a: über *Bohrung setzen* (Körper entscheidet) |
| 19 | `drill_hole` | Bohrung setzen | a | a: oben: 1 Körper, face; d: Kürzel Ctrl+B |
| 20 | `plug_hole` | Bohrung verschließen | a | a: oben: hole |
| 21 | `create_barrel_hinge` | Bolzenscharnier | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 22 | `insert_barrel_hinge` | Bolzenscharnier | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 23 | `create_lid` | Deckel erzeugen | a | a: Liste: face; c: Erzeugen → Bausteine → Deckel erzeugen |
| 24 | `insert_seal_groove` | Dichtnut | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 25 | `create_seal` | Dichtnut mit Dichtung | a | a: Liste: face |
| 26 | `screw_lid` | Drehdeckel erzeugen | a | a: Liste: face; c: Erzeugen → Bausteine → Drehdeckel erzeugen |
| 27 | `rotate_object` | Drehen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; d: Kürzel Ctrl+R |
| 28 | `remesh_uniform` | Dreiecke angleichen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 29 | `decimate_mesh` | Dreiecke verringern | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 30 | `insert_printed_thread` | Druckbares Gewinde | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 31 | `orient_for_print` | Druckoptimal ausrichten | a | a: Liste: ohne Auswahl |
| 32 | `sketch_revolve_cut` | Durch Drehen schneiden | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 33 | `sketch_loft_cut` | Durch Überblenden schneiden | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 34 | `create_gusset` | Eckwinkel | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 35 | `insert_gusset` | Eckwinkel | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 36 | `replace_profile_liners` | Einlagen für neues Profil | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; c: Erzeugen → Bausteine → Einlagen für neues Profil |
| 37 | `compensate_first_layer` | Elefantenfuß ausgleichen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 38 | `sketch_sweep_cut` | Entlang einer Bahn schneiden | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 39 | `sketch_sweep` | Entlang eines Bogens führen | a | c: Erzeugen → Zeichnen … (Art); a: Art-Umschalter im Schritt (indirekt) |
| 40 | `chamfer_edges` | Fase anbringen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; b: Kantenmenü; a: Merkmalfenster an der Kante |
| 41 | `create_room_pane` | Fensterscheibe | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 42 | `insert_room_pane` | Fensterscheibe | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 43 | `paint_slot` | Filament auf eine Fläche | a | a: Filamentwähler |
| 44 | `clear_filament` | Filament entfernen | a | a: Filamentwähler |
| 45 | `assign_slot` | Filament zuweisen | a | a: Filamentwähler |
| 46 | `create_living_hinge` | Filmscharnier | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 47 | `insert_living_hinge` | Filmscharnier | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 48 | `subdivide_surface` | Fläche unterteilen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 49 | `push_face` | Fläche versetzen | a | a: Merkmalfenster (Feldzeile); d: Kürzel Q |
| 50 | `brep_to_mesh` | Flächenbearbeitung beenden | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 51 | `sculpt_strokes` | Formen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; w: Werkzeugleiste *Formen* |
| 52 | `draft_faces` | Formschräge anstellen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen, face |
| 53 | `check_join_path` | Fügeweg prüfen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 54 | `create_printed_nut` | Gedruckte Mutter | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 55 | `insert_printed_nut` | Gedruckte Mutter | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 56 | `cut_counter_form` | Gegenform einlassen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 57 | `place_group_on_bed` | Gemeinsam auf das Bett setzen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 58 | `create_threaded_rod` | Gewindebolzen | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 59 | `insert_threaded_rod` | Gewindebolzen | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 60 | `lattice_fill` | Gitter füllen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 61 | `smooth_mesh` | Glätten | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 62 | `sketch_extrude` | Grundform hochziehen | b | b: Fläche: *Auf dieser Fläche zeichnen*; Einladung leere Szene *Zeichnen*; w: Werkzeugleiste *Zeichnen*; c: Erzeugen → Zeichnen … (Sammeleintrag) |
| 63 | `create_holder_shelf` | Halter Ablage | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 64 | `insert_holder_shelf` | Halter Ablage | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 65 | `create_holder_fork` | Halter Gabel | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 66 | `insert_holder_fork` | Halter Gabel | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 67 | `create_holder_ring` | Halter rund | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 68 | `insert_holder_ring` | Halter rund | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 69 | `create_holder_u` | Halter U-Form | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 70 | `insert_holder_u` | Halter U-Form | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 71 | `insert_heatset_m4` | Heat-Set-Einpressbuchse | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 72 | `split_bodies` | In Einzelteile aufteilen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 73 | `mesh_to_exact` | In Flächen und Kanten umwandeln | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 74 | `create_cable_clip` | Kabelclip | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 75 | `insert_cable_clip` | Kabelclip | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 76 | `insert_cable_gland` | Kabeldurchführung mit Zugentlastung | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 77 | `resize_chamber` | Kammer ändern | a | a: Liste: face |
| 78 | `create_channel_joint` | Kanalnaht | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 79 | `insert_channel_joint` | Kanalnaht | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 80 | `remesh_mesh` | Kanten verfeinern | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 81 | `create_brep_cone` | Kegel anlegen | c | c: Erzeugen → Grundformen → Kegel anlegen |
| 82 | `create_cone` | Kegel anlegen | f | o: Verlauf-Kontextmenü *Als Dreiecksmodell rechnen* am exakten Grundkörper |
| 83 | `pattern` | Kopien in Reihe oder Kreis | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 84 | `create_brep_sphere` | Kugel anlegen | c | c: Erzeugen → Grundformen → Kugel anlegen |
| 85 | `create_sphere` | Kugel anlegen | f | o: Verlauf-Kontextmenü *Als Dreiecksmodell rechnen* am exakten Grundkörper |
| 86 | `insert_bearing_seat` | Kugellager einsetzen | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 87 | `insert_lug` | Lasche mit Loch | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 88 | `field_cut` | Lochfeld schneiden | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; c: Erzeugen → Lochfeld schneiden |
| 89 | `insert_pegboard_hook` | Lochwand-Einhänger | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 90 | `insert_magnet_pocket` | Magnettasche | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 91 | `set_material` | Material festlegen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 92 | `resize_feature` | Merkmal ändern | a | a: Merkmalfenster (Feldzeile) |
| 93 | `rotate_feature` | Merkmal drehen | a | a: Merkmalfenster (Feldzeile) |
| 94 | `remove_feature` | Merkmal entfernen | a | a: Merkmalfenster (Feldzeile) |
| 95 | `duplicate_feature` | Merkmal verdoppeln | a | a: Merkmalfenster (Feldzeile) |
| 96 | `move_feature` | Merkmal verschieben | a | a: Merkmalfenster (Feldzeile) |
| 97 | `pattern_feature` | Merkmal vervielfachen | a | a: oben: hole, pin, cone, sphere, torus, slot |
| 98 | `detect_region` | Merkmale an dieser Stelle erkennen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; b: Kontextmenü der Ansicht am Netzkörper |
| 99 | `insert_nut_trap` | Mutternfalle | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 100 | `insert_profile_tongue` | Nutfeder für Aluprofil | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 101 | `duplicate_object` | Objekt duplizieren | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; d: Kürzel Ctrl+D |
| 102 | `delete_object` | Objekt entfernen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; b: Kontextmenü *Entfernen*; d: Kürzel Del |
| 103 | `rename_object` | Objekt umbenennen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; d: Kürzel F2 |
| 104 | `thicken` | Offene Fläche schließen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 105 | `create_organizer` | Organizer anlegen | c | c: Erzeugen → Grundformen → Organizer anlegen |
| 106 | `create_organizer_rim` | Organizer-Rand | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 107 | `insert_organizer_rim` | Organizer-Rand | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 108 | `create_organizer_foot` | Organizer-Steckfuß | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 109 | `insert_organizer_foot` | Organizer-Steckfuß | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 110 | `create_organizer_divider` | Organizer-Trennwand | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 111 | `insert_organizer_divider` | Organizer-Trennwand | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 112 | `create_organizer_tray` | Organizer-Wanne | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 113 | `insert_organizer_tray` | Organizer-Wanne | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 114 | `create_dowel` | Passstift und Passbohrung | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 115 | `insert_dowel` | Passstift und Passbohrung | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 116 | `create_profile_clamp_set` | Profilklemme mit Einlagen | c | c: Erzeugen → Grundformen → Profilklemme mit Einlagen |
| 117 | `create_profile_clamp_liner` | Profilklemmen-Einlage | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 118 | `insert_profile_clamp_liner` | Profilklemmen-Einlage | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 119 | `create_profile_clamp_shell` | Profilklemmschale | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 120 | `insert_profile_clamp_shell` | Profilklemmschale | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 121 | `test_piece` | Prüfstück erzeugen | a | a: Liste: hole, face, pin |
| 122 | `create_box` | Quader anlegen | f | o: Verlauf-Kontextmenü *Als Dreiecksmodell rechnen* am exakten Grundkörper |
| 123 | `create_brep_box` | Quader anlegen | b | c: Erzeugen → Grundformen → Quader anlegen; b: Einladung leere Szene |
| 124 | `create_detent_disc` | Rastdrehscheibe | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 125 | `insert_detent_disc` | Rastdrehscheibe | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 126 | `insert_latch` | Rastnase | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 127 | `create_room_floor` | Raumboden | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 128 | `insert_room_floor` | Raumboden | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 129 | `create_room_wall` | Raumwand | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 130 | `insert_room_wall` | Raumwand | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 131 | `displace_image` | Relief auflegen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 132 | `repair` | Reparieren | a | a: oben: edge_loop; a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; d: Kürzel Ctrl+Shift+R |
| 133 | `create_brep_torus` | Ring anlegen | c | c: Erzeugen → Grundformen → Ring anlegen |
| 134 | `create_torus` | Ring anlegen | f | o: Verlauf-Kontextmenü *Als Dreiecksmodell rechnen* am exakten Grundkörper |
| 135 | `create_brep_tube` | Rohr anlegen | c | c: Erzeugen → Grundformen → Rohr anlegen |
| 136 | `create_tube` | Rohr anlegen | f | o: Verlauf-Kontextmenü *Als Dreiecksmodell rechnen* am exakten Grundkörper |
| 137 | `create_pipe_clamp` | Rohrschelle | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 138 | `insert_pipe_clamp` | Rohrschelle | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 139 | `sketch_revolve` | Rotationskörper aufziehen | a | c: Erzeugen → Zeichnen … (Art); a: Art-Umschalter im Schritt (indirekt) |
| 140 | `insert_hinge_eye` | Scharnierauge | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 141 | `insert_hose_barb` | Schlauchtülle | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 142 | `insert_keyhole` | Schlüsselloch-Aufhängung | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 143 | `insert_snap_connector` | Schnappverbinder für eine Naht | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 144 | `insert_snap_fit` | Schnappverbindung | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 145 | `intersect_objects` | Schnittmenge | a | a: oben: ≥2 Körper; a: Liste: 1 Körper, mehrere Merkmalszeilen; d: Kürzel Ctrl+Shift+X |
| 146 | `create_printed_screw` | Schraube | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 147 | `insert_printed_screw` | Schraube | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 148 | `thread_exact` | Schraube erstellen | c | c: Erzeugen → Grundformen → Schraube erstellen |
| 149 | `insert_screw_hole` | Schraubenloch mit Senkung | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 150 | `inlay_text` | Schrift einlegen | a | a: Liste: face; c: Erzeugen → Schrift einlegen |
| 151 | `create_label` | Schriftzug als Körper | c | c: Erzeugen → Schriftzug als Körper |
| 152 | `countersink_hole` | Senken | a | a: oben: hole, cone |
| 153 | `create_seal_gasket` | Separate Dichtung | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 154 | `insert_seal_gasket` | Separate Dichtung | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 155 | `scale_object` | Skalieren | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 156 | `mirror_object` | Spiegeln | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; d: Kürzel Ctrl+M |
| 157 | `create_foot` | Standfuß | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 158 | `insert_foot` | Standfuß | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 159 | `create_rod_connector` | Steckhülse und Stangenverbinder | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 160 | `insert_rod_connector` | Steckhülse und Stangenverbinder | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 161 | `pose_armature` | Stellung geben | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; w: Werkzeugleiste *Skelett* |
| 162 | `load_step` | STEP laden | c | c: Erzeugen → STEP laden |
| 163 | `pin_for_bore` | Stift für Bohrung | a | a: Liste: hole, thread |
| 164 | `sketch_pocket` | Tasche schneiden | a | a: oben: face; b: Fläche: *Auf dieser Fläche zeichnen* (Richtung entscheidet) |
| 165 | `label_text` | Text aufbringen | a | a: Liste: face; c: Erzeugen → Text aufbringen |
| 166 | `apply_texture` | Textur aufbringen | a | a: Liste: face |
| 167 | `slots_from_texture` | Textur in Filamente umrechnen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 168 | `create_fit_ladder` | Toleranz-Testkörper | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 169 | `insert_fit_ladder` | Toleranz-Testkörper | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 170 | `create_overhang_fan` | Überhangfächer | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 171 | `insert_overhang_fan` | Überhangfächer | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 172 | `check_collisions` | Überschneidungen prüfen | e |  |
| 173 | `union_objects` | Vereinigen | a | a: oben: ≥2 Körper; a: Liste: 1 Körper, mehrere Merkmalszeilen; b: Kontextmenü bei ≥2 Körpern; d: Kürzel Ctrl+Shift+V |
| 174 | `fillet_edges` | Verrunden | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; b: Kantenmenü; a: Merkmalfenster an der Kante |
| 175 | `translate_object` | Verschieben | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; d: Kürzel Ctrl+T |
| 176 | `resize_closure` | Verschluss ändern | a | a: Liste: hole, face, pin |
| 177 | `create_rib` | Versteifungsrippe | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 178 | `insert_rib` | Versteifungsrippe | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 179 | `create_wall_mount` | Wandhalter | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 180 | `insert_wall_mount` | Wandhalter | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 181 | `create_wall_ladder` | Wandstärkenleiter | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 182 | `insert_wall_ladder` | Wandstärkenleiter | a | a: Katalog-Kachel (Panelknopf *Bausteinkatalog …*) |
| 183 | `blend_union` | Weich verschmelzen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen |
| 184 | `bead_edges` | Wulst anlegen | a | a: Liste: 1 Körper, ≥2 Körper, mehrere Merkmalszeilen; b: Kantenmenü; a: Merkmalfenster an der Kante |
| 185 | `load_outline` | Zeichnung hochziehen | c | c: Erzeugen → Zeichnung hochziehen |
| 186 | `slot_hole` | Zum Langloch ziehen | a | a: Merkmalfenster (Feldzeile) |
| 187 | `sketch_loft` | Zwischen zwei Umrissen aufspannen | a | c: Erzeugen → Zeichnen … (Art); a: Art-Umschalter im Schritt (indirekt) |
| 188 | `create_brep_cylinder` | Zylinder anlegen | b | c: Erzeugen → Grundformen → Zylinder anlegen; b: Einladung leere Szene |
| 189 | `create_cylinder` | Zylinder anlegen | f | o: Verlauf-Kontextmenü *Als Dreiecksmodell rechnen* am exakten Grundkörper |
| 190 | `file.new` | Neu | c | c: Datei → Neu; w: Werkzeugleiste; d: Kürzel Ctrl+N |
| 191 | `file.open` | Öffnen … | c | c: Datei → Öffnen …; w: Werkzeugleiste; o: Startbildschirm; d: Kürzel Ctrl+O |
| 192 | `file.save` | Speichern | c | c: Datei → Speichern; w: Werkzeugleiste; d: Kürzel Ctrl+S |
| 193 | `file.import` | Modell einfügen … | b | c: Datei → Modell einfügen …; b: Einladung leere Szene; w: Werkzeugleiste; o: Startbildschirm; d: Kürzel Ctrl+I |
| 194 | `file.export` | Exportieren … | c | c: Datei → Exportieren …; o: Prüfbericht *Exportieren*; d: Kürzel Ctrl+E |
| 195 | `file.print_settings` | An den Slicer übergeben … | c | c: Datei → An den Slicer übergeben …; o: Prüfbericht; Kopfzeile (Drucker); d: Kürzel Ctrl+P |
| 196 | `file.catalog` | Bausteinkatalog … | a | c: Datei → Bausteinkatalog …; a: Panelknopf *Bausteinkatalog …*; b: Einladung leere Szene; d: Kürzel Ctrl+K |
| 197 | `file.part_adopt` | Baustein aus Datei hinzufügen … | a | a: Knopf im Katalogdialog (über *Bausteinkatalog …*) |
| 198 | `file.part_share` | Baustein als Datei weitergeben … | a | a: Knopf im Katalogdialog (über *Bausteinkatalog …*) |
| 199 | `edit.settings` | Einstellungen … | c | c: Bearbeiten → Einstellungen …; d: Kürzel Ctrl+, |
| 200 | `edit.undo` | Rückgängig | c | c: Bearbeiten → Rückgängig; d: Kürzel Ctrl+Z |
| 201 | `edit.redo` | Wiederholen | c | c: Bearbeiten → Wiederholen; d: Kürzel Ctrl+Y |
| 202 | `edit.add_parameter` | Parameter anlegen … | c | c: Bearbeiten → Parameter anlegen …; o: Parameterkarte |
| 203 | `edit.bind_parameters` | Zahlen an Maße binden … | f | o: Parameterkarte (nur wenn feste Zahlen passen) |
| 204 | `edit.auto_split` | Automatisch teilen … | a | a: Liste: 1 Körper, ≥2 Körper |
| 205 | `settings.language` | Einstellungen: Sprache | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 206 | `settings.unit` | Einstellungen: Anzeigeeinheit | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 207 | `settings.theme` | Einstellungen: Thema | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 208 | `settings.updates` | Einstellungen: Beim Start nach einer neuen Version sehen | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 209 | `settings.slicer` | Einstellungen: Slicer | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 210 | `settings.navigation` | Einstellungen: Navigation | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 211 | `settings.shortcuts` | Einstellungen: Tastenbelegung | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 212 | `settings.diff_palette` | Einstellungen: Differenzansicht | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 213 | `settings.auto_accept` | Einstellungen: Umkehrbare Chat-Vorschläge ohne Nachfrage übernehmen | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 214 | `settings.ai_disclosure_reset` | Einstellungen: KI-Hinweis erneut anzeigen | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 215 | `settings.remote` | Einstellungen: Fernsteuerung durch andere Programme zulassen (MCP) | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 216 | `settings.remote_port` | Einstellungen: Port der Fernsteuerung | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 217 | `settings.thread_families` | Einstellungen: Gewindereihen in den Auswahllisten | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 218 | `settings.printer` | Einstellungen: Drucker | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 219 | `settings.material` | Einstellungen: Material | c | c: indirekt: Bearbeiten → Einstellungen … (Strg+,), dort die Zeile |
| 220 | `view.fit` | Einpassen | c | c: Ansicht → Einpassen; d: Kürzel Home |
| 221 | `view.toggle_right` | Rechten Bereich zeigen | c | c: Ansicht → Rechten Bereich zeigen; d: Kürzel F9 |
| 222 | `view.bed` | Druckplatte zeigen | c | c: Ansicht → Druckplatte zeigen; d: Kürzel Ctrl+Shift+D |
| 223 | `help.manual` | Handbuch … | c | c: Hilfe → Handbuch …; o: Startbildschirm; i im Merkmalfenster; d: Kürzel F1 |
| 224 | `tool.section` | Ansicht: Schnitt | b | b: Werkzeugzeile unter der Ansicht; d: Kürzel Alt+1 |
| 225 | `tool.measure` | Ansicht: Messen | b | b: Werkzeugzeile unter der Ansicht; d: Kürzel Alt+2 |
| 226 | `tool.transform` | Ansicht: Bewegen | b | b: Werkzeugzeile unter der Ansicht; d: Kürzel Alt+3 |
| 227 | `tool.analysis` | Ansicht: Analyse | b | b: Werkzeugzeile unter der Ansicht; d: Kürzel Alt+4 |
| 228 | `tool.layers` | Ansicht: Schichten | b | b: Werkzeugzeile unter der Ansicht; d: Kürzel Alt+5 |
| 229 | `tool.explode` | Ansicht: Explosion | b | b: Werkzeugzeile unter der Ansicht; d: Kürzel Alt+6 |
| 230 | `tool.split` | Ansicht: Teilen | b | b: Werkzeugzeile unter der Ansicht; d: Kürzel Alt+7 |
| 231 | `menu.0` | Datei: Speichern unter … | c | c: Datei → Speichern unter …; d: Kürzel Ctrl+Shift+S |
| 232 | `menu.1` | Datei: Modell aus dem Netz … | c | c: Datei → Modell aus dem Netz … |
| 233 | `menu.2` | Datei: Modell erzeugen … | b | c: Datei → Modell erzeugen …; b: Einladung leere Szene *Aus Text oder Bild …*; d: Kürzel Ctrl+G |
| 234 | `menu.3` | Datei: G-Code gegenprüfen … | c | c: Datei → G-Code gegenprüfen … |
| 235 | `menu.4` | Bearbeiten: Material kalibrieren … | c | c: Bearbeiten → Material kalibrieren … |
| 236 | `menu.5` | Bearbeiten: Varianten erzeugen … | c | c: Bearbeiten → Varianten erzeugen … |
| 237 | `menu.6` | Bearbeiten: Filamentlager … | a | c: Bearbeiten → Filamentlager …; a: Filamentwähler im Panel: *Filamentlager öffnen*; o: Startbildschirm |
| 238 | `menu.7` | Bearbeiten: Chat einrichten … | c | c: Bearbeiten → Chat einrichten …; o: Chat *einrichten* |
| 239 | `menu.8` | Erzeugen: Zeichnen … | b | c: Erzeugen → Zeichnen …; w: Werkzeugleiste *Zeichnen*; b: Einladung leere Szene *Zeichnen* |
| 240 | `menu.9` | Erzeugen > Bausteine: Gegenstücke setzen … | c | c: Erzeugen → Bausteine → Gegenstücke setzen … |
| 241 | `menu.10` | Ansicht: Karten an ihren Platz | c | c: Ansicht → Karten an ihren Platz |
| 242 | `menu.11` | Ansicht > Darstellung: Massiv | c | c: Ansicht → Darstellung → Massiv; d: Kürzel 1 |
| 243 | `menu.12` | Ansicht > Darstellung: Massiv mit Kanten | c | c: Ansicht → Darstellung → Massiv mit Kanten; d: Kürzel 2 |
| 244 | `menu.13` | Ansicht > Darstellung: Drahtgitter | c | c: Ansicht → Darstellung → Drahtgitter; d: Kürzel 3 |
| 245 | `menu.14` | Ansicht > Darstellung: Transparent | c | c: Ansicht → Darstellung → Transparent; d: Kürzel 4 |
| 246 | `menu.15` | Ansicht > Darstellung: Flache Schattierung | c | c: Ansicht → Darstellung → Flache Schattierung |
| 247 | `menu.16` | Ansicht > Darstellung: Weiche Schattierung | c | c: Ansicht → Darstellung → Weiche Schattierung |
| 248 | `menu.17` | Ansicht > Darstellung: Perspektivisch | c | c: Ansicht → Darstellung → Perspektivisch; d: Kürzel 5 |
| 249 | `menu.18` | Ansicht > Darstellung: Orthografisch | c | c: Ansicht → Darstellung → Orthografisch; d: Kürzel 6 |
| 250 | `menu.19` | Ansicht > Kamera: Isometrisch | b | c: Ansicht → Kamera → Isometrisch; b: Kameraleiste in der Ansicht; d: Kürzel Ctrl+0 |
| 251 | `menu.20` | Ansicht > Kamera: Vorne | b | c: Ansicht → Kamera → Vorne; b: Kameraleiste in der Ansicht; d: Kürzel Ctrl+1 |
| 252 | `menu.21` | Ansicht > Kamera: Hinten | b | c: Ansicht → Kamera → Hinten; b: Kameraleiste in der Ansicht; d: Kürzel Ctrl+2 |
| 253 | `menu.22` | Ansicht > Kamera: Links | b | c: Ansicht → Kamera → Links; b: Kameraleiste in der Ansicht; d: Kürzel Ctrl+3 |
| 254 | `menu.23` | Ansicht > Kamera: Rechts | b | c: Ansicht → Kamera → Rechts; b: Kameraleiste in der Ansicht; d: Kürzel Ctrl+4 |
| 255 | `menu.24` | Ansicht > Kamera: Oben | b | c: Ansicht → Kamera → Oben; b: Kameraleiste in der Ansicht; d: Kürzel Ctrl+5 |
| 256 | `menu.25` | Ansicht > Kamera: Unten | b | c: Ansicht → Kamera → Unten; b: Kameraleiste in der Ansicht; d: Kürzel Ctrl+6 |
| 257 | `menu.26` | Ansicht > Thema: Dunkel | c | c: Ansicht → Thema → Dunkel; o: Einstellungsdialog |
| 258 | `menu.27` | Ansicht > Thema: Hell | c | c: Ansicht → Thema → Hell; o: Einstellungsdialog |
| 259 | `menu.28` | Ansicht > Navigation: Solidon — links verschiebt, rechts dreht, WASD fliegt | c | c: Ansicht → Navigation → Solidon — links verschiebt, rechts dreht, WASD fliegt; o: Einstellungsdialog |
| 260 | `menu.29` | Ansicht > Navigation: Wie in Cura — links wählt, rechts dreht | c | c: Ansicht → Navigation → Wie in Cura — links wählt, rechts dreht; o: Einstellungsdialog |
| 261 | `menu.30` | Ansicht > Navigation: Wie in Bambu Studio, Orca und PrusaSlicer — links dreht | c | c: Ansicht → Navigation → Wie in Bambu Studio, Orca und PrusaSlicer — links dreht; o: Einstellungsdialog |
| 262 | `menu.31` | Ansicht > Navigation: Wie im CAD — mittlere Taste dreht, rechts zoomt | c | c: Ansicht → Navigation → Wie im CAD — mittlere Taste dreht, rechts zoomt; o: Einstellungsdialog |
| 263 | `menu.32` | Ansicht > Navigation: Wie in Blender — links wählt, mittlere Taste dreht | c | c: Ansicht → Navigation → Wie in Blender — links wählt, mittlere Taste dreht; o: Einstellungsdialog |
| 264 | `menu.33` | Hilfe: Beispiele | c | c: Hilfe → Beispiele |
| 265 | `menu.34` | Hilfe: Zusätzliche Programme … | c | c: Hilfe → Zusätzliche Programme … |
| 266 | `menu.35` | Hilfe: Tastenkürzel … | c | c: Hilfe → Tastenkürzel …; d: Kürzel ? |
| 267 | `menu.36` | Hilfe: Erste Schritte … | c | c: Hilfe → Erste Schritte … |
| 268 | `menu.37` | Hilfe: Rückmeldung senden … | c | c: Hilfe → Rückmeldung senden … |
| 269 | `menu.38` | Hilfe: Nach einer neuen Version sehen | c | c: Hilfe → Nach einer neuen Version sehen |
| 270 | `menu.39` | Hilfe: Neuerungen … | c | c: Hilfe → Neuerungen … |
| 271 | `menu.40` | Hilfe: Solidon freischalten … | c | c: Hilfe → Solidon freischalten … |
| 272 | `menu.41` | Hilfe: Solidon3D unterstützen … | c | c: Hilfe → Solidon3D unterstützen …; o: Startbildschirm |
| 273 | `menu.42` | Hilfe: Über Solidon | c | c: Hilfe → Über Solidon |
