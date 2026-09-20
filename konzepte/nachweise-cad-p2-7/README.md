# P2.7 — Bausteine auf dem exakten Kern: Machbarkeitsnachweise und Übergabe

> **Stand 20.09.2026, Ausgangscommit `5e31809c1`** (main; beim Lesen lag der
> ungestagete Zwischenstand der Hauptaufgabe P1.3/P1.6 im Baum, beim
> Abschluss war er als `912789f7e`, `5d451fe74`, `1cf405496` committet —
> die Sonden wurden zuletzt am Stand `1cf405496` gefahren, siehe `laeufe.txt`).
> Dieser Ordner ist der alleinige Schreibbereich der parallelen Aufgabe zu
> [RM-188](../../ROADMAP.md#rm-188) / Konzept
> [§13.2 P2.7](../konzept-vollwertiges-cad-2026-09.md). Er enthält den
> Bericht, ausführbare Sonden und ihre Ausgaben. **Er behauptet keinen
> integrierten Kundenweg und keine Fertigmeldung für P2.7:** Die Sonden
> belegen die geprüften Bauwege des exakten Kerns; Produktionsanschluss,
> Registerstände und Statuspflege bleiben bei der Hauptaufgabe.
>
> Prüfregel: nur funktionale Kernsonden und statische Prüfungen. Keine
> Fensterdateien, keine Leistungsprüfung, keine Bilder, kein Paketbau. Die
> in den Ausgaben stehenden Dauerangaben sind Beobachtungen ohne Budget.

## 1. Ergebnis in fünf Sätzen

1. **Die Konzeptangabe „35 Bausteine / 31 konvertierende Pfade“ ist am Code
   halb richtig.** 35 Bausteine stimmen. Konvertierend sind aber **alle 35
   `insert_*`-Pfade** — die vier „angehaltenen“ der Stichprobe vom 19.09.
   (Klemmschale, Einlage, Dichtnut, Dichtung) hielten nur an ihrem
   Pflicht-Skizzenparameter an; mit gezeichneter Sitzkontur bzw. Dichtweg
   werden auch sie ein Netz. Dazu kommen **10 `create_*`-Pfade** der
   eigenständigen Bausteine, die von vornherein ein Netz erzeugen. **Die
   vollständige Matrix hat 45 Bausteinpfade**, nicht 31 (§2).
2. **Jede Form, die ein Baustein heute baut, entsteht mit dem vorhandenen
   exakten Satz** (`brep.edit`, `brep.profiles`, `sketch.profile.Profile`):
   Quader, Zylinder, Sechskant, Langloch, Keil, Kegelstumpf, Drehprofil,
   Nutenstein, gerundetes Rechteck, Gewindebolzen. Zwei Dinge fehlen im
   Produktionskern und sind als Sonde belegt: der **Normalversatz einer
   Skizzenkontur** (`BRepOffsetAPI_MakeOffset`, für Klemmen und Dichtungen)
   und der **Gewindegang mit dem Gangprofil des Netzwegs** (Helix-Sweep wie
   `threaded_rod`, aber mit dem Vierpunktprofil aus `shapes.thread_body`).
   Keine neue Abhängigkeit, keine Bibliothekslücke.
3. **Der Einsetzweg ist am exakten Träger nachgestellt:** dieselbe
   `_anchor`/`_matrix`-Lage wie im Netzweg, das exakte Werkzeug über
   `edit.transformed`, dann `edit.boolean`. Ergebnis gültig, geschlossen,
   ein Körper, STEP-Rundreise; `features_of` liest die aufgeweitete Bohrung
   und die Fase; der Kundenweg aus Konzept §5.1 bleibt bis Schritt 6 exakt.
4. **Der Netzweg unterscheidet sich vom exakten Weg fast überall nur durch
   Facettierung** — Volumen 48-Eck/Kreis = 0,997147, gemessen auf sechs
   Stellen an jedem Zylinderbaustein. **Drei echte Form-/Maßunterschiede**
   sind benannt (§5): das Gangprofil des vorhandenen `threaded_rod`,
   die Facettenkorrektur der Wand an Scharnierauge und Kabelclip (entfällt
   exakt) und die Rundungssehne der Kugel-Dichtschnur.
5. **Vier Befunde für die Integration** (§6): die Vereinigung Kern + Gang
   verschluckt den Gang ohne Fuzzy-Toleranz **still** (gültig, ein Körper,
   Volumen = Kern); Kegelkopf + Gewinde ergeben mit 0,01 mm Überlappung zwei
   Körper, mit Fuzzy einen — der aber **aus STEP ungültig zurückkommt**, weshalb
   der Senkkopf als Compound aus Kopf und Bolzen bleibt; Fuzzy-Stufen müssen
   auf **privaten Kopien** laufen, sonst reißt der Prozess (Exit 139, 3/3);
   und nach einem exakten Schnitt dürfen die Merkmale des Trägers nicht neu
   erkannt, sondern müssen wie in `_insert_at` fortgeführt werden — sonst
   trifft das zweite Ziel die falsche Bohrung.

## 2. Register und Pfade (S1, S2)

Gemessen über `bootstrap.load_operations()` am Stand oben
(`s1_register.py`, `s1.out`; Schemata in `s2_schemas.py`, `s2.out`):

| Zahl | Gemessen | Konzept |
|---|---|---|
| Bausteine (`PARTS`), `LIBRARY_VERSION` | **35**, Version 19 | 35 |
| Gruppen | calibration 3 · fasteners 6 · mechanics 8 · mounting 7 · routing 2 · structure 9 | 6 Gruppen |
| Operationen der Kategorie `parts` | **48** = 35 `insert_*` + 10 `create_*` (Bausteine) + `create_lid`, `screw_lid` (`geom/lid.py`), `replace_profile_liners` (`geom/profile_clamp_ops.py`) | 48 |
| konvertierende `insert_*`-Pfade am exakten Träger | **35 von 35** | 31 |
| netzerzeugende `create_*`-Pfade | **10 von 10** | nicht gezählt |
| angehalten | `create_lid`, `screw_lid` (massiver Körper — keine Bausteine) | 4 Bausteine |

Die vier in der Durchsicht angehaltenen Bausteine brauchen als Pflichtwert
eine gezeichnete Kontur (`seat_sketch`, `counter_sketch`, `path_sketch`;
`required=True` trotz Vorgabe). Mit `sketch_to_text(shapes.circle(20.25))`
bzw. `shapes.rectangle(20, 12)` laufen sie durch und konvertieren wie alle
anderen. Der Konvertierungspunkt ist für alle derselbe:
`parts/ops._insert_at` ruft `as_mesh_data(source.mesh)` (Zeile 789) und
`as_mesh_data(produced.mesh)` (Zeile 771); die Erzeuger `_register_creator`
ebenso (Zeile 490). **Ein Baustein liefert heute ausschließlich `MeshData`**
(`PartFn -> PartResult`, `build.result`), und `build.union`/`subtract`
rechnen über `geom.boolean` am Netz.

Die einzige Bausteinabhängigkeit vom Materialprofil sind `play` und `grip`
(`ops._part_values`: `profile.material.clearance`, `abs(profile.material.press)`)
— Werte, keine Geometrie; sie gelten für beide Bauarten unverändert.
Filamente hängen nicht am Baustein: `_concatenated_with_slots` und die
Slot-Übernahme laufen nach dem Bau (P2.2 hat native Slots je Fläche;
für einen exakten Baustein gilt `carried_face_slots` des Builders).

## 3. Sonden und Ausgaben

Alle Sonden liegen hier, laufen einzeln mit `.venv\Scripts\python.exe
konzepte/nachweise-cad-p2-7/<sonde>.py` und beenden mit dem echten
Exitcode (0 nur, wenn jede Zusicherung hielt). `run_all.sh` fährt alle und
schreibt `laeufe.txt`; der letzte vollständige Lauf: Stand `1cf405496`,
2026-09-20 09:00 UTC, **568 Zusicherungen in sieben messenden Sonden, alle
elf Prozesse Exit 0** (die Auskunftssonden S1, S2, S3b, S8b zählen keine
Zusicherungen). `_iso.py` biegt die Nutzerverzeichnisse um (§38),
`_probe.py` ist die gemeinsame Bibliothek: exakte Formen über die
vorhandene API, Messen am Körper (`BRepCheck_Analyzer`, Körperzahl,
Flächenarten, Kernintegrale, Punkt-im-Körper, STEP-Rundreise).

| Sonde | Was sie belegt | Zusicherungen | Exit |
|---|---|---|---|
| `s0_smoke.py` | jede Form der Bibliothek gegen Analytik: Quader, Zylinder, Sechskant, Langloch (zwei echte Bögen), Keil, Kegel, Nutenstein, gerundetes Rechteck, Boolesche, Drehung, Punkttest, STEP | 49 | 0 |
| `s1_register.py` | Register, Gruppen, Flags, Merkmale, Bauart je Pfad am exakten Träger | Zählung (kein Exitcode-Vertrag) | 0 |
| `s2_schemas.py` | je Baustein Parameter mit Grenzen/Einheiten/Wahl, Normteilbezüge, Bauhelfer, private Helfer | Auskunft | 0 |
| `s3_fasteners.py` | Verbindungen: Schraubenloch, Buchse, Mutternfalle (seitlich/unten), Gewinde außen/innen, Netzprofil-Gang exakt, Schraube (Sechskant/Senkkopf + `host_cut`, Compound), Mutter | 96 | 0 |
| `s3b_thread_debug.py` | Gegenfälle: Senkkopf-Fuzzy-Stufen mit STEP-Rundreise, ShapeFix, Compound; Kern + Gang je Fuzzy-Stufe auf privaten Kopien; Vereinigung ohne Fuzzy verschluckt den Gang | Auskunft | 0 (`s3b.lauf1-3.out`: 139 ohne private Kopien) |
| `s4_mechanics.py` | Mechanik: Bolzenscharnier (2 Körper, Spalt), Lagersitz, Passstift rund/hex/Schwalbenschwanz + Bohrung, Scharnierauge, Rastnase (Nase/Aussparung, Sperrflächenlage gegen Netz), Filmscharnier, Schnappverbinder (Arm/Tasche, Rastkante an der Mündung), Schnappverbindung | 110 | 0 |
| `s5_mounting.py` | Befestigung: Fuß/Tasche (Drehprofil), Schlüsselloch (Rückhaltekante), Magnettasche (Lippe enger als Tasche), Wandhalter, Lochwand-Einhänger (2 Körper, Nase hinter der Platte, Zunge), Klemmschale und Einlage über Konturversatz | 86 | 0 |
| `s6_structure.py` | Struktur/Kabel: Kabelclip, Kabeldurchführung mit `host_add` am Träger, Eckwinkel, Rippe, Nutfeder, vier Organizer-Teile, Dichtnut, Dichtung rechteckig/rund/Kreisweg (Torus) | 122 | 0 |
| `s7_calibration.py` | Toleranzleiter (2 Körper, Bohrungs-Ø je Stufe, Strichcodes), Wandleiter (dünnste Wand = Extrusionsbreite), Überhangfächer (Rampenwinkel) | 41 | 0 |
| `s8_insertion.py` | Einsetzweg am exakten Träger, Gegenfälle 3a–3f, Kundenweg §5.1 | 64 | 0 |
| `s8b_anchor_debug.py` | Trägerbohrung Ø5,2 (kompensiert), Ankerlage, Werkzeugtiefe | Auskunft | 0 |

Rote Vorläufe sind in dieser Übergabe absichtlich nicht wegformatiert: Jede
Korrektur betraf einen **falschen Erwartungswert der Sonde** (Analytik mit
vergessener Überlappung, Messpunkt an der Sechskantecke statt Flachseite,
Bisektion, die an einer Leiter die falsche Wand fand, Bohrung im Träger
Ø5,2 statt Ø5) oder eine **zu strenge Toleranz an einer belegten
Näherung** (NURBS-Hülle der Bounds, Sweep-Approximation). Kein Produktweg
wurde gelockert, keine Zusicherung gegen den Kern abgeschwächt.

## 4. Übergabematrix je Baustein

Spalten: Pfad · heutige Form (Bauhelfer aus `s2.out`) · Normteile ·
versprochene Merkmale · exakter Bauweg (vorhandene API / Eigenentwicklung)
· geprüfte Fälle (Sonde) · verbleibende Lücke. Der Konvertierungspunkt ist
für alle `_insert_at` bzw. `_register_creator` (§2); die Integrationsdateien
stehen in §7.

### 4.1 Verbindungen (`fasteners.py`)

| Baustein / Pfad | heute | Normteile | Merkmale | exakt | geprüft | Lücke |
|---|---|---|---|---|---|---|
| `screw_hole` / insert | cylinder + cone + cylinder, union | `screw`, `washer` | bore_1, countersink_1, washer_1, head_room_1 | `edit.cylinder`, `profiles.revolve` (Kegel), `edit.boolean` | M4, Tiefe 10, Senkung, Kopftiefe 2: Volumen gegen Analytik auf 1e-6, Ø je Zone bei z=-8/-1/Senkmitte, Werkzeug unter der Mündung, Bounds = Netz, Netz/exakt 0,997147, STEP (S3) | keine |
| `heatset_m4` / insert | cylinder + cone | `insert` | bore_1, chamfer_1 | wie oben | M4: Ø unten = Bohrung, Fase weitet an der Mündung, Netz/exakt = Facettierung, STEP (S3); am Träger, geneigt 30°, zwei Ziele, Kundenweg (S8) | keine |
| `nut_trap` / insert | hexagon + box + cylinder, turned | `nut`, `screw` | pocket_1, bore_1 | `Profile`-Sechskant → `profiles.extrude`, `edit.box`, `edit.cylinder`, `edit.transformed` | M4 seitlich und unten: Schlüsselweite in X, Umkreis in Y, Bounds = Netz beide Lagen, STEP (S3) | keine |
| `printed_thread` / insert außen | `thread_body` (von Hand vernähter Gang) + Kern, Intersect | `screw` | thread_1 | **a)** `profiles.threaded_rod` (vorhanden; Gangprofil 0,6134 p, Fuß 0,75 p) **b)** Prototyp `_probe.thread_ridge_exact` (Gangprofil des Netzwegs 0,55 p, Fuß 0,8 p, flacher Kamm; MakePipeShell + Fuzzy-Stufen) | M6 x 12: a) Gang-Ø 6,000 über den Umfang, Kern Ø 4,773 (Netz 4,900), Volumen Netz/exakt 1,125 = **Formunterschied**; b) Kern 4,92 wie Netz (+2·Überlappung), Gang 6,000, Netz/exakt 0,9905 (Kern und Gang facettiert), STEP (S3) | **Entscheidung Gangprofil** (§5.1); Dauer 19–25 s je Bolzen (Beobachtung) |
| `printed_thread` / insert innen | Kern (Ø Kern + Spiel) + Gang nach außen, unter der Mündung | `screw` | thread_1 (internal) | Bolzen mit `nominal + play` als Werkzeug unter der Mündung (`threaded_rod`-Docstring: „eine Differenz mit Spiel ergibt das Innengewinde“) | M6 x 8, Spiel 0,2: Werkzeug-Gang-Ø 6,200, unter der Mündung, Block minus Werkzeug gültig, STEP (S3) | wie außen |
| `printed_screw` / insert (`separate_from_host`, `host_cut`) | hexagon oder cone + Bolzen | `screw` | thread_1, countersink_1 (host_cut) | Sechskantkopf + `threaded_rod` vereinigt; **Senkkopf als Compound** aus Kegel und Bolzen (zwei Solids, tangierend) | M5 Sechskant: Kopf oben, Gewinde unten, Höhe = Netz, STEP; Senkkopf: **0,01 Überlappung → 2 Körper (B2)**, Fuzzy 1e-4/1e-3/1e-2 → 1 Körper, aber **STEP-Rundreise ungültig**, auch mit ShapeFix (s3b); Compound Kopf + Bolzen: gültig, STEP gültig; host_cut-Senkung = Facettierung (S3); Compound Träger + Schraube, 2 Körper, STEP (S8 3f) | Senkkopf ist exakt nur als Zweikörper-Compound STEP-fähig; ein Körper verlangt eine andere Kopfkonstruktion (Kegelfuß nicht tangential zum Gang) — Entscheidung (§5.1) |
| `printed_nut` / insert (`separate_from_host`) | hexagon − Innengewindewerkzeug | `screw`, `nut` | thread_1 (internal) | `Profile`-Sechskant − `threaded_rod(nominal + play)` | M5, Spiel 0,2: Höhe = Normhöhe, Achse frei, STEP (S3) | wie Gewinde |

