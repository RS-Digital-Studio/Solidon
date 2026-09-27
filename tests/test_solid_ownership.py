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


def test_canonical_recognition_does_not_rewrite_native_nurbs_geometry() -> None:
    """Polwerte, Trimmkurven, Topologie und native Vernetzung bleiben bytegleich."""
    import io

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepTools import BRepTools

    body = edit.cut_bore(
        edit.box(40.0, 30.0, 10.0),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=20.0,
    )
    source = Solid(BRepBuilderAPI_NurbsConvert(body.shape, True).Shape())
    before = io.BytesIO()
    BRepTools.Write_s(source.shape, before)
    assert len(features_of(source)) == 7
    assert len(profiles._planar_faces(source)) == 6
    after = io.BytesIO()
    BRepTools.Write_s(source.shape, after)
    assert after.getvalue() == before.getvalue()
    assert all(counts == (0, 0) for counts in _triangulations(source))


def test_unwrapping_surface_trims_is_read_only_bounded_and_cancellable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine tatsächliche Trimmhülle teilt Abbruch und Grenzen mit allen nativen Verbrauchern."""
    import io

    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_NurbsConvert
    from OCP.BRepTools import BRepTools
    from OCP.Geom import Geom_RectangularTrimmedSurface

    from app.core.brep import kernel
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    body = Solid(BRepBuilderAPI_NurbsConvert(edit.cylinder(6.0, 8.0).shape, True).Shape())
    basis = BRep_Tool.Surface_s(body.faces()[0]).Copy()
    trimmed = Geom_RectangularTrimmedSurface(basis, 1.0, 3.0, 1.0, 7.0)
    face = BRepBuilderAPI_MakeFace(trimmed, EPS_GEOM).Face()
    before = io.BytesIO()
    BRepTools.Write_s(face, before)

    class AfterOneWrapper:
        """Bricht nach dem ersten echten nativen Entpackschritt ab."""

        def __init__(self) -> None:
            self.calls = 0
            self.signal = CancelSignal()

        def raise_if_cancelled(self) -> None:
            self.calls += 1
            if self.calls == 2:
                self.signal.cancel()
            self.signal.raise_if_cancelled()

        @property
        def is_cancelled(self) -> bool:
            return self.signal.is_cancelled

    cancelled = AfterOneWrapper()
    with pytest.raises(OperationCancelled):
        kernel.untrimmed_surface(trimmed, cancelled=cancelled)
    assert cancelled.calls == 2
    with monkeypatch.context() as isolated:
        isolated.setattr(kernel, "_MAX_SURFACE_WRAPPERS", 0)
        assert kernel.untrimmed_surface(trimmed) is None
    original = kernel.untrimmed_surface(trimmed)
    assert original is not None
    assert original.Value(2.0, 4.0).Coord() == pytest.approx(
        basis.Value(2.0, 4.0).Coord(), abs=EPS_GEOM
    )
    after = io.BytesIO()
    BRepTools.Write_s(face, after)
    assert after.getvalue() == before.getvalue()


@pytest.mark.parametrize("nurbs", [False, True])
@pytest.mark.parametrize("operation", ["unround", "reround"])
def test_rounding_edits_preserve_all_native_source_geometry(nurbs: bool, operation: str) -> None:
    """Defeaturing darf auch Polgrad und Knoten benachbarter NURBS-Ebenen nicht verändern."""
    import io
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepTools import BRepTools

    from app.core.brep.properties import INTEGRAL_RELATIVE_ERROR

    source = edit.fillet(edit.box(40.0, 30.0, 20.0), 3.0, "vertical")
    if nurbs:
        source = Solid(BRepBuilderAPI_NurbsConvert(source.shape, True).Shape())
    feature = next(value for value in features_of(source).values() if value.kind == "fillet")
    before = io.BytesIO()
    BRepTools.Write_s(source.shape, before)
    if operation == "unround":
        result = edit.unround(source, feature.params["centre"], 3.0)
        squared_radii = 3.0 * 3.0**2
    else:
        result = edit.reround(source, feature.params["centre"], 3.0, 2.0)
        squared_radii = 3.0 * 3.0**2 + 2.0**2
    after = io.BytesIO()
    BRepTools.Write_s(source.shape, after)
    assert after.getvalue() == before.getvalue()
    assert result.is_closed and result.solid_count == 1
    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.volume == pytest.approx(
        24000.0 - 20.0 * (1.0 - math.pi / 4.0) * squared_radii,
        rel=INTEGRAL_RELATIVE_ERROR,
        abs=0.0,
    )
    assert Solid(source.shape).volume == pytest.approx(
        24000.0 - 20.0 * (1.0 - math.pi / 4.0) * 36.0,
        rel=INTEGRAL_RELATIVE_ERROR,
        abs=0.0,
    )


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


def test_identity_affine_transform_keeps_the_solid_and_its_face_numbers() -> None:
    """Die Identität braucht keine neue native Form oder neue Vernetzung."""
    source = edit.box(10.0, 8.0, 6.0)
    result, mapping = edit.transformed_with_faces(source, np.eye(4))
    assert result is source
    assert mapping == tuple(range(6))
    assert not source._cache


@pytest.mark.parametrize("entry", [edit.transformed, edit.transformed_with_faces])
def test_cancellation_precedes_even_an_identity_transform(entry: Any) -> None:
    """Ein schon abgebrochener Auftrag baut und prüft keine neue native Form."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = edit.box(10.0, 8.0, 6.0)
    cancelled = CancelSignal()
    cancelled.cancel()
    with pytest.raises(OperationCancelled):
        entry(source, np.eye(4), cancelled=cancelled)
    assert not source._cache


