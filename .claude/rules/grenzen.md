---
description: "Die Oberfläche wächst nicht mit — die gezählten Grenzen, was wo steht (Menüleiste, Karte der Handlungen, Kontextmenü, Palette), Zwillinge und Kernwechsel, Sperrgründe vor dem Dialog, Kürzel, Sortierung und Suche; wer eine Zahl erhöht, begründet es"
paths:
  - "app/core/registry/**/*.py"
  - "app/ui/main_window.py"
  - "app/ui/panels.py"
  - "app/ui/op_dialog.py"
  - "app/ui/tool_strip.py"
  - "app/ui/command_palette.py"
  - "app/ui/catalog.py"
  - "app/ui/selection_operations.py"
---

# Regeln für die Grenzen der Oberfläche

Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche (§2). Die Regel
lädt auch im Register, denn wer eine Operation einträgt, erweitert ein Menü;
`oberflaeche.md` gilt zusätzlich. Warum:
`konzepte/begruendungen/regel-grenzen.md`.

## Die Oberfläche wächst nicht mit

Die Zahlen hält `tests/test_interface_limits.py`, die Breitengrenze
`tests/test_sketch_editor.py` (sie braucht ein gebautes Fenster mit Thema):

| Grenze | Wert |
|---|---|
| Menüs in der Leiste | ≤ 9 |
| Zeilen in einem Menü (ein Untermenü zählt als eine) | ≤ 12 |
| Umschalter in der Werkzeugzeile | ≤ 8 — heute sieben: Schnitt, Messen, Bewegen, Analyse, Schichten, Explosion, Teilen — auf `Alt+1` bis `Alt+7` |
| Felder auf der Vorderseite eines Operationsdialogs, gezählt, was zugleich dasteht (Felder anderer Varianten stehen nicht da) | ≤ 4, bei mindestens 90 % der Operationen ≤ 3 (Bauplan §2.4, Entscheidung Robert) |
| Wörter über dem ersten Feld (Platzierungssatz, erster Satz der Beschreibung, Überschrift „Wann nicht?“) | ≤ 25, übersetzt ≤ 35 |
| Breite des Skizzenbereichs, der Werkzeug- und der Bedingungszeile | je ≤ 900 Bildpunkte |
| Menüeinträge je Operation | höchstens 1 — zusammengelegte Zwillinge (`MENU_TWINS`) haben 0 und leben im Dialog ihres Partners, erreichbar über Palette und Verlauf |

Wer eine Zahl erhöhen will, tut es mit Absicht und begründet es im Commit. Der
achte Platz der Werkzeugzeile ist keine Einladung: Eine Funktion, die eine
Leiste will, verdrängt eine andere oder ist keine wert (`MAX_TOOLS`).

**Gefaltet wird je Kategorie und nur so weit, bis der Rest passt:**
`folded_categories` (`registry/surfaces.py`, auch für `menu_path`) nimmt die
hinteren Kategorien aus `MENU_GROUPS`. Eine direkte Kategorie trägt ihren Namen
als Überschrift, außer sie ist die einzige; die direkten stehen vor den
gefalteten, getrennt durch einen nackten Trennstrich.

## Wo eine Operation steht

- **Was einer Auswahl gilt, steht rechts in der Karte der Handlungen — und nur
  dort** (Entscheidung Robert): `PANEL_CATEGORIES` (`registry.py`),
  `in_the_menu_bar`, und `_build_menus` legt dafür kein Menü an. Die Aktionen
  entstehen trotzdem am Fenster (Kürzel, Palette über `_op_actions` und das
  Feld *Funktion suchen …* oben, Kürzelübersicht „Handlungen rechts“); **nackte Tasten bleiben an Objektbaum
  und Ansicht** (`_scope_shortcut`), sonst läge Entf über *Schritt löschen*, und
  zwei Aktionen auf einer Taste führt Qt beide nicht aus.
- **In der Leiste bleibt, was keine Auswahl braucht:** *Datei*, *Bearbeiten*,
  *Erzeugen* samt *Bausteine* (Katalog, Gegenstücke, Deckel ohne Kachel),
  *Ansicht*, *Hilfe*; *Automatisch teilen* steht in der Karte
  (`add_window_action`).
