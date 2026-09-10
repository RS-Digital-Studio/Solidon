---
paths:
  - "app/core/geom/**/*.py"
  - "app/core/registry/**/*.py"
  - "app/core/scene/**/*.py"
---

# Regeln für Operationen

Eine Operation ist die einzige Stelle, an der Geometrie entsteht oder sich
ändert — auch nicht „kurz" im Viewport, auch nicht im Agenten (Regel 2).

**Eine Geste ist nicht dasselbe wie ein Schritt.** Eine Op darf beliebig viele
Nutzergesten sammeln, solange ihr Ergebnis vollständig aus ihren Parametern
folgt: Der Editor schreibt in einen Parameterwert, die Geometrie entsteht erst
bei der Auswertung, und was das Fenster währenddessen zeigt, ist eine Vorschau.
Die Skizze macht es so (§30.1), das Sculpting wird es so machen. Was dabei
einzuhalten ist, steht unten unter „Sammelparameter" und wird von
`tests/test_gesture_ops.py` über das ganze Register geprüft.

## Vollständig oder gar nicht

Keine Op ohne Registereintrag, Parameterschema, Geometrietest und übersetzte
Texte. Die acht Schritte stehen als Checkliste in `AGENTS.md`; `/neue-op`
führt sie durch. Der Registereintrag braucht `name`, `title`, `category`,
`params`, `reversible`, `consumes`/`produces`, `applies_to`, `deterministic`,
`doc`, optional `shortcut`.

`tests/test_registry_consistency.py` parametrisiert über das Register: eine
unvollständige Op fällt dort auf, ein doppeltes Kürzel auch.

**Was die Operation von ihrer Eingabe verlangt, steht im Register.** Eine Op
des exakten Kerns trägt `requires_kind="brep"`; das Menü graut sie bei einem
Netz aus und schreibt den Grund in den Tooltip, statt sie anzubieten und nach
dem ausgefüllten Dialog abzulehnen (Regel 19). Der gute Satz im Kern bleibt —
er ist die zweite Hürde, nicht die erste. Eine Aufzählung in der Oberfläche
wäre beim nächsten Zuwachs des exakten Kerns unvollständig.

**Und die zweite Hürde muss es wirklich geben.** `applies_to` war bis zum
03.09.2026 eine Zusage, die nur Menü und Merkmalspanel eingelöst haben; die
Auswertung selbst hat nie gefragt. Über Chat oder Kommandozeile lief damit
`resize_feature` auf einer **Bohrung** durch — am exakten Kern und an der
Materialkompensation vorbei — und `rotate_feature` auf einer **Kugelfläche**,
die keine Lage hat. Beide Male blieb der Körper wasserdicht, und nichts wurde
rot. Wer eine Op schreibt, die ein erkanntes Merkmal annimmt, prüft die Art
gegen den **eigenen** Registereintrag, nicht gegen eine Liste im Modul; den
Satz dazu liefert `perceive.actions.reason_against`, damit Panel und Kern
denselben sagen.

## Parameter

Jeder Parameter hat Titel, Vorgabe, Einheit, Grenzen und einen `doc`-Satz, der
sagt, was er bewirkt — nicht, wie er heißt. Vorderseite des Dialogs: die zwei
bis drei Werte, die man tatsächlich ändert. Alles Weitere hinter „Weitere
Einstellungen" (§2.4).

Toleranzen verweisen ins Materialprofil (`auto:<material>`), nie als Zahl.
Wo ein Projektparameter passt, steht keine Streuzahl.

### Sammelparameter (`kind` in `sketch`, `strokes`, `armature`)

Ein Editor sammelt darin, was er nicht in Zahlen fassen kann: eine Skizze als
JSON-Text (§30.1), eine Strichliste, ein Skelett. Fünf Eigenschaften machen
aus so einem Wert einen zulässigen Schritt statt eines Lochs in Regel 2 —
`tests/test_gesture_ops.py` prüft alle fünf über das Register: er geht in den
Op-Hash ein, er übersteht die runde Reise durch die Projektdatei, er ist
reiner Text, der Agent sieht ihn nicht, und er steht auf der Rückseite des
Dialogs.

Zwei davon sind leicht zu übersehen:

