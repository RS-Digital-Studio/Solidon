"""Dialogzustände behalten ihre erreichbaren Inhalte nach einer Layoutänderung."""

import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QDialog, QMenuBar, QWidget

from app.ui.counterpart_dialog import CounterpartDialog
from app.ui.shortcuts_window import ShortcutsWindow


def _settle(application: QApplication) -> None:
    """Lässt verzögerte Layoutmessungen einen vollständigen Umlauf durchlaufen."""
    for _ in range(12):
        application.processEvents()


def test_shortcut_search_reveals_closed_groups_and_restores_their_state(qt_app: QApplication):
    bar = QMenuBar()
    for group, title, shortcut in (
        ("Datei", "Öffnen", "Ctrl+O"),
        ("Bearbeiten", "Rückgängig", "Ctrl+Z"),
    ):
        action = bar.addMenu(group).addAction(title)
        action.setShortcut(QKeySequence(shortcut))
    dialog = ShortcutsWindow(bar)
    try:
        first, second = dialog.tree.topLevelItem(0), dialog.tree.topLevelItem(1)
        assert first is not None and second is not None
        first.setExpanded(False)
        second.setExpanded(True)
        dialog.search.setText("Öffnen")
        assert first.isExpanded()
        assert not first.child(0).isHidden()
        assert second.isHidden()
        dialog.search.setText("Rückgängig")
        assert second.isExpanded()
        assert first.isHidden()
        dialog.search.clear()
        assert not first.isExpanded()
        assert second.isExpanded()
        assert not first.isHidden() and not second.isHidden()
    finally:
        dialog.deleteLater()
        bar.deleteLater()


def test_rebuilt_counterpart_fields_stay_before_the_accept_button(qt_app: QApplication):
    dialog = CounterpartDialog("Erste Fläche", "Zweite Fläche")
    try:
        for index in range(dialog.pairs.count()):
            dialog.pairs.setCurrentIndex(index)
            fields = list(dialog._fields.values())
            expected = [*fields, dialog._accept]
            seen: list[QWidget] = []
            next_field = dialog.pairs.nextInFocusChain()
            while next_field is not dialog.pairs:
                if next_field in expected:
                    seen.append(next_field)
                next_field = next_field.nextInFocusChain()
            assert seen == expected
    finally:
        dialog.deleteLater()


