---
name: ops-reihendurchlauf-kundensicht
description: "Wie sich alle Operationen von Solidon am Stück aus Kundensicht fahren lassen — und die Falle, die dabei Fehlbefunde erzeugt."
metadata: 
  node_type: memory
  type: project
  originSessionId: d474ff57-f892-4d62-b470-757ac37dd633
  modified: 2026-08-09T08:33:36.419Z
---

Alle registrierten Operationen lassen sich in einem Lauf durchfahren:
`new_project` → `History(document).apply(...)` mit `OperationDraft` →
`evaluate(document, profile, sources=ProjectSources(project))`. Ein Quader als
Eingang, zwei Objekte für die booleschen, `takes_whole_scene` bekommt alle.
92 Läufe über 77 Ops brauchen rund zwei Minuten.

**Die Falle:** Die Vorgabe aus dem Parameterschema ist **nicht** das, was der
Kunde im Dialog sieht. `OperationDialog` belegt aus der Auswahl vor — bei
`drill_hole`, `plug_hole`, `label_text` und `create_label` steht dort `z = 10`
(Oberseite des Körpers), im Schema `z = 0`. Wer nur gegen das Schema misst,
meldet Bohrungen als wirkungslos, die in der Anwendung sitzen. Jeden Fund aus
dem Reihenlauf darum in der laufenden Oberfläche gegenprüfen:
`window.run_operation(spec)` → `window._op_dialog.values()` → `accept()`.

Nützliche Zugriffe: `REGISTRY.all()`, `spec.params.spec()` für das Schema,
`window._op_actions` für die Menüeinträge, `palette_entries(REGISTRY)` für die
Befehlspalette, `MENU_TWINS` für die zusammengelegten Mesh/B-Rep-Paare (sie
haben absichtlich keinen eigenen Menüeintrag).

Für die Slicer gilt dasselbe in Grün: `SlicerSetup` von Hand zu bauen misst das
Skript, nicht Solidon — die Oberfläche setzt `machine_profile`, `base_process`
und `base_filament` als **Pfade** aus `find_profiles`. Mit Namen scheitert die
Orca-Familie ohne Grund. Siehe [[oberflaeche-von-hand-fahren]] und
[[slicer-lokal-zum-gegenmessen]].
