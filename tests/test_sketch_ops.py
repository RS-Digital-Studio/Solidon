"""Die Skizzen- und Formgebungs-Operationen (Bauplan §30.1, §40 zu P13).

Jede Operation wird über das Register aufgerufen und gegen eine geschlossene
Formel gemessen — nicht gegen ein selbst erzeugtes Ergebnis. Ein Kreis, der
als exakte Kurve in den Kern geht, trifft π; ein diskretisierter träfe es
nicht. Genau daran erkennt man, dass der Weg stimmt.
"""

from __future__ import annotations

import dataclasses
import math
import sys

import numpy as np
import pytest

from app.core.brep.kernel import Solid, available
from app.core.brep.profiles import _lift_frame
from app.core.errors import AppError, NeedsSolidError, ValidationError
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
    PlaneFrame,
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


def _square(half: float, *, clockwise: bool) -> tuple[SketchElement, ...]:
    """Vier Linien um den Ursprung, links- oder rechtsherum geschlossen."""
    corners = [(-half, -half), (half, -half), (half, half), (-half, half)]
    if clockwise:
        corners = [corners[0], corners[3], corners[2], corners[1]]
    return tuple(SketchElement("line", (corners[i], corners[(i + 1) % 4])) for i in range(4))


@pytest.mark.parametrize("hole_clockwise", [False, True], ids=["Loch-links", "Loch-rechts"])
def test_a_hole_is_subtracted_whichever_way_it_was_drawn(hole_clockwise: bool) -> None:
    """Skizze 1: ein Loch wird abgezogen, egal in welchem Drehsinn es gezeichnet
    wurde.

    ``_face`` drehte jeden Lochring bedingungslos um. Lief er im selben Drehsinn
    wie seine Außenkontur, wurde er dadurch zur zweiten Außenkontur und
    **addiert** statt abgezogen — +67 % Volumen, ohne einen Befund. In der
    Zeichenfläche gibt es kein Rechteckwerkzeug: Ein Umriss entsteht Linie für
    Linie, der Drehsinn ist reiner Zufall der Klickreihenfolge.

    Gemessen: 40 x 40 mit einem Loch 20 x 20, fünf hoch — (1600 − 400) · 5.
    """
    from app.core.types import Sketch

    outline = _square(20.0, clockwise=False) + _square(10.0, clockwise=hole_clockwise)
    sketch = Sketch(plane="plane:xy", elements=outline, constraints=())

    body = solid_of(run("sketch_extrude", sketch=sketch_to_text(sketch), height=5.0))

    assert body.volume == pytest.approx(6000.0, rel=0.001)


# --- Tasche ---------------------------------------------------------------------


def test_a_pocket_follows_the_plane_of_its_sketch() -> None:
    """Auf einer anderen Ebene gezeichnet schnitt die Tasche trotzdem von oben.

    ``sketch_extrude`` liest die Ebene seit seinem Fix; ``sketch_pocket``
    blieb auf Welt-Z (Gesamtreview 25.08.2026, D-2). Eine 10×10-Zeichnung auf
    XZ, durchgehend: Der Kanal läuft entlang Y — Kastenquerschnitt 10 × 5 (nur
    die obere Hälfte der Zeichnung liegt im Körper), mal 30 Tiefe.
    """
    import dataclasses

    from app.core.sketch.serialize import sketch_to_text
    from app.core.sketch.shapes import rectangle as shape_rectangle

    drawn = dataclasses.replace(shape_rectangle(10.0, 10.0), plane="plane:xz")
    result = run("sketch_pocket", brep_box(), sketch=sketch_to_text(drawn), through=True)
    body = solid_of(result)

    assert body.volume == pytest.approx(40.0 * 30.0 * 20.0 - 10.0 * 30.0 * 5.0, rel=1e-6), (
        "der Kanal folgt der Zeichenebene, nicht Welt-Z"
    )


