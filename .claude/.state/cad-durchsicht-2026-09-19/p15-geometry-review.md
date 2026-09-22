# P1.5 – drei erste Gegenfälle für Geometrie und Semantik

## Umfang und Stand

Lesender Entwurf während des P1.4-Entwicklungstors. Grundlage sind
`p15-entry-plan.md`, das Paket P1.5 in
`konzepte/konzept-vollwertiges-cad-2026-09.md`, Recherche §§3/5.4 sowie die
geltenden Bereichskarten und Wahrnehmungsregeln. Es wurden **keine Tests,
Sonden oder Geometrieberechnungen ausgeführt**. Die folgenden Sollwerte sind
analytisch hergeleitet; erwartete Unterschiede der Endausgabe sind erst durch
die vorgeschlagenen Tests zu bestätigen. Keine Produktdatei wurde geändert.

Die drei Körper unten prüfen verschiedene Fachregeln. Ein gemeinsamer
`Feature`-/`SurfacePatch`-Vertrag besteht schon. Er muss diese Regeln tragen;
ein weiterer Erkenner oder eine zweite Sammlung semantischer IDs ist nicht
nötig. Gruppenumfang und Unsicherheit bleiben in `FeatureActionGroup` bzw.
der vorhandenen Beziehungsauskunft.

## Am aktuellen Code belegte Grenzen

1. **Mündungsfase:** `perceive.features._partial_cones_folded` nimmt
   Teilkegel an einer Langlochwand in deren Auswahl und Trägerliste auf.
   `brep.features._one_slot` vereinigt ausschließlich zwei Zylinderbögen und
   zwei ebene Flanken. `features_of` ruft danach keinen entsprechenden
   Fasenpass auf; native Teilkegel bleiben durch `_describe` eigenständige
   `cone` mit `partial=True`. Dies ist eine unterschiedliche semantische
   Behandlung derselben Nachbarschaft, nicht bloß ein anderer Fitweg.
   Im Mesh-Pass gewinnt bei mehreren benachbarten Slots außerdem die Zahl
   gemeinsamer Dreieckskanten, bei Gleichstand der Name. Das ist noch kein
   Beweis einer eindeutigen Zugehörigkeit und nicht unterteilungsinvariant.

2. **Teilzylinder:** `brep.features.FULL_TURN = 0.9` trennt am Umfang von
   324°; `perceive.features.FULL_TURN_SPAN = 300.0` trennt bei 300°.
   Native Kreiszylinder lesen dabei die Parametergrenzen des einzelnen
   Face, Mesh `span_about` die größte Winkellücke der wirklichen Ecken.
   Weder identische Schwellen noch identische Eingangsgrößen sind belegt.
   Ein 315°-Restmantel liegt gezielt zwischen diesen Regeln.
   `relations.cavity_chain_state_at` beschränkt sich zudem auf `hole` und
   `cone`. `_cavity_links` verbindet vollständig gemeinsame Randringe oder
   vollständige ebene Ringschultern. Die zwei offenen Schnittlinien zweier
   überlappender Mäntel sind kein solcher Ring. Ein fehlender Kettennachweis
   darf hier nicht als Beweis einer sicher einzelnen Höhlung dienen.

3. **Kleine Ebene:** Nativ verwirft `_describe` erst Flächen mit
   `area <= EPS_GEOM`. Mesh `_planar_face_entries` verlangt dagegen
   `area >= MIN_FACE_AREA` mit 4 mm², selbst bei bereits übergebenem
   Planaritätsnachweis und bei `all_facets=True`. Dadurch trifft die Grenze
   auch die lokale Rollenprüfung. `_large_facet_faces` hat zuvor schon
   Nachbarschaft und vollständige Rundträger berücksichtigt; dieser
   Nachweis kann die spätere harte Flächenschranke nicht überwinden.
   Zusätzlich publiziert `detect_faces` die Fläche mit `round(area, 4)`,
   während native Flächen ungerundet bleiben. Die Rundung im Sortierschlüssel
   hat einen anderen Zweck und muss dafür nicht entfernt werden.

Diese Punkte sind durch Lesen belegt. Insbesondere sind die genaue Anzahl
nativer Teilflächen und die finalen Namen der beiden Rundkörper noch keine
gemessenen Ergebnisse.

