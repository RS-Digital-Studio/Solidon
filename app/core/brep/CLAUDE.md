# `app/core/brep/` — der zweite Konstruktionskern

Boundary Representation über OpenCASCADE, **neben** dem Mesh-Kern, nicht an
seiner Stelle (§30).

## Eigentum an der nativen Form

`Solid` übernimmt beim Eintritt eine eigene Kopie von Topologie und Geometrie
ohne fremde Triangulation (`BRepBuilderAPI_Copy`, `copyGeom=True`,
`copyMesh=False`). Seine veröffentlichte `shape` sowie die Flächen-/Kanten-
Handles werden intern nur gelesen. Ein `frozen`-Dataclass allein schützt
keinen OCCT-Handle gegen native Mutationen.

Tessellation arbeitet auf einer weiteren privaten Arbeitsform. Sie schreibt
nie an die Shape eines Szene- oder Cache-Eintrags. Die Dreieckzuordnung läuft
über `ModifiedShape(original_face)` der Kopie und die ursprüngliche
Flächenkarte, nicht über eine angenommene gleiche Besuchsreihenfolge.
`brep_to_mesh` ruft diesen Weg direkt auf; ein zusätzlicher Qualitäts-Solid
wäre vor der Mesherkopie redundant.

Boolesche Operationen werden durch `kernel.boolean_builder` leer angelegt:
NonDestructive und gegebenenfalls Fuzzy-Toleranz stehen **vor** dem ersten
Build. Der Zwei-Shape-Konstruktor rechnet bereits und wird nicht benutzt.
Fillet, Chamfer, Shell, Draft, ShapeFix und Press/Pull erhalten private
Eingabeformen einschließlich der daraus gewählten Flächen/Kanten. Ein neuer
Ergebnis-Solid trennt anschließend auch die vom Builder geteilten Unterformen.

Exakte Bounds bleiben eine Float64-Antwort aus `AddOptimal` ohne Triangulation
und Formtoleranz; Zeichenwege sollen dafür keinen nativen Aufruf je Frame
auslösen. Ein Bounds-Cache ersetzt keinen Eigentumsvertrag.

Planare Merkmalsnormalen folgen der Orientierung der B-Rep-Fläche:
`TopAbs_REVERSED` kehrt die Trägerebenennormale um. Damit verwenden
Auswahlrahmen, Taschen und Ziehen dieselbe nach außen gerichtete Normale.

Die exakte Bohrung verwendet das Material des Zielkörpers über einen trägen
`knowledge.profiles.for_object`-Import. Freie Normalen, Aufweitungen und
Übergänge übernehmen das validierte Profil aus `geom.prepare.drill_outline`;
`edit.bore_profile` rotiert es analytisch. Mesh und B-Rep teilen damit Maße
und Mündungsbezug, ohne exakte Kreise zu tessellieren.

**Ein Langloch ist vier Flächen und ein Merkmal.** `features._slots_instead_of_half_bores`
setzt sie nach dem Beschreiben wieder zusammen — die einzige Ausnahme von „eine
Fläche, ein Merkmal" in dieser Datei, und dieselbe Aussage wie
`perceive.slots` am Netz. Erkannt wird topologisch: zwei angeschnittene
Zylinderflächen mit gleichem Radius und paralleler Achse, beide ins Loch
gewölbt, die sich **genau zwei** ebene Nachbarn teilen — und diese zwei Ebenen
grenzen an **beide** Bögen. Damit ist eine Tasche mit verrundeten Ecken keines:
Zwei benachbarte Ecken teilen eine Wand, nicht zwei. Die Toleranzen und die
Abgrenzung stehen in `.claude/rules/operationen.md`.

Offene Randbohrungen und Langlöcher ergänzt `features_of` über dieselbe
Wandprüfung wie der Mesh-Kern (§21.1). `edit.slot_bore` vereinigt nach dem
Schnitt koplanare Flanken, damit Nachziehen ohne neue Breitenzugabe das
Merkmal erhält. `edit.fill_bore` schließt den ganzen Langlochumriss und
begrenzt bei einer Randöffnung den Füllkörper an ihrer Außenwand.

