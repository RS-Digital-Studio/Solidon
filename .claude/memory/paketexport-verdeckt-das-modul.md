---
name: paketexport-verdeckt-das-modul
description: "from app.core.scene import evaluate liefert die Funktion, nicht das Modul — der träge Paketexport trägt denselben Namen; Modulzugriff nur über import_module"
metadata: 
  node_type: memory
  type: project
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-20T12:39:45.100Z
---

`app.core.scene` exportiert über `lazy.install` den Namen `evaluate` als
**Funktion** — denselben Namen wie das Untermodul `app/core/scene/evaluate.py`.
Deshalb liefert `from app.core.scene import evaluate as evaluate_module` die
Funktion, und jeder Zugriff auf `evaluate_module._with_features` scheitert erst
zur Laufzeit (Pyright meldet es als „Cannot access attribute for FunctionType").
`import app.core.scene.evaluate as m` hilft nicht: `IMPORT_FROM` fragt zuerst
das Paketattribut, und das ist wieder die Funktion.

**Why:** Am 20.09.2026 in `tests/test_native_references.py` genau so geschrieben;
`tests/test_evaluation.py` und `test_matching_answers.py` umgehen es seit je mit
`import_module("app.core.scene.evaluate")`, ohne dass es irgendwo stand.

**How to apply:** Private Helfer eines Moduls, dessen Name ein Paketexport
verdeckt (`scene.evaluate`, `scene.history`?), immer über
`importlib.import_module("app.core.scene.evaluate")` holen. Dasselbe gilt für
jedes Paket mit `_EXPORTS`: `registry`, `agent`, `brep` — vor dem Import in
`__init__.py` nachsehen, ob der Modulname auch ein Exportname ist.
Siehe [[architektur-sonde-type-checking]].
