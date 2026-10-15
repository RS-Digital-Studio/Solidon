"""Im Merkmalfenster wartet *Übernehmen* auf die erste Änderung (FD-99 mit FD-31).

An einer Bohrung stand *Übernehmen* für „Bohrung ändern“ orange da, bevor
jemand ein Maß angefasst hatte, ebenso an einer Fläche für „Fläche
versetzen“ bei 0 mm; der Klick legte nichts an oder wurde abgelehnt. Die
Maßgruppe im Bild wartet seit F1 auf die erste Änderung und nennt das erste
Feld — dieselbe Regel und derselbe Satz gelten hier (``first_change``).
Eine Handlung, deren Vorgabe selbst etwas tut, bleibt sofort übernehmbar.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.core.geom.mesh import read_mesh
from app.core.perceive import features
from app.ui.first_change import first_change_sentence
from app.ui.panels import FeaturePanel

MESHES = Path(__file__).parent / "data" / "meshes"


def _panel(kind: str) -> FeaturePanel:
    mesh = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")
    found = features.detect(mesh)
    identifier, chosen = next((key, value) for key, value in found.items() if value.kind == kind)
    panel = FeaturePanel()
    panel.show_feature(identifier, chosen, features=found, mesh=mesh)
    panel.resize(420, 900)
    panel.show()
    QApplication.processEvents()
    return panel


def _arm(panel: FeaturePanel, op: str) -> object:
    row = next(row for row in panel._shown_rows.values() if row.op == op)
    panel._arm(row.key)
    QApplication.processEvents()
    return row


def test_resizing_a_hole_waits_for_the_first_change(qt_app: QApplication) -> None:
    panel = _panel("hole")
    try:
        row = _arm(panel, "resize_hole")
        apply = panel._apply
        assert not apply.isEnabled(), "ohne Änderung gibt es nichts zu übernehmen"
        said = first_change_sentence(row.widgets.values(), panel)
        assert said and apply.toolTip() == said and apply.accessibleDescription() == said
        assert not panel.can_accept()

        diameter = row.widgets["diameter"]
        start = diameter.value()
        diameter.setValue(start + 1.0)
        QApplication.processEvents()
        assert apply.isEnabled(), "die erste Änderung gibt den Knopf frei"

        diameter.setValue(start)
        QApplication.processEvents()
        assert not apply.isEnabled(), "zurück auf den heutigen Stand: wieder nichts zu tun"
    finally:
        panel.deleteLater()


def test_the_scope_box_is_a_change_of_its_own(qt_app: QApplication) -> None:
    panel = _panel("hole")
    try:
        _arm(panel, "resize_hole")
        if panel._every.isHidden():
            return  # ohne gleichartige Geschwister kein Haken
        panel._every.toggle()
        QApplication.processEvents()
        assert panel._apply.isEnabled(), "der Haken ändert den Umfang, keinen Wert"
    finally:
        panel.deleteLater()


def test_an_offer_that_does_something_by_itself_stays_ready(qt_app: QApplication) -> None:
    panel = _panel("hole")
    try:
        _arm(panel, "rotate_feature")
        assert panel._apply.isEnabled(), "Drehen um 90° tut schon etwas"
    finally:
        panel.deleteLater()


def test_pushing_a_face_by_nothing_waits_too(qt_app: QApplication) -> None:
    panel = _panel("face")
    try:
        row = _arm(panel, "push_face")
        assert not panel._apply.isEnabled(), "0 mm versetzt nichts"
        row.widgets["distance"].setValue(1.0)
        QApplication.processEvents()
        assert panel._apply.isEnabled()
    finally:
        panel.deleteLater()
