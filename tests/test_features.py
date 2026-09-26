"""Merkmalserkennung gegen eine Platte mit bekannten Maßen (§21.1, §40).

plate_holes.stl ist 80 x 50 x 8 mm mit vier Bohrungen zu 5,2 mm — jede Zahl,
die die Erkennung erzeugt, lässt sich also prüfen statt bewundern.
"""

from __future__ import annotations

import dataclasses
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive import features as features_module
from app.core.perceive.actions import actions_for
from app.core.perceive.features import (
    _FEATURE_CACHE,
    CACHE_LIMIT,
    EDGE_LOOP_LIMIT,
    FREEFORM_ROUND_COUNT,
    FREEFORM_ROUND_SHARE,
    component_count,
    detect,
    detect_cones,
    detect_edge_loops,
    detect_faces,
    detect_holes,
    detect_pins,
    detect_spheres,
    detect_tori,
    fit_cylinder,
    fit_sphere,
    fit_torus,
    forget_cache,
    freeform_dropped,
    is_a_freeform,
)
from app.core.perceive.relations import widening_at_the_mouth
from app.core.types import Feature, FeatureId, Profile, SurfacePatch
from app.core.units import EPS_GEOM

MESHES = Path(__file__).parent / "data" / "meshes"


def plate(name: str = "plate_holes.stl") -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def cube() -> MeshData:
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


def as_a_file_arrives(body: trimesh.Trimesh) -> MeshData:
    """Durch eine STL geschickt und **ungeschweißt** zurückgelesen.

    Genau so kommt jede STL an, und genau so lädt ``generate.into_project``
    (``weld: False``). Das Format kennt keine gemeinsamen Ecken: Jedes Dreieck
    bringt seine eigenen drei Punkte mit, also hat topologisch jede Kante
    keinen Partner — auch an einem Körper, der rundum geschlossen ist.

    Der Umweg über die Datei ist Absicht und nicht Umständlichkeit: Ein von
    Hand gebautes ``Trimesh`` ist bereits zusammengeführt, und ein Test darauf
    prüfte den Fall nicht, um den es hier geht.
    """
    data = trimesh.exchange.stl.export_stl(body)
    return MeshData.of(
        trimesh.load(trimesh.util.wrap_as_stream(data), file_type="stl", process=False)
    )


# --- bores ----------------------------------------------------------------------


def test_all_four_bores_are_found() -> None:
    """§40: plate_holes is recognised completely."""
    holes = detect_holes(plate())

    assert len(holes) == 4
    assert {hole.id for hole in holes} == {"hole_1", "hole_2", "hole_3", "hole_4"}


def test_the_bore_diameter_is_measured_correctly() -> None:
    for hole in detect_holes(plate()):
        assert hole.params["diameter"] == pytest.approx(5.2, abs=0.05)
        assert hole.params["residual"] < 0.02, "a drilled hole fits a cylinder closely"


@pytest.mark.parametrize("angle", [0.0, 45.0])
def test_a_cylinder_axis_does_not_depend_on_the_eigenvector_sign(
    monkeypatch: pytest.MonkeyPatch, angle: float
) -> None:
    """Dasselbe Bohrungsnetz behält seine Richtung bei beiden gültigen Eigenbasen."""
    mesh = plate()
    hole = detect_holes(mesh)[0]
    body = mesh.raw.copy()
    body.apply_transform(trimesh.transformations.rotation_matrix(math.radians(angle), (1, 0, 0)))
    first = fit_cylinder(body, list(hole.face_indices))
    original = np.linalg.eigh

    def opposite_basis(values):
        """Die zweite mathematisch gleichwertige Eigenbasis derselben Matrix."""
        eigenvalues, vectors = original(values)
        return eigenvalues, -vectors

    monkeypatch.setattr(np.linalg, "eigh", opposite_basis)
    second = fit_cylinder(body, list(hole.face_indices))

    assert first is not None and second is not None
    np.testing.assert_allclose(second.axis, first.axis, atol=1e-12)
    np.testing.assert_allclose(second.centre, first.centre, atol=1e-10)
    assert second.radius == pytest.approx(first.radius)


def test_the_bores_stand_upright_and_go_through() -> None:
    for hole in detect_holes(plate()):
        axis = hole.params["axis"]
        assert abs(abs(axis[2]) - 1.0) < 0.01, "the bores run along Z"
        assert hole.params["through"] is True
        assert hole.params["depth"] == pytest.approx(8.0, abs=0.1)


def test_the_bores_sit_where_they_were_drilled() -> None:
    centres = sorted(
        (round(hole.params["centre"][0], 1), round(hole.params["centre"][1], 1))
        for hole in detect_holes(plate())
    )
    assert centres == [(-25.0, -15.0), (-25.0, 15.0), (25.0, -15.0), (25.0, 15.0)]


def test_the_numbering_is_reproducible() -> None:
    first = {hole.id: hole.params["centre"] for hole in detect_holes(plate())}
    second = {hole.id: hole.params["centre"] for hole in detect_holes(plate())}
    assert first == second


def test_two_coaxial_bores_are_numbered_from_below() -> None:
    """§21.2: Zwei Bohrungen übereinander haben dieselbe Mitte in X und Y.

    Eine Durchführung durch zwei Wände ist die häufigste Doppelbohrung
    überhaupt — und die Sortierung, aus der die Nummern entstehen, verglich
    nur X und Y. Der Vergleich endete unentschieden, und welche von beiden
    ``hole_1`` wurde, hing an der Reihenfolge der gefundenen Flecken. Eine
    Provenienz-ID darf das nicht: Eine Op, die an ``hole_2`` hängt, säße nach
    der nächsten Auswertung an der anderen Bohrung.
    """
    lower = trimesh.creation.box(extents=(30.0, 30.0, 4.0))
    upper = trimesh.creation.box(extents=(30.0, 30.0, 4.0))
    upper.apply_translation((0.0, 0.0, 20.0))
    bore = trimesh.creation.cylinder(radius=2.6, height=60.0, sections=64)
    body = MeshData.of(trimesh.util.concatenate([lower, upper]).difference(bore))

    holes = sorted(detect_holes(body), key=lambda hole: hole.id)

    assert [hole.id for hole in holes] == ["hole_1", "hole_2"]
    heights = [hole.params["centre"][2] for hole in holes]
    assert heights == sorted(heights), f"die untere ist hole_1: {heights}"


def _bent_bracket() -> MeshData:
    """Ein gebogener Winkel: innen R3, außen R5 um dieselbe Mitte, zwei gerade Schenkel."""
    from shapely.geometry import Point, box
    from shapely.ops import unary_union

    bend = Point(0.0, 0.0).buffer(5.0, quad_segs=32).difference(Point(0.0, 0.0).buffer(3.0))
    shape = unary_union(
        [bend.intersection(box(0.0, 0.0, 6.0, 6.0)), box(3, -30, 5, 0), box(-30, 3, 0, 5)]
    )
    return MeshData.of(trimesh.creation.extrude_polygon(shape, height=8.0))


def _hollow_ball() -> MeshData:
    """Eine Kugelschale: außen R10, innen R7 um dieselbe Mitte."""
    outer = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
    inner = trimesh.creation.icosphere(subdivisions=4, radius=7.0)
    inner.invert()
    return MeshData.of(trimesh.util.concatenate([outer, inner]))


def _named_sizes(mesh: MeshData, kind: str) -> dict[str, float]:
    features_module.forget_cache()
    return {
        name: round(float(feature.params.get("radius", feature.params.get("diameter", 0.0))), 3)
        for name, feature in detect(mesh).items()
        if feature.kind == kind
    }


@pytest.mark.parametrize(("body", "kind"), [(_bent_bracket, "fillet"), (_hollow_ball, "sphere")])
def test_concentric_shapes_keep_their_names_whatever_the_triangle_order(body, kind) -> None:
    """RM-211: Die Nummer hing bei gleicher Mitte an der Reihenfolge der Flecken.

    Konzentrische Rundungen — innen und außen an einem gebogenen Winkel, eine
    Kugelschale — haben dieselbe Mitte, und nach der Mitte allein war der
    Vergleich unentschieden. Am Winkel hieß die äußere Rundung ``fillet_1``,
    mit rückwärts gespeicherten Dreiecken die innere; an der Kugelschale wurde
    aus ``sphere_1`` ``sphere_2``. Eine Passung auf ``fillet_1`` zeigte danach
    auf die andere Rundung — ohne Befund und mit denselben Zahlen im
    Merkmalfenster (gefunden an vier Clips aus ``CC2-Werkzeugbox``,
    22.09.2026).
    """
    mesh = body()
    raw = mesh.raw
    count = len(raw.faces)
    forward = _named_sizes(mesh, kind)
    assert forward, f"no {kind} found"
    for order in (np.arange(count)[::-1], np.random.default_rng(211).permutation(count)):
        reordered = MeshData.of(
            trimesh.Trimesh(np.asarray(raw.vertices), np.asarray(raw.faces)[order], process=False)
        )
        assert _named_sizes(reordered, kind) == forward


def test_concentric_fillets_are_numbered_by_their_size() -> None:
    """Bei gleicher Mitte entscheidet das Maß, und zwar das kleinere zuerst."""
    assert _named_sizes(_bent_bracket(), "fillet") == {"fillet_1": 3.0, "fillet_2": 5.0}


def test_the_numbering_order_groups_what_the_rounding_splits() -> None:
    """Zwei Mitten um eine Rundungsgrenze sind eine Mitte, und das Maß entscheidet.

    ``119,0005`` liegt auf der Grenze zwischen ``119,000`` und ``119,001``.
    Zwei konzentrische Rundungen, deren Mitten um 10⁻¹² daneben liegen,
    rundeten auseinander, und das Rauschen ordnete sie. Wer dagegen allein
    steht, bleibt, wo ihn die gerundete Mitte hinstellt — die Nummern aller
    anderen Merkmale ändern sich nicht.
    """
    from app.core.perceive.features import NUMBERING_DIGITS, numbering_order

    centres = [
        (99.6893, 119.0005 + 1e-12, 3.8),
        (99.6893, 119.0005 - 1e-12, 3.8),
        (99.6893, 119.0005, 3.8),
        (10.0, 5.0, 0.0),
        (10.0004, -3.0, 0.0),
        (-2.0, 7.0, 1.0),
    ]
    radii = [5.0, 1.0, 3.0, 2.0, 2.0, 2.0]

    def order(permutation: list[int]) -> list[int]:
        found = numbering_order(
            len(permutation),
            (
                (lambda index: centres[permutation[index]], NUMBERING_DIGITS),
                (lambda index: (radii[permutation[index]],), NUMBERING_DIGITS),
            ),
            lambda index: (permutation[index],),
        )
        return [permutation[index] for index in found]

    expected = [5, 4, 3, 1, 2, 0]
    assert order([0, 1, 2, 3, 4, 5]) == expected
    assert order([5, 4, 3, 2, 1, 0]) == expected
    assert order([2, 0, 4, 1, 5, 3]) == expected
    # Wer allein steht, steht wie nach der gerundeten Mitte.
    alone = [3, 4, 5]
    assert [index for index in expected if index in alone] == sorted(
        alone, key=lambda index: tuple(round(value, 3) for value in centres[index])
    )


def test_the_body_order_ignores_the_order_of_triangles_corners_and_vertices() -> None:
    """Flecken und Dreiecke kommen in der Ordnung des Körpers — nicht der Datei.

    Mit umgekehrter Dreiecksfolge lieferten 12 von 101 Korpuskörpern andere
    Merkmale (22.09.2026): Die Einpassungen summieren in Fleckfolge, und an
    der Kippe eines Fits entscheidet die letzte Stelle. Dieselbe Form in
    anderer Folge — Dreiecke gemischt, Ecken im Dreieck verdreht, Ecken
    umnummeriert — muss dieselbe geometrische Folge ergeben.
    """
    from app.core.perceive.features import in_body_order

    body = trimesh.creation.icosphere(subdivisions=2, radius=10.0)
    rng = np.random.default_rng(7)
    groups = [sorted(rng.choice(len(body.faces), 25, replace=False).tolist()) for _ in range(4)]
    groups = [
        sorted(set(group) - set().union(*groups[:number])) for number, group in enumerate(groups)
    ]

    def geometry(mesh: trimesh.Trimesh, ordered: list[list[int]]) -> list[list[tuple]]:
        corners = np.asarray(mesh.vertices)[np.asarray(mesh.faces)]
        return [
            [tuple(sorted(map(tuple, np.round(corners[face], 12)))) for face in group]
            for group in ordered
        ]

    faces = np.asarray(body.faces)
    shuffle = rng.permutation(len(faces))
    renumber = rng.permutation(len(body.vertices))
    moved = np.roll(faces[shuffle], 1, axis=1)
    other = trimesh.Trimesh(
        vertices=np.asarray(body.vertices)[np.argsort(renumber)],
        faces=renumber[moved],
        process=False,
    )
    back = np.empty(len(faces), dtype=np.int64)
    back[shuffle] = np.arange(len(faces))
    other_groups = [[int(back[face]) for face in group][::-1] for group in groups[::-1]]
    assert geometry(body, in_body_order(body, groups)) == geometry(
        other, in_body_order(other, other_groups)
    )


def test_a_contour_point_carried_by_two_corners_counts_once() -> None:
    """Die zwei Enden einer Mantelkante fallen in der Projektion auf einen Punkt.

    Wie weit sie auseinanderliegen, hing am Rauschen der Achse und damit an der
    Reihenfolge der Dreiecke: An einer Schwammablage aus dem Korpus trug ein
    Bogen aus drei Konturpunkten so eine vierte „Ecke" 10⁻¹⁵ neben der dritten
    und galt in 81 von 200 Reihenfolgen als Rundung (22.09.2026). Die
    Kontur verlangt vier unabhängige Ecken; drei bestimmen jeden Kreis.
    """
    from app.core.perceive.features import _cylinder_contour

    arc = np.array([[3.0 * math.cos(a), 3.0 * math.sin(a)] for a in np.radians([-20, 0, 20])])
    doubled = np.vstack((arc, arc + np.array([[1e-15, -2e-15], [0.0, 3e-15], [-1e-15, 0.0]])))
    assert _cylinder_contour(doubled, 0.01, None) is None

    from app.core.perceive.features import _distinct_points

    assert len(_distinct_points(doubled)) == 3


