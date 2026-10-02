"""Dialogzustände behalten ihre erreichbaren Inhalte nach einer Layoutänderung."""

import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QMenuBar,
    QScrollArea,
    QWidget,
)

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


def _room(dialog: QDialog) -> int:
    """Die Breite, die ``fit_dialog_to_screen`` einem Dialog höchstens lässt."""
    from app.ui.style import NORMAL

    screen = dialog.screen()
    assert screen is not None
    border = dialog.frameGeometry().width() - dialog.width()
    return screen.availableGeometry().width() - 2 * NORMAL - border


def _sideways(dialog: QDialog, scroll: QScrollArea, natural: int) -> None:
    """Quer rollt höchstens, was der Bildschirm von der natürlichen Breite abschneidet.

    Offscreen ist der Bildschirm 800 Punkte breit und die Schrift breiter als
    unter Windows; dort deckelt ``fit_dialog_to_screen`` die Breite, und der
    Rest rollt (``fenster.md``, Dialoggröße nach Auslöser). Auf einem
    Bildschirm mit Platz ist der Unterschied null. Mehr als dieser Rest hieße:
    Die zugeklappten Zeilen waren beim Öffnen nicht mitgerechnet (RM-342 D-N5).
    """
    assert scroll.horizontalScrollBar().maximum() == max(0, natural - dialog.width())


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "it", "pt"])
def test_settings_advanced_rows_fit_without_widening_the_dialog(
    qt_app: QApplication, language: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die zurückgestellten Zeilen passen schon vor dem Aufklappen in die Breite.

    In jeder Sprache: Ein längerer Satz in der Klappe ist genau der Fall, den
    das Öffnen mitrechnen muss.
    """
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
        natural = dialog._natural_advanced_width
        assert initial_width == min(natural, _room(dialog)), "beim Öffnen schon so breit wie nötig"
        heading.click()
        _settle(qt_app)
        assert dialog.width() == initial_width
        _sideways(dialog, dialog._scroll, natural)

        expanded_height = dialog.height()
        short_height = max(dialog.minimumSizeHint().height(), expanded_height // 2)
        assert short_height < expanded_height
        dialog.resize(initial_width, short_height)
        _settle(qt_app)
        assert dialog.height() == short_height
        assert dialog.width() == initial_width
        assert dialog._scroll.verticalScrollBar().maximum() > 0
        _sideways(dialog, dialog._scroll, natural)
    finally:
        if dialog is not None:
            dialog.release()
            dialog.close()
        install_language(spoken)
        set_language(spoken)


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "it", "pt"])
def test_print_settings_hidden_sections_fit_without_widening_the_dialog(
    qt_app: QApplication, language: str
) -> None:
    """*Weitere Einstellungen* und *Profile des Slicers* zählen schon beim Öffnen mit.

    Der Druckdialog maß nur die Reiterleiste; aufgeklappt rollte er auf
    Deutsch 138 Punkte quer, obwohl der Bildschirm Platz hatte (RM-342 D-N5).
    Geprüft wird jeder Reiter, denn jeder hat eigene Zeilen.
    """
    from PySide6.QtWidgets import QToolButton

    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    spoken = get_language()
    dialog: PrintSettingsDialog | None = None
    try:
        install_language(language)
        set_language(language)
        dialog = PrintSettingsDialog(Session(), UiSettings())
        assert dialog.wait_for_slicers()
        dialog.show()
        _settle(qt_app)
        natural = dialog._natural_width()
        opened = dialog.width()
        assert opened == min(natural, _room(dialog)), "beim Öffnen schon so breit wie nötig"
        closed = [
            heading
            for heading in dialog.findChildren(QToolButton)
            if heading.objectName() == "sectionHeading" and not heading.isChecked()
        ]
        assert len(closed) >= 2, "Reiter und Slicerprofile stehen zugeklappt"
        for heading in closed:
            heading.click()
        _settle(qt_app)
        for index in range(dialog.tabs.count()):
            dialog.tabs.setCurrentIndex(index)
            _settle(qt_app)
            assert dialog.width() == opened, dialog.tabs.tabText(index)
            _sideways(dialog, dialog._scroll, natural)
    finally:
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()
        install_language(spoken)
        set_language(spoken)


def test_the_hidden_width_is_the_width_after_opening(qt_app: QApplication) -> None:
    """``expanded_width`` rechnet zugeklappt, was aufgeklappt gemessen wird.

    Eine Klappe in einer Gruppe in einem Rollbereich, mit einer Zeile, die
    breiter ist als alles Sichtbare, und einer bedingt verborgenen, die noch
    breiter ist. Zugeklappt gerechnet muss herauskommen, was der Dialog nach
    dem Aufklappen braucht, wenn auch die verborgene Zeile erscheint.
    """
    from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QLineEdit, QVBoxLayout

    from app.ui.panels import collapsible
    from app.ui.style import DialogScrollArea, expanded_width

    dialog = QDialog()
    try:
        outer = QVBoxLayout(dialog)
        scroll = DialogScrollArea(dialog)
        contents = QWidget(scroll)
        column = QVBoxLayout(contents)
        group = QGroupBox("Gruppe", contents)
        group_form = QFormLayout(group)
        group_form.addRow("Sichtbar", QLineEdit(group))
        body = QWidget(group)
        hidden = QFormLayout(body)
        hidden.addRow("Breit", QLabel("x" * 80, body))
        late = QLabel("y" * 120, body)
        hidden.addRow("Später", late)
        hidden.setRowVisible(late, False)
        section = collapsible("Weitere Einstellungen", body, open_now=False)
        group_form.addRow(section)
        column.addWidget(group)
        scroll.setWidget(contents)
        outer.addWidget(scroll)

        computed = expanded_width(scroll, hidden)
        assert computed > max(dialog.sizeHint().width(), dialog.minimumSizeHint().width())

        hidden.setRowVisible(late, True)
        body.setVisible(True)
        for layout in (hidden, section.layout(), group_form, column, outer):
            assert layout is not None
            layout.invalidate()
            layout.activate()
        needed = (
            contents.sizeHint().width()
            + 2 * scroll.frameWidth()
            + scroll.verticalScrollBar().sizeHint().width()
        )
        margins = outer.contentsMargins()
        assert computed == needed + margins.left() + margins.right()
    finally:
        dialog.deleteLater()


def test_parameter_dialog_keeps_validation_and_actions_reachable_when_short(
    qt_app: QApplication,
) -> None:
    """Der Formularinhalt rollt; Fehlermeldung und Aktionsknöpfe bleiben erreichbar."""
    from PySide6.QtCore import QPoint, QSize

    from app.ui.dialogs import ParameterDialog
    from app.ui.settings import UiSettings
    from app.ui.theme import apply_theme

    apply_theme(qt_app, UiSettings().theme)
    dialog = ParameterDialog({})
    try:
        dialog.show()
        _settle(qt_app)
        natural_height = dialog.height()
        short_height = max(dialog.minimumSizeHint().height(), natural_height // 2)
        assert short_height < natural_height
        dialog.resize(dialog.width(), short_height)
        _settle(qt_app)
        assert dialog.height() == short_height
        locked_size = QSize(dialog.size())
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        assert buttons.isVisible()
        assert buttons.parentWidget() is dialog
        assert dialog._scroll.verticalScrollBar().maximum() > 0

        dialog.name_field.clear()
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None
        ok.click()
        _settle(qt_app)
        assert dialog.size() == locked_size
        assert dialog.problem.isVisible()
        assert dialog._scroll.verticalScrollBar().maximum() > 0
        problem_position = dialog.problem.mapTo(dialog._scroll.viewport(), QPoint(0, 0))
        problem_rect = dialog.problem.rect().translated(problem_position)
        assert dialog._scroll.viewport().rect().contains(problem_rect)
        assert buttons.isVisible()
        assert buttons.geometry().bottom() < dialog.rect().bottom()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_expression_dialog_keeps_validation_and_actions_reachable_when_short(
    qt_app: QApplication,
) -> None:
    """Ein ungültiger Ausdruck wird im Rollbereich sichtbar; die Knöpfe bleiben stehen."""
    from PySide6.QtCore import QPoint, QSize

    from app.ui.settings import UiSettings
    from app.ui.sketch_editor import ExpressionDialog
    from app.ui.theme import apply_theme

    apply_theme(qt_app, UiSettings().theme)
    dialog = ExpressionDialog({})
    try:
        dialog.hint.setText("Der Hinweistext bleibt beim Prüfen sichtbar. " * 32)
        dialog.show()
        _settle(qt_app)
        natural_height = dialog.height()
        short_height = max(dialog.minimumSizeHint().height(), natural_height // 2)
        assert short_height < natural_height
        dialog.resize(dialog.width(), short_height)
        _settle(qt_app)
        assert dialog.height() == short_height
        locked_size = QSize(dialog.size())
        assert dialog.scroll_area.horizontalScrollBar().maximum() == 0
        assert dialog.buttons.isVisible()

        dialog.field.clear()
        ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None
        ok.click()
        _settle(qt_app)
        assert dialog.size() == locked_size
        assert dialog.problem.isVisible()
        assert dialog.scroll_area.verticalScrollBar().maximum() > 0
        problem_position = dialog.problem.mapTo(dialog.scroll_area.viewport(), QPoint(0, 0))
        problem_rect = dialog.problem.rect().translated(problem_position)
        assert dialog.scroll_area.viewport().rect().contains(problem_rect)
        assert dialog.buttons.geometry().bottom() < dialog.rect().bottom()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_dialog_button_rows_use_the_design_spacing(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parameter-, Filament- und Einstellungsdialog halten denselben Knopfabstand ein."""
    from app.ui import settings_dialog as settings_module
    from app.ui.dialogs import ParameterDialog
    from app.ui.filament_picker import NewFilamentDialog
    from app.ui.settings import UiSettings
    from app.ui.style import SPACE

    for dialog in (ParameterDialog({}), NewFilamentDialog()):
        try:
            buttons = dialog.findChild(QDialogButtonBox)
            assert buttons is not None
            button_layout = buttons.layout()
            assert button_layout is not None
            assert button_layout.spacing() == SPACE
        finally:
            dialog.deleteLater()

    monkeypatch.setattr(settings_module.discover, "remembered_path", lambda _key: "")
    monkeypatch.setattr(settings_module._SlicerWorker, "work", lambda worker: worker.done.emit(()))
    settings = settings_module.SettingsDialog(UiSettings(), slicer_path="")
    try:
        buttons = settings.findChild(QDialogButtonBox)
        assert buttons is not None
        button_layout = buttons.layout()
        assert button_layout is not None
        assert button_layout.spacing() == SPACE
    finally:
        settings.release()
        settings.deleteLater()


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


@pytest.mark.parametrize(
    ("doc", "available", "reason", "expected"),
    [
        ("Maß setzen", True, "", ["Maß setzen"]),
        ("Legt den Wert fest.", True, "", ["Maß setzen", "Legt den Wert fest."]),
        ("Erst wählen.", False, "Erst wählen.", ["Maß setzen", "Erst wählen."]),
        (
            "Legt den Wert fest.",
            False,
            "Erst wählen.",
            ["Maß setzen", "Erst wählen.", "Legt den Wert fest."],
        ),
    ],
)
def test_the_palette_tooltip_names_every_line_once(
    qt_app: QApplication, doc: str, available: bool, reason: str, expected: list[str]
) -> None:
    """Titel, Grund und Beschreibung stehen je einmal im Tooltip, zeilengenau
    (RM-342, C-N2): Ein ``doc`` gleich dem Titel und ein Grund gleich dem
    ``doc`` wurden entdoppelt, ohne dass ein Test es hielt."""
    from app.core.registry import PaletteEntry
    from app.ui.command_palette import CommandPalette

    entry = PaletteEntry(
        name="tooltip_sample",
        title="Maß setzen",
        category="modify",
        doc=doc,
        shortcut="",
        available=available,
        reason=reason,
    )
    dialog = CommandPalette([entry])
    try:
        item = dialog.list.item(0)
        assert item is not None
        assert item.toolTip().split("\n") == expected
    finally:
        dialog.deleteLater()
