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
from app.ui.slot_handle import SlotHandle, dragged_slot, settled_length, slot_outline
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


def test_a_drag_into_the_middle_snaps_to_the_round_bore(profile: Profile) -> None:
    """Eine Geste, die in einer Absage endet, ist keine Bedienung.

    ``slot_hole`` lehnt jede Länge zwischen der Breite und
    :func:`prepare.shortest_slot` ab. Der Griff zieht deshalb nie dorthin: Die
    obere Hälfte des Streifens hält die kürzeste Länge, die untere rastet auf
    die Breite selbst — die runde Bohrung (Robert, 24.09.2026: „wenn man ein
    langloch so zieht, dass es wieder eine normale Bohrung wäre, sollte es
    kurz einrasten"). Ein Zeiger auf der Mitte meint also das runde Loch, und
    die Operation nimmt es an: An einer runden Bohrung ändert sich dann nichts.
    """
    entry = a_drilled_plate(profile)
    bore = the_bore(entry)
    # Gegen den **gemessenen** Durchmesser: Die Erkennung liest das facettierte
    # Netz, und das ist nicht auf die Stelle genau der Wert, mit dem gebohrt
    # wurde. Der Griff rechnet mit dem, was am Merkmal steht — wie die
    # Operation auch.
    width = float(bore.params["diameter"])
    shortest = shortest_slot(width)

    assert pulled_to(bore, 0.0, 0.0)[0] == pytest.approx(width), "auf der Mitte: rund"
    assert pulled_to(bore, 0.0, (width + shortest) / 4.0 - 0.01)[0] == pytest.approx(width)
    assert pulled_to(bore, 0.0, (width + shortest) / 4.0 + 0.01)[0] == pytest.approx(shortest)
    gezogen = run_op(
        "slot_hole", entry, profile, at_feature=bore.id, slot_length=width, slot_angle=0.0
    )
    assert gezogen.mesh is entry.mesh, "die runde Bohrung bleibt, wie sie ist"


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

    # Knapp über der Mitte des Streifens zwischen Breite und kürzester Länge:
    # Dort hält der Griff den Anschlag, darunter rastet er auf rund.
    shortest = shortest_slot(float(bore.params["diameter"]))
    length, _turned = pulled_to(bore, 0.0, 0.99 * shortest / 2.0)
    assert length == pytest.approx(shortest)
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


@pytest.mark.parametrize("towards", [0.0, 40.0, 200.0])
def test_the_handle_reads_a_world_direction_as_the_same_angle_at_a_noisy_axis(
    towards: float,
) -> None:
    """Ein Zug entlang +Y heißt 90°, auch wenn die Achse im Messrauschen neben Z steht.

    Der Griff zählt gegen denselben Rahmen wie der Schnitt
    (``prepare.slot_frame``). Am Besenhalter (Achsen 4e-8 rad neben Z) und an
    der vernetzten Teppichecke (0,02° bis 0,07°) zeigte Winkel 0 bis zum
    30.09.2026 in eine Richtung, die das Rauschen bestimmte — derselbe Zug zur
    selben Wand ergab an jeder Bohrung eine andere Zahl. Hier steht die Achse
    0,03° neben Z, in drei Richtungen gekippt; Zug und Umriss bleiben bei +Y.
    """
    tilt = math.radians(0.03)
    axis = (
        math.sin(tilt) * math.cos(math.radians(towards)),
        math.sin(tilt) * math.sin(math.radians(towards)),
        math.cos(tilt),
    )
    centre = (2.0, -3.0, 5.0)

    length, angle = dragged_slot(centre, axis, BORE, (centre[0], centre[1] + 12.0, centre[2]))
    drawn = slot_outline(centre, axis, BORE, 24.0, 90.0)

    assert length == pytest.approx(24.0, abs=1e-3)
    assert angle == pytest.approx(90.0, abs=0.5)
    spread = np.ptp(drawn, axis=0)
    assert spread[1] == pytest.approx(24.0, abs=0.05), "der Umriss liegt entlang +Y"
    assert spread[0] == pytest.approx(BORE, abs=0.05)


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


def test_a_narrower_width_allows_the_handle_to_shrink_below_its_old_width() -> None:
    """Breite und Länge stammen aus demselben Entwurf, auch beim Verkleinern."""
    renderer = RecordingRenderer(size=(800, 600))
    handle = a_handle(renderer, [])
    handle.set_values(4.5, 0.0, diameter=4.0)
    assert handle.length == pytest.approx(4.5)
    assert handle.radius == pytest.approx(2.0)
    assert np.ptp(handle._outline.points[:, 1]) == pytest.approx(4.0)
    assert np.ptp(handle._outline.points[:, 0]) == pytest.approx(4.5)