def test_pushing_a_face_keeps_the_features() -> None:
    """„Fläche versetzen" löschte alle Merkmale des Körpers (D-5).

    Mit ``features={}`` hatte der Körper danach keine anklickbaren Flächen
    mehr: „Auf dieser Fläche zeichnen", die exakte Bohrung und jede Passung
    liefen ins Leere — jede andere B-Rep-Op rechnet sie neu.
    """
    result = run("push_face", entry=brep_box(), distance=5.0, nx=1.0, ny=0.0, nz=0.0)

    assert result.outputs[0].features, "der versetzte Körper behält seine Merkmale"


def test_pushing_a_face_past_the_body_says_so() -> None:
    """Ein Weg, der den Körper auslöscht, war ein stummer Schritt (D-6).

    distance = -25 auf einem 20 mm hohen Quader: Volumen null, null Befunde,
    im Verlauf ein Schritt, im Bild nichts. Jetzt ein Satz mit Vorschlag.
    """
    from app.core.errors import GeometryError

    with pytest.raises(GeometryError):
        run("push_face", entry=brep_box(height=20.0), distance=-25.0, nx=0.0, ny=0.0, nz=1.0)


def test_a_spline_over_the_axis_is_refused_with_a_sentence() -> None:
    """Die Achsprüfung von revolve sah Spline-Stützpunkte nicht (D-3).

    Ein Querschnitt, dessen Spline 40 mm über die Drehachse greift, meldete
    als linkeste Stelle 10 — der Kern lief und starb als roher
    ``StdFail_NotDone``, verpackt als „unerwarteter Fehler" samt
    Fehlerbericht, für eine Zeichnung des Kunden.
    """
    from app.core.sketch.serialize import sketch_to_text
    from app.core.types import Sketch, SketchElement

    crossing = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="spline", points=((10.0, 0.0), (-40.0, 5.0), (10.0, 10.0))),
            SketchElement(kind="line", points=((10.0, 10.0), (10.0, 0.0))),
        ),
    )
    with pytest.raises(ValidationError) as caught:
        run("sketch_revolve", sketch=sketch_to_text(crossing))

    assert caught.value.suggestions or str(caught.value.detail), (
        "abgewiesen mit Satz — nicht als roher Kernfehler"
    )


def test_a_loft_keeps_the_drawn_hole() -> None:
    """``loft`` verlor jedes gezeichnete Loch stillschweigend (D-1).

    ``extrude`` daneben hält dieselbe Zusage seit je (its Test steht in
    ``test_sketch.py``): Eine Platte mit Loch hat das Volumen beider. Der
    Übergang bekam den vollen Körper — 16000 statt 15000 mm³, null Befunde.
    """
    import dataclasses

    from app.core.sketch.serialize import sketch_to_text
    from app.core.sketch.shapes import rectangle as shape_rectangle

    outer = shape_rectangle(40.0, 40.0)
    inner = shape_rectangle(10.0, 10.0)
    drawn = dataclasses.replace(outer, elements=outer.elements + inner.elements)

    body = solid_of(run("sketch_loft", sketch=sketch_to_text(drawn), height=10.0, top_scale=1.0))

    assert body.volume == pytest.approx((1600.0 - 100.0) * 10.0, rel=1e-6), (
        "das gezeichnete Loch gehört in den Übergang"
    )


