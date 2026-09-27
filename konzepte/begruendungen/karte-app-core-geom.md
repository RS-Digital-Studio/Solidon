# Begründungen zu `app/core/geom/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, Datenfluss,
> Einstiege und Stolperfallen verdichtet wurde. Die Karte steht dort; hier
> stehen die ausführlichen Beschreibungen, Messwerte und Anlässe ihres Tages —
> wörtlich, gegliedert nach den Überschriften der Karte.

Grundlage ist die ungesicherte Zwischenfassung der Karte vom selben Tag. Wo sie
einen Absatz gegenüber dem letzten Commit gekürzt oder gestrichen hatte, steht
hier die längere Fassung aus dem Commit (*HEAD-Fassung*); wo sie Neues trug —
die Absätze aus der Paketübernahme der Durchsicht 0.5.1 —, steht ihr Wortlaut.
Ein Vermerk *Früher unter „…“* nennt die Stelle der alten Karte. Was davon
inzwischen als Regel in `.claude/rules/` steht, gilt dort; die Absätze hier
sind der Hintergrund.

## Vorspann

*Früher unter „Grenzen“, HEAD-Fassung — die Regel dazu steht heute in `operationen.md` (der `caveat`).*

- **Der Sehnenzug wird benannt, nicht versteckt.** Eine Verrundung am Netz
  ist ein Vieleck; wie fein, entscheidet `units.MAX_FACET_SAG` — dieselbe
  Zahl, mit der der exakte Kern tesselliert. Wer eine echte Kurve braucht,
  arbeitet an einem `brep`-Körper weiter, und der `caveat` der Operation sagt
  das auch.

## Plattformgleich gerechnet

*Früher im Kopf der Karte, HEAD-Fassung.*

`transform.rotation_about` (und `rotation` um eine Hauptachse) rechnet die
Drehmatrix aus den exakten Winkelfunktionen in `units` (RM-187): Ein rechter
Winkel und eine halbe Drehung sind exakt, und `knowledge/parts/shapes.turned`
nimmt dieselbe Matrix wie `exact.turned`. Mit `math.sin(math.radians(180))`
lag eine um 180 Grad gedrehte Rampe um 10⁻¹⁶ neben der Stirnfläche ihrer
Rippe, und die Vereinigung ließ beide Flächen als Doppelwand ohne Dicke
stehen (Bereichslauf, 21.09.2026).

**Plattformgleich gerechnet wird mit einem kleinen Werkzeugsatz** (RM-187).
Plattformabhängig sind BLAS (`np.dot`, `@`, `inner`, `einsum` auf ARM,
`np.linalg.norm` ohne Achse), LAPACK (`svd`, `eigh`, `lstsq`, `solve`,
`inv`) und transzendente Funktionen aus NumPy wie aus `math`; gleich auf
jeder Maschine sind Grundrechenarten, `sqrt`, `np.cross`, Normen über eine
Achse, `math.hypot`/`math.fsum` und NumPys paarweise Summe. Was dafür da ist:

`tests/test_platform_identity.py` prüft die Wege in `_WAYS` auf einer
Maschine: jede plattformabhängige Rechnung bekommt ein Rauschen von einem ULP
(`platform_noise`), und ein zweiter Lauf tauscht den BLAS-Kern
(`OPENBLAS_CORETYPE`). Wer einen Weg baut, der am Ende Geometrie oder eine
Wahl zwischen Lagen erzeugt, nimmt ihn dort auf.

*Früher unter „Kanten“.*

**Werkzeuge und Eckanschluss rechnen plattformgleich** (RM-166): Längen über
`_length` (`math.hypot`), Skalarprodukte über `units.dot3`/`transform.along`,
Winkel über `mesh.stable_arccos` und `units.exact_sin`/`exact_cos`, die kleinen
Gleichungssysteme über `_solved3`/`_least_squares3` (Cramer, Normalgleichungen)
statt LAPACK, die Kugel über `_icosphere` (trimeshs Unterteilung, elementweise
auf den Radius gelegt), und die Normalen der Züge aus `mesh.stable_normals`.
`tests/test_platform_identity.py` fährt Verrunden und Fase an der schiefen
Tetraederecke (`corner_fillet`, `corner_chamfer`). Plattformabhängig bleiben nur
Entscheidungen fern ihrer Schwelle: die Grenzprüfungen `_reaches` und
`contact_band_limit`, Konvexität und Windung aus trimesh, das Vorzeichen in
`transform.moved`.

## Die Boolesche Rückfallkette (§17.2)

*HEAD-Fassung — Stufen und Vermerke stehen heute im Docstring von `boolean.py` und in `operationen.md`.*

Sie ist das Muster, das dieses Gebiet prägt — kein Sonderfall, sondern der
Normalweg:

| Stufe | Was sie tut | Vermerk |
|---|---|---|
| 1 | direkt durch den Kern | `direct` |
| 2 | verschweißen, entnadeln — ohne ein dichtes Netz aufzureißen —, erneut | `welded` |
| 3 | die Eingangsgeometrie minimal stören | `jittered` |
| 4 | auf Voxeln rechnen, neu vernetzen | `voxel` |
| 5 | aufgeben — mit Befund und Weg nach vorn | — |

**Die Stufe, die es geschafft hat, wird in die Operation geschrieben.** So
rechnet dieselbe Datei gleich nach (§11.3), und der Bericht kann sagen, was
die Zahlen wert sind. Stufe 4 kostet Genauigkeit und läuft **nie
stillschweigend**. In Entwurfsqualität endet die Kette nach Stufe 2, damit das
Iterieren schnell bleibt (§31).

`tests/test_boolean.py` erzwingt jede Stufe einzeln.

*HEAD-Fassung.*

**Vor der ersten Stufe gehen ineinandersteckende Teile eines Eingangs
vereinigt hinein** (`_parts_united_first`, RM-221). An Schalen, die einander
durchdringen, rechnet der Kern nichts Verlässliches: Eine Vereinigung blieb
zweiteilig oder verschmolz still, eine Bohrung machte aus zwei Teilen drei
oder vier, und das Volumen zählte den gemeinsamen Raum doppelt. Gefragt wird
`repair.parts_that_cross` (nur bei mehr als einem Teil, gemerkt je Netz),
vereinigt über `repair.resolve_self_intersections` — denselben Weg wie
*Überschneidungen auflösen* —, und der Befund `boolean.parts_united` sagt es.
Scheitert die Vorfrage oder das Vereinigen, bleibt der Eingang, wie er war.

*Zwischenfassung (Paketübernahme).*

**Nach jeder gelungenen Stufe bekommt das Ergebnis die Darstellung seiner
Eingänge zurück** (`attributes.in_source_layout`, RM-261): Jedes Dreieck, das
der Kern bitgleich übernommen hat, beginnt an der Ecke seines Vorbilds, und
die übernommenen Ecken stehen in der Reihenfolge des Eingangs. Dreiecksfolge
und Koordinaten bleiben die des Kerns. `prepare_ops._without_scars`, das den
Kern ein zweites Mal rechnen lässt, legt ebenso zurück. Warum, steht in
`operationen.md`.

Ein geschlossenes Ergebnis mit positivem Volumen bleibt auch als kleiner
Messkörper gültig. `EPS_GEOM` ist eine Längentoleranz und kein Mindestvolumen;
Kontaktreste entscheidet `kernel_jobs.native_contact` an der Float64-Rechengrenze.
Fertigungsspiel und Restwand bewertet anschließend der fachliche Aufrufer.

*HEAD-Fassung.*

**Dicht per Index ist noch nicht dicht.** `_kernel` verschweißt seine Ausgabe
so, wie jeder Slicer sie verschweißen wird (`_tidied`): Eckpunktpaare unter der
Schweißtoleranz und Dreiecke mit doppeltem Index fallen weg — übernommen nur,
wenn Netz und Volumen es überstehen. Warum, steht an der Funktion und in
`operationen.md` (RM-166); der Kundenweg STL → Operation → STL → Import ist
`test_export.py::test_a_mesh_op_result_on_an_stl_survives_the_weld`.

Kanten- und Flächenoperationen reichen `ctx.quality` durch alle Teilschritte,
auch Werkzeugvereinigung, Eckanschlüsse und Wiederherstellung einer Rundung.
Kein innerer Booleschritt darf den Entwurf auf feine Qualität hochstufen.

**Und `ctx.cancelled` geht denselben Weg.** *Verrunden*, *Fase*, *Wulst* und
die *Formschräge* fragen das Token zwischen den Kanten beziehungsweise den
Wänden und geben es an jeden Booleschritt weiter; innerhalb eines
Werkzeugkörpers ist nichts zu unterbrechen, davor schon. Der Grund ist
gemessen: Eine Lochplatte mit sechzig Bohrungen braucht 2,7 Sekunden für die
Fase über alle Kanten und 6,9 für die Verrundung (§15.6).

Die drei nativen Netzstufen übergeben `Mesh64` an Manifold und lesen dessen
Status und Volumen vor der Rückvernetzung. Nullvolumen bei flächigem Kontakt
wird als leeres Netz weitergegeben; erst `allow_empty` entscheidet, ob das
eine zulässige Antwort ist. Für gedrehte und gekrümmte Kontaktflächen begrenzt
`gamma(8) * max|Koordinate| * Oberfläche` die native Float64-Rundung.
Dieses datenabhängige Band ist keine Drucktoleranz; echte dünne Schnitte
oberhalb der Rechenunsicherheit bleiben erhalten. Dieselbe Grenze gilt je
nativer Zusammenhangskomponente, damit Kontaktreste auch neben echten Körpern
verschwinden. Verbleibende Schalen werden als orientierte Mesh-Puffer angefügt;
eine erneute native Vereinigung würde negative Hohlraumschalen füllen.
Änderungen am gemeinsamen Kern entwerten den Ergebnis-Cache über
`paths.results_cache_dir()` für alle Operationen: im Quellbetrieb durch den
Core-Zeitstempel, im Paket durch die Anwendungsfassung (§38).
Die Plausibilität verwendet
das orientierte Volumenintegral ohne
Schwerpunktdivision und lehnt offene oder umgestülpte Ergebnisse weiterhin ab.
Die native Eingangsgrenze fordert schreibbare C-Puffer; die Rückvernetzung
erzeugt eigene schreibbare Arrays, damit weitere Netzoperationen und
Abstandsmessungen dieselbe Ausgabe übernehmen können. `shared_volume`
verwendet denselben Kern und unterscheidet Kontakt von dünnem Schnittvolumen.

*Früher im Kopf der Karte.*

Erneute B-Rep-Merkmalserkennung in `ops`, `edge_ops`, `face_ops` und
`prepare_ops` erhält denselben `ctx.cancelled`; sie erzeugt kein eigenes
Token und gibt bei Abbruch kein Teilresultat zurück.
In `prepare_ops` reicht dessen `raise_if_cancelled` auch durch Bohrungs-,
Einlauf- und Langlochübernahme bis zu `matching.match`. Der Meshzwilling
verwendet denselben Rückruf bereits bei der Erkennung des neuen Langlochs.

Die allgemeinen Booleschen Nutzerbefehle verwenden bei ausschließlich
exakten Eingängen `brep.edit.boolean` und erhalten deren Körperart. Sobald
ein Mesh beteiligt ist, gilt die Netz-Rückfallkette. Beide Wege prüfen leere
Ergebnisse und wirkungslose Änderungen, bevor sie einen Körper zurückgeben.

## Die Karte

### Grundlage

*HEAD-Fassung.*

`mesh.py` (die Mesh-Hülle um den Geometriekern, §9; `read_mesh` liest nur, was
trimesh zu einem Körper macht — kein 3MF, kein Dateiformatwissen darüber
hinaus, das liegt in `ingest/`; `unique_edges` beantwortet „welche Kanten,
wie oft" über eine Kantennummer statt über `np.unique(axis=0)` — viermal
schneller an 180 000 Kanten, und die Randringe der Merkmalsketten, die
Rückwand-Prüfung der Bausteine und die Fleckennachbarschaft fragen es;
`edge_table` ist die eine Kantenzählung je Netz — Reparatur, Teilezerlegung
(`face_components`, gemerkt je Netz) und Dichtheit lesen sie, und
`is_watertight` samt Umlaufsinn legt sie mit trimeshs Definition in dessen
Cache, statt die Kanten ein zweites Mal gruppieren zu lassen, RM-224; wer
einem Netz nur Dreiecke nimmt, nimmt `without_faces`, wer nur welche anhängt,
ruft `carry_appended_edges` — beide leiten die Zählung ab, statt 3,6
Millionen Kanten neu zu sortieren; `stable_areas` gibt die Flächen einzelner
Dreiecke mit denselben Bits wie `stable_normals`)
· `boolean.py` (die Kette
oben) · `difference.py` (die Differenzansicht §18.7 — sie beschneidet beide
Körper zuerst auf den Quader, in dem sich ihre Häute unterscheiden
(`_changed_region`: Ecken über den Suchbaum zugeordnet, Dreiecke als
Nummer in kanonischer Drehung verglichen); die Differenz liegt in dessen
Hülle, und zwei Schnitte an einer Platte mit 204 000 Dreiecken kosten so
25 statt 366 ms — bleibt die Box über der Hälfte der gemeinsamen Hülle,
rechnet sie am ganzen Körper; von den zwei Schnitten rechnet sie nur, was die
Volumenbilanz |A − B| − |B − A| = |A| − |B| nicht schon beantwortet —
`_empty_by_balance`, RM-212) · `intersections.py` (Selbstdurchdringung als Feld, eine Rechnung für Karte und Bereichstest) · `repair.py` (Netze reparieren: verzweigte Kanten
auflösen (`resolve_branching_edges` — dort liegen Flächen übereinander, die
kleinste geht), Sanduhr-Ecken auftrennen (`split_pinched_vertices` — zwei
Löcher, die sich eine Ecke teilen, sind zwei Ringe), Ränder vernähen und
Ringe schließen (`boundary_loops` + `fill_boundary_loops`, in der Reihenfolge
oben: Band, Fläche mit Löchern, glatteste Triangulierung, Ohren nach Newell,
Fächer als Rückfall, und **keine Fläche auf eine Kante, die schon zwei
trägt**); deckungsgleiche Dreiecke
(`remove_doubled_faces`): gegenläufige Paare sind Taschen und fallen paarweise,
gleich umlaufende Kopien sind Doppelungen und behalten eine, und kein
zusammenhängendes Teil verschwindet ganz; jede Frage nach Rändern und
Verzweigungen liest dieselbe Kantenzählung (`_edge_table`, im Cache des
Netzes) — und dort zwei Nachbarn, die man leicht
verwechselt: `remove_small_components` misst die **Fläche** gegen die größte
Komponente und wirft lose Fragmente, `remove_hollow_shells` misst das
**Volumen** gegen null und wirft Flächenpaare ohne Dicke; ein Bauteil von
einem halben Millimeter hat ein Volumen, eine Haut von hundert
Quadratmillimetern keines) · `attributes.py` (Materialslots durch
eine Operation hindurch behalten, §20) · `enclosure.py` (Konturverschachtelung
ohne `rtree`) · **`lathe.py`** (Drehkörper, deren Ecken auf jeder Maschine
dieselben Bits tragen — `cylinder`, `annulus`, `revolve`, `circle_points`;
die Topologie macht weiter `trimesh`, ersetzt werden nur die Ecken, und ob
die Struktur dafür passt, prüft es bei **jedem** Aufruf nach. Der Anlass
steht in RM-187: `np.cos` wählt seine Implementierung nach der CPU, und aus
drei Zehnteln eines Billiardstels Millimeter wurden nach einer Booleschen
Operation 1224, 1226 und 1228 Dreiecke an demselben Körper)

*Zwischenfassung, im selben Absatz ergänzt (Paketübernahme):*

`mesh.py`: „`on_surface` fragt einen Index, der die Bäume seiner
Größenbänder hält — wer denselben Körper mehrmals fragt, hält ihn
(`surface_index`, `prepare.surface_index_of`); `lifted_caps` hebt ebene Deckel
samt Wand an, der Netz-Zwilling von `brep.edit.collared`“. `boolean.py`:
„`body_split` ist das eine Urteil über einen zerfallenden Körper“.

*Früher unter „Netz, Farbe, Text“, HEAD-Fassung.*

**`mesh.on_surface` sucht ohne `rtree`** — und seit dem 22.09.2026 ohne
eine Python-Liste je Abfragepunkt: Die Kandidaten kommen je Größenband als
dünn besetzte Matrix aus dem Baum (`sparse_distance_matrix`, in Portionen
gleichen Radius; vereinzelte ferne Punkte gehen den Listenweg), zwei exakte
Siebe (Spanne je Dreieck, Abstand zum Quader um das Dreieck) lassen an
Nadeldreiecken einen Bruchteil übrig, und der Sieger je Punkt kommt aus
`np.minimum.at` statt aus einem `lexsort` über Millionen Paare — kleinster
Abstand, darunter kleinste Nummer, dieselbe Antwort wie zuvor. Der Index
dahinter (`_SurfaceIndex`: Dreiecke, Schwerpunkte, Spannen, Quader, Baum)
wird einmal gebaut und beliebig oft gefragt. Und `mesh_ops.deviation` stellt
nur **eine** Frage, das Maximum: `mesh.max_distance_to_surface` misst exakt,
aber nur die Punkte, deren Schranke das Maximum noch heben kann — erst die
Schranke aus dem nächsten Schwerpunkt, nach dem ersten Maß die engere aus
acht Schwerpunkten und den Dreiecken an den nächsten Ecken
(`bound_at_corners`, für große Dreiecke mit fernem Schwerpunkt), dann in
wachsenden Portionen exakt, bis keine Schranke mehr über dem Gemessenen liegt
(am Besenhalter mit 97 Prozent Nadeln: 2,9 → 0,25 s). Was neben einer alten
Ecke liegt, wird gar nicht gefragt: Der exakte Kern lässt beim Vereinfachen
Ecken weg statt sie zu verschieben, und ein Punkt auf einer Ecke hat
Abstand null.

*Früher unter „Messen und Schneiden“, HEAD-Fassung.*

**Die Wandstärke der Bereichsprüfung rechnet seither ebenfalls ohne
Index** (RM-050, 23.09.2026): `knowledge/parts/range_check.local_wall_thickness`
ersetzte VTKs `vtkStaticCellLocator` durch `mesh.ray_hits_batch` — dieselbe
Möller-Trumbore-Rechnung wie `ray_hits`, aber über zwei Achsen zugleich (viele
Strahlen, dieselben Dreiecke) und blockweise über die Dreiecksachse, damit der
Speicher begrenzt bleibt. Das Paket `vtk` ist damit keine Abhängigkeit mehr.
**Ab `RAY_CULL_PAIRS` Paaren wählt `ray_hits_batch` die Dreiecke je
Strahl über einen räumlichen Index vor** (`_indexed_ray_hits`, RM-214): ein
Baum aus Hüllquadern über Blättern von `RAY_INDEX_LEAF` Dreiecken in
Morton-Reihenfolge; jeder Strahl steigt ihn mit einem Scheibentest hinab
(`_crossing`) und rechnet nur gegen die Dreiecke der Blätter, deren Quader er
durchquert. Die Quader sind um das baryzentrische `edge_margin` und ein
Milliardstel der Szenendiagonale gewachsen. Der Index entscheidet nur, welche
Paare gerechnet werden — jedes gerechnete Paar trägt dieselben Bits wie im
Vollvergleich, Gleichstände behält die kleinste Nummer, und der Beweis steht
an der Funktion; ausgenommen sind nur fast streifende Treffer an der Grenze
von `RAY_PARALLEL_EPS`, deren Lage auch der Vollvergleich nur gerundet kennt.
Ein negatives `minimum_travel` und nicht endliche Strahlen rechnen voll; hält
eine Strahlgruppe mehr als `RAY_INDEX_PAIRS` Paare, teilt sie sich. Ohne Index
war die Wandstärke quadratisch (Dichtschnur mit 45 368 Dreiecken: 378 s); die
Vorauswahl nach Reichweite davor half an dünnen Wänden, kostete an
Vollkörpern aber mehr als der Vollvergleich. Mit dem Index (26.09.2026, unter
Last, bitgleich zum Vorgänger): Vollkugel 12 800 Dreiecke 31 → 0,5 s, Vollkugel
51 200 Dreiecke 2,0 s bei 47 MB Spitze, Hohlkugel 7,6 → 0,6 s, Platte mit 96 Bohrungen
(37 260 Dreiecke) 16,9 → 4,6 s. `tests/test_geometry_review.py` vergleicht
bitgleich gegen den Einzelstrahl und trägt je Sicherung einen konstruierten
Fall; jede Sicherung einzeln herausgenommen macht ihn rot.