@pytest.mark.parametrize("begun", [False, True])
def test_a_slot_proposal_keeps_the_bore_draft_when_changing_its_measure_fields(begun: bool) -> None:
    """Der Signalanschluss übergibt einen begonnenen Entwurf ohne fremde Handlung."""
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow
    from app.ui.placement_flow import QuietHost

    host = QuietHost(
        {
            "at_feature": "hole_1",
            "diameter": 7.0,
            "compensate": True,
            "x": 11.0,
            "y": 13.0,
            "z": 5.0,
        },
        lambda values: False,
    )
    if begun:
        host.begin_edit()
    events = []
    state = SimpleNamespace(
        _quiet_placement=SimpleNamespace(spec_of=lambda: SimpleNamespace(name="resize_hole")),
        _quiet_host=host,
        _quiet_target=("obj_1", "hole_1"),
        object_tree=SimpleNamespace(selected=lambda: "obj_1"),
        end_quiet_placement=lambda: events.append("end"),
        feature_panel=SimpleNamespace(
            take_values=lambda op, values: events.append((op, dict(values)))
        ),
        _place_from_feature_panel=lambda op, values, **kwargs: events.append(
            (op, dict(values), kwargs)
        ),
    )
    MainWindow._on_slot_proposed(state, "hole_1", 18.0, 30.0)
    assert events[0] == "end", "erst den alten Besitzer lösen, dann die Handlung wechseln"
    assert events[1][0] == events[2][0] == "slot_hole"
    assert events[2][1] == {**host.values(), "slot_length": 18.0, "slot_angle": 30.0}
    assert events[2][2] == {"editing": True}, "der erste Zug ist bereits eine Eingabe"


@pytest.mark.parametrize(
    ("running", "armed", "begun", "feature", "handed"),
    [
        # Die zwei Zwillinge am Loch geben einander die Maßgruppe weiter.
        ("resize_hole", "slot_hole", False, "hole_1", True),
        ("slot_hole", "resize_hole", False, "hole_1", True),
        # Ein begonnener Entwurf bleibt bei seiner Handlung.
        ("resize_hole", "slot_hole", True, "hole_1", False),
        # Ein anderes Merkmal ist kein Zwilling dieses Entwurfs.
        ("resize_hole", "slot_hole", False, "hole_2", False),
        # *Merkmal verschieben* hat keinen Weg ins Bild und beendet sie wie bisher.
        ("resize_hole", "move_feature", False, "hole_1", False),
    ],
)
def test_the_twin_field_in_the_panel_takes_over_the_measures_in_the_view(
    running: str, armed: str, begun: bool, feature: str, handed: bool
) -> None:
    """Ein Klick in das Feld des Zwillings rechts hält die Maße im Bild (24.09.2026).

    An einer Bohrung steht *Bohrung ändern* im Bild und *Zum Langloch ziehen*
    rechts. Ein Klick in dessen Längenfeld beendete die Maßgruppe: Maßlinien,
    Knöpfe und Umriss verschwanden, und die Länge wurde ohne jedes Maß zur
    Kante getippt (Robert: „die maße fehlen auch beim langloch"). Jetzt
    übernimmt die angefasste Handlung die Maßgruppe, mit den Werten des Felds.
    """
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow
    from app.ui.placement_flow import QuietHost

    host = QuietHost({"at_feature": "hole_1", "diameter": 5.2}, lambda values: False)
    if begun:
        host.begin_edit()
    started = []
    state = SimpleNamespace(
        _quiet_placement=SimpleNamespace(spec_of=lambda: SimpleNamespace(name=running)),
        _quiet_host=host,
        _quiet_target=("obj_1", "hole_1"),
        object_tree=SimpleNamespace(selected=lambda: "obj_1", selected_feature=lambda: "hole_1"),
        feature_panel=SimpleNamespace(armed_by_tab=lambda: False),
        _place_from_feature_panel=lambda op, params, **kwargs: started.append(
            (op, dict(params), kwargs)
        ),
    )
    values = {"at_feature": feature, "slot_length": 18.0, "slot_angle": 0.0}

    assert MainWindow._hand_the_measures_over(state, armed, values) is handed
    assert started == ([(armed, values, {})] if handed else [])

    # **Tab bleibt im Fenster** (Review 24.09.2026): Wer mit der Tastatur in
    # das Feld des Zwillings geht, holt es nicht ins Bild.
    started.clear()
    state.feature_panel = SimpleNamespace(armed_by_tab=lambda: True)
    assert not MainWindow._hand_the_measures_over(state, armed, values)
    assert not started


@pytest.mark.parametrize("armed_opens_measures", [False, True])
def test_a_pull_without_measures_starts_an_editable_slot_draft(armed_opens_measures: bool) -> None:
    """Nach Escape startet der nächste Zug samt Werten und freigegebener Bearbeitung."""
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow
    from app.ui.placement_flow import QuietHost

    values = {"at_feature": "slot_1", "diameter": 4.0, "compensate": False}
    host = QuietHost(values, lambda values: False)
    started = []

    def take_values(op, proposed):
        values.update(proposed)
        if armed_opens_measures:
            state._quiet_placement = SimpleNamespace(
                active=True, spec_of=lambda: SimpleNamespace(name="slot_hole")
            )
            state._quiet_host = host
        return True

    state = SimpleNamespace(
        _quiet_placement=None,
        _quiet_host=None,
        object_tree=SimpleNamespace(selected_feature=lambda: "slot_1"),
        feature_panel=SimpleNamespace(
            take_values=take_values, preview_values=lambda: ("slot_hole", dict(values))
        ),
        _place_from_feature_panel=lambda op, params, **kwargs: started.append(
            (op, dict(params), kwargs)
        ),
    )
    MainWindow._on_slot_proposed(state, "slot_1", 12.0, 30.0)
    if armed_opens_measures:
        assert host.begun and host.values() == values
        assert not started
    else:
        assert started == [("slot_hole", values, {"editing": True})]


