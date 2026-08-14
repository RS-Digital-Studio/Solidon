"""Der Skeletteditor im Fenster (Konzept P16 §7.5).

Dieselbe Bauart wie die Formsitzung: ein Werkzeugmodus, eine Leiste neben der
Werkzeugzeile, ein Zustand im Fenster, eine Operation am Ende. Was ihn
unterscheidet, ist die Arbeitsteilung dahinter — **hier werden Gesten
gesammelt, die Stellung selbst ist eine Zahl.**

Zwei Klicks machen einen Knochen: erst das Gelenk, dann das Ende. Die Winkel
setzt niemand mit der Maus; sie stehen im Dialog der Operation, wo auch ein
Projektparameter erlaubt ist. Das ist der Punkt, an dem Posing hierher gehört
und nicht zu einem Animationsprogramm.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.geom.pose import armature_from_text
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    return MainWindow(Session(), UiSettings())


def with_a_body(window: MainWindow) -> str:
    """Die saubere Figur aus dem Korpus — ein Körper, der ein Skelett verdient."""
    window.open_path(MESHES / "clean_figure.stl")
    window.session.wait_for_idle()
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    object_id = window.object_tree.selected()
    assert object_id
    return str(object_id)


def bone(
    window: MainWindow, head: tuple[float, float, float], tail: tuple[float, float, float]
) -> None:
    """Ein Knochen sind zwei Klicks."""
    window._on_bone_point(head)
    window._on_bone_point(tail)


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
    """Wer formt, setzt kein Skelett — und umgekehrt.

    Ein Modus, der beides gleichzeitig kann, kann keines von beidem
    verlässlich: Derselbe Klick müsste zwei Dinge bedeuten.
    """
    object_id = with_a_body(window)
    window.start_sculpt(object_id)

    window.start_armature(object_id)

    assert not window.setting_armature()
    assert window.sculpting()


# --- Knochen setzen -------------------------------------------------------------


def test_two_clicks_make_one_bone(window: MainWindow) -> None:
    """Erst das Gelenk, dann das Ende."""
    object_id = with_a_body(window)
    window.start_armature(object_id)

    window._on_bone_point((0.0, 0.0, 0.0))
    assert not window._armature_bones, "nach einem Klick steht noch kein Knochen"

    window._on_bone_point((0.0, 0.0, 20.0))
    assert len(window._armature_bones) == 1
    assert window._armature_bones[0].head == (0.0, 0.0, 0.0)
    assert window._armature_bones[0].tail == (0.0, 0.0, 20.0)


def test_the_next_bone_hangs_on_the_one_before(window: MainWindow) -> None:
    """Ein Skelett ist meistens eine Kette.

    Wer für jeden Knochen sein Elternteil wählen muss, klickt dreimal so oft
    wie nötig.
    """
    object_id = with_a_body(window)
    window.start_armature(object_id)

    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    bone(window, (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))

    assert window._armature_bones[0].parent == ""
    assert window._armature_bones[1].parent == window._armature_bones[0].name


def test_a_new_chain_hangs_on_nothing(window: MainWindow) -> None:
    """Für den zweiten Arm — sonst wächst alles an einer Kette weiter."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))

    window.break_armature_chain()
    bone(window, (10.0, 0.0, 0.0), (20.0, 0.0, 0.0))

    assert window._armature_bones[1].parent == ""


def test_a_name_is_used_once_and_then_forgotten(window: MainWindow) -> None:
    """Ein stehen gebliebener Name wäre der Name des nächsten Knochens.

    Zwei Knochen mit demselben Namen sind ein Skelett, dessen Stellung niemand
    mehr zuordnet — die Winkel stehen je Name.
    """
    object_id = with_a_body(window)
    window.start_armature(object_id)

    window.pose_bar.name.setText("oberarm")
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    bone(window, (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))

    assert window._armature_bones[0].name == "oberarm"
    assert window._armature_bones[1].name != "oberarm"
    assert not window.pose_bar.name.text()


def test_a_repeated_name_is_made_unique(window: MainWindow) -> None:
    """Auch wenn jemand denselben Namen zweimal tippt."""
    object_id = with_a_body(window)
    window.start_armature(object_id)

    window.pose_bar.name.setText("arm")
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    window.pose_bar.name.setText("arm")
    bone(window, (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))

    names = [entry.name for entry in window._armature_bones]
    assert len(set(names)) == 2, f"zwei Knochen, zwei Namen: {names}"


# --- zurücknehmen ---------------------------------------------------------------


def test_undo_takes_back_the_half_set_bone_first(window: MainWindow) -> None:
    """Sonst nähme das erste Strg+Z einen fertigen Knochen und ließe den
    angefangenen stehen."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    window._on_bone_point((0.0, 0.0, 20.0))

    window.action_undo()

    assert window._armature_head is None
    assert len(window._armature_bones) == 1, "der fertige Knochen steht noch"


def test_undo_then_takes_back_a_whole_bone(window: MainWindow) -> None:
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    bone(window, (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))
    before = len(window.session.project.document.ops)

    window.action_undo()

    assert len(window._armature_bones) == 1
    assert len(window.session.project.document.ops) == before, "der Verlauf bleibt unberührt"


# --- was dabei herauskommt ------------------------------------------------------


def test_finishing_writes_one_operation_with_the_skeleton(window: MainWindow) -> None:
    """Regel 16: Der ganze Vorgang ist eine Transaktion."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    bone(window, (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))
    before = len(window.session.project.document.ops)

    window.finish_armature()

    ops = window.session.project.document.ops
    assert len(ops) == before + 1
    assert ops[-1].op == "pose_armature"
    bones = armature_from_text(str(ops[-1].params["armature"]))
    assert len(bones) == 2
    assert bones[1].parent == bones[0].name


def test_the_pose_stays_empty_because_it_is_a_number(window: MainWindow) -> None:
    """Der Editor setzt das Skelett, die Winkel sind Zahlen.

    Sie gehören in den Dialog der Operation, wo auch ein Projektparameter
    stehen darf — das ist der Punkt, an dem Posing hierher gehört.
    """
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))

    window.finish_armature()

    assert window.session.project.document.ops[-1].params["pose"] == ""


def test_an_empty_session_leaves_no_step_behind(window: MainWindow) -> None:
    object_id = with_a_body(window)
    before = len(window.session.project.document.ops)

    window.start_armature(object_id)
    window.finish_armature()

    assert len(window.session.project.document.ops) == before


def test_escape_ends_the_session_without_throwing_it_away(window: MainWindow) -> None:
    """Wie beim Formen: Escape beendet und verwirft nicht."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    before = len(window.session.project.document.ops)

    window._escape()

    assert not window.setting_armature()
    assert len(window.session.project.document.ops) == before + 1
