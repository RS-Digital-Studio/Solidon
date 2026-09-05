# `app/core/brep/` — der zweite Konstruktionskern

Boundary Representation über OpenCASCADE, **neben** dem Mesh-Kern, nicht an
seiner Stelle (§30).

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
| `ops.py` | Die B-Rep-Operationen im Register (§25, §10) |
| `edit.py` | Einen Körper formen |
| `features.py` | Merkmale aus der Topologie (§30, §21) |
| `step.py` | STEP hinein und hinaus |

## Grenzen

- **Kein zweiter Wahrheitsbegriff.** Weicht B-Rep vom Mesh-Kern ab, ist das
  ein Befund, kein „beide haben recht".
- Verrundungen auf Mesh-Kanten bleiben ungebaut, solange dieser Kern der Ort
  dafür ist.
