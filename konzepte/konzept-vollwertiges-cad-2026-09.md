# Was Solidon zu einem vollwertigen CAD fehlt

> **Entscheidungen vom 17.09.2026, technisch geprüft am 18.09.2026.**
> Die sechzehn Entscheidungen in §14 bleiben bestehen; §14.1 ergänzt
> Roberts Vorgabe vom 18.09.: direkt am Modell mit Maßfeldern und ✓/×. Teilfunktionen und
> zwei vorgezogene Korrekturen sind bereits gebaut (§13); der weitere Ausbau ist geplant.
> Prüfstand der Geometriesonden: `2148ddfa`; beim Git-Abgleich auf `6ea0575e`
> blieben Anwendungscode und Tests unverändert. Der abschließende Torlauf
> wird in der Recherche protokolliert.
> Historische Messungen vom 17.09. sind von den Nachweisen in §17 zu unterscheiden.
>
> **Der Plan bleibt als Ganzes gedacht und beginnt nach Veröffentlichung von
> 0.4.3.** Diese beauftragte Durchsicht verbessert Konzept, Recherche und
> Roadmap; sie beginnt keine Umsetzung und erklärt die Veröffentlichung nicht für erfolgt.
>
> **Vierte Fassung.** Die Gegenprüfung der ersten Fassung steht in §16;
> zusätzliche Korrekturen, Prüfgrenzen und Nachweise stehen in §§17–18.
> §13 ergänzt die Paketgrenzen und Voraussetzungen für die Umsetzung.
> Die [vertiefte Recherche](recherche-cad-paritaet-2026-09.md) belegt weitere
> Lücken, Bibliotheksoptionen und eine begrenzte native Fensterprüfung.
> Offene Arbeit wird in [RM-188](../ROADMAP.md#rm-188) geführt.

---

Anlass ist Roberts Frage vom 17.09.2026: *„was fehlt uns, um es zu einem
vollwertigen 3D-CAD-Programm zu machen, ohne CAD-Erfahrung und alles möglichst
einfach, und STL die Merkmale und alles sauber zu erkennen."* Dazu am selben
Tag seine Entscheidung, die dieses Papier trägt:

> **„Exakt oder Netz sollte immer gleich bearbeitbar und erkennbar sein."**

Sie schließt an den 10.09.2026 an („alles soll immer bearbeitbar sein, egal ob
importiert, Format egal") und macht aus einer Sammlung von Einzellücken eine
Richtung: **Parität.**

---

## 1. Drei Ziele, ein gemeinsamer Bedienweg

1. **Vollwertig** heißt hier: die beschlossenen Konstruktionswege für Druckteile
   vollständig bedienen. Baugruppen und Zeichnungsableitung bleiben nach §14
   ausdrücklich außerhalb des Umfangs.
2. **Ohne CAD-Erfahrung, möglichst einfach** heißt: am Körper arbeiten, Maße
   verständlich ändern und Fehler beheben können, ohne die Rechenkerne zu
   kennen. Pauschale Lernzeiten anderer Programme sind ohne vergleichbare
   Aufgabe und Nutzerstudie keine Abnahmegrundlage.
3. **STL-Merkmale sauber erkennen** unterstützt beide Ziele. Der lokale Korpus
   belegt keine Marktführerschaft; maßgebend sind Maßtreue, vollständige
   Kundenwege und erklärte Grenzen.

Roberts Paritätssatz bedeutet dieselben Handlungen und dieselbe fachliche
Bedeutung für beide Körperarten. Er verspricht keine identischen Dreieckslisten
oder gleichen Fehlergrenzen. Eine Näherung bleibt als solche erkennbar; eine
nicht unterstützte Geometrie wird begründet abgewiesen statt still umgedeutet.

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

Registerzahlen und 15 Kernbedingungen wurden am 18.09. bestätigt (§17).
Quelltextumfang, die 16 UI-Namen und die 55,1-ms-Einzelmessung bleiben
historische Angaben vom 17.09.; sie sind keine neue Leistungsabnahme.
Die Kategorie `parts` enthält 48 Operationen, aber 35 Bausteine. Die später
genannten 31 sind die damals geprüften netzerzeugenden Bausteinpfade.

---

## 3. Die Kernaussage: eine Einbahnstraße, zwei blinde Flecken

Nach der Gegenprüfung steht die Lage anders da als in der ersten Fassung. Drei
Befunde tragen alles Weitere, und alle drei sind gemessen:

**A — Die Einbahnstraße.** Von 132 Operationen halten **20** einen exakten
Körper exakt, **3** verlangen ihn, **56** machen aus ihm ein Netz. Von diesen 56
haben genau **zwei** einen exakten Zwilling; **54 haben keinen direkten Zwilling.** Der
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
| Gewinde, historische Probe der Topologieerkennung | **7 `pin` Ø8,16**, kein daraus erkanntes Gewinde | 1 `thread` Ø10,0, Steigung 1,5 |
| Hohlraum | 12 `face` | 6 `face`, 1 `void` |

Zwei Richtungen, nicht eine: Bei Verrundung und Fase ist der exakte Kern
**reicher und genauer**, bei Torus, Gewinde und Hohlraum **ärmer oder falsch**.

**Erzeugung und Import unterscheiden:** `thread_exact` ergänzt bereits ein
`thread_1` mit `provenance="generated"`, Durchmesser, Steigung, Länge, Lage
und Mantelflächen. Drei Tests bestätigen diesen Vertrag (§17). Der Ausbau
betrifft die Erkennung ohne diese Erzeugerinformation, insbesondere nach
STEP-Import; die vorhandene Benennung wird erhalten und nicht neu gebaut.

Dazu eine Eigenart, die die Auswertung betrifft: **Der exakte Körper trägt nur,
was die Operation selbst hineingeschrieben hat.** `features_of` wird von den
Operationen gerufen, nicht zur Neuerkennung in `_with_features`. Dort wird
nur `MeshData` dem Netzdetektor übergeben; ein `Solid` hat zwar eine abrufbare
Tessellierung, nimmt aber diesen automatischen Erkennungsweg nicht. Bei einer **starren** Bewegung zieht
`_carried_along` die Merkmale seit dem 17.09.2026 mit (Commit `5ad173de6`; vorher
stand nach 30° um X die Deckfläche weiter mit Normale (0,0,1) bei z = 10, und
ein Zapfen darauf kam unter dem Bett heraus). Was bleibt, ist gemessen und
klein: **`mirror_object` gibt einen exakten Körper mit null Merkmalen zurück** —
als einzige der sechzehn damals geprüften exakten Operationen. Am 18.09.
über `scene.evaluate` bestätigt: sechs Merkmale vor, null nach Spiegelung.
Für Netze gilt der Befund nicht; dort führt die Auswertung Merkmale nach.
Ein leeres `features`-Feld allein wäre deshalb kein ausreichender Nachweis.

**C — Die Erkennung misst systematisch zu klein.** Das ist der Befund mit der
größten Breitenwirkung, und er ist bis auf die Ursache durchgemessen (§4).

---

## 4. Maßschätzung und tatsächliche Netzkontur unterscheiden

### 4.1 Ursache und Geltungsbereich

`fit_cylinder`, `fit_cone`, `fit_sphere` und `fit_torus` benutzen
`body.triangles_center` — Dreiecksschwerpunkte — in unterschiedlichen
Einpassungsverfahren. Für einen regelmäßigen Zylindermantel, dessen ebene
Sehnenflächen in zwei Dreiecke gleicher Bauart zerlegt sind, gilt:

```
gemessen = Umkreismaß · √(5 + 4·cos(2π/n)) / 3
```

Der Faktor folgt aus der Lage des Dreiecksschwerpunkts auf einem Drittel
beziehungsweise zwei Dritteln der Sehne. Die folgende Zylinderreihe wurde
am 18.09. bestätigt. Für Kegel, Kugeln, Tori, Teilbögen, ungleiche
Winkelabstände und andere Triangulierungen ist dies keine allgemeine
Fehlerformel. Die historische Übereinstimmung am Ringdurchmesser von
`torus_ring` belegt insbesondere nicht den Fehler beider Torusradien.

### 4.2 Die Wirkung und die Grenze der Passungsaussage

| Soll Ø in mm | Facetten | gemessen in mm | Abweichung in mm |
|---:|---:|---:|---:|
| 5,2 | 16 | 5,1113 | −0,0887 |
| 5,2 | 24 | 5,1605 | −0,0395 |
| 5,2 | 48 | 5,1901 | −0,0099 |
| 15,0 | 16 | 14,7441 | −0,2559 |
| 30,0 | 16 | 29,4882 | −0,5118 |
| 30,0 | 24 | 29,7720 | −0,2280 |

Bei diesen idealen Fällen ist der Fehler einseitig zu klein und wächst mit
dem Durchmesser. Die zusätzlich geprüften 8- und 12-Eck-Bohrungen Ø5,2
wurden nicht als Bohrung erkannt; das ist keine universelle Grenze bei
16 Facetten. Ein absichtlich polygonales Loch darf nicht automatisch als
ungenau exportierter Kreis umgedeutet werden.

`scene.fits.check` benutzt die Differenz der Merkmalsdurchmesser. Bei gleicher
Facettierung wirkt derselbe Verzerrungsfaktor auf beide Maße; er hebt sich
nicht exakt auf. Die historischen Rechenbeispiele lauten:

| Soll Ø Loch | n Loch | Soll Ø Zapfen | n Zapfen | Differenz der Soll-Ø | gemessene Differenz |
|---:|---:|---:|---:|---:|---:|
| 20 | 48 | 19,6 | 48 | 0,400 | 0,399 |
| 20 | 16 | 19,6 | 48 | 0,400 | 0,096 |
| 30 | 16 | 29,6 | 64 | 0,400 | −0,080 |

**Die letzte Zeile belegt keine Fehlwarnung bei einer kollisionsfreien
Passung.** Ein 16-Eck-Loch mit Umkreis-Ø30 hat einen Inkreis-Ø von
`30 · cos(π/16) = 29,4236 mm`. Ein koaxialer 64-Eck-Zapfen Ø29,6 kollidiert
damit tatsächlich: Die Gegenprobe ergibt 14,8330 mm³ Schnittvolumen (§17).
Die Differenz der zugrunde gelegten Kreis-Sollmaße ist etwas anderes als
das freie Spiel der vorhandenen Netze.

Der Maßvertrag trennt deshalb **geschätztes analytisches Maß**, **reale
Netzkontur mit Facettierungsabweichung** und **Fertigungsspiel aus dem
Materialprofil** (Bauplan §11.2). Eine Radiuskorrektur darf nicht allein
durch eine größere Zahl eine kollidierende Passung als passend erklären.
Die Abnahme führt deshalb über `fits.check` und eine unabhängige geometrische
Gegenprobe, nicht allein über zwei berechnete Durchmesser.

### 4.3 Lösungsansatz: geometriespezifische Fits mit Gegenproben

Für zylindrische Wände existiert `radial_cylinder`: projizierte Ecken,
konvexe Hülle, Vereinfachung, Kreiseinpassung sowie Prüfung von Normalen,
Abweichung und Winkelabdeckung. Die Toleranz berücksichtigt bereits
`ROUND_WALL_TOLERANCE` zusätzlich zur Schweißtoleranz. Dies ist der erste
zu prüfende Wiederverwendungsweg, kein bereits bewiesener Ersatz aller Fits.

Unterteilungspunkte liegen auf Sehnen, nicht auf dem ursprünglichen Kreis.
Sie müssen von ursprünglichen Konturecken unterschieden werden. Der
historische Prototyp zeigt selbst, dass eine bloße Hülle nicht genügt:

| Facetten | Unterteilung | Schwerpunktfit R | alle Ecken R | Hüllecken R |
|---:|---|---:|---:|---:|
| 16 | keine | 19,6588 | 20,0000 | 20,0000 |
| 16 | einfach | 19,7232 | 19,8088 | 19,9416 |
| 16 | zweifach | 19,7393 | 19,7607 | 19,9482 |
| 48 | zweifach | 19,9709 | 19,9732 | 19,9966 |

Sollradius jeweils 20 mm. Diese Prototypzahlen sind am 18.09. nicht erneut
gemessen; Verfahren und Eingaben müssen vor Übernahme reproduzierbar gesichert
werden. Am einfach unterteilten 16-Eck verfehlt auch der Hüllenwert einen
Durchmesserfehler unter 0,01 mm deutlich.

**Kegel, Kugel und Torus benötigen eigene Fitverträge.** Eine gemeinsame
2D-Hülle bildet weder einen Kegelstumpf mit axial wechselndem Radius noch
eine Kugelkalotte oder beide Radien eines Torus allgemein ab. Je Form sind
unabhängige Sollgeometrie, Teilabdeckung, Rauschen, Ausreißer, Unterteilung
und ähnliche Gegenformen zu prüfen. Keine pauschale Änderung „derselbe
Punktsatz in allen vier Funktionen“.

Der historische Prototyplauf berichtet **370 bestanden und 3 gefallen**,
also 373 Ergebnisse; die zuvor daneben genannte Zahl 372 war inkonsistent.
Ohne Laufprotokoll und Prototypstand ist das kein belastbarer
Regressionsnachweis. Die zwei bestehenden Form-Gegenproben
`test_the_residual_cannot_see_a_blown_up_circle` und
`test_the_normals_decide_the_shape_and_not_the_residual` dürfen nicht
einfach entfallen: Ihre fachlichen Absagen müssen auch nach einem neuen
Fit belegt sein. Ebenso wenig darf eine höhere Streuung allein durch
Anheben einer Testschranke akzeptiert werden. Fitfehler und Abstand der
Facettenschwerpunkte zur analytischen Fläche sind getrennt zu definieren.

### 4.4 Historische Plausibilitätsprobe am Kundenmodell

Am Filament-Rack wurden Treffer auf einem 0,5-mm-Raster innerhalb 0,02 mm
gezählt: 13 von 103 Merkmalen zuvor, 67 von 100 mit Prototyp; mittlerer
Rasterabstand 0,074 → 0,040 mm. Das ist eine Beobachtung, kein unabhängiges
Gütemaß. Tatsächliche Maße können neben diesem Raster liegen; zudem
unterscheiden sich die verglichenen Merkmalsmengen. Für die Abnahme sind
korrespondierende Merkmale und unabhängig bekannte Maße erforderlich.

### 4.5 Bereits behoben und weiterhin zu prüfen

`CYLINDER_SPREAD` ist seit `9c54ee1de` von der Breite einzelner Dreiecke
gelöst. `_chord_sag` und `ROUND_WALL_TOLERANCE` bilden den Maßstab. Die drei
Regressionstests einschließlich der Platte bis 815 104 Dreiecke bestehen
(§17). Der alte Fehler ist nicht erneut zu implementieren; eine Fitänderung
muss seinen Schutz erhalten.

„Größter Abstand zur Achse“ bleibt als Pauschalkorrektur verworfen:
Ein Ausreißer vergrößert das Ergebnis. Auch ein guter Fit rekonstruiert
keinen sicheren Nennwert aus einer beliebigen STL-Datei.

---

## 5. Die Einbahnstraße, im Detail

Historische Stichprobe über `kind_of(produced.mesh)`, entsprechend dem
Ausgabevergleich in `scene.evaluate`. Die Gruppen 20 + 3 + 56 decken nicht
alle 132 Operationen ab. Für die Umsetzung ist deshalb eine vollständige
Matrix je Eingabeart, Variante und Ausgabe anzulegen: erhalten, konvertiert,
abgelehnt, ohne Geometrieausgabe oder nicht geprüft. `delete_object` ist etwa
keine erfolgreiche geometrieerhaltende Ausgabe. Ein fehlender Zwilling
beweist zudem nicht, dass kein mehrstufiger exakter Arbeitsweg möglich ist.

**Die historische Liste von 20 als „erhalten“ gezählten Operationen:** `chamfer_edges`,
`check_join_path`, `delete_object`, `draft_faces`, `duplicate_object`,
`fillet_edges`, `intersect_objects`, `mirror_object`, `pattern`, `place_on_bed`,
`push_face`, `resize_hole`, `rotate_object`, `set_material`, `sketch_pocket`,
`slot_hole`, `slots_from_texture`, `subtract_objects`, `translate_object`,
`union_objects`.

**56 machen ein Netz daraus.** Nach Kategorie: 31 Bausteine (`insert_*`),
7 `holes`, 7 `mesh`, 3 `prepare`, 2 `transform`, 2 `colour`, 4 einzeln.

Drei davon sind keine Kernfrage, sondern Versehen:

- **Die beiden Skalierungswege verlieren die exakte Darstellung.**
  Verschieben, Drehen und Spiegeln bleiben exakt; `scale_object` und
  `fit_to_size` nicht. Die OCCT-Grundoperationen sind vorhanden — historisch gemessen: `gp_Trsf.SetScale`
  (Quader 10³ × 2 → 8000,0) und `gp_GTrsf` für ungleichförmig (2/1/0,5 → 1000,0).
  Ungleichförmige Skalierung kann Kreise zu Ellipsen und analytische Flächen
  zu anderen Flächenarten machen. Merkmalsarten, Radien, Referenzen, Passungen
  und Materialzuordnung dürfen nicht unverändert vom Eingang übernommen werden.
- **Zwei von drei Filamentoperationen ändern die Körperart nebenbei.**
  `slots_from_texture` bleibt exakt; `assign_slot` und `paint_slot` machen ein
  Netz — bei **unverändertem Volumen**. Für den Erhalt des B-Rep braucht es
  zusätzlich einen Vertrag für die Filamentzuordnung zur Darstellung:
  erneute Tessellierung, Qualitätswechsel und Speichern dürfen die Bemalung
  nicht verlieren. Gleiches Volumen allein belegt diesen Erhalt nicht.
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

### 6.1 Bezugsebenen jenseits der drei Hauptebenen

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

Richtig ist deshalb: **Außer den drei Hauptebenen gibt es keine frei
benannte Bezugsebene.** Für einen anderen Ort führt der heutige Bedienweg
über einen Hilfskörper. Das kostet zwei Schritte im Verlauf, einen
Zwischenzustand, in dem die Hilfsplatte im Exportplan steht, keinen direkten parametrischen Ebenenabstand zum ursprünglichen Bezugskörper
und einen Verlauf, in dem „Quader anlegen“ steht, wo
„Bezugsebene 20 mm über der Deckfläche" gemeint war.

Am Bedienweg gezählt: **vier Klicks und eine Zahl** mit einer Versatzebene
gegen **neun Klicks und zwei Körper im Verlauf** über den Hilfsquader — und
danach steckt der Abstand in den Parametern des Hilfsquaders statt in einem
benannten Ebenenmaß. Das Löschen des Körpers ist nicht das Entfernen seines
Erzeugungsschritts: Im non-destruktiven Verlauf können dessen Parameter
weiterhin änderbar sein.

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
| Muster und Spiegelung **als Merkmal im Körper** | Objektmuster vorhanden; `mirror_object` ersetzt den Körper | Erweiterung |
| Merkmalsarten Tasche, Nut, Rippe, Kante, Fase, Symmetrie, Lochmuster | fehlt | frei |
| Torus, Gewinde, Hohlraum und Freiform aus **exakter Topologie erkennen** | unvollständig; erzeugte Gewinde sind bereits benannt | Ausbau gemäß §14; Aufwandshypothesen in §12 |
| STEP-Baugruppenstruktur (XCAF: Namen, Farben, Baum) | fehlt | frei |
| Verlauf: einfügen, umsortieren, zurückspulen, stummschalten | fehlt (nur ändern und löschen) | frei |
| Mesh → exakte Geometrie | fehlt | **RM-022 offen** |
| Baugruppen mit Hierarchie, Instanzen, lebenden Bedingungen | fehlt | **ausgeschlossen** (Robert, 17.09.2026 — §14 Nr. 1) |
| Zeichnungsableitung mit Bemaßung | fehlt | **ausgeschlossen**; stehende Messbemaßungen im Viewport nach Bauplan §18.3 bleiben bestehen |
| Ellipse, Tangente Bogen-an-Bogen | fehlt | Erweiterung von Solver, Editor, Profilbildung und Speicherung |

„Frei“ in dieser Bestandsliste bedeutet nicht beauftragt. §14 Nr. 1 legt den
Umfang über die Stufen fest. Variable Fillets, zusätzliche Fasenarten,
Mehrprofil-Loft, neue Merkmalsfamilien, XCAF-Struktur und Verlaufssortierung
sind damit keine stillen Zusatzpakete. Vor ihrer Aufnahme ist der Umfang
explizit zu erweitern; die Parität bestehender Handlungen bleibt beauftragt.

### 7.1 Zeichnungsableitung — unterschiedliche Voraussetzungen

Die erste Fassung hatte es andersherum. Gemessen an `plate_holes.stl`:

```
HLR Draufsicht:  3,7 ms  ->  196 sichtbare Kanten, 192 davon kürzer als 1 mm
```

Eine Zeichnung dieser Platte braucht **8** Elemente: 4 Randlinien und 4 Kreise.
Die 196 gehen exakt auf — 4 + 4 × 48 Facetten. Am exakten Körper dagegen:

```
HLRBRep_Algo     (exakt): 5 Kanten, {Line: 4, Circle: 1}
HLRBRep_PolyAlgo (polygonal): 30 Kanten, {Line: 30}
```

Die Fünf-Kanten-Probe hat eine Bohrung und ist kein direkter Vergleich zur
Vierlochplatte mit acht idealen Konturelementen. Auch `HLRBRep_PolyAlgo`
erwartet triangulierte `TopoDS_Shape`-Objekte mit Kanten, nicht unmittelbar
Solidons `MeshData`. Adapter und Konturqualität sind Teil des Aufwands.
[OCCT-Referenz](https://occt3d.com/dev/doc/refman/html/class_h_l_r_b_rep___poly_algo.html).

Die historischen Zeiten zum Bauen der OCCT-Form aus einem Netz lauten: 796 Dreiecke
0,14 s, 12 736 Dreiecke 3,59 s — hochgerechnet **rund eine Minute** für ein
übliches 200 000-Dreieck-STL. Und die Kantenzahl verdoppelt sich mit jeder
Verfeinerung: ein feineres Netz gibt eine schlechtere Zeichnung. Derselbe
Fehler wie in §4 — gemessen wird die Facettierung.

Diese wenigen Zeiten sind keine belastbare Laufzeitprognose für andere
Modelle. Weder eine fertige Zeichnungsableitung noch deren Aufwand folgen
aus einem HLR-Aufruf; Maßbezüge, Ansichten, Beschriftung und Export fehlen
in dieser Probe. Für die beschlossenen Stufen bleibt das Thema ausgeschlossen.

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
Flächen bleiben eben. Analytische Parameter sind nur ein Teil der Rückgewinnung. Zusätzlich fehlen
passende Begrenzungen, Nachbarschaft, Schnitt- und Übergangskurven,
Orientierung, Toleranzverteilung und Gültigkeitsprüfung des zusammengesetzten
Volumens. Gerade tangentiale Anschlüsse werden nicht durch einen beliebigen
Flächenschnitt gelöst.

### 8.2 Der bessere Weg: nachbauen statt nähen — und was er nicht kann

Statt Flächen zusammenzusetzen, den Körper als **Folge registrierter
Operationen** nachbauen: Grundform, Bohrungen, Senkungen, Verrundungen. Das Ziel
ist ein exakter Körper mit einer **neuen Konstruktion mit Verlauf**. Die
ursprüngliche Historie wird nicht rekonstruiert (Bauplan §42).

**Wo die historische Volumenprobe nahe liegt** (noch keine Formabnahme): `plate_holes` 0,00 %,
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
liegt. **Nach dem Bauen ist ein unabhängiger Formvergleich nötig.** Gleiches Volumen
ist nicht hinreichend: Eine Bohrung an der falschen Stelle kann exakt dasselbe
Volumen abziehen. Zusätzlich sind beidseitige Oberflächenabweichung,
Lochlagen, Wandstärken, Hohlräume, Zusammenhang und gültige Topologie zu
prüfen. Gegenprobe: zwei sonst identische Platten mit gleich großen, aber
versetzten Bohrungen müssen trotz gleichen Volumens als verschieden gelten.

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
  Kugel. Drei Kandidaten mit einfacher Grundform, die „prismatisch“ aussortieren würde.
  Richtig ist: **ein belegtes Grundvolumen plus erklärte Aufträge und Abzüge, deren Ergebnis
  die lokale Form und die Topologie des Netzes innerhalb des vereinbarten
  Abweichungsbudgets trifft.**

Und: `post_with_fillet` scheitert **nicht an „organisch"**. Die Erkennung
liefert alles — Grundplatte, Kopffläche π·6², Zapfen Ø12×30, Hohlkehle
Ø18/Ø6. Ein eigenständiger Zylinder lässt sich bereits mit einem Körper vereinigen;
„kein Weg setzt einen Zapfen auf einen Körper“ war zu weitgehend. Offen sind
insbesondere die automatische Rolle der Teilformen, ihre Reihenfolge und
der verlässlich passende Übergang. Eine Liste erkannter Merkmale ist noch
keine vollständige Konstruktionsbeschreibung.

### 8.3 Vorhandene Werkzeuge und Auslieferungsnachweis

`GeomAPI_IntSS` (Schnittkurve zweier Flächen — „die schwere Stelle" des alten
Konzepts), `BRepBuilderAPI_Sewing`, `ShapeFix_Shape`, `ShapeFix_Solid`,
`BRepOffsetAPI_MakeFilling`, `GeomAPI_PointsToBSplineSurface`, `HLRBRep_Algo`.
In der Entwicklungsbindung verfügbar heißt nicht im Kundenpaket geprüft.
`packaging/solidon3d.spec` nennt zwölf OCP-Module ausdrücklich; neue Imports
brauchen Paketproben auf Windows, Linux und macOS. Solange dieselbe
freigegebene Distribution benutzt wird, entsteht nicht durch einen Import
eine neue Abhängigkeit. Änderungen am nativen Umfang oder an der Distribution
werden gegen Lizenzliste und Manifest geprüft (Regeln 15 und 22).

---

## 9. Die Oberfläche, an Dialogen und Panels geprüft

Die Vorlage berichtet fünf Wege über `build_application`, offscreen, ein
Prozess je Block. Das ist eine historische Dialog-/Panelprobe, keine Abnahme
am sichtbar gerenderten Fenster; sie wurde am 18.09. nicht wiederholt. **Ein Vorbehalt vorweg:** offscreen ist `viewport.renderer`
leer — was im Bild passiert, ist damit nicht gemessen; die Zahlen gelten dem
Dialog- und Panelanteil.

### 9.1 Die Klickzahlen

| Weg | Klicks | Bemerkung |
|---|---:|---|
| Quader + Bohrung + Verrundung, neu konstruiert | **13** | einer davon nur, um die Gruppe *Ändern* aufzuklappen |
| Skizze auf einer Fläche bis zum Körper | **6** | der beste der fünf Wege |
| Fremde STL laden, Bohrung ändern, exportieren | ~9 | Import 1,26 s |

**Der Skizzenweg zeigt in dieser Probe verständliche Rückmeldungen.**
Eine Laien-Abnahme ist damit nicht erfolgt. Die
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
Befehlspalette auf Strg+Umschalt+P. Für unerfahrene Nutzer ist die Entdeckbarkeit dieser Handlungen deshalb zu
prüfen. Eine Bearbeitung kann jedoch eine Auswahl voraussetzen; der leere
Projektzustand allein belegt noch keinen Fehler.

Dass die Operationen dort wohnen, ist eine Entscheidung (Robert, 11.09.2026).
Neu ist die gezählte Verteilung. Zu trennen sind das Erzeugen im leeren
Projekt und die anschließende Bearbeitung eines gewählten Körpers.

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

- **19 fachliche Eingabefelder** in der nativen Gegenprobe vom 18.09.,
  fünf Handlungsblöcke untereinander; die frühere Angabe „36“ war keine
  belastbare Zählung eigenständiger Eingaben,
- „X" / „Y" / „Z" **je viermal** als Beschriftung, mit vier verschiedenen
  Bedeutungen beziehungsweise Gruppenbezügen,
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

### 9.5 Zwei Obergrenzen sind erreicht

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
  Ebenenzeile des Skizzeneditors, für den gewählten Grund- oder Flächenbezug; der beschlossene Einstieg
  bleibt „Neue Ebene …“ mit Art-Auswahl (§14 Nr. 11): `Zeichenebene: [Fläche an Halter ▾]  Abstand: [ 0,00 mm ]`. Vier Klicks.
- **Revolve-Cut wird kein zweiter Eintrag**, sondern ein Feld im Dialog.
- **Der Nachbau ist kein Werkzeug**, sondern eine Zeile im Prüfbericht:
  *„Dieses Modell lässt sich nachbauen — danach sind seine Maße änderbar."*
  Eine Prüfung erzeugt zunächst einen Kandidaten; erst nach bestandener
  Formprüfung und einer Vergleichsvorschau kann er übernommen werden.
  Ein ausdrücklich gestarteter Versuch erhält auch bei Ablehnung eine
  verständliche Antwort. Die Klickzahl ist am fertigen Weg abzunehmen.
- **Die Maßkorrektur aus §4 braucht keinen neuen Betriebsmodus.** Sie ist
  jedoch ein Eingriff in Fit, Formentscheidung und Maßverbraucher, keine
  einzelne Zeile. Unsicherheit wird dort erklärt, wo ein Maß übernommen wird.

### 10.1 Die Zwillings-Haken fallen — Folge aus Roberts Entscheidung

Gemessen:

| Paar | Parameter Netz / exakt | Unterschied |
|---|---|---|
| `create_box` / `create_brep_box` | 12 / 11 | genau einer: `anchor` |
| `create_cylinder` / `create_brep_cylinder` | gleich | — |
| `drill_hole` / `drill_brep_hole` | 17 / 17 | **keiner** |
| `hollow_object` / `shell_exact` | 5 / 1 | `open_top`, `open_at`, `vents` |

Die sichtbaren Kernwahl-Haken fallen gemäß §14. Die automatische Auswahl
muss aber die Handlung bewahren: Ein Mesh-Eingang wird durch die Wahl des
exakten Bohrbefehls nicht zu B-Rep. Beim Anlegen neuer Grundkörper kann der
exakte Weg die Vorgabe sein; bei Bearbeitungen entscheidet die vorhandene
Körperart zusammen mit den unterstützten Parametern.

**Aushöhlen benötigt eine korrigierte Entscheidungstabelle.** `shell_exact`
ruft `shell_open_top` und öffnet immer die Oberseite. Die zuvor vorgeschlagene
Regel „Oben öffnen → Netz, sonst exakt“ würde einen geschlossen gewünschten
Körper öffnen. Bis zur vollständigen Parität gilt:

| Eingabe / gewünschte Wirkung | zulässiger Weg |
|---|---|
| B-Rep, oben offen, keine Entlüftung, kein abweichender Flächenbezug | vorhandener `shell_exact`-Weg |
| B-Rep, geschlossen oder andere Öffnung oder Entlüftung | entsprechender exakter Ausbau; bis dahin bestehender Netzweg mit Vorschauhinweis |
| Mesh | vorhandener Netzweg; kein bloßer Aufruf einer B-Rep-pflichtigen Op |
| Optionaler exakter Kern fehlt | erklärter verfügbarer Weg; kein stilles Scheitern |

`open_at` und sämtliche bisherigen Parameter bleiben berücksichtigt. Das
Entfernen der Haken darf weder alte Projekte umschreiben noch Optionen oder
Wirkung verändern; der Umschaltzeitpunkt steht in §13.

**`MENU_TWINS` bleibt** (es trägt Menüzusammenlegung, Palette und
`change_kernel`); der sichtbare Haken fällt. Gewinn: *Quader anlegen* verliert
ein Feld auf der Vorderseite, *Bohrung setzen* eine wirkungslose Zeile, zwei
Sätze fallen aus sechs Sprachkatalogen.

Was an die Stelle tritt, hängt an der **Handlung** statt am Körper: ein Satz am
Feld, wenn er zutrifft („Der Bogen entsteht hier als Folge gerader Stücke; die
Abweichung bleibt unter 0,02 mm"), ein Hinweis nach dem fachlichen Genauigkeitsbudget statt nach einer
Schichthöhe. Schichthöhe misst nicht die zulässige radiale Maßabweichung.
*[Diese Schritte exakt rechnen]* wird nur angeboten, wenn die gesamte
betroffene Kette mit gleicher Bedeutung neu gerechnet werden kann. Bei
fehlender Rekonstruktion ist ein anderes Exportformat oder das Ändern des
konvertierenden Schritts der ehrliche Rückweg.

### 10.2 Maße direkt am Modell, ein sichtbarer Abschluss

**Vorgabe Robert, 18.09.2026, nach der vertieften Durchsicht:** Eingabefelder
wie die Abstände beim Bohrungsetzen am Modell zeigen, etwas von der Maßlinie
abgesetzt. Daneben ✓ zum Bestätigen und × zum Abbrechen. Bei Bewegen und den
anderen geeigneten Operationen denselben Weg verwenden. Im Panel keine
parallel angebotene Zahlenbearbeitung; „Auf alle“ unmittelbar unter dem
Eingabefeld im Viewport. Dialoge sind für diese Hauptwege nicht der Einstieg.

Der Bestand ist teilweise vorhanden: `PlacementFlow` zeigt Abstände und
Tiefe im Bild; `DragValueBar` trägt Zugwerte; `TransformBar` enthält X/Y/Z,
Winkel und Skalierungswerte. Die Bestätigung ist heute unterschiedlich:
Enter in der Bewegen-Leiste, Loslassen beim Körperzug, späteres Übernehmen
bei einem Merkmalsvorschlag. Der Ausbau führt diese Wege zusammen.

Ein aktiver Operationsentwurf hält Werte, Ziel und Sammelauswahl. Tippen und
Ziehen sind Vorschau. **Ein gemeinsames ✓/× an der aktiven Feldgruppe**
übernimmt beziehungsweise verwirft den ganzen Entwurf; Enter/Escape tun
dasselbe. Tab, Fokusverlust und Kamerabewegung schreiben nichts. Nach
Übernahme ist der Entwurf verbraucht, ein weiterer Enter verschiebt nicht
noch einmal. Vorher bleibt „Noch nicht übernommen“ sichtbar. Ein Undo nimmt
alle zusammengehörigen Änderungen zurück.

„Auf alle N gleichartigen … anwenden“ steht darunter, wenn die Handlung
weitere passende Merkmale desselben Körpers besitzt. Alle Ziele werden vor
Übernahme hervorgehoben und in der Vorschau geändert; kein stilles Übergehen
eines ungeeigneten Ziels. Die Auswahl bleibt zunächst auf dem einen Merkmal.
Die Panel-Zahlenfelder und der parallele Übernahmeknopf entfallen nach dem
Umschalten der jeweiligen Familie; seltene Zusatzoptionen dürfen ergänzen,
nicht denselben Wert ein zweites Mal bearbeiten.

Das ist eine bewusst geänderte Bedienentscheidung gegenüber „kein Anwenden
unten bei Bewegen“ vom 03.09. und gegenüber dem bisherigen Abschluss eines
Körperzugs beim Loslassen. ✓ ist der Abschluss der Vorschau und kein zusätzlicher
Bestätigungsdialog. Die ursprünglichen 16 Entscheidungen bleiben erhalten;
diese Ergänzung präzisiert ihren Bedienweg. Vor der Umsetzung entsprechende
Bauplan- und Bedienverträge nachführen.

Der [vollständige Ablauf](recherche-cad-paritaet-2026-09.md#42-direkt-am-modell-bearbeiten--vorgabe-vom-18092026)
regelt Feldabstand, Überlappung, Bezugssysteme, Mehrfeld-/Sammelbearbeitung,
Fehler, Eingabezustände, Tastatur und die Übertragung auf weitere Operationen.
Abnahme: Hauptwege mit geschlossenem Panel, auf Netz und B-Rep, mit einem
Undo und ohne unbemerkt unbestätigte Änderung. Sinnvolle Abstandsbezüge nach
§10.3 gehören zu diesem Vertrag.

### 10.3 Sinnvolle Kanten und Merkmale als Abstandsbezug

**Ergänzung Robert, 18.09.:** Die Abstandsmaße müssen brauchbare Bezüge zum
Ausrichten finden. Der heutige Weg nimmt die zwei nächsten nicht parallelen
Randstücke sowie nahe Bohrungsmitten. Die vertiefte Gegenprobe zeigt die
Grenze: Eine nicht erkannte Ø0,5-mm-Bohrung liefert zwei Kreisfacetten von
0,032702 mm als Bezugskanten, obwohl der vorhandene Test mit bereits
benanntem Bohrungsmerkmal besteht.

Der gemeinsame Editor schlägt geometrisch geeignete, konstruktiv sinnvolle
Bezüge vor und hebt sie hervor. Ausdrücklich gewählte Bezüge haben Vorrang;
Außenkante, Innenkante, Mitte und Achse sind fachlich zu unterscheiden.
Triangulationsdiagonalen und belegte Kreisfacetten werden keine geraden
Ausrichtungsbezüge. Kurze echte Ausschnittkanten bleiben auswählbar.
Fast parallele Kanten dürfen keine numerisch instabile Positionsbestimmung
liefern; verdeckte Rückseiten und fremde Körper sind keine stillen Vorgaben.

„Bezug ändern“ an der Maßbeschriftung erlaubt die direkte Auswahl einer
anderen passenden Kante oder eines Merkmals im Modell. Ab Eingabebeginn
bleiben Bezug und Vorzeichen bis ✓/× fest. Mitte–Mitte, Kantenabstand und
Randabstand werden eindeutig bezeichnet; ein berechneter Versatz verspricht
keine dauerhafte assoziative Bindung, solange diese nicht gespeichert und
nachgeführt wird. Die vollständigen Regeln und Gegenfälle stehen in der
[Recherche §4.4](recherche-cad-paritaet-2026-09.md#44-sinnvolle-bezüge-zum-ausrichten--ergänzung-vom-1809).

---

## 11. Bibliotheken

**Für die Umsetzung werden zunächst die vorhandenen Bibliotheken verwendet.**
Ob sie jeden schwierigen Fall ausreichend tragen, ist Teil der jeweiligen
Machbarkeitsprüfung, besonders bei STEP-Gewinden und dem Nachbau.

| Kandidat | Belegter Stand / Prüfgrenze | Konsequenz |
|---|---|---|
| OCP / OCCT | `cadquery-ocp-novtk==8.0.1.0.0`; enthaltene `ShapeAnalysis_CanonicalRecognition` erkennt im NURBS-STEP-Gegenbeispiel sechs Ebenen und Ø6-Zylinder | Diesen vorhandenen Weg zuerst anschließen; Trägerfläche, Bohrungssemantik und stabile Referenz getrennt prüfen. API-Sonde in Recherche §5.2 |
| `planegcs` 0.8.0 | PyPI führt Wheels für CPython 3.12/3.13 auf Windows x64 und Linux x64 sowie ein Quellpaket; keine dort gelisteten 3.14-/macOS-Wheels | Kein unmittelbar passender Ersatz; Eigenbau wäre zu evaluieren, nicht grundsätzlich unmöglich |
| `py-slvs` / SolveSpace | Nach Bauplan §30.1 wegen GPL ausgeschlossen | Kein geplanter Einsatz |
| Analysis Situs | BSD-3-Clause; kanonische Umwandlung und attributierter Nachbarschaftsgraph dokumentiert; betrachteter Header hängt an Active Data | Reserve für belegte Restlücken des vorhandenen OCCT. Kein notwendiger Einbau für die bereits erfolgreiche API-Sonde; konkrete Quellteile, ABI und Plattformen offen |
| Open3D 0.20.0 | Seit 16.09.2026 CPython-3.14-Wheels, auch Windows; Ebenensegmentierung ist keine vollständige CAD-Merkmalserkennung | Nur bei gemessenem Nutzen für Aufbereitung/Segmentierung; Paketumfang und Intel-macOS-Abdeckung prüfen |
| `pyransac3d` | Apache-2.0; Zylinder-Code warnt vor unzureichender Realgeometrie-Erkennung und verwendet globalen Zufall | Nur Vergleichsbasis; eigene begrenzte Fits mit NumPy/SciPy bevorzugt prüfen. Keine fertige Bohrungssemantik, Zuordnung oder Rekonstruktion |
| CGAL Shape Detection | Das betrachtete Paket ist GPL-lizenziert | Nach Projektregel 15 ausgeschlossen |
| Point2CAD, CAD-Recode, CADFit, BRepNet | Lernende Rekonstruktion ist nach §15 kein Bestandteil dieses Vorhabens; BRepNet zusätzlich nichtkommerziell lizenziert | Keine geplante Produktabhängigkeit |
| `mesh2cad` | Mindestens zwei verschiedene Projekte: `Sanaxen/mesh2cad` und `Danxtream/Mesh2CAD-Converter` | Keine gemeinsame Leistungsbehauptung; Lizenzkette, Formtreue und tatsächlicher parametrischer Nachbau nicht nachgewiesen |

Die [vertiefte Bibliotheksbewertung](recherche-cad-paritaet-2026-09.md#5-bibliotheken-konkrete-eignung-statt-sammelliste)
enthält Primärquellen, Versionsabgleich, vorhandene Kernwerkzeuge,
Alternativen und Integrationsgrenzen. Ihre §§5.5–5.6 bewerten ausdrücklich
Eigenentwicklung in Python, Cython oder C++: eigene fachliche Erkennung,
Referenzauswahl und Bedienung; native Beschleunigung nach Messung. KI-gestützte
Implementierung ist dafür zulässig, aber kein Ersatz für unabhängige
Sollwerte, Plattformprüfung und Review. Ein eigener vollständiger B-Rep-Kern
ist durch die gefundenen Lücken nicht begründet.
Es wurde keine neue Abhängigkeit installiert oder freigegeben.

Die Paketdaten zu `planegcs` wurden am 18.09. auf der
[versionsgebundenen PyPI-Seite](https://pypi.org/project/planegcs/0.8.0/)
geprüft. Der eigene Solver bleibt die Ausgangslage. Ein Austausch verlangt
einen belegten fachlichen Vorteil sowie vollständige Plattformabdeckung;
eine einzelne Laufzeit oder fehlende Wheels entscheiden das nicht allein.

---

## 12. Umfang, Risiken und belastbare Zeitangaben

**Die früheren Tageswerte waren weder gemessene „KI-Zeit“ noch belastbare
Personentage.** Ihnen fehlten eine definierte Arbeitsweise, ein Vergleich mit
abgeschlossenen Paketen und vollständige Integrations-/Prüfkosten. Deshalb
werden sie als Planungsgrundlage zurückgezogen. Eine pauschale Umrechnung
von menschlichen Tagen in KI-Minuten wäre ebenso unbelegt.

| Bereich / Pakete | Vorhandene Grundlage | Was den Aufwand bestimmt |
|---|---|---|
| Maßeditor und sinnvolle Bezüge, P0.3/P0.4/P5.1 | Platzierungs- und Zugfelder; Oberflächenreferenzen | Einheitlicher Entwurf, ✓/×, Fokus, Tastatur, Mehrfachziel, Überdeckung und stabile Referenz während der Vorschau |
| Maße/Fits/Zuordnung, P1.1–P1.4 | NumPy/SciPy und vorhandene Erkenner | Teilflächen, Rauschen, grobe Facetten, echte Polygone, Mehrdeutigkeit, Laufzeit und Speicher bei vielen Merkmalen |
| Skalieren/Spiegeln, P2.1 | OCCT-Transformationen | Ungleichförmige Skalierung verändert Merkmalsarten; alte Maße, doppelte Merkmale und Referenzen müssen auf beiden Kernen korrekt bleiben |
| Filamentzuordnung, P2.2 | Vorhandene Zuweisungen | Flächenzuordnung nach neuer Tessellierung, Qualitätswechsel und Speicherung |
| Innenraum/Torus/Freiform/NURBS, P2.3 | Analytische OCCT-Typen und erfolgreich erprobte kanonische Erkennung | Getrimmte/angeschnittene Flächen, zusammengesetzte Merkmale, Unsicherheit und dauerhafte Identität |
| Exakte Merkmalsoperationen, P2.4 | `fill_bore`, `cut_bore`, vorhandenes Defeaturing für Verrundungen | Alle bislang unterstützten Merkmalsarten, Nachbarflächen und gleiches Ergebnis der Bedienhandlung |
| Importgewinde und Handlungen, P2.5/P2.6 | Eigene Gewindeerzeugung, `counterpart.py` | Geometrische Steigung ohne Erzeugerwissen, Händigkeit, Teilgewinde und Gegenstückplatzierung; hoher Verfahrensanteil |
| Bausteine, P2.7 | 35 Bausteine, davon 31 in der untersuchten Folge konvertierend | Je Familie exakte Werkzeuge, Attribute, Merkmale, Passungen und Bereichsprüfung; kein einzelner Massenersatz |
| Ebenen/Projektion, P3 | Skizzenlöser, OCCT-Schnitt, Konturen | Bezugserhalt über den gesamten Verlauf und fachlich getrennte Flächenkontur-/Schnittwege |
| Nachbau, P4 | Primitive, Boolesche Operationen, erkennbare Merkmale | Konkurrierende Konstruktionen, unbekannte Restform und unabhängige lokale Formprüfung; hoher Verfahrensanteil |

Die relativen Größen S/L/XL und Abnahmekriterien stehen ausschließlich in
§13.2. Vor einem Paket werden offene Machbarkeitsfragen an repräsentativen
Gegenbeispielen geklärt. Erst abgeschlossene, vergleichbare Pakete erlauben
eine Zeitspanne mit dokumentierten Annahmen. Getrennt erfassen: aktive
Entwicklung, automatisierte Rechen-/Testlaufzeit und erforderliche manuelle
Prüfung auf den Zielplattformen. Eine frühe API-Sonde ist kein fertig
integrierter Kundenweg. Auch KI-geschriebener C++-Code durchläuft diese Abnahme.

Die sieben `mesh`-Operationen (`decimate_mesh`, `remesh_*`, `smooth_mesh`,
`sculpt_strokes`, `subdivide_surface`, `pose_armature`) erzeugen
definitionsgemäß Netze und sind kein Paritätsbruch.

---

## 13. Der Umsetzungsplan

**Beginn nach bestätigter Veröffentlichung von 0.4.3.** Ein Tag oder ein
gebautes Paket allein erfüllt diese Voraussetzung nicht. Der gesamte
beschlossene Umfang bleibt erhalten; „am Stück abarbeiten“ bedeutet eine
Folge überprüfbarer Pakete, keinen einzigen großen Umbau.

### 13.1 Verträge und Koexistenz

Vor Implementierung eines Pakets werden seine Aufrufer, parallelen Kernpfade,
Cache-, Speicher- und UI-Verbraucher am dann aktuellen Stand erfasst.
Jedes Paket endet mit den betroffenen Tests, aktualisierter Doku und vor
seinem Commit dem vollständigen Tor. Geplant ist ein Commit je Paket.
Robert hat für diese Dokumentdurchsicht am 18.09. Commit und Push ausdrücklich
beauftragt; das ist kein Start der beschriebenen Implementierungspakete.

**Additiv → umschalten → abbauen:** Neue Kernzweige und Ebenenparser werden
zunächst neben den alten aufgebaut. P2.8 ist das benannte Umschaltpaket für
neue Eingaben ohne Kernwahl-Haken. Bestehende Operationsnamen, Parameter und
gespeicherte Schritte bleiben reproduzierbar; kein automatisches Umrechnen
alter Projekte. Entfernt werden erst nachgewiesen unbenutzte UI-Pfade, keine
zum Laden alter Projekte benötigten Operationen.

Das Zwischenfenster ist ausdrücklich erlaubt: Die neue Fähigkeit ist bereits
prüfbar, während die bisherige Oberfläche und die Konvertierungsmeldung noch
bestehen. Fallen Abnahmen durch, bleibt der alte Eingabeweg aktiv. Ein
Runtime-Fehler darf nicht still in einen anderen geometrischen Sinn
umgedeutet werden. Der Rückfall bei einer nicht unterstützten exakten
Bearbeitung wird vor Übernahme erklärt und als benannte Netzoperation
gespeichert.

Die Bauplanverträge werden **vor** ihrer Implementierung ergänzt:
§§9/30.1 für Ebenen, §§21/30 für Erkennung und Referenzen, §§15/16/42 für
Nachbau und Genauigkeit. Die in §14 beschlossenen Entscheidungen werden
dabei übernommen, nicht erneut zur Wahl gestellt.

### 13.2 Pakete und überprüfbare Ergebnisse

S/L/XL sind relative Größen, keine Tagesangaben. Alle noch nicht
implementierten Pakete stehen auf **geplant**; die beiden historischen
Korrekturen folgen unter der Tabelle. Jeder Tabellenpunkt umfasst Kernweg,
sämtliche Eingabewege, Übersetzungen und die jeweils betroffene Doku.

| Paket / Status | Umfang | Ergebnis und verpflichtende Abnahme |
|---|---|---|
| P0.1 / geplant | S | Positions-Dreier bleibt zusammen; Einzahltexte in Quelle und allen Katalogen; gesperrte Knöpfe erklären ihren Grund; leere Skizze antwortet. Vier Fälle aus §9.6 am tatsächlichen Bedienort prüfen |
| P0.2 / geplant | L | Konvertierung im Vorschauband vor Übernahme, Operation und Rückweg im Befund; Baumzeile bezeichnet beide Körperarten gleichwertig oder keine. Kein neuer Bestätigungsdialog |
| P0.3 / geplant | L | Gemeinsamen Maßeditor nach §10.2 additiv aufbauen: ein Entwurf, ✓/×, Enter/Escape, Vorschau und Zielumfang. Vorhandene Platzierungs-/Zugfelder nutzen; Fokusverlust schreibt nicht, Enter schreibt nur einmal. Noch kein paralleles zweites Eingabesystem |
| P0.4 / geplant | L | Referenzauswahl nach §10.3: echte Kanten/Mitten/Achsen, verständlicher Maßbezug und direkter Bezugswechsel. Unerkanntes Kreisloch gegen kleinen echten Ausschnitt prüfen; Bezüge beim Tippen/Ziehen stabil halten und fast parallele Kombinationen ablehnen. Keine flüchtige Kandidaten-ID als gespeicherter Bezug |
| P1.1 / geplant | L | Zylinder-Maßvertrag und Fit nach §4, einschließlich Kontur statt Schwerpunkt, Achse, Teilabdeckung, Unterteilung und bewusst polygonaler Gegenformen |
| P1.2 / geplant | XL | Kegel-, Kugel- und Torusfits jeweils gegen eigene Sollkörper; Radien, Lage, Achsen und Winkel prüfen. Fehlklassifikationen dürfen nicht durch gelockerte Tests verdeckt werden |
| P1.3 / geplant | L | `fits.check` mit gleicher und ungleicher Facettierung plus unabhängiger Kollisionsprobe; grobe/unsichere Maße verständlich kennzeichnen, keinen Nennwert erraten |
| P1.4 / geplant | XL | Zuordnung räumlich vorsortieren und `FEATURE_LIMIT_COUNT` anhand Laufzeit/Spitzenbedarf erhöhen. Mehr als 1000 Merkmale behalten IDs über Änderungen, Cache und Wiederöffnung; dichte/symmetrische Fälle erhalten korrekte Mehrdeutigkeit statt eines zufälligen Partners |
| P2.1 / geplant | L | `scale_object`, `fit_to_size`, Spiegelung exakt; Maße und Referenzen auf beiden Kernen nachführen. Die in §18 belegten Doppelmerkmale und alten Flächeninhalte müssen auch auf dem bestehenden Netzweg verschwinden. Ungleichförmige Skalierung eines Kreises darf keine unveränderte Kreis-/Bohrungskennung mit altem Radius hinterlassen |
| P2.2 / geplant | L | `assign_slot`, `paint_slot` erhalten B-Rep und Filamentzuweisung über Qualitätswechsel, neue Tessellierung und Speicherung; gleiches Volumen allein genügt nicht |
| P2.3 / geplant | L | `void`, `torus`, `curved_face` im exakten Kern mit derselben fachlichen Bedeutung wie am Netz. Hohlraum/Tasche, ganzer/angeschnittener Torus, Freiform/analytische B-Splines und Nahtteilungen getrennt prüfen. Die gültige NURBS-STEP-Platte aus §18 muss sechs Flächen und eine Bohrung liefern; eine Formänderung findet nie still in der Erkennung statt |
| P2.4 / geplant | XL | Senken, Verschließen und Verschieben/Drehen/Verdoppeln/Entfernen von Merkmalen exakt. Die Unterstützung aller bisher akzeptierten Merkmalsarten prüfen, nicht nur `fill_bore` auf einem zylindrischen Loch |
| P2.5 / geplant | XL | Gewindesteigung an importierter B-Spline-Geometrie bestimmen; Innen/Außen, Händigkeit, Achse, Gangzahl, Teilgewinde und unvollständige Flanken erfassen. Auch gedrehte und neu parametrisierte STEP-Flächen prüfen; geometrische Steigung nicht mit dem beliebigen Kurvenparameter verwechseln |
| P2.6 / geplant | XL | Torus ändern/verschieben/verdoppeln/entfernen, Gewinde ändern, Gewinde verschließen, Filament und Gegenstück ausbauen. Ganze Körper von Wulst/Hohlkehle unterscheiden; ein nicht abtrennbarer Torusanteil ist kein vollständiges Ringwerkzeug |
| P2.7 / geplant | XL | Alle 31 in der Stichprobe konvertierenden Bausteinpfade exakt; vollständige 35-Baustein-Matrix erstellen und weitere relevante Pfade mitprüfen. Je Baustein Körper, Schneidwerkzeug, Zugaben, eigene Merkmale, Passungen und Parameterbereich abnehmen |
| P2.8 / geplant | L | **Umschalten:** alle vier Kernwahl-Haken entfernen, neue Grundkörper bevorzugt exakt, Bearbeitung nach Körperart und Parametervertrag (§10.1). Aushöhlen offen/geschlossen/`open_at`/Entlüftung sowie optional fehlenden Kern prüfen; alte Projekte unverändert auswerten |
| P3.1 / geplant | L | Ebenenvertrag: Versatz-, Dreipunkt- und Neigungsebene gehören der Skizze. Parser, Parameterausdrücke, Rundreise und Verträglichkeit mit alten Ebenenangaben zuerst |
| P3.2 / geplant | XL | Rahmen, Referenzauflösung, Cache und Verwaisung über sämtliche Verbraucher: Skizzen-Ops, `field_ops`, `seal_ops`, Projektion. Verschieben, Drehen, Maßänderung, Kantenaufteilung und gelöschte Bezüge durchprüfen |
| P3.3 / geplant | L | Ein Eintrag „Neue Ebene …“ mit Art-Auswahl, alle drei Arten und Vorschau. Dreipunktebene anfangs mit Weltkoordinaten und ausdrücklichem Hinweis auf fehlende Körperbindung; Bedienung auf beiden Kernen |
| P3.4 / geplant | L | Flächenkontur als eigene Handlung: Außen- und Innenränder, B-Rep-Drähte und Netzränder; Schnitt bleibt eigener Weg. Kreise aus exakten Kurven beziehungsweise belegten Netzmerkmalen mit ausgewiesener Näherung |
| P3.5 / geplant | L | Exakten Ebenenschnitt über `BRepAlgoAPI_Section` anschließen und Kontur-/Schnittweg unterscheiden. Ebenen- und Konturänderungen, Undo/Redo, Speicherung und Wiederöffnung am echten Editor abnehmen |
| P4.1 / geplant | XL | Nachbaukandidaten aus belegten Grundvolumen, Aufträgen und Abzügen erzeugen. Stützebenen allein rekonstruieren keine beliebige konkave Grundform; mehrdeutige Rollen von `pin` ausdrücklich auflösen |
| P4.2 / geplant | XL | Nachbau ausschließlich mit exakter Ausgabe und unabhängiger Formprüfung nach §13.5; unbekannte Geometrie nicht weglassen. Keine Fertigungskompensation beim Kopieren erkannter Maße |
| P4.3 / geplant | L | Geprüften Nachbau hinter dem Import atomar übernehmen, importiertes Netz verbrauchen, Herkunft und nicht übertragbare Attribute ausweisen. Eine Transaktion einschließlich neuer Parameter; Undo stellt Originalzustand wieder her |
| P5.1 / geplant | XL | Maßoperationen nach §10.2 und §14.1 familienweise auf direkten Viewport-Editor umstellen: Bohrung/Platzierung → Bewegen/Drehen/Skalieren → weitere Merkmals-/Form-/Bausteinmaße. Nach bestandener Paritätsprobe die zugehörigen Panel-/Dialogeingaben entfernen. „Auf alle“ unter dem Feld, vollständige Sammelvorschau, ein Undo. Jede passende Handlung bleibt einmal erreichbar; fehlende Handlung erklären |
| P5.2 / geplant | L | Vollständige Auswahlmatrix Körper/Merkmal, Netz/B-Rep am Fenster abnehmen, Hauptwege bei geschlossenem Panel, ✓/× und Enter/Escape, Sammelziele, Abbruch und Undo. Kleines Fenster, HiDPI, hell/dunkel, lange Texte und Tastatur; Oberflächengrenzen bleiben grün |

Die geplante Operation *Gewinde ändern* durchläuft die vollständige Checkliste
für neue Ops: Register, Schema, Determinismus, Geometrie, beide Qualitätsstufen,
Befunde und alle Sprachkataloge. Bei P2.7 bleiben Bausteinversionierung,
Bereichsprüfung und Normteilmaße verbindlich. Die Umsetzung wird je
Bausteingruppe in weitere commit-fähige Teilpakete zerlegt; eine einzelne
Großänderung über alle 31 ist nicht die Paketgrenze.

**Bereits erledigt, kein neuer Bauauftrag:** `CYLINDER_SPREAD`
(`9c54ee1de`) und Merkmale bei starrer Drehung exakter Körper (`5ad173de6`).
Die exakte Spiegelung ist davon nicht mitbehoben (§17).

### 13.3 Besondere Verträge der Ebenen

Ein neues Prädikat „benötigt einen berechneten Rahmen“ darf die Bedeutung von
`is_feature_plane` nicht still ändern. Jede neue Ebenenart erhält eine
kanonische gespeicherte Definition mit endlichen Werten, Einheiten,
Orientierung und entarteten Fällen. Abstand und Winkel sollen die vorhandene
Parametergrammatik nutzen; deren Abhängigkeiten müssen auch beim Cache und
bei der Parametersuche gefunden werden.

**`edge_key` ist keine dauerhaft stabile Referenz bei Änderungen.** Der
Schlüssel enthält gerundeten Weltmittelpunkt und Richtung, bei geschlossenen
Kanten zusätzlich die Größe. Am Quader änderten sich schon bei Verschiebung
um (1, 2, 3) mm alle zwölf Schlüssel (§17). Eine geneigte Ebene braucht
zusätzlich Objektbezug, gerichteten Kantenbezug, Zuordnung und Behandlung von
Teilung/Vereinigung oder Mehrdeutigkeit. Das gleiche Format in beiden Kernen
ersetzt diese Lebenszyklusregeln nicht. Geschlossene oder gekrümmte Kanten
definieren ohne Zusatzvertrag keine einzelne Drehachse.

„Ebene an dieser Stelle festhalten“ muss den letzten gültigen Rahmen
**reproduzierbar speichern**, nicht aus einem flüchtigen UI-Cache beziehen.
Bei verlorener Referenz nach Wiederöffnung gelten dieselben Antworten;
ohne belegbaren Rahmen wird eine andere Ebene angeboten statt geraten.
Einmal beantwortete Zuordnungen, Parameteränderungen und Undo/Redo gehören
zur Abnahme. Die eingefrorene Ebene folgt dem Körper ausdrücklich nicht mehr.

Ob ein Formatsprung nötig ist, wird am finalen Speichervertrag entschieden.
Eine reine Erweiterung der bisherigen Zeichenkette kann wie zusätzliche
Bedingungsarten ohne Strukturmigration auskommen; das gilt nicht automatisch
für neue Referenz- oder Rahmenfelder. Alte Projekte müssen weiter rechnen,
neue unverständliche Angaben müssen alte Leser sicher ablehnen. Ändert sich
das Format, gelten Version, Migration und Altdateitest aus AGENTS.md.

Flächenkontur und Ebenenschnitt bleiben verschiedene Handlungen. Ein Kreis
ist nur bei Übernahme in seiner Ebene ein Kreis; geneigte Projektion kann
eine Ellipse ergeben. Am Netz ist ein Kreis eine aus Merkmalen begründete
Näherung, nicht die unveränderte Polygonkontur. Ein schlecht passendes
Merkmal darf keine falsche Kontur erzeugen. Für die zunächst übernommene
Hilfsgeometrie gilt: **Kopie, kein lebender Kantenbezug**; das wird benannt.
Assoziative Konturprojektion ist hier nicht still mitversprochen; die
Bezugsebene selbst bleibt nach den obigen Regeln assoziativ.

### 13.4 Abnahme der Parität

Der Sechs-Schritte-Weg aus §5.1 bleibt nach jedem Schritt exakt und lässt sich
als STEP exportieren und wieder einlesen. Die Form wird zusätzlich an
unabhängigen Maßen und gültiger Topologie geprüft. Derselbe Kundenweg an
einem Netz bietet dieselben fachlichen Handlungen mit erklärter Näherung.

Für jede Merkmalsart wird dieselbe Sollgeometrie in B-Rep und als Netz
geprüft. Gefordert sind passende Arten, Maße, Lage, Verhalten und zulässige
Handlungen innerhalb der jeweiligen Fehlergrenzen; **nicht** dieselbe Zahl
von Topologieflächen oder deren Roh-IDs. Die zwanzig Teilflächen einer
Verrundung müssen vor einer Gleichheitszusage fachlich gruppiert werden.
Ein als B-Spline gespeicherter Zylinder darf nicht allein wegen seines
Speichertyps zur Freiform erklärt werden.

Für Gewinde braucht es zusätzlich importierte STEP-Referenzen mit unabhängig
bekannten Maßen. Ein einzelnes selbst erzeugtes Gewinde beweist den
beschlossenen Importweg nicht. Nichtnormale oder unsichere Gewinde werden
nicht still auf den nächsten Tabelleneintrag gerundet. *Gegenstück anlegen*
erhält einen Platzierungsweg; bis zur Übernahme bleibt es Vorschau.
Die Eigenachsendrehung eines rotationssymmetrischen Torus ist wirkungslos;
das verbietet nicht jede Änderung seiner räumlichen Ausrichtung.

### 13.5 Abnahme des Nachbaus

Der Nachbau erzeugt eine **neue** Konstruktionsfolge, nicht die ursprüngliche
Historie (§42). Jede erzeugende Op muss tatsächlich B-Rep liefern:
`create_cylinder` und `create_torus` sind heute Netzoperationen; der
Zylinder benötigt den exakten Pfad, für den Torus ist vor dem Nachbau ein
exakter Erzeugungsweg erforderlich. Ein STEP-fähiges Ziel entsteht nicht
allein durch eine Liste registrierter Ops.

`DrillParams.compensate` ist standardmäßig `True`. Beim Übernehmen gemessener
Geometrie wird Fertigungskompensation ausdrücklich abgeschaltet; Materialprofil
und Spiel dürfen die zurückgewonnene Form nicht nebenbei verändern.
Angenommene Maße und Mehrdeutigkeiten werden vor der Übernahme sichtbar.

Vor Freigabe werden zwei benannte Grenzen festgelegt: maximale lokale
Formabweichung in mm und ergänzende Volumenabweichung. Numerik,
Facettierung, Fitunsicherheit, Prüfabtastung und Fertigungsspiel sind getrennt
zu budgetieren (Bauplan §11.2). `MAX_FACET_SAG` gilt nicht automatisch für
fremde STL-Dateien; `match_tolerance()` ersetzt keinen Rekonstruktionsvertrag.

Die Prüfung umfasst gültigen Solid, Komponenten/Hohlräume, beidseitigen
Oberflächenvergleich, Lochlagen, Achsen, Durchmesser und Wand-/Bodenstärken.
Volumen und Schwerpunkt ergänzen diese lokalen Prüfungen. Eine Stichprobe
belegt keinen exakten Maximalabstand; Auflösung und verbleibende Unsicherheit
sind Teil ihres Nachweises. Gleiches Volumen bei versetztem Loch ist eine
verpflichtende Negativprobe.

Positive Kandidaten: `plate_holes`, `plate_countersunk` und
`plate_coarse_slots`; danach die weiteren Grundformen aus §8.2. Bei
`bridge_two_end_supports` und `island_tower` wird der **falsche Vollquader-
Kandidat** verworfen, nicht der Dateiname dauerhaft gesperrt. Eine später
korrekte Rekonstruktion darf die Formprüfung bestehen. Unbekannte Geometrie
bleibt ein erklärter Ablehnungsgrund; nichts wird unbemerkt weggelassen.

Kandidat und Vergleich entstehen vor der Dokumentänderung, abbrechbar und mit
Fortschritt. Erst die Übernahme verbraucht das Original hinter dem Importschritt.
Eine Transaktion umfasst Ops, neue Projektparameter und alle Attributänderungen.
Abbruch oder Absage erzeugt keinen Teilverlauf; Undo/Redo und Wiederöffnung
stellen denselben Zustand her. Änderungen eines nachgebauten Maßes werden
gegen die nachfolgenden Schritte geprüft. Bestehende nachgelagerte Bezüge
dürfen nicht ohne gültige Zuordnung auf das Ergebnis umgebogen werden.

Herkunft und ursprüngliche Quelldaten bleiben erhalten. Neue Modellierung
begründet keine neuen Nutzungsrechte. Filamentzuweisung, geschützte Nähte
und andere nicht übertragbare Attribute werden am jeweiligen Modell vor
Übernahme genannt. RM-022 wird beim Start dieses Pakets wie beschlossen
neu gefasst; die heutige Dokumentdurchsicht ändert das Register nicht.

### 13.6 Abhängigkeiten und Nachweis je Paket

| Voraussetzung | Verbraucher |
|---|---|
| Veröffentlichung 0.4.3 bestätigt | alle Implementierungspakete |
| P0 | kann unabhängig von der neuen Geometrie umgesetzt werden |
| P1.1–P1.3: Maßvertrag und Fits | P2-Merkmalshandlungen und P4-Formprüfung |
| P1.4: Zuordnungsbudget | große Merkmalskorpora; keine ungemessene Grenzerhöhung |
| P2.1–P2.7 und Handlungsmatrix grün | P2.8: Kernwahl-Haken entfernen |
| P3.1: gespeicherter Ebenenvertrag | P3.2–P3.5; Parser allein genügt nicht |
| passende exakte Erzeuger, Maßvertrag und unabhängige Formprüfung | P4-Übernahme; keine Pflicht, zuvor sämtliche Skizzenfunktionen zu verbrauchen |
| P2-Handlungen festgelegt | P5 endgültige Gliederung; Entwurf und bestehende Bedienfehler können früher geprüft werden |

Pro kleinem Schritt wird der Importgraph mit **den eigenen geänderten
Produktionspfaden** befragt, beispielsweise:

```powershell
.venv/Scripts/python.exe tools/affected_tests.py app/core/perceive/features.py --run
.venv/Scripts/python.exe tools/affected_tests.py app/core/brep/features.py --run
.venv/Scripts/python.exe tools/affected_tests.py app/core/sketch/planes.py app/core/sketch/serialize.py --run
```

Die Beispiele sind je Paket um alle tatsächlich geänderten Pfade zu ergänzen.
Verpflichtende direkte Anschlussprüfungen je Gebiet:

| Pakete | Bereits vorhandene Testorte, um die neuen Fälle zu ergänzen |
|---|---|
| P0/P5 | `test_feature_panel.py`, `test_interface_limits.py`, `test_sketch_editor.py`, `test_translations.py`; tatsächliches Fenster zusätzlich |
| P1 | `test_features.py`, `test_matching.py`, Passungsprüfung durch `fits.check` |
| P2 | `test_brep.py`, `test_exact_thread_features.py`, `test_geometry_review_regressions.py`, Baustein- und Attributtests |
| P3 | `test_sketch_serialize.py`, `test_sketch_ops.py`, `test_sketch_end_to_end.py`, `test_orphans.py`, `test_project.py` |
| P4 | Korpus plus `test_history.py`, `test_project.py` und neue negative Formvergleiche |

Die 3,2-Millionen-Dreiecke-Probe bleibt ein gesonderter Leistungsnachweis
mit Laufzeit und Spitzenbedarf. Sie wird nicht als teurer Standardfall an
jede kleine Änderung gehängt. Die bestehende Regression bis 815 104 bleibt;
die Anwendungsgrenze aus RM-042 ist unabhängig von einem direkten
Erkennungsaufruf zu prüfen. Bei P1.4 ist auch der ungünstige Fall räumlich
dichter und symmetrischer Merkmale zu messen.

Vor jedem Paketcommit gilt das vollständige Tor über den Skill
`pruefen`; ein roter Schritt wird nicht auf den nächsten gestapelt.
Testzahlen und Exit-Codes werden erst nach dem jeweiligen Lauf eingetragen.
Offscreen prüft keine gerenderte Auswahl und keine tatsächliche
Zeigerbedienung; die Fensterabnahme und neue OCP-Imports im gebauten Paket
auf allen Zielplattformen bleiben eigene Nachweise.

**Übergabe je Paket:** Ausgangs-/Endcommit, eigene Pfade, erfüllte
Abnahmepunkte, genaue Befehle mit Testzahlen/Exit-Codes, offene manuelle oder
Paketprüfungen, Format-/Cacheänderungen und Rückfallweg dokumentieren.
Konzeptabweichungen ausdrücklich begründen. Nicht gemessene Zahlen bleiben
offen; ein erfolgreiches Teilpaket erledigt nicht die ganze Stufe.

### 13.7 Entscheidungen vollständig zugeordnet

| Entscheidungen aus §14 | Umsetzung |
|---|---|
| 1, 2, 16 | Umfang, Release-Sperre und P0 |
| 3 | gesamte P2-Reihe einschließlich P2.7 |
| 4 | P2.8 nach bestandener Handlungsmatrix |
| 5, 9, 10, 15 | P2.3, P2.5, P2.6 |
| 6, 11, 13 | P3.1–P3.5, einschließlich vorgezogener Bauplanverträge |
| 7, 14 | P4.1–P4.3 |
| 8 | P5.1/P5.2 |
| Ergänzung 18.09. (§14.1) | P0.3/P0.4, danach P5.1/P5.2 |
| 12 | P1.4 |

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
Körper" für den Kunden nicht mehr vorkommt — weil beide dieselben fachlichen
Handlungen anbieten und Maße sowie Grenzen
verständlich ausweisen. Die jeweiligen Näherungsfehler und nicht sicher
bestimmbaren Merkmale werden dadurch nicht aufgehoben.

### 14.1 Ergänzende Bedienentscheidung vom 18.09.2026

Nach der vertieften Prüfung ergänzt Robert die obigen Entscheidungen:
**Direkter am Modell arbeiten, weniger Dialoge und Panelbedienung.** Maße
werden im Viewport mit abgesetztem Eingabefeld sowie ✓/× angeboten, auch
beim Bewegen und weiteren geeigneten Operationen. „Auf alle“ steht unter dem
Feld; das Panel trägt keine doppelten Maßfelder. Sinnvolle, hervorgehobene und wechselbare Kanten-/Merkmalsbezüge gehören
zur Ausrichtung dazu. Vertrag und Übergang stehen in §§10.2–10.3,
Umsetzung in P0.3/P0.4/P5.1/P5.2. Der Start nach Veröffentlichung von
0.4.3 bleibt bestehen. Dies ist eine Ergänzung, keine rückwirkende Änderung
der 16 Entscheidungen vom 17.09.

---

## 15. Was hier ausdrücklich **nicht** gebaut wird

0. **Keine Baugruppen und keine Zeichnungsableitung** (Robert, 17.09.2026).
   Sie waren — anders als die erste Fassung behauptete — nie abgelehnt, nur nie
   beauftragt; an diesem Tag sind sie es. Für Baugruppen gilt zusätzlich die
   technische Lage: flache Szene ohne `parent_id`, 3MF wird beim Einlesen
   verflacht. Eine vollständige aktuelle Prüfung verfügbarer 3D-Löser liegt
   hier nicht vor; aus der kleinen Kandidatenliste folgt keine allgemeine
   Nichtverfügbarkeit. **Bauplan §18.3 widerspricht der Entscheidung nicht:**
   Er verlangt Messbemaßungen im Viewport, kein technisches Zeichnungsblatt.
   Diese Messfunktion bleibt erhalten.
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
und §18.3 sagt Messbemaßungen im Viewport zu, keine Zeichnungsableitung.
Die ausdrückliche Abgrenzung für dieses Vorhaben steht jetzt in §14.

**16.2 „183 Aufrufe von `as_mesh_data`" — trägt nichts.** Eine Grep-Zahl: zwei
Drittel sind Typ-Engführungen oder lesende Anzeigepfade. Die belastbare Zahl
steht in §5 und ist am Ergebnis gemessen.

**16.3 Die Zeichnungsableitung hat unterschiedliche Voraussetzungen** (§7.1).
Die erste Fassung leitete aus einer HLR-Klasse einen kleinen Gesamtaufwand
ab. Auch der umgekehrte Schluss „am exakten Körper billig“ geht zu weit:
Die Probe misst keine fertige Zeichnung mit Maßbezügen und lesbarem Layout.

**16.4 „Bezugsebenen gibt es gar nicht" war zu grob** (§6.1), und **„torus und
thread tragen null Operationen" ist als Zählung richtig, als Aussage über den
Bedienstand zu grob**: 78 Operationen gelten dem Körper und greifen auch an
einem Torus; am Gewinde läuft die Gewindepassung ohne einen einzigen
`applies_to`-Eintrag. Richtig ist: *Es sind die einzigen zwei Merkmalsarten
ohne eigene Merkmalsoperation.*

Zwei Funde stammen aus der Prüfung selbst. Der erste — ein `Solid` führt seine
Merkmale nach einer Drehung nicht nach — ist **noch am selben Tag behoben**
(`5ad173de6`), zusammen mit dem `CYLINDER_SPREAD`-Befund aus §4.5
(`9c54ee1de`). Der zweite betraf RM-128: Dort standen `face` und
`edge_loop` als Arten ohne Operation — gemessen tragen sie 43 und 1
`applies_to`-Einträge; ohne solche Einträge sind `torus` und `thread`.
Der Roadmap-Text ist mit der Vertiefung vom 18.09. korrigiert; die
Registerzählung ersetzt weiterhin keine vollständige Bedienprüfung.

**Und die Lehre, die dieses Papier sich selbst erteilt hat:** Die erste Fassung
warnte in ihrem Schlussabschnitt davor, eine geerbte Ablehnung weiterzureichen,
ohne ihre Messung nachzufahren — und tat im selben Dokument genau das. Wer hier
später liest, misst am Code nach, bevor er es glaubt.

---

## 17. Technische Gegenprüfung vom 18.09.2026

Die sechzehn Produktentscheidungen wurden nicht geändert. Korrigiert wurden
deren technische Begründung und Umsetzungsvoraussetzungen.

| Befund | Korrektur |
|---|---|
| Die Formel für Zylinderschwerpunkte wurde auf vier Fitarten verallgemeinert | Geltungsbereich eingegrenzt; eigenständige Formverträge und Gegenproben (§4) |
| Soll-Durchmesserdifferenz wurde mit realem Passungsspiel gleichgesetzt | Kollisionsgegenprobe; Netzkontur, geschätztes Maß und Fertigungsspiel getrennt (§4.2) |
| Hüllfit und drei rote Prototyptests galten als fast fertiger Fix | Unterteilungsabweichung und ungesicherte Prototypzahlen benannt; keine bloße Lockerung der Tests (§4.3) |
| Volumengleichheit sollte den Nachbau freigeben | Beidseitige Form-, Maß- und Topologieprüfung; Gegenprobe mit versetzter Bohrung (§13.5) |
| Netz-Erzeuger und voreingestellte Bohrungskompensation sollten exakte Rekonstruktion tragen | Ausgabeart jeder Op belegen; Kompensation beim Nachbau abschalten (§13.5) |
| Aushöhlen wurde bei „geschlossen“ an den oben öffnenden exakten Zweig geroutet | Entscheidungstabelle nach tatsächlicher Wirkung (§10.1) |
| `edge_key` galt als ausreichender assoziativer Bezug | Objektbezug, Zuordnung, Orientierung, Verwaisung und gespeicherter Rückfallrahmen ergänzt (§13.3) |
| Keine Zeichnungsableitung galt als Widerspruch zu §18.3 | Messbemaßung im Viewport bleibt; kein Widerspruch zur ausgeschlossenen Zeichnungsableitung (§15) |
| „Alles ist ungebaut“, bereits erledigte Punkte und Indexstatus widersprachen sich | Stand getrennt; auch vorhandene Erzeugerbenennung exakter Gewinde berücksichtigt; Paketstatus und Entscheidungszuordnung ergänzt (§13) |
| Tageswerte, HLR, Rastertreffer und Offscreen-Proben wurden überdehnt | Messung, historische Angabe, Schätzung und ausstehende Abnahme getrennt |

### 17.1 Stand und tatsächlich ausgeführte Prüfungen

`2148ddfa` ändert gegenüber `60f052d1` ausschließlich dieses Konzept und
seinen Index. Die ersten beiden Testbefehle unten liefen auf `60f052d1`;
ihr Anwendungscode ist auch am geprüften `2148ddfa` unverändert.
Der dritte Testbefehl und die späteren Sonden liefen auf `2148ddfa`.

Umgebung: Windows, lokale `.venv`, Python 3.14.2, NumPy 2.5.3,
SciPy 1.18.1, trimesh 5.1.0, cadquery-ocp-novtk 8.0.1.0.0.
Python erfüllt `requires-python >=3.14`, weicht aber vom dokumentierten
Entwicklungs-/CI-Stand 3.14.7 ab. Dies sind lokale Nachweise, keine
Plattform- oder Paketfreigabe.

**Vorhandene Regressionstests: drei Prozesse, jeweils Exit 0, zusammen neun
bestandene Testfälle.**

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_features.py::test_bores_survive_any_triangle_count tests/test_features.py::test_the_spread_of_a_bore_does_not_follow_the_triangle_count tests/test_features.py::test_a_coarsely_facetted_bore_survives_a_dense_triangulation
# 3 passed in 14.30s
.venv/Scripts/python.exe -m pytest -q tests/test_matching.py::test_mirroring_keeps_the_pin_that_an_operation_made tests/test_geometry_review_regressions.py::test_pattern_copies_remain_exact
# 3 passed in 5.12s; lineares und kreisförmiges Muster parametrisiert
.venv/Scripts/python.exe -m pytest -q tests/test_exact_thread_features.py
# 3 passed in 1.56s, auf 2148ddfa
```

Der Spiegelungstest prüft den Mesh-Pfad und beweist **nicht** den Erhalt am
B-Rep. Die separate Sonde unten zeigt dort weiterhin die Lücke.

**Vom Projektwerkzeug zugeordnete Prüfungen der Dokumentänderung:**

```powershell
.venv/Scripts/python.exe tools/affected_tests.py konzepte/konzept-vollwertiges-cad-2026-09.md konzepte/README.md --run
```

Das Werkzeug wählte `tests/data/make_corpus.py`, `tests/test_examples.py`,
`tests/test_public_php_security.py` und `tests/test_toolchain.py`.
Erster Prozess: **82 bestanden, 140 übersprungen**, 31,14 s, Exit 0.
Zweiter Prozess: **99 bestanden, 1 übersprungen**, 5,43 s, Exit 0.
Auch der Werkzeugprozess endete mit Exit 0. Zusammen mit den gezielten
Regressionen sind das **190 bestandene und 141 übersprungene Testfälle**;
übersprungene Fälle gelten nicht als Abnahme. `git diff --check` ist sauber.
Die 16 Entscheidungszeilen wurden gegen HEAD unverändert geprüft, ebenso
Abschnittsfolge, Codeblöcke, lokale Dokumentverweise und benannte Testdateien.

**Register und numerische Sonden, getrennt von der Testsuite:**

- `bootstrap.load_operations()` ohne Nutzerbausteine: 132 Ops, 15 belegte
  Kategorien, alle `reversible`; `PARTS.all()`: 35 Bausteine;
  `FeatureKind`: 12 Arten; `solver._CONSTRAINT_TARGETS`: 15 Bedingungen.
- Projektion: `tests/data/meshes/plate_holes.stl` mit trimesh als Mesh laden;
  für jede Fläche aus `detect_faces` ihren Rahmen mit
  `frame_of(normal, centre)` bilden; leere `Sketch` an `edit.project`
  geben. Sechs `ValidationError`; auf `plane:xy` ohne Flächenrahmen
  392 Hilfsstrecken. Das prüft den Kernaufruf, keine Zeigergeste im Fenster.
- Radiusreihe: zentrierte Box 90 × 90 × 8 mm minus zentrierter Zylinder
  Höhe 20 mm, Sollradius und Facettenzahl aus §4.2,
  `difference(..., engine="manifold")`, dann `forget_cache()` und
  `detect_holes(MeshData.of(body))`. Ergebnisse wie in §4.2; zusätzlich
  Ø50 mit 32 Facetten: 49,7860 mm, Ø5,2 mit 8/12 Facetten: keine Bohrung.
- Exakte Spiegelung: `Document` mit `create_brep_box` 40 × 30 × 20 mm,
  anschließend `mirror_object(axis="x")`, Eingabe/Ausgabe `obj_1`;
  `evaluate` mit Profil Centauri Carbon 2 / PETG, Qualität `fine`.
  Kein angehaltener Schritt, `kind="brep"` vorher/nachher, Merkmale 6 → 0.
- Kantenschlüssel: `edit.box(40, 30, 20)`, `edit.edges_of` und `edge_key`;
  nach `edit.transformed` mit Translation (1, 2, 3) mm erneut erfassen.
  Je zwölf Schlüssel, **keine** gemeinsame Kennung.
- Passungsgegenprobe: zentrierte Box 60 × 60 × 8 mm minus 16-Eck-Zylinder
  Ø30, Höhe 12 mm; darin ein koaxialer 64-Eck-Zapfen Ø29,6, Höhe 6 mm.
  Differenz und Schnitt über manifold, keine Materialkompensation.
  Positives Schnittvolumen **14,8330 mm³**; unabhängig erklärt durch
  Loch-Inkreis-Ø29,4236. Die beiden Ø20-Kontrollfälle aus §4.2 haben
  Schnittvolumen null. Beim Auslesen der leeren Schnitte meldete trimesh
  eine RuntimeWarning zur Schwerpunktberechnung; diese Sonden sind deshalb
  ausdrücklich kein warnungsfreier Pytest-Lauf.

Die zuletzt genannten sechs Messschritte lassen sich mit den benannten
Parametern wiederholen. Unabhängige Sollwerte sind Kreisgeometrie,
Dimensionsvorgaben und der erwartete Erhalt der Referenzen; sie werden
nicht aus dem untersuchten Ergebnis zurückgerechnet.

### 17.2 Grenzen dieser Durchsicht

Nicht wiederholt wurden die historischen 20-/56-Operationsproben, die
Prototyp-Fitfamilie, das Filament-Rack, Solverzeit, HLR-/Nähversuche oder
Offscreen-Klickzahlen. Sie bleiben berichtete Messungen vom 17.09., bis
Eingaben, Skript, Commit und vollständiges Protokoll gesichert sind.
Ihre weitergehenden Schlussfolgerungen wurden entsprechend begrenzt.

In diesem ersten Prüfabschnitt liefen kein vollständiger Torlauf, keine neue
Fensterabnahme, keine Paketbauten, kein 3,2-Millionen-Dreiecke-Lauf und kein
Nachbauprototyp. Die anschließende Vertiefung mit begrenzter nativer Fahrt
und weiteren Tests steht in §18. Anwendungscode wurde nicht geändert.


---

## 18. Vertiefte Recherche zu Erkennung, Bibliotheken und Bedienung

Die [Recherche vom 18.09.](recherche-cad-paritaet-2026-09.md) ergänzt die
vorherige Gegenprüfung um Primärquellen, weitere Auswertungssonden und einen
begrenzten nativen Windows-Ablauf. Sie ersetzt keine vollständige
Produktabnahme. Ihre wichtigsten Konsequenzen für diesen Plan:

1. **B-Rep ist nicht automatisch analytisch erkennbar.** Eine gültige
   NURBS-Platte mit Bohrung verliert alle sieben Merkmale; auch nach STEP-
   Schreiben und -Lesen. P2.3 muss kanonische Erkennung von analytischen
   B-Splines einschließen. Die vertiefte API-Sonde erkennt mit dem bereits
   installierten OCCT sechs Ebenen und den Ø6-Zylinder. Diesen Weg zuerst
   anschließen; Analysis Situs bleibt ein Kandidat für nachgewiesene Restlücken.
2. **Skalierung betrifft beide Kerne.** Ein auf Faktor 2 skalierter Quader
   trägt zwölf statt sechs Flächenmerkmale, darunter alte Flächeninhalte.
   P2.1 benötigt einen korrekten Transformationsvertrag und eindeutige
   Zuordnung, nicht nur einen neuen exakten Erzeuger.
3. **Gleiche Bedienung braucht einen gemeinsamen fachlichen Vertrag:**
   Form, Maßherkunft, Nachweisqualität, Referenz und verfügbare Handlung.
   Ein RANSAC-Zylinder ist noch keine Bohrung; ein erkannter Bereich ist
   noch nicht zwangsläufig sicher lokal änderbar.
4. **Native Prüfung präzisiert die Oberflächenkritik.** STL-Import,
   Auswahl und Fokuswechsel wurden gefahren. Das Bohrungsfenster trägt
   19 fachliche Eingabefelder; die alte Zählung 36 wird nicht fortgeführt.
   Übernahme, Undo und der vollständige STEP-Vergleich bleiben nativ offen.
5. **907 zusätzliche Testfälle bestanden** in zwei gezielten Läufen
   (356 Geometrie/Skizze/Erkennung/Passung, 551 Oberfläche/Bedienlogik).
   Die neuen Gegenbeispiele sind dadurch nicht behoben; sie zeigen fehlende
   Abdeckung. Zehn definierte Kundenwege und eine Darstellung/Merkmal/
   Handlung/Zustand-Matrix bilden die Abnahme, keine bloße Registerzahl.
6. **Eigenentwicklung gezielt einsetzen.** Recherche §§5.5–5.6 ordnen
   Python, vorhandenes Cython und mögliche C++-Ergänzungen konkreten Aufgaben
   zu: fachliche Erkennung, stabile Bezüge, Maßbedienung und gemessene
   Rechenengpässe. Kein neuer Gesamtgeometriekern und kein Bibliothekswechsel
   ohne belegten Vorteil. Die alten Tageswerte sind zurückgezogen (§12).

Die Priorität lautet: falsche Maß-/Referenznachführung beheben, Erkennung
vervollständigen, Handlungen auf beiden Kernen durchgängig anschließen,
Bedienwege direkt am Modell mit Maßfeldern und ✓/× abnehmen (§10.2),
anschließend den geprüften Nachbau ausbauen. Zusätzliche
CAD-Funktionen aus der Recherche sind als Vorschläge gekennzeichnet; die
16 Entscheidungen und der Start nach Veröffentlichung von 0.4.3 bleiben
unverändert. RM-188 führt den Gesamtumfang, RM-022 den Nachbau.
