"""*Kopieren* im Fenster *Werte dieses Schritts* gibt die gespeicherten Werte (RA-7).

Der Dialog verspricht: „seine Werte stehen aber unverändert in der Datei. Sie
lassen sich hier herauskopieren.“ Gezeigt wird lesbar (Feldnamen, Anzeigeeinheit,
gerundet); kopiert wurde dasselbe — aus 12,3456 mm wurden „12,35 mm“, in Zoll
„0,4860 in“. Jetzt gibt *Kopieren* Schlüssel und Zahl wie in der Datei.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtWidgets import QApplication, QPushButton

from app.ui.labels import set_display_unit


@dataclass
class _Step:
    op: str
    params: dict[str, Any] = field(default_factory=dict)


def test_copy_hands_out_the_stored_values(qt_app: QApplication) -> None:
    from app.ui.refusal_details import StepValuesDialog

    step = _Step("paint_slot", {"x": 12.3456, "radius": 3.14159, "slot": 2})
    set_display_unit("in")
    dialog = StepValuesDialog(step)
    try:
        shown = dialog.text.toPlainText()
        assert "12.3456" not in shown and "in" in shown, "gezeigt wird lesbar"
        copy = next(
            button for button in dialog.findChildren(QPushButton) if button.text() == "Kopieren"
        )
        copy.click()
        clipboard = QApplication.clipboard()
        assert clipboard is not None
        copied = clipboard.text()
        assert "x = 12.3456" in copied, copied
        assert "radius = 3.14159" in copied, copied
        assert "slot = 2" in copied, copied
    finally:
        dialog.deleteLater()
        set_display_unit("mm")