def test_a_pocket_keeps_the_drawn_island() -> None:
    """``sketch_pocket`` fräste die Insel eines gezeichneten Lochs weg.

    Zwilling des Loft-Fundes darüber: ``shifted`` legt jede Region um — auch
    bei 0/0 — und verlor dabei die Löcher; ``scaled`` daneben nimmt sie seit
    je mit. Dieselbe Skizze extrudierte also MIT Loch und schnitt als Tasche
    OHNE — der Rahmen war gemeint, gefräst wurde die volle Fläche.
    """
    import dataclasses

    from app.core.sketch.serialize import sketch_to_text
    from app.core.sketch.shapes import rectangle as shape_rectangle

    outer = shape_rectangle(20.0, 20.0)
    inner = shape_rectangle(10.0, 10.0)
    drawn = dataclasses.replace(outer, elements=outer.elements + inner.elements)

    body = solid_of(run("sketch_pocket", brep_box(), sketch=sketch_to_text(drawn), through=True))

    assert body.volume == pytest.approx(40.0 * 30.0 * 20.0 - (400.0 - 100.0) * 20.0, rel=1e-6), (
        "die Insel des gezeichneten Lochs gehört stehen"
    )


def test_a_sweep_refuses_a_sketch_on_a_foreign_plane() -> None:
    """Der Bogen läuft entlang X und Z — das ist seine Definition.

    Eine Skizze auf einer anderen Ebene wurde stillschweigend wie auf XY
    gerechnet (D-2). Abgelehnt statt übergangen (Regel 21), mit Vorschlag
    (Regel 17).
    """
    import dataclasses

    from app.core.errors import ValidationError
    from app.core.sketch.serialize import sketch_to_text
    from app.core.sketch.shapes import rectangle as shape_rectangle

    drawn = dataclasses.replace(shape_rectangle(10.0, 10.0), plane="plane:yz")
    with pytest.raises(ValidationError) as caught:
        run("sketch_sweep", sketch=sketch_to_text(drawn))

    assert caught.value.suggestions, "eine Absage trägt eine Handlung (Regel 17)"


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
    # ``NeedsSolidError`` und nicht ``ValidationError``: der Titel des einen
    # lautet „Ein Wert liegt außerhalb des zulässigen Bereichs", und hier ist
    # kein Wert außerhalb eines Bereichs — der Körper hat die falsche Art. Im
    # Prüfbericht von ``puppenhaus_fertig`` stand deshalb eine Meldung über
    # Zahlen, wo keine Zahl schuld war.
    with pytest.raises(NeedsSolidError) as raised:
        run("sketch_pocket", entry, shape="rectangle", length=5, width=5, depth=2)
    # Regel 17: der Satz muss einen Weg nennen, nicht nur den Zustand — und
    # der Weg muss es geben. „Exakt aushöhlen" stand hier, bis ``shell_exact``
    # als Zwilling zu ``hollow_object`` zusammengelegt wurde (MENU_TWINS): Der
    # Menüeintrag ist seitdem weg, und ein Vorschlag, der auf ihn zeigt, wäre
    # eine Sackgasse. Genannt wird deshalb der Haken, über den die Operation
    # heute erreichbar ist.
    assert "Flächen und Kanten später bearbeiten" in str(raised.value)


@pytest.mark.parametrize(
    ("title", "params"),
    [
        ("Oberkante unter dem Körper", {"z": -20.0}),
        ("Oberkante an der Unterseite", {"z": -10.0}),
        ("Ort weit daneben", {"x": 200.0}),
        ("Ort knapp daneben", {"x": 40.0}),
    ],
    ids=lambda entry: entry if isinstance(entry, str) else "",
)
def test_a_pocket_that_misses_the_body_says_so(title: str, params: dict[str, float]) -> None:
    """Eine Tasche, die nichts abträgt, lief stumm durch (§2.7).

    Gemessen an der laufenden Oberfläche: vier Fälle, in denen das Volumen
    unverändert blieb, und in allen vieren kein Befund. Im Verlauf stand ein
    Schritt, im Bild dasselbe Teil — und der Nutzer sucht den Fehler in der
    Geometrie statt in der Position. Denselben Satz bekommt seit je, wer eine
    Magnettasche neben den Körper setzt.
    """
    result = run("sketch_pocket", brep_box(), shape="rectangle", length=10, width=10, **params)

    assert solid_of(result).volume == pytest.approx(24000.0), "diese Tasche trägt nichts ab"
    codes = {finding.code for finding in result.findings}
    assert "boolean.without_effect" in codes, f"{title}: stumm geblieben"


