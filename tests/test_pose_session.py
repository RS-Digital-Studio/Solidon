"""Das Skelettwerkzeug im Fenster (Konzept P16 §7.5, RM-561).

Dieselbe Bauart wie die Formsitzung: ein Werkzeugmodus, eine Leiste neben der
Werkzeugzeile, ein Zustand im Fenster, eine Operation am Ende.

Der erste Klick setzt ein Gelenk, jeder weitere einen Knochen am Fuß des
vorigen — n Knochen sind n + 1 Klicks. Enter beendet die Kette, ein Klick auf
ein Gelenk setzt dort fort. Ziehen an einem Gelenk beugt den Knochen, der dort
endet; geschrieben wird dasselbe ``pose``-Feld, das der Schrittdialog als
Zahlen zeigt. *Fertig* legt den Schritt ohne Dialog an.

Geprüft wird offscreen über die Methoden, die die Ansicht ruft: ein Klick ist
ein Punkt, ein Zug ist ein Winkel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from app.core.geom.pose import armature_from_text, pose_angles
from app.ui.main_window import MainWindow
from app.ui.session import Session
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window
from tests.ui_helpers import with_a_body

MESHES = Path(__file__).parent / "data" / "meshes"


def chain(window: MainWindow, *points: tuple[float, float, float]) -> None:
    """Eine Kette: der erste Punkt ein Gelenk, jeder weitere ein Knochen."""
    for point in points:
        window._on_bone_point(point)


def bend(window: MainWindow, joint: int, degrees: float) -> None:
    """Am Gelenk ziehen, bis der Knochen um ``degrees`` gebeugt ist, und loslassen."""
    window._on_joint_drag_started(joint)
    assert window._armature_drag is not None, "an diesem Gelenk endet kein Knochen"
    window._bend_to(degrees)
    window._on_joint_drag_finished()


def test_exact_armature_gestures_wait_for_the_conversion_and_write_once(
    window: MainWindow,
) -> None:
    """Am exakten Körper wartet *Fertig* auf die Vorschau mit der Konvertierung
    — ohne Dialog, und geschrieben wird genau einmal (Entscheidung Robert,
    21.09.2026: der Klick vor dem Bild verfällt nicht)."""
    from app.core.scene.history import OperationDraft
    from tests.helpers import exact_kernel

    exact_kernel()
    assert window.session.apply(
        "Quader",
        [OperationDraft("create_brep_box", params={"width": 20.0, "depth": 20.0, "height": 20.0})],
    )
    assert window.session.wait_for_idle(30_000)
    identifier = next(iter(window.session.last_result.scene.objects))
    window.object_tree.select_object(identifier)
    window.start_armature(identifier)
    chain(window, (10.0, 10.0, 0.0), (10.0, 10.0, 20.0))
    before = len(window.session.project.document.ops)
    window.finish_armature()
    assert window._op_dialog is None, "kein Dialog mehr"
    assert len(window.session.project.document.ops) == before
    assert window.session.wait_for_idle(30_000)
    QApplication.processEvents()
    assert window.session.wait_for_idle(30_000)
    assert len(window.session.project.document.ops) == before + 1
    assert window.session.last_result.scene.objects[identifier].kind == "mesh"
    assert window.session.project.document.ops[-1].op == "pose_armature"


# --- hinein und heraus ----------------------------------------------------------


def test_the_session_needs_something_to_hang_bones_in(window: MainWindow) -> None:
    window.start_armature()

    assert not window.setting_armature()
    assert not window.pose_bar.isVisible()


def test_starting_shows_the_bar_and_hides_the_view_tools(window: MainWindow) -> None:
    object_id = with_a_body(window)

    window.start_armature(object_id)

    assert window.setting_armature()
    assert window.pose_bar.isVisibleTo(window)
    assert not window.tools.isVisibleTo(window)


def test_two_sessions_do_not_open_at_once(window: MainWindow) -> None:
    """Wer formt, setzt kein Skelett — und umgekehrt."""
    object_id = with_a_body(window)
    window.start_sculpt(object_id)

    window.start_armature(object_id)

    assert not window.setting_armature()
    assert window.sculpting()


def test_the_toolbar_holds_one_key_per_tool(window: MainWindow) -> None:
    """Je Werkzeug ein Kürzel (RM-561): Strg+Umschalt+F formt, Strg+Umschalt+K
    öffnet das Skelett — und der Knopf sagt es."""
    from PySide6.QtGui import QKeySequence

    object_id = with_a_body(window)
    window.object_tree.select_object(object_id)
    QApplication.processEvents()
    for action, keys in (
        (window._toolbar_sculpt, "Ctrl+Shift+F"),
        (window._toolbar_armature, "Ctrl+Shift+K"),
    ):
        assert action.shortcut() == QKeySequence(keys)
        native = QKeySequence(keys).toString(QKeySequence.SequenceFormat.NativeText)
        assert native in action.toolTip(), "der Knopf nennt seine Taste"
    window._toolbar_armature.trigger()
    assert window.setting_armature()


# --- Knochen setzen -------------------------------------------------------------


def test_the_first_click_is_a_joint_and_the_second_a_bone(window: MainWindow) -> None:
    object_id = with_a_body(window)
    window.start_armature(object_id)

    window._on_bone_point((0.0, 0.0, 0.0))
    assert not window._armature_bones, "nach einem Klick steht noch kein Knochen"
    assert "Ende des Knochens" in window.pose_bar.state.text()

    window._on_bone_point((0.0, 0.0, 20.0))
    assert len(window._armature_bones) == 1
    assert window._armature_bones[0].head == (0.0, 0.0, 0.0)
    assert window._armature_bones[0].tail == (0.0, 0.0, 20.0)


def test_each_further_click_is_one_more_bone(window: MainWindow) -> None:
    """S1: ein Arm aus zwei Knochen sind drei Klicks, nicht vier (RM-561) —
    der Kopf des nächsten Knochens ist der Fuß des vorigen."""
    object_id = with_a_body(window)
    window.start_armature(object_id)

    chain(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))

    first, second = window._armature_bones
    assert second.head == first.tail
    assert first.parent == "" and second.parent == first.name
    assert [bone.name for bone in window._armature_bones] == ["bone_1", "bone_2"], (
        "Namen werden durchnummeriert, umbenannt wird im Schrittdialog"
    )


def test_enter_ends_the_chain_and_the_next_click_starts_a_new_one(window: MainWindow) -> None:
    """Für den zweiten Arm: Enter, dann wieder ein Gelenk und ein Knochen."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    chain(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))

    window.viewport.chainEnded.emit()
    chain(window, (10.0, 0.0, 0.0), (20.0, 0.0, 0.0))

    assert window._armature_bones[1].parent == ""
    assert window._armature_bones[1].head == (10.0, 0.0, 0.0)


