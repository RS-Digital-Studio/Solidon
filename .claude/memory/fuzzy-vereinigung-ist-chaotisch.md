---
name: fuzzy-vereinigung-ist-chaotisch
description: "Die Boolesche Vereinigung eines gesweepten Gewindegangs mit dem Kern verschluckt den Gang still; welche Fuzzy-Stufe ihn rettet, wechselt je Größe und Länge — nähen statt vereinigen."
metadata: 
  node_type: memory
  type: project
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-20T22:42:56.975Z
---

Rasterfahrt vom 21.09.2026 (P2.7a, sechs Gewindegrößen M3 bis M10, drei Längen,
Fuzzy-Stufen 1e-3, 3e-3, 1e-2 mal Steigung auf privaten Kopien): Die plain
Vereinigung von Kern und gesweeptem Gang gab in **jedem** Fall den nackten Kern
zurück — gültig, geschlossen, ein Körper, Volumen des Kerns. Die rettende
Stufe war je Fall eine andere (M3 × 0,5: L6 → 1e-2, L8 → 1e-3, L12 → 3e-3),
zwei Fälle (M5 × 0,8 L8, M6 × 1 L8) fanden keine, jede Stufe kostete 7 bis
24 Sekunden. Das Ergebnis hängt an Details wie Sockeltiefe, Vorlaufwindung
und Zuschnittradius und ist damit nicht vorhersagbar.

**Why:** Die Flanke des Gangs ist eine BSpline-Regelfläche, der Kern ein
Zylinder; OCCT findet ihre Schnittkurve nur mit Toleranz, und ohne sie
klassifiziert es den Gang als „innen“ und lässt ihn weg. „Gültig und
geschlossen“ ist deshalb kein Beleg — der nackte Kern ist beides.

**How to apply:** Ein Gewinde exakt bauen heißt nähen, nicht vereinigen:
`profiles.helical_thread` baut Kern und Gang aus Flächen mit geteilten
Helixkanten (44 Flächen, 30 ms, Volumen gegen Pappus auf 2·10⁻⁷). Wer die
Vereinigung trotzdem braucht (`threaded_rod`, RM-195), misst das Volumen gegen
die Analytik oder eine Untergrenze über dem Kern, nie nur Gültigkeit. Siehe
[[bausteinbereich-ist-ein-produktionsvertrag]] für die Maßseite und
[[gegenprobe-bei-geaenderter-bauart]] für die Messung.
