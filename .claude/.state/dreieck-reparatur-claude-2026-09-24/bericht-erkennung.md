# Review: Erkennung bearbeitbarer Formen an Dreiecksnetzen — Reparatur und lokale Erkennung

Stand: 24.09.2026, abgeschlossen 22:25. Prüfer: Claude, nur lesend (keine Änderung in `app/`
oder `tests/`). Grundlage: Arbeitsbaum `F:\3D Druck` gegenüber HEAD `8ed5d6299`, darin der
Codex-Patch `.claude/.state/triangle-repair-review-2026-09-24/staged.patch` und die laufende
Arbeit der Hauptsitzung an `geom/repair.py` und `ingest/loader.py`. Sonden und Messausgaben:
`.claude/.state/dreieck-reparatur-claude-2026-09-24/sonden/` (Liste am Ende).

**Status** jedes Befunds gilt für den Stand zwischen 22:17 und 22:22 Uhr; alle offenen
Befunde sind dort erneut gemessen (`sonden/nachmessung_2217.txt`, `nachmessung_2219.txt`).
Zeilennummern gelten für diesen Stand.

Kennzeichnung: **belegt** = gemessen oder am Code nachgewiesen; **vermutet** = abgeleitet,
nicht gemessen.

## Kurzfassung — priorisiert

| Rang | Befund | Schwere | Ort | Kernmessung | Status 22:22 |
|---|---|---|---|---|---|
| 1 | **B10** Nach bestätigter Vollerkennung eines großen Modells bricht jeder Folgeschritt mit „zu viele Dreiecke für die lokale Suche“ ab — auch Reparieren und Verschieben | hoch | `app/core/scene/evaluate.py:2494`, `:2624`; `app/core/perceive/local.py:625-699` (`raise` in `:664`, `:667`, `:697`) | Besenhalter (59 740 △) mit Grenze 50 000: Schritt 2 hält an, `local_budget`, 22,3 s | **offen** |
| 2 | **B4** Fehlende Wand bzw. Deckfläche wird je Ring gedeckelt: Bohrung zugestopft, Durchgang wird Sackloch, 570 Durchdringungen — Bericht nur „geschlossen“ | hoch | `app/core/geom/repair.py:1008` (`fill_boundary_loops`), `:1028` (`_fill_loops`), `:485` (`FILL_LOOP_SHARE`), `:1831`/`:1848` (Befunde) | 4 → 3 Bohrungen; ganze Oberseite fehlt → 4 Sacklöcher, 570 Durchdringungen; Senkung weg → Bohrung oben gedeckelt | **offen**, Zapfen-Doppelscheibe behoben |
| 3 | **B5** Lokale Erkennung am Großnetz: Radius ≤ 8 → „Suchrand“, ≥ 10 → „zu viele Dreiecke“; Vorgabe 10 | hoch | `app/core/perceive/local.py:153` (`_region`), `:66` (`LOCAL_FACE_LIMIT`), `app/core/perceive/ops.py:20-22` (Vorgabe 10) | Drache (2 330 374 △): 18 von 18 Stellen ohne Ergebnis; Radiusreihe 5…15 kippt zwischen 8 und 10 | **offen** |
| 4 | **B11** Reparaturschritt prüft immer räumlich auf Durchdringungen: Minuten statt Sekunden, ohne Fortschritt | mittel | `app/core/geom/ops.py:725`; `app/core/geom/repair.py:1474`, `:1486`; Zwilling `app/core/perceive/maps.py:906` | Drache 12,4 → 72,2 s, Gartenschlauchhalter 3,4 → 22,2 s | **offen** (seit 18 Uhr langsamer) |
| 5 | **B3** Lochfüllung wählt Dreiecke quer zur Fläche; Verrundung R 3 wird R 2,77 | mittel | `app/core/geom/repair.py:842` (`_loop_triangles`), `:1028` (`_fill_loops`) | Rucksackhalter: `fillet` R 3,0003/17 △ → R 2,773/10 △ | **offen** |
| 6 | **B6** „Gerundete Seiten“ hängen an der Vernetzung; formgleiche Kantenteilung (= Vernähen von T-Stößen) ändert sie | mittel | `app/core/perceive/features.py:8016` (`detect_curved_faces`) | Besenhalter 5 436,07 → 4 241,84 mm²; Siebhalter-Ring: gerundete Seiten werden zu Verrundungen R 2,5 | **offen** |
| 7 | **B8** Verschweißen eines gerissenen Netzes legt auch absichtlich getrennte Ecken zusammen | niedrig | `app/core/geom/repair.py:1622` (`_tears_it_further`), `:1684` (Schweißschritt) | Siebhalter-Ring: 7 996 → 7 972 △, Flächen 16 → 28 | **offen** |
| 8 | **B7** „Doppelte Punkte wurden verschweißt“ für eine unbenutzte Ecke; Schritt gilt als verändernd | niedrig | `app/core/geom/repair.py:66` (`merge_vertices`), `:1706` | Torus + 1 unbenutzte Ecke → `repair.welded`, `removed: 1`, `changed=True` | **offen** |
| 9 | **B9** Kernkarte verweist auf `evaluate._renamed`, das es nicht gibt | niedrig | `app/core/CLAUDE.md:135` | kein Treffer in Code und Historie | **offen** |
| — | **B1** Zwei fehlende Dreiecke an einer Ecke → gefalteter Fächer, Oberseite verschwindet | hoch | `app/core/geom/repair.py:569`, `:683` (`_hole_rings`), `:826` (`_folds`) | vorher 7 Durchdringungen, 5 statt 6 Flächen | **behoben** (Hauptsitzung), nachgemessen 22:17 |
| — | **B2** Umgedrehter Einzelkörper in Mehrkörpernetz bleibt umgestülpt; Ø34-Bohrung wird zu Verrundungen | hoch | `app/core/geom/repair.py:196` (`unify_normals`), `turn_shells_outward`; `app/core/ingest/loader.py:1092-1120` | vorher −10 228,65 mm³, 2 statt 3 Bohrungen | **behoben** (Hauptsitzung), nachgemessen 22:17 |