### 4.2 Mechanik (`mechanics.py`)

| Baustein / Pfad | heute | Normteile | Merkmale | exakt | geprüft | Lücke |
|---|---|---|---|---|---|---|
| `barrel_hinge` / insert (`bodies=2`) | liegende Zylinder + Boxen, Bohrung mit Spalt | — | hinge_1 (Achse X) | `edit.cylinder` + `edit.transformed` (90° um Y), `edit.box`, Boolesche | Bolzen 4, Breite 24, Spiel 0,3: **2 Körper** exakt wie Netz, radialer und axialer Spalt Luft, Bolzen Material, Wand über der Bohrung = wall, Netz/exakt 0,9993, STEP (S4) | keine |
| `bearing_seat` / insert | cylinder | `bearing` | seat_1 | `edit.cylinder` | 608 fest, Übermaß 0,1: Sitz-Ø = außen − Übermaß, unter der Mündung, Facettierung 0,997147 auf 1e-6 (S4) | keine |
| `dowel` / insert pin (rund/hex/dovetail) | cylinder / hexagon / gerundeter Schwalbenschwanz (Bogen + Sehne), Fasenring = cylinder − cone | — | pin_1 | `edit.cylinder`, Sechskant-`Profile`, `Profile` aus Bogen + Strecke, Fasenring über `profiles.revolve` | Ø6, Länge 8, Fase 0,6: steht auf der Fläche, Umkreis ≤ Ø, Fase verengt auf min(Apothem, r − Fase), STEP je Form (S4) | keine |
| `dowel` / insert bore | cylinder unter der Mündung + Einführkegel | — | bore_1 | wie oben | Ø = Nenn + Spiel, Fase weitet, Facettierung (S4) | keine |
| `hinge_eye` / insert | liegender Zylinder + Box − Bohrung; **Außen-Ø mit Facettenkorrektur** `wall / inscribed_ratio` | — | eye_1 (Achse X) | wie barrel_hinge, **ohne Korrektur** | Stift 3, Wand 2: Wand hinter der Bohrung genau 2,000 exakt; Netz 2,0043 (S4) | Korrektur beim exakten Weg entfernen (§5.2) |
| `latch` / insert (Nase/Aussparung) | wedge, 180° um X gedreht | — | ramp_1 | `_probe.wedge` (Polygon in YZ, `plane:yz` extrudiert) + `edit.transformed` | 6 x 1 x 3, Spiel 0,2: Volumen exakt, Sperrfläche/Schräge liegen wie im Netz (Punktproben Netz = exakt; volle Tiefe oben bei z = Höhe), Netz = exakt (S4) | keine |
| `living_hinge` / insert (`lies_flat`) | box − box | — | hinge_1 | `edit.box`, Boolesche | 30/15/2/0,4/1,5: Volumen, Film unten (0..0,4), Netz = exakt (S4) | keine |
| `snap_connector` / insert pin | box + wedge | — | arm_1, hook_1 | `edit.box`, `_probe.wedge` | Ø6, Länge 9: Haken sitzt ab z = catch, Bounds und Volumen = Netz (S4) | keine |
| `snap_connector` / insert bore | box − Lippe (Rastkante) unter der Mündung | — | catch_1 | Boolesche | Rastkante zwischen Mündung und Haken leer, darunter voll, Netz = exakt (S4) | keine |
| `snap_fit` / insert | ein extrudierter Seitenriss (trimesh direkt) | — | arm_1, hook_1 | `profiles.extrude(Profile, plane:yz)` | 8/16/1,6/1,2/35°: Volumen, Haltefläche oben, Bounds und Volumen = Netz, STEP (S4) | keine |

