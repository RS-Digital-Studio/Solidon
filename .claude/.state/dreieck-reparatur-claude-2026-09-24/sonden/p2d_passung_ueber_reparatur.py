"""Sonde 2d: Eine Passung Zapfen↔Bohrung über zwei Körper, dazwischen „Kleine Teile entfernen“ am Bohrungskörper."""

from __future__ import annotations

import os
import sys
import tempfile

_ISOLATED = tempfile.mkdtemp(prefix="solidon-sonde-")
for _variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
                  "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED
sys.path.insert(0, r"F:\3D Druck")

from pathlib import Path  # noqa: E402

import trimesh  # noqa: E402

from app.core.activation import store as activation_store  # noqa: E402

activation_store.DEMO_UNTIL = None
activation_store.TRIAL_FROM = activation_store.DEMO_FROM

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Fit, FeatureRef, Source  # noqa: E402

load_operations()
PROFILE = profiles.make_profile("centauri-carbon-2", "petg")
OUT = Path(__file__).with_suffix(".txt")
REPO = Path(r"F:\3D Druck")


def asked_log():
    questions = []

    def ask(question, choices):
        questions.append((question[:120], choices))
        return choices[0]

    return ask, questions


def report(out, title, project):
    ask, questions = asked_log()
    result = evaluate(project.document, PROFILE, sources=ProjectSources(project), ask=ask)
    out.write(f"\n# {title}: complete={result.complete} stopped_at={result.stopped_at} Fragen={questions}\n")
    for finding in result.scene.report.findings:
        if finding.code.startswith(("fit", "feature", "perceive", "repair")):
            out.write(f"  {finding.severity} {finding.code} op={finding.op_id} {dict(finding.values)}\n")
    for object_id, body in result.scene.objects.items():
        rounds = sorted((n, f.kind, round(float(f.params["diameter"]), 3))
                        for n, f in body.features.items() if f.kind in {"hole", "pin"})
        out.write(f"  {object_id}: {rounds}\n")
    out.flush()
    return result


def main() -> None:
    plate = trimesh.load(REPO / "tests/data/meshes/plate_holes.stl", force="mesh")
    crumb = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    crumb.apply_translation((70.0, 0.0, 0.0))
    pin = trimesh.creation.cylinder(radius=2.45, height=10.0, sections=64)
    project = new_project("centauri-carbon-2", "petg")
    for key, mesh in (("src_1", trimesh.util.concatenate([plate, crumb])), ("src_2", pin)):
        project.sources[key] = mesh.export(file_type="stl")
        project.document.sources[key] = Source(id=key, kind="import", path=f"sources/{key}.stl",
                                               sha256="")
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"}),
                            OperationDraft(op="load", params={"source": "src_2", "unit": "mm"})])
    with OUT.open("w", encoding="utf-8") as out:
        first = report(out, "geladen", project)
        hole = sorted(n for n, f in first.scene.objects["obj_1"].features.items() if f.kind == "hole")[0]
        pin_id = next(n for n, f in first.scene.objects["obj_2"].features.items() if f.kind == "pin")
        project.document.fits.append(Fit(name="Stift", a=FeatureRef("obj_2", pin_id),
                                         b=FeatureRef("obj_1", hole), kind="clearance",
                                         tolerance="auto:petg"))
        report(out, "mit Passung", project)
        history.apply("Kleine Teile entfernen", [OperationDraft(
            op="repair", inputs=("obj_1",), params={"small_components": True})])
        report(out, "nach Reparatur des Bohrungskörpers", project)


if __name__ == "__main__":
    main()
