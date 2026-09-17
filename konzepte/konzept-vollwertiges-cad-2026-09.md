# Was Solidon zu einem vollwertigen CAD fehlt

> **Stand 17.09.2026 — Recherche und Entscheidungsvorlage. Nichts davon ist
> beauftragt, nichts davon ist gebaut.** Alle Zahlen hier sind an diesem Tag
> am HEAD gemessen, nicht aus Dokumenten übernommen; wo eine Zahl aus einem
> anderen Dokument stammt, steht die Quelle daneben. Offene Arbeit entsteht
> daraus erst, wenn sie ein Kästchen im Register von `ROADMAP.md` bekommt.

Anlass ist Roberts Frage vom 17.09.2026: *„was fehlt uns, um es zu einem
vollwertigen 3D-CAD-Programm zu machen, ohne CAD-Erfahrung und alles möglichst
einfach, und STL die Merkmale und alles sauber zu erkennen."*

---

## 1. Die Frage sind drei Fragen, und zwei davon ziehen gegeneinander

Sie lassen sich nicht zusammen beantworten, weil sie verschiedene Dinge wollen:

1. **Vollwertig** heißt: was ein CAD kann, kann Solidon auch — Bezugsebenen,
   Baugruppen, Zeichnungen, jede Operation auf exakter Geometrie.
2. **Ohne CAD-Erfahrung, möglichst einfach** heißt: der Kunde soll *nicht*
   lernen, was ein CAD verlangt. Shapr3D braucht drei bis fünf Tage
   Einarbeitung, Fusion 400 bis 1200 Stunden, Tinkercad liefert das erste
   Modell unter einer Stunde (Recherche in
   [konzept-einfache-bedienung-2026-09.md](konzept-einfache-bedienung-2026-09.md) §2,
   13.09.2026). Jede Fähigkeit aus Frage 1 kostet an dieser Stelle.
