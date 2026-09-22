"""Wo eine Skizze liegen darf — der Ebenenvertrag (Bauplan §30.1, RM-188 P3.1).

Drei Ebenen sind fest, die vierte ist eine Fläche des Modells, und seit dem
22.09.2026 gibt es drei abgeleitete: parallel versetzt, gekippt, durch drei
Punkte. Sie gehören **der Skizze**, die sie benutzt, und stehen in keinem
Objektbaum (Konzept-Entscheidung 6) — deshalb sind sie eine Zeichenkette im
Parameter und kein Szenenobjekt.

Geprüft wird hier, was der Vertrag verspricht: dass die Schreibweise eindeutig
lesbar ist, auch wenn die Basis selbst Doppelpunkte trägt; dass ein Maß ein
Projektparameter sein darf; dass die Rundreise durch die Projektdatei nichts
verliert; und dass jede alte Ebenenangabe weiter gilt.
"""

from __future__ import annotations

import math

import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.scene.orphans import feature_ref_of_sketch
from app.core.sketch.planes import (
    BASE_FRAMES,
    MAX_PLANE_DEPTH,
    OffsetPlane,
    ThroughPlane,
    TiltPlane,
    derived_plane,
    feature_plane,
    frame_for_plane,
    frame_for_sketch,
    is_derived_plane,
    offset_plane,
    standing_on_feature,
    through_plane,
    tilt_plane,
    to_world,
)
from app.core.sketch.serialize import (
    sketch_from_text,
    sketch_parameter_references,
    sketch_to_text,
)
from app.core.types import (
    Feature,
    OpContext,
    Parameter,
    Scene,
    SceneObject,
    Sketch,
    SketchElement,
    Vec3,
)


def _plate(normal: Vec3 = (0.0, 0.0, 1.0), centre: Vec3 = (0.0, 0.0, 8.0)) -> SceneObject:
    """Ein Körper mit genau einer erkannten Fläche, auf der sich zeichnen lässt."""
    return SceneObject(
        id="obj_1",
        name="Platte",
        mesh=trimesh.creation.box(extents=(40.0, 40.0, 16.0)),
        features={
            "face_1": Feature(
                id="face_1",
                kind="face",
                params={"normal": normal, "centre": centre},
                provenance="detected",
            )
        },
    )


def _length(vector: Vec3) -> float:
    return math.sqrt(sum(value * value for value in vector))


# --- Die Schreibweise ist eindeutig lesbar --------------------------------------


def test_a_flat_plane_is_not_derived() -> None:
    """Grundebene und Fläche bleiben, was sie waren."""
    assert not is_derived_plane("plane:xy")
    assert not is_derived_plane(feature_plane("obj_1", "face_1"))
    assert derived_plane("plane:xy") is None
    assert derived_plane(feature_plane("obj_1", "face_1")) is None


def test_an_offset_reads_its_base_even_when_the_base_carries_colons() -> None:
    """``feature:<obj>:<face>`` hat selbst zwei Doppelpunkte — gelesen wird von hinten.

    Das ist der Grund für die Reihenfolge im Format: Von vorn wäre nicht zu
    entscheiden, wo die Basis aufhört und der Abstand anfängt.
    """
    written = offset_plane(feature_plane("obj_1", "face_1"), 20.0)
    described = derived_plane(written)

    assert described == OffsetPlane(base="feature:obj_1:face_1", distance="20.0")


def test_a_measure_may_be_a_project_parameter() -> None:
    """Ein Abstand darf ein Maßausdruck aus §13 sein — sie tragen keinen Doppelpunkt."""
    assert derived_plane(offset_plane("plane:xy", "@wand")) == OffsetPlane(
        base="plane:xy", distance="@wand"
    )
    assert derived_plane(offset_plane("plane:xy", "=@wand * 2 + 1")) == OffsetPlane(
        base="plane:xy", distance="=@wand * 2 + 1"
    )


def test_a_tilt_reads_base_axis_and_angle() -> None:
    assert derived_plane(tilt_plane("plane:xy", "x", 30.0)) == TiltPlane(
        base="plane:xy", axis="x", angle="30.0"
    )


def test_three_points_read_as_three_points() -> None:
    described = derived_plane(through_plane([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)]))

    assert isinstance(described, ThroughPlane)
    assert described.points[1] == (10.0, 0.0, 0.0)