## 1. Durchgehendes Langloch mit vollständiger Mündungsfase

**Zweck:** Zusammensetzung aus Zylinder-, Kegel- und Ebenenanteilen;
angeschnittene Kegel behalten ihre Träger, aber werden nicht zu zwei
zusätzlichen angeblich eigenständigen Senkungen.

### Bestehender Bauweg

In `app/core/brep/edit.py` ausschließlich vorhandene Helfer verwenden:

1. `box(60, 30, 8)`; der Quader liegt bei z = 0…8.
2. `slot_bore(..., position=(0,0,4), direction=(0,0,1), diameter=6,
   depth=8, length=26, angle_deg=0, overlap=0)`.
3. Aus `edges_of` die inneren oberen Mündungskanten wählen:
   `abs(edge.middle[2] - 8) <= EPS_GEOM`,
   `abs(edge.middle[0]) < 20`, `abs(edge.middle[1]) < 10`.
   Mit `edge_key` und `chamfer(body, 1, "named", keys)` nur diesen Ring
   fasen. Die Ortsgrenzen wählen zwischen weit getrennten bekannten Kanten;
   sie sind keine neue Formtoleranz. Vor dem Fasen muss die Auswahl den
   vollständigen inneren Ring und keine äußere Plattenkante ergeben.
4. Derselbe fertige Solid geht an `features_of`; seine private Tessellation
   über `Solid.to_mesh(deflection=...)` geht an `detect`.

Vorhandene Vergleichsfälle:
`tests/test_features.py::_plate_with_a_chamfered_slot` und
`test_the_chamfer_at_a_slot_mouth_belongs_to_the_slot`,
`tests/test_surface_patches.py::test_merged_slot_chamfer_retains_its_true_apices_and_radian_half_angles`.
Ihr `buffer`-/Hüllenbau ist ein guter Verbraucherfall, **kein** unabhängiger
Beleg des ursprünglichen exakten Kegelwinkels. Dafür wird hier die echte
native 1-mm-Fase konstruiert. Der normale geschlossene Slot bleibt durch
`tests/test_brep.py::a_slotted_block` abgedeckt; dessen `overlap=0.1` darf
nicht in die neuen Sollmaße hineingelesen werden.

### Unabhängige Sollwerte

Achsenabstand der Halbkreise `L=20`, gerader Radius `r=3`. Die
Querschnittsfläche eines Stadions ist `A(r)=2 L r + π r²`.
Von z = 0…7 bleibt r = 3, von z = 7…8 gilt r(z) = z − 4.

- Freier enger Querschnitt: `120 + 9π` mm²; Mündung oben:
  `160 + 16π` mm².
- Abgezogenes Volumen:
  `7 A(3) + ∫[0,1] A(3+t) dt = 980 + 226π/3` mm³.
- Materialvolumen: `13420 − 226π/3` mm³.
- Gesamte Körperoberfläche:
  `5040 + 17π + √2 (40 + 7π)` mm².
- Zwei Halbzylindermäntel zusammen: `42π` mm²; zwei senkrechte
  Flanken zusammen: 280 mm².
- Beide Halbkegel zusammen: `7π√2` mm²; beide schrägen Fasenflanken
  zusammen: `40√2` mm².
- Kegelspitzen `(−10,0,4)` und `(10,0,4)`, gerichtete Achse +z,
  Halbwinkel π/4. Das volle Kegelmaß an z = 8 wäre Ø8; das enge
  Langlochmaß bleibt Ø6, Länge 26 und Weg 20.
- Zylindrischer Mantel: Tiefe 7, Mitte `(0,0,3.5)`; die Öffnung geht
  trotzdem durch. Wandtiefe 7 und Plattendicke 8 sind verschiedene Größen.

### Abnahme und kleinster Anschluss

Die zwei Kegelstücke müssen in beiden Erkennungswegen dieselbe Zugehörigkeit
zur Öffnung erhalten. Die angenommenen Träger mit zwei wirklichen Spitzen
bleiben erhalten; keine Mittelung und kein neuer Fit. Die Auswahl soll den
belegten Bearbeitungsumfang benennen. Gesondert prüfen, ob die zwei schrägen
ebenen Fasenflanken bereits mitgetragen werden: Der bestehende Test prüft
nur, dass **irgendein** geneigter Anteil im Slot liegt. Das beweist keine
vollständige Mündungsfase.

