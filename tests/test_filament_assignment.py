"""Die Schnellauswahl zeigt den Wirkungsbereich und meldet ausschließlich bewusste Spulenwahl."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.core.knowledge import filaments
from app.core.types import MaterialSlot, SceneObject
from app.ui.filament_assignment import QuickFilamentPicker


def _body(
    identifier: str, name: str, material_slots: list[MaterialSlot] | None = None
) -> SceneObject:
    """Ein kleiner gültiger Körper stellt den echten Auswahlvertrag her."""
    import trimesh

    from app.core.geom.mesh import MeshData

    return SceneObject(
        id=identifier,
        name=name,
        mesh=MeshData.of(
            trimesh.creation.box(),
            slots=((material_slots[0].index,) * 12) if material_slots else (),
        ),
        material_slots=material_slots or [],
    )


@pytest.fixture
def picker(qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ein eigenes Lager, ohne Hauptfenster und ohne Renderer."""
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    widget = QuickFilamentPicker()
    yield widget
    widget.close()


def test_no_selection_keeps_inventory_reachable(picker: QuickFilamentPicker) -> None:
    seen: list[bool] = []
    picker.inventoryRequested.connect(lambda: seen.append(True))
    assert not picker.picker.isEnabled()
    picker.inventory_button.click()
    assert seen == [True]
    assert not picker.clear_button.isEnabled()


def test_inventory_error_is_visible_and_repaired_file_refreshes_choices(
    picker: QuickFilamentPicker,
) -> None:
    """Kein leeres Lager als Fehlerersatz und kein veralteter Snapshot nach Reparatur."""
    from dataclasses import replace

    first = filaments.save(filaments.CatalogueFilament("Alt", "#112233"))
    picker.set_context([_body("part", "Teil")])
    before = filaments.catalogue_path().read_bytes()
    filaments.catalogue_path().write_text("{kaputt", encoding="utf-8")
    picker.refresh()
    assert not picker.notice.isHidden()
    assert "Sicherung" in picker.notice.text()
    assert picker.inventory_button.isEnabled()
    filaments.catalogue_path().write_bytes(before)
    filaments.save(replace(first, name="Neu"))
    picker.refresh()
    assert picker.notice.isHidden()
    assert "Neu" in picker.picker.itemText(1)


def test_removal_is_reachable_without_a_catalogue_spool(picker: QuickFilamentPicker) -> None:
    """Auch ein fremdes Projektfilament lässt sich ohne Besitzangabe wieder entfernen."""
    seen = []
    picker.clearRequested.connect(lambda: seen.append(True))
    picker.set_context([_body("part", "Teil")])
    assert not picker.clear_button.isEnabled()
    picker.set_context([_body("part", "Teil", [MaterialSlot(0, "Fremde Spule")])])
    assert filaments.catalogue() == ()
    assert picker.clear_button.isEnabled()
    picker.clear_button.click()
    assert seen == [True]


def test_removal_only_uses_the_selected_faces(picker: QuickFilamentPicker) -> None:
    """Eine neutrale Fläche bietet kein Entfernen der anderen noch bemalten Flächen an."""
    from dataclasses import replace

    from app.core.types import Feature

    obj = _body("part", "Teil", [MaterialSlot(1, "Spule")])
    obj = replace(
        obj,
        mesh=replace(obj.mesh, slots=(0, 1) * 6),
        features={
            "neutral": Feature("neutral", "face", "generated", {}, face_indices=(0,)),
            "assigned": Feature("assigned", "face", "generated", {}, face_indices=(1,)),
        },
    )
    picker.set_context([obj], selected_features=(("part", "neutral"),))
    assert not picker.clear_button.isEnabled()
    picker.set_context([obj], selected_features=(("part", "assigned"),))
    assert picker.clear_button.isEnabled()


def test_legacy_object_material_is_named_and_removable_without_a_spool(
    picker: QuickFilamentPicker,
) -> None:
    """Ein altes ABS-Körpermaterial bleibt echte Information und benötigt keine Lager-Spule."""
    from dataclasses import replace

    from app.ui.filament_picker import FilamentPanel

    obj = replace(_body("legacy", "Alt"), material="abs")
    picker.set_context([obj])
    assert "ABS" in picker.picker.currentText()
    assert picker.clear_button.isEnabled()
    assert filaments.catalogue() == ()
    panel = FilamentPanel()
    panel.show_scene([obj])
    assert panel._used[0][0].material_type == "ABS"