def test_coinciding_mantle_points_are_merged_before_the_neighbour_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alle Ecken einer Mantellinie fallen auf einen Punkt — gesucht wird zwischen verschiedenen.

    An der großen Bohrung aus ``test_bore_floor_resize`` kamen 525 312 Punkte
    herein, 1 024 davon verschieden. Die Nachbarsuche über alle zählte jedes
    Paar deckungsgleicher Punkte: 134 Millionen Paare, 7 bis 21 s je Aufruf und
    viermal je Größenänderung einer Bohrung (26.09.2026). Das Ergebnis bleibt
    dasselbe: je Gruppe der lexikographisch kleinste Punkt, bei Gleichstand
    der mit der kleineren Nummer, in der Reihenfolge der Nummern.
    """
    from scipy.spatial import cKDTree

    from app.core.perceive.features import _distinct_points

    ring = np.array(
        [[5.0 * math.cos(a), 5.0 * math.sin(a)] for a in np.linspace(0.0, 2.0 * math.pi, 64)[:-1]]
    )
    rng = np.random.default_rng(26092026)
    points = ring[rng.integers(0, len(ring), size=20_000)]
    # Eine Kette unter EPS_GEOM hängt an einem Punkt und wird mit ihm eins.
    chain = ring[:1] + np.array([[0.4 * EPS_GEOM, 0.0], [0.8 * EPS_GEOM, 0.0]])
    points = np.concatenate((points, chain, ring))
    searched = []
    original = cKDTree

    def counted(data: np.ndarray) -> Any:
        searched.append(len(data))
        return original(data)

    monkeypatch.setattr("scipy.spatial.cKDTree", counted)
    merged = _distinct_points(points)
    assert searched and max(searched) <= len(ring) + len(chain)

    order = np.lexsort(points.T[::-1])
    first_of_value: dict[tuple[float, float], int] = {}
    for index in order.tolist():
        first_of_value.setdefault(tuple(points[index]), index)
    expected = sorted(
        index
        for value, index in first_of_value.items()
        if not (value[1] == 0.0 and 5.0 < value[0] <= 5.0 + EPS_GEOM)
    )
    assert np.array_equal(merged, points[expected])


def test_a_face_keeps_its_area_unrounded() -> None:
    """Regel 6: Der Kern rundet nicht — die Fläche steht, wie sie gemessen ist.

    Ebene und gekrümmte Flächen trugen ihre Fläche auf vier Stellen gerundet,
    der exakte Kern dieselbe Fläche ungerundet: zwei Zwillinge, zwei Zahlen.
    Wo zwei gleich große Flächen verglichen werden, rundet der Schlüssel
    (``AREA_DIGITS``), nicht der Wert.
    """
    body = trimesh.creation.box(extents=(10.0, 10.0 / 3.0, 1.0))
    features_module.forget_cache()
    faces = [f for f in detect(MeshData.of(body)).values() if f.kind == "face"]
    largest = max(faces, key=lambda face: face.params["area"])
    assert largest.params["area"] == pytest.approx(100.0 / 3.0, abs=1e-9)


def u_profile() -> MeshData:
    """Ein U-Profil mit einer Durchgangsbohrung im linken Schenkel.

    Der rechte Schenkel steht auf derselben Achse — er liegt in der Projektion
    „über" der Bohrung, ohne sie zu verschließen. Genau die Lage, an der die
    Prüfung „liegt irgendein Dreieck über der Achse" das falsche Ergebnis
    liefert.
    """
    left = trimesh.creation.box(extents=(4.0, 30.0, 20.0))
    left.apply_translation((-11.0, 0.0, 0.0))
    right = trimesh.creation.box(extents=(4.0, 30.0, 20.0))
    right.apply_translation((11.0, 0.0, 0.0))
    base = trimesh.creation.box(extents=(26.0, 30.0, 4.0))
    base.apply_translation((0.0, 0.0, -12.0))
    bore = trimesh.creation.cylinder(
        radius=3.0,
        height=40.0,
        sections=64,
        transform=trimesh.transformations.rotation_matrix(math.pi / 2.0, [0.0, 1.0, 0.0]),
    )
    bore.apply_translation((-11.0, 0.0, 0.0))
    frame = trimesh.boolean.union([left, right, base])
    return MeshData.of(trimesh.boolean.difference([frame, bore]))


def test_a_bore_through_one_leg_of_a_u_is_a_through_bore() -> None:
    """Der Fund: „durchgehend" hieß wörtlich „kein Dreieck irgendwo darüber".

    Der gegenüberliegende Schenkel eines U-Profils liegt in der Projektion
    senkrecht zur Achse genau über der Bohrung — er verschließt sie aber
    nicht, er steht zwanzig Millimeter daneben. Die Bohrung galt damit als
    Sackloch; im Steckbrief steht dann „Sackbohrung Ø 6" über einem Loch, durch
    das man hindurchsieht, und eine Passung dagegen zu setzen ist sinnlos.

    Gefragt wird deshalb entlang der Achse: Material zählt, wo es **im**
    Bohrungsabschnitt liegt.
    """
    holes = detect_holes(u_profile())

    assert len(holes) == 1, [hole.id for hole in holes]
    assert holes[0].params["through"] is True


def test_a_blind_bore_stays_blind() -> None:
    """Die Gegenprobe: Ein Sackloch hat seinen Boden **im** eigenen Abschnitt.

    Ohne sie wäre die Prüfung mit „immer durchgehend" grün.
    """
    plate_body = trimesh.creation.box(extents=(30.0, 30.0, 12.0))
    bore = trimesh.creation.cylinder(radius=3.0, height=8.0, sections=64)
    # Von oben eingesenkt, der Boden liegt bei z = -2.
    bore.apply_translation((0.0, 0.0, 6.0))
    body = MeshData.of(trimesh.boolean.difference([plate_body, bore]))

    holes = detect_holes(body)

    assert holes, "die Sackbohrung wird gefunden"
    assert all(hole.params["through"] is False for hole in holes)


def test_a_cube_has_no_bores() -> None:
    assert detect_holes(cube()) == []


def test_a_pin_is_not_reported_as_a_bore() -> None:
    """Die Normalen entscheiden: zur Achse zeigend ist eine Bohrung, von ihr
    weg ein Stift.
    """
    pin = MeshData.of(trimesh.creation.cylinder(radius=4.0, height=20.0, sections=48))
    # Nur die Hülle, ohne die zwei Endkappen — die sind Flächen, kein Zylinder.
    shell = [
        index for index, normal in enumerate(pin.raw.face_normals) if abs(float(normal[2])) < 0.5
    ]
    fit = fit_cylinder(pin.raw, shell)

    assert fit is not None
    assert fit.radius == pytest.approx(4.0, abs=0.05)
    assert not fit.inward, "a cylinder seen from outside is a pin"
    assert detect_holes(pin) == []


def test_a_cylinder_bigger_than_its_body_is_no_feature() -> None:
    """Ein sanft gebogener Arm **ist** örtlich ein Zylinder mit großem Radius —
    als Merkmal ist er trotzdem keines.

    Gemessen an einem heruntergeladenen Sockel von 160 auf 231 auf 14 mm: Die
    Erkennung fand dort zehn Zapfen, den dicksten mit Ø 631,6 mm. Ein Zapfen ist
    das, was man mit einer Bohrung paart (§14), und mit einem Ø 631 paart
    niemand etwas. Über sieben Modelle waren es 21 von 112 Zapfen und 19 von
    165 Bohrungen, die breiter waren als ihr eigener Körper.

    Gebogen und nicht gerade, damit die Einpassung überhaupt anspringt: Ein
    flacher Streifen hat keine gewölbte Fläche, in die ein Zylinder passt.
    """
    ring = trimesh.creation.annulus(r_min=290.0, r_max=300.0, height=8.0)
    # Nur ein Achtel davon — ein flacher Bogen, wie ihn ein Arm hat. Sein
    # Radius ist 295 mm, sein Körper misst quer zur Achse keine 240.
    arc = ring.slice_plane([0.0, 0.0, 0.0], [0.0, 1.0, 0.0])
    arc = arc.slice_plane([0.0, 0.0, 0.0], [-1.0, 1.0, 0.0])
    body = MeshData.of(arc)
    across = max(body.bounds.size[0], body.bounds.size[1])

    gefunden = detect_pins(body) + detect_holes(body)

    assert across < 590.0, "der Bogen ist schmaler als der Zylinder, der in ihn passt"
    for feature in gefunden:
        assert float(feature.params["diameter"]) <= across + 1e-6, (
            f"{feature.id} mit Ø {feature.params['diameter']} auf {across:.1f} mm Körper"
        )


def test_a_real_pin_is_kept() -> None:
    """Die Gegenprobe, und die ist die wichtigere: Ein Zapfen, der in seinen
    Körper passt, bleibt — sonst hätte die Prüfung die Merkmalserkennung
    stillgelegt.

    Ø 8 auf einem Körper, der quer zur Achse 22 mm misst: das ist der
    Sechskantzapfen einer Querstange aus dem Bestand, und der wird gebraucht.
    """
    # Der Quader kürzer als der Zapfen, sonst steckt der ganz in ihm und es
    # gibt keine gewölbte Außenfläche, in die etwas einzupassen wäre.
    stange = trimesh.creation.box(extents=(22.0, 10.0, 12.0))
    zapfen = trimesh.creation.cylinder(
        radius=4.0,
        height=18.0,
        sections=48,
        transform=trimesh.transformations.rotation_matrix(1.5707963, [1.0, 0.0, 0.0]),
    )
    body = MeshData.of(trimesh.boolean.union([stange, zapfen]))

    gefunden = detect_pins(body)

    assert gefunden, "der Zapfen wird weiter gefunden"
    assert any(abs(float(feature.params["diameter"]) - 8.0) < 0.3 for feature in gefunden), [
        round(float(f.params["diameter"]), 2) for f in gefunden
    ]


# --- faces ----------------------------------------------------------------------


def test_the_six_faces_of_a_cube_are_found() -> None:
    faces = detect_faces(cube())

    assert len(faces) == 6
    for face in faces:
        assert face.params["area"] == pytest.approx(400.0)


def test_the_largest_face_comes_first() -> None:
    faces = detect_faces(plate())

    assert faces[0].id == "face_1"
    assert faces[0].params["area"] > faces[-1].params["area"]
    assert faces[0].params["area"] == pytest.approx(80.0 * 50.0, rel=0.05)


def test_faces_of_the_same_size_are_numbered_the_same_way_every_time() -> None:
    """§21.2: Eine Provenienz-ID muss eine Neuberechnung überleben.

    Die sechs Flächen eines Würfels sind exakt gleich groß, sortiert wurde
    aber nur nach Fläche — welche ``face_1`` wird, hing damit an der
    Reihenfolge der Dreiecke im Netz. Dieselbe Geometrie mit anders
    nummerierten Dreiecken gab eine andere Zuordnung: ``face_1`` lag einmal
    links und einmal unten.

    Die Zuordnung (§21.2) fängt das im Regelbetrieb wieder ein, weil sie über
    die Lage vergleicht — aber die **Ersterkennung** ist der Fall, in dem es
    noch nichts zum Vergleichen gibt.
    """
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    turned = trimesh.Trimesh(
        vertices=box.vertices.copy(), faces=np.roll(box.faces, 5, axis=0), process=False
    )

    first = {
        face.id: tuple(round(value, 2) for value in face.params["centre"])
        for face in detect_faces(MeshData.of(box))
    }
    second = {
        face.id: tuple(round(value, 2) for value in face.params["centre"])
        for face in detect_faces(MeshData.of(turned))
    }

    assert len(first) == 6
    assert first == second


def test_turning_a_part_does_not_renumber_its_faces() -> None:
    """Die Gegenbedingung, und sie schließt den naheliegenden Tiebreak aus.

    Nach Koordinaten zu sortieren wäre deterministisch und trotzdem falsch:
    Deck- und Bodenfläche einer Platte sind gleich groß, und um zwanzig Grad
    gekippt tauschen sie ihre Reihenfolge. ``align`` legt aber ``face_1``
    eines gedrehten Teils auf ``face_1`` des festen — beide müssen dieselbe
    Fläche des Teils meinen, sonst liegt das Teil verkehrt herum auf dem
    anderen.
    """
    flat = plate()
    tilted = MeshData.of(
        flat.raw.copy().apply_transform(
            trimesh.transformations.rotation_matrix(math.radians(20.0), [1.0, 0.0, 0.0])
        )
    )

    before = {face.id: face.face_indices for face in detect_faces(flat)}
    after = {face.id: face.face_indices for face in detect_faces(tilted)}

    assert before, "ohne erkannte Flächen prüft der Vergleich nichts"
    assert before == after, "dieselben Dreiecke tragen dieselbe Nummer"


def test_a_face_knows_where_it_looks() -> None:
    top = max(detect_faces(cube()), key=lambda face: face.params["centre"][2])
    assert top.params["normal"][2] == pytest.approx(1.0, abs=1e-6)


# --- open edges -----------------------------------------------------------------


def test_an_open_model_reports_its_edges() -> None:
    broken = normalise(
        read_mesh((MESHES / "broken_open.stl").read_bytes(), ".stl"), "mm", mend=False
    ).mesh
    loops = detect_edge_loops(broken)

    assert loops and loops[0].kind == "edge_loop"
    # Die Datei ist eingecheckt und ändert sich nicht: fünf offene Kanten.
    # ``> 0`` bliebe grün, wenn die Zählung nur noch eine einzige meldete.
    assert loops[0].params["open_edges"] == 5


def test_a_closed_model_has_no_open_edges() -> None:
    assert detect_edge_loops(cube()) == []


def test_two_holes_in_a_shell_are_two_features() -> None:
    """Der Fund: Alle offenen Kanten wurden **ein** Merkmal.

    Der gemeinsame Schwerpunkt zweier Löcher liegt zwischen ihnen — also im
    Leeren. Die Kamera flog auf einen Punkt, an dem nichts ist, und die Zahl
    daneben („8 offene Kanten") gehörte zu zwei Stellen, die nichts
    miteinander zu tun haben. Jede zusammenhängende Kantenschleife ist ein
    eigener Defekt und bekommt ein eigenes Merkmal.
    """
    parts = []
    for shift in (-20.0, 20.0):
        box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        box.apply_translation((shift, 0.0, 0.0))
        # Die Deckfläche heraus: übrig bleibt ein offener Kasten mit einer
        # Schleife aus vier Kanten.
        box.update_faces(
            np.array([index for index, normal in enumerate(box.face_normals) if normal[2] < 0.9])
        )
        parts.append(box)
    broken = MeshData.of(trimesh.util.concatenate(parts))

    loops = detect_edge_loops(broken)

    assert len(loops) == 2, [loop.id for loop in loops]
    assert sum(int(loop.params["open_edges"]) for loop in loops) == 8
    xs = sorted(round(float(loop.params["centre"][0]), 1) for loop in loops)
    assert xs == [-20.0, 20.0], "jede Schleife sitzt an ihrem eigenen Loch"


@pytest.mark.parametrize("name", ["plate_holes.stl", "torus_ring.stl", "cube_clean.stl"])
def test_a_closed_model_stays_closed_when_it_arrives_unwelded(name: str) -> None:
    """Der Fund: Eine geschlossene Datei meldete eine offene Stelle je Dreieck.

    Eine STL speichert jedes Dreieck mit eigenen Ecken. Wer die gespeicherte
    Topologie befragt statt der geometrischen, bekommt deshalb an **jeder**
    Kante „kein Partner" — gemessen 2 388 offene Kanten an ``plate_holes.stl``,
    6 912 an ``torus_ring.stl``, 36 an ``cube_clean.stl``. Alle drei Teile sind
    dicht; die Zahlen beschrieben das Dateiformat und nicht das Modell.

    Für den Kunden ist das die Auskunft, für die er Solidon öffnet (Weg 1,
    §2.2): Er zieht ein heruntergeladenes Teil herein und liest im Prüfbericht,
    was damit ist. Eine Zahl, die dort etwas anderes beschreibt als sein Teil,
    ist schlimmer als keine.

    Geprüft wird an drei Dateien und nicht an einer: Die Zahl der Dreiecke
    reicht von 12 bis 2 304, und die Toleranz des Zusammenführens hängt an der
    Modellgröße.
    """
    path = MESHES / name
    body = trimesh.load(path, process=False, force="mesh")

    assert not body.is_watertight, (
        f"{name} kommt hier bereits zusammengeführt an — dann prüft der Test seinen Aufbau"
    )
    assert trimesh.load(path, process=True, force="mesh").is_watertight, (
        f"{name} ist auch zusammengeführt nicht dicht — dann ist es der falsche Prüfling"
    )

    assert detect_edge_loops(MeshData.of(body)) == [], (
        "ein dichtes Teil hat keine offene Stelle, gleich wie die Datei es speichert"
    )


def test_a_real_hole_survives_the_merge() -> None:
    """Und die Gegenrichtung, ohne die die Änderung oben wertlos wäre.

    Was ``repair`` schließt, muss die Erkennung erst finden. Ein Zusammenführen,
    das ein echtes Loch verschwinden ließe, nähme der Reparatur die Grundlage —
    und das wäre der schlechtere Fehler: Der Kunde bekäme „alles in Ordnung"
    über einem Teil, das beim Drucken auffliegt.

    Der Kasten ohne Deckel kommt hier denselben Weg wie oben, also
    ungeschweißt. Zusammengelegt werden nur Ecken **am selben Ort**; die vier
    Kanten des offenen Randes haben keinen Partner am selben Ort und bleiben
    deshalb, was sie sind.
    """
    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    box.update_faces(
        np.array([index for index, normal in enumerate(box.face_normals) if normal[2] < 0.9])
    )

    loops = detect_edge_loops(as_a_file_arrives(box))

    assert len(loops) == 1, [loop.id for loop in loops]
    assert loops[0].params["open_edges"] == 4, "die vier Kanten der fehlenden Deckfläche"
    assert loops[0].params["centre"][2] == pytest.approx(5.0, abs=1e-6), (
        "die Schleife sitzt oben, wo der Deckel fehlt"
    )


def test_two_holes_stay_two_when_the_file_arrives_unwelded() -> None:
    """Die Absicht von ``5c90fac6`` gilt auch hier — sie ist der Grund, warum
    nicht einfach alles zu einem Merkmal zusammengefasst wird.

    Zwei Löcher, ungeschweißt geladen: zwei Merkmale an zwei Orten, nicht eines
    dazwischen im Leeren.
    """
    parts = []
    for shift in (-20.0, 20.0):
        part = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        part.apply_translation((shift, 0.0, 0.0))
        part.update_faces(
            np.array([index for index, normal in enumerate(part.face_normals) if normal[2] < 0.9])
        )
        parts.append(part)

    loops = detect_edge_loops(as_a_file_arrives(trimesh.util.concatenate(parts)))

    assert len(loops) == 2, [loop.id for loop in loops]
    xs = sorted(round(float(loop.params["centre"][0]), 1) for loop in loops)
    assert xs == [-20.0, 20.0], "jede Schleife sitzt an ihrem eigenen Loch"


def test_an_unwelded_edge_loop_keeps_its_number_when_the_body_turns() -> None:
    """Dieselbe Zusage wie unten, aber am ungeschweißten Netz — und nur hier
    lässt sie sich überhaupt verletzen.

    Das Zusammenführen nummeriert die Ecken um, und es ordnet sie dabei **nach
    Koordinaten**. Genau davor warnt ``detect_faces``: Eine Ordnung nach
    Koordinaten überlebt keine Drehung. Die Erkennung rechnet deshalb zwar über
    die zusammengeführte Topologie, sortiert aber über die **Original**-Nummern
    der Ecken, die sich weder beim Drehen noch beim Umsortieren ändern.

    **Der Test unten kann das nicht prüfen**, und das ist der Grund für diesen
    hier: Er baut sein Netz von Hand, damit ist es bereits zusammengeführt, und
    Orts- und Original-Nummern fallen zusammen. Gegengeprobt — mit den
    Ortsnummern wandert ``edge_loop_1`` bei dieser Drehung von x=−20 auf x=−20,
    obwohl es bei +20 liegen müsste; der Test unten bleibt dabei grün.
    """
    parts = []
    for shift in (-20.0, 20.0):
        part = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        part.apply_translation((shift, 0.0, 0.0))
        part.update_faces(
            np.array([index for index, normal in enumerate(part.face_normals) if normal[2] < 0.9])
        )
        parts.append(part)
    body = trimesh.util.concatenate(parts)

    before = detect_edge_loops(as_a_file_arrives(body))
    assert len(before) == 2, "sonst prüft der Test seinen eigenen Aufbau"
    assert before[0].params["open_edges"] == before[1].params["open_edges"], (
        "nur bei gleicher Kantenzahl entscheidet das zweite Kriterium — darum geht es hier"
    )

    turn = trimesh.transformations.rotation_matrix(np.pi, (0.0, 0.0, 1.0))
    turned = body.copy()
    turned.apply_transform(turn)
    after = detect_edge_loops(as_a_file_arrives(turned))

    assert len(after) == 2
    expected = trimesh.transform_points([list(before[0].params["centre"])], turn)[0]
    assert tuple(after[0].params["centre"]) == pytest.approx(tuple(expected), abs=1e-6), (
        "edge_loop_1 meint nach der Drehung die andere Schleife — daran hängen Ops und Passungen"
    )


def test_many_open_places_come_as_one_summary() -> None:
    """Die zweite Linie: ein Netz, das wirklich in Stücken ankommt.

    Nicht mehr der ungeschweißte Regelfall — den beantwortet die Erkennung
    selbst —, sondern ein Körper, der tatsächlich aus lauter losen Dreiecken
    besteht. Die bleiben auch zusammengeführt lose, denn sie liegen wirklich
    nicht aneinander.

    Zwanzig Stellen bekommen einen eigenen Namen, der Rest **eine** Zeile.
    Dreitausend einzeln anklickbare Einträge sind keine Bedienung, und die
    Zuordnung (§21.2) wächst quadratisch in der Zahl der Merkmale.

    Die Schranke daneben ist keine Zierde: Der Test baut seinen Prüfling aus
    ``EDGE_LOOP_LIMIT`` und wanderte damit stillschweigend mit, wenn jemand die
    Grenze auf hunderttausend setzte — er prüfte dann die Aktualität der Zahl
    statt ihrer Richtigkeit. Was die Zahl leisten muss, ist eine Liste, die
    jemand durchgeht; das ist die Zusage, und sie steht hier.
    """
    assert EDGE_LOOP_LIMIT <= 50, (
        "die Grenze ist eine Bedienzahl — was darüber liegt, geht niemand mehr durch"
    )

    count = EDGE_LOOP_LIMIT + 12
    apart = trimesh.util.concatenate(
        [
            trimesh.Trimesh(
                vertices=np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
                + np.array([10.0 * index, 0.0, 0.0]),
                faces=np.array([[0, 1, 2]]),
                process=False,
            )
            for index in range(count)
        ]
    )

    loops = detect_edge_loops(MeshData.of(apart))

    assert len(loops) == EDGE_LOOP_LIMIT + 1, [loop.id for loop in loops]
    summary = loops[-1]
    assert summary.kind == "edge_loop", "das Kontextmenü zum Reparieren hängt an der Art"
    assert summary.params["loops"] == count - EDGE_LOOP_LIMIT, (
        "die Sammelzeile sagt, wie viele Stellen sie zusammenfasst"
    )
    assert summary.params["open_edges"] == 3 * (count - EDGE_LOOP_LIMIT)
    # **Der Ort ist eine echte Stelle, kein Schwerpunkt.** Ein Mittelwert über
    # alle läge zwischen ihnen und damit im Leeren — genau der Fehler, den die
    # Aufteilung in einzelne Schleifen behoben hat (§18.4).
    assert any(
        summary.params["centre"] == loop.params["centre"]
        for loop in detect_edge_loops(MeshData.of(apart))
    )
    assert sum(int(loop.params["open_edges"]) for loop in loops) == 3 * count, (
        "keine offene Kante geht beim Zusammenfassen verloren"
    )


def test_an_edge_loop_keeps_its_number_when_the_body_turns() -> None:
    """Zwei gleich große Schleifen behalten ihre Nummer, wenn das Teil sich dreht.

    An den IDs hängen Ops und Passungen (§21.2), und ``detect_faces`` sagt
    neunzig Zeilen weiter oben ausdrücklich, warum: Eine Nummerierung nach
    Koordinaten überlebt keine Drehung. ``detect_edge_loops`` tat trotzdem
    genau das — bei gleicher Kantenzahl entschied der gerundete Mittelpunkt.

    **Gedreht wird um 180 Grad, und das ist keine Willkür.** Bei zwanzig Grad
    bliebe die linke Schleife links; der Test wäre auch mit der alten
    Sortierung grün und würde eine Zusage prüfen, die er gar nicht auslöst.
    Erst eine Drehung, welche die Reihenfolge *umkehrt*, stellt die Frage.

    Verglichen wird über den mitgedrehten Mittelpunkt: Trägt ``edge_loop_1``
    danach die Stelle, die vorher ``edge_loop_1`` war, meint die ID dieselbe
    Schleife.
    """
    parts = []
    for shift in (-20.0, 20.0):
        box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        box.apply_translation((shift, 0.0, 0.0))
        box.update_faces(
            np.array([index for index, normal in enumerate(box.face_normals) if normal[2] < 0.9])
        )
        parts.append(box)
    body = trimesh.util.concatenate(parts)

    before = detect_edge_loops(MeshData.of(body))
    assert len(before) == 2, "sonst prüft der Test seinen eigenen Aufbau"
    assert before[0].params["open_edges"] == before[1].params["open_edges"], (
        "nur bei gleicher Kantenzahl entscheidet das zweite Kriterium — darum geht es hier"
    )

    turn = trimesh.transformations.rotation_matrix(np.pi, (0.0, 0.0, 1.0))
    turned = body.copy()
    turned.apply_transform(turn)
    after = detect_edge_loops(MeshData.of(turned))

    assert len(after) == 2
    expected = trimesh.transform_points([list(before[0].params["centre"])], turn)[0]
    assert tuple(after[0].params["centre"]) == pytest.approx(tuple(expected), abs=1e-6), (
        "edge_loop_1 meint nach der Drehung die andere Schleife — daran hängen Ops und Passungen"
    )


# --- everything together --------------------------------------------------------


def test_detection_names_everything_it_found() -> None:
    features = detect(plate())

    kinds = {feature.kind for feature in features.values()}
    assert "hole" in kinds
    assert "face" in kinds
    assert all(feature.provenance == "detected" for feature in features.values())
    assert all(identifier == feature.id for identifier, feature in features.items())


# --- was kein Merkmal ist ---------------------------------------------------------


def generated_body() -> MeshData:
    """Ein erzeugtes Netz, wie ein Bildmodell es liefert (siehe tests/data/README)."""
    return normalise(read_mesh((MESHES / "generated_figure.stl").read_bytes(), ".stl"), "mm").mesh


def test_a_generated_mesh_does_not_drown_in_faces() -> None:
    """Der Fund, aus dem ``MIN_FACE_AREA`` entstand.

    Der relative Anteil an der größten Fläche filtert nur bei einem
    konstruierten Teil. Auf einem gleichmäßig facettierten Netz ist jede Facette
    „mindestens zwei Prozent der größten", und die Kugel meldete 180 Flächen.
    Danach war jede Zuordnung mehrdeutig und die Auswertung hielt bei jeder
    Operation an (§21.3) — Weg 3 kam nach der Reparatur nicht weiter.
    """
    features = detect(generated_body())

    # **Erst festhalten, dass überhaupt etwas erkannt wird.** Ohne diese Zeile
    # wäre der Test auch grün, wenn ``detect`` gar nichts mehr liefert — eine
    # gefilterte Teilmenge einer leeren Menge ist leer. Gemessen: drei Kugeln
    # und eine offene Kante.
    assert features, "die Erkennung liefert auf diesem Netz nichts mehr"

    faces = [entry for entry in features.values() if entry.kind == "face"]
    assert not faces, f"{len(faces)} Flächen auf einem organischen Netz"


def test_a_scratch_is_not_a_bore() -> None:
    """Eine Düse legt 0,4 mm breite Bahnen — 0,05 mm hat kein Werkzeug gemacht."""
    body = generated_body()
    assert detect(body), "die Erkennung liefert auf diesem Netz nichts mehr"
    holes = detect_holes(body)

    # **Nicht ``all(... >= 0.5)``.** Auf einem organischen Netz gibt es keine
    # Bohrung, die Liste ist also leer — und ``all`` über eine leere Liste ist
    # wahr. Die Zusicherung war grün, ohne je etwas zu prüfen, und hätte
    # einen Kratzer durchgelassen, der als Ø2 gemeldet wird.
    assert not holes, f"{len(holes)} angebliche Bohrungen auf einem organischen Netz"


def test_the_faces_of_a_real_part_survive_the_limit() -> None:
    """Die Grenze darf nur das treffen, was sie treffen soll."""
    faces = detect_faces(plate())

    assert len(faces) == 6, "eine Platte hat sechs Seiten, und alle sind Flächen"


def test_a_face_keeps_its_centre_when_it_gets_a_hole() -> None:
    """Der Mittelpunkt gehört der Form, nicht der Vernetzung.

    Als Mittel über die Dreiecksschwerpunkte wanderte er zum Loch, weil dort
    viele kleine Dreiecke entstehen: bei einem 60 × 40er Deckel um 16,8 mm.
    Die Zuordnung (§21.2) hielt die Oberseite danach für eine andere Fläche und
    meldete die alte als verwaist — vier Warnungen im Beispielprojekt, ohne
    dass jemand etwas falsch gemacht hätte.
    """
    from app.core.geom.prepare import drill
    from app.core.knowledge import profiles

    box = trimesh.creation.box(extents=(60.0, 40.0, 6.0))
    box.apply_translation((0.0, 0.0, 3.0))
    plain = MeshData.of(box)
    drilled = drill(
        plain,
        position=(-20.0, 0.0, 6.0),
        axis="z",
        diameter=4.5,
        depth=0.0,
        profile=profiles.make_profile("centauri-carbon-2", "petg"),
    ).mesh

    def top_of(mesh: MeshData) -> tuple[float, ...]:
        top = max(detect_faces(mesh), key=lambda face: face.params["centre"][2])
        return tuple(top.params["centre"])

    before, after = top_of(plain), top_of(drilled)

    moved = sum((a - b) ** 2 for a, b in zip(before, after, strict=True)) ** 0.5
    assert moved < 1.0, f"der Mittelpunkt wanderte um {moved:.1f} mm"


def plate_with_pin() -> MeshData:
    """Eine Platte mit einem 6-mm-Stift darauf — das Gegenstück einer Bohrung."""
    base = trimesh.creation.box(extents=(40.0, 40.0, 8.0))
    base.apply_translation((0.0, 0.0, 4.0))
    pin = trimesh.creation.cylinder(radius=3.0, height=12.0, sections=48)
    pin.apply_translation((0.0, 0.0, 12.0))
    return MeshData.of(trimesh.boolean.union([base, pin]))


def test_a_pin_is_recognised_as_one() -> None:
    """§14 braucht beide Enden einer Passung; eine Bohrung allein ist die
    Hälfte.
    """
    found = detect_pins(plate_with_pin())

    assert len(found) == 1
    assert found[0].id == "pin_1"
    assert found[0].kind == "pin"
    assert found[0].params["diameter"] == pytest.approx(6.0, abs=0.02)
    assert found[0].params["axis"][2] == pytest.approx(1.0, abs=0.01)


def test_a_pin_on_a_plate_is_not_reported_as_a_bore() -> None:
    assert detect_holes(plate_with_pin()) == []


def test_a_bore_is_not_reported_as_a_pin() -> None:
    assert detect_pins(plate()) == []


def test_a_small_flat_face_is_not_swallowed_by_the_curve_next_to_it() -> None:
    """Der Fehler hinter dem Stift: ein Deckel aus vielen koplanaren Dreiecken
    ist eine Fläche.

    Nur nach Fläche gegen die größte Fläche des Körpers beurteilt, ist die
    Oberseite eines 6-mm-Stifts unter zwei Prozent einer 40-mm-Platte — sie
    zählte als gekrümmt, schloss sich der Wand an, und die Zylinder-Einpassung
    über Deckel-plus-Wand fand gar nichts.
    """
    from app.core.perceive.features import _large_facet_faces

    body = plate_with_pin().raw
    planar = _large_facet_faces(body)

    top = max(
        (facet for facet in body.facets if len(facet) >= 8),
        key=lambda facet: len(facet),
    )
    assert {int(index) for index in top} <= planar


def test_a_cylinder_has_three_faces_and_not_fifty() -> None:
    """§21.1: „auf die Fläche zeigen" meint eine Fläche, keine Facette.

    Ein Ø-50-Zylinder mit 48 Segmenten trug einundfünfzig Merkmale der Art
    ``face`` — achtundvierzig Mantelstreifen, Deckel, Boden und die Bohrung.
    Fusion zeigt für denselben Körper drei Flächen. Ein Merkmalsbaum von
    ``face_1`` bis ``face_51`` ist keine Auswahl, sondern eine Liste.

    Der Mantel wird jetzt als das gemeldet, was er ist: ein Zylinder, also ein
    ``pin`` — dieselbe Erkennung, die auch die Bohrung findet.
    """
    import trimesh

    body = trimesh.creation.cylinder(radius=25.0, height=20.0, sections=48)
    bore = trimesh.creation.cylinder(radius=4.1, height=40.0, sections=48)
    features = detect(MeshData.of(trimesh.boolean.difference([body, bore])))

    kinds = [entry.kind for entry in features.values()]
    assert sorted(kinds) == ["face", "face", "hole", "pin"], kinds


def test_a_coarse_prism_keeps_its_sides() -> None:
    """Die Grenze zwischen Rundung und Kante liegt bei dreißig Grad.

    Ein Achteck-Prisma ist kein Zylinder — seine acht Seiten sind Flächen, an
    denen jemand etwas ansetzt, und sie einzeln zu melden ist richtig. Erst ab
    zwölf Segmenten (30 Grad) wird aus dem Vieleck eine Rundung.
    """
    import trimesh

    prism = MeshData.of(trimesh.creation.cylinder(radius=25.0, height=20.0, sections=8))

    faces = detect_faces(prism)

    assert len(faces) == 10, "acht Seiten, Deckel und Boden"


def test_components_are_counted() -> None:
    two = normalise(read_mesh((MESHES / "two_components.stl").read_bytes(), ".stl"), "mm").mesh
    assert component_count(two) == 2
    assert component_count(cube()) == 1


# --- gesenkte Bohrung (§21.1) ---------------------------------------------------


def test_a_countersink_does_not_swallow_its_own_bore() -> None:
    """Gefunden am 22.08.2026, und es war schlimmer als „die Senkung fehlt".

    Kegelwand und Bohrungswand hängen zusammen, die Fleckenbildung trennte sie
    nicht, und die Zylindereinpassung über Wand-plus-Kegel kam als nichts
    heraus. Ein gesenktes Loch — die häufigste Bohrung in einem Druckteil —
    stand damit überhaupt nicht in der Szene, und der Agent konnte auf nichts
    zeigen (Leitprinzip 5).
    """
    bores = detect_holes(plate("plate_countersunk.stl"))

    assert len(bores) == 1, f"one bore under the sink: {[bore.id for bore in bores]}"
    assert bores[0].params["diameter"] == pytest.approx(5.2, abs=0.15)
    # Die Tiefe ist die des **Zylinders**, nicht die der Platte: 8 mm minus die
    # 2,4 mm, die der Kegel wegnimmt. Das bleibt auch so — was die Senkung
    # dazutut, steht in ``through`` und nicht in ``depth``.
    assert bores[0].params["depth"] == pytest.approx(5.6, abs=0.15)


def test_a_countersunk_bore_is_still_a_through_hole() -> None:
    """Die zweite Hälfte desselben Fundes, und sie stand bis heute offen.

    ``through`` mass die Höhe der **Zylinderwand** gegen die Dicke des
    Körpers. Bei einer Senkung gehört das obere Stück des Lochs aber zum
    Kegel, nicht zum Zylinder — 5,6 gegen 8 mm, und damit galt die häufigste
    Bohrung eines Druckteils als Sackloch. Das ist keine Frage der Anzeige:
    Eine Passung sucht sich ihr Gegenstück über die Merkmalsarten (§14), und
    in ein Sackloch geht keine durchgesteckte Schraube.

    Entscheidbar ist es, seit der Kegel selbst ein Merkmal ist (§21.1) —
    vorher gab es nichts, was die fehlenden 2,4 mm hätte erklären können.
    """
    bores = detect_holes(plate("plate_countersunk.stl"))

    assert bores[0].params["through"] is True


def test_a_sink_does_not_turn_a_blind_bore_into_a_through_one() -> None:
    """Die Gegenprobe, und sie ist der Grund für die zweite Korpusdatei.

    ``plate_countersunk_blind.stl`` trägt dieselbe Senkung über einem Loch,
    das vor der Unterseite endet: 3,6 mm Zylinder plus 2,4 mm Kegel sind 6 von
    8 mm. Wer die Senkung bloß als „geht durch" verbucht, statt ihre Tiefe zu
    addieren, bekommt diesen Test rot.
    """
    bores = detect_holes(plate("plate_countersunk_blind.stl"))

    assert len(bores) == 1, f"one bore under the sink: {[bore.id for bore in bores]}"
    assert bores[0].params["depth"] == pytest.approx(3.6, abs=0.15)
    assert bores[0].params["through"] is False


def test_the_bore_reads_the_same_alone_as_in_a_whole_detection() -> None:
    """Dieselbe Frage, zwei Wege — und beide müssen dasselbe sagen.

    ``detect`` gibt die einmal gesuchten Einpassungen weiter, ``detect_holes``
    allein sucht sie selbst. Genau an dieser Naht entstand der Fehler schon
    einmal (siehe ``test_the_expensive_search_runs_once_per_detection``), und
    er ist von der teuren Sorte: Jeder Test **innerhalb** eines der beiden Wege
    bleibt grün, während die Anwendung etwas anderes sieht als die
    Kommandozeile.
    """
    mesh = plate("plate_countersunk.stl")

    alone = detect_holes(mesh)[0]
    together = detect(mesh)[alone.id]

    assert alone.params["through"] == together.params["through"]
    assert alone.params["depth"] == pytest.approx(together.params["depth"])


def test_the_same_plate_without_the_sink_was_never_the_problem() -> None:
    """Die Gegenprobe, damit der Test oben nicht auf ein anderes Maß hereinfällt."""
    assert len(detect_holes(plate("plate_holes.stl"))) == 4


def test_the_expensive_search_runs_once_per_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Docstring von ``_cylinders`` verspricht es seit es ihn gibt, die
    Verdrahtung hielt es nicht: ``detect_holes`` und ``detect_pins`` riefen
    jede für sich.

    Gezählt statt gemessen — eine Zeitmessung wäre auf einer belegten Maschine
    kein Wächter (§31).
    """
    from app.core.perceive import features

    calls = 0
    original = features._fitted

    def counted(mesh: MeshData, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(mesh, **kwargs)

    monkeypatch.setattr(features, "_fitted", counted)
    features.detect(plate())

    assert calls == 1, f"the search ran {calls} times for one detection"


def test_the_planar_mask_is_shared_by_fits_and_faces(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die beiden Erkennungsphasen brauchen dieselbe Maske nur einmal.

    Gezählt wird die Rechnung (``_large_facet_faces_read``), nicht die Frage:
    Seit dem 22.09.2026 merkt sich die Hülle die Antwort je Körper, und die
    Durchgangsprobe fragt sie ein weiteres Mal — gerechnet wird trotzdem einmal.
    """
    original = features_module._large_facet_faces_read
    calls = 0

    def counted(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(features_module, "_large_facet_faces_read", counted)
    forget_cache()
    found = detect(plate())

    assert calls == 1
    assert any(feature.kind == "hole" for feature in found.values())
    assert any(feature.kind == "face" for feature in found.values())


# --- Kegel (§21.1) ---------------------------------------------------------------


def test_the_countersink_is_a_feature_of_its_own() -> None:
    """Eine Senkung war bis zum 22.08.2026 ein namenloser Haufen Dreiecke.

    Damit konnte der Agent nicht auf sie zeigen, und Leitprinzip 5 lässt ihm
    keinen zweiten Weg — Koordinaten erzeugt er nicht.
    """
    cones = detect_cones(plate("plate_countersunk.stl"))

    assert len(cones) == 1, f"one sink: {[cone.id for cone in cones]}"
    # Der **Öffnungswinkel**, nicht der Halbwinkel: Eine Senkung heißt „90 Grad".
    assert cones[0].params["angle"] == pytest.approx(90.0, abs=0.5)
    assert cones[0].params["recess"] is True
    # Ø 10 auf die Stelle: der Durchmesser kommt aus den **Ecken** des Flecks
    # und nicht aus den Dreiecksmitten, die ein Stück darunter liegen.
    assert cones[0].params["diameter"] == pytest.approx(10.0, abs=0.05)
    # Und die Mitte liegt auf der Deckfläche, nicht an der Spitze im Nichts.
    assert cones[0].params["centre"][2] == pytest.approx(4.0, abs=0.05)


# --- Kugel und Torus (§21.1, Ausbaustufe §41) -------------------------------------


def test_a_socket_is_recognised_as_a_sphere() -> None:
    """Die Kugel als **Pfanne** — der Fall, den §41 zuerst nennt.

    Eine freistehende Kugel kommt in einem Druckteil kaum vor, eine Pfanne für
    ein Kugelgelenk oder einen Magneten dauernd. Vor dem 22.08.2026 kam an
    ``sphere_socket.stl`` nichts heraus als die sechs Flächen des Blocks: keine
    Falschmeldung, aber auch kein Merkmal, auf das der Agent hätte zeigen
    können (Leitprinzip 5).
    """
    spheres = detect_spheres(plate("sphere_socket.stl"))

    assert len(spheres) == 1, f"one socket: {[sphere.id for sphere in spheres]}"
    # R = 8 im Entwurf; eine Icosphere ist einbeschrieben, die Facetten liegen
    # also ein Stück innen. Gemessen 7,97.
    assert spheres[0].params["diameter"] == pytest.approx(15.94, abs=0.1)
    # Der Mittelpunkt liegt auf der Oberfläche des Blocks, nicht in der Mitte
    # der Kappe — dort, wo eine Kugel läge, die man hineinsetzt.
    assert spheres[0].params["centre"][2] == pytest.approx(7.5, abs=0.05)
    assert spheres[0].params["recess"] is True


def test_an_extruded_curve_wall_is_not_a_sphere_at_any_height() -> None:
    """Ein senkrecht extrudierter Kurvenzug bestimmt keinen Kugelmittelpunkt.

    Die Mantelnormalen haben keine Z-Komponente. Damit hat das Kugelsystem nur
    Rang drei: Eine Verschiebung in Z darf aus demselben Fleck weder eine
    andere Kugel noch ein anderes Güteurteil machen.
    """

    def wall_at(z_offset: float) -> tuple[trimesh.Trimesh, list[int]]:
        angles = np.linspace(-0.04, 0.04, 5)
        lower = np.column_stack(
            [100.0 * np.cos(angles), 100.0 * np.sin(angles), np.full(5, z_offset)]
        )
        upper = lower.copy()
        upper[:, 2] += 10.0
        vertices = np.vstack([lower, upper])
        faces: list[tuple[int, int, int]] = []
        for index in range(4):
            faces.extend(
                [
                    (index, index + 1, index + 6),
                    (index, index + 6, index + 5),
                ]
            )
        body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        return body, list(range(len(faces)))

    for z_offset in (0.0, 20.0):
        body, patch = wall_at(z_offset)
        assert (
            np.linalg.matrix_rank(np.column_stack([body.face_normals[patch], np.ones(len(patch))]))
            == 3
        )
        assert fit_sphere(body, patch) is None


def test_a_ring_is_recognised_as_a_torus() -> None:
    """Die zweite Form, und die teurere: Mit ihr kommt später der Radius einer
    Verrundung, weil eine Verrundung um eine runde Kante ein Torusstück ist.
    """
    tori = detect_tori(plate("torus_ring.stl"))

    assert len(tori) == 1, f"one ring: {[torus.id for torus in tori]}"
    # ``diameter`` ist der Ring — derselbe Schlüssel wie bei jeder anderen Art,
    # weil die Zuordnung die Größe eines Merkmals genau dort liest (§21.2).
    assert tori[0].params["diameter"] == pytest.approx(40.0, abs=0.2)
    assert tori[0].params["tube_diameter"] == pytest.approx(10.0, abs=0.2)
    assert abs(tori[0].params["axis"][2]) == pytest.approx(1.0, abs=0.01)


def test_a_piece_of_a_ring_is_enough_for_the_two_radii() -> None:
    """Ein Torus**stück** reicht der Einpassung, ein ganzer Ring ist nicht nötig.

    Das ist der Unterschied zum früheren Weg, der Ring- und Röhrenradius aus
    den **Rändern** des Flecks las: Ränder hat ein Ausschnitt auch, nur sagen
    sie dort nichts. Der Meridianschnitt eines Torus ist ein Kreis, und eine
    Kreiseinpassung braucht keinen ganzen Kreis.

    Die Zahl, auf die es ankommt, ist der **Röhren**radius — an einer
    Verrundung ist er ihr Radius.
    """
    ring = trimesh.creation.torus(
        major_radius=20.0, minor_radius=5.0, major_sections=96, minor_sections=48
    )
    angle = np.arctan2(ring.triangles_center[:, 1], ring.triangles_center[:, 0])
    quarter = [int(index) for index in np.where((angle > 0.0) & (angle < math.pi / 2.0))[0]]

    fit = fit_torus(ring, quarter)

    assert fit is not None and fit.good, "a quarter of a ring is still a ring"
    assert fit.ring_radius == pytest.approx(20.0, abs=0.1)
    assert fit.tube_radius == pytest.approx(5.0, abs=0.1)


def test_too_small_a_piece_is_refused_instead_of_guessed() -> None:
    """Und darunter wird abgelehnt, nicht geraten (Regel 21, §41).

    Bei einem Zweiundzwanzig-Grad-Ausschnitt liegt der Ringradius um das
    Vierfache daneben — die Einpassung findet dann eine Form, die niemand
    gemeint hat. Auffallen muss das dem **Rückstand**, nicht einem Menschen:
    Er steigt auf 0,078 und damit über ``ROUND_TOLERANCE``, und ``good`` wird
    falsch. Ein Elftel-Ring kommt gar nicht mehr durch die Schutzbedingung.
    """
    ring = trimesh.creation.torus(
        major_radius=20.0, minor_radius=5.0, major_sections=96, minor_sections=48
    )
    angle = np.arctan2(ring.triangles_center[:, 1], ring.triangles_center[:, 0])
    sliver = [int(index) for index in np.where((angle > 0.0) & (angle < math.pi / 8.0))[0]]

    fit = fit_torus(ring, sliver)

    assert fit is None or not fit.good, "a sliver must not pass as a ring"


def test_a_fillet_no_longer_swallows_the_post_it_sits_on() -> None:
    """Das Alltagsteil, an dem die Erkennung bis zum 22.08.2026 nichts fand.

    Eine Säule mit verrundetem Fuß: Die Verrundung schließt **tangential** an —
    das ist ihr Zweck —, und die Fleckenbildung trennt an Knicken. Mantel und
    Kehle lagen deshalb in **einem** Fleck, auf den weder ein Zylinder noch ein
    Torus passte. Sieben ebene Flächen kamen heraus und sonst nichts: keine
    Mantelfläche, auf die der Agent hätte zeigen können, keine Passung, die sie
    findet, kein Eintrag im Steckbrief.
    """
    found = detect(plate("post_with_fillet.stl"))
    pins = [entry for entry in found.values() if entry.kind == "pin"]
    tori = [entry for entry in found.values() if entry.kind == "torus"]

    assert len(pins) == 1, f"the post is a pin: {sorted(found)}"
    assert pins[0].params["diameter"] == pytest.approx(12.0, abs=0.05)
    assert len(tori) == 1, f"the fillet is a torus: {sorted(found)}"
    assert tori[0].params["tube_diameter"] == pytest.approx(6.0, abs=0.05)


@pytest.mark.parametrize("sections", [64, 126])
def test_a_shallow_blind_bore_survives_a_dense_rounded_entrance(sections: int) -> None:
    """Ein unsicherer Torusfit darf die dahinterliegende Bohrungswand nicht verschlucken."""
    from tests.data.make_corpus import rounded_magnet_bore

    body = rounded_magnet_bore(sections)
    assert body.is_volume
    found = detect(MeshData.of(body))
    holes = [feature for feature in found.values() if feature.kind == "hole"]
    assert len(holes) == 1, [(feature.kind, feature.params) for feature in found.values()]
    assert holes[0].params["diameter"] == pytest.approx(9.0, abs=0.02)
    assert not holes[0].params["through"]
    assert holes[0].params["depth"] == pytest.approx(1.3, abs=0.02)


def test_a_rounded_edge_keeps_its_own_radius() -> None:
    """Der Fehlbefund, der schlimmer war als ein fehlender Befund.

    An einem Quader mit **einer** verrundeten Kante R 3 meldete die Erkennung
    einen Zapfen mit Ø 28,92 — fast so breit wie das Teil. Nicht „nichts
    gefunden", sondern etwas Falsches gefunden: §14 nennt einen Zapfen das,
    womit man eine Bohrung paart, und die Operationen aus ``applies_to`` boten
    sich daran an.

    Die Ursache saß **über** der Einpassung, nicht in ihr. Zwei ebene Facetten
    von 1110 und 510 mm² galten als gekrümmt, weil sie die Rundung berühren,
    und hängten sich ihrem Fleck an; die Kreiseinpassung gewichtet quadratisch,
    und vier Punkte in bis zu 25 mm Abstand ziehen einen Kreis von R 3 auf
    14,46. Der Löser war in Ordnung — er bekam den falschen Fleck.
    """
    found = detect(plate("block_with_rounded_edge.stl"))
    fillets = [entry for entry in found.values() if entry.kind == "fillet"]

    assert len(fillets) == 1, f"one rounded edge: {sorted(found)}"
    # **R 3, nicht Ø 6.** Eine Verrundung wird mit ihrem Radius bestellt,
    # gezeichnet und gemessen; der Durchmesser steht daneben, weil die
    # Zuordnung die Größe aus diesem Schlüssel liest (§21.2).
    assert fillets[0].params["radius"] == pytest.approx(3.0, abs=0.05)
    assert not [entry for entry in found.values() if entry.kind == "pin"], (
        "a rounded edge is not a pin — nothing pairs with it (§14)"
    )
    # Und die zwei großen Ebenen daneben sind wieder Flächen.
    assert sum(1 for entry in found.values() if entry.kind == "face") == 6


def test_the_residual_cannot_see_a_blown_up_circle() -> None:
    """Ein Viertelbogen samt Deckeln darf keinen guten Zylinder ergeben.

    Der frühere Schwerpunktfit meldete R89,79 statt R3 bei winzigem
    relativem Restfehler. Die bekannte falsche Eingabe bleibt der Gegenfall;
    ihr falscher Radius ist kein Sollwert des neuen Konturvertrags.
    """
    cylinder = trimesh.creation.cylinder(radius=3.0, height=30.0, sections=96)
    angle = np.arctan2(cylinder.triangles_center[:, 1], cylinder.triangles_center[:, 0])
    quarter = [int(index) for index in np.where((angle > 0.0) & (angle < math.pi / 2.0))[0]]
    axial = np.abs(cylinder.face_normals[quarter, 2])
    assert np.any(axial > 0.9) and np.any(axial < 0.1), "the patch includes caps and mantle"

    fit = fit_cylinder(cylinder, quarter)

    assert fit is None or not fit.good


def test_a_ring_is_not_a_heap_of_flat_faces() -> None:
    """Der Wächter gegen die Reparatur von oben.

    Die zweite Schwelle misst an der **Gesamtoberfläche** und nicht an der
    größten Facette — denn ein Torus besteht nur aus Mantelstreifen, seine
    größte Facette ist selbst einer, und jede läge damit bei fast hundert
    Prozent. Gegen die größte gemessen zerfiel ``torus_ring.stl`` in 288 ebene
    Flächen.
    """
    found = detect(plate("torus_ring.stl"))

    assert [entry.kind for entry in found.values()] == ["torus"], sorted(found)


def test_nothing_that_was_recognised_gets_split_again() -> None:
    """Die Nachtrennung greift **nur**, wo keine Form gefunden wurde.

    Grundsätzlich nachgetrennt zerfiel im Beispielprojekt *Aushöhlen und
    Teilen* ein Kegel in zwei — ein Kegel hat keine feste Krümmung, sein
    Querradius wächst stetig. Zwei gespiegelte Senkungen sehen für die
    Zuordnung ohnehin gleich aus, also hielt die Auswertung an und fragte
    viermal, welches Merkmal ``cone_1`` entspricht. In einem **mitgelieferten
    Beispiel**, dem freundlichsten Weg, den die Anwendung hat.

    Der Wächter dagegen ist die gesenkte Bohrung: ein einziger Kegel, und er
    muss einer bleiben.
    """
    cones = [
        entry for entry in detect(plate("plate_countersunk.stl")).values() if entry.kind == "cone"
    ]

    assert len(cones) == 1, f"one sink, not two: {[cone.id for cone in cones]}"


def test_a_chamfered_bore_is_one_bore_and_not_four() -> None:
    """Der Standardfall jeder Schraubenbohrung, und er lieferte vier Merkmale.

    Die Vereinigung von Bohrer und Fasenkegel setzt Punkte auf die
    Bohrungswand; die Boolesche Operation trianguliert sie darunter mit
    Knicken von siebzig bis neunzig Grad, und die Fleckenbildung trennt dort zu
    Recht. Heraus kamen **vier** Bohrungen für ein Loch — zwei mit
    ``through=True``, zwei mit ``through=False``.

    Für den Nutzer ist das schlimmer als eine fehlende Bohrung: Vier Merkmale
    an derselben Stelle sind für die Zuordnung vier gleich gute Kandidaten,
    also hält die Auswertung an und fragt bei **jeder** Auswertung — mit einer
    Frage, auf die es keine richtige Antwort gibt (§21.3).
    """
    found = detect(plate("plate_chamfer_and_taper.stl"))
    bores = [entry for entry in found.values() if entry.kind == "hole"]

    assert len(bores) == 1, f"one bore, not four: {sorted(found)}"
    assert bores[0].params["diameter"] == pytest.approx(6.0, abs=0.05)
    assert bores[0].params["through"] is True


def test_the_corpus_carries_all_three_kinds_of_cone() -> None:
    """§21.1 nennt drei: Senkung, Fase, Verjüngung. Der Korpus trug nur die
    Senkung, und zwar bis zum 22.08.2026 in zwei Dateien.

    Jeder grüne Lauf sagte damit nichts über die anderen beiden. Hier stehen
    Fase und Verjüngung nebeneinander — die eine ausgehöhlt, die andere
    aufgesetzt.
    """
    cones = detect_cones(plate("plate_chamfer_and_taper.stl"))
    by_shape = {entry.params["recess"]: entry for entry in cones}

    assert len(cones) == 2, f"a chamfer and a taper: {[cone.id for cone in cones]}"
    assert by_shape[True].params["diameter"] == pytest.approx(9.0, abs=0.1)
    assert by_shape[False].params["diameter"] == pytest.approx(10.0, abs=0.1)


def test_a_bore_beside_a_boss_still_goes_through() -> None:
    """Die Dicke des Körpers ist nicht die Dicke an der Bohrung.

    Die alte Prüfung mass die Spanne **aller** Punkte entlang der Achse: An
    einer 10 mm dicken Platte mit einem 15 mm hohen Zapfen daneben kam eine
    Dicke von 25 mm heraus, und die durchgehende Bohrung galt als Sackloch.
    Eine Platte mit einem Dom und einer Bohrung daneben ist ein Alltagsteil.

    Die Prüfung fragt heute nicht mehr nach Dicken, sondern danach, ob ein
    Dreieck über der Achse liegt — dem Zapfen daneben ist das gleichgültig.
    """
    bores = [
        entry
        for entry in detect(plate("plate_chamfer_and_taper.stl")).values()
        if entry.kind == "hole"
    ]

    assert bores[0].params["through"] is True


def test_a_full_cylinder_is_never_taken_for_a_fillet() -> None:
    """Die Gegenprobe, und sie ist über den ganzen Korpus gemessen.

    Getrennt wird an der Überdeckung um die Achse: Bohrungen und Zapfen
    überdecken 345 bis 356 Grad, eine verrundete Quaderkante 90. Dazwischen
    liegt nichts — die Schwelle bei 300 muss nicht kalibriert werden, sie sitzt
    in einem Loch.
    """
    for name in ("plate_holes.stl", "clean_figure.stl", "plate_chamfer_and_taper.stl"):
        found = detect(plate(name))

        # Ein Verbot über eine gefilterte Menge ist grün, solange die Menge
        # leer ist. Erst festhalten, dass auf jedem der drei Körper überhaupt
        # runde Merkmale erkannt werden — sonst prüft die Zeile darunter, dass
        # nichts nichts ist.
        round_ones = [entry for entry in found.values() if "diameter" in entry.params]
        assert round_ones, f"{name}: kein einziges rundes Merkmal erkannt"

        assert not [entry for entry in found.values() if entry.kind == "fillet"], (
            f"{name}: a whole cylinder is not a fillet"
        )


def test_a_thread_is_not_a_stack_of_eight_pins() -> None:
    """Ein M6-Gewinde meldete acht Zapfen, die es nicht gibt.

    Jede Windung ist für sich ein Zylinderstück — koaxial zu den anderen,
    gleich dick, einen Millimeter darüber, also genau die Steigung. §14 nennt
    einen Zapfen das, womit man eine Bohrung paart; mit einem Gewindegang
    paart niemand etwas. Und für die Zuordnung sind acht koaxiale gleich große
    Merkmale acht gleich gute Kandidaten.

    Das Gewinde selbst bleibt: Es entsteht in einem Baustein und trägt seinen
    Namen von dort (§21.1 — „Ein Gewinde sieht sie nicht"). Verworfen wird
    allein, was die Erkennung daneben stellt.
    """
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Gewinde",
        [
            OperationDraft(op="create_box", params={"width": 30.0, "depth": 30.0, "height": 10.0}),
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"size": "M6", "length": 12.0, "internal": False, "z": 5.0},
            ),
        ],
    )
    result = evaluate(
        project.document,
        profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )
    entry = next(iter(result.scene.objects.values()))
    kinds = [feature.kind for feature in entry.features.values()]

    assert "pin" not in kinds, f"a thread turn is not a pin: {sorted(entry.features)}"
    assert kinds.count("thread") == 1, "and the thread itself stays"


def test_a_countersink_is_not_a_sphere() -> None:
    """Die Gegenprobe, und sie ist der Grund für die strengere Schwelle.

    Eine 90°-Senkung passt erstaunlich gut auf eine Kugel: gemessen ein
    Rückstand von 0,054, also **unter** der Schwelle, die für Zylinder und
    Kegel gilt. Die echte Kalotte liefert 0,0003 — zwei Größenordnungen
    darunter. Genau davor warnt §41: Ein Anpassungsverfahren, das Grundformen
    sucht, findet auch welche, die niemand gemeint hat, und die Reihenfolge der
    Prüfungen entscheidet, welchen Namen ein Fleck bekommt.
    """
    found = detect(plate("plate_countersunk.stl"))
    kinds = sorted({feature.kind for feature in found.values()})

    assert "sphere" not in kinds, f"the sink became a sphere: {kinds}"
    assert "torus" not in kinds, f"the sink became a torus: {kinds}"
    # Und was dort steht, steht weiter dort.
    assert "cone" in kinds and "hole" in kinds, kinds


def test_a_bore_is_never_read_as_a_torus() -> None:
    """Ein Zylinder ist ein Torus mit unendlichem Ringradius, die Einpassung
    findet an jeder Bohrung also einen. Sie darf ihn nur nicht behalten.
    """
    assert not detect_tori(plate("plate_holes.stl"))
    assert not detect_spheres(plate("plate_holes.stl"))


def test_a_plain_bore_is_never_read_as_a_cone() -> None:
    """Ein Zylinder ist ein Kegel mit Öffnungswinkel null, also findet die
    Einpassung an jeder Bohrung auch einen.

    Stünde eine Bohrung als Kegel in der Szene, wäre sie für jede
    Bohrungs-Operation unsichtbar — deshalb entscheidet der Winkel und nicht
    die Reihenfolge.
    """
    assert detect_cones(plate()) == []
    assert len(detect_holes(plate())) == 4


def test_a_cone_that_sticks_out_is_not_a_recess() -> None:
    """Dieselbe Form, andere Seite — und die Unterscheidung entscheidet, was
    man damit tun kann.
    """
    base = trimesh.creation.box(extents=(40.0, 40.0, 6.0))
    boss = trimesh.creation.cone(radius=6.0, height=10.0, sections=64)
    boss.apply_translation((0.0, 0.0, 3.0))
    mesh = MeshData.of(trimesh.boolean.union([base, boss]))

    cones = detect_cones(mesh)

    assert len(cones) == 1
    assert cones[0].params["recess"] is False
    # Öffnungswinkel des Kegels aus Radius 6 und Höhe 10: 2 · atan(6/10) = 61,93°.
    assert cones[0].params["angle"] == pytest.approx(61.9, abs=1.5)


def test_the_normals_decide_the_shape_and_not_the_residual() -> None:
    """Der Fall, an dem die naheliegende Reihenfolge scheitert.

    Jede Facette eines aufgesetzten Kegels ist **ein** Dreieck von der
    Grundfläche zur Spitze; ihr Schwerpunkt liegt auf einem Drittel der Höhe,
    und damit liegen alle Schwerpunkte auf einem Kreis. Die
    frühere Zylindereinpassung fand dort einen tadellosen Zylinder. Der
    Konturvertrag muss die Kegelfläche jetzt bereits selbst ablehnen.
    """
    from app.core.perceive.features import fit_cone, fit_cylinder

    base = trimesh.creation.box(extents=(40.0, 40.0, 6.0))
    boss = trimesh.creation.cone(radius=6.0, height=10.0, sections=64)
    boss.apply_translation((0.0, 0.0, 3.0))
    body = MeshData.of(trimesh.boolean.union([base, boss])).raw
    from app.core.perceive.features import _connected_patches, _large_facet_faces

    planar = _large_facet_faces(body)
    curved = [index for index in range(len(body.faces)) if index not in planar]
    patch = max(_connected_patches(body, curved), key=len)

    cylinder = fit_cylinder(body, patch)
    cone = fit_cone(body, patch)

    assert cylinder is None or not cylinder.good, "cone normals and corners do not prove a cylinder"
    # Halbwinkel aus Radius 6 und Höhe 10: atan(6/10) = 30,96°.
    assert cone is not None and cone.half_angle == pytest.approx(30.9, abs=1.0)


def test_one_ring_is_one_feature_and_not_two() -> None:
    """Ein Ring zerfällt in Flecken, und jeder wurde ein eigenes Merkmal.

    Im Bildschirmfoto eines Kunden standen drei Wülste untereinander: Ø 34,09,
    Ø 34,06 und Ø 34,03 mm. Drei Kanten oder eine, dreimal erkannt? Am Korpus
    nachgestellt kam derselbe einzelne Ring in **jeder** geprüften Vernetzung
    als zwei Merkmale heraus — 33,93 und 33,94 bei 48 Segmenten, 33,73 und
    33,75 bei 24. Für die Zuordnung sind zwei Merkmale an derselben Stelle zwei
    gleich gute Kandidaten, also hält die Auswertung an und fragt (§21.3).

    Zylinderflecken werden seit `4ae96ec` zusammengefasst; für Ringe fehlte das
    Gegenstück.
    """
    for sections, tube in ((48, 0.5), (24, 0.5), (96, 1.0)):
        ring = trimesh.creation.torus(
            major_radius=17.0, minor_radius=tube, major_sections=sections, minor_sections=12
        )
        found = [entry for entry in detect(MeshData(raw=ring)).values() if entry.kind == "torus"]

        assert len(found) == 1, f"{sections} Segmente: {[e.params['diameter'] for e in found]}"


def test_two_rings_above_each_other_stay_two() -> None:
    """Die Gegenprobe, und sie entscheidet über das Kriterium.

    Der **Rest** trennt die beiden Fälle nicht: Zwei Hälften eines Rings
    zusammengelegt streuen 0,00040 — und zwei verschiedene Ringe, fälschlich
    zusammengelegt, ebenfalls 0,00040. Was sie trennt, ist der Mittelpunkt.
    """
    lower = trimesh.creation.torus(
        major_radius=17.0, minor_radius=0.5, major_sections=48, minor_sections=12
    )
    upper = trimesh.creation.torus(
        major_radius=17.0, minor_radius=0.5, major_sections=48, minor_sections=12
    )
    upper.apply_translation((0.0, 0.0, 8.0))

    found = [
        entry
        for entry in detect(MeshData(raw=trimesh.util.concatenate([lower, upper]))).values()
        if entry.kind == "torus"
    ]

    assert len(found) == 2
    assert sorted(round(float(entry.params["centre"][2])) for entry in found) == [0, 8]


@pytest.mark.parametrize(
    ("name", "expected"),
    [("plate_holes.stl", 10), ("post_with_fillet.stl", 9), ("torus_ring.stl", 1)],
)
def test_detection_sees_the_same_part_whether_it_arrives_welded_or_not(
    name: str, expected: int
) -> None:
    """Dieselbe Datei, zweimal geladen, muss dieselbe Auskunft geben.

    Der Zwilling des Fundes vom 26.08.2026: ``detect_edge_loops`` fragte die
    **gespeicherte** Topologie statt der geometrischen und meldete an einer
    ungeschweißten STL eine offene Stelle je Dreieck. Das ist behoben — die
    übrigen ``detect_*`` fragten weiter dasselbe Falsche, und dort fällt es
    nicht als Übermaß auf, sondern als **Schweigen**: Roh geladen kam aus
    ``detect`` gar nichts zurück, obwohl dieselbe Datei verschweißt zehn, neun
    und ein Merkmal liefert.

    Ein Übermaß sieht jeder, ein Schweigen niemand — der Kunde liest „keine
    Merkmale erkannt" und hält es für eine Eigenschaft seines Teils. Und er hat
    keine Möglichkeit, es zu bemerken: Ob eine Datei mit gemeinsamen Ecken
    ankommt, entscheidet das Format, nicht er. ``generate.into_project`` lädt
    aus gutem Grund ungeschweißt, also trifft es ausgerechnet Weg 3.

    Geprüft wird auf **Gleichheit beider Wege** und nicht auf eine feste Zahl:
    Was die Erkennung findet, darf sich mit ihr weiterentwickeln — dass die
    Antwort vom Dateiformat abhängt, darf nie wieder passieren.
    """
    path = MESHES / name
    welded = MeshData.of(trimesh.load(path, process=True, force="mesh"))
    unwelded = MeshData.of(trimesh.load(path, process=False, force="mesh"))

    from_welded = detect(welded)
    from_unwelded = detect(unwelded)

    assert len(from_welded) == expected, f"der verschweißte Weg ist der Bezug: {name}"
    assert len(from_unwelded) == len(from_welded), (
        f"{name}: roh {len(from_unwelded)} Merkmale, verschweißt {len(from_welded)} — "
        "die Auskunft hängt am Dateiformat"
    )


def test_the_same_mesh_is_not_examined_twice() -> None:
    """Ein bitgleiches Netz kann keine anderen Merkmale haben.

    Die Erkennung läuft nach **jeder** Operation, und das ist richtig (§21.2):
    Sonst wäre ``hole_3`` in Schritt fünf ein anderes Loch als in Schritt vier.
    Sie lief aber auch dann, wenn die Geometrie gar nicht gerechnet wurde —
    nach einem Treffer im Plattencache. Gemessen an den neun Beispielprojekten,
    je drei Auswertungen wie beim Öffnen: 11,65 s Erkennung, davon **7,52 s auf
    bitgleichen Netzen**.

    Geprüft wird beides, was ein Cache falsch machen kann: dass er antwortet
    (sonst wäre er keiner) und dass er dasselbe antwortet (sonst wäre er
    schlimmer als keiner).
    """
    forget_cache()
    mesh = MeshData.of(trimesh.load(MESHES / "plate_holes.stl", process=False, force="mesh"))

    first = detect(mesh)
    assert first, "ohne erkannte Merkmale prüft der Test nichts"
    second = detect(mesh)

    assert second == first, "dasselbe Netz, andere Merkmale"
    assert second is not first, "der Aufrufer darf sein Ergebnis behalten dürfen"

    # Ein zweites Netz mit denselben Zahlen, aber eigenen Feldern: Der
    # Schlüssel ist der Inhalt und nicht die Objektkennung — ``id()`` wird
    # wiederverwendet, sobald ein Körper freigegeben ist.
    twin = MeshData.of(trimesh.load(MESHES / "plate_holes.stl", process=False, force="mesh"))
    assert detect(twin) == first, "gleicher Inhalt, gleiche Antwort"


def test_a_changed_mesh_is_examined_again() -> None:
    """Und die Gegenrichtung, ohne die der Test oben eine Falle wäre.

    Ein Cache, der auf ein *verändertes* Netz die alte Antwort gibt, ist der
    schlimmste Fall überhaupt: Der Kunde bohrt, und der Merkmalsbaum zeigt
    weiter das Teil von vorher.
    """
    forget_cache()
    body = trimesh.load(MESHES / "plate_holes.stl", process=False, force="mesh")
    before = detect(MeshData.of(body))

    moved = body.copy()
    moved.apply_translation([0.0, 0.0, 7.0])
    after = detect(MeshData.of(moved))

    assert after, "das verschobene Teil hat dieselben Merkmale, nur woanders"
    heights_before = sorted(
        round(float(f.params["centre"][2]), 2) for f in before.values() if "centre" in f.params
    )
    heights_after = sorted(
        round(float(f.params["centre"][2]), 2) for f in after.values() if "centre" in f.params
    )
    assert heights_before, "ohne Höhen misst der Vergleich nichts"
    assert heights_after != heights_before, "das verschobene Netz bekam die alte Antwort"


# ``_face_candidates`` statt ``detect_faces``: Die Erkennung baut ihre Flächen
# seit RM-207 in zwei Schritten (erst alle, billig; nach dem Musterfalten die
# übrigen fertig), und ``detect_faces`` ist der Weg für Aufrufer von außen.
@pytest.mark.parametrize("phase", ["fit_cone", "_face_candidates", "_shapes_on_a_freeform"])
def test_cancelled_recognition_does_not_fill_the_caches(
    monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    """Abbruch im Fit, zwischen Detektoren und vor Veröffentlichung bleibt ohne Teilresultat."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    mesh = plate()
    vertices, faces = mesh.raw.vertices.copy(), mesh.raw.faces.copy()
    signal = CancelSignal()
    forget_cache()
    original = getattr(features_module, phase)
    calls = 0

    def cancel_after_phase(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        result = original(*args, **kwargs)
        signal.cancel()
        return result

    with monkeypatch.context() as patch:
        patch.setattr(features_module, phase, cancel_after_phase)
        with pytest.raises(OperationCancelled):
            detect(mesh, check_cancelled=signal.raise_if_cancelled)

    assert calls == 1, "nach dem Abbruch darf kein weiterer Fleck derselben Phase rechnen"
    assert not features_module._FEATURE_CACHE
    assert not features_module._CACHE_INDICES
    assert not features_module._FREEFORM_DROPPED
    np.testing.assert_array_equal(mesh.raw.vertices, vertices)
    np.testing.assert_array_equal(mesh.raw.faces, faces)
    signal.reset()
    assert detect(mesh, check_cancelled=signal.raise_if_cancelled)


def test_cancelled_recognition_does_not_reorder_a_warm_cache() -> None:
    """Auch ein schneller Cachetreffer achtet den schon verlangten Abbruch."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    forget_cache()
    first, second = cube(), plate()
    detect(first)
    detect(second)
    before = list(features_module._FEATURE_CACHE.items())
    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        detect(first, check_cancelled=signal.raise_if_cancelled)

    assert list(features_module._FEATURE_CACHE.items()) == before


def test_a_long_history_stays_in_the_feature_cache() -> None:
    """Ein warmer langer Verlauf darf den Cache nicht beim Lesen leeren.

    Das Kundenmodell hat 132 verschiedene Zwischenkörper. Mit der früheren
    Grenze von 32 verdrängten die ersten Schritte eines neuen Durchlaufs genau
    die später noch benötigten Einträge; trotz vollständiger Treffer im
    Ergebnis-Cache wurde jedes Merkmal erneut gesucht.
    """
    forget_cache()
    body = trimesh.load(MESHES / "cube_clean.stl", process=False, force="mesh")
    history_length = 132

    for step in range(history_length):
        moved = body.copy()
        moved.apply_translation([float(step) * 3.0, 0.0, 0.0])
        detect(MeshData.of(moved))

    assert len(_FEATURE_CACHE) == history_length, (
        "der Cache muss alle Zwischenkörper des gemessenen Kundenverlaufs halten"
    )


def test_the_cache_keeps_only_what_it_promises() -> None:
    """Die Grenze hält, sonst wächst er über die Laufzeit eines Tages hinaus."""
    forget_cache()
    body = trimesh.load(MESHES / "cube_clean.stl", process=False, force="mesh")

    for step in range(CACHE_LIMIT + 5):
        moved = body.copy()
        moved.apply_translation([float(step) * 3.0, 0.0, 0.0])
        detect(MeshData.of(moved))

    assert len(_FEATURE_CACHE) == CACHE_LIMIT, (
        f"{len(_FEATURE_CACHE)} gemerkte Netze bei einer Grenze von {CACHE_LIMIT}"
    )


def test_the_feature_cache_holds_when_readers_and_writers_meet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auswertung und Vorschau fragen den Merker aus verschiedenen Fäden.

    Nachschlagen und Nachvornerücken waren zwei Schritte: Verdrängte ein
    anderer Faden den Eintrag dazwischen, warf ``move_to_end`` ``KeyError``
    mitten aus der Erkennung. Hier verdrängt jeder Schreibzugriff den ältesten
    Eintrag (Grenze eins), und drei Leser fragen dieselben Netze.
    """
    import sys
    import threading

    monkeypatch.setattr(features_module, "CACHE_LIMIT", 1)
    forget_cache()
    body = trimesh.load(MESHES / "cube_clean.stl", process=False, force="mesh")
    meshes = []
    for step in range(3):
        moved = body.copy()
        moved.apply_translation([float(step) * 3.0, 0.0, 0.0])
        meshes.append(MeshData.of(moved))
    keys = [features_module._mesh_key(mesh) for mesh in meshes]
    errors: list[BaseException] = []
    stop = threading.Event()

    def read() -> None:
        while not stop.is_set():
            for mesh in meshes:
                try:
                    features_module.known_detection(mesh)
                except BaseException as problem:
                    errors.append(problem)
                    return

    def write() -> None:
        for _round in range(3000):
            for key in keys:
                features_module._remember(key, {}, 0, 0, False)

    interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        readers = [threading.Thread(target=read) for _ in range(3)]
        writer = threading.Thread(target=write)
        for thread in (*readers, writer):
            thread.start()
        writer.join()
        stop.set()
        for thread in readers:
            thread.join()
    finally:
        sys.setswitchinterval(interval)
        forget_cache()
    assert not errors, errors[:3]


def test_the_inner_wall_of_a_hollow_box_knows_it_is_inside() -> None:
    """Innen- und Außenwand zeigen in dieselbe Richtung und hießen gleich.

    Handbuchbild vom 02.09.2026, Objektbaum der ausgehöhlten Dose: „Rückseite
    3200 mm²" und „Rückseite 2797 mm²", viermal so — der Kunde konnte die
    Innenwand nur an der Zahl erkennen. Die Wahrnehmung entscheidet jetzt an
    der Stelle, an der sie alle Flächen kennt: Eine Fläche liegt innen, wenn
    eine gleichgerichtete weiter außen liegt.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import detect

    outer = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
    outer.apply_translation((0.0, 0.0, 10.0))
    cavity = trimesh.creation.box(extents=(34.0, 24.0, 20.0))
    cavity.apply_translation((0.0, 0.0, 13.0 + 10.0))  # oben offen, Boden bleibt
    hollow = trimesh.boolean.difference([outer, cavity])
    faces = [f for f in detect(MeshData.of(hollow)).values() if f.kind == "face"]

    def side(normal: tuple[float, float, float], *, inner: bool) -> list:
        return [
            f
            for f in faces
            if tuple(round(v) for v in f.params["normal"]) == normal
            and bool(f.params.get("inner")) is inner
        ]

    # Die Rückwand: außen bei y = +15 zeigt +y; die Innenwand vorn zeigt auch +y.
    assert side((0, 1, 0), inner=False), "die Außenwand nach hinten gilt als außen"
    assert side((0, 1, 0), inner=True), "die Innenwand nach hinten gilt als innen"
    assert side((0, -1, 0), inner=False) and side((0, -1, 0), inner=True)
    # Der Boden: nur eine Fläche zeigt nach unten — außen. Nach oben zeigen
    # zwei: der Rand der Wände bei z = 20 (außen) und der Boden innen bei
    # z = 3 — und der liegt unter dem Rand, also innen. Genau so heißt er im
    # Objektbaum: „Oberseite innen" ist der Grund der Dose.
    assert side((0, 0, -1), inner=False) and not side((0, 0, -1), inner=True)
    assert side((0, 0, 1), inner=False), "der Rand der Wände ist außen"
    assert side((0, 0, 1), inner=True), "der Boden innen liegt unter dem Rand"


def test_a_solid_box_has_no_inner_faces() -> None:
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import detect

    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    faces = [f for f in detect(MeshData.of(box)).values() if f.kind == "face"]

    assert len(faces) == 6
    assert not any(f.params.get("inner") for f in faces)


def test_an_inner_face_is_named_as_such() -> None:
    from app.core.types import Feature
    from app.ui.labels import feature_name

    outer = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"normal": (0.0, 1.0, 0.0), "centre": (0.0, 15.0, 10.0), "area": 800.0},
    )
    inner = Feature(
        id="face_2",
        kind="face",
        provenance="detected",
        params={
            "normal": (0.0, 1.0, 0.0),
            "centre": (0.0, -12.0, 12.0),
            "area": 600.0,
            "inner": True,
        },
    )

    assert feature_name("face_1", outer) != feature_name("face_2", inner)
    assert feature_name("face_1", outer) in feature_name("face_2", inner)


def test_a_fillet_smaller_than_any_tool_is_none() -> None:
    """Dieselbe Schranke wie bei Bohrung und Zapfen — sie fehlte hier.

    **Der Befund (3d-druck-7f, 03.09.2026):** Im Objektbaum eines Kundenmodells
    standen Zeilen mit „Hohlkehle R0,00 mm", dazu eine ganze Leiter nach unten
    — R0,01, R0,03, R0,20. Gemessen an „Blessed Family — Heart Script Decor":
    109 erkannte Verrundungen, die kleinste mit **0,0007 mm** Radius, und
    zweiundzwanzig unter einer Extrusionsbahn (0,42 mm). Das ist Tesselierung
    und keine Kante: Wo ein paar Dreiecke zufällig um eine Achse stehen,
    findet der Fit einen Zylinderausschnitt.

    `MIN_CYLINDER_DIAMETER` gab es längst, mit genau dieser Begründung — „was
    für kein Werkzeug zu klein ist, ist für keine Passung zu klein" —, und sie
    galt für Bohrungen und Zapfen. Der Kommentar bei den Zapfen sagt sogar
    ausdrücklich „dieselbe Schranke wie bei der Bohrung"; die Verrundung war
    die dritte, an die niemand gedacht hat.

    Geprüft wird an einem Quader mit zwei verrundeten Kanten: eine über der
    Schranke, eine darunter. Der Test nimmt sie über die Passungen entgegen,
    damit er ohne den vollen Erkennungslauf auskommt.
    """
    from dataclasses import replace

    from app.core.perceive.features import (
        MIN_CYLINDER_DIAMETER,
        CylinderFit,
        detect_fillets,
    )

    mesh = MeshData(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    gross = CylinderFit(
        axis=(0.0, 0.0, 1.0),
        centre=(0.0, 0.0, 0.0),
        radius=3.0,
        residual=0.0,
        inward=False,
        spread=0.0,
    )
    winzig = replace(gross, radius=MIN_CYLINDER_DIAMETER / 2.0 - 0.01)
    genau = replace(gross, radius=MIN_CYLINDER_DIAMETER / 2.0)

    fläche = tuple(range(6))
    gefunden = detect_fillets(mesh, [(gross, list(fläche)), (winzig, list(fläche))])

    assert [f.params["radius"] for f in gefunden] == [3.0], (
        "was für kein Werkzeug groß genug ist, ist auch keine Verrundung"
    )
    assert [f.id for f in gefunden] == ["fillet_1"], (
        "und die Nummern bleiben lückenlos — eine fillet_2 ohne fillet_1 wäre "
        "ein Verweis ins Leere (§21.2)"
    )

    auf_der_grenze = detect_fillets(mesh, [(genau, list(fläche))])
    assert len(auf_der_grenze) == 1, "genau auf der Schranke zählt noch"


# --- Was der Kunde mit einem erkannten Merkmal tun kann (Panel, 03.09.2026) --------


def test_the_actions_of_a_bore_come_with_their_measured_values() -> None:
    """Die Auskunft fürs Merkmalspanel — eine Liste, kein Nachschlagewerk.

    Robert am 03.09.2026: „evtl noch ein eigenes panel damit man nicht für
    alles rechtsklick machen muss übersichtlich, verständlich innovativ und
    intuitiv." Der Entwurf dazu ist, dass eine geänderte Zahl **die Operation
    ist**: Das Panel zeigt, was Solidon gemessen hat, und der Kunde ändert es.

    Damit muss jedes Feld seinen **heutigen** Wert mitbringen — eine Vorgabe,
    die nicht der gemessene Wert ist, wäre eine stille Änderung, sobald jemand
    auf Übernehmen drückt.

    **Abgeleitet aus dem Register, nicht aus einer zweiten Tabelle.** Welche
    Operationen für eine Merkmalsart gelten, steht in ihren ``applies_to``;
    eine Liste daneben, die dasselbe noch einmal sagt, weiß beim nächsten
    Registereintrag die Hälfte.
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import actions_for
    from app.core.types import Feature

    load_operations()
    bore = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "centre": (-15.0, 0.0, 2.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 8.0,
            "depth": 20.0,
            "through": True,
        },
    )

    actions = actions_for(bore)
    by_op = {entry.op: entry for entry in actions if entry.op}

    assert "move_feature" in by_op, sorted(by_op)
    assert "remove_feature" in by_op
    assert "rotate_feature" in by_op

    move = by_op["move_feature"]
    fields = {field.name: field for field in move.fields}
    assert fields["x"].value == pytest.approx(-15.0), "die Vorgabe ist der gemessene Ort"
    assert fields["y"].value == pytest.approx(0.0)
    assert fields["z"].value == pytest.approx(2.0)
    assert fields["x"].unit == "mm" and fields["x"].kind == "length"
    assert "at_feature" not in fields, "die Kennung wählt das Panel selbst, sie ist kein Feld"

    turn = by_op["rotate_feature"]
    turn_fields = {field.name: field for field in turn.fields}
    assert turn_fields["axis"].kind == "choice"
    assert [value for value, _label in turn_fields["axis"].choices] == ["x", "y", "z"]
    assert turn_fields["angle"].kind == "angle"

    assert by_op["remove_feature"].fields == (), "eine Handlung ohne Felder ist ein Knopf"


@pytest.mark.parametrize("count", (2, 3))
def test_the_move_note_counts_the_actual_cavity_sections(count: int) -> None:
    """Stufenbohrungen nennen ihre zwei oder drei Zylinder, keine erfundene Senkung."""
    from app.core.bootstrap import load_operations
    from app.core.perceive.relations import cavity_chains

    load_operations()
    contour = [[12.0, 0.0], [12.0, 4.0 * count], [2.0 + count, 4.0 * count]]
    for index in range(count, 0, -1):
        contour.append([2.0 + index, 4.0 * (index - 1)])
        if index > 1:
            contour.append([1.0 + index, 4.0 * (index - 1)])
    contour.append([12.0, 0.0])
    mesh = MeshData.of(trimesh.creation.revolve(contour, sections=48))
    features = detect(mesh)
    chains = cavity_chains(features, mesh)
    assert len(chains) == 1
    chain = chains[0]
    assert len(chain) == count
    assert {feature.kind for feature in chain} == {"hole"}

    for feature in chain:
        move = next(
            action
            for action in actions_for(feature, features, mesh=mesh)
            if action.op == "move_feature"
        )
        assert str(move.note) == (
            f"Verknüpft: {count} Abschnitte dieser Öffnung werden gemeinsam verschoben."
        )


def test_feature_actions_do_not_swallow_an_unexpected_registry_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein kaputter vorhandener Eintrag ist keine noch nicht registrierte Operation."""
    from app.core.bootstrap import load_operations
    from app.core.perceive import actions

    load_operations()
    assert actions._spec_or_none("absent_operation") is None
    original_get = actions.REGISTRY.get

    def broken_get(name: str):
        if name == "move_feature":
            raise RuntimeError("registry broken")
        return original_get(name)

    monkeypatch.setattr(actions.REGISTRY, "get", broken_get)
    bore = Feature(id="hole_1", kind="hole", provenance="detected", params={"diameter": 6.0})
    with pytest.raises(RuntimeError, match="registry broken"):
        actions_for(bore)


def test_an_edge_loop_is_told_why_nothing_applies() -> None:
    """Was nicht gilt, kommt **mit** — als Satz, nicht als Lücke.

    Ein Panel, das bei einer Kantenschleife nichts zeigt, lässt den Kunden
    raten, ob die Handlungen fehlen oder vergessen wurden. Eine Zeile
    „Verschieben — eine offene Kantenschleife ist ein Loch im Netz" beantwortet
    die Frage und beendet das Suchen (Entwurf 3d-druck-d4, 03.09.2026).
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import actions_for
    from app.core.types import Feature

    load_operations()
    loop = Feature(
        id="edge_1",
        kind="edge_loop",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "open_edges": 12},
    )

    actions = actions_for(loop)

    assert actions, "auch hier steht etwas — nur eben, warum es nicht geht"
    assert all(entry.op is None for entry in actions), [entry.op for entry in actions]
    assert all(str(entry.reason) for entry in actions), "jede Zeile trägt ihren Grund"
    assert any("Netz" in str(entry.reason) for entry in actions)


def test_no_feature_is_smaller_than_the_tool_that_would_make_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kegel, Kugel und Torus hatten die Werkzeugschranke auch nicht.

    **Der Befund, eine Stunde nach der Verrundung (03.09.2026):** Ich hatte
    die Schranke bei `detect_fillets` nachgetragen und in den Kommentar
    geschrieben, sie habe „hier als Einziger" gefehlt. Gemessen an Roberts
    Modellen stimmte das nicht — `garden-hose-holder.3mf` (392 532 Dreiecke)
    lieferte **1130 Merkmale**: 497 Kugeln, 421 Tori, 183 Kegel, und **257
    davon trugen ein Maß unter einer Extrusionsbahn** (0,42 mm), der kleinste
    Kegel mit 0,0074 mm.

    Der Suchfehler dahinter ist der lehrreiche Teil: Ich hatte nach den
    Aufrufern derselben *Zylinder*-Einpassung gesucht und damit genau die drei
    Arten übersehen, die eine andere benutzen. Danach 834 Merkmale, keines
    mehr unter einer Bahn.

    Robert am selben Tag: „wir brauchen auch nur Merkmale usw, die auch von
    der Größenordnung zum 3D-Drucker passen und sinnvoll sind."

    Beim Torus entscheidet das **kleinere** der beiden Maße: Ein Ring von
    40 mm aus einem Rohr von drei Zehnteln ist nichts, was ein Drucker legen
    kann.
    """
    from dataclasses import replace

    from app.core.perceive.features import (
        MIN_CYLINDER_DIAMETER,
        ConeFit,
        SphereFit,
        TorusFit,
        detect_cones,
        detect_spheres,
        detect_tori,
    )

    mesh = MeshData(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    fläche = list(range(6))
    winzig = MIN_CYLINDER_DIAMETER / 2.0 - 0.01
    genau = MIN_CYLINDER_DIAMETER / 2.0

    kegel = ConeFit(
        axis=(0.0, 0.0, 1.0),
        apex=(0.0, 0.0, 0.0),
        centre=(0.0, 0.0, 0.0),
        half_angle=45.0,
        radius=3.0,
        residual=0.0,
        recess=False,
    )
    # Dieser Test isoliert die Werkzeuggröße. Die geometrische Kegelgüte prüft
    # ``test_cone_fit_quality.py`` an echten Flächen statt an Würfelflächen.
    monkeypatch.setattr(features_module, "_cone_is_recognisable", lambda *_args, **_kwargs: True)
    gefunden = detect_cones(mesh, [(kegel, fläche), (replace(kegel, radius=winzig), fläche)])
    assert [f.params["diameter"] for f in gefunden] == [6.0], "ein Kegel unter Werkzeuggröße"
    assert [f.id for f in gefunden] == ["cone_1"], "und die Nummern bleiben lückenlos"
    assert len(detect_cones(mesh, [(replace(kegel, radius=genau), fläche)])) == 1

    kugel = SphereFit(centre=(0.0, 0.0, 0.0), radius=3.0, residual=0.0, recess=False)
    # Dieser Test isoliert die Werkzeuggröße. Die geometrische Kugelgüte prüft
    # ``test_sphere_fit_quality.py`` an echten Flächen statt an Würfelflächen.
    monkeypatch.setattr(features_module, "_sphere_is_recognisable", lambda *_args, **_kwargs: True)
    gefunden = detect_spheres(mesh, [(kugel, fläche), (replace(kugel, radius=winzig), fläche)])
    assert [f.params["diameter"] for f in gefunden] == [6.0], "eine Kugel unter Werkzeuggröße"
    assert [f.id for f in gefunden] == ["sphere_1"]
    assert len(detect_spheres(mesh, [(replace(kugel, radius=genau), fläche)])) == 1

    torus = TorusFit(
        axis=(0.0, 0.0, 1.0),
        centre=(0.0, 0.0, 0.0),
        ring_radius=8.0,
        tube_radius=2.0,
        residual=0.0,
        recess=False,
    )
    # Entsprechend gehört die Torusgüte in ``test_torus_fit_quality.py``.
    monkeypatch.setattr(features_module, "_torus_is_recognisable", lambda *_args, **_kwargs: True)
    # **Der Ring ist groß, die Röhre nicht** — genau der Fall, den ein Blick
    # allein auf ``diameter`` durchgelassen hätte.
    dünn = replace(torus, tube_radius=winzig)
    gefunden = detect_tori(mesh, [(torus, fläche), (dünn, fläche)])
    assert [f.params["tube_diameter"] for f in gefunden] == [4.0], (
        "ein Ring von 16 mm aus einem Rohr von einem Viertel ist nicht druckbar"
    )
    assert [f.id for f in gefunden] == ["torus_1"]
    # Und andersherum: winziger Ring, dicke Röhre — auch das ist nichts.
    gestaucht = replace(torus, ring_radius=winzig)
    assert detect_tori(mesh, [(gestaucht, fläche)]) == []


def test_the_operation_refuses_exactly_what_the_panel_greys_out() -> None:
    """Anschluss: Hinsehen und Ausführen antworten dasselbe.

    Das Panel graut eine Zeile aus und schreibt einen Grund daneben; der Kern
    lehnt denselben Aufruf ab und nennt einen Grund. Solange beides aus
    derselben Tabelle kommt, kann es nicht auseinanderlaufen — und dass es aus
    derselben kommt, prüft dieser Test und nicht ein Kommentar.

    Der Fall, den er fängt: Bis zum 03.09.2026 führte ``geom.prepare_ops`` eine
    zweite Ausgabe der Gründetabelle mit denselben fünf Sätzen. Zwei davon
    waren dort veraltet, und niemand hätte es gemerkt — ein Satz, den nur der
    Chat zu sehen bekommt, wird von keinem Bildschirmfoto widerlegt.
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive import actions
    from app.core.perceive.actions import ACTION_ORDER, actions_for, reason_against
    from app.core.registry import FEATURE_KINDS
    from app.core.types import Feature

    load_operations()
    for kind in FEATURE_KINDS:
        feature = Feature(
            id=f"{kind}_1",
            kind=kind,
            provenance="detected",
            params={"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "diameter": 6.0},
        )
        for row, action in zip(ACTION_ORDER, actions_for(feature), strict=True):
            for op in row:
                against = reason_against(op, kind)
                if action.op == op:
                    assert against is None, f"{kind}/{op}: das Panel bietet es an"
                else:
                    assert against is not None, f"{kind}/{op}: das Panel bietet es nicht an"
                    assert str(against), f"{kind}/{op}: der Grund ist leer"
                    # **Nicht leer ist zu wenig.** Der Auffangsatz
                    # ``_UNKNOWN_KIND`` ist nicht leer und sagt trotzdem nichts
                    # („Für diese Art von Merkmal gibt es noch keine
                    # Handlung"). Genau daran ist ``thread`` bis zum 10.09.2026
                    # vorbeigelaufen: fünf Zeilen, fünfmal derselbe
                    # Nichtsatz, und dieser Test blieb grün. Regel 17 verlangt
                    # einen Handlungsvorschlag, keinen belegten Platz.
                    assert against is not actions._UNKNOWN_KIND, (
                        f"{kind}/{op}: der Auffangsatz ist kein Grund (Regel 17)"
                    )


def test_a_torus_carries_the_five_handlings_and_only_the_slot_is_refused() -> None:
    """Ein Ring fiel bis zum 03.09.2026 in den Auffangsatz, und bis zum 21.09.2026 stand
    an ihm jede Zeile grau: „hat nichts, woran sich einzeln etwas ändern ließe".

    Seit P2.6 tragen Wulst und Kehle Versetzen, Ändern, Drehen, Verdoppeln und
    Entfernen in beiden Kernen (``prepare_ops._move_torus`` und Geschwister).
    Was bleibt, ist das Langloch — gezogen wird ein Loch, und ein Ring hat
    keines — mit seinem eigenen Satz, und der Ring, der der ganze Körper ist
    (``tests/test_torus_feature_ops.py``).
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import actions_for
    from app.core.types import Feature

    load_operations()
    ring = Feature(
        id="torus_1",
        kind="torus",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 12.0,
            "tube_diameter": 3.0,
            "recess": False,
        },
    )

    actions = actions_for(ring)

    offered = {entry.op for entry in actions if entry.op is not None}
    assert offered == {
        "move_feature",
        "resize_feature",
        "rotate_feature",
        "duplicate_feature",
        "remove_feature",
    }, [(entry.op, str(entry.reason)) for entry in actions]
    refused = [entry for entry in actions if entry.op is None]
    assert len(refused) == 1 and "Ring" in str(refused[0].reason), [
        str(entry.reason) for entry in refused
    ]
    # Das Feld für die Rohrdicke steht mit dem gemessenen Wert da.
    resize = next(entry for entry in actions if entry.op == "resize_feature")
    tube = next(field for field in resize.fields if field.name == "tube_diameter")
    assert tube.value == 3.0


def test_the_panel_offers_duplicating_beside_the_original() -> None:
    """Die Vorgabe ist hier **nicht** der gemessene Wert, und das mit Absicht.

    Sonst gilt im Panel die gemessene Zahl (``_FROM_FEATURE``), damit ein Klick
    auf Übernehmen nichts still ändert. Beim Verdoppeln wäre die gemessene
    Mitte die Stelle, an der das Merkmal schon liegt: eine Boolesche auf sich
    selbst, ein Schritt im Verlauf und dasselbe Teil im Bild. Um einen
    Durchmesser versetzt liegt die Kopie neben dem Original und ist zu sehen
    (Vorschlag 3d-druck-d4, 03.09.2026).

    Y und Z bleiben dagegen gemessen — versetzt wird in **eine** Richtung, und
    welche das ist, soll man an der Zahl erkennen.
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import actions_for
    from app.core.types import Feature

    load_operations()
    bore = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "centre": (-15.0, 2.0, 3.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 8.0,
            "depth": 20.0,
            "through": True,
        },
    )

    row = next(entry for entry in actions_for(bore) if entry.op == "duplicate_feature")
    fields = {field.name: field.value for field in row.fields}

    assert fields["x"] == pytest.approx(-7.0), fields
    assert fields["y"] == pytest.approx(2.0), fields
    assert fields["z"] == pytest.approx(3.0), fields


def test_one_countersink_is_one_cone(profile: Profile) -> None:
    """Eine Senkung stand dreimal im Objektbaum.

    **Befund 3d-druck-a0, 03.09.2026**, beim Gegenlesen des Changelogs
    gefunden und nicht bei einer Suche danach: Ein Quader mit **einer**
    durchgehenden Bohrung Ø 6 und **einer** Senkung Ø 12 lieferte **drei**
    Kegel.

    | | Dreiecke | Ø | Achse | Halbwinkel |
    |---|---|---|---|---|
    | cone_1 | 56 | 11,98 | Z | 44,94° |
    | cone_2 | 8 | 11,98 | Z | 44,94° |
    | cone_3 | 37 | 12,88 | 3° verkippt | 47,14° |

    Die drei Flecken sind **disjunkt** — zusammen 101 Dreiecke, keine
    gemeinsame Fläche. Es war also ein Mantel in drei Stücken und kein
    dreifacher Fit; der Unterschied entscheidet, ob eine Zusammenführung die
    Antwort ist oder eine bessere Einpassung.

    **Das dritte Geschwister ohne die Regel:** `_merged_cylinders` gibt es seit
    je, `_merged_tori` seit einem Kundenbild mit drei Wülsten — für den Kegel
    hat sie niemand gebaut. Dieselbe Familie wie die Werkzeugschranke, die
    Bohrung und Zapfen hatten und Verrundung, Kegel, Kugel und Torus nicht.

    Warum es dem Kunden weh tut: Drei Senkungen, wo eine ist. Er klickt eine
    an, und die Operationen antworten je nach Zeile verschieden — zwei lehnen
    mit gutem Grund ab, die dritte ändert 0,4 mm³ an einer Stelle, die er nicht
    gemeint hat.

    Geprüft wird beides: dass eine Senkung **eine** wird, und dass zwei
    Senkungen **zwei** bleiben.

    **Was dieser Test ausdrücklich nicht misst:** :data:`CONE_SAME_ANGLE`.
    Gegengeprobt — die Schranke entschärft, und der Test bleibt grün. Das ist
    kein Mangel, sondern die Sache selbst: Sie ist ein Vorfilter, der einen
    groben Ausreißer abfängt, bevor ein Fit dafür gerechnet wird. Getrennt
    wird über die Spitze und darüber, dass der gemeinsame Fit ``good`` bleibt
    — und **das** misst der zweite Teil hier. Wer die Winkelschranke prüfen
    will, braucht zwei Kegel mit derselben Spitze und derselben Achse bei
    verschiedenem Winkel; die schneiden einander und kommen an einem Körper
    nicht vor.
    """
    from app.core.geom.prepare_ops import countersink, drill

    def with_a_countersink(body: MeshData, x: float) -> MeshData:
        bored = drill(
            body,
            position=(x, 0.0, 10.0),
            axis="z",
            diameter=6.0,
            profile=profile,
            compensate=False,
        ).mesh
        return countersink(
            bored, position=(x, 0.0, 10.0), axis="z", diameter=12.0, profile=profile
        ).mesh

    block = MeshData(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))

    single = detect_cones(with_a_countersink(block, 15.0))
    assert len(single) == 1, (
        f"eine Senkung ist ein Kegel, nicht {len(single)} — "
        f"Ø {[round(float(f.params['diameter']), 2) for f in single]}"
    )
    assert float(single[0].params["diameter"]) == pytest.approx(12.0, abs=0.15), (
        "und er trägt das Maß der Senkung, nicht das eines Ausschnitts"
    )
    assert len(single[0].face_indices) > 90, "der zusammengeführte Fleck trägt den ganzen Mantel"

    # **Die Gegenprobe gehört in denselben Test**: Eine Zusammenführung, die
    # zu viel zusammenführt, sieht am ersten Fall genauso gut aus.
    both = with_a_countersink(with_a_countersink(block, -15.0), 15.0)
    pair = detect_cones(both)
    assert len(pair) == 2, f"zwei Senkungen bleiben zwei, nicht {len(pair)}"
    apart = abs(float(pair[0].params["centre"][0]) - float(pair[1].params["centre"][0]))
    assert apart == pytest.approx(30.0, abs=0.5), "und zwar an ihren beiden Orten"


def test_the_cache_counts_weight_and_not_only_entries() -> None:
    """Die Cache-Grenze zählte Einträge, und die kosten sehr verschieden viel.

    **Gemessen am 03.09.2026**, angestoßen von Roberts Frage nach Dingen, die
    gesetzt und nie abgeräumt werden: Ein Eintrag für
    `garden-hose-holder.3mf` (392 532 Dreiecke, 797 Merkmale) wiegt **3,9 MiB**
    — davon 2,7 allein an Flächenindizes, 97 425 Stück zu je 28 Byte. Bei
    :data:`CACHE_LIMIT` von 256 hielte der Cache damit **991 MiB**, und der
    Kundenverlauf, mit dem die 256 begründet sind (132 verschiedene Netze),
    käme auf gut 500.

    Abgeräumt **wurde** also — die Grenze zählte nur das Falsche. Für ein
    kleines Teil mit tausend Indizes je Eintrag sind 256 Einträge sieben
    Megabyte, und dort soll der Cache voll ausgenutzt werden; für ein großes
    kostet derselbe Zähler das Hundertfache.

    Geprüft wird deshalb beides: dass die Anzahl die kleinen weiter deckelt,
    und dass ein einzelner Eintrag über der Gewichtsgrenze trotzdem bleibt —
    ihn wegzuwerfen hieße, ihn beim nächsten Aufruf sofort neu zu rechnen, und
    der Cache wäre nicht begrenzt, sondern aus.
    """
    from app.core.perceive.features import (
        _CACHE_INDICES,
        _FEATURE_CACHE,
        CACHE_INDEX_LIMIT,
        CACHE_LIMIT,
        detect,
        forget_cache,
    )

    forget_cache()
    for step in range(CACHE_LIMIT + 8):
        # Jeder Körper ein anderes Maß, damit jeder einen eigenen Schlüssel hat.
        detect(MeshData(trimesh.creation.box(extents=(10.0 + step * 0.01, 10.0, 10.0))))

    assert len(_FEATURE_CACHE) == CACHE_LIMIT, "die Anzahl deckelt die kleinen weiter"
    assert len(_CACHE_INDICES) == len(_FEATURE_CACHE), (
        "und der Gewichtszähler läuft mit — sonst wächst er, während der Cache verdrängt"
    )
    assert sum(_CACHE_INDICES.values()) < CACHE_INDEX_LIMIT, (
        "kleine Körper kommen der Gewichtsgrenze nicht nahe"
    )

    # Ein einzelner Eintrag bleibt, auch wenn er für sich schwer ist.
    forget_cache()
    detect(MeshData(trimesh.creation.icosphere(subdivisions=5)))
    assert len(_FEATURE_CACHE) == 1
    assert sum(_CACHE_INDICES.values()) > 0, "und sein Gewicht steht im Zähler"

    # Und Vergessen räumt beide Seiten ab. Ein Zähler, der einen Eintrag
    # überlebt, ist genau die Sorte Rest, um die es hier geht.
    forget_cache()
    assert not _FEATURE_CACHE and not _CACHE_INDICES


def test_the_support_cache_lets_go_of_a_dead_body() -> None:
    """Die gemerkten Antworten eines Körpers sterben mit ihm — nicht erst mit der Grenze.

    **Gemessen am 21.09.2026:** Vier Ikosphären nacheinander erkannt, danach
    369 MiB an Stützpunktlesungen, Flecken und Abdrücken zu Netzen, die
    niemand mehr hatte — der Merker fiel erst bei 4096 Einträgen je Frage.
    Jeder Körper führt jetzt seine Schlüssel, und ``weakref.finalize`` räumt
    sie aus, sobald er stirbt.
    """
    import gc

    from app.core.perceive import features as module

    forget_cache()
    mesh = MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=5.0))
    body = mesh.raw
    key = id(body)
    detect(mesh)
    remembered = {
        name: sum(1 for entry in answers if entry[0] == key)
        for name, answers in module._SUPPORT_CACHE.items()
    }
    assert sum(remembered.values()) > 0, "die Vorbedingung: der Körper hat Antworten hinterlassen"
    assert key in module._MEMORIES and module._MEMORIES[key].answers
    assert module._DIGESTS, "und Abdrücke seiner Fleckenlisten"

    del mesh, body
    gc.collect()

    assert key not in module._MEMORIES, "der Merker des toten Körpers ist weg"
    assert not [
        entry for answers in module._SUPPORT_CACHE.values() for entry in answers if entry[0] == key
    ], "und keine seiner Antworten steht mehr im Stützcache"
    assert not module._DIGESTS, "auch die Abdrücke seiner Listen sind fort"


