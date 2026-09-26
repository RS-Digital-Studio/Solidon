---
name: heiles-netz-nicht-verschweissen
description: Ein Netz, an dem jede Kante genau zwei Flächen trägt, wird nicht verschweißt; eine Schweißregel wird am Importkorpus gegen HEAD gemessen, nicht an den Testkörpern (RM-239, 26.09.2026)
metadata:
  type: project
---

Die erste Fassung des zweistufigen Verschweißens (`repair.weld`) legte auch
an heilen Netzen jede Kante bis `EPS_GEOM` zusammen. Die Testkörper blieben
grün; das Einlesen aller 521 Körper aus `F:\3D Dateien` gegen einen
Arbeitsbaum auf HEAD zeigte sechs Körper, die vorher dicht waren und danach
nicht mehr — Deckel, beide Drehdeckel, `stuhl.glb` (129 Teile), `tisch.glb`
(257 Teile), `image_00001_.glb`. Winzige Kanten gibt es an echten Modellen
reichlich, und an einem heilen Netz sind sie kein Schaden.

Die Regel seitdem: Trägt jede Kante **nach der vollen Zählung** genau zwei
Flächen, bleibt das Netz unberührt. Die volle Zählung und nicht die lebende,
damit ein Netz mit flach gedrückten Flächen (die Senkplatte, von trimesh
gelesen) weiter als beschädigt gilt.

**Why:** Eine Regel über alle Punktgruppen wirkt an jedem Körper, und die
Testdaten decken nur die Fälle ab, für die sie gebaut wurde.

**How to apply:** Vor einer Änderung an Verschweißen oder Reparatur
`.claude/.state/rm-232-erster-klick-2026-09-25/rm239/korpus_import.py` zweimal
fahren — `<arbeitsbaum-HEAD> <alt.jsonl>` und `"F:/3D Druck" <neu.jsonl>` —
und je Körper `closed`, `codes` und `parts` vergleichen; gezählt wird
„dicht → offen", nicht die Summe. Zeiten nur abwechselnd messen, weil andere
Sitzungen die Maschine teilen. Verwandt: [[kernausgabe-ist-per-index-dicht]],
[[verifikation-an-echten-modellen]], [[rueckfallregel-an-ihren-treffern-messen]].
