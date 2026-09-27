"""Welches Bedienelement ein Name aus dem Wortschatz der Bildanleitungen meint.

Der Kern nennt Namen (:mod:`app.core.guides`), die Oberfläche kennt die
Widgets. Zusammengeführt wird beides hier und nur hier — für die Tour, die
einen Bereich aufleuchten lässt (``MainWindow._flash_area``), und für die
Aufnahme der Bildanleitungen, die Nummer und Rahmen auf genau dieses Element
setzt (``tools/make_guides.py``). Vorher stand die Zuordnung der sieben
Tour-Namen im Fenster selbst, und eine zweite hätte in der Aufnahme gestanden.

**Ein Name, der sich nicht auflösen lässt, ist ein Fehler** (:class:`MissingTargetError`)
und keine leere Markierung. Genau so scheitert die Aufnahme beim Release, wenn
ein Knopf umbenannt, verschoben oder entfernt wurde — das ist die Zusage,
dass das Handbuch zur Version passt (Konzept Handbuch §6). Wo ein fehlendes
Ziel nur einen Schönheitsfehler bedeutet, fängt der Aufrufer den Fehler selbst
ab, wie die Tour.

Zwei Fragen, zwei Funktionen: :func:`widget_for` beantwortet „welches Widget",
auch wenn es gerade nicht zu sehen ist; :func:`area_for` beantwortet „wo auf
dem Bildschirm", und das nur für Sichtbares. Menüeinträge und Listenzeilen
haben kein eigenes Widget — sie haben nur einen Ort.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialogButtonBox,
    QListWidget,
    QMenu,
    QPushButton,
    QScrollArea,
    QWidget,
)

from app.core import guides

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow


class MissingTargetError(LookupError):
    """Ein Name aus dem Wortschatz, dessen Ziel gerade nicht da ist."""


def _start(window: MainWindow, attribute: str) -> QWidget:
    return getattr(window.start_screen, attribute)  # type: ignore[no-any-return]


def _drop_area(window: MainWindow) -> QWidget:
    from app.ui.start_screen import DropArea

    area = window.start_screen.findChild(DropArea)
    if area is None:
        raise MissingTargetError("start.drop: der Startbildschirm hat keine Ablagefläche")
    return area


def _open_dialog(window: MainWindow) -> QWidget:
    """Der offene Operationsdialog, sonst der Dialog, der gerade modal läuft."""
    dialog = window._op_dialog
    if dialog is not None and dialog.isVisible():
        return dialog
    modal = QApplication.activeModalWidget()
    if modal is None:
        raise MissingTargetError("dialog: es ist kein Dialog offen")
    return modal


def _accept_button(window: MainWindow) -> QWidget:
    """Der Hauptknopf des offenen Dialogs.

    Im Operationsdialog heißt er wie die Operation, bei Bausteinen „Einsetzen";
    in anderen Dialogen ist es der Knopf, den die Knopfleiste als Bestätigung
    führt.
    """
    dialog = _open_dialog(window)
    accept = getattr(dialog, "_accept_button", None)
    if isinstance(accept, QAbstractButton):
        return accept
    box = dialog.findChild(QDialogButtonBox)
    if box is not None:
        # Nur die Knopfarten, die die Anwendung benutzt — eine weitere hier
        # zählte ``test_every_used_qt_standard_button_is_covered_by_the_language_test``
        # als neuen Knopf ohne geprüfte Übersetzung.
        for role in (QDialogButtonBox.StandardButton.Ok, QDialogButtonBox.StandardButton.Save):
            button = box.button(role)
            if button is not None:
                return button
    raise MissingTargetError(f"dialog.accept: {type(dialog).__name__} hat keinen Hauptknopf")


def _report_action(window: MainWindow) -> QWidget:
    """Die erste Handlung, die der Prüfbericht zum gewählten Befund anbietet."""
    offers = window.report._offers
    buttons = [button for button in offers.findChildren(QPushButton) if button.isVisible()]
    if not buttons:
        raise MissingTargetError("report.action: kein Befund gewählt, oder er bietet nichts an")
    return buttons[0]


def _report_slicer(window: MainWindow) -> QWidget:
    """„An den Slicer übergeben …" — er steht nur da, wenn nichts mehr zu beanstanden ist."""
    button: QWidget = window.report.to_slicer
    return button


