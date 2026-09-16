"""Profilklemmen verlangen zwei ausdrückliche Materialien und nur passende Konturfelder."""

import pytest
from PySide6.QtWidgets import QDialog

from app.core.bootstrap import load_operations
from app.core.geom.profile_clamp_ops import ProfileClampSetParams
from app.core.registry import REGISTRY
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_to_text
from app.ui.op_dialog import MaterialField, OperationDialog


@pytest.fixture
def clamp_dialog(qt_app):
    load_operations()
    assert ProfileClampSetParams.spec()
    dialog = OperationDialog(REGISTRY.get("create_profile_clamp_set"), {})
    yield dialog
    dialog.reject()
    dialog.deleteLater()


def material(dialog, field, value):
    editor = dialog._editors[field]
    index = editor.findData(value)
    assert index >= 0
    editor.setCurrentIndex(index)


def test_both_material_roles_are_explicit_and_gate_acceptance(clamp_dialog):
    dialog = clamp_dialog
    for field in ("clamp_material", "liner_material"):
        editor = dialog._editors[field]
        assert "Wie das Projekt" not in editor.currentText()
        assert not editor.value()
    assert not dialog._accept_button.isEnabled()
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Rejected
    material(dialog, "clamp_material", "petg")
    assert not dialog._accept_button.isEnabled()
    assert "Einlagen" in dialog._accept_button.toolTip()
    material(dialog, "liner_material", "tpu-95a")
    assert dialog._accept_button.isEnabled()
    assert dialog.values()["clamp_material"] == "petg"
    assert dialog.values()["liner_material"] == "tpu-95a"
    material(dialog, "clamp_material", "")
    assert not dialog._accept_button.isEnabled()


def test_drawn_profile_requires_its_visible_drawing_but_round_keeps_its_dimension(clamp_dialog):
    dialog = clamp_dialog
    material(dialog, "clamp_material", "petg")
    material(dialog, "liner_material", "tpu-95a")
    shape = dialog._editors["profile_shape"]
    diameter = dialog.values()["diameter"]
    assert dialog._accept_button.isEnabled()
    shape.setCurrentIndex(shape.findData("drawn"))
    assert not dialog._accept_button.isEnabled()
    drawing = dialog._editors["counter_sketch"]
    assert not drawing.isHidden()
    drawing.set_text(sketch_to_text(shapes.rectangle(25, 15)))
    assert dialog._accept_button.isEnabled()
    drawing.set_text("")
    assert not dialog._accept_button.isEnabled()
    shape.setCurrentIndex(shape.findData("round"))
    assert dialog._accept_button.isEnabled()
    assert dialog.values()["diameter"] == diameter


def test_optional_material_still_can_follow_the_project(qt_app):
    editor = MaterialField("")
    assert editor.currentText() == "Wie das Projekt"
    assert editor.value() == ""
    editor.deleteLater()


def test_inactive_ellipse_width_preserves_a_confirmed_drawing(clamp_dialog):
    """Ein früheres Ellipsenmaß darf den gezeichneten Kreis nicht strecken."""
    dialog = clamp_dialog
    shape = dialog._editors["profile_shape"]
    shape.setCurrentIndex(shape.findData("ellipse"))
    dialog._editors["width"].set_value(47.0)
    shape.setCurrentIndex(shape.findData("drawn"))
    drawing = sketch_to_text(shapes.circle(16))
    dialog._editors["counter_sketch"].set_text(drawing)
    assert dialog.values()["counter_sketch"] == drawing
    assert dialog.values()["width"] == pytest.approx(47.0)
    assert not dialog._editors["width"].isEnabled()
    material(dialog, "clamp_material", "petg")
    assert dialog.values()["counter_sketch"] == drawing


def test_profile_clamp_opens_form_choice_before_an_optional_drawing(qt_app):
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    load_operations()
    window = MainWindow(Session(), UiSettings())
    window.launch_operation(REGISTRY.get("create_profile_clamp_set"))
    dialog = window._op_dialog
    assert dialog is not None
    assert dialog.spec.name == "create_profile_clamp_set"
    assert dialog.values()["profile_shape"] == "round"
    assert dialog._editors["counter_sketch"].isHidden()
    dialog.reject()
