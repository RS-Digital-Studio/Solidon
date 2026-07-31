"""Die Skizzen- und Formgebungs-Operationen (Bauplan §30.1, §40 zu P13).

Jede Operation wird über das Register aufgerufen und gegen eine geschlossene
Formel gemessen — nicht gegen ein selbst erzeugtes Ergebnis. Ein Kreis, der
als exakte Kurve in den Kern geht, trifft π; ein diskretisierter träfe es
nicht. Genau daran erkennt man, dass der Weg stimmt.
"""

from __future__ import annotations

import math

import pytest

from app.core.brep.kernel import Solid, available
from app.core.errors import ValidationError
from app.core.registry import REGISTRY
from app.core.scene import ResultCache, evaluate
from app.core.scene.cancel import NeverCancelled
from app.core.sketch.serialize import sketch_to_text
from app.core.types import (
    Document,
    OpContext,
    Operation,
    OpResult,
    Parameter,
    Profile,
    Scene,
    SceneObject,
    Sketch,
    SketchElement,
)
from tests.test_sketch import rectangle

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")


def run(
    op: str,
    entry: SceneObject | None = None,
    parameters: dict[str, Parameter] | None = None,
    **params: object,
) -> OpResult:
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry} if entry else {}, parameters=parameters or {}),
            inputs=[entry] if entry else [],
            params=spec.params(**params),
            profile=None,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def solid_of(result: OpResult) -> Solid:
    body = result.outputs[0].mesh
    assert isinstance(body, Solid)
    return body


def brep_box(width: float = 40.0, depth: float = 30.0, height: float = 20.0) -> SceneObject:
    entry = run("create_brep_box", width=width, depth=depth, height=height).outputs[0]
    entry.id = "obj_1"
    return entry


# --- Extrudieren: vier Grundformen gegen vier Formeln ---------------------------


def test_an_extruded_rectangle_is_a_block() -> None:
    body = solid_of(run("sketch_extrude", shape="rectangle", length=40, width=20, height=10))
    assert body.volume == pytest.approx(8000.0, rel=1e-9)


def test_an_extruded_circle_hits_pi() -> None:
    body = solid_of(run("sketch_extrude", shape="circle", length=20, height=5))
    assert body.volume == pytest.approx(math.pi * 100.0 * 5.0, rel=1e-9)


def test_an_extruded_slot_is_a_rectangle_plus_a_circle() -> None:
    body = solid_of(run("sketch_extrude", shape="slot", length=30, width=10, height=4))
    assert body.volume == pytest.approx((20.0 * 10.0 + math.pi * 25.0) * 4.0, rel=1e-9)


def test_an_extruded_hexagon_matches_the_regular_polygon_area() -> None:
    body = solid_of(run("sketch_extrude", shape="polygon", length=20, corners=6, height=3))
    assert body.volume == pytest.approx(3.0 * math.sqrt(3.0) / 2.0 * 100.0 * 3.0, rel=1e-9)


# --- Tasche ---------------------------------------------------------------------


def test_a_pocket_removes_exactly_its_volume() -> None:
    result = run("sketch_pocket", brep_box(), shape="rectangle", length=10, width=10, depth=5)
    assert solid_of(result).volume == pytest.approx(24000.0 - 500.0, rel=1e-9)


def test_a_through_pocket_ignores_the_depth() -> None:
    result = run("sketch_pocket", brep_box(), shape="circle", length=10, depth=1, through=True)
    assert solid_of(result).volume == pytest.approx(24000.0 - math.pi * 25.0 * 20.0, rel=1e-9)


def test_a_pocket_on_a_mesh_says_it_needs_a_brep_body() -> None:
    import trimesh

    from app.core.geom.mesh import MeshData

    cube = MeshData.of(trimesh.creation.box(extents=(10, 10, 10)))
    entry = SceneObject(id="obj_1", name="mesh cube", mesh=cube)
    with pytest.raises(ValidationError):
        run("sketch_pocket", entry, shape="rectangle", length=5, width=5, depth=2)


