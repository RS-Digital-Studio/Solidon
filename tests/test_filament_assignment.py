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
        mesh=MeshData.of(trimesh.creation.box()),
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
    picker.set_context([_body(identifier="part", name="Teil")], has_feature=True)
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
    # Offscreen hat synthetische Schriftmetriken. Der Einzelknopf bestimmt
    # deshalb beide Seiten der Breitenzusage; die echten 244 Pixel werden
    # zusätzlich auf der nativen Plattform geprüft.
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
    quick.set_context(list(result.scene.objects.values()), has_feature=True)
    QApplication.processEvents()
    assert quick.scope.height() >= quick.scope.heightForWidth(quick.scope.width())
