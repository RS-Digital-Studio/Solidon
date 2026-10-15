"""Ein Balken ohne Ende im Fenster, in dem der Kunde arbeitet, sagt: Gleich kommt etwas (FD-101).

*Wählen …* im Fenster einer neuen Spule liest die Profile des Slicers im
Arbeiter und zeigt solange einen Balken ohne Ende mit *Abbrechen*; die Auswahl
öffnet erst mit der Antwort. Der Prüfstand kannte als Zeichen nur die rechnende
Sitzung und den Satz des Merkmalfensters, gab dem Fenster zwei Sekunden und
meldete „nicht auffindbar“, obwohl es danach dastand.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tools.function_surface import pending


@pytest.mark.parametrize(
    ("bar", "expected"),
    [("ohne_ende", True), ("verborgen", False), ("mit_ende", False)],
    ids=["ohne-ende", "verborgen", "mit-ende"],
)
def test_a_bar_without_end_in_the_modal_window_is_pending(
    qt_app: Any, bar: str, expected: bool
) -> None:
    from PySide6.QtWidgets import QDialog, QProgressBar, QVBoxLayout, QWidget

    window = SimpleNamespace(session=SimpleNamespace(busy=False), feature_panel=QWidget())
    dialog = QDialog()
    dialog.setModal(True)
    progress = QProgressBar(dialog)
    QVBoxLayout(dialog).addWidget(progress)
    progress.setRange(0, 0 if bar != "mit_ende" else 100)
    progress.setVisible(bar != "verborgen")
    dialog.show()
    for _ in range(20):
        qt_app.processEvents()
    try:
        assert pending(window) is expected
    finally:
        dialog.hide()
        dialog.deleteLater()
        window.feature_panel.deleteLater()
        qt_app.processEvents()
    # Ohne Fenster sagt nichts mehr, dass etwas kommt.
    assert pending(window) is False