**Der Cache-Schlüssel muss die Parameter enthalten, die *in* einem
Sammelparameter gelesen werden.** Ein Maß in der Skizze darf ein Ausdruck sein,
ein Gelenkwinkel einer Stellung auch; ändert sich der Projektparameter
dahinter, ändert sich der **Text** nicht — die Auswertung gäbe das alte
Ergebnis zurück. `resolve_params` hilft dabei nicht: Sie sieht die **oberste**
Ebene eines Parametersatzes, und ein Sammelparameter steht dort als *ein* Wert.

`NESTED_REFERENCES` in `scene/evaluate.py` ordnet jedem betroffenen `kind`
seinen Sammler zu — `sketch` → `sketch_parameter_references()`, `armature` →
`pose_parameter_references()` —, und `_with_nested_context()` mischt die Werte
in den Schlüssel. **Eine Zuordnung und keine Bedingung**, weil genau das schon
einmal schiefging: `"sketch"` stand dort hart verdrahtet, die Pose kam später
dazu und wurde übersehen — obwohl vier Stellen zusagten, dass ein Gelenkwinkel
ein Projektparameter sein darf. Wer einen neuen Sammelparameter mit Ausdrücken
baut, trägt ihn hier ein; das ist eine Zeile und keine Suche.

`strokes` steht bewusst nicht drin: Ein Pinselstrich *ist* eine Koordinate,
kein Maß, das jemand an einen Parameter hängt.

**Und der Schlüssel muss die Träger kennen, von denen eine Operation an den
eigenen Eingängen vorbei liest.** `operation_hash` deckt die Hashes der
Eingänge — drei Lesarten greifen aber auf fremde Körper der Szene zu: das
Ziel von `align_to_feature` (`kind="feature"`), die `up_to`-Fläche
(`TARGET_FIELD`) und die `feature:<id>`-Ebene jeder Skizze
(`face_of_sketch`, dieselbe Funktion wie im Verweisfilter).
`_with_nested_context` mischt die Hashes **aller** Träger des benannten
Merkmals in den Schlüssel — alle, weil zwei Körper denselben Merkmalsnamen
tragen können. Ohne das behielt ein ausgerichteter Körper mit Cache die alte
Lage und eine `up_to`-Extrusion die alte Höhe, über das Schließen hinaus.
**Und die vierte hängt an keinem Parameter.** `orient_for_print` liest die
*übrigen* Körper der Szene — es dreht seine Eingänge und ordnet sie danach an,
ohne einen in einen fremden zu legen. Über die Oberfläche sind das alle
(`whole_scene`), ein **gespeicherter** Auftrag trägt aber die Teilmenge von
damals, und genau der liest an seinen Eingängen vorbei. Kein Feld benennt sie, also
findet sie keiner der drei Zweige oben. Sie ist am **Register** deklariert
(`OperationSpec.reads_other_bodies`), und `_with_nested_context` mischt dann
die Hashes **aller** Objekte unter `#scene` in den Schlüssel. Ohne das wich
ein gedrehter Körper einem Nachbarn aus, der längst woanders stand — mit
Cache-Treffer, über das Schließen hinaus.

Wer eine neue Lesart aus `ctx.scene` baut, trägt sie hier ein — dieselbe
Pflicht wie bei `NESTED_REFERENCES` darüber. Und die Frage davor lautet, ob
ein *Parameter* das Gelesene benennt: Wenn ja, gehört sie zu den drei oben;
wenn nein, ist sie eine Eigenschaft der Operation und gehört ins Register.

**Der Agent bekommt den Parameter nicht zu sehen.** Skizzen entstehen über
benannte Grundformen und Maße, nie über rohe Punktlisten (§26, Leitprinzip 5).
`json_schema()` lässt `kind="sketch"` deshalb ganz aus, und die Sitzung lehnt
ein trotzdem mitgeschicktes Argument ab. Zwei Ebenen, weil eine Lücke im
Schema noch kein Verbot ist.

## Boolesche Operationen

Die Rückfallkette (§17.2) hat fünf Stufen, und die erreichte Stufe gehört in
`solver`:

| Stufe | Verfahren | Vermerk |
|---|---|---|
| 1 | direkt | `direct` |
| 2 | verschweißen, Toleranz erhöhen, erneut | `welded` |
| 3 | minimale Störung der Eingangsgeometrie | `jittered` (+ Startwert) |
| 4 | voxelbasiert rechnen, zurück vernetzen | `voxel` |
| 5 | Abbruch mit Befund und Handlungsvorschlag | — |

