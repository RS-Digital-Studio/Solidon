# Konzept — ein eingelesenes Netz verrunden

Stand 23.08.2026.

Anlass: Der Registerpunkt „Verrundung und Fase gehen auf einem Netz nicht" ist
der teuerste im ganzen Register. Der Lauf über neun heruntergeladene Modelle
hat gezeigt, dass man **bei jedem der neun** dagegenläuft: Wer eine STL lädt,
kann sie nicht verrunden. Das ist Weg 1, der häufigste Weg, und damit die
häufigste Enttäuschung.

Dieses Dokument beantwortet **nicht**, ob wir das bauen. Es beantwortet, **was
es wäre** — damit die Entscheidung an Zahlen hängt und nicht an einem Gefühl.

Bezug: Bauplan §30 (zweiter Kern, die Einbahntür), §21.1 (Merkmalserkennung),
§25 (Operationskatalog), AGENTS.md („Was NICHT gebaut wird").

---

## 1. Was heute passiert

`fillet_edges` und `chamfer_edges` tragen `requires_kind="brep"`. Ausgewertet
wird das nur in der Oberfläche (`app/ui/labels.py`, `app/ui/main_window.py`) —
der Menüeintrag ist ausgegraut. Es gibt keinen Fehler, keinen Vorschlag und
keinen Weg; das Handbuch sagt dazu bloß „Verrundung, Fase oder STEP sind
ausgegraut".

Der Bauplan führte „Verrundungen auf Mesh-Kanten **vor dem B-Rep-Kern**" unter
dem, was nicht gebaut wird. Der Kern steht inzwischen. Die Aussage ist damit
nicht mehr, dass es verboten ist, sondern dass niemand gesagt hat, was danach
gilt.

## 2. Warum man ein Netz nicht einfach hineinreicht

Der naheliegende Gedanke ist, das Netz mit `BRepBuilderAPI_Sewing` zu einem
Körper zu nähen und darauf zu verrunden. Gemessen an
`tests/data/meshes/block_with_rounded_edge.stl`:

| | |
|---|---|
| Netz | 108 Dreiecke |
| nach dem Nähen | **108 Flächen, 324 Kanten** |

**Jede Dreiecksseite wird eine Kante.** Ein `fillet` darauf verrundete nicht die
Modellkante, sondern jede einzelne Facette — das Ergebnis wäre unbrauchbar und
der Lauf langsam. Das ist kein Umsetzungsproblem, sondern die Sache selbst:

> Ein Netz hat keine Kanten im B-Rep-Sinn. Es hat Dreiecke, die zufällig an
> Modellkanten aneinanderstoßen.

Was fehlt, ist also nicht ein Aufruf, sondern die **Rückgewinnung der echten
Flächen**.

## 3. Was dafür schon steht

Die Merkmalserkennung deckt Netze inzwischen vollständig ab. Gemessen am
23.08.2026, gezählt **nur über flächige Merkmale** — `edge_loop` ist
herausgerechnet, sonst schmeichelt die Zahl:

| Korpus | Dreiecke | gedeckt | erkannte Arten |
|---|---|---|---|
| organisch (`generated_body`) | 3364 | 100,0 % | `edge_loop`, `sphere` |
| `block_with_rounded_edge.stl` | 108 | 100,0 % | `face`, `fillet` |
| `plate_holes.stl` | 796 | 100,0 % | `face`, `hole` |
| `clean_figure.stl` | 738 | 100,0 % | `face`, `pin`, `sphere` |
| `post_with_fillet.stl` | 2704 | **89,3 %** | `face`, `pin`, `torus` |

**Das ist der Grund, warum die Frage jetzt gestellt werden kann und vorher
nicht.** Bis zum 22.08.2026 lieferte die Erkennung Ebenen und Bohrungen; seit
dem 23.08. kommen Kegel, Kugel, Torus und Verrundung dazu (§21.1, Commits
`9cedb94`, `fda888d`, `e3b01b7`, `25163ff`). Die Vorarbeit für eine
Flächenrückgewinnung ist gebaut worden, ohne dass jemand sie so genannt hat.

## 4. Der Weg, in fünf Schritten

1. **Merkmale erkennen.** Steht. 89–100 % Deckung, siehe oben.
2. **Je Merkmal eine analytische Fläche bauen.** OpenCASCADE hat alle fünf
   Arten, die die Erkennung liefert: `Geom_Plane`, `Geom_CylindricalSurface`,
   `Geom_ConicalSurface`, `Geom_SphericalSurface`, `Geom_ToroidalSurface`. Die
   Parameter liegen im Merkmal (Mittelpunkt, Achse, Radien).
3. **Schnittkurven zwischen benachbarten Flächen berechnen.** Die schwere
   Stelle, siehe §5.
4. **Nähen, Solid bilden, `ShapeFix`.** Handwerk, kein offenes Problem.
5. **`fillet_edges` wie auf jedem exakten Körper.** Steht seit dem B-Rep-Kern.

## 5. Die schwere Stelle, und drei offene Fragen

**Schritt 3 ist der Punkt, an dem es eine Phase braucht und keine Sitzung.**

**Erstens: Die Erkennung liefert keine Nachbarschaft.** Ein `Feature` trägt
seine Dreiecke (`face_indices`), aber nirgends steht, welche Fläche an welche
grenzt. Auf der B-Rep-Seite ist das eine Kante; auf der Netzseite müsste man es
aus den geteilten Dreieckskanten erschließen. Das ist machbar — die
Nachbarschaftskarte in `brep/features.py::_rounded_neighbours` löst dieselbe
Frage für den exakten Kern und könnte Vorbild sein.

**Zweitens: Die Toleranzen der Einpassung müssen irgendwo aufgefangen werden.**
Ein eingepasster Zylinder trägt einen Rückstand von bis zu 0,02 mm
(`CYLINDER_SPREAD`); die Ebene daneben ebenso. Ihre Schnittkurve liegt damit
nicht genau dort, wo die Dreiecke sie zeigen. Was das für die Maßhaltigkeit
bedeutet, ist ungemessen — und es ist die Frage, an der ein Kunde merkt, ob das
Ergebnis brauchbar ist.

**Drittens: Was passiert mit dem Rest?** Bei `post_with_fillet.stl` tragen
10,7 % der Dreiecke kein flächiges Merkmal. Drei Wege sind denkbar, und keiner
ist umsonst: als Freiformfläche annähern (teuer, ungenau), den Körper
zurückweisen (ehrlich, aber der Kunde steht wieder ohne Weg da), oder nur die
erkannten Teile exakt machen und den Rest als Netz behalten (ein Zwitter, den
der Bauplan nicht kennt).

## 6. Was es nicht ist

- **Kein Ersatz für den Import.** Wer eine STEP-Datei hat, soll sie laden; die
  Rückgewinnung ist für den Fall, dass es nur ein Netz gibt.
- **Keine Zusage auf jedes Netz.** Ein gescannter Körper oder eine erzeugte
  Figur hat keine analytischen Flächen. Für die bleibt es beim Netz, und das
  muss die Oberfläche sagen können, bevor der Kunde es versucht.
- **Keine Rücknahme der Einbahntür (§30).** Der bestehende Weg B-Rep → Netz
  bleibt, wie er ist. Hier entsteht ein **neuer** Weg, der aus einem Netz einen
  *neuen* Körper rechnet — nicht denselben zurück.
- **Kein stiller Umbau.** Was der Kunde bekommt, ist ein anderer Körper als
  sein Netz: analytisch statt facettiert, maßhaltig im Rahmen der Einpassung.
  Das gehört ihm gesagt, und die Provenienz gehört ausgewiesen (§22.5 denkt
  denselben Gedanken für Kennzahlen).

## 7. Was zu entscheiden ist

**Nicht: „bauen wir das?" — sondern: „ist das eine Phase wert?"** Die fünf
Schritte sind kein Commit und keine Sitzung; Schritt 3 allein trägt drei offene
Fragen, von denen die zweite (Toleranz) erst nach dem Bauen messbar wird.

Dagegen steht der Kundenwert, und der ist der höchste im Register: **neun von
neun** heruntergeladenen Modellen laufen heute dagegen.

Ein Zwischenschritt, der billig ist und heute schon hilft, ohne die
Entscheidung vorwegzunehmen: Die ausgegrauten Einträge sagen nicht, **warum**
sie ausgegraut sind. Ein Satz an dieser Stelle — „geht nur auf exakten Körpern,
Ihr Modell ist ein Netz" — kostet nichts und nimmt dem Kunden das Rätselraten.
Das ist Oberfläche und gehört nicht in dieses Konzept, aber es gehört genannt,
damit die große Entscheidung nicht die kleine blockiert.
