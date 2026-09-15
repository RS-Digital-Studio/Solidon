"""Das Lochfeld verlangt seine Region und hält beide Zeichnungen auseinander."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_to_text
from app.ui.op_dialog import OperationDialog, SketchUseDialog
from app.ui.sketch_editor import SketchField


@pytest.fixture
def field_dialog(qt_app: QApplication):
    load_operations()
    dialog = OperationDialog(REGISTRY.get("field_cut"), {"body": "Platte"})
    yield dialog
    dialog.reject()
    dialog.deleteLater()


def test_field_cannot_be_applied_until_its_region_is_drawn(field_dialog):
    region = field_dialog._editors["region_sketch"]
    assert isinstance(region, SketchField)
    assert "Grundform" not in region.summary.text()
    assert not field_dialog._accept_button.isEnabled()
    assert "Feldbereich" in field_dialog._accept_button.toolTip()
    field_dialog.accept()
    assert field_dialog.result() == QDialog.DialogCode.Rejected
    region.set_text(sketch_to_text(shapes.rectangle(40, 30)))
    assert field_dialog._accept_button.isEnabled()
    region.set_text("")
    assert not field_dialog._accept_button.isEnabled()


def test_field_exclusions_are_optional_and_preserve_their_own_contour(field_dialog):
    region = field_dialog._editors["region_sketch"]
    exclusion = field_dialog._editors["exclusion_sketch"]
    assert isinstance(region, SketchField) and isinstance(exclusion, SketchField)
    assert "Grundform" not in exclusion.summary.text()
    outer = sketch_to_text(shapes.rectangle(40, 30))
    inner = sketch_to_text(shapes.circle(8))
    region.set_text(outer)
    assert field_dialog._accept_button.isEnabled()
    exclusion.set_text(inner)
    assert field_dialog.values()["region_sketch"] == outer
    assert field_dialog.values()["exclusion_sketch"] == inner
    exclusion.set_text("")
    assert field_dialog._accept_button.isEnabled()


def test_an_invalid_required_sketch_keeps_the_correction_visible(field_dialog):
    region = field_dialog._editors["region_sketch"]
    region.set_text("{broken}")
    assert not field_dialog._accept_button.isEnabled()
    assert region.summary.text() in field_dialog._accept_button.toolTip()
    region.set_text(sketch_to_text(shapes.rectangle(40, 30)))
    assert field_dialog._accept_button.isEnabled()


@pytest.mark.parametrize("on_body", ["", "Platte"])
def test_free_sketch_explains_why_cutting_needs_a_body(qt_app, on_body):
    load_operations()
    dialog = SketchUseDialog(on_body=on_body)
    for row in range(dialog._list.count()):
        item = dialog._list.item(row)
        if item.data(Qt.ItemDataRole.UserRole) not in {"field_cut", "sketch_pocket"}:
            continue
        assert bool(item.flags() & Qt.ItemFlag.ItemIsEnabled) == bool(on_body)
        if not on_body:
            assert "Körper" in item.text()
            dialog._list.setCurrentRow(row)
            assert not dialog.chosen()
            assert not dialog._use.isEnabled()
    dialog.reject()
    dialog.deleteLater()


def test_free_sketch_field_uses_the_body_beneath_the_drawing(qt_app, monkeypatch):
    from app.core.scene import OperationDraft
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    window.session.apply("Platte", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(30000)
    window.object_tree.tree.clearSelection()
    identifier = next(iter(window.session.last_result.scene.objects))
    monkeypatch.setattr(SketchUseDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(SketchUseDialog, "chosen", lambda self: "field_cut")
    text = sketch_to_text(shapes.rectangle(20, 20))
    window.start_sketch("", text)
    assert window._body_under_the_outline() == identifier
    window.finish_sketch()
    dialog = window._op_dialog
    assert dialog is not None
    assert dialog.spec.name == "field_cut"
    assert dialog.values()["region_sketch"] == text
    assert window.object_tree.selected_objects() == (identifier,)
    dialog.reject()
