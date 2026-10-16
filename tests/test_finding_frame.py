"""Der Flug zu einer Befundstelle zeigt sie in jeder Projektion gleich groß (FD-111).

Perspektivisch gibt der Abstand die Bildgröße vor; orthografisch tut er es
nicht, und die Stelle stand mittig, aber so groß wie der Zoom davor — winzig
oder formatfüllend. Geprüft an der Entscheidung der Ansicht mit einer
Rendererattrappe (``qt_app``: die Ansicht ist ein Widget).
"""

from __future__ import annotations

import math
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from app.ui.render.api import CameraPose
from tests.render_fakes import RecordingRenderer


@pytest.fixture
def view_and_renderer(qt_app: QApplication) -> Iterator[tuple[object, RecordingRenderer]]:
    from app.ui.viewport import Viewport

    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    renderer.set_camera_pose(CameraPose((300.0, -300.0, 240.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
    try:
        yield view, renderer
    finally:
        view.renderer = None
        view.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("zoom_before", [2000.0, 3.0])
def test_an_orthographic_flight_sizes_the_place_like_the_perspective_one(
    view_and_renderer: tuple[object, RecordingRenderer], zoom_before: float
) -> None:
    """Weit herausgezoomt wie hineingezoomt: Nach dem Flug gilt der Abstand."""
    view, renderer = view_and_renderer
    renderer.set_parallel_projection(True)
    renderer.set_parallel_scale(zoom_before)
    view.fly_to((10.0, 20.0, 5.0), reach=140.0)  # type: ignore[attr-defined]
    expected = 140.0 * math.tan(math.radians(renderer.view_angle()) / 2.0)
    assert renderer.parallel_scale() == pytest.approx(expected)
    assert renderer.camera_pose().focal_point == pytest.approx((10.0, 20.0, 5.0))


def test_a_perspective_flight_leaves_the_parallel_scale_alone(
    view_and_renderer: tuple[object, RecordingRenderer],
) -> None:
    """Perspektivisch trägt der Abstand die Größe; der Maßstab bleibt, wie er war."""
    view, renderer = view_and_renderer
    renderer.set_parallel_scale(77.0)
    view.fly_to((10.0, 20.0, 5.0), reach=140.0)  # type: ignore[attr-defined]
    assert renderer.parallel_scale() == pytest.approx(77.0)
    pose = renderer.camera_pose()
    assert math.dist(pose.position, pose.focal_point) == pytest.approx(140.0)
