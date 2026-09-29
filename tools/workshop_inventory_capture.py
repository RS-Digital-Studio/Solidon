"""Filamentlager über echte Bedienelemente aufnehmen, nur im Vorführprofil.

Die Hauptaufnahme isoliert APPDATA vor dem ersten App-Import. Dieser Helfer
prüft zusätzlich den aufgelösten Katalogpfad, bevor ein Lager gelesen oder
geändert wird. Angaben und Zuweisung bleiben als eigener Beleg beim Film.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict
from pathlib import Path
from time import monotonic
from typing import Any


def isolated_catalogue(folder: Path, roaming: Path, catalogue: Path) -> Path:
    """Nur der tatsächliche Katalog dieses Aufnahmeprofils darf verwendet werden."""
    expected = (folder / "profile" / "roaming").resolve()
    target = catalogue.resolve()
    if roaming.resolve() != expected or not target.is_relative_to(expected):
        raise RuntimeError("Filamentlager liegt außerhalb des Vorführprofils; Aufnahme anhalten.")
    return target


def _catalogue(tutorial: Any) -> Path:
    from app.core.knowledge import filaments

    roaming = os.environ.get("APPDATA")
    if not roaming:
        raise RuntimeError("APPDATA ist nicht für die Aufnahme gesetzt; Aufnahmeprofil prüfen.")
    return isolated_catalogue(tutorial.folder, Path(roaming), filaments.catalogue_path())


def _proof(tutorial: Any, phase: str, **values: Any) -> None:
    """Nur Vorführwerte und tatsächlich gespeicherte Ergebnisse festhalten."""
    path = tutorial.folder / "inventory-evidence.json"
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    entries.append({"phase": phase, **values})
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _frame(
    tutorial: Any, *, dialog: Any = None, seconds: float = 0.15, overlays: tuple[Any, ...] = ()
) -> None:
    """Einen unveränderten Zwischenzustand der tatsächlichen Eingabe festhalten."""
    picture = tutorial.recorder._capture_frame(
        "", "", dialog=dialog, overlays=overlays, settle_frames=0
    )
    tutorial.recorder._store(picture, seconds)


def _click(tutorial: Any, widget: Any, *, dialog: Any = None) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton

    point = widget.rect().center()
    if isinstance(widget, QCheckBox):
        option = QStyleOptionButton()
        widget.initStyleOption(option)
        point = (
            widget.style()
            .subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, widget)
            .center()
        )
    QTest.mouseMove(widget, point, 100)
    tutorial.recorder.click("", "", dialog=dialog, target=widget.mapToGlobal(point))
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=point, delay=100)
    tutorial.settle(8)


def _type(
    tutorial: Any,
    widget: Any,
    value: str,
    *,
    dialog: Any = None,
    commit: bool = True,
    frame_stride: int = 1,
) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QInputMethodEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QAbstractSpinBox, QApplication

    edit = widget.lineEdit() if isinstance(widget, QAbstractSpinBox) else widget
    if not edit.isVisible() or not edit.isEnabled():
        raise RuntimeError("Das echte Eingabefeld ist nicht erreichbar; Dialog prüfen.")
    _click(tutorial, edit, dialog=dialog)
    QTest.keyClick(edit, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    _frame(tutorial, dialog=dialog, seconds=0.6)
    for index, character in enumerate(value, 1):
        if ord(character) < 128:
            QTest.keyClicks(edit, character)
        else:
            event = QInputMethodEvent()
            event.setCommitString(character)
            QApplication.sendEvent(edit, event)
        tutorial.settle(2)
        if index % frame_stride == 0 or index == len(value):
            _frame(tutorial, dialog=dialog, seconds=0.3)
    if commit:
        QTest.keyClick(edit, Qt.Key.Key_Tab)
    tutorial.settle(8)
    _frame(tutorial, dialog=dialog, seconds=1.5)


def _choose(
    tutorial: Any, picker: Any, value: Any, *, dialog: Any = None, confirm_value: bool = True
) -> None:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    index = picker.findData(value)
    if index < 0:
        raise RuntimeError("Der gewünschte Eintrag fehlt in der sichtbaren Auswahl.")
    QTest.qWait(250)
    QTest.mouseClick(
        picker,
        Qt.MouseButton.LeftButton,
        pos=QPoint(picker.width() - 12, picker.height() // 2),
        delay=100,
    )
    QTest.qWait(400)
    item = picker.model().index(index, 0)
    picker.view().scrollTo(item)
    tutorial.settle(8)
    popup = picker.view().window()
    overlays = (dialog, popup) if dialog is not None else (popup,)
    # Ein erneutes Aktivieren des Elterndialogs schließt die echte Auswahlliste.
    _frame(tutorial, seconds=4.0, overlays=overlays)
    if not picker.view().isVisible():
        raise RuntimeError("Die echte Auswahlliste wurde vor dem Klick geschlossen.")
    point = picker.view().visualRect(item).center()
    QTest.mouseMove(picker.view().viewport(), point, 100)
    QTest.qWait(100)
    tutorial.recorder.add(
        "",
        "",
        0.35,
        target=picker.view().viewport().mapToGlobal(point),
        click=True,
        overlays=overlays,
    )
    if not picker.view().isVisible():
        raise RuntimeError("Die Auswahlliste ist vor dem Auswahlklick nicht mehr sichtbar.")
    QTest.mouseClick(
        picker.view().viewport(),
        Qt.MouseButton.LeftButton,
        pos=point,
        delay=100,
    )
    tutorial.settle(8)
    if confirm_value and picker.currentData() != value:
        raise RuntimeError("Die tatsächliche Auswahl wurde nicht übernommen.")


def _segment(
    tutorial: Any,
    key: str,
    de: tuple[str, str, str],
    en: tuple[str, str, str],
    *,
    action: Any = None,
    dialog: Any = None,
    target: Any = None,
    short_voice: tuple[str, str] | None = None,
) -> None:
    """Ansage, echte Handlung und Ergebnis als zusammenhängende Rohszene speichern."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QImageReader

    from app.i18n import get_language

    first = len(tutorial.recorder.slides)
    tutorial.add(de[0], en[0], de[1], en[1], 4.0 if action else 10.0, dialog=dialog, target=target)
    action_first = len(tutorial.recorder.slides)
    if action:
        action()
        action_last = len(tutorial.recorder.slides)
        tutorial.add(de[0], en[0], de[1], en[1], 6.0, dialog=dialog, target=target)
    else:
        action_last = action_first
    size = QImageReader(str(tutorial.recorder.slides[-1].path)).size()
    crop = [0, 0, size.width(), size.height()]
    if dialog is not None:
        origin = dialog.mapToGlobal(QPoint(0, 0)) - tutorial.window.mapToGlobal(QPoint(0, 0))
        crop = [
            round(origin.x() * size.width() / tutorial.window.width()),
            round(origin.y() * size.height() / tutorial.window.height()),
            round(dialog.width() * size.width() / tutorial.window.width()),
            round(dialog.height() * size.height() / tutorial.window.height()),
        ]
    language = get_language()
    text = de if language == "de" else en
    tutorial._inventory_scenes.append(
        {
            "key": key,
            "action": "inventory",
            "title": text[0],
            "detail": text[1],
            "voice": text[2],
            "short_voice": short_voice[0 if language == "de" else 1] if short_voice else "",
            "short": short_voice is not None,
            "minimum_seconds": 10.0,
            "first_slide": first,
            "last_slide": len(tutorial.recorder.slides),
            "action_first_slide": action_first,
            "action_last_slide": action_last,
            "model_crop": crop,
            "focus": None,
        }
    )


