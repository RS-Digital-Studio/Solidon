"""Dichtweg, Vorschau und Verlauf verwenden denselben unveränderten Trägereingang."""

import copy

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.core.bootstrap import load_operations
from app.core.geom.seal import opening_choices
from app.core.geom.seal_ops import CreateSealParams
from app.core.registry import REGISTRY
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_to_text
from app.core.types import FeatureRef
from app.ui.main_window import MainWindow
from app.ui.op_dialog import OperationDialog
from app.ui.seal_dialog import SealPathField
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.test_outline_dialog import _until
from tests.test_seal_openings import plate
from tests.test_seal_ops import cube


@pytest.fixture
def spec():
    load_operations()
    assert CreateSealParams.spec()
    return REGISTRY.get("create_seal")


def open_window(tmp_path, entry):
    path = tmp_path / "carrier.stl"
    path.write_bytes(entry.mesh.raw.export(file_type="stl"))
    window = MainWindow(Session(), UiSettings())
    window.open_path(path)
    assert window.session.wait_for_idle(30000)
    assert window.session.last_result.complete
    return window


def open_operation(window, spec, **values):
    source = next(iter(window.session.last_result.scene.objects))
    window.run_operation(spec, values, on_bodies=(source,))
    dialog = window._op_dialog
    assert dialog is not None
    return dialog


def drawing_values():
    return {
        "path_sketch": sketch_to_text(shapes.circle(10)),
        "groove_width": 2,
        "groove_depth": 2,
        "gasket_width": 1.6,
        "protrusion": 0.4,
        "body_material": "petg",
        "gasket_material": "tpu-95a",
    }


def test_one_field_keeps_all_four_values_and_preserves_dimension_expressions(qt_app, spec):
    entry = plate()
    selected = opening_choices(entry, FeatureRef(entry.id, "top"))[1]
    values = {
        "path_sketch": "",
        "support_feature": "plate:top",
        "opening_signature": selected.signature,
        "counterface": "other:bottom",
        "groove_depth": "=@depth",
        "body_material": "petg",
        "gasket_material": "tpu-95a",
    }
    dialog = OperationDialog(spec, {}, values=values)
    field = dialog._editors["path_sketch"]
    assert isinstance(field, SealPathField)
    assert not {"support_feature", "opening_signature", "counterface"} & dialog._editors.keys()
    assert all(dialog.values()[key] == value for key, value in values.items())
    field.set_selection({"path_sketch": sketch_to_text(shapes.circle(10))})
    changed = dialog.values()
    assert changed["groove_depth"] == "=@depth"
    assert changed["body_material"] == "petg" and changed["gasket_material"] == "tpu-95a"
    assert (
        changed["support_feature"] == changed["opening_signature"] == changed["counterface"] == ""
    )
    dialog.reject()


def test_empty_path_disables_apply_and_does_not_launch_a_sketch_first(qt_app, tmp_path, spec):
    window = open_window(tmp_path, cube())
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    window.launch_operation(spec)
    dialog = window._op_dialog
    assert dialog is not None and dialog.spec.name == "create_seal"
    assert isinstance(dialog._editors["path_sketch"], SealPathField)
    assert not dialog._accept_button.isEnabled()
    assert "Dichtweg" in dialog._accept_button.toolTip()
    assert not window._preview_shown
    dialog.accept()
    assert len(window.session.project.document.ops) == 1
    dialog.reject()


@pytest.mark.parametrize(
    ("name", "width"),
    [("create_seal_gasket", 2.6), ("insert_seal_gasket", 2.6), ("insert_seal_groove", 3.0)],
)
def test_path_width_is_a_section_measure_and_never_the_drawing_extent(qt_app, spec, name, width):
    dialog = OperationDialog(REGISTRY.get(name), {})
    drawing = dialog.values()["path_sketch"]
    assert dialog.values()["width"] == pytest.approx(width)
    dialog._editors["width"].set_value(width + 1)
    assert dialog.values()["width"] == pytest.approx(width + 1)
    assert dialog.values()["path_sketch"] == drawing
    dialog.reject()