# --- Rotieren -------------------------------------------------------------------


def test_a_revolved_rectangle_is_a_ring() -> None:
    body = solid_of(
        run("sketch_revolve", shape="rectangle", length=5, width=8, offset=10, angle=360)
    )
    assert body.volume == pytest.approx(math.pi * (15.0**2 - 10.0**2) * 8.0, rel=1e-9)


def test_a_revolved_circle_is_a_torus_by_pappus() -> None:
    body = solid_of(run("sketch_revolve", shape="circle", length=6, offset=10, angle=360))
    centroid_radius = 10.0 + 3.0
    assert body.volume == pytest.approx(2.0 * math.pi * centroid_radius * math.pi * 9.0, rel=1e-6)


def test_a_partial_revolve_takes_its_share() -> None:
    body = solid_of(
        run("sketch_revolve", shape="rectangle", length=5, width=8, offset=10, angle=90)
    )
    assert body.volume == pytest.approx(math.pi * (15.0**2 - 10.0**2) * 8.0 / 4.0, rel=1e-9)


# --- Entlang eines Bogens -------------------------------------------------------


def test_a_swept_circle_is_an_elbow_by_pappus() -> None:
    body = solid_of(run("sketch_sweep", shape="circle", length=10, bend_radius=20, bend_angle=90))
    assert body.volume == pytest.approx(math.pi * 25.0 * (math.pi / 2.0 * 20.0), rel=1e-6)


def test_a_bend_tighter_than_the_profile_is_rejected() -> None:
    with pytest.raises(ValidationError):
        run("sketch_sweep", shape="circle", length=10, bend_radius=4, bend_angle=90)


# --- Aufspannen -----------------------------------------------------------------


def test_a_loft_between_rectangles_is_a_frustum() -> None:
    body = solid_of(
        run("sketch_loft", shape="rectangle", length=40, width=20, height=10, top_scale=0.5)
    )
    lower, upper = 800.0, 200.0
    expected = 10.0 / 3.0 * (lower + upper + math.sqrt(lower * upper))
    assert body.volume == pytest.approx(expected, rel=1e-6)


# --- Gezeichnete Skizze als Parameter (§30.1) -----------------------------------


def drawn_text(width_value: str = "@width", height_value: str = "@height") -> str:
    """Das verzogene Rechteck aus test_sketch, als Parametertext einer Op."""
    return sketch_to_text(rectangle(width_value, height_value))


def scene_parameters(**values: float) -> dict[str, Parameter]:
    return {name: Parameter(name=name, value=value) for name, value in values.items()}


def test_a_drawn_sketch_beats_the_base_shape_and_reads_the_parameters() -> None:
    """§30.1: die gezeichnete Skizze ersetzt die Grundform, und ihre Maße lesen
    die Projektparameter der Szene — dieselben Werte wie überall (§13). Die
    absurde Grundform daneben stellt sicher, dass wirklich die Skizze rechnet."""
    result = run(
        "sketch_extrude",
        parameters=scene_parameters(width=30.0, height=12.0),
        shape="circle",
        length=999.0,
        height=4.0,
        sketch=drawn_text(),
    )
    assert solid_of(result).volume == pytest.approx(30.0 * 12.0 * 4.0, rel=1e-9)


def test_a_drawn_sketch_revolves_as_drawn() -> None:
    """Bei der Rotation gilt die Skizze wie gezeichnet: x ist der Abstand von
    der Achse, der Abstand-Parameter greift nicht — sonst verschöbe er einen
    Querschnitt, der seinen Ort schon kennt."""
    text = sketch_to_text(
        Sketch(
            plane="plane:xz",
            elements=(
                SketchElement("line", ((10.0, 0.0), (15.0, 0.0))),
                SketchElement("line", ((15.0, 0.0), (15.0, 8.0))),
                SketchElement("line", ((15.0, 8.0), (10.0, 8.0))),
                SketchElement("line", ((10.0, 8.0), (10.0, 0.0))),
            ),
        )
    )
    body = solid_of(run("sketch_revolve", offset=999.0, sketch=text))
    assert body.volume == pytest.approx(math.pi * (15.0**2 - 10.0**2) * 8.0, rel=1e-9)