## Antworten auf die drei Prüffragen

**1. Merkmals-Lebenszyklus nach Reparatur (`repair_object` → `features={}` bei Änderung).**
Am Netz trägt der Weg: Namen bleiben stabil, wenn die Reparatur das Merkmal nicht berührt
(`hole_1` bleibt `hole_1`), erzeugte Merkmale behalten `provenance="generated"` und
`created_by`, Passungen und spätere Schritte mit Merkmalsnamen laufen weiter, und in acht
Szenarien an Korpus- und Kundennetzen entstand **keine** Rückfrage (Abschnitt „Geprüft ohne
Befund“). Ausnahme ist der große Weg: Oberhalb von `FEATURE_LIMIT_TRIANGLES` misst
`detect_known` alle bisherigen Merkmale nach und hält den ganzen Schritt an, sobald eines
davon sein lokales Budget reißt (B10). Testlücke: Der Normalfall „Reparatur ändert das Netz
und lässt ein erzeugtes Merkmal unberührt“ ist belegt (Sonde p2c), aber nicht in der Suite.

**2. Lokale Erkennung.** Die neuen Kennungen `local_*` (`local.py:90-138`) tragen, was der
Codex-Patch verspricht; alle sechs Gründe haben Handlungsvorschläge, `ValidationError`
behält den Detailsatz. Das Problem liegt davor: Der Suchbereich ist ein Würfel über alle
Dreiecke, und am Drachen — dem Referenzmodell der Zeitschätzung (`RECOGNITION_REFERENCE_TRIANGLES`) —
liegt zwischen „Suchrand“ und „Budget“ kein Radius, der etwas findet (B5). Dieselbe Würfelsammlung lässt nach bestätigter
Vollerkennung jeden Folgeschritt scheitern (B10). Abbruch prüft `_region` blockweise; das ist
in Ordnung.

**3. Erkennung roh gegen repariert.** An beschädigten Netzen stellt die Reparatur die
Erkennung des unbeschädigten Netzes fast immer wieder her — Sonde 1: 135 Schadensfälle an
13 Dateien mit 14 Körpern (Korpus und Kunde), Verschweißen, gedrehte Normalen, T-Stöße und kleine Löcher
(1–6 Dreiecke) ergeben dieselben Arten, Anzahlen und Maße, und die Erkennung dauert danach
wieder so lange wie am unbeschädigten Netz (beschädigt bis fünfmal länger, z. B.
Siebhalter-Ring 2,12 s beschädigt gegen 0,40 s repariert). Scheinmerkmale aus kleinen
Füllungen auf Kugel, Torus und Zapfen entstehen nicht (Sonde 6). Ausnahmen, alle belegt:
große Lücken und fehlende Wände (B4), eine ungünstig gewählte Füllung an einer Verrundung
(B3), gerundete Seiten nach dem Vernähen (B6), das Schweißen eines gerissenen Netzes (B8);
B1 und B2 sind behoben. Von 80 Körpern der Kundendateien in `F:\3D Dateien` (Sonde 0) ist
nach dem Einlesen genau einer offen — „Blessed Family – Heart Script Decor“ mit vier
verzweigten Kanten; Import und Reparatur liefern dort dasselbe (dicht, ein Teil, 26 statt 27
Flächen, 8 Verrundungen, 18 gerundete Seiten; der Flächenunterschied ist nicht weiter
untersucht).

## Offene Befunde im Einzelnen

### B10 — Nach bestätigter Vollerkennung eines großen Modells bricht jeder Folgeschritt ab

