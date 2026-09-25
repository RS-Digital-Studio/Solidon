"""Sonde 2b: Reparatur dicht an einem verwiesenen Merkmal, und der große Weg über die Auswertung.

D: Lochplatte mit zwei fehlenden Dreiecken in einer Bohrungswand, ungeschweißt
   geladen (dann flickt der Import nicht), die Bohrung in einem Folgeschritt
   genannt, dazwischen „Reparieren“.
F: Großer Weg (Dreiecksgrenze auf 1 wie in den Tests): Laden, lokale Erkennung
   an einer Bohrung, Reparatur (Kleinstteil entfernen), Bohrung ändern.

Jede Rückfrage wird notiert (Antwort: erste Wahl).
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile

_ISOLATED = tempfile.mkdtemp(prefix="solidon-sonde-")
for _variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
                  "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED
sys.path.insert(0, r"F:\3D Druck")

from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.activation import store as activation_store  # noqa: E402

activation_store.DEMO_UNTIL = None
activation_store.TRIAL_FROM = activation_store.DEMO_FROM

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive.features import forget_cache  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

load_operations()
PROFILE = profiles.make_profile("centauri-carbon-2", "petg")
OUT = Path(__file__).with_suffix(".txt")
REPO = Path(r"F:\3D Druck")


class Asked:
    def __init__(self) -> None:
        self.questions: list[tuple[str, list[str]]] = []

    def __call__(self, question: str, choices: list[str]) -> str:
        self.questions.append((question, list(choices)))
        return choices[0]


def project_with(payload: bytes, **load_params):
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/probe.stl", sha256=""
    )
    history = History(project.document)
    history.apply(
        "Laden",
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm", **load_params})],
    )
    return project, history


def report(out, title, project):
    asked = Asked()
    forget_cache()
    result = evaluate(project.document, PROFILE, sources=ProjectSources(project), ask=asked)
    out.write(f"\n# {title}\n  complete={result.complete} stopped_at={result.stopped_at}\n")
    for question, choices in asked.questions:
        out.write(f"  FRAGE: {question!r} -> {choices}\n")
    for finding in result.scene.report.findings:
        out.write(f"  Befund {finding.severity:7s} {finding.code} op={finding.op_id} "
                  f"{dict(finding.values) if finding.values else ''}\n")
    for object_id, body in result.scene.objects.items():
        out.write(f"  Körper {object_id} tri={body.mesh.triangle_count} wt={body.mesh.is_watertight}\n")
        for name, feature in sorted(body.features.items()):
            if feature.kind not in {"hole", "pin", "slot", "cone"}:
                continue
            params = feature.params
            out.write(
                f"    {name}:{feature.kind} d={float(params.get('diameter', 0)):.3f} "
                f"c={tuple(round(float(v), 2) for v in params.get('centre', ()))} "
                f"prov={feature.provenance} by={feature.created_by} n={len(feature.face_indices)}\n"
            )
    out.flush()
    return result


def wall_triangles(mesh: trimesh.Trimesh, centre_xy, radius) -> list[int]:
    centres = np.asarray(mesh.triangles_center)
    radial = np.linalg.norm(centres[:, :2] - np.asarray(centre_xy), axis=1)
    return [int(i) for i in np.flatnonzero(np.abs(radial - radius) < 0.2)]


def main() -> None:
    evaluation = importlib.import_module("app.core.scene.evaluate")
    with OUT.open("w", encoding="utf-8") as out:
        # D — zwei Dreiecke fehlen in der Wand von hole bei (25, 15)
        plate = trimesh.load(REPO / "tests/data/meshes/plate_holes.stl", force="mesh")
        wall = wall_triangles(plate, (25.0, 15.0), 2.6)
        adjacency = plate.face_adjacency
        first = wall[len(wall) // 2]
        partner = next(int(b if a == first else a) for a, b in adjacency.tolist()
                       if first in (a, b) and int(b if a == first else a) in wall)
        keep = np.ones(len(plate.faces), dtype=bool)
        keep[[first, partner]] = False
        damaged = trimesh.Trimesh(plate.vertices, plate.faces[keep], process=False)
        payload = damaged.export(file_type="stl")

        project, history = project_with(payload, weld=False)
        before = report(out, "D0 ungeschweißt geladen, zwei Dreiecke fehlen in der Bohrungswand", project)
        holes = {n: f for n, f in before.scene.objects["obj_1"].features.items() if f.kind == "hole"}
        target = min(holes, key=lambda n: np.linalg.norm(
            np.asarray(holes[n].params["centre"][:2]) - (25.0, 15.0)))
        out.write(f"  Ziel: {target}\n")
        history.apply("Reparieren", [OperationDraft(op="repair", inputs=("obj_1",), params={})])
        history.apply("Bohrung ändern", [OperationDraft(
            op="resize_hole", inputs=("obj_1",), params={"at_feature": target, "diameter": 6.0})])
        report(out, "D1 nach Reparatur, die genannte Bohrung geändert", project)

        # F — großer Weg über die Auswertung
        evaluation.FEATURE_LIMIT_TRIANGLES = 1
        crumb = trimesh.creation.box(extents=(0.6, 0.6, 0.6))
        crumb.apply_translation((80.0, 0.0, 0.0))
        payload = trimesh.util.concatenate([plate, crumb]).export(file_type="stl")
        project, history = project_with(payload)
        seed_candidates = wall_triangles(plate, (25.0, 15.0), 2.6)
        face = seed_candidates[0]
        point = tuple(float(v) for v in plate.triangles_center[face])
        normal = tuple(float(v) for v in plate.face_normals[face])
        history.apply("Lokal erkennen", [OperationDraft(
            op="detect_region", inputs=("obj_1",),
            params={"radius": 10.0, "x": point[0], "y": point[1], "z": point[2],
                    "nx": normal[0], "ny": normal[1], "nz": normal[2]})])
        local = report(out, "F0 großer Weg: geladen und lokal erkannt", project)
        found = [n for n, f in local.scene.objects["obj_1"].features.items() if f.kind == "hole"]
        out.write(f"  lokal erkannte Bohrungen: {found}\n")
        history.apply("Kleine Teile entfernen", [OperationDraft(
            op="repair", inputs=("obj_1",), params={"small_components": True})])
        if found:
            history.apply("Bohrung ändern", [OperationDraft(
                op="resize_hole", inputs=("obj_1",), params={"at_feature": found[0], "diameter": 6.0})])
        report(out, "F1 großer Weg: Reparatur, dann die lokal erkannte Bohrung geändert", project)


if __name__ == "__main__":
    main()
