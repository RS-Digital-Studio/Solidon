---
name: viewport-zwei-renderer-messen
description: "Entscheidung Robert 05./06.09.2026 — PyVista/PyVistaQt fallen; eigener Adapter mit zwei Renderern (VTK direkt, pygfx/wgpu). Am 06.09.2026 entschieden: Solidon benutzt den GFX-Renderer (pygfx), VTK bleibt zweiter Renderer hinter dem Vertrag"
metadata:
  node_type: memory
  type: project
  originSessionId: f205bb02-89f3-41d7-a514-397ddd2fe07b
  modified: 2026-09-06T06:18:34.210Z
---

Robert hat am 05.09.2026 entschieden: „Ich will die beste Lösung, Aufwand ist
mir egal“ und „bau beides und mess“. Der Viewport hat eine eigene
Adapterschnittstelle unter `app/ui/render/` (`api.py`); dahinter zwei Renderer:

1. **pygfx/wgpu** (`gfx_renderer.py`, rendercanvas als eigene Grafikfläche) —
   **seit dem 06.09.2026 die Vorgabe** („wir werden dann den gfx renderer
   benutzen“, Robert, an drei Sitzungen zugleich).
2. **VTK direkt** (`vtk_renderer.py`, ohne PyVista/PyVistaQt, Qt-Einbettung
   über `QVTKRenderWindowInteractor`) — der zweite Renderer, weiter über
   `SOLIDON_RENDERER=vtk` wählbar und mit denselben Bildtests gemessen.

**Stand 06.09.2026 morgens:** Die Codex-Sitzung 01a07353 hat bis 04:39 ein
Renderer-Paket aufgebaut (GFX-AO, Tiefenlinien, Pick aus dem Bildpuffer mit
Sichtstrahlpunkt, Beschriftungslayout, Flächenanker im Schnitt, VTK-Passfolge)
und war dann am Limit; 3d-druck-7e führt es fort (Audit-Ordner
`.claude/.state/renderer-audit-2026-09-05-01a07353/`, Ablauf `run_block.py`,
Sonde `probe.py`, Leistungsreihe `budget_probe.py`). Gemessen mit
`tools/window_bench.py --renderer` (weg4-figur-formen, maximiert, RTX 4080):
Zug je Bild VTK 6,9 ms, pygfx 4,9 ms; Bild im Stand 7,2 gegen 3,8 ms;
Arbeitsspeicher gleich (~495 MiB); pygfx braucht beim ersten Bild ~1,5 s für
Shader.

**Why:** PyVista sperrt VTK auf 9.6.2 und trägt eigene Lebensdauerfehler; der
Review nennt beide Wege. Hardware älter als 2012/2013 (kein Vulkan/DX12/Metal)
ist für Robert kein Kriterium („sowas altes hat doch keiner mehr“); VMs
bekommen WARP/lavapipe. Im V7-Vergleich zeigte VTK-SSAO Bettkorn und Streifen
(RGBA16F-Positionspuffer), GFX zeichnete glatter.

**How to apply:** Vorgabe `gfx` in `choice.py`; PyVista/PyVistaQt aus
`pyproject`, `constraints.txt`, Freigabeliste, Lizenzbeilage und Spec (kein
Import mehr in `app/`); VTK bleibt als Abhängigkeit, solange
`vtk_renderer.py`, `range_check.py` und `qt_platform.py` es brauchen.
Nicht gemessen: Speicher über Fenster- und Sprachwechsel, kopierte Bytes je
Szene; die zwei Prüfstände unter `.claude/.state/` sprechen noch
VTK-Ereignisse (Registerpunkt). Robert sah das erste VTK-Fenster fast
schwarz: Der Lichtsatz (`vtkLightKit`) fehlte — behoben, in beiden Renderern.
Siehe [[vtk-qt-referenzen-halten-zu-lange]], [[vtk-sagt-ja-und-tut-nichts]].
