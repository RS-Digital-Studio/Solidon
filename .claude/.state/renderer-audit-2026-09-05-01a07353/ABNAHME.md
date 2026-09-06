# Renderer und Oberfläche: Abnahme

Stand 06.09.2026, 12:30 Uhr. Fortgeführt von 3d-druck-f7 nach der Codex-Sitzung
01a07353, deren Renderer-Paket bis V9 reichte (siehe `v7-renderer-visual-findings.md`,
`shared-fixes-v*/manifest.json`). Robert hat am Morgen entschieden: **Solidon zeichnet
mit pygfx (GFX).** VTK bleibt als zweiter Renderer hinter demselben Vertrag und
springt ein, wenn eine Maschine keinen wgpu-Adapter hat (`choice.effective_backend`).

## Was eingebaut ist

| Bereich | Ergebnis | Nachweis |
|---|---|---|
| Vorgabe und Rückfall | `SOLIDON_RENDERER` unbesetzt heißt GFX; ohne wgpu-Adapter zeichnet VTK und sagt es im Protokoll; ohne beides bleibt die Ansicht leer mit Hinweis | `tests/test_render_choice.py` |
| PyVista fällt | `pyvista`/`pyvistaqt` sind aus `pyproject`, `constraints.txt`, Freigabeliste, Spec und Lizenzbeilage (70 → 51 Laufzeitkomponenten); `vtk` ist direkte Abhängigkeit | `tests/test_licences.py`, `THIRD-PARTY-NOTICES.md` |
| GFX-Auswahl | Exakter Weltpunkt aus Sichtstrahl und Float64-Dreieck; wiederverwendeter Pickdurchgang; Trefferring in einem Rücklesen | `tests/test_render_gfx_regressions.py` |
| GFX-Bild | Umgebungsverdeckung in zwei Durchgängen (`gfx_occlusion.py`), Tiefenlinien gegen koplanare Lücken (`gfx_lines.py`), gewichtete Transparenz, `force_opaque` | dieselbe Datei, `tests/test_render_vtk.py` über beide Renderer |
| Körperkanten | Drahtgitter-Mesh über derselben Geometrie statt einer CPU-Kantenliste (285 ms bei 197 000, 5,8 s und 114 MB bei 3,15 Mio. Dreiecken je Aufbau); angehobene Markierungen zeigen keine gepunkteten Kanten mehr | `edges_cost.py`, Bild `final-v9/gfx/file-02/mode-solid_edges.png` (vorher) |
| Beschriftung | Layout ohne Überlappung mit Vorrang für Auswahl und Hover, Verbindungslinien, Felder aus echten Textmaßen; ausgeschiedene Namen ruhen verborgen im Baum statt je Bild neu zu entstehen | `tests/test_feature_label_layout.py`, `camera-profile-*.txt` |
| Hüllquader | je Item und je Geometriestand gecacht, Beschriftungen zählen wie VTK-2D-Aktoren nicht mit | `camera-profile-v10-*.txt` |
| VTK | Beschriftungsfelder aus `vtkTextRenderer`-Maßen, eigene Passfolge mit Kamerapass im SSAO-Puffer, Bias an der RGBA16F-Stufe, SwapControl einmalig | `tests/test_render_vtk_presentation.py` |
| Viewport | Flächenanker im Schnitt auf einem echten Dreiecksrest, Bettentscheidung je gezeichneter Szene, Konturen folgen der Körpervorschau, Merkmalsauswahl über Körper hinweg | `tests/test_viewport_decisions.py`, `tests/test_viewport_pending_transform.py`, `tests/test_selection.py` |

## Modellmatrix am echten Fenster