- **Ein Text, eine Wirkung** (RM-507): gleicher Menütext ist dieselbe
  `QAction`; Dialoge bestätigen mit `op_dialog.accept_text`; sichtbarer und
  zugänglicher Name kommen aus einem Schlüssel.
- **Den Menüort einer Operation mit Auswahl entscheidet ihre Kachel, nicht ihre
  Kategorie:** `catalogue_operations()` (`surfaces.py`) ist die Quelle für
  Leiste, Karte, `menu_path` und Wächter; `create_lid` und `screw_lid` stehen
  ohne Kachel an der Fläche **und** unter *Erzeugen → Bausteine*.
- **Zum Katalog in einem Klick, wenn das Teil gewählt ist** (Entscheidung
  Robert): Hauptknopf *Bausteine*, dazu *Datei → Bausteinkatalog …*, Strg+K,
  *Erzeugen → Bausteine*
  (`test_a_chosen_part_reaches_the_catalogue_in_one_click`).
- **Der Katalog führt aus seiner Sperre hinaus:** Bei genau einem Körper gilt
  ein Baustein ihm, auch ohne Auswahl, wie die Palette (`MainWindow._lone_body`); in der leeren
  Szene stehen unter dem Satz die Wege, die er nennt (`PartCatalog.offer_ways`:
  *Quader anlegen*, *Modell einfügen …*). Ein modaler Katalog, der „wählen Sie
  im Objektbaum“ sagt, ist eine Sackgasse (RM-356).
- **Das Kontextmenü an Körper und Merkmal trägt keine Operationen**
  (Entscheidung Robert), nur *Diesen Schritt ändern*, *Auf dieser Fläche
  zeichnen* und die Sichtbarkeit; der Viewport zeigt dasselbe Menü.
- **Der Wegweiser nennt den Ort:** `menu_path` schreibt „Handlungen rechts
  (bei gewähltem Körper) → Vereinigen“, „(bei gewähltem Merkmal: Fläche)“,
  „(ohne Auswahl)“ oder „Befehlspalette“, sonst den Menüweg; Werkzeugbeschreibungen
  und Palettenzeilen nennen ihn mit „Ort:“, Handbuch und Tour dieselben Orte
  (`test_every_menu_path_in_the_texts_exists_in_the_menu_bar`).
- **`HANDLE_INSTEAD`** (`panels.py`): An der Bohrung ist der Griff die Zeile
  *Zum Langloch ziehen* (der Doppelklick im Baum startet die erste passende
  Handlung); am Langloch bleibt sie, dort ist sie die einzige.
- **Ein Wächter ist so scharf wie seine weiteste Ausnahme** — geprüft an ihren
  Rändern, nicht am Normalfall.

**Jede neue Funktion nennt ihren Hauptweg** (§2.2), bevor sie einen Platz
bekommt:

| Weg | Ort an der Oberfläche |
|---|---|
| Weg 1 — fremdes Modell anpassen | Auswahlfenster am Merkmal, Vorschlag im Prüfbericht, Werkzeugzeile (*Teilen*: zwei Klicks legen die Ebene, Verbinder vorgewählt) |
| Weg 2 — neu konstruieren | obere Werkzeugleiste („Zeichnen“: erst skizzieren, die Erzeugungsart fragt der Dialog bei „Fertig“), Menü *Erzeugen*, Karte der Handlungen; Grundkörper tragen vorn *Maße als Parameter anlegen* (§13) |
| Weg 3 — generieren | Chat, Generierungsdialog, Einladung der leeren Szene |
| Weg 4 — organisch formen | obere Werkzeugleiste (*Formen*, *Skelett* — am gewählten oder einzigen Körper, sonst sagen sie es vorher) |
| keiner der vier | Untermenü und Befehlspalette, sonst nichts |

## Die Karte der Handlungen

Was vorn steht, richtet sich nach Art und Menge der Auswahl (Entscheidung
Robert).

- **Die Rangfolge steht in `selection_operations.py`** (`quick_names(bodies,
  feature_kind)` über `QUICK_BODIES`, `QUICK_BODY`, `QUICK_FEATURES`,
  `QUICK_FEATURE`) — eine Empfehlung, keine Aufzählung; Unvollständigkeit ist
  hier kein Fehler. Aus dem Register herleiten lässt sie sich nicht:
  Kategorie-Rang und Kürzel sind kein Häufigkeitssignal.