def test_project_filament_without_inventory_is_still_named(picker: QuickFilamentPicker) -> None:
    obj = _body(
        identifier="part", name="Teil", material_slots=[MaterialSlot(index=1, name="Fremd")]
    )
    picker.set_context([obj])
    assert "Fremd" in picker.picker.currentText()
    assert picker.picker.currentData() == ""
    assert filaments.catalogue() == ()


def test_mixed_assignment_is_not_a_guessed_spool(picker: QuickFilamentPicker) -> None:
    first = _body(identifier="first", name="A", material_slots=[MaterialSlot(index=1, name="Rot")])
    second = _body(
        identifier="second", name="B", material_slots=[MaterialSlot(index=1, name="Blau")]
    )
    picker.set_context([first, second])
    assert "Mehrere Filamente" in picker.picker.currentText()
    assert picker.picker.currentData() == ""


def test_unused_slot_does_not_announce_multimaterial(picker: QuickFilamentPicker) -> None:
    """Nach dem Färben des ganzen Körpers bestimmen seine Flächen die aktuelle Anzeige."""
    active = MaterialSlot(index=0, name="Aktiv", colour=(1, 0, 0))
    stale = MaterialSlot(index=1, name="Früher", colour=(0, 0, 1))
    picker.set_context([_body("part", "Teil", [active, stale])])
    assert picker.picker.currentText() == "Im Projekt: Aktiv"


def test_partial_assignment_does_not_claim_the_whole_body_is_assigned(
    picker: QuickFilamentPicker,
) -> None:
    """Die noch unbemalten Flächen bleiben bei einem teilweise gefärbten Körper sichtbar."""
    from dataclasses import replace

    active = MaterialSlot(index=1, name="Aktiv", colour=(1, 0, 0))
    body = _body("part", "Teil", [active])
    body = replace(body, mesh=replace(body.mesh, slots=(0, 1) * 6))
    picker.set_context([body])
    assert "Mehrere Filamente" in picker.picker.currentText()


def test_mixed_body_and_face_selection_names_the_actual_scope(picker: QuickFilamentPicker) -> None:
    """Eine Flächenwahl an B darf die vollständige Zuweisung an Körper A nicht verschweigen."""
    picker.set_context(
        [_body("whole", "Ganz"), _body("partial", "Teilweise")],
        selected_features=(("partial", "top"), ("partial", "side")),
    )
    assert picker.scope.text() == "Ganze Körper: 1. Gewählte Flächen: 2."
    assert picker.picker.currentText() == "Filament für die Auswahl"


def test_refresh_and_context_do_not_emit_assignment(picker: QuickFilamentPicker) -> None:
    seen: list[filaments.CatalogueFilament] = []
    picker.spoolChosen.connect(seen.append)
    obj = _body(identifier="part", name="Teil")
    before = list(obj.material_slots)
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456", remaining_grams=123))
    picker.set_context([obj])
    picker.refresh()
    assert not seen
    assert obj.material_slots == before
    row = picker.picker.findData(entry.identifier)
    assert "123" in picker.picker.itemText(row)
    picker._chosen(row)
    assert seen == [entry]
    assert obj.material_slots == before


def test_same_label_is_a_different_choice(picker: QuickFilamentPicker) -> None:
    first = filaments.save(filaments.CatalogueFilament("Spule", "#123456", location="A"))
    second = filaments.save(filaments.CatalogueFilament("Spule", "#123456", location="B"))
    picker.set_context(
        [_body(identifier="part", name="Teil")], selected_features=(("part", "face"),)
    )
    assert "nur die gewählte Fläche" in picker.scope.text()
    assert picker.picker.findData(first.identifier) != picker.picker.findData(second.identifier)


def test_archive_between_display_and_click_does_not_assign(picker: QuickFilamentPicker) -> None:
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456"))
    picker.set_context([_body(identifier="part", name="Teil")])
    row = picker.picker.findData(entry.identifier)
    filaments.archive(entry.identifier)
    seen: list[object] = []
    picker.spoolChosen.connect(seen.append)
    picker._chosen(row)
    assert not seen
    assert picker.picker.findData(entry.identifier) < 0