Je Fall ein eigener nativer Windows-Prozess (`probe.py --full`): Import über den
Dateidialog, Drehen und Zeigen, unabhängig gerechnete Oberflächentreffer, vier
Darstellungsarten, beide Projektionen, Merkmals- und Überhangkarte, Schnitt, helles
und dunkles Thema, Merkmalsauswahl im Baum, Schichten, gehaltene Körpervorschau,
Verschieben, Rückgängig und Wiederholen, eine Merkmalbearbeitung, Speichern, STL- und
3MF-Export, erneutes Öffnen. Gewertet wird nur ein vollständig geschlossener Prozess
mit Exit 0; „rot" zählt die fachlichen Prüfungen mit `passed=false`. Die
Millisekunden sind Mediane: Zug je Kamerastellung bis zum fertigen Bild, das Bild in
der Darstellung `solid`, das Bild mit allen Merkmalsnamen, die Merkmalssuche unter dem
Zeiger. Fenster 1600 × 1000, RTX 4080, während andere Sitzungen auf derselben Maschine
arbeiteten (Fremdlast, siehe unten).

Endstand `final-v10` (Quelle `final-source-v10`, der committete Stand):

| Nr. | Datei | Ausgang | rot | Import s | Zug ms | Fläche ms | Namen ms | Hover ms |
|---|---|---|---|---|---|---|---|---|
| 5 | `top-single.stl` | vollständig, Exit 0 | 0 | 22,6 | 7,0 | 8,6 | 10,6 | – |
| 12 | `1x1-bin.stl` | vollständig, Exit 0 | 0 | 22,1 | 7,3 | 11,4 | 16,3 | 11,2 |
| 13 | `tree_with_tray_stl.stl` | vollständig, Exit 0 | 0 | 14,1 | 7,2 | 10,7 | 9,9 | 3,2 |
| 14 | `tree_no_tray_stl.stl` | vollständig, Exit 0 | 0 | 18,7 | 8,5 | 7,8 | 9,1 | 3,4 |
| 15 | `large-screwdriver-holder-with-honeycomb-pattern.stl` | vollständig, Exit 0 | 0 | 7,1 | 6,9 | 10,0 | 16,5 | 1,9 |
| 16 | `the-over-engineered-backpack-wall-mount-v2.3mf` | vollständig, Exit 0 | 0 | 13,5 | 9,6 | 10,3 | 22,1 | 3,0 |
| 17 | `the-over-engineered-backpack-wall-mount-v2.stl` | vollständig, Exit 0 | 0 | 4,0 | 9,1 | 7,5 | 13,7 | 3,3 |
| 18 | `countercleaner.3mf` | vollständig, Exit 0 | 0 | 13,6 | 8,1 | 8,9 | 12,2 | 4,3 |
| 19 | `carpet-corner-clip.step` | vollständig, Exit 0 | 1 | 12,5 | 9,4 | 9,3 | 21,4 | 36,5 |
| 20 | `Wedge-Lock (Base).stl` | vollständig, Exit 0 | 0 | 15,2 | 7,7 | 10,3 | 14,3 | 2,2 |
| 21 | `Wedge-Lock (Top) (1).stl` | vollständig, Exit 0 | 0 | 8,7 | 7,6 | 7,7 | 17,9 | 2,2 |
| 22 | `Wedge-Lock (Set).stl` | vollständig, Exit 0 | 0 | 5,6 | 8,5 | 8,4 | 20,5 | 2,1 |
| 23 | `Wedge-Lock (Top).stl` | vollständig, Exit 0 | 0 | 6,8 | 8,8 | 9,7 | 17,9 | 1,6 |

Vorstufe `final-v9` (Quelle `final-source-v9`, vor Drahtgitter, Beschriftungspool und
Hüllquader-Cache; die Fälle 1 bis 11 stehen dort und wurden auf V10 nicht wiederholt,
weil sich für sie nur die Leistung ändert):

