"""Unabhängige Kreis- und Polygonmaße der Zylindereinpassung."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect, detect_holes, fit_cylinder, radial_cylinder
from app.core.units import EPS_GEOM
from tests.helpers import stop_after


def cylinder_mantle(
    radius: float,
    sections: int,
    *,
    angle: float = 360.0,
    rings: tuple[float, ...] = (-4.0, 4.0),
    other_diagonal: bool = False,
    oblique: bool = False,
) -> trimesh.Trimesh:
    """Ein Polygonmantel aus bekannten Kreisecken, ohne Deckel im Fitfleck.

    Beide Diagonalen und beliebige axiale Zwischenringe beschreiben dieselben
    ebenen Facetten. Schiefe Mündungen ändern nur die Höhen der Endpunkte.
    """
    closed = math.isclose(angle, 360.0)
    count = sections if closed else sections + 1
    angles = np.linspace(0.0, math.radians(angle), count, endpoint=not closed)
    corners = radius * np.column_stack((np.cos(angles), np.sin(angles)))
    vertices = [
        (x, y, height + (0.2 * x - 0.1 * y if oblique else 0.0))
        for height in rings
        for x, y in corners
    ]
    faces: list[tuple[int, int, int]] = []
    for ring in range(len(rings) - 1):
        for segment in range(sections):
            following = (segment + 1) % count
            a, b = ring * count + segment, ring * count + following
            c, d = a + count, b + count
            faces.extend(((a, b, c), (b, d, c)) if other_diagonal else ((a, b, d), (a, d, c)))
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def subdivided(body: trimesh.Trimesh, depth: int) -> trimesh.Trimesh:
    """Neue Punkte liegen auf alten Sehnen, nicht auf dem gedachten Kreis."""
    vertices, faces = np.array(body.vertices), np.array(body.faces)
    for _ in range(depth):
        vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


@pytest.mark.parametrize("radius", (2.6, 7.5, 20.0))
@pytest.mark.parametrize("sections", (16, 24, 48, 1024))
@pytest.mark.parametrize("depth", (0, 1, 2))
def test_the_circle_measure_and_the_actual_polygon_band_are_separate(
    radius: float, sections: int, depth: int
) -> None:
    """Umkreis und Inkreis stammen aus unabhängigen analytischen Sollwerten."""
    body = subdivided(cylinder_mantle(radius, sections), depth)
    before = (np.array(body.vertices), np.array(body.faces))
    patch = list(range(len(body.faces)))

    fit = fit_cylinder(body, patch)

    assert fit is not None and fit.good
    assert fit.radius == pytest.approx(radius, abs=1e-9)
    assert fit.centre == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    assert fit.fit_error == pytest.approx(0.0, abs=1e-9)
    assert fit.radial_min == pytest.approx(radius * math.cos(math.pi / sections), abs=1e-9)
    assert fit.radial_max == pytest.approx(radius, abs=1e-9)
    assert fit.residual < 1e-9
    radial = radial_cylinder(body, patch)
    assert radial is not None
    assert radial.radius == pytest.approx(radius, abs=1e-9)
    assert radial.fit_error == pytest.approx(fit.fit_error, abs=1e-9)
    assert np.array_equal(body.vertices, before[0])
    assert np.array_equal(body.faces, before[1])


@pytest.mark.parametrize("other_diagonal", (False, True))
@pytest.mark.parametrize("rings", ((-4.0, 4.0), (-4.0, -3.99, -3.9, -3.0, 4.0)))
@pytest.mark.parametrize("shift", ((0.0, 0.0, 0.0), (1e6, -3e6, 5e6)))
def test_rigid_motion_and_uneven_triangulation_preserve_the_measure(
    other_diagonal: bool, rings: tuple[float, ...], shift: tuple[float, float, float]
) -> None:
    """Eine schräg beschnittene Wand behält Achse und Kreis auch weit vom Ursprung."""
    body = cylinder_mantle(15.0, 24, rings=rings, other_diagonal=other_diagonal, oblique=True)
    matrix = trimesh.transformations.rotation_matrix(0.73, (2.0, -1.0, 3.0))
    matrix[:3, 3] = shift
    expected_axis = matrix[:3, 2]
    body.apply_transform(matrix)

    fit = fit_cylinder(body, list(range(len(body.faces))))

    assert fit is not None and fit.good
    assert abs(float(np.asarray(fit.axis) @ expected_axis)) == pytest.approx(1.0, abs=1e-9)
    assert fit.radius == pytest.approx(15.0, abs=1e-6)
    assert fit.centre == pytest.approx(shift, abs=1e-6)
    assert fit.radial_min == pytest.approx(15.0 * math.cos(math.pi / 24), abs=1e-6)
    assert fit.radial_max == pytest.approx(15.0, abs=1e-6)
    assert radial_cylinder(body, list(range(len(body.faces)))) is not None


@pytest.mark.parametrize("angle,sections", ((45.0, 6), (90.0, 12), (180.0, 24), (270.0, 36)))
@pytest.mark.parametrize("depth", (0, 2))
def test_partial_arcs_use_their_real_facets_and_keep_the_radial_edit_limit(
    angle: float, sections: int, depth: int
) -> None:
    """Der fehlende Bogen wird weder als Sehne noch als freie Bohrung erfunden."""
    body = subdivided(cylinder_mantle(7.5, sections, angle=angle), depth)
    patch = list(range(len(body.faces)))

    fit = fit_cylinder(body, patch)

    assert fit is not None and fit.good
    assert fit.radius == pytest.approx(7.5, abs=1e-9)
    assert fit.centre == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    half_step = math.radians(angle / sections) / 2.0
    assert fit.radial_min == pytest.approx(7.5 * math.cos(half_step), abs=1e-9)
    assert fit.radial_max == pytest.approx(7.5, abs=1e-9)
    radial = radial_cylinder(body, patch)
    assert (radial is not None) is (angle >= 180.0)


@pytest.mark.parametrize("deformation", ("ellipse", "outlier", "dent", "opposing_normals"))
def test_a_circle_fit_does_not_hide_deformation_or_inconsistent_material(
    deformation: str,
) -> None:
    """Eine gute mittlere Anpassung entschuldigt keinen örtlich falschen Mantel."""
    body = cylinder_mantle(15.0, 48)
    if deformation == "ellipse":
        body.apply_scale((1.12, 1.0, 1.0))
    elif deformation in ("outlier", "dent"):
        vertices = np.array(body.vertices)
        vertices[[5, 53], :2] *= 1.08 if deformation == "outlier" else 0.94
        body = trimesh.Trimesh(vertices, body.faces, process=False)
    else:
        faces = np.array(body.faces)
        faces[5:15] = faces[5:15, ::-1]
        body = trimesh.Trimesh(body.vertices, faces, process=False)

    fit = fit_cylinder(body, list(range(len(body.faces))))

    assert fit is None or not fit.good


@pytest.mark.parametrize("sections", (6, 8, 12))
def test_an_intentional_coarse_polygon_is_not_published_as_a_round_pin(sections: int) -> None:
    """Ein möglicher Umkreis beweist keine runde Konstruktionsabsicht."""
    body = trimesh.creation.cylinder(radius=7.5, height=8.0, sections=sections)
    found = detect(MeshData.of(body))

    assert not [feature for feature in found.values() if feature.kind in {"pin", "hole"}]


def test_a_flat_strip_and_a_cap_contaminated_arc_do_not_measure_a_cylinder() -> None:
    """Achse und kreisförmige Kontur müssen beide belegt sein."""
    strip = cylinder_mantle(3.0, 1, angle=10.0)
    body = trimesh.creation.cylinder(radius=3.0, height=30.0, sections=96)
    angles = np.arctan2(body.triangles_center[:, 1], body.triangles_center[:, 0])
    contaminated = np.flatnonzero((angles > 0.0) & (angles < math.pi / 2.0)).tolist()
    assert np.max(np.abs(body.face_normals[contaminated, 2])) > 0.9

    for source, patch in ((strip, list(range(len(strip.faces)))), (body, contaminated)):
        fit = fit_cylinder(source, patch)
        assert fit is None or not fit.good


def test_published_round_measures_keep_float_precision_and_the_polygon_band() -> None:
    """Das Kernmaß wird nicht vor Anzeige und Passungsprüfung gerundet."""
    radius = 7.51234567
    body = trimesh.creation.cylinder(radius=radius, height=8.1234567, sections=24)
    found = detect(MeshData.of(body))
    pin = next(feature for feature in found.values() if feature.kind == "pin")

    assert pin.params["diameter"] == pytest.approx(2.0 * radius, abs=1e-9)
    assert pin.params["depth"] == pytest.approx(8.1234567, abs=1e-9)
    assert pin.params["fit_error"] == pytest.approx(0.0, abs=1e-9)
    assert pin.params["radial_min"] == pytest.approx(radius * math.cos(math.pi / 24), abs=1e-9)
    assert pin.params["radial_max"] == pytest.approx(radius, abs=1e-9)


@pytest.mark.parametrize("depth", (0, 2))
def test_cut_endpoints_inside_facets_do_not_shrink_the_circle(depth: int) -> None:
    """Eine Schnittkante macht aus einem Sehnenpunkt keine ursprüngliche Kreisecke."""
    body = cylinder_mantle(7.43, 48).slice_plane((0.0, -0.4, 0.0), (0.0, 1.0, 0.0))
    body = subdivided(body, depth)
    vertices = np.asarray(body.vertices)
    on_cut = np.isclose(vertices[:, 1], -0.4, atol=1e-9)
    assert on_cut.any()
    assert np.max(np.abs(np.linalg.norm(vertices[on_cut, :2], axis=1) - 7.43)) > 0.01

    fit = fit_cylinder(body, list(range(len(body.faces))))

    assert fit is not None and fit.good
    assert fit.radius == pytest.approx(7.43, abs=1e-9)
    assert fit.centre == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    assert fit.radial_min == pytest.approx(7.43 * math.cos(math.pi / 48), abs=1e-9)
    assert fit.radial_max == pytest.approx(7.43, abs=1e-9)


@pytest.mark.parametrize("unshared", (False, True))
def test_face_order_and_local_subdivision_keep_the_same_original_corners(unshared: bool) -> None:
    """Auch getrennte STL-Ecken und nur örtlich verfeinerte Facetten tragen dasselbe Maß."""
    source = cylinder_mantle(15.0, 24)
    vertices, faces = trimesh.remesh.subdivide(
        source.vertices, source.faces, face_index=np.arange(13)
    )
    faces = faces[np.random.default_rng(17).permutation(len(faces))]
    if unshared:
        vertices = vertices[faces].reshape(-1, 3)
        faces = np.arange(len(vertices)).reshape(-1, 3)
    body = trimesh.Trimesh(vertices, faces, process=False)

    fit = fit_cylinder(body, list(range(len(body.faces))))

    assert fit is not None and fit.good
    assert fit.radius == pytest.approx(15.0, abs=1e-9)
    assert fit.radial_min == pytest.approx(15.0 * math.cos(math.pi / 24), abs=1e-9)
    assert fit.radial_max == pytest.approx(15.0, abs=1e-9)


def test_a_cylinder_beside_a_rounding_owns_only_its_actual_cylindrical_faces() -> None:
    """Der Korpus Ø12/R3 trennt die Säule von der ersten benachbarten Torusfacette."""
    path = Path(__file__).parent / "data" / "meshes" / "post_with_fillet.stl"
    body = trimesh.load_mesh(path)
    found = detect(MeshData.of(body))
    pin = next(feature for feature in found.values() if feature.kind == "pin")
    ring = next(feature for feature in found.values() if feature.kind == "torus")
    points = np.asarray(body.vertices)[np.unique(np.asarray(body.faces)[list(pin.face_indices)])]

    assert pin.params["diameter"] == pytest.approx(12.0, abs=5e-6)
    assert np.linalg.norm(points[:, :2], axis=1) == pytest.approx(6.0, abs=5e-6)
    assert not set(pin.face_indices).intersection(ring.face_indices)
    assert not [feature for feature in found.values() if feature.kind == "curved_face"]


@pytest.mark.parametrize("entry", ("fit", "radial"))
def test_cylinder_measurement_checks_an_existing_cancellation(entry: str) -> None:
    """Ein bereits abgebrochener Auftrag beginnt keine Kreiseinpassung."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    body = cylinder_mantle(3.0, 48)
    patch = list(range(len(body.faces)))
    signal = CancelSignal()
    signal.cancel()
    with pytest.raises(OperationCancelled):
        if entry == "fit":
            fit_cylinder(body, patch, check_cancelled=signal.raise_if_cancelled)
        else:
            radial_cylinder(body, patch, check_cancelled=signal.raise_if_cancelled)


