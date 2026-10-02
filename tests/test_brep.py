"""Der zweite Konstruktionskern (Bauplan §30; §40 für P12).

Drei Sätze entscheiden diese Phase: eine Verrundung an einer Referenzkante
geometrisch exakt, STEP fähig zur runden Reise, und die Mesh/B-Rep-Markierung
richtig. Jeder davon wird gegen eine Zahl gemessen, die sich von Hand
nachrechnen lässt, nicht gegen ein Bild.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import trimesh

from app.core.brep import edit, profiles, step
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, tessellate
from app.core.errors import GeometryError, NeedsSolidError, ValidationError
from app.core.export.writer import export_bytes, plan_export, write_plan
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cancel import NeverCancelled
from app.core.scene.project import ProjectSources, new_project
from app.core.sketch.profile import Profile as Outline
from app.core.sketch.profile import ProfileSegment as Segment
from app.core.types import Mesh, OpContext, Profile, Scene, SceneObject, Source, kind_of
from app.core.units import EPS_DISPLAY, EPS_GEOM
from tests.helpers import CountingToken, exact_kernel

exact_kernel()

BRepPrimAPI_MakeSphere = importlib.import_module("OCP.BRepPrimAPI").BRepPrimAPI_MakeSphere

WIDTH, DEPTH, HEIGHT = 40.0, 30.0, 20.0


def block() -> Solid:
    return edit.box(WIDTH, DEPTH, HEIGHT)


def _coloured_block() -> Solid:
    """Der Quader trägt oben Slot drei und auf den übrigen Flächen Slot zwei."""
    import numpy as np

    body = block()
    top = np.all(np.abs(body.raw.triangles[:, :, 2] - HEIGHT) <= EPS_GEOM, axis=1)
    return body.with_triangle_slots(tuple(int(value) for value in np.where(top, 3, 2)))


@pytest.mark.parametrize(
    "matrix",
    [
        ((1.0, 0.0, 0.0, 13.0), (0.0, 1.0, 0.0, -5.0), (0.0, 0.0, 1.0, 7.0), (0, 0, 0, 1)),
        ((0.0, -1.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0, 0, 0, 1)),
        ((-1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0, 0, 0, 1)),
        ((1.5, 0.2, 0.0, 0.0), (0.0, 0.8, 0.0, 0.0), (0.0, 0.0, 2.0, 0.0), (0, 0, 0, 1)),
    ],
    ids=["translation", "rotation", "reflection", "affine"],
)
def test_exact_face_filaments_follow_the_native_transform(matrix) -> None:
    """Der inverse Ort jedes Ergebnisdreiecks entscheidet unabhängig über sein Filament."""
    import dataclasses

    import numpy as np

    original = _coloured_block()
    result = edit.transformed(original, matrix)
    assert isinstance(result, Solid)
    for deflection in (0.4, 0.01):
        mesh = dataclasses.replace(result, deflection=deflection).mesh
        inverse = np.linalg.inv(matrix)
        points = mesh.raw.triangles_center @ inverse[:3, :3].T + inverse[:3, 3]
        top = np.abs(points[:, 2] - HEIGHT) <= EPS_GEOM
        assert set(mesh.slots) == {2, 3}
        assert np.array_equal(np.asarray(mesh.slots), np.where(top, 3, 2))
    assert set(original.mesh.slots) == {2, 3}


@pytest.mark.parametrize("kind", ["difference", "union", "intersection"])
def test_exact_boolean_keeps_old_face_filaments_and_neutral_cut_faces(kind: str) -> None:
    """Echte alte Randflächen behalten ihre Herkunft; eine Abzugsfläche übernimmt kein Werkzeug."""
    import numpy as np

    original = _coloured_block()
    tool = edit.moved(edit.box(WIDTH, DEPTH, HEIGHT), (WIDTH / 2, 0.0, 0.0))
    tool = tool.with_triangle_slots((4,) * tool.triangle_count)
    result = edit.boolean(kind, [original, tool])
    mesh = result.mesh
    points = np.asarray(mesh.raw.triangles_center)
    normals = np.asarray(mesh.raw.face_normals)
    expected = np.full(mesh.triangle_count, 2)
    expected[np.abs(points[:, 2] - HEIGHT) <= EPS_GEOM] = 3
    if kind == "difference":
        expected[np.abs(points[:, 0]) <= EPS_GEOM] = 0
        assert set(expected) == {0, 2, 3}
    elif kind == "union":
        expected[points[:, 0] > WIDTH / 2 + EPS_GEOM] = 4
        assert set(expected) == {2, 3, 4}
    else:
        expected[(np.abs(points[:, 0]) <= EPS_GEOM) & (normals[:, 0] < -0.9)] = 4
        assert set(expected) == {2, 3, 4}
    assert np.array_equal(np.asarray(mesh.slots), expected)
    assert result.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT * (1.5 if kind == "union" else 0.5)
    )


def test_exact_fillet_keeps_old_faces_and_marks_new_round_surfaces_neutral() -> None:
    import numpy as np

    result = edit.fillet(_coloured_block(), 2.0, "vertical")
    points = result.raw.triangles_center
    normals = np.abs(result.raw.face_normals)
    vertical_planes = np.any(np.abs(normals[:, :2] - 1.0) <= EPS_GEOM, axis=1)
    top = np.abs(points[:, 2] - HEIGHT) <= EPS_GEOM
    bottom = np.abs(points[:, 2]) <= EPS_GEOM
    expected = np.where(top, 3, np.where(vertical_planes | bottom, 2, 0))
    assert set(expected) == {0, 2, 3}
    assert np.array_equal(np.asarray(result.mesh.slots), expected)


@pytest.mark.parametrize("operation", ["shell", "draft", "push"])
def test_exact_profile_edits_preserve_filaments_on_surviving_surfaces(operation: str) -> None:
    import numpy as np

    from app.core.brep import profiles

    source = _coloured_block()
    if operation == "shell":
        result = profiles.shell_open_top(source, 2.0)
    elif operation == "draft":
        result = profiles.draft_vertical(source, 3.0)
    else:
        result = profiles.push_faces(source, (0.0, 0.0, 1.0), 2.0)
    points = result.raw.triangles_center
    if operation == "shell":
        outer = (
            (np.abs(np.abs(points[:, 0]) - WIDTH / 2) <= EPS_GEOM)
            | (np.abs(np.abs(points[:, 1]) - DEPTH / 2) <= EPS_GEOM)
            | (np.abs(points[:, 2]) <= EPS_GEOM)
        )
        # Der stehen gebliebene Rand oben gehört weiterhin zur ursprünglichen Deckfläche.
        top = np.abs(points[:, 2] - HEIGHT) <= EPS_GEOM
        expected = np.where(outer, 2, np.where(top, 3, 0))
        assert set(expected) == {0, 2, 3}
    elif operation == "draft":
        expected = np.where(np.abs(points[:, 2] - HEIGHT) <= EPS_GEOM, 3, 2)
        assert set(expected) == {2, 3}
    else:
        expected = np.where(points[:, 2] > HEIGHT + EPS_GEOM, 0, 2)
        assert set(expected) == {0, 2}
    assert np.array_equal(np.asarray(result.mesh.slots), expected)


def test_exact_slot_followup_preserves_the_boundary_between_coplanar_filaments() -> None:
    """Das Langloch entfernt künstliche Nähte, aber keine echte Filamentgrenze."""
    import dataclasses

    import numpy as np

    first = _coloured_block()
    second = edit.moved(block(), (WIDTH / 2, 0.0, 0.0))
    second = second.with_triangle_slots((4,) * second.triangle_count)
    source = edit.boolean("union", [first, second])
    result = edit.slot_bore(
        source,
        position=(-10.0, 0.0, HEIGHT / 2),
        direction=(0.0, 0.0, 1.0),
        diameter=4.0,
        depth=HEIGHT + 2.0,
        length=8.0,
        angle_deg=0.0,
        overlap=0.0,
    )
    for solid in (result, dataclasses.replace(result, deflection=0.01)):
        triangles = solid.raw.triangles
        top = np.all(np.abs(triangles[:, :, 2] - HEIGHT) <= EPS_GEOM, axis=1)
        points = triangles.mean(axis=1)
        assert top.any()
        assert np.array_equal(
            np.asarray(solid.mesh.slots)[top], np.where(points[top, 0] > WIDTH / 2, 4, 3)
        )
        # Kein Deckdreieck überbrückt die Materialgrenze bei x = 20.
        assert not np.any(
            (triangles[top, :, 0].min(axis=1) < WIDTH / 2 - EPS_GEOM)
            & (triangles[top, :, 0].max(axis=1) > WIDTH / 2 + EPS_GEOM)
        )


def test_native_face_attributes_follow_a_copy_with_reordered_faces(monkeypatch) -> None:
    """Eine echte Compound-Kopie kehrt die Körperreihenfolge um; die Farben bleiben örtlich."""
    import dataclasses

    import numpy as np
    from OCP.BRep import BRep_Builder
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_COMPOUND, TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS_Compound

    from app.core.brep import kernel

    left = edit.moved(block(), (-40.0, 0.0, 0.0))
    right = edit.moved(block(), (40.0, 0.0, 0.0))
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    builder.Add(compound, left.shape)
    builder.Add(compound, right.shape)
    source = Solid(compound)
    slots = tuple(int(value) for value in np.where(source.raw.triangles_center[:, 0] < 0, 2, 4))
    original_mapping = np.asarray(source.raw.face_attributes[kernel._FACE_ATTRIBUTE]).copy()
    original_copy = kernel.copy_shape

    def reordered_copy(shape):
        copied, mapping, edges = original_copy(shape)
        if copied.ShapeType() != TopAbs_COMPOUND:
            return copied, mapping, edges
        children = ShapeMap()
        TopExp.MapShapes_s(copied, TopAbs_SOLID, children)
        reordered = TopoDS_Compound()
        builder.MakeCompound(reordered)
        for index in range(children.Extent(), 0, -1):
            builder.Add(reordered, children.FindKey(index))

        def renumbered(kind, old_mapping):
            old, new = ShapeMap(), ShapeMap()
            TopExp.MapShapes_s(copied, kind, old)
            TopExp.MapShapes_s(reordered, kind, new)
            return tuple(int(new.FindIndex(old.FindKey(target + 1))) - 1 for target in old_mapping)

        return reordered, renumbered(TopAbs_FACE, mapping), renumbered(TopAbs_EDGE, edges)

    monkeypatch.setattr(kernel, "copy_shape", reordered_copy)
    assigned = source.with_triangle_slots(slots)
    assert assigned._copied_faces != tuple(range(source.face_count))
    assert np.array_equal(assigned.raw.triangles, source.raw.triangles)
    assert np.array_equal(source.raw.face_attributes[kernel._FACE_ATTRIBUTE], original_mapping)
    for result in (assigned, dataclasses.replace(assigned, deflection=0.01)):
        expected = np.where(result.raw.triangles_center[:, 0] < 0, 2, 4)
        assert np.array_equal(np.asarray(result.mesh.slots), expected)
        for face_index in range(result.face_count):
            indices = result.triangles_of_face(face_index)
            assert indices
            assert result.faces_of_triangles(indices) == (face_index,)
    assert source.mesh.slots == ()


def test_native_attribute_history_does_not_hide_a_conflicting_merge() -> None:
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

    source = _coloured_block()
    other = edit.moved(block(), (WIDTH, 0.0, 0.0))
    other = other.with_triangle_slots((4,) * other.triangle_count)
    joined = edit.boolean("union", [source, other])
    unifier = ShapeUpgrade_UnifySameDomain(joined.shape, True, True, False)
    unifier.Build()
    with pytest.raises(ValidationError) as failure:
        joined.replacing(unifier.Shape(), history=unifier.History())
    assert failure.value.suggestions


def test_native_attribute_history_honours_cancellation() -> None:
    from app.core.brep.kernel import carried_face_slots
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = _coloured_block()
    cancelled = CancelSignal()
    cancelled.cancel()
    with pytest.raises(OperationCancelled):
        carried_face_slots(source.shape, [(source.shape, source.face_slots)], cancelled=cancelled)
    with pytest.raises(OperationCancelled):
        source.with_triangle_slots((4,) * source.triangle_count, cancelled=cancelled)


@pytest.mark.parametrize("broken", ["missing", "short", "outside"])
def test_native_filaments_require_a_complete_triangle_face_mapping(broken: str) -> None:
    import numpy as np

    from app.core.brep.kernel import _FACE_ATTRIBUTE
    from app.core.errors import InternalError

    source = block()
    mapping = np.asarray(source.raw.face_attributes[_FACE_ATTRIBUTE]).copy()
    if broken == "missing":
        del source.raw.face_attributes[_FACE_ATTRIBUTE]
    elif broken == "short":
        source.raw.face_attributes[_FACE_ATTRIBUTE] = mapping[:-1]
    else:
        mapping[0] = source.face_count
        source.raw.face_attributes[_FACE_ATTRIBUTE] = mapping
    with pytest.raises(InternalError):
        source.with_triangle_slots((2,) * source.triangle_count)


@pytest.mark.parametrize("slots", [(2,), (8,) * 6, (-1,) * 6])
def test_native_filament_constructor_rejects_invalid_face_slots(slots) -> None:
    from app.core.errors import InternalError

    source = block()
    with pytest.raises(InternalError):
        Solid(source.shape, face_slots=slots)


@pytest.mark.parametrize("slot", [False, True])
@pytest.mark.parametrize("entry", ["face", "triangle"])
def test_native_filament_rejects_boolean_slot_numbers(slot: bool, entry: str) -> None:
    from app.core.errors import InternalError

    source = block()
    with pytest.raises(InternalError):
        if entry == "face":
            Solid(source.shape, face_slots=(slot,) * source.face_count)
        else:
            source.with_triangle_slots((slot,) * source.triangle_count)


def test_native_filament_storage_cannot_save_part_of_one_face() -> None:
    source = block()
    values = [0] * source.triangle_count
    values[source.triangles_of_face(0)[0]] = 2
    with pytest.raises(ValidationError) as failure:
        source.with_triangle_slots(tuple(values))
    assert failure.value.suggestions


def test_native_boolean_does_not_treat_missing_attributes_as_an_explicit_colour() -> None:
    """Wie beim Netz darf eine wirklich zugewiesene Quelle die unzugewiesene Fläche färben."""
    import numpy as np

    plain = block()
    assigned = edit.moved(block(), (WIDTH / 2, 0.0, 0.0))
    assigned = assigned.with_triangle_slots((4,) * assigned.triangle_count)
    result = edit.boolean("union", [plain, assigned])
    expected = np.where(result.raw.triangles_center[:, 0] >= -EPS_GEOM, 4, 0)
    assert set(expected) == {0, 4}
    assert np.array_equal(np.asarray(result.mesh.slots), expected)


def _native_affine_shape(source: Solid, diagonal: tuple[float, float, float]) -> Solid:
    """Unabhängige Eingabe: native NURBS-Form ohne Solidons Transformationsweg."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
    from OCP.gp import gp_GTrsf, gp_Mat, gp_XYZ

    x, y, z = diagonal
    transform = gp_GTrsf(gp_Mat(x, 0.0, 0.0, 0.0, y, 0.0, 0.0, 0.0, z), gp_XYZ(7.0, -3.0, 5.0))
    return Solid(BRepBuilderAPI_GTransform(source.shape, transform, True).Shape())


@pytest.mark.parametrize("original_trims", [False, True])
def test_affine_cylinder_integrals_keep_the_ellipse_and_its_location(
    monkeypatch: pytest.MonkeyPatch, original_trims: bool
) -> None:
    """Ein rationaler Ellipsenmantel braucht Integration über seine Knotenspannen."""
    import numpy as np
    from scipy.integrate import quad
    from scipy.special import ellipe

    from app.core.brep import properties

    if original_trims:
        monkeypatch.setattr(properties, "_SUBDIVISIONS", ())

    solid = _native_affine_shape(edit.cylinder(6.0, 8.0), (2.0, 1.0, 0.5))
    assert solid.is_closed and solid.solid_count == 1
    assert solid.volume == pytest.approx(72.0 * math.pi, rel=1e-10)
    expected_area = 36.0 * math.pi + 96.0 * ellipe(0.75)
    assert solid.area == pytest.approx(expected_area, rel=1e-10)
    for kind in ("volume", "surface"):
        assert solid._properties(kind).centre == pytest.approx((7.0, -3.0, 7.0), abs=1e-8)
    assert solid._properties("volume").inertia is None
    perimeter = 24.0 * ellipe(0.75)
    radial_y = quad(
        lambda angle: (
            math.sin(angle) ** 2
            * math.sqrt(36.0 * math.sin(angle) ** 2 + 9.0 * math.cos(angle) ** 2)
        ),
        0.0,
        math.tau,
        epsabs=1e-11,
        epsrel=1e-11,
    )[0]
    radial_x = perimeter - radial_y
    cap = 18.0 * math.pi
    expected = np.diag(
        (
            cap * (9.0 + 16.0) / 2.0 + 36.0 * radial_y + 64.0 / 12.0 * perimeter,
            cap * (36.0 + 16.0) / 2.0 + 144.0 * radial_x + 64.0 / 12.0 * perimeter,
            cap * 45.0 / 2.0 + 144.0 * radial_x + 36.0 * radial_y,
        )
    )
    assert np.asarray(solid._properties("surface").inertia) == pytest.approx(expected, abs=1e-7)


@pytest.mark.parametrize("original_trims", [False, True])
def test_affine_oblate_sphere_surface_is_not_a_coarse_quadrature(
    monkeypatch: pytest.MonkeyPatch, original_trims: bool
) -> None:
    """Die geschlossene Sphäroidformel prüft rationalen U- und V-Verlauf."""
    from app.core.brep import properties

    if original_trims:
        monkeypatch.setattr(properties, "_SUBDIVISIONS", ())
    solid = _native_affine_shape(Solid(BRepPrimAPI_MakeSphere(3.0).Shape()), (2.0, 2.0, 1.0))
    eccentricity = math.sqrt(0.75)
    area = 72.0 * math.pi * (1.0 + 0.25 / eccentricity * math.atanh(eccentricity))
    assert solid.volume == pytest.approx(144.0 * math.pi, rel=1e-10)
    assert solid.area == pytest.approx(area, rel=1e-10)
    assert solid._properties("volume").centre == pytest.approx((7.0, -3.0, 5.0), abs=1e-8)
    assert solid._properties("surface").centre == pytest.approx((7.0, -3.0, 5.0), abs=1e-8)


@pytest.mark.parametrize("original_trims", [False, True])
def test_affine_trimmed_faces_keep_the_hole_area_and_surface_centre(
    monkeypatch: pytest.MonkeyPatch, original_trims: bool
) -> None:
    """Eine versetzte Bohrung trimmt die Deckflächen; ihre Löcher dürfen nicht mitmessen."""
    from scipy.special import ellipe

    from app.core.brep import properties

    if original_trims:
        monkeypatch.setattr(properties, "_SUBDIVISIONS", ())

    source = edit.bore(edit.box(20.0, 16.0, 8.0), position=(3.0, 1.0, 8.0), axis="z", diameter=4.0)
    solid = _native_affine_shape(source, (2.0, 1.0, 0.5))
    hole_area = 8.0 * math.pi
    mantle_area = 64.0 * ellipe(0.75)
    area = 2.0 * (640.0 - hole_area) + 2.0 * (40.0 + 16.0) * 4.0 + mantle_area
    assert solid.volume == pytest.approx(2560.0 - 32.0 * math.pi, rel=1e-10)
    void_fraction = 32.0 * math.pi / (2560.0 - 32.0 * math.pi)
    assert solid._properties("volume").centre == pytest.approx(
        (7.0 - 6.0 * void_fraction, -3.0 - void_fraction, 7.0), abs=1e-8
    )
    assert solid.area == pytest.approx(area, rel=1e-10)
    removed_surface = 2.0 * hole_area
    centre = solid._properties("surface").centre
    offset = (mantle_area - removed_surface) / area
    assert centre == pytest.approx((7.0 + 6.0 * offset, -3.0 + offset, 7.0), abs=1e-8)


@pytest.mark.parametrize(
    "linear",
    [
        ((2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 2.0)),
        ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((2.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.5)),
        ((1.0, 0.3, 0.0), (0.0, 1.0, 0.2), (0.0, 0.0, 1.0)),
        ((0.0, -2.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 2.0)),
        ((-2.0, -0.3, 0.0), (0.0, 1.0, 0.2), (0.0, 0.0, 0.5)),
    ],
)
def test_affine_transform_maps_each_face_into_the_final_owned_solid(linear) -> None:
    """Unsymmetrische Flächen und Translation entlarven eine erfundene Indexzuordnung."""
    import numpy as np
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    source = edit.box(10.0, 8.0, 6.0)
    matrix = tuple((*row, offset) for row, offset in zip(linear, (7.0, -3.0, 5.0), strict=True))
    result, mapping = edit.transformed_with_faces(source, (*matrix, (0.0, 0.0, 0.0, 1.0)))
    affine = np.asarray(linear)
    determinant = float(np.linalg.det(affine))
    assert result is not source
    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.is_closed and result.solid_count == 1
    assert result.volume == pytest.approx(480.0 * abs(determinant), rel=1e-10)
    assert sorted(mapping) == list(range(6))
    for index, target in enumerate(mapping):
        before = GProp_GProps()
        after = GProp_GProps()
        BRepGProp.SurfaceProperties_s(source.faces()[index], before)
        BRepGProp.SurfaceProperties_s(result.faces()[target], after, 1e-12)
        old = before.CentreOfMass()
        new = after.CentreOfMass()
        expected = affine @ np.array((old.X(), old.Y(), old.Z())) + (7.0, -3.0, 5.0)
        assert (new.X(), new.Y(), new.Z()) == pytest.approx(expected, abs=1e-8)
        assert all(not result.faces()[target].IsPartner(face) for face in source.faces())
    assert source.bounds.minimum == pytest.approx((-5.0, -4.0, 0.0), abs=EPS_GEOM)


@pytest.mark.parametrize("change", ["nan", "infinite", "singular", "projective", "ragged"])
def test_invalid_affine_transforms_stop_with_an_action(change: str) -> None:
    """Ungültige Matrizen dürfen weder orthogonalisiert noch teilweise gelesen werden."""
    import numpy as np

    matrix = np.eye(4)
    if change == "nan":
        matrix[0, 0] = math.nan
    elif change == "infinite":
        matrix[2, 3] = math.inf
    elif change == "singular":
        matrix[1, 1] = 0.0
    elif change == "projective":
        matrix[3, 1] = 0.2
    else:
        matrix = matrix[:3, :3]
    with pytest.raises(GeometryError) as failure:
        edit.transformed(edit.box(10.0, 8.0, 6.0), matrix)
    assert failure.value.suggestions


@pytest.mark.parametrize("original_trims", [False, True])
def test_a_trimmed_bezier_paraboloid_keeps_its_inner_circle(
    monkeypatch: pytest.MonkeyPatch, original_trims: bool
) -> None:
    """z=x²+y² auf einem Kreisring hat eine unabhängige geschlossene Flächenformel."""
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepLib import BRepLib
    from OCP.collections import Array2_gp_Pnt
    from OCP.Geom import Geom_BezierSurface
    from OCP.Geom2d import Geom2d_Circle
    from OCP.gp import gp_Ax2d, gp_Dir2d, gp_Pnt, gp_Pnt2d
    from OCP.TopoDS import TopoDS

    from app.core.brep import properties

    poles = Array2_gp_Pnt(1, 3, 1, 3)
    heights = (1.0, -1.0, 1.0)
    for i in range(3):
        for j in range(3):
            poles.SetValue(i + 1, j + 1, gp_Pnt(i - 1.0, j - 1.0, heights[i] + heights[j]))
    surface = Geom_BezierSurface(poles)

    def rim(radius: float):
        """Ein echter Kreis als Trimmkurve auf der unveränderten Bézier-Fläche."""
        circle = Geom2d_Circle(gp_Ax2d(gp_Pnt2d(0.5, 0.5), gp_Dir2d(1.0, 0.0)), radius)
        return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle, surface).Edge()).Wire()

    builder = BRepBuilderAPI_MakeFace(surface, rim(0.5), True)
    builder.Add(TopoDS.Wire(rim(0.25).Reversed()))
    face = builder.Face()
    BRepLib.BuildCurves3d_s(face)
    assert BRepCheck_Analyzer(face).IsValid()
    if original_trims:
        monkeypatch.setattr(properties, "_SUBDIVISIONS", ())
    result = properties.properties(face, "surface")
    area = math.pi / 6.0 * (5.0**1.5 - 2.0**1.5)
    moment_z = 2.0 * math.pi * ((5.0**2.5 - 2.0**2.5) / 80.0 - (5.0**1.5 - 2.0**1.5) / 48.0)
    assert result.mass == pytest.approx(area, rel=1e-9)
    assert result.centre == pytest.approx((0.0, 0.0, moment_z / area), abs=1e-9)


