"""Ein offener Zylindermantel bekommt einen Radius, keine erfundene scharfe Kante."""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import GeometryError
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Feature, OpContext, Profile, Scene, SceneObject


def _clip(kind: str) -> SceneObject:
    """Dieselbe abgegrenzte 184-Grad-Zylinderhaut an beiden Kernen."""
    if kind == "mesh":
        path = Path(__file__).parent / "data" / "meshes" / "open_cylinder_clip.stl"
        mesh = MeshData.of(trimesh.load_mesh(path, process=True))
        return SceneObject(id="clip", name="Clip", mesh=mesh, features=detect(mesh))

    pytest.importorskip("OCP")
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid

    outer = Solid(BRepPrimAPI_MakeCylinder(16.0, 17.0, math.radians(184.0)).Shape())
    inner = Solid(BRepPrimAPI_MakeCylinder(12.0, 17.0, math.radians(184.0)).Shape())
    body = edit.boolean("difference", [outer, inner])
    return SceneObject(id="clip", name="Clip", kind="brep", mesh=body, features=features_of(body))


def _inner(entry: SceneObject) -> Feature:
    return min(
        (feature for feature in entry.features.values() if feature.kind == "fillet"),
        key=lambda feature: float(feature.params["radius"]),
    )


def _redescribed(entry: SceneObject) -> SceneObject:
    """Die neue Topologie wird wie nach der Auswertung frisch gelesen."""
    if entry.kind == "brep":
        from app.core.brep.features import features_of

        features = features_of(entry.mesh)
    else:
        features = detect(as_mesh_data(entry.mesh))
    return dataclasses.replace(entry, features=features)


def _edit(entry: SceneObject, operation: str, profile: Profile, **params: object) -> SceneObject:
    """Eine registrierte Handlung mit derselben Merkmalswahl wie im Auswahlpanel."""
    load_operations()
    spec = REGISTRY.get(operation)
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(at_feature=_inner(entry).id, **params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, message: None,
            ask=lambda question, options: options[0],
            cancelled=NeverCancelled(),
        )
    )
    return _redescribed(result.outputs[0])


def _resize(entry: SceneObject, radius: float, profile: Profile) -> SceneObject:
    return _edit(entry, "resize_feature", profile, diameter=2.0 * radius)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("tilted", [False, True])
def test_an_open_cylinder_changes_only_its_inner_radius(
    kind: str, tilted: bool, profile: Profile
) -> None:
    """Vergrößern, verkleinern, wiederholen: Außenradius und Höhe bleiben fest."""
    source = _clip(kind)
    if tilted:
        transform = trimesh.transformations.rotation_matrix(math.radians(31.0), (1.0, 2.0, 3.0))
        transform[:3, 3] = (103.0, -27.0, 48.0)
        if kind == "brep":
            from app.core.brep.edit import transformed

            moved = transformed(source.mesh, transform)
        else:
            raw = as_mesh_data(source.mesh).raw.copy()
            raw.apply_transform(transform)
            moved = MeshData.of(raw)
        source = _redescribed(dataclasses.replace(source, mesh=moved))
    source_vertices = np.array(as_mesh_data(source.mesh).raw.vertices, copy=True)
    source_volume = source.mesh.volume
    entry = source
    sweep = math.radians(184.0)
    factor = 72.0 * math.sin(sweep / 72.0) if kind == "mesh" else sweep

    for radius in (13.0, 11.0, 13.0):
        entry = _resize(entry, radius, profile)
        body = as_mesh_data(entry.mesh).raw
        assert entry.kind == kind
        assert body.is_watertight and body.is_winding_consistent
        assert len(body.split()) == 1
        assert entry.mesh.volume == pytest.approx(
            17.0 * factor * (16.0**2 - radius**2) / 2.0, abs=0.001
        )
        assert float(_inner(entry).params["radius"]) == pytest.approx(radius, abs=0.001)
        assert _inner(entry).params.get("radial") is True
        outer = max(
            (feature for feature in entry.features.values() if feature.kind == "fillet"),
            key=lambda feature: float(feature.params["radius"]),
        )
        assert float(outer.params["radius"]) == pytest.approx(16.0, abs=0.001)
        assert np.ptp(body.vertices @ np.asarray(_inner(entry).params["axis"])) == pytest.approx(
            17.0, abs=0.001
        )

    assert source.mesh.volume == pytest.approx(source_volume, abs=0.000001)
    assert np.array_equal(as_mesh_data(source.mesh).raw.vertices, source_vertices)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_cylindrical_side_wall_has_no_sharp_corner_to_restore(
    kind: str, profile: Profile
) -> None:
    """Auch der direkte API-Weg verweigert die erfundene Kante ohne Quelländerung."""
    source = _clip(kind)
    vertices = np.array(as_mesh_data(source.mesh).raw.vertices, copy=True)
    volume = source.mesh.volume
    with pytest.raises(GeometryError) as failure:
        _edit(source, "remove_feature", profile)
    assert "keine abgerundete Kante" in str(failure.value)
    assert source.mesh.volume == pytest.approx(volume, abs=0.000001)
    assert np.array_equal(as_mesh_data(source.mesh).raw.vertices, vertices)


