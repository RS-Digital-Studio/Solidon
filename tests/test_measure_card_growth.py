"""Eine wachsende Maßgruppe bleibt stehen und rückt nur so weit, wie der Platz verlangt (FD-87)."""

import pytest
from PySide6.QtCore import QAbstractAnimation, QPoint, QPropertyAnimation, QRect
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

from app.ui import motion
from app.ui.labels import LengthSpin
from app.ui.panels import FIELD_PROPERTY
from tests.test_measure_group_layout import language as language
from tests.test_measure_group_layout import selected_hole as selected_hole
from tests.ui_helpers import placement_layout, settle_measure_layout, wait_until
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


def _settled(window, qt_app):
    wait_until(qt_app, lambda: not window.overlay._moves and window.overlay._pending is None)
    settle_measure_layout(qt_app)


def _refuse_the_diameter(window, flow, qt_app) -> None:
    """0,1 mm liegt unter der Untergrenze: Unter dem Feld steht die Ablehnung."""
    field = next(
        widget
        for widget in flow._measure_group.findChildren(LengthSpin)
        if widget.property(FIELD_PROPERTY) == "diameter"
    )
    field.lineEdit().setFocus()
    field.lineEdit().selectAll()
    QTest.keyClicks(field.lineEdit(), "0,1")
    assert window.session.wait_for_idle(30_000)
    settle_measure_layout(qt_app)


def _the_least_shift(before: QRect, size, room: QRect) -> QRect:
    """Die alte Ecke, nur so weit in den Raum gerückt, wie die neue Größe verlangt."""
    left = max(room.left(), min(before.left(), room.right() - size.width() + 1))
    top = max(room.top(), min(before.top(), room.bottom() - size.height() + 1))
    return QRect(left, top, size.width(), size.height())


@pytest.mark.parametrize("height", [150, 250])
def test_a_growing_card_keeps_its_place_and_moves_only_as_far_as_the_room_asks(
    qt_app, monkeypatch, height
):
    """Die Karte steht rechts neben dem Setzpunkt und wird um 250 Punkte höher.

    Bis hierher verlor sie mit der neuen Größe ihren Platz und sprang an den
    nächsten freien beim Setzpunkt: 125 Punkte hoch, bei der höheren Karte
    dazu 281 nach links. Jetzt bleibt die Ecke, und unten am Raum rückt sie
    genau um den Überstand.
    """
    flow, session, viewport, dialog = placement_layout(qt_app, (1920, 1080), 1.0, "bottom")
    try:
        monkeypatch.setattr(dialog, "values_stand_elsewhere", True)
        group = QWidget(viewport)
        layout = QFormLayout(group)
        title = QLabel("Bohrung ändern", group)
        title.setMinimumSize(300, height)
        layout.addRow(title)
        flow.set_measure_fields(
            group, editors=(), interpret=lambda: True, refresh=lambda _values: None
        )
        viewport.renderer.world_to_display = lambda point: (
            960 + point[0] * 10,
            540 + point[1] * 10,
            0.5,
        )
        flow.redraw()
        flow.redraw()
        card = flow._measure_box
        assert flow._measure_drag.placed_rect() is None, "Voraussetzung: der Fluss wählt"
        before = card.geometry()
        title.setMinimumSize(300, height + 250)
        flow.redraw()
        after = card.geometry()
        assert after.height() > before.height(), "Voraussetzung: die Karte wächst"
        assert after == _the_least_shift(before, after.size(), flow._measure_drag._room), (
            before,
            after,
        )
        flow.redraw()
        assert card.geometry() == after, "und sie bleibt dort"
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_the_card_glides_to_its_new_place(selected_hole, qt_app, monkeypatch):
    """Der Wechsel geht mit dem Übergang aus ``motion``, nicht als Sprung.

    Hier steht die Karte unter Setzpunkt und Griff am unteren Rand; höher
    passt sie dort nicht mehr hin und muss über beide — sie gleitet dorthin.
    """
    from app.ui import placement_flow

    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    _settled(window, qt_app)
    card = flow._measure_box
    before = card.geometry()
    monkeypatch.setattr(motion, "animations_enabled", lambda: True)
    started: list[tuple[QPoint, QPoint]] = []
    original = motion.glide

    def watched(widget, point, *, smooth, duration=motion.SHORT_MS):
        if widget is card and smooth:
            started.append((QPoint(widget.pos()), QPoint(point)))
        original(widget, point, smooth=smooth, duration=duration)

    monkeypatch.setattr(placement_flow, "glide", watched)
    _refuse_the_diameter(window, flow, qt_app)
    assert card.height() > before.height(), "Voraussetzung: die Karte wächst"
    assert started, "die Karte sprang ohne Übergang"
    origin, target = started[0][0], started[-1][1]
    assert origin == before.topLeft() and target != origin, started
    wait_until(qt_app, lambda: card.pos() == target)
    flow.redraw()
    assert card.pos() == target, "die nächste Runde hält das Ziel"


def test_glide_moves_once_keeps_its_target_and_yields_to_a_jump(qt_app, monkeypatch):
    """Eine Gleitbewegung je Widget: dasselbe Ziel läuft weiter, ein Sprung hält sie an."""
    widget = QWidget()
    try:
        widget.setGeometry(10, 10, 50, 50)
        widget.show()
        monkeypatch.setattr(motion, "animations_enabled", lambda: True)
        motion.glide(widget, QPoint(200, 10), smooth=True)
        glides = widget.findChildren(QPropertyAnimation)
        assert len(glides) == 1 and glides[0].endValue() == QPoint(200, 10)
        assert glides[0].duration() <= motion.SHORT_MS
        motion.glide(widget, QPoint(200, 10), smooth=False)
        assert glides[0].state() == QAbstractAnimation.State.Running, "dasselbe Ziel läuft weiter"
        motion.glide(widget, QPoint(30, 40), smooth=False)
        assert widget.pos() == QPoint(30, 40), "ein anderes Ziel ohne Übergang springt"
        qt_app.processEvents()
        assert not [
            glide for glide in widget.findChildren(QPropertyAnimation) if glide.objectName()
        ]
        monkeypatch.setattr(motion, "animations_enabled", lambda: False)
        motion.glide(widget, QPoint(90, 90), smooth=True)
        assert widget.pos() == QPoint(90, 90), "ohne Bewegung steht es sofort"
    finally:
        widget.deleteLater()
