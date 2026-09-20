# P2.5 — Gewinde an importierter B-Spline-Geometrie: Nachweise und Übergabe

> **Stand 20.09.2026, Ausgangscommit `d483e1477`** (main; die Sonden sind
> zuletzt am Stand `ee16040e7` gefahren, mit dem damals ungestageten
> Zwischenstand der Hauptaufgabe P1.4b im Baum. Beim Abschluss stand HEAD
> auf `c01f8ab23`; die gemessenen Module — `brep/profiles.threaded_rod`,
> `brep/features.py`, `brep/step.py`, `perceive/helix.py`,
> `perceive/features.py`, `scene/fits.py` — sind zwischen beiden Ständen
> unverändert, `git diff --stat` leer). Dieser Ordner ist der alleinige Schreibbereich der
> parallelen Aufgabe zu [RM-188](../../ROADMAP.md#rm-188) / Konzept
> [§13.2 P2.5](../konzept-vollwertiges-cad-2026-09.md). Er enthält den
> Bericht, den ausführbaren Prototyp, die Referenzkörper als STEP, die
> Sonden und ihre Ausgaben. **Er behauptet keinen integrierten Kundenweg
> und keine Fertigmeldung für P2.5:** Die Sonden belegen, dass die
> fachliche Auskunft eines Gewindes aus importierter Geometrie mit dem
> vorhandenen Werkzeugsatz messbar ist, und sie benennen die Grenzen.
> Produktionsanschluss, Registerstände und Statuspflege bleiben bei der
> Hauptaufgabe.
>
> Prüfregel: nur funktionale Kernsonden und statische Prüfungen (Ruff,
> Format für diesen Ordner). Keine Fensterdateien, keine Leistungsprüfung,
> keine Bilder, kein Paketbau, kein eigener vollständiger Torlauf — die
> Hauptaufgabe fährt ihr Tor parallel. Dauerangaben in den Ausgaben sind
> Beobachtungen ohne Budget, und sie sind unter Fremdlast gemessen.

## 1. Ergebnis in sechs Sätzen

1. **Heute weiß Solidon über ein importiertes Gewinde nichts Exaktes.**
   Der exakte Weg (`brep/features.py::features_of`) liest aus dem
   STEP-Bolzen elf Zapfen Ø 4,77 (die Kernstücke zwischen den Gängen) und
   kein Gewinde; der Netzweg (`perceive/helix.py`) misst an der
   Tessellation Steigung 0,99 und Ø 6,04, kennt aber weder Händigkeit noch
   Vorschub noch Gangzahl — und findet ein **Linksgewinde gar nicht** (S1,
   Befund B1). Händigkeit gibt es nur als **Erzeugerwissen** des Bausteins
   (`thread_exact` trägt `handedness="right"` ohne Maßquelle).
2. **Die Auskunft ist aus der Geometrie messbar, mit dem festgeschriebenen
   Satz:** OCP 8.0.1 zum Abtasten der Kanten nach Bogenlänge
   (`GCPnts_UniformAbscissa`), NumPy/SciPy für Achse (`least_squares`),
   Regression und Phasen. Der Prototyp `thread_probe.py` liefert Achse,
   Fußpunkt, Vorschub je Umdrehung, Händigkeit, Gangzahl, Teilung,
   Innen/Außen, Kamm- und Fußradius, Gangtiefe, Länge, Umläufe und eine
   Wendelabweichung als Unsicherheit — **oder einen Grund**, nie eine
   geratene Steigung (§4).
3. **Siebzehn STEP-Referenzkörper** aus drei unabhängigen Konstruktionen
   (`threaded_rod`-Sweep, eigener Helix-Sweep mit dem Gangprofil des
   Netzwegs, Boolesche Ableitungen) werden ohne Namen und ohne
   Operationswerte eingelesen; die Sollwerte sind Konstruktionsmaße, keine
   Auslesungen (§3). Fremde STEP-Gewinde gibt es im Baum und auf dieser
   Maschine nicht — das bleibt ein Abnahmeposten (§8).
4. **Die Fallmatrix hält** (§5, S3): rechts und links, außen und innen,
   ein- und zweigängig, gedreht und verschoben, angeschnitten, kurz (2,5
   Umläufe), beschädigt, geteilte Träger und NURBS-Neuparametrisierung
   liefern dieselbe Auskunft auf 1e-4 (Teilung, Vorschub) bzw. 1e-3
   (Radien) und 1e-6 (Achse); die sechs Gegenfälle (Zylinder, Ringrillen,
   Rändel, Wellenprofil, Naht ohne Rille, Viertelgang) werden mit
   benanntem Grund abgelehnt. Eingabe unverändert, Abbruch propagiert.
5. **Netz und nativ unterscheiden sich in der gemeinsamen Auskunft nur
   durch Facettierung und Fehlendes** (§6): Teilung im Raster 0,01,
   Kammradius im Facettenband; was das Netz nicht kennt (Händigkeit,
   Gangzahl, Vorschub) wird als unbekannt geführt, nicht verglichen. Wo
   das Netz **nichts** findet (Linksgang, angeschnitten, unter fünf
   Umläufen), steht das als Netzbefund, nicht als Toleranz.
6. **Fünf Befunde außerhalb des Prototyps** (§7): `threaded_rod` verliert an
   neun von 23 gemessenen Längen den Gang **still** oder liefert einen Körper
   unter dem Kernvolumen (B3, S4 — ein Kundenweg ohne Fehlermeldung, M8 × 1,25
   mit Länge 8 darunter); der Netzweg misst die Gangtiefe je nach Tessellation
   um −18 % bis +46 % falsch (B4); die Gewindepassung vergleicht Steigungen auf
   `EPS_GEOM` und verlangt Händigkeit, was mit gemessenen Werten aus zwei
   Wegen sofort „stimmt nicht überein" meldet (B5); `thread` steht nicht in
   `DETECTABLE_KINDS` — sobald der exakte Weg Gewinde erkennt, ist das eine
   Entscheidung, keine Zeile (B6); und der Nenndurchmesser eines
   Innengewindes ist im Vertrag der Grund-Ø, im Kopf der Kern-Ø (B7).

## 2. Der Bestand: drei Wege, zwei Sorten Wissen (S1)

Gemessen an M6 × 1, Länge 12, in `s1_inventory.py` (`s1_inventory.out`,
17 Zusicherungen, Exit 0):

| Weg | Was ankommt | Woher | Was fehlt |
|---|---|---|---|
| Erzeuger `thread_exact` (`brep/ops.py` Z. 358, Körper aus `brep/profiles.threaded_rod`, Merkmal Z. 415; ebenso `parts/build.py` Z. 145 und `geom/lid.py`) | `thread_1` mit `diameter 6`, `pitch 1`, `handedness right`, `length`, `centre`, `axis`, `internal False`; `provenance="generated"`, `measure_sources={}` | Operationswerte — **Erzeugerwissen**, keine Messung | Vorschub, Gangzahl, Unsicherheit; kein Maß trägt eine Quelle |
| Import STEP → `features_of` | `curved_face 2, face 6, fillet 2, pin 11` (Ø 4,7732 = Kern-Ø) | Topologie der Flächen | **kein `thread`**, keine Steigung, keine Händigkeit — Konzept §3 nennt dieselbe Lücke („7 pin Ø 8,16") |
| Netz `perceive.features.detect` → `helix.find_helices` | `thread` Ø 6,0382, Steigung 0,99, `internal False`, Länge 12,03; `measure_sources` `fit`/`facets` | Konzentration von `z − p·θ/2π` über scharfen Kantenzügen, **nur für Rechtsgang** | Händigkeit, Vorschub, Gangzahl; **Linksgewinde: 0 Wendeln** (B1); Mindestbestand 5 Umläufe und 200 scharfe Kanten |
| Normteiltabelle `knowledge/standards` | M2–M8 mit Nennmaß, Steigung, Kernloch | Tabelle | keine Funktion Steigung → Größe; `fasteners.size_for_thread` ordnet nur einem Bohrungs-Ø ein Innengewinde zu |
| Gegenstück `counterpart.pair_named("screw_and_nut")` | teilt `size`, `play`; Passung `thread` | Baustein | ein Importgewinde ohne `size` hat keinen Weg — **P2.6**, hier nur festgestellt |
| Bausteine `printed_thread` außen/innen (Netzprofil `shapes.thread_body`) | der Netzweg misst beide mit Steigung 1,0000 | Netz | der Innenbaustein ist ein **Werkzeug** (Kern + Gang, wird abgezogen): geometrisch ein Außengewindekörper; das Innengewinde entsteht am Träger und wird dort gemessen (S2/S3 `m8_innen`) |

**Fachliche Zwillinge, an denen die neue Auskunft hängt** (nur gelesen):
`helix.GROOVE_RANGE = (0.40, 1.20)` (Gangtiefe je Teilung), `helix.MIN_TURNS
= 5`, `Helix.diameter` („außen der Kamm, innen der Grund"), die
Gewindepassung `scene/fits.py` (Steigung auf `EPS_GEOM`, `handedness` in
`right`/`left`, Materialseite nur vom Loch), die Spiegelregel
`perceive/matching.py::moved_features` (Z. 670 am Stand `ee16040e7`: `det < 0` dreht `handedness`), der
Steckbrief `perceive/digest.py` Z. 433 (Innen-/Außengewinde, Ø, Steigung,
Achse), die Beschriftung `ui/labels.py` Z. 2071/2211 (Ø × Steigung) und
`perceive/actions.py` Z. 227 (ein erkanntes Gewinde hat heute keine
Handlung). **Der Prototyp baut keine zweite Maßlogik:** Er nimmt
`GROOVE_RANGE` aus `helix`, dieselbe Nenn-Ø-Festlegung wie
`Helix.diameter`, `units.EPS_GEOM` und `positive_axis`.

## 3. Referenzkörper (S2)

`s2_reference.py` baut mit `reference.py` siebzehn Körper, schreibt sie
nach `step/<name>.step`, liest sie zurück und prüft, dass **kein
Erzeugermerkmal** mitkommt (`features_of` kennt kein `thread`, jede
Herkunft ist `detected`; den Produktnamen der STEP-Datei liest weder
`step.read` in ein Merkmal noch der Prototyp). Die Sollwerte
stehen in `cases.json` und stammen aus den **Konstruktionsmaßen**, nicht
aus dem Prüfling: Teilung, Vorschub, Gangzahl, Händigkeit, Innen/Außen,
Nenn-Ø, Gangtiefe (`0,6134 · p` beim ISO-Profil des `threaded_rod`,
`0,55 · p − 0,01` beim eigenen Sweep, dessen Kern 0,01 über dem Profilfuß
sitzt), Länge und Achse (bei der gedrehten Lage aus der Rotationsmatrix).

Drei voneinander unabhängige Konstruktionen:

| Konstruktion | Fälle | Warum unabhängig |
|---|---|---|
| `profiles.threaded_rod` — Fünfpunktprofil mit Sockel, `MakePipeShell` auf dem Kernzylinder | `m6_rechts`, `m10_rechts`, daraus `m6_links` (Spiegelung `diag(1,−1,1)`), `m6_gedreht` (37° um (1,1,0), Versatz (12,−7,3)), `m6_angeschnitten` (alles unter x = −1 fehlt), `m6_kurz` (Stück z 4,75..7,25), `m6_beschaedigt` (Sektor 60° über z 4..8 ab r = 2,6 fehlt), `m6_geteilt` (`BOPAlgo_Splitter` mit der Ebene z = 6, danach vereinigt), `m6_nurbs` (`BRepBuilderAPI_NurbsConvert`) | der Produktionsweg — sein Gang ist ein echter Sweep, kein Netz |
| `internal_block`: Block minus (`threaded_rod` + Spiel 0,2) | `m8_innen` (M8 × 1,25, Tiefe 10, Spiel 0,2 → Grund-Ø 8,2) | Differenz statt Sweep; Material außen |
| `_helix_ridge`: eigener Helix-Sweep mit dem **Vierpunktprofil des Netzwegs** (`shapes.thread_body`), je Gang eine Wendel mit Phasenversatz, Fuzzy-Stufen auf privaten Kopien | `zweigaengig` (Ø 8, Teilung 1, Vorschub 2, zwei Gänge) | anderes Profil, anderer Bauweg, zwei Kämme |
| Gegenfälle | `gegen_zylinder` (glatt), `gegen_ringrillen` (vier Tori), `gegen_raendel` (zwölf Längsrillen), `gegen_welle` (Drehkörper mit Spline-Meridian, sechs Wellen), `gegen_naht` (Wendel mit Tiefe 0,02), `gegen_viertelgang` (Sektor 90° über z 3..3,4 des M6) | periodisch, gekrümmt, wendelförmig — aber kein Gewinde |

**Fremde STEP-Referenzen** (Konzept §13.4: „Ein einzelnes selbst erzeugtes
Gewinde beweist den beschlossenen Importweg nicht"): Der Testkorpus
`tests/data/` enthält keine STEP-Datei, die Sonden von P2.3/P2.7 keine mit
Gewinde, der Downloads-Korpus dieser Maschine nur STL/3MF. Die drei
Konstruktionen oben sind der Ersatz, den dieser Ordner leisten kann; ein
Hersteller-STEP (Schraube oder Gewindeeinsatz, mit modelliertem und nicht
nur kosmetischem Gewinde) bleibt in §8 als Abnahmeposten stehen.

Lauf: `s2_reference.out`, **80 von 80 Zusicherungen, Exit 0** (Stand
`ee16040e7`, 2026-09-20 12:24 UTC). Zu jedem Gewindefall prüft S2 die
**Voraussetzung des Falls** selbst — der Körper trägt B-Spline-Flanken, der
kurze Bolzen mehr Volumen als sein Kern —, bevor S3 ihn misst (§7 B3 ist
die Lehre daraus). Bauzeiten als Beobachtung: `threaded_rod`
M6 und M10 je 23 s, Block minus Bolzen 54 s, zwei Gänge 45 s, Naht 12 s,
alle Ableitungen unter einer Sekunde. Die STEP-Dateien (zusammen 10 MB,
0,005–1,9 MB je Körper) sind **nicht eingecheckt** (`.gitignore` dieses
Ordners): S2 erzeugt sie deterministisch aus den Konstruktionsmaßen, und
`run_all.sh` fährt S2 vor S3.

## 4. Das Verfahren (`thread_probe.py`)

Der Prototyp ist Kerncode ohne Qt, ohne neue Abhängigkeit, mit
durchgereichtem `check_cancelled` in jeder Schleife. Sein Weg, je Schritt
mit dem, was er wiederverwendet:

| Schritt | Was | Womit |
|---|---|---|
| 1 Kandidaten | alle Kanten, die weder Strecke noch Kreis sind (`BRepAdaptor_Curve.GetType`), nach **Bogenlänge** abgetastet (`GCPnts_UniformAbscissa`, ≥ 120 Punkte, ≤ 0,05 mm Abstand); ebene Kurven fallen heraus (die Stirnprofile sind auch B-Splines) | OCP |
| 2 Züge | Kanten, die einen Vertex teilen **und** dort tangential anschließen (≤ 10°), werden ein Zug; Punkte in Kurvenreihenfolge | `TopExp.MapShapesAndAncestors`, `IndexedMap…ShapeMapHasher` |
| 3 Achse | Startwerte: SVD-Hauptrichtungen der Punkte und die Achsen aller Zylinderflächen des Körpers; Einpassung eines Zylinders (`scipy.optimize.least_squares`, `lm`), bester Start nach Radiusstreuung; Vorzeichen über `units.positive_axis` | SciPy, NumPy, vorhandene Achsregel |
| 4 Wendel | Winkel `arctan2` in einer rechtshändigen Basis, `unwrap`; Regression `z = z0 + L·θ/2π` → **Vorschub L** je Umdrehung, **Händigkeit** aus dem Vorzeichen, Umläufe aus dem Winkelbereich, **Wendelabweichung** = größter Punktabstand von der Geraden, Phase `(z − L·θ/2π) mod L` | NumPy `lstsq` |
| 5 Rahmen | der Zug mit den meisten Umläufen gibt Achse und Fußpunkt vor; alle anderen werden **in diesem Rahmen** neu gemessen, damit Phasen vergleichbar sind; Züge mit gleichem Vorschub (±2e-3), gleicher Händigkeit, Abweichung ≤ 2 % L und Radiusstreuung ≤ 2e-3 bilden die Gruppe | — |
| 6 Wendeln | gleicher Radius + gleiche Phase = eine Wendel, ihre Stücke summieren Umläufe (geteilte Träger, beschädigte Flanken) | — |
| 7 Materialseite | `BRepLProp_SLProps`-Normale an der Fläche neben dem Zug, orientiert nach `Face.Orientation`: zeigt sie von der Achse weg, ist das Material innen → Außengewinde | OCP |
| 8 Gangzahl | die Menge (Radius, Phase) ist unter Verschiebung um 1/n periodisch — **alle** Wendeln, nicht nur Kammphasen: ein flacher Kamm hat zwei Kanten je Gang | — |
| 9 Auskunft | Teilung = L/n; Gangtiefe = Kamm − Fuß; Prüfung gegen `helix.GROOVE_RANGE`; Nenn-Ø außen Kamm, innen Grund (wie `Helix.diameter`); Länge aus dem axialen Bereich der Gruppe; Unsicherheit = größte Wendelabweichung der Gruppe | `helix`, `units` |

**Der Kurvenparameter ist kein Winkel.** Nichts oben liest `u` einer
B-Spline: Abgetastet wird nach Bogenlänge, der Winkel kommt aus der
Projektion auf die eingepasste Achse. Deshalb liefert `m6_nurbs` (jede
Fläche und Kante als NURBS, andere Parametrisierung) dieselbe Auskunft wie
`m6_rechts`, und `m6_geteilt` (Kanten an z = 6 geteilt) auch.

**Was ein Grund ist und was nicht.** Der Prototyp lehnt ab mit: „keine
Kantenzüge außer Strecken, Kreisen und ebenen Kurven" (glatter Zylinder,
Ringrillen, Rändel — und das Wellenprofil, dessen Spline-Meridiane eben
sind), „kein Zug windet sich um eine Achse", „Ausschnitt unter einer
Umdrehung: nur 0,33 Umläufe belegt — Achse und Steigung wären geraten"
(Viertelgang), „Wendelabweichung … über 2 % des Vorschubs", „Kamm ohne
Rille: Züge auf einem Radius", „Gangtiefe 0,010 mm ist 0,01 Teilungen —
außerhalb (0,4, 1,2)" (Naht mit Tiefe 0,02: die Wendel ist da, die Rille
nicht). Jede Ablehnung trägt, was gemessen wurde (Achse, Umläufe,
Vorschub), soweit es belastbar ist — und **nie eine Steigung als
Antwort**.

Drei Fehlwege sind während des Baus gemessen und im Code als Kommentar
festgehalten: die Verkettung über bloße Vertexnachbarschaft (Kamm, beide
Fußwendeln und Stirnkurven wurden **ein** Zug mit 36 „Umläufen" und 6 mm
Abweichung), ebene Stirnkurven als Kandidaten (dieselbe Falle) und die
Gangzahl aus Kammphasen allein (vier Kammkanten des zweigängigen Körpers
mit Abständen 0,35/0,15/0,35/0,15 → Gangzahl fälschlich 1).

## 5. Fallmatrix (S3)

`s3_matrix.py` misst jeden STEP-Körper frisch (`step.read`), hält die
Auskunft gegen `cases.json`, prüft **Eingabeunveränderlichkeit** (Flächen-,
Kantenzahl, Volumen und die Abtastpunkte der ersten Kandidatenkante vor und
nach der Messung identisch), vergleicht mit dem Netzweg (§6) und prüft
**Abbruch** (ein Zähler wirft nach 50 Prüfungen; ein zweiter zählt, dass die
Prüfung laufend aufgerufen wird). Toleranzen: Teilung und Vorschub 1e-4,
Radien 1e-3, Achse 1e-6 im Skalarprodukt, Länge 1e-3 (nur bei vollständigen
Körpern), Wendelabweichung unter 1 % der Teilung — gemeldet, nicht
verschluckt.

| Fall | Soll | Gemessen (STEP, ohne Erzeugerwissen) | Netz (`find_helices`) |
|---|---|---|---|
| `m6_rechts` | p 1, L 1, n 1, rechts, außen, Ø 6, Tiefe 0,6134, Länge 12, Achse z | p 1,0000, L 1,0000, n 1, right, außen, Ø 6,0000, Tiefe 0,6130, Länge 12,000, 12,00 Umläufe, Abw. 2e-5 | Ø 6,0382, p 0,99, außen |
| `m10_rechts` | p 1,5, L 1,5, Ø 10, Tiefe 0,9201, Länge 20 | p 1,5000, L 1,5000, n 1, right, Ø 10,0000, Tiefe 0,9200, Länge 20,000, 13,33 Umläufe, Abw. 4,3e-3 (ein Punkt einer Fußkante, RMS 1,4e-4) | Ø 10,0001, p 1,50 |
| `m6_links` | wie M6, **links** | **left**, sonst wie `m6_rechts` | **0 Wendeln** (B1) |
| `m8_innen` | p 1,25, **innen**, Grund-Ø 8,2, Tiefe 0,7668, Länge 10 | **innen**, p 1,2500, L 1,2500, Ø 8,2000, Tiefe 0,7670, Länge 10,000, 8,00 Umläufe | Ø 7,8158 (Kamm + Tiefe; B4), p 1,25, innen |
| `zweigaengig` | p 1, **L 2, n 2**, Ø 8, Tiefe 0,54, Länge 12 | p 1,0000, **L 2,0000, n 2**, right, Ø 8,0000, Tiefe 0,5400, Länge 12,000, 6,00 Umläufe | **0 Wendeln** (Beobachtung, Ursache nicht untersucht; dasselbe Gangprofil findet der Netzweg am Baustein `printed_thread`, S1 §6) |
| `m6_gedreht` | Achse (0,4255, −0,4255, 0,7986), Mitte verschoben | Achse (0,425547, −0,425547, 0,798636), Skalarprodukt 1 − 1e-6; sonst wie M6 | wie `m6_rechts` |
| `m6_angeschnitten` | wie M6, Länge nicht zugesichert | p 1,0001, L 1,0001, 7,65 Umläufe, Länge 12,000 (die Wendel reicht über den Rest) | **0 Wendeln** (B2: 200 scharfe Kanten fehlen) |
| `m6_kurz` | wie M6, Länge 2,5 | p 1,0000, L 1,0000, 2,50 Umläufe, Ø 6,0000, Tiefe 0,6130, Länge 2,500 | **0 Wendeln** (B2: unter fünf Umläufen) |
| `m6_beschaedigt` | wie M6, Länge nicht zugesichert | p 1,0000, 11,45 Umläufe (Stücke summiert), Ø 6,0000 | 2 Wendeln, die längste 4,71 Umläufe |
| `m6_geteilt` | wie M6 | wie `m6_rechts` (Stücke an z = 6 summiert) | Ø 6,0390, p 0,99 |
| `m6_nurbs` | wie M6 | wie `m6_rechts` | Ø 6,0349, p 0,99 |
| `gegen_zylinder` | kein Gewinde | „keine Kantenzüge außer Strecken, Kreisen und ebenen Kurven" | — |
| `gegen_ringrillen` | kein Gewinde | dito | — |
| `gegen_raendel` | kein Gewinde | dito | — |
| `gegen_welle` | kein Gewinde | dito (Spline-Meridiane sind eben) | — |
| `gegen_naht` | kein Gewinde | „Gangtiefe 0,010 mm ist 0,01 Teilungen — außerhalb (0,4, 1,2)" | — |
| `gegen_viertelgang` | kein Gewinde | „Ausschnitt unter einer Umdrehung: nur 0,33 Umläufe belegt — Achse und Steigung wären geraten" | — |

Dazu je Fall: Eingabe unverändert (17/17), und am Ende der Abbruch: der
Zähler wirft nach 50 Prüfungen aus der Messung heraus; ohne Grenze wird
die Prüfung an M6 **1454-mal** aufgerufen (Kanten, Fit, Züge). Die Messung
selbst dauert je Körper 0,4–0,9 s (Beobachtung unter Fremdlast; der
STEP-Import ist nicht enthalten).

Lauf: `s3_matrix.out`, **165 von 165 Zusicherungen, Exit 0**. Der erste Lauf (`s3_matrix.lauf1.out`, 5 rote von 145)
ist absichtlich aufgehoben: Er zeigt die drei Stellen, an denen der
Prototyp vor der Korrektur falsch lag — Nenn-Ø beim Innengewinde (B7, zwei
rote Zeilen: Sollwert und Netzverhältnis), Gangzahl aus Kammphasen (§4),
Wendelabweichung mit absoluter Grenze — und die vierte, die **kein**
Prototypfehler war: `m6_kurz` kam aus `threaded_rod(6, 1, 2.5)` ohne Gang
(B3).

## 6. Netz gegen nativ: Facettierung, Fehlendes, Nichtgefundenes

Für jeden gefundenen Fall misst S3 dieselbe Tessellation (`as_mesh_data`)
mit `helix.find_helices` und vergleicht **Gleiches gegen Gleiches**:
Teilung gegen Teilung (Raster des Netzwegs 0,01), Kammradius gegen
Kammradius (Facettenband ≤ 3 %), Innen/Außen. Die Gangtiefe des Netzwegs
steht als Beobachtung daneben — sie kommt aus Facetten. Händigkeit,
Gangzahl und Vorschub kennt das Netz nicht: sie werden als **unbekannt**
geführt, nicht verglichen.

| Größe | Netz gegen exakt | Einordnung |
|---|---|---|
| Teilung | 0,99 gegen 1,0000 (M6), 1,50 gegen 1,5000 (M10), 1,25 gegen 1,2500 (M8 innen) | Raster 0,01 des Netzwegs — Facettierung |
| Kammradius | ×1,0064 (M6, alle Ableitungen), ×1,00001 (M10), ×0,9835 (M8 innen), ×1,00002 (beschädigt) | ≤ 3 % — Facettenband; die Tessellation des STEP-Imports ist bei M6 gröber relativ zum Gang als bei M10 |
| Gangtiefe | **×1,46** (M6: 0,897 gegen 0,613), ×1,000 (M10), **×0,82** (M8 innen: 0,630 gegen 0,767), ×1,001 (beschädigt — anders tesselliert) | **keine Facettierung, ein Messfehler des Netzwegs** (B4): dieselbe Form liefert je nach Tessellation 0,61, 0,90 oder 0,63 |
| Nenn-Ø innen | 7,8158 gegen 8,2000 | Folge der Tiefe (B4); der exakte Weg liest den Grund-Ø direkt |
| Innen/Außen | gleich in allen 8 Vergleichen | — |
| Händigkeit, Gangzahl, Vorschub | Netz: **unbekannt** | nicht verglichen; der Netzweg setzt Rechtsgang voraus (B1) und kennt keinen Vorschub getrennt von der Teilung |
| Existenz | Netz findet `m6_links`, `zweigaengig`, `m6_angeschnitten`, `m6_kurz` **nicht** | B1/B2: Zwillinge weichen in der Existenz ab, nicht in Zahlen |

## 7. Befunde für die Integration

| Nr. | Befund | Beleg | Folge |
|---|---|---|---|
| **B1** | Der Netzweg findet **kein Linksgewinde**: Die Konzentration von `z − p·θ/2π` setzt Rechtsgang voraus (`helix.py`) | S1 §3b: Spiegelung derselben Tessellation → 0 Wendeln; S3 `m6_links`: Netz 0 Wendeln | `find_helices` muss beide Vorzeichen prüfen (`z ∓ p·θ/2π`) und die Händigkeit als Maß liefern — sonst meldet der Netz-Zwilling eines Linksgewindes „kein Gewinde", während der exakte Zwilling es misst |
| **B2** | Der Netzweg braucht **fünf Umläufe** (`MIN_TURNS`) und 200 scharfe Kanten | S3 `m6_kurz` (2,5 Umläufe), `m6_angeschnitten`: Netz 0 Wendeln | die Untergrenze des exakten Wegs ist eine Umdrehung; wo beide Zwillinge existieren, weicht die Auskunft nicht in Zahlen, sondern in **Existenz** ab — der Vertrag muss „nicht gemessen" von „kein Gewinde" trennen |
| **B3** | **`threaded_rod` liefert an mehreren Längen den Kern ohne Gang** — gültig, geschlossen, ein Körper, Volumen = Kern, keine Meldung: jede halbzahlige Umlaufzahl (Länge/Steigung + 2 = x,5) des Rasters, dazu M8 × 1,25 mit Länge 8; bei M10 × 1,5, Länge 4 einen Körper **unter** dem Kernvolumen | S4 `s4_rod_lengths.py`, 12/12, Exit 0: **9 von 23 Rasterpunkten** — alle sieben halbzahligen (M6 × 1 bei 2,5/3,5/4,5/6,5/10,5; M8 × 1,25 bei 5,625; M10 × 1,5 bei 6,75) und M8 × 1,25 bei Länge 8 (8,40 Umläufe) ohne Gang, M10 × 1,5 bei Länge 4 mit 96,7 statt 209,2 mm³ Kern. Die Stufen einzeln: Sweep 41,2 mm³ geschlossen, Zuschnitt 22,9 mm³ sound, **Vereinigung = Kern** | dieselbe Familie wie P2.7 §6 B1 (Vereinigung verschluckt den Gang still). `_is_sound_rod` fragt geschlossen und einteilig — beides erfüllt der Kern allein; eine **Volumenzusicherung** (Ergebnis > Kern) fängt es. Ein Kundenweg: `thread_exact` mit Länge 2,5 und Steigung 1 erzeugt heute einen glatten Bolzen |
| **B4** | Der Netzweg misst die **Gangtiefe** je nach Tessellation falsch — am Innengewinde ein Fünftel zu klein, am M6-Bolzen die Hälfte zu groß; sein Nenn-Ø eines Innengewindes (Kamm + Tiefe) verfehlt damit den Grund-Ø | S3 `m8_innen`: Netz-Tiefe 0,630 gegen 0,767 (×0,82), Netz-Nenn-Ø 7,8158 gegen 8,2000; **und** M6 außen: 0,897 gegen 0,613 (×1,46), während M10 und der anders tessellierte beschädigte M6 auf 1e-3 stimmen | `Helix.depth` taugt als Tor (`GROOVE_RANGE`), nicht als Maß; `Helix.diameter` eines Innengewindes ist als Nennmaß unzuverlässig. Der exakte Weg misst Kamm- und Grundradius direkt (8,2000) |
| **B5** | Die Gewindepassung vergleicht Steigungen auf `EPS_GEOM` (1e-6) und verlangt `handedness` in `right`/`left` (`fits.py` Z. 135–156) | Netz 0,99 gegen exakt 1,0000 → `fit.pitch_mismatch`; Netz ohne Händigkeit → `fit.not_measurable` | mit gemessenen Steigungen aus zwei Wegen braucht die Regel eine **Unsicherheit je Maß** (Netzraster 0,01; exakt die Wendelabweichung) statt einer Gleichheit auf 1e-6; die Händigkeit wird zum Maß mit Quelle |
| **B6** | `thread` steht **nicht** in `DETECTABLE_KINDS` (`perceive/features.py` Z. 721): erzeugte Gewinde werden fortgeführt, nie neu erkannt; `Feature.recognised` ist genau dafür da | Code, gelesen | sobald der exakte Weg Gewinde erkennt, ist zu entscheiden, ob `thread` erkennbar wird (dann muss **jedes** Bausteingewinde, auch links und kurz, wiedergefunden werden — B1/B2) oder erzeugte Gewinde `recognised=False` tragen. Keine Zeile, eine Entscheidung |
| **B7** | Nenndurchmesser: `Helix.diameter` sagt „außen der Kamm, innen der Grund"; das erste Prototyp-Maß nahm den Kamm-Ø (6,666 statt 8,2 am M8-Innengewinde) | S3, erster Lauf (`s3_matrix.lauf1.out`) | der Vertrag braucht **beide Radien** (`crest_radius`, `root_radius`) neben `diameter`; die Bezeichnung des Nennmaßes gehört in den Vertragskommentar, nicht in zwei Köpfe |
| **B8** | Es gibt keine Zuordnung Steigung + Ø → Normgröße; `size_for_thread` kennt nur Bohrungs-Ø → Innengewinde | S1 §4 | für P2.6 („Gegenstück") — hier nur festgestellt; eine Zuordnung bleibt ein **Vorschlag mit Toleranz** (Konzept §13.4: nicht still auf den nächsten Tabelleneintrag runden) |

## 8. Übergabematrix

### 8.1 Belegte und offene Fälle

| Fall | Stand | Sonde |
|---|---|---|
| Rechtsgewinde außen, vollständig (M6 × 1, M10 × 1,5) | belegt | S3 |
| Linksgewinde außen | belegt (Spiegelung) | S3 |
| Innengewinde (Block minus Bolzen) | belegt, Nenn-Ø = Grund-Ø | S3 |
| zweigängig (Vorschub 2 · Teilung) | belegt, Gangzahl aus Periodizität | S3 |
| gedreht und verschoben | belegt, Achse auf 1e-6 | S3 |
| angeschnitten (Halbkörper) | belegt, `partial` — Länge nicht zugesichert | S3 |
| kurz (2,5 Umläufe) | belegt | S3 |
| beschädigte Flanken (Sektor fehlt) | belegt, Stücke summieren Umläufe | S3 |
| geteilte Trägerflächen (`BOPAlgo_Splitter`) | belegt | S3 |
| neue Parametrisierung (`NurbsConvert`) | belegt | S3 |
| Gegenfälle: Zylinder, Ringrillen, Rändel, Wellenprofil, Naht, Viertelgang | belegt, je mit Grund | S3 |
| Eingabeunveränderlichkeit, STEP-Rundreise, Abbruch | belegt | S2, S3 |
| dreigängig und mehr | **offen** — Verfahren allgemein, kein Referenzkörper gebaut (jeder Gang kostet eine Vereinigung; zwei Gänge 45 s in S2) | — |
| Innengewinde links, Innengewinde mehrgängig | **offen** — Kombination nicht gebaut | — |
| konisches Gewinde (Rohrgewinde) | **offen** — Radius ändert sich mit z; der Zylinderfit lehnt es ab (Radiusstreuung), ein Grund ist da, eine Auskunft nicht | — |
| Gewinde, dessen Flanken **ohne scharfe Kanten** modelliert sind (verrundeter Kamm und Fuß als Tangentenübergang) | **offen** — Kandidaten sind Kanten; ein Gewinde aus lauter tangentialen Flächenübergängen hat keine; dann müsste die Wendel aus Flächenisolinien gelesen werden | — |
| fremdes Hersteller-STEP mit modelliertem Gewinde | **offen** — nicht verfügbar (§3) | — |
| Gewinde auf dem Netz mit Händigkeit (B1) | **offen** — Netzweg, nicht Teil dieses Prototyps | — |

### 8.2 Wiederverwendete APIs und Eigenentwicklungen

| Baustein | Vorhanden | Neu (Eigenentwicklung, ~Zeilen) |
|---|---|---|
| Kantenabtastung nach Bogenlänge | OCP `GCPnts_UniformAbscissa`, `BRepAdaptor_Curve` | — |
| Kantenarten, Nachbarschaft | `BRepAdaptor_Curve.GetType`, `TopExp.MapShapesAndAncestors`, `IndexedMap…ShapeMapHasher` (wie `brep/features.py`) | Verkettung tangential (40 Z.) |
| Zylinderachsen als Startwerte | `Solid.faces()`, `BRepAdaptor_Surface.Cylinder()` (wie `features_of`) | — |
| Achsfit | `scipy.optimize.least_squares` | Zielfunktion, Startwahl (60 Z.) |
| Wendelregression, Phasen, Gangzahl | NumPy | 120 Z. |
| Materialseite | `BRepLProp_SLProps`, `Face.Orientation` (wie `_native_patch`) | 30 Z. |
| Gangtiefe je Teilung, Nenn-Ø | `helix.GROOVE_RANGE`, `Helix.diameter`-Festlegung | — |
| Abbruch | `check_cancelled`-Muster aus `helix.find_helices`; im Produkt `CancelToken.raise_if_cancelled` wie `features_of` | — |
| Vertrag | `Feature`, `MeasureSource`, `SurfacePatch` (`types.py`) | keine neue Klasse — **kein paralleler Merkmalsvertrag** |

Keine neue Abhängigkeit; keine Bibliothek fehlt. Der Prototyp hat rund 700
Zeilen mit Docstrings; im Produkt sind es weniger, weil die Sondenanteile
(Winding-Dumps, `describe`) entfallen.

**Zwillingsklasse** (`.claude/rules/zwillinge.md`): Der exakte Gewindeleser
neben `helix.find_helices` ist ein **gewollter** Zwilling — zwei Rechenkerne,
und der Zweig endet ohne ihn (das Netz hat keine Kanten, der exakte Körper
keine Dreiecke, an denen man die Konzentration misst). Die Pflicht dazu:
ein Paritätstest, der beide auf dieselbe Frage gleich antworten lässt —
S3 §6 ist seine Vorlage. **Nicht** zu verdoppeln sind die fachlichen
Anteile: `GROOVE_RANGE`, die Nenn-Ø-Festlegung, das Verschlucken der
Phantome (`_threads_instead_of_phantoms` nimmt `helices` als Parameter —
der exakte Weg ruft dieselbe Funktion mit seinen Wendeln), die Texte des
Steckbriefs. Wer `MIN_TURNS` des Netzwegs auf die Umdrehung des exakten
Wegs stellt oder umgekehrt, hat nicht zusammengelegt, sondern eine
Messgrenze verschoben (§7 B2).

### 8.3 Minimale Integrationsdateien

| Datei | Änderung |
|---|---|
| `app/core/brep/thread.py` (neu) oder Abschnitt in `brep/features.py` | das Verfahren aus §4 als `read_thread(solid, *, cancelled)`; Rückgabe ein `Feature` je Gewinde mit `face_indices` aus `solid.triangles_of_face` der Flächen, die die Züge tragen, `surface_patches` der Kernzylinder (`native`) |
| `app/core/brep/features.py::features_of` | nach den Zapfen: `read_thread` aufrufen; die Zapfen **auf der Wendel** verschwinden wie beim Netzweg (`_threads_instead_of_phantoms` mit `_SWALLOWED_BY_A_HELIX` — dieselbe Regel, nicht kopiert: die Funktion nimmt `helices` als Parameter, braucht dafür aber ein `Helix`-ähnliches Objekt mit `face_indices` der Dreiecke; der exakte Weg liefert sie über `solid.triangles_of_face`) |
| `app/core/types.py` | Vertragskommentar am `thread`: `handedness` mit Maßquelle (`native` gemessen, `parameter` erzeugt), neu `lead`, `starts`, `crest_radius`, `root_radius`, `uncertainty`; `diameter` bleibt der Nenn-Ø (B7) |
| `app/core/perceive/helix.py` | B1: beide Vorzeichen; `Helix.handedness`; B2 bleibt (dokumentiert) |
| `app/core/perceive/features.py` | `_threads_instead_of_phantoms` schreibt Händigkeit und Gangzahl, wo das Netz sie kennt; B6 entscheiden (`DETECTABLE_KINDS`) |
| `app/core/scene/fits.py` | B5: Steigungsvergleich mit Unsicherheit beider Seiten; Händigkeit als Maß mit Quelle |
| `app/core/perceive/matching.py` | Spiegelregel bleibt; ein **gemessenes** `handedness` wird nach Spiegelung neu gemessen, nicht gedreht (Maßquelle `native` → Neumessung wie bei Radien) |
| `app/core/perceive/digest.py`, `app/ui/labels.py`, `app/core/perceive/actions.py` | Steckbrief und Beschriftung nennen Händigkeit und Gangzahl, wenn gemessen; die Handlung am erkannten Gewinde bleibt **P2.6** |
| `app/i18n/locales/*.json` | die neuen Texte (Händigkeit, Gangzahl, Gründe der Ablehnung) in allen sechs Sprachen |
| `tests/test_exact_thread_features.py`, `tests/test_helix.py`, `tests/test_features.py`, neu `tests/test_thread_import.py` | die Fallmatrix aus §5 als Regressionen. Die 17 STEP-Körper sind zusammen 10 MB (0,6–0,8 MB je Bolzen, 1,4–1,9 MB für die Booleschen Ableitungen) — zu viel für `tests/data/`. Zwei Wege: die **sechs tragenden** als Daten (`m6_rechts`, `m6_links`, `m8_innen`, `zweigaengig`, `m6_kurz`, `gegen_naht`, ≈ 3 MB) und die Ableitungen im Test aus `m6_rechts` (jede unter einer Sekunde); oder ein Modul-Fixture, das S2 nachbaut (M6 23 s, Block 54 s, zwei Gänge 45 s in S2 — im Tor zu langsam). Die Hauptaufgabe entscheidet |

Ausdrücklich **nicht** Teil von P2.5 (P2.6): Gewinde ändern, Gewinde
verschließen, Gegenstück aus einem Importgewinde, Normgrößenvorschlag aus
Steigung + Ø (B8), Filament am Gewinde.

### 8.4 Anschluss an den bestehenden Vertrag

| Anschluss | Wie |
|---|---|
| `Feature` | `kind="thread"`, `provenance="detected"`, `params` wie heute plus `handedness`, `lead`, `starts`, `crest_radius`, `root_radius`, `uncertainty`, `turns`; keine neue Klasse |
| Maßherkunft | `measure_sources`: `native` für alles, was an Kanten und Flächen des exakten Körpers gemessen ist; `fit` für die Achse (eingepasst) — die Achse eines Kernzylinders, wenn er die Startachse bestätigt, `native` |
| Originalträger | `surface_patches`: der Kernzylinder als `cylinder`/`native`, die Flankenflächen als Menge in `face_indices` (Dreiecke über `solid.triangles_of_face`); die Wendelkanten selbst haben im Vertrag keinen Platz und brauchen keinen — die Auskunft steht in `params` |
| gemeinsame Beziehungen | Gewindepassung `fits.py` (B5); Spiegelung `matching.py`; Zuordnung nach Transformation über dieselbe `moved_features`-Regel |
| Auswahl | wie beim Netz-`thread`: Klick auf eine Flankenfläche wählt das Gewinde, weil seine Dreiecke in `face_indices` stehen |
| Agent | Steckbrief (`digest.py`) nennt Händigkeit und Gangzahl mit Quelle; ein `thread` ohne Händigkeit (Netz) sagt „nicht gemessen" |
| Operationen | keine neue Operation in P2.5; `thread_exact` bekommt B3 (Volumenzusicherung) — das ist eine Korrektur am Erzeuger, kein Merkmalsvertrag |

### 8.5 Abnahmekriterien für P2.5

1. Die 17 Fälle aus §5 laufen als Kernregressionen mit den Toleranzen aus
   §5 — keine gelockert — und die sechs Gegenfälle lehnen mit Grund ab.
2. Derselbe Körper liefert über STEP-Rundreise, `NurbsConvert` und
   geteilte Träger dieselbe Auskunft (Teilung 1e-4, Achse 1e-6).
3. Ein Linksgewinde wird an **beiden** Zwillingen als links gemessen (B1),
   und die Spiegelung eines gemessenen Gewindes misst neu statt zu drehen.
4. `fits.py` nimmt zwei gemessene Gewinde (exakt/exakt, exakt/Netz) mit
   ihrer Unsicherheit an (B5), und ein Gewinde ohne Händigkeit sagt „nicht
   gemessen", nicht „stimmt nicht überein".
5. `thread_exact` mit Länge 2,5 und Steigung 1 liefert einen Gang oder eine
   Meldung — nie einen glatten Bolzen (B3).
6. Steckbrief, Beschriftung und Merkmalkarte nennen Händigkeit und Gangzahl
   mit Quelle in allen sechs Sprachen; kein fester Text.
7. Abbruch: `CancelToken` reißt die Messung an jeder Schleife ab (S3
   belegt es am Prototyp); Cache und Wiederöffnung tragen die neuen Maße
   mit ihren Quellen.
8. Entwicklungstor grün für genau diesen Stand; Fenster und Leistung beim
   Release.

## 9. Läufe, gelesene Stände und Grenzen dieser Übergabe

Alle Sonden laufen einzeln mit `.venv\Scripts\python.exe
konzepte/nachweise-cad-p2-5/<sonde>.py` und beenden mit dem echten
Exitcode (0 nur, wenn jede Zusicherung hielt); `run_all.sh` fährt alle vier
nacheinander in eigenen Prozessen und schreibt `laeufe.txt`. Letzter
vollständiger Lauf: Stand `ee16040e7`, 2026-09-20 12:24 UTC, **274
Zusicherungen in vier Sonden, alle vier Prozesse Exit 0**. `_iso.py` biegt
die Nutzerverzeichnisse um (§38) und teilt `_probe.py` mit P2.7.

| Sonde | Was sie belegt | Zusicherungen | Exit |
|---|---|---|---|
| `s1_inventory.py` | Bestand: Erzeugerwissen gegen gemessene Auskunft an drei Wegen, Normteiltabelle, Gegenstück, Bausteine; B1 | 17 | 0 |
| `s2_reference.py` | 17 Referenzkörper als STEP, Rückimport ohne Erzeugermerkmal, Voraussetzung je Fall (Wendelflächen, Volumen), Sollwerte aus Konstruktionsmaßen | 80 | 0 |
| `s3_matrix.py` | Fallmatrix gegen den Prototyp, Eingabeunveränderlichkeit, Netzvergleich, Abbruch | 165 | 0 |
| `s4_rod_lengths.py` | B3: `threaded_rod` über 23 Längen, die Stufe des Verlusts | 12 | 0 |
| `s3_matrix.lauf1.out` | der erste S3-Lauf vor den Korrekturen (B7 zweimal, Gangzahl, Grenze, B3) — aufgehoben, kein Nachweis | 140 von 145 | 1 |

Gelesen, nicht geändert (Stand `ee16040e7` mit dem ungestageten
Zwischenstand der Hauptaufgabe in `perceive/matching.py`, `scene/*`,
`ui/*` — keine der hier zitierten Zeilen liegt in einem geänderten
Abschnitt): `app/core/perceive/helix.py`, `perceive/features.py`
(`detect`, `_threads_instead_of_phantoms`, `DETECTABLE_KINDS`),
`perceive/matching.py` (`moved_features`), `perceive/digest.py`,
`perceive/actions.py`, `brep/features.py` (`features_of`),
`brep/profiles.py` (`threaded_rod`, `_joined_rod`, `_fuzzy_boolean`),
`brep/kernel.py`, `brep/step.py`, `scene/fits.py`, `types.py`,
`counterpart.py`, `knowledge/parts/fasteners.py`, `knowledge/standards.py`,
`ui/labels.py`, `tests/test_exact_thread_features.py`, `tests/test_helix.py`,
`tests/test_thread_features.py`, Konzept §3, §13.2, §13.4, §13.8,
Recherche §5, ROADMAP RM-188, P2.7-Nachweise (dieser Ordner teilt deren
`_probe.py`).

Was diese Übergabe **nicht** ist: kein Produktionscode, kein Test im Tor,
kein Fensterlauf, keine Leistungsmessung (die Dauerangaben sind unter
wechselnder Fremdlast entstanden — derselbe M10-Bolzen brauchte im ersten
S2-Lauf dieser Sitzung 56 s, im letzten 23 s), keine Aussage über fremde
STEP-Dateien, keine Aussage über Gewinde ohne scharfe Kanten oder mit
veränderlichem Radius. Der Prototyp ist an elf Gewindekörpern und sechs
Gegenfällen gemessen; jede Zahl in diesem Bericht steht in einer
`.out`-Datei mit Exitcode.

**Nicht committet.** Die Vorgabe verlangt ein belegtes grünes
Entwicklungstor für genau diesen Stand und verbietet zugleich einen
eigenen Torlauf neben dem der Hauptaufgabe; der Baum trägt außerdem deren
ungestageten Zwischenstand. Zur Übernahme mit Pathspec
`konzepte/nachweise-cad-p2-5/` gehören genau diese Dateien: `README.md`,
`.gitignore`, `_iso.py`, `thread_probe.py`, `reference.py`,
`s1_inventory.py`, `s2_reference.py`, `s3_matrix.py`, `s4_rod_lengths.py`,
`run_all.sh`, `cases.json`, `laeufe.txt` und die fünf Ausgaben
`s1_inventory.out`, `s2_reference.out`, `s3_matrix.out`,
`s3_matrix.lauf1.out`, `s4_rod_lengths.out`. `step/` und `__pycache__/`
bleiben draußen. Nichts außerhalb des Ordners wurde geändert; die
Registerzeile zu P2.5 in `ROADMAP.md` und der Eintrag in
`konzepte/README.md` sind Sache der Hauptaufgabe.

Prüfstand dieses Ordners: `ruff check` und `ruff format --check` auf
`konzepte/nachweise-cad-p2-5/` — beide 0. Kein vollständiger Torlauf aus
dieser Sitzung (Vorgabe: die Hauptaufgabe fährt ihres); der Ordner enthält
keinen Code, den das Tor sammelt (`tests/` unberührt, Sonden liegen unter
`konzepte/`, die `ruff` mitprüft).