@pytest.mark.parametrize("knots", [(0.0, 1.0, 2.0, 3.0, 4.0), (0.0, 0.001, 0.21, 0.9, 1.0)])
def test_a_planar_bspline_boundary_keeps_its_exact_green_moments(knots) -> None:
    """Eine analytische Ebene mit BSpline-Rand und Kreisloch hat unabhängige Polynomintegrale."""
    from numpy.polynomial import Polynomial
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.collections import Array1_double, Array1_gp_Pnt, Array1_int
    from OCP.Geom import Geom_BSplineCurve
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pln, gp_Pnt
    from OCP.TopoDS import TopoDS

    from app.core.brep import properties

    points = (
        (0.0, 0.0),
        (2.0, -1.0),
        (6.0, -1.0),
        (8.0, 0.0),
        (10.0, 2.0),
        (10.0, 6.0),
        (8.0, 8.0),
        (6.0, 10.0),
        (2.0, 10.0),
        (0.0, 8.0),
        (-1.0, 6.0),
        (-1.0, 2.0),
        (0.0, 0.0),
    )
    poles = Array1_gp_Pnt(1, len(points))
    parameters = Array1_double(1, len(knots))
    multiplicities = Array1_int(1, len(knots))
    for index, (x, y) in enumerate(points, 1):
        poles.SetValue(index, gp_Pnt(x, y, 0.0))
    for index, value in enumerate(knots, 1):
        parameters.SetValue(index, value)
        multiplicities.SetValue(index, 4 if index in (1, len(knots)) else 3)
    curve = Geom_BSplineCurve(poles, parameters, multiplicities, 3, False)
    outer = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(curve).Edge()).Wire()
    builder = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(), gp_Dir(0.0, 0.0, 1.0)), outer, True)
    circle = gp_Circ(gp_Ax2(gp_Pnt(3.0, 4.0, 0.0), gp_Dir(0.0, 0.0, 1.0)), 1.0)
    inner = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()
    builder.Add(TopoDS.Wire(inner.Reversed()))
    face = builder.Face()
    assert BRepCheck_Analyzer(face).IsValid()
    t = Polynomial((0.0, 1.0))
    basis = ((1.0 - t) ** 3, 3.0 * t * (1.0 - t) ** 2, 3.0 * t**2 * (1.0 - t), t**3)
    area, moment_x, moment_y = -math.pi, -3.0 * math.pi, -4.0 * math.pi
    for start in range(0, 12, 3):
        x = sum(points[start + index][0] * value for index, value in enumerate(basis))
        y = sum(points[start + index][1] * value for index, value in enumerate(basis))
        area += ((x * y.deriv() - y * x.deriv()).integ())(1.0) / 2.0
        moment_x += ((x**2 * y.deriv()).integ())(1.0) / 2.0
        moment_y -= ((y**2 * x.deriv()).integ())(1.0) / 2.0
    result = properties.properties(face, "surface")
    assert result.mass == pytest.approx(area, rel=1e-10)
    assert result.centre == pytest.approx((moment_x / area, moment_y / area, 0.0), abs=1e-9)


@pytest.mark.parametrize("radius", [11.0, 13.0])
def test_an_offset_nurbs_skin_keeps_its_analytic_integrals(radius: float) -> None:
    """Der zweite Radialschritt misst die ganze Offset-Haut statt eines nativen Fehlwerts."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy, BRepBuilderAPI_NurbsConvert
    from OCP.BRepLib import BRepLib
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.TopoDS import TopoDS

    height, turn, target = 17.0, math.radians(184.0), 12.5
    annulus = edit.boolean(
        "difference",
        [
            Solid(BRepPrimAPI_MakeCylinder(16.0, height, turn).Shape()),
            Solid(BRepPrimAPI_MakeCylinder(12.0, height, turn).Shape()),
        ],
    )
    source = Solid(BRepBuilderAPI_NurbsConvert(annulus.shape, True).Shape())
    inner = min(
        (feature for feature in features_of(source).values() if feature.kind == "fillet"),
        key=lambda feature: feature.params["radius"],
    )
    changed = edit.reround(source, inner.params["centre"], 12.0, radius)
    selected = edit._cylinder_at(changed, inner.params["centre"], radius)
    assert selected is not None
    private = BRepBuilderAPI_Copy(selected, True, False).Shape()
    builder = BRepOffsetAPI_MakeThickSolid()
    builder.MakeThickSolidBySimple(private, radius - target)
    assert builder.IsDone()
    shape = TopoDS.Solid(builder.Shape())
    assert BRepLib.OrientClosedSolid_s(shape)
    skin = Solid(shape)
    assert skin.is_closed and skin.solid_count == 1

    low, high = sorted((radius, target))
    sector_area = turn * (high**2 - low**2) / 2.0
    expected_volume = height * sector_area
    expected_area = height * turn * (low + high) + 2.0 * height * (high - low) + 2.0 * sector_area
    centre = (
        (high**3 - low**3) * math.sin(turn) / (3.0 * sector_area),
        (high**3 - low**3) * (1.0 - math.cos(turn)) / (3.0 * sector_area),
        height / 2.0,
    )
    assert skin.volume == pytest.approx(expected_volume, abs=EPS_GEOM)
    assert skin._properties("volume").centre == pytest.approx(centre, abs=EPS_GEOM)
    assert skin.area == pytest.approx(expected_area, abs=EPS_GEOM)


def _ridged_surface_face():
    """Ein Zacken aus ebenen Streifen, zusammen als eine gültige BSpline-Fläche."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.collections import Array1_double, Array1_int, Array2_gp_Pnt
    from OCP.Geom import Geom_BSplineSurface
    from OCP.gp import gp_Pnt

    positions = (0.0, 0.2, 0.20001, 0.20002, 1.0)
    poles = Array2_gp_Pnt(1, 2, 1, 5)
    u_knots, u_mults = Array1_double(1, 2), Array1_int(1, 2)
    v_knots, v_mults = Array1_double(1, 5), Array1_int(1, 5)
    for index, u in enumerate((0.0, 1.0), 1):
        u_knots.SetValue(index, u)
        u_mults.SetValue(index, 2)
        for j, v in enumerate(positions, 1):
            poles.SetValue(index, j, gp_Pnt(u, v, 2.0 if j == 3 else 1.0))
    for index, v in enumerate(positions, 1):
        v_knots.SetValue(index, v)
        v_mults.SetValue(index, 2 if index in (1, 5) else 1)
    surface = Geom_BSplineSurface(poles, u_knots, v_knots, u_mults, v_mults, 1, 1, False, False)
    return BRepBuilderAPI_MakeFace(surface, 1e-9).Face()


@pytest.mark.parametrize("original_trims", [False, True])
def test_a_narrow_surface_span_is_never_missed_by_the_quadrature(
    monkeypatch: pytest.MonkeyPatch, original_trims: bool
) -> None:
    """Die Summe vier ebener Rechtecke widerlegt eine scheinbar fehlerfreie Unterabtastung."""
    from OCP.BRepCheck import BRepCheck_Analyzer

    from app.core.brep import properties

    face = _ridged_surface_face()
    assert BRepCheck_Analyzer(face).IsValid()
    if original_trims:
        monkeypatch.setattr(properties, "_SUBDIVISIONS", ())
    sloping_area = 2.0 * math.sqrt(1.0 + 1e-10)
    flat_area = 1.0 - 2e-5
    expected_area = flat_area + sloping_area
    expected_y = (0.5 - 0.20001 * 2e-5 + 0.20001 * sloping_area) / expected_area
    expected_z = (flat_area + 1.5 * sloping_area) / expected_area
    result = properties.properties(face, "surface")
    assert result.mass == pytest.approx(expected_area, rel=1e-10)
    assert result.centre == pytest.approx((0.5, expected_y, expected_z), abs=1e-9)


@pytest.mark.parametrize("swap", [False, True])
@pytest.mark.parametrize("wrapped", ["offset", "outer_trim", "inner_trim"])
def test_offset_integration_keeps_narrow_basis_knots(
    monkeypatch: pytest.MonkeyPatch, swap: bool, wrapped: str
) -> None:
    """Eine schräg getrimmte Ebene verliert keine unter Offsethüllen verborgene Knotenspanne."""
    import numpy as np
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepLib import BRepLib
    from OCP.Geom import Geom_OffsetSurface, Geom_RectangularTrimmedSurface
    from OCP.Geom2d import Geom2d_Line
    from OCP.gp import gp_Dir2d, gp_Pnt, gp_Pnt2d

    from app.core.brep import properties

    basis = BRepAdaptor_Surface(_ridged_surface_face()).BSpline().Copy()
    for row in range(1, 3):
        for column, y in enumerate((0.0, 0.2, 0.5, 0.8, 1.0), 1):
            basis.SetPole(row, column, gp_Pnt(float(row - 1), y, 0.0))
    if swap:
        basis.ExchangeUV()
    if wrapped == "inner_trim":
        basis = Geom_RectangularTrimmedSurface(basis, 0.0, 1.0, 0.0, 1.0)
    # Die Parametergeschwindigkeit springt, die Fläche und ihre Normale sind
    # trotzdem überall dieselbe Ebene. OCCT darf diese zulässige C0-Basis lesen.
    surface = Geom_OffsetSurface(basis, 2.0, True)
    if wrapped == "outer_trim":
        surface = Geom_RectangularTrimmedSurface(surface, 0.0, 1.0, 0.0, 1.0)
    corners = [(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)]
    if swap:
        corners = [(v, u) for u, v in corners]
    wire = BRepBuilderAPI_MakeWire()
    for start, end in zip(corners, corners[1:] + corners[:1], strict=True):
        direction = (end[0] - start[0], end[1] - start[1])
        curve = Geom2d_Line(gp_Pnt2d(*start), gp_Dir2d(*direction))
        wire.Add(BRepBuilderAPI_MakeEdge(curve, surface, 0.0, math.hypot(*direction)).Edge())
    face = BRepBuilderAPI_MakeFace(surface, wire.Wire(), True).Face()
    assert BRepLib.BuildCurves3d_s(face, EPS_GEOM)
    assert BRepCheck_Analyzer(face).IsValid()
    monkeypatch.setattr(properties, "_SUBDIVISIONS", ())
    result = properties.properties(face, "surface")
    # Die UV-Dreiecksränder werden durch die stückweise lineare Parametrisierung
    # zu diesem bekannten Polygon. Seine Momente kommen aus der Schuhbändelformel.
    v_values = np.array((0.1, 0.2, 0.20001, 0.20002, 0.9))
    y_values = np.interp(v_values, (0.0, 0.2, 0.20001, 0.20002, 1.0), (0.0, 0.2, 0.5, 0.8, 1.0))
    right = np.column_stack((0.95 - 0.5 * v_values, y_values))
    left = np.column_stack((0.05 + 0.5 * v_values, y_values))[::-1]
    polygon = np.concatenate((right, left))
    after = np.roll(polygon, -1, axis=0)
    cross = polygon[:, 0] * after[:, 1] - after[:, 0] * polygon[:, 1]
    area = float(np.sum(cross)) / 2.0
    centre = np.sum((polygon + after) * cross[:, None], axis=0) / (6.0 * area)
    assert result.mass == pytest.approx(area, abs=EPS_GEOM)
    assert result.centre == pytest.approx((*centre, -2.0 if swap else 2.0), abs=EPS_GEOM)


def test_a_narrow_solid_span_keeps_its_volume_and_centre() -> None:
    """Ein Dreieckssteg zählt auch bei scheinbar kleinem GK-Fehler vollständig zum Prisma."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakePolygon,
        BRepBuilderAPI_MakeSolid,
        BRepBuilderAPI_MakeWire,
        BRepBuilderAPI_Sewing,
    )
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.gp import gp_Pnt
    from OCP.TopoDS import TopoDS

    top = _ridged_surface_face()
    surface = BRepAdaptor_Surface(top).BSpline()

    def polygon(points):
        """Eine gerichtete ebene Außenwand des bekannten Prismas."""
        builder = BRepBuilderAPI_MakePolygon()
        for point in points:
            builder.Add(gp_Pnt(*point))
        builder.Close()
        return BRepBuilderAPI_MakeFace(builder.Wire()).Face()

    def side(x: float):
        """Die gesamte gebrochene Oberkante bleibt eine BSpline-Kante der Seitenwand."""
        builder = BRepBuilderAPI_MakeWire()
        builder.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(x, 0.0, 0.0), gp_Pnt(x, 0.0, 1.0)).Edge())
        builder.Add(BRepBuilderAPI_MakeEdge(surface.UIso(x)).Edge())
        builder.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(x, 1.0, 1.0), gp_Pnt(x, 1.0, 0.0)).Edge())
        builder.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(x, 1.0, 0.0), gp_Pnt(x, 0.0, 0.0)).Edge())
        return BRepBuilderAPI_MakeFace(builder.Wire()).Face()

    sewing = BRepBuilderAPI_Sewing(1e-9)
    sewing.Add(top)
    sewing.Add(side(0.0))
    sewing.Add(side(1.0).Reversed())
    sewing.Add(polygon([(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (1.0, 0.0, 0.0)]))
    sewing.Add(polygon([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0), (0.0, 0.0, 1.0)]))
    sewing.Add(polygon([(1.0, 1.0, 0.0), (0.0, 1.0, 0.0), (0.0, 1.0, 1.0), (1.0, 1.0, 1.0)]))
    sewing.Perform()
    solid = Solid(BRepBuilderAPI_MakeSolid(TopoDS.Shell(sewing.SewedShape())).Shape())
    assert BRepCheck_Analyzer(solid.shape).IsValid()
    assert solid.is_closed and solid.solid_count == 1
    assert solid.volume == pytest.approx(1.00001, rel=1e-10)
    assert solid.area == pytest.approx(8.0000000001, rel=1e-10)
    expected_y = (0.5 + 1e-5 * 0.20001) / 1.00001
    expected_z = (0.5 + 1e-5 * 4.0 / 3.0) / 1.00001
    assert solid._properties("volume").centre == pytest.approx(
        (0.5, expected_y, expected_z), abs=1e-9
    )


def test_an_exhausted_surface_integral_stops_without_a_cached_guess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der begrenzte Rückfall darf eine nicht gerechnete Zahl nicht als Maß ablegen."""
    from app.core.brep import properties

    solid = _native_affine_shape(edit.cylinder(6.0, 8.0), (2.0, 1.0, 0.5))
    monkeypatch.setattr(properties, "_SUBDIVISIONS", ())
    monkeypatch.setattr(properties, "_MAX_EVALUATIONS", 0)
    with pytest.raises(GeometryError) as failure:
        _ = solid.area
    assert failure.value.suggestions
    assert "surface" not in solid._cache


@pytest.mark.parametrize("reported_error", [-1.0, 1.0, math.nan, math.inf])
def test_an_unresolved_volume_quadrature_is_not_cached(
    monkeypatch: pytest.MonkeyPatch, reported_error: float
) -> None:
    """Eine ungültige oder zu große Quadraturfehlerschätzung darf keine Kennzahl liefern.

    Der Python-Rückfall ist seit dem knotenzerlegten Verbund die letzte Stufe;
    der Test nimmt den nativen Weg weg, damit die Quadratur überhaupt läuft.
    """
    from scipy import integrate

    from app.core.brep import properties

    solid = _native_affine_shape(edit.cylinder(6.0, 8.0), (2.0, 1.0, 0.5))
    original = integrate.quad_vec

    def uncertain(*args, **kwargs):
        """Rechnet die echten Momente und beschädigt ausschließlich den Fehlernachweis."""
        result, _, info = original(*args, **kwargs)
        return result, reported_error, info

    def unavailable(*args, **kwargs):
        """Der native Verbundweg fällt aus — wie an einer Fläche, die sich nicht teilen lässt."""
        raise ValueError("unavailable native compound")

    monkeypatch.setattr(properties, "_volume_ladder", unavailable)
    monkeypatch.setattr(integrate, "quad_vec", uncertain)
    with pytest.raises(GeometryError) as failure:
        _ = solid.volume
    assert failure.value.suggestions
    assert "volume" not in solid._cache


