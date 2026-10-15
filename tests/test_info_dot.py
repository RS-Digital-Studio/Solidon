"""Das Info-Zeichen der Merkmalzeilen ist ein Symbol, kein Buchstabe (FD-96).

Am Knopf stand ``tr("i")`` als Text, halbfett in neun Punkt — neben den
Strichsymbolen der Karte las er sich als Schriftzeichen. Jetzt trägt er das
Symbol aus dem eigenen Satz (``icons``); Kurzhilfe, zugänglicher Name und der
Sprung ins Handbuch bleiben.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QToolButton

from app.core.geom.mesh import read_mesh
from app.core.perceive import features
from app.ui.panels import FeaturePanel

MESHES = Path(__file__).parent / "data" / "meshes"


def test_the_info_dot_carries_a_symbol_and_no_letter(qt_app: QApplication) -> None:
    mesh = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")
    found = features.detect(mesh)
    identifier, hole = next((key, value) for key, value in found.items() if value.kind == "hole")
    panel = FeaturePanel()
    try:
        panel.show_feature(identifier, hole, features=found, mesh=mesh)
        dots = [
            widget
            for widget in panel.findChildren(QToolButton)
            if widget.objectName() == "infoDot" and widget.isVisibleTo(panel)
        ]
        assert dots, "ohne sichtbares Zeichen prüft dieser Test nichts"
        for dot in dots:
            assert dot.text() == "", f"Buchstabe statt Symbol: {dot.text()!r}"
            assert not dot.icon().isNull(), "ohne Symbol bliebe ein leerer Kreis"
            assert dot.toolTip(), "der Satz hinter dem Zeichen bleibt"
            assert dot.accessibleName(), "und der Name für den Bildschirmleser"
    finally:
        panel.deleteLater()