@pytest.mark.parametrize(
    "written",
    [
        "offset:plane:xy",
        "offset::20",
        "tilt:plane:xy:30",
        "tilt:plane:xy:z:30",
        "through:0,0,0;10,0,0",
        "through:0,0;10,0,0;0,10,0",
        "through:a,b,c;10,0,0;0,10,0",
    ],
)
def test_an_unreadable_plane_says_so_with_a_way_out(written: str) -> None:
    """Regel 17: Eine Skizze, deren Ebene niemand versteht, liegt sonst irgendwo."""
    with pytest.raises(ValidationError) as problem:
        derived_plane(written)

    assert problem.value.suggestions, "an unreadable plane must offer a way out"


# --- Die Rahmen liegen, wo sie sollen -------------------------------------------


def test_an_offset_moves_along_the_normal_and_keeps_the_axes() -> None:
    """Die Zeichnung liegt auf der versetzten Ebene gleich herum wie auf der Basis."""
    base = BASE_FRAMES["plane:xy"]
    frame = frame_for_plane(offset_plane("plane:xy", 20.0))

    assert frame is not None
    assert frame.origin == pytest.approx((0.0, 0.0, 20.0))
    assert frame.x_axis == pytest.approx(base.x_axis)
    assert frame.y_axis == pytest.approx(base.y_axis)
    assert frame.normal == pytest.approx(base.normal)


def test_an_offset_on_a_face_starts_at_the_face() -> None:
    """Der Bezug ist die Fläche des Körpers, nicht der Weltnullpunkt.

    Das ist der Unterschied zu ``sketch_pocket.z``, das es schon gibt: Dort
    steht eine absolute Höhe, hier ein Abstand zu einer Fläche, die sich mit
    dem Körper mitbewegt.
    """
    plane = offset_plane(feature_plane("obj_1", "face_1"), 5.0)
    frame = frame_for_plane(plane, [_plate()])

    assert frame is not None
    assert frame.origin == pytest.approx((0.0, 0.0, 13.0))


def test_an_offset_reads_the_project_parameter() -> None:
    frame = frame_for_plane(offset_plane("plane:xy", "=@wand * 2"), (), {"wand": 3.0})

    assert frame is not None
    assert frame.origin == pytest.approx((0.0, 0.0, 6.0))


def test_an_offset_without_the_parameters_draws_nothing_rather_than_guessing() -> None:
    """Eine Ansicht ohne Parameter schweigt; eine Operation ohne sie sagt es.

    Der Unterschied ist die Rolle des Aufrufers — Regel 17 gilt der Handlung,
    nicht dem Bild.
    """
    plane = offset_plane("plane:xy", "@wand")

    assert frame_for_plane(plane) is None
    with pytest.raises(ValidationError) as problem:
        frame_for_sketch(plane)
    assert problem.value.suggestions


def test_a_tilt_turns_the_drawing_with_it() -> None:
    """Gekippt wird die ganze Ebene, nicht nur ihre Normale.

    Wer die Achsen aus der gekippten Normalen neu rechnet, dreht die Skizze um
    einen Winkel, den niemand erklären kann — dasselbe Argument wie in
    ``frame_of``.
    """
    frame = frame_for_plane(tilt_plane("plane:xy", "x", 90.0))

    assert frame is not None
    # Um die eigene X-Achse gekippt: X bleibt, Y wird zu Z, die Normale zu -Y.
    assert frame.x_axis == pytest.approx((1.0, 0.0, 0.0), abs=1e-12)
    assert frame.y_axis == pytest.approx((0.0, 0.0, 1.0), abs=1e-12)
    assert frame.normal == pytest.approx((0.0, -1.0, 0.0), abs=1e-12)


def test_a_tilt_keeps_its_frame_right_handed() -> None:
    """Eine Drehung erhält Längen und Winkel — sonst stünde die Zeichnung schief."""
    frame = frame_for_plane(tilt_plane("plane:xy", "y", 37.0))

    assert frame is not None
    for axis in (frame.x_axis, frame.y_axis, frame.normal):
        assert _length(axis) == pytest.approx(1.0, abs=1e-12)
    assert sum(a * b for a, b in zip(frame.x_axis, frame.y_axis, strict=True)) == pytest.approx(
        0.0, abs=1e-12
    )