def test_an_affine_rotated_open_round_bore_retains_its_exact_volume() -> None:
    """Die Schwerpunktintegration dieser gültigen NURBS-Form darf nicht nativ hängen."""
    import numpy as np

    from app.core.geom.transform import rotation

    source = edit.cut_bore(
        edit.box(40.0, 30.0, 10.0),
        position=(19.0, 0.0, 8.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=4.0,
    )
    matrix = np.diag((2.0, 1.0, 0.5, 1.0)) @ rotation("x", 37.0) @ rotation("z", 23.0)
    result = edit.transformed(source, matrix)
    removed_area = 9.0 * (math.pi - math.acos(1.0 / 3.0)) + math.sqrt(8.0)
    assert result.is_closed and result.solid_count == 1
    assert result.volume == pytest.approx(12000.0 - 4.0 * removed_area, rel=1e-10)


@pytest.mark.parametrize("kind", ["surface", "volume"])
@pytest.mark.parametrize("reported_error", [-1.0, 1.0, math.nan, math.inf])
def test_an_unresolved_analytic_integral_is_not_cached(
    monkeypatch: pytest.MonkeyPatch, kind: str, reported_error: float
) -> None:
    """Auch analytische Trägerflächen dürfen ihre gemeldete Rechengrenze nicht übergehen.

    Das Volumen fragt je Fläche ``BRepGProp_Vinert`` nach seinem Fehler, die
    Fläche den Sammelaufruf ``SurfaceProperties`` — beschädigt wird jeweils die
    Auskunft, die der Weg tatsächlich liest.
    """
    from OCP.BRepGProp import BRepGProp, BRepGProp_Vinert

    from app.core.brep import properties

    solid = edit.box(10.0, 8.0, 6.0)
    if kind == "surface":
        monkeypatch.setattr(BRepGProp, "SurfaceProperties_s", lambda *args: reported_error)
    else:
        monkeypatch.setattr(BRepGProp_Vinert, "GetEpsilon", lambda self: reported_error)
    monkeypatch.setattr(properties, "_MAX_EVALUATIONS", 0)
    with pytest.raises(GeometryError) as failure:
        _ = solid.area if kind == "surface" else solid.volume
    assert failure.value.suggestions
    assert kind not in solid._cache


@pytest.mark.parametrize("mass", [-1.0, math.nan, math.inf])
def test_invalid_native_measures_never_reach_the_cache(
    monkeypatch: pytest.MonkeyPatch, mass: float
) -> None:
    """Nach ungültiger nativer Zahl wird nur ein neu berechnetes, richtiges Maß gecacht."""
    from OCP.GProp import GProp_GProps

    solid = edit.box(10.0, 8.0, 6.0)
    monkeypatch.setattr(GProp_GProps, "Mass", lambda self: mass)
    assert solid.area == pytest.approx(376.0, rel=1e-10)
    assert solid._properties("surface").mass == pytest.approx(376.0, rel=1e-10)


def test_the_volume_integral_keeps_reflection_and_separate_bodies() -> None:
    """Gerichtete Flüsse müssen Volumen und gewichteten Schwerpunkt gemeinsam erhalten."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    builder = BRep_Builder()
    shape = TopoDS_Compound()
    builder.MakeCompound(shape)
    builder.Add(shape, edit.cylinder(6.0, 8.0).shape)
    builder.Add(shape, edit.moved(edit.cylinder(4.0, 6.0), (20.0, 4.0, 1.0)).shape)
    solid = _native_affine_shape(Solid(shape), (-2.0, 1.0, 0.5))
    assert solid.solid_count == 2 and solid.is_closed
    assert solid.volume == pytest.approx(96.0 * math.pi, rel=1e-10)
    assert solid._properties("volume").centre == pytest.approx((-3.0, -2.0, 7.0), abs=1e-8)


def test_affine_transformation_preserves_the_analytic_cylinder_when_possible() -> None:
    """Gleichförmiger Maßstab, Spiegelung und Drehung brauchen keine NURBS-Konvertierung."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane

    result, mapping = edit.transformed_with_faces(
        edit.cylinder(6.0, 8.0),
        ((0.0, 2.0, 0.0, 7.0), (2.0, 0.0, 0.0, -3.0), (0.0, 0.0, 2.0, 5.0), (0.0, 0.0, 0.0, 1.0)),
    )
    kinds = [BRepAdaptor_Surface(face).GetType() for face in result.faces()]
    assert kinds.count(GeomAbs_Cylinder) == 1
    assert kinds.count(GeomAbs_Plane) == 2
    assert sorted(mapping) == [0, 1, 2]
    assert result.volume == pytest.approx(576.0 * math.pi, rel=1e-10)


def test_affine_transformation_keeps_two_separate_solids() -> None:
    """Ein affiner Schritt darf getrennte Körper weder vereinen noch einen verlieren."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    shape = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(shape)
    builder.Add(shape, edit.box(10.0, 8.0, 6.0).shape)
    builder.Add(shape, edit.moved(edit.box(4.0, 2.0, 3.0), (20.0, 0.0, 0.0)).shape)
    result, mapping = edit.transformed_with_faces(
        Solid(shape),
        ((2.0, 0.2, 0.0, 7.0), (0.0, 1.0, 0.0, -3.0), (0.0, 0.0, 0.5, 5.0), (0.0, 0.0, 0.0, 1.0)),
    )
    assert result.solid_count == 2 and result.is_closed
    assert result.volume == pytest.approx(504.0, rel=1e-10)
    assert sorted(mapping) == list(range(12))


def test_a_rigid_motion_proves_itself_without_a_volume_integral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verschieben und Drehen belegen sich über die Partnerschaft der Formen, nicht über Integrale.

    Zwei konvergierte Volumenintegrale je Bewegung kosteten an einem
    STEP-Gewinde 27 s (Review 21.09.2026); Maßstab und Scherung bauen die
    Flächen neu und behalten die Probe.
    """
    from app.core.geom.transform import rotation

    integrals: list[str] = []
    original = Solid._properties

    def counting(self: Solid, kind: str, *, cancelled: Any = None) -> Any:
        integrals.append(kind)
        return original(self, kind, cancelled=cancelled)

    monkeypatch.setattr(Solid, "_properties", counting)
    source = edit.box(10.0, 8.0, 6.0)
    moved = edit.moved(source, (7.0, -3.0, 5.0))
    turned = edit.transformed(source, rotation("z", 30.0))
    assert integrals == [], "eine starre Bewegung rechnet kein Volumen"
    assert moved.bounds.minimum == pytest.approx((2.0, -7.0, 5.0), abs=EPS_GEOM)
    assert turned.solid_count == 1 and turned.is_closed
    scaled = edit.transformed(
        source,
        ((2.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.5, 0.0), (0.0, 0.0, 0.0, 1.0)),
    )
    assert integrals.count("volume") == 2, "Maßstab belegt sich weiter über das Volumen"
    assert scaled.volume == pytest.approx(480.0, rel=1e-10)


def test_affine_translation_does_not_round_a_small_motion_away() -> None:
    """Eine Längentoleranz ist keine Identitätsprüfung einer Transformationsmatrix."""
    result = edit.moved(edit.box(10.0, 8.0, 6.0), (0.0, 0.0, 1e-7))
    assert result.bounds.minimum[2] == pytest.approx(1e-7, abs=1e-12)


@pytest.mark.parametrize(
    "failure_kind", ["not_done", "wrong_volume", "open_face", "missing_mapping"]
)
def test_an_unproven_native_transform_never_returns_a_new_solid(
    monkeypatch: pytest.MonkeyPatch, failure_kind: str
) -> None:
    """Gültige Eingaben reichen nicht: Builder-Abschluss, Körper und Zuordnung zählen."""
    # Das Modul, nicht das Paketattribut: ``edit`` holt den Builder über
    # ``from OCP.BRepBuilderAPI import``, also aus dem Stub-Modul; nur ein Patch
    # dort ist sichtbar und wird nach dem Test auch dort zurückgesetzt.
    import OCP.BRepBuilderAPI as BRepBuilderAPI

    source = edit.box(10.0, 8.0, 6.0)
    unrelated = edit.box(11.0, 8.0, 6.0)
    real_builder = BRepBuilderAPI.BRepBuilderAPI_Transform

    class IncompleteBuilder:
        """Ein echter Builder mit gezielt beschädigtem Ergebnisvertrag."""

        def __init__(self, *args):
            self.builder = real_builder(*args)

        def IsDone(self):  # noqa: N802
            return failure_kind != "not_done" and self.builder.IsDone()

        def Shape(self):  # noqa: N802
            if failure_kind == "wrong_volume":
                return unrelated.shape
            if failure_kind == "open_face":
                return unrelated.faces()[0]
            return self.builder.Shape()

        def ModifiedShape(self, shape):  # noqa: N802
            if failure_kind == "missing_mapping":
                return unrelated.faces()[0]
            return self.builder.ModifiedShape(shape)

    monkeypatch.setattr(BRepBuilderAPI, "BRepBuilderAPI_Transform", IncompleteBuilder)
    with pytest.raises(GeometryError) as failure:
        edit.moved(source, (7.0, -3.0, 5.0))
    assert failure.value.suggestions
    assert source.volume == pytest.approx(480.0, rel=1e-10)
    assert source.bounds.minimum == pytest.approx((-5.0, -4.0, 0.0), abs=EPS_GEOM)


# --- exactness ------------------------------------------------------------------


def test_the_body_answers_from_the_kernel_not_from_the_triangles() -> None:
    solid = block()

    assert solid.volume == pytest.approx(WIDTH * DEPTH * HEIGHT, rel=1e-9)
    assert solid.area == pytest.approx(2 * (40 * 30 + 40 * 20 + 30 * 20), rel=1e-9)
    assert (solid.face_count, solid.edge_count) == (6, 12)


def _nurbs(solid: Solid) -> Solid:
    """Derselbe Körper mit jeder Fläche und Kurve als NURBS — wie aus manchem STEP."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

    return Solid(BRepBuilderAPI_NurbsConvert(solid.shape, True).Shape())


def _open_box() -> Solid:
    """Ein Quader ohne Deckel: fünf Flächen, genäht, vier freie Kanten am Rand."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    sewing = BRepBuilderAPI_Sewing(EPS_GEOM)
    faces = TopExp_Explorer(block().shape, TopAbs_FACE)
    kept = 0
    while faces.More():
        if kept < 5:
            sewing.Add(faces.Current())
        kept += 1
        faces.Next()
    sewing.Perform()
    return Solid(sewing.SewedShape())


def test_an_open_shell_or_a_lone_face_is_not_closed() -> None:
    """``is_closed`` fragt nach freien Kanten — und fand bis zum 22.09.2026 nie eine.

    ``ShapeAnalysis_Shell.CheckOrientedShells`` zeichnet freie Kanten nur mit
    ``alsofree`` auf; ohne das Argument meldete ``HasFreeEdges`` immer nein,
    und ein Kasten ohne Deckel, sogar eine einzelne Fläche, galt als
    geschlossen. Jede Prüfung, die darauf baute — ``_built`` nach Verrunden
    und Fase, ``transformed``, der Gewindebolzen, die Vereinigung der
    Bausteine —, sah deshalb nur die Körperzahl.
    """
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    assert block().is_closed
    assert edit.cylinder(10.0, 5.0).is_closed
    assert edit.sphere(8.0).is_closed
    assert edit.cone(10.0, 0.0, 5.0).is_closed, "die Spitze ist eine entartete Kante, keine freie"
    assert not _open_box().is_closed
    lone = Solid(TopoDS.Face(TopExp_Explorer(block().shape, TopAbs_FACE).Current()))
    assert not lone.is_closed


def test_the_bounding_box_comes_from_the_shape_not_from_the_triangles() -> None:
    """Der Hüllquader eines exakten Körpers ist exakt (§30, Regel 6).

    Er kam aus der Tessellation und war damit konstant rund 0,025 mm zu klein —
    die halbe Abweichung, die das Anzeigenetz haben darf. Bei Ø 50 stand
    49,9755 mm, wo Fusion denselben Körper mit 25,00 mm Radius misst. Daran
    hängen die Maße im Baum, die Bauraumprüfung, das Anordnen, der Haftungsrand
    und jede Passungsprüfung: ein Zapfen Ø 6 verlor so ein Zehntel seines
    Spiels, bevor jemand gedruckt hatte.
    """
    solid = edit.cylinder(diameter=50.0, height=40.0)
    box = solid.bounds

    assert box.size[0] == pytest.approx(50.0, abs=EPS_GEOM)
    assert box.size[1] == pytest.approx(50.0, abs=EPS_GEOM)
    assert box.size[2] == pytest.approx(40.0, abs=EPS_GEOM)
    # Und die Tessellation bleibt, was sie ist: eine Annäherung, die es nicht
    # trifft. Stünde hier dieselbe Zahl, käme der Hüllquader weiter von dort.
    assert solid.to_mesh().bounds.size[0] < 50.0 - EPS_GEOM


def test_the_bounding_box_is_measured_once_per_body() -> None:
    """Der Hüllquader wird je Körper einmal gemessen, wie Volumen und Fläche.

    ``AddOptimal`` kostete an ``build_tray_v3.step`` 0,37 s je Frage, und das
    Fenster fragt bei jeder Auswertung für jedes Objekt — Kopfzeile,
    Objektbaum, Ansicht, Platzierung —, im Hauptthread (Review 22.09.2026).
    Dasselbe Objekt beim zweiten Mal heißt: nicht noch einmal gemessen. Eine
    private Kopie misst neu und kommt auf dieselben Zahlen.
    """
    from dataclasses import replace

    solid = edit.cylinder(diameter=50.0, height=40.0)
    first = solid.bounds
    assert solid.bounds is first
    copy = replace(solid)
    assert copy.bounds == first
    # Verschoben reist der Hüllquader mit — und ist derselbe, den der Körper
    # selbst mäße.
    moved = edit.moved(solid, (5.0, -3.0, 2.0))
    carried = moved._cache["bounds"]
    del moved._cache["bounds"]
    assert moved.bounds == carried
    assert carried.minimum == pytest.approx((-20.0, -28.0, 2.0), abs=EPS_GEOM)


def test_closedness_is_asked_once_per_body() -> None:
    """``is_closed`` geht über jede Kante — und wird je Körper einmal gerechnet.

    Gefragt wird nach jedem Verrunden, Bewegen, Schneiden und in der
    Erkennung, am Gewindebolzen M3 x 0,5 x 60 mehrmals je Schritt über 365
    Flächen (Review 22.09.2026). Die gemerkte Antwort ist dieselbe, auch für
    eine offene Schale.
    """
    solid = edit.cylinder(diameter=10.0, height=5.0)
    assert "closed" not in solid._cache
    assert solid.is_closed
    assert solid._cache["closed"] is True
    assert solid.is_closed
    shell = _open_box()
    assert not shell.is_closed
    assert shell._cache["closed"] is False
    assert not shell.is_closed

    """§40 für P12. Vier Stehende mit r gerundet: die Rechnung ist geschlossen."""
    radius = 3.0

    rounded = edit.fillet(block(), radius, "vertical")

    corner = radius**2 - math.pi * radius**2 / 4.0
    expected = WIDTH * DEPTH * HEIGHT - 4.0 * corner * HEIGHT
    assert rounded.volume == pytest.approx(expected, rel=1e-9)


def test_a_single_named_edge_is_the_only_one_that_changes() -> None:
    """RM-147 E4: Wer **eine** Kante brechen wollte, bekam vier.

    Die Auswahl kannte nur Gruppen — alle senkrechten, alle waagerechten, oben,
    unten, alle. Genannt wird eine Kante jetzt über ihren eigenen Schlüssel,
    und die Rechnung ist geschlossen: Was eine Kante wegnimmt, ist genau ein
    Viertel dessen, was die vier senkrechten wegnehmen.
    """
    radius = 3.0
    solid = block()
    upright = [entry for entry in edit.edges_of(solid) if entry.upright]
    assert len(upright) == 4, "ein Quader hat vier stehende Kanten — sonst prüft der Test nichts"

    one = edit.fillet(solid, radius, "named", [edit.edge_key(upright[0])])

    corner = radius**2 - math.pi * radius**2 / 4.0
    assert one.volume == pytest.approx(WIDTH * DEPTH * HEIGHT - corner * HEIGHT, rel=1e-9)


def test_an_edge_key_survives_a_second_run_and_names_only_its_own_edge() -> None:
    """Der Schlüssel muss eine zweite Auswertung überleben (§21, E4).

    Ein nativer Handle gehört dem Lauf, der ihn erzeugt hat, und ein Index in
    die Topologie verschiebt sich, sobald davor etwas anderes passiert. Beides
    in einer Projektdatei hieße, beim nächsten Öffnen eine andere Kante zu
    verrunden — still. Der Schlüssel kommt deshalb aus der Geometrie.
    """
    keys = [edit.edge_key(entry) for entry in edit.edges_of(block())]
    again = [edit.edge_key(entry) for entry in edit.edges_of(block())]

    assert len(set(keys)) == len(keys), "zwei Kanten teilen keinen Schlüssel"
    assert sorted(keys) == sorted(again), "derselbe Körper, dieselben Schlüssel"
    # Und er trifft wirklich seine eigene Kante: Was zurückkommt, liegt dort,
    # wo der Schlüssel es sagt.
    found = edit.named_edges(block(), [keys[3]])
    assert len(found) == 1
    assert edit.edge_key(found[0]) == keys[3]


def test_edge_points_follow_the_curve_and_not_the_chord() -> None:
    """Eine Kante anzuklicken heißt, sie dort zu treffen, wo sie liegt.

    Mitte und Richtung beschreiben eine Kante gut genug, um sie nach Lage
    auszuwählen — für einen Zeiger reichen sie nicht. Der Kreis am Zylinder
    ist der Beweis: Seine Mitte liegt auf der Achse, also **im Material**
    und nicht auf der Kante, und Anfang und Ende fallen zusammen. Wer die
    Kante über diese drei Zahlen suchte, zielte auf einen Punkt, an dem
    nichts ist.

    Die gerade Kante daneben bleibt zwei Punkte lang. Eine Strecke feiner
    abzutasten kostet nur Rechenzeit — die Abweichung ist dort null.
    """
    gerade = next(entry for entry in edit.edges_of(block()) if entry.upright)
    ecken = edit.edge_points(gerade)

    assert len(ecken) == 2, "eine Strecke braucht keine Zwischenpunkte"
    assert ecken[0][2] == pytest.approx(0.0) and ecken[1][2] == pytest.approx(HEIGHT)

    radius = 10.0
    kreis = edit.edges_of(edit.cylinder(2.0 * radius, HEIGHT))[0]
    bogen = edit.edge_points(kreis)

    assert len(bogen) > 8, "ein Kreis besteht nicht aus zwei Punkten"
    for punkt in bogen:
        assert math.hypot(punkt[0], punkt[1]) == pytest.approx(radius, abs=1e-6)
    # Und die Mitte, über die die Auswahl nach Lage geht, liegt eben nicht auf
    # ihm: Sie sitzt auf der Achse, zehn Millimeter von jedem Punkt entfernt.
    achse = math.hypot(kreis.middle[0], kreis.middle[1])
    assert achse == pytest.approx(0.0, abs=1e-6)


def test_a_named_edge_that_is_gone_says_so_instead_of_doing_nothing() -> None:
    """Eine Kante kann verschwinden, weil ein Schritt davor sie weggenommen hat.

    Das ist eine Auskunft an den Kunden und kein Programmfehler — und es ist
    ein **anderer** Satz als „zu dieser Auswahl gehört keine Kante": Dort gibt
    es die Sorte nicht, hier gab es sie und gibt es nicht mehr.
    """
    with pytest.raises(GeometryError) as weg:
        edit.fillet(block(), 2.0, "named", ["e:99.00,99.00,99.00:0.000,0.000,1.000"])
    assert "nicht mehr" in str(weg.value.detail)

    with pytest.raises(GeometryError) as leer:
        edit.fillet(block(), 2.0, "named", [])
    assert "keine Kante benannt" in str(leer.value.detail)


@pytest.mark.parametrize("failure", ["missing_rounding", "defeaturing", "missing_edge"])
def test_rounding_failures_offer_editing_instead_of_mesh_repair(
    failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein exakter Rundungsfehler führt zurück zur Eingabe, nicht zur Netzreparatur."""
    from unittest.mock import Mock

    import OCP.BRepAlgoAPI as brep_api  # noqa: N813 - Name der externen OCP-API

    source = block()
    centre = (WIDTH / 2.0, DEPTH / 2.0, HEIGHT / 2.0)
    if failure != "missing_rounding":
        source = edit.fillet(source, 3.0, "vertical")
    before = source.volume
    if failure == "defeaturing":
        builder = Mock()
        builder.IsDone.return_value = False
        monkeypatch.setattr(brep_api, "BRepAlgoAPI_Defeaturing", lambda: builder)
    elif failure == "missing_edge":
        # Kein Beleg aus der Builder-Historie: der Radiuswechsel sagt ab, statt die
        # nächste Kante an der alten Mitte zu nehmen.
        monkeypatch.setattr(edit, "_sharp_edge_after", lambda *_args, **_kwargs: None)

    with pytest.raises(GeometryError) as failed:
        if failure == "missing_edge":
            edit.reround(source, centre, 3.0, 2.0)
        else:
            edit.unround(source, centre, 3.0)

    offered = "change_selection" if failure == "missing_edge" else "correct_input"
    assert {action.id for action in failed.value.suggestions} == {offered, "cancel"}
    assert source.volume == pytest.approx(before, abs=EPS_GEOM)


def test_a_chamfer_takes_off_exactly_its_triangle() -> None:
    distance = 2.0

    broken = edit.chamfer(block(), distance, "vertical")

    expected = WIDTH * DEPTH * HEIGHT - 4.0 * (distance**2 / 2.0) * HEIGHT
    assert broken.volume == pytest.approx(expected, rel=1e-9)


def test_a_precise_boolean_needs_no_fallback_chain() -> None:
    """§30: zwei exakte Körper sind sich nicht uneinig, was innen ist."""
    drilled = edit.boolean(
        "difference", [block(), edit.moved(edit.cylinder(8.0, 40.0), (0.0, 0.0, -5.0))]
    )

    expected = WIDTH * DEPTH * HEIGHT - math.pi * 16.0 * HEIGHT
    assert drilled.volume == pytest.approx(expected, rel=1e-9)


def test_a_failed_difference_names_the_editing_not_a_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine Bohrung zieht ab; ihre Meldung darf nicht vom Verbinden sprechen."""
    import OCP.BRepAlgoAPI as brep_api  # noqa: N813 - Name der externen OCP-API

    class BrokenBoolean:
        """Kleinster Ersatz für einen Booleschen Builder ohne Ergebnis."""

        def __init__(self) -> None:
            pass

        def SetNonDestructive(self, _value: bool) -> None:  # noqa: N802
            pass

        def SetRunParallel(self, _value: bool) -> None:  # noqa: N802
            pass

        def SetArguments(self, _values: object) -> None:  # noqa: N802
            pass

        def SetTools(self, _values: object) -> None:  # noqa: N802
            pass

        def Build(self) -> None:  # noqa: N802 - bildet die externe OCP-API nach
            pass

        def IsDone(self) -> bool:  # noqa: N802 - bildet die externe OCP-API nach
            return False

    monkeypatch.setattr(brep_api, "BRepAlgoAPI_Cut", BrokenBoolean)
    part = block()

    with pytest.raises(GeometryError) as caught:
        edit.boolean("difference", [part, part])

    from app.core.errors import BOOLEAN_GEOMETRY_UNSAFE_DETAIL

    assert caught.value.detail == BOOLEAN_GEOMETRY_UNSAFE_DETAIL


def test_a_radius_that_does_not_fit_is_an_error_not_a_guess() -> None:
    with pytest.raises(GeometryError):
        edit.fillet(block(), 100.0, "vertical")


def test_a_selection_that_matches_nothing_says_so() -> None:
    with pytest.raises(GeometryError):
        edit.fillet(edit.cylinder(10.0, 20.0), 1.0, "vertical")


def test_both_kernels_ask_the_same_question_of_a_thin_walled_box(profile: Profile) -> None:
    """Derselbe Radius, dieselbe Frage — am Netz wie am exakten Körper.

    Der Prüfkörper misst 40 x 30 x 20 mm: 3 mm Boden, zwei 6 mm dicke
    Seitenwände, die übrigen Seiten sind offen. Die um (3, 3, 3) versetzte
    Aussparung liegt dort bündig, weil ``box`` in XY zentriert ist.
    Am 14.09.2026 nahm das Netz über **alle** Kanten einen Radius von
    2 mm an, der exakte Kern sagte ihn ab, und ein Vorbehalt im Register
    erklärte den Unterschied. Am 22.09.2026 gemessen, *wie* das Netz ihn
    annahm: Zwei Bänder zu je 2 mm auf einer 3 mm breiten Stirnfläche
    überlappen, und die Wand kam still niedriger heraus. Vom 23.09.2026 an
    stellten beide Kerne dieselbe Frage (``edges.contact_band_limit``) und
    sagten denselben Radius mit demselben größten Wert ab.

    **Seit dem 28.09.2026 lässt eine Gruppe die Kanten aus, die das Maß nicht
    tragen** (RM-279 (ii), Entscheidung der Release-Sitzung 0.5.1 nach
    Kundensicht, Robert gemeldet): Die Frage ist an beiden Kernen dieselbe
    (``edges.contact_band_limits``). Das Netz rundet hier 17 Kanten und nennt
    die vier ausgelassenen mit 1,5 mm; die Wand bleibt 20 mm hoch. Der exakte
    Kern fragt dasselbe. Weil OpenCASCADE die verbleibenden 17 Kanten nicht
    gemeinsam baut, probiert RM-284 einzelne Auslassungen auf frischer Form:
    Hier werden 16 Kanten verrundet und eine mit ihrem Ort genannt. Der direkte
    Aufruf der B-Rep-Hilfsfunktion bleibt streng und lehnt die ganze Gruppe ab.
    """
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN

    from app.core.geom.edges import round_edges
    from app.core.geom.mesh import MeshData

    aussen = edit.box(40.0, 30.0, 20.0)
    innen = edit.moved(edit.box(34.0, 24.0, 20.0), (3.0, 3.0, 3.0))
    kasten = edit.boolean("difference", [aussen, innen])

    with pytest.raises(GeometryError):
        edit.fillet(kasten, 2.0, "all")

    exakt = SceneObject(id="obj_1", name="Kasten", mesh=kasten, kind="brep")
    exact_result = run("fillet_edges", exakt, profile, radius=2.0, edges="all")
    exact_body = exact_result.outputs[0].mesh
    assert isinstance(exact_body, Solid)
    assert exact_body.solid_count == 1
    assert exact_body.is_closed
    assert kasten.volume == pytest.approx(40.0 * 30.0 * 20.0 - 34.0 * 24.0 * 17.0, abs=EPS_GEOM)
    assert exact_body.bounds.size == pytest.approx((40.0, 30.0, 20.0), abs=EPS_GEOM)
    fillets = [feature for feature in features_of(exact_body).values() if feature.kind == "fillet"]
    assert fillets
    assert all(
        float(feature.params["radius"]) == pytest.approx(2.0, abs=EPS_GEOM) for feature in fillets
    )
    # Unabhängige Materialproben: Wandmitten bleiben, der Hohlraum bleibt
    # frei. Bei z=10 liegt der R2-Kreis außen um (-18, -13), innen um
    # (-12, -7); Quadratpunkte auf beiden Seiten des Kreisbogens prüfen
    # Abtrag und Füllung. Alle Proben liegen deutlich neben der Oberfläche.
    for point, before, after in (
        ((-17.0, 0.0, 10.0), True, True),
        ((0.0, -12.0, 10.0), True, True),
        ((0.0, 0.0, 1.5), True, True),
        ((0.0, 0.0, 10.0), False, False),
        ((-19.9, -14.9, 10.0), True, False),
        ((-19.0, -14.0, 10.0), True, True),
        ((-13.9, -8.9, 10.0), False, True),
        ((-13.0, -8.0, 10.0), False, False),
    ):
        for body, expected in ((kasten, before), (exact_body, after)):
            actual = BRepClass3d_SolidClassifier(body.shape, gp_Pnt(*point), EPS_GEOM)
            assert (actual.State() == TopAbs_IN) is expected, point
    exact_skipped = next(
        finding for finding in exact_result.findings if finding.code == "edges.exact_group_skipped"
    )
    assert exact_skipped.values["skipped"] == 1
    assert exact_skipped.values["worked"] == 16
    assert exact_skipped.location is not None
    too_narrow = next(
        finding for finding in exact_result.findings if finding.code == "edges.too_narrow"
    )
    assert (too_narrow.values["skipped"], too_narrow.values["worked"]) == (4, 16)

    netz = MeshData.of(tessellate(kasten.shape, 0.05).raw)
    teils = round_edges(netz, 2.0, "all", quality="draft")
    ausgelassen = next(f for f in teils.findings if f.code == "edges.too_narrow")
    assert ausgelassen.values["largest_mm"] == pytest.approx(1.5, abs=0.01)
    assert (ausgelassen.values["skipped"], ausgelassen.values["worked"]) == (4, 17)
    assert ausgelassen.suggestions, "der Befund nennt einen Ausweg"
    assert teils.mesh.is_watertight
    assert teils.mesh.bounds.size[2] == pytest.approx(20.0, abs=1e-6)

    gerundet = round_edges(netz, 1.4, "all", quality="draft")
    assert gerundet.mesh.is_watertight, "unter der Grenze rundet das Netz"
    assert gerundet.mesh.bounds.size[2] == pytest.approx(20.0, abs=1e-6), (
        "und die Wand bleibt so hoch, wie sie war"
    )

    grenze = str(REGISTRY.get("fillet_edges").caveat)
    assert "3 mm" not in grenze, f"der Vorbehalt über zwei Antworten ist gefallen: {grenze}"


def test_a_fillet_group_builds_each_candidate_on_its_own_native_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein abgewiesener Builder darf die native Form des nächsten Versuchs nicht berühren."""
    solid = _coloured_block()
    entries = edit.choose(solid, "vertical")
    selected_edges = solid.checked_edge_indices(edit.native_edge_indices(solid, entries))
    points = tuple(entry.middle for entry in edit._edges_at(solid, selected_edges))
    before = solid.mesh.to_bytes()
    attempts: list[Solid] = []
    original_build = edit._build_constant_fillet

    def build_candidate(
        working: Solid, chosen: list[edit.EdgeInfo], radius: float, **kwargs: Any
    ) -> Solid:
        assert not working.shape.IsPartner(solid.shape), "der Eingang bleibt privat"
        assert not any(working.shape.IsPartner(previous.shape) for previous in attempts), (
            "jeder neue Kandidat braucht eine eigene native Form"
        )
        assert len(edit.native_edge_indices(working, chosen)) == len(chosen)
        attempts.append(working)
        if len(attempts) == 1:
            raise GeometryError("Erste Kombination absichtlich abgewiesen.")
        return original_build(working, chosen, radius, **kwargs)

    monkeypatch.setattr(edit, "_build_constant_fillet", build_candidate)

    result, skipped = edit.fillet_group(solid, 1.0, selected_edges)

    assert len(attempts) == 2
    assert skipped == (points[0],)
    assert result.is_closed and result.is_watertight and result.solid_count == 1
    # Drei senkrechte Kanten verlieren je Quadrat minus Viertelkreis, über 20 mm.
    assert result.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - 3.0 * (1.0 - math.pi / 4.0) * HEIGHT,
        abs=EPS_GEOM,
        rel=0.0,
    )
    assert {2, 3}.issubset(result.face_slots)
    assert solid.mesh.to_bytes() == before


def test_a_fillet_group_omits_each_individually_open_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine Gruppe mit zwei offenen Einzelkanten bleibt nach ihrem Ausschluss geschlossen."""
    solid = block()
    entries = edit.choose(solid, "vertical")
    selected_edges = edit.native_edge_indices(solid, entries)
    points = tuple(entry.middle for entry in entries)
    open_points = set(points[-2:])
    attempts: list[tuple[tuple[float, float, float], ...]] = []

    class Candidate:
        def __init__(self, is_watertight: bool) -> None:
            self.is_watertight = is_watertight

    def build_candidate(
        _solid: Solid, chosen: list[edit.EdgeInfo], _radius: float, **_kwargs: Any
    ) -> Any:
        candidate_points = tuple(entry.middle for entry in chosen)
        attempts.append(candidate_points)
        if len(candidate_points) == 1:
            return Candidate(candidate_points[0] not in open_points)
        return Candidate(set(candidate_points) == set(points[:-2]))

    monkeypatch.setattr(edit, "_fits_the_wall", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(edit, "_build_constant_fillet", build_candidate)

    result, skipped = edit.fillet_group(solid, 1.0, selected_edges)

    assert result.is_watertight
    assert skipped == points[-2:]
    assert attempts[0] == points
    assert attempts[-1] == points[:-2]
    assert len(attempts) == 1 + len(entries) + 1


def test_a_failed_single_edge_exclusion_is_not_built_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine fehlgeschlagene Auslassung bleibt im Einzelauslassungslauf übersprungen."""
    solid = block()
    entries = edit.choose(solid, "vertical")
    selected_edges = edit.native_edge_indices(solid, entries)
    points = tuple(entry.middle for entry in entries)
    open_point = points[-1]
    attempts: list[tuple[tuple[float, float, float], ...]] = []

    class Candidate:
        def __init__(self, is_watertight: bool) -> None:
            self.is_watertight = is_watertight

    def build_candidate(
        _solid: Solid, chosen: list[edit.EdgeInfo], _radius: float, **_kwargs: Any
    ) -> Candidate:
        candidate_points = tuple(entry.middle for entry in chosen)
        attempts.append(candidate_points)
        if len(candidate_points) == 1:
            return Candidate(candidate_points[0] != open_point)
        return Candidate(False)

    monkeypatch.setattr(edit, "_fits_the_wall", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(edit, "_build_constant_fillet", build_candidate)

    with pytest.raises(GeometryError):
        edit.fillet_group(solid, 1.0, selected_edges)

    assert attempts[0] == points
    assert attempts.count(points[:-1]) == 1
    assert len(attempts) == 1 + 2 * len(entries)


def test_a_single_edge_probe_is_reused_by_the_group_exclusion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die offene Einzelkante schließt die Gruppe ohne erneuten nativen Bau aus."""
    solid = block()
    entries = edit.choose(solid, "vertical")[:2]
    selected_edges = solid.checked_edge_indices(edit.native_edge_indices(solid, entries))
    points = tuple(entry.middle for entry in edit._edges_at(solid, selected_edges))
    open_point = points[-1]
    attempts: list[tuple[tuple[float, float, float], ...]] = []

    class Candidate:
        def __init__(self, is_watertight: bool) -> None:
            self.is_watertight = is_watertight

    def build_candidate(
        _solid: Solid, chosen: list[edit.EdgeInfo], _radius: float, **_kwargs: Any
    ) -> Candidate:
        candidate_points = tuple(entry.middle for entry in chosen)
        attempts.append(candidate_points)
        if len(candidate_points) == 1:
            return Candidate(candidate_points[0] != open_point)
        return Candidate(False)

    monkeypatch.setattr(edit, "_fits_the_wall", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(edit, "_build_constant_fillet", build_candidate)

    result, skipped = edit.fillet_group(solid, 1.0, selected_edges)

    assert result.is_watertight
    assert skipped == (open_point,)
    assert attempts == [points, (points[0],), (points[1],)]


def test_a_fillet_group_omits_two_edges_that_the_kernel_cannot_build(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei echte B-Rep-Kandidaten können aus einer getrennten Gruppe entfallen."""
    from dataclasses import replace

    from OCP.BRep import BRep_Builder
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.TopoDS import TopoDS_Compound

    from app.core.geom import edge_ops
    from app.core.registry import Registry
    from app.core.scene import ResultCache
    from app.core.types import Finding, OpResult

    def cylinder(radius: float, height: float, x: float, y: float, z: float) -> Solid:
        axis = gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0.0, 0.0, 1.0), gp_Dir(0.0, 1.0, 0.0))
        return Solid(BRepPrimAPI_MakeCylinder(axis, radius, height).Shape())

    parts = []
    expected_bad = []
    expected_good = []
    for offset in (0.0, 40.0):
        large = cylinder(5.0, 10.0, offset, 0.0, 0.0)
        small = cylinder(2.5, 30.0, offset - 5.24187234, -3.84353671, -20.0)
        parts.append(edit.boolean("union", [large, small]))
        expected_good.append((offset - 2.762923404947445, -4.167283798638342, 5.0))
        expected_bad.append((offset - 4.805223638300356, -1.3819644662289552, 5.0))

    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for part in parts:
        builder.Add(compound, part.shape)
    solid = Solid(compound)
    candidates = edit.choose(solid, "vertical")
    points = (*expected_good, *expected_bad)
    chosen = tuple(
        min(candidates, key=lambda entry: math.dist(entry.middle, point)) for point in points
    )
    assert all(
        math.dist(entry.middle, point) < 1e-5 for entry, point in zip(chosen, points, strict=True)
    )
    chosen_indices = edit.native_edge_indices(solid, chosen)
    individually_rounded_volumes = tuple(
        edit.fillet(solid, 1.0, "vertical", selected_edges=(index,)).volume
        for index in chosen_indices[: len(expected_good)]
    )
    assert all(
        not math.isclose(volume, solid.volume, rel_tol=0.0, abs_tol=1e-5)
        for volume in individually_rounded_volumes
    )
    expected_volume = solid.volume - sum(
        solid.volume - volume for volume in individually_rounded_volumes
    )

    result, skipped = edit.fillet_group(solid, 1.0, chosen_indices)

    assert result.is_closed and result.is_watertight
    assert result.component_count == 2
    assert result.volume == pytest.approx(expected_volume, abs=1e-5)
    assert len(skipped) == 2
    assert all(
        any(math.dist(actual, expected) < 1e-5 for actual in skipped) for expected in expected_bad
    )
    assert all(
        not any(math.dist(actual, expected) < 1e-5 for actual in skipped)
        for expected in expected_good
    )

    # Der Anschluss beginnt an dieser belegten nativen Auswahl. Nur die
    # vorgelagerte Netzzug-Zuordnung ist festgelegt; Gruppenbau, Befundfabrik
    # und Auswertung bleiben echt, einschließlich der Wiederholung aus dem Cache.
    monkeypatch.setattr(
        edge_ops, "_group_that_fits", lambda *_args, **_kwargs: (chosen_indices, [])
    )
    own = Registry()
    own.register(
        replace(
            REGISTRY.get("create_brep_box"),
            name="rounding_source",
            fn=lambda _ctx: OpResult(
                outputs=[SceneObject(id="", name="Rundungsprobe", mesh=solid, kind="brep")]
            ),
        )
    )
    fillet = REGISTRY.get("fillet_edges")
    raw_results: list[OpResult] = []
    raw_findings_before: list[tuple[Finding, ...]] = []

    def recorded_fillet(ctx: OpContext) -> OpResult:
        output = fillet.fn(ctx)
        raw_results.append(output)
        raw_findings_before.append(
            tuple(replace(entry, values=dict(entry.values)) for entry in output.findings)
        )
        return output

    own.register(replace(fillet, fn=recorded_fillet))
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document, registry=own)
    history.apply("Prüfkörper", [OperationDraft(op="rounding_source")])
    target = project.document.ops[-1].outputs[0]
    history.apply(
        "Rundungsgruppe",
        [
            OperationDraft(
                op="fillet_edges", inputs=(target,), params={"radius": 1.0, "edges": "vertical"}
            )
        ],
    )
    cache = ResultCache()
    for _pass in range(2):
        evaluated = evaluate(
            project.document,
            profile,
            registry=own,
            cache=cache,
            ask=lambda question, choices: pytest.fail(f"Unerwartete Frage: {question}"),
        )
        assert evaluated.complete
        assert len(raw_results) == 1, "der warme Lauf verwendet den rohen Operationscache"
        assert tuple(raw_results[0].findings) == raw_findings_before[0]
        raw_findings = [
            entry for entry in raw_results[0].findings if entry.code == "edges.exact_group_skipped"
        ]
        reported = [
            entry
            for entry in evaluated.scene.report.findings
            if entry.code == "edges.exact_group_skipped"
        ]
        assert len(raw_findings) == 2
        assert all(entry.op_id is None for entry in raw_findings), (
            "die Auswertung ändert keine Rohbefunde"
        )
        assert len(reported) == 2, "jede ausgelassene Kante behält ihre eigene Stelle"
        for expected in expected_bad:
            assert any(
                entry.location is not None
                and entry.location == pytest.approx(expected, abs=1e-5, rel=0.0)
                for entry in reported
            )
        assert all(entry.op_id == project.document.ops[-1].id for entry in reported)
        assert all(entry.object_id == target for entry in reported)
        assert all(
            entry.values["worked"] == 2 and entry.values["skipped"] == 1 for entry in reported
        )


def test_a_failed_combined_fillet_exclusion_is_not_built_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine erfolglose gemeinsame Auslassung wird nicht nochmals aufgebaut."""
    solid = block()
    entries = edit.choose(solid, "vertical")
    selected_edges = edit.native_edge_indices(solid, entries)
    points = tuple(entry.middle for entry in entries)
    open_points = set(points[-2:])
    attempts: list[tuple[tuple[float, float, float], ...]] = []

    class Candidate:
        is_watertight = False

    def build_candidate(
        _solid: Solid, chosen: list[edit.EdgeInfo], _radius: float, **_kwargs: Any
    ) -> Candidate:
        candidate_points = tuple(entry.middle for entry in chosen)
        attempts.append(candidate_points)
        if len(candidate_points) == 1:
            candidate = Candidate()
            candidate.is_watertight = candidate_points[0] not in open_points
            return candidate
        return Candidate()

    monkeypatch.setattr(edit, "_fits_the_wall", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(edit, "_build_constant_fillet", build_candidate)

    with pytest.raises(GeometryError):
        edit.fillet_group(solid, 1.0, selected_edges)

    assert attempts[0] == points
    assert attempts.count(points[:-2]) == 1
    assert len(attempts) == 1 + len(entries) + 1 + len(entries)


# --- which edges ----------------------------------------------------------------


def test_the_named_selections_pick_what_they_say() -> None:
    solid = block()

    assert len(edit.choose(solid, "all")) == 12
    assert len(edit.choose(solid, "vertical")) == 4, "the four uprights"
    assert len(edit.choose(solid, "horizontal")) == 8
    assert len(edit.choose(solid, "top")) == 4
    assert all(entry.middle[2] == pytest.approx(HEIGHT) for entry in edit.choose(solid, "top"))
    assert all(entry.middle[2] == pytest.approx(0.0) for entry in edit.choose(solid, "bottom"))


# --- Der Weg zum Netz -----------------------------------------------------------


def test_the_tessellation_is_closed_and_keeps_the_volume() -> None:
    mesh = edit.fillet(block(), 3.0, "vertical").to_mesh()

    assert isinstance(mesh, MeshData)
    assert mesh.is_watertight
    assert mesh.volume > 0.0, "not inside out"


def test_two_touching_bodies_of_a_compound_share_no_corner() -> None:
    """Ein Verbund aus zwei Körpern wird zwei geschlossene Netze, auch wo sie sich berühren.

    Durchsicht 0.5.1 (Prüfer rest-schraube): Die Senkkopfschraube liegt am
    exakten Kern als Verbund in ihrer Senkung, und Kopf und Senkung haben
    denselben oberen Rand. Die Tessellierung verschweißte die 42 Ecken dieses
    Rands über beide Körper hinweg — das Netz des Szenenobjekts war danach
    nicht mehr dicht, fünf Teile statt drei, und der Assistent las nach jeder
    Schraube „Dieses Objekt ist nicht mehr geschlossen“. Hier dasselbe an zwei
    Würfeln, die sich in einer ganzen Fläche berühren.
    """
    from app.core.knowledge.parts.exact import compound

    left = edit.box(10.0, 10.0, 10.0)
    right = edit.transformed(
        edit.box(10.0, 10.0, 10.0),
        ((1.0, 0.0, 0.0, 10.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    )
    pair = compound(left, right)

    mesh = as_mesh_data(pair)
    assert pair.solid_count == 2
    assert mesh.component_count == 2
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(2000.0)
    # Ein einzelner Körper verschweißt weiter wie bisher: dieselben Ecken.
    alone = as_mesh_data(left)
    assert alone.is_watertight and len(alone.raw.vertices) == 8


def test_a_finer_setting_gives_more_triangles_and_less_error() -> None:
    solid = edit.fillet(block(), 3.0, "vertical")

    coarse = tessellate(solid.shape, 0.5)
    fine = tessellate(solid.shape, 0.01)

    assert fine.triangle_count > coarse.triangle_count
    assert abs(fine.volume - solid.volume) < abs(coarse.volume - solid.volume)


def test_a_mesh_operation_gets_the_tessellation(profile: Profile) -> None:
    """§30: der Weg zum Netz steht jederzeit offen."""
    solid = block()

    converted = as_mesh_data(solid)

    assert isinstance(converted, MeshData)
    assert converted.triangle_count == 12


def test_the_marking_follows_the_body_not_the_claim() -> None:
    assert kind_of(block()) == "brep"
    assert kind_of(MeshData.of(trimesh.creation.box(extents=(1.0, 1.0, 1.0)))) == "mesh"


def test_a_solid_satisfies_the_mesh_protocol() -> None:
    """Genau das lässt Viewport und Prüfbericht unverändert mit ihm
    arbeiten (§9).
    """
    assert isinstance(block(), Mesh)


# --- STEP -----------------------------------------------------------------------


def test_step_makes_the_round_trip() -> None:
    """§40 für P12: zurück als derselbe Körper, nicht als dasselbe Bild."""
    solid = edit.fillet(block(), 3.0, "vertical")

    again = step.read(step.write(solid))

    assert again.volume == pytest.approx(solid.volume, rel=1e-9)
    assert again.face_count == solid.face_count
    assert again.edge_count == solid.edge_count


def test_the_object_name_travels_into_the_step_file() -> None:
    """Sonst heißt das Teil in Fusion „Körper1" (§29).

    Der Übersetzer schreibt ohne Zutun seinen eigenen Namen in das PRODUCT —
    „Open CASCADE STEP translator 7.9 1" —, und das ist der Name, den ein
    fremdes Programm anzeigt. Der Objektname steht im Dokument die ganze Zeit
    da; er ging nur auf dem Weg verloren. Beim 3MF war das schon einmal ein
    Fund, dort kam eine Baugruppe als „Object 1, Object 2" an.
    """
    payload = step.write(block(), "Halteklotz").decode("utf-8", errors="replace")

    assert "Halteklotz" in payload
    assert "Open CASCADE STEP translator" not in payload.split("DATA;")[1].split("ENDSEC;")[0]


def test_a_step_export_carries_the_name_from_the_scene(profile: Profile, tmp_path: Path) -> None:
    """Und zwar über den ganzen Weg, nicht nur in der einen Funktion."""
    entry = SceneObject(id="obj_1", name="Lagerbock", mesh=block(), kind="brep")

    plan = plan_export([entry], project_name="Teil", profile=profile, export_format="step")
    written = write_plan(plan, tmp_path, "step")

    assert "Lagerbock" in written[0].read_text(encoding="utf-8", errors="replace")


def test_a_broken_step_file_is_a_user_error() -> None:
    with pytest.raises(ValidationError):
        step.read(b"this is not a STEP file")


def test_step_knows_its_own_suffixes() -> None:
    assert step.is_step(".STEP") and step.is_step(".stp")
    assert not step.is_step(".stl")


# --- Features aus der Topologie -------------------------------------------------


def test_a_bore_is_read_off_the_topology_rather_than_fitted() -> None:
    """§30: kein Gruppieren, keine Zylindereinpassung — eine zylindrische
    Fläche nennt ihren Radius.
    """
    drilled = edit.boolean(
        "difference", [block(), edit.moved(edit.cylinder(8.0, 40.0), (0.0, 0.0, -5.0))]
    )

    found = features_of(drilled)

    holes = {name: entry for name, entry in found.items() if entry.kind == "hole"}
    assert len(holes) == 1
    assert holes["hole_1"].params["diameter"] == pytest.approx(8.0)
    assert holes["hole_1"].params["axis"][2] == pytest.approx(1.0)


def test_a_brep_feature_names_all_its_viewport_triangles() -> None:
    """Eine exakte Fläche ist nicht dasselbe wie ein Dreieck des Anzeigenetzes.

    Die Bohrungswand ist im B-Rep genau **eine** Fläche. Im Viewport besteht
    sie aus vielen Dreiecken. ``features_of`` schrieb früher die Nummer der
    B-Rep-Fläche als ``face_indices`` hinein; der Viewport las sie als
    Dreiecksnummer und färbte dadurch einen einzelnen Keil der Außenwand.
    """
    import numpy as np

    diameter = 5.2
    drilled = edit.boolean(
        "difference",
        [edit.cylinder(9.0, 13.0), edit.moved(edit.cylinder(diameter, 20.0), (0.0, 0.0, -3.0))],
    )

    hole = next(entry for entry in features_of(drilled).values() if entry.kind == "hole")
    assert len(hole.face_indices) > 12, "ein runder Mantel braucht viele Anzeigedreiecke"

    triangles = np.asarray(drilled.raw.triangles)[list(hole.face_indices)]
    radii = np.linalg.norm(triangles[:, :, :2], axis=2)
    assert radii == pytest.approx(diameter / 2.0, abs=drilled.deflection), (
        "jede markierte Ecke liegt auf der Bohrungswand, keine auf der Außenwand"
    )


def test_brep_features_partition_the_whole_simple_body() -> None:
    """Beim einfachen Rohr bleibt kein Dreieck fremd und keines doppelt."""
    drilled = edit.boolean(
        "difference",
        [edit.cylinder(9.0, 13.0), edit.moved(edit.cylinder(5.2, 20.0), (0.0, 0.0, -3.0))],
    )
    groups = [set(feature.face_indices) for feature in features_of(drilled).values()]

    assert set().union(*groups) == set(range(drilled.triangle_count))
    assert sum(len(group) for group in groups) == drilled.triangle_count, (
        "jedes Dreieck gehört genau einer exakten Fläche"
    )


def test_a_rounded_corner_is_not_reported_as_a_hole() -> None:
    """Eine Verrundung ist auch ein Zylinder — sie eine Bohrung zu nennen
    setzte eine Schraube in eine Wand.
    """
    rounded = edit.fillet(block(), 3.0, "vertical")

    found = features_of(rounded)

    assert not [entry for entry in found.values() if entry.kind == "hole"]
    # **Und sie ist auch nicht nichts.** Solange der Ausschnitt verworfen wurde,
    # war die Zusicherung oben grün, weil überhaupt kein Merkmal entstand — sie
    # hätte nicht gemerkt, dass die vier Kanten spurlos verschwinden.
    fillets = [entry for entry in found.values() if entry.kind == "fillet"]
    assert len(fillets) == 4, f"vier senkrechte Kanten: {sorted(found)}"
    # Kein Einpassen: der Radius steht exakt in der Topologie.
    assert {entry.params["radius"] for entry in fillets} == {3.0}
    assert not any(entry.params["recess"] for entry in fillets), "Außenkanten, keine Kehlen"


def test_a_hollow_corner_is_a_throat_and_an_outer_one_is_not() -> None:
    """Beide sind Zylinderausschnitte mit demselben Radius; unterscheiden lässt
    sie nur, auf welcher Seite das Material liegt.

    Nicht über die Flächenorientierung — die kam an den vier gleichen Kanten
    eines Quaders zweimal so und zweimal anders heraus.
    """
    profile = edit.boolean("union", [edit.box(40.0, 10.0, 10.0), edit.box(10.0, 10.0, 40.0)])

    fillets = [
        entry
        for entry in features_of(edit.fillet(profile, 3.0, "all")).values()
        # **Nur die Kanten.** Die Ecken, an denen drei zusammenlaufen, sind
        # Kugelstücke und heißen seit derselben Erweiterung auch ``fillet``;
        # ihre Zahl hängt an der Gestalt und nicht an der Frage dieses Tests.
        if entry.kind == "fillet" and entry.params["length"] > 0.0
    ]

    throats = [entry for entry in fillets if entry.params["recess"]]
    assert len(throats) == 2, f"das T hat zwei einspringende Ecken: {len(fillets)} Ausschnitte"
    # Der Umriss hat acht Ecken, also acht Kanten längs y und je acht auf den
    # beiden Stirnflächen: 24 Kanten, davon zwei Kehlen. Bis zur
    # Nahtzusammenführung (P1.5) zählte der Kern 26: Die Vereinigung schnitt
    # die Bodenfläche in drei Stücke, und die Verrundung ihrer beiden langen
    # Kanten kam als je drei kollineare Viertelmäntel — ein Mantel von 34 mm.
    assert len(fillets) - len(throats) == 22
    long_ones = [entry for entry in fillets if entry.params["length"] == pytest.approx(34.0)]
    assert len(long_ones) == 2, sorted(entry.params["length"] for entry in fillets)
    assert not any(entry.params.get("radial") for entry in long_ones)


def test_the_planar_faces_come_with_their_area() -> None:
    found = features_of(block())

    areas = sorted(entry.params["area"] for entry in found.values() if entry.kind == "face")
    assert areas == [600.0, 600.0, 800.0, 800.0, 1200.0, 1200.0]


# --- as operations --------------------------------------------------------------


def run(op: str, entry: SceneObject | None, profile: Profile, **params: object):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry} if entry else {}),
            inputs=[entry] if entry else [],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_the_primitives_come_out_marked_as_brep(profile: Profile) -> None:
    result = run("create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0)

    assert result.outputs[0].kind == "brep"
    assert result.outputs[0].mesh.volume == pytest.approx(24000.0, rel=1e-9)


def test_create_brep_cylinder_stands_on_the_bed(profile: Profile) -> None:
    result = run("create_brep_cylinder", None, profile, diameter=20.0, height=15.0)

    assert result.outputs[0].mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6)


def test_fillet_edges_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Block", mesh=block(), kind="brep")

    result = run("fillet_edges", entry, profile, radius=3.0, edges="vertical")

    corner = 9.0 - math.pi * 9.0 / 4.0
    assert result.outputs[0].mesh.volume == pytest.approx(24000.0 - 4 * corner * 20.0, rel=1e-9)
    assert result.outputs[0].kind == "brep"


def test_a_group_choice_ignores_an_older_single_pick(profile: Profile) -> None:
    """Der Umschalter entscheidet, nicht ein Wert, der noch dasteht (E4).

    Der Dialog graut die Kantenliste aus, wenn eine Gruppe gewählt ist — er
    **löscht** sie aber nicht, und das ist richtig: eine Zeile, die
    verschwindet, sucht man (§2.6). Damit blieb der Wert im Schritt stehen und
    gewann über den Umschalter: Wer eine Kante ankreuzte, danach auf
    *senkrechte* zurückging und anwendete, bekam weiter seine eine. Der Dialog
    sagte das eine, gerechnet wurde das andere — und beides sah richtig aus.
    """
    entry = SceneObject(id="obj_1", name="Block", mesh=block(), kind="brep")
    eine = edit.edge_key(next(info for info in edit.edges_of(block()) if info.upright))
    corner = 9.0 - math.pi * 9.0 / 4.0

    gruppe = run("fillet_edges", entry, profile, radius=3.0, edges="vertical", edge_keys=eine)
    einzeln = run("fillet_edges", entry, profile, radius=3.0, edges="named", edge_keys=eine)

    assert gruppe.outputs[0].mesh.volume == pytest.approx(24000.0 - 4 * corner * 20.0, rel=1e-9), (
        "die Gruppe nimmt alle vier — der stehengebliebene Wert zählt nicht"
    )
    assert einzeln.outputs[0].mesh.volume == pytest.approx(24000.0 - corner * 20.0, rel=1e-9)


def test_chamfer_edges_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Block", mesh=block(), kind="brep")

    result = run("chamfer_edges", entry, profile, distance=2.0, edges="vertical")

    assert result.outputs[0].mesh.volume == pytest.approx(24000.0 - 4 * 2.0 * 20.0, rel=1e-9)


def test_a_mesh_body_is_turned_away_with_a_sentence(profile: Profile) -> None:
    """§33.1: der Titel nennt die Art des Fehlers, das Detail seinen Grund.

    Vorher war das eine ValidationError, und die heißt „Ein Wert liegt
    außerhalb des zulässigen Bereichs" — für einen Radius, der einwandfrei war.
    Der erklärende Satz stand im Detail und erreichte den Prüfbericht nicht;
    wer danach suchte, suchte bei den Zahlen.

    **Gefragt wird die Umwandlung — die dritte Umstellung dieser Art an einem
    Tag.** Erst stand hier ``sketch_pocket``, bis die Tasche am 30.08.2026 auch
    in Netze schneiden lernte; dann ``fillet_edges``, dann ``draft_faces``, bis
    beide am 10.09.2026 dasselbe lernten.

    ``brep_to_mesh`` ist die einzige der drei verbliebenen, die es nie anders
    geben kann: „ein exakter Körper wird ein Netz" braucht einen exakten
    Körper, und daran ändert kein Ausbau des Mesh-Kerns etwas. Die zwei
    anderen (``drill_brep_hole``, ``shell_exact``) sind versteckte Zwillinge
    ohne eigenen Menüeintrag. Die Zusage über den **Satz** gilt unverändert —
    sie hängt an ``brep_input`` und nicht an einer bestimmten Operation.
    """
    entry = SceneObject(
        id="obj_1", name="Netz", mesh=MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    )

    with pytest.raises(NeedsSolidError) as problem:
        run("brep_to_mesh", entry, profile, deflection=0.05)

    error = problem.value
    assert "bearbeitbare Flächen und Kanten" in str(error.title)
    assert error.detail is not None and "festen Dreiecken" in str(error.detail)
    assert error.object_id == "obj_1", "der Fehler nennt den Körper, den er meint"
    assert error.suggestions, "Regel 17: nie ohne Handlungsvorschlag"


def test_a_bead_reports_the_loss_of_exact_faces(profile: Profile) -> None:
    """Die zusätzliche Leiste lässt einen exakten Körper sichtbar zum Netz werden."""
    original = block()
    entry = SceneObject(
        id="obj_1", name="Klotz", mesh=original, kind="brep", features=features_of(original)
    )

    result = run("bead_edges", entry, profile, radius=1.5)

    assert result.outputs[0].kind == "mesh"
    assert result.outputs[0].mesh.is_watertight
    assert result.outputs[0].mesh.volume > original.volume
    notices = [finding for finding in result.findings if finding.code == "brep.converted"]
    assert len(notices) == 1
    assert notices[0].object_id == entry.id
    assert notices[0].values["triangles"] == result.outputs[0].mesh.triangle_count
    assert entry.kind == "brep" and entry.mesh is original


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_tiny_bead_names_the_bead_in_its_warning(kind: str, profile: Profile) -> None:
    """Der Hinweis muss die ausgeführte Handlung benennen."""
    body = block()
    source = SceneObject(
        id="obj_1", name="Klotz", kind=kind, mesh=body if kind == "brep" else as_mesh_data(body)
    )

    result = run("bead_edges", source, profile, radius=0.01)

    warnings = [finding for finding in result.findings if finding.code == "edges.without_effect"]
    assert len(warnings) == 1
    assert "Wulst" in str(warnings[0].message)
    assert "Verrundung" not in str(warnings[0].message)


@pytest.mark.parametrize("operation", ["fillet_edges", "chamfer_edges"])
@pytest.mark.parametrize("size, tiny", [(0.01, True), (1.5, False)])
def test_exact_edge_operations_report_changes_below_print_resolution(
    operation: str, size: float, tiny: bool, profile: Profile
) -> None:
    """Die Druckgrenze stammt aus dem Profil und gilt auch für exakte Flächen."""
    source = SceneObject(id="obj_1", name="Klotz", kind="brep", mesh=block())
    params = {"radius" if operation == "fillet_edges" else "distance": size}

    result = run(operation, source, profile, **params)

    assert result.outputs[0].kind == "brep"
    assert result.outputs[0].mesh.is_closed
    assert result.outputs[0].mesh.volume < source.mesh.volume
    warnings = [finding for finding in result.findings if finding.code == "edges.without_effect"]
    assert len(warnings) == int(tiny)
    if tiny:
        assert warnings[0].object_id == source.id
        assert 0.0 < warnings[0].values["removed_mm3"] < profile.smallest_printable_volume


def test_brep_to_mesh_is_a_step_in_the_stack(profile: Profile) -> None:
    """§30: eine Richtung — und rücknehmbar, weil es eine Operation ist wie
    jede andere.
    """
    entry = SceneObject(id="obj_1", name="Block", mesh=block(), kind="brep")

    result = run("brep_to_mesh", entry, profile, deflection=0.05)

    assert result.outputs[0].kind == "mesh"
    assert isinstance(result.outputs[0].mesh, MeshData)
    assert [finding.code for finding in result.findings] == ["brep.converted"]


# --- der ganze Weg --------------------------------------------------------------


def test_a_step_file_becomes_a_scene_object(profile: Profile, tmp_path: Path) -> None:
    payload = step.write(edit.fillet(block(), 3.0, "vertical"))
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/teil.step", sha256=""
    )
    History(project.document).apply(
        "STEP laden", [OperationDraft(op="load_step", params={"source": "src_1"})]
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    entry = result.scene.objects["obj_1"]
    assert entry.kind == "brep"
    # Quader 40 x 30 x 20 minus vier Kantenrundungen R 3 über die Höhe 20:
    # 24 000 - 20 * (36 - 9 pi) = 23 845,487.
    assert entry.mesh.volume == pytest.approx(23845.4867, rel=1e-6)


def test_the_stack_carries_a_body_through_fillet_and_conversion(
    profile: Profile,
) -> None:
    """Markierung an jedem Schritt richtig — das dritte P12-Kriterium (§40)."""
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 20.0}
            )
        ],
    )
    history.apply(
        "Verrunden",
        [OperationDraft(op="fillet_edges", inputs=("obj_1",), params={"radius": 3.0})],
    )
    history.apply("Netz", [OperationDraft(op="brep_to_mesh", inputs=("obj_1",), params={})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    assert result.scene.objects["obj_1"].kind == "mesh"

    History(project.document).undo()
    back = evaluate(project.document, profile, sources=ProjectSources(project))
    assert back.scene.objects["obj_1"].kind == "brep", "one undo brings the exact body back"


def test_a_brep_object_exports_as_step(profile: Profile, tmp_path: Path) -> None:
    entry = SceneObject(
        id="obj_1", name="Block", mesh=edit.fillet(block(), 3.0, "vertical"), kind="brep"
    )

    plan = plan_export([entry], project_name="Teil", profile=profile, export_format="step")
    written = write_plan(plan, tmp_path, "step")

    assert written[0].name == "Teil_Block.step"
    again = step.read(written[0].read_bytes())
    assert again.volume == pytest.approx(entry.mesh.volume, rel=1e-9)


def test_a_mesh_cannot_pretend_to_be_a_step(profile: Profile) -> None:
    """Und der Fehler sagt, worum es geht.

    Er war eine ``ValidationError``, und deren Titel lautet „Ein Wert liegt
    außerhalb des zulässigen Bereichs" — im Dialog stand er über der richtigen
    Erklärung. Hier ist kein Wert außerhalb eines Bereichs; hier hat der Körper
    die falsche Art.
    """
    mesh = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))

    with pytest.raises(NeedsSolidError) as problem:
        export_bytes(mesh, "step", None, "", mesh)

    assert problem.value.values["constraint"] == "needs_brep"
    assert "STEP" in str(problem.value.detail)


def test_step_comes_back_addressable_and_stable() -> None:
    """Ein STEP-Körper ist adressierbar, und zwar bei jedem Laden gleich.

    Das Konzept P15 führte das als Lücke D16 („STEP-Import wird nicht
    kanonisiert — Flächen kommen nicht adressierbar zurück"). Der Befund kam
    aus dem Vergleich mit einer anderen Anwendung und wurde ungeprüft
    übernommen; er trifft auf Solidon nicht zu. `load_step` ruft `features_of`
    wie jede andere B-Rep-Operation.

    Geprüft wird trotzdem, und zwar das, worauf es ankommt: nicht nur *dass*
    Flächen zurückkommen, sondern dass dieselbe Datei dieselben Namen ergibt.
    Wäre die Reihenfolge zufällig, zeigte eine gespeicherte Skizzenebene
    (`feature:face_3`) morgen auf eine andere Wand — und niemand sähe, warum.
    """
    payload = step.write(edit.box(40.0, 30.0, 20.0))
    runs = [
        {
            key: (
                round(entry.params["area"], 4),
                tuple(round(v, 6) for v in entry.params["centre"]),
            )
            for key, entry in features_of(step.read(payload)).items()
        }
        for _ in range(3)
    ]

    assert len(runs[0]) == 6, "sechs Wände, sechs Namen"
    assert runs[0] == runs[1] == runs[2], "und jedes Laden ergibt dieselben"


def test_a_round_stud_is_not_a_hole() -> None:
    """Auf welcher Seite das Material liegt, entscheidet den Namen (§21).

    Jede geschlossene Zylinderfläche galt als Bohrung. Ein Ø-8-Zapfen, in
    Fusion gebaut und über STEP zurückgeholt, kam damit als „hole,
    diameter 8.0, depth 40" an — und dasselbe galt für jede Säule, jeden Dom
    und jeden Gewindekern. Das Vokabular aus §21 hat ``pin`` seit je; benutzt
    wurde es nur von den Bausteinen, die ihre Merkmale selbst benennen.
    """
    stud = edit.cylinder(diameter=8.0, height=40.0)

    kinds = {feature.kind for feature in features_of(stud).values()}

    assert "pin" in kinds, "ein Vollzylinder ist ein Zapfen"
    assert "hole" not in kinds, "und ganz sicher keine Bohrung"


def test_a_bore_through_a_block_stays_a_hole() -> None:
    """Die Gegenprobe — sonst wäre die Unterscheidung nur umgedreht."""
    from app.core.brep import edit as brep_edit

    drilled = brep_edit.boolean("difference", [block(), brep_edit.cylinder(8.0, 60.0)])

    kinds = {feature.kind for feature in features_of(drilled).values()}

    assert "hole" in kinds
    assert "pin" not in kinds


def test_losing_the_exact_body_is_said_where_it_happens(profile: Profile) -> None:
    """Der Weg von B-Rep zu Netz ist erlaubt, aber eine Einbahnstraße.

    Vorher ging man sie unbemerkt: „Aushöhlen" auf einem exakten Quader gibt
    Dreiecke zurück, und erst drei Schritte später lehnte „Tasche schneiden"
    mit „hier liegt ein Netz" ab — neben einer Operation, die nichts dafür
    kann. Gesagt wird es jetzt bei der Operation, die es verursacht.
    """
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Exakter Quader",
        [OperationDraft(op="create_brep_box", params={"width": 40, "depth": 40, "height": 40})],
    )

    before = evaluate(project.document, profile, sources=ProjectSources(project))
    assert [entry.kind for entry in before.scene.objects.values()] == ["brep"]
    assert not [f for f in before.scene.report.findings if f.code == "evaluate.exact_became_mesh"]

    history.apply(
        "Aushöhlen",
        [OperationDraft(op="hollow_object", inputs=("obj_1",), outputs=("obj_1",), params={})],
    )
    after = evaluate(project.document, profile, sources=ProjectSources(project))

    assert [entry.kind for entry in after.scene.objects.values()] == ["mesh"]
    said = [f for f in after.scene.report.findings if f.code == "evaluate.exact_became_mesh"]
    assert said, "der Verlust der Exaktheit gehört in den Bericht"
    assert said[0].severity == "info", "es ist ein erlaubter Weg, keine Warnung"
    assert said[0].values["op"] == "hollow_object", "und er nennt, wer ihn gegangen ist"


def test_the_exact_bore_takes_exactly_what_the_formula_says() -> None:
    """Die Kennzahl gegen den analytischen Körper, nicht gegen einen Vorlauf.

    Ein Zylinderschnitt hat eine geschlossene Formel, und der exakte Kern muss
    sie treffen — nicht ungefähr, sondern bis auf die Rechengenauigkeit. Genau
    das ist der Grund, aus dem es ihn gibt: Auf einem Netz wäre die Bohrung ein
    Vieleck mit ``BORE_SECTIONS`` Seiten und das Volumen um ein knappes Promille
    daneben.
    """
    from app.core.brep import edit as brep_edit

    solid = brep_edit.box(40.0, 30.0, 20.0)
    drilled = brep_edit.bore(solid, position=(0.0, 0.0, 20.0), axis="z", diameter=6.0)

    assert drilled.volume == pytest.approx(24000.0 - math.pi * 9.0 * 20.0, rel=1e-9)
    assert drilled.is_closed


def test_a_blind_bore_stops_at_its_depth() -> None:
    """Tiefe null bohrt durch, jede andere hört auf — dieselbe Zusicherung wie
    auf der Mesh-Seite, weil dieselben Parameter dasselbe bedeuten müssen.
    """
    from app.core.brep import edit as brep_edit

    solid = brep_edit.box(40.0, 30.0, 20.0)
    blind = brep_edit.bore(solid, position=(0.0, 0.0, 20.0), axis="z", diameter=6.0, depth=8.0)

    assert blind.volume == pytest.approx(24000.0 - math.pi * 9.0 * 8.0, rel=1e-9)
    assert blind.is_closed, "ein Sackloch lässt den Boden stehen"


def test_resizing_a_bore_keeps_an_exact_body(profile: Profile) -> None:
    """Derselbe Kundenweg auf STEP: Maß ändern, ohne Flächen und Kanten in
    feste Dreiecke umzuwandeln.

    Vergrößern und Verkleinern werden gegen die analytischen Zylindervolumen
    geprüft. Ein Bild oder eine Tessellation wäre gerade bei diesem Kern die
    falsche Wahrheit.
    """
    original = edit.bore(block(), position=(0.0, 0.0, HEIGHT), axis="z", diameter=6.0)
    features = features_of(original)
    bore = next(entry for entry in features.values() if entry.kind == "hole")
    source = SceneObject(id="obj_1", name="Block", mesh=original, kind="brep", features=features)

    larger = run("resize_hole", source, profile, at_feature=bore.id, diameter=10.0).outputs[0]
    smaller = run("resize_hole", source, profile, at_feature=bore.id, diameter=4.0).outputs[0]

    assert larger.kind == smaller.kind == "brep"
    assert larger.mesh.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - math.pi * (10.0 / 2.0) ** 2 * HEIGHT,
        rel=1e-9,
    )
    assert smaller.mesh.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - math.pi * (4.0 / 2.0) ** 2 * HEIGHT,
        rel=1e-9,
    )
    assert larger.mesh.is_closed and smaller.mesh.is_closed
    assert larger.features[bore.id].params["diameter"] == pytest.approx(10.0)
    assert smaller.features[bore.id].params["diameter"] == pytest.approx(4.0)