def _selection_parts(window: MainWindow) -> QWidget:
    """„Bausteine" unten im Auswahlfenster — sichtbar ohne Auswahl und an einer Fläche."""
    button: QWidget = window.selection_operations.catalog_button
    return button


def _transform_values(window: MainWindow) -> QWidget:
    """Die Zahlenfelder der Bewegen-Leiste, gleich welche Rolle gerade gewählt ist."""
    fields: QWidget = window.transform_bar.fields
    return fields


def _first_parameter(window: MainWindow) -> QWidget:
    """Das Wertfeld der ersten Zeile unter *Parameter*.

    Über die Reihenfolge und nicht über den Namen: Ein benanntes Maß heißt nach
    seinem Titel in der Sprache, in der es angelegt wurde (``breite``,
    ``width``), und eine Anleitung soll in jeder Sprache dieselbe Zeile meinen.
    """
    editors = window.parameters._editors
    if not editors:
        raise MissingTargetError("parameters.first: das Projekt hat noch keinen Parameter")
    return next(iter(editors.values()))


def _naming_box(window: MainWindow) -> QWidget:
    """Der Haken *Maße als Parameter anlegen* im offenen Operationsdialog."""
    dialog = window._op_dialog
    naming = dialog._naming if dialog is not None and dialog.isVisible() else None
    if naming is None:
        raise MissingTargetError("dialog.naming: kein offener Dialog mit benannten Maßen")
    return naming


def _draw_button(window: MainWindow) -> QWidget:
    """*Zeichnen* in der Werkzeugleiste — ein Knopf ohne Menüeintrag gleichen Namens."""
    button = window.toolbar.widgetForAction(window._toolbar_sketch)
    if button is None:
        raise MissingTargetError("toolbar.draw: die Werkzeugleiste trägt kein Zeichnen")
    return button


def _sketch_panel(window: MainWindow, name: str) -> Any:
    panel = window._sketch_panel
    if panel is None:
        raise MissingTargetError(f"{name}: der Zeichenmodus ist nicht offen")
    return panel


def _sketch_plane(window: MainWindow) -> QWidget:
    """Die Wahl der Zeichenebene im offenen Zeichenmodus."""
    choice: QWidget = _sketch_panel(window, "sketch.plane").plane_choice
    return choice


def _sketch_pull(window: MainWindow) -> QWidget:
    """*Hochziehen* an der fertigen Kontur."""
    button: QWidget = window.sketch_pull_button
    return button


def _sketch_done(window: MainWindow) -> QWidget:
    """*Fertig* im Zeichenmodus."""
    button: QWidget = window.sketch_finish_button
    return button


def _named(window: MainWindow, kind: str, rest: str) -> QWidget:
    """Ein Ziel mit Namen dahinter, dessen Widget die Oberfläche unter diesem Namen führt."""
    name = f"{kind}:{rest}"
    if kind == "tool":
        tool = window.tools._buttons.get(rest)
        if tool is None:
            raise MissingTargetError(f"{name}: kein Werkzeug dieses Namens unter der Ansicht")
        return tool
    if kind == "transform":
        role = window.transform_bar.role_buttons.get(rest)
        if role is None:
            raise MissingTargetError(f"{name}: die Bewegen-Leiste kennt diese Rolle nicht")
        return role
    if kind == "section":
        from app.core.registry.registry import group_title

        group = window.selection_operations._groups.get(group_title(rest))
        if group is None:
            raise MissingTargetError(f"{name}: das Auswahlfenster zeigt diesen Abschnitt nicht")
        heading: QWidget = group[1]
        return heading
    if kind == "sketch":
        button = _sketch_panel(window, name)._tool_buttons.get(rest)
        if button is None:
            raise MissingTargetError(f"{name}: der Zeichenmodus kennt dieses Werkzeug nicht")
        return button  # type: ignore[no-any-return]
    raise MissingTargetError(f"{name}: hat kein eigenes Widget, nur einen Ort (area_for)")