@pytest.mark.parametrize("allowed", [False, True])
def test_a_cross_axis_turn_checks_the_current_draft_before_changing_the_panel(
    allowed: bool,
) -> None:
    """Der Ring darf keine fremde Karte aktivieren, während der Langlochentwurf gebunden ist."""
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow

    events = []

    def may_change():
        events.append("check")
        return allowed

    state = SimpleNamespace(
        _quiet_placement=SimpleNamespace(spec_of=lambda: SimpleNamespace(name="slot_hole")),
        _quiet_command_allowed=may_change,
        feature_panel=SimpleNamespace(
            take_values=lambda op, values: events.append((op, values)) or True
        ),
    )
    MainWindow._on_feature_turn_proposed(state, "slot_1", "x", 30.0)
    assert events == (
        ["check", ("rotate_feature", {"axis": "x", "angle": 30.0})] if allowed else ["check"]
    )


def test_a_slot_gesture_does_not_discard_an_unfinished_depth_change() -> None:
    """Eine noch offene Tiefenänderung gehört weiter dem Bohrungsentwurf."""
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow
    from app.ui.placement_flow import QuietHost

    host = QuietHost({"at_feature": "hole_1", "diameter": 6.0, "depth": 4.0}, lambda values: False)
    host.begin_edit()
    events = []
    feature = Feature(
        id="hole_1", kind="hole", provenance="detected", params={"depth": 10.0, "through": True}
    )
    state = SimpleNamespace(
        _quiet_placement=SimpleNamespace(spec_of=lambda: SimpleNamespace(name="resize_hole")),
        _quiet_host=host,
        _quiet_target=("obj_1", "hole_1"),
        object_tree=SimpleNamespace(selected=lambda: "obj_1"),
        _selected_feature_object=lambda: feature,
        viewport=SimpleNamespace(cancel_slot_drag=lambda: events.append("cancel_slot")),
        _say_the_change_comes_first=lambda: events.append("explain"),
    )
    MainWindow._on_slot_proposed(state, "hole_1", 18.0, 30.0)
    assert events == ["cancel_slot", "explain"]
    assert host.begun and host.values()["depth"] == pytest.approx(4.0)


def test_a_slot_step_takes_the_new_width_from_its_measure_fields(profile: Profile) -> None:
    """Die Vorschaufreigabe für einen bestehenden Schritt enthält auch seine Breite."""
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow

    feature = Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        created_by=2,
        params={
            "diameter": 6.0,
            "length": 20.0,
            "axis": (0.0, 0.0, 1.0),
            "direction": (1.0, 0.0, 0.0),
            "centre": (0.0, 0.0, 0.0),
        },
    )
    entry = SceneObject(
        id="obj_1",
        name="Platte",
        mesh=MeshData.of(trimesh.creation.box()),
        features={feature.id: feature},
    )
    state = SimpleNamespace(
        object_tree=SimpleNamespace(selected=lambda: entry.id),
        session=SimpleNamespace(
            profile=profile,
            last_result=SimpleNamespace(scene=Scene(objects={entry.id: entry})),
            project=SimpleNamespace(
                document=SimpleNamespace(ops=[SimpleNamespace(id=2, op="slot_hole")])
            ),
        ),
    )
    order = MainWindow._prepare_slot_change(
        state, feature.id, {"diameter": 4.0, "compensate": False}
    )
    assert order.change_op == 2
    assert order.change_values == {"diameter": 4.0, "compensate": False}
    assert feature.params["diameter"] == pytest.approx(6.0), "der Entwurf ändert keine Geometrie"


@pytest.mark.parametrize("entered, shown", [(5.0, 5.0), (4.3, 4.4), (4.0, 4.0), (1.0, 4.4)])
def test_a_rebound_slot_draft_survives_until_the_handle_is_rebuilt(
    entered: float, shown: float
) -> None:
    """Der Editorwechsel räumt den Griff ab; sein Entwurf muss den Neuaufbau überleben."""
    from functools import partial
    from types import SimpleNamespace

    from app.ui.viewport import Viewport

    renderer = RecordingRenderer(size=(800, 600))
    state = SimpleNamespace(
        _slot_target="",
        _slot_waiting=None,
        _slot_width=None,
        _slot_handle=None,
        renderer=renderer,
        _face_seat=((0.0, 0.0, 5.0), (0.0, 0.0, 1.0), 3.0),
        _on_slot_released=lambda *_args: None,
        _on_slot_interacted=lambda *_args: None,
        _on_slot_interaction_cancelled=lambda: None,
        _settled_angle=lambda value: value,
    )
    state.waiting_slot_drag = partial(Viewport.waiting_slot_drag, state)
    feature = Feature(
        id="slot_1",
        kind="slot",
        provenance="detected",
        params={
            "length": 20.0,
            "diameter": 6.0,
            "axis": (0.0, 0.0, 1.0),
            "direction": (1.0, 0.0, 0.0),
        },
    )
    Viewport.reshape_slot(state, entered, 30.0, diameter=4.0, feature_id=feature.id)
    assert state._slot_waiting == pytest.approx((shown, 30.0)), "auch ohne Griff gültig zeichnen"
    Viewport._attach_slot_handle(state, feature)
    handle = state._slot_handle
    assert handle is not None and handle.length == pytest.approx(shown)
    assert handle.angle == pytest.approx(30.0) and handle.radius == pytest.approx(2.0)
    assert handle._outline is not None