def test_a_pocket_that_works_stays_quiet() -> None:
    """Die Gegenprobe: wo etwas abgetragen wird, ist kein Befund fällig."""
    result = run("sketch_pocket", brep_box(), shape="rectangle", length=10, width=10, depth=5)

    assert "boolean.without_effect" not in {finding.code for finding in result.findings}


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


def test_a_drawn_sketch_lofts_to_its_own_scaled_copy() -> None:
    """§30.1: Auch das Aufspannen nimmt die gezeichnete Skizze.

    **Diese Operation hatte als einzige der fünf kein Skizzenfeld** — und der
    Fertig-Dialog des Skizzenmodus bot sie trotzdem an, weil er alle
    Operationen der Kategorie ``sketch`` auflistet. Wer nach dem Zeichnen
    „Zwischen zwei Umrissen aufspannen" wählte, bekam einen ``InternalError``
    (`'sketch_loft' has no sketch parameter`) und seine Zeichnung wurde nicht
    verwendet. Gemessen am gebauten Dialog, nicht vermutet.

    Der obere Umriss ist die um ``top_scale`` verkleinerte Kopie des unteren,
    skaliert **um seinen eigenen Mittelpunkt** — sonst wanderte die Form beim
    Verkleinern zum Ursprung, und aus einem Pyramidenstumpf würde ein
    schiefer Keil. Bei den Grundformen fällt das nicht auf, weil die um den
    Ursprung zentriert sind; eine gezeichnete Skizze liegt irgendwo.

    Die absurde Grundform daneben stellt sicher, dass wirklich die Skizze
    rechnet — dasselbe Muster wie beim Extrudieren darüber.
    """
    lower = 30.0 * 12.0
    upper = lower * 0.5**2
    body = solid_of(
        run(
            "sketch_loft",
            parameters=scene_parameters(width=30.0, height=12.0),
            shape="circle",
            length=999.0,
            height=10.0,
            top_scale=0.5,
            sketch=drawn_text(),
        )
    )
    expected = 10.0 / 3.0 * (lower + upper + math.sqrt(lower * upper))
    assert body.volume == pytest.approx(expected, rel=1e-6)


def test_every_sketch_use_the_dialog_offers_really_takes_a_sketch() -> None:
    """Was der Fertig-Dialog anbietet, muss die Zeichnung auch annehmen.

    Der Dialog listet die Operationen der Kategorie ``sketch`` — er fragt
    nicht, ob sie ein Skizzenfeld haben. ``sketch_loft`` hatte keines, und
    damit endete eine von fünf Verwendungen in einem internen Fehler statt in
    einem Körper.

    Der Test steht hier und nicht in der Oberfläche, weil die **Ursache** im
    Register liegt: Eine Operation, die als Verwendung einer Skizze im Menü
    steht, ohne eine annehmen zu können, ist im Register falsch — nicht im
    Dialog, der sie treu wiedergibt.
    """
    uses = [spec for spec in REGISTRY.all() if spec.category == "sketch"]
    assert len(uses) >= 5, "ohne geladenes Register prüft diese Zählung nichts"

    ohne = [
        spec.name
        for spec in uses
        if not any(entry.kind == "sketch" for entry in spec.params.spec())
    ]
    assert not ohne, (
        f"diese Verwendungen stehen im Fertig-Dialog und nehmen keine Skizze an: {ohne}"
    )


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


def test_the_exact_thread_is_offered_as_a_screw() -> None:
    """Der Außengang war vorhanden, für Einsteiger aber nur als Bolzen lesbar."""
    assert str(REGISTRY.get("thread_exact").title) == "Schraube erstellen"


def test_the_thread_pitch_needs_a_core() -> None:
    with pytest.raises(ValidationError):
        run("thread_exact", diameter=3.0, pitch=3.0, length=12.0)