def test_three_points_span_their_plane_from_the_first_one() -> None:
    """Der erste Punkt ist der Ursprung, die erste Achse zeigt zum zweiten.

    Das ist die Richtung, die der Zeichnende selbst gewählt hat — sie aus der
    Normalen zu rechnen, nähme sie ihm wieder weg.
    """
    frame = frame_for_plane(through_plane([(1.0, 2.0, 3.0), (11.0, 2.0, 3.0), (1.0, 12.0, 3.0)]))

    assert frame is not None
    assert frame.origin == pytest.approx((1.0, 2.0, 3.0))
    assert frame.x_axis == pytest.approx((1.0, 0.0, 0.0))
    assert frame.normal == pytest.approx((0.0, 0.0, 1.0))
    # Und der Zeichenpunkt (10, 10) landet dort, wo er hingehört.
    assert to_world(frame, (10.0, 10.0)) == pytest.approx((11.0, 12.0, 3.0))


def test_three_points_on_one_line_say_so() -> None:
    """Drei Punkte auf einer Geraden spannen keine Ebene auf."""
    with pytest.raises(ValidationError) as problem:
        frame_for_sketch(through_plane([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]))

    assert problem.value.suggestions


def test_a_plane_may_stand_on_a_derived_one() -> None:
    """Versatz über Neigung ist eine sinnvolle Konstruktion, und sie rechnet."""
    plane = offset_plane(tilt_plane("plane:xy", "x", 90.0), 4.0)
    frame = frame_for_plane(plane)

    assert frame is not None
    # Die gekippte Ebene hat die Normale -Y; vier Millimeter dorthin.
    assert frame.origin == pytest.approx((0.0, -4.0, 0.0), abs=1e-12)


def test_a_plane_that_stands_on_itself_stops() -> None:
    """Gegen eine beschädigte Datei, nicht gegen den Nutzer — sonst liefe es endlos."""
    plane = "plane:xy"
    for _step in range(MAX_PLANE_DEPTH + 1):
        plane = offset_plane(plane, 1.0)

    with pytest.raises(ValidationError) as problem:
        frame_for_sketch(plane)
    assert problem.value.suggestions


# --- Die Rundreise durch die Projektdatei ---------------------------------------


@pytest.mark.parametrize(
    "plane",
    [
        "plane:xy",
        "plane:xz",
        "plane:yz",
        "feature:obj_1:face_1",
        "feature:face_1",
        "offset:plane:xy:20.0",
        "offset:feature:obj_1:face_1:@wand",
        "tilt:plane:yz:y:-15.5",
        "through:0.0,0.0,0.0;10.0,0.0,0.0;0.0,10.0,0.0",
        "offset:tilt:plane:xy:x:90.0:4.0",
    ],
)
def test_a_plane_survives_the_round_trip(plane: str) -> None:
    """Was hineingeht, kommt heraus — auch die alte Kurzform ``feature:<id>``."""
    written = sketch_to_text(Sketch(plane=plane, elements=(), constraints=()))

    assert sketch_from_text(written).plane == plane


@pytest.mark.parametrize(
    "plane",
    [
        "plane:xw",
        "offset:plane:xy:zwanzig",
        "offset:plane:nope:20",
        "tilt:plane:xy:z:30",
        "through:0,0,0;1,0,0",
        "offset:plane:xy:=@wand +",
    ],
)
def test_a_damaged_plane_never_becomes_a_sketch(plane: str) -> None:
    """Der Text kommt aus einer fremden Datei und wird geprüft wie jede Eingabe (§32)."""
    written = sketch_to_text(Sketch(plane="plane:xy", elements=(), constraints=())).replace(
        '"plane": "plane:xy"', f'"plane": "{plane}"'
    )

    with pytest.raises(ValidationError):
        sketch_from_text(written)


# --- Was an einer Ebene hängt, muss auffallen (RM-188 P3.2) ----------------------


def test_a_plane_parameter_reaches_the_cache_key() -> None:
    """Ein Abstand aus einem Projektparameter zählt wie ein Maß in der Zeichnung.

    Ohne diese Abhängigkeit bliebe nach einer Parameteränderung das alte
    Ergebnis im Cache stehen, und die Skizze läge weiter auf der alten Höhe —
    sichtbar erst beim nächsten vollständigen Neurechnen (§15).
    """
    written = sketch_to_text(
        Sketch(plane=offset_plane("plane:xy", "=@wand * 2"), elements=(), constraints=())
    )

    assert sketch_parameter_references(written) == frozenset({"wand"})


def test_a_plane_parameter_is_found_through_every_derivation() -> None:
    """Auch wenn die Ebene auf einer anderen steht, die selbst ein Maß trägt."""
    plane = offset_plane(tilt_plane("plane:xy", "x", "@neigung"), "@hoehe")
    written = sketch_to_text(Sketch(plane=plane, elements=(), constraints=()))

    assert sketch_parameter_references(written) == frozenset({"neigung", "hoehe"})