@pytest.mark.parametrize(
    "stage", ("_cylinder_contour", "_cylinder_band", "_radial_boundaries_are_planar")
)
def test_cancellation_inside_the_measurement_leaves_no_partial_feature_cache(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    """Originaldaten und globaler Erkennungscache bleiben bis zum vollständigen Ergebnis sauber."""
    from app.core.errors import OperationCancelled
    from app.core.perceive import features as detection
    from app.core.scene.cancel import CancelSignal

    body = (
        trimesh.load_mesh(Path(__file__).parent / "data" / "meshes" / "open_cylinder_clip.stl")
        if stage == "_radial_boundaries_are_planar"
        else trimesh.creation.cylinder(radius=3.0, height=8.0, sections=48)
    )
    mesh = MeshData.of(body)
    before = (np.array(body.vertices), np.array(body.faces))
    signal = CancelSignal()
    checks = []
    original = getattr(detection, stage)

    def during(*args):
        callback = args[-1]
        assert callback == signal.raise_if_cancelled

        def stop() -> None:
            checks.append(True)
            if len(checks) == 2:
                signal.cancel()
            callback()

        return original(*args[:-1], stop)

    detection.forget_cache()
    monkeypatch.setattr(detection, "FIT_SCAN_BLOCK", 16)
    monkeypatch.setattr(detection, stage, during)
    with pytest.raises(OperationCancelled):
        detection.detect(mesh, check_cancelled=signal.raise_if_cancelled)
    assert len(checks) == 2
    assert not detection._FEATURE_CACHE
    assert np.array_equal(body.vertices, before[0])
    assert np.array_equal(body.faces, before[1])
    monkeypatch.setattr(detection, stage, original)
    signal.reset()
    found = detection.detect(mesh, check_cancelled=signal.raise_if_cancelled)
    if stage == "_radial_boundaries_are_planar":
        wall = min(
            (feature for feature in found.values() if feature.kind == "fillet"),
            key=lambda feature: float(feature.params["radius"]),
        )
        assert wall.params["diameter"] == pytest.approx(24.0, abs=1e-6)
    else:
        pin = next(feature for feature in found.values() if feature.kind == "pin")
        assert pin.params["diameter"] == pytest.approx(6.0, abs=1e-9)


@pytest.mark.parametrize("open_ended", (False, True))
def test_slot_consumers_keep_the_original_circle_measure(open_ended: bool) -> None:
    """Beide Langlochwege lesen denselben Kreisradius ohne Kernrundung."""
    from shapely.geometry import LineString, box

    radius, travel, height = 3.51234567, 8.1234567, 5.1234567
    start = 15.0 if open_ended else -travel / 2.0
    cutter = LineString([(start, 0.0), (start + travel, 0.0)]).buffer(radius, quad_segs=16)
    body = trimesh.creation.extrude_polygon(
        box(-20.0, -15.0, 20.0, 15.0).difference(cutter), height
    )
    assert body.is_volume
    found = detect(MeshData.of(body))
    slot = next(feature for feature in found.values() if feature.kind == "slot")

    assert bool(slot.params.get("open")) is open_ended
    assert slot.params["diameter"] == pytest.approx(2.0 * radius, abs=1e-9)
    assert slot.params["depth"] == pytest.approx(height, abs=1e-9)
    if not open_ended:
        assert slot.params["travel"] == pytest.approx(travel, abs=1e-9)
        assert slot.params["length"] == pytest.approx(travel + 2.0 * radius, abs=1e-9)


@pytest.mark.parametrize("inward", (False, True))
@pytest.mark.parametrize("mirrored", (False, True))
def test_material_direction_and_reflection_preserve_the_measured_band(
    inward: bool, mirrored: bool
) -> None:
    """Innen-/Außenrolle folgt den echten Flächennormalen, nicht einer Achsenkonvention."""
    body = cylinder_mantle(7.5, 24)
    if inward:
        body.invert()
    if mirrored:
        body.apply_scale((-1.0, 1.0, 1.0))

    fit = fit_cylinder(body, list(range(len(body.faces))))

    assert fit is not None and fit.good
    assert fit.inward is inward
    assert fit.radius == pytest.approx(7.5, abs=1e-9)
    assert fit.radial_min == pytest.approx(7.5 * math.cos(math.pi / 24), abs=1e-9)
    assert fit.radial_max == pytest.approx(7.5, abs=1e-9)


def test_small_measured_contour_errors_are_not_reported_as_perfect_nominal_geometry() -> None:
    """Aufgelöste Abweichung bleibt sichtbar, obwohl eine Kreisnäherung sinnvoll ist."""
    radius, error, sections = 15.0, 0.002, 48
    body = cylinder_mantle(radius, sections)
    vertices = np.array(body.vertices)
    offsets = np.tile(np.where(np.arange(sections) % 2, error, -error), 2)
    vertices[:, :2] *= (1.0 + offsets / radius)[:, None]
    body = trimesh.Trimesh(vertices, body.faces, process=False)

    fit = fit_cylinder(body, list(range(len(body.faces))))

    assert fit is not None and fit.good
    assert fit.fit_error is not None and error - 1e-6 <= fit.fit_error <= error + 1e-6
    assert fit.radius == pytest.approx(radius, abs=1e-5)
    assert fit.radial_max == pytest.approx(radius + error, abs=1e-9)
    angle = math.tau / sections
    a, b = radius - error, radius + error
    side = math.sqrt(a * a + b * b - 2.0 * a * b * math.cos(angle))
    assert fit.radial_min == pytest.approx(a * b * math.sin(angle) / side, abs=1e-9)


def test_a_semicircle_with_long_tangent_flanks_is_not_one_cylinder() -> None:
    """Ein echter Bogen beweist seine langen ebenen Fortsetzungen nicht mit."""
    radius = 3.0
    angles = np.linspace(0.0, math.pi, 37)
    corners = np.vstack(
        (
            (radius, -9.0),
            radius * np.column_stack((np.cos(angles), np.sin(angles))),
            (-radius, -9.0),
        )
    )
    count = len(corners)
    vertices = [(x, y, z) for z in (-4.0, 4.0) for x, y in corners]
    faces = [
        face
        for index in range(count - 1)
        for face in (
            (index, index + 1, index + count + 1),
            (index, index + count + 1, index + count),
        )
    ]
    body = trimesh.Trimesh(vertices, faces, process=False)
    assert body.is_winding_consistent
    assert np.max(np.linalg.norm(body.vertices[:, :2], axis=1)) == pytest.approx(math.sqrt(90.0))

    assert fit_cylinder(body, list(range(len(body.faces)))) is None


@pytest.mark.parametrize("prepared,stop_at", ((True, 1), (False, 1), (False, 2)))
def test_direct_fillet_measurement_carries_cancellation_into_lazy_fitting(
    prepared: bool, stop_at: int
) -> None:
    """Auch der einzelne Verbraucher prüft vor Arbeit und reicht den Abbruch weiter."""
    from app.core.errors import OperationCancelled
    from app.core.perceive.features import detect_fillets

    body = trimesh.creation.cylinder(radius=3.0, height=8.0, sections=48)
    mesh = MeshData.of(body)
    before = (np.array(body.vertices), np.array(body.faces))
    stop, reached = stop_after(stop_at)

    with pytest.raises(OperationCancelled):
        detect_fillets(mesh, [] if prepared else None, check_cancelled=stop)

    assert len(reached) == stop_at
    assert np.array_equal(body.vertices, before[0])
    assert np.array_equal(body.faces, before[1])


@pytest.mark.parametrize("angle", (0.0, 0.73, 1.2))
def test_the_body_size_filter_compares_facets_in_the_cylinder_axis_frame(angle: float) -> None:
    """Ein Ø30-Kreis passt auch dann, wenn keine Facette die Weltachsen berührt."""
    radius, height, count = 15.0, 2.0, 16
    body = trimesh.creation.cylinder(radius=radius, height=height, sections=count)
    body.apply_transform(trimesh.transformations.rotation_matrix(math.pi / count, (0.0, 0.0, 1.0)))
    body.apply_transform(trimesh.transformations.rotation_matrix(angle, (1.0, 2.0, 3.0)))
    assert body.is_volume
    assert body.volume == pytest.approx(count * radius**2 * math.sin(math.tau / count) * height / 2)

    found = detect(MeshData.of(body))
    pins = [feature for feature in found.values() if feature.kind == "pin"]

    assert len(pins) == 1
    assert pins[0].params["diameter"] == pytest.approx(2 * radius, abs=1e-9)


def test_a_cylindrical_remainder_with_a_nonplanar_notch_is_not_a_complete_radial_wall() -> None:
    """Der Fit einer Resthaut darf eine ausgesparte Delle nicht zu heil erklären."""
    source = cylinder_mantle(12.0, 72, angle=184.0, rings=(0.0, 17.0))
    patch = [index for index in range(len(source.faces)) if index not in (70, 71, 73)]
    fit = fit_cylinder(source, patch)

    assert fit is not None and fit.good
    assert fit.radius == pytest.approx(12.0, abs=1e-9)
    assert radial_cylinder(source, patch) is None


# --- Längs unterteilte Zylindermäntel bleiben als ein Merkmal erkennbar ---------------


def _subdivided_inner_wall(
    *, radius: float = 5.75, height: float = 8.5, sections: int = 48, levels: int = 6
) -> MeshData:
    """Einen innen gerichteten Mantel mit vielen Dreiecken je Facette bauen."""
    angles = np.linspace(0.0, 2.0 * np.pi, sections, endpoint=False)
    z_values = np.linspace(-height / 2.0, height / 2.0, levels)
    vertices = np.asarray(
        [(radius * np.cos(angle), radius * np.sin(angle), z) for z in z_values for angle in angles],
        dtype=float,
    )
    faces: list[tuple[int, int, int]] = []
    for level in range(levels - 1):
        lower = level * sections
        upper = (level + 1) * sections
        for section in range(sections):
            following = (section + 1) % sections
            # Umgekehrte Windung: Die Normalen zeigen in die Bohrung.
            faces.extend(
                [
                    (lower + section, upper + following, lower + following),
                    (lower + section, upper + section, upper + following),
                ]
            )
    return MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))


