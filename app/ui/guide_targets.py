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

import itertools
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QTabBar,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QWidget,
)

from app.core import guides
from app.ui.labels import RowCheckBox
from app.ui.overlay import MARGIN, free_span

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
    """*Bausteinkatalog …* unten im Auswahlfenster — ohne Auswahl und an einer Fläche."""
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


def _more_flap(window: MainWindow) -> QWidget:
    """Die Klappe *Weitere Einstellungen* im offenen Operationsdialog."""
    dialog = window._op_dialog
    flap = getattr(dialog, "advanced", None) if dialog is not None and dialog.isVisible() else None
    if not isinstance(flap, QWidget) or not flap.isVisible():
        raise MissingTargetError("dialog.more: kein offener Dialog mit weiteren Einstellungen")
    return flap


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


def _print_dialog() -> QWidget:
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
def _filament_section(window: MainWindow) -> QWidget:
    """Die Klappe „Filament und Druck“ unter der Liste der Auswahl."""
    section = window.selection_operations.print_section
    heading = section.findChild(QToolButton, "sectionHeading")
    if heading is None:
        raise MissingTargetError("filament.section: keine Klappe „Filament und Druck“")
    return heading


def _filament_picker(window: MainWindow) -> QWidget:
    """Der Filamentwähler in der Klappe — dort wird gefärbt (RM-510)."""
    return window.quick_filament.picker


def marked_widgets(window: MainWindow, name: str) -> list[QWidget]:
    """Jedes Widget, das ``name`` als Kennzeichen trägt (``guides.TARGET_PROPERTY``).

    Gesucht wird im Fenster und in jedem offenen Fenster ohne Elternteil — ein
    Dialog über ``exec()`` hängt nicht immer am Hauptfenster. Sichtbare stehen
    vorn, sonst gilt die Reihenfolge, in der sie entstanden sind.
    """
    roots: list[QWidget] = [window]
    roots.extend(
        widget
        for widget in QApplication.topLevelWidgets()
        if widget is not window and widget.isVisible() and widget.parentWidget() is None
    )
    found: list[QWidget] = []
    for root in roots:
        if root.property(guides.TARGET_PROPERTY) == name:
            found.append(root)
        found.extend(
            widget
            for widget in root.findChildren(QWidget)
            if widget.property(guides.TARGET_PROPERTY) == name
        )
    # Ein verborgenes Feld eines offenen Dialogs geht einem liegengebliebenen
    # aus einem geschlossenen vor.
    return sorted(
        found, key=lambda widget: (not widget.isVisible(), not widget.window().isVisible())
    )


def _marked(name: str) -> Callable[[MainWindow], QWidget]:
    """Ein Finder für ein Ziel, das sein Widget als Kennzeichen trägt."""

    def find(window: MainWindow) -> QWidget:
        found = marked_widgets(window, name)
        if not found:
            raise MissingTargetError(f"{name}: kein Bedienelement trägt dieses Kennzeichen")
        return found[0]

    return find


def _rebuild_button(window: MainWindow) -> QWidget:
    """*Modell nachbauen* in der Auswahlkarte — er steht nur an einem Netzkörper."""
    button: QWidget = window.selection_operations.rebuild_button
    return button


def _search_field(window: MainWindow) -> QWidget:
    """Das Suchfeld der Auswahlkarte (RM-735)."""
    field: QWidget = window.selection_operations.search
    return field


def _toolbar_search(window: MainWindow) -> QWidget:
    """*Funktion suchen …* oben in der Werkzeugleiste."""
    button: QWidget = window.function_search
    return button


def _progress_cancel(window: MainWindow) -> QWidget:
    """*Abbrechen* in der Statusleiste — er steht nur, solange etwas läuft."""
    button: QWidget = window.cancel_button
    return button


def _preview_banner(window: MainWindow) -> QWidget:
    """Das Vorschauband über der Ansicht — es steht nur, solange eine Vorschau läuft."""
    banner: QWidget = window.viewport.banner
    return banner


