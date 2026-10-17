"""Ein freigegebener Renderer bleibt nicht im Speicher der Ansicht (FD-193).

``Viewport.release_renderer`` schließt den Renderer beim Fensterende und beim
Sprachwechsel. Die Ansicht hielt ihn danach weiter — in den
Vergleichsschlüsseln ihrer Merkmalsflächen (``_Same(self.renderer)``) — bis
das Fenster selbst ging: nach einem Sprachwechsel blieb der alte Renderer mit
seinen Puffern liegen, und bis zum Fix in ``GfxRenderer.close`` auch seine
Bildschirmfläche bis zum Prozessende (CI-Probe 38855455034).
"""

from __future__ import annotations

import gc
import weakref

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from tests.ui_helpers import MESHES
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


def test_a_released_renderer_is_not_held_by_the_view(window: MainWindow) -> None:
    from tests.render_fakes import RecordingRenderer

    renderer = RecordingRenderer(size=(900, 600))
    window.viewport.renderer = renderer
    window.open_path(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(60_000)
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    window.object_tree.select_feature(object_id, hole)
    for _ in range(20):
        QApplication.processEvents()
    assert window.viewport._feature_patch_drawn is not None, "die Lage: eine Fläche steht"
    released = weakref.ref(renderer)
    del renderer
    window.viewport.release_renderer()
    for _ in range(5):
        QApplication.processEvents()
    gc.collect()
    assert released() is None, [type(holder).__name__ for holder in gc.get_referrers(released())]