def test_a_reader_in_one_thread_keeps_its_key_while_a_writer_evicts_in_another(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``get`` und ``move_to_end`` sind zwei Schritte — dazwischen darf niemand verdrängen.

    Das Merkmalfenster fragt ``fillet_blocked`` → ``detect_faces`` im
    Hauptfaden, während der Arbeiter dieselbe Frage für die nächste Auswertung
    stellt. Ohne Schloss verdrängte der Schreiber den Schlüssel zwischen den
    zwei Schritten des Lesers, und der bekam einen ``KeyError`` (Review
    perceive #7, 21.09.2026). Nachgestellt mit einem Wörterbuch, das den Leser
    im ersten Schritt anhalten lässt, bis der Schreiber dran war — oder, mit
    Schloss, bis er es aufgibt zu warten.
    """
    import threading
    from collections import OrderedDict

    from app.core.perceive import features as module

    body = trimesh.creation.box()
    evicted = threading.Event()

    class Hooked(OrderedDict):
        def __contains__(self, key: object) -> bool:
            present = super().__contains__(key)
            if present:
                evicted.wait(0.3)
            return present

        def get(self, key, default=None):  # type: ignore[override]
            value = super().get(key, default)
            if value is not default:
                evicted.wait(0.3)
            return value

    forget_cache()
    monkeypatch.setattr(module, "_SUPPORT_CACHE", {"probe": Hooked()})
    monkeypatch.setattr(module, "CACHE_LIMIT_PER_QUESTION", 1)
    assert module.remembered("probe", body, [0], lambda: "eins") == "eins"
    results: list[str] = []

    def reader() -> None:
        results.append(module.remembered("probe", body, [0], lambda: "neu gerechnet"))

    def writer() -> None:
        module.remembered("probe", body, [1], lambda: "zwei")
        evicted.set()

    reading = threading.Thread(target=reader)
    writing = threading.Thread(target=writer)
    reading.start()
    writing.start()
    reading.join(5.0)
    writing.join(5.0)
    assert results == ["eins"], "der Leser bekommt seine gemerkte Antwort, keinen KeyError"


def test_the_planar_faces_of_a_body_are_read_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_large_facet_faces`` rechnet je Körper einmal — und gibt jedem seine eigene Menge.

    Jeder Klick auf eine Bohrung fragte sie zweimal, je 0,17 s an der
    Lochplatte mit 360 000 Dreiecken (Review Paket D, 22.09.2026). Die
    lokale Erkennung mit ``requested`` oder Flächenbudget bleibt ungemerkt:
    Sie fragt nach anderen Flecken.
    """
    from app.core.perceive import features as module

    mesh = plate("plate_countersunk.stl")
    body = mesh.raw
    runs = 0
    real = module._large_facet_faces_read

    def counted(*args: object, **rest: object) -> object:
        nonlocal runs
        runs += 1
        return real(*args, **rest)

    monkeypatch.setattr(module, "_large_facet_faces_read", counted)
    forget_cache()
    first = module._large_facet_faces(body)
    assert first and runs == 1
    second = module._large_facet_faces(body)
    assert second == first and runs == 1, "der zweite Aufruf liest die Antwort des ersten"
    second.clear()
    assert module._large_facet_faces(body) == first, "und jeder bekommt seine eigene Menge"


def test_the_welded_reading_of_an_unstitched_mesh_is_made_once() -> None:
    """Eine ungeschweißte STL wird je Körper einmal verschweißt — nicht bei jedem Klick.

    Merkmalfenster, Steckbrief und Ansicht fragen nach jedem Klick nach der
    Geometrie; bis zum 22.09.2026 schweißte jede Frage neu, mit einem neuen
    Körper, an dem kein Merker eine Antwort fand. Ein geschweißtes Netz kommt
    unverändert zurück und hinterlässt keinen Eintrag, der es festhielte.
    """
    from app.core.perceive import features as module

    stitched = MeshData.of(trimesh.creation.box(extents=(20.0, 30.0, 40.0)))
    forget_cache()
    assert module._one_body(stitched) is stitched
    assert id(stitched.raw) not in module._MEMORIES, "ein geschweißtes Netz merkt sich nichts"

    loose = trimesh.creation.box(extents=(20.0, 30.0, 40.0))
    loose = trimesh.Trimesh(
        vertices=loose.vertices[loose.faces].reshape(-1, 3),
        faces=np.arange(len(loose.faces) * 3).reshape(-1, 3),
        process=False,
    )
    mesh = MeshData.of(loose)
    assert not module.fully_stitched(mesh.raw), "die Vorbedingung: ungeschweißt"
    welded = module._one_body(mesh)
    assert welded is not mesh and welded.raw.is_watertight
    assert module._one_body(mesh) is welded, "dieselbe verschweißte Fassung beim zweiten Mal"
    other = module._one_body(MeshData.of(loose.copy()))
    assert other is not welded, "ein anderer Körper bekommt seine eigene"


def test_every_fitted_kind_asks_the_same_question() -> None:
    """Die Werkzeugschranke wird an **einer** Stelle gefragt, nicht an sechs.

    **Der Anlass ist ein Zwilling meiner eigenen Arbeit vom selben Tag
    (03.09.2026):** `_too_small_to_make` entstand, damit die nächste
    Merkmalsart die Frage beantworten **muss** statt sie zu übersehen — und
    bekam sie nur bei den drei Erkennern, die an dem Tag neu dazukamen. Kegel,
    Kugel und Torus riefen die Funktion; Bohrung, Zapfen und Verrundung
    verglichen weiter von Hand gegen `MIN_CYLINDER_DIAMETER`.

    Dieselbe Bedingung, dasselbe Ergebnis — und trotzdem der Fehler, gegen den
    die Funktion gebaut war: Wer fragt „wer ruft `_too_small_to_make` nicht?",
    bekommt drei Namen und hält sie für die Lücke. **Eine halbe
    Vereinheitlichung ist schlechter als keine, weil sie vollständig
    aussieht.**

    Dieser Wächter prüft deshalb den Quelltext und nicht das Verhalten: Die
    Konstante darf außerhalb ihrer eigenen Definition und der einen Funktion
    nirgends mehr verglichen werden.
    """
    import re

    import app.core.perceive.features as modul

    quelle = Path(modul.__file__).read_text(encoding="utf-8")

    # Zeilen, die die Konstante in einem Vergleich benutzen — Kommentare und
    # Docstrings zählen nicht, sie dürfen sie beim Namen nennen.
    vergleiche = [
        zeile.strip()
        for zeile in quelle.splitlines()
        if "MIN_CYLINDER_DIAMETER" in zeile
        and not zeile.lstrip().startswith(("#", "*", '"', "'"))
        and re.search(r"[<>=!]=|<|>", zeile)
    ]

    assert vergleiche == ["return size < MIN_CYLINDER_DIAMETER"], (
        "die Schranke wird nur in _too_small_to_make verglichen, sonst nirgends: "
        + "; ".join(vergleiche)
    )


def test_a_socket_stays_a_socket_when_the_mesh_gets_finer(profile: Profile) -> None:
    """Eine Kugelpfanne wurde zur Senkung, sobald das Netz fein genug war.

    **Der Fall (03.09.2026), und er ist der unangenehmste von heute:** Ein
    feineres Netz machte die Erkennung *schlechter*. Dieselbe Pfanne Ø 16 in
    demselben Quader:

    | Netz | Kegel-Rückstand | Kugel-Rückstand | erkannt als |
    |---|---|---|---|
    | 482 Dreiecke | 0,0891 | 0,00049 | Kugel |
    | 1602 Dreiecke | **0,0779** | 0,00009 | **Senkung** |
    | 5746 Dreiecke | 0,0736 | 0,00002 | **Senkung** |

    Der Kegelzweig wird vor dem Kugelzweig gefragt, und sein Rückstand rutscht
    mit steigender Feinheit unter `CONE_TOLERANCE` (0,08). Bei 0,0891 fiel er
    durch und die Pfanne erreichte die Kugel; bei 0,0779 nicht mehr.

    Heruntergeladene Modelle sind fein vernetzt — der Fall trifft also genau
    die Dateien, mit denen ein Kunde ankommt. Im Objektbaum stand dann
    „Senkung", und die Operationen behandelten eine Pfanne wie eine Bohrung.

    **Die Reihenfolge bleibt, die Kugel muss sich den Vortritt verdienen:** Sie
    verdrängt den Kegel nur, wenn sie um Größenordnungen besser passt
    (`SPHERE_BEATS_CONE`). An einer echten Senkung ist der Kegel der bessere
    Fit — Verhältnis 0,7 —, an einer Pfanne liegt es bei 182 aufwärts.

    Geprüft wird beides, und das zweite ist das wichtigere: dass eine echte
    Senkung eine Senkung bleibt.
    """
    from app.core.geom.prepare_ops import countersink, drill
    from app.core.perceive.features import detect_cones, detect_spheres

    def with_a_socket(fineness: int) -> MeshData:
        block = trimesh.creation.box(extents=(60.0, 60.0, 20.0))
        ball = trimesh.creation.icosphere(subdivisions=fineness, radius=8.0)
        ball.apply_translation((0.0, 0.0, 10.0 + 8.0 - 4.0))
        return MeshData(trimesh.boolean.difference([block, ball]))

    for fineness in (3, 4):
        mesh = with_a_socket(fineness)
        balls = detect_spheres(mesh)
        cones = detect_cones(mesh)
        assert len(balls) == 1, (
            f"Feinheit {fineness}: die Pfanne ist eine Kugel, gefunden {len(balls)} "
            f"(und {len(cones)} Kegel)"
        )
        assert balls[0].params["recess"] is True, "und zwar eine Pfanne, keine Kuppel"
        assert not cones, f"Feinheit {fineness}: keine Senkung, sondern eine Pfanne"

    # **Die Gegenrichtung, und sie trägt den Fix:** Eine echte Senkung darf
    # nicht zur Kugel werden. Ohne diese Hälfte wäre der Fix eine Verschiebung
    # des Fehlers und keine Behebung.
    block = MeshData(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))
    bored = drill(
        block,
        position=(0.0, 0.0, 10.0),
        axis="z",
        diameter=6.0,
        profile=profile,
        compensate=False,
    ).mesh
    sunk = countersink(
        bored, position=(0.0, 0.0, 10.0), axis="z", diameter=12.0, profile=profile
    ).mesh
    assert detect_cones(sunk), "eine Senkung bleibt eine Senkung"
    assert not detect_spheres(sunk), "und wird keine Pfanne"


def test_a_sphere_that_beats_a_cone_is_fitted_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Gegenprobe zum Vortritt der Kugel zählt die teure Einpassung.

    Ein feines Kugelsegment besteht den Kegelfit, wird aber wegen seines viel
    kleineren Kugelrückstands als Kugel erkannt. Derselbe Fleck braucht dafür
    keine zweite identische Kleinste-Quadrate-Rechnung.
    """
    block = trimesh.creation.box(extents=(60.0, 60.0, 20.0))
    ball = trimesh.creation.icosphere(subdivisions=4, radius=8.0)
    ball.apply_translation((0.0, 0.0, 14.0))
    mesh = MeshData(trimesh.boolean.difference([block, ball]))
    original = features_module.fit_sphere
    patches: list[tuple[int, ...]] = []

    def counted(
        body: trimesh.Trimesh, patch: list[int], **kwargs
    ) -> features_module.SphereFit | None:
        patches.append(tuple(patch))
        return original(body, patch, **kwargs)

    monkeypatch.setattr(features_module, "fit_sphere", counted)
    forget_cache()

    found = detect(mesh)

    assert any(feature.kind == "sphere" for feature in found.values())
    assert len(patches) == len(set(patches)), patches


def test_a_countersink_knows_the_bore_it_widens() -> None:
    """Die Senkung findet ihre Bohrung — und der Zapfen findet keine.

    **Der Fall.** Robert hat am 04.09.2026 an einem heruntergeladenen Halter
    den Durchmesser einer Bohrung geändert; über ihr saß eine Senkung, die
    stehen blieb, und im Teil entstand eine Stufe. Gesagt wurde nichts:
    ``resize_hole`` ändert genau ein Merkmal und kannte seine Nachbarschaft
    nicht. ``prepare_ops._feature_body`` schreibt seit dem 03.09.2026 im
    Docstring, was fehlt — „Bis Solidon die Nachbarschaft kennt, ist die
    Absage die richtige Antwort".

    **Und der Fehlgriff der ersten Fassung steht hier mit drin**, denn er ist
    die eigentliche Schärfe des Tests: Ohne die Bedingung „auch ein Hohlraum"
    fand die Bohrung Ø 34 des Halters den Zapfen Ø 40,80 als ihre Senkung —
    koaxial, weiter, und seine Mitte liegt in ihrer Strecke. Ein Zapfen umgibt
    die Bohrung aber, er mündet nicht in sie.

    Geprüft an der Platte des Korpus in beiden Richtungen: ``plate_holes.stl``
    hat vier Bohrungen ohne Senkung und darf **kein** Paar liefern,
    ``plate_countersunk.stl`` genau eines.
    """
    ohne = detect(plate("plate_holes.stl"))
    for feature in ohne.values():
        assert widening_at_the_mouth(feature, ohne) is None, (
            f"{feature.id} hat eine Senkung bekommen, die es nicht gibt"
        )

    mit = detect(plate("plate_countersunk.stl"))
    paare = {
        feature.id: found.id
        for feature in mit.values()
        if (found := widening_at_the_mouth(feature, mit)) is not None
    }
    assert len(paare) == 1, f"genau ein Paar erwartet, gefunden: {paare}"
    bohrung, senkung = next(iter(paare.items()))
    assert mit[bohrung].kind == "hole", f"die Bohrung ist keine: {mit[bohrung].kind}"
    assert mit[senkung].params["diameter"] > mit[bohrung].params["diameter"], (
        "die Senkung muss weiter sein als ihre Bohrung"
    )


def test_material_beside_a_bore_is_not_its_countersink() -> None:
    """Ein Zapfen um eine Bohrung herum ist keine Aufweitung ihrer Öffnung.

    Die Gegenprobe zum Test darüber, an einem eigens gebauten Körper statt am
    Kundenmodell: Eine Bohrung **im** Zapfen ist koaxial mit ihm, er ist
    weiter, und seine Mitte liegt in ihrer Strecke — drei der vier Bedingungen
    treffen zu. Was ihn ausschließt, ist die vierte.

    **Der Prüfkörper ist eigens dafür gebaut, und das ist der Punkt.** Der
    erste Anlauf nahm ``plate_with_pin`` aus dieser Datei: eine Platte mit
    einem Stift daneben, ohne Bohrung darin. Ohne die Hohlraum-Bedingung war
    der Test trotzdem grün — er traf den Fall nicht. Ein Rohr trifft ihn: Die
    Bohrung steckt im Zapfen, wie am Halter (Ø 34 in Ø 40,80), an dem der
    Fehlgriff aufgefallen ist.
    """
    tube = trimesh.creation.annulus(r_min=8.0, r_max=14.0, height=20.0, sections=96)
    body = MeshData.of(tube)
    features = detect(body)
    pins = [feature for feature in features.values() if feature.kind == "pin"]
    bores = [feature for feature in features.values() if feature.kind == "hole"]
    assert pins and bores, (
        f"der Prüfkörper trägt nicht beides — Zapfen {[p.id for p in pins]}, "
        f"Bohrungen {[b.id for b in bores]}; dann prüft der Test nichts"
    )

    for feature in features.values():
        found = widening_at_the_mouth(feature, features)
        assert found is None or found.kind != "pin", (
            f"{feature.id} hält den Zapfen {found.id if found else ''} für seine Senkung"
        )


def test_each_condition_of_the_countersink_rule_separates_something() -> None:
    """Fünf Bedingungen, und jede muss allein etwas trennen.

    **Der Anlass ist ein Fehlschlag dieser Datei.** Nach dem ersten Anlauf
    standen drei Tests auf der Regel, und eine Mutation je Bedingung zeigte:
    Vier von fünf hielt niemand fest. Die Korpusplatte hat keine Senkung, die
    gesenkte Platte hat genau ein Paar — bei einem einzigen Kandidaten findet
    ihn jede Bedingung, gleich welche man streicht. Der Docstring behauptete
    fünf gemessene Bedingungen; gemessen war eine (gefunden am 04.09.2026 nach
    einem Zuruf von 3d-druck-11, die denselben Fehler an ihrer eigenen
    Begründung gefunden hatte).

    Geprüft wird deshalb an der **echten** gesenkten Platte, und verändert wird
    je Durchgang genau ein Wert der Senkung. Was danach nicht mehr gefunden
    wird, hat die Bedingung getrennt.
    """
    features = dict(detect(plate("plate_countersunk.stl")))
    bore = next(feature for feature in features.values() if feature.kind == "hole")
    sink = next(
        feature
        for feature in features.values()
        if feature.kind == "cone" and feature.params.get("recess")
    )
    assert widening_at_the_mouth(bore, features) is not None, (
        "der Grundfall trifft nicht — dann trennt keine der Abwandlungen etwas"
    )

    centre = [float(value) for value in sink.params["centre"]]
    axis = [float(value) for value in sink.params["axis"]]
    radius = float(bore.params["diameter"]) / 2.0

    abwandlungen = {
        # Quer zur Achse gekippt: dieselbe Stelle, andere Richtung.
        "gleiche Achse": {"axis": (axis[1], axis[2], axis[0])},
        # Danebengeschoben, quer zur Achse — zwei Bohrungen nebeneinander
        # haben dieselbe Richtung und sind trotzdem zwei.
        "Mitten auf einer Linie": {"centre": (centre[0] + radius * 4.0, centre[1], centre[2])},
        # Weit weg **auf** der Achse: die Senkung der nächsten Wand.
        "auf der Strecke der Bohrung": {
            "centre": tuple(centre[index] + axis[index] * radius * 40.0 for index in range(3))
        },
        # Enger als ihre Bohrung — dann ist sie keine Senkung.
        "ist weiter": {"diameter": float(bore.params["diameter"]) / 2.0},
        # Materie statt Hohlraum.
        "ist ein Hohlraum": {"recess": False},
    }

    for bedingung, änderung in abwandlungen.items():
        verändert = dataclasses.replace(sink, params={**sink.params, **änderung})
        gefunden = widening_at_the_mouth(bore, {**features, sink.id: verändert})
        assert gefunden is None, (
            f"Bedingung {bedingung!r} trennt nichts: die Senkung wird auch "
            f"als {gefunden.id} gefunden"
        )


def test_the_search_does_not_rehash_the_mesh_for_every_patch() -> None:
    """Die Erkennung liest die Normalen je Fleck — und hasht dabei nicht neu.

    **Der teuerste Posten der Erkennung war Buchhaltung.** Jeder Zugriff auf
    ``body.face_normals`` lässt ``trimesh`` prüfen, ob sich das Netz geändert
    hat, und diese Prüfung hasht das ganze Netz. Gemessen am 04.09.2026 an
    einem Segel mit 421 194 Dreiecken und 3362 Flecken: 227 036 Hashes,
    **17,3 von 26,6 Sekunden** (cProfile), allein 4832 Aufrufe aus
    ``fit_sphere``.

    Mit ``Cache.__enter__`` um den Durchgang fällt die Prüfung weg, solange
    niemand schreiben kann — und niemand kann: ``_one_body`` gibt bei Bedarf
    ein neues Netz zurück, die vier Einpassungen lesen nur.

        421 194 Dreiecke:    24,34 s ->  6,33 s
        885 570 Dreiecke:    17,25 s -> 10,58 s
        1 223 836 Dreiecke: 562,72 s -> 153,20 s

    **Gezählt statt gestoppt**, denn eine Zeitmessung wäre maschinenabhängig
    und würde in der Suite streuen. Gemessen wird die Sache selbst: Vor dem
    Umbau kostete ``post_with_fillet.stl`` 3566 Hashes, danach **drei** — und
    drei sind es an jedem der vier Korpusmodelle, gleich wie groß sie sind und
    wie viele Merkmale sie tragen. Genau das ist die Zusage: Die Zahl hängt
    nicht mehr an der Zahl der Flecken.
    """
    from app.core.perceive.features import forget_cache

    def hashes_of(name: str) -> tuple[int, int]:
        """Wie oft ``detect`` das Netz hasht — und wie viele Merkmale es fand.

        Der Zähler steht in einer eigenen Funktion und nicht in der Schleife:
        Ein Lambda, das eine Schleifenvariable fängt, sieht deren **letzten**
        Wert, und der Zähler zählte dann für das falsche Modell.
        """
        mesh = plate(name)
        forget_cache()
        body = mesh.raw
        treffer: list[int] = []
        echt = body._cache._id_function
        body._cache._id_function = lambda: (treffer.append(1), echt())[1]
        try:
            return len(detect(mesh)), len(treffer)
        finally:
            body._cache._id_function = echt

    gezaehlt: dict[str, int] = {}
    for name in ("plate_holes.stl", "post_with_fillet.stl"):
        merkmale, treffer_zahl = hashes_of(name)
        features = merkmale
        gezaehlt[name] = treffer_zahl
        assert features, f"{name} trägt keine Merkmale — dann prüft der Test nichts"
        assert treffer_zahl < 50, (
            f"{name}: {treffer_zahl} Hashes über das ganze Netz — die Sperre greift nicht"
        )

    # Und die eigentliche Zusage: Das größere Modell mit den meisten Flecken
    # kostet nicht mehr Hashes als das kleine. Eine Obergrenze allein ginge
    # durch, sobald jemand sie großzügig genug wählt.
    assert gezaehlt["post_with_fillet.stl"] <= gezaehlt["plate_holes.stl"] + 2, (
        f"die Zahl wächst mit dem Modell: {gezaehlt}"
    )


def _curvature_patch_family(count: int, *, noisy: bool = False) -> MeshData:
    """Viele getrennte Rundflecken wie an einem gegliederten Druckteil.

    Die Form jedes Glieds bleibt gleich, nur ihre Zahl wächst. Leichtes
    Radialrauschen erzeugt innerhalb jedes Flecks echte Krümmungssprünge, ohne
    die Flecken miteinander zu verbinden.
    """
    rng = np.random.default_rng(7291)
    parts: list[trimesh.Trimesh] = []
    subdivisions = 2 if noisy else 1
    for index in range(count):
        part = trimesh.creation.icosphere(subdivisions=subdivisions, radius=1.0)
        vertices = np.asarray(part.vertices, dtype=float).copy()
        if noisy:
            vertices *= (1.0 + rng.normal(0.0, 0.02, len(vertices)))[:, None]
        part = trimesh.Trimesh(vertices=vertices, faces=part.faces, process=False)
        part.apply_scale((1.0, 1.3, 0.7))
        part.apply_translation((index * 4.0, 0.0, 0.0))
        parts.append(part)
    return MeshData.of(trimesh.util.concatenate(parts))


def test_curvature_splitting_scans_adjacency_once_for_many_failed_patches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mehr Flecken dürfen keinen weiteren Ganznetz-Durchlauf auslösen.

    Der Kundenfall hatte 392 532 Dreiecke und viele Flecken, auf die keine
    Grundform passte. Jeder davon durchlief bislang sämtliche
    Flächennachbarschaften erneut. Gezählt wird der Zugriff auf genau diese
    Grundmenge; eine Zeitgrenze wäre maschinenabhängig.
    """
    descriptor = trimesh.Trimesh.face_adjacency
    assert descriptor.fget is not None
    reads = 0

    def counted(body: trimesh.Trimesh) -> np.ndarray:
        nonlocal reads
        reads += 1
        return np.asarray(descriptor.fget(body))

    monkeypatch.setattr(trimesh.Trimesh, "face_adjacency", property(counted))
    for name in ("fit_cone", "fit_cylinder", "fit_sphere", "fit_torus"):
        monkeypatch.setattr(features_module, name, lambda *_args, **_kwargs: None)

    def reads_for(count: int) -> int:
        nonlocal reads
        reads = 0
        forget_cache()
        # Ohne Grundform bleibt von jedem Glied nur der Rest: eine gerundete
        # Seite je Ellipsoid (``detect_curved_faces``, ein Zugriff auf die
        # Nachbarschaft für alle zusammen) — und sonst nichts.
        found = detect(_curvature_patch_family(count))
        assert {feature.kind for feature in found.values()} == {"curved_face"}, found
        return reads

    few = reads_for(4)
    many = reads_for(32)

    assert many <= few + 2, f"vier Flecken: {few}, zweiunddreißig Flecken: {many}"


def test_batched_curvature_splitting_matches_the_previous_result() -> None:
    """Die einmalige Indexierung ändert keinen Flecken, und die Stücke folgen dem Körper.

    Die Reihenfolge ist seit dem 23.09.2026 die des Körpers
    (``in_body_order``), nicht die der Dreiecksnummern.
    """
    body = _curvature_patch_family(6, noisy=True).raw
    faces = list(range(len(body.faces)))
    patches = features_module._connected_patches(body, faces)
    jumps = features_module._curvature_jumps(body)
    pairs = np.asarray(body.face_adjacency)
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))

    def previous(patch: list[int]) -> list[list[int]]:
        wanted = set(patch)
        adjacency = [
            pair
            for pair, angle, step in zip(pairs, angles, jumps, strict=True)
            if angle < features_module.CURVATURE_LIMIT
            and step <= features_module.CURVATURE_JUMP
            and int(pair[0]) in wanted
            and int(pair[1]) in wanted
        ]
        if not adjacency:
            return [patch]
        groups = trimesh.graph.connected_components(
            np.asarray(adjacency), nodes=np.asarray(patch), engine="scipy"
        )
        return [[int(index) for index in group] for group in groups]

    expected = [features_module.in_body_order(body, previous(patch)) for patch in patches]
    actual = features_module._split_patches_by_curvature(body, patches, jumps)

    assert any(len(pieces) > 1 for pieces in expected), "die Probe erzeugt keinen Krümmungssprung"
    assert actual == expected


