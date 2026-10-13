"""Die gewählte Maßkartenlage bleibt erhalten; die Felder behalten ihre Bedienung."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QFocusEvent, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSlider,
    QSpinBox,
    QStyle,
    QStyleOptionButton,
    QTextEdit,
    QToolButton,
    QWidget,
)
from shiboken6 import delete, isValid

from app.ui.measure_card_drag import MeasureCardDrag
from app.ui.theme import apply_theme, current_theme
from tests import qt_roots

roots = qt_roots.roots


class _DeathWatch(QObject):
    """Die echte Sterbenachricht vor dem Produktfilter und spätere Zugriffe sehen."""

    def __init__(self, card):
        super().__init__()
        self.card = card
        self.events = []
        self.active_at_notice = {}

    def eventFilter(self, watched, event):  # noqa: N802 — Qt-Name
        if watched is self.card and event.type() in (
            QEvent.Type.Destroy,
            QEvent.Type.DeferredDelete,
        ):
            self.events.append(event.type())
            self.active_at_notice[event.type()] = QApplication.overrideCursor() is not None
        return False

    def record_move(self, *args):
        self.events.append("move")


class _TransportWatch(QObject):
    """Fenstertransport und tatsächlich weitergeleitete Widgetereignisse trennen."""

    def __init__(self):
        super().__init__()
        self.events = []

    def eventFilter(self, watched, event):  # noqa: N802 — Qt-Name
        if event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonRelease,
        ):
            self.events.append((watched, event.type(), event.buttons()))
        return False


@pytest.fixture
def card(qt_app, roots):
    """Echte Qt-Karte mit freiem Titel, Inhalt und absichtlich versetztem Bildraum."""
    before = current_theme()
    apply_theme(qt_app, "light")
    view = roots(QWidget())
    view.resize(1200, 900)
    box = QWidget(view)
    box.setGeometry(620, 100, 320, 300)
    title = QLabel("Bohrung ändern", box)
    title.setGeometry(15, 15, 280, 35)
    title.setObjectName("title")
    drag = MeasureCardDrag(box)
    room = QRect(40, 50, 1040, 780)
    drag.update_room(room)

    def redraw():
        placed = drag.placed_rect()
        if placed is not None:
            box.move(placed.topLeft())

    drag.positionChanged.connect(redraw)
    view.show()
    qt_app.processEvents()
    yield box, title, drag, room
    if isValid(view):
        view.close()
        view.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    apply_theme(qt_app, before)


def _mouse(
    widget, kind, global_pos, *, button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.LeftButton
):
    """Ein Qt-Mausereignis mit unverändertem Bildschirmbezug trotz Kartenbewegung."""
    event = QMouseEvent(
        kind,
        QPointF(widget.mapFromGlobal(global_pos)),
        QPointF(global_pos),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QCoreApplication.sendEvent(widget, event)


def _begin(widget, delta=None):
    if delta is None:
        delta = QPoint(-210, 170)
    start = widget.mapToGlobal(widget.rect().center())
    _mouse(widget, QEvent.Type.MouseButtonPress, start, button=Qt.MouseButton.LeftButton)
    _mouse(widget, QEvent.Type.MouseMove, start + delta)
    return start + delta


def _drop(widget, end):
    _mouse(
        widget,
        QEvent.Type.MouseButtonRelease,
        end,
        button=Qt.MouseButton.LeftButton,
        buttons=Qt.MouseButton.NoButton,
    )


@pytest.mark.parametrize("surface", ["title", "blank", "scroll_blank", "scroll_title"])
def test_title_and_free_surfaces_move_the_card(qt_app, card, surface):
    box, title, drag, room = card
    target = title
    if surface == "blank":
        target = QWidget(box)
        target.setGeometry(15, 60, 280, 80)
        target.show()
    elif surface in ("scroll_blank", "scroll_title"):
        scroll = QScrollArea(box)
        scroll.setGeometry(15, 60, 280, 160)
        content = QWidget()
        content.resize(240, 120)
        scroll.setWidget(content)
        scroll.show()
        target = content
        if surface == "scroll_title":
            target = QLabel("Bohrung ändern", content)
            target.setGeometry(10, 10, 200, 35)
            target.show()
    drag.update_room(room)
    before = box.pos()
    end = _begin(target)
    _drop(target, end)
    assert box.pos() != before
    assert drag.placed_rect() == box.geometry()
    assert room.contains(box.geometry())
    assert qt_app.overrideCursor() is None


def test_click_below_drag_threshold_does_not_choose_a_place(qt_app, card):
    box, title, drag, _ = card
    before = box.geometry()
    end = _begin(title, QPoint(1, 1))
    _drop(title, end)
    assert drag.placed_rect() is None
    assert box.geometry() == before
    assert qt_app.overrideCursor() is None


@pytest.mark.parametrize(
    "factory",
    [
        QLineEdit,
        QSpinBox,
        QDoubleSpinBox,
        QComboBox,
        QCheckBox,
        QPushButton,
        QToolButton,
        QSlider,
        QScrollBar,
        QTextEdit,
        QGroupBox,
    ],
)
def test_controls_and_their_children_do_not_drag(qt_app, card, factory):
    box, _, drag, room = card
    control = factory(box)
    control.setGeometry(15, 70, 250, 70)
    if isinstance(control, QGroupBox):
        control.setCheckable(True)
    control.show()
    drag.update_room(room)
    before = box.geometry()
    target = control
    if isinstance(control, (QSpinBox, QDoubleSpinBox)):
        target = control.lineEdit()
    end = _begin(target)
    _drop(target, end)
    assert drag.placed_rect() is None
    assert box.geometry() == before
    assert qt_app.overrideCursor() is None


@pytest.mark.parametrize("kind", ["buddy", "selection", "link"])
def test_labels_with_own_actions_do_not_drag(qt_app, card, kind):
    box, title, drag, room = card
    if kind == "buddy":
        title.setBuddy(QLineEdit(box))
    elif kind == "selection":
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    else:
        title.setText('<a href="https://example.invalid">Hilfe</a>')
    drag.update_room(room)
    end = _begin(title)
    _drop(title, end)
    assert drag.placed_rect() is None


def test_inputs_buttons_and_fold_keep_their_actions(qt_app, card):
    box, _, drag, room = card
    field = QLineEdit(box)
    field.setGeometry(10, 65, 120, 32)
    combo = QComboBox(box)
    combo.addItems(["Erstes", "Zweites"])
    combo.setGeometry(150, 65, 150, 32)
    check = QCheckBox("Haken", box)
    check.setGeometry(10, 100, 120, 32)
    fold = QToolButton(box)
    fold.setCheckable(True)
    fold.setText("Weitere Werte")
    fold.setGeometry(10, 135, 200, 32)
    accepted = []
    button = QPushButton("Übernehmen", box)
    button.clicked.connect(lambda: accepted.append(True))
    button.setGeometry(10, 175, 200, 32)
    for widget in (field, combo, check, fold, button):
        widget.show()
    drag.update_room(room)
    QTest.mouseClick(field, Qt.MouseButton.LeftButton)
    QTest.keyClicks(field, "12")
    combo.setFocus()
    QTest.keyClick(combo, Qt.Key.Key_Down)
    option = QStyleOptionButton()
    option.initFrom(check)
    option.text = check.text()
    indicator = check.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, check)
    QTest.mouseClick(check, Qt.MouseButton.LeftButton, pos=indicator.center())
    for widget in (fold, button):
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
    assert field.text() == "12"
    assert combo.currentIndex() == 1
    assert check.isChecked()
    assert fold.isChecked()
    assert accepted == [True]
    assert drag.placed_rect() is None


def test_size_changes_keep_place_and_temporary_clamping_is_reversible(qt_app, card):
    box, title, drag, room = card
    end = _begin(title)
    _drop(title, end)
    chosen = box.pos()
    for height in (500, 300, 600, 300):
        box.resize(box.width(), height)
        drag.update_room(room)
        rect = drag.placed_rect()
        assert room.contains(rect)
        if height == 300:
            assert rect.topLeft() == chosen
    for width in (440, 320):
        box.resize(width, box.height())
        drag.update_room(room)
        assert drag.placed_rect().topLeft() == chosen
    narrow = QRect(80, 100, 360, 400)
    drag.update_room(narrow)
    assert narrow.contains(drag.placed_rect())
    drag.update_room(room)
    assert drag.placed_rect().topLeft() == chosen


@pytest.mark.parametrize("ending", ["escape", "hide", "reset", "destroy", "focus"])
def test_interrupted_drag_returns_cursor_and_application_filter(qt_app, card, ending):
    box, title, drag, _ = card
    parent = box.parentWidget()
    before = box.pos()
    _begin(title)
    assert qt_app.overrideCursor() is not None
    if ending == "escape":
        QTest.keyClick(title, Qt.Key.Key_Escape)
    elif ending == "hide":
        box.hide()
    elif ending == "reset":
        drag.reset()
    elif ending == "focus":
        QCoreApplication.sendEvent(title, QFocusEvent(QEvent.Type.FocusOut))
    else:
        box.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert qt_app.overrideCursor() is None
    if ending != "destroy":
        assert drag.placed_rect() is None
        assert box.pos() == before
    # Ein späteres Ereignis außerhalb der Karte trifft keinen alten Zug.
    QTest.mouseMove(parent)


def test_replaced_group_and_new_order_do_not_keep_old_callbacks(qt_app, card):
    box, title, drag, room = card
    end = _begin(title)
    _drop(title, end)
    title.setParent(None)
    drag.reset()
    replacement = QLabel("Neue Bohrung", box)
    replacement.setGeometry(15, 15, 280, 35)
    replacement.show()
    drag.update_room(room)
    before = box.geometry()
    title.show()
    end = _begin(title)
    _drop(title, end)
    assert box.geometry() == before
    assert drag.placed_rect() is None
    title.close()
    title.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    end = _begin(replacement)
    _drop(replacement, end)
    assert drag.placed_rect() is not None


def test_direct_parent_destruction_never_moves_the_dying_card(qt_app, card, monkeypatch):
    box, title, _, _ = card
    _begin(title)
    trace = _DeathWatch(box)
    monkeypatch.setattr(box, "move", trace.record_move)
    # Beim synchronen Elternabbau erreicht Destroy den Python-Filter nicht;
    # QObject meldet das tatsächliche Lebensende über sein Signal.
    box.destroyed.connect(lambda: trace.events.append("destroyed"))
    qt_app.installEventFilter(trace)
    try:
        delete(box.parentWidget())
    finally:
        qt_app.removeEventFilter(trace)
    assert "destroyed" in trace.events
    assert not isValid(box)
    assert "move" not in trace.events[trace.events.index("destroyed") :]
    assert qt_app.overrideCursor() is None


def test_deferred_delete_ends_an_active_drag_without_touching_the_dying_card(
    qt_app, card, monkeypatch
):
    box, title, _, _ = card
    _begin(title)
    assert qt_app.overrideCursor() is not None
    trace = _DeathWatch(box)
    monkeypatch.setattr(box, "move", trace.record_move)
    # Zuletzt installiert, sieht der Beobachter dieselbe Nachricht zuerst.
    qt_app.installEventFilter(trace)
    try:
        box.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    finally:
        qt_app.removeEventFilter(trace)
    assert QEvent.Type.DeferredDelete in trace.events
    assert trace.active_at_notice[QEvent.Type.DeferredDelete]
    assert "move" not in trace.events[trace.events.index(QEvent.Type.DeferredDelete) :]
    assert qt_app.overrideCursor() is None


def test_window_deactivation_restores_the_living_card(qt_app, card):
    box, title, drag, _ = card
    before = box.pos()
    _begin(title)
    QCoreApplication.sendEvent(box.window(), QEvent(QEvent.Type.WindowDeactivate))
    assert box.pos() == before
    assert drag.placed_rect() is None
    assert qt_app.overrideCursor() is None


@pytest.mark.parametrize(
    "growth",
    [(308, 12, 1311, 895), (308, 12, 1124, 1050), (12, 12, 1420, 895), (308, 0, 1124, 907)],
    ids=["width", "height", "left", "top"],
)
def test_late_room_growth_keeps_the_dropped_anchor(qt_app, card, growth):
    """Der EN-Flow legt richtig ab; erst die spätere freie Fläche wächst."""
    box, title, drag, _ = card
    box.resize(321, 237)
    room = QRect(308, 12, 1124, 895)
    target = QPoint(960, 90)
    drag.update_room(room)
    end = _begin(title, target - box.pos())
    _drop(title, end)
    assert box.pos() == target

    larger = QRect(*growth)
    drag.update_room(larger)
    assert drag.placed_rect().topLeft() == target

    smaller = QRect(room.left(), room.top(), 900, 895)
    drag.update_room(smaller)
    assert smaller.contains(drag.placed_rect())
    assert drag.placed_rect().left() < target.x()
    drag.update_room(larger)
    assert drag.placed_rect().topLeft() == target


@pytest.mark.parametrize("surface", ["title", "blank"])
def test_window_transport_releases_the_card_before_hovering_another_child(qt_app, card, surface):
    """Nach dem echten Fenster-Release gehört der nächste freie Zug dem Feldkind."""
    box, title, drag, room = card
    combo = QComboBox(box)
    combo.setGeometry(20, 90, 240, 32)
    combo.addItems(["Erster Wert", "Zweiter Wert"])
    combo.setMouseTracking(True)
    combo.show()
    drag.update_room(room)
    view = box.window()
    view.activateWindow()
    qt_app.processEvents()
    handle = view.windowHandle()
    assert handle is not None
    if surface == "title":
        start = title.mapToGlobal(title.rect().center())
    else:
        start = box.mapToGlobal(box.rect().bottomRight() - QPoint(10, 10))
    target = box.pos() + QPoint(-210, 170)
    end = start + target - box.pos()
    trace = _TransportWatch()
    qt_app.installEventFilter(trace)
    held = False
    try:
        QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=handle.mapFromGlobal(start))
        held = True
        # Der Produktfilter wird beim Druck global; der Beobachter liest zuerst.
        qt_app.removeEventFilter(trace)
        qt_app.installEventFilter(trace)
        midway = start + QPoint(round((end.x() - start.x()) / 2), round((end.y() - start.y()) / 2))
        for point in (midway, end):
            QTest.mouseMove(handle, handle.mapFromGlobal(point))
            qt_app.processEvents()
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=handle.mapFromGlobal(end))
        held = False
        qt_app.processEvents()
        after_release = len(trace.events)
        hover = combo.mapToGlobal(combo.rect().center())
        QTest.mouseMove(handle, handle.mapFromGlobal(hover))
        qt_app.processEvents()
        assert box.pos() == target
        detail = [(type(w).__name__, kind.name, buttons.value) for w, kind, buttons in trace.events]
        assert (
            combo,
            QEvent.Type.MouseMove,
            Qt.MouseButton.NoButton,
        ) in trace.events[after_release:], detail
        widgets = [event for event in trace.events[:after_release] if isinstance(event[0], QWidget)]
        assert any(kind == QEvent.Type.MouseButtonPress for _, kind, _ in widgets), detail
        assert any(
            kind == QEvent.Type.MouseMove and buttons & Qt.MouseButton.LeftButton
            for _, kind, buttons in widgets
        ), detail
        assert any(
            kind == QEvent.Type.MouseButtonRelease and not buttons for _, kind, buttons in widgets
        ), detail
        assert qt_app.overrideCursor() is None
    finally:
        if held:
            QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=handle.mapFromGlobal(end))
        qt_app.removeEventFilter(trace)