### 4.3 Befestigung (`mounting.py`, `profile_clamps.py`)

| Baustein / Pfad | heute | Normteile | Merkmale | exakt | geprüft | Lücke |
|---|---|---|---|---|---|---|
| `foot` / insert (Fuß) | `lathe.revolve` Drehprofil | — | foot_1 (face oben) | `profiles.revolve(Profile)` | Ø10 h3: Kegelfläche am Standende, Säule Ø am Teil, Facettierung, STEP (S5) | keine |
| `foot` / insert (Tasche) | Drehprofil unter der Mündung | — | foot_1 (bore) | wie oben | Sitz voller Ø, Schräge weitet die Mündung, Facettierung (S5) | keine |
| `keyhole` / insert (`keeps_up`) | cylinder + 2 Langlöcher (slot, 90° gedreht) | `screw` | pocket_1, bore_1 | `edit.cylinder`, `_probe.slot` (zwei echte Bögen) + `edit.transformed` | M4, Weg 8, Tiefe 4, Kopftiefe 2,5: Schlitz in −Y, Kopfkanal unten offen, **Rückhaltekante über dem Kanal**, Einstieg kopfbreit, Facettierung, STEP (S5) | keine |
| `magnet_pocket` / insert | cylinder + Lippe (cone) + Haut | `magnet` | pocket_1 | `edit.cylinder`, `profiles.revolve` (Kegel) | 8x3, Spiel 0,2, Übermaß 0,15: Öffnung = Magnet − Übermaß, Tasche = Magnet + Spiel, enger als Tasche, STEP (S5) | keine |
| `pegboard_hook` / insert (`joined_by_host`, `keeps_up`) | slot × 2 + box × 2 + wedge je Haken | `board` | hook_n, latch_n | `_probe.slot`, `edit.box`, `_probe.wedge`, `edit.transformed` | skadis, 2 Haken, Zunge: **2 Körper** wie Netz, Nase hinter der Platte, Zapfen in −Y, Zylinderflächen, Bounds = Netz bis auf Sag der Langlochenden (0,0056), Facettierung, STEP (S5) | keine |
| `wall_mount` / insert | box + box − Zylinder (Achse Y) | `screw` | plate_1, bore_n (Achse Y) | `edit.box`, `edit.cylinder` + `edit.transformed` | 30x25x3, M4, 2 Löcher: zwei Zylinderflächen, Loch geht durch, Volumen Analytik, STEP (S5) | keine |
| `profile_clamp_shell` / insert + create (`standalone`) | Manifold-CrossSection: `section_of` (facettiert), `offset_section`, Halbierung, Ohren, extrude; Schraubenloch + Kopf-/Mutterntasche | `screw`, `nut` | front, back | **`BRepOffsetAPI_MakeOffset` auf der `Profile`-Fläche** (`_probe.offset_face`), `BRepPrimAPI_MakePrism`, Boolesche für Ohren, Halbierung als Schnitt mit Halbraumbox, Normteilaufnahmen als Zylinder/Sechskant | Kreis Ø20,25, Wand 4, Tiefe 40, untere Hälfte, M4: Offset bleibt exakter Zylinder (Ø 28,25), Hälfte endet bei y = −0,5, Loch durchs Ohr, Kopftasche unten, Netz/exakt 1,00004 (Sitz nach `CONTOUR_SAG` facettiert, Löcher 48-Eck), Bounds Netz = exakt (0,02), STEP (S5) | Offset-Helfer gehört nach `brep/profiles.py`; Ohren-Kontur und `_monotone`-Montageprüfung bleiben 2D (Shapely) — auf der `Profile`-Ebene nachzuziehen |
| `profile_clamp_liner` / insert + create | Gegenkontur − Übermaß, Außenkontur = Offset, Bund, Freiraum hinten | — | front, back | wie Schale | Ø20, Stärke 2, Bund 1,2/1,5, hinten 2, Übermaß 0,1: Bund vorn breiter als Kern, Freiraum hinten (Länge 39,5), Netz/exakt 0,99973, STEP (S5) | wie Schale |

