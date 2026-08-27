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