_FINDERS: Final[dict[str, Callable[[MainWindow], QWidget]]] = {
    "filament.section": _filament_section,
    "filament.picker": _filament_picker,
    "statusbar": lambda window: window.statusBar(),
    "report.action": _report_action,
    "report.slicer": _report_slicer,
    "selection.parts": _selection_parts,
    "start.drop": _drop_area,
    "dialog": _open_dialog,
    "dialog.accept": _accept_button,
    "dialog.naming": _naming_box,
    "dialog.more": _more_flap,
    "transform.values": _transform_values,
    "parameters.first": _first_parameter,
    "toolbar.draw": _draw_button,
    "sketch.done": _sketch_done,
    "feature.apply": _marked("feature.apply"),
    "feature.in_view": _marked("feature.in_view"),
    "feature.every": _marked("feature.every"),
    "measure.reference": _marked("measure.reference"),
    "search": _search_field,
    "toolbar.search": _toolbar_search,
    "progress.cancel": _progress_cancel,
    "preview.banner": _preview_banner,
    "selection.rebuild": _rebuild_button,
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
    """Das Widget hinter einem Namen aus dem Wortschatz, auch wenn es gerade verdeckt ist.

    Feste Namen über ihre Tabellen, die neuen Arten über ihr Kennzeichen
    (:data:`guides.TARGET_PROPERTY`, :func:`marked_widgets`) oder ein
    öffentliches Attribut. Was nur einen Ort hat (Menüzeile, Listenzeile,
    Stelle im Bild), hat kein Widget: :class:`MissingTargetError`.
    """
    if not guides.is_target(name):
        raise MissingTargetError(f"{name}: kein Name aus dem Wortschatz der Anleitungen")
    if name in _AREAS:
        return getattr(window, _AREAS[name])  # type: ignore[no-any-return]
    if name in _START:
        return _start(window, _START[name])
    if name in _PRINT:
        return getattr(_print_dialog(), _PRINT[name])  # type: ignore[no-any-return]
    finder = _FINDERS.get(name)
    if finder is not None:
        return finder(window)
    kind, _separator, rest = name.partition(":")
    if kind == "operation":
        button = window.selection_operations.button_for(rest)
        if button is not None and button.isVisible():
            return button
    if kind in _MARKED_KINDS:
        return _marked(name)(window)
    if kind == "handle" and rest in _BARS:
        return _bar(window, rest)
    if kind == "dialog":
        return _dialog_of_class(window, rest)
    return _named(window, kind, rest)


def area_for(window: MainWindow, name: str) -> QRect:
    """Wo das Ziel gerade auf dem Bildschirm steht, in globalen Koordinaten.

    Nur Sichtbares hat einen Ort. Ein Menüeintrag hat ihn nur, solange sein
    Menü offen ist — das öffnet der Aufrufer. Ein Widget in einem Rollbereich
    wird vorher in den Blick gerollt, wie der Kunde es mit dem Mausrad täte:
    Im aufgeklappten Abschnitt *Ändern* stand *Verrunden* unterhalb des
    sichtbaren Teils, und ein Rahmen darum hätte ins Leere gezeigt.

    Diese Funktion **deckt auf** — Reiter, Klappen, Rollen —, denn eine Tour
    und ein Bild im Handbuch zeigen das Ziel und nicht den Weg dorthin. Wer
    die Klicks des Kunden zählt, fragt :func:`next_click`.
    """
    if name == "history.last":
        return _last_row(window.history_panel.list, name)
    if name == "viewport":
        return _open_view(window)
    kind, separator, rest = name.partition(":")
    if kind == "part":
        return _catalog_tile(rest, name)
    if separator and kind in ("history", "menu"):
        return _open_menu_entry_named(_menu_name(kind, rest), name)
    if kind in _ROW_KINDS:
        view, item = _row(window, kind, rest, name)
        _reveal(view)
        return _item_area(view, item, reveal=True)
    if kind == "view":
        return _spot(point_for(window, *_object_and_feature(rest)))
    if kind == "handle" and rest not in _BARS:
        return _spot(_grip_point(window, rest, name))
    if kind == "operation":
        # **Erst der Knopf, dann das Menü** (RM-737, B3): Die Hälfte der
        # Operationen hat gar keine Menüzeile; vorher scheiterte sie hier,
        # bevor nach ihrem Knopf gefragt war.
        button = window.selection_operations.button_for(rest)
        if button is not None and not button.isVisible():
            _reveal(button)
        if button is not None and button.isVisible():
            return _global(_in_view(button))
    if kind in ("command", "operation"):
        action = _action_for(window, kind, rest)
        shown = _shown_in_toolbar(window, action)
        if shown is not None:
            return _global(shown)
        return _open_menu_entry(action, name)
    widget = widget_for(window, name)
    # Ein Bereich des Fensters wird nicht hervorgeholt: Eine Legende über das
    # ganze Fenster zeigt für die verdeckte Seite auf ihren Reiter.
    if not widget.isVisible() and name not in _AREAS:
        _reveal(widget)
    if not widget.isVisible():
        tab = _tab_of_a_page_behind(widget)
        if tab is not None:
            return tab
        raise MissingTargetError(f"{name}: {type(widget).__name__} ist gerade nicht zu sehen")
    if isinstance(widget, RowCheckBox):
        return _checkbox_area(_in_view(widget))
    return _global(_in_view(widget))


def _checkbox_area(box: QWidget) -> QRect:
    """Beschriftung und Kästchen eines Hakens in einer Formularzeile.

    Der Haken füllt die ganze Feldspalte (``labels.RowCheckBox``), gezeichnet
    wird nur sein Quadrat am linken Rand. Ein Rahmen um das Widget umschloss
    ein leeres Feld, und die Beschriftung stand außerhalb (*Maße als Parameter
    anlegen*, *Oben öffnen*; Durchsicht 28.09.2026).
    """
    square = QRect(box.mapToGlobal(QPoint(0, 0)), QSize(box.height(), box.height()))
    for form in box.window().findChildren(QFormLayout):
        caption = form.labelForField(box)
        if caption is not None and caption.isVisible():
            return square.united(_global(caption))
    return square


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


#: Was vor einem verdeckten Ziel liegt: ein Reiter, dessen Seite nicht vorn ist,
#: oder eine zugeklappte Klappe.
ObstacleKind = Literal["reiter", "klappe"]

#: Die Kopfzeilen, die einen Inhalt auf- und zuklappen: ein Abschnitt
#: (``panels.collapsible``) und eine Handlung im Merkmalfenster (RM-510).
_HEADINGS: Final = frozenset({"sectionHeading", "actionHeading"})


@dataclass(frozen=True, slots=True)
class _Obstacle:
    """Ein Hindernis auf dem Weg zum Ziel und der Klick, der es wegnimmt."""

    why: ObstacleKind
    clicked: QWidget
    """Die Reiterleiste oder die Kopfzeile der Klappe."""
    index: int = -1
    """Bei einem Reiter seine Stelle in der Leiste."""

    def rect(self) -> QRect:
        if isinstance(self.clicked, QTabBar):
            place = self.clicked.tabRect(self.index)
            return QRect(self.clicked.mapToGlobal(place.topLeft()), place.size())
        return _global(self.clicked)

    def remove(self) -> None:
        """Nimmt das Hindernis weg, wie der Klick es täte — nur für :func:`_reveal`."""
        if isinstance(self.clicked, QTabBar):
            self.clicked.setCurrentIndex(self.index)
        elif isinstance(self.clicked, QAbstractButton) and not self.clicked.isChecked():
            self.clicked.setChecked(True)


def _obstacles(widget: QWidget) -> list[_Obstacle]:
    """Was zwischen dem Kunden und diesem Widget liegt, von außen nach innen.

    **Die eine Antwort für zwei Fragen** (RM-737, B2): :func:`_reveal` nimmt
    die Hindernisse weg, :func:`next_click` nennt das erste als Klick. Gefragt
    wird an jedem Vorfahren: Steckt er in einem Reiter, dessen Seite nicht vorn
    ist, oder ist er verborgen, und neben ihm steht eine zugeklappte Kopfzeile?
    Ein Reiter ohne sichtbare Leiste ist kein Weg, den ein Kunde gehen kann;
    er steht nicht in der Liste.
    """
    found: list[_Obstacle] = []
    child = widget
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QTabWidget):
            index = next(
                (
                    number
                    for number in range(parent.count())
                    if (page := parent.widget(number)) is not None
                    and (page is widget or page.isAncestorOf(widget))
                ),
                -1,
            )
            bar = parent.tabBar()
            if index >= 0 and index != parent.currentIndex() and not bar.isHidden():
                found.append(_Obstacle("reiter", bar, index))
        elif child.isHidden():
            heading = next(
                (
                    candidate
                    for candidate in parent.children()
                    if isinstance(candidate, QToolButton)
                    and candidate is not child
                    and candidate.objectName() in _HEADINGS
                ),
                None,
            )
            if heading is None and isinstance(parent.property("heading"), QToolButton):
                heading = parent.property("heading")
            if heading is not None and not heading.isChecked():
                found.append(_Obstacle("klappe", heading))
        child, parent = parent, parent.parentWidget()
    found.reverse()
    return found