- **Schwere:** hoch — jede Operation hält an; der Satz nennt einen „Bereich“, den der Schritt nicht hat.
- **Status 22:19: offen, erneut gemessen.**
- **Ort:** `app/core/scene/evaluate.py:2494` (`local_only = mesh.triangle_count > FEATURE_LIMIT_TRIANGLES`; die gespeicherte Wahl gilt nur bei `operation.op == "load"`, `:2499-2510`), `:2624` (`detect_known(mesh, {**transformed.candidates, **output_features})` über **alle** bisherigen Merkmale); `app/core/perceive/local.py:625-699` (`detect_known`: `_region` gibt bei Budgetüberschreitung `None` → `raise local_error("budget")` in `:667`; `raise local_error("boundary")` in `:664` und `:697`).
- **Belegt mit verschobener Grenze** (automatische Grenze 50 000 statt 1 500 000, wie die Suite `FEATURE_LIMIT_TRIANGLES` verschiebt): `F:\3D Dateien\broomholdervcd_d35mm.stl` (59 740 △) geladen, Vollerkennung bestätigt → 62 Merkmale. Danach:
  - „Reparieren“: `complete=False`, `stopped_at=2`, `op.repair.ValidationError` „Dieser Bereich enthält zu viele Dreiecke für die lokale Suche. Wählen Sie einen kleineren Bereich oder verringern Sie zuerst die Dreiecke.“ (`constraint: local_budget`), 22,3 s.
  - Nur „Verschieben“ um 5 mm: derselbe Abbruch (`op.translate_object.ValidationError`, `local_budget`).
  - Reproduktion: `sonden/p8_bestaetigt_dann_reparatur.py` → `p8_bestaetigt_dann_reparatur.txt`.
- **Vermutet an echten Größen:** Ab 1,5 Mio. Dreiecken ist `LOCAL_FACE_LIMIT` (50 000) ein Dreißigstel des Netzes; am Drachen reißt schon Radius 10 das Budget (B5). Ein großes ebenes Flächenmerkmal bekommt in `detect_known` den flächengleichen Durchmesser als Radius und reißt es damit sicher. Derselbe Weg greift ohne Bestätigung, sobald ein Schritt ein Netz mit Merkmalen über die Grenze wachsen lässt.
- **Kundensicht:** Wer bei einem großen Modell „Mit Merkmalserkennung laden“ wählt, kann danach nichts mehr tun; Strg+Z nimmt den Schritt, nicht die Ursache.
- **Fix-Vorschlag:**
  1. `detect_known` hält einen Folgeschritt nicht wegen eines nicht nachmessbaren Merkmals an: Es verliert seine Belegung wie am Netz üblich (`perceive.orphaned`, bzw. `perceive.referenced_lost`, wenn `needed`/`referenced` es nennen); anhalten und fragen nur für benötigte Merkmale — die Mengen liegen in `_with_features` schon vor.
  2. Starre Bewegungen im großen Weg über `transformed.exact` mitnehmen statt nachmessen (der Vollweg tut das über `carry_detection`; im lokalen Zweig fehlt der Zwilling).
  3. Die bestätigte Wahl (`recognition-answer:`) für die Nachfolger desselben Körpers gelten lassen, statt beim ersten Folgeschritt still auf den lokalen Weg zu fallen — mit der Arbeit an `_recognition_choice`/`CONFIRMED_FEATURE_LIMIT_TRIANGLES` abstimmen.
- **Testidee:** wie `test_large_path_revalidates_known_features_after_translation`, dazu eine große ebene Fläche unter den bekannten Merkmalen und ein `LOCAL_FACE_LIMIT`, das deren Würfel reißt: `_with_features` nach `translate` und nach `repair` ist vollständig, höchstens mit Befund; heute `local_budget`.

### B4 — Fehlende Wand oder Deckfläche wird je Ring gedeckelt

- **Schwere:** hoch — Funktionsmerkmale verschwinden oder wechseln die Topologie; der Bericht sagt „geschlossen“.
- **Status 22:21: offen**, erneut gemessen (`sonden/p4_grosse_luecken.txt`, `e4_oberseite.py`); die Zapfenzeile ist in der Hauptsitzung behoben.
- **Ort:** `app/core/geom/repair.py:1008` (`fill_boundary_loops`, Docstring „…und lässt stehen, was eine fehlende Wand ist“), `:1028` (`_fill_loops`: jeder Randring für sich), `:485` (`FILL_LOOP_SHARE` = 5 % der Körperoberfläche entscheidet über die Warnung), `:1831` (`repair.wide_hole_filled`), `:1848` (`repair.holes_filled`, `info`).
- **Entschieden ist das Schließen** (Robert, 22.09.2026, „alles bei der Reparatur beheben“; `tests/test_repair.py::test_a_missing_wall_is_closed_and_said_so`, mit „Offen lassen“ am breiten Loch). Falsch ist, **wie** geschlossen wird und **was** der Bericht sagt.
- **Messungen** (Import- und Reparaturweg jeweils gleich):

