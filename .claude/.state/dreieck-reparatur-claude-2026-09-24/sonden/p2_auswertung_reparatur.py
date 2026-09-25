"""Sonde 2: Der Weg über die Auswertung — Import, Merkmalsschritte, Reparatur, Folgeschritte.

Fragt: Bleiben die Namen der Merkmale über einen verändernden Reparaturschritt
stabil, laufen Passung und spätere Schritte weiter, und fragt die Auswertung
etwas, das sie nicht fragen müsste? Jede Rückfrage wird mitgeschrieben und
mit der ersten Antwort beantwortet — gezählt wird, ob überhaupt gefragt wird.

Isoliert wie die Suite: Nutzerverzeichnisse in einen Temp-Ordner, Demo-Frist
wie in ``tests/conftest.py`` ausgeschaltet. Schreibt nichts in ``app/`` oder
``tests/``.
"""

from __future__ import annotations

import os
import sys
import tempfile

_ISOLATED = tempfile.mkdtemp(prefix="solidon-sonde-")
for _variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
                  "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED

sys.path.insert(0, r"F:\3D Druck")

from collections import Counter  # noqa: E402
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
from app.core.types import Fit, FeatureRef, Source  # noqa: E402

OUT = Path(__file__).with_suffix(".txt")
REPO = Path(r"F:\3D Druck")

load_operations()
PROFILE = profiles.make_profile("centauri-carbon-2", "petg")


class Asked:
    """Jede Frage wird notiert und mit der ersten Wahl beantwortet."""

    def __init__(self) -> None:
        self.questions: list[tuple[str, list[str]]] = []

    def __call__(self, question: str, choices: list[str]) -> str:
        self.questions.append((question, list(choices)))
        return choices[0]


def listing(scene_object) -> list[str]:
    rows = []
    for name, feature in sorted(scene_object.features.items()):
        params = feature.params
        dims = ", ".join(
            f"{key}={float(params[key]):.3f}"
            for key in ("diameter", "area", "depth", "length")
            if isinstance(params.get(key), int | float) and not isinstance(params.get(key), bool)
        )
        centre = params.get("centre")
        where = ("(" + ", ".join(f"{float(v):.2f}" for v in centre) + ")") if isinstance(
            centre, tuple | list) else "?"
        rows.append(
            f"{name}:{feature.kind}[{dims}]@{where} prov={feature.provenance} "
            f"rec={feature.recognised} by={feature.created_by} n={len(feature.face_indices)} "
            f"src={dict(feature.measure_sources) if feature.measure_sources else {}}"
        )
    return rows


def run(out, title: str, build) -> None:
    out.write(f"\n# {title}\n")
    forget_cache()
    project, history, steps = build()
    asked = Asked()
    result = evaluate(project.document, PROFILE, sources=ProjectSources(project), ask=asked)
    out.write(f"  complete={result.complete} stopped_at={result.stopped_at}\n")
    for question, choices in asked.questions:
        out.write(f"  FRAGE: {question!r} -> {choices}\n")
    for finding in result.scene.report.findings:
        out.write(
            f"  Befund {finding.severity:7s} {finding.code} op={finding.op_id} "
            f"{dict(finding.values) if finding.values else ''}\n"
        )
    for object_id, scene_object in result.scene.objects.items():
        out.write(f"  Körper {object_id} tri={scene_object.mesh.triangle_count} "
                  f"wt={scene_object.mesh.is_watertight} reserviert={sorted(scene_object.reserved_feature_ids)}\n")
        for row in listing(scene_object):
            out.write(f"    {row}\n")
    out.flush()
    return project, history, result


def plate_with_crumb() -> bytes:
    plate = trimesh.load(REPO / "tests/data/meshes/plate_holes.stl", force="mesh")
    crumb = trimesh.creation.box(extents=(0.6, 0.6, 0.6))
    crumb.apply_translation((80.0, 0.0, 0.0))
    return trimesh.util.concatenate([plate, crumb]).export(file_type="stl")


def base_project(payload: bytes, **load_params):
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


