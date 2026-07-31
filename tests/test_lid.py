"""The lid over an opening (§25, §14, §40).

A box of known dimensions, so every number the lid comes out with can be
checked: the collar is the cavity minus twice the clearance, and the proof that
it fits is that lid and housing share no volume at all.
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom import lid as lid_module
from app.core.geom.boolean import shared_volume
from app.core.geom.mesh import MeshData
from app.core.knowledge import profiles
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject

load_operations()

#: The housing every test measures against: 60 x 40 x 30 outside, 3 mm walls,
#: 1,5 mm floor, open at the top. Cavity 54 x 34.
OUTER = (60.0, 40.0, 30.0)
CAVITY = (54.0, 34.0)


def housing(material: str | None = None) -> SceneObject:
    outer = trimesh.creation.box(extents=OUTER)
    outer.apply_translation((0.0, 0.0, OUTER[2] / 2.0))
    inner = trimesh.creation.box(extents=(CAVITY[0], CAVITY[1], 27.0))
    inner.apply_translation((0.0, 0.0, 16.5))
    body = trimesh.boolean.difference([outer, inner])
    return SceneObject(id="obj_1", name="Gehäuse", mesh=MeshData.of(body), material=material)


def make_lid(entry: SceneObject, profile: Profile, **params: object):
    spec = REGISTRY.get("create_lid")
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


def test_the_lid_covers_the_opening(profile: Profile) -> None:
    """A lid with a hole in it is not a lid — the section's own hole is filled."""
    result = make_lid(housing(), profile, thickness=2.4, collar=4.0)
    body = result.outputs[1].mesh

    plate = OUTER[0] * OUTER[1] * 2.4
    assert body.bounds.size[0] == pytest.approx(OUTER[0])
    assert body.bounds.size[1] == pytest.approx(OUTER[1])
    assert body.volume > plate, "the plate is solid, plus a collar"
    assert body.is_watertight


def test_the_collar_is_the_cavity_less_the_clearance(profile: Profile) -> None:
    """§12: the number comes from the material profile, not from the file."""
    result = make_lid(housing(), profile, thickness=2.4, collar=4.0)
    body = result.outputs[1].mesh.raw

    gap = profiles.material("petg").clearance + lid_module.COLLAR_RELIEF
    collar = body.slice_plane([0.0, 0.0, 29.0], [0.0, 0.0, -1.0])
    width = collar.bounds[1][:2] - collar.bounds[0][:2]

    assert width[0] == pytest.approx(CAVITY[0] - 2.0 * gap, abs=0.01)
    assert width[1] == pytest.approx(CAVITY[1] - 2.0 * gap, abs=0.01)


def test_the_lid_really_goes_in(profile: Profile) -> None:
    """The one measurement that matters: lid and housing share no volume."""
    entry = housing()
    body = make_lid(entry, profile, thickness=2.4, collar=4.0).outputs[1].mesh

    assert shared_volume(body.raw, entry.mesh.raw) < 1e-6


def test_the_lid_sits_on_the_rim(profile: Profile) -> None:
    result = make_lid(housing(), profile, thickness=2.4, collar=4.0)
    body = result.outputs[1].mesh

    assert body.bounds.minimum[2] == pytest.approx(OUTER[2] - 4.0), "the collar reaches down"
    assert body.bounds.maximum[2] == pytest.approx(OUTER[2] + 2.4), "the plate sits on top"


def test_a_softer_lid_gets_more_room(profile: Profile) -> None:
    """§12 again: the lid of a TPU housing is not the lid of a PETG one."""
    stiff = make_lid(housing(), profile, collar=4.0).findings[0].values["clearance_mm"]
    soft = make_lid(housing("tpu-95a"), profile, collar=4.0).findings[0].values["clearance_mm"]

    assert soft > stiff
    assert soft == pytest.approx(profiles.material("tpu-95a").clearance)


def test_a_lid_without_a_collar_is_a_plate(profile: Profile) -> None:
    result = make_lid(housing(), profile, thickness=2.4, collar=0.0)
    body = result.outputs[1].mesh

    assert body.volume == pytest.approx(OUTER[0] * OUTER[1] * 2.4, rel=0.001)
    assert body.bounds.minimum[2] == pytest.approx(OUTER[2])


def test_a_solid_body_has_nothing_to_close(profile: Profile) -> None:
    block = trimesh.creation.box(extents=(40.0, 40.0, 20.0))
    block.apply_translation((0.0, 0.0, 10.0))
    entry = SceneObject(id="obj_1", name="Klotz", mesh=MeshData.of(block))

    with pytest.raises(ValidationError) as problem:
        make_lid(entry, profile, collar=4.0)

    assert problem.value.constraint == "no_cavity"


