"""Die schnelle Druckausrichtung darf keinen nicht stehenden Gewinner übernehmen (RM-308).

Der Korpustorus besitzt eine breite, tragfähige Auflage, wenn seine Ringachse
senkrecht steht. Die alte Heuristik bevorzugte bei 45° und 60° jedoch gekippte
Lagen mit zu schmaler Auflage und dem Schwerpunkt außerhalb ihrer Hülle.
Das Urteil hier kommt aus dem wirklich bewegten Ergebnis: Ein unabhängiger
trimesh-Ebenenschnitt und das Volumenintegral prüfen die Auflage und den
Schwerpunkt, ohne Solidons Standprüfung oder Schichtschneider aufzurufen.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import shapely
import trimesh
from shapely.geometry import GeometryCollection, LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

from app.core.errors import OperationCancelled
from app.core.geom import orient, prepare_ops
from app.core.geom.mesh import MeshData, as_mesh_data, read_mesh
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY
from app.core.scene.cancel import CancelSignal, NeverCancelled
from app.core.slice import orientation
from app.core.types import OpContext, OpResult, Profile, Quality, Scene, SceneObject
from app.core.units import EPS_GEOM

MESHES = Path(__file__).parent / "data" / "meshes"


def run_fast(source: SceneObject, profile: Profile, quality: Quality = "draft") -> OpResult:
    """Der registrierte Kundenweg mit ausgeschalteter gründlicher Suche."""
    spec = REGISTRY.get("orient_for_print")
    return spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(thorough=False, arrange=False),
            profile=profile,
            quality=quality,
            seed=41,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def assert_printable_standing(mesh: MeshData, profile: Profile) -> None:
    """Erste Schicht und Schwerpunkt am Ergebnis, ohne die geprüfte Auswahlfunktion."""
    raw = mesh.raw
    height = min(profile.printer.layer_height / 2.0, float(np.ptp(raw.vertices[:, 2])) / 2.0)
    z = float(raw.vertices[:, 2].min()) + height
    segments = trimesh.intersections.mesh_plane(raw, (0.0, 0.0, 1.0), (0.0, 0.0, z))
    # Das gemeinsame Rechenepsilon verbindet gleiche Segmentenden. Die
    # Ringparität erhält das Loch, statt die konvexe Hülle als Auflage zu zählen.
    lines = [shapely.set_precision(LineString(segment[:, :2]), EPS_GEOM) for segment in segments]
    contact = GeometryCollection()
    for region in polygonize(unary_union(lines)):
        contact = contact.symmetric_difference(Polygon(region.exterior))

    triangles = np.asarray(raw.triangles)
    signed = np.sum(triangles[:, 0] * np.cross(triangles[:, 1], triangles[:, 2]), axis=1) / 6.0
    centre = np.sum(signed[:, None] * np.sum(triangles, axis=1) / 4.0, axis=0) / signed.sum()
    assert not contact.is_empty, "Die gewählte Lage braucht eine tatsächliche erste Schicht."
    assert contact.convex_hull.buffer(EPS_GEOM).covers(Point(centre[:2])), (
        "Der Schwerpunkt der gewählten Lage liegt außerhalb der Auflage."
    )
    footing = contact.buffer(-profile.printer.extrusion_width / 2.0, join_style="mitre").area
    assert footing >= profile.smallest_first_layer, (
        f"Die tragfähige Auflage ist mit {footing:.3f} mm² kleiner als "
        f"die {profile.smallest_first_layer:.3f} mm² aus dem Druckprofil."
    )


@pytest.mark.parametrize("angle", [45.0, 60.0])
@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_the_fast_operation_selects_a_standing_pose_from_the_real_corpus(
    profile: Profile, angle: float, quality: Quality
) -> None:
    """Eine stehende Alternative darf weit hinter den ersten Heuristikplätzen liegen."""
    profile = replace(profile, printer=replace(profile.printer, overhang_limit=angle))
    mesh = normalise(read_mesh((MESHES / "torus_ring.stl").read_bytes(), ".stl"), "mm").mesh
    vertices, faces = mesh.raw.vertices.copy(), mesh.raw.faces.copy()
    assert mesh.is_watertight
    # Die Eingabelage belegt eine stehende Alternative unabhängig von jeder Suche.
    assert_printable_standing(mesh, profile)
    source = SceneObject(id="obj_1", name="Ring", mesh=mesh)
    result = run_fast(source, profile, quality)

    assert len(result.outputs) == 1
    assert_printable_standing(as_mesh_data(result.outputs[0].mesh), profile)
    np.testing.assert_array_equal(mesh.raw.vertices, vertices)
    np.testing.assert_array_equal(mesh.raw.faces, faces)


def test_the_first_standing_heuristic_rank_wins_not_the_smallest_support_estimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Standprüfung filtert die schnelle Reihenfolge; sie erfindet keine neue Wertung."""
    body = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    entries = [
        orient.Orientation((0.0, 0.0, -1.0), 400.0, 0.0, 20.0, 0.0),
        orient.Orientation((1.0, 0.0, 0.0), 300.0, 0.0, 20.0, 200.0),
        orient.Orientation((0.0, 1.0, 0.0), 200.0, 0.0, 20.0, 0.0),
    ]
    monkeypatch.setattr(orient, "ranked_orientations", lambda *args, **kwargs: entries)
    checked = []

    def standing(entry: orient.Orientation) -> bool:
        checked.append(entry)
        return entry is not entries[0]

    result = orient.orient_for_print(body, standing=standing)
    assert result.chosen is entries[1], "der spätere kleinere Stützraum ändert die Heuristik nicht"
    assert checked == entries[:2], "nach der ersten stehenden Lage ist die Suche beendet"


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_no_standing_pose_is_refused_with_an_action_and_keeps_the_input(
    profile: Profile, quality: Quality
) -> None:
    """Eine ganze kleine Würfelfläche ist kleiner als die profilgebundene Mindestauflage."""
    edge = 2.0 * profile.printer.extrusion_width
    mesh = MeshData.of(trimesh.creation.box(extents=(edge, edge, edge)))
    # Jede Schnittfläche eines konvexen Körpers ist höchstens halb so groß
    # wie seine Oberfläche; hier genügt sogar diese großzügige obere Grenze.
    assert mesh.area / 2.0 < profile.smallest_first_layer
    vertices, faces = mesh.raw.vertices.copy(), mesh.raw.faces.copy()
    source = SceneObject(id="obj_1", name="Kleiner Würfel", mesh=mesh)

    with pytest.raises(orient.NoStandingOrientationError) as problem:
        run_fast(source, profile, quality)

    assert not isinstance(problem.value, orient.NoFittingOrientationError)
    assert {action.id for action in problem.value.suggestions} - {"cancel"}
    assert "steht" in str(problem.value.title).lower()
    np.testing.assert_array_equal(mesh.raw.vertices, vertices)
    np.testing.assert_array_equal(mesh.raw.faces, faces)