**Ein Langloch wird nicht rotiert, sondern aufgezogen.** Der Umriss aus
`geom.prepare.slot_profile` wird über `profiles.extrude` zum Prisma, und zwar
**vom Boden zur Mündung**: `extrude` verlangt eine positive Höhe, und ein
Rahmen mit umgekehrter Normale wäre linkshändig — derselbe `slot_angle` drehte
darin in die andere Richtung als im Netz-Kern. Dieselbe Ebene, dieselbe Höhe,
nur ein anderer Ursprung. `_bore_span` in `ops.py` beantwortet Rahmen,
Werkzeuglänge und Mündungslage für beide Bauarten; `edit.slot_bore` zieht eine
bereits erkannte Bohrung nachträglich auseinander. Die Enden bleiben in beiden
Fällen echte Zylinderflächen — gemessen trifft der exakte Kern das analytische
Volumen auf die sechste Stelle, wo der Netz-Kern seine Bögen abtastet.

Der Mittelpunkt einer Bohrung oder eines Zapfens liegt **auf der Achse, in
der Mitte der V-Spanne** des Mantels — nicht im Flächenschwerpunkt, der bei
einem schräg beschnittenen Mantel radial und axial daneben liegt und den
Schneidzylinder von `edit.resize_bore` aus der Achse schob. Ob ein Loch
durchgeht (`through`), sagen die Nachbarflächen des Mantels: Reicht eine bis
an die Achse (Boden, Bohrerspitze, Kalotte), ist es ein Sackloch; der Abstand
wird gemessen, nicht geschnitten, weil eine Kegelspitze im Schnitt ein
entarteter Punkt ist.

Splines aus Skizzen übernehmen die kubischen Kontrollpunkte aus
`sketch.profile.spline_controls`; sie werden nicht neu interpoliert.
Der Draht erhält eine exakte Bézier-Kante je Stück, damit Flächen- und
Volumenintegrale auch an den inneren Kurvenknoten stimmen.

`thread_exact` benennt sein Außengewinde als erzeugtes `thread_1` mit den
unveränderten Werten für Durchmesser, Steigung und bewendelte Länge. Der
Mittelpunkt liegt bei halber Länge, die Achse zeigt in der Vorgabelage
nach +Z. Sie muss es nicht: Der Bolzen erbt seit dem 09.09.2026 dieselben
sieben Lagefelder wie Quader und Zylinder
(`geom.primitive_ops.PositionedPrimitiveParams`), und `placement_transform`
wirkt vor der Merkmalserkennung — das Gewinde wandert also mit. Ohne die
Felder bekäme er als einziger Erzeuger des Menüs *Erzeugen* keinen Griff
an seiner Vorschau. Das Merkmal
trägt die wirklichen Manteldreiecke; planare Anschnitte bleiben getrennte
Flächen. Es verwendet denselben Gewindevertrag wie die Bausteine, ohne die
exakten Operationswerte für die Anzeige zu runden.

## Eine Kante hat einen Schlüssel, keine Nummer

`edge_key` (RM-147 E4) beschreibt eine Kante über **Mittelpunkt und
Richtung**, gerundet auf ein Hundertstel beziehungsweise drei Stellen — die
Richtung ohne Vorzeichen, denn dieselbe Kante läuft je nach beschreibender
Fläche in beide Richtungen. Ein nativer Handle gehört dem Lauf, der ihn
erzeugt hat, und ein Index in `solid.edges()` verschiebt sich, sobald davor
etwas anderes passiert; beides in einer Projektdatei hieße, beim nächsten
Öffnen eine andere Kante zu verrunden. `named_edges` löst die Schlüssel wieder
auf, `fillet` und `chamfer` nehmen sie als `keys`, und die Auswahl `named`
sagt im Register, dass sie gelten. Eine Kante, die es nicht mehr gibt, ist ein
Satz an den Kunden — und ein anderer als „zu dieser Auswahl gehört keine
Kante".

`edge_points` gibt dieselbe Kante als **Punktfolge**, abgetastet nach
Abweichung (`DEFLECTION`, dieselbe Zahl wie die Tessellation). Mitte und
Richtung genügen für eine Auswahl nach Lage und nicht für einen Zeiger: Der
Schwerpunkt eines Bogens liegt neben ihm, beim Kreis einer Zylinderkante sogar
auf der Achse — also im Material. Eine Strecke kommt mit zwei Punkten zurück,
ein Kreis mit so vielen, wie die Abweichung verlangt. Die Ansicht projiziert
sie und misst im Bild (`ui/render/edges.nearest_polyline`).

## Ein Loch lässt sich hier auch wieder schließen (10.09.2026)

