"""Die Auswahlkarte hält keinen Leerraum zwischen Liste und „Filament und Druck“ (FD-93).

Am Zapfen standen rund 75 Punkte leer zwischen „Prüfstück erzeugen“ und
„Filament und Druck“: Das Panel der Handlungen reservierte eine feste
Mindesthöhe (``PANEL_LEAST_HEIGHT``, 280 Punkte), und was der Inhalt davon
nicht brauchte, bekam die Liste als Stretch. Die Höhe kommt jetzt aus dem
sichtbaren Inhalt; die Liste wächst nicht über ihren Wunsch, und was ein
Träger an Höhe übrig lässt, steht unter dem letzten Abschnitt.

Die Fläche ist die kleinste, für die Solidon gebaut ist: 1920 × 1080 logisch.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QToolButton

from app.core.scene.project import save
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.style import NORMAL
from tests.ui_helpers import wait_for_print_findings
from tools import function_scenes


@pytest.fixture(autouse=True)
def _readable_font(qt_app: QApplication) -> Iterator[None]:
    """Eine echte Schrift: Offscreen misst Qt unter Windows sonst Ersatzkästchen,
    und die breiten Kästchen füllten die reservierte Höhe von selbst."""
    fonts = Path(__file__).parents[1] / "app/core/geom/data/fonts"
    font_ids = [
        QFontDatabase.addApplicationFont(str(fonts / name))
        for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
    ]
    assert min(font_ids) >= 0, "Die gebündelte Prüfschrift wurde nicht geladen"
    before = qt_app.font()
    qt_app.setFont(QFont("DejaVu Sans", 9))
    yield
    qt_app.setFont(before)
    for font_id in font_ids:
        QFontDatabase.removeApplicationFont(font_id)


@pytest.fixture
def a_pin(qt_app: QApplication, tmp_path: Path) -> Iterator[MainWindow]:
    """Ein Netzkörper mit Zapfen, der Zapfen gewählt."""
    path = tmp_path / "zapfen.p3d"
    save(function_scenes.build_scene("merkmal.pin.netz"), path)
    window = MainWindow(Session(), UiSettings())
    window.resize(1920, 1080)
    window.show()
    window._show_start_screen(False)
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    wait_for_print_findings(window)
    result = window.session.last_result
    object_id = next(iter(result.scene.objects))
    pin = next(
        name
        for name, feature in result.scene.objects[object_id].features.items()
        if feature.kind == "pin"
    )
    window.object_tree.select_feature(object_id, pin)
    for _round in range(10):
        qt_app.processEvents()
    assert window.session.wait_for_idle(60_000)
    qt_app.processEvents()
    yield window
    assert window.session.wait_for_idle(60_000)
    window.wait_for_workers()
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


def test_no_empty_band_between_the_list_and_the_print_section(
    qt_app: QApplication, a_pin: MainWindow
) -> None:
    panel = a_pin.selection_operations
    section = panel.print_section
    assert section.isVisible(), "ohne Filamentabschnitt prüft dieser Test nichts"
    # Der Leerraum lag **in** der Liste: Sie war höher als ihre Knöpfe. Gemessen
    # wird vom letzten sichtbaren Knopf der Liste bis zur Klappe darunter.
    for _round in range(10):
        qt_app.processEvents()
    content = panel.scroller.widget()
    shown = [button for button in content.findChildren(QToolButton) if button.isVisibleTo(content)]
    assert shown, "ohne sichtbare Listenzeile prüft dieser Test nichts"
    last = max(button.mapTo(panel, button.rect().bottomLeft()).y() for button in shown)
    gap = section.geometry().top() - last
    assert gap <= 3 * NORMAL, f"{gap} Punkte leer über „Filament und Druck“"
