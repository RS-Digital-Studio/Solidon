# Begründungen zu `.claude/rules/ansicht.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

## Regeln für die Ansicht

Aus den Kommentaren im `paths:`-Kopf der Regel:

Das Renderer-Paket ist am 05./06.09.2026 entstanden und fiel bis dahin aus dieser Liste: Wer am Renderer arbeitete, bekam die Ansichtsregeln nicht zu sehen, obwohl sie über seine Dateien sprechen.

Die Maßtinte rechnet seit dem 21.09.2026 mit ``display_to_world`` und dem Geräteverhältnis — und lud diese Regel bis dahin nie.

Und die 3D-Maus, aus demselben Grund wie das Renderer-Paket: Der ganze Abschnitt über sie steht in dieser Datei — Achsenabbildung, Empfindlichkeit, der Übersprechfilter —, aber wer `spacemouse.py` anfasste, bekam nur `oberflaeche.md` zu sehen. Nachgetragen am 07.09.2026.

**Zwei Gebiete sind am 18.09.2026 von hier weggezogen**, weil sie für zwei
Dateien galten und für dreiundzwanzig luden:

| Gebiet | Steht jetzt in | Lädt bei |
|---|---|---|
| Der Langlochgriff, der Bewegen-Griff, die Beschriftung am Griff | `griffe.md` | `slot_handle.py`, `viewport.py`, `transform_bar.py` |
| Die eigene Steuerung, der zweite Treiber, Drehpunkt und Drehteller | `kamera.md` | `spacemouse.py`, `viewport.py`, `render/navigator.py`, `render/api.py`, die Einstellungen |

Wer am Viewport selbst arbeitet, bekommt weiterhin alle drei.

## Die Auswahl hat eine Tiefe, und der Klick wandert durch sie

Seit dem 03.09.2026 schiebt links im Schema `solidon` **auch** die Ansicht.
Das ändert an der Stufung nichts: `_left_up` trennt Klick und Zug an der
Zugschwelle des Systems, und nur der Klick wandert (siehe unten).

* **Der Linksklick geht eine Stufe.** Der erste wählt den Körper, der nächste
  das Merkmal unter dem Zeiger. Das Modell von Figma und Illustrator: erst die
  Gruppe, dann das Element darin. Vorher gewann sofort das Merkmal, und ein
  Körper mit erkannten Bohrungen war per Klick **überhaupt nicht auswählbar** —
  wer die Platte verschieben wollte, musste in den Objektbaum ausweichen.
* **Der Rechtsklick meint immer das Genaueste** (`_select_at(..., direct=True)`).
  Das folgt aus §18.5: Weg 1 passt ein fremdes Modell an, indem man auf die Stelle
  zeigt, die stört. Gestuft wäre diese Zusage an eine Vorbedingung geknüpft, die
  niemand kennt. Die Operationen dafür stehen im Auswahlfenster am Merkmal; das
  Menü zeigt nur, was es dort gibt (Ursprungsschritt, Zeichnen, Ausblenden).

**Ein Merkmalsklick am schon allein gewählten Körper meldet ihn nicht noch
einmal** (Durchsicht 0.5.1). `objectPicked` wählte im Baum den Körper ohne
Merkmal — Maßgruppe ab, Merkmalfenster leer, Körperfarbe hin und zurück — und
gleich danach alles für das Merkmal; von Bohrung zu Bohrung eine ganze
Auswahlrunde je Klick. Und die Ansicht wählt das Merkmal erst **nach**
`featurePicked` selbst, und nur, wenn die Auswahl aus dem Baum nicht ankam
(eine Ansicht ohne Baum); mit Umschalt oder Strg bleibt die alte Folge, weil
der Baum dort auch herausnimmt.

### Und eine Kante gehört auf dieselbe Stufe