def test_a_rod_that_did_not_close_is_refused_instead_of_handed_over() -> None:
    """Ein offener Bolzen wird abgelehnt, nicht herausgegeben.

    Er trägt weder den STEP-Export noch eine weitere Operation; bei 100 mm und
    1 mm Steigung kam einmal einer mit null Volumen und null Komponenten
    heraus, und keiner sagte etwas.

    **Geprüft wird die Zusage, nicht ein Maß.** Hier stand ``diameter=100``,
    weil ab 50 mm nie ein geschlossener Körper herauskam — seit der Gang einen
    Sockel im Kern hat, kommt einer, und der Test prüfte damit eine Absage, die
    es zu Recht nicht mehr gibt. Was bleiben muss, ist die Grenze selbst: Was
    nicht geschlossen ist, geht nicht hinaus. Also bekommt ``_checked_rod``
    zwei Zylinder, die einander nicht berühren — zwei Komponenten, wie sie
    keine Vereinigung der Welt zusammenbringt.
    """
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep import profiles

    near = Solid(BRepPrimAPI_MakeCylinder(3.0, 12.0).Shape())
    far = Solid(
        BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(50.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0)), 3.0, 12.0
        ).Shape()
    )
    apart = profiles._fuzzy_boolean("union", near, far)
    assert apart.component_count == 2, "ohne zwei Stücke prüft dieser Test nichts"

    with pytest.raises(AppError) as raised:
        profiles._checked_rod(apart, 6.0, 1.0)

    assert raised.value.suggestions


def test_a_fine_pitch_yields_a_sound_rod_and_a_tight_mesh() -> None:
    """Eine feine Steigung auf einem großen Durchmesser — der schwerste Fall.

    Hier stand die Erwartung, dass er abgelehnt wird: „ergibt neunzehn
    Bruchstücke". Beides ist überholt. Der Sockel im Kern hat die
    Durchdringung so tief gemacht wie den Gang hoch, und die Vernetzung folgt
    seit dem 20.08.2026 der Steigung statt einer festen Feinheit.

    Geprüft wird deshalb beides, und zwar getrennt: der **Körper** (geschlossen,
    ein Stück, Volumen zwischen Kern und Hülle) und sein **Netz**. Ein
    Viertelmillimeter Steigung war genau der Fall, in dem die
    Standardfeinheit von 0,05 mm die Flanke aufriss — der Körper trug den
    STEP-Export, das STL daneben hatte Löcher. Zwei Fragen an zwei Dinge, und
    bis dahin beantwortete eine Prüfung sie beide falsch.
    """
    body = solid_of(run("thread_exact", diameter=10.0, pitch=0.25, length=12.0))

    ridge = 0.6134 * 0.25
    core = math.pi * (10.0 / 2.0 - ridge) ** 2 * 12.0
    hull = math.pi * 5.0**2 * 12.0

    assert body.is_closed, "die Hülle ist offen"
    assert body.solid_count == 1, f"{body.solid_count} Körper statt einem"
    assert core <= body.volume <= hull, f"{body.volume:.1f} mm³ liegt nicht zwischen Kern und Hülle"
    assert body.is_watertight, "der Körper trägt, sein Netz nicht — das STL bekäme Löcher"


def test_a_thread_keeps_the_diameter_it_was_asked_for() -> None:
    """M2 mit 1,5 mm Steigung ergab einen Bolzen von 0,16 mm.

    Die Kernprüfung fragte nur, ob überhaupt ein Kern übrig bleibt — bei 2 mm
    Außendurchmesser und 1,5 mm Steigung sind das 0,08 mm, formal mehr als
    null und praktisch kein Bolzen. Herausgekommen ist ein Faden, der den
    versprochenen Durchmesser um den Faktor zwölf verfehlt.
    """
    with pytest.raises(ValidationError):
        run("thread_exact", diameter=2.0, pitch=1.5, length=12.0)