def test_vectorised_face_radii_match_the_pair_by_pair_result() -> None:
    """Das schnelle Minimum behält jeden Radius der früheren Schleife."""
    body = _curvature_patch_family(5, noisy=True).raw
    pairs = np.asarray(body.face_adjacency)
    radii = features_module.pair_radii(body)
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    expected = np.full(len(body.faces), np.inf, dtype=float)
    for (first, second), radius, angle in zip(pairs, radii, angles, strict=True):
        if angle >= features_module.CURVATURE_LIMIT or not np.isfinite(radius):
            continue
        expected[int(first)] = min(expected[int(first)], float(radius))
        expected[int(second)] = min(expected[int(second)], float(radius))

    actual = features_module._face_radii(body, pairs, radii)

    np.testing.assert_array_equal(actual, expected)


def test_batched_curvature_splitting_checks_for_cancellation_inside_the_work() -> None:
    """Ein Abbruch wartet nicht bis hinter alle Flecken und Fits."""

    class StopHereError(RuntimeError):
        pass

    body = _curvature_patch_family(32).raw
    patches = features_module._connected_patches(body, list(range(len(body.faces))))
    jumps = features_module._curvature_jumps(body)
    checks = 0

    def stop() -> None:
        nonlocal checks
        checks += 1
        if checks == 8:
            raise StopHereError

    with pytest.raises(StopHereError):
        features_module._split_patches_by_curvature(body, patches, jumps, check_cancelled=stop)
    assert checks == 8


def _mast_after_moving_its_pin(tmp_path: Path, seed: int) -> tuple[MeshData, dict[str, object]]:
    """Ein eingelesener Mast, dessen Zapfen einmal versetzt wurde.

    **Eingelesen und nicht gebaut**, weil es genau um den Weg geht, den ein
    Kunde nimmt: Datei öffnen, ein Merkmal anfassen, Ergebnis im Baum lesen.
    Und versetzt, weil erst die Boolesche Operation neu vernetzt.
    """
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles as knowledge_profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    mast = trimesh.creation.cylinder(radius=2.5, height=115.0, sections=360)
    path = tmp_path / "mast.stl"
    mast.export(path)

    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/mast.stl", sha256=""
    )
    project.sources["src_1"] = path.read_bytes()
    History(project.document).apply(
        "Probe",
        [
            OperationDraft(op="load", params={"source": "src_1", "unit": "mm"}),
            OperationDraft(
                op="move_feature",
                inputs=("obj_1",),
                params={"at_feature": "pin_1", "x": 0.0, "y": 0.0, "z": 5.0},
                # **Der Startwert steht hier und wird nicht gewürfelt.** Die
                # Rückfallkette der Booleschen stupst die Eckpunkte an (§11.3),
                # und wie viele Streifen dabei entstehen, hängt daran. Ohne
                # festen Wert schwankt die Zahl der Funde von Lauf zu Lauf, und
                # ein Test darüber wäre eine Münze.
                seed=seed,
            ),
        ],
    )
    result = evaluate(
        project.document,
        knowledge_profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )
    entry = next(iter(result.scene.objects.values()))
    return entry.mesh, dict(entry.features)


@pytest.mark.parametrize("seed", [0, 1, 7, 23, 902239366])
def test_a_boolean_seam_does_not_become_a_feature(tmp_path: Path, seed: int) -> None:
    """Ein versetztes Merkmal erfand fünfzig Formen, die es nicht gibt.

    Gemessen von 3d-druck-11 an einem Kundenmodell und hier nachgestellt: Ein
    glatter Mast Ø 5 mit drei Merkmalen kam nach ``move_feature`` mit
    **zweiundsiebzig** zurück — zwanzig „Verrundungen", sieben Kegel, zwei
    Kugeln, dazu ein Torus Ø 89,91 auf einem Körper von Ø 5. Es sind die
    schmalen Dreiecksstreifen, die eine Boolesche Operation an ihren
    Nahtstellen hinterlässt: sechs bis neun Dreiecke, über die ganze Länge
    des Körpers gezogen.

    ``MIN_CYLINDER_DIAMETER`` griff dort nicht — die Streifen sind im
    Durchmesser groß genug. Zu klein ist ihre **Breite**
    (:data:`app.core.perceive.features.MIN_SURFACE_WIDTH`).

    Eine historische Messung über zehn Startwerte senkte 369 erfundene Formen
    auf 22 — je Lauf eine bis vier bleiben übrig, und welche, hängt am Stups
    der Rückfallkette. Wer hier
    ``== {}`` schreibt, bekommt einen Test, der bei jedem zweiten Startwert
    rot ist; die verbleibenden gehören in die Zusammenführung der Flächen und
    nicht in diese Schranke.

    Fünf hier gespeicherte Startwerte prüfen unterschiedliche Neuvernetzungen.
    Jeder Lauf muss auch den echten Zapfen mit seinem Durchmesser behalten.
    """
    _mesh, features = _mast_after_moving_its_pin(tmp_path, seed)
    fitted = {
        name: feature
        for name, feature in features.items()
        if getattr(feature, "kind", "") in ("hole", "cone", "sphere", "torus", "fillet")
    }
    assert len(fitted) <= 5, "Neuvernetzung erfand: " + str(
        [(n, f.kind) for n, f in fitted.items()]
    )

    # Und der echte Zapfen bleibt, mit seinem echten Maß — das ist die Hälfte,
    # auf die es ankommt: Eine Schranke, die alles verwirft, bestünde die Zeile
    # darüber ebenfalls.
    pins = [f for f in features.values() if getattr(f, "kind", "") == "pin"]
    assert len(pins) == 1
    assert float(pins[0].params["diameter"]) == pytest.approx(5.0, abs=0.05)


def test_a_real_narrow_surface_survives_the_sliver_guard() -> None:
    """Die Schranke darf nichts Echtes nehmen — und schmal ist nicht dünn.

    Die Gegenprobe zum Test darüber, denn eine Schranke, die alles verwirft,
    besteht ihn ebenfalls. Über den Referenzkorpus ist die schmalste echte
    Fläche 0,379 mm breit und die schmalste echte Verrundung einer Kundendatei
    0,646 mm; die Streifen der Neuvernetzung messen 0,013 bis 0,038 mm.
    """
    from app.core.perceive.features import MIN_SURFACE_WIDTH, _a_sliver

    for name in ("plate_holes.stl", "plate_countersunk.stl", "post_with_fillet.stl"):
        mesh = plate(name)
        found = detect(mesh)
        for feature_name, feature in found.items():
            if feature.kind not in ("hole", "pin", "cone", "sphere", "torus", "fillet"):
                continue
            assert not _a_sliver(mesh.raw, list(feature.face_indices)), (
                f"{name}: {feature_name} ({feature.kind}) wäre unter"
                f" {MIN_SURFACE_WIDTH} mm verworfen worden"
            )


def test_the_width_is_asked_where_the_diameter_is_asked() -> None:
    """Beide Schranken an denselben sechs Stellen — sonst ist es eine halbe.

    Der Zwilling zu :func:`test_every_fitted_kind_asks_the_same_question`, und
    aus demselben Grund: ``_a_sliver`` ist entstanden, weil
    ``_too_small_to_make`` die falsche Achse misst. Wenn die neue Frage nur bei
    fünf der sechs Arten gestellt wird, sieht die Vereinheitlichung vollständig
    aus und ist es nicht.
    """
    import app.core.perceive.features as modul

    source = Path(modul.__file__).read_text(encoding="utf-8")
    lines = source.splitlines()
    asks_diameter = [
        index
        for index, line in enumerate(lines)
        if "_too_small_to_make(" in line and not line.lstrip().startswith(("#", "*", '"', "'"))
    ]
    # Der Aufruf innerhalb der Definition selbst zählt nicht mit.
    asks_diameter = [i for i in asks_diameter if not lines[i].lstrip().startswith("def ")]

    for index in asks_diameter:
        window = "\n".join(lines[max(0, index - 6) : index + 7])
        assert "_a_sliver(" in window, (
            "hier wird der Durchmesser geprüft und die Breite nicht: " + lines[index].strip()
        )

    comparisons = [
        line.strip()
        for line in lines
        if "MIN_SURFACE_WIDTH" in line
        and not line.lstrip().startswith(("#", "*", '"', "'"))
        and re.search(r"[<>=!]=|<|>", line)
    ]
    assert comparisons == ["return area / reach < MIN_SURFACE_WIDTH"], (
        "die Breitenschranke wird nur in _a_sliver verglichen: " + "; ".join(comparisons)
    )


# --- Freiformen -----------------------------------------------------------------


def _listed(kinds: dict[str, int]) -> dict[str, Feature]:
    """Eine Merkmalsliste, wie ``detect`` sie zurückgäbe — nur die Arten zählen."""
    return {
        f"{kind}_{number}": Feature(
            id=f"{kind}_{number}", kind=kind, provenance="detected", params={}
        )
        for kind, count in kinds.items()
        for number in range(1, count + 1)
    }


def _scan_like_blob(seed: int = 7) -> MeshData:
    """Ein Körper wie ein Scan: glatte Beulen auf einer Kugel, feines Rauschen,
    unten eine ebene Standfläche.

    **Ohne das Rauschen findet die Erkennung an so einem Körper nichts** —
    die Krümmung ändert sich zu stetig, als dass ``_split_patches_by_curvature``
    Flecken abteilte (gemessen am 05.09.2026: zwei Flächen, sonst nichts).
    Mit ihm zerfällt die Oberfläche in Dutzende Flecken annähernd gleicher
    Krümmung, und auf jeden passt eine Kugel — genau der Mechanismus, der auf
    dem Kiefer-Scan eines Kunden 281 Rundformen fand; hier sind es 39.
    """
    rng = np.random.default_rng(seed)
    ball = trimesh.creation.icosphere(subdivisions=5, radius=20.0)
    vertices = np.asarray(ball.vertices, dtype=float).copy()
    unit = vertices / np.linalg.norm(vertices, axis=1)[:, None]
    centres = rng.normal(size=(40, 3))
    centres /= np.linalg.norm(centres, axis=1)[:, None]
    widths = rng.uniform(0.15, 0.5, size=40)
    heights = rng.uniform(-0.25, 0.25, size=40)
    scale = np.ones(len(vertices))
    for centre, width, height in zip(centres, widths, heights, strict=True):
        distance = np.arccos(np.clip(unit @ centre, -1.0, 1.0))
        scale += height * np.exp(-((distance / width) ** 2))
    scale += rng.normal(scale=0.01, size=len(vertices))
    blob = trimesh.Trimesh(vertices=vertices * scale[:, None], faces=ball.faces, process=False)
    with_base = trimesh.intersections.slice_mesh_plane(
        blob, plane_normal=(0.0, 0.0, 1.0), plane_origin=(0.0, 0.0, -12.0), cap=True
    )
    return MeshData.of(with_base)


