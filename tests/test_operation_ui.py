"""Selecting a face, and correcting an operation afterwards (§18.5, §15.4).

Offscreen, and without opening a single dialog: a test that calls ``exec()``
waits for a person who is not there. What is checked is what goes *into* the
dialog and what comes back out of the change — the dialog itself is generated
from the schema and checked in ``tests/test_ui.py``.

The same trap has a second door, and it cost an afternoon here: a live
``MainWindow`` answers ``session.failed`` with a modal message box. Anything
that is *meant* to fail therefore runs on a bare ``Session``, which carries the
same signal and shows nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.errors import ValidationError
from app.core.registry import REGISTRY
from app.core.scene import OperationDraft
from app.ui.main_window import MainWindow
from app.ui.op_dialog import OperationDialog
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    """The plate with four bores — every feature kind this needs is on it."""
    window = MainWindow(Session(), UiSettings())
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    return window


def select(window: MainWindow, feature_id: str | None = None) -> str:
    """Pick the object and, if asked, one of its features — as a click would."""
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    object_id = window.object_tree.selected()
    assert object_id is not None

    if feature_id is not None:
        for index in range(item.childCount()):
            child = item.child(index)
            assert child is not None
            if window.object_tree.tree.itemWidget(child, 0) is None and feature_id in (
                child.data(1, 0x0100),
                child.data(1, 32),
            ):
                child.setSelected(True)
                item.setSelected(False)
                break
    return object_id


# --- the selection reaches the dialog -------------------------------------------


def test_without_a_feature_nothing_is_filled_in(window: MainWindow) -> None:
    object_id = select(window)

    assert window._from_selection(REGISTRY.get("drill_hole"), object_id) == {}


def test_a_selected_bore_fills_in_where_it_is(window: MainWindow) -> None:
    """The join §25 asks for: the operation starts where the feature is.

    plate_holes has its bores at ±25/±15, so the filled-in position can be
    checked against the file rather than against itself.
    """
    object_id = select(window)
    window._on_feature_picked("hole_1")

    values = window._from_selection(REGISTRY.get("drill_hole"), object_id)

    assert set(values) >= {"x", "y", "z", "axis"}
    assert (abs(values["x"]), abs(values["y"])) == (pytest.approx(25.0), pytest.approx(15.0))
    assert values["axis"] == "z"


def test_a_part_is_told_the_name_of_the_feature(window: MainWindow) -> None:
    object_id = select(window)
    window._on_feature_picked("hole_1")

    values = window._from_selection(REGISTRY.get("insert_heatset_m4"), object_id)

    assert values == {"at_feature": "hole_1"}


def test_a_feature_that_is_gone_fills_in_nothing(window: MainWindow) -> None:
    """Not an error: the tree and the scene may be a moment apart."""
    object_id = select(window)
    window._on_feature_picked("hole_99")

    assert window._from_selection(REGISTRY.get("drill_hole"), object_id) == {}


# --- the dialog opens on values instead of defaults -----------------------------


def test_the_dialog_starts_on_what_it_was_given(qt_app: QApplication) -> None:
    spec = REGISTRY.get("drill_hole")

    dialog = OperationDialog(spec, [], None, values={"diameter": 8.5, "x": -12.0, "axis": "y"})

    assert dialog.values()["diameter"] == pytest.approx(8.5)
    assert dialog.values()["x"] == pytest.approx(-12.0)
    assert dialog.values()["axis"] == "y"


def test_what_it_was_not_given_keeps_the_default(qt_app: QApplication) -> None:
    spec = REGISTRY.get("drill_hole")

    dialog = OperationDialog(spec, [], None, values={"x": 3.0})

    assert dialog.values()["diameter"] == pytest.approx(5.0), "the schema's default"


def test_a_filled_in_value_is_not_hidden_behind_the_advanced_box(qt_app: QApplication) -> None:
    """A value that was just decided belongs where it can be seen."""
    spec = REGISTRY.get("drill_hole")
    depth = next(entry for entry in spec.params.spec() if entry.name == "depth")
    assert depth.placement == "advanced", "otherwise this test proves nothing"

    dialog = OperationDialog(spec, [], None, values={"depth": 4.0})

    assert dialog.values()["depth"] == pytest.approx(4.0)


# --- correcting an operation ----------------------------------------------------


def test_an_operation_can_be_given_other_numbers(window: MainWindow) -> None:
    select(window)
    window.session.apply(
        "Bohren",
        [
            OperationDraft(
                op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "x": 0.0, "y": 0.0}
            )
        ],
    )
    window.session.wait_for_idle()
    op_id = window.session.project.document.ops[-1].id

    window.session.change_params(op_id, {"x": 10.0})
    window.session.wait_for_idle()

    assert window.session.history.operation(op_id).params["x"] == pytest.approx(10.0)
    assert window.session.history.operation(op_id).params["diameter"] == pytest.approx(5.0)
    assert window.session.last_result is not None
    assert window.session.last_result.complete


def test_a_refused_change_reaches_the_surface_as_a_suggestion(qt_app: QApplication) -> None:
    """§2.7: what cannot be done is said, not swallowed.

    On the session alone, without a window: a live ``MainWindow`` answers
    ``failed`` with a modal message box, and a test that lets one open waits for
    somebody to click it. What is checked here is that the signal carries the
    error — who shows it is the window's business.
    """
    session = Session()
    problems: list[object] = []
    session.failed.connect(problems.append)

    session.change_params(999, {"x": 1.0})

    assert problems and isinstance(problems[0], ValidationError)


def test_every_operation_of_the_history_can_be_opened(window: MainWindow) -> None:
    """A transaction of several operations gets a row per operation (§15.4)."""
    select(window)
    window.session.apply(
        "Zwei Schritte",
        [
            OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Platte"}),
            OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 4.0}),
        ],
    )
    window.session.wait_for_idle()
    QApplication.processEvents()

    rows = window.history_panel.list
    reachable = {
        rows.item(index).data(0x0100)
        for index in range(rows.count())
        if rows.item(index) is not None and rows.item(index).data(0x0100) is not None
    }

    assert {entry.id for entry in window.session.project.document.ops} <= reachable