| Beschädigung | Ergebnis der Reparatur | Erkennung vorher → nachher | Bericht |
|---|---|---|---|
| `plate_holes.stl`: ganze Wand der Bohrung (25, 15) fehlt (96 △) | dicht, 31 322,35 → **31 491,76 mm³** (= π·2,6²·8: zugestopft) | 4 → **3** Bohrungen | nur `repair.holes_filled` (info) |
| Viertel der Wand fehlt (24 △) | dicht, +4,0 mm³ | 4 → 3 Bohrungen + 1 `curved_face` | nur `repair.holes_filled` |
| halbe Wand fehlt (48 △) | dicht, +25,9 mm³ | 4 → 3 Bohrungen + 1 `curved_face` | nur `repair.holes_filled` |
| **ganze Oberseite fehlt** (202 △; Randringe: Rechteck + vier Mündungen zu je 48) | dicht, Volumen gleich, aber das Rechteck liegt mit 2 Dreiecken **über** den Mündungen, jede Mündung bekommt zusätzlich einen Deckel: **570 Durchdringungen** | 4 Durchgangsbohrungen → 4 **Sacklöcher** (`through=False`), Flächen 6 → 10 | `repair.wide_hole_filled` (sagt nichts über die Bohrungen) + `repair.holes_filled` |
| `plate_countersunk.stl`: Kegel der Senkung fehlt (96 △) | dicht, +112 mm³: Ø10 oben gedeckelt **und** die Ø5,2-Mündung darunter — der Durchgang wird ein Sackloch von unten | Senkung weg, Bohrung mit falscher Topologie | nur `repair.holes_filled` |
| `post_with_fillet.stl`: Mantel des Zapfens Ø12 fehlt (193 △) | bis 18:40: Doppelscheibe ohne Volumen, 190 Durchdringungen. **Seit 18:41 behoben:** Deckelring bleibt offen (96 Kanten), 0 Durchdringungen, Befund `repair.no_thickness` | Zapfen weg (richtig: es gibt keinen Mantel) | `repair.holes_filled`, `repair.no_thickness` |

- **Kundensicht:** Ein Download, dem eine Zylinderfläche fehlt (typischer Tessellierungsausfall), kommt „repariert“ zurück; die Schraubenbohrung ist zu oder die Senkung hat einen Boden. Der Bericht zeigt einen Hinweis, der Kunde merkt es am Druck.
- **Fix-Vorschlag:**
  1. **Ringe einer Ebene gemeinsam füllen:** Außenring und darin liegende Innenringe derselben Ebene sind eine Fläche mit Löchern — als Polygon mit Löchern triangulieren (Ohrenschneiden mit Brückenkanten oder GEOS-Triangulierung in der Ringebene), nicht fünf Scheiben.
  2. **Mantellücke als Mantel schließen:** Zwei koaxiale Ringe derselben Komponente, deren Ringnachbarn zueinander zeigen, sind eine fehlende Wand — als Band zwischen den Ringen überbrücken (stellt die Bohrung wieder her), statt beide Ringe zu deckeln.
  3. **Bericht nach Wirkung, nicht nach Fläche:** Verschließt eine Füllung die Mündung eines vorher offenen Hohlraums oder macht sie einen Durchgang zum Sackloch, ist das eine `warning` mit Ort und „Offen lassen“ — dieselbe Handlung wie beim breiten Loch.
  - **Zwillinge:** Importweg (`ingest/loader.py`, Schritt 4b) und Reparaturschritt teilen `repair()`; der Fix sitzt einmal.
- **Testidee:** die fünf offenen Zeilen oben als Korpusfälle: Bohrungszahl sinkt nicht still, `self_intersection_check` findet keine neuen Durchdringungen, Durchgänge bleiben Durchgänge; heute rot.

### B5 — Lokale Erkennung am Großnetz findet bei keinem Radius etwas

- **Schwere:** hoch für große Modelle — der beworbene Rückweg „einzelne Merkmale lokal erkennen“ liefert am Referenzmodell nichts.
- **Status 22:18: offen**, erneut gemessen (`sonden/e5_drache_radiusreihe.py`).
- **Ort:** `app/core/perceive/local.py:153-171` (`_region`: Würfeltest `point ± radius` gegen die Hüllquader aller Dreiecke), `:66` (`LOCAL_FACE_LIMIT` = 50 000), `:246` (`_recognise_region`: `continuing` sperrt jeden glatt über den Rand laufenden Fleck), `app/core/perceive/ops.py:20-22` (Vorgabe `radius = 10`).
- **Messung:** `F:\3D Dateien\Mausoleum Dragon.3mf`, ein Körper mit 2 330 374 △ (= `RECOGNITION_REFERENCE_TRIANGLES`), 88,9 × 31,5 × 57,8 mm, dicht. Sechs echte Stellen (ebene Unterseite, waagrechte Oberseite, senkrechte Wand, drei zufällige) je Radius 5/20/60: **18 von 18 ohne Ergebnis** (`sonden/p5_lokal_gross.txt`). Radiusreihe an der Unterseite: r = 5/6/7/8 → `boundary` bei 12 837/16 817/23 447/39 161 △ im Würfel; r = 10/12/15 → `budget`. Die Unterseite selbst hat nur 3 274 △; das Budget verbrauchen fremde, dicht modellierte Flächen im Würfel. Je Versuch 1,5–2,4 s.
- **Kundensicht:** Radius 10 → „Wählen Sie einen kleineren Bereich“; Radius 5 → „Vergrößern Sie den Suchradius“. Kein Radius dazwischen hilft.
- **Fix-Vorschlag:**
  1. Den Bereich vom Saatdreieck aus über `face_adjacency` fluten (innerhalb des Suchradius), nicht über den Würfel sammeln; das Budget gilt dann dem, was zur Stelle gehört.
  2. Ebene Flächen ohne Fit-Budget: koplanare Flutung bis zu scharfen Kanten belegt die Fläche vollständig (dieselbe Koplanaritätsprüfung wie `surfaces.planar_patch` gegen `EPS_GEOM`).
  3. Kein Pendel im Dialog: Hat derselbe Treffer `local_boundary` bei kleinerem und `local_budget` bei größerem Radius geliefert, eine Aussage („für die lokale Suche zu groß“) mit *Dreiecke verringern* als erstem Knopf.
  - **Zwilling:** `detect_known` benutzt dieselbe Würfelsammlung (B10); ein Fix gilt beiden.