def test_the_freeform_verdict_needs_the_count_and_the_share() -> None:
    """Zwei Zahlen an der fertigen Liste — und die Fälle, an denen sie gemessen sind.

    Die Nozzle-Box ist der wichtige: konstruiert, 116 Merkmale, 69 davon
    Kugeln und Ringe (59 %). Das Register vom 04.09.2026 kannte für
    Konstruiertes nur 0 bis 7 %; die Schwelle liegt deshalb bei sieben
    Zehnteln und nicht bei der Hälfte. Der Ring allein ist zu hundert Prozent
    rund und trotzdem ein Ring — dafür die Mindestzahl.
    """
    assert math.isclose(FREEFORM_ROUND_SHARE, 0.7)
    assert FREEFORM_ROUND_COUNT == 12

    assert is_a_freeform(_listed({"sphere": 8, "torus": 4}))
    assert is_a_freeform(_listed({"sphere": 60, "torus": 40, "cone": 10, "face": 20})), (
        "77 Prozent, wie die Retro-Maus"
    )
    assert not is_a_freeform(
        _listed({"sphere": 17, "torus": 52, "cone": 22, "hole": 8, "face": 16, "fillet": 1})
    ), "die Nozzle-Box: konstruiert, 59 Prozent rund"
    assert not is_a_freeform(_listed({"sphere": 11, "face": 1})), "elf sind zu wenige"
    assert not is_a_freeform(_listed({"torus": 1})), "torus_ring.stl: ein Ring ist ein Ring"
    assert is_a_freeform(
        _listed({"torus": 12, "cone": 7, "face": 1}),
        unpublished_round_shapes=27,
    ), "unsichere Kugelfits bleiben als Freiformbeleg erhalten"
    assert not is_a_freeform({})


def test_on_a_freeform_the_round_shapes_go_and_the_rest_stays() -> None:
    kept, dropped = features_module._shapes_on_a_freeform(
        _listed({"sphere": 20, "torus": 10, "cone": 3, "fillet": 2, "hole": 1, "pin": 1, "face": 2})
    )
    assert dropped == 35
    assert {feature.kind for feature in kept.values()} == {"hole", "pin", "face"}

    unchanged = _listed({"sphere": 1, "face": 6})
    assert features_module._shapes_on_a_freeform(unchanged) == (unchanged, 0)


@pytest.fixture(scope="module")
def scan_detection() -> tuple[MeshData, dict[FeatureId, Feature], int]:
    """Der Scan-Körper einmal erkannt — 2,3 s je Erkennung, und zwei Tests lesen dasselbe.

    Der Zähler der weggelassenen Rundformen wird sofort abgelesen: Die
    Suite leert den Merkmalscache vor jedem Test, und mit ihm den Zähler.
    """
    mesh = _scan_like_blob()
    forget_cache()
    found = detect(mesh)
    return mesh, found, freeform_dropped(mesh)


def test_a_scan_keeps_its_flat_base_and_loses_the_invented_round_shapes(
    scan_detection: tuple[MeshData, dict[FeatureId, Feature], int],
) -> None:
    """Der Kundenfall an einem Körper aus dem Test selbst — ohne Korpusdatei,
    weil kein freies Scanmodell im Korpus liegt.

    Was bleibt, ist das Echte: die ebene Standfläche. Was geht, sind die
    Kugeln und Ringe, die die Krümmungsflecken hergaben — und der Zähler
    daneben sagt der Auswertung, wie viele es waren (Regel 17).
    """
    _mesh, found, dropped = scan_detection

    kinds = {feature.kind for feature in found.values()}
    assert dropped >= FREEFORM_ROUND_COUNT, dropped
    assert not kinds & {"sphere", "torus", "cone", "fillet"}, kinds
    assert "face" in kinds, "die Standfläche ist echt und bleibt"


@pytest.mark.parametrize("with_sphere", [False, True])
def test_without_the_freeform_rule_the_same_scan_keeps_only_supported_round_shapes(
    monkeypatch: pytest.MonkeyPatch,
    with_sphere: bool,
) -> None:
    """Nur eine unabhängig gebaute Kugel belegt eine Rundform im verrauschten Scan.

    Beide Freiformregeln sind hier aus: die Zählung der Rundformen und die
    Haut aus Splittern (RM-193) — der Scan-Körper trägt einen Fleck über der
    Hälfte seiner Oberfläche mit 1 640 Splittern und wäre sonst eine Freiform,
    bevor eine einzige Rundform gezählt ist.
    """
    monkeypatch.setattr(features_module, "FREEFORM_ROUND_COUNT", 10**6)
    monkeypatch.setattr(features_module, "FREEFORM_SPLINTERS", 10**9)
    forget_cache()
    scan = _scan_like_blob()
    if with_sphere:
        ball = trimesh.creation.icosphere(radius=7.234567, subdivisions=2)
        ball.apply_translation((60.0, 0.0, 0.0))
        mesh = MeshData.of(trimesh.util.concatenate((scan.raw, ball)))
        expected_faces = set(range(scan.triangle_count, mesh.triangle_count))
    else:
        mesh = scan
        expected_faces = set()
    points, faces = mesh.raw.vertices.copy(), mesh.raw.faces.copy()

    found = detect(mesh)

    round_shapes = [f for f in found.values() if f.kind in ("sphere", "torus")]
    assert len(round_shapes) == int(with_sphere)
    if with_sphere:
        sphere = round_shapes[0]
        assert sphere.kind == "sphere"
        assert sphere.params["diameter"] == pytest.approx(2 * 7.234567, abs=EPS_GEOM, rel=0)
        assert sphere.params["centre"] == pytest.approx((60, 0, 0), abs=EPS_GEOM, rel=0)
        assert set(sphere.face_indices) == expected_faces
    assert freeform_dropped(mesh) == 0
    np.testing.assert_array_equal(mesh.raw.vertices, points)
    np.testing.assert_array_equal(mesh.raw.faces, faces)


def test_a_constructed_part_with_one_round_feature_is_left_alone() -> None:
    """Die Gegenrichtung am Korpus: Pfanne, Ring und Verrundung bleiben."""
    for name in ("sphere_socket.stl", "torus_ring.stl", "post_with_fillet.stl"):
        forget_cache()
        mesh = plate(name)
        found = detect(mesh)
        assert freeform_dropped(mesh) == 0, name
        assert any(f.kind in ("sphere", "torus") for f in found.values()), name


def _blob_with_a_countersunk_bore() -> MeshData:
    """Der Scan-Körper mit einer gesenkten Bohrung durch seine Standfläche.

    Von der ebenen Unterseite bei z = −12 nach oben: Ø 5 durchgehend, darüber
    die 90-Grad-Senkung auf Ø 10. Beides gebohrt, nicht behauptet — die
    Erkennung soll es an der Geometrie finden.
    """
    blob = _scan_like_blob().raw
    bore = trimesh.creation.cylinder(radius=2.5, height=30.0, sections=64)
    bore.apply_translation((0.0, 0.0, -3.0))
    sink = trimesh.creation.cone(radius=5.0, height=5.0, sections=64)
    sink.apply_translation((0.0, 0.0, -12.0))
    return MeshData.of(trimesh.boolean.difference([blob, bore, sink]))


