---
name: vtk-sagt-ja-und-tut-nichts
description: "VTK nimmt Einstellungen an und führt sie nicht aus — Hardware-Picker treffen hier gar nichts, und Depth Peeling meldet Erfolg, ohne je zu laufen (03.09.2026 gemessen)."
metadata:
  type: reference
---

**Zwei VTK-Fähigkeiten lassen sich auf dieser Maschine einschalten und tun
danach nichts.** Beide melden Erfolg. Beide sind am laufenden Fenster
gemessen (03.09.2026), nicht am Quelltext geschlossen.

**Hardware-Picker treffen nichts.** `vtkHardwarePicker` und `vtkPropPicker`
gaben an jeder geprüften Stelle `None` zurück — nicht nur an dünnen
Griffpfeilen, sondern auch mitten auf dem Körper in der Bildmitte, bei
aktivem Fenster und nach ausdrücklichem `render()`. Ein `vtkCellPicker`
antwortet an denselben Koordinaten sofort. Das trifft alles, was pyvista
selbst pickt: `AffineWidget3D` stellt sich beim Anhängen einen Hardware-Picker
hin (`enable_mesh_picking(picker='hardware')`), und sein Griff war deshalb
nicht bedienbar. Wer ein pyvista-Widget benutzt, setzt danach
`interactor.SetPicker(vtkCellPicker())` — **danach**, sonst überschreibt das
Widget es, und an **beiden** Interactor-Objekten (`plotter.interactor` ist das
Qt-Widget, `plotter.iren.interactor` der VTK-Interactor; der Rückruf fragt den
zweiten).

**Depth Peeling meldet Erfolg und läuft nicht.** `enable_depth_peeling()` gibt
`True` zurück, `GetUseDepthPeeling()` steht danach auf 1 — und
`GetLastRenderingUsedDepthPeeling()` bleibt **0**, das Bild ändert sich um
keinen Bildpunkt. Zweimal versucht: beim Umschalten in den Transparenzmodus
und vor dem allerersten Bild, mit acht Schichten und `occlusion_ratio=0`. Die
bekannten Voraussetzungen stimmten dabei (`MultiSamples=0`,
`AlphaBitPlanes=1`). Der Aufruf wurde deshalb wieder ausgebaut.

**Wonach man fragt, wenn eine VTK-Einstellung wirken soll:** nicht nach dem
Rückgabewert und nicht nach dem `Get`-Gegenstück — beide sagen nur, dass die
Einstellung angekommen ist. Es gibt oft ein `LastRenderingUsed…`, und wo
nicht, entscheidet der Bildvergleich. Verwandt mit [[text-gesetzt-heisst-nicht-gezeigt]]
und [[qt-luegt-vor-dem-anzeigen]]: Dieselbe Sorte Lüge, eine Schicht tiefer.

**Und ein Prüfstand, der nichts zeigt, misst nichts.** Der erste Bildvergleich
zum Depth Peeling gab null Unterschied, weil das Fenster ohne offenes Projekt
die **Startfläche** zeigt und der Viewport gar nicht im Bild ist. Zwei
identische Bilder von einer Seite, die keine Geometrie enthält, sehen aus wie
„die Änderung bewirkt nichts". Wer den Viewport fotografiert, öffnet vorher
ein Projekt und wartet auf `session.last_result`.
