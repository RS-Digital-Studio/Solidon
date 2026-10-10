# Entwurf: Netze schmal halten — int32-Dreiecke und float32-Ecken

**Stand 10.10.2026, Entwurf ohne Code.** Teil 3 von
[RM-698](../ROADMAP.md#rm-698). Die Frage: Lassen sich Dreiecksindizes als
`int32` und Ecken einfach genau halten, ohne dass sich beim Druck etwas zeigt?
Maßstab ist **druckgleich** (Bauplan §11.2), mit den Leitplanken aus dem Review
der Regel: `EPS_GEOM` liegt ab 16 mm unter dem float32-Raster, die
Koplanarprüfung gilt nur in float64, Auswertung mit und ohne Cache bleibt
bitgleich, Indexrechnungen `a·n + b` laufen in int32 über. Gemessen am i9 unter
Windows, Python 3.14.7, Stand `paket/sparen`.

## Wo der Speicher liegt

Ein geladenes Netz hält am Spiderman (885 570 Dreiecke, 441 601 Ecken) 574 Byte
je Dreieck. Davon sind die **Grunddaten** — Ecken in float64 und Dreiecke in
int64 — nur 36 Byte. Der Rest sind Ableitungen, die `trimesh` und Solidon im
Cache des Netzes ablegen:

| Posten | Byte je Dreieck | Typ |
|---|---|---|
| `triangles`, `triangles_cross`, `triangles_center`, Normalen | 72 + 24 + 24 + 24 | float64, von `trimesh` aus den Ecken |
| `edges`, `edges_sorted`, `edges_face` | 48 + 48 + 24 | int64, `trimesh` |
| `face_adjacency*` (sieben Felder) | rund 130 | int64 und float64, `trimesh` |
| Kantentabelle (`solidon_edge_table`, `geom.mesh.edge_table`) | 60 | int64, Solidon |
| Nachbarindex, Eckenfächer, Eckenrang (`perceive.features`) | 48 + 28 + 4 | int64, Solidon |
| Grunddaten | 12 + 24 | float64 Ecken, int64 Dreiecke |

Ältere Stände im Verlauf sind schlank (`MeshData.lean`): Grunddaten,
`area_faces`, Teile und die Schichtanalyse, rund 52 Byte je Dreieck.

**Schmale Grunddaten allein sparen am gezeigten Netz etwa 3 %.** Viel bringen
sie nur in den schlanken Ständen, auf der Platte und im Hilfsprozess. Am
gezeigten Netz zählen die abgeleiteten Indextabellen.

## Messungen

**Grunddaten**, Ecken auf float32 und Dreiecke auf int32 verengt:

| Modell | Dreiecke | im Speicher | Plattencache (komprimiert) | größte Rundung |
|---|---|---|---|---|
| Laptop-Riser | 173 592 | 6,0 → 3,0 MB | 1,4 → 1,2 MB | 3,8 nm (81 % der Ecken über `EPS_GEOM`) |
| Eiffelturm 18 cm | 312 938 | 10,6 → 5,3 MB | 2,1 → 1,9 MB | 1,9 nm |
| Spiderman | 885 570 | 30,4 → 15,2 MB | 8,3 → 7,8 MB | 0,95 nm |
| Puppenbett (GLB) | 1 229 570 | 42,2 → 21,1 MB | 8,7 → 7,8 MB | 0,06 nm |

`trimesh` weitet beim Bau beides wieder: Ecken auf float64, Dreiecke auf int64.

**Verlustfrei in float32?** Das ist der Anteil der Ecken, die float32 exakt
trägt (`probe_narrow_lossless.py`):

| Modell | geladen | um 5 mm verschoben | um 30° gedreht |
|---|---|---|---|
| Laptop-Riser | 100 % | 95,4 % | 0 % |
| Eiffelturm | 100 % | 83,8 % | 0 % |
| Spiderman | 100 % | 93,4 % | 0 % |
| Puppenbett | 100 % | 7,7 % | 0 % |

Ein STL trägt float32, daher stimmt jede geladene Ecke exakt. Nach der ersten
Drehung stimmt keine mehr.

**Rundung auf float32.** Eine Sonde des Koordinators hat am 09.10. neun
Korpusnetze auf float32 gerundet, mit Versatz 0, 150 und 300 mm. Merkmale,
Arten und Namen blieben überall gleich, die größte Maßabweichung lag bei
0,49 µm, also unter `PRINT_LIMIT` (2,5 µm). Das Raster von float32 ist ab
16 mm gröber als `EPS_GEOM` (1e-6 mm): Bei 16 mm liegen zwei darstellbare
Werte 1,9 nm auseinander, bei 300 mm 30 nm.

**Kantentabelle in int32**, also `unique`, `inverse` und `counts` zusammen:
Riser 10,4 → 5,2 MB, Eiffelturm 18,8 → 9,4 MB, Spiderman 53,1 → 26,6 MB,
Puppenbett 73,8 → 36,9 MB, jeweils 60 → 30 Byte je Dreieck. Das ist
verlustfrei, solange ein Netz weniger als 2³¹ Ecken hat.

**Indexrechnungen `a·n + b`.** Ein Durchgang über `app/` findet 28 Stellen.
Davon wandeln zwölf ihre Eingänge nicht im Umfeld auf int64:
`brep/canonical.py:1064`, `brep/from_mesh.py:2119`,
`geom/attributes.py:235`, `geom/mesh.py:1186–1187` (liest `table.unique`
direkt), `geom/mesh_ops.py:513`, `perceive/features.py:5319` und `8081`,
`perceive/groups.py:2027` und `2787`; dazu zwei Treffer ohne Indizes
(`geom/autosplit.py:2045`, `geom/edges.py:3073`, Fließkomma). Mit int32-Eingängen rechnet NumPy
in int32. Am Spiderman ist `a·n` für Kantencodes bis zu 441 601² ≈ 1,9·10¹¹
groß und läuft damit still über.

## Varianten

**A — Ecken auf float32 runden (verlustbehaftet).** Druckgleich wäre das:
Die Abweichung liegt unter 0,5 µm. Die Verträge halten aber nur, wenn jede
Operation ihr Ergebnis auf dasselbe Raster rundet, bevor jemand es liest.
Sonst rechnet ein Lauf aus dem Cache mit anderen Ecken als ein frischer,
und die Gleichheit mit und ohne Cache bricht. Auch dann bleiben Verschweißen,
Nullflächen und die Koplanarprüfung (`EPS_GEOM`) ab 16 mm unter dem Raster.
Ein Splitterdreieck kann beim Runden kippen und ist danach entartet oder
schneidet seinen Nachbarn. Die Ersparnis am gezeigten Netz liegt bei rund
1 %. Regel 6 („doppelte Genauigkeit“) müsste dafür mit Ansage fallen.
**Nicht empfohlen.**

**B — Ecken in float32 nur halten, wo sie es exakt sind (verlustfrei).** Das
ist bitgleich und berührt keinen Vertrag. Es trifft aber nur geladene und
wenige verschobene Stände, und in `trimesh` geht es gar nicht: Ein schlanker
Stand müsste seine Felder außerhalb von `trimesh` tragen. Der Nutzen ist
klein, deshalb nur zusammen mit C.

**C — Dreiecke als int32 in schlanken Ständen und auf der Platte
(verlustfrei).** Das spart 12 Byte je Dreieck in jedem schlanken Stand (am
Spiderman 10,6 MB je Stand) und etwas in jeder Cachedatei. Dafür muss
`MeshData` eine schmale Form neben dem `trimesh`-Netz halten und erst bei
Bedarf weiten. Das ist ein Umbau am Kerntyp und braucht eine Entscheidung,
bevor er gebaut wird.

**D — Solidons eigene Indextabellen in int32 (verlustfrei).** Die
Kantentabelle in `geom/mesh.py` spart am gezeigten Netz 30 Byte je Dreieck,
also 5 % (Spiderman 26,6 MB, Puppenbett 36,9 MB). Nachbarindex, Eckenfächer
und Eckenrang in `perceive/features.py` bringen weitere 40 Byte (Gebiet E).
Voraussetzung: Jede Rechnung `a·n + b` über diese Felder weitet vorher auf
int64. Zuerst die Leser der Kantentabelle (`geom/mesh.py:1186–1187`, die
Nutzer von `edge_table` in `geom/repair.py`, `geom/mesh_ops.py` und
`generate.py`), dann die übrigen Indexrechnungen der Liste oben.

## Bedingung: der Abdruck der Filamentbuchung

`filament_usage` bildet seinen Abdruck bisher aus `vertices.tobytes()` und
`faces.tobytes()` des ausgewerteten Körpers. Jede Änderung dieser Bits lässt
einen schon gebuchten Druck nach dem Update als neu erscheinen, auch eine
druckgleiche wie das Runden auf float32 oder eine andere Dreiecksfolge.
**RM-706 landet deshalb vor jeder Stufe, die Netzbits ändert.** Danach
entsteht der Geometrieteil des Abdrucks aus den gespeicherten Eingängen.
Ändert sich der Abdruck trotzdem, gehört eine Gegenprobe dazu: Ein mit dem
alten Stand gebuchter Druck wird wiedererkannt. C und D ändern die Bits des
ausgewerteten Netzes nicht: D betrifft nur eine Ableitung, und C weitet beim
Lesen wieder auf int64. A ändert sie und darf erst nach RM-706 kommen.

## Empfehlung

1. **D zuerst**, mit Wächter. Die Kantentabelle hält int32, sobald das Netz
   unter 2³¹ Ecken bleibt, sonst int64. Jede Indexrechnung über ihre Felder
   weitet ausdrücklich auf int64. Dazu zwei Tests: ein Netz mit mehr als
   46 341 Ecken, an dem ein Code in int32 überliefe, mit Sollwert aus der
   int64-Rechnung; und ein Durchgang über `app/`, der jede Rechnung
   `a·n + b` über Indexfelder ohne int64 im Umfeld meldet.
2. **C** als eigener Punkt mit Entscheidung, wenn D gemessen ist.
3. **A nicht.** **B nur zusammen mit C.**

## Prüfplan für jede Stufe

- `tools/check_print_equal.py` über Korpus und Beispielprojekte, vorher gegen
  nachher. D und C sind verlustfrei, Soll ist deshalb Abweichung 0 und
  bitgleiche Ecken.
- Gleichheit mit und ohne Cache (§15.1), Hilfsprozess gegen Prozess, jede
  Plattform: bitgleich.
- Speicher am Spiderman und am Puppenbett vorher und nachher: Spitze und
  Dauerstand, mit dem Bereiniger wie im Fensterprozess.
- Gegenprobe: Mit absichtlich weggelassener int64-Weitung wird der
  Überlauftest rot.
