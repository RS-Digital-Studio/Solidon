# `app/core/sketch/` — Skizzen mit Zwangsbedingungen

2D-Geometrie, die ein Löser bestimmt statt gezogener Punkte (§30.1) — die
Grundlage für alles, was aus einem Umriss entsteht. Der Editor liegt in
`app/ui/sketch_editor.py` (Regeln: `.claude/rules/zeichenflaeche.md`); hier
steht die Rechnung darunter. Herleitungen und Messwerte:
`konzepte/begruendungen/karte-app-core-sketch.md`.

## Der Weg

```
shapes.py     Grundformen (Linie, Kreis, Bogen …)
     │
     ▼
solver.py     Zwangsbedingungen lösen  ──>  bestimmte Koordinaten
     │
     ▼
profile.py    geschlossene Umrisse finden, Hierarchie aus Außen und Löchern
     │
     ▼
ops.py        Extrudieren, Rotieren, Ausschneiden — die Skizzen-Operationen
```

`planes.py` sagt davor, **wo** die Skizze liegt: Grundebene, Fläche des Modells
oder abgeleitete Ebene — versetzt, gekippt, durch drei Punkte. Die abgeleitete
gehört **der Skizze**, steht in keinem Objektbaum und ist eine Zeichenkette im
Parameter, deren Abstand ein Projektparameter sein darf. `frame_for_plane`
schweigt, wenn sie sich nicht auflösen lässt, `frame_for_sketch` sagt warum;
`frame_in_scene` ist der Weg für jeden Verbraucher außerhalb der Skizzen-Ops.

## Die Karte

| Datei | Rolle |
|---|---|
| `solver.py` | Der 2D-Löser (`solve_sketch`) samt Zugmodus, Rang (`_matrix_rank`), Redundanz (`_losses`), Elementgleichungen (`_element_equations`), Kurvenbedingungen (`_curve_equation`, `CURVE_SLOTS`), `closest_on_spline` |
| `profile.py` | Vom gelösten Element zum Umriss: `arc_sweep` (wie weit ein Bogen läuft), `EllipseFrame`/`ellipse_turn`, `spline_controls`, `path_of`, `flat_curve` (Punktfolge der Ansicht) |
| `shapes.py` | Grundformen und Lochbilder; `grid_centres`, die mittige Rasterlage für Skizze und Feldschnitt; `rectangle_between`/`circle_around` (bemaßt, für das Aufziehen) und `simple_shape` (Einfachform für den Schrittdialog) |
| `planes.py` | Wo eine Skizze liegt (oben) |
| `edit.py` | Trimmen (so entsteht der Ellipsenbogen), Verlängern, Versetzen, Spiegeln; Ecken (`corner_at`, `fillet`, `chamfer`); Formen aus zwei Klicks (`polygon_at`, `slot_between`, `hole_grid_between`, `bolt_circle_at`); `project` (exakt über `brep.section`), `face_outline`, `ellipse_from_clicks`, Splinepunkte, `removed`; Strecken auf ein Maß (`scaled`, `stretched`); die Pläne der Kurvenbedingungen (`tangent_plan`, `curvature_plan`, `on_curve_plan`, `equal_axes_plan`, `taken_back`) |
| `ops.py` | Die Operationen der Kategorie „Skizze"; `cut_regions`/`_cut_span` für Tasche und Übergangsschnitt; `_cut_with_tool` für die Schnitte mit Werkzeug; `sketch_join` teilt mit `sketch_extrude` `RaisedOutlineParams` |
| `serialize.py` | **Die ganze Skizze als ein Parameterwert** einer Operation |
| `traced.py` | Ein Sehnenzug aus einem Netzschnitt wird Strecken, Bögen und Kreise (`traced_loop`, für den Nachbau); ein Bogen braucht drei Sehnen bis `MAX_ARC_STEP` und eine Sehnenhöhe bis `sag`; eine gerade Kante kippt nicht zum ersten Punkt einer Rundung (`_exact_part`), eine kurze Strecke fällt ohne Kippen weg (`_without_short`), ein fast tangentialer Bogen wird tangential (`_tangent`, `NEAR_TANGENT`); `on_bisector` hält gerückte Bögen gleichschenklig |