### 4.4 Kabel und Struktur (`structure.py`, `containers.py`, `seals.py`)

| Baustein / Pfad | heute | Normteile | Merkmale | exakt | geprüft | Lücke |
|---|---|---|---|---|---|---|
| `cable_clip` / insert | liegende Zylinder (Ring) − Öffnung + Sockel; **Außen-Ø mit Facettenkorrektur** | `tube` | seat_1 | `edit.cylinder` + `edit.transformed`, `edit.box`, Boolesche, ohne Korrektur | cable-5, Wand 2: Bügelwand seitlich genau 2 (Luft bis inner/2, Material bis outer/2), Öffnung = Ø − 2·Verengung, Netz um 0,0043 breiter (Korrektur), STEP (S6) | Korrektur entfernen (§5.2) |
| `cable_gland` / insert (`host_add`) | cylinder + box; `host_add` box hinter der Wand | `tube` | bore_1, relief_1 | `edit.cylinder`, `edit.box`; **Aufbau + Träger, dann Werkzeug** (die Reihenfolge von `_insert_at`) | cable-5, Wand 3: Loch durch die Wand, Klemmspalt 0,8·Ø, host_add = Quader, am Träger Volumen gegen Analytik 1e-6 (inkl. Überlappungsanteil), Kabelweg frei, STEP (S6) | keine |
| `gusset` / insert | wedge | — | gusset_1 | `_probe.wedge` | Schenkel 12: t·l²/2, Netz = exakt (S6) | keine |
| `rib` / insert | box + 2 wedge | — | rib_1 | `edit.box`, `_probe.wedge`, `edit.transformed` | 20x10, Anlauf 2: Volumen, Netz = exakt, STEP (S6) | keine |
| `profile_tongue` / insert | box + tapered_bar | `profile_slot` | tongue_1 | `edit.box`, Nutenstein-`Profile` | 2020, Länge 20, Schräge 1,5: Hals = Nut − Spiel, Kopf = Kern − Spiel, Enden laufen zu, Netz = exakt, STEP (S6) | keine |
| `organizer_tray` / insert + create | `rounded_prism` (Manifold, Ecken nach `MAX_FACET_SAG`) − Innenraum | — | base, floor, rim (`facets`-Quellen) | `Profile` mit vier **exakten Viertelkreisen** → `profiles.extrude`, Boolesche | 120x80x40, Wand 3, R8: Volumen Analytik 1e-6, acht Zylinderflächen, Außenmaße exakt, Netz/exakt 0,9997 (Ecken), STEP (S6) | Merkmale `base/floor/rim` messen heute Dreiecke (`_horizontal_area`) — exakt aus Flächenintegralen |
| `organizer_divider` / insert + create | box | — | base, top, front, back | `edit.box` | Netz = exakt (S6) | wie oben |
| `organizer_rim` / insert + create | rounded_prism − rounded_prism, verschoben auf Material | — | rim | wie tray | Volumen Analytik, Bounds = Netz (S6) | wie oben |
| `organizer_foot` / insert + create (`not_at_face`) | cylinder + cylinder | — | base, seat, pin | `edit.cylinder` | Volumen, Zapfen-Ø, Facettierung genau 0,997147 (S6) | wie oben |
| `seal_groove` / insert | `geom.seal.seal_geometry`: `section_of` (facettiert), `offset_section` ±w/2 (Band), extrude | — | groove_mouth/floor/walls (`facets`) | **Band = Offset(+w/2) − Offset(−w/2)** über `_probe.offset_face`, Prisma unter der Mündung | Rechteckweg 20x12, Nut 3x2: unter der Mündung, Ecken außen Kreisbögen (4 Zylinderflächen), Volumen Analytik (außen gerundet, innen scharf) 1e-6, Nutbreite symmetrisch, Netz/exakt 0,9998, STEP (S6) | Offset-Helfer (wie Klemmen); `seal_features` ordnet Dreiecke nach Normalen — exakt nach Flächen |
| `seal_gasket` / insert + create rechteckig (`separate_from_host`) | Band, um Höhe angehoben | — | gasket_contact/bottom/walls | wie Nut | 2,6 x 2,4: steht auf der Fläche, Netz/exakt 0,9998, STEP (S6) | wie Nut |
| `seal_gasket` / rund | `_round_tube`: Kapselkette aus Kugelhüllen (Manifold) | — | gasket_contact/bottom (`curved_face`) | **Kapselkette exakt**: je Strecke `BRepPrimAPI_MakeCylinder`, je Ecke `MakeSphere`, Vereinigung (`_probe.capsule_chain`); Kreisweg → `BRepPrimAPI_MakeTorus` | Rechteckweg Ø2,4: 4 Zylinder + 4 Kugeln, Volumen Analytik 1e-6 (Steinmetz-Viertel und Viertelkugel je Ecke), Netz/exakt 0,9933; Kreisweg Ø20: **eine Torusfläche**, 2π²Rr² auf 1e-6, größter Netzabstand 0,0055 ≤ Bahn-Sag + Kugel-Sag, Netz/exakt 0,9882 (zweifache Facettierung), STEP (S6) | Bögen im Weg brauchen Torusstücke (Kreisweg belegt; Teilbögen nicht gemessen) |