Stufe 4 kostet Genauigkeit und wird im Prüfbericht ausgewiesen, nie
stillschweigend verwendet. In Entwurfsqualität endet die Kette nach Stufe 2.
Nach `voxel` ist die Materialslot-Zuweisung neu zu übertragen — die Vernetzung
wurde ersetzt (§20).

## Beide Qualitätsstufen

`ctx.quality` kennt Entwurf und Fein. Entwurf ist das, womit iteriert wird und
worin der Agent arbeitet; Fein gilt beim Export und im finalen Prüfbericht.
Eine Op, die beide gleich behandelt, sollte das bewusst tun.

## Befunde

Findings zurückgeben, nicht selbst protokollieren. Der Prüfbericht setzt sie
zusammen, der Agent liest sie über `read_report`.

**Eine Operation, die nichts bewirkt hat, sagt das.** Das steht unterhalb
dessen, was Regel 17 erfasst — dort geht es um Ausnahmen, und hier gab es
keine: im Verlauf ein Schritt, im Bild dasselbe Teil, und der Nutzer sucht den
Fehler in der Geometrie statt in der Position. `boolean.without_effect`
vergleicht die Volumina und verlangt dafür nur ein `volume` (`HasVolume`) —
`MeshData` und der exakte `Solid` bringen beide eines mit. Die Skizzen-Ops
rechnen im exakten Kern (§30.1) und kamen deshalb lange nicht daran: eine
Tasche neben dem Körper lief genauso stumm durch, wie es die Magnettasche
einmal tat. Gemessen wurde an vier Fällen — Oberkante unter dem Körper, Ort
daneben —, und in allen vieren sagte niemand etwas.

**Wer Boolesches rechnet, fragt danach — ohne Ausnahme.** Bohren, Stopfen, jeder
Baustein und die Skizzentasche taten es; `label_text` nicht, und darum kam
„BASIS" graviert auf einem Rahmen mit unverändertem Volumen und unveränderter
Dreieckszahl zurück, ohne eine Zeile im Prüfbericht. Eine neue Operation mit
`boolean(...)` ist erst fertig, wenn diese Frage darin steht.

**Und die Frage gilt nicht nur dem Booleschen.** Am 31.08.2026 hat sie
`sculpt_strokes` gefehlt, und dort war der Ausgang schlimmer als Schweigen: Die
Operation meldete „Die Züge dieser Sitzung wurden auf den Körper übertragen",
während kein einziger Eckpunkt sich bewegt hatte. Der Vorbehalt im eigenen
Registereintrag beschreibt genau diesen Fall — „Ein Strich sitzt an einer Stelle
im Raum, und wer die Form darunter ändert, verschiebt die Fläche unter ihm
weg" —, und geprüft wurde er nicht. Gemessen am Schaustück des vierten Wegs, das
im Bild ein glatter Kiesel war: drei Fingerrillen 18 mm über dem Körper in der
Luft, null Abtrag, zwei Schritte im Verlauf, kein Wort im Bericht.

**Wo „getroffen" nicht „gewirkt" heißt, wird die Wirkung gemessen und nicht der
Treffer.** Der vierte Zug desselben Schaustücks griff 321 von 5770 Eckpunkten
und trug dabei 0,41 mm ab, bei eingestellter Stärke 5,0 — formal ein Treffer,
im Druck nichts. `sculpt.no_effect` misst deshalb die größte Verschiebung
gegen `Profile.printer.layer_height`: Was unter einer Schichthöhe bleibt,
entsteht auch im Druck nicht. Daneben nennt `sculpt.strokes_missed` die Zahl
der Züge, die gar nichts erreicht haben — die beiden Aussagen sind verschieden,
und die zweite sagt dem Nutzer, wo er suchen muss.

**Und gefragt wird mit dem Profil.** Die Grenze ist nicht `EPS_GEOM`, sondern
`Profile.smallest_printable_volume` — ein Stück Extrusionsbahn von einer
Bahnbreite Länge. Ein Werkzeug, das den Körper knapp verfehlt, schneidet keine
Null: es nimmt den Span mit, den die beiden Hüllen gemeinsam haben. Eine
Bohrung Ø4,2 durch eine 14 mm dicke Platte, gesetzt in die Öffnung eines
Rahmens statt aufs Material, trug **0,002 mm³** ab statt 194 — mehr als das
Rechenepsilon und trotzdem nichts, was jemand je zu sehen bekommt. Ohne
`profile` bleibt es beim Epsilon: ein Aufrufer, der keinen Drucker kennt, soll
keinen erfinden (Regel 7).

