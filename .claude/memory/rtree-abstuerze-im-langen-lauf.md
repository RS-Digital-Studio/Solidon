---
name: rtree-abstuerze-im-langen-lauf
description: "rtree war die Absturzursache seit 08/2026 und ist seit 24.08.2026 aus dem Prozess — wer wieder Access Violations sieht, sucht zuerst, wer es zurückgeholt hat."
metadata: 
  node_type: memory
  type: project
  originSessionId: dbd41399-e6de-443d-b168-384423e01c1a
  modified: 2026-08-08T04:14:31.945Z
---

**Seit dem 24.08.2026 ist die Ursache draußen, nicht nur gemildert.** Ein
Kunde verlor beim Maßeändern (Weg 2, „Breite auf 90") die Anwendung; Robert
zog die Grenze auf null. Alle drei Nutzer des Index sind ersetzt —
`geom/mesh.on_surface` (eigener cKDTree über Dreiecksschwerpunkten),
`ingest/outline` und der **Schnittdeckel** (`geom/enclosure.py` ersetzt
trimeshs `enclosure_tree`, shapelys STRtree liefert die Kandidaten) — und das
Paket ist deinstalliert und aus `constraints.txt`, `pyproject.toml` und der
Lizenzliste entfernt. `tests/test_slots.py::test_the_geometry_paths_never_loads_rtree`
fährt alle drei Wege in einem eigenen Prozess und besteht darauf, dass
`rtree` nie in `sys.modules` steht.

Der dritte Nutzer flog **nicht** über die Quelltextsuche auf, sondern über
die Probe mit blockiertem Import — 171 grüne Tests mit installiertem Paket
hatten ihn nicht gezeigt. Wer je wieder eine Access Violation aus dieser
Familie sieht: zuerst prüfen, ob jemand rtree zurückgeholt hat
(`pip show rtree`), nicht im eigenen Code suchen.

Der Rest dieser Notiz beschreibt die Zeit **davor** und bleibt als
Begründung stehen:

Seit dem 6. August 2026 bricht `pytest -q` über die ganze Suite auf dieser
Maschine mit „Windows fatal exception: access violation" ab. Die Stelle
wandert (`shapes.thread_body`, `test_translations`, `test_slots`), die
Ursache ist immer dieselbe Ecke: `rtree`/libspatialindex, aufgerufen aus
`trimesh.proximity.nearby_faces`. Einmal kam sogar ein unmöglicher
`TypeError: 'int' object does not support the context manager protocol` aus
`rtree/index.py` — die Signatur beschädigten Prozessspeichers, kein Logikfehler.

**Why:** Zweimal per `git stash` gegengeprüft: der Absturz tritt mit und ohne
die eigenen Änderungen auf, und `tests/test_slots.py` allein stürzt in beiden
Zuständen in zwei von drei Läufen ab. Es ist kein Regressionssignal — wer es
dafür hält, sucht stundenlang im falschen Code.

**How to apply:** Die Suite in Portionen fahren, dann ist sie vollständig grün
(2807 Tests, Stand 06.08.2026):

```
.venv\Scripts\python.exe -m pytest -q $(ls tests/test_[a-o]*.py | tr '\n' ' ')
.venv\Scripts\python.exe -m pytest -q tests/test_p*.py
.venv\Scripts\python.exe -m pytest -q $(ls tests/test_[q-s]*.py | tr '\n' ' ')
.venv\Scripts\python.exe -m pytest -q tests/test_t*.py
.venv\Scripts\python.exe -m pytest -q $(ls tests/test_[u-w]*.py | tr '\n' ' ')
```

Bricht eine Portion ab, dieselben Dateien einzeln laufen lassen — einzeln
gehen sie durch. Ein *echtes* Fehlschlagen (`F` im Punktemuster) ist etwas
anderes als ein Prozessabbruch und wird verfolgt.

Bevor jemand `rtree` neu installiert: das ändert die Umgebung und gehört
Robert gefragt. Siehe auch [[parallele-sitzungen-formwerk]] und
[[leistungstests-fremdlast]] — beide beschreiben dieselbe Falle, dem eigenen
Code zuzuschreiben, was der Maschine gehört.

**Seit 08.08.2026 deutlich seltener.** Die Slot-Übertragung
(`geom.attributes.transfer`) stellte je Auswertung 113168 Anfragen an den
Index, weil sie für jedes Dreieck des Ergebnisses den Abstand zu jeder Quelle
suchte. Mit dem Vorfilter dort sind es 1180 — und sechzig Auswertungen
hintereinander gingen ohne einen einzigen Fehlgriff durch, wo etwa drei zu
erwarten gewesen wären. Die volle Suite läuft seither in einem Stück
(3168 Tests, ~5:30 min); ein Abriss am Prozessende kommt noch vor, aber nicht
mehr regelmäßig. Wer wieder Abstürze sieht, zählt zuerst die rtree-Anfragen,
statt am Fehlerbild zu raten.