def _reveal(widget: QWidget) -> None:
    """Holt ein verdecktes Ziel hervor, wie der Kunde es täte.

    Er klickt auf den Reiter, auf dessen Seite es steht, und klappt die Gruppe
    auf, in der es liegt: Die Karte der Handlungen klappt Gruppen zu, sobald
    mehr als ``OPEN_UP_TO`` Knöpfe offen stünden, und seit RM-511 steht vorn
    nicht immer die Auswahl. Die Hindernisse sind dieselben, die
    :func:`next_click` als Klicks nennt (:func:`_obstacles`).
    """
    for obstacle in _obstacles(widget):
        obstacle.remove()
    QApplication.processEvents()


def _tab_of_a_page_behind(widget: QWidget) -> QRect | None:
    """Der Reiter, hinter dem das Ziel steht, wenn seine Seite nicht vorn ist.

    Seit RM-511 teilen sich Auswahl, Prüfbericht und Chat die rechte Karte,
    und vorn steht immer nur eine Seite. Eine Legende über das ganze Fenster
    nennt sie trotzdem einzeln; für die verdeckte zeigt die Nummer auf ihren
    Reiter, dorthin klickt der Kunde.
    """
    tab = next((obstacle for obstacle in _obstacles(widget) if obstacle.why == "reiter"), None)
    if tab is None or not tab.clicked.isVisible():
        return None
    return tab.rect()


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
    # **Die Lücke zwischen den Karten, wo sie auch stehen** — seit sie sich
    # verschieben lassen, liegt die Auswahl womöglich links (``free_span``,
    # dieselbe Rechnung, mit der die Ansicht ihnen ausweicht).
    host = window.overlay
    cards = [
        zone.geometry() for zone in (host.left, host.right) if zone is not None and zone.isVisible()
    ]
    covered_left, covered_right = free_span(host.width(), cards)
    origin = host.mapToGlobal(QPoint(0, 0))
    if covered_left:
        left = max(left, origin.x() + covered_left - MARGIN + gap)
    if covered_right:
        right = min(right, origin.x() + host.width() - covered_right + MARGIN - 1 - gap)
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
    for name, _menus, action in menubar_entries(window):
        if name == rest or action.text() == title:
            return action
    raise MissingTargetError(f"command:{rest}: „{title}“ steht in keinem Menü")


#: Eine Zeile eines Menüs: ihr ``objectName``, die Titel der Menüs darüber
#: (von außen nach innen) und die Aktion selbst.
MenuEntry = tuple[str, tuple[str, ...], QAction]


def menu_entries(menu: QWidget, menus: tuple[str, ...] = ()) -> Iterator[MenuEntry]:
    """Jede anklickbare Zeile eines Menüs oder der Leiste, Untermenüs eingeschlossen.

    Trennstriche und Überschriften fallen weg (``style.menu_heading`` ist ein
    Trennstrich mit Text), ein Untermenü liefert seine Kinder statt sich selbst
    und gibt ihnen seinen Titel in den Weg mit.
    """
    for action in menu.actions():
        if action.isSeparator():
            continue
        sub = action.menu()
        if isinstance(sub, QMenu):
            yield from menu_entries(sub, (*menus, action.text()))
            continue
        yield action.objectName(), menus, action


def menubar_entries(window: MainWindow) -> list[MenuEntry]:
    """Jede Zeile der Menüleiste mit Namen und Weg — die eine Lesart der Leiste.

    Suche (``MainWindow._menu_commands``), Wortschatz (``menu:``) und
    Funktionsliste lesen sie hier. Der Name ist der ``objectName`` aus der
    unübersetzten Quelle (:func:`guides.menubar_name`), der Weg die Titel der
    Menüs darüber in der Anzeigesprache.
    """
    return list(menu_entries(window.menuBar()))


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


# --- Die neuen Arten (RM-737) --------------------------------------------------

#: Arten, deren Widget sein Ziel als Kennzeichen trägt (``guides.TARGET_PROPERTY``).
_MARKED_KINDS: Final = frozenset(
    {
        "field",
        "feature",
        "edge",
        "feature.field",
        "measure.field",
        "finding.action",
        "print",
        "setting",
    }
)

#: Arten, deren Ziel eine Zeile in einer Liste oder einem Baum ist.
_ROW_KINDS: Final = frozenset({"tree.row", "history.row", "finding", "start.recent"})

#: Die Leisten über der Ansicht, als ``handle:<rolle>``.
_BARS: Final = frozenset(
    {
        "bar.section",
        "bar.split",
        "bar.analysis",
        "bar.explode",
        "bar.sculpt",
        "bar.pose",
        "bar.draw",
    }
)