## Warum `serialize.py` der Schlüssel ist

Eine Skizze ist **ein** Schritt im Stapel, weil der Editor in einen
Parameterwert schreibt und die Geometrie erst bei der Auswertung entsteht
(Regel 2) — dasselbe Muster wie `geom/sculpt.py` und `geom/pose.py`; wer es
bricht, bricht die Reproduzierbarkeit.
`sketch_parameter_references(strict=True)` reicht Unlesbares als Fehler weiter,
damit kein beschädigtes Maß als unbenutzt gilt; ohne `strict` meldet die
Operation beim Auswerten. `resolve_sketch_values` löst für Bausteine ohne
Szenenkontext nur Maßwerte in einer Kopie auf, der gespeicherte Text bleibt;
fehlende Namen sind Ausdrucksfehler, nie null. `_created` und `cut_regions`
reichen `ctx.cancelled` an `brep.features.features_of` weiter.

## Stolperfallen

### Der Löser

- **Der Löser rät nicht.** Unterbestimmt bleibt unterbestimmt, widersprüchlich
  heißt `SketchConflictError` mit Vorschlag; gezeichnete Skizzen melden ihre
  Freiheitsgrade, vorgegebene Grundformen nicht. Bei gleichem Rest (bis
  `_TOL`) nennt er die später gesetzte Bedingung (`_worst_constraints`), bei
  einer Doppelung die am stärksten am Nullraum beteiligten (`_losses`).
- **„Konzentrisch" ist keine Bedingungsart**, sondern die Deckung der Mitten,
  und es gibt ein `equal`, kein `equal_radius` — eine zweite Art wäre ein
  zweiter Weg, denselben Sachverhalt zu speichern, zu prüfen, zu migrieren.
- **Der Winkel rechnet als Sinus** (`_angle_equation`): Periode 180, also nur
  Werte echt zwischen 0 und `MOST_ANGLE_DEGREES`; in der Datei in Grad (§11
  gilt den Längen).
- **Eine neue Element- oder Bedingungsart erhöht `format_version`**: Die
  Migration schreibt nichts um, aber ein älteres Programm lehnt ab, statt halb
  zu laden (§16.2). `_CONSTRAINT_TARGETS` und `_CONSTRAINT_KINDS` hält
  `tests/test_sketch.py` deckungsgleich, die Elementarten
  `tests/test_sketch_curves.py`.
- **Der Zug ist ein eigener Modus des Lösers**
  (`solve_sketch(..., dragged=, start=)`): Gezogene Punkte stehen am Zeiger,
  alles andere folgt mit der kleinsten Bewegung ab `start`; zwei Stufen im
  Docstring, `DRAG_STIFFNESS` ein Zwanzigstel wie in SolveSpace. Begrenzt über
  `DRAG_REACH_TRIES`/`DRAG_SLIDE_TRIES`; findet keine Stufe eine Lage oder
  kehren die gezogenen Punkte ganz zurück, bleibt die Zeichnung stehen. Die
  zweite Stufe beginnt am Stand vor dem Schritt, nie am Ende der ersten: Das
  liegt in einem flachen Tal, wohin die Rundung es trägt. Geprüft wird in
  Schritten wie die Maus (`tests/test_sketch_edit.py`).
