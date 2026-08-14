"""Einrasten auf Merkmale (Bauplan §18.11).

Das Versprechen ist „Bohrungsachsen zur Deckung bringen", und die Prüfung ist
derselbe Satz in Zahlen: danach sind die Achsen parallel und die Mittelpunkte
an einem Ort.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.core.errors import AppError
from app.core.geom.align import align, align_matrix, frame_of, rotation_between
from app.core.geom.mesh import read_mesh
from app.core.geom.transform import apply, rotation, translation
from app.core.ingest.loader import normalise
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Document, Feature, Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def plate():
    return normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh


def hole(mesh, name: str = "hole_1") -> Feature:
    return detect(mesh)[name]


# --- die Drehung ----------------------------------------------------------------


def test_a_direction_is_turned_onto_another() -> None:
    matrix = rotation_between((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    turned = matrix @ np.array([1.0, 0.0, 0.0, 1.0])

    assert turned[:3] == pytest.approx([0.0, 0.0, 1.0], abs=1e-9)


def test_the_same_direction_needs_no_turn() -> None:
    assert rotation_between((0.0, 0.0, 1.0), (0.0, 0.0, 1.0)) == pytest.approx(np.eye(4))


def test_the_opposite_direction_is_turned_all_the_way() -> None:
    matrix = rotation_between((0.0, 0.0, 1.0), (0.0, 0.0, -1.0))
    turned = matrix @ np.array([0.0, 0.0, 1.0, 1.0])

    assert turned[:3] == pytest.approx([0.0, 0.0, -1.0], abs=1e-9)


# --- die Bezugssysteme ----------------------------------------------------------


def test_a_bore_carries_axis_and_centre() -> None:
    direction, point = frame_of(hole(plate()))

    assert abs(direction[2]) == pytest.approx(1.0, abs=1e-6), "the bores run along Z"
    assert len(point) == 3


def test_a_feature_without_an_axis_says_so() -> None:
    loop = Feature(id="edge_loop_1", kind="edge_loop", provenance="detected", params={})

    with pytest.raises(AppError):
        frame_of(loop)


# --- bore onto bore -------------------------------------------------------------


def test_two_bores_end_up_coaxial() -> None:
    """§18.11: „Bohrungsachsen zur Deckung bringen" — genau daraufhin geprüft."""
    fixed = plate()
    moving = apply(apply(plate(), rotation("y", 35.0)), translation((60.0, -20.0, 15.0)))

    target = hole(fixed, "hole_1")
    source = hole(moving, "hole_2")
    result = align(moving, source, target)

    after = detect(result)["hole_2"]
    axis_after = np.asarray(after.params["axis"], dtype=float)
    axis_target = np.asarray(target.params["axis"], dtype=float)
    assert abs(float(axis_after @ axis_target)) == pytest.approx(1.0, abs=1e-3)
    assert np.asarray(after.params["centre"]) == pytest.approx(
        np.asarray(target.params["centre"]), abs=0.05
    )


def test_flipping_turns_the_body_the_other_way() -> None:
    fixed = plate()
    moving = plate()
    straight = align_matrix(hole(moving, "hole_1"), hole(fixed, "hole_1"))
    flipped = align_matrix(hole(moving, "hole_1"), hole(fixed, "hole_1"), flip=True)

    assert not np.allclose(straight, flipped)


def test_two_faces_meet_front_to_front() -> None:
    """Ein Teil auf ein anderes zu legen heißt, dass die Normalen aufeinander
    zeigen.
    """
    fixed = plate()
    moving = apply(plate(), rotation("x", 20.0))

    target = detect(fixed)["face_1"]
    source = detect(moving)["face_1"]
    result = align(moving, source, target)

    after = detect(result)["face_1"]
    normal_after = np.asarray(after.params["normal"], dtype=float)
    normal_target = np.asarray(target.params["normal"], dtype=float)
    assert float(normal_after @ normal_target) == pytest.approx(-1.0, abs=1e-3)


# --- Als Operation ---------------------------------------------------------------


def test_aligning_is_an_operation(document: Document, profile: Profile) -> None:
    """AGENTS.md Regel 2: ein Einrasten ist eine Op, die Datei sagt also, was
    womit in Flucht gebracht wurde.
    """
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    for name in ("src_1", "src_2"):
        document.sources[name] = Source(
            id=name, kind="import", path="sources/plate_holes.stl", sha256=""
        )
        project.sources[name] = (MESHES / "plate_holes.stl").read_bytes()

    history = History(document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_2", "unit": "mm"})])
    history.apply(
        _("Drehen"),
        [
            OperationDraft(
                op="rotate_object", inputs=("obj_2",), params={"axis": "y", "angle": 25.0}
            )
        ],
    )
    history.apply(
        _("Ausrichten"),
        [
            OperationDraft(
                op="align_to_feature",
                inputs=("obj_2",),
                params={"feature": "hole_1", "target": "obj_1:hole_3"},
            )
        ],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    moved = result.scene.objects["obj_2"].features["hole_1"]
    fixed = result.scene.objects["obj_1"].features["hole_3"]
    assert np.asarray(moved.params["centre"]) == pytest.approx(
        np.asarray(fixed.params["centre"]), abs=0.05
    )


def test_a_target_that_does_not_exist_stops_the_chain(document: Document, profile: Profile) -> None:
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()

    history = History(document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    history.apply(
        _("Ausrichten"),
        [
            OperationDraft(
                op="align_to_feature",
                inputs=("obj_1",),
                params={"feature": "hole_1", "target": "obj_9:hole_1"},
            )
        ],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert not result.complete, "a target that is not there stops instead of guessing"


def test_the_operation_belongs_to_bores_and_faces() -> None:
    spec = REGISTRY.get("align_to_feature")

    assert set(spec.applies_to) == {"hole", "face"}
    assert spec in REGISTRY.for_feature("hole")