- **Am einen gewählten Körper steht *Modell nachbauen* bei den Hauptaktionen**
  (`selection_operations.REBUILD`, RM-508): ein Dialog, keine Operation; er
  steht nur, wenn er geht (`MainWindow._rebuild_allowed`), nie im Bericht.
- **Das Merkmal hat Vorrang vor der Menge** — wer eine Bohrung anklickt,
  meint sie, nicht den Körper darunter; bei mehreren markierten Zeilen gibt der
  Baum kein gewähltes Merkmal zurück. Mehrere markierte Merkmalszeilen eines
  Körpers bieten vorn *Als Muster zusammenfassen* (`QUICK_SEVERAL_FEATURES`,
  `MainWindow._several_features_chosen`).
- **Eine Art ohne eigene Zeile bekommt die generischen Merkmalshandlungen**
  (ändern, verschieben, entfernen) — **nur, soweit das Register sie an ihr
  anbietet:** `quick_names` schneidet gegen `REGISTRY.for_feature(kind)`; wo es
  nichts kennt, steht nichts (`feature_requirement` fragt nur, ob **der
  Körper** ein solches Merkmal hat).
- **Eine gewählte Kante ist eine Stufe für sich:** An ihr gelten die Zeilen aus
  `perceive.actions.EDGE_OPERATIONS` oben im Merkmalfenster;
  `MainWindow.selected_feature_kind` meldet `"edge"`, sobald
  `Viewport.has_a_chosen_edge()` es sagt (der Kantenklick setzt die Baumauswahl
  auf den Körper), und `_fits_the_level` lässt die Karte leer.
- **Was das Merkmalfenster als Feld zeigt, bekommt keinen zweiten Knopf**
  (Entscheidung Robert; die Liste steht im Kern, `perceive.actions.ACTION_ORDER`,
  gelesen über `_shown_as_fields()`) — wie eine Hauptaktion nicht auch in der
  Suchliste steht. Eine Art aus lauter Feldern hat eine leere Karte (ein Test,
  der dort eine Liste verlangt, prüft die Gewohnheit); wer eine Handlung aus der
  Karte nimmt, zählt je Merkmalsart nach, was übrig bleibt (*Senken* am Kegel
  hat eine eigene Zeile in `QUICK_FEATURES`).
- **Die Suchliste folgt der Menüleiste, in jeder Sprache** (`_card_group`:
  `menu_rank`; eine Kategorie, die das Menü faltet, ist eine eigene Gruppe, die
  der Werkzeugzeile steht am Ende ihrer Gruppe, `TOOL_STRIP_CATEGORIES`),
  Einträge nach `sort_key`; eine Gruppe über der Menügrenze beginnt zugeklappt
  (`OPEN_UP_TO` = `MAX_SUBMENU_ENTRIES`, `test_interface_limits`), gerechnet an
  der Stufe. Eine selbst bewegte Klappe bleibt über Auswahlwechsel (`clicked`,
  nicht `toggled`); ein Suchtreffer öffnet seine Gruppe.
- **Der Knopf *Bausteine* ist ein Hauptknopf** an Körper und Fläche, an der
  Bohrung *Passende Bausteine …* mit gefiltertem Katalog (`MATCHING_PARTS_AT`),
  an der Verrundung keiner (Entscheidung Robert). **Ohne Auswahl bleibt er**,
  von der Operationsliste nur das Folgende.
- **Handlungen für alle Körper (`takes_whole_scene`) stehen nur ohne Auswahl**
  (Entscheidung Robert), in der Karte davon nur `SCENE_ACTIONS_IN_THE_CARD`
  (`surfaces.py`), die übrigen in der Palette.
  Darüber steht „Gilt für alle Körper.", ohne Suchfeld; ein
  Suchtext von der letzten Auswahl filtert dort nichts weg
  (`SelectionOperationsPanel._without_a_selection`).
- **Eine Karte ohne Liste lädt nicht zum Suchen ein:** Das Suchfeld verschwindet
  mit der Liste, ein Satz nennt, wo die Handlungen stehen; wer sucht und nichts
  findet, behält es, mit *In allen Funktionen suchen* (Palette, dasselbe Wort).
  Beide Leeren setzt eine Stelle
  (`SelectionOperationsPanel._only_this_sentence`).