- **Gelöst wird je zusammenhängendem Teil, in Verschiebungen** (RM-541,
  `_parts`, `_solve_part`): jeder Teil ab null, `x_scale` seine Größe
  (`_part_size`: Streuung aller Punkte, die er liest, gehaltene
  eingeschlossen, mindestens sein größter Längenrest — nie ein Nulltest),
  die dichte Rechnung höchstens `DENSE_FIRST_STEP`. So hängt der erste
  Schritt weder am Nullpunkt noch an anderen Teilen; ein Teil, der schon bis
  `_TOL` gilt, bleibt, einer, der weiter als `FARTHEST_MOVE` liefe oder
  dessen Rest sich in `STALL_WINDOW` Auswertungen nicht halbiert, auch
  (`_watchdog`). Ein kleiner Teil mit vollem Rang rechnet beim Lösen wie im
  Zug über `dogbox` (kürzester Gauß-Newton-Schritt), nie über `lsmr` und nie
  über dichtes TRF, das bei Unterbestimmtheit jeden Schritt auf den Rand
  setzt; `DRAG_STIFFNESS` ist dort die Box. Mit Doppelungen bleibt er bei
  TRF: `lstsq` nähme deren Rauschsingulärwerte für Richtungen.
- **Gerechnet wird um die Mitte der Zeichnung** (`solve_sketch` um
  `_solve_here`): Die Ableitungen rechnen aus Koordinatendifferenzen, und
  weit vom Nullpunkt rauschen sie. Zurück rückt nur, was sich bewegt hat;
  Unbewegtes behält seine Zahl bitgleich. Die Fassung 1 rechnet ohne.
- **Der Löser rechnet über scipy mit BLAS und LAPACK** (SVD, `lstsq`,
  `lsmr`) — die Ausnahme von „kein BLAS" in `.claude/rules/kern.md`.
  Zugesagt ist dieselbe Lage bis `_TOL` an jedem Ort, gehalten von den
  Ortswächtern in `tests/test_sketch.py` (`…_alike_wherever_it_lies`), die
  jede Rundung über Versätze ändern; nur die Größe des Teils rechnet ohne
  BLAS, weil sie den Weg wählt.
- **Die Fassung des Lösers steht an der Skizze** (`Sketch.solver`,
  `types.SKETCH_SOLVER`): `1` rechnet über `_solve_in_coordinates` wie bis
  0.5 (Migration 49 → 50), der Editor ab der ersten Änderung mit der
  heutigen. Wer Lösungen unterbestimmter Skizzen wandern lässt, hebt
  `SKETCH_SOLVER` samt Migration; die Fassung steht im Cache-Schlüssel jeder
  Skizze.
- **Feste Punkte kosten die Zerlegung nichts** (`_matrix_rank` schält
  Einerzeilen dünn ab, `_solve` gibt die `csr_matrix`; der Rest zerlegt
  sich in getrennten Blöcken mit der Schranke der ganzen Matrix,
  `_blockwise_rank`) und zählen nicht ins
  Budget der dichten Matrix (`MAX_JACOBIAN_BYTES`), das sonst alle dichten
  Zeilen samt Kreis-Eichzeilen zählt; `_losses` macht im Fehlerfall alles dicht
  und prüft dasselbe Budget.
- **Ein Bogen mit drei festen Punkten** verliert seine Gleichung, wenn sie an
  den gespeicherten Punkten gilt; sonst bleibt sie, und der Widerspruch wird
  gemeldet.

### Formen, Ecken und Kurven

- **Die zwei gezeichneten Formen halten sich selbst, ohne bemaßt zu sein**
  (`polygon_at` über einen Hilfskreis, `slot_between`; Bilanz im Docstring);
  Lochbilder halten über Bedingungen zwischen den Mitten.
- **Eine Rundung trägt ihre Tangente als Senkrechte** (`edit.fillet`). **Die
  gebrochene Ecke bleibt als Hilfspunkt** (`_held_by_the_virtual_corner`) auf
  beiden verlängerten Schenkeln: `horizontal`/`vertical` vom fernen Ende, sonst
  `parallel` — die lineare Achse geht vor; die Fase misst von dort (Maß plus
  `equal`).
