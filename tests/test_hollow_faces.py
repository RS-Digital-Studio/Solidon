"""Aushöhlen mit frei gewählten Öffnungsflächen, Wand innen oder außen (P6.3).

Konzept §13.2, Zeile P6.3: eine oder mehrere gewählte Flächen bleiben offen,
die übrigen bleiben erhalten; das Wandmaß wächst nach innen oder nach außen.
Am exakten Körper rechnet ``BRepOffsetAPI_MakeThickSolidByJoin``, am Netz das
Raster des bisherigen Aushöhlens mit einem Öffnungswerkzeug je Fläche.

Die Sollwerte kommen aus der Konstruktion, nicht aus der Operation: Ein
Quader 40 × 30 × 20 mit Wand 2 und offener Ober- und Vorderseite hat den
Hohlraum 36 × 28 × 18, also 24000 − 18144 = 5856 mm³ Material. Außen mit
gerundeten Stößen ist es die Minkowski-Summe mit der Kugel, unter der
Öffnungsebene abgeschnitten (Bericht P6.3, Sonde ``probe_thick.py``).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.autosplit import upright_normal
from app.core.geom.hollow import erosion_steps
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.slice.analysis import cross_section
from app.core.types import Feature, OpContext, Profile, Scene, SceneObject, Vec3
from tests.helpers import exact_kernel
from tests.test_missing_ops import run

A, B, C = 40.0, 30.0, 20.0
WALL = 2.0

#: Material des Quaders mit offener Ober- und Vorderseite: Hohlraum 36 auf 28 auf 18.
TOP_AND_FRONT_OPEN = A * B * C - (A - 2 * WALL) * (B - WALL) * (C - WALL)

#: Außen, Oberseite offen, runde Stöße: Minkowski-Summe mit der Kugel vom
#: Radius der Wand, oberhalb der Öffnungsebene abgeschnitten, ohne den Quader.
OUTSIDE_TOP_OPEN = (
    WALL * (A * B + 2 * B * C + 2 * C * A)
    + math.pi * WALL**2 * (C + (A + B) / 2.0)
    + 2.0 / 3.0 * math.pi * WALL**3
)


def _face(features: dict[str, Feature], normal: Vec3) -> str:
    """Die eine ebene Fläche mit dieser Normale."""
    found = [
        feature.id
        for feature in features.values()
        if feature.kind == "face"
        and np.dot(np.asarray(feature.params["normal"], dtype=float), normal) > 0.99
    ]
    assert len(found) == 1, found
    return found[0]


def _exact_box() -> SceneObject:
    edit = exact_kernel()
    from app.core.brep.features import features_of

    body = edit.box(A, B, C)
    return SceneObject(
        id="obj_1", name="Kasten", mesh=body, kind="brep", features=features_of(body)
    )


def _mesh_box() -> SceneObject:
    """Derselbe Quader als Netz, auf dem Bett wie der exakte (z von 0 bis 20)."""
    raw = trimesh.creation.box(extents=(A, B, C))
    raw.apply_translation((0.0, 0.0, C / 2.0))
    mesh = MeshData.of(raw)
    return SceneObject(id="obj_1", name="Kasten", mesh=mesh, features=detect(mesh))


def _is_open(mesh: MeshData, feature: Feature, offset: float) -> bool:
    """Ist an dieser Fläche Luft, eine halbe Wand vor oder hinter ihr?

    Gefragt wird an der Mitte der Fläche, um ``offset`` entlang ihrer Normalen
    versetzt — negativ für eine Wand innen, positiv für eine Wand außen. Eine
    offene Fläche hat dort keine Wand mehr. Gemessen über einen Schnitt durch
    den Punkt quer zur Normalen, damit zwei benachbarte Öffnungen einander
    nicht die Antwort nehmen (ein Querschnitt mit Loch zählte sie nicht).
    """
    from shapely.geometry import Point

    normal = np.asarray(feature.params["normal"], dtype=float)
    point = np.asarray(feature.params["centre"], dtype=float) + normal * offset
    turn = upright_normal((float(normal[0]), float(normal[1]), float(normal[2])))
    turned = mesh.raw.copy()
    turned.apply_transform(turn)
    probe = (turn @ np.append(point, 1.0))[:3]
    shape = cross_section(MeshData.of(turned), float(probe[2]))
    return shape is None or shape.is_empty or not shape.contains(Point(probe[0], probe[1]))


def _codes(result: Any) -> set[str]:
    return {finding.code for finding in result.findings}


# --- exakt -----------------------------------------------------------------------


def test_an_exact_box_opens_at_two_chosen_faces_and_keeps_the_others(profile: Profile) -> None:
    load_operations()
    source = _exact_box()
    top = _face(source.features, (0.0, 0.0, 1.0))
    front = _face(source.features, (0.0, -1.0, 0.0))
    kept = {
        name: feature
        for name, feature in source.features.items()
        if feature.kind == "face" and name not in {top, front}
    }

    result = run("hollow_object", source, profile, wall=WALL, openings=(top, front))

    output = result.outputs[0]
    assert output.kind == "brep"
    assert output.mesh.is_closed
    assert float(output.mesh.volume) == pytest.approx(TOP_AND_FRONT_OPEN, rel=1e-9)
    assert not any(finding.converts_exact_body for finding in result.findings)
    # Die vier ungewählten Außenflächen bleiben — unter ihren Namen, mit ihrer Fläche.
    for name, before in kept.items():
        after = output.features.get(name)
        assert after is not None, (name, sorted(output.features))
        assert after.params["area"] == pytest.approx(before.params["area"], rel=1e-9)
        assert np.allclose(after.params["normal"], before.params["normal"], atol=1e-9)
    # Die Wand steht wirklich: der Boden des Hohlraums liegt eine Wand über dem Bett.
    floors = [
        feature
        for feature in output.features.values()
        if feature.kind == "face"
        and np.allclose(feature.params["normal"], (0.0, 0.0, 1.0), atol=1e-9)
        and feature.params["centre"][2] == pytest.approx(WALL, abs=1e-9)
    ]
    assert len(floors) == 1
    assert floors[0].params["area"] == pytest.approx((A - 2 * WALL) * (B - WALL), rel=1e-9)
    # Oben bleibt nur der Rand um die Öffnung stehen.
    rim = [
        feature
        for feature in output.features.values()
        if feature.kind == "face"
        and np.allclose(feature.params["normal"], (0.0, 0.0, 1.0), atol=1e-9)
        and feature.params["centre"][2] == pytest.approx(C, abs=1e-9)
    ]
    assert sum(feature.params["area"] for feature in rim) == pytest.approx(
        A * B - (A - 2 * WALL) * (B - WALL), rel=1e-9
    )
    done = next(finding for finding in result.findings if finding.code == "hollow.done")
    assert done.values["wall_mm"] == pytest.approx(WALL)


def test_an_exact_box_grows_its_wall_outside_and_stays_flush_at_the_opening(
    profile: Profile,
) -> None:
    load_operations()
    source = _exact_box()
    top = _face(source.features, (0.0, 0.0, 1.0))

    result = run("hollow_object", source, profile, wall=WALL, openings=(top,), wall_side="outside")

    output = result.outputs[0]
    assert output.kind == "brep" and output.mesh.is_closed
    assert float(output.mesh.volume) == pytest.approx(OUTSIDE_TOP_OPEN, rel=1e-9)
    bounds = output.mesh.bounds
    assert tuple(bounds.minimum) == pytest.approx((-A / 2 - WALL, -B / 2 - WALL, -WALL), abs=1e-6)
    # Die Öffnung bleibt bündig mit der gewählten Fläche — nichts wächst darüber.
    assert tuple(bounds.maximum) == pytest.approx((A / 2 + WALL, B / 2 + WALL, C), abs=1e-6)


def test_an_exact_cylinder_opens_at_its_top(profile: Profile) -> None:
    edit = exact_kernel()
    load_operations()
    from app.core.brep.features import features_of

    body = edit.cylinder(30.0, 20.0)
    source = SceneObject(
        id="obj_1", name="Dose", mesh=body, kind="brep", features=features_of(body)
    )
    top = _face(source.features, (0.0, 0.0, 1.0))

    result = run("hollow_object", source, profile, wall=WALL, openings=(top,))

    output = result.outputs[0]
    assert output.kind == "brep"
    expected = math.pi * (15.0**2 * 20.0 - 13.0**2 * 18.0)
    assert float(output.mesh.volume) == pytest.approx(expected, rel=1e-9)


def test_open_top_outside_stays_exact_without_openings(profile: Profile) -> None:
    """*Oben öffnen* mit Wand außen ist dieselbe Handlung wie die gewählte Oberseite."""
    load_operations()
    source = _exact_box()

    result = run(
        "hollow_object", source, profile, wall=WALL, open_top=True, vents=0, wall_side="outside"
    )

    output = result.outputs[0]
    assert output.kind == "brep"
    assert float(output.mesh.volume) == pytest.approx(OUTSIDE_TOP_OPEN, rel=1e-9)


def test_a_wall_too_thick_for_the_body_says_so_and_leaves_it(profile: Profile) -> None:
    """OpenCASCADE gibt bei zu großer Wand den Eingang zurück, ohne zu werfen."""
    load_operations()
    source = _exact_box()
    top = _face(source.features, (0.0, 0.0, 1.0))

    result = run("hollow_object", source, profile, wall=16.0, openings=(top,))

    assert float(result.outputs[0].mesh.volume) == pytest.approx(A * B * C, rel=1e-12)
    thin = next(finding for finding in result.findings if finding.code == "hollow.too_thin")
    assert thin.severity == "warning"
    assert thin.suggestions, "ein Befund ohne Ausweg ist unfertig (Regel 17)"
    assert "hollow.done" not in _codes(result)


def _ell() -> SceneObject:
    """Sockel 40 × 30 × 10 mit einer Rippe 40 × 4 × 30 an der Hinterkante."""
    edit = exact_kernel()
    from app.core.brep.features import features_of
    from app.core.geom.transform import translation

    base = edit.box(40.0, 30.0, 10.0)
    rib = edit.transformed(edit.box(40.0, 4.0, 30.0), translation((0.0, 13.0, 0.0)))
    body = edit.unified(edit.boolean("union", [base, rib]))
    return SceneObject(
        id="obj_1", name="Winkel", mesh=body, kind="brep", features=features_of(body)
    )


def _ell_tops(source: SceneObject) -> tuple[str, ...]:
    tops = tuple(
        feature.id
        for feature in source.features.values()
        if feature.kind == "face"
        and np.allclose(feature.params["normal"], (0.0, 0.0, 1.0), atol=1e-9)
    )
    assert len(tops) == 2
    return tops


def test_colliding_inner_walls_are_explained_instead_of_built(profile: Profile) -> None:
    """Der konkave Fall: Die Innenwände an der Rippe finden keinen gemeinsamen Verlauf.

    Gemessen am 23.09.2026: OpenCASCADE gibt den Winkel mit beiden gewählten
    Oberseiten unverändert zurück, obwohl das Raster darin Platz für einen
    Hohlraum findet. Das ist keine zu dicke Wand, und der Befund sagt das.
    Mit „Teil unverändert lassen" bleibt der Körper, wie er war.
    """
    load_operations()
    source = _ell()

    result = run(
        "hollow_object",
        source,
        profile,
        wall=1.0,
        openings=_ell_tops(source),
        exact_fallback="unchanged",
    )

    assert result.outputs[0].mesh is source.mesh
    collide = next(finding for finding in result.findings if finding.code == "hollow.walls_collide")
    assert collide.severity == "warning" and collide.suggestions
    assert "hollow.too_thin" not in _codes(result)


def test_where_the_exact_kernel_gives_way_the_raster_builds_the_wall_after_asking(
    profile: Profile,
) -> None:
    """Regel 21: Der Rückfall aufs Raster ist eine Frage, und ihre Antwort steht im Schritt.

    Dieselben Öffnungen, dieselbe Wand, am Dreiecksmodell: Die Rippe (4 mm) ist
    dünner als zwei Wände zu 2,5 mm, sie bleibt voll; der Sockel bekommt
    seinen Hohlraum. Oben offen sind beide gewählten Flächen, soweit darunter
    Luft liegt — über der vollen Rippe nennt ``hollow.opening_misses`` die
    Fläche, statt eine Kerbe zu schneiden.
    """
    load_operations()
    source = _ell()
    asked: list[str] = []

    def answer(question: str, choices: list[str]) -> str:
        asked.append(question)
        return choices[0]

    spec = REGISTRY.get("hollow_object")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(wall=2.5, openings=_ell_tops(source)),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=answer,
            cancelled=NeverCancelled(),
        )
    )

    assert len(asked) == 1
    assert result.answered == {"exact_fallback": "raster"}
    output = result.outputs[0]
    assert output.kind == "mesh"
    assert output.mesh.is_watertight and output.mesh.component_count == 1
    codes = _codes(result)
    assert "hollow.exact_fallback" in codes and "hollow.done" in codes
    # Der Sockel ist hohl: sein Hohlraum 35 auf 21 auf 5 (Wand 2,5, oben offen bis
    # an die Rippe) nimmt Material, die Rippe bleibt voll.
    assert float(output.mesh.volume) < float(source.mesh.volume) - 0.8 * 35.0 * 21.0 * 5.0

    stored = run(
        "hollow_object",
        source,
        profile,
        wall=2.5,
        openings=_ell_tops(source),
        exact_fallback="raster",
    )
    assert float(stored.outputs[0].mesh.volume) == pytest.approx(
        float(output.mesh.volume), rel=1e-12
    ), "die gespeicherte Antwort rechnet ohne Frage dasselbe"


# --- Netz -----------------------------------------------------------------------


def _top_and_front_band(wall: float, tolerance: float) -> tuple[float, float]:
    """Das Material des oben und vorn offenen Quaders, wenn jede Innenfläche
    des Rasters bis zu ``tolerance`` neben ihrer Sollage liegt."""
    thin, thick = wall - tolerance, wall + tolerance
    return (
        A * B * C - (A - 2 * thin) * (B - thin) * (C - thin),
        A * B * C - (A - 2 * thick) * (B - thick) * (C - thick),
    )


def _raster_tolerance(result: Any) -> float:
    done = next(finding for finding in result.findings if finding.code == "hollow.done")
    return float(done.values["tolerance_mm"])


def test_a_mesh_box_opens_at_two_chosen_faces_and_nowhere_else(profile: Profile) -> None:
    load_operations()
    source = _mesh_box()
    top = _face(source.features, (0.0, 0.0, 1.0))
    front = _face(source.features, (0.0, -1.0, 0.0))

    result = run("hollow_object", source, profile, wall=WALL, openings=(top, front), vents=2)

    output = result.outputs[0]
    body = output.mesh
    assert output.kind == "mesh"
    assert body.is_watertight
    assert body.component_count == 1
    for name, feature in source.features.items():
        wanted = name in {top, front}
        assert _is_open(body, feature, -WALL / 2.0) is wanted, name
    # Ein offener Hohlraum ist seine eigene Entlüftung: keine Bohrung im Boden.
    done = next(finding for finding in result.findings if finding.code == "hollow.done")
    assert done.values["vents"] == 0
    # Die Wand trifft das Raster: jede Innenfläche höchstens eine halbe Zelle daneben.
    least, most = _top_and_front_band(WALL, _raster_tolerance(result))
    assert least <= float(body.volume) <= most, (least, float(body.volume), most)


def test_a_mesh_box_grows_its_wall_outside_and_the_rim_stays_flush(profile: Profile) -> None:
    load_operations()
    source = _mesh_box()
    top = _face(source.features, (0.0, 0.0, 1.0))

    result = run("hollow_object", source, profile, wall=WALL, openings=(top,), wall_side="outside")

    body = result.outputs[0].mesh
    assert body.is_watertight and body.component_count == 1
    tolerance = _raster_tolerance(result)
    bounds = body.bounds
    # Bündig an der Öffnung: nichts ragt über die gewählte Fläche hinaus.
    assert float(bounds.maximum[2]) == pytest.approx(C, abs=1e-6)
    assert float(bounds.minimum[2]) == pytest.approx(-WALL, abs=tolerance + 1e-3)
    assert float(bounds.maximum[0]) == pytest.approx(A / 2 + WALL, abs=tolerance + 1e-3)
    for name, feature in source.features.items():
        assert _is_open(body, feature, WALL / 2.0) is (name == top), name
    # Das Innere ist der alte Körper: die Öffnung hat genau seinen Umriss.
    assert float(body.volume) == pytest.approx(OUTSIDE_TOP_OPEN, rel=0.06)


def _two_boxes() -> SceneObject:
    """Zwei Würfel 20 mm, verbunden durch einen Steg von 2 mm — dünner als zwei Wände.

    Der Innenraum zerfällt damit in zwei Hohlräume, und eine Öffnung am linken
    Würfel erreicht den rechten nicht.
    """
    from app.core.geom.boolean import boolean

    left = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    left.apply_translation((-20.0, 0.0, 10.0))
    right = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    right.apply_translation((20.0, 0.0, 10.0))
    web = trimesh.creation.box(extents=(22.0, 20.0, 2.0))
    web.apply_translation((0.0, 0.0, 1.0))
    joined = boolean("union", [MeshData.of(left), MeshData.of(right), MeshData.of(web)]).mesh
    return SceneObject(id="obj_1", name="Paar", mesh=joined, features=detect(joined))


def test_a_cavity_no_opening_reaches_is_named(profile: Profile) -> None:
    """Die Öffnung am linken Würfel lässt den rechten Hohlraum geschlossen — gesagt wird es.

    Gemessen am Tischorganizer aus dem Kundenkorpus (23.09.2026): Neben dem
    geöffneten Fach blieben weitere Hohlräume zu, am bisherigen Weg mit
    Entlüftung genauso, und kein Befund nannte sie.
    """
    load_operations()
    source = _two_boxes()
    left_top = next(
        feature.id
        for feature in source.features.values()
        if feature.kind == "face"
        and np.allclose(feature.params["normal"], (0.0, 0.0, 1.0), atol=1e-6)
        and float(feature.params["centre"][0]) < -10.0
        and float(feature.params["centre"][2]) > 19.0
    )

    result = run("hollow_object", source, profile, wall=WALL, openings=(left_top,))

    closed = next(
        finding for finding in result.findings if finding.code == "hollow.closed_cavities"
    )
    assert closed.values["count"] == 1
    # Der rechte Hohlraum: 16 mm Würfel, auf das Raster genau.
    assert float(closed.values["closed_cm3"]) == pytest.approx(16.0**3 / 1000.0, rel=0.2)
    assert closed.suggestions

    both = run("hollow_object", source, profile, wall=WALL, openings=(left_top,), vents=0)
    assert "hollow.closed_cavities" in _codes(both), "die Entlüftung öffnet ihn nicht"

    shut = run("hollow_object", source, profile, wall=WALL, vents=0)
    assert "hollow.closed_cavities" not in _codes(shut), "gewollt geschlossen ist kein Befund"


def _wedge_profile() -> list[tuple[float, float]]:
    """Querschnitt eines Keils in (y, z): Boden 30, Rückwand 20, Schräge dazwischen."""
    return [(-15.0, 0.0), (15.0, 0.0), (-15.0, 20.0)]


#: Von (Umrisskoordinate p, q, Zugrichtung e) nach (x, y, z) = (e, p, q): eine
#: zyklische Vertauschung, also eine echte Drehung ohne Spiegelung.
_WEDGE_FRAME = np.array(
    [[0.0, 0.0, 1.0, -20.0], [1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
)


def _mesh_wedge() -> SceneObject:
    from shapely.geometry import Polygon

    raw = trimesh.creation.extrude_polygon(Polygon(_wedge_profile()), 40.0)
    raw.apply_transform(_WEDGE_FRAME)
    mesh = MeshData.of(raw)
    return SceneObject(id="obj_1", name="Keil", mesh=mesh, features=detect(mesh))


def _exact_wedge() -> SceneObject:
    edit = exact_kernel()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt

    from app.core.brep.features import features_of
    from app.core.brep.profiles import prism

    polygon = BRepBuilderAPI_MakePolygon()
    for p, q in _wedge_profile():
        polygon.Add(gp_Pnt(p, q, 0.0))
    polygon.Close()
    face = BRepBuilderAPI_MakeFace(polygon.Wire(), True).Face()
    body = edit.transformed(prism(face, 40.0), _WEDGE_FRAME)
    return SceneObject(id="obj_1", name="Keil", mesh=body, kind="brep", features=features_of(body))


def _slope(features: dict[str, Feature]) -> str:
    found = [
        feature.id
        for feature in features.values()
        if feature.kind == "face"
        and float(feature.params["normal"][2]) > 0.1
        and float(feature.params["normal"][2]) < 0.99
    ]
    assert len(found) == 1, sorted((f.id, f.params.get("normal")) for f in features.values())
    return found[0]


def test_a_slanted_face_opens_on_the_mesh_as_well(profile: Profile) -> None:
    """Keine Achsrichtung: Die Schräge eines Keils bleibt offen, Boden und Rückwand zu.

    Soll aus der Konstruktion: Der Hohlraum ist das Dreieck mit dem Abstand der
    Wand zu Boden und Rückwand, bis an die Schräge — Katheten 25 und 16⅔,
    Länge 36 —, also 7500 mm³ Luft in 12000 mm³ Keil.
    """
    load_operations()
    source = _mesh_wedge()
    assert float(source.mesh.volume) == pytest.approx(12000.0, rel=1e-9)
    slope = _slope(source.features)

    result = run("hollow_object", source, profile, wall=WALL, openings=(slope,))

    body = result.outputs[0].mesh
    assert body.is_watertight and body.component_count == 1
    assert float(body.volume) == pytest.approx(12000.0 - 7500.0, rel=0.08)
    for name, feature in source.features.items():
        assert _is_open(body, feature, -WALL / 2.0) is (name == slope), name


def test_the_same_slanted_face_opens_exactly(profile: Profile) -> None:
    load_operations()
    source = _exact_wedge()
    assert float(source.mesh.volume) == pytest.approx(12000.0, rel=1e-9)
    slope = _slope(source.features)

    result = run("hollow_object", source, profile, wall=WALL, openings=(slope,))

    assert result.outputs[0].kind == "brep"
    assert float(result.outputs[0].mesh.volume) == pytest.approx(4500.0, rel=1e-9)


@pytest.mark.parametrize("kind", ["curved_face", "face"])
def test_a_curved_face_on_a_mesh_is_refused_with_a_way_forward(profile: Profile, kind: str) -> None:
    """Am Netz bleibt nur eine ebene Fläche offen — eine gewölbte sagt ab, mit Weg.

    Beide Fälle: die Art sagt schon „gewölbt" (``curved_face``), und eine
    Fläche, deren Dreiecke nicht in einer Ebene liegen, obwohl sie ``face``
    heißt — der Mantel einer Dose, von Hand so benannt.
    """
    load_operations()
    raw = trimesh.creation.cylinder(radius=15.0, height=20.0, sections=64)
    mesh = MeshData.of(raw)
    mantle = tuple(
        int(index) for index in np.flatnonzero(np.abs(np.asarray(raw.face_normals)[:, 2]) < 0.5)
    )
    curved = Feature(
        id="wall_1",
        kind=kind,
        provenance="detected",
        params={"area": 1885.0, "centre": (0.0, 0.0, 0.0), "normal": (1.0, 0.0, 0.0)},
        face_indices=mantle,
    )
    source = SceneObject(id="obj_1", name="Dose", mesh=mesh, features={"wall_1": curved})

    with pytest.raises(ValidationError) as caught:
        run("hollow_object", source, profile, wall=WALL, openings=("wall_1",))

    assert caught.value.field == "openings"
    assert caught.value.constraint == "not_planar"
    assert caught.value.suggestions


@pytest.mark.parametrize(
    ("case", "constraint"),
    [
        ("unknown", "unknown_feature"),
        ("foreign", "foreign_feature"),
        ("not_a_face", "not_a_face"),
        ("with_open_at", "opening_twice"),
    ],
)
def test_every_refusal_of_an_opening_names_its_reason(
    profile: Profile, case: str, constraint: str
) -> None:
    load_operations()
    source = _mesh_box()
    top = _face(source.features, (0.0, 0.0, 1.0))
    front = _face(source.features, (0.0, -1.0, 0.0))
    params: dict[str, Any] = {"wall": WALL}
    if case == "unknown":
        params["openings"] = ("face_99",)
    elif case == "foreign":
        params["openings"] = (f"obj_2:{top}",)
    elif case == "not_a_face":
        drilled = run(
            "drill_hole", source, profile, x=0.0, y=0.0, z=C, diameter=6.0, depth=5.0
        ).outputs[0]
        source = SceneObject(
            id="obj_1", name="Kasten", mesh=drilled.mesh, features=detect(drilled.mesh)
        )
        hole = next(f.id for f in source.features.values() if f.kind == "hole")
        params["openings"] = (hole,)
    else:
        params.update(openings=(top,), open_at=front)

    with pytest.raises(ValidationError) as caught:
        run("hollow_object", source, profile, **params)

    assert caught.value.constraint == constraint
    assert caught.value.field == ("open_at" if case == "with_open_at" else "openings")
    assert caught.value.suggestions, "jede Absage nennt einen Ausweg (Regel 17)"


# --- Kundenweg: Gehäuse mit mehreren Öffnungen (§13.9) ----------------------------


@pytest.mark.parametrize("exact", [True, False])
def test_an_enclosure_with_two_openings_goes_through_history_undo_and_the_file(
    profile: Profile, tmp_path: Any, exact: bool
) -> None:
    """Der Kundenweg aus Konzept §13.9: Gehäuse anlegen, zwei Seiten offen,
    Wand ändern, speichern, wieder öffnen, ein Strg+Z.

    Auf beiden Körperarten: der Quader exakt und als Netz. Der Schritt trägt
    seine Flächen als Kennungen; nach dem Öffnen der Datei rechnet er
    dasselbe, und ein Undo nimmt ihn als Ganzes zurück.
    """
    if exact:
        exact_kernel()
    from app.core.scene import ResultCache, evaluate
    from app.core.scene.history import History, OperationDraft
    from app.core.scene.project import load, new_project, save

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    box = "create_brep_box" if exact else "create_box"
    history.apply("Kasten", [OperationDraft(op=box, params={"width": A, "depth": B, "height": C})])
    first = evaluate(project.document, profile, cache=ResultCache())
    body = first.scene.objects["obj_1"]
    top = _face(body.features, (0.0, 0.0, 1.0))
    front = _face(body.features, (0.0, -1.0, 0.0))

    history.apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object",
                inputs=("obj_1",),
                params={"wall": WALL, "openings": [top, front]},
            )
        ],
    )
    opened = evaluate(project.document, profile, cache=ResultCache())
    assert opened.stopped_at is None, opened.stopped_at
    hollowed = opened.scene.objects["obj_1"]
    assert hollowed.kind == ("brep" if exact else "mesh")
    volume = float(hollowed.mesh.volume)
    if exact:
        assert volume == pytest.approx(TOP_AND_FRONT_OPEN, rel=1e-9)
    else:
        least, most = _top_and_front_band(WALL, erosion_steps(WALL)[1] / 2.0 + 1e-3)
        assert least <= volume <= most, (least, volume, most)

    # Die Wand ändern heißt, den Schritt ändern — er rechnet neu, mit denselben Flächen.
    step = project.document.ops[-1]
    history.change_params(step.id, {**step.params, "wall": 3.0})
    thicker = evaluate(project.document, profile, cache=ResultCache())
    changed = float(thicker.scene.objects["obj_1"].mesh.volume)
    if exact:
        assert changed == pytest.approx(A * B * C - (A - 6.0) * (B - 3.0) * (C - 3.0), rel=1e-9)
    else:
        least, most = _top_and_front_band(3.0, erosion_steps(3.0)[1] / 2.0 + 1e-3)
        assert least <= changed <= most, (least, changed, most)

    path = save(project, tmp_path / "gehaeuse.p3d")
    reopened = load(path)
    again = evaluate(reopened.document, profile, cache=ResultCache())
    assert reopened.document.ops[-1].params["openings"] == [top, front]
    assert float(again.scene.objects["obj_1"].mesh.volume) == pytest.approx(
        float(thicker.scene.objects["obj_1"].mesh.volume), rel=1e-9
    )

    history.undo()
    history.undo()
    back = evaluate(project.document, profile, cache=ResultCache())
    assert float(back.scene.objects["obj_1"].mesh.volume) == pytest.approx(A * B * C, rel=1e-9)
    history.redo()
    forth = evaluate(project.document, profile, cache=ResultCache())
    assert float(forth.scene.objects["obj_1"].mesh.volume) == pytest.approx(volume, rel=1e-9)


@pytest.mark.parametrize("exact", [True, False])
def test_a_cancelled_hollowing_stops_without_a_result(profile: Profile, exact: bool) -> None:
    """Abbrechen hält an, ohne halben Körper — auf beiden Kernen (§15.6)."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    load_operations()
    source = _exact_box() if exact else _mesh_box()
    top = _face(source.features, (0.0, 0.0, 1.0))
    signal = CancelSignal()
    signal.cancel()
    spec = REGISTRY.get("hollow_object")

    with pytest.raises(OperationCancelled):
        spec.fn(
            OpContext(
                scene=Scene(objects={source.id: source}),
                inputs=[source],
                params=spec.params(wall=WALL, openings=(top,)),
                profile=profile,
                quality="fine",
                seed=None,
                progress=lambda fraction, text: None,
                ask=lambda question, choices: choices[0],
                cancelled=signal,
            )
        )