| Nr. | Datei | Ausgang | rot | Import s | Zug ms | Fläche ms | Namen ms | Hover ms |
|---|---|---|---|---|---|---|---|---|
| 1 | `drill-holder.3mf` | vollständig, Exit 0 | 0 | 22,0 | 14,2 | 16,5 | 48,4 | 4,7 |
| 2 | `top-double.stl` | vollständig, Exit 0 | 0 | 29,5 | 8,1 | 11,3 | 22,2 | 13,5 |
| 3 | `bottom-double.stl` | vollständig, Exit 0 | 0 | 13,6 | 10,2 | 13,2 | 24,6 | 12,0 |
| 4 | `desk-organizer-v3_desk-organizer-v3_body1.stl` | vollständig, Exit 0 | 1 | 21,9 | 12,4 | 11,9 | 29,7 | 6,9 |
| 5 | `top-single.stl` | Abbruch 0xD00000FF nach 690 s (siehe unten) | 0 | 16,8 | 9,5 | – | – | 11,1 |
| 6 | `insert-top-triple (1).stl` | vollständig, Exit 0 | 0 | 26,8 | 10,7 | 11,0 | 27,4 | 9,2 |
| 7 | `insert-top-triple.stl` | vollständig, Exit 0 | 0 | 13,8 | 10,3 | 11,0 | 23,3 | 10,6 |
| 8 | `bottom-single.stl` | vollständig, Exit 0 | 0 | 19,2 | 7,6 | 8,0 | 20,2 | 10,2 |
| 9 | `peg.stl` | vollständig, Exit 0 | 0 | 29,1 | 8,7 | 9,6 | 15,7 | 7,4 |
| 10 | `2x1-tray.stl` | vollständig, Exit 0 | 0 | 66,2 | 8,9 | 8,5 | 20,2 | 8,1 |
| 11 | `1x1-tray.stl` | vollständig, Exit 0 | 0 | 46,3 | 7,1 | 8,9 | 15,8 | 9,1 |

Damit sind 23 von 23 Dateien mit GFX vollständig durchgelaufen (11 auf V9, 13 auf
V10, Fall 5 auf V10 wiederholt). Der STEP-Fall lag auf V7 noch bei 40 ms je
Kamerastellung und 60 ms mit Namen; die Bettentscheidung je gezeichneter Szene und
der Beschriftungspool bringen ihn auf 9,4 beziehungsweise 21,4 ms. Die Bilder aller
Fälle liegen in `final-v9/gfx/file-XX/` und `final-v10/gfx/file-XX/`; angesehen
wurden je Fall Thema hell/dunkel, Darstellungsarten, Schnitt, Schichten und
Merkmalbilder der Fälle 1–4, 6–9, 13, 18 und 19.

## Befunde

**Fall 4, Senkung statt Fläche (Bedienentscheidung, offen).** Ein Rasterklick bei
(675, 583) trifft laut GPU und CPU-Orakel dieselbe Zelle 6216 auf der Bodenfläche
`face_2` (Punkt 1,06 / 2,74 / 5,00). Die Anwendung wählt `cone_16`: eine Senkung
in der schrägen Wand, deren Öffnung der Sichtstrahl 56 mm vor dem Boden durchquert.
`_bore_aim` folgt seiner Regel „ein Klick ist eine Blickrichtung" — jede Öffnung vor
dem Auftreffpunkt zählt. Das Orakel (`near_axial_feature: false`) hält dagegen, dass
der Kunde die Fläche sieht, auf die er klickt. Vorschlag: Die Zielhilfe gilt nur,
solange der sichtbare Treffer innerhalb der Öffnungslänge plus Reichweite hinter dem
Austritt liegt; liegt er weiter dahinter, ist die Fläche gemeint. Nicht umgesetzt,
weil es die Bohrungsauswahl des Drillholders berührt — Entscheidung Robert.

**Fall 19, Nachbarmerkmal am Rand (kein Fehler).** Bei (878, 448) nennt die GPU das
Dreieck 1346 (`face_25`), der CPU-Strahl das Nachbardreieck 1360 (`fillet_8`); der
Weltpunkt stimmt überein. Rasterpixelmitte gegen exakten Strahl an der gemeinsamen
Kante zweier Merkmale — welches Merkmal einen Randpixel besitzt, ist Konvention.
Die übrigen vier „roten" Treffer des Falls sind Hintergrundklicks ohne Fläche.

