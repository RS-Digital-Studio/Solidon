"""Reiter mit eigener Fensterhülle und einem verlustfreien Rückweg (§2.5).

Der Platz im Reiterstapel bleibt bestehen. Nur sein Inhalt zieht um; damit
bleiben Kennung, Sichtbarkeit, Meldungen und Auswahl der Anwendung dieselben.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.ui.leash import stop_watching_the_dying
from app.ui.style import NORMAL, fit_dialog_to_screen


def reachable_geometry(saved: object, rooms: list[QRect]) -> QRect | None:
    """Ein gespeichertes Fenster vollständig auf einem vorhandenen Bildschirm."""
    if not isinstance(saved, list) or len(saved) != 4:
        return None
    if any(type(value) is not int or abs(value) > 100_000 for value in saved):
        return None
    rect = QRect(*saved)
    if rect.width() < 1 or rect.height() < 1 or not rooms:
        return None
    room = max(
        rooms, key=lambda area: area.intersected(rect).width() * area.intersected(rect).height()
    )
    width, height = min(rect.width(), room.width()), min(rect.height(), room.height())
    return QRect(
        max(room.left(), min(rect.left(), room.right() - width + 1)),
        max(room.top(), min(rect.top(), room.bottom() - height + 1)),
        width,
        height,
    )


class _PanelWindow(QMainWindow):
    """Ein eigener OS-Rahmen; Schließen bedeutet zurück in den Reiterstapel."""

    def __init__(self, owner: DetachableTabs, page: QWidget, title: str) -> None:
        super().__init__(owner.window(), Qt.WindowType.Window)
        self.owner = owner
        self.page = page
        self.setWindowTitle(title)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        body = QWidget(self)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        back = QPushButton(tr("Zurück in Solidon"), body)
        back.clicked.connect(self._return)
        layout.addWidget(back)
        layout.addWidget(page, 1)
        self.setCentralWidget(body)
        self.resize(max(page.sizeHint().width(), 400), max(page.sizeHint().height(), 300))
        # Dieselben Aktionen arbeiten weiterhin auf derselben Sitzung. Keine
        # Kopie mit eigener Aktivierung oder abweichendem Sperrzustand.
        for action in owner.window().findChildren(QAction):
            if action.shortcutContext() == Qt.ShortcutContext.WindowShortcut:
                self.addAction(action)
        self._ready = True

    def _return(self) -> None:
        self.owner.return_page(self.page)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt-Name
        self._return()
        event.accept()

    def event(self, event: QEvent) -> bool:
        result = super().event(event)
        if getattr(self, "_ready", False) and event.type() in (
            QEvent.Type.Move,
            QEvent.Type.Resize,
        ):
            self.owner.remember_layout()
        return result


class DetachableTabs(QTabWidget):
    """Umordnen und Herausziehen bei stabiler Zuordnung der echten Inhalte."""

    layoutChanged = Signal(dict)
    pageVisibilityChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pages: dict[QWidget, QWidget] = {}
        self._windows: dict[QWidget, _PanelWindow] = {}
        self._pending: dict[QWidget, QRect] = {}
        self._keys: dict[QWidget, str] = {}
        self._pressed: QWidget | None = None
        self._press_at = QPoint()
        self._closing = False
        self._restoring = False
        self._save = QTimer(self)
        self._save.setSingleShot(True)
        self._save.setInterval(150)
        self._save.timeout.connect(self._emit_layout)
        self.currentChanged.connect(self._selected)
        self._prepare_bar(self.tabBar())
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.screenRemoved.connect(self._screens_changed)

    def _prepare_bar(self, bar: QTabBar) -> None:
        bar.setMovable(True)
        bar.installEventFilter(self)
        bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        bar.customContextMenuRequested.connect(self._menu)
        bar.tabMoved.connect(self.remember_layout)

    def setTabBar(self, bar: QTabBar) -> None:  # noqa: N802 - Qt-Name
        super().setTabBar(bar)
        self._prepare_bar(bar)

    def addTab(self, widget: QWidget, *args: Any) -> int:  # noqa: N802 - Qt-Name
        return self.insertTab(self.count(), widget, *args)

    def insertTab(self, index: int, widget: QWidget, *args: Any) -> int:  # noqa: N802 - Qt-Name
        holder = QWidget(self)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(widget)
        self._pages[holder] = widget
        return super().insertTab(index, holder, *args)

    def widget(self, index: int) -> QWidget | None:
        holder = super().widget(index)
        return self._pages.get(holder, holder) if holder is not None else None

    def currentWidget(self) -> QWidget | None:  # type: ignore[override]  # noqa: N802 - Qt erlaubt None
        return self.widget(self.currentIndex())

    def indexOf(self, widget: QWidget) -> int:  # noqa: N802 - Qt-Name
        holder = next((slot for slot, page in self._pages.items() if page is widget), widget)
        return super().indexOf(holder)

    def setCurrentWidget(self, widget: QWidget) -> None:  # noqa: N802 - Qt-Name
        index = self.indexOf(widget)
        self.setCurrentIndex(index)
        self._selected(index)

    def setTabVisible(self, index: int, visible: bool) -> None:  # noqa: N802 - Qt-Name
        super().setTabVisible(index, visible)
        page = self.widget(index)
        window = self._windows.get(page) if page is not None else None
        if window is not None:
            window.setVisible(visible)
        elif visible and page in self._pending:
            rect = self._pending.pop(page)
            assert page is not None
            self.detach_page(page)
            self._place_window(self._windows[page], rect)
        self.pageVisibilityChanged.emit(index)

    def is_detached(self, page: QWidget) -> bool:
        """Der Inhalt hat eine eigene Fensterhülle, auch wenn er gerade verborgen ist."""
        return page in self._windows

    def page_is_visible(self, page: QWidget) -> bool:
        """Ein herausgezogener Inhalt bleibt sichtbar neben anderen Reitern."""
        window = self._windows.get(page)
        return window.isVisible() if window is not None else self.currentWidget() is page

    def _selected(self, index: int) -> None:
        page = self.widget(index)
        window = self._windows.get(page) if page is not None else None
        if window is not None and self.isTabVisible(index):
            window.showNormal()
            window.raise_()
            window.activateWindow()

    def detach_page(self, page: QWidget, at: QPoint | None = None) -> None:
        index = self.indexOf(page)
        if index < 0 or page in self._windows or not self.isTabVisible(index):
            return
        holder = super().widget(index)
        assert holder is not None
        window = _PanelWindow(self, page, self.tabText(index))
        self._windows[page] = window
        placeholder = QWidget(holder)
        layout = QVBoxLayout(placeholder)
        label = QLabel(tr("Dieser Reiter ist in einem eigenen Fenster geöffnet."), placeholder)
        label.setWordWrap(True)
        layout.addWidget(label)
        show = QPushButton(tr("Fenster zeigen"), placeholder)
        show.clicked.connect(window.showNormal)
        show.clicked.connect(window.raise_)
        show.clicked.connect(window.activateWindow)
        layout.addWidget(show)
        back = QPushButton(tr("Zurück in Solidon"), placeholder)
        back.clicked.connect(window._return)
        layout.addWidget(back)
        holder_layout = holder.layout()
        assert holder_layout is not None
        holder_layout.addWidget(placeholder)
        window.show()
        if at is not None:
            window.move(at)
        fit_dialog_to_screen(window)
        window.raise_()
        window.activateWindow()
        page.show()
        self.updateGeometry()
        self.pageVisibilityChanged.emit(index)
        self.remember_layout()

    def return_page(self, page: QWidget) -> None:
        window = self._windows.pop(page, None)
        if window is None:
            return
        holder = super().widget(self.indexOf(page))
        assert holder is not None
        layout = holder.layout()
        assert layout is not None
        while layout.count():
            item = layout.takeAt(0)
            assert item is not None
            placeholder = item.widget()
            if placeholder is not None:
                placeholder.hide()
                placeholder.deleteLater()
        layout.addWidget(page)
        page.show()
        window.hide()
        window.deleteLater()
        self.updateGeometry()
        self.pageVisibilityChanged.emit(self.indexOf(page))
        self.remember_layout()

    def configure_pages(self, pages: Mapping[str, QWidget], saved: object) -> None:
        """Stabile Kennungen und gespeicherten Stand nach dem vollständigen Aufbau setzen."""
        self._keys = {page: key for key, page in pages.items()}
        if not isinstance(saved, dict):
            return
        self._restoring = True
        order = saved.get("order", [])
        if isinstance(order, list):
            seen: set[str] = set()
            for key in order:
                if isinstance(key, str) and key in pages and key not in seen:
                    self.tabBar().moveTab(self.indexOf(pages[key]), len(seen))
                    seen.add(key)
        windows = saved.get("windows", {})
        if isinstance(windows, dict):
            rooms = [screen.availableGeometry() for screen in QApplication.screens()]
            for key, geometry in windows.items():
                if key not in pages:
                    continue
                rect = reachable_geometry(geometry, rooms)
                page = pages[key]
                if rect is not None:
                    if self.isTabVisible(self.indexOf(page)):
                        self.detach_page(page)
                        self._place_window(self._windows[page], rect)
                    else:
                        self._pending[page] = rect
        self._restoring = False
        self._save.stop()

    def layout_state(self) -> dict[str, object]:
        order = [
            self._keys[page]
            for index in range(self.count())
            if (page := self.widget(index)) in self._keys
        ]
        windows = {
            self._keys[page]: [rect.x(), rect.y(), rect.width(), rect.height()]
            for page, rect in self._pending.items()
            if page in self._keys
        }
        windows.update(
            {
                self._keys[page]: [window.x(), window.y(), window.width(), window.height()]
                for page, window in self._windows.items()
                if page in self._keys
            }
        )
        return {"order": order, "windows": windows}

    def remember_layout(self, *_args: object) -> None:
        if self._keys and not self._closing and not self._restoring:
            self._save.start()

    def _emit_layout(self) -> None:
        self.layoutChanged.emit(self.layout_state())

    def shutdown_windows(self) -> None:
        """Beim Programmende alle Zusatzfenster schließen, ohne den Merker zu ändern."""
        self._closing = True
        self._save.stop()
        for page in tuple(self._windows):
            self.return_page(page)

    def _screens_changed(self, *_args: object) -> None:
        QTimer.singleShot(0, self, self._fit_windows)

    def _fit_windows(self) -> None:
        rooms = [screen.availableGeometry() for screen in QApplication.screens()]
        for window in self._windows.values():
            rect = reachable_geometry(
                [window.x(), window.y(), window.width(), window.height()], rooms
            )
            if rect is not None:
                self._place_window(window, rect)

    @staticmethod
    def _place_window(window: _PanelWindow, rect: QRect) -> None:
        """x/y gehören zum Rahmen, Breite/Höhe zum Inhalt: entsprechend zurücksetzen."""
        window.resize(rect.size())
        window.move(rect.topLeft())
        fit_dialog_to_screen(window)

    def _menu(self, at: QPoint) -> None:
        index = self.tabBar().tabAt(at)
        if index < 0:
            index = self.currentIndex()
        page = self.widget(index)
        if page is None:
            return
        menu = QMenu(self)
        detached = page in self._windows
        action = menu.addAction(
            tr("Zurück in Solidon") if detached else tr("In eigenem Fenster öffnen")
        )
        action.triggered.connect(
            lambda: self.return_page(page) if detached else self.detach_page(page)
        )
        for text, step in ((tr("Nach links"), -1), (tr("Nach rechts"), 1)):
            action = menu.addAction(text)
            action.setEnabled(0 <= index + step < self.count())
            action.triggered.connect(
                lambda _checked=False, step=step: self.tabBar().moveTab(index, index + step)
            )
        menu.exec(self.tabBar().mapToGlobal(at))
        menu.deleteLater()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt-Name
        if stop_watching_the_dying(self, watched, event):
            return False
        if watched is self.tabBar():
            if (
                isinstance(event, QKeyEvent)
                and event.type() == QEvent.Type.KeyPress
                and (
                    event.key() == Qt.Key.Key_Menu
                    or (
                        event.key() == Qt.Key.Key_F10
                        and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                    )
                )
            ):
                self._menu(self.tabBar().tabRect(self.currentIndex()).center())
                return True
            if isinstance(event, QMouseEvent):
                if (
                    event.type() == QEvent.Type.MouseButtonPress
                    and event.button() == Qt.MouseButton.LeftButton
                ):
                    self._pressed = self.widget(self.tabBar().tabAt(event.position().toPoint()))
                    self._press_at = event.globalPosition().toPoint()
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    page, self._pressed = self._pressed, None
                    at = event.globalPosition().toPoint()
                    outside = (
                        not self.tabBar()
                        .rect()
                        .adjusted(-24, -24, 24, 24)
                        .contains(event.position().toPoint())
                    )
                    if (
                        page is not None
                        and outside
                        and (at - self._press_at).manhattanLength()
                        >= QApplication.startDragDistance()
                    ):
                        # Erst Qts laufende Umordnung beenden, dann den Inhalt umhängen.
                        QTimer.singleShot(0, self, lambda: self.detach_page(page, at))
        return super().eventFilter(watched, event)
