"""Feldwege, Rat und Knopf nach dem Merge von Restpaket A und B — im Dialog und im Fenster.

Drei Regeln treffen sich in ``dialogs.ErrorNotice`` und ``dialogs.show_error``:

* FD-95: Im offenen Dialog ist *Eingabe korrigieren* ohne erreichbares Feld
  kein Rat — die Eingabe steht darüber.
* FD-182: Ein Feldweg ist ein Knopf nur, wo das Feld im Dialog steht; sonst
  steht *Eine andere Ebene wählen* als Rat.
* RB2-2: Was als Knopf steht, steht nicht noch einmal als Satz — auch ein Weg
  ohne Schritt, den der Dialog selbst einlöst.

Der zweite Weg ist das Fenster: Der Befund der Skizze mit unlesbarer Ebene
bietet *Eine andere Ebene wählen* als Knopf an (nicht als Satz), und der Knopf
öffnet den Schritt im Skizzenmodus, wo die Zeichenebene gewählt wird.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from app.core.bootstrap import load_operations
from app.core.errors import CORRECT_INPUT, PICK_PLANE, ValidationError
from app.core.registry import REGISTRY
from app.core.types import Action
from app.i18n import set_language
from app.i18n.catalog import install_language
from app.ui.dialogs import offered_actions, unhandled_advice
from app.ui.op_dialog import OperationDialog
from app.ui.theme import apply_theme
from tests.plane_refusals import UNREADABLE_PLANE, sketch_plane_refusal, square_on

#: Ein Weg ohne Schritt, den der Operationsdialog selbst einlöst (RB2-2).
REACHABLE = Action(id="use_reachable", label="Die kleinste Kantenlänge nehmen, die noch geht.")


def _rounds(qt_app: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qt_app.processEvents()
        time.sleep(0.005)


def _inside(widget: QWidget | None, editor: QWidget) -> bool:
    while widget is not None:
        if widget is editor:
            return True
        widget = widget.parentWidget()
    return False


def _buttons(dialog: OperationDialog) -> list[str]:
    return [
        button.text()
        for button in dialog._refusal.findChildren(QPushButton)
        if not button.isHidden()
    ]


@pytest.fixture
def sketch_dialog(qt_app: QApplication) -> Iterator[OperationDialog]:
    load_operations()
    install_language("de")
    set_language("de")
    apply_theme(qt_app, "light")
    dialog = OperationDialog(REGISTRY.get("sketch_pocket"), {"body": "Körper"})
    dialog.show()
    _rounds(qt_app)
    yield dialog
    dialog.close()
    dialog.deleteLater()


def test_a_reachable_field_way_is_a_button_and_not_a_sentence(
    qt_app: QApplication, sketch_dialog: OperationDialog
) -> None:
    """FD-182 und RB2-2: Knopf mit Sprung in die Skizze, kein Satz darüber."""
    error = sketch_plane_refusal(UNREADABLE_PLANE)
    assert error.values.get("field") == "sketch"
    sketch_dialog.show_refusal(error)
    _rounds(qt_app)
    assert _buttons(sketch_dialog) == [str(PICK_PLANE.label)]
    lines = sketch_dialog._refusal.text().splitlines()
    assert str(PICK_PLANE.label) not in lines, "der Knopf steht nicht noch einmal als Satz"
    next(
        button
        for button in sketch_dialog._refusal.findChildren(QPushButton)
        if button.text() == str(PICK_PLANE.label)
    ).click()
    _rounds(qt_app)
    assert _inside(sketch_dialog.focusWidget(), sketch_dialog._editors["sketch"])


def test_without_its_field_correct_input_is_silent_and_the_plane_way_is_advice(
    qt_app: QApplication, sketch_dialog: OperationDialog
) -> None:
    """FD-95 und FD-182: kein Knopf ins Leere, *Eingabe korrigieren* still, die Ebene als Rat."""
    error = ValidationError("no_such_field", "Absage", suggestions=[CORRECT_INPUT, PICK_PLANE])
    sketch_dialog.show_refusal(error)
    _rounds(qt_app)
    assert _buttons(sketch_dialog) == []
    lines = sketch_dialog._refusal.text().splitlines()
    assert str(CORRECT_INPUT.label) not in lines
    assert lines.count(str(PICK_PLANE.label)) == 1


def test_a_stepless_way_the_dialog_handles_stands_once_as_its_button(
    qt_app: QApplication, sketch_dialog: OperationDialog
) -> None:
    """RB2-2 zusammen mit den Feldwegen: Knopf ja, Satz nein, Feldweg weiter Knopf."""
    error = ValidationError(
        "depth", "Absage", suggestions=[REACHABLE, CORRECT_INPUT], values={"reachable": 1.5}
    )
    assert error.op_id is None
    sketch_dialog.show_refusal(error, {REACHABLE.id: lambda _error: None})
    _rounds(qt_app)
    assert sorted(_buttons(sketch_dialog)) == sorted(
        [str(REACHABLE.label), str(CORRECT_INPUT.label)]
    ), "der Weg ohne Schritt und der Feldsprung in die Tiefe"
    lines = sketch_dialog._refusal.text().splitlines()
    assert str(REACHABLE.label) not in lines
    assert str(CORRECT_INPUT.label) not in lines


def test_in_the_window_the_plane_way_is_a_button_that_opens_the_sketch(
    qt_app: QApplication,
) -> None:
    """Der zweite Weg: Befund aus der Kette, Knopf aus dem Fenster, Skizzenmodus mit der Ebene."""
    from app.core.scene import OperationDraft
    from app.ui.main_window import MainWindow
    from app.ui.panels import as_error
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    load_operations()
    install_language("de")
    set_language("de")
    window = MainWindow(Session(), UiSettings())
    window.resize(1600, 900)
    window.show()
    window._show_start_screen(False)
    try:
        window.session.apply(
            "Skizze",
            [
                OperationDraft(
                    op="sketch_extrude",
                    inputs=(),
                    params={"sketch": square_on(UNREADABLE_PLANE), "height": 4.0},
                )
            ],
        )
        assert window.session.wait_for_idle(60_000)
        _rounds(qt_app)
        result = window.session.last_result
        assert result is not None
        finding = next(
            entry for entry in result.scene.report.findings if PICK_PLANE in entry.suggestions
        )
        error = as_error(finding, window.session.project.document)
        handlers = window.error_handlers()
        assert error.op_id is not None
        assert PICK_PLANE in offered_actions(error, handlers), "im Fenster ein Knopf"
        assert str(PICK_PLANE.label) not in unhandled_advice(error, handlers), "und kein Satz"
        handlers[PICK_PLANE.id](error)
        _rounds(qt_app)
        # Die Ebene steht in der Skizze: Der Schritt geht im Skizzenmodus auf,
        # wo die Zeichenebene gewählt wird.
        panel = window._sketch_panel
        assert panel is not None, "der Schritt geht in seiner Skizze auf"
        assert panel.plane_choice.currentData() == UNREADABLE_PLANE, "die Ebene steht zur Wahl"
    finally:
        for child in window.findChildren(OperationDialog):
            child.reject()
        assert window.session.wait_for_idle(60_000)
        window.wait_for_workers()
        window.hide()
        window.deleteLater()
        qt_app.processEvents()