### 4.5 Kalibrierung (`testbodies.py`, alle `standalone`, `not_at_face`)

| Baustein / Pfad | heute | Merkmale | exakt | geprüft | Lücke |
|---|---|---|---|---|---|
| `fit_ladder` / insert + create (`bodies=2`) | 2 Boxen + Zylinder − Bohrungen − Strichcode-Boxen | pin_n, bore_n, face_1 | `edit.box`, `edit.cylinder`, Boolesche | Ø6, 4 Stufen: 2 Körper wie Netz, Bohrungs-Ø je Stufe auf 1e-6 (6,10/6,15/6,20/6,25), Zapfen stehen, Strichcodes graviert, Bounds = Netz, Netz/exakt (S7) | keine |
| `wall_ladder` / insert + create | Boxen | face_1 | `edit.box` | 0,42 x 6: Volumen, Netz = exakt, dünnste Wand = 0,420 (S7) | keine |
| `overhang_fan` / insert + create | box + `_ramp` (trimesh von Hand) | face_1 | `profiles.extrude(Profile, plane:yz)` je Rampe | 20°+10°x6: Volumen, Netz = exakt, letzte Rampe auf der Winkelgeraden, STEP (S7) | keine |

## 5. Erlaubte Facettierung und echte Unterschiede

**Erlaubt (Repräsentation, keine Form):**

| Unterschied | Maß | Wo |
|---|---|---|
| 48-Eck im Umkreis gegen Kreis | Volumen ×0,997147 (`polygon_ratio(48)`), Bounds gleich (Ecken auf dem Umkreis) | jeder Zylinder, Kegel, Sitz; auf 1e-6 bestätigt an `bearing_seat`, `organizer_foot` |
| Langlochenden aus 24 Punkten ohne Punkt auf der Achse | Extremum um r·(1 − cos π/46) innerhalb (0,0056 bei r = 2,4) | `pegboard_hook`, `keyhole` |
| Organizer-Ecken nach `MAX_FACET_SAG` | Volumen ×0,9997 | `organizer_*` |
| Kugel-Sweep: Bahn nach `_SEAL_SAG`, Kugeln nach Winkel/Sag | Volumen ×0,988–0,993; Netzabstand ≤ 0,0055 | `seal_gasket` rund |
| BSpline-Hülle der Bounds (`AddOptimal`) | +1e-5 je Seite, kein Formmaß; Sweep-Approximation ≤ 1e-4 am Radius; STEP-Rundreise ±1e-5 relativ | Gewinde |

**Echte Form- oder Maßunterschiede (Entscheidungen, keine Toleranzen):**

1. **Gangprofil.** `profiles.threaded_rod` baut 0,6134 p tief mit 0,75 p Fuß
   und spitzem Kamm (ISO-nah); `shapes.thread_body` baut 0,55 p tief, 0,8 p
   Fuß, Kamm flach zwischen 0,25 p und 0,55 p. M6 x 12: Kern Ø 4,773 gegen
   4,900, Volumen 253,4 gegen 285,1 mm³ (×1,125). **Beides ist exakt
   baubar** (S3). Die Wahl entscheidet, ob alte Netzprojekte und neue exakte
   Bausteine dasselbe Gewinde tragen (Zusammenschraubbarkeit über die
   Bibliotheksversion) — sie gehört zu Robert, nicht in eine Toleranz.
   Empfehlung: das Netzprofil exakt nachbauen (Prototyp
   `thread_ridge_exact`), `threaded_rod` als Erzeuger *Gewindebolzen*
   unverändert lassen; sonst ändert P2.7 ein Maß und verlangt
   `LIBRARY_VERSION` + Änderungsverlauf (§24.4).