def test_a_click_on_a_joint_continues_there_and_on_the_chain_end_ends_it(
    window: MainWindow,
) -> None:
    """Ein Klick auf ein vorhandenes Gelenk setzt dort fort; ein Doppelklick auf
    den letzten Punkt beendet die Kette, sein zweiter Klick öffnet sie nicht
    wieder."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    chain(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))
    joints = [rest for _posed, _ends, rest in window._armature_joints()]

    end = joints.index((0.0, 0.0, 40.0))
    window.viewport.jointPicked.emit(end)
    window.viewport.jointPicked.emit(end)
    assert window._armature_head is None, "der Doppelklick beendet die Kette"

    middle = joints.index((0.0, 0.0, 20.0))
    window.viewport.jointPicked.emit(middle)
    window._on_bone_point((10.0, 0.0, 20.0))
    branch = window._armature_bones[-1]
    assert branch.head == (0.0, 0.0, 20.0)
    assert branch.parent == window._armature_bones[0].name, "der Ast hängt am ersten Knochen"


def test_the_bar_has_no_name_field_and_no_extra_buttons(qt_app: QApplication) -> None:
    """*Neue Kette*, *Letzten zurück* und das Namensfeld sind entfallen (RM-561):
    Enter und Strg+Z tun dasselbe, und Namen braucht nur, wer Winkel bindet."""
    from PySide6.QtWidgets import QLineEdit, QPushButton

    from app.ui.pose_bar import PoseBar

    leiste = PoseBar()
    assert not leiste.findChildren(QLineEdit)
    assert [knopf.text() for knopf in leiste.findChildren(QPushButton)] == [leiste.done.text()]


def test_every_button_in_the_bar_says_what_it_does(qt_app: QApplication) -> None:
    """Jeder Knopf der Skelettleiste trägt einen Tooltip — *Fertig* sagt, dass
    danach ein Verlaufsschritt steht."""
    from PySide6.QtWidgets import QPushButton

    from app.ui.pose_bar import PoseBar

    leiste = PoseBar()
    knoepfe = leiste.findChildren(QPushButton)
    assert knoepfe
    stumm = [knopf.text() for knopf in knoepfe if not knopf.toolTip().strip()]
    assert not stumm, "Knöpfe ohne Tooltip: " + ", ".join(stumm)


# --- beugen ---------------------------------------------------------------------


def test_dragging_a_joint_bends_its_bone_and_the_rest_stays(window: MainWindow) -> None:
    """Ziehen am Gelenk beugt den Knochen, der dort endet, und schreibt seine
    Winkel; *Fertig* legt Skelett und Stellung ohne Dialog als einen Schritt an.
    Was kein Knochen erreicht, bleibt stehen (fester Rumpf)."""
    import numpy as np

    object_id = with_a_body(window)
    body = window.session.last_result.scene.objects[object_id].mesh
    low, high = body.raw.bounds
    middle = (low + high) / 2.0
    top = float(high[2])
    shoulder = (float(middle[0]), float(middle[1]), top - 25.0)
    elbow = (float(middle[0]), float(middle[1]), top - 12.0)
    hand = (float(middle[0]), float(middle[1]), top - 2.0)
    window.start_armature(object_id)
    chain(window, shoulder, elbow, hand)
    before = len(window.session.project.document.ops)

    joints = [ends for _posed, ends, _rest in window._armature_joints()]
    bend(window, joints.index("bone_2"), 40.0)

    angles = window._armature_angles["bone_2"]
    assert any(abs(value) > 1.0 for value in angles), angles
    assert "bone_1" not in window._armature_pose, "nur der gezogene Knochen dreht"
    window.finish_armature()
    assert window._op_dialog is None
    assert window.session.wait_for_idle(30_000)
    ops = window.session.project.document.ops
    assert len(ops) == before + 1 and ops[-1].op == "pose_armature"
    written = pose_angles(str(ops[-1].params["pose"]))
    assert written["bone_2"] == pytest.approx(angles)
    posed = window.session.last_result.scene.objects[object_id].mesh
    feet = np.asarray(body.raw.vertices)[:, 2] < float(low[2]) + 5.0
    assert np.allclose(posed.raw.vertices[feet], body.raw.vertices[feet], atol=1e-3), (
        "die Füße bleiben stehen"
    )
    assert not np.allclose(posed.raw.vertices, body.raw.vertices), "der Arm ist gebeugt"


def test_a_typed_angle_is_exact_and_undo_takes_back_the_bend(window: MainWindow) -> None:
    """Tippen statt ziehen gibt genau den Winkel (§18.11); Strg+Z nimmt die
    letzte Beugung zurück, nicht den Knochen."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    chain(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    joint = [ends for _posed, ends, _rest in window._armature_joints()].index("bone_1")
    window._on_joint_drag_started(joint)
    window._on_joint_angle_typed(30.0)

    # Offscreen schaut die Kamera entlang +Y: gedreht wird um diese Achse.
    assert window._armature_angles["bone_1"] == pytest.approx((0.0, 30.0, 0.0), abs=0.01)
    assert window.undo_bone()
    assert "bone_1" not in window._armature_pose
    assert len(window._armature_bones) == 1, "der Knochen bleibt"


