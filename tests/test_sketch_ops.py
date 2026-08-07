"""Die Skizzen- und Formgebungs-Operationen (Bauplan §30.1, §40 zu P13).

Jede Operation wird über das Register aufgerufen und gegen eine geschlossene
Formel gemessen — nicht gegen ein selbst erzeugtes Ergebnis. Ein Kreis, der
als exakte Kurve in den Kern geht, trifft π; ein diskretisierter träfe es
nicht. Genau daran erkennt man, dass der Weg stimmt.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from app.core.brep.kernel import Solid, available
from app.core.errors import ValidationError
from app.core.registry import REGISTRY
from app.core.scene import ResultCache, evaluate
from app.core.scene.cancel import NeverCancelled
from app.core.sketch import shapes
from app.core.sketch.planes import frame_for
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


def test_a_drawn_sketch_cuts_a_pocket_where_x_and_y_say() -> None:
    """Die Skizze ersetzt nur die Grundform — alles andere gilt weiter:
    x und y verschieben auch den gezeichneten Umriss."""
    result = run(
        "sketch_pocket",
        brep_box(),
        parameters=scene_parameters(width=10.0, height=8.0),
        shape="circle",
        length=999.0,
        depth=5.0,
        x=-5.0,
        y=-4.0,
        sketch=drawn_text(),
    )
    assert solid_of(result).volume == pytest.approx(24000.0 - 10.0 * 8.0 * 5.0, rel=1e-9)


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


# --- die Ebene der Skizze (§30.1) ------------------------------------------------


def test_a_sketch_is_extruded_along_the_normal_of_its_plane() -> None:
    """``Sketch.plane`` ist ein Vertrag, kein Feld zum Anschauen.

    §30.1 nennt vier Ebenen — die drei Hauptebenen und eine angeklickte
    planare Fläche. Der Typ deklariert sie, das Dateiformat speichert sie, und
    bis hierher **las sie niemand**: jede Skizze lag auf XY, gleichgültig, was
    dastand. Ein Feld, das man setzen kann und das nichts tut, ist schlimmer
    als keines — es sieht aus wie eine Zusage.

    Gemessen wird an der Hüllbox, nicht am Volumen: ein Quader hat auf jeder
    Ebene dasselbe Volumen, und genau deshalb hätte ein Volumentest den Fehler
    nie gefunden.
    """
    from dataclasses import replace

    from app.core.sketch import shapes

    flat = shapes.rectangle(40.0, 20.0)
    upright = replace(flat, plane="plane:xz")

    on_xy = solid_of(run("sketch_extrude", sketch=sketch_to_text(flat), height=10.0))
    on_xz = solid_of(run("sketch_extrude", sketch=sketch_to_text(upright), height=10.0))

    assert on_xy.volume == pytest.approx(on_xz.volume, rel=1e-9), (
        "dasselbe Rechteck, dieselbe Menge"
    )

    assert on_xy.bounds.size == pytest.approx((40.0, 20.0, 10.0), abs=1e-6)
    # Auf XZ liegt die Skizzenbreite in Z, und aufgezogen wird nach Y.
    assert on_xz.bounds.size == pytest.approx((40.0, 10.0, 20.0), abs=1e-6)


# --- Fläche versetzen (Konzept P15 §7 Etappe 6, D10) ----------------------------


def test_pushing_a_face_moves_the_wall_and_the_neighbours_follow() -> None:
    """Press/Pull: eine Fläche greifen und versetzen, ohne den Rest neu zu
    zeichnen.

    Das Standardwerkzeug jedes CAD, und Solidon hatte es nicht: eine Wand
    zwei Millimeter herauszuziehen hieß, die Operation zu suchen, die sie
    erzeugt hat, und ihre Zahl zu ändern — wenn es eine gab. Bei einem
    importierten STEP gibt es keine.

    Gemessen an der Hüllbox: der Quader wird in genau einer Achse länger, und
    die Nachbarwände wachsen mit, statt eine Lücke zu lassen.
    """
    if not available():
        pytest.skip("ohne B-Rep-Kern gibt es keine Flächen zum Greifen")

    entry = brep_box(width=40.0, depth=30.0, height=20.0)
    before = entry.mesh.bounds.size

    result = run("push_face", entry=entry, distance=5.0, nx=1.0, ny=0.0, nz=0.0)

    after = solid_of(result).bounds.size
    assert after[0] == pytest.approx(before[0] + 5.0, abs=1e-6), "in X fünf länger"
    assert after[1] == pytest.approx(before[1], abs=1e-6), "in Y unverändert"
    assert after[2] == pytest.approx(before[2], abs=1e-6), "in Z unverändert"
    assert solid_of(result).volume > entry.mesh.volume


def test_pulling_a_face_inwards_removes_material() -> None:
    """Ein negativer Weg zieht die Wand hinein — dasselbe Werkzeug."""
    if not available():
        pytest.skip("ohne B-Rep-Kern gibt es keine Flächen zum Greifen")

    entry = brep_box(width=40.0, depth=30.0, height=20.0)

    result = run("push_face", entry=entry, distance=-5.0, nx=1.0, ny=0.0, nz=0.0)

    assert solid_of(result).bounds.size[0] == pytest.approx(35.0, abs=1e-6)
    assert solid_of(result).volume < entry.mesh.volume


def test_pushing_a_face_by_nothing_is_a_user_error() -> None:
    """Null Weg ist keine Bewegung, sondern ein vergessener Wert."""
    if not available():
        pytest.skip("ohne B-Rep-Kern gibt es keine Flächen zum Greifen")

    with pytest.raises(ValidationError):
        run("push_face", entry=brep_box(), distance=0.0, nx=1.0, ny=0.0, nz=0.0)


# --- Skizzenebene aus einer Fläche (§30.1, Konzept P15 D9) ----------------------


def sketch_on(plane: str, size: float = 10.0) -> str:
    """Ein Quadrat auf der genannten Ebene, als Skizzentext."""
    drawn = dataclasses.replace(shapes.rectangle(size, size), plane=plane)
    return sketch_to_text(drawn)


def test_frame_of_a_face_points_away_from_the_body() -> None:
    """Die Normale einer Fläche zeigt nicht verlässlich nach außen.

    OpenCASCADE führt sie als Achsenrichtung der Ebene, und die hängt an der
    Orientierung der Fläche im Körper: der Quader oben meldet für die Fläche
    bei x = −20 die Richtung +X, also nach innen. Wer darauf extrudiert, baut
    in den Körper hinein. Der Rahmen richtet sie deshalb am Körper aus — und
    das ist der Grund, warum es diesen Test gibt.
    """
    box = brep_box()
    away = frame_for("feature:face_1", [box])
    assert away.origin == pytest.approx((-20.0, 0.0, 10.0))
    assert away.normal == pytest.approx((-1.0, 0.0, 0.0))

    other = frame_for("feature:face_2", [box])
    assert other.normal == pytest.approx((1.0, 0.0, 0.0))


def test_frame_axes_are_orthonormal_and_right_handed() -> None:
    """Sonst verzerrt die Skizze — und zwar unauffällig.

    Eine schiefe zweite Achse liefert immer noch einen Körper, nur eben einen
    falschen. Die Probe ist billig, der Fehler wäre teuer.
    """
    box = brep_box()
    for name in ("face_1", "face_3", "face_6"):
        frame = frame_for(f"feature:{name}", [box])
        x_axis = np.asarray(frame.x_axis)
        y_axis = np.asarray(frame.y_axis)
        normal = np.asarray(frame.normal)
        assert float(np.linalg.norm(x_axis)) == pytest.approx(1.0)
        assert float(np.linalg.norm(y_axis)) == pytest.approx(1.0)
        assert float(x_axis @ y_axis) == pytest.approx(0.0, abs=1e-9)
        assert np.cross(x_axis, y_axis) == pytest.approx(normal)


def test_the_top_face_matches_the_global_plane() -> None:
    """Eine waagerechte Fläche darf nichts drehen.

    Wäre die erste Achse anders gewählt, käme dieselbe Skizze auf derselben
    Höhe gedreht heraus — und niemand wüsste, warum.
    """
    frame = frame_for("feature:face_6", [brep_box()])
    assert frame.x_axis == pytest.approx((1.0, 0.0, 0.0))
    assert frame.y_axis == pytest.approx((0.0, 1.0, 0.0))
    assert frame.normal == pytest.approx((0.0, 0.0, 1.0))


def test_extruding_on_a_face_grows_away_from_it() -> None:
    """Der eigentliche Zweck: ein Klotz auf der Seitenwand, nicht darin.

    Zehn auf zehn, fünf hoch, auf der Fläche bei x = +20 — der Körper muss bei
    genau 20 anfangen und bei 25 aufhören. Das Volumen prüft mit, dass die
    Skizze dabei nicht verzerrt wurde.
    """
    box = brep_box()
    result = run(
        "sketch_extrude", box, sketch=sketch_on("feature:face_2"), height=5.0, name="Klotz"
    )
    body = solid_of(result)
    assert body.volume == pytest.approx(500.0, rel=1e-6)
    low, high = body.bounds.minimum, body.bounds.maximum
    assert low[0] == pytest.approx(20.0)
    assert high[0] == pytest.approx(25.0)
    # Auf der Fläche zentriert, nicht am Weltursprung: die Skizze liegt im
    # Rahmen der Fläche, und deren Mitte ist (20, 0, 10).
    assert (low[1] + high[1]) / 2.0 == pytest.approx(0.0, abs=1e-6)
    assert (low[2] + high[2]) / 2.0 == pytest.approx(10.0, abs=1e-6)


def test_an_unknown_face_says_which_ones_exist() -> None:
    """Regel 17: der Fehler nennt einen Weg weiter.

    Eine Fläche kann verschwinden, weil eine Operation davor sie verschluckt
    hat — dann ist die Skizze nicht falsch, sondern verwaist, und der Nutzer
    braucht die Liste dessen, was jetzt da ist.
    """
    with pytest.raises(ValidationError) as caught:
        frame_for("feature:face_99", [brep_box()])
    assert caught.value.suggestions


# --- Extrudieren bis zu einer Fläche (D14) --------------------------------------


def test_extruding_up_to_a_face_takes_its_height_from_there() -> None:
    """Die Höhe steht dann nicht mehr im Dialog, sondern im Körper.

    Zwanzig Millimeter abzumessen und einzutippen ist die Art Arbeit, die eine
    Anwendung übernehmen soll: die Oberseite des Quaders liegt bei z = 20, also
    ist die Höhe 20 — und sie bleibt es, wenn der Quader morgen 25 hoch ist.
    """
    box = brep_box()
    result = run("sketch_extrude", box, shape="rectangle", length=10, width=10, up_to="face_6")
    body = solid_of(result)
    assert body.volume == pytest.approx(100.0 * 20.0, rel=1e-6)
    assert body.bounds.maximum[2] == pytest.approx(20.0)


def test_a_target_parallel_to_the_direction_is_refused() -> None:
    """Eine Wand, an der man entlangfährt, wird nie erreicht.

    Ohne diese Prüfung käme eine Division durch beinahe null heraus und daraus
    ein Körper von einigen Kilometern Höhe — rechnerisch erklärbar, als
    Antwort auf „bis zu dieser Fläche" aber unbrauchbar.
    """
    box = brep_box()
    with pytest.raises(ValidationError) as caught:
        run("sketch_extrude", box, shape="rectangle", length=10, width=10, up_to="face_2")
    assert caught.value.suggestions


def test_a_target_behind_the_sketch_is_refused() -> None:
    """Nach unten extrudieren heißt, die Skizze auf die andere Fläche zu legen.

    Eine negative Höhe stillschweigend als positive zu lesen, baute den Körper
    in die falsche Richtung; sie durchzulassen, baute ihn rückwärts durch die
    Skizze. Beides wäre eine Antwort auf eine Frage, die niemand gestellt hat.
    """
    box = brep_box(height=20.0)
    with pytest.raises(ValidationError) as caught:
        run(
            "sketch_extrude",
            box,
            shape="rectangle",
            length=10,
            width=10,
            sketch=sketch_on("feature:face_6"),
            up_to="face_5",
        )
    assert caught.value.suggestions


def test_two_regions_become_one_body() -> None:
    """Zwei Stege nebeneinander sind eine Handlung, nicht zwei.

    Die Vorgabe nimmt alle Umrisse und vereinigt sie. Ohne das brauchte ein
    Halter aus zwei Stegen zwei Operationen und eine Vereinigung — drei
    Einträge im Stapel für etwas, das in einer Zeichnung steht.
    """
    from app.core.types import SketchElement

    def square(size: float, at: tuple[float, float]) -> tuple[SketchElement, ...]:
        half = size / 2.0
        x, y = at
        corners = [
            (x - half, y - half),
            (x + half, y - half),
            (x + half, y + half),
            (x - half, y + half),
        ]
        return tuple(
            SketchElement(kind="line", points=(corners[i], corners[(i + 1) % 4])) for i in range(4)
        )

    drawn = Sketch(
        plane="plane:xy", elements=square(10.0, (-20.0, 0.0)) + square(10.0, (20.0, 0.0))
    )
    both = run("sketch_extrude", sketch=sketch_to_text(drawn), height=4.0)
    assert solid_of(both).volume == pytest.approx(2.0 * 100.0 * 4.0, rel=1e-6)

    single = run("sketch_extrude", sketch=sketch_to_text(drawn), height=4.0, region=1)
    assert solid_of(single).volume == pytest.approx(100.0 * 4.0, rel=1e-6)


def test_asking_for_a_region_that_is_not_there_says_how_many_are() -> None:
    """Regel 17: der Fehler nennt die Zahl, nach der niemand fragen musste."""
    with pytest.raises(ValidationError) as caught:
        run(
            "sketch_extrude",
            shape="rectangle",
            length=10,
            width=10,
            region=7,
            sketch=sketch_on("plane:xy"),
        )
    assert caught.value.suggestions
    assert caught.value.values.get("regions") == 1