def test_a_slot_draft_moves_its_handles_only_when_the_target_centre_changes() -> None:
    """Panelkoordinaten versetzen dieselben Griffe; die Rückmeldung baut sie nicht erneut."""
    from types import SimpleNamespace

    from app.ui.viewport import Viewport

    feature = Feature(
        id="slot_1", kind="slot", provenance="detected", params={"centre": (1.0, 2.0, 3.0)}
    )
    rebuilt = []
    state = SimpleNamespace(
        _slot_handle=None,
        _slot_target="",
        _slot_width=None,
        _move_target="",
        _grip_shift=(0.0, 0.0, 0.0),
        _gizmo_wanted=True,
        slot_handle_feature=lambda: feature,
        set_gizmo=lambda wanted: rebuilt.append((wanted, state._grip_shift)),
    )
    for _ in range(2):
        Viewport.reshape_slot(
            state, 12.0, 30.0, diameter=4.0, feature_id=feature.id, centre=(7.0, 6.0, 3.0)
        )
    assert state._move_target == feature.id
    assert rebuilt == [(True, (6.0, 4.0, 0.0))]


def test_cancelling_the_slot_measures_restores_the_panels_actual_values() -> None:
    """Abbrechen beendet den Entwurf und liest die noch unveränderte Merkmalskarte neu."""
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow

    selected = []
    state = SimpleNamespace(
        _leave_the_measures=lambda: True,
        object_tree=SimpleNamespace(selected_feature=lambda: "slot_1"),
        _on_feature_selected=selected.append,
        _click_after_evaluation=None,
        feature_panel=SimpleNamespace(),
    )
    state._drop_click_of = lambda owner: MainWindow._drop_click_of(state, owner)
    MainWindow._cancel_from_feature_panel(state)
    assert selected == ["slot_1"]


def test_accepting_identical_slot_values_keeps_the_outline_while_preparation_is_pending() -> None:
    """Ein noch nicht möglicher Abschluss erhält den Griff auch ohne neues Wertesignal."""
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow
    from app.ui.placement_flow import QuietHost
    from app.ui.viewport import Viewport

    values = {"at_feature": "slot_1", "slot_length": 12.0, "slot_angle": 30.0, "diameter": 4.0}
    host = QuietHost(values, lambda values: False)
    host.begin_edit()
    changed = []
    host.valuesChanged.connect(lambda: changed.append(True))
    viewport = SimpleNamespace(_slot_handle=None, _slot_target="", _slot_width=None)
    attempts = []
    state = SimpleNamespace(
        _quiet_host=host,
        _quiet_placement=SimpleNamespace(
            spec_of=lambda: SimpleNamespace(name="slot_hole"),
            accept=lambda: attempts.append(viewport._slot_waiting),
        ),
        _reshape_slot_from_values=lambda params: Viewport.reshape_slot(
            viewport,
            params["slot_length"],
            params["slot_angle"],
            diameter=params["diameter"],
            feature_id=params["at_feature"],
        ),
    )
    MainWindow._on_slot_dragged(state, "slot_1", 12.0, 30.0)
    assert not changed, "identische Werte liefern kein neues Signal"
    assert attempts == [(12.0, 30.0)]
    assert viewport._slot_target == "slot_1" and viewport._slot_width == pytest.approx(4.0)
    assert host.begun and host.values() == values


def test_the_slot_panel_commits_all_fields_of_its_preview() -> None:
    """Ein wartender Griff darf beim Panelabschluss die Breite nicht abschneiden."""
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow

    taken = []
    state = SimpleNamespace(
        _quiet_placement=None,
        _quiet_host=None,
        _end_changed_quiet_placement=lambda: None,
        viewport=SimpleNamespace(slot_drag_waits=lambda: True),
        _apply_placed_feature=lambda op, params: taken.append((op, dict(params))),
    )
    values = {
        "at_feature": "slot_1",
        "slot_length": 12.0,
        "slot_angle": 30.0,
        "diameter": 4.0,
        "compensate": True,
        "x": 8.0,
        "y": 9.0,
        "z": 5.0,
    }
    MainWindow._apply_from_feature_panel(state, "slot_hole", values)
    assert taken == [("slot_hole", values)]


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
    # Gebaut an der runden Bohrung, gezogen auf 18: Der Versatz der Knöpfe ist
    # die halbe Differenz — und genau darauf setzt der fremde Zug auf.
    pulled = 9.0 - BORE / 2.0
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
    # Zehn Bildpunkte je Millimeter: Der Knopfsitz fällt auf einen ganzen
    # Bildpunkt, und die Hand greift ihn genau.
    renderer = RecordingRenderer(size=(800, 600), scale=10.0)
    taken: list[tuple[float, float]] = []
    handle = a_handle(renderer, taken)

    # Der rechte Knopf sitzt auf dem Rand der runden Bohrung, x = 3,0 — dort
    # greift die Hand, und der Knopf wandert um ihren Weg.
    seat = renderer.world_to_display(handle.knob_seats[0])
    x, y = round(seat[0]), round(seat[1])
    renderer.item_picks[(x, y)] = handle.knobs[0]
    handle.handle(PointerEvent("move", x, y))
    assert handle.handle(PointerEvent("press", x, y, button="left"))

    target = renderer.world_to_display((12.0, 0.0, 5.0))
    assert handle.handle(PointerEvent("move", round(target[0]), round(target[1])))
    assert handle.handle(PointerEvent("release", round(target[0]), round(target[1]), button="left"))

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
    renderer = RecordingRenderer(size=(800, 600), scale=10.0)
    taken: list[tuple[float, float]] = []
    handle = a_handle(renderer, taken)

    # Diesmal der linke Knopf, und gezogen wird nach links.
    seat = renderer.world_to_display(handle.knob_seats[1])
    x, y = round(seat[0]), round(seat[1])
    renderer.item_picks[(x, y)] = handle.knobs[1]
    handle.handle(PointerEvent("move", x, y))
    handle.handle(PointerEvent("press", x, y, button="left"))
    target = renderer.world_to_display((-10.0, 0.0, 5.0))
    handle.handle(PointerEvent("move", round(target[0]), round(target[1])))
    handle.handle(PointerEvent("release", round(target[0]), round(target[1]), button="left"))

    length, angle = taken[0]
    assert length == pytest.approx(20.0, abs=0.01)
    # Nach links gezogen heißt dieselbe Achse — der Winkel zeigt zurück auf 0,
    # weil der gegriffene Knopf der gegenüberliegende ist.
    assert angle == pytest.approx(0.0, abs=0.01)