2. **Facettenkorrektur der Wand** (`hinge_eye`: `wall / inscribed_ratio`,
   `cable_clip`: `wall / cos(π/48)` + Float32-Reserve). Sie gleicht die
   Apothem-Verkürzung des 48-Ecks aus und macht den Netz-Außendurchmesser
   um 0,0043 mm größer. Exakt ist die Wand ohne Korrektur genau `wall`
   (gemessen 2,000). Beim exakten Weg entfällt sie; der Netzweg behält sie.
   Ein Vergleich Netz gegen exakt an diesen zwei Bausteinen muss das wissen.
3. **Provenienz- gegen natives Merkmal nach einem Schnitt.** Die
   Buchsenbohrung `heatset_m4_bore_1` (aus Parametern, Mitte der ganzen
   Werkzeugtiefe 8,6) und die vom exakten Kern gelesene Zylinderfläche
   (Ø5,6, axial 8,1, ohne Fase) haben dieselbe Achse und einen Mittenversatz
   von genau `INSERT_LEAD_IN / 2` (S8). Kein Fehler — dieselbe Semantik wie
   am Netz (`measure_sources = parameter`) —, aber die Integration muss wie
   heute beide führen oder eine Regel nennen (P1.5-Vertrag).

## 6. Befunde und Gegenfälle für die Integration

| Nr. | Befund | Gemessen | Folge |
|---|---|---|---|
| B1 | **Kern + Gang ohne Fuzzy-Toleranz: der Gang verschwindet still.** Vereinigung gültig, ein Körper, geschlossen — Volumen = Kern (228,14 statt 287,88) | `s3b.out`: tol None/1e-6/1e-4 → Gang Ø 4,92 (= Kern); tol 1e-3 → Gang Ø 6,000 | Jede Gewinde-Vereinigung braucht die Stufenleiter aus `ROD_FUZZ_RATIOS` **und eine Volumenuntergrenze** (Kern + Ganganteil). `_is_sound_rod` prüft nur Volumen > 0, geschlossen, ein Körper — den stillen Fall fängt es nicht. Hinweis an die Hauptaufgabe, kein Eingriff hier |
| B2 | **Kegelkopf + Gewindebolzen mit 0,01 mm Überlappung → zwei Körper**; der Netzweg verschmilzt dieselbe Lage. Fuzzy 1e-4/1e-3/1e-2 macht einen Körper (V 291,63, −0,05 %), **der aus STEP ungültig zurückkommt** — bei jeder Stufe, auch nach `ShapeFix_Shape`. Der Compound aus Kopf und Bolzen (zwei Solids, tangierend) ist gültig und STEP-fähig | `s3.out`, `s3b.out` Abschnitte 1, 1b, 1c | Der gedruckte Senkkopf bleibt exakt ein Zweikörper-Compound (er ist ohnehin `separate_from_host`); eine Einkörper-Lösung verlangt einen Kegelfuß, der die Gangspitzen nicht tangiert — eine Maßentscheidung, keine Toleranz |
| B2a | **Dieselben Eingaben mehrfach durch Fuzzy-Booleans**: bei der dritten Vereinigung reißt der Prozess (Exit 139), reproduzierbar 3 von 3; ebenso ein Punkttest auf der degenerierten Form aus B1 | `s3b.lauf1-3.out`; mit `copy_shape` je Stufe läuft dieselbe Folge durch (`s3b.out`) | Jede Stufe der Leiter auf privaten Kopien (`brep/CLAUDE.md` verlangt es für Fillet/Chamfer/ShapeFix bereits); `_joined_rod` reicht dieselben `core`/`ridge` an `_fuzzy_boolean` und `_sewn` weiter — prüfen, ob dort Kopien entstehen |
| B3 | **Merkmale nach dem Schnitt neu erkennen vergibt neue Namen**: `hole_1` wird die Ø5,6-Buchse, `hole_2` der Rest; das zweite Ziel trifft die erste Bohrung erneut | `s8.out` (erster Lauf): Abtrag 38,6 statt 63,0 mm³ | Wie `_insert_at`: `dict(source.features)` fortführen und die Provenienzmerkmale ergänzen; nicht `features_of` auf dem Ergebnis. Für exakte Körper wird das die Aufgabe des Zuordnungsvertrags (P1.4/P1.5) |
| B4 | Exakte Vereinigung bei **reiner Flächenberührung** gelingt (ein Körper, Volumen = Summe); der Netzweg braucht `BOOLEAN_OVERLAP` | `s8.out` 3a | Das Einsenken um 0,01 kann bleiben (schadet exakt nicht, Volumen −0,3 mm³); es ist keine Voraussetzung mehr |
| B5 | **Werkzeug genau so groß wie die Bohrung** (koinzidente Zylinderflächen): gültig, Volumen unverändert | `s8.out` 3b | `without_effect` greift wie am Netz (Volumenvergleich) |
| B6 | Werkzeug neben dem Körper: gültig, Volumen unverändert | 3c | wie B5 |
| B7 | Geneigte Fläche (30° um X): Bohrungsachse = Flächennormale, Abtrag = volle Buchse | 3d | `_matrix` gilt unverändert für `edit.transformed` |
| B8 | Zwei Ziele: doppelter Abtrag, zwei Ø5,6 erkannt (nach B3) | 3e | `insert`-Schleife bleibt |
| B9 | `separate_from_host`: Träger und Schraube als **Compound** (`BRep_Builder`), zwei Körper, Volumen = Summe, STEP-Rundreise | 3f | `_concatenated_with_slots` braucht ein exaktes Gegenstück (Compound); `Solid.solid_count` zählt bereits 2 |
| B10 | `bore.compensated`: `drill_brep_hole` Ø5 bohrt am PETG-Profil Ø5,2 | `s8b.out` | Sondenerwartungen aus dem Trägermerkmal ableiten; für P2.7 kein Befund |
| B11 | Kundenweg §5.1 (Quader, Bohrung, R3, Aushöhlen 2, Buchse, Senkung) bleibt exakt bis Schritt 6; Schritt 5 Netz/exakt 0,9995; STEP am Ende | `s8.out` 4 | Das Konzeptbeispiel ist mit dem exakten Weg vollständig |
| B12 | Dauer: `threaded_rod` M6 x 12 rund 22 s, Prototyp 16 s, M5 x 12 17 s; die Punktklassifikation über den Umfang eines Sweep-Bolzens (36 Winkel x 60 Bisektionsschritte) ist der langsamste Sondenschritt — spürbar, ohne Zeitstempel gemessen (Beobachtung, keine Messung mit Budget) | `s3.out`, `s3b.out` | Gewindebausteine sind die einzigen mit spürbarer Rechenzeit; alle anderen Sondenschritte liegen unter einer Sekunde. Bewertung gegen §31 gehört zum Release |