`fill_bore` ist das Gegenstück zum Bohren, `cut_bore` das zum Merkmal statt zur
Fläche: eine freie Achse, die **Mitte** als Bezug — dieselben zwei Zahlen, die
`resize_bore` liest. Beide bauen ihren Zylinder über `_centred_bore`; der
Unterschied ist ein `gain` auf den Radius, und der ist keine Feinheit: Beim
Füllen ist er nötig, weil der gemessene Durchmesser von einem Vieleck stammt
und dessen Flanken innerhalb des Umkreises liegen, beim Schneiden wäre er ein
Maßfehler. In der Länge bleiben beide exakt — die Mündungen liegen in ebenen
Flächen, die OpenCASCADE ohne Sehnenfehler tesselliert, und eine Zugabe dort
ließe beim Füllen einen Zapfen stehen, den am exakten Körper nichts wieder
abschneidet.

Damit ist die letzte Absage gefallen, die den exakten Kern vom Netz-Kern
trennte: Bis dahin lehnten `slot_hole` und `resize_hole` das Versetzen eines
Lochs mit einem Satz ab. Gemessen an einer exakten Platte 60 × 40 × 10, Bohrung
Ø 8 von (−20 | −10) nach (0 | 0): geschlossen, Volumen davor und danach
23497,345 — dieselbe Zahl. Das Langloch daneben nimmt 1467,57 mm³ weg, den
analytischen Wert auf fünf Stellen.

## Eine Rundung wegnehmen heißt, ihre Fläche zu streichen

`unround` gibt `BRepAlgoAPI_Defeaturing` die Rundungsfläche, und der Kern
verlängert die Nachbarn selbst. Gemessen an einem Quader mit vier Rundungen zu
R = 3: 23884,115 mm³ nach dem Wegnehmen einer, analytisch 23845,487 + 1,9314·20
— dieselbe Zahl auf vier Stellen, in 18 ms. `reround` ist das plus einer neuen
Verrundung an der zurückgekommenen Kante.

**Gesucht wird die Fläche über Radius und Lage**, und die Lage über den Abstand
zur **begrenzten Zylinderfläche** (`BRepExtrema_DistShapeShape`). Die unendliche
Achse unterscheidet keine getrennten Rundungen gleicher Achse und gleichen
Radius. `gp_Cylinder.Location()` hilft ebenso wenig: Die Parametrisierung
wählt irgendeinen Punkt auf der Achse, auch weit neben dem Merkmalsschwerpunkt.
Der Flächenabstand berücksichtigt dagegen die tatsächliche Ausdehnung und
bleibt von diesem Ursprung unabhängig. Der Radius filtert davor grob
(`FILLET_RADIUS_SLACK`), weil der Netz-Kern ihn an einem Sehnenzug misst und
deshalb ein wenig zu klein herauskommt. Ist der Abstand nicht bestimmbar,
bricht die Zuordnung ab, statt eine andere Fläche zu bearbeiten.

**Und `push_faces` nimmt einen Ort entgegen.** Ohne ihn bewegte es jede Fläche,
deren Normale in die gegebene Richtung zeigt — an einer Treppe alle Stufen
(24000,0 statt 21000,0, Befund Robert 10.09.2026). Die Richtung bleibt der
Vorfilter, die Stelle entscheidet.

## Eine Bahn ist kein Bogen

`sweep_path` (RM-147 E3) führt einen Querschnitt entlang einer gezeichneten
Bahn und benutzt dafür **`MakePipeShell`** mit `RightCorner`, nicht
`MakePipe`: An einer scharfen Ecke hört `MakePipe` auf zu bauen — gemessen an
einer Bahn aus 40 mm hoch und 30 mm quer ein Körper von 3141 mm³ statt 5497,
also genau das erste Segment, und ohne ein Wort dazu. `MakeSolid()` schließt
die Schale danach zu einem Körper; ohne diesen Schritt wäre das Ergebnis hohl,
und das fiele erst beim Schneiden oder Exportieren auf.

Innenkonturen folgen einzeln derselben Bahn und werden mit derselben
Booleschen Differenz wie beim Loft vom Außenkörper abgezogen. `MakePipeShell`
übernimmt nur den Außendraht; Löcher einer Profilfläche übernimmt es nicht.

Die Anfangstangente der ersten gerichteten Drahtkante muss senkrecht zum
XY-Querschnitt verlaufen. Geprüft wird die exakte Kurvenableitung, damit
Bögen und Splines nicht nach ihrer Sehne beurteilt werden. Schräger oder
entarteter Beginn hält vor dem Körperaufbau mit einem Handlungsvorschlag an.

## Was er einbringt

Was ein Netz nicht geben kann: echte Kanten — und damit Fasen und
Verrundungen, die rund sind statt facettiert, präzise Boolesche Operationen
ohne Tessellations-Artefakte, und STEP hinein wie hinaus.

