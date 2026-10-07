# Begründungen zu `.claude/rules/grenzen.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

Wo ein Absatz auf „(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)“ verweist, steht
der Vorfall selbst in `ROADMAP-ARCHIV.md` unter „### `.claude/rules/oberflaeche.md`“,
gegliedert nach den Abschnitten, in denen die Regeln damals standen.

## Kopf: warum die Regel im Register lädt

Sie lädt nicht nur in der Oberfläche, sondern auch im **Register**: Wer eine
Operation einträgt, erweitert ein Menü, und die drei Dateien, die dieser
Abschnitt am häufigsten nennt, liegen in `app/core/registry/`.

## Die Oberfläche wächst nicht mit

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

**Faltung (aus der Regel verschoben, 06.10.2026):** Die Rechnung liegt im Kern,
damit `menu_path` dieselbe Antwort gibt wie die Leiste; `MENU_GROUPS` zählt von
häufig nach selten. Die Überschrift einer direkten Kategorie setzt `addSection`
(zählt nicht in der Zeilengrenze, `isSeparator()` bleibt wahr); bei einer
einzigen Kategorie fiele „Bausteine → Bausteine“. Der nackte Trennstrich vor den
gefalteten, weil eine Überschrift alles bis zum nächsten benennt. Wer eine
Unterscheidung einführt, führt die Anordnungsfrage mit ein.

## Wo eine Operation steht

Im Original stand in der Tabelle der Hauptwege bei Weg 2 „Menü *Erzeugen* /
*Ändern*“ und bei Weg 4 „Menü *Ändern*“ — ein Menü, das es nach derselben Datei
nicht mehr gibt („Die Menüs *Objekt*, *Ändern* und *Vorbereiten* gibt es deshalb
nicht mehr“). Die verdichtete Tabelle nennt dort die Karte der Handlungen. Die
alte Tabelle wörtlich am Ende dieses Abschnitts.

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

* **Ein Wächter ist so scharf wie seine weiteste Ausnahme.** Der Test, der
  „jede Operation ist im Menü auffindbar" zusichert, nahm die *Kategorie* aus
  — und blieb deshalb grün, während zwei Operationen nirgends standen. Wer
  eine Ausnahme formuliert, prüft sie an ihren Rändern und nicht an ihrem
  Normalfall.

**Jede neue Funktion nennt ihren Hauptweg** (§2.2), bevor sie einen Platz
bekommt:

| Weg | Ort an der Oberfläche |
|---|---|
| Weg 1 — fremdes Modell anpassen | Auswahlfenster am Merkmal, Vorschlag im Prüfbericht, Werkzeugzeile (*Trennen*: zwei Klicks legen die Ebene, Verbinder vorgewählt) |
| Weg 2 — neu konstruieren | obere Werkzeugleiste („Zeichnen": erst skizzieren, die Erzeugungsart fragt der Dialog bei „Fertig"), Menü *Erzeugen* / *Ändern*; die Grundkörper tragen vorn den Haken *Maße als Parameter anlegen* (§13) |
| Weg 3 — generieren | Chat und Generierungsdialog |
| Weg 4 — organisch formen | obere Werkzeugleiste (*Formen*, *Skelett* — beide brauchen einen gewählten Körper und sagen das, bevor man klickt), Menü *Ändern* |
| keiner der vier | Untermenü und Befehlspalette, sonst nichts |

## Die Karte der Handlungen

*Bis zur Verdichtung in `fenster.md`:*