def _caption(tutorial: Any, step: dict[str, Any], **kwargs: Any) -> None:
    _segment(
        tutorial,
        step["key"],
        tuple(step["de"][field] for field in ("title", "detail", "voice")),
        tuple(step["en"][field] for field in ("title", "detail", "voice")),
        short_voice=(step["de"]["short_voice"], step["en"]["short_voice"])
        if step.get("short")
        else None,
        **kwargs,
    )


def _wait_for_inventory(tutorial: Any, view: Any) -> None:
    deadline = monotonic() + 30
    while not view.wait_for_workers(0):
        if monotonic() >= deadline:
            raise RuntimeError("Lagerschreiben dauert zu lange; den sichtbaren Hinweis prüfen.")
        tutorial.settle(4)
    tutorial.settle(12)


def _entry(tutorial: Any) -> Any:
    from app.core.knowledge import filaments

    _catalogue(tutorial)
    snapshot = filaments.read_snapshot()
    if len(snapshot.spools) != 1:
        raise RuntimeError("Genau eine Vorführspule erwartet; isolierten Lagerstand prüfen.")
    return next(iter(snapshot.spools.values()))


def _view(tutorial: Any) -> Any:
    from app.ui.filament_inventory import InventoryView

    view = tutorial.window._inventory_view
    if not isinstance(view, InventoryView) or tutorial.window.stack.currentWidget() is not view:
        raise RuntimeError("Filamentlager ist nicht sichtbar; den Aufnahmeschritt prüfen.")
    return view


