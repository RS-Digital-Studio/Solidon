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
Millionen Dreiecken (`run_budgets.py`) steht im Nachtrag unten.

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
voll) und ist einzeln grün. Leistungstests (`-m performance`, unter dem Schloss):
um 11:40 Uhr 32 grün; ein zweiter Lauf um 12:42 Uhr, während drei Sitzungen und
die Aufräumarbeit auf C: liefen, ließ
`test_the_multicolour_example_opens_without_a_surface_search_explosion` mit
zwei von zwei Regressionsstrichen fallen — dieselbe Quelle, derselbe Code. Auf
dem zusammengeführten Stand ist das Tor allein zu fahren, bevor daraus ein
Befund wird.

## Nachtrag: Leistungsreihe am Baum (12:45–12:55 Uhr)

`run_budgets.py --source final-source-v10 --name budget-final-v10`, je Lauf ein
eigener Prozess, 120 Kamerastellungen, Bild bis GPU-fertig, Umgebungsverdeckung
an, RTX 4080, während andere Sitzungen liefen (letzte Spalte: geschätzte fremde
CPU-Last über 32 logische Prozessoren). `full` zeichnet das Netz unverändert,
`lod` den regulären Anzeigeweg (Dezimierung auf 200 000 Dreiecke) mit
Körperkanten; `solid-no-edges` nimmt nur die Kantengrenze aus dem Bild.

| Lauf | Dreiecke im Bild | Bild Median ms | p95 ms | RSS MiB | Fremdlast CPU % |
|---|---:|---:|---:|---:|---:|
| `gfx-s0-full-product` | 197120 | 6,9 | 9,2 | 406 | 20,1 |
| `gfx-s0-full-solid-no-edges` | 197120 | 7,2 | 15,0 | 406 | 22,6 |
| `gfx-s1-full-solid-no-edges` | 788480 | 6,9 | 9,7 | 553 | 18,7 |
| `gfx-s1-lod-product` | 200000 | 17,5 | 20,2 | 689 | 19,5 |
| `gfx-s2-full-solid-no-edges` | 3153920 | 6,5 | 10,2 | 1116 | 18,4 |
| `gfx-s2-lod-product` | 200000 | 10,6 | 15,8 | 1407 | 26,7 |
| `vtk-s0-full-product` | 197120 | 2,2 | 7,2 | 391 | 10,7 |
| `vtk-s0-full-solid-no-edges` | 197120 | 2,6 | 7,5 | 351 | 23,3 |
| `vtk-s1-full-solid-no-edges` | 788480 | 2,5 | 8,4 | 521 | 20,4 |
| `vtk-s1-lod-product` | 200000 | 13,8 | 17,9 | 642 | 20,0 |
| `vtk-s2-full-solid-no-edges` | 3153920 | 2,3 | 10,0 | 1175 | 15,9 |
| `vtk-s2-lod-product` | 200000 | 4,7 | 5,7 | 1349 | 26,7 |

Was daraus folgt:

- **Beide Renderer sind bei 3,15 Millionen Dreiecken bildstabil.** GFX bleibt
  bei 6,5 bis 7,2 ms je Bild, unabhängig von der Dreieckszahl — das ist der
  Python-Anteil von pygfx je `render()` (drei Aufrufe je Bild), nicht die GPU.
  VTK liegt bei 2,2 bis 2,6 ms. Beides ist weit unter einem Bildwechsel bei
  60 Hz; ein Unterschied, den ein Kunde am Zug nicht sieht.
- **Der Szenenaufbau ist bei GFX doppelt so teuer wie bei VTK:** 3,8 s gegen
  2,0 s beim vollen 3,15-Millionen-Netz (`ui_heartbeat.aufbau`), 1,5 gegen 1,0 s
  bei 197 000. Der Verdacht liegt bei den Punktnormalen, die pygfx auf der CPU
  rechnet, und den Puffer-Kopien beim Anlegen; nicht profiliert — ein eigener
  Punkt (unten).