def _print_dialog(window: MainWindow) -> QWidget:
    """Der Druckdialog. Er läuft modal über ``exec()`` und hängt an keinem Attribut."""
    from app.ui.print_settings_dialog import PrintSettingsDialog

    dialog = QApplication.activeModalWidget()
    if not isinstance(dialog, PrintSettingsDialog):
        raise MissingTargetError("print: der Druckdialog ist nicht offen")
    return dialog


#: Die Teile des Druckdialogs: Name → Attribut des Dialogs.
_PRINT: Final[dict[str, str]] = {
    "print.printer": "printer_choice",
    "print.slice": "slice_button",
    "print.save": "save_button",
}


#: Die Bereiche des Hauptfensters: Name → Attribut des Fensters.
#:
#: Als Attributname und nicht als Lambda: Fenster und diese Datei kennen
#: einander, und mypy kann den Typ eines Attributs, das ``MainWindow`` erst in
#: ``__init__`` setzt, in einem solchen Kreis nicht bestimmen.
_AREAS: Final[dict[str, str]] = {
    "tree": "object_tree",
    "parameters": "parameters",
    "history": "history_panel",
    "report": "report",
    "viewport": "viewport",
    "toolbar": "toolbar",
    "tools": "tools",
    "header": "header",
    "selection": "feature_dock",
}

#: Die Knöpfe des Startbildschirms: Name → Attribut des Startbildschirms.
_START: Final[dict[str, str]] = {
    "start.new": "new_button",
    "start.model": "import_button",
    "start.project": "open_button",
    "start.manual": "manual_button",
}

#: Was sich nur mit einer Frage an den Zustand finden lässt.
_FINDERS: Final[dict[str, Callable[[MainWindow], QWidget]]] = {
    "statusbar": lambda window: window.statusBar(),
    "report.action": _report_action,
    "report.slicer": _report_slicer,
    "selection.parts": _selection_parts,
    "start.drop": _drop_area,
    "dialog": _open_dialog,
    "dialog.accept": _accept_button,
    "dialog.naming": _naming_box,
    "transform.values": _transform_values,
    "parameters.first": _first_parameter,
    "toolbar.draw": _draw_button,
    "sketch.plane": _sketch_plane,
    "sketch.pull": _sketch_pull,
    "sketch.done": _sketch_done,
}

#: Die Namen, die keinen eigenen Widget haben, nur einen Ort.
_PLACES: Final = frozenset({"history.last"})

#: Was diese Datei auflöst. ``tests/test_guides.py`` hält es gegen den
#: Wortschatz im Kern — ein Name dort, den hier niemand kennt, wäre eine
#: Anleitung, die erst beim Release scheitert.
RESOLVED: Final[frozenset[str]] = (
    frozenset(_AREAS) | frozenset(_START) | frozenset(_PRINT) | frozenset(_FINDERS) | _PLACES
)


def widget_for(window: MainWindow, name: str) -> QWidget:
    """Das Widget hinter einem festen Namen oder einem ``operation:``/``field:``-Ziel."""
    if not guides.is_target(name):
        raise MissingTargetError(f"{name}: kein Name aus dem Wortschatz der Anleitungen")
    if name in _AREAS:
        return getattr(window, _AREAS[name])  # type: ignore[no-any-return]
    if name in _START:
        return _start(window, _START[name])
    if name in _PRINT:
        return getattr(_print_dialog(window), _PRINT[name])  # type: ignore[no-any-return]
    finder = _FINDERS.get(name)
    if finder is not None:
        return finder(window)
    kind, _separator, rest = name.partition(":")
    if kind == "field":
        dialog = window._op_dialog
        editor = dialog._editors.get(rest) if dialog is not None else None
        if editor is None:
            raise MissingTargetError(f"{name}: kein offener Dialog mit diesem Feld")
        return editor
    if kind == "operation":
        button = window.selection_operations._buttons.get(rest)
        if button is not None and button.isVisible():
            return button
    return _named(window, kind, rest)