- **Testidee:** große ebene Grundplatte aus wenigen Dreiecken, daneben im Würfel eine dicht unterteilte Freiform > 50 000 △ ohne Verbindung; `detect_local` an der Platte mit der Vorgabe 10 → vollständige Fläche; heute `budget`.

### B11 — Jeder Reparaturschritt rechnet die räumliche Durchdringungsprüfung

- **Schwere:** mittel — Wartezeit ohne Fortschritt; jede Einstellung im Reparaturdialog zahlt sie erneut (§31: Parameteränderung → sichtbares Ergebnis unter 2 s).
- **Status 22:21: offen**, seit der ersten Messung langsamer (größeres Paarbudget `intersection_budget`, `repair.py:1474`; gleichzeitige Last anderer Sitzungen auf dem Rechner nicht ausgeschlossen).
- **Ort:** `app/core/geom/ops.py:725` (Codex-Patch: `inspect_intersections=True` für jeden ausdrücklichen Reparaturschritt) → `app/core/geom/repair.py:1486` (`self_intersection_check`, ohne Merker, ohne Fortschritt); Zwilling `app/core/perceive/maps.py:906` (Netzfehlerkarte rechnet dasselbe noch einmal).
- **Messung** (`repair()` direkt, `sonden/e11_durchdringungsdauer.py`):

| Modell | ohne Prüfung | mit Prüfung (18:3x) | mit Prüfung (22:21) | Ergebnis |
|---|---|---|---|---|
| `Mausoleum Dragon.3mf` (2 330 374 △) | 10,2 / 12,4 s | 46,8 s | **72,2 s** | nichts zu ändern |
| `garden-hose-holder.3mf` (392 532 △) | 1,8 / 3,4 s | 12,1 s | **22,2 s** | `repair.self_intersections_detected` (die Teile überlappen wirklich) |

- **Fix-Vorschlag:** Ergebnis je Netz merken (wie `_edge_table` im Netzcache) und in Reparatur **und** Fehlerkarte denselben Merker lesen; nur im endgültigen Lauf rechnen, nicht in der Live-Vorschau (`detect_features=False`-Weg); `ctx.progress` durchreichen oder die Diagnose als Hintergrundauskunft des Berichts führen.
- **Testidee:** zwei Aufrufe am selben Netz rechnen `crossing_faces` einmal (Zähler per monkeypatch); Leistungswächter nur beim Release.

### B3 — Die Lochfüllung wählt Dreiecke in der Projektionsebene; Verrundung R 3 wird R 2,77

- **Schwere:** mittel — stilles Fehlmaß an einem bearbeitbaren Merkmal nach Import oder Reparatur.
- **Status 22:20: offen**, erneut gemessen (`sonden/e3_verrundung_fuellung.py`). `_folds` (`repair.py:826`) verwirft nur gefaltete Fächer, nicht eine gültige, aber quer liegende Ohrenwahl.
- **Ort:** `app/core/geom/repair.py:842` (`_loop_triangles`: Ohrenschneiden in der Newell-Ebene, das erste gültige Ohr gewinnt), `:1028` (`_fill_loops`: der erste Versuch ohne Kantenkonflikt wird genommen).
- **Messung:** `F:\3D Dateien\the-over-engineered-backpack-wall-mount-v2.stl` (15 906 △). `fillet_2` R 3,0003, Länge 14,937, 17 △, als Fächer vernetzt. Entfernt 10177 `[5410,5402,5411]` und 10178 `[5410,5411,5408]`. Die Füllung legt `[5402,5411,5408]` mit Normale (−0,48 | 0,02 | 0,88) quer zur Verrundung. Danach: `fillet` R **2,773** (−7,6 %), Länge 13,261, **10** △. In Sonde 1 die einzige Maßabweichung der reparierten von der unbeschädigten Erkennung.
- **Kundensicht:** Nach dem Laden steht R 2,77 im Baum; „Radius ändern“ geht vom falschen Maß aus.
- **Fix-Vorschlag:** kleine Ringe (bis etwa sechs Ecken) über alle Triangulierungen mit dem kleinsten größten Diederwinkel gegen die Ringnachbarn wählen (Liepa: erst Diederwinkel, dann Fläche), größere Ringe das Ohr mit dem kleinsten Normalensprung zuerst; Gültigkeit weiter in der Newell-Ebene. Plattformgleich rechnen (RM-187) und in `tests/test_platform_identity.py` (`_WAYS`) aufnehmen. Zwilling: Import- und Reparaturweg teilen den Füller.
- **Testidee:** Quader mit fächerförmig vernetzter Verrundung R 3, zwei Fächerdreiecke entfernt → R 3 ± 1 µm und gleiche Dreieckszahl nach `repair`; heute R 2,773.

### B6 — „Gerundete Seiten“ hängen an der Vernetzung