@pytest.mark.parametrize("change", ["name", "colour", "material_type", "slicer_profile", "stock"])
def test_quick_choice_checks_the_identity_that_was_displayed(
    picker: QuickFilamentPicker, change: str
) -> None:
    """Nur Bestandsänderungen lassen sich ohne neue Druckentscheidung übernehmen."""
    from dataclasses import replace

    entry = filaments.save(filaments.CatalogueFilament("Alt", "#123456", "PLA"))
    picker.set_context([_body("part", "Teil")])
    row = picker.picker.findData(entry.identifier)
    updates = {
        "name": {"name": "Neu"},
        "colour": {"colour": "#987654"},
        "material_type": {"material_type": "PETG"},
        "slicer_profile": {"slicer_profile": "Neu"},
        "stock": {"remaining_grams": 200},
    }
    fresh = filaments.save(replace(entry, **updates[change]))
    seen = []
    picker.spoolChosen.connect(seen.append)
    picker._chosen(row)
    if change == "stock":
        assert seen == [fresh]
    else:
        assert not seen
        assert "erneut" in picker.notice.text()
        assert not picker.notice.isHidden()
        picker._chosen(picker.picker.findData(entry.identifier))
        assert seen == [fresh]
        assert picker.notice.isHidden()


def test_operation_dialog_forwards_spool_outside_parameters(
    qt_app: QApplication, picker: QuickFilamentPicker
) -> None:
    """Die lokale Kennung landet im Bindungsweg, niemals in reproduzierbaren Op-Werten."""
    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.filament_picker import FilamentField
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456"))
    dialog = OperationDialog(REGISTRY.get("paint_slot"), {"part": "Teil"})
    field = dialog.findChild(FilamentField)
    assert field is not None
    seen: list[object] = []
    dialog.spoolChosen.connect(seen.append)
    row = next(
        index for index in range(field.count()) if entry.identifier[:8] in field.itemText(index)
    )
    field.setCurrentIndex(row)
    field._chosen(row)
    assert seen == [entry]
    assert entry.identifier not in repr(dialog.values())
    assert dialog.values()["replace_filament"] is True


def test_dialog_project_or_neutral_choice_clears_previous_physical_spool(
    qt_app: QApplication, picker: QuickFilamentPicker
) -> None:
    """Die letzte Wahl bestimmt Werte und Bindung; eine frühere Spule bleibt nicht aktiv."""
    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.filament_picker import _ID_ROLE, FilamentField
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    entry = filaments.save(filaments.CatalogueFilament("Regal", "#123456", "PLA"))
    slot = MaterialSlot(index=2, name="Projekt", colour=(1, 0, 0), material_type="ABS")
    dialog = OperationDialog(REGISTRY.get("paint_slot"), {"part": "Teil"}, slots=[slot])
    field = dialog.findChild(FilamentField)
    seen = []
    dialog.spoolChosen.connect(seen.append)
    for row in (field.findData(entry.identifier, _ID_ROLE), field.findData(2), field.findData(0)):
        field.setCurrentIndex(row)
        field._chosen(row)
    assert seen == [entry, None, None]
    assert dialog.values()["slot"] == 0
    assert all(
        dialog.values()[key] == "" for key in ("name", "colour", "material_type", "slicer_profile")
    )
    assert not dialog.values()["replace_filament"]


def test_changed_spool_explains_reselection_in_the_open_dialog(
    qt_app: QApplication, picker: QuickFilamentPicker
) -> None:
    """Der Konflikt bleibt als lesbarer Hinweis direkt neben der erneuten Auswahl erreichbar."""
    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.filament_picker import _ID_ROLE, FilamentField
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456"))
    dialog = OperationDialog(REGISTRY.get("paint_slot"), {"part": "Teil"})
    field = dialog.findChild(FilamentField)
    row = field.findData(entry.identifier, _ID_ROLE)
    filaments.archive(entry.identifier)
    field.setCurrentIndex(row)
    field._chosen(row)
    assert not dialog._filament_notice.isHidden()
    assert "aktualisierten Liste" in dialog._filament_notice.text()
    assert field.findData(entry.identifier, _ID_ROLE) < 0


def test_multi_feature_editor_preserves_legacy_scope_and_named_choices(
    qt_app: QApplication,
) -> None:
    """Eine alte Einzelwahl öffnet als markierte Fläche und lässt sich gezielt erweitern."""
    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.op_dialog import FeatureSetField, OperationDialog

    bootstrap.load_operations()
    dialog = OperationDialog(
        REGISTRY.get("clear_filament"),
        {"part": "Teil"},
        values={"at_feature": "top"},
        features={"top": "Oberseite", "side": "Seite"},
        source_objects=("part",),
    )
    field = dialog.findChild(FeatureSetField)
    assert field is not None
    assert dialog.values()["at_feature"] == ""
    assert dialog.values()["at_features"] == ["top"]
    assert not dialog._rows["at_feature"].isRowVisible(dialog._editors["at_feature"])
    assert dialog.take_feature("side", "Seite", "part")
    assert dialog.values()["at_features"] == ["top", "side"]
    assert not dialog.take_feature("foreign", "Fremd", "other")
    assert field.list.item(0).text() == "Oberseite"


