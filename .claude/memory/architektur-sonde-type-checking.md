---
name: architektur-sonde-type-checking
description: "Eine Importgraph-Sonde meldet Phantomzyklen, solange sie TYPE_CHECKING-Blöcke als Kanten zählt; und bei Kernänderungen ist „betroffen\" fast immer die ganze Suite."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e44e7ebf-a72f-4543-a02a-0efbcc35b48d
  modified: 2026-09-02T16:21:32.020Z
---

Zwei Messfallen aus der Architektur-Durchsicht am 02.09.2026 (Sitzung 3d-druck-85):

1. **Vier von vier gemeldeten Zyklen waren keine.** Die erste Sonde zählte
   Importe unter `if TYPE_CHECKING:` als eifrige Kanten und fand vier Zyklen
   (`activation`, `geom.mesh ↔ export.threemf`, `scene ↔ scene.history`,
   `agent ↔ agent.session`). Mit ausgeschlossenen TYPE_CHECKING-Blöcken: null.
   Was übrig blieb, war ein einziger **träger** Import gegen die Schichtrichtung
   (`geom/mesh.py` → `export.threemf.read_objects`), und der ist begründet.
2. **Eine Testauswahl aus dem Importgraphen ist bei Kernänderungen die
   Suite.** `app.i18n` hat Fan-in 167, `types.py` 125, `errors.py` 94. Schon
   `catalog.py` + `tables.py` ergaben 184 von 194 Testdateien.
   `tools/affected_tests.py` sagt das dann ehrlich („das ist die Suite") —
   sein Wert liegt bei Änderungen an einem Blatt, einer UI-Datei oder einem
   Werkzeug.

**Why:** Beide Fehler sehen wie Befunde aus. Vier Phantomzyklen hätten vier
Umbauten ausgelöst; eine Auswahl, die die Suite ist, hätte man für ein
kaputtes Werkzeug halten können.

**How to apply:** Eine Importsonde schließt `TYPE_CHECKING` aus, bevor sie
Zyklen meldet — und unterscheidet eifrig/träge, weil nur eifrig ein Zyklus
ist. Vor einer Testauswahl den Fan-in der geänderten Module ansehen; liegt
`i18n`, `types`, `errors` oder `log` dabei, direkt das Tor fahren. Siehe auch
[[zwei-laeufe-nach-jeder-code-aenderung]] und [[fuenf-tests-eine-lage]].