def test_escape_cancels_a_running_bend(window: MainWindow) -> None:
    object_id = with_a_body(window)
    window.start_armature(object_id)
    chain(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    window._on_joint_drag_started(1)
    window._bend_to(25.0)

    window._escape()

    assert window.setting_armature(), "Escape nahm nur den laufenden Zug"
    assert window._armature_drag is None
    assert "bone_1" not in window._armature_pose


# --- zurücknehmen und Escape ----------------------------------------------------


def test_escape_takes_the_half_bone_and_then_finishes(window: MainWindow) -> None:
    """Escape nimmt das Unfertige — ein Gelenk ohne Knochen — und beendet sonst
    wie *Fertig*, ohne Dialog und ohne etwas wegzuwerfen (RM-561)."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    chain(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    window.viewport.chainEnded.emit()
    window._on_bone_point((10.0, 0.0, 0.0))
    before = len(window.session.project.document.ops)

    window._escape()
    assert window.setting_armature()
    assert window._armature_head is None and len(window._armature_bones) == 1

    window._escape()
    assert not window.setting_armature()
    assert window._op_dialog is None
    assert window.session.wait_for_idle(30_000)
    ops = window.session.project.document.ops
    assert len(ops) == before + 1
    assert armature_from_text(str(ops[-1].params["armature"]))


def test_undo_goes_back_click_by_click(window: MainWindow) -> None:
    object_id = with_a_body(window)
    window.start_armature(object_id)
    chain(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))
    before = len(window.session.project.document.ops)

    window.action_undo()
    assert len(window._armature_bones) == 1
    assert window._armature_head == (0.0, 0.0, 20.0), "die Kette steht wieder am ersten Fuß"
    window.action_undo()
    window.action_undo()
    assert not window._armature_bones and window._armature_head is None
    assert len(window.session.project.document.ops) == before, "der Verlauf bleibt unberührt"


def test_an_empty_session_leaves_no_step_behind(window: MainWindow) -> None:
    object_id = with_a_body(window)
    before = len(window.session.project.document.ops)

    window.start_armature(object_id)
    window.finish_armature()

    assert len(window.session.project.document.ops) == before


def test_finishing_writes_one_step_and_one_undo_takes_it(window: MainWindow) -> None:
    """Regel 16: Der ganze Vorgang ist eine Transaktion."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    chain(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))
    before = len(window.session.project.document.ops)

    window.finish_armature()
    assert window.session.wait_for_idle(30_000)
    ops = window.session.project.document.ops
    assert len(ops) == before + 1
    bones = armature_from_text(str(ops[-1].params["armature"]))
    assert len(bones) == 2 and bones[1].parent == bones[0].name

    window.session.undo()
    assert window.session.wait_for_idle(30_000)
    assert len(window.session.project.document.ops) == before


def test_a_bound_angle_bends_the_body_and_follows_the_parameter(qt_app: QApplication) -> None:
    """Der Punkt, an dem Posing hierher gehört und nicht zu Blender: Ein
    Gelenkwinkel darf ein Projektparameter sein, und wird der Parameter
    geändert, bewegt sich der Körper mit (§15, ``NESTED_REFERENCES``)."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene import OperationDraft
    from app.core.types import Parameter

    session = Session()
    session.import_model(MESHES / "cube_clean.stl")
    assert session.wait_for_idle(60_000)

    session.add_parameter(Parameter(name="neigung", value=10.0, unit="°"))
    session.apply(
        "Stellung geben",
        [
            OperationDraft(
                op="pose_armature",
                inputs=("obj_1",),
                params={
                    "armature": '[{"n":"b1","h":[0,0,0],"t":[0,0,10]}]',
                    "pose": '{"b1":["=@neigung",0,0]}',
                },
            )
        ],
    )
    assert session.wait_for_idle(60_000)

    result = session.last_result
    assert result is not None
    zehn_grad = as_mesh_data(result.scene.objects["obj_1"].mesh).bounds.size

    session.change_parameter("neigung", 45.0)
    assert session.wait_for_idle(60_000)

    result = session.last_result
    assert result is not None
    fuenfundvierzig = as_mesh_data(result.scene.objects["obj_1"].mesh).bounds.size

    assert zehn_grad != fuenfundvierzig, (
        "der gebeugte Körper hängt am Parameter — sonst steht ein altes Ergebnis im Cache"
    )


def test_the_context_menu_opens_the_editor_and_not_a_raw_dialog(window: MainWindow) -> None:
    """Das Kontextmenü führt die Gesten-Operationen in ihren Editor, nicht in einen
    Rohdialog (§2.6: der kürzeste Weg vom Sehen zum Tun)."""
    from app.core.registry import REGISTRY
    from app.ui.op_dialog import OperationDialog
    from app.ui.seal_flow import SealFlow

    with_a_body(window)
    gesture = {"sketch", "strokes", "armature"}
    offered = [
        spec
        for spec in REGISTRY.all()
        if spec.consumes == 1 and {entry.kind for entry in spec.params.spec()} & gesture
    ]
    assert len(offered) >= 3, f"nur {len(offered)} Gesten-Operationen im Kontextmenü?"

    for spec in offered:
        item = window.object_tree.tree.topLevelItem(0)
        assert item is not None
        item.setSelected(True)
        window.object_tree.operationRequested.emit(spec)
        QApplication.processEvents()
        opened = (
            window._sketch_panel is not None
            or window.sculpting()
            or window.setting_armature()
            or bool(window.findChildren(SealFlow))
        )
        assert opened, f"{spec.title} landete nicht in ihrem Editor"
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        window._escape()
        QApplication.processEvents()
        assert window.session.wait_for_idle(30_000)


# --- ein zweites Mal an dasselbe Skelett ----------------------------------------


def test_reopening_brings_bones_and_pose_back_and_bending_changes_the_same_step(
    window: MainWindow,
) -> None:
    """S3: Ein Doppelklick im Verlauf öffnet das Werkzeug mit Knochen **und**
    greifbaren Gelenken; gezogen wird weiter an derselben Stellung, und *Fertig*
    ändert denselben Schritt, statt einen zweiten anzulegen."""
    from app.core.geom.pose import armature_to_text, pose_text
    from app.core.scene.history import OperationDraft
    from app.core.types import Bone

    gesetzt = [
        Bone(name="arm", head=(0.0, 0.0, 0.0), tail=(0.0, 0.0, 10.0), parent=""),
        Bone(name="hand", head=(0.0, 0.0, 10.0), tail=(0.0, 0.0, 20.0), parent="arm"),
    ]
    koerper = with_a_body(window)
    window.session.apply(
        "Skelett",
        [
            OperationDraft(
                op="pose_armature",
                inputs=(koerper,),
                params={
                    "armature": armature_to_text(gesetzt),
                    "pose": pose_text({"arm": [0.0, 20.0, 0.0]}),
                },
            )
        ],
    )
    assert window.session.wait_for_idle(60_000)
    step = window.session.project.document.ops[-1].id
    count = len(window.session.project.document.ops)

    window.edit_operation(step)
    assert window.session.wait_for_idle(30_000)
    assert window.setting_armature()
    assert window._armature_step == step
    assert [bone.name for bone in window._armature_bones] == ["arm", "hand"]
    assert window._armature_angles["arm"] == pytest.approx((0.0, 20.0, 0.0))
    shown = window.viewport.bones_shown
    assert shown[1][0] != (0.0, 0.0, 10.0), "die Knochen stehen in der Stellung im Bild"

    joints = [ends for _posed, ends, _rest in window._armature_joints()]
    bend(window, joints.index("hand"), 15.0)
    window.finish_armature()
    assert window.session.wait_for_idle(30_000)
    assert len(window.session.project.document.ops) == count, "derselbe Schritt, kein zweiter"
    written = pose_angles(str(window.session.history.operation(step).params["pose"]))
    assert written["arm"] == pytest.approx((0.0, 20.0, 0.0))
    assert "hand" in written


def _bound_arm(window: MainWindow, angle: object) -> tuple[str, int]:
    """Ein Körper mit Arm und Hand, die Hand gestellt mit ``angle`` um Y."""
    from app.core.geom.pose import armature_to_text, pose_text
    from app.core.scene.history import OperationDraft
    from app.core.types import Bone, Parameter

    koerper = with_a_body(window)
    window.session.add_parameter(Parameter(name="w", value=20.0, unit="°"))
    assert window.session.wait_for_idle(30_000)
    gesetzt = [
        Bone(name="arm", head=(0.0, 0.0, 0.0), tail=(0.0, 0.0, 10.0), parent=""),
        Bone(name="hand", head=(0.0, 0.0, 10.0), tail=(0.0, 0.0, 20.0), parent="arm"),
    ]
    window.session.apply(
        "Skelett",
        [
            OperationDraft(
                op="pose_armature",
                inputs=(koerper,),
                params={
                    "armature": armature_to_text(gesetzt),
                    "pose": pose_text({"arm": [0.0, 0.0, 0.0], "hand": [0.0, angle, 0.0]}),
                },
            )
        ],
    )
    assert window.session.wait_for_idle(60_000)
    return koerper, window.session.project.document.ops[-1].id


def test_dragging_a_bound_angle_keeps_its_binding_and_says_where_to_change_it(
    window: MainWindow,
) -> None:
    """Review F2 (Regel 21): Ein Zug am Gelenk schrieb drei Zahlen über einen
    Winkel, der an einem Projektmaß hing — still, und Varianten über das Maß
    bewegten den Knochen danach nicht mehr. Jetzt bleibt der Zug aus, die
    Bindung steht, und der Satz nennt den Weg."""
    said: list[str] = []
    _koerper, step = _bound_arm(window, "=@w")
    window.edit_operation(step)
    assert window.session.wait_for_idle(30_000)
    window.announce = lambda text, *args, **kwargs: said.append(str(text))  # type: ignore[method-assign]
    joints = [ends for _posed, ends, _rest in window._armature_joints()]
    window._on_joint_drag_started(joints.index("hand"))
    assert window._armature_drag is None
    assert window._armature_pose["hand"][1] == "=@w"
    assert said and "=@w" in said[-1] and "Diesen Schritt ändern" in said[-1]
    window._on_joint_drag_started(joints.index("arm"))
    assert window._armature_drag is not None, "Gegenprobe: ein freier Winkel lässt sich ziehen"
    window._on_joint_drag_cancelled()
    window.finish_armature()
    assert window.session.wait_for_idle(30_000)
    written = pose_angles(str(window.session.history.operation(step).params["pose"]))
    assert written["hand"][1] == "=@w"


def test_an_unreadable_angle_rests_only_its_own_bone(window: MainWindow) -> None:
    """Review G1: Ein einziger ungebundener Winkel stellte das ganze Skelett in
    Ruhe. Jetzt steht nur sein Knochen in Ruhe, die anderen in ihrer Stellung,
    und der Satz nennt ihn."""
    from app.core.geom.pose import armature_to_text, pose_text
    from app.core.scene.history import OperationDraft
    from app.core.types import Bone

    said: list[str] = []
    gesetzt = [
        Bone(name="arm", head=(0.0, 0.0, 0.0), tail=(0.0, 0.0, 10.0), parent=""),
        Bone(name="bein", head=(5.0, 0.0, 0.0), tail=(5.0, 0.0, -10.0), parent=""),
    ]
    koerper = with_a_body(window)
    window.session.apply(
        "Skelett",
        [
            OperationDraft(
                op="pose_armature",
                inputs=(koerper,),
                params={
                    "armature": armature_to_text(gesetzt),
                    "pose": pose_text({"arm": [0.0, 20.0, 0.0], "bein": [0.0, "=@fehlt", 0.0]}),
                },
            )
        ],
    )
    window.session.wait_for_idle(60_000)
    step = window.session.project.document.ops[-1].id
    window.announce = lambda text, *args, **kwargs: said.append(str(text))  # type: ignore[method-assign]
    window.start_armature(koerper, step=step)
    assert window._armature_angles["arm"] == pytest.approx((0.0, 20.0, 0.0))
    assert "bein" not in window._armature_angles
    assert any("bein" in text for text in said)


def test_a_new_chain_in_bent_skin_starts_where_the_skin_rests(window: MainWindow) -> None:
    """Review G1: Der erste Klick einer neuen Kette in gebeugter Haut wurde als
    Ruhepunkt genommen, wo das Bild ihn zeigte — der Knochen band dann Haut, die
    in Ruhe woanders liegt. Über das getroffene Dreieck kommt er in die Ruhe,
    und ein neuer Knochen zeigt die Haut mit seinen Gewichten."""
    import numpy as np

    _koerper, step = _bound_arm(window, 60.0)
    window.edit_operation(step)
    assert window.session.wait_for_idle(30_000)
    shown = window._armature_shown
    rest = window._sculpt_mesh(window._armature_target)
    assert shown is not None and rest is not None and shown is not rest, "die Haut ist gebeugt"
    bent = np.asarray(shown.raw.vertices)
    still = np.asarray(rest.raw.vertices)
    moved = np.flatnonzero(np.linalg.norm(bent - still, axis=1) > 2.0)
    assert len(moved), "Voraussetzung: die Hand bewegt Haut"
    corner = int(moved[0])
    face = int(np.flatnonzero((np.asarray(shown.raw.faces) == corner).any(axis=1))[0])
    corners = np.asarray(shown.raw.faces)[face]
    clicked = bent[corners].mean(axis=0)
    window._on_bone_point(tuple(float(v) for v in clicked))
    head = np.asarray(window._armature_head)
    resting = still[corners].mean(axis=0)
    shown_place = clicked
    assert np.linalg.norm(head - shown_place) > 1.0, "nicht dort, wo das Bild die Haut zeigt"
    assert np.linalg.norm(head - resting) < np.linalg.norm(head - shown_place)
    before = window._armature_shown
    window._on_bone_point(tuple(float(v) for v in clicked + np.asarray((0.0, 3.0, 0.0))))
    assert len(window._armature_bones) == 3
    assert window.wait_for_armature_skin()
    assert window._armature_shown is not before, "die Haut zeigt den neuen Knochen"


def test_a_large_skin_is_bent_in_a_worker_and_clicks_use_what_is_shown(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review F3: Gewichte und gebeugte Haut rechnete jeder Klick im
    Hauptfaden, an 327 680 Dreiecken 1,2 s. Ab der Sofortgrenze rechnet ein
    Arbeiter; ein Klick trifft den gezeigten Körper und rechnet keine Haut."""
    import app.core.geom.pose as pose
    import app.ui.placement_flow as placement_flow

    monkeypatch.setattr(placement_flow, "AT_ONCE_BELOW", 1)
    built: list[int] = []
    original = pose.Skin.__init__

    def counted(self: Any, *args: Any, **kwargs: Any) -> None:
        built.append(1)
        original(self, *args, **kwargs)

    monkeypatch.setattr(pose.Skin, "__init__", counted)
    _koerper, step = _bound_arm(window, 60.0)
    window.edit_operation(step)
    assert window.session.wait_for_idle(30_000)
    assert window._armature_skin_worker is not None, "die Haut rechnet im Arbeiter"
    assert window.wait_for_armature_skin()
    shown = window._armature_shown
    assert shown is not None and shown is not window._sculpt_mesh(window._armature_target)
    built.clear()
    window._on_bone_point(tuple(float(v) for v in shown.raw.vertices[0]))
    assert built == [], "der Klick rechnet keine Haut"


def test_reopening_and_finishing_unchanged_adds_no_undo_step(window: MainWindow) -> None:
    from app.core.geom.pose import armature_to_text
    from app.core.scene.history import OperationDraft
    from app.core.types import Bone

    koerper = with_a_body(window)
    window.session.apply(
        "Skelett",
        [
            OperationDraft(
                op="pose_armature",
                inputs=(koerper,),
                params={
                    "armature": armature_to_text([Bone("arm", (0, 0, 0), (0, 0, 10))]),
                    "pose": '{"arm":[0,30,0]}',
                },
            )
        ],
    )
    assert window.session.wait_for_idle(60_000)
    transactions = len(window.session.project.document.transactions)
    window.start_armature(koerper)
    assert window.session.wait_for_idle(30_000)
    window.finish_armature()
    assert window.session.wait_for_idle(30_000)
    assert len(window.session.project.document.transactions) == transactions


def test_a_body_without_an_armature_starts_empty(window: MainWindow) -> None:
    window.start_armature(with_a_body(window))

    assert window._armature_bones == [], "ohne Skelett fängt der Editor leer an"
    assert window._armature_step is None


def test_an_unreadable_armature_does_not_block_the_editor(window: MainWindow) -> None:
    """Ein unlesbares Skelett lässt den Editor leer anfangen, statt ihn zu verweigern."""
    from app.core.scene.history import OperationDraft

    koerper = with_a_body(window)
    window.session.apply(
        "Skelett",
        [
            OperationDraft(
                op="pose_armature",
                inputs=(koerper,),
                params={"armature": "das ist kein Skelett", "pose": ""},
            )
        ],
    )
    assert window.session.wait_for_idle(60_000)

    window.start_armature(koerper)

    assert window.setting_armature(), "der Editor muss trotzdem aufgehen"
    assert window._armature_bones == []
    assert window._armature_step is None


def test_bones_and_the_open_chain_end_are_drawn_inside_the_body(window: MainWindow) -> None:
    """RM-367 W4-6 und W4-7: Knochen und Gelenke stehen im Bild, ein Klick auf
    die Haut setzt das Gelenk ins Innere, und das offene Kettenende ist markiert."""
    import numpy as np

    object_id = with_a_body(window)
    window.start_armature(object_id)
    entry = window.session.last_result.scene.objects[object_id]
    vertices = np.asarray(entry.mesh.raw.vertices, dtype=float)
    top = tuple(float(v) for v in vertices[int(np.argmax(vertices[:, 2]))])
    # Offscreen schaut die Kamera entlang +Y: Die vordere Haut ist die mit
    # kleinstem Y, ihr Blick führt in den Körper.
    side = tuple(float(v) for v in vertices[int(np.argmin(vertices[:, 1]))])

    window._on_bone_point(side)
    joint = window.viewport.joint_shown
    assert joint is not None, "das gesetzte Gelenk steht im Bild"
    gap = float(np.linalg.norm(np.asarray(joint) - np.asarray(side)))
    assert gap > 1.0, f"das Gelenk liegt nicht auf der Haut ({gap:.2f} mm)"
    low, high = entry.mesh.bounds.minimum, entry.mesh.bounds.maximum
    assert all(low[axis] < joint[axis] < high[axis] for axis in range(3)), joint

    window._on_bone_point(top)
    assert len(window.viewport.bones_shown) == 1, "der Knochen steht im Bild"
    assert window.viewport.joint_shown == window._armature_bones[0].tail, "das offene Ende"
    assert len(window.viewport.joints_shown) == 2, "beide Gelenke lassen sich greifen"

    window.finish_armature()
    assert window.viewport.bones_shown == ()


def test_pose_print_findings_remain_in_the_bar_after_finishing(window: MainWindow) -> None:
    """RM-377: Nach dem Posieren bleibt der Befund am Ort der Handlung."""
    from app.core.types import Finding, Report
    from app.i18n import _

    object_id = with_a_body(window)
    window.start_armature(object_id)
    chain(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    window.finish_armature()
    assert window.session.wait_for_idle(30_000)
    finding = Finding(
        code="pose.pinched",
        severity="warning",
        object_id=object_id,
        message=_(
            "An den gebeugten Gelenken schnürt sich die Haut ein — für diese "
            "Winkel ist das Netz dort zu grob."
        ),
    )
    window.session.last_result.scene.report = Report((finding,))
    window.pose_bar.analysis.choice.setCurrentIndex(2)
    window._check_sculpted_walls()
    assert window.wait_for_sculpt_check()
    assert "schnürt" in window.pose_bar.analysis.note.text()
    assert "Stützen" in window.pose_bar.analysis.note.text()
    assert window.pose_bar.isVisibleTo(window)
    assert window.pose_bar.done.text() == "Schließen"
    window.pose_bar.done.click()
    assert not window.pose_bar.isVisibleTo(window)
    assert window.viewport.analysis_map is None


def test_history_reopens_the_requested_armature_instead_of_the_latest(window: MainWindow) -> None:
    """RM-375: Die gewählte Operationskennung bestimmt das Skelett. Strg+Z nimmt
    an einem wieder geöffneten Skelett den letzten Knochen weg."""
    from app.core.geom.pose import armature_to_text
    from app.core.scene.history import OperationDraft
    from app.core.types import Bone

    target = with_a_body(window)
    for name in ("first", "second"):
        window.session.apply(
            "Skelett",
            [
                OperationDraft(
                    "pose_armature",
                    inputs=(target,),
                    params={
                        "armature": armature_to_text(
                            [Bone(name=name, head=(0, 0, 0), tail=(0, 0, 10))]
                        ),
                        "pose": "",
                    },
                )
            ],
        )
        assert window.session.wait_for_idle(30_000)
    first = window.session.project.document.ops[-2].id
    window.edit_operation(first)
    assert window.session.wait_for_idle(30_000)
    assert window.setting_armature()
    assert window._armature_step == first
    assert [entry.name for entry in window._armature_bones] == ["first"]
    assert window.undo_bone()
    window.finish_armature()
    assert window.session.wait_for_idle(30_000)
    assert window.session.history.operation(first).params["armature"] == ""
    assert len(window.session.project.document.ops) == 3
    window.session.undo()
    assert window.session.wait_for_idle(30_000)
    assert len(armature_from_text(window.session.history.operation(first).params["armature"])) == 1
