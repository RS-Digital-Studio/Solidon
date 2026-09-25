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

## Abends: native Fenster und Übergabe (gebaut, gemessen)

- `overlay.keep_widgets_alien` (AA_DontCreateNativeWidgetSiblings, in `Viewport.__init__`
  vor der Fläche) und `overlay.hold_above_the_view` (`childEvent` von `Viewport` und
  `OverlayHost`): nativ 106 → 20 im Stand, 29 mit Bohrung. `scenario_verdeckt.py`: acht
  Zustände, Werkzeuge, Skizze — nichts verdeckt.
- Widgets im endgültigen Elternteil: Halter vor Feldern, `measure_fields(op, None)`.
- Übergabe von Fluss zu Fluss: `_build_floating`, `_wire_floating` (`_links`),
  `_park_floating`, `_take_parked_floating`, Vorrat `_PARKED` je Kennung mit `destroyed`
  (`scenario_abbau.py`: nach dem Schließen leer, Ansicht und Tinte eingesammelt).
  Die Maßtinte geht mit (8 Renderer-Elemente). `wheel_needs_focus` idempotent.
- `start` baut einmal auf (`_redraw_held`), `end_quiet_placement` ohne Rücklauf
  (`_ending_quiet_placement`), `FeaturePanel.measuring`.
- Platzsuche der Nähe nach bis zur Grenze: an drei Körpern dieselben Plätze
  (`scenario_plaetze.py`, vorher/nachher).
- Nachweise am Fenster statt Fenstertests (die laufen erst beim Release):
  `scenario_uebergabe.py` an Wabenhalter, Schraubendreherhalter, Pegboard-Teil.
- Bildtakt (`max_fps`): gemessen folgenlos (`scenario_bestellung.py`, `scenario_zug.py`),
  gebaut und wieder entfernt.

Zahlen, abwechselnd bei gleicher Last (`ab.sh`), Bohrung zu Bohrung bis zur Fläche:
Wabenhalter 200–208 → 127–128 ms, Platte 310 → 163 ms; „alles alien" 100–103 ms.
Unter schwerer Fremdlast (16–25 Kerne anderer Torläufe) schwankt schon der synchrone
Teil zwischen 58 und 97 ms — dann nur Verhältnisse lesen.

## Offen in RM-232 (im Register)

Wabenhalter unter 100 ms. Rest im Hauptfaden (`scenario_zeitleiste.py`,
`scenario_teilprofil.py`): `set_measuring` aus/an beim Bohrungswechsel (87
Sichtbarkeitswechsel, ~10 ms), Werkzeug neu in den Renderer (~10 ms),
`_redraw_features` 14 ms, zwei Bilder je Klick, Zeigen/Bewegen der neun nativen
Felder (~20 ms).

## Danach (Vorgabe Robert: nichts liegen lassen)

- RM-239: Sonde `rm239/schweissen2.py` — nur Ränder verschweißen, Punktgruppen nach Blatt
  trennen. Abnahmefälle grün (`rm239/pruefe_faelle.py`), Testkorpus 36/36 wie heute
  (`rm239/korpus.py`); noch: F:\3D Dateien, Zeit (1,1 gegen 0,55 s am Millionennetz),
  Import und Reparatur auf die eine Funktion, doppelte Schale beim Import.
- RM-240: halbe und Dreiviertelwand, Senkungskegel.
- RM-241, A5, B1: von der Bedienweg-Sitzung gebaut und archiviert, am Code nachgesehen.

Die dichte Platte ist `tests/data/meshes/plate_holes.stl` viermal unterteilt
(796 · 4⁴ = 203 776 Dreiecke): `python erzeuge_platte.py`.