- **Der Anzeigeweg mit Dezimierung kostet mehr je Bild als das volle Netz**
  (GFX 10,6–17,5 ms, VTK 4,7–13,8 ms bei 200 000 Dreiecken): Die Kantensuche
  liefert am dezimierten Netz viele Konturlinien, und der Baum trägt in dieser
  Reihe keine Merkmale; die Spanne zwischen s1 und s2 liegt in der Fremdlast.
  Auch das ist ein Posten für die Kantenzahl, nicht für den Renderer.
- **Arbeitsspeicher gleich:** 406 gegen 391 MiB bei 197 000, 1116 gegen 1175
  MiB beim vollen 3,15-Millionen-Netz.

## Nachtrag: Aufbauprofil (14:00 Uhr) und der Ausbau

`build_profile.py --stage 2` misst `GfxRenderer.add_surface` samt erstem
Bild am Baum mit 3 153 920 Dreiecken, ohne Fenster, unter cProfile
(`build-profile-s2.txt`):

| Posten | Zeit |
|---|---|
| `add_surface` selbst | 35 ms |
| erstes Bild | 4 055 ms |
| davon: Renderpipelines übersetzen (`create_render_pipeline`, 3 Aufrufe) | 1 043 ms |
| davon: Punktnormalen auf der CPU (`pygfx.utils.normals_from_vertices`) | 823 ms |
| davon: Pufferupload (`write_buffer`, 14 Aufrufe) | 678 ms |
| davon: WGSL erzeugen und Bindungen (`generate_wgsl`, `get_bindings`) | 856 ms |
| davon: Renderzustand (`get_renderstate`) | 304 ms |
| zweites Bild | 4,4 ms |

Der „Szenenaufbau“ der Leistungsreihe (3,8 s) ist also das **erste Bild**,
nicht das Anlegen: `add_surface` legt nur Python-Objekte an, pygfx baut
Geometrie, Shader und Pipelines beim ersten `render()`. Zwei Hebel, beide mit
Zahl und beide ungebaut:

- **Vorwärmen beim Start.** Pipelines und Shadermodule cacht pygfx je
  Shaderquelle; ein kleines Netz mit demselben Material beim Anzeigen des
  Fensters (im Leerlauf, nicht vor dem ersten Bild) nähme dem ersten
  Kundenmodell rund 1,9 s ab (Pipelines, WGSL, Renderzustand). Kostet den
  Start dieselbe Zeit, aber dort sieht sie niemand.
- **Normalen mitgeben.** Übergibt `add_surface` Punktnormalen, rechnet pygfx
  keine; die Ansicht hat sie vom Netz oft schon (trimesh cacht
  `vertex_normals`). Spart bis 0,8 s je großem Netz; braucht einen
  optionalen Parameter im Vertrag.

**Ausbau (Robert, 06.09.2026: „dann ausbau sauber“):** Der VTK-Renderer ist
aus dem Baum; `factory.py` baut den einen Renderer, die Bildtests heißen
`test_render_contract.py` und laufen über pygfx allein. Die
VTK-Spalten dieser Abnahme bleiben als Messlatte stehen, sie sind nicht mehr
reproduzierbar.

## Offen

- Das erste Bild eines großen Netzes (profiliert, siehe Nachtrag): vorwärmen
  beim Start und Normalen mitgeben — beides ungebaut.
- Zahl der Konturlinien am dezimierten Netz — der Anzeigeweg ist je Bild
  teurer als das volle Netz.

- Fall 4 ist entschieden und gebaut: Die Zielhilfe gilt, solange das Sichtbare
  in Reichweite hinter dem Austritt der Öffnung liegt; weiter dahinter meint
  der Klick die Fläche, die er sieht (`_bore_aim`, Test in
  `test_selection.py`).
- Leistungsreihe und Leistungstests nach dem Commit; Nachtrag folgt.
- `vtk` ist seit dem Ausbau des VTK-Renderers nur noch die Geometriebibliothek
  der Bereichsprüfung; auf 9.7.0 heben (eigener Schritt mit Tor) oder durch
  eine eigene Strahl- und Dreieckspaarprüfung ersetzen, dann fällt es ganz.
- Speicher über Fenster- und Sprachwechsel ist für GFX nicht gemessen.
