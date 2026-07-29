"""The lid over an opening (§25, §14, §40).

A box of known dimensions, so every number the lid comes out with can be
checked: the collar is the cavity minus twice the clearance, and the proof that
it fits is that lid and housing share no volume at all.
"""

from __future__ import annotations

import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom import lid as lid_module
from app.core.geom.boolean import shared_volume
from app.core.geom.mesh import MeshData
from app.core.knowledge import profiles
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
    body = result.outputs[0].mesh

    plate = OUTER[0] * OUTER[1] * 2.4
    assert body.bounds.size[0] == pytest.approx(OUTER[0])
    assert body.bounds.size[1] == pytest.approx(OUTER[1])
    assert body.volume > plate, "the plate is solid, plus a collar"
    assert body.is_watertight


def test_the_collar_is_the_cavity_less_the_clearance(profile: Profile) -> None:
    """§12: the number comes from the material profile, not from the file."""
    result = make_lid(housing(), profile, thickness=2.4, collar=4.0)
    body = result.outputs[0].mesh.raw

    gap = profiles.material("petg").clearance + lid_module.COLLAR_RELIEF
    collar = body.slice_plane([0.0, 0.0, 29.0], [0.0, 0.0, -1.0])
    width = collar.bounds[1][:2] - collar.bounds[0][:2]

    assert width[0] == pytest.approx(CAVITY[0] - 2.0 * gap, abs=0.01)
    assert width[1] == pytest.approx(CAVITY[1] - 2.0 * gap, abs=0.01)


def test_the_lid_really_goes_in(profile: Profile) -> None:
    """The one measurement that matters: lid and housing share no volume."""
    entry = housing()
    body = make_lid(entry, profile, thickness=2.4, collar=4.0).outputs[0].mesh

    assert shared_volume(body.raw, entry.mesh.raw) < 1e-6


def test_the_lid_sits_on_the_rim(profile: Profile) -> None:
    result = make_lid(housing(), profile, thickness=2.4, collar=4.0)
    body = result.outputs[0].mesh

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
    body = result.outputs[0].mesh

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
    lid_body = result.outputs[0].mesh
    assert lid_body.is_watertight
    assert shared_volume(lid_body.raw, body) < 1e-6


def test_the_lid_carries_the_material_of_the_body_it_closes(profile: Profile) -> None:
    result = make_lid(housing("tpu-95a"), profile, collar=4.0)

    assert result.outputs[0].material == "tpu-95a"
