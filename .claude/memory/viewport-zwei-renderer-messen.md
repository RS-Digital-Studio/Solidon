---
name: viewport-zwei-renderer-messen
description: "Entscheidung Robert 05.09.2026 — PyVista/PyVistaQt fallen; eigener Adapter mit zwei Renderern (VTK direkt, pygfx/wgpu). Stand 05.09.2026 abends: beide gebaut und gemessen, Wahl über SOLIDON_RENDERER, Entscheidung offen"
metadata:
  node_type: memory
  type: project
  originSessionId: f205bb02-89f3-41d7-a514-397ddd2fe07b
  modified: 2026-09-05T20:59:45.920Z
---

Robert hat am 05.09.2026 entschieden: „Ich will die beste Lösung, Aufwand ist
mir egal“ und „bau beides und mess“. Der Viewport hat eine eigene
Adapterschnittstelle unter `app/ui/render/` (`api.py`); dahinter zwei Renderer:

1. **VTK direkt** (`vtk_renderer.py`, ohne PyVista/PyVistaQt, Qt-Einbettung
   über `QVTKRenderWindowInteractor`) — Vorgabe.
2. **pygfx/wgpu** (`gfx_renderer.py`, rendercanvas als eigene Grafikfläche).

**Stand am Abend des 05.09.2026 (Commits auf origin main):** Beide stehen,
die Bildtests laufen je Test über beide, `SOLIDON_RENDERER=vtk|gfx` wählt
(`choice.py`, keine Einstellung in der Oberfläche). Gemessen mit
`tools/window_bench.py --renderer` (weg4-figur-formen, maximiert, RTX 4080):
Zug je Bild VTK 6,9 ms, pygfx 4,9 ms; Bild im Stand 7,2 gegen 3,8 ms;
Arbeitsspeicher gleich (~495 MiB); pygfx braucht beim ersten Bild ~1,5 s für
Shader. pygfx hat keine SSAO, Beschriftungsfelder sind Balken, das Licht
verläuft weicher (linear statt sRGB). **Robert hat noch nicht entschieden.**

**Why:** PyVista sperrt VTK auf 9.6.2 und trägt eigene Lebensdauerfehler; der
Review nennt beide Wege. Hardware älter als 2012/2013 (kein Vulkan/DX12/Metal)
ist für Robert kein Kriterium („sowas altes hat doch keiner mehr“); VMs
bekommen WARP/lavapipe.

**How to apply:** Erst Roberts Entscheidung, dann: PyVista/PyVistaQt (oder
pygfx samt Begleitern) aus `pyproject`, `constraints.txt`, Freigabeliste,
Lizenzbeilage und Spec; VTK auf 9.7.0; Python 3.14.7 als letzter
Umgebungsschritt. Nicht gemessen: Speicher über Fenster- und Sprachwechsel,
kopierte Bytes je Szene; die zwei Prüfstände unter `.claude/.state/` sprechen
noch VTK-Ereignisse (Registerpunkt). Robert sah das erste VTK-Fenster fast
schwarz: Der Lichtsatz (`vtkLightKit`) fehlte — behoben, in beiden Renderern.
Siehe [[vtk-qt-referenzen-halten-zu-lange]], [[vtk-sagt-ja-und-tut-nichts]].
