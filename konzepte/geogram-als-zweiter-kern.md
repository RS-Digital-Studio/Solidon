# Geogram als zweiter Boolescher Kern — was es wäre, und was es nicht löst

> **Erledigt am 17.09.2026, am selben Tag. Es wird kein zweiter Kern gebaut.**
>
> §7 dieses Dokuments verlangte eine Messung, bevor irgendetwas entschieden
> wird: *Läuft schon die Eingabe auseinander, oder erst das Ergebnis?* Die
> Messung ist gefahren (Läufe 35262208955 und 35265459662, drei Plattformen),
> und sie hat die Frage beantwortet und die Entscheidung gleich mit:
>
> **Die Eingabe lief auseinander.** Der Klotz — eine Box ohne transzendente
> Funktion — war auf allen drei Plattformen bitgleich; Hohlraum und Nachbar,
> beide aus ``cos``/``sin``, auf allen drei verschieden. Ursache ist NumPys
> Wahl der SIMD-Implementierung: AVX-512 auf Ubuntu, AVX2 auf Windows, NEON auf
> macOS.
>
> **Und manifold3d ist plattformgleich.** Nachdem die Eingangskörper über
> ``units.circle_point`` gebaut werden, liefert die Boolesche Operation auf
> allen drei Plattformen denselben Fingerabdruck — 1222 Dreiecke,
> ``8c1169913b6ac670``. Das ist der Satz, den dieses Dokument nicht zu hoffen
> wagte: Der Kern, den wir haben, kann, was wir brauchen.
>
> Damit fällt die Begründung für jeden Wechsel. Geogram bleibt fachlich
> beeindruckend und kostet nichts — aber es löst kein Problem, das wir haben.
> Der Rest des Dokuments bleibt als Recherchestand stehen; §5 und §7 sind
> überholt, §3 (fertige Wheels, Bindung ohne Boolesche Operationen) gilt
> weiter, falls die Frage je aus einem anderen Grund zurückkommt.
>
> Der Nachweis steht in ``tests/test_platform_identity.py``, der Fall im
> Register unter [RM-187](../ROADMAP.md#rm-187).

**Stand:** 17.09.2026 · **Recherche und Konzept, nichts davon gebaut — und
nichts davon zu bauen.** · Schwester von
[anfrage-trueform.md](anfrage-trueform.md), die dieselbe Frage an den
kommerziellen Kandidaten stellte und aus demselben Grund zurückgezogen ist.

**Was dieses Dokument beantwortet:** Ob Geogram den Mac-Befund vom 17.09.2026
lösen könnte, ob der Kunde dafür einen Compiler braucht, und was ein Einbau
kosten würde. **Was es nicht beantwortet:** ob wir es tun — dafür fehlt eine
Messung, die in §7 steht und die es bis heute nicht gibt.

---

## 1. Der Anlass, in drei Zahlen

Dieselbe Boolesche Operation — eine Bohrung mit Senkung verkleinern — liefert
auf Windows und Ubuntu **1178 Dreiecke** und auf dem ARM64-Mac der CI **1176**.
Die Senkung trägt dort 240 statt 241. Alle Maße sind gleich (Ø 11,928, Winkel
89,838); nur die Triangulierung ist es nicht. Daraus wurde ein Rand in Form
einer Acht, daraus keine zwei Randringe, daraus keine Bohrungskette — ein
Merkmal, das auf Windows bearbeitbar ist und auf dem Mac nicht.

Die Ursache steht in
[`.claude/memory/arm-rechnet-anders-als-x86.md`](../.claude/memory/arm-rechnet-anders-als-x86.md):
Auf ARM64 entstehen FMA-Instruktionen von selbst, auf x86 erst mit Opt-in;
`a×b+c` rundet dort einmal statt zweimal. **manifold3d sagt Topologie zu und
Numerik nicht** — „guaranteed manifold output", kein Wort zu bitgleichen
Ergebnissen über Plattformen.

Behoben ist der **Symptomweg** (die Erkennung verträgt jetzt beide Netze:
`_without_notches`, `_rings_through_a_shared_corner`). Die Ursache ist es
nicht, und sie wird wiederkommen — an einer anderen Stelle, mit einer anderen
Zahl.

## 2. Was Geogram ist

Die Geometriebibliothek von Bruno Lévy (Inria, vormals ALICE), gewachsen aus
über dreißig Veröffentlichungen in SIGGRAPH, ACM TOG, SGP und Eurographics.
Sie trägt die **3-Klausel-BSD-Lizenz** — Regel 15 und Regel 22 stehen dem
nicht entgegen, sie wäre ein Eintrag in `licences.toml` und sonst nichts.

Für uns zählen zwei Teile:

* **Exakte Arithmetik nach Shewchuk** (`expansion_nt`, Fließkomma-Expansionen)
  plus **PCK**, ein Generator für geometrische Prädikate. Das ist der Stand der
  Technik, nicht eine Eigenwerbung.
* **Boolesche Operationen** — `mesh_union`, `mesh_intersection`,
  `mesh_difference` in `geogram/mesh/mesh_surface_intersection.h`, dazu das
  Demo-Programm `boolean_op`. Schnittpunkte werden in **exakter Genauigkeit**
  gerechnet (`vec3E`, homogene Koordinaten `vec3HE`), und an koplanaren Gebieten
  trägt die Eindeutigkeit der Delaunay-Triangulierung die Robustheit.

Genau das ist der Punkt, an dem manifold3d nach eigener Aussage nicht steht:
Dort heißt es, exakte Arithmetik sei „slow, complex, and often still suffers
failures in edge cases", und koplanare Flächen sind ein offener Punkt, weil
„floating point is problematic".

## 3. Roberts Frage: braucht der Kunde einen Compiler?

**Nein.** Das war die Sorge, und sie ist ausgeräumt — aber nicht so, wie es
zuerst aussah.

Auf PyPI liegt `geogram` in Version 0.0.7, gebaut von Bruno Lévy und Cyprien
Plateau--Holleville (beide Inria), Quelle
[`PlathC/grampy`](https://github.com/PlathC/grampy), Lizenz BSD.
**16 fertige Wheels** für alle drei Plattformen, gemessen am 17.09.2026:

| Plattform | Räder |
|---|---|
| Windows | `win_amd64` für 3.9, 3.10, 3.11 und **`cp312-abi3`** |
| macOS | `macosx_10_15_x86_64` und `macosx_11_0_arm64`, je vier |
| Linux | `manylinux_2_27_x86_64` / `manylinux_2_28`, je vier |

Das `cp312-abi3` ist der Teil, der zählt: **Stable ABI** heißt, dasselbe Rad
läuft auf 3.12, 3.13, 3.14 und weiter. Unsere Untergrenze ist 3.14 — es gibt
also für jede unserer drei Plattformen ein fertiges Rad, und weder der Kunde
noch unser Bauserver bräuchte einen Compiler. Die Installation wäre eine Zeile
in `pyproject.toml` und eine feste Version in `constraints.txt`, genau wie bei
`manifold3d`.

### Und der Haken, der alles daran aufhängt

**Diese Bindung kann die Booleschen Operationen nicht.** `grampy` bindet
Geograms Voronoi-Diagramm und Delaunay-Triangulierung — das ist der
ausdrückliche Zweck des Pakets, und die Beispiele zeigen nichts anderes.
`mesh_union` und seine zwei Geschwister sind **nicht** darin.

Damit steht die Antwort auf Roberts Frage in zwei Teilen, und nur der erste ist
gut:

* Der **Auslieferungsweg** ist offen und belegt: Geogram lässt sich als abi3-Rad
  für alle drei Plattformen bauen, ohne dass jemand beim Kunden etwas übersetzt.
  Das ist keine Vermutung mehr, sondern ein Paket, das man heute installieren
  kann.
* Die **Bindung, die wir brauchen**, gibt es nicht. Wir müssten sie selbst
  schreiben und selbst bauen — mit `pybind11` oder `nanobind` gegen
  `mesh_surface_intersection.h`, über `cibuildwheel` für drei Plattformen, und
  danach selbst pflegen.

## 4. Was das an Arbeit hieße

Kein Detailplan — dafür ist die Entscheidung nicht reif. Die Umrisse, damit die
Größenordnung stimmt:

| Stück | Was darin steckt |
|---|---|
| Die Bindung | Drei Funktionen, Netz hinein, Netz heraus. `numpy` → `GEO::Mesh` → `numpy`. Klein, aber es ist C++, und wir haben bisher keines im Baum |
| Der Bau | `cibuildwheel` für win/mac/linux, abi3, Geogram als Submodul oder über CMake `FetchContent`. Der Teil, den `grampy` bereits gelöst hat und von dem man abschreiben darf |
| Die Rückfallkette | `geom/boolean.py` bekommt eine Stufe. **Nicht** als Ersatz — als erste Stufe vor `direct`, mit Rückfall auf den heutigen Weg. Die Stufe wird in die Operation geschrieben (`solver`), wie alle anderen |
| Die Tests | `tests/test_boolean.py` erzwingt jede Stufe einmal; eine neue Stufe ist ein neuer Fall. Dazu der Korpus gegen die alten Kennzahlen |
| Die Pflege | Eine Bibliothek, die wir selbst binden, ist eine, die wir selbst reparieren. Bei `manifold3d` genügt heute ein Versionssprung |

Der letzte Punkt ist der teuerste und steht nicht in Stunden. Er ist derselbe,
der in der trueform-Anfrage als Frage 5 steht: Woran binden wir uns, und was
kostet es, wenn es bricht.

## 5. Die Determinismus-Zusage fehlt auch hier

Das ist der Satz, der dieses Dokument von einer Empfehlung unterscheidet.

Geograms eigene Dokumentation macht **keine ausdrückliche Aussage** zu
bitgleichen Ergebnissen über Architekturen hinweg — genauso wenig wie
manifold3d, genauso wenig wie trueform. Und sie nennt ausdrücklich eine
Einschränkung: Geogram hat **keinen Snap-Rounding-Algorithmus**, der zusichert,
dass die auf doppelte Genauigkeit zurückgerundeten Punkte keine neuen
Schnitte erzeugen.

Was sich daraus **ableiten** lässt, und was davon eine Vermutung bleibt:

* Die **Kombinatorik** — welcher Punkt liegt auf welcher Seite, welche Dreiecke
  entstehen — kommt aus exakten Prädikaten. Ein exaktes Prädikat ist eine reine
  Funktion seiner Eingabe; FMA kann den Fließkomma-**Filter** davor anders
  greifen lassen, aber der Filter entscheidet nur, *ob* exakt nachgerechnet
  wird, nicht *was* herauskommt. Die Triangulierung sollte damit
  architekturunabhängig sein. **Das ist eine Ableitung aus der Bauart und keine
  Zusage** — belegt wäre sie erst durch die Messung in §7.
* Die **Koordinaten** werden exakt gerechnet und dann auf `double` gerundet.
  Rundung ist deterministisch, solange die exakte Zahl dieselbe ist.
* Die fehlende Snap-Rundung betrifft einen anderen Fall — sie ist eine Aussage
  über *Gültigkeit* des Ergebnisses, nicht über seine *Gleichheit* auf zwei
  Rechnern.

Regel 21 verbietet, aus „sollte" ein „ist" zu machen. Wer Geogram einbaut, ohne
§7 gemessen zu haben, kauft dasselbe Problem noch einmal — mit mehr eigenem
Code darunter.

## 6. Der Vergleich der drei, in einer Tabelle

| | manifold3d (heute) | Geogram | trueform |
|---|---|---|---|
| Lizenz | Apache-2.0 | BSD-3 | PolyForm Noncommercial — Vertrag nötig |
| Wheels für 3.14 auf allen drei | ja | **nur Voronoi/Delaunay** | ja |
| Boolesche Ops in Python | ja | **Bindung fehlt** | ja |
| Arithmetik | IEEE-754 mit symbolischer Störung | exakt (Shewchuk) | exakt (Ganzzahlkern) |
| Determinismus zugesagt | nein | **nein** | nein (gefragt) |
| Tempo (Fremdbenchmark) | 120,3 ms Median | nicht vergleichbar gemessen | 18 ms Median |
| Gültige Ergebnisse | 1000/1000 | nicht gemessen | — |
| Kosten | null | null | unbekannt, Frage läuft |
| Wenn es ausfällt | forken erlaubt | forken erlaubt | Vertragssache |

**manifold3d bleibt vorerst richtig.** Es kostet nichts, es liefert Räder, es
löste im Fremdbenchmark 1000 von 1000 Paaren gültig, und die Apache-Lizenz
federt einen Ausfall ab. Ein Wechsel muss besser sein als das, nicht nur
exakter.

## 7. Die Messung, die vor jeder Entscheidung steht

Sie kostet einen CI-Lauf und beantwortet die Frage, an der alles hängt:

> **Läuft schon die Eingabe auseinander, oder erst das Ergebnis?**

`_sloping_bore` baut seine Punkte aus `cos` und `sin`, und die kommen aus der
libm der Plattform. Weichen schon die Eckpunkte des Eingangsnetzes zwischen
Windows und dem Mac ab, dann **hilft kein exakter Kern** — ein exakter Kern
rechnet exakt mit den Zahlen, die er bekommt, und zwei verschiedene Eingaben
geben zwei verschiedene Ergebnisse, auch exakt gerechnet. Dann wäre die
Ursache in unserem eigenen Netzaufbau und nicht in manifold3d, und weder
Geogram noch trueform lösten sie.

Die Sonde dafür ist geschrieben (`quantisierung.py` im Arbeitsordner der
Sitzung, drei Messpunkte mit Fingerabdruck je Stufe) und **auf Windows
gefahren**; was fehlt, ist derselbe Lauf auf dem ARM-Runner der CI und der
Vergleich der Hashes. Bis dahin ist die Ursachenkette an ihrer ersten Stelle
nicht gemessen, sondern erschlossen.

**Zwei Wege sind auf demselben Weg schon ausgeschlossen worden, durch Messung
und nicht durch Vermutung:**

* **Die Eingabe vor der Operation quantisieren** macht die Netze **schlechter**
  — 1422 bis 1596 Dreiecke statt 1226. Runden zerstört die Koplanarität der
  Klotzflächen, und der Kern trianguliert danach mehr statt weniger.
* **Die doppelte Ecke nachträglich verschweißen** trifft das Volumen auf
  0,000e+00 genau und lässt das Netz trotzdem nicht wasserdicht zurück;
  `_tidied` lehnt zu Recht ab.

## 8. Empfehlung

1. **Erst §7 messen.** Ein CI-Lauf, und er entscheidet, ob die Frage nach einem
   anderen Kern überhaupt die richtige ist. Alles andere davor ist Arbeit an
   einer Ursache, die niemand gemessen hat.
2. **Die Antwort von Polydera abwarten.** Die Anfrage steht in
   [anfrage-trueform.md](anfrage-trueform.md) und ist noch nicht gesendet; ihre
   Frage 3 ist wörtlich dieselbe wie die, die Geogram offen lässt. Kommt von
   dort eine belastbare Determinismus-Zusage, ist das ein Argument, das Geogram
   nicht hat.
3. **Geogram bleibt der Rückhalt, nicht der Plan.** Es ist die einzige der drei
   Möglichkeiten, die exakt rechnet, nichts kostet, forkbar bleibt und bei der
   der Auslieferungsweg nachweislich offen ist. Was fehlt, ist eine Bindung von
   etwa dreihundert Zeilen C++ und der Wille, sie zu pflegen. Das ist ein
   überschaubarer Preis — aber nur, wenn §7 sagt, dass er etwas kauft.