def test_a_screw_hole_is_not_an_opening(profile: Profile) -> None:
    """A 4 mm bore is a bore. A collar in it would be a pin nobody asked for."""
    plate = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    plate.apply_translation((0.0, 0.0, 5.0))
    bore = trimesh.creation.cylinder(radius=2.0, height=30.0, sections=64)
    entry = SceneObject(
        id="obj_1", name="Platte", mesh=MeshData.of(trimesh.boolean.difference([plate, bore]))
    )

    with pytest.raises(ValidationError) as problem:
        make_lid(entry, profile, collar=4.0)

    assert problem.value.constraint == "no_cavity"


def test_two_compartments_get_two_collars(profile: Profile) -> None:
    """A divided box: one collar per compartment is what stops the lid turning."""
    outer = trimesh.creation.box(extents=(80.0, 40.0, 20.0))
    outer.apply_translation((0.0, 0.0, 10.0))
    cut = []
    for offset in (-20.0, 20.0):
        pocket = trimesh.creation.box(extents=(30.0, 34.0, 18.0))
        pocket.apply_translation((offset, 0.0, 11.0))
        cut.append(pocket)
    body = trimesh.boolean.difference([outer, *cut])
    entry = SceneObject(id="obj_1", name="Kasten", mesh=MeshData.of(body))

    result = make_lid(entry, profile, thickness=2.0, collar=3.0)

    assert result.findings[0].values["cavities"] == 2
    lid_body = result.outputs[1].mesh
    assert lid_body.is_watertight
    assert shared_volume(lid_body.raw, body) < 1e-6


def test_the_lid_carries_the_material_of_the_body_it_closes(profile: Profile) -> None:
    result = make_lid(housing("tpu-95a"), profile, collar=4.0)

    assert result.outputs[1].material == "tpu-95a"


def test_a_screw_post_bore_is_not_a_compartment(profile: Profile) -> None:
    """The real neighbour of an opening: M3 holes in the corner posts.

    Eight square millimetres against eighteen hundred — a collar in one would be
    a pin in the screw's way. The absolute limit settles it without measuring
    the cavities against each other, which would throw away a small compartment
    that a collar fits perfectly well.
    """
    body = housing().mesh.raw.copy()
    posts = []
    for x in (-26.0, 26.0):
        for y in (-16.0, 16.0):
            bore = trimesh.creation.cylinder(radius=1.6, height=40.0, sections=32)
            bore.apply_translation((x, y, 20.0))
            posts.append(bore)
    entry = SceneObject(
        id="obj_1", name="Gehäuse", mesh=MeshData.of(trimesh.boolean.difference([body, *posts]))
    )

    result = make_lid(entry, profile, thickness=2.0, collar=3.0)

    assert result.findings[0].values["cavities"] == 1, "the box, not the four bores"


def test_a_small_compartment_still_gets_a_collar(profile: Profile) -> None:
    """A pen slot of 12 x 12 next to a compartment fifteen times its size."""
    outer = trimesh.creation.box(extents=(80.0, 40.0, 20.0))
    outer.apply_translation((0.0, 0.0, 10.0))
    big = trimesh.creation.box(extents=(50.0, 34.0, 18.0))
    big.apply_translation((-12.0, 0.0, 11.0))
    small = trimesh.creation.box(extents=(12.0, 12.0, 18.0))
    small.apply_translation((25.0, 0.0, 11.0))
    body = trimesh.boolean.difference([outer, big, small])
    entry = SceneObject(id="obj_1", name="Kasten", mesh=MeshData.of(body))

    result = make_lid(entry, profile, thickness=2.0, collar=3.0)

    assert result.findings[0].values["cavities"] == 2
    assert shared_volume(result.outputs[1].mesh.raw, body) < 1e-6


# --- the turning lid ------------------------------------------------------------


def jar(radius: float = 20.0, wall: float = 3.0, height: float = 60.0) -> SceneObject:
    """A round tin, open at the top: the shape a screw lid belongs on."""
    outer = trimesh.creation.cylinder(radius=radius, height=height, sections=96)
    outer.apply_translation((0.0, 0.0, height / 2.0))
    inner = trimesh.creation.cylinder(radius=radius - wall, height=height - wall, sections=96)
    inner.apply_translation((0.0, 0.0, height / 2.0 + wall / 2.0 + 0.1))
    return SceneObject(
        id="obj_1", name="Dose", mesh=MeshData.of(trimesh.boolean.difference([outer, inner]))
    )


def make_screw_lid(entry: SceneObject, profile: Profile, **params: object):
    spec = REGISTRY.get("screw_lid")
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


def radii(body: MeshData, low: float, high: float) -> tuple[float, float]:
    """Smallest and largest distance from the axis inside a band of height."""
    points = np.asarray(body.raw.vertices)
    inside = points[(points[:, 2] > low) & (points[:, 2] < high)]
    lengths = np.linalg.norm(inside[:, :2], axis=1)
    lengths = lengths[lengths > 1e-9]
    return float(lengths.min()), float(lengths.max())