@pytest.mark.parametrize("kind", ["volume", "surface"])
def test_cancellation_is_checked_before_a_cached_native_measure(kind: str) -> None:
    """Auch ein Cachetreffer darf einen abgebrochenen Auftrag nicht fortsetzen."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = edit.box(10.0, 8.0, 6.0)
    cached = source._properties(kind)
    cancelled = CancelSignal()
    cancelled.cancel()
    with pytest.raises(OperationCancelled):
        source._properties(kind, cancelled=cancelled)
    assert source._cache[kind] is cached


@pytest.mark.parametrize("route", ["volume", "surface", "transform"])
def test_cancellation_during_native_quadrature_keeps_source_and_cache(
    monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    """Abbruch zwischen echten Quadraturpunkten bleibt Abbruch; ein späterer Lauf gelingt.

    Die Python-Quadratur ist seit dem knotenzerlegten Verbund der letzte
    Rückfall; der Test nimmt den nativen Weg weg, damit sie überhaupt läuft.
    """
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from scipy.integrate import quad_vec

    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = edit.cylinder(6.0, 8.0)
    if route != "transform":
        source = Solid(BRepBuilderAPI_NurbsConvert(source.shape, True).Shape())
    else:
        assert source.volume == pytest.approx(72.0 * math.pi, rel=1e-9)
        assert source.is_closed and source.solid_count == 1
    before = source.bounds, _triangulations(source), dict(source._cache)
    cancelled = CancelSignal()
    visited = 0

    def interrupting_quadrature(function: Any, *args: Any, **kwargs: Any) -> Any:
        """Das Signal kommt nach einem wirklich berechneten Integrationspunkt."""

        def point_then_cancel(value: float) -> Any:
            nonlocal visited
            result = function(value)
            visited += 1
            cancelled.cancel()
            return result

        return quad_vec(point_then_cancel, *args, **kwargs)

    def unavailable_patches(*args: Any, **kwargs: Any) -> Any:
        """Auch der Rückfall einer nicht aufteilbaren Fläche muss abbrechen können."""
        raise ValueError("unavailable private patches")

    matrix = np.diag((2.0, 1.0, 0.5, 1.0))
    with monkeypatch.context() as probe:
        probe.setattr("scipy.integrate.quad_vec", interrupting_quadrature)
        if route == "surface":
            probe.setattr("app.core.brep.properties._spanned_surface", unavailable_patches)
        else:
            probe.setattr("app.core.brep.properties._volume_ladder", unavailable_patches)
        with pytest.raises(OperationCancelled):
            if route == "transform":
                edit.transformed_with_faces(source, matrix, cancelled=cancelled)
            else:
                source._properties(route, cancelled=cancelled)
    assert visited > 0
    assert source.bounds == before[0]
    assert _triangulations(source) == before[1]
    assert source._cache.keys() == before[2].keys()
    assert all(source._cache[key] is value for key, value in before[2].items())

    cancelled.reset()
    if route == "transform":
        result = edit.transformed(source, matrix, cancelled=cancelled)
        assert result.volume == pytest.approx(72.0 * math.pi, rel=1e-9)
        assert not result.shape.IsPartner(source.shape)
    else:
        expected = (72.0 if route == "volume" else 66.0) * math.pi
        assert source._properties(route, cancelled=cancelled).mass == pytest.approx(
            expected, rel=1e-9
        )
    assert source.bounds == before[0]
    assert _triangulations(source) == before[1]


def test_affine_integrals_do_not_modify_source_or_owned_triangulations() -> None:
    """Teilflächen für Integrale sind Arbeitskopien, keine neue Szenentopologie."""
    source = edit.cylinder(6.0, 8.0)
    result = edit.transformed(source, np.diag((2.0, 1.0, 0.5, 1.0)))
    before = _triangulations(source), _triangulations(result)
    assert result.area > 0.0 and result.volume > 0.0
    assert (_triangulations(source), _triangulations(result)) == before
    assert result.face_count == source.face_count == 3


@pytest.mark.parametrize(
    "matrix",
    [
        ((1.0, 0.3, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0, 0, 0, 1)),
        ((2.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.5, 0.0), (0, 0, 0, 1)),
        ((-1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0, 0, 0, 1)),
    ],
    ids=["shear", "anisotropic", "mirror"],
)
def test_an_affine_transform_leaves_the_nurbs_input_byte_identical(matrix: Any) -> None:
    """Auch die allgemeine Abbildung arbeitet auf einer privaten Kopie (§30).

    ``BRepBuilderAPI_GTransform`` schreibt an den Kanten seiner Eingabe: An
    einer NURBS-Platte mit Bohrung setzte eine Scherung das Prüfkennzeichen
    von vier Unterformen des Eingangs zurück (``0111000`` → ``0101000`` im
    BRep-Abbild, gemessen 22.09.2026) — an einem Körper, der der Szene und
    dem Cache gehört.
    """
    import io

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepTools import BRepTools

    body = edit.cut_bore(
        edit.box(60.0, 40.0, 10.0),
        position=(-10.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=8.0,
        depth=12.0,
    )
    source = Solid(BRepBuilderAPI_NurbsConvert(body.shape, True).Shape())
    before = io.BytesIO()
    BRepTools.Write_s(source.shape, before)
    result = edit.transformed(source, matrix)
    after = io.BytesIO()
    BRepTools.Write_s(source.shape, after)
    assert after.getvalue() == before.getvalue()
    assert result.face_count == source.face_count
    assert result.volume == pytest.approx(
        source.volume * abs(float(np.linalg.det(np.asarray(matrix, dtype=float)[:3, :3]))),
        rel=1e-6,
    )


def test_the_surface_integral_keeps_complex_trimmed_thread_flanks_unchanged() -> None:
    """Das Flächenintegral eines Gewindes lässt Form, Vernetzung und Cache des Körpers stehen.

    Eine Länge genügt: Die zweite (12 mm) prüfte dieselbe Zusage an denselben
    Flächenarten, nur mit mehr Umläufen (Review 21.09.2026).
    """
    source = profiles.threaded_rod(10.0, 1.5, 8.0)
    before = source.bounds, source.volume, source.face_count, _triangulations(source)
    before_mesh = source._cache.get("mesh")
    area = source.area
    assert np.isfinite(area) and area > 0.0
    cached = source._properties("surface")
    assert source._properties("surface") is cached
    assert source.bounds.minimum == pytest.approx(before[0].minimum, abs=EPS_GEOM)
    assert source.bounds.maximum == pytest.approx(before[0].maximum, abs=EPS_GEOM)
    assert source.volume == pytest.approx(before[1], abs=EPS_GEOM)
    assert (source.face_count, _triangulations(source)) == before[2:]
    assert source._cache.get("mesh") is before_mesh


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


def test_native_faces_can_be_found_from_their_tessellation_triangles() -> None:
    """Die inverse Zuordnung entdoppelt Flächen, ohne die Auswahl zu verbreitern."""
    solid = edit.cylinder(6.0, 8.0)
    groups = [solid.triangles_of_face(index) for index in range(solid.face_count)]
    assert all(groups)
    assert solid.faces_of_triangles(()) == ()
    for index, triangles in enumerate(groups):
        assert solid.faces_of_triangles(triangles) == (index,)
    assert solid.faces_of_triangles((groups[2][0], groups[0][0], groups[2][0])) == (0, 2)


@pytest.mark.parametrize("choice", ["negative", "past_end", "fractional"])
def test_invalid_triangle_selection_never_addresses_a_different_face(choice: str) -> None:
    """Negative NumPy-Indices dürfen nicht heimlich eine andere Fläche auswählen."""
    from app.core.errors import AppError

    solid = edit.cylinder(6.0, 8.0)
    index = {"negative": -1, "past_end": solid.triangle_count, "fractional": 0.5}[choice]
    with pytest.raises(AppError) as failure:
        solid.faces_of_triangles((index,))
    assert failure.value.suggestions


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

        def SetRunParallel(self, value: bool) -> None:  # noqa: N802
            assert value
            events.append("parallel")

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
    # Parallel auf allen Kernen (Review 23.09.2026): am Gehäuse ``Cat_3.stp``
    # plus Gewindehals 2,01 → 0,33 s, Ergebnis bitgleich zum seriellen Lauf.
    assert events.index("parallel") < events.index("build")
    events.clear()
    profiles._fuzzy_boolean(kind, first, second, "Aus diesem Loch entsteht nichts.")
    assert events.count("build") == 1
    assert events.index("fuzzy") < events.index("build")
    assert events.index("protected") < events.index("build")
    assert events.index("parallel") < events.index("build")


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


#: Die Memos je Fläche — Träger, Maße, Indexkarte — sind Auskünfte über den
#: Eingang, keine Änderung an ihm: Eine Operation darf sie am Eingang anlegen,
#: so wie ``volume`` und ``faces()`` es seit je tun. Was da war, bleibt dasselbe Objekt.
MEMO_KEYS = frozenset({"surfaces", "face_properties", "map:face"})


def _native_selection_state(solid: Solid) -> tuple[Any, ...]:
    """Hält Originalform, vorhandene Cacheobjekte und gegebenenfalls Netzarrays fest."""
    import io

    from OCP.BRepTools import BRepTools

    native = io.BytesIO()
    BRepTools.Write_s(solid.shape, native)
    mesh = solid._cache.get("mesh")
    return (
        native.getvalue(),
        tuple(
            sorted((key, id(value)) for key, value in solid._cache.items() if key not in MEMO_KEYS)
        ),
        None
        if mesh is None
        else (mesh.raw.vertices.tobytes(), mesh.raw.faces.tobytes(), mesh.slots),
    )


def _native_selection_centres(solid: Solid) -> list[tuple[float, float, float]]:
    """Liest Auswahlorte unabhängig von der kanonischen Auswahlprüfung."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    centres = []
    for face in solid.faces():
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        point = props.CentreOfMass()
        centres.append((point.X(), point.Y(), point.Z()))
    return centres