**Was ein späterer Schritt behoben hat, warnt nicht mehr.** `SETTLED_BY`
(`scene/evaluate.py`) streicht einen Befund, sobald einer aus seiner Menge an
einem **späteren** Schritt und am **selben Körper** steht. Beides gehört zur
Bedingung: Ein Reparieren vor dem Einlesen des nächsten Modells hebt dessen
Befunde nicht auf, und zwei Modelle in einer Szene teilen sich den Bericht,
nicht ihre Löcher. Gestrichen und nicht herabgestuft — „Das Modell ist nicht
geschlossen" steht im Präsens und beschreibt einen Zustand, den es nicht mehr
gibt; als Hinweis wäre der Satz nicht milder, sondern falsch. Übrig bleibt der
Satz des Schritts, der es behoben hat, und der erzählt die ganze Geschichte.

## Eine grobe Vorauswahl darf nicht das Urteil sein

`over_the_edge_along` fragte den Hüllquader: Ragt die Mündungsscheibe hinaus,
hat die Bohrung eine offene Flanke. Der Docstring nannte die Näherung
ausdrücklich („gemessen am Hüllquader und nicht an der wirklichen Form") — und
genau deshalb hat zwei Monate niemand nachgesehen, was sie kostet: **jede**
Bohrung auf einen Zylinder, eine Kugel oder einen Ring bekam die Warnung, weil
der Scheitel einer gekrümmten Fläche auf der Hülle liegt und die getroffene
Facette schräg steht (gemessen 09.09.2026: Normale (0,9988 | 0,0491 | 0),
0,0785 mm Überstand). Der Körper war danach jedes Mal wasserdicht, einteilig
und richtig gebohrt.

**Eine Warnung, die im Normalfall kommt, ist keine Warnung mehr.** Sie ist der
Lärm, nach dem niemand mehr in den Prüfbericht sieht — und sie schickt den
Kunden an einen Rand, an dem nichts ist. Wo die grobe Frage anschlägt, wird
deshalb an der Sache nachgemessen; wo kein Netz vorliegt, bleibt es bei der
Näherung, und die ist dort zu streng und nie zu milde.

Die Frage davor, für jede Näherung im Haus: **Wie oft schlägt sie im Normalfall
an?** Eine Näherung, die nur Fehlalarme in einem seltenen Fall erzeugt, ist
richtig; eine, die den häufigsten Fall trifft, ist ein Fehler mit Docstring.

**Und der Test dazu muss den Weg des Kunden gehen.** Der erste Anlauf setzte
die Bohrachse von Hand auf (1, 0, 0) — ideal achsparallel, damit `extent = 0`,
und der Fall entsteht gar nicht. Er blieb ohne den Fix grün. Was ihn trägt,
ist die Normale aus dem echten Treffer (`original_surface_hit`), denn erst die
tesselierte Facette erzeugt den Überstand.

## Eine Zahl beschreibt die Regel, nicht die Lage

`_feature_body` lehnte einen Flächenausschnitt mit zwei Randringen ab, weil
zwei Ringe hießen: „dieses Merkmal geht in ein anderes über". Der Schluss war
richtig gemessen und galt für **eine** Lage. Nach dem Verschließen der Bohrung
unter einer Senkung bleiben es zwei Ringe — unten liegt jetzt aber Material
statt eines weiteren Hohlraums, und die Senkung war damit nicht mehr zu
löschen (Befund Robert, 09.09.2026; gemessen an `plate_countersunk.stl`:
zwei Ringe zu 48 Ecken vorher, zwei zu 65 und 48 danach).

**Gefragt wird an der Sache, nicht an ihrer Kennzahl.**
`perceive.relations.cavity_chain_state_at` beantwortet beides — ob das Merkmal
Abschnitt einer Kette ist und ob es einen fremden Rand berührt —, und erst
wenn beides verneint ist, gehört der Hohlraum ihm allein (`_stands_alone`).
`feature_placement_geometry` traf diese Unterscheidung seit je; sie fehlte
allein im Werkzeugbau.

Die allgemeine Form, weil sie über diesen Fall hinausgeht: **Wer aus einer
Zahl auf einen Sachverhalt schließt, schreibt dazu, unter welcher Bedingung
der Schluss gilt — und prüft die Bedingung, nicht die Zahl.**

## Ein Füllkörper hat die Form des Werkzeugs, nicht die des Hohlraums

Einen Hohlraum zu schließen heißt nicht, ihn nachzubauen. Ein Körper, der die
Kegelwand einer Senkung nachbildet, endet **auf** ihr, und die Vereinigung
lässt dort zwei Flächen nebeneinander stehen statt einer: Im Objektbaum standen
danach zwei Senkungen (Ø 10,34 und Ø 10,36), und der Oberseite fehlte weiterhin
das Stück, das der Trichter aus ihr geschnitten hatte (Robert, 10.09.2026).

Was trägt, ist die Bauart, die `_closed_at` für jede Bohrung geht: ein Körper,
der **überall breiter** ist als der Hohlraum, dessen Mantelfläche also im
vollen Material liegt, mit Zugabe an den Enden und danach an der Körpergrenze
gekappt. Übrig bleibt genau eine ebene Fläche.

**Und die Gegenrichtung dazu:** Was nach dem Füllen wieder ausgeschnitten wird,
ist exakt das Merkmal — dort ist jede Zugabe ein Maßfehler. Ein Durchgang mit
der üblichen Werkzeugzugabe war 0,02 mm weiter als die Bohrung darunter, und
der Baum zeigte danach zwei Bohrungen übereinander.

## Ein Vieleck aus einem gemessenen Durchmesser ist enger als er

`trimesh.creation.cylinder` baut ein **eingeschriebenes** Vieleck: Der
angegebene Durchmesser ist sein Umkreis, seine Flanken liegen um
`cos(π/sections)` weiter innen. Wer aus einem **gemessenen** Maß ein Werkzeug
baut, das dieses Maß wiederherstellen soll, rechnet den Unterschied dazu
(`_polygon_gain`) — sonst schrumpft die Bohrung bei jedem Zyklus: gemessen
7,9848 vor dem Zug, 7,9696 danach, also 0,015 mm je Durchgang.

Dass das nie auffiel, hat einen Grund, und der ist Zufall: Die Zugabe aus §39
(`FEATURE_OVERLAP`, 0,02 mm) hat bei den üblichen Durchmessern dieselbe
Größenordnung wie der Vieleckverlust und deckt ihn zu. Wer sie weglässt — weil
sein Werkzeug exakt sein muss —, verliert diese Deckung mit.

## Toleranzen sind Durchmessermaße

`clearance` und `press` aus dem Materialprofil gelten **im Durchmesser**, wie
überall im Haus: Ein Passstift bekommt seine Bohrung als `diameter + play`
(`knowledge/parts/mechanics.py`), und die Passungsprüfung rechnet
`hole_diameter - pin_diameter` (`scene/fits.py`). Wer eine Kontur radial
einzieht, nimmt die Hälfte.

Der Deckelkragen tat es nicht und bekam damit das doppelte Spiel — die Passung
des Beispiels „Dose mit Deckel" meldete bei jedem Öffnen 0,90 mm statt
0,25 mm. Daneben stand `COLLAR_RELIEF = 0.2`, „damit der Deckel nicht auf dem
Kragen sitzt": eine Zahlenkonstante für eine Toleranz, also ein Verstoß gegen
Regel 7 im Gewand einer Fertigungszugabe. Sie untergrub die Kalibrierung
(§28.3) — wer sein Material misst und 0,15 mm einträgt, bekam trotzdem 0,55 mm
je Seite. **Dass etwas nicht klemmt, ist die Aufgabe des Gleitspiels aus dem
Profil**; dafür ist es da, und dafür wird es gemessen.

## Ein Langloch trägt keine Aufweitung, und seine Länge ist nicht sein Weg

Zwei Entscheidungen zum Langloch, beide vom 10.09.2026, beide leicht in die
falsche Richtung zu drehen.

**Kein Langloch mit Senkung** (Entscheidung Robert). Eine Senkung über einem
Langloch wäre entweder rund — dann säße ein Schraubenkopf nur in dessen Mitte
versenkt — oder selbst ein Langloch, und dann bliebe offen, welche der beiden
Längen der Kunde meint. Solange die Frage nicht gestellt ist, wird sie nicht
geraten (Regel 21). Der Dialog graut die drei Aufweitungsfelder aus
(`depends_on=("slotted", (False,))`), `prepare_ops.bore_shape` legt sie für
Chat und Kommandozeile beiseite, und `prepare.slot_travel` weist sie ab, wenn
sie doch zusammen ankommen. Drei Ebenen für eine Entscheidung: Der Dialog ist
kein Vertrag, und der Kern ist keine Oberfläche.

**Und ein gesetzter Haken ohne Länge ist eine Absage, keine runde Bohrung.**
`slot_travel` liest die Null als „rund" — richtig für einen direkten Aufruf,
falsch für den Haken: Wer *Langloch* anhakt und die Länge stehen lässt, bekäme
ein rundes Loch und ein Häkchen, das das Gegenteil behauptet. Gefunden wurde
das am gebauten Dialog und nicht im Code; die Vorgabe der Länge steht deshalb
auf dem Doppelten des vorgegebenen Durchmessers, damit der erste Klick
durchgeht. **Ein Feld, das mit einer Absage begrüßt, ist keine Vorgabe.**

**Die Materialtoleranz weitet ein Langloch überall, auch an den Enden.**
Gerechnet wird deshalb `Mittellinie = Länge − nominaler Durchmesser`, und
die Zugabe liegt auf dem Radius. Wer stattdessen die *Gesamtlänge* festhielte,
nähme dem Kunden bei jedem Druck ein Stück Verschiebeweg ab — und der
Verschiebeweg ist der Grund, aus dem es Langlöcher gibt.

**Und was für eine runde Bohrung an ihrer Mitte gefragt wird, wird an einem
Langloch an beiden Enden gefragt** (`prepare.slot_ends`). Die Mitte steckt tief
im Material, während ein Ende schon über die Kante ragt; wer nur sie fragt,
schweigt zu einer aufgerissenen Flanke. Gemeldet wird trotzdem höchstens
einmal — zwei gleichlautende Sätze über dasselbe Loch sagen nichts Zweites.

**Der Winkel zählt gegen den Rahmen, den er bekommt — und die zwei Wege
bekommen verschiedene.** `drill_hole` baut ihn aus der Normalen der
angeklickten **Fläche**, `slot_hole` aus der Achse des erkannten Merkmals, und
die normiert die Erkennung auf „größte Komponente positiv". `frame_of` spiegelt
seine erste Achse mit der Normalen; gemessen an derselben Platte ergeben
45 Grad von oben gebohrt 45 Grad, von unten gebohrt 135, an der erkannten
Bohrung beide Male 45. **Das bleibt so**: Eine erkannte Bohrung hat zwei
Mündungen, und welche gemeint ist, hat niemand gesagt (Regel 21). Wer eine
Zahl von einem Weg auf den anderen überträgt, überträgt sie nicht.

**Und die Zugabe, die einen Werkzeugkörper vom gemessenen Maß fernhält, steht
einmal** — `prepare.FEATURE_OVERLAP`. Sie stand am 10.09.2026 zweimal da, mit
demselben Wert und dem Vermerk „dieselbe Zahl, derselbe Grund"; genau diese
Form hat `BOOLEAN_OVERLAP` schon einmal gekostet. Ihr Grund ist außerdem nicht
mehr die Koplanarität — die rechnet `manifold3d` robust, gemessen 27.08.2026 —,
sondern der **Tangentialkontakt**: Ein Langlochkörper ohne Zugabe legte sich
entlang zweier Linien an die alte Bohrungswand.

## Szene: Platzierung, Kennungen, Cache, Projektdatei

Bis zum 06.09.2026 standen diese Regeln in der Karte `app/core/scene/CLAUDE.md`;
eine Karte sagt, was wo liegt, eine Regel, was zu halten ist.

- **Oberflächenplatzierung verändert kein Dokument.** `prepare_surface()`
  bestimmt die zusammenhängende Originalfläche und ihre Randtopologie einmal;
  der Worker hält den unveränderlichen Kontext je Netz und Patch im Cache.
  `at_point()`, `point_with_distances()` und `point_with_centre()` verwenden
  dieselbe Flächenprüfung einschließlich Aussparungen. Zwei geradlinige
  Bezugskanten müssen unabhängig sein; Triangulationsdiagonalen und belegte
  Kreisfacetten liefern keine scheinbaren linearen Maße. Auf gekrümmten
  Flächen bleiben Punkt und Normale nutzbar, aber keine ebenen Abstände.
  Mittelpunkt-Offsets zeigen von der Bohrungsmitte zum Ziel entlang U/V.
- **Ein Sichtstrahl wird am Originalnetz geprüft.** `original_surface_hit()`
  ersetzt unbekannte LOD-Zellen durch Originaldreiecke und berücksichtigt alle
  Schnittebenen. Ihre positive Seite entfällt; künstliche Kappen sind kein
  Platzierungsziel. Ergebnisse und freie Normalen bleiben Float64-Werte.
- **Werkzeugvorschau und Operation teilen die Geometrie.** `prepare_tool()`
  liefert einen unveränderlichen `PlacementTool` mit lokalem Körper und
  ausgewähltem Merkmalsversatz. `surface_values(..., prepared_tool=...)`
  berechnet daraus neue Koordinaten ohne weiteren Körperbau; dieser Kontext
  gehört zu genau den gewählten Eingaben. `placement_tool()` bleibt der
  kompatible reine Mesh-Zugriff. Mündung oder Basis liegt bei null. Nur der
  temporäre Anzeigeaktor erhält den `frame_of()`-Rahmen am Treffer. Winkel,
  Einsenkung und Schnittspiegelung stecken bereits im Werkzeug. Bausteine
  deklarieren ihre Richtungsfelder über `normal_fields()`, damit gleichnamige
  Rezeptmaße erhalten bleiben. Beim Merkmalsversetzen ist `source` zusammen
  mit `feature` Pflicht; vollständige Bohrketten bilden ein Werkzeug.

- **Vergebene Merkmalskennungen bleiben reserviert.** Die Auswertung führt
  `SceneObject.reserved_feature_ids` über Zwischenoperationen fort und
  verhindert eine neue Zuordnung gelöschter Namen. Cache und Objekthash
  tragen die sortierte Sammlung; ein Projekt rekonstruiert sie aus den Ops.
- **Der Ergebniscache versioniert geometrische Auskünfte.** Alte Einträge
  ohne den aktuellen Formatstand sind Fehltreffer. Auch Änderungen erzeugter
  Geometrie und Merkmalsmetadaten gehören zu dieser Kompatibilitätsgrenze.
  Ein exakter mitgeführter
  Innenraum zählt zum Speicherbudget und zur Objektidentität.

- **Die Merkmalerkennung nimmt bis zu eine Million Dreiecke je Körper an.**
  `FEATURE_LIMIT_TRIANGLES` begrenzt die Auswertung; Importhinweise und
  Generator-Reduktion lesen dieselbe Grenze. Karten, Darstellung und die
  höchstens tausend zuzuordnenden Merkmale haben eigene Leistungsbudgets.
  Eine Anhebung wird an echten feinen Netzen einschließlich der oberen
  Gegenprobe gemessen; die Geometrie wird für die Erkennung nicht reduziert.
- **`OpContext.scene` ist nur lesend** (Regel 3). Ops erzeugen Objekte, sie
  ändern keine.
- **Reparieren und erneut versuchen ersetzt den angehaltenen Suffix atomar.**
  Die Reparatur steht vor dem fehlerhaften Schritt; dieser und alle jüngeren
  Schritte werden mit neuen Kennungen neu geplant. Alte Fassungen liegen in
  `DocumentChange.before.edited_ops`, ihre Entfernung in `after.edited_ops`.
  Reparatur und neue Fassungen gehören zu einer Transaktion, damit ein Undo
  exakt den alten Suffix zurückholt. Die gemeinsame Zielprüfung in
  `repair_targets()` verlangt lebende Eingänge und schließt Operationen des
  exakten Kerns aus: Eine Netzreparatur würde ihre bearbeitbaren Flächen in
  feste Dreiecke umwandeln und den erneuten Versuch unbrauchbar machen.
- **Objektzahländerung hält die Auswertung an** statt sie zu verschlucken.
- **Keine absoluten Pfade** in der Projektdatei (Regel 12), **kein
  ausführbarer Code** darin (Regel 13).
- Format geändert? Dann alle fünf Schritte: Version, Migration,
  Beispieldatei, Test, alte Migrationen behalten.

## Test

Kennzahlen gegen eine Datei aus `tests/data/`, nicht gegen ein selbst
erzeugtes Ergebnis. Bei Geometrie zuerst der Test, dann die Umsetzung. Ein
neues Fehlerbild wird eine Testdatei, kein Sonderfall im Code.