def test_resizing_a_step_bore_uses_the_unrounded_topology(profile: Profile) -> None:
    """Ein STEP-Maß reist in doppelter Genauigkeit bis zum Werkzeug.

    Vier Nachkommastellen gehören in die Anzeige, nicht zwischen den exakten
    Körper und seinen Füllring. Sonst bleibt beim Vergrößern eine hauchdünne
    alte Lippe stehen; beim Verkleinern schwimmt ein loser Ring im Loch.
    """
    original_diameter = 6.00004
    original_depth = 8.00004
    original = edit.bore(
        block(),
        position=(0.0, 0.0, HEIGHT),
        axis="z",
        diameter=original_diameter,
        depth=original_depth,
    )
    features = features_of(original)
    bore = next(entry for entry in features.values() if entry.kind == "hole")
    source = SceneObject(id="obj_1", name="Block", mesh=original, kind="brep", features=features)

    assert bore.params["diameter"] == pytest.approx(original_diameter, abs=EPS_GEOM)
    assert bore.params["depth"] == pytest.approx(original_depth, abs=EPS_GEOM)

    unchanged = run(
        "resize_hole",
        source,
        profile,
        at_feature=bore.id,
        diameter=float(bore.params["diameter"]),
    )
    assert unchanged.outputs[0] is source, "bloßes Bestätigen ändert den exakten Körper nicht"

    for target in (10.0, 4.0):
        changed = run("resize_hole", source, profile, at_feature=bore.id, diameter=target).outputs[
            0
        ]
        holes = [entry for entry in changed.features.values() if entry.kind == "hole"]
        expected = WIDTH * DEPTH * HEIGHT - math.pi * (target / 2.0) ** 2 * original_depth

        assert changed.mesh.volume == pytest.approx(expected, rel=1e-9)
        assert len(holes) == 1, "kein alter Rand und kein loser Füllring"
        assert holes[0].params["diameter"] == pytest.approx(target, abs=EPS_GEOM)
        assert holes[0].params["depth"] == pytest.approx(original_depth, abs=EPS_GEOM)


