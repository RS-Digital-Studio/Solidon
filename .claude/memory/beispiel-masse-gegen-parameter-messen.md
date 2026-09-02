---
name: beispiel-masse-gegen-parameter-messen
description: "Ein Beispielprojekt kann still falsch sein, wenn eine Op mit ihren Vorgabewerten läuft — die Dose war 40,01 statt 40,00 hoch, die Schrift unsichtbar im Boden; die Maße des Ergebnisses gegen die Parameter messen, je Schritt"
metadata: 
  node_type: memory
  type: project
  originSessionId: c1806dc1-e846-4999-89d4-b8c3c4636d14
  modified: 2026-09-02T17:42:45.458Z
---

Gemessen am 02.09.2026 am mitgelieferten Beispiel `dose-mit-deckel.p3d`:
Objektbaum und Statuszeile zeigten 40,01 mm bei Parameter 40,00. Schritt für
Schritt (Dokument gekürzt, je Transaktion ausgewertet): Die Beschriftung
senkte den Körper um 0,01 unter den Boden, „Anordnen" hob ihn danach aufs
Bett. Die Op `label_text` stand ohne Ort und Richtung im Beispiel — also mit
ihren **Vorgaben** (0, 0, 0) und Normale nach oben —, und das ist der Boden
einer Dose auf dem Bett: Die Schrift wurde erhaben ins Material gebaut, war
unsichtbar, nur die Überlappung ragte heraus. Kein Test sah es
(`test_examples` öffnet und rechnet), kein Befund sagte es (die
Volumenprüfung sah eine Änderung, die Komponentenprüfung sah nichts
Loses).

**Why:** Vorgabewerte einer Operation sind für den Dialog gedacht, in dem
der Klick auf die Fläche sie überschreibt. Ein Beispiel, das die Op ohne
diese Werte anlegt, nimmt die Vorgaben — und die können an genau diesem
Körper unsichtbar falsch sein. Das Beispiel ist erzeugt, reproduzierbar
und getestet, und trotzdem falsch: Die Tests fragten, ob es öffnet, nicht,
ob seine Maße stimmen.

**How to apply:**
- Für jedes erzeugte Beispiel die Hülle des Ergebnisses gegen die
  Parameter halten (Breite/Tiefe/Höhe) und jede Abweichung erklären können
  — 55,60 bei einer erhabenen Schrift auf der Vorderseite ist erklärbar,
  40,01 war es nicht.
- Wandert ein Maß, das Dokument je Transaktion kürzen und die Hülle je
  Schritt messen — die Ursache steht in dem Schritt, in dem sie sich ändert.
- Eine Op, die im Beispiel ohne Ort und Richtung steht, trägt sie
  ausdrücklich ein (`x, y, z, nx, ny, nz`), so wie der Klick es täte.
- Was eine Vorgabe stumm falsch machen kann, bekommt einen Befund in der
  Op: `label.buried` misst, wie viel der Schrift über der Fläche ankommt.

Siehe [[rezept-ist-der-fund-op-ist-die-ursache]] (derselbe Schluss: der
Fund im Beispiel, die fehlende Prüfung in der Op) und
[[gestellte-daten-widersprechen-echten-daneben]].
