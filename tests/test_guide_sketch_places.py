"""Punkte, Stellen, Bedingungen und die neue Ebene im Skizzeneditor als Wortschatz (FD-175).

Vier Fenster des Skizzeneditors hatten keinen Weg: *Koordinaten …* braucht einen
gewählten Punkt, *Abstand* zwei, die Frage nach dem neuen Maß eine Zeile der
Bedingungsliste und *Neue Ebene …* einen Eintrag im Ebenenfeld. Jetzt nennt der
Wortschatz die Stellen dazu — ``sketch.point:N``, ``sketch.at:X_Y``,
``sketch.constraint:<art>``, ``sketch.new_plane`` — und die Knöpfe
(``sketch.constrain:<art>``, ``sketch.coordinates``). Geprüft am Editor, wie ihn
das Feld *Dichtweg* öffnet: ein Kreis um den festen Mittelpunkt mit Maß 20 mm.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core import guides
from app.ui import guide_targets

CIRCLE = (
    '{"plane":"plane:xy","elements":[{"kind":"circle","points":[[0.0,0.0],[20.0,0.0]]}],'
    '"constraints":[{"kind":"distance","targets":[0,1],"value":"20"},'
    '{"kind":"fixed","targets":[0]}]}'
)


@pytest.mark.parametrize(
    ("name", "known"),
    [
        ("sketch.point:2", True),
        ("sketch.point:0", False),
        ("sketch.at:5_10", True),
        ("sketch.at:5", False),
        ("sketch.constraint:distance", True),
        ("sketch.constrain:distance", True),
        ("sketch.coordinates", True),
        ("sketch.new_plane", True),
    ],
)
def test_the_sketch_names_belong_to_the_vocabulary(name: str, known: bool) -> None:
    assert guides.is_target(name) is known


def _in_editor(qt_app: Any, look: Any) -> list[Any]:
    """``look(dialog)`` im offenen Skizzeneditor, wie ihn ``SketchField`` modal öffnet."""
    from PySide6.QtCore import QTimer

    from app.ui.sketch_editor import SketchEditorDialog

    dialog = SketchEditorDialog(CIRCLE)
    found: list[Any] = []

    def run() -> None:
        try:
            found.append(look(dialog))
        except Exception as error:  # Der Befund gehört ins Ergebnis, nicht in die Schleife.
            found.append(error)
        finally:
            dialog.reject()

    QTimer.singleShot(150, run)
    dialog.exec()
    dialog.deleteLater()
    qt_app.processEvents()
    return found


def test_a_point_and_a_spot_are_clicked_where_the_canvas_draws_them(qt_app: Any) -> None:
    window = SimpleNamespace(_sketch_panel=None)

    def look(dialog: Any) -> Any:
        canvas = dialog.canvas
        rim = guide_targets.next_click(window, "sketch.point:2")  # type: ignore[arg-type]
        spot = guide_targets.next_click(window, "sketch.at:5_10")  # type: ignore[arg-type]
        drawn = canvas.mapToGlobal(canvas._to_screen(20.0, 0.0).toPoint())
        aimed = canvas.mapToGlobal(canvas._to_screen(5.0, 10.0).toPoint())
        return rim.rect.center(), drawn, spot.rect.center(), aimed, rim.why

    ((rim, drawn, spot, aimed, why),) = _in_editor(qt_app, look)
    assert (rim, spot, why) == (drawn, aimed, "ziel")


def test_a_constraint_row_is_found_by_its_kind_at_the_selection(qt_app: Any) -> None:
    """Die Liste zeigt, was am gewählten Mittelpunkt hängt — darunter das Maß."""
    window = SimpleNamespace(_sketch_panel=None)

    def look(dialog: Any) -> Any:
        listing = dialog.panel.constraint_list
        # Wie ein Klick auf den Mittelpunkt (``SketchCanvas._select``).
        dialog.canvas._select(("point", (0,)), False)
        qt_app.processEvents()
        click = guide_targets.next_click(window, "sketch.constraint:distance")  # type: ignore[arg-type]
        row = listing.row(listing.itemAt(listing.viewport().mapFromGlobal(click.rect.center())))
        kinds = [
            dialog.canvas.sketch.constraints[index].kind
            for index in dialog.panel.constraint_indices(row)
        ]
        with pytest.raises(guide_targets.MissingTargetError):
            guide_targets.next_click(window, "sketch.constraint:angle")  # type: ignore[arg-type]
        return kinds

    assert _in_editor(qt_app, look) == [["distance"]]


def test_the_new_plane_opens_its_field_first(qt_app: Any) -> None:
    window = SimpleNamespace(_sketch_panel=None)

    def look(dialog: Any) -> Any:
        field = dialog.panel.plane_choice
        first = guide_targets.next_click(window, "sketch.new_plane")  # type: ignore[arg-type]
        field.showPopup()
        qt_app.processEvents()
        try:
            second = guide_targets.next_click(window, "sketch.new_plane")  # type: ignore[arg-type]
        finally:
            field.hidePopup()
        return first.why, second.why

    assert _in_editor(qt_app, look) == [("aufklappen", "ziel")]


def test_the_buttons_of_the_editor_carry_their_names(qt_app: Any) -> None:
    from PySide6.QtWidgets import QWidget

    # Ein Fenster ohne Zeichenmodus: Gesucht wird im offenen Editor obenauf.
    window = QWidget()
    window._sketch_panel = None  # type: ignore[attr-defined]
    window._op_dialog = None  # type: ignore[attr-defined]

    def look(dialog: Any) -> Any:
        coordinates = guide_targets.widget_for(window, "sketch.coordinates")  # type: ignore[arg-type]
        distance = guide_targets.widget_for(window, "sketch.constrain:distance")  # type: ignore[arg-type]
        return coordinates is dialog.panel.coordinate_button, distance.window() is dialog

    found = _in_editor(qt_app, look)
    window.deleteLater()
    assert found == [(True, True)]