def test_repeated_mesh_resizing_keeps_a_blind_bore_blind(profile: Profile) -> None:
    """Ein gerundeter Anzeigewert darf die Bohrung nicht schrittweise vertiefen."""
    exact = edit.bore(
        edit.box(30.0, 30.0, 20.0),
        position=(0.0, 0.0, 20.0),
        axis="z",
        diameter=6.00004,
        depth=8.00004,
    )
    mesh = as_mesh_data(exact.to_mesh())
    features = detect(mesh)
    bore = next(entry for entry in features.values() if entry.kind == "hole")
    source = SceneObject(id="obj_1", name="Block", mesh=mesh, features=features)

    smaller = run("resize_hole", source, profile, at_feature=bore.id, diameter=4.0).outputs[0]
    reduced = smaller.features[bore.id]
    larger = run("resize_hole", smaller, profile, at_feature=bore.id, diameter=8.0).outputs[0]
    enlarged = larger.features[bore.id]

    assert not reduced.params["through"]
    assert not enlarged.params["through"]
    assert reduced.params["depth"] == pytest.approx(bore.params["depth"], abs=EPS_DISPLAY / 10.0)
    assert enlarged.params["depth"] == pytest.approx(bore.params["depth"], abs=EPS_DISPLAY / 10.0)
    assert larger.mesh.bounds.minimum == pytest.approx(mesh.bounds.minimum, abs=EPS_GEOM)
    assert larger.mesh.bounds.maximum == pytest.approx(mesh.bounds.maximum, abs=EPS_GEOM)


def test_the_exact_bore_agrees_with_the_mesh_on_direction_at_the_centre() -> None:
    """Skizze 10: bei der Vorgabeposition — der Achsmitte — entschieden die zwei
    Kerne den Tiebreak verschieden. Das Netz nimmt ``>=`` (nach unten), der
    exakte Kern nahm ``>`` (nach oben); wer zwischen ``create_box`` und
    ``create_brep_box`` umschaltete, bohrte in die Gegenrichtung — und
    ``MENU_TWINS`` ist dann kein Umschalten. Beide gehen jetzt zur
    tieferliegenden Hälfte, gemessen am Schwerpunkt.
    """
    from app.core.brep import edit as brep_edit

    solid = brep_edit.box(40.0, 30.0, 20.0)  # z 0..20, Mitte bei z = 10
    bored = brep_edit.bore(solid, position=(0.0, 0.0, 10.0), axis="z", diameter=6.0, depth=5.0)

    # Nach unten gebohrt (z 5..10 entfernt) steigt der Schwerpunkt über die Mitte.
    assert float(bored.mesh.raw.center_mass[2]) > 10.0, "ins Material nach unten, wie das Netz"


def test_a_bore_across_the_body_follows_its_axis() -> None:
    """Quer durch, entlang X — die Achse geht in den Zylinder und nicht in eine
    nachträgliche Drehung.
    """
    from app.core.brep import edit as brep_edit

    solid = brep_edit.box(40.0, 30.0, 20.0)
    across = brep_edit.bore(solid, position=(-20.0, 0.0, 10.0), axis="x", diameter=6.0)

    assert across.volume == pytest.approx(24000.0 - math.pi * 9.0 * 40.0, rel=1e-9)


def test_the_exact_branch_survives_a_bore(profile: Profile) -> None:
    """**Der Punkt, um den es geht.** Wer einen exakten Quader anlegt und eine
    Bohrung setzt, hatte danach ein Netz — und damit fielen Fase, Verrundung,
    Formschräge, Fläche versetzen, exaktes Aushöhlen, Tasche schneiden und der
    STEP-Export aus. Der exakte Zweig endete nach einem Schritt.

    Geprüft wird deshalb nicht die Bohrung, sondern was **nach** ihr noch geht:
    eine Verrundung, die einen exakten Körper braucht.
    """
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Exakter Quader",
        [OperationDraft(op="create_brep_box", params={"width": 40, "depth": 30, "height": 20})],
    )
    history.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_brep_hole",
                inputs=("obj_1",),
                params={"diameter": 6.0, "z": 20.0, "compensate": False},
            )
        ],
    )
    history.apply(
        "Verrundung",
        [OperationDraft(op="fillet_edges", inputs=("obj_1",), params={"radius": 2.0})],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.stopped_at is None, "die Kette läuft durch"
    assert [entry.kind for entry in result.scene.objects.values()] == ["brep"]
    assert not [
        f for f in result.scene.report.findings if f.code == "evaluate.exact_became_mesh"
    ], "eine exakte Bohrung verliert die Exaktheit nicht"


def test_the_exact_bore_and_its_twin_read_the_same_parameters() -> None:
    """Beide Kerne teilen **ein** Schema, keine zwei gleichlautenden.

    Daran hängt ``change_kernel``: Es reicht die Parameter des einen Schritts
    an den anderen weiter, und wortgleiche Schemata laufen beim nächsten
    Nachbessern auseinander. Dasselbe Objekt kann das nicht.
    """
    from app.core.registry import MENU_TWINS, REGISTRY

    assert MENU_TWINS["drill_brep_hole"] == "drill_hole"
    exact = REGISTRY.get("drill_brep_hole")
    mesh = REGISTRY.get("drill_hole")
    assert exact.params is mesh.params, "ein Schema, nicht zwei gleichlautende"
    assert exact.deterministic, "ohne Rückfallkette braucht es keinen Startwert"


def test_switching_a_bore_between_the_kernels_keeps_its_values(profile: Profile) -> None:
    """Ein gesetzter Schritt lässt sich nachträglich umstellen — mit denselben
    Werten, sonst wäre es eine andere Bohrung.
    """
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Exakter Quader",
        [OperationDraft(op="create_brep_box", params={"width": 40, "depth": 30, "height": 20})],
    )
    values = {"diameter": 6.0, "x": 0.0, "y": 0.0, "z": 20.0, "compensate": False}
    history.apply(
        "Bohrung im Netz",
        [OperationDraft(op="drill_hole", inputs=("obj_1",), params=dict(values))],
    )
    bore_step = project.document.ops[-1]

    history.change_kernel(bore_step.id, "drill_brep_hole", dict(values))

    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert [entry.kind for entry in result.scene.objects.values()] == ["brep"]
    body = next(iter(result.scene.objects.values()))
    assert body.mesh.volume == pytest.approx(24000.0 - math.pi * 9.0 * 20.0, rel=1e-9)


def test_the_corner_where_three_fillets_meet_is_one_too() -> None:
    """Verrundet man alle Kanten, bleibt an jeder Ecke ein Kugelstück übrig.

    Es fiel bis dahin durch: ``_describe`` kannte Ebene und Zylinder, und acht
    von 26 Flächen waren damit nichts — ausgerechnet die, die der Kunde als
    „abgerundete Ecke" sieht.
    """
    rounded = edit.fillet(block(), 2.0, "all")

    found = features_of(rounded)

    fillets = [entry for entry in found.values() if entry.kind == "fillet"]
    # Zwölf Kanten und acht Ecken: der Quader hat keine Fläche mehr, die durchfällt.
    assert len(fillets) == 20, f"12 Kanten + 8 Ecken: {sorted(found)}"
    assert len(found) == len(rounded.faces()), "keine Fläche bleibt unbenannt"
    corners = [entry for entry in fillets if entry.params["length"] == 0.0]
    assert len(corners) == 8
    assert {entry.params["radius"] for entry in corners} == {2.0}


def test_a_socket_is_a_sphere_and_not_a_corner() -> None:
    """Beide sind Kugelausschnitte — die Größe trennt sie nicht.

    Der erste Versuch maß den Anteil an der Vollkugel: Eckverrundung 0,125,
    volle Kugel 1,000. Das trennt falsch, denn eine Pfanne ist nie mehr als
    eine Halbkugel, und eine flache Kalotte deckt selbst 0,1 ab. Was sie
    trennt, ist die Nachbarschaft: An einer Ecke laufen verrundete Kanten
    zusammen, an einer Pfanne nicht.
    """
    ball = Solid(BRepPrimAPI_MakeSphere(6.0).Shape())
    hollowed = edit.boolean("difference", [block(), edit.moved(ball, (0.0, 0.0, 20.0))])

    found = features_of(hollowed)

    spheres = [entry for entry in found.values() if entry.kind == "sphere"]
    assert len(spheres) == 1, f"die Mulde ist eine Kugel: {sorted(found)}"
    assert spheres[0].params["recess"], "eingelassen, keine Kuppel"
    assert not [entry for entry in found.values() if entry.kind == "fillet"]


