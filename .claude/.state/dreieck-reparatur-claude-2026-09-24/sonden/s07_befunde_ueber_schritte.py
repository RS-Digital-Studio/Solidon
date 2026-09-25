"""Sonde 7: Welche Befunde stehen am Ende im Bericht, wenn mehrere Schritte folgen?

Fälle (Dokumente wie im Kunden-Weg: load + repair-Schritte, evaluate):
  a) broken_selfint.stl: load → repair (Vorgabe) → repair (Selbstdurchdringungen an)
  b) pirate obj_8_Cylinder_B.stl: load → repair (SI an)  [Teile 2 → 1]
  c) broken_open.stl (bleibt nach Import offen?) → repair
"""

from __future__ import annotations

import sys
from pathlib import Path

from common import KUNDE, MESHES  # noqa: F401  (setzt sys.path)

from app.core import bootstrap
from app.core.knowledge import profiles
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Document, Source
from app.i18n import _


bootstrap.load_operations()


def run(path: Path, steps: list[dict]) -> None:
    project = new_project("centauri-carbon-2", "petg")
    document = Document(format_version=1, app_version="0.0.1")
    project.document = document
    document.sources["src_1"] = Source(id="src_1", kind="import", path=f"sources/{path.name}", sha256="")
    project.sources["src_1"] = path.read_bytes()
    history = History(document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    for params in steps:
        history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=("obj_1",), params=params)])
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = evaluate(document, profile, sources=ProjectSources(project))
    print(f"\n=== {path.name}  Schritte: load + {steps}")
    print("vollständig:", result.complete, "angehalten bei:", result.stopped_at)
    body = result.scene.objects.get("obj_1")
    if body is not None:
        mesh = body.mesh
        print("Endkörper: dicht=", mesh.is_watertight, "Teile=", mesh.component_count,
              "Volumen=", round(mesh.volume, 3))
    for f in result.scene.report.findings:
        if f.object_id not in (None, "obj_1"):
            continue
        acts = [a.id for a in f.suggestions]
        print(f"  op{f.op_id} {f.severity:7} {f.code:42} {str(f.message)[:110]} {acts}")
    sys.stdout.flush()


if __name__ == "__main__":
    run(MESHES / "broken_selfint.stl", [{}, {"self_intersections": True}])
    run(KUNDE / "pirate+ship+with+sails_stls" / "obj_8_Cylinder_B.stl", [{"self_intersections": True}])
    run(MESHES / "broken_open.stl", [{}])
    run(MESHES / "partially_open.stl", [{}])
    run(MESHES / "generated_figure.stl", [{"self_intersections": True}])