def test_a_press_into_the_opening_of_a_slot_moves_the_knob_by_the_pointers_way() -> None:
    """Wer ins Langloch drückt und zieht, verschiebt den Knopf, er springt nicht.

    Langloch Ø 6 auf 30 mm entlang x, der rechte Knopf am Scheitel x = 15.
    Gedrückt wird im Endbogen neben dem Knopf, bei (13 | 2), und acht
    Millimeter zur Mitte gezogen. Der Knopf wandert mit: (15 - 8 | 0), also
    14 mm lang in der alten Richtung. Vom Zeiger aus gerechnet stünde er bei
    (5 | 2) — 2 · √29 ≈ 10,8 mm lang und 21,8 Grad gedreht.
    """
    renderer = RecordingRenderer(size=(800, 600))
    taken: list[tuple[float, float]] = []
    handle = a_handle(renderer, taken)
    handle.set_values(30.0, 0.0)

    press = renderer.world_to_display((13.0, 2.0, 5.0))
    assert handle.take_press(PointerEvent("press", int(press[0]), int(press[1]), button="left"), 0)
    target = renderer.world_to_display((5.0, 2.0, 5.0))
    handle.handle(PointerEvent("move", int(target[0]), int(target[1])))
    handle.handle(PointerEvent("release", int(target[0]), int(target[1]), button="left"))

    length, angle = taken[0]
    assert length == pytest.approx(14.0, abs=0.05)
    assert angle == pytest.approx(0.0, abs=0.5)


def test_a_slot_pulled_back_into_its_bore_snaps_round() -> None:
    """Zurück bis in das Loch hinein rastet der Zug auf die runde Bohrung.

    Langloch Ø 6 auf 30 mm, der rechte Knopf am Scheitel x = 15. Er wird bis
    x = 2 zurückgezogen — mitten in die Bohrung, deren Rand bei x = 3 liegt.
    Gemeldet wird die Breite als Länge, in der Richtung, die galt; der Umriss
    ist ein Kreis vom Radius 3 um die Mitte, mit derselben Punktzahl wie
    vorher.
    """
    renderer = RecordingRenderer(size=(800, 600), scale=10.0)
    taken: list[tuple[float, float]] = []
    handle = a_handle(renderer, taken)
    handle.set_values(30.0, 20.0)
    seat = renderer.world_to_display(handle.knob_seats[0])
    x, y = round(seat[0]), round(seat[1])
    renderer.item_picks[(x, y)] = handle.knobs[0]
    handle.handle(PointerEvent("move", x, y))
    handle.handle(PointerEvent("press", x, y, button="left"))
    outward = renderer.world_to_display((16.0, 0.0, 5.0))
    handle.handle(PointerEvent("move", round(outward[0]), round(outward[1])))
    drawn = len(handle._outline.points)
    inside = renderer.world_to_display((2.0, 0.0, 5.0))
    handle.handle(PointerEvent("move", round(inside[0]), round(inside[1])))
    handle.handle(PointerEvent("release", round(inside[0]), round(inside[1]), button="left"))

    assert taken == [(pytest.approx(BORE), pytest.approx(20.0))]
    ring = np.asarray(handle._outline.points)
    assert len(ring) == drawn, "dieselbe Punktzahl — der Renderer tauscht nur Punkte"
    assert np.hypot(ring[:, 0], ring[:, 1]) == pytest.approx(np.full(len(ring), BORE / 2.0))


@pytest.mark.parametrize("knob", [0, 1])
def test_a_round_bore_pulled_out_and_back_asks_for_nothing(knob: int) -> None:
    """Eine runde Bohrung, hinaus und wieder auf rund gezogen, ist kein Vorschlag.

    **An beiden Knöpfen.** Am linken spiegelte der Griff die Richtung, die beim
    Einrasten gar nicht vom Zeiger kam, und aus 0 Grad wurden 180 — ein
    Vorschlag ohne Wirkung (Review 24.09.2026).
    """
    renderer = RecordingRenderer(size=(800, 600), scale=10.0)
    taken: list[tuple[float, float]] = []
    cancelled: list[bool] = []
    handle = a_handle(renderer, taken)
    handle._cancel = lambda: cancelled.append(True)
    assert handle.length == pytest.approx(BORE), "die Knöpfe sitzen auf dem Rand"
    seat = renderer.world_to_display(handle.knob_seats[knob])
    x, y = round(seat[0]), round(seat[1])
    renderer.item_picks[(x, y)] = handle.knobs[knob]
    handle.handle(PointerEvent("move", x, y))
    handle.handle(PointerEvent("press", x, y, button="left"))
    side = 1.0 if knob == 0 else -1.0
    away = renderer.world_to_display((12.0 * side, 5.0 * side, 5.0))
    handle.handle(PointerEvent("move", round(away[0]), round(away[1])))
    back = renderer.world_to_display((1.0 * side, 0.5 * side, 5.0))
    handle.handle(PointerEvent("move", round(back[0]), round(back[1])))
    assert handle.angle == pytest.approx(0.0), "eingerastet bleibt die Richtung, die galt"
    handle.handle(PointerEvent("release", round(back[0]), round(back[1]), button="left"))

    assert not taken
    assert cancelled == [True]


