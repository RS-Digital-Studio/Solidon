---
name: register-zaehlen-load-operations
description: "Die Zahl der Operationen nur nach load_operations() messen — ohne sie fehlen die Bausteine; der Stand wächst (61 → 77 → 83)."
metadata: 
  node_type: memory
  type: project
  originSessionId: 6180825b-9e5b-47a2-822c-4431629af86e
  modified: 2026-08-14T03:10:04.490Z
---

Wer die Zahl der Operationen ermittelt, ruft `app.core.bootstrap.load_operations()`
und danach `REGISTRY.all()` — sonst fehlen die sechzehn `insert_*`-Operationen,
die aus der Bausteinbibliothek entstehen. Ein Zähllauf über
`pkgutil.walk_packages` kam am 11.08.2026 auf 61 statt 77 und wurde zur
Grundlage eines Fehlbefunds („die Website rundet auf"), der bis auf die
Website und ins Konzeptpapier durchschlug.

**Why:** Die Baustein-Ops werden nicht beim Import der Module registriert,
sondern beim Aufbau über `load_operations()`. Der Unterschied ist unsichtbar,
solange man nicht zählt.

**How to apply:** Zahlen über das Register immer nach `load_operations()`
messen. `tests/test_website.py` hält die beworbenen Zahlen gegen Register und
Bibliothek — bei Zweifeln an einer Zahl zuerst dort nachsehen, und die Suite
laufen lassen, bevor eine Zahl in Text oder Werbung wandert.

**Die Zahl selbst ist kein Merkposten, sie wächst.** Am 14.08.2026 waren es
**83**, davon sechs mit Tastenkürzel. Wer eine Zahl aus dem Gedächtnis in einen
Text schreibt, schreibt eine veraltete — immer neu messen.

Verwandt: [[ops-reihendurchlauf-kundensicht]], [[oberflaeche-von-hand-fahren]].