def test_a_corner_fillet_leaves_no_degenerate_triangles() -> None:
    """Am Pol einer Kugelfläche entstand ein Dreieck mit zwei gleichen Ecken.

    **Die Fläche war dabei nie kaputt** — Euler-Zahl 2, Volumen unverändert,
    kein Loch. Aber ``is_watertight`` meldete „nein", weil trimesh die
    degenerierten Kanten als offen zählt, und das ist die Prüfung, die viele
    Werkzeuge fahren, unsere eigenen Tests eingeschlossen. In die exportierte
    STL wanderten die acht Dreiecke mit.

    **Zwei Fehlschlüsse liegen auf dem Weg dorthin, beide gemessen und
    verworfen:** ``is_watertight`` als Beweis für ein Loch — es ist keiner —,
    und „die drei Knotennummern sind nicht paarweise verschieden" als
    Bedingung. OCCT vergibt am Pol *zwei* Nummern für denselben Ort; erst
    trimesh führt sie beim Einlesen zusammen. Geprüft wird deshalb über die
    Koordinaten.
    """
    import numpy as np

    from app.core.geom.mesh import as_mesh_data

    solid = edit.fillet(edit.box(WIDTH, DEPTH, HEIGHT), 2.0, "all")
    mesh = as_mesh_data(solid.mesh).raw

    entartet = int(np.sum(mesh.area_faces <= EPS_GEOM))
    assert entartet == 0, f"{entartet} Dreiecke mit Fläche null"
    assert mesh.is_watertight, "acht Pole, acht offene Kanten — so sah es aus"
    assert mesh.euler_number == 2, "die Oberfläche war schon vorher geschlossen"
    assert solid.volume == pytest.approx(mesh.volume, rel=1e-3), (
        "das Weglassen darf am Körper nichts ändern"
    )


# --- was der Netz-Zwilling meldete und dieser nicht ------------------------------


@pytest.mark.parametrize(
    "attempt",
    [
        lambda: profiles.shell_open_top(edit.sphere(20.0), 1.0),
        lambda: profiles.draft_vertical(edit.sphere(20.0), 5.0),
        lambda: profiles.push_faces(edit.box(40.0, 30.0, 20.0), (0.0, 0.0, 1.0), -25.0),
        lambda: profiles.draft_vertical(_nurbs(edit.box(60.0, 40.0, 10.0)), 3.0),
    ],
    ids=["shell_open_top", "draft_vertical", "push_faces", "draft_on_nurbs"],
)
def test_a_refusal_of_the_exact_kernel_offers_no_mesh_repair(attempt: Callable[[], Any]) -> None:
    """Wo der exakte Kern absagt, heißt der Weg nach vorn „Eingabe korrigieren".

    Ohne eigene Vorschläge erbte die Absage „Reparieren und erneut versuchen"
    und „Stellen zeigen" — Netzreparatur und offene Kanten gibt es an einem
    B-Rep-Körper nicht (Review 21.09.2026; ``edit.boolean`` sagte es schon).

    **Und die Formschräge an einer NURBS-Wand kam gar nicht als Absage an**
    (22.09.2026): ``BRepOffsetAPI_DraftAngle.Add`` wirft an einer
    B-Spline-Fläche ``Standard_ConstructionError``, und der Aufruf stand
    außerhalb der Fehlerübersetzung — der Kunde las „unerwarteter Fehler" und
    wurde um einen Fehlerbericht gebeten, an einem STEP-Teil aus einem
    Programm, das jede Fläche als NURBS schreibt.
    """
    from app.core.errors import CANCEL, CORRECT_INPUT, REPAIR_AND_RETRY, SHOW_LOCATIONS

    with pytest.raises(GeometryError) as caught:
        attempt()
    offered = [action.id for action in caught.value.suggestions]
    assert CORRECT_INPUT.id in offered and CANCEL.id in offered
    assert REPAIR_AND_RETRY.id not in offered and SHOW_LOCATIONS.id not in offered


@pytest.mark.parametrize(
    ("build", "sentence"),
    [
        (
            lambda outline: profiles.loft(outline, outline, 10.0),
            "Aus einem der gezeichneten Löcher entsteht kein Durchzug.",
        ),
        (
            lambda outline: profiles.sweep_path(
                outline,
                Outline(segments=(Segment("line", (0.0, 0.0), (0.0, 30.0)),)),
            ),
            "Entlang dieser Bahn lässt sich der Querschnitt nicht führen.",
        ),
    ],
    ids=["loft", "sweep_path"],
)
def test_a_hole_that_cannot_be_cut_is_refused_with_the_sentence_of_its_way(
    build: Callable[[Any], Solid], sentence: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scheitert das Abziehen eines gezeichneten Lochs, spricht die Absage vom Loch.

    ``_fuzzy_boolean`` trug bis zum 22.09.2026 den Satz des alten
    Gewindebolzens („Kern und Gang des Gewindes ließen sich nicht zu einem
    Körper verbinden …") — seit RM-195 rufen es nur noch Durchzug und Bahn,
    und ein Loch im Durchzug scheiterte mit einem Satz über ein Gewinde, das
    es nicht gab. Das Scheitern wird hier erzwungen: Der Kern schneidet
    diese Löcher, und eine Eingabe, an der er es nicht kann, wäre eine
    Frage der OCCT-Version.
    """

    class Refusing:
        """Ein Boolescher Builder, der nicht fertig wird."""

        def Build(self) -> None:  # noqa: N802 - Name der externen OCP-API
            return None

        def IsDone(self) -> bool:  # noqa: N802 - Name der externen OCP-API
            return False

    monkeypatch.setattr(profiles, "boolean_builder", lambda *args, **kwargs: Refusing())
    square = Outline(
        segments=(
            Segment("line", (-10.0, -10.0), (10.0, -10.0)),
            Segment("line", (10.0, -10.0), (10.0, 10.0)),
            Segment("line", (10.0, 10.0), (-10.0, 10.0)),
            Segment("line", (-10.0, 10.0), (-10.0, -10.0)),
        ),
        holes=(Outline(circle=((0.0, 0.0), 3.0)),),
    )
    with pytest.raises(GeometryError) as caught:
        build(square)
    assert caught.value.detail == sentence
    assert "Gewinde" not in str(caught.value.detail)


def test_the_exact_box_takes_corner_and_place_in_one_motion(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bezugspunkt und Lage sind eine Matrix: ein Prüf- und Kopierweg, nicht zwei.

    Der Eckbezug lief als eigenes ``edit.moved`` vor der Lage — zwei native
    Builder, zwei Gültigkeitsprüfungen, zwei Kopien für eine Bewegung
    (Review 21.09.2026). Gemessen wird, wo die Ecke landet, und dass kein
    zweiter Bewegungsschritt mehr läuft.
    """
    moved_calls: list[tuple[float, float, float]] = []
    original = edit.moved

    def counting(solid: Solid, offset: tuple[float, float, float]) -> Solid:
        moved_calls.append(offset)
        return original(solid, offset)

    monkeypatch.setattr(edit, "moved", counting)
    placed = run(
        "create_brep_box",
        None,
        profile,
        width=12.0,
        depth=8.0,
        height=5.0,
        anchor="corner",
        x=4.0,
        y=5.0,
        z=6.0,
    ).outputs[0]
    assert placed.mesh.bounds.minimum == pytest.approx((4.0, 5.0, 6.0), abs=1e-9)
    assert placed.mesh.bounds.maximum == pytest.approx((16.0, 13.0, 11.0), abs=1e-9)
    assert float(placed.mesh.volume) == pytest.approx(480.0, rel=1e-12)
    assert moved_calls == []


def test_a_bore_that_swallows_the_body_is_refused(profile: Profile) -> None:
    """Ein Körper, der nichts ist, kommt nicht als Erfolg zurück.

    **Der schwerste Zwillingsbefund vom 27.08.2026.** OCCT rechnet sauber
    durch, wenn das Werkzeug den Körper vollständig deckt, und gibt eine leere
    Form zurück: null Volumen, null Flächen, nicht wasserdicht. Bis dahin ging
    die als Ergebnis durch — im Objektbaum stand danach ein Objekt mit Namen,
    das man anklicken, umbenennen und **speichern** konnte, und der Prüfbericht
    sagte kein Wort; gemeldet hätte es erst der Export.

    Der Netz-Zwilling wirft an derselben Stelle seit je, und zwar mit genau
    diesem Satz — er ist deshalb geteilt (``boolean.NOTHING_LEFT_*``) und nicht
    ein zweites Mal geschrieben. ``without_effect`` fängt den Fall nicht: Es
    prüft auf *nichts abgetragen*, hier wurde *alles* abgetragen.
    """
    from app.core.errors import GeometryError
    from app.core.geom.boolean import NOTHING_LEFT_TITLE

    body = run("create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0).outputs[0]

    with pytest.raises(GeometryError) as caught:
        run("drill_brep_hole", body, profile, diameter=50.0)

    assert str(caught.value.title) == str(NOTHING_LEFT_TITLE)
    assert caught.value.suggestions, "ein Fehler ohne Weg nach vorn ist unfertig (Regel 17)"


def test_a_bore_over_the_edge_says_so_in_the_exact_kernel_too(profile: Profile) -> None:
    """Dieselbe Warnung wie im Netz — sie fehlte nur, weil die Signatur ein
    ``MeshData`` verlangte.

    Gemessen waren sechs von sechs Fällen still, bei geometrisch identischem
    Ergebnis (Abweichung unter 0,005 %). Die Prüfung liest nichts als den
    Hüllquader, und den trägt ``Solid`` auch; sie fragt jetzt nach einem
    Protokoll, wie ``without_effect`` es mit ``HasVolume`` vormacht.
    """
    body = run("create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0).outputs[0]

    over = run("drill_brep_hole", body, profile, diameter=10.0, x=18.0)
    inside = run("drill_brep_hole", body, profile, diameter=10.0, x=0.0)

    assert "bore.over_the_edge" in {entry.code for entry in over.findings}
    # Die Gegenprobe: eine Bohrung im Material warnt nicht, sonst warnt jede.
    assert "bore.over_the_edge" not in {entry.code for entry in inside.findings}


def test_the_exact_shell_reports_what_the_mesh_twin_reports(profile: Profile) -> None:
    """*Exakt aushöhlen* gab in keinem einzigen Fall einen Befund zurück.

    Dreizehn Wandstärken gemessen, von 0,2 bis 50: Bei 15 mm kam ein Körper mit
    Nullspalt zurück — unverändertes Volumen und nicht mehr wasserdicht —,
    zwischen 16 und 50 passierte fast immer gar nichts, und gesagt wurde nie
    etwas. OCCT gibt bei zu großem negativem Offset die Eingangsform zurück,
    ohne zu werfen. Der Netz-Zwilling kennt für dieselbe Lage fünf Codes.

    Beide Befunde kommen aus derselben Fabrik wie beim Zwilling — sonst wäre
    hier der nächste Zwilling entstanden, statt einen zu beseitigen.
    """
    body = run("create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0).outputs[0]

    hopeless = run("shell_exact", body, profile, wall=15.0)
    unprintable = run("shell_exact", body, profile, wall=0.3)
    sound = run("shell_exact", body, profile, wall=2.0)

    assert "hollow.too_thin" in {entry.code for entry in hopeless.findings}
    assert "hollow.wall_below_nozzle" in {entry.code for entry in unprintable.findings}

    # **Und der brauchbare Fall schweigt nicht — er berichtet.** Hier stand
    # „bleibt still" als Gegenprobe, und das schrieb den letzten Unterschied
    # zwischen den Zwillingen fest: Mit einer Wandstärke, die funktioniert,
    # sagte der Netz-Zwilling ``hollow.done`` mit seinen Zahlen und der exakte
    # gar nichts. Wie viel Material weg ist, ist der Grund, aus dem man
    # aushöhlt. Was die Gegenprobe wirklich meint, ist „keine **Warnung**".
    codes = {entry.code for entry in sound.findings}
    assert codes == {"hollow.done"}, codes
    assert all(entry.severity == "info" for entry in sound.findings)
    fertig = next(entry for entry in sound.findings if entry.code == "hollow.done")
    assert fertig.values["removed_cm3"] > 0.0, "ohne die Zahl ist die Meldung leer"


def test_the_printable_wall_comes_from_the_profile_not_from_a_number(profile: Profile) -> None:
    """Die Grenze ist zwei Extrusionsbreiten — je Drucker eine andere Zahl.

    Im Schema stand ``minimum=0.4`` am Netz und ``0.2`` am exakten Kern. Die
    Abweichung fiel auf; der eigentliche Fund ist, dass auch die 0,4 nur
    zufällig stimmt — für eine 0,4er Düse. Ein Schema-Minimum kann das nicht
    leisten, es steht zur Deklarationszeit fest und das Profil kommt mit dem
    Auftrag (§39, Regel 7).
    """
    from app.core.geom.hollow import below_printable_wall

    least = profile.minimum_wall_thickness
    assert least > 0.4, (
        f"dieser Drucker muss über der alten Schemazahl liegen, sonst prüft der "
        f"Test nichts: {least}"
    )

    assert below_printable_wall(least - 0.1, profile) is not None
    assert below_printable_wall(least + 0.1, profile) is None


def test_without_a_printer_there_is_no_wall_verdict(profile: Profile) -> None:
    """Ohne Drucker keine Aussage über die Wandstärke.

    Der Fall kommt vor — ein direkter Aufruf der Operation ohne Profil, wie
    ihn Tests und die Kommandozeile bauen. Die alte Zahlenkonstante brauchte
    keinen Drucker, ``Profile.minimum_wall_thickness`` schon; ohne diesen
    Zweig endete `shell_exact` dort in einem AttributeError. Gefunden von ce
    im Torlauf, an `test_the_exact_shell_leaves_exactly_the_wall`.

    Dieselbe Regel wie bei ``boolean.without_effect``: Die Grenze *ist* der
    Drucker, also gibt es sie ohne ihn nicht — und ein Aufrufer, der keinen
    kennt, soll keinen erfinden.
    """
    from app.core.geom.hollow import below_printable_wall

    assert below_printable_wall(0.1, None) is None
    # Die Gegenprobe: mit Drucker gibt es sehr wohl ein Urteil.
    assert below_printable_wall(0.1, profile) is not None


# --- Was die Tessellierung hinterlässt ------------------------------------------


def _with_a_t_junction() -> MeshData:
    """Zwei Dreiecke, deren gemeinsame Kante nur eines von ihnen kennt.

    Der Defekt aus dem Eiffelturm-Fund, im Kleinen: Die lange Kante des einen
    Dreiecks wurde beim Bau des Nachbarn von einem Punkt geteilt, und der
    anderen Seite hat es nie jemand gesagt. Kein Loch — die Flächen liegen
    lückenlos aneinander —, und trotzdem melden beide Seiten offene Kanten.
    """
    import numpy as np
    import trimesh

    from app.core.geom.mesh import MeshData

    punkte = np.array(
        [
            [0.0, 0.0, 0.0],  # 0
            [2.0, 0.0, 0.0],  # 1
            [1.0, 1.0, 0.0],  # 2  Spitze oben
            [1.0, 0.0, 0.0],  # 3  sitzt auf der Kante 0-1
            [1.0, -1.0, 0.0],  # 4 Spitze unten
        ],
        dtype=float,
    )
    # Oben ein ungeteiltes Dreieck über 0-1, unten zwei, die den Punkt 3 kennen.
    dreiecke = np.array([[0, 1, 2], [0, 3, 4], [3, 1, 4]], dtype=np.int64)
    return MeshData.of(trimesh.Trimesh(vertices=punkte, faces=dreiecke, process=False))


def test_the_stitcher_closes_a_seam_the_hole_filler_cannot() -> None:
    """Der Riss an der Flanke ist eine T-Kreuzung, kein Loch.

    Der Fall ist macOS: Ein Gewindebolzen ist dort als **Form** in Ordnung —
    geschlossen, ein Stück, richtiges Volumen, STEP trägt ihn —, aber seine
    Vernetzung ritzt an der Flanke. `_finely_meshed` half nicht, weil es
    ausschließlich versucht, feiner zu vernetzen; repariert wurde nie.

    Warum **Vernähen** und nicht Füllen: Gemessen an einem M6-Netz mit einem
    echten Loch lässt `repair.fill_holes` es offen und rührt kein Dreieck an —
    zu Recht, denn ein Dreieck über kollinearen Punkten hat keine Fläche. Was
    hier fehlt, ist kein Material, sondern ein Punkt, den die Nachbarfläche
    nicht kennt.

    Der echte Riss lässt sich auf dieser Plattform nicht erzeugen (unter
    Windows ist jede Größe dicht), also bekommt der Vernäher den Defekt
    vorgesetzt, den der Befund beschreibt.
    """
    from app.core.geom.repair import open_edge_count, stitch_t_junctions

    kaputt = _with_a_t_junction()
    vorher = open_edge_count(kaputt)
    assert vorher > 0, "der Prüfling muss offene Kanten haben, sonst prüft nichts"

    geheilt, naehte = stitch_t_junctions(kaputt)

    assert naehte > 0, "die T-Kreuzung muss gefunden werden"
    assert open_edge_count(geheilt) < vorher


def test_a_repair_that_makes_it_worse_is_dropped() -> None:
    """Drei Nähte heißen nicht drei geschlossene Kanten.

    Beim Bauen gemessen und beinahe übersehen: An einem Netz, dessen Ränder
    gar keine T-Kreuzungen sind — ein absichtlich zerlegter Würfel —, findet
    der Vernäher trotzdem drei Nähte und hinterlässt **18 offene Kanten statt
    15**. Er teilt Flächen an Punkten, die dort zufällig aufsitzen.

    Die Zahl der Nähte ist damit kein Erfolgsmaß. `_stitched` vergleicht
    deshalb die offenen Kanten und gibt das Original zurück, wenn es nicht
    besser wurde: Eine Reparatur, die verschlimmert, ist keine.
    """
    import trimesh

    from app.core.brep.kernel import _stitched
    from app.core.geom.mesh import MeshData
    from app.core.geom.repair import open_edge_count

    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    fein = box.subdivide()
    zerlegt = MeshData.of(
        trimesh.util.concatenate(
            [
                trimesh.Trimesh(vertices=fein.vertices, faces=fein.faces[:6], process=False),
                trimesh.Trimesh(vertices=box.vertices, faces=box.faces[3:], process=False),
            ]
        )
    )
    assert not zerlegt.is_watertight

    ergebnis = _stitched(zerlegt)

    assert ergebnis is zerlegt, "verschlimmerte Reparatur muss verworfen werden"
    assert open_edge_count(ergebnis) == open_edge_count(zerlegt)


def test_a_closed_mesh_never_reaches_the_stitcher(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Normalfall kostet die Frage, nicht die Arbeit.

    `is_watertight` sind 0,1 ms an einem Netz mit 13 744 Dreiecken, das
    Vernähen 2,6 ms. Die Abkürzung lohnt also — aber sie ist **nur** eine
    Abkürzung: Auch ohne sie käme dasselbe Netz heraus, weil der Vernäher an
    einem dichten Netz nichts findet.

    Deshalb prüft dieser Test nicht das Ergebnis, sondern ob der teure Weg
    überhaupt betreten wird. Der erste Anlauf verglich die Objektidentität und
    blieb grün, als die Bedingung ausgeschaltet war — er prüfte eine Zusage,
    die auch ohne sie gilt.
    """
    import trimesh

    from app.core.brep import kernel
    from app.core.geom import repair
    from app.core.geom.mesh import MeshData

    gerufen: list[int] = []
    echt = repair.stitch_t_junctions

    def zaehlend(mesh: MeshData) -> tuple[MeshData, int]:
        gerufen.append(1)
        return echt(mesh)

    monkeypatch.setattr(repair, "stitch_t_junctions", zaehlend)

    dicht = MeshData.of(trimesh.creation.box(extents=(4.0, 4.0, 4.0)))
    assert dicht.is_watertight

    assert kernel._stitched(dicht) is dicht
    assert not gerufen, "ein dichtes Netz darf den Vernäher nicht kosten"


def test_every_twin_pair_answers_the_same_question_the_same_way(profile: Profile) -> None:
    """Vier Paare, dieselben Eingaben, dieselben Befunde.

    Ein Zwilling ist dieselbe Handlung in zwei Rechenkernen, und der Kunde
    wählt zwischen ihnen über einen Haken im selben Dialog. Er erwartet also
    dasselbe Verhalten — und vor allem dieselben **Auskünfte**. Läuft ein Paar
    auseinander, merkt es niemand: Beide Wege funktionieren, nur einer
    schweigt.

    Drei Unterschiede sind einzeln gemeldet und einzeln behoben worden
    (`bore.over_the_edge`, der leere Körper beim zu großen Loch,
    `hollow.too_thin`), und beim vierten Anlauf stellte sich heraus, dass noch
    einer offen war: Mit einer Wandstärke, die *funktioniert*, meldete das Netz
    `hollow.done` und der exakte Kern nichts. Einzeln gemeldete Fälle finden
    den nächsten nicht — dieser Test fährt alle Paare gegeneinander.

    Die Werte treffen absichtlich die Grenzen: ein Loch größer als der Körper,
    eine Wand dicker als das halbe Teil. Dort trennt sich, wer etwas sagt und
    wer schweigt.
    """
    from app.core.registry.registry import MENU_TWINS

    assert len(MENU_TWINS) >= 4, f"zu wenige Paare gefunden: {MENU_TWINS}"

    quader_exakt = run(
        "create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0
    ).outputs[0]
    quader_netz = run("create_box", None, profile, width=40.0, depth=30.0, height=20.0).outputs[0]

    faelle: list[tuple[str, str, dict[str, object]]] = [
        ("drill_brep_hole", "drill_hole", {"diameter": 6.0}),
        ("drill_brep_hole", "drill_hole", {"diameter": 10.0, "x": 18.0}),
        ("shell_exact", "hollow_object", {"wall": 2.0}),
        ("shell_exact", "hollow_object", {"wall": 15.0}),
    ]

    abweichend: list[str] = []
    for exakt, netz, werte in faelle:
        assert MENU_TWINS.get(exakt) == netz, f"{exakt} ist nicht mehr mit {netz} gepaart"
        codes_exakt = {entry.code for entry in run(exakt, quader_exakt, profile, **werte).findings}
        codes_netz = {entry.code for entry in run(netz, quader_netz, profile, **werte).findings}
        # Verglichen wird die **Menge** der Codes, nicht ihre Zahl: Der
        # Netz-Zwilling darf zusätzlich über sein Raster sprechen, das der
        # exakte Kern nicht hat. Was beide kennen, müssen beide sagen.
        gemeinsam = codes_exakt | codes_netz
        fehlt_exakt = {code for code in gemeinsam if code in codes_netz and code not in codes_exakt}
        if fehlt_exakt & {"hollow.done", "hollow.too_thin", "bore.over_the_edge"}:
            abweichend.append(f"{exakt} schweigt zu {sorted(fehlt_exakt)} bei {werte}")

    assert not abweichend, abweichend


def test_every_opencascade_import_in_the_application_resolves() -> None:
    """Jeder ``from OCP.… import …`` in ``app/`` und ``tools/`` trifft einen Namen.

    OCP 8 hat Module leer zurückgelassen, statt sie zu entfernen: ``OCP.GCE2d``
    und ``OCP.TColgp`` importieren, aber ``GCE2d_MakeSegment`` und
    ``TColgp_Array1OfPnt2d`` gibt es nicht mehr. Der Fehler fällt erst, wenn die
    Zeile läuft — bei der Selbstschnittprüfung der Skizze war das kein Test in
    dieser Datei, sondern das Beispielprojekt „skizze-mit-massen" (05.09.2026).
    Statisch geprüft trifft es jede Stelle, auch die, die kein Test hier fährt.
    """
    import ast
    import importlib

    root = Path(__file__).resolve().parent.parent
    missing: list[str] = []
    checked: set[tuple[str, str]] = set()
    for path in sorted([*(root / "app").rglob("*.py"), *(root / "tools").rglob("*.py")]):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if node.module != "OCP" and not node.module.startswith("OCP."):
                continue
            for alias in node.names:
                checked.add((node.module, alias.name))
                try:
                    getattr(importlib.import_module(node.module), alias.name)
                except Exception as problem:
                    missing.append(
                        f"{path.relative_to(root)}:{node.lineno} {node.module}.{alias.name}"
                        f" ({type(problem).__name__})"
                    )
    assert checked, "Keine OCP-Importe gefunden; die Prüfung hat keinen Gegenstand."
    assert not missing, "\n".join(missing)


def test_an_open_result_of_an_exact_resize_is_an_error_not_a_scene_object(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Vertrag, nicht die Ursache: Ein offener Körper kommt nie in die Szene.

    An der Teppichklammer (Durchsicht vom 05.09.2026, Datei 19) kam
    ``resize_hole`` mit offener Tessellation zurück, und die Operation galt
    als gelungen — Volumen und Flächen waren da. Die Ursache ist behoben
    (``brep.features`` legt die Mitte auf die Achse); hier wird der Fall
    gestellt, damit die Frage nach der Geschlossenheit zum Erfolg gehört.
    """
    from app.core.geom import prepare_ops

    original = edit.bore(block(), position=(0.0, 0.0, HEIGHT), axis="z", diameter=6.0)
    features = features_of(original)
    bore = next(entry for entry in features.values() if entry.kind == "hole")
    source = SceneObject(id="obj_1", name="Block", mesh=original, kind="brep", features=features)

    class Open(Solid):
        @property
        def is_closed(self) -> bool:
            return False

    honest = edit.resize_bore(
        original,
        position=bore.params["centre"],
        direction=bore.params["axis"],
        previous_diameter=6.0,
        diameter=7.0,
        depth=float(bore.params["depth"]),
    )
    monkeypatch.setattr(
        edit,
        "resize_bore",
        lambda *args, **kwargs: Open(honest.shape),
    )

    with pytest.raises(GeometryError) as caught:
        run("resize_hole", source, profile, at_feature=bore.id, diameter=7.0)

    assert caught.value.title == prepare_ops.OPEN_BODY_TITLE
    assert caught.value.suggestions, "Regel 17: ein Fehler trägt einen Handlungsvorschlag"


def test_the_exact_primitives_take_the_same_placement_as_their_twins(profile: Profile) -> None:
    """Ein Umschalten zwischen den Kernen lässt den Körper, wo er ist (§15.4).

    Seit die Grundkörper eine freie Position und Richtung tragen, müssen beide
    Zwillinge sie kennen — sonst stünde der exakte Quader nach dem Haken
    „Flächen und Kanten später bearbeiten" wieder im Ursprung, und der
    Umschalter verschwiege sechs Felder (``test_a_twin_toggle_says_what_it_takes_away``).
    Gemessen an den Hüllquadern: Der Quader ist in beiden Kernen exakt, der
    Zylinder des Netzes ein 128-Eck, das der Anzeigetoleranz genügt.
    """
    placement = {"x": 12.0, "y": -7.0, "z": 30.0, "nx": 1.0, "ny": 0.0, "nz": 1.0}
    size = {"width": 40.0, "depth": 30.0, "height": 20.0}

    twin = run("create_box", None, profile, anchor="centre", **size, **placement).outputs[0]
    exact = run("create_brep_box", None, profile, **size, **placement).outputs[0]
    assert exact.kind == "brep"
    assert exact.mesh.bounds.minimum == pytest.approx(twin.mesh.bounds.minimum, abs=EPS_DISPLAY)
    assert exact.mesh.bounds.maximum == pytest.approx(twin.mesh.bounds.maximum, abs=EPS_DISPLAY)

    round_twin = run(
        "create_cylinder", None, profile, diameter=20.0, height=15.0, segments=128, **placement
    ).outputs[0]
    round_exact = run(
        "create_brep_cylinder", None, profile, diameter=20.0, height=15.0, **placement
    ).outputs[0]
    assert round_exact.mesh.bounds.centre == pytest.approx(
        round_twin.mesh.bounds.centre, abs=EPS_DISPLAY
    )
    assert round_exact.mesh.volume == pytest.approx(math.pi * 100.0 * 15.0, rel=1e-9)

    # Und ohne Angaben steht alles, wo es stand: kein Versatz, keine Drehung.
    plain = run("create_brep_box", None, profile, **size).outputs[0]
    assert plain.mesh.bounds.minimum == pytest.approx((-20.0, -15.0, 0.0), abs=EPS_GEOM)


@pytest.mark.parametrize(
    ("op", "params"),
    [
        ("translate_object", {"dx": 5.0, "dy": -3.0}),
        ("rotate_object", {"axis": "z", "angle": 15.0}),
        ("place_on_bed", {}),
        ("mirror_object", {}),
        ("orient_for_print", {"thorough": False}),
        ("orient_for_print", {"thorough": True, "candidates": 24}),
        ("arrange_bed", {"spacing": 6.0}),
    ],
)
def test_a_rigid_move_leaves_an_exact_body_exact(op: str, params: dict[str, object]) -> None:
    """Verschieben, Drehen, Spiegeln, Ausrichten, Anordnen: der Körper bleibt bearbeitbar.

    **Der Fall, für den es das gibt.** Roberts Filamenthalter kam am
    06.09.2026 aus einer Skizze als exakter Körper und war nach „Auf dem Bett
    anordnen" ein Netz. *Verrunden* stand danach ausgegraut im Menü, mit dem
    Hinweis, man möge die Schritte zurücknehmen — für eine Verschiebung, die
    an der Form nichts ändert. Gemessen wurden damals sieben Bewegungen, fünf
    davon warfen den exakten Körper weg.

    Geprüft wird die Sorte **und** das Volumen: Eine Bewegung, die den Körper
    exakt lässt, aber dabei sein Volumen ändert, hat ihn verbogen.
    """
    from app.core.knowledge.profiles import make_profile
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    profile = make_profile("centauri-carbon-2", "pla")
    project = new_project("centauri-carbon-2", "pla")
    document = project.document
    history = History(document)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 20.0}
            )
        ],
    )
    before = next(
        iter(evaluate(document, profile, sources=ProjectSources(project)).scene.objects.values())
    )
    assert before.kind == "brep", "der Ausgangskörper ist exakt"

    history.apply(op, [OperationDraft(op=op, inputs=("obj_1",), params=params)])
    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.scene.objects, f"{op} hat die Auswertung angehalten (bei {result.stopped_at})"
    after = next(iter(result.scene.objects.values()))
    assert after.kind == "brep", f"{op} hat den exakten Körper zu Dreiecken gemacht"
    assert after.mesh.volume == pytest.approx(before.mesh.volume, rel=1e-9), (
        f"{op} hat den Körper verbogen"
    )


def test_a_scaled_body_stays_exact_without_a_conversion_notice() -> None:
    """Skalieren erhält den exakten Körper und meldet keine erfolgte Vernetzung."""
    from app.core.knowledge.profiles import make_profile
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    profile = make_profile("centauri-carbon-2", "pla")
    project = new_project("centauri-carbon-2", "pla")
    document = project.document
    history = History(document)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 20.0}
            )
        ],
    )
    history.apply(
        "Skalieren", [OperationDraft(op="scale_object", inputs=("obj_1",), params={"factor": 1.1})]
    )
    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    after = next(iter(result.scene.objects.values()))
    assert after.kind == "brep"
    assert isinstance(after.mesh, Solid)
    assert after.mesh.bounds.size == pytest.approx((44.0, 33.0, 22.0))
    assert after.mesh.volume == pytest.approx(44.0 * 33.0 * 22.0)
    assert "evaluate.exact_became_mesh" not in {f.code for f in result.scene.report.findings}


