---
description: "Die Oberfläche wächst nicht mit — neun Menüs, zwölf Zeilen je Menü, acht Werkzeuge, acht Felder vorn, ein Menüeintrag je Operation; wer eine Zahl erhöht, begründet es"
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

Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche (§2). **Diese
Datei ist am 18.09.2026 aus `oberflaeche.md` ausgegliedert** — die übrigen
Oberflächenregeln gelten weiter und laden zusätzlich.

Sie lädt nicht nur in der Oberfläche, sondern auch im **Register**: Wer eine
Operation einträgt, erweitert ein Menü, und die drei Dateien, die dieser
Abschnitt am häufigsten nennt, liegen in `app/core/registry/`.

## Die Oberfläche wächst nicht mit

Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche (§2). Die Zahlen
dazu stehen in `tests/test_interface_limits.py` und werden rot, wenn sie
gerissen werden — die Breitengrenze des Skizzenbereichs in
`tests/test_sketch_editor.py`, weil sie ein gebautes Fenster **mit Thema**
braucht und nicht das Register:

| Grenze | Wert |
|---|---|
| Menüs in der Leiste | ≤ 9 |
| Zeilen in einem Menü (ein Untermenü zählt als eine) | ≤ 12 |
| Umschalter in der Werkzeugzeile | ≤ 8 — heute sieben: Schnitt, Messen, Bewegen, Analyse, Schichten, Explosion, Trennen — auf `Alt+1` bis `Alt+7` |
| Felder auf der Vorderseite eines Operationsdialogs | ≤ 8 |
| Breite des Skizzenbereichs, der Werkzeug- und der Bedingungszeile | je ≤ 900 Bildpunkte |
| Menüeinträge je Operation | höchstens 1 — zusammengelegte Zwillinge (`MENU_TWINS`) haben 0 und leben im Dialog ihres Partners, erreichbar über Palette und Verlauf |

Wer eine Zahl erhöhen will, tut das mit Absicht und begründet es im Commit.
Die Werkzeugzeile hat sieben von acht Plätzen belegt, seit das Bemalen mit dem
Punkt-Radius-Pinsel fiel — Färben läuft über das Auswahlfenster am Merkmal. Der
achte Platz ist keine Einladung: Eine Funktion, die eine Leiste will,
verdrängt eine andere, oder sie ist keine wert (`MAX_TOOLS` in
`tests/test_interface_limits.py`).

**Und gefaltet wird, weil es sein muss — je Kategorie, nicht je Gruppe.** Wer
ein Menü über die Zeilengrenze wachsen lässt, bekommt kein Untermenü für die
ganze Gruppe: `folded_categories` (`app/core/registry/surfaces.py`) faltet nur
so weit, bis der Rest passt, und nimmt sich dabei die **hinteren** Kategorien
aus `MENU_GROUPS` — die Reihenfolge dort geht von häufig nach selten. Die
Rechnung liegt im Kern, damit `menu_path` sie fragen kann; sie war einmal in
`panels.py`, und deshalb nannten Handbuch, Agent und Tour einen Weg, den die
Leiste anders baute.

Drei Folgen für die Oberfläche:

* **Eine Kategorie, die direkt im Menü steht, behält ihren Namen als
  Überschrift** (`addSection`, nicht `addSeparator`). Ein nackter Trennstrich
  hält sie auseinander und **benennt** sie nicht; man erfuhr den Namen nur,
  wenn ein Untermenü ihn trug — also genau dann, wenn der Weg einen Klick
  länger war. Eine Überschrift ist ein Trennstrich mit Text und zählt in der
  Zeilengrenze nicht mit (`isSeparator()` bleibt wahr).
