"""Aus dem Operationsschema erzeugte Dialoge: Werte, Auswahl und gestufte Tiefe (§2.5)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
)

from app.core.registry import REGISTRY
from app.ui.main_window import MainWindow
from app.ui.op_dialog import OperationDialog
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


def test_a_dialog_is_generated_from_the_parameter_schema(qt_app: QApplication) -> None:
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    values = dialog.values()

    assert set(values) == {entry.name for entry in REGISTRY.get("load").params.spec()}
    assert values["unit"] == "auto"
    assert values["weld"] is True


@pytest.mark.parametrize("finish", ["accept", "reject"])
def test_operation_waits_for_the_saved_spool_and_window_keeps_a_cancelled_dialogs_write(
    window: MainWindow,
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    finish: str,
) -> None:
    """Anwenden wartet auf die neue Spule; Abbrechen verliert keinen bestätigten Lagerauftrag."""
    from time import monotonic

    from PySide6.QtCore import QCoreApplication
    from PySide6.QtTest import QTest

    from app.core.knowledge import filaments
    from app.ui.filament_picker import NEW_FILAMENT, FilamentField, NewFilamentDialog

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    original = filaments.save
    entered, released = threading.Event(), threading.Event()

    def save(entry):
        entered.set()
        assert released.wait(5)
        return original(entry)

    def confirm(dialog):
        dialog.name.setText("Neue Spule")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(filaments, "save", save)
    monkeypatch.setattr(NewFilamentDialog, "exec", confirm)
    dialog = OperationDialog(REGISTRY.get("assign_slot"), ["obj_1"], window, values={"slot": 0})
    field = dialog.findChild(FilamentField)
    assert field is not None
    writer = field._writes
    dialog.show()
    try:
        field._make_one(field.findData(NEW_FILAMENT))
        assert entered.wait(2)
        assert not dialog._accept_button.isEnabled()
        assert "gespeichert" in dialog._accept_button.toolTip()
        dialog.accept()
        assert not dialog.isHidden()
        if finish == "reject":
            dialog.reject()
            dialog.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not window.wait_for_workers(0)
        assert writer.parent() is window
    finally:
        released.set()
        deadline = monotonic() + 5
        while not writer.wait_for_workers(0) and monotonic() < deadline:
            QTest.qWait(10)
    assert writer.wait_for_workers(0)
    assert [entry.name for entry in filaments.catalogue()] == ["Neue Spule"]
    if finish == "accept":
        assert dialog._accept_button.isEnabled()
        assert dialog.values()["name"] == "Neue Spule"
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
        dialog.deleteLater()


def test_choosing_a_profileless_filament_clears_old_slicer_metadata(
    qt_app: QApplication,
) -> None:
    """Ein Filamentwechsel darf keine unsichtbare Herstellerwahl behalten.

    Eine lokale Spule hat bewusst kein Slicer-Profil. Wird sie in einem
    geöffneten Farbschritt gewählt, muss deshalb der alte Profilname
    verschwinden; sonst fährt die neue Spule mit den Druckwerten der alten.
    """
    dialog = OperationDialog(
        REGISTRY.get("assign_slot"),
        ["obj_1"],
        values={
            "slot": 1,
            "name": "PETG Grau",
            "colour": "#808080",
            "material_type": "PETG",
            "slicer_profile": "Elegoo PETG PRO @ECC2",
        },
    )
    try:
        dialog._fill_filament_fields("PLA Weiß", "#ffffff", "PLA", "")

        values = dialog.values()
        assert values["name"] == "PLA Weiß"
        assert values["material_type"] == "PLA"
        assert values["slicer_profile"] == "", "die leere Auswahl löscht den alten Wert"
    finally:
        dialog.deleteLater()


def test_a_feature_parameter_offers_the_features(qt_app: QApplication) -> None:
    """§18.5: „face_2" tippt niemand, der es nicht vorher abgelesen hat.

    Der Parameter war ein leeres Textfeld, und sein eigener doc-Satz versprach,
    er werde „beim Anklicken im Fenster eingetragen" — abzulesen war die
    Kennung nur im Objektbaum, wo die Namen bei Standardbreite abgeschnitten
    sind.
    """
    from PySide6.QtWidgets import QComboBox

    spec = REGISTRY.get("create_lid")
    features = {"face_2": "face_2 · 3915 mm²", "hole_1": "hole_1 · Ø5,19 mm"}
    dialog = OperationDialog(spec, ["obj_1"], features=features)
    try:
        editor = dialog._editors["at_feature"]
        assert isinstance(editor, QComboBox), "eine Liste, kein Textfeld"

        labels = [editor.itemText(index) for index in range(editor.count())]
        assert "face_2 · 3915 mm²" in labels, "die Beschriftung, nicht die Kennung"
        assert editor.itemData(0) == "", "ohne Merkmal geht es auch — der Parameter ist optional"
        assert dialog.values()["at_feature"] == "", "und die Vorgabe bleibt leer"

        editor.setCurrentIndex(labels.index("hole_1 · Ø5,19 mm"))
        assert dialog.values()["at_feature"] == "hole_1", "die Kennung reist mit, nicht der Text"
    finally:
        dialog.deleteLater()


def test_an_unknown_feature_is_shown_not_replaced(qt_app: QApplication) -> None:
    """Ein gespeicherter Wert, den die Liste nicht kennt, bleibt stehen.

    Wer eine Operation aus dem Verlauf öffnet, deren Merkmal seit einer
    Umbenennung nicht mehr da ist, soll sehen, was dasteht — nicht
    stillschweigend ein anderes bekommen.
    """
    from PySide6.QtWidgets import QComboBox

    spec = REGISTRY.get("create_lid")
    dialog = OperationDialog(
        spec, ["obj_1"], values={"at_feature": "face_9"}, features={"face_2": "face_2 · 100 mm²"}
    )
    try:
        editor = dialog._editors["at_feature"]
        assert isinstance(editor, QComboBox)
        assert dialog.values()["at_feature"] == "face_9"
    finally:
        dialog.deleteLater()


def test_clicking_a_feature_fills_the_field(qt_app: QApplication) -> None:
    """Der ``doc``-Satz versprach es seit je: „wird beim Anklicken im Fenster
    eingetragen".

    Einzulösen war das nicht, solange der Dialog das Fenster sperrte — es gab
    kein Anklicken, während er offen war. Jetzt ist der kürzeste Weg zu einer
    Fläche wieder der, auf sie zu zeigen.
    """
    spec = REGISTRY.get("create_lid")
    dialog = OperationDialog(spec, ["obj_1"], features={"face_2": "face_2 · 3915 mm²"})
    try:
        assert dialog.take_feature("face_2", "face_2 · 3915 mm²")
        assert dialog.values()["at_feature"] == "face_2"

        # Ein Merkmal, das die Liste nicht kennt, kommt trotzdem an: erkannt
        # wird nach jeder Operation neu, der Dialog steht seit vorher offen.
        assert dialog.take_feature("hole_7", "hole_7 · Ø3,20 mm")
        assert dialog.values()["at_feature"] == "hole_7"
    finally:
        dialog.deleteLater()


def test_a_dialog_without_a_feature_field_takes_nothing(qt_app: QApplication) -> None:
    """Der Aufrufer weiß sonst nicht, ob sein Klick angekommen ist."""
    dialog = OperationDialog(REGISTRY.get("drill_hole"), ["obj_1"])
    try:
        assert not dialog.take_feature("face_2", "face_2 · 100 mm²")
    finally:
        dialog.deleteLater()


def test_clicking_a_spot_fills_the_position(qt_app: QApplication) -> None:
    """§18.5: zeigen statt tippen — und §11 bleibt gewahrt.

    *Bohrung setzen* öffnete mit X, Y und Z auf 0,00, und der Ursprung liegt
    bei einer geladenen Platte an einer Ecke. Wer dort bohrte, kratzte einen
    Span von der Kante ab. Was der Klick einträgt, steht danach lesbar da: die
    Zahl ist die Wahrheit, das Zeigen nur die bequeme Eingabe.
    """
    dialog = OperationDialog(REGISTRY.get("drill_hole"), ["obj_1"])
    try:
        assert dialog.take_point((12.5, -7.25, 4.0))

        values = dialog.values()
        assert values["x"] == pytest.approx(12.5)
        assert values["y"] == pytest.approx(-7.25)
        assert values["z"] == pytest.approx(4.0)
    finally:
        dialog.deleteLater()


def test_a_dialog_without_a_position_takes_no_point(qt_app: QApplication) -> None:
    """Nicht jede Operation hat eine Stelle, an der sie arbeitet."""
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    try:
        assert not dialog.take_point((1.0, 2.0, 3.0))
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize(
    ("shown", "requested", "expected"),
    [(False, 240, 380), (False, 520, 520), (True, 380, 380), (True, 520, 520)],
)
def test_the_dialog_keeps_out_of_the_middle_of_the_view(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    shown: bool,
    requested: int,
    expected: int,
) -> None:
    """Bei vorhandenem Platz steht der Dialog rechts und vollständig im Anker.

    Die Breiten sind Vorgaben dieser Geometrieprobe. Vor dem Anzeigen zählt
    die Mindestbreite, danach die gewählte Fensterbreite; die Schriftmetrik
    des Offscreen-Treibers sagt nichts über einen Kundendialog aus.
    """
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QWidget

    anchor = QWidget()
    anchor.resize(1200, 800)
    anchor.show()
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    try:
        if shown:
            dialog.setFixedWidth(requested)
            dialog.show()
            QApplication.processEvents()
        else:
            monkeypatch.setattr(dialog, "sizeHint", lambda: QSize(requested, 400))
        dialog.place_beside(anchor)
        middle = anchor.mapToGlobal(anchor.rect().center()).x()

        assert dialog.x() > middle, "der Dialog lässt bei genügend Platz die Mitte frei"
        assert dialog.y() >= anchor.mapToGlobal(anchor.rect().topLeft()).y()
        right_edge = anchor.mapToGlobal(anchor.rect().topRight()).x()
        assert dialog.x() + expected <= right_edge, "auch die Mindestbreite bleibt im Anker"
    finally:
        dialog.deleteLater()
        anchor.deleteLater()


def test_a_narrow_view_leaves_the_dialog_where_it_was(qt_app: QApplication) -> None:
    """Passt er nicht daneben, bleibt er, wo Qt ihn hingesetzt hat.

    Ein Dialog halb außerhalb des Bildschirms wäre schlimmer als einer in der
    Mitte.
    """
    from PySide6.QtWidgets import QWidget

    anchor = QWidget()
    anchor.resize(120, 400)
    anchor.show()
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    try:
        before = dialog.pos()
        dialog.place_beside(anchor)

        assert dialog.pos() == before
    finally:
        dialog.deleteLater()
        anchor.deleteLater()


def test_advanced_parameters_sit_behind_the_fold(qt_app: QApplication) -> None:
    """§2.4: die Vorderseite hält, was Leute wirklich ändern.

    Und der hintere Teil ist wirklich weg, nicht nur grau: eine ankreuzbare
    Gruppe graut ihre Felder aus und lässt sie stehen — die gestufte Tiefe war
    damit gedacht und nicht gebaut.
    """
    dialog = OperationDialog(REGISTRY.get("load"), [])

    assert hasattr(dialog, "advanced"), "load hat hintere Parameter, also gibt es die Klappe"
    assert not dialog.advanced.isChecked(), "sie beginnt zugeklappt"

    hidden = [
        editor
        for name, editor in dialog._editors.items()
        if next(entry.placement for entry in dialog.spec.params.spec() if entry.name == name)
        == "advanced"
    ]
    assert hidden, "diese Operation hat welche"
    assert all(not editor.isVisibleTo(dialog) for editor in hidden), "zugeklappt heißt unsichtbar"


def test_an_open_advanced_section_never_overlaps_the_action_buttons(
    qt_app: QApplication,
) -> None:
    """Der aufgeklappte Gewinde-Dialog bleibt vollständig bedienbar."""
    dialog = OperationDialog(REGISTRY.get("insert_printed_thread"), [])
    try:
        dialog.show()
        QApplication.processEvents()
        dialog.advanced.setChecked(True)
        QApplication.processEvents()

        box = dialog.findChild(QDialogButtonBox)
        assert box is not None
        advanced = [
            editor
            for name, editor in dialog._editors.items()
            if next(entry.placement for entry in dialog.spec.params.spec() if entry.name == name)
            == "advanced"
        ]
        assert advanced and all(editor.isVisibleTo(dialog) for editor in advanced)
        assert max(editor.geometry().bottom() for editor in advanced) < box.geometry().top()
    finally:
        dialog.close()
