# RM-232 — erster Merkmalklick (Stand 25.09.2026, nachmittags)

Auftrag Robert: Kernauskünfte des Merkmalfensters (alike_for_actions u. a.) aus dem
Hauptfaden in einen Arbeiter. Dazu am selben Tag: „es werden auch beim auswahlpanel
oder dem panel von der bohrung in dem viewport anderes bzw das im viewport an einer
anderen stelle gezeigt bevor die ansicht wieder passt".

## Gebaut und gemessen

- Kernauskünfte ab 20 000 Dreiecken im Arbeiter (`MainWindow._answer_in_worker`,
  `panels.feature_answers`, `FeaturePanel.known_answers/remember_answers/show_pending`).
- Arbeiterkopie mit den trimesh-Merkern des Originals (`for_a_worker`, include_cache):
  Kernauskünfte an der Kopie 529 → 264 ms.
- `features.vertex_rank` als die eine Eckennummer (vorher dreimal: `_canonical_vertices`,
  `_vertex_rank`, `placement._welded_adjacency`); Nachbarschaft der Platzierung 114 → 30 ms.
- `relations._blended_cavity_faces` sucht ab der Wand: 277 Bohrungen gleich, 404 → 100 ms
  (`uebergang_gleich.py`).
- Zwischenbilder: `GfxRenderer.render` bestellt, `render_now` sofort (erstes Vorschaubild);
  `PlacementFlow._seat_waits` hält die Maßkarte verborgen, bis ihre Fläche da ist;
  `set_measuring` vor `flow.start`; `MainWindow._lay_out_now`; `selection_operations._ListScroller`.
  Nachweis: `scenario_malen.py` (Malereignisse mit Geometrie), `scenario_frames.py`.
- Verworfen, gemessen: zwei Arbeiterkopien nebeneinander (Kernsonde 420 → 260 ms, am
  Fenster 420 → 500 ms: GIL, fehlende Merker für `at_point`) — Docstring `for_a_worker`.

Zahlen (offscreen, `rm232_probe.py`, dichte Platte): erster Bohrungsklick synchron 172 → 36 ms,
längste Lücke 171 → 52 ms, bis Ruhe 850 → 334 ms; Bohrung zu Bohrung 72–89 ms.
Echtes Fenster (`slot_probe.py clicktime`): Bohrung zu Bohrung 351 ms Platte, 348 ms Wabenhalter.

## Offen in RM-232

- Echtes Fenster: 140 von 854 Widgets nativ (AA_DontCreateNativeWidgetSiblings aus, die
  Karten liegen als native Geschwister über der wgpu-Fläche); `setVisible` 1,3 ms und malt
  sofort (`scenario_nativ.py`). Die Maßgruppe baut je Klick neu (`end_quiet_placement` →
  `dispose`, fünf `redraw`); `seat_of` rechnet Öffnungen und Kanten je Klick (39 ms).

## Danach (Vorgabe Robert: nichts liegen lassen)

- RM-239: Sonde `rm239/schweissen2.py` — nur Ränder verschweißen, Punktgruppen nach Blatt
  trennen. Abnahmefälle grün (`rm239/pruefe_faelle.py`), Testkorpus 36/36 wie heute
  (`rm239/korpus.py`); noch: F:\3D Dateien, Zeit (1,1 gegen 0,55 s am Millionennetz),
  Import und Reparatur auf die eine Funktion, doppelte Schale beim Import.
- RM-240: halbe und Dreiviertelwand, Senkungskegel.
- RM-241, A5, B1: von der Bedienweg-Sitzung gebaut und archiviert, am Code nachgesehen.

Die dichte Platte ist `tests/data/meshes/plate_holes.stl` viermal unterteilt
(796 · 4⁴ = 203 776 Dreiecke): `python erzeuge_platte.py`.
