"""Exakte Körper besitzen ihre Form; Folgearbeit verändert keinen Eingabezustand."""

from __future__ import annotations

import importlib
from dataclasses import replace
from typing import Any

import numpy as np
import pytest

from app.core.brep import edit, profiles
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, available, tessellate
from app.core.units import EPS_GEOM

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")


def _triangulations(solid: Solid) -> tuple[tuple[int, int], ...]:
    """Die native Vernetzung jeder Eingabefläche, ohne selbst zu vernetzen."""
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location

    result = []
    for face in solid.faces():
        triangulation = BRep_Tool.Triangulation_s(face, TopLoc_Location())
        result.append(
            (0, 0)
            if triangulation is None
            else (triangulation.NbNodes(), triangulation.NbTriangles())
        )
    return tuple(result)


def test_a_solid_owns_a_copy_of_the_supplied_shape() -> None:
    """Eine nachträglich versetzte fremde Shape kann den Solid nicht verschieben."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Trsf, gp_Vec
    from OCP.TopLoc import TopLoc_Location

    original = BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape()
    solid = Solid(original)
    assert not solid.shape.IsPartner(original)
    shift = gp_Trsf()
    shift.SetTranslation(gp_Vec(7.123456789, -3.0, 2.0))
    original.Move(TopLoc_Location(shift))
    assert solid.bounds.minimum == pytest.approx((0.0, 0.0, 0.0), abs=EPS_GEOM, rel=0.0)
    assert solid.bounds.maximum == pytest.approx((10.0, 20.0, 30.0), abs=EPS_GEOM, rel=0.0)


def test_a_second_quality_wrapper_does_not_share_native_faces() -> None:
    """Der bestehende Weg brep_to_mesh darf nicht denselben TShape weiterreichen."""
    original = edit.cylinder(12.0, 8.0)
    other = Solid(original.shape, deflection=0.01)
    assert not other.shape.IsPartner(original.shape)
    assert all(
        not first.IsPartner(second) for first in original.faces() for second in other.faces()
    )
    assert other.bounds.minimum == pytest.approx(original.bounds.minimum, abs=EPS_GEOM, rel=0.0)
    assert other.bounds.maximum == pytest.approx(original.bounds.maximum, abs=EPS_GEOM, rel=0.0)


def test_moving_a_solid_keeps_precise_location_and_separate_ownership() -> None:
    """Die Lage wird einmal kopiert, ohne Rundung oder Änderung des Originals."""
    original = edit.box(10.0, 8.0, 6.0)
    offset = (7.123456789, -3.23456789, 2.3456789)
    moved = edit.moved(original, offset)
    assert not moved.shape.IsPartner(original.shape)
    assert original.bounds.minimum == pytest.approx((-5.0, -4.0, 0.0), abs=EPS_GEOM, rel=0.0)
    assert moved.bounds.minimum == pytest.approx(
        tuple(low + shift for low, shift in zip((-5.0, -4.0, 0.0), offset, strict=True)),
        abs=EPS_GEOM,
        rel=0.0,
    )
    assert moved.volume == pytest.approx(480.0, abs=EPS_GEOM, rel=0.0)


def test_replacing_quality_never_inherits_a_mesh_or_property_cache() -> None:
    """Auch dataclasses.replace erzeugt eine neue Form mit eigenem, kaltem Cache."""
    original = edit.cylinder(12.0, 8.0)
    original.to_mesh()
    assert original.volume > 0.0
    assert original._cache
    finer = replace(original, deflection=0.01)
    assert not finer._cache
    assert finer._cache is not original._cache
    assert not finer.shape.IsPartner(original.shape)


def test_tessellation_never_populates_the_original_faces() -> None:
    """Auch zwei aufeinanderfolgende Feinheiten arbeiten nur an privaten Formen."""
    solid = edit.cylinder(12.0, 8.0)
    before = _triangulations(solid)
    assert all(entry == (0, 0) for entry in before)
    coarse = tessellate(solid.shape, 0.5)
    fine = tessellate(solid.shape, 0.01)
    assert fine.triangle_count > coarse.triangle_count
    assert _triangulations(solid) == before
    assert solid.bounds.size == pytest.approx((12.0, 12.0, 8.0), abs=EPS_GEOM, rel=0.0)


def test_private_tessellation_keeps_original_face_indices() -> None:
    """Eine versetzte Bohrung färbt genau ihren echten Mantel und keine Nachbarwand."""
    solid = edit.bore(
        edit.box(20.0, 16.0, 8.0),
        position=(3.123456789, 1.23456789, 8.0),
        axis="z",
        diameter=4.0,
    )
    found = features_of(solid)
    hole = next(feature for feature in found.values() if feature.kind == "hole")
    assert hole.face_indices
    corners = solid.raw.triangles[list(hole.face_indices)]
    radial = np.linalg.norm(corners[:, :, :2] - np.array([3.123456789, 1.23456789]), axis=2)
    assert radial == pytest.approx(2.0, abs=EPS_GEOM, rel=0.0)
    groups = [set(solid.triangles_of_face(index)) for index in range(solid.face_count)]
    assert set.union(*groups) == set(range(solid.triangle_count))
    assert sum(map(len, groups)) == solid.triangle_count
    assert all(entry == (0, 0) for entry in _triangulations(solid))


@pytest.mark.parametrize("kind", ["union", "difference", "intersection"])
def test_boolean_options_precede_the_only_build(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    """Der Zweiform-Konstruktor rechnet schon; ausschließlich leer konfigurieren."""
    import OCP.BRepAlgoAPI as brep_api  # noqa: N813 - Name der externen OCP-API

    first = edit.box(10.0, 8.0, 6.0)
    second = edit.moved(edit.box(4.0, 4.0, 8.0), (3.0, 0.0, -1.0))
    events: list[str] = []

    class RecordingBoolean:
        """Zeichnet die Reihenfolge auf, statt bei Konstruktion heimlich zu rechnen."""

        def __init__(self, *args: object) -> None:
            assert not args, "the two-shape constructor already builds"
            events.append("new")

        def SetArguments(self, values: Any) -> None:  # noqa: N802
            assert values.Size() == 1
            events.append("arguments")

        def SetTools(self, values: Any) -> None:  # noqa: N802
            assert values.Size() == 1
            events.append("tools")

        def SetNonDestructive(self, value: bool) -> None:  # noqa: N802
            assert value
            events.append("protected")

        def SetFuzzyValue(self, value: float) -> None:  # noqa: N802
            assert value == pytest.approx(EPS_GEOM, rel=0.0)
            events.append("fuzzy")

        def Build(self) -> None:  # noqa: N802
            assert "protected" in events
            events.append("build")

        def IsDone(self) -> bool:  # noqa: N802
            return True

        def Shape(self) -> Any:  # noqa: N802
            return first.shape

    for name in ("BRepAlgoAPI_Fuse", "BRepAlgoAPI_Cut", "BRepAlgoAPI_Common"):
        monkeypatch.setattr(brep_api, name, RecordingBoolean)
    edit.boolean(kind, [first, second])
    assert events.count("build") == 1
    events.clear()
    profiles._fuzzy_boolean(kind, first, second)
    assert events.count("build") == 1
    assert events.index("fuzzy") < events.index("build")
    assert events.index("protected") < events.index("build")


@pytest.mark.parametrize("operation", ["fillet", "chamfer", "shell", "draft", "sew", "push"])
def test_modification_uses_private_input_topology(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    """Auch nichtboolesche Builder dürfen die veröffentlichte Form nicht erhalten."""
    solid = edit.box(20.0, 16.0, 10.0)
    original_faces = solid.faces()
    original_bounds = solid.bounds
    original_volume = solid.volume
    module_name, builder_name = {
        "fillet": ("OCP.BRepFilletAPI", "BRepFilletAPI_MakeFillet"),
        "chamfer": ("OCP.BRepFilletAPI", "BRepFilletAPI_MakeChamfer"),
        "shell": ("OCP.BRepOffsetAPI", "BRepOffsetAPI_MakeThickSolid"),
        "draft": ("OCP.BRepOffsetAPI", "BRepOffsetAPI_DraftAngle"),
        "sew": ("OCP.ShapeFix", "ShapeFix_Shape"),
        "push": ("OCP.BRepPrimAPI", "BRepPrimAPI_MakePrism"),
    }[operation]
    module = importlib.import_module(module_name)
    real_builder = getattr(module, builder_name)
    seen: list[Any] = []

    def private_input(shape: Any) -> None:
        assert all(not shape.IsPartner(original) for original in (solid.shape, *original_faces))
        seen.append(shape)

    class CheckedBuilder:
        """Prüft die echte native Eingabe und lässt danach den echten Builder arbeiten."""

        def __init__(self, *args: Any) -> None:
            if args:
                private_input(args[0])
            self._builder = real_builder(*args)

        def MakeThickSolidByJoin(self, *args: Any) -> Any:  # noqa: N802
            private_input(args[0])
            return self._builder.MakeThickSolidByJoin(*args)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._builder, name)

    monkeypatch.setattr(module, builder_name, CheckedBuilder)
    if operation == "fillet":
        changed = edit.fillet(solid, 1.0, "vertical")
    elif operation == "chamfer":
        changed = edit.chamfer(solid, 1.0, "vertical")
    elif operation == "shell":
        changed = profiles.shell_open_top(solid, 1.0)
    elif operation == "draft":
        changed = profiles.draft_vertical(solid, 3.0)
    elif operation == "sew":
        changed = profiles._sewn(solid)
    else:
        changed = profiles.push_faces(solid, (0.0, 0.0, 1.0), 2.0)
    assert seen, "the real native modifier was not reached"
    assert not changed.shape.IsPartner(solid.shape)
    mesh = changed.to_mesh()
    assert mesh.is_watertight
    assert mesh.raw.is_winding_consistent
    assert mesh.volume > 0.0
    assert abs(mesh.volume - changed.volume) < changed.area * changed.deflection
    assert solid.bounds.minimum == pytest.approx(original_bounds.minimum, abs=EPS_GEOM, rel=0.0)
    assert solid.bounds.maximum == pytest.approx(original_bounds.maximum, abs=EPS_GEOM, rel=0.0)
    # Neuer Wrapper misst dieselbe Eingabe ungecacht, statt den Volumencache zu bestätigen.
    assert Solid(solid.shape).volume == pytest.approx(original_volume, abs=EPS_GEOM, rel=0.0)
    assert all(entry == (0, 0) for entry in _triangulations(solid))


@pytest.mark.parametrize(
    "kind,expected_volume", [("union", 512.0), ("difference", 384.0), ("intersection", 96.0)]
)
def test_real_boolean_keeps_its_input_geometry(kind: str, expected_volume: float) -> None:
    """Alle drei echten Booleschen Wege rechnen, ohne den warmen Eingang zu verändern."""
    first = edit.box(10.0, 8.0, 6.0)
    second = edit.moved(edit.box(4.0, 4.0, 8.0), (3.0, 0.0, -1.0))
    before = [(body.bounds, body.volume, body.face_count) for body in (first, second)]
    result = edit.boolean(kind, [first, second])  # type: ignore[arg-type]
    assert result.volume == pytest.approx(expected_volume, abs=EPS_GEOM, rel=0.0)
    for body, (bounds, volume, faces) in zip((first, second), before, strict=True):
        fresh = Solid(body.shape)
        assert fresh.bounds.minimum == pytest.approx(bounds.minimum, abs=EPS_GEOM, rel=0.0)
        assert fresh.bounds.maximum == pytest.approx(bounds.maximum, abs=EPS_GEOM, rel=0.0)
        assert fresh.volume == pytest.approx(volume, abs=EPS_GEOM, rel=0.0)
        assert fresh.face_count == faces
        assert all(entry == (0, 0) for entry in _triangulations(body))
