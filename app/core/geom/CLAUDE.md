# `app/core/geom/` — wo Geometrie entsteht

Die einzige Stelle, an der Geometrie entsteht oder sich ändert (Regel 2).
Gerechnet wird gegen `manifold3d` und `trimesh`.

`move_feature` versetzt eine eindeutig topologisch verbundene Senkbohrung
als ganzen Hohlraum: alle Abschnitte aus `perceive.relations.cavity_chain_at`
begrenzen gemeinsam den Werkzeugkörper, alle Kennungen und Mittelpunkte
reisen mit. Zwei äußere Randringe werden geschlossen; eine unvollständige
oder mehrdeutige Fläche bleibt abgelehnt.

`remove_feature` fragt bei einer solchen Kette über `ctx.ask`, ob alle
Abschnitte mitgehen, und hält die Antwort im Parameter `sections`
(`OpResult.answered`) fest — derselbe Weg, den `load` mit der Einheit geht.

**Beide Antworten gehen denselben Weg: erst geht der ganze Hohlraum zu, dann
wird frisch geschnitten, was bleiben soll.** Bei „ganzer Hohlraum" entfällt der
zweite Schritt, bei „nur das gewählte" schneidet `_cavity_tool` die übrigen
Abschnitte wieder aus dem vollen Material — für die Abschnitte weiter innen
zusätzlich durch den gefüllten hindurch, sonst verlören sie ihren Weg nach
außen. Den Füllkörper liefert `_cavity_plug`: aus den Flächen des Hohlraums,
wo sie einen geschlossenen Körper hergeben, sonst als **Stopfen**
(`_chain_plug`) — ein Zylinder über die ganze Kette, wie ihn der Absagetext
seit je empfiehlt. Ein Füllkörper, der die Kegelwand nachbildet, endet auf ihr,
und die Vereinigung lässt dort zwei Flächen nebeneinander stehen.

Ob der zweite Randring eines einzelnen Abschnitts ein Übergang oder sein Boden
ist, beantwortet `_stands_alone` an derselben Kette und nicht die Ringzahl:
Nach dem Verschließen der Bohrung bleiben es zwei Ringe, und die Senkung
gehört sich dann selbst. Größenänderungen bleiben einzelne
Abschnitte und melden die übrigen; bei mehrteiligen Ketten wird keine
unvollständige automatische Änderung einer einzelnen Senkung vorgeschlagen.

Die Regeln stehen in `.claude/rules/operationen.md`.

`repair()` übernimmt Verschweißen und Dreiecksbereinigung nur, wenn ein
geschlossener Eingang danach geschlossen bleibt. Andernfalls bleiben das
Netz und seine Materialzuweisungen erhalten; ein Befund nennt den ausgelassenen
Schritt. Die Zusicherung entspricht `ingest.loader.normalise`. Die einzelnen
Reparaturhilfen bleiben für ausdrücklich gesteuerte Reparaturketten verfügbar.

**Die Kantenwarnung misst am Hüllquader nur vor.** `over_the_edge_along`
meldet eine offene Flanke, wenn die Mündungsscheibe über die Hülle ragt — das
ist billig und für einen `Solid` der einzige Weg. Auf einer gekrümmten Fläche
trifft es aber immer zu: Der Scheitel liegt auf der Hülle, und die getroffene
Facette steht schräg. Wo ein Netz vorliegt, entscheidet deshalb
`_flank_is_open` nach: ein Kranz von Punkten auf dem Bohrungsumfang, an
mehreren Tiefen in beide Achsrichtungen; liegt er an einer davon vollständig
im Material, reißt dort nichts auf. Innen und außen trennt `mesh.on_surface`
über die Normale des nächsten Dreiecks — nicht `trimesh.contains` (führt durch
`rtree`) und nicht `ray_hit_distances` (Kantentreffer zählen mehrfach, die
Parität trägt nicht).

Merkmalswerkzeuge verwenden die gemessene Tiefe unabhängig vom Durchmesser.
`_tool_for` erhält bei Bohrungen den tatsächlichen Sehnenzug ihrer Wandflächen.
Füllkörper umschließen die äußersten Wandknoten auch bei fremder Tessellation;
an offenen Langlöchern begrenzt die Mündungsebene den Füllkörper (§21.1).
Nach einem Versatz entscheidet die Zielgeometrie über den Durchgang, auch bei
rein seitlicher Bewegung. Verlorener Durchgang erzeugt einen Befund und
korrigiert das Merkmal. Entfernte Kennungen bleiben in
`SceneObject.reserved_feature_ids` für spätere Kopien gesperrt (§21.2).