- **Was der Filament-Schnellwähler trägt, steht nicht auch in der Liste**
  (`PICKER_HANDLES`), und in der leeren Karte tritt er beiseite
  (`MainWindow._update_actions`; das Lager steht in Kopfzeile und Menü). **Wer
  eine Karte für einen neuen Zustand öffnet, prüft, welche leeren Zustände darin
  zum ersten Mal sichtbar werden.**
- **Eine Beschriftung, die nicht in ihre Spalte passt, bricht um:** Die
  Zweierspalte fragt, ob **jede** in ihre Hälfte passt; `_wrap_label` bricht an
  einer Wortgrenze auf höchstens zwei Zeilen, gemessen an der zeichnenden
  Schrift (Beiwerk aus der Differenz zum Wunschmaß). Der ganze Titel bleibt als
  `operationTitle` am Knopf, denn die Suche braucht ihn.

## Die Vorderseite eines Dialogs

Was vorn steht und wie bedingte Felder erscheinen, steht in `vorderseite.md`;
sie lädt mit Operationsdialog, Merkmalfenster und Parameterschema.

- **Leere Materialrollen beginnen mit dem Projektmaterial**
  (`MainWindow.run_operation`), ausdrückliche Werte haben Vorrang. Beim
  Wiederöffnen bleiben die gespeicherten Rollen stehen.
- **Auch ein Sammeleintrag beginnt am gemeinsamen Einstieg**
  (`MainWindow.launch_operation`): *Zeichnen …* öffnet unmittelbar
  die Zeichnung, wie Palette und Kürzel.

## Zwillinge: eine Handlung, zwei Rechenkerne

**Eine Operation je Handlung, nicht je Variante:** Neun Texturmuster sind ein
Eintrag mit Auswahlparameter, Rechteck aus zwei Ecken oder aus Mitte und Maß
ein Werkzeug mit Umschalter. **Erzeugen und Schneiden mit demselben Werkzeug
sind zwei Handlungen** (ein Erzeuger nimmt nichts, ein Schnitt den gewählten
Körper) — die Eingangszahl steht je Operation fest, und der Stapel vergibt die
Kennungen vor der Rechnung: eigene Operationen (`sketch_revolve_cut` neben
`sketch_revolve`, `sketch_pocket` neben `sketch_extrude`), aber kein eigener
Eintrag, sondern die Variantengruppe ihres Erzeugers
(`konzepte/konzept-vollwertiges-cad-2026-09.md`, Abschnitt 10).

**Die Mesh/B-Rep-Zwillinge** (Quader, Zylinder, Bohrung, Aushöhlen) haben
**einen** Eintrag; `menu_twins()` sagt, welcher ihn trägt, auch für den
Menüort des Agenten (§2.6). Der Zwilling heißt **genau** wie sein Partner
(`create_brep_box` „Quader anlegen“, `drill_brep_hole` „Bohrung setzen“):
Der Kunde sucht das Substantiv, die Palette sortiert nach Titel, und ein Wort
davor läse sich wie eine Qualitätsstufe. Wo der versteckte steht, sagt
`TWIN_WAYS` („über die Befehlspalette“ bzw. „im selben Dialog — der Körper
entscheidet“); im Menü steht er nicht (`hidden_from_the_menu`), und weggelassen
wird er nur, wenn sein Partner angeboten wird. **Was die beiden trennt, ist der
erste Satz ihres `doc`** — die Palette zeigt ihn unter dem gleichen Titel, beim
exakten Erzeuger mit dem Vorteil („mit echten Kanten“).
`tests/test_ui.py::test_twins_differ_in_the_sentence_the_palette_shows` prüft
jedes Paar in jeder Sprache ohne Fenster.

**Es gibt keinen Kernwahl-Haken** (Entscheidung Robert; CAD-Konzept Abschnitt
10.1): Ein Grundkörper entsteht exakt, wo der exakte Kern da ist
(`registry.menu_twins()`, faul, denn die Antwort lädt OpenCASCADE; der
Netz-Zwilling steht in der Befehlspalette, der Agent liest an ihm „Zweite
Wahl“). *Bohrung setzen* und *Aushöhlen* fragen die Körperart ihres Eingangs
(`operationen.md`, „Den Kern wählt der Körper, nicht der Kunde“;
`hollow_object`: oben offen bleibt exakt, eine Entlüftung zählt dort nicht,
sonst Netzweg mit Hinweis über `evaluate.exact_became_mesh`). Ohne exakten
Kern bleiben die Netz-Erzeuger sichtbar — ein erklärter Weg, kein stilles
Scheitern; gespeicherte Schritte behalten ihren Kern.