**Fall 5, einmaliger Hänger (nicht reproduzierbar).** Im V9-Lauf blieb der Prozess
in `shot()` beim `grabWindow` stehen und endete nach 690 s mit 0xD00000FF; zeitgleich
liefen VTK-Offscreen-Prüfungen einer anderen Sitzung. Auf V10 lief derselbe Fall
vollständig durch. Bleibt als Beobachtung.

**Vorheriger V7-Stand**: Die dort notierten Punkte (Featurekanten beim Körperzug,
Kameramatrizen je Anker, VTK-Abbrüche 18/19, Bettkorn unter VTK-SSAO) sind in V8/V9
behoben und mit den obigen Läufen bestätigt; die VTK-Fälle 18/19 wurden auf dem
Endstand nicht erneut nativ gefahren, weil VTK der zweite Renderer ist.

## Leistung

Profil am Drillholder (157 Merkmalsnamen, 1600 × 1000, `camera_profile.py`, 40
Kamerastellungen, mit cProfile-Aufschlag, fremde Suite im Hintergrund):

| | vorher (V9) | nachher (V10) |
|---|---|---|
| Kamerastellung mit allen Namen | 66 ms | 34 ms |
| Kamerastellung ohne Namen | – | 15 ms |
| davon `GfxLabels.build` je Bild | ~25 ms (fünf neue `gfx.Text`) | ~2,6 ms |
| davon `_scene_bounds` je Bild | ~10 ms (2 × 76 Objekte rekursiv) | unter 1 ms |

Was bleibt, ist pygfx selbst: drei `render()`-Aufrufe je Bild (deckend, danach
Durchscheinendes und Überlagerungen, dann das Achsenkreuz) mit je rund 1,5 ms
Lichtaufbereitung (`DirectionalLight._gfx_update_uniform_buffer` ruft je Licht
`look_at`) und Pipelinesuche. Das ist Python im Renderer, keine GPU-Zeit
(Zaun 0,4–0,7 ms). Die Leistungsreihe am Baum mit 197 000, 788 000 und 3,15
Millionen Dreiecken (`run_budgets.py`) wird nach dem Commit gefahren und hier ergänzt.

## Tor

Ruff, `ruff format --check` und mypy (258 Dateien) grün. Geteilte Suite auf dem
Endstand: der Rest in einem Zug 7364 grün, 5 rot — alle fünf starten Unterprozesse
(`test_process`, `test_way_three`, `test_part_file`, zweimal `test_suite_script`)
und fielen mit „fork: File too large" / „xmalloc: cannot allocate", weil C: in diesem
Moment voll war (0 GB frei) und 10 600 liegengebliebene `solidon-tests-*`-Ordner
sowie ein 13-GB-Prozess einer anderen Sitzung den Commit-Speicher füllten. Einzeln
nachgefahren: vier grün, `test_a_portion_that_never_runs_stops_at_the_floor` läuft
in die 120-s-Grenze des Tests (das Skript startet dort dutzende Bash-Prozesse; auf
dieser Maschine unter Last je Fork sekundenlang). Fensterdateien: 58 von 60 im
Protokoll, `test_window_chrome.py` und `test_wording.py` einzeln grün;
`test_install.py` Exit 127 nach 60 grünen Tests und `test_widget_lifetime.py` Exit
139 sind der bekannte Bestand aus `CLAUDE.md`; `test_operation_ui.py` riss einmal
im Arbeiter-`__init__` (bekannte Familie) und lief geteilt vollständig grün;
`test_ui.py::test_saving_shows_that_it_is_working` fiel mit WinError 112 (Platte
voll) und ist einzeln grün. Leistungstests: siehe Nachtrag.

## Offen

- Bedienentscheidung zu Fall 4 (oben).
- Leistungsreihe und Leistungstests nach dem Commit; Nachtrag folgt.
- `vtk` kann jetzt auf 9.7.0 gehoben werden (PyVistas Sperre `vtk<9.7` ist weg) —
  eigener Schritt mit Tor.
- Speicher über Fenster- und Sprachwechsel ist für GFX nicht gemessen.