def test_radial_changes_retriangulate_the_planar_caps_when_needed(profile: Profile) -> None:
    """Innenknoten im ebenen Deckel dürfen die neue Öffnung nicht verengen."""
    path = Path(__file__).parent / "data" / "meshes" / "open_cylinder_clip_cap_nodes.stl"
    body = MeshData.of(trimesh.load_mesh(path, process=True))
    source = SceneObject(id="clip", name="Clip", mesh=body, features=detect(body))
    entry = source
    factor = 72.0 * math.sin(math.radians(184.0) / 72.0)
    for radius in (14.0, 11.0, 14.0):
        entry = _resize(entry, radius, profile)
        assert entry.mesh.is_watertight and entry.mesh.component_count == 1
        assert float(_inner(entry).params["radius"]) == pytest.approx(radius, abs=0.001)
        assert entry.mesh.volume == pytest.approx(
            17.0 * factor * (16.0**2 - radius**2) / 2.0, abs=0.001
        )
        assert entry.mesh.bounds.maximum[2] == pytest.approx(17.0, abs=0.000001)
        assert entry.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=0.000001)
    assert source.mesh.volume == pytest.approx(17.0 * factor * (16.0**2 - 12.0**2) / 2.0, abs=0.001)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_the_inner_radius_cannot_cross_the_outer_wall(kind: str, profile: Profile) -> None:
    """Eine Radiusänderung darf die tragende Wand nicht wegnehmen."""
    source = _clip(kind)
    volume = source.mesh.volume
    with pytest.raises(GeometryError):
        _resize(source, 17.0, profile)
    assert source.mesh.volume == pytest.approx(volume, abs=0.000001)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_radial_edit_stays_within_its_selected_angular_patch(kind: str, profile: Profile) -> None:
    """Material auf der Gegenseite derselben Achse liegt außerhalb der gewählten Haut."""
    source = _clip(kind)
    if kind == "brep":
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.gp import gp_Pnt

        from app.core.brep import edit
        from app.core.brep.kernel import Solid

        witness = Solid(BRepPrimAPI_MakeBox(gp_Pnt(-0.5, -13.0, 3.5), 1.0, 1.0, 10.0).Shape())
        joined = edit.boolean("union", [source.mesh, witness])
    else:
        witness = trimesh.creation.box(extents=(1.0, 1.0, 10.0))
        witness.apply_translation((0.0, -12.5, 8.5))
        joined = MeshData.of(trimesh.util.concatenate([as_mesh_data(source.mesh).raw, witness]))
    source = _redescribed(dataclasses.replace(source, mesh=joined))
    reference = _resize(_clip(kind), 13.0, profile)
    edited = _resize(source, 13.0, profile)
    assert edited.mesh.component_count == 2
    assert edited.mesh.volume == pytest.approx(reference.mesh.volume + 10.0, abs=0.001)
    pieces = as_mesh_data(edited.mesh).raw.split()
    saved = min(pieces, key=lambda piece: float(piece.volume))
    assert saved.volume == pytest.approx(10.0, abs=0.001)
    assert saved.bounds == pytest.approx(np.array([[-0.5, -13.0, 3.5], [0.5, -12.0, 13.5]]))
