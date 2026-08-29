"""Von der Textur zum Filament (Bauplan §20).

Das Abnahmekriterium von P9 nennt eine Eigenschaft, und es ist die, die sich
leicht verliert: „Quantisierung reproduzierbar für denselben Startwert". Ein
k-Means, das aus einem globalen Zufallszustand zieht, besteht jede
Sichtprüfung — und liefert im nächsten Lauf ein anderes Teil.
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh
from PIL import Image

from app.core.errors import ValidationError
from app.core.geom import texture
from app.core.geom.attributes import counts, used_slots
from app.core.geom.mesh import MeshData
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject


def plate() -> trimesh.Trimesh:
    """Eine Platte, fein genug, um eine Grenze durch ihre Dreiecke zu tragen."""
    body = trimesh.creation.box(extents=(20.0, 20.0, 2.0))
    return body.subdivide().subdivide().subdivide()


def painted(colours: list[tuple[int, int, int]]) -> trimesh.Trimesh:
    """Eine Platte, deren Dreiecke von links nach rechts eingefärbt sind."""
    body = plate()
    middle = body.triangles_center[:, 0]
    edges = np.linspace(middle.min(), middle.max() + 1e-9, len(colours) + 1)
    faces = np.zeros((len(body.faces), 4), dtype=np.uint8)
    faces[:, 3] = 255
    for index, colour in enumerate(colours):
        inside = (middle >= edges[index]) & (middle < edges[index + 1])
        faces[inside, :3] = colour
    body.visual.face_colors = faces
    return body


def textured(image: Image.Image) -> trimesh.Trimesh:
    body = plate()
    uv = np.zeros((len(body.vertices), 2))
    uv[:, 0] = (body.vertices[:, 0] + 10.0) / 20.0
    uv[:, 1] = (body.vertices[:, 1] + 10.0) / 20.0
    body.visual = trimesh.visual.TextureVisuals(uv=uv, image=image)
    return body


# --- die Farbe lesen ------------------------------------------------------------


def test_a_plain_body_carries_no_colour() -> None:
    assert texture.face_colours(plate()) is None


def test_face_colours_are_read_as_they_are() -> None:
    colours = texture.face_colours(painted([(255, 0, 0), (0, 0, 255)]))

    assert colours is not None
    assert np.unique(colours, axis=0).shape == (2, 3)


def test_a_texture_is_sampled_at_the_centre_of_the_triangle() -> None:
    """Die Ecken zu mitteln erfände ein Violett, das in keinem Filament ist."""
    image = Image.new("RGB", (32, 32), (255, 0, 0))
    for column in range(16):
        for row in range(32):
            image.putpixel((column, row), (0, 0, 255))

    colours = texture.face_colours(textured(image))

    assert colours is not None
    assert np.unique(colours, axis=0).shape == (2, 3), "two colours in, two colours out"


def test_a_pbr_texture_is_tinted_by_its_base_colour_factor() -> None:
    body = textured(Image.new("RGB", (2, 2), (255, 255, 255)))
    body.visual.material = trimesh.visual.material.PBRMaterial(
        baseColorTexture=body.visual.material.image,
        baseColorFactor=(32, 128, 255, 255),
    )

    colours = texture.face_colours(body)

    assert colours is not None
    assert colours == pytest.approx(np.tile((32 / 255, 128 / 255, 1.0), (len(body.faces), 1)))


def test_sampling_does_not_expand_the_whole_texture() -> None:
    """Auch eine riesige Textur kostet nur Speicher je Dreieck, nicht je Pixel."""

    class Pixels:
        def __getitem__(self, _position: tuple[int, int]) -> tuple[int, int, int]:
            return (24, 140, 220)

    class HugeImage:
        size = (32_768, 32_768)

        def convert(self, _mode: str) -> HugeImage:
            return self

        def load(self) -> Pixels:
            return Pixels()

    body = textured(HugeImage())  # type: ignore[arg-type]

    colours = texture.face_colours(body)

    assert colours is not None
    assert colours == pytest.approx(np.tile((24 / 255, 140 / 255, 220 / 255), (len(body.faces), 1)))


# --- quantisation ---------------------------------------------------------------


def test_fewer_colours_than_filaments_stay_as_they_are() -> None:
    colours = np.array([[1.0, 0.0, 0.0]] * 5 + [[0.0, 0.0, 1.0]] * 5)

    result = texture.quantise(colours, 4, seed=0)

    assert result.count == 2, "three filaments for two colours would be a lie"
    assert set(result.labels.tolist()) == {0, 1}


def test_the_same_seed_gives_the_same_assignment() -> None:
    """§20 und §11.3: die Datei muss das Teil auch im nächsten Lauf
    beschreiben.
    """
    generator = np.random.default_rng(7)
    colours = generator.random((400, 3))

    first = texture.quantise(colours, 4, seed=42)
    second = texture.quantise(colours, 4, seed=42)

    assert np.array_equal(first.labels, second.labels)
    assert np.allclose(first.centres, second.centres)


def test_the_starting_value_is_the_only_source_of_chance() -> None:
    """Zwei Startwerte dürfen sich unterscheiden — sonst nichts."""
    generator = np.random.default_rng(7)
    colours = np.vstack(
        [
            generator.normal(centre, 0.02, size=(120, 3))
            for centre in ([0.9, 0.1, 0.1], [0.1, 0.1, 0.9], [0.9, 0.9, 0.9])
        ]
    )

    for seed in (0, 1, 2, 3):
        result = texture.quantise(colours, 3, seed=seed)
        assert result.count == 3
        # Gut getrennte Cluster kommen gleich heraus, wie auch immer der Start
        # gezogen wurde.
        assert sorted(np.bincount(result.labels).tolist()) == [120, 120, 120]


def test_quantising_onto_one_filament_is_allowed() -> None:
    generator = np.random.default_rng(3)
    result = texture.quantise(generator.random((50, 3)), 1, seed=0)

    assert result.count == 1
    assert set(result.labels.tolist()) == {0}


def test_a_quantisation_needs_a_colour() -> None:
    with pytest.raises(ValueError):
        texture.quantise(np.zeros((3, 3)), 0, seed=0)


# --- smoothing ------------------------------------------------------------------


def test_a_single_stray_triangle_is_taken_back() -> None:
    body = plate()
    labels = np.zeros(len(body.faces), dtype=np.int32)
    labels[len(body.faces) // 2] = 1

    result = texture.smooth(body, labels)

    assert set(result.tolist()) == {0}, "one triangle is not a filament change"


def test_a_real_boundary_survives_the_smoothing() -> None:
    body = plate()
    labels = (body.triangles_center[:, 0] > 0).astype(np.int32)

    result = texture.smooth(body, labels)

    assert np.array_equal(result, labels), "half a plate is not speckle"


# --- der ganze Weg --------------------------------------------------------------


def test_four_colours_onto_two_filaments() -> None:
    body = painted([(255, 0, 0), (240, 20, 20), (0, 0, 255), (20, 20, 240)])

    mesh, slots = texture.to_slots(MeshData.of(body), 2, seed=1)

    assert len(slots) == 2
    assert used_slots(mesh) == (0, 1)
    left, right = (counts(mesh)[index] for index in (0, 1))
    assert left == pytest.approx(right, rel=0.1), "the plate was painted in halves"


def test_a_patch_too_small_for_a_filament_change_is_dropped() -> None:
    body = plate()
    colours = np.zeros((len(body.faces), 4), dtype=np.uint8)
    colours[:, 3] = 255
    colours[:, :3] = (255, 0, 0)
    colours[0, :3] = (0, 255, 0)
    body.visual.face_colors = colours

    _mesh, slots = texture.to_slots(MeshData.of(body), 4, seed=0)

    assert len(slots) == 1, "one triangle of green is not worth an AMS slot"


def test_a_body_without_colour_keeps_what_it_had() -> None:
    mesh = MeshData.of(plate())

    result, slots = texture.to_slots(mesh, 4, seed=0)

    assert slots == []
    assert result.slots == ()


def test_the_slot_colours_are_the_ones_that_will_be_shown() -> None:
    mesh, slots = texture.to_slots(MeshData.of(painted([(255, 0, 0), (0, 0, 255)])), 2, seed=0)

    assert used_slots(mesh) == (0, 1)
    shown = sorted(slot.colour for slot in slots if slot.colour is not None)
    assert shown[0] == pytest.approx((0.0, 0.0, 1.0), abs=0.01)
    assert shown[1] == pytest.approx((1.0, 0.0, 0.0), abs=0.01)


# --- as operations --------------------------------------------------------------


def run(op: str, entry: SceneObject, profile: Profile, seed: int | None = None, **params: object):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=seed,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_assign_slot_paints_the_whole_object(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Deckel", mesh=MeshData.of(plate()))

    result = run("assign_slot", entry, profile, slot=2, name="Rot", colour="#FF0000")

    output = result.outputs[0]
    assert used_slots(output.mesh) == (2,)
    assert output.material_slots[0].colour == pytest.approx((1.0, 0.0, 0.0))
    assert output.material_slots[0].name == "Rot"


def test_assign_slot_rejects_a_colour_it_cannot_read(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Deckel", mesh=MeshData.of(plate()))

    with pytest.raises(ValidationError) as problem:
        run("assign_slot", entry, profile, slot=0, colour="rot")

    assert problem.value.field == "colour"


def test_slots_from_texture_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(
        id="obj_1", name="Figur", mesh=MeshData.of(painted([(255, 0, 0), (0, 0, 255)]))
    )

    result = run("slots_from_texture", entry, profile, seed=5, filaments=2)

    assert used_slots(result.outputs[0].mesh) == (0, 1)
    assert len(result.outputs[0].material_slots) == 2
    assert [finding.code for finding in result.findings] == ["colour.quantised"]


def test_slots_from_texture_says_when_there_is_nothing_to_convert(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Figur", mesh=MeshData.of(plate()))

    result = run("slots_from_texture", entry, profile, seed=0, filaments=4)

    assert [finding.code for finding in result.findings] == ["colour.no_texture"]
    assert result.outputs[0] is entry, "nothing was changed, so nothing is replaced"


def test_slots_from_texture_reports_when_the_model_has_fewer_colours(profile: Profile) -> None:
    entry = SceneObject(
        id="obj_1", name="Figur", mesh=MeshData.of(painted([(255, 0, 0), (0, 0, 255)]))
    )

    result = run("slots_from_texture", entry, profile, seed=0, filaments=5)

    assert "colour.fewer_than_asked" in [finding.code for finding in result.findings]