3. **STL-Merkmale sauber erkennen** heißt: das, was der Kunde mitbringt, wird
   wieder zu Konstruktion. Das ist die einzige der drei Fragen, die **beide**
   anderen bedient — und die einzige, in der Solidon heute im Markt vorn steht
   ([konzept-wettbewerb-2026-08.md](konzept-wettbewerb-2026-08.md) §2.3:
   „die am meisten unterschätzte Position im ganzen Programm").

Dieses Papier beantwortet alle drei, aber es empfiehlt nicht alle drei
gleich stark. Die Empfehlung steht in §3 und wird in §12 zu einer Reihenfolge.

---

## 2. Der Bestand, gemessen

Wer „was fehlt uns" fragt, muss zuerst wissen, was da ist. Am 17.09.2026
gezählt, über `bootstrap.load_operations()` und am Quelltext:

| | Zahl |
|---|---|
| Registrierte Operationen | **132**, in 15 belegten Kategorien, **alle rücknehmbar** |
| Bausteine | **35** in 6 Gruppen (AGENTS.md nennt noch 27 — veraltet) |
| Merkmalsarten am Netz | **12** (`FeatureKind`, `app/core/types.py:51`) |
| Zwangsbedingungen im Skizzenlöser | **15** im Kern (`solver._CONSTRAINT_TARGETS`), 16 Namen in der Oberfläche |
| Zeilen `app/core/geom` / `perceive` / `sketch` / `brep` / `app/ui` | 33 927 / 12 869 / 5 610 / 4 494 / 105 268 |
| Zeilen Tests | 262 482 in 305 Dateien |

Der Skizzenlöser ist kein Provisorium: `scipy.optimize.least_squares` mit
`trf`/`lsmr`, **analytische Jacobi-Zeile je Bedingung**, dünn besetzt, plus
eigener Zugmodus mit `DRAG_STIFFNESS`. Gemessen 200 Bedingungen über 100
Linien in **55,1 ms** — das Budget aus §31 ist 100 ms. Freiheitsgrade werden
über den Rang ermittelt und im Klartext angezeigt; Splines gibt es, im exakten
Kern als interpolierende B-Spline mit exaktem Flächenintegral.

Der exakte Kern ist OCP 8.0.1 (OpenCASCADE, LGPL-2.1 mit Linking-Ausnahme),
formal optional, im Kundenpaket zwölf Module fest mitgeliefert. Er trägt
Extrude, Revolve, Sweep über Bogen und gezeichnete Bahn, Loft, Fillet,
Chamfer, Shell, Draft, Push/Pull, Boolesche Operationen, exakte Bohrungen mit
Senkung und Langloch, ein echtes helikales Gewinde und STEP in beide
Richtungen.

**Das ist kein Programm, dem CAD-Grundlagen fehlen.** Deshalb lautet die
Antwort auf „was fehlt" nicht „eine Funktion".

---

## 3. Die Kernaussage: es fehlt keine Funktion, es reißen drei Ketten

Solidon hat von fast allem ein Stück. Was fehlt, ist an drei Stellen die
**Fortsetzung** — und zwar jeweils genau an der Stelle, an der ein Kunde aus
einem einzelnen Schritt eine Konstruktion machen würde.

| Kette | Sie beginnt | Sie reißt bei | Gemessen |
|---|---|---|---|
| **1 — Der exakte Zweig** | `create_brep_box`, `load_step`, `sketch_extrude` | dem zweiten oder dritten Schritt | **183 Aufrufe** von `as_mesh_data` außerhalb von `brep/` |
| **2 — Die Skizze am Körper** | Fläche anklicken, Skizze liegt dort | dem Versuch, sich auf den Körper zu beziehen | *Projizieren* scheitert auf **6 von 6** Flächen des eigenen Körpers |
| **3 — Das Erkannte** | 12 Merkmalsarten, 89–100 % Flächendeckung | dem Rückweg zu bearbeitbarer Geometrie | `torus` und `thread`: **0 Operationen**; Mesh→B-Rep: **0 Zeilen** |

Drei Ketten, drei Kapitel. Die Empfehlung am Ende: **Kette 2 zuerst, dann 1,
dann 3** — nicht, weil 3 unwichtig wäre, sondern weil 3 ohne 1 und 2 nirgends
hinführt.

---

## 4. Kette 1 — der exakte Zweig endet nach einem Schritt

`drill_brep_hole` ist 2026 aus genau diesem Grund entstanden; der Docstring
sagt es wörtlich: *„ohne sie endete der exakte Zweig nach einem Schritt."*
Für den Rest gilt es weiterhin.

**Wer den exakten Kern kennt:** drei Operationen verlangen ihn
(`shell_exact`, `drill_brep_hole`, `brep_to_mesh`), elf verzweigen zweikernig
(`fillet_edges`, `chamfer_edges`, `push_face`, `draft_faces`, `sketch_pocket`,
`field_cut`, `resize_hole`, `slot_hole`, `resize_feature`, `remove_feature`),
die fünf Skizzenoperationen erzeugen ihn, starre Bewegungen halten ihn.

**Wer ihn nicht kennt** — und deshalb still vernetzt: `countersink_hole`,
`plug_hole`, `cut_away`, `split_bodies`, `split_pinned`, `thicken`,
`hollow_object` und **alle 48 Bausteinoperationen**. Gemeldet wird es
zuverlässig (`evaluate.py:598` vergleicht die Art vorher und nachher und hängt
`evaluate.exact_became_mesh` an) — aber der Kunde, der eine Platte exakt
bohrt und dann eine Einpressbuchse einsetzt, hat danach ein Netz.

Dazu kommen Einschränkungen innerhalb des exakten Kerns, die im Alltag
auffallen:

- **Fillet: ein Radius je Operation.** `builder.Add(radius, edge)` in einer
  Schleife — kein variabler Radius, kein Flächen-Flächen-Fillet, kein
  Eckenrückzug.
- **Chamfer: nur 45° über eine Distanz.** Kein Distanz-Distanz, kein
  Distanz-Winkel.
- **Shell öffnet, was oben liegt** (`_top_faces`) — keine frei gewählten
  Öffnungsflächen, keine variable Wandstärke.
- **Draft stellt alles Senkrechte an**, neutrale Ebene fest auf der Unterkante.
- **Revolve nur um Z.** Keine Drehachse aus einer Konstruktionslinie.
- **Loft nur zwei Querschnitte**, keine Leitkurven.
- **Sweep ohne Twist und ohne mitlaufende Skalierung**; der Querschnitt muss
  auf XY liegen, die Bahn auf XZ oder YZ.
- **Kein Revolve-Cut, kein Sweep-Cut, kein Loft-Cut, kein „Vereinigen im
  selben Schritt".** Nur Extrude kennt einen Schnitt (`sketch_pocket`).
  Alles andere erzeugt einen neuen Körper, den man danach abzieht — zwei
  Schritte für eine Handlung, und im Verlauf steht eine Hilfsgeometrie, die
  niemand gemeint hat.
- **`pattern` und `mirror_object` erzeugen getrennte Objekte**, deren Kopien
  ihre Merkmale verlieren (`features={}`). Ein Lochbild im selben Körper gibt
  es nur als Schnitt über `field_cut`, nicht als wiederholtes Merkmal.
- **STEP kommt ohne Struktur herein**: `STEPControl_Reader` liefert einen
  Compound als **ein** Szenenobjekt. Kein XCAF, also keine Bauteilnamen, keine
  Farben, kein Baugruppenbaum.
- **Auf Torus- und Freiformflächen findet der exakte Kern keine Merkmale** —
  `features._describe` beschreibt Ebene, Zylinder, Kegel, Kugel und gibt sonst
  `None` zurück. Ein importiertes STEP mit B-Spline-Flächen hat dort nichts
  Anklickbares: keine Skizze auf der Fläche, keine Passung, kein
  Bohrungsbezug. **Dieselbe Geometrie zeigt als STL mehr Merkmale als als
  STEP**, und für den Kunden ist das ein Widerspruch ohne sichtbare Ursache.

---

## 5. Kette 2 — die Skizze findet den Körper nicht

Das ist der billigste und der wirksamste Punkt des ganzen Papiers.

**Der Befund.** *Projizieren* (`sketch/edit.py:476`) heißt so, ist aber kein
Projizieren, sondern ein **Ebenenschnitt** durch den Körper. Auf der Fläche,
auf der man gerade zeichnet, schneidet die Ebene nichts — sie ist koplanar zum
Rand. Über alle sechs Flächen von `plate_holes.stl` durchgefahren: **sechs von
sechs enden mit** *„Diese Ebene schneidet den Körper nicht — dort gibt es
keine Kante."* Genau der Fusion-Normalfall („auf die Fläche skizzieren, die
Kontur der Fläche übernehmen") ist damit versperrt.

Zweitens: **alles kommt als Strecke an.** Dieselbe Platte auf `plane:xy`
ergibt 392 Elemente, ausnahmslos `kind="line"`, kürzeste Kante 0,17 mm.
Bohrungskanten werden zu Polygonzügen — **auch an einem exakten Körper**, weil
`Solid.raw` die Tessellierung liefert.

Dass das nicht so sein muss, ist gemessen: ein exakter Quader mit einer
Bohrung trägt `{GeomAbs_Line: 26, GeomAbs_Circle: 4}`. **Die Kreise sind da.**
Wer `Solid.shape` statt `Solid.raw` nimmt und `BRepAdaptor_Curve` fragt,
bekommt aus einer Bohrungskante einen Kreis mit Mittelpunkt und Radius statt
24 Strecken — und damit ein Skizzenelement, auf das eine Bedingung passt.

Drittens fehlt das **Bezugssystem**, und das ist die größte strukturelle
Lücke des ganzen Programms. Suche nach `offset_plane`, `Versatzebene`,
`datum` im gesamten Quelltext: **kein Treffer.** Es gibt genau zwei Sorten
Skizzenebene — die drei Hauptebenen und eine erkannte planare Fläche. Es gibt
keine Ebene „20 mm über dieser Fläche", keine Ebene durch drei Punkte, keine
Ebene senkrecht auf einer Kante, keine Winkelebene, keine freie Achse.

Was daraus folgt, ist unscheinbar und teuer: **Wer nicht auf einer
vorhandenen Fläche zeichnen kann, kann dort nicht konstruieren.** Ein Deckel
5 mm über dem Rand, eine Bohrung in einer schrägen Anschlussfläche, eine
Rippe in der Symmetrieebene — jedes dieser Alltagsdinge braucht eine Ebene,
die es nicht gibt.

Viertens: **die Projektion ist nicht assoziativ.** Die Hilfslinien sind eine
Kopie ohne Rückbezug; ändert sich der Körper, altert die Hilfsgeometrie still.
Ein „Konvertieren" im CAD-Sinn — benannte Kante wird Skizzenelement, mit
stabiler Kennung — gibt es nicht.

---

## 6. Kette 3 — das Erkannte wird nicht wieder Konstruktion

Die Erkennung ist gut. Zwölf Arten, an einem mechanischen Korpus von 203 776
Dreiecken in 0,92 Sekunden, Kennungen über Drehung und Verschiebung stabil
(gemessen: sechs Korpusdateien, je 100 % zugeordnet, null verwaist, null
mehrdeutig). Das Verfahren ist Region Growing über die Flächennachbarschaft
mit Abbruch am Knick, dann Formentscheidung aus den Normalen und Einpassung
nach kleinsten Quadraten; beim Gewinde eine Steigungssuche über die
Phasenkonzentration von `z − p·θ/2π`, was der Sache nach ein Hough-Votum ist.

**Und dann hört es auf.** Über das Register gezählt, welche Operationen eine
Merkmalsart annehmen:

```
face 43 · hole 15 · pin 7 · cone 6 · slot 6 · sphere 4
fillet 2 · void 2 · curved_face 2 · edge_loop 1 · torus 0 · thread 0
```

Ein erkannter Wulst und ein eingelesenes Gewinde sind ein Etikett ohne
Handlung. Beim Gewinde nennt der Satz wenigstens den Umweg; beim Torus gibt es
keinen.

**Was gar nicht erkannt wird**, obwohl es die häufigsten Merkmale nach der
Bohrung sind: Tasche, Nut, Rippe, Steg, Wand, Lasche, Dom, scharfe Kante,
Kantenzug, Symmetrieebene, Dünnstelle als benennbares Merkmal, Lochmuster als
Muster. Eine rechteckige Tasche mit verrundeten Ecken steht als vier `fillet`
und ein paar `face` im Baum — richtig gerechnet, und für den Kunden nicht
das, was er sieht. Eine Fase heißt „Senkung 90° Ø 5,8"; wer „Fase 1 mm" sucht,
findet sie nicht. Bauplan §21.1 sagt Symmetrieebenen ausdrücklich zu; im Code
gibt es sie nicht.

Und der Rückweg zu exakter Geometrie fehlt ganz: `grep -rn "Sewing|to_brep|
from_mesh" app/` liefert **null Treffer**. Das ist eine Entscheidung, keine
Vergesslichkeit — sie steht an drei Stellen im Code und als RM-022 offen im
Register.

### 6.1 Der naive Nähweg ist tot, aber aus einem anderen Grund als bisher notiert

[konzept-flaechenrueckgewinnung-2026-08.md](konzept-flaechenrueckgewinnung-2026-08.md)
§6 verwarf ihn mit einer Messung: `block_with_rounded_edge.stl`, 108 Dreiecke,
genäht → **108 Flächen, 324 Kanten**, und ein Fillet darauf verrundete jede
Facette.

Die Messung stimmt, aber sie ist unvollständig: **`ShapeUpgrade_UnifySameDomain`
wurde damals nicht gefahren.** Heute nachgemessen:

| Datei | Dreiecke | genäht | nach Unify | Flächenarten |
|---|---:|---|---|---|
| `block_with_rounded_edge.stl` | 108 | 108 Flächen, 324 Kanten | **30 Flächen, 168 Kanten** | alle `GeomAbs_Plane` |
| dasselbe, Winkeltoleranz 0,1 | 108 | — | **16 Flächen, 138 Kanten** | alle `GeomAbs_Plane` |
| `plate_holes.stl` | 796 | 796 Flächen, 2388 Kanten | **198 Flächen, 1176 Kanten** | alle `GeomAbs_Plane` |

Der Befund dreht sich damit um. **Das Zusammenfassen ebener Facetten kann
OpenCASCADE allein** — dafür braucht es die Merkmalserkennung nicht. Was es
nicht kann, ist die Rundung zum Zylinder und die Bohrungswand zum
Zylindermantel zu machen: alle 30 beziehungsweise 198 Flächen bleiben eben.
**Der Flaschenhals ist ausschließlich das Ersetzen der gekrümmten
Facettenbänder durch analytische Flächen** — und genau deren Parameter
(Achse, Radius, Winkel, Mitte) liefert Solidons Erkennung bereits fertig.

### 6.2 Die Werkzeuge dafür liegen schon im Paket

Geprüft gegen die gepinnte Bindung, alles vorhanden:

| Aufgabe | Baustein |
|---|---|
| Schnittkurve zweier Flächen — „die schwere Stelle" aus §5 des alten Konzepts | `GeomAPI_IntSS` |
| Facetten zusammenfassen | `ShapeUpgrade_UnifySameDomain` |
| Flächen zum Volumen nähen | `BRepBuilderAPI_Sewing`, `ShapeFix_Shape`, `ShapeFix_Solid` |
| nicht erkannten Rest schließen | `BRepOffsetAPI_MakeFilling`, `GeomAPI_PointsToBSplineSurface` |
| Zeichnungsableitung, auch am Netz | `HLRBRep_Algo`, `HLRBRep_PolyAlgo` |

**Keine neue Abhängigkeit, keine Lizenzfrage, kein Eintrag in `licences.toml`.**
Regel 22 wird nicht berührt.

### 6.3 Der bessere Weg: nicht nähen, sondern nachbauen

Es gibt einen Weg, den das alte Konzept nicht betrachtet hat, und er passt
besser zu Solidons Architektur als das Nähen.

Statt aus erkannten Flächen ein Volumen zusammenzusetzen, wird der Körper als
**Folge registrierter Operationen nachgebaut**: Grundform aus den Ebenen,
darauf `drill_brep_hole` je Bohrung, `chamfer_edges`/`fillet_edges` je
Verrundung, `countersink_hole` je Senkung. Alle Parameter dafür liefert die
Erkennung heute schon — gemessen an `plate_holes.stl`:

```
hole_1..4   diameter 5.1901  depth 8.0  through True  residual 0.0
face_1..6   area 3915.29 / 640.0 / 400.0
```

Was dabei entsteht, ist nicht „ein exakter Körper", sondern **eine
Konstruktion mit Verlauf**: parametrisch, im Stapel, jeder Schritt einzeln
änderbar, jede Bohrung ein benanntes Maß. Das ist genau das, was „vollwertiges
CAD" für den Kunden bedeutet — und es benutzt ausschließlich, was schon da
ist. Der Fachbegriff dafür ist *design intent recovery*; das MIT-lizenzierte
`mesh2cad` (OpenCascade + PySide6) geht denselben Weg und nennt dieselbe
Grenze: es trägt extrudierte Platten und Gehäuse, keine organischen Formen.

Die Grenze ist ehrlich benennbar und deckt den Zielkunden: Halterungen,
Gehäuse, Adapter, Platten sind prismatisch. Was nicht trägt, sagt die
Anwendung **vorher**, nicht nach dem Versuch.

Die drei offenen Fragen aus §5 des alten Konzepts bleiben — und der Nachbauweg
entschärft zwei davon:

1. **Nachbarschaftskarte** (welche Fläche grenzt an welche): beim Nähen
   zwingend, beim Nachbauen nicht — eine Bohrung braucht Achse und Durchmesser,
   nicht ihre Nachbarn.
2. **Toleranzbudget**: siehe §7, jetzt gemessen.
3. **Umgang mit dem nicht erkannten Rest**: beim Nachbauen fällt er weg statt
   zum Zwitter zu werden — was nicht als Operation erklärbar ist, wird nicht
   nachgebaut, und der Körper bleibt ein Netz. Kein „Zwitter, den der Bauplan
   nicht kennt".

---

## 7. Die Erkennung misst systematisch zu klein — neuer Fund

Das ist der unmittelbarste Teil von „STL die Merkmale sauber erkennen", und er
ist heute gemessen.

Ein STL kennt den Kreis nicht mehr, nur das Vieleck. Der gemeinte Radius liegt
auf dem **Umkreis** — dort liegen die Facettenecken. Wer über alle Punkte
eines Flecks mittelt, landet zwischen Umkreis und Inkreis, also zu klein.
`fit_cylinder` mittelt (Kåsa-Kreisfit über die projizierten Punkte).

Gemessen an gebohrten Platten, Sollradius und Facettenzahl beide bekannt:

| Soll Ø | Facetten | erkannt Ø | Abweichung | Umkreis aus den Ecken |
|---:|---:|---:|---:|---:|
| 5,2 | 8 | — nichts erkannt | — | — |
| 5,2 | 12 | — nichts erkannt | — | — |
| 5,2 | 16 | 5,1113 | **−0,0887** | 5,2000 (±0,0000) |
| 5,2 | 24 | 5,1605 | −0,0395 | 5,2000 |
| 5,2 | 48 | 5,1901 | −0,0099 | 5,2000 |
| 15,0 | 16 | 14,7441 | **−0,2559** | 15,0000 |
| 30,0 | 16 | 29,4882 | **−0,5118** | 30,0000 |
| 30,0 | 24 | 29,7720 | −0,2280 | 30,0000 |
| 50,0 | 32 | 49,7860 | −0,2140 | 50,0000 |

Drei Dinge stehen darin:

1. **Der Fehler ist systematisch und einseitig — immer zu klein.** Das ist die
   schlechtere Richtung: ein zu klein gemessenes Durchgangsloch führt zu einer
   Passung, in die die Schraube nicht geht.
2. **Er wächst mit dem Durchmesser.** Bei Ø5 sind 0,09 mm verschmerzbar, bei
   Ø30 sind 0,51 mm eine halbe Wandstärke. Ein STL mit 16 Segmenten je Kreis
   ist keine Ausnahme, sondern ein üblicher älterer Export.
3. **Der Umkreis aus den Netzecken trifft in allen sechs Fällen exakt** —
   Abweichung 0,0000. Der Ort dafür ist derselbe Fleck, der schon vorliegt:
   größter Abstand der Fleckecken zur bereits ermittelten Achse.

Dazu: **unter 16 Facetten wird gar nichts mehr erkannt.** Ein grob
facettiertes Loch fällt durch, ohne dass der Kunde erfährt, warum.

Der zweite Messfund derselben Richtung steht in der Bestandsaufnahme der
Erkennung: `CYLINDER_SPREAD` ist an der **Facettenbreite** normiert
(`width = sqrt(mean(area) * 2)`). Eine feinere Vernetzung halbiert die Breite,
ohne die Polygonnäherung zu ändern — der Wert verdoppelt sich exakt und reißt
die Schranke. Gemessen an derselben Platte, nur unterteilt:

```
203 776 Dreiecke  0,93 s  {hole: 4, face: 6}
815 104 Dreiecke  2,18 s  {face: 6}          <- vier Bohrungen weg
```

Bei 815 104 Dreiecken gelten **alle** Dreiecke als eben; es gibt keinen einzigen
gekrümmten Fleck mehr. Die Bohrung verschwindet aus dem Objektbaum, ohne
Hinweis. Beide Funde haben dieselbe Ursache: Die Erkennung misst die
**Facettierung** und nicht die Geometrie, die darunter gemeint war.

---

## 8. Was „vollwertig" darüber hinaus verlangt — die Prüfliste

Wenn „vollwertiges CAD" wörtlich gemeint ist, ist dies die Liste. Sie ist
vollständig und nach Gewicht sortiert; die Spalte „Lage" sagt, ob der Punkt
frei ist oder gegen eine bestehende Entscheidung läuft.

| Fähigkeit | Stand | Lage |
|---|---|---|
| Bezugsgeometrie: Versatzebene, Ebene durch drei Punkte, Winkelebene, Achse, Punkt | **fehlt ganz** | frei |
| Kanten eines Körpers als exakte Skizzenelemente übernehmen | fehlt (nur Ebenenschnitt, nur Strecken) | frei |
| Fillet mit variablem Radius, Flächen-Flächen-Fillet | fehlt | frei |
| Chamfer Distanz-Distanz und Distanz-Winkel | fehlt | frei |
| Shell mit gewählten Öffnungen, Draft mit gewählten Flächen | fehlt | frei |
| Revolve-Cut, Sweep-Cut, Loft-Cut, „im selben Schritt vereinigen" | fehlt | frei |
| Loft über mehr als zwei Schnitte, Leitkurven; Sweep mit Twist | fehlt | frei |
| Muster und Spiegelung **als Merkmal im Körper** | fehlt (nur getrennte Objekte) | frei |
| Merkmalsarten: Tasche, Nut, Rippe, Kante, Fase, Symmetrie, Lochmuster | fehlt | frei |
| Exakte Merkmale auf Torus- und Freiformflächen (STEP) | fehlt (`_describe` gibt `None`) | frei |
| STEP-Baugruppenstruktur lesen (XCAF: Namen, Farben, Baum) | fehlt | frei |
| Verlauf: Schritt einfügen, umsortieren, zurückspulen, stummschalten | fehlt (nur ändern und löschen) | frei |
| Durchmesser als Messwerkzeug ohne erkanntes Merkmal | fehlt | Bauplan §18.3 entscheidet es bewusst anders |
| Mesh → exakte Geometrie | fehlt | **RM-022 offen, Entscheidung** |
| **Baugruppen** mit Hierarchie, Instanzen, lebenden Bedingungen | fehlt (flache Szene; Passungen melden, koppeln nicht) | **abgelehnt** (Wettbewerb §5) |
| **Zeichnungsableitung** mit Bemaßung | fehlt (`drawing.py` ist ein Handbuchwerkzeug) | **abgelehnt** (Wettbewerb §5) |
| Ellipse in der Skizze | fehlt | frei, klein |
| Tangente Bogen-an-Bogen | fehlt | frei, klein |

**Zu den beiden abgelehnten Punkten.** Sie sind am 13.08.2026 mit den
Marktgruppen verworfen worden, und die Begründung war stimmig: Solidon ist die
Vorstufe vor dem Slicer, kein Maschinenbau-CAD. Roberts heutige Frage macht
sie wieder auf, deshalb gehören die Kosten hierher und nicht in eine Fußnote:

- **Baugruppen** wären der größere Eingriff. `Scene.objects` ist ein flaches
  Wörterbuch ohne `parent_id`, ohne Instanzen; 3MF wird beim Einlesen
  ausdrücklich verflacht. Eine Hierarchie zieht Projektformat, Migration,
  Objektbaum, Auswertung und jede Passung nach. Lebende Bedingungen zwischen
  Körpern brauchen zusätzlich einen 3D-Löser — und dafür gibt es **keine
  einsetzbare fremde Bibliothek** (§10).
- **Zeichnungsableitung** wäre der kleinere Eingriff, als gedacht:
  `HLRBRep_PolyAlgo` arbeitet auf der Triangulation und liefert sichtbare und
  verdeckte Kanten **auch für Netze**; `drawing.py` kann bereits Maßlinien
  zeichnen, nur setzt sie heute niemand aus Geometrie. Ein Blatt mit drei
  Ansichten, automatischen Hauptmaßen und PDF-Ausgang ist eine überschaubare
  Serie. Ob der Zielkunde das braucht, ist eine Produktfrage, keine technische.

---

## 9. Einfachheit ist kein Weglassen, sondern eine Reihenfolge

Jede Fähigkeit aus §8 macht das Programm größer. Die Grenzen dafür stehen
bereits als Test (`tests/test_interface_limits.py`, aus P15 E12): höchstens
neun Menüs, zwölf Zeilen je Menü, acht Werkzeuge, **acht Felder auf der
Vorderseite**, genau ein Menüeintrag je Operation, kein Werkzeug ohne
Hinweissatz.

Die Regel, die daraus folgt, steht schon geschrieben und gilt hier
unverändert (P15 E11 und E14): **eine Operation je Handlung, nicht je
Variante** — fünfzehn neue Fähigkeiten wurden dort zu sechs neuen
Menüeinträgen. Und: alles ist **da**, aber nicht alles ist **vorn**.

Angewendet auf dieses Papier heißt das konkret:

- **Bezugsebenen werden kein Menü.** Sie erscheinen dort, wo man sie braucht:
  im Ebenenwähler der Skizze als vierte Möglichkeit neben den drei
  Hauptebenen — „auf dieser Fläche, mit Abstand ___".
- **Revolve-Cut wird kein zweiter Menüeintrag**, sondern ein Feld im Dialog
  von *Rotationskörper aufziehen*: neuer Körper oder abziehen. Genau das war
  die Entscheidung aus
  [konzept-varianten-zusammenlegen-2026-08.md](konzept-varianten-zusammenlegen-2026-08.md).
- **Der Nachbau aus §6.3 ist kein Werkzeug**, sondern ein Angebot im
  Prüfbericht, wenn die Erkennung trägt: „Dieses Modell lässt sich als
  Konstruktion nachbauen — vier Bohrungen, eine Verrundung. [Nachbauen]".
  Trägt sie nicht, steht das Angebot nicht da, und es steht auch kein
  ausgegrauter Eintrag herum.
- **Die Radiuskorrektur aus §7 ist gar keine Bedienung.** Sie ist eine
  Zeile im Fitter und wirkt überall, ohne dass jemand etwas lernt. Das ist der
  Idealfall: bessere Vorgabe statt zusätzlicher Einstellmöglichkeit (§2.4).

---

## 10. Bibliotheken — was hilft, was nicht

Der Auftrag lautete ausdrücklich, Bibliotheken zu prüfen. Ergebnis: **für
keinen der Punkte oben wird eine neue Abhängigkeit gebraucht**, und für den
einen, bei dem eine naheliegt, ist sie nicht einsetzbar.

| Kandidat | Lizenz | Urteil |
|---|---|---|
| **OCP 8.0.1** (im Paket) | Apache-2.0 / LGPL-2.1 mit OCCT-Ausnahme | trägt §6.2 und die Zeichnungsableitung vollständig |
| **`planegcs`** 0.8.0, FreeCADs 2D-Löser | LGPL-2.1-or-later — nach `licences.toml` zulässig | **nicht einsetzbar**: Räder nur für cp312/cp313, nur `win_amd64` und `manylinux x86-64`. Solidon fährt **CPython 3.14.7** und liefert macOS mit. Selbst bauen hieße Eigen3 und Boost in die CI für drei Plattformen |
| **`py-slvs`** (SolveSpace) | **GPL-3.0-or-later** | ausgeschlossen durch Regel 15 |
| **Ansatz** (2D/3D-Löser, Rust) | MIT | 7 Commits, keine Python-Bindung, 2D-Skizzenbedingungen ausdrücklich nicht umgesetzt. Kein Kandidat |
| **`pyransac3d`**, `PrimitivesFittingLib` | MIT/BSD | lösen ein Problem, das Solidon schon gelöst hat (89–100 % Flächendeckung ohne sie) |
| **Point2CAD, CAD-Recode, CADFit, ComplexGen** | Forschung, teils ohne Freigabe | lernende Rekonstruktion aus Punktwolken. Widerspricht Leitprinzip 7 („deterministische Geometrie") und §42; als Wissensquelle für das Verfahren nützlich, nicht als Baustein |
| **`mesh2cad`** | MIT | dieselbe Idee wie §6.3, als Beleg brauchbar, nicht zum Einbau |

Der wichtigste Satz dieses Kapitels: **Solidon braucht `planegcs` nicht.**
Der eigene Löser ist mit 15 Bedingungsarten, analytischer Jacobimatrix und
55 ms auf 200 Bedingungen der besseren Lösung näher als eine Bindung, die auf
der Zielplattform gar nicht läuft. Diese Entscheidung war 2026 schon einmal
gefallen ([konzept-sindricad.md](konzept-sindricad.md) §3.1) und ist heute
gegen den aktuellen Paketstand bestätigt.

---

## 11. Was hier ausdrücklich **nicht** vorgeschlagen wird

Damit die Vorschläge oben nicht mit alten Entscheidungen kollidieren:

1. **Kein Ersatz des Mesh-Kerns durch B-Rep.** §30 sagt „neben, nicht statt";
   der Mesh-Kern trägt Weg 1 und Weg 3.
2. **Keine Verzweigungen im Op-Stack**, kein Plugin-System, keine Cloud, kein
   Konto, keine Telemetrie, keine Browser-Version, kein eigener Slicer.
3. **Kein Einfach-/Profi-Modus** und keine Betriebsarten-Umschaltung
   (Produktkompass §1.1) — stattdessen gestufte Tiefe.
4. **Kein Umbau der Bedienzone zu einem Befehlsband** (abgelehnt 29.08.2026).
5. **Kein naives Nähen mit anschließendem Fillet** — mit Zahlen widerlegt,
   heute erneut (§6.1).
6. **Kein lernendes Verfahren in der Geometrie.** Absicht darf
   probabilistisch sein, Geometrie rechnet Code.
7. **Kein Text als Skizzenkontur, keine assoziativen Skizzenmuster, kein
   `offset_face`, kein FEM, keine Topologieoptimierung, kein Sculpting-Ausbau.**
8. **Keine Zusage, dass jede STL zurückgewonnen wird.** Was nicht trägt, wird
   vorher gesagt.

---

## 12. Stufenplan

Vier Stufen, jede für sich abnehmbar, jede mit einem Kriterium, das rot werden
kann. Die Reihenfolge folgt dem Kundennutzen je Aufwand, nicht der Logik der
Kapitel.

### Stufe 1 — Die Erkennung misst, was gemeint war

Der kleinste Eingriff mit der größten Breitenwirkung; er verbessert jede
Bohrungsoperation, jede Passung und jeden Prüfbericht auf einmal.

- Radius der Rundformen am **Umkreis** bestimmen statt am Mittel (§7).
- `CYLINDER_SPREAD` von der Facettenbreite lösen, damit eine feinere
  Vernetzung kein Merkmal mehr verschluckt.
- Unterhalb von 16 Facetten benennen, warum nichts erkannt wurde, statt zu
  schweigen.

*Abnahme:* Der gemessene Durchmesser weicht bei 16, 24, 32 und 48 Facetten um
weniger als 0,01 mm vom Sollmaß ab (heute bis 0,51 mm). `plate_holes.stl`
behält seine vier Bohrungen bei jeder Unterteilungsstufe bis 3,2 Mio.
Dreiecke. Beide Fälle als Testdatei, nicht als Sonderfall im Code.

### Stufe 2 — Die Skizze findet den Körper

Löst Kette 2 und macht das vorhandene Skizzensystem erst benutzbar.

- **Bezugsebenen**: Versatz zu einer Fläche, Ebene durch drei Punkte,
  Winkelebene. Im Ebenenwähler, nicht im Menü (§9).
- ***Projizieren* auf der eigenen Fläche**: statt des Ebenenschnitts die
  Flächenkontur selbst übernehmen.
- **Kreise bleiben Kreise**: am exakten Körper über `BRepAdaptor_Curve` statt
  über die Tessellierung; am Netz die erkannten Rundformen als Kreis statt
  als Polygonzug.

*Abnahme:* Auf jeder der sechs Flächen von `plate_holes.stl` liefert
*Projizieren* die Kontur dieser Fläche. Eine Bohrungskante kommt als **ein**
Kreiselement an, nicht als 24 Strecken. Eine Skizze auf einer Versatzebene
5 mm über einer Fläche erzeugt einen Körper an der richtigen Stelle.

### Stufe 3 — Der exakte Zweig hält

Löst Kette 1. Umfang ist eine Entscheidung; die Reihenfolge nach Häufigkeit
im Kundenweg ist: `countersink_hole`, `cut_away`, `plug_hole`, `hollow_object`,
dann die Bausteine mit den meisten Einsätzen.

- B-Rep-Zweig für die genannten Operationen.
- Revolve-Cut, Sweep-Cut, Loft-Cut und „vereinigen" als Feld im jeweiligen
  Dialog, nicht als neuer Menüeintrag.
- Merkmale auf Torus- und Freiformflächen im exakten Kern, damit ein STEP
  nicht weniger zeigt als dieselbe Geometrie als STL.

*Abnahme:* Ein Kundenweg von fünf Schritten (STEP laden, bohren, senken,
aushöhlen, verrunden) endet als exakter Körper und lässt sich als STEP
exportieren. Heute endet er nach Schritt zwei als Netz.

### Stufe 4 — Das Erkannte wird Konstruktion (RM-022, neu gefasst)

Das ist die Stufe, die eine ausdrückliche Umfangsentscheidung braucht, und
dieses Papier schlägt vor, sie **als Nachbau** zu führen und nicht als
Flächenrückgewinnung (§6.3).

- Aus den erkannten Merkmalen eine Operationsfolge erzeugen: Grundform,
  Bohrungen, Senkungen, Verrundungen, Fasen.
- Das Angebot steht im Prüfbericht, wenn die Erkennung trägt, und sonst nicht.
- Was nicht als Operation erklärbar ist, wird nicht nachgebaut; der Körper
  bleibt dann ein Netz, und das wird gesagt.

*Abnahme:* `plate_holes.stl`, `plate_countersunk.stl` und
`block_with_rounded_edge.stl` kommen als Konstruktion mit Verlauf zurück; das
Volumen trifft das Netz innerhalb der Facettierungstoleranz aus §7; jede
Bohrung ist ein änderbarer Wert. `post_with_fillet.stl` und eine erzeugte
Figur werden **abgelehnt**, mit Begründung, vor dem Versuch.

---

## 13. Offene Entscheidungen für Robert

Neun Fragen. Die ersten drei sind Produktentscheidungen, der Rest ist Umfang.

1. **Soll „vollwertig" wörtlich gelten?** Wenn ja, werden Baugruppen und
   Zeichnungsableitung wieder aufgemacht — beide sind am 13.08.2026 abgelehnt.
   Wenn nein, ist §8 eine Prüfliste und keine Arbeitsliste, und die vier Stufen
   aus §12 sind die Antwort.
2. **Zeichnungsableitung: ja oder nein?** Technisch billiger als gedacht
   (`HLRBRep_PolyAlgo` trägt auch Netze). Produktfrage: braucht ein Maker, der
   vor dem Slicer steht, ein bemaßtes Blatt?
3. **Baugruppen: ja oder nein?** Der teuerste Punkt des Papiers. Ohne 3D-Löser
   keine lebenden Bedingungen, und einen zulässigen gibt es nicht zu kaufen.
4. **Stufe 1 sofort?** Sie ist klein, wirkt überall, und der Fehler geht heute
   in die gefährliche Richtung. Eine eigene Serie oder an RM-042 angehängt.
5. **Wie weit geht Stufe 3?** Vier Operationen, zehn, oder alle 48
   Bausteine?
6. **Stufe 4 als Nachbau statt als Flächenrückgewinnung — einverstanden?**
   Das ändert RM-022 im Kern: nicht mehr „Flächen nähen", sondern „Operationen
   erzeugen".
7. **Wie wird ein nachgebauter Körper in der Provenienz geführt?** Er ist
   nicht mehr die Kundendatei, sondern eine Auslegung davon. §32 und
   `scene/foreign.py` müssen das ausweisen.
8. **Torus und Gewinde: bekommen sie Operationen, oder verschwinden sie aus
   dem Baum?** Null Handlungen an einem sichtbaren Merkmal ist die schlechteste
   der beiden Möglichkeiten (RM-128).
9. **`FEATURE_LIMIT_COUNT` = 1000**: Ein Lochblech mit mehr Merkmalen verliert
   bei jedem Schritt alle Kennungen. Grenze anheben, oder den Fall benennen?

---

## 14. Was dieses Papier über sich selbst sagt

Zwei seiner eigenen Befunde waren beim Schreiben schon einmal falsch:

- Der Nähweg galt als widerlegt; er ist es weiterhin, aber die Zahl, mit der
  er widerlegt wurde, war zur Hälfte ein Messartefakt (§6.1). Wer eine
  Ablehnung erbt, sollte ihre Messung nachfahren, bevor er sie weiterreicht.
- Die Merkmalserkennung galt als der starke Teil. Sie ist es — und sie misst
  bei grober Facettierung einen halben Millimeter daneben, in die Richtung, in
  der eine Passung klemmt (§7). Ein Verfahren, das an 35 Korpusdateien grün
  ist, ist an *diesen* 35 grün.

Und die Warnung, die diese Sammlung sich selbst erteilt hat, gilt auch für
diese Datei: Was hier als offen steht, steht das über den 17.09.2026. Wer es
später liest, misst am Code nach, bevor er es glaubt.