- **Schwere:** mittel — Umfang und Namen gerundeter Seiten sind nach Vernähen oder Neuvernetzung nicht stabil; eine Filamentzuweisung trifft danach nur noch Teile.
- **Status 22:18: offen**, erneut gemessen (`sonden/e6_kantenteilung.py`).
- **Ort:** `app/core/perceive/features.py:8016` (`detect_curved_faces`: `rounded = set(adjacency[(angles > EPS_ANGLE) & smooth].ravel())` — ein Dreieck zählt nur, wenn es selbst an einer gekrümmten Naht liegt).
- **Messung:** `broomholdervcd_d35mm.stl`, 199 Kanten formgleich am Mittelpunkt geteilt (beide Nachbarn, dicht, Volumen bitgleich 40 473,782 mm³): Bohrungen, Verrundungen, Kegel, Flächen unverändert, gerundete Seiten 9 → 8, Fläche **5 436,07 → 4 241,84 mm²**; fünf verschwinden (836,35/836,35/822,72/647,85/262,77 mm²), vier neue entstehen. Siebhalter-Ring nach dem Vernähen von T-Stößen (Sonde 1): drei Seiten zu 70,99 mm² werden zu **zwei Verrundungen R 2,500** und zwei Seiten zu 60,23 mm². An `1x1-bin`, `Wedge-Lock (Base)`, `post_with_fillet` keine Änderung.
- **Mechanik vermutet** (am Code nachvollzogen, nicht je Dreieck vermessen): Die geteilte Hälfte eines Mantelrechtecks liegt nur noch an ebenen Kanten und fällt aus `rounded`.
- **Fix-Vorschlag:** `rounded` auf koplanare Facetten schließen (gehört ein Dreieck einer Facette dazu, gehört die Facette dazu) — dieselbe Denkweise wie `facet_middles`. `_curved_faces`/`_curved_faces_read` nach derselben Regel prüfen.
- **Testidee:** D-Profil-Korpus, alle Diagonalen formgleich teilen → dieselben gerundeten Seiten; heute rot.

### B8 — Verschweißen eines gerissenen Netzes legt absichtlich getrennte Ecken zusammen

- **Schwere:** niedrig — sub-µm-Geometrie, aber 24 Dreiecke fallen, zwölf Kleinstflächen erscheinen.
- **Status 22:20: offen**, erneut gemessen (`sonden/e8_ring_schweissen.py`).
- **Ort:** `app/core/geom/repair.py:1622` (`_tears_it_further` wägt die **Summe** offener und verzweigter Kanten des ganzen Netzes), `:1684` (Schweißschritt in `repair()`); Zwilling `app/core/ingest/loader.py:929-1017` (Schritt 2).
- **Messung:** `Siebhalter+X1C.3mf`, Körper „Ring“ (7 996 △, Schweißtoleranz 0,092 µm) trägt 12 Eckpaare im Abstand 0,015 µm. Unbeschädigt: `repair.weld_skipped` (richtig, sonst 18 verzweigte Kanten). Mit einem Riss (74 offene Kanten) wiegt die Heilung die Verzweigungen auf: Schweißung angenommen, 24 Dreiecke entartet und entfernt (7 996 → 7 972), Flächen 16 → **28** (zwölf neue zu 1,169 mm²).
- **Fix-Vorschlag:** je Punktgruppe entscheiden: nur zusammenlegen, wo keine Kante mit drei Nachbarn und kein entartetes Dreieck entsteht; die übrigen Gruppen im Befund `repair.weld_skipped` zählen. Zwilling im Import mitziehen.
- **Testidee:** Würfel mit zwei 1e-8 mm getrennten Ecken plus Riss → Riss geschlossen, Ecken getrennt, Dreieckszahl gleich.

### B7 — „Doppelte Punkte wurden verschweißt“ für eine unbenutzte Ecke

- **Schwere:** niedrig — falscher Berichtssatz; mit `features={}` zusätzlich eine volle Neuerkennung ohne Formänderung.
- **Status 22:20: offen**, erneut gemessen.
- **Ort:** `app/core/geom/repair.py:66` (`merge_vertices` zählt `before - len(body.vertices)`; trimesh entfernt dabei auch unbenutzte Ecken), `:1706` (`repair.welded`, `changed=True`); Zwilling `app/core/ingest/loader.py:952` (`welded = len(body.vertices) < before`, als `ingest.welded` bei OBJ/PLY/3MF).
- **Messung:** `torus_ring.stl` plus eine unbenutzte Ecke → `changed=True`, `repair.welded` mit `removed: 1`; ohne sie `changed=False`, keine Befunde.
- **Fix-Vorschlag:** unbenutzte Ecken still vorab entfernen, nur echte Verschmelzungen zählen; eine reine Umnummerierung setzt `changed` nicht.
- **Testidee:** Netz plus unbenutzte Ecke → kein `repair.welded`; echte Doppelecke → weiter `removed: 1`.

### B9 — Die Kernkarte verweist auf `evaluate._renamed`