*Früher im Kopf der Karte, HEAD-Fassung.*

**Die Selbstdurchdringung rechnet `intersections.py`, und zwar für beide
Fragesteller** (RM-206): `repair.self_intersecting_faces` (welche Dreiecke,
für die Netzfehlerkarte, mit Paarbudget) und
`knowledge/parts/range_check.has_self_intersections` (ob überhaupt, für den
Bereichstest, vollständig). Kandidaten über Sweep-and-Prune, bei großen
Netzen in Scheiben entlang einer zweiten Achse — Achsen und Breite wählt
`_plan` an einer festen Stichprobe (Baum 166 000 Dreiecke: 146 Mio. statt
8 Mio. Sweep-Paare, 16 s → 5 s; jedes Paar zählt nur in der Scheibe der
unteren Ecke seiner gemeinsamen Hülle) —, danach die Trennprüfung
(`_separated`: eine Ebene oder in der Draufsicht eine Kante trennt mit
Abstand, eine gemeinsame Ecke nur in derselben Ebene; RM-244), dann je Paar
als Feld: Ecken innerhalb `EPS_GEOM` sind ein topologischer Punkt, nicht koplanare Paare
entscheiden ihre Schnittstrecken auf der Schnittgeraden, koplanare der
Trennachsensatz. Die Karte rechnete bis zum 22.09.2026 Möller-Trumbore und sah
zwei deckungsgleiche Dreiecke derselben Ebene nicht, ebenso wenig ein Paar,
das sich eine Ecke teilt und trotzdem durch das andere läuft; der Bereichstest
lief als Python-Schleife über VTK-Kontakte (Schraubenloch 1,5 s je Ecke,
jetzt Millisekunden). Und
`ops.repair_object` gibt einen Eingang, an dem nichts zu reparieren war,
unverändert zurück: Ein exakter Körper bleibt exakt, statt als Netz mit
„nichts zu reparieren" zurückzukommen.

`deviation.deviation_bounds` prüft ausgefüllte Originaldreiecke gegen einen
bereits belegten analytischen `SurfacePatch`, ohne neue Formeinpassung.
**Gerechnet wird je Trägerart für alle Dreiecke zugleich** (`_Batch`,
`deviation_bounds_grouped` für viele Träger in einem Aufruf, Ergebnis als
`DeviationTable` aus Arrays): Die Array-Klammern `_Bands`/`_A` tragen dieselbe
Zusage wie `_I` — Summe, Produkt und Quotient um mindestens ein ULP nach außen
gerundet (arithmetisch, `|x|·2⁻⁵¹ + 5·10⁻³²⁴`, weil `np.nextafter` das
Dreißigfache kostet), jede Wurzel durch exaktes Quadrieren nach Dekker
bestätigt, unter `2⁻⁹⁶⁸` die exakten Zweierpotenzen als Schranke. Das Dreieck
ist die letzte Achse (`(…, 3, n)`), damit jede Operation über zusammenhängende
Zeilen läuft. Der Stapel rechnet nur unter `_BATCH_MAGNITUDE`, wo nichts
überläuft; Ebene, Kugel, Zylinder und Kegel enden dort, **und der Torus seit
dem 22.09.2026 auch**: `torus_refine` führt im Stapel dieselbe Rechnung, die
`_torus` skalar je Dreieck führt — die vier glatten Innenkandidaten und die
Kantenstücke. Geteilt wird dabei nicht blind, sondern an den Stellen, an denen
der Abstand kehrt: `_torus_breakpoints` löst dafür eine Quartik
(`m²·r² - R²·h² = 0`, Wurzeln aus den Eigenwerten der Begleitmatrizen, im
Stapel für alle Dreiecke in einem `np.linalg.eigvals`), und `_TORUS_HALVINGS`
halbiert jedes Stück noch zweimal, weil die Sehnenschranke mit dem Quadrat der
Stückbreite fällt. Den skalaren Weg geht nur noch, wessen Achse das Dreieck
treffen könnte — dort braucht die Kandidatenmenge exakte Bruchrechnung
(`_axis_candidates`). Gemessen am 21.09.2026: Lochplatte 449 → 11 ms,
Lochblech 10 mal 10 10,8 s → 132 ms, Dose mit Deckel 11,8 s → 98 ms, Ring
2,4 s → 127 ms bei identischen Klammern.
**Und das Verfeinerungsbudget gehört dem Dreieck, nicht dem Träger**
(`_MAX_REFINEMENTS`). Bis zum 22.09.2026 galt es je Aufruf: Die ersten
Dreiecke eines Rings verbrauchten es, alle weiteren bekamen die
Rechteckklammer — an 4 096 Ringdreiecken im Mittel 0,16 mm breit, wo die
übrigen Träger auf Mikrometer schließen. Jetzt sind es 0,0021 mm, und die
Analysekarte einer Verrundung rechnet in 0,53 s statt 30 (RM-202).

*Früher im Kopf der Karte.*

Ebene, Zylinder, gerichteter Kegel, Kugel und Ringtorus teilen gerichtete
Zahlenklammern und echte baryzentrische Zeugen. Deren zwei Floatparameter
bezeichnen eine exakte reelle Kombination der Originalecken; gerundete
Anzeigekoordinaten begründen keine Untergrenze. Kugel und Zylinder verwenden
konvexe Radiusgrenzen, der Kegel globale konkave Stützebenen, der Torus
vollständige Kantenintervalle und eingeschlossene Innen-/Achsenkandidaten.
Die einmalige Kegelwinkelklammer verwendet begrenzte exakte Taylor-Terme;
deterministische punktförmige Winkelfunktionen allein wären kein Fehlerbeweis.
Die Kantenarbeit ist je Dreieck begrenzt (`_MAX_REFINEMENTS`), einschließlich
der anfänglichen Intervalle — ein Budget je Träger verbrauchten die ersten
Dreiecke eines Rings allein. Nach Verbrauch bleibt eine schnelle gültige Klammer.
Jede Ausgabe trägt Unter-/Obergrenze in mm und kennzeichnet die erreichte
Zielbreite. Der Abschluss bestätigt erneut endliche, geordnete Grenzen,
auch nach einer numerisch offenen Verfeinerung. Nicht endlich einschließbare
Eingaben bleiben unbekannt; Abbruch propagiert auch während Vorbereitung und
Verfeinerung. Keine neue Geometrie,
keine Reparatur, kein eigener Karten- oder Projektcache entstehen dabei.

*Früher im Kopf der Karte, HEAD-Fassung.*

`contours.section_of` übernimmt einen gezeichneten Querschnitt mit allen
Innenringen unabhängig von der Umlaufrichtung; ungültige Konturen werden
nicht still repariert. `polygons_of` gibt alle Komponenten mitsamt ihren
Löchern zurück. `offset_section` versetzt normal mit runden Übergängen:
positiv wächst Material, negativ schrumpft es; Aufspaltung oder Kollaps
bleiben sichtbar. Fertigungsspiel kommt ausschließlich vom Aufrufer. Die
Eckenzahl der Bögen (`_round_steps`) ist die kleinste durch vier teilbare,
deren Sehnen `MAX_FACET_SAG` einhalten — entschieden über `units.exact_cos`,
nicht über `ceil` einer Bibliotheksfunktion.
`sketch_solid.outline_points(max_sag=...)` nutzt die gemeinsame echte
Splinekurve mit begrenzter Sehnenabweichung, Abbruch und Punktbudget.
Ohne diese optionale Grenze bleibt die bisherige Abtastung erhalten.

### Bewegen und Ausrichten

*Früher im Kopf der Karte, HEAD-Fassung.*

`transform.moved_object` führt analytische Merkmalteilträger zusammen mit
der Form weiter. Native Neutessellierung ordnet jeden Teilträger über die
tatsächlichen alten und neuen Topologieflächen zu — über die Umkehrabbildung
Fläche → Dreiecke, die `_triangles_by_face` je exaktem Körper einmal baut und
in `solid._cache` ablegt (statt je Merkmal über alle Dreiecke zu suchen: 124
Suchläufe an 31 Merkmalen, Review 21.09.2026). Ein unbelegter Ausschnitt
einer nativen Fläche entfällt als Träger, statt zur ganzen Fläche zu wachsen.
Punkte, Normalen, gerichtete Kegelnappen und Radien werden anschließend
einmal über `perceive.surfaces` transformiert; der Operationsabbruch reicht
bis in diese Zuordnung. Netztransformationen erhalten die Dreiecksreihenfolge.

*HEAD-Fassung.*

`transform.py` · `ops.py` (Kategorie „Transformation") · `align.py` (Merkmale
in Flucht bringen)

`transform.moved_object` führt Körper und Merkmale gemeinsam in den
Ergebnisraum. Transformationen, Muster, Druckausrichtung und Anordnung
verwenden denselben Weg. `transform.apply` gibt der bewegten Kopie mit, was
das Quellnetz über seine Topologie schon wusste (`_carry_cache`:
Nachbarschaften, Kanten, Teilezahl, Fleckennachbarschaft; bei starrer
Bewegung auch Facetten, Winkel, Flächen, gedrehte Normalen und die Randringe
der Merkmalsketten) — `copy()` gäbe ein Netz mit leerem Gedächtnis, und die
Auswertung fragte danach alles neu. Bei einer Spiegelung wandert nichts mit:
Der Umlaufsinn dreht sich, die Kantentabellen stimmten nicht mehr. Ein exakter Körper bleibt auch bei ungleichmäßiger
Skalierung exakt; sein Anker kommt aus den nativen Grenzen. Die Historie des
nativen Builders ordnet vollständige alte Topologieflächen den neuen Flächen
zu, deren aktuelle Dreiecke anschließend die Auswahl tragen. Teilmengen einer
nativen Fläche werden bei neuer Tessellierung nicht still erweitert.
`perceive.matching.transformed_features` führt die belegten Maße nach;
eine zum elliptischen Querschnitt verzerrte Kreisfläche behält kein altes
Kreismaß. Eine zusätzliche Bettkorrektur durchläuft denselben Weg erneut.
Der Abbruch aus `OpContext.cancelled` reist bis in die native Maßprüfung und
deren begrenzte Python-Integration. Eine Unterbrechung bleibt
`OperationCancelled`; sie wird weder als Geometriefehler noch als Anlass
für einen weiteren Integrationsweg behandelt.

*Früher im Kopf der Karte.*

`place_on_bed` bleibt eine Einzeloperation; `place_group_on_bed` erhält alle
gespeicherten Eingaben mit derselben Translation. Beide verwenden denselben
Helfer, der den tiefsten aktuellen Z-Wert auswertet. Kein im UI vorberechneter
Versatz: Vorgängeränderung, Cache und Wiederöffnung müssen dieselbe Absicht
neu rechnen. Merkmale und B-Rep bleiben über `moved_object` erhalten.

### Körper erzeugen und formen

*HEAD-Fassung.*

`primitive_ops.py` (Quader, Zylinder, Kegel oder Kegelstumpf, Kugel und Ring
am Netz; Kegel und Ring dienen auch als verständliche Werkzeugkörper für
Boolesche Ops. **Seit P2.8 sind die Netz-Erzeuger die versteckten Zwillinge**:
Wo der exakte Kern da ist, zeigt das Menü `brep/ops.create_brep_*`, und
`ANCHORS` sowie `tube_fits_the_ring` stehen hier einmal für beide Kerne)
· `blend.py` (weiches Verschmelzen — sein Abstandsfeld misst den Weg zur
**Ebene** des nächsten Dreiecks, nicht zu seiner Mitte: Die Oberflächenwolke
ist diskret, und der Weg zum nächsten Punkt fällt vor einer ebenen Wand
wellig aus. Eine Wand zerfiel damit in 67 koplanare Gruppen, und die
Erkennung las daraus Schichten; das neue Netz bekommt die Filamente beider
Körper über `attributes.transfer`) · `displace.py`
(Höhenfeld — nur die der Projektion zugewandten Eckpunkte wandern, in ihrer
Richtung: von oben senkrecht, um die Achse radial, auf eine Fläche nur deren
Dreiecke entlang ihrer Normalen) · `lattice.py` (Gitterfüllung; die Wabe teilt
ihre Wände, der Gyroid sagt ab, wo der Hohlraum für seine Zelle zu groß ist)
· `texture_ops.py`
(Oberflächentexturen als echte Geometrie) · `sculpt.py` · `pose.py`
(Skelett und Stellung) · `sketch_solid.py` (einen Skizzenumriss zu einem Netz
aufziehen)

*Früher im Kopf der Karte.*

Die Oberseitenmerkmale der Meshgrundformen lesen Fläche und Mitte aus
`top_face_of` an den tatsächlichen Dreiecken. Der gemeinsame Merkmalshelfer
bekommt dafür `facets` als Quelle; die vorgegebene Flächennormale bleibt
`parameter`. Ein erzeugter Name ändert diese Messquelle nicht.

Die fünf analytischen Grundkörper entstehen lokal über
`primitive_local_tool()`. Operation und temporäre Oberflächenvorschau beziehen
damit denselben Körper auf denselben Ursprung. `x/y/z` verschieben diesen
Bezugspunkt; eine gesetzte `nx/ny/nz`-Richtung legt sein lokales +Z über
`sketch.planes.frame_of()` in den Raum. Der Nullvektor bewahrt die bisherige
aufrechte Lage. `angle` dreht ihn zusätzlich um seine eigene Hochachse —
`frame_of` legt die Querachse deterministisch, aber nicht wählbar fest, und
für einen Quader ist das der Unterschied. Der Name ist derselbe wie bei den
Bausteinen; das Register zählt ihn zu den Platzierungsfeldern
(`PART_PLACEMENT_PARAMS`), und damit gehen die Grundkörper denselben Weg durch
die Oberflächenplatzierung.

*HEAD-Fassung.*

`texture_ops.texture_tool()` erzeugt den gemeinsamen Werkzeugkörper für
Vorschau und Operation. `coverage="whole_face"` bindet die gewählte ebene
Fläche über ihre Kennung, schneidet die Musterpolygone an ihren tatsächlichen
Dreiecken zu und hält Innenringe sowie konkave Ränder frei. Eben heißt
dabei `faces.FLAT_ENOUGH_FOR_A_TOOL` (ein Viertel des Booleschen Überlapps)
und nicht `EPS_GEOM` — eine schräge STL-Fläche liegt um ihre float32-Rundung
neben der Ebene; die Dichtnut fragt dieselbe Grenze. Die Drehung gilt
innerhalb dieser festen Kontur. `rectangle` bleibt die Vorgabe für vorhandene
Operationen mit freier Position und Breite/Höhe. Beide Wege enden in
`tool_in_outline()`, das auch *Merkmal ändern* an einem gelesenen Muster
ruft (`prepare_ops._resize_pattern`): mit dem gelesenen Stil (oder dem
gewählten — ein fremdes Muster `other` bekommt so einen eigenen Stil), Feld und
Winkel, und mit `cell=` der gemessenen Zellbreite — `pattern_shapes()`
rechnet daraus je Stil den Anteil an der Teilung, `cell_width_for()` sagt,
was Teilung und Drucker davon zulassen: Die Wand zwischen zwei Zellen bleibt
so breit wie sein kleinstes Detail (`wall=`, die Bahn bei FDM, der Bildpunkt
bei Resin — `PrinterProfile.smallest_detail`), und die Berührgrenze ist je Stil eine andere
(`_max_share`: Rauten berühren sich schon bei 1/√2). Überlappende Umrisse (die Streuflecken des
Rauschens) führt `_merged()` vor dem Extrudieren zusammen; getrennt
extrudiert ließen sie doppelte Dreiecke auf der Deckfläche zurück. Das
flache Werkzeug selbst baut `flat_tool()`; `tool_in_outline()` legt es auf
die Ebene, ein gelesenes Muster legt es über `perceive.patterns.Field.placed`
ab — auch um einen Zylinder.

**Um einen Zylinder** (`wrap="cylinder"`) teilt `refined_for_bending()` das
Feld vorher so fein, dass jede Kante des Feldes höchstens `BEND_SAG` unter
dem Bogen hängt (`mesh_ops.refined`, ein Durchgang des exakten Kerns, konform
und je Schale getrennt; die Diagonalen im Inneren einer Fläche bis zum
Dreifachen, unter `MAX_FACET_SAG`),
und `wrapped()` biegt danach die Ecken: Rillenböden und Kronen folgen dem
Zylinder, die Tiefe bleibt die verlangte. Ein Feld, das den Umfang erreicht,
bekommt über `wrap_pitch()` die Teilung, mit der es aufgeht (Finding
`texture.pitch_wrapped`), wird über mehr als eine Runde gezeichnet und je
Zelle einmal gewählt (`_one_turn()`) — an der Naht wird keine Zelle
geschnitten, denn zwei an `±π·R` getrennte Hälften verschweißt die Boolesche
Rechnung nicht zuverlässig. `STRIP_PATTERNS` sind die Stile, deren Zelle so
lang ist wie das Feld.