def test_a_plane_without_parameters_depends_on_none() -> None:
    """Die Gegenprobe — sonst hinge jede Skizze an allem."""
    written = sketch_to_text(
        Sketch(plane=offset_plane("plane:xy", 20.0), elements=(), constraints=())
    )

    assert sketch_parameter_references(written) == frozenset()


@pytest.mark.parametrize(
    ("plane", "expected"),
    [
        ("plane:xy", None),
        ("feature:obj_1:face_1", "feature:obj_1:face_1"),
        ("offset:feature:obj_1:face_1:20", "feature:obj_1:face_1"),
        ("tilt:feature:obj_1:face_1:x:30", "feature:obj_1:face_1"),
        ("offset:tilt:feature:obj_1:face_1:x:30:5", "feature:obj_1:face_1"),
        ("offset:plane:xy:20", None),
        ("through:0,0,0;1,0,0;0,1,0", None),
    ],
)
def test_a_derived_plane_still_stands_on_its_face(plane: str, expected: str | None) -> None:
    """Verschwindet die Fläche, ist auch die Ebene darüber heimatlos.

    Die Verwaisungsprüfung fragte bis zum 22.09.2026 nur ``is_feature_plane``
    und sah durch eine Ableitung nicht hindurch — eine Skizze auf einer
    Versatzebene hätte ihre Fläche verlieren können, ohne dass es jemand
    meldet.
    """
    assert standing_on_feature(plane) == expected


def test_the_orphan_check_sees_the_face_under_a_derived_plane() -> None:
    """Und die Prüfung selbst, nicht nur ihr Baustein."""
    written = sketch_to_text(
        Sketch(
            plane=offset_plane(feature_plane("obj_1", "face_1"), 5.0),
            elements=(),
            constraints=(),
        )
    )

    reference = feature_ref_of_sketch(written)

    assert reference is not None
    assert (reference.object_id, reference.feature_id) == ("obj_1", "face_1")


# --- Und die Operation zeichnet wirklich dort (RM-188 P3.1, Ende zu Ende) --------


def _on_plane(plane: str, parameters: dict[str, Parameter] | None = None) -> object:
    """Ein Quader aus einer gezeichneten Skizze auf der genannten Ebene."""
    sketch = sketch_to_text(
        Sketch(
            plane=plane,
            elements=(
                SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
                SketchElement(kind="line", points=((10.0, 0.0), (10.0, 10.0))),
                SketchElement(kind="line", points=((10.0, 10.0), (0.0, 10.0))),
                SketchElement(kind="line", points=((0.0, 10.0), (0.0, 0.0))),
            ),
            constraints=(),
        )
    )
    spec = REGISTRY.get("sketch_extrude")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={}, parameters=parameters or {}),
            inputs=[],
            params=spec.params(sketch=sketch, height=4.0),
            profile=None,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    return result.outputs[0].mesh


def test_a_body_really_stands_on_its_offset_plane() -> None:
    """Der Beweis, dass der Vertrag kein Papier ist.

    Bis zum 22.09.2026 gab ``_frame_of`` für alles, was keine Flächenebene war,
    ``None`` zurück — der B-Rep-Kern nahm dann seine eigene Grundebene, und die
    Zeichnung läge auf z = 0 statt zwanzig Millimeter darüber. Der Ebenenvertrag
    wäre eine Angabe gewesen, die niemand einlöst.
    """
    load_operations()
    flat = _on_plane("plane:xy")
    lifted = _on_plane(offset_plane("plane:xy", 20.0))

    assert flat.bounds.minimum[2] == pytest.approx(0.0, abs=1e-9)
    assert lifted.bounds.minimum[2] == pytest.approx(20.0, abs=1e-9)
    assert lifted.bounds.maximum[2] == pytest.approx(24.0, abs=1e-9)
    assert lifted.volume == pytest.approx(flat.volume, rel=1e-9), "nur die Höhe ändert sich"


def test_a_body_reads_the_project_parameter_of_its_plane() -> None:
    """Und der Abstand darf ein Projektparameter sein (§13)."""
    load_operations()
    body = _on_plane(
        offset_plane("plane:xy", "=@sockel + 2"),
        {"sockel": Parameter(name="sockel", value=6.0, unit="mm")},
    )

    assert body.bounds.minimum[2] == pytest.approx(8.0, abs=1e-9)