Bis dahin pickte der Renderer Flächen und Merkmale, keine Kanten; die
Kantenwahl der Verrundung lag als Liste im Dialog („Senkrecht · 20 mm ·
x -20,0, y -15,0", zum Ankreuzen). Die Lage in dieser Zeile fragt
`edges.edge_lie_of`: Ein Ring hat keine Richtung und liegt, wie seine Ebene
liegt — die Mündung einer Querbohrung heißt „Senkrecht“ (RM-269). Wer **diese eine Ecke** brechen wollte,
musste sie in einer Aufzählung wiedererkennen.

Sie ist jetzt eine dritte Sache, die ein Klick treffen kann — und sie geht
denselben Weg wie das Merkmal, das ist der ganze Entwurf (Robert, 10.09.2026:
„man wählt auch erst den körper, dann das untergeordnete wie bei allem anderen
auch"). `_goes_deeper` beantwortet die Stufenfrage für **beide**; zwei
Rechnungen dafür liefen auseinander, und dann wählte ein Klick eine Kante an
einem Körper, den derselbe Klick gerade erst als Ganzes gewählt hätte.

Vier Festlegungen:

* **Gemessen wird im Bild, nicht in der Szene.** Eine Kante ist dort eine
  Linie ohne Breite; in Millimetern wäre der Fangbereich herangezoomt quer
  über die Fläche und herausgezoomt kleiner als der Zeiger
  (`EDGE_REACH_PIXELS`, zehn Bildpunkte — enger als die Reichweite eines
  Merkmals, denn wer die Kante meint, zielt genauer).
* **Der Abstand entscheidet, bei Gleichstand die Tiefe**
  (`render.edges.nearest_polyline`). Ohne die zweite Hälfte bekäme ein Klick
  auf die Silhouette eines Quaders zufällig die Kante auf der Rückseite —
  dieselbe Stelle im Bild, dreißig Millimeter weiter weg.
* **Gegen die Strecken, nicht die Punkte.** Eine lange gerade Kante hat zwei
  Punkte und tausend Bildpunkte dazwischen, und einen davon meint der Zeiger.
  Bögen kommen als Punktfolge aus dem Kern (`brep.edit.edge_points`): Der
  Schwerpunkt eines Viertelkreises liegt neben ihm.
* **Der Körper gibt die Auswahlfarbe ab**, wie an ein Merkmal.
  `highlighted_object()` gibt `None` zurück, solange eine Kante gewählt ist.
  Das ist der Fund, den nur das gerenderte Fenster zeigen konnte: Die Linie
  liegt auf dem Körper, und in derselben Farbe ist sie unsichtbar — die Suite
  war grün, jede Auskunft daneben stimmte, und im Bild leuchtete der ganze
  Quader.

**Und drei Dinge, die eine neue Auswahlart mitbringt** — alle drei standen
beim ersten Anlauf offen und kamen aus dem Review, keines aus der Suite:

* **Sie muss überall fallen, wo eine andere Auswahl entsteht.** Die Kante hing
  an genau einem Weg — ihrem eigenen Klick — und überlebte Escape, den
  Objektbaum und jede Merkmalsauswahl. Weil sie die Auswahlfarbe an sich zieht,
  bekam der **neue** Körper dabei keine: Ein Klick in den Baum wählte sichtbar
  nichts. `_drop_edge()` ist deshalb eine Stelle, gerufen aus `select`,
  `select_feature` und `_refresh_feature_selection`.
* **Sie muss in `selection_depth` mitzählen.** Sonst ist der Weg zurück nicht
  eingelöst: Escape sprang von der Kante aus dem Körper heraus statt eine
  Stufe auf ihn zurück.
* **Und sie darf keinen fremden Klick verschlucken.** Der Kantenklick stand
  vor `_on_picked` und damit vor dem Abzweig für Messen, Trennen, Skelett und
  Formen — der Messklick verschwand **stumm**, obwohl der Messweg für genau
  diesen Fall einen Satz führt. Gefragt wird `_means_a_feature()`, also
  dieselbe Rangfolge wie beim Zeiger. Dasselbe gilt für Umschalt und Strg,
  solange keine Kante gewählt ist: Wer dazunimmt, meint Körper oder Merkmal.
* **An einer gewählten Kante nehmen Umschalt und Strg weitere Kanten desselben
  Körpers dazu** (RM-563). Der Kunde fand keinen Weg, mehrere Kanten zu
  verrunden: Der Kantenklick verweigerte das Dazunehmen ausdrücklich, und die
  Gruppen im Dialog („alle senkrechten“) trafen selten genau seine. Die
  zuletzt geklickte führt (Fasenmarken, Titel), ein Fehlklick mit Taste wirft
  die Sammlung nicht weg, und rechts auf eine der gewählten bleibt die Gruppe,
  wie bei mehreren Körpern. Menü und Befehlspalette belegen den Dialog mit
  denselben Kanten vor, sonst rundete OK still die Vorgabegruppe. Und das
  Merkmalfenster behält beim Dazunehmen, was schon eingetragen ist
  (`FeaturePanel.show_edge`): Wer zuerst den Radius tippt und dann die nächste
  Kante holt, meint ihn weiter.
* **Eine Ecke bringt ihre Kanten, und die Linie zeigt die ganze Kontur**
  (RM-590, RM-579, Review G). Die Kunden-E-Mail zu RM-563 nannte „Kanten und
  Ecken“: Eine Ecke verrunden hieß, ihre drei Kanten einzeln mit Strg
  zusammenzuklicken, und ein Klick auf die Ecke traf eine davon. Eine Ecke ist
  ein Endpunkt, an dem sich mindestens drei Kanten treffen — an zweien liegt
  ein Knick oder der Übergang einer Strecke in einen Bogen —, und sie fängt nur
  in halber Kantenreichweite, damit eine Kante kurz vor ihrem Ende anklickbar
  bleibt. Am exakten Körper rundet OpenCASCADE eine Kante mit jeder tangential
  anschließenden; am Quader mit gerundeten senkrechten Kanten ging Verrunden an
  einer oberen Strecke über alle acht Stücke des Rands, und die Linie zeigte
  eine. Gelesen wird die Kontur aus demselben Builder, ohne zu bauen.

**Ein Vorfilter misst gegen den Hüllquader der Kante, nicht gegen ihre
Stützpunkte.** Der erste Anlauf tat das zweite und warf zwölf von zwölf
Kanten weg: Eine gerade Kante hat genau zwei Punkte, und bei dreißig
Millimetern Länge liegt ihre Mitte fünfzehn davon entfernt — derselbe Satz,
der drei Absätze weiter oben für den Bildraum schon steht. **Eine Regel, die
man selbst aufgeschrieben hat, schützt nicht davor, sie zwei Funktionen
weiter zu brechen.** Der Quader ist großzügiger als die Kante, und das ist
hier richtig: Ein Vorfilter darf zu viel durchlassen, nie zu wenig — genauer
trennt der Bildabstand danach.

**Der Zeiger stellt dieselbe Frage** (seit 10.09.2026): `_look_under_pointer`
fragt `_edge_under`, und das sind wörtlich die Bedingungen von `_edge_click` —
Stufe, Körper unter dem Zeiger, Kante im Bild. Die Rolle bleibt dabei
`feature`, und das ist Absicht: Eine Kante ist die zweite Stufe wie ein
Merkmal, derselbe Handgriff hat dasselbe Bild. Ein eigener Kantenzeiger würde
einen Unterschied behaupten, den die Bedienung nicht macht.

**Und rechts meint die Kante ohne Vorbedingung** (14.09.2026). Der Rechtsklick
ging zwar zuerst zur Kante, stellte die Stufenfrage aber fest mit
`direct=False` — auf einem noch nicht gewählten Körper zeigte er also das Menü
der Fläche darunter, auf dem gewählten das der Kante. Damit hing die Zusage aus
§18.5 wieder an einer Vorbedingung, die niemand kennt; `_edge_click` nimmt
`direct` jetzt entgegen, wie `_click_target` daneben.

Zwei Dinge hängen mit daran, und beide waren falsch:

* **Der Körper wird angesagt, bevor die Kante gesetzt wird** — dieselbe
  Reihenfolge wie in `_select_at`, und aus demselben Grund: Die zwei
  Handlungen an der Kante holen ihren Eingang aus dem Objektbaum. Ohne die
  Ansage leuchtete nach einem direkten Klick die Linie, und *Verrunden*
  daneben fände nichts, woran es ansetzen könnte. Auf dem gestuften Weg
  kostet das nichts: Dort ist der Körper längst gewählt.
* **Gesucht wird im Bild, also mit dem Punkt aus dem Bild.** Der Rechtsklick
  rechnete ihn vorher in die Szene zurück (`_from_view`) und gab ihn so an
  `_edge_click` weiter — auf Platte 2 suchte er die Kante damit eine
  Bettbreite neben dem gezeichneten Körper und fand keine. Nur die Körper-
  und Merkmalssuche darunter fragt die Szene; für die Kante ist der Bildpunkt
  der richtige, genau wie beim Linksklick.

### An der gewählten Kante stehen die Seiten der Fase

Welche Fläche die Breite trägt und welche den zweiten Abstand oder den
Winkel, war nur als Regel im Tooltip zu lesen („am weitesten nach oben, dann
hinten, dann rechts"). Das Bild zeigt es jetzt, und drei Festlegungen gelten
für jede Marke dieser Art:

* **Die Ansicht rechnet nicht und schaltet nicht.** Wo die Marken liegen,
  sagt der Kern (`edge_ops.chamfer_marks`) mit denselben Normalen, mit denen
  die Operation fast — eine Marke, die eine andere Fläche nennt als die Fase
  nimmt, ist damit ausgeschlossen. Ein Klick auf eine Marke ändert keinen
  Wert in der Ansicht, er meldet (`chamferSidesSwapRequested`), und das
  Fenster schaltet den Haken im Merkmalfenster; Vorschau und Übernehmen
  lesen denselben Stand wie nach einem Klick auf den Haken.
* **Die zweite Kodierung ist eine Ziffer, keine Farbe** (Regel 18): „1 · …"
  an der Bezugsfläche, „2 · …" an der anderen; die breitere Linie sagt es ein
  drittes Mal. Die Statuszeile nennt beide Flächen in Worten, denn die
  Beschriftung im Bild erreicht keinen Bildschirmleser.
* **Die Marke nimmt den Klick vor Kante und Fläche — aber nur ihre äußere
  Hälfte.** Beide Marken beginnen an der Kante; zählte die ganze Linie, wäre
  die Kante selbst nicht mehr anzuklicken. Der Zeiger zeigt über der Marke
  dieselbe Rolle wie über einer Kante (`_set_hover_edge`), weil derselbe
  Handgriff dasselbe Bild hat.

### Ein Merkmal hat eine Reichweite

`_feature_at` hatte keine, und das war der gemeldete Fehler: Es nahm das
Merkmal mit dem nächsten **Mittelpunkt**, es gab also immer einen Gewinner,
sobald der Körper ein Merkmal hatte
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Gemessen wird gegen die **Dreiecke** des Merkmals
(`geom.mesh.distance_to_triangles`), gegen den nächsten Ort *auf* dem Dreieck
und nicht gegen den nächsten Eckpunkt — die Deckfläche der Platte hat zwei
Dreiecke, ein Klick in ihre Mitte liegt vierzig Millimeter von jedem Eckpunkt
entfernt. Die Reichweite wächst mit der Diagonale (`FEATURE_REACH_SHARE`),
weil im dezimierten Anzeigenetz gepickt wird (§18.9).

Drei Folgen davon:

* **Ein Klick trifft die Oberfläche, nie die Achse.** Der Mittelpunkt einer
  Bohrung liegt im Leeren. Drei Tests zeigten dorthin und prüften damit die
  Rechenweise statt einen Klick; wer einen neuen schreibt, nimmt die
  Bohrungswand (`on_the_bore_wall`).
* **Ein Merkmal ohne eigene Dreiecke bleibt über seinen Mittelpunkt
  erreichbar** — eine offene Kantenschleife hat keine, und sie ist der Befund,
  den man am ehesten anklicken will.
* **Vorbereitet wird je Körper und Auswertung** (`_feature_geometry`), mit dem
  Hüllquader als billiger Vorprüfung: Die Frage stellt der Zeiger bei jeder
  Ruhepause neu (90 ms), und der genaue Abstand ist nur für die ein oder zwei
  Merkmale nötig, deren Quader ihn überhaupt erreicht. Geleert wird in
  `show_scene` — die Dreiecke gehören einer Auswertung, nicht dem Viewport.

**Und jeder Klickpfad rechnet über `_from_view` in die Szene zurück** (§25) —
Linksklick, Rechtsklick und Zeigersuche gleichermaßen; auf Platte 2 fragt sonst
einer eine Bettbreite daneben
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

### Ein Klick ist eine Blickrichtung, kein Punkt

Der Abschnitt darüber setzt voraus, dass unter dem Zeiger ein Dreieck liegt.
**Bei einer Bohrung liegt dort keines** — in der Draufsicht trifft ein Klick in
die Bohrungsmitte nichts, und schon wenige Bildpunkte neben ihr gewinnt die
Deckfläche (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Zwei Ursachen, und beide liegen vor der Reichweite:

* **Senkrecht in eine Durchgangsbohrung trifft der Strahl nichts.** Die
  Zylinderwand liegt parallel zu ihm, dahinter kommt keine Fläche. Der Picker
  gab nichts zurück, `_on_left_click` machte daraus `objectPicked.emit("")` —
  ein Klick mitten in die Bohrung **hob die Auswahl auf**. Ausgerechnet in der
  Ansicht, in der man ein Lochbild anklickt.
* **Landet der Strahl daneben auf der Deckfläche, gewinnt sie immer.** Ihr
  Abstand ist null, der der Bohrung größer als null; die Reichweite ist eine
  Obergrenze und kein Vorrang.

Gefragt wird deshalb der **Sichtstrahl** (`_pick_ray` → `_bore_aim`, gerechnet
in `bore_span`): Welche Bohrung durchquert er, bevor er auf dem Sichtbaren
landet? Drei Eigenschaften daran sind tragend:

* **`until` ist der Auftreffpunkt, und ohne diese Grenze wird es falsch.** In
  der Vorderansicht liegt hinter der Stirnfläche jede Bohrung der Platte; was
  der Strahl erst dahinter durchquert, hat niemand gemeint; die Vorderansicht
  ist die Gegenprobe und wählt weiter die Stirnfläche.
* **Der Achsbereich kommt aus den Dreiecken des Merkmals**, nicht aus `depth`
  und nicht aus dem Hüllquader — der kennt die Achse nicht, und eine schräge
  Bohrung hat beides. Ohne die Begrenzung reicht der Zylinder unendlich weit
  und eine Bohrung am einen Ende fängt Klicks am anderen.
* **Zurück kommt ein Punkt auf der Achse**, nicht der Auftreffpunkt. Damit
  bleibt die ganze Kette dahinter unberührt — Stufung, Kontextmenü und Zeiger
  bekommen einen Punkt wie immer, und von einem Punkt im Loch findet
  `_feature_inside` die Bohrung. Auf der Achse und nicht in der Mitte des
  Durchtritts: Ein Punkt über der Öffnung liegt der Deckfläche näher als der
  Bohrungswand, und dann gewinnt wieder die Fläche.

Der entartete Fall ist der wichtigste und der einzige, den man leicht verliert:
**Blickt man senkrecht in die Bohrung, läuft der Strahl parallel zur Achse**,
es gibt keinen Ein- und Austritt durch den Mantel, und die quadratische
Gleichung dazu hat keinen Leitkoeffizienten. Wer dort durch null teilt,
verliert genau die Draufsicht.

**Und ein Langloch ist im Querschnitt kein Kreis** (24.09.2026). Gerechnet
wird gegen seinen Umriss — zwei Kreise an den Enden der Mittellinie und das
Band dazwischen, konvex, also ein Abschnitt je Strahl (`_stadium_span`) —,
und vom Punkt im Loch führt `_feature_inside` über den Abstand zur
Mittellinie zum Langloch. Mit dem Kreis um die Mitte allein traf ein Klick in
das Ende eines Langlochs in der Draufsicht nichts, und ein Druck dort zog den
Körper statt das Langloch. Wer eine weitere Öffnungsform dazunimmt, gibt ihr
ihren Umriss, nicht den Kreis ihres Durchmessers.

**Gefragt wird an drei Stellen, und an allen drei derselbe Aufruf**
(`_aim_at`): Linksklick, Rechtsklick, Zeigersuche. Der Zeiger kostet damit
einen Oberflächen-Pick je Ruhepause statt eines Blicks in den Tiefenpuffer —
gemessen 0,16 ms unter VTK, und die Zusage darunter ist es wert: Ein Zeiger, der die
Merkmalsform über einer Bohrung zeigt, wo der Klick sie nicht wählt,
verspricht etwas, das nicht eintritt. **Nicht** gefragt wird beim Messen,
Bemalen und Ziehen — dort ist eine Stelle auf der Oberfläche gemeint, und ein
Punkt in der Luft wäre falsch.

**Und die Reichweite wirkt hier als Zielhilfe**, nicht als Grenze: Gezielt wird
in Pixeln, und der Rand einer M3-Bohrung ist an einem großen Teil wenige davon
breit. Derselbe Wert wie beim Klick auf die Fläche eines Merkmals, denn es ist
dieselbe Frage — wie weit daneben meint noch dies. Bei 24 Pixeln, also weit
außerhalb der Bohrung, bleibt es die Fläche.

### Und wo kein Merkmal ist, ist trotzdem ein Körper

Der Abschnitt darüber löst die **Bohrung**, weil sie ein Merkmal ist, auf das
man zeigen kann. Ein **rechteckiger Ausschnitt** ist keines: vier Wandflächen,
von denen keine „richtiger" ist als die andere — und bei senkrechtem Blick
liegen sie parallel zum Strahl, dort ist so wenig ein Dreieck zu treffen wie an
der Bohrungswand. Der Picker gab nichts zurück, und ein Klick in den Ausschnitt
**hob die Auswahl auf**.

Entschieden wird dort deshalb nicht, welches Merkmal gemeint ist, sondern
**welcher Körper**: Wer in eine Öffnung zeigt, hat auf das Teil gezeigt.
`_through_aim` fragt dafür die **konvexe Hülle** (`geom.mesh.hull_planes` und
`ray_span_in_hull` — die Rechnung steht im Kern, in `app/ui` gibt es kein
`trimesh` und soll keines geben). Drei Eigenschaften, alle drei tragend:

* **Die Hülle und nicht der Hüllquader.** Der Quader eines L-Profils reicht
  weit ins Leere, und damit wäre die Zusage aus §18.5 weg, dass ein Klick
  daneben die Auswahl aufhebt — der einzige Weg, sie ohne den Objektbaum
  loszuwerden
  (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).
* **Die Kerbe zählt mit, und das ist gewollt.** Durch den fehlenden Quadranten
  eines L-Profils läuft der Strahl in der Hülle, ohne das Netz zu treffen. Ein
  Kriterium, das das ausnimmt, müsste „Loch" von „Einbuchtung" unterscheiden —
  eine Unterscheidung, die niemand trifft, der auf ein Teil zeigt und zwei
  Bildpunkte neben die Silhouette kommt.
* **Nur wenn sonst nichts da ist.** Gefragt wird erst, wenn weder eine Fläche
  noch eine Bohrung getroffen wurde. Damit kostet der Normalfall nichts, und
  die Hülle wird je Körper einmal gerechnet (`_object_hulls`, geleert mit den
  Merkmalsdreiecken in `show_scene`).

**Der Kostendeckel ist derselbe wie beim Schattenumriss, und aus demselben
Grund:** Die exakte Hülle von `dense_1m.stl` braucht 5084 ms, weil bei einer
feinen Kugel jeder Punkt auf ihr liegt. Über eine Stichprobe von 4096 Punkten
plus den äußersten in sechs Achsenrichtungen sind es 20 ms; an der Korpusplatte
liefern beide dasselbe, zwölf Flächen und 32 000 mm³. Gerechnet wird über
**Halbräume**, nicht über ein Hüllnetz — ein Strahl gegen 8202 Hülldreiecke
wäre wieder das, was die Stichprobe gerade vermeidet.

## Die Leertaste gehört dem, der sie braucht

**Ohne `answers_space` schaltete während jeder Vorschau in keinem Fenster ein
Haken** (RM-448): Der Vergleich der Vorschau nahm die Taste überall, auch
dort, wo der Fokus auf einem Haken oder Knopf lag.

## Messen

§18.1 sagt es ohne Vorbehalt: „orthografisch ist beim Messen Pflicht". Der
Werkzeugweg setzte trotzdem nur den Messmodus — die vorhandene Umschaltung
gehörte dem Skizzeneditor. Wer perspektivisch arbeitete und zu messen anfing,
setzte seine Punkte in einem Bild, in dem zwei gleich lange Strecken
verschieden lang aussehen, je weiter sie von der Bildmitte weg liegen.

**Die Maße waren nie falsch** — sie kommen aus den Fangkoordinaten und nicht
aus dem Bild. Falsch war, worauf der Nutzer beim Setzen zielt, und das ist der
Grund für die Pflicht.

`MainWindow._on_measure_mode` schaltet deshalb beim **Betreten** um und beim
**Verlassen** zurück. Drei Feinheiten hängen daran:

* **Nicht bei jedem Wechsel der Messart.** Von *Abstand* auf *Wandstärke* ist
  kein Verlassen; ein zweites Merken überschriebe die Projektion, zu der der
  Nutzer zurückwill, und er stünde nach dem Messen orthografisch da, ohne es
  je gewählt zu haben.
* **`settings.projection` bleibt unberührt.** Messen stellt vorübergehend um,
  wie der Skizzeneditor daneben; die gespeicherte Wahl gehört dem Nutzer. Das
  Häkchen im Menü zieht dagegen mit, denn es sagt, was **gilt**.
* **Eine ausdrückliche Wahl im Menü gewinnt.** `action_projection` setzt
  währenddessen auch das Rückkehrziel — die Pflicht gilt dem Werkzeug, nicht
  gegen den Nutzer.

Der Abschnitt darüber gilt der **Auswahl**: Dort fragt der Zeiger dieselbe
Rechnung wie der Klick, damit er nichts verspricht, was nicht eintritt. Beim
Messen gilt dasselbe, und dort fehlte es — mit demselben Ergebnis, nur
umgekehrt: Der Kern **zieht** einen Messklick auf die nächste Ecke oder Kante
(`geom.measure.snap`), und im Bild geschah das erst *nach* dem Klick. Wer zielt,
zielte blind (Robert, 03.09.2026: „bei messen ist das zielen relativ schwer").

Drei Sachen hängen daran, und jede war für sich falsch:

* **Die Fangweite gehört in Bildpunkte** (`MEASURE_SNAP_PIXELS`, 16). Der Kern
  rechnet in zwei Prozent der Modelldiagonale, weil er kein Bild hat — an einem
  200 mm langen Teil vier Millimeter. Herangezoomt sind das zweihundert
  Bildpunkte und der Fang reißt den Punkt quer über die Fläche; herausgezoomt
  sind es zwei und es gibt keinen Fang mehr. `_snap_radius_at` misst den
  Maßstab an der Stelle (`_pixels_per_mm_at`, zwei Punkte quer zur
  Blickrichtung durch dieselbe Projektion — wie `pixels_per_mm`) und gibt dem
  Kern seine Weite in Millimetern. Ohne Bild kommt `None` zurück, und dann
  bleibt es bei der Weite des Kerns.
* **Gefangen wird nur, was man sieht.** Das ist die Hälfte, die im Kern lag:
  `visible_edges` nimmt scharfe und offene Kanten, `corner_points` nur Punkte
  mit drei sichtbaren Kanten. Über alle Dreieckskanten gerechnet fing ein Klick
  zwei Millimeter neben der Ecke mit Abstand **null** auf der Diagonalen der
  Deckfläche — auf einer Linie, die es im Bild nicht gibt.
* **Und die Marke steht vor dem Klick da.** `_preview_snap` bei jeder Ruhepause
  des Zeigers, dieselbe Rechnung wie der Klick (`_snap_for_measure`, ein
  Aufruf, zwei Anrufer). Beim Winkelmessen bleibt es bei der Merkmalssuche —
  dort wählt man ebene Flächen, und deren Hervorhebung *ist* die Zielhilfe.

Die Marke ist ein Kreuz mit einem Punkt in der Mitte, **in der Bildebene**
(`_screen_axes`) und in fester Bildgröße (`SNAP_MARK_PIXELS`,
`SNAP_DOT_PIXELS`). Beides ist gemessen und nicht gewählt: Entlang der
Weltachsen gezeichnet war sie in der isometrischen Ansicht auf ein Drittel
verkürzt und im gerenderten Fenster kaum zu finden, und in Millimetern wüchse
sie beim Hineinzoomen quer über das Teil.

**Worauf gefangen wurde, sagt die Größe** — Ecke groß, Kante mittel, freie
Stelle klein — und ein Satz in der Beschreibung der Ansicht
(`snap_sentence`, gelesen von Bildschirmlesern). Nicht die Farbe (Regel 18),
und nicht die Statuszeile: Die trägt beim Messen den Fortschritt („Erster Punkt
gewählt"), und ein Satz, der bei jeder Mausbewegung wechselt, überschriebe ihn.
Der Satz gehört auch **nicht** in die Szene — ein übersetzter Text am
Renderer stünde in sechs Sprachen an einer Stelle, die keine Prüfung sieht
(siehe „Was am Griff steht, ist ASCII").

Weg ist die Marke, sobald der Zeiger das Bild verlässt, das Werkzeug wechselt
oder die Szene neu aufgebaut wird. Die Maße überleben eine Auswertung, die
Marke nicht: Sie zeigt auf eine Ecke, die dieser Schritt entfernt haben kann.

## Was gefärbt wird

**Eine Marke nennt nur das Herkunftswort, das warnt** (`feature_label(...,
compact=True)`, im Kern `measure_qualifier(..., compact=True)`): „eingepasst“,
„aus dem Schritt“, „Maß nicht bestimmt“. Das Wort einer direkt gemessenen oder
aus dem exakten Modell übernommenen Zahl steht im Objektbaum, im
Merkmalfenster und im Tooltip, nicht an jeder Marke — dreißigmal „gemessen“
verbreiterte die Kästen, bis die Platzierung Beschriftungen wegließ.

**Eine Bohrungsmarkierung verschließt die Öffnung nicht.** Ihre Innenwand wird
von beiden Öffnungen durchscheinend gezeichnet. Deckend liegt die Farbe der
fernen Wand aus schrägem Blick über dem ganzen Loch und sieht wie ein Deckel
aus, obwohl geometrisch keiner da ist; nur eine Seite zu zeichnen lässt die
Markierung im Gegenblick dagegen ganz verschwinden. Andere Merkmalsflächen
bleiben deckend und beidseitig sichtbar.

Umgebungsverdeckung und Kontaktschatten weichen, solange eine Analysekarte
läuft: beide dunkeln nach, und die Karte färbt nach Zahlen — der abgelesene
Wert wäre ein anderer als der gemeldete. Beide hängen deshalb an einer
Eigenschaft (`ambient_occlusion`, `contact_shadows`) und nicht am Zustand des
Renderers: offscreen gibt es keinen, und ein Test, der sich dort überspringt,
prüft nie etwas.

## Schatten und Licht

Der Kontaktschatten ist **selbst projiziert** und hängt an keinem
Schattenwurf des Renderers: VTKs `enable_shadows` verschattete ganze
Seitenflächen schwarz und ließ die Ränder der Platte auslaufen, und die eigene
Projektion hat den Rendererwechsel unverändert überstanden. Geworfen wird
schräg — senkrecht projiziert liegt der Schatten unter dem Körper und ist von
ihm verdeckt.

**Der Schatten folgt der Kamera, weil das Licht es tut.** Das Frontlicht des
Renderers hängt an der Kamera: ein Körper ist in jeder Ansicht von vorn beleuchtet. Eine
feste Weltrichtung für den Schatten passt deshalb zu *keinem* Blickwinkel —
sie stand hier, mit einer Begründung, die auf eine Standardansicht verwies, die
es so nicht gab. `shadow_direction` leitet sie aus der Kamerastellung ab,
`_redraw_shadows` zieht sie bei jedem Ansichtswechsel nach — am Ende jeder
Kamerageste (`on_end` des Navigators), nach jedem Schritt der 3D-Maus und
nach jeder Kameravorgabe, nicht an einem Ereignis des Renderers. (Bis zum
05.09.2026 hing dafür ein Beobachter an VTKs `EndInteractionEvent`, weil der
Orientierungswürfel am Interaktionsstil vorbei drehte; das Achsenkreuz des
eigenen Renderers ist Anzeige und kein Griff, `set_axes_marker`, und niemand
bewegt die Kamera mehr an der Ansicht vorbei.)

**Ein Schatten fällt auf die Fläche, auf der sein Körper steht.** Nicht immer
auf die Platte: `shadow_catchers` sucht zu jedem Körper die Flächen unter ihm
— die Druckplatte und jeden Körper, dessen Oberkante nicht höher liegt als
seine Unterkante. Ohne das löst sich der Schatten eines Turms auf einer 12 mm
hohen Grundplatte von ihm ab und taucht erst daneben auf. Beide Stücke werden
gezeichnet, und das ist kein Widerspruch: Licht, das an der Grundplatte
vorbeigeht, trifft die Druckplatte, und weil jedes Stück am Umriss seiner
Fläche geschnitten wird (`clip_polygon`, Sutherland-Hodgman), verdeckt die
Grundplatte genau den Teil, der sonst doppelt läge. Dasselbe Schneiden hält den
Schatten auf der Platte: außerhalb lag er auf blankem Hintergrund und
behauptete Boden, wo keiner ist. Die Plattenkante kommt aus `_bed_extent`,
gemerkt in `show_build_volume` — ohne gezeigten Bauraum gibt es nichts zu
schneiden. **Und sie gehört der Platte des Körpers**, nicht der ersten
(`_bed_outline_for`): seit die Betten nebeneinander stehen, liegt der Umriss
eines Körpers auf Platte 2 eine Bettbreite weiter, und am Umriss von Platte 1
geschnitten wäre sein Schatten restlos weg.

`_place_shadows` läuft über Körper, Hüllstücke **und** Auffangflächen, und die
innerste Schleife tat zweimal zu viel. Gemessen an
`1-24+scale+polebarn.3mf` — 89 Körper, 266 150 Dreiecke — kostete **eine**
Kamerageste 1843 ms im Qt-Hauptthread; §2.8 gibt ihr einen Lidschlag (Robert:
„nach jedem kameraverschieben hängt es erstmal").

Drei Änderungen, jede einzeln gemessen:

| | je Geste, echter Renderer |
|---|---|
| vorher | rund 1,9 s + 246 ms Zeichnen |
| ebene Hülle über GEOS statt Qhull (`geom.mesh.planar_outline`) | 440 ms |
| Umriss je Stück **einmal**, dann verschoben (`_shadow_base_of`) | |
| ein Aktor je Körper statt je Stück und Fläche (442 → 89) | **126 ms** + 87 ms |

Die zweite Zeile ist die, die man beim Lesen übersieht: **Eine tiefere
Auffangfläche verschiebt den Umriss, sie ändert ihn nicht.** `shadow_points`
versetzt jeden Punkt um `(z − ground)` mal der waagerechten Lichtrichtung; das
`ground` ist für alle Punkte dasselbe und fällt als gemeinsamer Summand
heraus. Die Ausnahme ist seine eigene Klammer (`maximum(…, 0)`) — ein Punkt
**unter** der Fläche wirft keinen Schatten nach vorn, und dort ist die
Projektion nicht mehr linear. Gerechnet wird der Umriss deshalb auf der
Unterkante des Stücks, wo die Klammer nie greift, und von dort nur nach unten
verschoben.

Die dritte hängt an einer Zusage, die man dabei nicht verlieren darf: Die
Aktoren bleiben **körperweise**, weil `_shadow_owners` sie beim Zug an einem
Körper mitschiebt (`_shift_shadow`). Alle Schatten in **einen** Aktor zu legen
wäre noch billiger und nähme dem Zug seine Vorschau.

Die Umrisse aller Stücke gehen in **einem** vektorisierten Aufruf
(`core.geom.mesh.planar_outlines`) durch shapely; `shadow_soups` ist eine
reine Funktion. Über `SHADOW_PROJECTION_ABOVE` (4 000 Hüllpunkten) wirft ein
`_ShadowWorker`, und bis er fertig ist, bleibt der Schatten des vorigen
Winkels stehen. Je Körper **ein** Aktor mit fester Kapazität, der nur neue
Punkte bekommt (`_show_shadow_soups`) — am Piratenschiff (17 Körper, 35 254
Hüllpunkte) 46,7 → 0,5 ms Hauptthread am Ende jeder Drehung. Die Hüllen
liegen in Körperkoordinaten; der Versatz der Ansicht (Platten, Explosion)
kommt beim Wurf dazu — vorher blieb der Schatten beim Auseinanderziehen
stehen. Und **jeder Zug zieht den Schatten mit**, der am Griff
(`_drag_shadow`) wie der freie am Körper (`continue_body_drag_at`).

**Was je Bild neu gerechnet wird, wird je Körper vorbereitet.** Der
Schattenumriss lief als Triangulierung über jeden Punkt des Anzeigenetzes: 129
ms bei zweiundachtzigtausend Dreiecken, je Körper und Szenenaufbau, im
Qt-Hauptthread. Die konvexe Hülle steht einmal (`shadow_hull_of`), ein
Ansichtswechsel projiziert nur noch daraus. Und sie bekommt einen Kostendeckel:
bei einer feinen Kugel liegt *jeder* Punkt auf der Hülle, und die Rechnung wäre
teurer als das, was sie ersetzt. Über `SHADOW_HULL_POINTS` genügt eine
Stichprobe — plus die äußersten Punkte in vierzehn Hauptrichtungen, sonst
verliert ein gescannter Halter seine Ecken.

### Zwei Werte hängen am Thema, und beide aus demselben Grund

Die Farben des Themas sind nicht die einzige Größe, die zwischen hell und
dunkel wechselt. **Beleuchtung und Deckkraft wirken auf verschieden hellem
Grund verschieden stark**, und wer sie als eine Zahl führt, hat sie für genau
ein Thema richtig eingestellt.

**Das Frontlicht** (`HEADLIGHT`): Der Renderer stellt fünf Lichter auf
(`LIGHT_KIT` in `gfx_renderer.py` — der Lichtsatz, den PyVista und VTK
aufstellten), und nur eines — das Frontlicht aus der Kamerarichtung — trifft
die zum Betrachter zeigenden Seitenwände; die vier Kameralichter stehen über
und hinter dem Teil. Der Körper
ist im hellen Thema 2,45-mal dunkler als im dunklen (`#78828e` gegen
`#b9c4d0`), Schattierung multipliziert, also sind auf ihm auch alle
Helligkeitsunterschiede 2,45-mal kleiner — 0,0155 gegen 0,0380 zwischen zwei
Außenwänden. Das ist kein Beleuchtungsfehler, sondern Multiplikation, und
deshalb hilft dort nur mehr Licht: 0,45 statt 0,25.

**Die Schattendeckkraft** (`SHADOW_OPACITY`): Derselbe Wert 0,18 ergab 1,44
Kontrast auf der hellen Plattenfläche und 1,05 auf der dunklen — das
Vierundfünfzigfache an Luminanzunterschied. Ein Schatten hat auf hellem Grund
viel weiter nach unten Platz. Im hellen Thema sind es deshalb 0,03; das ergibt
1,06 und damit genau die Lautstärke des dunklen Themas („der Schatten wie im
dunklen Thema reicht", Robert, 30.08.2026).

**Zwei Wege, die vorher gemessen und verworfen wurden**, damit sie niemand
erneut geht: Ein ambienter Anteil am Körper hebt alle Flächen gleich und macht
ihn dabei *flacher* (Wandunterschied 1,19 → 1,12, Abhebung von der Platte
8,41 → 5,75). Ein Glanzanteil ändert an den Wänden fast nichts und am Deckel
gar nichts.

**Und die Falle beim Bauen solcher Paare**: Eine themenabhängige Konstante
nützt nichts, solange die Zeichenstelle weiter die Konstante liest statt den
gemerkten Wert — und ein Test, der nur die Methode prüft, bleibt dabei grün.
Gemessen: Nimmt man den Ruf aus `set_theme` heraus, fällt kein Test.
`tests/test_viewport_decisions.py` hält deshalb je Paar **drei** Zusagen: die
Richtung der Werte, dass `set_theme` sie setzt, und dass das Zeichnen sie
liest.

## Was die Ansicht sich merkt

Der Fund kam aus dem Quelltext (3d-druck-85): Ohne Tiefenschälung mischt ein
Renderer halbdurchsichtige Flächen in der Reihenfolge, in der die Aktoren
angelegt wurden. Unter VTK war das zweimal gemessen nicht behebbar — Depth
Peeling meldete Erfolg und fuhr nie (`LastRenderingUsedDepthPeeling=0` bei
stimmenden Voraussetzungen), und `vtkDepthSortPolyData` sortiert nur
**innerhalb** eines Aktors; der Aufruf wurde deshalb nie eingebaut, denn ein
Aufruf, der nichts bewirkt, sieht in einem Jahr aus wie einer, der etwas
bewirkt (dieselbe Entscheidung wie bei Mica und `DWMWA_BORDER_COLOR` am
Fensterchrom). pygfx mischt Durchscheinendes gewichtet und
reihenfolgeunabhängig (`weighted_blend`) und sortiert je Bild selbst nach dem
Abstand zur Kamera — die Regel darunter bleibt dieselbe, und der Viewport
rechnet sie weiter über den Vertrag.

**Was trägt, ist die Ordnung der Aktoren selbst** (`_order_by_depth`): Sie
werden nach dem Abstand ihres Mittelpunkts zur Kamera neu eingehängt, der
fernste zuerst. Das ist der Maleralgorithmus auf Objektebene — richtig
für getrennte Körper, machtlos bei sich durchdringenden, und genau der
gemeldete Fall
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Drei Dinge daran sind tragend:

* **Sie hängt an `_draw`, nicht an ihren Anlässen.** Die Kamera ändert sich an
  einem Dutzend Stellen — `view_from`, Radzoom, Zugende, 3D-Maus,
  Skizzenkamera —, und wer sie dort einzeln nachzöge, vergäße eine. Der erste
  Anlauf tat genau das und war deshalb an `show_scene` gehängt: Dort steht die
  Kamera noch auf der alten Stellung, `view_from` kommt danach, und im Bild
  änderte sich nichts.
* **Sie merkt sich, wofür sie geordnet hat** (Kameralage und Körperliste).
  An der Zeichenstelle läuft sie sonst bei jedem Bild, auch mitten in einem
  Zug.
* **Umgehängt wird über den Vertrag** (`set_draw_order`), und der Renderer
  setzt die Reihenfolge um, ohne ein Element aufzugeben: Die Elemente
  bleiben, was sie sind — mit Namen, Sichtbarkeit und Matrix. Ein Weg über
  Entfernen und Neuanlegen verlöre all das. (pygfx sortiert Durchscheinendes
  je Bild selbst nach dem Abstand zur Kamera; sein `set_draw_order` legt
  keine eigene Reihenfolge darüber, weil die gemessen genau das aufhöbe.)

**Und der Hüllquader der Szene zählt nicht mit, was vorn liegt** (21.09.2026).
`_scene_bounds` (der Rahmen für *Alles zeigen* und den Tiefenbereich) nahm
bis dahin jedes sichtbare Geometrie-Element mit. Griff, Knöpfe, Marken und
die Maßtinte zeichnen aber ohne Tiefentest (`keep_in_front`), und die Tinte
sitzt auf einer Ebene mitten im Tiefenbereich: Sie weitete den Quader auf
ihre Ebene und den Tiefenbereich auf 42 statt 80 an der Lochplatte, und
*Alles zeigen* rahmte eine Ebene statt des Modells. `GfxItem.in_front` (aus
`keep_in_front` beim Anlegen) nimmt diese Elemente aus dem Quader heraus.

Ein Teil unter der Platte war **vollständig** unsichtbar: `culling = "back"`
wirft die Rückseite der Ebene weg, also sieht man **von unten** hindurch. Von
oben blieb sie undurchdringlich. `BED_SUNKEN_OPACITY` ist 0,45 — praktisch
alles, und dieselbe Zahl, die der Darstellungsmodus *Transparent* schon führt
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

**Und sie gilt nur, solange wirklich etwas darunter liegt** (`sunken_body`,
gefragt an der Szene und nicht am Bild). Das ist Roberts ausdrückliche
Fassung, und sie nimmt der Sache ihre einzige Abwägung: Die Fläche existiert,
damit der Kontaktschatten auf etwas fällt — über einer leeren Platte bleibt
sie deckend, und die Frage stellt sich gar nicht.

Drei Dinge hängen daran:

* **Nur die gefüllte Ebene** (`_bed_surfaces`, je Platte eine). Das Raster ist
  ohnehin ein Drahtgitter mit 0,35, der Bauraum sind Linien; verdeckt hat
  immer nur `bed_surface_<n>`.
* **Die Frage wird bei jeder Auswertung neu gestellt** (`_apply_bed_
  transparency` in `show_scene`). Die Platte steht schon, seit der Drucker
  gewählt wurde; ob etwas unter ihr liegt, ändert sich mit jedem Schritt.
* **Und sie zählt zur Tiefenordnung** (`sees_through`, `_order_by_depth`):
  Eine durchscheinende Fläche unter *allen* Körpern ist genau der Fall, den
  eine falsche Zeichenreihenfolge ruiniert — ohne sie wäre falsch dargestellt,
  was die Durchsicht zeigen soll (Hinweis 3d-druck-85).

**Ganz weg gibt es weiterhin**, und das ist etwas anderes: *Ansicht →
Druckplatte zeigen* (Strg+Umschalt+D) blendet Bett, Bauraum und Maßstab aus,
gemerkt über den Neustart. Für „das Teil einmal ganz allein sehen" ist das
direkter als Durchsichtigkeit.

## Mehrere Druckplatten

Jede Platte hat ihren eigenen Nullpunkt, und `arrange_bed` setzt Platte 2 an
denselben Ort wie Platte 1 — das ist richtig, denn beide werden einzeln
gedruckt. Ein Bett für alle zeigt davon das Falsche: zwei identische Sockel
lagen Punkt auf Punkt übereinander, und gemeldet wurde es als „bei Projekten
mit mehreren Platten sehe ich trotzdem nur eine".

* **Die erste Platte bleibt, wo sie ist.** Nach +X und nicht um die Mitte
  verteilt: Eine Szene mit einer Platte sieht danach Bild für Bild aus wie
  vorher, und wer eine zweite dazubekommt, sieht sie kommen statt die erste
  wegrutschen zu sehen.
* **Die Elemente tragen die Nummer im Namen.** Der Name ist die Adresse, unter
  der ein Test (`item_of`) und das Aufräumen ein Element finden — mit festen
  Namen wären vier Betten nicht auseinanderzuhalten, und unter PyVista, dessen
  `name=` Gleichnamiges ersetzte, blieb von vieren eines übrig.
* **Ein Klick muss zurückgerechnet werden** (`plate_at`, `_from_view`, ganz oben
  in `_on_picked`). Was der Nutzer trifft, liegt in der Ansicht; was eine
  Operation als Ort bekommt, muss in der Szene liegen. Ohne die Umkehrung setzte
  ein Klick auf Platte 2 die Bohrung eine Bettbreite daneben — und weil dort
  meistens nichts ist, hätte sie stumm nichts getan.

Der Versatz liegt mit dem Auseinanderziehen (§18.8) zusammen in
`_view_offset`, damit jede Zeichenstelle beides bekommt oder keines. **Maße und
Fangmarke gehen seit dem 03.09.2026 mit, die Schichtkonturen seit dem
12.09.2026** (RM-119): Sie lagen bei zwei Platten quer über dem falschen Teil —
gemessen am Brett auf Platte 2, das im Bild bei x 160 bis 360 steht, während
seine Kontur bei -100 bis 100 gezeichnet wurde. `set_layer` nimmt dafür den
Körper entgegen, dem die Schicht gehört; ohne ihn gibt es keinen Versatz, den
man zuordnen könnte.

**Die Schnittebene geht ausdrücklich nicht mit, und das ist eine Entscheidung**
(RM-119, 12.09.2026). Sie ist eine **Szenen**ebene: Bei zwei Platten liegen die
Körper in der Szene übereinander, eine Ebene bei x = 0 schneidet also beide in
ihrer Mitte, und im Bild stehen zwei aufgeschnittene Teile nebeneinander. Genau
das ist die Frage, für die ein Schnitt da ist — Wandstärke, Innenraum. Eine
Bildebene träfe immer nur eine Platte, und der Schieberweg müsste mit jeder
weiteren um eine Bettbreite wachsen; er kommt aus den Körpergrenzen
(`section_ranges`), also aus der Szene. Schnitt und Bedienung stimmen so
überein, und wer das ändert, ändert beides.

**Und das Schwierige daran ist nicht die Rechnung, sondern die Zuordnung.**
`view_point_of` braucht einen Körper, und in der Szene liegen die Platten
*übereinander* — `arrange_bed` setzt Platte 2 an denselben Nullpunkt. Ein Punkt
in Szenenkoordinaten gehört damit zu beiden, und `_object_at` kann die Frage
dort gar nicht beantworten. Beantwortbar ist sie **im Bild**, wo die Betten
nebeneinander stehen: `_object_at_view` prüft den Hüllquader **plus** Versatz
gegen einen Ansichtspunkt.

Gefragt wird deshalb beim **Klick** und nicht beim Zeichnen: Dort liegt der
Ansichtspunkt vor. Ein Maß merkt sich das Ergebnis je Punkt
(`Measurement.object_ids` — zwei Enden dürfen zu zwei Körpern gehören,
`object_id` daneben benennt das Maß als Ganzes und reicht nicht), die Vorschau
in `_snap_owner`. Ohne Kennung bleibt ein Punkt, wo er ist; ein Versatz, den
man nicht zuordnen kann, ist keiner.

## Eine Zahl in Bildpunkten ist ein Logikpunkt

Die Ansicht führt ein Dutzend Zahlen in Bildpunkten: Trefferflächen, Fangweiten,
Zugschwellen, gezeichnete Größen. **Sie alle stehen in Logikpunkten** — das ist
die Größe, die ein Mensch vor dem Bildschirm sieht, und die einzige, über die
sich reden lässt („der Griff ist achtunddreißig Bildpunkte lang").

Alles, womit sie verglichen werden, ist dagegen ein **Gerätepixel**: Der Zeiger
kommt so herein (der Qt-Adapter in `gfx_renderer` multipliziert
`event.position()` mit dem Geräteverhältnis), `world_to_display` antwortet so
(`view_size` ist die physische Größe), und der Pickpuffer liegt in derselben
Auflösung. Auf einem Bildschirm mit 100 Prozent Skalierung fällt beides
zusammen, und deshalb fällt der Fehler dort nicht auf.

**Umgerechnet wird an der Vergleichsstelle, mit dem Faktor der Ansicht** —
`Renderer.device_ratio()` am Vertrag, `Viewport._device_ratio()` und
`Viewport._device_pixels(logisch)` in der Ansicht. Die Gegenrichtung — jedes
Ereignis und jede Projektion in Logikpunkte zu übersetzen — wäre dieselbe
Rechnung an 119 statt an elf Stellen und stünde quer zum Vertrag („Bildpunkte
zählen wie Qt, in Gerätepixeln").

Gemessen am 14.09.2026, dieselbe Geste in Logikpunkten bei 100 und bei 200
Prozent:

| Konstante | gemessen über | bei 100 % | bei 200 % |
|---|---|---|---|
| `CLICK_SLACK` | den Navigator, Klick gegen Zug | 10,5 | **5,2** |
| `CURSOR_PIXELS` am Umriss | `_resting_role` über `grip_reach` | 10,5 | **5,2** |
| `CURSOR_PIXELS` als Marke | die gezeichnete Marke | 10,0 | **5,0** |
| `SNAP_MARK_PIXELS` | die Armlänge über `_pixels_per_mm_at` | 13,0 | **6,5** |
| `PULL_HANDLE_PIXELS` | die Grifflänge im Bild | 38,0 | **19,0** |
| `PULL_HIT_PIXELS` | `pull_handle_reach` neben der Spitze | 17,4 | **8,7** |
| `AXIS_LABEL_PIXELS` | den gezeichneten Buchstaben | 64,0 | **32,0** |

Die halben Punkte sind die Auflösung der Sonde (sie tastet in Zehnteln), die
17,4 beim Griff der Abstand zur **Strecke** und nicht zur Spitze. Gemessen
wird durch die Entscheidung des Prüflings: Eine Sonde, die die Vergleichszeile
nachbaut, meldet nach dem Fix dieselben Zahlen wie davor — sie misst dann sich
selbst.

Drei Zahlen waren schon vorher richtig und bleiben das Vorbild:
`MEASURE_SNAP_PIXELS`, `EDGE_REACH_PIXELS` und `PICK_SLACK_PIXELS`. Das
`SNAP_PIXELS` der Platzierung rechnete nur im Tiefenfang mit dem Verhältnis;
beim Bezugsklick (`_pick_reference`) fehlte es, und ebenso bei
`GIZMO_LEAST_PIXELS` (`_gizmo_scale_for`) — beide bei 200 Prozent halb so
groß, gefunden und behoben in der Durchsicht 0.5.0 (22.09.2026). Wer eine
neue Bildpunktzahl einführt, sucht jede Verwendung ab, nicht nur die, an die
er gedacht hat.

**Zwei Zahlen dürfen es ausdrücklich nicht** — `SNAP_DOT_PIXELS` und
`SKETCH_POINT_PIXELS`. Sie gehen als Punktgröße an den Renderer, und pygfx
rechnet Punktgrößen und Linienbreiten **selbst** von logischen Bildpunkten in
Gerätepixel um (`l2p` in seinem Shader). Wer sie hier multiplizierte,
verdoppelte sie bei 200 Prozent. Dieselbe Grenze gilt für jede `width=` und
jede `size=` am Vertrag.

**`is_click` bleibt eine reine Rechnung.** Der Faktor kommt als Argument vom
`Navigator`, der den Renderer kennt; eine Qt-Frage in der Funktion machte sie
ohne Bildschirm unprüfbar. Der Langlochgriff (`slot_handle.py`) vergleicht
gegen dieselbe Konstante und rechnet genauso um.

## Der Mauszeiger

* **Silhouette schlägt Bildidee.** Bei 32 Punkten wird ein Zeiger nicht
  gelesen. Der Schnittzeiger trug zuerst denselben Körper wie das Symbol der
  Werkzeugzeile und war ein Fleck mit Strich; erst die grobe Form — Linie,
  darüber und darunter eine Hälfte — erzählt etwas. **Angesehen wird auf vier
  Untergründen**: Viewport dunkel, Akzent (ein gewählter Körper!), Körpergrau,
  helles Thema. (Der Schnittzeiger selbst ist seit dem 30.08.2026 wieder
  ausgebaut — er war fertig gezeichnet und wurde nie gesetzt, denn der
  Schnitt hat keine Klickgeste: seine Ebene wird an der Leiste gezogen. Die
  Lehre über die Silhouette bleibt; die Zeichnung war ihr Anlass.)
* **Eine gezeichnete Rolle braucht eine Setzstelle.** Der ausgebaute
  Schnittzeiger ist der Beleg: gezeichnet, begründet, nie gesetzt — der
  Kunde sah ihn nie, und niemand merkte es. `tests/test_cursors.py` hält
  seither beide Richtungen: Jedes gesetzte Rollen-Literal ist bekannt
  (sonst fällt es still auf den Systempfeil — „moving" statt „move" stand
  an der häufigsten Zuggeste), und jede gezeichnete Rolle wird irgendwo
  gesetzt.

**Ein Maß in Millimetern gehört nicht an den Zeiger.** Der Pinselradius ist der
Fall, an dem das auffällt: Ein Zeiger hat feste Punktgröße und weiß nichts von
der Kamera — beim ersten Zoom behauptet er eine Größe, die er nicht mehr hat.
Was ein Weltmaß zeigt, gehört als Ring in die Szene.

* **Der Vertrag zählt Bildpunkte wie Qt** — von oben links, in Gerätepixeln.
  pygfx zählt in logischen Bildpunkten, und die Umrechnung mit dem
  Geräteverhältnis liegt **einmal** im Renderer, nicht an den Zeichenstellen.
  (VTK zählte Y von unten, und bis zum 05.09.2026 spiegelte `_note_pointer`
  selbst.) Wer die Umrechnung an einer Zeichenstelle wiederholt, rechnet
  doppelt, und das Hover-Picking sucht am falschen Ort — was bei einem
  Geräteverhältnis von 1,0 immer stimmt und deshalb lange nicht auffällt.

**Gesucht wird erst, wenn die Maus steht** (`HOVER_DELAY_MS`, einmaliger
Timer). Bei jeder Bewegung zu picken hieße, den Tiefenpuffer hunderte Male in
der Sekunde im Qt-Hauptthread zu lesen. Ein Zug an der Kamera stoppt die Suche
ganz — wer dreht, will nicht wissen, was unter dem Zeiger liegt.

## Wann gemalt wird

### Die Ansicht bestellt ihr Bild — und nichts über ihr malt vorzeitig

Robert: „es werden auch beim auswahlpanel oder dem panel von der bohrung in
dem viewport anderes bzw das im viewport an einer anderen stelle gezeigt
bevor die ansicht wieder passt". Bild für Bild aufgenommen, stimmte das
dreifach: Das Auswahlfenster stand nach jedem Bohrungsklick einmal gequetscht
da (Zeilen höher als ihr Platz, ohne Überschrift, 90–150 ms), die Karte
*Bohrung ändern* stand zuerst oben rechts neben dem Prüfbericht und sprang
dann neben die Bohrung, und ein Rollbalken schaltete sich an und brach alle
Texte neu um. Vier Sätze gegen Zwischenbilder:

* **`render()` bestellt, `render_now()` zeichnet sofort.** `force_draw` ist
  `repaint()`, und das malt das **ganze Fenster** auf der Stelle — auch
  Nachbarn, deren Layout noch aussteht. Am sichtbaren Fenster stellt
  `render()` das Bild in Qts Malrunde nach den Layouts. Sofort zeichnet nur,
  wer das Bild in derselben Runde braucht: das erste Bild einer Vorschau,
  weil die Freigabe von *Übernehmen* daran hängt (`differenceApplied`).
  Picks laufen über einen eigenen Durchgang und hängen am angezeigten Bild
  nicht.
* **Ein Widget über der Grafikfläche ein-, aus- oder nach vorn zu holen
  malt ebenfalls sofort.** `show`, `hide`, `setVisible`, `raise_` an einem
  Kind der Ansicht über der nativen wgpu-Fläche — das ist Qt, kein Aufruf
  von uns. Wer es tut, hat vorher alles umgestellt, was im selben Bild
  stehen soll: das Merkmalfenster auf „Messen" **vor** dem Start der
  Maßgruppe (`MainWindow._place_from_feature_panel`), die Layouts gelegt
  (`MainWindow._lay_out_now`), und eine Karte, deren Platz noch gerechnet
  wird, bleibt verborgen (`PlacementFlow._seat_waits`) — auch ihr `raise_`.
* **Ein neuer Inhalt legt seine Layouts sofort.** Die Höhe des
  Auswahlfensters pflanzt sich über vier Stufen fort (Merkmalfenster,
  Rollinhalt, Rollbereich, Knopfzeile), jede in einer eigenen
  Ereignisrunde, und die Malrunde kam dazwischen. `_lay_out_now` arbeitet
  die Anfragen am Ende jedes Aufbaus ab (`LAYOUT_HOPS`).
* **Ein `QScrollArea` fragt seinen Inhalt nur einmal.** Seine Wunschhöhe
  stammt vom ersten Fragen und bleibt stehen; die Operationsliste verlangte
  so an einer Bohrung weiter die 384 Punkte vom Aufbau, als alle Handlungen
  sichtbar waren, für drei Knöpfe von 81. Ein Rollbereich, dessen Inhalt
  wechselt, fragt ihn bei jeder Frage neu und meldet jeden Umbau nach oben
  (`selection_operations._ListScroller`).

**Gemessen wird an den Malereignissen, nicht an Bildschirmfotos.** Eine
Aufnahme des Fensters kostet bei 3413 Punkten Breite rund 50 ms und
verschiebt die Folge, die sie aufnehmen soll. Der Prüfstand zählt die
`Paint`-Ereignisse des Rollinhalts und prüft bei jedem, ob die Höhe schon zu
seinem Minimum und die Knopfzeile zu ihrer Wunschhöhe passt; der Stapel zeigt,
wer gemalt hat (`.claude/.state/rm-232-erster-klick-2026-09-25/scenario_malen.py`).
Vorher: je Bohrungsklick zwei bis sechs gequetschte Bilder; nachher keines.

### Nur was über der Grafikfläche liegt, hat ein eigenes Fenster

Die Grafikfläche ist ein natives Fenster (`present_method="screen"`). Ohne
`AA_DontCreateNativeWidgetSiblings` macht Qt daraufhin jede Ebene darüber
nativ **samt allen ihren Geschwistern**, und ein Elternteil, in das ein
natives Widget umzieht, zwingt jedes spätere Kind dazu. Gemessen am
Wabenhalter: 140 von 854 Widgets waren eigene Windows-Fenster, darunter die
ganze Andockleiste — das Merkmalfenster entstand als Kind des Hauptfensters,
wurde dort nativ und nahm das beim Umzug mit. Ein Bohrungsklick legte 30
Fenster an; jedes `setVisible` kostete 1,3 ms und malte sofort, neun Fenster
anlegen und zeigen 19 ms, löschen 13, verbergen 9, jedes `move` 1 ms
(Sonden unter `.claude/.state/rm-232-erster-klick-2026-09-25/`:
`scenario_nativ*.py`, `scenario_fensterkosten.py`).

* **Die Regel setzt die Ansicht vor ihrer Fläche** (`overlay.keep_widgets_alien`
  in `Viewport.__init__`), und nativ wird nur, was über der Fläche liegen muss:
  die direkten Kinder von `Viewport` und `OverlayHost`, beim Polieren
  (`overlay.hold_above_the_view`, in beider `childEvent`). Ihr Inhalt malt in
  ihr Fenster. Danach: 20 native Widgets im Stand, 29 mit gewählter Bohrung.
* **Ein Widget entsteht in seinem endgültigen Elternteil.** Wer es als Kind der
  Ansicht baut und dann in eine Karte hängt, gibt ihm beim Polieren ein
  eigenes Fenster, das es behält — und ein natives Kind macht seine Vorfahren
  nativ. So kamen Kantenmaße und das Feldkästchen der Maßgruppe zu je einem
  zweiten Fenster im ersten (`PlacementFlow._build_floating` baut die Halter
  vor den Feldern, `FeaturePanel.measure_fields(op, None)`).
* **Was über der Fläche schwebt, bleibt über den Fluss hinaus.** Jeder
  Merkmalklick baut einen neuen `PlacementFlow`; der Vorgänger legt seine
  schwebenden Widgets und die Maßtinte verborgen und ungebunden ab
  (`_park_floating`, Verbindungen in `_links`), der Nachfolger übernimmt sie
  (`_take_parked_floating`, `_wire_floating`). Höchstens ein Satz je Ansicht,
  unter ihrer Kennung und nicht in einem schwachen Wörterbuch: Der Satz hält
  die Ansicht selbst fest, ein Schlüssel, den sein Wert hält, fiele nie weg.
  `destroyed` der Ansicht räumt den Eintrag.
* **Wer prüft, ob etwas verdeckt ist**, fährt `scenario_verdeckt.py`: jedes
  sichtbare Widget, das die Fläche schneidet und in eine Fläche darunter malt.
  Nach dem Umbau über acht Fensterzustände, Werkzeuge und Skizzenmodus: keines.

Gemessen am echten Fenster, abwechselnd mit derselben Fremdlast (`ab.sh`),
Bohrung zu Bohrung bis zur Fläche: Wabenhalter 200–208 → 127–128 ms, dichte
Platte 310 → 163 ms; unter schwerer Fremdlast bleibt das Verhältnis (452 →
261 ms). Ohne jedes native Überlagerungsfenster — unsichtbar, nur als
Untergrenze — wären es 100–103 ms.

**Nicht der Bildtakt.** rendercanvas nimmt ohne Angabe `max_fps=30`; am
Qt-Bildschirmweg wartet eine Bestellung trotzdem nur 2,5 ms im Median bis zum
Zeichnen (`scenario_bestellung.py`), und eine Kamerageste zeichnet mit 30 und
mit dem Takt des Bildschirms gleich oft (`scenario_zug.py`). Wer dort ansetzt,
misst vorher.

### Ein Zug zeichnet leichter, sein letztes Bild voll

Solange eine Taste gezogen wird, das Rad dreht, die 3D-Maus fährt oder eine
Flugtaste liegt, ist die Ansicht **in Bewegung** (`note_camera_motion`), und
die Umgebungsverdeckung zeichnet ihre leichte Stufe (vier Richtungen, zwei
Schritte, 3 × 3 Glättung). Das Loslassen beendet die Bewegung **vor** der
Geste, damit deren Bild schon voll ist; zeichnet sie keines, kommt genau eines
nach (`frame_was_reduced`). Rad, 3D-Maus und ein stillstehender Zug enden
nach `INTERACTION_SETTLE_MS` (180 ms), `settle_camera` sofort.
**`set_camera_pose` allein ist keine Bewegung** — so stellen
Bildschirmfotos und Handbuchbilder ihre Kamera, und die gehören voll
gezeichnet. Gemessen: Intel UHD 770 15,8 → 13,4 ms GPU je Bild (auf einer
RTX 4080 ohne messbaren Unterschied); zusammen mit dem Licht, das sich nicht
mehr je Bild dreht (`render/CLAUDE.md`), kostet eine Bewegung am
Platzierungsgriff 13,6 → 8,8 ms und ein Takt der 3D-Maus an 815 000
Dreiecken 16,7 → 8,7 ms.

## Aufbau und Leistung

Sieben von acht Szenenaufbauten waren unnötig — ein Klick auf einen Körper,
ein Themenwechsel, derselbe Wert noch einmal —, und an einem großen Modell
kostet jeder drei Viertel Sekunden. Sichtbar wurde es als Fehler: Jeder
Aufbau nimmt dem Actor seine Vorschau-Matrix, und nach einem Zug am Griff
sprang der Körper an die alte Stelle zurück, bevor er an der neuen landete
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

**`set_theme` konnte als Einziger nicht prüfen**, und der Grund war kein
Versäumnis am Vergleich, sondern ein fehlendes Feld: Der Viewport merkte
sein Thema nirgends. `self._theme` beginnt bei `None`, damit der erste Aufruf
durchläuft — das Fenster setzt das Thema beim Start, und ein
vorbelegtes Feld ließe die Startfarben ungesetzt. Seine Prüfung steht
**ganz vorn**, vor dem Umfärben der Leisten: Ändert sich das Thema
nicht, ist jede Zeile darunter Arbeit für dasselbe Bild.

**Der Test dafür misst nicht bei allen dasselbe.** `set_theme` steigt
offscreen vor `show_scene` aus (`if self.renderer is None`); ein Test über
den Aufbau-Zähler wäre dort grün, ohne etwas zu sagen. Geprüft
wird er deshalb an seiner Wirkung (den gesetzten Farben), die anderen sieben am
Zähler. Gegenprobe: jede der acht Prüfungen **einzeln** ausgebaut,
achtmal rot — ein Lauf mit allen acht Mutationen hätte beim ersten
abgebrochen und die übrigen sieben ungeprüft gelassen.

Das Fenster ruft `show_build_volume` bei **jeder** Auswertung — es weiß nicht,
ob sich am Bauraum etwas geändert hat, und die Ansicht wusste es auch nicht.
Vier Aktoren je Platte flogen weg und kamen identisch wieder: gemessen am
12.09.2026 am eigenen Renderer ohne Fenster **19,2 ms für ein Bett und 71,3 ms
für vier**, im Qt-Hauptthread. Danach sind es 2,1 und 2,5 ms, und das ist das
Anfordern des Bildes, nicht der Aufbau.

`_bed_built` merkt sich, woraus die stehende Kulisse gebaut wurde: **Renderer,
Bauraum, Plattenzahl und die beiden Bettfarben**. Jedes davon hat seinen Grund
— der Renderer, weil ein Austausch dieselben Aktoren woanders braucht; die
Farben, weil ein Themenwechsel sonst ein fast schwarzes Bett auf hellem Grund
stehen ließe.

Was **nicht** im Zustand steht, hängt an vorhandenen Aktoren und wird bei jedem
Aufruf gesetzt: Bettsichtbarkeit und Zeichenebene über `_apply_bed_visibility`,
die Deckkraft über `_apply_bed_transparency`. Vorher galt dort die Reihenfolge
(„frisch gebaut, dann ausblenden"); die gibt es nicht mehr, also gilt die Regel
in beide Richtungen.

`extract_feature_edges` war der teuerste einzelne Posten eines Szenenaufbaus
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Der Kommentar bei `FEATURE_EDGE_LIMIT` rechnet mit „dreißig Millisekunden
je Körper und Szenenaufbau". Die Rechnung stimmt; ihre **Annahme** stimmt
nicht — ein Szenenaufbau ist nicht selten. `show_scene` läuft bei
jeder Auswahl eines Körpers, jedem Themenwechsel und jedem Schritt der
Schieber für Explosion, Schnitt und Schicht.

**Genau dieselbe Fehleinschätzung stand schon einmal beim Schatten** und
ist dort behoben: `_shadow_hulls_for` nennt sie in eigenen Worten („sein
Docstring nannte das ‚einmal je Szenenaufbau' und meinte damit ‚selten' —
das stimmte nicht"). Die Kanten daneben blieben zwanzig Tage stehen. Der Cache
ist deshalb **dieselbe Bauart**: `_edge_meshes` neben `_shadow_splits`,
verglichen wird die **Identität** des Netzes und nicht sein Inhalt —
ein Hash über Millionen Dreiecke wäre nicht billiger als die Suche,
die er spart. Und der Schnittschieber trifft ihn aus demselben Grund
absichtlich nicht: `cut` erzeugt dort wirklich ein neues Netz.

**Was die Messung widerlegt hat**, und das gehört dazu: Die Vermutung war
`DISPLAY_DECIMATION_ABOVE` (500 000 Dreiecke, **je Körper**) — 32
Körper mit im Mittel 171 000 kommen zusammen auf fünfeinhalb
Millionen, von denen drei über der Schwelle liegen. Der Verdacht war
falsch: `_for_display` kostet beim ersten Aufbau 1044 ms und danach **0 ms**,
weil `DISPLAY_CACHE_KEPT` (4) für diese drei reicht. Wer die Schwelle
angefasst hätte, hätte nichts gewonnen.

**Und die Suche selbst zählt in Zahlen, nicht in Zeilen** (21.09.2026,
Leistung B10). `feature_edges` (`render/edges.py`) fand die geteilten Kanten
über `np.unique(edges, axis=0)` — einen Zeilenvergleich, der ein Feld von
Kantenpaaren sortiert: 333 ms bei 200 000 Dreiecken, im Qt-Hauptthread je
Auswertung. Jede Kante ist nach `edges.sort(axis=1)` ein Paar `(klein, groß)`
mit beiden Indizes unter der Eckenzahl `n`; als `klein·n + groß` wird sie
eine `int64`-Zahl, eindeutig (bei 1,3 Mio. Ecken ist `n²` rund 1,7·10¹², weit
unter der Grenze). Ein `argsort` über diese Zahlen ersetzt den Zeilenvergleich
(57 ms). `test_render_shapes.py::test_feature_edges_match_a_row_wise_reference_on_a_dense_mesh`
hält den Zahlenschlüssel gegen die langsame, offensichtlich richtige Rechnung
— eine falsche Kodierung (zu kleines `n`, Kollisionen) fiele dort auf. Die
`face_components` daneben (`_shadow_hulls_for`) bleiben Sache des Kerns.

Kanten, Schattenhüllen und Punktnormalen hängen am **Netz**, nicht an der
Szene. Ein neues Anzeigenetz über `SCENE_PREPARATION_ABOVE` (20 000
Dreiecken, zusammengezählt über die neuen) geht mit allem, was es braucht,
in den `_SceneMeshWorker` (`_MeshTask`: Kanten bis `FEATURE_EDGE_LIMIT`,
Hüllen in Körperkoordinaten, Normalen über `Renderer.surface_normals`);
darunter rechnet der Aufbau selbst, weil ein Arbeiter für ein paar
Millisekunden das Bild nur in die nächste Ereignisrunde schöbe. Bis der
Arbeiter fertig ist, bleibt die letzte gültige Ansicht stehen. Gemessen am
Baum mit 200 000 Dreiecken: 272–335 → 36–40 ms Hauptthread je Auswertung.

**Die Merker halten zwei Netze je Körper** (`_MeshMemo`, `MESH_MEMO_KEPT`):
Der historische Bohrschritt wechselt je Tastendruck zwischen dem Eingang vor
dem Schritt und dem Endergebnis, und mit einem Eintrag verdrängte jeder
Wechsel den anderen — an der Senkplatte 0,57 s bis zum Bild statt 33 ms. Eine
Generation, kein Wachstum: Das dritte Netz verdrängt das älteste.

**Ein Aufbau zeichnet ein Bild.** `select`, `_redraw_measurements` und die
Schatten laufen in `_apply_scene` mit `draw=False`;
`test_a_scene_build_draws_exactly_one_frame` hält es fest.

`_redraw_feature_patch` und `_redraw_hover_patch` merken sich, wofür sie
zuletzt gebaut haben (`_feature_patch_state`, `_hover_patch_drawn`), und
vergleichen Netze mit `_Same` — nach Identität, nicht über `id()`: Eine
freigegebene Auswertung kann an derselben Adresse wiedererstehen. Gebaut wird
mit geteilten Ecken (`_lifted_patch`, `_lifted_and_rim`), der Umriss durch
Zählen nach Ort (`edges.outline_edges`), und eine unbeleuchtete Fläche
rechnet keine Normalen. Gemessen an der Senkplatte (311 000 Dreiecke): Fläche
300 → 63 ms, Kette einer Senkbohrung 1 100 → 175 ms, Hover bei gewähltem
Merkmal 250–380 → 17–80 ms.

**An großen Körpern rechnet ein Arbeiter ohne Schloss, die Hohlraumfläche
bleibt am Original** (Durchsicht 0.5.1). Ab `MARKING_IN_WORKER_FROM` Dreiecken
entstehen Ecken, Normalen und Kontur in `_MarkingWorker` aus den schlichten
Feldern des Netzes; gemerkt werden die letzten `MARKING_MEMORY`. Die
Hohlraumfläche (`cavity_surface_indices`) dagegen **nicht** an der geteilten
Arbeiterkopie: Unter dem Schloss der Kopie warteten die Kernauskünfte des
Merkmalfensters — die Maße standen Sekunden später. Nur eine Kette ab
`CAVITY_IN_WORKER_FROM` Dreiecken rechnet im Arbeiter, an einer **eigenen**
Kopie aus `features.copy_with_answers`: Sie liest die Flächenfits des
Originals, statt sie neu einzupassen (ohne das: Laptop-Ständer 1 784 statt
74 ms, Senkplatte 858 statt 207 ms).

### Die Maßtinte hält ihre Elemente und tauscht nur Punkte

Die Maßtinte der Platzierung (`placement_flow._Dimensions`) zeichnet Striche,
Pfeile und Marken als Elemente **im** Renderer, seit sie kein maskiertes
Widget mehr ist (der Grund steht am Anfang von RM-198: die Fenstermaske riss
über Vulkan das Gerät). Sie liegt vor dem Material (`keep_in_front`), unter
Griff und Knöpfen (`DRAW_ORDER = -1`).

**Acht dauerhafte Elemente, nicht zehn neue je Aufbau.** Fünf Linien
(Unterlage, Striche, Zuordnungen, Umriss, das leuchtende Maß mit dem Fokus)
und drei Flächen (Markenrand,
Pfeile, Marken) entstehen einmal mit fester Kapazität; jeder Aufbau schreibt
nur neue Punkte hinein (`Item.update_points`, der Renderer tauscht die Zahlen
in den Puffern, ohne neue Geometrie). Bis zum 21.09.2026 räumte jeder Aufbau
zehn Elemente ab und legte zehn neue an — pygfx baut je neuem Element eine
Pipeline, und das kostete zwölf von zweiundzwanzig Millisekunden je
Kamerageste, Radraste und Tastendruck in einem Feld. Danach: `refresh` 0,66
statt 4,0 ms, `redraw` 7,7 statt 22 ms.

**Was die Ansicht abräumt, kommt im Renderer wieder** (RM-232, 27.09.2026).
Markierung, Kontur, Schwebefläche, Merkmalspunkte, Beschriftung, Verbinder und
Griffpfeile entstehen je Klick weiter über `add_*` und gehen über `remove`;
der Renderer gibt einem neuen Element gleicher Bauart die pygfx-Objekte eines
abgeräumten (Regel und Grenzen in `app/ui/render/CLAUDE.md`). Am Wabenhalter
kostete Bohrung zu Bohrung damit 79–85 statt 98–102 ms. Zwei Folgen für jeden
Aufrufer: **Ein abgeräumtes Element wird nicht mehr angefasst** — kommt es
wieder, hält der alte Griff eine leere Gruppe, und was man daran dreht,
geschieht nirgends. Und **wer ein Element umfärbt, umdeckt oder anders
pickbar stellt, nimmt es aus dem Vorrat** (`restyled`): Seine Materialien
entsprechen nicht mehr der Bauart, unter der ein anderer es bekäme.

### Der erste Pick kostet eine halbe Sekunde — und niemand soll ihn bezahlen

Gemessen am echten Fenster (10.09.2026, Filamenthalter mit 2812 Dreiecken):
`pick_surface` braucht beim **ersten** Aufruf rund 500 ms, jeder weitere zwei
bis vier. wgpu baut dabei seinen eigenen Renderdurchgang für die Kennungen
auf; die Zahl hängt deshalb kaum am Modell — auf der **leeren** Szene sind es
dieselben 420 ms.

Bezahlt hat das bisher die erste Geste, die pickt, und das ist fast jede: ein
Klick über `_world_at`, oder der Drehbeginn, weil `_aim_rotation` die
Bildmitte fragt. Für den Kunden sah es aus, als hänge das Programm einmal —
danach lief alles flüssig (Robert, 09.09.2026: „ein bisschen
performanceprobleme beim bewegen haben wir auch noch").

`_warm_the_picker` zieht den Pick deshalb vor, und zwar an zwei Bedingungen:

* **Über einen Timer**, nicht im Aufruf selbst. Sonst verschöbe sich die halbe
  Sekunde nur an eine andere Stelle desselben Ereignisses.
* **Am Anfang von `_apply_scene`**, vor dessen frühen Rückkehrpunkten — nicht
  am Ende. Der leere Aufbau kommt beim Programmstart, und dort ist die
  Wartezeit umsonst: Der Kunde sieht die Startfläche oder sucht eine Datei.
  Am Ende der Methode liefe es erst mit dem ersten Modell, also mitten im
  Öffnen.

Einmal je Renderer (`_picker_warm`); die Pipeline bleibt danach stehen, auch
über Szenenwechsel hinweg. Gemessen nach dem Umbau: die erste Geste kostet 46
statt 511 ms.

#### Und neue Körper bringen neue Pipelines mit

„Die Pipeline bleibt danach stehen" gilt für den Durchgang, nicht für die
Objekte darin. **Gemessen am echten Fenster** (`drilled_v6.p3d`, 990 Dreiecke,
Aufwärmen beim Start gelaufen): Der erste `pick_surface` nach dem Öffnen kostete
36, 189 und 739 ms in drei ruhigen Läufen und 577 bis 1327 ms in drei Läufen
unter Fremdlast; jeder weitere unter 8 ms. Die Spanne ist groß, weil der
Treiber Teile seiner Übersetzung wiederverwendet — keiner der sechs Läufe lag
in der Nähe eines warmen Picks. Bezahlt hat es wieder die erste Geste, und das
war genau der Fehler, gegen den das Aufwärmen gebaut wurde.

`_warm_again_for_new_geometry` am **Ende** von `_apply_scene` armiert
`_picker_warm` neu, sobald die Auswertung eine andere ist als die, für die die
Aktoren zuletzt gebaut wurden. Danach: 3,21, 3,33 und 3,36 ms.

**Nur bei neuer Geometrie**, und die Bedingung trägt: `show_scene` läuft auch
bei jedem Themenwechsel, jeder Auswahl und jedem Schritt der Schieber für
Explosion, Schnitt und Schicht. Dort stehen dieselben Netze, und ein Pick je
Schieberschritt wäre ein zusätzlicher Renderdurchgang je Schritt.

**Geprüft wird der Anschluss, nicht die Zeit** — offscreen gibt es keinen
echten Renderer, und ein Doppel ist immer schnell
(`tests/test_viewport_decisions.py::test_the_picker_is_warmed_up_before_the_first_gesture`
und `::test_new_geometry_warms_the_picker_again`).
Die Zahlen stehen im Prüfstand, nicht in der Suite.

**Die Schriftzeichen der Beschriftungen gehen denselben Weg**
(`_warm_the_glyphs`, Durchsicht 0.5.1): pygfx rendert jedes Zeichen beim
ersten Gebrauch, und der kam mit dem ersten Merkmalsklick (am Laptop-Ständer
rund 90 ms). `LABEL_GLYPHS` wird nach dem ersten Szenenaufbau im Leerlauf in
Stücken vorgebaut (`Renderer.warm_glyphs`); wer neue Zeichen in Beschriftungen
bringt, trägt sie dort ein.

### Der Adapter wird einmal gefragt, und nicht im Hauptthread

`factory.available()` fragt vor jedem Viewport nach einem wgpu-Adapter, weil
ein Renderer ohne Adapter nicht höflich stirbt, sondern mit dem Prozess. Die
Frage kostet — gemessen am 14.09.2026 auf Windows 11 mit einer RTX 4080 unter
Fremdlast aus vier Agenten, je Zeile der Median aus drei Prozessen:

| | Zeit |
|---|---|
| erste Adapterfrage im Prozess | **1071 ms** (0,76 bis 1,12 s) |
| jede weitere im selben Prozess | 269 bis 315 ms |
| `available()` heute, Hauptthread, gefolgt von `make_renderer` | 763 + 668 = **1431 ms** |
| dieselbe Frage nach einer Frage im Nebenthread | 376 ms |
| Nebenthread fragt, Hauptthread baut nur noch | 0 + **661 ms** |

Auf Roberts Maschine waren es 5 bis 7,8 s im guten Fall und unter Last
Minuten. Das Startbudget ist drei Sekunden (§31).

Drei Dinge folgen daraus, und alle drei stehen in `app/ui/render/factory.py`:

* **Die Antwort bleibt liegen.** Sie gilt für die Maschine, nicht für das
  Fenster; der Sprachwechsel baut einen zweiten Viewport, und der fragte
  bisher neu.
* **Gefragt wird nebenan.** `app.ui.app.main` startet `_AdapterProbe` an der
  Leine, bevor das Register geladen wird — die Zeit vergeht, während
  Einstellungen, Erscheinungsbild und Fenster entstehen. Der wgpu-Instanzzeiger
  ist prozessweit; gemessen baute und zeichnete der Renderer im Hauptthread
  unverändert, nachdem ein Nebenthread ihn aufgebaut hatte.
* **Und mit Frist.** `ADAPTER_TIMEOUT_SECONDS` (20 s, rund das
  Zweieinhalbfache des schlechtesten *guten* Falls) begrenzt das Warten auf
  eine **laufende** Frage. Danach meldet sich die Ansicht mit dem Satz ab, den
  sie für einen fehlenden Adapter ohnehin hat (§27) — sie nörgelt nicht, und
  sie hält das Fenster nicht minutenlang. Wo niemand vorgearbeitet hat (Suite,
  Kommandozeile), wird wie bisher gewartet: Ein Test, der wegen Maschinenlast
  überspringt, wäre schlechter als ein Test, der eine Sekunde braucht.

## Die Skizze ist Vordergrund, der Körper Zusammenhang

Während des Zeichnens bleibt der vorhandene Körper sichtbar, aber mit
`SKETCH_CONTEXT_OPACITY` deutlich leiser als die Arbeitsgeometrie. Die normale
Transparenz von 45 Prozent war im echten Handbuchbild lauter als die Skizze;
16 Prozent lassen Form und Lage erkennen, ohne eingeprägte Details mit dem
Umriss konkurrieren zu lassen. Kontaktschatten und orange Körperauswahl treten
in dieser Zeit ebenfalls zurück. Beim Verlassen stellt der gewählte
Darstellungsmodus seine Deckkraft wieder her.

`viewport.py` trägt einen guten Teil des Skizzenmodus, und **seine Regeln
stehen nicht hier**, sondern in `zeichenflaeche.md` — dort, wo der Rest des
Editors steht. Die Datei lädt mit `sketch_editor.py` und nicht mit dieser; wer
eines der folgenden Stücke anfasst, liest sie zusätzlich:

| Was | Wo die Regel steht |
|---|---|
| `sketch_grid`, `grid_step_for`, `pixels_per_mm`, `LEAST_VIEW_PIXELS` | Raster und Maßstab |
| `show_sketch_cursor`, `sketch_cursor`, `CURSOR_PIXELS` | die Fangmarke und ihre 6,9 ms |
| `set_sketching`, `_sketch_hit`, `sketch_screen_at` | wohin ein Klick fällt |
| `set_sketch_pull`, `pull_cage`, `pulled_height`, `polyline_distance` | der Ziehgriff der Querschau |
| `MEASURE_GAP`, `DragValueBar.anchor` | die Zahl am Zeiger |
| `apply_wheel_zoom`, `view_on_plane`, `cameraMoved` | Zoom und Schwenk auf einer Ebene |
| `place_sketch_cards`, `spread_sketch_cards`, `SKETCH_CARD_FONT_PIXELS` | keine Karte über einer anderen |

## Renderstart: Plattform und Wayland

**Ob der Renderer überhaupt starten darf, entscheidet die wirksame
Qt-Plattform.** Sie steht beim Aufbau der `QGuiApplication` fest. Ein später
gestartetes Werkzeug kann `QT_QPA_PLATFORM` aus der Umgebung entfernen, macht
aus einer laufenden Offscreen-Anwendung aber keine Windows- oder
XCB-Anwendung. Wer danach nur die Variable liest, baut ein natives
Renderfenster ohne passenden Qt-Kontext — mit VTK starb der Prozess so beim
nächsten Fensteraufbau in `render_window_interactor.initialize`, und ein
wgpu-Renderer ohne Grafikfläche stirbt nicht höflicher. Deshalb fragt
`viewport._available()` zuerst `QGuiApplication.platformName()`, nimmt die
Umgebungsvariable nur vor dem Anwendungsaufbau als Rückfall und fragt erst
danach `factory.available()` nach dem wgpu-Adapter.

**Und auf Wayland wird die Ansicht nicht gebaut.** Der wgpu-Fensterweg ist
nur unter X11 und Xwayland geprüft; den nativen Wayland-Betrieb von
rendercanvas hat noch niemand gefahren (Registerpunkt in `ROADMAP.md`). Die
Weiche ist älter als der Renderer: VTKs Qt-Anbindung übergab `winId()` als
X-Window, fand unter dem Wayland-Plugin kein Display und nahm den Prozess mit
(`std::bad_array_new_length` — Martin Donecker, CachyOS, 28.08.2026). Deshalb
wählt `app/ui/qt_platform.py` **vor** der `QGuiApplication` xcb, sobald ein
X11-Display da ist — Qt 6 nähme in einer Wayland-Sitzung sonst von sich aus
Wayland, auch neben Xwayland —, und `_available()` lehnt ab, was trotzdem als
Wayland ankommt; `unavailable_hint()` sagt dann, was fehlt. In einer
Wayland-Sitzung lautet die Wahl `xcb;wayland`, nicht `xcb`: Qt geht die Liste
durch, und das X11-Plugin braucht neun Bibliotheken vom System, die das
Linux-Paket nicht mitbringt (`libxcb-cursor0` fehlt auf einem Ubuntu-GNOME
regelmäßig). Mit `xcb` allein hieße das kein Start; mit Wayland dahinter
startet die Anwendung ohne 3D-Ansicht, und der Hinweis nennt die Bibliothek —
mit `DISPLAY` die Bibliothek, ohne `DISPLAY` Xwayland. Wer die Plattform vor dem Aufbau
liest oder setzt, geht über diese eine Funktion — die Werkzeuge in `tools/`,
die `QT_QPA_PLATFORM` entfernen, weil sie das echte Fenster wollen, bauen sie
nicht nach.

**Das Eingabemodul** (RM-062): PySide6 bringt `compose`, `ibus` und
`qtvirtualkeyboard`, kein Fcitx-Modul. Nennt die Umgebung Fcitx
(`QT_IM_MODULE`, `QT_IM_MODULES`, `XMODIFIERS`) oder nur `XMODIFIERS` IBus
(GNOME unter XWayland, sonst bliebe `compose`), nimmt
`qt_platform.prefer_an_input_method_qt_has` vor der Anwendung `ibus`; für
Fcitx außerhalb des Flatpak mit `IBUS_USE_PORTAL=1`, wo Fcitx5 das Portal
trägt. Weil ein `wayland` in `QT_IM_MODULE` unter X11 als keines zählt, wählt
die Anwendung das Eingabemodul nach der Plattform. Die Herleitung steht an
`input_method_environment`.

## Was nur das Bild zeigt

Die Regel ist keine neue, sondern die aus §35 an ein Widget gerichtet:
**Was man nicht angesehen hat, ist ungeprüft.** Ein Dialog wird deshalb einmal
gerendert und angesehen, bevor er als fertig gilt — vier Fehler kamen an einem
Tag durch eine grüne Suite und waren im gerenderten Fenster sofort zu sehen
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

**Und angesehen wird unter der echten Plattform.** Unter
`QT_QPA_PLATFORM=offscreen` hat Qt auf dieser Maschine null Schriftfamilien:
Jede Beschriftung wird ein leeres Kästchen, und **jede Breitenmessung ist
damit falsch** (Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).
Dieselbe Falle steht bei den erzeugten Bildern (`/erzeugen`) — sie gilt
für jede Messung an einem Widget, nicht nur für Bildschirmfotos.

Der Aufruf dafür ist drei Zeilen und braucht kein Fenster auf dem Schirm:

```text
app = QApplication([])
apply_style(app, "dark")
dialog = SupportDialog(kind=KIND_SURVEY)
dialog.show()
app.processEvents()
dialog.grab().save("bogen.png")
```

**Und wer ihn in mehreren Sprachen ansieht, installiert die Kataloge.**
`set_language` setzt eine Variable und sonst nichts; geladen wird über
`install_catalog(sprache, read_catalog(sprache))`, so wie `make_figures.py` es
tut. Ohne diese Zeile ist jedes Bild deutsch — und der Lauf sieht vollständig
aus, weil er sechs Dateien schreibt und sechs Zeilen ausgibt
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).
**Die Gegenprobe kostet nichts: Sind zwei Bilder gleich groß,
zeigen sie dasselbe.**

**Für den Viewport gilt genau diese Zeile nicht.** `widget.grab()` malt den
Qt-Widgetbaum ab und weiß nichts von dem, was der Renderer auf der
Grafikkarte in den Viewport gezeichnet hat — das Bild kommt mit einer
**schwarzen Mitte** zurück, und schlimmer als kein Bild ist eines, das eine
leere Ansicht behauptet. Was die Grafikkarte zeigt, holt nur der Bildschirm:

```text
window.show()  # wirklich zeigen, nicht offscreen
QApplication.primaryScreen().grabWindow(window.winId()).save("bild.png")
```

Vier weitere Dinge tragen einen solchen Prüfstand, alle vier am 24.08.2026
einmal gefehlt:

* **`bootstrap.load_operations()` vor dem ersten Registerzugriff**, sonst
  endet der erste Import in `unknown operation 'load'`.
* **Kein `QT_QPA_PLATFORM`.** Offscreen hat Qt hier null Schriftfamilien und
  die Ansicht baut keinen Renderer — beides ist genau das, was geprüft werden
  soll.
* **Die Schritte an einer `QTimer.singleShot`-Kette**, nicht in einer
  Warteschleife: die hängt bei sichtbarem Fenster. Und
  `faulthandler.dump_traceback_later`, damit ein Hänger sich meldet, statt zu
  schweigen. `window.start()` wird **nicht** gerufen — es öffnet beim ersten
  Start einen modalen Dialog, und der Prüfstand stünde.
* **`app.processEvents()` unmittelbar vor jedem Schuss.** `render()` zeichnet
  die Ansicht sofort, die Qt-Widgets malen erst im nächsten
  Ereignisdurchlauf: Ohne das zeigte ein Bild
  eine Skizze in der Szene und daneben „Leere Skizze" in der Statuszeile —
  zwei Zustände in einem Bild, und beide echt. Wer dem geglaubt hätte, hätte
  einen Fehler gesucht, den es nicht gibt.

Für eine Zeile, die nicht umbrechen kann — eine Skala, eine Knopfleiste —
lohnt daneben die Zahl: `sizeHint().width()` gegen `width()`, **in jeder
Sprache**. Was gequetscht wird, meldet Qt nicht.

#### Ein Widget, das nachgibt, darf nicht weniger verlangen

Eine Leiste, die bei Enge auf Symbole umschaltet, ist die richtige Antwort auf
zu wenig Platz — und sie schließt einen Kreis, wenn man sie naiv baut:

    eng → Symbole → schmaler → kleinere Wunschbreite → Container gibt weniger
        → immer noch „eng" → nie zurück

**Wer nachgibt, verlangt weiter das Volle.** `sizeHint()` meldet die Breite
**mit** Beschriftung, auch während Symbole stehen; die gemerkte Zahl entsteht
im breiten Zustand und wird im engen nur verglichen. Damit bekommt die Leiste
den Platz, wo er da ist, und weicht nur, wo er wirklich fehlt
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Das ist dieselbe Lehre wie bei der Höhenverteilung der Karten
(`oberflaeche.md`, „Gerechnet wird nie mit den Höhen, die gerade gesetzt
wurden") — hier in der Breite und mit einem Zustand statt einer Zahl.

**Und zwei Nachbarn, beide am selben Tag bezahlt:**

* **`SizePolicy.Fixed` schützt nicht den Knopf, sondern lähmt die Leiste.** Es
  hebt deren Mindestbreite auf die Summe der Kinder (gemessen 1325 statt 708);
  ein enges Fenster quetscht dann trotzdem, und die Umschaltung kommt nie zum
  Zug. Was hilft, ist `layout.setSizeConstraint(SetNoConstraint)` — die Leiste
  darf schmaler werden als ihre Kinder wollen, und dann greift die Regel oben.
* **`SizePolicy.Ignored` ist keine abgeschwächte Form davon.** An den
  Zahlenfeldern gesetzt bekamen sie **null** Punkte und verschwanden ganz —
  schlimmer als die Quetschung, die es beheben sollte.

#### Ein Messwert, der zu glatt ist, ist selbst der Befund

Die Wörter sind verschieden lang — „Verschieben", „Move", „Mettre à l'échelle" —,
und eine identische Breite kann es nur geben, wenn **kein Wort mehr da ist**.
Die Zahl war das Symptom, nicht die Entwarnung
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

Die Frage davor kostet nichts: **Sollte dieser Wert sich unterscheiden?** Wo
Sprache, Schrift oder Inhalt eingehen und trotzdem dieselbe Zahl herauskommt,
ist ein Weg abgeschnitten, den niemand abgeschnitten hat. Verwandt mit der
Gegenprobe aus `oberflaeche.md`: „Sind zwei Bilder gleich groß, zeigen sie
dasselbe" — dort als Beweis benutzt, hier als Alarm.

Zahlen an Bildern werden **angesehen, nicht nur gerechnet**
(Vorfall: ROADMAP-ARCHIV.md, 04.09.2026).

**Ein Layout, das nur bei der geprüften Breite stimmt, ist ungeprüft.** Drei
Fehler wurden am selben Tag sichtbar, und alle drei erst, als das Handbuch die
Fenster bildschirmfüllend aufnahm statt in einem Kasten von 1180 Punkten: Der
Bausteinkatalog legte seine Gruppen ineinander, weil der Kachelmodus seine
Zeilen beim Einfügen rechnet und ein späteres `setSizeHint` nur speichert —
`doItemsLayout()` nach einer echten Änderung. Die zehn Bedingungsknöpfe der
Skizze blieben in zwei Zeilen à fünf, weil diese Aufteilung für den
Laptopschirm gedacht war und seither überall galt. Und das Raster der
Zeichenfläche war ein halber Millimeter fein, weil `MIN_GRID_PX` auf sieben
stand — ein Wert, der bei kleinem Fenster nie auffiel. Wer eine Ansicht ändert,
sieht sie bei **beiden** Enden an: der Mindestgröße und dem vollen Bildschirm.