def test_empty_feature_selection_never_expands_to_the_whole_body(qt_app: QApplication) -> None:
    """Beim Umwählen bleibt die Vorschau stehen, bis eine neue begrenzte Wahl vorliegt."""
    from PySide6.QtCore import Qt

    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.op_dialog import FeatureSetField, OperationDialog

    bootstrap.load_operations()
    dialog = OperationDialog(
        REGISTRY.get("clear_filament"),
        {"part": "Teil"},
        values={"at_features": ["top"]},
        features={"top": "Oberseite"},
    )
    field = dialog.findChild(FeatureSetField)
    changes = []
    dialog.valuesChanged.connect(lambda: changes.append(dialog.values()))
    field.list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert not dialog._accept_button.isEnabled()
    assert dialog.values()["at_features"] == ["top"]
    assert not changes
    dialog.accept()
    assert dialog.result() == 0
    field.whole.setChecked(True)
    assert dialog._accept_button.isEnabled()
    assert dialog.values()["at_features"] == []
    assert changes[-1]["at_features"] == []


def test_missing_saved_feature_is_preserved_in_the_multi_editor(qt_app: QApplication) -> None:
    """Ein nicht mehr gefundenes Merkmal wird nicht still auf eine andere Fläche umgebogen."""
    from PySide6.QtCore import Qt

    from app.ui.op_dialog import FeatureSetField

    field = FeatureSetField({"side": "Seite"}, ["missing"])
    assert field.value() == ["missing"]
    assert field.list.item(1).data(Qt.ItemDataRole.UserRole) == "missing"


def test_embedded_picker_fits_the_narrow_selection_dock(qt_app: QApplication) -> None:
    """Ein schmaler Rollbereich hält Pfeil und Lagerknopf vollständig erreichbar."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QScrollArea

    from app.core.scene import OperationDraft
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.style import NORMAL, apply_style
    from app.ui.theme import apply_theme

    apply_theme(qt_app, "dark")
    apply_style(qt_app, "dark")
    session = Session()
    window = MainWindow(session, UiSettings())
    window.resize(1280, 800)
    window.show()
    assert session.apply("Prüfkörper", [OperationDraft("create_box")])
    assert session.wait_for_idle()
    result = session.evaluate_now()
    window.object_tree.select_object(next(iter(result.scene.objects)))
    # Offscreen hat synthetische Schriftmetriken. Geprüft wird mindestens
    # 244 Pixel Breite, bei größeren Knopfmaßen entsprechend mehr. Das ist
    # keine Messung einer festen nativen Fensterbreite.
    width = max(
        244, window.quick_filament.inventory_button.minimumSizeHint().width() + 2 * NORMAL + 20
    )
    window.resizeDocks([window.feature_dock], [width], Qt.Orientation.Horizontal)
    QTest.qWait(100)
    scroller = window.feature_dock.widget()
    assert isinstance(scroller, QScrollArea)
    assert scroller.horizontalScrollBar().maximum() == 0
    quick = window.quick_filament
    for control in (quick.picker, quick.inventory_button):
        right = control.mapTo(scroller.viewport(), QPoint(control.width(), 0)).x()
        assert right <= scroller.viewport().width()
        assert control.isVisible()
    quick.set_context(
        list(result.scene.objects.values()),
        selected_features=((next(iter(result.scene.objects)), "face"),),
    )
    QApplication.processEvents()
    assert quick.scope.height() >= quick.scope.heightForWidth(quick.scope.width())


def test_refresh_only_visits_each_whole_body_slot_array_once(
    picker: QuickFilamentPicker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Text und Entfernen-Knopf teilen denselben vollständigen Flächendurchlauf."""
    from app.ui import filament_assignment

    calls = []
    original = filament_assignment.used_slots

    def counted(mesh):
        calls.append(mesh)
        return original(mesh)

    monkeypatch.setattr(filament_assignment, "used_slots", counted)
    first = _body("one", "Teil", [MaterialSlot(1, "Rot")])
    second = _body("two", "Anderes Teil")
    picker.set_context([first, second])
    assert len(calls) == 2
    assert picker.clear_button.isEnabled()
