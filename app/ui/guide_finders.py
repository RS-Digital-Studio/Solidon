"""Finder fester Namen des Wortschatzes, die ``guide_targets`` nicht mehr fasst (FD-101).

``guide_targets`` steht an der Größengrenze der Codestruktur (Regel 6, 2 000
Zeilen); seine Tabelle ``_FINDERS`` und ``next_click`` verweisen für diese
Namen hierher.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtWidgets import QAbstractItemView, QComboBox, QWidget

    from app.ui.guide_targets import Click
    from app.ui.main_window import MainWindow

#: Die erste Spule aus dem Lager in einem Filamentfeld — ein Ort, kein Widget.
SPOOL: Final = "filament.spool"

#: Die erste Zeile mit Filament in der Liste *Filamente* der Kopfzeile — ein Ort.
PROJECT_FILAMENT: Final = "filaments.first"

#: Feste Namen, deren Widget den Namen als Kennzeichen trägt
#: (``guides.TARGET_PROPERTY``); ``guide_targets.widget_for`` sucht sie über
#: ``marked_widgets``. Ein neuer Name steht hier und am Widget, sonst nirgends.
MARKED: Final = frozenset(
    {
        "parts.save",
        "filament.add",
        "filament.profile",
        "filament.colour",
        "feature.apply",
        "feature.in_view",
        "feature.every",
        "measure.reference",
        "measure.apply",
        "donation.paypal",
        "update.page",
        "install.action",
        "install.details",
        "install.follow.comfyui",
        "install.locate",
        "filament.import",
        "usage.review",
        "tabs.bar",
        "tabs.return",
        "chat.starter",
        "chat.send",
        "disclosure.privacy",
        "activation.offline",
        "generate.prompt",
        "generate.start",
        "disclosure.continue",
    }
)


def first_parameter_label(window: MainWindow) -> QWidget:
    """Die Beschriftung der ersten Zeile unter *Parameter* (``parameters.first.label``).

    Dieselbe Zeile wie ``parameters.first``, über die Reihenfolge. Ein
    Rechtsklick auf die Beschriftung öffnet das Menü der Zeile
    (``menu:parameters.edit``); das Wertfeld trägt das Menü seines Textfelds.
    """
    from app.ui.guide_targets import MissingTargetError

    panel = window.parameters
    if not panel._editors:
        raise MissingTargetError("parameters.first.label: das Projekt hat noch keinen Parameter")
    label: QWidget = panel._titles[next(iter(panel._editors))]
    return label


def bind_button(window: MainWindow) -> QWidget:
    """*Zahlen an Maße binden …* unter den Parametern (``parameters.bind``).

    Er steht nur, solange eine feste Zahl zu einem Maß passt; aufgelöst wird er
    auch verborgen, wie jedes Widget hinter einem festen Namen.
    """
    button: QWidget = window.parameters.bind_button
    return button


def spool_list(window: MainWindow) -> tuple[QComboBox, QAbstractItemView, list[int]] | None:
    """Das sichtbare Filamentfeld mit Spulen aus dem Lager: Feld, Liste, Zeilen der Spulen.

    Gesucht wird im Fenster und in jedem offenen Fenster darüber — ein
    Operationsdialog hängt nicht immer am Hauptfenster. Eine Spule erkennt die
    Liste an ihrer zugänglichen Beschreibung (``filament_picker.spool_label``).
    Erst das Filamentfeld eines Dialogs, dann die Schnellwahl unter *Filament
    und Druck* der Auswahlkarte (``QuickFilamentPicker``, FD-175): Steht ein
    Dialog offen, meint der Weg dessen Feld.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.core.knowledge import filaments
    from app.ui.filament_assignment import QuickFilamentPicker
    from app.ui.filament_picker import FilamentField, spool_label

    labels = {spool_label(entry) for entry in filaments.catalogue()}
    roots = [window, *(top for top in QApplication.topLevelWidgets() if top is not window)]
    fields: list[QComboBox] = [
        field for root in roots for field in root.findChildren(FilamentField)
    ]
    fields += [quick.picker for root in roots for quick in root.findChildren(QuickFilamentPicker)]
    for field in fields:
        if not field.isVisible():
            continue
        role = Qt.ItemDataRole.AccessibleDescriptionRole
        rows = [row for row in range(field.count()) if field.itemData(row, role) in labels]
        if rows:
            return field, field.view(), rows
    return None


def spool_click(window: MainWindow, name: str) -> Click:
    """Der nächste Klick zu ``filament.spool``: die Liste aufklappen, dann die Spule.

    Wählt der Kunde eine Spule, für die der Körper keine freie Nummer mehr hat,
    fragt das Feld, welches Filament sie ersetzt (``message:filament_slot``).
    """
    from PySide6.QtCore import QPoint, QRect, Qt

    from app.ui.guide_targets import Click, MissingTargetError

    found = spool_list(window)
    if found is None:
        raise MissingTargetError(f"{name}: kein Filamentfeld zeigt eine Spule aus dem Lager")
    field, view, rows = found
    if not view.isVisible():
        area = QRect(field.mapToGlobal(QPoint(0, 0)), field.size())
        return Click(area, Qt.MouseButton.LeftButton, "aufklappen", name)
    place = view.visualRect(field.model().index(rows[0], field.modelColumn()))
    if place.isEmpty():
        raise MissingTargetError(f"{name}: die Zeile der Spule hat gerade keinen Ort")
    area = QRect(view.viewport().mapToGlobal(place.topLeft()), place.size())
    return Click(area, Qt.MouseButton.LeftButton, "ziel", name)


def project_filament_click(window: MainWindow, name: str) -> Click:
    """Der nächste Klick zu ``filaments.first``: erst *Filamente* in der Kopfzeile, dann die Zeile.

    Die Liste nennt die Filamente des Projekts, eine Zeile *Ohne Filament* zuletzt;
    die hat keine Druckwerte. Ein Doppelklick auf eine Zeile mit Filament öffnet
    die Druckwerte dieser Spule (``FilamentPanel._on_activated``).
    """
    from PySide6.QtCore import QPoint, QRect, Qt

    from app.ui.filament_picker import _SLOT_ROLE
    from app.ui.guide_targets import Click, MissingTargetError

    if not window.filament_popup.isVisible():
        button = window.header.filament_button
        if not button.isVisible():
            raise MissingTargetError(f"{name}: *Filamente* steht nicht in der Kopfzeile")
        area = QRect(button.mapToGlobal(QPoint(0, 0)), button.size())
        return Click(area, Qt.MouseButton.LeftButton, "aufklappen", name)
    listing = window.filaments.list
    for row in range(listing.count()):
        item = listing.item(row)
        if item is None or item.data(_SLOT_ROLE) is None:
            continue
        place = listing.visualItemRect(item)
        if place.isEmpty():
            raise MissingTargetError(f"{name}: die Zeile des Filaments hat gerade keinen Ort")
        area = QRect(listing.viewport().mapToGlobal(place.topLeft()), place.size())
        return Click(area, Qt.MouseButton.LeftButton, "ziel", name)
    raise MissingTargetError(f"{name}: kein Körper der Szene trägt ein Filament")


#: Was nur einen Ort hat und seinen Weg selbst kennt: Name → nächster Klick.
PLACE_CLICKS: Final[dict[str, Callable[[MainWindow, str], Click]]] = {
    SPOOL: spool_click,
    PROJECT_FILAMENT: project_filament_click,
}