Materialslots werden nach einer Booleschen Operation anhand der erhaltenen
Eingangsflächen übertragen; eine gleiche Dreieckszahl beweist keine gleiche
Zuordnung. Rasterbudgets multiplizieren mit unbegrenzten Ganzzahlen.
`paint_slot.replace_filament` übernimmt eine ausdrücklich gewählte Spule
vollständig, auch unbekannte Materialwerte. Ohne dieses gespeicherte Flag
behält die Operation das historische Ergänzungsverhalten leerer Felder.
`clear_filament` entfernt eine Zuweisung am Körper oder an `at_features`;
das frühere einzelne `at_feature` bleibt lesbar. Die Dreiecke aller gewählten
Merkmale werden gemeinsam vor der Platzsuche betrachtet. Bei einer Teilmenge werden andere bisherige
Slot-0-Flächen mit ihrer unveränderten Definition auf einen freien Platz
verschoben. Ohne Platz bleibt der Körper unverändert und der Fehler nennt
die nötige größere Auswahl. Geometrie, Merkmale und exakte Hohlrauminformation
bleiben erhalten; ein neutrales Slot 0 besitzt keine Filamentdefinition.
Ein altes allein am Körper gespeichertes Material wird vor dem teilweisen
Färben oder Entfernen über `slots_for_object` in explizite Definitionen
übernommen. Vollständige Abwahl leert auch dieses alte Materialfeld.
Die Differenzansicht überspringt ausschließlich identische Netzarrays,
keine bloß gleichen Hüllquader und Volumina.

Eine mitgeführte exakte `MeshData.cavity` folgt in `transform.apply` derselben
Matrix wie der Körper. Änderungen der Topologie verwerfen die Auskunft,
solange ihre Gültigkeit nicht eigens hergestellt wird.
Reine Slotzuweisungen in `attributes.with_slot` und `paint.fill_feature`
erhalten den Innenraum unverändert; sie ändern keine Geometrie.

Die allgemeinen Booleschen Nutzerbefehle verwenden bei ausschließlich
exakten Eingängen `brep.edit.boolean` und erhalten deren Körperart. Sobald
ein Mesh beteiligt ist, gilt die Netz-Rückfallkette. Beide Wege prüfen leere
Ergebnisse und wirkungslose Änderungen, bevor sie einen Körper zurückgeben.

## Die Boolesche Rückfallkette (§17.2)

Sie ist das Muster, das dieses Gebiet prägt — kein Sonderfall, sondern der
Normalweg:

| Stufe | Was sie tut | Vermerk |
|---|---|---|
| 1 | direkt durch den Kern | `direct` |
| 2 | verschweißen, aufräumen, erneut | `welded` |
| 3 | die Eingangsgeometrie minimal stören | `jittered` |
| 4 | auf Voxeln rechnen, neu vernetzen | `voxel` |
| 5 | aufgeben — mit Befund und Weg nach vorn | — |

**Die Stufe, die es geschafft hat, wird in die Operation geschrieben.** So
rechnet dieselbe Datei gleich nach (§11.3), und der Bericht kann sagen, was
die Zahlen wert sind. Stufe 4 kostet Genauigkeit und läuft **nie
stillschweigend**. In Entwurfsqualität endet die Kette nach Stufe 2, damit das
Iterieren schnell bleibt (§31).

`tests/test_boolean.py` erzwingt jede Stufe einzeln.

Kanten- und Flächenoperationen reichen `ctx.quality` durch alle Teilschritte,
auch Werkzeugvereinigung, Eckanschlüsse und Wiederherstellung einer Rundung.
Kein innerer Booleschritt darf den Entwurf auf feine Qualität hochstufen.

Die drei nativen Netzstufen übergeben `Mesh64` an Manifold und lesen dessen
Status und Volumen vor der Rückvernetzung. Nullvolumen bei flächigem Kontakt
wird als leeres Netz weitergegeben; erst `allow_empty` entscheidet, ob das
eine zulässige Antwort ist. Für gedrehte und gekrümmte Kontaktflächen begrenzt
`gamma(8) * max|Koordinate| * Oberfläche` die native Float64-Rundung.
Dieses datenabhängige Band ist keine Drucktoleranz; echte dünne Schnitte
oberhalb der Rechenunsicherheit bleiben erhalten. Die Plausibilität verwendet
das orientierte Volumenintegral ohne
Schwerpunktdivision und lehnt offene oder umgestülpte Ergebnisse weiterhin ab.
Die native Eingangsgrenze fordert schreibbare C-Puffer; die Rückvernetzung
erzeugt eigene schreibbare Arrays, damit weitere Netzoperationen und
Abstandsmessungen dieselbe Ausgabe übernehmen können. `shared_volume`
verwendet denselben Kern und unterscheidet Kontakt von dünnem Schnittvolumen.

## Die Karte

**Grundlage**

`mesh.py` (die Mesh-Hülle um den Geometriekern, §9; `read_mesh` liest nur, was
trimesh zu einem Körper macht — kein 3MF, kein Dateiformatwissen darüber
hinaus, das liegt in `ingest/`) · `boolean.py` (die Kette
oben) · `repair.py` (Netze reparieren — und dort zwei Nachbarn, die man leicht
verwechselt: `remove_small_components` misst die **Fläche** gegen die größte
Komponente und wirft lose Fragmente, `remove_hollow_shells` misst das
**Volumen** gegen null und wirft Flächenpaare ohne Dicke; ein Bauteil von
einem halben Millimeter hat ein Volumen, eine Haut von hundert
Quadratmillimetern keines) · `attributes.py` (Materialslots durch
eine Operation hindurch behalten, §20) · `enclosure.py` (Konturverschachtelung
ohne `rtree`)

**Bewegen und Ausrichten**

`transform.py` · `ops.py` (Kategorie „Transformation") · `align.py` (Merkmale
in Flucht bringen)

**Körper erzeugen und formen**

