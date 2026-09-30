"""Dialogzustände behalten ihre erreichbaren Inhalte nach einer Layoutänderung."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMenuBar, QWidget

from app.ui.counterpart_dialog import CounterpartDialog
from app.ui.shortcuts_window import ShortcutsWindow


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
