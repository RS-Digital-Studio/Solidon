"""Öffnungswahl ist an die reale Trägerfläche gebunden und nie an Listenplätze."""

import json
from dataclasses import replace

import numpy as np
import pytest

from app.core.deferred import trimesh
from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.geom.seal import match_opening, opening_choices
from app.core.types import Feature, FeatureRef, SceneObject


def plate():
    import manifold3d as m

    body = m.Manifold.cube((60, 40, 6), center=True)
    for x in (-12, 12):
        body -= m.Manifold.cylinder(10, 5, circular_segments=48, center=True).translate((x, 0, 0))
    built = body.to_mesh64()
    mesh = MeshData.of(
        trimesh.Trimesh(
            vertices=np.array(built.vert_properties[:, :3]),
            faces=np.array(built.tri_verts),
            process=False,
        )
    )
    indices = np.flatnonzero(mesh.raw.face_normals[:, 2] > 0.99)
    feature = Feature(
        "top",
        "face",
        "generated",
        {"normal": (0, 0, 1), "centre": (0, 0, 3)},
        face_indices=tuple(int(index) for index in indices),
    )
    return SceneObject("plate", "Prüfplatte", mesh, features={"top": feature})


def test_similar_openings_stay_distinct_when_candidates_are_reordered():
    source = plate()
    choices = opening_choices(source, FeatureRef("plate", "top"))
    assert len(choices) == 2
    for selected in choices:
        assert match_opening(tuple(reversed(choices)), selected.signature) is selected
    assert choices[0].signature != choices[1].signature


def test_signature_follows_a_real_rigidly_moved_carrier_frame():
    source = plate()
    choices = opening_choices(source, FeatureRef("plate", "top"))
    matrix = trimesh.transformations.rotation_matrix(0.71, (1, 2, 3))
    matrix[:3, 3] = (30, -15, 7)
    raw = source.mesh.raw.copy()
    raw.apply_transform(matrix)
    feature = source.features["top"]
    moved = replace(
        source,
        mesh=MeshData.of(raw),
        features={
            "top": replace(
                feature,
                params={
                    "normal": matrix[:3, :3] @ np.array((0, 0, 1)),
                    "centre": matrix[:3, :3] @ np.array((0, 0, 3)) + matrix[:3, 3],
                },
            )
        },
    )
    after = opening_choices(moved, FeatureRef("plate", "top"))
    for choice in choices:
        found = match_opening(after, choice.signature)
        assert found is not None
        assert found.centre == pytest.approx(choice.centre, abs=1e-8)
        assert found.area == pytest.approx(choice.area, abs=1e-8)


def test_changed_carrier_geometry_requires_a_new_visible_choice():
    source = plate()
    selected = opening_choices(source, FeatureRef("plate", "top"))[0]
    raw = source.mesh.raw.copy()
    raw.vertices[:, 0] *= 1.1
    changed = opening_choices(replace(source, mesh=MeshData.of(raw)), FeatureRef("plate", "top"))
    assert match_opening(changed, selected.signature) is None


def test_two_geometrically_equal_answers_remain_ambiguous():
    choices = opening_choices(plate(), FeatureRef("plate", "top"))
    assert match_opening((choices[0], choices[0]), choices[0].signature) is None


@pytest.mark.parametrize(
    "text",
    ["{broken", "{}", "[]", '{"version":999}', "x" * 1_048_577],
    ids=["broken", "empty", "list", "future", "oversized"],
)
def test_signature_is_bounded_versioned_data(text):
    with pytest.raises(ValidationError) as caught:
        match_opening((), text)
    assert caught.value.suggestions


def test_signature_rejects_nonfinite_geometry_and_unknown_fields():
    choices = opening_choices(plate(), FeatureRef("plate", "top"))
    payload = json.loads(choices[0].signature)
    payload["ring"][0][0] = float("nan")
    with pytest.raises(ValidationError):
        match_opening(choices, json.dumps(payload))
    payload = json.loads(choices[0].signature)
    payload["source_code"] = "__import__('os')"
    with pytest.raises(ValidationError):
        match_opening(choices, json.dumps(payload))


def test_wrong_object_reference_is_not_reinterpreted_as_the_input_face():
    with pytest.raises(ValidationError):
        opening_choices(plate(), FeatureRef("other", "top"))


def test_large_json_integers_and_duplicate_keys_are_rejected_as_data_errors():
    choices = opening_choices(plate(), FeatureRef("plate", "top"))
    payload = json.loads(choices[0].signature)
    payload["ring"][0][0] = 10**400
    with pytest.raises(ValidationError):
        match_opening(choices, json.dumps(payload))
    with pytest.raises(ValidationError):
        match_opening(
            choices, choices[0].signature.replace('"version":1', '"version":1,"version":1')
        )
    assert choices[0].carrier is choices[1].carrier
