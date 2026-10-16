"""Ein Fenster mit gewählter Bohrung, dessen Karte steht — für die Fenstertests der Auswahlkarte.

Gebraucht von ``test_feature_footer_window.py``, ``test_feature_footer_low_window.py``
und ``test_card_tab_chain.py``. Ein eigenes Modul statt einer Fixture, die eine
Testdatei aus der anderen holt (Review 1 Restpaket A, RA-9).

Die Karte öffnet mit einer Bewegung über Zeitgeber; davor misst ihr Sichtfeld
rund 90 Punkte, und jede Lagefrage wäre erfunden. :func:`settle` wartet, bis die
Seite eine Weile dieselbe Größe hat.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

from app.core.scene.project import save
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import wait_for_print_findings
from tools import function_scenes


def settle(qt_app: QApplication, page: QWidget) -> None:
    """Bis die Seite dreißig Runden lang dieselbe Größe hat, höchstens zehn Sekunden."""
    last, still = None, 0
    deadline = time.monotonic() + 10
    while still < 30 and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
        size = page.size()
        still = still + 1 if size == last else 0
        last = size


@contextmanager
def hole_window(
    qt_app: QApplication, folder: Path, width: int, height: int
) -> Iterator[MainWindow]:
    """Das Fenster in dieser Größe mit der erkannten Bohrung gewählt; danach abgebaut."""
    path = folder / "bohrung.p3d"
    save(function_scenes.build_scene("erkannte_bohrung.netz"), path)
    window = MainWindow(Session(), UiSettings())
    window.resize(width, height)
    window.show()
    window._show_start_screen(False)
    try:
        window.open_path(path)
        assert window.session.wait_for_idle(60_000)
        wait_for_print_findings(window)
        result = window.session.last_result
        object_id = next(iter(result.scene.objects))
        hole = next(
            name
            for name, feature in result.scene.objects[object_id].features.items()
            if feature.kind == "hole"
        )
        window.object_tree.select_feature(object_id, hole)
        for _round in range(10):
            qt_app.processEvents()
        assert window.session.wait_for_idle(60_000)
        settle(qt_app, window.feature_dock)
        yield window
    finally:
        assert window.session.wait_for_idle(60_000)
        window.wait_for_workers()
        window.hide()
        window.deleteLater()
        qt_app.processEvents()