@pytest.mark.xfail(
    sys.platform.startswith(("linux", "darwin")),
    reason=(
        "Auf der OCCT-Version der Linux- und macOS-Runner schließt der helikale "
        "Gang nicht am Kern — auch nicht mit ShapeFix und nicht über drei "
        "Fuzzy-Toleranzen hinweg (gemessen am 13.08.2026, siehe ROADMAP). Unter "
        "Windows, der Plattform der Demo, kommt M6 geschlossen heraus. Nicht "
        "`strict`: sobald eine Version es dort kann, ist der Lauf grün und diese "
        "Marke fällt.\n\n"
        "macOS kam am 20.08.2026 dazu, und zwar nicht als neuer Befund: Bis zur "
        "Reparatur des Testschritts brach der Lauf dort an `xvfb-run` ab, das es "
        "auf macOS nicht gibt — die Tests wurden nie erreicht. Der erste Lauf, "
        "der sie erreichte, meldete dieselbe Zeile mit denselben Maßen (M6, "
        "1,0 mm) wie Linux, zweimal hintereinander. Dieselbe Rechnung, dieselbe "
        "fremde OCCT-Version."
    ),
    strict=False,
)
def test_a_sound_thread_still_goes_through() -> None:
    """Die Gegenprobe — die üblichen Maße dürfen die Prüfung nicht treffen.

    Der **Körper** wird überall verlangt: geschlossen, ein Stück, im Maß. Das
    **Netz** nur dort, wo die Vernetzung es hergibt. Auf dem macOS-Runner
    bleibt M6 mit einem Millimeter Steigung undicht, auch nachdem die Feinheit
    dreimal halbiert wurde — dort ritzt die Tessellation der Flanke, und
    Verfeinern hilft nicht. Auf dieser Maschine und unter Linux sind alle drei
    Größen dicht.

    Die Lücke ist damit benannt und nicht versteckt: Ein Gewinde, das auf
    einem Mac als STL exportiert wird, kann Löcher haben; STEP und jede
    weitere Operation tragen es trotzdem, denn die hängen am Körper. Der
    offene Punkt steht in ROADMAP.md.
    """
    for major, pitch in ((6.0, 1.0), (10.0, 1.5), (20.0, 2.5)):
        body = solid_of(run("thread_exact", diameter=major, pitch=pitch, length=12.0))
        assert body.is_closed, (major, pitch)
        assert body.solid_count == 1, (major, pitch)
        assert body.bounds.size[0] == pytest.approx(major, rel=0.01)
        if sys.platform != "darwin":
            assert body.is_watertight, (major, pitch)


def test_a_thread_holds_more_material_than_its_core() -> None:
    """Ein Gewindebolzen liegt zwischen zwei Zylindern, und beide kann man
    ausrechnen: Weniger Material als sein **Kern** kann er nicht haben, mehr
    als seine **Hülle** auch nicht.

    Die Schranke steht hier, weil der Test darüber sie nicht hat. Wasserdicht
    und außen sechs Millimeter war ein Gewinde auch dann noch, als der Gang in
    den Kern hineinschnitt statt darauf zu liegen: Am 20.08.2026 lieferte der
    Kandidat ``SetMode(gp_Ax2)`` für alle drei Größen ein Volumen **unter** dem
    Kernvolumen — wasserdicht, eine Komponente, richtiges Hüllmaß, und
    geometrisch unmöglich. Die Hülle zu prüfen sagt nichts über das Material
    darin.

    Der Kerndurchmesser folgt ISO 68-1: ``d3 = d − 1,0825 · P``.
    """
    for major, pitch in ((6.0, 1.0), (10.0, 1.5), (20.0, 2.5)):
        body = solid_of(run("thread_exact", diameter=major, pitch=pitch, length=12.0))
        core = math.pi * ((major - 1.0825 * pitch) / 2.0) ** 2 * 12.0
        hull = math.pi * (major / 2.0) ** 2 * 12.0
        assert core <= body.volume <= hull, (
            f"M{major:.0f}: {body.volume:.1f} mm³ liegt nicht zwischen "
            f"Kern {core:.1f} und Hülle {hull:.1f}"
        )


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