**Der Wechsel steht am Schritt, nicht im Dialog:** `History.change_kernel` aus
dem Kontextmenü des Verlaufs (`HistoryPanel.kernelSwitchRequested`,
`MainWindow.switch_kernel`), mit einem Satz, der den Nutzen nennt, nie den
Rechenkern (`registry.kernel_switch_label`: „Mit echten Flächen und Kanten
rechnen“, „Als Dreiecksmodell rechnen“). Zwei Sperren vor dem Klick: in den
exakten Kern nur, wenn er da ist (sonst fehlt der Eintrag; das Fenster prüft den
direkten Aufruf ein zweites Mal); ins Netz nur, wenn kein späterer Schritt
bearbeitbare Flächen braucht (`needs_exact`). Getauscht wird nur zwischen den
Grundkörpern aus `PRIMITIVE_TWINS`; an Bohren und Aushöhlen entscheidet der
Körper.

**Zwei Zeilen mit demselben Text sind eine Frage ohne Antwort:** Menüleiste und
Auswahlfenster legen `MENU_TWINS` gleich zusammen; `surfaces.context_menu()`
bleibt die **Rohmenge** (`tests/test_acceptance_p0.py`). Gezählt wird am
gebauten Menü („kein Kontextmenü zeigt zwei Zeilen mit demselben Text“) —
ein Test, der `operations_for_feature` als Sollmenge nimmt, schrumpft mit einem
Filter darin still mit.

## Der Satz kommt vor den Dialog

- **Ein Zwilling, der eine Bedingung hat, fragt sie — vorher:** Das Menü graut
  eine Operation mit `requires_kind="brep"` an einem Netz aus, mit dem Grund im
  Tooltip. Eine Kette (`_reason_locked`) speist Menüleiste, Kontextmenü,
  Auswahlkarte und die Variantenliste im Dialog; der Satz des Kerns bleibt die
  zweite Hürde. Wer einen Zwilling mit Eingang dazunimmt, nimmt diese Frage mit.
- **Ein gesperrtes Werkzeug kennt zwei Lagen:** War der Körper nie exakt, liegt
  der Weg am Erzeugerschritt; hat ihn eine Mesh-Operation vernetzt, nur an
  diesem Schritt — `spoiled_the_exact_body()` liest ihn aus
  `evaluate.exact_became_mesh`, `kind_requirement` nennt ihn beim Titel. Der
  Vorschlag ist ausführbar (keinen Schritt hinter die schieben, die ihn
  brauchen). Mit `requires_kind="mesh"` sagt ein Werkzeug am exakten Körper
  *Flächenbearbeitung beenden*.
- **Auch ohne Feld:** *Vereinigen*, *Abziehen*, *Auf das Bett setzen* und Entf
  laufen an exakten Körpern ohne Dialog (Regel 19); einen Dialog gibt es nur,
  wenn die Handlung den Körper umwandeln kann — das Register verlangt ein Netz,
  oder die Eingänge sind gemischt (`MainWindow._order_may_convert`).
- **Was am gewählten Körper nie etwas tun kann, sagt es am Menüeintrag**
  (`requires_body` und `lid.reason_against`, deklariert nach `operationen.md`,
  „Was die Operation verlangt, steht im Register“) — *Offene Fläche schließen*,
  *In Einzelteile aufteilen*, *Gitter füllen*, die Deckel an der gewählten
  Fläche, einmal je Merkmal und Auswertung gerechnet; *An Merkmal ausrichten*
  verlangt sein Ziel (`_NEEDS_TARGET`), und der Dialog sperrt mit demselben
  Satz, wenn die Liste leer ist. Was an einer Zahl im Dialog hängt, sagt das
  Vorschauband.
- **Ein Menü zeigt Hinweise nur, wenn man es ihm sagt:** `QMenu` hat
  `toolTipsVisible == False`, **Untermenüs erben es nicht** — jedes Menü mit
  gesperrten Handlungen setzt es (die Menüleiste an ihren drei Stellen, das
  Kontextmenü am Körper, das der Skizze), und wer einen Grund schreibt, prüft
  `toolTipsVisible()` mit. **Grau ohne Grund gibt es auch ohne
  `requires_kind`:** Die Bedingungen der Skizze holen ihren Halbsatz aus
  `_needs_phrase`, derselben Quelle wie Knopf und Kürzelmeldung.