def test_a_typed_length_between_round_and_slot_does_not_snap_round() -> None:
    """Eine eingetragene Zahl rastet nicht: Rund zeigt der Umriss nur genau auf der Breite.

    Zwischen Breite und kürzester Länge lehnt der Schnitt ab
    (``NEITHER_ROUND_NOR_SLOT``); ein Kreis im Bild verspräche dort die runde
    Bohrung (Review 24.09.2026). Der Zug rastet weiter (``settled_length``).
    """
    renderer = RecordingRenderer(size=(800, 600))
    handle = a_handle(renderer, [])
    shortest = shortest_slot(BORE)
    lower_half = (BORE + shortest) / 2.0 - 0.01
    assert settled_length(lower_half, BORE) == pytest.approx(BORE), "der Zug rastet hier"

    handle.set_values(lower_half, 0.0)
    assert handle.length == pytest.approx(shortest), "die Zahl zeigt die kürzeste Länge"
    handle.set_values(BORE, 0.0)
    assert handle.length == pytest.approx(BORE), "genau die Breite ist rund"


def test_escape_at_the_measures_discards_and_deselects_like_cancel() -> None:
    """Escape tut an der Maßgruppe, was Abbrechen tut (Robert, 25.09.2026).

    Zwei Wege kommen an: die Taste des Fensters (``MainWindow._escape``) und
    Escape in einem Maßfeld (``PlacementFlow.step_back``). Beide verwerfen
    und wählen ab; ein Bezugswahlmodus nimmt das erste Escape weiter für
    sich.
    """
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow
    from app.ui.placement_flow import PlacementFlow, QuietHost

    chosen: list[object] = []
    window = SimpleNamespace(
        # Kein Vorher/Nachher-Vergleich offen: Escape geht an die Maße.
        history_panel=SimpleNamespace(compare=SimpleNamespace(isChecked=lambda: False)),
        _local_features=None,
        _draw_flow=None,
        _disarm_plane_points=lambda: False,
        session=SimpleNamespace(split_running=False, inserting=None),
        _sketch_panel=None,
        _armature_target=None,
        _sculpt_target=None,
        tools=SimpleNamespace(active=lambda: None),
        _leave_the_measures=lambda: True,
        object_tree=SimpleNamespace(select_object=chosen.append),
        _step_selection_out=lambda: pytest.fail("Escape ging an den Maßen vorbei"),
    )
    MainWindow._escape(window)  # type: ignore[arg-type]
    assert chosen == [None], "die Taste des Fensters wählt ab"

    cancelled: list[bool] = []
    picking = {"now": True}
    flow = SimpleNamespace(
        _disposed=False,
        dialog=QuietHost({}, lambda values: False),
        _cancel_reference_pick=lambda: picking["now"],
        _cancel_measures=lambda: cancelled.append(True),
        back=lambda: pytest.fail("Escape im Maßfeld ging den alten Weg"),
    )
    PlacementFlow.step_back(flow)  # type: ignore[arg-type]
    assert not cancelled, "erst geht die Bezugswahl"
    picking["now"] = False
    PlacementFlow.step_back(flow)  # type: ignore[arg-type]
    assert cancelled == [True], "dann wie Abbrechen"


def test_a_round_bore_that_stays_round_proposes_nothing() -> None:
    """Endet ein Zug oder der Ring an einer runden Bohrung rund, wird nichts vorgeschlagen.

    Übernommen stünde sonst ein Schritt im Verlauf, der nur sagt, dass sie
    schon rund ist (Review 24.09.2026). Ein Langloch, das rund wird, und eine
    Bohrung, die länger wird, schlagen weiter vor.
    """
    from types import SimpleNamespace

    from app.ui.viewport import Viewport

    proposed: list[tuple[object, ...]] = []
    cancelled: list[bool] = []
    feature = {"now": SimpleNamespace(id="hole_1", kind="hole")}
    view = SimpleNamespace(
        slot_handle_feature=lambda: feature["now"],
        _slot_handle=SimpleNamespace(radius=3.0),
        _slot_borrowed=True,
        _on_slot_interaction_cancelled=lambda: cancelled.append(True),
        _end_drag=lambda: None,
        _repaint_preview=lambda: None,
        drag_bar=SimpleNamespace(dismiss=lambda: None),
        slotProposed=SimpleNamespace(emit=lambda *values: proposed.append(values)),
    )

    Viewport._on_slot_released(view, 6.0, 90.0)  # type: ignore[arg-type]
    assert cancelled == [True] and not proposed, "rund bleibt rund: kein Vorschlag"

    Viewport._on_slot_released(view, 18.0, 90.0)  # type: ignore[arg-type]
    assert proposed == [("hole_1", 18.0, 90.0)], "länger gezogen: der Vorschlag steht"

    feature["now"] = SimpleNamespace(id="slot_1", kind="slot")
    Viewport._on_slot_released(view, 6.0, 90.0)  # type: ignore[arg-type]
    assert proposed[-1] == ("slot_1", 6.0, 90.0), "ein Langloch, das rund wird, schon"
    assert cancelled == [True]