def _button(parent: Any, text: str) -> Any:
    from PySide6.QtWidgets import QPushButton

    matches = [button for button in parent.findChildren(QPushButton) if button.text() == text]
    visible = [button for button in matches if button.isVisible()]
    if len(visible) != 1:
        raise RuntimeError(f"Bedienelement nicht eindeutig sichtbar: {text}")
    return visible[0]


def _open(tutorial: Any, step: dict[str, Any]) -> None:
    from app.core.knowledge import filaments

    path = _catalogue(tutorial)
    if filaments.read_snapshot().spools:
        raise RuntimeError("Vorführlager ist nicht leer; einen frischen Aufnahmeordner verwenden.")
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.i18n import tr

    matches = [
        (menu, action)
        for menu in tutorial.window._menus
        for action in menu.actions()
        if action.text() == str(tr("Filamentlager …"))
    ]
    if len(matches) != 1:
        raise RuntimeError("Der Menüeintrag zum Filamentlager ist nicht eindeutig.")
    menu, action = matches[0]

    def open_menu() -> None:
        bar = tutorial.window.menuBar()
        QTest.mouseClick(
            bar, Qt.MouseButton.LeftButton, pos=bar.actionGeometry(menu.menuAction()).center()
        )
        tutorial.settle(10)
        point = menu.actionGeometry(action).center()
        QTest.mouseMove(menu, point, 100)
        _frame(tutorial, seconds=6.0, overlays=(menu,))
        QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=point)
        tutorial.settle(18)

    _segment(
        tutorial,
        "open-menu",
        (
            "Das Filamentlager öffnen",
            "Bearbeiten → Filamentlager",
            "Im Menü Bearbeiten öffne ich das Filamentlager.",
        ),
        (
            "Open the filament inventory",
            "Edit → Filament inventory",
            "I open the filament inventory from the Edit menu.",
        ),
        action=open_menu,
    )
    tutorial.settle(18)
    view = _view(tutorial)
    _caption(tutorial, step, target=view.empty_add_button)
    _proof(tutorial, "open", isolated=True, catalogue=path.relative_to(tutorial.folder).as_posix())


