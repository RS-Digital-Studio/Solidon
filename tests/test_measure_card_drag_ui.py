"""Die gewählte Maßkartenlage bleibt erhalten; die Felder behalten ihre Bedienung."""

import sys

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QRect, Qt
from PySide6.QtGui import QCursor, QFocusEvent
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

from app.ui import app_events
from app.ui.cursors import cursor
from app.ui.measure_card_drag import MeasureCardDrag
from app.ui.theme import apply_theme, current_theme
from tests import qt_roots
from tests.ui_helpers import begin_card_drag, end_card_drag, send_mouse_event

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
            self.active_at_notice[event.type()] = self.card.findChild(
                QLabel, "title"
            ).testAttribute(Qt.WidgetAttribute.WA_SetCursor)
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
    end = begin_card_drag(target)
    end_card_drag(target, end)
    assert box.pos() != before
    assert drag.placed_rect() == box.geometry()
    assert room.contains(box.geometry())
    assert qt_app.overrideCursor() is None


def test_click_below_drag_threshold_does_not_choose_a_place(qt_app, card):
    box, title, drag, _ = card
    before = box.geometry()
    end = begin_card_drag(title, QPoint(1, 1))
    end_card_drag(title, end)
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
    end = begin_card_drag(target)
    end_card_drag(target, end)
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
    end = begin_card_drag(title)
    end_card_drag(title, end)
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
    end = begin_card_drag(title)
    end_card_drag(title, end)
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
    before_cursor = QCursor(title.cursor())
    before_owned = title.testAttribute(Qt.WidgetAttribute.WA_SetCursor)
    begin_card_drag(title)
    assert title.testAttribute(Qt.WidgetAttribute.WA_SetCursor)
    assert title.cursor().shape() == cursor("move", title).shape()
    assert title.cursor().pixmap().toImage() == cursor("move", title).pixmap().toImage()
    assert app_events.application_events().listening(drag)
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
        assert title.cursor().shape() == before_cursor.shape()
        assert title.cursor().pixmap().toImage() == before_cursor.pixmap().toImage()
        assert title.testAttribute(Qt.WidgetAttribute.WA_SetCursor) is before_owned
    assert not app_events.application_events().listening(drag)
    # Ein späteres Ereignis außerhalb der Karte trifft keinen alten Zug.
    QTest.mouseMove(parent)


def test_replaced_group_and_new_order_do_not_keep_old_callbacks(qt_app, card):
    box, title, drag, room = card
    end = begin_card_drag(title)
    end_card_drag(title, end)
    title.setParent(None)
    drag.reset()
    replacement = QLabel("Neue Bohrung", box)
    replacement.setGeometry(15, 15, 280, 35)
    replacement.show()
    drag.update_room(room)
    before = box.geometry()
    title.show()
    end = begin_card_drag(title)
    end_card_drag(title, end)
    assert box.geometry() == before
    assert drag.placed_rect() is None
    title.close()
    title.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    end = begin_card_drag(replacement)
    end_card_drag(replacement, end)
    assert drag.placed_rect() is not None


def test_direct_parent_destruction_never_moves_the_dying_card(qt_app, card, monkeypatch):
    box, title, _drag, _ = card
    begin_card_drag(title)
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
    box, title, drag, _ = card
    begin_card_drag(title)
    assert title.testAttribute(Qt.WidgetAttribute.WA_SetCursor)
    assert title.cursor().shape() == cursor("move", title).shape()
    assert title.cursor().pixmap().toImage() == cursor("move", title).pixmap().toImage()
    assert app_events.application_events().listening(drag)
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
    before_cursor = QCursor(title.cursor())
    before_owned = title.testAttribute(Qt.WidgetAttribute.WA_SetCursor)
    begin_card_drag(title)
    QCoreApplication.sendEvent(box.window(), QEvent(QEvent.Type.WindowDeactivate))
    assert box.pos() == before
    assert title.cursor().shape() == before_cursor.shape()
    assert title.cursor().pixmap().toImage() == before_cursor.pixmap().toImage()
    assert title.testAttribute(Qt.WidgetAttribute.WA_SetCursor) is before_owned
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
    end = begin_card_drag(title, target - box.pos())
    end_card_drag(title, end)
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
        # Der Beobachter sieht den Fenstertransport vor dem gemeinsamen Verteiler.
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