#: Die Griffe im Bild: Rolle → Name des Bildelements, das der Renderer führt
#: (``render.gizmo``, ``scale_widget``, ``slot_handle``).
_GRIPS: Final[dict[str, str]] = {
    "move.x": "gizmo:arrow:0",
    "move.y": "gizmo:arrow:1",
    "move.z": "gizmo:arrow:2",
    "rotate.x": "gizmo:ring:0",
    "rotate.y": "gizmo:ring:1",
    "rotate.z": "gizmo:ring:2",
    "scale": "scale-handle",
    "slot.end": "slot-handle:knob:0",
}

#: Griffe, die am Ursprung des Bewegungsgriffs gefasst werden: an einem
#: gewählten Merkmal und am Dach eines Bausteins.
_GRIP_ORIGINS: Final = frozenset({"feature.grip", "part.grip"})

#: Was diese Datei an Arten auflöst — ``tests/test_guides.py`` hält es gegen
#: ``guides.TARGET_KINDS``.
RESOLVED_KINDS: Final[frozenset[str]] = frozenset(
    {
        "command",
        "operation",
        "field",
        "part",
        "tool",
        "transform",
        "section",
        "sketch",
        "history",
        "feature",
        "edge",
        "feature.field",
        "measure.field",
        "menu",
        "finding",
        "finding.action",
        "print",
        "setting",
        "handle",
        "tree.row",
        "history.row",
        "view",
        "dialog",
        "start.recent",
    }
)

#: Wie viele Dreiecke :func:`point_for` probiert, bevor es aufgibt.
_POINT_TRIES: Final = 48


def _menu_name(kind: str, rest: str) -> str:
    """``history:edit`` ist ``menu:history.edit`` — der Name der Anleitungen bleibt."""
    return f"history.{rest}" if kind == "history" else rest


def _bar(window: MainWindow, role: str) -> QWidget:
    """Eine Leiste über der Ansicht; sie steht nur, solange ihr Werkzeug offen ist."""
    bars: dict[str, QWidget] = {
        "bar.section": window.section_bar,
        "bar.split": window.split_bar,
        "bar.analysis": window.analysis_bar,
        "bar.explode": window.explode_bar,
        "bar.sculpt": window.sculpt_bar,
        "bar.pose": window.pose_bar,
        "bar.draw": window.draw_bar,
    }
    return bars[role]


def _dialog_of_class(window: MainWindow, name: str) -> QWidget:
    """Das offene Fenster dieser Klasse — ``dialog:print_settings_dialog``."""
    candidates = [*QApplication.topLevelWidgets(), *window.findChildren(QDialog)]
    for candidate in candidates:
        if (
            candidate.isWindow()
            and candidate.isVisible()
            and guides.dialog_name(type(candidate).__name__) == name
        ):
            return candidate
    raise MissingTargetError(f"dialog:{name}: kein Fenster dieser Klasse ist offen")


def _object_and_feature(rest: str) -> tuple[str, str | None]:
    """``obj_1.op5.pin_1`` ist Körper ``obj_1`` mit Merkmal ``op5.pin_1``."""
    object_id, separator, feature_id = rest.partition(".")
    return object_id, feature_id if separator else None


def _spot(point: QPoint) -> QRect:
    """Eine Stelle als kleines Rechteck um den Punkt."""
    return QRect(point.x() - 2, point.y() - 2, 5, 5)


def _row(
    window: MainWindow, kind: str, rest: str, name: str
) -> tuple[QAbstractItemView, QTreeWidgetItem | QListWidgetItem]:
    """Die Liste oder der Baum und die Zeile, die ``name`` meint."""
    if kind == "tree.row":
        tree = window.object_tree.tree
        object_id, feature_id = _object_and_feature(rest)
        iterator = QTreeWidgetItemIterator(tree)
        while (item := iterator.value()) is not None:
            if item.data(0, Qt.ItemDataRole.UserRole) == object_id and (
                (feature_id is None and item.parent() is None)
                or (feature_id is not None and item.data(1, Qt.ItemDataRole.UserRole) == feature_id)
            ):
                return tree, item
            iterator += 1
        raise MissingTargetError(f"{name}: der Baum zeigt keine solche Zeile")
    if kind == "history.row":
        from app.ui.labels import step_number

        listing = window.history_panel.list
        document = window.session.project.document
        number = int(rest)
        for row in range(listing.count()):
            entry = listing.item(row)
            op_id = entry.data(Qt.ItemDataRole.UserRole) if entry is not None else None
            if entry is not None and op_id is not None and step_number(document, op_id) == number:
                return listing, entry
        raise MissingTargetError(f"{name}: der Verlauf hat keinen Schritt mit dieser Nummer")
    if kind == "start.recent":
        recent = window.start_screen.recent_list
        entry = recent.item(int(rest) - 1)
        if entry is None:
            raise MissingTargetError(f"{name}: „Zuletzt geöffnet“ hat so viele Einträge nicht")
        return recent, entry
    report = window.report.list
    for row in range(report.count()):
        entry = report.item(row)
        finding = entry.data(Qt.ItemDataRole.UserRole) if entry is not None else None
        if entry is not None and not entry.isHidden() and getattr(finding, "code", None) == rest:
            return report, entry
    raise MissingTargetError(f"{name}: der Prüfbericht zeigt keinen Befund mit dieser Kennung")


def _item_rect(view: QAbstractItemView, item: QTreeWidgetItem | QListWidgetItem) -> QRect:
    """Die Zeile in Koordinaten ihrer Sichtfläche — leer, wenn sie gerade keine hat."""
    if isinstance(view, QTreeWidget) and isinstance(item, QTreeWidgetItem):
        return view.visualItemRect(item)
    if isinstance(view, QListWidget) and isinstance(item, QListWidgetItem):
        return view.visualItemRect(item)
    return QRect()