**Ohne Auswahl bleibt von ihr der Weg zu den Bausteinen** (Entscheidung
Robert, 18.09.2026: „bei keiner Auswahl sollte das merkmalpanel auch da sein
um Bausteine setzen zu können"). Bis dahin verschwand die Karte ganz, und
damit der einzige sichtbare Zugang zum Katalog — übrig blieben Strg+K und
zwei Menüwege, die niemand sucht, der gerade auf eine leere Fläche geklickt
hat. Drei der siebenundzwanzig Bausteine stehen frei (`standalone`) und
brauchen keinen Körper; bei den übrigen sagt der Katalog selbst, was fehlt.
Die Operationsliste bleibt weg — sie gilt einer Auswahl, und die gibt es
nicht.

**Und eine Karte ohne Liste lädt nicht zum Durchsuchen ein.** Das Suchfeld
stand fest im Layout und war immer sichtbar; an einer Auswahl mit leerer
Karte — einem Langloch, einer Kante — versprach es etwas zu finden, wo es
nichts gibt (Befund Robert, 18.09.2026). Es verschwindet mit der Liste, und
ein Satz nennt, wo die Handlungen dieser Auswahl stehen. Wer **sucht** und
nichts findet, behält es: Dort ist das Feld die Ursache und der Weg zurück.

**Und der Filament-Schnellwähler gehört nicht in die leere Karte.** Er hat
einen eigenen leeren Zustand („Das Filamentlager ist auch ohne Auswahl
erreichbar."), und der war nie zu sehen, solange die Karte ganz verschwand.
Seit sie bleibt, stünden drei Blöcke über demselben Zustand: die Kopfzeile
„Nichts gewählt", sein Satz und der Satz, der die Antwort trägt. Er tritt
beiseite (`MainWindow._update_actions`), das Lager steht in der Kopfzeile und
im Menü. **Wer eine Karte für einen Zustand öffnet, den es vorher nicht gab,
sieht nach, welche leeren Zustände darin dadurch zum ersten Mal sichtbar
werden.**

**Eine gewählte Kante ist eine Stufe für sich** (Befund Robert, 18.09.2026:
„bei einer kante zu viele optionen die sinnlos bei kanten sind"). Sie ist
kein Merkmal und steht in keiner Baumzeile — der Kantenklick setzt die
Baumauswahl sogar auf den **Körper** zurück, und damit stand hier die volle
Körperliste: Aushöhlen, Auf dem Bett anordnen, Teilen. Was an ihr gilt, sind
die drei Zeilen aus `perceive.actions.EDGE_OPERATIONS`, und die stehen oben
im Merkmalfenster. `MainWindow.selected_feature_kind` meldet dafür `"edge"`,
sobald `Viewport.has_a_chosen_edge()` es sagt; `_fits_the_level` findet die
Art in keinem `applies_to` und lässt die Karte leer.

**Und was in dieser Karte vorn steht, richtet sich nach der Auswahl — nach
ihrer Art und nach ihrer Menge** (Robert, 07.09.2026: „es sollten immer je
nach auswahl und menge der auswahl die sinnvollsten aktionen dastehen"). Fest
verdrahtet waren es die drei Booleschen; an einem einzelnen Körper standen
damit drei graue Knöpfe, denn eine Vereinigung braucht zwei.

Vier Sätze dazu, und der letzte ist der, an dem ein mechanischer Entwurf
gescheitert ist:

* **Die Rangfolge steht in `selection_operations.py`**, nicht im Register:
  `quick_names(bodies, feature_kind)` liest sie aus `QUICK_BODIES`,
  `QUICK_BODY`, `QUICK_FEATURES` und `QUICK_FEATURE`. Sie ist eine
  **Empfehlung, keine Aufzählung** — was dort fehlt, steht in der Suchliste,
  im Menü und in der Palette. Deshalb ist Unvollständigkeit hier kein Fehler,
  anders als bei einer Angabe, die eine Fähigkeit ausspricht (`requires_kind`,
  `applies_to`): die gehört ins Register, weil eine Liste in der Oberfläche
  beim nächsten Zuwachs schweigt.

* **Eine Art ohne eigene Zeile bekommt die generischen Merkmalshandlungen**
  (ändern, verschieben, entfernen) statt einer leeren Zeile — **solange das
  Register sie an dieser Art anbietet.** Kegel, Stift und Kugel bieten die drei
  **mit** an, nicht genau sie: gemessen am 07.09.2026 trägt `pin` sieben
  Operationen, `cone` sechs und `sphere` vier.

  **Und wo das Register nichts kennt, steht nichts.** `applies_to` nennt sechs
  Arten (`face`, `hole`, `cone`, `pin`, `sphere`, `edge_loop`), die Erkennung
  liefert mehr — Torus, Verrundung und Gewinde haben null Operationen. Für die
  standen bis zum 07.09.2026 drei Knöpfe da, hinter denen keine einzige lag.
  Schlimmer als graue Knöpfe: `feature_requirement` fragt, ob **der Körper**
  ein solches Merkmal hat, nicht ob das **gewählte** eines ist — auf einem
  Körper mit Bohrung waren sie bedienbar und hätten auf ein anderes Merkmal
  gewirkt. `quick_names` schneidet den Rückfall deshalb gegen
  `REGISTRY.for_feature(kind)`; für die sechs bekannten Arten ändert das
  nichts.

* **Die Suchliste darunter ist in Gruppen gefaltet, jede ein Abschnitt zum
  Zuklappen** (`panels.collapsible`, dieselbe Kopfzeile mit Linie wie die
  linke Spalte) — die Gruppe ist `group_title(spec.category)`, also dieselbe
  Einteilung wie im Menü. Graue Zwischenüberschriften über einer Wand
  gleicher Knöpfe (Robert, 11.09.2026: „sieht alles ziemlich monoton und
  dadurch unübersichtlich aus"). Ein Suchtreffer öffnet seine Gruppe, sonst
  fände man, was man sucht, hinter einer zugeklappten Kopfzeile nicht.
* **Der Knopf *Bausteine* unten ist ein Hauptknopf** (`make_primary`,
  Akzentfarbe und halbfett — Regel 18) und steht an Körper und Fläche: Dort
  ist ein Baustein möglich, und der Knopf soll auffallen (Robert,
  11.09.2026). An einer Bohrung oder Verrundung steht er nicht.
* **Aus dem Register herleiten lässt sich das nicht.** Gemessen am 07.09.2026:
  Nach Kategorie-Rang aus `MENU_GROUPS` sortiert stünden bei zwei gewählten
  Körpern *Auf dem Bett anordnen*, *Objekt duplizieren* und *Objekt entfernen*
  vorn — die Kategorie `scene` steht im Menü vor `boolean`, weil sie
  Objektverwaltung ist, nicht weil sie die konstruktive Hauptsache wäre. Die
  Booleschen, der Grund für diese Fläche, fielen heraus. Ein Kürzel als
  Häufigkeitssignal hilft dort nicht: *Löschen* und *Umbenennen* tragen eines.

* **Eine Gruppe über der Menügrenze beginnt zugeklappt** (`OPEN_UP_TO`,
  dieselben zwölf wie `MAX_SUBMENU_ENTRIES`; `test_interface_limits` hält
  beide zusammen). Die vier Operationsmenüs sind am 11.09.2026 in diese Karte
  gewandert, und mitgewandert war die Zahl der Einträge, nicht die Grenze: An
  einem gewählten Körper — dem Zustand nach jedem Import — standen 42 Knöpfe
  offen, 24 davon unter „Ändern" (Durchsicht 14.09.2026). Gerechnet wird an
  der Stufe, nicht am Bestand: Dieselbe Gruppe hat an einer Fläche zwei
  Einträge und steht dort offen. Wer eine Klappe selbst bewegt, behält das
  über Auswahlwechsel hinweg (`clicked`, nicht `toggled` — nur die Geste
  zählt); ein Suchtreffer öffnet weiter.
* **Und was der Filament-Schnellwähler über der Liste trägt, steht nicht auch
  darin** (`PICKER_HANDLES`). *Filament entfernen* stand zweimal in derselben
  Karte — oben gesperrt mit Grund, solange nichts zugewiesen ist, unten
  bedienbar: derselbe Text mit entgegengesetzter Aussage.

**Was das Merkmalsfenster darüber als Feld zeigt, bekommt in der Karte keinen
zweiten Knopf.** Beide liegen im selben Fenster übereinander, und an einer
gewählten Bohrung standen *Bohrung ändern*, *Merkmal drehen* und *Merkmal
verdoppeln* damit zweimal: oben mit dem gemessenen Wert und einem Knopf,
darunter als Knopf, der denselben Weg noch einmal anbietet (Robert,
09.09.2026: „hier soll immer nur für das ausgewählte etwas stehen"; „statt
nochmal über einen Button und Dialog zu gehen, eher den Wert eingeben und dann
bestätigen"). Es ist dieselbe Regel, nach der eine Hauptaktion nicht auch in
der Suchliste steht, nur eine Karte höher.

Die Liste dazu steht im **Kern** (`perceive.actions.ACTION_ORDER`) und wird
über `_shown_as_fields()` nur gelesen — eine zweite Aufzählung in der
Oberfläche wüsste bei der nächsten Feldhandlung die Hälfte. Zwei Folgen, beide
gemessen:

* **Eine Art, deren Handlungen vollständig Felder sind, hat eine leere Karte**,
  und das ist die richtige Antwort — Stift und Kugel. Ein Test, der dort „die
  Liste ist nicht leer" verlangt, prüft die Gewohnheit.
* **Und eine Art, deren letzte verbliebene Handlung ein Schnellknopf einer
  *anderen* Art war, verliert sie ganz.** Der Kegel trägt sechs Operationen,
  fünf davon als Feld; die sechste — *Senken* — war ein Knopf der Zeile für
  `hole` und stand an einer Senkung an keiner der beiden Stellen. Er hat
  seitdem eine eigene Zeile in `QUICK_FEATURES`. Wer eine Handlung aus der
  Karte nimmt, zählt je Merkmalsart nach, was übrig bleibt.

**Und eine Beschriftung, die nicht in ihre Spalte passt, bricht um.** Zwei
Fehler steckten in demselben Bild („Bohru…ndern", Robert, 09.09.2026): Die
Zweierspalte maß die **Summe** beider Wunschbreiten, teilt den Platz aber
hälftig — gefragt ist, ob **jeder** von beiden in seine Hälfte passt. Und auch
einspaltig blieb der Titel zu breit; `_wrap_label` bricht ihn deshalb an einer
Wortgrenze auf höchstens zwei Zeilen, gemessen gegen die Schrift, mit der
wirklich gezeichnet wird — das Beiwerk des Knopfes kommt aus der Differenz zu
seinem Wunschmaß und nicht aus einer Zahl im Stylesheet, denn die Suite fährt
ohne. Der ungebrochene Titel bleibt als `operationTitle` am Knopf: `text()`
ändert sich, und die Suche darunter braucht den ganzen.

**Und Handlungen für alle Körper stehen nur ohne Auswahl.** Am gewählten
Körper sagte der Knopf, er gelte diesem Körper, und nahm doch alle. Robert,
05.10.2026: „Eigentlich reicht hier druckoptimal ausrichten, machen ja alle
ziemlich das gleiche und nur ohne Auswahl.“ Die Karte zeigt deshalb nur
`SCENE_ACTIONS_IN_THE_CARD`; *Auf dem Bett anordnen* (Strg+Umschalt+O) und
*Überschneidungen prüfen* stehen in der Palette, und `menu_path` nennt dort
„Befehlspalette“ statt „bei gewähltem Körper“ (RM-506).

**Und die Gruppen folgen der Menüleiste** (RM-506). Sortiert wurde mit
`str.casefold` des übersetzten Titels: Auf Deutsch stand „Ändern“ mit 32
Einträgen am Körper zugeklappt am Ende, und jede Sprache hatte eine eigene
Folge. Eine Kategorie, die das Menü in ein Untermenü faltet, ist in der Karte
eine eigene Gruppe, so dass keine mehr als zwölf Einträge zeigt. Was die
Werkzeugzeile schon trägt (*Bewegen*: verschieben, drehen, skalieren), steht am
Ende seiner Gruppe — bei 1600 × 1000 lag *Verrunden* sonst hinter sieben
Transformationen unter dem Ausschnitt.

**Und an einer Bohrung heißt der Knopf *Passende Bausteine …*** (Robert,
05.10.2026). Der volle Katalog an einer Bohrung bot neunundvierzig Bausteine,
von denen fünf dort ansetzen; der gefilterte führt mit einem Klick zu allen.
Findet die Kartensuche nichts, bietet sie *In allen Funktionen suchen*: Sie
kennt nur, was zur Auswahl passt, und „gewinde“ am Körper blieb leer, obwohl
es die Funktion gibt.

## Die Vorderseite eines Dialogs

*Bis zur Verdichtung in `oberflaeche.md`:*

**Ein vorbelegter Wert kommt nach vorn — außer er ist eine Richtung.** Der
Dialog holt, was gerade entschieden wurde, vor die Klappe: die angeklickte
Fläche, die vorgewählte Position (§18.5, `decided` in `op_dialog.py`). Der
Klick trägt aber auch die Normale der Fläche ein, drei Zahlen, von denen je
nach Fläche eine ungleich null ist — und die stand dann vorn: *Normale Z* an
der Oberseite, *Achse* und *Normale X* an der linken, ein Dialog, der bei
jeder Bohrung anders aussah (Durchsicht 14.09.2026). Eine Vektorkomponente
tippt niemand von Hand. `direction_fields` (die Normale aus
`normal_fields_of`, dazu `axis`) bleibt hinten; der Wert gilt trotzdem.

**Die Vorgabe trifft den Körper, nicht den Ursprung.** *Teilen* beginnt in
der Mitte des gewählten Körpers (`_plane_through`, 13.09.2026), *Dreiecke
verringern* bei der Hälfte seiner Dreiecke und *Dreiecke angleichen* bei einem
Fünfzigstel seiner längsten Kante (`_measured_from_body`, `EDGE_SHARE`,
14.09.2026). Feste Zahlen trafen entweder das große Teil oder das kleine:
50 000 Dreiecke an einer Platte mit wenigen hundert ließen das Band „am
Volumen ändert sich nichts" sagen, und 1,0 mm waren an 200 mm grob und an
5 mm zerstörerisch. Gefragt wird nach den **Feldern** (`axis`/`position`,
`triangles`, `edge` in Millimetern), nicht nach dem Namen der Operation; die
Zahl bleibt im Feld und lässt sich ändern. *Druckplatten* bleibt bei seinem
Höchstwert: Das Feld steht hinter der Klappe und ist eine Obergrenze, keine
erwartete Zahl.

*Aus `grenzen.md`:*

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

**Ein Sammelparameter bekommt seinen Editor, nicht sein Speicherformat** —
getipptes JSON ist keiner. `ArmatureField` baut je Knochen eine Zeile mit drei
Winkeln — sobald der Dialog ein Skelett hat (aus dem Editor oder aus dem Wert
der Operation), sonst bleibt das Textfeld als Rückfall. Die Winkel sind
`ValueField`, denn §13 gilt für einen Winkel wie für eine Länge. Im **Schema**
bleibt der Sammelparameter hinten (`tests/test_gesture_ops.py`); im Dialog
steht er vorn, wenn er der Grund ist, aus dem der Dialog aufgeht.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Ein Umschalter zwischen Varianten schaltet den ganzen Dialog um**, nicht nur
die Rechnung: `OperationDialog.switch_variant` blendet aus, was die gewählte
Variante nicht kennt, und tauscht die Beschreibung. Die Werte beim Anwenden zu
filtern genügt nicht — was stehen bleibt, verspricht eine Wirkung.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

## Bedingte Felder

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

## Zwillinge: eine Handlung, zwei Rechenkerne

**Eine Operation je Handlung, nicht je Variante.** Neun Texturmuster sind ein
Menüeintrag mit einem Auswahlparameter, nicht neun Einträge. **Erzeugen und
Schneiden mit demselben Werkzeug sind zwei Handlungen** (P6.5): Ein Erzeuger
nimmt nichts und setzt einen neuen Körper, ein Schnitt nimmt den gewählten und
setzt ihn fort — die Eingangszahl steht je Operation fest, und der Stapel
vergibt die Kennungen vor der Rechnung. Deshalb eigene Operationen
(`sketch_revolve_cut` neben `sketch_revolve`, wie `sketch_pocket` neben
`sketch_extrude`), aber kein eigener Menüeintrag: Sie stehen in der
Variantengruppe ihres Erzeugers, das Feld ist die Art (Konzept §10). Rechteck aus zwei
Ecken oder aus Mitte und Maß ist dasselbe Werkzeug mit einem Umschalter. Die
Mesh/B-Rep-Zwillinge (Quader, Zylinder, Bohrung, Aushöhlen) sind dieselbe
Handlung in zwei Rechenkernen: **ein** Eintrag, und `menu_twins()` im Register
sagt, welcher der beiden ihn trägt — auch für den Menüort, den der Agent nennt
(§2.6). **Einen Haken zwischen den Kernen gibt es nicht mehr** (P2.8, Konzept
§10.1, Entscheidung 4): Ein Erzeuger entsteht exakt, wo der Kern da ist; eine
Bearbeitung fragt die Körperart ihres Eingangs (*Bohrung setzen*, *Aushöhlen*
— „der Körper entscheidet"); der versteckte Zwilling steht in der
Befehlspalette, und ein gespeicherter Schritt wechselt seinen Kern über das
Kontextmenü des Verlaufs (`History.change_kernel`).

*Bis zur Verdichtung in `oberflaeche.md`:*

**Die Kernwahl-Haken sind gefallen** (P2.8, Konzept §10.1, Entscheidung 4
vom 17.09.2026). Bis dahin stand im Dialog jedes Zwillingspaars ein
Umschalter „Flächen und Kanten später bearbeiten“, vorn, mit einer Zählung der
Schritte darüber — eine Entscheidung, die der Kunde beim Anlegen treffen
musste, um sieben Werkzeuge nicht später grau zu finden. Heute entscheidet
niemand mehr: Ein Grundkörper entsteht exakt, wo der exakte Kern da ist
(`registry.menu_twins()`, faul, denn die Antwort lädt OpenCASCADE: sichtbar
`create_brep_*`, versteckt der Netz-Zwilling, erreichbar über die
Befehlspalette — und der Agent liest an ihm „Zweite Wahl“ mit dem Namen des
Eintrags im Menü); *Bohrung setzen* und
*Aushöhlen* fragen die Körperart ihres Eingangs (`prepare_ops.drill_hole`,
`hollow_object` mit der Tabelle aus §10.1: Oberseite offen ohne Entlüftung
bleibt exakt, alles andere geht den Netzweg und `evaluate.exact_became_mesh`
sagt es im Vorschauband). Ohne exakten Kern bleiben die Netz-Erzeuger
sichtbar — ein erklärter Weg, kein stilles Scheitern. Gespeicherte Schritte
behalten ihren Kern; ein altes Projekt rechnet unverändert.

**Der Wechsel steht am Schritt, nicht im Dialog.** `History.change_kernel`
stellt einen Schritt weiter auf seinen Zwilling um — vom Kontextmenü des
Verlaufs aus (`HistoryPanel.kernelSwitchRequested`, `MainWindow.switch_kernel`),
mit dem Satz, der den Nutzen nennt und nie den Rechenkern („Mit echten
Flächen und Kanten rechnen“, „Als Dreiecksmodell rechnen“,
`registry.kernel_switch_label`). Zwei Sperren vor dem Klick (Regel 19): in den
exakten Kern nur, wenn er da ist (dann fehlt der Eintrag; das Fenster prüft
es ein zweites Mal für den direkten Aufruf); ins Netz nur, wenn kein
späterer Schritt einzeln bearbeitbare Flächen braucht (der Kern wirft
`needs_exact` mit der Zahl der Schritte). Getauscht wird nur zwischen den
fünf Grundkörpern aus `PRIMITIVE_TWINS` — Bohren und Aushöhlen entscheidet
der Körper selbst, ein Wechsel an ihrem Schritt liefe ins Leere (gemessen im
Review vom 21.09.2026); und beliebige Operationen gegeneinander wäre kein
Bearbeiten mehr, sondern ein Umschreiben der Geschichte.

*Aus `grenzen.md`:*

**Zwei Zeilen mit demselben Text sind eine Frage ohne Antwort.** `drill_hole`
und `drill_brep_hole` tragen denselben Titel; die Menüleiste legt das Paar über
`MENU_TWINS` zusammen, und das Auswahlfenster am Merkmal muss dieselbe
Zusammenlegung kennen. **Dieselbe Frage, zwei Rechnungen** — genau der Grund,
aus dem die Menütiefe in den Kern gewandert ist.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

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

**Und der Zwilling heißt genau wie sein Partner.** `create_brep_box` trägt
„Quader anlegen", `drill_brep_hole` „Bohrung setzen" (`app/core/brep/ops.py`)
— denselben Titel wie `create_box` und `drill_hole`. Den Unterschied nennt
nicht der Titel, sondern der Weg: `TWIN_WAYS` in `registry.py` sagt je Paar,
wo der versteckte Zwilling steht („über die Befehlspalette" bzw. „im selben
Dialog — der Körper entscheidet"); im Menü steht er nicht ein zweites Mal
(`hidden_from_the_menu`). Kein eigener Titel und kein Wort davor: Die
Befehlspalette sortiert nach Titel, und „Exakt" vor dem Namen liest sich wie
eine Qualitätsstufe, obwohl es den Rechenkern meint. Dahinter steht der
Kunde: Er sucht das **Substantiv** („Bohrung"), und wer den Zwilling
umformuliert, nimmt ihm eine der beiden Antworten aus der Liste.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

## Der Satz kommt vor den Dialog

**Ein Zwilling, der eine Bedingung hat, fragt sie — vorher.** Das Menü graut
eine Operation des exakten Kerns (`requires_kind="brep"`) an einem Netz aus
und schreibt den Grund in den Tooltip; dieselbe Kette (`_reason_locked`)
speist Menüleiste, Kontextmenü, Auswahlkarte und die Variantenliste im Dialog
— eine weitere Formulierung derselben Auskunft wäre eine weitere
Gelegenheit, auseinanderzulaufen. Der Satz des Kerns ist gut und bleibt; er
ist die *zweite* Hürde. (Gemessen, als der Haken die erste war: Haken wählbar,
Dialog geht durch, Auswertung hält bei op 2 an, Absage im Prüfbericht.)

*Bis zur Verdichtung in `oberflaeche.md`:*

**Ein gesperrtes Werkzeug kennt zwei Lagen, nicht eine.** Der Körper war nie
exakt — dann steht der Wechsel am Erzeugerschritt im Verlauf. Oder er war es
und ist es nicht mehr, weil eine Mesh-Operation dazwischen liegt; dann hilft
kein Wechsel am Erzeuger, sondern nur am Schritt, der vernetzt hat.
`spoiled_the_exact_body()` liest den Schuldigen aus
`evaluate.exact_became_mesh` und `kind_requirement` nennt ihn beim Titel. Der
Vorschlag muss dabei ausführbar sein: Der erste Entwurf schlug vor, „den
Schritt im Verlauf nach hinten zu nehmen" — und das geht nicht, aus gutem
Grund (spätere Operationen bauen auf seinen Ausgaben auf, und auch das
Verschieben im Verlauf setzt keinen Schritt hinter die, die ihn brauchen).
Und eine dritte Lage ist die umgekehrte: Ein Werkzeug mit
`requires_kind="mesh"` (*Merkmale an dieser Stelle erkennen*) bekommt am
exakten Körper seinen eigenen Satz — *Flächenbearbeitung beenden* —, nicht
den Satz über die fehlenden Kurven; seit Grundkörper exakt entstehen, ist
das dort der Normalfall.

*Aus `grenzen.md`:*

**Und die Regel gilt auch ohne Feld.** *Vereinigen*, *Abziehen*, *Auf das
Bett setzen* und Entf haben keinen Parameter; an exakten Körpern bleiben sie
exakt und laufen ohne Dialog (Regel 19). Gezeigt wird eine feldlose Handlung
nur, wenn sie den Körper **umwandeln** kann — das Register verlangt ein Netz,
oder die Eingänge sind gemischt (`MainWindow._order_may_convert`). Ein Dialog
mit null Feldern vor einer rücknehmbaren Handlung war die Sackgasse aus Regel
19 in neuer Gestalt (Review 21.09.2026).

*Bis zur Verdichtung in `oberflaeche.md`:*

**Und der Satz kommt, wo es geht, vor den Dialog.** Elf der Dialoge ohne
Bild konnten am gewählten Körper nie etwas tun; drei davon sagen es seit dem
14.09.2026 am Menüeintrag (`requires_body`, `operationen.md`): *Offene Fläche
schließen* an einem geschlossenen, *In Einzelteile zerlegen* an einem Stück,
*Gitter füllen* ohne Hohlraum. *Deckel erzeugen* und *Drehdeckel erzeugen*
fragen seit der Bedienweg-Durchsicht die **gewählte Fläche**
(`lid.reason_against`, im Fenster einmal je Merkmal und Auswertung gerechnet,
unter derselben Dreiecksgrenze wie die Körperfakten): An einer massiven Platte
standen sie an jeder Fläche bedienbar und konnten nur scheitern. Ebenso *An
Merkmal ausrichten*, dessen Ziel ein zweiter Körper mit Merkmal ist
(`_NEEDS_TARGET`; das Ziel ist seither Pflicht, und der Dialog sperrt mit
demselben Satz, wenn die Liste leer ist). Was bleibt, ist *Teilen* auf einer
Ebene, die nichts trifft — das hängt an einer Zahl, die erst im Dialog
entschieden wird; dort trägt das Band den Satz.

*Aus `grenzen.md`:*

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

## Eine Grenze steht dort, wo gewählt wird

**Eine Grenze steht dort, wo gewählt wird.** `caveat` im Registereintrag sagt,
wann eine Operation die falsche Wahl ist. Einundvierzig von hundertzweiundvierzig
Operationen tragen einen (die Zahl prüft `tests/test_registry_consistency.py`;
ungeprüft altert sie still). Er gehört überall dorthin, wo gewählt wird, nicht
allein in die Handbuchreferenz: `caveat_line()` (`app/core/registry/surfaces.py`)
ist die eine Quelle und trägt das Wort davor: Ohne Vorwort liest sich die Grenze
als Fortsetzung des `doc`-Satzes. Im Dialog ein **eigenes Label**, halbfett, mit
dem Wort als zweiter Kodierung (Regel 18); im Tooltip unter dem Satz; beim
Agenten in der Werkzeugbeschreibung. **Nicht in die Statuszeile** — die ist eine
Zeile, und eine abgeschnittene Warnung ist schlimmer als keine.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

## Ein erzeugtes Merkmal bietet den Schritt an, der es erzeugt hat

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

## Ein Zeichen darf allein stehen, als geeinigtes Bild oder an fester Stelle

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

## Ein Kürzel folgt dem deutschen Titel

*Bis zur Verdichtung in `oberflaeche.md`:*

**Ein Kürzel folgt dem deutschen Titel.** So hält es der Bestand seit je —
*Bohrung setzen* auf Strg+B, *Drehen* auf Strg+R, *Aushöhlen* auf Strg+H —, und
eine Übersetzung ändert daran nichts: Kürzel sind keine Texte, sie stehen im
Register. Ist der einfache Buchstabe belegt, kommt Umschalt dazu (*Vereinigen*
Strg+Umschalt+V, *Abziehen* Strg+Umschalt+A); ist auch das belegt, **bleibt die
Operation ohne Kürzel**. *Skalieren* ist der Fall: S gehört dem Speichern,
Umschalt+S dem Speichern unter, und ein erfundener Buchstabe wäre schlechter als
keiner. Fünfzehn der hundertzweiundvierzig Operationen führen eines; wer eine sechzehnte Taste
vergibt, prüft vorher am **gebauten Fenster** gegen die dreiundvierzig, die
nicht aus dem Register kommen — Ansichten, Werkzeugzeile, Dateibefehle,
Navigation. Eine doppelt belegte Taste führt keine der beiden Aktionen aus
(„Ambiguous shortcut overload"), und das merkt man erst beim Drücken;
`tests/test_ui.py` (`test_no_two_shortcuts_in_the_window_collide`) hält es fest,
`tests/test_registry_consistency.py` allein sähe nur die eine Hälfte.

## Sortiert wird nach dem Titel, gesucht in der Sprache des Kunden

**Und sortiert wird nach dem Titel, überall mit `i18n.sort_key`** — in der
Menüleiste (`by_category`), in der Palette und im Kontextmenü, nicht in der
Ordnung von `Registry.all()`, die der internen englischen Bezeichner. Nicht
`str` und nicht `casefold`: „Überhangfächer" landet nach Codepunkt hinter allem
anderen. Nicht zu verwechseln mit `registry.search.fold`, der **Suchfaltung** —
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

**Und gesucht wird in der Sprache des Kunden, am Wortanfang** (Durchsicht
0.5.1, 26.09.2026). Die Kundenwörter stehen je Sprache im Katalog
(`registry.search.CUSTOMER_WORDS`, Kontext „Suchwörter"); vorher gab es sie
nur auf Deutsch, und von 330 Kundenwörtern in sechs Sprachen führten 183 ans
Ziel, danach 328 (Gegenprobe mit anderen Wörtern: 63 → 144 von 168). Ein
Titeltreffer mitten im Wort („stützen" in „unterstützen") zählt nach den
Kundenwörtern, die Wörter einer Anfrage müssen in **einer** Wendung stehen,
und in den ungenauen Stufen (`LOOSE_RANK`) entscheidet dieselbe Wertung,
mit der der Agent seine Werkzeuge wählt (`rank_entries`).

**Die Kundenwörter gehören der Palette, nicht dem Agenten.** Der Agent wertet
nur `SYNONYMS` (`rank_operations`, `customer_words=False`). Mit den
Kundenwörtern holte „Versteifung" den Eckwinkel neben die Rippe ins
ausführliche Angebot, und qwen3:14b traf „Versteife die Wand mit einer Rippe"
0 von 2 statt 3 von 3 (Durchsicht 0.5.1). Wer ein Kundenwort auch dem Agenten
geben will, ändert sein Angebot — das ist eine Verhaltensänderung mit Suite
vorher/nachher (`.claude/rules/agentenschicht.md`). Wer ein Kundenwort
einträgt, trägt es in allen Sprachen ein und prüft zwei Dinge: dass es kein
Füllwort ist (eine Wendung „zu einem Teil" traf jede Anfrage mit „eine" und
„Teils"), und dass es nicht über einen kurzen Stamm ein anderes Wort meint —
`test_every_customer_word_belongs_to_a_row_of_the_palette` hält die Schlüssel
am Register und an den Fensterbefehlen fest.

## Maße als Parameter anlegen

Die Regel in `grenzen.md` sichern `test_naming_the_dimensions_makes_them_project_parameters`,
`test_only_a_primitive_offers_to_name_its_dimensions`,
`test_a_holder_template_names_its_dimensions_but_not_an_idle_field` und
`test_the_naming_box_remembers_the_last_choice`. Dass der Haken die letzte Wahl
übernimmt, statt jedes Mal aus zu stehen, folgt aus Weg 2: Wer Maße benennt, tut
es bei jedem Grundkörper, und musste den Haken bisher jedes Mal neu finden
(RM-369, Entscheidung Robert). Gemerkt wird beim Übernehmen, nicht beim Klick
auf den Haken; wer ihn nur ausprobiert und abbricht, hat nichts entschieden.
