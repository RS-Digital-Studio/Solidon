---
name: obergrenze-ist-keine-zusicherung
description: "Eine hergeleitete Obergrenze dessen, was ein Schritt bewegen *kann*, taugt nicht als Schwelle dessen, was er bewegen *darf* — die konservative absolute Schwelle war die richtige (RM-166, 14.09.2026)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1d7e5e75-9e5f-4fd1-86b2-4be658771056
  modified: 2026-09-14T08:05:00.244Z
---

Bei `boolean._tidied` (RM-166, 14.09.2026) hob ich die Volumenzusicherung
von `is_close(…, EPS_GEOM)` auf „Oberfläche × Schweißtoleranz", weil das die
physikalische Obergrenze ist, die ein Weld am Volumen ändern kann — und weil
ich fürchtete, `EPS_GEOM` absolut ließe den Fix an großen Körpern still
zurückfallen. Beides klang hergeleitet. Gemessen: acht Tests rot, die mit
`EPS_GEOM` grün waren — eine dünne Verschneidung von 0,004 mm³ wurde auf
0,0009 verschweißt, Fasenvolumina an gemischten Ecken verschoben sich um
2,5·10⁻⁵, feste Volumen- und Dreieckszahlen der Kantentests kippten.

**Why:** Die Obergrenze beschreibt den schlimmsten Fall, den der Schritt
erzeugen *kann*. Die Zusicherung soll aber genau diesen Fall ausschließen —
sie muss also *unter* der Obergrenze liegen, nicht auf ihr. Und die Furcht
vor dem stillen Rückfall war ungemessen: Der Fix wirkte an 30 000 mm³ mit
`EPS_GEOM`, weil ein Weld unter der Toleranz nur Rechenrauschen bewegt.

**How to apply:** Eine Schwelle, die bereits im Nachbarcode steht
(`repair.unify_normals`: `EPS_GEOM` absolut), zuerst übernehmen und den
Fall messen, den man fürchtet — erst wenn er wirklich eintritt, die Schwelle
begründet ändern. Siehe [[schranke-aus-einem-messwert-ist-geraten]],
[[zwei-schwellen-eine-frage]] und [[fix-der-nicht-gruen-macht]].