- **Ellipse**: drei Punkte (Mitte, zwei Achsenden), der Bogen fünf (dazu Anfang
  und Ende gegen den Uhrzeigersinn); die zweite Achse steht senkrecht
  (`_ellipse_axes_equation`), welche länger ist, legt die Folge nicht fest;
  Bogenenden über einen winkelfreien radialen Rest (für Kreise genau, sonst
  obere Schranke). Profil und Netz rechnen ohne Winkelfunktion — Parameter als
  Einheitsvektoren, der Sehnenfehler am Parametermittelpunkt gemessen,
  höchstens `MAX_FACET_SAG`; exakt eine `Geom_Ellipse`. Nach einer Booleschen
  ist die Kante ein B-Spline: Steht die Ebene senkrecht auf der Extrusion, holt
  die Flächenkontur die Ellipse zurück (`brep.edit._section_ellipse`, gegen die
  Kantentoleranz), `_exact_outline` rückt Bogenenden auf sie.
- **Kurvenbedingungen** nennen eine Kurve über den ersten Punkt ihres Elements
  (`CURVE_SLOTS`: `on_curve`, `smooth`, `curvature`); Ableitungen aus
  Dualzahlen (`_Dual`), keine zweite Herleitung; `curvature` in Millimetern
  (mal `L²/2`, `L` fest); *Punkt auf Kurve* am Spline an der nächsten Stelle.
  Ein Spline liest einen Übergang nur an einem seiner Punkte, *krümmungsstetig*
  nur an einem Ende. **Wer eine Kurve zerlegt, nimmt ihre Bedingungen mit**
  (`_curve_targets`: zum Stück, das die Stelle trägt; ein Splineanfang behält
  seine Nummer; zwei Bögen einer getrimmten Ellipse hängen über Mitte, Achsende
  und gleich lange zweite Achsen). **Wie eine Bedingung zwischen Kurven
  entsteht, plant der Kern** (`tangent_plan`, `CurvePlan`, `taken_back`); die
  Oberfläche fragt nur.
- **Eine Splinekurve für Vorschau und Körper**: `profile.spline_controls`
  (Catmull-Rom-Bézier) für 2D-Schnittprüfung und B-Rep, eine Kante je
  Teilkurve, Drehsinn aus dem exakten Integral.
- **Ein Bogenpunkt für Vorschau und Körper**: `profile.points_on_circle` setzt
  die Ecken eines Bogens plattformgleich (`mesh.periodic_sin_cos`), für die
  Skizze wie für `geom.sketch_solid`.
- **Kettenenden rasten aufeinander ein** (`profile._starting_at`): verkettet
  wird über `_JOIN_TOL`, der exakte Kern verbindet Kanten nur auf 10⁻⁷ —
  dazwischen entstand ein undichter Körper. Ein Erzeuger meldet einen
  undichten Körper trotzdem als `mesh.not_watertight` (`ops._created`).
- **Strecken bleibt am Bezugspunkt und in seiner Richtung** (`edit.stretched`):
  um den Punkt der Hülle, der dem Nullpunkt am nächsten liegt
  (`_anchor_of`), nur die getippte Achse. Runde Elemente oder eine Bedingung
  ohne Maß, die das nicht übersteht, strecken gleichmäßig (`Stretch.evenly`).
- **Ringe brauchen getrennte Grenzen**: Kreise analytisch, andere über ihre
  B-Rep-Grenzen; Kreuzung, Berührung, doppelte Ringe halten mit Vorschlag.
- **Eine Profiländerung, die Ergebnisse ändert, hebt
  `profile.PROFILE_REVISION`** — sie steht in der Cache-Kennung aller sechs
  Verbraucher (Hochziehen, Tasche, Drehen, Führen, Überblenden, Lochfeld;
  `test_every_profile_consumer_carries_the_profile_revision`).

### Aus dem Körper

- **Die Flächenkontur ist der Rand, nicht der Schnitt** (`face_outline`): die
  Fläche direkt oder über parallele Versatzebenen (`standing_on_feature`); auf
  Grund-, Dreipunkt- oder gekippter Ebene eine Absage, keine Suche. Ränder
  exakt aus `brep.edit.face_loops`, am Netz aus
  `perceive.relations.boundary_rings`; ein Netzring wird nur ein Kreis, wenn
  ein Rundmerkmal Ecken **und** Sehnenmitten auf `MAX_FACET_SAG` belegt.
