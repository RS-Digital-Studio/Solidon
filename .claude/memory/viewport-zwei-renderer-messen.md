---
name: viewport-zwei-renderer-messen
description: "Entscheidung Robert 05.09.2026 — PyVista/PyVistaQt fallen; eigener Adapter mit zwei Renderern (VTK direkt, pygfx/wgpu), beide auf echten Szenen gemessen; Aufwand egal, alte GPUs kein Kriterium"
metadata: 
  node_type: memory
  type: project
  originSessionId: f205bb02-89f3-41d7-a514-397ddd2fe07b
  modified: 2026-09-05T15:01:38.538Z
---

Robert hat am 05.09.2026 entschieden: „Ich will die beste Lösung, Aufwand ist
mir egal“ und „bau beides und mess“. Der Viewport bekommt eine eigene
Adapterschnittstelle unter `app/ui/render/`; dahinter zwei Renderer:

1. **VTK direkt** (ohne PyVista/PyVistaQt, Qt-Einbettung über QOpenGLWidget
   und vtkGenericOpenGLRenderWindow) — der risikoarme, zuerst gebaute.
2. **pygfx/wgpu** (rendercanvas für Qt) — der moderne, danach gebaut.

Gemessen wird auf Roberts echten Szenen und einmal in einer VM ohne
Grafiktreiber: kopierte Bytes, Szenenaufbau- und Updatezeit, Drag-Framezeit,
Speicher über Fenster- und Sprachwechsel, und ob jede Viewport-Funktion
(Picking, Schnitt, Transparenz, Text, Screenshot) gleichwertig steht. Mit den
Zahlen entscheidet Robert, was ausgeliefert wird.

**Why:** PyVista sperrt VTK auf 9.6.2 und trägt eigene Lebensdauerfehler; der
Review nennt beide Wege. Hardware älter als 2012/2013 (kein Vulkan/DX12/Metal)
ist für Robert kein Kriterium („sowas altes hat doch keiner mehr“); VMs
bekommen WARP/lavapipe.

**How to apply:** Reihenfolge: Update-Paket (pyvistaqt 0.13.0 nur als
Zwischenstand) → Adapter + VTK-Renderer im eigenen Arbeitsbaum, jeder Schritt
gegen die Fenstertests → pygfx-Renderer hinter derselben Schnittstelle →
Messtabelle → Entscheidung → PyVista aus Abhängigkeiten, Lizenzliste und
Stückliste, VTK 9.7.0 → Python 3.14.7 als letzter Umgebungsschritt.
Siehe [[vtk-qt-referenzen-halten-zu-lange]], [[vtk-sagt-ja-und-tut-nichts]].
