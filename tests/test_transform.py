"""Transformationen, und dass ein Ziehen als Operation endet (§18.11, §25)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.geom.mesh import read_mesh
from app.core.geom.transform import (
    anchor_point,
    apply,
    decompose_transform,
    place_on_bed,
    rotation,
    scaling,
    snap_to_step,
    translation,
)
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Document, Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def cube():
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


# --- the arithmetic -------------------------------------------------------------


def test_moving_shifts_the_bounds_and_keeps_the_volume() -> None:
    body = cube()
    moved = apply(body, translation((5.0, -2.0, 10.0)))

    assert moved.bounds.centre == pytest.approx((5.0, -2.0, 10.0))
    assert moved.volume == pytest.approx(body.volume)
    assert body.bounds.centre == pytest.approx((0.0, 0.0, 0.0)), "the input is untouched"


def test_rotating_around_the_centre_leaves_the_centre_alone() -> None:
    body = cube()
    turned = apply(body, rotation("z", 45.0, body.bounds.centre))

    assert turned.bounds.centre == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    assert turned.volume == pytest.approx(body.volume)
    width, depth, _height = turned.bounds.size
    assert width == pytest.approx(20.0 * 2**0.5, rel=1e-6), "a cube turned 45 degrees is wider"
    assert depth == pytest.approx(width)


def test_rotating_by_ninety_degrees_swaps_two_axes() -> None:
    body = apply(cube(), scaling((1.0, 2.0, 3.0), (0.0, 0.0, 0.0)))
    turned = apply(body, rotation("x", 90.0, (0.0, 0.0, 0.0)))

    before = body.bounds.size
    after = turned.bounds.size
    assert after[0] == pytest.approx(before[0])
    assert after[1] == pytest.approx(before[2])
    assert after[2] == pytest.approx(before[1])


def test_scaling_multiplies_the_volume() -> None:
    body = cube()
    bigger = apply(body, scaling((2.0, 2.0, 2.0), body.bounds.centre))

    assert bigger.volume == pytest.approx(body.volume * 8.0)
    assert bigger.bounds.size == pytest.approx((40.0, 40.0, 40.0))
    assert bigger.bounds.centre == pytest.approx((0.0, 0.0, 0.0))


def test_scaling_by_zero_is_refused() -> None:
    with pytest.raises(ValueError):
        scaling((1.0, 0.0, 1.0))


def test_the_anchor_decides_what_stays_put() -> None:
    body = cube()
    assert anchor_point(body, "centre") == pytest.approx((0.0, 0.0, 0.0))
    assert anchor_point(body, "origin") == (0.0, 0.0, 0.0)
    assert anchor_point(body, "bed") == pytest.approx((0.0, 0.0, -10.0))


def test_placing_on_the_bed_only_moves_in_z() -> None:
    body = apply(cube(), translation((3.0, 4.0, 25.0)))
    placed = place_on_bed(body)

    assert placed.bounds.minimum[2] == pytest.approx(0.0)
    assert placed.bounds.centre[0] == pytest.approx(3.0)
    assert placed.bounds.centre[1] == pytest.approx(4.0)


def test_a_dragged_matrix_becomes_editable_steps() -> None:
    """§18.11: ein Ziehen wird zu Operationen, deren Zahlen sich weiter ändern
    lassen.
    """
    steps = decompose_transform(translation((5.0, 0.0, -3.0)))
    assert steps.offset == pytest.approx((5.0, 0.0, -3.0))
    assert steps.moves
    assert not steps.turns
    assert not steps.resizes

    turned = decompose_transform(rotation("z", 30.0))
    assert turned.axis == "z"
    assert turned.angle == pytest.approx(30.0, abs=1e-6)
    assert turned.turns
    assert not turned.moves

    resized = decompose_transform(scaling((2.0, 2.0, 2.0)))
    assert resized.scale == pytest.approx(2.0)
    assert resized.resizes


def test_a_combined_drag_yields_several_steps() -> None:
    matrix = translation((4.0, 0.0, 0.0)) @ rotation("y", 45.0)
    steps = decompose_transform(matrix)

    assert steps.moves
    assert steps.turns
    assert steps.axis == "y"
    assert steps.angle == pytest.approx(45.0, abs=1e-6)


def test_an_untouched_gizmo_yields_nothing() -> None:
    import numpy as np

    steps = decompose_transform(np.eye(4))
    assert not steps.moves
    assert not steps.turns
    assert not steps.resizes


def test_snapping_rounds_to_the_step() -> None:
    """§18.11: Einrasten gehört zur Interaktion, nicht zur Geometrie."""
    assert snap_to_step(10.4, 1.0) == pytest.approx(10.0)
    assert snap_to_step(10.6, 1.0) == pytest.approx(11.0)
    assert snap_to_step(37.0, 15.0) == pytest.approx(30.0)
    assert snap_to_step(38.0, 15.0) == pytest.approx(45.0)
    assert snap_to_step(10.4, 0.0) == pytest.approx(10.4), "a step of zero means no snapping"


# --- as operations --------------------------------------------------------------


def prepared(document: Document) -> History:
    project = new_project("centauri-carbon-2", "petg")
    document.sources.update(project.document.sources)
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/cube_clean.stl", sha256=""
    )
    history = History(document)
    history.apply(
        _("Laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})],
    )
    return history


def evaluate_with(document: Document, profile: Profile):
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    project.sources["src_1"] = (MESHES / "cube_clean.stl").read_bytes()
    return evaluate(document, profile, sources=ProjectSources(project))


@pytest.mark.parametrize(
    ("name", "params", "check"),
    [
        ("translate_object", {"dx": 5.0, "dz": 2.0}, lambda mesh: mesh.bounds.centre[0] == 5.0),
        ("rotate_object", {"axis": "z", "angle": 90.0}, lambda mesh: mesh.volume > 0),
        ("scale_object", {"factor": 2.0}, lambda mesh: mesh.bounds.size[0] == 40.0),
        ("place_on_bed", {}, lambda mesh: mesh.bounds.minimum[2] == 0.0),
    ],
)
def test_every_transformation_runs_as_an_operation(
    document: Document, profile: Profile, name: str, params: dict, check
) -> None:
    history = prepared(document)
    history.apply(
        REGISTRY.get(name).title, [OperationDraft(op=name, inputs=("obj_1",), params=params)]
    )

    result = evaluate_with(document, profile)

    assert result.complete
    assert check(result.scene.objects["obj_1"].mesh)


def test_a_transformation_is_taken_back_by_one_undo(document: Document, profile: Profile) -> None:
    """§18.11: ein Ziehen wird eine Operation, ein Undo nimmt es also zurück."""
    history = prepared(document)
    before = evaluate_with(document, profile).scene.objects["obj_1"].mesh.bounds.centre

    history.apply(
        _("Verschieben"),
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 12.0})],
    )
    moved = evaluate_with(document, profile).scene.objects["obj_1"].mesh.bounds.centre
    assert moved[0] == pytest.approx(before[0] + 12.0)

    history.undo()
    assert evaluate_with(document, profile).scene.objects[
        "obj_1"
    ].mesh.bounds.centre == pytest.approx(before)


def test_the_transformations_are_registered_completely() -> None:
    for name in ("translate_object", "rotate_object", "scale_object", "place_on_bed"):
        spec = REGISTRY.get(name)
        assert spec.category == "transform"
        assert (spec.consumes, spec.produces) == (1, 1)
        assert str(spec.doc)


def test_fit_to_size_reaches_the_given_edge(profile: Profile) -> None:
    """Der Fall, für den die Operation entstand: ein erzeugtes Netz kommt auf
    einem Einheitswürfel an und soll ein Maß bekommen, nicht einen Faktor.

    Gerechnet gegen cube_clean.stl: zwanzig Millimeter Kante, Ziel achtzig.
    """
    body = normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh
    assert max(body.bounds.size) == pytest.approx(20.0, abs=1e-6)

    project = new_project("centauri-carbon-2", "pla")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/cube_clean.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "cube_clean.stl").read_bytes()
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    history.apply(
        "Auf Maß",
        [
            OperationDraft(
                op="fit_to_size", inputs=("obj_1",), outputs=("obj_1",), params={"largest": 80.0}
            )
        ],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))
    bodies = [entry for entry in result.scene.objects.values() if entry.mesh is not None]

    assert len(bodies) == 1
    assert max(bodies[0].mesh.bounds.size) == pytest.approx(80.0, abs=1e-6)
    # Gleichmäßig: ein Würfel bleibt ein Würfel.
    assert min(bodies[0].mesh.bounds.size) == pytest.approx(80.0, abs=1e-6)
    said = [f for f in result.scene.report.findings if f.code == "transform.fitted"]
    assert said, "die Operation sagt, worauf sie gebracht hat"
    assert said[0].values["from_mm"] == pytest.approx(20.0, abs=1e-3)


def test_fit_to_size_refuses_a_body_without_extent() -> None:
    """Ein Maß braucht etwas, worauf es sich bezieht — sonst teilt die
    Rechnung durch null.

    Der Körper wird direkt gebaut: über eine Skalierung ginge es nicht, denn
    der Faktor null wird schon eine Ebene tiefer abgelehnt.
    """
    import numpy as np
    import trimesh

    from app.core.errors import GeometryError
    from app.core.geom.mesh import MeshData
    from app.core.geom.ops import fit_to_size
    from app.core.types import OpContext, SceneObject

    punkt = trimesh.Trimesh(
        vertices=np.zeros((3, 3), dtype=float), faces=np.array([[0, 1, 2]]), process=False
    )
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import Scene

    spec = REGISTRY.get("fit_to_size")
    entry = SceneObject(id="obj_1", name="Nichts", mesh=MeshData(raw=punkt))
    context = OpContext(
        scene=Scene(objects={entry.id: entry}),
        inputs=[entry],
        params=spec.params(largest=80.0),
        profile=None,
        quality="fine",
        seed=None,
        progress=lambda fraction, text: None,
        ask=lambda question, choices: choices[0],
        cancelled=NeverCancelled(),
    )

    with pytest.raises(GeometryError) as problem:
        fit_to_size(context)
    assert problem.value.suggestions, "und nennt, was jetzt zu tun ist"
