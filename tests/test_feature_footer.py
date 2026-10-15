"""Die Knopfzeile des Merkmalfensters steht unter der offenen Handlung (FD-136).

„Merkmal ändern“ stand offen oben in der Karte, *Übernehmen* ganz unten unter
„Filament und Druck“ — der Blick sprang über die ganze Karte. Gehört die
Knopfzeile dem Panel, steht sie jetzt direkt unter der scharfen Handlung und
wandert mit, wenn eine andere scharf wird.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.core.geom.mesh import read_mesh
from app.core.perceive import features
from app.ui.panels import FeaturePanel

MESHES = Path(__file__).parent / "data" / "meshes"


def _hole_panel() -> FeaturePanel:
    mesh = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")
    found = features.detect(mesh)
    identifier, hole = next((key, value) for key, value in found.items() if value.kind == "hole")
    panel = FeaturePanel()
    panel.show_feature(identifier, hole, features=found, mesh=mesh)
    panel.resize(420, 900)
    panel.show()
    QApplication.processEvents()
    return panel


def _armed_box(panel: FeaturePanel) -> object:
    return next(row.box for row in panel._shown_rows.values() if row.key == panel._armed)


def test_the_footer_stands_right_below_the_open_handling(qt_app: QApplication) -> None:
    panel = _hole_panel()
    try:
        rows = panel._rows
        assert panel._armed is not None, "ohne scharfe Handlung prüft dieser Test nichts"
        assert rows.indexOf(panel._footer) == rows.indexOf(_armed_box(panel)) + 1
        assert panel._footer.geometry().top() >= _armed_box(panel).geometry().bottom()

        others = [row.key for row in panel._shown_rows.values() if row.key in panel._runs]
        other = next(key for key in others if key != panel._armed)
        panel._arm(other)
        QApplication.processEvents()
        assert rows.indexOf(panel._footer) == rows.indexOf(_armed_box(panel)) + 1, (
            "die Knopfzeile wandert mit der scharfen Handlung"
        )
        assert panel._armed_title.isHidden(), "der Titel steht schon in der Kopfzeile darüber"
    finally:
        panel.deleteLater()
