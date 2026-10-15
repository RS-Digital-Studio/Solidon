"""Eine Absage spricht in den Wörtern des Fensters (FD-95, FD-105, FD-118).

* Unter einer Schrittabsage stand ihr Titel noch einmal als „Art: …“, und
  *Eingabe korrigieren* war im offenen Dialog ein Satz ohne Knopf (FD-95).
* *Einzelheiten* nannten „obj_1“, „Operation: 3“ und eine Stelle mit sechzehn
  Nachkommastellen; *Werte ansehen* zeigte „paint_slot“ und „radius = 12.0“ in
  einem Fenster für zwanzig Zeilen (FD-105, FD-118).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QApplication, QPushButton

from app.core import bootstrap
from app.core.errors import CANCEL, CORRECT_INPUT, AppError, ValidationError
from app.core.registry import REGISTRY
from app.ui.dialogs import problem_text, spoken_values

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