@pytest.mark.parametrize("owned", [False, True], ids=["geerbt", "eigener"])
def test_drag_restores_the_receivers_own_or_inherited_cursor(qt_app, card, owned):
    """Ein geerbter Zeiger bleibt nach dem Zug geerbt, ein eigener bleibt derselbe."""
    box, title, drag, _ = card
    box.setCursor(Qt.CursorShape.IBeamCursor)
    if owned:
        title.setCursor(Qt.CursorShape.CrossCursor)
    expected = title.cursor().shape()
    end = begin_card_drag(title)
    assert title.cursor().shape() == cursor("move", title).shape()
    assert title.cursor().pixmap().toImage() == cursor("move", title).pixmap().toImage()
    assert qt_app.overrideCursor() is None
    end_card_drag(title, end)
    assert title.cursor().shape() == expected
    assert title.testAttribute(Qt.WidgetAttribute.WA_SetCursor) is owned
    assert not app_events.application_events().listening(drag)
    box.setCursor(Qt.CursorShape.WaitCursor)
    if not owned:
        assert title.cursor().shape() == Qt.CursorShape.WaitCursor


@pytest.mark.parametrize("surface", ["title", "blank"])
def test_window_transport_keeps_the_move_cursor_outside_the_card(qt_app, card, surface):
    """Der wirkliche Druckempfänger behält den Zug bis zum Release außerhalb der Karte."""
    box, title, drag, room = card
    target = title if surface == "title" else box
    view = box.window()
    view.activateWindow()
    qt_app.processEvents()
    handle = view.windowHandle()
    start = target.mapToGlobal(target.rect().center())
    if target is box:
        start = box.mapToGlobal(box.rect().bottomRight() - QPoint(10, 10))
    outside = view.mapToGlobal(QPoint(view.width() - 5, view.height() - 5))
    QTest.mouseMove(handle, handle.mapFromGlobal(start))
    QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=handle.mapFromGlobal(start))
    changes = []
    drag.positionChanged.connect(lambda: changes.append(box.pos()))
    try:
        QTest.mouseMove(handle, handle.mapFromGlobal(outside))
        qt_app.processEvents()
        assert not box.rect().contains(box.mapFromGlobal(outside))
        assert len(changes) == 1, "Eine Widgetzustellung ergibt genau eine Bewegung"
        expected = cursor("move", target).pixmap().toImage()
        assert target.cursor().shape() == cursor("move", target).shape()
        assert handle.cursor().shape() == cursor("move", target).shape()
        assert target.cursor().pixmap().toImage() == expected
        assert handle.cursor().pixmap().toImage() == expected
        assert qt_app.overrideCursor() is None
        assert app_events.application_events().listening(drag)
    finally:
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=handle.mapFromGlobal(outside))
    assert room.contains(box.geometry())
    assert drag.placed_rect() == box.geometry()
    assert not app_events.application_events().listening(drag)
    assert not target.testAttribute(Qt.WidgetAttribute.WA_SetCursor)


@pytest.mark.parametrize("timing", ["before", "during"])
@pytest.mark.parametrize("ending", ["release", "reset", "error"])
def test_foreign_override_survives_drag_and_its_error_path(
    qt_app, card, monkeypatch, timing, ending
):
    """Auch ein nach Zugbeginn gesetzter fremder Override bleibt an seinem Platz."""
    box, title, drag, _ = card
    assert qt_app.overrideCursor() is None
    active = False
    errors = []
    try:
        if timing == "before":
            QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
            active = True
        end = begin_card_drag(title)
        if timing == "during":
            QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
            active = True
        assert qt_app.overrideCursor().shape() == Qt.CursorShape.CrossCursor
        if ending == "error":
            with monkeypatch.context() as patch:
                patch.setattr(sys, "excepthook", lambda _kind, error, _trace: errors.append(error))

                def fail_move(*_args):
                    raise RuntimeError("Erzwungener Bewegungsfehler")

                patch.setattr(box, "move", fail_move)
                try:
                    send_mouse_event(title, QEvent.Type.MouseMove, end + QPoint(10, 10))
                except RuntimeError as error:
                    errors.append(error)
            assert len(errors) == 1 and isinstance(errors[0], RuntimeError)
            assert "Erzwungener Bewegungsfehler" in str(errors[0])
        elif ending == "reset":
            drag.reset()
        else:
            end_card_drag(title, end)
        assert qt_app.overrideCursor().shape() == Qt.CursorShape.CrossCursor
        assert not title.testAttribute(Qt.WidgetAttribute.WA_SetCursor)
        assert not app_events.application_events().listening(drag)
        QApplication.restoreOverrideCursor()
        active = False
        assert qt_app.overrideCursor() is None
    finally:
        drag.reset()
        if active:
            QApplication.restoreOverrideCursor()
        # Ein ursprünglicher fehlerhafter Produkt-Override darf den Rotlauf
        # nicht in den nächsten Fall verschleppen; beide Einträge gehören diesem Test.
        while qt_app.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()