`sketch_solid.py` ist das Gegenstück zu `brep/profiles.extrude` für den Fall,
dass kein exakter Körper vorliegt — und dieser Fall ist der häufigste: Wer ein
heruntergeladenes STL öffnet, hat ein Netz. Bis zum 30.08.2026 endete das
Abtragen dort an einem Satz („besteht bereits aus festen Dreiecken"); seitdem
schneidet `sketch_pocket` über die Boolesche Kette auch in ein Netz. Was dabei
entsteht, ist wieder ein Netz — der Unterschied bleibt, die Absage nicht.

`sculpt.py` und `pose.py` sind **Sammelparameter-Ops**: viele Gesten, ein
Schritt. Das Ergebnis folgt vollständig aus den Parametern, was das Fenster
währenddessen zeigt, ist Vorschau. `tests/test_gesture_ops.py` prüft das über
das ganze Register.

`pose_parameter_references(strict=True)` meldet unlesbare Stellungswerte
sofort. Die Verwendungsabfrage kann damit unbekannte Abhängigkeiten von
unbenutzten Maßen unterscheiden. Skelettlisten enthalten Koordinaten und
keine Projektmaße; nur die Winkelwerte der Stellung sammeln Referenzen.
Der Standardvertrag bleibt für den Cache erhalten: Die Operation meldet
beschädigte Texte bei ihrer Auswertung.

*Früher im Kopf der Karte.*

`seal.py` erzeugt Dichtnut und unverformten Dichtring — als Formen mit zwei
Auswertern (P2.7): Band und Versatz über `knowledge/parts/section.Section`,
die Schnur am Netz als Kapselkette, exakt als `brep.profiles.round_cord` — aus demselben
geschlossenen Weg und normalem Versatz. Runde Querschnitte verwenden die
Vereinigung identisch facettierter Kugelhüllen, damit gemeinsame Bahnenden
keine inneren Kappen zurücklassen. `opening_choices` bindet Innenringe an
die tatsächlichen Dreiecke einer gewählten Trägerfläche; ihre begrenzte
versionierte Signatur beschreibt lokale Konturen und Topologie, keine
Listenposition. `match_opening` liefert nur eine eindeutige belegte Wahl.
Starre Bewegungen führen den lokalen Rahmen mit; veränderte oder mehrdeutige
Flächen verlangen über `ctx.ask` eine neue gespeicherte Antwort.

`seal_ops.create_seal` erhält den Träger und erzeugt eine separate Dichtung.
Beide Materialien sind ausdrückliche `material_params`; der gespeicherte
Gegenflächenbezug liest über `reads_other_bodies` den aktuellen Szenenstand.
Der gemeinsame `sketch.ops.cut_regions` erhält Mesh- und B-Rep-Schnittwege.
Ein geometrischer Materialmantel bestätigt Boden- und Seitenrestwand aus
dem aktuellen Material-/Druckprofil; die Dichtung darf den verbleibenden
Träger nicht schneiden. Die optionale Gegenfläche wird an ihren wirklichen
Dreiecken auf parallele Gegenrichtung und vollständige Überdeckung geprüft.
Abstand, unverformte Überdeckung und Schnittvolumen sind geometrische
Auskünfte und behaupten weder Materialverformung noch Dichtheit.

Beim ausdrücklichen Materialwechsel des Dichtträgers bleiben die über den
Taschenschnitt übertragenen Farbflächen und Slotnummern erhalten. Nur
inkompatible Herstellerprofil-/Materialbindungen werden am Ergebnis gelöst;
der Befund nennt die nötige Neuzuweisung. Gleiches Material behält seine
Zuordnung. Globale Spulenbindungen und der Eingabekörper werden nicht geändert.

`profile_clamp_ops` erzeugt vier feste Rollen: untere/obere Schale und
untere/obere Einlage. Beide Materialfelder sind ausdrückliche Profilkennungen
und über `material_params` Hashabhängigkeiten. Eine gemeinsame Kontur wird
einmal gelöst; originale Skizzenausdrücke bleiben im Operationsparameter.
Der Sitz hat normales Gesamtspiel aus beiden Profilen, die Gegenkontur das
Pressmaß der Einlage. Fertigungsspiel und Sehnenabweichung bleiben getrennt.
Alle vier Rollen liegen in einem Rahmen: Die Einlage sitzt mit ihrem Bund bei
null, die Schale bekommt die Bundhöhe als `lift` — die Schale allein kennt
dieses Maß nicht (`knowledge/parts/CLAUDE.md`).

Der Ersatzweg erhält beide Schalen unverändert und prüft den gesamten
Hohlraum, einen umlaufenden Materialstreifen sowie die wirklichen
Stirnflächen. Die Bindung liegt als `profile_clamp` auf der echten
Frontfläche; lokale Gegen-, Außen- und Sitzkonturen sind Beschreibungen,
keine eigenständigen Passungsmerkmale. Ein starrer oder gespiegelter Rahmen
wird über Mittelpunkt, Normalenrichtung, X und `profile_clamp_y` mitgeführt.
Skalierte oder veränderte Sitze bestehen die Geometrieprüfung nicht allein
wegen erhaltener Metadaten. Gleiches Sitzspiel erhält die vorhandene
Einlagenaußenkontur exakt; neues Spiel wird vom festen Sitz nach innen
abgetragen und erneut auf Mindestwand geprüft.

Alle vier Teile dürfen unabhängig angeordnet sein. Die Schalen werden jeweils
in ihrem eigenen Rahmen gegen den Sitz geprüft, die alten Einlagen gegen
ihre vollständige Konstruktion. `liner_clearance` und `counter_press` speichern
dazu die tatsächlich angewandten Zugaben, getrennt von der heutigen
Materialkalibrierung. Jede Ersatz-Einlage behält ihren eigenen belegten
starren Rahmen und ihre Druckplatte. Diese Prüfung beschreibt die Form des
Anschlusses, nicht einen behaupteten Kontakt der momentan angeordneten Teile.

Beim Einlagenwechsel erhält `attributes.transfer` bestehende Filamente am
gleichen Material. Ein ausdrücklicher Materialwechsel löst die alte
Spulenidentität und meldet die nötige Filamentauswahl. Die Operation schreibt
weder Projektzustand noch globale Spulenbindungen; ungenutzte Bindungen sind
kein Beleg für die neue Einlage.

`field_ops.field_tools` bereitet vollständige Öffnungen in bestehenden
Skizzenprofilen vor. Innenringe und getrennte Regionen bleiben erhalten,
Ausschlüsse werden mit Randabstand berücksichtigt. Das gemeinsame mittige
`sketch.shapes.grid_centres` liefert die Rasterlage; der Feldursprung bleibt bei
einer Größenänderung fest. Ränder und Stege prüfen den ganzen Werkzeugumriss,
nicht nur den Mittelpunkt. Gekrümmte Grenzen werden konservativ begrenzt;
exakte Splineflächen verwenden dieselbe B-Rep-Kurve wie der Schnittweg.
`field_cut` nimmt zwei normale Skizzenwerte (Pflichtbereich und optionale Ausschlüsse)
auf derselben Ebene. Der gemeinsame `sketch.ops.cut_regions` bewahrt Tiefe,
Durchgang und Flächenrahmen auf beiden Kernen. Materialkompensation ist
ausdrücklich auf Kreis und Langloch begrenzt; beim Langloch wachsen Breite
und Gesamtlänge um dieselbe Materialzugabe.
Runde Öffnungen erhalten stabile Rasterkennungen nur nach Wiedererkennung
am wirklichen Schnitt. Ihre Tiefe und ihr Durchgang bleiben gemessen;
`_with_nominal_bore(..., sections=ARC_STEPS)` belegt das bekannte Durchmessermaß
an sämtlichen Wandpunkten. Der Weg umgeht weder die gemeinsame Grenze der
Gesamterkennung noch behauptet er Nominalmaße nach Jitter- oder Voxelrückfall.
Am Netz gibt `_named_bores` nur diese benannten Bohrungen aus; alle übrigen
Merkmale erkennt die Auswertung aus dem Merker nach und ordnet sie denen des
Eingangs zu — eine ausgegebene Neuerkennung stünde dort als mitgebracht neben
den alten Namen (`face_2` neben `face_top`). Am exakten Körper bleibt die
Ausgabe seine vollständige Lesung.

### Wandungen

*HEAD-Fassung.*

`hollow.py` (Aushöhlen — mit den Entlüftungen, die es druckbar machen; die
Öffnung liegt oben oder an der gewählten Seite: `open_towards` ist eine
Achsrichtung, `_mouth` zieht den äußersten Querschnitt des Hohlraums in dieser
Richtung durch, und die Operation leitet sie aus der Normalen der Fläche in
`open_at` ab, RM-087. Die Entlüftungen sitzen, wo der Hohlraum ist:
`_vent_spots` nimmt die Stellen aus dem Raster, an denen der ganze
Bohrerquerschnitt unter Hohlraum liegt, bohrt bis über den höchsten Boden
darunter und zählt eine Entlüftung erst, wenn sie Material abgetragen hat —
weniger Platz als verlangt sagt `hollow.fewer_vents`. **Seit P6.3 dazu gewählte
Öffnungsflächen und die Wand außen** (`openings`, `outward`): am Netz das
Raster wie bisher — innen erodiert, außen mit derselben Kugel gewachsen
(`_outer_field`) —, danach je ebener Fläche ein Öffnungswerkzeug im
aufgerichteten Rahmen der Fläche (`_opening_tool`): innen der Umriss der
Fläche geschnitten mit dem Hohlraum eine Wand und eine Zelle unter ihr,
außen der Umriss plus ein Band über den nach außen gehenden Randkanten, damit
der Rand bündig bleibt wie am exakten Kern. Eine Fläche ohne Hohlraum darunter
bleibt zu (`hollow.opening_misses`); bleiben trotz Öffnung oder Entlüftung
Teile des Innenraums geschlossen, sagt es `hollow.closed_cavities`. Der
bisherige Innenweg ohne gewählte Flächen rechnet unverändert — goldene
Volumina in `tests/test_hollow_faces.py`) ·
`lid.py` (ein Deckel für eine Öffnung — auch vor einer Seitenöffnung:
`opening_frame` nimmt jede achsparallele **Außen**fläche, `create_lid` dreht den
Körper mit `upright_normal` nach oben, baut wie immer und dreht Deckel und
Merkmale zurück; die Hohlraumdecke liegt innen und wird abgewiesen)

*Früher im Kopf der Karte, HEAD-Fassung.*

`lid.screw_lid` benennt Hals- und Deckelgewinde aus demselben rechtsgängigen
`thread_body`-Erzeuger mit `handedness="right"`. Das Innenwerkzeug ändert den
Materialbereich, nicht den Drehsinn. Lageänderungen benutzen weiterhin den
gemeinsamen Merkmaltransformationsweg, die Paarprüfung liegt in `scene.fits`.
**Am exakten Gehäuse bleiben beide Deckel exakt** (P2.8, die Bearbeitung
fragt den Körper): `exact_opening` schneidet die Öffnung aus den Flächen
(`brep.section.horizontal_regions`), `exact_build` baut Platte und Kragen,
`exact_screw_neck` und `exact_screw_cap` nähen Hals und Kappe aus dem exakten
Bausteingewinde (`build.threaded`), beide Wendeln mit derselben Phase am Rand.
Der Kragen folgt in beiden Kernen der engsten Öffnung über seine Tiefe
(`collar_footprints`, `exact_footprints`: Hohlraum am Rand minus Material am
Kragenboden), und ragt er trotzdem in die Wand, sagt die Operation die freie
Tiefe (`collar_hits_wall`) statt einen Deckel auszugeben, der nicht passt.
Passungsweiten und Hals messen in beiden Kernen die schmale Seite in jeder
Drehung: am Netz aus dem Polygon (`_narrowest`), exakt aus den Randpunkten
der Flächen (`_exact_width`, `_short_side` ist die gemeinsame Rechnung); an
einem runden Rand gilt dort das exakte Hüllrechteck. `_short_side` misst die
Projektionen auf die Kanten der konvexen Hülle und wählt das Rechteck nach
kleinster Fläche, nicht nach kleinster Weite. Es benötigt keine
GEOS-Rekonstruktion der Rechteckecken; deren Division durch null auf
macOS/arm64 darf eine gültige Öffnung nicht unbrauchbar machen. Kantenrichtungen
kommen aus den ursprünglichen Randpunkten, die Projektionen aus dem lokalen
Maßrahmen, damit nahe Randpunkte beim Verschieben nicht zu Nullkanten werden.

### Druckvorbereitung

*HEAD-Fassung.*

`prepare.py` und `prepare_ops.py` (Bohrungen, Teilen, Abschneiden — das halbe
Teilen mit einer bleibenden Seite, `cut_away` über `section.cut` —, Anordnen,
Kollisionen, §18.6) · `mouth_cap.py` (der Deckel einer gekrümmten Mündung,
RM-248: `mouth_surface` tastet die Fläche um einen Rand als Höhenfeld über
seiner Ausgleichsebene ab — an den Facetten, auf einem Raster, bis
`MOUTH_REACH` des Radius —, passt ein Polynom dritten Grades in
Grundrechenarten ein, wirft Proben einer anderen Fläche hinaus und sagt
`None`, wo keine glatte Fläche steht; `cap_grid` baut daraus den Deckel des
Netzstopfens, `support_points` die Stützpunkte der exakten Füllung) ·
`autosplit.py` (schneiden, bis es auf die Platte passt; überzeugt keine
achsparallele Ebene, fragt ein Fächer aus zwölf gekippten Richtungen — nur Nähte mit weniger
Konturen, als achsparallel möglich, eine schiefe Naht geht als `split_line` in den Verlauf; je
Naht werden beide Stiftseiten fertig gebaut und am Stützvolumen verglichen, `pins_on_b`; nach einer
billigen Naht-Vorauswahl entscheidet das interne Stützvolumen der fertig
verstifteten Hälften, §22.3; `search_plane` sagt neben der Ebene, wie viele
Ebenen an einer gesperrten Sichtfläche gescheitert sind — daran unterscheidet
`split_to_fit` „keine Ebene" von „keine Ebene neben der Sperre",
`split.blocked_by_protection`; braucht ein Stück mehr als einen Schnitt, plant
`_plan_step` die Folge: `_alternatives` nennt verschiedene Abtastlagen, die
Spiegelebene, die gleichmäßige Teilung und die Nebenachsen, `_rollout` teilt je
Lage den Rest billig zu Ende, `_PlanCost` ordnet nach Stücken, dann
Klebestellen, begrenzt über `PLAN_BUDGET` Probeschnitte; `_gaps` findet Lagen
zwischen losen Teilen, `Candidate.gap`, ein Schritt ohne Stifte;
`_child_reserves` gibt die Stiftzugabe nur der Hälfte mit Stiften; `_room`
kennt die Sperrzonen des Betts; `_mirrored_step` schneidet die Stücke
beiderseits einer Spiegelebene gespiegelt; `fewest_parts` ist die untere
Schranke hinter `split.fewest_parts`) ·
`symmetry.py` (`mirror_plane` misst Spiegelsymmetrie quer zu einer Richtung:
Mitte der Ausdehnung, Flächenschwerpunkt, dann gespiegelte Ecken und
Dreiecksmitten gegen die Oberfläche über `max_distance_to_surface`, Grenze
`units.match_tolerance`) ·
`pins.py` (Passstifte; Auto Split wählt die Form aus Fügefläche und
Materialtiefe und hält den Kleberhinweis als Operationsparameter fest) ·
`orient.py` (Kandidatenlagen aus Hülle und größten Flächen; `extreme_points`
hält je Netz die äußersten Ecken, `turned_extents` dreht nur sie, und
`_Placed` kennt die Hüllbox einer Kandidatenlage, bevor ein Dreieck bewegt
ist — die Suche über zweihundert Lagen kopiert das Netz nur dort, wo eine
Sperrfläche die Projektion verlangt, und gibt `build_area.placement_offset`
die gedrehten äußersten Ecken als Umriss mit. `evaluate_directions` misst je
Lage Standfläche, Überhangfläche, Höhe und den **geschätzten Stützraum**
`Orientation.support` — Überhangfläche in Projektion mal Höhe über dem Bett;
die Heuristik ordnet weiter nach `score`, die Suche schneidet zusätzlich die
Lagen mit der kleinsten Schätzung, siehe `slice/CLAUDE.md`. Die Projektionen
rechnen je Lage mit einem wiederverwendeten Zwischenfeld, in derselben
Reihenfolge wie die tatsächliche Bewegung; die Speichergrenze der Stapel
verändert keine Kennzahl, auch nicht deren letzte Stelle.)

*Zwischenfassung, im selben Absatz ergänzt (Paketübernahme):*

`pins.py`: „Auto Split wählt die Form aus Fügefläche und Materialtiefe und
hält den Kleberhinweis und die erste Stiftnummer (`first_pin`) als
Operationsparameter fest“. `orient.py`: „Die Stapel laufen auf bis zu
`PROJECTION_WORKERS` Arbeitern; Folge und Bits bleiben die eines Fadens.“

*HEAD-Fassung.*

**Ein Langloch ist eine Bohrung mit zwei Bogenmittelpunkten.** Der Umriss
entsteht einmal (`prepare.slot_profile`) und wird von beiden Kernen aufgezogen
— vom Netz-Kern über `sketch_solid.extrude_profile`, vom exakten über
`brep.profiles.extrude`, wo die Enden echte Zylinderflächen bleiben.
Der Umriss normalisiert seinen Winkel auf eine halbe Umdrehung: geometrisch
gleiche Langlöcher erhalten dadurch auch dieselbe Facettierung und Schnittfolge.
`slot_travel` rechnet die Gesamtlänge des Dialogs in die Mittellinie um und
lehnt dabei die Aufweitung ab; `slot_ends` nennt die beiden Endpunkte, an
denen jede Prüfung fragen muss, die für eine runde Bohrung an der Mitte fragt.
`prepare.edge_findings` stellt diese Frage beim Setzen, Ziehen und
Verbreitern für beide Kerne und meldet eine offene Flanke höchstens einmal.
Der Weg dorthin hat zwei Eingänge: `drill_hole` setzt eines (`slotted`,
`slot_length`, `slot_angle`), `slot_hole` zieht eine **erkannte** Bohrung
nachträglich auseinander (`prepare.slot_bore`, exakt `brep.edit.slot_bore`).
Die Regel dazu steht in `.claude/rules/operationen.md`.

Auch beim nachträglichen Ziehen bleibt die Kombination mit einer Senkung
ausgeschlossen. `slot_hole` prüft vorher die topologische Hohlraumkette;
ein verbundener oder mehrdeutiger weiterer Abschnitt hält die Handlung an.
Eine gesonderte runde Aufweitung lässt sich nicht durch bloßes Ändern ihres
Durchmessers zu einer passenden Langlochsenkung machen.

**Und die vier Merkmalshandlungen bleiben am exakten Körper exakt** (P2.4,
20.09.2026): `move_feature`, `duplicate_feature`, `rotate_feature` und
`remove_feature` gehen an einer Bohrung oder einem Langloch ohne Kette den
exakten Zweig (`EXACT_CAVITY_KINDS`, `_exact_move_cavity` und Geschwister)
— schließen über `brep.edit.fill_bore`, schneiden über `cut_bore` oder
`slot_bore`, erkennen mit `features_of` und führen die Kennung belegt fort
(`_exact_features_after`: `_bore_match_id` an der gesetzten Stelle, dann
`match`, `FeatureContinuation` für das bewusst gesetzte Merkmal). Bis dahin
liefen sie über das Netz, und der Körper kam als Netz zurück. **Eine Kette
aus Bohrung und Senkung geht denselben Weg** (`_exact_move_chain` und
Geschwister): Ihr Einlauf kommt aus `bore_entrance`, Stopfen und Werkzeug
sind Rotationskörper derselben Profile wie bei `resize_hole`
(`_entrance_tools`, `_exact_chain_solid`), begrenzt an den wirklichen
Randebenen — verschoben beim Versetzen (`_plane_moved`), gedreht und an den
Mündungen um den Überstand der Neigung nach außen gerückt beim Kippen
(`_plane_turned`, `_reach_past_a_tilted_face`, `_cone_past_a_tilted_face`;
der Boden eines Sacklochs bleibt). Gewählt werden darf jeder Abschnitt;
gedreht wird um dessen Mitte, und `_exact_features_after` führt alle
Abschnitte belegt fort. **„Nur das gewählte Merkmal“ einer Kette**
(`_exact_remove_section`) hält die Reihenfolge des Netzwegs: Liegt etwas
hinter dem Abschnitt, geht erst der ganze Hohlraum zu, und
`_exact_chain_cut_kept` schneidet die übrigen Abschnitte frisch — die
hinteren bis zur Mündung durch, die vorderen ab ihrer eigenen Randebene;
der innerste wird aus seinen Flächen gefüllt, und die Senkung darüber
bleibt als Kegelstumpf mit ebenem Boden stehen. **Was allein steht, geht
aus seinen Flächen** (`EXACT_FACE_KINDS`, `_exact_move_by_faces` und
Geschwister): Der Körper eines Zapfens, einer Kuppe oder eines Kegelstumpfs
— und ebenso einer Senkung oder Pfanne ohne Bohrung darunter — kommt aus
`brep.edit.solid_from_faces` — die nativen Flächen an ihren ebenen Randringen
geschlossen, das exakte Gegenstück zu `_body_from_faces` —; an der alten
Stelle steht das Gegenteil dessen, was das Merkmal ist, an der neuen das
Merkmal selbst, und `is_a_cavity` sagt, welches von beiden Vereinigen und
welches Abtragen ist. Gekippt werden davon Zapfen und Kegel, die Kugel hat
keine Lage. Der Zapfen (`_exact_rotate_pin`) kommt aus seinen Kennzahlen, und
der gekippte Zylinder reicht unter die Mitte so weit, wie
`_reach_past_a_tilted_face` verlangt, statt neben der Grundfläche zu
schweben; die Erkennung nennt danach die Mitte des sichtbaren Mantels, und
genau dort wird er wiedergesucht. Der Kegel (`_exact_rotate_cone`) dreht um
die Mitte seines weiten Endes, und dort liegt die Grundfläche: Er wird über
sie hinaus mit derselben Flanke so weit weitergeführt, wie
`_cone_past_a_tilted_face` verlangt — ins Material beim Stumpf, ins Freie bei
der Senkung, sonst bliebe ihr eine Decke; Höhe und schmalen Radius nennt
`edit.cone_extent`, und die Erkennung beschreibt den gekippten Kegel am Ende
dieser Weiterführung. **Senken und Verschließen** gehen denselben Weg
(`_exact_countersink`, `_exact_plug`): Mündung, Materialseite und die
Mitte eines Stopfens aus Zahlen kommen aus `prepare.sink_placement` und
`prepare.plug_placement` — am Netz-Zwilling gemessen, für beide Kerne
dieselbe Antwort —, der Kegel trägt seinen Durchmesser exakt an der Mündung
und geht um `FEATURE_OVERLAP` mit derselben Flanke darüber hinaus, der
Stopfen am Merkmal ist `_exact_cavity_filled`, der aus Zahlen wird an
`edit.convex_hull` beschnitten wie am Netz an `shell`. **Und der Einschluss**
ist ein Hohlraum ohne Rand: Sein Körper sind seine Schalen
(`edit.void_body` — die Innenschale ohne die Inseln darin), gefüllt beim
Entfernen, gefüllt und um die Insel herum neu geschnitten beim Versetzen.
Seit dem 23.09.2026 gilt das auch für *Merkmal ändern* an Zapfen, Kegel und
Kugel (`_exact_resize_by_faces`; vorher `result_kind="mesh"`).
Damit bleibt am exakten Körper keine Merkmalshandlung mehr, die vernetzt;
`evaluate.exact_became_mesh` ist der Befund für die Operationen, die es
noch tun (Netzwerkzeuge wie Glätten und Dezimieren, siehe die
Paritätstabelle).

*`_plane_moved` heißt heute `_plane_placed`.*

*HEAD-Fassung.*

**Das Merkmalsmuster** (`pattern_feature`, P6.7) wiederholt Merkmale linear,
kreisförmig oder gespiegelt in **einem** Schritt und bleibt ein Körper —
anders als `scene.ops.pattern`, das ganze Körper kopiert. Jede Instanz ist
die Quelle, bewegt: Das Werkzeug entsteht einmal an der Stelle der Quelle
(`_pattern_probe` — dieselben Körper wie beim Verdoppeln: `_placing_tool`,
die Kette über `_chain_copy_tool`, der Ring aus Kennzahlen) und wird je Platz
mit der Matrix des Musters versetzt, gedreht oder gespiegelt; die Merkmale der
Kopie führt `perceive.matching.transformed_features` nach, derselbe Weg wie
bei einer Spiegelung des ganzen Körpers (P0.0). Vor dem Schneiden prüft
`_checked_places` jeden Platz: Überschneidet sein Werkzeug die Quelle oder
einen angenommenen Platz, oder teilt es kein Volumen mit dem Körper, entsteht
er nicht (`pattern_feature.overlap`, `pattern_feature.no_target`, je Platz
benannt). Am Netz schneiden alle Werkzeuge in einer Booleschen je Richtung;
am exakten Körper je Art das exakte Werkzeug der Verdoppelung
(`_exact_cavity_tool`, `_exact_chain_tool_placed` mit `_plane_placed`,
`edit.transformed` des Flächenkörpers, `_exact_torus_tool`) und das Ende von
`_exact_copy_result`. Die Quelle bleibt maßgebend, weil der Schritt sie beim
Namen nennt und bei jeder Auswertung neu liest. Matrizen und Punkte rechnen
elementweise (`transform.moved_points`, `math.fsum`), nicht über BLAS
(RM-187).

**`slot_hole` nimmt seit dem 22.09.2026 auch eine Breite entgegen**
(`diameter`, leer heißt „so breit wie gemessen"; `compensate` wie bei
`resize_hole`): Ein Zug an den Knöpfen und ein neuer Durchmesser in den
Feldern sind damit **ein** Schritt (Entscheidung Robert). Eine andere Breite
schließt die alte Öffnung wie ein Versetzen und schneidet ohne Zugabe — sonst
stünde ein schmaleres Langloch in der weiteren Bohrung. Zwei Schritte gingen
nicht: Das Langloch heißt nach dem ersten Zug neu (`SLOT_FEATURE_RENAMED`),
und der zweite Schritt kennte seinen Namen erst nach der Auswertung.
Auch eine kürzere Länge schließt zuerst den vorhandenen Umriss und schneidet
ihn neu, an beiden Kernen über dieselben Wege wie die Breitenänderung.
Die Untergrenze bleibt `prepare.shortest_slot` für die gewünschte Breite —
außer genau der Breite selbst (`prepare.is_round_length`): Dann schließt
`slot_hole` die Öffnung und schneidet eine runde Bohrung, am Netz mit dem
48-Eck der Bohrwerkzeuge (`prepare.slot_bore` mit Länge = Durchmesser), exakt
über `edit.cut_bore`; die Suche danach ist `_recognised_round`, die Befunde
`slot_hole.round_again` und `slot_hole.already_round`.
**`slot_hole` und `resize_hole` nehmen dabei eine Stelle entgegen** (`x/y/z`,
**leer** heißt „lass es, wo es ist" — `_named_place` beantwortet das für beide,
und die Felder sind `optional`, weil die Null an einer Koordinate die Mitte des
Teils ist). Leer gilt dabei **je Achse**: Wer nur `x` nennt, versetzt nur in x,
und y und z behalten ihren gemessenen Wert. Wer versetzt, schließt zuerst die
alte Stelle — am Netz über `_closed_at`, am exakten Körper über
`brep.edit.fill_bore` — und schneidet an der neuen. **Wer dreht, ebenso**
(`_slot_turned`, seit dem 15.09.2026): Ein Langloch in neuer Richtung war bis
dahin ein zweites quer über dem ersten, mit Warnung — jetzt ist es ein
gedrehtes, und `slot_hole.turned` sagt den Winkel. **Geschnitten und nicht
geändert**: `resize_bore` verglich dort die zwei Durchmesser, fand sie gleich
und gab den Körper unverändert zurück; gemessen am 10.09.2026 blieb das Loch
bei (−20 | −10) und der Befund sagte „Die Bohrung hat bereits diesen
Durchmesser". Zwei Dinge hängen daran und sind beide gemessen: Die Tiefe wird
**vor** dem Verschließen abgelesen (`feature.face_indices` zeigen danach auf
fremde Dreiecke), und die Zuordnung sucht das Merkmal an seiner **neuen** Mitte
— mit der alten meldete der Netz-Weg es als verloren und der exakte warf einen
Programmfehler.

### Kanten und Flächen

*Früher unter „Kanten“, HEAD-Fassung.*

`edge_ops.py` — *Verrunden*, *Fase anbringen* und *Wulst anlegen* im Register, **kernübergreifend**
(und alle drei lesen `ctx.bound_edges` — die von der Auswertung vor dem Cache
gebundene Kantenauswahl geht als `selected_edges` an den Kern, der Wulst mit
`edges_on_mesh=True`, weil er am Netz vereinigt; ohne Bindung gilt der
Schlüsselweg):
Der Rumpf fragt `SceneObject.kind` und wählt danach den Rechenweg — `edit.fillet`
am exakten Körper, `edges.round_edges` am Netz. Sie standen bis zum 10.09.2026
in `brep/ops.py` mit `requires_kind="brep"`; wer ein STL einlas, fand sie
ausgegraut (Entscheidung Robert: „alles soll immer bearbeitbar sein"). Kein
Zwillingspaar (`MENU_TWINS`) — dort wählt der **Kunde**, hier der Körper, und
für ein Netz gibt es den exakten Weg gar nicht (§30).

`edges.py` — die Kanten eines Netzes als **Züge**, mit denselben Schlüsseln,
die der exakte Kern vergibt. `edges_of` merkt sich die Züge im Cache des
Netzes (wie `MeshData.component_count`; der Cache verfällt mit der
Geometrie): Die Auswertung bindet ein Kantenfeld vor dem Cache am Eingang,
und die Operation verkettete dieselben Züge gleich darauf ein zweites Mal —
am Lochblech 20 mal 20 ein warmer Kantenschritt von 434 statt 91 ms. **Und die eine Stelle, an der beide Kerne ihre
Kanten für die Auswertung hergeben** (P1.4c.4b): `edges_in_kernel` liefert
die Liste, die die Operation gleich sieht — Topologie am exakten Körper,
Züge am Netz, mit `on_mesh` immer das Netz —, `indices_in_kernel` die
Indizes gewählter Kanten im Raum dieses Kerns (`brep.edit.native_edge_indices`
beziehungsweise die Position in `edges_of`), `points_in_kernel` den Zug
fürs Bild. `described_by_key` legt jede Kante unter ihren Schlüssel und den
alten Lageschlüssel; mehr als ein Eintrag ist eine Kollision, die
`scene.edge_binding` vor dem Cache fragt. `edge_fingerprint`/`same_edge`
sind der ungerundete Beleg dahinter; `checked_indices` und
`EDGE_SELECTION_REJECTED` die eine Indexprüfung mit dem einen Satz für Netz
und exakten Kern. `round_edges`, `bevel_edges` und `bead_edges` nehmen mit
`selected_edges` die gebundene Auswahl an — vor Schlüsseln und Gruppe, ohne
Rückfall (`selected_or_wanted`). Eine Bauteilkante besteht in einem feinen Netz
aus vielen Dreieckskanten; wer sie einzeln ausgäbe, zeigte vierzig Kanten, wo
der Kunde eine sieht. `edge_key` steht hier und wird von `brep.edit`
mitbenutzt: Dieselbe Kante bekommt aus beiden Kernen denselben Schlüssel,
sonst müsste alles darüber — Anklicken, Beschriftung, der Parameter
`edge_keys` — die zwei Rechenwege auseinanderhalten. **Die Auswahl selbst
steht hier ebenfalls**: `choose` und `wanted` beantworten „alle senkrechten"
für beide Kerne, `brep.edit` ruft sie. `MeshEdge.convex` sagt zusätzlich, ob
Material weggeht oder dazukommt; am exakten Körper weiß das die Topologie
selbst — und daran hängt beim Verrunden, ob abgezogen oder vereinigt wird.

*Früher unter „Kanten“.*

Geschlossene Kantenzüge tragen im Schlüssel zusätzlich ihre Ausdehnung vom
Linienschwerpunkt, am Kreis also den Radius. Mitte und Richtung allein
unterscheiden die konzentrischen Ränder eines Rohrs nicht. Alte Schlüssel
bleiben als Alias lesbar, wenn genau eine Kante passt. Mehrere Treffer
halten zur Neuauswahl an; keine Reihenfolge entscheidet über die Geometrie.
Eine explizite Auswahl muss vollständig auflösbar sein. Fehlt nur eine der
genannten Kanten, hält der ganze Bearbeitungsschritt an; die noch vorhandenen
Kanten werden nicht als stillschweigende Teilauswahl behandelt.

`faces.py` — die **Flächen** eines Netzes bearbeiten, Gegenstück zu `edges.py`:
*Fläche versetzen* und die *Formschräge*. Über der gewählten Fläche entsteht ein
Prisma ihres eigenen Umrisses — Boden und Deckel sind ihre Dreiecke, der Mantel
steht auf den Kanten, die nur zu einem von ihnen gehören. Ein Polygon wird dabei
nie gebildet; das trifft auch einen Umriss mit Loch. `_prism_from` nimmt einen
**Versatz je Knoten**: fest ergibt das gerade Prisma des Versetzens, mit der
Höhe wachsend den Keil der Formschräge.

*Früher unter „Kanten“, HEAD-Fassung.*

**Die Formschräge an gewählten Flächen** (P6.4, `draft_walls`): Richtung und
neutrale Ebene sind wählbar, ohne Angabe gilt das alte Anstellen aller
Wände in Entformungsrichtung mit neutraler Ebene am Anfang des Körpers. Jede
Ecke einer angestellten Fläche wandert in den Schnitt ihrer Ebenen
(`_moved_corners`: neue der angestellten, alte der übrigen, Ebenen an der Ecke
über `units.SAME_PLANE_AT_A_CORNER`; Widerspruch über `MAX_FACET_SAG` oder
Rutschen über `units.GRAZING_SLIDE` ist eine Absage), zwischen alter und neuer
Fläche entsteht je Wand ein Werkzeug (`_prism_between`, gemeinsame
Diagonale für Nachbarwerkzeuge), jenseits der neutralen Ebene abgezogen,
davor vereinigt; eine Wand, die sie kreuzt, wird dort geteilt.
`_tangent_walls` nimmt tangential anschließende Streifen mit (gerundete
senkrechte Ecken), `_checked_tools` prüft je Bauteil, dass kein Werkzeug in
fremdes Material läuft (`DRAFT_CUTS_THROUGH`; ein ganz aufgezehrtes loses
Teil bleibt erlaubt). So bleibt an Innenecken keine Säule und am Sechskant
keine Rippe — der frühere Keil über jeder Wand ließ beides stehen.

`face_ops.py` — *Fläche versetzen* und *Formschräge anstellen* im Register,
kernübergreifend wie `edge_ops.py`. Die Formschräge trägt `faces`
(Merkmalsliste, leer = alle Wände), `direction` (sechs Achsen), `neutral`
und `neutral_height`; `applies_to=("face",)` mit `also_on_body`, damit sie an
Fläche und Körper angeboten wird. **Und `push_face` hat dabei seinen
Parameter gewechselt**: Es nahm eine Richtung und bewegte jede Fläche, die
dorthin zeigte — an einer Treppe alle Stufen zugleich (24000,0 statt 21000,0).
Gemeint ist die gewählte Fläche, und die benennt jetzt ein Merkmalsverweis; die
Richtungsfelder tragen nur noch gespeicherte Schritte (§16).

*Früher unter „Kanten“.*

**Mit gewählter Fläche sagt `push_face`, wo die Flächen danach liegen**
(`faces.pushed_features`): die gewählte um den Weg entlang ihrer Normalen,
jede ebene Nachbarwand um den Streifen aus gemeinsamer Kantenlänge und Weg in
ihrer Ebene gewachsen. Am Netz reisen diese Erwartungen als Merkmale mit, am
exakten Körper belegt `prepare_ops._exact_features_after` die Übergänge, und
`brep.profiles.push_faces` legt die Seitenwände mit `edit.unified` wieder zu
je einer Fläche zusammen. Ohne das verloren die Seiten ihre Namen oder
bekamen still fremde.

*Früher unter „Kanten“, HEAD-Fassung.*

**Verrunden mit Verlauf** (P6.1): `RadiusLaw` trägt Stellen (Anteil der Länge
vom Anfang) und Radien, dazwischen monoton kubisch (Fritsch-Carlson wie
scipys PCHIP, nur Grundrechenarten); `starts_at_first` legt den Anfang einer
offenen Kante (links, vorn, unten — die Richtungsregel des Kantenschlüssels),
`loop_start` den eines Rings (Punkt kleinster Lage in `LOOP_START`, Richtung
nach `LOOP_WAY`; Verfeinerung nur zwischen ähnlich langen Sehnen), und
`LawOnChain`/`law_on_points` übersetzen Bogenlänge in Stelle und Radius — für
das Werkzeug wie für die Bandprüfung. Am Netz baut `_varying_tool` je
Kettenstück einen Loft aus Querschnitten (`_wedge_section`, derselbe
Querschnitt wie `_wedge`), gleich viele Sehnen je Stück, dichter wo der
Verlauf gekrümmt ist (`LENGTHWISE_SAG_SHARE`), Überstand als Kopie der
Endquerschnitte. `check_varying_radius` sagt ab, wo es keine Form gibt (Ring
mit verschiedenem Anfangs- und Endradius, verschiedene Radien an einer
gemeinsamen Ecke, gemischte Ecke); `contact_band_limit(law=)` misst jeden
Strahl am Radius seiner Stelle. `samples_along` liefert dem exakten Kern je
Konturkante seine Tabelle.

**Fasen mit zwei Abständen oder Abstand und Winkel** (P6.2): `ChamferShape`
trägt die zweite Rücknahme oder den Winkel, `reference_first` bestimmt die
Bezugsfläche (am weitesten nach oben, dann hinten, dann rechts; `flip_sides`
tauscht), `chamfer_reaches` rechnet beide Rücknahmen — dieselben Zeilen für
`_wedge`, `_chamfer_contacts`, die Bandprüfung und `brep.edit.chamfer`
(`_faces_at_edge`, `Add(d1, d2, Kante, Fläche)`). An einer gemischten Ecke
(außen und innen) sagen sie ab. Wo drei ungleiche Fasen sich treffen, schließt
das Netz die Ecke eben, OpenCASCADE gewölbt — der Vorbehalt steht im Register.
Der exakte Kern fragt die Flächen an einem Punkt **auf** der Kante
(`brep.edit._point_on_edge`, Mitte des Kurvenparameters), nicht am
Linienschwerpunkt — der liegt bei einem Kreis auf der Achse.

**Welche Fläche welches Maß trägt, sagt der Kern auch der Anzeige**:
`edges.EdgeSides` (Punkt auf der Kante, je Fläche Normale und Richtung in die
Fläche) kommt aus `edges.mesh_edge_sides` (Stück auf halber Länge, seine
Normalen, `_along_face`) oder `brep.edit.edge_sides` (Normalen aus
`_faces_at_edge`, Richtung per `BRepClass_FaceClassifier`);
`edge_ops.edge_sides` wählt den Kern, `edge_ops.chamfer_marks` rechnet mit
`chamfer_shape`/`chamfer_reaches` und denselben Normalen in derselben Folge
die zwei `ChamferMark` (Bezugsfläche zuerst, `None` bei gleicher Breite oder
ungültigen Werten, Ausdrücke über `expressions.resolve_params`). Schnittmaße
und Winkel an schrägen (Sechseck 120°, Dreieck 60°) und gekrümmten
Nachbarflächen (Kegelstumpf, Pappus) prüft `tests/test_mesh_edges.py` gegen
die Konstruktion.

`bead_edges` legt einen **Wulst** auf: ein Rundstab auf der Kante, je Stück ein
Zylinder und je Knick eine Kugel. Die Stücke gehen einzeln in die Kette —
zusammengelegt überlappen sie sich, und ein Körper mit doppelt belegtem Raum
hat kein Volumen (24250 statt 24186). **Die Kehlnaht im Innenwinkel ist nicht
die glatte Hohlkehle**: Die macht `round_edges` an einer konkaven Kante, und
der Unterschied ist der Faktor zwischen 104,45 mm³ und 28,97.

Zylinder **und** Kugel hängen dabei am Radius: `_ring_steps` für den Umlauf,
`_ball` für den Knoten. Die Kugel des Wulstes hält nur die Sehnengrenze, die
des Eckanschlusses zusätzlich die Winkelgrenze — dort ersetzt sie die Flächen
der angrenzenden Zylinder, hier füllt sie nur deren Zwickel, und der
Unterschied ist eine Unterteilung, also viermal so viele Dreiecke.

### Messen, Schneiden, Netz, Text

*Früher unter „Messen und Schneiden“, HEAD-Fassung.*

`measure.py` (§18.3 — Abstand, Wandstärke, Winkel, und der **Fang**: `visible_edges` und `corner_points` sagen, was im Bild überhaupt eine Kante oder eine Ecke ist, `snap` zieht den Klick darauf) · `section.py` (Ebene durch einen Körper, §18.2) ·
`difference.py` (was eine Änderung hinzugefügt und was sie entfernt hat —
**ab wann das eine Änderung ist, sagt der Drucker**:
`Profile.smallest_printable_volume`, dieselbe Grenze und dieselbe Begründung
wie bei `boolean.without_effect`. Die Szene bringt das Profil mit; ohne eines
bleibt es beim Vernetzungsrauschen, denn wer keinen Drucker kennt, soll keinen
erfinden — Regel 7, RM-097; eine Seite, die der Kern nicht schneidet, folgt aus
der Volumenbilanz, auch an Körpern mit eingeschlossenen Hohlräumen,
`_shells_apart`)

`section.clip_triangles` begrenzt lose Markierungsdreiecke an denselben
Halbräumen wie Körper. Es bleibt eine offene Anzeigefläche ohne zusätzliche
Kappen; die übergebenen Eckpunkte und der ursprüngliche Körper bleiben erhalten.

`section._apply` schneidet in einem Rahmen, in dem die Ebene waagerecht liegt
(`transform.rotation_between`, elementweise bewegt), und `_capped` baut den
Deckel aus den X/Y-Koordinaten dort — `trimesh` legte ihn über eine SVD in die
Ebene. Eine achsparallele Ebene dreht nur Vorzeichen und Achsen und ist Bit
für Bit umkehrbar. Die Wandstärke (`measure.ray_distances`) schießt über
denselben Strahltest wie der Rest (`mesh.ray_hits` mit `edge_margin` und
`minimum_travel`).

*Früher im Kopf der Karte.*

`Difference.result` bewahrt den vollständigen Nachherkörper auch dann, wenn
der zusätzliche Volumenvergleich unvollständig ist. Bei überlappenden
positiven Schalen werden geometrisch identische Komponenten vor dem
Vergleich abgezogen; negative Innenschalen bleiben mit ihrem Körper
verbunden. Reine Kontaktschalen innerhalb des Float64-Rechenfehlers zählen
nicht als entferntes Material. Echte Änderungen hinter aufgesetzter Schrift
bleiben Teil des Vergleichs. `SceneDifference.findings` trägt daneben die
Befunde der vorgeschauten Schritte, nicht die Vorgeschichte des Imports.

*Früher unter „Netz, Farbe, Text“, HEAD-Fassung.*

`mesh_ops.py` (Arbeit am Netz selbst) · `colour_ops.py` · `paint.py` (Flächen
in ein Filament färben) · `texture.py` (von einer Textur zu druckbaren Slots)
· `label_ops.py` (Text und Logos auf einer Fläche; die Schriften dazu liegen
in `data/fonts/`)

**Kanten verfeinern** (`remesh`) teilt einen geschlossenen Körper konform
durch den exakten Kern (`_split_conforming`): `refine_to_length` so oft, bis
keine Kante mehr über der verlangten Länge liegt — ein Durchgang lässt die
Diagonalen im Inneren eines geteilten Dreiecks bis zum Vierfachen stehen,
drei reichten an elf Kundenmodellen. Slots und Farben kommen über `face_id`
vom Herkunftsdreieck (`_inherited`), nicht über `attributes.transfer`, und
auf allen drei Wegen wird die Herkunft am Ergebnis vermerkt
(`perceive.features.note_refinement`): Die Auswertung trägt die Merkmale
darüber weiter, statt sie neu zu erkennen (`.claude/rules/operationen.md`). Nur
ein offenes Netz und ein dichtes, das der Kern ablehnt, gehen die zwei Wege
über `trimesh` (`subdivide_to_size` halbiert seit trimesh 5.1 selbst
konform, braucht aber zwei- bis viermal so viele Dreiecke; gleichmäßig nur,
wenn es trotzdem aufreißt). Vorab schätzt `estimated_triangles` aus Fläche
**und** geteilten Kanten — die Fläche allein lag an fein facettierten Netzen
um das Sechzehnfache zu tief —, der offene Weg fragt die Obergrenze
`_on_demand_count`, danach zählt jeder Durchgang gegen
`MAX_REMESH_TRIANGLES`. Die vorgeschlagene Kantenlänge sucht
`_reachable_edge` an derselben Zählung, mit `ESTIMATE_RESERVE` über einer
Schätzung; ein offenes Netz bekommt *Netz reparieren* dazu. Ein `MemoryError` wird in
allen drei Teilungen (`remesh`, `uniform`, `subdivided`) zum Satz mit Weg
(`_out_of_memory`). `refined` bleibt der eine Durchgang fürs Biegen.

*Früher unter „Netz, Farbe, Text“.*

Die Netzoperationen fragen `ctx.cancelled` nach ihrer Rechnung, je Durchgang
der gleichmäßigen Teilung und je Portion der Abweichungsmessung
(`deviation(..., cancelled=)`, `max_distance_to_surface(..., cancelled=)`);
die Rechnung in `manifold3d` und `trimesh` selbst läuft ohne Rückruf bis zum
Ende. *Offene Fläche schließen* (`_thickened`) trägt die Filamente mit: Außen-
und Innenhaut dieselben Slots, eine Randwand den ihres Dreiecks. Das
Anzeigeraster (`_clustered_for_display`) kennzeichnet ein Dreieck bis 2²¹
Ecken als eine Zahl, darüber zeilenweise (`_first_of_each_triangle`).

Matplotlib gehört direkt zum Extra `geom`: `label_ops` liest daraus die
Schriftkonturen und DejaVu-Dateien, `brep/lettering.py` übernimmt dieselben
Glyphenpfade als Kurven. `constraints.txt` bindet die Version; installiert
wird der Bedarf durch `pyproject.toml`, unabhängig von anderen Kernen.

*Früher unter „Netz, Farbe, Text“, HEAD-Fassung.*

**Eine Beschriftung sieht überall gleich aus, oder sie ist keine.** Ein Projekt
wandert zwischen Rechnern, und eine Systemschrift, die es hier gibt und dort
nicht, macht daraus zwei verschiedene Teile. Angeboten wird deshalb nur, was
mitreist: DejaVu bringt matplotlib mit, Liberation, Comfortaa und Dancing
Script liegen in `data/fonts/` (SIL OFL, Lizenztexte unter
`knowledge/data/third_party_licenses/`, Zuordnung in `BUNDLED_FONT_LICENCES`).
`FONT_STYLES` holt fett und kursiv über `weight` und `style` aus denselben
Dateien, die ohnehin im Paket liegen.

**Nicht jede Familie hat alle vier.** Comfortaa und Dancing Script sind
*variable* Schriften — eine Datei mit einer Gewichtsachse, die matplotlib nicht
instanziieren kann. „Fett" liefert dort dieselben Umrisse, und der Riegel für
die Familie greift nicht, weil die ja da ist. `FONT_STYLES_AVAILABLE` sagt
deshalb je Familie, was es wirklich gibt, und `FONTS_WITH_ALL_STYLES` daneben
ist dieselbe Auskunft für den Dialog: Das Feld *Schnitt* hängt über
`depends_on` an der Schrift und graut aus, wo es nichts zu wählen gibt — statt
anzubieten und danach abzulehnen.

**Und was zu dünn zum Drucken ist, misst `stroke_width` am gesetzten Text.**
Doppelte Fläche durch Umfang über die Umrisse, die die Operation ohnehin baut;
`too_thin_to_print` rechnet daraus die Höhe, ab der es trägt. **Keine Tabelle je
Familie** — eine solche hing an einem Beispielwort, verschwieg den Schnitt (fett
ist rund anderthalbmal so breit) und wäre acht Zahlen gewesen, die niemand
nachmisst. Verglichen wird gegen `narrowest_bead`, die schmalste Bahn dieses
Druckers: `NARROW_LINE_SHARE` aus `slice/advise.py`, dieselbe Zahl wie beim
Wandvorschlag und nicht der Düsendurchmesser. Die Operation macht daraus einen
Befund mit der Zahl, keine Sperre: Wer nur ansehen oder exportieren will, darf
klein bleiben.

**Und matplotlib fällt still zurück.** Wer eine Schrift verlangt, die fehlt,
bekommt keine Ausnahme, sondern DejaVu Sans und eine Zeile auf der
Fehlerausgabe. `font_properties` prüft deshalb nach, welche **Familie** die
gefundene Datei führt (`get_font(...).family_name`), und sagt es (Regel 21) —
die zweite Hürde hinter der Spec, die den Ordner mitnimmt. Am Dateinamen
gemessen wäre der Riegel halb: „DejaVu" steht auch in `DejaVuSans.ttf`, wenn
„DejaVu Serif" gemeint war.

## Stolperfallen

### Merkmalshandlungen

*Früher im Kopf der Karte.*

Ein neu benannter Nutboden erhält seinen Ebenenträger durch Prüfung aller
Originalecken. Zusammengefasste Sacklochböden behalten die Teilträger ihrer
tatsächlichen Ausgangsflächen. Beim Platzieren eines Merkmals auf einer neuen
Oberfläche werden alte Dreiecks- und Trägerbezüge gemeinsam entfernt; erst die
Auswertung bestätigt die neue Originalhaut.

*Früher im Kopf der Karte, HEAD-Fassung.*

Wiederhergestellte Bohrungen und Langlöcher verwenden das gemessene
Konturmaß ohne zusätzliche Vieleckkorrektur. `prepare_ops._placing_tool`
trennt das maßhaltige Setzen vom vergrößerten Werkzeug zum Schließen oder
Abtragen; die axiale Überlappung an Mündungen bleibt erhalten. Tatsächlich
umschreibende Hüllwerkzeuge behalten ihre geometrisch nötige Sehnenzugabe.

Was ein Merkmalsschritt am Netz nur weiterreicht, geht ohne Dreiecksnummern
hinaus (`_without_old_triangles`, an jeder Netzausgabe von Versetzen,
Verdoppeln, Drehen, Ändern, Entfernen, Verschließen, Abschneiden und dem
Trichter `_torus_result`): Die Vereinigung nummeriert neu, und die alten
Nummern bezeichneten fremde Dreiecke; die Auswertung gibt die Oberfläche an
der neuen Erkennung zurück. Die Regel steht in `.claude/rules/operationen.md`.

Ein Ring oder Gewinde ohne gemessene Achse hat keine Lage: `_torus_axis`
sagt mit `FEATURE_WITHOUT_AXIS` ab (bis zum 21.09.2026 stand still die
Z-Achse da). Und die vier exakten Verdoppelungen — Hohlraum, Kette,
Flächenkörper, Ring — enden in `_exact_copy_result`, dem Gegenstück zu
`_exact_cavity_result`; der verlorene Durchgang wird dort für jede Kopie
gefragt, nicht nur für die einzelne Bohrung.

**Wulst und Kehle** (Torusmerkmale) tragen seit P2.6 dieselben fünf
Handlungen wie Bohrung und Zapfen — `prepare_ops._move_torus` und
Geschwister, je Kern. Das Werkzeug ist der volle Ring aus den Kennzahlen
(`_torus_ring_mesh`, exakt `brep.edit.torus`): vereinigt der Wulst,
abgezogen die Kehle. Nur das Schließen an der alten Stelle braucht mehr:
exakt `brep.edit.defeatured`, am Netz der Körper aus den eigenen Dreiecken
der Ringfläche ohne den Schaftkern zwischen den Randringen
(`_torus_tool_mesh`, `_torus_shaft_core`) — ein parametrischer Ring deckt
sich nie mit der vorhandenen Ringfläche und hinterließ Splitter. Ein Ring,
der der ganze Körper ist, sagt es (`TORUS_IS_THE_BODY`); ein Torusstück,
hinter dem der Schaft nicht weitergeht, ist nicht abzutrennen
(`TORUS_NOT_SEPARABLE`).

**Ein Gewinde** trägt Ändern und Entfernen (`_resize_thread`, `_remove_thread`):
außen nimmt das Entfernen den Gang zwischen Fuß- und Kammradius weg und
lässt den Kern stehen, das Ändern nimmt die bewendelte Strecke als
Hüllzylinder weg und vereinigt das Bausteingewinde (`build.threaded`) auf
derselben Achse; innen füllt das Entfernen die Strecke über dem Kammradius
(„Gewinde verschließen“), das Ändern füllt und schneidet mit dem neuen
Innenwerkzeug. Die Enden entscheidet `_thread_span` an der Nachbarschaft:
Material dahinter, Luft dahinter, und nur ein eingesunkenes aufgesetztes
Bausteingewinde endet um `BOOLEAN_OVERLAP` vor seinem Sockel — ein Stopfen
greift hinter Material um dieselbe Spanne hinein. Ein Merkmal nennt innen
die **Gewindebezeichnung** (den Grund-Ø der Gänge), das Werkzeug rechnet in
der Bohrung darunter (`_tool_diameter`). Ein **erkanntes** Gewinde am Netz
sagt Grenzen und Strecke über seine eigenen Ecken (`_thread_corners`,
`_thread_bounds`) — der Fit über Dreiecksmitten liegt radial innerhalb der
Kammecken und axial neben der Stange —, und sein Kern bleibt um den Überlapp
unter dem gemessenen Fuß. Ist das Gewinde der ganze Körper, nimmt die Hülle
alles, und das neue Gewinde ist danach allein der Körper. Linksgängig
(belegt, `types.thread_is_left_handed`), mehrgängig und ohne Strecke sind
Absagen mit Vorschlag. Versetzt, gedreht oder verdoppelt wird nicht das
Gewinde, sondern der Körper oder die Bohrung.

**Filament nehmen Wulst, Kehle und Gewinde seit P2.6 wie eine Fläche an**
(`paint_slot`, `clear_filament`): Der Ring und ein erkanntes Gewinde nennen
ihre Dreiecke selbst; ein **erzeugtes** Gewinde nennt keine, denn der
Baustein sagt nur Achse, Mitte, Durchmesser, Steigung und Länge (§24.1).
`paint.feature_triangles` beantwortet das für beide Operationen: Die Flächen
des erzeugten Gewindes sind alle Dreiecke in seiner Hülle — radial bis zum
Kamm, axial über die bewendelte Strecke — ohne die Deckel quer zur Achse,
also ohne die Spitze und ohne den Sockel, auf dem es sitzt. Am exakten
Körper sind das ganze native Flächen (die Flanken liegen ganz in der Hülle,
die Deckel ganz außerhalb), und `validate_full_faces` prüft es beim Färben.

*Früher im Kopf der Karte.*

`move_feature` versetzt eine eindeutig topologisch verbundene Senkbohrung
als ganzen Hohlraum: alle Abschnitte aus `perceive.relations.cavity_chain_at`
begrenzen gemeinsam den Werkzeugkörper, alle Kennungen und Mittelpunkte
reisen mit. Zwei äußere Randringe werden geschlossen; eine unvollständige
oder mehrdeutige Fläche bleibt abgelehnt. Eine gerundete Mündungskante reist
mit (`mouth_blends=True` an `_cavity_plug`, `_paired_cavity_body`,
`_past_curved_mouths`, `_bore_end_rims`; RM-259) — beim Versetzen,
Verdoppeln, im Muster und beim Entfernen der ganzen Kette, nicht beim Ändern
und Kippen, die aus Profilen neu schneiden.

`remove_feature` fragt bei einer solchen Kette über `ctx.ask`, ob alle
Abschnitte mitgehen, und hält die Antwort im Parameter `sections`
(`OpResult.answered`) fest — derselbe Weg, den `load` mit der Einheit geht.

*Früher im Kopf der Karte, HEAD-Fassung.*

**Beide Antworten gehen denselben Weg: erst geht der ganze Hohlraum zu, dann
wird frisch geschnitten, was bleiben soll.** Bei „ganzer Hohlraum" entfällt der
zweite Schritt, bei „nur das gewählte" schneidet `_cavity_tool` die übrigen
Abschnitte wieder aus dem vollen Material — für die Abschnitte weiter innen
zusätzlich durch den gefüllten hindurch, sonst verlören sie ihren Weg nach
außen. Den Füllkörper liefert `_cavity_plug`: aus den Flächen des Hohlraums,
wo sie einen geschlossenen Körper hergeben, sonst als **Stopfen**
(`_chain_plug`) — ein Zylinder über die ganze Kette, wie ihn der Absagetext
seit je empfiehlt. Ein Füllkörper, der die Kegelwand nachbildet, endet auf ihr,
und die Vereinigung lässt dort zwei Flächen nebeneinander stehen.

Ob der zweite Randring eines einzelnen Abschnitts ein Übergang oder sein Boden
ist, beantwortet `_stands_alone` an derselben Kette und nicht die Ringzahl:
Nach dem Verschließen der Bohrung bleiben es zwei Ringe, und die Senkung
gehört sich dann selbst. Der Umfang `entrance_mode="keep"` ändert einen
Abschnitt und meldet die übrigen; `follow` nimmt den belegten Einlauf mit.
Eine unvollständige Änderung einer einzelnen Senkung bleibt ausgeschlossen.
Die geprüfte Eigenständigkeit erreicht Werkzeugbau und Verschluss auch beim
Versetzen, Verdoppeln und der freien Platzierung samt ihrer Vorschau.
Eine alleinstehende Senkung übernimmt ihren vorhandenen Boden in den
Flächenkörper. `_cavity_floor` belegt ihn wie den Boden einer Bohrung am
vollständigen gemeinsamen Rand; ein neuer Fächer würde einen quantisierten
Boden anders triangulieren und beim Füllen eine innere Schale zurücklassen.
Der vorhandene Erkennungsmerker liefert die Bodenflächen, ohne eine zweite
Herleitung ihrer Zugehörigkeit.

*Früher im Kopf der Karte.*

`resize_hole` erhält mit `keep` beim Verkleinern Lage und Außenmaß der anderen Abschnitte.
Eine entstehende Ringschulter gehört anschließend weiter zur erkannten Kette.
Die Bodenkennung bleibt erhalten, wenn vor und nach dem Schnitt eine vollständige
Scheibe am ganzen Wandrand liegt und dieselbe reale Ebene bestätigt ist. Neue
koplanare B-Rep-Teilflächen dürfen dazu nur vollständig und ohne überlappende
Eigentümer zusammengefasst werden. Der vorhandene Erkennungslauf liefert die
neuen Bodenmaße; allgemeine Zuordnungsgrenzen bleiben unverändert.
Bei belegten Randebenen schließt `_section_closed(extend_inner=False)` zuerst
den gewählten Abschnitt und stellt die übrigen in ihren bisherigen Grenzen
wieder her; danach schneidet `resize_bore` den neuen Durchmesser. Dadurch
entstehen am quantisierten Sacklochboden keine nahezu koplanaren Füllhäute.
Das Entfernen eines Abschnitts behält dagegen `extend_inner=True`, damit
innere Abschnitte ihren Weg durch den gefüllten Abschnitt nach außen behalten.

*Früher im Kopf der Karte, HEAD-Fassung.*

`_bore_end_planes` misst vollständige Randringe am ursprünglichen Netz.
Der Schnitt reicht bis zur äußersten Mündung der zugehörigen Kette, auch bei
einer schrägen Senkung oder einem tangentialen Rundungsübergang. Offene
Mündungen erhalten die vorhandene Werkzeugzugabe; Böden und geschlossene
Stufen behalten ihre Ebene. Die Wiedererkennung vergleicht verschobene
axiale Mittelpunkte am ursprünglichen Wandintervall; sie ändert dafür nur
den Vergleichspunkt, nicht die gemessene Ergebnisgeometrie.
Nachbarbefunde messen den Abstand des tatsächlichen Schnittwerkzeugs zu
den geschlossenen benachbarten Hohlräumen. Hüllquader dienen nur zur Vorauswahl;
eine bestehende dünne Wand wird nur bei weiterer Verschlechterung gemeldet.

*Früher im Kopf der Karte.*

`bore_entrance` prüft für Operation und Handlungsvorgabe denselben gemeinsamen
Einlauf. Eine bereits geprüfte Kettenauskunft wird über `cavity` und
`touches_other` weitergegeben; `()` belegt, dass kein gemeinsamer Einlauf
existiert. Der Schema-Standard bleibt `keep`; eine belegte neue Merkmalsaktion
belegt `follow` vor. Dort erhalten alle radialen Profile denselben Zuwachs,
Senkungswinkel und axiale Stufenlagen bleiben. Die radiale Einführbreite ist
im Normalquerschnitt auf Höhe der Mündungsebene definiert; die Schnittkurve
auf einer schrägen Außenfläche folgt daraus. Echte Ringschultern bleiben
radiale Stufen. Eine schräge gemeinsame Kegel-/Zylinderkante wird dagegen
durch den kreisrunden Hals des neuen Kegels ersetzt, ohne künstliche Schulter.

Beide Kerne schneiden dieselben Profile an denselben Randebenen. Der exakte
Füllkörper bildet das alte Profil nach, damit er keine tieferen Nachbarlöcher
unter der weiten Senkung füllt. Hinterschnitte, Verzweigungen, doppelte Ränder,
versetzte Stufen und ungeklärte Profile nennen die vorhandene `keep`-Wahl.
Eine **Verengung** (`narrowing`, die Haltelippe einer Magnettasche) hat ihr
eigenes Profil und ist immer der letzte Abschnitt ihrer Seite
(`_EntranceSection.narrowing`): Der Schaft endet an ihrem Fuß
(`_narrowing_foot`), ihr Kegel läuft auf die Öffnung und als Zylinder der
Öffnung über die Mündung hinaus (`_narrowing_outline`). Ihr Werkzeug reicht
wie der Kegel einer Senkung in den Abschnitt davor hinein; zwei Werkzeuge,
die sich in der Fußebene nur berühren, ließen am Netz beide Deckel als Haut
quer durch die Tasche stehen. Mitgenommen behält sie Breite, Winkel und
Höhe. *Nur Bohrungsdurchmesser* geht an einer Kette mit Verengung ebenfalls
über die Profile (`_entrance_with_a_narrowing`, `keep`): Ihre Öffnung bleibt,
an einer weiteren Tasche setzt sie am alten Fuß an und wird steiler, an einer
engeren behält sie ihren Winkel und setzt höher an (`_narrowing_radii`); ist
die Tasche nicht weiter als die Öffnung, verschwindet sie, und
`resize.narrowing_swallowed` sagt es (`_narrowing_after_resize`, ohne *Senkung
mitziehen*). Am Netz liegt das Ergebnis danach ohne Narben
(`_without_scars`): Die Erkennung liest eine Verengung nur an einer Wand aus
ganzen Facetten und mit offener Mündung. **Gekippt wird eine Kette mit
Verengung nicht** (`rotate_feature`, derselbe Satz wie im Merkmalfenster:
`perceive.actions.narrowing_reason`): Schräg zur Fläche liest keine Erkennung
die Lippe wieder als Verengung, und jede weitere Handlung rechnete ohne sie;
ohne Lippe kippt die Tasche. Versetzen, Verdoppeln, Muster und Entfernen der
ganzen Kette gehen am exakten Körper weiter über die eigenen Flächen
(`_exact_chain_own_cavity`, `_exact_own_chain_filled`, `_exact_own_cut`).

*Merkmal ändern* an einer **Senkung auf ihrer Bohrung** schneidet sie aus
denselben Profilen neu (`_resize_chain_countersink`, `mouths` in
`_side_tools`): neuer Radius in der Mündung, derselbe Winkel, die Bohrung
bleibt — am exakten Körper Volumen für Volumen dasselbe wie gleich so tief
gesenkt. Bis zur Durchsicht 0.5.1 streckte der exakte Kern den Kegelstumpf um
die Mündung, und enger blieb eine Haut quer über der Bohrung; das Netz sagte
ab. Wo der Kegel nicht die äußere Senkung einer Seite ist, sagen Operation und
Merkmalfenster denselben Satz (`countersink_resize_refusal`).
Ein einzelner Zylinder behandelt beide Umfänge gleich. Eine gleichzeitige
Lageänderung mit Einlauf läuft als **ein** Schritt (`_moved_after_resizing`,
22.09.2026). Und die Nachbarwand wird auch beim **Versetzen** gefragt, nicht nur
beim Vergrößern: `drill` gibt sein Werkzeug heraus, und der Satz nennt dann
die Stelle als Ausweg (`_neighbour_message`, `moved=True`).

*HEAD-Fassung, in der Zwischenfassung aus diesem Absatz gestrichen. Die übrigen Sätze der HEAD-Fassung über die Verengung sind durch die Fassung darüber ersetzt:*

Eine gleichzeitige
Lageänderung mit Einlauf läuft als **ein** Schritt (`_moved_after_resizing`,
22.09.2026): erst der Neuschnitt an der alten Stelle, dann die ganze Kette
über die Maschinerie von `move_feature` an die neue — bewegt um die
Differenz zur alten Mitte (der Neuschnitt lässt sie an einer schrägen
Mündung axial wandern), nur wenn die ganze Kette wiedererkannt ist (sonst
sagt der Schritt ab, mit dem Rückweg), mit den Befunden des neuen Orts
statt des alten (`PLACE_BOUND_FINDINGS`) und mit den Übergängen beider
Läufe als einem (`_continued_through`). Der Einlauf-Neuschnitt selbst
belegt am exakten Kern seine Übergänge — ohne sie hielt der nächste Schritt,
der die Bohrung braucht, die Kette an — und trägt die übrige Topologie des
neu gebauten Körpers unter ihren alten Namen weiter (`_exact_rest_carried`;
bis dahin waren die sechs Flächen der Platte nach dem Neuschnitt aus dem
Baum verschwunden). Ob ein Durchmesser die Bohrung so lässt, wie sie ist,
sagt `bore_is_unchanged` — die Operation und das Fenster fragen dieselbe
Antwort.

*Früher unter „Druckvorbereitung“, HEAD-Fassung.*

`bore_depth_is_unchanged` beantwortet für Tiefenoperation und Formwechsel
dieselbe Frage: Ändert der eingetragene Wert die Bohrung tatsächlich? Leer,
„ganz durch“ und die halbe Anzeigestelle folgen damit einer gemeinsamen Regel.

**Die Nummer eines zerlegten Teils hängt an der Geometrie, nicht am Rauschen.**
`_loose_parts` ordnet nach Volumen — aber nach dem **gerundeten Verhältnis zum
größten Teil** (`_SAME_SIZE`), und bei Gleichstand entscheidet `_where_it_sits`,
die Mitte des Hüllquaders. Der Grund steht in beiden Docstrings: Zwei gleich
große Teile unterschieden sich in den letzten Stellen mit der Tessellierung,
und ihre Nummern tauschten bei manchen Größen. Die Kennung eines Objekts ist
der Anker für jeden späteren Schritt; ein Tausch nimmt ihm sein Ziel.

*Früher im Kopf der Karte.*

Nach geometrisch bestätigter Zuordnung erhält `_with_nominal_bore` bekannte
Operationsmaße, damit der Fit an Dreiecksmitten Durchmesser und Senkungswinkel
nicht bei jeder Folgeänderung verkleinert. Alle Wandpunkte müssen das aus
der Werkzeugunterteilung abgeleitete Sehnenband einhalten; `voxel` und
`jittered` behaupten keine so bestätigten Nominalmaße. Bei Kegeln bleibt der
äußere Durchmesser das wirkliche maximale Maß der beschnittenen Mündung.

Die Nachprüfung einer Bohrungsänderung verwendet oberhalb der gemeinsamen
Grenze `perceive.local.FEATURE_LIMIT_TRIANGLES` die örtliche Suche
`detect_known`. Beim gemeinsamen Einlauf umfasst sie alle neu konstruierten
Abschnitte; der erforderliche Suchradius entsteht aus dem vollständig
gekappten Werkzeug. Das ist ein geometrisch belegter Umfang, keine größere
Erkennungstoleranz. Der Sollbeschreiber einer schrägen Senkung liegt wie der
Erkennungsbefund am äußersten Kegel-/Ebenenschnitt. Die Nominalprüfung kann
mit `sections` die tatsächliche Kreisunterteilung des Erzeugers übernehmen.

*Früher im Kopf der Karte, HEAD-Fassung — die Regeln dazu stehen heute in `operationen.md`.*

**Und eine Kette geht als Ganzes** (RM-172, 15.09.2026): `move_feature`,
`_rotate_cavity_chain` und `_duplicate_cavity_chain` nehmen Bohrung und
Senkung zusammen. Fürs Kippen baut `_chain_tool` das Werkzeug aus den
Kennzahlen der Abschnitte — mit Überstand an beiden Enden: die Bohrung über
ihre Mündung hinaus, die äußere Senkung als größerer Kegel
(`_measured_section` mit `outward`). Wie weit, rechnen
`_reach_past_a_tilted_face` und `_cone_past_a_tilted_face` aus der Neigung.
Fürs Versetzen bleibt es beim exakten Flächenkörper, den `_past_the_mouths`
an seinen Mündungen um die Zugabe aus §39 verlängert — das Werkzeug aus
Kennzahlen kostete dort Volumen, der bündige Körper ließ eine Haut von 5 µm
stehen. Gedreht wird um die Mitte des gewählten Abschnitts. Nur `slot_hole`
sagt an einer Kette weiter ab. Weitet sich die Bohrung an beiden Enden, hat
die Kette zwei Seiten (`relations.cavity_sides`, RM-245): `_chain_tool` baut
je Seite ihre Erweiterungen mit Überstand und die Bohrung dazwischen einmal,
der exakte Einlauf liest die zweite Seite als `_BoreEntrance.back`.

*Früher im Kopf der Karte, HEAD-Fassung.*

Merkmalswerkzeuge verwenden die gemessene Tiefe unabhängig vom Durchmesser.
`_tool_for` erhält bei Bohrungen den tatsächlichen Sehnenzug ihrer Wandflächen.
Füllkörper umschließen die äußersten Wandknoten auch bei fremder Tessellation;
an offenen Langlöchern begrenzt die Mündungsebene den Füllkörper (§21.1).
Nach einem Versatz entscheidet die Zielgeometrie über den Durchgang, auch bei
rein seitlicher Bewegung. Verlorener Durchgang erzeugt einen Befund und
korrigiert das Merkmal. Entfernte Kennungen bleiben in
`SceneObject.reserved_feature_ids` für spätere Kopien gesperrt (§21.2).

**Die Kantenwarnung misst am Hüllquader nur vor.** `over_the_edge_along`
meldet eine offene Flanke, wenn die Mündungsscheibe über die Hülle ragt — das
ist billig und für einen `Solid` der einzige Weg. Auf einer gekrümmten Fläche
trifft es aber immer zu: Der Scheitel liegt auf der Hülle, und die getroffene
Facette steht schräg. Wo ein Netz vorliegt, entscheidet deshalb
`_flank_is_open` nach: ein Kranz von Punkten auf dem Bohrungsumfang, an
mehreren Tiefen in beide Achsrichtungen; liegt er an einer davon vollständig
im Material, reißt dort nichts auf. Innen und außen trennt `mesh.on_surface`
über die Normale des nächsten Dreiecks — nicht `trimesh.contains` (führt durch
`rtree`) und nicht `ray_hit_distances` (Kantentreffer zählen mehrfach, die
Parität trägt nicht). Dieselbe Frage stellen seit dem 15.09.2026 alle Wege,
die eine Bohrung neu setzen — Versetzen, Verdoppeln, Drehen, Ändern, frei
platziert oder als Kette (`prepare_ops._edge_findings`): je Abschnitt des
gesetzten Hohlraums am gefüllten Körper vor dem Schnitt, an der Mitte, an den
Enden eines Langlochs und an den Austritten der Achse aus dem Hüllquader
(`_axis_exits`); dort fragt `prepare.mouth_over_the_edge` nur den halben
Radius hinter der Mündung, denn eine gekippte Bohrung reißt kurz hinter ihrem
Austritt auf und steckt weiter innen wieder im Material. Gemeldet wird
höchstens einmal — die Fahne eines Minigolf-Satzes gewann beim Versetzen um
2 mm 8,5 Prozent Volumen, und der Bericht schwieg.

**Was aus dem Review vom 15.09.2026 sonst noch hier steht:** `_rooted` und
`_tool_for` reichen Qualität, Startwert und Abbruchmarke an ihre Boolesche
durch (`_placing_tool`, `_closed_at`); `_tool_for` fragt `hole_is_clear` vor
dem Flächenkörper und gibt dem Flächenkörper einer Bohrung den Kragen aus
`_past_the_mouths` mit — den nimmt seither auch die Kettenkopie beim
Verdoppeln statt des Werkzeugs aus Kennzahlen. `hole_is_clear` lässt dem
Sacklochboden `FEATURE_OVERLAP` Spiel, nicht zehn Nanometer, und
`_without_cavities` nennt seine neun Achsproben (`_CAVITY_AXIS_SAMPLES`).
`MeshData.component_count` merkt sich seine Zahl im Cache des Netzes.

*Früher unter „Grenzen“.*

- **Freie Platzierung verwendet den gemeinsamen `frame_of()`-Rahmen.**
  Bei `drill_hole`, `move_feature` und `duplicate_feature` bewahrt der
  Nullvektor die frühere Achsen- beziehungsweise Verschiebungssemantik.
  Die freie Bohrungsnormale zeigt vom Material weg; ihr Werkzeug verläuft
  ab der Mündung nach lokal -Z. `drill_tool()` erzeugt auch Aufweitung und
  Übergang als einen geschlossenen Rotationskörper. Die tatsächliche Op
  und ihre Vorschau verwenden das Material des Zielkörpers.
  Das Werkzeug reicht exakt von null bis zur negativen Eingabetiefe; ein
  Blindboden erhält keine Überlappungszugabe, auch nicht beim Mittenanker.
  Durchgangsaufrufer wählen ausdrücklich größere Höhen. An den bekannten
  lokalen Werkzeugenden bereinigt `drill()` ausschließlich Float64-Rauschen
  der Koordinatentransformation, je Vertex begrenzt durch die wirklichen
  Matrixterme. Echte Flächenabstände oberhalb dieser Rechengrenze bleiben
  erhalten; Materialtoleranz und globale Schweißtoleranz ändern sich nicht.

- **Merkmalswerkzeuge umfassen die belegte vollständige Form.**
  `feature_placement_geometry()` bestimmt den wirklichen Materialanschluss
  und schließt zusammenhängende Bohrketten gemeinsam; eine Kette mit
  gekrümmter Mündung trägt das Werkzeug ihrer Operation (`flush=False`), und
  die alte Stelle füllt `_cavity_plug`. `x/y/z` bleiben die
  Zielmitte des gewählten Merkmals; ein lokaler Versatz verbindet sie mit der
  angeklickten Mündung oder Basis. Weitere Kettenglieder behalten beim
  Versetzen ihre Kennungen und bekommen beim Kopieren jeweils neue.

- **Textvorschauen verwenden echte Konturen.** `local_text_body()` wird von
  der Operation und der Platzierung verwendet; lokale Drehung und
  Überlappung entstehen nur einmal. Der Anzeigeaktor verändert keine
  gespeicherte Geometrie. **Jeder Parameter der Form reist mit** — auch der
  Schnitt: Er fehlte in `scene/placement.py`, und die Vorschau zeigte den
  normalen, während die Operation den fetten baute.

### Reparatur

*Früher im Kopf der Karte.*

`repair()` übernimmt die Dreiecksbereinigung nur, wenn das Netz danach nicht
schlechter ist — gewogen über die Summe offener und verzweigter Kanten
(`_tears_it_further`). Andernfalls bleiben das Netz und seine
Materialzuweisungen erhalten, und das Protokoll nennt den ausgelassenen
Schritt. Die einzelnen Reparaturhilfen bleiben für ausdrücklich gesteuerte
Reparaturketten verfügbar.

*Früher im Kopf der Karte, HEAD-Fassung.*

**Verschweißt wird überall mit derselben Funktion** (`repair.weld`, RM-239):
Import (`ingest.loader.normalise`, Schritt 2), Reparatur und Stufe 2 der
Booleschen Kette fragen sie, die beiden letzten über `merge_vertices`.
**Unter `EPS_GEOM` ist ein Ort ein Ort, darüber entscheidet die Datei:** Eine
Dreieckssuppe wird zuerst gelesen — was auf `EPS_GEOM` zusammenfällt, ist eine
Ecke (`_read_soup`; gruppiert auf der Schweißtoleranz, fein geteilt nur, wo
eine Gruppe weiter streut) —, danach, und am Netz mit geteilten Ecken sofort,
kommt nur zusammen, was an einer offenen oder verzweigten Kante liegt oder als
Kante unter `EPS_GEOM` zusammenfällt (`_joined_at_the_rims`). Eine Ecke in
heiler Fläche bleibt, auch wenn eine andere näher liegt als die
Schweißtoleranz: am Ring aus `Siebhalter+X1C.3mf` zwölf Fasen von 0,016 µm
zwischen zwei Flächen, die zusammengezogen aus 16 erkannten Flächen 28
machten. Jede Punktgruppe wird nach Flächenblatt getrennt (`_sheets`):
Zusammen bleibt, was in der Datei eine Ecke war, was nach dem Verschweißen
eine Kante mit genau zwei Flächen teilt, eine gleich umlaufende Doppelung,
und an einer Kante mit mehr Flächen die zwei, die denselben Körper begrenzen
— um die Kante nach einem Pseudowinkel aus Grundrechenarten geordnet
(`_around_the_edge`, `_pseudo_angle`; die Ordnung entscheidet über die
Topologie, RM-187). Zwei Dreiecke am selben Winkel haben Luft zwischen sich:
Zwei Körper, die sich berühren, bleiben zwei, auch als Dreieckssuppe; zwei,
die sich an einem Rand nur an einer Ecke treffen, behalten zwei Ecken
(`whole_fans`; beim Lesen einer Suppe ist die Ecke ein Punkt). Lässt sich eine
Kante nicht ordnen, bleiben die Gruppen an ihren Enden ganz. Übernommen wird
nur, was die Summe offener und verzweigter Kanten an den Dreiecken, die nicht
flach gedrückt sind, nicht erhöht (`_damage`) — ein flach gedrücktes fällt im
Schritt danach. Der Schlüssel ist trimeshs (Lage, Texturkoordinaten,
Eckennormalen): Wo keine zwei Blätter aufeinanderliegen, kommt Ecke für Ecke
dasselbe heraus wie aus `Trimesh.merge_vertices`, und die Kantenzählung des
Ergebnisses liegt im Cache (`mesh.remember_edge_table`). Eine Kopie derselben
Schale mit eigenen Ecken hat keinen offenen Rand; sie sucht der Import eigens
(`loader._without_doubled_shell`).

*Früher im Kopf der Karte.*

Normalenkorrekturen vergleichen die Reihenfolge der Dreiecksecken; eine
geänderte Windung muss das Volumen nicht ändern. Beim Vernähen und Schließen
reisen Flächenfarben und Materialslots von den jeweiligen Ausgangsflächen
mit. Neue Lochflächen verfolgen dafür sämtliche Randkanten und die beim
Füllen entstehenden Diagonalen.

Der ausdrückliche Reparaturschritt prüft Durchdringungen auch bei ausgeschalteter
Auflösung und bietet die passende Einstellung an. Die automatische Lochfüllung
beim Import aktiviert diese zusätzliche Diagnose nicht: Dort gehört kein
Korrekturvorschlag für Reparatureinstellungen an den Ladeschritt.
Durchdringungen werden vor und nach ihrer Auflösung räumlich geprüft. Nur eine
vollständig geprüfte direkte Float64-Vereinigung gilt als behoben und trägt
den Solver `direct`. Geschlossene positive Schalen sind einzelne Operanden;
unklar zugeordnete Innenschalen bleiben unverändert. Ein unvollständiger oder
erfolgloser Versuch liefert einen Restbefund mit Handlung. Bei geänderter
Geometrie deklariert die Reparatur keine alten Merkmale erneut; die gemeinsame
Erkennung führt die Merkmale am Ergebnis nach.

*Früher im Kopf der Karte, HEAD-Fassung.*

**Die Schnittsuche läuft einmal je Netz und weiß, wie weit sie kam**
(`repair.crossings_of`, `intersections.Crossings`). Ihr Budget zählt in
**genauen Paarprüfungen**: Ein Paar, dessen Hüllen sich wirklich überlappen,
kostet die ganze Trennprüfung einen Bruchteil (`SEPARATION_COST`) und, was
sie nicht trennt, die genaue Prüfung dazu; ein Paar, das schon der
Nummernvergleich an die genaue Prüfung gibt, kostet diese allein. Die
Sweep-Kandidaten zählen nicht. Das Budget wächst mit dem Netz
(`INTERSECTION_PAIRS_PER_TRIANGLE`, mindestens `MAX_INTERSECTION_PAIRS`). **Am offenen oder gegeneinander
gewickelten Netz und über `perceive.maps.MAP_LIMIT_TRIANGLES` gilt nur der
Sockel** (`_intersection_findings`): Dort löst die Reparatur nichts auf, und
am Drachen kostete das mitwachsende Budget 70 s für „nichts zu tun". Jede
gefundene Überschneidung bekommt eine Zeile — auch an einem verkehrten oder
flachen Körper —, und nach einem Auflösen mit unvollständiger Suche steht der
Hinweis daneben. Reicht es nicht, meldet `Crossings`
`complete=False` und die Dreiecke, die bis dahin geprüft sind (`checked`);
die Netzfehlerkarte zeigt die übrigen als ungeprüft statt als sauber. Das
Ergebnis liegt im Cache des Netzes: Reparatur, Befund und Karte fragen
dieselbe Rechnung, der Fortschritt läuft über `ctx.progress`.
`_crossing_shape` sagt, **wer** sich kreuzt — verschiedene Schalen, eine
deckungsgleiche Überlagerung oder eine Schale mit sich selbst. Nur die ersten
beiden löst die Vereinigung auf; eine Schale, die sich selbst kreuzt
(`repair.self_crossing`, die gefaltete Röhre), wird benannt und nicht
vereinigt — `[netz, netz]` löste sie am Korpus nie und kostete am
Piratenschiff 49 s. Nachgeprüft wird nach dem Vereinigen nur, was in der Nähe
der alten Schnitte liegt.

**Ein Ring wird in der Reihenfolge gefüllt, die seine Form am wenigsten
verbiegt** (`_fill_loops`, eine Warteschlange aus `_FillJob`):

1. **Zwei koaxiale Ringe mit gegeneinander gerichteten Nachbarn sind eine
   fehlende Wand** und bekommen ein Band (`_band_between`, `BAND_PARALLEL`):
   Bohrungswand und Senkungskegel kommen zurück statt zweier Deckel.
   Kreuzt das Band vorhandene Flächen (`_band_crosses`) oder verbinden die
   Wände die Ringe schon — Rohr ohne Deckel, Kugel ohne Pole —, wird jeder
   Ring für sich gefüllt. **Und ein Ring, der ein Stück einer solchen Wand
   umläuft, ist dieselbe fehlende Wand** (`_wall_between_rims`, RM-240): Liegen
   seine Ecken in zwei parallelen Ebenen, je ein zusammenhängendes Stück, und
   liegt keine Nachbarfläche eines Stücks zum anderen hin, wird zwischen den
   Stücken ein Mantel gezogen (`_zipped`) — die halbe und die Dreiviertelwand
   einer Bohrung und eines Senkungskegels kommen mit ihren Teilungen zurück,
   eine gerade Wand eben.

2. **Ringe in einer Ebene, einer im anderen, sind eine Fläche mit Löchern**
   (`_bridged_holes`): eine Triangulierung mit Brückenkanten statt fünf
   übereinanderliegender Scheiben — die fehlende Oberseite einer Lochplatte
   lässt die vier Durchgänge offen.

3. **Ein Ring bis `SMOOTH_FILL_CORNERS` Ecken geht über alle
   Triangulierungen** (`_smoothest_fill`, nach Liepa): zuerst der kleinste
   größte Knick gegen die Nachbarn, dann die kleinste Fläche. So kommen die
   Dreiecke einer Verrundung, eine Würfelkante und ein Viertel einer
   Bohrungswand als dieselben zurück.

4. **Größere Ringe gehen über Ohren** (`_loop_triangles`: verkettete Liste,
   Menge der Reflexecken, Abbruch je `EARS_PER_CANCEL_CHECK`), und keine
   Diagonale auf eine Kante, die schon zwei Flächen trägt. Der Fächer über der
   Ringmitte bleibt der letzte Rückfall; gefaltete Füllungen (`_folds`) gelten
   nie.

*Früher im Kopf der Karte.*

Eine Füllung erbt Slot und Farbe zuerst vom eigenen Rand, dann von der
geerbten Diagonale. Eine Fläche ohne Dicke bleibt offen (`_flat_fills`,
`repair.no_thickness` mit *Dicke geben*, das nur die offenen Teile aufträgt:
`mesh_ops._thickened_open_parts`); lose offene Splitter unter
`SMALL_COMPONENT_SHARE` der größten Komponente fallen nach dem Füllen weg
(`remove_open_splinters`, `repair.splinters_removed`), und was danach noch
als flacher Ring offen steht, zählt `_flat_still_open` am Endstand — die
Bilanz des Füllers gilt dem Netz vor dem Entfernen. Beide Paarungen der
Ringe (Band, Fläche mit Löchern) sieben vorab über ganze Felder; je Paar in
Python kostete eine Kugel mit 1 500 Dreieckslöchern 78 s. Der Füller fragt
den Abbruch je Ring, und der Import reicht ihn durch (`normalise(cancelled=)`).

*Früher im Kopf der Karte, HEAD-Fassung.*

**Außen ist je Verschachtelungsbaum** (`turn_shells_outward` über
`_Shells.containers`, die eine umhüllende Schale beim ersten Strahl einmal
ausschneidet): Eine freie Schale muss positiv sein; ist sie negativ, dreht sie
sich samt allem, was belegt in ihr liegt, und ein richtiger Hohlkörper
daneben bleibt, wie er ist. Ein einzelner Körper braucht dafür nur sein
Vorzeichen. **Umschlossen heißt ganz darin** (`_Shells.inside`): Die Schalen
schneiden sich nicht (Zertifikat `perceive.features._shells_do_not_cross`,
sonst ein Paar quer durch die Wand über `_first_crossing_between`), und eine
Ecke liegt innen — dieselbe Frage wie die Hohlraumerkennung. Ein Teil quer
durch die Wand eines anderen ist frei: Verkehrt wird es gedreht, und
gemeldet wird es als ineinandersteckend, nicht als Teil im Teil. Eine
positive Schale **im Material** einer anderen — die Summe der
Vorzeichen aller umschließenden Schalen ist mindestens eins — wird nicht
geraten, sondern gemeldet (`parts_inside_parts`, `repair.part_inside` mit Ort
und *In Einzelteile zerlegen*, aus Import und Reparatur derselbe Befund); eine
Kugel frei im Hohlraum liegt in Luft und ist keiner. Die Wicklung macht `wind_consistently`
einheitlich: über die Kantentabelle und einen Breitenbaum aus
`scipy.sparse.csgraph`, je Teil wird die kleinere Hälfte gedreht (an der
Gähnenden Katze 0,4 statt 13 bis 23 s in trimeshs `fix_winding`). Jedes
Vorzeichen, an dem eine Entscheidung hängt, kommt aus `mesh.signed_volume`
oder der schalennahen Summe in `_shell_volumes`, nie aus dem
ursprungsbezogenen `enclosed_volume`: Ein Würfel von 1 mm bei 10⁸ mm hatte
dort ein Volumen aus Rundung.

### Anordnen und Ausrichten

*Früher unter „Druckvorbereitung“.*

Die geometrische Vorauswahl projiziert dieselben Normalenrichtungen in
begrenzten Gruppen auf Z. Vollständige Netzkopien entstehen erst für die
Platzierungsprüfung; eine begrenzte Bestenliste prüft sie in der vollständigen
Bewertungsreihenfolge, bis genügend passende Lagen vorliegen. Ungenutzte
Vertices zählen wie bei den Netzbounds nicht zur Höhe. Gleiche Flächensummen
behalten die lexikographische Reihenfolge ihrer Normalengruppen.

*Früher unter „Druckvorbereitung“, HEAD-Fassung.*

`core/build_area.py` ist der gemeinsame Druckbereichsvertrag: `printable_area`
liefert eine polygonale Fläche ohne feste Sperrzonen, `printable_height` die
freigegebene Höhe. Beide lesen `PrinterProfile`; ohne optionale Kontur gilt
das nominelle Rechteck aus `build_volume`. Alle Konturen verwenden XY relativ
zur nominellen Bettmitte, Z beginnt auf dem Bett. Ein `margin` gehört zum
Auftrag und verändert das Maschinenprofil nicht. `fits_on_bed` prüft die
aktuelle Lage; `placement_offset` sucht eine passende Verschiebung aufs Bett.
Bei Sperrzonen zählt die tatsächliche XY-Projektion statt nur der Hüllbox.

Anordnung, Bauraumprüfung und Orientierung verwenden diesen Vertrag. Die
Orientierung prüft auch eine Vierteldrehung in der Platte und erhält die
XY-Mitte, solange sie passt. `SearchResult.transform` trägt die vollständige
Bewegung zum Originalkörper, einschließlich B-Rep; die Grundrichtung allein
beschreibt die Platzierung nicht. Auto Split prüft jedes Endstück samt
Verbinderreserve gegen dieselbe Kontur. `oversize` liefert nur dimensionale
Überstände; `fits` entscheidet zusätzlich über die polygonale Fläche.
Eine Zwischenhälfte ohne passende Lage hat unbekannten Stützbedarf (`inf`),
kann aber weitere Schnitte benötigen. Andere Geometriefehler bleiben Fehler.

*Früher unter „Druckvorbereitung“.*

**Gepackt wird in der Ecke, gelegt wird in der Mitte.** `arrange_on_bed` sucht
jede Lage weiter an der hintersten, dann linkesten freien Stelle (§29) — das
Verfahren bleibt mitsamt seiner Abnahme. Erst danach schiebt `_into_the_middle`
jede Platte als Ganzes in die Mitte der freigegebenen Fläche, wie es jeder
Slicer daneben tut (`best_object_pos` steht dort auf `0.5x0.5`). Verschoben
wird je Achse nur, was hineinpasst, und nur wenn die Zielfläche wirklich frei
ist — die Prüfung gegen Sperrzonen läge sonst hinter der Verschiebung.
Was in einer Achse nur ohne den Rand passt, liegt in dieser Achse auf der
Bettmitte, geprüft gegen das Bett samt Sperrzonen, und `check_build_volume`
nennt es `arrange.narrow_margin` (Hinweis mit dem verbleibenden Abstand)
statt „über den Bauraum hinaus" (RM-229).
`occupied` nennt Körper, die liegen bleiben und ihren Platz belegen; eine
Platte mit solchen wird nicht zentriert.

**`orient_for_print` legt hin, was es umgeworfen hat.** Ein gedrehter Körper
braucht mehr Fläche als ein stehender und lief sonst in seinen Nachbarn
(Befund Robert, 09.09.2026). Der Parameter `arrange` ruft dieselbe Anordnung
mit denselben Werten für Abstand und Platten. **Über die Oberfläche bekommt sie
die ganze Szene** (`whole_scene`, wie *Auf dem Bett anordnen*), es bleibt also
niemand liegen und die Platte wird zentriert. Ein **gespeicherter** Auftrag
trägt dagegen seine damalige Teilmenge; dort gehen die übrigen als `occupied`
mit und die Zentrierung entfällt. Was der Abstand enthalten
muss — Plattenhaftung und Stützrand —, rechnet `export.writer.clearance_margin`,
und vorbelegt wird er in der Oberfläche (`MainWindow._spacing_for`), weil
Druckeinstellungen nicht zur Auswertung gehören.

Der Parameter `arrange` steht dabei auf `True`, auch für **gespeicherte**
Aufträge: Ein alter Stapel ordnet beim Öffnen mit und legt seine Körper
auseinander (Entscheidung Robert, 10.09.2026). Ohne Migration, weil die
Änderung die Lage berichtigt und keine Maße umdeutet — Bauplan §29 führt die
Begründung.

**Und beide Anordnungen trennen nach Filament, wo der Drucker sonst spült**
(`by_material`, Vorgabe An — Entscheidung Robert, 19.09.2026). Ob die Trennung
nötig ist, fragt `_filament_groups` den Drucker: `PrinterProfile.nozzles`
zählt die Düsen, eine Wechselstation nicht; getrennt wird erst, wenn mehr
Filamente auf dem Bett liegen als Düsen. Den Gruppenweg selbst gibt es einmal
(`_arranged_in_filament_groups`), für *Auf dem Bett anordnen* und für das
Hinlegen nach dem Ausrichten — dort mit den liegengebliebenen Körpern als
`occupied`, in der Zählung der jeweiligen Gruppe.

**Und was sie nicht meldet, nimmt sie selbst mit.** Bei einem einzigen Körper
meldet die Operation ihre Matrix, und `scene.evaluate` führt die Merkmale
damit nach; bei mehreren hat jeder seine eigene, eine davon zu melden wäre
eine falsche Angabe über die anderen — dort bewegt die Operation die Merkmale
selbst, je Körper mit seiner Drehung und dem Versatz des Anordnens darüber.
Genau in diesem Fall, nicht immer: Beides zusammen wäre eine Drehung zu viel.

*Früher unter „Druckvorbereitung“, HEAD-Fassung.*

**Und weil sie an ihren Eingängen vorbei liest, sagt sie es dem Schlüssel.**
Der Registereintrag trägt `reads_other_bodies=True`; ohne das behielte ein
Ergebnis seine Gültigkeit, nachdem jemand einen nicht gewählten Körper
verschoben hat — der gedrehte wiche einem Nachbarn aus, der längst woanders
steht. Die Regel dazu steht in `.claude/rules/operationen.md` unter „Und die
vierte hängt an keinem Parameter".

*Früher unter „Druckvorbereitung“.*

**Ein Zug speichert einen Weg, gemeint war ein Platz.** `back_onto_bed` holt
zurück, was eine Bewegung von der Druckfläche oder in ein anderes Teil
geschoben hat. Die drei Operationen, die ein Gizmo-Zug anlegt —
`translate_object`, `rotate_object`,
`scale_object` — rufen es über den Parameter `keep_on_bed`. Erst wird
zurückgeschoben, den kürzesten Weg, den `placement_offset` ohnehin zuerst
prüft; steht dort ein Nachbar, sucht `arrange_on_bed` eine freie Stelle **auf
derselben Platte**. Ist dort nichts frei, bleibt der Körper liegen und
die Bauraum- und Kollisionsprüfung sagen es wie bisher — ein Plattenwechsel
hinter dem Rücken des Kunden wäre ein Teil, das er beim Drucken nicht wiederfindet.

**Die Vorgabe ist aus, und den Haken setzt der Zug** (`MainWindow.
_on_transform_dragged`, vier Stellen). Ein getippter Wert ist eine Ansage und
wird ausgeführt; ein Zug ist ein Zeigen. Der Unterschied ist gemessen: Das
Galerieteil `website/teile/gehaeuse.p3d` schiebt seinen Deckel um 135 mm und
graviert danach bei x = 135 — mit stiller Rückholung fiel „SOLIDON" in sieben
lose Buchstaben —, und ein Kranz, der bewusst über den Bauraum gelegt wird,
soll das melden statt zurückzurücken.

*Früher unter „Druckvorbereitung“, HEAD-Fassung.*

Drei Bedingungen tragen das Verhalten, und jede hat ihren Grund: Geprüft wird
der **Eingang** (wer schon daneben stand, ist geparkt und wird nicht
eingefangen), bewegt wird nur in **XY** (die Höhe hat *Auf das Bett setzen*,
und ein für einen Schnitt angehobener Körper darf nicht heruntergezogen
werden), und die **gemeldete Matrix** trägt Bewegung und Rückholung zusammen
— sonst zeigte die Vorschau dorthin, wohin die Zahlen weisen, und der Körper
läge woanders. Auch diese drei lesen die übrigen Körper, also tragen auch sie
`reads_other_bodies=True`.

### Kanten und Flächen

*Früher unter „Kanten“.*

Das Entfernen und Ändern einer erkannten Netzrundung rekonstruiert die
ursprüngliche Kante nur zwischen genau zwei nachgewiesenen ebenen Flächen.
Die Flächenerkennung grenzt diese von Mantelfacetten ab; eine Tangente einer
gekrümmten Nachbarwand darf keine Ersatzebene für einen Füllkörper werden.

*Früher unter „Kanten“, HEAD-Fassung.*

**Und die Formschräge holt ihre Wände selbst.** Die Merkmalserkennung
beantwortet „was kann der Kunde anklicken" und verwirft kleine Flächen; an
einem Quader von 8 auf 5 auf 0,5 mm sind die beiden schmalen Wände 2,5 mm²
groß und damit kein Merkmal — angestellt wurden zwei der vier senkrechten
Wände.
`_walls_no_feature_claims` ergänzt, was kein Merkmal beansprucht. Drei
Bedingungen stehen davor, und jede hat ihren gemessenen Grund:

- **Eine Richtung muss es geben.** Ein entartetes Dreieck trägt die Normale
  `[0, 0, 0]`, und deren Z-Anteil ist null — ungeprüft gilt es als senkrecht,
  der Keil darüber hat die Dicke null.

- **Die ganze Gruppe muss eben sein, nicht nur ihr erstes Dreieck.**
  `trimesh.facets` gruppiert über einen Krümmungsradius und nicht über einen
  Winkel: Eine Kugel mit 327 680 Dreiecken kommt als **eine** Gruppe zurück.

- **Und gezählt wird die Ergänzung, nicht die Summe** (`MOST_WALLS_TO_GUESS`).
  Ein Teil mit vielen erkannten senkrechten Flächen bekam sonst keine
  einzige — also nichts behoben, wo der Befund entsteht.

Was die Grenze verhindert, ist gemessen und **nicht** ein Abbruch: An
`plate_countersunk.stl` stehen 48 Mantelstreifen zu vier erkannten Wänden,
und jeden anzustellen zerlegt die Bohrung — ihr Rand bei z = 1 mm kommt statt
als **eine** Kontur als 22 zurück, acht davon ohne Ausdehnung, während
Volumen, Dichtheit und Rückfallstufe unauffällig bleiben. Wer die Grenze
anhebt, prüft die Ränder.

Ein nicht geschlossenes Netz wird vorher angehalten (`_must_be_closed`, mit
der Frage, die Stufe 2 der Rückfallkette stellt): Die Keile gehen als
Differenz hinein, und auf der Voxelstufe kam von 4000 mm³ noch 101 zurück.

*Früher unter „Kanten“.*

Am exakten Körper binden `push_face` und das Entfernen einer Rundung die
gewählten Merkmalsdreiecke über `Solid.complete_faces_of_triangles` an ihre
aktuellen vollständigen Originalflächen. Leere, unvollständige oder ungültige
Auswahlen halten an; Mittelpunktnähe ersetzt keinen belegten Träger. Der
Operationsabbruch wird vor und nach der Zuordnung geprüft und an den nativen
Builder weitergegeben. Ohne Merkmalsauswahl bleibt der gespeicherte
Richtungsweg von `push_face` erhalten. Der Radiuswechsel einer Rundung geht
seit P1.4c.4a denselben Weg: `_exact_fillet` bindet die gewählte Rundungsfläche
für Entfernen **und** Ändern über `complete_faces_of_triangles`, und
`brep.edit.reround` belegt die scharfe Ersatzkante aus der Builder-Historie
statt die nächste an der alten Mitte zu nehmen (`brep/CLAUDE.md`).

`edges.radial_rounding` bearbeitet positiv belegte Zylinderwände innerhalb
ihrer eigenen Randkurven. Ob eine Rundung überhaupt eine Kante ersetzt, fragt
`edges._around` bei der Erkennung nach (`perceive.features.planes_beside`),
mit der gemeinsamen Schwelle `units.UPRIGHT_TO_AXIS`; der Absagesatz
`edges.NOT_BETWEEN_TWO_PLANES` steht auch in der grauen Zeile des
Merkmalspanels. Eine gewölbte Wand des Baums, deren Facetten alle innerhalb
`features.NEARLY_FLAT_ANGLE` um ihre Mittelnormale liegen — eine Wand mit
Formschräge, wie eingelesene Halter sie tragen —, zählt dabei als Ebene
(`features.nearly_flat_mask`); dafür reisen die Merkmale des Objekts bis
`sharp_corner`, `unround` und `reround` mit. Ein konvexes Setzwerkzeug aus den Flächen (Kegel, Kuppel)
bekommt in `prepare_ops._placing_tool` einen Sockel in die Grundfläche und
spart die Hohlräume aus, die durch es laufen. Die ausgewählten Knoten skalieren radial samt
Sehnenunterteilungen; angrenzende Flächen müssen in ihren bisherigen Ebenen
bleiben. Ein geschlossener Zwischenkörper zwischen
alter und neuer Haut prüft boolesch auf fremdes Material und Wandverlust.
Sein Volumen muss auch zum Ergebnis mit der ursprünglichen Topologie passen;
Nullhäute einer bloßen Neuvernetzung werden damit kein Bestandteil des Modells.
Werden bisherige Dreiecksdiagonalen eines ebenen Randes durch die Änderung
ungültig, übernimmt stattdessen der geprüfte Schnitt dessen neue Triangulation.

*Früher unter „Kanten“, HEAD-Fassung.*

`rounding_tool` baut den Werkzeugkörper: im Querschnitt der Zwickel zwischen
den zwei Flächen und dem Bogen, stückweise über den Zug gezogen. Wie fein der
Bogen wird, sagt `_arc_steps` — aus `units.MAX_FACET_SAG` und
`MAX_FACET_ANGLE`, denselben zwei Grenzen, mit denen OpenCASCADE tesselliert.
Eine feste Stückzahl wäre bei R = 30 zu grob und bei R = 0,5 Verschwendung.

*Früher unter „Kanten“.*

Vollständig gewählte Eckknoten bekommen eigene Anschlussflächen. Der Knoten
stammt aus `MeshEdge.node_indices`, nicht aus gerundeten Ortskoordinaten.
Zwei zusammentreffende Kanten behalten den unmittelbaren Flankenschnitt.
Bei rein konvexen oder konkaven Knoten begrenzt der ursprüngliche
Normalenkegel den Kugelanschluss; ein Tetraeder aus den Berührpunkten
reicht dafür nicht. Mehr als drei Ebenen werden gemeinsam versetzt:
Gibt es mehrere Offsetzentren, verbindet sie die Minkowski-Summe des
versetzten lokalen Polyeders mit der Kugel. Die facettierte Kugel wird je
Operation einmal erzeugt und hält die Sehnenabweichung im Dreiecksinneren ein.

*Früher unter „Kanten“, HEAD-Fassung.*

**Ob eine Rundung oder Fase auf ihre Flächen passt, fragen beide Kerne vorher
gleich** (`contact_band_limit`): Strahlen in der Ebene jeder Fläche quer zur
Kante, der nächste Treffer ist der Rand der Fläche, die Berührlinie einer
gewählten Nachbarkante zählt mit. Passt es nicht, sagt `too_large_for_the_faces`
das größte Maß; der exakte Kern fragt dasselbe, wenn OpenCASCADE abgelehnt hat
(`edge_ops._why_it_does_not_fit`). Schmaler als `edge_ops.narrowest_face`
(kleinstes Druckerdetail) zählt nicht. Eine **Gruppe** („alle", „oben" …)
überspringt Züge, an denen keine zwei Flächen unter einem Winkel stoßen
(`workable`, Befund `edges.skipped`); eine benannte Kante hält an.

*Früher unter „Kanten“.*

Fasen verbinden die tatsächlichen Schnittpunkte ihrer Flanken auf den
Nachbarflächen. Bei mehr als drei Flächen schließt deren ebene oder
facettierte konvexe Hülle die Ecke. Diese Mesh-Kappe kann von OpenCASCADEs
Splinekappe abweichen; Flankenabstände und Kontaktpunkte bleiben exakt.
Die Eckwerkzeuge werden gemeinsam mit den Kantenwerkzeugen geschnitten.
Ein Knoten, dessen Kontaktpunkte keinen Körper ergeben, bekommt **keine**
Haube: Die Flanken schneiden dort auch ohne sie, und eine fremde Ausnahme aus
der Hüllenrechnung wäre beim Kunden ein Programmfehler (`_corner_hull`).

Der gemischte orthogonale Dreiflächenknoten verwendet einen örtlich
begrenzten Ebenen- oder Torusübergang, auch in der komplementären Innenform.
Seine drei Zylinder teilen die feinere Winkelunterteilung der Torusfläche;
beide Parameterrichtungen teilen sich die zulässige Sehnenabweichung.
Die Auswahl wird zuerst im Weltsystem aufgelöst. Die Rechnung erfolgt im
Rahmen des gemischten Knotens; nur das aus den Float64-Rechenschritten
abgeleitete Rauschen an seinen drei belegten Ebenen wird bereinigt.
Knoten-IDs und Materialslots bleiben beim Hin- und Rückweg erhalten.
Unabhängige Gruppen gewählter Züge rechnen nacheinander in ihren eigenen
Rahmen, auch auf demselben Körper. Gemeinsame ursprüngliche Knoten bestimmen
die Gruppen; ihre Reihenfolge folgt der ursprünglichen Auswahlliste.
Die Ausgangspunkte und Normalen bleiben maßgeblich: Nach einer Gruppe sind
deren Knotennummern keine Vertexindizes des neu vernetzten Zwischenkörpers.
Rechenstufen und Befunde aller Gruppen gehen ins gemeinsame Ergebnis ein.
Die fünf künstlichen Kontaktseiten des Ersatzkörpers überlappen den
Anschluss um `EPS_GEOM`; die echte Oberfläche und die Kurven bleiben stehen.
Die ursprünglichen Kontaktflanken der drei Kantenwerkzeuge verwenden
denselben numerischen Überlapp statt einer Zugabe zum Bauteilmaß.
Vor einem lokalen Materialersatz müssen die tatsächlichen Eingangsflächen
und das Volumen den drei ursprünglichen Ebenen entsprechen. Ein weiteres
Detail im Bereich hält mit einem Vorschlag für ein kleineres Maß an.
Alle Booleschen Vorbereitungen tragen ihre Rechenstufe und Befunde bis zum
Operationsergebnis weiter.

**Den Überstand an den Enden bekommt, was abgezogen wird — nicht, was außen
liegt.** Beim Verrunden fällt beides zusammen (außen abziehen, innen
vereinigen), beim Wegnehmen einer Rundung nicht: Dort wird außen *vereinigt*,
und ein Überstand klebt an, statt zu helfen.
An einem gemischten Eckanschluss enden die Kantenwerkzeuge genau am Knoten;
ein Überstand könnte auf dessen anderer Seite eine innere Fehlstelle schneiden.

*Früher unter „Kanten“, HEAD-Fassung.*

`unround` und `reround` gehen den Weg zurück: `sharp_corner` rechnet aus einer
erkannten Rundung die Kante, die sie ersetzt hat — über den **Schnitt der zwei
Nachbarebenen** und nicht über den Radius, denn der stammt aus einem Sehnenzug
und ist ein wenig zu klein (2,9772 an einer Rundung von 3,0). Der Füllkörper
ist der Zwickel **ohne** Bogen; er deckt die Rundung ab, und seine Flanken
liegen in den Nachbarebenen, wo ohnehin Material ist.
Beim erneuten Verrunden geht das vollständige `MeshData` aus `unround` in
`round_edges` weiter. So können beide Booleschen Schritte die Materialslots
erhaltener Flächen übertragen; ein Neuaufbau allein aus `raw` verlöre sie.

### Slots, Netz, Text, Innenraum

*Früher im Kopf der Karte, HEAD-Fassung.*

Materialslots werden nach einer Booleschen Operation anhand der erhaltenen
Eingangsflächen übertragen; eine gleiche Dreieckszahl beweist keine gleiche
Zuordnung. Rasterbudgets multiplizieren mit unbegrenzten Ganzzahlen.
`assign_slot`, `paint_slot` und `clear_filament` ändern Attribute über
`attributes.with_slots` und erhalten dabei Mesh oder BRep. Bei exakten Körpern
bindet `Solid` die Slots an native Flächen und bildet sie bei jeder neuen
Tessellation auf die neuen Dreiecke ab. `validate_full_faces` weist Teilmengen
einer nativen Fläche vor der Zuweisung zurück, auch wenn ihr bisheriger Slot
bereits dem Ziel entspricht. Eine Teilfläche wird beim Vernetzen nicht
heimlich zur ganzen Fläche erweitert. Vorhandene Merkmalsindices bleiben
bei einer reinen Attributänderung gültig.
`paint_slot.replace_filament` übernimmt eine ausdrücklich gewählte Spule
vollständig, auch unbekannte Materialwerte. Ohne dieses gespeicherte Flag
behält die Operation das historische Ergänzungsverhalten leerer Felder.
`clear_filament` entfernt eine Zuweisung am Körper oder an `at_features`;
das frühere einzelne `at_feature` bleibt lesbar. Die Dreiecke aller gewählten
Merkmale werden gemeinsam vor der Platzsuche betrachtet. Bei einer Teilmenge werden andere bisherige
Slot-0-Flächen mit ihrer unveränderten Definition auf einen freien Platz
verschoben. Ohne Platz bleibt der Körper unverändert und der Fehler nennt
die nötige größere Auswahl. Geometrie, Merkmale und exakte Hohlrauminformation
bleiben erhalten; ein neutrales Slot 0 besitzt keine Filamentdefinition.
Ein altes allein am Körper gespeichertes Material wird vor dem teilweisen
Färben oder Entfernen über `slots_for_object` in explizite Definitionen
übernommen. Vollständige Abwahl leert auch dieses alte Materialfeld.
Die Differenzansicht überspringt ausschließlich identische Netzarrays,
keine bloß gleichen Hüllquader und Volumina. Und identische Netzarrays mit
anderen Farben überspringt sie nicht mehr (RM-169): `Difference.recoloured`
trägt dann den Körper danach, `Difference.retriangulated` den Körper danach,
wenn die Dreiecke sich ändern und das Volumen unter dem bleibt, was der
Drucker hinterlässt — `compare_scenes` setzt beides, die Ansicht zeichnet den
Körper danach über den davor (`Viewport._cover_body`). `SceneDifference.changed`
bleibt die Volumenfrage; `reshaped` und `recoloured` sind die zwei anderen.
Eine unvollständige Differenz (`difference.incomplete`, ein Schnitt ist
gescheitert) trägt kein `retriangulated`: Zwei Volumina von null sind dann
keine Aussage über das Volumen.

Eine mitgeführte exakte `MeshData.cavity` folgt in `transform.apply` derselben
Matrix wie der Körper. Änderungen der Topologie verwerfen die Auskunft,
solange ihre Gültigkeit nicht eigens hergestellt wird.
Reine Slotzuweisungen in `attributes.with_slot` und `paint.fill_feature`
erhalten den Innenraum unverändert; sie ändern keine Geometrie.

*Früher unter „Netz, Farbe, Text“, HEAD-Fassung.*

**Zwei Dezimierungen, zwei Zusagen.** `mesh_ops.decimate` ist die der
Operation: Zielzahl, Solvername, beidseitig gemessene Abweichung, Volumen-
und Wasserdichtheitsprüfung. Vor jedem Solver läuft das exakte Vorspiel
(`_exactly_flattened`): `manifold3d.simplify(0)` nimmt die Ecken heraus,
deren Nachbarschaft eben oder gerade ist — punktgleiche Oberfläche, jede
neue Ecke eine alte, geprüft an Dichtheit, Teilzahl und Volumen
(`units.VOLUME_SUM_NOISE`); reicht das allein unter das Ziel, heißt der Solver
`"exact"`. Die viermal unterteilte Lochplatte: 203 776 → 814 Dreiecke in
110 ms, wo `fast_simplification` vier Sekunden stillstand und der Rückfall
danach elf brauchte. Danach der Rückfall auf den exakten Kern, und zwar an
**zwei** Fragen: wenn `fast_simplification` das Ziel verfehlt, und wenn sein
Ergebnis kein Körper mehr ist (`_lost_body` — nicht mehr geschlossen oder in
mehr Teile zerfallen). An CAD-Exporten mit echten Nadeln — ein Zylinder aus
2 048 Sektionen, der Besenhalter — nimmt sein Flip-Schutz kein Dreieck weg,
und dort findet auch das Vorspiel nichts, weil jede Ecke etwas beschreibt.
An dünnwandigen Gittern zieht er dagegen Kanten zusammen, die nicht
zusammengehören: erzeugte Eule 150 000 → zehn offene Teile statt eines,
Voronoi-Spiderman bei 30 000 zwölf statt zwei. Der Rückfall prüft sein eigenes
Ergebnis auf Dichtheit, Teilzahl, Volumen und Abweichung, gibt also nur Heiles
her — die Eule rettet er bei 150 000 und 60 000 vollständig. Wo er ablehnt,
bleibt das zerrissene Ergebnis stehen und `_deviation_findings` sagt es
(`mesh.not_watertight`, `mesh.components_split`).
`mesh_ops.decimate_for_display` ist die des Bildschirms — Anzeige ab der
Schwelle aus §31, Beispielbilder, Stellvertreter der Orientierungssuche:
erst der exakte Kern nach Sehnenfehler (`units.MAX_FACET_SAG` als Start, je
Schritt vervierfacht), dann das Zusammenlegen im Raster für Netze, die der
Kern nicht nimmt (`_clustered_for_display`). Die angeforderte Dreieckszahl ist
ein Richtwert; der Rasterweg darf bis zum Doppelten behalten. Was der Kern beim
Vereinfachen an Schalen stehen lässt, die im Mittel dünner sind als seine
Toleranz, geht nicht mit (`kernel_jobs.without_slivers`), und `_as_mesh` verschweißt nur,
wo das Netz dabei dicht bleibt — beides riss an Kundenmodellen das grobe Netz
der Vorschau auf, und die Bohrung darauf scheiterte (RM-212). Für die große
Anzeige sind damit höchstens 400.000 Dreiecke bei einem Richtwert von 200.000
zulässig (§31). Eine geometrische Abweichung wird hier nicht gemessen.
**Die Operation hat eine Tür zum Anzeigeweg:** `decimate_mesh(method="fast")`
ruft `decimate_for_display` und sonst nichts (`_decimated_fast`) — keine
Messung, ein Befund `mesh.simplified_unmeasured`, der das sagt. Die grobe
Vorschau der Sitzung nimmt diesen Weg (Entscheidung Robert, 23.09.2026,
RM-208); die Vorgabe bleibt `"measured"`, jedes vorhandene Projekt rechnet
wie zuvor. Zahlen und Grenze in `.claude/rules/wartezeit.md`, „Die grobe
Vorschaustufe".
`mesh_ops.raster_for_display` ist nur das Raster, für das Vorschaubild im
Objektbaum: Der exakte Kern hält während `simplify` den GIL und hielt damit
aus dem Arbeiter heraus das Fenster an (gemessen bis 800 ms, siehe
`wartezeit.md`, „Ein Arbeiter ist nur nebenläufig …").

*Die Zwischenfassung nennt für den gehaltenen GIL „am Besenhalter bis 456 ms“; die Messung steht in `konzepte/begruendungen/regel-wartezeit.md`.*

*Früher unter „Innenraum und verlustfreie Netze“.*

`MeshData.cavity` ist eine optionale, geschlossene Schnittgeometrie des
tatsächlich ausgehöhlten Innenraums. Sie hat höchstens eine Ebene und reist
als eigene Vertex-/Flächentabellen im NPZ-Cache. `transform.apply` führt
dieselbe Matrix auf beiden Netzen aus; sonstige Geometrieänderungen verwerfen
die Auskunft, solange kein belegbarer Folgeraum berechnet wird.
`lattice_fill` beschneidet das Gitter auf diesen Raum. Ohne Auskunft sind
geschlossene, nach innen gerichtete Innenschalen die Grundlage — und wo auch
die fehlen, die **Entlüftung**: Ein ausgehöhlter Körper, der als STL draußen
war, hat eine Schale, weil die Entlüftungsbohrung außen und innen verbindet.
`_cavity_mesh` schließt die erkannten durchgehenden Bohrungen probeweise
(`_bore_solid`, mit der Zugabe aus `prepare.FEATURE_OVERLAP` — zwei
zusammenfallende Zylinderflächen schließt keine Boolesche zuverlässig), und
was danach eingeschlossen ist, ist der Innenraum; der Befund
`lattice.cavity_from_vents` sagt es, und `labels.body_facts` sperrt den
Menüeintrag deshalb nicht mehr. Ein Hüllquader oder eine konvexe Hülle
ersetzt weiterhin keinen Innenraum.

Neuvernetzung überträgt Slots über `attributes.transfer` — außer *Kanten
verfeinern*, das die Herkunft jedes Dreiecks kennt (`mesh_ops._inherited`,
`.claude/rules/operationen.md`). Sein Ergebnis trägt je Dreieck den Ursprung
(`mesh.remember_refined_units`), weitergereicht durch Boolesche Operationen an
den unberührten Dreiecken (`attributes.carry_refined_units`),
`repair.merge_vertices`, `MeshData.replacing` mit denselben Dreiecken und
`to_bytes`; die Erkennung zählt daran das ungeteilte Netz. Skulptur-Etappen
verwenden das verlustfreie NPZ statt STL. Beim Lesen aus Projektquellen werden
NPY-Header und entpackte Größe vor der Array-Allokation geprüft.
`measure.surface_gap` verwendet den räumlichen Index von Manifold mit
`Mesh64`; fehlende Körperübernahme ist keine Abstandsaussage.
`measure.body_overlap` misst die vollständige starre Körperverschneidung.
Zwei native Körper werden auf eigenen Kopien validiert und nichtdestruktiv
verschnitten; auch Prüfkennzeichen am Original bleiben unverändert. Netz und
gemischte Paare benutzen ausschließlich unveränderte Dreiecke und die direkte
Boolesche Stufe mit gültiger leerer Ausgabe. Kein Reparaturweg begründet einen
Nachweis. Fehler bleiben Fehler, Abbruch wird vor und nach nativen Aufrufen
geprüft. Ein gemischtes Ergebnis beschreibt ausschließlich den Netzzwilling;
die Passungsprüfung in `scene.fits` benennt diese Grenze sowie Einbaulage und
Fertigungsspiel getrennt vom gemessenen Überdeckungsvolumen.
