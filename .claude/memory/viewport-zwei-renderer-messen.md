---
name: viewport-zwei-renderer-messen
description: "Entscheidung Robert 05./06.09.2026 — PyVista/PyVistaQt fallen; zwei Renderer gebaut und gemessen, dann GFX (pygfx) gewählt und der VTK-Renderer am 06.09.2026 ausgebaut; vtk bleibt nur als kopflose Geometrie der Bereichsprüfung"
metadata:
  node_type: memory
  type: project
  originSessionId: f205bb02-89f3-41d7-a514-397ddd2fe07b
  modified: 2026-09-06T11:36:29.408Z
---

Robert hat am 05.09.2026 entschieden: „Ich will die beste Lösung, Aufwand ist
mir egal“ und „bau beides und mess“. Der Viewport hat eine eigene
Adapterschnittstelle unter `app/ui/render/` (`api.py`); dahinter standen
zwei Renderer, VTK direkt und pygfx/wgpu, mit denselben Bildtests gemessen.

**06.09.2026, morgens:** „wir werden dann den gfx renderer benutzen“ — pygfx
wurde die Vorgabe. **06.09.2026, mittags:** „dann ausbau sauber“ — der
VTK-Renderer (`vtk_renderer.py`), `choice.py` und `SOLIDON_RENDERER` sind
ausgebaut; `app/ui/render/factory.py` baut den einen Renderer,
`tests/test_render_contract.py` hält den Vertrag. Das Paket `vtk` bleibt als
kopflose Geometriebibliothek der Bereichsprüfung der Bausteine
(`knowledge/parts/range_check.py`: `vtkStaticCellLocator`,
`vtkCollisionDetectionFilter`) — kein Rendering, kein Qt, kein GL. Es ganz
zu ersetzen ist ein eigener Registerpunkt mit Validierung über alle 27
Bausteine.

**Why:** PyVista sperrte VTK auf 9.6.2 und trug eigene Lebensdauerfehler; VTK
brauchte einen GL-Kontext (CI ohne Grafikkarte starb daran) und kannte unter
Qt nur X11 (Wayland-Absturz beim Kunden). pygfx läuft über wgpu auf Vulkan,
DX12 und Metal, in VMs mit WARP/lavapipe; Hardware älter als 2012/2013 ist
für Robert kein Kriterium. Gemessen (Abnahme in
`.claude/.state/renderer-audit-2026-09-05-01a07353/ABNAHME.md`): GFX 6,5 bis
7,2 ms je Bild bis 3,15 Millionen Dreiecke, VTK 2,2 bis 2,6 ms — beides weit
unter einem Bildwechsel; VTK-SSAO zeigte Bettkorn und Streifen
(RGBA16F-Positionspuffer), GFX zeichnete glatter.

**How to apply:** Der Renderer ist pygfx, ohne Schalter; wer einen zweiten
braucht, baut ihn hinter `api.py` und misst ihn mit `test_render_contract.py`.
Die X11-Bevorzugung in `qt_platform.py` stammt aus der VTK-Zeit und bleibt,
bis jemand den wgpu-Fensterweg unter nativem Wayland fährt. Die
Fensterdateien laufen in der CI weiter nicht — der Grund (VTK ohne GL) ist
weg, der Probelauf steht aus. Siehe [[vtk-qt-referenzen-halten-zu-lange]],
[[vtk-sagt-ja-und-tut-nichts]] (beide Geschichte des VTK-Renderers).
