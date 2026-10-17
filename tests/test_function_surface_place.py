"""Die Fläche einer Zeile ist die Fläche um ihr Ziel, nicht die Auswahlkarte (FD-130, RM-737).

``function_surface.surface_for`` kannte Dialog, Bericht, Werkzeugleiste und
Merkmal und fiel sonst auf die Karte der Auswahl zurück. Die Zeilen
``parameters`` und ``parameters.first`` maßen so Texte und Felder der rechten
Karte („Nichts gewählt …“); Wertfeld, Einheit und „…“ der Parameterzeile
fehlten, und E5, V1 bis V3 urteilten über die falsche Karte. Jetzt ist die
Fläche die Seite oder der Abschnitt der Karte, in der das Ziel steht; die
Auswahlkarte nur, wenn es dort steht.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


def _settle(qt_app: Any, rounds: int = 30) -> None:
    for _ in range(rounds):
        qt_app.processEvents()


@pytest.fixture
def with_parameter(qt_app: Any, tmp_path: Path) -> Iterator[Any]:
    """Das kleinste gemessene Fenster mit der Startszene der Zeile ``parameters.first``."""
    from app.core.scene.project import save
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from tools import function_scenes
    from tools.function_checks import SMALLEST_WINDOW

    path = tmp_path / "parameter.netz.p3d"
    save(function_scenes.build_scene("parameter.netz"), path)
    window = MainWindow(Session(), UiSettings())
    window.resize(*SMALLEST_WINDOW)
    window.show()
    window._show_start_screen(False)
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    _settle(qt_app)
    try:
        yield window
    finally:
        window.hide()
        window.release()


def test_the_parameter_rows_measure_the_parameter_section(qt_app: Any, with_parameter: Any) -> None:
    """Parameterleiste und erste Parameterzeile: der Abschnitt *Parameter* der linken Karte."""
    from app.ui import guide_targets
    from tools import function_surface

    window = with_parameter
    first = guide_targets.widget_for(window, "parameters.first")
    assert first.isVisible(), "Voraussetzung: die Szene trägt einen Parameter"
    for target in ("parameters", "parameters.first"):
        surface = function_surface.surface_for(window, target)
        assert surface is not window.feature_dock, target
        assert surface.isAncestorOf(window.parameters) and surface.isAncestorOf(first), target
        # Der Abschnitt, nicht die ganze linke Karte: Objekte und Verlauf gehören nicht dazu.
        assert not surface.isAncestorOf(window.object_tree), target
        assert not surface.isAncestorOf(window.history_panel), target


def test_each_target_measures_the_part_of_the_card_it_stands_in(
    qt_app: Any, with_parameter: Any
) -> None:
    """Die Auswahlkarte, wenn das Ziel dort steht; sonst Bericht, Abschnitt, Leiste."""
    from tools import function_surface

    window = with_parameter
    surface = function_surface.surface_for
    # Nach dem Öffnen steht der Prüfbericht vorn, nach der Auswahl die Auswahlkarte.
    assert window.report.isVisible()
    assert surface(window, "report") is window.report
    window.object_tree.select_object("obj_1")
    _settle(qt_app)
    # Gegenprobe: Was in der Auswahlkarte steht, misst weiter die Auswahlkarte.
    assert surface(window, "search") is window.feature_dock
    assert surface(window, "selection") is window.feature_dock
    assert surface(window, "toolbar") is window.toolbar
    objects = surface(window, "tree.row:obj_1")
    assert objects.isAncestorOf(window.object_tree)
    assert not objects.isAncestorOf(window.parameters)
    assert surface(window, "menu:menubar.speichern") is window.menuBar()
