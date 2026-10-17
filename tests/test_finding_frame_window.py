"""Die Befundauswahl rahmt den Körper, und ein anderes Projekt rahmt neu (FD-111).

Ein Befund ohne eigenen Ort (zu groß für den Bauraum, Erkennung übersprungen,
Netzfehler einer Operation) wählte den Körper und ließ die Kamera stehen — im
Prüfstand stand sie noch in der Nahsicht der vorigen Szene, und der 400er
Quader füllte das Bild. Das Öffnen des Projekts hatte nicht neu gerahmt, weil
sein Körper wieder ``obj_1`` hieß und das als Verschieben galt.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.render_fakes import RecordingRenderer


@pytest.fixture
def host(qt_app: QApplication) -> Iterator[tuple[MainWindow, RecordingRenderer]]:
    """Ein Fenster mit einem Körper und einer Rendererattrappe."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Scene, SceneObject

    window = MainWindow(Session(), UiSettings())
    renderer = RecordingRenderer()
    window.viewport.renderer = renderer
    body = SceneObject(
        id="obj_1",
        name="Quader",
        mesh=MeshData.of(trimesh.creation.box(extents=(400.0, 300.0, 20.0))),
    )
    result = EvaluationResult(Scene(objects={"obj_1": body}))
    window.session.last_result = result
    window.session.result_current = True
    window.viewport.show_scene(result)
    window.object_tree.show_scene(result)
    try:
        yield window, renderer
    finally:
        from shiboken6 import isValid

        if isValid(window):
            window.release()
            window.viewport.renderer = None
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_a_finding_without_a_place_frames_its_body(
    host: tuple[MainWindow, RecordingRenderer],
) -> None:
    from app.core.types import Finding

    window, renderer = host
    finding = Finding(
        code="arrange.out_of_build_volume",
        severity="warning",
        message="Ein Objekt steht über den Bauraum hinaus.",
        object_id="obj_1",
    )
    before = len(renderer.reset_bounds)
    window._on_finding_activated(finding)
    assert window.object_tree.selected() == "obj_1"
    assert len(renderer.reset_bounds) > before, "die Kamera blieb, wo sie war"
    bounds = renderer.reset_bounds[-1]
    assert bounds is not None
    width = bounds[1] - bounds[0]
    assert width >= 400.0, "gerahmt wird der Körper des Befunds"


def test_another_project_is_framed_when_its_scene_arrives(
    host: tuple[MainWindow, RecordingRenderer],
) -> None:
    """Das zweite Projekt trägt wieder ``obj_1``, und es steht trotzdem im Bild."""
    window, renderer = host
    # Das Fenster kennt sein erstes Projekt, wie nach dem Start.
    window.session.projectChanged.emit()
    shown = window.session.last_result
    assert shown is not None and window.viewport._fitted_to == "objects"
    window.session.start_new()
    before = len(renderer.reset_bounds)
    window.viewport.show_scene(shown)
    assert len(renderer.reset_bounds) > before, "das neue Projekt stand in der alten Kamera"
