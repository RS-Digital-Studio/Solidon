"""Der Druckeinstellungsdialog (Bauplan §29, §2.4).

Offscreen wie alle Oberflächentests. Geprüft wird, was der Dialog verspricht:
jede Einstellung des Modells hat ein Feld, die Felder schreiben zurück, die
Vorschläge kommen mit Begründung, und ohne Slicer bleibt er benutzbar.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import trimesh
from PySide6.QtCore import QCoreApplication, QPoint, QRect, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QToolButton,
    QWidget,
)

from app.core import activation
from app.core.brep import edit
from app.core.errors import SCALE_TO_FIT, ExternalToolError
from app.core.export import handover, writer
from app.core.export.slicer_profiles import SlicerProfile
from app.core.geom.mesh import MeshData
from app.core.ingest import threemf
from app.core.knowledge import print_settings, profiles
from app.core.scene.cancel import CancelSignal
from app.core.slice import gcode
from app.core.slice.analysis import total_overhang
from app.core.slice.gcode import GcodeMetrics
from app.core.types import (
    Feature,
    Finding,
    MaterialSlot,
    Profile,
    SceneObject,
    SettingAdvice,
    SlotOverride,
)
from app.i18n import tr
from app.ui import main_window as preflight_main
from app.ui import print_settings_dialog as print_dialog
from app.ui.dialogs import offered_actions
from app.ui.labels import BoundedLengthSpin, BoundedSpin
from app.ui.print_settings_dialog import (
    FIELD_WIDTH,
    FIELDS,
    FILAMENT_FIELDS,
    GROUPS,
    SCREEN_MARGIN,
    FilamentOverrideDialog,
    PrintSettingsDialog,
    _ColourButton,
    group_title,
    settings_for_export,
)
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import session as session


@pytest.mark.parametrize("which", ["printer_choice", "machine_choice"])
def test_typing_an_unknown_printer_preserves_the_choice_and_output_state(
    dialog: PrintSettingsDialog,
    qt_app: QApplication,
    tmp_path: Path,
    which: str,
) -> None:
    """Die getrennte Suche ändert weder die bestätigte Wahl noch das Druckergebnis."""
    box = getattr(dialog, which)
    if which == "machine_choice":
        box.addItem("Herstellerdrucker", "machine-profile")
        box.setEnabled(True)
        box.setCurrentIndex(0)
    original = dialog.session.profile
    gcode_file = tmp_path / "plate.gcode"
    gcode_file.write_text("; gespeichertes Ergebnis", encoding="utf-8")
    dialog._gcode = [gcode_file]
    dialog._release_the_save()
    before = (
        box.currentData(),
        dialog.slice_button.isEnabled(),
        dialog.open_button.isEnabled(),
        dialog.save_button.isEnabled(),
        dialog.state.text(),
    )
    box.search_field.setText("Unbekannter Drucker-Suchtext")
    qt_app.processEvents()
    assert box.currentData() == before[0]
    assert dialog.session.profile == original
    assert dialog.slice_button.isEnabled() == before[1]
    assert dialog.open_button.isEnabled() == before[2]
    assert dialog.save_button.isEnabled() == before[3]
    assert dialog.state.text() == before[4]


@pytest.mark.parametrize("path", ["infill.density", "layers.layer_height", "retraction.length"])
def test_search_opens_the_matching_section_and_scrolls_to_its_field(
    qt_app: QApplication, session: Session, path: str
) -> None:
    """Auch hinter zugeklappter Tiefe führt ein Treffer zu einem sichtbaren Eingabefeld.

    Vorn stehen seit RM-514 nur Fülldichte und Stützen, ohne eigene Klappe;
    ein Treffer dort klappt nichts auf.
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog.show()
    try:
        assert dialog.front_toggle is None, "vorn gibt es keine Klappe mehr"
        dialog.tabs_toggle.setChecked(False)
        dialog.resize(620, 400)
        dialog._lift(path)
        for _ in range(4):
            qt_app.processEvents()
        field = next(entry for entry in FIELDS if entry.path == path)
        assert field.front or dialog.tabs_toggle.isChecked()
        editor = dialog._editors[path]
        assert editor.isVisibleTo(dialog)
        visible = dialog._scroll.viewport()
        position = editor.mapTo(visible, editor.rect().center())
        assert visible.rect().contains(position), "die Hervorhebung liegt im sichtbaren Ausschnitt"
    finally:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()


@pytest.mark.parametrize(
    (
        "selector_path",
        "active_value",
        "target_path",
        "unrelated_selector_path",
        "unrelated_active_value",
    ),
    [
        ("support.style", "tree", "support.z_gap", "adhesion.kind", "brim"),
        ("adhesion.kind", "brim", "adhesion.brim_width", "support.style", "tree"),
    ],
)
def test_search_guides_to_the_selector_for_an_inactive_detail_field(
    dialog: PrintSettingsDialog,
    qt_app: QApplication,
    request: pytest.FixtureRequest,
    selector_path: str,
    active_value: str,
    target_path: str,
    unrelated_selector_path: str,
    unrelated_active_value: str,
) -> None:
    """Die Suche nennt den nötigen Umschalter und aktiviert die Gruppe nicht selbst."""
    from PySide6.QtTest import QTest

    def close_dialog() -> None:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()
        qt_app.processEvents()

    request.addfinalizer(close_dialog)
    dialog.show()
    # Die Suche steht hinter „Weitere Einstellungen" (RM-514); wer sucht,
    # hat die Klappe offen.
    dialog.tabs_toggle.setChecked(True)
    for _ in range(3):
        qt_app.processEvents()
    selector = dialog._editors[selector_path]
    target = dialog._editors[target_path]
    # Der Ausgangszustand wird hergestellt, nicht angenommen: Der allgemeine
    # Drucker legt mit PLA einen Skirt, und dann stand die Haftung nicht auf „keine“.
    assert isinstance(selector, QComboBox)
    selector.setCurrentIndex(selector.findData("none"))
    for _ in range(3):
        qt_app.processEvents()
    before = dialog.settings
    target_before = print_settings.read_path(before, target_path)
    search_window_size_before = (dialog.width(), dialog.height())
    assert isinstance(selector, QComboBox)
    selector_description = selector.accessibleDescription()
    assert selector.currentData() == "none"
    assert dialog._labels[target_path].isHidden()

    term = str(dialog._fields[target_path].title)
    assert dialog.search_hits(term) == [target_path]
    dialog.search.setText(term)
    QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    for _ in range(3):
        qt_app.processEvents()

    assert dialog.settings == before
    assert selector.currentData() == "none"
    assert dialog._labels[target_path].isHidden()
    assert dialog.highlighted() == selector_path
    assert selector.isVisibleTo(dialog)
    assert dialog._search_at == 0
    assert dialog.search_state.text()
    # Die Suche ist ein passiver Anlass: Der Rahmen bleibt so breit und darf
    # wachsen, um den Hinweis zu zeigen, nie schrumpfen (RM-487). Mit echten
    # Schriften (Linux-Runner) wuchs er dafür um 32 bis 105 Punkte.
    assert dialog.width() == search_window_size_before[0]
    assert dialog.height() >= search_window_size_before[1]
    requirement = dialog.search_requirement.text()
    assert requirement
    assert str(dialog._fields[selector_path].title) in requirement
    assert dialog.search_requirement.isVisibleTo(dialog)
    assert dialog.search_requirement.accessibleDescription() == requirement
    assert requirement in selector.accessibleDescription()

    unrelated = dialog._editors[unrelated_selector_path]
    assert isinstance(unrelated, QComboBox)
    assert dialog.tabs_toggle is not None
    if not dialog.tabs_toggle.isChecked():
        folded_frame = dialog.frameGeometry()
        QTest.mouseClick(dialog.tabs_toggle, Qt.MouseButton.LeftButton)
        for _ in range(3):
            qt_app.processEvents()
        assert dialog.tabs_toggle.isChecked()
        assert dialog.frameGeometry().topLeft() == folded_frame.topLeft()
    unrelated_group = GROUPS.index(unrelated_selector_path.partition(".")[0])
    dialog.tabs.setCurrentIndex(unrelated_group)
    for _ in range(3):
        qt_app.processEvents()
    assert unrelated.isVisibleTo(dialog)
    window_size_before_changes = (dialog.width(), dialog.height())
    frame_anchor_before_changes = dialog.frameGeometry().topLeft()
    unrelated.setFocus()
    unrelated.setCurrentIndex(unrelated.findData(unrelated_active_value))
    for _ in range(3):
        qt_app.processEvents()
    assert dialog.tabs.currentIndex() == unrelated_group
    assert unrelated.hasFocus()
    assert dialog.search_requirement.isVisibleTo(dialog)
    assert dialog._search_requirement_target == target_path
    # Eingeblendete Felder einer anderen Gruppe sind ein passiver Anlass: so
    # breit wie vorher, höher oder gleich, und wenn unten der Platz fehlt, nur
    # so weit hinauf wie nötig (RM-487) — nie seitwärts, nie tiefer.
    assert dialog.width() == window_size_before_changes[0]
    assert dialog.height() >= window_size_before_changes[1]
    assert dialog.frameGeometry().left() == frame_anchor_before_changes.x()
    assert dialog.frameGeometry().top() <= frame_anchor_before_changes.y()

    dialog.tabs.setCurrentIndex(GROUPS.index(selector_path.partition(".")[0]))
    for _ in range(3):
        qt_app.processEvents()
    selector.setCurrentIndex(selector.findData(active_value))
    for _ in range(3):
        qt_app.processEvents()

    assert selector.currentData() == active_value
    assert not dialog._labels[target_path].isHidden()
    assert target.isVisibleTo(dialog)
    assert dialog.highlighted() == target_path
    assert not dialog.search_requirement.isVisibleTo(dialog)
    assert dialog.search_requirement.text() == ""
    assert dialog._search_requirement_target == ""
    assert dialog.width() == window_size_before_changes[0]
    assert dialog.height() >= window_size_before_changes[1]
    assert dialog.frameGeometry().left() == frame_anchor_before_changes.x()
    assert dialog.frameGeometry().top() <= frame_anchor_before_changes.y()
    assert selector.accessibleDescription() == selector_description
    assert print_settings.read_path(dialog.settings, target_path) == target_before

    dialog.tabs.setCurrentIndex(unrelated_group)
    for _ in range(3):
        qt_app.processEvents()
    unrelated.setFocus()
    unrelated.setCurrentIndex(unrelated.findData("none"))
    for _ in range(3):
        qt_app.processEvents()
    assert dialog.tabs.currentIndex() == unrelated_group
    assert unrelated.hasFocus()
    assert not dialog.search_requirement.isVisibleTo(dialog)


def test_changing_a_selector_does_not_revisit_an_unrelated_search_hit(
    dialog: PrintSettingsDialog,
    qt_app: QApplication,
    request: pytest.FixtureRequest,
) -> None:
    """Eine Auswahl in Haftung hält den aktiven Suchtreffer unter Stützen nicht im Fokus."""
    from PySide6.QtTest import QTest

    def close_dialog() -> None:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()
        qt_app.processEvents()

    request.addfinalizer(close_dialog)
    dialog.show()
    for _ in range(3):
        qt_app.processEvents()
    # Die Suche steht hinter „Weitere Einstellungen" (RM-514): erst aufklappen,
    # dann einen Treffer vorn suchen, der die Klappe nicht braucht.
    assert dialog.tabs_toggle is not None
    assert not dialog.tabs_toggle.isChecked()
    folded_frame = dialog.frameGeometry()
    QTest.mouseClick(dialog.tabs_toggle, Qt.MouseButton.LeftButton)
    for _ in range(3):
        qt_app.processEvents()
    assert dialog.tabs_toggle.isChecked()
    assert dialog.frameGeometry().topLeft() == folded_frame.topLeft()
    dialog.search.setText("fill_density")
    QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    for _ in range(3):
        qt_app.processEvents()

    assert dialog._search_hits[dialog._search_at] == "infill.density"
    assert dialog._search_requirement_target == ""
    adhesion_group = GROUPS.index("adhesion")
    dialog.tabs.setCurrentIndex(adhesion_group)
    for _ in range(3):
        qt_app.processEvents()
    selector = dialog._editors["adhesion.kind"]
    target = dialog._editors["infill.density"]
    assert isinstance(selector, QComboBox)
    assert selector.isVisibleTo(dialog)
    window_size_after_open = (dialog.width(), dialog.height())
    frame_anchor_after_open = dialog.frameGeometry().topLeft()
    selector.setFocus()
    selector.setCurrentIndex(selector.findData("brim"))
    for _ in range(3):
        qt_app.processEvents()

    assert dialog.tabs.currentIndex() == adhesion_group
    assert selector.hasFocus()
    assert not target.hasFocus()
    assert dialog._search_requirement_target == ""
    assert (dialog.width(), dialog.height()) == window_size_after_open
    assert dialog.frameGeometry().topLeft() == frame_anchor_after_open


@pytest.mark.parametrize("outcome", ["unmatched-profile", "empty-inventory", "failure"])
def test_late_slicer_profile_outcomes_keep_the_outer_frame(
    qt_app: QApplication,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    """Ein Fremdprofil öffnet passiv; ein leerer Bestand bleibt ohne Größenwechsel."""
    from PySide6.QtTest import QTest

    from app.ui.style import ContentFitIntent

    dialog = PrintSettingsDialog(session, UiSettings())
    queued: list[ContentFitIntent] = []
    queue_refit = dialog._queue_refit

    def record_intent(intent: ContentFitIntent) -> None:
        queued.append(intent)
        queue_refit(intent)

    monkeypatch.setattr(dialog, "_queue_refit", record_intent)
    dialog.show()
    try:
        # Warten, nicht schließen: ``wait_for_workers`` setzt den Dialog auf
        # „wird geschlossen“, und die späte Antwort unten fiele weg.
        assert dialog.wait_for_slicers()
        dialog._leash.wait_all(2000)
        for _ in range(3):
            qt_app.processEvents()
        toggle = dialog.slicer_toggle
        assert toggle is not None
        if toggle.isChecked():
            QTest.mouseClick(toggle, Qt.MouseButton.LeftButton)
            for _ in range(3):
                qt_app.processEvents()
        assert not toggle.isChecked()
        folded_frame = dialog.frameGeometry()
        queued.clear()

        if outcome == "unmatched-profile":
            dialog._profiles_found(
                [
                    SlicerProfile(
                        path=Path("/x/Fremder Drucker.json"),
                        name="Fremder Drucker 0.6 nozzle",
                        kind="machine",
                        printer_model="Fremder Drucker",
                        nozzle=0.6,
                    )
                ]
            )
        elif outcome == "empty-inventory":
            dialog._profiles_found([])
        else:
            dialog._profiles_failed("Prüfungsfehler")
        for _ in range(4):
            qt_app.processEvents()

        passively_opened = outcome != "empty-inventory"
        assert toggle.isChecked() is passively_opened
        assert dialog.slicer_inner.isVisibleTo(dialog.slicer_box) is passively_opened
        # Passiv wächst höchstens die Höhe, nie die Breite (RM-487).
        assert dialog.frameGeometry().width() == folded_frame.width()
        if not passively_opened:
            assert dialog.frameGeometry() == folded_frame
        if passively_opened:
            assert queued and set(queued) == {"passive"}
        else:
            assert not queued

        for expected_checked in (not passively_opened, passively_opened):
            queued.clear()
            QTest.mouseClick(toggle, Qt.MouseButton.LeftButton)
            for _ in range(3):
                qt_app.processEvents()
            assert toggle.isChecked() is expected_checked
            assert queued and queued[-1] == "explicit"
            assert dialog.frameGeometry().topLeft() == folded_frame.topLeft()
    finally:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()
        qt_app.processEvents()


def test_changing_search_clears_the_pending_prerequisite_target(
    dialog: PrintSettingsDialog,
    qt_app: QApplication,
    request: pytest.FixtureRequest,
) -> None:
    """Eine neue Suche löst keine Rückkehr zum alten, inzwischen fremden Treffer aus."""
    from PySide6.QtTest import QTest

    def close_dialog() -> None:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()
        qt_app.processEvents()

    request.addfinalizer(close_dialog)
    dialog.show()
    # Die Suche steht hinter „Weitere Einstellungen" (RM-514).
    dialog.tabs_toggle.setChecked(True)
    for _ in range(3):
        qt_app.processEvents()
    target_path = "support.z_gap"
    dialog.search.setText(str(dialog._fields[target_path].title))
    QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    for _ in range(3):
        qt_app.processEvents()
    assert dialog._search_requirement_target == target_path

    dialog.search.setText("wall_loops")
    QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    for _ in range(3):
        qt_app.processEvents()
    assert dialog._search_hits[dialog._search_at] == "shell.wall_count"
    assert dialog._search_requirement_target == ""

    support_group = GROUPS.index("support")
    dialog.tabs.setCurrentIndex(support_group)
    for _ in range(3):
        qt_app.processEvents()
    selector = dialog._editors["support.style"]
    target = dialog._editors["shell.wall_count"]
    assert isinstance(selector, QComboBox)
    selector.setFocus()
    selector.setCurrentIndex(selector.findData("tree"))
    for _ in range(3):
        qt_app.processEvents()

    assert dialog.tabs.currentIndex() == support_group
    assert selector.hasFocus()
    assert not target.hasFocus()
    assert dialog._search_requirement_target == ""


def test_print_dialog_depth_keeps_the_frame_anchor_and_returns_collapsed_height(
    qt_app: QApplication, session: Session
) -> None:
    """Explizites Klappen passt die Höhe an; Zuklappen stellt sie am selben Anker zurück."""
    from PySide6.QtWidgets import QScrollArea

    dialog = PrintSettingsDialog(session, UiSettings())
    dialog.resize(660, 450)
    dialog.show()
    try:
        # Erst wenn die Slicersuche zurück ist, steht die zugeklappte Höhe:
        # Ihr Ergebnis darf den Rahmen passiv wachsen lassen (RM-487).
        assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
        for _ in range(8):
            qt_app.processEvents()
        width = dialog.width()
        collapsed_height = dialog.height()
        anchor = dialog.frameGeometry().topLeft()
        assert dialog.findChildren(QScrollArea) == [dialog._scroll]
        assert not dialog._scroll.isAncestorOf(dialog._buttons)
        for opened in (True, False, True, False):
            dialog.tabs_toggle.setChecked(opened)
            for _ in range(3):
                qt_app.processEvents()
            assert dialog.width() == width
            assert dialog.frameGeometry().topLeft() == anchor
            if not opened:
                assert dialog.height() == collapsed_height
            assert dialog._buttons.isVisibleTo(dialog)
    finally:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()


def test_print_actions_wrap_when_their_translated_names_exceed_the_window(
    qt_app: QApplication, session: Session
) -> None:
    """Lange Aktionsnamen dürfen das Fenster nicht über den Bildschirm verbreitern."""
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog.resize(620, 450)
    try:
        for button in dialog._buttons.buttons():
            button.setText(button.text() * 4)
        dialog._fit_buttons()
        assert dialog._buttons.orientation() == Qt.Orientation.Vertical
        assert dialog.width() == 620
    finally:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()


@pytest.mark.parametrize(
    ("material", "general"),
    [
        ("petg", profiles.DEFAULT_PRINTER),
        (profiles.DEFAULT_RESIN_MATERIAL, profiles.DEFAULT_RESIN_PRINTER),
    ],
    ids=["fdm", "resin"],
)
def test_a_project_with_a_printer_from_another_computer_opens_with_the_general_printer(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    material: str,
    general: str,
) -> None:
    """Ein Projekt mit einem Drucker, den dieser Rechner nicht kennt, öffnet.

    Übernommen aus dem Paket „dialoge" der Durchsicht 0.5.0: ``Session.profile``
    warf ``ValidationError``, ``_update_header`` warf im Slot, die Auswertung
    meldete modal „Dieses Druckerprofil ist nicht bekannt.", und der
    Druckdialog öffnete nicht. Gerechnet wird mit dem allgemeinen Drucker
    desselben Verfahrens; der Bericht nennt ihn und bietet die Wahl an, und der
    Druckdialog zeigt den Drucker, mit dem tatsächlich gerechnet wird — nicht
    den ersten der Liste.
    """
    import sys

    from app.core.errors import CHOOSE_PRINTER
    from app.core.scene.project import save
    from app.ui.main_window import MainWindow

    raised: list[BaseException] = []
    monkeypatch.setattr(sys, "excepthook", lambda _kind, error, _trace: raised.append(error))
    sender = Session()
    sender.project.document.printer = "vom-anderen-rechner"
    sender.project.document.material = material
    path = tmp_path / "fremd.p3d"
    save(sender.project, path)

    window = MainWindow(Session(), UiSettings())
    failures: list[object] = []
    window.session.failed.connect(failures.append)
    try:
        window.open_path(path)
        assert window.session.wait_for_idle(60_000)
        QApplication.processEvents()
        assert not raised, raised
        assert not failures, failures
        assert window.session.project.document.printer == "vom-anderen-rechner"
        assert window.session.profile.printer.id == general
        said = [
            entry
            for entry in window.session.last_result.scene.report.findings
            if entry.code == "profile.printer_missing"
        ]
        assert len(said) == 1
        assert CHOOSE_PRINTER in said[0].suggestions
        assert str(profiles.printer(general).title) in str(said[0].message)

        dialog = PrintSettingsDialog(window.session, UiSettings(), window)
        try:
            assert dialog.printer_choice.currentData() == general
        finally:
            dialog.close()
    finally:
        window.wait_for_workers()
        window.close()


def test_the_filament_panel_keeps_material_identity_and_marks_the_right_override(
    qt_app: QApplication,
) -> None:
    """Gleich benanntes PLA und PETG bleiben zwei Spulen mit getrennten Druckwerten."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.ui.filament_picker import FilamentPanel

    first = MaterialSlot(index=1, name="Schwarz", colour=(0.0, 0.0, 0.0), material_type="PLA")
    second = replace(first, index=2, material_type="PETG")
    settings = print_settings.resolve(profiles.make_profile())
    settings = handover.with_slot_override(
        settings,
        second,
        SlotOverride(
            name=second.name,
            colour=second.colour,
            temperature=replace(settings.temperature, nozzle=240),
        ),
    )
    panel = FilamentPanel()
    mesh = MeshData.of(trimesh.creation.box((10, 10, 10)))
    mesh = replace(mesh, slots=(1, 2) * (mesh.triangle_count // 2))
    panel.show_scene(
        [SceneObject(id="obj_1", name="Teil", mesh=mesh, material_slots=[first, second])], settings
    )
    assert len(panel._used) == 2
    assert {entry[0].material_type: entry[4] for entry in panel._used} == {
        "PLA": False,
        "PETG": True,
    }


def test_old_filament_values_need_an_explicit_transfer_before_binding(qt_app: QApplication) -> None:
    """Öffnen verändert nichts; der sichtbare Übernahmeknopf füllt nur den offenen Dialog."""
    from app.core.export.threemf import slot_identity

    slot = MaterialSlot(index=1, name="Schwarz", colour=(0.0, 0.0, 0.0), material_type="PETG")
    settings = print_settings.resolve(profiles.make_profile())
    legacy = SlotOverride(
        name=slot.name, colour=slot.colour, temperature=replace(settings.temperature, nozzle=240)
    )
    settings = replace(settings, slot_overrides=(legacy,))
    dialog = FilamentOverrideDialog(slot, settings)
    assert dialog.override() is None
    assert dialog.legacy_values_button.isEnabled()
    dialog.legacy_values_button.click()
    adopted = dialog.override()
    assert adopted is not None and adopted.key == slot_identity(slot)
    assert adopted.temperature is not None and adopted.temperature.nozzle == 240
    assert settings.slot_overrides == (legacy,), "erst Bestätigen bindet die Werte im Projekt"
    dialog.reject()
    assert handover.override_for(settings, slot) is None


def test_changing_plates_preserves_filament_profile_identity(session: Session) -> None:
    """Die weiße Spule behält auf ihrer Einzelplatte dasselbe Profil wie in der Gesamtansicht."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene

    slots = [
        MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0)),
        MaterialSlot(index=2, name="Weiß", colour=(1.0, 1.0, 1.0)),
    ]
    session.last_result = EvaluationResult(
        scene=Scene(
            objects={
                f"obj_{index + 1}": SceneObject(
                    id=f"obj_{index + 1}",
                    name=slot.name,
                    plate=index,
                    mesh=MeshData(trimesh.creation.box(), slots=(slot.index,) * 12),
                    material_slots=[slot],
                )
                for index, slot in enumerate(slots)
            }
        )
    )
    made = PrintSettingsDialog(session, UiSettings())
    made.settings = replace(made.settings, slot_profiles=("Rot-Profil", "Weiß-Profil"))
    for plate, expected in (
        (1, ("Weiß-Profil",)),
        (0, ("Rot-Profil",)),
        (None, ("Rot-Profil", "Weiß-Profil")),
    ):
        index = made.plate_choice.findData(plate)
        made.plate_choice.setCurrentIndex(index)
        made.plate_choice.activated.emit(index)
        assert made._profiles_for(made._plate_slots()) == expected


@pytest.mark.parametrize("stored_state", ["none", "saved", "legacy", "bound"])
def test_plate_job_adds_its_identity_without_replacing_project_process_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stored_state: str
) -> None:
    """Der echte Setter ändert Metadaten, aber weder Druckgrundlage noch Auswertung."""
    import trimesh

    from app.core.export import manufacturer, threemf
    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SlotProfileBinding
    from app.ui import print_settings_dialog as module
    from app.ui.main_window import MainWindow

    session = Session()
    document = session.project.document
    document.printer = "centauri-carbon-2"
    document.material = "pla"
    profile = session.profile
    saved = replace(
        print_settings.resolve(profile),
        layers=replace(
            print_settings.resolve(profile).layers,
            layer_height=0.20,
            line_width=0.45,
        ),
    )
    slots = (
        MaterialSlot(0, "Schwarz", (0.0, 0.0, 0.0), None, "PLA"),
        MaterialSlot(1, "Rot", (1.0, 0.0, 0.0), None, "PETG"),
    )
    profile_names = ("PLA-Werkstatt", "PETG-Werkstatt")
    bindings = tuple(
        SlotProfileBinding(
            profile_name=name,
            name=slot.name,
            colour=slot.colour,
            material=slot.material,
            material_type=slot.material_type,
        )
        for slot, name in zip(slots, profile_names, strict=True)
    )
    if stored_state in {"legacy", "bound"}:
        saved = replace(
            saved,
            slot_profiles=profile_names,
            slot_profile_bindings=bindings if stored_state == "bound" else None,
        )
    document.print_settings = None if stored_state == "none" else saved
    body = SceneObject(
        id="obj_1",
        name="Zweifarbiges Teil",
        mesh=MeshData(trimesh.creation.box(), slots=(0,) * 6 + (1,) * 6),
        material_slots=list(slots),
    )
    result = EvaluationResult(scene=Scene(objects={body.id: body}))
    session.last_result = result
    session.result_current = True
    session._evaluation_settings = saved
    # Der Dialog kann bereits die wirksame Herstellergrundlage zeigen. Beim
    # bloßen Öffnen der Platte ist dieser Unterschied keine Kundenänderung.
    shown = replace(
        saved,
        layers=replace(saved.layers, layer_height=0.12, line_width=0.42),
    )
    writes = []
    foundation_reads = []
    titles = []
    signal_errors = []
    # Nur die Anzeigeziele sind Doppel. Der Signalweg nutzt die echten
    # _on_project-, _update_header- und Grundlagenmethoden ohne ein Widget.
    window = SimpleNamespace(
        session=session,
        settings=UiSettings(),
        # Dasselbe Projekt: Der Anschluss räumt keine Tour und keinen Download ab.
        _tour_project=session.project,
        _close_requested=False,
        _foundation_pending=None,
        _foundation_cache=None,
        _map_request=None,
        _announcement_document=document,
        _follow_the_run_in_the_report=lambda: None,
        _split_points=(),
        _quiet_host=None,
        _drop_feature_preview=lambda: None,
        viewport=SimpleNamespace(show_protected=lambda _protected: None),
        _pending_split_reveal=frozenset(),
        _created_to_choose=(),
        _refresh_parameters=lambda: None,
        history_panel=SimpleNamespace(show_document=lambda *_args: None),
        chat=SimpleNamespace(show_document=lambda _document: None),
        _refresh_applied_bar=lambda: None,
        setWindowTitle=titles.append,
        header=SimpleNamespace(
            show_project=lambda *_args: None,
            show_profile=lambda *_args: None,
            show_target=lambda *_args: None,
        ),
        _update_review_status=lambda: None,
        _fit_toolbar=lambda: None,
        _update_actions=lambda: None,
        filaments=SimpleNamespace(show_scene=lambda *_args: None),
        _start_print_findings=lambda *_args: None,
        _click_after_evaluation=None,
        _click_refusal=None,
    )
    window._check_waiting_click = lambda: MainWindow._check_waiting_click(window)
    window._withdraw_click_refusal = lambda **kwargs: MainWindow._withdraw_click_refusal(
        window, **kwargs
    )
    window._update_header = lambda: MainWindow._update_header(window)
    window.effective_print_settings = lambda: MainWindow.effective_print_settings(window)
    window._update_facts = lambda: foundation_reads.append(window.effective_print_settings())
    window._print_foundation = lambda quality: MainWindow._print_foundation(window, quality)
    window._foundation_key = lambda quality: MainWindow._foundation_key(window, quality)
    foundation_key = MainWindow._foundation_key(window, shown.quality)
    window._foundation_cache = (foundation_key, manufacturer.Foundation(settings=shown))
    starts: list[tuple[object, object]] = []
    runs: list[bool] = []

    def start_foundation(key: object, quality: object) -> None:
        starts.append((key, quality))
        window._foundation_pending = key

    window._start_foundation = start_foundation
    monkeypatch.setattr(session, "evaluate_async", lambda: runs.append(True))
    dialog = SimpleNamespace(
        session=session,
        settings=shown,
        _opened_with=shown,
        _handover_project_id="",
        _plate_slots=lambda: slots,
        _profiles_for=lambda _slots: saved.slot_profiles,
    )
    before = session.profile
    generation = session.result_generation

    def on_project_changed() -> None:
        writes.append(document.print_settings)
        try:
            MainWindow._on_project(window)
        except Exception as error:
            # PySide reicht Ausnahmen eines Signals nicht an emit() zurück.
            signal_errors.append(error)

    session.projectChanged.connect(on_project_changed)
    try:
        job = module.PrintSettingsDialog._plate_job(
            dialog,
            (body,),
            (0,),
            tmp_path,
            "Projekt",
            handover.SlicerSetup(Path("slicer"), "orca"),
        )
        first_stored = document.print_settings
        second_job = module.PrintSettingsDialog._plate_job(
            dialog,
            (body,),
            (0,),
            tmp_path,
            "Projekt",
            handover.SlicerSetup(Path("slicer"), "orca"),
        )
    finally:
        session.projectChanged.disconnect(on_project_changed)

    after = session.profile
    assert signal_errors == [], "der echte projectChanged-Anschluss muss vollständig durchlaufen"
    assert job.settings.inventory_project_id
    assert second_job.settings.inventory_project_id == job.settings.inventory_project_id
    assert document.print_settings is first_stored, (
        "weitere Aufträge schreiben die Metadaten nicht neu"
    )
    assert job.settings.layers == shown.layers, "die Übergabedatei nutzt die sichtbaren Dialogwerte"
    assert job.profile == before
    assert job.slot_profiles == (
        {
            threemf.slot_identity(slots[0]): "PLA-Werkstatt",
            threemf.slot_identity(slots[1]): "PETG-Werkstatt",
        }
        if stored_state in {"legacy", "bound"}
        else {}
    )
    assert second_job.slot_profiles == job.slot_profiles
    assert dialog.settings == replace(shown, inventory_project_id=job.settings.inventory_project_id)
    assert dialog._opened_with == dialog.settings, (
        "die Kennung wird auch im Vergleichsstand ohne Änderung der Prozesswerte nachgeführt"
    )
    assert not module.PrintSettingsDialog.has_changes(dialog), (
        "allein die interne Kennung darf beim Schließen keine Einstellungen speichern"
    )
    assert after == before, "der Prozessvergleich für eine spätere Auswertung bleibt unverändert"
    assert MainWindow._foundation_key(window, shown.quality) == foundation_key, (
        "projectChanged darf keine neue Druckgrundlage und damit keinen Neulauf anfordern"
    )
    MainWindow._print_foundation(window, shown.quality)
    for key, _quality in starts:
        MainWindow._foundation_found(window, key, manufacturer.Foundation(settings=shown))
    assert starts == [], "eine Kennungsänderung darf keine neue Druckgrundlage anfordern"
    assert runs == [], "ohne neue Grundlage erreicht kein Auslöser den Verlaufslauf"
    assert session.last_result is result and session.result_generation == generation
    if stored_state != "none":
        expected = replace(saved, inventory_project_id=job.settings.inventory_project_id)
        if stored_state == "legacy":
            expected = replace(expected, slot_profile_bindings=bindings)
        assert document.print_settings == expected, (
            "Prozesswerte bleiben gleich; alte Filamentplätze werden einmalig nachgebunden"
        )
        assert writes == [expected]
        assert len(foundation_reads) == 1, "projectChanged erreicht die echte Grundlagenabfrage"
        assert session.modified, (
            "die neue Kennung wird als ungespeicherte Dokumentänderung markiert"
        )
        assert len(titles) == 2, "Dokument- und Kopfzeilenanschluss aktualisieren den Titel"
    else:
        assert document.print_settings is None, (
            "ohne gespeicherte Werte bleibt das Projekt unverändert"
        )
        assert writes == []
        assert foundation_reads == []
        assert not session.modified


def test_foundation_arrival_runs_history_when_process_values_changed() -> None:
    """Die spätere Grundlage kann bei veränderten Prozesswerten einen Lauf auslösen."""
    from types import SimpleNamespace

    from app.core.export import manufacturer
    from app.core.knowledge import profiles
    from app.core.knowledge.profiles import for_process
    from app.core.types import PrintSettings
    from app.ui.main_window import MainWindow

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    previous = print_settings.resolve(profile)
    previous = replace(
        previous,
        layers=replace(previous.layers, layer_height=0.20, line_width=0.45),
    )
    current = replace(
        previous,
        layers=replace(previous.layers, layer_height=0.12, line_width=0.42),
    )
    document = SimpleNamespace(print_settings=current)

    class SessionState:
        def __init__(self) -> None:
            self.project = SimpleNamespace(document=document)
            self.last_result = object()
            self.evaluation_profile = for_process(profile, previous)

        @property
        def profile(self):
            return for_process(profile, document.print_settings)

        def evaluation_follows(self, settings: PrintSettings) -> bool:
            return Session.evaluation_follows(self, settings)

    session = SessionState()
    runs: list[bool] = []
    session.evaluate_async = lambda: runs.append(True)
    key = ("grundlage",)
    window = SimpleNamespace(
        session=session,
        _foundation_pending=key,
        _foundation_cache=None,
        _close_requested=False,
        _foundation_key=lambda _quality: key,
        effective_print_settings=lambda: current,
    )

    MainWindow._foundation_found(window, key, manufacturer.Foundation(settings=current))

    assert runs == [True], "abweichende Prozesswerte laufen tatsächlich bis evaluate_async"


def test_plate_job_keeps_a_real_dialog_choice_for_persistence_and_handover(
    tmp_path: Path,
) -> None:
    """Eine echte Wahl bleibt im Dialog änderbar und wird an den Auftrag übergeben."""
    from types import SimpleNamespace

    from app.core.knowledge import profiles
    from app.core.types import PrintSettings
    from app.ui import print_settings_dialog as module

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    opened = print_settings.resolve(profile)
    changed = print_settings.with_choice(opened, "shell.wall_count", opened.shell.wall_count + 1)
    document = SimpleNamespace(print_settings=None)
    writes: list[PrintSettings] = []
    session = SimpleNamespace(
        profile=profile,
        last_result=None,
        project=SimpleNamespace(document=document),
        set_print_settings=lambda settings: writes.append(settings),
    )
    dialog = SimpleNamespace(
        session=session,
        settings=changed,
        _opened_with=opened,
        _handover_project_id="",
        _plate_slots=lambda: (),
        _profiles_for=lambda _slots: (),
    )

    job = module.PrintSettingsDialog._plate_job(
        dialog,
        (),
        (0,),
        tmp_path,
        "Projekt",
        handover.SlicerSetup(Path("slicer"), "orca"),
    )

    assert job.settings.shell.wall_count == changed.shell.wall_count
    assert job.settings.inventory_project_id
    assert module.PrintSettingsDialog.has_changes(dialog), "die echte Wahl bleibt speicherpflichtig"
    assert writes == [], "nur der Dialogabschluss speichert eine echte Nutzereinstellung"


@pytest.mark.parametrize("stored_state", ["none", "saved", "identified", "legacy", "bound"])
@pytest.mark.parametrize("chosen", [False, True])
def test_plate_job_keeps_inventory_identity_through_real_close_and_reopening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stored_state: str, chosen: bool
) -> None:
    """Der echte Abschluss behält Kennung, eigene Wahl und Lager-Fingerprint."""
    from contextlib import nullcontext

    import trimesh

    from app.core import filament_usage
    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene
    from app.ui import main_window
    from app.ui import print_settings_dialog as module

    session = Session()
    document = session.project.document
    document.printer = "centauri-carbon-2"
    document.material = "pla"
    slots = (
        MaterialSlot(0, "Schwarz", (0.0, 0.0, 0.0), None, "PLA"),
        MaterialSlot(1, "Rot", (1.0, 0.0, 0.0), None, "PETG"),
    )
    body = SceneObject(
        id="obj_1",
        name="Zweifarbiges Teil",
        mesh=MeshData(trimesh.creation.box(), slots=(0,) * 6 + (1,) * 6),
        material_slots=list(slots),
    )
    session.last_result = EvaluationResult(scene=Scene(objects={body.id: body}))
    saved = print_settings.resolve(session.profile)
    if stored_state == "identified":
        saved = replace(saved, inventory_project_id="persistente-projektkennung")
    if stored_state in {"legacy", "bound"}:
        saved = replace(saved, slot_profiles=("PLA-Werkstatt", "PETG-Werkstatt"))
        if stored_state == "bound":
            saved = handover.bind_slot_profiles(saved, slots)
    document.print_settings = None if stored_state == "none" else saved
    signal = SimpleNamespace(connect=lambda *_args: None)

    def make_dialog() -> SimpleNamespace:
        stored = document.print_settings
        base = print_settings.resolve(session.profile)
        opened = print_settings.on_base(stored, base) if stored is not None else base
        dialog = SimpleNamespace(
            session=session,
            settings=opened,
            _opened_with=opened,
            _handover_project_id=opened.inventory_project_id,
            _plate_slots=lambda: slots,
            slice_comparison=None,
            sliced=signal,
            reported=signal,
            handedOver=signal,
            setupRequested=signal,
            filamentsRequested=signal,
            usage_notice=SimpleNamespace(changed=signal, requests={}),
            scene_action=None,
            take_scene_action=lambda: None,
            deleteLater=lambda: None,
        )
        dialog._profiles_for = lambda _slots: dialog.settings.slot_profiles
        dialog.has_changes = lambda: module.PrintSettingsDialog.has_changes(dialog)
        return dialog

    setup = handover.SlicerSetup(Path("slicer"), "orca")

    def plate_job(dialog: SimpleNamespace):
        return module.PrintSettingsDialog._plate_job(
            dialog, (body,), (0,), tmp_path, "Projekt", setup
        )

    dialog = make_dialog()
    if chosen:
        dialog.settings = print_settings.with_choice(
            dialog.settings, "shell.wall_count", dialog.settings.shell.wall_count + 1
        )
    jobs = []
    during = []
    changed = []

    def execute() -> int:
        jobs.append(plate_job(dialog))
        during.append(document.print_settings)
        changed.append(dialog.has_changes())
        return 0

    dialog.exec = execute
    window = SimpleNamespace(
        session=session,
        settings=UiSettings(),
        filaments=SimpleNamespace(return_to_print_button=SimpleNamespace(hide=lambda: None)),
        usage_notice=SimpleNamespace(offer=lambda *_args, **_kwargs: None),
        _end_inserting_for_output=lambda: None,
        _gcode_returned=lambda *_args: None,
        _slicer_findings=lambda *_args: None,
        _count_delivery=lambda *_args: None,
        _refresh_inventory=lambda: None,
        _store_settings=lambda: None,
        _offer_support=lambda: None,
    )
    monkeypatch.setattr(main_window, "PrintSettingsDialog", lambda *_args: dialog)
    monkeypatch.setattr(main_window, "waiting", nullcontext)
    monkeypatch.setattr(main_window, "ensure_print_disclosure", lambda *_args: None)

    main_window.MainWindow.action_print_settings(window)

    first = jobs[0]
    assert changed == [chosen], "Metadaten sind keine Wahl; eine echte Änderung bleibt eine"
    if stored_state == "none":
        assert during == [None], "ein Plattenauftrag führt keinen Prozesssatz ins Projekt ein"
    else:
        assert during[0] is not None
        expected = replace(saved, inventory_project_id=first.settings.inventory_project_id)
        if stored_state == "legacy":
            expected = handover.bind_slot_profiles(expected, slots)
        assert during == [expected], "vor dem Abschluss bleiben gespeicherte Prozesswerte erhalten"
    after_close = document.print_settings
    if chosen:
        assert after_close is not None
        assert after_close.inventory_project_id == first.settings.inventory_project_id, (
            "der echte Dialogabschluss darf die neue Kennung nicht wieder löschen"
        )
        assert after_close.chosen == frozenset({"shell.wall_count"})
        assert after_close.shell.wall_count == first.settings.shell.wall_count
    else:
        assert after_close is during[0], "reine Metadaten lösen beim Abschluss keinen Setter aus"

    reopened = make_dialog()
    assert not reopened.has_changes()
    second = plate_job(reopened)
    first_usage = filament_usage.prepare(first.objects, first.settings, first.profile, "Projekt")
    second_usage = filament_usage.prepare(
        second.objects, second.settings, second.profile, "Projekt"
    )
    assert first_usage and second_usage
    assert first.profile == second.profile
    assert replace(
        handover.bind_slot_profiles(first.settings, slots), inventory_project_id=""
    ) == replace(handover.bind_slot_profiles(second.settings, slots), inventory_project_id="")
    if stored_state != "none" or chosen:
        assert second.settings.inventory_project_id == first.settings.inventory_project_id
        assert first_usage[0].fingerprint == second_usage[0].fingerprint, (
            "derselbe Druck behält nach dem Wiederöffnen seinen echten Lager-Fingerprint"
        )
        if stored_state == "identified":
            assert first.settings.inventory_project_id == "persistente-projektkennung"
    else:
        assert after_close is None, "ohne eigene Wahl bleibt der None-Vertrag unverändert"
        assert second.settings.inventory_project_id != first.settings.inventory_project_id
        assert first_usage[0].fingerprint != second_usage[0].fingerprint


@pytest.mark.parametrize("same_name", [False, True])
def test_plate_job_preserves_global_profile_positions_and_full_material_identity(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, same_name: bool
) -> None:
    """Die sichtbare Profilwahl muss auch am ausgegebenen Slot des Laufs ankommen."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene
    from app.ui import print_settings_dialog as module

    slots = [
        MaterialSlot(0, "Schwarz" if same_name else "PLA", (0.0, 0.0, 0.0), None, "PLA"),
        MaterialSlot(0, "Schwarz" if same_name else "PETG", (0.0, 0.0, 0.0), None, "PETG"),
    ]
    objects = [
        SceneObject(
            id=f"body-{index}",
            name=slot.name,
            mesh=MeshData(trimesh.creation.box()),
            plate=0 if same_name else index,
            material_slots=[slot],
        )
        for index, slot in enumerate(slots)
    ]
    session.last_result = EvaluationResult(scene=Scene(objects={body.id: body for body in objects}))
    made = PrintSettingsDialog(session, UiSettings())
    made.settings = replace(
        made.settings, slot_profiles=("Profile PLA", "Profile PETG"), inventory_project_id="review"
    )
    if not same_name:
        index = made.plate_choice.findData(1)
        made.plate_choice.setCurrentIndex(index)
        made.plate_choice.activated.emit(index)
    monkeypatch.setattr(
        module, "write_assembly", lambda *_args, **_kwargs: (tmp_path / "one.3mf", [])
    )
    setup = handover.SlicerSetup(Path("slicer"), "orca")
    plate = 0 if same_name else 1
    job = made._plate_job(objects, (plate,), tmp_path, "Projekt", setup)
    run = module._prepare_plate(job, plate)
    expected = (
        {"PLA": "Profile PLA", "PETG": "Profile PETG"} if same_name else {"PETG": "Profile PETG"}
    )
    assert {slot.material_type: slot.material for slot in run.slots} == expected
    if not same_name:
        made.settings = replace(made.settings, slot_profiles=("Profile PLA", ""))
        direct = made._plate_run(objects, plate, tmp_path, "Projekt", setup)
        assert direct.slots[0].material is None, "keine Wahl auf Platte zwei erbt nicht Platte eins"


def test_standalone_plate_file_cli_and_usage_share_the_same_local_tools(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine echte 3MF trägt dieselbe lokale Belegung und Profile wie der CLI-Lauf."""
    import xml.etree.ElementTree as ET
    import zipfile

    import trimesh

    from app.core.export import threemf
    from app.core.filament_usage import from_gcode, prepare
    from app.core.geom.mesh import MeshData
    from app.ui import print_settings_dialog as module

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    slots = [
        MaterialSlot(0, "Andere Platte", None, None, "ABS"),
        MaterialSlot(0, "Schwarz", (0.0, 0.0, 0.0), None, "PLA"),
        MaterialSlot(0, "Schwarz", (0.0, 0.0, 0.0), None, "PETG"),
    ]
    objects = tuple(
        SceneObject(
            id=f"body-{index}",
            name=f"Teil {index}",
            mesh=MeshData(trimesh.creation.box((10, 10, 10))),
            plate=0 if index == 0 else 1,
            material_slots=[slot],
        )
        for index, slot in enumerate(slots)
    )
    names = ("Profile ABS", "Profile PLA", "Profile PETG")
    files = {}
    for kind, name in zip(("ABS", "PLA", "PETG"), names, strict=True):
        path = tmp_path / f"{kind}.json"
        path.write_text(
            json.dumps({"name": name, "filament_vendor": [f"Maker {kind}"]}), encoding="utf-8"
        )
        files[name] = path
    monkeypatch.setattr(
        handover,
        "profile_file",
        lambda name, _setup, kind: files.get(name) if kind == "filament" else None,
    )
    settings = replace(
        print_settings.resolve(profile), slot_profiles=names, inventory_project_id="review"
    )
    setup = handover.SlicerSetup(Path("slicer"), "orca")
    job = module._PlateJob(
        objects,
        (1,),
        tmp_path,
        "Projekt",
        setup,
        settings,
        profile,
        {threemf.slot_identity(slot): name for slot, name in zip(slots, names, strict=True)},
    )
    run = module._prepare_plate(job, 1)
    with zipfile.ZipFile(run.model) as container:
        root = ET.fromstring(container.read(threemf.MODEL_PATH))
        embedded = json.loads(container.read(threemf.PROJECT_SETTINGS_PATH))
    ns = threemf.CORE_NAMESPACE
    mesh_objects = root.findall(f".//{{{ns}}}resources/{{{ns}}}object")
    assignments = [
        {int(face.attrib["p1"]) for face in body.findall(f".//{{{ns}}}triangle")}
        for body in mesh_objects
    ]
    assert assignments == [{0}, {1}]
    assert [slot.index for slot in run.slots] == [0, 1]
    assert [slot.material for slot in run.slots] == ["Profile PLA", "Profile PETG"]
    assert embedded["filament_vendor"] == ["Maker PLA", "Maker PETG"]
    assert embedded["filament_type"] == ["PLA", "PETG"]
    request = prepare(objects, settings, profile, "Projekt", slots_by_plate={1: run.slots})[1]
    assert [line.slot for line in request.lines] == list(run.slots)
    measured = from_gcode(request, gcode.GcodeMetrics(filament_grams_by_tool=(47.0, 6.0)))
    assert [line.grams for line in measured.lines] == pytest.approx([47.0, 6.0])
    assert request.fingerprint == prepare(objects, settings, profile, "Projekt")[1].fingerprint
    cli_folder = tmp_path / "cli"
    cli_folder.mkdir()
    config = handover.write_config(settings, profile, setup, cli_folder, run.slots)
    cli_profiles = [json.loads(path.read_text(encoding="utf-8")) for path in config.filaments]
    assert [entry["name"] for entry in cli_profiles] == embedded["filament_settings_id"]
    assert [entry["filament_type"][0] for entry in cli_profiles] == embedded["filament_type"]


def test_a_new_printer_does_not_keep_a_known_foreign_machine_profile(session: Session) -> None:
    """Eine frühere Wahl für Centauri ist beim Wechsel zu A1 keine Wahl für den neuen Drucker."""
    session.change_scene_profile("centauri-carbon-2", "pla")
    old = SlicerProfile(
        Path("old.json"),
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
    )
    new = SlicerProfile(
        Path("new.json"),
        "Bambu Lab A1 0.4 nozzle",
        "machine",
        printer_model="Bambu Lab A1",
        nozzle=0.4,
    )
    made = PrintSettingsDialog(
        session,
        UiSettings(
            slicer_machine_profile=str(old.path), slicer_profile_printer="centauri-carbon-2"
        ),
    )
    made._profiles_found([old, new])
    assert made.machine_choice.currentData() == str(old.path)
    made.printer_choice.setCurrentIndex(made.printer_choice.findData("bambu-a1"))
    assert session.wait_for_idle()
    assert made.machine_choice.currentData() == str(new.path)


@pytest.mark.parametrize("change", ["temperature", "quality", "machine", "process"])
def test_a_changed_print_job_cannot_save_its_previous_gcode(
    dialog: PrintSettingsDialog, tmp_path: Path, change: str
) -> None:
    """Eingabefelder und Profilauswahl entwerten die vorherige Druckdatei gemeinsam."""
    previous = tmp_path / "previous.gcode"
    previous.write_text("; vorheriger Auftrag\n", encoding="utf-8")
    dialog._gcode = [previous]
    dialog._release_the_save()
    if change == "temperature":
        field = dialog._editors["temperature.nozzle"]
        field.setValue(field.value() + 10)
    elif change == "quality":
        dialog.quality.setCurrentIndex((dialog.quality.currentIndex() + 1) % dialog.quality.count())
    else:
        box = dialog.machine_choice if change == "machine" else dialog.process_choice
        box.addItem("Anderes Profil", "different-profile.json")
        box.setCurrentIndex(box.count() - 1)
    assert not dialog._gcode
    assert not dialog.save_button.isEnabled()
    assert previous.is_file(), "die frühere Ausgabe wird entwertet, nicht gelöscht"


def test_adopting_an_own_filament_includes_its_installed_base(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der sichtbare Übernahmeweg liest Temperatur und Bett aus dem Herstellerbestand."""
    from app.core.export import slicer_profiles as sp

    executable = tmp_path / "OrcaSlicer" / "orca-slicer.exe"
    installed = executable.parent / "resources" / "profiles"
    base = installed / "Vendor" / "filament" / "base.json"
    user = tmp_path / "settings" / "OrcaSlicer" / "user" / "default"
    own = user / "filament" / "Meine Spule.json"
    for path, data in (
        (
            base,
            {
                "name": "PETG base",
                "filament_type": ["PETG"],
                "nozzle_temperature": ["250"],
                "hot_plate_temp": ["80"],
            },
        ),
        (own, {"name": "Meine Spule", "inherits": "PETG base", "filament_flow_ratio": ["0.96"]}),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(sp, "install_root", lambda _executable: installed)
    monkeypatch.setattr(sp, "user_roots", lambda _flavour, _executable: [user])
    dialog._slicer_path = executable
    dialog._filament_profile = str(own)
    dialog._filament_title = "Meine Spule"
    dialog._adopt_filament_values()
    assert dialog.settings.temperature.nozzle == 250
    assert dialog.settings.temperature.bed == 80
    assert dialog.settings.filament.flow_ratio == pytest.approx(0.96)
    assert "Meine Spule" in dialog.state.text()


def test_adopting_a_prusa_filament_keeps_the_selected_bundle_section(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Übernahmeknopf liest das gewählte Filament statt nur dessen gemeinsamer INI."""
    from app.core.export import slicer_profiles as sp

    executable = tmp_path / "PrusaSlicer" / "prusa-slicer.exe"
    root = executable.parent / "resources" / "profiles"
    root.mkdir(parents=True)
    (root / "PrusaResearch.ini").write_text(
        "[filament:Prusament PLA]\nfilament_type = PLA\ntemperature = 210\n"
        "[filament:Prusament PLA Silk]\ninherits = Prusament PLA\ntemperature = 217\n"
        "filament_max_volumetric_speed = 5\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    chosen = sp.profile_by_name(executable, "prusa", "Prusament PLA Silk", "filament")
    assert chosen is not None
    dialog._slicer_path = executable
    before = dialog.settings
    dialog._remember_filament_profile(chosen)
    assert dialog.settings == before, "das Zuordnen allein übernimmt keine Werte"

    dialog.adopt_filament.click()

    assert dialog.settings.temperature.nozzle == 217
    assert dialog.settings.filament.max_flow == pytest.approx(5.0)
    assert "Prusament PLA Silk" in dialog.state.text()
    dialog._forget_filament_profile()


def test_adopted_values_leave_with_their_filament(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review Stufe A+B, H12: Ohne Herstellergrundlage macht *Werte
    übernehmen* die Werte zur eigenen Wahl. Wechselte das Filament, blieben
    sie stehen — ein PETG fuhr mit den Temperaturen des PLA davor. Was noch
    genau dem vorigen Profil gleicht, geht mit ihm; eine spätere eigene
    Änderung bleibt."""
    from app.core.export import slicer_profiles as sp

    executable = tmp_path / "PrusaSlicer" / "prusa-slicer.exe"
    root = executable.parent / "resources" / "profiles"
    root.mkdir(parents=True)
    (root / "PrusaResearch.ini").write_text(
        "[filament:Prusament PLA]\nfilament_type = PLA\ntemperature = 218\n"
        "filament_max_volumetric_speed = 15\n"
        "[filament:Prusament PETG]\nfilament_type = PETG\ntemperature = 240\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    pla = sp.profile_by_name(executable, "prusa", "Prusament PLA", "filament")
    petg = sp.profile_by_name(executable, "prusa", "Prusament PETG", "filament")
    assert pla is not None and petg is not None
    dialog._slicer_path = executable
    dialog._remember_filament_profile(pla)
    dialog.adopt_filament.click()
    assert "temperature.nozzle" in dialog.settings.chosen
    dialog.settings = print_settings.with_choice(dialog.settings, "filament.max_flow", 12.0)

    dialog._remember_filament_profile(petg)

    assert "temperature.nozzle" not in dialog.settings.chosen, "das PLA ist gegangen"
    assert dialog.settings.temperature.nozzle != 218
    assert dialog.settings.filament.max_flow == pytest.approx(12.0), "die eigene Änderung bleibt"
    dialog._forget_filament_profile()
    assert not dialog.adopt_filament.isEnabled()


@pytest.fixture
def dialog(qt_app: QApplication, session: Session) -> PrintSettingsDialog:
    """Der Dialog im **fertigen** Zustand — Slicersuche abgewartet.

    Seit dem 13.09.2026 läuft ``discover.find_programs`` in einem Arbeiter
    (§2.8): Der Dialog erscheint sofort mit dem gemerkten Slicer, und was
    installiert ist, kommt nach. Wer die Erhebung nicht abwartet, prüft den
    Wartezustand — und ein Test, der danach ``_slicer_path`` von Hand setzt,
    bekommt ihn von der nachgereichten Antwort wieder überschrieben. Dieselbe
    Zusage wie ``wait_for_survey`` bei der Erstinbetriebnahme; den
    Wartezustand selbst prüfen die Tests, die ihn meinen.
    """
    made = PrintSettingsDialog(session, UiSettings())
    assert made.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    return made


# --- Vollständigkeit ----------------------------------------------------------------


def test_the_save_button_says_what_it_is_waiting_for(dialog: PrintSettingsDialog) -> None:
    """„Druckdatei speichern …" ist der Satz, für den ein Slicer-Kunde gekommen ist.

    Gesperrt stand er wortlos da, während die zwei Knöpfe daneben ihren Grund
    vorbildlich nennen: *Slicen* sagt „Dieser Slicer braucht ein
    Druckerprofil", *Im Slicer öffnen* sagt „Zu diesem Slicer ist kein Fenster
    installiert". Nur hier stand nichts — dabei ist der Grund der einfachste
    von allen: Es gibt noch keine Datei.

    Geprüft werden alle drei Kanäle, die auch die Nachbarn bedienen. Der
    Tooltip allein wäre eine Bedeutung über das Aussehen (Regel 18); die
    Beschreibung für den Bildschirmleser ist die zweite Kodierung.
    """
    assert not dialog.save_button.isEnabled(), "nothing has been sliced yet"
    assert dialog.save_button.isHidden(), "RM-514: er erscheint mit der Druckdatei"
    for channel, value in (
        ("tooltip", dialog.save_button.toolTip()),
        ("accessible description", dialog.save_button.accessibleDescription()),
    ):
        assert value.strip(), f"the disabled save button carries no {channel}"
        assert "Slicen" in value, f"the {channel} should name the way out: {value!r}"

    # **Und der Grund verschwindet, wenn er nicht mehr gilt.** Ein Hinweis, der
    # an einem freigegebenen Knopf hängen bleibt, ist die Umkehrung des
    # Fehlers: Er sagt, etwas fehle, während es da ist.
    dialog._release_the_save()
    assert dialog.save_button.isEnabled()
    assert not dialog.save_button.isHidden(), "mit der Datei steht er da"
    assert not dialog.save_button.toolTip()
    assert not dialog.save_button.accessibleDescription()


def test_every_setting_in_the_model_has_a_field() -> None:
    """Eine Einstellung ohne Feld wäre eine, die der Nutzer nie zu sehen
    bekommt — und die er trotzdem an den Slicer schickt."""
    settings = print_settings.resolve(profiles.make_profile())
    covered = {field.path for field in FIELDS}

    for group in (
        "layers",
        "shell",
        "infill",
        "temperature",
        "cooling",
        "speed",
        "support",
        "adhesion",
        "retraction",
        "filament",
    ):
        section = getattr(settings, group)
        for name in section.__slots__:
            assert f"{group}.{name}" in covered, f"{group}.{name} hat kein Feld im Dialog"


def test_every_field_points_at_a_real_setting(dialog: PrintSettingsDialog) -> None:
    for field in FIELDS:
        print_settings.read_path(dialog.settings, field.path)


def test_filament_dialog_contains_only_values_that_belong_to_the_spool(
    qt_app: QApplication,
) -> None:
    """Ein Filament darf keine zweite Geometrie des Teils erzeugen.

    Schichthöhe, Wände und Tempo gelten dem Teil. Temperatur, Kühlung,
    Rückzug und Materialkennwerte können sich dagegen zwischen zwei Spulen
    desselben Drucks unterscheiden. Genau diese Grenze muss die Oberfläche
    sichtbar einhalten.
    """
    paths = {field.path for field in FILAMENT_FIELDS}

    assert {path.partition(".")[0] for path in paths} == {
        "temperature",
        "cooling",
        "retraction",
        "filament",
    }
    assert "filament.colour" not in paths, "die Farbe wird am Filament selbst gewählt"
    assert not paths & {
        "layers.layer_height",
        "shell.wall_count",
        "speed.outer_wall",
    }
    settings = print_settings.resolve(profiles.make_profile())
    dialog = FilamentOverrideDialog(MaterialSlot(index=1, name="PLA"), settings)
    assert set(dialog.editors) == paths, "jeder erlaubte Wert ist im Dialog erreichbar"


def test_filament_dialog_builds_one_groupwise_override(qt_app: QApplication) -> None:
    """Ein Haken je Bereich statt neunzehn versteckter Einzelentscheidungen."""
    from PySide6.QtWidgets import QDialogButtonBox

    from app.ui.style import SPACE, WIDE

    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "petg"))
    slot = MaterialSlot(index=1, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    dialog = FilamentOverrideDialog(slot, settings)
    layout = dialog.layout()
    assert layout is not None
    margins = layout.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (WIDE,) * 4
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    button_layout = buttons.layout()
    assert button_layout is not None
    assert button_layout.spacing() == SPACE

    def settle() -> None:
        for _ in range(8):
            qt_app.processEvents()

    dialog.show()
    settle()
    collapsed_height = dialog.height()

    assert all(not group.isChecked() for group in dialog.groups.values())
    assert all(body.isHidden() for body in dialog.group_bodies.values()), (
        "ohne eigene Werte bleiben die neunzehn Detailfelder eingeklappt"
    )
    dialog.groups["temperature"].setChecked(True)
    settle()
    assert not dialog.group_bodies["temperature"].isHidden()
    assert dialog.height() > collapsed_height, "geöffnete Felder brauchen sichtbar mehr Raum"
    nozzle = dialog.editors["temperature.nozzle"]
    assert isinstance(nozzle, BoundedSpin)
    nozzle.setValue(210)

    override = dialog.override()
    assert override is not None
    assert override.key == (slot.name, slot.colour, slot.material, slot.material_type)
    assert override.temperature is not None
    assert override.temperature.nozzle == 210
    assert override.cooling is None
    assert override.retraction is None
    assert override.filament is None

    dialog.project_values_button.click()
    settle()

    assert all(not group.isChecked() for group in dialog.groups.values())
    assert all(body.isHidden() for body in dialog.group_bodies.values())
    assert dialog.height() == collapsed_height, "Zuklappen gibt die geöffnete Höhe zurück"
    assert isinstance(nozzle, BoundedSpin)
    assert nozzle.value() == settings.temperature.nozzle
    assert dialog.override() is None, "ein sichtbarer Knopf nimmt alle eigenen Werte zurück"


def test_filament_override_refuses_a_number_until_it_is_corrected(
    qt_app: QApplication,
) -> None:
    """Eine Spule übernimmt weder einen geklemmten Wert noch eine offene Ablehnung."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "petg"))
    slot = MaterialSlot(index=1, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    dialog = FilamentOverrideDialog(slot, settings)
    dialog.show()
    try:
        dialog.groups["temperature"].setChecked(True)
        qt_app.processEvents()
        editor = dialog.editors["temperature.nozzle"]
        assert isinstance(editor, BoundedSpin)
        before = settings.temperature.nozzle
        line = editor.lineEdit()
        line.setFocus()
        line.selectAll()
        QTest.keyClicks(line, "401")
        refusal = editor.refusal()
        assert editor.refused_value() == pytest.approx(401)
        assert "Obergrenze" in refusal and "400" in refusal
        assert dialog._refusals["temperature.nozzle"].isVisibleTo(dialog)
        ok = dialog._ok_button
        assert ok is not None
        assert not ok.isEnabled()
        assert refusal in ok.toolTip()

        QTest.keyClick(line, Qt.Key.Key_Return)
        dialog.accept()
        assert dialog.result() != QDialog.DialogCode.Accepted
        assert editor.value() == before

        line.selectAll()
        QTest.keyClicks(line, "400")
        QTest.keyClick(line, Qt.Key.Key_Return)
        assert editor.refused_value() is None
        assert dialog._refusals["temperature.nozzle"].isHidden()
        assert ok.isEnabled()
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
        override = dialog.override()
        assert override is not None and override.temperature is not None
        assert override.temperature.nozzle == 400
    finally:
        dialog.reject()
        qt_app.processEvents()
        dialog.deleteLater()


def test_every_field_lands_in_a_known_group() -> None:
    for field in FIELDS:
        assert field.group in GROUPS


def test_filament_settings_precede_temperature_and_speed_tabs() -> None:
    """Materialwerte stehen vor den davon abgeleiteten Druckgeschwindigkeiten."""
    assert GROUPS.index("filament") < GROUPS.index("temperature")
    assert GROUPS.index("filament") < GROUPS.index("speed")


def test_the_front_page_stays_short() -> None:
    """§2.4: vorn die zwei bis drei Werte, die man ändert. Wird das eine
    zweite vollständige Liste, ist die gestufte Tiefe verloren.

    RM-514 (Entscheidung Robert): vorn Drucker, Filamente, Qualität,
    Fülldichte und Stützen — die ersten drei in der Kopfzeile, die übrigen
    zwei aus dieser Tabelle. Schichthöhe, Wände, Füllmuster und Temperaturen
    stehen hinter „Weitere Einstellungen".
    """
    front = [field.path for field in FIELDS if field.front]
    assert front == ["infill.density", "support.style"]


# --- Werte hin und zurück -----------------------------------------------------------


def test_the_editors_start_on_the_resolved_values(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["layers.layer_height"]
    assert isinstance(editor, BoundedSpin)
    assert editor.value() == pytest.approx(dialog.settings.layers.layer_height)


def test_the_printer_header_refuses_out_of_range_numbers(
    dialog: PrintSettingsDialog,
    qt_app: QApplication,
) -> None:
    """Düsendurchmesser und Düsenanzahl lehnen Zahlen jenseits ihrer Grenzen ab."""
    from PySide6.QtTest import QTest

    dialog.show()
    # Die Düsenzahl steht hinter „Weitere Einstellungen" (RM-514).
    dialog.tabs_toggle.setChecked(True)
    qt_app.processEvents()
    try:
        other = dialog.nozzle_choice.count() - 1
        assert dialog.nozzle_choice.itemData(other) is None
        dialog.nozzle_choice.setCurrentIndex(other)
        dialog.nozzle_choice.activated.emit(other)
        assert not dialog.nozzle.isHidden(), "„Andere …“ öffnet das eigene Maß an der Düsenzeile"
        for path, editor, boundary in (
            ("nozzle", dialog.nozzle, dialog.nozzle.maximum()),
            ("nozzle_count", dialog.nozzle_count, dialog.nozzle_count.maximum()),
        ):
            assert isinstance(editor, BoundedLengthSpin | BoundedSpin)
            line = editor.lineEdit()
            line.setFocus()
            line.selectAll()
            invalid = editor.maximum() + 1
            shown = str(int(invalid)) if path == "nozzle_count" else editor.textFromValue(invalid)
            QTest.keyClicks(line, shown)

            reason = editor.refusal()
            assert editor.refused_value() == pytest.approx(invalid)
            assert "Obergrenze" in reason
            assert editor.textFromValue(boundary) in reason
            assert dialog._header_refusals[path].isVisibleTo(dialog)
            assert dialog._first_numeric_refusal() == tr(
                "{name}: {value}", name=editor.accessibleName(), value=reason
            )

            line.selectAll()
            corrected = (
                str(int(boundary)) if path == "nozzle_count" else editor.textFromValue(boundary)
            )
            QTest.keyClicks(line, corrected)
            assert editor.refused_value() is None
            assert dialog._header_refusals[path].isHidden()
    finally:
        dialog.reject()
        dialog.wait_for_workers()
        qt_app.processEvents()
        dialog.deleteLater()


@pytest.mark.parametrize(
    ("path", "invalid", "boundary", "bound_word"),
    [
        ("layers.layer_height", 1.5, 1.2, "Obergrenze"),
        ("shell.wall_count", 21, 20, "Obergrenze"),
        ("shell.wall_count", 0, 1, "Untergrenze"),
    ],
)
def test_print_settings_refuse_out_of_range_numbers_until_corrected_or_reset(
    dialog: PrintSettingsDialog,
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    path: str,
    invalid: float,
    boundary: float,
    bound_word: str,
) -> None:
    """Grenzen bleiben beim Feld sichtbar; weder Tippen noch Enter klemmt den Wert."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    dialog.show()
    dialog._lift(path)
    qt_app.processEvents()

    def close_dialog() -> None:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()
        qt_app.processEvents()

    request.addfinalizer(close_dialog)
    editor = dialog._editors[path]
    assert isinstance(editor, BoundedSpin)
    assert not editor.keyboardTracking(), "ein Zwischenstand darf das Modell nicht verändern"
    field = dialog._fields[path]
    before = print_settings.read_path(dialog.settings, path)
    line = editor.lineEdit()

    def type_number(value: float) -> None:
        line.setFocus()
        line.selectAll()
        shown = (
            str(int(value))
            if field.kind == "int"
            else editor.locale().toString(value, "f", editor.decimals())
        )
        QTest.keyClicks(line, shown)

    type_number(invalid)
    refusal = editor.refusal()
    assert editor.refused_value() == pytest.approx(invalid)
    assert bound_word in refusal
    assert editor.textFromValue(boundary) in refusal
    assert dialog._refusals[path].isVisibleTo(dialog)
    assert print_settings.read_path(dialog.settings, path) == before

    QTest.keyClick(line, Qt.Key.Key_Return)
    assert line.text().strip(), "Enter lässt den abgelehnten Tipp stehen"
    assert editor.refused_value() == pytest.approx(invalid)
    assert print_settings.read_path(dialog.settings, path) == before

    monkeypatch.setattr(
        dialog.session,
        "last_result",
        _shown_result(SimpleNamespace(objects={"Teil": _cube_object()})),
    )

    def unexpected_setup() -> None:
        pytest.fail("eine offene Grenzablehnung darf keinen Übergabeweg erreichen")

    monkeypatch.setattr(dialog, "_current_setup", unexpected_setup)
    dialog._slice()
    dialog._open_in_slicer()
    assert editor.refused_value() == pytest.approx(invalid)

    type_number(boundary)
    QTest.keyClick(line, Qt.Key.Key_Return)
    assert editor.refused_value() is None
    assert dialog._refusals[path].isHidden()
    expected = int(boundary) if field.kind == "int" else boundary
    assert print_settings.read_path(dialog.settings, path) == expected
    assert not editor.refusal()

    type_number(invalid)
    QTest.keyClick(line, Qt.Key.Key_Return)
    assert editor.refused_value() == pytest.approx(invalid)
    dialog._resets[path].click()
    assert editor.refused_value() is None
    assert dialog._refusals[path].isHidden()
    assert print_settings.read_path(dialog.settings, path) == print_settings.read_path(
        dialog._base(), path
    )


@pytest.mark.parametrize(
    ("selector_path", "active_value", "number_path"),
    [
        ("support.style", "grid", "support.density"),
        ("adhesion.kind", "brim", "adhesion.brim_width"),
    ],
)
def test_disabling_a_settings_group_clears_its_refusal_gate(
    dialog: PrintSettingsDialog,
    qt_app: QApplication,
    request: pytest.FixtureRequest,
    selector_path: str,
    active_value: str,
    number_path: str,
) -> None:
    """Ein ausgeblendeter Zahlenwert darf die Druckübergabe nicht weiter sperren."""
    from PySide6.QtTest import QTest

    dialog.show()
    dialog._lift(number_path)
    qt_app.processEvents()

    def close_dialog() -> None:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()
        qt_app.processEvents()

    request.addfinalizer(close_dialog)
    selector = dialog._editors[selector_path]
    selector.setCurrentIndex(selector.findData(active_value))
    editor = dialog._editors[number_path]
    assert isinstance(editor, BoundedSpin)
    line = editor.lineEdit()
    line.setFocus()
    line.selectAll()
    invalid = editor.maximum() + 1
    shown = editor.locale().toString(invalid, "f", editor.decimals())
    QTest.keyClicks(line, shown)

    refusal = editor.refusal()
    assert refusal
    from app.ui.print_settings_dialog import setting_title

    # Der Sperrgrund nennt das Feld (RM-342, D-N2).
    named = f"{setting_title(number_path)}: {refusal}"
    assert dialog._first_numeric_refusal() == named
    assert dialog._refusals[number_path].isVisibleTo(dialog)

    selector.setCurrentIndex(selector.findData("none"))
    qt_app.processEvents()

    assert editor.refusal() == refusal
    assert dialog._first_numeric_refusal() == ""
    assert dialog._refusals[number_path].isHidden()
    assert refusal not in dialog.slice_button.toolTip()
    assert refusal not in dialog.open_button.toolTip()

    selector.setCurrentIndex(selector.findData(active_value))
    qt_app.processEvents()

    assert editor.refusal() == refusal
    assert dialog._first_numeric_refusal() == named
    assert dialog._refusals[number_path].isVisibleTo(dialog)
    assert named in dialog.slice_button.toolTip()
    assert refusal in dialog.open_button.toolTip()


def test_an_adhesion_measure_brought_along_keeps_a_refusal_elsewhere(
    dialog: PrintSettingsDialog,
    qt_app: QApplication,
    request: pytest.FixtureRequest,
) -> None:
    """Raft bringt seine Schichtzahl mit und lässt eine abgelehnte Schichthöhe stehen.

    Elegoos Standardprozess führt null Raft-Schichten; die Wahl „Raft“ trägt
    dann Solidons Vorgabe nach (``print_settings._with_a_measure``). Dafür
    lud der Dialog alle Felder neu, und eine abgelehnte Zahl in einem anderen
    Feld verschwand still samt Sperre.
    """
    from PySide6.QtTest import QTest

    dialog.show()
    qt_app.processEvents()

    def close_dialog() -> None:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()
        qt_app.processEvents()

    request.addfinalizer(close_dialog)
    dialog.settings = print_settings.with_path(dialog.settings, "adhesion.raft_layers", 0)
    path = "layers.layer_height"
    dialog._lift(path)
    editor = dialog._editors[path]
    assert isinstance(editor, BoundedSpin)
    line = editor.lineEdit()
    line.setFocus()
    line.selectAll()
    invalid = editor.maximum() + 0.3
    QTest.keyClicks(line, editor.locale().toString(invalid, "f", editor.decimals()))
    refusal = editor.refusal()
    assert refusal

    selector = dialog._editors["adhesion.kind"]
    selector.setCurrentIndex(selector.findData("raft"))
    qt_app.processEvents()

    layers = print_settings.read_path(dialog.settings, "adhesion.raft_layers")
    assert layers > 0, "die Haftungsart hat ihr Maß mitgebracht"
    raft_editor = dialog._editors["adhesion.raft_layers"]
    assert isinstance(raft_editor, BoundedSpin)
    assert raft_editor.value() == pytest.approx(layers), "und ihr Feld zeigt es"
    assert editor.refusal() == refusal
    assert dialog._first_numeric_refusal() == tr(
        "{name}: {value}", name=editor.accessibleName(), value=refusal
    )
    assert refusal in dialog.slice_button.toolTip()


def test_advice_values_read_like_the_field_beside_them(dialog: PrintSettingsDialog) -> None:
    """Die Spalte „Vorschlag" schreibt jeden Wert, wie ihn das Feld zeigt.

    Dort stand ``f"{wert:g}"``: im deutschen Fenster „0.16 mm" neben einem
    Feld mit „0,160 mm", eine Bahngeschwindigkeit als „59.5238 mm/s", und
    ein Haken als „0 → 1". Jetzt Komma, die Nachkommastellen des Felds und
    „aus → an".
    """
    assert dialog._shown("layers.layer_height", 0.16) == "0,160 mm"
    assert dialog._shown("speed.outer_wall", 59.52380952380952) == "59,5 mm/s"
    assert dialog._shown("shell.outer_wall_first", True) == "an"
    assert dialog._shown("shell.outer_wall_first", False) == "aus"


def test_a_speed_survives_being_shown(dialog: PrintSettingsDialog) -> None:
    """Ein Feld, das einen Wert nur anzeigt, darf ihn nicht verändern.

    Die Bahngeschwindigkeiten standen auf null Nachkommastellen. Das ist keine
    Frage der Anzeige: der Wert, den ``advise`` aus dem Volumenstrom errechnet,
    ist selten glatt — bei 5 mm³/s, 0,2 mm Schicht und 0,42 mm Bahn sind es
    59,52 mm/s. Gerundet auf 60 fördert die Düse 5,04 mm³/s, und damit stand
    allein durch das Öffnen des Fensters mehr in der Datei, als das Material
    verträgt.
    """
    from app.ui.print_settings_dialog import _setting_editor_value

    genau = 59.52380952380952
    dialog.settings = replace(
        dialog.settings, speed=replace(dialog.settings.speed, outer_wall=genau)
    )
    dialog._load_into_editors()

    # Seit Stufe A liest der Dialog nur das Feld zurück, das sich geändert hat
    # (``_editor_changed``); bloßes Anzeigen ändert das Modell gar nicht.
    assert dialog.settings.speed.outer_wall == genau
    zurueck = _setting_editor_value(
        dialog._editors["speed.outer_wall"], dialog._fields["speed.outer_wall"]
    )

    fluss = dialog.settings.layers.layer_height * dialog.settings.layers.line_width
    assert zurueck * fluss <= dialog.settings.filament.max_flow + 1e-9, (
        "der angezeigte Wert darf den Volumenstrom des Materials nicht überschreiten"
    )
    assert zurueck == pytest.approx(genau, abs=0.05), "und er bleibt bei dem, was er war"


def test_choosing_a_filament_adopts_its_values(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Wer eine Spule wählt, bekommt ihre Werte — auch den Volumenstrom.

    Solidon kennt „PETG" und bringt 10 mm³/s mit; Elegoo PETG PRO fährt 5.
    Ohne diese Übernahme rechnet die Beratung gegen eine Grenze, die das
    eingelegte Material nicht hat.
    """
    datei = tmp_path / "Spule.json"
    datei.write_text(
        json.dumps(
            {
                "name": "Spule",
                "nozzle_temperature": ["255"],
                "hot_plate_temp": ["75"],
                "filament_max_volumetric_speed": ["5"],
            }
        ),
        encoding="utf-8",
    )
    dialog._filament_profile = str(datei)
    dialog._filament_title = "Spule"

    dialog._adopt_filament_values()

    assert dialog.settings.filament.max_flow == 5.0
    assert dialog.settings.temperature.nozzle == 255
    assert dialog.settings.temperature.bed == 75


def test_adopting_says_why_nothing_changed(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Der Knopf „Werte übernehmen" endet nie stumm (Regel 17).

    Ein Profil ohne lesbare Werte ließ den Klick folgenlos, und ein Wert wie
    ``nan`` warf eine Ausnahme aus dem Slot. Beides sagt jetzt die Zeile
    darunter; die Einstellungen bleiben, wie sie waren.
    """
    empty = tmp_path / "Leer.json"
    empty.write_text(json.dumps({"name": "Leer"}), encoding="utf-8")
    before = dialog.settings
    dialog._filament_profile = str(empty)
    dialog._filament_title = "Leer"
    dialog.state.setText("")

    dialog._adopt_filament_values()

    assert dialog.settings == before
    assert "Leer" in dialog.state.text(), "der Klick braucht eine Antwort"

    broken = tmp_path / "Kaputt.json"
    broken.write_text(
        json.dumps({"name": "Kaputt", "nozzle_temperature": ["nan"]}), encoding="utf-8"
    )
    dialog._filament_profile = str(broken)
    dialog._filament_title = "Kaputt"
    dialog.state.setText("")

    dialog._adopt_filament_values()

    assert dialog.settings == before
    assert dialog.state.text(), "ein unlesbarer Wert wird gemeldet, nicht geworfen"


def test_filling_the_filament_list_changes_nothing(dialog: PrintSettingsDialog) -> None:
    """Was ein Projekt mitbringt, gilt.

    Die Liste wird beim Öffnen befüllt und dabei eine Vorauswahl gesetzt. Käme
    daraus eine Übernahme, überschriebe allein das Aufgehen des Fensters die
    Einstellungen des Projekts — eine Dichtung aus TPU wäre danach keine mehr.
    Deshalb hängt die Übernahme an ``activated`` (der Wahl eines Menschen) und
    nicht an ``currentIndexChanged``.
    """
    vorher = dialog.settings

    dialog._fill_filaments(None)

    assert dialog.settings is vorher, "das Befüllen der Liste ändert keine Einstellung"


def test_changing_a_field_reaches_the_settings(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["shell.wall_count"]
    assert isinstance(editor, BoundedSpin)
    assert editor.decimals() == 0
    assert editor.singleStep() == 1

    editor.setValue(7)

    assert dialog.settings.shell.wall_count == 7


def test_changing_the_quality_reloads_every_field(dialog: PrintSettingsDialog) -> None:
    before = dialog.settings.layers.layer_height
    index = dialog.quality.findData("fine")
    assert index >= 0

    dialog.quality.setCurrentIndex(index)

    assert dialog.settings.quality == "fine"
    assert dialog.settings.layers.layer_height != before
    editor = dialog._editors["layers.layer_height"]
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.value() == pytest.approx(dialog.settings.layers.layer_height)


def test_the_colour_button_says_which_colour_it_is(qt_app: QApplication) -> None:
    """Regel 18: die Farbe allein trägt die Bedeutung nicht.

    Getragen hat sie bisher der Hexwert — richtig als zweite Kodierung und
    trotzdem schwach: „#4A90D9" beschreibt für niemanden eine Spule im Regal.
    Der Name tut beides, und die Zahl steht im Tooltip, wo sie hingehört.

    Die `QApplication` steht nicht aus Gewohnheit in der Signatur: Ein Widget
    ohne sie bringt den ganzen Lauf zum Absturz, und `pytest-randomly`
    entscheidet, ob vorher ein anderer Test eine gebaut hat.
    """
    button = _ColourButton("#3FAE6B")
    assert button.text() == "Grün"
    assert "3FAE6B" in button.toolTip().upper(), "genau bleibt genau"

    button.set_value("#112233")
    assert button.text() == "Schwarz"
    assert "112233" in button.toolTip().upper()


def test_a_checkbox_writes_through(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["shell.outer_wall_first"]
    assert isinstance(editor, QCheckBox)

    editor.setChecked(True)

    assert dialog.settings.shell.outer_wall_first is True


def test_an_enum_writes_through(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["support.style"]
    assert isinstance(editor, QComboBox)

    editor.setCurrentIndex(editor.findData("tree"))

    assert dialog.settings.support.style == "tree"


def test_disabled_support_and_bed_adhesion_hide_their_detail_rows(
    dialog: PrintSettingsDialog,
) -> None:
    """Abgeschaltete Stützen und Haftung lassen keine wirkungslosen Felder stehen."""
    support_paths = (
        "support.placement",
        "support.threshold_angle",
        "support.z_gap",
        "support.xy_gap",
        "support.density",
        "support.interface_layers",
        "support.block_channels",
        "support.spare_ledges",
    )
    support = dialog._editors["support.style"]
    assert isinstance(support, QComboBox)
    support.setCurrentIndex(support.findData("tree"))
    threshold = dialog._editors["support.threshold_angle"]
    assert isinstance(threshold, QDoubleSpinBox)
    threshold.setValue(37.0)
    saved_threshold = dialog.settings.support.threshold_angle
    assert all(not dialog._labels[path].isHidden() for path in support_paths)
    support.setCurrentIndex(support.findData("none"))
    assert all(dialog._labels[path].isHidden() for path in support_paths)
    assert dialog.settings.support.threshold_angle == saved_threshold
    support.setCurrentIndex(support.findData("tree"))
    assert all(not dialog._labels[path].isHidden() for path in support_paths)
    assert threshold.value() == saved_threshold

    adhesion_paths = (
        "adhesion.skirt_loops",
        "adhesion.skirt_distance",
        "adhesion.brim_width",
        "adhesion.raft_layers",
    )
    adhesion = dialog._editors["adhesion.kind"]
    assert isinstance(adhesion, QComboBox)
    adhesion.setCurrentIndex(adhesion.findData("brim"))
    brim_width = dialog._editors["adhesion.brim_width"]
    assert isinstance(brim_width, QDoubleSpinBox)
    brim_width.setValue(9.5)
    saved_brim_width = dialog.settings.adhesion.brim_width
    assert {path for path in adhesion_paths if not dialog._labels[path].isHidden()} == {
        "adhesion.brim_width"
    }
    adhesion.setCurrentIndex(adhesion.findData("none"))
    assert all(dialog._labels[path].isHidden() for path in adhesion_paths)
    assert dialog.settings.adhesion.brim_width == saved_brim_width

    adhesion.setCurrentIndex(adhesion.findData("brim"))
    assert {path for path in adhesion_paths if not dialog._labels[path].isHidden()} == {
        "adhesion.brim_width"
    }
    assert brim_width.value() == saved_brim_width


def test_automatic_adhesion_rows_follow_the_selected_slicer_family(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-341: Slicer-Erkennung und Wahl aktualisieren die sichtbare Haftungsart."""
    from app.ui import print_settings_dialog as module

    dialog.session.start_new("centauri-carbon-2", "pla")
    automatic = print_settings.with_path(
        print_settings.with_path(
            print_settings.resolve(dialog.session.profile), "adhesion.kind", "auto"
        ),
        "adhesion.skirt_loops",
        0,
    )
    dialog.settings = automatic
    dialog._foundation = None
    dialog._foundation_key = None
    dialog._slicers = ()
    dialog._slicer_path = None
    dialog._load_into_editors()
    adhesion_paths = tuple(print_settings.ADHESION_DETAILS)
    skirt_loops = dialog._editors["adhesion.skirt_loops"]

    def visible_paths() -> set[str]:
        return {path for path in adhesion_paths if not dialog._labels[path].isHidden()}

    # Der Auto-Brim der Orca-Familie zeigt Breite und Abstand zum Teil: Der
    # Abstand gehört seit RM-318 zum Brim (anliegender Brim am schlanken Teil).
    brim = {"adhesion.brim_width", "adhesion.brim_gap"}
    assert visible_paths() == brim
    assert dialog.settings.adhesion.skirt_loops == 0
    assert skirt_loops.value() == 0

    target = "adhesion.skirt_loops"
    term = str(dialog._fields[target].title)
    assert dialog.search_hits(term) == [target]
    dialog.jump_to(term)
    assert dialog._search_requirement_target == target

    prusa = Path("PrusaSlicer.exe")
    orca = Path("OrcaSlicer.exe")
    dialog._slicers = (prusa, orca)
    monkeypatch.setattr(dialog, "_choose_slicer", lambda _found: prusa)
    monkeypatch.setattr(dialog, "_forget_result", lambda: None)
    monkeypatch.setattr(dialog, "_clear_profile_choices", lambda: None)
    monkeypatch.setattr(dialog, "_show_slicer_state", lambda: None)
    monkeypatch.setattr(dialog, "_start_profile_search", lambda: None)
    monkeypatch.setattr(dialog, "_refresh_advice", lambda: None)
    monkeypatch.setattr(module.discover, "remember_path", lambda *_args: None)

    dialog._slicers_found((prusa, orca))
    assert visible_paths() == {"adhesion.skirt_loops", "adhesion.skirt_distance"}
    assert dialog._search_requirement_target == ""
    assert (
        skirt_loops.value() == print_settings.resolve(dialog.session.profile).adhesion.skirt_loops
    )

    skirt_loops.setValue(0)
    assert "adhesion.skirt_loops" in dialog.settings.explicit
    assert handover.values_for(dialog.settings, dialog.session.profile, "prusa")["skirts"] == "0"

    dialog._slicer_chosen(1)
    assert visible_paths() == brim
    assert dialog._search_requirement_target == target
    assert not dialog.search_requirement.isHidden()

    brim_width = dialog._editors["adhesion.brim_width"]
    assert isinstance(brim_width, BoundedSpin)
    invalid_width = brim_width.maximum() + 1
    brim_width.lineEdit().setText(brim_width.textFromValue(invalid_width))
    refusal = brim_width.refusal()
    assert refusal

    dialog._slicer_chosen(0)
    assert brim_width.refusal() == refusal
    dialog._slicer_chosen(1)
    assert brim_width.refusal() == refusal
    dialog._slicer_chosen(0)
    assert brim_width.refusal() == refusal
    assert visible_paths() == {"adhesion.skirt_loops", "adhesion.skirt_distance"}
    assert dialog._search_requirement_target == ""
    assert dialog.highlighted() == target
    assert skirt_loops.value() == 0


def test_late_slicer_detection_does_not_take_the_user_back_to_a_search_hit(
    dialog: PrintSettingsDialog, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-341: Passive Erkennung lässt einen manuell gewählten Reiter stehen."""
    from app.ui import print_settings_dialog as module

    dialog.session.start_new("centauri-carbon-2", "pla")
    dialog.settings = print_settings.with_path(
        print_settings.resolve(dialog.session.profile), "adhesion.kind", "auto"
    )
    dialog._foundation = None
    dialog._foundation_key = None
    dialog._slicers = ()
    dialog._slicer_path = None
    dialog._load_into_editors()

    target = "adhesion.skirt_loops"
    dialog.jump_to(str(dialog._fields[target].title))
    qt_app.processEvents()
    assert dialog._search_requirement_target == target
    assert dialog.tabs.currentIndex() == module.GROUPS.index("adhesion")

    retraction_index = module.GROUPS.index("retraction")
    dialog.tabs.setCurrentIndex(retraction_index)
    qt_app.processEvents()
    retraction = dialog._editors["retraction.length"]
    initial = retraction.value()
    retraction.setValue(initial + 0.1)
    qt_app.processEvents()
    chosen_length = retraction.value()
    assert print_settings.read_path(dialog.settings, "retraction.length") == pytest.approx(
        chosen_length
    )
    assert "retraction.length" in dialog.settings.explicit

    prusa = Path("PrusaSlicer.exe")
    orca = Path("OrcaSlicer.exe")
    dialog._slicers = (prusa, orca)
    monkeypatch.setattr(dialog, "_choose_slicer", lambda _found: prusa)
    monkeypatch.setattr(dialog, "_forget_result", lambda: None)
    monkeypatch.setattr(dialog, "_clear_profile_choices", lambda: None)
    monkeypatch.setattr(dialog, "_show_slicer_state", lambda: None)
    monkeypatch.setattr(dialog, "_start_profile_search", lambda: None)
    monkeypatch.setattr(dialog, "_refresh_advice", lambda: None)
    monkeypatch.setattr(module.discover, "remember_path", lambda *_args: None)

    dialog._slicers_found((prusa, orca))
    qt_app.processEvents()

    assert dialog.tabs.currentIndex() == retraction_index
    assert retraction.value() == pytest.approx(chosen_length)
    assert print_settings.read_path(dialog.settings, "retraction.length") == pytest.approx(
        chosen_length
    )
    assert dialog.highlighted() == target
    assert dialog._search_requirement_target == ""
    assert dialog.search_requirement.isHidden()


def test_an_enum_shows_words_and_stores_the_english_value(dialog: PrintSettingsDialog) -> None:
    """§4.1: der gespeicherte Wert geht in die Projektdatei und zum Slicer und
    bleibt englisch; gezeigt wird die Übersetzung."""
    editor = dialog._editors["infill.pattern"]
    assert isinstance(editor, QComboBox)

    index = editor.findData("gyroid")
    assert index >= 0
    editor.setCurrentIndex(index)

    assert dialog.settings.infill.pattern == "gyroid"
    assert editor.itemData(editor.findData("grid")) == "grid"
    assert editor.itemText(editor.findData("grid")) != "grid", "Gitter, nicht grid"


def test_every_choice_entry_says_what_it_does(dialog: PrintSettingsDialog) -> None:
    """Der Name benennt, der Satz erklärt — an jedem Eintrag jeder Auswahl.

    „Gyroid" oder „Baumstruktur" sagen einem Kunden nicht, wann er sie wählen
    soll; der Satz aus ``choice_note`` tut es, als Tooltip über der offenen
    Liste und als ``AccessibleDescriptionRole`` für den Bildschirmleser.
    Geprüft über **alle** Enum-Felder, nicht an einem Beispiel: fünfzehn
    erklärte Einträge von siebenundsechzig wären schlimmer als keine.

    Wo ein Feld für einen Wert einen eigenen Satz führt (``choice_notes``),
    gilt dieser: „Automatisch“ heißt bei Stützen und Haftung etwas anderes als
    der allgemeine Satz (Review Stufe A+B, H8).
    """
    from app.ui.labels import choice_note

    missing = []
    for field in FIELDS:
        if field.kind != "enum":
            continue
        editor = dialog._editors[field.path]
        assert isinstance(editor, QComboBox)
        own = {value: str(text) for value, text in field.choice_notes}
        for index in range(editor.count()):
            value = editor.itemData(index)
            note = own.get(value) or choice_note(value)
            if note is None:
                continue
            if editor.itemData(index, Qt.ItemDataRole.ToolTipRole) != note:
                missing.append(f"{field.path}: {value!r} ohne Tooltip")
            if editor.itemData(index, Qt.ItemDataRole.AccessibleDescriptionRole) != note:
                missing.append(f"{field.path}: {value!r} ohne AccessibleDescription")

    assert not missing, "Auswahlwerte ohne Satz am Eintrag:\n" + "\n".join(missing)


def test_slicing_greys_out_before_the_click_when_the_licence_ran_out(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Lizenzgrenze steht vor dem Klick, nicht hinter dem Dialog.

    `handover.slice_model` fragt `activation.require` erst im Arbeiter — mit
    abgelaufener Demo füllte der Kunde den ganzen Dialog aus, drückte
    *Slicen* und bekam dann die Absage (Regel 19). Von den vier Grenzen war
    SLICER die einzige ohne Ausgrauen; CHANGE, EXPORT und CHAT hatten es.
    Der Slicer-Pfad wird gesetzt, damit der Knopf nicht aus dem falschen
    Grund grau ist.
    """
    from app.core import activation
    from app.core.activation import store

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))
    dialog = PrintSettingsDialog(session, UiSettings())
    # Die Slicersuche läuft im Arbeiter: abwarten, sonst überschreibt ihre
    # nachgereichte Antwort den Pfad darunter, und der Knopf ist aus dem
    # falschen Grund grau.
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    # Ein Name mit Familie: Ein Programm ohne Familie sperrt Slicen seit
    # RM-071 aus eigenem Grund, und der stünde hier vor der Lizenz.
    dialog._slicer_path = Path("prusa-slicer-console")
    dialog._show_slicer_state()

    assert not dialog.slice_button.isEnabled(), "abgelaufen sperrt vor dem Klick"
    reason = dialog.slice_button.toolTip()
    assert reason, "der Grund steht am Knopf"
    assert dialog.slice_button.accessibleDescription() == reason

    monkeypatch.setattr(store, "TRIAL_FROM", None)
    dialog._show_slicer_state()
    sale_reason = dialog.slice_button.toolTip()
    assert "Testzeitraum" not in sale_reason
    assert "Geräteaktivierung" in sale_reason

    monkeypatch.setattr(store, "TRIAL_FROM", store.DEMO_FROM)
    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=5))
    dialog._show_slicer_state()

    assert dialog.slice_button.isEnabled(), "Testzeitraum plus Slicer heißt frei"
    assert not dialog.slice_button.toolTip()


def test_a_cura_without_its_loader_only_offers_its_window(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-521: Findet Solidon den Lader einer Flatpak- oder AppImage-Cura nicht,
    sperrt der Dialog *Slicen* mit dem Satz aus dem Kern, und der Öffnen-Knopf
    bleibt der Weg. Die Lizenz ist frei, damit kein anderer Grund davor steht."""
    from app.core.activation import store
    from app.core.export import cura_linux

    monkeypatch.setattr(store, "TRIAL_FROM", store.DEMO_FROM)
    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=5))
    monkeypatch.setattr(handover, "console_refusal", lambda _found: cura_linux.WINDOW_ONLY)
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    dialog._slicer_path = Path("UltiMaker-Cura-5.13.0-linux-X64.AppImage")
    dialog._show_slicer_state()

    reason = str(cura_linux.WINDOW_ONLY)
    assert not dialog.slice_button.isEnabled()
    assert dialog.slice_button.toolTip() == reason
    assert dialog.slice_button.accessibleDescription() == reason
    assert dialog.open_button.isEnabled(), "Curas Fenster bleibt der Weg"
    assert reason not in dialog.open_button.toolTip()


def _cura_appimage_dialog(
    session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **appimage: Any
) -> tuple[PrintSettingsDialog, list[Path]]:
    """Ein Druckdialog mit einer AppImage-Cura, deren Kopie noch aussteht, im
    Betrieb der Anwendung: Der Fensterfaden wartet nie (``build_application``)."""
    from app.core.activation import store
    from app.core.export import cura_linux
    from tests.cura_fakes import appimage_cura

    monkeypatch.setattr(store, "TRIAL_FROM", store.DEMO_FROM)
    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=5))
    mounts: list[Path] = []
    found, _point = appimage_cura(tmp_path, monkeypatch, mounts, **appimage)
    monkeypatch.setattr(cura_linux, "_never_waits", None)
    cura_linux.never_wait_in(threading.current_thread())
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    dialog._slicer_path = found
    return dialog, mounts


def _until_mounted(mounts: list[Path]) -> None:
    deadline = time.monotonic() + 10.0
    while not mounts and time.monotonic() < deadline:
        time.sleep(0.01)
    assert mounts, "der Cura-Arbeiter hat nicht eingehängt"


def test_the_dialog_rebases_without_waiting_and_again_after_curas_copy(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RM-521: Während der Cura-Arbeiter die Druckerkopie einer AppImage-Cura
    anlegt, gründet der Dialog ohne zu warten (Fensterfaden); danach gründet er
    mit Curas Bestand neu."""
    from app.core.export import manufacturer, slicer_profiles

    seen: list[tuple[float, bool]] = []
    original = manufacturer.base_settings

    def spy(profile: Any, quality: Any, setup: Any) -> Any:
        started = time.monotonic()
        result = original(profile, quality, setup)
        root = slicer_profiles.install_root(setup.executable) if setup is not None else None
        seen.append((time.monotonic() - started, root is not None))
        return result

    monkeypatch.setattr(manufacturer, "base_settings", spy)
    dialog, mounts = _cura_appimage_dialog(session, monkeypatch, tmp_path, delay=3.0)
    dialog._start_profile_search()
    _until_mounted(mounts)
    started = time.monotonic()
    dialog._foundation_key = None
    dialog._rebase()
    during = time.monotonic() - started

    assert dialog.wait_for_cura_printer(60_000)
    QCoreApplication.processEvents()
    dialog.release()

    assert during < 1.0, "der Fensterfaden wartet nicht auf die Kopie"
    assert seen and seen[-1][1], "nach dem Arbeiter gründet der Dialog mit Curas Bestand"


def test_a_dialog_closed_during_curas_copy_gets_no_rebase(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Schließen wartet nicht auf den kopierenden Arbeiter, und sein spätes
    Ergebnis gründet den geschlossenen Dialog nicht mehr neu."""
    from app.ui import leash

    calls: list[str] = []
    original = PrintSettingsDialog._rebase

    def counted(self: PrintSettingsDialog, *args: object) -> None:
        calls.append("rebase")
        original(self, *args)

    monkeypatch.setattr(PrintSettingsDialog, "_rebase", counted)
    dialog, mounts = _cura_appimage_dialog(session, monkeypatch, tmp_path, delay=2.0)
    dialog._start_profile_search()
    _until_mounted(mounts)
    started = time.monotonic()
    dialog.reject()
    closing = time.monotonic() - started
    before = len(calls)
    leash.wait_for_all(60_000)
    for _round in range(5):
        QCoreApplication.processEvents()
    dialog.release()

    assert closing < 1.0
    assert len(calls) == before


@pytest.mark.parametrize("loader", [True, False])
def test_slicing_waits_with_a_reason_until_curas_copy_tells(
    qt_app: QApplication,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    loader: bool,
) -> None:
    """Ob eine AppImage-Cura rechnen kann, weiß erst ihre Kopie. Bis dahin steht
    „Curas Drucker werden gelesen …“ an *Slicen* (kein Knopf auf eine
    Vermutung), danach frei oder der Sperrsatz."""
    from app.core.export import cura_linux

    reading = str(tr("Curas Drucker werden gelesen …"))
    dialog, mounts = _cura_appimage_dialog(session, monkeypatch, tmp_path, delay=2.0, loader=loader)
    dialog._start_profile_search()
    _until_mounted(mounts)
    dialog._show_slicer_state()

    assert not dialog.slice_button.isEnabled()
    assert dialog.slice_button.toolTip() == reading
    assert dialog.open_button.isEnabled()

    assert dialog.wait_for_cura_printer(60_000)
    QCoreApplication.processEvents()
    dialog._show_slicer_state()
    after = dialog.slice_button.toolTip()
    dialog.release()

    assert after != reading
    if not loader:
        assert after == str(cura_linux.WINDOW_ONLY)


def test_slicing_greys_out_until_the_profiles_are_chosen(
    qt_app: QApplication, session: Session
) -> None:
    """Die dritte Hürde derselben Bauart: Profilwahl vor dem Klick.

    Ein Slicer der Orca-Familie ohne gewähltes Drucker- und Prozessprofil
    lehnt jeden Auftrag ab — das stand bisher erst **nach** dem Klick in der
    Statuszeile, der Knopf blieb aktiv (Fund ce, 26.08.2026: Klick ohne
    sichtbare Folge, Prüfstand hing). Der Knopf kennt jetzt die Stufen:
    Suche läuft, Drucker fehlt, Prozess fehlt, frei — und der Grund am Knopf
    ist wörtlich derselbe Satz wie der Wächter in `_slice` (eine Quelle).
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    dialog._slicer_path = Path("orca-slicer")
    dialog._needs_profiles = True
    dialog._profiles_pending = True
    dialog._show_slicer_state()

    assert not dialog.slice_button.isEnabled()
    assert "durchgesehen" in dialog.slice_button.toolTip(), "laufende Suche heißt warten"

    dialog._profiles_pending = False
    dialog._show_slicer_state()

    assert not dialog.slice_button.isEnabled()
    assert dialog.slice_button.toolTip() == dialog._machine_missing_line()
    assert dialog.slice_button.accessibleDescription() == dialog.slice_button.toolTip()

    dialog.machine_choice.addItem("Drucker", "m1")
    dialog.machine_choice.setCurrentIndex(0)

    assert not dialog.slice_button.isEnabled()
    assert dialog.slice_button.toolTip() == dialog._process_missing_line()

    dialog.process_choice.addItem("Prozess", "p1")
    dialog.process_choice.setCurrentIndex(0)

    assert dialog.slice_button.isEnabled(), "beide Profile gewählt heißt frei"
    assert not dialog.slice_button.toolTip()


def test_a_share_is_shown_in_percent_and_stored_as_a_fraction(
    dialog: PrintSettingsDialog,
) -> None:
    """Ein Feld mit [%] und einer 0,15 darin ist falsch beschriftet — der Kern
    rechnet in Anteilen, die Werkstatt spricht in Prozent."""
    editor = dialog._editors["infill.density"]
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.value() == pytest.approx(dialog.settings.infill.density * 100.0)

    editor.setValue(35.0)

    assert dialog.settings.infill.density == pytest.approx(0.35)


def test_the_close_button_speaks_german(dialog: PrintSettingsDialog) -> None:
    """Regel 20: Qt beschriftet seine Standardknöpfe selbst — auch der Text
    muss durch tr() gehen."""
    from PySide6.QtWidgets import QDialogButtonBox

    boxes = dialog.findChildren(QDialogButtonBox)
    close = next(
        button
        for box in boxes
        if (button := box.button(QDialogButtonBox.StandardButton.Close)) is not None
    )
    assert close.text() == "Schließen"


# --- Vorschläge ---------------------------------------------------------------------


def test_the_advice_list_names_a_reason(qt_app: QApplication) -> None:
    """Einstellung und Vorschlag in der Tabelle, der ganze Grund darunter (RM-514).

    Als dritte Spalte endete der Grund in jeder Zeile auf „…", obwohl der Code
    Umbruch versprach. Jetzt steht er für die gewählte Zeile vollständig unter
    der Tabelle, mit dem Namen der Einstellung davor, und an jeder Zeile als
    Kurzhilfe. Vorgewählt ist die erste Zeile ohne Hervorhebung — eine
    eingefärbte Zeile im Ruhezustand wäre eine Akzentfläche mehr (B12).
    Zugeklappt sagt der Abschnitt nur die Zahl, daneben *Übernehmen* — und
    dem Bildschirmleser, der die Zeile daneben nicht mithört, was übernommen
    wird (§19.1).
    """
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())
    view = dialog.advice_view

    assert view.columnCount() == 2
    count = view.topLevelItemCount()
    assert count > 1, "TPU bremst mehrere Tempi — sonst prüft der Test die Wahl nicht"
    assert dialog.advice_toggle is not None and not dialog.advice_toggle.isChecked()
    assert dialog._advice_summary is not None
    assert dialog._advice_summary.text() == f"{count} Vorschläge"
    assert dialog.apply_button.text() == "Übernehmen"
    assert dialog.apply_button.accessibleName() == "Vorschläge übernehmen"
    assert dialog.apply_button.isVisibleTo(dialog.advice_box)

    entries = dialog._current_advice()
    first = view.topLevelItem(0)
    assert first is not None
    assert view.currentItem() is first and not first.isSelected()
    said = dialog.advice_reason.text()
    assert said.startswith(dialog._advice_title(entries[0])), said
    assert str(entries[0].reason) in said
    assert all(str(entries[0].reason) in first.toolTip(column) for column in range(2))

    second = view.topLevelItem(1)
    assert second is not None
    view.setCurrentItem(second)
    assert dialog.advice_reason.text().startswith(dialog._advice_title(entries[1]))

    # Eine eigene Wahl überlebt den Neuaufbau der Liste; die stille Vorgabe
    # wird dabei nicht zur Wahl.
    dialog._show_advice()
    assert view.currentItem() is not None and view.currentItem().isSelected()
    assert dialog.advice_reason.text().startswith(dialog._advice_title(entries[1]))


def test_applying_the_advice_moves_the_editors(qt_app: QApplication) -> None:
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())
    before = dialog.settings.speed.outer_wall

    dialog._apply_advice()

    assert dialog.settings.speed.outer_wall < before
    editor = dialog._editors["speed.outer_wall"]
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.value() == pytest.approx(dialog.settings.speed.outer_wall)


def test_applying_the_advice_says_what_it_changed(qt_app: QApplication) -> None:
    """Der Knopf sagt, was er getan hat — und dass er nichts tat.

    Die Felder änderten sich still, und die Liste darüber rechnete neu: Wer
    nicht gerade auf die richtige Zeile sah, wusste nicht, was übernommen
    war. Mit allen Haken abgewählt blieb der Klick ganz ohne Antwort.
    """
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog.wait_for_slicers()
    titles = [
        str(dialog._fields[entry.path].title)
        for entry in dialog._chosen_advice()
        if entry.path in dialog._fields
    ]
    assert titles, "ohne Vorschlag prüft der Test nichts"

    dialog._apply_advice()

    assert all(title in dialog.state.text() for title in titles), dialog.state.text()

    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog.wait_for_slicers()
    for index in range(dialog.advice_view.topLevelItemCount()):
        item = dialog.advice_view.topLevelItem(index)
        assert item is not None
        item.setCheckState(0, Qt.CheckState.Unchecked)
    before = dialog.settings

    dialog._apply_advice()

    assert dialog.settings == before
    assert dialog.state.text(), "auch ein Klick ohne Haken bekommt eine Antwort"


def test_the_advice_list_is_never_empty_of_words(dialog: PrintSettingsDialog) -> None:
    """Auch wenn nichts einzuwenden ist, steht das da — eine leere Stelle sähe
    aus wie ein Fehler.

    Als Satz und nicht als Tabellenzeile: Die Tabelle mit drei Spaltenköpfen
    und einem Knopf ohne Arbeit war der größte Block des Dialogs für die
    kleinste Auskunft.
    """
    dialog._refresh_advice()
    if dialog.advice_view.topLevelItemCount():
        first = dialog.advice_view.topLevelItem(0)
        assert first is not None and first.text(0)
        return
    assert not dialog.apply_button.isVisibleTo(dialog), "kein Knopf ohne Arbeit"
    # Zugeklappt (RM-514) steht der Satz in der Zeile der Klappe …
    summary = dialog._advice_summary
    assert summary is not None and summary.isVisibleTo(dialog)
    assert dialog.advice_state.text(), "der Satz steht da"
    assert summary.text() == dialog.advice_state.text()
    # … und aufgeklappt an der Stelle der Tabelle.
    assert dialog.advice_toggle is not None
    dialog.advice_toggle.setChecked(True)
    assert not dialog.advice_view.isVisibleTo(dialog), "keine leere Tabelle"
    assert not dialog.apply_button.isVisibleTo(dialog), "kein Knopf ohne Arbeit"
    assert dialog.advice_state.isVisibleTo(dialog)


# --- Aussehen und gestufte Tiefe ----------------------------------------------------


def _path_of(dialog: PrintSettingsDialog, editor: QWidget) -> str:
    """Der Einstellungspfad zu einem Feld des Dialogs."""
    return next(path for path, known in dialog._editors.items() if known is editor)


def _in_form(form: QFormLayout, editor: QWidget) -> bool:
    """Ob ``editor`` in einer Feldzelle dieses Formulars steht, auch in einem Halter."""
    for row in range(form.rowCount()):
        item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
        holder = item.widget() if item is not None else None
        if holder is not None and (holder is editor or holder.isAncestorOf(editor)):
            return True
    return False


def test_no_field_stretches_across_the_whole_dialog(dialog: PrintSettingsDialog) -> None:
    """Ein Wert wie 0,200 stand in einem 726 Bildpunkte breiten Kasten.

    Ein `QFormLayout` gibt der Spalte der Editoren allen Platz, den es hat —
    gemessen waren das im Kasten „Das Wichtigste" 726 von 970 Bildpunkten je
    Zeile. Die Zahl links, ihre Beschriftung eine Handbreit daneben, und acht
    solche Zeilen sind das erste, was jemand von diesem Dialog sieht.

    Gemessen wird am gezeigten Fenster und nicht an `maximumWidth`: Dass eine
    Grenze gesetzt ist, heißt nicht, dass das Layout sie einhält.
    """
    # Erst zeigen, dann aufziehen — wie der Kunde: Die Anfangsgröße beim
    # Zeigen folgt dem Bildschirm (offscreen 800 Punkte) und nicht einem
    # ``resize`` davor; eine danach gezogene Breite bleibt (``fenster.md``).
    dialog.show()
    for _ in range(16):
        QApplication.processEvents()
    dialog.resize(960, 760)
    for _ in range(16):
        QApplication.processEvents()

    assert dialog.width() >= 900, "der Test taugt nur an einem breiten Fenster"
    # ``panels.even_fields`` (4d955a9e7) gibt den gedeckelten Feldern eines
    # Formulars eine Kante: die Wunschbreite des breitesten Nachbarn. Breiter
    # als der breiteste Wert seines Formulars wird damit keines — und genau das
    # ist die Zusage, nicht die eigene Wunschbreite jedes Felds.
    neighbours: dict[int, int] = {}
    for form in dialog.findChildren(QFormLayout):
        members = [
            editor
            for editor in dialog._editors.values()
            if FIELD_WIDTH.get(dialog._fields[_path_of(dialog, editor)].kind) is not None
            and _in_form(form, editor)
        ]
        widest = max((editor.sizeHint().width() for editor in members), default=0)
        for editor in members:
            neighbours[id(editor)] = max(neighbours.get(id(editor), 0), widest)
    too_wide = []
    for path, editor in dialog._editors.items():
        limit = FIELD_WIDTH.get(dialog._fields[path].kind)
        if limit is None:
            continue
        allowed = max(limit, editor.sizeHint().width(), neighbours.get(id(editor), 0))
        if editor.width() > allowed:
            too_wide.append(f"{path}: {editor.width()} statt höchstens {allowed}")
    assert not too_wide, "\n".join(too_wide)


def test_the_deeper_settings_fold_away_instead_of_greying_out(
    dialog: PrintSettingsDialog,
) -> None:
    """„Weitere Einstellungen ☐" sagt nicht „zugeklappt", es sagt „aus".

    Dieselbe Anwendung hat das an zwei anderen Stellen schon entschieden — der
    Operationsdialog und der Generierungsdialog nehmen den Umschalter mit dem
    Dreieck aus `panels.collapsible`. Hier standen zwei ankreuzbare Gruppen:
    „Weitere Einstellungen" und „Profile des Slicers", letztere über drei
    grauen Auswahlfeldern, was sich wie eine Sperre liest.
    """
    dialog.show()
    QApplication.processEvents()

    # **Die Grundmenge sind die Abschnitte, nicht mehr die Gruppen.** Bis zum
    # G12-Umbau standen hier zwei `QGroupBox` („Das Wichtigste", „Was dieses
    # Teil verlangt"), und die Zusicherung darunter hing an ihnen: ohne Gruppe
    # wäre `checkable` leer und der Test grün, ohne etwas geprüft zu haben.
    # Seit alle vier Abschnitte dieselbe Aufklapper-Form tragen, gibt es keine
    # Gruppe mehr — die Zusicherung muss also die Abschnitte zählen, sonst
    # prüft sie ihre eigene Abschaffung.
    abschnitte = [
        toggle
        for toggle in dialog.findChildren(QToolButton)
        if toggle.objectName() == "sectionHeading"
    ]
    assert abschnitte, "kein Abschnitt im Dialog — dann sagt die Prüfung darunter nichts"
    checkable = [box.title() for box in dialog.findChildren(QGroupBox) if box.isCheckable()]
    assert not checkable, f"ankreuzbar statt aufklappbar: {checkable}"

    for toggle, content in ((dialog.tabs_toggle, dialog.tabs), (dialog.slicer_toggle, None)):
        assert toggle is not None, "ohne Umschalter kommt niemand an den Inhalt"
        assert toggle.arrowType() == Qt.ArrowType.RightArrow, toggle.text()
        assert not toggle.isChecked(), "zu ist der Anfangszustand (§2.4)"
        if content is not None:
            assert not content.isVisibleTo(dialog), "zugeklappt heißt weg, nicht grau"

    dialog.tabs_toggle.setChecked(True)
    QApplication.processEvents()
    assert dialog.tabs.isVisibleTo(dialog)
    assert dialog.tabs_toggle.arrowType() == Qt.ArrowType.DownArrow


def test_a_hint_that_points_into_a_folded_section_opens_it(
    dialog: PrintSettingsDialog,
) -> None:
    """Drei Hinweise zeigen auf die Profilauswahl. Zugeklappt wäre das ein
    Rat, dem man nicht folgen kann."""
    dialog._open_slicer_section()

    assert dialog.slicer_toggle is not None
    assert dialog.slicer_toggle.isChecked()
    assert dialog.slicer_inner.isVisibleTo(dialog.slicer_box)


def test_every_field_says_what_it_does(dialog: PrintSettingsDialog) -> None:
    """Sechsundfünfzig Felder, und keines erklärte sich.

    „Naht", „Bahnerzeuger", „Genaue Außenwand", „Flussverhältnis" — wer diese
    Wörter kennt, braucht den Dialog nicht, und wer sie nicht kennt, findet
    hier nichts, was ihn hineinlässt. Der Satz steht am Feld und ist keine
    Wiederholung des Titels: Er sagt, was passiert, wenn man den Wert bewegt.
    """
    stumm = [field.path for field in FIELDS if not field.note]
    assert not stumm, f"ohne Erklärung: {stumm}"

    schlecht = []
    for field in FIELDS:
        satz = str(field.note)
        if not satz.endswith((".", "!", "?")):
            schlecht.append(f"{field.path}: kein Satz — {satz!r}")
        if satz.strip().lower() == str(field.title).strip().lower():
            schlecht.append(f"{field.path}: nur der Titel wiederholt")
        if len(satz) > 220:
            schlecht.append(f"{field.path}: {len(satz)} Zeichen sind kein Tooltip mehr")
    assert not schlecht, "\n".join(schlecht)


def test_the_explanation_arrives_at_the_field_and_at_its_label(
    dialog: PrintSettingsDialog,
) -> None:
    """Am Feld, an der Beschriftung und in der Statuszeile.

    Wer eine Zeile nicht versteht, zeigt auf ihre Beschriftung — dort steht das
    unverständliche Wort. Ein Tooltip nur am Eingabefeld findet, wer schon
    weiß, wohin er greifen muss. Und ``accessibleDescription`` ist derselbe
    Satz für den, der den Bildschirm nicht liest.
    """
    fehlt = []
    for field in FIELDS:
        editor = dialog._editors[field.path]
        satz = str(field.note)
        if satz not in editor.toolTip():
            fehlt.append(f"{field.path}: Tooltip {editor.toolTip()!r}")
        # Der Farbknopf nennt zuerst den Hexwert und hängt den Satz an: der
        # Wert ist am Knopf nirgends sonst zu lesen, auf ihm steht der Name.
        # Der Satz darf ihn nicht verdrängen — beides oder keins.
        if isinstance(editor, _ColourButton) and "#" not in editor.toolTip():
            fehlt.append(f"{field.path}: der Farbwert ist aus dem Tooltip gefallen")
        if editor.statusTip():
            fehlt.append(f"{field.path}: Statustipp am Feld")
        if editor.accessibleDescription() != satz:
            fehlt.append(f"{field.path}: accessibleDescription fehlt")
    assert not fehlt, "\n".join(fehlt)

    beschriftungen = 0
    stumm = []
    for form in dialog.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            widget = item.widget() if item is not None else None
            if not isinstance(widget, QLabel):
                continue
            titel = widget.text().split(" [")[0]
            if titel not in {str(f.title) for f in FIELDS}:
                continue  # Drucker, Grundprofil, Filament — keine Einstellung
            beschriftungen += 1
            if not widget.toolTip():
                stumm.append(titel)
    assert not stumm, f"Beschriftung ohne Erklärung: {stumm}"
    assert beschriftungen >= 8, f"nur {beschriftungen} Beschriftungen gefunden"


def test_a_dialog_built_after_a_language_change_speaks_that_language(
    qt_app: QApplication, session: Session
) -> None:
    """Sechsundfünfzig Felder standen deutsch in einem englischen Fenster.

    ``FIELDS`` ist ein Modulrumpf, und ``tr()`` darin übersetzte **beim
    Import** — also in der Sprache, die zu diesem Zeitpunkt galt, und beim
    Start ist das noch keine. ``main_window.py`` zieht dieses Modul auf
    Modulebene nach, ``install_language`` läuft danach; und ein Sprachwechsel
    zur Laufzeit (``app.rebuild_for_language``) baut die **Fenster** neu auf,
    nicht die Module. Der größte Dialog der Anwendung blieb damit in der
    Startsprache.

    **Beide Schritte, sonst misst der Test seinen eigenen Aufbau**:
    ``install_language`` lädt den Katalog, ``set_language`` schaltet ihn
    scharf. Wer nur den zweiten ruft, bekommt überall die Message-ID zurück —
    also Deutsch — und hält den Rückfall für den Fehler.

    ``source_text`` gibt die Message-ID (den deutschen Quelltext), ``tr`` die
    Fassung in der jetzt gültigen Sprache: Damit braucht der Test keinen
    einzigen englischen Satz als Literal und altert nicht mit dem Katalog.
    """
    from app.i18n import get_language, set_language, source_text, tr
    from app.i18n.catalog import install_language

    vorher = get_language()
    try:
        install_language("en")
        set_language("en")

        gewandert = 0
        stehengeblieben = []
        for field in FIELDS:
            for teil, wert in (("Titel", field.title), ("Satz", field.note)):
                deutsch = source_text(wert)
                if not deutsch:
                    continue
                englisch = tr(deutsch, getattr(wert, "context", None))
                if englisch != deutsch:
                    gewandert += 1
                if str(wert) != englisch:
                    stehengeblieben.append(f"{field.path} ({teil}): {str(wert)!r}")
        assert not stehengeblieben, "in der Startsprache hängengeblieben:\n" + "\n".join(
            stehengeblieben
        )
        # Ohne diese Zusicherung wäre der Test auch dann grün, wenn der
        # englische Katalog gar nicht angekommen ist: Dann ist jede
        # Übersetzung gleich ihrer Message-ID, und die Schleife oben findet
        # nichts (`tests.md`, „Ein Verbotstest über eine leere Menge").
        assert gewandert >= 100, f"nur {gewandert} übersetzte Texte — kam der Katalog an?"

        # Und am gebauten Fenster, nicht nur an der Tabelle: Der Dialog liest
        # die Texte in ``_label`` und ``_editor``, und dort muss das ``str()``
        # stehen.
        gebaut = PrintSettingsDialog(session, UiSettings())
        hoehe = next(f for f in FIELDS if f.path == "layers.layer_height")
        texte = {label.text() for label in gebaut.findChildren(QLabel)}
        # Ohne Einheit in der Klammer, seit sie am Wert steht (B12) — der
        # Titel selbst ist der ganze Text der Beschriftung.
        assert tr(source_text(hoehe.title)) in texte
        assert source_text(hoehe.title) not in texte
        assert gebaut._editors[hoehe.path].suffix().strip() == "mm"
        assert gebaut._editors[hoehe.path].accessibleDescription() == tr(source_text(hoehe.note))
    finally:
        set_language(vorher)


def test_a_freshly_built_colour_row_carries_both(dialog: PrintSettingsDialog) -> None:
    """Am gebauten Dialog rettet ``_load_into_editors`` den Tooltip.

    Es ruft ``set_value`` und damit ``_refresh``, und der schreibt den Tooltip
    neu — der Hexwert wäre auch da, wenn ``_editor`` ihn vorher überschrieben
    hätte. Geprüft wird deshalb die Zeile, wie ``_editor`` sie verlässt: Dort
    liegt der Wächter, und dort fällt der Wert weg, wenn ihn jemand entfernt.
    """
    field = next(f for f in FIELDS if f.path == "filament.colour")

    editor = dialog._editor(field)

    assert isinstance(editor, _ColourButton)
    assert "#" in editor.toolTip(), "der Farbwert steht nirgends sonst"
    assert str(field.note) in editor.toolTip()


def test_the_colour_button_keeps_its_value_and_its_sentence(qt_app: QApplication) -> None:
    """Der eine Knopf, der seinen Tooltip selbst schreibt.

    Er trägt den Namen der Farbe und im Tooltip ihren Hexwert — den steht
    sonst nirgends. Nach jedem Klick baut ``_refresh`` den Tooltip neu; ein von
    außen gesetzter Satz wäre danach weg.
    """
    button = _ColourButton("#4a90d9", None, note="Die Farbe für die Vorschau.")

    assert "#4A90D9" in button.toolTip()
    assert "Die Farbe für die Vorschau." in button.toolTip()

    button.set_value("#101010")
    assert "#101010".upper() in button.toolTip()
    assert "Die Farbe für die Vorschau." in button.toolTip()


@pytest.mark.parametrize("slicer", [None, "PrusaSlicer.exe", "orca-slicer.exe"])
def test_slicer_hints_preserve_the_colour_last_chosen_in_the_dialog(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch, slicer: str | None
) -> None:
    """Eine erneuerte Sliceranzeige darf den Hexwert nicht auf die ursprüngliche Farbe setzen."""
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog

    dialog._slicer_path = Path(slicer) if slicer else None
    dialog._mark_fields_this_slicer_ignores()
    editor = dialog._editors["filament.colour"]
    own_description = editor.accessibleDescription()
    for colour in ("#123456", "#987654"):
        monkeypatch.setattr(QColorDialog, "getColor", lambda *_args, value=colour: QColor(value))
        editor.click()
        dialog._mark_fields_this_slicer_ignores()
        assert dialog.settings.filament.colour == colour
        assert colour.upper() in editor.toolTip()
        assert editor.accessibleDescription() == own_description


@pytest.mark.parametrize(
    ("slicer", "ignored"), [("superslicer.exe", True), ("PrusaSlicer.exe", False)]
)
def test_superslicer_greys_out_the_scarf_seam_and_drops_its_suggestion(
    dialog: PrintSettingsDialog, slicer: str, ignored: bool
) -> None:
    """RM-459: SuperSlicer gehört zur Prusa-Familie, kennt die Schrägnaht aber
    nicht. Das Feld sagt es, und ein Vorschlag darauf steht nicht in der Liste."""
    dialog._slicer_path = Path(slicer)
    dialog._mark_fields_this_slicer_ignores()
    editor = dialog._editors["shell.scarf_seam"]
    assert editor.isEnabled() is not ignored
    assert ("kennt diese Einstellung nicht" in editor.toolTip()) is ignored

    suggestion = SettingAdvice(path="shell.scarf_seam", value=True, was=False, reason="rund")
    dialog._advice_entries = [suggestion]
    assert (suggestion in dialog._current_advice()) is not ignored


@pytest.mark.parametrize("supported", [True, False, None])
def test_chamber_advice_requires_the_current_machines_heater(supported: bool | None) -> None:
    """Die reine Angebotsfunktion darf die graue Kammerzeile nicht umgehen."""
    from app.core.export import manufacturer
    from app.core.slice import advise

    profile = profiles.make_profile("centauri-carbon-2", "abs")
    settings = print_settings.with_path(print_settings.resolve(profile), "temperature.chamber", 0)
    foundation = manufacturer.Foundation(settings, chamber_control=supported)
    host = SimpleNamespace(
        _advice_entries=advise._from_material(settings, profile),
        _current_flavour=lambda: "orca",
        _slicer_path=Path("elegoo-slicer.exe"),
        _foundation_for_current_setup=lambda: foundation,
    )
    shown = PrintSettingsDialog._current_advice(host)
    assert any(entry.path == "temperature.chamber" for entry in shown) is (supported is True)
    assert settings.temperature.chamber == 0, "der gespeicherte Wert bleibt unverändert"


@pytest.mark.parametrize("supported", [True, False])
def test_rebase_refreshes_hardware_offers_even_when_values_are_unchanged(
    monkeypatch: pytest.MonkeyPatch, supported: bool
) -> None:
    """Die reine Anschlussprobe braucht kein Fenster und keine Ereignisschleife."""
    from app.core.export import manufacturer

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(Path("orca-slicer.exe"), "orca", base_process="Neu")
    foundation = manufacturer.Foundation(settings, chamber_control=supported)
    monkeypatch.setattr(manufacturer, "base_settings", lambda *_args: foundation)
    refreshed = []

    def nothing() -> None:
        pass

    host = SimpleNamespace(
        _settling=False,
        _built=True,
        _current_setup=lambda: setup,
        session=SimpleNamespace(profile=profile),
        settings=settings,
        _foundation_key=None,
        _foundation=manufacturer.Foundation(settings, chamber_control=not supported),
        _load_into_editors=nothing,
        _mark_fields_this_slicer_ignores=lambda: refreshed.append(host._foundation.chamber_control),
        _refresh_advice=nothing,
        _refresh_auto_adhesion_values=nothing,
        _update_inactive_setting_rows=nothing,
        _refresh_search_target_for_conditions=nothing,
        _mark_origins=nothing,
        _show_foundation=nothing,
    )
    PrintSettingsDialog._rebase(host)
    assert host.settings == settings
    assert refreshed == [supported]


@pytest.mark.parametrize("supported", [True, False, None])
def test_chamber_field_names_missing_hardware_and_recovers_after_selection(
    dialog: PrintSettingsDialog, supported: bool | None
) -> None:
    """Feld und Beschriftung erklären dieselbe belegte Maschinenfähigkeit."""
    from app.core.export import manufacturer

    dialog._slicer_path = Path("orca-slicer.exe")
    dialog._foundation = manufacturer.Foundation(dialog.settings, chamber_control=supported)
    dialog._mark_fields_this_slicer_ignores()
    editor = dialog._editors["temperature.chamber"]
    assert editor.isEnabled() is (supported is True)
    reason = manufacturer.chamber_limitation(dialog._foundation)
    if reason is not None:
        for widget in (editor, dialog._labels["temperature.chamber"]):
            assert widget.toolTip() == str(reason)
            assert widget.accessibleDescription() == str(reason)
    dialog._foundation = manufacturer.Foundation(dialog.settings, chamber_control=True)
    dialog._mark_fields_this_slicer_ignores()
    assert editor.isEnabled()
    assert "ohne Wirkung" not in editor.toolTip()
    assert "nicht belegt" not in editor.toolTip()


def test_superslicer_explains_tree_supports_and_restores_them_on_program_change(
    dialog: PrintSettingsDialog,
) -> None:
    """RM-480: Die gespeicherte Wahl bleibt, angeboten wird der wirksame Ersatz.

    Der Fensterfall gehört zum Release; der Kernersatz wird getrennt geprüft.
    """
    from PySide6.QtTest import QTest

    editor = dialog._editors["support.style"]
    assert isinstance(editor, QComboBox)
    tree = editor.findData("tree")
    assert tree >= 0
    own_tip = editor.itemData(tree, Qt.ItemDataRole.ToolTipRole)
    editor.setCurrentIndex(tree)
    dialog._slicer_path = Path("superslicer.exe")
    dialog._mark_fields_this_slicer_ignores()
    assert editor.currentData() == "tree"
    assert dialog.settings.support.style == "tree"
    assert not editor.model().flags(editor.model().index(tree, 0)) & Qt.ItemFlag.ItemIsEnabled
    assert "Gitter" in editor.toolTip()
    assert "Gitter" in editor.itemData(tree, Qt.ItemDataRole.AccessibleDescriptionRole)
    editor.setCurrentIndex(editor.findData("grid"))
    for key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
        for _ in range(editor.count()):
            QTest.keyClick(editor, key)
            assert editor.currentData() != "tree"
    dialog._slicer_path = Path("PrusaSlicer.exe")
    dialog._mark_fields_this_slicer_ignores()
    assert editor.model().flags(editor.model().index(tree, 0)) & Qt.ItemFlag.ItemIsEnabled
    assert editor.itemData(tree, Qt.ItemDataRole.ToolTipRole) == own_tip
    editor.setCurrentIndex(tree)
    assert dialog.settings.support.style == "tree"


def test_a_part_that_fits_no_bed_is_named_before_slicing(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KUNDE-09: Der Laptop-Ständer (205 × 272 mm) passt in keiner Drehung auf
    das Bett. *Slicen* rechnete trotzdem Minuten und endete mit „hat nicht
    geantwortet" und einer Zahl. Jetzt steht oben, um wie viel es zu groß ist,
    daneben *Modell teilen* und *Auf den Bauraum verkleinern*, und *Slicen*
    nennt denselben Grund. Ein passender Würfel bekommt nichts davon."""
    import types as types_module

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.ui import print_settings_dialog as module

    width = dialog.session.profile.printer.build_volume[0]
    slab = trimesh.creation.box(extents=(width + 30.0, width + 30.0, 10.0))
    slab.apply_translation((0.0, 0.0, 5.0))
    big = SceneObject(id="obj_1", name="Ständer", mesh=MeshData.of(slab))
    called: list[tuple[str, object]] = []
    window_handlers = {
        "split_model": lambda error: called.append(("split_model", error.object_id)),
        "scale_to_fit": lambda error: called.append(("scale_to_fit", error.object_id)),
    }
    monkeypatch.setattr(module, "handlers_of", lambda _widget: window_handlers)

    scene = types_module.SimpleNamespace(objects={"obj_1": big})
    monkeypatch.setattr(
        dialog.session,
        "last_result",
        types_module.SimpleNamespace(scene=scene, object_names={}, stopped_at=None),
    )
    # Die Ersatzszene gilt als feine Rechnung, sonst wartet der Klick auf sie
    # (RM-426, ``_wait_for_fine``).
    monkeypatch.setattr(type(dialog.session), "fine_current", property(lambda _self: True))
    # Ein Slicer ist da — ohne ihn nennt *Slicen* zu Recht zuerst den fehlenden
    # Slicer, und die Suite fragt die Maschine nicht (``_machine_stays_out_of_it``).
    dialog._slicer_path = Path("prusa-slicer-console")
    dialog._show_slicer_state()

    assert "Ständer" in dialog.oversize_note.text()
    assert "zu groß" in dialog.oversize_note.text()
    assert not dialog.oversize_note.isHidden()
    assert not dialog.slice_button.isEnabled()
    assert dialog.slice_button.toolTip() == dialog.oversize_note.text()
    buttons = {
        button.text(): button for button in dialog._oversize_actions.findChildren(QPushButton)
    }
    assert set(buttons) == {"Modell teilen", "Auf den Bauraum verkleinern"}
    buttons["Modell teilen"].click()
    assert called == [("split_model", "obj_1")]

    small = types_module.SimpleNamespace(objects={"obj_1": _cube_object()})
    monkeypatch.setattr(dialog.session, "last_result", _shown_result(small))
    dialog._show_slicer_state()
    assert dialog.oversize_note.isHidden()


def test_the_cura_fan_hint_follows_the_number_of_layers(dialog: PrintSettingsDialog) -> None:
    """Curas Hochlauf trifft null und eine Schicht ohne Lüfter genau; ab zwei
    laufen die Schichten dazwischen an, und nur dann nennt das Feld es.

    Der Dialog fragte ``slicer_keys.limitation`` ohne die Einstellungen — und
    die antwortet dann immer mit nichts: Seit der Hinweis am Wert hängt, stand
    er im Dialog nie, auch nicht bei drei Schichten ohne Lüfter."""
    dialog._slicer_path = Path("CuraEngine.exe")
    editor = dialog._editors["cooling.disable_first_layers"]

    editor.setValue(3)
    assert "Lüfterpause" in editor.toolTip()
    assert "4" in editor.toolTip(), "hoch bis zur ersten Schicht danach"

    editor.setValue(1)
    assert "Lüfterpause" not in editor.toolTip()


# --- ohne Slicer --------------------------------------------------------------------


def test_the_dialog_opens_without_a_slicer(
    monkeypatch: pytest.MonkeyPatch, session: Session
) -> None:
    """§27: das Backend meldet sich ab, es nörgelt nicht — die Einstellungen
    bleiben trotzdem pflegbar."""
    monkeypatch.setattr("app.core.discover.find_program", lambda *args, **kwargs: None)

    dialog = PrintSettingsDialog(session, UiSettings())

    assert not dialog.slice_button.isEnabled()
    assert dialog.state.text()
    assert dialog._editors["layers.layer_height"].isEnabled()


def test_slicing_without_a_scene_says_what_is_missing(dialog: PrintSettingsDialog) -> None:
    dialog._slice()
    assert dialog.state.text()


# --- die zweite Übergabeart (§29) ----------------------------------------------------


def test_opening_hands_the_plates_to_the_window_and_remembers(
    monkeypatch: pytest.MonkeyPatch, dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """Der Öffnen-Knopf schreibt die Platten und ruft das Fenster — und die
    benutzte Übergabeart wird gemerkt (§29), damit sie beim nächsten Aufbau
    der Hauptweg ist."""
    import types as types_module

    from app.ui import print_settings_dialog as module

    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    dialog._slicer_path = executable
    written = tmp_path / "platte.3mf"
    written.write_bytes(b"x")
    scene = types_module.SimpleNamespace(objects={"obj_1": _cube_object()})
    # ``last_result`` ist ein schlichtes Instanzattribut — direkt setzen,
    # wie es die Auswertung selbst tut.
    monkeypatch.setattr(
        dialog.session,
        "last_result",
        types_module.SimpleNamespace(scene=scene, object_names={}, stopped_at=None),
    )
    # Die Ersatzszene gilt als feine Rechnung, sonst wartet der Klick auf sie
    # (RM-426, ``_wait_for_fine``).
    monkeypatch.setattr(type(dialog.session), "fine_current", property(lambda _self: True))
    monkeypatch.setattr(dialog, "_chosen_plates", lambda: [0])
    monkeypatch.setattr(dialog, "_plate_slots", list)
    # ``with_settings`` wird mitgelesen und nicht nur geschluckt: Der
    # Übergabeweg reicht die Wahl des Kunden durch, und ein Ersatz mit
    # ``**kwargs`` wäre an dieser Stelle blind für sie.
    handed: list[bool] = []

    def _run(job: object, plate: int) -> object:
        handed.append(job.with_settings)
        return module.PlateRun(
            plate=plate,
            model=written,
            slots=(MaterialSlot(0, ""),),
            keep_arrangement=False,
            findings=(),
        )

    monkeypatch.setattr(module, "_prepare_plate", _run)
    opened: list[tuple[Path, object]] = []
    monkeypatch.setattr(
        module.handover, "open_in_slicer", lambda model, setup: opened.append((model, setup))
    )

    assert dialog.settings.handover == "slice", "die Vorgabe ist der bisherige Weg"
    dialog._open_in_slicer()
    assert dialog._worker is not None
    assert dialog._worker.wait(5_000)
    QApplication.processEvents()

    assert opened and opened[0][0] == written, "das Fenster bekommt die geschriebene Datei"
    assert dialog.settings.handover == "open", "die benutzte Art ist gemerkt"
    assert dialog.state.text(), "die Handlung quittiert sich (§2.8)"
    assert handed == [True], "und die Wahl des Kunden reist mit — hier vorbelegt mit ja"

    # Und die Gegenrichtung: Wer den Haken wegnimmt, öffnet den Slicer mit
    # dessen eigenem Profil.
    dialog.ui_settings.print_settings_in_files = False
    dialog._open_in_slicer()
    assert dialog._worker is not None
    assert dialog._worker.wait(5_000)
    QApplication.processEvents()
    assert handed == [True, False]


@pytest.mark.parametrize("way", ["open", "slice"])
def test_an_error_in_the_report_is_named_before_the_model_leaves(
    monkeypatch: pytest.MonkeyPatch, dialog: PrintSettingsDialog, tmp_path: Path, way: str
) -> None:
    """Der Export fragte bei Fehlern, die Übergabe an den Slicer nicht.

    Beide schicken das Modell hinaus, und keins von beiden holt ein Strg+Z
    zurück (Regel 19 erlaubt hier die Frage). Wer abbricht, übergibt nichts
    und behält seine Übergabeart; ein Fehler auf einer anderen Platte oder
    eine bloße Warnung hält niemanden auf.
    """
    import types as types_module

    from app.core.types import Finding, Report
    from app.ui import print_settings_dialog as module

    executable = tmp_path / "prusa-slicer.exe"
    executable.write_bytes(b"")
    dialog._slicer_path = executable
    cube = _cube_object()
    other = replace(_cube_object(), id="obj_2", plate=1)
    broken = Finding(
        code="ingest.not_watertight",
        severity="error",
        message="Der Körper ist nicht geschlossen.",
        object_id="obj_1",
    )
    elsewhere = replace(broken, object_id="obj_2", message="Auf Platte 2")
    warning = replace(broken, severity="warning", message="Nur eine Warnung")
    scene = types_module.SimpleNamespace(
        objects={"obj_1": cube, "obj_2": other},
        report=Report((broken, elsewhere, warning)),
    )
    monkeypatch.setattr(
        dialog.session,
        "last_result",
        types_module.SimpleNamespace(scene=scene, object_names={}, stopped_at=None),
    )
    # Die Ersatzszene gilt als feine Rechnung, sonst wartet der Klick auf sie
    # (RM-426, ``_wait_for_fine``).
    monkeypatch.setattr(type(dialog.session), "fine_current", property(lambda _self: True))
    monkeypatch.setattr(dialog, "_chosen_plates", lambda: [0])
    monkeypatch.setattr(dialog, "_plate_slots", list)
    asked: list[list[str]] = []
    answer = {"go": False}

    def ask(findings: list[Finding], _parent: object) -> bool:
        asked.append([str(entry.message) for entry in findings])
        return answer["go"]

    monkeypatch.setattr(module, "confirm_handover", ask)
    reported: list[object] = []
    dialog.reported.connect(reported.append)
    started: list[object] = []
    monkeypatch.setattr(dialog._leash, "start", started.append)
    before = dialog.settings.handover

    (dialog._open_in_slicer if way == "open" else dialog._slice)()

    assert asked == [["Der Körper ist nicht geschlossen."]], (
        "gefragt wird mit den Fehlern der gewählten Platte, ohne Warnung und fremde Platte"
    )
    assert not started, "abgebrochen heißt: nichts geht hinaus"
    assert dialog.settings.handover == before, "und die Übergabeart bleibt, wie sie war"
    assert "Prüfbericht" in dialog.state.text()
    assert reported, "die Fehler landen im Prüfbericht"

    answer["go"] = True
    (dialog._open_in_slicer if way == "open" else dialog._slice)()
    assert len(asked) == 2
    assert started, "weitergehen übergibt"


@pytest.mark.parametrize(
    ("program", "files"),
    [
        pytest.param("elegoo-slicer.exe", 1, id="Orca-Familie: eine Datei"),
        pytest.param("prusa-slicer.exe", 2, id="PrusaSlicer: je eine"),
    ],
)
def test_several_plates_open_as_one_project_where_the_slicer_knows_plates(
    monkeypatch: pytest.MonkeyPatch,
    dialog: PrintSettingsDialog,
    tmp_path: Path,
    program: str,
    files: int,
) -> None:
    """Vier Platten sind für die Orca-Familie eine Projektdatei — und ein Fenster.

    **Der Anlass** (Robert, 11.09.2026: „jede platte öffnet ein weiteres
    Slicerfenster, statt alle platten in einem zum öffnen"): Je Platte eine
    Datei hieß je Platte ein Fenster, und vier Starts des ElegooSlicers auf
    einmal stritten um dieselbe Filamentbibliothek, bis einer mit „remove_all:
    Zugriff verweigert" abbrach. Der Slicer speichert seine Projekte selbst
    mit mehreren Platten, und dieselbe Datei schreibt *Exportieren* längst
    (``write_assembly`` ohne ``plate``).

    PrusaSlicer kennt eine Platte je Datei und bekommt weiter je eine.
    """
    import types as types_module

    from app.ui import print_settings_dialog as module

    executable = tmp_path / program
    executable.write_bytes(b"")
    dialog._slicer_path = executable
    written = tmp_path / "projekt.3mf"
    written.write_bytes(b"x")
    first = _cube_object()
    second = replace(_cube_object(), id="obj_2", plate=1)
    scene = types_module.SimpleNamespace(objects={"obj_1": first, "obj_2": second})
    monkeypatch.setattr(
        dialog.session,
        "last_result",
        types_module.SimpleNamespace(scene=scene, object_names={}, stopped_at=None),
    )
    # Die Ersatzszene gilt als feine Rechnung, sonst wartet der Klick auf sie
    # (RM-426, ``_wait_for_fine``).
    monkeypatch.setattr(type(dialog.session), "fine_current", property(lambda _self: True))
    monkeypatch.setattr(dialog, "_chosen_plates", lambda: [0, 1])
    monkeypatch.setattr(dialog, "_plate_slots", list)

    projects: list[tuple[int, ...]] = []
    plates: list[int] = []

    def _project(job: object) -> object:
        projects.append(job.plates)
        return module.ProjectRun(
            model=written, slots_by_plate={0: (MaterialSlot(0, ""),), 1: (MaterialSlot(0, ""),)}
        )

    def _plate(job: object, plate: int) -> object:
        plates.append(plate)
        return module.PlateRun(plate=plate, model=written, slots=(MaterialSlot(0, ""),))

    monkeypatch.setattr(module, "_prepare_plates", _project)
    monkeypatch.setattr(module, "_prepare_plate", _plate)
    opened: list[Path] = []
    monkeypatch.setattr(
        module.handover, "open_in_slicer", lambda model, setup: opened.append(model)
    )

    dialog._open_in_slicer()
    assert dialog._worker is not None
    assert dialog._worker.wait(5_000)
    QApplication.processEvents()

    assert len(opened) == files, f"{len(opened)} Fenster für zwei Platten"
    if files == 1:
        assert projects == [(0, 1)], "beide Platten in einer Projektdatei"
        assert not plates, "und keine Datei je Platte daneben"
        assert "in einer Datei" in dialog.state.text(), dialog.state.text()
    else:
        assert plates == [0, 1] and not projects
        assert "je eine Datei" in dialog.state.text(), dialog.state.text()


def test_plate_files_are_prepared_outside_the_qt_thread(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die 3MF-Serialisierung steht vor dem Slicer und gehört mit in den Arbeiter."""
    import threading
    import types as types_module

    from app.core.errors import OperationCancelled
    from app.ui import print_settings_dialog as module

    executable = tmp_path / "prusa-slicer-console.exe"
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(executable=executable, flavour="prusa")
    scene = types_module.SimpleNamespace(objects={"obj_1": _cube_object()})
    monkeypatch.setattr(
        dialog.session,
        "last_result",
        types_module.SimpleNamespace(scene=scene, object_names={}, stopped_at=None),
    )
    # Die Ersatzszene gilt als feine Rechnung, sonst wartet der Klick auf sie
    # (RM-426, ``_wait_for_fine``).
    monkeypatch.setattr(type(dialog.session), "fine_current", property(lambda _self: True))
    monkeypatch.setattr(dialog, "_current_setup", lambda: setup)
    monkeypatch.setattr(dialog, "_chosen_plates", lambda: [0])
    monkeypatch.setattr(dialog, "_plate_slots", list)

    threads: list[int] = []
    model = tmp_path / "platte.3mf"
    model.write_bytes(b"")

    def prepare(_job: object, plate: int) -> object:
        threads.append(threading.get_ident())
        return module.PlateRun(plate=plate, model=model, slots=(MaterialSlot(0, ""),))

    monkeypatch.setattr(module, "_prepare_plate", prepare)
    monkeypatch.setattr(
        module.handover,
        "slice_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OperationCancelled()),
    )
    qt_thread = threading.get_ident()

    dialog._slice()

    assert dialog.progress.isVisibleTo(dialog), "Fortschritt steht vor der Vorbereitung"
    assert dialog.cancel_slice.isEnabled(), "auch die Vorbereitung lässt sich abbrechen"
    assert dialog._worker is not None and dialog._worker.wait(5_000)
    QApplication.processEvents()
    assert threads and threads[0] != qt_thread, "die 3MF-Datei wurde im Qt-Thread geschrieben"


def test_closing_does_not_wait_in_the_qt_thread_for_plate_preparation(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Schließen bleibt bedienbar, solange die 3MF-Datei geschrieben wird.

    Der neue Aufbereiter kann nicht mitten in ``write_assembly`` anhalten.
    Deshalb muss der Dialog den Abschluss abwarten, ohne seinerseits im
    Qt-Hauptthread auf ``QThread.wait()`` stehen zu bleiben (§2.8).
    """
    import types as types_module

    from app.ui import print_settings_dialog as module

    executable = tmp_path / "prusa-slicer-console.exe"
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(executable=executable, flavour="prusa")
    scene = types_module.SimpleNamespace(objects={"obj_1": _cube_object()})
    monkeypatch.setattr(
        dialog.session,
        "last_result",
        types_module.SimpleNamespace(scene=scene, object_names={}, stopped_at=None),
    )
    # Die Ersatzszene gilt als feine Rechnung, sonst wartet der Klick auf sie
    # (RM-426, ``_wait_for_fine``).
    monkeypatch.setattr(type(dialog.session), "fine_current", property(lambda _self: True))
    monkeypatch.setattr(dialog, "_current_setup", lambda: setup)
    monkeypatch.setattr(dialog, "_chosen_plates", lambda: [0])
    monkeypatch.setattr(dialog, "_plate_slots", list)

    started = threading.Event()
    release = threading.Event()
    model = tmp_path / "platte.3mf"

    def prepare(_job: object, plate: int) -> object:
        started.set()
        release.wait(1.0)
        model.write_bytes(b"")
        return module.PlateRun(plate=plate, model=model, slots=(MaterialSlot(0, ""),))

    monkeypatch.setattr(module, "_prepare_plate", prepare)
    dialog._slice()
    worker = dialog._worker
    assert worker is not None and started.wait(1.0)

    delayed_release = threading.Timer(0.5, release.set)
    delayed_release.start()
    try:
        begun = time.perf_counter()
        dialog.reject()
        elapsed = time.perf_counter() - begun
    finally:
        release.set()
        delayed_release.cancel()

    assert elapsed < 0.2, f"das Schließen blockierte den Qt-Thread {elapsed:.2f} s"
    assert worker.cancelled.is_cancelled
    assert worker.wait(2_000)

    deadline = time.monotonic() + 1.0
    while not dialog._settled and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    assert dialog._settled, "der Dialog wurde nach dem Arbeiter nicht zu Ende geschlossen"


def test_closing_ignores_a_worker_error_already_waiting_in_qt(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein eingereihtes Ergebnis darf nach dem Dialogausgang kein Fenster mehr öffnen."""
    from app.ui import print_settings_dialog as module

    source = tmp_path / "source.gcode"
    source.write_bytes(b"G1 X1\n")
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x", encoding="utf-8")
    shown: list[object] = []
    monkeypatch.setattr(module, "show_error", lambda problem, parent=None: shown.append(problem))

    dialog._start_gcode_save(((source, blocker / "target.gcode"),))
    worker = dialog._worker
    assert worker is not None and worker.wait(2_000)

    dialog.reject()
    QApplication.processEvents()

    assert shown == [], "ein vor dem Schließen eingereihter Fehler öffnete danach noch einen Dialog"


@pytest.mark.parametrize("outcome", ["sliced", "failed", "cancelled"])
def test_only_a_finished_slicer_start_counts_as_handed_over(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """``handedOver`` kommt mit dem Ergebnis — und nur dann (Robert, 23.09.2026).

    Das Fenster zählt daran die Ergebnisse bis zur Einladung zur Unterstützung.
    Ein Slicer, der scheitert, und ein Lauf, den der Kunde abbricht, sind kein
    Erfolg und dürfen die Einladung nicht näher bringen.
    """
    import types as types_module

    from app.core.errors import ExternalToolError
    from app.ui import print_settings_dialog as module

    executable = tmp_path / "prusa-slicer-console.exe"
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(executable=executable, flavour="prusa")
    scene = types_module.SimpleNamespace(objects={"obj_1": _cube_object()})
    monkeypatch.setattr(
        dialog.session,
        "last_result",
        types_module.SimpleNamespace(scene=scene, object_names={}, stopped_at=None),
    )
    # Die Ersatzszene gilt als feine Rechnung, sonst wartet der Klick auf sie
    # (RM-426, ``_wait_for_fine``).
    monkeypatch.setattr(type(dialog.session), "fine_current", property(lambda _self: True))
    monkeypatch.setattr(dialog, "_current_setup", lambda: setup)
    monkeypatch.setattr(dialog, "_chosen_plates", lambda: [0])
    monkeypatch.setattr(dialog, "_plate_slots", list)
    model = tmp_path / "platte.3mf"
    model.write_bytes(b"")
    output = tmp_path / "platte.gcode"
    output.write_text("G1 X1\n", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "_prepare_plate",
        lambda _job, plate: module.PlateRun(plate=plate, model=model, slots=(MaterialSlot(0, ""),)),
    )

    def slicing(*_args: object, **_kwargs: object) -> handover.SliceOutcome:
        if outcome == "failed":
            raise ExternalToolError(tool="slicer", detail="Der Slicer hat abgebrochen.")
        return handover.SliceOutcome(gcode_path=output, metrics=gcode.GcodeMetrics())

    monkeypatch.setattr(module.handover, "slice_model", slicing)
    monkeypatch.setattr(module, "show_error", lambda *args, **kwargs: None)
    handed: list[bool] = []
    dialog.handedOver.connect(lambda: handed.append(True))

    dialog._slice()
    worker = dialog._worker
    assert worker is not None and worker.wait(5_000)
    if outcome == "cancelled":
        dialog._cancel_slice()
    QApplication.processEvents()

    assert handed == ([True] if outcome == "sliced" else []), outcome


def test_opening_in_the_slicer_counts_as_handed_over(
    monkeypatch: pytest.MonkeyPatch, dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """*Im Slicer öffnen* ist ebenso ein Slicer-Start wie *Slicen*."""
    import types as types_module

    from app.ui import print_settings_dialog as module

    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    dialog._slicer_path = executable
    written = tmp_path / "platte.3mf"
    written.write_bytes(b"x")
    scene = types_module.SimpleNamespace(objects={"obj_1": _cube_object()})
    monkeypatch.setattr(
        dialog.session,
        "last_result",
        types_module.SimpleNamespace(scene=scene, object_names={}, stopped_at=None),
    )
    # Die Ersatzszene gilt als feine Rechnung, sonst wartet der Klick auf sie
    # (RM-426, ``_wait_for_fine``).
    monkeypatch.setattr(type(dialog.session), "fine_current", property(lambda _self: True))
    monkeypatch.setattr(dialog, "_chosen_plates", lambda: [0])
    monkeypatch.setattr(dialog, "_plate_slots", list)
    monkeypatch.setattr(
        module,
        "_prepare_plate",
        lambda _job, plate: module.PlateRun(
            plate=plate, model=written, slots=(MaterialSlot(0, ""),), keep_arrangement=False
        ),
    )
    monkeypatch.setattr(module.handover, "open_in_slicer", lambda model, setup: None)
    handed: list[bool] = []
    dialog.handedOver.connect(lambda: handed.append(True))

    dialog._open_in_slicer()
    assert dialog._worker is not None
    assert dialog._worker.wait(5_000)
    QApplication.processEvents()

    assert handed == [True]


@pytest.mark.parametrize("changed", [False, True])
def test_cancelling_rejects_a_slice_result_already_waiting_in_qt(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: bool
) -> None:
    """Ein eingereihtes Slicer-Ergebnis wird nach Abbrechen nicht mehr übernommen."""
    import types as types_module

    from app.ui import print_settings_dialog as module

    executable = tmp_path / "prusa-slicer-console.exe"
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(executable=executable, flavour="prusa")
    scene = types_module.SimpleNamespace(objects={"obj_1": _cube_object()})
    monkeypatch.setattr(
        dialog.session,
        "last_result",
        types_module.SimpleNamespace(scene=scene, object_names={}, stopped_at=None),
    )
    # Die Ersatzszene gilt als feine Rechnung, sonst wartet der Klick auf sie
    # (RM-426, ``_wait_for_fine``).
    monkeypatch.setattr(type(dialog.session), "fine_current", property(lambda _self: True))
    monkeypatch.setattr(dialog, "_current_setup", lambda: setup)
    monkeypatch.setattr(dialog, "_chosen_plates", lambda: [0])
    monkeypatch.setattr(dialog, "_plate_slots", list)
    model = tmp_path / "platte.3mf"
    model.write_bytes(b"")
    output = tmp_path / "platte.gcode"
    output.write_text("G1 X1\n", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "_prepare_plate",
        lambda _job, plate: module.PlateRun(plate=plate, model=model, slots=(MaterialSlot(0, ""),)),
    )
    monkeypatch.setattr(
        module.handover,
        "slice_model",
        lambda *_args, **_kwargs: handover.SliceOutcome(
            gcode_path=output,
            metrics=gcode.GcodeMetrics(),
        ),
    )
    delivered: list[object] = []
    dialog.sliced.connect(delivered.append)

    dialog._slice()
    worker = dialog._worker
    assert worker is not None and worker.wait(2_000)

    if changed:
        field = dialog._editors["temperature.nozzle"]
        field.setValue(field.value() + 5)
    else:
        dialog._cancel_slice()
    QApplication.processEvents()

    assert dialog._gcode == []
    assert delivered == []
    assert dialog.slice_comparison is None
    if not changed:
        assert tr("Abgebrochen.") in dialog.state.text()


def test_opening_is_not_remembered_by_merely_looking(dialog: PrintSettingsDialog) -> None:
    """Gemerkt wird bei Nutzung, nie bei Ansicht: Der Dialog steht offen, und
    die Übergabeart bleibt, was sie war."""
    assert dialog.settings.handover == "slice"


def test_the_remembered_handover_makes_its_button_primary(
    qt_app: QApplication, session: Session
) -> None:
    """Der gemerkte Weg ist der Hauptknopf — entschieden beim Aufbau (§29)."""
    from dataclasses import replace

    from app.core.knowledge import print_settings as knowledge_settings

    stored = replace(knowledge_settings.resolve(session.profile), handover="open")
    session.project.document.print_settings = stored

    dialog = PrintSettingsDialog(session, UiSettings())
    try:
        assert dialog.open_button.isDefault(), "der gemerkte Weg trägt den Hauptknopf"
        assert not dialog.slice_button.isDefault()
    finally:
        dialog.release()
        dialog.deleteLater()


def test_opening_needs_a_window_and_says_so(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """CuraEngine allein rechnet nur — der Öffnen-Knopf sperrt mit Grund an
    beiden Kodierungen (Regel 18), der Rechen-Knopf bleibt davon unberührt."""
    engine = tmp_path / "CuraEngine.exe"
    engine.write_bytes(b"")
    dialog._slicer_path = engine

    dialog._show_slicer_state()

    assert not dialog.open_button.isEnabled()
    assert "Fenster" in dialog.open_button.toolTip()
    assert dialog.open_button.accessibleDescription()
    assert dialog.slice_button.isEnabled(), "der Rechen-Weg kann, was er konnte"


class WaitingWorker:
    """Ein Arbeiter, der nur Buch führt: läuft, bis jemand auf ihn wartet.

    Der echte startet nur, wenn ein Slicer installiert ist und zur
    Orca-Familie gehört — ein Test, der das voraussetzt, prüft die Maschine des
    Bauservers.
    """

    def __init__(self) -> None:
        self.waited: list[int | None] = []
        self.cancelled = False

    def isRunning(self) -> bool:  # noqa: N802 — Qt gibt den Namen vor
        return not self.waited

    def cancel(self) -> None:
        self.cancelled = True

    def wait(self, timeout_ms: int | None = None) -> bool:
        self.waited.append(timeout_ms)
        return True


@pytest.mark.parametrize("work", ["profile", "stock"])
def test_closing_explains_why_profile_or_stock_work_keeps_the_window_open(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch, work: str
) -> None:
    """Auch ohne Slicerauftrag bleibt der aufgeschobene Fensterabschluss sichtbar erklärt."""
    from PySide6.QtTest import QTest

    from app.ui import print_settings_dialog as module

    entered, released = threading.Event(), threading.Event()

    def blocked(*_args, **_kwargs):
        entered.set()
        assert released.wait(3)
        return []

    if work == "profile":
        monkeypatch.setattr(module.slicer_profiles, "find_profiles", blocked)
        worker = module._ProfileWorker(Path("orca-slicer.exe"), "orca")
        dialog._profile_worker = worker
    else:
        monkeypatch.setattr(module, "prepare_usage", blocked)
        worker = module._StockWorker((), dialog.settings, dialog.session.profile)
        dialog._stock_worker = worker
    dialog.show()
    dialog._leash.start(worker)
    try:
        assert entered.wait(1)
        dialog.reject()
        assert not dialog.isHidden()
        assert dialog.isEnabled()
        assert dialog.state.isEnabled()
        assert dialog.progress.isEnabled()
        assert not dialog.slice_button.isEnabled()
        assert not dialog.open_button.isEnabled()
        assert not dialog._editors["layers.layer_height"].isEnabled()
        assert not dialog.machine_choice.isEnabled()
        assert dialog.state.isVisibleTo(dialog)
        assert "geschlossen" in dialog.state.text()
        assert "laufenden Arbeiten" in dialog.state.text()
        QTest.qWait(20)
        assert not dialog._settled
    finally:
        released.set()
        assert worker.wait(2_000)
        deadline = time.monotonic() + 2
        while not dialog._settled and time.monotonic() < deadline:
            QTest.qWait(10)
    assert dialog._settled
    assert dialog.isHidden()


def test_every_way_out_waits_for_the_profile_search(dialog: PrintSettingsDialog) -> None:
    """Ein Thread, der sein Fenster überlebt, nimmt den Prozess mit.

    Der Dialog wartete im ``closeEvent`` — und das kommt nur, wenn das Fenster
    geschlossen wird. *Slicen* und *Abbrechen* gehen über ``done``, und Qt
    schickt dabei kein Schließereignis: Gemessen lief die Profilsuche nach
    ``accept()`` weiter, während der Aufrufer seine Referenz fallen ließ.

    Der dritte Weg ist der der Suite: Dort wird ein Dialog **weggeräumt**, nicht
    geschlossen. Die Aufräumhilfe in ``tests/conftest.py`` sucht dafür
    ``wait_for_workers`` an jedem obersten Fenster — ein Dialog ohne diesen
    Namen bleibt unbeachtet, mit laufendem Arbeiter.
    """
    worker = WaitingWorker()
    dialog._profile_worker = worker  # type: ignore[assignment]

    dialog.accept()

    assert worker.waited, "der Knopf ging hinaus, ohne auf die Suche zu warten"

    second = PrintSettingsDialog(dialog.session, UiSettings())
    later = WaitingWorker()
    second._profile_worker = later  # type: ignore[assignment]
    try:
        second.wait_for_workers()
        assert later.waited, "und weggeräumt wird auch gewartet"
        assert later.waited[0] is not None, "dort mit Grenze — ein hängender Arbeiter fällt auf"
    finally:
        second.deleteLater()


def test_cura_printer_suggestion_does_not_hold_the_dialog_open(
    dialog: PrintSettingsDialog,
) -> None:
    """Der optionale Cura-Abgleich läuft nach dem Schließen sicher weiter."""
    from app.ui import print_settings_dialog as module

    entered, released = threading.Event(), threading.Event()

    class WaitingCuraPrinterWorker(module._CuraPrinterWorker):
        def work(self) -> None:
            entered.set()
            assert released.wait(3)

    worker = WaitingCuraPrinterWorker(Path("Cura.exe"), profiles.printer_profiles())
    dialog._cura_printer_worker = worker
    dialog._leash.start(worker)
    try:
        assert entered.wait(1)
        assert dialog._settle(0)
        assert worker.isRunning(), "die optionale Profilprüfung darf den Schluss nicht halten"
    finally:
        released.set()
        assert worker.wait(2_000)
        dialog._leash.wait_all(2_000)


def test_cura_without_an_active_machine_is_not_reported_as_failed_adoption(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ui import print_settings_dialog as module

    monkeypatch.setattr(module.slicer_profiles, "chosen_printer", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(module.slicer_profiles, "chosen_machine", lambda *_args: "")
    result: list[module._CuraPrinterSuggestion] = []
    worker = module._CuraPrinterWorker(Path("CuraEngine.exe"), profiles.printer_profiles())
    worker.done.connect(result.append)
    worker.work()

    assert len(result) == 1
    assert result[0].printer_id == ""
    assert not result[0].unreadable
    dialog._cura_printer_found(result[0])
    # Gemeint ist „kein Satz über eine gescheiterte Übernahme“; die Zeile
    # darf weiter sagen, was der Profilbestand gerade tut (RM-417).
    assert "ließ sich nicht übernehmen" not in dialog.profile_note.text()
    assert dialog._cura_printer_id == ""
    assert dialog.adopt_printer.isHidden()

    monkeypatch.setattr(
        module.slicer_profiles, "chosen_machine", lambda *_args: "cura-instance:broken"
    )
    monkeypatch.setattr(module.slicer_profiles, "profile_by_name", lambda *_args: None)
    unreadable: list[module._CuraPrinterSuggestion] = []
    worker = module._CuraPrinterWorker(Path("CuraEngine.exe"), profiles.printer_profiles())
    worker.done.connect(unreadable.append)
    worker.work()

    assert len(unreadable) == 1 and unreadable[0].unreadable
    dialog._cura_printer_found(unreadable[0])
    assert "ließ sich nicht übernehmen" in dialog.profile_note.text()


def test_a_slicer_without_profiles_gets_a_way_out(dialog: PrintSettingsDialog) -> None:
    """Regel 17: „Keine Profile gefunden — ohne sie lehnt dieser Slicer den
    Auftrag ab." war die ganze Auskunft.

    Ein Satz über den Zustand, und dann nichts. Wer einen Slicer gerade
    installiert hat, hat genau diesen Zustand — die Profile entstehen erst,
    wenn er einmal gelaufen ist und einen Drucker kennt. Das steht jetzt dabei.

    Geprüft wird an der Zahl der Sätze und nicht am Wortlaut: ein Text, den
    der Test buchstäblich mitliest, prüft sich selbst.
    """
    dialog._profiles_found([])

    note = dialog.profile_note.text()
    assert note, "ohne Profile bleibt der Hinweis vom Suchen stehen"
    sentences = [part for part in note.replace("!", ".").split(".") if part.strip()]
    assert len(sentences) >= 2, f"der Hinweis endet bei der Feststellung: {note!r}"
    assert not dialog.machine_choice.isEnabled(), "und die Auswahl bleibt leer und gesperrt"


def test_both_orca_profiles_are_asked_for_before_the_run(qt_app: QApplication) -> None:
    """Die Orca-Familie braucht zwei Profile, geprüft wurde nur eines.

    Ohne Prozessprofil hat Solidons Datei kein Systemprofil, auf das sie sich
    legen kann (siehe `handover._orca_process`), und der Slicer bricht ab,
    bevor er das Modell ansieht. Gemessen gegen ElegooSlicer 1.5.3.4: mit dem
    Systemprofil darunter läuft derselbe Aufruf durch, ohne es endet er in
    „Der Slicer hat keine Druckdatei geschrieben" — ein Satz über das Ende,
    nicht über die Ursache.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "app" / "ui" / "print_settings_dialog.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    guarded: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        condition = ast.unparse(node.test)
        if "setup.flavour" not in condition:
            continue
        for field in ("machine_profile", "base_process"):
            if f"setup.{field}" in condition:
                guarded.add(field)

    assert guarded == {"machine_profile", "base_process"}, (
        f"nur diese Profile werden vor dem Lauf verlangt: {sorted(guarded)}"
    )


# --- was bleibt, wenn der Dialog zugeht ---------------------------------------------


def test_the_chosen_profiles_are_kept_without_a_slicer_run(qt_app: QApplication) -> None:
    """Was im Dialog stand, gilt auch für den Export (§29, A5).

    Gemerkt wurde die Profilwahl nur beim **Slicen**. Wer sie hier einstellte
    und danach über *Datei → Exportieren* eine 3MF schrieb, bekam die Auswahl
    vom vorletzten Mal — für den Nutzer ist es dieselbe Entscheidung, und der
    Docstring von ``remembered_setup`` verspricht sie.
    """
    settings = UiSettings()
    session = Session()
    dialog = PrintSettingsDialog(session, settings)
    dialog.machine_choice.addItem("Centauri", "C:/profile/machine/centauri.json")
    dialog.machine_choice.setCurrentIndex(dialog.machine_choice.count() - 1)
    dialog.process_choice.addItem("0.20 fein", "C:/profile/process/fein.json")
    dialog.process_choice.setCurrentIndex(dialog.process_choice.count() - 1)
    dialog._filament_profile = "C:/profile/filament/petg-pro.json"

    dialog.reject()

    assert settings.slicer_machine_profile == "C:/profile/machine/centauri.json"
    assert settings.slicer_base_process == "C:/profile/process/fein.json"
    assert settings.slicer_base_filament == "C:/profile/filament/petg-pro.json"
    assert settings.slicer_profile_printer == session.profile.printer.id
    assert (
        settings.slicer_filament_per_material[session.profile.material.id]
        == "C:/profile/filament/petg-pro.json"
    )


def test_closing_early_does_not_wipe_what_was_remembered(qt_app: QApplication) -> None:
    """Die Profilsuche läuft im Hintergrund.

    Wer den Dialog vorher wieder zumacht, hat eine leere Auswahl vor sich —
    sie zu übernehmen hieße, eine gemerkte Einstellung zu löschen, weil
    niemand hingesehen hat.
    """
    settings = UiSettings()
    settings.slicer_machine_profile = "C:/profile/machine/centauri.json"
    settings.slicer_base_process = "C:/profile/process/fein.json"
    dialog = PrintSettingsDialog(Session(), settings)

    dialog.reject()

    assert settings.slicer_machine_profile == "C:/profile/machine/centauri.json"
    assert settings.slicer_base_process == "C:/profile/process/fein.json"


def _pretend_a_slicer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein gefundener Slicer, ohne einen auf der Maschine zu verlangen."""
    from app.ui import print_settings_dialog as module

    monkeypatch.setattr(
        module.discover, "find_program", lambda *args, **kwargs: Path("elegoo-slicer.exe")
    )
    monkeypatch.setattr(
        module.handover,
        "detect",
        lambda found: handover.SlicerSetup(executable=found, flavour="orca"),
    )


def test_a_profile_of_another_printer_is_not_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A6: Ein Maschinenprofil gehört zu genau einem Drucker.

    Ohne diesen Abgleich trägt die 3MF eines Prusa-Projekts das Profil des
    Elegoo, mit dem zuletzt gearbeitet wurde — richtig gerechnet, falsch
    adressiert. Schlimmer als gar keines: Die Datei sieht vollständig aus.
    """
    from app.ui.print_settings_dialog import remembered_setup

    _pretend_a_slicer(monkeypatch)
    settings = UiSettings()
    settings.slicer_machine_profile = "Centauri Carbon 0.4"
    settings.slicer_profile_printer = "centauri-carbon"

    assert remembered_setup(settings, "petg", "prusa-mk4") is None, "anderer Drucker, nichts gilt"

    same = remembered_setup(settings, "petg", "centauri-carbon")
    assert same is not None
    assert same.machine_profile == "Centauri Carbon 0.4", "derselbe Drucker, alles gilt"


@pytest.mark.parametrize("change", ["same", "slicer", "printer", "missing"])
def test_a_profile_refresh_keeps_a_plate_only_in_its_current_context(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """Die laufende Wahl übersteht die erneute Suche, aber keinen fremden Drucker/Slicer."""
    from contextlib import nullcontext

    old = Path("elegoo-slicer.exe")
    current = Path("orca-slicer.exe") if change == "slicer" else old
    if change == "missing":
        current = None
    printer = "generic-220" if change == "printer" else "centauri-carbon-2"
    combo = SimpleNamespace(clear=lambda: None, setEnabled=lambda enabled: None)
    host = SimpleNamespace(
        _bed_plate="Engineering Plate",
        _bed_plate_context=("centauri-carbon-2", old),
        _slicer_path=current,
        session=SimpleNamespace(profile=profiles.make_profile(printer)),
        ui_settings=UiSettings(),
        _show_nozzle=lambda: None,
        _forget_filament_profile=lambda: None,
        machine_choice=combo,
        process_choice=combo,
        slot_rows=[],
        profile_note=SimpleNamespace(setText=lambda text: None),
        _offer_the_slicers_printer=lambda name: None,
    )
    host._refresh_bed_plate_context = lambda: PrintSettingsDialog._refresh_bed_plate_context(host)
    monkeypatch.setattr(print_dialog, "QSignalBlocker", lambda value: nullcontext())

    PrintSettingsDialog._clear_profile_choices(host)

    assert host._bed_plate == ("Engineering Plate" if change == "same" else "")


@pytest.mark.parametrize("saved_printer", ["", "centauri-carbon-2", "generic-220"])
@pytest.mark.parametrize("saved_slicer", ["", "elegoo-slicer.exe", "orca-slicer.exe"])
@pytest.mark.parametrize("available", [False, True])
def test_the_initial_plate_and_export_share_the_same_profile_ownership(
    monkeypatch: pytest.MonkeyPatch, saved_printer: str, saved_slicer: str, available: bool
) -> None:
    """Alte leere Marker gelten weiter; bekannte fremde Marker und fehlende Programme nicht."""
    current = Path("elegoo-slicer.exe") if available else None
    settings = UiSettings()
    settings.slicer_machine_profile = "Ausgewählte Maschine"
    settings.slicer_base_process = "Eigener Prozess"
    settings.slicer_base_filament = "Eigenes Filament"
    settings.slicer_bed_plate = "Engineering Plate"
    settings.slicer_profile_printer = saved_printer
    settings.slicer_profile_slicer = saved_slicer
    host = SimpleNamespace(
        ui_settings=settings,
        _slicer_path=current,
        _bed_plate_context=None,
        _bed_plate="",
        session=SimpleNamespace(profile=profiles.make_profile("centauri-carbon-2")),
    )
    monkeypatch.setattr(print_dialog.discover, "find_program", lambda *args: current)
    monkeypatch.setattr(
        print_dialog.handover, "detect", lambda path: handover.SlicerSetup(path, "orca")
    )

    PrintSettingsDialog._refresh_bed_plate_context(host)
    exported = print_dialog.remembered_setup(settings, "pla", "centauri-carbon-2")

    valid = available and saved_printer != "generic-220" and saved_slicer != "orca-slicer.exe"
    assert host._bed_plate == ("Engineering Plate" if valid else "")
    assert (exported is not None) is valid
    if exported is not None:
        assert exported.plate == host._bed_plate
        assert exported.machine_profile == "Ausgewählte Maschine"
        assert exported.base_process == "Eigener Prozess"
        assert exported.base_filament == "Eigenes Filament"


def test_a_later_slicer_does_not_revive_a_legacy_plate_from_a_missing_program() -> None:
    """Ein zwischenzeitlich fehlendes Programm löscht die bekannte Herkunft nicht."""
    settings = UiSettings()
    settings.slicer_bed_plate = "Engineering Plate"
    host = SimpleNamespace(
        ui_settings=settings,
        _slicer_path=Path("elegoo-slicer.exe"),
        _bed_plate_context=None,
        _bed_plate="",
        session=SimpleNamespace(profile=profiles.make_profile("centauri-carbon-2")),
    )
    PrintSettingsDialog._refresh_bed_plate_context(host)
    assert host._bed_plate == "Engineering Plate"
    host._slicer_path = None
    PrintSettingsDialog._refresh_bed_plate_context(host)
    assert host._bed_plate == ""
    host._slicer_path = Path("orca-slicer.exe")
    PrintSettingsDialog._refresh_bed_plate_context(host)
    assert host._bed_plate == ""


def test_an_old_settings_file_still_carries_its_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne Vermerk wird nicht verglichen.

    Eine Einstellung aus einer älteren Version kennt den Drucker nicht, für
    den sie gewählt wurde. Sie deshalb zu verwerfen wäre eine Verschlechterung
    für jeden, der schon eingerichtet hat.
    """
    from app.ui.print_settings_dialog import remembered_setup

    _pretend_a_slicer(monkeypatch)
    settings = UiSettings()
    settings.slicer_machine_profile = "Centauri Carbon 0.4"

    setup = remembered_setup(settings, "petg", "prusa-mk4")
    assert setup is not None
    assert setup.machine_profile == "Centauri Carbon 0.4"


def test_a_profile_of_another_slicer_is_not_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dieselbe Regel wie beim Drucker, für den Slicer: Ein Maschinenprofil
    aus dem Orca-Bestand ist für PrusaSlicer eine fremde Datei.

    Gemessen am 30.08.2026: Der frühe Rückweg von ``_remember_slicer_choice``
    ließ den Orca-Bestand jeden Wechsel überleben (nach einem Wechsel auf
    Prusa oder Cura sind die Auswahlfelder immer leer), und beim nächsten
    Start bekam PrusaSlicer das Elegoo-Profil aufgelegt.
    """
    from app.ui.print_settings_dialog import remembered_setup

    _pretend_a_slicer(monkeypatch)
    settings = UiSettings()
    settings.slicer_machine_profile = "Centauri Carbon 0.4"
    settings.slicer_profile_slicer = r"C:\anderswo\prusa-slicer.exe"

    assert remembered_setup(settings, "petg") is None, "anderer Slicer, nichts gilt"

    settings.slicer_profile_slicer = "elegoo-slicer.exe"
    same = remembered_setup(settings, "petg")
    assert same is not None, "derselbe Slicer, alles gilt"

    # Ohne Vermerk kein Vergleich — der Zustand jeder Installation, die vor
    # diesem Feld eingerichtet wurde (dieselbe Zusage wie beim Drucker).
    settings.slicer_profile_slicer = ""
    assert remembered_setup(settings, "petg") is not None


def test_remembering_profiles_also_notes_their_slicer(
    monkeypatch: pytest.MonkeyPatch, dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """Wer Profile speichert, speichert wessen sie sind — sonst überlebt der
    Bestand des alten Slicers den Wechsel in den Einstellungen."""
    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    dialog._slicer_path = executable
    dialog.machine_choice.addItem("Elegoo Centauri Carbon 2 0.4 nozzle", "ECC2.json")

    dialog._remember_slicer_choice(require_machine=False)

    assert dialog.ui_settings.slicer_profile_slicer == str(executable)


def test_the_project_settings_win_over_the_preset(qt_app: QApplication) -> None:
    """§29: was eingestellt wurde, gilt beim nächsten Öffnen weiter — sonst
    wäre der Dialog eine Sitzung lang gültig und danach vergessen.

    Eingestellt heißt seit Stufe A des Konzepts Herstellerprofil: mit Herkunft
    (``with_choice``, wie der Dialog es schreibt). Ein Wert ohne Herkunft ist
    Grundlage und folgt dem Profil (``print_settings.on_base``)."""
    session = Session()
    stored = print_settings.with_choice(
        print_settings.resolve(session.profile), "shell.wall_count", 9
    )
    session.project.document.print_settings = stored

    dialog = PrintSettingsDialog(session, UiSettings())

    assert dialog.settings.shell.wall_count == 9


def test_a_project_without_settings_falls_back_to_the_preset(dialog: PrintSettingsDialog) -> None:
    """Kein eigener Satz heißt „noch nichts entschieden", nicht „alles null"."""
    assert dialog.settings.shell.wall_count > 0


def test_the_session_takes_the_settings_and_marks_the_project(qt_app: QApplication) -> None:
    session = Session()
    changed = print_settings.with_path(
        print_settings.resolve(session.profile), "infill.density", 0.42
    )

    session.set_print_settings(changed)

    assert session.project.document.print_settings == changed
    assert session.modified


def test_setting_the_same_values_changes_nothing(qt_app: QApplication) -> None:
    """Den Dialog zu öffnen und ohne Änderung zu schließen darf ein Projekt
    nicht als geändert markieren."""
    session = Session()
    same = print_settings.resolve(session.profile)
    session.set_print_settings(same)
    session._dirty = False

    session.set_print_settings(same)

    assert not session.modified


# --- Vorschläge einzeln wählen ------------------------------------------------------


def test_advice_can_be_taken_one_at_a_time(qt_app: QApplication) -> None:
    """Alles oder nichts hieße: wer einen Vorschlag nicht will, gibt die
    übrigen mit auf."""
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.advice_view.topLevelItemCount() >= 2

    first = dialog.advice_view.topLevelItem(0)
    assert first is not None
    first.setCheckState(0, Qt.CheckState.Unchecked)
    skipped = str(first.data(0, Qt.ItemDataRole.UserRole))
    before = print_settings.read_path(dialog.settings, skipped)

    dialog._apply_advice()

    assert print_settings.read_path(dialog.settings, skipped) == before


def test_every_advice_starts_checked(qt_app: QApplication) -> None:
    """Die Vorschläge sind begründet — sie vorbelegt zu lassen ist die gute
    Vorgabe, nicht die bequeme."""
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())

    for index in range(dialog.advice_view.topLevelItemCount()):
        item = dialog.advice_view.topLevelItem(index)
        assert item is not None and item.checkState(0) == Qt.CheckState.Checked


# --- die Druckdatei -----------------------------------------------------------------


def test_the_save_button_stays_off_until_something_was_sliced(
    dialog: PrintSettingsDialog,
) -> None:
    """Ein Knopf, der eine Datei speichern soll, die es nicht gibt, ist eine
    Sackgasse."""
    assert not dialog.save_button.isEnabled()


def test_slicing_makes_the_file_available(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Ohne diesen Schritt wäre der ganze Lauf eine Zahl auf dem Bildschirm
    und nichts, was auf einen Drucker geht."""
    produced = tmp_path / "plate_1.gcode"
    produced.write_text("; nur ein Test\n", encoding="utf-8")
    outcome = handover.SliceOutcome(gcode_path=produced, metrics=gcode.GcodeMetrics())

    dialog._sliced([outcome])

    assert dialog.save_button.isEnabled()
    assert dialog._gcode == [produced]


def test_saving_gcode_reads_outside_the_qt_thread(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine große Druckdatei hält die Ereignisschleife beim Kopieren nicht an."""
    source = tmp_path / "source.gcode"
    target = tmp_path / "target.gcode"
    source.write_bytes(b"G1 X1\n")
    main_thread = threading.get_ident()
    read_threads: list[int] = []
    original_open = Path.open

    def observed_open(path: Path, *args: object, **kwargs: object):
        if path == source:
            read_threads.append(threading.get_ident())
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", observed_open)
    dialog._start_gcode_save(((source, target),))
    deadline = time.monotonic() + 2.0
    while dialog._worker is not None and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)

    assert target.read_bytes() == b"G1 X1\n"
    assert read_threads and all(thread != main_thread for thread in read_threads)
    assert tr("Gespeichert") in dialog.state.text()


def test_a_completed_gcode_copy_is_not_reported_as_cancelled(
    dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """Nach dem atomaren Ersetzen gewinnt die wahre, bereits sichtbare Wirkung."""
    source = tmp_path / "source.gcode"
    target = tmp_path / "target.gcode"
    source.write_bytes(b"G1 X1\n")

    dialog._start_gcode_save(((source, target),))
    worker = dialog._worker
    assert worker is not None and worker.wait(2_000)

    dialog._cancel_slice()
    QApplication.processEvents()

    assert target.read_bytes() == b"G1 X1\n"
    assert tr("Gespeichert") in dialog.state.text()


def test_a_gcode_write_error_is_shown_as_a_recoverable_error(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein gesperrtes Ziel reißt den Speicherarbeiter nicht aus dem Dialog."""
    from app.core.errors import FileWriteError
    from app.ui import print_settings_dialog as module

    source = tmp_path / "source.gcode"
    source.write_bytes(b"G1 X1\n")
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x", encoding="utf-8")
    shown: list[object] = []
    monkeypatch.setattr(module, "show_error", lambda problem, parent=None: shown.append(problem))

    dialog._start_gcode_save(((source, blocker / "target.gcode"),))
    deadline = time.monotonic() + 2.0
    while dialog._worker is not None and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)

    assert shown and isinstance(shown[0], FileWriteError)
    assert dialog._save_copies, "Erneut versuchen braucht den letzten Auftrag"


def test_a_plate_write_error_does_not_retry_an_old_gcode_copy(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Fehler der 3MF-Vorbereitung gehört nicht zum vorigen Speicherauftrag."""
    from app.core.errors import FileWriteError
    from app.ui import print_settings_dialog as module

    source = tmp_path / "alt.gcode"
    source.write_bytes(b"G1 X1\n")
    dialog._save_copies = ((source, tmp_path / "alt-kopie.gcode"),)
    retried: list[object] = []
    monkeypatch.setattr(dialog, "_start_gcode_save", retried.append)

    def choose_retry(problem: object, parent: object = None) -> None:
        assert parent is dialog
        handler = dialog.error_handlers().get("retry")
        if handler is not None:
            handler(problem)  # type: ignore[arg-type]

    monkeypatch.setattr(module, "show_error", choose_retry)

    dialog._slice_failed(FileWriteError(str(tmp_path / "platte.3mf"), detail="voll"))

    assert retried == []


def test_every_plate_keeps_its_own_print_file(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Zwei Platten sind zwei Druckdateien — und zwei Zahlen, die sich addieren.

    Das ist der Punkt, an dem die Übergabe lange stehen blieb: Sie schrieb die
    erste Platte und sagte das auch, aber wer den Satz übersah, hielt eine halbe
    Druckdatei für die ganze.
    """
    outcomes = []
    for index in (1, 2):
        produced = tmp_path / f"platte-{index}.gcode"
        produced.write_text("; nur ein Test\n", encoding="utf-8")
        outcomes.append(
            handover.SliceOutcome(
                gcode_path=produced,
                metrics=gcode.GcodeMetrics(print_seconds=600.0, filament_grams=10.0),
            )
        )

    dialog._sliced(outcomes)

    assert dialog._gcode == [entry.gcode_path for entry in outcomes]
    # Zwanzig Minuten und zwanzig Gramm, nicht zehn: gedruckt wird zweimal.
    #
    # **Gegen ``facts`` und nicht gegen eine ausgeschriebene Schreibweise.**
    # Hier stand „20,0 g" mit einer Begründung daneben, die das Komma als
    # Sache der Anzeigesprache erklärte — richtig, und trotzdem hat der Test
    # damit die *Stellenzahl* mitgenagelt, die er nicht meinte. Seit der
    # Dialog dieselbe Quelle benutzt wie die Statuszeile, schreibt er „20 g":
    # Über zehn Gramm ist bei einer Schätzung die Nachkommastelle keine
    # Aussage. Die Zusage ist die Zahl, nicht ihre Form.
    from app.ui.facts import duration, mass

    assert duration(2 * 600.0) in dialog.state.text()
    assert mass(2 * 10.0) in dialog.state.text()
    assert "2" in dialog.state.text()


@pytest.mark.parametrize(
    "properties, lengths, expected",
    [
        (((1.2, 2.85),), (1000.0,), 7.655276),
        (((1.2, 2.85), (1.24, 1.75)), (1000.0, 2000.0), 13.620375),
        (((1.2, 2.85), (None, None)), (1000.0, 2000.0), None),
    ],
)
def test_slicer_result_and_inventory_use_the_same_frozen_material_quantities(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch, properties, lengths, expected
) -> None:
    """2,85-mm-Filament und Mischmaterial lesen nach dem Lauf keine neuen Dialogwerte."""
    from app.core.filament_usage import UsageLine, UsageRequest
    from app.ui import print_settings_dialog as module
    from app.ui.facts import mass

    request = UsageRequest(
        "material-snapshot",
        "Probe",
        0,
        tuple(
            UsageLine(
                MaterialSlot(index, f"Filament {index}"),
                None,
                density=density,
                diameter=diameter,
            )
            for index, (density, diameter) in enumerate(properties)
        ),
    )
    produced = tmp_path / "material.gcode"
    produced.write_text("G1 X10 E1\n", encoding="utf-8")
    raw = gcode.GcodeMetrics(filament_mm=sum(lengths), filament_mm_by_tool=lengths)
    outcome = handover.SliceOutcome(produced, raw, findings=gcode.findings_for(raw))
    monkeypatch.setattr(handover, "slice_model", lambda *_args, **_kwargs: outcome)
    worker = module._SliceWorker(
        [module.PlateRun(0, produced, slots=())],
        dialog.settings,
        dialog.session.profile,
        handover.SlicerSetup(tmp_path / "slicer", "orca"),
    )
    worker._usage = {0: request}
    offered = []
    finished = []
    worker.usageReady.connect(offered.append)
    worker.done.connect(finished.append)
    worker.work()
    dialog.settings = replace(
        dialog.settings, filament=replace(dialog.settings.filament, density=9.0, diameter=0.5)
    )
    dialog._sliced(finished[0])
    grams = outcome.metrics.grams(9.0, 0.5)
    if expected is None:
        assert grams is None
        assert tr("Unbekannt") in dialog.state.text()
        assert not any(finding.code == "gcode.material" for finding in outcome.findings)
    else:
        assert grams == pytest.approx(expected)
        assert sum(line.grams for line in offered[0].lines) == pytest.approx(expected)
        assert mass(expected) in dialog.state.text()
        material = next(finding for finding in outcome.findings if finding.code == "gcode.material")
        assert material.values["grams"] == pytest.approx(round(expected, 1))


def test_every_plate_becomes_its_own_run(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Die Übergabe nimmt alle Platten, nicht die erste.

    Der Fund, aus dem das entstand: `_slice` schrieb die Baugruppe von
    `plates[0]`, meldete „geslicet wird die erste" und hörte auf. Der Export
    konnte längst alle. Geprüft wird an der Stelle, die je Platte ihre Datei
    baut — jede trägt nur ihre eigenen Teile und einen eigenen Namen.
    """
    import trimesh

    from app.core.export import handover
    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    def body(size: float, name: str, plate: int) -> SceneObject:
        mesh = trimesh.creation.box(extents=(size, size, size))
        mesh.apply_translation((0.0, 0.0, size / 2.0))
        return SceneObject(id=name, name=name, mesh=MeshData.of(mesh), plate=plate)

    objects = [body(20.0, "A", 0), body(30.0, "B", 1), body(15.0, "C", 1)]
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    runs = [
        dialog._plate_run(objects, plate, tmp_path, "satz", setup)
        for plate in sorted({entry.plate for entry in objects})
    ]

    assert [entry.plate for entry in runs] == [0, 1]
    # Zwei Dateien, nicht eine: sonst schriebe die zweite Platte die erste über.
    assert len({entry.model for entry in runs}) == 2
    assert all(entry.model.is_file() for entry in runs)


def test_the_chosen_slot_profile_reaches_the_run(
    dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """Was die Slot-Zeile einsammelt, steht am Slot des Laufs (§20).

    Der Fund dazu: `slot_profiles` wurde eingesammelt, gemeldet („{slot}
    druckt mit {profil}.") und nie an `write_config` gereicht —
    `MaterialSlot.material` setzte niemand, alle Slots slicten mit dem
    Basisfilament, nur die Farbe stimmte.
    """
    import trimesh

    from app.core.export import handover
    from app.core.geom.mesh import MeshData
    from app.core.types import MaterialSlot, SceneObject

    mesh = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    mesh.apply_translation((0.0, 0.0, 10.0))
    # Beide Slots tragen Flächen: Ein deklarierter Slot ohne Dreieck ist eine
    # alte unbenutzte Spule und geht nicht mehr in die Übergabe (e06d57cef).
    slotted = SceneObject(
        id="A",
        name="A",
        mesh=MeshData(mesh, slots=(0,) * 6 + (1,) * 6),
        material_slots=[
            MaterialSlot(index=0, name="Gehäuse"),
            MaterialSlot(index=1, name="Schrift"),
        ],
    )
    dialog.settings = replace(dialog.settings, slot_profiles=("", "Elegoo PLA"))
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    run = dialog._plate_run([slotted], 0, tmp_path, "satz", setup)

    assert run.slots[0].material is None, "ohne Wahl gilt das Filament der Platte"
    assert run.slots[1].material == "Elegoo PLA"


def test_an_unknown_printer_leaves_the_dialog_responsive(dialog: PrintSettingsDialog) -> None:
    """Ohne passenden Drucker bleibt die Filamentliste leer — und still.

    Der Fund dahinter ist der Normalfall und kein Sonderfall: Solidons Vorgabe
    ist der „Allgemeine FDM-Drucker 220 mm", und dazu hat kein Slicer ein
    Profil. Die Vorbelegungssuche lief trotzdem, schlug ohne Drucker den
    ganzen Filamentbestand auf (5962 Profile statt 42, je eines mit Erbkette
    aus Dateien) und blockierte dabei den Qt-Hauptthread. Wirkungslos war sie
    obendrein: gesucht wurde ein Eintrag in einer Liste, die leer ist.
    """
    dialog._profiles = []

    begonnen = time.perf_counter()
    dialog._fill_filaments(None)

    assert time.perf_counter() - begonnen < 0.5, "ohne Drucker wird nichts aufgeschlagen"
    assert dialog._filament_profile == "", "und nichts steht da, was nicht da ist"
    assert not dialog.adopt_filament.isEnabled(), "ohne Profil ist die Handlung keine"


def test_a_connector_of_infill_reaches_the_advice_list(
    qt_app: QApplication, session: Session
) -> None:
    """Der Vorschlag zum Verbinder steht in der Liste, nicht nur in der Rechnung.

    Gemessen am Querschnitt, so wie man es am geschnittenen Teil nachmisst: Ein
    Zapfen mit Ø 5,04 mm ist bei zwei Wänden à 0,42 mm innen 3,36 mm Füllmuster
    und außen 1,68 mm Material — mehr Muster als Material, und genau dort sitzt
    die Verbindung. Bei drei Wänden (der Vorgabe) hält es sich die Waage, und
    dann sagt Solidon nichts.
    """
    session.import_model(Path(__file__).parent / "data" / "meshes" / "cube_clean.stl")
    assert session.wait_for_idle(60_000)
    result = session.last_result
    assert result is not None, "die Szene steht"

    # Ein Zapfen, wie ihn `split_pinned` erzeugt — die Planung rechnet ihn aus
    # der Schnittfläche, er ist also kein Parameter, den jemand einträgt.
    entry = next(iter(result.scene.objects.values()))
    entry.features["pin_1"] = Feature(
        id="pin_1", kind="pin", provenance="generated", params={"diameter": 5.04}
    )

    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog._connector_diameters() == (5.04,)
    _wait_for_print_advice(dialog, qt_app)

    dialog._editors["shell.wall_count"].setValue(3)
    titel = {
        dialog.advice_view.topLevelItem(row).text(0)
        for row in range(dialog.advice_view.topLevelItemCount())
    }
    assert not any("Wände" in eintrag for eintrag in titel), "bei drei Wänden trägt der Zapfen"

    dialog._editors["shell.wall_count"].setValue(2)
    _wait_for_print_advice(dialog, qt_app)
    zeilen = [
        (
            dialog.advice_view.topLevelItem(row).text(0),
            dialog.advice_view.topLevelItem(row).text(1),
        )
        for row in range(dialog.advice_view.topLevelItemCount())
    ]

    passend = [zeile for zeile in zeilen if "Wände" in zeile[0]]
    assert passend, f"der Vorschlag fehlt in der Liste: {zeilen}"
    assert "2 → 3" in passend[0][1], "und er nennt beide Zahlen"


def test_a_guessed_pin_never_sets_a_setting(qt_app: QApplication, session: Session) -> None:
    """Ein „Zapfen" aus der Merkmalserkennung ist eine Vermutung, keine Vorgabe.

    Gemessen an einem heruntergeladenen Sockel von 160 auf 231 auf 14 mm: Die
    Erkennung fand zehn Zapfen, den dicksten mit Ø 631,6 mm — an einem Teil,
    das an seiner schmalsten Stelle 14 mm misst. Die Wandregel rechnete daraus
    **376 Wände**, und *Vorschläge übernehmen* schrieb sie ins Projekt.
    """
    session.import_model(Path(__file__).parent / "data" / "meshes" / "cube_clean.stl")
    assert session.wait_for_idle(60_000)
    result = session.last_result
    assert result is not None
    entry = next(iter(result.scene.objects.values()))
    entry.features["pin_9"] = Feature(
        id="pin_9", kind="pin", provenance="detected", params={"diameter": 631.582}
    )

    dialog = PrintSettingsDialog(session, UiSettings())

    assert dialog._connector_diameters() == (), "eine Vermutung zählt nicht mit"
    dialog._editors["shell.wall_count"].setValue(2)
    zeilen = [
        (
            dialog.advice_view.topLevelItem(row).text(0),
            dialog.advice_view.topLevelItem(row).text(1),
        )
        for row in range(dialog.advice_view.topLevelItemCount())
    ]
    assert not [zeile for zeile in zeilen if "Wände" in zeile[0]], zeilen

    # Und die Gegenprobe in derselben Szene: ein **erzeugter** Zapfen zählt.
    entry.features["pin_1"] = Feature(
        id="pin_1", kind="pin", provenance="generated", params={"diameter": 5.04}
    )
    zweiter = PrintSettingsDialog(session, UiSettings())

    assert zweiter._connector_diameters() == (5.04,), "der geplante Zapfen schon"


# --- Profilauswahl (§29) ------------------------------------------------------------


def _profile(name: str, kind: str, **kwargs: object) -> SlicerProfile:
    return SlicerProfile(path=Path(f"/x/{name}.json"), name=name, kind=kind, **kwargs)  # type: ignore[arg-type]


def test_the_found_profiles_fill_both_choices(dialog: PrintSettingsDialog) -> None:
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
        default_process="0.20mm Standard",
    )
    found = [
        machine,
        _profile("0.20mm Standard", "process", compatible_printers=(machine.name,)),
        _profile("0.12mm Fein", "process", inherits="0.20mm Standard"),
    ]

    dialog._profiles_found(found)

    assert dialog.machine_choice.count() == 1
    assert dialog.machine_choice.isEnabled()
    assert dialog.process_choice.count() == 2


def test_the_active_slicer_variant_and_nozzle_choice_stay_in_step(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    """Aktive CC2-Düse, Bahnbreite und Maschinenvariante folgen derselben Wahl."""
    from app.core.export import slicer_profiles
    from app.core.knowledge import profiles

    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    monkeypatch.setattr(profiles, "_printers", None)
    session = Session()
    session.start_new("centauri-carbon-2", "pla")
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    # Nur warten, nicht schließen: ``wait_for_workers`` ist der Abbau der Suite
    # und setzt den Dialog auf „wird geschlossen“ — danach verwarf
    # ``_profiles_found`` jede Antwort, und die Düse blieb auf 0,4.
    dialog._leash.wait_all(2000)

    def close_dialog() -> None:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()
        qt_app.processEvents()

    request.addfinalizer(close_dialog)
    dialog._slicer_path = Path("ElegooSlicer.exe")
    dialog._profiles_pending = False
    dialog.machine_choice.setCurrentIndex(-1)
    dialog.ui_settings.slicer_machine_profile = ""
    dialog.ui_settings.slicer_profile_printer = ""
    dialog.ui_settings.slicer_profile_slicer = ""
    found = [
        _profile(
            f"Elegoo Centauri Carbon 2 {diameter:.1f} nozzle",
            "machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=diameter,
        )
        for diameter in (0.2, 0.4, 0.6, 0.8)
    ]
    active = found[2]
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: active.name)
    monkeypatch.setattr(
        slicer_profiles,
        "chosen_printer",
        lambda *_args, **_kwargs: dialog.session.profile.printer.id,
    )
    monkeypatch.setattr(dialog, "_machines_worth_showing", lambda machines: machines)

    dialog._profiles_found(found)

    assert tuple(
        dialog.nozzle_choice.itemData(index) for index in range(dialog.nozzle_choice.count() - 1)
    ) == (0.2, 0.4, 0.6, 0.8)
    assert dialog.nozzle_choice.currentData() == pytest.approx(0.6)
    printer = profiles.printer("centauri-carbon-2")
    assert printer.nozzle_diameter == pytest.approx(0.6)
    assert printer.extrusion_width == pytest.approx(0.63)
    assert dialog.machine_choice.currentData() == slicer_profiles.identity(active)

    chosen = dialog.nozzle_choice.findData(0.2)
    assert chosen >= 0
    dialog.nozzle_choice.setCurrentIndex(chosen)
    dialog.nozzle_choice.activated.emit(chosen)

    printer = profiles.printer("centauri-carbon-2")
    assert printer.nozzle_diameter == pytest.approx(0.2)
    assert printer.extrusion_width == pytest.approx(0.21)
    assert dialog.machine_choice.currentData() == slicer_profiles.identity(found[0])


def test_profile_search_preserves_a_pending_custom_nozzle_draft(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    """Eine passive Profilantwort ersetzt den noch nicht bestätigten eigenen Wert nicht."""
    from PySide6.QtTest import QTest

    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    monkeypatch.setattr(profiles, "_printers", None)
    session = Session()
    session.start_new("centauri-carbon-2", "pla")
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.wait_for_slicers()
    # Warten, nicht schließen (siehe ``test_the_active_slicer_variant_…``).
    dialog._leash.wait_all(2000)

    def close_dialog() -> None:
        dialog.reject()
        dialog.wait_for_workers()
        dialog.deleteLater()
        qt_app.processEvents()

    request.addfinalizer(close_dialog)
    dialog._slicer_path = Path("OrcaSlicer.exe")
    dialog._profiles_pending = False
    dialog.machine_choice.setCurrentIndex(-1)
    other = dialog.nozzle_choice.count() - 1
    dialog.nozzle_choice.setCurrentIndex(other)
    dialog.nozzle_choice.activated.emit(other)
    line = dialog.nozzle.lineEdit()
    line.setFocus()
    line.selectAll()
    QTest.keyClicks(line, dialog.nozzle.locale().toString(0.55, "f", dialog.nozzle.decimals()))
    line.setCursorPosition(2)
    expected = (line.text(), line.isModified(), line.cursorPosition())
    found = [
        _profile(
            f"Elegoo Centauri Carbon 2 {diameter:.1f} nozzle",
            "machine",
            printer_model="Elegoo Centauri Carbon 2",
            vendor="Elegoo",
            nozzle=diameter,
        )
        for diameter in (0.4, 0.6)
    ]
    monkeypatch.setattr(dialog, "_slicer_machine_for_project", lambda _found: (found[1], True))
    monkeypatch.setattr(dialog, "_machines_worth_showing", lambda machines: machines)

    dialog._profiles_found(found)

    assert dialog.nozzle_choice.currentData() is None
    assert dialog.nozzle.isVisibleTo(dialog)
    assert (line.text(), line.isModified(), line.cursorPosition()) == expected


def test_changing_printers_clears_the_previous_nozzle_success_message(
    dialog: PrintSettingsDialog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Status zur alten Maschine bleibt nach dem Druckerwechsel nicht stehen."""
    generic = tr("Die Auswahl bestimmt Bahnbreite und Slicer-Maschinenprofil.")
    dialog.nozzle_state.setText(
        tr("Düse {value} gewählt; Bahnbreite und Maschinenprofil sind angepasst.").replace(
            "{value}", dialog.nozzle.text()
        )
    )
    monkeypatch.setattr(dialog, "_refill_slicer_profiles", lambda: None)
    index = dialog.printer_choice.findData("centauri-carbon-2")
    assert index >= 0

    dialog.printer_choice.setCurrentIndex(index)

    assert dialog.nozzle_state.text() == generic


def test_imported_printer_identity_limits_nozzle_choices_to_its_model_and_vendor(
    dialog: PrintSettingsDialog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein importierter Slicer-Drucker erkennt Geschwister, aber keinen fremden Hersteller."""
    from app.core.export import slicer_profiles

    source = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        vendor="Elegoo",
        nozzle=0.4,
    )
    foreign = _profile(
        "Other Centauri Carbon 2 0.6 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        vendor="Other",
        nozzle=0.6,
    )
    active = _profile(
        "Elegoo Centauri Carbon 2 0.6 nozzle",
        "machine",
        printer_model="elegoo centauri carbon 2",
        vendor="ELEGOO",
        nozzle=0.6,
    )
    found = [source, foreign, active]
    # ``Session.profile`` ist abgeleitet (aus Dokument und Druckeinstellungen)
    # und hat keinen Setter; die Attrappe steht deshalb an der Klasse.
    imported = replace(
        dialog.session.profile,
        printer=slicer_profiles._discovered_printer(
            source,
            "orca",
            {
                "printer_technology": "FFF",
                "printable_area": ["0x0", "256x0", "256x256", "0x256"],
                "printable_height": "256",
                "nozzle_diameter": ["0.4"],
            },
            {},
            "OrcaSlicer",
        ),
    )
    monkeypatch.setattr(type(dialog.session), "profile", property(lambda _self: imported))
    dialog._slicer_path = Path("OrcaSlicer.exe")
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args, **_kwargs: active.name)

    machine, belongs = dialog._slicer_machine_for_project(found)

    assert machine is active
    assert belongs
    assert dialog._machines_worth_showing(slicer_profiles.machines(found)) == [source, active]


def test_refitting_fdm_controls_keeps_a_standard_nozzle_editor_closed(
    dialog: PrintSettingsDialog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Das erneute Anzeigen der FDM-Felder öffnet „Andere …“ nicht mit."""
    standard = dialog.nozzle_choice.findData(0.6)
    assert standard >= 0
    monkeypatch.setattr(dialog, "_nozzle_changed", lambda _value: True)

    dialog.nozzle_choice.setCurrentIndex(standard)
    dialog.nozzle_choice.activated.emit(standard)
    assert dialog.nozzle.isHidden()

    dialog._fit_to_technology()

    assert dialog.nozzle.isHidden()


_PRUSA_BUNDLE = """[vendor]
name = Prusa Research

[printer_model:MK4S]
name = Original Prusa MK4S
variants = HF0.4; 0.4
default_materials = Prusament PLA @MK4S HF0.4

[printer:*common*]
printer_technology = FFF
nozzle_diameter = 0.4

[printer:Original Prusa MK4S HF0.4 nozzle]
inherits = *common*
printer_model = MK4S
nozzle_high_flow = 1
default_print_profile = 0.20mm SPEED @MK4S HF0.4

[printer:Original Prusa MK4S 0.4 nozzle]
inherits = *common*
printer_model = MK4S
nozzle_high_flow = 0
default_print_profile = 0.20mm SPEED @MK4S 0.4

[print:0.20mm SPEED @MK4S HF0.4]
layer_height = 0.2
compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]

[print:0.20mm SPEED @MK4S 0.4]
layer_height = 0.2
compatible_printers_condition = printer_model=="MK4S" and ! nozzle_high_flow[0]

[filament:Prusament PLA @MK4S HF0.4]
filament_type = PLA
compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]
"""


def test_prusa_gets_the_profile_choice_and_its_sections_are_told_apart(
    dialog: PrintSettingsDialog, session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stufe C des Konzepts Herstellerprofil: PrusaSlicer bekommt dieselbe
    Profilwahl wie die Orca-Familie, vorgewählt wie PrusaSlicer selbst wählt.

    Alle Profile eines Bündels teilen eine Datei. Am Pfad erkannt, war jeder
    Eintrag derselbe, und die Auswahl zeigte den gewählten Drucker über dem
    ersten Abschnitt der Datei (``slicer_profiles.identity``). Verlangt wird
    keine Wahl: Ohne Drucker des Bündels gehen Solidons Werte hinaus.
    """
    from app.core.export import slicer_profiles as sp

    executable = tmp_path / "PrusaSlicer" / "prusa-slicer-console.exe"
    root = executable.parent / "resources" / "profiles"
    root.mkdir(parents=True)
    (root / "PrusaResearch.ini").write_text(_PRUSA_BUNDLE, encoding="utf-8")
    executable.write_bytes(b"")
    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    _select_printer(dialog, "prusa-mk4s")
    assert session.wait_for_idle()
    dialog._slicer_path = executable

    dialog._profiles_found(
        sp.find_profiles(executable, "prusa", kinds=("machine", "process", "filament"))
    )

    assert dialog.machine_choice.currentData() == "Original Prusa MK4S HF0.4 nozzle"
    assert dialog.process_choice.currentData() == "0.20mm SPEED @MK4S HF0.4"
    assert dialog.process_choice.count() == 1, "der Prozess der Standarddüse passt nicht"
    setup = dialog._current_setup()
    assert setup is not None
    assert setup.base_filament == "Prusament PLA @MK4S HF0.4"
    assert dialog._profile_gap() == ""

    dialog.machine_choice.setCurrentIndex(-1)
    assert dialog._profile_gap() == "", "ohne Drucker gilt Solidons Satz"


_PRUSA_STAGES = (
    _PRUSA_BUNDLE
    + """
[print:0.10mm FAST DETAIL @MK4S HF0.4]
layer_height = 0.1
compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]

[print:0.15mm SPEED @MK4S HF0.4]
layer_height = 0.15
compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]

[print:0.20mm STRUCTURAL @MK4S HF0.4]
layer_height = 0.2
compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]

[print:0.28mm DRAFT @MK4S HF0.4]
layer_height = 0.28
compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]
"""
)


def test_the_quality_picks_the_manufacturers_process(
    dialog: PrintSettingsDialog, session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stufe F (Entscheidung I): Die Qualität stellt das Prozessfeld auf den
    Prozess des Herstellers, eine Wahl im Prozessfeld stellt die Qualität, und
    ein Prozess, der zu keiner gehört, heißt dort „Eigener Prozess". Hin und
    zurück bleibt es verlustfrei; gemerkt wird der Standard, solange das Feld
    der Qualität folgt — die Qualität gehört zum Projekt."""
    from app.core.export import slicer_profiles as sp
    from app.ui.print_settings_dialog import _OWN_PROCESS

    executable = tmp_path / "PrusaSlicer" / "prusa-slicer-console.exe"
    root = executable.parent / "resources" / "profiles"
    root.mkdir(parents=True)
    (root / "PrusaResearch.ini").write_text(_PRUSA_STAGES, encoding="utf-8")
    executable.write_bytes(b"")
    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    _select_printer(dialog, "prusa-mk4s")
    assert session.wait_for_idle()
    dialog._slicer_path = executable
    dialog._profiles_found(
        sp.find_profiles(executable, "prusa", kinds=("machine", "process", "filament"))
    )
    assert dialog.process_choice.currentData() == "0.20mm SPEED @MK4S HF0.4"

    def choose_quality(key: str) -> None:
        dialog.quality.setCurrentIndex(dialog.quality.findData(key))

    def pick_process(name: str) -> None:
        index = dialog.process_choice.findData(name)
        dialog.process_choice.setCurrentIndex(index)
        dialog.process_choice.activated.emit(index)

    choose_quality("fine")
    assert dialog.process_choice.currentData() == "0.10mm FAST DETAIL @MK4S HF0.4"
    assert dialog.settings.layers.layer_height == pytest.approx(0.1)
    choose_quality("strong")
    assert dialog.process_choice.currentData() == "0.20mm STRUCTURAL @MK4S HF0.4"
    choose_quality("fine")
    assert dialog.process_choice.currentData() == "0.10mm FAST DETAIL @MK4S HF0.4"

    pick_process("0.28mm DRAFT @MK4S HF0.4")
    assert dialog.quality.currentData() == dialog.settings.quality == "draft"

    pick_process("0.15mm SPEED @MK4S HF0.4")
    assert dialog.quality.currentData() == _OWN_PROCESS
    dialog._remember_slicer_choice(require_machine=False)
    assert dialog.ui_settings.slicer_base_process == "0.15mm SPEED @MK4S HF0.4"

    choose_quality("standard")
    assert dialog.process_choice.currentData() == "0.20mm SPEED @MK4S HF0.4"
    assert dialog.quality.findData(_OWN_PROCESS) < 0
    choose_quality("fine")
    dialog._remember_slicer_choice(require_machine=False)
    assert dialog.ui_settings.slicer_base_process == "0.20mm SPEED @MK4S HF0.4", (
        "gemerkt wird der Standard, die Qualität wählt"
    )


def test_switching_the_slicer_empties_the_profile_choice(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Wer zwei Slicer hat, wechselt — und die Auswahl darf nicht stehenbleiben.

    Gemessen: Mit gefüllter Orca-Auswahl und danach eingestelltem CuraEngine
    ging ein ``-j`` auf eine Orca-Datei hinaus, und der Slicer war nach einer
    Zehntelsekunde tot. ``_start_profile_search`` kehrt für ``cura`` früh
    zurück; geleert wird deshalb am Anfang, nicht am Ende.

    Und die gemerkte Wahl bleibt: das Leere zu merken löschte das Profil, das
    zum nächsten Orca-Lauf gehört.
    """
    from app.core import discover

    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
        default_process="0.20mm Standard",
    )
    dialog._profiles_found([machine, _profile("0.20mm Standard", "process")])
    assert dialog.machine_choice.count() == 1, "so weit ist es der Orca-Fall"
    dialog.ui_settings.slicer_machine_profile = str(machine.path)

    engine = tmp_path / "CuraEngine.exe"
    engine.write_text("")
    # `recheck_slicer` fragt die **Mehrzahl** — seit der Slicer-Auswahl geht
    # jeder Weg zum Slicer über `_pick_slicer`. Ein Patch auf `find_program`
    # ging hier ins Leere und war nur deshalb grün, weil die ungepatchte Suche
    # auf dieser Maschine ohne Profilbestand endete (30.08.2026).
    monkeypatch.setattr(discover, "find_programs", lambda *_args, **_kwargs: (engine,))

    dialog.recheck_slicer()
    # Seit dem 13.09.2026 sucht auch dieser Weg im Arbeiter (§2.8): Der Aufruf
    # kehrt sofort zurück, der Fund kommt nach.
    assert dialog.wait_for_slicers(), "die zweite Suche kam nicht zurück"

    assert dialog.machine_choice.count() == 0, "kein Orca-Profil für CuraEngine"
    assert not dialog.machine_choice.isEnabled()
    assert dialog.process_choice.count() == 0
    assert dialog._filament_profile == ""
    assert dialog._profiles == []

    # Und die zweite Zusicherung: was nicht gewählt werden kann, wird nicht
    # gemerkt — sonst stünde beim nächsten Orca-Lauf nichts mehr da.
    dialog._remember_slicer_choice(require_machine=False)

    assert dialog.ui_settings.slicer_machine_profile == str(machine.path)


def test_the_matching_profile_is_preselected(qt_app: QApplication) -> None:
    """§2.4: eine gute Vorgabe ist mehr wert als eine gute
    Einstellmöglichkeit. Das Maschinenprofil nennt seinen Drucker und sein
    Standard-Prozessprofil selbst — es gibt nichts zu erfragen."""
    session = Session()
    session.project.document.printer = "centauri-carbon-2"
    dialog = PrintSettingsDialog(session, UiSettings())
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
        default_process="0.20mm Standard",
    )
    other = _profile(
        "Ganz anderes Gerät", "machine", printer_model="Ganz anderes Gerät", nozzle=0.4
    )

    dialog._profiles_found(
        [
            other,
            machine,
            _profile("0.12mm Fein", "process", compatible_printers=(machine.name,)),
            _profile("0.20mm Standard", "process", compatible_printers=(machine.name,)),
        ]
    )

    assert dialog.machine_choice.currentData() == str(machine.path)
    assert dialog.process_choice.currentText().startswith("0.20mm Standard")


def test_processes_of_other_printers_stay_out(dialog: PrintSettingsDialog) -> None:
    """Ungefiltert stünden hier zweitausend Einträge, von denen einer stimmt —
    und der Slicer lehnte jeden anderen ab, ohne zu sagen warum."""
    machine = _profile("Meiner 0.4 nozzle", "machine", printer_model="Meiner", nozzle=0.4)
    dialog._profiles_found(
        [
            machine,
            _profile("Passt", "process", compatible_printers=(machine.name,)),
            _profile("Passt nicht", "process", compatible_printers=("Ein anderer",)),
        ]
    )

    shown = [
        dialog.process_choice.itemText(index) for index in range(dialog.process_choice.count())
    ]
    assert shown == ["Passt"]


def test_an_own_profile_is_marked_in_words(dialog: PrintSettingsDialog) -> None:
    machine = _profile("Meiner 0.4 nozzle", "machine", printer_model="Meiner", nozzle=0.4)
    dialog._profiles_found([machine, _profile("Meine Version", "process", from_user=True)])

    assert "(" in dialog.process_choice.itemText(0)


def test_no_profiles_found_says_what_that_means(dialog: PrintSettingsDialog) -> None:
    dialog._profiles_found([])

    assert dialog.profile_note.text()
    assert not dialog.machine_choice.isEnabled()


#: Der Slicer, aus dem die Profile der Merkfälle stammen — ein anderer als der
#: vermerkte ``C:/Anderswo/OrcaSlicer.exe``.
_FOUND_SLICER = Path("C:/Programme/ElegooSlicer/elegoo-slicer.exe")


def test_a_remembered_choice_wins_over_the_match(qt_app: QApplication) -> None:
    """Wer einmal abgewichen ist, meinte es so."""
    session = Session()
    session.project.document.printer = "centauri-carbon-2"
    settings = UiSettings()
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
    )
    other = _profile("Etwas anderes", "machine", printer_model="Etwas anderes", nozzle=0.4)
    settings.slicer_machine_profile = str(other.path)
    dialog = PrintSettingsDialog(session, settings)
    # Profile kommen nur aus einem gefundenen Slicer; ohne Programm gilt keine
    # gemerkte Wahl (RM-289 B11, ``_remembered_profiles_match``).
    dialog._slicer_path = _FOUND_SLICER

    dialog._profiles_found([machine, other])

    assert dialog.machine_choice.currentData() == str(other.path)


def test_a_remembered_machine_waits_for_its_slicer(qt_app: QApplication) -> None:
    """Ohne gefundenes Programm gilt die gemerkte Maschine nicht — der
    Bestand, aus dem sie stammt, ist nicht da (RM-289 B11)."""
    session = Session()
    session.project.document.printer = "centauri-carbon-2"
    settings = UiSettings()
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
    )
    other = _profile("Etwas anderes", "machine", printer_model="Etwas anderes", nozzle=0.4)
    settings.slicer_machine_profile = str(other.path)
    dialog = PrintSettingsDialog(session, settings)
    try:
        dialog._slicer_path = None
        dialog._profiles_found([machine, other])

        assert dialog.machine_choice.currentData() == str(machine.path)
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize(
    ("printer", "slicer", "wins"),
    [
        ("centauri-carbon-2", "", "gemerkt"),
        ("", "", "gemerkt"),
        ("generic-220", "", "passend"),
        ("centauri-carbon-2", "C:/Anderswo/OrcaSlicer.exe", "passend"),
    ],
)
def test_a_remembered_machine_belongs_to_its_printer_and_slicer(
    qt_app: QApplication, printer: str, slicer: str, wins: str
) -> None:
    """Die gemerkte Maschine gilt nur für Drucker und Slicer, für die sie
    gewählt wurde — dieselbe Regel wie beim Export (``remembered_setup``).
    Ohne sie trug ein Projekt auf dem allgemeinen Drucker das Maschinenprofil
    des Centauri Carbon 2: Der Slicer rechnete mit 256 mm Bett, Solidon mit 220."""
    session = Session()
    session.project.document.printer = "centauri-carbon-2"
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
    )
    other = _profile("Etwas anderes", "machine", printer_model="Etwas anderes", nozzle=0.4)
    settings = UiSettings()
    settings.slicer_machine_profile = str(other.path)
    settings.slicer_profile_printer = printer
    settings.slicer_profile_slicer = slicer
    dialog = PrintSettingsDialog(session, settings)
    try:
        dialog._slicer_path = _FOUND_SLICER
        dialog._profiles_found([machine, other])

        expected = other if wins == "gemerkt" else machine
        assert dialog.machine_choice.currentData() == str(expected.path)
    finally:
        dialog.deleteLater()


def test_the_printer_the_slicer_is_set_to_can_be_adopted(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Passt zum Drucker des Projekts kein Profil, der Slicer steht aber auf
    einem Drucker, den Solidon kennt, bietet der Dialog genau diesen an —
    und merkt ihn für das nächste Projekt (Robert, 27.09.2026: allgemeiner
    Drucker im Projekt, der ElegooSlicer auf dem Centauri Carbon 2)."""
    monkeypatch.setattr(
        "app.core.export.slicer_profiles.chosen_machine",
        lambda _flavour, _executable: "Elegoo Centauri Carbon 2 0.4 nozzle",
    )
    session = Session()
    session.project.document.printer = "generic-220"
    settings = UiSettings()
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
    )
    dialog = PrintSettingsDialog(session, settings)
    try:
        dialog._slicer_path = Path("ElegooSlicer.exe")
        dialog._profiles_found([machine])

        assert dialog.machine_choice.currentIndex() == 0, "der einzige Eintrag ist die Wahl"
        # Der Knopf selbst; der Abschnitt darum zeigt sich erst mit einem
        # gefundenen Slicer, und den gibt es hier nicht.
        assert not dialog.adopt_printer.isHidden()
        title = str(profiles.printer("centauri-carbon-2").title)
        assert dialog.adopt_printer.text() == f"{title} übernehmen"
        assert "ElegooSlicer" in dialog.adopt_printer.toolTip()
        assert dialog.adopt_printer.accessibleDescription() == dialog.adopt_printer.toolTip()

        dialog.adopt_printer.click()

        assert dialog.printer_choice.currentData() == "centauri-carbon-2"
        assert session.profile.printer.id == "centauri-carbon-2"
        assert settings.printer == "centauri-carbon-2", "das nächste Projekt beginnt damit"
        assert dialog.adopt_printer.isHidden(), "jetzt passt das Profil"
    finally:
        dialog.deleteLater()


def test_curas_active_printer_can_be_adopted_without_losing_print_choices(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    from app.core.export import slicer_profiles
    from app.core.knowledge import print_settings
    from app.core.types import PrinterProfile

    original_profiles_dir = profiles.user_profiles_dir

    def restore_profile_cache() -> None:
        profiles.user_profiles_dir = original_profiles_dir
        profiles.reload()

    request.addfinalizer(restore_profile_cache)
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path / "user-profiles")
    profiles.reload()

    candidate = PrinterProfile(
        id="slicer-cura-active-instance",
        title="Ender-3 V3 SE",
        build_volume=(220.0, 200.0, 250.0),
        cura_definition="creality_ender3v3se",
    )
    active = slicer_profiles.SlicerProfile(
        path=tmp_path / "creality_ender3v3se.def.json",
        name=candidate.title,
        kind="machine",
        printer_model=candidate.cura_definition,
        printer_id=candidate.id,
        cura_instance=tmp_path / "machine_instances" / "active.global.cfg",
    )

    monkeypatch.setattr(
        slicer_profiles,
        "chosen_printer",
        lambda _flavour, _executable, _known, **_kwargs: "",
    )
    monkeypatch.setattr(
        slicer_profiles, "chosen_machine", lambda _flavour, _executable: "cura-instance:active"
    )
    monkeypatch.setattr(slicer_profiles, "profile_by_name", lambda *_args: active)
    monkeypatch.setattr(slicer_profiles, "discover_printers", lambda *_args: (candidate,))
    session = Session()
    session.change_scene_profile("generic-220", "petg")
    assert session.wait_for_idle()
    settings = UiSettings()
    dialog = PrintSettingsDialog(session, settings)
    own_temperature = replace(dialog.settings.temperature, nozzle=210)
    override = SlotOverride(
        name="PLA Weiß",
        colour=(1.0, 1.0, 1.0),
        temperature=own_temperature,
    )
    dialog.settings = replace(
        dialog.settings,
        slot_profiles=("Haus PETG", "Haus PLA weiß"),
        slot_overrides=(override,),
    )
    dialog.settings = print_settings.with_choice(dialog.settings, "infill.density", 0.62)
    try:
        # Erst die Slicersuche abwarten: Ihre späte Antwort startet die
        # Profilsuche neu und leerte den Kandidaten (RM-417, ``dialog``-Fixture).
        assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
        dialog._slicer_path = Path("Cura.exe")
        dialog._start_profile_search()
        assert dialog.wait_for_cura_printer()

        assert candidate.id not in profiles.printer_profiles(), "der Suchlauf speichert nichts"
        assert dialog._cura_printer_candidate == candidate
        assert not dialog.adopt_printer.isHidden()
        title = str(candidate.title)
        assert dialog.adopt_printer.text() == f"{title} übernehmen"
        assert dialog.adopt_printer.accessibleDescription() == dialog.adopt_printer.toolTip()

        from app.core import discover

        # Jede Ablage zählt, nicht nur der Stand danach: Die Wahl, die der
        # Übernahme folgt, schreibt die Marke ein zweites Mal und verdeckte eine
        # erste Ablage ohne sie (Review P2 N10).
        saves: list[tuple[str, str | None]] = []
        save = profiles.save_printer

        def recorded(profile: PrinterProfile, *, slicer: str | None = None) -> PrinterProfile:
            saves.append((profile.id, slicer))
            return save(profile, slicer=slicer)

        monkeypatch.setattr(profiles, "save_printer", recorded)
        dialog.adopt_printer.click()

        assert candidate.id in profiles.printer_profiles(), "erst der Klick speichert das Profil"
        assert profiles.printer(candidate.id) == candidate
        mark = discover.program_mark("Cura.exe")
        assert mark, "sonst prüft die Marke nichts"
        assert profiles.printer_slicer(candidate.id) == mark
        mine = [slicer for identifier, slicer in saves if identifier == candidate.id]
        assert mine and mine[0] == mark, f"die Übernahme legt ohne Marke ab: {mine}"
        assert session.profile.printer.id == candidate.id
        assert settings.printer == candidate.id
        assert session.project.document.material == "petg"
        assert dialog.settings.infill.density == pytest.approx(0.62)
        assert dialog.settings.slot_profiles == ("Haus PETG", "Haus PLA weiß")
        assert dialog.settings.slot_overrides == (override,)
        assert dialog.nozzle.value_mm() == pytest.approx(candidate.nozzle_diameter)
        assert dialog.adopt_printer.isHidden()
    finally:
        assert session.wait_for_idle(60_000)
        dialog.deleteLater()


def test_the_print_dialog_offers_the_printers_of_its_slicer(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Erst der Slicer, dann seine Drucker — auch hier (Entscheidung Robert,
    06.10.2026), dieselbe Liste wie im Erststart und in den Einstellungen.

    Ein Kunde mit Anycubic Slicer Next fand hier nur den Kobra S1 Max aus dem
    Erststart und den Kobra 2 aus Solidons Tabelle, nicht seinen Kobra S1. Die
    Erhebung speichert nichts; erst die Wahl legt den Drucker ab, und das
    Projekt rechnet mit ihm.
    """
    from app.core import discover
    from app.core.export import slicer_profiles
    from app.core.types import PrinterProfile

    original_profiles_dir = profiles.user_profiles_dir

    def restore_profile_cache() -> None:
        profiles.user_profiles_dir = original_profiles_dir
        profiles.reload()

    request.addfinalizer(restore_profile_cache)
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path / "profiles")
    profiles.reload()
    kobra = PrinterProfile(
        id="slicer-kobra-s1",
        title="Anycubic Kobra S1 0.4 nozzle",
        build_volume=(250.0, 250.0, 250.0),
        vendor="Anycubic",
    )
    monkeypatch.setattr(slicer_profiles, "discover_printers", lambda *_args: (kobra,))
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: "")
    executable = tmp_path / "AnycubicSlicerNext" / "AnycubicSlicerNext.exe"
    executable.parent.mkdir()
    executable.write_text("", encoding="utf-8")
    discover.remember_path("slicer", str(executable))
    session = Session()
    settings = UiSettings()
    dialog = PrintSettingsDialog(session, settings)
    try:
        assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
        assert dialog.wait_for_printer_survey(), "die Drucker des Slicers kamen nicht"
        index = dialog.printer_choice.findData(kobra.id)
        assert index >= 0, "der Drucker des Slicers steht zur Wahl"
        assert dialog.printer_choice.itemText(index) == "Anycubic Kobra S1"
        assert dialog.printer_choice.findData("centauri-carbon-2") < 0, (
            "ein Tabellendrucker, den der Slicer nicht nennt, steht nicht da"
        )
        assert dialog.printer_choice.currentData() == session.profile.printer.id
        assert kobra.id not in profiles.printer_profiles(), "die Erhebung speichert nichts"

        dialog.printer_choice.setCurrentIndex(index)
        dialog.printer_choice.activated.emit(index)

        assert kobra.id in profiles.user_printer_profiles(), "erst die Wahl speichert ihn"
        assert session.profile.printer.id == kobra.id
        assert settings.printer == kobra.id
        assert dialog.printer_choice.currentData() == kobra.id
    finally:
        assert session.wait_for_idle(60_000)
        dialog.release()
        dialog.deleteLater()
        discover.remember_path("slicer", "")


def test_the_print_dialog_says_whose_printers_it_lists_and_what_went_wrong(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Die Druckerliste folgt dem Slicer darüber: Kurzhilfe und Suchzeile nennen
    ihn. Scheitert das Ablegen des gewählten Druckers, springt die Wahl zurück,
    die Vorgabe für neue Projekte bleibt, und der Grund steht unter dem Drucker
    — in der Zustandszeile überschrieb ihn der nächste Sperrgrund (Regel 17).
    Eine gescheiterte Erhebung zeigt alle Drucker und sagt es; vorher still.
    """
    from app.core import discover
    from app.core.errors import FileWriteError
    from app.core.export import slicer_profiles
    from app.core.types import PrinterProfile

    original_profiles_dir = profiles.user_profiles_dir

    def restore_profile_cache() -> None:
        profiles.user_profiles_dir = original_profiles_dir
        profiles.reload()

    request.addfinalizer(restore_profile_cache)
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path / "profiles")
    profiles.reload()
    kobra = PrinterProfile(
        id="slicer-kobra-s1",
        title="Anycubic Kobra S1 0.4 nozzle",
        build_volume=(250.0, 250.0, 250.0),
        vendor="Anycubic",
    )
    monkeypatch.setattr(slicer_profiles, "discover_printers", lambda *_args: (kobra,))
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: "")
    executable = tmp_path / "AnycubicSlicerNext" / "AnycubicSlicerNext.exe"
    executable.parent.mkdir()
    executable.write_text("", encoding="utf-8")
    discover.remember_path("slicer", str(executable))
    session = Session()
    settings = UiSettings()
    dialog = PrintSettingsDialog(session, settings)
    try:
        assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
        assert dialog.wait_for_printer_survey(), "die Drucker des Slicers kamen nicht"
        tip = (
            "Mit diesem Drucker rechnet das Projekt. Zur Wahl stehen die Drucker aus "
            "Anycubic Slicer Next und Ihre eigenen."
        )
        assert dialog.printer_choice.toolTip() == tip
        assert dialog.printer_choice.accessibleDescription() == tip
        assert dialog.printer_label.toolTip() == tip
        assert dialog.printer_choice.search_field.placeholderText() == (
            "Drucker aus Anycubic Slicer Next suchen …"
        )
        assert dialog.printer_state.isHidden(), "ohne Grund keine Zeile"

        before = session.profile.printer.id
        default = settings.printer

        def full_disk(_profile: PrinterProfile, **_values: object) -> PrinterProfile:
            raise FileWriteError(detail="kein Platz")

        monkeypatch.setattr(profiles, "save_printer", full_disk)
        index = dialog.printer_choice.findData(kobra.id)
        dialog.printer_choice.setCurrentIndex(index)
        dialog.printer_choice.activated.emit(index)

        assert session.profile.printer.id == before
        assert dialog.printer_choice.currentData() == before, "die Wahl springt zurück"
        assert settings.printer == default, "der nicht abgelegte Drucker wird keine Vorgabe"
        assert not dialog.printer_state.isHidden()
        assert dialog.printer_state.text() == (
            "Der Drucker ließ sich nicht speichern. Prüfen Sie den freien Speicherplatz "
            "und die Schreibrechte, und wählen Sie ihn erneut."
        )
        dialog._show_slicer_state()
        assert "wählen Sie ihn erneut" in dialog.printer_state.text(), (
            "die Zustandszeile überschreibt den Grund nicht"
        )

        def unreadable(*_args: object) -> tuple[PrinterProfile, ...]:
            raise RuntimeError("Bestand kaputt")

        monkeypatch.setattr(slicer_profiles, "discover_printers", unreadable)
        dialog._start_printer_survey()
        assert dialog.wait_for_printer_survey(), "die gescheiterte Erhebung kam nicht zurück"

        assert dialog.printer_choice.findData("centauri-carbon-2") >= 0, "alle bekannten"
        assert dialog.printer_state.text() == (
            "Die Drucker von Anycubic Slicer Next ließen sich nicht lesen. Wählen Sie Ihren "
            "aus allen bekannten Druckern oder einen anderen Slicer."
        )
        assert dialog.printer_choice.search_field.placeholderText() == "Drucker suchen …"
    finally:
        assert session.wait_for_idle(60_000)
        dialog.release()
        dialog.deleteLater()
        discover.remember_path("slicer", "")


def test_only_a_picked_printer_becomes_the_next_projects_printer(
    qt_app: QApplication,
) -> None:
    """Die Wahl im Feld zählt, das Befüllen beim Öffnen nicht: Ein Projekt,
    das einen anderen Drucker mitbringt, ändert die Vorgabe nicht."""
    session = Session()
    session.project.document.printer = "centauri-carbon-2"
    settings = UiSettings()
    settings.printer = "generic-220"
    dialog = PrintSettingsDialog(session, settings)
    try:
        assert settings.printer == "generic-220", "geöffnet ist nicht gewählt"
        index = dialog.printer_choice.findData("prusa-mk4s")
        assert index >= 0
        dialog.printer_choice.setCurrentIndex(index)
        dialog.printer_choice.activated.emit(index)
        assert settings.printer == "prusa-mk4s"
    finally:
        dialog.deleteLater()


def test_a_built_fit_counts_like_an_entered_one(session: Session, qt_app) -> None:
    """§29: die Regeln für Passungen greifen auch ohne Eintrag im Dokument.

    Der Deckel aus ``create_lid`` bekommt sein Spiel aus dem Materialprofil und
    trägt es nirgends ein — im gedruckten Gewürzset liefen deshalb genau die
    Regeln nicht, die es für Passungen gibt: genaue Außenwand, gebremste
    Beschleunigung, Bügeln der Gleitfläche. Der Stapel weiß es trotzdem.
    """
    from app.core.scene import History, OperationDraft
    from app.ui.print_settings_dialog import PrintSettingsDialog

    dialog = PrintSettingsDialog(session, UiSettings())
    try:
        assert not dialog._fits_in_play(), "ein leeres Projekt hat keine Passung"

        History(session.project.document).apply(
            "Grundkörper",
            [OperationDraft(op="create_cylinder", params={"diameter": 40.0, "height": 20.0})],
        )
        assert not dialog._fits_in_play(), "ein Zylinder ist noch keine"

        History(session.project.document).apply(
            "Deckel",
            [OperationDraft(op="create_lid", inputs=("obj_1",), params={"thickness": 2.4})],
        )
        session.evaluate_now()
        assert dialog._fits_in_play(), "ein Deckel legt zwei Flächen mit Spiel aufeinander"
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize("collar,expected", [(0.0, ()), (4.0, ("clearance",))])
def test_a_declared_lid_condition_also_controls_print_advice(
    session: Session, qt_app: QApplication, collar: float, expected: tuple[str, ...]
) -> None:
    """Der Heuristikweg aktiviert keine ausdrücklich schlafende Passung erneut."""
    from app.core.types import FeatureRef, Fit, Operation

    document = session.project.document
    document.ops.append(Operation(id="op_1", op="create_lid", params={"collar": collar}))
    document.fits.append(
        Fit(
            "Deckel",
            FeatureRef("obj_1", "lip"),
            FeatureRef("obj_2", "rim"),
            when_positive=("op_1", "collar"),
        )
    )
    from types import SimpleNamespace

    import trimesh

    from app.core.geom.mesh import MeshData

    body = SceneObject(id="obj_1", name="Teil", mesh=MeshData.of(trimesh.creation.box()))
    session.last_result = _shown_result(SimpleNamespace(objects={body.id: body}))
    dialog = PrintSettingsDialog(session, UiSettings())
    try:
        assert dialog._fits_in_play() == expected
    finally:
        dialog.deleteLater()


# --- ein Filament je Materialslot (§20) -----------------------------------------


def _two_slots() -> list[object]:
    """Zwei Materialslots, wie ein Schild mit Schriftzug sie hat.

    Der Dialog liest sie über ``_plate_slots`` aus der Szene; hier wird genau
    diese eine Auskunft ersetzt. Ein wirklich erzeugter Schriftzug kostete in
    einem Oberflächentest mehr Zeit als der ganze Rest der Datei — und geprüft
    wird der Dialog, nicht die Beschriftungs-Op.
    """
    from app.core.types import MaterialSlot

    return [
        MaterialSlot(index=0, name="Gehäuse", colour=(0.0, 0.0, 0.0)),
        MaterialSlot(index=1, name="Schrift", colour=(1.0, 1.0, 1.0)),
    ]


def test_one_slot_shows_no_list(dialog: PrintSettingsDialog) -> None:
    """Ein einfarbiges Teil hat eine Farbe und braucht keine Liste darüber.

    Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche (§2): die Zeile
    „Filament" ist dann die ganze Aussage.
    """
    assert dialog.slot_rows == []


def test_a_second_slot_gets_its_own_choice(
    qt_app: QApplication, session: Session, tmp_path: Path, monkeypatch
) -> None:
    """Zwei Slots, zwei Auswahlen — und die Wahl bleibt im Projekt.

    Ein Schriftzug in Weiß auf schwarzem Gehäuse sind zwei Spulen mit zwei
    Temperaturen. Ohne diese Zeilen ließe sich das drucken, aber nicht sagen,
    und die zweite Farbe liefe mit den Werten der ersten.
    """
    monkeypatch.setattr(PrintSettingsDialog, "_plate_slots", lambda _self, **_kwargs: _two_slots())
    dialog = PrintSettingsDialog(session, UiSettings())

    assert len(dialog.slot_rows) == 2, "je Slot eine Zeile"
    # Der Name steht am zugänglichen Namen der Zeile und nicht in einem
    # ``text()``: Die Zeile trägt seit dem Farbfeld zwei Teile, und ein
    # Bildschirmleser braucht den Namen ohnehin am Container.
    assert "Gehäuse" in dialog.slot_rows[0][0].accessibleName()
    assert "Schrift" in dialog.slot_rows[1][0].accessibleName()
    # Und an der Auswahl selbst: Der Fokus landet auf ihr, nicht auf der
    # Zeile — ohne Namen las der Bildschirmleser nur „Kombinationsfeld".
    assert dialog.slot_rows[0][1].accessibleName() == "Gehäuse"
    assert dialog.slot_rows[1][1].accessibleName() == "Schrift"

    box = dialog.slot_rows[1][1]
    box.addItem("Haus PLA weiß", str(tmp_path / "pla.json"))
    box.setCurrentIndex(box.count() - 1)
    dialog._slot_filament_chosen(1)

    gemerkt = dialog.settings.slot_profiles
    assert len(gemerkt) == 2, "ein Eintrag je Slot"
    assert gemerkt[1] == "Haus PLA weiß", "der Name reist mit, nicht der Pfad"


@pytest.mark.parametrize("availability", ["missing", "incompatible", "no_profiles"])
def test_unavailable_slot_profile_stays_visible_without_changing_the_binding(
    qt_app: QApplication, session: Session, monkeypatch, availability: str
) -> None:
    """Ein fehlendes Profil darf weder ein anderes vortäuschen noch seine Bindung verlieren."""
    slots = _two_slots()
    monkeypatch.setattr(PrintSettingsDialog, "_plate_slots", lambda _self, **_kwargs: slots)
    dialog = PrintSettingsDialog(session, UiSettings())
    wanted = _profile("Mein PETG Spezial", "filament", filament_type="PETG")
    fallback = _profile("Anderes PETG", "filament", filament_type="PETG")
    fitting = [] if availability == "no_profiles" else [fallback]
    dialog._profiles = [fallback, wanted] if availability == "incompatible" else fitting
    monkeypatch.setattr(dialog, "_filaments_worth_showing", lambda _machine: fitting)
    dialog.ui_settings.slicer_base_filament = str(fallback.path)
    dialog.settings = handover.bind_slot_profiles(
        replace(dialog.settings, slot_profiles=(wanted.name,), slot_profile_bindings=None), slots
    )
    before = dialog.settings

    dialog._fill_filaments(None)

    box = dialog.slot_rows[0][1]
    assert wanted.name in box.currentText()
    assert box.currentText() == tr("Nicht verfügbar: {profile}").replace("{profile}", wanted.name)
    assert not box.model().item(box.currentIndex()).isEnabled()
    assert dialog.settings == before
    assert handover.configured_slots(slots, dialog.settings)[0].material == wanted.name
    if fitting:
        monkeypatch.setattr(dialog, "_refresh_advice", lambda: None)
        box.setCurrentIndex(box.findData(str(fallback.path)))
        box.activated.emit(box.currentIndex())
        assert handover.configured_slots(slots, dialog.settings)[0].material == fallback.name
    dialog.reject()


def test_a_slot_stores_the_profile_name_and_not_its_caption(
    qt_app: QApplication, session: Session, monkeypatch
) -> None:
    """Gespeichert wurde die **Beschriftung**, und die ist übersetzt.

    ``currentText()`` gibt bei einem selbst angelegten Profil „Haus PLA weiß
    (eigenes)" — im englischen Fenster „(own)". Der Slicer kennt weder das eine
    noch das andere: Die Slot-Wahl kam nie an, und beim nächsten Öffnen fand
    die Vorbelegung ihren eigenen Eintrag nicht wieder.

    **Der Test daneben konnte es nicht sehen**, und das ist der zweite Teil
    des Befunds: Er legte den Eintrag mit ``addItem("Haus PLA weiß", pfad)``
    an, also mit einer Beschriftung, die dem Namen gleicht. Zwei Wege, die
    dasselbe zurückgeben, unterscheidet keine Zusicherung — hier wird der
    Datensatz deshalb entzerrt, indem das Profil ein eigenes ist und seine
    Beschriftung damit einen Zusatz trägt.
    """
    monkeypatch.setattr(PrintSettingsDialog, "_plate_slots", lambda _self, **_kwargs: _two_slots())
    dialog = PrintSettingsDialog(session, UiSettings())
    eigenes = _profile("Haus PLA weiß", "filament", from_user=True, filament_type="PLA")
    dialog._profiles = [eigenes]

    box = dialog.slot_rows[1][1]
    box.addItem(eigenes.title("eigenes"), str(eigenes.path))
    box.setCurrentIndex(box.count() - 1)
    assert box.currentText() != eigenes.name, "sonst prüft der Test zwei gleiche Zahlen"

    dialog._slot_filament_chosen(1)

    assert dialog.settings.slot_profiles[1] == "Haus PLA weiß"
    assert "(" not in dialog.settings.slot_profiles[1], "kein Anhang, den kein Slicer kennt"
    # Und die Vorbelegung findet die Wahl wieder — ohne sie wäre der Name zwar
    # richtig abgelegt und beim nächsten Öffnen trotzdem verloren.
    assert dialog._filament_index(box, "Haus PLA weiß") == box.count() - 1


def test_the_slot_assignment_outlives_a_quality_change(
    qt_app: QApplication, session: Session, monkeypatch
) -> None:
    """Der Zwilling des Druckerwechsels, eine Stufe weiter.

    ``_quality_changed`` löst neu auf, und das ist richtig: Eine Stufe zu
    wechseln *heißt*, sich neue Vorgaben geben zu lassen. Die Slotbelegung
    fällt nicht darunter — sie sagt, **welche Spule auf welchem Materialslot
    des Modells liegt** (§20), und das ändert sich nicht, weil jemand von 0,2
    auf 0,12 mm geht.

    Der Beweis steht im Code und nicht in der Meinung: ``resolve`` ist eine
    reine Funktion aus Profil und Stufe, und ``slot_profiles`` ist das einzige
    Feld, für das sie keine Quelle hat. „Rücknehmbar über die Stufe, aus der
    man kam" gilt deshalb für jeden anderen Wert und für diesen einen nicht —
    er kommt von keiner Stufe zurück, weil er von keiner kam.

    Schlimmer als der Verlust war, dass man ihn nicht sah: Die zwei
    Auswahlfelder standen unverändert da, während das Modell nichts mehr von
    ihnen wusste, und beim Export lief die weiße Schrift mit dem Filament der
    Platte.

    **Beide Hälften**, sonst wäre „es ändert sich nichts mehr" auch grün.
    """
    monkeypatch.setattr(PrintSettingsDialog, "_plate_slots", lambda _self, **_kwargs: _two_slots())
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog.settings = replace(dialog.settings, slot_profiles=("Haus PETG", "Haus PLA weiß"))
    assert dialog.settings.quality == "standard"
    assert print_settings.read_path(dialog.settings, "layers.layer_height") == pytest.approx(0.2)

    _select_quality(dialog, "fine")

    assert dialog.settings.slot_profiles == ("Haus PETG", "Haus PLA weiß"), (
        "die Spule je Slot ist keine Vorgabe der Stufe"
    )
    assert print_settings.read_path(dialog.settings, "layers.layer_height") == pytest.approx(
        0.12
    ), "und die Stufe wirkt weiterhin auf alles, was ihr gehört"


def test_filament_values_outlive_a_quality_change(qt_app: QApplication, session: Session) -> None:
    """Werte einer Spule kommen aus keiner Qualitätsstufe.

    Der Dialog bewahrte die Zuordnung des Filamentprofils, aber nicht den
    daneben gespeicherten ``SlotOverride``. Eine weiße PLA-Schrift auf einem
    PETG-Gehäuse sprang damit beim Wechsel auf „fein" unbemerkt von 210 auf
    240 Grad zurück.
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    own_temperature = replace(dialog.settings.temperature, nozzle=210)
    override = SlotOverride(
        name="PLA Weiß",
        colour=(1.0, 1.0, 1.0),
        temperature=own_temperature,
    )
    dialog.settings = replace(dialog.settings, slot_overrides=(override,))

    _select_quality(dialog, "fine")

    assert dialog.settings.slot_overrides == (override,)
    assert dialog.settings.quality == "fine"
    assert dialog.settings.layers.layer_height == pytest.approx(0.12), (
        "die Qualitätsstufe wirkt weiterhin auf die Projektwerte"
    )


def test_the_slot_assignment_outlives_a_printer_change(
    qt_app: QApplication, session: Session, monkeypatch
) -> None:
    """Derselbe Verlust an der zweiten Stelle — der dritte Zwilling.

    ``_scene_profile_changed`` rettet seit heute die übersteuerten Werte, und
    zwar über die 56 Pfade aus ``FIELDS``. ``slot_profiles`` steht in keinem
    Feld des Dialogs und fiel damit durch dasselbe Loch wie beim
    Stufenwechsel: Die Rettung, die den Fehler behob, ließ genau diesen einen
    Wert liegen.
    """
    monkeypatch.setattr(PrintSettingsDialog, "_plate_slots", lambda _self, **_kwargs: _two_slots())
    dialog = PrintSettingsDialog(session, UiSettings())
    try:
        _select_printer(dialog, "generic-220")
        dialog.settings = replace(dialog.settings, slot_profiles=("Haus PETG", "Haus PLA weiß"))

        _select_printer(dialog, "prusa-mini")

        assert dialog.settings.slot_profiles == ("Haus PETG", "Haus PLA weiß")
        assert print_settings.read_path(dialog.settings, "layers.line_width") == pytest.approx(
            0.45
        ), "und der Druckerwechsel wirkt weiterhin"
    finally:
        assert session.wait_for_idle(60_000)


def test_changing_only_the_project_printer_keeps_every_filament_choice(
    qt_app: QApplication, session: Session
) -> None:
    """Der Kopfzeilenweg darf weder Projektmaterial noch Slotwerte umstellen."""
    session.change_scene_profile("generic-220", "petg")
    assert session.wait_for_idle()
    dialog = PrintSettingsDialog(session, UiSettings())
    own_temperature = replace(dialog.settings.temperature, nozzle=210, bed=60)
    override = SlotOverride(
        name="PLA Weiß",
        colour=(1.0, 1.0, 1.0),
        temperature=own_temperature,
    )
    dialog.settings = replace(
        dialog.settings,
        slot_profiles=("PETG Schwarz", "PLA Weiß"),
        slot_overrides=(override,),
    )
    try:
        _select_printer(dialog, "prusa-mini")

        assert session.project.document.printer == "prusa-mini"
        assert session.project.document.material == "petg"
        assert session.profile.material.id == "petg"
        assert dialog.settings.slot_profiles == ("PETG Schwarz", "PLA Weiß")
        assert dialog.settings.slot_overrides == (override,)
    finally:
        assert session.wait_for_idle(60_000)


def _select_quality(dialog: PrintSettingsDialog, quality: str) -> None:
    """Die Stufe über die Auswahl wechseln, wie ein Kunde es tut."""
    index = dialog.quality.findData(quality)
    assert index >= 0, quality
    dialog.quality.setCurrentIndex(index)


def test_a_different_printer_keeps_what_the_customer_set(
    qt_app: QApplication, session: Session
) -> None:
    """Ein Druckerwechsel warf jeden eigenen Wert weg — wortlos.

    ``_scene_profile_changed`` löste den ganzen Satz neu auf. Übersteuerte
    Werte und mitgebrachte Werte (aus einer eingelesenen 3MF) waren damit fort:
    62 % Füllung wurden beim Umstellen des Druckers zu 15 %, ohne Ansage und
    ohne Undo — der Dialog ist kein Verlaufsschritt.

    Ein Drucker wechselt **Vorgaben**. Was von der alten Vorgabe abweicht, ist
    keine Vorgabe, sondern eine Entscheidung, und die bleibt. Beide Hälften
    stehen hier: Ohne die zweite wäre „nichts ändert sich mehr" auch grün, und
    das wäre der nächste Fehler.
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    try:
        _select_printer(dialog, "generic-220")
        assert print_settings.read_path(dialog.settings, "layers.line_width") == pytest.approx(0.42)

        fuellung = dialog._editors["infill.density"]
        assert isinstance(fuellung, QDoubleSpinBox)
        fuellung.setValue(62.0)  # das Feld zeigt Prozent, das Modell 0…1
        assert print_settings.read_path(dialog.settings, "infill.density") == pytest.approx(0.62)

        _select_printer(dialog, "prusa-mini")

        assert print_settings.read_path(dialog.settings, "infill.density") == pytest.approx(0.62), (
            "die eigene Entscheidung überlebt den Wechsel"
        )
        assert print_settings.read_path(dialog.settings, "layers.line_width") == pytest.approx(
            0.45
        ), "und die unangetastete Vorgabe folgt der neuen Düse"
        assert dialog._editors["infill.density"].value() == pytest.approx(62.0), (
            "auch im Feld, nicht nur im Modell"
        )
    finally:
        # **Der Druckerwechsel wertet neu aus, und zwar nebenher.** Ein
        # Arbeiter, der den Test überlebt, nimmt beim Abbau den Prozess mit —
        # der Lauf riss danach in ``_no_worker_outlives_its_window``, mit
        # „passed" davor und Exit 139 dahinter (siehe ``Session.wait_for_idle``).
        assert session.wait_for_idle(60_000)


def _select_printer(dialog: PrintSettingsDialog, printer_id: str) -> None:
    """Den Drucker über die Auswahl wechseln, wie ein Kunde es tut.

    Über den Index und nicht über ``_scene_profile_changed``: Am Signal hängt
    die halbe Zusicherung, und ein Test, der die Methode selbst ruft, prüft
    den Weg nicht (`.claude/rules/tests.md`, „Am Weg vorbei").
    """
    index = dialog.printer_choice.findData(printer_id)
    assert index >= 0, printer_id
    dialog.printer_choice.setCurrentIndex(index)


def test_the_nozzle_is_settable_and_reaches_the_computation(
    session: Session, monkeypatch, tmp_path: Path
) -> None:
    """Eine andere Düse lässt sich am Drucker einstellen — und sie rechnet mit.

    Die mitgelieferte Tabelle führt **jedes** der sechzehn Geräte mit 0,4. Wer
    eine andere aufschraubt, konnte das bis zum 16.09.2026 nirgends sagen, und
    daran hängt mehr als eine Zahl: Bahnbreite und Schichthöhe kommen aus ihr,
    und die Wahl des Maschinenprofils im Slicer auch. Gemessen an dem Tag:
    ElegooSlicer stand auf „… 0.2 nozzle", der Auftrag war für 0,4 gerechnet —
    der Slicer nahm ihn nicht an, jede Linienbreite stand auf null, und er
    meldete „zu geringe Linienbreite".

    Geprüft wird über das Feld und nicht über ``_nozzle_changed``: Am Signal
    hängt die halbe Zusicherung (`.claude/rules/tests.md`, „Am Weg vorbei").
    """
    from app.core.export import slicer_profiles
    from app.core.knowledge import print_settings, profiles

    # **In einen eigenen Ordner, sonst erbt die halbe Datei diese Düse.** Die
    # Einstellung gehört dem Gerät und wird deshalb wirklich gespeichert; ohne
    # diese Zeile stand danach in jedem folgenden Test ein Centauri mit 0,6,
    # und sechs von ihnen wurden rot — isoliert gefahren alle grün.
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    monkeypatch.setattr(profiles, "_printers", None)
    dialog = PrintSettingsDialog(session, UiSettings())
    before = profiles.printer(str(dialog.printer_choice.currentData()))
    assert dialog.nozzle.value_mm() == pytest.approx(before.nozzle_diameter), (
        "das Feld zeigt die Düse des gewählten Druckers"
    )
    assert (
        tuple(
            dialog.nozzle_choice.itemData(index)
            for index in range(dialog.nozzle_choice.count() - 1)
        )
        == slicer_profiles.COMMON_NOZZLE_SIZES
    )
    other = dialog.nozzle_choice.count() - 1
    dialog.nozzle_choice.setCurrentIndex(other)
    dialog.nozzle_choice.activated.emit(other)
    assert not dialog.nozzle.isHidden(), "eigene Düsengröße bleibt erreichbar"

    dialog.nozzle.set_value_mm(0.6)

    after = profiles.printer(before.id)
    assert after.nozzle_diameter == pytest.approx(0.6), "die Düse gehört zum Drucker"
    assert after.extrusion_width == pytest.approx(0.63), (
        "die Bahnbreite zieht mit — sonst gehört sie zur alten Düse"
    )

    computed = print_settings.resolve(profiles.make_profile(before.id, "pla"), "standard")
    assert computed.layers.line_width == pytest.approx(0.63), "und die Rechnung nimmt sie an"


def test_the_slot_choice_survives_the_project_file(tmp_path: Path) -> None:
    """Die Zuordnung gehört ins Projekt und nicht an den Rechner.

    Sie beschreibt das Teil — welcher Slot aus welcher Spule kommt —, und ein
    Projekt, das man weitergibt, soll das mitbringen. Der **Name** reist,
    nicht der Pfad (Regel 12).
    """
    from app.core.scene.serialise import print_settings_from_data, print_settings_to_data

    settings = replace(
        print_settings.resolve(profiles.make_profile()),
        slot_profiles=("Haus PETG", "Haus PLA weiß"),
    )

    zurueck = print_settings_from_data(print_settings_to_data(settings))

    assert zurueck.slot_profiles == ("Haus PETG", "Haus PLA weiß")


def test_a_late_profile_search_does_not_overwrite_a_choice(qt_app: QApplication) -> None:
    """**Der Wettlauf, an dem ein Test einmal unter Last hing.**

    Die Profilsuche läuft in einem Arbeiter und antwortet nachgereicht. Wer in
    der Zwischenzeit selbst eine Maschine gewählt hatte, sah sie danach auf
    etwas anderes springen — und beim Schließen wurde die *neue* gemerkt, nicht
    seine. Dieselbe Regel wie beim Druckervorschlag der Erstinbetriebnahme:
    Eine Vorgabe, die eine Wahl überschreibt, ist keine Vorgabe mehr (§2.4).

    Sichtbar wurde es, seit ``recheck_slicer`` die Suche ein zweites Mal
    startet: Beim ersten Öffnen ist die Auswahl leer, danach nicht mehr.
    """
    session = Session()
    settings = UiSettings()
    dialog = PrintSettingsDialog(session, settings)

    # So sieht es aus, wenn jemand gewählt hat, bevor die Suche antwortet.
    dialog.machine_choice.addItem("Meine Maschine", "C:/meine/maschine.json")
    dialog.machine_choice.setCurrentIndex(dialog.machine_choice.count() - 1)

    dialog._profiles_found(
        [
            _profile("Etwas anderes", "machine", printer_model="Etwas anderes", nozzle=0.4),
            _profile("Und noch was", "machine", printer_model="Und noch was", nozzle=0.6),
        ]
    )

    assert dialog.machine_choice.currentData() == "C:/meine/maschine.json"


def test_the_chosen_machine_survives_until_the_dialog_closes(qt_app: QApplication) -> None:
    """Und sie ist danach gemerkt — das ist der Punkt der Sache (§29, A5).

    Der Test daneben prüft die Auswahl, dieser die Folge: Was im Dialog stand,
    gilt auch für den Export.
    """
    session = Session()
    settings = UiSettings()
    dialog = PrintSettingsDialog(session, settings)
    dialog.machine_choice.addItem("Meine Maschine", "C:/meine/maschine.json")
    dialog.machine_choice.setCurrentIndex(dialog.machine_choice.count() - 1)

    # Zwei Profile, nicht eines: Bei genau einem fällt ``_profiles_found`` auf
    # Index 0 zurück, und der wäre zufällig der eigene Eintrag — der Test wäre
    # grün, ohne etwas zu prüfen.
    dialog._profiles_found(
        [
            _profile("Etwas anderes", "machine", printer_model="Etwas anderes", nozzle=0.4),
            _profile("Und noch was", "machine", printer_model="Und noch was", nozzle=0.6),
        ]
    )
    dialog.reject()

    assert settings.slicer_machine_profile == "C:/meine/maschine.json"


def test_a_failed_slicer_run_leaves_its_reason_in_the_dialog(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Fenster darf den Lauf nicht vergessen, wenn das Fehlerfenster zugeht.

    Gemessen im Kundendurchgang: PrusaSlicer lehnte eine Platte in
    Bettkoordinaten ab — „Der Slicer sagt, die Teile liegen außerhalb seines
    Bauraums", mit *Auf dem Bett anordnen* als erster Handlung. Der Satz
    erschien einmal; danach stand in der Zeile, die eben noch „Der Slicer
    rechnet …" sagte, nichts mehr.

    Geprüft wird über den Slot, der am Signal des Arbeiters hängt, und der
    Fehlerdialog wird dabei stillgelegt: ``exec`` wartet auf einen Menschen.
    """
    from app.core.errors import ARRANGE_ON_BED, ExternalToolError
    from app.ui import print_settings_dialog as modul

    gezeigt: list[object] = []
    monkeypatch.setattr(modul, "show_error", lambda problem, parent=None: gezeigt.append(problem))
    dialog.state.setText("Der Slicer rechnet …")

    dialog._slice_failed(
        ExternalToolError(
            tool="prusa-slicer",
            detail="Der Slicer sagt, die Teile liegen außerhalb seines Bauraums.",
            suggestions=(ARRANGE_ON_BED,),
        )
    )

    assert gezeigt, "das Fehlerfenster kommt weiterhin"
    assert "außerhalb seines Bauraums" in dialog.state.text(), dialog.state.text()


def test_a_failed_slicer_run_returns_the_plate_findings(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der externe Abbruch darf die genauere Vorprüfung nicht verschlucken."""
    from app.core.errors import ExternalToolError
    from app.core.types import Finding
    from app.ui import print_settings_dialog as modul

    monkeypatch.setattr(modul, "show_error", lambda *args, **kwargs: None)
    returned: list[list[Finding]] = []
    dialog.reported.connect(returned.append)
    finding = Finding(
        code="arrange.out_of_build_volume",
        severity="error",
        message="Das Teil ist größer als der Bauraum.",
    )

    dialog._slice_failed(
        ExternalToolError(tool="elegoo-slicer", detail="Keine Druckdatei."),
        [finding],
    )

    assert returned == [[finding]], "der Prüfbericht erfährt sonst nichts vom Abbruch"


# --- Fehlerhandlungen des Slicer-Wegs -----------------------------------------------


class _WindowWithHandlers(QWidget):
    """Ein Fenster, das eigene Fehlerhandlungen trägt — wie das Hauptfenster."""

    def error_handlers(self) -> dict[str, object]:
        return {"repair_and_retry": lambda _error: None, "export_only": lambda _error: None}


def test_the_dialog_wires_the_three_slicer_actions(qt_app: QApplication, session: Session) -> None:
    """Drei Kennungen wurden angeboten und von niemandem eingelöst.

    `show_output`, `check_profile` und `choose_slicer` standen in den
    Slicer-Fehlschlägen und hatten nirgends einen Handler — angeboten wird
    aber nur, wofür es einen gibt, also blieben sie Sätze zum Lesen. Auf einem
    Rechner mit drei Slicern war das eine Sackgasse (§2.1).
    """
    parent = _WindowWithHandlers()
    dialog = PrintSettingsDialog(session, UiSettings(), parent=parent)

    known = dialog.error_handlers()

    for name in ("show_output", "check_profile", "choose_slicer"):
        assert name in known, f"{name} wurde angeboten und nicht eingelöst"
        assert callable(known[name])


def test_choose_printer_error_action_uses_the_open_dialog_selector(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Rückweg aus der Fehlerkarte öffnet keinen zweiten Druckdialog."""
    from app.core.errors import ExternalToolError

    parent = _WindowWithHandlers()
    parent_calls: list[object] = []
    monkeypatch.setattr(
        parent,
        "error_handlers",
        lambda: {"choose_printer": parent_calls.append},
    )
    dialog = PrintSettingsDialog(session, UiSettings(), parent=parent)
    opened: list[bool] = []
    monkeypatch.setattr(dialog.printer_choice, "showPopup", lambda: opened.append(True))

    known = dialog.error_handlers()
    handler = known["choose_printer"]
    handler(ExternalToolError(tool="cura", detail="Drucker wählen."))

    assert opened == [True]
    assert not parent_calls, "der Hauptfenster-Handler öffnete sonst einen zweiten Dialog"


def test_the_dialog_keeps_the_handlers_of_its_window(
    qt_app: QApplication, session: Session
) -> None:
    """Die eigene Liste **ergänzt** die des Fensters, sie ersetzt sie nicht.

    `handlers_of` nimmt das erste Widget der Elternkette, das
    `error_handlers` trägt, und kehrt zurück. Eine eigene Methode am Dialog
    verdeckt damit das ganze Wörterbuch darüber: Die neuen Knöpfe wären da,
    die alten — reparieren, verkleinern, teilen, nur exportieren — still fort,
    und zwar für jeden Fehler, der mit diesem Dialog als Fenster erscheint.
    """
    parent = _WindowWithHandlers()
    dialog = PrintSettingsDialog(session, UiSettings(), parent=parent)

    known = dialog.error_handlers()

    assert "repair_and_retry" in known, "die Handlungen des Fensters gingen verloren"
    assert "export_only" in known


def test_finding_the_profiles_twice_does_not_double_the_list(
    dialog: PrintSettingsDialog,
) -> None:
    """Zweimal gefunden heißt nicht zweimal angehängt.

    Aus tausend Druckerprofilen wurden im Handlauf zweitausend, jedes doppelt
    (30.08.2026). `_profiles_found` füllte ohne zu leeren; geschützt war nur
    der Weg über `_slicer_chosen`, der vorher `_clear_profile_choices` ruft.
    Über `recheck_slicer` lief er ungeschützt — eine Absicherung am Aufrufer
    lässt den nächsten Aufrufer wieder frei.
    """
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
        default_process="0.20mm Standard",
    )
    found = [machine, _profile("0.20mm Standard", "process")]

    dialog._profiles_found(found)
    einmal = dialog.machine_choice.count()
    dialog._profiles_found(found)

    assert dialog.machine_choice.count() == einmal, "der zweite Fund hängte an, statt zu ersetzen"


def test_switching_the_slicer_drops_the_result_of_the_old_one(
    dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """Die Ergebniszeile des alten Slicers überlebte den Wechsel.

    Frisch auf PrusaSlicer gewechselt, und die Statuszeile zeigte weiter
    „Druckzeit: 18 min …" vom ElegooSlicer-Lauf davor — *Druckdatei speichern*
    bot dessen Datei an. Wer dort speichert, hält einen fremden Lauf für
    seinen eigenen (Handlauf, 30.08.2026).
    """
    ergebnis = tmp_path / "alt.gcode"
    ergebnis.write_text("; vom alten Slicer")
    dialog._gcode = [ergebnis]
    dialog.save_button.setEnabled(True)
    dialog.state.setText("Druckzeit: 18 min · Material: 4,7 g")
    dialog._slicers = (tmp_path / "elegoo-slicer.exe", tmp_path / "prusa-slicer.exe")
    dialog._slicer_path = dialog._slicers[0]

    dialog._slicer_chosen(1)

    assert dialog._gcode == [], "die Druckdatei des alten Slicers wurde weiter angeboten"
    assert not dialog.save_button.isEnabled()
    # Seit Stufe C sieht der Dialog auch PrusaSlicers Profile durch und sagt das
    # in der Statuszeile — die Kennzahlen des alten Laufs dürfen nur nicht bleiben.
    assert "Druckzeit" not in dialog.state.text(), "die Kennzahlen des alten Laufs standen noch da"


# --- Die Slicersuche haelt den Dialog nicht auf (§2.8) ----------------------------


def _slow_slicer_search(monkeypatch: pytest.MonkeyPatch, found: tuple[Path, ...] = ()):
    """Eine Slicersuche, die wartet, bis der Test sie freigibt.

    Der Rückgabewert nennt den Thread, in dem sie lief — denn das ist der
    eigentliche Fund: ``discover.find_programs`` kostete auf einer Maschine mit
    sechs Slicern 3,1 s warm und über 11 s kalt, und bis zum 13.09.2026 lief
    das im Konstruktor des Dialogs, also im Qt-Hauptthread. Zehn Sekunden nach
    dem Klick auf *Drucken* erschien gar nichts.
    """
    from app.core import discover

    tor = threading.Event()
    lief_in: list[str] = []

    def langsam(_tool_id: str, _names: object) -> tuple[Path, ...]:
        lief_in.append(threading.current_thread().name)
        tor.wait(10.0)
        return found

    monkeypatch.setattr(discover, "find_programs", langsam)
    return tor, lief_in


def test_the_print_dialog_stands_before_the_slicer_search_comes_back(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Dialog ist da, bevor irgendjemand nach Slicern gesucht hat (§2.8).

    Gemessen am 13.09.2026 auf dieser Maschine: ``find_programs`` brauchte
    3,1 s warm und 11,2 bis 13,3 s kalt, und der Aufruf stand im Konstruktor.
    Wer *Drucken* klickte, sah das Fenster erst danach — über der Grenze von
    zwei Sekunden aus ``.claude/rules/wartezeit.md``, und ohne Fortschritt,
    ohne Abbruch, ohne irgendetwas.

    Vier Zusagen, und die erste ist die, die den Fehler wirklich ausschließt:
    Die Suche läuft **nicht im Hauptthread**. Die übrigen drei sind der
    Wartezustand — kein Zustand ohne Erhebung, ein Grund an beiden Knöpfen
    (Regel 18: Tooltip, Statuszeile, Bildschirmleser), und alles andere im
    Dialog bleibt bedienbar.
    """
    tor, lief_in = _slow_slicer_search(monkeypatch)
    try:
        begonnen = time.perf_counter()
        dialog = PrintSettingsDialog(session, UiSettings())
        dialog.show()
        qt_app.processEvents()
        gebraucht = time.perf_counter() - begonnen

        assert gebraucht < 2.0, f"der Dialog wartete {gebraucht:.1f} s auf die Suche"
        # Der Arbeiter ist gestartet, erreicht die Suche aber erst, wenn sein
        # Thread läuft — unter Last (Tor mit acht Arbeitern) nach dem Blick hier.
        frist = time.monotonic() + 10.0
        while not lief_in and time.monotonic() < frist:
            time.sleep(0.01)
        assert lief_in, "die Suche lief gar nicht — dann prüft dieser Test nichts"
        assert lief_in[0] != threading.main_thread().name, (
            f"die Suche lief im Qt-Hauptthread ({lief_in[0]}) — genau das war der Fehler"
        )

        # Kein Zustand ohne Erhebung: nicht „Dafür fehlt ein Slicer", solange
        # noch niemand nachgesehen hat.
        assert "gesucht" in dialog.state.text(), dialog.state.text()
        assert "fehlt ein Slicer" not in dialog.state.text()
        assert not dialog.setup_button.isVisible(), (
            "der Weg zu einem Slicer steht vor der Antwort — ein Angebot ohne Frage"
        )
        for knopf in (dialog.slice_button, dialog.open_button):
            assert not knopf.isEnabled(), "während der Suche wird nicht geslicet"
            grund = knopf.toolTip()
            assert "gesucht" in grund, grund
            assert knopf.accessibleDescription() == grund

        # Und der Kunde darf währenddessen alles andere tun.
        assert dialog._editors["layers.layer_height"].isEnabled()
        assert dialog.quality.isEnabled()
    finally:
        tor.set()
        dialog.wait_for_slicers()
        dialog.release()


def test_the_missing_slicer_names_its_button_as_it_reads(dialog: PrintSettingsDialog) -> None:
    """Der Grund am grauen Knopf nennt den Weg so, wie er dasteht.

    „der Knopf Zusätzliche Programme richtet einen ein" las sich als Satz
    ohne Knopf; der Name steht jetzt in Anführungszeichen und genau so, wie
    ihn der Knopf trägt — mit den drei Punkten.
    """
    dialog._slicers_pending = False
    dialog._slicer_path = None
    dialog._show_slicer_state()

    grund = dialog.slice_button.toolTip()
    assert f"„{dialog.setup_button.text()}“" in grund, grund


def test_the_slicer_search_arrives_and_settles_the_choice(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Was die Suche findet, kommt über ihr Signal an — und wird die Wahl.

    Die Gegenrichtung zum Test darüber: Der Dialog steht sofort, aber er bleibt
    nicht leer. Die Wahl folgt derselben Regel wie früher im Konstruktor — der
    gemerkte Slicer gewinnt, sonst der erste Fund —, und die Auswahlzeile
    erscheint, weil es diesmal etwas zu wählen gibt (§2.4).
    """
    from app.core import discover

    erster = tmp_path / "ElegooSlicer" / "elegoo-slicer.exe"
    gemerkter = tmp_path / "PrusaSlicer" / "prusa-slicer.exe"
    for datei in (erster, gemerkter):
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text("", encoding="utf-8")
    tor, _lief_in = _slow_slicer_search(monkeypatch, (erster, gemerkter))
    discover.remember_path("slicer", str(gemerkter))
    try:
        dialog = PrintSettingsDialog(session, UiSettings())
        qt_app.processEvents()
        # Der gemerkte gilt schon vorläufig — er steht in der Konfiguration und
        # kostet keinen Ordnerdurchgang.
        assert dialog._slicer_path == gemerkter
        assert dialog._slicers == (gemerkter,)
        assert dialog._slicers_pending

        tor.set()
        assert dialog.wait_for_slicers(), "die Suche kam nicht zurück"

        assert dialog._slicers == (erster, gemerkter), "die Liste kam nicht an"
        assert dialog._slicer_path == gemerkter, "der gemerkte schlägt den ersten Fund"
        assert dialog.slicer_choice.count() == 2, "die Auswahl wurde nicht gefüllt"
        assert dialog.slicer_choice.currentData() == str(gemerkter)
        assert not dialog._slicers_pending
        assert "gesucht" not in dialog.state.text(), "der Wartezustand blieb stehen"
    finally:
        tor.set()
        dialog.release()
        # Der Merker liegt in der Konfiguration und überlebt den Test sonst —
        # der nächste fände einen Slicer vor, den er nie gesetzt hat.
        discover.remember_path("slicer", "")


def test_a_second_slicer_search_replaces_the_answer_of_the_first(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``recheck_slicer`` während einer laufenden Suche: die alte Antwort zählt nicht.

    Dasselbe Muster wie bei der Profilsuche (``_profile_worker = None``): Die
    Halteleine hält den alten Arbeiter bis zu seinem Ende, sein Signal gehört
    aber nicht mehr zur aktuellen Frage. Ohne diese Unterscheidung überschriebe
    der Nachzügler genau das, wonach der Kunde gerade gefragt hat — er kommt
    aus der Zeit **vor** der Installation und kann den neuen Slicer gar nicht
    kennen.

    Gefahren wird über die echten Signale und nicht über einen Direktaufruf des
    Slots: Die Wache fragt ``sender()``, und ohne Absender gilt jede Antwort
    als die eigene.
    """
    from app.core import discover

    alt = tmp_path / "Alt" / "elegoo-slicer.exe"
    neu = tmp_path / "Neu" / "prusa-slicer.exe"
    for datei in (alt, neu):
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text("", encoding="utf-8")

    tore = [threading.Event(), threading.Event()]
    funde: list[tuple[Path, ...]] = [(alt,), (neu,)]
    zaehler = threading.Lock()
    laeufe: list[int] = []

    def langsam(_tool_id: str, _names: object) -> tuple[Path, ...]:
        with zaehler:
            nummer = min(len(laeufe), 1)
            laeufe.append(nummer)
        tore[nummer].wait(10.0)
        return funde[nummer]

    monkeypatch.setattr(discover, "find_programs", langsam)
    dialog = PrintSettingsDialog(session, UiSettings())
    vorlaeufig = dialog._slicer_path
    try:
        erster = dialog._slicer_worker
        assert erster is not None
        bis = time.monotonic() + 5.0
        while not laeufe and time.monotonic() < bis:
            qt_app.processEvents()
        assert laeufe, "die erste Suche lief nicht an"

        dialog.recheck_slicer()
        zweiter = dialog._slicer_worker
        assert zweiter is not None and zweiter is not erster, "der zweite Start ersetzt nicht"

        # Der veraltete antwortet zuerst — und darf nichts bewirken.
        tore[0].set()
        erster.wait(10_000)
        qt_app.processEvents()

        assert dialog._slicer_path == vorlaeufig, "die veraltete Suche hat die Wahl geschrieben"
        assert alt not in dialog._slicers, "ihre Liste kam trotzdem an"
        assert dialog._slicers_pending, "der Wartezustand endete mit dem falschen Lauf"

        tore[1].set()
        assert dialog.wait_for_slicers(), "die zweite Suche kam nicht zurück"

        assert dialog._slicer_path == neu, "der Fund der aktuellen Suche fehlt"
        assert dialog._slicers == (neu,)
    finally:
        for tor in tore:
            tor.set()
        dialog.release()


def test_closing_during_the_slicer_search_leaves_no_worker_behind(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zumachen, während gesucht wird — kein Absturz, kein Zombie.

    Die Suche hängt an keiner fremden Antwort, aber sie läuft in einem Thread,
    und ein Thread, der sein Fenster überlebt, nimmt den Prozess mit
    (:mod:`app.ui.leash`). ``release`` ist der Name, den die Aufräumhilfe der
    Suite blind ruft — sie wartet über ``_settle``, und dort steht der neue
    Arbeiter seit dem 13.09.2026 in derselben Liste wie seine vier Geschwister.
    """
    from app.ui import leash

    tor, _lief_in = _slow_slicer_search(monkeypatch)
    dialog = PrintSettingsDialog(session, UiSettings())
    qt_app.processEvents()
    laeuft = dialog._slicer_worker
    assert laeuft is not None and laeuft.isRunning(), "ohne laufenden Arbeiter prüft das nichts"
    assert laeuft in leash.alive(), "der Arbeiter hängt nicht an der Halteleine"

    dialog.reject()
    tor.set()
    dialog.release()

    assert not laeuft.isRunning(), "der Arbeiter überlebte seinen Dialog"


def test_closing_during_the_slicer_search_does_not_wait_for_it(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zumachen, während gesucht wird — und zwar sofort.

    Der Arbeiter holte die Suche aus dem Konstruktor, und ``_settle`` holte
    sie ans Ende zurück: Er stand in derselben Liste wie der Slicerlauf, der
    den Arbeitsordner braucht, und ``done`` schob das Schließen auf, bis auch
    er zurück war — bis zu 13 s mit gesperrten Knöpfen und „Wird geschlossen,
    sobald …“, ausgerechnet für den Kunden, der gleich wieder zumacht.
    Gefunden über den Weg *Filamente …* zum Filamentwähler
    (``test_operation_ui``): Der Abschnitt ging nicht auf, weil ``finished``
    erst nach der Suche kam. Der Test darüber bleibt wahr: Beim Abbau wartet
    der Dialog weiterhin auf sie.
    """
    tor, _lief_in = _slow_slicer_search(monkeypatch)
    dialog = PrintSettingsDialog(session, UiSettings())
    qt_app.processEvents()
    laeuft = dialog._slicer_worker
    assert laeuft is not None and laeuft.isRunning(), "ohne laufenden Arbeiter prüft das nichts"
    fertig: list[int] = []
    dialog.finished.connect(fertig.append)

    dialog.reject()

    assert fertig == [int(QDialog.DialogCode.Rejected)], "der Dialog ging nicht sofort zu"
    assert dialog.isHidden(), "und sperrt das Fenster nicht mehr"
    assert laeuft.isRunning(), "die Suche läuft weiter — sie hält nur nichts mehr auf"

    tor.set()
    dialog.release()
    assert not laeuft.isRunning(), "beim Abbau wartet der Dialog trotzdem auf sie"


def test_the_reason_for_the_grey_button_is_on_screen(
    dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """Der Grund stand nur im Tooltip, und der erscheint erst beim Zielen.

    Wer den grauen *Slicen*-Knopf sah, las nirgends, was ihm fehlt — die
    Auswahl dazu liegt zudem in einer zugeklappten Box (Handlauf,
    30.08.2026). Ein grauer Knopf allein ist außerdem Bedeutung über Farbe
    (Regel 18).
    """
    dialog._slicer_path = tmp_path / "elegoo-slicer.exe"
    dialog._needs_profiles = True
    dialog._profiles_pending = False
    dialog.machine_choice.clear()

    dialog._show_slicer_state()

    assert not dialog.slice_button.isEnabled(), "ohne Profil bleibt der Knopf zu"
    grund = dialog.slice_button.toolTip()
    assert grund, "der Grund steht am Knopf"
    assert dialog.state.text() == grund, "und er steht auch sichtbar auf dem Bildschirm"


def test_a_finished_run_keeps_its_numbers_on_screen(
    dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """Ohne Grund bleibt stehen, was der Lauf ergeben hat.

    Die Gegenrichtung zum Test darüber: Die Zeile trägt beides, und ein
    fehlender Grund darf das Ergebnis nicht wegwischen.
    """
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
        default_process="0.20mm Standard",
    )
    dialog._profiles_found([machine, _profile("0.20mm Standard", "process")])
    dialog._slicer_path = tmp_path / "elegoo-slicer.exe"
    dialog.state.setText("Druckzeit: 18 min · Material: 4,7 g")

    dialog._show_slicer_state()

    assert dialog.state.text() == "Druckzeit: 18 min · Material: 4,7 g"


def test_the_plate_carries_the_height_of_its_tallest_part(
    dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """Ohne die Höhe kann niemand merken, dass die Druckdatei zu kurz ist.

    Cura druckte bei zentriert importiertem Modell still die halbe Höhe — was
    unter dem Druckbett lag, fiel weg (Handlauf, 30.08.2026). Der Vergleich
    dagegen braucht ein Maß, und das kennt nur die Oberfläche.
    """
    import trimesh

    from app.core.export import handover
    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    flach = trimesh.creation.box(extents=(20.0, 20.0, 5.0))
    hoch = trimesh.creation.box(extents=(20.0, 20.0, 30.0))
    objekte = [
        SceneObject(id="A", name="A", mesh=MeshData.of(flach)),
        SceneObject(id="B", name="B", mesh=MeshData.of(hoch)),
    ]
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    run = dialog._plate_run(objekte, 0, tmp_path, "satz", setup)

    assert run.model_height == pytest.approx(30.0), "die höchste der Platte zählt"


def test_the_worker_hands_the_height_to_the_slicer(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Durchgereicht ist nicht gerufen.

    Das Feld an `PlateRun` nützt nichts, solange der Arbeiter es nicht
    weitergibt — und das ist genau die Stelle, an der eine Kette still endet.
    """
    from app.core.errors import OperationCancelled
    from app.core.export import handover
    from app.ui import print_settings_dialog as modul

    gesehen: list[object] = []

    def merken(*_args: object, **kwargs: object) -> object:
        gesehen.append(kwargs.get("model_height"))
        raise OperationCancelled()

    monkeypatch.setattr(modul.handover, "slice_model", merken)
    modell = tmp_path / "platte.3mf"
    modell.write_bytes(b"")
    lauf = modul.PlateRun(plate=0, model=modell, model_height=42.5)
    worker = modul._SliceWorker(
        [lauf],
        print_settings.resolve(profiles.make_profile()),
        profiles.make_profile(),
        handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca"),
    )

    worker.run()

    assert gesehen == [42.5], "die Höhe kam beim Slicer nicht an"


def test_a_stale_reason_leaves_the_state_line(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Ein Grund, der nicht mehr gilt, muss weichen.

    Nach dem Wechsel von der Orca-Familie auf PrusaSlicer stand weiter
    „Dieser Slicer braucht ein Druckerprofil“ da, während der Knopf schon
    frei war — ein Widerspruch auf demselben Bildschirm. Der Schutz, der
    ein *Ergebnis* vor dem Überschreiben bewahrt, deckte versehentlich auch
    einen veralteten *Grund* (Handlauf 3d-druck-55, 30.08.2026).
    """
    dialog._slicer_path = tmp_path / "elegoo-slicer.exe"
    dialog._needs_profiles = True
    dialog._profiles_pending = False
    dialog.machine_choice.clear()
    dialog._show_slicer_state()
    assert dialog.state.text(), "erst muss der Grund dastehen"

    # Wechsel auf einen Slicer ohne Profilpflicht
    dialog._needs_profiles = False
    dialog._slicer_path = tmp_path / "prusa-slicer.exe"
    dialog._show_slicer_state()

    assert dialog.slice_button.isEnabled(), "ohne Profilpflicht ist der Knopf frei"
    assert not dialog.state.text(), f"der alte Grund stand noch da: {dialog.state.text()!r}"


def test_a_result_survives_a_state_refresh(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Die Gegenrichtung: Ein Ergebnis darf dabei nicht mitgerissen werden.

    Die Zeile trägt zweierlei, und nur das eine ist alt geworden.
    """
    dialog._slicer_path = tmp_path / "prusa-slicer.exe"
    dialog._needs_profiles = False
    dialog.state.setText("Druckzeit: 18 min · Material: 4,7 g")

    dialog._show_slicer_state()

    assert dialog.state.text() == "Druckzeit: 18 min · Material: 4,7 g"


# --- Was der Kundenweg am Dialog gefunden hat (D13) ---------------------------------


@pytest.mark.parametrize("screen", ["this", "full"])
def test_the_dialog_grows_when_the_profile_section_opens_itself(
    qt_app: QApplication,
    session: Session,
    tmp_path: Path,
    screen: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die nachgereichte Klappe darf die Felder darüber nicht stauchen.

    Dieselbe Familie wie ``first_run._grow_to_content`` (Robert, 26.08.2026:
    Auswahlfelder auf 16 von 28 Punkten): Der Dialog steht auf seiner
    Aufmachgröße, und wenn ``_open_slicer_section`` Sekunden später vier
    Profilzeilen einblendet, wird der Fehlbetrag aus dem oberen Bereich
    gepresst. Gemessen an der Kundenfahrt vom 30.08.2026 (Bild 2 gegen 1).

    **Er wächst, soweit der Bildschirm reicht.** Auf dem Runner unter macOS
    stand er schon auf der vollen nutzbaren Höhe (768 Punkte), und „größer als
    vorher" war dort keine Frage an den Dialog, sondern an den Bildschirm.
    ``full`` stellt genau diesen Bildschirm nach: nutzbar ist, was der Dialog
    beim Aufmachen schon einnimmt.
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    dialog._slicer_path = tmp_path / "orca-slicer.exe"
    dialog.slicer_box.setVisible(True)
    # **Mit Zeilen, die sich einblenden.** Seit RM-514 steht im Kasten nur,
    # was eine Wahl ist; ohne gefundene Profile bliebe er leer, und es gäbe
    # nichts, wofür der Dialog wachsen müsste. Zwei Zeilen wie nach einer
    # nachgereichten Profilsuche.
    for choice, (title, path) in (
        (dialog.machine_choice, ("Orca Drucker 0.4 nozzle", "m.json")),
        (dialog.process_choice, ("0.20mm Standard", "p.json")),
    ):
        choice.blockSignals(True)
        choice.addItem(title, path)
        choice.blockSignals(False)
    dialog._show_profile_rows()
    dialog.resize(dialog.sizeHint())
    # **Gezeigt, sonst misst die zweite Zusicherung nichts.** Vor dem ersten
    # Anzeigen hat kein Widget eine gelegte Höhe: Das Feld meldete 0, und
    # „0 >= 23" ist kein Befund über Stauchung, sondern über ein Layout, das
    # es noch nicht gibt (dieselbe Falle wie `isVisible` vor dem Anzeigen).
    dialog.show()
    # Gemessen wird gesammelt im nächsten Umlauf (``_queue_refit``): Ein
    # einzelnes ``processEvents`` sah die Anfangsgröße noch nicht, und das
    # Aufklappen ging in der noch wartenden Anfangsmessung auf.
    for _ in range(8):
        qt_app.processEvents()
    assert dialog._content_height.initial_fit_done
    # **Oben am Schirm**, sonst misst „soweit der Bildschirm reicht“ die Lage:
    # Ausdrückliches Klappen hält den Anker (RM-487) und wächst nur bis zum
    # unteren Rand unter ihm. Mit echten Schriften stand der Dialog tiefer, als
    # die Rechnung unten annimmt, und blieb sechs Punkte darunter.
    area = dialog.screen().availableGeometry()
    dialog.move(area.topLeft())
    for _ in range(4):
        qt_app.processEvents()
    before = dialog.height()
    field = dialog._editors["layers.layer_height"]
    tall_enough = field.sizeHint().height()
    real = dialog.screen().availableGeometry()
    if screen == "full":
        tight = QRect(real.x(), real.y(), real.width(), before + SCREEN_MARGIN)
        monkeypatch.setattr(
            dialog, "screen", lambda: SimpleNamespace(availableGeometry=lambda: QRect(tight))
        )
    room = dialog.screen().availableGeometry().height() - SCREEN_MARGIN

    dialog._open_slicer_section()
    for _ in range(8):
        qt_app.processEvents()

    wanted = min(dialog.sizeHint().height(), room)
    assert dialog.height() >= max(before, wanted), (
        f"der Dialog wächst mit der aufgeklappten Auswahl bis {wanted}, steht auf {dialog.height()}"
    )
    assert dialog.height() > before or before >= room, "Platz war da, gewachsen ist er nicht"
    assert field.height() >= tall_enough, "und die Felder darüber behalten ihre Höhe"


def test_the_upper_fields_keep_their_height_when_the_dialog_cannot_grow(
    qt_app: QApplication, session: Session, tmp_path: Path
) -> None:
    """Und wenn er nicht wachsen *kann*, geben die Felder trotzdem nicht nach.

    Auf macOS ARM ist genau das eingetreten (08.09.2026): Der Dialog wuchs,
    aber nicht genug, und das Feld darüber fiel von 26 auf 22 Punkte. Der Test
    darüber sah es hier nie, weil dieser Bildschirm den Dialog wachsen lässt,
    soweit er will — der Fall entsteht also, indem ihm die Höhe genommen wird,
    wie sie ihm dort ein kleinerer Bildschirm nimmt.
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    dialog._slicer_path = tmp_path / "orca-slicer.exe"
    dialog.slicer_box.setVisible(True)
    dialog.resize(dialog.sizeHint())
    dialog.show()
    qt_app.processEvents()
    field = dialog._editors["layers.layer_height"]
    tall_enough = field.sizeHint().height()
    dialog.setMaximumHeight(dialog.height())

    dialog._open_slicer_section()
    qt_app.processEvents()

    assert field.height() >= tall_enough, (
        f"gestaucht: {field.height()} statt {tall_enough} — der Fehlbetrag der "
        "nachgereichten Klappe darf nicht aus dem oberen Bereich kommen"
    )


def test_every_group_of_the_depth_can_be_reached_at_the_default_width(
    qt_app: QApplication, session: Session
) -> None:
    """Acht Gruppen, und bei der Vorgabebreite waren zwei davon unerreichbar.

    Die Kundenfahrt vom 30.08.2026 (Bild 3) zeigte die Reiterleiste
    abgeschnitten — „Geschwindigkeit | S…", und *Haftung, Rückzug, Filament*
    stand nirgends. Qts Ausweg dafür sind Rollknöpfe, und die sind unter
    unserem Stylesheet blanke Flächen: gemessen je 16 auf 22 Punkte in einer
    einzigen Farbe, ein ``image:`` an ihnen greift nicht. Wer nichts zum
    Rollen sieht, hat die achte Gruppe nicht.

    **Geprüft wird die Bauart, nicht die Pixelzahl.** Ob die Leiste an einer
    bestimmten Breite passt, hängt an der Schriftmetrik, und die gibt es
    offscreen nicht (der Bildschirm ist dort 800 Punkte breit, jede Familie
    liefert dieselbe synthetische Metrik). Zugesichert ist deshalb, was den
    Fall unabhängig davon ausschließt: kein Rollen, gekürzte Beschriftungen
    statt abgeschnittener, der volle Name im Tooltip, und ein Dialog, der
    sich beim Aufklappen die Breite der Leiste nimmt, soweit der Bildschirm
    sie hergibt.
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog.resize(dialog.sizeHint())
    narrow = dialog.width()
    dialog.tabs_toggle.setChecked(True)
    qt_app.processEvents()
    bar = dialog.tabs.tabBar()

    assert dialog.tabs.count() == len(GROUPS), "sonst prüft dieser Test die falsche Leiste"
    assert not bar.usesScrollButtons(), "die Rollknöpfe sind blank — sie sind kein Ausweg"
    assert bar.elideMode() == Qt.TextElideMode.ElideRight, "gekürzt statt abgeschnitten"
    for index in range(dialog.tabs.count()):
        assert dialog.tabs.tabToolTip(index) == dialog.tabs.tabText(index), (
            "eine gekürzte Beschriftung braucht ihren vollen Namen daneben"
        )

    screen = dialog.screen()
    deckel = screen.availableGeometry().width() - 48
    room = dialog._room_for_tabs()
    assert room >= min(bar.sizeHint().width(), deckel), (
        f"die Rechnung deckt die Leiste: {room} px für {bar.sizeHint().width()} px Bedarf"
    )
    assert room <= deckel, "und sie bleibt auf dem Bildschirm"
    assert dialog.width() >= min(room, narrow), "gewachsen ist der Dialog auch"


def test_the_colour_is_chosen_at_the_spool_not_on_the_front_page() -> None:
    """Zwei Orte für dieselbe Farbe, und einer davon wusste es besser.

    Die Vorderseite trug ein Farbfeld, das für das **ganze** Teil galt; die
    Spule trägt ihre eigene, und `handover` überschreibt damit den Feldwert,
    sobald es einen Slot gibt. Wer beides sieht, muss raten, welches zählt —
    „die materialauswahl und farbe sind sinnlos, da wir ja nach den filamenten
    gehen" (Robert, 30.08.2026).

    Der Wert selbst bleibt im Modell: Ein Teil ganz ohne Spule hat sonst keine
    Farbe für den Slicer (`test_the_colour_reaches_the_slicer`). Er ist der
    Rückfall und gehört damit nach hinten, nicht nach vorn.
    """
    colour = next(field for field in FIELDS if field.path == "filament.colour")

    assert not colour.front, "die Farbe kommt von der Spule, nicht aus der Kopfzeile"
    assert colour.group in GROUPS, "als Rückfall bleibt sie erreichbar"


def test_the_header_shows_where_the_material_comes_from(
    qt_app: QApplication, session: Session
) -> None:
    """Keine zweite Wahl neben den Spulen — die Kopfzeile *berichtet*.

    „das material kommt ja auch aus dem filament" (Robert, 30.08.2026): Wer
    hier ein Material einstellen konnte, stellte etwas ein, das die Spule
    schon sagt. Ohne Spule steht die Projektvorgabe da, und zwar mit ihrer
    Herkunft — ein Wert ohne Herkunft ist eine Behauptung.
    """
    dialog = PrintSettingsDialog(session, UiSettings())

    assert not hasattr(dialog, "material_choice"), "die zweite Wahl ist weg"
    text = dialog.material_state.text()
    assert str(tr("Projektvorgabe")) in text, text
    assert str(tr("PLA")) in text or "PLA" in text, text


def test_the_header_names_every_material_the_spools_bring(
    qt_app: QApplication, session: Session
) -> None:
    """Mehrere Spulen heißen mehrere Materialien — dann stehen sie alle da.

    Ein Gehäuse in PETG mit einem Schriftzug in PLA ist der Fall, an dem die
    Slot-Entscheidung gemessen wurde. Die Anzeige darf ihn nicht auf eines der
    beiden verkürzen: Der Kunde soll sehen, was er eingelegt hat.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import MaterialSlot, Scene

    session.last_result = EvaluationResult(
        scene=Scene(
            objects={
                "obj_1": SceneObject(
                    id="obj_1",
                    name="Zweifarbig",
                    mesh=MeshData(
                        raw=trimesh.creation.box(),
                        slots=tuple(0 if index < 6 else 1 for index in range(12)),
                    ),
                    material_slots=[
                        MaterialSlot(
                            index=0, name="Gehäuse", colour=(0.0, 0.0, 0.0), material_type="PETG"
                        ),
                        MaterialSlot(
                            index=1, name="Schrift", colour=(1.0, 1.0, 1.0), material_type="PLA"
                        ),
                    ],
                )
            }
        )
    )
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog.refresh_materials()

    text = dialog.material_state.text()
    assert "PETG" in text and "PLA" in text, text
    assert str(tr("Projektvorgabe")) not in text, "mit Spulen ist die Vorgabe nicht die Quelle"
    assert "Spule" in dialog.material_state.toolTip()


def test_the_material_line_leads_to_where_the_choice_is(
    qt_app: QApplication, session: Session
) -> None:
    """Anzeige mit Weg, nicht Anzeige statt Weg.

    Ein Label, das sagt „das Material kommt aus der Spule", und den Kunden
    dann suchen lässt, wo Spulen gewählt werden, ist die halbe Antwort. Der
    Knopf daneben führt dorthin — das Fenster klappt den Abschnitt auf und
    lässt ihn aufleuchten.
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    seen: list[bool] = []
    dialog.filamentsRequested.connect(lambda: seen.append(True))

    dialog.material_link.click()

    assert seen == [True], "der Weg zum Filamentwähler geht vom Dialog aus"
    assert dialog.material_link.toolTip(), "und er sagt vorher, wohin er führt"


def test_the_portuguese_header_keeps_every_control_visible_at_manual_width(
    qt_app: QApplication, session: Session
) -> None:
    """Die 520-Pixel-Aufnahme darf Kopfwerte und Handlungen nicht abschneiden."""
    from app.i18n import set_language

    set_language("pt")
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog.show_materials(("PLA Branco · #FFFFFF", "TPU 95A Preto · #000000"))
    dialog.resize(560, 720)
    dialog.show()
    qt_app.processEvents()

    controls = (
        dialog.quality,
        dialog.printer_choice,
        dialog.material_state,
        dialog.material_link,
        dialog.share_settings,
    )
    right = dialog.contentsRect().right()
    assert all(control.geometry().right() <= right for control in controls)
    assert dialog.quality.fontMetrics().horizontalAdvance(dialog.quality.currentText()) + 40 <= (
        dialog.quality.width()
    )
    assert (
        dialog.printer_choice.fontMetrics().horizontalAdvance(dialog.printer_choice.currentText())
        + 40
        <= dialog.printer_choice.width()
    )
    assert dialog.material_link.sizeHint().width() <= dialog.material_link.width()
    assert dialog.share_settings.sizeHint().width() <= dialog.share_settings.width()
    assert dialog.material_state.wordWrap(), "nur die lange Filamentliste darf umbrechen"

    # Die Folge der Abhängigkeiten: Drucker, Filamente, Qualität, und die
    # Mitgabe steht bei der Übergabe unten — gemessen im Dialog, denn die
    # Mitgabe hat einen anderen Elternteil als die Kopfzeile.
    def top(widget: QWidget) -> int:
        return widget.mapTo(dialog, QPoint(0, 0)).y()

    assert top(dialog.printer_choice) < top(dialog.material_state) < top(dialog.quality)
    assert top(dialog.quality) < top(dialog.share_settings)


def test_the_print_dialog_asks_in_the_order_its_answers_depend_on(
    dialog: PrintSettingsDialog,
) -> None:
    """Was eine andere Angabe bestimmt, steht vor ihr.

    Robert, 29.09.2026: „der Slicer unten und den Drucker oben, obwohl der
    Drucker vom Slicer abhängig ist, ist nicht gut". Der Slicer liefert die
    Druckerprofile, der Drucker die Düse, die Platte die Slots der
    Filamentzeile, Drucker und Stufe den Prozess, der Prozess die Grundlage
    der Werte — und die Mitgabe gilt der Übergabe, also steht sie bei deren
    Knöpfen.

    Geprüft an der Bauart (Zeile im Formular, Platz im Rollbereich) und nicht
    an Bildpunkten: Die Plattenzeile ist mit einer Platte verborgen, ihr Platz
    in der Folge bleibt. Die Slicerzeile steht immer da, ohne Slicer mit
    „Programm wählen …“ allein (RM-601).
    """
    from PySide6.QtWidgets import QFormLayout

    head = next(
        form
        for form in dialog.findChildren(QFormLayout)
        if form.getWidgetPosition(dialog.printer_choice)[0] >= 0
    )

    def row(widget: QWidget) -> int:
        number = head.getWidgetPosition(widget)[0]
        assert number >= 0, f"{widget.objectName() or type(widget).__name__} fehlt in der Kopfzeile"
        return number

    rows = [
        row(dialog.slicer_label),
        row(dialog.printer_choice),
        row(dialog.adopt_printer.parentWidget()),
        row(dialog.nozzle_label),
        row(dialog.plate_label),
        row(dialog.filament_label),
        row(dialog.quality_label),
    ]
    assert rows == sorted(rows) and len(set(rows)) == len(rows), rows

    content = dialog._scroll.widget().layout()
    assert content is not None

    def place(target: object) -> int:
        for index in range(content.count()):
            item = content.itemAt(index)
            if item is None:
                continue
            if item.layout() is target:
                return index
            widget = item.widget()
            if widget is not None and (
                widget is target or (isinstance(target, QWidget) and widget.isAncestorOf(target))
            ):
                return index
        raise AssertionError(f"{target} steht nicht im Rollbereich")

    order = [
        place(head),
        place(dialog.slicer_box),
        place(dialog.foundation_note),
        place(dialog.front_box),
        place(dialog.tabs_box),
        place(dialog.advice_box),
    ]
    assert order == sorted(order) and len(set(order)) == len(order), order
    # Düsenzahl und Suche stehen hinter „Weitere Einstellungen" (RM-514), die
    # Mitgabe außerhalb des Rollbereichs bei den Knöpfen der Übergabe.
    assert dialog.tabs_box.isAncestorOf(dialog.search)
    assert dialog.tabs_box.isAncestorOf(dialog.nozzle_count)
    assert not dialog._scroll.isAncestorOf(dialog.share_settings)
    outer = dialog.layout()
    assert outer is not None
    below = [outer.itemAt(index).widget() for index in range(outer.count())]
    holder = next(
        widget
        for widget in below
        if widget is not None and widget.isAncestorOf(dialog.share_settings)
    )
    assert below.index(dialog._scroll) < below.index(holder) < below.index(dialog._buttons)


def test_the_header_names_the_material_a_body_really_prints_in(
    qt_app: QApplication, session: Session
) -> None:
    """„warum aber noch material pla falls einer unterschiedliche materialien
    hat" (Robert, 30.08.2026) — und er hatte recht.

    Ein Körper trägt sein Material auch **ohne** Spule: ``SceneObject.material``
    ist der Weg, über den eine TPU-Dichtung im PETG-Gehäuse gerechnet wird
    (§12). Die Anzeige las nur die Spulen und schrieb daneben unbeirrt „PLA —
    Projektvorgabe" — ein Material, in dem kein einziger Körper gedruckt wird.

    Zwei Körper aus zwei Materialien stehen beide da; gefragt wird dasselbe,
    was auch die Toleranz fragt (``profiles.for_object``), also eine Quelle
    und nicht zwei.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    def body(name: str, material: str) -> SceneObject:
        mesh = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        return SceneObject(id=name, name=name, mesh=MeshData.of(mesh), material=material)

    dialog = PrintSettingsDialog(session, UiSettings())

    dialog.show_materials(dialog._materials_of([body("obj_1", "tpu-95a")]))
    single = dialog.material_state.text()
    assert "TPU" in single, single
    assert str(tr("Projektvorgabe")) not in single, "es gibt ein Material, also keine Vorgabe"

    mixed = dialog._materials_of([body("obj_1", "petg"), body("obj_2", "tpu-95a")])
    dialog.show_materials(mixed)
    text = dialog.material_state.text()
    assert "PETG" in text and "TPU" in text, text

    # Und die zweite Spule desselben Körpers: Für die Toleranz entscheidet
    # Slot 0, gedruckt wird der Schriftzug daneben trotzdem — wer wissen will,
    # was er einlegen muss, will beide sehen.
    from app.core.types import MaterialSlot

    painted_source = body("obj_1", "")
    painted = replace(
        painted_source,
        mesh=MeshData(
            raw=painted_source.mesh.raw,
            slots=tuple(0 if index < 6 else 1 for index in range(12)),
        ),
        material=None,
        material_slots=[
            MaterialSlot(index=0, name="Gehäuse", material_type="PETG"),
            MaterialSlot(index=1, name="Schrift", material_type="PLA"),
        ],
    )
    dialog.show_materials(dialog._materials_of([painted]))
    both = dialog.material_state.text()
    assert "PETG" in both and "PLA" in both, both


def test_a_body_without_anything_falls_back_and_says_so(
    qt_app: QApplication, session: Session
) -> None:
    """Der häufigste Fall überhaupt: eingelesene Datei, kein Material, keine
    Spule. Dann gilt die Projektvorgabe — und sie nennt sich beim Namen,
    damit niemand sie für eine Messung hält."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    mesh = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    plain = SceneObject(id="obj_1", name="Import", mesh=MeshData.of(mesh))
    dialog = PrintSettingsDialog(session, UiSettings())

    dialog.show_materials(dialog._materials_of([plain]))

    assert str(tr("Projektvorgabe")) in dialog.material_state.text()


# --- Suchen statt scrollen (D11) ----------------------------------------------------


def test_the_search_finds_a_setting_by_its_words(qt_app: QApplication, session: Session) -> None:
    """56 Einstellungen in zehn Gruppen, und die Geste, die jeder Slicer hat.

    Gesucht wird über das, was der Kunde liest: Titel, Einheit, Gruppenname
    und den Satz darunter. Der **Satz** gehört ausdrücklich dazu, und das ist
    gemessen: „Überhänge" steht in drei note-Sätzen und in keinem einzigen
    Titel. Wer das Wort kennt, sucht danach — und fände ohne den Satz nichts.

    Gefaltet wie in der Befehlspalette, damit „aushoehlen" und „Aushöhlen"
    dasselbe finden.
    """
    dialog = PrintSettingsDialog(session, UiSettings())

    assert dialog.search_hits("Fülldichte") == ["infill.density"]
    assert dialog.search_hits("fuelldichte") == ["infill.density"], "gefaltet gesucht"
    assert "adhesion.brim_width" in dialog.search_hits("brim"), "der Slicer-Begriff steht im Titel"

    aus_dem_satz = dialog.search_hits("Überhänge")
    assert "shell.outer_wall_first" in aus_dem_satz, "das Wort steht nur im Satz darunter"
    assert not any("überhäng" in str(field.title).casefold() for field in FIELDS), (
        "sonst prüft diese Zeile den Titel und nicht den Satz"
    )

    # Und der Gruppenname trägt: „Wo sind die Stützen-Einstellungen" ist die
    # Frage, mit der ein Slicer-Kunde ankommt — sie findet alle sieben.
    stuetzen = dialog.search_hits(group_title("support"))
    assert {field.path for field in FIELDS if field.group == "support"} <= set(stuetzen)

    assert dialog.search_hits("") == [], "eine leere Suche hebt nichts"
    assert dialog.search_hits("gibtesnicht") == []


def test_the_search_also_knows_the_name_from_the_slicer(
    qt_app: QApplication, session: Session
) -> None:
    """Wer aus einem Slicer kommt, sucht unter dem Wort, das er dort gelernt hat.

    Die Wandzahl heißt bei PrusaSlicer ``perimeters``, bei Orca ``wall_loops``
    und bei Cura ``wall_line_count``. Keines der drei steht im Dialog — und
    das ist **gemessen**, nicht angenommen: Die Zusicherung unten prüft für
    jedes, dass es in Titel, Satz und Gruppenname nicht vorkommt. Ohne sie
    prüfte dieser Test die Wortsuche noch einmal und nicht die Schlüssel.

    Die Namen kommen aus derselben Tabelle, mit der die Übergabe schreibt.
    Ein zweites Verzeichnis wäre eines, das altert, sobald ein Slicer einen
    Schlüssel umbenennt — deshalb steht hier `keys_for` und keine Liste.
    """
    from app.core.export.slicer_keys import keys_for

    dialog = PrintSettingsDialog(session, UiSettings())

    for fremd in ("perimeters", "wall_loops", "wall_line_count"):
        lesbar = " ".join(
            " ".join((str(f.title), str(f.note), group_title(f.group))) for f in FIELDS
        )
        assert fremd.casefold() not in lesbar.casefold(), (
            f"„{fremd}“ steht im lesbaren Text — dann prüft diese Zeile die Wortsuche"
        )
        assert "shell.wall_count" in dialog.search_hits(fremd), (
            f"„{fremd}“ muss die Wandzahl finden"
        )

    # Und die Zuordnung stimmt in die andere Richtung: Was der Dialog findet,
    # steht auch wirklich in der Übergabetabelle dieses Feldes.
    assert set(keys_for("shell.wall_count")) == {"perimeters", "wall_loops", "wall_line_count"}

    # Ein Schlüssel darf nicht das halbe Fenster treffen — dieselbe Grenze, an
    # der die Einheit „mm" gescheitert ist (22 von 56). Gemessen ist der
    # breiteste `support_material` mit sieben: sechs Stützzeilen und die
    # Bahnbreite, die seit den Rollenbreiten auch
    # `support_material_extrusion_width` schreibt (3e501baaf).
    breiteste = max(
        len(dialog.search_hits(schluessel)) for feld in FIELDS for schluessel in keys_for(feld.path)
    )
    assert breiteste <= 7, f"ein Schlüssel trifft {breiteste} von {len(FIELDS)} Zeilen"

    # Und die Abdeckung: Ohne sie wäre der Test grün, wenn die Tabelle
    # zusammenschrumpft — ein Filter über eine leere Menge findet nie etwas.
    mit_namen = [f for f in FIELDS if keys_for(f.path)]
    assert len(mit_namen) == len(FIELDS), (
        f"nur {len(mit_namen)} von {len(FIELDS)} Feldern haben einen Slicer-Namen"
    )


def test_the_search_reads_an_underscore_as_a_space(qt_app: QApplication, session: Session) -> None:
    """„wall loops" ist derselbe Schlüssel wie ``wall_loops``.

    Der Schlüssel steht mit Unterstrich in der Tabelle, gelesen und
    ausgesprochen wird er mit Leerzeichen — und wer ihn aus einem Forumsbeitrag
    abschreibt, tippt mal das eine, mal das andere. Gefunden hat bis hierhin
    nur die Schreibweise der Tabelle; die andere gab **nichts** zurück, obwohl
    die Zeile danebensteht.
    """
    dialog = PrintSettingsDialog(session, UiSettings())

    mit_strich = dialog.search_hits("wall_loops")
    assert "shell.wall_count" in mit_strich, "die Schreibweise der Tabelle muss weiter finden"
    assert dialog.search_hits("wall loops") == mit_strich, (
        "mit Leerzeichen getippt findet die Suche etwas anderes als mit Unterstrich"
    )
    assert dialog.search_hits("support material") == dialog.search_hits("support_material")


def test_the_search_lifts_the_hit_instead_of_hiding_the_rest(
    qt_app: QApplication, session: Session
) -> None:
    """Heben, nicht filtern — die Slicer-Antwort, nicht die CAD-Antwort.

    Eine Liste, die sich beim Tippen umbaut, nimmt dem Kunden die Übersicht,
    die er gerade gewonnen hat: Wer „Temperatur" sucht, will sehen, **wo** sie
    steht, um beim nächsten Mal direkt hinzugehen. Also bleibt jede Gruppe
    stehen, die Klappe geht auf, der Reiter wechselt, und der Treffer wird
    hervorgehoben.
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.tabs_toggle is not None and not dialog.tabs_toggle.isChecked()

    # „Bügeln" liegt hinter der Klappe und trifft genau eine Zeile — an einem
    # Begriff mit acht Treffern (etwa „Bett", das in fünf note-Sätzen steht)
    # prüfte der Test die Reihenfolge statt das Heben.
    assert dialog.search_hits("Bügeln") == ["shell.ironing"]

    dialog.jump_to("Bügeln")
    qt_app.processEvents()

    assert dialog.tabs_toggle.isChecked(), "die Tiefe klappt auf, wenn der Treffer dort liegt"
    assert dialog.tabs.count() == len(GROUPS), "keine Gruppe ist verschwunden"
    assert dialog.tabs.tabText(dialog.tabs.currentIndex()) == group_title("shell")
    assert dialog.highlighted() == "shell.ironing", dialog.highlighted()


def test_the_search_walks_through_its_hits_and_counts_them(
    qt_app: QApplication, session: Session
) -> None:
    """Vier Treffer heißen vier — und ein zweites Drücken führt zum nächsten.

    Ohne Zähler weiß niemand, ob er alles gesehen hat; ohne Weitergehen ist
    der zweite Treffer unerreichbar, und beides zusammen ist die Geste, die
    ein Slicer-Kunde mitbringt.
    """
    dialog = PrintSettingsDialog(session, UiSettings())

    # „Bahnbreite“ ist der Feldname in Einstellungen, Befunden und Handbuch
    # (oberflaeche.md); er steht in mehreren Zeilen.
    hits = dialog.search_hits("Bahnbreite")
    assert len(hits) >= 2, hits

    dialog.jump_to("Bahnbreite")
    first = dialog.highlighted()
    dialog.jump_to("Bahnbreite")
    second = dialog.highlighted()

    assert first != second, "das zweite Drücken führt weiter"
    assert {first, second} <= set(hits)
    # Der ganze Satz, nicht eine Ziffer darin: „2" steht auch in „1 von 2",
    # und genau daran blieb die Mutationsprobe zuerst grün.
    assert dialog.search_state.text() == f"2 von {len(hits)}", dialog.search_state.text()


def test_the_search_field_sits_where_it_can_be_seen(qt_app: QApplication, session: Session) -> None:
    """Über den Reitern von „Weitere Einstellungen", und die Klappe nennt es.

    Vorn stehen seit RM-514 nur Fülldichte und Stützen; gesucht wird, was
    dahinter liegt. Damit das Suchfeld nicht nur findet, wer den Bereich
    schon offen hat, nennt die zugeklappte Zeile es zuerst — und es steht
    über allen Reitern, nicht in einem davon.
    """
    from PySide6.QtWidgets import QLabel

    dialog = PrintSettingsDialog(session, UiSettings())

    assert dialog.tabs_box.isAncestorOf(dialog.search)
    assert not dialog.tabs.isAncestorOf(dialog.search), "über den Reitern, nicht in einem"
    summary = next(
        label
        for label in dialog.tabs_box.findChildren(QLabel)
        if label.objectName() == "sectionSummary"
    )
    assert summary.text().startswith("Suche"), summary.text()
    assert dialog.search.placeholderText(), "es sagt, wofür es da ist"
    dialog.tabs_toggle.setChecked(True)
    assert dialog.search.isVisibleTo(dialog)


def test_the_dialog_uses_one_form_of_section(qt_app: QApplication, session: Session) -> None:
    """Zwei Abschnittsformen im selben Dialog sind eine zu viel (Befund B9).

    „Das Wichtigste" und „Was dieses Teil verlangt" standen als gerahmte
    `QGroupBox` mit eingelassenem Titel — die Qt-Form von 2010 — über den
    rahmenlosen Aufklappern „Weitere Einstellungen" und „Profile des Slicers".
    Zwei Formen heißen zwei Rhythmen: Der Blick sucht die Gliederung, statt
    sie zu bekommen.

    Gewonnen hat die Aufklapper-Familie, und zwar nicht aus Geschmack: Sie
    kann, was die andere nicht kann (§2.5 verlangt zuklappbare Abschnitte),
    und dieselbe Form trägt links im Fenster schon Objektbaum, Parameter und
    Verlauf. Der Kunde lernt einen Griff und nicht zwei.
    """
    dialog = PrintSettingsDialog(session, UiSettings())

    kaesten = [
        box
        for box in dialog.findChildren(QGroupBox)
        if box.window() is dialog and box.title().strip()
    ]

    assert not kaesten, f"noch gerahmt: {[box.title() for box in kaesten]}"
    # Vorn stehen zwei Zeilen ohne Klappe (RM-514); was sich klappen lässt,
    # trägt dieselbe Kopfzeile.
    assert dialog.front_toggle is None
    assert (
        dialog.advice_toggle is not None and dialog.advice_toggle.objectName() == "sectionHeading"
    )


def test_the_front_shows_density_and_supports_and_hides_the_rest(
    qt_app: QApplication, session: Session
) -> None:
    """Vorn Fülldichte und Stützen, der Rest hinter „Weitere Einstellungen" (RM-514).

    Beim Öffnen zeigte der Dialog 34 Bedienelemente. Schichthöhe, Wände,
    Füllmuster, Düsen- und Betttemperatur und die Düsenzahl kommen aus
    Drucker, Filament und Qualität; sie stehen zugeklappt dahinter.
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.tabs_toggle is not None and not dialog.tabs_toggle.isChecked()

    for path in ("infill.density", "support.style"):
        assert dialog._editors[path].isVisibleTo(dialog), path
    behind = (
        "layers.layer_height",
        "shell.wall_count",
        "infill.pattern",
        "temperature.nozzle",
        "temperature.bed",
    )
    for path in behind:
        assert dialog.tabs_box.isAncestorOf(dialog._editors[path]), path
        assert not dialog._editors[path].isVisibleTo(dialog), path
    assert not dialog.nozzle_count.isVisibleTo(dialog)
    assert dialog.nozzle_choice.isVisibleTo(dialog), "der Durchmesser bleibt beim Drucker"


def test_every_form_row_of_a_dialog_starts_at_one_line(
    qt_app: QApplication, session: Session
) -> None:
    """Ein Dialog, eine Beschriftungsspalte (Befund B8/B11).

    Ein `QFormLayout` rechnet seine Spalte für sich. Wo zwei davon in einem
    Dialog stehen — und das tun sie hier: Vorderseite, acht Gruppen der Tiefe,
    Profilzuordnung —, beginnen die Felder an verschiedenen Stellen. Gemessen
    am gebauten Dialog waren es **zehn** verschiedene linke Kanten von 11 bis
    226 Punkten; im Einstellungsdialog 148 oben gegen 70 unten.

    Der Blick sucht dann in jeder Zeile neu, wo der Wert anfängt. Angeglichen
    wird nach links, nicht nach rechts: Die Feldbreiten sind eine getroffene
    Entscheidung (`_editor` — „keines breiter, als sein Wert ist"), die
    Startlinie ist keine.
    """
    dialog = PrintSettingsDialog(session, UiSettings())
    dialog.tabs_toggle.setChecked(True)
    # Der Profilkasten mit Zeilen, wie nach einer Profilsuche, und offen.
    for choice, (title, path) in (
        (dialog.machine_choice, ("Orca Drucker 0.4 nozzle", "m.json")),
        (dialog.process_choice, ("0.20mm Standard", "p.json")),
    ):
        choice.blockSignals(True)
        choice.addItem(title, path)
        choice.blockSignals(False)
    dialog.slicer_box.setVisible(True)
    dialog._show_profile_rows()
    dialog._open_slicer_section()
    dialog.show()
    qt_app.processEvents()

    breiten: set[int] = set()
    reiterbreiten: set[int] = set()
    kastenbreiten: set[int] = set()
    kanten_je_block: list[set[int]] = []
    for form in dialog.findChildren(QFormLayout):
        block: set[int] = set()
        besitzer = form.parentWidget()
        im_reiter = besitzer is not None and dialog.tabs.isAncestorOf(besitzer)
        im_kasten = besitzer is not None and dialog.slicer_box.isAncestorOf(besitzer)
        for row in range(form.rowCount()):
            marke = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            feld = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if marke is None or feld is None:
                continue
            label, widget = marke.widget(), feld.widget()
            if widget is None or label is None or not widget.isVisibleTo(dialog):
                continue
            (reiterbreiten if im_reiter else kastenbreiten if im_kasten else breiten).add(
                label.width()
            )
            block.add(widget.mapTo(dialog, widget.rect().topLeft()).x())
        if block:
            kanten_je_block.append(block)

    assert kanten_je_block, "keine Formularzeile gefunden — dann prüft nichts darunter"
    # **Eine Beschriftungsspalte, geprüft an ihrer Breite.** Die absolute
    # Startlinie darf sich zwischen Abschnitten um deren Einrückung
    # unterscheiden — ein Reiterinhalt ist ein eigener Kasten, und elf Punkte
    # Innenabstand sind Gliederung, kein Sprung. Was nicht sein darf, ist eine
    # zweite Spaltenbreite: Sie entsteht, sobald ein Formular seine Beschriftung
    # allein ausrechnet, und genau daran begannen die Felder an zehn Stellen.
    #
    # **Reiter und Profilkasten sind dabei je ein Kasten für sich**
    # (``align_forms(apart=…)``): Ihre Zeilen teilen eine Spalte, der übrige
    # Dialog eine eigene. Die längste Beschriftung eines verborgenen Reiters
    # oder des zugeklappten Profilkastens zog sonst die Vorderseite auf 170
    # Punkte, wo 120 reichen.
    assert len(breiten) == 1, f"{len(breiten)} Beschriftungsbreiten: {sorted(breiten)}"
    assert len(reiterbreiten) == 1, f"{len(reiterbreiten)} in den Reitern: {sorted(reiterbreiten)}"
    assert len(kastenbreiten) == 1, f"{len(kastenbreiten)} im Profilkasten: {sorted(kastenbreiten)}"
    for block in kanten_je_block:
        assert len(block) == 1, f"in einem Block springen die Kanten: {sorted(block)}"


def test_every_group_holds_one_subject(qt_app: QApplication, session: Session) -> None:
    """Drei Themen in einem Gruppennamen sind kein Titel (Befund B10).

    „Haftung, Rückzug, Filament" hieß der achte Reiter, und er trug sechzehn
    Felder — fast dreimal so viele wie der Schnitt, und mehr als die drei
    kleinsten Gruppen zusammen. Wer den Rückzug sucht, liest erst eine
    Aufzählung und dann sechzehn Zeilen.

    Die Teilung stand schon im Datenmodell: Jedes Feld trägt seinen Bereich im
    Pfad (`adhesion.brim_width`, `retraction.z_hop`, `filament.density`), und
    vierzig von sechsundfünfzig Feldern lagen längst in dem Reiter, den ihr
    Pfad nennt. Nur die sechzehn der Sammelgruppe wichen ab.

    Geprüft wird deshalb die Deckung selbst: Der Reiter eines Feldes ist sein
    Bereich, nicht eine zweite Zuordnung daneben, die auseinanderlaufen kann.
    """
    from app.ui.print_settings_dialog import GROUPS

    abweichung = [
        f"{field.path} → {field.group}"
        for field in FIELDS
        if field.path.partition(".")[0] != field.group
    ]

    assert FIELDS, "ohne Felder prüft das hier nichts"
    assert not abweichung, f"Reiter und Bereich laufen auseinander: {abweichung}"
    assert "other" not in GROUPS, "die Sammelgruppe ist aufgelöst"

    groesste = max(sum(1 for f in FIELDS if f.group == g and not f.front) for g in GROUPS)
    assert groesste <= 9, f"die größte Gruppe trägt {groesste} Felder"


def test_the_spool_colour_is_big_enough_to_read(qt_app: QApplication) -> None:
    """Die Farbe steht als Überschrift, nicht als Fußnote (Befund B28).

    Der Dialog heißt „Druckeinstellungen — Gehäuse", und die Farbe daneben
    sagt, **welche** Spule gemeint ist. Sie war ein 14-Punkte-Quadrat in einem
    620 Punkte breiten Dialog — dieselbe Größe wie in einer Listenzeile, wo
    sie neben zwanzig Geschwistern steht und nur unterscheiden muss.

    **Geprüft wird die Rechnung, nicht das Bild.** Ob 14 Punkte zu klein sind,
    hängt an der Schriftgröße, und offscreen gibt es keine Schrift: Dort meldet
    auch die fette Überschrift 14 Punkte, und jede Pixelprüfung wäre in einer
    Lage grün, die es beim Kunden nicht gibt (`tests.md`). Zugesichert ist
    deshalb, was unabhängig davon gilt — das Feld ist so hoch wie seine Zeile
    und nie kleiner als das Listenmaß.
    """
    from PySide6.QtWidgets import QLabel

    from app.ui.filament_picker import SWATCH_PIXELS
    from app.ui.print_settings_dialog import swatch_size

    hoch = QLabel("Text")
    hoch.setFixedHeight(40)
    klein = QLabel("Text")
    klein.setFixedHeight(6)
    # Mit einer Schrift, deren Zeile unter dem Listenmaß bleibt: Offscreen
    # hat Windows keine Schrift und meldet 14 Punkte, der Mac hat eine und
    # meldet zwanzig — dann wäre „nie unter dem Listenmaß" dort nicht
    # prüfbar (Tag-Lauf 02.09.2026). Die Zusicherung hängt nicht an der
    # Schrift, also bekommt die Zeile eine, die sicher darunter liegt.
    tiny = klein.font()
    tiny.setPointSize(3)
    klein.setFont(tiny)

    assert swatch_size(hoch) == 40, "so hoch wie die Zeile"
    assert swatch_size(klein) == SWATCH_PIXELS, "aber nie unter dem Listenmaß"


def test_the_filament_dialog_uses_that_calculation() -> None:
    """Die Hälfte, die der Test darüber nicht prüfen kann.

    Er prüft die Rechnung an einem Widget bekannter Höhe — und bliebe grün,
    wenn der Dialog sie gar nicht ruft und wieder die Konstante setzt (die
    Mutation „im Dialog nicht benutzt" hat genau das gezeigt). Am Quelltext
    geprüft, weil die Pixelfrage offscreen nicht messbar ist; beide zusammen
    sichern den Weg.
    """
    import inspect

    from app.ui.print_settings_dialog import FilamentOverrideDialog

    quelle = inspect.getsource(FilamentOverrideDialog.__init__)

    assert "swatch_size(title)" in quelle, "die Überschrift gibt das Maß vor"
    assert "SWATCH_PIXELS, SWATCH_PIXELS" not in quelle, "und nicht mehr die Listenkonstante"


# --- Was die Datei mitnimmt ---------------------------------------------------------


def _shown_result(scene: SimpleNamespace) -> SimpleNamespace:
    """Ein Auswertungsergebnis als Attrappe, mit allem, was die Sitzung daran liest.

    ``Session.picture_first`` (KUNDE-14) fragt ``object_names`` und
    ``stopped_at``; eine Attrappe nur mit ``scene`` riss dort mit
    ``AttributeError``. Die Körper der Szene gelten als gezeigt.
    """
    return SimpleNamespace(
        scene=scene, object_names={name: name for name in scene.objects}, stopped_at=None
    )


def _cube_object() -> SceneObject:
    """Ein Körper, an dem sich die Größe einer 3MF ablesen lässt."""
    import trimesh

    from app.core.geom.mesh import MeshData

    return SceneObject(
        id="obj_1",
        name="Würfel",
        mesh=MeshData(raw=trimesh.creation.box(extents=(20.0, 20.0, 20.0))),
    )


@pytest.mark.parametrize("flavour", ["orca", "prusa"])
def test_slice_comparison_uses_selected_plate_quality_and_effective_materials(
    tmp_path: Path, flavour: str
) -> None:
    """Die Gegenprobe enthält weder die übrige Platte noch alte Projektvorgaben."""
    from app.core.export import threemf
    from app.core.slice.estimate import PlateComparison, estimate
    from app.ui import print_settings_dialog as module

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile, "fine")
    first = MaterialSlot(index=0, name="Gehäuse", material_type="PLA")
    second = MaterialSlot(index=0, name="Dichtung", material_type="TPU")
    settings = handover.with_slot_override(
        settings,
        second,
        SlotOverride(filament=replace(settings.filament, density=2.4, max_flow=2.0)),
    )
    selected = [
        replace(_cube_object(), id=f"selected_{index}", plate=1, material_slots=[slot])
        for index, slot in enumerate((first, second))
    ]
    objects = (_cube_object(), *selected)
    setup = handover.SlicerSetup(executable=tmp_path / "slicer.exe", flavour=flavour)
    job = module._PlateJob(objects, (1,), tmp_path, "Teil", setup, settings, profile, {})
    merged = tuple(
        threemf.merge_slots(
            [
                threemf.AssemblyPart(entry.mesh, slots=tuple(entry.material_slots))
                for entry in selected
            ]
        )
    )
    # Die Zeit kommt aus der Schichtanalyse der Platte (RM-465), nicht aus
    # Volumen und Oberfläche der Teile.
    run = module.PlateRun(
        1,
        tmp_path / "plate.3mf",
        slots=merged,
        comparison=PlateComparison(1, None, None, seconds=321.0),
    )

    actual = module._comparison_for_job(job, [run])

    choices = [
        handover.settings_for_slot(settings, profile, slot, setup)
        for slot in (merged if flavour == "orca" else (merged[0], merged[0]))
    ]
    expected = [
        estimate(entry.mesh.volume, entry.mesh.area, own)
        for entry, own in zip(selected, choices, strict=True)
    ]
    assert actual.grams == pytest.approx(sum(item.grams for item in expected))
    assert actual.seconds == pytest.approx(321.0)


def test_slice_comparison_keeps_unknown_material_distribution_unknown(tmp_path: Path) -> None:
    """Oberflächenanteile beweisen keine Volumenanteile verschiedener Filamente."""
    from app.core.slice.estimate import PlateComparison
    from app.ui import print_settings_dialog as module

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    first = MaterialSlot(0, "Erste", material_type="PLA")
    second = MaterialSlot(1, "Zweite", material_type="PLA")
    settings = handover.with_slot_override(
        settings,
        second,
        SlotOverride(filament=replace(settings.filament, density=2.4)),
    )
    body = _cube_object()
    body = replace(body, mesh=replace(body.mesh, slots=(0, 1) * 6), material_slots=[first, second])
    setup = handover.SlicerSetup(executable=tmp_path / "slicer.exe", flavour="orca")
    job = module._PlateJob((body,), (0,), tmp_path, "Teil", setup, settings, profile, {})
    run = module.PlateRun(
        0,
        tmp_path / "plate.3mf",
        slots=(first, second),
        comparison=PlateComparison(0, None, None, seconds=99.0),
    )

    actual = module._comparison_for_job(job, [run])

    assert actual.grams is None
    assert actual.seconds == pytest.approx(99.0), "die Zeit der Platte hängt nicht am Material"


def test_slice_comparison_resolves_the_profile_bound_to_the_plate(tmp_path: Path) -> None:
    """Die Profilauswahl ist Teil des Jobs und liefert die wirksame Dichte."""
    from app.core.slice.estimate import estimate
    from app.ui import print_settings_dialog as module

    source = tmp_path / "filament.json"
    source.write_text(
        json.dumps({"filament_density": ["2.4"], "filament_max_volumetric_speed": ["2"]}),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    slot = MaterialSlot(0, "Spule", material_type="PLA")
    body = replace(_cube_object(), material_slots=[slot])
    setup = handover.SlicerSetup(executable=tmp_path / "slicer.exe", flavour="orca")
    job = module._PlateJob((body,), (0,), tmp_path, "Teil", setup, settings, profile, {})
    run = module.PlateRun(0, tmp_path / "plate.3mf", slots=(replace(slot, material=str(source)),))

    actual = module._comparison_for_job(job, [run])

    expected = estimate(
        body.mesh.volume,
        body.mesh.area,
        replace(settings, filament=replace(settings.filament, density=2.4, max_flow=2.0)),
    )
    assert actual.grams == pytest.approx(expected.grams)
    assert actual.seconds is None, "ohne Schichtanalyse der Platte keine Zeit (RM-465)"


def test_successful_slice_compares_the_job_snapshot_without_reading_the_current_scene(
    dialog: PrintSettingsDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Arbeiter, Ergebnisannahme und Prüfbericht reichen denselben Vergleichskontext weiter."""
    from types import SimpleNamespace

    from app.core.slice.estimate import PlateComparison, estimate
    from app.ui import print_settings_dialog as module
    from app.ui.main_window import MainWindow

    settings = replace(
        print_settings.resolve(dialog.session.profile, "fine"),
        filament=replace(dialog.settings.filament, density=2.4, max_flow=2.0),
    )
    dialog.settings = settings
    selected = replace(_cube_object(), id="selected", plate=1)
    scene = SimpleNamespace(objects={"excluded": _cube_object(), "selected": selected})
    monkeypatch.setattr(dialog.session, "last_result", _shown_result(scene))
    # Der Slicer bekommt die feine Rechnung (RM-426); die Attrappe ist sie.
    monkeypatch.setattr(type(dialog.session), "fine_current", property(lambda _self: True))
    setup = handover.SlicerSetup(executable=tmp_path / "slicer.exe", flavour="prusa")
    monkeypatch.setattr(dialog, "_current_setup", lambda: setup)
    monkeypatch.setattr(dialog, "_chosen_plates", lambda: [1])
    monkeypatch.setattr(dialog, "_plate_slots", list)
    expected = estimate(selected.mesh.volume, selected.mesh.area, settings)
    # Eine Platte ohne Stützen, wie ``plate_comparison`` sie bei Stützart
    # „keine“ liefert: Stützmenge 0,0. Eine unbekannte Stützmenge (``None``)
    # hält die Zeitgegenprobe seit der Stützrechnung an
    # (``estimate.time_comparison_blocked``) — dann prüfte der Test die Zeit nicht.
    monkeypatch.setattr(
        module,
        "_prepare_plate",
        lambda _job, plate: module.PlateRun(
            plate,
            tmp_path / "plate.3mf",
            slots=(MaterialSlot(0, ""),),
            comparison=PlateComparison(plate, 0.0, None, seconds=expected.seconds),
        ),
    )
    monkeypatch.setattr(
        module.handover,
        "slice_model",
        lambda *_args, **_kwargs: handover.SliceOutcome(
            gcode_path=tmp_path / "plate.gcode",
            metrics=gcode.GcodeMetrics(
                filament_grams=expected.grams,
                resolved_model_grams=expected.grams,
                print_seconds=expected.seconds,
            ),
        ),
    )
    findings: list[object] = []
    # Absichtlich ohne session: Der automatische Rückweg darf keinen späteren
    # Szenen- oder Projektzustand für die Gegenprobe heranziehen.
    window = SimpleNamespace(
        report=SimpleNamespace(add_findings=lambda entries, **_kwargs: findings.extend(entries)),
        _focus_report=lambda: None,
        announce=lambda _text: None,
    )
    window._compare_totals = lambda metrics, comparison: MainWindow._compare_totals(
        window, metrics, comparison
    )
    delivered = []

    def returned(outcomes: list[handover.SliceOutcome]) -> None:
        delivered.append(dialog.slice_comparison)
        MainWindow._gcode_returned(window, outcomes, dialog.slice_comparison)

    dialog.sliced.connect(returned)
    dialog._slice()
    worker = dialog._worker
    assert worker is not None and worker.wait(2_000)
    QApplication.processEvents()

    assert len(delivered) == 1 and delivered[0] is not None
    assert delivered[0].grams == pytest.approx(expected.grams)
    assert delivered[0].seconds == pytest.approx(expected.seconds)
    assert not [entry for entry in findings if entry.code == "gcode.deviation"]
    MainWindow._compare_totals(
        window,
        gcode.GcodeMetrics(
            filament_grams=expected.grams * 0.5,
            resolved_model_grams=expected.grams * 0.5,
            print_seconds=expected.seconds * 0.5,
        ),
        dialog.slice_comparison,
    )
    assert len([entry for entry in findings if entry.code == "gcode.deviation"]) == 2
    dialog._forget_result()
    assert dialog.slice_comparison is None


def _settings_in(path: Path) -> bool:
    """Trägt die 3MF Solidons Druckeinstellungen?"""
    import zipfile

    with zipfile.ZipFile(path) as archive:
        return "Metadata/project_settings.config" in archive.namelist()


def test_a_customer_can_export_geometry_without_our_values(
    qt_app: QApplication, session: Session, tmp_path: Path
) -> None:
    """Der Weg, den es bis zum 03.09.2026 nicht gab (§29).

    Der Kern konnte es immer: ``writer._plate_settings`` gibt bei fehlenden
    Einstellungen ein leeres Verzeichnis zurück, und die 3MF trägt dann nur
    Geometrie und Materialslots. Erreichbar war das nicht — der Export löste
    an seiner eigenen Stelle auf (``document.print_settings or resolve(...)``),
    und damit trug **jede** exportierte 3MF Solidons Temperaturen,
    Geschwindigkeiten und Kühlung, auch die aus einem Projekt, in dem nie
    jemand Druckeinstellungen geöffnet hatte.

    Geprüft wird die Anwendung und nicht der Kern: dieselbe Kette, die der
    Knopf im Menü geht — Wahl, :func:`settings_for_export`, Export-Arbeiter,
    fertige Datei. Ein Test gegen ``_plate_settings`` bliebe grün, während der
    Kunde weiterhin nicht hinkommt.
    """
    from app.ui.main_window import _ExportWorker

    document = session.project.document
    assert document.print_settings is None, "ein frisches Projekt hat noch keine"

    written: dict[bool, Path] = {}
    for wanted in (True, False):
        ui = UiSettings()
        ui.print_settings_in_files = wanted
        folder = tmp_path / f"mitgeben-{wanted}"
        folder.mkdir()
        worker = _ExportWorker(
            [_cube_object()],
            folder / "probe.3mf",
            "3mf",
            profile=session.profile,
            sources={},
            settings=settings_for_export(document, session.profile, ui),
            ui_settings=ui,
            material=session.profile.material.id,
        )
        paths, _findings = worker._assembly()
        assert len(paths) == 1
        written[wanted] = paths[0]

    assert _settings_in(written[True]), "mit Haken trägt die Datei Solidons Werte"
    assert not _settings_in(written[False]), (
        "ohne Haken geht nur Geometrie hinaus — der Slicer nimmt sein eigenes Profil"
    )
    # Und der Unterschied ist nicht nur ein fehlender Eintrag im Verzeichnis:
    # Die Beilage ist der größte Teil einer kleinen Datei.
    assert written[False].stat().st_size < written[True].stat().st_size


def test_only_looking_at_the_settings_leaves_the_project_alone(
    dialog: PrintSettingsDialog,
) -> None:
    """Wer nachsieht, ändert nichts (§29).

    Bis zum 03.09.2026 schrieb schon das bloße Öffnen die aufgelösten Werte
    ins Dokument: ``main_window`` rief ``set_print_settings(dialog.settings)``
    nach ``exec()``, ohne zu fragen, ob etwas geschehen war — und der Dialog
    hat nur „Schließen", also nicht einmal einen Abbruch. Wer wissen wollte,
    welche Temperatur vorgeschlagen würde, trug sie danach in jeder
    exportierten 3MF mit sich, ohne Weg zurück.

    Gemessen wird an ``has_changes`` und nicht an einer Liste von Knöpfen:
    Das erfasst jeden der sieben Wege, auf denen sich ``settings`` ändert.
    """
    assert not dialog.has_changes(), "nach dem Aufbau hat niemand etwas getan"

    # Eine echte Handlung des Nutzers: die Stufe wechseln.
    other = next(
        index
        for index in range(dialog.quality.count())
        if dialog.quality.itemData(index) != dialog.settings.quality
    )
    dialog.quality.setCurrentIndex(other)

    assert dialog.has_changes(), "eine gewechselte Stufe ist eine Änderung"


def test_the_head_offers_the_way_back(dialog: PrintSettingsDialog) -> None:
    """Die Wahl aus dem Druckhinweis ist im Dialog zu sehen und zu ändern.

    Ohne diesen Umschalter wäre die Wahl selbst wieder eine Einbahnstraße —
    genau der Fehler, den sie behebt. Der Haken trägt seine Erklärung in allen
    drei Kanälen, denn eine Bedeutung allein über die Stellung eines Kästchens
    wäre keine (Regel 18).
    """
    assert dialog.share_settings.isChecked(), "vorbelegt wie der bisherige Weg"
    for channel, value in (
        ("tooltip", dialog.share_settings.toolTip()),
        ("accessible description", dialog.share_settings.accessibleDescription()),
    ):
        assert "Geometrie" in value, f"der {channel} sagt, was ohne Haken hinausgeht: {value!r}"
        assert "direkten Slicen" in value
        assert "unabhängig vom Haken" in value

    dialog.share_settings.setChecked(False)
    assert not dialog.ui_settings.print_settings_in_files, (
        "der Haken schaltet die Einstellung, nicht nur sich selbst"
    )


# --- Vorschläge, die man auch annehmen kann ------------------------------------------


def test_share_failure_stays_with_the_choice_and_a_successful_retry_clears_it(
    dialog: PrintSettingsDialog, monkeypatch, tmp_path
) -> None:
    """Ein Speicherfehler überschreibt weder den Druckstatus noch spätere Erfolge."""
    from app.ui import print_settings_dialog

    dialog.state.setText("Druckdatei wird vorbereitet")
    monkeypatch.setattr(print_settings_dialog, "save_settings", lambda _settings: None)
    dialog.share_settings.setChecked(False)
    assert not dialog.share_notice.isHidden()
    assert "Schreibrechte" in dialog.share_notice.text()
    assert dialog.share_notice.text() in dialog.share_settings.accessibleDescription()
    assert dialog.state.text() == "Druckdatei wird vorbereitet"
    layout = dialog.share_notice.parentWidget().layout()
    assert layout.indexOf(dialog.share_notice) == layout.indexOf(dialog.share_settings) + 1
    assert not dialog.ui_settings.print_settings_in_files

    monkeypatch.setattr(print_settings_dialog, "save_settings", lambda _settings: tmp_path)
    dialog.share_settings.setChecked(True)
    assert dialog.share_notice.isHidden() and not dialog.share_notice.text()
    assert dialog.share_settings.accessibleDescription() == dialog.share_settings.toolTip()
    assert dialog.state.text() == "Druckdatei wird vorbereitet"


def test_no_advice_proposes_a_value_the_dialog_cannot_show() -> None:
    """Ein Vorschlag ist ein Knopf, kein Hinweis — „Vorschläge übernehmen"
    schreibt ihn ins Projekt.

    Gemessen am 03.09.2026 mit einem Verbinder von Ø 60 mm, wie ihn das Teilen
    eines großen Körpers erzeugt: `advise` schlug **36 Wände** vor, das Feld
    hier reicht bis 20. Übernommen stand 36 im Dokument, die an den Slicer
    übergebene Datei trug `wall_loops: 36` — und der Dialog zeigte daneben 20,
    weil sein Feld nicht weiter reicht. Anzeige und Datei sagten Verschiedenes,
    und 36 Bahnen à 0,42 mm sind 15 mm Wandstärke.

    Der Docstring von `_from_connectors` kannte den Grundsatz schon für den
    kleineren Fall: „ein Vorschlag, den niemand annimmt, macht die vier daneben
    unglaubwürdig". Er galt nur nicht für den großen.

    Geprüft wird über die Randlagen, nicht über die gutmütigen: winzige und
    riesige Körper, dünne und unsinnig dicke Zapfen, jede Passungsart.
    """
    from app.core.slice import advise
    from app.core.types import BoundingBox

    fields = {field.path: field for field in FIELDS}
    profile = Profile(
        printer=next(iter(profiles.printer_profiles().values())),
        material=next(iter(profiles.material_profiles().values())),
    )
    boxes = (
        BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(2.0, 2.0, 2.0)),
        BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(160.0, 231.0, 14.0)),
        BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(900.0, 900.0, 900.0)),
    )
    connectors = ((), (4.0, 6.0), (33.5,), (33.7,), (60.0,), (631.6,))

    offenders: list[str] = []
    seen = 0
    for quality in print_settings.quality_presets():
        resolved = print_settings.resolve(profile, quality)
        for box in boxes:
            for pins in connectors:
                for advice in advise.advise(resolved, profile, None, bounds=box, connectors=pins):
                    seen += 1
                    field = fields.get(advice.path)
                    if field is None or field.choices:
                        continue
                    if not isinstance(advice.value, (int, float)) or isinstance(advice.value, bool):
                        continue
                    shown = float(advice.value) * field.factor
                    if shown < field.minimum or shown > field.maximum:
                        offenders.append(
                            f"{advice.path} = {shown:g}, Feld erlaubt "
                            f"{field.minimum:g}…{field.maximum:g} (Zapfen {pins})"
                        )

    # Gemessen sind es 39 über die 72 Lagen; die Schwelle liegt knapp darunter,
    # damit sie greift, wenn die Menge einbricht — ein Filter über eine leere
    # Menge findet nichts und besteht.
    assert seen > 30, f"nur {seen} Vorschläge geprüft — der Lauf sagt nichts"
    assert not offenders, "unerreichbare Vorschläge:\n" + "\n".join(sorted(set(offenders)))


def test_the_core_knows_how_many_walls_the_dialog_offers() -> None:
    """Die Grenze steht zweimal, und sie muss dieselbe sein.

    Der Kern darf die Oberfläche nicht fragen (Regel 1), also trägt er seine
    eigene Zahl. Zwei Zahlen laufen auseinander, sobald jemand eine ändert —
    dieser Test ist die Klammer, und er nennt beim Reißen gleich die andere
    Stelle.
    """
    from app.core.slice.advise import MOST_WALLS_WORTH_SUGGESTING

    field = next(entry for entry in FIELDS if entry.path == "shell.wall_count")
    assert field.maximum == MOST_WALLS_WORTH_SUGGESTING, (
        "advise.MOST_WALLS_WORTH_SUGGESTING und das Feld shell.wall_count "
        "im Druckdialog müssen dieselbe Obergrenze führen"
    )


def test_the_list_of_ignored_settings_matches_what_the_slicers_take() -> None:
    """Welche Einstellung ankommt, wird gemessen und nicht aus der Tabelle geschlossen.

    Ein Wert erreicht den Slicer auf drei Wegen: über eine Zeile in `TABLES`,
    über `ADHESION_KEYS`, oder weil `handover` ihn verrechnet —
    `support.density` steht in keiner Prusa-Zeile und wird trotzdem übergeben,
    weil daraus ein Linienabstand wird. Der erste Anlauf am 03.09.2026 las nur
    die Tabelle und hätte drei Felder bei Prusa und zwei bei Cura gesperrt, die
    sehr wohl wirken.

    Gemessen wird deshalb am Ergebnis: Wert ändern, `values_for` zweimal bauen,
    vergleichen — und das über **vier Haftungsarten**, weil
    `_only_chosen_adhesion` die Maße der nicht gewählten nullt. „Skirt-Runden"
    bei eingestelltem Brim ist eine Abhängigkeit und kein toter Wert; wer das
    verwechselt, sperrt vier Felder zu viel.
    """
    from app.core.export import handover, slicer_keys

    profile = Profile(
        printer=next(iter(profiles.printer_profiles().values())),
        material=next(iter(profiles.material_profiles().values())),
    )
    base = print_settings.resolve(profile, next(iter(print_settings.quality_presets())))
    layouts = [
        print_settings.with_path(base, "adhesion.kind", kind)
        for kind in ("skirt", "brim", "raft", "none")
    ]

    def other(field: object) -> object:
        """Ein zweiter Wert, der sich vom ersten unterscheidet."""
        now = print_settings.read_path(base, field.path)  # type: ignore[attr-defined]
        if field.choices:  # type: ignore[attr-defined]
            return next((c for c in field.choices if str(c) != str(now)), None)  # type: ignore[attr-defined]
        if isinstance(now, bool):
            return not now
        if isinstance(now, (int, float)):
            candidate = float(now) + max(1.0, abs(float(now)) * 0.5)
            ceiling = field.maximum / (field.factor or 1.0)  # type: ignore[attr-defined]
            if candidate > ceiling:
                candidate = max(field.minimum / (field.factor or 1.0), float(now) / 2.0)  # type: ignore[attr-defined]
            return int(candidate) if isinstance(now, int) else candidate
        return None

    for flavour in slicer_keys.TABLES:
        if flavour == "other":
            # Ein Programm ohne Familie bekommt nichts übersetzt — jedes Feld
            # ist dort „nicht übernommen", und ``takes`` sagt es ohne Liste.
            assert all(not slicer_keys.takes(flavour, field.path) for field in FIELDS)
            continue
        measured: set[str] = set()
        checked = 0
        for field in FIELDS:
            second = other(field)
            if second is None:
                continue  # kein zweiter Wert — etwa eine Farbe
            checked += 1
            works = any(
                handover.values_for(layout, profile, flavour)
                != handover.values_for(
                    print_settings.with_choice(layout, field.path, second), profile, flavour
                )
                for layout in layouts
            )
            if not works:
                measured.add(field.path)
        assert checked > 50, f"{flavour}: nur {checked} Felder geprüft — der Lauf sagt nichts"
        # Was als Geometrie reist, sieht diese Messung nicht: in der Baugruppe
        # oder, bei Cura, als eigenes Netz neben den Teilen (Stufe D).
        if slicer_keys.reads_assembly_file(flavour) or slicer_keys.takes_mesh_settings(flavour):
            measured -= slicer_keys.AS_GEOMETRY
        assert measured == slicer_keys.NOT_TAKEN_BY[flavour], (
            f"{flavour}: gemessen {sorted(measured)}, "
            f"eingetragen {sorted(slicer_keys.NOT_TAKEN_BY[flavour])}"
        )


def test_without_a_machine_profile_the_printers_own_vendor_narrows_the_filaments(
    qt_app: QApplication, session: Session
) -> None:
    """Ohne Maschinenprofil zeigt die Liste die Filamente des eigenen Herstellers.

    Vorher blieb sie leer, und das war eine Leistungsentscheidung: Der Bestand
    eines installierten Slicers hält 5962 Filamentprofile über 48 Hersteller,
    und sie alle in eine Combobox zu legen ließ die Anwendung minutenlang
    stehen. Solidon weiß aber mehr — der Drucker des Projekts kennt seinen
    Hersteller, und die Profilnamen tragen ihn vorn.

    Zwei Fälle, die den Filter fast unbrauchbar gemacht hätten, beide am
    03.09.2026 gemessen:

    * **Der Vorgabedrucker hat gar keinen Hersteller.** ``generic-220`` heißt
      „Allgemeiner FDM-Drucker"; ein Filter auf sein leeres Feld träfe mit
      ``startswith("")`` jeden Eintrag und stellte genau den Hänger wieder her.
    * **Der Herstellername ist nicht der Namensanfang.** Der Hersteller heißt
      „Bambu Lab", die Profile heißen „Bambu PLA Basic" — auf den vollen Namen
      verglichen waren es null von vier Treffern.
    """
    from app.core.export import slicer_profiles as sp
    from app.ui.print_settings_dialog import PrintSettingsDialog

    dialog = PrintSettingsDialog(session, UiSettings())
    dialog._profiles = [
        sp.SlicerProfile(path=Path(__file__), name=name, kind="filament")
        for name in ("Elegoo PLA @EC", "Elegoo PETG @EC", "Bambu PLA Basic", "Generic ABS")
    ]

    printers = profiles.printer_profiles()
    generic = next(key for key, entry in printers.items() if not entry.vendor)
    dialog.session.project.document.printer = generic
    assert dialog._filaments_worth_showing(None) == [], (
        "ohne Hersteller bleibt es leer — sonst stünden 5962 Einträge in der Liste"
    )

    two_words = next((key for key, entry in printers.items() if " " in entry.vendor.strip()), "")
    if two_words:
        dialog.session.project.document.printer = two_words
        found = dialog._filaments_worth_showing(None)
        assert found, (
            f"{printers[two_words].vendor!r}: das erste Wort muss zählen, "
            "sonst trifft der Filter nichts"
        )
        first = printers[two_words].vendor.split(" ")[0].casefold()
        assert all(entry.name.casefold().startswith(first) for entry in found)


def test_the_vendor_fallback_never_binds_a_filament_of_another_material(
    qt_app: QApplication, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 21, gemessen am 19.09.2026 mit Creality Print: Für ein PLA-Projekt
    auf dem Centauri fand sich keine Maschine, der Herstellerfilter lieferte
    „Elegoo Generic ABS" als ersten Namen, und der wurde das Filament des
    Laufs. Ohne Profil derselben Materialart bleibt die Zeile leer und sagt
    es; mit einem passenden nimmt sie das — nicht das alphabetisch erste.
    """
    from app.core.export import slicer_profiles as sp
    from app.ui.print_settings_dialog import PrintSettingsDialog

    printers = profiles.printer_profiles()
    elegoo = next(key for key, entry in printers.items() if entry.vendor == "Elegoo")
    session.project.document.printer = elegoo
    session.project.document.material = "pla"
    dialog = PrintSettingsDialog(session, UiSettings())
    abs_profile = sp.SlicerProfile(
        path=Path("Elegoo Generic ABS.json"),
        name="Elegoo Generic ABS",
        kind="filament",
        filament_type="ABS",
    )
    petg_profile = sp.SlicerProfile(
        path=Path("Elegoo Generic PETG.json"),
        name="Elegoo Generic PETG",
        kind="filament",
        filament_type="PETG",
    )
    pla_profile = sp.SlicerProfile(
        path=Path("Elegoo Generic PLA.json"),
        name="Elegoo Generic PLA",
        kind="filament",
        filament_type="PLA",
    )

    dialog._profiles = [abs_profile, petg_profile]
    dialog._fill_filaments(None)
    assert dialog._filament_profile == "", "kein PLA-Profil im Bestand — dann keines"
    assert "Materialart" in dialog.filament_shown.text()

    dialog._profiles = [abs_profile, petg_profile, pla_profile]
    dialog._fill_filaments(None)
    assert dialog._filament_profile == str(pla_profile.path), "das Profil derselben Materialart"


def test_an_adopted_twin_does_not_take_the_machines_of_the_project_printer(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eingebauter Centauri Carbon 2 im Projekt, derselbe aus dem Slicer übernommen (RM-600).

    Roberts Drache, 08.10.2026: Die Liste der Druckerprofile zeigte die 0,2er,
    0,6er und 0,8er Maschine, aber nicht die 0,4er, mit der er druckt — die
    hieß wie sein übernommener Drucker und wurde diesem zugeordnet. Gewählt
    war damit nichts, ein Prozess fehlte, und das Filament fiel ohne Maschine
    auf „Elegoo PLA @0.2 nozzle". Dazu bot der Dialog an, den Drucker des
    Slicers zu übernehmen, auf dem das Projekt längst stand.
    """
    from app.core.export import slicer_profiles

    built_in = profiles.printer("centauri-carbon-2")
    twin = replace(
        built_in, id="slicer-orca-af8733f715e1dfb0606b", title="Elegoo Centauri Carbon 2 0.4 nozzle"
    )
    profiles.save_printer(twin, slicer="elegooslicer")
    dialog.session.project.document.printer = built_in.id
    stock = [
        SlicerProfile(path=Path(f"{name}.json"), name=name, kind="machine", nozzle=nozzle)
        for name, nozzle in (
            ("Elegoo Centauri Carbon 2 0.2 nozzle", 0.2),
            ("Elegoo Centauri Carbon 2 0.4 nozzle", 0.4),
            ("Elegoo Centauri Carbon 2 0.6 nozzle", 0.6),
            ("Bambu Lab A1 0.4 nozzle", 0.4),
        )
    ]

    shown = [entry.name for entry in dialog._machines_worth_showing(stock)]
    assert shown == [entry.name for entry in stock[:3]], shown

    dialog._slicer_path = Path("elegoo-slicer.exe")
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: stock[1].name)
    assert dialog._printer_of_the_slicer() == "", "das Projekt steht schon auf diesem Gerät"
    machine, belongs = dialog._slicer_machine_for_project(stock)
    assert machine is stock[1]
    assert belongs


def test_the_printer_list_shows_the_printer_you_actually_have(
    qt_app: QApplication, session: Session
) -> None:
    """„Ich hab da mehr Drucker zur Auswahl, offiziell hab ich nur den einen."

    Robert am 03.09.2026, und gemessen an seinem ElegooSlicer: **1001**
    Maschinenprofile in der Liste, davon 103 einem Solidon-Drucker zuordenbar
    und vier seinem — die Düsenvarianten. Die Vorwahl traf dabei die richtige;
    unbrauchbar war die Liste dahinter.

    Zugeordnet wird über `printer_for`, also über dieselbe Auskunft, mit der
    auch die Vorwahl arbeitet — keine zweite Namensheuristik daneben.

    **Und der Rückfall ist der eigentliche Test:** Für den Vorgabedrucker
    ordnet sich kein Profil zu, und eine leere Druckerliste wäre schlimmer als
    eine lange — ohne Maschinenprofil lehnt der Slicer jeden Auftrag ab. Ein
    Filter, der alles wegnimmt, ist keiner.
    """
    from app.core.export import slicer_profiles as sp
    from app.ui.print_settings_dialog import PrintSettingsDialog

    dialog = PrintSettingsDialog(session, UiSettings())
    printers = profiles.printer_profiles()
    named = next((key, entry) for key, entry in printers.items() if entry.vendor and " " not in key)
    stock = [
        sp.SlicerProfile(path=Path(name), name=name, kind="machine")
        for name in (
            f"{named[1].title} 0.4 nozzle",
            f"{named[1].title} 0.6 nozzle",
            "Foreign Q9 0.4 nozzle",
        )
    ]

    dialog.session.project.document.printer = named[0]
    mine = dialog._machines_worth_showing(stock)
    assert len(mine) == 2, f"nur die eigenen Düsenvarianten, nicht {[m.name for m in mine]}"
    assert all(str(named[1].title) in entry.name for entry in mine)

    generic = next(key for key, entry in printers.items() if not entry.vendor)
    dialog.session.project.document.printer = generic
    assert dialog._machines_worth_showing(stock) == stock, (
        "wo sich nichts zuordnen lässt, bleibt alles stehen — sonst hätte der "
        "Slicer kein Maschinenprofil und lehnte jeden Auftrag ab"
    )


def test_no_locked_button_in_this_dialog_stays_silent(dialog: PrintSettingsDialog) -> None:
    """Dieselbe Zusage wie oben, nur für alle Knöpfe statt für einen.

    Der Test über *Druckdatei speichern …* steht seit Langem da, und trotzdem
    fiel *Vorschläge übernehmen* durch: gesperrt, weil es nichts zu übernehmen
    gibt, und wortlos. Gemessen am 03.09.2026 über alle sichtbaren Knöpfe des
    Dialogs — von vier gesperrten trug einer keinen Grund.

    Ein Test je Knopf fängt den nächsten Knopf nicht. Die Regel gilt dem
    Dialog, also prüft sie ihn als Ganzes; wer einen fünften Knopf hinzufügt,
    bekommt sie ohne weiteres Zutun.

    Die Tabelle darüber sagt zwar „Nichts einzuwenden.", aber das ist ein Satz
    an einer anderen Stelle: Wer auf den grauen Knopf zeigt, fragt ihn.
    """
    # **Gezeigt, nicht nur gebaut.** Vor dem ``show()`` steht der Dialog auf
    # halbem Weg: Die Profilsuche läuft nicht, und die zwei Slicer-Knöpfe
    # tragen ihren Grund noch nicht. Gemessen am gebauten Fenster ist er nach
    # dem Anzeigen da („Der Profilbestand wird durchgesehen …"), und das ist
    # der Zustand, den ein Kunde sieht — ein Test davor prüfte einen, den es
    # für ihn nie gibt.
    dialog.show()
    for _ in range(10):
        QApplication.processEvents()

    stumm = []
    for button in dialog.findChildren(QPushButton):
        if not button.isVisibleTo(dialog) or not button.text() or button.isEnabled():
            continue
        # Beide Kanäle, wie bei den Nachbarn: Ein Grund, den nur die Maus
        # findet, ist für den Bildschirmleser keiner (Regel 18).
        if not (button.toolTip() and button.accessibleDescription()):
            stumm.append(button.text())
    assert not stumm, f"gesperrt und ohne Grund: {stumm}"


def test_the_machine_list_follows_the_printer_of_the_project(qt_app: QApplication) -> None:
    """Wer den Drucker wechselt, bekommt die Profile des neuen — nicht die alten.

    **Roberts Fall, gemessen am 03.09.2026 von 3d-druck-c7 und hier
    nachgestellt.** Der Dialog öffnet mit dem Drucker aus den Einstellungen,
    und das ist bei frischem Stand der allgemeine 220er. Für den ordnet sich
    kein Profil zu, also greift die Notbremse in ``_machines_worth_showing``
    („bleibt nichts übrig, bleibt alles stehen") und zeigt den ganzen Bestand.
    Danach stellt der Kunde seinen Drucker ein — und die Liste blieb, wie sie
    war:

        A) generic-220         1001 zur Wahl, nichts gewählt
        B) Centauri Carbon 2   1001 zur Wahl, nichts gewählt
        C) neu gefüllt            4 zur Wahl, das richtige gewählt

    ``_scene_profile_changed`` lud die Editoren neu und frischte die Beratung
    auf, rührte die drei Profilfelder aber nicht an. Für den einzigen Drucker,
    den Robert besitzt, hieß das: aus 1001 Einträgen suchen, obwohl vier davon
    seine sind und ``printer_for`` sie kennt.

    **Die gemerkte Wahl überlebt den Wechsel nicht.** Sie galt für den vorigen
    Drucker; ein Maschinenprofil gehört zu genau einem. Innerhalb desselben
    Druckers bleibt sie stehen — das hält
    ``test_a_remembered_choice_wins_over_the_match`` fest.
    """
    session = Session()
    session.project.document.printer = "generic-220"
    settings = UiSettings()
    weit = _profile("Fremder Drucker 0.4 nozzle", "machine", printer_model="Fremder", nozzle=0.4)
    meiner = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
    )
    from app.ui.style import select_data

    dialog = PrintSettingsDialog(session, settings)
    dialog._profiles_found([weit, meiner])

    assert dialog.machine_choice.count() == 2, "der allgemeine Drucker sieht alles"

    select_data(dialog.printer_choice, "centauri-carbon-2")
    dialog._scene_profile_changed()

    assert session.profile.printer.id == "centauri-carbon-2", "die Vorbedingung des Tests"
    assert dialog.machine_choice.count() == 1, "jetzt nur noch die des neuen Druckers"
    assert dialog.machine_choice.currentData() == str(meiner.path)


def test_a_printer_the_slicer_does_not_know_says_which_one(
    dialog: PrintSettingsDialog,
) -> None:
    """„Zu diesem Drucker passt kein Profil" ließ offen, welcher gemeint ist.

    Der Satz ist wahr und ist trotzdem keine Auskunft: Er sagt nicht, *welcher*
    Drucker keines hat, nicht *welcher Slicer* keines mitbringt, und damit auch
    nicht, warum die Liste darunter voll ist. Gemessen an einem frischen
    Projekt auf *Allgemeiner FDM-Drucker 220 mm* mit ElegooSlicer: 1001 Profile
    zur Wahl, das Feld leer, *Slicen* gesperrt — und kein Wort darüber, dass
    der Slicer für genau diesen Drucker keines kennt.

    Wer beide Namen liest, weiß sofort, ob er den Drucker wechseln oder ein
    Profil suchen muss. Geprüft wird deshalb, dass beide Namen vorkommen, und
    nicht der Wortlaut — ein Test, der den Satz mitliest, prüft sich selbst.
    """
    dialog._slicer_path = Path("C:/Programme/ElegooSlicer/elegoo-slicer.exe")
    fremd = SlicerProfile(
        path=Path("Afinia H+1(HS) 0.4 nozzle.json"),
        name="Afinia H+1(HS) 0.4 nozzle",
        kind="machine",
        printer_model="Afinia H+1",
        nozzle=0.4,
    )
    dialog._profiles_found([fremd])

    note = dialog.profile_note.text()
    assert note, "ohne Zuordnung bleibt der Hinweis vom Suchen stehen"
    drucker = dialog.printer_choice.currentText()
    assert drucker, "ohne Druckernamen prüft dieser Test nichts"
    assert drucker in note, f"der Hinweis nennt den Drucker nicht: {note!r}"
    assert "lslicer" in note.lower() or "elegoo" in note.lower(), (
        f"der Hinweis nennt den Slicer nicht: {note!r}"
    )
    assert "{" not in note, f"ein Platzhalter blieb stehen: {note!r}"


def test_without_a_manufacturer_profile_one_sentence_says_it_and_no_field_stands_empty(
    dialog: PrintSettingsDialog,
) -> None:
    """Ein Satz statt zweier, und kein leeres Feld (RM-514, C3/D11).

    PrusaSlicer verlangt kein Profil. Fand sich für den Drucker keines, klappte
    der Kasten auf: vier leere Felder, „Für … bringt PrusaSlicer kein eigenes
    Profil mit — es gelten Solidons Werte …" darin und „Ohne Profil des
    Herstellers gelten Solidons Vorgaben …" darunter, zwei Wörter für eine
    Sache. Dazu „Erst einen Drucker wählen", obwohl oben einer stand — es
    fehlte das Druckerprofil.
    """
    dialog._slicer_path = Path("C:/Programme/Prusa3D/PrusaSlicer/prusa-slicer.exe")
    # Zwei fremde Drucker: Steht genau einer zur Wahl, ist er die Wahl
    # (``_profiles_found``), und dann gäbe es den Fall ohne Profil nicht.
    fremde = [
        _profile(f"Fremder Drucker {name} 0.4 nozzle", "machine", printer_model=name, nozzle=0.4)
        for name in ("A", "B")
    ]
    dialog._profiles_found(fremde)

    drucker = dialog.printer_choice.currentText()
    satz = dialog.foundation_note.text()
    assert drucker and drucker in satz and "PrusaSlicer" in satz, satz
    assert not dialog.profile_note.text(), "derselbe Satz nicht noch einmal im Kasten"
    assert dialog.slicer_toggle is not None and not dialog.slicer_toggle.isChecked(), (
        "nichts zu wählen — der Kasten bleibt zu"
    )

    dialog._open_slicer_section()
    sichtbar = [
        box
        for box in (dialog.process_choice, *(box for _label, box in dialog.slot_rows))
        if box.isVisibleTo(dialog.slicer_box)
    ]
    assert all(box.count() for box in sichtbar), "ein sichtbares Auswahlfeld hat etwas zur Wahl"
    assert not dialog.process_choice.isVisibleTo(dialog.slicer_box)
    assert not dialog.profile_note.isVisibleTo(dialog.slicer_box)
    assert "Druckerprofil" in dialog.filament_shown.text(), dialog.filament_shown.text()

    # Für Cura gibt es nichts zu wählen: derselbe eine Satz, kein Kasten.
    dialog._slicer_path = Path("C:/Programme/Cura/CuraEngine.exe")
    dialog._show_foundation_note()
    assert "Solidons Werte" in dialog.foundation_note.text()


def test_no_caption_stands_twice_in_the_print_dialog(dialog: PrintSettingsDialog) -> None:
    """„Drucker" stand zweimal, „Düse" meinte Durchmesser und Temperatur (RM-514, C14).

    Gezählt werden die Beschriftungen aller Formulare des Dialogs, auch der
    zugeklappten Reiter: Wer „Düse" liest, soll nicht raten, welche gemeint
    ist. Und die Slotzeilen stehen an derselben Kante wie die übrigen — der
    Farbpunkt im Feld, nicht eingerückt vor der Beschriftung.
    """
    from PySide6.QtWidgets import QLabel

    beschriftungen: list[str] = []
    for form in dialog.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            label = item.widget() if item is not None else None
            if isinstance(label, QLabel) and label.text().strip():
                beschriftungen.append(label.text().strip())
    assert len(beschriftungen) > 40, "die Formulare wurden nicht gefunden"
    doppelt = sorted({text for text in beschriftungen if beschriftungen.count(text) > 1})
    assert not doppelt, f"zweimal im Dialog: {doppelt}"
    for text in ("Druckerprofil", "Prozessprofil", "Filamentprofil", "Düsentemperatur"):
        assert text in beschriftungen, text
    assert not [text for text in beschriftungen if text.startswith(" ")], "keine Einrückung"


def test_the_handover_lines_stand_right_above_the_buttons(
    dialog: PrintSettingsDialog, qt_app: QApplication
) -> None:
    """Zustand, Bestand und *Werte mitgeben* gehören zu den Knöpfen (RM-514, C15).

    Sie standen am Ende des Rollbereichs; nach dem Zuklappen trennten bis zu
    260 Punkte Leere die Mitgabe von den Knöpfen, die sie betrifft. Jetzt
    stehen sie außerhalb, und dazwischen liegt höchstens zweimal ``NORMAL``.
    """
    from app.ui.style import NORMAL

    dialog.show()
    for _ in range(8):
        qt_app.processEvents()
    dialog.tabs_toggle.setChecked(True)
    for _ in range(8):
        qt_app.processEvents()
    dialog.tabs_toggle.setChecked(False)
    dialog.resize(dialog.width(), dialog.height() + 260)
    for _ in range(8):
        qt_app.processEvents()

    for widget in (dialog.state, dialog.stock_notice, dialog.share_settings):
        assert not dialog._scroll.isAncestorOf(widget), widget
    unten = dialog.share_settings.mapTo(dialog, dialog.share_settings.rect().bottomLeft()).y()
    luecke = dialog._buttons.geometry().top() - unten
    assert 0 <= luecke <= 2 * NORMAL, luecke


def test_without_a_matching_profile_the_nozzle_still_narrows_the_list(
    dialog: PrintSettingsDialog,
) -> None:
    """„1001 Profile sind bisschen viel" (Robert, 03.09.2026).

    Für einen Drucker, dem sich kein Profil zuordnet, zeigte die Notbremse den
    **ganzen** Bestand — beim ElegooSlicer 1001 Einträge, 78 Hersteller. Eine
    echte Auskunft über den Drucker gibt es aber auch dann: seine Düse. Ein
    Profil für 0,8 mm ist an einem 0,4-mm-Drucker die falsche Wahl, gleich wie
    der Drucker heißt; am echten Bestand bleiben damit 387 statt 1001.

    Der Herstellername hülfe hier nicht: Er ist genau bei dem Drucker leer, bei
    dem diese Stufe überhaupt greift (`generic-220`).

    Und die Notbremse dahinter bleibt: Passt auch keine Düse, steht wieder
    alles da — der Slicer lehnt ohne Maschinenprofil jeden Auftrag ab.
    """

    def machine(name: str, nozzle: float) -> SlicerProfile:
        return SlicerProfile(path=Path(f"{name}.json"), name=name, kind="machine", nozzle=nozzle)

    fremd = [
        machine("Afinia H+1(HS) 0.4 nozzle", 0.4),
        machine("Voron 2.4 0.8 nozzle", 0.8),
        machine("Snapmaker J1 0.6 nozzle", 0.6),
        machine("RatRig V-Core 0.4 nozzle", 0.4),
    ]
    mine = dialog.session.profile.printer
    assert mine.nozzle_diameter == pytest.approx(0.4), "sonst prüft dieser Test etwas anderes"

    gezeigt = dialog._machines_worth_showing(fremd)
    assert [entry.name for entry in gezeigt] == [
        "Afinia H+1(HS) 0.4 nozzle",
        "RatRig V-Core 0.4 nozzle",
    ], "die Liste zeigt Düsen, die dieser Drucker nicht hat"

    # Passt keine, bleibt alles stehen — eine leere Liste wäre schlimmer.
    nur_dick = [machine("Voron 2.4 0.8 nozzle", 0.8)]
    assert dialog._machines_worth_showing(nur_dick) == nur_dick

    # Und die gemerkte Wahl überlebt auch diese Stufe.
    dialog.ui_settings.slicer_machine_profile = "Voron 2.4 0.8 nozzle.json"
    gezeigt = dialog._machines_worth_showing(fremd)
    assert "Voron 2.4 0.8 nozzle" in [entry.name for entry in gezeigt], (
        "wer einmal abgewichen ist, meinte es so"
    )


def test_the_printer_list_can_be_searched_by_typing(dialog: PrintSettingsDialog) -> None:
    """Auch 387 Einträge findet niemand durch Rollen.

    Die Düsenstufe darüber drittelt die Liste; was bleibt, ist immer noch zu
    lang für ein Aufklappmenü. Getippt wird deshalb, und gesucht wird **im
    ganzen Namen**: Wer „Ender" eingibt, meint „Creality Ender-3 V3", und der
    Herstellername steht davor. Am echten Bestand: „ender" trifft 21 Einträge,
    „Centauri" vier.

    Ein getippter Name, den es nicht gibt, darf keine Wahl werden — sonst
    stünde im Feld ein Drucker, den der Slicer nicht kennt.
    """
    box = dialog.machine_choice
    assert not box.isEditable(), "Suchtext und bestätigte Druckerwahl bleiben getrennt"

    dialog._profiles_found(
        [
            SlicerProfile(path=Path(f"{name}.json"), name=name, kind="machine", nozzle=0.4)
            for name in (
                "Creality Ender-3 V3 0.4 nozzle",
                "Elegoo Centauri Carbon 2 0.4 nozzle",
                "Voron 2.4 0.4 nozzle",
            )
        ]
    )
    box.search_field.setText("ender")
    assert box.filtered.rowCount() == 1, "mitten im Namen wird nicht gesucht"
    assert "Ender-3" in box.filtered.index(0, 0).data()


def _wait_for_print_advice(dialog: PrintSettingsDialog, application: QApplication) -> None:
    """Die aktive asynchrone Empfehlung einschließlich nachgereichter Signale abholen."""
    deadline = time.monotonic() + 10
    while dialog._advice_pending and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.005)
    application.processEvents()
    assert not dialog._advice_pending, "die Druckprüfung kam nicht zurück"
    assert not dialog._advice_problem, dialog._advice_problem


def _print_advice_dialog(qt_app, objects, *, settings=None):
    """Ein echter Druckauftrag ohne Hauptfenster und Renderer."""
    from types import SimpleNamespace

    session = Session()
    session.project.document.print_settings = settings
    session.last_result = SimpleNamespace(
        scene=SimpleNamespace(objects={obj.id: obj for obj in objects})
    )
    made = PrintSettingsDialog(session, UiSettings())
    # Wie die Fixture ``dialog``: Die Slicersuche läuft im Arbeiter, und ihre
    # nachgereichte Antwort überschreibt sonst den Pfad, den der Aufrufer setzt.
    assert made.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    return made


def _print_advice_cube(name="Würfel", *, plate=0, slots=()):
    """Kleine vollständige Testgeometrie für den Druckdialog.

    Mehrere Slots bekommen je eigene Dreiecke: Ein deklarierter Slot ohne
    Fläche ist eine alte unbenutzte Spule und erscheint weder in der Übergabe
    noch als Filamentzeile (e06d57cef).
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    mesh = trimesh.creation.box((10, 10, 10))
    mesh.apply_translation((0, 0, 5))
    painted: tuple[int, ...] = ()
    if len(slots) > 1:
        indices = [int(slot.index) for slot in slots]
        painted = tuple(indices[face % len(indices)] for face in range(len(mesh.faces)))
    return SceneObject(
        id=name,
        name=name,
        mesh=MeshData.of(mesh, painted),
        plate=plate,
        material_slots=list(slots),
    )


@pytest.mark.parametrize("from_spool", [False, True])
def test_print_advice_uses_the_actual_body_material(qt_app, from_spool):
    """Die PLA-Projektvorgabe darf eine TPU-Dichtung nicht ohne Geschwindigkeitsrat lassen."""
    body = _print_advice_cube(
        slots=(MaterialSlot(0, "TPU Schwarz", material_type="TPU"),) if from_spool else ()
    )
    if not from_spool:
        body.material = "tpu-95a"
    dialog = _print_advice_dialog(qt_app, [body])
    assert not dialog.apply_button.isEnabled(), "ohne Messung gibt es keine Entwarnung"
    assert dialog.advice_state.text()
    _wait_for_print_advice(dialog, qt_app)
    assert any(
        entry.path == "speed.outer_wall" and entry.value == 30 for entry in dialog._current_advice()
    )


def test_cura_takes_the_channel_advice_like_the_orca_family(qt_app, monkeypatch):
    """*Kanäle frei halten* ist bei Cura seit Stufe D ein Vorschlag zum Übernehmen.

    Bis zum 27.09.2026 nahm Cura die Stützsperre nicht an, und die Zeile stand
    nicht anhakbar mit dem Handgriff im Cura-Fenster da (an der Okarina hatten
    53 m Stütze die Kanäle gefüllt, ohne dass der Dialog es erwähnte). Jetzt
    reist die Sperre zu CuraEngine als eigenes Netz mit ``anti_overhang_mesh``
    (``slicer_keys.takes_mesh_settings``); für das Fenster nennt der Befund der
    Übergabe den Handgriff.
    """
    from app.core.types import SettingAdvice

    dialog = _print_advice_dialog(qt_app, [_print_advice_cube()])
    _wait_for_print_advice(dialog, qt_app)
    advice = SettingAdvice(
        path="support.block_channels", value=True, was=False, reason="Kanäle im Teil"
    )
    dialog._advice_entries = [advice]

    for flavour in ("cura", "orca"):
        monkeypatch.setattr(dialog, "_current_flavour", lambda chosen=flavour: chosen)
        assert dialog._current_advice() == [advice], flavour


@pytest.mark.parametrize("flavour", [None, "cura", "orca", "prusa"])
def test_the_advice_without_bodies_keeps_material_reasons_before_filtering_flow(flavour):
    """B7: Auch der synchrone Dialoganschluss muss die Slicerfähigkeit kennen.
    Nur den fertigen Rat zu filtern verlor bei kleinem Durchsatz den TPU-Grund.
    Die Prüfung ruft die fachlichen Methoden auf; sie erzeugt kein Fenster."""
    profile = profiles.make_profile("bambu-p1s", "tpu-95a")
    settings = print_settings.with_path(print_settings.resolve(profile), "speed.outer_wall", 200.0)
    settings = print_settings.with_path(settings, "filament.max_flow", 0.6)
    owner = SimpleNamespace(
        _settling=False,
        _stock_revision=0,
        _stock_timer=SimpleNamespace(start=lambda: None),
        _check_print_result=lambda: None,
        _plate_bodies=list,
        _advice_request=None,
        _advice_worker=None,
        _advice_timer=SimpleNamespace(stop=lambda: None),
        settings=settings,
        session=SimpleNamespace(profile=profile),
        slice_result=None,
        _show_advice=lambda: None,
        _current_flavour=lambda: flavour,
        _slicer_path=None,
        _foundation_for_current_setup=lambda: print_dialog.manufacturer.Foundation(settings),
    )

    PrintSettingsDialog._refresh_advice(owner)
    shown = PrintSettingsDialog._current_advice(owner)

    outer = [entry for entry in shown if entry.path == "speed.outer_wall"]
    assert len(outer) == 1
    expected = 30.0 if flavour in ("orca", "prusa") else print_settings.flow_speed_limit(settings)
    assert outer[0].value == pytest.approx(expected)


def test_the_flow_cap_is_offered_only_where_the_slicer_does_not_cap(qt_app, monkeypatch):
    """Die Orca-Familie und PrusaSlicer deckeln das Tempo selbst nach dem
    Volumenstrom des Filaments. Dort ändert der Vorschlag nichts am Druck, und
    an der Kobra 2 hob er über die Innenwand die Lückenfüllung von 100 auf
    142 mm/s (Gesamtprüfung, 27.09.2026). Cura deckelt nicht: Dort bleibt er."""
    from app.core.slice import advise
    from app.core.types import SettingAdvice

    dialog = _print_advice_dialog(qt_app, [_print_advice_cube()])
    _wait_for_print_advice(dialog, qt_app)
    cap = SettingAdvice(
        path="speed.inner_wall", value=142.0, was=150.0, reason=advise.FLOW_LIMIT_REASON
    )
    walls = SettingAdvice(path="shell.wall_count", value=3, was=2, reason="Dünne Wand")
    dialog._advice_entries = [cap, walls]

    for flavour, shown in (("orca", [walls]), ("prusa", [walls]), ("cura", [cap, walls])):
        monkeypatch.setattr(dialog, "_current_flavour", lambda chosen=flavour: chosen)
        assert dialog._current_advice() == shown, flavour


def test_print_advice_cannot_disable_support_needed_by_another_body(qt_app):
    """Der Würfel braucht keine Stützen; der Kegel auf derselben Platte behält sie."""
    import math

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.geom.transform import place_on_bed

    cube = _print_advice_cube()
    mesh = trimesh.creation.cone(radius=20, height=10, sections=32)
    mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
    cone = SceneObject(id="Kegel", name="Kegel", mesh=place_on_bed(MeshData.of(mesh)))
    # Eine eigene Wahl: ohne Herkunft wäre „grid" seit Stufe A Grundlage und
    # käme beim Öffnen aus dem Profil.
    settings = print_settings.with_choice(
        print_settings.resolve(profiles.make_profile()), "support.style", "grid"
    )
    dialog = _print_advice_dialog(qt_app, [cube, cone], settings=settings)
    _wait_for_print_advice(dialog, qt_app)
    assert set(dialog._body_analyses) == {cube.id, cone.id}
    dialog._apply_advice()
    assert dialog.settings.support.style == "grid"


def test_print_advice_ignores_other_plates_and_keeps_a_rejected_choice(qt_app):
    """Ein ausgeschlossener Zapfen erhöht keine Wandzahl; Abwahl überlebt neue Werte."""
    cube = _print_advice_cube(slots=(MaterialSlot(0, "TPU", material_type="TPU"),))
    pin = _print_advice_cube("Zapfen", plate=1)
    pin.features["pin"] = Feature(
        id="pin", kind="pin", provenance="generated", params={"diameter": 20.0}
    )
    dialog = _print_advice_dialog(qt_app, [cube, pin])
    index = dialog.plate_choice.findData(0)
    dialog.plate_choice.setCurrentIndex(index)
    dialog._plate_chosen(index)
    _wait_for_print_advice(dialog, qt_app)
    assert dialog._connector_diameters() == ()
    assert set(dialog._body_analyses) == {cube.id}
    assert not any(entry.path == "shell.wall_count" for entry in dialog._current_advice())
    for row in range(dialog.advice_view.topLevelItemCount()):
        item = dialog.advice_view.topLevelItem(row)
        if item.data(0, Qt.ItemDataRole.UserRole) == "speed.outer_wall":
            item.setCheckState(0, Qt.CheckState.Unchecked)
    before = dialog.settings.speed.outer_wall
    dialog._editors["infill.density"].setValue(27)
    _wait_for_print_advice(dialog, qt_app)
    dialog._apply_advice()
    assert dialog.settings.speed.outer_wall == before


def test_print_advice_keeps_its_layers_when_only_the_advice_changes(qt_app, monkeypatch):
    """DRUCK-14: Ein geänderter Rat bricht den Schnitt nicht ab.

    Gleich nach dem Öffnen kommen Maschine, Prozess und Filament aus der
    Profilsuche nach; jedes ändert den Auftrag. Bis zur Durchsicht 0.5.1 brach
    das den laufenden Schnitt ab, und der nächste Arbeiter schnitt denselben
    Körper noch einmal. Hier ändert ein Feld den Rat, während geschnitten wird:
    geschnitten wird einmal, und der Rat gilt dem neuen Stand.
    """
    from app.core.types import SliceResult
    from app.ui import print_settings_dialog as module

    entered = threading.Event()
    release = threading.Event()
    calls = []

    def measure(mesh, height, **_rest):
        calls.append(height)
        entered.set()
        assert release.wait(5)
        return SliceResult(layers=(), support_volume=0, first_layer_area=100)

    monkeypatch.setattr(module, "slice_body", measure)
    dialog = _print_advice_dialog(qt_app, [_print_advice_cube()])
    dialog._start_advice()
    assert entered.wait(3)
    running = dialog._advice_worker
    dialog._editors["infill.density"].setValue(31)
    assert running is not None and not running.cancelled.is_cancelled
    assert not running.rules_wanted, "er misst weiter, sein Rat ist überholt"
    release.set()
    _wait_for_print_advice(dialog, qt_app)

    assert len(calls) == 1, "dieselbe Geometrie wird nur einmal geschnitten"
    assert dialog._advice_request == dialog._advice_context()
    # Das Feld spricht Prozent, der Kern rechnet Anteile (``Field.factor``).
    assert dialog.settings.infill.density == pytest.approx(0.31)


def test_print_advice_takes_the_layers_the_report_already_has(qt_app, monkeypatch):
    """DRUCK-14: Hat der Prüfbericht dieselben Schichten, schneidet der Dialog nicht.

    Nach dem Laden rechnet der Prüfbericht die Schichtanalyse jedes Körpers mit
    demselben Raster, Winkel und derselben Brückenbreite (``findings.analysed``).
    Am Bohrmaschinenhalter schnitt der Dialog sie danach noch einmal, 2,3 s.
    """
    from app.core.types import SliceResult
    from app.ui import print_settings_dialog as module

    known = SliceResult(layers=(), support_volume=12.0, first_layer_area=100)
    asked = []

    def remembered(mesh, settings, angle, wall):
        asked.append((angle, wall))
        return known

    def measure(*_args, **_kwargs):
        raise AssertionError("die Schichten des Prüfberichts genügen")

    monkeypatch.setattr(module, "remembered_analysis", remembered)
    monkeypatch.setattr(module, "slice_body", measure)
    dialog = _print_advice_dialog(qt_app, [_print_advice_cube()])
    dialog._start_advice()
    _wait_for_print_advice(dialog, qt_app)

    assert asked and all(angle > 0.0 and wall > 0.0 for angle, wall in asked)
    assert dialog.slice_result is known


def test_print_advice_restarts_for_actual_layers_and_rejects_cancelled_results(qt_app, monkeypatch):
    """Ein neuer Schichtwert löst den alten Auftrag ab, auch wenn dessen Ergebnis schon wartet."""
    from app.core.types import SliceResult
    from app.ui import print_settings_dialog as module

    entered = threading.Event()
    release = threading.Event()
    calls = []

    def measure(
        mesh, height, *, first_layer_height, overhang_angle, bridge_from, cancelled, support_volume
    ):
        # ``bridge_from`` ausdrücklich in der Signatur und nicht in ``**kwargs``:
        # Die Attrappe soll rot werden, wenn der Dialog die Zahl nicht mehr
        # hereingibt — sie kommt seit RM-097 aus dem Material.
        assert bridge_from > 0.0
        # Und die Säulen bleiben aus: Die Vorschläge lesen sie nicht, und an
        # einem Gitterbecher waren sie ein Drittel der Wartezeit (19.09.2026).
        assert support_volume is False
        calls.append((height, first_layer_height, threading.get_ident()))
        if len(calls) == 1:
            entered.set()
            assert release.wait(5)
        return SliceResult(layers=(), support_volume=0, first_layer_area=100)

    monkeypatch.setattr(module, "slice_body", measure)
    dialog = _print_advice_dialog(qt_app, [_print_advice_cube()])
    initial = (dialog.settings.layers.layer_height, dialog.settings.layers.first_layer_height)
    dialog._start_advice()
    assert entered.wait(3)
    qt_app.processEvents()
    assert "Würfel" in dialog.advice_state.text()
    assert not dialog.advice_progress.isHidden()
    assert dialog.advice_progress.maximum() == 0
    dialog._editors["layers.layer_height"].setValue(0.12)
    dialog._editors["layers.first_layer_height"].setValue(0.32)
    release.set()
    _wait_for_print_advice(dialog, qt_app)
    assert [(height, first) for height, first, _ in calls] == [initial, (0.12, 0.32)]
    assert all(thread_id != threading.get_ident() for _, _, thread_id in calls)
    assert dialog._analysed_context == dialog._analysis_context()
    dialog._editors["infill.density"].setValue(28)
    _wait_for_print_advice(dialog, qt_app)
    assert len(calls) == 2, "eine Fülldichteänderung verlangt keine neue Schichtgeometrie"


def test_print_advice_remembers_measured_layers_across_dialogs(qt_app, monkeypatch):
    """Befund Robert, 19.09.2026: „Vorschläge beim Slicen dauern ewig."

    Der Dialog wird bei jedem Öffnen neu gebaut und schnitt jeden Körper
    jedes Mal neu. Die Sitzung behält jetzt den letzten gemessenen Stand; ein
    zweiter Dialog über dieselben Körper und Schichten fragt die Geometrie
    nicht noch einmal. Ein anderes Netz oder eine andere Schichthöhe schon.
    """
    from types import SimpleNamespace

    from app.core.types import SliceResult
    from app.ui import print_settings_dialog as module

    calls: list[tuple[float, float]] = []

    def measure(mesh, height, *, first_layer_height, **_rest):
        calls.append((height, first_layer_height))
        return SliceResult(layers=(), support_volume=0, first_layer_area=100)

    monkeypatch.setattr(module, "slice_body", measure)
    cube = _print_advice_cube()
    first = _print_advice_dialog(qt_app, [cube])
    session = first.session
    first._start_advice()
    _wait_for_print_advice(first, qt_app)
    assert len(calls) == 1, "der erste Dialog misst"
    first.close()
    qt_app.processEvents()

    second = PrintSettingsDialog(session, UiSettings())
    assert second.wait_for_slicers()
    second._start_advice()
    _wait_for_print_advice(second, qt_app)
    assert len(calls) == 1, "der zweite Dialog bekommt die Schichten aus der Sitzung"
    assert second._body_analyses, "und hat sie als seinen Stand"
    second.close()
    qt_app.processEvents()

    # Ein anderes Netz unter derselben Kennung ist ein anderer Körper.
    other = _print_advice_cube()
    session.last_result = _shown_result(SimpleNamespace(objects={other.id: other}))
    third = PrintSettingsDialog(session, UiSettings())
    assert third.wait_for_slicers()
    third._start_advice()
    _wait_for_print_advice(third, qt_app)
    assert len(calls) == 2, "ein neues Netz wird gemessen"
    third.close()
    qt_app.processEvents()


def test_accepted_material_advice_preserves_the_effective_filament_group(qt_app):
    """Die angenommene Kühlzeit schreibt einen SlotOverride und behält dessen übrige Kühlung."""
    slot = MaterialSlot(0, "PLA Schwarz", material_type="PLA")
    settings = print_settings.resolve(profiles.make_profile())
    settings = handover.with_slot_override(
        settings,
        slot,
        SlotOverride(
            cooling=replace(settings.cooling, minimum_layer_time=0, fan_speed=0.43),
        ),
    )
    dialog = _print_advice_dialog(qt_app, [_print_advice_cube(slots=(slot,))], settings=settings)
    _wait_for_print_advice(dialog, qt_app)
    assert any(entry.path == "cooling.minimum_layer_time" for entry in dialog._current_advice())
    dialog._apply_advice()
    effective = handover.settings_for_slot(dialog.settings, dialog.session.profile, slot)
    assert effective.cooling.minimum_layer_time > 0
    assert effective.cooling.fan_speed == pytest.approx(0.43)
    assert handover.override_for(dialog.settings, slot).cooling == effective.cooling


def test_print_advice_uses_manufacturer_flow_and_keeps_other_manufacturer_values(
    qt_app,
    monkeypatch,
    tmp_path,
):
    """Herstellerwerte begrenzen den Rat; eine angenommene Kühlzeit erhält deren Nachbarwerte.

    Den Tempodeckel nach dem Volumenstrom bietet der Dialog für die
    Orca-Familie nicht an (``slicer_keys.caps_volumetric_speed``): Der Slicer
    deckelt selbst nach dem Volumenstrom, den er bekommt, und der Deckel hob an
    der Kobra 2 die Lückenfüllung des Herstellers an (27.09.2026). Die
    Außenwand bleibt deshalb, und der Volumenstrom des Herstellers geht mit.
    """
    profile = tmp_path / "maker.json"
    profile.write_text(
        json.dumps(
            {
                "type": "filament",
                "name": "Maker PLA",
                "filament_type": ["PLA"],
                "nozzle_temperature": ["215"],
                "fan_min_speed": ["43"],
                "fan_max_speed": ["43"],
                "slow_down_layer_time": ["0"],
                "filament_max_volumetric_speed": ["0.6"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        handover,
        "profile_source",
        lambda *_args: SlicerProfile(profile, "Maker PLA", "filament", from_user=True),
    )
    monkeypatch.setattr(handover, "_profile_roots", lambda *_args: (tmp_path,))
    slot = MaterialSlot(0, "Maker PLA", material="Maker PLA", material_type="PLA")
    dialog = _print_advice_dialog(qt_app, [_print_advice_cube(slots=(slot,))])
    dialog._slicer_path = Path("orca-slicer.exe")
    dialog._refresh_advice()
    _wait_for_print_advice(dialog, qt_app)
    before = dialog.settings.speed.outer_wall
    dialog._apply_advice()
    setup = handover.SlicerSetup(Path("orca-slicer.exe"), "orca")
    effective = handover.settings_for_slot(dialog.settings, dialog.session.profile, slot, setup)
    assert dialog.settings.speed.outer_wall == pytest.approx(before), "Orca deckelt selbst"
    assert effective.filament.max_flow == pytest.approx(0.6)
    assert effective.temperature.nozzle == 215
    assert effective.cooling.fan_speed == pytest.approx(0.43)
    assert effective.cooling.minimum_layer_time > 0
    assert handover.override_for(dialog.settings, slot).cooling == effective.cooling


@pytest.mark.parametrize("when", ["before_open", "field_change"])
def test_empty_print_dialog_explains_an_impossible_flow_and_recovers(qt_app, when):
    """Auch ohne Modell bleiben ungültige Empfehlungen sichtbar korrigierbar.

    Vor dem Öffnen gesetzt heißt: früher selbst gewählt. Ohne Herkunft wären
    die Werte seit Stufe A Grundlage und kämen beim Öffnen aus dem Profil.
    """
    session = Session()
    settings = print_settings.resolve(session.profile)
    invalid = settings
    for path, value in (
        ("layers.layer_height", 0.8),
        ("layers.line_width", 2.0),
        ("filament.max_flow", 0.5),
    ):
        invalid = print_settings.with_choice(invalid, path, value)
    if when == "before_open":
        session.set_print_settings(invalid)
    dialog = PrintSettingsDialog(session, UiSettings())
    if when == "field_change":
        dialog._editors["layers.layer_height"].setValue(0.8)
        dialog._editors["layers.line_width"].setValue(2.0)
        dialog._editors["filament.max_flow"].setValue(0.5)
    assert dialog.settings.filament.max_flow == pytest.approx(0.5)
    assert "Volumenstrom" in dialog.advice_state.text()
    assert "Verringern" in dialog.advice_state.text()
    assert not dialog.advice_state.isHidden()
    assert not dialog.apply_button.isEnabled()
    assert dialog.advice_view.topLevelItemCount() == 0
    assert dialog.advice_control.text() == tr("Erneut prüfen")
    dialog.advice_control.click()
    assert "Volumenstrom" in dialog.advice_state.text()
    dialog._editors["filament.max_flow"].setValue(12.0)
    assert not dialog._advice_problem
    assert dialog.advice_state.isHidden()
    assert dialog._current_advice()
    dialog.reject()


@pytest.mark.parametrize("known_problem", [False, True])
def test_print_advice_failure_has_a_retry_and_never_claims_the_part_is_ready(
    qt_app,
    monkeypatch,
    known_problem,
):
    """Eine fehlende Analyse bleibt sichtbar unvollständig und kann neu angefordert werden."""
    from app.core.errors import ValidationError
    from app.core.types import SliceResult
    from app.ui import print_settings_dialog as module

    attempts = []

    def measure(*_args, **_kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            if known_problem:
                raise ValidationError(field="temperature.nozzle", detail="Ungültiges Profil <NaN>.")
            raise ValueError("review analysis failure")
        return SliceResult(layers=(), support_volume=0, first_layer_area=100)

    monkeypatch.setattr(module, "slice_body", measure)
    dialog = _print_advice_dialog(qt_app, [_print_advice_cube()])
    deadline = time.monotonic() + 5
    while dialog._advice_pending and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.005)
    assert dialog._advice_problem
    assert ("<NaN>" if known_problem else "review analysis failure") in dialog.advice_state.text()
    assert dialog.advice_state.textFormat() == Qt.TextFormat.PlainText
    assert not dialog.apply_button.isEnabled()
    assert dialog.advice_control.text() == tr("Erneut prüfen")
    assert dialog.advice_view.topLevelItemCount() == 0
    dialog.advice_control.click()
    _wait_for_print_advice(dialog, qt_app)
    assert len(attempts) == 2


def test_print_advice_offers_executable_actions_and_removes_stale_buttons(qt_app, monkeypatch):
    """Ein Analysefehler reicht seinen konkreten Rückweg und dieselben Fehlerdaten weiter."""
    from app.core.errors import Action, AppError
    from app.ui import print_settings_dialog as module

    problem = AppError(
        detail="Profil konnte nicht gelesen werden <Datei>.",
        suggestions=[
            Action("show_output", "Ausgabe ansehen"),
            Action("manual_help", "Profil im Slicer prüfen"),
            Action("cancel", "Abbrechen"),
        ],
    )

    def fail(*_args, **_kwargs):
        raise problem

    monkeypatch.setattr(module, "slice_body", fail)
    dialog = _print_advice_dialog(qt_app, [_print_advice_cube()])
    handled = []
    monkeypatch.setattr(dialog, "error_handlers", lambda: {"show_output": handled.append})
    deadline = time.monotonic() + 5
    while dialog._advice_pending and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.005)
    actions = [
        button
        for button in dialog.findChildren(QPushButton)
        if button.text() == "Ausgabe ansehen" and not button.isHidden()
    ]
    assert len(actions) == 1
    assert "Ausgabe ansehen" not in dialog.advice_state.text()
    assert "Profil im Slicer prüfen" in dialog.advice_state.text()
    assert "Abbrechen" not in dialog.advice_state.text()
    actions[0].click()
    assert handled == [problem]
    dialog._editors["layers.layer_height"].setValue(0.3)
    assert actions[0].isHidden()
    actions[0].click()
    assert handled == [problem]
    dialog.reject()


def test_cancelled_print_advice_keeps_its_state_when_a_late_error_arrives(qt_app, monkeypatch):
    """Ein überholter Fehler ersetzt weder den Abbruch noch den ausdrücklichen Neuversuch."""
    from app.core.errors import ValidationError
    from app.ui import print_settings_dialog as module

    entered = threading.Event()
    release = threading.Event()

    def measure(*_args, **_kwargs):
        entered.set()
        assert release.wait(5)
        raise ValidationError(field="temperature.nozzle", detail="Überholter Profilfehler")

    monkeypatch.setattr(module, "slice_body", measure)
    dialog = _print_advice_dialog(qt_app, [_print_advice_cube()])
    dialog._start_advice()
    assert entered.wait(3)
    dialog.advice_control.click()
    cancelled_message = dialog.advice_state.text()
    release.set()
    deadline = time.monotonic() + 5
    while dialog._advice_worker is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.005)
    assert dialog._advice_worker is None
    assert dialog.advice_state.text() == cancelled_message
    assert not dialog._advice_pending
    assert not dialog.apply_button.isEnabled()


def test_closing_cancels_the_print_advice_worker_without_waiting_in_qt(qt_app, monkeypatch):
    """Der Schließweg lässt keine Geometriearbeit hinter einem verschwundenen Dialog zurück."""
    from app.core.types import SliceResult
    from app.ui import print_settings_dialog as module

    entered = threading.Event()
    release = threading.Event()
    tokens = []

    def measure(*_args, cancelled, **_kwargs):
        tokens.append(cancelled)
        entered.set()
        assert release.wait(5)
        return SliceResult(layers=(), support_volume=0, first_layer_area=100)

    monkeypatch.setattr(module, "slice_body", measure)
    dialog = _print_advice_dialog(qt_app, [_print_advice_cube()])
    dialog._start_advice()
    assert entered.wait(3)
    started = time.monotonic()
    dialog.reject()
    elapsed = time.monotonic() - started
    release.set()
    dialog.wait_for_workers(2000)
    qt_app.processEvents()
    assert elapsed < 0.25
    assert tokens[0].is_cancelled
    assert dialog._settled


def test_a_slot_profile_choice_invalidates_visible_print_advice_immediately(qt_app):
    """Die Herkunft eines Filaments ändert den Rat schon vor dem nächsten Übernahmeklick."""
    slots = (
        MaterialSlot(0, "Rot", material_type="PLA"),
        MaterialSlot(1, "Weiß", material_type="PLA"),
    )
    dialog = _print_advice_dialog(qt_app, [_print_advice_cube(slots=slots)])
    _wait_for_print_advice(dialog, qt_app)
    previous = dialog._advice_request
    box = dialog.slot_rows[0][1]
    box.addItem("Neues PLA", "Neues PLA")
    box.setCurrentIndex(0)
    dialog._slot_filament_chosen(0)
    assert dialog._advice_pending
    assert not dialog.apply_button.isEnabled()
    assert dialog._advice_request != previous
    assert dialog._advice_request == dialog._advice_context()


def test_a_changed_scene_replaces_slot_rows_on_the_same_plate(qt_app):
    """Eine andere Körperbelegung auf derselben Platte behält keine verwaisten Filamentzeilen."""
    from types import SimpleNamespace

    slots = (
        MaterialSlot(0, "Rot", material_type="PLA"),
        MaterialSlot(1, "Weiß", material_type="PLA"),
    )
    dialog = _print_advice_dialog(qt_app, [_print_advice_cube(slots=slots)])
    assert len(dialog.slot_rows) == 2
    green = _print_advice_cube(slots=(MaterialSlot(0, "Grün", material_type="PLA"),))
    dialog.session.last_result = _shown_result(SimpleNamespace(objects={green.id: green}))
    dialog.session.sceneChanged.emit(dialog.session.last_result)
    assert not dialog.slot_rows
    assert not dialog._slot_names
    assert "Grün" in dialog.material_state.text()
    assert all(
        "Rot" not in str(key) and "Weiß" not in str(key) for key in dialog._slot_rows_context
    )


def test_secondary_filament_advice_is_visible_but_not_applicable_in_prusa(qt_app):
    """Eine Empfehlung an den zweiten Extruder darf nicht als übertragbar erscheinen."""
    import trimesh

    from app.core.geom.mesh import MeshData

    red = MaterialSlot(0, "Rot", material_type="PLA")
    white = MaterialSlot(0, "Weiß", material_type="PLA")
    large = _print_advice_cube("Groß", slots=(red,))
    large.mesh = MeshData.of(trimesh.creation.box((40, 40, 10)))
    small = _print_advice_cube("Klein", slots=(white,))
    # Eine eigene Wahl: ohne Herkunft wäre der Rand seit Stufe A Grundlage, und
    # der Vorschlag für den kleinen Würfel stünde als übertragbar daneben.
    settings = print_settings.with_choice(
        print_settings.resolve(profiles.make_profile()), "adhesion.kind", "brim"
    )
    # Ohne Mindestzeit je Schicht, damit der kleine Würfel einen Rat für seine
    # Spule bekommt (``advise`` schlägt sie nur vor, wo keine gilt).
    settings = print_settings.with_choice(settings, "cooling.minimum_layer_time", 0.0)
    dialog = _print_advice_dialog(qt_app, [large, small], settings=settings)
    dialog._slicer_path = Path("PrusaSlicer.exe")
    dialog._refresh_advice()
    _wait_for_print_advice(dialog, qt_app)
    white_advice = next(
        entry
        for entry in dialog._current_advice()
        if entry.path == "cooling.minimum_layer_time" and entry.slot.name == "Weiß"
    )
    assert white_advice.unavailable
    assert not dialog.apply_button.isEnabled()
    assert "erste Filament" in dialog.apply_button.toolTip()
    dialog._apply_advice()
    assert handover.override_for(dialog.settings, white) is None
    assert any(
        "erste Filament" in dialog.advice_view.topLevelItem(row).toolTip(0)
        and not dialog.advice_view.topLevelItem(row).flags() & Qt.ItemFlag.ItemIsUserCheckable
        for row in range(dialog.advice_view.topLevelItemCount())
    )


def test_direct_export_uses_the_remembered_quality(session: Session) -> None:
    """Ein ungeöffneter Druckdialog darf die gewählte Feinheit nicht verlieren."""
    settings = settings_for_export(
        session.project.document, session.profile, UiSettings(print_quality="fine")
    )
    assert settings is not None and settings.quality == "fine"
    assert settings.layers == print_settings.resolve(session.profile, "fine").layers


def test_late_profile_signals_cannot_replace_a_newer_slicer(dialog: PrintSettingsDialog) -> None:
    """Ein verspäteter Fund und sein finished gehören weiter zum alten Slicer."""
    from app.ui.print_settings_dialog import _ProfileWorker

    old = _ProfileWorker(Path("old.exe"), "orca")
    current = _ProfileWorker(Path("new.exe"), "orca")
    old.done.connect(dialog._profiles_found)
    old.finished.connect(dialog._profile_search_finished)
    dialog._profile_worker = current
    dialog._profiles_pending = True
    old.done.emit([_profile("Alter Drucker", "machine")])
    old.finished.emit()
    assert dialog._profiles == []
    assert dialog._profiles_pending
    assert dialog._profile_worker is current
    dialog._profile_worker = None


def _calibrated_advice_case(monkeypatch):
    """Ein 55-Grad-Überhang mit einer passenden 60-Grad-PLA-Probe."""
    import math

    import trimesh

    from app.core.geom.mesh import MeshData

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    original = profiles.material
    calibrated = replace(
        original("pla"),
        overhang_angle=60.0,
        calibration_printer=profile.printer.id,
        calibration_nozzle_diameter=profile.printer.nozzle_diameter,
        calibration_layer_height=settings.layers.layer_height,
        calibration_extrusion_width=settings.layers.line_width,
    )
    monkeypatch.setattr(
        profiles,
        "material",
        lambda identifier: calibrated if identifier == "pla" else original(identifier),
    )
    mesh = trimesh.creation.box((8, 8, 8))
    mesh.apply_translation((0, 0, 4))
    mesh.vertices[:, 0] += mesh.vertices[:, 2] * math.tan(math.radians(55))
    body = SceneObject(
        id="slope",
        name="Schräges Teil",
        mesh=MeshData.of(mesh),
        material_slots=[MaterialSlot(0, "PLA", material_type="PLA")],
    )
    return profile, settings, body


def test_print_advice_reanalyses_when_line_width_invalidates_the_overhang_calibration(
    qt_app, monkeypatch
):
    """Die Schichtgeometrie folgt der Probe, bis eine andere Bahnbreite sie ungültig macht."""
    from app.ui import print_settings_dialog as module

    _profile, settings, body = _calibrated_advice_case(monkeypatch)
    measure = module.slice_body
    calls = []

    def recorded(*args, **kwargs):
        calls.append((kwargs["overhang_angle"], threading.get_ident()))
        return measure(*args, **kwargs)

    monkeypatch.setattr(module, "slice_body", recorded)
    dialog = _print_advice_dialog(qt_app, [body], settings=settings)
    _wait_for_print_advice(dialog, qt_app)
    calibrated = dialog.slice_result
    assert calibrated is not None
    # Am Überhang gemessen, nicht am Stützvolumen: Die Vorschläge lassen die
    # Stützsäulen seit dem 19.09.2026 aus (``support_volume=False``), die
    # Überhangflächen je Schicht messen sie weiter — und die folgen dem Winkel.
    assert total_overhang(calibrated) == pytest.approx(0.0, abs=1e-6)
    assert calls[0][0] == pytest.approx(60.0)
    dialog._editors["infill.density"].setValue(28)
    _wait_for_print_advice(dialog, qt_app)
    assert len(calls) == 1
    dialog._editors["layers.line_width"].setValue(settings.layers.line_width + 0.05)
    _wait_for_print_advice(dialog, qt_app)
    assert [angle for angle, _thread in calls] == pytest.approx([60.0, 45.0])
    assert all(worker_thread != threading.get_ident() for _angle, worker_thread in calls)
    assert total_overhang(dialog.slice_result) > total_overhang(calibrated)


@pytest.mark.parametrize("change", ["material", "printer", "mixed_materials"])
def test_print_advice_rechecks_the_strictest_slot_calibration_when_reusing_geometry(
    qt_app, monkeypatch, change
):
    """Ein früherer großzügiger Winkel gilt weder für PETG noch für einen anderen Drucker."""
    from app.ui.print_settings_dialog import _AdviceWorker

    profile, settings, body = _calibrated_advice_case(monkeypatch)
    results = []

    def calculate(previous):
        worker = _AdviceWorker((body,), settings, profile, None, {}, (), (), previous)
        worker.done.connect(lambda _entries, measured: results.append(measured))
        worker.work()
        assert results
        return results[-1]

    measured = calculate({})
    assert measured[body.id][0] == pytest.approx(60.0)
    # Der Messwertspeicher trägt seit RM-097 drei Werte: Winkel, Mindestwand
    # (zugleich die Brückenbreite) und das Ergebnis. Beide Grenzen stehen im
    # Schlüssel, denn ``_analysis_context`` kennt die Materialien nicht.
    initial = measured[body.id][2]
    first_wall = measured[body.id][1]
    if change == "material":
        body.material_slots = [MaterialSlot(0, "PETG", material_type="PETG")]
    elif change == "printer":
        profile = replace(profile, printer=replace(profile.printer, id="different-printer"))
    else:
        body.material_slots.append(MaterialSlot(1, "PETG", material_type="PETG"))
        body.mesh = replace(body.mesh, slots=(0, 1) * (body.mesh.triangle_count // 2))
    repeated = calculate(measured)
    assert len(results) == 2
    assert repeated[body.id][0] == pytest.approx(45.0)
    assert repeated[body.id][2] is not initial
    assert total_overhang(repeated[body.id][2]) > total_overhang(initial), (
        "ein strengerer Winkel sieht mehr Überhang — die Säulen darunter lassen die Vorschläge aus"
    )
    assert repeated[body.id][1] > 0.0 and first_wall > 0.0, (
        "die Brückenbreite steht neben dem Winkel im Schlüssel (RM-097)"
    )


@pytest.mark.parametrize("flavour", ["cura", "prusa"])
def test_direct_3mf_export_preserves_format_and_native_settings(
    qt_app: QApplication,
    session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flavour: str,
) -> None:
    """Die Dateiwahl gilt auch bei einem Slicer mit anderem Eingabeformat."""
    import zipfile

    from app.ui import main_window

    setup = handover.SlicerSetup(tmp_path / "slicer.exe", flavour)
    monkeypatch.setattr(main_window, "remembered_setup", lambda *args: setup)
    worker = main_window._ExportWorker(
        [_cube_object()],
        tmp_path / "chosen.3mf",
        "3mf",
        profile=session.profile,
        sources={},
        settings=print_settings.resolve(session.profile),
        ui_settings=UiSettings(),
        material=session.profile.material.id,
    )
    paths, _findings = worker._assembly()
    assert paths == [tmp_path / "chosen.3mf"]
    with zipfile.ZipFile(paths[0]) as archive:
        assert "3D/3dmodel.model" in archive.namelist()
        if flavour == "prusa":
            assert "Metadata/Slic3r_PE.config" in archive.namelist()


@pytest.mark.parametrize("language", ["en", "es", "fr", "it", "pt"])
def test_top_surface_speed_uses_its_context_in_the_built_dialog(
    session: Session, language: str
) -> None:
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language, read_catalog

    previous = get_language()
    install_language(language)
    set_language(language)
    built = PrintSettingsDialog(session, UiSettings())
    try:
        expected = read_catalog(language)["Druckgeschwindigkeit\x04Oberfläche"]
        field = next(field for field in FIELDS if field.path == "speed.top_surface")
        assert str(field.title) == expected
        assert expected in {label.text() for label in built.findChildren(QLabel)}
    finally:
        built.close()
        built.deleteLater()
        set_language(previous)


def test_a_resin_printer_reduces_the_dialog_to_what_applies_and_a_switch_brings_it_back(
    qt_app: QApplication, session: Session
) -> None:
    """RM-071: An einem Resin-Drucker zeigt der Dialog nur, was gilt — und ein
    Wechsel auf einen Filamentdrucker bringt Stufe, Felder, Vorschläge und
    Slicen zurück, samt dem Material des Verfahrens."""
    session.start_new(profiles.DEFAULT_RESIN_PRINTER, profiles.DEFAULT_RESIN_MATERIAL)
    assert session.profile.printer.is_resin
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    try:
        hidden = (
            dialog.front_box,
            dialog.tabs_box,
            dialog.advice_box,
            dialog.quality,
            dialog.nozzle_control,
            dialog.nozzle_choice,
            dialog.nozzle_count,
            dialog.share_settings,
            dialog.slice_button,
            dialog.save_button,
            dialog.search,
        )
        assert all(widget.isHidden() for widget in hidden)
        assert not dialog.nozzle_state.isVisibleTo(dialog)
        assert not dialog.open_button.isHidden() and not dialog.printer_choice.isHidden()
        assert dialog.filament_label.text() == tr("Material")
        assert dialog.open_button.font().bold(), "Öffnen ist der Hauptknopf"
        # Keine FDM-Werte in einer Datei für ein Harzbad.
        assert (
            settings_for_export(
                session.project.document,
                session.profile,
                UiSettings(print_settings_in_files=True),
            )
            is None
        )
        # Und kein Rat: die Liste bleibt leer, ohne dass ein Arbeiter rechnet.
        assert dialog._advice_entries == [] and not dialog._advice_pending

        dialog.printer_choice.setCurrentIndex(dialog.printer_choice.findData("centauri-carbon-2"))
        assert not session.profile.printer.is_resin
        assert session.profile.material.id == profiles.DEFAULT_MATERIAL, (
            "PLA statt Harz, sobald ein Filamentdrucker dasteht"
        )
        assert all(not widget.isHidden() for widget in hidden)
        assert dialog.nozzle_state.isVisibleTo(dialog)
        assert dialog.filament_label.text() == tr("Filamente")

        dialog.printer_choice.setCurrentIndex(
            dialog.printer_choice.findData(profiles.DEFAULT_RESIN_PRINTER)
        )
        assert session.profile.printer.is_resin
        assert session.profile.material.id == profiles.DEFAULT_RESIN_MATERIAL
        assert all(widget.isHidden() for widget in hidden)
        assert not dialog.nozzle_state.isVisibleTo(dialog)
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize("field", ["nozzle", "nozzle_count"])
def test_a_printer_that_cannot_be_saved_says_so_and_shows_what_holds(
    monkeypatch: pytest.MonkeyPatch, dialog: PrintSettingsDialog, field: str
) -> None:
    """Düse und Düsenzahl gehören dem Drucker und landen in seinem Profil —
    und das Schreiben kann scheitern.

    Die Ausnahme lief aus dem Slot heraus: kein Satz, und das Feld zeigte die
    neue Düse, während der Drucker mit der alten weiterrechnete (Regel 17).
    """
    from app.core.errors import FileWriteError

    def refuse(_entry: object) -> object:
        raise FileWriteError(detail="kein Platz")

    monkeypatch.setattr(profiles, "save_printer", refuse)
    before = profiles.printer(str(dialog.printer_choice.currentData()))
    if field == "nozzle":
        other = dialog.nozzle_choice.count() - 1
        dialog.nozzle_choice.setCurrentIndex(other)
        dialog.nozzle_choice.activated.emit(other)
        dialog.nozzle.set_value_mm(before.nozzle_diameter + 0.2)
        assert dialog.nozzle.value_mm() == pytest.approx(before.nozzle_diameter)
        message = dialog.nozzle_state.text()
    else:
        dialog.nozzle_count.setValue(before.nozzles + 1)
        assert dialog.nozzle_count.value() == before.nozzles
        message = dialog.state.text()
    assert "Drucker" in message and "speichern" in message
    assert profiles.printer(before.id) == before


def test_switching_print_tabs_keeps_the_outer_size_and_scrolls_the_current_page(
    dialog: PrintSettingsDialog, qt_app: QApplication
) -> None:
    """Ein Reiterwechsel springt nicht und aktualisiert die Rollfläche.

    Der Wechsel ist eine passive Änderung (RM-487): Eine höhere Seite darf den
    Rahmen bis zum Bildschirmrand unter dem Anker wachsen lassen, keine lässt
    ihn schrumpfen, Breite und Anker bleiben. Nach einem Durchgang steht der
    Rahmen. Geklappt wird erst nach der Anfangsmessung, wie beim Kunden: Vorher
    ging die Klappe in der Anfangsmessung auf, der Dialog war ohne Anker und
    rückte beim ersten höheren Reiter hinauf.
    """
    dialog.show()
    for _ in range(16):
        qt_app.processEvents()
    assert dialog._content_height.initial_fit_done
    assert dialog.tabs_toggle is not None
    dialog.tabs_toggle.setChecked(True)
    for _ in range(16):
        qt_app.processEvents()
    width = dialog.width()
    anchor = dialog.frameGeometry().topLeft()
    bottom = dialog.screen().availableGeometry().bottom()
    height = dialog.height()
    for index in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(index)
        for _ in range(16):
            qt_app.processEvents()
        assert dialog.width() == width
        assert dialog.height() >= height, "ein Reiterwechsel nimmt keine Höhe zurück"
        assert dialog.frameGeometry().topLeft() == anchor
        assert dialog.frameGeometry().bottom() <= bottom
        height = dialog.height()
        page = dialog.tabs.currentWidget()
        assert page is not None and page.isVisibleTo(dialog)
    settled = dialog.size()
    for index in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(index)
        for _ in range(16):
            qt_app.processEvents()
        assert dialog.size() == settled, dialog.tabs.tabText(index)
    assert dialog.width() >= dialog._room_for_tabs()
    chosen_width = max(dialog.minimumWidth(), 620)
    dialog.resize(chosen_width, dialog.height())
    dialog.tabs.setCurrentIndex(0)
    for _ in range(16):
        qt_app.processEvents()
    assert dialog.width() == chosen_width


def test_custom_nozzle_entry_expands_inside_the_window_and_closes_again(
    dialog: PrintSettingsDialog, qt_app: QApplication
) -> None:
    """„Andere …“ zeigt ein Feld; der Rahmen wächst höchstens und springt nicht zurück."""
    from app.ui.style import SPACE, WIDE

    dialog.show()
    # Die Slicersuche reicht Zeilen nach; käme sie zwischen den zwei
    # Messungen an, wüchse die Seite unabhängig von der Düse (macOS-Runner).
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    for _ in range(16):
        qt_app.processEvents()
    layout = dialog.layout()
    assert layout is not None
    margins = layout.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (WIDE,) * 4
    button_layout = dialog._buttons.layout()
    assert button_layout is not None
    assert button_layout.spacing() == SPACE
    page = dialog._scroll.widget()
    assert page is not None

    def rows_height() -> int:
        # In der Breite, die die Seite hat, wie der Dialog selbst misst
        # (``DialogScrollArea.sizeHint``), und ohne den Statussatz unter der
        # Düse, der mit jeder Wahl wechselt. Der Größenwunsch der Seite rechnet
        # in einer eigenen Wunschbreite, und die hängt an diesem Satz: Auf dem
        # macOS-Runner sank sie beim Zuklappen von 442 auf 408 Punkte, andere
        # Sätze brachen in mehr Zeilen um, und die Seite war zugeklappt höher
        # als aufgeklappt (641 gegen 637, Tag-Lauf 0.5.2).
        state = dialog.nozzle_state
        return dialog._scroll.sizeHint().height() - state.heightForWidth(state.width())

    closed_size = dialog.size()
    closed_content_height = rows_height()
    assert dialog.nozzle.isHidden()

    other = dialog.nozzle_choice.count() - 1
    dialog.nozzle_choice.setCurrentIndex(other)
    dialog.nozzle_choice.activated.emit(other)
    for _ in range(16):
        qt_app.processEvents()

    assert not dialog.nozzle.isHidden()
    assert rows_height() > closed_content_height
    # Die Zeile darf den Rahmen wachsen lassen, nie breiter (RM-487).
    assert dialog.width() == closed_size.width()
    assert dialog.height() >= closed_size.height()
    expanded_size = dialog.size()
    expanded_content_height = rows_height()

    standard = dialog.nozzle_choice.findData(0.4)
    assert standard >= 0
    dialog.nozzle_choice.setCurrentIndex(standard)
    dialog.nozzle_choice.activated.emit(standard)
    for _ in range(16):
        qt_app.processEvents()

    assert dialog.nozzle.isHidden()
    assert rows_height() < expanded_content_height
    assert dialog.size() == expanded_size, "Zuklappen lässt den Außenrahmen ruhig stehen"


def test_every_setting_field_carries_its_name_and_its_unit_once(
    dialog: PrintSettingsDialog, qt_app: QApplication
) -> None:
    """Sechsundfünfzig Felder, und ein Bildschirmleser las „Drehfeld, 0,200".

    `oberflaeche.md`: „Wo Felder stehen, tragen sie ihren Namen — und ‚wo'
    heißt jede Stelle." Hier hatte keines einen ``accessibleName`` und keine
    Beschriftung einen Buddy; „Erste Schicht" steht zweimal (Schichthöhe und
    Tempo), also nennt der Name bei Gleichstand die Gruppe. Und die Werte einer
    Spule trugen die Einheit zweimal — „Düse [°C]" über „210 °C" (B12).
    """
    names = [dialog._editors[field.path].accessibleName() for field in FIELDS]
    assert all(names), [field.path for field, name in zip(FIELDS, names, strict=True) if not name]
    assert len(set(names)) == len(names), sorted(n for n in names if names.count(n) > 1)
    for path, label in dialog._labels.items():
        assert label.buddy() is dialog._editors[path], path

    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "petg"))
    spool = FilamentOverrideDialog(MaterialSlot(index=1, name="PLA Weiß"), settings)
    try:
        from PySide6.QtWidgets import QLabel

        for text in (label.text() for label in spool.findChildren(QLabel)):
            assert "[" not in text, f"Einheit doppelt: {text}"
        assert all(editor.accessibleName() for editor in spool.editors.values())
    finally:
        spool.deleteLater()


def test_a_crashed_stock_check_reads_as_lines_not_as_title_colon_detail(
    dialog: PrintSettingsDialog, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch der Absturz der Bestandsprüfung schrieb ``str(InternalError(…))``."""
    from types import SimpleNamespace

    from app.ui import print_settings_dialog as module

    def broken(*_args: object, **_kwargs: object) -> object:
        raise ValueError("boom")

    monkeypatch.setattr(module, "prepare_usage", broken)
    # Die Prüfung läuft nur mit einem Ergebnis; welche Körper es trägt, ist
    # gleich, denn sie scheitert vor dem ersten.
    monkeypatch.setattr(dialog.session, "last_result", _shown_result(SimpleNamespace(objects={})))
    dialog._stock_revision += 1
    dialog._refresh_stock()
    worker = dialog._stock_worker
    assert worker is not None
    worker.wait(10_000)
    qt_app.processEvents()

    shown = dialog.stock_notice.text()
    assert shown, "der Absturz wird gesagt"
    assert ".:" not in shown, shown


def test_a_stock_problem_reads_as_two_lines_not_as_title_colon_detail(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Bestandshinweis zeigte ``str(problem)``: „Titel.: Detail" samt der
    Adressen für den Code — `oberflaeche.md` will beides nicht."""
    from app.core.errors import ValidationError
    from app.ui import print_settings_dialog as module

    def broken(*_args: object, **_kwargs: object) -> object:
        raise ValidationError(
            title="Das Filamentlager lässt sich nicht lesen.",
            field="catalogue",
            constraint="unreadable",
            detail="Die Datei bleibt unverändert.",
        )

    monkeypatch.setattr(module, "prepare_usage", broken)
    said: list[str] = []
    worker = module._StockWorker(
        (),
        print_settings.resolve(profiles.make_profile("generic-220", "pla")),
        profiles.make_profile("generic-220", "pla"),
    )
    worker.done.connect(said.append)
    worker.work()
    lines = said[0].splitlines()
    assert lines[:2] == [
        "Das Filamentlager lässt sich nicht lesen.",
        "Die Datei bleibt unverändert.",
    ]
    assert ".:" not in said[0] and "catalogue" not in said[0]


def test_opening_needs_no_machine_profile_but_slicing_does(
    monkeypatch: pytest.MonkeyPatch, dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """*Im Slicer öffnen* war gesperrt, solange im Slicerprofil kein Drucker
    gewählt war — „Wählen Sie einen Drucker aus der Liste.“, obwohl oben einer
    stand. Das Fenster des Slicers bringt seine Profile selbst mit (RM-336).
    *Slicen* braucht das Profil weiter und sagt es mit seinem eigenen Satz."""
    from app.ui import print_settings_dialog as module

    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    dialog._slicer_path = executable
    monkeypatch.setattr(module.handover, "window_program", lambda found: found)
    dialog._needs_profiles = True
    dialog._profiles_pending = False
    dialog.machine_choice.clear()
    dialog.machine_choice.addItem("— bitte wählen —", "")
    dialog.machine_choice.addItem("Elegoo Centauri Carbon 2 0.4 nozzle", "ecc2")
    dialog.machine_choice.setEnabled(True)
    dialog.machine_choice.setCurrentIndex(0)

    dialog._show_slicer_state()

    assert dialog.open_button.isEnabled(), dialog.open_button.toolTip()
    assert not dialog.slice_button.isEnabled()
    assert dialog.slice_button.toolTip() == dialog._profile_gap()
    assert dialog.slice_button.toolTip() != "Wählen Sie einen Drucker aus der Liste."
    assert dialog._current_setup(for_slicing=False) is not None


def test_opening_without_a_machine_profile_reaches_the_window_and_keeps_its_receipt(
    monkeypatch: pytest.MonkeyPatch, dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """RM-431: Der Klick auf *Im Slicer öffnen* ohne Druckerprofil kommt am
    Fenster an, und die Quittung bleibt stehen. Danach überschrieb der Grund
    des Rechen-Wegs („Dieser Slicer braucht ein Druckerprofil …“) die Zeile
    „An … übergeben“, sobald der Arbeiter fertig war."""
    import types as types_module

    from app.ui import print_settings_dialog as module

    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    dialog._slicer_path = executable
    monkeypatch.setattr(module.handover, "window_program", lambda found: found)
    dialog._needs_profiles = True
    dialog._profiles_pending = False
    dialog.machine_choice.clear()
    dialog.machine_choice.addItem("— bitte wählen —", "")
    dialog.machine_choice.addItem("Elegoo Centauri Carbon 2 0.4 nozzle", "ecc2")
    dialog.machine_choice.setEnabled(True)
    dialog.machine_choice.setCurrentIndex(0)
    written = tmp_path / "platte.3mf"
    written.write_bytes(b"x")
    scene = types_module.SimpleNamespace(objects={"obj_1": _cube_object()})
    monkeypatch.setattr(
        dialog.session,
        "last_result",
        types_module.SimpleNamespace(scene=scene, object_names={}, stopped_at=None),
    )
    # Die Ersatzszene gilt als feine Rechnung, sonst wartet der Klick auf sie
    # (RM-426, ``_wait_for_fine``).
    monkeypatch.setattr(type(dialog.session), "fine_current", property(lambda _self: True))
    monkeypatch.setattr(dialog, "_chosen_plates", lambda: [0])
    monkeypatch.setattr(dialog, "_plate_slots", list)
    monkeypatch.setattr(
        module,
        "_prepare_plate",
        lambda _job, plate: module.PlateRun(
            plate=plate,
            model=written,
            slots=(MaterialSlot(0, ""),),
            keep_arrangement=False,
            findings=(),
        ),
    )
    opened: list[tuple[Path, object]] = []
    monkeypatch.setattr(
        module.handover, "open_in_slicer", lambda model, setup: opened.append((model, setup))
    )

    dialog._open_in_slicer()
    assert dialog._worker is not None, dialog.state.text()
    assert dialog._worker.wait(5_000)
    QApplication.processEvents()

    assert [model for model, _setup in opened] == [written], "der Klick kommt am Fenster an"
    receipt = f"An {module._slicer_title(executable)} übergeben — das Fenster gehört jetzt Ihnen."
    assert dialog.state.text() == receipt
    assert not dialog.slice_button.isEnabled(), "rechnen braucht das Profil weiter"
    assert dialog.slice_button.toolTip() == dialog._machine_missing_line()

    # Auch der nächste Durchlauf der Zustandsprüfung lässt die Quittung stehen.
    dialog._show_slicer_state()
    assert dialog.state.text() == receipt


def test_a_generic_printer_slices_with_prusaslicer_without_a_bundle_printer(
    dialog: PrintSettingsDialog, session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-431: Allgemeiner Drucker, PrusaSlicer mit einem Bündel, das ihn nicht
    kennt — das Druckerprofil bleibt von selbst leer, und Solidons Werte gehen
    hinaus. *Slicen* war trotzdem gesperrt mit „Wählen Sie einen Drucker aus
    der Liste.“ (Rückschritt gegenüber 0.5.1)."""
    from app.core.export import slicer_profiles as sp

    executable = tmp_path / "PrusaSlicer" / "prusa-slicer-console.exe"
    root = executable.parent / "resources" / "profiles"
    root.mkdir(parents=True)
    (root / "PrusaResearch.ini").write_text(_PRUSA_BUNDLE, encoding="utf-8")
    executable.write_bytes(b"")
    monkeypatch.setattr(sp, "user_roots", lambda *_args: [])
    _select_printer(dialog, "generic-220")
    assert session.wait_for_idle()
    dialog._slicer_path = executable
    dialog._needs_profiles = True
    dialog._profiles_pending = False

    dialog._profiles_found(
        sp.find_profiles(executable, "prusa", kinds=("machine", "process", "filament"))
    )
    dialog._show_slicer_state()

    assert not str(dialog.machine_choice.currentData() or ""), "kein Drucker des Bündels passt"
    assert dialog.slice_button.isEnabled(), dialog.slice_button.toolTip()
    assert not dialog.slice_button.toolTip()
    setup = dialog._current_setup()
    assert setup is not None and setup.machine_profile == ""


#: Welche Haftungsmaße bei welcher Bettart wirken — von Hand, nicht aus dem
#: Kern abgeleitet, damit der Test eine falsche Tabelle dort finden kann (RM-432).
_SHOWN_FOR_KIND: dict[str, set[str]] = {
    "none": set(),
    "skirt": {"adhesion.skirt_loops", "adhesion.skirt_distance"},
    "brim": {"adhesion.brim_width"},
    "raft": {"adhesion.raft_layers"},
}


@pytest.mark.parametrize("kind", ["none", "skirt", "brim", "raft"])
def test_measures_of_other_bed_types_are_hidden_and_do_not_lock_slicing(
    dialog: PrintSettingsDialog, kind: str
) -> None:
    """Nur die Maße der gewählten Bettart stehen da; ein abgelehnter Wert in
    einem ausgeblendeten Feld sperrt nicht (RM-341)."""
    selector = dialog._editors["adhesion.kind"]
    assert isinstance(selector, QComboBox)
    selector.setCurrentIndex(selector.findData(kind))
    dialog._update_inactive_setting_rows()
    form = dialog._tab_forms["adhesion"]
    every = set().union(*_SHOWN_FOR_KIND.values())
    for path in every:
        assert form.isRowVisible(dialog._labels[path]) is (path in _SHOWN_FOR_KIND[kind]), path

    hidden = sorted(every - _SHOWN_FOR_KIND[kind])
    if hidden:
        editor = dialog._editors[hidden[0]]
        assert isinstance(editor, BoundedSpin)
        editor.lineEdit().setText("99999")
        assert not editor.refusal() or dialog._first_numeric_refusal() == ""


#: Der Schlüssel, an dem jede Haftungsart im Slicer wirkt, und die Felder, die
#: dazugehören — von außen, aus den Schlüsselnamen der drei Familien.
_ADHESION_EFFECT: dict[str, dict[str, tuple[str, ...]]] = {
    "orca": {
        "skirt_loops": ("adhesion.skirt_loops", "adhesion.skirt_distance"),
        "brim_width": ("adhesion.brim_width",),
        "raft_layers": ("adhesion.raft_layers",),
    },
    "prusa": {
        "skirts": ("adhesion.skirt_loops", "adhesion.skirt_distance"),
        "brim_width": ("adhesion.brim_width",),
        "raft_layers": ("adhesion.raft_layers",),
    },
    "cura": {
        "skirt_line_count": ("adhesion.skirt_loops", "adhesion.skirt_distance"),
        "brim_width": ("adhesion.brim_width",),
        "raft_surface_layers": ("adhesion.raft_layers",),
    },
}


@pytest.mark.parametrize("material", ["pla", "petg"])
@pytest.mark.parametrize(
    ("flavour", "program"),
    [("orca", "OrcaSlicer.exe"), ("prusa", "PrusaSlicer.exe"), ("cura", "CuraEngine.exe")],
)
def test_automatic_adhesion_shows_exactly_the_measures_the_slicer_gets(
    dialog: PrintSettingsDialog, flavour: str, program: str, material: str
) -> None:
    """RM-432: „Automatisch“ zeigte bei PrusaSlicer und Cura die Brimbreite, die
    dort null ist, und versteckte die Skirt-Felder, die wirken — die Übergabe
    macht aus „Automatisch“ die Art des Materials. Sichtbar sind jetzt genau
    die Felder, deren Schlüssel der Slicer mit einem Wert bekommt."""
    dialog.session.start_new("centauri-carbon-2", material)
    dialog.settings = print_settings.with_path(
        print_settings.resolve(dialog.session.profile), "adhesion.kind", "auto"
    )
    dialog._foundation = None
    dialog._foundation_key = None
    dialog._slicer_path = Path(program)
    dialog._load_into_editors()
    dialog._update_inactive_setting_rows()

    written = handover.values_for(dialog.settings, dialog.session.profile, flavour)
    expected = {
        path
        for key, paths in _ADHESION_EFFECT[flavour].items()
        if float(written.get(key, "0")) > 0
        for path in paths
    }
    shown = {
        path
        for paths in _ADHESION_EFFECT[flavour].values()
        for path in paths
        if not dialog._labels[path].isHidden()
    }
    assert expected, written
    assert shown == expected


def test_the_refusal_at_the_slice_button_names_its_field(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Am Knopf stand nur „95 °C liegt über der Obergrenze 90 °C.“ — welches der
    dreißig Felder gemeint war, musste man suchen (RM-342, D-N2)."""
    from app.ui.print_settings_dialog import setting_title

    selector = dialog._editors["support.style"]
    assert isinstance(selector, QComboBox)
    selector.setCurrentIndex(selector.findData("grid"))
    editor = dialog._editors["support.density"]
    monkeypatch.setattr(editor, "refusal", lambda: "95 liegt über der Obergrenze 90.")

    assert dialog._first_numeric_refusal() == (
        f"{setting_title('support.density')}: 95 liegt über der Obergrenze 90."
    )


@pytest.mark.parametrize("with_settings", [False, True])
def test_plate_preparation_compares_the_final_writer_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, with_settings: bool
) -> None:
    """Die Gegenprobe folgt der endgültigen Teilauflösung, nicht den Dialogvorgaben."""
    from app.core.slice.estimate import PlateComparison
    from app.ui import print_settings_dialog as module

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    body = replace(_cube_object(), plate=3)
    setup = handover.SlicerSetup(tmp_path / "slicer.exe", "prusa")
    job = module._PlateJob(
        (body,),
        (3,),
        tmp_path,
        "Teil",
        setup,
        settings,
        profile,
        {},
        with_settings=with_settings,
        with_comparison=True,
    )
    effective = (
        replace(
            settings,
            layers=replace(settings.layers, first_layer_height=0.37),
            support=replace(settings.support, style="normal", density=0.23),
        )
        if with_settings
        else None
    )
    passed = []

    def write(objects, folder, *, comparison, **_kwargs):
        comparison(((body, body.mesh, effective),))
        return folder / "actual.3mf", []

    def compare(plate, parts, actual_profile, **kwargs):
        passed.append((plate, parts, actual_profile, kwargs))
        return PlateComparison(plate, 17.0 if effective else None, 29 if effective else None)

    monkeypatch.setattr(module, "write_assembly", write)
    monkeypatch.setattr(module, "plate_comparison", compare)
    run = module._prepare_plate(job, 3)
    assert len(passed) == 1
    assert passed[0][0] == 3
    assert passed[0][1][0][2] is effective
    assert passed[0][3]["separate_objects"] is True
    assert run.comparison == PlateComparison(
        3, 17.0 if effective else None, 29 if effective else None
    )


def test_unknown_material_does_not_discard_independent_plate_comparisons(tmp_path: Path):
    """Fehlende Materialanteile lassen die bereits berechneten Modelllagen bestehen."""
    from app.core.slice.estimate import PlateComparison
    from app.ui import print_settings_dialog as module

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    body = _cube_object()
    setup = handover.SlicerSetup(tmp_path / "slicer.exe", "orca")
    job = module._PlateJob((body,), (0,), tmp_path, "Teil", setup, settings, profile, {})
    run = module.PlateRun(0, tmp_path / "actual.3mf", comparison=PlateComparison(0, 0.0, 100))
    actual = module._comparison_for_job(job, [run])
    assert actual.grams is None
    assert actual.seconds is None, "die Platte nennt keine Zeit"
    assert actual.plates == (run.comparison,)


def test_changed_dialog_job_does_not_publish_its_previous_comparison():
    """Die neue Gegenprobe umgeht nicht den Schutz gegen veraltete Dialogaufträge."""
    from app.core.scene.cancel import CancelSignal
    from app.ui import print_settings_dialog as module

    published = []
    worker = SimpleNamespace(cancelled=CancelSignal(), comparison=module.SliceComparison(1.0, 1.0))
    host = SimpleNamespace(
        _worker=worker,
        _job_context=("plates", 3, 1),
        _print_context=lambda: ("plates", 0),
        _sliced=lambda *args, **kwargs: published.append((args, kwargs)),
    )
    module.PrintSettingsDialog._slice_done(host, worker, [])
    assert not published


@pytest.fixture
def preflight_user_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
    ):
        monkeypatch.setenv(variable, str(tmp_path / "user-data"))
    monkeypatch.setattr(activation, "require", lambda *_args, **_kwargs: None)


def _preflight_box(size: tuple[float, float, float], x: float = 0.0) -> MeshData:
    raw = trimesh.creation.box(extents=size)
    raw.apply_translation((x, 0.0, size[2] / 2.0))
    return MeshData.of(raw)


def test_prepare_plate_carries_only_the_written_plate_and_its_export_tessellation(
    tmp_path: Path,
    preflight_user_data: None,
) -> None:
    """Fremde Platten und die gröbere Ansicht gehören nicht zur Vorprüfung."""
    profile = profiles.make_profile("prusa-mini", "pla")
    exact = replace(edit.cylinder(40.0, 10.0), deflection=0.5)
    selected = (
        SceneObject("round", "Zylinder", exact, kind="brep", plate=0),
        SceneObject("small", "Würfel", _preflight_box((20.0, 20.0, 10.0), x=60.0), plate=0),
    )
    excluded = SceneObject("large", "Andere Platte", _preflight_box((231.0, 231.0, 10.0)), plate=1)
    expected = tuple(writer.mesh_for_export(entry.mesh, profile) for entry in selected)
    assert expected[0].triangle_count > exact.triangle_count, (
        "Der Kontrollkörper muss tatsächlich feiner exportiert als angezeigt werden"
    )
    before = [entry.mesh.raw.vertices.copy() for entry in (*selected, excluded)]
    job = print_dialog._PlateJob(
        objects=(*selected, excluded),
        plates=(0, 1),
        folder=tmp_path,
        name="RM479",
        setup=handover.SlicerSetup(tmp_path / "SuperSlicer.exe", "prusa"),
        settings=print_settings.resolve(profile),
        profile=profile,
        slot_profiles={},
        with_settings=False,
    )

    run = print_dialog._prepare_plate(job, 0)
    written = threemf.read_objects(run.model.read_bytes())

    assert len(written) == len(selected) == 2
    assert sorted(part.mesh.triangle_count for part in written) == sorted(
        mesh.triangle_count for mesh in expected
    ), "Die tatsächlich geschriebene Datei muss die feinere Exportvernetzung tragen"
    meshes = getattr(run, "meshes", None)
    assert meshes is not None, "PlateRun trägt noch keinen Snapshot seiner Exportnetze"
    assert isinstance(meshes, tuple)
    assert len(meshes) == len(selected), "Ein Körper von Platte 1 darf Platte 0 nicht sperren"
    assert getattr(run, "object_ids", ()) == ("round", "small"), (
        "Die Fehlerzuordnung braucht dieselben Körper in derselben Reihenfolge wie die Netze"
    )
    for actual, wanted in zip(meshes, expected, strict=True):
        assert isinstance(actual, MeshData)
        assert actual.triangle_count == wanted.triangle_count
        np.testing.assert_allclose(actual.raw.triangles, wanted.raw.triangles, atol=1e-9, rtol=0.0)
    for previous, entry in zip(before, (*selected, excluded), strict=True):
        np.testing.assert_array_equal(previous, entry.mesh.raw.vertices)


class _PreflightSignalLog:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def emit(self, *values: Any) -> None:
        self.calls.append(values)


def test_preflight_failure_racing_with_cancel_is_suppressed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, preflight_user_data: None
) -> None:
    from app.core.errors import ExternalToolError

    profile = profiles.make_profile("prusa-mini", "pla")
    run = print_dialog.PlateRun(
        plate=0,
        model=tmp_path / "plate.3mf",
        meshes=(_preflight_box((231.0, 231.0, 10.0)),),
        object_ids=("large",),
    )
    host = SimpleNamespace(
        _runs=[run],
        _settings=print_settings.resolve(profile),
        _profile=profile,
        _setup=handover.SlicerSetup(tmp_path / "PrusaSlicer.exe", "prusa"),
        _usage={},
        cancelled=CancelSignal(),
        step=_PreflightSignalLog(),
        failed=_PreflightSignalLog(),
        done=_PreflightSignalLog(),
    )

    def cancelled_refusal(*_args: Any, **_kwargs: Any) -> None:
        host.cancelled.cancel()
        raise ExternalToolError(values={"constraint": "slicer_build_volume", "part_index": 0})

    monkeypatch.setattr(handover, "slice_model", cancelled_refusal)

    print_dialog._SliceWorker.work(host)

    assert host.failed.calls == []
    assert host.done.calls == []


def test_queued_preflight_failure_after_cancel_button_is_suppressed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.errors import ExternalToolError

    events: list[Any] = []
    cancelled = CancelSignal()
    cancelled.cancel()
    host = SimpleNamespace(
        _settling=False,
        _worker=SimpleNamespace(cancelled=cancelled),
        _job_context=("same",),
        _print_context=lambda: ("same",),
        _failed_save_copies=None,
        state=SimpleNamespace(setText=events.append),
    )
    monkeypatch.setattr(print_dialog, "show_error", lambda problem, *_args: events.append(problem))

    PrintSettingsDialog._slice_failed(
        host, ExternalToolError(values={"constraint": "slicer_build_volume", "part_index": 0})
    )

    assert events == []


def test_slice_worker_passes_the_same_prepared_snapshot_to_slice_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, preflight_user_data: None
) -> None:
    """Ein späterer Szenenstand darf die Vorprüfung des vorbereiteten Laufs nicht ersetzen."""
    profile = profiles.make_profile("prusa-mini", "pla")
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(tmp_path / "SuperSlicer.exe", "prusa")
    snapshot = (_preflight_box((40.0, 40.0, 10.0)), _preflight_box((20.0, 20.0, 10.0), x=60.0))
    slots = (MaterialSlot(index=0, name="PLA", colour="#ffffff", material="pla"),)
    export_finding = Finding("export.kept", "info", "Exportbefund der gewählten Platte")
    # Der Host stellt den künftigen Datensatz bereit: So wird die fehlende
    # Weitergabe geprüft, unabhängig davon, ob PlateRun das Feld schon kennt.
    entry = SimpleNamespace(
        plate=0,
        model=tmp_path / "plate-1.3mf",
        meshes=snapshot,
        slots=slots,
        keep_arrangement=True,
        model_height=10.0,
        used_tools=(0,),
        findings=(export_finding,),
    )
    host = SimpleNamespace(
        _runs=[entry],
        _settings=settings,
        _profile=profile,
        _setup=setup,
        _usage={},
        # Absichtlich ein anderer neuer Szenenstand; maßgeblich ist entry.
        _objects=(SceneObject("later", "Späterer Stand", _preflight_box((231.0, 231.0, 10.0))),),
        cancelled=CancelSignal(),
        step=_PreflightSignalLog(),
        failed=_PreflightSignalLog(),
        done=_PreflightSignalLog(),
        usageReady=_PreflightSignalLog(),
    )
    captured: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    outcome = handover.SliceOutcome(tmp_path / "plate-1.gcode", GcodeMetrics())

    def receive(*args: Any, **kwargs: Any) -> handover.SliceOutcome:
        captured.append((args, kwargs))
        return outcome

    monkeypatch.setattr(handover, "slice_model", receive)

    print_dialog._SliceWorker.work(host)

    assert len(captured) == 1
    args, options = captured[0]
    assert args == ([entry.model], settings, profile, setup)
    assert options.get("model_meshes") is snapshot, (
        "_SliceWorker reicht die Exportnetze seines vorbereiteten PlateRun noch nicht weiter"
    )
    assert options["slots"] is slots
    assert options["model_height"] == pytest.approx(10.0)
    assert options["expected_tools"] == (0,)
    assert options["cancelled"] is host.cancelled
    assert host.step.calls == [(1, 1)]
    assert host.failed.calls == []
    assert host.done.calls == [([outcome],)]
    assert outcome.findings == [export_finding]


@pytest.mark.parametrize(
    ("part_index", "object_ids", "expected"),
    [
        (1, ("first", "second"), "second"),
        (0, ("first", "second"), "first"),
        (-1, ("first", "second"), None),
        (2, ("first", "second"), None),
        (True, ("first", "second"), None),
        ("1", ("first", "second"), None),
        (None, ("first", "second"), None),
        (1, ("first",), None),
        (1, ("first", ""), None),
    ],
)
def test_preflight_worker_binds_only_a_valid_snapshot_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    preflight_user_data: None,
    part_index: object,
    object_ids: tuple[str, ...],
    expected: str | None,
) -> None:
    """Weder geänderte Auswahl noch ungültiger Index dürfen einen anderen Körper treffen."""
    from app.core.errors import CANCEL, CHOOSE_PRINTER, SCALE_TO_FIT, SPLIT_MODEL, ExternalToolError

    profile = profiles.make_profile("prusa-mini", "pla")
    meshes = (_preflight_box((20.0, 20.0, 10.0)), _preflight_box((231.0, 231.0, 10.0)))
    entry = SimpleNamespace(
        plate=0,
        model=tmp_path / "plate.3mf",
        meshes=meshes,
        object_ids=object_ids,
        slots=(),
        keep_arrangement=False,
        model_height=10.0,
        used_tools=(),
        findings=(),
    )
    problem = ExternalToolError(
        object_id="old-selection",
        values={"constraint": "slicer_build_volume", "part_index": part_index},
        suggestions=(SPLIT_MODEL, SCALE_TO_FIT, CHOOSE_PRINTER, CANCEL),
    )

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise problem

    monkeypatch.setattr(handover, "slice_model", refuse)
    host = SimpleNamespace(
        _runs=[entry],
        _settings=print_settings.resolve(profile),
        _profile=profile,
        _setup=handover.SlicerSetup(tmp_path / "SuperSlicer.exe", "prusa"),
        _usage={},
        cancelled=CancelSignal(),
        step=_PreflightSignalLog(),
        failed=_PreflightSignalLog(),
    )

    print_dialog._SliceWorker.work(host)

    delivered = host.failed.calls[0][0]
    assert delivered.object_id == expected
    actions = {action.id for action in delivered.suggestions}
    assert {"split_model", "scale_to_fit"}.issubset(actions) == (expected is not None)
    assert "choose_printer" in actions


def test_preflight_failure_never_falls_back_to_the_current_selection() -> None:
    from app.core.errors import ExternalToolError
    from app.ui.main_window import MainWindow

    host = SimpleNamespace(object_tree=SimpleNamespace(selected_objects=lambda: ["small-cube"]))
    problem = ExternalToolError(values={"constraint": "slicer_build_volume"})

    assert MainWindow._object_of(host, problem) is None
    problem.object_id = "large-part"
    assert MainWindow._object_of(host, problem) == "large-part"
    assert MainWindow._object_of(host, ExternalToolError()) == "small-cube"


@pytest.mark.parametrize("action_id", ["split_model", "scale_to_fit", "arrange_on_bed"])
@pytest.mark.parametrize("changed_while_closing", [False, True])
def test_preflight_scene_action_waits_for_the_print_dialog_to_finish(
    monkeypatch: pytest.MonkeyPatch,
    preflight_user_data: None,
    action_id: str,
    changed_while_closing: bool,
) -> None:
    """Eine beendete Fehlermeldung bedeutet noch keinen beendeten Druckdialog."""
    from contextlib import nullcontext

    from app.core.errors import ExternalToolError
    from app.ui import main_window

    events: list[str] = []
    profile = profiles.make_profile("prusa-mini", "pla")
    problem = ExternalToolError(
        object_id="large-part", values={"constraint": "slicer_build_volume", "part_index": 1}
    )
    signal = SimpleNamespace(connect=lambda *_args: None)
    handlers = {action_id: lambda error: events.append(f"handled:{error.object_id}")}
    window = SimpleNamespace(
        session=SimpleNamespace(request_fine=lambda: None),
        settings=UiSettings(),
        filaments=SimpleNamespace(return_to_print_button=SimpleNamespace(hide=lambda: None)),
        usage_notice=SimpleNamespace(offer=lambda *_args, **_kwargs: None),
        _end_inserting_for_output=lambda: None,
        _gcode_returned=lambda *_args: None,
        _slicer_findings=lambda *_args: None,
        _count_delivery=lambda *_args: None,
        _refresh_inventory=lambda: None,
        _store_settings=lambda: None,
        _offer_support=lambda: None,
        error_handlers=lambda: handlers,
    )
    dialog = SimpleNamespace(
        settings=print_settings.resolve(profile),
        sliced=signal,
        reported=signal,
        handedOver=signal,
        setupRequested=signal,
        filamentsRequested=signal,
        usage_notice=SimpleNamespace(changed=signal, requests={}),
        scene_action=None,
        _scene_action_context=None,
        _job_context=("original-job",),
        _print_context=lambda: current_context[0],
        has_changes=lambda: False,
        deleteLater=lambda: events.append("deleted"),
        parentWidget=lambda: window,
        _failed_save_copies=None,
        _show_slicer_output=lambda *_args: None,
        _open_printer_choice=lambda *_args: None,
        reject=lambda: events.append("close-requested"),
    )
    current_context = [("original-job",)]
    dialog.take_scene_action = lambda: print_dialog.PrintSettingsDialog.take_scene_action(dialog)

    def execute() -> int:
        events.append("modal-entered")
        offered = print_dialog.PrintSettingsDialog.error_handlers(dialog)
        # finished kann während der Fehlermeldung den laufenden Kontext leeren.
        dialog._job_context = None
        offered[action_id](problem)
        assert events == ["modal-entered", "close-requested"]
        assert dialog.scene_action == (action_id, problem)
        events.append("workers-settled")
        if changed_while_closing:
            current_context[0] = ("new-job",)
        events.append("modal-returned")
        return 0

    dialog.exec = execute
    monkeypatch.setattr(print_dialog, "handlers_of", lambda _parent: handlers)
    monkeypatch.setattr(main_window, "PrintSettingsDialog", lambda *_args: dialog)
    monkeypatch.setattr(main_window, "waiting", nullcontext)
    monkeypatch.setattr(main_window, "ensure_print_disclosure", lambda *_args: None)

    main_window.MainWindow.action_print_settings(window)

    expected = [
        "modal-entered",
        "close-requested",
        "workers-settled",
        "modal-returned",
        "deleted",
    ]
    if not changed_while_closing:
        expected.append("handled:large-part")
    assert events == expected


@pytest.mark.parametrize("job_context", [None, ("old-job",)])
def test_preflight_failure_of_a_replaced_job_is_discarded(
    monkeypatch: pytest.MonkeyPatch, job_context: tuple[str, ...] | None
) -> None:
    from app.core.errors import ExternalToolError

    shown: list[Any] = []
    changed: list[str] = []
    host = SimpleNamespace(
        _settling=False,
        _worker=None,
        _job_context=job_context,
        _print_context=lambda: ("new-job",),
        _failed_save_copies=None,
        state=SimpleNamespace(setText=changed.append),
        reported=_PreflightSignalLog(),
    )
    monkeypatch.setattr(print_dialog, "show_error", lambda problem, *_args: shown.append(problem))
    problem = ExternalToolError(values={"constraint": "slicer_build_volume", "part_index": 1})

    PrintSettingsDialog._slice_failed(host, problem, [Finding("old", "info", "Alter Auftrag")])

    assert shown == []
    assert changed == []
    assert host.reported.calls == []


def test_preflight_action_is_discarded_when_the_job_changes_in_the_error_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.errors import ExternalToolError

    invoked: list[str] = []
    context = [("old-job",)]
    dialog = SimpleNamespace(
        parentWidget=lambda: None,
        _job_context=context[0],
        _print_context=lambda: context[0],
        scene_action=None,
        _scene_action_context=None,
        _failed_save_copies=None,
        _show_slicer_output=lambda *_args: None,
        _open_printer_choice=lambda *_args: None,
        reject=lambda: invoked.append("closed"),
    )
    monkeypatch.setattr(
        print_dialog,
        "handlers_of",
        lambda _parent: {"split_model": lambda _error: invoked.append("split")},
    )
    offered = PrintSettingsDialog.error_handlers(dialog)
    problem = ExternalToolError(
        object_id="large", values={"constraint": "slicer_build_volume", "part_index": 1}
    )
    context[0] = ("new-job",)

    offered["split_model"](problem)

    assert invoked == []
    assert dialog.scene_action is None


def test_a_save_failure_without_print_job_context_still_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.errors import FileWriteError

    shown: list[Any] = []
    host = SimpleNamespace(
        _settling=False,
        _worker=None,
        _job_context=None,
        _failed_save_copies=None,
        state=SimpleNamespace(setText=lambda _text: None),
    )
    monkeypatch.setattr(print_dialog, "show_error", lambda problem, *_args: shown.append(problem))
    problem = FileWriteError()

    PrintSettingsDialog._slice_failed(host, problem)

    assert shown == [problem]


def test_preflight_internal_part_index_is_not_a_customer_value() -> None:
    from app.core.errors import ExternalToolError
    from app.ui.dialogs import spoken_values

    problem = ExternalToolError(
        values={"constraint": "slicer_build_volume", "part_index": 7, "excess_mm": 51.0}
    )

    lines = spoken_values(problem)

    assert len(lines) == 1
    assert "51" in lines[0]


def test_preflight_split_uses_the_offending_object_instead_of_the_selection(
    preflight_user_data: None,
) -> None:
    from app.core.errors import ExternalToolError
    from app.ui.main_window import MainWindow

    selected = SceneObject("small", "Würfel", _preflight_box((20.0, 20.0, 20.0)))
    oversized = SceneObject("large", "Großes Teil", _preflight_box((231.0, 231.0, 10.0)))
    applied: list[Any] = []
    split: list[str] = []
    window = SimpleNamespace(
        session=SimpleNamespace(
            last_result=SimpleNamespace(
                scene=SimpleNamespace(objects={"small": selected, "large": oversized})
            ),
            profile=profiles.make_profile("prusa-mini", "pla"),
            apply=lambda _title, drafts: applied.extend(drafts),
        ),
        object_tree=SimpleNamespace(selected_objects=lambda: ["small"]),
        action_auto_split=split.append,
    )
    window._object_of = lambda error: MainWindow._object_of(window, error)
    problem = ExternalToolError(
        object_id="large", values={"constraint": "slicer_build_volume", "part_index": 1}
    )

    MainWindow._split_after_error(window, problem)
    assert split == ["large"]
    assert applied == []


@pytest.mark.parametrize("dimensions", [(231, 231, 10), (20, 20, 250)])
def test_preflight_button_names_size_editing_without_an_automatic_fit_promise(dimensions):
    with pytest.raises(ExternalToolError) as raised:
        handover._check_plate(
            [_preflight_box(dimensions)],
            profiles.make_profile("prusa-mini", "pla"),
            handover.SlicerSetup(Path("PrusaSlicer.exe"), "prusa"),
        )
    offered = offered_actions(raised.value, {"scale_to_fit": lambda error: None})
    action = next(action for action in offered if action.id == "scale_to_fit")
    assert str(action.label) == "Verkleinern …"
    assert action.primary == SCALE_TO_FIT.primary
    assert str(SCALE_TO_FIT.label) == "Auf den Bauraum verkleinern"


def _preflight_scale_host(
    *, object_id="large", deleted=False, current=True, quiet=True, accept_selection=True
):
    events = []
    selected = ["other", "pin"]
    objects = {
        "other": SceneObject(
            "other",
            "Other",
            _preflight_box((20, 20, 20)),
            features={"pin": Feature("pin", "pin", "detected", {"diameter": 5.0})},
        )
    }
    if not deleted:
        objects["large"] = SceneObject("large", "Large", _preflight_box((231, 231, 10)))

    def select(identity):
        events.append(("select", identity))
        if accept_selection:
            selected[:] = [identity, None]

    host = SimpleNamespace(
        session=SimpleNamespace(
            last_result=SimpleNamespace(scene=SimpleNamespace(objects=objects)),
            result_current=current,
            profile=profiles.make_profile("prusa-mini", "pla"),
            history=SimpleNamespace(discardable=False),
            apply=lambda *args, **kwargs: events.append(("applied", args)),
        ),
        object_tree=SimpleNamespace(
            selected_objects=lambda: [selected[0]],
            selected=lambda: selected[0],
            selected_feature=lambda: selected[1],
            select_object=select,
        ),
        _quiet_command_allowed=lambda: quiet,
        _begin_from_the_start_screen=lambda: True,
        _local_features=None,
        settings=UiSettings(),
    )
    host._object_of = lambda error: preflight_main.MainWindow._object_of(host, error)
    host._selected_feature_object = lambda: preflight_main.MainWindow._selected_feature_object(host)
    host.feature_instead_of = lambda op: preflight_main.MainWindow.feature_instead_of(host, op)
    host._sister_for_the_chosen_feature = lambda spec: (
        preflight_main.MainWindow._sister_for_the_chosen_feature(host, spec)
    )
    host.run_operation = lambda spec, given, on_bodies: events.append(
        ("dialog", spec.name, given, tuple(on_bodies))
    )
    error = ExternalToolError(object_id=object_id, values={"constraint": "slicer_build_volume"})
    return host, events, error


def test_scale_error_selects_whole_bound_object_and_opens_existing_dialog():
    host, events, error = _preflight_scale_host()
    assert host.feature_instead_of("scale_object").name == "resize_feature"
    preflight_main.MainWindow._scale_after_error(host, error)
    assert events == [("select", "large"), ("dialog", "scale_object", {"about": "bed"}, ("large",))]
    assert host.object_tree.selected_feature() is None


@pytest.mark.parametrize(
    "options",
    [
        {"object_id": None},
        {"deleted": True},
        {"current": False},
        {"quiet": False},
        {"accept_selection": False},
    ],
)
def test_scale_action_does_not_open_for_unknown_deleted_stale_or_busy_context(options):
    host, events, error = _preflight_scale_host(**options)
    preflight_main.MainWindow._scale_after_error(host, error)
    assert not any(event[0] in {"dialog", "applied"} for event in events)
    if options != {"accept_selection": False}:
        assert not events


def test_other_scale_error_keeps_existing_automatic_behaviour():
    host, events, error = _preflight_scale_host()
    error.values.clear()
    preflight_main.MainWindow._scale_after_error(host, error)
    assert len(events) == 1 and events[0][0] == "applied"
    draft = events[0][1][1][0]
    assert draft.op == "scale_object" and draft.inputs == ("large",)
    assert draft.params["factor"] == pytest.approx(180 / 231 * 0.99)


def test_real_operation_entry_reaches_size_dialog_with_fixed_id_without_feature_rewrite(
    monkeypatch,
):
    host, events, error = _preflight_scale_host()
    # Alle Auswahlentscheidungen bleiben die echten Methoden. Nur der
    # Fensteraufbau endet am Eintritt in den vorhandenen Operationsdialog.
    for name in (
        "_from_selection",
        "_spacing_for",
        "_plane_through",
        "_measured_from_body",
        "_source_names",
        "_parameter_values",
        "_feature_names",
        "_image_names",
        "_edge_names",
    ):
        setattr(host, name, lambda *args, **kwargs: {})
    host._object_names = lambda: {"other": "Other", "large": "Large"}
    host._seat_for = lambda *args: None
    host._sketch_surroundings = lambda: ()
    host._slots_of_selection = lambda: ()
    host._pick_image_source = lambda *args: None
    host._pick_model_source = lambda *args: None
    host._cancel_source_read = lambda *args: None
    host.run_operation = lambda spec, given, on_bodies: preflight_main.MainWindow.run_operation(
        host, spec, given, on_bodies=on_bodies
    )

    class ReachedDialogError(Exception):
        pass

    def capture(spec, names, parent, **kwargs):
        events.append(("actual-dialog", spec.name, kwargs["source_objects"], kwargs["values"]))
        raise ReachedDialogError()

    monkeypatch.setattr(preflight_main, "OperationDialog", capture)
    with pytest.raises(ReachedDialogError):
        preflight_main.MainWindow._scale_after_error(host, error)
    assert events == [
        ("select", "large"),
        ("actual-dialog", "scale_object", ("large",), {"about": "bed"}),
    ]


# --- Ein Vorschlag je Teil am Feld (RM-289, B6) ---------------------------------------


def _tower_and_plate() -> tuple[SceneObject, SceneObject]:
    tower = trimesh.creation.box(extents=(4.0, 4.0, 80.0))
    tower.apply_translation((0.0, 0.0, 40.0))
    wide = trimesh.creation.box(extents=(60.0, 60.0, 10.0))
    wide.apply_translation((50.0, 0.0, 5.0))
    return (
        SceneObject(id="obj_1", name="Turm", mesh=MeshData.of(tower)),
        SceneObject(id="obj_2", name="Platte", mesh=MeshData.of(wide)),
    )


def test_the_advice_worker_names_who_gets_an_accepted_suggestion(qt_app: QApplication) -> None:
    """Nach dem Übernehmen fragt der Rat, welchen Teilen der Brim gilt — dieselbe
    Frage wie der Export (``split_for_parts``, ``part_advice``)."""
    from app.core.slice.analysis import slice_body

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.with_accepted(
        print_settings.resolve(profile, "standard"), "adhesion.kind", "brim"
    )
    objects = _tower_and_plate()
    worker = print_dialog._AdviceWorker(objects, settings, profile, None, {}, (), (), {})
    results = {
        body.id: (
            45.0,
            0.8,
            slice_body(
                body.mesh,
                settings.layers.layer_height,
                first_layer_height=settings.layers.first_layer_height,
                support_volume=False,
            ),
        )
        for body in objects
    }

    assert worker._accepted_targets(results) == {"adhesion.kind": ("Turm",)}


def test_the_field_says_which_parts_get_a_suggestion_and_what_the_rest_prints(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B6: Im Feld stand „Brim“ fett, als gälte er der Platte. Daneben steht jetzt,
    dass nur der Turm ihn bekommt und die übrigen Teile die eigene Wahl drucken;
    *Zurücksetzen* führt zu dieser Wahl zurück (B2)."""
    chosen = print_settings.with_choice(dialog.settings, "adhesion.kind", "none")
    dialog.settings = print_settings.with_accepted(chosen, "adhesion.kind", "brim")
    monkeypatch.setattr(dialog, "_plate_bodies", lambda: list(_tower_and_plate()))
    dialog._accepted_parts = {"adhesion.kind": ("Turm",)}

    dialog._mark_origins()

    note = dialog._part_notes["adhesion.kind"]
    assert not note.isHidden()
    assert "Turm" in note.text() and "Ihre Einstellung" in note.text(), note.text()
    assert "Ihre Einstellung" in dialog._resets["adhesion.kind"].toolTip()

    dialog._reset_field("adhesion.kind")

    assert dialog.settings.adhesion.kind == "none"
    assert "adhesion.kind" in dialog.settings.chosen
    assert dialog._part_notes["adhesion.kind"].isHidden()


def test_a_suggestion_no_part_asks_for_says_it_applies_to_all(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog.settings = print_settings.with_accepted(dialog.settings, "adhesion.kind", "brim")
    monkeypatch.setattr(dialog, "_plate_bodies", lambda: list(_tower_and_plate()))
    dialog._accepted_parts = {"adhesion.kind": ()}

    dialog._mark_origins()

    note = dialog._part_notes["adhesion.kind"]
    assert not note.isHidden()
    assert note.text() == str(tr("Gilt allen Teilen: Keines verlangt diesen Vorschlag für sich."))


def test_profiles_arrive_in_one_read_and_fill_the_processes_once(
    dialog: PrintSettingsDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Profilantwort läuft in einem Lesedurchgang und füllt die Prozesse einmal (RM-602).

    An Roberts ElegooSlicer stand der Dialog 2,5 s: jede Frage las die Profile
    neu, und die Prozesse füllten sich zweimal — einmal über das Signal der
    Maschinenwahl, gleich danach mit dem passenden Profil.
    """
    from app.core.export import slicer_profiles

    dialog._slicer_path = Path("ElegooSlicer.exe")
    dialog._profiles_pending = False
    dialog.machine_choice.setCurrentIndex(-1)
    dialog.ui_settings.slicer_machine_profile = ""
    # Die gewählte Maschine ist nicht die erste der Liste — sonst steht die
    # Auswahl nach dem Füllen schon auf ihr, und kein Signal läuft. Bei Robert
    # war die 0,4er die zweite von vier.
    found = [
        _profile(
            f"Elegoo Centauri Carbon 2 {diameter:.1f} nozzle",
            "machine",
            printer_model="Elegoo Centauri Carbon 2",
            nozzle=diameter,
        )
        for diameter in (0.2, 0.4)
    ]
    machine = found[1]
    monkeypatch.setattr(slicer_profiles, "match", lambda *_args, **_kwargs: (machine, None))
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: "")
    monkeypatch.setattr(dialog, "_machines_worth_showing", lambda machines: machines)
    calls: list[bool] = []
    monkeypatch.setattr(
        dialog,
        "_fill_processes",
        lambda _preferred: calls.append(slicer_profiles._SINGLE_READ.documents is not None),
    )

    dialog._profiles_found(found)

    assert dialog.machine_choice.currentData() == slicer_profiles.identity(machine)
    assert calls == [True], "einmal, und im Lesedurchgang"
    assert getattr(slicer_profiles._SINGLE_READ, "documents", None) is None, "danach verworfen"