def test_an_object_qualified_face_does_not_pick_the_first_duplicate() -> None:
    """Flächenkennungen sind nur innerhalb eines Körpers eindeutig.

    Beide Quader haben ``face_2``. Die neue Ebenenangabe benennt den zweiten
    Körper mit und muss deshalb dessen Lage liefern; die alte Angabe darunter
    bleibt für bestehende Projekte weiterhin lesbar.
    """
    first = brep_box(width=40.0)
    first.id = "obj_a"
    second = brep_box(width=60.0)
    second.id = "obj_b"

    exact = frame_for("feature:obj_b:face_2", [first, second])
    legacy = frame_for("feature:face_2", [first, second])

    assert exact.origin[0] == pytest.approx(30.0), "der ausdrücklich benannte Körper zählt"
    assert legacy.origin[0] == pytest.approx(20.0), "alte Projekte behalten ihre Lesart"


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


def test_a_vanished_target_face_blames_the_up_to_field() -> None:
    """Der Fehler zeigt auf das Feld, in dem der Fehler steht.

    Die Zielfläche gehört zum Feld ``up_to``, nicht zur Skizzenebene — vorher
    nannte der Fehler ``plane`` und riet „Auf einer der drei Grundebenen
    zeichnen", und beides führte den Kunden vom richtigen Feld weg: gezeichnet
    war längst, nur das Ziel der Höhe war weg.
    """
    box = brep_box()
    with pytest.raises(ValidationError) as caught:
        run("sketch_extrude", box, shape="rectangle", length=10, width=10, up_to="face_99")
    assert caught.value.field == "up_to"
    advice = [str(action.label) for action in caught.value.suggestions]
    assert advice, "der Fehler muss Vorschläge tragen"
    assert not any("Grundebenen" in line for line in advice)


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


def test_a_bodiless_result_is_a_sentence_not_an_object() -> None:
    """Ein Ergebnis ohne Körper wird abgewiesen, wo es entsteht.

    Alle vier Erzeuger-Ops laufen durch ``_created`` — kommt dort nichts an
    (kein Solid, Volumen null), stand vorher trotzdem ein Objekt in der
    Szene: unsichtbar, Volumen null, und jeder spätere Schritt darauf
    scheiterte weit weg von der Ursache.
    """
    from app.core.brep import edit
    from app.core.errors import GeometryError
    from app.core.sketch.ops import _created

    small = brep_box(10.0, 10.0, 10.0).mesh
    big = brep_box(40.0, 40.0, 40.0).mesh
    gone = edit.boolean("difference", [small, big])
    with pytest.raises(GeometryError) as caught:
        _created("", "x", gone)
    assert caught.value.suggestions


