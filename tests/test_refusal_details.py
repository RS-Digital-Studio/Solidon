"""Eine Absage spricht in den Wörtern des Fensters (FD-95, FD-105, FD-118).

* Unter einer Schrittabsage stand ihr Titel noch einmal als „Art: …“, und
  *Eingabe korrigieren* war im offenen Dialog ein Satz ohne Knopf (FD-95).
* *Einzelheiten* nannten „obj_1“, „Operation: 3“ und eine Stelle mit sechzehn
  Nachkommastellen; *Werte ansehen* zeigte „paint_slot“ und „radius = 12.0“ in
  einem Fenster für zwanzig Zeilen (FD-105, FD-118).
"""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from app.core import bootstrap
from app.core.errors import CANCEL, CORRECT_INPUT, AppError, ValidationError
from app.core.registry import REGISTRY
from app.core.scene import OperationDraft
from app.core.types import Operation
from app.ui.dialogs import problem_text, spoken_values
from app.ui.session import Session
from tests.ui_helpers import session as session

#: Der Titel, den ``evaluate._finding_from`` einer Schrittabsage als ``kind`` mitgibt.
STEP_TITLE = "Die Eingabe war so nicht verwendbar."


def test_a_step_refusal_does_not_repeat_its_title_as_kind() -> None:
    """FD-95: „Art: Die Eingabe war so nicht verwendbar.“ unter dem Satz, der es
    schon sagt — eine Quelle für Halt und Dialog (``spoken_values``)."""
    refusal = AppError(
        title="Der Abstand ist größer als der Körper.",
        op_id=3,
        values={"kind": STEP_TITLE, "spacing": 12.0},
    )
    lines = spoken_values(refusal)
    assert not any(STEP_TITLE in line for line in lines), lines
    assert any("12" in line for line in lines), "die übrigen Angaben bleiben"


def test_the_kind_of_a_feature_stays_because_it_says_something() -> None:
    """Eine Merkmalsart ist keine Wiederholung: „Art: Bohrung“ bleibt stehen."""
    part = AppError(title="Der Stift passt nicht.", op_id=3, values={"kind": "hole"})
    assert "Art: Bohrung" in spoken_values(part)


def test_a_refusal_outside_a_step_keeps_its_kind() -> None:
    """Ohne Schritt ist ``kind`` keine Wiederholung des Titels."""
    error = AppError(title="Zu groß.", values={"kind": "Würfel"})
    assert any("Würfel" in line for line in spoken_values(error))


def _drill_dialog() -> Any:
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    return OperationDialog(REGISTRY.get("drill_hole"), {})


def test_correct_input_in_the_open_dialog_jumps_into_the_named_field(
    qt_app: QApplication,
) -> None:
    """FD-95: Im Dialog, der selbst die Eingabe ist, wird *Eingabe korrigieren* ein
    Knopf, der den Cursor ins Feld setzt, das der Kern nennt."""
    dialog = _drill_dialog()
    try:
        dialog.show()
        QApplication.processEvents()
        refusal = ValidationError(
            "depth",
            "So tief reicht der Körper nicht.",
            constraint="maximum",
            values={"kind": STEP_TITLE},
            suggestions=(CORRECT_INPUT, CANCEL),
            op_id=1,
        )
        dialog.show_refusal(refusal, {})
        notice = dialog._refusal
        assert "Eingabe korrigieren" not in notice.text(), "kein Satz, sondern ein Knopf"
        assert STEP_TITLE not in notice.text()
        buttons = [b for b in notice.findChildren(QPushButton) if b.text() == "Eingabe korrigieren"]
        assert len(buttons) == 1
        dialog._editors["diameter"].setFocus()
        buttons[0].click()
        QApplication.processEvents()
        field = dialog._editors["depth"]
        focused = dialog.focusWidget()
        assert focused is field or field.isAncestorOf(focused), "der Cursor steht in Tiefe"
    finally:
        dialog.close()
        dialog.deleteLater()


