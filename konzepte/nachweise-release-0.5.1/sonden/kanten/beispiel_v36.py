"""Schreibt ``edge_groups_v36.p3d`` — mit dem Stand, der Format 36 schreibt (RM-279).

Aufruf aus der Wurzel eines Arbeitsbaums auf 1163c30d7:
python beispiel_v36.py <zieldatei>. Zwei Quader 40 x 30 x 20 mit Querbohrung
Ø 6 längs Y, einer als Netz (obj_1), einer exakt (obj_2, 60 mm daneben); an
beiden *Verrunden* R 1 an „waagerecht“. Der Radius des exakten Schritts wird
danach von 1,5 auf 1 geändert, damit die Datei auch eine gespeicherte Fassung
in ``changes.before``/``after`` trägt. Gibt die Volumina aus.
"""

import os
import sys
from pathlib import Path

TREE = os.getcwd()
sys.path.insert(0, TREE)
import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(Path(TREE).resolve()), app.__file__
from app.core.bootstrap import load_operations  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.scene.evaluate import evaluate  # noqa: E402
from app.core.scene.history import History, OperationDraft  # noqa: E402
from app.core.scene.migrations import FORMAT_VERSION  # noqa: E402
from app.core.scene.project import ProjectSources, new_project, save  # noqa: E402
from app.i18n import _  # noqa: E402

assert FORMAT_VERSION == 36, FORMAT_VERSION
load_operations()
target = Path(sys.argv[1])
project = new_project(printer="centauri-carbon-2", material="petg")
history = History(project.document)
box = {"width": 40.0, "depth": 30.0, "height": 20.0}
history.apply(_("Quader"), [OperationDraft(op="create_box", params=box)])
history.apply(
    _("Bohrung setzen"),
    [
        OperationDraft(
            op="drill_hole",
            params={"diameter": 6.0, "x": 0.0, "y": -15.0, "z": 10.0, "axis": "y", "depth": 0.0},
            inputs=("obj_1",),
        )
    ],
)
history.apply(_("Quader"), [OperationDraft(op="create_brep_box", params=box)])
history.apply(
    _("Verschieben"),
    [OperationDraft(op="translate_object", params={"dx": 60.0}, inputs=("obj_2",))],
)
history.apply(
    _("Bohrung setzen"),
    [
        OperationDraft(
            op="drill_hole",
            params={"diameter": 6.0, "x": 60.0, "y": -15.0, "z": 10.0, "axis": "y", "depth": 0.0},
            inputs=("obj_2",),
        )
    ],
)
history.apply(
    _("Verrunden"),
    [
        OperationDraft(
            op="fillet_edges", params={"radius": 1.0, "edges": "horizontal"}, inputs=("obj_1",)
        )
    ],
)
history.apply(
    _("Verrunden"),
    [
        OperationDraft(
            op="fillet_edges", params={"radius": 1.5, "edges": "horizontal"}, inputs=("obj_2",)
        )
    ],
)
last = project.document.ops[-1]
history.change_params(last.id, {"radius": 1.0})

profile = profiles.make_profile("centauri-carbon-2", "petg")
result = evaluate(project.document, profile, sources=ProjectSources(project))
assert result.complete, [f.code for f in result.scene.report.findings]
for object_id, entry in result.scene.objects.items():
    print(object_id, entry.kind, f"{entry.mesh.volume:.4f}")
save(project, target)
print("geschrieben:", target)
