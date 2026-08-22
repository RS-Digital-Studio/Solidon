# Abgleich: `.claude/konzept-p15-konstruieren-und-zeigen.md`

**Geprüft am:** 19.08.2026 gegen `main` (b0415d6)
**Letzte Änderung am Dokument:** 843f0dd, 13.08.2026 („Zwei Notizen führten als
offen, was der Code längst konnte")
**Stand laut Dokument:** §2 „Erhoben am 03.08.2026 gegen den Arbeitsbaum"

**Ergebnis in einem Satz:** Die *Begründung* des Konzepts trägt unverändert; die
*Bestandsaufnahme* in §2 und §2.1 ist an praktisch jeder Zahl überholt, und §7
Etappe 1 hakt einen ViewCube ab, den es im Code seit dem 12.08.2026 nicht mehr
gibt.

**Zählung:** stimmt 5 · überholt 11 · falsch 1 · unprüfbar 0

---

## 1. „55 Operationen im Register, 16 Kategorien; 16 Bausteine" (§2)

**Urteil: überholt** — und im Dokument selbst widersprüchlich.

**Beleg**

```
.venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations; ..."
ops: 85
kategorien: 15 ['boolean','colour','holes','import','label','mesh','parts',
                'prepare','primitive','repair','scene','shaping','sketch',
                'surface','transform']
parts: 17
```

Etappe 8 (Zeile 908–909) schreibt dagegen „vierzehn statt dreiundsiebzig" — also
73 Operationen und 14 Kategorien. Beide Zahlen des Dokuments sind heute falsch,
und sie widersprechen einander schon innerhalb der Datei. Auch D5 und D6
(Zeilen 248–249) rechnen weiter mit „55 Menüeinträge" bzw. „6 Kürzel an 55
Operationen".

**Was stattdessen dastehen müsste (§2):**
> * **85 Operationen** im Register, 15 Kategorien; **17 Bausteine**

**Und in Etappe 8:** „getragen von der **Kategorie**, fünfzehn statt
fünfundachtzig".

---

## 2. „2211 Tests grün (`-m "not performance"`, 158 s)" (§2)

**Urteil: überholt.**

**Beleg**

```
.venv/Scripts/python.exe -m pytest -q -m "not performance" --collect-only
4232/4251 tests collected (19 deselected)
```

Die Laufzeit habe ich nicht gemessen (der Sammellauf allein braucht 4,7 s); die
Zahl der Tests hat sich seit dem 03.08. fast verdoppelt. Ergänzend:
`tests/` enthält heute 133 Testdateien.

**Was stattdessen dastehen müsste:**
> * **4232 Tests grün** (`-m "not performance"`), keine Importfehler

---

## 3. „Skizzen: 5 Ops, 9 Bedingungsarten, 200 Bedingungen in 90 ms; Elemente nur Punkt, Linie, Kreis, Bogen" (§2)

**Urteil: überholt** in drei von vier Teilen; auch hier widerspricht Etappe 4
dem §2 desselben Dokuments.

**Belege**

* **5 Ops — stimmt.** Kategorie `sketch`: `sketch_extrude`, `sketch_loft`,
  `sketch_pocket`, `sketch_revolve`, `sketch_sweep`.
* **Bedingungsarten: zehn, nicht neun.**
  `app/core/types.py:1049` — `SketchConstraintKind = Literal["distance",
  "coincident", "horizontal", "vertical", "parallel", "perpendicular",
  "tangent", "symmetric", "fixed", "reference"]`. Die zehnte (`reference`) hat
  Etappe 4 selbst gebaut (`app/core/sketch/solver.py:59,65`).
* **Elemente: fünf, nicht vier.** `app/core/types.py:1048` —
  `SketchElementKind = Literal["point","line","arc","circle","spline"]`.
  Der Spline kam mit Etappe 4.
* **90 ms — nicht mehr erreicht.** `tests/.performance.json` führt für
  `sketch_solve_200` den **besten je gemessenen Lauf** dieser Maschine mit
  **116,7 ms**; drei Läufe heute ergaben 185, 284 und 294 ms und liessen
  `test_the_sketch_solver_meets_its_budget` scheitern (Budget §31: 100 ms).
  Die heutigen Werte sind lastbehaftet, der Bestwert von 116,7 ms ist es nicht —
  er liegt über den behaupteten 90 ms und über dem Bauplanbudget.

**Was stattdessen dastehen müsste:**
> * Skizzen: 5 Ops, **10 Bedingungsarten**, eigener scipy-Solver mit
>   analytischen Ableitungen, 200 Bedingungen in **rund 120 ms** — damit über
>   dem Budget aus §31
> * Skizzenelemente: **Punkt, Linie, Kreis, Bogen, Spline**

*Nebenbefund:* Etappe 4 nennt `bolt_circle` und `hole_grid` „als Grundformen".
Sie stehen in `app/core/sketch/shapes.py:184,212`, aber **nicht** in
`SHAPE_CHOICES` (`shapes.py:22` führt nur `rectangle, slot, circle, polygon`);
erreichbar sind sie über den Skizzeneditor
(`app/ui/sketch_editor.py:2121`). „Als Werkzeuge im Skizzeneditor" wäre die
genauere Formulierung.

---

## 4. „6 Kürzel an Operationen, 21 im Fenster; 13 Symbole insgesamt, keines für eine Operation" (§2, D5, D6)

**Urteil: überholt.**

**Belege**

* **6 Kürzel an Operationen — stimmt weiterhin** (`delete_object` Del,
  `drill_hole` Ctrl+B, `duplicate_object` Ctrl+D, `rename_object` F2,
  `rotate_object` Ctrl+R, `translate_object` Ctrl+T). Dazu kommt seit Etappe 8
  die zweite Belegung `FUSION` in `app/ui/shortcut_schemes.py:25` mit elf
  weiteren Tastenzuordnungen.
* **21 im Fenster → 31.**
  ```
  MainWindow(Session(), UiSettings()); entries(w.menuBar())  →  31
  ```
* **13 Symbole → 49.** `app/ui/icons.py`, `PATHS` hat 49 Einträge, davon **15
  Kategoriesymbole** (`category.*`) — also für jede Registerkategorie eines.
  „Keines für eine Operation" gilt nicht mehr: `split_line` deklariert ein
  eigenes (`icon="split"`), alle übrigen erben das ihrer Kategorie, und
  `tests/test_interface_limits.py:219`
  (`test_every_operation_has_an_icon_and_every_icon_exists`) hält das fest.

**Was stattdessen dastehen müsste:**
> * **6 Kürzel an Operationen**, 31 im Fenster, dazu eine zweite Belegung
> * **49 Symbole**, darunter eines je Registerkategorie — jede Operation trägt
>   damit ein Symbol

---

## 5. „Viewport ohne Anti-Aliasing, Umgebungsverdeckung, Schatten, Studiolicht; kein ViewCube, keine Ansichtsleiste; keine Druckerverbindung" (§2, D4, D20, D22)

**Urteil: überholt** — mit einer Ausnahme, die den nächsten Punkt trägt.

**Belege**

* Kantenglättung: `app/ui/viewport.py:1258` — `self.plotter.enable_anti_aliasing("fxaa")`
* Umgebungsverdeckung: `app/ui/viewport.py:1286` — `enable_ssao(radius=SSAO_RADIUS, ...)`
* Kontaktschatten: `app/ui/viewport.py:403 shadow_direction`, `:453 shadow_points`
  (selbst projiziert, nicht `enable_shadows`)
* Feature-Kanten: `app/ui/viewport.py:1716` — `surface.extract_feature_edges(...)`
* **Studiolicht: fehlt weiterhin** — kein `add_light`/`Light(` in `viewport.py`.
* **Ansichtsleiste: fehlt weiterhin** (bewusst, Etappe 1).
* **Druckerverbindung: fehlt weiterhin** — kein Treffer für
  `moonraker|octoprint` in `app/`. D22 ist im Dokument selbst als offen geführt
  („Nicht in P15, aber notiert") und stimmt.
* **ViewCube: fehlt heute wieder** → siehe Punkt 5b.

**Was stattdessen dastehen müsste (§2 als historischer Stand kenntlich machen):**
> Erhoben am 03.08.2026, **vor** den Etappen dieses Konzepts — was Etappe 1 bis 9
> daran geändert haben, steht in §7.

---

## 5b. Etappe 1: „**ViewCube** (D4) — `add_camera_orientation_widget`, anklickbar, dreht die Kamera auf die getroffene Seite" (Zeile 672)

**Urteil: falsch** (gemessen am heutigen Code), und im Dokument doppelt
widersprüchlich.

**Belege**

* `grep -rn "add_camera_orientation_widget" app/ tests/` → **kein Treffer**.
* `git log -S "add_camera_orientation_widget" -- app/ui/` → nur zwei Commits:
  f52aea5 (eingebaut) und **f04c35d, 12.08.2026** („Der Zeiger sagt jetzt, was
  ein Klick täte"), dessen Diff lautet:
  ```
  -            self.plotter.add_camera_orientation_widget()
  +            self.plotter.add_axes(
  ```
* Der Docstring von `_add_orientation_widget` (`app/ui/viewport.py:1192 ff.`)
  sagt es ausdrücklich: „Von den zwei Anzeigen, die damals doppelt im Bild
  standen, ist **der Würfel gegangen** und dieses Kreuz geblieben."

**Zwei Widersprüche im Dokument selbst:**

1. Der Haken bei Zeile 681 („das Bild fand die Doppelung: `add_axes` neben dem
   Würfel") legt nahe, das Achsenkreuz sei gewichen — tatsächlich ist am
   03.08. `add_axes` gegangen (Commit 1f5590a) und am 12.08. der Würfel
   zurückgenommen worden. Das Dokument kennt nur den ersten Schritt.
2. Die *Abnahme* von Etappe 1 (Zeile 685) verlangt: „**Die Ansichtsleiste**
   erreicht alle sieben Voreinstellungen ohne Menü" — während der Haken darüber
   (Zeile 673–675) sagt: „**Die Ansichtsleiste unten links entfällt**". Der
   Abnahmesatz prüft etwas, das derselbe Punkt gerade abgeschafft hat.

**Was stattdessen dastehen müsste:**
> - [x] **Orientierungsanzeige** (D4) — zuerst als anklickbarer Würfel
>       (`add_camera_orientation_widget`), seit dem 12.08.2026 wieder als
>       Achsenkreuz `add_axes` unten links: zwei Anzeigen für dieselbe Auskunft
>       waren eine zu viel. Die Ansichtsleiste entfällt; die sieben
>       Voreinstellungen bleiben über Menü und Kürzel erreichbar (§19.2).
>
> *Abnahme:* … Die sieben Voreinstellungen sind über Menü und Kürzel
> erreichbar.

---

## 6. „Agent … 33 Referenzanfragen" (§2.1)

**Urteil: überholt.**

**Beleg**

```
.venv/Scripts/python.exe -c "from tests.agent_cases import ALL_CASES; print(len(ALL_CASES))"
39
```

`AGENTS.md` („Testarten") nennt ebenfalls 39; `tools/run_agent_suite.py:38`
liest genau diese Liste.

**Was stattdessen dastehen müsste:**
> · Regelsammlung mit Version · **39 Referenzanfragen**.

---

## 7. „Handbuch mit 25 Seiten und 20 Abbildungen · sieben Beispielprojekte · sechs Formatversionen mit Migrationen" (§2.1)

**Urteil: überholt**, alle vier Zahlen.

**Belege**

```
manual.pages()          → 40 Seiten      (app/core/manual.py:1396)
figures.FIGURES         → 25 Abbildungen (app/core/figures.py:970)
examples.EXAMPLES       →  9 Beispiele   (app/core/examples.py; 9 .p3d in app/examples/)
migrations.FORMAT_VERSION → 8            (app/core/scene/migrations.py:27,
                                          sieben Migrationsschritte, Zeilen 139–145)
```

**Was stattdessen dastehen müsste:**
> **Auslieferung** — Handbuch mit **40 Seiten und 25 Abbildungen**, keine von
> Hand gepflegt · **neun Beispielprojekte** …
>
> **Dokumentlogik** — … · **acht Formatversionen** mit Migrationen und
> eingecheckten Beispieldateien.

---

## 8. „Auswertung aus dem Cache: 0,3 ms" (§1.1, §2.1)

**Urteil: stimmt** (Größenordnung bestätigt).

**Beleg** — `tests/.performance.json`, Bestwert dieser Maschine:
`evaluate_cached: 0.4 ms`; ein Lauf heute meldete „evaluate_cached: 1 ms".
Der Test `test_reevaluating_from_the_cache_is_quick`
(`tests/test_performance.py:282`) prüft gegen die Schranke aus §31 (unter 1 s)
und ist grün.

Wenn man genau sein will: **0,4 ms**. Die Aussage, aus der das Argument gegen
SindriCADs „stateless full rebuild" gebaut ist, trägt unverändert.

---

## 9. „P15 ist vollständig abgearbeitet; von 22 Lücken vier begründet abgelehnt" (Kopfkasten, §7)

**Urteil: stimmt.**

**Beleg** — `ROADMAP.md:2236 ff.` („## P15 — Konstruieren und zeigen"):
„Das Konzept steht in `.claude/konzept-p15-konstruieren-und-zeigen.md` und ist
vollständig abgearbeitet." Dort auch: „**Vier Dinge wurden begründet nicht
gebaut**".

**Ein Unterschied in den Gründen, der auffällt:** Die ROADMAP begründet „Text
als Skizzenkontur" mit der **Zeichensatz-Abhängigkeit** („macht aus einer
Projektdatei eine, die auf einem anderen Rechner anders aussieht"), das Konzept
(Zeile 762–768) mit der **Struktur von `Profile`** („trägt genau einen
geschlossenen Umriss"). Beide Gründe sind stichhaltig, aber die zwei Unterlagen
nennen verschiedene. Ebenso führt die ROADMAP „assoziative Skizzenmuster" als
eine der vier Ablehnungen, während §7 sie im Haken zu `bolt_circle`/`hole_grid`
nur nebenbei erwähnt und als [–] allein „Text als Skizzenkontur" markiert.

**Was stattdessen dastehen müsste (Etappe 4, Text als Skizzenkontur):**
Den Grund der ROADMAP mit aufnehmen — „und weil ein Schriftzug den Zeichensatz
des Rechners mitschleppt, auf dem er entstand".

---

## 10. „Import STL/3MF/OBJ/GLB/GLTF/PLY/OFF/STEP/STP/SVG/DXF · Export STL/3MF/OBJ/PLY/STEP" (§2)

**Urteil: überholt** — die Importliste stimmt, die Exportliste ist unvollständig.

**Belege**

```
app/core/ingest/fetch.py:58  ALLOWED_SUFFIXES
  ('.stl','.obj','.ply','.off','.glb','.gltf','.3mf','.step','.stp','.svg','.dxf')   ✓ elf, wie behauptet

app/core/export/writer.py:58 FORMAT_SUFFIX
  stl, 3mf, obj, ply, glb, step        ← GLB kam dazu
```

Der Kommentar bei `writer.py:63` sagt es selbst: „GLB ist das einzige Format
hier, das nicht zum Drucken gedacht ist, sondern zum Zeigen … Gelesen wurde es
längst, hinaus ging es nicht."

**Was stattdessen dastehen müsste:**
> * Export: STL, 3MF (als Baugruppe), OBJ, PLY, **GLB**, STEP

---

## 11. „Die sieben Obergrenzen aus E12 sind als Tests umgesetzt und werden eingehalten" (E12, Etappe 0, Abnahme Etappe 8)

**Urteil: stimmt.**

**Beleg** — `tests/test_interface_limits.py`:

| Grenze | Konstante / Test |
|---|---|
| ≤ 9 Menüs | `MAX_MENUS = 9` (Z. 39), `test_the_menu_bar_stays_readable` |
| ≤ 8 Umschalter | `MAX_TOOLS = 8` (Z. 43), `test_the_tool_strip_stays_a_single_row` |
| ≤ 8 Felder vorn | `MAX_FRONT_PARAMS = 8` (Z. 47), `test_no_operation_floods_the_front_of_its_dialog` |
| genau 1 Menüeintrag je Op | `test_every_operation_has_exactly_one_menu_entry` (Z. 279) |
| ≤ 12 Untermenüeinträge | `MAX_SUBMENU_ENTRIES = 12` (Z. 51), `test_no_menu_becomes_a_list_to_search` |
| 0 Werkzeuge ohne Hinweis | `test_every_tool_says_what_it_expects` (Z. 143) |
| 0 Operationen ohne Symbol | `test_every_operation_has_an_icon_and_every_icon_exists` (Z. 219) |

```
.venv/Scripts/python.exe -m pytest tests/test_interface_limits.py -q
25 passed in 16.79s
```

Gemessen im laufenden Fenster: **8 Menüs** (Datei, Bearbeiten, Objekt, Ändern,
Bausteine, Vorbereiten, Ansicht, Hilfe).

**Eine Zahl darin ist überholt:** E12 begründet die Werkzeuggrenze mit „heute
sieben; die achte Funktion verdrängt eine". Heute sind es **acht**
(`section, measure, transform, analysis, layers, explode, split, paint`) — die
Grenze ist erreicht, nicht mehr unterschritten.

**Was stattdessen dastehen müsste (E12, Zeile 505):**
> | Umschalter in der Werkzeugzeile | **≤ 8** | heute **acht** — die Grenze ist
> erreicht; die nächste Funktion verdrängt eine, oder sie ist keine Leiste wert |

---

## 12. „Der Farbakzent ist vertagt; Anwendungssymbol bleibt kupfer (#e08b4e), Diff-Blau bleibt #3b82c4" (§6)

**Urteil: stimmt.**

**Belege**

```
app/images/icon/solidon3d.svg:7        fill="#e08b4e"
app/images/icon/solidon3d-small.svg:22 fill="#e08b4e"
website/icon.svg:7                     fill="#e08b4e"
website/style.css:42                   --accent: #e08b4e
app/ui/palette.py:196                  added=Encoding("#3b82c4", "forward", "+", ADDED_LABEL)
```

Weder `#0A84FF` noch das vorgeschlagene `#2E6B9E` kommen irgendwo im
Repository vor. Der Kasten „Entscheidung vom 03.08.2026: zurückgestellt" gilt
unverändert.

---

## 13. „Die Höhenkarte aus einem Graustufenbild fehlt … Notiert, nicht gebaut" (Etappe 5)

**Urteil: überholt.** Sie ist gebaut — als eigene Operation.

**Belege**

* `app/core/geom/displace.py:315` — `@register_op(name="displace_image",
  title=_("Relief auflegen"), category="surface", …)`
* Modul-Docstring (`displace.py:1`): „Displacement über ein Höhenfeld (Bauplan
  §25, **Konzept P16 Entscheidung G**). Ein Bild wird zur Geometrie … hier *ist*
  das Höhenfeld der Zweck."
* Der Bildparameter, den das Schema laut Etappe 5 „nicht kennt", existiert
  inzwischen: `app/core/types.py:74` beschreibt die eingebettete Bildquelle,
  `app/ui/main_window.py:5901` ruft die Operation mit `{"source": source_id}`.

**Die zweite Hälfte der Behauptung stimmt:** `apply_texture` führt weiterhin
genau **acht** Muster — `app/core/geom/texture_ops.py:40` `PATTERNS = ("rib",
"wave", "knurl_straight", "knurl_diamond", "hexagon", "dimple", "voronoi",
"noise")`.

Damit ist auch E5s „Neun Wege gegen ihre sieben" (Zeile 386–387) wieder
eingelöst — nur eben über zwei Operationen statt über einen neunten Musterwert,
was E11 („eine Operation je Handlung, nicht je Variante") sogar besser
entspricht.

**Was stattdessen dastehen müsste:**
> - [x] **Eine** Operation `apply_texture` mit einem Parameter *Muster* über acht
>       Werte — nicht acht Menüeinträge (E11). Die **Höhenkarte aus einem
>       Graustufenbild** ist bewusst *nicht* der neunte Musterwert: sie ist ein
>       abgetastetes Feld und braucht einen Bildparameter. Sie kam in P16 als
>       eigene Operation `displace_image` („Relief auflegen") in derselben
>       Kategorie.

---

## 14. „Die Bauplanänderungen aus §9 stehen noch aus" (§9, Folgentabelle)

**Urteil: überholt** — zwei der elf Zeilen sind erledigt, neun nicht. Die
Tabelle ist als „was zu ändern wäre" formuliert und gilt für neun Zeilen
unverändert; für zwei ist sie irreführend.

**Erledigt**

| Zeile | Beleg |
|---|---|
| **§25 Operationskatalog** — Kategorie Oberfläche | `3d-agent-bauplan.md:1189` — „**Oberfläche** — Textur auf eine gewählte Fläche prägen oder einschneiden: Rippe, Welle, Rändel gerade und gekreuzt, Wabe, Noppen, Voronoi, Rauschen … als exaktes Gitter, nicht als abgetastetes Höhenfeld" |
| **§26/§32** — MCP | `3d-agent-bauplan.md:1276` — „### 26.6 Fernsteuerung über MCP", mit allen vier Auflagen aus E9 als nummerierte Liste |

**Noch offen** (jeweils geprüft am Bauplan v10, Stand heute)

| Zeile | Befund |
|---|---|
| §25, Rest | Weder **Gitterfüllung** in der Kategorie Oberfläche, noch **Muster** unter Transformation (Z. 1163), noch **Fläche versetzen** / **Aufdicken** unter Formgebung (Z. 1173), noch **Spline / Referenzmaß / Skizzenmuster** unter Skizze (Z. 1169). `grep -n "Gitter\|lattice\|Aufdick\|thicken\|Spline\|Referenzmaß"` findet in §25 nichts davon. |
| §18 Viewport | Kein Abschnitt Darstellungsqualität; §18.1 (Z. 817) nennt weiter nur „Massiv, Drahtgitter, Massiv+Kanten, transparent … Sieben Kameravoreinstellungen". `grep` nach `Kantenglättung\|Umgebungsverdeckung\|Kontaktschatten\|Feature-Kanten\|ViewCube` im ganzen Bauplan: kein Treffer. |
| §19 Bedienung | §19.1–19.3 (Z. 895–920) unverändert: keine Werkzeugregel aus E2, keine sieben Obergrenzen, keine Kürzelbelegungen, keine `?`-Übersicht, kein Symbol je Operation. |
| §10 Register | Das Beispiel bei Z. 538–553 und die Ausgabetabelle führen **kein Feld `icon`** — obwohl `app/core/registry/registry.py:213` es seit Etappe 0 hat. `applies_to` wird bei Z. 543 weiter nur mit „steuert das Kontextmenü am Feature" beschrieben, obwohl es laut `.claude/rules/oberflaeche.md:145` auch die Befehlspalette sortiert. |
| §30.1 | Elemente weiter „Linie, Bogen, Kreis, Punkt" (kein Spline), Bedingungen weiter neun (kein Referenzmaß), und Stufe zwei steht unverändert als Absichtserklärung da — die verlangte Präzisierung („der Editor *ist* ein Viewport-Modus") fehlt. |
| §31 Leistungsbudget | Die Tabelle (Z. 1430–1444) enthält keinen Zielwert für Texturprägung, Gitterfüllung oder die neue Darstellung. |
| §41 Ausbaustufen | Weder **Druckerverbindung** noch **STEP-Kanonisierung** aufgenommen (Z. 1836–1859). |
| §19.1 Farbe / §37.1 Marke | im Dokument selbst als *vertagt* durchgestrichen — konsistent, siehe Punkt 12. |
| `.claude/rules/oberflaeche.md` | **erledigt**: Z. 134–143 führen die Zuordnung „Funktion → Hauptweg". |
| ROADMAP.md | **erledigt**: `ROADMAP.md:2236 ff.` |

**Was stattdessen dastehen müsste (Kopf von §9):**
> Nichts davon wird ohne Ansage geändert. Erledigt sind **§25 (Kategorie
> Oberfläche)**, **§26.6 (MCP)**, `.claude/rules/oberflaeche.md` und die
> ROADMAP. Offen sind:

---

## 15. „Sechs von 68 Modellen im Korpus sind nicht geschlossen" (Etappe 6, thicken)

**Urteil: stimmt.**

**Beleg** — `ROADMAP.md:586` beschreibt den Korpus („68 Modelle aus einem
privaten Druckordner, 106 MB, STL und 3MF"), `ROADMAP.md:598`: „Sechs von 68
sind nicht geschlossen. Das ist bei Community-Modellen normal". Die Zahl 68 ist
an zwei weiteren Stellen als Durchlaufquote festgehalten (`ROADMAP.md:995`,
`:1184` — „68 von 68").

Der eingecheckte Korpus in `tests/data/` ist ein anderer (15 Netze, 10
Projektdateien) — die 68 sind der private Ordner und im Repository nicht
nachzählbar, aber in der ROADMAP belegt.

---

## 16. E14: „§2.2 nennt **drei** Hauptwege" (Zeile 529, 538)

**Urteil: überholt.** (Nicht in der Arbeitsliste, aber eine interne Behauptung
über den Bauplan und damit prüfbar.)

**Beleg** — `3d-agent-bauplan.md:101` — „### 2.2 **Vier** Hauptwege", mit
„**Weg 4 — Organisch formen**" (Z. 121) und dem Nachtrag bei Z. 131:
„**Nachgetragen am 18.08.2026.** Dieser Abschnitt führte drei Wege, während der
vierte längst gebaut war (P16)."

Auch die Regel-Datei, auf die Etappe 0 verweist, führt inzwischen vier:
`.claude/rules/oberflaeche.md:142` — „Weg 4 — organisch formen", `:143` —
„keiner der vier".

**Was stattdessen dastehen müsste (E14):**
> ### E14 — Jede neue Funktion muss ihren Platz in einem der **vier** Wege haben
>
> §2.2 nennt **vier** Hauptwege … · MCP, Kürzelbelegung → in **keinem** der vier
> Wege, also Einstellungen.

---

## Was unverändert trägt

Nicht alles am Dokument ist Zahl. Was ohne Änderung stehen bleiben kann:

* **§1** (die vier Quellen) — extern, nicht Gegenstand dieser Prüfung.
* **E1** („jede übernommene Funktion bekommt die Druckintelligenz") — in Etappe
  5 als Düsen- und Schichthöhenprüfung *vor* dem Bauen belegt
  (`3d-agent-bauplan.md:1193` hat den Satz sogar übernommen).
* **E5** (exakte Gitter statt abgetastetem Höhenfeld) — im Bauplan §25 wörtlich
  angekommen.
* **E9** (MCP mit vier Auflagen) — Bauplan §26.6, `app/core/agent/remote.py:46`
  (`HOST = "127.0.0.1"`), `app/ui/remote_server.py`; Tests: 16 in
  `tests/test_remote.py`, 8 in `tests/test_remote_server.py`. Die Abnahme in
  Etappe 9 nennt „Vierzehn Protokolltests und vier am laufenden Fenster" — auch
  das ist inzwischen mehr geworden (16 und 8).
* **E7** (zwei Belegungen, eine Quelle) — `app/ui/shortcut_schemes.py:25 FUSION`
  mit `sketch_extrude: E`, `push_face: Q`, `fillet_edges: F`,
  `translate_object: M`; die Abnahme von Etappe 8 stimmt Taste für Taste.
* **§10** (der Satz über SindriCAD, Meshy und Druckbarkeit) — Haltung, keine
  Messung.

---

## Empfehlung

Zwei Eingriffe, in dieser Reihenfolge:

1. **§2 und §2.1 als Momentaufnahme kennzeichnen**, nicht fortschreiben. Der
   Absatz beginnt heute mit „Erhoben am 03.08.2026 gegen den Arbeitsbaum" —
   ein Satz mehr („die Etappen in §7 haben diesen Stand überholt; die aktuellen
   Zahlen stehen in ROADMAP.md") nimmt dem ganzen Abschnitt die Alterung, ohne
   dass ihn je wieder jemand nachzählen muss. Das ist billiger als elf Zahlen
   zu pflegen, die in vier Wochen wieder falsch sind.
2. **Etappe 1, ViewCube, richtigstellen** (Punkt 5b) und den Abnahmesatz von
   der abgeschafften Ansichtsleiste lösen. Das ist der einzige Punkt, an dem
   das Dokument etwas als gebaut abhakt, was im Code nicht steht — und der
   einzige, der jemanden in die Irre führt, der danach sucht.

Alles Übrige (Punkte 6, 7, 10, 13, 14, 16) sind Einzelzeilen, die sich beim
nächsten Anfassen mitziehen lassen.