def test_the_neck_and_the_lid_are_one_thread(profile: Profile) -> None:
    """The measurement that decides it: does the lid grip, or does it slide off?

    The lid is cut from the core diameter plus the clearance, so its material
    reaches into the valley of the neck. Cut from the major diameter instead —
    the mistake the part library's nut made — it would be a sleeve.
    """
    result = make_screw_lid(jar(), profile, height=8.0, pitch=3.0)
    neck, lid = result.outputs[0].mesh, result.outputs[1].mesh

    neck_core, neck_crest = radii(neck, 60.5, 67.5)
    lid_core, lid_crest = radii(lid, 1.0, 8.0)

    assert lid_core > neck_core, "the lid has to reach into the valley of the neck"
    assert lid_crest > neck_crest, "and clear its crest"
    gap = profiles.material("petg").clearance
    assert lid_crest - neck_crest == pytest.approx(gap / 2.0, abs=0.02)


def test_both_halves_come_out_closed(profile: Profile) -> None:
    result = make_screw_lid(jar(), profile, height=8.0, pitch=3.0)

    assert result.outputs[0].mesh.is_watertight, "the tin with its neck"
    assert result.outputs[1].mesh.is_watertight, "and the lid"


def test_the_neck_keeps_the_diameter_of_the_opening(profile: Profile) -> None:
    """A neck wider than the tin is a lid that overhangs the wall it sits on."""
    result = make_screw_lid(jar(radius=20.0), profile, height=8.0, pitch=3.0)

    assert result.findings[0].values["neck_mm"] == pytest.approx(40.0, abs=0.5)
    assert result.outputs[0].mesh.bounds.size[0] == pytest.approx(40.0, abs=0.1)


def test_the_lid_stands_on_its_open_end(profile: Profile) -> None:
    """§25: printed the other way up a cap needs support in its own thread."""
    lid = make_screw_lid(jar(), profile, height=8.0, pitch=3.0).outputs[1].mesh

    assert lid.bounds.minimum[2] == pytest.approx(0.0, abs=0.01)


def test_the_skirt_is_taller_than_the_neck(profile: Profile) -> None:
    """Otherwise the lid comes to rest on the end of the thread, not on the rim."""
    result = make_screw_lid(jar(), profile, height=8.0, pitch=3.0, thickness=2.4)
    lid = result.outputs[1].mesh

    assert lid.bounds.size[2] > 8.0 + 2.4


def test_a_thin_wall_cannot_carry_a_coarse_thread(profile: Profile) -> None:
    """Two ridge depths of 5 mm pitch do not fit into a wall of 1,5."""
    with pytest.raises(ValidationError) as problem:
        make_screw_lid(jar(radius=20.0, wall=1.5), profile, height=8.0, pitch=5.0)

    assert problem.value.constraint == "too_coarse"


def test_a_softer_material_gets_more_play(profile: Profile) -> None:
    """§12: the clearance of the thread is the material's, like every other."""
    stiff = make_screw_lid(jar(), profile, pitch=3.0).findings[0].values["clearance_mm"]
    soft_jar = jar()
    soft_jar.material = "tpu-95a"
    soft = make_screw_lid(soft_jar, profile, pitch=3.0).findings[0].values["clearance_mm"]

    assert soft > stiff


def test_the_ceiling_of_a_cavity_is_not_an_opening(profile: Profile) -> None:
    """The review's find: flat was not enough, it has to look up.

    A box open at the bottom has an interior ceiling — flat, pointing down, with
    a centre at 26,9 of 30 mm. Chosen as the opening it built a lid inside the
    box and no step complained, because a cut below that plane does meet a wall.
    """
    outer = trimesh.creation.box(extents=(60.0, 40.0, 30.0))
    outer.apply_translation((0.0, 0.0, 15.0))
    inner = trimesh.creation.box(extents=(54.0, 34.0, 27.0))
    inner.apply_translation((0.0, 0.0, 13.4))
    body = MeshData.of(trimesh.boolean.difference([outer, inner]))
    features = detect(body)
    ceiling = next(
        entry
        for entry in features.values()
        if entry.kind == "face"
        and entry.params["normal"][2] < -0.9
        and entry.params["centre"][2] > 1
    )
    entry = SceneObject(id="obj_1", name="Kasten", mesh=body, features=features)

    with pytest.raises(ValidationError) as problem:
        make_lid(entry, profile, collar=4.0, at_feature=ceiling.id)

    assert problem.value.constraint == "not_upright"


def test_a_chosen_rim_decides_the_height(profile: Profile) -> None:
    """And the other way round: the face that was clicked is the one that counts."""
    entry = housing()
    entry.features = detect(entry.mesh)
    rim = next(
        feature
        for feature in entry.features.values()
        if feature.kind == "face"
        and feature.params["normal"][2] > 0.9
        and feature.params["centre"][2] == pytest.approx(OUTER[2])
    )

    result = make_lid(entry, profile, collar=4.0, at_feature=rim.id)

    assert result.findings[0].values["z_mm"] == pytest.approx(OUTER[2])