def _hollow_box(wall: float = 3.0) -> Solid:
    """Ein exakt ausgehöhlter Kasten in Roberts Maßen — die Wand ist das Thema."""
    from app.core.knowledge.profiles import make_profile
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    project = new_project("centauri-carbon-2", "pla")
    document = project.document
    history = History(document)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 215.0, "depth": 75.0, "height": 215.0}
            )
        ],
    )
    history.apply(
        "Aushöhlen", [OperationDraft(op="shell_exact", inputs=("obj_1",), params={"wall": wall})]
    )
    result = evaluate(
        document, make_profile("centauri-carbon-2", "pla"), sources=ProjectSources(project)
    )
    return next(iter(result.scene.objects.values())).mesh


@pytest.mark.parametrize("radius", [2.0, 2.9, 3.0, 5.0])
def test_a_radius_that_eats_the_wall_is_refused_instead_of_taking_the_process(
    radius: float,
) -> None:
    """Ein zu großer Radius an einer dünnen Wand endet mit einem Satz, nicht mit einem Absturz.

    **Der Fall.** Roberts Filamenthalter, ein auf 3 mm ausgehöhlter Kasten:
    Ein Radius von 3 mm auf den oberen Kanten nahm am 06.09.2026 den ganzen
    Prozess mit — Zugriffsverletzung in ``BRepFilletAPI_MakeFillet::Build``,
    kein Traceback, kein Dialog, die Arbeit weg. Zwischen 2,0 und 2,9 war es
    subtiler: OpenCASCADE meldete Erfolg und lieferte einen Körper, der in
    zwei Solids zerfallen war und acht Prozent mehr Volumen hatte als vorher.

    Gemessen wurde beides an derselben Reihe: 1,2 und 1,4 gehen, ab 2,0 nicht
    mehr, und ab 3,0 mit mehr als einer Kante stürzte es. Geprüft wird hier
    die Absage — dass der Test überhaupt bis zu seiner Zusicherung kommt, ist
    die halbe Aussage.
    """

    with pytest.raises(GeometryError) as raised:
        edit.fillet(_hollow_box(), radius, "top")

    assert raised.value.suggestions, "jede Ausnahme trägt einen Handlungsvorschlag"
    assert "Radius" in str(raised.value.detail)


@pytest.mark.parametrize("with_post", [False, True])
@pytest.mark.parametrize("rounded", [False, True])
@pytest.mark.parametrize("moved", [False, True])
def test_edge_size_uses_its_neighbouring_walls_not_the_remote_plate(
    with_post: bool, rounded: bool, moved: bool
) -> None:
    """Eine dünne Grundplatte begrenzt die Rundung senkrechter Kanten nicht."""
    source = edit.box(100.0, 100.0, 3.0)
    edge_length = 4.0 * 3.0
    if with_post:
        source = edit.boolean(
            "union", [source, edit.moved(edit.box(30.0, 30.0, 20.0), (0.0, 0.0, 3.0))]
        )
        edge_length += 4.0 * 20.0
    choice = "vertical"
    keys = []
    if moved:
        matrix = trimesh.transformations.rotation_matrix(math.radians(31.0), (2.0, 1.0, -3.0))
        matrix[:3, 3] = (103.0, -27.0, 48.0)
        source = edit.transformed(
            source, tuple(tuple(float(value) for value in row) for row in matrix)
        )
        keys = [
            edit.edge_key(edge)
            for edge in edit.edges_of(source)
            if abs(sum(edge.direction[i] * float(matrix[i, 2]) for i in range(3))) >= 1.0 - EPS_GEOM
        ]
        assert len(keys) == (8 if with_post else 4)
        choice = "named"
    original_volume = source.volume
    size = 4.0
    expected_area = size**2 * (1.0 - math.pi / 4.0) if rounded else size**2 / 2.0

    result = (
        edit.fillet(source, size, choice, keys)
        if rounded
        else edit.chamfer(source, size, choice, keys)
    )

    assert result.volume == pytest.approx(original_volume - edge_length * expected_area, abs=1e-6)
    assert result.solid_count == 1
    assert result.to_mesh().is_watertight
    assert source.volume == pytest.approx(original_volume, abs=1e-9)


@pytest.mark.parametrize("radius", [0.8, 1.2, 1.4])
def test_a_radius_that_fits_the_wall_still_works(radius: float) -> None:
    """Und was passt, geht weiter durch — der Schutz sperrt nicht das Übliche."""

    body = _hollow_box()
    turned = edit.fillet(body, radius, "top")

    assert turned.solid_count == 1, "ein Körper bleibt ein Körper"
    assert turned.volume < body.volume, "eine Verrundung an einer Außenkante nimmt Material weg"
    assert turned.volume > body.volume * 0.99, "aber nur wenig"


