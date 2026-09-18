---
description: "Fenster und Dialoge — höchstens drei Zonen, der Hauptknopf, die automatische Sicherung, wie Karten ihre Höhe teilen, und warum setParent(None) ein Kind zum Fenster macht"
paths:
  - "app/ui/main_window.py"
  - "app/ui/app.py"
  - "app/ui/dialogs.py"
  - "app/ui/*dialog*.py"
  - "app/ui/start_screen.py"
  - "app/ui/first_run.py"
  - "app/ui/manual_window.py"
  - "app/ui/overlay.py"
  - "app/ui/panels.py"
---

# Regeln für Fenster und Dialoge

Wie die Zonen liegen, was ein Dialog vorn zeigt und hinten verbirgt, wo der
Hauptknopf steht, und was beim Aufräumen schiefgeht. **Ausgegliedert aus
`oberflaeche.md` am 18.09.2026** — die allgemeinen Oberflächenregeln (Texte,
Zahlen, Barrierefreiheit) gelten weiter und laden zusätzlich.

## Fenster

Höchstens drei sichtbare Zonen: links Objektbaum, Parameter und Verlauf als
einklappbare Abschnitte; Mitte der Viewport; rechts **entweder** Chat **oder**
Prüfbericht, umschaltbar und ganz ausblendbar. Die Umschaltung springt zum
Bericht, wenn eine Warnung entsteht.

**Die Handlungen an der Auswahl stehen in einer zweiten Karte darunter,
nicht in derselben** (Entscheidung Robert, 07.09.2026): Bericht und Chat
schließen mit ihrem eigenen Rand ab, die Auswahlkarte trägt denselben Stil,
den Abstand dazwischen hält `MARGIN`, und durch die Lücke ist das Modell zu
sehen — die Maske der Spalte (`overlay.CardColumn`) nimmt sie aus. Für F9,
Warnungszähler und Höhenverteilung bleibt es **eine** Zone; die zweite Karte
folgt ihrem Inhalt.

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
* **Das Merkmal hat Vorrang vor der Menge.** Wer eine Bohrung angeklickt hat,
  meint sie und nicht den Körper darunter. Beides zugleich gibt es nicht: Der
  Baum gibt kein gewähltes Merkmal zurück, sobald mehrere Zeilen markiert sind.
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