Der kleine gemeinsame Anschluss gehört an den vorhandenen
Zusammensetzungspass, nach der geometrischen Einzelerkennung. Eine
Nachbarentscheidung darf nicht allein aus Dreieckskantenzahl oder Name
entstehen. Zunächst ist dieser eindeutige Fall zu schließen; die allgemeine
Zuweisung eines Teilkegels zwischen konkurrierenden Öffnungen bleibt ohne
zusätzlichen Nachweis unsicher.

Die schon vorhandenen vollständigen Ring-/Schulterregeln bleiben unverändert
als Gegenkontrolle: `tests/test_counterbore_transitions.py::_shouldered_bore`
mit `test_a_flat_annular_shoulder_keeps_the_complete_cavity` sowie
`test_only_a_complete_flat_annulus_connects_the_sections`. Koaxialität allein
überbrückt weder eine gewölbte Schulter noch einen offenen Rand.

## 2. Zwei überlappende Bohrungen mit je 315° Restmantel

**Zweck:** Die unterschiedliche Umfangsregel gezielt treffen und wirkliche
Berührung von einem sicheren Einzelmerkmal unterscheiden. Die Form ist
absichtlich kein Stadion und hat keine seitliche Mündung in einer Ebene.

### Bestehender Bauweg

`edit.box(40,30,10)`, danach zweimal
`edit.cut_bore(..., position=(±d/2,0,5), direction=(0,0,1),
diameter=6, depth=10)` mit `d=6 cos(π/8)`.
Die zweite Differenz arbeitet auf dem Ergebnis der ersten.
Wie in `tests/test_geometry_review_regressions.py::bore_review_body` gehen
derselbe native Endkörper und seine Tessellation an die beiden Erkenner.
Keine erfundenen Feature-Dictionaries als Haupteingang.

Die vorhandenen echten Randöffnungen aus
`test_open_round_cut_and_open_slot_are_detected_slots` sind die positive
Gegenkontrolle: Dort enden die offenen Linien an einer freien Außenebene.
Hier grenzen sie an die andere Rundwand. Die dokumentierte Abfrage in
`slots.open_slots_instead_of_fillets` darf diesen Unterschied nicht verlieren.

### Unabhängige Sollwerte

Radius R = 3, halber Schnittwinkel α = π/8. Der ausgeschnittene Bogen
jedes Kreises hat 2α = 45°; der sichtbare Mantel je Träger hat
`2π − 2α = 7π/4 = 315°`.

- Gemeinsame Linsenfläche:
  `I = 2 R² α − (d/2) √(4 R² − d²) = 9π/4 − 9√2/2` mm².
- Vereinigte Luftfläche: `A = 2π R² − I = 63π/4 + 9√2/2` mm².
- Materialvolumen: `12000 − 315π/2 − 45√2` mm³.
- Gesamte Rundwandfläche: `2 · R · 10 · 7π/4 = 105π` mm².
- Gesamte Körperoberfläche: `3800 + 147π/2 − 9√2` mm².
- Zwei gemeinsame axiale Schnittlinien:
  `x=0`, `y=±3 sin(π/8)`, `z=0…10`.
- Zwei Trägerachsen `(±d/2,0,z)`, Radius 3, Materialseite nach innen;
  eine zusammenhängende Luftöffnung an Ober- und Unterseite, kein Boden.

Die Träger sind über ihre tatsächlichen Originalanteile zu vergleichen,
nicht über die Zahl von OCCT-Faces. Eine Naht kann einen Träger in mehrere
native Faces zerlegen. Sie ändert weder 315° Gesamtüberdeckung noch die zwei
wirklichen Schnittlinien.

### Abnahme und kleinster Anschluss

Zuerst die tatsächlichen Einzelergebnisse festhalten: Bei akzeptiertem
315°-Meshfit führt die heutige 300°-Regel in den vollen `hole`-Zweig;
ein natives Face mit 315° führt an 324° vorbei in den `fillet`-Zweig.
Die konkrete native Nahtzerlegung und Endzusammenfassung sind noch ungetestet.
Der Test darf diese Differenz nicht durch Änderung eines Sollwinkels umgehen.