- **Was aus dem Körper kommt, kommt fest und einmal** (`_held_copy`, auch für
  `project`): Punkte `fixed`, eine Kopie, die nicht folgt; Punkte auf einer
  Geraden fallen weg (`_straight_enough`, Float32-Auflösung am Ort),
  Vorhandenes kommt nicht noch einmal (`_element_key`).
- **Flächenrahmen übernehmen die orientierte Merkmalsnormale**, nie die Mitte
  des Hüllquaders; eine blinde Tasche endet in beiden Kernen genau an Oberkante
  und Tiefe.

### Die Skizzen-Operationen

- **Eine gezeichnete Tasche verschiebt nicht** (`sketch_pocket`): X und Y
  setzen nur die Grundform; die Zeichnung liegt schon in ihrer Ebene. **Die
  Zeichenfläche ist nie „Bis zur Fläche"** (`_is_the_drawing_face`): Absage mit
  der Höhe als Zahl.
- **Sweep an gezeichneter Bahn** (`sketch_sweep`, `along`, `path_sketch`):
  `profile.path_of` gibt eine offene Kette mit zwei freien Enden, auf XZ oder
  YZ (`brep.profiles.PATH_PLANES`), der Anfang im Ursprung — ein Verlauf, kein
  Ort, und ein Kreis ist keine. Die Anfangstangente steht senkrecht zum
  Querschnitt, sonst Absage vor dem Bau; die Umsetzungskennung hält ältere
  Ergebnisse ohne diese Prüfungen aus dem Cache.
- **Übergang aus zwei Zeichnungen** (`sketch_loft`, `top`, `top_scale`,
  `top_sketch`): dieselbe Ebene, gleich viele Umrisse (Löcher je Paar prüft
  `brep.profiles.loft`), verbunden in der Folge von `regions_of`, und der
  `doc`-Satz sagt es.
- **Drehen, Führen und Überblenden schneiden auch**: je Werkzeug eine Operation
  mit einem Eingang direkt hinter ihrem Erzeuger in *Zeichnen …*,
  kein Umschalter (die Eingangszahl steht je Operation fest, `grenzen.md`); das
  Werkzeug entsteht exakt über die Helfer der Erzeuger, liegt über einen
  geprüften Starrkörperzug am Ziel und wird exakt oder über die Rückfallkette
  abgezogen (Stufe in `solver`, `boolean.without_effect`); ungültig exakt
  rechnet am Netz weiter (`sketch.exact_cut_unsound`). Die Nut dreht um
  Richtung und Punkt oder um `axis_feature` (der Punkt sagt dann nur die Höhe);
  der Kanal beginnt ohne Angabe an Ober- oder Unterseite (`heading`) und dreht
  um die Senkrechte (`turn`), eine anders beginnende Bahn wird um die Querachse
  ihrer Ebene gedreht; der Übergang misst wie die Tasche, durchgehend genau bis
  zur Gegenseite.
- **Eine Bahn wird geprüft, bevor der Kern sie baut** (`_check_path`: Kreuzung
  über `profile.crosses_itself`, zu enge Biegung), danach
  `brep.profiles.intersects_itself` — `BRepCheck_Analyzer` hält einen Kreis Ø4
  um einen Bogen R1 für gültig.
- **Ein Übergang zwischen Vielecken fragt, wenn er drehen könnte**
  (`_paired_corners`, nur beim Schnitt: Gleichstand fragt über `ctx.ask`, die
  Antwort geht als `twist` in den Schritt); der Erzeuger bleibt bei
  `CheckCompatibility`, damit alte Projekte gleich rechnen.
- **Ein Lochbild ist eine Grundform mit mehreren Umrissen** (`bolt_circle`,
  `hole_grid` in `PATTERN_CHOICES`, nicht `SHAPE_CHOICES`): nur Hochziehen und
  Tasche; Hauptmaß `length`, dazu `count`, `columns`, `rows`, `hole_diameter`;
  nichts ist assoziativ, ein Projektparameter dreht den Teilkreis.
- **Kein Qt.** Der Editor ruft hier herein, nie umgekehrt.