def test_no_fitting_pose_keeps_its_distinct_refusal(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Druckraumverletzung behauptet nicht, der Körper könnte grundsätzlich nicht stehen."""
    profile = replace(profile, printer=replace(profile.printer, build_volume=(1.0, 1.0, 1.0)))
    source = SceneObject(
        id="obj_1", name="Zu groß", mesh=MeshData.of(trimesh.creation.box(extents=(20.0,) * 3))
    )

    def forbidden(*args: object, **kwargs: object) -> bool:
        pytest.fail("Eine schon zu große Lage braucht keine Standprüfung.")

    monkeypatch.setattr(prepare_ops, "standing_check", lambda *args, **kwargs: forbidden)
    with pytest.raises(orient.NoFittingOrientationError) as problem:
        run_fast(source, profile)
    assert not isinstance(problem.value, orient.NoStandingOrientationError)


@pytest.mark.parametrize("when", ["before", "after"])
def test_the_shared_standing_check_can_be_cancelled_on_both_sides(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, when: str
) -> None:
    """Weder vor dem Auflagenschnitt noch nach ihm darf ein Abbruch als Lage durchrutschen."""
    mesh = MeshData.of(trimesh.creation.box(extents=(20.0,) * 3))
    entry = orient.Orientation((0.0, 0.0, -1.0), 400.0, 0.0, 20.0)
    signal = CancelSignal()
    original = orientation._contact
    calls = []

    def contact(*args: object, **kwargs: object):
        calls.append(True)
        assert when == "after", "vor dem Abbruch darf kein Schnitt beginnen"
        result = original(*args, **kwargs)
        signal.cancel()
        return result

    monkeypatch.setattr(orientation, "_contact", contact)
    if when == "before":
        signal.cancel()
    with pytest.raises(OperationCancelled):
        orientation.standing_check(mesh, profile, cancelled=signal)(entry)
    assert len(calls) == (0 if when == "before" else 1)


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_resin_does_not_apply_the_fdm_standing_requirement(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, quality: Quality
) -> None:
    """Ein Resinteil hängt an Stützen; die FDM-Linienauflage entscheidet dort nicht."""
    profile = replace(profile, printer=replace(profile.printer, technology="resin"))
    source = SceneObject(
        id="obj_1",
        name="Kleiner Würfel",
        mesh=MeshData.of(trimesh.creation.box(extents=(0.8,) * 3)),
    )

    def forbidden(*args: object, **kwargs: object):
        pytest.fail("Ein Resinauftrag darf die FDM-Standprüfung nicht anfordern.")

    monkeypatch.setattr(prepare_ops, "standing_check", forbidden)
    result = run_fast(source, profile, quality)
    assert len(result.outputs) == 1
    assert result.outputs[0].mesh.is_watertight


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_the_fast_check_preserves_the_exact_body(profile: Profile, quality: Quality) -> None:
    """Auch mit Standprüfung bleibt ein exakter Ring exakt und trägt die gewählte Bewegung."""
    from tests.helpers import exact_kernel

    exact_kernel()
    from app.core.brep import edit
    from app.core.brep.kernel import Solid

    body = edit.torus((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 40.0, 10.0)
    source = SceneObject(id="obj_1", name="Exakter Ring", mesh=body, kind="brep")
    volume = body.volume
    result = run_fast(source, profile, quality)
    assert len(result.outputs) == 1
    output = result.outputs[0]
    assert output.kind == "brep" and isinstance(output.mesh, Solid)
    assert output.mesh.volume == pytest.approx(volume, rel=1e-10)
    assert body.volume == pytest.approx(volume, rel=1e-10)
    assert_printable_standing(as_mesh_data(output.mesh), profile)


@pytest.mark.parametrize("compiled", [False, True])
@pytest.mark.parametrize("angle", [45.0, 60.0])
def test_a_standing_spherical_ribbon_is_not_falsely_discarded(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, compiled: bool, angle: float
) -> None:
    """Der unabhängige Schnitt belegt die tragende Lage des dünnen Korpusbandes."""
    from app.core.slice import analysis

    if compiled and analysis._chain is None:
        pytest.skip("Der native Schnittkern ist hier nicht gebaut.")
    if not compiled:
        monkeypatch.setattr(analysis, "_chain", None)
    profile = replace(profile, printer=replace(profile.printer, overhang_limit=angle))
    mesh = normalise(
        read_mesh((MESHES / "ambiguous_sphere_ribbon.stl").read_bytes(), ".stl"), "mm"
    ).mesh
    candidate = orient.ranked_orientations(
        mesh, printer=profile.printer, overhang_limit=profile.overhang_limit_degrees
    )[0]
    from app.core.geom.transform import apply

    matrix = orient.fitting_transform(mesh, candidate.direction, profile.printer)
    assert matrix is not None
    assert_printable_standing(apply(mesh, matrix), profile)
    assert orientation.standing_check(mesh, profile)(candidate)
    result = run_fast(SceneObject(id="obj_1", name="Kugelband", mesh=mesh), profile)
    np.testing.assert_allclose(result.transform, matrix, atol=EPS_GEOM, rtol=0.0)
    assert_printable_standing(as_mesh_data(result.outputs[0].mesh), profile)


def test_cached_fast_results_from_before_the_standing_check_are_obsolete() -> None:
    """Ein alter Cachegewinner darf die neue Standprüfung nicht umgehen."""
    assert int(REGISTRY.get("orient_for_print").cache_version) >= 2


@pytest.mark.parametrize("compiled", [False, True])
@pytest.mark.parametrize("with_neighbour", [False, True])
def test_crossing_contact_segments_keep_their_area_and_the_neighbours_hole(
    monkeypatch: pytest.MonkeyPatch, compiled: bool, with_neighbour: bool
) -> None:
    """Zwei Dreiecke tragen Fläche; ein gültiger Nachbarring darf ihren Verlust nicht verdecken."""
    from app.core.slice import analysis

    if compiled and analysis._chain is None:
        pytest.skip("Der native Schnittkern ist hier nicht gebaut.")
    if not compiled:
        monkeypatch.setattr(analysis, "_chain", None)
    loops = [[(-4.0, -2.0), (4.0, 2.0), (-4.0, 2.0), (4.0, -2.0)]]
    if with_neighbour:
        loops.extend(
            [
                [(10.0, 0.0), (20.0, 0.0), (20.0, 10.0), (10.0, 10.0)],
                [(12.0, 2.0), (14.0, 2.0), (14.0, 4.0), (12.0, 4.0)],
            ]
        )
    points, nodes = [], []
    offset = 0
    for loop in loops:
        for index, point in enumerate(loop):
            following = (index + 1) % len(loop)
            points.append((point, loop[following]))
            nodes.append((offset + index, offset + following))
        offset += len(loop)
    shape, contours = analysis._polygon_with_contours(
        np.asarray(points), np.asarray(nodes, dtype=np.int64), capture_contours=True
    )
    assert shape is not None and shape.is_valid
    # Zwei Dreiecke: jeweils Grundseite 8 und Höhe 2. Daneben 10² minus 2².
    assert shape.area == pytest.approx(16.0 + (96.0 if with_neighbour else 0.0))
    assert shape.covers(Point(0.0, 1.0)) and shape.covers(Point(0.0, -1.0))
    if with_neighbour:
        assert shape.covers(Point(15.0, 5.0))
        assert not shape.covers(Point(13.0, 3.0)), "Das Loch bleibt frei."
    assert contours == analysis._to_polygons(shape)