Kein Fall verlangte eine neue Abhängigkeit; alle Aufrufe liegen in der
festgeschriebenen OCP-Bindung (8.0.1). Geprüft, aber nicht gebraucht:
`BRepOffsetAPI_MakePipeShell` mit Rundungsmodus für die Dichtschnur — die
Kapselkette ist einfacher und deckt genau die Form des Netzwegs.

## 7. Integration: Dateien, Weg, Abnahme

**Kundenweg und Bezeichnungen bleiben.** Menü *Bausteine* → Katalog
(`ui/catalog.py`) → Dialog des Bausteins mit „An Merkmal“; Kontextmenü an
Fläche oder Bohrung (§18.5); Agent über `insert_<name>`. Die Operationen
heißen weiter `insert_<name>` / `create_<name>`; gespeicherte Schritte
bleiben lesbar. **Kein weiterer Kernwahl-Haken**: „Flächen und Kanten später
bearbeiten“ steht an vier Erzeugern (`MENU_TWINS`) und fällt mit P2.8. Der
Baustein entscheidet nach `SceneObject.kind` — dasselbe Muster wie
*Verrunden*/*Fase* in `geom/edge_ops.py` (Verzweigung nach Bauart, eine
Operation). Ein exakter Träger bekommt einen exakten Baustein; ein Netz
behält den heutigen Weg.

**Zwei Bauarten für die Bausteinfunktionen** (Architekturentscheidung,
Robert fragen):

| | A · zweite Funktion je Baustein | B · eine Formbeschreibung, zwei Auswerter |
|---|---|---|
| Idee | `PartSpec.fn_exact` liefert `PartResult` mit `Solid` (erfüllt das `Mesh`-Protokoll) | `shapes` beschreibt Formen (cylinder, box, hexagon, slot, wedge, cone, revolve, extrude, offset, capsule, union, subtract, moved, turned); `build` wertet je Bauart als `MeshData` oder `Solid` aus |
| Aufwand | 35 zweite Funktionen; sieben Bausteine bauen heute direkt mit trimesh/Manifold (`snap_fit`, `dowel` dovetail, `foot`, `organizer_*`, `profile_clamp_*`, `seal_*`, `overhang_fan`) | einmalige Umstellung von `shapes.py`/`build.py`; die sieben direkten Bauer werden auf die Beschreibung gezogen |
| Risiko | zwei Quellen je Maß — laufen auseinander (Regel aus `bausteine.md`) | Formbeschreibung muss Profile (Bögen) und Konturversatz tragen; Bereichstest läuft je Bauart |
| Empfehlung | — | **B.** Ein Baustein, ein Merkmalvertrag, ein Bereichstest; die Sonden hier sind faktisch der exakte Auswerter für jede vorkommende Form |

**Dateien, die die Integration anfasst** (Lesebefund; nichts davon ist hier geändert):

| Datei | Was |
|---|---|
| `app/core/knowledge/parts/shapes.py` | Formbeschreibung bzw. exakte Zwillinge jeder Form (§4: alle vorkommenden Formen sind über `edit`/`profiles`/`Profile` belegt) |
| `app/core/knowledge/parts/build.py` | `union`/`subtract`/`result` nach Bauart; Merkmale unverändert (`bore`, `pin`, `face`, `thread`) |
| `app/core/knowledge/parts/ops.py` | `_insert_at` und `_register_creator`: Verzweigung nach `kind`; `_place` → `edit.transformed(tool, _matrix(...))`; `_concatenated_with_slots` → Compound (B9); `without_effect`/`_hanging_loose` über `Solid.volume`/`solid_count`; Merkmale fortführen (B3) |
| `app/core/knowledge/parts/registry.py` | `PartSpec` um die exakte Fähigkeit; `LIBRARY_VERSION` nur, wenn ein Maß sich ändert (Gangprofil, §5.1) |
| `app/core/knowledge/parts/fasteners.py` | Gewinde: Gangprofil-Entscheidung; Senkkopf mit Fuzzy-Stufe (B2) |
| `app/core/knowledge/parts/mechanics.py`, `structure.py` | Facettenkorrektur nur am Netz (§5.2) |
| `app/core/knowledge/parts/containers.py`, `seals.py`, `profile_clamps.py`, `app/core/geom/seal.py`, `geom/profile_clamp_ops.py` | Konturversatz und Band exakt (`offset_face`/`band`); Kapselkette/Torus für die Schnur; `_features`/`seal_features` aus Flächen statt Dreiecksnormalen |
| `app/core/brep/profiles.py` | Konturversatz als öffentlicher Helfer; `threaded_rod` mit wählbarem Gangprofil oder zweiter Erzeuger |
| `app/core/brep/edit.py` | `boolean(..., tolerance=)` (B2) oder Stufenleiter; Compound-Bau |
| `app/core/knowledge/parts/range_check.py` | Bereichsprüfung am exakten Körper: `BRepCheck_Analyzer`, `solid_count`, Wand-/Spaltmessung über die Tessellierung |
| `app/core/knowledge/parts/preview.py`, `scad.py` | Vorschau aus der Tessellierung; SCAD unverändert (schreibt Datei) |
| `app/core/scene/evaluate.py` | `exact_became_mesh` entfällt für exakte Bausteinpfade |
| `tests/test_exact_body_parity.py` | **die Abnahme**: je Bausteinzeile `MESH` → `BREP` (`PART_CASES`, `STANDALONE`), 133 Operationen bleiben vollständig |
| `tests/test_parts.py`, `tests/test_brep.py`, `tests/test_geometry_review_regressions.py`, `tests/test_seal_parts.py`, `tests/test_profile_clamps.py`, `tests/test_organizer_build.py` | Sonden dieses Ordners als Regressionen: Volumen gegen Analytik, Funktionsmaße in Richtung, Körperzahl, STEP |
| `app/core/knowledge/parts/CLAUDE.md`, `.claude/rules/bausteine.md`, `app/core/brep/CLAUDE.md` | Karte und Regel: „gebaut gegen manifold3d“ wird „gebaut als Formbeschreibung, gerechnet je Bauart“ |
| `app/i18n/locales/*` | keine neuen Texte nötig, solange Titel und `doc` bleiben; ein neuer Befund (Fuzzy-Stufe) bräuchte einen Katalogeintrag |
| `konzepte/README.md`, `ROADMAP.md` (RM-188 P2.7) | Verweis auf diesen Ordner; Stand „läuft“ — durch die Hauptaufgabe |

**Abnahmekriterien je Teilpaket** (eine Bausteingruppe je Commit, Konzept §13.2):

1. `test_exact_body_parity.py`: jede `insert_*`/`create_*`-Zeile der Gruppe liefert `BREP` am exakten Träger und weiterhin `MESH` am Netzträger.
2. Je Baustein: nativ gültig (`BRepCheck_Analyzer`), geschlossen, erklärte Körperzahl (`bodies`, `joined_by_host`, `separate_from_host`), Volumen gegen unabhängige Analytik (Toleranz 1e-6 absolut oder 1e-9 relativ, keine gelockerten Tests), Funktionsmaße in Richtung (unter der Mündung, Rastkante/Sperrfläche/Lippe an der richtigen Seite), Provenienzmerkmale mit Achse/Mitte, STEP-Rundreise (Volumen, Flächenzahl).
3. Netz gegen exakt: Volumenverhältnis innerhalb des ausgewiesenen Facettierungsmaßes (§5), Bounds gleich bis auf den Sag; jeder darüber hinausgehende Unterschied ist benannt (Gangprofil, Facettenkorrektur).
4. Bereichstest der Gruppe von Hand am exakten Körper (`check_part`), wie es die Regel verlangt; Merkmalsversprechen (`feature_requirements`) grün.
5. Undo, Cache (`cache_version`), Wiederöffnung und Agentenweg unverändert; keine Konvertierungsmeldung mehr am exakten Träger.
6. Entwicklungstor vor dem Commit (`/pruefen`); Fenster und Leistung beim Release.

## 8. Gelesene Stände und Grenzen dieser Übergabe

Gelesen und gegen den Arbeitsbaum gehasht (`git hash-object`, 12 Zeichen);
vier Dateien tragen den ungestageten Zwischenstand der Hauptaufgabe und
wurden **so** gelesen, wie sie im Baum standen:

| Datei | Stand | |
|---|---|---|
| `app/core/knowledge/parts/registry.py` | `089379b6cdef` | |
| `app/core/knowledge/parts/ops.py` | `91d75952c131` | |
| `app/core/knowledge/parts/build.py` | `1250a704a0c5` | |
| `app/core/knowledge/parts/shapes.py` | `877d166f375b` | |
| `app/core/knowledge/parts/fasteners.py` | `d71892cb0e7e` | |
| `app/core/knowledge/parts/mechanics.py` | `84e3577c75c6` | |
| `app/core/knowledge/parts/mounting.py` | `4dcde2bbd193` | |
| `app/core/knowledge/parts/structure.py` | `4608a3f5c58a` | |
| `app/core/knowledge/parts/containers.py` | `05515382f6a5` | |
| `app/core/knowledge/parts/profile_clamps.py` | `07ff346b6f7b` | modifiziert (+9) |
| `app/core/knowledge/parts/seals.py` | `cc027d1a2d18` | modifiziert (+14/−7) |
| `app/core/knowledge/parts/testbodies.py` | `df889f1a19bd` | |
| `app/core/knowledge/standards.py`, `data/standards.toml` | `20648ea1e85b`, `448b264bbd2e` | |
| `app/core/geom/seal.py`, `geom/profile_clamp_ops.py` | `27c5a3001d77`, `f356a262122f` | |
| `app/core/brep/kernel.py`, `profiles.py`, `edit.py`, `ops.py`, `step.py` | `9e00e0179784`, `0db2881c4df4`, `5e48790d4e0f`, `dc09a4819746`, `02dffb83878b` | |
| `app/core/brep/features.py` | `be1a01948ba1` | modifiziert (+203) |
| `app/core/sketch/profile.py` | `5ab9f7c64433` | |
| `app/core/units.py` | `ccb1995bde95` | modifiziert (+27) |

**Nicht geprüft und nicht behauptet:** Fensterweg (Katalog, Dialog,
Kontextmenü), Leistung gegen §31, Undo/Cache/Wiederöffnung mit einem
exakten Bausteinergebnis (der Prototyp lebt in der Sonde, nicht im
Register), Bereichsläufe über alle Parameterecken, Teilbögen im Dichtweg,
installierte Plattformen. Die Sonden fahren je Baustein einen
charakteristischen Fall mit Normteil, Spiel und den Grenzen, die den Weg
entscheiden (Senkkopf, Rastkante, Lippe, Zunge, zwei Körper) — nicht das
kartesische Produkt der Grenzen.

**Tor und Commit.** Beim Abschluss war der Baum bis auf diesen Ordner sauber
(HEAD `1cf405496`, der Zwischenstand der Hauptaufgabe war committet). Das
Entwicklungstor für genau diesen Stand plus diesen Ordner: Kernsammlung
`suite-getrennt.sh` **12682 bestanden, 26 übersprungen, 0 Läufe mit Fehler,
Prozessausgang 0** (7:46 min, acht Arbeiter); `ruff check .` 0, `ruff format
--check .` 0 (1122 Dateien), `mypy` 0 (301 Dateien). Fensterdateien und
Leistung nicht gefahren — Release. Committet mit ausdrücklichem Pathspec
`konzepte/nachweise-cad-p2-7/`; die Dateien:

```
README.md                 dieser Bericht
pruefkoerper.md           Fälle, Parameter, Sollwerte je Sonde
_iso.py, _probe.py        Isolation und Sondenbibliothek
run_all.sh, laeufe.txt    Gesamtlauf und direkte Exitcodes
s0_smoke … s8b_anchor_debug (.py)   die elf Sonden
s0 … s8b (.out)           ihre Ausgaben vom Stand 1cf405496
s3b.lauf1-3.out           die drei Abrisse (Exit 139) vor der Kopienregel
```

`konzepte/` ist von Ruff nicht ausgenommen; mypy prüft nur `app/`. Der
Ordner schreibt nichts ins Projekt; `_iso.py` legt die Nutzerverzeichnisse
nach `%TEMP%/solidon-p27-iso`. `konzepte/README.md` und RM-188 verweisen
noch nicht hierher — das bleibt bei der gemeinsamen Statuspflege.