@pytest.mark.parametrize("levels", (2, 6, 17))
def test_a_longitudinally_subdivided_bore_wall_stays_one_hole(levels: int) -> None:
    """Axiale Unterteilung verändert weder Kreismaß noch wirkliche Facettenradien."""
    radius, height = 5.75, 8.5
    sections = 48
    mesh = _subdivided_inner_wall(radius=radius, height=height, sections=sections, levels=levels)
    radial_minimum = radius * np.cos(np.pi / sections)
    # Die Originalecken tragen den Umkreis, die Mitte einer Facettensehne
    # den Inkreis. Beide Sollwerte kommen aus der konstruierten Kontur.
    vertices = np.asarray(mesh.raw.vertices)
    assert np.linalg.norm(vertices[:, :2], axis=1) == pytest.approx(radius, abs=EPS_GEOM, rel=0)
    chord_middle = (vertices[0, :2] + vertices[1, :2]) / 2.0
    assert np.linalg.norm(chord_middle) == pytest.approx(radial_minimum, abs=EPS_GEOM, rel=0)

    holes = detect_holes(mesh)

    assert len(holes) == 1
    hole = holes[0]
    assert set(hole.face_indices) == set(range(len(mesh.raw.faces)))
    assert hole.params["diameter"] == pytest.approx(2.0 * radius, abs=EPS_GEOM, rel=0)
    assert hole.params["depth"] == pytest.approx(height, abs=EPS_GEOM, rel=0)
    assert hole.params["fit_error"] == pytest.approx(0.0, abs=EPS_GEOM, rel=0)
    assert hole.params["radial_min"] == pytest.approx(radial_minimum, abs=EPS_GEOM, rel=0)
    assert hole.params["radial_max"] == pytest.approx(radius, abs=EPS_GEOM, rel=0)