`primitive_ops.py` (Quader, Zylinder, Kegel oder Kegelstumpf, Kugel und Ring;
Kegel und Ring dienen auch als verständliche Werkzeugkörper für Boolesche Ops)
· `blend.py` (weiches Verschmelzen) · `displace.py`
(Höhenfeld) · `lattice.py` (Gitterfüllung) · `texture_ops.py`
(Oberflächentexturen als echte Geometrie) · `sculpt.py` · `pose.py`
(Skelett und Stellung) · `sketch_solid.py` (einen Skizzenumriss zu einem Netz
aufziehen)

Die fünf analytischen Grundkörper entstehen lokal über
`primitive_local_tool()`. Operation und temporäre Oberflächenvorschau beziehen
damit denselben Körper auf denselben Ursprung. `x/y/z` verschieben diesen
Bezugspunkt; eine gesetzte `nx/ny/nz`-Richtung legt sein lokales +Z über
`sketch.planes.frame_of()` in den Raum. Der Nullvektor bewahrt die bisherige
aufrechte Lage. `angle` dreht ihn zusätzlich um seine eigene Hochachse —
`frame_of` legt die Querachse deterministisch, aber nicht wählbar fest, und
für einen Quader ist das der Unterschied. Der Name ist derselbe wie bei den
Bausteinen; das Register zählt ihn zu den Platzierungsfeldern
(`PART_PLACEMENT_PARAMS`), und damit gehen die Grundkörper denselben Weg durch
die Oberflächenplatzierung.

