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

## Angehalten am 25.09.2026 abends (Robert: „mach dir notizen, wir machen später weiter")

Committet sind RM-232 bis 9d8d33395 (Code) und ad0404e37 (Sonden, Erinnerungen),
am 26.09.2026 dazu a255b14f8 — der angefangene Rest von RM-232 (Wabenhalter unter
100 ms). Gefahren sind dafür nur die betroffenen Tests ohne Fenster (grün bis auf die
erzeugten Handbuchseiten, die erst der Paketbau neu schreibt) und mypy; die Fenstertests
laufen beim Release. In `tests/test_ui.py` stehen drei Zeilen dazu in einem Test einer
anderen Sitzung, der noch nicht committet ist (Attrappe von
`test_first_measure_edit_releases_split_…`). Was der Commit enthält:

| Datei | Was |
|---|---|
| `app/ui/render/api.py` | `hold_frames(ms)`, `release_frames()` am Vertrag, Vorgabe tut nichts |
| `app/ui/render/gfx_renderer.py` | Anhalten mit eigener Frist (`_hold_timer`), `request_draw(self._frame)` statt `_draw` (dreimal), `_frame` hält fest, `render()` merkt vor, `render_now()` beendet das Anhalten |
| `app/ui/placement_flow.py` | `FRAME_HOLD_MS = 50`; `_hold_frames`/`_release_frames`; angehalten bei beiden Sitzsuchen (`_begin_at_feature`, `_begin_on_a_face`), frei nach `_settle` (done/failed in `try/finally`), in `_stop` und `_camera_moved`; `_seated_on_a_face` herausgezogen; `redraw` kehrt bei `_seat_is_coming()` früh zurück (nur Werkzeug verbergen) |
| `app/ui/main_window.py` | `_measuring_to_release` + `_release_measuring`; `end_quiet_placement(measuring_follows=)` und `_end_changed_quiet_placement(measuring_follows=)`; `_on_selection` gibt `not settle_actions` mit; `_on_features_selected` → Hülle um `_show_chosen_features`; `_place_from_feature_panel` → Hülle um `_place_measures`, dort `end_quiet_placement(measuring_follows=True)` |
| `tests/render_fakes.py` | `holds`, `releases` (hält nichts an — Bildzählungen bleiben) |
| `tests/test_surface_placement_ui.py` | `_another_hole`, zwei neue Fenstertests (Anhalten/Freigeben, Messen bleibt von Bohrung zu Bohrung) — **nie gelaufen** (erst beim Release) |
| `tests/test_render_gfx_regressions.py` | `test_held_frames_arrive_as_one_after_the_release` — Fenstertest, **nie gelaufen** |
| `tests/test_ui.py` | Attrappe von `test_first_measure_edit_releases_split_…` nachgezogen — gelaufen, grün |

Neue Sonden hier: `scenario_rundgang.py` (Ereignisse je Klick), `scenario_hauptprofil.py`
(Profil Klick bis Fläche), `scenario_messen.py` (wer ruft `set_measuring`), `ab_head.sh`
(HEAD-Arbeitsbaum gegen Hauptbaum, Zeitleiste). Der HEAD-Arbeitsbaum lag im Scratchpad
und ist entfernt: `git worktree add --detach <ordner> HEAD`, dann `bash ab_head.sh <ordner> 3`.

**Gemessen** (ruhige Maschine, Wabenhalter, Median Klick 3–10):

- `set_measuring` je Klick 1 statt 2 Aufrufe (5–6 statt 18 + 1,5 ms). Die Ursache des
  zweiten war `_place_from_feature_panel` → `end_quiet_placement()` **nach** dem schon
  vorgemerkten Ausschalten.
- Das Bild vor `_settle` ist weg; danach kommen noch **ein bis zwei** Bilder (vermutlich
  Expose der gezeigten nativen Felder — prüfen).
- `scenario_zeiten`: 121 ms bis zur Fläche. `ab_head.sh` drei Runden, RUHE:
  HEAD 120 / 141 / 143, neu 133 / 127 / 124 — Rauschen ±15 ms, **kein belegter Gewinn**.
- Zeitleiste neu: synchron fertig ~60, Arbeiter fertig ~70, `_settle` 82 → 101, Bild 107 → 120.

**Offen, in dieser Reihenfolge:**

1. Nachweise am Fenster erneut fahren (`scenario_uebergabe`, `scenario_verdeckt`,
   `scenario_abbau`, `scenario_plaetze`) — nach diesen Änderungen noch nicht.
2. Lücke Arbeiterende → `_settle` (~13 ms, Qt malt Merkmalfenster/Baum dazwischen),
   `_settle` 18–24 ms (`set_gizmo` 9× je Klick, native `raise_`/`move`/`show`,
   `_size_measure_fields`), das zweite Bild danach, `_layout_feature_labels` 10× je Klick.
   Kandidaten: Werkzeug über Flüsse behalten (Schlüssel ist ortsfrei, gleiche Bohrung →
   kein `prepare_tool`, kein `add_surface`), Griff umhängen statt neu bauen (Regel in
   `ansicht.md`/`griffe.md` beachten), Maßgruppen-Kästchen wiederverwenden.
3. Mehr Runden A/B nur bei ruhiger Maschine (Last vorher prüfen); Ziel Klick bis Ruhe < 100 ms.
4. Doku: `ansicht.md` (Bild anhalten, Messen über die Auswahlrunde), `app/ui/CLAUDE.md`,
   `render/CLAUDE.md` („Zeichnen an einer Stelle" um das Anhalten ergänzen).
5. Tor (`suite-getrennt.sh`, ruff, format, mypy), dann Commit nur der eigenen Hunks.

Danach: RM-239 (oben), RM-240, **RM-246** (Laptop-Ständer offen nach Reparatur, Rasterstufe
+31 % Volumen — heute ins Register eingetragen; Sonde und Übergabenotiz der
Langloch-Sitzung in `.claude/.state/rm-246-laptop-staender-2026-09-25/`).