def test_a_skin_of_splinters_is_not_fitted_piece_by_piece(monkeypatch: pytest.MonkeyPatch) -> None:
    """RM-193, Entscheidung Robert 22.09.2026: Der Fleck über der halben
    Oberfläche, auf den keine Grundform passt und der nach Krümmung in
    Splitter zerfällt, ist die Haut einer Freiform. Seine Splitter werden
    nicht mehr eingepasst — am Drachen aus TripoSG 27 554 Stücke, 33 der 37
    Sekunden für null Merkmale —, seine Stücke von Gewicht schon, und das
    Urteil über das Modell kommt aus der Haut, nicht aus einer Zählung.

    Gezählt werden die Kegeleinpassungen, denn die sind der Preis: Am
    Scan-Körper der Tests (1 640 Splitter in einem Fleck, dazu 1 222 kleine
    Flecken, die weiter ganz gelesen werden) fallen sie um ein Drittel
    (364 → 230), und das Ergebnis bleibt Merkmal für Merkmal dasselbe.

    **Die Schwelle steht hier auf der Hälfte statt auf zwei Dritteln**, denn
    der Scan-Körper liegt mit 63,6 Prozent zerfallender Fläche knapp darunter
    — geprüft wird die Mechanik, nicht die Zahl. Die Zahl selbst ist an
    ``F:\\3D Dateien`` kalibriert und steht an der Konstanten; ein Körper, der
    unter ihr bleibt, verliert nichts, sondern wird gelesen wie zuvor und von
    der Zählung beurteilt — genau das tut dieser hier ohne den Patch.
    """
    monkeypatch.setattr(features_module, "FREEFORM_SKIN_SHARE", 0.5)
    mesh = _scan_like_blob()
    original = features_module.fit_cone
    calls: list[int] = []

    def counted(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(features_module, "fit_cone", counted)

    forget_cache()
    with_skin = detect(mesh)
    fits_with_skin = len(calls)
    assert features_module.recognised_as_freeform(mesh), "die Haut macht das Modell zur Freiform"
    assert features_module._fitted(mesh).freeform_skin

    calls.clear()
    monkeypatch.setattr(features_module, "FREEFORM_SPLINTERS", 10**9)
    forget_cache()
    without_skin = detect(mesh)
    fits_without_skin = len(calls)

    assert fits_with_skin < fits_without_skin * 0.7, (fits_with_skin, fits_without_skin)
    assert {f.id: (f.kind, f.face_indices) for f in with_skin.values()} == {
        f.id: (f.kind, f.face_indices) for f in without_skin.values()
    }, "dieselben Merkmale, mit und ohne den Umweg über die Splitter"


def test_a_ball_that_is_the_whole_body_stays_a_ball() -> None:
    """Ein Körper, der selbst eine Grundform ist, wird keine Freiform.

    Der Fall kam am 22.09.2026 aus dem Korpus: Die drei Bowlingkugeln aus
    ``BowlingGame.3mf`` sind je **ein** Fleck über 65 024 Dreiecke, auf den
    eine Kugel mit Rückstand 0,0 passt — und sie zerfallen nach Krümmung
    trotzdem in 662 Stücke, 659 davon Splitter. Wer diese Stücke fürs
    Hauturteil zählt, erklärt eine mathematisch perfekte Kugel zur Haut einer
    Figur, und :func:`is_a_freeform` nimmt sie anschließend weg: ein Merkmal
    weniger, ohne dass irgendetwas an der Kugel unsicher wäre.

    Ein Donut, ein Kegel, ein Ball — jede Grundform, die ein ganzes Modell
    ist, zerfällt nach Krümmung wie eine Figur. Nur der Fit trennt sie, also
    entscheidet er zuerst: Gezählt wird für die Haut nur, was **keine**
    Grundform ergeben hat.
    """
    for body, expected in (
        (trimesh.creation.icosphere(subdivisions=5, radius=8.75), "sphere"),
        (trimesh.creation.torus(major_radius=20.0, minor_radius=6.0, major_sections=180), "torus"),
    ):
        mesh = MeshData.of(body)
        forget_cache()
        found = detect(mesh)
        kinds = sorted(feature.kind for feature in found.values())
        assert not features_module.recognised_as_freeform(mesh), (
            f"{expected}: ein Körper, der selbst eine Grundform ist, ist keine Freiform"
        )
        assert expected in kinds, f"{expected} erwartet, gefunden: {kinds}"


def test_the_skin_judgement_only_counts_patches_without_a_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Das Urteil über die Haut fällt **nach** der ersten Runde, nicht darin.

    Solange es beim ersten Fleck ohne Form fiel, hing es an der Reihenfolge:
    Derselbe Körper mit einer Kugel und einem kleinen unlesbaren Fleck wurde
    zur Freiform, wenn der kleine Fleck zufällig vorne stand, und blieb eine
    Kugel, wenn er hinten stand. Jetzt läuft erst ``classify`` über alle
    Flecken, dann die Nachtrennung über die gescheiterten — und nur deren
    Fläche entscheidet.

    Geprüft an der Nachtrennung: Sie darf nur mit den Flecken laufen, auf die
    nichts gepasst hat.
    """
    seen: list[int] = []
    original = features_module._split_patches_by_curvature

    def watching(body, patches, jump, *, worth_splitting=None, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(0 if worth_splitting is None else int(worth_splitting.sum()))
        return original(body, patches, jump, worth_splitting=worth_splitting, **kwargs)

    monkeypatch.setattr(features_module, "_split_patches_by_curvature", watching)
    mesh = MeshData.of(trimesh.creation.icosphere(subdivisions=5, radius=8.75))
    forget_cache()
    detect(mesh)

    assert not seen, "auf die Kugel passte eine Form — nachgetrennt wird nichts"


def test_a_smooth_body_over_half_its_surface_is_no_skin_without_splinters() -> None:
    """Die Gegenrichtung: Kapsel, Ellipsoid und der Bogen eines Buchstabens
    liegen mit ihrem gekrümmten Fleck über der Hälfte, zerfallen aber in ein
    bis fünf Stücke von Gewicht — keine Haut, kein Freiformurteil, und ihre
    gerundeten Seiten bleiben, was sie waren."""
    for name, mesh in (
        ("Kapsel", MeshData.of(trimesh.creation.capsule(radius=8.0, height=30.0, count=(48, 48)))),
        ("Ellipsoid", _curvature_patch_family(1)),
        ("Buchstabe S", _letter("S")),
    ):
        forget_cache()
        found = detect(mesh)
        assert not features_module._fitted(mesh).freeform_skin, name
        assert not features_module.recognised_as_freeform(mesh), name
        assert any(f.kind == "curved_face" for f in found.values()), name


def test_a_freeform_keeps_the_countersink_that_hangs_on_a_bore() -> None:
    """Der Preis, den ``_shapes_on_a_freeform`` bis zum 10.09.2026 offen trug.

    Sein Docstring nannte ihn selbst — „auf einer Figur mit einer echten
    Senkung geht die Senkung mit […] gemessen ist er noch an keinem Modell" —
    und an dem Tag kam das Modell: Roberts ``garden-hose-holder.3mf``, ein
    konstruierter Halter, dessen geschwungener Bogen ihn mit einem
    Rundformanteil von 0,701 gegen die Schwelle 0,700 zur Freiform machte. Mit
    den 51 erfundenen Kegeln fielen seine vier echten 90-Grad-Senkungen, und
    ohne sie fand ``cavity_chain_at`` an keiner der vier Schraubstellen mehr
    die Kette Bohrung-Senkung-Bohrung.

    Hier steht derselbe Fall als Körper aus dem Test: eine Freiform, die
    weiterhin ihre erfundenen Rundformen verliert, und **eine** echte Senkung,
    die bleibt, weil sie an einer Bohrung hängt.
    """
    mesh = _blob_with_a_countersunk_bore()
    forget_cache()

    found = detect(mesh)

    assert freeform_dropped(mesh) >= FREEFORM_ROUND_COUNT, (
        "der Körper ist weiter eine Freiform und verliert seine erfundenen Rundformen"
    )
    bores = [f for f in found.values() if f.kind == "hole"]
    sinks = [f for f in found.values() if f.kind == "cone"]
    assert len(bores) == 1, f"eine Bohrung, gefunden: {[f.id for f in bores]}"
    assert len(sinks) == 1, f"eine Senkung, gefunden: {[f.id for f in sinks]}"
    assert sinks[0].params["diameter"] == pytest.approx(10.0, abs=0.05)
    assert not [f for f in found.values() if f.kind in ("sphere", "torus", "fillet")], (
        "gerettet wird nur, was an einer Bohrung hängt — nichts sonst"
    )
    assert widening_at_the_mouth(bores[0], found) is sinks[0], (
        "und die Nachbarschaft steht: die Senkung sitzt an der Mündung dieser Bohrung"
    )


def test_only_a_shape_at_the_mouth_of_a_bore_survives_the_freeform_rule() -> None:
    """Die Bedingung selbst, ohne Geometrie — und ihre Gegenprobe.

    ``sits_at_the_mouth_of`` ist die eine Antwort auf „gehört diese Aufweitung
    zu dieser Bohrung"; :func:`widening_at_the_mouth` fragt sie von der Bohrung
    aus, der Freiformfilter aus der Gegenrichtung. Was sie nicht belegt, geht
    weiter weg — sonst rettete der Filter am Kundenmodell nicht vier von 55
    Kegeln, sondern alle 55.
    """
    bore = Feature(
        id=FeatureId("hole_1"),
        kind="hole",
        provenance="detected",
        params={"diameter": 5.0, "depth": 8.0, "axis": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 4.0)},
    )
    sink = Feature(
        id=FeatureId("cone_1"),
        kind="cone",
        provenance="detected",
        params={
            "diameter": 10.0,
            "axis": (0.0, 0.0, 1.0),
            "centre": (0.0, 0.0, 0.0),
            "recess": True,
        },
    )
    elsewhere = dataclasses.replace(
        sink, id=FeatureId("cone_2"), params={**sink.params, "centre": (40.0, 0.0, 0.0)}
    )
    narrower = dataclasses.replace(
        sink, id=FeatureId("cone_3"), params={**sink.params, "diameter": 3.0}
    )
    a_bump = dataclasses.replace(
        sink, id=FeatureId("cone_4"), params={**sink.params, "recess": False}
    )

    assert features_module.sits_at_the_mouth_of(bore, sink)
    assert not features_module.sits_at_the_mouth_of(bore, elsewhere), "vierzig Millimeter daneben"
    assert not features_module.sits_at_the_mouth_of(bore, narrower), "enger als ihre Bohrung"
    assert not features_module.sits_at_the_mouth_of(bore, a_bump), "eine Kuppe ist Materie"

    kept, dropped = features_module._shapes_on_a_freeform(
        {
            **_listed({"sphere": 20, "torus": 10}),
            bore.id: bore,
            sink.id: sink,
            elsewhere.id: elsewhere,
        }
    )
    assert set(kept) == {bore.id, sink.id}, "die Senkung an der Bohrung bleibt, die daneben geht"
    assert dropped == 31


def _block_with_a_trapped_pocket() -> MeshData:
    """Ein Quader mit einem Zylinder darin, der nirgendwo herauskommt.

    Genau die Bauart, die Robert am 10.09.2026 in ``garden-hose-holder.3mf``
    fand: der Negativkörper als eigene Schale im Netz, nie boolesch abgezogen.
    Nachgestellt, indem der Zylinder **umgedreht** an den Quader gehängt wird —
    seine Normalen zeigen dann ins Material, und genau das macht ihn zum
    Hohlraum statt zum zweiten Körper.
    """
    block = trimesh.creation.box(extents=(40.0, 40.0, 20.0))
    pocket = trimesh.creation.cylinder(radius=1.0, height=9.0, sections=48)
    pocket.invert()
    return MeshData.of(trimesh.util.concatenate([block, pocket]))


def test_a_cavity_with_no_way_out_is_a_void_and_not_a_bore() -> None:
    """Acht Bohrungen, die man weder sehen noch bohren kann (Robert, 10.09.2026).

    ``garden-hose-holder.3mf`` trug acht eigene geschlossene Schalen mit
    negativem Volumen, je Ø 2 auf 9 mm. Nach ``_one_body`` liegen ihre nach
    innen zeigenden Mäntel im selben Netz, und für ``detect_holes`` sah das aus
    wie eine Bohrung — dieselben Normalen, derselbe Kreis, nur ohne Öffnung.
    Der Objektbaum zeigte sie als ``hole`` mit ``through=False``.

    Hier steht der Fall als Körper aus dem Test. Gemessen wird beides: dass ein
    Einschluss als solcher herauskommt, **und** dass an seiner Stelle keine
    Bohrung mehr steht.
    """
    mesh = _block_with_a_trapped_pocket()
    forget_cache()

    found = detect(mesh)

    voids = [feature for feature in found.values() if feature.kind == "void"]
    assert len(voids) == 1, f"ein Einschluss, gefunden: {[f.id for f in found.values()]}"
    # π · 1² · 9 = 28,27 mm³ — dieselbe Zahl, die am Kundenmodell achtmal stand.
    assert voids[0].params["volume"] == pytest.approx(28.27, abs=0.2)
    assert not [feature for feature in found.values() if feature.kind == "hole"], (
        "an der Stelle eines Einschlusses steht keine Bohrung mehr"
    )
    assert any(feature.kind == "face" for feature in found.values()), (
        "die sechs Flächen des Quaders bleiben — der Einschluss nimmt nur seine eigenen"
    )

    # **Und er ist keine Sackgasse.** Der erste Entwurf sperrte hier alles mit
    # der Begründung, an einen eingeschlossenen Hohlraum komme kein Werkzeug
    # heran — dabei versetzt ``test_a_cavity_inside_the_body_moves_without_
    # losing_material`` seit dem 03.09.2026 genau so einen. Was fehlt, ist das
    # Maß und nicht der Zugang.
    load_operations()
    offered = {action.op for action in actions_for(voids[0]) if action.op}
    assert offered == {"move_feature", "remove_feature"}, (
        f"Versetzen und Entfernen gehen an einem Einschluss, gefunden: {sorted(offered)}"
    )
    refused = [action for action in actions_for(voids[0]) if not action.op]
    assert all(str(action.reason) for action in refused), (
        "und jede Absage nennt ihren Grund (Regel 17)"
    )


def test_nested_air_chambers_keep_their_material_islands() -> None:
    """Luft, Materialinsel und deren eigene Luftkammer besitzen getrennte Grenzen."""
    block = trimesh.creation.box(extents=(40.0, 40.0, 40.0))
    air = trimesh.creation.box(extents=(12.0, 12.0, 12.0))
    island = trimesh.creation.box(extents=(6.0, 6.0, 6.0))
    nested = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    air.invert()
    nested.invert()
    mesh = MeshData.of(trimesh.util.concatenate([block, air, island, nested]))
    voids = features_module.detect_voids(mesh)
    assert sorted(feature.params["volume"] for feature in voids) == pytest.approx([8.0, 1512.0])
    outer = max(voids, key=lambda feature: feature.params["volume"])
    inner = min(voids, key=lambda feature: feature.params["volume"])
    assert set(outer.face_indices) == set(range(12, 36))
    assert set(inner.face_indices) == set(range(36, 48))
    assert outer.params["centre"] == pytest.approx((0.0, 0.0, 0.0))


def test_air_chamber_beside_a_material_island_keeps_only_its_own_surfaces() -> None:
    """Zwei getrennte Luftkammern bleiben getrennt, auch wenn eine eine Insel enthält."""
    block = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
    first = trimesh.creation.box(extents=(8.0, 8.0, 8.0))
    first.apply_translation((-8.0, 0.0, 0.0))
    first.invert()
    island = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    island.apply_translation((-8.0, 0.0, 0.0))
    second = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
    second.apply_translation((8.0, 0.0, 0.0))
    second.invert()
    mesh = MeshData.of(trimesh.util.concatenate([block, first, island, second]))
    voids = features_module.detect_voids(mesh)
    assert [feature.params["volume"] for feature in voids] == pytest.approx([504.0, 64.0])
    assert set(voids[0].face_indices) == set(range(12, 36))
    assert set(voids[1].face_indices) == set(range(36, 48))


@pytest.mark.parametrize("before_work", [False, True])
def test_void_containment_can_cancel_and_restart_without_partial_features(
    monkeypatch: pytest.MonkeyPatch, before_work: bool
) -> None:
    """Abbruch erreicht die echte Schalenprüfung, ohne Geometrie oder Cache zu verändern.

    Die Schalenprüfung ist seit dem 21.09.2026 das Gitterzertifikat samt
    Strahltest (``_shells_do_not_cross``), nicht mehr eine native Differenz
    je Paar; der Abbruch muss unmittelbar danach greifen.
    """
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    original = features_module._shells_do_not_cross
    mesh = _block_with_a_trapped_pocket()
    before_vertices = mesh.raw.vertices.copy()
    before_faces = mesh.raw.faces.copy()
    signal = CancelSignal()
    calls = []

    def stop(*args, **kwargs):
        """Erst die echte Schalenprüfung ausführen, dann den Abbruch verlangen."""
        result = original(*args, **kwargs)
        calls.append(result)
        signal.cancel()
        return result

    forget_cache()
    if before_work:
        signal.cancel()
    else:
        monkeypatch.setattr(features_module, "_shells_do_not_cross", stop)
    with pytest.raises(OperationCancelled):
        detect(mesh, check_cancelled=signal.raise_if_cancelled)
    assert calls == ([] if before_work else [True])
    assert np.array_equal(mesh.raw.vertices, before_vertices)
    assert np.array_equal(mesh.raw.faces, before_faces)
    monkeypatch.setattr(features_module, "_shells_do_not_cross", original)
    assert len([feature for feature in detect(mesh).values() if feature.kind == "void"]) == 1


def _tube_with_a_pocket(centre_x: float) -> MeshData:
    """Ein Rohr (Innenradius 5, Außenradius 15) mit einer umgestülpten Tasche 4 × 4 × 4.

    Bei ``centre_x = 10`` liegt die Tasche ganz in der Rohrwand; bei ``5``
    kreuzt sie die Innenwand — ihr Hüllquader bleibt trotzdem strikt im
    Hüllquader des Rohrs, das Tor der Bounds lässt sie also durch.
    """
    tube = trimesh.creation.annulus(r_min=5.0, r_max=15.0, height=20.0, sections=96)
    pocket = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
    pocket.apply_translation((centre_x, 0.0, 0.0))
    pocket.invert()
    return MeshData.of(trimesh.util.concatenate([tube, pocket]))


def test_a_pocket_inside_the_wall_needs_no_native_difference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enthaltensein ohne einen Manifold je Paar — und exakt, wo die Schalen sich kreuzen.

    Am Quader mit acht Kammern aus 434 176 Dreiecken kostete die native
    Differenz je Schalenpaar 1,2 s (gemessen am 21.09.2026). Kreuzen sich die
    Schalen nicht — das belegt das Gitterzertifikat über die Hüllquader der
    Dreiecke —, entscheidet ein Strahl von einer Ecke des Kinds; nur wo das
    Zertifikat fehlt, rechnet die Differenz wie bisher, und die sagt an einer
    Tasche, die die Innenwand durchstößt, weiter: kein Einschluss.
    """
    import importlib

    geometry = importlib.import_module("app.core.geom.boolean")
    original = geometry.boolean
    calls: list[str] = []

    def counted(kind, *args, **kwargs):
        calls.append(kind)
        return original(kind, *args, **kwargs)

    monkeypatch.setattr(geometry, "boolean", counted)

    inside = features_module.detect_voids(_tube_with_a_pocket(10.0))
    assert [feature.params["volume"] for feature in inside] == pytest.approx([64.0])
    assert calls == [], "die Tasche in der Wand braucht keine native Differenz"

    crossing = features_module.detect_voids(_tube_with_a_pocket(5.0))
    assert crossing == [], "eine Tasche, die die Innenwand durchstößt, ist kein Einschluss"
    assert calls == ["difference"], "und genau dort entscheidet die Differenz"


def test_the_crossing_certificate_reads_triangle_boxes_not_shell_boxes() -> None:
    """Zwei Schalen mit überlappenden Hüllquadern kreuzen sich nur, wenn ihre Dreiecke es tun.

    Eine Kugel in einer Kugel: Der Hüllquader der Innenkugel ragt in die
    Ecken hinein, die die Außenkugel nicht füllt, und die Hüllquader beider
    Schalen überlappen — das Zertifikat sieht die Dreiecke und sagt trotzdem
    ja. Eine kreuzende Tasche bekommt es nicht.
    """
    outer = trimesh.creation.icosphere(subdivisions=5, radius=40.0)
    inner = trimesh.creation.icosphere(subdivisions=5, radius=30.0)
    outer_bounds = features_module._triangle_bounds(np.asarray(outer.triangles, dtype=float))
    inner_bounds = features_module._triangle_bounds(np.asarray(inner.triangles, dtype=float))
    assert features_module._shells_do_not_cross(inner_bounds, outer_bounds)
    assert features_module._shells_do_not_cross(outer_bounds, inner_bounds)

    tube = trimesh.creation.annulus(r_min=5.0, r_max=15.0, height=20.0, sections=96)
    pocket = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
    pocket.apply_translation((5.0, 0.0, 0.0))
    tube_bounds = features_module._triangle_bounds(np.asarray(tube.triangles, dtype=float))
    pocket_bounds = features_module._triangle_bounds(np.asarray(pocket.triangles, dtype=float))
    assert not features_module._shells_do_not_cross(pocket_bounds, tube_bounds)


def test_a_ray_through_every_face_middle_decides_nothing_and_the_difference_takes_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sechs Strahlen durch sechs Diagonalen: unentscheidbar — und der Einschluss bleibt.

    Vom Mittelpunkt eines Würfels trifft jeder achsenparallele Strahl die
    Mitte einer Seite, also die Diagonale zwischen deren zwei Dreiecken. Der
    Strahltest sagt dann ``None`` statt zu raten, und die native Differenz
    entscheidet wie bisher.
    """
    import importlib

    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    triangles = np.asarray(box.triangles, dtype=float)
    bounds = features_module._triangle_bounds(triangles)
    assert features_module._point_inside_shell(np.zeros(3), triangles, bounds) is None
    assert features_module._point_inside_shell(np.array([1.0, 2.0, 3.0]), triangles, bounds)
    assert not features_module._point_inside_shell(np.array([1.0, 2.0, 30.0]), triangles, bounds)

    # Ein Tetraeder als Tasche, dessen erste Ecke im Mittelpunkt des Würfels
    # liegt — genau der Fall, in dem der Strahl nichts entscheidet. Das
    # Umstülpen dreht jedes Dreieck um; ``[2, 1, 0]`` wird dabei ``[0, 1, 2]``.
    pocket = trimesh.Trimesh(
        vertices=[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]],
        faces=[[2, 1, 0], [0, 1, 3], [0, 3, 2], [1, 2, 3]],
        process=False,
    )
    assert pocket.is_watertight and pocket.volume > 0.0
    pocket.invert()
    mesh = MeshData.of(trimesh.util.concatenate([box, pocket]))
    geometry = importlib.import_module("app.core.geom.boolean")
    original = geometry.boolean
    calls: list[str] = []

    def counted(kind, *args, **kwargs):
        calls.append(kind)
        return original(kind, *args, **kwargs)

    monkeypatch.setattr(geometry, "boolean", counted)
    voids = features_module.detect_voids(mesh)
    assert [feature.params["volume"] for feature in voids] == pytest.approx([4.5])
    assert calls == ["difference"]


def test_unreadable_shells_are_reported_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scheitert die Differenz, fehlen die Einschlüsse nicht still (Regel 17).

    Bis zum 21.09.2026 gab ``_shells_inside_the_material`` bei einem
    ``GeometryError`` leere Gruppen zurück, und niemand erfuhr davon.
    ``unreadable_void_shells`` nennt der Auswertung jetzt die Zahl der Schalen
    des Körpers, damit sie einen Befund daraus machen kann.
    """
    import importlib

    from app.core.errors import GeometryError

    geometry = importlib.import_module("app.core.geom.boolean")

    def broken(*_args, **_kwargs):
        raise GeometryError("nicht lesbar")

    monkeypatch.setattr(geometry, "boolean", broken)
    mesh = _tube_with_a_pocket(5.0)
    forget_cache()
    assert features_module.unreadable_void_shells(mesh) == 0, "vor der Erkennung weiß es niemand"
    found = detect(mesh)
    assert not [feature for feature in found.values() if feature.kind == "void"]
    assert features_module.unreadable_void_shells(mesh) == 2, "zwei Schalen, keine lesbar"

    forget_cache()
    detect(_tube_with_a_pocket(10.0))
    assert features_module.unreadable_void_shells(_tube_with_a_pocket(10.0)) == 0, (
        "wo keine Differenz nötig war, ist auch nichts unlesbar"
    )


def test_an_open_mesh_keeps_its_bores_because_a_sign_says_nothing_there() -> None:
    """Die Grenze der Auskunft, und sie hält an, statt zu raten (Regel 21).

    Das Vorzeichen eines eingeschlossenen Volumens trägt nur an einem dichten
    Netz. Ist das Netz offen, ist eine Schale mit negativem Volumen genauso gut
    eine Lücke wie ein Einschluss — und aus einer Lücke einen Einschluss zu
    machen wäre geraten. Solche Modelle behalten, was sie hatten.
    """
    mesh = _block_with_a_trapped_pocket()
    body = mesh.raw.copy()
    # Ein Dreieck weg, und das Netz ist offen — sonst ändert sich nichts.
    body.update_faces(np.arange(len(body.faces)) != 0)
    forget_cache()

    assert not body.is_watertight, "die Vorbedingung des Tests"
    assert features_module.detect_voids(MeshData.of(body)) == [], (
        "an einem offenen Netz wird kein Einschluss behauptet"
    )
    # **Und der Satz „behalten, was sie hatten" gehört in ein assert.** Ohne
    # diese zwei Zeilen misst der Test nur die leere Liste; dass die Bohrung
    # danach noch dasteht, stünde allein im Docstring.
    kept = detect(MeshData.of(body))
    assert any(feature.kind == "hole" for feature in kept.values()), (
        f"die Bohrung bleibt, wie sie war: {sorted({f.kind for f in kept.values()})}"
    )


def test_two_air_pockets_keep_their_names_however_the_file_was_written() -> None:
    """§21.2: Die Nummer eines Einschlusses hängt an seinem Ort, nicht an der Datei.

    **Der Fall, den keine einzelne Datei zeigt.** Die Nummern kamen aus
    ``face_components``, und die Reihenfolge dort folgt dem Flächenindex — also
    dem, in welcher Reihenfolge ein Exporter die Dreiecke geschrieben hat.
    Dieselbe Geometrie aus einem anderen Werkzeug bekam damit vertauschte
    Namen, und eine Op, die an ``void_2`` hängt, saß danach am anderen.

    Geprüft wird deshalb an **zwei** Netzen mit denselben zwei Hohlräumen, die
    sich nur in der Anhängereihenfolge unterscheiden. Ohne die Sortierung nach
    der Mitte tauschen die Volumina zwischen den beiden Läufen die Plätze.
    """
    block = trimesh.creation.box(extents=(60.0, 40.0, 20.0))
    klein = trimesh.creation.cylinder(radius=1.0, height=9.0, sections=48)
    klein.invert()
    klein.apply_translation((-15.0, 0.0, 0.0))
    gross = trimesh.creation.cylinder(radius=2.0, height=9.0, sections=48)
    gross.invert()
    gross.apply_translation((15.0, 0.0, 0.0))

    namen: list[list[tuple[str, float]]] = []
    for reihenfolge in ([block, klein, gross], [block, gross, klein]):
        forget_cache()
        found = detect(MeshData.of(trimesh.util.concatenate(reihenfolge)))
        voids = sorted(
            (feature for feature in found.values() if feature.kind == "void"),
            key=lambda feature: feature.id,
        )
        assert len(voids) == 2, (
            f"die Vorbedingung: zwei Einschlüsse, gefunden {[f.id for f in voids]}"
        )
        namen.append([(str(f.id), round(float(f.params["volume"]), 1)) for f in voids])

    assert namen[0] == namen[1], (
        f"die Kennungen hängen an der Reihenfolge der Dreiecke: {namen[0]} gegen {namen[1]}"
    )
    # Und die Sortierung ist die nach der Mitte: der linke Hohlraum zuerst.
    assert namen[0][0][1] < namen[0][1][1], "void_1 sitzt bei x = -15 und ist der kleinere"


def test_a_lopsided_winding_is_not_an_air_pocket() -> None:
    """Ein Vorzeichen ist nur dort eine Auskunft, wo die Normalen zeigen.

    Drei Fälle, die die erste Fassung alle drei zum „Lufteinschluss" machte —
    und mit ihnen verschwanden die Flächen, auf denen sie lagen, aus dem
    Objektbaum. Gefunden bei der Durchsicht am 10.09.2026; keiner davon ist
    theoretisch: *Normalen vereinheitlichen* ist beim Einlesen ein abwählbarer
    Schalter, und ``trimesh`` dreht bei einem **zweiten** invertierten Körper
    ohnehin nichts (``fix_inversion`` sieht nur das Gesamtvolumen).

    Der teuerste ist der zweite: Dort ist der Fremdkörper echt, liegt sechzig
    Millimeter neben dem Teil — und stand als „Lufteinschluss im Material" da,
    während seine sechs Flächen gelöscht waren.
    """
    block = trimesh.creation.box(extents=(40.0, 40.0, 20.0))

    neighbour = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    neighbour.invert()
    neighbour.apply_translation((60.0, 0.0, 0.0))
    apart = MeshData.of(trimesh.util.concatenate([block, neighbour]))

    inside_out = block.copy()
    inside_out.invert()

    # **Der dritte Fall muss am Umlaufsinn scheitern und an nichts sonst** —
    # sonst prüft er ein anderes Tor als sein Name sagt. Gemessen bei der
    # Durchsicht am 10.09.2026: Ein *einteiliger* Quader mit gedrehten
    # Dreiecken fällt schon an ``len(components) < 2``, und werden die
    # Dreiecke des **Quaders** gedreht, wird er selbst negativ — dann gibt es
    # keine feste Umgebung, und die Einschlussprobe fängt ihn. In beiden
    # Fassungen blieb der Test grün, nachdem ``is_winding_consistent`` aus
    # ``detect_voids`` entfernt war.
    #
    # Gedreht werden deshalb Dreiecke der **Schale**: Der Quader bleibt fest
    # (Volumen +32 000), die Tasche bleibt negativ (-25,3 statt -28,3, und
    # schon diese Zahl ist falsch), und die Einschlussprobe sagt „innen". Übrig
    # bleibt genau ein Tor.
    pocket = trimesh.creation.cylinder(radius=1.0, height=9.0, sections=48)
    pocket.invert()
    two_parts = trimesh.util.concatenate([block, pocket])
    faces = two_parts.faces.copy()
    first_of_the_shell = len(block.faces)
    faces[first_of_the_shell : first_of_the_shell + 10] = faces[
        first_of_the_shell : first_of_the_shell + 10
    ][:, ::-1]
    mixed = trimesh.Trimesh(vertices=two_parts.vertices, faces=faces, process=False)
    assert not mixed.is_winding_consistent, "die Vorbedingung des dritten Falls"
    parts = features_module.face_components(mixed)
    volumes = [features_module._enclosed_volume(mixed, part) for part in parts]
    assert len(parts) == 2 and max(volumes) > 0.0, (
        "er muss an Komponentenzahl und fester Umgebung vorbeikommen, sonst misst "
        f"er die statt des Umlaufsinns: {[round(v, 1) for v in volumes]}"
    )

    for name, body in (
        ("ein getrennter umgestülpter Nachbarkörper", apart),
        ("ein vollständig umgestülptes Teil", MeshData.of(inside_out)),
        ("ein Teil mit uneinheitlichem Umlaufsinn", MeshData.of(mixed)),
    ):
        forget_cache()
        assert features_module.detect_voids(body) == [], name
        found = detect(body)
        assert any(feature.kind == "face" for feature in found.values()), (
            f"{name}: seine Flächen bleiben im Objektbaum"
        )
        assert not [feature for feature in found.values() if feature.kind == "void"], name


# --- gerundete Seiten ----------------------------------------------------------


def _letter(text: str) -> MeshData:
    """Ein Buchstabe aus der Schriftzug-Operation — 60 mm hoch, 5 mm dick.

    Dieselbe Schrift, mit der Robert den Fall sah: Ein D trug im Baum vier
    ebene Flächen und keinen seiner zwei Bögen.
    """
    from app.core.geom.label_ops import local_text_body

    forget_cache()
    return local_text_body(text, 60.0, "DejaVu Sans Mono", 5.0, style="regular", angle=0.0)


def test_the_two_bows_of_a_d_are_curved_faces_outside_and_inside() -> None:
    """Roberts Fall (11.09.2026, am Schriftzug): „bei den Seiten fehlen die
    gerundeten flächen". Ober- und Unterseite, die zwei geraden Flanken — und
    der Bogen außen wie der Bogen innen fehlten, weil sie weder Zylinder noch
    Kugel noch Ring sind und keine Ebene haben.

    Jetzt sind sie ``curved_face``: der große Bogen außen zuerst (die Größe
    ordnet wie bei den ebenen Flächen), der hohle innen als ``inner`` — aus
    der Konvexität seiner Nähte gelesen, nicht aus einer Normale, die ein
    Bogen nicht hat.
    """
    found = detect(_letter("D"))

    curved = [feature for feature in found.values() if feature.kind == "curved_face"]
    assert [feature.id for feature in curved] == ["curve_1", "curve_2"]
    outer, inner = curved
    assert outer.params["area"] > inner.params["area"], "der Bogen außen ist der größere"
    assert outer.params["inner"] is False and inner.params["inner"] is True
    assert outer.provenance == "detected" and outer.face_indices, "echte Dreiecke, kein Etikett"

    planar = [feature for feature in found.values() if feature.kind == "face"]
    assert len(planar) == 4, "die vier ebenen Flächen bleiben, wie sie waren"
    claimed = {index for feature in planar for index in feature.face_indices}
    assert not claimed & set(outer.face_indices) and not claimed & set(inner.face_indices), (
        "eine gerundete Seite ist der Rest — nie ein Dreieck, das einer Ebene gehört"
    )


def test_a_bow_keeps_its_area_when_its_facets_are_split() -> None:
    """Wird jede Manteldiagonale eines D formgleich geteilt, bleiben die Bögen dieselben.

    Aus jedem Rechteck des Mantels werden vier Dreiecke, und zwei davon
    berühren keine Rundungsnaht mehr — sie liegen nur an der Diagonale und an
    der Deckfläche. Gezählt wurde ein Dreieck bis dahin nur an einer Naht;
    am Besenhalter schrumpften die gerundeten Seiten so von 5 436 auf
    4 242 mm² (Befund B6 der Erkennungsdurchsicht, 24.09.2026).
    """
    letter = _letter("D")
    before = sorted(
        round(feature.params["area"], 6)
        for feature in detect(letter).values()
        if feature.kind == "curved_face"
    )
    body = letter.raw
    vertices = np.asarray(body.vertices).tolist()
    faces = np.asarray(body.faces).tolist()
    normals = np.asarray(body.face_normals)
    angles = np.asarray(body.face_adjacency_angles)
    split: dict[int, list[list[int]]] = {}
    for (first, second), (a, b), angle in zip(
        np.asarray(body.face_adjacency).tolist(),
        np.asarray(body.face_adjacency_edges).tolist(),
        angles,
        strict=True,
    ):
        if angle > 1e-9 or abs(normals[first][2]) > 0.5 or first in split or second in split:
            continue
        middle = len(vertices)
        vertices.append(((np.asarray(vertices[a]) + np.asarray(vertices[b])) / 2.0).tolist())
        for face in (first, second):
            corners = faces[face]
            at = corners.index(a)
            head, tail = (a, b) if corners[(at + 1) % 3] == b else (b, a)
            other = next(vertex for vertex in corners if vertex not in (a, b))
            split[face] = [[head, middle, other], [middle, tail, other]]
    assert split, "der Mantel hat Diagonalen"
    rebuilt = [row for index, corners in enumerate(faces) for row in split.get(index, [corners])]
    divided = MeshData.of(trimesh.Trimesh(np.asarray(vertices), np.asarray(rebuilt), process=False))
    assert divided.is_watertight and divided.volume == pytest.approx(letter.volume, rel=1e-12)

    forget_cache()
    after = sorted(
        round(feature.params["area"], 6)
        for feature in detect(divided).values()
        if feature.kind == "curved_face"
    )

    assert after == pytest.approx(before, rel=1e-9)


def test_the_curved_faces_of_a_letter_count_its_bows() -> None:
    """Ein o hat zwei ovale Mäntel, eine 3 zwei Bögen außen und zwei innen.

    Die o-Öffnung liegt an ihrer schlechtesten Stelle 0,447 mm neben einem
    Stadion mit Radius 8,334 mm. Ihr kleiner mittlerer Fehler belegte früher
    fälschlich ein Langloch. Ein I hat dagegen nur ebene Seiten.
    """
    found = detect(_letter("o"))
    curves = [f for f in found.values() if f.kind == "curved_face"]
    assert len(curves) == 2
    assert sorted(bool(f.params["inner"]) for f in curves) == [False, True]
    assert "slot" not in {f.kind for f in found.values()}, "die ovale Öffnung ist kein Stadion"

    found = detect(_letter("3"))
    inner_flags = sorted(bool(f.params["inner"]) for f in found.values() if f.kind == "curved_face")
    assert inner_flags == [False, False, True, True]

    found = detect(_letter("I"))
    assert not [f for f in found.values() if f.kind == "curved_face"]


def _arc(
    centre: tuple[float, float], radius: float, start: float, stop: float
) -> list[tuple[float, float]]:
    """Ein Bogen in Schritten von einem Grad, wie ein CAD-Export ihn tesselliert."""
    steps = round(abs(stop - start))
    return [
        (
            centre[0] + radius * math.cos(math.radians(start + (stop - start) * step / steps)),
            centre[1] + radius * math.sin(math.radians(start + (stop - start) * step / steps)),
        )
        for step in range(steps + 1)
    ]


def _extruded(outline: list[tuple[float, float]]) -> MeshData:
    """Der Umriss 20 mm hoch aufgezogen: Streifen über die ganze Höhe, Nadeldreiecke."""
    from shapely.geometry import Polygon

    return MeshData.of(trimesh.creation.extrude_polygon(Polygon(outline), 20.0))


def test_tangent_arcs_of_an_extrusion_are_each_a_fillet() -> None:
    """Zwei tangentiale Bögen R 5 und R 8 eines Prismas sind zwei Verrundungen (RM-219).

    Die Nachtrennung trennt erst am doppelten Radius (``CURVATURE_JUMP``), und
    auf beide Bögen zusammen passt kein Zylinder: Bis zum 25.09.2026 stand hier
    eine gerundete Seite, am Besenhalter acht davon mit Bögen von R 0,54 bis
    R 5,44. An einem Prisma trennt ``_arcs_of_a_prism`` an jedem Radiuswechsel.
    """
    outline = [
        (0.0, 0.0),
        *_arc((20.0, 5.0), 5.0, -90.0, 0.0)[:-1],
        *_arc((17.0, 5.0), 8.0, 0.0, 90.0),
        (0.0, 13.0),
    ]
    forget_cache()
    found = detect(_extruded(outline))

    rounds = sorted(float(f.params["radius"]) for f in found.values() if f.kind == "fillet")
    assert rounds == pytest.approx([5.0, 8.0], rel=1e-9)
    assert not [f for f in found.values() if f.kind == "curved_face"]


def test_a_prism_with_restless_radii_is_not_cut_into_arcs() -> None:
    """Springt der Radius je Dreieck an vielen Nähten, ist er Rauschen und kein Umriss.

    Derselbe Umriss aus R 5 und R 8, die Ecken um ±2 µm radial verrauscht: Der
    Radius je Dreieck springt dann an fast jeder Naht über ``PRISM_ARC_JUMP``,
    wie an Schriftzügen und Logos des Korpus (dort an 17 bis 58 Prozent der
    Nähte, an den Bögen einer Konstruktion höchstens an 6,9). Zerlegt, fielen
    Splitter heraus, die als kurze Stücke auf einen Kreis passen.
    """
    rng = np.random.default_rng(219)
    clean = [
        *_arc((20.0, 5.0), 5.0, -90.0, 0.0)[:-1],
        *_arc((17.0, 5.0), 8.0, 0.0, 90.0),
    ]
    centres = [(20.0, 5.0)] * 90 + [(17.0, 5.0)] * 91
    restless = []
    for (x, y), (cx, cy) in zip(clean, centres, strict=True):
        radius = math.hypot(x - cx, y - cy)
        push = 0.002 * (2.0 * rng.random() - 1.0) / radius
        restless.append((x + (x - cx) * push, y + (y - cy) * push))

    def arcs_of(profile: list[tuple[float, float]]) -> list[list[int]]:
        body = _extruded([(0.0, 0.0), *profile, (0.0, 13.0)]).raw
        normals = np.asarray(body.face_normals)
        side = [int(i) for i in np.flatnonzero(np.abs(normals[:, 2]) < 0.5)]
        piece = [
            i for i in side if abs(normals[i, 1] + 1.0) > 1e-6 and abs(normals[i, 0] + 1.0) > 1e-6
        ]
        piece = [i for i in piece if abs(normals[i, 1] - 1.0) > 1e-6]
        return features_module._arcs_of_a_prism(body, piece)

    assert len(arcs_of(clean)) >= 2, "ohne Rauschen trennt die Bogentrennung die zwei Bögen"
    assert arcs_of(restless) == []


def test_an_elliptic_extrusion_stays_one_curved_face() -> None:
    """Die Gegenrichtung: Wandert die Krümmung stetig, entsteht keine Verrundung.

    Die Trennung schneidet dort nicht — kein Nachbar weicht um zwei Prozent
    ab —, und auf den ganzen Ellipsenbogen passt kein Kreis.
    """
    outline = [
        (0.0, 0.0),
        *[
            (20.0 + 10.0 * math.cos(math.radians(turn)), 8.0 + 8.0 * math.sin(math.radians(turn)))
            for turn in range(-90, 91)
        ],
        (0.0, 16.0),
    ]
    forget_cache()
    found = detect(_extruded(outline))

    assert [f.kind for f in found.values() if f.kind != "face"] == ["curved_face"]


def _restless_ellipse(amount: float) -> MeshData:
    """Die halbe Ellipse von oben, jede Ecke um bis zu ``amount`` radial verrückt."""
    rng = np.random.default_rng(8)
    bow = []
    for turn in range(-90, 91):
        x = 20.0 + 10.0 * math.cos(math.radians(turn))
        y = 8.0 + 8.0 * math.sin(math.radians(turn))
        push = amount * (2.0 * rng.random() - 1.0) / math.hypot(x - 20.0, y - 8.0)
        bow.append((x + (x - 20.0) * push, y + (y - 8.0) * push))
    return _extruded([(0.0, 0.0), *bow, (0.0, 16.0)])


def test_a_restless_spline_is_a_curved_side_and_no_row_of_fillets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Umriss mit wanderndem Radius ist eine gerundete Seite (RM-243).

    Dieselbe Ellipse, die Ecken um ±1 µm radial verrauscht — so liegen die
    Buchstaben „RS" am Screen-Cover. Die Nachtrennung zerlegt den Umriss an
    den Sprüngen des Radius je Dreieck, und jedes Stück passt für sich auf
    einen Kreis: Bis zum 26.09.2026 standen hier zwölf Verrundungen von
    R 6,35 bis R 12,51. Die Stücke schließen tangential aneinander an, und
    der Radius wächst über drei Kreise hinweg — ein Verlauf, kein Übergang.
    """
    forget_cache()
    found = detect(_restless_ellipse(0.001))
    assert [f.kind for f in found.values() if f.kind != "face"] == ["curved_face"]

    # Ohne die Frage nach dem Verlauf stünden die Stücke als Verrundungen da;
    # sonst prüfte der Test nichts.
    monkeypatch.setattr(features_module, "_wandering_outline", lambda *_args: None)
    forget_cache()
    rows = [f for f in detect(_restless_ellipse(0.001)).values() if f.kind == "fillet"]
    assert len(rows) >= 3


def test_a_drawn_arc_beside_a_restless_spline_stays_a_fillet() -> None:
    """Ein CAD-Umriss setzt Bögen und Splines nebeneinander (RM-243).

    Die verrauschte Ellipse von oben läuft an ihrem Scheitel tangential in
    einen gezeichneten Bogen R 5 über, beides ein Fleck. Die Stücke der
    Ellipse fallen, der Bogen bleibt — wie am Screen-Cover der exakte Bogen
    R 22,975 im Schriftzug des Originals.
    """
    rng = np.random.default_rng(8)
    bow = []
    for turn in range(-90, 90):
        x = 20.0 + 10.0 * math.cos(math.radians(turn))
        y = 8.0 + 8.0 * math.sin(math.radians(turn))
        push = 0.001 * (2.0 * rng.random() - 1.0) / math.hypot(x - 20.0, y - 8.0)
        bow.append((x + (x - 20.0) * push, y + (y - 8.0) * push))
    drawn = [
        (20.0 + 5.0 * math.cos(math.radians(turn)), 11.0 + 5.0 * math.sin(math.radians(turn)))
        for turn in range(90, 181)
    ]
    forget_cache()
    found = detect(_extruded([(0.0, 0.0), *bow, *drawn, (0.0, 11.0)]))

    rounds = [float(f.params["radius"]) for f in found.values() if f.kind == "fillet"]
    assert rounds == pytest.approx([5.0], rel=1e-6)
    assert "curved_face" in {f.kind for f in found.values()}


def _basket_arch(flank: float, seed: int) -> MeshData:
    """Ein Korbbogen R 10 · R 16 · R 10 auf zwei Flanken, jede Ecke um bis zu
    0,6 µm radial verrückt."""
    rng = np.random.default_rng(seed)
    points = [(0.0, -flank), (0.0, 0.0)] if flank > 0.0 else [(0.0, 0.0)]
    x = y = 0.0
    heading = 90.0
    for radius, sweep in ((10.0, 50.0), (16.0, 80.0), (10.0, 50.0)):
        cx = x - radius * math.sin(math.radians(heading))
        cy = y + radius * math.cos(math.radians(heading))
        for step in range(1, round(sweep) + 1):
            angle = math.radians(heading - 90.0 + step)
            push = 0.0006 * (2.0 * rng.random() - 1.0)
            points.append(
                (
                    cx + (radius + push) * math.cos(angle),
                    cy + (radius + push) * math.sin(angle),
                )
            )
        heading += sweep
        x = cx + radius * math.cos(math.radians(heading - 90.0))
        y = cy + radius * math.sin(math.radians(heading - 90.0))
    if flank > 0.0:
        points.append((x, -flank))
    return _extruded(points)


@pytest.mark.parametrize("seed", [4, 7])
def test_a_basket_arch_keeps_its_arcs_although_the_radius_changes_twice(seed: int) -> None:
    """Zwei Wechsel gegeneinander sind kein Verlauf (RM-243).

    Auf 5 mm hohen Flanken zerlegt die Nachtrennung den verrauschten Korbbogen
    in Stücke, und jeder der drei Bögen kommt als Verrundung heraus. Der Radius
    steigt und fällt wieder — eine Konstruktion aus zwei Radien, wie die
    Flaschentasche, die in ihre engere Einlaufrundung übergeht. Die Stücke
    eines Bogens bestätigen einander, und ein Stück über der Naht zweier
    Bögen passt auf einen Zwischenkreis, ohne einen dritten Radius zu machen.
    Verlangte die Bestätigung beide Richtungen, verlöre die Saat 7 ihren
    Bogen R 16.
    """
    forget_cache()
    found = detect(_basket_arch(5.0, seed))

    rounds = sorted(float(f.params["radius"]) for f in found.values() if f.kind == "fillet")
    assert rounds == pytest.approx([10.0, 10.0, 16.0], rel=0.002)


@pytest.mark.parametrize("seed", [2, 10])
def test_a_single_change_of_radius_leaves_a_construction_alone(
    seed: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Wechsel ist ein Übergang (RM-243).

    Derselbe Korbbogen direkt auf der Grundlinie: Neben den Stücken der Bögen
    liegen dort Rauschstücke an den Ecken (R 8,3 bis R 9,0), die einen
    einzelnen tangentialen Wechsel zum Nachbarn bilden. Ein Wechsel allein
    macht keinen Umriss — die Erkennung gibt dasselbe wie ohne die Regel.
    """
    forget_cache()
    ruled = sorted(
        round(float(f.params["radius"]), 6)
        for f in detect(_basket_arch(0.0, seed)).values()
        if f.kind == "fillet"
    )
    monkeypatch.setattr(features_module, "_wandering_outline", lambda *_args: None)
    forget_cache()
    unruled = sorted(
        round(float(f.params["radius"]), 6)
        for f in detect(_basket_arch(0.0, seed)).values()
        if f.kind == "fillet"
    )
    assert len(unruled) >= 3, "ohne Rundungen prüft der Test nichts"
    assert ruled == unruled


def test_the_circle_pairs_of_an_outline_are_those_of_the_double_loop() -> None:
    """Die Vorauswahl der Kreispaare lässt kein Paar aus und ändert keine Folge.

    Die Bestätigung im wandernden Umriss fragte jedes Paar Kreise einzeln —
    am Meshy-Murmelbrett 12 961 Stücke in einem Fleck, 32 s für eine Frage
    (Durchsicht 0.5.1, erkennung-05). ``_circle_pairs`` nimmt vorher heraus,
    was keine der Bedingungen erfüllen kann. Geprüft wird gegen die
    Doppelschleife mit denselben Rechnungen, auch an den Grenzen selbst:
    Radien genau um :data:`CYLINDER_TOLERANCE` auseinander, Achsen genau auf
    dem Grenzwinkel, Versatz genau an :data:`SINK_FIT_LIMIT`.
    """
    from app.core import units
    from app.core.perceive.features import (
        CYLINDER_TOLERANCE,
        SINK_AXIS_LIMIT,
        SINK_FIT_LIMIT,
        CylinderFit,
        _circle_pairs,
    )

    generator = np.random.default_rng(243)
    limit = units.exact_cos_degrees(SINK_AXIS_LIMIT)
    fits: dict[int, CylinderFit] = {}
    for number in range(400):
        radius = float(generator.choice([2.0, 5.0, 11.0]) * (1.0 + 0.2 * generator.random()))
        axis = np.array([0.0, 0.0, 1.0]) + 0.05 * (generator.random(3) - 0.5)
        axis /= math.sqrt(float((axis * axis).sum()))
        centre = generator.random(3) * 2.0
        fits[3 * number] = CylinderFit(
            axis=tuple(float(value) for value in axis),
            centre=tuple(float(value) for value in centre),
            radius=radius,
            residual=0.0,
            inward=bool(generator.random() < 0.5),
        )
    # Genau an den Grenzen: Radius, Achswinkel, Querversatz.
    base = CylinderFit(
        axis=(0.0, 0.0, 1.0), centre=(0.0, 0.0, 0.0), radius=4.0, residual=0.0, inward=True
    )
    fits[5000] = base
    fits[5001] = dataclasses.replace(base, radius=4.0 / (1.0 - CYLINDER_TOLERANCE))
    tilt = math.sqrt(1.0 - limit * limit)
    fits[5002] = dataclasses.replace(base, axis=(tilt, 0.0, limit))
    fits[5003] = dataclasses.replace(base, centre=(4.0 * SINK_FIT_LIMIT, 0.0, 3.0))
    fits[5004] = dataclasses.replace(base, radius=4.0 * (1.0 - CYLINDER_TOLERANCE))
    numbers = sorted(fits)

    def accepted(one: int, other: int) -> bool:
        first, second = fits[one], fits[other]
        if first.inward is not second.inward:
            return False
        axis = np.asarray(first.axis, dtype=float)
        if abs(float((axis * np.asarray(second.axis, dtype=float)).sum())) < limit:
            return False
        offset = np.asarray(second.centre, dtype=float) - np.asarray(first.centre, dtype=float)
        across = offset - axis * float((offset * axis).sum())
        step = abs(first.radius - second.radius)
        scale = max(first.radius, second.radius)
        return (
            step <= scale * CYLINDER_TOLERANCE
            and math.sqrt(float((across * across).sum())) <= scale * SINK_FIT_LIMIT
        )

    expected = [
        (one, other)
        for position, one in enumerate(numbers)
        for other in numbers[position + 1 :]
        if accepted(one, other)
    ]
    assert len(expected) > 50, "ohne angenommene Paare prüft der Test nichts"
    pairs = _circle_pairs(fits, numbers, limit)
    assert [pair for pair in pairs if accepted(*pair)] == expected
    assert pairs == sorted(pairs), "dieselbe Folge wie die Doppelschleife"
    assert len(pairs) < len(numbers) * (len(numbers) - 1) // 20, "die Vorauswahl wählt aus"


def test_a_piece_of_an_outline_stays_when_the_merge_joined_it_to_a_face_elsewhere() -> None:
    """Zurückgezogen wird nur, was ganz auf dem Umriss liegt (RM-243).

    Am Eiffelturm lag ein Bruchstück der Bögen R 24 über 172 Grad in einem
    wandernden Nachbarfleck; die Zusammenlegung hatte es mit dem Hauptbogen
    vereint. Fiel alles, was den Umriss berührt, verloren zwei der vier
    Bögen 31 und 47 Dreiecke.
    """
    outline = np.zeros(8, dtype=bool)
    outline[[0, 1, 2]] = True
    entries = [("Umrissstück", [0, 1]), ("Bogen mit Bruchstück", [2, 3, 4]), ("anderswo", [5])]

    kept = features_module._off_the_outline(entries, outline)

    assert [name for name, _faces in kept] == ["Bogen mit Bruchstück", "anderswo"]


@pytest.mark.parametrize(
    "name",
    [
        "cube_clean.stl",
        "plate_holes.stl",
        "post_with_fillet.stl",
        "sphere_socket.stl",
        "torus_ring.stl",
    ],
)
def test_a_constructed_part_leaves_no_curved_face_over(name: str) -> None:
    """Am Korpus bleibt nichts übrig: Bohrung, Zapfen, Verrundung, Pfanne und
    Ring beanspruchen jedes gerundete Dreieck selbst. Eine gerundete Seite,
    die hier auftauchte, wäre ein Merkmal zu viel — und ein Filamentfeld an
    einem Fleck, den schon die Bohrung trägt."""
    forget_cache()
    found = detect(plate(name))
    assert not [f for f in found.values() if f.kind == "curved_face"], name


def test_a_freeform_gets_no_curved_face_because_its_skin_would_be_one(
    scan_detection: tuple[MeshData, dict[FeatureId, Feature], int],
) -> None:
    """Auf einem Scan wäre die ganze Haut eine einzige gerundete Seite, und
    die sagt nichts. Der Freiformfilter geht vor: Was er als erfunden verwirft,
    bekommt auch keinen Rest."""
    _mesh, found, dropped = scan_detection
    assert dropped > 0, "ohne Freiformurteil prüft der Test nichts"
    assert not [f for f in found.values() if f.kind == "curved_face"]


def test_turning_a_letter_does_not_renumber_its_curved_faces() -> None:
    """Dieselbe Stabilität wie bei den ebenen Flächen: Größe zuerst, dann die
    Eckennummern — und beides überlebt eine Drehung des Körpers."""
    upright = _letter("3")
    turned = MeshData.of(
        upright.raw.copy().apply_transform(
            trimesh.transformations.rotation_matrix(math.radians(90.0), (0.0, 0.0, 1.0))
        )
    )
    before = {
        f.id: (round(float(f.params["area"]), 1), f.params["inner"])
        for f in detect(upright).values()
        if f.kind == "curved_face"
    }
    forget_cache()
    after = {
        f.id: (round(float(f.params["area"]), 1), f.params["inner"])
        for f in detect(turned).values()
        if f.kind == "curved_face"
    }
    assert before == after and len(before) == 4


def test_the_patch_search_gives_what_the_row_by_row_filter_gave() -> None:
    """Die Fleckenbildung rechnet im Feld und antwortet wie zuvor (RM-132).

    Die Auswahl der Nachbarpaare stand als Schleife mit einer Menge daneben,
    das Ergebnis als ``int()`` je Dreieck — an einer verrauschten Freiform mit
    120 610 Flecken kostete beides zusammen hundert Millisekunden. Gerechnet
    wird jetzt über zwei Felder; geprüft wird gegen genau die Formulierung,
    die sie ersetzt, **einschließlich der Reihenfolge** — seit dem 23.09.2026
    der des Körpers (``in_body_order``): Die Einpassungen summieren in
    Fleckfolge, und die Erkennung darf nicht an der Folge der Dreiecke hängen.
    """
    mesh = plate("post_with_fillet.stl")
    body = mesh.raw
    planar = features_module._large_facet_faces(body)
    curved = [index for index in range(len(body.faces)) if index not in planar]

    def row_by_row(faces: list[int]) -> list[list[int]]:
        wanted = set(faces)
        pairs = np.asarray(body.face_adjacency)
        angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
        pairs = pairs[angles < features_module.CURVATURE_LIMIT]
        adjacency = [pair for pair in pairs if pair[0] in wanted and pair[1] in wanted]
        if not adjacency:
            return [[index] for index in faces]
        groups = trimesh.graph.connected_components(
            np.asarray(adjacency), nodes=np.asarray(faces), engine="scipy"
        )
        return [[int(index) for index in group] for group in groups]

    expected = features_module.in_body_order(body, row_by_row(curved))

    assert features_module._connected_patches(body, curved) == expected
    assert len(expected) > 1, "ein einziger Fleck prüft die Auswahl nicht"


def test_a_patch_search_without_a_single_neighbour_returns_each_triangle() -> None:
    """Der Randfall der Feldrechnung: keine zulässige Kante, jedes Dreieck für sich.

    Ein Ikosaeder knickt an jeder seiner Kanten um 41,8 Grad; unter
    ``CURVATURE_LIMIT`` bleibt keine einzige Nachbarschaft übrig. Vorher
    entschied darüber eine leere Liste, jetzt ein leeres Feld — und ``not []``
    und ``not len(feld)`` sind dieselbe Frage nur für den, der sie beide
    hingeschrieben hat. (Ein Würfel taugt dafür nicht: Seine zwei Dreiecke je
    Seite liegen in einer Ebene und sind damit Nachbarn.)
    """
    body = trimesh.creation.icosphere(subdivisions=0)
    faces = list(range(len(body.faces)))

    singles = [[index] for index in faces]
    assert features_module._connected_patches(body, faces) == features_module.in_body_order(
        body, singles
    )


# --- Lehren aus 34 Modellen aus dem Netz (15.09.2026) -----------------------------


def _mantle_split_by_angle(body: trimesh.Trimesh, cut: float) -> tuple[list[int], list[int]]:
    """Der Mantel eines Zylinders um Z, geteilt in einen kleinen Bogen bis ``cut`` Grad
    und den Rest."""
    normals = np.asarray(body.face_normals)
    centres = np.asarray(body.triangles_center)
    mantle = [index for index in range(len(body.faces)) if abs(normals[index][2]) < 0.5]
    angles = np.degrees(np.arctan2(centres[mantle, 1], centres[mantle, 0])) % 360.0
    small = [face for face, angle in zip(mantle, angles, strict=True) if angle < cut]
    big = [face for face, angle in zip(mantle, angles, strict=True) if angle >= cut]
    return small, big


def _with_small_arc_scaled(
    body: trimesh.Trimesh, small: list[int], factor: float
) -> trimesh.Trimesh:
    """Die Ecken des kleinen Bogens radial um ``factor`` versetzt — ein zweiter
    Zylinder derselben Achse, oder derselbe mit etwas Rauschen."""
    vertices = np.array(body.vertices, dtype=float)
    chosen = np.unique(np.asarray(body.faces)[small])
    vertices[chosen, :2] *= factor
    return trimesh.Trimesh(vertices, body.faces, process=False)


def test_a_patch_on_the_same_cylinder_joins_it_even_when_the_fit_spreads_more() -> None:
    """Gemessen an einem Uhrenteil (15.09.2026): Eine Bohrung Ø 30 kam nach dem
    Ändern einer anderen Bohrung in vier Bögen zurück; drei fanden zusammen, der
    vierte lag mit 0,003 mm auf demselben Kreis und hob die Streuung des
    gemeinsamen Fits über die seiner Teile — im Baum standen zwei Hohlkehlen R 15
    statt einer Bohrung. Ein Fleck, der im Vertrag des Fits auf der vorhandenen
    Wand liegt, gehört zu ihr."""
    from app.core.perceive.features import (
        _lies_on_the_cylinder,
        _merged_cylinders,
        _same_cylinder,
        angular_span,
        fit_cylinder,
    )

    body = trimesh.creation.cylinder(radius=15.0, height=4.0, sections=72)
    small, big = _mantle_split_by_angle(body, 45.0)
    body = _with_small_arc_scaled(body, small, 1.0 + 1e-4)
    mesh = MeshData.of(body)
    first, second = fit_cylinder(body, big), fit_cylinder(body, small)
    assert first is not None and second is not None
    assert _same_cylinder(body, (first, big), (second, small))
    together = fit_cylinder(body, big + small)
    assert together is not None
    assert together.spread > max(first.spread, second.spread), (
        "ohne die gewachsene Streuung misst dieser Test nichts"
    )
    assert _lies_on_the_cylinder(body, first, small)

    merged = _merged_cylinders(body, mesh, [(first, big), (second, small)])

    assert len(merged) == 1, "zwei Stücke derselben Wand sind ein Zylinder"
    assert angular_span(body, merged[0][0], merged[0][1]) > 300.0


def test_a_third_patch_joins_the_wall_that_the_first_two_already_made() -> None:
    """Der dritte Bogen findet die Wand, die die ersten zwei schon gemacht haben.

    Seit dem 22.09.2026 sucht :func:`_merged_cylinders` seine Kandidaten über
    vier Spalten statt über eine Schleife (Seite, Radius, Achsrichtung,
    Kollinearität — an einem Noppenfeld mit 1 403 Kuppen waren es 984 906
    Einzelfragen und 10,9 von 14 s der Erkennung). Der Fall, der dabei
    schiefgehen kann, ist genau dieser: Was schon zusammengefasst wurde, muss
    dem nächsten Stück weiter als Kandidat erscheinen.
    """
    from app.core.perceive.features import _merged_cylinders, angular_span, fit_cylinder

    body = trimesh.creation.cylinder(radius=15.0, height=4.0, sections=72)
    # Drei Bögen derselben Wand: 45 Grad, 45 Grad und der Rest.
    first_arc, rest = _mantle_split_by_angle(body, 45.0)
    second_arc = [face for face in rest if _angle_of(body, face) < 90.0]
    third_arc = [face for face in rest if _angle_of(body, face) >= 90.0]
    assert first_arc and second_arc and third_arc, "ohne drei Bögen misst dieser Test nichts"
    fits = [(fit_cylinder(body, arc), arc) for arc in (first_arc, second_arc, third_arc)]
    assert all(fit is not None for fit, _arc in fits)

    merged = _merged_cylinders(body, MeshData.of(body), [(fit, arc) for fit, arc in fits])

    assert len(merged) == 1, "drei Bögen derselben Wand sind ein Zylinder"
    assert angular_span(body, merged[0][0], merged[0][1]) > 300.0


def _angle_of(body: trimesh.Trimesh, face: int) -> float:
    """Der Winkel der Dreiecksmitte um die Z-Achse, in Grad von 0 bis 360."""
    centre = np.asarray(body.triangles_center, dtype=float)[face]
    return float(math.degrees(math.atan2(centre[1], centre[0])) % 360.0)


def test_a_patch_on_a_different_cylinder_stays_apart() -> None:
    """Die Gegenprobe zur Regel darüber: Fünf Prozent Radius liegen innerhalb der
    Toleranz von ``_same_cylinder`` und trotzdem nicht auf der Wand."""
    from app.core.perceive.features import (
        _lies_on_the_cylinder,
        _merged_cylinders,
        _same_cylinder,
        fit_cylinder,
    )

    body = trimesh.creation.cylinder(radius=15.0, height=4.0, sections=72)
    small, big = _mantle_split_by_angle(body, 45.0)
    # Getrennte Originalecken: Die Änderung des kleinen Bogens darf nicht
    # gleichzeitig die Randfacetten des großen Bogens verformen. Der frühere
    # gemeinsame Eckbestand erzeugte dort unbemerkt zwei echte Ausreißer.
    larger = body.submesh([big], append=True)
    smaller = body.submesh([small], append=True)
    smaller.apply_scale((1.05, 1.05, 1.0))
    body = trimesh.util.concatenate([larger, smaller])
    big = list(range(len(larger.faces)))
    small = list(range(len(larger.faces), len(body.faces)))
    for patch, expected in ((big, 15.0), (small, 15.75)):
        points = np.asarray(body.vertices)[np.unique(body.faces[patch])]
        assert np.linalg.norm(points[:, :2], axis=1) == pytest.approx(expected, abs=1e-9)
    first, second = fit_cylinder(body, big), fit_cylinder(body, small)
    assert first is not None and second is not None
    assert _same_cylinder(body, (first, big), (second, small)), (
        "ohne eine Paarung, die die Vorprüfung besteht, misst dieser Test nichts"
    )

    assert not _lies_on_the_cylinder(body, first, small)
    assert len(_merged_cylinders(body, MeshData.of(body), [(first, big), (second, small)])) == 2


def _plate_with_a_chamfered_slot() -> MeshData:
    """Eine Platte mit Langloch Ø 6 × 26, dessen Mündung eine 45-Grad-Fase trägt."""
    from shapely.geometry import LineString

    from app.core.geom.boolean import boolean

    plate = MeshData.of(trimesh.creation.box(extents=(60.0, 30.0, 8.0)))
    outline = LineString([(-10.0, 0.0), (10.0, 0.0)]).buffer(3.0, quad_segs=16)
    cutter = trimesh.creation.extrude_polygon(outline, height=20.0)
    cutter.apply_translation((0.0, 0.0, -10.0))
    lower = np.asarray(outline.exterior.coords, dtype=float)
    upper = np.asarray(outline.buffer(1.5, quad_segs=16).exterior.coords, dtype=float)
    chamfer = trimesh.convex.convex_hull(  # type: ignore[no-untyped-call]
        np.vstack(
            (
                np.column_stack((lower, np.full(len(lower), 3.0))),
                np.column_stack((upper, np.full(len(upper), 4.5))),
            )
        )
    )
    body = boolean("difference", [plate, MeshData.of(cutter)]).mesh
    return boolean("difference", [body, MeshData.of(chamfer)]).mesh


def test_the_chamfer_at_a_slot_mouth_belongs_to_the_slot() -> None:
    """Am Rahmen eines Schreibtisch-Organizers (MakerWorld, 15.09.2026) wurden aus
    33 gefasten Langlöchern 126 „Senkungen 90°" — je Langloch vier Halbkegel, an
    denen jede Operation absagte. Ein Kegelstück am Mantel eines Langlochs ist
    dessen Mündungsfase und geht darin auf."""
    mesh = _plate_with_a_chamfered_slot()
    found = detect(mesh)

    kinds = {
        kind: sum(feature.kind == kind for feature in found.values()) for kind in ("slot", "cone")
    }
    assert kinds == {"slot": 1, "cone": 0}, kinds
    slot = next(feature for feature in found.values() if feature.kind == "slot")
    normals = np.asarray(mesh.raw.face_normals)[list(slot.face_indices)]
    tilted = np.abs(normals[:, 2])
    assert np.any((tilted > 0.6) & (tilted < 0.8)), (
        "die Halbkegel der Fase stehen im Langloch, nicht daneben"
    )


def _plate_with_a_notch_below_half_a_turn() -> MeshData:
    """Ein Bogen von rund 130 Grad in der Kante einer Platte, dessen Enden in zwei
    konvexe Bögen übergehen — wie der Umriss eines Uhrenankers: kein Rand, an dem
    eine offene Bohrung mündet, und keine zwei Ebenen, die eine Kante ergäben."""
    from shapely.geometry import Point, box

    outline = box(-20.0, -10.0, 20.0, 10.0).difference(Point(0.0, 12.0).buffer(5.0, quad_segs=24))
    for side in (-1.0, 1.0):
        outline = outline.union(Point(side * 4.58, 10.0).buffer(3.0, quad_segs=16))
    return MeshData.of(trimesh.creation.extrude_polygon(outline, height=6.0))


def test_the_panel_greys_what_a_fillet_without_two_planes_cannot_do() -> None:
    """50 von 52 Versuchen an Umrissbögen aus 34 Netzmodellen endeten nach dem Klick
    mit „grenzt nicht an zwei ebene Flächen" (15.09.2026). Das Panel stellt die
    Frage der Operation vorher — mit ihrem Satz."""
    from app.core.geom.edges import NOT_BETWEEN_TWO_PLANES
    from app.core.perceive.actions import fillet_blocked

    mesh = _plate_with_a_notch_below_half_a_turn()
    found = detect(mesh)
    arc = next(
        feature
        for feature in found.values()
        if feature.kind == "fillet" and feature.params.get("recess")
    )
    assert arc.params.get("radial") is None, "unter 180 Grad ist der Bogen keine runde Wand"

    assert fillet_blocked(arc, found, mesh) is NOT_BETWEEN_TWO_PLANES
    from app.core.registry import REGISTRY

    titles = {str(REGISTRY.get(name).title) for name in ("remove_feature", "resize_feature")}
    greyed = {
        str(row.title): row.reason
        for row in actions_for(arc, found, mesh=mesh)
        if str(row.title) in titles
    }
    assert len(greyed) == 2 and all(
        reason is NOT_BETWEEN_TWO_PLANES for reason in greyed.values()
    ), greyed
    assert fillet_blocked(arc, found, None) is None, "ohne Netz keine Vermutung"


def test_an_edge_fillet_between_two_planes_keeps_its_rows() -> None:
    """Die Gegenprobe: eine echte verrundete Quaderkante bleibt bedienbar."""
    from app.core.geom.edges import round_edges
    from app.core.perceive.actions import fillet_blocked

    body = round_edges(
        MeshData.of(trimesh.creation.box(extents=(30.0, 20.0, 10.0))), 3.0, "vertical"
    ).mesh
    found = detect(body)
    edge = next(feature for feature in found.values() if feature.kind == "fillet")

    assert fillet_blocked(edge, found, body) is None
    from app.core.registry import REGISTRY

    offered = {str(row.title): row.op for row in actions_for(edge, found, mesh=body)}
    assert offered[str(REGISTRY.get("remove_feature").title)] == "remove_feature"
    assert offered[str(REGISTRY.get("resize_feature").title)] == "resize_feature"


def test_a_fillet_click_reads_the_planes_of_a_body_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Ebenen eines Körpers entstehen je Körper einmal, nicht je Klick.

    ``fillet_blocked`` fragte bei **jeder** Auswahl einer Rundung die volle
    Flächenerkennung (``detect_faces``) im Hauptfaden — mit Trägern und
    Innenlage, die die Maske gar nicht liest. Am Halter mit Wabenmuster
    (``large-screwdriver-holder-with-honeycomb-pattern.stl``, 7 956 Dreiecke)
    kostete ein Rundungsklick so 560 bis 610 ms, jedes Mal (22.09.2026).
    Die Maske braucht nur die Facetten; sie bleibt am Körper gemerkt, und der
    Zwilling in ``edges._around`` liest dieselbe.
    """
    from app.core.geom.edges import round_edges
    from app.core.perceive.actions import fillet_blocked
    from app.core.perceive.features import detect_faces, face_mask, planar_mask

    body = round_edges(
        MeshData.of(trimesh.creation.box(extents=(30.0, 20.0, 10.0))), 3.0, "vertical"
    ).mesh
    found = detect(body)
    edges = [feature for feature in found.values() if feature.kind == "fillet"]
    assert len(edges) >= 2
    expected = face_mask(body, detect_faces(body))
    assert np.array_equal(planar_mask(body), expected), "dieselbe Menge wie die volle Erkennung"

    forget_cache()
    reads: list[int] = []
    original = features_module._planar_face_entries

    def counted(*args: Any, **kwargs: Any) -> Any:
        reads.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(features_module, "_planar_face_entries", counted)
    for edge in (*edges, *edges):
        assert fillet_blocked(edge, found, body) is None

    assert len(reads) == 1, "je Körper einmal gelesen, nicht je Klick"


def test_the_panel_welds_and_indexes_a_body_once_for_all_bores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Mündungsprobe einer gesenkten Bohrung verschweißt und indiziert den Körper einmal.

    ``bore_entrance`` — das Merkmalfenster fragt es für jede angeklickte
    Bohrung mit Senkung — kopierte und verschweißte den ganzen Körper dreimal
    und baute für die Mündungsprobe einen Suchbaum über alle Dreiecke. Am
    Gartenschlauchhalter mit 392 532 Dreiecken kostete ein Klick so bis zu
    0,4 s im Hauptfaden, am Bohrhalter 48 ms je Bohrung (RM-181, gemessen am
    22.09.2026). Beides ist eine Eigenschaft des Körpers und nicht der
    Bohrung.
    """
    from app.core.geom import mesh as mesh_module

    bodies = []
    for x in (0.0, 30.0):
        profile = [[12.0, 0.0], [12.0, 10.0], [5.5, 10.0], [5.5, 8.5], [3.0, 6.0], [3.0, 0.0]]
        body = trimesh.creation.revolve([*profile, [12.0, 0.0]], sections=48)
        body.apply_translation([x, 0.0, 0.0])
        bodies.append(body)
    mesh = MeshData.of(trimesh.util.concatenate(bodies))
    found = detect(mesh)
    from app.core.perceive.relations import cavity_chains

    bores = [chain[0] for chain in cavity_chains(found, mesh)]
    assert len(bores) == 2, "zwei Bohrungen mit Senkung"

    welds: list[int] = []
    indexes: list[int] = []
    merge, index_of = trimesh.Trimesh.merge_vertices, mesh_module._SurfaceIndex.of

    def counted_merge(self: trimesh.Trimesh, *args: Any, **kwargs: Any) -> Any:
        welds.append(1)
        return merge(self, *args, **kwargs)

    def counted_index(body: trimesh.Trimesh) -> Any:
        indexes.append(1)
        return index_of(body)

    monkeypatch.setattr(trimesh.Trimesh, "merge_vertices", counted_merge)
    monkeypatch.setattr(mesh_module._SurfaceIndex, "of", staticmethod(counted_index))
    offered = []
    for bore in bores:
        for _repeat in range(2):
            rows = actions_for(bore, found, mesh=mesh)
            offered.append({row.op for row in rows if row.op})

    assert all("resize_hole" in ops for ops in offered)
    assert len(welds) <= 1, f"{len(welds)} verschweißte Kopien für {len(offered)} Handlungslisten"
    assert len(indexes) <= 1, f"{len(indexes)} Suchbäume für {len(offered)} Handlungslisten"


def test_the_nearly_flat_sides_of_a_body_are_read_once() -> None:
    """Die gerundeten Seiten, die als Ebene neben einer Rundung gelten, liest der Körper einmal.

    Am Countercleaner (701 900 Dreiecke) las jede Frage des Merkmalfensters
    die großen gerundeten Seiten neu — 0,1 s je Klick auf eine Rundung.
    """
    from shapely import affinity
    from shapely.geometry import Point, box

    from app.core.perceive.features import nearly_flat_mask

    # Ein elliptischer Bogen ist kein Zylinder — er bleibt eine gerundete Seite.
    arc = affinity.scale(Point(0.0, 0.0).buffer(10.0, quad_segs=32), 1.6, 1.0)
    outline = box(-20.0, -10.0, 0.0, 10.0).union(arc)
    body = MeshData.of(trimesh.creation.extrude_polygon(outline, height=6.0))
    found = detect(body)
    assert any(feature.kind == "curved_face" for feature in found.values()), sorted(
        feature.kind for feature in found.values()
    )

    first = nearly_flat_mask(body.raw, found)
    assert nearly_flat_mask(body.raw, found) is first, "dieselbe gemerkte Antwort"
    assert not first.flags.writeable
    changed = {name: feature for name, feature in found.items() if feature.kind != "curved_face"}
    assert not nearly_flat_mask(body.raw, changed).any(), "ohne gerundete Seite keine Ebene"


def test_the_panel_builds_the_body_of_a_cone_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ob eine Kegelmulde einen eigenen Körper hat, wird je Körper einmal gefragt.

    ``no_own_body`` baute für jeden Klick auf einen Kegel den Körper aus seinen
    Flächen neu und richtete dessen Normalen aus — am Sieb aus
    ``Siebhalter+X1C.3mf`` (1 484 Dreiecke) 200 ms je Klick (RM-181).
    """
    from app.core.geom import prepare_ops
    from app.core.geom.boolean import boolean

    plate = MeshData.of(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    tip = trimesh.creation.cone(radius=8.0, height=6.0, sections=64)
    tip.apply_transform(trimesh.transformations.rotation_matrix(math.pi, (1.0, 0.0, 0.0)))
    tip.apply_translation((0.0, 0.0, 5.0 + EPS_GEOM))
    body = boolean("difference", [plate, MeshData.of(tip)]).mesh
    found = detect(body)
    cones = [feature for feature in found.values() if feature.kind == "cone"]
    assert len(cones) == 1, sorted(feature.kind for feature in found.values())

    builds: list[int] = []
    original = prepare_ops._body_from_faces

    def counted(*args: Any, **kwargs: Any) -> Any:
        builds.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(prepare_ops, "_body_from_faces", counted)
    first = actions_for(cones[0], found, mesh=body)
    second = actions_for(cones[0], found, mesh=body)

    assert [row.op for row in first] == [row.op for row in second]
    assert len(builds) <= 1, f"{len(builds)} Körperbauten für zwei Handlungslisten"


@pytest.mark.parametrize(
    "name",
    (
        "plate_holes.stl",
        "plate_countersunk.stl",
        "block_with_rounded_edge.stl",
        "post_with_fillet.stl",
    ),
)
def test_the_planar_mask_is_the_mask_of_the_detected_faces(name: str) -> None:
    """Dieselbe Dreiecksmenge wie ``face_mask(mesh, detect_faces(mesh))`` — nur ohne
    Träger und Innenlage gerechnet. Panel und Operation fragen beide diese Maske."""
    from app.core.perceive.features import detect_faces, face_mask, planar_mask

    mesh = normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh

    expected = face_mask(mesh, detect_faces(mesh))
    assert expected.any(), "jeder dieser Körper hat ebene Flächen"
    assert np.array_equal(planar_mask(mesh), expected)
    assert not planar_mask(mesh).flags.writeable, "die gemerkte Antwort bleibt unverändert"


def _tab_with_a_round_end() -> MeshData:
    """Eine Lasche: ein Rechteck, dessen Ende ein Halbkreis ist — die runde Wand geht
    tangential in die beiden Flanken über."""
    from shapely.geometry import LineString

    outline = LineString([(0.0, 0.0), (0.0, -20.0)]).buffer(6.0, quad_segs=24)
    body = trimesh.creation.extrude_polygon(outline, height=4.0)
    return MeshData.of(body)


def test_a_round_wall_that_blends_into_its_flanks_says_so_before_the_click() -> None:
    """Der Umrissbogen eines Uhrenankers geht tangential in seine Flanken über; radial
    versetzt schöbe er sie aus ihrer Ebene, und ``radial_rounding`` sagte erst nach
    dem Klick ab — 32 Mal in sieben Modellen (15.09.2026). Die Erkennung sagt es
    vorher, Panel und Operation mit demselben Satz."""
    from app.core.perceive.actions import WALL_BLENDS_INTO_ITS_NEIGHBOURS

    mesh = _tab_with_a_round_end()
    found = detect(mesh)
    walls = [feature for feature in found.values() if feature.kind == "fillet"]
    assert walls, "ohne runde Wand misst dieser Test nichts"
    wall = walls[0]
    assert wall.params.get("radial") is True
    assert wall.params.get("tangent") is True

    from app.core.registry import REGISTRY

    rows = {str(row.title): row for row in actions_for(wall, found, mesh=mesh)}
    for name in ("remove_feature", "resize_feature"):
        row = rows[str(REGISTRY.get(name).title)]
        assert row.op is None and row.reason is WALL_BLENDS_INTO_ITS_NEIGHBOURS, (name, row)


def _plate_with_half_a_cone() -> MeshData:
    """Ein Kegelstumpf auf einer Platte, beide durch die Kegelachse halbiert: ein
    Kegelstück von 180 Grad, das zu keinem Langloch und keiner Bohrung gehört."""
    from app.core.geom.boolean import boolean

    plate = trimesh.creation.box(extents=(30.0, 30.0, 6.0))
    plate.apply_translation((0.0, 0.0, 3.0))
    boss = trimesh.creation.revolve([[0.0, 6.0], [6.0, 6.0], [3.0, 9.0], [0.0, 9.0]], sections=64)
    body = boolean("union", [MeshData.of(plate), MeshData.of(boss)]).mesh
    knife = trimesh.creation.box(extents=(40.0, 40.0, 40.0))
    knife.apply_translation((0.0, -20.0, 0.0))
    return boolean("difference", [body, MeshData.of(knife)]).mesh


def test_a_cone_piece_stays_in_the_tree_as_a_conical_face_without_body_actions() -> None:
    """Die Blütenblätter eines Gewindeprüfers sind Kegel von 259 Grad, die
    Kastenecken eines Organizers Viertelkegel: keine Senkung, keine Verjüngung,
    aber auch nichts, was verschwinden dürfte — ohne sie hielt die Freiformprobe
    vier Körper für Figuren. Ein Kegelstück bleibt als Kegelfläche im Baum, und
    jede Körperhandlung steht grau mit dem Satz, den auch die Operation sagt."""
    from app.core.perceive.actions import CONE_PIECE_HAS_NO_BODY, cone_piece_blocked
    from app.core.perceive.digest import _feature_line

    mesh = _plate_with_half_a_cone()
    found = detect(mesh)
    cones = [feature for feature in found.values() if feature.kind == "cone"]
    assert len(cones) == 1, [feature.id for feature in cones]
    piece = cones[0]
    assert piece.params.get("partial") is True
    assert cone_piece_blocked(piece) is CONE_PIECE_HAS_NO_BODY
    assert "Kegelfläche" in _feature_line(piece.id, piece)

    rows = actions_for(piece, found, mesh=mesh)
    offered = [row for row in rows if row.op is not None]
    assert not offered, [str(row.title) for row in offered]
    # Jede Zeile, deren Operation einen Kegel annähme, trägt den Satz; die Zeile
    # *Zum Langloch ziehen* gilt keinem Kegel und behält ihren eigenen.
    with_the_sentence = [row for row in rows if row.reason is CONE_PIECE_HAS_NO_BODY]
    assert len(with_the_sentence) >= 5, [str(row.reason)[:40] for row in rows]


def test_a_cone_piece_is_refused_by_the_operation_with_the_same_sentence() -> None:
    """Chat und Kommandozeile kommen am Panel vorbei — die Operation sagt dasselbe."""
    from app.core.errors import ValidationError
    from app.core.geom.prepare_ops import _movable_feature
    from app.core.perceive.actions import CONE_PIECE_HAS_NO_BODY
    from app.core.types import SceneObject

    mesh = _plate_with_half_a_cone()
    found = detect(mesh)
    piece = next(feature for feature in found.values() if feature.kind == "cone")
    source = SceneObject(id="obj_1", name="Halbkegel", mesh=mesh, features=found)

    with pytest.raises(ValidationError) as problem:
        _movable_feature(source, piece.id, "move_feature")
    assert problem.value.detail is CONE_PIECE_HAS_NO_BODY


def _plate_with_a_cross_bored_boss() -> MeshData:
    """Ein Kegelstumpf auf einer Platte mit einer Querbohrung durch seinen Mantel:
    drei Randringe, kein Körper aus den Flächen."""
    from app.core.geom.boolean import boolean

    plate = trimesh.creation.box(extents=(30.0, 30.0, 6.0))
    plate.apply_translation((0.0, 0.0, 3.0))
    boss = trimesh.creation.revolve([[0.0, 6.0], [6.0, 6.0], [4.5, 10.0], [0.0, 10.0]], sections=64)
    body = boolean("union", [MeshData.of(plate), MeshData.of(boss)]).mesh
    across = trimesh.creation.cylinder(radius=1.0, height=30.0, sections=32)
    across.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (0.0, 1.0, 0.0)))
    across.apply_translation((0.0, 0.0, 8.0))
    return boolean("difference", [body, MeshData.of(across)]).mesh


def test_a_cone_without_a_body_of_its_own_is_greyed_with_the_sentence_of_the_operation() -> None:
    """Uhrenteil 16 (15.09.2026): fünf Absagen nach dem Klick an einem Kegel, dessen
    Rand drei Ringe hat — das Panel bot jede Zeile an. Es fragt jetzt vorher, was
    ``_tool_for`` fragt, und schreibt denselben Satz."""
    from app.core.errors import ValidationError
    from app.core.geom.prepare_ops import NO_BODY_FROM_FACES, _tool_for
    from app.core.perceive.actions import no_own_body

    mesh = _plate_with_a_cross_bored_boss()
    found = detect(mesh)
    cone = next(feature for feature in found.values() if feature.kind == "cone")
    assert not cone.params.get("recess") and not cone.params.get("partial")

    assert no_own_body(cone, (), False, mesh) is NO_BODY_FROM_FACES
    greyed = {str(row.title): row for row in actions_for(cone, found, mesh=mesh)}
    assert all(row.op is None for row in greyed.values()), [
        title for title, row in greyed.items() if row.op is not None
    ]
    with pytest.raises(ValidationError) as problem:
        _tool_for(mesh, cone, tuple(float(v) for v in cone.params["centre"]), alone=True)
    assert problem.value.detail is NO_BODY_FROM_FACES


def _block_with_a_round_bottomed_v() -> MeshData:
    """Ein Klotz mit einer flachen V-Nut (Flanken unter 17 Grad), an deren Grund
    ein Kreis sitzt, der die Flanken schräg schneidet: ein Bogen von rund 156 Grad
    zwischen zwei Ebenen, die ihn nicht tangential fortsetzen."""
    from shapely.geometry import Point, Polygon, box

    outline = (
        box(0.0, 0.0, 40.0, 20.0)
        .difference(Polygon([(20.0, 15.0), (36.67, 20.0), (3.33, 20.0)]))
        .difference(Point(20.0, 17.0).buffer(4.0, quad_segs=24))
    )
    return MeshData.of(trimesh.creation.extrude_polygon(outline, height=10.0))


def test_two_planes_that_cut_the_arc_obliquely_are_no_edge_under_it() -> None:
    """An den Gleisen einer Modellscheune (15.09.2026) rechnete *Entfernen* aus zwei
    Ebenen neben einer Hohlkehle eine Kante, die es nicht gibt, trug 2,7 Prozent
    des Volumens ab und ließ die Hohlkehle stehen. Zwei Ebenen neben einem Bogen
    sind nur dann seine Kante, wenn sie ihn tangential fortsetzen — das prüfen
    Panel und Operation jetzt gleich."""
    from app.core.errors import GeometryError
    from app.core.geom.edges import NOT_BETWEEN_TWO_PLANES, sharp_corner
    from app.core.perceive.actions import fillet_blocked

    mesh = _block_with_a_round_bottomed_v()
    found = detect(mesh)
    arc = next(
        feature
        for feature in found.values()
        if feature.kind == "fillet" and feature.params.get("recess")
    )
    assert arc.params.get("radial") is None, "unter 180 Grad ist der Bogen keine runde Wand"

    assert fillet_blocked(arc, found, mesh) is NOT_BETWEEN_TWO_PLANES
    with pytest.raises(GeometryError) as problem:
        sharp_corner(mesh, arc)
    assert problem.value.detail is NOT_BETWEEN_TWO_PLANES


def _cup_with_a_boss_inside() -> MeshData:
    """Ein Ring Ø70/Ø60 auf einem Boden, in der Mitte ein Zapfen Ø16: Die Innenwand
    hat die Gestalt eines Bohrungsmantels, aber in ihrem Zylinder steht Material."""
    from app.core.geom.boolean import boolean

    ring = trimesh.creation.annulus(r_min=30.0, r_max=35.0, height=5.0)
    ring.apply_translation((0.0, 0.0, 3.5))
    floor = trimesh.creation.cylinder(radius=35.0, height=1.0, sections=96)
    floor.apply_translation((0.0, 0.0, 0.5))
    boss = trimesh.creation.cylinder(radius=8.0, height=5.0, sections=64)
    boss.apply_translation((0.0, 0.0, 3.5))
    return boolean("union", [MeshData.of(ring), MeshData.of(floor), MeshData.of(boss)]).mesh


def test_a_hole_with_material_inside_is_a_wall_and_every_row_says_so() -> None:
    """Uhrenteil 06 (15.09.2026): Die Innenwand eines Rades mit Speichen und Nabe,
    Ø 66,8, stand als Bohrung im Baum. Ihre Flächen ergeben keinen Körper, also
    baute *Versetzen* den vollen Zylinder aus den Kennzahlen — minus 49 Prozent
    Volumen und drei lose Teile nach 1,5 mm. Panel und Operation fragen jetzt,
    ob im Zylinder Material steht, und sagen denselben Satz."""
    from app.core.errors import ValidationError
    from app.core.geom.prepare_ops import HOLE_IS_NOT_EMPTY, _tool_for, hole_is_clear
    from app.core.perceive.actions import no_own_body

    mesh = _cup_with_a_boss_inside()
    found = detect(mesh)
    wall = max(
        (feature for feature in found.values() if feature.kind == "hole"),
        key=lambda feature: float(feature.params["diameter"]),
    )
    assert float(wall.params["diameter"]) == pytest.approx(60.0, abs=0.5)
    assert not hole_is_clear(mesh, wall)
    assert no_own_body(wall, (), False, mesh) is HOLE_IS_NOT_EMPTY
    rows = actions_for(wall, found, mesh=mesh)
    assert rows and all(row.op is None for row in rows), [
        str(row.title) for row in rows if row.op is not None
    ]
    with pytest.raises(ValidationError) as problem:
        _tool_for(mesh, wall, tuple(float(v) for v in wall.params["centre"]), alone=True)
    assert problem.value.detail is HOLE_IS_NOT_EMPTY

    # Und eine leere Bohrung bleibt eine: dieselbe Frage, andere Antwort.
    plate = trimesh.creation.box(extents=(30.0, 30.0, 6.0))
    bore = trimesh.creation.cylinder(radius=3.0, height=8.0, sections=64)
    from app.core.geom.boolean import boolean

    clean = boolean("difference", [MeshData.of(plate), MeshData.of(bore)]).mesh
    hole = next(feature for feature in detect(clean).values() if feature.kind == "hole")
    assert hole_is_clear(clean, hole)


def test_a_pocket_over_a_small_hole_in_its_floor_is_not_through() -> None:
    """Der Minigolf-Becher (15.09.2026): Topf Ø 116, im Boden eine Bohrung Ø 8 auf
    derselben Achse. Über der Achse lag kein Dreieck, also galt der Topf als
    durchgehend — und *Versetzen* schnitt ihn mit einem Messer von
    Durchmesserlänge quer durch den Boden. Durch eine Bohrung sieht man nur
    hindurch, wenn ihre ganze Mündung frei ist."""
    from app.core.geom.boolean import boolean

    plate = trimesh.creation.box(extents=(30.0, 30.0, 10.0))
    pocket = trimesh.creation.cylinder(radius=10.0, height=6.0, sections=96)
    pocket.apply_translation((0.0, 0.0, 5.0))
    pin_hole = trimesh.creation.cylinder(radius=2.0, height=14.0, sections=48)
    mesh = boolean(
        "difference", [MeshData.of(plate), MeshData.of(pocket), MeshData.of(pin_hole)]
    ).mesh
    holes = {
        round(float(feature.params["diameter"])): feature
        for feature in detect(mesh).values()
        if feature.kind == "hole"
    }
    assert set(holes) == {20, 4}, sorted(holes)
    assert holes[20].params["through"] is False, "der Boden mit dem Loch ist ein Boden"
    assert holes[4].params["through"] is True, "und die kleine Bohrung geht durch"


def _widened_through_bore(bands: int) -> MeshData:
    """Platte 30 × 30 × 10, Ø 5 durch, oben Ø 9 zwei Millimeter tief, dazwischen 45 Grad Übergang.

    ``bands`` sagt, in wie viele Ringe der Übergangskegel tesselliert ist: Ein
    Ring ist die Bauart des Netzbohrers, vier sind die der Tessellierung des
    exakten Körpers (BRepMesh) — und dort berührt nur der äußerste Ring die
    Endebene der Aufweitung.
    """
    from app.core.geom.boolean import boolean

    steps = [(2.5 + 2.0 * step / bands, 6.0 + 2.0 * step / bands) for step in range(bands + 1)]
    profile = [(0.0, -1.0), (2.5, -1.0), *steps, (4.5, 11.0), (0.0, 11.0)]
    tool = trimesh.creation.revolve(profile, sections=64)
    plate = trimesh.creation.box(extents=(30.0, 30.0, 10.0))
    plate.apply_translation((0.0, 0.0, 5.0))
    return boolean("difference", [MeshData.of(plate), MeshData.of(tool)]).mesh


@pytest.mark.parametrize("bands", [1, 4], ids=["netzgebohrt", "tesselliert"])
def test_the_widening_over_a_through_bore_is_not_through_however_it_is_tessellated(
    bands: int,
) -> None:
    """Die Aufweitung Ø 9 über einer Ø-5-Durchgangsbohrung endet am Übergang — an jedem Netz.

    Der Abschnitt der Aufweitung sah vom Übergangskegel nur das Band, das
    ihre Endebene berührt: am netzgebohrten Zwilling der ganze Kegel, an der
    Tessellierung des exakten Körpers ein Streifen von 4,0 bis 4,5 mm Radius
    — und der Ring bei 0,6 (2,7 mm) blieb frei, die Aufweitung hieß dort
    durchgehend, der exakte Kern sagte nein (Kreuzbefund Paket A, 22.09.2026).
    Gefragt werden jetzt die Flächen, die an den Mantel grenzen, in ganzer
    Länge — dieselbe Frage wie ``brep.features._axis_covered``. Die Bohrung
    selbst bleibt durchgehend, und der gegenüberliegende Schenkel des U-Profils
    (``test_a_bore_through_one_leg_of_a_u_is_a_through_bore``) zählt weiter
    nicht: Er grenzt nicht an den Mantel.
    """
    forget_cache()
    holes = {
        round(float(feature.params["diameter"]), 1): feature.params["through"]
        for feature in detect(_widened_through_bore(bands)).values()
        if feature.kind == "hole"
    }
    assert holes == {5.0: True, 9.0: False}, holes


def test_the_widening_reads_the_same_on_the_tessellated_exact_body() -> None:
    """Dieselbe Aufweitung aus dem exakten Kern, gelesen an seiner Tessellierung (P1.5)."""
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.prepare import drill_outline
    from app.core.knowledge import profiles
    from app.core.sketch.planes import frame_of

    outline = drill_outline(
        diameter=5.0,
        depth=12.0,
        profile=profiles.make_profile("centauri-carbon-2", "petg"),
        compensate=False,
        widening_diameter=9.0,
        widening_depth=2.0,
        transition_angle=90.0,
    )
    body = edit.bore_profile(
        edit.box(60.0, 40.0, 10.0), outline, frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 10.0))
    )
    exact = {
        round(float(feature.params["diameter"]), 1): feature.params["through"]
        for feature in features_of(body).values()
        if feature.kind == "hole"
    }
    assert exact == {5.0: True, 9.0: False}, exact
    for deflection in (0.1, 0.02):
        forget_cache()
        meshed = {
            round(float(feature.params["diameter"]), 1): feature.params["through"]
            for feature in detect(as_mesh_data(body.to_mesh(deflection=deflection))).values()
            if feature.kind == "hole"
        }
        assert meshed == exact, (deflection, meshed)


def test_a_patch_missing_one_triangle_gets_it_back() -> None:
    """Ein Band aus Dreiecken ohne eines hat keinen brauchbaren Rand mehr.

    **Der Fall ist plattformabhängig und gemessen** (17.09.2026): Die Senkung
    aus ``test_shrinking_keeps_the_countersink_and_recognises_the_new_shoulder``
    trägt auf Windows und Ubuntu 241 Dreiecke, auf dem Mac der CI 240 — bei
    identischen Maßen und identischen Bohrungen daneben. Welches herausfällt,
    entscheidet die letzte Stelle einer Normalen.

    Was das kostet, ist nicht ein Dreieck, sondern der ganze Zusammenhang:
    ``relations.boundary_rings`` verlangt an jedem Randknoten genau zwei
    Randkanten. Fehlt eines, laufen dort vier zusammen, aus zwei Randringen
    wird einer, und ohne Ringe findet ``cavity_chain_at`` die Kette
    Bohrung–Senkung nicht mehr.

    Gefahren wird der Fall an jedem Dreieck des Bandes einzeln — jedes ist der
    Mac-Fall, den es hier nicht gibt.
    """
    from app.core.perceive.features import _notch_faces, _without_notches

    # Ein Kegelmantel: dasselbe Band, das die Senkung einer Bohrung bildet.
    profile = [(3.0, 0.0), (6.0, 3.0)]
    body = trimesh.creation.revolve(profile, sections=48)
    faces = list(range(len(body.faces)))
    assert not _notch_faces(body, faces), "das vollständige Band hat keinen fransigen Rand"

    for missing in faces:
        rest = [index for index in faces if index != missing]
        assert _notch_faces(body, rest), f"ohne Dreieck {missing} franst der Rand aus"
        healed = _without_notches(body, [rest])[0]
        assert set(healed) == set(faces), f"Dreieck {missing} kam nicht zurück"


def test_a_notch_of_two_triangles_is_closed_as_a_pair() -> None:
    """Wo kein einzelnes Dreieck reicht, schließt die kleinste eindeutige Menge.

    **Das ist der Fall, den der Mac der CI zeigt** (17.09.2026): Am
    ausgefransten Knoten der Senkung liegen vier freie Dreiecke, und **keines**
    bringt den Rand allein in Ordnung — die erste Fassung der Heilung verlangte
    genau eines und ließ die Kerbe deshalb offen. Ein Kegelsegment besteht aus
    einem koplanaren Paar; fällt eines heraus, fallen beide.
    """
    from app.core.perceive.features import _notch_faces, _without_notches

    body = trimesh.creation.revolve([(3.0, 0.0), (6.0, 3.0)], sections=48)
    faces = list(range(len(body.faces)))
    # (0, 2) ist eines der 253 Paare dieses Bandes, bei denen genau **eine**
    # Zweiermenge den Rand schließt. (0, 1) wäre es nicht: dort schließen
    # mehrere, und der Test bliebe auch ohne die Regel grün.
    rest = [index for index in faces if index not in {0, 2}]
    candidates = sorted(_notch_faces(body, rest))
    assert candidates, "ohne die zwei Dreiecke franst der Rand aus"
    assert not [f for f in candidates if not _notch_faces(body, [*rest, f])], (
        "der Fall lebt davon, dass kein einzelnes Dreieck den Rand schließt"
    )
    healed = _without_notches(body, [rest])[0]
    assert set(healed) == set(faces), "die eindeutige Zweiermenge kommt zurück"

    # **Für den mehrdeutigen Zweig gibt es hier keinen Test**, und das ist
    # gemessen: An diesem Band schließen von 435 ausfransenden Paaren 406 mit
    # genau einer Zweiermenge und 29 gar nicht — mehrdeutig ist keines. Ein
    # Test dafür bräuchte einen eigens konstruierten Körper; die Zusage steht
    # in ``_closing_set`` und fiele sonst als Zierat auf, der nichts prüft.


def test_the_vertex_face_index_reads_a_degenerate_mesh_like_trimesh_does() -> None:
    """Ein entartetes Dreieck schickt ``trimesh.vertex_faces`` in eine Schleife je Ecke.

    Gemessen am 21.09.2026: 37 ms bei 10 000 Dreiecken, 20 s bei 300 000,
    sechs Minuten bei 1,3 Millionen — und ein Generatornetz aus TripoSG trägt
    solche Dreiecke. Der gepackte Index sortiert einmal stabil und gibt je
    Ecke dieselbe Menge; die Kandidaten der Kerbenschließung ändern sich nicht.
    """
    from app.core.perceive.features import _candidates_at, _rim_of, _vertex_faces_index

    band = trimesh.creation.revolve([(3.0, 0.0), (6.0, 3.0)], sections=48)
    faces = np.vstack([band.faces, [[0, 0, 1]]])
    body = trimesh.Trimesh(vertices=band.vertices, faces=faces, process=False)
    ranges, own = _vertex_faces_index(body)
    theirs = np.asarray(body.vertex_faces)
    assert len(ranges) == len(body.vertices) + 1 and ranges[-1] == 3 * len(body.faces)
    for vertex in range(len(body.vertices)):
        mine = set(own[ranges[vertex] : ranges[vertex + 1]].tolist())
        assert mine == {int(face) for face in theirs[vertex] if face >= 0}, vertex
    assert own[ranges[0] : ranges[1]].tolist().count(len(band.faces)) == 2, (
        "das entartete Dreieck steht an seiner doppelten Ecke zweimal"
    )

    patch = [index for index in range(len(band.faces)) if index != 5]
    rim = _rim_of(body, patch)
    assert rim is not None and rim.frayed
    found = _candidates_at(body, patch, rim.frayed)
    assert found and 5 in found
    # Die Kandidaten sind dieselben wie über ``trimesh.vertex_faces``:
    inside = np.zeros(len(body.faces), dtype=bool)
    inside[patch] = True
    neighbours = features_module._neighbour_index(body)[0]
    expected = set()
    for node in rim.frayed:
        for face in theirs[node]:
            if face < 0 or inside[face]:
                continue
            beside = neighbours[face]
            beside = beside[beside >= 0]
            if len(beside) and inside[beside].any():
                expected.add(int(face))
    assert found == expected


def test_a_notch_too_large_to_be_one_stays_open() -> None:
    """Was drei Dreiecke braucht, ist ein Loch — und ein Loch wird nicht zugenäht.

    Die Grenze steht als ``NOTCH_AT_MOST``. Ohne sie wäre die Heilung keine
    Heilung mehr, sondern eine Erfindung: Sie würde jede Lücke schließen, die
    sich schließen lässt, auch eine, die jemand gemeint hat.
    """
    from app.core.perceive.features import NOTCH_AT_MOST, _without_notches

    assert NOTCH_AT_MOST == 2, "die Grenze ist eine Entscheidung, keine Zufallszahl"
    body = trimesh.creation.revolve([(3.0, 0.0), (6.0, 3.0)], sections=48)
    faces = list(range(len(body.faces)))
    rest = [index for index in faces if index not in {0, 1, 2, 3, 4, 5}]
    healed = _without_notches(body, [rest])[0]
    assert set(healed) != set(faces), "sechs fehlende Dreiecke sind keine Kerbe"


def _notch_closure_by_recounting(body, patch, candidates):
    """Unabhängiger Sollwert: den gesamten neuen Rand für jede kleine Menge neu zählen."""
    from collections import Counter
    from itertools import combinations

    for count in range(1, features_module.NOTCH_AT_MOST + 1):
        found = []
        for group in combinations(candidates, count):
            edges = Counter()
            for triangle in np.asarray(body.faces)[[*patch, *group]]:
                a, b, c = map(int, triangle)
                for start, end in ((a, b), (b, c), (c, a)):
                    edges[tuple(sorted((start, end)))] += 1
            if any(number > 2 for number in edges.values()):
                continue
            degrees = Counter()
            for edge, number in edges.items():
                if number == 1:
                    degrees.update(edge)
            if not any(number > 2 for number in degrees.values()):
                found.append(group)
        if found:
            return found[0] if len(found) == 1 else None
    return None


def test_more_frayed_nodes_than_two_triangles_can_touch_never_start_the_search(monkeypatch):
    """Zwölf ausgefranste Knoten können zwei Dreiecke nicht erreichen; keine Paarsuche nötig."""
    body = trimesh.creation.revolve([(3.0, 0.0), (6.0, 3.0)], sections=12)
    patch = list(range(0, len(body.faces), 2))
    candidates = tuple(range(1, len(body.faces), 2))
    rim = features_module._rim_of(body, patch)
    assert rim is not None and len(rim.frayed) == 12
    assert _notch_closure_by_recounting(body, patch, candidates) is None

    def unexpected(*_args):
        pytest.fail("an impossible two-triangle closure must not be searched")

    monkeypatch.setattr(features_module, "_edge_codes", unexpected)
    monkeypatch.setattr(features_module, "_closes", unexpected)
    assert features_module._closing_set(body, rim, candidates) is None


def test_exactly_six_frayed_nodes_can_be_closed_by_two_triangles():
    """Die notwendige Schranke lässt ihren Randfall zu: zwei getrennte dreieckige Kerben."""
    corners = np.array(
        [(0, 0, 0), (2, 0, 0), (1, 2, 0), (1, -1, 0), (3, 2, 0), (-1, 2, 0)], dtype=float
    )
    body = trimesh.Trimesh(
        vertices=np.vstack((corners, corners + np.array((10, 0, 0)))),
        faces=[
            (0, 1, 3),
            (1, 2, 4),
            (2, 0, 5),
            (6, 7, 9),
            (7, 8, 10),
            (8, 6, 11),
            (0, 1, 2),
            (6, 7, 8),
        ],
        process=False,
    )
    patch, candidates = list(range(6)), (6, 7)
    rim = features_module._rim_of(body, patch)
    assert rim is not None and len(rim.frayed) == 6
    assert _notch_closure_by_recounting(body, patch, candidates) == candidates
    assert features_module._closing_set(body, rim, candidates) == candidates


def test_small_notches_match_a_complete_independent_boundary_recount():
    """Jede einzelne und doppelte Lücke eines Kegelbands behält die alte Randentscheidung."""
    from itertools import combinations

    body = trimesh.creation.revolve([(3.0, 0.0), (6.0, 3.0)], sections=12)
    checked = 0
    for count in (1, 2):
        for missing in combinations(range(len(body.faces)), count):
            patch = [index for index in range(len(body.faces)) if index not in missing]
            rim = features_module._rim_of(body, patch)
            if rim is None or not rim.frayed:
                continue
            assert len(rim.frayed) <= 6
            assert features_module._closing_set(body, rim, missing) == _notch_closure_by_recounting(
                body, patch, missing
            )
            checked += 1
    assert checked == 276


def _subdivided(mesh: MeshData, depth: int) -> MeshData:
    """Dieselbe Form, nur feiner trianguliert.

    ``trimesh.remesh.subdivide`` setzt neue Ecken auf die Mitten vorhandener
    Kanten. Die Form bleibt damit exakt dieselbe — eine Bohrung behält ihr
    48-Eck —, allein die Zahl der Dreiecke vervierfacht sich je Stufe. Wer
    danach etwas anderes erkennt als vorher, misst das Netz statt des Körpers.
    """
    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    faces = np.asarray(mesh.raw.faces)
    for _ in range(depth):
        vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    return MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=True))


def test_bores_survive_any_triangle_count() -> None:
    """Die Lochplatte behält ihre vier Bohrungen, wie fein sie auch vernetzt ist.

    **Gemessen am 17.09.2026, und es war ein Fehler.** Dieselbe Platte, über
    ``subdivide`` verfeinert, verlor ab 815 104 Dreiecken alle vier Bohrungen:
    Der Baum zeigte sechs Flächen und sonst nichts, und der ganze Bohrungsmantel
    fiel zusätzlich in die ebenen Flächen zurück. Die Ursache war
    :attr:`CylinderFit.spread` — es maß in Facettenbreiten, und eine
    Unterteilung halbiert die Facettenbreite, ohne die Polygonnäherung des
    Kreises anzufassen. Der Zähler blieb stehen, der Nenner halbierte sich, und
    der Wert verdoppelte sich mit jeder Stufe: 0,0138 bei 203 776 Dreiecken,
    0,0277 bei 815 104 — an einer Schranke von 0,02.

    Ein eingelesenes Netz ist so dicht, wie es sein Erzeuger gemacht hat. Diese
    Zahl darf nicht entscheiden, ob eine Bohrung eine ist.

    **Die Reihe hört bei 815 104 Dreiecken auf, und das ist eine Messung.** Die
    nächste Stufe hält ihre vier Bohrungen ebenfalls — 3 260 416 Dreiecke,
    26,7 s, 2,6 GB Spitze —, kostet aber mehr, als ein Test wert ist, der
    neben siebenhundert anderen im selben Prozess läuft. Der Fehler zeigt sich
    eine Stufe früher; dort wird er festgehalten.
    """
    original = plate()
    for depth in range(6):
        mesh = _subdivided(original, depth)
        forget_cache()
        bores = detect_holes(mesh)
        assert len(bores) == 4, (
            f"bei {len(mesh.raw.faces)} Dreiecken kamen {len(bores)} Bohrungen zurück"
        )
        for bore in bores:
            assert bore.params["diameter"] == pytest.approx(5.2, abs=5e-6)


def test_the_spread_of_a_bore_does_not_follow_the_triangle_count() -> None:
    """Die Ursache selbst, Zahl für Zahl: Streuung gegen Netzdichte.

    Der Fleck ist derselbe Bohrungsmantel, die Form ist dieselbe — nur die
    Triangulierung wechselt. Die Streuung darf sich daran nicht messen: Sie
    misst, wie weit die Punkte neben ihrem Kreis liegen, und das ist eine
    Eigenschaft der **Polygonnäherung**, nicht der Dreiecke darauf.

    Gemessen läuft sie in die Sättigung — 0,000 bei 796 Dreiecken, 0,255 ab
    50 944, 0,257 bei 3 260 416. Der Anstieg zu Beginn ist echt: Erst mit
    Ecken auf den Sehnen streuen die Schwerpunkte überhaupt um ihren Kreis.

    **Geprüft wird das Verhältnis, nicht der Abstand**, und das ist Absicht:
    Das alte Maß verdoppelte sich je Stufe, exakt und ohne Ausnahme. Ein
    Faktor nahe eins schließt es aus; eine Differenz unter einer festen
    Schranke ließe es bei kleinen Werten noch durch.
    """
    original = plate()
    values = []
    for depth in range(6):
        mesh = _subdivided(original, depth)
        forget_cache()
        found = detect_holes(mesh)
        assert len(found) == 4
        patch = list(found[0].face_indices)
        fit = fit_cylinder(mesh.raw, patch)
        assert fit is not None and fit.good
        values.append(fit.spread)
    assert max(values) < 0.5, f"die Streuung läuft davon: {values}"
    assert values[-1] / values[-2] < 1.2, f"sie folgt noch der Dreieckszahl: {values}"


def test_a_coarsely_facetted_bore_survives_a_dense_triangulation() -> None:
    """Der Maßstab ist die Sehnenhöhe **dieses** Netzes, nicht eine feste Länge.

    Die Gegenprobe zur Grenze nach unten: Wer die Streuung schlicht in
    Millimetern misst, bekommt für ein grob facettiertes Loch eine große Zahl,
    ohne dass etwas daran falsch wäre — die Abweichung *ist* dort groß, weil
    das Vieleck grob ist. Gemessen an einem Loch Ø 40 mit sechzehn Facetten
    (17.09.2026): Sehnenhöhe 0,384 mm, Streuung 0,096 mm. In Sehnenhöhen sind
    das 0,25, in Zehntelmillimetern 9,6 — und an einer Schranke von 2,0 wäre
    die Bohrung weg.

    Sechzehn, vierundzwanzig und achtundvierzig Facetten, jede zweimal
    unterteilt: Die Streuung liegt bei allen neun Läufen zwischen 0,000 und
    0,251. Die Facettenzahl geht sie nichts an.
    """
    for sections in (16, 24, 48):
        block = trimesh.creation.box(extents=(90.0, 90.0, 12.0))
        bore = trimesh.creation.cylinder(radius=20.0, height=40.0, sections=sections)
        original = MeshData.of(block.difference(bore))
        for depth in range(3):
            mesh = _subdivided(original, depth)
            forget_cache()
            found = detect_holes(mesh)
            assert len(found) == 1, (
                f"{sections} Facetten, {len(mesh.raw.faces)} Dreiecke: {len(found)} Bohrungen"
            )
            fit = fit_cylinder(mesh.raw, list(found[0].face_indices))
            assert fit is not None and fit.spread < 0.5, (
                f"{sections} Facetten, {len(mesh.raw.faces)} Dreiecke: {fit}"
            )


# --- kleine echte Flächen (P1.5) --------------------------------------------------------


def _stud_on_a_plate() -> trimesh.Trimesh:
    """Ein 1-mm-Nocken auf einer Platte 40 × 30 × 4 — als Netz, ohne exakten Kern.

    Beide Quader überlappen in genau 1 mm³, damit der Bau nicht an einer bloßen
    Berührung zweier Deckflächen hängt (Review P1.5). Volumen 4801, Oberfläche
    2964, fünf Nockenflächen zu je 1 mm².
    """
    base = trimesh.creation.box(extents=(40.0, 30.0, 4.0))
    base.apply_translation((0.0, 0.0, 2.0))
    post = trimesh.creation.box(extents=(1.0, 1.0, 2.0))
    post.apply_translation((0.0, 0.0, 4.0))
    return trimesh.boolean.union([base, post])


def _small_faces(found: dict[FeatureId, Feature]) -> dict[tuple[float, float, float], Feature]:
    return {
        tuple(round(float(value), 3) for value in entry.params["centre"]): entry  # type: ignore[misc]
        for entry in found.values()
        if entry.kind == "face" and float(entry.params["area"]) < features_module.MIN_FACE_AREA
    }


STUD_CENTRES = {
    (0.0, 0.0, 5.0),
    (0.5, 0.0, 4.5),
    (-0.5, 0.0, 4.5),
    (0.0, 0.5, 4.5),
    (0.0, -0.5, 4.5),
}


@pytest.mark.parametrize("subdivided", [False, True], ids=["roh", "unterteilt"])
def test_a_one_millimetre_stud_keeps_its_five_faces(subdivided: bool) -> None:
    """Fünf Flächen zu je 1 mm² liegen unter ``MIN_FACE_AREA`` — und sind Flächen.

    Der exakte Kern nennt sie, das Netz nannte keine (P1.5, Gegenfall 3). Was
    sie trägt, ist nicht die Größe, sondern der Rand: An allen Seiten stößt
    der Nocken mit rechten Winkeln an Flächen, die nicht zu ihm gehören. Eine
    Unterteilung derselben Dreiecke ändert daran nichts — weder entsteht eine
    Fläche mehr, noch fällt eine weg.
    """
    raw = _stud_on_a_plate()
    if subdivided:
        raw = trimesh.Trimesh(*trimesh.remesh.subdivide(raw.vertices, raw.faces))
    body = MeshData.of(raw)
    assert body.volume == pytest.approx(4801.0) and body.area == pytest.approx(2964.0)

    found = detect(body)
    faces = [entry for entry in found.values() if entry.kind == "face"]

    assert len(found) == len(faces) == 11, sorted(entry.kind for entry in found.values())
    small = _small_faces(found)
    assert set(small) == STUD_CENTRES
    for centre, entry in small.items():
        assert float(entry.params["area"]) == pytest.approx(1.0)
        normal = np.asarray(entry.params["normal"], dtype=float)
        expected = np.asarray(centre) - np.asarray((0.0, 0.0, 4.5 if centre[2] < 5.0 else 4.0))
        assert np.allclose(normal, expected / np.linalg.norm(expected), atol=1e-9)
        assert len(entry.face_indices) == (8 if subdivided else 2)
        assert body.raw.area_faces[list(entry.face_indices)].sum() == pytest.approx(1.0)
    largest = max(faces, key=lambda entry: float(entry.params["area"]))
    assert float(largest.params["area"]) == pytest.approx(1200.0)
    top = next(entry for entry in faces if abs(float(entry.params["area"]) - 1199.0) < 1e-6)
    assert top.params["centre"][2] == pytest.approx(4.0)


def test_the_stud_faces_keep_their_names_after_a_translation() -> None:
    """Die fünf kleinen Flächen bleiben nach einer Verschiebung dieselben Merkmale.

    Die Zuordnung (``matching.match``) findet sie über die mitbewegten alten
    Merkmale wieder — eine Fläche, die die Erkennung findet, aber die
    Zuordnung verliert, wäre nur halb angeschlossen (P1.5, Gegenfall 1:
    „lokale Wiedererkennung und dieselbe benannte Auswahl").
    """
    from app.core.perceive.matching import match, moved_features

    body = _stud_on_a_plate()
    mesh = MeshData.of(body)
    before = detect(mesh)
    small_before = _small_faces(before)
    assert set(small_before) == STUD_CENTRES

    matrix = np.eye(4)
    matrix[:3, 3] = (3.0, -2.0, 0.0)
    moved = body.copy()
    moved.apply_transform(matrix)
    moved_mesh = MeshData.of(moved)
    after = detect(moved_mesh)
    carried = moved_features(dict(before), matrix)
    result = match(carried, after, moved_mesh.bounds.centre, moved_mesh.bounds.diagonal)

    assert result.settled, result
    assert not result.orphaned and not result.ambiguous
    for centre, feature in small_before.items():
        successor = after[result.mapping[feature.id]]
        expected = tuple(round(float(v), 3) for v in np.add(centre, (3.0, -2.0, 0.0)))
        assert tuple(round(float(v), 3) for v in successor.params["centre"]) == expected
        assert float(successor.params["area"]) == pytest.approx(1.0)


def test_the_stud_is_read_the_same_from_the_exact_body_and_its_tessellation() -> None:
    """Dieselben elf Flächen aus ``features_of`` und aus ``detect`` an zwei Abweichungen."""
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep import edit
    from app.core.brep.features import features_of

    body = edit.boolean(
        "union", [edit.box(40.0, 30.0, 4.0), edit.moved(edit.box(1.0, 1.0, 2.0), (0.0, 0.0, 3.0))]
    )
    native = features_of(body)
    assert set(_small_faces(native)) == STUD_CENTRES and len(native) == 11
    for deflection in (0.1, 0.02):
        found = detect(body.to_mesh(deflection=deflection))
        assert len(found) == 11 and set(_small_faces(found)) == STUD_CENTRES, deflection


def test_a_small_facet_needs_sharp_borders_all_around_to_count() -> None:
    """Der Beleg ist der Rand: Eine kleine Fläche zwischen zwei Rundungsstufen zählt nicht.

    Ein 24-seitiger Zylinder Ø 6 hat Mantelstreifen von 0,78 mm × 10 mm — klein,
    eben, und an beiden Längsrändern nur um 15 Grad geknickt. Die Kugel und der
    Mantel bleiben, was sie waren; der Nocken gewinnt nur, weil ihn rechte
    Winkel begrenzen.
    """
    stub = trimesh.creation.cylinder(radius=3.0, height=10.0, sections=24)
    plate = trimesh.creation.box(extents=(40.0, 30.0, 4.0))
    plate.apply_translation((0.0, 0.0, -7.0))
    body = MeshData.of(trimesh.boolean.union([plate, stub]))

    found = detect(body)

    assert not _small_faces(found), "Mantelstreifen sind keine Flächen"
    assert sorted(entry.kind for entry in found.values()).count("pin") == 1
    sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=5.0))
    assert not [entry for entry in detect(sphere).values() if entry.kind == "face"]


# --- die Mündungsfase eines Langlochs (P1.5) --------------------------------------------


def _exact_slot_with_a_mouth_chamfer() -> Any:
    """Platte 60 × 30 × 8, Langloch Ø 6 × 26 durch, oben eine 1-mm-Fase am Ring (Review P1.5).

    Sollwerte: abgezogen 980 + 226π/3, Material 13420 − 226π/3; die zwei
    Halbkegel zusammen 7π√2, die zwei schrägen Flanken zusammen 40√2.
    """
    from app.core.brep import edit

    plate = edit.box(60.0, 30.0, 8.0)
    slotted = edit.slot_bore(
        plate,
        position=(0.0, 0.0, 4.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=8.0,
        length=26.0,
        angle_deg=0.0,
        overlap=0.0,
    )
    rim = [
        entry
        for entry in edit.edges_of(slotted)
        if abs(entry.middle[2] - 8.0) <= EPS_GEOM
        and abs(entry.middle[0]) < 20.0
        and abs(entry.middle[1]) < 10.0
    ]
    assert len(rim) == 4, "der innere Ring oben: zwei Geraden, zwei Halbkreise"
    return edit.chamfer(slotted, 1.0, "named", [edit.edge_key(entry) for entry in rim])


def _mouth_chamfer_checked(found: dict[FeatureId, Feature], mesh: MeshData, tag: str) -> None:
    kinds = sorted(entry.kind for entry in found.values())
    assert kinds == ["face"] * 6 + ["slot"], (tag, kinds)
    slot = next(entry for entry in found.values() if entry.kind == "slot")
    assert slot.params["diameter"] == pytest.approx(6.0, abs=1e-9)
    assert slot.params["length"] == pytest.approx(26.0, abs=1e-9)
    assert slot.params["travel"] == pytest.approx(20.0, abs=1e-9)
    assert slot.params["depth"] == pytest.approx(7.0, abs=1e-9), "die Wandtiefe bleibt ohne Fase"
    assert slot.params["through"] is True
    by_kind: dict[str, list[SurfacePatch]] = {}
    for patch in slot.surface_patches:
        by_kind.setdefault(patch.kind, []).append(patch)
    assert {kind: len(parts) for kind, parts in by_kind.items()} == {
        "cylinder": 2,
        "plane": 4,
        "cone": 2,
    }, tag
    areas = mesh.raw.area_faces
    apices = sorted(tuple(round(float(v), 6) for v in p.params["apex"]) for p in by_kind["cone"])
    assert apices == [(-10.0, 0.0, 4.0), (10.0, 0.0, 4.0)], (tag, apices)
    for cone in by_kind["cone"]:
        assert float(cone.params["half_angle"]) == pytest.approx(math.pi / 4.0, abs=1e-6)
        assert np.allclose(np.abs(np.asarray(cone.params["axis"], dtype=float)), (0, 0, 1))
    tilted = [
        p
        for p in by_kind["plane"]
        if abs(abs(float(np.asarray(p.params["axis"])[2])) - math.sqrt(0.5)) < 1e-6
    ]
    assert len(tilted) == 2, (tag, [p.params["axis"] for p in by_kind["plane"]])
    for flank in tilted:
        assert areas[list(flank.face_indices)].sum() == pytest.approx(20.0 * math.sqrt(2.0))
    covered = {index for patch in slot.surface_patches for index in patch.face_indices}
    assert covered <= set(slot.face_indices)
    normals = np.asarray(mesh.raw.face_normals)[list(slot.face_indices)]
    assert not np.any(np.abs(normals[:, 2]) > 0.99), "kein Deckel im Langloch"


def test_the_mouth_chamfer_of_a_slot_belongs_to_it_on_both_cores() -> None:
    """Zwei Halbkegel und zwei schräge Flanken: an beiden Kernen dieselbe Zugehörigkeit.

    Nativ standen die Kegel als ``cone`` mit ``partial`` neben dem Langloch
    und die Flanken als Flächen — drei Merkmale ohne Körperhandlung; am Netz
    fehlten die Flanken ganz. Die Träger bleiben mit ihren wirklichen Spitzen
    und Normalen erhalten, die Maße des Langlochs bleiben die Nennmaße.
    """
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep.features import features_of

    body = _exact_slot_with_a_mouth_chamfer()
    assert body.volume == pytest.approx(13420.0 - 226.0 * math.pi / 3.0, rel=1e-9)
    native = features_of(body)
    _mouth_chamfer_checked(native, body.mesh, "nativ")
    for deflection in (0.05, 0.01):
        _mouth_chamfer_checked(
            detect(body.to_mesh(deflection=deflection)), body.to_mesh(deflection=deflection), "netz"
        )


def _cone_between_two_slots() -> Any:
    """Platte 60 × 30 × 8, zwei Langlöcher Ø 6 × 26 bei y = ±4, dazwischen eine Senkung Ø 12 → 6.

    Die Senkung sitzt am Ursprung und geht von z = 8 drei Millimeter tief; ihr
    Mantel wird von beiden inneren Langlochflanken (y = ±1) beschnitten und
    berührt so beide Langlöcher mit gleich vielen Kanten.
    """
    from app.core.brep import edit

    body = edit.box(60.0, 30.0, 8.0)
    for y in (-4.0, 4.0):
        body = edit.slot_bore(
            body,
            position=(0.0, y, 4.0),
            direction=(0.0, 0.0, 1.0),
            diameter=6.0,
            depth=8.0,
            length=26.0,
            angle_deg=0.0,
            overlap=0.0,
        )
    sink = edit.moved(edit.cone(6.0, 14.0, 4.0), (0.0, 0.0, 5.0))
    return edit.boolean("difference", [body, sink])


def _one_partial_cone_and_two_slots(
    found: dict[FeatureId, Feature], label: str, *, bare: bool
) -> None:
    """Genau ein Kegel, als Kegelfläche, und zwei Langlöcher — ``bare``: ohne Kegelträger.

    Am Netz ist der Kegelmantel **ein** Fleck (``_merged_cones`` führt ihn
    über die Spitze zusammen), und die Langlöcher bekommen nichts davon. Der
    exakte Kern trägt die Naht des Kegels bei +x: Der Streifen dort ist zwei
    Flächen, die je nur ein Langloch berühren und als Mündungsfase darin
    aufgehen — seine Langlöcher tragen deshalb je einen Kegelträger.
    """
    cones = [entry for entry in found.values() if entry.kind == "cone"]
    assert len(cones) == 1 and cones[0].params.get("partial") is True, (
        f"{label}: {[(entry.kind, entry.params.get('partial')) for entry in found.values()]}"
    )
    slots = [entry for entry in found.values() if entry.kind == "slot"]
    assert len(slots) == 2, label
    for slot in slots:
        assert set(slot.face_indices).isdisjoint(cones[0].face_indices), label
        if bare:
            assert not [patch for patch in slot.surface_patches if patch.kind == "cone"], (
                f"{label}: das Langloch {slot.id} hat den Kegel verschluckt"
            )


def test_a_partial_cone_between_two_slots_stays_where_it_is() -> None:
    """Berührt ein Kegelstück zwei Langlöcher gleich stark, hat niemand belegt, wem es gehört.

    Am Netz teilt die Senkung mit beiden Langlöchern acht Kanten; bis zum
    21.09.2026 entschied dann der alphabetisch spätere Name, und der Kegel
    verschwand im zweiten Langloch — der exakte Kern ließ ihn als Kegelfläche
    stehen. Beide Kerne sagen jetzt dasselbe, an zwei Abweichungen des Netzes.
    """
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep.features import features_of

    body = _cone_between_two_slots()
    _one_partial_cone_and_two_slots(features_of(body), "exakt", bare=False)
    for deflection in (0.1, 0.02):
        forget_cache()
        _one_partial_cone_and_two_slots(
            detect(body.to_mesh(deflection=deflection)), f"Netz {deflection}", bare=True
        )


def test_a_partial_cone_with_one_clear_owner_still_folds_into_that_slot() -> None:
    """Die Gegenprobe zur Gleichstandsregel: ein klarer Sieger nimmt das Stück weiter mit.

    Dieselbe Platte, aber die Senkung um 1 mm zum oberen Langloch gerückt —
    dort teilt der Kegel mehr Kanten mit ``slot_2`` als mit ``slot_1`` und
    geht als Mündungsfase darin auf, wie an einem Langloch allein.
    """
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep import edit

    body = edit.box(60.0, 30.0, 8.0)
    for y in (-4.0, 4.0):
        body = edit.slot_bore(
            body,
            position=(0.0, y, 4.0),
            direction=(0.0, 0.0, 1.0),
            diameter=6.0,
            depth=8.0,
            length=26.0,
            angle_deg=0.0,
            overlap=0.0,
        )
    sink = edit.moved(edit.cone(6.0, 14.0, 4.0), (0.0, 1.0, 5.0))
    body = edit.boolean("difference", [body, sink])
    forget_cache()
    found = detect(body.to_mesh(deflection=0.1))
    assert not [entry for entry in found.values() if entry.kind == "cone"], (
        f"{[(entry.kind, entry.params.get('partial')) for entry in found.values()]}"
    )
    slots = {entry.id: entry for entry in found.values() if entry.kind == "slot"}
    assert len(slots) == 2
    carriers = {
        name: [patch.kind for patch in slot.surface_patches if patch.kind == "cone"]
        for name, slot in slots.items()
    }
    assert sum(1 for kinds in carriers.values() if kinds) == 1, carriers


def _slab_with_a_top(amplitude: float = 0.0, bend: float = 0.0, seed: int = 7) -> MeshData:
    """Ein geschlossener Block 60 × 60 × 6 mit fein unterteilten Tafeln oben und unten.

    ``amplitude`` legt Rauschen auf die Höhe beider Tafeln, wie ein erzeugtes
    Netz eine ebene Partie trägt; ``bend`` wölbt die obere sanft, wie eine
    konstruierte Fläche mit großem Radius.
    """
    rng = np.random.default_rng(seed)
    count = 60
    steps = np.linspace(-30.0, 30.0, count + 1)
    grid = np.array([(x, y) for y in steps for x in steps])
    heights = 6.0 + amplitude * (rng.random(len(grid)) - 0.5) - bend * (grid**2).sum(axis=1)
    top = np.column_stack([grid, heights])
    bottom = np.column_stack([grid, amplitude * (rng.random(len(grid)) - 0.5)])
    faces = []
    for row in range(count):
        for column in range(count):
            a = row * (count + 1) + column
            b, c, d = a + 1, a + count + 1, a + count + 2
            faces += [(a, b, d), (a, d, c)]
    shift = len(grid)
    faces += [(shift + a, shift + c, shift + b) for a, b, c in faces[: 2 * count * count]]
    ring = (
        list(range(count))
        + [column * (count + 1) + count for column in range(count)]
        + [(count + 1) * (count + 1) - 1 - column for column in range(count)]
        + [(count - column) * (count + 1) for column in range(count)]
    )
    for here, there in zip(ring, ring[1:] + ring[:1], strict=True):
        faces += [(here, shift + there, there), (here, shift + here, shift + there)]
    body = trimesh.Trimesh(np.vstack([top, bottom]), faces, process=False)
    trimesh.repair.fix_normals(body)
    assert body.is_watertight and body.is_winding_consistent
    return MeshData.of(body)


@pytest.mark.parametrize(
    ("amplitude", "bend", "rough"),
    [(0.004, 0.0, True), (0.0005, 0.0, False), (0.0, 1 / 800.0, False), (0.0, 0.0, False)],
    ids=["verrauscht", "float-fein", "sanft-gekrümmt", "eben"],
)
def test_only_noise_makes_a_rough_tafel(amplitude: float, bend: float, rough: bool) -> None:
    """Rau ist Rauschen, nicht Krümmung und nicht die letzte Stelle (RM-235).

    Ein erzeugtes Netz trägt ebene Partien als Tafel, deren Knicke in beide
    Richtungen gehen; eine sanft gekrümmte konstruierte Fläche biegt sich in
    eine, und fast ebene CAD-Flächen knicken unter einem Zehntelgrad. Nur die
    erste Tafel ist rau — die anderen zwei scheitern an derselben
    Ebenheitsprüfung und dürfen trotzdem nicht zur Haut zählen.
    """
    body = _slab_with_a_top(amplitude, bend).raw
    planar = features_module._large_facet_faces(body)
    tafeln = float(body.area_faces[np.abs(body.face_normals[:, 2]) > 0.9].sum())
    share = features_module._rough_facet_area(body, planar)
    if rough:
        assert share == pytest.approx(tafeln, rel=0.01), (share, tafeln)
    else:
        assert share == 0.0


def test_rough_tafeln_make_a_body_skin_on_their_own() -> None:
    """Raue Tafeln machen den Körper zur Haut, auch wo die Splitter es nicht tun.

    Am erzeugten Puppenhausbett lagen 57 Prozent der Oberfläche in
    verrauschten Tafeln und 34 Prozent in Splittern; die Splitterregel sah
    nur die zweiten, und 96 893 Splitter wurden eingepasst (25.09.2026). Hier:
    der Scan-Körper der Tests neben einem Block, dessen Deckfläche
    verrauscht beziehungsweise sanft gewölbt ist. Nur die verrauschte zählt.
    """
    blob = _scan_like_blob().raw
    for amplitude, bend, skin in ((0.004, 0.0, True), (0.0, 1 / 800.0, False)):
        slab = _slab_with_a_top(amplitude, bend).raw
        joined = MeshData.of(trimesh.util.concatenate([blob, slab]))
        rough = features_module._rough_facet_area(
            joined.raw, features_module._large_facet_faces(joined.raw)
        )
        assert (rough >= features_module.FREEFORM_ROUGH_SHARE * float(joined.raw.area)) is skin
        forget_cache()
        assert features_module._fitted(joined).freeform_skin is skin, (amplitude, bend)


def test_the_facet_verdict_and_the_patches_stop_between_their_steps() -> None:
    """Facettenurteil, Flecken und Krümmungssprünge prüfen den Abbruch unterwegs.

    Am Drachen mit 2,3 Millionen Dreiecken lagen sie bis zu 9,6 s ohne
    Prüfung hintereinander, und so lange wartete *Abbrechen* (§15.6,
    25.09.2026). Jeder Rumpf fragt jetzt zwischen seinen Schritten; ein
    Abbruch in der Mitte kommt beim Aufrufer an.
    """
    from app.core.errors import OperationCancelled

    body = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=64)
    faces = list(range(len(body.faces)))
    runs = {
        "Facettenurteil": lambda check: features_module._facet_verdicts_read(body, check),
        "Flecken": lambda check: features_module._connected_patches_read(body, faces, check),
        "Krümmungssprünge": lambda check: features_module._curvature_jumps(body, check),
    }
    for name, run in runs.items():
        counted: list[int] = []
        run(lambda counted=counted: counted.append(1))
        assert len(counted) >= 2, (name, len(counted))

        def cancel_on_the_second(seen: list[int] = []) -> None:  # noqa: B006
            seen.append(1)
            if len(seen) == 2:
                raise OperationCancelled

        with pytest.raises(OperationCancelled):
            run(cancel_on_the_second)


def _refined(mesh: MeshData, edge: float) -> MeshData:
    """*Kanten verfeinern* ohne Herkunftsvermerk — so, wie ein Folgeschritt das Netz sieht."""
    from app.core.geom.mesh_ops import remesh

    refined = remesh(mesh, edge)
    return MeshData.of(
        trimesh.Trimesh(
            np.asarray(refined.raw.vertices), np.asarray(refined.raw.faces), process=False
        )
    )


@pytest.mark.parametrize("name", ["block_with_rounded_edge.stl", "post_with_fillet.stl"])
def test_a_refined_mesh_is_recognised_like_its_original(name: str) -> None:
    """Fein geteilt erkennt die Erkennung dasselbe wie am Original (ERKENNUNG-04).

    *Kanten verfeinern* ändert die Form nicht, nur die Zahl der Dreiecke — und
    die Ebenenregel zählte Dreiecke: Jeder Streifen einer Verrundung trug
    danach acht und mehr koplanare Dreiecke und galt als Ebene. Aus dem Quader
    mit gerundeter Kante wurden 30 Flächen ohne Verrundung, aus der Säule mit
    Kehle 102 Flächen ohne Zapfen (Durchsicht 0.5.1). Gezählt wird jetzt
    höchstens je Umrissecke; ein Streifen hat vier.
    """
    mesh = plate(name)
    forget_cache()
    before = detect(mesh)
    forget_cache()
    after = detect(_refined(mesh, 1.0))
    forget_cache()

    def summary(found: dict[FeatureId, Feature]) -> list[tuple[str, float]]:
        return sorted(
            (feature.kind, round(float(feature.params.get("radius") or 0.0), 2))
            for feature in found.values()
        )

    assert summary(after) == summary(before)


def test_a_strip_below_the_resolution_keeps_its_triangle_count() -> None:
    """Ein Splitter unter der Erkennungsauflösung bleibt nach Dreiecken gezählt (ERKENNUNG-04).

    Ein gezogener Umriss mit einer Rundung R 3 und einer R 0,1, fein geteilt:
    Die Streifen der R 3 sind 0,2 mm breit, knicken um 3,75 Grad und liegen auf
    3 mm — sie zählen nach ihren vier Ecken und gehören zur Rundung. Die der
    R 0,1 sind 0,026 mm breit und liegen auf 0,1 mm, unter
    :data:`MIN_CYLINDER_DIAMETER`: Wie die Kantenstreifen eines Boolesch
    gebauten Körpers bleiben sie bei ihren Dreiecken und aus der Rundformsuche
    heraus.
    """
    from shapely.geometry import Polygon

    from app.core.perceive.features import (
        MIN_FLAT_FACES,
        _curved_faces,
        _facet_areas,
        _facet_table,
        _flat_counts,
        _one_body,
    )

    def arc(x: float, y: float, radius: float, start: float, count: int) -> list[tuple]:
        return [
            (
                x + radius * math.cos(start + math.pi / 2 * step / count),
                y + radius * math.sin(start + math.pi / 2 * step / count),
            )
            for step in range(count + 1)
        ]

    outline = [(0.0, 0.0), (30.0, 0.0), *arc(27.0, 17.0, 3.0, 0.0, 24)]
    outline += arc(0.1, 19.9, 0.1, math.pi / 2, 6)
    body = _one_body(
        _refined(MeshData.of(trimesh.creation.extrude_polygon(Polygon(outline), 10.0)), 1.0)
    ).raw
    facets = list(body.facets)
    members, owner, sizes, _touches = _facet_table(facets, len(body.faces), _curved_faces(body))
    counted = _flat_counts(body, facets, members, owner, sizes)
    areas = np.asarray(_facet_areas(body, facets))
    widths = []
    for number, facet in enumerate(facets):
        corners = np.asarray(body.vertices)[np.asarray(body.faces)[facet].ravel()]
        widths.append(
            areas[number] / float(np.linalg.norm(corners.max(axis=0) - corners.min(axis=0)))
        )
    rounding = [number for number, width in enumerate(widths) if 0.15 < width < 0.25]
    splinters = [number for number, width in enumerate(widths) if width < 0.05]
    assert len(rounding) == 24 and len(splinters) == 6
    assert all(sizes[number] >= MIN_FLAT_FACES for number in (*rounding, *splinters))
    assert all(counted[number] == 4 for number in rounding)
    assert all(counted[number] == sizes[number] for number in splinters)


def _turned_bore(entry: list[list[float]]) -> MeshData:
    """Ein gedrehter Ring Ø 24 × 10 mit Bohrung Ø 6; ``entry`` ist der Weg der Mündung.

    Die Punkte laufen von der Bohrungswand (Radius 3) zur Deckfläche (z = 10);
    48 Segmente, wie ein fein vernetzter Mantel (7,5 Grad je Teilung).
    """
    profile = [[12.0, 0.0], [12.0, 10.0], *reversed(entry), [3.0, 0.0], [12.0, 0.0]]
    return MeshData.of(trimesh.creation.revolve(profile, sections=48))


def test_a_bore_with_a_steep_lead_in_is_a_bore_and_a_cone() -> None:
    """Eine Mündung, die unter der Knickgrenze abknickt, ist Bohrung und Kegel (ERKENNUNG-11).

    Ein Einführkegel mit 20 Grad Halbwinkel steht um 20 Grad gegen die
    Bohrungswand — unter :data:`CURVATURE_LIMIT`, also lagen Wand und Kegel in
    einem Fleck, auf den keine Form passte, und die Bohrung fehlte. Dieselbe
    Lage wie die Haltelippe einer Magnettasche. Die fünfte Runde teilt an der
    Naht, die ringsum gleich und doppelt so scharf knickt wie die Teilung des
    Mantels.
    """
    lead = 1.5
    entry = [[3.0, 10.0 - lead], [3.0 + lead * math.tan(math.radians(20.0)), 10.0]]
    forget_cache()
    found = detect(_turned_bore(entry))

    holes = [feature for feature in found.values() if feature.kind == "hole"]
    cones = [feature for feature in found.values() if feature.kind == "cone"]
    assert len(holes) == 1 and holes[0].params["diameter"] == pytest.approx(6.0, abs=0.01)
    assert len(cones) == 1 and cones[0].params["angle"] == pytest.approx(40.0, abs=1.0)
    assert not [feature for feature in found.values() if feature.kind == "curved_face"]


def test_a_rounded_mouth_is_no_seam() -> None:
    """Eine grob geteilte Rundung knickt an jeder Reihe gleich — das ist keine Naht (ERKENNUNG-11).

    Vier Reihen über neunzig Grad knicken je 22,5 Grad, so scharf wie die Naht
    einer Lippe. Getrennt wird trotzdem nicht: Jede Reihe knickt auch gegen
    ihre Nachbarreihe so, und eine Naht muss doppelt so scharf sein wie jeder
    andere weiche Knick ihrer Dreiecke. Die Erkennung ist mit und ohne die
    fünfte Runde dieselbe.
    """
    radius = 1.5
    turns = [math.radians(22.5 * step) for step in range(5)]
    entry = [
        [3.0 + radius - radius * math.cos(angle), 10.0 - radius + radius * math.sin(angle)]
        for angle in turns
    ]
    mesh = _turned_bore(entry)
    forget_cache()
    with_seams = detect(mesh)
    forget_cache()
    original = features_module._pieces_at_a_seam
    try:
        features_module._pieces_at_a_seam = lambda *_args, **_kwargs: []
        without_seams = detect(mesh)
    finally:
        features_module._pieces_at_a_seam = original
    forget_cache()
    assert with_seams == without_seams


def test_the_recognition_tells_how_far_it_is() -> None:
    """Die Vollerkennung meldet ihren erledigten Anteil, nur wachsend, bis eins (KUNDE-14).

    Sie meldete nur ihren Text, und beim Laden des Piratenschiffs stand der
    Balken 48 Sekunden auf „Merkmale erkennen · 0 %“, während allein die Uhr
    lief (Durchsicht 0.5.1). Jetzt zählt sie erledigte Etappen, Flecken und
    Stücke — hier an der Säule mit Kehle, deren Mantel die Nachtrennung in
    rund hundert Stücke zerlegt. Der Anteil ändert die Erkennung nicht, und
    eine Antwort aus dem Merker meldet nichts.
    """
    from itertools import pairwise

    from app.core.perceive.features import SHARE_STEP

    forget_cache()
    body = normalise(read_mesh((MESHES / "post_with_fillet.stl").read_bytes(), ".stl"), "mm").mesh
    told: list[float] = []
    found = detect(body, progress=told.append)

    assert told[0] < 0.05, told[:3]
    assert told[-1] == 1.0
    assert all(later > earlier for earlier, later in pairwise(told)), "nur wachsend"
    assert all(later - earlier >= SHARE_STEP * 0.999 for earlier, later in pairwise(told[:-1]))
    # Nicht nur die Etappen, auch die Einpassung dazwischen: Der Balken wandert
    # mit jedem Stück und steht nicht, bis die Runde fertig ist.
    assert len(told) > 50, len(told)

    forget_cache()
    assert detect(body) == found, "der Anteil ändert die Erkennung nicht"
    again: list[float] = []
    detect(body, progress=again.append)
    assert again == [], "eine Antwort aus dem Merker meldet nichts"


def test_a_small_patch_is_grouped_like_a_large_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein kleiner Fleck wird sortiert gruppiert, und es kommen dieselben Flecken heraus.

    ``_connected_patches_read`` legte je Aufruf zwei Masken über alle
    Dreiecke und Nähte und einen Graphen über alle Dreiecke an —
    :func:`_cylinder_beside_a_torus` ruft sie je Stück, am Meshy-Murmelbrett
    3 656-mal für 71 s (Durchsicht 0.5.1, erkennung-05). Der kleine Weg
    nummeriert den Fleck aufsteigend um; Gruppen, ihre Folge und ihre
    Dreiecke müssen dieselben sein wie auf dem großen Weg — hier an zufälligen
    Auswahlen einer fein geteilten Kugel mit Kerben und Inseln erzwungen.
    """
    body = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
    generator = np.random.default_rng(5)
    count = len(body.faces)
    samples = [
        sorted(generator.choice(count, size=size, replace=False).tolist())
        for size in (7, 40, 300, 1500)
    ]
    samples.append(list(range(0, count, 3)))
    for faces in samples:
        monkeypatch.setattr(features_module, "SORTED_CORNERS_SHARE", 0.0)
        large = features_module._connected_patches_read(body, faces)
        monkeypatch.setattr(features_module, "SORTED_CORNERS_SHARE", 1.0)
        small = features_module._connected_patches_read(body, faces)
        assert small == large, len(faces)
    assert any(len(features_module._connected_patches_read(body, faces)) > 1 for faces in samples)


def test_a_refinement_that_turns_a_triangle_is_not_the_same_surface() -> None:
    """Ein umgedrehtes Teildreieck ist eine andere Oberfläche, auch in derselben Ebene.

    ``refined_twin`` belegte je Ursprung die Ebene und den Inhalt, nicht die
    Richtung: Ein Teilstück mit vertauschtem Umlaufsinn liegt in seiner Ebene
    und deckt denselben Inhalt — übertragen wurde trotzdem, und die Merkmale
    trugen danach Innen und Außen eines Dreiecks, das nach der anderen Seite
    zeigt (``inward``, ``inner``, das Tor des einheitlichen Umlaufsinns bei
    den Einschlüssen).
    """
    from app.core.geom.mesh_ops import remesh

    mesh = plate()
    refined = remesh(mesh, 2.0)
    origin = features_module.refined_twin(mesh, refined)
    assert origin is not None, "die echte Teilung trägt ihre Herkunft"
    faces = np.asarray(refined.raw.faces).copy()
    faces[0] = faces[0][[0, 2, 1]]
    turned = MeshData.of(trimesh.Trimesh(np.asarray(refined.raw.vertices), faces, process=False))
    features_module.note_refinement(mesh, turned, origin)

    assert not turned.raw.is_winding_consistent
    assert features_module.refined_twin(mesh, turned) is None


def test_a_refined_open_mesh_counts_its_open_edges_anew() -> None:
    """Die Teilung setzt neue Ecken auf den offenen Rand — die Stelle wird neu gezählt.

    Eine offene Stelle zählt Kanten und mittelt Ecken des Netzes, nicht der
    Oberfläche. Übertragen stand nach *Kanten verfeinern* an einem Kasten
    ohne Deckel weiter „4 offene Kanten“, wo das feinere Netz 32 trägt; die
    frische Erkennung desselben Netzes sagte 32.
    """
    from app.core.geom.mesh_ops import remesh

    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    kept = np.flatnonzero(np.asarray(box.face_normals)[:, 2] < 0.5)
    opened = MeshData.of(
        trimesh.Trimesh(np.asarray(box.vertices), np.asarray(box.faces)[kept], process=False)
    )
    forget_cache()
    before = [f.params["open_edges"] for f in detect(opened).values() if f.kind == "edge_loop"]
    assert before == [4], "der offene Deckel ist eine Stelle mit vier Kanten"
    refined = remesh(opened, 4.0)
    origin = features_module.refined_twin(opened, refined)
    assert origin is not None, "das Verfeinern belegt seine Herkunft"
    features_module.carry_refined_detection(opened, refined, origin)

    loops = [dict(f.params) for f in detect(refined).values() if f.kind == "edge_loop"]
    fresh = [
        dict(f.params)
        for f in features_module.detect_edge_loops(features_module._one_body(refined))
    ]
    assert loops == fresh
    assert fresh[0]["open_edges"] > 4