def _native_selection_contains(solid: Solid, point: tuple[float, float, float]) -> bool:
    """Prüft einen unabhängig gewählten Materialpunkt am exakten Ergebnis."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer

    explorer = TopExp_Explorer(solid.shape, TopAbs_SOLID)
    while explorer.More():
        classifier = BRepClass3d_SolidClassifier(explorer.Current())
        classifier.Perform(gp_Pnt(*point), EPS_GEOM)
        if classifier.State() == TopAbs_IN:
            return True
        explorer.Next()
    return False


@pytest.mark.parametrize("nurbs", [False, True])
@pytest.mark.parametrize("selected", ["lower", "both"])
def test_direct_native_faces_move_the_selected_steps_even_with_another_search_centre(
    nurbs: bool, selected: str
) -> None:
    """Die zwei echten Stufen behalten ihre Auswahl, auch gegen eine fremde alte Suchmitte."""
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepCheck import BRepCheck_Analyzer

    source = edit.boolean(
        "union",
        [edit.box(20.0, 30.0, 10.0), edit.moved(edit.box(20.0, 30.0, 20.0), (20.0, 0.0, 0.0))],
    )
    if nurbs:
        source = Solid(BRepBuilderAPI_NurbsConvert(source.shape, True).Shape())
    centres = _native_selection_centres(source)
    lower = next(
        index for index, point in enumerate(centres) if math.dist(point, (0, 0, 10)) < EPS_GEOM
    )
    upper = next(
        index for index, point in enumerate(centres) if math.dist(point, (20, 0, 20)) < EPS_GEOM
    )
    indices = (lower,) if selected == "lower" else (upper, lower)
    source.to_mesh()
    before = _native_selection_state(source)

    result = profiles.push_faces(
        source,
        (1.0, 0.0, 0.0),
        5.0,
        centre=(20.0, 0.0, 20.0),
        selected_faces=indices,
    )

    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.is_closed and result.solid_count == 1
    expected = 20.0 * 30.0 * (15.0 + (20.0 if selected == "lower" else 25.0))
    assert result.volume == pytest.approx(expected, abs=EPS_GEOM, rel=0.0)
    assert _native_selection_contains(result, (0.0, 0.0, 14.0))
    assert _native_selection_contains(result, (20.0, 0.0, 24.0)) is (selected == "both")
    assert not _native_selection_contains(source, (0.0, 0.0, 14.0))
    assert _native_selection_state(source) == before


@pytest.mark.parametrize("nurbs", [False, True])
def test_direct_rounding_face_overrides_a_nearer_different_rounding(nurbs: bool) -> None:
    """Von vier gleich großen Viertelzylindern verschwindet genau die gewählte Ecke."""
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepCheck import BRepCheck_Analyzer

    from app.core.brep.properties import INTEGRAL_RELATIVE_ERROR

    source = edit.fillet(edit.box(40.0, 30.0, 20.0), 3.0, "vertical")
    if nurbs:
        source = Solid(BRepBuilderAPI_NurbsConvert(source.shape, True).Shape())
    centres = _native_selection_centres(source)
    chosen = [index for index, point in enumerate(centres) if point[0] > 17.0 and point[1] > 12.0]
    other = [point for point in centres if point[0] < -17.0 and point[1] < -12.0]
    assert len(chosen) == len(other) == 1
    source.to_mesh()
    before = _native_selection_state(source)

    result = edit.unround(source, other[0], 3.0, selected_faces=chosen)

    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.is_closed and result.solid_count == 1
    assert result.volume == pytest.approx(
        24000.0 - 3.0 * 20.0 * 3.0**2 * (1.0 - math.pi / 4.0),
        rel=INTEGRAL_RELATIVE_ERROR,
        abs=0.0,
    )
    assert _native_selection_contains(result, (19.5, 14.5, 10.0))
    assert not _native_selection_contains(result, (-19.5, -14.5, 10.0))
    assert not _native_selection_contains(source, (19.5, 14.5, 10.0))
    assert _native_selection_state(source) == before


@pytest.mark.parametrize("operation", ["push", "unround"])
@pytest.mark.parametrize(
    "indices",
    [(), (-1,), (6,), (0.25,), (True,), (np.bool_(True),), ("0",)],
    ids=["empty", "negative", "past_end", "fractional", "bool", "numpy_bool", "text"],
)
def test_explicit_native_selection_rejects_invalid_indices_before_copying(
    operation: str, indices: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine ungültige ausdrückliche Auswahl eröffnet weder eine Kopie noch eine Ersatzsuche."""
    from app.core.brep import kernel
    from app.core.errors import ValidationError

    source = edit.box(20.0, 16.0, 10.0)
    before = _native_selection_state(source)

    def unexpected_copy(_shape: Any) -> Any:
        raise AssertionError("invalid native selection reached a copier")

    monkeypatch.setattr(kernel, "copy_shape", unexpected_copy)
    with pytest.raises(ValidationError) as rejected:
        if operation == "push":
            profiles.push_faces(source, (0, 0, 1), 2.0, selected_faces=indices)
        else:
            edit.unround(source, (0, 0, 0), 3.0, selected_faces=indices)
    assert rejected.value.suggestions
    assert _native_selection_state(source) == before