def test_a_slot_step_pulled_back_to_its_bore_is_taken_out() -> None:
    """Zurück auf die Bohrung, aus der es kam: Der Schritt fällt, statt zu bleiben.

    Welche Bohrung das war, sagt die Sichtung vor dem Schritt. Geprüft wird an
    einem Stellvertreter mit genau den Feldern, die die Prüfung liest.
    """
    from types import SimpleNamespace

    from app.core.types import FeatureRef, ReferenceSight
    from app.ui.main_window import MainWindow

    hole = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"diameter": 6.0, "centre": (10.0, -5.0, 5.0), "axis": (0.0, 0.0, 1.0)},
    )
    step = SimpleNamespace(
        id=2,
        op="slot_hole",
        params={
            "at_feature": "hole_1",
            "slot_length": 20.0,
            "slot_angle": 0.0,
            "x": 10.0,
            "y": -5.0,
            "z": 5.0,
            "diameter": None,
            "compensate": False,
        },
    )
    sight = ReferenceSight(key="at_feature", ref=FeatureRef("obj_1", "hole_1"), feature=hole)
    state = SimpleNamespace(
        session=SimpleNamespace(
            project=SimpleNamespace(document=SimpleNamespace(ops=[step])),
            last_result=SimpleNamespace(sights={2: (sight,)}),
        )
    )

    def undone(**changes: object) -> bool:
        return MainWindow._slot_step_undone(state, 2, changes)  # type: ignore[arg-type]

    assert undone(slot_length=6.0), "rund, an ihrer Stelle, in ihrer Breite"
    assert undone(slot_length=6.004), "die halbe Anzeigestufe ist noch dieselbe Breite"
    assert not undone(slot_length=12.0), "noch ein Langloch"
    assert not undone(slot_length=6.0, x=14.0), "versetzt: der Schritt trägt die Stelle"
    assert not undone(slot_length=6.0, diameter=8.0), "verbreitert: der Schritt trägt die Breite"
    assert not undone(slot_length=6.0, y="=@lage"), "ein Ausdruck lässt sich nicht nachrechnen"
    step.params["x"] = 12.0
    assert not undone(slot_length=6.0), "der Schritt hat die Bohrung schon versetzt"


def test_both_ways_to_accept_a_slot_step_meet_in_one_place() -> None:
    """Merkmalfenster und Maßgruppe schreiben einen Langlochschritt an derselben Stelle.

    Beide übernehmen über ``_commit_preview_order``. Am Scraper-Modell
    (24.09.2026) saß die Prüfung „zurück auf die Bohrung" nur in
    ``_change_slot_step``, einer Methode ohne Aufrufer: Das Übernehmen änderte
    den Schritt auf Länge = Breite, statt ihn fallen zu lassen. Jetzt prüft
    ``_commit_slot_change`` am gemeinsamen Weg, und die tote Methode ist weg.
    """
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow, _PreviewOrder

    committed: list[tuple[int, dict[str, object]]] = []
    removed: list[list[int]] = []
    changed: list[tuple[int, dict[str, object]]] = []
    said: list[str] = []
    undone = {"now": True}
    state = SimpleNamespace(
        session=SimpleNamespace(
            history=SimpleNamespace(operation=lambda op_id: SimpleNamespace(op="slot_hole")),
            remove_operations=lambda ids: removed.append(list(ids)) or True,
            change_params=lambda op_id, values: changed.append((op_id, values)) or True,
        ),
        _slot_step_undone=lambda step_id, changes: undone["now"],
        _slot_named_later=lambda step_id: False,
        announce=lambda text: said.append(str(text)),
    )
    state._commit_slot_change = lambda step_id, changes: (
        committed.append((step_id, changes))
        or MainWindow._commit_slot_change(state, step_id, changes)  # type: ignore[arg-type]
    )

    order = _PreviewOrder(change_op=2, change_values={"slot_length": 6.0})
    assert MainWindow._commit_preview_order(state, order)  # type: ignore[arg-type]
    assert committed == [(2, {"slot_length": 6.0})]
    assert removed == [[2]] and not changed, "zurück auf die Bohrung: der Schritt fällt"
    assert said, "und es wird gesagt"

    undone["now"] = False
    assert MainWindow._commit_preview_order(state, order)  # type: ignore[arg-type]
    assert changed == [(2, {"slot_length": 6.0})], "sonst wird er geändert"


