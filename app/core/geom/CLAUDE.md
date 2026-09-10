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
oben) · `repair.py` (Netze reparieren) · `attributes.py` (Materialslots durch
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

**Ein Langloch ist eine Bohrung mit zwei Bogenmittelpunkten.** Der Umriss
entsteht einmal (`prepare.slot_profile`) und wird von beiden Kernen aufgezogen
— vom Netz-Kern über `sketch_solid.extrude_profile`, vom exakten über
`brep.profiles.extrude`, wo die Enden echte Zylinderflächen bleiben.
`slot_travel` rechnet die Gesamtlänge des Dialogs in die Mittellinie um und
lehnt dabei die Aufweitung ab; `slot_ends` nennt die beiden Endpunkte, an
denen jede Prüfung fragen muss, die für eine runde Bohrung an der Mitte fragt.
Der Weg dorthin hat zwei Eingänge: `drill_hole` setzt eines (`slotted`,
`slot_length`, `slot_angle`), `slot_hole` zieht eine **erkannte** Bohrung
nachträglich auseinander (`prepare.slot_bore`, exakt `brep.edit.slot_bore`).
Die Regel dazu steht in `.claude/rules/operationen.md`.

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

**Kanten**

`edges.py` — die Kanten eines Netzes als **Züge**, mit denselben Schlüsseln,
die der exakte Kern vergibt. Eine Bauteilkante besteht in einem feinen Netz
aus vielen Dreieckskanten; wer sie einzeln ausgäbe, zeigte vierzig Kanten, wo
der Kunde eine sieht. `edge_key` steht hier und wird von `brep.edit`
mitbenutzt: Dieselbe Kante bekommt aus beiden Kernen denselben Schlüssel,
sonst müsste alles darüber — Anklicken, Beschriftung, der Parameter
`edge_keys` — die zwei Rechenwege auseinanderhalten. `MeshEdge.convex` sagt
zusätzlich, ob Material weggeht oder dazukommt; am exakten Körper weiß das
die Topologie selbst.

**Messen und Schneiden**

`measure.py` (§18.3 — Abstand, Wandstärke, Winkel, und der **Fang**: `visible_edges` und `corner_points` sagen, was im Bild überhaupt eine Kante oder eine Ecke ist, `snap` zieht den Klick darauf) · `section.py` (Ebene durch einen Körper, §18.2) ·
`difference.py` (was eine Änderung hinzugefügt und was sie entfernt hat)

**Netz, Farbe, Text**

`mesh_ops.py` (Arbeit am Netz selbst) · `colour_ops.py` · `paint.py` (Flächen
in ein Filament färben) · `texture.py` (von einer Textur zu druckbaren Slots)
· `label_ops.py` (Text und Logos auf einer Fläche)

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
  gespeicherte Geometrie.

- **Millimeter, doppelte Genauigkeit.** Vergleich über `units.is_close()`,
  nie mit `==`.
- **Keine Zahlenkonstante für Toleranzen** — `auto:<material>` verweist ins
  Materialprofil (Regel 7).
- **Nie eine Eingabe verändern.** `OpResult.outputs` sind neue Objekte.
- **Verrundungen auf Mesh-Kanten vor dem B-Rep-Kern** werden ausdrücklich
  nicht gebaut. Dafür ist `brep/` da.

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
