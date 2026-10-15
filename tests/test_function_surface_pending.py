"""Ein Balken ohne Ende im Fenster, in dem der Kunde arbeitet, sagt: Gleich kommt etwas (FD-101).

*Wählen …* im Fenster einer neuen Spule liest die Profile des Slicers im
Arbeiter und zeigt solange einen Balken ohne Ende mit *Abbrechen*; die Auswahl
öffnet erst mit der Antwort. Der Prüfstand kannte als Zeichen nur die rechnende
Sitzung und den Satz des Merkmalfensters, gab dem Fenster zwei Sekunden und
meldete „nicht auffindbar“, obwohl es danach dastand.

Ohne modales Fenster arbeitet der Kunde im Hauptfenster: Das Filamentlager liegt
dort als Seite, zeigt beim Lesen der Slicerfilamente sofort den Wartezeiger und
den Balken erst nach zwei Sekunden — so lange gab der Prüfstand der Auswahl, und
*Aus dem Slicer übernehmen* hieß „nicht auffindbar“ (FD-175).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tools.function_surface import pending


def _window() -> Any:
    """Ein Hauptfenster mit Sitzung und Merkmalfenster — mehr fragt ``pending`` nicht."""
    from PySide6.QtWidgets import QWidget

    window = QWidget()
    window.session = SimpleNamespace(busy=False)  # type: ignore[attr-defined]
    window.feature_panel = QWidget(window)  # type: ignore[attr-defined]
    return window


@pytest.mark.parametrize(
    ("bar", "expected"),
    [("ohne_ende", True), ("verborgen", False), ("mit_ende", False)],
    ids=["ohne-ende", "verborgen", "mit-ende"],
)
def test_a_bar_without_end_in_the_modal_window_is_pending(
    qt_app: Any, bar: str, expected: bool
) -> None:
    from PySide6.QtWidgets import QDialog, QProgressBar, QVBoxLayout

    window = _window()
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
        qt_app.processEvents()
    # Ohne Fenster sagt nichts mehr, dass etwas kommt.
    try:
        assert pending(window) is False
    finally:
        window.deleteLater()
        qt_app.processEvents()


@pytest.mark.parametrize("sign", ["balken", "wartezeiger", "nichts"])
def test_a_page_of_the_main_window_that_waits_is_pending(qt_app: Any, sign: str) -> None:
    """Ohne modales Fenster zählt das Hauptfenster: Balken ohne Ende oder Wartezeiger (FD-175)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QProgressBar, QVBoxLayout, QWidget

    window = _window()
    page = QWidget(window)
    QVBoxLayout(window).addWidget(page)
    progress = QProgressBar(page)
    progress.setRange(0, 0)
    progress.setVisible(sign == "balken")
    if sign == "wartezeiger":
        page.setCursor(Qt.CursorShape.BusyCursor)
    window.show()
    for _ in range(20):
        qt_app.processEvents()
    try:
        assert pending(window) is (sign != "nichts")
    finally:
        window.hide()
        window.deleteLater()
        qt_app.processEvents()