def test_a_damaged_sketch_text_is_a_correctable_error() -> None:
    with pytest.raises(ValidationError):
        run("sketch_extrude", sketch="{kaputt")


def _document_with(width: float) -> Document:
    return Document(
        format_version=1,
        app_version="0.0.1",
        parameters=scene_parameters(width=width, height=12.0),
        ops=[
            Operation(
                id=1,
                op="sketch_extrude",
                outputs=("obj_1",),
                params={"sketch": drawn_text(), "height": 4.0},
            )
        ],
    )


def test_a_parameter_change_reaches_a_cached_sketch(profile: Profile) -> None:
    """§15: der Cache-Schlüssel deckt alles, wovon das Ergebnis abhängt — auch
    die Werte, die ein Maßausdruck im Skizzentext liest. Ohne sie überlebte
    der alte Körper die Parameteränderung im Cache."""
    cache = ResultCache()
    first = evaluate(_document_with(30.0), profile, cache=cache)
    assert first.complete

    changed = evaluate(_document_with(20.0), profile, cache=cache)
    assert changed.complete
    body = changed.scene.objects["obj_1"].mesh
    assert isinstance(body, Solid)
    assert body.volume == pytest.approx(20.0 * 12.0 * 4.0, rel=1e-9)


# --- Formgebung auf fertigen Körpern --------------------------------------------


def test_the_exact_shell_leaves_exactly_the_wall(  # shell_exact
) -> None:
    result = run("shell_exact", brep_box(), wall=3.0)
    assert solid_of(result).volume == pytest.approx(24000.0 - 34.0 * 24.0 * 17.0, rel=1e-9)


def test_the_exact_thread_is_a_core_plus_a_helical_ridge() -> None:
    """thread_exact: der Gang ist ein echter Sweep, und sein Volumen folgt dem
    verallgemeinerten Pappus — Querschnitt mal Schwerpunktweg der Helix. Die
    Enden werden auf Länge geschnitten und der Fuß sitzt im Kern, darum ist
    die Schranke bewusst weich; die harten Schranken sind die zwei Zylinder."""
    major, pitch, length = 10.0, 1.5, 12.0
    body = solid_of(run("thread_exact", diameter=major, pitch=pitch, length=length))

    ridge = 0.6134 * pitch
    core_radius = major / 2.0 - ridge
    core = math.pi * core_radius**2 * length
    outer = math.pi * (major / 2.0) ** 2 * length
    assert core < body.volume < outer

    helix = (length / pitch) * math.hypot(2.0 * math.pi * core_radius, pitch)
    gang = (pitch * 0.375) * ridge * helix
    assert body.volume - core == pytest.approx(gang, rel=0.2)


def test_the_thread_pitch_needs_a_core() -> None:
    with pytest.raises(ValidationError):
        run("thread_exact", diameter=3.0, pitch=3.0, length=12.0)


def test_the_draft_angle_matches_the_closed_form() -> None:
    """draft_faces: ein Quader mit angestellten Seiten ist ein Integral, das
    man von Hand rechnen kann — V = WDH − (W+D)H²·tanα + 4/3·H³·tan²α."""
    angle = 5.0
    result = run("draft_faces", brep_box(), angle=angle)
    slope = math.tan(math.radians(angle))
    width, depth, height = 40.0, 30.0, 20.0
    expected = (
        width * depth * height
        - (width + depth) * height**2 * slope
        + 4.0 / 3.0 * height**3 * slope**2
    )
    assert solid_of(result).volume == pytest.approx(expected, rel=1e-6)
