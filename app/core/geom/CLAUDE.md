# `app/core/geom/` — wo Geometrie entsteht

Die einzige Stelle, an der Geometrie entsteht oder sich ändert (Regel 2).
Gerechnet wird gegen `manifold3d` und `trimesh`.

`move_feature` versetzt eine eindeutig topologisch verbundene Senkbohrung
als ganzen Hohlraum: alle Abschnitte aus `perceive.relations.cavity_chain_at`
begrenzen gemeinsam den Werkzeugkörper, alle Kennungen und Mittelpunkte
reisen mit. Zwei äußere Randringe werden geschlossen; eine unvollständige
oder mehrdeutige Fläche bleibt abgelehnt. Größenänderungen bleiben einzelne
Abschnitte und melden die übrigen; bei mehrteiligen Ketten wird keine
unvollständige automatische Änderung einer einzelnen Senkung vorgeschlagen.

Die Regeln stehen in `.claude/rules/operationen.md`.

`repair()` übernimmt Verschweißen und Dreiecksbereinigung nur, wenn ein
geschlossener Eingang danach geschlossen bleibt. Andernfalls bleiben das
Netz und seine Materialzuweisungen erhalten; ein Befund nennt den ausgelassenen
Schritt. Die Zusicherung entspricht `ingest.loader.normalise`. Die einzelnen
Reparaturhilfen bleiben für ausdrücklich gesteuerte Reparaturketten verfügbar.

Merkmalswerkzeuge verwenden die gemessene Tiefe unabhängig vom Durchmesser.
Nach einem Versatz entscheidet die Zielgeometrie über den Durchgang, auch bei
rein seitlicher Bewegung. Verlorener Durchgang erzeugt einen Befund und
korrigiert das Merkmal. Entfernte Kennungen bleiben in
`SceneObject.reserved_feature_ids` für spätere Kopien gesperrt (§21.2).

Materialslots werden nach einer Booleschen Operation anhand der erhaltenen
Eingangsflächen übertragen; eine gleiche Dreieckszahl beweist keine gleiche
Zuordnung. Rasterbudgets multiplizieren mit unbegrenzten Ganzzahlen.
Die Differenzansicht überspringt ausschließlich identische Netzarrays,
keine bloß gleichen Hüllquader und Volumina.

Eine mitgeführte exakte `MeshData.cavity` folgt in `transform.apply` derselben
Matrix wie der Körper. Änderungen der Topologie verwerfen die Auskunft,
solange ihre Gültigkeit nicht eigens hergestellt wird.

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
aufrechte Lage.

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
