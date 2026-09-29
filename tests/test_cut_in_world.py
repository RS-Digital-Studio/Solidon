"""Ein Schnitt in freier Richtung legt sein Werkzeug in die Welt, nicht den Körper in dessen Rahmen.

*Bohrung setzen* mit der Normalen einer angeklickten Fläche legte bis zur
Durchsicht 0.5.1 den ganzen Körper in den Rahmen der Bohrung, schnitt dort und
legte ihn zurück; *Bohrung ändern* und *Zum Langloch ziehen* taten dasselbe
(RM-274). Hin- und Rückrechnung runden: Am Gartenschlauchhalter (Ø 3 × 2 mm in
die größte Fläche) standen danach 17 490 Ecken außerhalb des Schnitts nicht mehr
an ihrem Ort, und der Merker über die Körpergrenze rechnete 1 078 statt 79
Fragen neu. Jetzt wandert das Werkzeug in die Welt, und jede Ecke, die der
Schnitt nicht berührt, bleibt Bit für Bit, wo sie war — dieselbe Zusage wie beim
achsparallelen Bohren.

**Die Enden des Werkzeugs gehen mit.** Im Rahmen der Bohrung legte
``_restore_drill_end_planes`` Körperecken im Float64-Rauschen einer Werkzeugebene
genau auf sie. In Weltlage lässt sich eine schräge Ebene nicht genau treffen, und
ein Werkzeug, das bündig in einer schrägen Fläche endet, lässt eine Haut stehen.
Deshalb reicht ein Ende, das in einer Fläche mit Luft dahinter liegt — die
Mündung in der angeklickten Fläche, ein Boden in der Unterseite —, um
``BOOLEAN_OVERLAP`` über sie hinaus. An einer Fläche aus einer STL (float32) ließ
schon der alte Weg die Mündung zu — auch das halten die Fälle hier fest.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.geom import lathe, transform
from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean
from app.core.geom.mesh import MeshData, as_mesh_data, ray_hit_distances
from app.core.geom.prepare import BORE_SECTIONS, drill
from app.core.perceive.features import detect
from app.core.sketch.planes import frame_of
from app.core.types import Profile
from tests.helpers import feature_operation

#: Ab welchem Abstand zur Achse eine Ecke sicher außerhalb jedes Werkzeugs liegt,
#: über dessen größtem Radius (mm) — weit über jeder Rundung, weit unter jedem Maß.
CLEAR = 0.05

#: Die Fälle für *Bohrung setzen* mit freier Richtung, je mit dem größten
#: Abstand ihres Werkzeugs von der Achse: Radius 2, Langloch 12 lang (Mitten
#: der Bögen 4 von der Mitte, dazu der Radius), Aufweitung Ø 8.
DRILLED: dict[str, tuple[dict[str, Any], float]] = {
    "Sackloch": ({"depth": 3.0}, 2.0),
    "durch": ({"depth": 0.0}, 2.0),
    "Langloch": ({"depth": 3.0, "slot_length": 12.0}, 6.0),
    "Aufweitung": ({"depth": 5.0, "widening_diameter": 8.0, "widening_depth": 1.5}, 4.0),
    "Mittenanker": ({"depth": 3.0, "anchor": "centre"}, 2.0),
}


def _turn() -> np.ndarray:
    """Schräg in zwei Achsen, ohne rechten Winkel: erst 23° um x, dann 31° um z."""
    return transform.composed(transform.rotation("z", 31.0), transform.rotation("x", 23.0))


def _tilted_block(*, subdivided: bool = True) -> MeshData:
    """Quader 40 × 30 × 12 mit einer Kugel Ø 10 an einer fernen Ecke, schräg gedreht.

    Unterteilt tragen auch die ebenen Flächen viele Ecken abseits des Lochs. Wer
    vor dem Schnitt die alte Bohrung schließt, legt danach koplanare Dreiecke
    zusammen (``prepare_ops._without_scars``) und vernetzt ebene Flächen neu —
    für diese Wege bleibt der Quader deshalb ungeteilt, und die fernen Ecken
    stehen auf der Kugel.
    """
    block = trimesh.creation.box(extents=(40.0, 30.0, 12.0))
    for _ in range(3 if subdivided else 0):
        block = block.subdivide()
    knob = trimesh.creation.icosphere(subdivisions=3, radius=5.0)
    knob.vertices = np.asarray(knob.vertices) + np.array([-15.0, 10.0, 6.0])
    joined = boolean("union", [MeshData.of(block), MeshData.of(knob)]).mesh
    return transform.apply(joined, _turn())


def _on_top(turn: np.ndarray, x: float = 3.0, y: float = -2.0) -> tuple[np.ndarray, np.ndarray]:
    """Eine Stelle auf der gedrehten Oberseite (z = 6) und deren Normale, beide mitgedreht."""
    normal = transform.turned(np.array([[0.0, 0.0, 1.0]]), turn)[0]
    point = transform.moved_points(np.array([[x, y, 6.0]]), turn)[0]
    return point, normal


def _stl_plate(angle: float = 17.5) -> tuple[MeshData, np.ndarray, np.ndarray]:
    """Platte 60 × 40 × 10, um y gedreht und auf float32 gerundet — wie aus einer STL.

    Die Stelle und die Normale sind die der ungerundeten Fläche; die Ecken der
    Platte liegen um die float32-Rundung daneben, so wie die Nachbardreiecke
    eines angeklickten Dreiecks einer eingelesenen schrägen Fläche.
    """
    turn = transform.rotation("y", angle)
    raw = transform.apply(MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0))), turn).raw
    rounded = raw.copy()
    rounded.vertices = np.asarray(raw.vertices, dtype=np.float32).astype(np.float64)
    normal = transform.turned(np.array([[0.0, 0.0, 1.0]]), turn)[0]
    point = transform.moved_points(np.array([[5.0, 3.0, 5.0]]), turn)[0]
    return MeshData.of(rounded), point, normal


def _rows(points: np.ndarray) -> np.ndarray:
    """Jede Ecke als ein Wert — gleich heißt Bit für Bit gleich."""
    return np.ascontiguousarray(points, dtype=np.float64).view([("", np.float64)] * 3).ravel()


def _off_axis(points: np.ndarray, point: np.ndarray, normal: np.ndarray) -> np.ndarray:
    offset = np.asarray(points, dtype=np.float64) - point
    along = offset @ normal
    return np.linalg.norm(offset - np.outer(along, normal), axis=1)


def _moved_outside(
    before: MeshData, after: MeshData, point: Any, normal: Any, reach: float
) -> tuple[int, int]:
    """Ecken außerhalb des Zylinders um die Achse: wie viele fehlen, wie viele sind neu."""
    old = np.asarray(before.raw.vertices, dtype=np.float64)
    new = np.asarray(after.raw.vertices, dtype=np.float64)
    point, normal = np.asarray(point, dtype=np.float64), np.asarray(normal, dtype=np.float64)
    old_outside = old[_off_axis(old, point, normal) > reach + CLEAR]
    new_outside = new[_off_axis(new, point, normal) > reach + CLEAR]
    assert len(old_outside) > 100, "der Körper muss Ecken abseits des Schnitts haben"
    missing = int((~np.isin(_rows(old_outside), _rows(new))).sum())
    foreign = int((~np.isin(_rows(new_outside), _rows(old))).sum())
    return missing, foreign


def _first_hit(mesh: MeshData, origin: np.ndarray, direction: np.ndarray) -> float:
    found = ray_hit_distances(np.asarray(mesh.raw.triangles), origin, direction)
    found = found[found > 0.0]
    return float(found.min()) if len(found) else math.inf


def _polygon_area(radius: float) -> float:
    """Die Fläche des eingeschriebenen Vielecks, mit dem am Netz gebohrt wird."""
    return BORE_SECTIONS / 2.0 * radius * radius * math.sin(2.0 * math.pi / BORE_SECTIONS)


@pytest.mark.parametrize("case", sorted(DRILLED))
def test_a_bore_along_a_tilted_normal_leaves_every_corner_outside_the_cut_in_place(
    case: str, profile: Profile
) -> None:
    """Jede Ecke außerhalb des Schnitts steht nach *Bohrung setzen* mit Normale bitgleich da.

    Vor RM-274 lag der ganze Körper für den Schnitt im Rahmen der Bohrung; an
    diesem schrägen Quader stand danach kaum eine Ecke mehr an ihrem Ort. Geprüft
    wird in beide Richtungen: Keine Ecke des Eingangs fehlt, und keine Ecke des
    Ergebnisses ist neu, außerhalb eines Zylinders um die Achse, der jedes
    Werkzeug dieser Fälle umschließt.
    """
    values, reach = DRILLED[case]
    body = _tilted_block()
    point, normal = _on_top(_turn())
    result = drill(
        body,
        position=tuple(float(value) for value in point),
        axis="z",
        normal=tuple(float(value) for value in normal),
        diameter=4.0,
        profile=profile,
        compensate=False,
        seed=1,
        **values,
    )

    assert _moved_outside(body, result.mesh, point, normal, reach) == (0, 0)
    assert result.mesh.raw.is_watertight
    if case == "Sackloch":
        # Das Vieleck mal die Tiefe: Die Zugabe über der Mündung schneidet Luft.
        assert body.volume - result.mesh.volume == pytest.approx(_polygon_area(2.0) * 3.0, abs=1e-9)


@pytest.mark.parametrize("case", ["Sackloch", "Langloch", "Aufweitung", "Tiefe gleich Dicke"])
def test_a_bore_into_a_tilted_face_of_an_stl_opens_at_its_mouth(
    case: str, profile: Profile
) -> None:
    """An einer schrägen float32-Fläche bleibt keine Haut über der Mündung.

    Der Weg über den Rahmen ließ hier bei jedem dieser Fälle eine Scheibe in der
    Mündung stehen — zwei Teile, der Strahl von außen traf nach einem Millimeter
    auf Material, und die Erkennung fand keine Bohrung (Durchsicht 0.5.1,
    ``konzepte/nachweise-release-0.5.1/sonden/bohren/p5_drill_platten.py``). Die
    Endebene in der Fläche lag um die
    float32-Rundung neben den Nachbardreiecken, und die Bereinigung fing nur
    Float64-Rauschen.
    """
    values: dict[str, Any] = {
        "Sackloch": {"depth": 4.0},
        "Langloch": {"depth": 4.0, "slot_length": 14.0},
        "Aufweitung": {"depth": 6.0, "widening_diameter": 10.0, "widening_depth": 2.0},
        "Tiefe gleich Dicke": {"depth": 10.0},
    }[case]
    body, point, normal = _stl_plate()
    result = drill(
        body,
        position=tuple(float(value) for value in point),
        axis="z",
        normal=tuple(float(value) for value in normal),
        diameter=6.0,
        profile=profile,
        compensate=False,
        seed=1,
        **values,
    )
    mesh = result.mesh

    assert mesh.component_count == 1, "eine Haut in der Mündung wäre ein zweites Teil"
    hit = _first_hit(mesh, point + normal, -normal)
    if case == "Tiefe gleich Dicke":
        # Der Boden fällt in die Unterseite, dahinter ist Luft: Die Bohrung geht durch.
        assert hit == math.inf
    else:
        assert hit == pytest.approx(1.0 + values["depth"], abs=1e-4)
    kinds = {feature.kind for feature in detect(mesh).values()}
    assert kinds & {"hole", "slot"}, kinds


@pytest.mark.parametrize("angle", [17.5, 33.0])
def test_a_floor_in_a_face_with_air_behind_it_goes_through(angle: float, profile: Profile) -> None:
    """Fällt der Boden eines Sacklochs in eine Fläche, hinter der Luft ist, geht die Bohrung durch.

    Das ist die Endebene des Bohrungsgebiets: Das Werkzeug reicht genau bis zur
    Tiefe. Im Rahmen der Bohrung legte die Bereinigung die Unterseite genau auf
    den Boden, und der Kern schnitt sie weg. In Weltlage trifft ein Boden eine
    schräge Fläche nicht genau — gemessen blieb bei 33° eine Haut unten
    (``konzepte/nachweise-release-0.5.1/sonden/bohren/p4_koplanar.py``). Jetzt
    reicht dieses Ende wie die Mündung
    um ``BOOLEAN_OVERLAP`` in die Luft dahinter.
    """
    turn = transform.rotation("y", angle)
    body = transform.apply(MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0))), turn)
    normal = transform.turned(np.array([[0.0, 0.0, 1.0]]), turn)[0]
    point = transform.moved_points(np.array([[5.0, 3.0, 5.0]]), turn)[0]
    result = drill(
        body,
        position=tuple(float(value) for value in point),
        axis="z",
        normal=tuple(float(value) for value in normal),
        diameter=6.0,
        depth=10.0,
        profile=profile,
        compensate=False,
        seed=1,
    )

    assert _first_hit(result.mesh, point + normal, -normal) == math.inf
    assert result.mesh.component_count == 1
    assert body.volume - result.mesh.volume == pytest.approx(_polygon_area(3.0) * 10.0, abs=1e-9)


def _bored(
    body: MeshData, point: np.ndarray, normal: np.ndarray
) -> tuple[MeshData, dict[str, Any], Any]:
    """Eine Sackbohrung Ø 6 × 4 an der Stelle, gebohrt ohne die Operation unter Prüfung.

    Das Werkzeug liegt in Weltlage und ragt über die Mündung; damit hängt der
    Ausgangskörper nicht an dem Weg, den die Fälle danach prüfen.
    """
    frame = frame_of(tuple(float(v) for v in normal), tuple(float(v) for v in point))
    tool = lathe.cylinder(radius=3.0, height=4.0 + BOOLEAN_OVERLAP, sections=BORE_SECTIONS)
    tool.apply_translation((0.0, 0.0, (BOOLEAN_OVERLAP - 4.0) / 2.0))
    to_world = np.eye(4)
    to_world[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    to_world[:3, 3] = point
    transform.moved(tool, to_world)
    mesh = boolean("difference", [body, MeshData.of(tool)], quality="fine", seed=1).mesh
    features = dict(detect(mesh))
    hole = next(feature for feature in features.values() if feature.kind == "hole")
    return mesh, features, hole


#: Die Merkmalswege über den Rahmen der Bohrung, je mit dem größten Abstand des
#: Werkzeugs von der Achse — *Bohrung ändern* auf Ø 8, auf eine neue Tiefe, und
#: *Zum Langloch ziehen* auf 14 mm (Mitten der Bögen 4 von der Mitte).
FEATURE_WAYS: dict[str, tuple[str, dict[str, Any], float]] = {
    "Bohrung ändern Ø 8": ("resize_hole", {"diameter": 8.0, "compensate": False}, 4.0),
    "neue Tiefe": ("resize_hole", {"diameter": 6.0, "depth": 6.0, "compensate": False}, 3.0),
    "Langloch": ("slot_hole", {"slot_length": 14.0, "slot_angle": 0.0}, 7.0),
}


@pytest.mark.parametrize("way", sorted(FEATURE_WAYS))
def test_changing_a_tilted_bore_leaves_every_corner_outside_the_cut_in_place(
    way: str, profile: Profile
) -> None:
    """*Bohrung ändern* und *Zum Langloch ziehen* lassen die Ecken abseits des Schnitts stehen.

    ``prepare.resize_bore`` und ``prepare.slot_bore`` legten den Körper wie das
    Bohren in den Rahmen der Bohrung und zurück (RM-274, derselbe Weg steht in
    RM-187 für ``resize_bore`` offen); an der Platte aus
    ``konzepte/nachweise-release-0.5.1/sonden/bohren/p6_merkmalwege.py`` blieb
    danach kein Dreieck bitgleich.
    """
    load_operations()
    point, normal = _on_top(_turn())
    mesh, features, hole = _bored(_tilted_block(subdivided=False), point, normal)
    name, values, reach = FEATURE_WAYS[way]
    result = feature_operation(name, mesh, features, hole, profile, **values)
    after = as_mesh_data(result.outputs[0].mesh)
    centre = np.asarray(hole.params["centre"], dtype=np.float64)

    assert _moved_outside(mesh, after, centre, normal, reach) == (0, 0)
    assert after.raw.is_watertight


def test_moving_a_tilted_bore_of_an_stl_keeps_its_new_mouth_open(profile: Profile) -> None:
    """*Bohrung ändern* mit neuer Stelle schließt die alte und öffnet die neue — auch an float32.

    Versetzt wird über den Mittenanker: Die Enden des Werkzeugs liegen in der
    Mündungsfläche und am Boden. Am Rahmenweg traf der Strahl in die neue
    Mündung nach einem Millimeter auf eine Haut (``p6_merkmalwege.py``, dieselbe
    Platte, um 5 mm quer versetzt); jetzt reicht das Ende in der Mündungsfläche
    in die Luft davor.
    """
    load_operations()
    body, point, normal = _stl_plate()
    mesh, features, hole = _bored(body, point, normal)
    across = np.cross(normal, np.array([0.0, 1.0, 0.0]))
    across /= np.linalg.norm(across)
    target = np.asarray(hole.params["centre"], dtype=np.float64) + across * 5.0
    result = feature_operation(
        "resize_hole",
        mesh,
        features,
        hole,
        profile,
        diameter=6.0,
        compensate=False,
        x=float(target[0]),
        y=float(target[1]),
        z=float(target[2]),
    )
    after = as_mesh_data(result.outputs[0].mesh)
    mouth = target + normal * float((point - target) @ normal)

    assert after.component_count == 1
    assert _first_hit(after, mouth + normal, -normal) == pytest.approx(5.0, abs=1e-4)