def test_a_pocket_cuts_every_drawn_region() -> None:
    """Zwei Taschen in einer Zeichnung sind eine Handlung, nicht zwei.

    Das Extrudieren nimmt seit je alle Umrisse; die Tasche lehnte dieselbe
    Zeichnung ab — dieselbe Skizze war je nach Werkzeug richtig oder falsch.
    Jetzt schneidet sie jeden Umriss, und die Regionsnummer wählt wie dort.
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

    drawn = Sketch(plane="plane:xy", elements=square(5.0, (-10.0, 0.0)) + square(5.0, (10.0, 0.0)))
    box = brep_box()  # 40 x 30 x 20
    both = run("sketch_pocket", box, sketch=sketch_to_text(drawn), depth=5.0)
    assert solid_of(both).volume == pytest.approx(24000.0 - 2.0 * 25.0 * 5.0, rel=1e-6)

    single = run("sketch_pocket", box, sketch=sketch_to_text(drawn), depth=5.0, region=1)
    assert solid_of(single).volume == pytest.approx(24000.0 - 25.0 * 5.0, rel=1e-6)


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


def test_lifting_a_drawing_point_keeps_the_order_of_the_axes() -> None:
    """Der Zeichenpunkt darf beim Weg nach OpenCASCADE nicht verrutschen.

    ``_lift_frame`` rechnet seit dem Umzug nach ``planes.to_world`` nicht mehr
    selbst; es hüllt das Ergebnis nur noch in ein ``gp_Pnt``. Genau dort kann
    eine Komponente vertauschen, ohne dass es auffällt — auf einer Hauptebene
    sähe (x, y, z) auch dann richtig aus, wenn zwei Achsen getauscht wären.

    Der Rahmen hier ist deshalb absichtlich gedreht: erste Achse nach +Y,
    zweite nach +Z, Ursprung abseits von null. Damit landet jede der drei
    Komponenten woanders, als sie im Zeichenpunkt stand.

    **Und die drei erwarteten Zahlen sind paarweise verschieden.** Der erste
    Entwurf dieses Tests erwartete (7, 2, 7) — zwei gleiche Werte, und die
    Vertauschung von X und Z wäre unbemerkt durchgelaufen. Ein Test gegen
    Verwechslung braucht Zahlen, die sich verwechseln ließen.
    """
    frame = PlaneFrame(
        origin=(4.0, -1.0, 2.0),
        x_axis=(0.0, 1.0, 0.0),
        y_axis=(0.0, 0.0, 1.0),
        normal=(1.0, 0.0, 0.0),
    )
    lifted = _lift_frame(frame)((3.0, 5.0))
    assert (lifted.X(), lifted.Y(), lifted.Z()) == pytest.approx((4.0, 2.0, 7.0))


def test_the_width_of_a_revolved_polygon_does_nothing_and_the_schema_says_so() -> None:
    """Ein Feld, das nichts tut, darf nicht bedienbar dastehen.

    ``_sketch_profile`` baut das Vieleck aus ``length`` und ``corners``; die
    Breite sieht es nicht. Und der Versatz zur Achse nimmt bei Kreis **und**
    Vieleck ``length / 2``, nicht ``width / 2`` — die Angabe wirkt also in
    keinem der beiden Zweige.

    Geprüft wird die **Wirkung** und daneben, dass das Schema sie richtig
    ausweist. Nur die Liste festzunageln wäre ein Ist-Zustand-Test: Er wäre
    auch grün, wenn beides gemeinsam falsch stünde — und genau so stand es
    hier, mit einem Kommentar daneben, der die Wirkung behauptete.
    """
    narrow = solid_of(
        run("sketch_revolve", shape="polygon", length=20, width=5, corners=6, offset=10, angle=360)
    )
    wide = solid_of(
        run("sketch_revolve", shape="polygon", length=20, width=20, corners=6, offset=10, angle=360)
    )
    assert narrow.volume == pytest.approx(wide.volume), "die Breite tut beim Vieleck nichts"

    # Die Gegenprobe: beim Rechteck wirkt sie, sonst prüfte der Test oben nur,
    # dass zwei gleiche Aufrufe gleich ausgehen.
    thin = solid_of(run("sketch_revolve", shape="rectangle", length=20, width=5, offset=10))
    thick = solid_of(run("sketch_revolve", shape="rectangle", length=20, width=20, offset=10))
    assert thick.volume > thin.volume * 3.0, "beim Rechteck wirkt sie sehr wohl"

    entry = next(e for e in REGISTRY.get("sketch_revolve").params.spec() if e.name == "width")
    assert entry.depends_on is not None
    assert "polygon" not in entry.depends_on[1], "und das Schema weist sie nicht als wirksam aus"