`sketch_solid.py` ist das Gegenstück zu `brep/profiles.extrude` für den Fall,
dass kein exakter Körper vorliegt — und dieser Fall ist der häufigste: Wer ein
heruntergeladenes STL öffnet, hat ein Netz. Bis zum 30.08.2026 endete das
Abtragen dort an einem Satz („besteht bereits aus festen Dreiecken"); seitdem
schneidet `sketch_pocket` über die Boolesche Kette auch in ein Netz. Was dabei
entsteht, ist wieder ein Netz — der Unterschied bleibt, die Absage nicht.

`sculpt.py` und `pose.py` sind **Sammelparameter-Ops**: viele Gesten, ein
Schritt. Das Ergebnis folgt vollständig aus den Parametern, was das Fenster
währenddessen zeigt, ist Vorschau. `tests/test_gesture_ops.py` prüft das über
das ganze Register.

**Wandungen**

`hollow.py` (Aushöhlen — mit den Entlüftungen, die es druckbar machen) ·
`lid.py` (ein Deckel für eine Öffnung)

**Druckvorbereitung**

`prepare.py` und `prepare_ops.py` (Bohrungen, Teilen, Anordnen, Kollisionen,
§18.6) · `autosplit.py` (schneiden, bis es auf die Platte passt; nach einer
billigen Naht-Vorauswahl entscheidet das interne Stützvolumen der fertig
verstifteten Hälften, §22.3) ·
`pins.py` (Passstifte; Auto Split wählt die Form aus Fügefläche und
Materialtiefe und hält den Kleberhinweis als Operationsparameter fest) ·
`orient.py`

**Die Nummer eines zerlegten Teils hängt an der Geometrie, nicht am Rauschen.**
`_loose_parts` ordnet nach Volumen — aber nach dem **gerundeten Verhältnis zum
größten Teil** (`_SAME_SIZE`), und bei Gleichstand entscheidet `_where_it_sits`,
die Mitte des Hüllquaders. Der Grund steht in beiden Docstrings: Zwei gleich
große Teile unterschieden sich in den letzten Stellen mit der Tessellierung,
und ihre Nummern tauschten bei manchen Größen. Die Kennung eines Objekts ist
der Anker für jeden späteren Schritt; ein Tausch nimmt ihm sein Ziel.

**Ein Langloch ist eine Bohrung mit zwei Bogenmittelpunkten.** Der Umriss
entsteht einmal (`prepare.slot_profile`) und wird von beiden Kernen aufgezogen
— vom Netz-Kern über `sketch_solid.extrude_profile`, vom exakten über
`brep.profiles.extrude`, wo die Enden echte Zylinderflächen bleiben.
`slot_travel` rechnet die Gesamtlänge des Dialogs in die Mittellinie um und
lehnt dabei die Aufweitung ab; `slot_ends` nennt die beiden Endpunkte, an
denen jede Prüfung fragen muss, die für eine runde Bohrung an der Mitte fragt.
`prepare.edge_findings` stellt diese Frage beim Setzen, Ziehen und
Verbreitern für beide Kerne und meldet eine offene Flanke höchstens einmal.
Der Weg dorthin hat zwei Eingänge: `drill_hole` setzt eines (`slotted`,
`slot_length`, `slot_angle`), `slot_hole` zieht eine **erkannte** Bohrung
nachträglich auseinander (`prepare.slot_bore`, exakt `brep.edit.slot_bore`).
Die Regel dazu steht in `.claude/rules/operationen.md`.

Auch beim nachträglichen Ziehen bleibt die Kombination mit einer Senkung
ausgeschlossen. `slot_hole` prüft vorher die topologische Hohlraumkette;
ein verbundener oder mehrdeutiger weiterer Abschnitt hält die Handlung an.
Eine gesonderte runde Aufweitung lässt sich nicht durch bloßes Ändern ihres
Durchmessers zu einer passenden Langlochsenkung machen.

**`slot_hole` und `resize_hole` nehmen dabei eine Stelle entgegen** (`x/y/z`,
**leer** heißt „lass es, wo es ist" — `_named_place` beantwortet das für beide,
und die Felder sind `optional`, weil die Null an einer Koordinate die Mitte des
Teils ist). Wer versetzt, schließt zuerst die
alte Stelle — am Netz über `_closed_at`, am exakten Körper über
`brep.edit.fill_bore` — und schneidet an der neuen. **Geschnitten und nicht
geändert**: `resize_bore` verglich dort die zwei Durchmesser, fand sie gleich
und gab den Körper unverändert zurück; gemessen am 10.09.2026 blieb das Loch
bei (−20 | −10) und der Befund sagte „Die Bohrung hat bereits diesen
Durchmesser". Zwei Dinge hängen daran und sind beide gemessen: Die Tiefe wird
**vor** dem Verschließen abgelesen (`feature.face_indices` zeigen danach auf
fremde Dreiecke), und die Zuordnung sucht das Merkmal an seiner **neuen** Mitte
— mit der alten meldete der Netz-Weg es als verloren und der exakte warf einen
Programmfehler.

Die geometrische Vorauswahl projiziert dieselben Normalenrichtungen in
begrenzten Gruppen auf Z. Vollständige Netzkopien entstehen erst für die
Platzierungsprüfung; eine begrenzte Bestenliste prüft sie in der vollständigen
Bewertungsreihenfolge, bis genügend passende Lagen vorliegen. Ungenutzte
Vertices zählen wie bei den Netzbounds nicht zur Höhe. Gleiche Flächensummen
behalten die lexikographische Reihenfolge ihrer Normalengruppen.

`core/build_area.py` ist der gemeinsame Druckbereichsvertrag: `printable_area`
liefert eine polygonale Fläche ohne feste Sperrzonen, `printable_height` die
freigegebene Höhe. Beide lesen `PrinterProfile`; ohne optionale Kontur gilt
das nominelle Rechteck aus `build_volume`. Alle Konturen verwenden XY relativ
zur nominellen Bettmitte, Z beginnt auf dem Bett. Ein `margin` gehört zum
Auftrag und verändert das Maschinenprofil nicht. `fits_on_bed` prüft die
aktuelle Lage; `placement_offset` sucht eine passende Verschiebung aufs Bett.
Bei Sperrzonen zählt die tatsächliche XY-Projektion statt nur der Hüllbox.

Anordnung, Bauraumprüfung und Orientierung verwenden diesen Vertrag. Die
Orientierung prüft auch eine Vierteldrehung in der Platte und erhält die
XY-Mitte, solange sie passt. `SearchResult.transform` trägt die vollständige
Bewegung zum Originalkörper, einschließlich B-Rep; die Grundrichtung allein
beschreibt die Platzierung nicht. Auto Split prüft jedes Endstück samt
Verbinderreserve gegen dieselbe Kontur. `oversize` liefert nur dimensionale
Überstände; `fits` entscheidet zusätzlich über die polygonale Fläche.
Eine Zwischenhälfte ohne passende Lage hat unbekannten Stützbedarf (`inf`),
kann aber weitere Schnitte benötigen. Andere Geometriefehler bleiben Fehler.

**Gepackt wird in der Ecke, gelegt wird in der Mitte.** `arrange_on_bed` sucht
jede Lage weiter an der hintersten, dann linkesten freien Stelle (§29) — das
Verfahren bleibt mitsamt seiner Abnahme. Erst danach schiebt `_into_the_middle`
jede Platte als Ganzes in die Mitte der freigegebenen Fläche, wie es jeder
Slicer daneben tut (`best_object_pos` steht dort auf `0.5x0.5`). Verschoben
wird je Achse nur, was hineinpasst, und nur wenn die Zielfläche wirklich frei
ist — die Prüfung gegen Sperrzonen läge sonst hinter der Verschiebung.
`occupied` nennt Körper, die liegen bleiben und ihren Platz belegen; eine
Platte mit solchen wird nicht zentriert.

**`orient_for_print` legt hin, was es umgeworfen hat.** Ein gedrehter Körper
braucht mehr Fläche als ein stehender und lief sonst in seinen Nachbarn
(Befund Robert, 09.09.2026). Der Parameter `arrange` ruft dieselbe Anordnung
mit denselben Werten für Abstand und Platten. **Über die Oberfläche bekommt sie
die ganze Szene** (`whole_scene`, wie *Auf dem Bett anordnen*), es bleibt also
niemand liegen und die Platte wird zentriert. Ein **gespeicherter** Auftrag
trägt dagegen seine damalige Teilmenge; dort gehen die übrigen als `occupied`
mit und die Zentrierung entfällt. Was der Abstand enthalten
muss — Plattenhaftung und Stützrand —, rechnet `export.writer.clearance_margin`,
und vorbelegt wird er in der Oberfläche (`MainWindow._spacing_for`), weil
Druckeinstellungen nicht zur Auswertung gehören.

Der Parameter `arrange` steht dabei auf `True`, auch für **gespeicherte**
Aufträge: Ein alter Stapel ordnet beim Öffnen mit und legt seine Körper
auseinander (Entscheidung Robert, 10.09.2026). Ohne Migration, weil die
Änderung die Lage berichtigt und keine Maße umdeutet — Bauplan §29 führt die
Begründung.

**Und weil sie an ihren Eingängen vorbei liest, sagt sie es dem Schlüssel.**
Der Registereintrag trägt `reads_other_bodies=True`; ohne das behielte ein
Ergebnis seine Gültigkeit, nachdem jemand einen nicht gewählten Körper
verschoben hat — der gedrehte wiche einem Nachbarn aus, der längst woanders
steht. Die Regel dazu steht in `.claude/rules/operationen.md` unter „Und die
vierte hängt an keinem Parameter".

**Ein Zug speichert einen Weg, gemeint war ein Platz.** `back_onto_bed` holt
zurück, was eine Bewegung von der Druckfläche geschoben hat, und die drei
Operationen, die ein Gizmo-Zug anlegt — `translate_object`, `rotate_object`,
`scale_object` — rufen es über den Parameter `keep_on_bed`. Erst wird
zurückgeschoben, den kürzesten Weg, den `placement_offset` ohnehin zuerst
prüft; steht dort ein Nachbar, sucht `arrange_on_bed` eine freie Stelle **auf
derselben Platte**. Ist dort nichts frei, bleibt der Körper liegen und
`check_build_volume` sagt es wie bisher — ein Plattenwechsel hinter dem Rücken
des Kunden wäre ein Teil, das er beim Drucken nicht wiederfindet.

**Die Vorgabe ist aus, und den Haken setzt der Zug** (`MainWindow.
_on_transform_dragged`, vier Stellen). Ein getippter Wert ist eine Ansage und
wird ausgeführt; ein Zug ist ein Zeigen. Der Unterschied ist gemessen: Das
Galerieteil `website/teile/gehaeuse.p3d` schiebt seinen Deckel um 135 mm und
graviert danach bei x = 135 — mit stiller Rückholung fiel „SOLIDON" in sieben
lose Buchstaben —, und ein Kranz, der bewusst über den Bauraum gelegt wird,
soll das melden statt zurückzurücken.

Drei Bedingungen tragen das Verhalten, und jede hat ihren Grund: Geprüft wird
der **Eingang** (wer schon daneben stand, ist geparkt und wird nicht
eingefangen), bewegt wird nur in **XY** (die Höhe hat *Auf das Bett setzen*,
und ein für einen Schnitt angehobener Körper darf nicht heruntergezogen
werden), und die **gemeldete Matrix** trägt Bewegung und Rückholung zusammen
— sonst zeigte die Vorschau dorthin, wohin die Zahlen weisen, und der Körper
läge woanders. Auch diese drei lesen die übrigen Körper, also tragen auch sie
`reads_other_bodies=True`.

**Kanten**

`faces.py` — die **Flächen** eines Netzes bearbeiten, Gegenstück zu `edges.py`:
*Fläche versetzen* und die *Formschräge*. Über der gewählten Fläche entsteht ein
Prisma ihres eigenen Umrisses — Boden und Deckel sind ihre Dreiecke, der Mantel
steht auf den Kanten, die nur zu einem von ihnen gehören. Ein Polygon wird dabei
nie gebildet; das trifft auch einen Umriss mit Loch. `_prism_from` nimmt einen
**Versatz je Knoten**: fest ergibt das gerade Prisma des Versetzens, mit der
Höhe wachsend den Keil der Formschräge.

Die neutrale Ebene der Formschräge liegt in beiden Kernen auf der unteren
Z-Grenze des Körpers. Ein reiner Höhenversatz ändert weder Abtrag noch Maße;
auch vollständig unter Z = 0 entstehen vollwertige Keile statt Nullvolumen.

`face_ops.py` — *Fläche versetzen* und *Formschräge anstellen* im Register,
kernübergreifend wie `edge_ops.py`. **Und `push_face` hat dabei seinen
Parameter gewechselt**: Es nahm eine Richtung und bewegte jede Fläche, die
dorthin zeigte — an einer Treppe alle Stufen zugleich (24000,0 statt 21000,0).
Gemeint ist die gewählte Fläche, und die benennt jetzt ein Merkmalsverweis; die
Richtungsfelder tragen nur noch gespeicherte Schritte (§16).

`edge_ops.py` — *Verrunden*, *Fase anbringen* und *Wulst anlegen* im Register, **kernübergreifend**:
Der Rumpf fragt `SceneObject.kind` und wählt danach den Rechenweg — `edit.fillet`
am exakten Körper, `edges.round_edges` am Netz. Sie standen bis zum 10.09.2026
in `brep/ops.py` mit `requires_kind="brep"`; wer ein STL einlas, fand sie
ausgegraut (Entscheidung Robert: „alles soll immer bearbeitbar sein"). Kein
Zwillingspaar (`MENU_TWINS`) — dort wählt der **Kunde**, hier der Körper, und
für ein Netz gibt es den exakten Weg gar nicht (§30).

`edges.py` — die Kanten eines Netzes als **Züge**, mit denselben Schlüsseln,
die der exakte Kern vergibt. Eine Bauteilkante besteht in einem feinen Netz
aus vielen Dreieckskanten; wer sie einzeln ausgäbe, zeigte vierzig Kanten, wo
der Kunde eine sieht. `edge_key` steht hier und wird von `brep.edit`
mitbenutzt: Dieselbe Kante bekommt aus beiden Kernen denselben Schlüssel,
sonst müsste alles darüber — Anklicken, Beschriftung, der Parameter
`edge_keys` — die zwei Rechenwege auseinanderhalten. **Die Auswahl selbst
steht hier ebenfalls**: `choose` und `wanted` beantworten „alle senkrechten"
für beide Kerne, `brep.edit` ruft sie. `MeshEdge.convex` sagt zusätzlich, ob
Material weggeht oder dazukommt; am exakten Körper weiß das die Topologie
selbst — und daran hängt beim Verrunden, ob abgezogen oder vereinigt wird.

Geschlossene Kantenzüge tragen im Schlüssel zusätzlich ihre Ausdehnung vom
Linienschwerpunkt, am Kreis also den Radius. Mitte und Richtung allein
unterscheiden die konzentrischen Ränder eines Rohrs nicht. Alte Schlüssel
bleiben als Alias lesbar, wenn genau eine Kante passt. Mehrere Treffer
halten zur Neuauswahl an; keine Reihenfolge entscheidet über die Geometrie.
Eine explizite Auswahl muss vollständig auflösbar sein. Fehlt nur eine der
genannten Kanten, hält der ganze Bearbeitungsschritt an; die noch vorhandenen
Kanten werden nicht als stillschweigende Teilauswahl behandelt.

`rounding_tool` baut den Werkzeugkörper: im Querschnitt der Zwickel zwischen
den zwei Flächen und dem Bogen, stückweise über den Zug gezogen. Wie fein der
Bogen wird, sagt `_arc_steps` — aus `units.MAX_FACET_SAG` und
`MAX_FACET_ANGLE`, denselben zwei Grenzen, mit denen OpenCASCADE tesselliert.
Eine feste Stückzahl wäre bei R = 30 zu grob und bei R = 0,5 Verschwendung.

Vollständig gewählte Eckknoten bekommen eigene Anschlussflächen. Der Knoten
stammt aus `MeshEdge.node_indices`, nicht aus gerundeten Ortskoordinaten.
Zwei zusammentreffende Kanten behalten den unmittelbaren Flankenschnitt.
Bei rein konvexen oder konkaven Knoten begrenzt der ursprüngliche
Normalenkegel den Kugelanschluss; ein Tetraeder aus den Berührpunkten
reicht dafür nicht. Mehr als drei Ebenen werden gemeinsam versetzt:
Gibt es mehrere Offsetzentren, verbindet sie die Minkowski-Summe des
versetzten lokalen Polyeders mit der Kugel. Die facettierte Kugel wird je
Operation einmal erzeugt und hält die Sehnenabweichung im Dreiecksinneren ein.

Fasen verbinden die tatsächlichen Schnittpunkte ihrer Flanken auf den
Nachbarflächen. Bei mehr als drei Flächen schließt deren ebene oder
facettierte konvexe Hülle die Ecke. Diese Mesh-Kappe kann von OpenCASCADEs
Splinekappe abweichen; Flankenabstände und Kontaktpunkte bleiben exakt.
Die Eckwerkzeuge werden gemeinsam mit den Kantenwerkzeugen geschnitten.

Der gemischte orthogonale Dreiflächenknoten verwendet einen örtlich
begrenzten Ebenen- oder Torusübergang, auch in der komplementären Innenform.
Seine drei Zylinder teilen die feinere Winkelunterteilung der Torusfläche;
beide Parameterrichtungen teilen sich die zulässige Sehnenabweichung.
Die Auswahl wird zuerst im Weltsystem aufgelöst. Die Rechnung erfolgt im
Rahmen des gemischten Knotens; nur das aus den Float64-Rechenschritten
abgeleitete Rauschen an seinen drei belegten Ebenen wird bereinigt.
Knoten-IDs und Materialslots bleiben beim Hin- und Rückweg erhalten.
Unabhängige Gruppen gewählter Züge rechnen nacheinander in ihren eigenen
Rahmen, auch auf demselben Körper. Gemeinsame ursprüngliche Knoten bestimmen
die Gruppen; ihre Reihenfolge folgt der ursprünglichen Auswahlliste.
Die Ausgangspunkte und Normalen bleiben maßgeblich: Nach einer Gruppe sind
deren Knotennummern keine Vertexindizes des neu vernetzten Zwischenkörpers.
Rechenstufen und Befunde aller Gruppen gehen ins gemeinsame Ergebnis ein.
Die fünf künstlichen Kontaktseiten des Ersatzkörpers überlappen den
Anschluss um `EPS_GEOM`; die echte Oberfläche und die Kurven bleiben stehen.
Die ursprünglichen Kontaktflanken der drei Kantenwerkzeuge verwenden
denselben numerischen Überlapp statt einer Zugabe zum Bauteilmaß.
Vor einem lokalen Materialersatz müssen die tatsächlichen Eingangsflächen
und das Volumen den drei ursprünglichen Ebenen entsprechen. Ein weiteres
Detail im Bereich hält mit einem Vorschlag für ein kleineres Maß an.
Alle Booleschen Vorbereitungen tragen ihre Rechenstufe und Befunde bis zum
Operationsergebnis weiter.

**Den Überstand an den Enden bekommt, was abgezogen wird — nicht, was außen
liegt.** Beim Verrunden fällt beides zusammen (außen abziehen, innen
vereinigen), beim Wegnehmen einer Rundung nicht: Dort wird außen *vereinigt*,
und ein Überstand klebt an, statt zu helfen.
An einem gemischten Eckanschluss enden die Kantenwerkzeuge genau am Knoten;
ein Überstand könnte auf dessen anderer Seite eine innere Fehlstelle schneiden.

`unround` und `reround` gehen den Weg zurück: `sharp_corner` rechnet aus einer
erkannten Rundung die Kante, die sie ersetzt hat — über den **Schnitt der zwei
Nachbarebenen** und nicht über den Radius, denn der stammt aus einem Sehnenzug
und ist ein wenig zu klein (2,9772 an einer Rundung von 3,0). Der Füllkörper
ist der Zwickel **ohne** Bogen; er deckt die Rundung ab, und seine Flanken
liegen in den Nachbarebenen, wo ohnehin Material ist.
Beim erneuten Verrunden geht das vollständige `MeshData` aus `unround` in
`round_edges` weiter. So können beide Booleschen Schritte die Materialslots
erhaltener Flächen übertragen; ein Neuaufbau allein aus `raw` verlöre sie.

`bead_edges` legt einen **Wulst** auf: ein Rundstab auf der Kante, je Stück ein
Zylinder und je Knick eine Kugel. Die Stücke gehen einzeln in die Kette —
zusammengelegt überlappen sie sich, und ein Körper mit doppelt belegtem Raum
hat kein Volumen (24250 statt 24186). **Die Kehlnaht im Innenwinkel ist nicht
die glatte Hohlkehle**: Die macht `round_edges` an einer konkaven Kante, und
der Unterschied ist der Faktor zwischen 104,45 mm³ und 28,97.

**Messen und Schneiden**

`measure.py` (§18.3 — Abstand, Wandstärke, Winkel, und der **Fang**: `visible_edges` und `corner_points` sagen, was im Bild überhaupt eine Kante oder eine Ecke ist, `snap` zieht den Klick darauf) · `section.py` (Ebene durch einen Körper, §18.2) ·
`difference.py` (was eine Änderung hinzugefügt und was sie entfernt hat —
**ab wann das eine Änderung ist, sagt der Drucker**:
`Profile.smallest_printable_volume`, dieselbe Grenze und dieselbe Begründung
wie bei `boolean.without_effect`. Die Szene bringt das Profil mit; ohne eines
bleibt es beim Vernetzungsrauschen, denn wer keinen Drucker kennt, soll keinen
erfinden — Regel 7, RM-097)

**Netz, Farbe, Text**

`mesh_ops.py` (Arbeit am Netz selbst) · `colour_ops.py` · `paint.py` (Flächen
in ein Filament färben) · `texture.py` (von einer Textur zu druckbaren Slots)
· `label_ops.py` (Text und Logos auf einer Fläche; die Schriften dazu liegen
in `data/fonts/`)

**Eine Beschriftung sieht überall gleich aus, oder sie ist keine.** Ein Projekt
wandert zwischen Rechnern, und eine Systemschrift, die es hier gibt und dort
nicht, macht daraus zwei verschiedene Teile. Angeboten wird deshalb nur, was
mitreist: DejaVu bringt matplotlib mit, Liberation, Comfortaa und Dancing
Script liegen in `data/fonts/` (SIL OFL, Lizenztexte unter
`knowledge/data/third_party_licenses/`, Zuordnung in `BUNDLED_FONT_LICENCES`).
`FONT_STYLES` holt fett und kursiv über `weight` und `style` aus denselben
Dateien, die ohnehin im Paket liegen.

**Nicht jede Familie hat alle vier.** Comfortaa und Dancing Script sind
*variable* Schriften — eine Datei mit einer Gewichtsachse, die matplotlib nicht
instanziieren kann. „Fett" liefert dort dieselben Umrisse, und der Riegel für
die Familie greift nicht, weil die ja da ist. `FONT_STYLES_AVAILABLE` sagt
deshalb je Familie, was es wirklich gibt, und `FONTS_WITH_ALL_STYLES` daneben
ist dieselbe Auskunft für den Dialog: Das Feld *Schnitt* hängt über
`depends_on` an der Schrift und graut aus, wo es nichts zu wählen gibt — statt
anzubieten und danach abzulehnen.

**Und was zu dünn zum Drucken ist, misst `stroke_width` am gesetzten Text.**
Doppelte Fläche durch Umfang über die Umrisse, die die Operation ohnehin baut;
`too_thin_to_print` rechnet daraus die Höhe, ab der es trägt. **Keine Tabelle je
Familie** — eine solche hing an einem Beispielwort, verschwieg den Schnitt (fett
ist rund anderthalbmal so breit) und wäre acht Zahlen gewesen, die niemand
nachmisst. Verglichen wird gegen `narrowest_bead`, die schmalste Bahn dieses
Druckers: `NARROW_LINE_SHARE` aus `slice/advise.py`, dieselbe Zahl wie beim
Wandvorschlag und nicht der Düsendurchmesser. Die Operation macht daraus einen
Befund mit der Zahl, keine Sperre: Wer nur ansehen oder exportieren will, darf
klein bleiben.

**Und matplotlib fällt still zurück.** Wer eine Schrift verlangt, die fehlt,
bekommt keine Ausnahme, sondern DejaVu Sans und eine Zeile auf der
Fehlerausgabe. `font_properties` prüft deshalb nach, welche **Familie** die
gefundene Datei führt (`get_font(...).family_name`), und sagt es (Regel 21) —
die zweite Hürde hinter der Spec, die den Ordner mitnimmt. Am Dateinamen
gemessen wäre der Riegel halb: „DejaVu" steht auch in `DejaVuSans.ttf`, wenn
„DejaVu Serif" gemeint war.

## Was eine Operation hier einhalten muss

1. Registereintrag in `registry/` — ohne ihn gibt es sie nicht
2. Umsetzung als `OpFn`; Boolesches über die Kette, benutzte Stufe in `solver`
3. Bei Zufall: Startwert aus `ctx.seed`, `deterministic=False`
4. **Beide Qualitätsstufen bedienen** (`ctx.quality`)
5. Befunde als `findings` zurückgeben, nicht selbst protokollieren
6. Geometrietest gegen den Korpus in `tests/data/`
7. Texte übersetzbar, alle fünf Kataloge ziehen nach

## Grenzen

- **Freie Platzierung verwendet den gemeinsamen `frame_of()`-Rahmen.**
  Bei `drill_hole`, `move_feature` und `duplicate_feature` bewahrt der
  Nullvektor die frühere Achsen- beziehungsweise Verschiebungssemantik.
  Die freie Bohrungsnormale zeigt vom Material weg; ihr Werkzeug verläuft
  ab der Mündung nach lokal -Z. `drill_tool()` erzeugt auch Aufweitung und
  Übergang als einen geschlossenen Rotationskörper. Die tatsächliche Op
  und ihre Vorschau verwenden das Material des Zielkörpers.
  Das Werkzeug reicht exakt von null bis zur negativen Eingabetiefe; ein
  Blindboden erhält keine Überlappungszugabe, auch nicht beim Mittenanker.
  Durchgangsaufrufer wählen ausdrücklich größere Höhen. An den bekannten
  lokalen Werkzeugenden bereinigt `drill()` ausschließlich Float64-Rauschen
  der Koordinatentransformation, je Vertex begrenzt durch die wirklichen
  Matrixterme. Echte Flächenabstände oberhalb dieser Rechengrenze bleiben
  erhalten; Materialtoleranz und globale Schweißtoleranz ändern sich nicht.
- **Merkmalswerkzeuge umfassen die belegte vollständige Form.**
  `feature_placement_geometry()` bestimmt den wirklichen Materialanschluss
  und schließt zusammenhängende Bohrketten gemeinsam. `x/y/z` bleiben die
  Zielmitte des gewählten Merkmals; ein lokaler Versatz verbindet sie mit der
  angeklickten Mündung oder Basis. Weitere Kettenglieder behalten beim
  Versetzen ihre Kennungen und bekommen beim Kopieren jeweils neue.
- **Textvorschauen verwenden echte Konturen.** `local_text_body()` wird von
  der Operation und der Platzierung verwendet; lokale Drehung und
  Überlappung entstehen nur einmal. Der Anzeigeaktor verändert keine
  gespeicherte Geometrie. **Jeder Parameter der Form reist mit** — auch der
  Schnitt: Er fehlte in `scene/placement.py`, und die Vorschau zeigte den
  normalen, während die Operation den fetten baute.

- **Millimeter, doppelte Genauigkeit.** Vergleich über `units.is_close()`,
  nie mit `==`.
- **Keine Zahlenkonstante für Toleranzen** — `auto:<material>` verweist ins
  Materialprofil (Regel 7).
- **Nie eine Eingabe verändern.** `OpResult.outputs` sind neue Objekte.
- **Der Sehnenzug wird benannt, nicht versteckt.** Eine Verrundung am Netz
  ist ein Vieleck; wie fein, entscheidet `units.MAX_FACET_SAG` — dieselbe
  Zahl, mit der der exakte Kern tesselliert. Wer eine echte Kurve braucht,
  arbeitet an einem `brep`-Körper weiter, und der `caveat` der Operation sagt
  das auch.

## Innenraum und verlustfreie Netze

`MeshData.cavity` ist eine optionale, geschlossene Schnittgeometrie des
tatsächlich ausgehöhlten Innenraums. Sie hat höchstens eine Ebene und reist
als eigene Vertex-/Flächentabellen im NPZ-Cache. `transform.apply` führt
dieselbe Matrix auf beiden Netzen aus; sonstige Geometrieänderungen verwerfen
die Auskunft, solange kein belegbarer Folgeraum berechnet wird.
`lattice_fill` beschneidet das Gitter auf diesen Raum. Ohne Auskunft sind nur
geschlossene, nach innen gerichtete Innenschalen eine eindeutige Grundlage.
Ein Hüllquader oder eine konvexe Hülle ersetzt keinen Innenraum.

Neuvernetzung überträgt Slots über `attributes.transfer`; Skulptur-Etappen
verwenden das verlustfreie NPZ statt STL. Beim Lesen aus Projektquellen werden
NPY-Header und entpackte Größe vor der Array-Allokation geprüft.
`measure.surface_gap` verwendet den räumlichen Index von Manifold mit
`Mesh64`; fehlende Körperübernahme ist keine Abstandsaussage.
