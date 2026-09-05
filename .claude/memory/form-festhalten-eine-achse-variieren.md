---
name: form-festhalten-eine-achse-variieren
description: "Ob eine Schranke auf der richtigen Achse liegt, entscheidet erst eine Messreihe, die die Form konstant hält und nur die gemessene Größe wachsen lässt."
metadata:
  node_type: memory
  type: feedback
  originSessionId: f37d7a68-f87d-4034-ac69-fe8f1cab6525
  modified: 2026-09-04T15:38:05.726Z
---

Eine Schranke misst eine Größe (Dreiecke) und meint eine andere (Rechenzeit). Ob
sie trifft, sagt kein Modellvergleich: Zwei Modelle unterscheiden sich in allem
zugleich. Nur eine Reihe, die **die Form festhält und die gemessene Größe
variiert**, trennt die Achsen.

Werkzeug bei Netzen: `trimesh.Trimesh.subdivide()` — vervierfacht die Dreiecke,
ohne die Form zu ändern. Am 04.09.2026 an der Stützkarte:

    59 740 Dreiecke ->  7,65 s
    238 960         -> 24,71 s
    955 840         -> 64,34 s

Fast linear. Über achtzehn *verschiedene* Modelle sah dieselbe Karte dagegen
willkürlich aus — das kleinste Modell war das teuerste. Beide Messungen sind
richtig, sie beantworten verschiedene Fragen: Der Modellvergleich zeigt, wie
stark die **Form** streut (Faktor 60), die Reihe zeigt, wie die **Größe**
skaliert.

**Why:** Die Streuung über Modelle verführt zum Schluss, die Schranke liege auf
der falschen Achse und gehöre weg. Die Reihe zeigte das Gegenteil: Ein Modell
derselben Bauart mit 900 000 Dreiecken rechnet über eine Minute — die Grenze
anzuheben wäre der Fehler gewesen, den die erste Messung nahegelegt hat.

**How to apply:** Vor jeder Änderung an einer Schranke eine Reihe fahren, die
alles außer der gemessenen Größe festhält. Wächst die Kosten dort mit, ist die
Achse richtig und nur die Zahl fraglich. Streut es allein zwischen Modellen,
liegt die Ursache in einer Eigenschaft, die keine Vorab-Zahl kennt — dann hilft
keine bessere Schranke, sondern eine Grenze an der Rechnung selbst.

Verwandt: [[schranke-aus-einem-messwert-ist-geraten]],
[[begrenzt-am-falschen-mass]], [[schwelle-misst-die-falsche-achse]],
[[am-eingang-drehen]].