def area_for(window: MainWindow, name: str) -> QRect:
    """Wo das Ziel gerade auf dem Bildschirm steht, in globalen Koordinaten.

    Nur Sichtbares hat einen Ort. Ein Menüeintrag hat ihn nur, solange sein
    Menü offen ist — das öffnet der Aufrufer. Ein Widget in einem Rollbereich
    wird vorher in den Blick gerollt, wie der Kunde es mit dem Mausrad täte:
    Im aufgeklappten Abschnitt *Ändern* stand *Verrunden* unterhalb des
    sichtbaren Teils, und ein Rahmen darum hätte ins Leere gezeigt.
    """
    if name == "history.last":
        return _last_row(window.history_panel.list, name)
    if name == "viewport":
        return _open_view(window)
    kind, separator, rest = name.partition(":")
    if kind == "part":
        return _catalog_tile(rest, name)
    if separator and kind == "history":
        return _open_menu_entry_named(f"history.{rest}", name)
    if kind in ("command", "operation"):
        action = _action_for(window, kind, rest)
        if kind == "operation":
            button = window.selection_operations._buttons.get(rest)
            if button is not None and button.isVisible():
                return _global(_in_view(button))
        shown = _shown_in_toolbar(window, action)
        if shown is not None:
            return _global(shown)
        return _open_menu_entry(action, name)
    widget = widget_for(window, name)
    if not widget.isVisible():
        raise MissingTargetError(f"{name}: {type(widget).__name__} ist gerade nicht zu sehen")
    return _global(_in_view(widget))


def _in_view(widget: QWidget) -> QWidget:
    """Das Widget in seinem Rollbereich in den sichtbaren Teil rollen, falls es einen hat."""
    parent = widget.parentWidget()
    while parent is not None and not isinstance(parent, QScrollArea):
        parent = parent.parentWidget()
    if parent is not None:
        parent.ensureWidgetVisible(widget, 0, 24)
    return widget


def _global(widget: QWidget) -> QRect:
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


def _open_view(window: MainWindow) -> QRect:
    """Der Teil der Ansicht, den man sieht: zwischen den Karten, über der Werkzeugzeile.

    Die Ansicht liegt als Ganzes **hinter** den Karten mit Objekten und
    Prüfbericht; ihr Widget reicht von Rand zu Rand. Ein Rahmen darum umschloss
    im ersten Probelauf fast das ganze Fenster und damit jeden anderen Bereich
    mit. Gemeint ist, was der Kunde als Ansicht sieht — gemessen an den Karten
    selbst, damit ein geändertes Layout hier nichts nachzuziehen verlangt.
    """
    view = _global(window.viewport)
    if not window.viewport.isVisible():
        raise MissingTargetError("viewport: die Ansicht ist gerade nicht zu sehen")
    # Ein Abstand zu den Karten, damit ein Rahmen um die Ansicht nicht auf dem
    # Rahmen der Nachbarkarte liegt und seine Nummer Platz neben ihr findet.
    gap = 16
    left, top, right, bottom = view.left(), view.top() + gap, view.right(), view.bottom()
    card = window.overlay.left
    if card is not None and card.isVisible():
        left = max(left, _global(card).right() + 1 + gap)
    column = window.right_column
    if column.isVisible():
        right = min(right, _global(column).left() - 1 - gap)
    strip = window.overlay.bottom
    if strip is not None and strip.isVisible():
        bottom = min(bottom, _global(strip).top() - 1 - gap)
    return QRect(QPoint(left, top), QPoint(right, bottom))


def _catalog_tile(part: str, name: str) -> QRect:
    """Die Kachel eines Bausteins im Katalog, der gerade offen ist.

    Der Katalog läuft modal über ``exec()`` und hängt an keinem Attribut des
    Fensters; seine Kachel ist eine Listenzeile ohne eigenes Widget.
    """
    from app.ui.catalog import PartCatalog

    catalog = QApplication.activeModalWidget()
    if not isinstance(catalog, PartCatalog):
        raise MissingTargetError(f"{name}: der Bausteinkatalog ist nicht offen")
    view = catalog.list
    for row in range(view.count()):
        item = view.item(row)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == part:
            view.scrollToItem(item)
            rect = view.visualItemRect(item)
            return QRect(view.viewport().mapToGlobal(rect.topLeft()), rect.size())
    raise MissingTargetError(f"{name}: der Katalog zeigt keinen Baustein dieses Namens")


