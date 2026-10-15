"""Finder fester Namen und Arten des Wortschatzes, die ``guide_targets`` nicht mehr fasst.

``guide_targets`` steht an der Größengrenze der Codestruktur (Regel 6, 2 000
Zeilen); seine Tabelle ``_FINDERS``, ``widget_for``, ``area_for`` und
``next_click`` verweisen für diese Namen hierher (FD-101, FD-175): Kennzeichen
am Widget (:data:`MARKED`, :data:`MARKED_KINDS`) und Orte ohne eigenes Widget,
die ihren Weg selbst kennen (:func:`place_click`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtWidgets import QAbstractItemView, QComboBox, QWidget

    from app.ui.guide_targets import Click
    from app.ui.main_window import MainWindow
    from app.ui.sketch_editor import SketchPanel

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
        "request.example",
        "request.send",
        "disclosure.privacy",
        "activation.offline",
        "generate.prompt",
        "generate.start",
        "disclosure.continue",
        "sketch.coordinates",
    }
)

#: Arten, deren Widget sein Ziel als Kennzeichen trägt (``guides.TARGET_PROPERTY``);
#: ``guide_targets.widget_for`` sucht sie über ``marked_widgets``.
MARKED_KINDS: Final = frozenset(
    {
        "field",
        "feature",
        "edge",
        "feature.field",
        "measure.field",
        "finding.action",
        "print",
        "setting",
        "message",
        "setting.section",
        "sketch.constrain",
    }
)

#: *Neue Ebene …* im Ebenenfeld des Skizzeneditors — ein Eintrag der Liste, ein Ort.
NEW_PLANE: Final = "sketch.new_plane"


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


def active_sketch_panel(window: MainWindow, name: str) -> SketchPanel:
    """Das Panel des offenen Skizzeneditors, sonst das des Zeichenmodus."""
    from PySide6.QtWidgets import QApplication

    from app.ui.guide_targets import MissingTargetError
    from app.ui.sketch_editor import SketchEditorDialog

    modal = QApplication.activeModalWidget()
    if isinstance(modal, SketchEditorDialog):
        return modal.panel
    panel: SketchPanel | None = window._sketch_panel
    if panel is None:
        raise MissingTargetError(f"{name}: kein Skizzeneditor und kein Zeichenmodus offen")
    return panel


def _number(name: str) -> int:
    """Die Zahl hinter ``art:`` als Index ab null (``sketch.point:1`` ist der erste)."""
    return int(name.partition(":")[2]) - 1


def sketch_point_click(window: MainWindow, name: str) -> Click:
    """``sketch.point:N``: der N-te Punkt der Skizze, wo er gezeichnet steht.

    Gezählt über die Punkte aller Elemente (``SketchCanvas.points``); ein Klick
    wählt ihn, mit Strg kommt er zur Auswahl dazu.
    """
    from app.ui.guide_targets import MissingTargetError

    canvas = active_sketch_panel(window, name).canvas
    points = canvas.points()
    index = _number(name)
    if not 0 <= index < len(points):
        raise MissingTargetError(f"{name}: die Skizze hat {len(points)} Punkte")
    return _plane_click(window, name, points[index])


def sketch_at_click(window: MainWindow, name: str) -> Click:
    """``sketch.at:X_Y``: die Stelle X, Y mm der Zeichenebene, an der ein Werkzeug klickt."""
    across, _sep, up = name.partition(":")[2].partition("_")
    return _plane_click(window, name, (float(across), float(up)))


def _plane_click(window: MainWindow, name: str, point: tuple[float, float]) -> Click:
    """Ein Klick auf einen Punkt der Zeichenebene, wo er gezeichnet steht.

    Im Skizzeneditor auf der Zeichenfläche; im Zeichenmodus des Fensters
    zeichnet die Ansicht, und der Punkt liegt dort, wo seine Ebene ihn in den
    Raum stellt (``planes.to_world``). Ohne Bild hat er dort keinen Ort.
    """
    from PySide6.QtCore import QRect, Qt

    from app.core.sketch.planes import frame_for_plane, to_world
    from app.ui.guide_targets import Click, MissingTargetError, point_of_world

    canvas = active_sketch_panel(window, name).canvas
    if canvas.isVisible():
        centre = canvas.mapToGlobal(canvas._to_screen(*point).toPoint())
    else:
        plane = canvas.sketch.plane
        frame = canvas.plane_frame(plane) or frame_for_plane(plane)
        spot = None if frame is None else point_of_world(window, to_world(frame, point))
        if spot is None:
            raise MissingTargetError(f"{name}: die Stelle hat in der Ansicht gerade keinen Ort")
        centre = spot
    area = QRect(centre.x() - 3, centre.y() - 3, 7, 7)
    return Click(area, Qt.MouseButton.LeftButton, "ziel", name)


def sketch_constraint_click(window: MainWindow, name: str) -> Click:
    """``sketch.constraint:<art>``: die erste Zeile der Bedingungsliste mit dieser Art.

    Die Liste zeigt, was an der Auswahl hängt (RM-519); ein Doppelklick auf eine
    Bedingung mit Wert fragt nach dem neuen Maß.
    """
    from PySide6.QtCore import QRect, Qt

    from app.ui.guide_targets import Click, MissingTargetError

    panel = active_sketch_panel(window, name)
    listing = panel.constraint_list
    kind = name.partition(":")[2]
    constraints = panel.canvas.sketch.constraints
    item = next(
        (
            listing.item(row)
            for row in range(listing.count())
            if any(
                0 <= index < len(constraints) and constraints[index].kind == kind
                for index in panel.constraint_indices(row)
            )
        ),
        None,
    )
    if item is None or not listing.isVisible():
        raise MissingTargetError(f"{name}: die Bedingungsliste zeigt keine Bedingung dieser Art")
    place = listing.visualItemRect(item)
    if place.isEmpty():
        raise MissingTargetError(f"{name}: die Zeile der Bedingung hat gerade keinen Ort")
    area = QRect(listing.viewport().mapToGlobal(place.topLeft()), place.size())
    return Click(area, Qt.MouseButton.LeftButton, "ziel", name)


def new_plane_click(window: MainWindow, name: str) -> Click:
    """``sketch.new_plane``: erst das Ebenenfeld aufklappen, dann *Neue Ebene …*."""
    from PySide6.QtCore import QPoint, QRect, Qt

    from app.ui.guide_targets import Click, MissingTargetError
    from app.ui.sketch_editor import NEW_PLANE as NEW_PLANE_DATA

    field = active_sketch_panel(window, name).plane_choice
    row = field.findData(NEW_PLANE_DATA)
    if row < 0 or not field.isVisible():
        raise MissingTargetError(f"{name}: das Ebenenfeld bietet keine neue Ebene an")
    view = field.view()
    if not view.isVisible():
        area = QRect(field.mapToGlobal(QPoint(0, 0)), field.size())
        return Click(area, Qt.MouseButton.LeftButton, "aufklappen", name)
    place = view.visualRect(field.model().index(row, field.modelColumn()))
    if place.isEmpty():
        raise MissingTargetError(f"{name}: der Eintrag hat gerade keinen Ort")
    area = QRect(view.viewport().mapToGlobal(place.topLeft()), place.size())
    return Click(area, Qt.MouseButton.LeftButton, "ziel", name)


#: Was nur einen Ort hat und seinen Weg selbst kennt: Name → nächster Klick.
PLACE_CLICKS: Final[dict[str, Callable[[MainWindow, str], Click]]] = {
    SPOOL: spool_click,
    PROJECT_FILAMENT: project_filament_click,
    NEW_PLANE: new_plane_click,
}

#: Dasselbe für Arten: ``art:name`` → nächster Klick.
PLACE_KINDS: Final[dict[str, Callable[[MainWindow, str], Click]]] = {
    "sketch.point": sketch_point_click,
    "sketch.at": sketch_at_click,
    "sketch.constraint": sketch_constraint_click,
}


def place_click(name: str) -> Callable[[MainWindow, str], Click] | None:
    """Wer den Weg zu einem Ort ohne eigenes Widget kennt — ``None`` für alles andere."""
    return PLACE_CLICKS.get(name) or PLACE_KINDS.get(name.partition(":")[0])
