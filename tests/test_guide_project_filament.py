"""Die Zeile eines Filaments unter *Filamente* als Ort im Wortschatz (FD-175).

Die Druckwerte einer Spule öffnet ein Doppelklick auf ihre Zeile in der Liste der
Kopfzeile (``FilamentPanel._on_activated``). Ohne Namen für die Zeile hatte das
Fenster der Druckwerte keinen Weg, und der Sprachfall maß es nie.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import trimesh
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

from app.core import guides
from app.core.geom.mesh import MeshData
from app.core.scene import EvaluationResult
from app.core.types import MaterialSlot, Scene, SceneObject
from app.ui import guide_targets
from app.ui.main_window import MainWindow
from tests.ui_helpers import shown_window

NAME = "filaments.first"


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    """Gezeigt und ohne Startbildschirm: Erst dann steht *Filamente* in der Kopfzeile."""
    yield from shown_window(qt_app)


def _scene(window: MainWindow, *, painted: bool) -> None:
    """Ein Körper ohne Filament und, wenn ``painted``, einer in PETG Rot."""
    objects = {
        "obj_1": SceneObject(id="obj_1", name="Ohne", mesh=MeshData.of(trimesh.creation.box()))
    }
    if painted:
        objects["obj_2"] = SceneObject(
            id="obj_2",
            name="Rot",
            mesh=MeshData.of(trimesh.creation.box(), slots=(1,) * 12),
            material_slots=[MaterialSlot(index=1, name="PETG Rot", colour=(0.8, 0.1, 0.1))],
        )
    result = EvaluationResult(scene=Scene(objects=objects))
    window._show_project_filaments(result, window.effective_print_settings())


def test_the_first_filament_row_is_a_place_of_the_vocabulary() -> None:
    assert guides.is_target(NAME)
    assert NAME in guide_targets.RESOLVED


def test_the_way_to_the_row_opens_the_list_first_then_names_the_row(
    window: MainWindow, qt_app: QApplication
) -> None:
    """Erst *Filamente* in der Kopfzeile, dann die Zeile mit Filament — nicht *Ohne Filament*."""
    _scene(window, painted=True)
    qt_app.processEvents()
    button = window.header.filament_button
    first = guide_targets.next_click(window, NAME)
    assert first.why == "aufklappen"
    assert first.rect == QRect(button.mapToGlobal(QPoint(0, 0)), button.size())
    button.click()
    qt_app.processEvents()
    try:
        assert window.filament_popup.isVisible()
        click = guide_targets.next_click(window, NAME)
        listing = window.filaments.list
        item = listing.itemAt(listing.viewport().mapFromGlobal(click.rect.center()))
        assert click.why == "ziel"
        assert item is not None and "PETG Rot" in item.text(), item and item.text()
        assert guide_targets.area_for(window, NAME) == click.rect
    finally:
        window.filament_popup.hide()


def test_a_scene_without_filament_has_no_such_row(window: MainWindow, qt_app: QApplication) -> None:
    """*Ohne Filament* hat keine Druckwerte: Der Ort fehlt, und der Grund sagt es."""
    _scene(window, painted=False)
    qt_app.processEvents()
    window.header.filament_button.click()
    qt_app.processEvents()
    try:
        with pytest.raises(guide_targets.MissingTargetError, match="kein Körper"):
            guide_targets.next_click(window, NAME)
    finally:
        window.filament_popup.hide()