## Eine Grenze steht dort, wo gewählt wird

`caveat` im Registereintrag sagt, wann eine Operation die falsche Wahl ist.
Dreiundsiebzig von hundertachtundsiebzig Operationen tragen einen (die Zahl prüft
`tests/test_registry_consistency.py`). `caveat_line()` (`surfaces.py`) ist die
eine Quelle und trägt das Wort davor, sonst liest sich die Grenze als
Fortsetzung des `doc`-Satzes: im Tooltip unter dem Satz, beim Agenten in der
Werkzeugbeschreibung — **nie in der Statuszeile**, denn eine abgeschnittene
Warnung ist schlimmer als keine. Im Dialog steht sie zugeklappt unter „Wann
nicht?“ (die Überschrift ist die zweite Kodierung, Regel 18; ihr Tooltip trägt
den Satz), damit über dem ersten Feld nur ein Satz steht (RM-513).

## Ein erzeugtes Merkmal bietet den Schritt an, der es erzeugt hat

*Diesen Schritt ändern* (§21.2) steht im Kontextmenü am Merkmal ganz oben, vor
der Sichtbarkeit — der einzige Weg vom Ergebnis zurück zum Schritt. Gefragt wird
über `Feature.created_by`, damit **ein** Eintrag jede Merkmalsart mitnimmt; ein
erkanntes Merkmal trägt `None` und bekommt ihn nicht. `thread` bleibt in den
`known_gaps` von `tests/test_registry_consistency.py` (die Prüfung fragt
`applies_to`) — wer die Ausnahme streicht, macht den Test rot. Erzeugte
Merkmale kommen aus Bausteinen (`knowledge/parts/build.py`) und dem
Verstiften, nicht aus `drill_hole` — wer den Eintrag testet, nimmt einen
Baustein.

## Ein Zeichen darf allein stehen, als geeinigtes Bild oder an fester Stelle

Die Skizzenwerkzeuge leben vom ersten Fall, die obere Werkzeugleiste vom zweiten
(sieben Knöpfe an fester Stelle, wenige an der Zahl, der Tooltip nennt Namen,
Kürzel und Zweck). Die Werkzeugzeile unter dem Viewport bleibt beschriftet: Ihre
Umschalter wechseln mit dem Zustand, und für „Schnitt“ und „Explosion“ gibt
es kein Bild.

- **Wo das Wort vom Knopf verschwindet, steht es an drei Stellen weiter:**
  `QAction`, Tooltip, `statusTip` — den Satz holt `_button_tip` aus dem
  Menüeintrag derselben Handlung. `_lock_hint` und `_pick_hint` stellen ihren
  Hinweis aus dem `statusTip` her — ein ungesetzter macht den Knopf nach dem
  Freischalten stumm; `_with_name` stellt am wortlosen Knopf den Namen voran
  (`wordless` am `QAction`), getrennt mit dem Zeichen, das der Satz nicht schon
  führt (Gedankenstrich vor dem Zweck, Doppelpunkt vor einem Grund mit
  Gedankenstrich).
- **Die Kopfzeile geht vor:** Erst verlieren die sieben Knöpfe ihr Wort, dann
  die Suche *Funktion suchen …*, die als Lupe bleibt (`_fit_toolbar`, drei
  Formen); gemerkt wird je Form, was sie ohne die Kopfzeile braucht.
- **Keiner der sieben Umschalter verschwindet:** `ToolStrip.set_tool_usable`
  graut ihn mit Grund (Explosion: „Dafür braucht es zwei Körper in der
  Szene.“), und `_update_actions` fragt ihn **nach** der Freigabe aller — eine
  Zeile, die sich beim Laden einer Datei umbaut, wirkt unzuverlässig.
- **Wer eine Beschriftung ausblendet, zieht Handbuch (`app/core/manual.py`) und
  Tour (`app/core/tour.py`) mit** — die Tour zuerst, ihre `done=`-Schritte
  rücken sonst nicht weiter.

## Ein Kürzel folgt dem deutschen Titel

