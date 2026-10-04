---
description: "Die Oberfläche wächst nicht mit — die gezählten Grenzen, was wo steht (Menüleiste, Karte der Handlungen, Kontextmenü, Palette), die Vorderseite eines Dialogs, bedingte Felder, Zwillinge und Kernwechsel, Sperrgründe vor dem Dialog, Kürzel, Sortierung und Suche; wer eine Zahl erhöht, begründet es"
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
| Umschalter in der Werkzeugzeile | ≤ 8 — heute sieben: Schnitt, Messen, Bewegen, Analyse, Schichten, Explosion, Trennen — auf `Alt+1` bis `Alt+7` |
| Felder auf der Vorderseite eines Operationsdialogs, gezählt, was zugleich dasteht (Felder anderer Varianten stehen nicht da) | ≤ 8 |
| Breite des Skizzenbereichs, der Werkzeug- und der Bedingungszeile | je ≤ 900 Bildpunkte |
| Menüeinträge je Operation | höchstens 1 — zusammengelegte Zwillinge (`MENU_TWINS`) haben 0 und leben im Dialog ihres Partners, erreichbar über Palette und Verlauf |

Wer eine Zahl erhöhen will, tut es mit Absicht und begründet es im Commit. Der
achte Platz der Werkzeugzeile ist keine Einladung: Eine Funktion, die eine
Leiste will, verdrängt eine andere oder ist keine wert (`MAX_TOOLS`).

**Gefaltet wird je Kategorie und nur so weit, bis der Rest passt:**
`folded_categories` (`app/core/registry/surfaces.py`) nimmt die hinteren
Kategorien aus `MENU_GROUPS` (dort von häufig nach selten); die Rechnung liegt
im Kern, damit `menu_path` dieselbe Antwort gibt wie die Leiste. Eine direkt
stehende Kategorie behält ihren Namen als Überschrift (`addSection`; zählt nicht
in der Zeilengrenze, `isSeparator()` bleibt wahr), außer sie ist die einzige
(„Bausteine → Bausteine“). Die direkten stehen vor den gefalteten, getrennt
durch einen nackten Trennstrich, denn eine Überschrift benennt alles bis zum
nächsten. Wer eine Unterscheidung einführt, führt die Anordnungsfrage mit ein.

## Wo eine Operation steht

- **Was einer Auswahl gilt, steht rechts in der Karte der Handlungen — und nur
  dort** (Entscheidung Robert): `PANEL_CATEGORIES` (`registry.py`),
  `in_the_menu_bar`, und `_build_menus` legt dafür kein Menü an. Die Aktionen
  entstehen trotzdem am Fenster (Kürzel, Palette über `_op_actions`,
  Kürzelübersicht „Handlungen rechts“); **nackte Tasten bleiben an Objektbaum
  und Ansicht** (`_scope_shortcut`), sonst läge Entf über *Schritt löschen*, und
  zwei Aktionen auf einer Taste führt Qt beide nicht aus.
- **In der Leiste bleibt, was keine Auswahl braucht:** *Datei*, *Bearbeiten*
  (mit *Automatisch teilen*), *Erzeugen* samt Abschnitt *Bausteine* (Katalog,
  Gegenstücke, Deckel ohne Kachel; `parts` steht in der Gruppe *Erzeugen*),
  *Ansicht*, *Hilfe*.
- **Den Menüort einer Operation mit Auswahl entscheidet ihre Kachel, nicht ihre
  Kategorie:** `catalogue_operations()` (`surfaces.py`) ist die Quelle für
  Leiste, Karte, `menu_path` und Wächter; `create_lid` und `screw_lid` stehen
  ohne Kachel an der Fläche **und** unter *Erzeugen → Bausteine*.
- **Zum Katalog in einem Klick, wenn das Teil gewählt ist** (Entscheidung
  Robert): Hauptknopf *Bausteine*, dazu *Datei → Bausteinkatalog …*, Strg+K,
  *Erzeugen → Bausteine*
  (`test_a_chosen_part_reaches_the_catalogue_in_one_click`).
- **Der Katalog führt aus seiner Sperre hinaus:** Bei genau einem Körper gilt
  ein Baustein ihm, auch ohne Auswahl (`MainWindow._lone_body`); in der leeren
  Szene stehen unter dem Satz die Wege, die er nennt (`PartCatalog.offer_ways`:
  *Quader anlegen*, *Modell einfügen …*). Ein modaler Katalog, der „wählen Sie
  im Objektbaum“ sagt, ist eine Sackgasse (RM-356).
- **Das Kontextmenü an Körper und Merkmal trägt keine Operationen**
  (Entscheidung Robert), nur *Diesen Schritt ändern*, *Auf dieser Fläche
  zeichnen* und die Sichtbarkeit; der Viewport zeigt dasselbe Menü.