# --- alte Projekte ---------------------------------------------------------------

#: Gemessen am Stand ``29dcefa4`` vor P6.3 (Sonde ``golden_hollow.py``): Quader
#: 60 auf 40 auf 30 als Netz, die fünf bisherigen Parameterformen. Die Zahlen sind
#: das Ergebnis, das ein gespeicherter Schritt weiter liefern muss.
LEGACY = {
    "closed vents 1": ({"wall": 2.0, "vents": 1}, 19868.7706125652),
    "closed vents 3": ({"wall": 2.0, "vents": 3}, 19827.151343868423),
    "open top": ({"wall": 2.0, "open_top": True}, 16621.456790123448),
    "open at front": ({"wall": 2.0, "open_at": "FRONT"}, 16438.12345679013),
    "closed wall 3": ({"wall": 3.0, "vents": 0}, 30078.333333333332),
}


@pytest.mark.parametrize("case", sorted(LEGACY))
def test_saved_hollowing_steps_compute_as_before(profile: Profile, case: str) -> None:
    load_operations()
    raw = trimesh.creation.box(extents=(60.0, 40.0, 30.0))
    mesh = MeshData.of(raw)
    features = detect(mesh)
    source = SceneObject(id="obj_1", name="Kasten", mesh=mesh, features=features)
    params, volume = LEGACY[case]
    if params.get("open_at") == "FRONT":
        params = {**params, "open_at": _face(features, (0.0, -1.0, 0.0))}

    result = run("hollow_object", source, profile, **params)

    assert float(result.outputs[0].mesh.volume) == pytest.approx(volume, rel=1e-9)