def _create(tutorial: Any, step: dict[str, Any]) -> None:
    from PySide6.QtWidgets import QColorDialog, QDialogButtonBox, QLineEdit, QScrollArea

    from app.i18n import get_language
    from app.ui.filament_picker import NewFilamentDialog

    view = _view(tutorial)
    language = get_language()
    _segment(
        tutorial,
        "create-open",
        (
            "Eine Spule anlegen",
            "Spule von Hand anlegen",
            "Ich lege eine Spule von Hand an. Die Angaben sind Vorführwerte.",
        ),
        (
            "Add a spool",
            "Add spool manually",
            "I add a spool manually. These are demonstration values.",
        ),
        target=view.empty_add_button,
    )

    def fill(dialog: Any) -> None:
        if not isinstance(dialog, NewFilamentDialog):
            raise RuntimeError("Spulendialog fehlt; Lageraufnahme prüfen.")
        dialog.setMinimumSize(800, 1000)
        tutorial.settle(12)
        _segment(
            tutorial,
            "create-form",
            (
                "Die Angaben einer Spule",
                "Name, Typ, Farbe, Lagerort und Bestand",
                "Hier stehen die Angaben der neuen Spule. Ich gehe die Felder der "
                "Reihe nach durch.",
            ),
            (
                "The spool details",
                "Name, type, colour, location and stock",
                "These are the details for the new spool. I work through the fields in order.",
            ),
            dialog=dialog,
        )
        _segment(
            tutorial,
            "create-name",
            (
                "Die Spule benennen",
                "PETG Orange · Vorführung",
                "Ich gebe der Spule einen Namen, den ich später wiedererkenne: PETG "
                "Orange, Vorführung.",
            ),
            (
                "Name the spool",
                "PETG Orange · Demo",
                "I give the spool a name I will recognise later: PETG Orange, Demo.",
            ),
            action=lambda: _type(
                tutorial, dialog.name, step[language]["spool_name"], dialog=dialog
            ),
            dialog=dialog,
            target=dialog.name,
        )
        _segment(
            tutorial,
            "create-type",
            (
                "Die Materialart wählen",
                "Typ: PETG",
                "Als Typ wähle ich PETG. Das ist die Materialart dieser Vorführspule.",
            ),
            (
                "Choose the material type",
                "Type: PETG",
                "I choose PETG as the type. That is the material type for this "
                "demonstration spool.",
            ),
            action=lambda: _choose(
                tutorial, dialog.material_type, step["material_type"], dialog=dialog
            ),
            dialog=dialog,
            target=dialog.material_type,
        )
        _segment(
            tutorial,
            "create-colour-open",
            ("Die Spulenfarbe öffnen", "Farbe wählen", "Für die Farbe öffne ich das Farbfeld."),
            (
                "Open the spool colour",
                "Choose a colour",
                "I open the colour field to choose its colour.",
            ),
            dialog=dialog,
            target=dialog.colour_buttons[0],
        )

        def colour_fill(colour_dialog: Any) -> None:
            if not isinstance(colour_dialog, QColorDialog):
                raise RuntimeError("Farbdialog fehlt; Spulenaufnahme prüfen.")
            colour_dialog.setMinimumSize(700, 600)
            colour_text = colour_dialog.findChild(QLineEdit, "qt_colorname_lineedit")
            if colour_text is None:
                raise RuntimeError("Das Eingabefeld für die Farbe fehlt.")
            _segment(
                tutorial,
                "create-colour",
                (
                    "Orange einstellen",
                    "Die Farbe gehört zur Vorführspule.",
                    "Ich trage diesen Orangeton ein und kontrolliere die Farbvorschau.",
                ),
                (
                    "Set the orange colour",
                    "The colour identifies the demonstration spool.",
                    "I enter this shade of orange and check the colour preview.",
                ),
                action=lambda: _type(tutorial, colour_text, step["colour"], dialog=colour_dialog),
                dialog=colour_dialog,
                target=colour_text,
            )
            if colour_dialog.currentColor().name().lower() != step["colour"].lower():
                raise RuntimeError("Die eingetippte Farbe stimmt nicht mit der Vorschau überein.")
            box = colour_dialog.findChild(QDialogButtonBox)
            button = box.button(QDialogButtonBox.StandardButton.Ok) if box else None
            if button is None:
                raise RuntimeError("Bestätigung im Farbdialog fehlt.")
            _segment(
                tutorial,
                "create-colour-confirm",
                (
                    "Die Farbe übernehmen",
                    "Die Vorschau ist orange.",
                    "Die Vorschau stimmt. Ich bestätige die Farbe.",
                ),
                (
                    "Confirm the colour",
                    "The preview is orange.",
                    "The preview looks right. I confirm the colour.",
                ),
                dialog=colour_dialog,
                target=button,
            )
            _click(tutorial, button, dialog=colour_dialog)

        tutorial.modal(
            lambda: _click(tutorial, dialog.colour_buttons[0], dialog=dialog), colour_fill
        )
        _segment(
            tutorial,
            "create-location",
            (
                "Den Lagerort eintragen",
                "Demo-Box A",
                "Als Lagerort trage ich Demo-Box A ein. So kann ich die Spule später wiederfinden.",
            ),
            (
                "Enter the storage location",
                "Demo box A",
                "I enter Demo box A as its location, so I can find the spool again later.",
            ),
            action=lambda: _type(
                tutorial, dialog.location, step[language]["location"], dialog=dialog
            ),
            dialog=dialog,
            target=dialog.location,
        )
        scroll = dialog.findChild(QScrollArea)
        if scroll is not None:
            scroll.ensureWidgetVisible(dialog.spool_weight)
        _segment(
            tutorial,
            "create-nominal",
            (
                "Die ursprüngliche Füllung eintragen",
                "Nennfüllung: 1000 g",
                "Die Nennfüllung ist die ursprüngliche Filamentmenge. Für diese Spule "
                "trage ich tausend Gramm ein.",
            ),
            (
                "Enter the original fill weight",
                "Nominal weight: 1000 g",
                "The nominal weight is the original amount of filament. I enter one "
                "thousand grams for this spool.",
            ),
            action=lambda: _type(
                tutorial, dialog.spool_weight, str(step["spool_grams"]), dialog=dialog
            ),
            dialog=dialog,
            target=dialog.spool_weight,
        )
        if scroll is not None:
            scroll.ensureWidgetVisible(dialog.stock_known)
        _segment(
            tutorial,
            "create-known",
            (
                "Eine bekannte Restmenge eintragen",
                "Restmenge bekannt",
                "Meine Restmenge ist bekannt. Deshalb aktiviere ich dieses Feld. "
                "Unbekannt wäre nicht dasselbe wie leer.",
            ),
            (
                "Enter known remaining stock",
                "Remaining amount known",
                "I know the remaining amount, so I enable this field. Unknown would "
                "not mean empty.",
            ),
            action=lambda: _click(tutorial, dialog.stock_known, dialog=dialog),
            dialog=dialog,
            target=dialog.stock_known,
        )
        if scroll is not None:
            scroll.ensureWidgetVisible(dialog.remaining)
        _segment(
            tutorial,
            "create-remaining",
            (
                "Den Restbestand eingeben",
                "Restmenge: 620 g",
                "Jetzt trage ich sechshundertzwanzig Gramm Rest ein. Gemeint ist das "
                "Filament, ohne das Gewicht der leeren Spule.",
            ),
            (
                "Enter the remaining amount",
                "Remaining amount: 620 g",
                "I enter six hundred and twenty grams remaining. This is filament "
                "only, without the empty spool's weight.",
            ),
            action=lambda: _type(
                tutorial, dialog.remaining, str(step["remaining_grams"]), dialog=dialog
            ),
            dialog=dialog,
            target=dialog.remaining,
        )
        box = dialog.findChild(QDialogButtonBox)
        button = box.button(QDialogButtonBox.StandardButton.Ok) if box else None
        if button is None or not button.isEnabled():
            raise RuntimeError("Spule lässt sich noch nicht anlegen; Eingaben prüfen.")
        _segment(
            tutorial,
            "create-save",
            (
                "Die Spule speichern",
                "Spule anlegen",
                "Die Angaben sind vollständig. Mit Spule anlegen speichere ich den Eintrag.",
            ),
            ("Save the spool", "Add spool", "The details are complete. Add spool saves the entry."),
            dialog=dialog,
            target=button,
        )
        _click(tutorial, button, dialog=dialog)

    tutorial.modal(lambda: _click(tutorial, view.empty_add_button), fill)
    _wait_for_inventory(tutorial, view)
    entry = _entry(tutorial)
    for field in ("material_type", "colour", "spool_grams", "remaining_grams"):
        actual = getattr(entry, field)
        expected = step[field]
        matches = (
            math.isclose(actual, expected) if isinstance(actual, float) else actual == expected
        )
        if not matches:
            raise RuntimeError(f"Gespeicherte Vorführangabe weicht ab: {field}")
    _segment(
        tutorial,
        "create-saved",
        (
            "Die neue Spule ist im Lager",
            "Den gespeicherten Eintrag ansehen.",
            "Die neue Spule steht jetzt im Lager. Ich öffne sie gleich und "
            "kontrolliere die gespeicherten Angaben.",
        ),
        (
            "The new spool is in the inventory",
            "Inspect the saved entry.",
            "The new spool is now in the inventory. I will open it and check the saved details.",
        ),
    )
    _proof(tutorial, "create", spool=asdict(entry))


