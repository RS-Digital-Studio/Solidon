"""Das Lochfeld verlangt seine Region und hält beide Zeichnungen auseinander."""

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_to_text
from app.ui.op_dialog import OperationDialog
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