Erforderlich ist eine gemeinsame Auskunft über den **belegten Teilmantel und
seine Öffnungs-/Nachbarschaftssituation**. Eine neue gemeinsame Zahl allein
wäre keine vollständige Lösung. Der endgültige Name kann daraus folgen;
eine vollständige, für sich sicher bewegliche Bohrung darf nicht allein aus
einem großen Winkel abgeleitet werden. Ebenso darf aus zwei Rundbögen ohne
gerade tangentiale Flanken kein Langloch werden.

`cavity_chain_state_at == (None, False)` ist hier ohne weiteren Beleg keine
Entwarnung: Die jetzige Funktion sieht weder alle möglichen Arten noch
offene Schnittlinien. Vorhandene Unsicherheits-/Handlungsauskunft wiederverwenden,
statt eine falsche Kette zu erfinden. Vollständiger Zusammenhang und sichere
Einzelbearbeitung sind getrennte Fragen. Die konkrete UI-/Operationsreaktion
prüft der parallele Verbraucherreview.

## 3. Ein echter 1-mm-Nocken auf einer großen ebenen Platte

**Zweck:** Echte kleine Ebenen ohne Rundfit, Kegelwinkel oder schmale
Boolesche Resthaut isolieren. Der Nachweis soll vor und nach Unterteilung
gelten; eine größere Umgebung darf die Ebene nicht verschwinden lassen.

### Bestehender Bauweg

`base=edit.box(40,30,4)` und
`post=edit.moved(edit.box(1,1,2),(0,0,3))`, dann
`edit.boolean("union", [base,post])`.
Die Körper überlappen in genau 1 mm³. Damit hängt der Bau nicht an einer
bloßen Berührung zweier Deckflächen. Nur der Abschnitt z = 4…5 steht außen.
Wieder native Erkennung und `detect` auf dessen Tessellation verwenden.

### Unabhängige Sollwerte

- Volumen: `40·30·4 + 1·1·2 − 1·1·1 = 4801` mm³.
- Oberfläche: Grundplatte `2(1200+160+120)=2960` mm²; verdeckte 1 mm²
  und neue Deckfläche 1 mm² heben sich auf, vier Seiten addieren 4 mm²:
  insgesamt **2964 mm²**.
- Elf zusammenhängende ebene Bereiche: Grundplattenboden 1200,
  Grundplattendecke 1199, je zwei Außenseiten 160 und 120,
  **fünf Nockenflächen je 1 mm²**.
- Kleine Flächenmitten: `(0,0,5)`, `(±0.5,0,4.5)`, `(0,±0.5,4.5)`;
  Normalen +z, ±x und ±y. Außenmaterial; keine innere Taschenrolle.

Die 1-mm²-Seiten liegen auch weit über dem bestehenden Breitenfilter
`MIN_SURFACE_WIDTH=0.2`: Für ein Quadrat ist `area/diagonal=1/√2` mm.
Der Fall isoliert somit die absolute Flächenschranke und benötigt keine
Lockerung des Schutzes gegen schmale Boolesche Streifen.

### Abnahme und kleinster Anschluss

Alle fünf kleinen Bereiche müssen mit genau ihren Originaldreiecken und
belegten Ebenenträgern auffindbar sein. Ganze Körperfläche, Normalen und
Rollen bleiben korrekt. Ein Wechsel von zwei zu vielen koplanaren Dreiecken
darf weder eine neue fachliche Ebene erzeugen noch eine vorhandene beseitigen.

**Die 4-mm²-Schranke nicht global absenken.** Ihr Anlass bleibt gültig:
`test_a_generated_mesh_does_not_drown_in_faces` schützt vor Hunderten
scheinbaren Ebenen auf einer organischen Figur;
`test_a_cylinder_has_three_faces_and_not_fifty` vor Mantelstreifen;
`test_a_coarse_prism_keeps_its_sides` schützt umgekehrt echte Polygonflächen.
Diese drei Gegenrichtungen sind gemeinsam erforderlich.