def _last_row(view: QListWidget, name: str) -> QRect:
    """Die letzte Zeile, die man sieht.

    Nicht die letzte der Liste: Ein Schritt aus mehreren Operationen steht als
    Gruppe mit eingeklappten Unterzeilen da („Drehen und aufs Bett setzen"),
    und ein Rahmen um die verborgene letzte Unterzeile schrumpfte auf einen
    Punkt am Rand.
    """
    for row in range(view.count() - 1, -1, -1):
        item = view.item(row)
        if item is None or item.isHidden():
            continue
        view.scrollToItem(item)
        rect = view.visualItemRect(item)
        return QRect(view.viewport().mapToGlobal(rect.topLeft()), rect.size())
    raise MissingTargetError(f"{name}: die Liste ist leer")


def action_for(window: MainWindow, name: str) -> QAction:
    """Die Menüaktion hinter einem ``command:``- oder ``operation:``-Ziel.

    Für die Aufnahme, die das Menü bis zu diesem Eintrag öffnet, bevor sie ihn
    markiert: :func:`area_for` findet einen Menüeintrag nur, solange sein Menü
    offen ist.
    """
    kind, _separator, rest = name.partition(":")
    if kind not in ("command", "operation"):
        raise MissingTargetError(f"{name}: nur Befehle und Operationen stehen in einem Menü")
    return _action_for(window, kind, rest)


def _action_for(window: MainWindow, kind: str, rest: str) -> QAction:
    """Die Menüaktion hinter einer Befehlskennung oder einem Operationsnamen."""
    if kind == "operation":
        action = window._op_actions.get(rest)
        if action is None:
            raise MissingTargetError(f"operation:{rest}: keine Operation dieses Namens im Menü")
        return action
    commands = window.window_commands()
    if rest not in commands:
        raise MissingTargetError(f"command:{rest}: keine Befehlskennung des Fensters")
    title = commands[rest][0]
    for action in _menu_actions(window.menuBar().actions()):
        if action.text() == title:
            return action
    raise MissingTargetError(f"command:{rest}: „{title}“ steht in keinem Menü")


def _menu_actions(actions: list[QAction]) -> Iterator[QAction]:
    for action in actions:
        if action.isSeparator():
            continue
        sub = action.menu()
        if isinstance(sub, QMenu):
            yield from _menu_actions(sub.actions())
            continue
        yield action


def _shown_in_toolbar(window: MainWindow, action: QAction) -> QWidget | None:
    """Der Knopf der Werkzeugleiste mit derselben Beschriftung, falls sichtbar."""
    for candidate in window.toolbar.actions():
        if candidate.text() == action.text():
            button = window.toolbar.widgetForAction(candidate)
            if button is not None and button.isVisible():
                return button
    return None


def _open_menu_entry(action: QAction, name: str) -> QRect:
    """Der Ort eines Eintrags in einem gerade offenen Menü."""
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QMenu) and widget.isVisible() and action in widget.actions():
            rect = widget.actionGeometry(action)
            return QRect(widget.mapToGlobal(rect.topLeft()), rect.size())
    raise MissingTargetError(f"{name}: steht weder sichtbar im Fenster noch in einem offenen Menü")


def _open_menu_entry_named(object_name: str, name: str) -> QRect:
    """Der Ort eines Eintrags mit diesem Objektnamen in einem gerade offenen Kontextmenü."""
    for widget in QApplication.topLevelWidgets():
        if not isinstance(widget, QMenu) or not widget.isVisible():
            continue
        for action in widget.actions():
            if action.objectName() == object_name:
                return _open_menu_entry(action, name)
    raise MissingTargetError(f"{name}: kein offenes Kontextmenü trägt diesen Eintrag")