def test_palette_detail_has_its_own_line_without_horizontal_scrolling(qt_app: QApplication):
    from app.core.registry import PaletteEntry
    from app.ui.command_palette import CommandPalette

    reason = "Wählen Sie zuerst einen Körper, damit der Befehl darauf angewendet werden kann. " * 4
    entry = PaletteEntry(
        name="dialog_layout_sample",
        title="Ein langer Befehlstitel für eine schmale Palette " * 4,
        category="modify",
        doc="Die vollständige Beschreibung des Befehls.",
        shortcut="Ctrl+Shift+B",
        available=False,
        reason=reason,
    )
    dialog = CommandPalette([entry])
    try:
        dialog.resize(520, 480)
        dialog.show()
        qt_app.processEvents()
        item = dialog.list.item(0)
        assert item is not None
        row = dialog.list.visualItemRect(item)
        assert row.height() >= 2 * dialog.list.fontMetrics().height()
        assert row.width() <= dialog.list.viewport().width()
        assert dialog.list.horizontalScrollBar().maximum() == 0
        assert dialog.list.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert reason in item.toolTip()
        assert str(entry.title) in item.toolTip()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_palette_shows_a_description_for_an_available_command(qt_app: QApplication) -> None:
    """Ein verfügbarer Treffer erklärt sein Ergebnis direkt in der Liste."""
    from app.core.registry import PaletteEntry
    from app.ui.command_palette import CommandPalette

    entry = PaletteEntry(
        name="available_dialog_layout_sample",
        title="Maß setzen",
        category="modify",
        doc="Legt den gewählten Wert für diesen Körper fest.",
        shortcut="",
        available=True,
        reason="",
    )
    dialog = CommandPalette([entry])
    try:
        item = dialog.list.item(0)
        assert item is not None
        assert item.text() == f"{entry.title}\n{entry.doc}"
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize("language", ["fr", "it"])
def test_settings_advanced_rows_fit_without_widening_the_dialog(
    qt_app: QApplication, language: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die zurückgestellten Zeilen passen schon vor dem Aufklappen in die Breite."""
    from PySide6.QtWidgets import QToolButton

    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language
    from app.ui import settings_dialog as settings_module
    from app.ui.settings import UiSettings
    from app.ui.theme import apply_theme

    spoken = get_language()
    dialog: settings_module.SettingsDialog | None = None
    monkeypatch.setattr(settings_module.discover, "remembered_path", lambda _key: "")
    monkeypatch.setattr(settings_module._SlicerWorker, "work", lambda worker: worker.done.emit(()))
    try:
        apply_theme(qt_app, UiSettings().theme)
        install_language(language)
        set_language(language)
        dialog = settings_module.SettingsDialog(UiSettings(language=language))
        dialog.show()
        _settle(qt_app)
        initial_width = dialog.width()
        heading = dialog.advanced.findChild(QToolButton)
        assert heading is not None
        heading.click()
        _settle(qt_app)
        assert dialog.width() == initial_width
        assert dialog._scroll.horizontalScrollBar().maximum() == 0

        expanded_height = dialog.height()
        short_height = max(dialog.minimumSizeHint().height(), expanded_height // 2)
        assert short_height < expanded_height
        dialog.resize(initial_width, short_height)
        _settle(qt_app)
        assert dialog.height() == short_height
        assert dialog.width() == initial_width
        assert dialog._scroll.verticalScrollBar().maximum() > 0
        assert dialog._scroll.horizontalScrollBar().maximum() == 0
    finally:
        if dialog is not None:
            dialog.release()
            dialog.close()
        install_language(spoken)
        set_language(spoken)


def test_dialog_rechecks_reachability_when_screen_metrics_change(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Monitor- und DPI-Wechsel planen eine neue, reine Erreichbarkeitsprüfung."""
    from app.ui import style

    class SignalProbe:
        def __init__(self) -> None:
            self.slots: list[object] = []

        def connect(self, slot: object) -> None:
            self.slots.append(slot)

        def disconnect(self, slot: object) -> None:
            self.slots.remove(slot)

        def emit(self, *args: object) -> None:
            for slot in tuple(self.slots):
                assert callable(slot)
                slot(*args)

    class ScreenProbe:
        def __init__(self) -> None:
            self.availableGeometryChanged = SignalProbe()
            self.logicalDotsPerInchChanged = SignalProbe()

    class WindowProbe:
        def __init__(self, screen: ScreenProbe) -> None:
            self.screenChanged = SignalProbe()
            self.current_screen = screen

        def screen(self) -> ScreenProbe:
            return self.current_screen

    scheduled: list[object] = []
    fitted: list[QWidget] = []

    class TimerProbe:
        @staticmethod
        def singleShot(  # noqa: N802 — Qt-Name
            _delay: int, _receiver: QObject, callback: object
        ) -> None:
            scheduled.append(callback)

    monkeypatch.setattr(style, "QTimer", TimerProbe)
    monkeypatch.setattr(style, "fit_dialog_to_screen", fitted.append)

    dialog = QDialog()
    scroll = style.DialogScrollArea(dialog)
    first = ScreenProbe()
    second = ScreenProbe()
    window = WindowProbe(first)
    try:
        scroll._watch_screen(window)  # type: ignore[arg-type]
        assert len(first.availableGeometryChanged.slots) == 1
        assert len(first.logicalDotsPerInchChanged.slots) == 1

        window.current_screen = second
        window.screenChanged.emit(second)
        assert first.availableGeometryChanged.slots == []
        assert first.logicalDotsPerInchChanged.slots == []
        assert len(second.availableGeometryChanged.slots) == 1
        assert len(second.logicalDotsPerInchChanged.slots) == 1

        second.logicalDotsPerInchChanged.emit(144.0)
        assert len(scheduled) == 2
        for callback in scheduled:
            assert callable(callback)
            callback()
        assert fitted == [dialog, dialog]
    finally:
        dialog.deleteLater()
        qt_app.processEvents()