def _item_area(
    view: QAbstractItemView, item: QTreeWidgetItem | QListWidgetItem, *, reveal: bool
) -> QRect:
    """Wo die Zeile steht, global; mit ``reveal`` vorher auf- und in den Blick gerollt."""
    if reveal:
        if isinstance(view, QTreeWidget) and isinstance(item, QTreeWidgetItem):
            parent = item.parent()
            while parent is not None:
                parent.setExpanded(True)
                parent = parent.parent()
            view.scrollToItem(item)
        elif isinstance(view, QListWidget) and isinstance(item, QListWidgetItem):
            view.scrollToItem(item)
    rect = _item_rect(view, item)
    if rect.isEmpty():
        raise MissingTargetError("die Zeile steht gerade nicht im Bild")
    return QRect(view.viewport().mapToGlobal(rect.topLeft()), rect.size())


def point_of_world(window: MainWindow, world: Sequence[float]) -> QPoint | None:
    """Ein Weltpunkt als globaler Bildschirmpunkt — ``None`` ohne Bild.

    Über :meth:`Viewport.display_of`, das in Gerätepixeln antwortet; der Faktor
    zum Qt-Logikpunkt kommt vom Renderer. Dieselbe Rechnung für Wortschatz,
    Prüfstand und Videos (``tools/make_video.py``).
    """
    viewport = window.viewport
    renderer = viewport.renderer
    display = viewport.display_of(world)
    if renderer is None or display is None:
        return None
    surface = renderer.widget if isinstance(renderer.widget, QWidget) else viewport
    ratio = float(renderer.device_ratio()) or 1.0
    return surface.mapToGlobal(QPoint(round(display[0] / ratio), round(display[1] / ratio)))


def _shows_the_view(window: MainWindow, point: QPoint) -> bool:
    """Ob an dieser Stelle die Ansicht selbst liegt — keine Karte, kein Feld darüber."""
    under = widget_under(point)
    renderer = window.viewport.renderer
    surface = renderer.widget if renderer is not None else None
    return under is not None and (under is window.viewport or under is surface)


def point_for(window: MainWindow, object_id: str, feature_id: str | None = None) -> QPoint:
    """Eine Stelle im Bild, an der ein Klick diesen Körper oder dieses Merkmal trifft.

    Eine der Kamera zugewandte Stelle **auf den Dreiecken** des Merkmals — die
    Mitte eines Durchgangslochs ist leer, die Achse kein Ziel. Probiert werden
    die größten zugewandten Dreiecke; eines gilt, wenn an seiner Mitte die
    Ansicht selbst liegt (:func:`widget_under`) und ihr Pick dasselbe
    Dreieck, mindestens denselben Körper meldet (``Viewport.placement_hit``).
    """
    import numpy as np

    from app.core.geom.mesh import as_mesh_data

    name = f"view:{object_id}" + (f".{feature_id}" if feature_id else "")
    viewport = window.viewport
    result = window.session.last_result
    entry = result.scene.objects.get(object_id) if result is not None else None
    if viewport.renderer is None or entry is None:
        raise MissingTargetError(f"{name}: die Ansicht zeigt diesen Körper nicht")
    raw = as_mesh_data(entry.mesh).raw
    faces = np.arange(len(raw.faces))
    if feature_id is not None:
        feature = entry.features.get(feature_id)
        if feature is None or not feature.face_indices:
            raise MissingTargetError(f"{name}: kein Merkmal dieses Namens mit Dreiecken")
        faces = np.asarray(feature.face_indices, dtype=int)
    facing = faces[raw.face_normals[faces] @ np.asarray(viewport.view_direction()) < 0.0]
    order = facing[np.argsort(-raw.area_faces[facing], kind="stable")][:_POINT_TRIES]
    wanted = {int(face) for face in faces}
    for face in order:
        centre = tuple(float(value) for value in raw.triangles_center[face])
        point = point_of_world(window, centre)
        display = viewport.display_of(centre)
        if point is None or display is None or not _shows_the_view(window, point):
            continue
        hit = viewport.placement_hit(int(display[0]), int(display[1]))
        if hit is None or hit[0] != object_id:
            continue
        if feature_id is not None and hit[2] >= 0 and hit[2] not in wanted:
            continue
        return point
    raise MissingTargetError(f"{name}: keine zugewandte Stelle, die ein Klick trifft")