def _detail(tutorial: Any, step: dict[str, Any]) -> None:
    from app.i18n import tr

    view = _view(tutorial)
    entry = _entry(tutorial)
    if view.pages.currentIndex() == 0:
        cards = [card for card in view.cards if card.entry.identifier == entry.identifier]
        if len(cards) != 1:
            raise RuntimeError("Die gespeicherte Vorführspule fehlt im Regal.")
        _segment(
            tutorial,
            f"{step['key']}-open",
            (
                "Die gespeicherte Spule öffnen",
                "Den Eintrag im Regal anklicken.",
                "Ich klicke die gespeicherte Spule an.",
            ),
            ("Open the saved spool", "Click the entry on the shelf.", "I click the saved spool."),
            action=lambda: _click(tutorial, cards[0]),
            target=cards[0],
        )
    tutorial.settle(12)
    _caption(tutorial, step, target=_button(view.detail, str(tr("Angaben ändern"))))
    _proof(tutorial, step["phase"], spool=asdict(entry))


def _edit(tutorial: Any, step: dict[str, Any]) -> None:
    from PySide6.QtWidgets import QDialogButtonBox, QScrollArea

    from app.i18n import tr
    from app.ui.filament_picker import NewFilamentDialog

    view = _view(tutorial)
    before = _entry(tutorial)

    def fill(dialog: Any) -> None:
        if not isinstance(dialog, NewFilamentDialog):
            raise RuntimeError("Spulenbearbeitung fehlt; Lageraufnahme prüfen.")
        dialog.setMinimumSize(800, 1000)
        dialog.focus_field("remaining_grams")
        scroll = dialog.findChild(QScrollArea)
        if scroll is not None:
            scroll.ensureWidgetVisible(dialog.remaining)
        tutorial.settle(12)
        _caption(
            tutorial,
            step,
            dialog=dialog,
            target=dialog.remaining,
            action=lambda: _type(
                tutorial, dialog.remaining, str(step["remaining_grams"]), dialog=dialog
            ),
        )
        box = dialog.findChild(QDialogButtonBox)
        button = box.button(QDialogButtonBox.StandardButton.Ok) if box is not None else None
        if button is None or not button.isEnabled():
            raise RuntimeError("Bestand lässt sich noch nicht speichern; Eingaben prüfen.")
        _segment(
            tutorial,
            "edit-save",
            ("Den Bestand speichern", "Spule speichern", "Ich speichere die neue Restmenge."),
            ("Save the remaining amount", "Apply the details", "I save the new remaining amount."),
            dialog=dialog,
            target=button,
        )
        _click(tutorial, button, dialog=dialog)

    edit_button = _button(view.detail, str(tr("Angaben ändern")))
    _segment(
        tutorial,
        "edit-open",
        (
            "Den Bestand ändern",
            "Angaben ändern",
            "Über Angaben ändern öffne ich den gespeicherten Eintrag.",
        ),
        ("Update the stock", "Edit details", "Edit details opens the saved entry."),
        target=edit_button,
    )
    tutorial.modal(lambda: _click(tutorial, edit_button), fill)
    _wait_for_inventory(tutorial, view)
    after = _entry(tutorial)
    if (
        after.identifier != before.identifier
        or after.remaining_grams is None
        or not math.isclose(after.remaining_grams, step["remaining_grams"])
    ):
        raise RuntimeError("Gespeicherter Vorführbestand stimmt nicht mit der Eingabe überein.")
    _proof(tutorial, "edit", before=asdict(before), after=asdict(after))