- **Schwere:** niedrig (Doku).
- **Status 22:25: offen.** Ort: `app/core/CLAUDE.md:135` („Sie entsteht bei der Auswertung (`evaluate._renamed`)“). Weder Code noch `git log -S "_renamed" -- app/core/scene/evaluate.py` kennen den Namen; die Vergabe geschieht in `evaluate._with_features` (`:2291`) über `perceive.matching.apply_mapping`.
- **Fix-Vorschlag:** Verweis korrigieren. `tests/test_directory_docs.py` prüft nur §-Verweise; ein Wächter über Backtick-Bezeichner in Karten wäre der Zwilling (vermutet sinnvoll, Zahl weiterer toter Verweise nicht gemessen).

## Behoben während der Durchsicht (nachgemessen)

### B1 — Zwei fehlende Dreiecke an einer Ecke: gefalteter Fächer, Oberseite verschwand

- **Status: behoben in der Hauptsitzung**; nachgemessen 22:17 (`sonden/e1_sanduhr_faltung.py`, `nachmessung_2217.txt`).
- **Befund vorher:** `plate_holes.stl` ohne Dreiecke 52 `[69,71,72]` und 55 `[69,73,74]` (gemeinsam nur Ecke 69): `split_pinched_vertices` erzeugte einen Achterring, `_loop_triangles` blieb stecken, der Fächer über die Mitte faltete sich (zwei Dreiecke mit Normale −z in der +z-Fläche). Ergebnis dicht, aber **7 Durchdringungen**, Oberseite 3 915,29 mm² fehlte in der Erkennung — im Reparatur- und im Importweg.
- **Jetzt** (`repair.py:683` `_hole_rings`, `:826` `_folds`): Reparatur und Import je 796 △, 0 Durchdringungen, Oberseite 3 915,29 mm² wieder erkannt, 4 Bohrungen + 6 Flächen wie unbeschädigt. In der Suite: `tests/test_repair.py::test_two_holes_touching_in_one_face_close_without_a_fold`, `::test_a_fold_is_never_taken_as_a_fill`.

### B2 — Umgedrehter Einzelkörper in einem Mehrkörpernetz blieb umgestülpt

- **Status: behoben in der Hauptsitzung**; nachgemessen 22:17 (`sonden/e2_umgedrehter_koerper.py`).
- **Befund vorher:** `broomholdervcd_d35mm.stl` (drei überlappende geschlossene Körper): Teil 2 blieb nach Import (ein Teil umgedreht in der Datei) und nach Reparatur (5 % Dreiecke gedreht) bei −10 228,65 mm³; Gesamtvolumen 20 016,48 statt 40 473,78 mm³; die Ø34-Aufnahme wurde zu vier Verrundungen; der Import meldete nichts, „Reparieren“ danach „nichts zu tun“.
- **Jetzt** (`repair.py:196` `unify_normals` mit `turn_shells_outward`, derselbe Weg in `ingest/loader.py:1098-1120`): beide Wege liefern drei positive Teile (9 727,01 / 10 228,65 / 20 518,12 mm³), Import meldet `ingest.normals_flipped`, 3 Bohrungen inklusive Ø34, Arten wie unbeschädigt. Der ungewollte Zwilling Import ↔ Reparatur ist damit zusammengelegt. In der Suite: `tests/test_repair.py::test_an_inverted_cube_beside_a_right_one_is_turned_outward`.

## Geprüft ohne Befund (belegt)

**Lebenszyklus über die ganze Auswertung** (Sonden `p2_*`, `p7_kundenweg.py`; jede Rückfrage mitgeschrieben):

| Szenario | Namen | Rückfragen | Folgeschritt / Passung |
|---|---|---|---|
| Lochplatte + Kleinstteil, gebohrte Bohrung, „Kleine Teile entfernen“, zwei `resize_hole` (A1) | `hole_1…hole_5`, Flächen stabil; Flächen des Kleinstteils fallen still (außerhalb der Hülle) | 0 | laufen |
| Senkungsplatte ungeschweißt geladen, repariert, `resize_hole` (B1) | `hole_1`, `cone_1` stabil | 0 | läuft, Senkung mitgeführt |
| Zwei durchdringende Quader, Bohrung, Durchdringungen aufgelöst, `resize_hole` (C1) | `hole_1` stabil; verschmolzene Flächen neu benannt, alte als `perceive.orphaned` (info) — es sind andere Flächen | 0 | läuft |
| Zwei Dreiecke fehlen in einer Bohrungswand, Reparatur, `resize_hole` genau dieser Bohrung (D1) | `hole_4` stabil (94 → 96 △) | 0 | läuft |
| Großer Weg (Grenze 1): `detect_region` an einer Bohrung, Kleinstteil entfernt, `resize_hole` (F1) | `hole_1` stabil | nur die gewollte Ladefrage | läuft |
| Erzeugter Zapfen (`generated`, `created_by=2`), unberührende Reparatur, zweites `resize_feature` (p2c) | `pin_1` bleibt `generated`, `created_by=2` | 0 | läuft |
| Passung Zapfen (Körper 2) ↔ Bohrung (Körper 1), Reparatur an Körper 1 (p2d) | stabil | 0 | Passung unverändert geprüft |
| Schraubendreherhalter, Rucksackhalter, Besenhalter, je geschweißt/ungeschweißt geladen, Reparatur, `resize_hole` (p7) | stabil (am Besenhalter benennt das `resize_hole` zwei Verrundungen an der geänderten Mündung neu — Folge der Bohrungsänderung) | 0 | läuft |