*Bohrung setzen* Strg+B, *Drehen* Strg+R, *Aushöhlen* Strg+H; Kürzel stehen im
Register, eine Übersetzung ändert sie nicht. Ist der Buchstabe belegt, kommt
Umschalt dazu (*Vereinigen* Strg+Umschalt+V, *Abziehen* Strg+Umschalt+A); ist
auch das belegt, **bleibt die Operation ohne Kürzel** — *Skalieren*: S und
Umschalt+S gehören dem Speichern, und ein erfundener Buchstabe wäre schlechter
als keiner. Wer eine Taste vergibt, prüft vorher am gebauten Fenster gegen die
Kürzel, die nicht aus dem Register kommen (Ansichten, Werkzeugzeile,
Dateibefehle, Navigation): Eine doppelt belegte Taste führt keine der beiden
Aktionen aus („Ambiguous shortcut overload“). `tests/test_ui.py`
(`test_no_two_shortcuts_in_the_window_collide`) hält das,
`tests/test_registry_consistency.py` sieht nur das Register.

**Löschen und Wiederholen binden ihre Tasten je Plattform aus einer Quelle**
(`shortcut_schemes`): `delete_keys`/`deletes` geben am Mac zu Entf die Taste
⌫ (seine Taste „delete“ sendet Backspace), `redo_keys` gibt unter Linux zu
Qts Strg+Umschalt+Z die Taste Strg+Y, die Tour und Texte nennen. Wer eine
dieser Handlungen bindet oder eine Taste dafür abfängt, fragt dort; beim
Messen nimmt die Ansicht die Rücktaste vor dem Kürzel an (letztes Maß).

## Sortiert wird nach dem Titel, gesucht in der Sprache des Kunden

**Was zur Auswahl passt, steht vorn:** `applies_to` ordnet Kontextmenü und
Befehlspalette (`palette_entries(for_feature=...)`) — eine Reihenfolge, keine
Auswahl; eine Palette, die aussortiert, wäre eine Betriebsart. **Sortiert wird
nach dem Titel, überall mit `i18n.sort_key`** (Menüleiste über `by_category`,
Palette, Kontextmenü, Karte) — nicht nach `Registry.all()`, nicht mit `str` oder
`casefold`: „ä“ zählt wie „a“ (DIN 5007-1). Die **Suchfaltung**
`registry.search.fold` ist etwas anderes („ä“ → „ae“ für „aushoehlen“);
der Kommentar an jeder Tabelle sagt, welche sie ist.

**Die Suche antwortet in drei Runden, jede nur bei Bedarf:** genau, dann am
Wortstamm („bohren“ → *Bohrung setzen*), zuletzt für mehrere Wörter
**irgendeines**, nach Trefferzahl — mit einer Zeile darüber, die das sagt, denn
eine Liste, die still weniger prüft, sähe aus wie eine genaue. Die Kundenwörter
stehen je Sprache im Katalog (`registry.search.CUSTOMER_WORDS`, Kontext
„Suchwörter“): Ein Titeltreffer mitten im Wort zählt nach ihnen, die Wörter
einer Anfrage stehen in **einer** Wendung, und die ungenauen Stufen
(`LOOSE_RANK`) werten wie der Agent (`rank_entries`).

**Die Kundenwörter gehören der Palette, nicht dem Agenten:** Er wertet nur
`SYNONYMS` (`rank_operations`, `customer_words=False`); ihm eines zu geben
ändert sein Angebot — Suite vorher und nachher (`agentenschicht.md`). Ein neues
Kundenwort steht in allen Sprachen, ist kein Füllwort und meint über einen
kurzen Stamm kein anderes Wort
(`test_every_customer_word_belongs_to_a_row_of_the_palette` hält die Schlüssel
am Register und an den Fensterbefehlen).

**Dieselben Kundenwörter führen durch das Handbuch** (`core/manual_search.py`):
Es faltet mit `fold`, wägt mit `strength` und liest die Kundenwörter über
`customer_phrases` und `says`; nennt eine Suche genau die Wendung einer
Operation, sucht es zusätzlich deren Titel als Wortfolge. Ein neues Kundenwort
ändert also auch, wo das Handbuch aufschlägt (`tests/test_manual_search.py`
misst die Quote, Konzept Handbuch §11). Eine eigene Wortliste des Handbuchs wäre ein Zwilling dieser
Tabelle (`zwillinge.md`).