def _back(tutorial: Any, step: dict[str, Any]) -> None:
    from app.i18n import tr

    view = _view(tutorial)
    shelf = _button(view.detail, str(tr("Zurück zum Regal")))
    _segment(
        tutorial,
        "back-shelf",
        ("Zum Regal zurückgehen", "Zurück zum Regal", "Ich gehe zurück zum Regal."),
        ("Return to the shelf", "Back to shelf", "I return to the shelf."),
        action=lambda: _click(tutorial, shelf),
    )
    tutorial.settle(10)
    _caption(tutorial, step, action=lambda: _click(tutorial, view.back_button))
    tutorial.settle(12)


def _assign(tutorial: Any, step: dict[str, Any]) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.core.export.threemf import slot_identity
    from app.ui.filament_picker import spool_slot

    entry = _entry(tutorial)
    result = tutorial.session.last_result
    bodies = list(result.scene.objects)
    if len(bodies) != 1:
        raise RuntimeError("Die Lageraufnahme erwartet genau ein Werkstattmodell.")
    tree = tutorial.window.object_tree.tree
    items = [tree.topLevelItem(index) for index in range(tree.topLevelItemCount())]
    item = next(
        (
            item
            for item in items
            if item is not None and str(item.data(0, Qt.ItemDataRole.UserRole)) == bodies[0]
        ),
        None,
    )
    if item is None:
        raise RuntimeError("Das Werkstattmodell ist im Objektbaum nicht sichtbar.")
    tree.scrollToItem(item)
    point = tree.visualItemRect(item).center()
    _segment(
        tutorial,
        "assign-select",
        (
            "Den Körper auswählen",
            "Pflanzenklemme im Objektbaum",
            "Ich wähle die Pflanzenklemme im Objektbaum aus.",
        ),
        (
            "Select the body",
            "Plant support clamp in the object tree",
            "I select the plant support clamp in the object tree.",
        ),
        action=lambda: QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=point),
        target=tree.viewport().mapToGlobal(point),
    )
    tutorial.settle(20)
    picker = tutorial.window.quick_filament.picker
    if not picker.isVisible() or not picker.isEnabled():
        raise RuntimeError("Die Spulenwahl ist am gewählten Körper nicht erreichbar.")
    _caption(
        tutorial,
        step,
        target=picker,
        action=lambda: _choose(tutorial, picker, entry.identifier, confirm_value=False),
    )
    tutorial.checked("Vorführspule dem tatsächlichen Modell zugewiesen")
    changed = tutorial.session.last_result.scene.objects[bodies[0]]
    slots = [{**asdict(slot), "name": str(slot.name)} for slot in changed.material_slots]
    expected = slot_identity(spool_slot(entry))
    if not any(slot_identity(slot) == expected for slot in changed.material_slots):
        raise RuntimeError("Das Modell trägt nicht die ausgewählte Vorführspule.")
    bindings = tutorial.window.effective_print_settings().spool_bindings
    if not any(binding.spool_identifier == entry.identifier for binding in bindings):
        raise RuntimeError("Die Zuweisung ist nicht mit der gewählten Lagerspule verbunden.")
    after = _entry(tutorial)
    if (
        after.remaining_grams is None
        or entry.remaining_grams is None
        or not math.isclose(after.remaining_grams, entry.remaining_grams)
    ):
        raise RuntimeError("Eine reine Materialzuweisung hat den Vorführbestand verändert.")
    _proof(
        tutorial,
        "assign",
        spool=asdict(after),
        body=bodies[0],
        material_slots=slots,
        spool_bindings=[{**asdict(binding), "name": str(binding.name)} for binding in bindings],
    )
    tutorial.settle(12)


def capture_step(tutorial: Any, step: dict[str, Any]) -> list[dict[str, Any]]:
    """Genau einen vereinbarten Lagerweg im isolierten Aufnahmeprofil bedienen."""
    _catalogue(tutorial)
    tutorial._inventory_scenes = []
    actions = {
        "open": _open,
        "create": _create,
        "detail": _detail,
        "edit": _edit,
        "verify": _detail,
        "back": _back,
        "assign": _assign,
    }
    phase = step["phase"]
    if phase not in actions:
        raise ValueError(f"Unbekannter Lagerschritt: {phase}")
    actions[phase](tutorial, step)
    return list(tutorial._inventory_scenes)
