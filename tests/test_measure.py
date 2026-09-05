"""Messen an einem Körper mit bekannten Maßen (Bauplan §18.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.geom.measure import (
    Measurement,
    MeasurementList,
    angle_between,
    bounding_box_of,
    distance,
    snap,
    volume_of,
    wall_thickness,
)
from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import normalise

MESHES = Path(__file__).parent / "data" / "meshes"


def cube():
    """20-mm-Würfel, auf den Ursprung zentriert, verschweißt und wasserdicht."""
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


def test_point_to_point_distance() -> None:
    assert distance((0.0, 0.0, 0.0), (3.0, 4.0, 0.0)) == pytest.approx(5.0)
    assert distance((1.0, 1.0, 1.0), (1.0, 1.0, 1.0)) == pytest.approx(0.0)


def test_angles_are_reported_as_the_smaller_one() -> None:
    assert angle_between((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)) == pytest.approx(90.0)
    assert angle_between((1.0, 0.0, 0.0), (1.0, 1.0, 0.0)) == pytest.approx(45.0)
    assert angle_between((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)) == pytest.approx(0.0)
    assert angle_between((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)) == pytest.approx(0.0)


def test_a_click_near_a_corner_snaps_onto_it() -> None:
    """§18.3: Einrasten ist das, was eine Messung reproduzierbar macht."""
    result = snap(cube(), (10.2, 9.8, 10.1))

    assert result.kind == "vertex"
    assert result.point == pytest.approx((10.0, 10.0, 10.0))
    assert result.distance < 0.5


def test_a_click_along_an_edge_snaps_onto_the_edge() -> None:
    result = snap(cube(), (0.0, 10.1, 10.2))

    assert result.kind == "edge"
    assert result.point[1] == pytest.approx(10.0, abs=1e-6)
    assert result.point[2] == pytest.approx(10.0, abs=1e-6)


def test_a_click_far_from_the_body_stays_where_it_is() -> None:
    result = snap(cube(), (100.0, 100.0, 100.0))

    assert result.kind == "free"
    assert result.point == pytest.approx((100.0, 100.0, 100.0))


def test_measuring_the_cube_edge_after_snapping() -> None:
    body = cube()
    first = snap(body, (-9.9, -10.1, -9.8)).point
    second = snap(body, (10.1, -9.9, -10.2)).point

    assert distance(first, second) == pytest.approx(20.0, abs=1e-9), "an edge of the cube"


def test_wall_thickness_of_a_solid_cube() -> None:
    """Von der Mitte einer Fläche gerade hindurch: 20 mm Material."""
    assert wall_thickness(cube(), (0.0, 0.0, 10.0)) == pytest.approx(20.0, abs=1e-3)


def test_wall_thickness_uses_the_face_below_an_off_centre_point() -> None:
    """Eine große Deckfläche darf nicht gegen ihren Schwerpunkt verlieren."""
    import trimesh

    from app.core.geom.mesh import MeshData

    plate = MeshData.of(trimesh.creation.box(extents=(100.0, 100.0, 2.0)))

    assert wall_thickness(plate, (40.0, 0.0, 1.0)) == pytest.approx(2.0, abs=1e-3)


def test_wall_thickness_ignores_a_degenerate_face_on_the_clicked_surface() -> None:
    """Eine Nullfläche besitzt keine Normale und darf die tragende Fläche nicht verdecken."""
    import numpy as np
    import trimesh

    from app.core.geom.mesh import MeshData

    plate = trimesh.creation.box(extents=(100.0, 100.0, 2.0))
    vertices = np.vstack(
        (
            np.asarray(((-50.0, 0.0, 1.0), (50.0, 0.0, 1.0), (50.0, 0.0, 1.0))),
            plate.vertices,
        )
    )
    faces = np.vstack((np.asarray(((0, 1, 2),)), plate.faces + 3))
    with_zero_face = MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))

    assert wall_thickness(with_zero_face, (-30.0, 0.0, 1.0)) == pytest.approx(2.0, abs=1e-3)


def test_wall_thickness_in_a_given_direction() -> None:
    assert wall_thickness(cube(), (0.0, 0.0, -10.0), (0.0, 0.0, 1.0)) == pytest.approx(
        20.0, abs=1e-3
    )


def test_wall_thickness_says_nothing_where_it_cannot_tell() -> None:
    """Ein Strahl, der den Körper verlässt, meldet nichts statt einer
    erfundenen Zahl.
    """
    assert wall_thickness(cube(), (0.0, 0.0, 10.0), (0.0, 0.0, 1.0)) is None


def test_bounds_and_volume_of_a_selection() -> None:
    body = cube()
    box = bounding_box_of([body])

    assert box.size == pytest.approx((20.0, 20.0, 20.0))
    assert box.centre == pytest.approx((0.0, 0.0, 0.0))
    assert volume_of([body]) == pytest.approx(8000.0)
    assert volume_of([body, body]) == pytest.approx(16000.0)


def test_an_empty_selection_has_no_size() -> None:
    box = bounding_box_of([])
    assert box.size == (0.0, 0.0, 0.0)
    assert volume_of([]) == 0.0


def test_dimensions_stay_until_they_are_deleted() -> None:
    """§18.3: dimensions remain until deleted."""
    dimensions = MeasurementList()
    dimensions.add(Measurement(kind="distance", value=20.0004))
    dimensions.add(Measurement(kind="thickness", value=2.4))

    assert len(dimensions) == 2
    assert dimensions.entries[0].shown == pytest.approx(20.0), "shown rounded to EPS_DISPLAY"
    assert dimensions.entries[0].value == pytest.approx(20.0004), "stored unrounded"

    dimensions.remove(0)
    assert len(dimensions) == 1
    dimensions.clear()
    assert len(dimensions) == 0


def test_the_snap_never_catches_a_line_that_is_not_there() -> None:
    """Gefangen wird nur, was man sieht — keine Triangulierungsdiagonale.

    **Der Befund (Robert, 03.09.2026):** „bei messen ist das zielen relativ
    schwer". Eine Ursache lag hier: Gerechnet wurde über *alle*
    Dreieckskanten. Die Deckfläche eines Quaders besteht aus zwei Dreiecken,
    und ihre gemeinsame Diagonale läuft mitten über die Fläche — ein Klick
    darauf hatte Abstand **null** und wurde als „Kante" gemeldet. Der Punkt
    saß auf einer Linie, die es im Bild nicht gibt, die Zahl daneben stimmte,
    und niemand konnte wissen, wovon sie galt.

    Der Punkt hier liegt auf der Diagonalen der Deckfläche
    (``x == y``, ``z == 5``) und weit von jeder echten Kante entfernt.
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    box = MeshData(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    auf_der_diagonalen = (5.0, 5.0, 5.0)

    gefangen = snap(box, auf_der_diagonalen, radius=1.0)

    assert gefangen.kind == "free", f"die Diagonale zweier Dreiecke ist keine Kante: {gefangen}"
    assert gefangen.point == auf_der_diagonalen, "und der Klick bleibt, wo er war"


def test_the_snap_takes_the_corner_the_edge_and_nothing_else() -> None:
    """Die drei Antworten an einer Stelle, nur über die Reichweite getrennt.

    Der Punkt liegt auf der Deckfläche, zwei Millimeter von beiden Randkanten
    und damit 2,83 mm von der Ecke. Er ist derselbe in allen drei Fällen —
    was sich ändert, ist allein die Weite, in der gefangen wird.
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    box = MeshData(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    stelle = (18.0, 18.0, 5.0)

    weit = snap(box, stelle, radius=4.0)
    assert weit.kind == "vertex" and weit.point == (20.0, 20.0, 5.0), f"die Ecke: {weit}"

    mittel = snap(box, stelle, radius=2.5)
    assert mittel.kind == "edge", f"zu weit für die Ecke, nah genug an der Kante: {mittel}"
    assert mittel.point[2] == pytest.approx(5.0), "und sie liegt auf der Deckfläche"

    eng = snap(box, stelle, radius=0.5)
    assert eng.kind == "free" and eng.point == stelle, f"und sonst bleibt er stehen: {eng}"


def test_a_sphere_has_no_corners_to_catch() -> None:
    """Ein rundes Teil hat keine Ecke, also fängt dort nichts.

    Über alle Netzknoten gerechnet lieferte jeder Klick auf eine Kugel einen
    „Eckpunkt" — den nächsten Knoten der Vernetzung. Damit hing die Messung an
    einer Entscheidung des Vernetzers und wanderte, sobald jemand die
    Auflösung änderte.
    """
    import trimesh

    from app.core.geom.measure import corner_points, visible_edges
    from app.core.geom.mesh import MeshData

    kugel = MeshData(trimesh.creation.icosphere(subdivisions=3, radius=20.0))

    assert len(visible_edges(kugel)) == 0, "eine geschlossene Kugel hat keine sichtbare Kante"
    assert len(corner_points(kugel)) == 0, "und erst recht keine Ecke"

    aussen = (20.0, 0.0, 0.0)
    assert snap(kugel, aussen, radius=5.0).kind == "free", "also bleibt jeder Klick stehen"


def test_a_hole_in_the_mesh_keeps_its_rim() -> None:
    """Eine offene Kante ist sichtbar, auch ohne Knick dahinter.

    Sie hängt nur an einem Dreieck; im Bild ist sie der Rand eines Lochs. Wer
    an einem kaputten Netz misst, meint oft genau diesen Rand — er ist der
    Befund, den er ansieht.

    Der Fall ist so gebaut, dass **nur** der offene Zweig ihn löst: Ohne
    Deckel ist keine der vier oberen Umlaufkanten mehr scharf — an jeder hängt
    nur noch die Seitenwand. Wer allein die Knickkanten nimmt, verliert den
    ganzen Lochrand, und die erste Zusicherung unten sagt das auch.
    """
    import numpy as np
    import trimesh

    from app.core.geom.measure import SHARP_EDGE_ANGLE, visible_edges
    from app.core.geom.mesh import MeshData

    roh = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    deckel = [index for index, normal in enumerate(roh.face_normals) if normal[2] > 0.9]
    ohne_deckel = trimesh.Trimesh(
        vertices=roh.vertices, faces=np.delete(roh.faces, deckel, axis=0), process=False
    )
    box = MeshData(ohne_deckel)

    def oben(kanten: object) -> int:
        """Wie viele der Kanten ganz auf der Höhe des fehlenden Deckels liegen."""
        return sum(
            1
            for a, b in kanten  # type: ignore[attr-defined]
            if abs(float(ohne_deckel.vertices[a][2]) - 5.0) < 1e-9
            and abs(float(ohne_deckel.vertices[b][2]) - 5.0) < 1e-9
        )

    winkel = np.asarray(ohne_deckel.face_adjacency_angles, dtype=float)
    nur_scharf = np.asarray(ohne_deckel.face_adjacency_edges)[winkel > SHARP_EDGE_ANGLE]
    assert oben(nur_scharf) == 0, (
        "ohne Deckel ist keine der oberen Kanten mehr ein Knick — sonst prüft "
        "dieser Test den offenen Zweig gar nicht"
    )

    assert oben(visible_edges(box)) >= 4, "der Rand des Lochs zählt trotzdem als sichtbar"