def main() -> None:
    with OUT.open("w", encoding="utf-8") as out:
        # A — Kleinstteil entfernen; Bohrungen und eine gebohrte Bohrung bleiben unberührt.
        def before_repair():
            project, history = base_project(plate_with_crumb())
            history.apply(
                "Bohren",
                [OperationDraft(op="drill_hole", inputs=("obj_1",),
                                params={"diameter": 4.0, "x": 10.0, "y": 10.0, "z": 4.0,
                                        "axis": "z", "depth": 0.0})],
            )
            return project, history, []

        project, history, first = run(out, "A0 vor der Reparatur", before_repair)
        body = first.scene.objects["obj_1"]
        holes = sorted(name for name, feature in body.features.items() if feature.kind == "hole")
        out.write(f"  Bohrungen vor der Reparatur: {holes}\n")
        generated = [n for n in holes if body.features[n].provenance == "generated"]
        detected = [n for n in holes if body.features[n].provenance == "detected"]

        def with_repair():
            project.document.fits.append(
                Fit(name="probe", a=FeatureRef("obj_1", detected[0]),
                    b=FeatureRef("obj_1", generated[0] if generated else detected[1]),
                    kind="clearance", tolerance="auto:petg")
            )
            history.apply(
                "Kleine Teile entfernen",
                [OperationDraft(op="repair", inputs=("obj_1",), params={"small_components": True})],
            )
            history.apply(
                "Bohrung ändern",
                [OperationDraft(op="resize_hole", inputs=("obj_1",),
                                params={"at_feature": detected[1], "diameter": 6.0})],
            )
            if generated:
                history.apply(
                    "Gebohrte Bohrung ändern",
                    [OperationDraft(op="resize_hole", inputs=("obj_1",),
                                    params={"at_feature": generated[0], "diameter": 3.0})],
                )
            return project, history, []

        run(out, "A1 nach Reparatur (Kleinstteil) + Passung + Folgeschritte", with_repair)

        # B — Ungeschweißt geladen, dann Reparieren (verschweißt, schließt nichts).
        def unwelded():
            payload = (REPO / "tests/data/meshes/plate_countersunk.stl").read_bytes()
            project, history = base_project(payload, weld=False)
            return project, history, []

        project_b, history_b, result_b = run(out, "B0 ungeschweißt geladen", unwelded)
        names_b = sorted(result_b.scene.objects["obj_1"].features)

        def unwelded_repaired():
            hole = next(n for n in names_b if n.startswith("hole"))
            cone = next((n for n in names_b if n.startswith("cone")), hole)
            project_b.document.fits.append(
                Fit(name="probe", a=FeatureRef("obj_1", hole), b=FeatureRef("obj_1", cone),
                    kind="clearance", tolerance="auto:petg")
            )
            history_b.apply(
                "Reparieren",
                [OperationDraft(op="repair", inputs=("obj_1",), params={})],
            )
            history_b.apply(
                "Bohrung ändern",
                [OperationDraft(op="resize_hole", inputs=("obj_1",),
                                params={"at_feature": hole, "diameter": 6.0})],
            )
            return project_b, history_b, []

        run(out, "B1 ungeschweißt geladen, repariert, Bohrung geändert", unwelded_repaired)

        # C — Zwei sich durchdringende Quader, Bohrung im einen, Durchdringung auflösen.
        def overlapping():
            one = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
            two = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
            two.apply_translation((12.0, 0.0, 0.0))
            payload = trimesh.util.concatenate([one, two]).export(file_type="stl")
            project, history = base_project(payload)
            history.apply(
                "Bohren",
                [OperationDraft(op="drill_hole", inputs=("obj_1",),
                                params={"diameter": 4.0, "x": -5.0, "y": 0.0, "z": 10.0,
                                        "axis": "z", "depth": 0.0})],
            )
            return project, history, []

        project_c, history_c, result_c = run(out, "C0 zwei Quader, gebohrt", overlapping)
        names_c = sorted(result_c.scene.objects["obj_1"].features)

        def overlapping_repaired():
            hole = next((n for n in names_c if "hole" in n), None)
            history_c.apply(
                "Durchdringungen auflösen",
                [OperationDraft(op="repair", inputs=("obj_1",),
                                params={"self_intersections": True})],
            )
            if hole:
                history_c.apply(
                    "Bohrung ändern",
                    [OperationDraft(op="resize_hole", inputs=("obj_1",),
                                    params={"at_feature": hole, "diameter": 5.0})],
                )
            return project_c, history_c, []

        run(out, "C1 Durchdringung aufgelöst, Bohrung geändert", overlapping_repaired)


if __name__ == "__main__":
    main()