**Ein Merkmal aus einem Baustein meint den Baustein.** Die Regel darüber
schneidet aus, was schon als Feld dasteht; diese sagt, wofür die Felder
gelten. Ein Schlüsselloch bringt zwölf Merkmale mit, zehn davon
Verrundungen, und `fillet` trägt im Register keine einzige Operation — wer
eine Schlitzkante anklickte, sah die Handlungen der Fläche darunter
(Robert, 10.09.2026: „hier sollten wir aber alles für das Schlüsselloch
sehen"). Gefragt wird über `Feature.created_by` und die **Kategorie**
`parts`, nicht über den Namen der Operation: `drill_hole` erzeugt ebenfalls
eine Bohrung mit Provenienz und ist kein Baustein.

Drei Handlungen, und sie gelten dem **Schritt**: Maße ändern, verschieben,
entfernen. Ein `resize_feature` auf die runde Tasche bohrte sie auf und
ließe den Schlitz stehen; was die Größe wirklich ändert, ist die
Schraubengröße im Schritt, und die ändert beide Hälften zusammen. Die Werte
kommen aus dem Schritt und nicht aus der Messung — aus zwei gemessenen
Durchmessern käme keine Schraubengröße zurück, und jedes Zurückschreiben
verlöre ein Stück.

**Und jede Handlung schickt nur ihren eigenen Ausschnitt.** Das Fenster
legt ihn über die Werte, die im Schritt stehen (`_change_part_step`); wer
beim Verschieben den Rest mit Vorgaben überschriebe, setzte die
Schraubengröße zurück, und das fiele erst beim nächsten Öffnen auf.

**Und der Griff im Bild hält sich an dieselbe Regel.** Sie galt bis zum
14.09.2026 nur für die Felder rechts: Der Zug am Griff der Tasche wurde ein
`move_feature` auf die Tasche — der Schlitz blieb bei (10 | 13) stehen, zehn
Verrundungen verloren ihre Erkennung, und der Verlauf trug einen zweiten
Schritt. Jeder Zug an einem Bausteinmerkmal — Griff, Körpergriff,
Bewegen-Leiste — geht in den Schritt des Bausteins
(`MainWindow._move_the_part`); und der Griff hängt an **jedem** seiner
Merkmale, auch an denen ohne eigene Operation (`Viewport.moves_as_a_part`).
Wer eine neue Geste an einem Merkmal baut, fragt zuerst, ob es aus einem
Baustein kam. **Und die Drehachse ist die des Bausteins, nie die des
angefassten Merkmals**: An einem benannten Sitz (`at_feature`) gibt das
Sitzmerkmal die Richtung (`direction_of`, dieselbe Funktion wie im Kern), mit
freier Richtung rechnet die Rundreise `placement_transform` →
`placement_values_of`, und was keins von beidem hat, dreht nur um sein Feld
*Achse* — jede andere Achse bekommt einen Satz mit dem Weg, nicht eine stille
Drehung um die falsche.

**Und die Fläche eines Bausteins ist der Baustein** (16.09.2026). Die Rippe
besteht aus nichts als Flächen, und an einer Fläche hing der Griff der Fläche:
ein Pfeil entlang der Normalen, dessen Zug ein `push_face` auf den
verschmolzenen Körper wurde (Robert: „bei manchen bausteinen keine
möglichkeit zum verschieben"). `Viewport.gizmo_target` kennt an einer
Bausteinfläche kein Press/Pull, `gizmo_feature` hängt den Bewegungsgriff
daran, und der Satz in der Statuszeile nennt den Baustein. Dieselbe Frage
stellen drei weitere Wege, und alle drei gingen bis dahin am Baustein vorbei:

* **Entf.** Am Dach im Baum wie an einer einzelnen Verrundung fällt der
  Schritt des Bausteins (`MainWindow._delete_the_chosen_feature`, derselbe
  Weg wie *Baustein entfernen* rechts) — und nie der Körper. Ohne Baustein
  gilt der Zwilling `remove_feature`; wo auch der nicht greift (eine Fläche,
  ein Gewinde, eine Verrundung), **fällt der Körper**, mit der Ansage in der
  Statuszeile und dem Rückweg über Strg+Z. Diese dritte Lage hat am
  16.09.2026 zweimal die Richtung gewechselt: Morgens fiel an einem
  Bausteindach still der ganze Körper (Robert: „wenn ich etwas im objektbaum
  oder viewport auswähle und entf drücke … wird der ganze körper gelöscht")
  — dafür ist die erste Lage da. Danach löschte Entf an einer Fläche gar
  nichts mehr und verwies auf Escape, und abends am eingelesenen Tray hieß
  es „warum kann ich kein körper mehr löschen": Im Bild trifft ein Klick
  immer eine Fläche, und ein Teil, das sich mit Entf nicht löschen lässt,
  ist eine Sackgasse (Regel 19). Eine Fläche ist kein Ding, das man löscht —
  der Körper ist gemeint. Der Eintrag *Ausblenden* im Kontextmenü heißt an
  einem Merkmal deshalb *Körper ausblenden* — er trifft den Körper, und der
  Name sagt es.
* **Körpergriff und Bewegen-Leiste bei gewähltem Dach.** `selected_feature`
  schweigt bei mehreren Zeilen; `_move_the_part` fragt dann
  `_common_part_step` statt den Zug an den ganzen Körper durchzulassen. **Und
  im Bild bekommt das Dach einen eigenen Griff**
  (`MainWindow._part_grip_anchor` → `Viewport.set_part_grip`): Vorher hing
  dort der Griff des Körpers mit seinem Skalierwürfel, der auf einen Zug die
  Maße des ganzen Teils ändert (Robert: „warum kann ich die bausteine nicht
  über den viewport verschieben?"). Welches Merkmal ihn trägt, sagt das
  Fenster — die Ansicht kann je Merkmal nur fragen, ob es aus *irgendeinem*
  Baustein kam.
* **Und die Bohrung eines Bausteins bekommt ihn ohne *Im Bild einstellen*.**
  Der Knopf steht nur an einem freien Loch (`placed_feature_kinds`), und ein
  Baustein bietet ihn nicht an — an einem Schraubenloch trug die Senkung
  einen Griff und die Bohrung daneben keinen. Die Langlochknöpfe bleiben dort
  weg: Ihr Zug schnitte ein Langloch neben den Schritt des Bausteins, und
  beim nächsten Verschieben bliebe es stehen.
* **Ein gebundener Wert bricht das Merkmalfenster nicht mehr ab.** Steht an
  einer Achse ein Ausdruck, bekommt das Feld das `ValueField` des
  Operationsdialogs (`FeaturePanel._part_fields`); `float("=@staerke")`
  beendete den Aufbau vorher mitten in der Liste, und rechts stand nur noch
  *Maße ändern* — ohne Verschieben und ohne Entfernen. Das ist dieselbe
  Lücke, die §13 beim Operationsdialog schon einmal geschlossen hat.
* **Filament.** Der Schnellwähler färbt an einer Bausteinfläche **alle**
  Flächen des Bausteins (`_part_faces_of_selection`, „Die Zuweisung gilt dem
  ganzen Baustein: 7 Flächen."); Wähler, Zuweisen und Entfernen lesen
  dieselbe Menge (`_filament_targets`). Die Rippe hat kein Filament je Seite
  (Robert: „wo stelle ich von der Versteifungsrippe insgesamt das filament
  ein?"). Die Chips in der Filamentspalte des Baums bleiben je Fläche — wer
  dort klickt, zeigt auf genau eine.

**Und eine gebundene Lage folgt dem Griff.** Hängt `z` eines Bausteins an
`=@staerke`, wandert der Zug als Versatz in den Ausdruck
(`expressions.shifted`: `=@staerke + 5`), statt ihn durch eine Zahl zu
ersetzen oder — wie bis zum 16.09.2026 — jede Bewegung abzulehnen; im
Beispielprojekt, dessen Bausteine ihre Höhe so binden, sprang damit jeder Zug
zurück (Robert: „das verschieben geht nicht springt immer wieder zurück").
Eine Achse ohne Zug bleibt unangetastet, auch ihr Ausdruck. Abgelehnt mit
Satz wird nur noch, was eine **Drehung** an einem gebundenen Wert ändern
würde — die Rundreise rechnet mit Zahlen und könnte den Ausdruck nicht
zurückschreiben.

**Und ein Langloch aus einem Schritt gehört dazu.** Es ist kein Baustein, aber
dieselbe Regel: Hat `slot_hole` es gezogen, ändert *Übernehmen* diesen Schritt
(`_change_slot_step`) und legt keinen zweiten obenauf — der schnitt bis zum
15.09.2026 quer über das erste (Robert: „habe ich 2 langlöcher"). Wer eine
weitere Operation baut, die ein Merkmal aus ihrem eigenen früheren Schritt
noch einmal anfasst, fragt zuerst `created_by`.

**Eine Anzahl ist keine Länge.** `count`, `steps`, `holes` sind ganze Zahlen
ohne Einheit; als Längenfeld hießen sie im Merkmalfenster „2,00 mm", in Zoll
„0,08 in", und gingen als `4.0` in den Schritt. `perceive.actions._kind_of`
nennt `int` deshalb `count`, das Fenster baut dafür ein Ganzzahlfeld, und was
zurückgeht, ist `int`. Wer eine neue Feldart in `ActionField.kind` einführt,
baut sie an beiden Enden — im Kern benannt, im Fenster gebaut und eingesammelt.

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

Solange ein Beispielprojekt offen ist, hat die rechte Spalte einen dritten
Reiter: die Tour (`app/ui/tour.py`, Schritte in `app/core/tour.py`). Sie
erkennt getane Schritte über `projectChanged` am Dokument und Verlauf, „Weiter"
schaltet jeden Schritt auch ohne Erkennung — Angebot, keine Sperre. Der
Warnungssprung zum Bericht lässt der aktiven Tour den Reiter; jedes andere
Projekt räumt ihn weg. Die Erkennungswerte müssen zu `tools/make_examples.py`
passen — driftet beides, wird `tests/test_tour.py` rot.

**Keine Betriebsarten.** Kein Umschalten zwischen „Bearbeiten" und
„Konstruieren" — es gibt einen Zustand, und der ist die Szene.

## Der Hauptknopf

**Ein Hauptknopf entsteht über `style.make_primary()`, nie über
`setDefault(True)`.** Das Stylesheet zeichnet `QPushButton:default` halbfett;
Qt rechnet die bevorzugte Breite aus der **normalen** Schrift des Widgets. Wo
ein Layout dem Knopf genau diese Breite gibt — in einer engen Leiste tut es
das —, wird die Beschriftung abgeschnitten: Auf dem Hauptknopf des
Trennwerkzeugs stand „etzt trenne", 89 Bildpunkte Text in 104 minus
Innenabstand. `make_primary` setzt die Schrift am Widget, damit die Rechnung
sie kennt; das Fett bleibt, denn es ist neben der Akzentfarbe die zweite
Kodierung (Regel 18). `tests/test_style.py` misst gegen die Schrift, mit der
wirklich gezeichnet wird, und verbietet `setDefault(True)` außerhalb von
`style.py`.

**Ein Knopf, der verwirft, entsteht über `style.make_danger()`** — das
Fehlerrot der Palette (`ROLES["error"]`) als Fläche, die Schrift darauf aus
`readable_on`, das Wort als zweite Kodierung (Regel 18). *Abbrechen* unter
*Übernehmen* im Merkmalfenster ist der Fall: gleich breit wie der Hauptknopf,
und ohne eigene Farbe dessen Zwilling (Robert, 11.09.2026). `tests/test_style.py`
misst die Fläche am gezeichneten Knopf.

**Und wo keiner gesetzt wird, setzt Qt selbst einen.** Das ist die stille
Hälfte derselben Regel, und sie ist die häufigere: `QDialog` macht beim
**ersten `show()`** den ersten Knopf mit `autoDefault` zum Default, gleich wo
er im Fenster sitzt. Er trägt damit die Akzentfarbe aus `QPushButton:default`
— aber **nicht** die halbfette Schrift, die `make_primary` am Widget setzt.
Übrig bleibt Bedeutung allein über Farbe, also Regel 18 — und was wie eine
Empfehlung aussieht, ist die Reihenfolge im Layout.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

Zwei Dinge folgen daraus:

* **Ein Fenster ohne Handlung nimmt `style.no_primary()`.** Es räumt den
  Default ab (`setAutoDefault(False)`), und das ist kein Verstoß gegen „ein
  Hauptknopf je Fenster", sondern deren Kehrseite: Wer nichts zu tun anbietet,
  hat auch nichts zu empfehlen. Wer eine Handlung hat, nimmt `make_primary` —
  auch wenn der Knopf gesperrt startet.
* **Gefunden wird das nur am angezeigten Fenster.** Vor dem `show()` meldet
  `isDefault()` überall `False`; ein Quelltext-Wächter nach `setDefault(True)`
  sieht gar nichts, weil es niemand ruft. `tests/test_style.py` hält deshalb
  **beide** Richtungen — `test_every_default_button_of_the_surface_goes_
  through_make_primary` am Text und `test_no_window_wears_an_accent_it_never_
  asked_for` am gebauten Fenster.
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Und ein typloses Stylesheet am Vorfahren nimmt ihm seine Farben.** Eine
Regel ohne Selektor — `setStyleSheet("background: #202225;")` an einer Karte,
einer Leiste, einem Rahmen — gilt für den Träger **und jeden Nachkommen** und
**ersetzt** dort die Regeln des Anwendungs-Stylesheets, statt sie zu ergänzen.
`QPushButton:default` greift dann nicht mehr, und weil diese Regel neben
`font-weight` auch `background` und `color` trägt, steht der Hauptknopf mit
Rahmen und **ohne lesbare Beschriftung** da. Es wirkt über Ebenen — auch aus
dem Stylesheet der Großeltern.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Und nur für die Eigenschaften, die sie selbst setzt.** Das ist die Hälfte,
ohne die man an fünf Stellen sucht, an denen nichts ist: Ein typloses
`border:` — wie es `_flash` beim Aufblinken eines Bereichs setzt
(`main_window.py`) — nimmt dem Hauptknopf gar nichts, weil `QPushButton` im
Anwendungs-Stylesheet eine eigene `border`-Regel trägt und die gewinnt.
Gefährlich ist allein dieselbe Eigenschaft, die der Knopf braucht, und das ist
`background`.

**Und die Abhilfe: Eine Regel mit Kennung trifft nur ihr Ziel.** Wer einem
Träger ein Stylesheet gibt, schreibt es an dessen `objectName` und nicht
typlos. Wo eine breite Regel bleiben muss, bekommt der Hauptknopf darin seine
Farben ausdrücklich (`#surveyNotice #surveyGive` in `app/ui/survey.py`).
`make_primary` bleibt in beiden Fällen — es rechnet die Breite gegen die
halbfette Schrift.

**Ein `QDialog` ist dabei nicht der Unterschied**, auch wenn es zuerst so
aussah: Ohne Stylesheet färbt der Knopf in einem schlichten `QWidget` genauso
wie im Dialog — und ein Gegenbeispiel, das dieselbe Bedingung trägt wie der
Fall, ist keines.

**Ein Knopf ohne sichtbare Beschriftung nimmt Klicks entgegen wie jeder
andere** — ein grüner Klicktest sagt nichts über sein Bild.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**Und er heißt nicht wie sein Werkzeug.** Der Umschalter der Werkzeugzeile
nennt das Werkzeug, der Knopf darin seine Handlung — „Trennen" oben, „Jetzt
trennen" unten. `tests/test_interface_limits.py` hält das fest.

## `setParent(None)` macht ein Kind zum Fenster (RM-101)

Qt kennt keinen „elternlosen Zustand" — ein Widget ohne Elternteil **ist** ein
Top-Level-Fenster. Wer ein Kind-Widget wegräumen will und ihm den Elternteil
nimmt, stellt es für die Dauer bis zum Löschen als eigenes Fenster auf den
Bildschirm. Gemessen am 12.09.2026 im Prüfbericht: vier Knöpfe „Auf das Bett
setzen" als Top-Level nach einem Befundwechsel, zwei davon sichtbar — und
genau das hatte jemand gesehen.

**Weggeräumt wird deshalb mit `hide()` und `deleteLater()`**, nie über den
Elternteil. `takeAt` nimmt es aus dem Layout, `hide` aus dem Bild, und der
Elternteil trägt es bis zum Löschen.

Dasselbe Wissen stand vorher zweimal als Kommentar im Code und einmal nicht:
`MainWindow._close_sketch` nennt den Absturz („ein Fenster, das im selben
Atemzug gelöscht wird"), `SketchEditor.take_constraint_list` die falsch
aufgelösten Tastenkürzel („`plane:xy` statt `plane:xz`"), und
`ReportPanel._show_offers` tat es trotzdem. Ein Kommentar an zwei Stellen ist keine Regel.

**Hinter einen Halt kommt kein Schritt** (§15.3). Hält die Kette an einem
Schritt an, zeigt das Bild den letzten vollständig gerechneten Zustand — und
was hinter dem Halt steht, wird nicht gerechnet. Ein neuer Schritt landete
dort trotzdem: durch den Dialog, in den Verlauf, nie ins Bild (Robert,
11.09.2026, nach einem Schriftwechsel: „da geht nichts mehr wenn ich die
operation ausführe"). Zwei Stellen halten das, und beide sind nötig:

* **Die Sitzung nimmt ihn nicht an** (`Session.halt_in_the_way`, gefragt in
  `apply` mit Entwürfen, `split_async`, `auto_split`, `split_along`,
  `create_lid`, `add_generated` und `accept_proposal`). Die Absage trägt die
  Handlungen des Halts selbst — dieselben Knöpfe wie im Prüfbericht, mit
  Schrittkennung, Werten und Körper, damit `error_handlers` sie ausführen
  kann (Regel 17). Eine Änderung **ohne** Schritt (Parameter, Passung,
  Drucker) geht weiter, denn die kann den Halt lösen; ebenso Rückgängig,
  *Schritt löschen* und die Wege des Verlaufs (`change_params`,
  `repair_and_retry`, `split_and_retry`, `recount_and_retry`).
* **Die Oberfläche sagt es vorher** (`_halt_reason`, die erste Frage in
  `_reason_locked`): Aktion, Palette, Karte und Zwillingshaken tragen den
  Grund mit Schrittnummer und Titel, dazu Automatisch teilen, Einfügen,
  Erzeugen, Zeichnen, Formen, Skelett und der Filamentwähler — dieselbe
  Bauart wie die Lizenzsperre und die Gestensperre daneben. Die Werkzeugzeile
  bleibt frei: Messen, Analyse und Schichten lesen nur.
* **Und das Merkmalfenster gehört dazu** (`FeaturePanel.set_locked`,
  13.09.2026). Es war die eine Bedienstelle, an der der Halt nicht ankam:
  Felder und beide Knöpfe blieben aktiv, und der Versuch endete in einem
  modalen „Das hat so nicht funktioniert" — eine Sackgasse hinter einem Klick,
  den die Oberfläche vorher hätte abraten können (Regel 19). Zwei Kodierungen
  (Regel 18): graue Knöpfe **und** der Grund als sichtbare Zeile über ihnen,
  dazu in Kurzhilfe, Statuszeile und zugänglicher Beschreibung. Die Sperre
  überlebt den Neuaufbau der Zeilen — ein Klick auf ein anderes Merkmal hebt
  sie nicht auf — und fällt nach einem Undo ohne Neuauswahl, weil
  `_update_actions` mit dem neuen Ergebnis den leeren Grund meldet.

Gemessen: Vorher standen nach dem Halt drei Schritte im Verlauf und einer im
Bild; nachher keiner, und der erste Knopf der Absage („Stückzahl anpassen und
erneut versuchen") löst den Halt — `test_a_halted_chain_takes_no_new_step_
and_names_the_way_on`.

## Die automatische Sicherung

Sie ist für den **Absturz** da (§38) und nie dafür, eine Entscheidung des
Nutzers zu überstimmen. Drei Regeln, alle drei einmal gebrochen gewesen:

* **Verworfen heißt verworfen.** `_may_discard` räumt die Sicherung, wenn der
  Nutzer *Verwerfen* wählt. `closeEvent` schrieb dort eine — nach der Frage,
  also genau dann, wenn jemand gerade Nein gesagt hatte.
* **Abgelehnt heißt einmal gefragt.** Eine Sicherung, die man nicht öffnen
  will, wird gelöscht; sonst ist sie weiter neuer als die Datei und dieselbe
  Frage kommt bei jedem Öffnen wieder. Gemessen waren es sechs Öffnungen und
  sechs Fragen. Was das Ablehnen kostet, steht im Dialog — eine Löschung ohne
  Ansage wäre der nächste Fehler.
* **Angenommen speichert in die Datei des Nutzers.** `Session.recover(candidate,
  path)` nimmt den Inhalt der Sicherung und behält den Pfad des Projekts.
  Über `open_project(candidate)` wurde die Sicherung zum Projekt: ein
  „Speichern" schrieb nach `…p3d.autosave`, die eigentliche Datei blieb
  unberührt, und die wiederhergestellte Arbeit war beim nächsten Öffnen wieder
  fort.
* **Namenlos heißt je Dokument eine Kennung, nicht je Rechner eine Datei.**
  Zwei Fenster mit je einem neuen, ungespeicherten Projekt schrieben beide
  `unsaved.p3d.autosave`: Die zweite Sicherung ersetzte die erste, und das
  Aufräumen aus dem einen Fenster löschte die des anderen (Gesamtreview
  05.09.2026, CORE-09). `Session.recovery_token` kommt aus
  `project.recovery_token()`, `_reset_for` zieht je Dokument eine neue, und
  jede der vier Sicherungsfunktionen nimmt sie entgegen. Angeboten wird beim
  Start die jüngste **fremde** Sicherung; abgelehnt wird genau sie geräumt
  (`discard_recovery`), angenommen wandert sie unter die eigene Kennung.

## Wie die Karten ihre Höhe teilen

`OverlayHost._share_room` verteilt die Höhe einer Zone auf ihre `RoomTaker`.
Drei Zusagen, und alle drei sind schon gebrochen worden:

* **Gerechnet wird nie mit den Höhen, die gerade gesetzt wurden.** Eine
  Zuteilung, die ihr eigenes Ergebnis liest, bekommt beim nächsten Durchlauf
  andere Zahlen und die Karte läuft auf und ab. Deshalb taugt `natural_height`
  **innerhalb** der Zuteilung nicht: sie liest für ihre Rollbereiche die
  gelegten Höhen. `extra_height` rechnet strukturell — je Posten der
  Unterschied zwischen dem, was er als Ganzes wünscht, und dem, was die Karten
  darin wünschen.
* **Was nicht den Karten gehört, wird abgezogen.** Abschnittsköpfe,
  Parameterleiste, Layoutabstände. Ungekürzt verteilt die Zuteilung mehr Höhe,
  als die Zone hat: Der Objektbaum stand auf 500 Pixeln in einem Abschnitt von
  121, das Elternwidget schnitt die Differenz weg, und weil der Baum von seiner
  eigenen Höhe ausging, meldete sein Rollbalken dazu nichts. Zehn Zeilen waren
  nicht abgeschnitten, sondern unerreichbar.
* **Jede Karte nennt ihren Boden** (`RoomTaker.least_height`), und verteilt wird
  nur, was darüber liegt. Sonst ist die Zuteilung eine Bitte. Der Boden hat
  zwei Quellen, und beide zählen — `fit_to_rows` mit seinen drei Mindestzeilen
  und der leere Zustand, dessen Höhe aus dem umbrochenen Satz kommt
  (`fit_wrapped`) und nicht aus der Zeilenrechnung. **Und nie höher als der
  Wunsch**: Eine Karte, die überhaupt nur eine Zeile *hat*, forderte über jene
  drei Mindestzeilen 130 Punkte für 128 gewünschte — Platz, den sie niemandem
  zeigen kann, während die Nachbarn ihn brauchen.

`tests/test_overlay.py` hält alle drei: „settles on one answer",
„moves a card once", „no card is pushed outside its section".
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)

**`fit_to_rows` rechnet mit *einer* Zeilenhöhe** — der ersten, mal der Zahl
der Zeilen. Für einen Baum, in dem jede Zeile gleich aussieht, ist das
richtig; für eine Liste mit fetten Zwischenüberschriften ist es zu wenig. Wer
eine Liste mit ungleichen Zeilen bemisst, nimmt `overlay.rows_height` — es
misst jede Zeile einzeln, und `wanted_height` muss dieselbe Quelle nehmen wie
das Setzen, sonst fordert die Karte etwas anderes, als sie einrichtet.

**Und was unter der Liste steht, gehört in beide Rechnungen.** Hinweis und
Knöpfe einer Karte sind kein Beiwerk der Zone, sondern Teil der Karte: Wer der
Liste die ganze Zuteilung gibt, schiebt sie unten heraus — und mit ihnen den
einzigen Weg, den die Karte anbietet.
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026)