- **Der Wegweiser nennt den Ort:** `menu_path` schreibt „Handlungen rechts
  (bei gewähltem Körper) → Vereinigen“ bzw. „(bei gewähltem Merkmal:
  Fläche)“, sonst den Menüweg; Werkzeugbeschreibungen beginnen mit „Ort:“,
  Handbuch und Tour nennen dieselben Orte
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
| Weg 1 — fremdes Modell anpassen | Auswahlfenster am Merkmal, Vorschlag im Prüfbericht, Werkzeugzeile (*Trennen*: zwei Klicks legen die Ebene, Verbinder vorgewählt) |
| Weg 2 — neu konstruieren | obere Werkzeugleiste („Zeichnen“: erst skizzieren, die Erzeugungsart fragt der Dialog bei „Fertig“), Menü *Erzeugen*, Karte der Handlungen; Grundkörper tragen vorn *Maße als Parameter anlegen* (§13) |
| Weg 3 — generieren | Chat und Generierungsdialog |
| Weg 4 — organisch formen | obere Werkzeugleiste (*Formen*, *Skelett* — beide brauchen einen gewählten Körper und sagen das vorher) |
| keiner der vier | Untermenü und Befehlspalette, sonst nichts |

## Die Karte der Handlungen

Was vorn steht, richtet sich nach Art und Menge der Auswahl (Entscheidung
Robert).

- **Die Rangfolge steht in `selection_operations.py`** (`quick_names(bodies,
  feature_kind)` über `QUICK_BODIES`, `QUICK_BODY`, `QUICK_FEATURES`,
  `QUICK_FEATURE`) — eine Empfehlung, keine Aufzählung; Unvollständigkeit ist
  hier kein Fehler. Aus dem Register herleiten lässt sie sich nicht:
  Kategorie-Rang und Kürzel sind kein Häufigkeitssignal.
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
- **Die Suchliste ist nach `group_title(spec.category)` gefaltet**
  (`panels.collapsible`); eine Gruppe über der Menügrenze beginnt zugeklappt
  (`OPEN_UP_TO` = `MAX_SUBMENU_ENTRIES`, `test_interface_limits`), gerechnet an
  der Stufe. Eine selbst bewegte Klappe bleibt über Auswahlwechsel (`clicked`,
  nicht `toggled`); ein Suchtreffer öffnet seine Gruppe.
- **Der Knopf *Bausteine* ist ein Hauptknopf** an Körper und Fläche, nicht an
  Bohrung oder Verrundung (Entscheidung Robert). **Ohne Auswahl bleibt dieser
  Weg** (Entscheidung Robert), von der Operationsliste nur das Folgende.
- **Handlungen für alle Körper stehen, wenn nichts gewählt ist — und nur dann**
  (Entscheidung Robert): welche, sagt das Register (`takes_whole_scene`:
  *Druckoptimal ausrichten*, *Auf dem Bett anordnen*, *Überschneidungen
  prüfen*). Am gewählten Körper sagte der Knopf, er gelte diesem Körper, und
  nahm doch alle. Darüber steht „Gilt für alle Körper.", ohne Suchfeld; ein
  Suchtext von der letzten Auswahl filtert dort nichts weg
  (`SelectionOperationsPanel._without_a_selection`).
- **Eine Karte ohne Liste lädt nicht zum Suchen ein:** Das Suchfeld verschwindet
  mit der Liste, ein Satz nennt, wo die Handlungen stehen; wer sucht und nichts
  findet, behält es. Beide Leeren setzt eine Stelle
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

- **Ein vorbelegter Wert kommt nach vorn, außer er ist eine Richtung:**
  `decided` (`op_dialog.py`) holt angeklickte Fläche und vorgewählte Position
  (§18.5) vor die Klappe; `direction_fields` (Normale aus `normal_fields_of`,
  `axis`) bleiben hinten und gelten trotzdem.
- **Die Vorgabe trifft den Körper, nicht den Ursprung:** *Teilen* in seiner
  Mitte (`_plane_through`), *Dreiecke verringern* bei der Hälfte seiner
  Dreiecke, *Dreiecke angleichen* bei einem Fünfzigstel seiner längsten Kante
  (`_measured_from_body`, `EDGE_SHARE`) — gefragt nach den Feldern
  (`axis`/`position`, `triangles`, `edge`), nicht nach der Operation; die Zahl
  bleibt änderbar. *Druckplatten* bleibt beim Höchstwert, das Feld ist eine
  Obergrenze.
