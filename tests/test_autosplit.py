"""Auto Split mit Verstiftung (Bauplan §25, §22.3, §14; §40 für P10).

Das Abnahmekriterium sind drei Sätze: jedes Teil für sich wasserdicht,
Passungspaare angelegt und geprüft, und ``oversized.stl`` in etwas Druckbares
geteilt, ohne dass jemand einen Parameter anfasst. Alle drei stehen hier.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom import autosplit, pins
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.prepare import split_at_plane
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cancel import NeverCancelled
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.split import apply_split, plan_split
from app.core.types import OpContext, Profile, Scene, SceneObject, Source

MESHES = Path(__file__).parent / "data" / "meshes"


def body(name: str = "oversized.stl") -> MeshData:
    """So, wie die Eingangsstufe ihn liefert — verschweißt und damit
    geschlossen.
    """
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def bar(length: float = 400.0) -> MeshData:
    return MeshData.of(trimesh.creation.box(extents=(length, 60.0, 40.0)))


# --- the search -----------------------------------------------------------------


def test_a_part_that_fits_is_left_alone(profile: Profile) -> None:
    small = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))

    assert autosplit.fits(small, profile)
    assert autosplit.find_plane(small, profile) is None
    assert not autosplit.split_to_fit(small, profile).divided


def test_the_oversize_is_measured_per_axis(profile: Profile) -> None:
    over = autosplit.oversize(body(), profile)

    assert over[0] == pytest.approx(400.0 - 252.0), "252 mm usable of a 256 mm plate"
    assert over[1] == 0.0 and over[2] == 0.0


def test_the_plane_lands_in_the_slim_middle(profile: Profile) -> None:
    """§22.3: der Querschnitt entscheidet, und die schmale prismatische Mitte
    gewinnt.
    """
    candidate = autosplit.find_plane(body(), profile)

    assert candidate is not None
    assert candidate.axis == "x", "cut across the direction that is too long"
    assert -85.0 < candidate.position < 85.0, "inside the middle bar"
    assert candidate.contours == 1, "one seam, not several thin bridges"
    assert candidate.area == pytest.approx(40.0 * 30.0), "the section of the middle"


def test_a_seam_with_several_bridges_loses(profile: Profile) -> None:
    """Zwei Arme nebeneinander: quer durch beide zu schneiden ist schlechter,
    als die Verbindung zu schneiden.
    """
    left = trimesh.creation.box(extents=(300.0, 20.0, 20.0))
    left.apply_translation((0.0, -40.0, 10.0))
    right = trimesh.creation.box(extents=(300.0, 20.0, 20.0))
    right.apply_translation((0.0, 40.0, 10.0))
    joint = trimesh.creation.box(extents=(40.0, 100.0, 20.0))
    joint.apply_translation((0.0, 0.0, 10.0))
    fork = MeshData.of(trimesh.boolean.union([left, right, joint]))

    candidate = autosplit.find_plane(fork, profile)

    assert candidate is not None
    assert candidate.contours == 1
    assert abs(candidate.position) <= 20.0, "through the joint, not through both arms"


def test_a_body_twice_too_long_takes_two_cuts(profile: Profile) -> None:
    outcome = autosplit.split_to_fit(bar(600.0), profile)

    assert len(outcome.parts) == 3
    assert all(autosplit.fits(part, profile) for part in outcome.parts)


def test_every_piece_is_closed_and_nothing_is_lost(profile: Profile) -> None:
    """Das P10-Kriterium: jedes Teil wasserdicht, und das Volumen geht auf."""
    whole = body()
    outcome = autosplit.split_to_fit(whole, profile)

    assert outcome.divided
    assert all(part.is_watertight for part in outcome.parts)
    assert sum(part.volume for part in outcome.parts) == pytest.approx(whole.volume, rel=1e-6)
    assert all(autosplit.fits(part, profile) for part in outcome.parts)


def test_the_steps_say_which_piece_was_cut(profile: Profile) -> None:
    """Ohne das lässt sich der Stapel nicht bauen — der nächste Schnitt
    braucht ein Objekt.
    """
    outcome = autosplit.split_to_fit(bar(600.0), profile)

    assert [step.part_index for step in outcome.cuts] == [0, 1]


def test_the_search_stops_instead_of_cutting_forever(profile: Profile) -> None:
    outcome = autosplit.split_to_fit(bar(4000.0), profile, max_parts=4)

    assert len(outcome.parts) == 4
    assert "split.too_many_parts" in {finding.code for finding in outcome.findings}


def test_convex_parts_take_an_l_apart(profile: Profile) -> None:
    """§22.3: die Zerlegung findet, wo ein L von selbst auseinanderfällt.

    Dieser Test übersprang sich früher, wenn die Antwort leer war, und die
    Antwort war immer leer: der Aufruf übergab ein ``randomizeSeed``, das dieses
    V-HACD nicht hat, der TypeError wurde als „Modul fehlt" gelesen, und der
    ganze Hinweispfad der Ebenensuche war hinter einer grünen Suite tot. Also:
    kein Skip. Ist V-HACD installiert, muss es liefern, und die Ecke des L ist
    das, was es finden muss.
    """
    shape = trimesh.boolean.union(
        [
            trimesh.creation.box(extents=(60.0, 20.0, 20.0)),
            trimesh.creation.box(extents=(20.0, 20.0, 60.0)).apply_translation([20.0, 0.0, 40.0]),
        ]
    )
    parts = autosplit.convex_parts(MeshData.of(shape))

    assert len(parts) >= 2, "an L is not convex"
    assert sum(abs(part.volume) for part in parts) == pytest.approx(abs(shape.volume), rel=0.05)
    assert [abs(part.volume) for part in parts] == sorted(
        (abs(part.volume) for part in parts), reverse=True
    ), "largest first, as documented"


def test_convex_parts_are_reproducible(profile: Profile) -> None:
    """§11.3: derselbe Körper gibt dieselben Stücke, ohne einen Startwert zu
    speichern.
    """
    shape = trimesh.boolean.union(
        [
            trimesh.creation.box(extents=(60.0, 20.0, 20.0)),
            trimesh.creation.box(extents=(20.0, 20.0, 60.0)).apply_translation([20.0, 0.0, 40.0]),
        ]
    )
    first = autosplit.convex_parts(MeshData.of(shape))
    second = autosplit.convex_parts(MeshData.of(shape))

    assert len(first) == len(second)
    assert [round(part.volume, 3) for part in first] == [round(part.volume, 3) for part in second]


# --- the pins -------------------------------------------------------------------


def test_pins_sit_inside_the_cut_face(profile: Profile) -> None:
    whole = body()
    candidate = autosplit.find_plane(whole, profile)
    assert candidate is not None

    plan = pins.plan_pins(whole, candidate)

    assert plan.count == 2, "one pin is a hinge"
    assert pins.PIN_MIN <= plan.diameter <= pins.PIN_MAX
    for position in plan.positions:
        assert position[0] == pytest.approx(candidate.position), "on the parting plane"
        assert abs(position[1]) < 20.0 and 5.0 < position[2] < 35.0, "inside the middle bar"


def test_a_face_too_small_gets_no_pins_and_says_so(profile: Profile) -> None:
    """Eine Naht ohne Stifte klebt immer noch; ein Stift durch die Wand nicht."""
    thin = MeshData.of(trimesh.creation.box(extents=(400.0, 3.0, 3.0)))
    candidate = autosplit.find_plane(thin, profile)
    assert candidate is not None

    plan = pins.plan_pins(thin, candidate)

    assert plan.count == 0
    assert [finding.code for finding in plan.findings] == ["split.face_too_small"]


def test_the_pin_goes_into_one_half_and_the_bore_into_the_other(profile: Profile) -> None:
    whole = body()
    candidate = autosplit.find_plane(whole, profile)
    assert candidate is not None
    first, second, _findings = split_at_plane(whole, candidate.plane)
    plan = pins.plan_pins(whole, candidate)

    pair = pins.add_pins(first, second, plan, profile)

    assert pair.first.is_watertight and pair.second.is_watertight
    assert pair.first.volume > first.volume, "the pins add material"
    assert pair.second.volume < second.volume, "the bores take it away"
    assert sorted(pair.pin_features) == ["pin_1", "pin_2"]
    assert sorted(pair.bore_features) == ["bore_1", "bore_2"]


def test_the_play_comes_from_the_material_profile(profile: Profile) -> None:
    """Regel 7: die Bohrung ist der Stift plus das kalibrierte Spiel, nie ein
    Literal.
    """
    whole = body()
    candidate = autosplit.find_plane(whole, profile)
    assert candidate is not None
    first, second, _findings = split_at_plane(whole, candidate.plane)
    plan = pins.plan_pins(whole, candidate)

    pair = pins.add_pins(first, second, plan, profile)

    pin = pair.pin_features["pin_1"].params["diameter"]
    bore = pair.bore_features["bore_1"].params["diameter"]
    assert bore - pin == pytest.approx(profile.material.clearance)


# --- Als Operation ---------------------------------------------------------------


def run(op: str, entry: SceneObject, profile: Profile, **params: object):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_split_pinned_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Balken", mesh=body())

    result = run("split_pinned", entry, profile, axis="x", position=0.0, pins=2)

    assert [output.name for output in result.outputs] == ["Balken A", "Balken B"]
    assert all(output.mesh.is_watertight for output in result.outputs)
    assert "pin_1" in result.outputs[0].features
    assert "bore_1" in result.outputs[1].features


def test_split_pinned_can_also_just_cut(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Balken", mesh=body())

    result = run("split_pinned", entry, profile, axis="x", position=0.0, pins=0)

    assert not any("pin_1" in output.features for output in result.outputs)
    assert all(output.mesh.is_watertight for output in result.outputs)


def test_a_plane_that_misses_the_body_is_a_user_error(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Balken", mesh=body())

    with pytest.raises(ValidationError) as problem:
        run("split_pinned", entry, profile, axis="x", position=9999.0, pins=2)

    assert problem.value.field == "position"


# --- the whole way --------------------------------------------------------------


@pytest.fixture
def loaded(profile: Profile) -> tuple[Project, MeshData]:
    project = new_project("centauri-carbon-2", "petg")
    payload = (MESHES / "oversized.stl").read_bytes()
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/oversized.stl", sha256=""
    )
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    return project, result.scene.objects["obj_1"].mesh


def test_the_plan_is_one_operation_per_cut(loaded, profile: Profile) -> None:
    _project, mesh = loaded

    plan = plan_split(mesh, "obj_1", profile)

    assert plan.cuts == 1
    assert all(draft.op == "split_pinned" for draft in plan.drafts)
    assert plan.drafts[0].params["axis"] == "x"


def test_oversized_is_divided_without_anybody_touching_a_parameter(
    loaded, profile: Profile
) -> None:
    """Das P10-Abnahmekriterium, Ende zu Ende (§40)."""
    project, mesh = loaded

    applied = apply_split(project.document, mesh, "obj_1", profile)
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    assert len(applied.object_ids) == 2
    for object_id in applied.object_ids:
        part = result.scene.objects[object_id]
        assert part.mesh.is_watertight, object_id
        assert autosplit.fits(part.mesh, profile), object_id


def test_the_seams_become_fit_pairs(loaded, profile: Profile) -> None:
    """§14: Auto Split legt die Paare an, denn dort entstehen sie."""
    project, mesh = loaded

    applied = apply_split(project.document, mesh, "obj_1", profile)

    assert [fit.tolerance for fit in applied.fits] == ["auto:petg", "auto:petg"]
    assert project.document.fits == applied.fits
    assert applied.fits[0].a.feature_id == "pin_1"
    assert applied.fits[0].b.feature_id == "bore_1"


def test_the_pairs_hold_when_the_scene_is_checked(loaded, profile: Profile) -> None:
    project, mesh = loaded
    apply_split(project.document, mesh, "obj_1", profile)

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    codes = {finding.code for finding in result.scene.report.findings}
    assert "fit.violated" not in codes
    assert "fit.missing_feature" not in codes


def test_one_undo_takes_a_cut_back(loaded, profile: Profile) -> None:
    project, mesh = loaded
    apply_split(project.document, mesh, "obj_1", profile)

    History(project.document).undo()
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    assert list(result.scene.objects) == ["obj_1"], "the whole part is back"


def test_a_part_that_already_fits_is_not_cut(profile: Profile) -> None:
    project = new_project("centauri-carbon-2", "petg")
    small = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))

    applied = apply_split(project.document, small, "obj_1", profile)

    assert applied.object_ids == ["obj_1"]
    assert applied.fits == []
    assert project.document.ops == []


def test_the_sections_of_a_turned_axis_match_the_upright_ones(profile: Profile) -> None:
    """Die Drehung muss exakt sein — die Stiftpositionen werden durch sie
    gerechnet.
    """
    plate = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))

    along_z = autosplit.sections_along(plate, "z", np.array([0.0]))[0]
    along_x = autosplit.sections_along(plate, "x", np.array([0.0]))[0]

    assert along_z is not None and along_x is not None
    assert along_z.area == pytest.approx(60.0 * 40.0)
    assert along_x.area == pytest.approx(40.0 * 20.0)