def _grip_point(window: MainWindow, role: str, name: str) -> QPoint:
    """Eine Stelle auf einem Griff im Bild.

    Wo der Griff sitzt und wie weit er greift, sagt ``Viewport.gizmo_reach``;
    welcher Teil wo liegt, sagt der Renderer, der die Teile unter ihrem Namen
    führt (``gizmo:arrow:0``). Gesucht wird zuerst entlang der Weltachsen und
    auf den Kreisen um sie, dann auf einem Raster um den Ursprung.
    """
    import math

    viewport = window.viewport
    renderer = viewport.renderer
    reach = viewport.gizmo_reach()
    if renderer is None or reach is None:
        raise MissingTargetError(f"{name}: im Bild steht kein Griff")
    origin, radius = reach
    if role in _GRIP_ORIGINS:
        point = point_of_world(window, origin)
        if viewport.gizmo_feature() is None or point is None:
            raise MissingTargetError(f"{name}: der Griff hängt an keinem Merkmal")
        return point
    wanted = _GRIPS.get(role)
    centre = viewport.display_of(origin)
    if wanted is None or centre is None:
        raise MissingTargetError(f"{name}: keine Rolle eines Griffs im Bild")
    axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    worlds: list[tuple[float, float, float]] = []
    for index, axis in enumerate(axes):
        worlds.extend(
            (
                origin[0] + axis[0] * radius * share,
                origin[1] + axis[1] * radius * share,
                origin[2] + axis[2] * radius * share,
            )
            for share in (0.25, 0.35, 0.45, 0.55, 0.65)
        )
        first, second = axes[(index + 1) % 3], axes[(index + 2) % 3]
        worlds.extend(
            (
                origin[0] + radius * (math.cos(turn) * first[0] + math.sin(turn) * second[0]),
                origin[1] + radius * (math.cos(turn) * first[1] + math.sin(turn) * second[1]),
                origin[2] + radius * (math.cos(turn) * first[2] + math.sin(turn) * second[2]),
            )
            for turn in (step * math.pi / 8 for step in range(16))
        )
    projected = [viewport.display_of(world) for world in worlds]
    probes = [spot for spot in projected if spot is not None]
    span = max((math.dist(spot, centre) for spot in probes), default=0.0) * 1.1
    probes.extend(
        (
            centre[0] + span * ring / 12 * math.cos(turn),
            centre[1] + span * ring / 12 * math.sin(turn),
        )
        for ring in range(1, 13)
        for turn in (step * math.pi / 24 for step in range(48))
    )
    hits = [spot for spot in probes if getattr(renderer.pick_item(*spot), "name", None) == wanted]
    if not hits:
        raise MissingTargetError(f"{name}: der Griff steht nicht im Bild")
    x, y = hits[len(hits) // 2]
    surface = renderer.widget if isinstance(renderer.widget, QWidget) else viewport
    ratio = float(renderer.device_ratio()) or 1.0
    point = surface.mapToGlobal(QPoint(round(x / ratio), round(y / ratio)))
    if not _shows_the_view(window, point):
        raise MissingTargetError(f"{name}: über dem Griff liegt ein Bedienelement")
    return point


def widget_under(point: QPoint) -> QWidget | None:
    """Was an dieser Bildschirmstelle einen Klick bekäme — die Probe vor jedem Klick.

    Zuerst ein offenes Menü und ein modaler Dialog, dann ``QApplication.widgetAt``;
    findet das nichts (ohne Fenstersystem), das oberste Fenster, das die Stelle
    enthält, und darin ``childAt``.
    """
    tops: list[QWidget | None] = [
        QApplication.activePopupWidget(),
        QApplication.activeModalWidget(),
    ]
    for top in tops:
        if top is not None and top.isVisible() and top.rect().contains(top.mapFromGlobal(point)):
            return top.childAt(top.mapFromGlobal(point)) or top
    found = QApplication.widgetAt(point)
    if found is not None:
        return found
    windows = [top for top in QApplication.topLevelWidgets() if top.isWindow() and top.isVisible()]
    # Ein Fenster mit Elternteil (Dialog, Karte) liegt über dem Hauptfenster.
    windows.sort(key=lambda top: top.parentWidget() is None)
    for top in windows:
        local = top.mapFromGlobal(point)
        if top.rect().contains(local):
            return top.childAt(local) or top
    return None


#: Die Zonen des Fensters, in denen ein Bedienelement steht (Kriterium E4).
Zone = Literal["ansicht", "karte_rechts", "karte_links", "dialog", "statusleiste", "kopf", "menue"]


def zone_of(window: MainWindow, widget: QWidget) -> Zone:
    """In welcher Zone des Fensters dieses Widget steht."""
    probe: QWidget | None = widget
    while probe is not None:
        if isinstance(probe, QMenu):
            return "menue"
        probe = probe.parentWidget()
    if widget.window() is not window:
        return "dialog"

    def inside(container: QWidget | None) -> bool:
        return container is not None and (container is widget or container.isAncestorOf(widget))

    if inside(window.menuBar()):
        return "menue"
    if inside(window.statusBar()):
        return "statusleiste"
    host = window.overlay
    if inside(host.right):
        return "karte_rechts"
    if inside(host.left):
        return "karte_links"
    if inside(window.viewport) or inside(host):
        return "ansicht"
    return "kopf"


def search_hits(window: MainWindow) -> list[str]:
    """Die Treffer der Suche, wie sie dastehen — als Namen aus dem Wortschatz.

    Eine Operation heißt ``operation:<name>``, ein Befehl des Fensters
    ``command:<kennung>``; die Überschrift über losen Treffern hat keinen Namen
    und fehlt. Ohne Suchtext ist die Liste leer.
    """
    from app.core.registry import REGISTRY

    hits = window.selection_operations.hits
    if not hits.isVisible():
        return []
    found: list[str] = []
    for row in range(hits.count()):
        item = hits.item(row)
        named = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if item is None or item.isHidden() or not named:
            continue
        found.append(f"operation:{named}" if REGISTRY.has(str(named)) else f"command:{named}")
    return found


def _hit_row(window: MainWindow, entry: str) -> QListWidgetItem | None:
    """Die Zeile dieser Operation oder dieses Befehls in der sichtbaren Trefferliste."""
    hits = window.selection_operations.hits
    if not hits.isVisible():
        return None
    for row in range(hits.count()):
        item = hits.item(row)
        if (
            item is not None
            and not item.isHidden()
            and item.data(Qt.ItemDataRole.UserRole) == entry
        ):
            return item
    return None


# --- Der nächste Klick ------------------------------------------------------------

#: Warum ein Klick fällig ist: das Ziel selbst oder ein Schritt auf dem Weg dorthin.
ClickReason = Literal["ziel", "reiter", "klappe", "menue", "untermenue", "aufklappen", "rollen"]


@dataclass(frozen=True, slots=True)
class Click:
    """Der nächste Klick des Kunden auf dem Weg zu einem Ziel (:func:`next_click`).

    ``rect`` ist global. Bei ``rollen`` ist es die Fläche, über der das Rad
    dreht, ``button`` ist dann ``NoButton`` und ``direction`` sagt, wohin:
    ``1`` weiter nach unten, ``-1`` nach oben.
    """

    rect: QRect
    button: Qt.MouseButton
    why: ClickReason
    target: str
    direction: int = 0


def next_click(window: MainWindow, name: str) -> Click:
    """Der nächste Klick auf dem Weg des Kunden zu ``name`` — **ohne etwas aufzudecken**.

    Steht das Ziel da, ist es das Ziel (``ziel``). Sonst ist es der erste
    Schritt dorthin: der Reiter, die Klappe, der Menütitel, das Untermenü, das
    Aufklappen einer Zeile oder das Rollen. Was dieselbe Frage für Touren
    beantwortet und dabei aufdeckt, ist :func:`area_for`; beide lesen die
    Hindernisse aus :func:`_obstacles`. Ist kein Weg zu sehen — ein
    geschlossenes Kontextmenü, ein Dialog, der nicht offen ist —, ist das ein
    :class:`MissingTargetError`; der Aufrufer geht dann einen Weg, den er
    selbst kennt.
    """
    if not guides.is_target(name):
        raise MissingTargetError(f"{name}: kein Name aus dem Wortschatz der Anleitungen")
    if name == "history.last":
        listing = window.history_panel.list
        last = next(
            (
                item
                for row in range(listing.count() - 1, -1, -1)
                if (item := listing.item(row)) is not None and not item.isHidden()
            ),
            None,
        )
        if last is None:
            raise MissingTargetError(f"{name}: die Liste ist leer")
        return _row_click(listing, last, name)
    if name == "viewport":
        return Click(_open_view(window), Qt.MouseButton.LeftButton, "ziel", name)
    kind, separator, rest = name.partition(":")
    if separator and kind in ("history", "menu"):
        action = _menu_action_named(window, _menu_name(kind, rest))
        if action is None:
            raise MissingTargetError(f"{name}: kein offenes Menü und keine Leiste trägt die Zeile")
        return _menu_click(window, action, name)
    if kind == "command":
        hit = _hit_row(window, rest)
        if hit is not None:
            return _visible_row_click(window.selection_operations.hits, hit, name, "ziel")
        if rest.startswith("tool."):
            return next_click(window, f"tool:{rest.removeprefix('tool.')}")
        action = _action_for(window, kind, rest)
        shown = _shown_in_toolbar(window, action)
        if shown is not None:
            return Click(_global(shown), Qt.MouseButton.LeftButton, "ziel", name)
        return _menu_click(window, action, name)
    if kind == "operation":
        return _operation_click(window, rest, name)
    if kind == "part":
        return _tile_click(rest, name)
    if kind in _ROW_KINDS:
        view, row_item = _row(window, kind, rest, name)
        obstacles = _obstacles(view)
        if obstacles:
            return _obstacle_click(obstacles[0], name)
        return _row_click(view, row_item, name)
    if kind == "view":
        point = point_for(window, *_object_and_feature(rest))
        return Click(_spot(point), Qt.MouseButton.LeftButton, "ziel", name)
    if kind == "handle" and rest not in _BARS:
        return Click(
            _spot(_grip_point(window, rest, name)), Qt.MouseButton.LeftButton, "ziel", name
        )
    widget = widget_for(window, name)
    button = (
        Qt.MouseButton.RightButton if name == "measure.reference" else Qt.MouseButton.LeftButton
    )
    return _widget_click(widget, name, button)


def _obstacle_click(obstacle: _Obstacle, name: str) -> Click:
    """Der Klick, der das erste Hindernis wegnimmt — wenn der Kunde es sehen kann."""
    if not obstacle.clicked.isVisible():
        raise MissingTargetError(f"{name}: der Weg führt über etwas, das gerade nicht dasteht")
    return Click(obstacle.rect(), Qt.MouseButton.LeftButton, obstacle.why, name)


def _widget_click(widget: QWidget, name: str, button: Qt.MouseButton) -> Click:
    """Der Klick auf ein Widget — oder der erste Schritt, der es hervorholt."""
    obstacles = _obstacles(widget)
    if obstacles:
        return _obstacle_click(obstacles[0], name)
    if not widget.isVisible():
        raise MissingTargetError(
            f"{name}: {type(widget).__name__} steht nicht da, und kein Weg führt hin"
        )
    scrolled = _scroll_needed(widget, name)
    if scrolled is not None:
        return scrolled
    rect = _checkbox_area(widget) if isinstance(widget, RowCheckBox) else _global(widget)
    return Click(rect, button, "ziel", name)


def _scroll_needed(widget: QWidget, name: str) -> Click | None:
    """Ob das Widget außerhalb des sichtbaren Teils seines Rollbereichs steht."""
    parent = widget.parentWidget()
    while parent is not None and not isinstance(parent, QScrollArea):
        parent = parent.parentWidget()
    if parent is None:
        return None
    viewport = parent.viewport()
    centre = widget.mapTo(viewport, widget.rect().center())
    if viewport.rect().contains(centre):
        return None
    direction = 1 if centre.y() >= viewport.height() else -1
    return Click(_global(viewport), Qt.MouseButton.NoButton, "rollen", name, direction)


def _row_click(
    view: QAbstractItemView, item: QTreeWidgetItem | QListWidgetItem, name: str
) -> Click:
    """Der Klick auf eine Zeile — oder das Aufklappen und Rollen davor."""
    if not view.isVisible():
        raise MissingTargetError(f"{name}: die Liste steht gerade nicht da")
    if isinstance(item, QTreeWidgetItem):
        ancestors: list[QTreeWidgetItem] = []
        parent = item.parent()
        while parent is not None:
            ancestors.append(parent)
            parent = parent.parent()
        for ancestor in reversed(ancestors):
            if not ancestor.isExpanded():
                return _expander_click(view, ancestor, name)
    elif isinstance(item, QListWidgetItem) and item.isHidden():
        from app.ui.panels import GROUP_ROLE

        group = item.data(GROUP_ROLE)
        listing = item.listWidget()
        header = next(
            (
                candidate
                for row in range(listing.count() if listing is not None else 0)
                if listing is not None
                and (candidate := listing.item(row)) is not None
                and not candidate.isHidden()
                and candidate.data(GROUP_ROLE) == group
            ),
            None,
        )
        if group is None or header is None:
            raise MissingTargetError(
                f"{name}: die Zeile ist verborgen, und keine Gruppe klappt sie auf"
            )
        return _visible_row_click(view, header, name, "aufklappen")
    return _visible_row_click(view, item, name, "ziel")


def _visible_row_click(
    view: QAbstractItemView,
    item: QTreeWidgetItem | QListWidgetItem,
    name: str,
    why: ClickReason,
) -> Click:
    rect = _item_rect(view, item)
    surface = view.viewport()
    if rect.isEmpty():
        raise MissingTargetError(f"{name}: die Zeile hat gerade keinen Ort")
    if not surface.rect().contains(rect.center()):
        direction = 1 if rect.center().y() >= surface.height() else -1
        return Click(_global(surface), Qt.MouseButton.NoButton, "rollen", name, direction)
    return Click(
        QRect(surface.mapToGlobal(rect.topLeft()), rect.size()),
        Qt.MouseButton.LeftButton,
        why,
        name,
    )


def _expander_click(view: QAbstractItemView, item: QTreeWidgetItem, name: str) -> Click:
    """Das Dreieck vor einer zugeklappten Baumzeile."""
    assert isinstance(view, QTreeWidget)
    rect = view.visualItemRect(item)
    surface = view.viewport()
    if rect.isEmpty() or not surface.rect().contains(rect.center()):
        direction = 1 if rect.center().y() >= surface.height() else -1
        return Click(_global(surface), Qt.MouseButton.NoButton, "rollen", name, direction)
    indent = view.indentation()
    arrow = QRect(rect.left() - indent, rect.top(), indent, rect.height())
    return Click(
        QRect(surface.mapToGlobal(arrow.topLeft()), arrow.size()),
        Qt.MouseButton.LeftButton,
        "aufklappen",
        name,
    )


def _tile_click(part: str, name: str) -> Click:
    """Die Kachel eines Bausteins im offenen Katalog, ohne zu rollen."""
    from app.ui.catalog import PartCatalog

    catalog = QApplication.activeModalWidget()
    if not isinstance(catalog, PartCatalog):
        raise MissingTargetError(f"{name}: der Bausteinkatalog ist nicht offen")
    view = catalog.list
    for row in range(view.count()):
        item = view.item(row)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == part:
            return _visible_row_click(view, item, name, "ziel")
    raise MissingTargetError(f"{name}: der Katalog zeigt keinen Baustein dieses Namens")


def _operation_click(window: MainWindow, operation: str, name: str) -> Click:
    """Eine Operation: ihr Treffer in der Suche, ihr Knopf, sonst ihre Menüzeile (B3)."""
    hit = _hit_row(window, operation)
    if hit is not None:
        return _visible_row_click(window.selection_operations.hits, hit, name, "ziel")
    button = window.selection_operations.button_for(operation)
    if button is not None:
        obstacles = _obstacles(button)
        if obstacles:
            return _obstacle_click(obstacles[0], name)
        if button.isVisible():
            return _widget_click(button, name, Qt.MouseButton.LeftButton)
    try:
        action = _action_for(window, "operation", operation)
    except MissingTargetError:
        raise MissingTargetError(f"{name}: weder ein Knopf noch eine Menüzeile steht da") from None
    shown = _shown_in_toolbar(window, action)
    if shown is not None:
        return Click(_global(shown), Qt.MouseButton.LeftButton, "ziel", name)
    return _menu_click(window, action, name)


def _open_menus() -> list[QMenu]:
    return [
        widget
        for widget in QApplication.topLevelWidgets()
        if isinstance(widget, QMenu) and widget.isVisible()
    ]


def _menu_action_named(window: MainWindow, object_name: str) -> QAction | None:
    """Die Aktion mit diesem ``objectName``: in einem offenen Menü, in der Leiste,
    oder der Titel eines benannten Menüs der Leiste."""
    for menu in _open_menus():
        for action in menu.actions():
            if action.objectName() == object_name:
                return action
    for entry_name, _menus, action in menubar_entries(window):
        if entry_name == object_name:
            return action
    for menu in window.findChildren(QMenu):
        if menu.objectName() == object_name:
            return menu.menuAction()
    return None


def _menubar_chain(container: QWidget, action: QAction, path: list[QMenu]) -> list[QMenu] | None:
    """Die Menüs von der Leiste bis zu dem, das ``action`` trägt — ``None`` außerhalb."""
    for entry in container.actions():
        if entry is action:
            return path
        sub = entry.menu()
        if isinstance(sub, QMenu):
            found = _menubar_chain(sub, action, [*path, sub])
            if found is not None:
                return found
    return None


def _menu_click(window: MainWindow, action: QAction, name: str) -> Click:
    """Die Zeile in einem offenen Menü — oder der Menütitel und die Untermenüs davor."""
    for menu in _open_menus():
        if action in menu.actions() and action.isVisible():
            place = menu.actionGeometry(action)
            return Click(
                QRect(menu.mapToGlobal(place.topLeft()), place.size()),
                Qt.MouseButton.LeftButton,
                "ziel",
                name,
            )
    bar = window.menuBar()
    chain = _menubar_chain(bar, action, [])
    if chain is None:
        raise MissingTargetError(f"{name}: das Kontextmenü ist zu — erst der Rechtsklick")
    if not chain:
        place = bar.actionGeometry(action)
        own = action.menu()
        why: ClickReason = "menue" if isinstance(own, QMenu) and not own.isVisible() else "ziel"
        return Click(
            QRect(bar.mapToGlobal(place.topLeft()), place.size()),
            Qt.MouseButton.LeftButton,
            why,
            name,
        )
    top = chain[0]
    if not top.isVisible():
        place = bar.actionGeometry(top.menuAction())
        return Click(
            QRect(bar.mapToGlobal(place.topLeft()), place.size()),
            Qt.MouseButton.LeftButton,
            "menue",
            name,
        )
    for outer, inner in itertools.pairwise(chain):
        if not inner.isVisible():
            place = outer.actionGeometry(inner.menuAction())
            return Click(
                QRect(outer.mapToGlobal(place.topLeft()), place.size()),
                Qt.MouseButton.LeftButton,
                "untermenue",
                name,
            )
    raise MissingTargetError(f"{name}: das Menü ist offen, aber die Zeile steht nicht darin")
