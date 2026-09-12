"""Der Langlochgriff in der Ansicht (§18.11, §21.1).

Zwei Knöpfe an einem gewählten Loch, gezogen wird in der Ebene seiner Mündung
— und daraus wird *Zum Langloch ziehen*. Geprüft wird an beiden Enden: dass
der Zug dieselbe Länge und dieselbe Richtung meint, die der Schnitt danach
nimmt, und dass die Geste im Fenster als genau ein Schritt ankommt.

**Die tragende Messung ist die erste.** Griff und Operation zählen ihren
Winkel gegen dieselbe Rahmenachse (:func:`app.core.sketch.planes.frame_of`);
liefe eine der beiden Seiten auf eine eigene Achse, läge das geschnittene Loch
um einen Winkel neben dem Umriss, den der Kunde beim Ziehen gesehen hat — und
kein Test über Zahlen allein würde es sehen.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.prepare import drill, shortest_slot, slot_profile, slot_travel
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.sketch.planes import frame_of
from app.core.types import Feature, OpContext, Profile, Scene, SceneObject
from app.ui.render.api import PointerEvent
from app.ui.slot_handle import SlotHandle, dragged_slot, slot_outline
from tests.render_fakes import RecordingRenderer

#: Der Durchmesser, mit dem hier gebohrt wird — groß genug, dass die Erkennung
#: das Langloch danach sicher wiederfindet.
BORE = 6.0


def a_drilled_plate(profile: Profile) -> SceneObject:
    """Eine Platte 60 x 40 x 10 mit einer durchgehenden Bohrung in der Mitte."""
    plate = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    mesh = drill(
        plate,
        profile=profile,
        position=(0.0, 0.0, 5.0),
        axis="z",
        diameter=BORE,
        compensate=False,
    ).mesh
    return SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))


def the_bore(entry: SceneObject) -> Feature:
    """Die eine erkannte Bohrung."""
    found = [feature for feature in entry.features.values() if feature.kind == "hole"]
    assert len(found) == 1, f"genau eine Bohrung erwartet, gefunden: {len(found)}"
    return found[0]


def run_op(op: str, entry: SceneObject, profile: Profile, **params: object) -> SceneObject:
    """Eine Operation fahren und danach neu erkennen, wie die Auswertung es tut."""
    from app.core.scene.cancel import NeverCancelled

    load_operations()
    spec = REGISTRY.get(op)
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, options: options[0],
            cancelled=NeverCancelled(),
        )
    )
    out = result.outputs[0]
    return dataclasses.replace(out, features=detect(as_mesh_data(out.mesh)))


def pulled_to(feature: Feature, angle: float, reach: float) -> tuple[float, float]:
    """Was ein Zug meint, der ``reach`` weit unter ``angle`` von der Mitte weg geht."""
    centre = feature.params["centre"]
    axis = feature.params["axis"]
    frame = frame_of(axis, centre)
    turn = math.radians(angle)
    point = (
        np.asarray(centre, dtype=float)
        + math.cos(turn) * np.asarray(frame.x_axis, dtype=float) * reach
        + math.sin(turn) * np.asarray(frame.y_axis, dtype=float) * reach
    )
    return dragged_slot(centre, axis, float(feature.params["diameter"]), point)


# --- Was der Zug meint, ist was der Schnitt nimmt ---------------------------------


@pytest.mark.parametrize("angle", [0.0, 30.0, 90.0, -45.0, 150.0])
def test_a_drag_cuts_the_slot_it_showed(angle: float, profile: Profile) -> None:
    """Die tragende Messung: Griff und Schnitt zählen denselben Winkel.

    Gezogen wird 12 mm von der Mitte weg; heraus kommt ein Langloch von 24 mm
    in genau dieser Richtung. Ohne Vorzeichen verglichen — ein Langloch hat
    keine Vorder- und keine Rückseite.
    """
    entry = a_drilled_plate(profile)
    bore = the_bore(entry)
    length, turned = pulled_to(bore, angle, 12.0)

    longer = run_op(
        "slot_hole", entry, profile, at_feature=bore.id, slot_length=length, slot_angle=turned
    )

    slots = [feature for feature in longer.features.values() if feature.kind == "slot"]
    assert len(slots) == 1, "aus dem Zug ist genau ein Langloch geworden"
    assert float(slots[0].params["length"]) == pytest.approx(24.0, abs=0.05)
    frame = frame_of(bore.params["axis"], bore.params["centre"])
    wanted = math.cos(math.radians(angle)) * np.asarray(frame.x_axis, dtype=float) + math.sin(
        math.radians(angle)
    ) * np.asarray(frame.y_axis, dtype=float)
    parallel = abs(float(np.asarray(slots[0].params["direction"], dtype=float) @ wanted))
    assert parallel == pytest.approx(1.0, abs=1e-3), (
        f"das geschnittene Loch liegt nicht in der gezogenen Richtung: {slots[0].params}"
    )


def test_the_drag_at_a_slot_starts_from_the_direction_it_already_has(profile: Profile) -> None:
    """Ein Zug am bestehenden Langloch verlängert es, statt es quer zu stellen.

    Der Griff belegt seine Knöpfe mit ``slot_angle_of`` — derselben Auskunft,
    die die Operation als Vorgabe nimmt. Ein Zug ohne eigene Richtung (über der
    Mitte) behält sie damit.
    """
    from app.core.geom.prepare_ops import slot_angle_of

    entry = a_drilled_plate(profile)
    bore = the_bore(entry)
    long_one = run_op(
        "slot_hole", entry, profile, at_feature=bore.id, slot_length=20.0, slot_angle=35.0
    )
    slot = next(feature for feature in long_one.features.values() if feature.kind == "slot")

    standing = slot_angle_of(slot, slot.params["axis"])
    # Ein Zug, der die Mitte trifft, hat keine eigene Richtung — dann gilt die,
    # die schon da ist.
    _length, turned = dragged_slot(
        slot.params["centre"],
        slot.params["axis"],
        float(slot.params["diameter"]),
        slot.params["centre"],
        angle=standing,
    )
    assert turned == pytest.approx(standing, abs=1e-9)
    assert abs(standing) == pytest.approx(35.0, abs=0.5), (
        "der Griff liest die Richtung, in der das Loch schon liegt"
    )


def test_a_drag_into_the_middle_still_asks_for_something_the_operation_takes(
    profile: Profile,
) -> None:
    """Eine Geste, die in einer Absage endet, ist keine Bedienung.

    ``slot_hole`` lehnt jede Länge unter :func:`prepare.shortest_slot` ab
    (``prepare.SLOT_TOO_SHORT``). Der Griff lässt deshalb gar nicht erst kürzer
    ziehen — auch nicht, wenn der Zeiger auf der Mitte steht.

    **Und der Anschlag wird bis zum Ende geprüft.** Hier stand bis zum
    11.09.2026 nur, dass die Operation die Länge *annimmt*, und das war die
    halbe Zusicherung: Der Griff rastete bei ``1.05`` mal Durchmesser, die
    Operation nahm das an, und die Merkmalserkennung machte daraus eine
    **Bohrung** — bei größeren Durchmessern gar nichts mehr. Der Kunde zog bis
    zum Anschlag und hatte danach nichts mehr zum Anklicken. Was zählt, ist
    also nicht die Annahme, sondern das Merkmal, das danach dasteht.
    """
    entry = a_drilled_plate(profile)
    bore = the_bore(entry)

    length, _turned = pulled_to(bore, 0.0, 0.0)

    # Gegen den **gemessenen** Durchmesser: Die Erkennung liest das facettierte
    # Netz, und das ist nicht auf die Stelle genau der Wert, mit dem gebohrt
    # wurde. Der Griff rechnet mit dem, was am Merkmal steht — wie die
    # Operation auch.
    assert length == pytest.approx(shortest_slot(float(bore.params["diameter"])))
    gezogen = run_op(
        "slot_hole", entry, profile, at_feature=bore.id, slot_length=length, slot_angle=0.0
    )
    arten = [feature.kind for feature in gezogen.features.values()]
    assert arten.count("slot") == 1, f"am Anschlag steht ein Langloch da, gefunden: {arten}"


@pytest.mark.parametrize("diameter", [2.0, 5.0, 12.0, 20.0, 40.0])
def test_the_shortest_slot_is_one_over_the_whole_range(diameter: float, profile: Profile) -> None:
    """Der Anschlag trägt über den ganzen Durchmesserbereich — nicht nur bei Ø 6.

    Die Grenze, an der die Erkennung kippt, wächst mit dem Durchmesser: Ø 5
    kippt bei 0,25 mm Weg, Ø 20 bei 1,0, Ø 40 bei 1,8 (gemessen 11.09.2026).
    Ein Anteil, der nur bei kleinen Löchern reicht, ist deshalb kein Anschlag,
    sondern ein Zufall — und genau so einer stand hier: ``1.05`` traf bei Ø 20
    die Kippgrenze auf den Punkt.
    """
    plate = trimesh.creation.box(extents=(160.0, 120.0, 12.0))
    entry = SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(plate), features={})
    drilled = run_op(
        "drill_hole", entry, profile, x=0.0, y=0.0, z=6.0, axis="z", diameter=diameter, depth=0.0
    )
    bore = next(feature for feature in drilled.features.values() if feature.kind == "hole")

    length, _turned = pulled_to(bore, 0.0, 0.0)
    pulled = run_op(
        "slot_hole", drilled, profile, at_feature=bore.id, slot_length=length, slot_angle=0.0
    )

    arten = [feature.kind for feature in pulled.features.values()]
    assert arten.count("slot") == 1, (
        f"Ø {diameter}: am Anschlag steht ein Langloch da, gefunden: {arten}"
    )


@pytest.mark.parametrize("angle", [-179.0, -90.0, 0.0, 90.0, 179.0, 200.0, -200.0])
def test_a_drag_never_leaves_the_range_the_field_allows(angle: float, profile: Profile) -> None:
    """Ein Zug rund um die Mitte bleibt im Bereich des Parameters.

    Das Feld führt −180 bis 180 Grad. Ein Winkel darüber hinaus wäre kein
    krummer Wert, sondern eine Absage des Schemas — und der Kunde hätte einen
    Zug gemacht, der nichts tut.
    """
    load_operations()
    spec = REGISTRY.get("slot_hole").params.spec()
    field = next(entry for entry in spec if entry.name == "slot_angle")

    entry = a_drilled_plate(profile)
    _length, turned = pulled_to(the_bore(entry), angle, 9.0)

    assert field.minimum is not None and field.maximum is not None
    assert field.minimum <= turned <= field.maximum


# --- Was im Bild steht, ist der Umriss des Schnitts -------------------------------


def test_the_outline_is_the_one_the_cut_uses() -> None:
    """Die Vorschau kommt aus derselben Funktion wie der Schnitt.

    Gegenprobe über die **Ecken**: Wo ``slot_profile`` seine Segmente
    aneinandersetzt, liegt auch ein Punkt des gezeichneten Linienzugs. Eine
    zweite Konstruktion daneben liefe beim nächsten Zuwachs auseinander, und im
    Bild stünde eine Form, die niemand schneidet.
    """
    centre, axis, diameter, length, angle = (2.0, -3.0, 4.0), (0.0, 0.0, 1.0), 5.0, 20.0, 30.0
    frame = frame_of(axis, centre)
    from app.core.sketch.planes import to_world

    drawn = slot_outline(centre, axis, diameter, length, angle)
    corners = [
        np.asarray(to_world(frame, segment.start), dtype=float)
        for segment in slot_profile(
            radius=diameter / 2.0,
            travel=slot_travel(diameter=diameter, length=length),
            angle_deg=angle,
        ).segments
    ]

    for corner in corners:
        gap = float(np.min(np.linalg.norm(drawn - corner, axis=1)))
        assert gap < 1e-9, f"die Ecke {corner} steht in keinem gezeichneten Punkt"
    assert np.allclose(drawn[0], drawn[-1]), "der Umriss ist geschlossen"


# --- Der Griff als Bedienelement --------------------------------------------------


def a_handle(renderer: RecordingRenderer, taken: list[tuple[float, float]]) -> SlotHandle:
    """Ein Griff an einer Bohrung Ø 6 in der Mitte, mit Aufzeichnung."""
    return SlotHandle(
        renderer,
        centre=(0.0, 0.0, 5.0),
        axis=(0.0, 0.0, 1.0),
        diameter=BORE,
        length=BORE,
        angle=0.0,
        knob_size=BORE,
        colour="#ff9f1c",
        release_callback=lambda length, angle: taken.append((length, angle)),
    )


def test_a_handle_built_for_a_waiting_drag_shows_its_outline_at_once() -> None:
    """Ein Griff, der einen wartenden Zug trägt, steht mit seinem Umriss da.

    Der Griff wird nach jedem Zug am Bewegungsgriff frisch gebaut. Bis zum
    11.09.2026 zeichnete der Aufbau nur die Knöpfe; den Umriss gab es erst
    mit dem nächsten Zug — nach dem Versetzen eines gezogenen Langlochs
    standen zwei Knöpfe um nichts herum (Robert: „das langloch dann
    verschiebe fehlt die richtige vorschau").
    """
    renderer = RecordingRenderer(size=(800, 600))
    plain = a_handle(renderer, [])
    assert plain._outline is None, "ohne wartenden Zug kein Umriss — der kommt mit dem Zug"
    waiting = SlotHandle(
        renderer,
        centre=(0.0, 0.0, 5.0),
        axis=(0.0, 0.0, 1.0),
        diameter=BORE,
        length=18.0,
        angle=30.0,
        knob_size=BORE,
        colour="#ff9f1c",
        release_callback=lambda length, angle: None,
        outlined=True,
    )
    outline = waiting._outline
    assert outline is not None, "der wartende Zug steht als Umriss im Bild"
    expected = slot_outline((0.0, 0.0, 5.0), (0.0, 0.0, 1.0), BORE, 18.0, 30.0)
    assert np.allclose(outline.points, expected), "und zwar der des Zugs, nicht der Bohrung"


def test_a_foreign_drag_carries_knobs_and_outline_along() -> None:
    """Ein Zug am Bewegungsgriff nimmt Knöpfe und Umriss mit — und lässt sie zurück.

    Während des Zugs stehen beide dort, wohin gezogen wird: Der Umriss zeigt
    das künftige Loch, und das soll an der Stelle stehen, die der Zeiger
    gerade meint. Der Versatz sitzt **auf** dem der Knöpfe, nicht an seiner
    Stelle — ein gezogener Griff hat seine Knöpfe schon aus der Bauposition
    heraus verschoben.
    """
    renderer = RecordingRenderer(size=(800, 600))
    handle = SlotHandle(
        renderer,
        centre=(0.0, 0.0, 5.0),
        axis=(0.0, 0.0, 1.0),
        diameter=BORE,
        length=BORE,
        angle=0.0,
        knob_size=BORE,
        colour="#ff9f1c",
        release_callback=lambda length, angle: None,
    )
    handle.set_values(18.0, 0.0)
    before = [np.asarray(knob.position(), dtype=float) for knob in handle.knobs]
    # Gebaut an der Mindestlänge, gezogen auf 18: Der Versatz der Knöpfe ist
    # die halbe Differenz — und genau darauf setzt der fremde Zug auf.
    pulled = 9.0 - shortest_slot(BORE) / 2.0
    assert before[0][0] == pytest.approx(pulled) and before[1][0] == pytest.approx(-pulled)

    handle.shift((6.0, 4.0, 0.0))
    after = [np.asarray(knob.position(), dtype=float) for knob in handle.knobs]
    assert np.allclose(after[0] - before[0], (6.0, 4.0, 0.0))
    assert np.allclose(after[1] - before[1], (6.0, 4.0, 0.0))
    assert handle._outline is not None
    assert np.allclose(handle._outline.position(), (6.0, 4.0, 0.0)), "der Umriss geht mit"
    assert handle.knob_seats[0][0] == pytest.approx(9.0), (
        "die Sitze bleiben, wo gebaut wird — die Beschriftung zieht der Griff selbst um"
    )

    handle.shift((0.0, 0.0, 0.0))
    back = [np.asarray(knob.position(), dtype=float) for knob in handle.knobs]
    assert np.allclose(back[0], before[0]) and np.allclose(back[1], before[1])
    assert np.allclose(handle._outline.position(), (0.0, 0.0, 0.0))


def test_one_pixel_of_pointer_jitter_does_not_start_a_slot_drag() -> None:
    """Ein Antippen mit Mauszittern eröffnet keine Langlochbearbeitung."""
    renderer = RecordingRenderer(size=(800, 600))
    taken: list[tuple[float, float]] = []
    handle = a_handle(renderer, taken)
    seat = renderer.world_to_display(handle.knob_seats[0])
    x, y = round(seat[0]), round(seat[1])
    renderer.item_picks[(x, y)] = handle.knobs[0]
    handle.handle(PointerEvent("move", x, y))
    handle.handle(PointerEvent("press", x, y, button="left"))
    handle.handle(PointerEvent("move", x + 1, y))
    handle.handle(PointerEvent("release", x + 1, y, button="left"))
    assert not taken
    assert "slot-handle:outline" not in renderer.names()


def test_dragging_back_clears_the_preview_and_reports_cancellation() -> None:
    """Zurückziehen auf den Druckpunkt lässt keinen Umriss oder Auftrag stehen."""
    renderer = RecordingRenderer(size=(800, 600))
    taken = []
    cancelled = []
    handle = a_handle(renderer, taken)
    handle._cancel = lambda: cancelled.append(True)
    original = (handle.length, handle.angle)
    seat = renderer.world_to_display(handle.knob_seats[0])
    x, y = round(seat[0]), round(seat[1])
    renderer.item_picks[(x, y)] = handle.knobs[0]
    handle.handle(PointerEvent("move", x, y))
    handle.handle(PointerEvent("press", x, y, button="left"))
    handle.handle(PointerEvent("move", x + 40, y + 20))
    outline = handle._outline
    handle.handle(PointerEvent("move", x, y))
    handle.handle(PointerEvent("release", x, y, button="left"))
    assert cancelled == [True]
    assert not taken
    assert (handle.length, handle.angle) == original
    assert outline is not None and outline in renderer.removed
    assert handle._outline is None


def test_the_knobs_report_the_drag_when_they_are_let_go() -> None:
    """Greifen, ziehen, loslassen — und die Ansicht bekommt Länge und Richtung.

    Die Attrappe blickt entlang der z-Achse; ihr Strahl trifft die Mündung der
    Bohrung damit senkrecht, und der Weg im Bild ist der Weg auf der Ebene.
    """
    renderer = RecordingRenderer(size=(800, 600))
    taken: list[tuple[float, float]] = []
    handle = a_handle(renderer, taken)

    # Der rechte Knopf sitzt am Scheitel, also bei x = 3.
    seat = renderer.world_to_display((BORE / 2.0, 0.0, 5.0))
    renderer.item_picks[(round(seat[0]), round(seat[1]))] = handle.knobs[0]
    handle.handle(PointerEvent("move", int(seat[0]), int(seat[1])))
    assert handle.handle(PointerEvent("press", int(seat[0]), int(seat[1]), button="left"))

    target = renderer.world_to_display((12.0, 0.0, 5.0))
    assert handle.handle(PointerEvent("move", int(target[0]), int(target[1])))
    assert handle.handle(PointerEvent("release", int(target[0]), int(target[1]), button="left"))

    assert len(taken) == 1
    length, angle = taken[0]
    assert length == pytest.approx(24.0, abs=0.01)
    assert angle == pytest.approx(0.0, abs=0.01)
    assert "slot-handle:outline" in renderer.names(), "der Zug zeigt den Umriss, den er meint"


def test_a_gesture_the_knobs_do_not_want_goes_on_to_the_camera() -> None:
    """Ein Griff, der nichts trifft, hält die Ansicht nicht auf.

    Er gibt ``False`` zurück, und ``_on_pointer`` reicht die Geste an die
    Kameraführung weiter — sonst wäre ein gewähltes Loch eine Sperre über dem
    ganzen Bild.
    """
    renderer = RecordingRenderer(size=(800, 600))
    handle = a_handle(renderer, [])

    assert not handle.handle(PointerEvent("press", 700, 500, button="left"))
    assert not handle.handle(PointerEvent("move", 700, 500))


def test_the_drag_stays_symmetric_around_the_centre_of_the_bore() -> None:
    """Das Loch wächst um seine Mitte, gleich an welchem Knopf gezogen wird.

    Die Mitte ist der eine Wert, den die Operation **nicht** mitbekommt — sie
    liest sie aus dem Merkmal. Ein Zug, der sie verschöbe, verspräche etwas,
    das der Schnitt nicht einlöst.
    """
    renderer = RecordingRenderer(size=(800, 600))
    taken: list[tuple[float, float]] = []
    handle = a_handle(renderer, taken)

    # Diesmal der linke Knopf, und gezogen wird nach links.
    seat = renderer.world_to_display((-BORE / 2.0, 0.0, 5.0))
    renderer.item_picks[(round(seat[0]), round(seat[1]))] = handle.knobs[1]
    handle.handle(PointerEvent("move", int(seat[0]), int(seat[1])))
    handle.handle(PointerEvent("press", int(seat[0]), int(seat[1]), button="left"))
    target = renderer.world_to_display((-10.0, 0.0, 5.0))
    handle.handle(PointerEvent("move", int(target[0]), int(target[1])))
    handle.handle(PointerEvent("release", int(target[0]), int(target[1]), button="left"))

    length, angle = taken[0]
    assert length == pytest.approx(20.0, abs=0.01)
    # Nach links gezogen heißt dieselbe Achse — der Winkel zeigt zurück auf 0,
    # weil der gegriffene Knopf der gegenüberliegende ist.
    assert angle == pytest.approx(0.0, abs=0.01)


# --- Wo der Griff sitzt, sagt das Register ----------------------------------------


def test_the_handle_sits_exactly_where_the_operation_applies() -> None:
    """Eine Aufzählung in der Ansicht wüsste beim nächsten Zuwachs die Hälfte."""
    from app.ui.viewport import slot_feature_kinds

    load_operations()

    assert slot_feature_kinds() == frozenset(REGISTRY.get("slot_hole").applies_to or ())
    assert "hole" in slot_feature_kinds() and "slot" in slot_feature_kinds()


def test_the_knobs_appear_at_a_hole_and_nowhere_else(qt_app: object) -> None:
    """Der Griff steht dort, wo er etwas auslösen kann — und sonst nirgends.

    Am ganzen Körper steht der Skalierwürfel, an einer Bohrung die Knöpfe, an
    einer Verrundung keines von beidem: Sie trägt im Register keine einzige
    Operation, und ein Griff, der nichts auslöst, wäre schlimmer als keiner.
    """
    import trimesh

    from app.core.scene import EvaluationResult
    from app.ui.viewport import Viewport

    load_operations()
    mesh = MeshData(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    features = {
        "hole_1": Feature(
            id="hole_1",
            kind="hole",
            provenance="detected",
            params={"diameter": 5.0, "centre": (-10.0, 0.0, 5.0), "axis": (0.0, 0.0, 1.0)},
        ),
        "fillet_1": Feature(
            id="fillet_1",
            kind="fillet",
            provenance="detected",
            params={"radius": 2.0, "centre": (10.0, 0.0, 5.0)},
        ),
    }
    result = EvaluationResult(
        scene=Scene(
            objects={"obj_1": SceneObject(id="obj_1", name="A", mesh=mesh, features=features)}
        )
    )

    viewport = Viewport()
    try:
        viewport.renderer = RecordingRenderer(size=(800, 600))
        viewport.show_scene(result)
        viewport.select("obj_1")

        viewport.select_feature("hole_1")
        viewport.set_gizmo(True)
        assert viewport._slot_handle is None, (
            "die Auswahl allein zeigt nur, was gewählt ist (Robert, 11.09.2026)"
        )
        viewport.set_placement_pointer(lambda event: False)
        assert viewport._slot_handle is not None, "mit *Im Bild einstellen* stehen die Knöpfe"
        assert viewport._scale_handle is None, "und kein Würfel — ein Merkmal hat keine Größe"
        viewport.set_placement_pointer(None)
        assert viewport._slot_handle is None, "und sie gehen mit der Platzierung"
        viewport.set_placement_pointer(lambda event: False)

        viewport.select_feature("fillet_1")
        viewport.set_gizmo(True)
        assert viewport._slot_handle is None, "eine Verrundung wird kein Langloch"

        viewport.select_feature(None)
        viewport.set_gizmo(True)
        assert viewport._slot_handle is None and viewport._scale_handle is not None, (
            "am ganzen Körper bleibt es beim Würfel"
        )
    finally:
        viewport.renderer = None
        viewport.deleteLater()


# --- Ziehen, nachbessern, bestätigen ----------------------------------------------


def a_slot_in_the_view(viewport: object) -> None:
    """Baut eine Szene mit einem erkannten Langloch, wählt es — und stellt es im Bild ein.

    Seit dem 11.09.2026 kommen die Griffe an Bohrung und Langloch mit der
    Platzierung (*Im Bild einstellen*), nicht mit der Auswahl; der Zeiger der
    Platzierung ist im Viewport die Ansage dafür (``set_placement_pointer``).
    """
    import trimesh

    from app.core.scene import EvaluationResult

    mesh = MeshData(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    slot = Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        params={
            "diameter": 6.0,
            "length": 20.0,
            "travel": 14.0,
            "axis": (0.0, 0.0, 1.0),
            "direction": (1.0, 0.0, 0.0),
            "centre": (0.0, 0.0, 5.0),
            "depth": 10.0,
            "through": True,
        },
    )
    result = EvaluationResult(
        scene=Scene(
            objects={
                "obj_1": SceneObject(
                    id="obj_1", name="Platte", mesh=mesh, features={"slot_1": slot}
                )
            }
        )
    )
    viewport.show_scene(result)  # type: ignore[attr-defined]
    viewport.select("obj_1")  # type: ignore[attr-defined]
    viewport.select_feature("slot_1")  # type: ignore[attr-defined]
    viewport.set_placement_pointer(lambda event: False)  # type: ignore[attr-defined]


def test_a_slot_carries_the_knobs_and_the_grip(qt_app: object) -> None:
    """Zwei Fähigkeiten, zwei Griffe — und seit RM-153 beide am Langloch.

    Bis zum 11.09.2026 stand hier das Gegenteil: Ein Langloch war in keinem
    ``applies_to`` von *Merkmal verschieben*, und der Bewegungsgriff blieb weg,
    weil drei Pfeile, die keine Operation einlöst, schlimmer wären als keine.
    Jetzt löst sie eine ein (Robert: „beim langloch bearbeiten fehlt das gizmo
    noch wenn wir auf im Bild einstellen klicken").
    """
    from app.ui.viewport import Viewport, movable_feature_kinds

    load_operations()
    assert "slot" in movable_feature_kinds(), "ein Langloch lässt sich versetzen (RM-153)"

    viewport = Viewport()
    try:
        viewport.renderer = RecordingRenderer(size=(800, 600))
        a_slot_in_the_view(viewport)
        viewport.set_gizmo(False)

        assert viewport._slot_handle is not None, "am Langloch stehen die Knöpfe"
        assert viewport._gizmo is not None, "und der Bewegungsgriff, der es versetzt und dreht"
        assert viewport._scale_handle is None, "ohne Würfel — ein Merkmal hat keine Größe"
    finally:
        viewport.renderer = None
        viewport.deleteLater()


def test_the_mark_at_a_slot_is_the_slot_and_not_its_bore(qt_app: object) -> None:
    """Die Marke eines Langlochs deckt das Langloch — nicht nur einen Kreis darin.

    Bis zum 11.09.2026 stand an einem erkannten Langloch derselbe Zylinder wie
    an einer Bohrung: Ø 6 über einem Loch von 20 mm Länge. Neben dem Umriss
    des Griffs waren das zwei Formen für dasselbe Loch.
    """
    from app.ui.viewport import Viewport

    load_operations()
    viewport = Viewport()
    try:
        viewport.renderer = RecordingRenderer(size=(800, 600))
        a_slot_in_the_view(viewport)
        viewport.set_gizmo(False)

        mark = viewport._shape_actor
        assert mark is not None, "das gewählte Langloch trägt seine Marke"
        span = mark.points.max(axis=0) - mark.points.min(axis=0)
        assert span[0] == pytest.approx(20.0, abs=0.05), "so lang wie das Langloch"
        assert span[1] == pytest.approx(6.0, abs=0.05), "so breit wie seine Bohrung"
        assert span[2] == pytest.approx(10.0, abs=0.05), "und so tief wie das Loch"
        assert mark.points[:, 2].max() == pytest.approx(10.0), "vom Sitz an der Öffnung aus"
    finally:
        viewport.renderer = None
        viewport.deleteLater()


def test_slot_grip_snap_labels_and_clearance_follow_the_preview(qt_app: object) -> None:
    """Rastung, Beschriftung und freier Raum gehören zum aktuellen Griffstand."""
    from app.ui.labels import length
    from app.ui.viewport import GIZMO_LABEL_GAP, Viewport, slot_measure_seat

    load_operations()
    viewport = Viewport()
    try:
        renderer = RecordingRenderer(size=(800, 600))
        viewport.renderer = renderer
        a_slot_in_the_view(viewport)
        handle = viewport._slot_handle
        assert handle is not None
        viewport._angle_step = 45.0
        seat = renderer.world_to_display(handle.knob_seats[0])
        x, y = round(seat[0]), round(seat[1])
        renderer.item_picks[(x, y)] = handle.knobs[0]
        handle.handle(PointerEvent("move", x, y))
        handle.handle(PointerEvent("press", x, y, button="left"))
        point = renderer.world_to_display((40.0, 39.0, 5.0))
        handle.handle(PointerEvent("move", round(point[0]), round(point[1])))
        assert handle.angle == pytest.approx(45.0)
        clearance = viewport.gizmo_reach()
        assert clearance is not None
        centre, radius = clearance
        for seat in handle.knob_seats:
            assert math.dist(centre, seat) < radius
        expected = [
            np.asarray(centre) + (np.asarray(seat) - centre) * GIZMO_LABEL_GAP
            for seat in handle.knob_seats
        ]
        # Seit RM-153 stehen davor X, Y und Z des Bewegungsgriffs; die zwei L
        # der Knöpfe stehen dahinter, und die Länge ist die letzte Marke — sie
        # folgt dem Zug wie die Knöpfe (Robert, 11.09.2026: „wenn man das
        # langloch zieht wäre auch das maß nicht schlecht wie groß es ist").
        assert viewport._gizmo_label_texts[-3:-1] == ["L", "L"]
        assert viewport._gizmo_label_texts[-1] == length(handle.length), (
            "die Länge steht im Bild, mit dem Wert des Zugs"
        )
        np.testing.assert_allclose(viewport._gizmo_label_base[-3:-1], expected)
        np.testing.assert_allclose(
            viewport._gizmo_label_base[-1], slot_measure_seat(handle), atol=1e-9
        )
        handle.handle(PointerEvent("move", x, y))
        handle.handle(PointerEvent("release", x, y, button="left"))
        assert viewport._drag_kind is None
        assert viewport.drag_bar.isHidden()
    finally:
        viewport.renderer = None
        viewport.deleteLater()


def test_a_drag_waits_in_its_bar_instead_of_writing_a_step(qt_app: object) -> None:
    """Der Zug endet in der Leiste — die Operation entsteht erst beim Übernehmen.

    „nach dem ziehen nochmal die eingabe bei den maßen und dann bestätigen"
    (Robert, 10.09.2026). Bis dahin ist nichts geschehen: kein Signal, kein
    Schritt, nur ein Umriss und zwei Zahlen.
    """
    from app.ui.viewport import Viewport

    load_operations()
    viewport = Viewport()
    gemeldet: list[tuple[str, float, float]] = []
    try:
        viewport.renderer = RecordingRenderer(size=(800, 600))
        viewport.slotDragged.connect(
            lambda name, length, angle: gemeldet.append((name, length, angle))
        )
        a_slot_in_the_view(viewport)
        viewport.set_gizmo(False)
        handle = viewport._slot_handle
        assert handle is not None

        vorgeschlagen: list[tuple[str, float, float]] = []
        viewport.slotProposed.connect(
            lambda name, length, angle: vorgeschlagen.append((name, length, angle))
        )

        handle._release(28.0, 15.0)

        assert not gemeldet, "der Zug allein schreibt nichts"
        # **Der Vorschlag geht nach rechts, nicht in eine eigene Leiste**
        # (11.09.2026): Länge und Richtung stehen unter *Zum Langloch ziehen*
        # im Merkmalfenster, und dort steht auch das eine Übernehmen.
        assert len(vorgeschlagen) == 1, "der Zug schlägt seine Zahlen vor"
        name, length, angle = vorgeschlagen[0]
        assert name == "slot_1"
        assert length == pytest.approx(28.0)
        assert angle == pytest.approx(15.0)
        assert viewport.slot_drag_waits(), "der Zug wartet auf seine Bestätigung"

        # Nachgebessert: der Umriss folgt der Zahl, das Modell nicht.
        viewport.reshape_slot(32.0, 15.0)
        assert not gemeldet
        assert viewport._slot_handle is not None
        assert viewport._slot_handle.length == pytest.approx(32.0)

        # Und erst das Übernehmen macht daraus eine Operation. Den Weg geht
        # das Merkmalfenster; hier steht die Stelle, an der er ankommt.
        viewport.apply_slot_drag(32.0, 15.0)
        assert len(gemeldet) == 1
        name, length, angle = gemeldet[0]
        assert name == "slot_1"
        assert length == pytest.approx(32.0)
        assert angle == pytest.approx(15.0)
    finally:
        viewport.renderer = None
        viewport.deleteLater()


def test_a_cancelled_drag_leaves_nothing_behind(qt_app: object) -> None:
    """Abbrechen heißt abbrechen: kein Signal, keine Leiste, kein Umriss."""
    from app.ui.viewport import Viewport

    load_operations()
    viewport = Viewport()
    gemeldet: list[object] = []
    try:
        viewport.renderer = RecordingRenderer(size=(800, 600))
        viewport.slotDragged.connect(lambda *args: gemeldet.append(args))
        a_slot_in_the_view(viewport)
        viewport.set_gizmo(False)
        assert viewport._slot_handle is not None
        viewport._slot_handle._release(30.0, 0.0)

        # **Ein anderer Zug lässt den wartenden stehen** (11.09.2026, Robert:
        # „das langloch ziehe und dann das langloch nochmal über das gizmo
        # verschieben will ist es wie abbrechen") — ``_end_drag`` allein bricht
        # ihn nicht mehr ab, das tut der Griff auch nach einem Zug am Pfeil.
        viewport._end_drag()
        assert viewport.slot_drag_waits(), "der Zug wartet weiter"
        assert viewport._slot_handle is not None
        assert viewport._slot_handle.length == pytest.approx(30.0), "und der neue Griff trägt ihn"

        # Abgebrochen wird über Escape — die eigene Leiste dafür ist am
        # 11.09.2026 gefallen; das Fenster nimmt ``cancel_slot_drag``.
        viewport.cancel_slot_drag()

        assert not gemeldet, "abgebrochen wird nichts angewandt"
        assert not viewport.slot_drag_waits()
        assert viewport._slot_handle is not None
        assert viewport._slot_handle.length < 30.0, "der Griff zeigt wieder das Merkmal"
    finally:
        viewport.renderer = None
        viewport.deleteLater()


def test_the_panel_shows_the_length_a_slot_really_has(qt_app: object) -> None:
    """Jedes Feld trägt seinen heutigen gemessenen Wert — auch am Langloch.

    Die allgemeine Zuordnung nimmt für *Länge* den doppelten Durchmesser; an
    einer runden Bohrung ist das die Vorgabe für ihr erstes Langloch, an einem
    bestehenden wäre es eine stille Verkürzung von 20 auf 12 mm.
    """
    from app.core.perceive.actions import actions_for

    load_operations()
    slot = Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        params={
            "diameter": 6.0,
            "length": 20.0,
            "travel": 14.0,
            "axis": (0.0, 0.0, 1.0),
            "direction": (0.86602540378, 0.5, 0.0),
            "centre": (0.0, 0.0, 0.0),
            "depth": 10.0,
            "through": True,
        },
    )

    zeile = next(action for action in actions_for(slot) if action.op == "slot_hole")
    werte = {field.name: field.value for field in zeile.fields}

    assert werte["slot_length"] == pytest.approx(20.0), "die gemessene Länge, nicht 2 x Durchmesser"
    assert float(werte["slot_angle"]) == pytest.approx(30.0, abs=0.01), "und die Richtung dazu"


def test_the_bar_goes_when_the_selection_does(qt_app: object) -> None:
    """Die Leiste gehört ihrem Zug — und der endet mit der Auswahl.

    Befund aus dem Review, gemessen: Ein Auswahlwechsel räumte den Griff ab und
    ließ die Leiste stehen. *Übernehmen* meldete danach ``('hole_2', 40, 15)``
    — ein 40-mm-Langloch in einem Loch, das niemand gezogen hat, und der
    Schritt lief unmittelbar in den Verlauf.
    """
    import trimesh

    from app.core.scene import EvaluationResult
    from app.ui.viewport import Viewport

    load_operations()
    mesh = MeshData(trimesh.creation.box(extents=(80.0, 40.0, 10.0)))
    slot = Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        params={
            "diameter": 6.0,
            "length": 20.0,
            "travel": 14.0,
            "axis": (0.0, 0.0, 1.0),
            "direction": (1.0, 0.0, 0.0),
            "centre": (-15.0, 0.0, 5.0),
            "depth": 10.0,
            "through": True,
        },
    )
    hole = Feature(
        id="hole_2",
        kind="hole",
        provenance="detected",
        params={"diameter": 5.0, "centre": (20.0, 0.0, 5.0), "axis": (0.0, 0.0, 1.0)},
    )
    result = EvaluationResult(
        scene=Scene(
            objects={
                "obj_1": SceneObject(
                    id="obj_1",
                    name="Platte",
                    mesh=mesh,
                    features={"slot_1": slot, "hole_2": hole},
                )
            }
        )
    )

    viewport = Viewport()
    gemeldet: list[tuple[str, float, float]] = []
    try:
        viewport.renderer = RecordingRenderer(size=(800, 600))
        viewport.slotDragged.connect(
            lambda name, length, angle: gemeldet.append((name, length, angle))
        )
        viewport.show_scene(result)
        viewport.select("obj_1")
        viewport.select_feature("slot_1")
        viewport.set_placement_pointer(lambda event: False)
        viewport.set_gizmo(False)
        assert viewport._slot_handle is not None
        viewport._slot_handle._release(40.0, 15.0)
        assert viewport.slot_drag_waits()

        viewport.select_feature("hole_2")

        assert not viewport.slot_drag_waits(), "der Zug geht mit seinem Griff"
        assert not viewport._slot_target
        assert viewport._drag_kind != "slot"
        viewport.apply_slot_drag(40.0, 15.0)
        assert not gemeldet, "und schreibt nichts an ein fremdes Loch"
    finally:
        viewport.renderer = None
        viewport.deleteLater()


def test_a_slot_shows_a_letter_for_every_arrow_and_every_knob(qt_app: object) -> None:
    """Der Buchstabe ist die zweite Kodierung des Griffs (Regel 18).

    Bis zum 11.09.2026 hatte das Langloch keinen Bewegungsgriff, und dieser
    Test hielt fest, dass dann auch kein X, Y, Z im Bild steht. Seit RM-153
    hat es ihn — und damit gehören die drei Buchstaben dazu, neben den zwei L
    der Knöpfe. Gezählt wird der letzte Satz, nicht die Summe: Jeder Aufbau
    schreibt seine Beschriftung neu, und ``labelled`` sammelt über die Zeit.
    """
    from app.ui.viewport import Viewport

    load_operations()
    viewport = Viewport()
    try:
        renderer = RecordingRenderer(size=(800, 600))
        viewport.renderer = renderer
        a_slot_in_the_view(viewport)
        viewport.set_gizmo(False)

        geschrieben = [texts for texts in renderer.labelled if "X" in texts or "L" in texts][-1]

        assert viewport._gizmo is not None, "am Langloch steht der Bewegungsgriff"
        assert {"X", "Y", "Z"} <= set(geschrieben), geschrieben
        assert geschrieben.count("L") == 2, "die zwei Knöpfe tragen ihr L"
        assert "S" not in geschrieben, "kein Würfel, kein S"
        assert geschrieben[-1].endswith("mm"), "und die Länge steht als Maß daneben"
    finally:
        viewport.renderer = None
        viewport.deleteLater()


def test_a_click_without_a_drag_asks_for_nothing(qt_app: object) -> None:
    """Ein Antippen ist kein Zug — und öffnet keine Leiste.

    Gemessen im Review: Klick auf einen Knopf ohne Mausbewegung, und die Leiste
    stand mit ``(6,30 | 0°)`` da — der Mindestlänge, die niemand gewählt hat.
    """
    renderer = RecordingRenderer(size=(800, 600))
    taken: list[tuple[float, float]] = []
    handle = a_handle(renderer, taken)

    seat = renderer.world_to_display((BORE / 2.0, 0.0, 5.0))
    renderer.item_picks[(round(seat[0]), round(seat[1]))] = handle.knobs[0]
    handle.handle(PointerEvent("move", int(seat[0]), int(seat[1])))
    handle.handle(PointerEvent("press", int(seat[0]), int(seat[1]), button="left"))
    handle.handle(PointerEvent("release", int(seat[0]), int(seat[1]), button="left"))

    assert not taken, "ohne Bewegung ist nichts gezogen worden"


def test_the_knobs_leave_the_hole_they_sit_on_clickable(qt_app: object) -> None:
    """Zwei Knöpfe, die zusammen breiter sind als ihre Lücke, verstecken das Loch.

    Gemessen im Review: Bei Ø 1 deckten sie 100 Prozent der Mündung ab, bei Ø 2
    noch 57,7, und unter Ø 1,68 überlappten sie einander — die Lehre von
    ``_face_handle`` war zurück („Ein Klick auf die Bohrung traf den Griff
    statt des Körpers", Robert, 03.09.2026).
    """
    from app.ui.slot_handle import KNOB_RADIUS_SHARE, WIDEST_KNOB_SHARE

    renderer = RecordingRenderer(size=(800, 600))
    for diameter in (1.0, 2.0, 6.0, 20.0):
        handle = SlotHandle(
            renderer,
            centre=(0.0, 0.0, 5.0),
            axis=(0.0, 0.0, 1.0),
            diameter=diameter,
            length=diameter,
            angle=0.0,
            # Die Ansicht deckelt nach unten; hier steht der ungünstigste Fall.
            knob_size=max(diameter, 4.0),
            colour="#ff9f1c",
            release_callback=lambda _length, _angle: None,
        )
        breite = 2.0 * handle._knob_size * KNOB_RADIUS_SHARE
        assert breite <= handle.length * WIDEST_KNOB_SHARE + 1e-9, (
            f"Ø {diameter}: die Knöpfe decken das Loch zu ({breite:.2f} von {handle.length:.2f})"
        )
        handle.remove()


def test_the_knobs_stay_on_the_outline_across_two_drags() -> None:
    """Der Versatz eines Knopfes zählt gegen die gebaute Geometrie, nicht gegen den Zug.

    ``Item.set_position`` verschiebt gegen das, was einmal in den Puffer
    geschrieben wurde. Gerechnet wurde der Bezug bis zum 10.09.2026 aus
    ``_start_length``/``_start_angle`` — und die setzt der **zweite** Druck neu.
    Beim ersten Zug ist das dasselbe, danach nicht mehr: Der Bezug wandert mit,
    der Puffer bleibt, und die Knöpfe laufen aus dem Umriss heraus — die
    beiden in entgegengesetzte Richtungen, weil ihr ``reach`` das Vorzeichen
    tauscht (Robert: „wenn ich das langloch ziehe driften die ziehpunkte für
    das langloch ab … sie bewegen sich entgegengesetzt").

    **Zwei Züge, und der zweite ist die Messung.** Der erste hält beide Wege
    zusammen und blieb auch mit dem Fehler grün; ein Test, der nur ihn fährt,
    misst nichts. Gemessen wird die Stelle **im Bild** — gebauter Sitz plus
    Versatz — gegen das, was der Griff selbst als Sitz nennt.
    """
    renderer = RecordingRenderer(size=(800, 600))
    handle = a_handle(renderer, [])
    gebaut = [np.asarray(seat, dtype=float) for seat in handle._built_seats]

    def zieh(bis: float) -> None:
        seat = renderer.world_to_display(handle.knob_seats[0])
        renderer.item_picks[(round(seat[0]), round(seat[1]))] = handle.knobs[0]
        handle.handle(PointerEvent("move", int(seat[0]), int(seat[1])))
        handle.handle(PointerEvent("press", int(seat[0]), int(seat[1]), button="left"))
        ziel = renderer.world_to_display((bis, 0.0, 5.0))
        handle.handle(PointerEvent("move", int(ziel[0]), int(ziel[1])))
        handle.handle(PointerEvent("release", int(ziel[0]), int(ziel[1]), button="left"))

    try:
        for nummer, bis in enumerate((12.0, 25.0), start=1):
            zieh(bis)
            for index, item in enumerate(handle.knobs):
                im_bild = gebaut[index] + np.asarray(item.position(), dtype=float)
                soll = np.asarray(handle.knob_seats[index], dtype=float)
                assert np.allclose(im_bild, soll, atol=1e-9), (
                    f"Zug {nummer}, Knopf {index}: im Bild {im_bild}, gemeint {soll}"
                )
    finally:
        handle.remove()