def test_native_selection_is_a_set_and_keeps_the_cold_source_cache() -> None:
    """Wiederholte Ganzzahlindices sind dieselbe Menge, kein zweiter Geometrieauftrag."""
    source = edit.box(20.0, 16.0, 10.0)
    before = _native_selection_state(source)

    assert source.checked_face_indices((np.int64(4), 1, 4)) == (1, 4)

    assert _native_selection_state(source) == before
    assert not source._cache


@pytest.mark.parametrize("problem", ["plane", "radius", "several"])
def test_direct_unround_rejects_a_nonmatching_face_instead_of_searching_elsewhere(
    problem: str,
) -> None:
    """Eine Ebene, ein falscher Radius und mehrere Rundungen bleiben Auswahlfehler."""
    from app.core.errors import GeometryError

    source = edit.fillet(edit.box(40.0, 30.0, 20.0), 3.0, "vertical")
    centres = _native_selection_centres(source)
    roundings = [
        index
        for index, point in enumerate(centres)
        if abs(point[0]) > 17.0 and abs(point[1]) > 12.0
    ]
    assert len(roundings) == 4
    if problem == "plane":
        indices = (
            next(index for index, point in enumerate(centres) if abs(point[2] - 20.0) < EPS_GEOM),
        )
    elif problem == "several":
        indices = tuple(roundings[:2])
    else:
        indices = (roundings[0],)
    before = _native_selection_state(source)

    with pytest.raises(GeometryError) as rejected:
        edit.unround(
            source,
            centres[roundings[0]],
            2.0 if problem == "radius" else 3.0,
            selected_faces=indices,
        )

    assert {action.id for action in rejected.value.suggestions} == {"correct_input", "cancel"}
    assert _native_selection_state(source) == before


def test_direct_push_rejects_a_cylinder_instead_of_moving_its_end_plane() -> None:
    """Der gegebene Mittelpunkt einer Stirnfläche ersetzt keinen gewählten Zylindermantel."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    from app.core.errors import ValidationError

    source = edit.cylinder(12.0, 8.0)
    wall = next(
        index
        for index, face in enumerate(source.faces())
        if BRepAdaptor_Surface(face).GetType() == GeomAbs_Cylinder
    )
    before = _native_selection_state(source)

    with pytest.raises(ValidationError) as rejected:
        profiles.push_faces(source, (0, 0, 1), 2.0, centre=(0, 0, 8), selected_faces=(wall,))

    assert rejected.value.suggestions
    assert _native_selection_state(source) == before


@pytest.mark.parametrize("operation", ["push", "unround"])
@pytest.mark.parametrize("stage", ["before", "selection", "after_copy"])
def test_direct_native_selection_cancellation_preserves_its_input_and_cache(
    operation: str, stage: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dasselbe Token stoppt vor Arbeit, innerhalb der Auswahl und nach der echten Kopie."""
    from app.core.brep import kernel
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = edit.box(20.0, 16.0, 10.0)
    before = _native_selection_state(source)
    cancelled = CancelSignal()
    copied: list[Any] = []
    original_copy = kernel.copy_shape

    def tracked_copy(shape: Any) -> tuple[Any, tuple[int, ...], tuple[int, ...]]:
        assert stage == "after_copy", "cancelled selection reached the copier"
        result = original_copy(shape)
        copied.append(result[0])
        cancelled.cancel()
        return result

    class InterruptedIndices(tuple):
        def __iter__(self):
            yield 0
            cancelled.cancel()
            yield 1

    if stage == "before":
        cancelled.cancel()
    indices = InterruptedIndices((0, 1)) if stage == "selection" else (0,)
    monkeypatch.setattr(kernel, "copy_shape", tracked_copy)
    with pytest.raises(OperationCancelled):
        if operation == "push":
            profiles.push_faces(source, (0, 0, 1), 2.0, selected_faces=indices, cancelled=cancelled)
        else:
            edit.unround(source, (0, 0, 0), 3.0, selected_faces=indices, cancelled=cancelled)

    assert bool(copied) is (stage == "after_copy")
    assert cancelled.is_cancelled
    assert _native_selection_state(source) == before