def test_correct_input_without_a_field_is_left_out_in_the_open_dialog(
    qt_app: QApplication,
) -> None:
    """Ohne genanntes Feld ist *Eingabe korrigieren* im Dialog kein Rat — die
    Eingabe steht darüber. Im Fehlerdialog des Fensters bleibt der Satz."""
    dialog = _drill_dialog()
    try:
        refusal = AppError(
            title="Das geht so nicht.",
            detail="Die Bohrung trifft keinen Körper.",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
        dialog.show_refusal(refusal, {})
        notice = dialog._refusal
        assert "Eingabe korrigieren" not in notice.text()
        assert not [
            b for b in notice.findChildren(QPushButton) if b.text() == "Eingabe korrigieren"
        ]
        assert "Eingabe korrigieren" in problem_text(refusal, {}), "ohne Dialog bleibt der Rat"
    finally:
        dialog.deleteLater()


class _Host(QWidget):
    """Ein Fenster mit Sitzung, wie ``show_details`` es als Elternteil bekommt."""

    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session


def test_the_details_name_body_step_and_place_in_words(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FD-105: „Objekt: obj_1“, „Operation: 1“ und „Stelle: (1.33e-16, …)“."""
    from app.ui.dialogs import show_details
    from app.ui.message_dialog import MessageDialog

    assert session.apply("Quader", [OperationDraft(op="create_box")])
    assert session.wait_for_idle(30_000)
    result = session.last_result
    assert result is not None
    body = next(iter(result.scene.objects))
    step = session.project.document.ops[0]
    caught: list[Any] = []
    monkeypatch.setattr(MessageDialog, "exec", lambda dialog: caught.append(dialog) or 0)
    host = _Host(session)
    try:
        show_details(
            AppError(
                title="Die Wand ist zu dünn.",
                object_id=body,
                op_id=step.id,
                values={"location": (1.3325671035519837e-16, 0.0, 10.0)},
            ),
            host,
        )
        (box,) = caught
        text = box.details.toPlainText()
        name = str(result.scene.objects[body].name)
        assert f"Objekt: {name}" in text
        assert f"Schritt 1: {REGISTRY.get(step.op).title}" in text
        assert "Stelle: 0,00 / 0,00 / 10,00 mm" in text
        assert body not in text and "e-16" not in text and "Operation:" not in text
        box.deleteLater()
    finally:
        host.deleteLater()


LEGACY_PAINT = Operation(
    id=2,
    op="paint_slot",
    inputs=("obj_1",),
    params={"slot": 1, "radius": 12.0, "x": 0.0, "y": 0.0, "z": 8.0, "name": "Rot"},
)


def test_the_step_values_speak_the_window_words(qt_app: QApplication) -> None:
    """FD-105: Titel und Feldnamen statt „paint_slot“ und „radius = 12.0“ —
    auch für Werte, die das Schema nicht mehr kennt (der alte Punktpinsel)."""
    from app.ui.dialogs import StepValuesDialog

    bootstrap.load_operations()
    dialog = StepValuesDialog(LEGACY_PAINT)
    try:
        text = dialog.text.toPlainText()
        shown = " ".join(label.text() for label in dialog.findChildren(QLabel))
        assert str(REGISTRY.get("paint_slot").title) in shown, "der Titel, nicht paint_slot"
        assert "paint_slot" not in shown
        assert "Filament: 1" in text
        assert "Bezeichnung: Rot" in text
        assert "Radius: 12,00 mm" in text
        assert "Position X: 0,00 mm" in text and "Position Z: 8,00 mm" in text
        assert "radius =" not in text and "12.0" not in text
    finally:
        dialog.deleteLater()


def test_the_step_values_window_is_as_tall_as_its_lines(qt_app: QApplication) -> None:
    """FD-118: sechs Zeilen in einem Fenster von 520 × 360, zwei Drittel leer."""
    from app.ui.dialogs import StepValuesDialog

    bootstrap.load_operations()
    dialog = StepValuesDialog(LEGACY_PAINT)
    try:
        dialog.show()
        for _ in range(3):
            QApplication.processEvents()
        assert dialog.text.verticalScrollBar().maximum() == 0, "alle Zeilen sichtbar"
        lines = dialog.text.toPlainText().count("\n") + 1
        spare = dialog.text.height() - lines * dialog.text.fontMetrics().lineSpacing()
        assert spare < 3 * dialog.text.fontMetrics().lineSpacing(), f"{spare} px leer"
        assert dialog.height() < 360
        assert dialog.text.accessibleName(), "FD-94: das Textfeld hat einen Namen"
    finally:
        dialog.close()
        dialog.deleteLater()