Kleinster fachlich vertretbarer Ausbau: den vorhandenen lokalen Nachweis
einer zusammenhängenden, an allen Ecken ebenen und gegen ihre Nachbarschaft
eigenständigen Fläche durch `_large_facet_faces` und
`_planar_face_entries` erhalten. Ein vollständiger akzeptierter Rundträger
darf seine Facetten weiterhin zurückfordern; bloße Planarität oder die Zahl
koplanarer Dreiecke genügt nicht. `surfaces.planar_patch` belegt nur den
Träger, nicht die Konstrukteursabsicht. Für den Nocken belegen die klaren
rechten Kanten und ebenen Nachbarbereiche die Eigenständigkeit. Die bisherige
Flächengröße kann eine vorsichtige automatische Auswahl ohne solchen lokalen
Beleg begrenzen; sie darf einen vorhandenen Beleg nicht pauschal löschen.

Eine vollständige neue allgemeine Klassifikationsregel ist damit noch nicht
bewiesen. Vor allem flache echte Fasen neben fein facettierten Freiformen
bleiben spätere Gegenfälle. Keine stillschweigende Annahme, dass jede kleine
Ebene ein bearbeitbares Einzelteil oder eine Schraubenauflage sei.

## Gemeinsamer Nachweisrahmen für diese drei Familien

- **Eigentum zuerst:** Ausgangs-Solidbytes und Mesharrays sichern;
  Erkennung und Nachfrage verändern weder Quelle noch Originalzuordnung.
  Native Gültigkeit, geschlossener Körper und ein Materialkörper sind
  Vorbedingungen der Sollvolumen, keine Ersatzprüfung der Merkmale.
- **Neu tessellieren und unterteilen getrennt:** unterschiedliche bestehende
  Deflektionsstufen über `Solid.to_mesh(deflection=...)`; daneben reine
  gleichmäßige und örtliche Unterteilung derselben Dreiecke. Letztere muss
  dieselbe Haut erhalten und darf insbesondere Randkantenzahlen nicht in
  neue semantische Zugehörigkeit verwandeln. Keine Leistungsprüfung.
- **Maße nicht vermischen:** Die Formeln oben sind native analytische
  Größen. Das neue Mesh ist bei Rundflächen eine andere, facettierte Haut.
  Dessen tatsächliche Fläche/Volumen dürfen nicht mit einem großzügigen
  Gleichheitsfehler zur Kreisform erklärt werden. Enge Fitmaße, tatsächliche
  Facettenmaße und die vorhandene Abweichungsauskunft getrennt prüfen.
  Die rein ebene Nockenform hat diese Rundungsabweichung nicht.
- **Auswahl vollständig prüfen:** Zuordnung nach analytischem Träger und
  geometrischem Bereich, kein Vergleich zufälliger `face_N`-Nummern;
  `SurfacePatch.face_indices` müssen Teil der aktuellen Featureauswahl
  bleiben. Bei jeder Vereinigung sowohl übernommene als auch zu Unrecht
  verschluckte Flächen prüfen. Native Quellen behalten Vorrang, ein über
  Tessellation gemessener Slotwert bleibt `fit`.
- **Transformation und Abbruch:** Starre Drehung, Translation und Spiegelung
  führen Punkte, Richtungen und Materialseite korrekt weiter. Der vorhandene
  Callback muss bis in Nachbarschaft und Zusammenfassung reichen; keine
  halb veröffentlichte Gruppe nach Abbruch.
- **Kleine Testintegration:** Erst bestehende Familien in
  `test_brep.py`, `test_features.py`, `test_surface_patches.py` und
  `test_geometry_review_regressions.py` erweitern; Beziehungsnachweise in
  `test_counterbore_transitions.py`/`test_relations.py` wiederverwenden.
  Kein zusätzlicher großer Harness. Fensterdateien und Leistungsdateien
  bleiben ausschließlich Release-Abnahme.

Priorität: Nocken als isolierter Nachweis der Flächengrenze, dann die
eindeutige Langlochfase, danach die 315°-Überlappung mit gemeinsamer
Unsicherheitsantwort. Dieses Blatt bereitet den ersten P1.5-Schnitt vor;
es erklärt weder P1.5 noch die vollständige zusammengesetzte Erkennung für
abgeschlossen.
