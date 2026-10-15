"""Jedes Feld eines Operationsdialogs trägt seinen Namen — einmal (FD-94).

Ein Bildschirmleser, der ein Feld ohne Namen erreicht, liest seinen Inhalt
vor oder nichts (``oberflaeche.md``, „Ein Feld ohne Namen“). Im
Operationsdialog blieben die Felder ohne Namen, die selbst der Editor sind
(Auswahl, Haken), und die Liste des Flächenwählers hieß nach dem Haken
„Ganzer Körper“, auch wo es ihn gar nicht gibt. Der Wächter öffnet jede
registrierte Operation.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QCheckBox, QHBoxLayout, QLabel, QSpinBox, QWidget

from app.core import bootstrap
from app.core.registry import REGISTRY
from app.ui.form_fields import explain, inputs_of, repeated_names, unnamed_inputs

#: Zwei erkannte Merkmale, damit Merkmalslisten Zeilen haben.
FEATURES = {"hole_1": "Bohrung 1 · Ø5,20 mm", "hole_2": "Bohrung 2 · Ø5,20 mm"}


def test_every_operation_dialog_names_each_field_once(qt_app: QApplication) -> None:
    """Kein Eingabefeld ohne Namen und keine zwei mit demselben, in jedem Dialog.

    Doppelt zählt nur, was ein Vorleser erreichen kann: Ein ``internal``-Feld
    steht nie da (Migrationsmarker, gespeicherte Lage) und teilt seinen Titel
    mit dem Feld, dem es dient.
    """
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    found: list[str] = []
    specs = REGISTRY.all()
    assert len(specs) > 150, f"nur {len(specs)} Operationen — dann prüft das nichts"
    for spec in specs:
        dialog = OperationDialog(spec, {"obj_1": "Quader"}, None, features=FEATURES)
        try:
            hidden = [
                widget
                for entry in spec.params.spec()
                if entry.internal and (editor := dialog._editors.get(entry.name)) is not None
                for widget in inputs_of(editor)
            ]
            if unnamed := unnamed_inputs(dialog):
                found.append(f"{spec.name}: ohne Namen {unnamed}")
            if repeated := repeated_names(dialog, ignore=hidden):
                found.append(f"{spec.name}: doppelt {repeated}")
        finally:
            dialog.deleteLater()
    assert not found, f"{len(found)} Dialoge:\n" + "\n".join(found)


def test_a_required_feature_list_is_named_after_its_row(qt_app: QApplication) -> None:
    """Die Liste heißt wie ihre Zeile; einen Haken „Ganzer Körper“ hat eine
    Pflichtliste nicht — auch keinen verborgenen, den ein Vorleser findet."""
    from app.ui.op_dialog import FeatureSetField, OperationDialog

    bootstrap.load_operations()
    for operation in ("pattern_feature", "group_pattern"):
        spec = REGISTRY.get(operation)
        title = str(
            next(entry for entry in spec.params.spec() if entry.name == "at_features").title
        )
        dialog = OperationDialog(spec, {"obj_1": "Quader"}, None, features=FEATURES)
        try:
            field = dialog.findChild(FeatureSetField)
            assert field is not None
            assert field.list.accessibleName() == title, operation
            assert field.findChildren(QCheckBox) == [], f"{operation}: Haken in einer Pflichtliste"
        finally:
            dialog.deleteLater()


def test_a_reason_replaces_the_sentence_inside_the_field_too(qt_app: QApplication) -> None:
    """Ein zweiter Satz (der Grund einer gesperrten Zeile) ersetzt auch den
    Tooltip des Innenfelds, das der erste gesetzt hat — sonst zeigt die Maus
    über der Zahl noch den alten Satz."""
    host = QWidget()
    caption = QLabel("Tiefe", host)
    field = QWidget(host)
    row = QHBoxLayout(field)
    number = QSpinBox(field)
    row.addWidget(number)

    explain(field, caption, "Wie tief gebohrt wird.")
    assert number.toolTip() == "Wie tief gebohrt wird."
    explain(field, caption, "Wirkt nur, wenn „Durchgehend“ nicht angehakt ist.")

    assert number.toolTip() == "Wirkt nur, wenn „Durchgehend“ nicht angehakt ist."
    assert number.accessibleDescription() == number.toolTip()
    host.deleteLater()