@pytest.mark.parametrize("operation", ["push", "unround"])
def test_direct_native_selection_survives_a_genuine_copy_face_reordering(
    operation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vertauschte echte Teilkörper widerlegen die Annahme gleicher Flächenbesuchsreihenfolge."""
    import math

    from OCP.BRep import BRep_Builder
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_COMPOUND, TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS_Compound

    from app.core.brep import kernel

    part = edit.box(40.0, 30.0, 20.0)
    if operation == "unround":
        part = edit.fillet(part, 3.0, "vertical")
    left = edit.moved(part, (-40.0, 0.0, 0.0))
    right = edit.moved(part, (40.0, 0.0, 0.0))
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    builder.Add(compound, left.shape)
    builder.Add(compound, right.shape)
    source = Solid(compound)
    centres = _native_selection_centres(source)
    if operation == "push":
        chosen = [
            index
            for index, point in enumerate(centres)
            if abs(point[0] + 40.0) < EPS_GEOM and abs(point[2] - 20.0) < EPS_GEOM
        ]
    else:
        chosen = [
            index
            for index, point in enumerate(centres)
            if -23.0 < point[0] < -20.0 and point[1] > 12.0
        ]
    assert len(chosen) == 1
    before = _native_selection_state(source)
    original_copy = kernel.copy_shape
    first_mapping: list[tuple[int, ...]] = []

    def reordered_copy(shape: Any) -> tuple[Any, tuple[int, ...], tuple[int, ...]]:
        copied, mapping, edges = original_copy(shape)
        if copied.ShapeType() != TopAbs_COMPOUND:
            return copied, mapping, edges
        children = ShapeMap()
        TopExp.MapShapes_s(copied, TopAbs_SOLID, children)
        reordered = TopoDS_Compound()
        builder.MakeCompound(reordered)
        for number in range(children.Extent(), 0, -1):
            builder.Add(reordered, children.FindKey(number))

        def renumbered(kind: Any, old_mapping: tuple[int, ...]) -> tuple[int, ...]:
            old, new = ShapeMap(), ShapeMap()
            TopExp.MapShapes_s(copied, kind, old)
            TopExp.MapShapes_s(reordered, kind, new)
            return tuple(int(new.FindIndex(old.FindKey(target + 1))) - 1 for target in old_mapping)

        changed = renumbered(TopAbs_FACE, mapping)
        if shape.IsSame(source.shape):
            first_mapping.append(changed)
        return reordered, changed, renumbered(TopAbs_EDGE, edges)

    monkeypatch.setattr(kernel, "copy_shape", reordered_copy)
    if operation == "push":
        result = profiles.push_faces(
            source, (0, 0, 1), 2.0, centre=(40, 0, 20), selected_faces=chosen
        )
        gained, untouched = (-40.0, 0.0, 21.0), (40.0, 0.0, 21.0)
        assert result.volume == pytest.approx(50400.0, abs=EPS_GEOM, rel=0.0)
    else:
        result = edit.unround(source, (59.0, 14.0, 10.0), 3.0, selected_faces=chosen)
        gained, untouched = (-20.5, 14.5, 10.0), (59.5, 14.5, 10.0)
        assert result.volume == pytest.approx(
            48000.0 - 7.0 * 20.0 * 3.0**2 * (1.0 - math.pi / 4.0),
            abs=EPS_GEOM,
            rel=0.0,
        )
    assert len(first_mapping) == 1
    assert first_mapping[0] != tuple(range(source.face_count))
    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.solid_count == 2 and result.is_closed
    assert _native_selection_contains(result, gained)
    assert not _native_selection_contains(result, untouched)
    assert _native_selection_state(source) == before


@pytest.mark.parametrize("operation", ["push", "unround"])
@pytest.mark.parametrize("stage", ["build", "result_copy"])
def test_direct_native_selection_cancellation_after_real_build_keeps_the_source(
    operation: str, stage: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abbruch nach Build oder Ergebniskopie veröffentlicht weder Ergebnis noch Quelländerung."""
    import OCP.BRepAlgoAPI as brep_api  # noqa: N813 — Name der externen OCP-API

    from app.core.brep import kernel
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = edit.box(40.0, 30.0, 20.0)
    if operation == "unround":
        source = edit.fillet(source, 3.0, "vertical")
    centres = _native_selection_centres(source)
    chosen = [
        index
        for index, point in enumerate(centres)
        if (
            point[0] > 17.0 and point[1] > 12.0
            if operation == "unround"
            else abs(point[2] - 20.0) < EPS_GEOM
        )
    ]
    assert len(chosen) == 1
    before = _native_selection_state(source)
    cancelled = CancelSignal()
    builds: list[bool] = []
    copies: list[Any] = []
    original_copy = kernel.copy_shape
    original_builder = (
        profiles.boolean_builder if operation == "push" else brep_api.BRepAlgoAPI_Defeaturing
    )

    def cancel_after_result_copy(
        shape: Any,
    ) -> tuple[Any, tuple[int, ...], tuple[int, ...]]:
        result = original_copy(shape)
        copies.append(result[0])
        if stage == "result_copy" and len(copies) == 2:
            cancelled.cancel()
        return result

    class CancelAfterBuild:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._builder = original_builder(*args, **kwargs)

        def Build(self, *args: Any) -> None:  # noqa: N802 — bildet die OCP-API nach
            self._builder.Build(*args)
            builds.append(bool(self._builder.IsDone()))
            if stage == "build":
                cancelled.cancel()

        def __getattr__(self, name: str) -> Any:
            return getattr(self._builder, name)

    monkeypatch.setattr(kernel, "copy_shape", cancel_after_result_copy)
    if operation == "push":
        monkeypatch.setattr(profiles, "boolean_builder", CancelAfterBuild)
    else:
        monkeypatch.setattr(brep_api, "BRepAlgoAPI_Defeaturing", CancelAfterBuild)
    with pytest.raises(OperationCancelled):
        if operation == "push":
            profiles.push_faces(source, (0, 0, 1), 2.0, selected_faces=chosen, cancelled=cancelled)
        else:
            edit.unround(
                source, centres[chosen[0]], 3.0, selected_faces=chosen, cancelled=cancelled
            )

    assert builds == [True]
    assert len(copies) == (1 if stage == "build" else 2)
    assert cancelled.is_cancelled
    assert _native_selection_state(source) == before


@pytest.mark.parametrize("nurbs", [False, True])
@pytest.mark.parametrize(
    "centre,minimum,maximum,gained,volume",
    [
        ((0.0, 0.0, 0.0), (-10.0, -8.0, -2.0), (10.0, 8.0, 10.0), (0.0, 0.0, -1.0), 3840.0),
        ((-10.0, 0.0, 5.0), (-12.0, -8.0, 0.0), (10.0, 8.0, 10.0), (-11.0, 0.0, 5.0), 3520.0),
    ],
    ids=["bottom", "left"],
)
def test_direct_native_push_uses_the_selected_planes_own_outward_normal(
    nurbs: bool,
    centre: tuple[float, float, float],
    minimum: tuple[float, float, float],
    maximum: tuple[float, float, float],
    gained: tuple[float, float, float],
    volume: float,
) -> None:
    """Auch die Unterseite und linke Seite folgen ihrer echten Orientierung statt dem Z-Hinweis."""
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepCheck import BRepCheck_Analyzer

    source = edit.box(20.0, 16.0, 10.0)
    if nurbs:
        source = Solid(BRepBuilderAPI_NurbsConvert(source.shape, True).Shape())
    selected = [
        index
        for index, point in enumerate(_native_selection_centres(source))
        if math.dist(point, centre) < EPS_GEOM
    ]
    assert len(selected) == 1
    before = _native_selection_state(source)

    result = profiles.push_faces(
        source,
        (0.0, 0.0, 1.0),
        2.0,
        centre=(0.0, 0.0, 10.0),
        selected_faces=selected,
    )

    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.is_closed and result.solid_count == 1
    assert result.bounds.minimum == pytest.approx(minimum, abs=EPS_GEOM, rel=0.0)
    assert result.bounds.maximum == pytest.approx(maximum, abs=EPS_GEOM, rel=0.0)
    assert result.volume == pytest.approx(volume, abs=EPS_GEOM, rel=0.0)
    assert _native_selection_contains(result, gained)
    assert not _native_selection_contains(result, (0.0, 0.0, 11.0))
    assert _native_selection_state(source) == before


def _edge_summary(edge: Any) -> tuple[float, float, float, float]:
    """Länge und Mitte einer nativen Kante als flaches Tupel, unabhängig von ``edit.edges_of``."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, props)
    point = props.CentreOfMass()
    return float(props.Mass()), point.X(), point.Y(), point.Z()


def _two_boxes_apart() -> tuple[Any, Any]:
    """Zwei Quader als Compound — links bei x = −40, rechts bei x = +40 — und der Builder dazu."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    part = edit.box(40.0, 30.0, 20.0)
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    builder.Add(compound, edit.moved(part, (-40.0, 0.0, 0.0)).shape)
    builder.Add(compound, edit.moved(part, (40.0, 0.0, 0.0)).shape)
    return compound, builder


def _reversing_copy(monkeypatch: pytest.MonkeyPatch, builder: Any) -> list[tuple[int, ...]]:
    """Lässt jede Compound-Kopie ihre Teilkörper rückwärts einhängen und sammelt die
    Kantenabbildungen."""
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_COMPOUND, TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS_Compound

    from app.core.brep import kernel

    original_copy = kernel.copy_shape
    edge_mappings: list[tuple[int, ...]] = []

    def reversed_copy(shape: Any) -> tuple[Any, tuple[int, ...], tuple[int, ...]]:
        copied, faces, edges = original_copy(shape)
        if copied.ShapeType() != TopAbs_COMPOUND:
            return copied, faces, edges
        children = ShapeMap()
        TopExp.MapShapes_s(copied, TopAbs_SOLID, children)
        reordered = TopoDS_Compound()
        builder.MakeCompound(reordered)
        for number in range(children.Extent(), 0, -1):
            builder.Add(reordered, children.FindKey(number))

        def renumbered(kind: Any, old_mapping: tuple[int, ...]) -> tuple[int, ...]:
            old, new = ShapeMap(), ShapeMap()
            TopExp.MapShapes_s(copied, kind, old)
            TopExp.MapShapes_s(reordered, kind, new)
            return tuple(int(new.FindIndex(old.FindKey(target + 1))) - 1 for target in old_mapping)

        changed_edges = renumbered(TopAbs_EDGE, edges)
        edge_mappings.append(changed_edges)
        return reordered, renumbered(TopAbs_FACE, faces), changed_edges

    monkeypatch.setattr(kernel, "copy_shape", reversed_copy)
    return edge_mappings


def test_a_copy_maps_every_native_edge_by_history_not_by_visiting_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Kantenabbildung einer Kopie ist bijektiv und trifft die geometrisch gleiche Kante,
    auch wenn die Kopie ihre Teilkörper in anderer Reihenfolge trägt."""
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp

    compound, builder = _two_boxes_apart()
    edge_mappings = _reversing_copy(monkeypatch, builder)
    source = Solid(compound)

    assert len(edge_mappings) == 1
    assert source._copied_edges == edge_mappings[0]
    assert sorted(source._copied_edges) == list(range(source.edge_count))
    assert source._copied_edges != tuple(range(source.edge_count))
    original = ShapeMap()
    TopExp.MapShapes_s(compound, TopAbs_EDGE, original)
    assert original.Extent() == source.edge_count == 24
    copied = source.edges()
    for index in range(source.edge_count):
        assert _edge_summary(copied[source._copied_edges[index]]) == pytest.approx(
            _edge_summary(original.FindKey(index + 1)), abs=EPS_GEOM, rel=0.0
        )


def test_an_explicit_edge_selection_survives_a_genuine_copy_edge_reordering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die am Eigentümer gewählte Kante wird an der vertauschten Arbeitskopie verrundet —
    nicht ihr Zwilling am anderen Körper."""
    import math

    from OCP.BRepCheck import BRepCheck_Analyzer

    compound, builder = _two_boxes_apart()
    source = Solid(compound)
    chosen = [
        index
        for index, edge in enumerate(source.edges())
        if _edge_summary(edge)[1:] == pytest.approx((-40.0, 15.0, 20.0), abs=EPS_GEOM, rel=0.0)
    ]
    assert len(chosen) == 1
    before = _native_selection_state(source)
    edge_mappings = _reversing_copy(monkeypatch, builder)

    result = edit.fillet(source, 3.0, "vertical", selected_edges=chosen)

    assert len(edge_mappings) >= 1
    assert edge_mappings[0] != tuple(range(source.edge_count))
    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.is_closed and result.solid_count == 2
    assert result.volume == pytest.approx(
        48000.0 - 40.0 * 3.0**2 * (1.0 - math.pi / 4.0), abs=EPS_GEOM, rel=0.0
    )
    assert not _native_selection_contains(result, (-40.0, 14.5, 19.5))
    assert _native_selection_contains(result, (40.0, 14.5, 19.5))
    assert _native_selection_state(source) == before


@pytest.mark.parametrize("operation", ["fillet", "chamfer"])
def test_an_explicit_edge_selection_takes_precedence_over_keys_and_group(operation: str) -> None:
    """Gewählte Kante vor Schlüssel vor Gruppe: Weder die Gruppe noch der genannte
    Schlüssel kommen dazu."""
    import math

    from OCP.BRepCheck import BRepCheck_Analyzer

    source = edit.box(40.0, 30.0, 20.0)
    top_along_x = [
        index
        for index, edge in enumerate(source.edges())
        if _edge_summary(edge)[1:] == pytest.approx((0.0, 15.0, 20.0), abs=EPS_GEOM, rel=0.0)
    ]
    assert len(top_along_x) == 1
    vertical = next(entry for entry in edit.edges_of(source) if abs(entry.direction[2]) > 0.5)
    before = _native_selection_state(source)

    if operation == "fillet":
        result = edit.fillet(
            source, 3.0, "vertical", [edit.edge_key(vertical)], selected_edges=top_along_x
        )
        removed = 40.0 * 3.0**2 * (1.0 - math.pi / 4.0)
    else:
        result = edit.chamfer(
            source, 3.0, "vertical", [edit.edge_key(vertical)], selected_edges=top_along_x
        )
        removed = 40.0 * 3.0**2 / 2.0

    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.is_closed and result.solid_count == 1
    assert result.volume == pytest.approx(24000.0 - removed, abs=EPS_GEOM, rel=0.0)
    assert not _native_selection_contains(result, (0.0, 14.5, 19.5))
    assert _native_selection_contains(result, (0.0, -14.5, 19.5))
    assert _native_selection_contains(result, (19.5, 14.5, 10.0))
    assert _native_selection_state(source) == before


@pytest.mark.parametrize("operation", ["fillet", "chamfer"])
@pytest.mark.parametrize("indices", [(), (-1,), (10**6,), (1.5,), (True,), ("0",)], ids=repr)
def test_an_invalid_edge_selection_is_rejected_before_any_copy(
    monkeypatch: pytest.MonkeyPatch, operation: str, indices: Any
) -> None:
    """Eine ungültige Kantenauswahl eröffnet weder eine Kopie noch fällt sie auf die
    Gruppe zurück."""
    from app.core.brep import kernel
    from app.core.errors import ValidationError

    source = edit.box(20.0, 16.0, 10.0)
    before = _native_selection_state(source)

    def unexpected_copy(_shape: Any) -> Any:
        raise AssertionError("invalid native edge selection reached a copier")

    monkeypatch.setattr(kernel, "copy_shape", unexpected_copy)
    with pytest.raises(ValidationError) as rejected:
        if operation == "fillet":
            edit.fillet(source, 2.0, "all", selected_edges=indices)
        else:
            edit.chamfer(source, 2.0, "all", selected_edges=indices)
    assert rejected.value.suggestions
    assert _native_selection_state(source) == before


@pytest.mark.parametrize("nurbs", [False, True])
def test_unround_proves_the_replacing_sharp_edge_from_the_builder_history(nurbs: bool) -> None:
    """Je Rundung nennt die Historie der beiden Wände genau die senkrechte Eckkante,
    die sie ersetzt."""
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

    source = edit.fillet(edit.box(40.0, 30.0, 20.0), 3.0, "vertical")
    if nurbs:
        source = Solid(BRepBuilderAPI_NurbsConvert(source.shape, True).Shape())
    fillets = [value for value in features_of(source).values() if value.kind == "fillet"]
    assert len(fillets) == 4
    before = _native_selection_state(source)

    for feature in fillets:
        faces = source.complete_faces_of_triangles(feature.face_indices)
        result, edge = edit._unround(source, feature.params["centre"], 3.0, faces, None)
        assert edge is not None
        assert 0 <= edge < result.edge_count
        length, *middle = _edge_summary(result.edges()[edge])
        x, y, _z = feature.params["centre"]
        assert length == pytest.approx(20.0, abs=EPS_GEOM, rel=0.0)
        assert middle == pytest.approx(
            (math.copysign(20.0, x), math.copysign(15.0, y), 10.0), abs=EPS_GEOM, rel=0.0
        )
    assert _native_selection_state(source) == before


@pytest.mark.parametrize("nurbs", [False, True])
def test_direct_reround_changes_the_selected_rounding_even_with_another_centre(
    nurbs: bool,
) -> None:
    """Von vier gleichen Rundungen bekommt genau die gewählte den neuen Radius — nicht
    die an der genannten Mitte."""
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepCheck import BRepCheck_Analyzer

    from app.core.brep.properties import INTEGRAL_RELATIVE_ERROR

    source = edit.fillet(edit.box(40.0, 30.0, 20.0), 3.0, "vertical")
    if nurbs:
        source = Solid(BRepBuilderAPI_NurbsConvert(source.shape, True).Shape())
    fillets = [value for value in features_of(source).values() if value.kind == "fillet"]
    chosen = next(f for f in fillets if f.params["centre"][0] > 0 and f.params["centre"][1] > 0)
    other = next(f for f in fillets if f.params["centre"][0] < 0 and f.params["centre"][1] < 0)
    faces = source.complete_faces_of_triangles(chosen.face_indices)
    source.to_mesh()
    before = _native_selection_state(source)

    result = edit.reround(source, other.params["centre"], 3.0, 2.0, selected_faces=faces)

    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.is_closed and result.solid_count == 1
    assert result.volume == pytest.approx(
        24000.0 - 20.0 * (1.0 - math.pi / 4.0) * (3.0 * 3.0**2 + 2.0**2),
        rel=INTEGRAL_RELATIVE_ERROR,
        abs=0.0,
    )
    radii = {
        (value.params["centre"][0] > 0, value.params["centre"][1] > 0): float(
            value.params["radius"]
        )
        for value in features_of(result).values()
        if value.kind == "fillet"
    }
    assert len(radii) == 4
    assert radii[(True, True)] == pytest.approx(2.0, abs=EPS_GEOM, rel=0.0)
    assert all(
        radius == pytest.approx(3.0, abs=EPS_GEOM, rel=0.0)
        for corner, radius in radii.items()
        if corner != (True, True)
    )
    assert _native_selection_state(source) == before


def test_reround_refuses_a_rounding_without_two_walls_instead_of_guessing_an_edge() -> None:
    """Eine Rundung zwischen Deckel und Zylindermantel hat keine belegte Ersatzkante:
    derselbe Satz wie am Netz."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.errors import CHANGE_SELECTION, GeometryError
    from app.core.geom.edges import NOT_BETWEEN_TWO_PLANES

    lying = Solid(
        BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(-20.0, 0.0, 10.0), gp_Dir(1.0, 0.0, 0.0)), 5.0, 40.0
        ).Shape()
    )
    body = edit.boolean("union", [edit.box(40.0, 30.0, 10.0), lying])
    along = next(
        entry
        for entry in edit.edges_of(body)
        if entry.middle == pytest.approx((0.0, 5.0, 10.0), abs=EPS_GEOM, rel=0.0)
    )
    source = edit.fillet(body, 2.0, "named", [edit.edge_key(along)])
    fillet = next(
        value
        for value in features_of(source).values()
        if value.kind == "fillet" and abs(float(value.params["radius"]) - 2.0) < EPS_GEOM
    )
    faces = source.complete_faces_of_triangles(fillet.face_indices)
    before = _native_selection_state(source)

    removed, edge = edit._unround(source, fillet.params["centre"], 2.0, faces, None)
    assert edge is None
    assert removed.is_closed and removed.solid_count == 1
    assert removed.volume == pytest.approx(body.volume, abs=EPS_GEOM, rel=0.0)
    with pytest.raises(GeometryError) as refused:
        edit.reround(source, fillet.params["centre"], 2.0, 1.0, selected_faces=faces)
    assert refused.value.detail == NOT_BETWEEN_TWO_PLANES
    assert refused.value.suggestions[0] is CHANGE_SELECTION
    assert _native_selection_state(source) == before


# --- Der Weg auf die Platte: ein Körper als Bytes und zurück -------------------------


def test_a_body_survives_the_byte_round_trip_with_its_faces_slots_and_triangles() -> None:
    """``to_bytes``/``from_bytes`` geben denselben Körper zurück — bitgenau, in Flächenreihenfolge.

    Der Plattencache soll exakte Körper ablegen können (Review Leistung B13:
    jedes Öffnen las STEP und erkannte das Gewinde neu, 1,45 s). Dafür muss
    außer dem Volumen die **Reihenfolge** der Flächen stehen — an ihr hängen
    ``face_slots`` — und die Tessellation dieselben Dreiecke liefern, denn die
    Merkmale zeigen mit ihren Indizes darauf.
    """
    from pathlib import Path

    from app.core.brep import step

    box = edit.box(20.0, 16.0, 10.0)
    coloured = Solid(box.shape, face_slots=tuple(index % 3 for index in range(box.face_count)))
    thread = step.read((Path(__file__).parent / "data" / "threads" / "m6_rechts.step").read_bytes())
    for body in (coloured, replace(thread, deflection=0.01)):
        payload = body.to_bytes()
        back = Solid.from_bytes(payload, deflection=body.deflection, face_slots=body.face_slots)
        assert not back.shape.IsPartner(body.shape)
        assert back.volume == body.volume
        assert back.deflection == body.deflection and back.face_slots == body.face_slots
        assert [back.face_properties(i).centre for i in range(back.face_count)] == [
            body.face_properties(i).centre for i in range(body.face_count)
        ]
        assert back.triangle_count == body.triangle_count
        assert back.mesh.slots == body.mesh.slots
        assert {name: feature.face_indices for name, feature in features_of(back).items()} == {
            name: feature.face_indices for name, feature in features_of(body).items()
        }


def test_a_stream_that_is_no_body_is_a_programming_error() -> None:
    """Ein unlesbarer Cacheeintrag ist kein Befund für den Kunden, sondern ein Bericht."""
    from app.core.errors import InternalError

    with pytest.raises(InternalError):
        Solid.from_bytes(b"kein Koerper")
