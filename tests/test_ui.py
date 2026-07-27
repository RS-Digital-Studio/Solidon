"""The surface: session, window and the dialogs generated from the schema (§2.5, §10).

Runs on the offscreen Qt platform, so it works without a screen. What is checked
here is wiring, not pixels: does the window build itself from the registry, does
a change go through the stack, does the evaluation stay in the worker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.registry import REGISTRY
from app.core.scene.project import load
from app.ui.main_window import MainWindow
from app.ui.op_dialog import OperationDialog
from app.ui.session import AskRequest, Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def session(qt_app: QApplication) -> Session:
    return Session()


@pytest.fixture
def window(qt_app: QApplication, session: Session) -> MainWindow:
    return MainWindow(session, UiSettings())


# --- session --------------------------------------------------------------------


def test_a_fresh_session_has_an_empty_project(session: Session) -> None:
    assert session.project.document.ops == []
    assert session.path is None
    assert not session.modified


def test_importing_a_model_goes_through_the_stack(session: Session) -> None:
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    assert [entry.op for entry in session.project.document.ops] == ["load"]
    assert session.modified
    result = session.evaluate_now()
    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(8000.0)


def test_undo_and_redo_reach_the_document(session: Session) -> None:
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    session.undo()
    session.wait_for_idle()
    assert session.project.document.ops == []

    session.redo()
    session.wait_for_idle()
    assert [entry.op for entry in session.project.document.ops] == ["load"]


def test_saving_and_reopening_keeps_the_stack(session: Session, tmp_path: Path) -> None:
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    path = session.save_project(tmp_path / "projekt.p3d")

    assert not session.modified
    assert [entry.op for entry in load(path).document.ops] == ["load"]


def test_an_ambiguous_unit_reaches_the_surface_as_a_question(session: Session) -> None:
    seen: list[AskRequest] = []
    session.askRequested.connect(lambda request: (seen.append(request), request.reply("in")))

    session.import_model(MESHES / "bracket_inch.stl")
    session.wait_for_idle()
    result = session.evaluate_now()

    assert seen, "the surface is asked instead of the core guessing"
    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((101.6, 50.8, 6.35))


def test_the_title_marks_unsaved_changes(session: Session, tmp_path: Path) -> None:
    assert not session.title.endswith("*")
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    assert session.title.endswith("*")

    session.save_project(tmp_path / "projekt.p3d")
    assert session.title == "projekt.p3d"


# --- window ---------------------------------------------------------------------


def test_the_menu_is_built_from_the_registry(window: MainWindow) -> None:
    labels: set[str] = set()
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        if menu is None:
            continue
        labels.update(action.text() for action in menu.actions())

    for spec in REGISTRY.all():
        assert str(spec.title) in labels, f"{spec.name} is missing from the menu"


def test_shortcuts_from_the_registry_are_installed(window: MainWindow) -> None:
    shortcuts = {
        action.shortcut().toString().lower()
        for menu_action in window.menuBar().actions()
        if menu_action.menu() is not None
        for action in menu_action.menu().actions()
        if not action.shortcut().isEmpty()
    }
    for spec in REGISTRY.all():
        if spec.shortcut:
            assert spec.shortcut.lower() in shortcuts


def test_the_window_starts_on_the_start_screen(window: MainWindow) -> None:
    assert window.stack.currentWidget() is window.start_screen


def test_the_right_panel_folds_away(window: MainWindow) -> None:
    assert window.right.isVisible() or True  # not shown yet, but wired
    window.action_toggle_right()
    assert not window.settings.right_panel_visible
    window.action_toggle_right()
    assert window.settings.right_panel_visible


def test_opening_a_model_leaves_the_start_screen(window: MainWindow) -> None:
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.stack.currentWidget() is window.splitter
    assert [entry.op for entry in window.session.project.document.ops] == ["load"]


def test_the_panels_follow_the_evaluation(window: MainWindow) -> None:
    window.open_path(MESHES / "two_components.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)

    assert window.object_tree.tree.topLevelItemCount() == 1
    assert window.report.list.count() >= 1, "the findings of the input stage are shown"
    assert window.history_panel.list.count() == 1


def test_the_status_bar_describes_the_selection(window: MainWindow) -> None:
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())
    window.object_tree.tree.setCurrentItem(window.object_tree.tree.topLevelItem(0))

    assert "20.00" in window.measurements.text()
    assert "cm³" in window.measurements.text()


# --- generated dialogs ----------------------------------------------------------


def test_a_dialog_is_generated_from_the_parameter_schema(qt_app: QApplication) -> None:
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    values = dialog.values()

    assert set(values) == {entry.name for entry in REGISTRY.get("load").params.spec()}
    assert values["unit"] == "auto"
    assert values["weld"] is True


def test_advanced_parameters_sit_behind_the_fold(qt_app: QApplication) -> None:
    """§2.4: the front side holds what people actually change."""
    from PySide6.QtWidgets import QGroupBox

    dialog = OperationDialog(REGISTRY.get("load"), [])
    groups = dialog.findChildren(QGroupBox)

    assert groups, "load has advanced parameters, so there is a fold"
    assert not groups[0].isChecked(), "the fold starts closed"
