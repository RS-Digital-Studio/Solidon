"""Transformationen, und dass ein Ziehen als Operation endet (§18.11, §25)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.build_area import fits_xy, printable_area
from app.core.geom.mesh import read_mesh
from app.core.geom.transform import (
    anchor_point,
    apply,
    decompose_transform,
    is_rigid,
    place_on_bed,
    rotation,
    scaling,
    snap_to_marks,
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


# --- die Rechnung ---------------------------------------------------------------


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


def test_even_a_small_scale_is_not_classified_as_a_rigid_motion() -> None:
    """Die relative Vorgabe von ``allclose`` ließ Maßstäbe bis 0,001 % durch.

    Dann reichte ``moved_body`` sie an OpenCASCADE weiter und behauptete, der
    Körper sei unter einer starren Bewegung exakt geblieben. Die Form hatte
    sich aber geändert; nur echte Orthonormalität darf den B-Rep-Weg nehmen.
    """
    assert not is_rigid(scaling((1.000005, 1.0, 1.0)))


def test_rotation_and_mirroring_are_rigid_motions() -> None:
    assert is_rigid(rotation("z", 37.0))
    assert is_rigid(scaling((-1.0, 1.0, 1.0)))


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


def test_snapping_to_marks_holds_only_near_a_named_place() -> None:
    """Freie Fahrt, kurzes Einrasten — an Stellen, die etwas bedeuten.

    Das Geschwister von ``snap_to_step``: Jenes rastet auf einem gleichmäßigen
    Raster ein, dieses auf einer Handvoll benannter Stellen — die halbe
    Wandstärke, die Rückseite, der Grund einer Tasche (Robert, 09.09.2026: „bei
    mitten und außenkanten immer so leicht einrasten, wenn wir in der nähe
    sind").
    """
    marken = (10.0, 20.0)

    # In der Nähe hält die Marke, außerhalb bleibt der rohe Wert stehen.
    assert snap_to_marks(10.4, marken, 1.0) == pytest.approx(10.0)
    assert snap_to_marks(9.6, marken, 1.0) == pytest.approx(10.0)
    assert snap_to_marks(12.0, marken, 1.0) == pytest.approx(12.0), "wer weiterzieht, kommt heraus"
    assert snap_to_marks(19.5, marken, 1.0) == pytest.approx(20.0)

    # Ohne Zone und ohne Marken passiert nichts — beides sind die Fälle, in
    # denen die Ansicht keinen Maßstab kennt.
    assert snap_to_marks(10.4, marken, 0.0) == pytest.approx(10.4)
    assert snap_to_marks(10.4, (), 5.0) == pytest.approx(10.4)

    # Zwei Marken in Reichweite: die nähere gewinnt …
    assert snap_to_marks(10.4, (10.0, 11.0), 2.0) == pytest.approx(10.0)
    assert snap_to_marks(10.7, (10.0, 11.0), 2.0) == pytest.approx(11.0)
    # … und bei genau gleichem Abstand die kleinere, damit dieselbe Eingabe
    # immer dasselbe ergibt (§15.1).
    assert snap_to_marks(10.5, (10.0, 11.0), 2.0) == pytest.approx(10.0)

    # Die Zone zählt beidseitig und schließt ihren Rand ein.
    assert snap_to_marks(11.0, (10.0,), 1.0) == pytest.approx(10.0)
    assert snap_to_marks(11.0, (10.0,), 0.999) == pytest.approx(11.0)


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
        expected = (-1, -1) if name in {"translate_object", "rotate_object"} else (1, 1)
        assert (spec.consumes, spec.produces) == expected
        assert str(spec.doc)


def test_scaling_reaches_from_a_unit_cube_to_a_build_volume() -> None:
    """Hundert war zu wenig, und die Ablehnung kam an der falschen Stelle an.

    Was ein Bildmodell liefert, ist auf einen Einheitswürfel normiert: die vier
    Möbel eines Puppenhauses maßen 0,6 bis 2,0 mm. Der Schrank hätte den Faktor
    141,7 gebraucht, `scale_object` deckelte bei hundert — und im Chat blieb
    ein Körper von 1,3 mm stehen.
    """
    from app.core.errors import ValidationError
    from app.core.registry.params import validate

    spec = REGISTRY.get("scale_object")
    assert validate(spec.params, {"factor": 141.7}).factor == pytest.approx(141.7)
    with pytest.raises(ValidationError) as raised:
        validate(spec.params, {"factor": 1001.0})
    assert raised.value.values["maximum"] == 1000.0


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
    # Ohne ``free_spot`` — wie jeder vor dem 28.09.2026 gespeicherte Schritt —
    # bleibt die Mitte, wo sie war, auch unter der Platte.
    assert tuple(bodies[0].mesh.bounds.centre) == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)
    assert bodies[0].plate == 0


def test_a_later_fit_to_size_settles_the_earlier_one(profile: Profile) -> None:
    """RM-676: Nur der letzte *Auf Maß bringen* eines Körpers bietet *Größe ändern* an.

    Ein späterer Schritt desselben Körpers bringt ihn ohnehin auf sein eigenes
    Maß; das Maß des früheren zu ändern bewegte am Ende nichts außer der Rechnung
    dazwischen. Weg 3 legt zwei davon an (Arbeitsgröße vor der Reparatur,
    Kundenmaß danach), und im Bericht steht nur der zweite.
    """
    project = new_project("centauri-carbon-2", "pla")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/cube_clean.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "cube_clean.stl").read_bytes()
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    for largest in (80.0, 50.0):
        history.apply(
            "Auf Maß",
            [
                OperationDraft(
                    op="fit_to_size",
                    inputs=("obj_1",),
                    outputs=("obj_1",),
                    params={"largest": largest},
                )
            ],
        )
    later = project.document.ops[-1].id

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    said = [f for f in result.scene.report.findings if f.code == "transform.fitted"]
    assert [(f.op_id, f.values["to_mm"]) for f in said] == [(later, 50.0)], (
        "der frühere Befund führte *Größe ändern* in einen Schritt ohne Wirkung aufs Maß"
    )
    assert max(result.scene.objects["obj_1"].mesh.bounds.size) == pytest.approx(50.0, abs=1e-6)


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


# --- Der genannte Drehpunkt: mehrere Körper um dieselbe Stelle ------------------


def test_a_named_pivot_turns_around_a_point_outside_the_body(
    document: Document, profile: Profile
) -> None:
    """Ein Körper dreht um eine Stelle, die nicht seine eigene ist.

    **Der Fall, für den es den Punkt gibt.** Ohne ihn liest ``anchor_point``
    den Bezug aus dem *eigenen* Netz: Bei zwei markierten Körpern drehte jeder
    um sich selbst, und die Anordnung, die der Kunde gerade hergestellt hat,
    fiele auseinander.

    Gemessen am Mittelpunkt: Der Würfel steht mittig um den Ursprung, eine
    Drehung um 180° um einen Punkt bei x = 10 muss ihn nach x = 20 tragen.
    """
    history = prepared(document)
    before = evaluate_with(document, profile).scene.objects["obj_1"].mesh.bounds.centre

    history.apply(
        _("Drehen"),
        [
            OperationDraft(
                op="rotate_object",
                inputs=("obj_1",),
                params={
                    "axis": "z",
                    "angle": 180.0,
                    "about": "point",
                    "pivot_x": 10.0,
                    "pivot_y": 0.0,
                    "pivot_z": 0.0,
                },
            )
        ],
    )
    after = evaluate_with(document, profile).scene.objects["obj_1"].mesh.bounds.centre

    assert after[0] == pytest.approx(2 * 10.0 - before[0], abs=1e-6), (
        f"eine 180°-Drehung um x=10 spiegelt den Mittelpunkt an dieser Stelle: "
        f"aus {before[0]} muss {2 * 10.0 - before[0]} werden, wurde {after[0]}"
    )
    assert after[1] == pytest.approx(-before[1], abs=1e-6)


def test_without_the_named_pivot_nothing_changes(document: Document, profile: Profile) -> None:
    """Die Vorgabe ist neutral — eine Datei ohne Punkt rechnet wie vorher.

    **Die Gegenprobe zur Migration, und sie gehört hierher und nicht in die
    Zusicherung.** Die drei Zahlen sind neu; wenn ihre Vorgabe das Verhalten
    verschöbe, änderte sich jedes bestehende Projekt still mit. Geprüft wird
    deshalb gegen den Anker, den alte Dateien tragen: ``centre`` lässt den
    Mittelpunkt stehen, egal was in ``pivot_x`` steht.
    """
    history = prepared(document)
    before = evaluate_with(document, profile).scene.objects["obj_1"].mesh.bounds.centre

    history.apply(
        _("Drehen"),
        [
            OperationDraft(
                op="rotate_object",
                inputs=("obj_1",),
                # about fehlt: die Vorgabe centre gilt, wie in jeder alten Datei
                params={"axis": "z", "angle": 90.0},
            )
        ],
    )
    after = evaluate_with(document, profile).scene.objects["obj_1"].mesh.bounds.centre

    assert after == pytest.approx(before, abs=1e-6), (
        f"ohne genannten Punkt bleibt der Mittelpunkt stehen — aus {before} wurde {after}"
    )


def test_a_named_pivot_of_zero_is_a_point_and_not_a_missing_value(
    document: Document, profile: Profile
) -> None:
    """Der Nullpunkt ist ein Drehpunkt und kein „nichts angegeben".

    **Deshalb entscheidet der Anker und nicht die Zahl.** Wer „nicht gesetzt"
    an ``pivot == (0, 0, 0)`` erkennen wollte, könnte „um den Ursprung" nicht
    davon unterscheiden — und eine Drehung um den Ursprung ist genau das, was
    ein Körper braucht, der neben ihm steht.
    """
    history = prepared(document)
    history.apply(
        _("Verschieben"),
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 30.0})],
    )
    versetzt = evaluate_with(document, profile).scene.objects["obj_1"].mesh.bounds.centre

    history.apply(
        _("Drehen"),
        [
            OperationDraft(
                op="rotate_object",
                inputs=("obj_1",),
                params={"axis": "z", "angle": 180.0, "about": "point"},
            )
        ],
    )
    gedreht = evaluate_with(document, profile).scene.objects["obj_1"].mesh.bounds.centre

    assert gedreht[0] == pytest.approx(-versetzt[0], abs=1e-6), (
        f"um den Ursprung gedreht muss aus x={versetzt[0]} x={-versetzt[0]} werden, "
        f"wurde {gedreht[0]} — der Nullpunkt wurde als „nicht gesetzt“ gelesen"
    )


# --- auf dem Bett gehalten (§29) ------------------------------------------------


def test_a_lettering_resize_keeps_a_saved_drag_clear(profile: Profile) -> None:
    """Der Handzug bleibt nach 100 → 130 mm auch innerhalb des Betts kollisionsfrei."""
    import dataclasses

    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.prepare import check_collisions
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    def run(name, entries, values, surroundings=None):
        spec = REGISTRY.get(name)
        return spec.fn(
            OpContext(
                scene=Scene(objects={entry.id: entry for entry in surroundings or entries}),
                inputs=entries,
                params=spec.params(**values),
                profile=profile,
                quality="fine",
                seed=7,
                progress=lambda *args: None,
                ask=lambda *args: None,
                cancelled=NeverCancelled(),
            )
        )

    def lettering(size):
        body = run("create_label", [], {"text": "Solidon3D", "size": size, "depth": 13.0}).outputs[
            0
        ]
        body = dataclasses.replace(body, id="obj_1")
        parts = run("split_bodies", [body], {"count": 9}).outputs
        parts = [dataclasses.replace(part, id=f"obj_{i + 1}") for i, part in enumerate(parts)]
        oriented = run("orient_for_print", parts, {"thorough": True}).outputs
        return [run("place_on_bed", [part], {}).outputs[0] for part in oriented]

    def collisions(body, surroundings):
        return [
            finding
            for other in surroundings
            if other.id != body.id and other.plate == body.plate
            for finding in check_collisions([body.mesh, other.mesh])
        ]

    small, large = lettering(100.0), lettering(130.0)
    offset = {"dx": -70.0, "dy": -100.0}
    before = run("translate_object", [small[2]], offset, small).outputs[0]
    assert fits_xy(before.mesh, printable_area(profile.printer))
    assert not collisions(before, small)
    unchanged = run("translate_object", [small[2]], {**offset, "keep_on_bed": True}, small).outputs[
        0
    ]
    assert unchanged.mesh.bounds.centre == pytest.approx(before.mesh.bounds.centre)

    # Freie Modellierung führt die Zahlen auch nach der Größenänderung aus.
    free = run("translate_object", [large[2]], offset, large).outputs[0]
    assert fits_xy(free.mesh, printable_area(profile.printer))
    assert collisions(free, large), "the saved drag must reproduce the reported overlap"

    # **Und innerhalb der Fläche bleibt der Körper, wo er ist** (Entscheidung
    # Robert, 18.09.2026). Die Bindung hielt bis dahin zwei Bedingungen —
    # innerhalb der Fläche *und* ohne Überschneidung —, und damit war das
    # Zusammenschieben zweier Teile über den Griff nicht mehr zu machen. Die
    # Überschneidung wird gemeldet, nicht behoben.
    result = run("translate_object", [large[2]], {**offset, "keep_on_bed": True}, large)
    held = result.outputs[0]
    assert fits_xy(held.mesh, printable_area(profile.printer))
    assert held.mesh.bounds.centre == pytest.approx(free.mesh.bounds.centre)
    assert not any(finding.code == "transform.rearranged_on_bed" for finding in result.findings)
    assert held.plate == large[2].plate
    assert held.mesh.bounds.minimum[2] == pytest.approx(large[2].mesh.bounds.minimum[2])
    assert result.transform is not None
    transformed = apply(as_mesh_data(large[2].mesh), result.transform)
    assert transformed.bounds.centre == pytest.approx(held.mesh.bounds.centre)


def loaded_twice(document: Document) -> History:
    """Zwei Würfel, damit ein Platz auch belegt sein kann."""
    history = prepared(document)
    history.apply(
        _("Laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})],
    )
    return history


def test_a_move_beyond_the_edge_comes_back(document: Document, profile: Profile) -> None:
    """Ein Zug über den Rand endet auf der Fläche — und am nächsten Platz.

    Der Anlass war kein Zug, sondern eine Parameteränderung darüber: Der Zug
    speichert einen Weg, und wenn *Druckoptimal ausrichten* danach neu
    anordnet, führt derselbe Weg neben das Bett. Geprüft wird die Wirkung, und
    die ist dieselbe.
    """
    history = prepared(document)
    history.apply(
        _("Verschieben"),
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_1",),
                params={"dx": 300.0, "keep_on_bed": True},
            )
        ],
    )

    result = evaluate_with(document, profile)
    mesh = result.scene.objects["obj_1"].mesh
    area = printable_area(profile.printer)

    assert fits_xy(mesh, area), f"steht bei x={mesh.bounds.centre[0]} und damit neben dem Bett"
    # Zurückgeschoben und nicht quer über die Platte gelegt: Der Körper steht
    # an der Kante, an der er hinausgelaufen wäre.
    assert mesh.bounds.maximum[0] == pytest.approx(area.bounds[2], abs=1e-6)
    assert any(
        finding.code == "transform.nudged_onto_bed" for finding in result.scene.report.findings
    ), "die Rückholung geschieht, wird aber nicht gesagt"


def test_a_typed_value_is_carried_out_as_it_stands(document: Document, profile: Profile) -> None:
    """Getippt wird ausgeführt, gezogen wird gezeigt.

    Die Vorgabe des Parameters ist **aus**, und das trägt zwei Fälle, die es
    wirklich gibt: Das Galerieteil *gehaeuse* schiebt seinen Deckel um 135 mm
    und graviert danach bei x = 135 — eine stille Rückholung ließe die Gravur
    ins Leere greifen. Und ein Kranz, der bewusst über den Bauraum gelegt
    wird, soll das melden statt zurückzurücken
    (`test_scene_ops.test_a_ring_that_leaves_the_build_volume_is_refused_with_advice`).
    """
    history = prepared(document)
    history.apply(
        _("Verschieben"),
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 300.0})],
    )

    result = evaluate_with(document, profile)
    mesh = result.scene.objects["obj_1"].mesh

    assert mesh.bounds.centre[0] == pytest.approx(300.0)
    assert not any(
        finding.code.startswith("transform.nudged") or finding.code.startswith("transform.rearr")
        for finding in result.scene.report.findings
    )


def test_who_stood_outside_already_stays_outside(document: Document, profile: Profile) -> None:
    """Ein geparkter Körper bleibt geparkt, so oft man ihn noch zieht.

    Geprüft wird der **Eingang**: Lag er nicht auf der Fläche, ist seine Lage
    eine Absicht und keine Panne. Ohne diese Bedingung finge der zweite Zug
    ein, was der erste bewusst hinausgelegt hat — und ein Körper, den man
    einmal neben das Bett gelegt hat, wäre dort nicht mehr zu bewegen.
    """
    history = prepared(document)
    # Getippt und damit bewusst: der Körper wird neben das Bett gelegt.
    history.apply(
        _("Verschieben"),
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 300.0})],
    )
    # Und jetzt gezogen — der Haken ist gesetzt und greift trotzdem nicht.
    history.apply(
        _("Verschieben"),
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_1",),
                params={"dy": 5.0, "keep_on_bed": True},
            )
        ],
    )

    mesh = evaluate_with(document, profile).scene.objects["obj_1"].mesh
    assert mesh.bounds.centre[0] == pytest.approx(300.0), "der geparkte Körper wurde eingefangen"


def test_a_taken_place_makes_it_rearrange(document: Document, profile: Profile) -> None:
    """Steht am nächsten Platz schon jemand, wird neu eingeordnet.

    Zurückschieben ist die Vorgabe, weil es am wenigsten bewegt — aber es darf
    nicht in einen Nachbarn schieben. Dann sucht dieselbe Anordnung, die
    *Auf dem Bett anordnen* benutzt, eine freie Stelle.
    """
    area = printable_area(profile.printer)
    history = loaded_twice(document)
    # Der zweite Würfel an die rechte Kante — genau dorthin, wohin der erste
    # zurückgeschoben würde.
    history.apply(
        _("Verschieben"),
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_2",),
                params={"dx": area.bounds[2] - 10.0},
            )
        ],
    )
    history.apply(
        _("Verschieben"),
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_1",),
                params={"dx": 300.0, "keep_on_bed": True},
            )
        ],
    )

    result = evaluate_with(document, profile)
    first = result.scene.objects["obj_1"].mesh
    second = result.scene.objects["obj_2"].mesh

    assert fits_xy(first, area)
    assert any(
        finding.code == "transform.rearranged_on_bed" for finding in result.scene.report.findings
    )
    # Und wirklich frei: Die Hüllquader dürfen sich in XY nicht überlappen.
    apart = (
        first.bounds.maximum[0] <= second.bounds.minimum[0]
        or second.bounds.maximum[0] <= first.bounds.minimum[0]
        or first.bounds.maximum[1] <= second.bounds.minimum[1]
        or second.bounds.maximum[1] <= first.bounds.minimum[1]
    )
    assert apart, "neu eingeordnet und trotzdem im Nachbarn"


def test_two_bodies_may_be_pushed_into_each_other(document: Document, profile: Profile) -> None:
    """Zwei Körper, die einander durchdringen, bleiben stehen.

    **Befund Robert, 18.09.2026:** „beim bewegen und einer Kollision werden
    die Körper versetzt, vllt will man sie aber zusammenhieben zum
    verschmelzen, so nicht möglich". Der Griff setzt ``keep_on_bed`` bei
    jedem Zug, und die Bindung hielt bis dahin auch „ohne Überschneidung" —
    wer zwei Teile ineinanderzog, bekam sie auseinandergeschoben, bevor er
    *Vereinigen* anklicken konnte.

    Zwei Körper am selben Ort sind eine Absicht; ein Körper neben dem Bett
    ist es nie. Gemeldet wird die Überschneidung weiterhin.
    """
    history = loaded_twice(document)
    # Den zweiten Würfel ein Stück zur Seite, damit der erste einen Weg hat.
    history.apply(
        _("Verschieben"),
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": 40.0})],
    )
    before = evaluate_with(document, profile).scene.objects
    gap = float(before["obj_2"].mesh.bounds.centre[0] - before["obj_1"].mesh.bounds.centre[0])

    # Und den ersten genau auf ihn — mit dem Haken, den jeder Griff setzt.
    history.apply(
        _("Verschieben"),
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_1",),
                params={"dx": gap, "keep_on_bed": True},
            )
        ],
    )

    result = evaluate_with(document, profile)
    first = result.scene.objects["obj_1"].mesh
    second = result.scene.objects["obj_2"].mesh
    assert first.bounds.centre[0] == pytest.approx(second.bounds.centre[0], abs=1e-6), (
        "der Zug muss ankommen, nicht ausweichen"
    )
    assert not any(
        finding.code == "transform.rearranged_on_bed" for finding in result.scene.report.findings
    )
    spoken = {finding.code for finding in result.scene.report.findings}
    assert spoken & {"arrange.collision", "arrange.bodies_in_one_place"}, (
        f"gemeldet wird sie trotzdem, gefunden: {sorted(spoken)}"
    )


def test_growing_over_the_edge_is_held_too(document: Document, profile: Profile) -> None:
    """Auch Wachsen bringt einen Körper über den Rand — ohne dass jemand schiebt."""
    area = printable_area(profile.printer)
    history = prepared(document)
    history.apply(
        _("Verschieben"),
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_1",),
                params={"dx": area.bounds[2] - 10.0},
            )
        ],
    )
    history.apply(
        _("Skalieren"),
        [
            OperationDraft(
                op="scale_object",
                inputs=("obj_1",),
                params={"factor": 4.0, "keep_on_bed": True},
            )
        ],
    )

    result = evaluate_with(document, profile)
    assert fits_xy(result.scene.objects["obj_1"].mesh, area)


def test_the_reported_matrix_lands_the_input_on_the_result(profile: Profile) -> None:
    """Die gemeldete Bewegung ist die Verschiebung **und** die Rückholung.

    Sie ist die Auskunft für Vorschau und Gizmo, und die muss den Eingang
    genau auf den Ausgang legen. Ohne die Nachführung zeigte die Vorschau den
    Körper dort, wohin die Zahlen zeigen — also neben dem Bett, wo er
    hinterher nicht liegt. Dieselbe Rechnung wie bei *Druckoptimal
    ausrichten*, wenn es nach dem Drehen anordnet.
    """
    import numpy as np

    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.transform import apply
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene, SceneObject

    body = as_mesh_data(cube())
    entry = SceneObject(id="obj_1", name="Würfel", mesh=body)
    spec = REGISTRY.get("translate_object")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(dx=300.0, keep_on_bed=True),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )

    assert result.transform is not None
    laid = apply(body, np.asarray(result.transform, dtype=float))
    assert laid.bounds.centre == pytest.approx(result.outputs[0].mesh.bounds.centre, abs=1e-6), (
        "die gemeldete Matrix zeigt woanders hin als der Körper liegt"
    )


def _moved_across(profile: Profile, objects: list, **params: object):
    """*Verschieben* am ersten Körper, mit allen als Szene."""
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    spec = REGISTRY.get("translate_object")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry for entry in objects}),
            inputs=[objects[0]],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_a_move_onto_another_plate_puts_the_body_there(profile: Profile) -> None:
    """Wer einen Körper auf ein anderes Bett zieht, legt ihn auf diese Platte.

    So gefunden (Robert, 29.09.2026: „wenn ich sie auf eine andere platte
    verschieben will springen sie auch"): Die Betten stehen im Bild
    nebeneinander, in der Szene übereinander. Ein Zug hinüber war ein Weg von
    einer Bettbreite und mehr auf der **eigenen** Platte, *Auf dem Bett
    halten* holte den Körper dorthin zurück, und er sprang. Die Platte gehört
    in den Schritt, gezählt wie im Plattenwähler; die Verschiebung gilt dort.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.types import SceneObject

    body = as_mesh_data(cube())
    entry = SceneObject(id="obj_1", name="Würfel", mesh=body, plate=2)

    result = _moved_across(profile, [entry], dx=30.0, plate=1, keep_on_bed=True)

    moved = result.outputs[0]
    assert moved.plate == 0, "Platte 1 im Wähler ist die erste der Szene"
    assert moved.mesh.bounds.centre[0] == pytest.approx(30.0)
    codes = {finding.code for finding in result.findings}
    assert not codes & {"transform.nudged_onto_bed", "transform.rearranged_on_bed"}, codes

    # Nur die Platte gewechselt, ohne Weg: Das ist eine Wirkung, und der Satz
    # „steht genau dort, wo er stand" wäre falsch.
    only_plate = _moved_across(profile, [entry], plate=1)
    assert only_plate.outputs[0].plate == 0
    assert "transform.without_effect" not in {finding.code for finding in only_plate.findings}

    # Null lässt ihn auf seiner Platte — die Vorgabe, die jeder alte Schritt hat.
    stays = _moved_across(profile, [entry], dx=30.0)
    assert stays.outputs[0].plate == 2


def test_the_target_plate_decides_where_a_move_is_held(profile: Profile) -> None:
    """Zurückgeholt wird auf der Zielplatte, um deren Körper herum.

    Ein Nachbar auf der alten Platte steht dem Körper nach dem Wechsel nicht
    mehr im Weg; einer auf der neuen schon. Der Körper wird über die rechte
    Kante gezogen, und genau dort steht auf der Zielplatte ein anderer.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.types import SceneObject

    area = printable_area(profile.printer)
    body = as_mesh_data(cube())
    at_the_edge = apply(body, translation((area.bounds[2] - 10.0, 0.0, 0.0)))
    entry = SceneObject(id="obj_1", name="Würfel", mesh=body, plate=1)
    neighbour = SceneObject(id="obj_2", name="Nachbar", mesh=at_the_edge, plate=0)

    result = _moved_across(profile, [entry, neighbour], dx=300.0, plate=1, keep_on_bed=True)

    moved = result.outputs[0]
    assert moved.plate == 0
    assert fits_xy(moved.mesh, area)
    assert "transform.rearranged_on_bed" in {finding.code for finding in result.findings}, (
        "der kürzeste Rückweg endet im Nachbarn der Zielplatte"
    )


def test_moving_an_exact_body_maps_faces_to_triangles_once_per_body(monkeypatch) -> None:
    """Die Umkehrabbildung Fläche → Dreiecke entsteht je Körper einmal und liegt in seinem
    Cache; ``Solid.triangles_of_face`` sucht sonst je Merkmal über alle Dreiecke — an
    einer Platte mit 31 Merkmalen 124 Suchläufe, 63 von 130 ms (Review, 21.09.2026)."""
    import numpy as np

    from app.core.geom.transform import moved_object
    from app.core.types import SceneObject
    from tests.helpers import exact_kernel

    exact_kernel()
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid

    body = edit.box(30.0, 20.0, 8.0)
    for x in (-8.0, 0.0, 8.0):
        body = edit.cut_bore(
            body, position=(x, 0.0, 4.0), direction=(0.0, 0.0, 1.0), diameter=3.0, depth=20.0
        )
    entry = SceneObject(
        id="obj_1", name="Platte", mesh=body, kind="brep", features=dict(features_of(body))
    )
    assert len(entry.features) >= 9
    searches: list[int] = []
    original = Solid.triangles_of_face

    def counted(self, face_index):
        searches.append(face_index)
        return original(self, face_index)

    monkeypatch.setattr(Solid, "triangles_of_face", counted)
    matrix = np.eye(4)
    matrix[:3, 3] = (5.0, -3.0, 2.0)
    moved = moved_object(entry, matrix)
    assert searches == [], "keine Suche je Merkmal über alle Dreiecke"
    assert "triangles_by_face" in body._cache and "triangles_by_face" in moved.mesh._cache
    assert set(moved.features) == set(entry.features)
    for name, feature in entry.features.items():
        after = moved.features[name]
        assert len(after.face_indices) == len(feature.face_indices)
        assert (
            after.params.get("centre") != feature.params.get("centre") or not feature.face_indices
        )


def test_four_quarter_turns_bring_every_point_back_bit_for_bit() -> None:
    """Eine Vierteldrehung ist exakt, vier davon sind die Ausgangslage.

    Mit ``cos(90°) = -8,5·10⁻⁵⁰`` statt null trug die Matrix einen Rest neben
    den Nullen, und über ``@`` rundete BLAS je nach CPU (RM-187). Aus exakten
    Winkelfunktionen und in fester Reihenfolge ist jede Ecke nach einer vollen
    Umdrehung wieder dieselbe Zahl.
    """
    import numpy as np

    from app.core.geom.transform import composed, moved_points, rotation_about

    corners = np.array([[1.25, -3.5, 7.0], [0.1, 0.2, 0.3], [-40.0, 12.5, 1e-3]])
    quarter = rotation_about((0.0, 0.0, 1.0), (2.0, -1.0, 0.0), 90.0)

    once = moved_points(corners, quarter)
    full = moved_points(corners, composed(quarter, quarter, quarter, quarter))

    assert np.array_equal(once[:, 2], corners[:, 2]), "um Z bleibt Z"
    # x' = cx - (y - cy), y' = cy + (x - cx): Nullen und Einsen, keine Reste.
    assert np.array_equal(once[0], [2.0 - (-3.5 - -1.0), -1.0 + (1.25 - 2.0), 7.0])
    assert np.array_equal(full, corners)
    half = rotation_about((1.0, 0.0, 0.0), (0.0, 0.0, 0.0), 180.0)
    assert np.array_equal(half[:3, :3], np.diag((1.0, -1.0, -1.0)))
    # Eine Ecke auf der Y-Achse landet auf der X-Achse — nicht um 10⁻⁴⁹ daneben,
    # denn danach wären zwei Flächen, die koplanar sein sollen, es nicht mehr.
    on_axis = moved_points(
        np.array([[0.0, 6.0, 1.0]]), rotation_about((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), 90.0)
    )
    assert np.array_equal(on_axis, [[-6.0, 0.0, 1.0]])


def test_the_centre_anchor_is_called_what_it_computes() -> None:
    """„Mitte“ ist die Mitte der Hülle, und die Kurzhilfe nennt sie so (RM-233).

    *Drehen*, *Skalieren* und *Spiegeln* nannten ihren Anker „Schwerpunkt“,
    gerechnet wurde mit der Mitte des Hüllquaders — an einem L-Winkel liegen
    beide Zentimeter auseinander. Die Auswahl darüber sagt „Mitte“, und der
    Satz dazu sagt jetzt dasselbe.
    """
    import trimesh

    from app.core.geom import transform
    from app.core.geom.mesh import MeshData

    angle = trimesh.util.concatenate(
        [
            trimesh.creation.box(
                extents=(40.0, 4.0, 4.0),
                transform=trimesh.transformations.translation_matrix((20.0, 2.0, 2.0)),
            ),
            trimesh.creation.box(
                extents=(4.0, 40.0, 4.0),
                transform=trimesh.transformations.translation_matrix((2.0, 20.0, 2.0)),
            ),
        ]
    )
    mesh = MeshData.of(angle)
    centre = transform.anchor_point(mesh, "centre")
    assert centre == pytest.approx(tuple(mesh.bounds.centre)), "gerechnet wird die Hüllmitte"
    assert centre != pytest.approx(tuple(angle.center_mass)), "der Fall unterscheidet beide"
    for name in ("rotate_object", "scale_object", "mirror_object"):
        about = next(entry for entry in REGISTRY.get(name).params.spec() if entry.name == "about")
        assert "Schwerpunkt" not in str(about.doc), (
            f"{name}: die Kurzhilfe verspricht den Schwerpunkt"
        )
        assert "Mitte" in str(about.doc), f"{name}: die Kurzhilfe nennt die Mitte nicht"


@pytest.mark.parametrize(
    "reference,expected",
    [
        ("bed", (0.0, 0.0, 5.0)),
        ("centre", (0.0, 0.0, 0.0)),
        ("corner_000", (10.0, 15.0, 5.0)),
        ("corner_001", (10.0, 15.0, -5.0)),
        ("corner_010", (10.0, -15.0, 5.0)),
        ("corner_011", (10.0, -15.0, -5.0)),
        ("corner_100", (-10.0, 15.0, 5.0)),
        ("corner_101", (-10.0, 15.0, -5.0)),
        ("corner_110", (-10.0, -15.0, 5.0)),
        ("corner_111", (-10.0, -15.0, -5.0)),
    ],
)
def test_absolute_translation_recomputes_reference_after_upstream_size_change(
    profile, reference, expected
):
    """An absolute target remains fixed when an earlier dimension changes."""
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import new_project

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Box", [OperationDraft(op="create_box", params={"width": 20, "depth": 30, "height": 10})]
    )
    history.apply(
        "Position",
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_1",),
                params={"mode": "absolute", "reference": reference, "x": 0, "y": 0, "z": 0},
            )
        ],
    )
    result = evaluate(project.document, profile, detect_features=False)
    assert result.stopped_at is None
    assert result.scene.objects["obj_1"].mesh.bounds.centre == pytest.approx(expected)
    history.change_params(1, {"width": 40})
    changed = evaluate(project.document, profile, detect_features=False)
    from app.core.geom.transform import reference_point

    assert reference_point(list(changed.scene.objects.values()), reference) == pytest.approx(
        (0, 0, 0)
    )


def test_absolute_translation_moves_a_group_as_one_assembly(profile):
    """All selected bodies retain their relative positions, with one undo."""
    from app.core.geom.transform import reference_point
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import new_project

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply("Boxes", [OperationDraft(op="create_box"), OperationDraft(op="create_box")])
    history.apply(
        "Offset", [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": 50})]
    )
    history.apply(
        "Position",
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_1", "obj_2"),
                params={"mode": "absolute", "x": 0, "y": 0, "z": 0},
            )
        ],
    )
    result = evaluate(project.document, profile, detect_features=False)
    assert result.stopped_at is None
    bodies = list(result.scene.objects.values())
    assert reference_point(bodies) == pytest.approx((0, 0, 0))
    assert bodies[1].mesh.bounds.centre[0] - bodies[0].mesh.bounds.centre[0] == pytest.approx(50)
    history.undo()
    previous = evaluate(project.document, profile, detect_features=False)
    assert previous.scene.objects["obj_2"].mesh.bounds.centre[0] == pytest.approx(50)


@pytest.mark.parametrize("angles", [(0, 0, 0), (20, 30, 40), (0, 90, 0), (180, 0, -90)])
def test_absolute_rotation_reaches_target_after_earlier_rotation_and_reload(
    profile, tmp_path, angles
):
    """Absolute angles refer to the creation frame and survive a project reload."""
    import numpy as np

    from app.core.geom.transform import composed, orientation_matrix, rotation
    from app.core.scene.project import load, new_project, save

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply("Box", [OperationDraft(op="create_box")])
    history.apply(
        "Turn",
        [OperationDraft(op="rotate_object", inputs=("obj_1",), params={"axis": "y", "angle": 25})],
    )
    history.apply(
        "Target",
        [
            OperationDraft(
                op="rotate_object",
                inputs=("obj_1",),
                params={
                    "mode": "absolute",
                    **dict(zip(("angle_x", "angle_y", "angle_z"), angles, strict=True)),
                },
            )
        ],
    )
    target = composed(rotation("z", angles[2]), rotation("y", angles[1]), rotation("x", angles[0]))[
        :3, :3
    ]
    for active in (project, load(save(project, tmp_path / "rotation.p3d"))):
        result = evaluate(active.document, profile, detect_features=False)
        assert result.stopped_at is None
        assert np.allclose(orientation_matrix(result.scene.objects["obj_1"]), target)
    history.change_params(2, {"axis": "x", "angle": 72})
    result = evaluate(project.document, profile, detect_features=False)
    assert np.allclose(orientation_matrix(result.scene.objects["obj_1"]), target)


def test_absolute_rotation_preserves_a_group_and_undo_restores_it(profile):
    """The first selected body defines one rotation for the whole assembly."""
    import numpy as np

    from app.core.scene.project import new_project

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply("Bodies", [OperationDraft(op="create_box"), OperationDraft(op="create_sphere")])
    history.apply(
        "Offset", [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": 50})]
    )
    before = evaluate(project.document, profile, detect_features=False)
    history.apply(
        "Turn",
        [
            OperationDraft(
                op="rotate_object",
                inputs=("obj_1", "obj_2"),
                params={"mode": "absolute", "angle_z": 90},
            )
        ],
    )
    after = evaluate(project.document, profile, detect_features=False)
    assert after.stopped_at is None
    difference = (
        np.asarray(after.scene.objects["obj_2"].mesh.bounds.centre)
        - after.scene.objects["obj_1"].mesh.bounds.centre
    )
    assert difference[:2] == pytest.approx((0, 50))
    history.undo()
    undone = evaluate(project.document, profile, detect_features=False)
    assert undone.object_hashes == before.object_hashes


@pytest.mark.parametrize(
    "frame",
    [
        None,
        ((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
        ((1, 0.2, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
    ],
)
def test_absolute_rotation_explains_unknown_reflected_or_sheared_frames(frame):
    """An unproven frame offers relative rotation instead of guessed angles."""
    from app.core.errors import ValidationError
    from app.core.geom.transform import orientation_angles
    from app.core.types import SceneObject

    body = SceneObject(id="one", name="Body", mesh=cube(), frame=frame)
    with pytest.raises(ValidationError) as caught:
        orientation_angles(body)
    assert "relativ" in str(caught.value.detail)


def test_absolute_translation_binds_feature_to_the_first_input(profile):
    """A group reference resolves on its first input and moves every selected body."""
    from app.core.geom.transform import reference_point
    from app.core.registry import needed_inputs
    from app.core.scene import orphans
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import Feature, OpContext, Operation, Scene, SceneObject

    bodies = [
        SceneObject(
            id=key,
            name=key,
            mesh=cube(),
            features={
                "anchor": Feature(
                    id="anchor", kind="plane", provenance="generated", params={"centre": centre}
                )
            },
        )
        for key, centre in (("a", (5.0, 6.0, 7.0)), ("b", (15.0, 16.0, 17.0)))
    ]
    spec = REGISTRY.get("translate_object")
    assert needed_inputs(spec) == 1
    params = {
        "mode": "absolute",
        "reference": "feature",
        "reference_feature": "anchor",
        "x": 0,
        "y": 0,
        "z": 0,
    }
    result = spec.fn(
        OpContext(
            scene=Scene(objects={body.id: body for body in bodies}),
            inputs=bodies,
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=0,
            progress=lambda *_: None,
            ask=lambda _q, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    assert reference_point(result.outputs, "feature", "anchor") == pytest.approx((0, 0, 0))
    assert reference_point(result.outputs[1:], "feature", "anchor") == pytest.approx((10, 10, 10))
    document = Document(
        format_version=1,
        app_version="0.0.1",
        ops=[Operation(id=1, op="translate_object", inputs=["a", "b"], params=params)],
    )
    references = orphans.references(document)
    assert len(references) == 1
    assert references[0].ref.object_id == "a"


@pytest.mark.parametrize(
    "reference", ["centre", "bed", *(f"corner_{index:03b}" for index in range(8))]
)
def test_absolute_quarter_turn_uses_the_selected_reference(profile, reference):
    """A quarter turn preserves the selected pivot, including every box corner."""
    from app.core.geom.transform import reference_point
    from app.core.scene.project import new_project

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Box", [OperationDraft(op="create_box", params={"width": 20, "depth": 30, "height": 10})]
    )
    before = evaluate(project.document, profile, detect_features=False)
    body = before.scene.objects["obj_1"]
    px, py, _pz = reference_point([body], reference)
    cx, cy, cz = body.mesh.bounds.centre
    history.apply(
        "Turn",
        [
            OperationDraft(
                op="rotate_object",
                inputs=("obj_1",),
                params={"mode": "absolute", "about": reference, "angle_z": 90},
            )
        ],
    )
    result = evaluate(project.document, profile, detect_features=False)
    assert result.stopped_at is None
    assert result.scene.objects["obj_1"].mesh.bounds.centre == pytest.approx(
        (px - (cy - py), py + (cx - px), cz)
    )
    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((30, 20, 10))
