# Was Solidon zu einem vollwertigen CAD fehlt

> **Stand 17.09.2026 — Befunde, Entscheidungen und vollständiger Umsetzungsplan.
> Sechzehn Entscheidungen sind an diesem Tag von Robert getroffen (§14); im Code
> ist nichts davon gebaut.** Alle Zahlen sind an diesem Tag am HEAD gemessen; wo
> eine Zahl aus einem anderen Dokument stammt, steht die Quelle daneben.
>
> **Der Plan ist als Ganzes gedacht** (Entscheidung Robert, 17.09.2026: *„alles
> sollte im Konzept stehen, damit wir das Konzept auf einmal abarbeiten
> können"*). Er beginnt **nach der Veröffentlichung von 0.4.3** — bis dahin wird
> nichts davon angefasst.
>
> **Zweite Fassung.** Die erste vom selben Tag wurde adversarial gegengeprüft;
> vier ihrer Aussagen hielten nicht. Was daraus wurde, steht in §16 — nicht als
> Fußnote, sondern weil drei der vier Korrekturen die Empfehlung verändert haben.

Anlass ist Roberts Frage vom 17.09.2026: *„was fehlt uns, um es zu einem
vollwertigen 3D-CAD-Programm zu machen, ohne CAD-Erfahrung und alles möglichst
einfach, und STL die Merkmale und alles sauber zu erkennen."* Dazu am selben
Tag seine Entscheidung, die dieses Papier trägt:

> **„Exakt oder Netz sollte immer gleich bearbeitbar und erkennbar sein."**

Sie schließt an den 10.09.2026 an („alles soll immer bearbeitbar sein, egal ob
importiert, Format egal") und macht aus einer Sammlung von Einzellücken eine
Richtung: **Parität.**

---

## 1. Die Frage sind drei Fragen, und zwei ziehen gegeneinander

1. **Vollwertig** heißt: was ein CAD kann, kann Solidon auch.
2. **Ohne CAD-Erfahrung, möglichst einfach** heißt: der Kunde soll *nicht*
   lernen, was ein CAD verlangt. Shapr3D braucht drei bis fünf Tage, Fusion 400
   bis 1200 Stunden, Tinkercad liefert das erste Modell unter einer Stunde
   ([konzept-einfache-bedienung-2026-09.md](konzept-einfache-bedienung-2026-09.md) §2).
   Jede Fähigkeit aus Frage 1 kostet hier.
3. **STL-Merkmale sauber erkennen** — die einzige Frage, die **beide** anderen
   bedient, und die einzige, in der Solidon im Markt vorn steht
   ([konzept-wettbewerb-2026-08.md](konzept-wettbewerb-2026-08.md) Teil 2.3).

Roberts Paritätssatz löst den Widerspruch zwischen 1 und 2 auf eine Weise, die
keine der drei Fragen einzeln gelöst hätte: **Wenn beide Körperarten dasselbe
können, verschwindet die teuerste Vokabel des Programms aus der Bedienung.**
Der Kunde muss nicht mehr wissen, was er hat — und das ist mehr wert als jede
einzelne neue Funktion.

---

## 2. Der Bestand, gezählt

| | Zahl |
|---|---|
| Registrierte Operationen | **132** in 15 belegten Kategorien, **alle rücknehmbar** |
| Bausteine | **35** in 6 Gruppen (AGENTS.md nennt noch 27 — veraltet) |
| Merkmalsarten am Netz | **12** (`FeatureKind`, `app/core/types.py:51`) |
| Zwangsbedingungen im Skizzenlöser | **15** im Kern, 16 Namen in der Oberfläche |
| Zeilen `geom` / `perceive` / `sketch` / `brep` / `ui` | 33 927 / 12 869 / 5 610 / 4 494 / 105 268 |
| Zeilen Tests | 262 482 in 305 Dateien |

Der Skizzenlöser ist kein Provisorium: `scipy.optimize.least_squares` mit
`trf`/`lsmr`, analytische Jacobi-Zeile je Bedingung, dünn besetzt, eigener
Zugmodus. Gemessen **200 Bedingungen in 55,1 ms** gegen ein Budget von 100 ms.
Splines gibt es, im exakten Kern als interpolierende B-Spline mit exaktem
Flächenintegral.

**Das ist kein Programm, dem CAD-Grundlagen fehlen.** Die Antwort auf „was
fehlt" ist deshalb keine Funktionsliste.

---

## 3. Die Kernaussage: eine Einbahnstraße, zwei blinde Flecken

Nach der Gegenprüfung steht die Lage anders da als in der ersten Fassung. Drei
Befunde tragen alles Weitere, und alle drei sind gemessen:

**A — Die Einbahnstraße.** Von 132 Operationen halten **20** einen exakten
Körper exakt, **3** verlangen ihn, **56** machen aus ihm ein Netz. Von diesen 56
haben genau **zwei** einen exakten Zwilling; **54 haben keinen Ausweg.** Der
Weg zurück existiert nicht — `brep_to_mesh` ist die einzige benannte Tür, und
sie führt nur hinaus.

**B — Der exakte Kern ist blind, wo das Netz sieht.** Dieselbe Geometrie,
beide Bauarten, gemessen:

| Geometrie | exakter Kern | Netz |
|---|---|---|
| Quader + Bohrung | 6 `face`, 1 `hole` | identisch |
| Quader + Verrundung R3 | 6 `face`, **20 `fillet`** (r exakt 3,0) | 6 `face`, 1 `curved_face` |
| Zylinder + Fase | 1 `pin` Ø20,0, 2 `cone` | 1 `pin` Ø**19,9567**, 2 `curved_face` |
| Torus | **{} — nichts** | 1 `torus` |
| Gewinde | **7 `pin` Ø8,16** (falsch) | 1 `thread` Ø10,0, Steigung 1,5 |
| Hohlraum | 12 `face` | 6 `face`, 1 `void` |

Zwei Richtungen, nicht eine: Bei Verrundung und Fase ist der exakte Kern
**reicher und genauer**, bei Torus, Gewinde und Hohlraum **ärmer oder falsch**.

Dazu eine Eigenart, die die Auswertung betrifft: **Der exakte Körper trägt nur,
was die Operation selbst hineingeschrieben hat.** `features_of` wird von den
Operationen gerufen, nie von der Auswertung — ein `Solid` hat keine Dreiecke,
an denen die Erkennung messen könnte. Bei einer **starren** Bewegung zieht
`_carried_along` die Merkmale seit dem 17.09.2026 mit (Commit `5ad173de6`; vorher
stand nach 30° um X die Deckfläche weiter mit Normale (0,0,1) bei z = 10, und
ein Zapfen darauf kam unter dem Bett heraus). Was bleibt, ist gemessen und
klein: **`mirror_object` gibt einen exakten Körper mit null Merkmalen zurück** —
als einzige der sechzehn geprüften exakten Operationen.

**C — Die Erkennung misst systematisch zu klein.** Das ist der Befund mit der
größten Breitenwirkung, und er ist bis auf die Ursache durchgemessen (§4).

---

## 4. Die Erkennung misst die Facettierung, nicht die Geometrie

### 4.1 Die Ursache, bewiesen

`fit_cylinder`, `fit_cone`, `fit_sphere` und `fit_torus` passen ihren Kreis
über `body.triangles_center` ein — die **Dreiecksschwerpunkte**. Die liegen
bauartbedingt innerhalb des Vielecks, und zwar um genau

```
gemessen = wahr · √(5 + 4·cos(2π/n)) / 3
```

Diese Formel trifft zwei unabhängige Korpusfälle auf **vier Nachkommastellen
exakt**: `torus_ring` Ringdurchmesser 39,9239 (Soll 40, 48 Segmente) und
`plate_holes` Bohrung 5,1901 (Soll 5,2, 48 Facetten). Das ist keine
Korrelation, das ist die Ursache.

### 4.2 Die Wirkung

| Soll Ø | Facetten | gemessen | Abweichung |
|---:|---:|---:|---:|
| 5,2 | 16 | 5,1113 | −0,0887 |
| 5,2 | 24 | 5,1605 | −0,0395 |
| 5,2 | 48 | 5,1901 | −0,0099 |
| 15,0 | 16 | 14,7441 | −0,2559 |
| 30,0 | 16 | 29,4882 | **−0,5118** |
| 30,0 | 24 | 29,7720 | −0,2280 |

Der Fehler ist **einseitig** — immer zu klein — und wächst mit dem Durchmesser.
Unter 16 Facetten wird gar nichts mehr erkannt, ohne dass ein Satz sagt, warum.

**Wo er nicht schadet:** Ein Übernehmen im Dialog ohne Änderung schrumpft
nichts. Gemessen an vier Fällen: Volumen vorher gleich Volumen nachher, ±0,00.
`resize_hole` nimmt einen absoluten Zieldurchmesser.

**Wo er schadet:** bei allem, was auf dem gemessenen Maß *aufbaut*.
`app/core/scene/fits.py:307` rechnet das Passungsspiel als Differenz **zweier
gemessener** Durchmesser. Bei gleicher Facettierung hebt sich der Fehler auf
(−0,007 mm), bei ungleicher nicht — und ungleich ist der Normalfall:
importiertes Teil gegen selbst konstruiertes.

| Ø Loch | n Loch | Ø Zapfen | n Zapfen | echtes Spiel | gemessenes | Fehler |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 48 | 19,6 | 48 | 0,400 | 0,399 | −0,001 |
| 20 | 16 | 19,6 | 48 | 0,400 | 0,096 | −0,304 |
| 30 | 16 | 29,6 | 64 | 0,400 | **−0,080** | **−0,480** |

Die letzte Zeile heißt: Die Prüfung meldet eine Überschneidung, wo die Teile
mit 0,4 mm Luft sitzen. Eine Spielpassung im Druck liegt bei 0,2 bis 0,4 mm —
der Fehler ist größer als die Sache, die er messen soll.

*Zur Belastbarkeit dieser Tabelle:* Sie ist aus der Formel gerechnet, und die
Formel ist an **sechs** unabhängigen Fällen bestätigt — `plate_holes`,
`torus_ring`, sowie Loch und Zapfen bei 16, 24 und 48 Facetten. Dabei zeigt
sich zusätzlich, dass **Zapfen und Loch identisch verzerrt werden** (Ø 12,
16 Facetten: beide 11,7953): Das ist genau die Voraussetzung dafür, dass sich
der Fehler bei gleicher Facettierung aufhebt und bei ungleicher nicht. Was
noch aussteht, ist der Lauf über `fits.check` selbst; er gehört in die Abnahme
von Stufe 1.

### 4.3 Der Fix — der bessere Weg steht schon im Haus

Den Kreis über die **Hüllecken der projizierten Ecken** einpassen statt über
die Schwerpunkte. Im selben Modul gibt es das Verfahren bereits: die Einpassung
für runde Wände nimmt die konvexe Hülle der Ecken, vereinfacht sie mit der
Schweißtoleranz und passt darauf ein — es wird nur nicht überall genommen.

**Warum die Hülle und nicht einfach die Ecken:** Die Ecken des Vielecks liegen
auf der gemeinten Fläche, die Punkte einer **Unterteilung** aber nicht — die
sitzen auf den Sehnen und ziehen den Fit nach innen. Aus der Hülle fallen sie
heraus. Gemessen an einem Loch Ø 40:

| Facetten | Unterteilung | Schwerpunkte (heute) | alle Ecken | **Hüllecken** |
|---:|---:|---:|---:|---:|
| 16 | keine | 19,6588 | 20,0000 | **20,0000** |
| 16 | einfach | 19,7232 | 19,8088 | **19,9416** |
| 16 | zweifach | 19,7393 | 19,7607 | **19,9482** |
| 48 | zweifach | 19,9709 | 19,9732 | **19,9966** |

Die Hülle ist in jedem der neun Fälle die beste der drei — und ohne
Unterteilung, dem Regelfall eines exportierten STL, trifft sie exakt.

Gemessen, als Plugin eingespielt, ohne eine Projektdatei anzufassen:

| Prüfung | Ergebnis |
|---|---|
| Ø 5,2 bei 16 / 24 / 48 Facetten | **5,2000 / 5,2000 / 5,2000** |
| mit 0,02 mm Rauschen | max. Abweichung 0,0048 mm |
| Testkosten (372 Tests der Erkennungsfamilie) | **370 bestanden, 3 gefallen** |

**Zwei der drei gefallenen Tests halten Schwächen fest, die der Fix beseitigt.**
Der eine heißt `test_the_residual_cannot_see_a_blown_up_circle`; der andere
trägt im Docstring wörtlich: *„Die Zylindereinpassung rechnet über die
Schwerpunkte und findet einen tadellosen Zylinder — Rückstand 0,0000 — an einem
Kegel mit 31 Grad."* Die Schwäche ist also **bekannt und umgangen**, nicht
unentdeckt: Solidon zieht daraus die richtige Konsequenz, dass die Form die
Normalen entscheiden und nicht der Rückstand. Nie gemessen wurde ihre Wirkung
auf das **Maß**. Mit den Ecken kann ein Kegel gar nicht mehr als Zylinder
durchgehen — der Fix behebt beides.

**Der dritte ist ein echter Konflikt, und er ist neu.** Der
`CYLINDER_SPREAD`-Umbau vom 17.09.2026 hat
`test_a_coarsely_facetted_bore_survives_a_dense_triangulation` mitgebracht, der
`spread < 0,5` verlangt. Der Eckenfit liefert dort **0,5000005** — keine
Haaresbreite, sondern der theoretische Wert: Liegt der Kreis auf dem Umkreis,
ist die mittlere Abweichung der Schwerpunkte davon genau die halbe Sehnenhöhe.
Daraus folgt für die Umsetzung: **`CYLINDER_SPREAD` und die Schranken um sie
herum sind auf den Schwerpunktfit geeicht und müssen mitgezogen werden.** Sie
sind gerade erst neu kalibriert worden; das zweite Mal gehört in denselben
Schritt wie der Fit selbst, nicht danach.

### 4.4 Der Praxisbeleg

Am echten Kundenmodell (Filament-Rack, 22 148 Dreiecke, 100 Merkmale mit
Durchmesser). Konstruierte Teile tragen runde Maße; wie oft eines getroffen
wird, ist deshalb das ehrlichste Gütemaß:

| | trifft ein 0,5-mm-Maß auf 0,02 mm genau |
|---|---|
| heute | **13 von 103** |
| mit dem Fix | **67 von 100** |

Mittlerer Abstand zum 0,5-mm-Raster: 0,074 → 0,040 mm. Nebenbei werden zwei
Ringe als `torus` erkannt statt als `fillet` — auch die Formentscheidung wird
sauberer.

### 4.5 Zwei Verwandte desselben Fehlers

- **`CYLINDER_SPREAD` war an der Facettenbreite normiert — behoben am
  17.09.2026** (Commit `9c54ee1de`). Nachgemessen: `plate_holes.stl` behält
  seine vier Bohrungen auch bei 815 104 Dreiecken. Der Befund steht hier
  weiter, weil er dieselbe Ursache hat wie §4.1 und weil die Reihe zeigt, wie
  eine Schranke stumpf wird, ohne rot zu werden. Wie es war: Eine feinere
  Vernetzung halbiert die Breite, ohne die Polygonnäherung zu ändern; der Wert
  verdoppelt sich und reißt die Schranke. Gemessen: dieselbe Platte,
  203 776 Dreiecke → 4 Bohrungen; 815 104 Dreiecke → **keine**. Bei der feineren
  Stufe gelten alle Dreiecke als eben.
- **Was ich zuerst vorschlug, war falsch.** „Größter Abstand zur Achse" trifft
  ohne Rauschen exakt und liegt bei 0,1 mm Rauschen **+0,32 mm** daneben. Ein
  Maximum ist bei verrauschten Netzen der schlechteste Schätzer. Die Ecken sind
  der richtige Punktsatz, nicht der äußerste Punkt.

---

## 5. Die Einbahnstraße, im Detail

Gemessen über `kind_of(produced.mesh)` — derselbe Vergleich, den
`app/core/scene/evaluate.py:586` zieht.

**20 Operationen halten den exakten Körper:** `chamfer_edges`,
`check_join_path`, `delete_object`, `draft_faces`, `duplicate_object`,
`fillet_edges`, `intersect_objects`, `mirror_object`, `pattern`, `place_on_bed`,
`push_face`, `resize_hole`, `rotate_object`, `set_material`, `sketch_pocket`,
`slot_hole`, `slots_from_texture`, `subtract_objects`, `translate_object`,
`union_objects`.

**56 machen ein Netz daraus.** Nach Kategorie: 31 Bausteine (`insert_*`),
7 `holes`, 7 `mesh`, 3 `prepare`, 2 `transform`, 2 `colour`, 4 einzeln.

Drei davon sind keine Kernfrage, sondern Versehen:

- **Skalieren ist der einzige Transform, der den Körper zerstört.**
  Verschieben, Drehen und Spiegeln bleiben exakt; `scale_object` und
  `fit_to_size` nicht. In OCCT ist beides trivial — gemessen: `gp_Trsf.SetScale`
  (Quader 10³ × 2 → 8000,0) und `gp_GTrsf` für ungleichförmig (2/1/0,5 → 1000,0).
- **Zwei von drei Filamentoperationen fällen den Körper nebenbei.**
  `slots_from_texture` bleibt exakt; `assign_slot` und `paint_slot` machen ein
  Netz — bei **unverändertem Volumen**. Sie färben nur.
- **Die Merkmalshandlungen sind gespalten.** `resize_hole` und `slot_hole`
  bleiben exakt, `move_feature`, `rotate_feature`, `duplicate_feature`,
  `remove_feature`, `plug_hole` und `countersink_hole` nicht — obwohl
  `app/core/brep/edit.py` mit `fill_bore`, `cut_bore`, `resize_bore` und
  `slot_bore` das Werkzeug bereits hat.

### 5.1 Wo der Kunde es merkt

Ein Kundenweg von sechs Schritten, Bauart nach jedem gemessen:

| Schritt | Operation | Bauart | STEP-Ausgabe |
|---|---|---|---|
| 1 Quader anlegen | `create_brep_box` | brep | ok |
| 2 Bohren | `drill_brep_hole` | brep | ok |
| 3 Verrunden R3 | `fillet_edges` | brep | ok |
| 4 Aushöhlen | `shell_exact` | brep | ok |
| 5 **Einpressbuchse einsetzen** | `insert_heatset_m4` | **mesh** | **abgelehnt** |
| 6 Senken | `countersink_hole` | mesh | abgelehnt |

Er kippt beim Einsetzen eines Bausteins — der häufigsten Geste nach dem Bohren.
Steht das Senken an dritter Stelle, kippt er schon dort: **Bohren hat einen
exakten Zwilling, Senken hat keinen.** Wer die Bohrung exakt setzt und sie dann
senkt, verliert in Schritt drei, was Schritt zwei ihm zugesagt hat.

Drei Beobachtungen zur Meldung an dieser Stelle:

1. **Derselbe Satz für zwei verschiedene Sachen.** Ein Katalogeintrag bedient
   `brep.converted` (der Kunde hat *Flächenbearbeitung beenden* geklickt) und
   `evaluate.exact_became_mesh` (es ist ihm passiert). Beim ersten stimmt der
   Hinweis „Rückgängig stellt den exakten Körper wieder her" — beim zweiten
   nimmt Undo die Buchse **mit**.
2. **Die Schwere ist `info`, die Folge ist `error`.** Die STEP-Ausgabe lehnt
   einen Schritt später mit `error` ab. Die einzige Stelle, an der der Kunde
   die Einbahnstraße noch umgehen könnte, spricht leiser als die, an der es zu
   spät ist.
3. **Die Meldung nennt die Operation nicht.** In `values["op"]` steht
   `insert_heatset_m4`; im Text steht sie nicht. Bei sechs Schritten kommt
   „irgendwann wurde es ein Netz" an.

---

## 6. Die Skizze findet den Körper nicht

**Der Befund hält, die Ursache ist kleiner als gedacht.** *Projizieren*
(`sketch/edit.py:476`) ist ein Ebenenschnitt. Auf der Fläche, auf der man
zeichnet, schneidet die Ebene nichts — **sechs von sechs** Flächen von
`plate_holes.stl` enden mit *„Diese Ebene schneidet den Körper nicht."*

Zwei Dinge, die die Gegenprüfung ergänzt hat:

- **Der Rand ist ein Tausendstel Millimeter.** Bei `z = 3,999` statt `4,0`
  liefert derselbe Aufruf 392 Elemente einschließlich aller Bohrungskonturen.
  *Projizieren* ist nicht kaputt — es hat einen Rand, den niemand verschoben hat.
- **Deshalb ist „scheitert" nicht das schärfste Argument.** Wer die Ebene um
  `EPS_GEOM` ins Material schiebt, bekommt für einen prismatischen Körper die
  richtige Kontur — und für eine angezogene oder verrundete Flanke eine leicht
  **falsche**. Das ist der Grund, die Flächenkontur selbst zu nehmen
  (`perceive/relations.boundary_rings` liefert sie am Netz bereits).

**Alles kommt als Strecke an**: 392 Elemente, ausnahmslos `kind="line"`,
kürzeste 0,17 mm — auch am exakten Körper, weil `Solid.raw` die Tessellierung
liefert. Dass es anders ginge, ist gemessen: ein exakter Quader mit Bohrung
trägt `{GeomAbs_Line: 26, GeomAbs_Circle: 4}`.

### 6.1 Bezugsebenen — „es gibt keine Ebene ohne Körper"

Die erste Fassung schrieb „Bezugsebenen gibt es gar nicht". Das war zu grob.
Gemessen:

- `planes.frame_of(normal, origin)` nimmt **freie Normale und freien
  Ursprung**. Eine gekippte Skizzenebene ist erreichbar; was fehlt, ist ihre
  Benennung — `feature:<obj>:<face>` ist eine Referenz, kein Ort.
- Der **Hilfskörper-Umweg funktioniert vollständig**: dünne Platte bei z=30
  erzeugen, darauf zeichnen, hochziehen, Platte löschen — der Zapfen bleibt
  millimetergenau (Volumen 628,3185 = π·5²·8 exakt).
- `sketch_pocket.z` ist eine Versatzebene für genau eine Operation — aber
  absolut gegen den Weltnullpunkt, nicht gegen eine Fläche.
- `up_to`/`height_to` gibt es nur für `sketch_extrude`. Solidon hat damit die
  **zweite** Hälfte: das Ende ist referenzierbar, der Anfang nicht.

Richtig ist deshalb: **Es gibt keine Ebene ohne Körper.** Man muss Material
erzeugen, um eine Ebene zu bekommen. Das kostet zwei Schritte im Verlauf, einen
Zwischenzustand, in dem die Hilfsplatte im Exportplan steht, **keine
Assoziativität** und einen Verlauf, in dem „Quader anlegen" steht, wo
„Bezugsebene 20 mm über der Deckfläche" gemeint war.

Am Bedienweg gezählt: **vier Klicks und eine Zahl** mit einer Versatzebene
gegen **neun Klicks und zwei Körper im Verlauf** über den Hilfsquader — und
danach steckt der Abstand in der Höhe eines gelöschten Quaders, ist also kein
änderbares Maß mehr.

---

## 7. Was „vollwertig" sonst verlangt

| Fähigkeit | Stand | Lage |
|---|---|---|
| Versatz-, Dreipunkt- und Neigungsebene | fehlt als benannte Sache | **Bauplanänderung** — §30.1 nennt nur Hauptebene und Fläche |
| Flächenkontur und Kanten als Skizzenelemente | fehlt (nur Ebenenschnitt, nur Strecken) | frei |
| Fillet mit variablem Radius, Flächen-Flächen-Fillet | fehlt | frei |
| Chamfer Distanz-Distanz und Distanz-Winkel | fehlt | frei |
| Shell mit gewählten Öffnungen, Draft mit gewählten Flächen | fehlt | frei |
| Revolve-Cut, Sweep-Cut, Loft-Cut, „im selben Schritt vereinigen" | fehlt | frei |
| Loft über mehr als zwei Schnitte, Sweep mit Twist | fehlt | frei |
| Muster und Spiegelung **als Merkmal im Körper** | fehlt (nur getrennte Objekte) | frei |
| Merkmalsarten Tasche, Nut, Rippe, Kante, Fase, Symmetrie, Lochmuster | fehlt | frei |
| `torus`, `thread`, `void`, Freiform im **exakten** Kern | fehlt (`_describe` → `None`) | frei, §12 beziffert es |
| STEP-Baugruppenstruktur (XCAF: Namen, Farben, Baum) | fehlt | frei |
| Verlauf: einfügen, umsortieren, zurückspulen, stummschalten | fehlt (nur ändern und löschen) | frei |
| Mesh → exakte Geometrie | fehlt | **RM-022 offen** |
| Baugruppen mit Hierarchie, Instanzen, lebenden Bedingungen | fehlt | **ausgeschlossen** (Robert, 17.09.2026 — §14 Nr. 1) |
| Zeichnungsableitung mit Bemaßung | fehlt | **ausgeschlossen** am selben Tag, obwohl Bauplan §18.3 Bemaßung zusagt |
| Ellipse, Tangente Bogen-an-Bogen | fehlt | frei, klein |

### 7.1 Zeichnungsableitung — billig für exakte Körper, teuer für Netze

Die erste Fassung hatte es andersherum. Gemessen an `plate_holes.stl`:

```
HLR Draufsicht:  3,7 ms  ->  196 sichtbare Kanten, 192 davon kürzer als 1 mm
```

Eine Zeichnung dieser Platte braucht **8** Elemente: 4 Randlinien und 4 Kreise.
Die 196 gehen exakt auf — 4 + 4 × 48 Facetten. Am exakten Körper dagegen:

```
HLRBRep_Algo     (exakt): 5 Kanten, {Line: 4, Circle: 1}   <- eine Zeichnung
HLRBRep_PolyAlgo (Netz): 30 Kanten, {Line: 30}             <- ein Polygonzug
```

Dazu skaliert das Bauen der OCCT-Form aus einem Netz überlinear: 796 Dreiecke
0,14 s, 12 736 Dreiecke 3,59 s — hochgerechnet **rund eine Minute** für ein
übliches 200 000-Dreieck-STL. Und die Kantenzahl verdoppelt sich mit jeder
Verfeinerung: ein feineres Netz gibt eine schlechtere Zeichnung. Derselbe
Fehler wie in §4 — gemessen wird die Facettierung.

**Eine Zeichnungsableitung ist damit eine Fähigkeit des exakten Kerns.** Am
Netz bräuchte sie die Merkmalserkennung als zweite Quelle, denn aus einem
48-Eck liest niemand einen Durchmesser ab.

---

## 8. Der Rückweg: das Erkannte wird wieder Konstruktion

### 8.1 Der naive Nähweg ist tot — aus einem anderen Grund als notiert

[konzept-flaechenrueckgewinnung-2026-08.md](konzept-flaechenrueckgewinnung-2026-08.md)
verwarf ihn mit „108 Dreiecke → 108 Flächen, 324 Kanten". Die Messung stimmt,
aber `ShapeUpgrade_UnifySameDomain` wurde damals nicht gefahren:

| Datei | genäht | nach Unify | Flächenarten |
|---|---|---|---|
| `block_with_rounded_edge.stl` | 108 Flächen / 324 Kanten | **30 / 168** | alle `GeomAbs_Plane` |
| `plate_holes.stl` | 796 / 2388 | **198 / 1176** | alle `GeomAbs_Plane` |

Der Befund dreht sich: **Ebene Facetten zusammenzufassen kann OpenCASCADE
allein.** Was es nicht kann, ist die Rundung zum Zylinder zu machen — alle
Flächen bleiben eben. Der Flaschenhals ist ausschließlich das Ersetzen der
gekrümmten Bänder durch analytische Flächen, und genau deren Parameter liefert
die Erkennung.

### 8.2 Der bessere Weg: nachbauen statt nähen — und was er nicht kann

Statt Flächen zusammenzusetzen, den Körper als **Folge registrierter
Operationen** nachbauen: Grundform, Bohrungen, Senkungen, Verrundungen. Was
entsteht, ist kein exakter Körper, sondern eine **Konstruktion mit Verlauf**.

**Wo er trägt** (Volumen gegen das Netz, gemessen): `plate_holes` 0,00 %,
`plate_holes_twin` 0,00 %, `plate_countersunk` −0,10 %, `plate_coarse_slots`
−0,04 %, `openscad_ascii` 0,02 %, `cube_clean` 0,00 %.

**Wo er bricht — und hier muss die erste Fassung widerrufen werden:**

| Datei | Netz | Nachbau | Abweichung | erkannte Merkmale |
|---|---:|---:|---:|---|
| `bridge_two_end_supports.ply` | 396 | 1296 | **+227 %** | `{face: 10}` |
| `island_tower.stl` | 4 500 | 9 000 | **+100 %** | `{face: 10}` |
| `clean_figure.stl` | 20 871 | 54 404 | **+161 %** | `{pin: 4, sphere: 1, face: 10}` |
| `post_with_fillet.stl` | 25 072 | 129 600 | **+417 %** | `{pin: 1, torus: 1, face: 7}` |

Die ersten beiden sind wasserdicht, eine Komponente, Euler 2, 100 %
achsparallele Flächen, **100 % Merkmalsdeckung, kein unerklärtes Merkmal** —
topologisch nicht von einem Vollquader zu unterscheiden. **Die Zusage „was
nicht trägt, sagt die Anwendung vorher" ist damit nicht haltbar.** Ein
Vorab-Gate ist möglich, tauscht aber falsche Ablehnungen gegen falsche
Annahmen: Es verwirft `block_with_rounded_edge` und `openscad_ascii`, deren
Nachbau auf 0,2 % genau ist, und lässt `broken_selfint` durch, der 37 % daneben
liegt. **Die einzige belastbare Probe ist der Volumenvergleich nach dem Bauen.**

Drei weitere Korrekturen:

- **Die Grundform steht nicht in den Flächen.** Bei
  `block_with_rounded_edge.stl` sind nur zwei der sechs Flächen unversehrt; die
  Form 40×30×20 entsteht erst aus dem **Schnitt der Stützebenen**. Das ist ein
  eigener Rechenschritt, den die erste Fassung nicht nannte.
- **`pin` ist mehrdeutig.** In `post_with_fillet` ist `pin_1` ein *aufgesetztes*
  Merkmal, in `dense_cylinder` ist `pin_1` der *ganze Körper*. Nichts in den
  Parametern unterscheidet das — und genau das ist die Frage „wie erkennt man
  die Grundform".
- **„Prismatisch" ist die falsche Grenze.** `torus_ring` → ein `create_torus`,
  `dense_cylinder` → ein `create_cylinder`, `sphere_socket` → Quader minus
  Kugel. Drei trivial nachbaubare Körper, die „prismatisch" aussortieren würde.
  Richtig ist: **ein erkanntes Grundvolumen plus erklärte Abzüge, deren Summe
  das Netz trifft.**

Und: `post_with_fillet` scheitert **nicht an „organisch"**. Die Erkennung
liefert alles — Grundplatte, Kopffläche π·6², Zapfen Ø12×30, Hohlkehle
Ø18/Ø6. Es fehlen drei Operationen: Torus hat keine, kein Weg setzt einen
Zapfen auf einen Körper, und es gibt kein Flächen-Flächen-Fillet.

### 8.3 Die Werkzeuge liegen im Paket

`GeomAPI_IntSS` (Schnittkurve zweier Flächen — „die schwere Stelle" des alten
Konzepts), `BRepBuilderAPI_Sewing`, `ShapeFix_Shape`, `ShapeFix_Solid`,
`BRepOffsetAPI_MakeFilling`, `GeomAPI_PointsToBSplineSurface`, `HLRBRep_Algo`.
Alle in der gepinnten Bindung vorhanden. **Keine neue Abhängigkeit, keine
Lizenzfrage** — Regel 22 wird nicht berührt.

---

## 9. Die Oberfläche, am laufenden Fenster gemessen

Fünf Wege durchs echte Fenster gefahren (`build_application`, offscreen, ein
Prozess je Block). **Ein Vorbehalt vorweg:** offscreen ist `viewport.renderer`
leer — was im Bild passiert, ist damit nicht gemessen; die Zahlen gelten dem
Dialog- und Panelanteil.

### 9.1 Die Klickzahlen

| Weg | Klicks | Bemerkung |
|---|---:|---|
| Quader + Bohrung + Verrundung, neu konstruiert | **13** | einer davon nur, um die Gruppe *Ändern* aufzuklappen |
| Skizze auf einer Fläche bis zum Körper | **6** | der beste der fünf Wege |
| Fremde STL laden, Bohrung ändern, exportieren | ~9 | Import 1,26 s |

**Der Skizzenweg ist der einzige, an dem ein Laie nicht scheitert.** Die
Statuszeile beantwortet beide Fragen zusammen und übersetzt sie:
*„Geschlossen · Bestimmt — nichts wackelt mehr (alle Freiheitsgrade vergeben).
Daraus wird ein Körper, und die Form kann nicht mehr wackeln."* Offene Umrisse
sperren *Hochziehen* mit Grund, nach *Fertig* erklärt sich das gesperrte Feld
*Grundform* selbst.

### 9.2 Die erste konstruktive Handlung ist unsichtbar

Die Menüleiste hat **fünf** Menüs, und keines heißt *Ändern*. **63 der 132
Operationen** stehen in `PANEL_CATEGORIES` und damit ausschließlich rechts in
der Auswahlkarte — die erst erscheint, wenn etwas gewählt ist. Die Gruppe
*Ändern* hat 29 Einträge und **startet zugeklappt** (`OPEN_UP_TO=12`).

Gezählt: **43 Operationen sind weder im Menü noch auf einem Kürzel noch als
Katalogkachel noch als Werkzeugknopf zu finden.** Darunter *Verrunden*, *Fase
anbringen*, *Aushöhlen*, *Glätten*, *Bohrung ändern*, *Senken*. Es bleiben zwei
Wege: die Auswahlkarte (mit passender Auswahl, Gruppe zugeklappt) und die
Befehlspalette auf Strg+Umschalt+P. **Ein Laie kennt das Kürzel nicht und hat
noch nichts ausgewählt — für ihn gibt es diese 43 nicht.**

Dass die Operationen dort wohnen, ist eine Entscheidung (Robert, 11.09.2026).
Neu ist die Zahl — und dass die erste konstruktive Handlung eines leeren
Projekts damit hinter einer Auswahl und einer zugeklappten Gruppe liegt.

### 9.3 Zwei Befunde, die zur Paritätsfrage gehören

**Das Vorschauband schweigt, wenn eine Operation den exakten Körper fällt.**
Gemessen an einem exakten Quader mit *Wulst anlegen*:

| Ort | was der Kunde sieht |
|---|---|
| Vorschauband im Dialog | nur „Vorschau — noch nicht übernommen" — **kein Wort davon, was gleich passiert** |
| Statuszeile danach | leer |
| Prüfbericht | `0 × Fehler · 0 × Warnung · 2 × Hinweis`; der Reiter springt erst ab `warning` |
| Baumzeile | `· weiter bearbeitbar` **verschwindet** — die einzige sichtbare Änderung, und sie ist ein Wegfall |

Der Kunde hakt *Flächen und Kanten später bearbeiten* an, setzt einen Wulst und
verliert genau die Eigenschaft, für die er den Haken gesetzt hat. Der Befund
ist gebaut, getestet und trägt den richtigen Satz — **er kommt nur nach der
Entscheidung und als `info`.** Das ist die Bedienseite der Einbahnstraße
aus §5.

**Die Baumzeile kennzeichnet nur den exakten Körper.** `· weiter bearbeitbar`
steht am `Solid`; ein Netz trägt im Zeilentext **gar nichts**, nur im Tooltip.
Nach einem STL-Import steht damit keine Aussage über die Bauart da — der
Unterschied ist nur erkennbar, wenn man vorher einmal einen exakten Körper
gesehen hat.

### 9.4 Das Merkmalfenster ist der neue Engpass

Der Umbau vom 11.09. hat die *Handlungen* erfolgreich entdoppelt — statt vier
bis fünf Stellen zeigen heute drei dieselbe Bohrung, und nur mit der
Überschrift. Dafür steht jetzt an einer gewählten Bohrung:

- **36 sichtbare Eingabefelder**, fünf Handlungsblöcke untereinander,
- „X" / „Y" / „Z" **je viermal** als Beschriftung, mit vier verschiedenen
  Bedeutungen,
- **ein** *Übernehmen*, das beim ersten Hinsehen auf *Merkmal verschieben*
  scharf ist (die erste in `ACTION_ORDER`), nicht auf *Bohrung ändern*. Erst
  der Fokus im Feld schaltet um — gemessen am wechselnden Tooltip.

Wer ein Loch aufbohren will, sieht eine Wand aus Zahlen und muss erst das
richtige Feld anfassen, damit der Knopf das Richtige meint.

**Und ein Merkmal ohne Handlung antwortet gar nicht.** Am Torus steht
Überschrift und Maß, zwei Knöpfe (*Baustein einsetzen*, *Vor Trennnähten
schützen*) — **kein Satz, kein Übernehmen, leere Statuszeile.** Dass keine
Handlungsknöpfe dastehen, ist entschieden (07.09.2026); **dass an ihrer Stelle
nichts steht, ist es nicht.** Für einen Laien ist das die Lage „ich habe das
Richtige angeklickt und die App antwortet nicht".

### 9.5 Drei Obergrenzen sind voll

| Grenze | heute | max |
|---|---:|---:|
| Zeilen im Datei-Menü | **12** | 12 |
| Felder auf der Vorderseite (5 Operationen) | **8** | 8 |
| Werkzeuge in der Zeile | **7** | 8 |
| Menüs in der Leiste | 5 | 9 |
| Offene Gruppe *Vorbereiten* | 11 | 12 |

**Der nächste Dateieintrag und das nächste Vorderseitenfeld dieser fünf
Operationen reißen das Tor.** Das ist keine Warnung für später — es ist die
Randbedingung jedes Vorschlags in diesem Papier.

### 9.6 Vier kleine Funde aus derselben Fahrt

- **Ein Positions-Dreier zerfällt über die Klappe.** Bei *Bohrung setzen* am
  Quader stehen vorn *Durchmesser* und *Position Z*, hinten *Position X* und
  *Position Y*. „Position Z" ohne X und Y ist eine sinnlose Zeile, und die
  Stelle, die der Kunde braucht, liegt hinter „Weitere Einstellungen". Derselbe
  Fall, den die Durchsicht vom 14.09. für *Normale/Achse* bereits behoben hat —
  eine Feldgruppe weiter links.
- **„Die Zuweisung betrifft 1 gewählte Körper."** Der Körper-Zweig hat keine
  Einzahlform, der Flächen-Zweig daneben hat eine. Der Satz steht im
  Vorgabezustand nach jedem Import; im Englischen wird „affects 1 selected
  bodies" daraus.
- **Grau ohne Auskunft.** *Jetzt trennen* und *Linie löschen* stehen gesperrt
  **ohne Tooltip, ohne `statusTip`, ohne zugängliche Beschreibung**; der Grund
  steht in einem Geschwister-Label. Regel 18 will die zweite Kodierung am
  Bedienelement. Der vorhandene Test prüft nur die sieben Umschalter, nicht
  deren Knöpfe.
- **Leere Skizze, *Fertig* — wortlos.** Kein Dialog, keine Statuszeile. Daneben
  sagen *Hochziehen* und *Abtragen* korrekt „Erst einen geschlossenen Umriss
  zeichnen." Das Verhalten ist entschieden und getestet; der Satz fehlt, den
  [konzept-einfache-bedienung-2026-09.md](konzept-einfache-bedienung-2026-09.md) §2.1
  ausdrücklich verlangt.

---

## 10. Einfachheit ist eine Reihenfolge, kein Weglassen

Die Grenzen stehen als Test (`tests/test_interface_limits.py`): neun Menüs,
zwölf Zeilen je Menü, acht Werkzeuge, **acht Felder auf der Vorderseite**, ein
Menüeintrag je Operation. Die Regel dazu ist entschieden (P15 E11/E14): eine
Operation je Handlung, nicht je Variante — und alles ist **da**, nicht alles
ist **vorn**.

Angewendet:

- **Die Versatzebene wird kein Menüeintrag**, sondern ein zweites Feld in der
  Ebenenzeile des Skizzeneditors, das nur erscheint, wenn die Wahl eine Fläche
  ist: `Zeichenebene: [Fläche an Halter ▾]  Abstand: [ 0,00 mm ]`. Vier Klicks.
- **Revolve-Cut wird kein zweiter Eintrag**, sondern ein Feld im Dialog.
- **Der Nachbau ist kein Werkzeug**, sondern eine Zeile im Prüfbericht:
  *„Dieses Modell lässt sich nachbauen — danach sind seine Maße änderbar."*
  Drei Klicks bis zum Ergebnis, gegen über dreißig beim Nachmessen und
  Neuzeichnen. Trägt die Erkennung nicht, steht die Zeile nicht da.
- **Die Radiuskorrektur aus §4 ist gar keine Bedienung.** Eine Zeile im Fitter,
  die überall wirkt, ohne dass jemand etwas lernt — bessere Vorgabe statt
  zusätzlicher Einstellmöglichkeit (§2.4).

### 10.1 Die Zwillings-Haken fallen — Folge aus Roberts Entscheidung

Gemessen:

| Paar | Parameter Netz / exakt | Unterschied |
|---|---|---|
| `create_box` / `create_brep_box` | 12 / 11 | genau einer: `anchor` |
| `create_cylinder` / `create_brep_cylinder` | gleich | — |
| `drill_hole` / `drill_brep_hole` | 17 / 17 | **keiner** |
| `hollow_object` / `shell_exact` | 5 / 1 | `open_top`, `open_at`, `vents` |

Die ersten drei Haken stellen nach dem 17.09. eine Frage mit nur einer
sinnvollen Antwort — bei *Bohrung setzen* sogar ein Feld, das nichts anbietet,
worüber man entscheiden könnte. Der vierte ist kein Kernwahl-Haken, sondern die
**Folge** aus zwei Feldern, die der Kunde ohnehin ausfüllt: *Oben öffnen* oder
Entlüftungen > 0 → Netzweg, sonst exakt.

**`MENU_TWINS` bleibt** (es trägt Menüzusammenlegung, Palette und
`change_kernel`); der sichtbare Haken fällt. Gewinn: *Quader anlegen* verliert
ein Feld auf der Vorderseite, *Bohrung setzen* eine wirkungslose Zeile, zwei
Sätze fallen aus sechs Sprachkatalogen.

Was an die Stelle tritt, hängt an der **Handlung** statt am Körper: ein Satz am
Feld, wenn er zutrifft („Der Bogen entsteht hier als Folge gerader Stücke; die
Abweichung bleibt unter 0,02 mm"), **Schweigen**, solange die Abweichung unter
einer Schichthöhe bleibt, und ein Befund mit Knopf dort, wo wirklich etwas
endet — beim STEP-Export, mit *[Diese Schritte exakt rechnen]* als Handlung
statt als Vorabfrage.

---

## 11. Bibliotheken

**Für keinen Punkt dieses Papiers wird eine neue Abhängigkeit gebraucht.**

| Kandidat | Lizenz | Urteil |
|---|---|---|
| **OCP 8.0.1** (im Paket) | Apache-2.0 / LGPL-2.1 mit OCCT-Ausnahme | trägt §8.3 und die Zeichnungsableitung vollständig |
| **`planegcs`** 0.8.0 (FreeCADs 2D-Löser) | LGPL-2.1-or-later, nach `licences.toml` zulässig | **nicht einsetzbar**: Räder nur cp312/cp313, nur `win_amd64` und `manylinux x86-64`. Solidon fährt CPython 3.14.7 und liefert macOS |
| **`py-slvs`** (SolveSpace) | **GPL-3.0-or-later** | ausgeschlossen durch Regel 15 |
| **Ansatz** (Rust) | MIT | 7 Commits, keine Python-Bindung, 2D-Bedingungen ausdrücklich nicht umgesetzt |
| **Analysis Situs** | **BSD-3-Clause** | C++, nicht einbaubar — aber das **Verfahren** ist frei: ein attributierter Nachbarschaftsgraph (Flächen als Knoten, Kanten als konvex/konkav/glatt) ist der Weg zu Tasche, Nut und Rippe, und er passt auf beide Kerne |
| `pyransac3d`, `PrimitivesFittingLib` | MIT/BSD | lösen, was Solidon schon gelöst hat |
| Point2CAD, CAD-Recode, CADFit | Forschung | lernende Rekonstruktion; widerspricht Leitprinzip 7 und §42. Als Wissensquelle nützlich, nicht als Baustein |
| `mesh2cad` | MIT | dieselbe Idee wie §8.2, als Beleg brauchbar |

**Solidon braucht `planegcs` nicht.** Der eigene Löser ist mit 15
Bedingungsarten und 55 ms auf 200 Bedingungen der besseren Lösung näher als
eine Bindung, die auf der Zielplattform nicht läuft.

---

## 12. Was die Parität kostet — Posten für Posten

Aus der Messung in §3 B und §5, nach Aufwand sortiert.

| Posten | Umfang | Aufwand |
|---|---|---|
| `scale_object`, `fit_to_size` exakt | `gp_Trsf.SetScale` / `gp_GTrsf`, beide gemessen | **0,5 Tage** |
| `assign_slot`, `paint_slot` halten den Körper | färben nur; Volumen ist unverändert | **0,5 Tage** |
| `void` im exakten Kern | `BRepClass3d.OuterShell_s` gegen die Schalen — exakt, ohne Einpassung | **0,5 Tage** |
| `torus` im exakten Kern | `GeomAbs_Torus` → `surface.Torus()` liest beide Radien ab | **0,5 Tage** |
| `mirror_object` gibt die Merkmale weiter | als einzige der sechzehn geprüften exakten Operationen liefert sie null | **0,5 Tage** |
| `countersink_hole`, `plug_hole` exakt | `edit.fill_bore`/`cut_bore` existieren | **2 Tage** |
| `move/rotate/duplicate/remove_feature` exakt | dieselben Werkzeuge | **3 Tage** |
| Freiformflächen als `curved_face` im exakten Kern | Sammelzweig für 6 durchfallende `GeomAbs_*`-Typen | **1 Tag** |
| `thread` im exakten Kern | kein `GeomAbs_Helix`. Der billige Weg wäre, dass `thread_exact` sein Gewinde beim Bauen benennt (Provenienz, §24.1) — **Robert hat den vollständigen gewählt**: die Steigung an der BSpline messen, damit auch eingelesene Gewinde erkannt werden | **5 bis 7 Tage**, und es ist ein neues Verfahren, kein Zweig |
| *Gegenstück anlegen* am Gewinde | `counterpart.py` steht; offen ist „wohin" | **2 Tage** |
| Torus und Gewinde bekommen Handlungen | `torus` in `PARAMETRIC_KINDS`, Operation *Gewinde ändern* | **4 Tage** |
| **31 Bausteine exakt** | der große Brocken: Bausteine bauen Netze, und an ihnen kippt der Kundenweg | **eigene Bauaufgabe** |

Die ersten fünf Posten sind zusammen **zweieinhalb Tage** und beseitigen die
auffälligsten Paritätsbrüche. Die sieben `mesh`-Operationen (`decimate_mesh`,
`remesh_*`, `smooth_mesh`, `sculpt_strokes`, `subdivide_surface`,
`pose_armature`) sind **kein** Paritätsbruch — sie erzeugen definitionsgemäß
Netze und gehören nicht auf diese Liste.

**Der teuerste Einzelposten ist das Gewinde**, und das ist eine bewusste Wahl:
Der billige Weg hätte nur selbst gebaute Gewinde benannt. Eingelesene STEP-Teile
mit Gewinde — der Fall, in dem ein Kunde ein fremdes Modell anpasst — wären
weiter als sieben falsche Zapfen erschienen.

---

## 13. Der Umsetzungsplan

**Beginn nach der Veröffentlichung von 0.4.3**, deren Vorbereitung am
17.09.2026 begonnen hat. Sechs Stufen, 0 bis 5, in dieser Reihenfolge; die
Abhängigkeiten stehen am Ende des Kapitels. Jede Stufe lässt nach ihrem letzten
Schritt ein grünes Tor zu, jede hat ein Kriterium, das rot werden kann.

**Zwei Punkte sind schon vor dem Beginn erledigt**, beide am 17.09.2026 und
beide aus Befunden dieses Papiers: `CYLINDER_SPREAD` (Stufe 1, Punkt 5) und die
Merkmale eines gedrehten exakten Körpers (Stufe 2, Punkt 5). Sie stehen mit
Commit-Kennung an ihrer Stelle, damit später nachvollziehbar bleibt, was der
Plan umfasste und was schon davor fiel.

**Der Umfang insgesamt:** rund 60 Arbeitstage für die Stufen 0 bis 3, dazu zwei
Posten, die eine eigene Vorlage brauchen, bevor sie einen Aufwand haben — die
31 Bausteine (Stufe 2e) und der Nachbau (Stufe 4).

**Warum diese Reihenfolge:** Stufe 1 muss vor Stufe 4 — ein Nachbau, der gegen
eine Toleranz geprüft wird, die den eigenen Messfehler enthält, prüft sich
selbst. Stufe 0 steht vorn, weil sie am billigsten ist und der Kunde sie sofort
sieht. Stufe 2 vor Stufe 3, weil die Skizze auf einer Bezugsebene an einem
Körper hängt, der bis dahin exakt bleiben soll.

---

### Stufe 0 — Sechs Bedienfunde, gebündelt

Kein Kern, ein Torlauf. Sie hängen an keiner anderen Stufe.

1. **Der Positions-Dreier zerfällt über die Klappe.** Bei *Bohrung setzen*
   stehen vorn *Durchmesser* und *Position Z*, hinten *Position X* und
   *Position Y*. Ein Dreier bleibt zusammen, auf welcher Seite auch immer —
   derselbe Fall, den die Durchsicht vom 14.09. für *Normale/Achse* eine
   Feldgruppe weiter links bereits behoben hat.
2. **„Die Zuweisung betrifft 1 gewählte Körper."** Der Körper-Zweig hat keine
   Einzahlform, der Flächen-Zweig daneben hat eine. Sechs Kataloge.
3. **Gesperrte Knöpfe ohne Auskunft** (*Jetzt trennen*, *Linie löschen*):
   Tooltip, `statusTip` und zugängliche Beschreibung an den Knopf, nicht an das
   Nachbarlabel. Regel 18.
4. **Leere Skizze, *Fertig* — wortlos.** Ein Satz, den §2.1 der
   Bedienungsdurchsicht ohnehin verlangt.
5. **Das Vorschauband sagt vorher**, wenn eine Operation die exakten Flächen
   kostet — und nur dann. Heute steht dort nur „Vorschau — noch nicht
   übernommen", und der Befund kommt danach als `info`.
6. **Die Baumzeile benennt beide Bauarten oder keine.** Heute trägt nur der
   exakte Körper `· weiter bearbeitbar`; ein Netz trägt im Zeilentext nichts.

**Abnahme:** Wer *Flächen und Kanten später bearbeiten* gewählt hat, liest
**vor** der Übernahme, dass der nächste Schritt sie kostet. Die vier übrigen
Funde je als Test.
**Aufwand:** 2 Tage mit Torlauf.

---

### Stufe 1 — Die Erkennung misst, was gemeint war

1. Kreisfit in `fit_cylinder` über die **Hüllecken der projizierten Ecken**
   statt über die Schwerpunkte — mit `hull.simplify(tolerance)` wie in der
   Einpassung für runde Wände, damit Sehnenpunkte aus einer Unterteilung
   herausfallen.
2. Dasselbe in `fit_cone`, `fit_sphere`, `fit_torus`.
3. **Die Schwellen im selben Schritt neu kalibrieren.** `CYLINDER_SPREAD` und
   die Schranken um sie herum sind auf den Schwerpunktfit geeicht; mit dem
   Umkreis liegt die mittlere Abweichung systematisch bei der halben
   Sehnenhöhe. Gemessen: `spread` springt von 0,167 auf 0,500 — das ist der
   theoretische Wert, kein Ausreißer. Wer den Fit ändert und die Schranke nicht,
   verliert Merkmale.
4. Die drei Tests nachziehen: zwei halten behobene Schwächen fest
   (`test_the_residual_cannot_see_a_blown_up_circle`,
   `test_the_normals_decide_the_shape_and_not_the_residual`), der dritte
   (`test_a_coarsely_facetted_bore_survives_a_dense_triangulation`) trägt die
   Schranke aus Punkt 3.
5. ~~`CYLINDER_SPREAD` von der Facettenbreite lösen.~~ **Erledigt am
   17.09.2026** (`9c54ee1de`): `_chord_sag` misst die Sehnenhöhe aus
   Winkelschritt und Facettenbreite, beides über den Median, beides
   unterteilungsfest. Nachgemessen — `plate_holes.stl` behält seine vier
   Bohrungen bis 815 104 Dreiecke.
6. Unter 16 Facetten benennen, warum nichts erkannt wurde.
7. **`FEATURE_LIMIT_COUNT` anheben und die Zuordnung beschleunigen.** Die
   Grenze von 1000 ist heute nötig, weil `match` quadratisch wächst (gemessen:
   2000 Merkmale = 39,97 s). Mit räumlicher Vorsortierung fällt der Grund weg.
   Die neue Grenze wird **gemessen**, nicht geraten.

**Abnahme:** Ø 5,2 wird bei 16, 24, 32 und 48 Facetten auf besser als 0,01 mm
gemessen (heute bis 0,51 mm). `plate_holes.stl` behält seine vier Bohrungen bei
jeder Unterteilung bis 3,2 Mio. Dreiecke. Die Passungsprüfung aus §4.2 wird am
**laufenden** Weg über `fits.check` gemessen, nicht gerechnet. Ein Lochblech
mit über 1000 Merkmalen behält seine Kennungen über einen Schritt hinweg, und
die Zuordnung bleibt im Budget. Alles als Testdatei.

**Aufwand:** 3 Tage für 1–4 und 6, plus 3 bis 4 Tage für Punkt 7. Punkt 5 ist
erledigt.
**Risiko:** gering und gemessen — am Stand nach dem `CYLINDER_SPREAD`-Umbau
bleiben **370 von 373** Tests der Erkennungsfamilie grün. Zwei der drei
gefallenen halten Schwächen fest, die der Fix beseitigt; der dritte ist die
Schranke aus Punkt 3.

---

### Stufe 2 — Parität: beide Körperarten können dasselbe

Die größte Stufe, und die, die Roberts Entscheidung einlöst.

**2a — Die fünf Kleinposten (2,5 Tage)**

1. `scale_object` und `fit_to_size` exakt — `gp_Trsf.SetScale` gleichförmig,
   `gp_GTrsf` ungleichförmig; beide gemessen (Quader 10³ × 2 → 8000,0).
2. `assign_slot` und `paint_slot` halten den Körper — sie färben nur, das
   Volumen ist ohnehin unverändert.
3. `void` im exakten Kern: `BRepClass3d.OuterShell_s` gegen die Schalen aus
   `TopExp_Explorer`. Exakt, ohne Toleranz, ohne Einpassung.
4. `torus` im exakten Kern: `GeomAbs_Torus` → `surface.Torus()` liest beide
   Radien ab.
5. **`mirror_object` gibt die Merkmale weiter.** Der große Teil dieses Punktes
   ist am 17.09.2026 erledigt (`5ad173de6`): Bei einer starren Bewegung zieht
   `_carried_along` die Merkmale mit, statt sie liegen zu lassen — der
   Drehfehler ist damit weg. Was die Gegenmessung danach noch fand: Von
   sechzehn exakten Operationen liefert **`mirror_object` als einzige null
   Merkmale**.

**2b — Die Merkmalshandlungen exakt (5 Tage)**

6. `countersink_hole` und `plug_hole` exakt — `edit.fill_bore` und `cut_bore`
   existieren.
7. `move_feature`, `rotate_feature`, `duplicate_feature`, `remove_feature`
   exakt, mit denselben Werkzeugen.

**2c — Freiform und Gewinde im exakten Kern (6 bis 8 Tage)**

8. **Die sechs durchfallenden Flächentypen werden `curved_face`** — dieselbe
   Art, derselbe Name, dieselben zwei Operationen wie am Netz. Ein aus STEP
   geladener Freiformkörper hat danach etwas Anklickbares. *(Entscheidung
   Robert: wie am Netz, nicht als eigene genauere Art — die Parität wörtlich.)*
9. **Gewinde: die Steigung an der BSpline messen.** Der vollständige Weg, der
   auch **eingelesene** Gewinde erkennt, nicht nur selbst gebaute. Damit fallen
   zugleich die sieben falschen `pin`, die eine Wendel heute erzeugt.
   *(Entscheidung Robert gegen den billigen Weg über die Provenienz.)*

**2d — Torus und Gewinde bekommen Handlungen (4 Tage)**

10. `torus` in `PARAMETRIC_KINDS`, `_feature_solid` baut den Ringkörper. Damit
    gelten *Ändern* (Ring-Ø und Schnur-Ø), *Verschieben*, *Verdoppeln* und
    *Entfernen* **ohne eine neue Operation**. *Drehen* bleibt abgelehnt, mit
    Satz: „Ein Ring um seine eigene Achse gedreht ist derselbe Ring."
11. Eine Operation *Gewinde ändern* — Größe aus der Normteiltabelle vorn,
    Steigung hinter der Klappe. Innen und außen ist ein Eintrag, die Richtung
    steht im Merkmal.
12. `plug_hole` nimmt `thread`; `paint_slot` und `clear_filament` nehmen beide
    Arten — sie brauchen Dreiecke, keine Ebene.
13. ***Gegenstück anlegen* am erkannten Gewinde** (`counterpart.py` steht,
    verlangt heute zwei markierte Stellen). Am Gewinde ist die eine Stelle
    gewählt; zu beantworten bleibt „wohin".

**2e — Die 31 Bausteine exakt (eigene Bauaufgabe)**

14. Bausteine bauen heute Netze. Damit kippt der Kundenweg an der häufigsten
    Geste nach dem Bohren. Der Weg ist je Baustein derselbe: den Werkzeugkörper
    exakt bauen und die Boolesche über den exakten Kern führen, statt
    `as_mesh_data` zu rufen.

**2f — Die Bedienseite (2 Tage)**

15. **Alle vier Zwillings-Haken fallen.** Exakt wird die Vorgabe, wo der Kern da
    ist; `anchor` lernt der exakte Quader. Bei *Aushöhlen* folgt der Kern aus
    den Feldern: *Oben öffnen* oder Entlüftungen > 0 → Netzweg, sonst exakt.
    `MENU_TWINS` bleibt (es trägt Menü, Palette und `change_kernel`), nur der
    sichtbare Haken geht.
16. Die Meldung `evaluate.exact_became_mesh` bekommt einen eigenen Text, der
    die **Operation nennt** und den richtigen Rückweg beschreibt; die Schwere
    wird an die Folge angeglichen. Heute teilt sie sich einen Katalogeintrag
    mit `brep.converted`, und nur dort stimmt der Undo-Hinweis.

**Abnahme der ganzen Stufe:** Der Sechs-Schritte-Weg aus §5.1 endet als exakter
Körper und exportiert als STEP — heute kippt er in Schritt 5. Dieselbe
Geometrie liefert in beiden Bauarten dieselben Merkmalsarten (die Tabelle in
§3 B wird zum Test). Ein gedrehter B-Rep-Körper trägt die gedrehte
Flächennormale. Ein eingelesenes STEP mit Freiformflächen hat anklickbare
Merkmale. Ein Torus und ein Gewinde bieten Handlungen an. Und: *Quader anlegen*
hat ein Feld weniger auf der Vorderseite, wo die Grenze heute 8/8 voll ist.

**Aufwand:** 20 bis 24 Tage ohne 2e; 2e ist eine eigene Bauaufgabe über 31
Bausteine.

---

### Stufe 3 — Die Skizze findet den Körper

1. **Das Prädikat trennen, ohne Verhaltensänderung.** `is_feature_plane` bleibt,
   daneben entsteht „braucht einen gerechneten Rahmen"; die zwölf Stellen
   werden umgestellt. **Alle Tests bleiben grün** — und dieser Schritt macht
   alle folgenden billig.
2. Kennung und Parser für die drei Ebenenarten, `_known_plane` streng geprüft
   (endliche Zahlen, Grenzen, keine entarteten Punkttripel), Rundreise durch
   die Projektdatei. **Kein Formatsprung** — der Wertebereich einer vorhandenen
   Zeichenkette wächst, das Dateischema nicht (Präzedenzfall
   `sketch/CLAUDE.md:80`).
3. `frame_for_plane` kennt die neuen Arten. Damit rechnen Kern, `field_ops`,
   `seal_ops` und *Projizieren* sofort richtig, ohne dass eine Bezugsebene
   entstehen könnte.
4. **Stabilität:** `orphans` trägt die Parameter mit (`_rewrite` baut die
   Kennung heute neu — genau dort ginge der Abstand verloren),
   `evaluate._with_nested_context` nimmt den Träger in den Cache-Schlüssel.
   Verschwindet die Bezugsfläche, wird **einmal** gefragt, und *Ebene an dieser
   Stelle festhalten* schreibt die zuletzt gerechnete Lage fest — mit dem Satz,
   dass sie dem Körper nicht mehr folgt.
5. **Oberfläche: ein Eintrag „Neue Ebene …" im Ebenenfeld, mit Art-Auswahl**
   (Versatz, drei Punkte, geneigt). *(Entscheidung Robert gegen drei getrennte
   Einträge — näher an „eine Operation je Handlung", Preis ist ein Klick und
   ein Oberbegriff.)* Dazu die Ebenenvorschau im Bild: Rechteck mit
   Rasterlinien, Beschriftung „5,00 mm über Oberseite" — Farbe **und** Text.
6. **Alle drei Ebenenarten**, da die Art-Auswahl sie ohnehin zusammenfasst. Die
   Dreipunktebene in der ersten Stufe über Weltkoordinaten, mit ausdrücklichem
   Befund „diese Ebene folgt dem Körper nicht"; assoziative Punkte sind eine
   eigene Frage. Die geneigte Ebene hängt an `edge_key` — der ist für beide
   Kerne schon derselbe, braucht aber einen zweiten Verweistyp in `orphans`.
7. **Flächenkontur übernehmen** als eigene Handlung neben *Projizieren*:
   `relations.boundary_rings` am Netz, Drahtzug der Fläche am exakten Körper.
   Nicht die Ebene um `EPS_GEOM` verschieben — das gäbe an einer angezogenen
   Flanke eine leicht falsche Kontur.
8. **Kreise bleiben Kreise:** am exakten Körper über `BRepAdaptor_Curve`
   (`GeomAbs_Circle` liefert Mitte, Achse, Radius), am Netz **aus dem erkannten
   Merkmal** — nicht aus den Punkten zurückgerechnet.
9. **Bauplan §30.1 erweitern**, mit Ansage, zusammen mit den sechs Sätzen, die
   RM-175 dort ohnehin nachträgt.

**Abnahme:** Auf jeder der sechs Flächen von `plate_holes.stl` liefert *Kontur
übernehmen* die Kontur dieser Fläche (heute: sechs von sechs scheitern). Eine
Bohrungskante kommt als **ein** Kreis an, nicht als 24 Strecken. Eine Skizze
5 mm über einer Fläche erzeugt den Körper an der richtigen Stelle, auf beiden
Kernen, und das Sollvolumen ist analytisch gerechnet, nicht aus dem Prüfling
genommen. Verschwindet die Bezugsfläche, bleibt der Abstand nach der Antwort
erhalten. Zweimal auswerten gibt identische Ergebnisse.

**Aufwand:** rund 19,5 Tage für alle drei Ebenenarten, plus 6 Tage für Kontur
und Kreise, plus 2 Tage für den exakten Ebenenschnitt über
`BRepAlgoAPI_Section`.

---

### Stufe 4 — Das Erkannte wird Konstruktion

1. **Grundform aus dem Schnitt der Stützebenen rechnen** — eigener Schritt. Die
   Flächenausdehnungen genügen nicht: bei `block_with_rounded_edge.stl` sind
   nur zwei der sechs Flächen unversehrt.
2. Die Mehrdeutigkeit von `pin` auflösen — in `post_with_fillet` ist es ein
   aufgesetztes Merkmal, in `dense_cylinder` der ganze Körper, und nichts in
   den Parametern unterscheidet das.
3. Operationsfolge erzeugen: Grundform, Bohrungen, Senkungen, Langlöcher,
   Verrundungen, Fasen. Grundformen sind nicht nur Quader — `torus_ring` ist
   ein `create_torus`, `dense_cylinder` ein `create_cylinder`.
4. **Volumen gegen das Netz prüfen — nach dem Bauen.** Weicht es ab, wird das
   Ergebnis verworfen und der Grund genannt. Ein Vorab-Gate wäre unehrlich: Es
   verwirft `block_with_rounded_edge` und `openscad_ascii`, deren Nachbau auf
   0,2 % genau ist, und lässt `broken_selfint` durch, der 37 % daneben liegt.
5. **Der Nachbau steht hinter dem Importschritt.** Nichts verschwindet aus dem
   Verlauf; das eingelesene Netz bleibt und wird verbraucht.
6. Das Angebot als Zeile im Prüfbericht, wenn die Probe trägt: *„Dieses Modell
   lässt sich nachbauen — danach sind seine Maße änderbar."* Dazu die Liste,
   **was nicht mitkommt**, an diesem Modell gemessen statt allgemein — die
   Filamentzuweisung je Dreieck ist der Posten, den niemand erwartet.
7. Die Herkunft ausweisen: „Nachgebaut aus Halter.stl — die Maße sind gemessen,
   nicht die Originalwerte."
8. **RM-022 neu fassen** als „Nachbau als Operationsfolge" — der Punkt behält
   seine Kennung und bekommt den gemessenen Inhalt.

**Abnahme:** `plate_holes`, `plate_countersunk` und `plate_coarse_slots` kommen
als Konstruktion mit Verlauf zurück, Volumen innerhalb einer **unabhängig**
festgelegten Toleranz — nicht der aus §4. `bridge_two_end_supports` und
`island_tower` werden **nach** dem Bauen verworfen, mit Satz. Eine erzeugte
Figur wird gar nicht erst angeboten. Der Nachbau ist **eine** Transaktion:
ein Undo nimmt ihn vollständig zurück.

**Aufwand:** eigene Vorlage. Die Grundformerkennung und die Mehrdeutigkeit von
`pin` sind ungelöste Fragen, keine Fleißarbeit.

---

### Stufe 5 — Die Auswahlkarte ordnen

Roberts Vorgabe vom 17.09.2026: *„alle Operationen sollen bei dem jeweiligen
zutreffenden Objekt angezeigt werden, wenn die sinnvoll daran sind, nichts
doppelt anzeigen, schön gegliedert und übersichtlich."*

Der Ausgangspunkt, gemessen: 63 der 132 Operationen stehen ausschließlich in
der Auswahlkarte; die Gruppe *Ändern* hat 29 Einträge und startet zugeklappt;
an einer gewählten Bohrung stehen **36 sichtbare Eingabefelder**, „X"/„Y"/„Z"
je viermal mit vier Bedeutungen, und das eine *Übernehmen* ist beim ersten
Hinsehen auf *Merkmal verschieben* scharf statt auf *Bohrung ändern*.

Diese Stufe ist eine **eigene Durchsicht**, keine Liste von Handgriffen: Sie
entscheidet die Gliederung, die Reihenfolge und die Frage, was eine Karte
zeigt, wenn nichts anwendbar ist. Sie kommt nach Stufe 2, weil sich bis dahin
ändert, welche Operationen an welcher Merkmalsart überhaupt stehen.

---

### Abhängigkeiten auf einen Blick

```
Stufe 0  ──────────────────────────────────  unabhängig
Stufe 1  ──────────────────────────────┬───  vor Stufe 4 (Toleranz)
Stufe 2  ──────────────────────────────┼───  vor Stufe 3 (Körper bleibt exakt)
                                       │     vor Stufe 5 (Merkmalsarten stehen fest)
Stufe 3  ──────────────────────────────┤
Stufe 4  ◄─────────────────────────────┘
Stufe 5  ◄─── nach Stufe 2
```

---

## 14. Die Entscheidungen vom 17.09.2026

Sechzehn Fragen, alle von Robert am selben Tag entschieden. Sie sind oben
eingearbeitet; hier stehen sie beisammen, damit später nachvollziehbar ist,
was gewählt wurde — und was damit **nicht** gewählt wurde.

| # | Frage | Entscheidung |
|---|---|---|
| 1 | Gilt „vollwertig" wörtlich? | **Nein** — die Stufen sind die Antwort. Baugruppen und Zeichnungsableitung bleiben außen vor |
| 2 | Wann beginnt der Plan? | **Nach 0.4.3**, als Ganzes |
| 3 | Wie weit geht die Parität? | **Alles, auch die 31 Bausteine** |
| 4 | Die vier Zwillings-Haken? | **Alle vier fallen** |
| 5 | Torus und Gewinde? | **Voller Ausbau** in Stufe 2 |
| 6 | Wem gehört die Versatzebene? | **Der Skizze**, die sie benutzt — kein Objektbaum-Eintrag |
| 7 | Wo steht der Nachbau? | **Hinter dem Importschritt** |
| 8 | Die 43 unsichtbaren Operationen? | Alle am zutreffenden Objekt, **nichts doppelt, gegliedert** — eigene Stufe 5 |
| 9 | Freiformflächen im exakten Kern? | **Als `curved_face`**, wie am Netz |
| 10 | Gewinde im exakten Kern? | **Steigung an der BSpline messen** — auch eingelesene Gewinde |
| 11 | Bedienung der Bezugsebenen? | **Ein Eintrag „Neue Ebene …"** mit Art-Auswahl |
| 12 | `FEATURE_LIMIT_COUNT` = 1000? | **Anheben und die Zuordnung beschleunigen** |
| 13 | Bauplan §30.1? | **Erweitern, wenn Stufe 3 ansteht** |
| 14 | RM-022? | **Neu fassen** als „Nachbau als Operationsfolge" |
| 15 | *Gegenstück anlegen* am Gewinde? | **In Stufe 2 mitnehmen** |
| 16 | Die sechs Bedienfunde? | **Ins Konzept**, als Stufe 0 — der Plan wird am Stück abgearbeitet |

**Was diese Entscheidungen zusammen bedeuten:** Solidon wird kein Fusion. Es
wird ein Programm, in dem die Frage „habe ich ein Netz oder einen exakten
Körper" für den Kunden nicht mehr vorkommt — weil beide dasselbe können, beide
dieselben Merkmale zeigen und beide dieselben Maße richtig messen.

---

## 15. Was hier ausdrücklich **nicht** gebaut wird

0. **Keine Baugruppen und keine Zeichnungsableitung** (Robert, 17.09.2026).
   Sie waren — anders als die erste Fassung behauptete — nie abgelehnt, nur nie
   beauftragt; an diesem Tag sind sie es. Für Baugruppen gilt zusätzlich die
   technische Lage: flache Szene ohne `parent_id`, 3MF wird beim Einlesen
   verflacht, und für lebende Bedingungen zwischen Körpern gibt es keinen
   zulässigen 3D-Löser zu kaufen. Bauplan §18.3 sagt Bemaßung zu; das bleibt
   ein offener Widerspruch zwischen Vertrag und Entscheidung und gehört beim
   nächsten Bauplan-Durchgang benannt.
1. Kein Ersatz des Mesh-Kerns durch B-Rep — §30 sagt „neben, nicht statt".
2. Keine Verzweigungen im Op-Stack, kein Plugin-System, keine Cloud, kein
   Konto, keine Telemetrie, keine Browser-Version, kein eigener Slicer.
3. Kein Einfach-/Profi-Modus — stattdessen gestufte Tiefe.
4. Kein Umbau der Bedienzone zu einem Befehlsband (abgelehnt 29.08.2026).
5. Kein naives Nähen mit anschließendem Fillet (§8.1).
6. Kein lernendes Verfahren in der Geometrie.
7. Kein Text als Skizzenkontur, keine assoziativen Skizzenmuster, kein
   `offset_face`, kein FEM, kein Sculpting-Ausbau.
8. **Keine Zusage, dass jede STL zurückgewonnen wird** — und nach §8.2 auch
   keine, dass man es vorher weiß.

---

## 16. Was die Gegenprüfung umgeworfen hat

Die erste Fassung dieses Papiers wurde am selben Tag adversarial geprüft. Vier
Aussagen hielten nicht, und drei davon haben die Empfehlung verändert.

**16.1 „Baugruppen und Zeichnungsableitung sind abgelehnt" — falsch.** Die
Stelle heißt **Teil 5 — Was wir nicht übernehmen** und listet sie neben „Abo"
und „Sculpting": gemeint ist *vom Wettbewerb nicht nachbauen*, mit dem
ausdrücklichen Vorbehalt „solange die Zielgruppe stimmt". Das Papier ist vom
11.08., nicht vom 13.08.; der 13.08. gehört zu vier anderen Fragen. Weder
`AGENTS.md` noch Bauplan §41 führen die beiden unter „Was NICHT gebaut wird",
und §18.3 sagt Bemaßung ausdrücklich zu. **Nicht abgelehnt, nur nie beauftragt.**

**16.2 „183 Aufrufe von `as_mesh_data`" — trägt nichts.** Eine Grep-Zahl: zwei
Drittel sind Typ-Engführungen oder lesende Anzeigepfade. Die belastbare Zahl
steht in §5 und ist am Ergebnis gemessen.

**16.3 Die Zeichnungsableitung ist andersherum billig** (§7.1). Die erste
Fassung führte sie wegen der Netzfähigkeit als „kleineren Eingriff" — sie ist
am Netz teuer und am exakten Körper billig.

**16.4 „Bezugsebenen gibt es gar nicht" war zu grob** (§6.1), und **„torus und
thread tragen null Operationen" ist als Zählung richtig, als Aussage über den
Bedienstand zu grob**: 78 Operationen gelten dem Körper und greifen auch an
einem Torus; am Gewinde läuft die Gewindepassung ohne einen einzigen
`applies_to`-Eintrag. Richtig ist: *Es sind die einzigen zwei Merkmalsarten
ohne eigene Merkmalsoperation.*

Zwei Funde stammen aus der Prüfung selbst. Der erste — ein `Solid` führt seine
Merkmale nach einer Drehung nicht nach — ist **noch am selben Tag behoben**
(`5ad173de6`), zusammen mit dem `CYLINDER_SPREAD`-Befund aus §4.5
(`9c54ee1de`). Der zweite steht: `ROADMAP.md:812` nennt bei RM-128 `face` und
`edge_loop` als Arten ohne Operation — gemessen tragen sie 43 und 1; ohne
Operation sind `torus` und `thread`, und die nennt der Punkt nicht.

**Und die Lehre, die dieses Papier sich selbst erteilt hat:** Die erste Fassung
warnte in ihrem Schlussabschnitt davor, eine geerbte Ablehnung weiterzureichen,
ohne ihre Messung nachzufahren — und tat im selben Dokument genau das. Wer hier
später liest, misst am Code nach, bevor er es glaubt.