* **Bei einer einzigen besetzten Kategorie bleibt die Überschrift weg** —
  sie wäre ein zweiter Name für dasselbe Menü („Bausteine → Bausteine").
* **Die direkten Kategorien stehen vor den gefalteten**, getrennt durch einen
  nackten Trennstrich. Eine Überschrift benennt alles bis zum nächsten
  Trennstrich, und eine Untermenü-Zeile dazwischen liest sich als Teil der
  Kategorie davor: „Transformation" und „Formgebung" standen unter „Verbinden
  und Abziehen". **Den Fall gab es vorher nicht** — eine Gruppe war ganz flach
  oder ganz gefaltet, und die Mischung entsteht erst mit
  `folded_categories`. Wer eine Unterscheidung einführt, führt die
  Anordnungsfrage mit ein; keine der acht bestehenden Menüprüfungen hat sie
  gestellt, und der Trennstrich hinter dem letzten direkten Block ist die ganze
  Antwort — die Zeilen dahinter tragen ihre Namen selbst.

**Wo eine Operation steht, entscheiden zwei Fragen: Gilt sie einer Auswahl,
und hat sie eine Kachel im Katalog.**

* **Was einer Auswahl gilt, steht rechts — und nur dort** (Robert,
  11.09.2026: „da wir die operationen rechts im auswahlpanel haben brauchen
  wir es nicht auch noch zusätzlich oben in der menüleiste"). Die Karte der
  Handlungen zeigt an Körper und Merkmal, was das Register für sie kennt,
  gruppiert nach `group_title(spec.category)` in einklappbaren Abschnitten,
  mit Suchfeld, mit Grund an jeder gesperrten Handlung. Die Menüs *Objekt*,
  *Ändern* und *Vorbereiten* gibt es deshalb nicht mehr: `PANEL_CATEGORIES`
  (`app/core/registry/registry.py`) nennt ihre Kategorien, `in_the_menu_bar`
  beantwortet die Frage je Kategorie, und `_build_menus` legt für eine
  solche Gruppe **kein Menü** an. Die Aktionen entstehen trotzdem — am
  Fenster, damit Strg+B bohrt, die Palette weiß, ob eine Handlung geht
  (`_update_actions` liest `_op_actions`), und die Kürzelübersicht sie unter
  „Handlungen rechts" führt. **Nackte Tasten bleiben an Objektbaum und
  Ansicht** (`_scope_shortcut`): Am Fenster dazu läge Entf noch einmal über
  dem Verlauf, wo *Schritt löschen* dieselbe Taste hat, und zwei Aktionen auf
  einer Taste führt Qt beide nicht aus.
* **In der Leiste bleibt, was keine Auswahl braucht**: *Datei*, *Bearbeiten*
  (dort auch *Automatisch teilen*, ein Ablauf über mehreren Operationen),
  *Erzeugen* mit Grundkörpern, Importen, Skizzen, Beschriftungen — und dem
  Abschnitt *Bausteine*: Katalog, Gegenstücke und die zwei Deckel ohne
  Kachel. Ein eigenes Menü *Bausteine* trug zuletzt genau diese vier Zeilen;
  die Kategorie `parts` steht deshalb in der Gruppe *Erzeugen*
  (`MENU_GROUPS`). *Ansicht* und *Hilfe* wie gehabt.
* **Ob eine Operation mit Auswahl einen Menüort hat, entscheidet ihre Kachel
  im Katalog — nicht ihre Kategorie.** `catalogue_operations()`
  (`app/core/registry/surfaces.py`) ist die eine Quelle; Leiste, Karte,
  `menu_path` und die Wächter fragen sie. Ein Baustein der Bibliothek steht im
  Katalog mit Bild, weil ein räumliches Teil als Textzeile die schlechtere
  Darstellung ist (§2.6). Nicht jede Operation der Kategorie hat eine Kachel:
  `create_lid` und `screw_lid` nicht, und die stehen in der Karte an der
  Fläche **und** unter *Erzeugen → Bausteine* — eine Ausnahme an der
  Kategorie hatte sie einmal aus beidem genommen (Vorfall: ROADMAP-ARCHIV.md,
  04.09.2026).
* **Zum Katalog in einem Klick, wenn das Teil gewählt ist** (Roberts
  Bedingung): der Hauptknopf *Bausteine* unter der Karte, an Körper und
  Fläche; dazu *Datei → Bausteinkatalog …*, Strg+K und *Erzeugen →
  Bausteine*. `test_a_chosen_part_reaches_the_catalogue_in_one_click` führt
  die Bedingung wörtlich.
* **Das Kontextmenü an Körper und Merkmal trägt keine Operationen.** Bis zum
  11.09.2026 stand dort dieselbe Liste wie rechts — gruppiert, nach
  `folded_groups` gefaltet, mit dem Katalog an der Stelle der Bausteine —,
  und vier gemessene Zusagen (§40, §35, Roberts Klick, §18.5) schlossen sich
  an der Fläche gegenseitig aus (Nachweise: ROADMAP-ARCHIV.md). Zwei Orte für
  dieselbe Liste sind einer zu viel (Robert: „ebenso dann beim rechtsklick im
  objektbaum"). Was bleibt, gibt es nur dort: *Diesen Schritt ändern* (der Weg
  vom Ergebnis zurück zum Schritt, §21.2), *Auf dieser Fläche zeichnen* und
  die Sichtbarkeit. Der Viewport zeigt dasselbe Menü.
* **Der Wegweiser des Chats nennt den Ort, nicht mehr das Menü.**
  `menu_path` schreibt für eine Handlung rechts „Handlungen rechts (bei
  gewähltem Körper) → Vereinigen" beziehungsweise „(bei gewähltem Merkmal:
  Fläche)", für alles in der Leiste den Menüweg wie bisher; die
  Werkzeugbeschreibungen leiten mit „Ort:" ein (Prompt-Version 6). Handbuch
  und Tour nennen dieselben Orte, und `test_every_menu_path_in_the_texts_exists_in_the_menu_bar`
  hält jeden „A → B" in den Texten an der Leiste fest.
* **`HANDLE_INSTEAD` bleibt** (`panels.py`): Es nimmt an der Bohrung *Zum
  Langloch ziehen* aus `operations_for_feature`, weil der Griff im Bild die
  Zeile ist — gebraucht vom Doppelklick im Baum, der die erste passende
  Handlung startet. Am Langloch bleibt sie, weil sie dort die einzige ist.

* **Ein Wächter ist so scharf wie seine weiteste Ausnahme.** Der Test, der
  „jede Operation ist im Menü auffindbar" zusichert, nahm die *Kategorie* aus
  — und blieb deshalb grün, während zwei Operationen nirgends standen. Wer
  eine Ausnahme formuliert, prüft sie an ihren Rändern und nicht an ihrem
  Normalfall.

**Zwei Zeilen mit demselben Text sind eine Frage ohne Antwort.** `drill_hole`
und `drill_brep_hole` tragen denselben Titel; die Menüleiste legt das Paar über
`MENU_TWINS` zusammen, und das Auswahlfenster am Merkmal muss dieselbe
Zusammenlegung kennen. **Dieselbe Frage, zwei Rechnungen** — genau der Grund,
aus dem die Menütiefe in den Kern gewandert ist.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

Weggelassen wird ein Zwilling nur, wenn sein Partner tatsächlich mit angeboten
wird; sonst wäre er spurlos weg statt zusammengelegt.

`surfaces.context_menu()` bleibt dabei die **Rohmenge** — der Name legt anderes
nahe, und `tests/test_acceptance_p0.py` nagelt diese Lesart ausdrücklich fest.
Was daraus Zeilen werden, entscheidet die Oberfläche.

**Und die Testfalle dazu, weil sie allgemeiner ist als der Fall:** Der
bestehende Test nimmt `operations_for_feature` als *Sollmenge* („alles, was sie
liefert, steht im Menü"). Ein Filter in dieser Methode lässt Erwartung und
Menü gemeinsam schrumpfen — der Test bleibt grün, ganz gleich was die Methode
tut. Das ist die Schwester von „Sollwert aus dem Prüfling": Dort erzeugt die
geprüfte Funktion die Erwartung, hier definiert sie die Grundmenge. Gezählt
wird deshalb am **gebauten** Menü, und die Zusage lautet nicht „*Bohrung
setzen* genau einmal", sondern „kein Kontextmenü zeigt zwei Zeilen mit
demselben Text" — die engere Fassung wäre am Tag des nächsten Zwillings still.

**Ein Zeichen darf allein stehen, wenn es entweder ein geeinigtes Bild ist
oder die Zahl klein und die Stelle fest bleibt.** Der Skizzeneditor lebt vom
ersten Fall: Linie, Kreis und Bogen sehen in jedem CAD gleich aus. Die obere
Werkzeugleiste vom zweiten — Blatt, Ordner und Diskette sind geeinigt, „Modell
einfügen", „Zeichnen", „Formen" und „Skelett" nicht; was sie trägt, sind
sieben Knöpfe an unveränderlicher Position mit einem Tooltip, der Namen,
Kürzel und Zweck in einem Satz nennt. Die Werkzeugzeile unter dem Viewport
bleibt beschriftet: sieben Umschalter, die mit dem Zustand wechseln, und für
„Schnitt" und „Explosion" gibt es kein Bild. (Sieben ist der Bestand, acht die
Grenze — ``MAX_TOOLS`` in ``test_interface_limits.py``, wo der Kommentar den
Unterschied ebenfalls führt.) Regel 18 verlangt eine zweite
Kodierung neben der **Farbe**, nicht eine Beschriftung neben jedem Zeichen.

**Und keiner der sieben verschwindet.** Die Explosionsansicht braucht zwei
Körper; bis zum 14.09.2026 nahm `set_available` ihren Umschalter mit dem
ersten Körper aus der Zeile und stellte ihn mit dem zweiten wieder hin — auf
der leeren Szene stand er grau neben den anderen sechs. Eine Zeile, die sich
beim Laden einer Datei umbaut, wirkt unzuverlässig (Bedienweg-Durchsicht).
`ToolStrip.set_tool_usable` graut ihn wie `set_usable` die übrigen, mit dem
Grund am Knopf („Dafür braucht es zwei Körper in der Szene."); `_update_actions`
fragt ihn **nach** der Freigabe aller, weil die jeden Knopf wieder öffnet.

Wo das Wort vom Knopf verschwindet, muss es an drei Stellen weiterstehen: am
`QAction` (Barrierefreiheitsbaum), im Tooltip und im `statusTip`. Den Satz
dafür holt `_button_tip` aus dem Menüeintrag derselben Handlung, samt Kürzel —
zwei eigene Erklärungen für einen Knopf driften auseinander. Der `statusTip`
ist dabei nicht nur Anzeige: `_lock_hint` und `_pick_hint` stellen den eigenen
Hinweis daraus wieder her, und ein ungesetzter macht den Knopf nach dem
Freischalten stumm. Beide Helfer ersetzen den Hinweis vollständig; damit am
unbeschrifteten Knopf nicht ein Bild und ein zusammenhangloser Satz übrig
bleiben, stellt `_with_name` den Namen voran (Merkmal `wordless` am `QAction`).
Getrennt wird mit dem Zeichen, das der Satz dahinter **nicht** schon führt:
Gedankenstrich vor dem Zweck, Doppelpunkt vor einem Grund, der selbst einen
Gedankenstrich hat.

**Wer eine Beschriftung ausblendet, zieht die Anleitungstexte mit.** Handbuch
(`app/core/manual.py`) und Tour (`app/core/tour.py`) verweisen auf Knöpfe beim
Namen; steht der Name nicht mehr am Knopf, sucht der Leser. Die Tour wiegt
schwerer als das Handbuch — ihre Schritte haben `done=`-Bedingungen und rücken
nicht weiter.

**Eine Operation je Handlung, nicht je Variante.** Neun Texturmuster sind ein
Menüeintrag mit einem Auswahlparameter, nicht neun Einträge. Rechteck aus zwei
Ecken oder aus Mitte und Maß ist dasselbe Werkzeug mit einem Umschalter. Die
Mesh/B-Rep-Zwillinge (Quader, Zylinder) sind dieselbe Handlung in zwei
Rechenkernen: ein Eintrag, „Exakt (B-Rep)" ist ein Umschalter hinten im
Dialog, und `MENU_TWINS` im Register hält die Zuordnung — auch für den
Menüort, den der Agent nennt (§2.6).

**Nicht jeder Zwilling braucht einen Umschalter.** Die Beschriftung liegt in
`TWIN_TOGGLES`, nicht als Zeichenkette in der Oberfläche; wer dort fehlt, hat
seinen Umschalter als **Wert** im Dialog des Partners. *An Ebene teilen* ist
*Teilen* mit `pins = 0` — ein Haken „Exakter Körper (B-Rep)" wäre dort eine
Wegbeschreibung zu etwas, das es nicht gibt. Solange das fest verdrahtet war,
taugte die ganze Zusammenlegung für nichts als die zwei Rechenkerne.

**Ein Umschalter, dessen Zwilling eine Bedingung hat, fragt sie — vorher.**
Das Menü graut eine Operation des exakten Kerns (`requires_kind="brep"`) an
einem Netz aus und schreibt den Grund in den Tooltip. Seit die Zwillinge
zusammengelegt sind, hat `drill_brep_hole` gar keinen eigenen Menüeintrag mehr:
Der **Haken ist der Weg zu ihr**, und dort wurde nicht gefragt. Gemessen an
einer eingelesenen STL — Haken wählbar, Dialog geht durch, Auswertung hält bei
op 2 an, Absage im Prüfbericht. Der Satz des Kerns ist gut und bleibt; er ist
die *zweite* Hürde, und die erste fehlte.

`_lock_twin_toggle` fragt dafür `_reason_locked`, also dieselbe Kette wie
Menüleiste und Kontextmenü — eine dritte Formulierung derselben Auskunft wäre
eine dritte Gelegenheit, auseinanderzulaufen.

**Und ein Menü zeigt Hinweise nur, wenn man es ihm sagt.** `QMenu` steht mit
`toolTipsVisible == False` auf der Welt: Der Satz, den `_add_operation` an die
gesperrte Handlung schreibt, kommt an — und Qt zeigt ihn nie. Die Eigenschaft
setzt jedes Menü, das gesperrte Handlungen trägt: die Menüleiste an ihren drei
Stellen, das Kontextmenü am Körper und das der Skizze ebenso.
**Untermenüs erben sie nicht** — und am ganzen Körper stehen die Operationen
gerade dort drin, nach Kategorie gruppiert, weil siebenundfünfzig Zeilen kein
Menü mehr sind.

Eine Zusage über einen Text ohne die Zusage, dass er erscheint, ist die Hälfte
einer Prüfung — wer einen Grund an eine Handlung schreibt, prüft
`toolTipsVisible()` des Menüs mit, in dem sie steht.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Grau ohne Grund gibt es auch ohne `requires_kind`.** Im Kontextmenü der
Skizze standen die zehn Bedingungen, die halbe Liste gesperrt, und keine sagte,
welche Auswahl ihr fehlt — obwohl der Halbsatz seit je existiert
(`_needs_phrase`) und am Knopf in der Leiste und in der Meldung nach dem Kürzel
schon steht. Die dritte Stelle bekommt ihn aus derselben Quelle, nicht neu
formuliert.

**Bei den ersten beiden Zwillingen konnte das nicht auffallen:**
`create_brep_box` und `create_brep_cylinder` verbrauchen nichts (`consumes=0`),
es gibt keinen Eingangskörper, der der falsche sein könnte. Wer einen Zwilling
mit Eingang dazunimmt, nimmt diese Frage mit.

**Und der Zwilling heißt genau wie sein Partner.** `create_brep_box` trägt
„Quader anlegen", `drill_brep_hole` „Bohrung setzen" (`app/core/brep/ops.py`)
— denselben Titel wie `create_box` und `drill_hole`. Den Unterschied nennt
nicht der Titel, sondern der Haken im Dialog des Partners („Flächen und Kanten
später bearbeiten", `_EXACT_TOGGLE` in `registry.py`); in der Palette steht
der Zwilling nicht ein zweites Mal (`hidden_from_the_menu`). Kein eigener
Titel und kein Wort davor: Die Befehlspalette sortiert nach Titel, und „Exakt"
vor dem Namen liest sich wie eine Qualitätsstufe, obwohl es den Rechenkern
meint. Dahinter steht der Kunde: Er sucht das **Substantiv** („Bohrung"), und
wer den Zwilling umformuliert, nimmt ihm eine der beiden Antworten aus der
Liste.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Ein Umschalter zwischen Varianten schaltet den ganzen Dialog um**, nicht nur
die Rechnung: `OperationDialog.switch_variant` blendet aus, was die gewählte
Variante nicht kennt, und tauscht die Beschreibung. Die Werte beim Anwenden zu
filtern genügt nicht — was stehen bleibt, verspricht eine Wirkung.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Ein Feld ohne Wirkung steht nicht da.** Eine Nummer kleiner als der
Umschalter: *Fläche* in „Relief auflegen" gilt nur, solange *Auflegen* auf
„Auf eine Fläche" steht, und die Operation übergeht den Wert sonst wortlos.
Die Zeile verschwindet, bis die Bedingung gilt, und bleibt dahinter gesperrt
und begründet — die Entscheidung vom 14.09.2026 (RM-171) steht oben unter
„Und was gerade nichts tut, steht nicht da". Bis dahin stand sie grau da, mit
dem Argument „wer eine Zeile vermisst, sucht sie"; der Preis waren vier tote
Zeilen im häufigsten Fall.

**Die Angabe steht am Parameter** (`ParamSpec.depends_on`), nicht in einer
Tabelle der Oberfläche: Dieselbe Auskunft brauchen vier Oberflächen. Der Dialog
blendet aus, sperrt und begründet, das Handbuch schreibt die Bedingung in die
Parametertabelle, der Agent bekommt sie in der Werkzeugbeschreibung, die
Kommandozeile liest dasselbe `json_schema`.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Agent und Mensch bekommen verschiedene Anreden, nicht verschiedene Inhalte.**
„Gilt bei Art = circular" hilft im Handbuch; der Agent kennt kein *Art*, er
setzt `kind` (`condition_text(..., keys=True)`). Der Dialog formuliert
eigenständig („Wirkt nur, wenn …"), weil er einen Tooltip an einem ausgegrauten
Feld schreibt und die Werte durch `choice_label` schickt — zwei Formulierungen,
eine Quelle.

`tests/test_operation_ui.py` liest deshalb
den Quelltext jeder Operation und meldet jeden Parameter, dessen sämtliche
Lesestellen in einem Zweig über einen Umschalter derselben Operation liegen.
Zwei Regeln machen die Prüfung brauchbar statt abgeschaltet: **in genau einem
Zweig** gelesen (was in beiden steht, wirkt immer), und **kein Aufruf, der den
ganzen Parametersatz weitergibt** (dort endet der Blick von außen). Ohne die
zweite meldete sie acht Funde, von denen sieben keine waren.

Ein **Haken** als Umschalter braucht zwei Dinge, die eine Auswahl nicht
braucht: einen typtreuen Vergleich — über `str()` hieße der gesuchte Wert
„True", und weil `1 == True` ist, machte eine Anzahl von 1 einen Haken wahr —
und einen eigenen Satz. „Wirkt nur, wenn „Gründlich suchen" auf „True" steht"
ist die Bauart der Anwendung und nicht ihre Bedienung.

Wer eine neue Abhängigkeit deklariert, prüft die **Art** des Umschalters mit:
Ein Wahrheitswert an einem Aufklappmenü oder ein Auswahlwert an einem Haken wäre
eine Bedingung, die nie zutrifft — und ein Feld, das immer grau bleibt.

**Ein Sammelparameter bekommt seinen Editor, nicht sein Speicherformat** —
getipptes JSON ist keiner. `ArmatureField` baut je Knochen eine Zeile mit drei
Winkeln — sobald der Dialog ein Skelett hat (aus dem Editor oder aus dem Wert
der Operation), sonst bleibt das Textfeld als Rückfall. Die Winkel sind
`ValueField`, denn §13 gilt für einen Winkel wie für eine Länge. Im **Schema**
bleibt der Sammelparameter hinten (`tests/test_gesture_ops.py`); im Dialog
steht er vorn, wenn er der Grund ist, aus dem der Dialog aufgeht.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Ein Grundkörper bietet an, seine Maße zu benennen** (§13, Entscheidung Robert,
14.09.2026). Der Haken *Maße als Parameter anlegen* steht vorn im Dialog jeder Operation der
Kategorie `primitive` (`offers_naming` in `main_window.py`); gesetzt, wird jedes
Millimetermaß der Vorderseite ein Projektparameter — benannt nach seiner
Beschriftung, wie der Kunde sie liest (*Breite* → `breite`, vergeben → `breite_2`),
mit übersetzbarem Titel und den Grenzen des Feldes — und der Schritt verweist mit
`=@breite` darauf. Parameter und Schritt gehen in **einer** Transaktion
(`changes` an `Session.apply`): Ein Strg+Z nimmt beides zusammen zurück. Ein Feld
mit einem Ausdruck bleibt, was es ist. Bis dahin konnte nur der Agent Maße
benennen; der Kunde musste den Parameter in der Leiste anlegen und `=@breite` in
das Feld tippen, zwei Dinge, von denen ein Neuling keines kennt. Nachweis:
`test_naming_the_dimensions_makes_them_project_parameters`,
`test_only_a_primitive_offers_to_name_its_dimensions`.

**Eine Grenze steht dort, wo gewählt wird.** `caveat` im Registereintrag sagt,
wann eine Operation die falsche Wahl ist. Fünfunddreißig von hundertzweiunddreißig
Operationen tragen einen (die Zahl prüft `tests/test_registry_consistency.py`;
ungeprüft altert sie still). Er gehört überall dorthin, wo gewählt wird, nicht
allein in die Handbuchreferenz: `caveat_line()` (`app/core/registry/surfaces.py`)
ist die eine Quelle und trägt das Wort davor: Ohne Vorwort liest sich die Grenze
als Fortsetzung des `doc`-Satzes. Im Dialog ein **eigenes Label**, halbfett, mit
dem Wort als zweiter Kodierung (Regel 18); im Tooltip unter dem Satz; beim
Agenten in der Werkzeugbeschreibung. **Nicht in die Statuszeile** — die ist eine
Zeile, und eine abgeschnittene Warnung ist schlimmer als keine.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Jede neue Funktion nennt ihren Hauptweg** (§2.2), bevor sie einen Platz
bekommt:

| Weg | Ort an der Oberfläche |
|---|---|
| Weg 1 — fremdes Modell anpassen | Auswahlfenster am Merkmal, Vorschlag im Prüfbericht, Werkzeugzeile (*Trennen*: zwei Klicks legen die Ebene, Verbinder vorgewählt) |
| Weg 2 — neu konstruieren | obere Werkzeugleiste („Zeichnen": erst skizzieren, die Erzeugungsart fragt der Dialog bei „Fertig"), Menü *Erzeugen* / *Ändern*; die Grundkörper tragen vorn den Haken *Maße als Parameter anlegen* (§13) |
| Weg 3 — generieren | Chat und Generierungsdialog |
| Weg 4 — organisch formen | obere Werkzeugleiste (*Formen*, *Skelett* — beide brauchen einen gewählten Körper und sagen das, bevor man klickt), Menü *Ändern* |
| keiner der vier | Untermenü und Befehlspalette, sonst nichts |

**Ein erzeugtes Merkmal bietet immer den Schritt an, der es erzeugt hat**
(§21.2). Der Eintrag *Diesen Schritt ändern* steht im Kontextmenü am Merkmal,
ganz oben und vor der Sichtbarkeit — er gilt dem Merkmal, die Sichtbarkeit
gilt dem Körper. Er ist der einzige Weg vom *Ergebnis* zurück zum *Schritt*:
sonst sucht der Kunde unter vierzehn Zeilen des Verlaufs die eine, die das
Ding erzeugt hat, das er gerade ansieht.

Die Frage lautete lange, welche Operation fachlich auf ein fertiges Gewinde
gehört, und `for_feature("thread")` gab darauf nichts zurück. Über
`applies_to` wäre die Antwort eine neue Operation je Merkmalsart gewesen;
über die Provenienz (`Feature.created_by`) ist sie **ein** Eintrag, der für
alle gilt und jede neue Merkmalsart von selbst mitnimmt. Ein **erkanntes**
Merkmal trägt `None` und bekommt ihn nicht — er führte dort ins Leere, und
das ist schlechter als keiner.

Damit bleibt `thread` in den `known_gaps` von
`tests/test_registry_consistency.py`, und das ist kein Rückstand: Die Prüfung
dort fragt `for_feature`, also `applies_to`, und über diesen Weg ist die Art
weiterhin leer. Wer die Ausnahme streicht, weil „das Gewinde jetzt etwas
anbietet", macht den Test rot.

Erzeugte Merkmale kommen aus **Bausteinen** (`knowledge/parts/build.py`) und
aus dem Verstiften, nicht aus jeder Operation: `drill_hole` rechnet Geometrie
und deklariert nichts, seine Bohrung findet die Erkennung wieder. Wer den
Eintrag testet, nimmt deshalb einen Baustein und nicht das Bohren.

**Was zur Auswahl passt, steht vorn.** `applies_to` sortiert nicht nur das
Kontextmenü, sondern auch die Befehlspalette
(`palette_entries(for_feature=...)`). Es ist eine Reihenfolge, keine Auswahl —
eine Palette, die aussortiert, wäre eine Betriebsart mit anderem Namen.

**Und sortiert wird nach dem Titel, überall mit `i18n.sort_key`** — in der
Menüleiste (`by_category`), in der Palette und im Kontextmenü, nicht in der
Ordnung von `Registry.all()`, die der internen englischen Bezeichner. Nicht
`str` und nicht `casefold`: „Überhangfächer" landet nach Codepunkt hinter allem
anderen. Nicht zu verwechseln mit `command_palette.fold`, der **Suchfaltung** —
dort wird „ä" zu „ae", weil jemand „aushoehlen" tippt; beim Sortieren zählt „ä"
wie „a" (DIN 5007-1), damit „Ändern" zwischen „Analyse" und „Anordnen" steht.
Zwei Aufgaben, zwei Tabellen, und der Kommentar an jeder sagt, welche.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Und die Suche antwortet in drei Runden, jede nur bei Bedarf.** Genau
passend, dann am Wortstamm („bohren" → *Bohrung setzen*), und für eine
mehrwortige Frage zuletzt: **irgendeines** der Wörter, nach Trefferzahl
sortiert, mit einer Zeile darüber, die das sagt („Kein Befehl passt auf alle
Wörter — das Folgende passt auf einzelne."). „ecke abrunden" gab eine leere
Liste, während „abrunden" das *Verrunden* fand (Bedienweg-Durchsicht
14.09.2026, sieben von 71 Kundenwörtern leer). Eine Liste, die
stillschweigend weniger prüft, sähe aus wie eine genaue — deshalb die Zeile.