- **Ein Erzeuger nimmt seine Lage nur von einer gezeigten Fläche** (RM-390):
  Ein gewählter Körper, eine Bohrung oder Kante setzen ihn nicht, er entsteht
  auf dem Bett (`values_for_object` gibt `consumes == 0` nichts). Auf einer
  gewählten Fläche steht er auf ihr und, wo nötig, in ihrer Ebene über das Bett
  gehoben (`placement.seats_on`, `seat_on_face`); vorn steht „Wird auf ‹Fläche›
  von ‹Körper› gesetzt“ mit *Auf das Bett* (`OperationDialog.show_seat`).
  Nach dem Übernehmen ist sein neuer Körper gewählt (`_queue_created_choice`).
- **Ein Grundkörper bietet an, seine Maße zu benennen** (§13, Entscheidung
  Robert): *Maße als Parameter anlegen* steht vorn in jedem Dialog der
  Kategorie `primitive` und im Erzeuger jedes Bausteins, der sich als Vorlage
  erklärt (`PartSpec.template`, die Halter; `offers_naming`). Gesetzt, wird
  jedes wirksame Millimetermaß der Vorderseite ein Projektparameter nach
  seiner Beschriftung (*Breite* → `breite`, vergeben → `breite_2`) mit
  übersetzbarem Titel und den Grenzen des Feldes, der Schritt verweist mit
  `=@breite` darauf, beides in **einer** Transaktion (`changes` an
  `Session.apply`); ein Feld mit Ausdruck bleibt, ein Feld, dessen
  `depends_on` gerade nicht gilt, wird keiner — es steht ja nicht da
  Der Haken steht beim ersten Start an und übernimmt danach die letzte Wahl
  beim Übernehmen (`UiSettings.name_dimensions`).
- **Ein Sammelparameter bekommt seinen Editor, nicht sein Speicherformat:**
  `ArmatureField` baut je Knochen drei Winkel (`ValueField`, §13), sobald der
  Dialog ein Skelett hat, sonst bleibt das Textfeld. Im Schema steht er hinten
  (`tests/test_gesture_ops.py`), im Dialog vorn, wenn er der Grund ist, aus dem
  der Dialog aufgeht.
- **Ein Umschalter zwischen Varianten schaltet den ganzen Dialog um**
  (`OperationDialog.switch_variant`): Was die Variante nicht kennt,
  verschwindet, die Beschreibung wechselt.
- **Leere Materialrollen beginnen mit dem Projektmaterial**
  (`MainWindow.run_operation`), ausdrückliche Werte haben Vorrang. Beim
  Wiederöffnen bleiben die gespeicherten Rollen stehen.
- **Auch ein Sammeleintrag beginnt am gemeinsamen Einstieg**
  (`MainWindow.launch_operation`): *Aus Skizze erzeugen* öffnet unmittelbar
  die Zeichnung, wie Palette und Kürzel.

## Bedingte Felder

Die Bedingung steht am Parameter (`ParamSpec.depends_on`), denn Dialog,
Handbuch (Parametertabelle), Agent (Werkzeugbeschreibung) und Kommandozeile
(`json_schema`) lesen sie. Der Dialog blendet ein Feld ohne Wirkung aus
(`oberflaeche.md`, „Gestufte Tiefe“): `OperationDialog._couple_dependent_fields`
nimmt es samt Beschriftung heraus und bringt es mit der Bedingung wieder;
dahinter bleibt es gesperrt und begründet, damit kein verborgenes Feld den
Fokus bekommt, und `adjustSize` läuft nur, wenn sich eine Zeile bewegt hat
(`test_a_rectangle_shows_only_the_rows_a_rectangle_has`). Im Merkmalfenster
folgt `FeaturePanel._follow_conditions` demselben `ActionField.depends_on`: Das
Feld verschwindet samt Beschriftung, kommt mit seinem Wert zurück und wird
nicht gesperrt — die Sperre gehört dem Kettenhalt (`_settle_lock`).

- **Agent und Mensch bekommen verschiedene Anreden, nicht verschiedene
  Inhalte:** „Gilt bei Art = circular“ im Handbuch, `kind` für den Agenten
  (`condition_text(..., keys=True)`), „Wirkt nur, wenn …“ im Dialog mit Werten
  durch `choice_label`.
- **`tests/test_operation_ui.py` liest den Quelltext jeder Operation** und
  meldet jeden Parameter, der nur in **genau einem** Zweig über einen Umschalter
  derselben Operation gelesen wird — nicht über einen Aufruf, der den ganzen
  Parametersatz weitergibt.
- **Ein Haken als Umschalter** braucht einen typtreuen Vergleich (über `str()`
  hieße der Wert „True“, und `1 == True`) und einen eigenen Satz.
- **Die Art des Umschalters wird mitgeprüft:** Ein Wahrheitswert an einem
  Aufklappmenü oder ein Auswahlwert an einem Haken trifft nie zu.