def test_a_slot_step_named_by_a_later_step_is_changed_not_taken_out() -> None:
    """Nennt ein späterer Schritt das Langloch, fällt sein Schritt nicht.

    Eine Fase an ``slot_1`` verwiese sonst auf ein Merkmal, das der Verlauf nie
    erzeugt hat (Review 24.09.2026). Geändert wird der Schritt trotzdem; der
    Kern sagt dann, dass aus dem Langloch wieder eine Bohrung geworden ist.
    """
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow

    features = {
        "slot_1": SimpleNamespace(created_by=2),
        "hole_2": SimpleNamespace(created_by=None),
    }
    ops = [
        SimpleNamespace(id=1, params={}),
        SimpleNamespace(id=2, params={"at_feature": "hole_1"}),
        SimpleNamespace(id=3, params={"at_feature": "hole_2"}),
    ]
    removed: list[list[int]] = []
    changed: list[int] = []
    state = SimpleNamespace(
        session=SimpleNamespace(
            last_result=SimpleNamespace(
                scene=SimpleNamespace(objects={"obj_1": SimpleNamespace(features=features)})
            ),
            project=SimpleNamespace(document=SimpleNamespace(ops=ops)),
            remove_operations=lambda ids: removed.append(list(ids)) or True,
            change_params=lambda op_id, values: changed.append(op_id) or True,
        ),
        _slot_step_undone=lambda step_id, changes: True,
        announce=lambda text: None,
    )
    state._slot_named_later = lambda step_id: MainWindow._slot_named_later(state, step_id)  # type: ignore[arg-type]

    assert not MainWindow._slot_named_later(state, 2)  # type: ignore[arg-type]
    assert MainWindow._commit_slot_change(state, 2, {"slot_length": 6.0})  # type: ignore[arg-type]
    assert removed == [[2]] and not changed, "niemand nennt es: der Schritt fällt"

    ops.append(SimpleNamespace(id=4, params={"at_features": ["slot_1"]}))
    assert MainWindow._slot_named_later(state, 2)  # type: ignore[arg-type]
    assert MainWindow._commit_slot_change(state, 2, {"slot_length": 6.0})  # type: ignore[arg-type]
    assert removed == [[2]] and changed == [2], "genannt: geändert statt entfernt"


def test_a_press_into_a_round_bore_pulls_it_out_in_the_hands_direction() -> None:
    """An der runden Bohrung bleibt der Zug aus der Mitte heraus.

    Sie hat keine Richtung, die zu erhalten wäre: Gedrückt bei (1 | 0) und
    nach (1 | 8) gezogen, steht der Knopf am Zeiger — √65 von der Mitte,
    also 2 · √65 ≈ 16,12 mm lang, gedreht um atan(8 / 1) ≈ 82,9 Grad.
    """
    renderer = RecordingRenderer(size=(800, 600))
    taken: list[tuple[float, float]] = []
    handle = a_handle(renderer, taken)

    press = renderer.world_to_display((1.0, 0.0, 5.0))
    assert handle.take_press(PointerEvent("press", int(press[0]), int(press[1]), button="left"), 0)
    target = renderer.world_to_display((1.0, 8.0, 5.0))
    handle.handle(PointerEvent("move", int(target[0]), int(target[1])))
    handle.handle(PointerEvent("release", int(target[0]), int(target[1]), button="left"))

    length, angle = taken[0]
    assert length == pytest.approx(2.0 * math.sqrt(65.0), abs=0.05)
    assert angle == pytest.approx(math.degrees(math.atan2(8.0, 1.0)), abs=0.5)


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


def test_a_round_hole_shows_no_second_diameter_beside_its_knobs(qt_app: object) -> None:
    """Die Länge neben den Knöpfen steht erst, wenn ein Langloch daraus wird (RM-516).

    An der runden Bohrung ist sie ihr Durchmesser, und der steht im Feld der
    Maßgruppe — daneben stand im Bild ein zweites „5,20 mm“.
    """
    from app.ui.labels import length
    from app.ui.viewport import Viewport

    load_operations()
    viewport = Viewport()
    try:
        viewport.renderer = RecordingRenderer(size=(800, 600))
        a_slot_in_the_view(viewport)
        handle = viewport._slot_handle
        assert handle is not None
        handle.set_values(2.0 * handle.radius, 0.0)
        viewport._update_slot_labels()
        assert viewport._gizmo_label_texts[-1] == "", "rund: keine Zahl neben den Knöpfen"
        handle.set_values(20.0, 0.0)
        viewport._update_slot_labels()
        assert viewport._gizmo_label_texts[-1] == length(20.0), "ein Langloch nennt seine Länge"
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


@pytest.mark.parametrize("ratio", [1.0, 1.5, 2.0])
def test_eight_logical_points_of_wobble_stay_a_click_at_any_scaling(
    qt_app: object, ratio: float
) -> None:
    """Auch auf einem Bildschirm mit 200 Prozent Skalierung ist Antippen kein Zug.

    ``CLICK_SLACK`` steht in Logikpunkten, die Zeigerpunkte kommen in
    Gerätepixeln — acht Logikpunkte Wackeln sind dort sechzehn davon, und ohne
    Umrechnung meldete der Griff dafür eine Länge, die niemand gezogen hat.
    Dieselbe Falle wie in :func:`app.ui.render.navigator.is_click`, und
    derselbe Faktor behebt sie.
    """
    renderer = RecordingRenderer(size=(800, 600))
    renderer.device_ratio = lambda: ratio  # type: ignore[method-assign]
    taken: list[tuple[float, float]] = []
    handle = a_handle(renderer, taken)

    seat = renderer.world_to_display((BORE / 2.0, 0.0, 5.0))
    renderer.item_picks[(round(seat[0]), round(seat[1]))] = handle.knobs[0]
    wobble = (round(seat[0] + 8.0 * ratio), round(seat[1]))
    handle.handle(PointerEvent("move", int(seat[0]), int(seat[1])))
    handle.handle(PointerEvent("press", int(seat[0]), int(seat[1]), button="left"))
    handle.handle(PointerEvent("move", *wobble, buttons=frozenset({"left"})))
    handle.handle(PointerEvent("release", *wobble, button="left"))

    assert not taken, f"acht Logikpunkte Wackeln sind kein Zug (Verhältnis {ratio}): {taken}"