**Codex-Tests:** `tests/test_repair_features.py` (entfernter erzeugter Zapfen über Cache, Wiederöffnen, Undo/Redo) und die `local_*`-Kennungen in `tests/test_local_detection.py` treffen, was sie behaupten.

**Reparatur und Erkennung an kleinen Schäden** (Sonde 1, 135 Fälle, 13 Dateien, 14 Körper): siehe Frage 3. Sonde 6 (Kugel, Torus, Zapfen, Verrundung, 1–3 Eckringe entfernt): keine Scheinmerkmale; Fülldreiecke bleiben teils unbeansprucht (Torus 2 015 → 2 008 △), die Art bleibt.

**Zurückgenommene Vermutung:** Ungeprüft mitgereichte erzeugte Merkmale (`unchecked`, z. B. Gewinde eines Bausteins) behalten nach einer umnummerierenden Reparatur keine veralteten Dreiecksnummern — Bausteinmerkmale werden ohne `face_indices` gebaut, `app/core/knowledge/parts/ops.py:1032` leert sie zusätzlich.

## Beobachtungen am Rand

- `app/ui/panels.py:650` `_local_targets` (Codex): Typ `Collection[ObjectId]`, verlangt aber ein `Mapping` und gibt sonst still `()` zurück; heute übergeben alle Aufrufer ein `Mapping`, ein künftiger Aufrufer mit einer Kennungsmenge verlöre den Knopf „Merkmale an dieser Stelle erkennen“ ohne Fehler. Typ auf `Mapping[ObjectId, SceneObject]` fassen.
- Der Referenzkörper `tests/data/meshes/post_with_fillet.stl` trägt selbst 4 sich durchdringende Dreiecke (`self_intersection_check` am unbeschädigten Netz, `p4_grosse_luecken.txt`); mit B11 meldet der Reparaturschritt dort künftig `repair.self_intersections_detected`. Korpusbeschreibung prüfen.
- Die während der Durchsicht gemeldeten ruff-Befunde der Parallelarbeit (`panels.py` F821, `loader.py` F401/RUF003, `tools/run_suite_isolated.py` Syntax) sind um 22:23 nicht mehr vorhanden (`ruff check` der betroffenen Dateien: bestanden).

## Testläufe (Exit-Code direkt gelesen, Ausgabe in Datei)

| Zeit | Umfang (`-m "not windowed and not performance"`) | Ergebnis |
|---|---|---|
| 18:03 | `test_repair_features.py`, `test_local_detection.py`, `test_features.py` | 253 bestanden, Exit 0 |
| 18:40 | dieselben + `test_repair.py` | 321 bestanden, 2 abgewählt, Exit 0 |
| 22:25 | dieselben vier am Endstand | **328 bestanden**, 2 abgewählt, Exit 0 (`sonden/tests_2222_claude.txt`) |

Keine Fenster- und Leistungstests (Projektregel).

## Sonden und Reproduktion

Alle unter `.claude/.state/dreieck-reparatur-claude-2026-09-24/sonden/`, jeweils mit `.txt`-Ausgabe:

| Datei | Frage |
|---|---|
| `p0_dichtheit.py` | Welche Kundenkörper sind nach dem Einlesen offen (80 Körper) |
| `p1_schaden_reparatur.py` | 135 Schadensfälle an 13 Dateien (14 Körper): Erkennung unbeschädigt / beschädigt / repariert, Laufzeit, Besitzer der Fülldreiecke (`…_alter_stand.txt` = Lauf vor der B1-Behebung) |
| `p2_auswertung_reparatur.py`, `p2b_…`, `p2c_…`, `p2d_…` | Lebenszyklus über die Auswertung: Namen, Rückfragen, Folgeschritte, Passung |
| `p3_lokal_reparatur.py` | `_with_features` im großen Weg nach Reparatur am Testzylinder |
| `p4_grosse_luecken.py` | B4 |
| `p5_lokal_gross.py`, `e5_drache_radiusreihe.py` | B5 |
| `p6_flicken_auf_rundungen.py` | Scheinmerkmale aus Füllungen auf Rundungen |
| `p7_kundenweg.py` | Kundenweg Laden → Reparieren → `resize_hole` an drei Kundendateien |
| `p8_bestaetigt_dann_reparatur.py` | B10 |
| `e1_sanduhr_faltung.py`, `e2_umgedrehter_koerper.py`, `e3_verrundung_fuellung.py`, `e4_oberseite.py`, `e4_zapfen_mantel.py`, `e6_kantenteilung.py`, `e8_ring_schweissen.py`, `e11_durchdringungsdauer.py` | Einzelsonden zu B1, B2, B3, B4, B6, B8, B11 |
| `e_offenes_kundennetz.py`, `e_besenhalter_wiederholbarkeit.py` | offener Kundenkörper roh/Import/Reparatur; Wiederholbarkeit der Reparatur (dreimal bitgleich) |
| `nachmessung_2217.txt`, `nachmessung_2219.txt` | Statusmessung aller Befunde am Endstand |

Die übrigen Dateien im Ordner (`s*.py`, `umbau_*.py`, `repair_stand_*.py` u. a.) stammen aus einer anderen Sitzung und sind hier nicht bewertet.