@pytest.mark.parametrize("ending", ["delete", "reparent"])
def test_lost_press_receiver_ends_the_registration(qt_app, card, ending):
    """Ein abgelegter oder direkt gelöschter Titel hinterlässt keinen laufenden Zug."""
    box, title, drag, _ = card
    begin_card_drag(title)
    assert app_events.application_events().listening(drag)
    if ending == "delete":
        delete(title)
    else:
        title.setParent(box.parentWidget())
    assert not app_events.application_events().listening(drag)
    assert qt_app.overrideCursor() is None
    if isValid(title):
        assert not title.testAttribute(Qt.WidgetAttribute.WA_SetCursor)
    before = box.geometry()
    QTest.mouseMove(box.parentWidget())
    assert box.geometry() == before


@pytest.mark.parametrize("failure", ["bounds", "move"])
def test_first_move_failure_releases_cursor_and_listener(qt_app, card, monkeypatch, failure):
    """Eine Ausnahme auch vor dem ersten Bewegungszustand gibt alle Ressourcen zurück."""
    box, title, drag, _ = card
    title.setCursor(Qt.CursorShape.CrossCursor)
    errors = []
    try:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "excepthook", lambda _kind, error, _trace: errors.append(error))

            def fail(*_args):
                raise RuntimeError("Erzwungener erster Zugfehler")

            patch.setattr(
                drag if failure == "bounds" else box,
                "_bounded" if failure == "bounds" else "move",
                fail,
            )
            try:
                begin_card_drag(title)
            except RuntimeError as error:
                errors.append(error)
        assert len(errors) == 1 and isinstance(errors[0], RuntimeError)
        assert "Erzwungener erster Zugfehler" in str(errors[0])
        assert not app_events.application_events().listening(drag)
        assert title.cursor().shape() == Qt.CursorShape.CrossCursor
        assert title.testAttribute(Qt.WidgetAttribute.WA_SetCursor)
        assert qt_app.overrideCursor() is None
        assert drag.placed_rect() is None
    finally:
        drag.reset()
        # Nur beim erwarteten Originalrot kann dessen ungesicherter Override übrig sein.
        while qt_app.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()


@pytest.mark.parametrize("ending", ["direct", "deferred"])
def test_helper_destruction_restores_the_living_receivers_cursor(qt_app, card, ending):
    """Auch ohne Kartenabbau endet der Helfer mit zurückgegebenem Widgetcursor."""
    box, title, drag, _ = card
    title.setCursor(Qt.CursorShape.CrossCursor)
    begin_card_drag(title)
    assert app_events.application_events().listening(drag)
    assert title.cursor().shape() == cursor("move", title).shape()
    assert title.cursor().pixmap().toImage() == cursor("move", title).pixmap().toImage()
    before = box.geometry()
    if ending == "direct":
        delete(drag)
    else:
        drag.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(drag)
    assert isValid(box) and isValid(title)
    assert title.cursor().shape() == Qt.CursorShape.CrossCursor
    assert title.testAttribute(Qt.WidgetAttribute.WA_SetCursor)
    assert qt_app.overrideCursor() is None
    assert not app_events.application_events().listening(drag)
    QTest.mouseMove(box.parentWidget())
    assert box.geometry() == before