## Die Einbahnstraße

```
B-Rep  ──────>  Mesh      jederzeit
B-Rep  <──╳───  Mesh      nie
```

**Der Rückweg existiert nicht, und der Objektbaum sagt das auch.** Ein Netz
hat die Kanten verloren, aus denen es gebaut wurde; das Gegenteil zu behaupten
ergäbe einen Körper, dessen „exakte" Verrundung ein Vieleck ist.

## Optional heißt: er meldet sich ab

Fehlt OpenCASCADE, ist `available()` falsch und `BRepUnavailable` die Antwort
— die Anwendung läuft weiter, die betroffenen Operationen sind es, die
verschwinden. **Kein Absturz, kein Stacktrace, ein Satz mit Weg nach vorn.**
Jeder Code hier prüft das, bevor er den Kern anfasst.

## OpenCASCADE 8 in der Bindung

Seit OCP 8.0.1 (05.09.2026) heißen fünf Dinge anders, und der Kern verlangt
diese Fassung (`pyproject.toml`, `brep`-Extra). Das gilt auch für den einen
Nutzer außerhalb dieses Verzeichnisses, `app/core/sketch/profile.py`:

| Vorher (OCP 7.9) | Jetzt |
|---|---|
| `OCP.TopTools.TopTools_IndexedMapOfShape` | `OCP.collections.IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher` |
| `TopTools_IndexedDataMapOfShapeListOfShape` | `OCP.collections.IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher` |
| `TopTools_ListOfShape` | `OCP.collections.List_TopoDS_Shape` |
| `TopoDS.Face_s(shape)`, `Edge_s`, `Wire_s` | `TopoDS.Face(shape)` — `TopoDS` ist ein Namensraum, kein `_s` |
| `Bnd_Box.Get()` | `kernel.box_limits(box)` — `Get` liefert eine ungebundene `Limits`-Struktur |
| `OCP.TColgp.TColgp_Array1OfPnt`, `TColgp_Array1OfPnt2d` | `OCP.collections.Array1_gp_Pnt`, `Array1_gp_Pnt2d` — `OCP.TColgp` ist ein leeres Modul |
| `OCP.GCE2d.GCE2d_MakeSegment`, `GCE2d_MakeArcOfCircle` | `OCP.GC.GC_MakeSegment2d`, `GC_MakeArcOfCircle2d` — `OCP.GCE2d` ist ein leeres Modul |

Die übrigen statischen Aufrufe (`TopExp.MapShapes_s`, `BRep_Tool.Triangulation_s`,
`BRepGProp.VolumeProperties_s`, `BRepBndLib.AddOptimal_s`) tragen ihr `_s`
weiter. Wer einen neuen Sammlungstyp braucht, sucht ihn in `OCP.collections`
über `dir()` — die Namen folgen dem C++-Template, nicht dem alten Typedef.
**Und ein leeres Modul importiert ohne Fehler**: `from OCP.GCE2d import …`
scheitert erst am Namen, und zwar erst, wenn die Zeile läuft — bei der
Skizze war das die Selbstschnittprüfung, die `tests/test_brep.py` nie
aufrief. Deshalb hält dort jetzt ein Test jeden `from OCP.…`-Import der
Anwendung gegen die installierte Bindung.

## Die Karte

| Datei | Rolle |
|---|---|
| `kernel.py` | Der `Solid` und sein Weg ins Netz. `available()`, `BRepUnavailable` |
| `profiles.py` | Vom Skizzenumriss zum exakten Körper (§30.1) — das größte Modul hier |
| `ops.py` | Die B-Rep-Operationen im Register (§25, §10) — **ohne** Verrunden und Fase, die stehen in `geom/edge_ops.py` |
| `edit.py` | Einen Körper formen |
| `features.py` | Merkmale aus der Topologie (§30, §21) |
| `step.py` | STEP hinein und hinaus |

## Grenzen

- **Kein zweiter Wahrheitsbegriff.** Weicht B-Rep vom Mesh-Kern ab, ist das
  ein Befund, kein „beide haben recht".
- **Verrunden und Fasen wohnen nicht mehr hier** (10.09.2026). Die zwei
  Operationen stehen in `geom/edge_ops.py` und nehmen beide Körperarten an;
  was dieser Kern beisteuert, ist `edit.fillet`/`edit.chamfer` — die exakte
  Hälfte, gerufen über eine Verzweigung nach `SceneObject.kind`. Der Grund
  für den Umzug ist die Karte selbst: Eine Operation, die auch Netze rechnet,
  ist keine B-Rep-Operation.