def test_opening_choice_is_readonly_until_the_normal_operation_dialog_applies(
    qt_app, tmp_path, spec
):
    window = open_window(tmp_path, plate())
    before = window.session.last_result
    document = copy.deepcopy(window.session.project.document)
    dialog = open_operation(window, spec)
    field = dialog._editors["path_sketch"]
    QTest.mouseClick(field.button, Qt.MouseButton.LeftButton)
    chooser = dialog.seal_flow.editor
    assert chooser is not None
    chooser.mode.setCurrentIndex(chooser.mode.findData("opening"))
    source = next(iter(before.scene.objects.values()))
    top = next(
        feature.id
        for feature in source.features.values()
        if feature.kind == "face" and feature.params["normal"][2] > 0.99
    )
    chooser.support.setCurrentIndex(chooser.support.findData(f"{source.id}:{top}"))
    _until(qt_app, lambda: chooser.contours.count() == 2)
    assert not chooser.accept_button.isEnabled()
    chooser.contours.setCurrentRow(1)
    _until(qt_app, chooser.accept_button.isEnabled)
    chosen = chooser.values()
    QTest.mouseClick(chooser.accept_button, Qt.MouseButton.LeftButton)
    assert field.selection() == chosen
    assert window.session.last_result is before
    assert window.session.project.document == document
    assert dialog.values()["support_feature"] == f"{source.id}:{top}"
    dialog.reject()


def test_drawing_applies_once_and_history_chooses_the_input_before_the_groove(
    qt_app, tmp_path, spec
):
    window = open_window(tmp_path, cube())
    session = window.session
    before = session.last_result
    dialog = open_operation(window, spec, **drawing_values())
    assert dialog._accept_button.isEnabled()
    _until(qt_app, lambda: window._preview_shown and not window._preview_busy.isActive())
    assert session.last_result is before
    dialog.accept()
    assert session.wait_for_idle(30000)
    result = session.last_result
    assert result.complete
    assert len(result.scene.objects) == 2
    operation = session.project.document.ops[-1]
    assert operation.op == "create_seal"
    assert len(session.project.document.transactions[-1].ops) == 1
    volumes = sorted(entry.mesh.volume for entry in result.scene.objects.values())
    assert volumes[-1] < 8000
    window.edit_operation(operation.id, field="opening_signature")
    editing = window._op_dialog
    assert editing is not None
    assert editing.values()["path_sketch"] == drawing_values()["path_sketch"]
    QTest.mouseClick(editing._editors["path_sketch"].button, Qt.MouseButton.LeftButton)
    _until(qt_app, lambda: editing.seal_flow.editor is not None)
    chooser = editing.seal_flow.editor
    _until(qt_app, chooser.accept_button.isEnabled)
    assert chooser.source.mesh.volume == pytest.approx(8000)
    assert len(chooser.objects) == 1
    assert chooser._surroundings.bodies[0].volume == pytest.approx(8000)
    assert session.last_result is result
    chooser.accept()
    assert editing.values()["path_sketch"] == drawing_values()["path_sketch"]
    editing.reject()
    session.undo()
    assert session.wait_for_idle(30000)
    assert len(session.last_result.scene.objects) == 1
    assert next(iter(session.last_result.scene.objects.values())).mesh.volume == pytest.approx(8000)
    session.redo()
    assert session.wait_for_idle(30000)
    assert sorted(
        entry.mesh.volume for entry in session.last_result.scene.objects.values()
    ) == pytest.approx(volumes)


def test_closed_history_ignores_late_preparation_and_keeps_sources_snapshot(
    qt_app, tmp_path, spec, monkeypatch
):
    window = open_window(tmp_path, cube())
    dialog = open_operation(window, spec, **drawing_values())
    flow = dialog.seal_flow
    flow.baseline = None
    callbacks = []
    monkeypatch.setattr(window.session, "placement_async", lambda *args: callbacks.append(args))
    flow.choose()
    _compute, ready, _failed = callbacks[0]
    project = window.session.project
    source = next(iter(project.sources))
    previous = project.sources[source]
    project.sources[source] = b"changed source"
    assert flow.sources[source] == previous
    dialog.reject()
    assert flow._cancel.is_cancelled
    ready(window.session.last_result)
    assert flow.editor is None


def test_document_change_closes_the_readonly_chooser(qt_app, tmp_path, spec):
    window = open_window(tmp_path, cube())
    dialog = open_operation(window, spec, **drawing_values())
    flow = dialog.seal_flow
    flow.choose()
    assert flow.editor is not None
    window.session.projectChanged.emit()
    assert flow._closed
    assert flow.editor is None