Maßgruppen im Bild übernehmen dieselben `depends_on`-Bedingungen wie die rechte
Spalte, einschließlich Auswahlwerten und Ketten. Der Adapter `_saved_fields`
reicht sie aus dem Parameterschema weiter. Titel, Eingabe und Ablehnung
verschwinden gemeinsam; verborgene Werte bleiben erhalten und sperren die
Übernahme nicht. Stille Wertaktualisierung und wiederverwendete Gruppen
berechnen die Sichtbarkeit erneut (`FeaturePanel._follow_measure_conditions`).

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
wird er nur, wenn sein Partner angeboten wird.

**Es gibt keinen Kernwahl-Haken** (Entscheidung Robert; CAD-Konzept Abschnitt
10.1): Ein Grundkörper entsteht exakt, wo der exakte Kern da ist
(`registry.menu_twins()`, faul, denn die Antwort lädt OpenCASCADE; der
Netz-Zwilling steht in der Befehlspalette, der Agent liest an ihm „Zweite
Wahl“). *Bohrung setzen* und *Aushöhlen* fragen die Körperart ihres Eingangs
(`operationen.md`, „Den Kern wählt der Körper, nicht der Kunde“;
`hollow_object`: oben offen ohne Entlüftung bleibt exakt, sonst Netzweg mit
Hinweis über `evaluate.exact_became_mesh`). Ohne exakten Kern bleiben die
Netz-Erzeuger sichtbar — ein erklärter Weg, kein stilles Scheitern;
gespeicherte Schritte behalten ihren Kern.

**Der Wechsel steht am Schritt, nicht im Dialog:** `History.change_kernel` aus
dem Kontextmenü des Verlaufs (`HistoryPanel.kernelSwitchRequested`,
`MainWindow.switch_kernel`), mit einem Satz, der den Nutzen nennt, nie den
Rechenkern (`registry.kernel_switch_label`: „Mit echten Flächen und Kanten
rechnen“, „Als Dreiecksmodell rechnen“). Zwei Sperren vor dem Klick: in den
exakten Kern nur, wenn er da ist (sonst fehlt der Eintrag; das Fenster prüft den
direkten Aufruf ein zweites Mal); ins Netz nur, wenn kein späterer Schritt
bearbeitbare Flächen braucht (`needs_exact`). Getauscht wird nur zwischen den
Grundkörpern aus `PRIMITIVE_TWINS` — an Bohren und Aushöhlen liefe ein
Wechsel ins Leere, dort entscheidet der Körper, und beliebige Operationen
gegeneinander wären ein Umschreiben der Geschichte.

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
  *In Einzelteile zerlegen*, *Gitter füllen*, die Deckel an der gewählten
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
Achtundsechzig von hundertdreiundsiebzig Operationen tragen einen (die Zahl prüft
`tests/test_registry_consistency.py`). `caveat_line()` (`surfaces.py`) ist die
eine Quelle und trägt das Wort davor, sonst liest sich die Grenze als
Fortsetzung des `doc`-Satzes: im Dialog ein eigenes halbfettes Label (Regel 18),
im Tooltip unter dem Satz, beim Agenten in der Werkzeugbeschreibung — **nie in
der Statuszeile**, denn eine abgeschnittene Warnung ist schlimmer als keine.

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
es kein Bild. Regel 18 verlangt eine zweite Kodierung neben der **Farbe**, nicht
eine Beschriftung neben jedem Zeichen.

- **Wo das Wort vom Knopf verschwindet, steht es an drei Stellen weiter:**
  `QAction`, Tooltip, `statusTip` — den Satz holt `_button_tip` aus dem
  Menüeintrag derselben Handlung. `_lock_hint` und `_pick_hint` stellen ihren
  Hinweis aus dem `statusTip` her — ein ungesetzter macht den Knopf nach dem
  Freischalten stumm; `_with_name` stellt am wortlosen Knopf den Namen voran
  (`wordless` am `QAction`), getrennt mit dem Zeichen, das der Satz nicht schon
  führt (Gedankenstrich vor dem Zweck, Doppelpunkt vor einem Grund mit
  Gedankenstrich).
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

## Sortiert wird nach dem Titel, gesucht in der Sprache des Kunden

**Was zur Auswahl passt, steht vorn:** `applies_to` ordnet Kontextmenü und
Befehlspalette (`palette_entries(for_feature=...)`) — eine Reihenfolge, keine
Auswahl; eine Palette, die aussortiert, wäre eine Betriebsart. **Sortiert wird
nach dem Titel, überall mit `i18n.sort_key`** (Menüleiste über `by_category`,
Palette, Kontextmenü) — nicht nach `Registry.all()`, nicht mit `str` oder
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
ändert also auch, wo das Handbuch aufschlägt — `tests/test_manual_search.py`
verlangt bei 50 Kundensuchen mindestens 80 Prozent richtige Seiten unter den
ersten drei. Eine eigene Wortliste des Handbuchs wäre ein Zwilling dieser
Tabelle (`zwillinge.md`).
