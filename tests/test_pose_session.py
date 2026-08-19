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


def test_finishing_opens_the_dialog_with_the_skeleton(window: MainWindow) -> None:
    """„Fertig" gibt an den Operationsdialog ab, wie es die Skizze vormacht.

    Vorher legte es eine Operation mit leerer Stellung an: nichts geschah,
    ohne Ansage, und weiter ging es nur über Verlauf → Doppelklick → JSON.
    Der Dialog öffnet mit gesetztem Skelett — die Winkel sind der nächste
    Handgriff, dort darf auch ein Projektparameter stehen.
    """
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    bone(window, (0.0, 0.0, 20.0), (0.0, 0.0, 40.0))
    before = len(window.session.project.document.ops)

    window.finish_armature()

    assert len(window.session.project.document.ops) == before, (
        "eine Operation mit leerer Stellung täte nichts — erst der Dialog"
    )
    dialog = window._op_dialog
    assert dialog is not None
    bones = armature_from_text(str(dialog.values()["armature"]))
    assert len(bones) == 2
    assert bones[1].parent == bones[0].name


def test_accepting_the_dialog_writes_one_operation(window: MainWindow) -> None:
    """Regel 16: Der ganze Vorgang ist eine Transaktion."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))
    before = len(window.session.project.document.ops)

    window.finish_armature()
    dialog = window._op_dialog
    assert dialog is not None
    dialog.accept()

    ops = window.session.project.document.ops
    assert len(ops) == before + 1
    assert ops[-1].op == "pose_armature"
    assert armature_from_text(str(ops[-1].params["armature"]))


def test_an_empty_session_leaves_no_step_behind(window: MainWindow) -> None:
    object_id = with_a_body(window)
    before = len(window.session.project.document.ops)

    window.start_armature(object_id)
    window.finish_armature()

    assert len(window.session.project.document.ops) == before


def test_escape_ends_the_session_without_throwing_it_away(window: MainWindow) -> None:
    """Wie beim Formen: Escape beendet und verwirft nicht — die gesetzten
    Knochen stehen im Dialog, der sich daraufhin öffnet."""
    object_id = with_a_body(window)
    window.start_armature(object_id)
    bone(window, (0.0, 0.0, 0.0), (0.0, 0.0, 20.0))

    window._escape()

    assert not window.setting_armature()
    dialog = window._op_dialog
    assert dialog is not None
    assert armature_from_text(str(dialog.values()["armature"]))


def test_a_bound_angle_bends_the_body_and_follows_the_parameter(qt_app: QApplication) -> None:
    """Der Punkt, an dem Posing hierher gehoert und nicht zu Blender.

    Vier Stellen sagten zu, dass ein Gelenkwinkel ein Projektparameter sein
    darf — Registereintrag, ``Pose``-Docstring, der ``fx``-Umschalter am
    Winkelfeld und der Kopf von ``tests/test_pose.py``. Der Kern antwortete
    darauf mit ``Diese Stellung laesst sich nicht lesen``.

    Geprueft wird Ende zu Ende, und der zweite Teil ist der wichtigere: Wird
    der Parameter geaendert, muss sich der Koerper **mitbewegen**. Der
    Cache-Schluessel deckt alles, wovon das Ergebnis abhaengt (§15) — und ein
    Ausdruck im JSON-Text der Operation ist fuer ``resolve_params``
    unsichtbar. Ohne ``NESTED_REFERENCES`` bliebe der Arm gebeugt, waehrend
    die Zahl daneben schon die neue ist.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene import OperationDraft
    from app.core.types import Parameter

    session = Session()
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

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
    session.wait_for_idle()

    result = session.last_result
    assert result is not None
    zehn_grad = as_mesh_data(result.scene.objects["obj_1"].mesh).bounds.size

    # Derselbe Stapel, ein anderer Parameterwert: Der Koerper muss folgen.
    session.change_parameter("neigung", 45.0)
    session.wait_for_idle()

    result = session.last_result
    assert result is not None
    fuenfundvierzig = as_mesh_data(result.scene.objects["obj_1"].mesh).bounds.size

    assert zehn_grad != fuenfundvierzig, (
        "der gebeugte Koerper haengt am Parameter — sonst steht ein altes Ergebnis im Cache"
    )