def test_fillet_stops_if_the_wall_map_cannot_prove_a_safe_radius(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Messfehler darf den nativen Aufruf mit Absturzrisiko nicht freigeben."""
    from app.core.perceive import maps

    def unavailable(_mesh: Mesh) -> None:
        raise RuntimeError("Messkern absichtlich nicht verfügbar")

    monkeypatch.setattr(maps, "wall_thickness_map", unavailable)

    with pytest.raises(GeometryError) as raised:
        edit.fillet(block(), 1.0, "top")

    assert raised.value.suggestions
    assert "Wandstärke" in str(raised.value.detail)
    _the_advice_is_one_the_window_wires(raised.value)


@pytest.mark.parametrize("values", [(), (math.nan, 0.0), (math.inf,)])
def test_fillet_stops_if_the_wall_map_has_no_finite_measurement(
    monkeypatch: pytest.MonkeyPatch,
    values: tuple[float, ...],
) -> None:
    """Leere und unbrauchbare Karten dürfen keine unendliche Freigabe ergeben."""
    from types import SimpleNamespace

    from app.core.perceive import maps

    monkeypatch.setattr(
        maps,
        "wall_thickness_map",
        lambda _mesh: SimpleNamespace(values=values),
    )

    with pytest.raises(GeometryError) as raised:
        edit.fillet(block(), 1.0, "top")

    assert raised.value.suggestions
    assert "Wandstärke" in str(raised.value.detail)
    _the_advice_is_one_the_window_wires(raised.value)


def _the_advice_is_one_the_window_wires(error: GeometryError) -> None:
    """Die unbelegte Wandmessung riet *Erneut versuchen* — ins Leere.

    ``main_window.error_handlers`` verdrahtet ``retry`` nur, solange ein
    gescheitertes Schreiben ansteht (Zweig ``_write_failure``); außerhalb
    dieses Falls führt ``tests/test_ui.py`` die Kennung ausdrücklich in
    ``postponed``, und ``dialogs.unhandled_advice`` macht daraus einen Satz.
    Zu wiederholen gibt es hier ohnehin nichts: Dieselbe Wandkarte über
    demselben Netz scheitert beim zweiten Anlauf identisch (07.09.2026).

    Geprüft werden die Kennungen und nicht die Zahl der Vorschläge — ein
    zweiter Rat wäre in Ordnung, ein unerreichbarer nicht. Nachgesehen wird im
    Fenster hier nicht: ``app/core`` darf Qt nicht importieren (Regel 1), und
    die Handlerliste steht in ``tests/test_ui.py`` unter ihrem eigenen
    Wächter.
    """
    assert {action.id for action in error.suggestions} == {"correct_input", "cancel"}, (
        f"unerreichbarer Rat: {[action.id for action in error.suggestions]}"
    )


def test_fillet_rejects_a_valid_shape_that_contains_two_solids() -> None:
    """BRepCheck prüft Gültigkeit, aber nicht die zugesicherte Körperzahl."""
    from types import SimpleNamespace

    from OCP.BRepCheck import BRepCheck_Analyzer

    source = block()
    second = edit.moved(block(), (100.0, 0.0, 0.0))
    compound = edit.boolean("union", [source, second])
    assert compound.solid_count == 2
    assert BRepCheck_Analyzer(compound.shape).IsValid(), "der Gegenbeweis muss gültig sein"

    builder = SimpleNamespace(
        Build=lambda: None,
        IsDone=lambda: True,
        Shape=lambda: compound.shape,
    )

    with pytest.raises(GeometryError) as raised:
        edit._built(source, builder, "fillet", 1.0, 1)

    assert raised.value.suggestions


def test_the_bolt_stands_where_it_is_put(profile: Profile) -> None:
    """Der Bolzen ist ein Erzeuger wie Quader und Zylinder — mit einer Lage.

    Er verbraucht nichts und erzeugt einen Körper, stand aber als einziger
    Erzeuger des Menüs *Erzeugen* ohne Ort, Richtung und Drehung da; der Griff
    an der Vorschau hängt genau an diesen Feldern und hätte ihn deshalb nicht
    bekommen (Robert, 09.09.2026: „alle Körper, die man über Erzeugen setzen
    kann").

    Drei Lagen, und die erste ist die Gegenprobe: **Ohne Werte steht er, wo er
    vorher stand** — vom Ursprung nach oben, wie es sein ``doc``-Satz sagt.
    Eine Platzierung, die bei Vorgabewerten etwas verschiebt, änderte
    stillschweigend jedes bestehende Projekt.
    """
    ruhend = run("thread_exact", None, profile, diameter=10.0, pitch=1.5, length=12.0)
    ruhe = ruhend.outputs[0].mesh.bounds

    assert ruhe.minimum[2] == pytest.approx(0.0, abs=1e-6), "er wächst vom Bett nach oben"
    mitte_x = (ruhe.minimum[0] + ruhe.maximum[0]) / 2.0
    mitte_y = (ruhe.minimum[1] + ruhe.maximum[1]) / 2.0
    assert (mitte_x, mitte_y) == pytest.approx((0.0, 0.0), abs=1e-6), "und über dem Ursprung"

    # Ein Ort verschiebt ihn und lässt ihn, was er ist.
    versetzt = run(
        "thread_exact", None, profile, diameter=10.0, pitch=1.5, length=12.0, x=20.0, y=5.0
    )
    weit = versetzt.outputs[0].mesh.bounds
    assert (weit.minimum[0] - ruhe.minimum[0]) == pytest.approx(20.0, abs=1e-6)
    assert (weit.minimum[1] - ruhe.minimum[1]) == pytest.approx(5.0, abs=1e-6)
    assert versetzt.outputs[0].mesh.volume == pytest.approx(
        ruhend.outputs[0].mesh.volume, rel=1e-9
    ), "verschoben ist derselbe Bolzen"

    # Und eine Richtung legt ihn hin: Was hoch war, ist jetzt lang.
    gelegt = run(
        "thread_exact", None, profile, diameter=10.0, pitch=1.5, length=12.0, nx=1.0, nz=0.0
    )
    liegend = gelegt.outputs[0].mesh.bounds
    hoch = ruhe.maximum[2] - ruhe.minimum[2]
    lang = liegend.maximum[0] - liegend.minimum[0]
    assert lang == pytest.approx(hoch, abs=1e-6), f"liegend {lang} statt stehend {hoch}"
    assert (liegend.maximum[2] - liegend.minimum[2]) == pytest.approx(
        ruhe.maximum[0] - ruhe.minimum[0], abs=1e-6
    ), "und was lang war, ist jetzt hoch"


def test_the_thread_feature_moves_with_the_bolt(profile: Profile) -> None:
    """Das benannte Gewinde beschreibt dieselbe Lage wie sein Körper.

    Mitte und Achse gingen als **feste Zahlen** ins Merkmal — ``(0, 0,
    length/2)`` und ``(0, 0, 1)``. Das war richtig, solange der Bolzen immer im
    Ursprung stand und nach oben zeigte, und wurde mit der Platzierung
    (09.09.2026) still falsch: Seine Dreiecke wanderten, die beiden Zahlen
    nicht. Das Gewinde benannte damit eine Achse, an der nichts liegt, und eine
    Passung oder eine Mutter dagegen zielte ins Leere.

    Der Test daneben (``test_the_bolt_stands_where_it_is_put``) hätte das nie
    gefangen: Er misst den Hüllquader, und der wandert ja.
    """
    versetzt = run(
        "thread_exact", None, profile, diameter=10.0, pitch=1.5, length=12.0, x=20.0, y=5.0
    )
    gewinde = versetzt.outputs[0].features["thread_1"]
    assert gewinde.params["centre"] == pytest.approx((20.0, 5.0, 6.0), abs=1e-6)
    assert gewinde.params["axis"] == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)

    # Und eine Richtung dreht die Achse mit, nicht nur die Dreiecke.
    gelegt = run(
        "thread_exact", None, profile, diameter=10.0, pitch=1.5, length=12.0, nx=1.0, nz=0.0
    )
    liegend = gelegt.outputs[0].features["thread_1"]
    assert liegend.params["axis"] == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)
    assert liegend.params["centre"] == pytest.approx((6.0, 0.0, 0.0), abs=1e-6)


# --- Ein Langloch ist auch exakt ein Merkmal ------------------------------------


def a_slotted_block(length: float = 20.0, angle: float = 0.0, depth: float = 10.0) -> Solid:
    """Eine exakte Platte 90 × 60 × 10 mit einem von oben offenen Langloch Ø6."""
    return edit.slot_bore(
        edit.box(90.0, 60.0, 10.0),
        position=(0.0, 0.0, 10.0 - depth / 2.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=depth,
        length=length,
        angle_deg=angle,
        overlap=0.1,
    )


def kinds_of(solid: Solid) -> dict[str, int]:
    counted: dict[str, int] = {}
    for feature in features_of(solid).values():
        counted[feature.kind] = counted.get(feature.kind, 0) + 1
    return counted


def test_an_exact_slot_is_one_feature_and_not_two_fillets() -> None:
    """Der Anlass, und er ist derselbe wie am Netz — nur zwei Wochen später.

    :mod:`app.core.perceive.slots` setzt seit dem 10.09.2026 zwei Halbzylinder
    zu einem Langloch zusammen. Der exakte Kern tat es nicht: Er beschreibt
    jede Topologiefläche für sich, und ein Langloch hat vier. Im Objektbaum
    standen ``fillet_1`` und ``fillet_2``, wo eine Öffnung ist, dazu zwei
    Wände — und die Handlungen eines Langlochs standen an keiner von ihnen
    (Robert, 11.09.2026: „auf einem langloch 2 werden und nicht mehr
    wählbar").

    **Gemessen wird bis zum Maß**, nicht nur bis zur Art: Ein Merkmal, das
    „Langloch" heißt und die falsche Länge trägt, ist im Dialog dasselbe
    Ärgernis wie gar keines.
    """
    solid = a_slotted_block()

    found = features_of(solid)
    slots = [feature for feature in found.values() if feature.kind == "slot"]

    assert len(slots) == 1, f"genau ein Langloch, gefunden: {kinds_of(solid)}"
    slot = slots[0]
    assert float(slot.params["length"]) == pytest.approx(20.1, abs=0.05)
    assert float(slot.params["diameter"]) == pytest.approx(6.1, abs=0.05)
    assert slot.params["centre"] == pytest.approx((0.0, 0.0, 5.0), abs=0.01)
    assert slot.params["through"], "das Loch geht durch die Platte"
    assert "fillet" not in kinds_of(solid), "die zwei Bögen gehen im Langloch auf"
    assert len(slot.face_indices) > 0, "und es ist im Bild anklickbar"


@pytest.mark.parametrize("angle", [0.0, 35.0, 90.0, -60.0])
def test_an_exact_slot_knows_which_way_it_lies(angle: float) -> None:
    """Die Richtung kommt aus der Topologie und nicht aus einer Einpassung."""
    solid = a_slotted_block(length=26.0, angle=angle)

    slot = next(feature for feature in features_of(solid).values() if feature.kind == "slot")

    direction = slot.params["direction"]
    measured = math.degrees(math.atan2(direction[1], direction[0]))
    # Ein Langloch hat keine Vorzugsrichtung: 35 Grad und 215 sind dieselbe Lage.
    assert min(abs(measured - angle), abs(abs(measured - angle) - 180.0)) < 0.5


@pytest.mark.parametrize("representation", ["brep", "mesh"])
def test_a_blind_exact_slot_says_it_does_not_go_through(representation: str) -> None:
    """Ein Sacklangloch behält seinen Boden als eigene Fläche.

    Dieselbe Entscheidung wie am Netz: Die zwei Flanken gehen im Langloch auf,
    der Boden nicht — seine Normale zeigt entlang der Achse, er liegt gar
    nicht im Mantel.
    """
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_OUT

    solid = a_slotted_block(depth=4.0)
    assert BRepCheck_Analyzer(solid.shape).IsValid()
    assert solid.solid_count == 1
    assert solid.volume == pytest.approx(54000.0 - (6.1 * 14.0 + math.pi * 3.05**2) * 4.0)
    # Die Mündung reicht bis Z=10, der Boden liegt bei Z=6. Eine bloß
    # kleinere Tiefe könnte ebenso einen vollständig geschlossenen Einschluss bauen.
    classifier = BRepClass3d_SolidClassifier(solid.shape)
    for z, expected in ((5.0, TopAbs_IN), (9.0, TopAbs_OUT)):
        classifier.Perform(gp_Pnt(0.0, 0.0, z), EPS_GEOM)
        assert classifier.State() == expected

    found = features_of(solid) if representation == "brep" else detect(as_mesh_data(solid))
    slot = next(feature for feature in found.values() if feature.kind == "slot")

    assert not slot.params["through"], "die Platte ist 10 mm dick, das Loch 4"
    assert float(slot.params["depth"]) == pytest.approx(4.0, abs=EPS_GEOM)
    assert slot.params["centre"] == pytest.approx((0.0, 0.0, 8.0), abs=EPS_GEOM)
    assert not any(feature.kind == "void" for feature in found.values())
    floor = next(
        feature
        for feature in found.values()
        if feature.kind == "face" and abs(feature.params["centre"][2] - 6.0) < EPS_GEOM
    )
    assert set(floor.face_indices).isdisjoint(slot.face_indices)


def test_two_exact_slots_stay_two() -> None:
    """Zwei Langlöcher nebeneinander werden nicht zu einem — und nicht zu vier."""
    solid = edit.box(90.0, 60.0, 10.0)
    for x in (-20.0, 20.0):
        solid = edit.slot_bore(
            solid,
            position=(x, 0.0, 5.0),
            direction=(0.0, 0.0, 1.0),
            diameter=6.0,
            depth=10.0,
            length=16.0,
            angle_deg=0.0,
            overlap=0.1,
        )

    assert kinds_of(solid).get("slot") == 2, kinds_of(solid)


def test_rounded_corners_of_a_pocket_are_not_an_exact_slot() -> None:
    """Die härteste Gegenprobe: vier Innenverrundungen, über Wände verbunden.

    Zwei gleich große Verrundungen mit paralleler Achse gibt es an jeder
    verrundeten Ecke; was ein Langloch daraus macht, ist der geschlossene
    Mantel. Zwei benachbarte Ecken einer Tasche teilen **eine** Wand, nicht
    zwei — und daran scheidet es sich.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec

    tool = edit.fillet(edit.box(40.0, 24.0, 8.0), 6.0, "vertical")
    lift = gp_Trsf()
    lift.SetTranslation(gp_Vec(0.0, 0.0, 16.0))
    raised = tool.replacing(BRepBuilderAPI_Transform(tool.shape, lift, True).Shape())
    pocket = edit.boolean("difference", [edit.box(90.0, 60.0, 20.0), raised])

    counted = kinds_of(pocket)

    assert "slot" not in counted, f"eine Tasche ist kein Langloch: {counted}"
    assert counted.get("fillet") == 4, f"ihre vier Ecken bleiben Verrundungen: {counted}"


def test_a_rounded_box_keeps_its_fillets() -> None:
    """Und ein rundum verrundeter Quader behält seine zwanzig Verrundungen.

    Die Achsen der zwölf Kantenverrundungen sind paarweise parallel und gleich
    groß — genau die Bedingung, die ein Langloch auch erfüllt. Was sie trennt,
    ist ``recess``: Bei einer Kantenverrundung liegt die Achse **im** Material.
    """
    rounded = edit.fillet(edit.box(40.0, 30.0, 20.0), 4.0, "all")

    counted = kinds_of(rounded)

    assert "slot" not in counted, f"kein Langloch an einem Quader: {counted}"
    assert counted.get("fillet") == 20, counted


# --- Die Achse trägt an beiden Kernen dasselbe Vorzeichen ------------------------


def test_an_exact_bore_from_below_carries_the_same_axis_as_the_mesh() -> None:
    """Das Vorzeichen der Achse entscheidet ``units.positive_axis``, nicht der Erzeuger.

    Der exakte Kern gab die Achse so zurück, wie OpenCASCADE die Fläche gebaut
    hatte: eine Bohrung von unten trug minus Z. Am Netz normiert
    ``fit_cylinder`` seit je auf „erste größte Komponente positiv" — und gegen
    den Rahmen dieser Achse zählt der Winkel eines Langlochs. Gemessen
    11.09.2026: 45 Grad an derselben Bohrung ergaben am Netz 45 und am exakten
    Körper 135 (Fund des Reviews).
    """
    from_below = edit.cut_bore(
        edit.box(90.0, 60.0, 10.0),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, -1.0),
        diameter=6.0,
        depth=10.0,
    )

    hole = next(feature for feature in features_of(from_below).values() if feature.kind == "hole")

    assert hole.params["axis"] == pytest.approx((0.0, 0.0, 1.0), abs=1e-9)


def test_an_exact_slot_keeps_the_axis_of_its_bore() -> None:
    """Nach *Zum Langloch ziehen* stand die Achse auf minus Z — und das Feld
    *Richtung* zeigte minus 45, wo 45 eingetragen war. Wer dieselbe 45 noch
    einmal eintrug, bekam ein Kreuz (gemessen 11.09.2026, Fund des Reviews).
    """
    slot = next(
        feature
        for feature in features_of(a_slotted_block(angle=45.0)).values()
        if feature.kind == "slot"
    )

    assert slot.params["axis"] == pytest.approx((0.0, 0.0, 1.0), abs=1e-9)
    # Und die Richtung folgt derselben Regel — die erste größte Komponente
    # ist positiv, gleich in welcher Reihenfolge die zwei Bögen gefunden wurden.
    direction = slot.params["direction"]
    assert direction[0] > 0.0, direction
    assert math.degrees(math.atan2(direction[1], direction[0])) == pytest.approx(45.0, abs=0.5)


def test_the_exact_drill_makes_a_slot_through_the_operation(profile: Profile) -> None:
    """Der Zweig ``slotted=True`` von ``drill_brep_hole`` — über das Register gefahren.

    Bis zum 11.09.2026 war er nur über den direkten Import von ``_slotted_bore``
    belegt; die Operation selbst und ihre Kantenschleife lief kein Test
    (Übergabe der Durchsicht vom 11.09.2026).
    """
    body = run("create_brep_box", None, profile, width=90.0, depth=60.0, height=10.0).outputs[0]
    low, high = body.mesh.bounds.minimum, body.mesh.bounds.maximum
    middle = ((low[0] + high[0]) / 2.0, (low[1] + high[1]) / 2.0)

    result = run(
        "drill_brep_hole",
        body,
        profile,
        diameter=6.0,
        x=middle[0],
        y=middle[1],
        z=float(high[2]),
        axis="z",
        anchor="mouth",
        depth=0.0,
        compensate=False,
        slotted=True,
        slot_length=20.0,
        slot_angle=30.0,
    )

    slots = [feature for feature in result.outputs[0].features.values() if feature.kind == "slot"]
    assert len(slots) == 1, kinds_of(result.outputs[0].mesh)
    assert float(slots[0].params["length"]) == pytest.approx(20.0, abs=0.05)
    direction = slots[0].params["direction"]
    measured = math.degrees(math.atan2(direction[1], direction[0])) % 180.0
    assert measured == pytest.approx(30.0, abs=0.5)
    assert "bore.over_the_edge" not in {finding.code for finding in result.findings}


def test_a_bore_moves_into_the_middle_of_the_part(profile: Profile) -> None:
    """Drei Nullen sind eine Stelle und keine Absage (RM-154).

    ``x/y/z`` lasen sich als „lass das Loch, wo es ist", sobald alle drei null
    waren. Damit ließ es sich in jede Stelle versetzen **außer** in den
    Ursprung — und Solidon legt einen Quader um den Ursprung, an einer mittig
    gelegten Platte ist (0 | 0 | 0) also die Mitte des Teils und kein Randfall.

    Seit die Felder ``optional`` tragen, steht „nicht gesagt" als ``None`` da,
    und die Null bedeutet wieder, was sie sagt. Gemessen wird an der Lage der
    Bohrung, nicht am Volumen: Das bleibt beim Versetzen gleich, und genau
    daran ist der Fehler zwei Wochen lang vorbeigegangen.
    """
    original = edit.bore(block(), position=(12.0, 8.0, HEIGHT), axis="z", diameter=6.0)
    features = features_of(original)
    bore = next(entry for entry in features.values() if entry.kind == "hole")
    source = SceneObject(id="obj_1", name="Block", mesh=original, kind="brep", features=features)

    moved = run(
        "resize_hole",
        source,
        profile,
        at_feature=bore.id,
        diameter=6.0,
        x=0.0,
        y=0.0,
        z=0.0,
    ).outputs[0]

    holes = [entry for entry in moved.features.values() if entry.kind == "hole"]
    assert len(holes) == 1, f"ein Loch erwartet, gefunden: {len(holes)}"
    centre = holes[0].params["centre"]
    assert abs(float(centre[0])) < 0.05 and abs(float(centre[1])) < 0.05, (
        f"das Loch steht bei {centre} und nicht in der Mitte"
    )


def test_a_bore_that_names_no_place_stays_where_it_is(profile: Profile) -> None:
    """Die Gegenrichtung derselben Zusage: Wer nichts sagt, versetzt nichts.

    Über Chat und Kommandozeile nennt niemand eine Stelle, und dort wäre der
    Ursprung die falsche Antwort — ohne diese Hälfte wanderte jede Bohrung in
    die Mitte, sobald jemand nur ihren Durchmesser ändert.
    """
    original = edit.bore(block(), position=(12.0, 8.0, HEIGHT), axis="z", diameter=6.0)
    features = features_of(original)
    bore = next(entry for entry in features.values() if entry.kind == "hole")
    source = SceneObject(id="obj_1", name="Block", mesh=original, kind="brep", features=features)

    changed = run("resize_hole", source, profile, at_feature=bore.id, diameter=9.0).outputs[0]

    holes = [entry for entry in changed.features.values() if entry.kind == "hole"]
    centre = holes[0].params["centre"]
    assert abs(float(centre[0]) - 12.0) < 0.05 and abs(float(centre[1]) - 8.0) < 0.05, (
        f"das Loch ist nach {centre} gewandert, ohne dass jemand eine Stelle nannte"
    )
    assert holes[0].params["diameter"] == pytest.approx(9.0, abs=0.05)


def test_an_exact_slot_gets_wider_and_keeps_its_travel(profile: Profile) -> None:
    """Dieselbe Zusage wie am Netz, am exakten Körper (RM-156).

    „Zwischen den beiden soll es keinen Unterschied geben bei gar nichts"
    (Robert, 10.09.2026) — also wird hier dasselbe gemessen: Ø 6 auf 20 wird zu
    Ø 8 auf 22, der Weg bleibt, und die Kennung geht nicht verloren.
    """
    original = a_slotted_block(length=20.0)
    features = features_of(original)
    slot = next(entry for entry in features.values() if entry.kind == "slot")
    travel = float(slot.params["length"]) - float(slot.params["diameter"])
    source = SceneObject(id="obj_1", name="Platte", mesh=original, kind="brep", features=features)

    wider = run("resize_hole", source, profile, at_feature=slot.id, diameter=8.0).outputs[0]

    assert wider.kind == "brep", "der exakte Körper bleibt exakt"
    slots = [entry for entry in wider.features.values() if entry.kind == "slot"]
    assert len(slots) == 1, f"ein Langloch erwartet: {[e.kind for e in wider.features.values()]}"
    assert slots[0].id == slot.id, "die Kennung bleibt"
    assert float(slots[0].params["diameter"]) == pytest.approx(8.0, abs=0.15)
    assert float(slots[0].params["length"]) - float(slots[0].params["diameter"]) == pytest.approx(
        travel, abs=0.15
    ), "der Verschiebeweg bleibt"


# --- Eine Drehung nimmt die Merkmale mit, an beiden Kernen -----------------------


def _turned_about_x(
    point: tuple[float, float, float], pivot: tuple[float, float, float], angle: float
) -> tuple[float, float, float]:
    """Der Sollwert, von Hand gerechnet: Drehung um eine Achse parallel zu X.

    Bewusst ohne ``app.core`` — weder ``geom.transform.rotation`` noch
    ``perceive.matching.moved_features``, denn beide sind Teil dessen, was hier
    gemessen wird. Drei Zeilen Schulgeometrie sind der unabhängige Vergleich.
    """
    radians = math.radians(angle)
    along_y = point[1] - pivot[1]
    along_z = point[2] - pivot[2]
    return (
        point[0],
        pivot[1] + along_y * math.cos(radians) - along_z * math.sin(radians),
        pivot[2] + along_y * math.sin(radians) + along_z * math.cos(radians),
    )


@pytest.mark.parametrize("creator", ["create_box", "create_brep_box"])
def test_a_turned_body_carries_its_top_face_along(creator: str, profile: Profile) -> None:
    """Nach *Drehen* sitzt die Deckfläche dort, wo der Körper sie hingedreht hat.

    **Am exakten Körper tat sie das nicht** (gemessen 17.09.2026). Die
    Merkmalserkennung in ``scene.evaluate`` misst an Dreiecken und sprang
    deshalb über jeden ``Solid`` hinweg — auch dort, wo die Operation eine
    starre Matrix gemeldet hatte. Der Hüllquader wanderte korrekt von z -11,83
    bis 21,83, die Deckfläche stand weiter mit Normale (0, 0, 1) bei z = 10.

    Der Kunde merkt es an der Skizze: ``sketch.planes`` baut den Skizzenrahmen
    aus ``normal`` und ``centre`` dieser Merkmale, und ein Zapfen auf der
    Deckfläche einer um 30 Grad gekippten Platte landete unter dem Bett.

    Gefahren wird beides, weil der Netz-Zwilling die Gegenprobe ist: Er war
    richtig, und er soll es bleiben.
    """
    angle = 30.0
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Platte",
        [OperationDraft(op=creator, params={"width": 50.0, "depth": 50.0, "height": 10.0})],
    )

    # Erst die Lage vor der Drehung messen: welches Merkmal die Deckfläche ist,
    # wo sie sitzt, und um welchen Punkt „Mitte" dreht. Nichts davon wird
    # angenommen — der Sollwert unten entsteht aus diesen Messwerten.
    flat = evaluate(project.document, profile, sources=ProjectSources(project)).scene.objects[
        "obj_1"
    ]
    upward = [
        name
        for name, feature in flat.features.items()
        if feature.kind == "face" and feature.params["normal"][2] > 1.0 - EPS_GEOM
    ]
    assert len(upward) == 1, f"eine Deckfläche erwartet: {sorted(flat.features)}"
    top = upward[0]
    centre_before = tuple(float(value) for value in flat.features[top].params["centre"])
    pivot = tuple(float(value) for value in flat.mesh.bounds.centre)

    history.apply(
        "Kippen",
        [
            OperationDraft(
                op="rotate_object",
                inputs=("obj_1",),
                outputs=("obj_1",),
                params={"axis": "x", "angle": angle, "about": "centre", "keep_on_bed": False},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    turned = result.scene.objects["obj_1"]

    assert result.stopped_at is None, "die Kette läuft durch"
    assert turned.kind == ("brep" if creator == "create_brep_box" else "mesh")
    assert top in turned.features, f"der Name bleibt: {sorted(turned.features)}"
    face = turned.features[top]
    # Die Normale dreht ohne Drehpunkt, der Mittelpunkt um die Mitte des
    # Körpers: (0, -sin 30, cos 30) und (0, -2,5, 9,330) bei dieser Platte.
    assert face.params["normal"] == pytest.approx(
        _turned_about_x((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), angle), abs=1e-6
    )
    assert face.params["centre"] == pytest.approx(
        _turned_about_x(centre_before, pivot, angle), abs=1e-6
    )


@pytest.mark.parametrize("work", ["fillet", "chamfer"])
def test_fillet_and_chamfer_ask_for_cancellation_while_they_work(work: str) -> None:
    """Verrunden und Fase fragen den Abbruch — an Wandkarte, Kanten, Bau und Prüfung.

    Bis zum 22.09.2026 nahmen ``edit.fillet`` und ``edit.chamfer`` keinen
    Token an: Wandkarte, Kantenwahl, der native Bau und die Prüfung danach
    liefen durch, und *Abbrechen* griff erst in der Erkennung am fertigen
    Körper. An jeder Stelle abgebrochen, bleibt der Eingang, wie er war.
    """
    from app.core.errors import OperationCancelled

    operation = edit.fillet if work == "fillet" else edit.chamfer
    source = block()
    volume = source.volume
    counting = CountingToken(limit=None)
    done = operation(source, 1.0, "top", cancelled=counting)
    assert done.solid_count == 1 and done.volume < volume
    asked = counting.calls
    assert asked >= 8, asked
    for limit in sorted({1, 2, asked // 2, asked - 1, asked}):
        early = CountingToken(limit=limit)
        with pytest.raises(OperationCancelled):
            operation(source, 1.0, "top", cancelled=early)
        assert early.calls == limit
    assert source.volume == pytest.approx(volume, abs=EPS_GEOM)


def _bezier_prism_face() -> tuple[Any, float]:
    """Eine ebene Fläche unter einem kubischen Bogen, mit ihrer Fläche aus Green.

    Der Bogen läuft von (0, 0) über die Pole (3, 6) und (7, 6) nach (10, 0),
    die Sehne schließt. ½∮(x dy − y dx) ist für das Polynom mit acht
    Gauß-Legendre-Knoten exakt; die Sehne auf der x-Achse trägt nichts.
    """
    import numpy as np
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.collections import Array1_gp_Pnt
    from OCP.Geom import Geom_BezierCurve
    from OCP.gp import gp_Pnt

    poles = [(0.0, 0.0), (3.0, 6.0), (7.0, 6.0), (10.0, 0.0)]
    array = Array1_gp_Pnt(1, 4)
    for number, (x, y) in enumerate(poles, start=1):
        array.SetValue(number, gp_Pnt(x, y, 0.0))
    wire = BRepBuilderAPI_MakeWire(
        BRepBuilderAPI_MakeEdge(Geom_BezierCurve(array)).Edge(),
        BRepBuilderAPI_MakeEdge(gp_Pnt(10.0, 0.0, 0.0), gp_Pnt(0.0, 0.0, 0.0)).Edge(),
    ).Wire()
    face = BRepBuilderAPI_MakeFace(wire, True).Face()
    points = np.asarray(poles)
    nodes, weights = np.polynomial.legendre.leggauss(8)
    area = 0.0
    for node, weight in zip(nodes, weights, strict=True):
        t = (node + 1.0) / 2.0
        basis = np.asarray([(1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t**2 * (1 - t), t**3])
        slope = np.asarray([(1 - t) ** 2, 2 * t * (1 - t), t**2])
        x, y = basis @ points
        dx, dy = slope @ (3.0 * np.diff(points, axis=0))
        area += 0.25 * (x * dy - y * dx) * weight
    return face, abs(area)


@pytest.mark.parametrize("sweep", ["extrusion", "revolution"])
def test_the_integration_ladder_splits_swept_faces_completely(sweep: str) -> None:
    """Die Teilung einer Extrusion und einer Drehfläche deckt ihre ganze Fläche (Leiter).

    ``ShapeUpgrade_SplitSurface`` schnitt eine Extrusion nicht in der Richtung
    ihrer Basiskurve und eine Drehfläche nicht in der ihres Profils; die
    Teilung deckte die Hälfte, dann ein Viertel, die Leiter kam nie zusammen,
    und jedes Volumen eines Körpers mit solchen Flächen fiel in den
    Python-Rückfall — erhabene Schrift auf einem Quader 75 s (22.09.2026).
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
    from OCP.collections import Array1_gp_Pnt
    from OCP.Geom import Geom_BezierCurve
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Vec
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from app.core.brep import properties

    def area(shape: Any) -> float:
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(shape, props)
        return float(props.Mass())

    array = Array1_gp_Pnt(1, 4)
    for number, (x, z) in enumerate([(5.0, 0.0), (8.0, 3.0), (4.0, 6.0), (6.0, 9.0)], start=1):
        array.SetValue(number, gp_Pnt(x, 0.0, z))
    edge = BRepBuilderAPI_MakeEdge(Geom_BezierCurve(array)).Edge()
    swept = (
        BRepPrimAPI_MakePrism(edge, gp_Vec(0.0, 7.0, 0.0)).Shape()
        if sweep == "extrusion"
        else BRepPrimAPI_MakeRevol(edge, gp_Ax1(gp_Pnt(), gp_Dir(0.0, 0.0, 1.0)), 2.0).Shape()
    )
    face = TopoDS.Face(TopExp_Explorer(swept, TopAbs_FACE).Current())
    whole = area(face)
    for subdivisions in (1, 2, 4):
        patches = properties._patches(face, subdivisions)
        assert len(patches) == subdivisions**2
        assert sum(area(patch) for patch in patches) == pytest.approx(whole, rel=1e-9)

    if sweep == "extrusion":
        base, expected = _bezier_prism_face()
        prism = BRepPrimAPI_MakePrism(base, gp_Vec(0.0, 0.0, 3.0)).Shape()
        measured = properties._spanned_volume(prism)
        assert measured.mass == pytest.approx(3.0 * expected, rel=1e-9)


def _box_with_an_open_trim(gap: float) -> Any:
    """Ein Quader 30 × 20 × 10 aus Spline-Flächen, an dem eine Fläche ihren
    Parameterrand nicht schließt: Die Randkurve einer Kante liegt um ``gap``
    neben ihren Nachbarn, die Kante trägt die Toleranz dafür — wie Fläche 0
    der Lochplatte ``pegboard-gs-100-v2.step`` (Lücke 5,7·10⁻⁴ im Parameter,
    9,7·10⁻⁴ mm im Raum).
    """
    from OCP.BRep import BRep_Builder, BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt, gp_Vec2d
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    box = BRepPrimAPI_MakeBox(gp_Pnt(3.0, 4.0, 5.0), 30.0, 20.0, 10.0).Shape()
    shape = BRepBuilderAPI_NurbsConvert(box, True).Shape()
    face = TopoDS.Face(TopExp_Explorer(shape, TopAbs_FACE).Current())
    edge = TopoDS.Edge(TopExp_Explorer(face, TopAbs_EDGE).Current())
    trim = BRep_Tool.CurveOnSurface_s(edge, face, 0.0, 0.0)
    BRep_Builder().UpdateEdge(
        edge, trim.Translated(gp_Vec2d(0.0, gap)), face, max(BRep_Tool.Tolerance_s(edge), gap)
    )
    return shape


def test_only_the_face_that_breaks_the_ladder_takes_the_slow_integral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine Fläche, deren Parameterrand nicht schließt, bringt die native Leiter
    nicht zusammen: Jede Teilung schließt die Lücke anders, und das Gebiet
    wandert mit der Stufe. Bis zur Durchsicht 0.5.1 fiel dann das Volumen des
    **ganzen** Körpers in den Python-Rückfall — an der Lochplatte
    ``pegboard-gs-100-v2.step`` 33 s nach dem Laden und nach jedem Schritt,
    für eine einzige von 49 Flächen (die übrigen 48 einigten sich auf 10⁻¹¹).

    Jetzt integriert nur diese eine Fläche entlang ihrer Randkurven; die
    übrigen behalten ihre native Leiter, und die Zusage des Volumens bleibt
    dieselbe: Rechenfehler und Uneinigkeit der Stufen zusammen unter
    ``INTEGRAL_RELATIVE_ERROR``. Gegenprobe ist der Rückfall über alle Flächen.
    """
    from app.core.brep import properties

    shape = _box_with_an_open_trim(1e-3)
    with pytest.raises(GeometryError):
        # Der Fall muss bestehen: Kommt die Leiter zusammen, wäre der Test keiner.
        properties._spanned_volume(shape)
    slow = properties._uv_volume(shape)

    integrated: list[Any] = []
    original = properties._uv_moments

    def counted(face: Any, *args: Any, **kwargs: Any) -> Any:
        integrated.append(face)
        return original(face, *args, **kwargs)

    monkeypatch.setattr(properties, "_uv_moments", counted)
    measured = properties.properties(shape, "volume")
    assert len(integrated) == 1
    assert measured.mass == pytest.approx(6000.0, rel=properties.INTEGRAL_RELATIVE_ERROR)
    assert measured.mass == pytest.approx(slow.mass, rel=properties.INTEGRAL_RELATIVE_ERROR)
    assert measured.centre == pytest.approx((18.0, 14.0, 10.0), abs=1e-6)


def test_fusing_touching_solids_removes_the_shared_face_and_keeps_filament_slots() -> None:
    """Das Entfernen einer Kontaktfläche behält die Farben der Außenflächen."""
    from collections import Counter

    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    lower = edit.box(40.0, 20.0, 10.0)
    lower = Solid(lower.shape, face_slots=(1,) * lower.face_count)
    upper = edit.moved(edit.box(40.0, 20.0, 10.0), (0.0, 0.0, 10.0))
    upper = Solid(upper.shape, face_slots=(2,) * upper.face_count)
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    builder.Add(compound, lower.shape)
    builder.Add(compound, upper.shape)
    source = Solid(
        compound,
        face_slots=(1,) * lower.face_count + (2,) * upper.face_count,
    )

    result = edit.fuse_solids(source)

    assert source.solid_count == 2
    assert result.solid_count == 1
    assert result.volume == pytest.approx(16_000.0)
    assert Counter(result.face_slots) == {1: 5, 2: 5}
