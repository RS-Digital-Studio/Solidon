"""Der Behälter-Assistent nutzt Schema, Vorschau und gemeinsame Rücknahme des Kerns."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox

from app.core.registry import REGISTRY
from app.core.scene.project import load, save
from app.ui.main_window import MainWindow
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


def _open_container(window: MainWindow, **values: object):
    """Die kompakte Netzgegenprobe verwendet denselben Menüweg und Vorschauauftrag."""
    from tests.render_fakes import RecordingRenderer

    if window.stack.currentWidget() is window.start_screen:
        assert window.start_empty()
    QApplication.processEvents()
    assert window.session.wait_for_idle(30_000)
    window.viewport.renderer = RecordingRenderer()
    window.run_operation(
        REGISTRY.get("create_container"),
        {
            "shape": "rectangular",
            "lid": "push",
            "kernel": "mesh",
            "width": 40,
            "depth": 30,
            "height": 20,
            "radius": 3,
        }
        | values,
    )
    assert window._op_dialog is not None
    return window._op_dialog


def _show_preview(window: MainWindow, qt_app: QApplication) -> None:
    """Auch die Freigabe wartet auf das gezeichnete Vorschauergebnis."""
    window._request_order_preview(window._preview_approval)
    assert window.session.wait_for_idle(60_000)
    qt_app.processEvents()


@pytest.mark.parametrize("shape", ["round", "rectangular"])
@pytest.mark.parametrize("lid", ["screw", "push", "hinged"])
def test_reopening_container_keeps_named_advanced_dimensions_in_the_fold(
    window: MainWindow, qt_app: QApplication, shape: str, lid: str
) -> None:
    """Gespeicherte Ausdrücke machen aus der Rückseite keine überfüllte Vorderseite."""
    dialog = _open_container(window, shape=shape, lid=lid)
    _show_preview(window, qt_app)
    assert dialog.can_accept(), dialog._refusal.text()
    dialog._accept_button.click()
    assert window.session.wait_for_idle(60_000)
    step = window.session.project.document.ops[0]
    assert window.session.change_params(step.id, {"floor": "=@container_wall"})
    assert window.session.wait_for_idle(60_000)
    before = deepcopy(window.session.project.document)
    entry = before.ops[0]
    window.edit_operation(entry.id)
    dialog = window._op_dialog
    assert dialog is not None
    assert not dialog.advanced.isChecked()
    active_front = [
        name
        for name, row in dialog._rows.items()
        if row is dialog._front and not dialog._editors[name].isHidden()
    ]
    assert len(active_front) <= 8, active_front
    assert {"shape", "lid", "height", "wall"} <= set(active_front)
    assert dialog._rows["floor"] is dialog._advanced_form
    assert not dialog._editors["floor"].isVisibleTo(dialog)
    values = dialog.values()
    assert values["floor"] == entry.params["floor"]
    assert values["floor"] == "=@container_wall"
    dialog.advanced.setChecked(True)
    assert dialog._editors["floor"].isVisibleTo(dialog)
    assert dialog.values() == values
    dialog.advanced.setChecked(False)
    assert not dialog._editors["floor"].isVisibleTo(dialog)
    dialog.reject()
    assert window.session.project.document == before


@pytest.mark.parametrize("shape", ["round", "rectangular"])
@pytest.mark.parametrize("lid", ["screw", "push", "hinged"])
def test_container_menu_uses_the_complete_wizard_schema(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, shape: str, lid: str
) -> None:
    """Alle sechs Kombinationen zeigen passende Felder und denselben stabilen Auftrag."""
    monkeypatch.setattr(window.session, "preview_async", lambda *_args, **_kwargs: None)
    before = deepcopy(window.session.project.document)
    window.launch_operation(REGISTRY.get("create_container"))
    dialog = window._op_dialog
    assert dialog is not None
    assert not dialog.offers_naming()
    assert "insert" in dialog._editors
    for name, value in (("shape", shape), ("lid", lid)):
        editor = dialog._editors[name]
        assert isinstance(editor, QComboBox)
        editor.setCurrentIndex(editor.findData(value))
    assert dialog._editors["diameter"].isHidden() == (shape != "round")
    assert dialog._editors["width"].isHidden() == (shape != "rectangular")
    assert dialog._editors["depth"].isHidden() == (shape != "rectangular")
    assert not dialog._editors["wall"].isHidden()
    dialog.advanced.setChecked(True)
    for name, condition in (
        ("radius", shape == "rectangular"),
        ("pitch", lid == "screw"),
        ("collar", lid == "push"),
        ("hinge_width", lid == "hinged"),
        ("opening_angle", lid == "hinged"),
    ):
        assert dialog._editors[name].isHidden() != condition, name
    assert dialog._editors["kernel"].isHidden()
    holes = dialog._editors["holes"]
    assert isinstance(holes, QCheckBox)
    for enabled in (True, False, True):
        holes.setChecked(enabled)
        assert dialog._editors["hole_diameter"].isHidden() != enabled
    order = dialog.preview_order()
    assert order == dialog.preview_order(), "Freigabe braucht identische Seeds und Maße"
    assert order.changes is not None
    assert order.changes.after.parameters
    assert order.changes.after.fits
    assert order.drafts[0].op == "create_container"
    assert order.drafts[0].params["shape"] == shape
    assert order.drafts[0].params["lid"] == lid
    dialog._editors["insert"].setChecked(True)
    inserted = dialog.preview_order()
    assert [draft.op for draft in inserted.drafts] == ["create_container", "add_container_insert"]
    assert inserted.drafts[1].inputs == inserted.drafts[0].outputs
    dialog.reject()
    assert window.session.project.document == before


@pytest.mark.parametrize("insert", [False, True])
@pytest.mark.parametrize("shape", ["round", "rectangular"])
@pytest.mark.parametrize("lid", ["screw", "push", "hinged"])
def test_container_preview_apply_undo_and_file_keep_one_transaction(
    window: MainWindow, qt_app: QApplication, tmp_path: Path, insert: bool, shape: str, lid: str
) -> None:
    """Eine sichtbare Übernahme trägt beide Körper, optionale Einlage, Maße und Passung."""
    from tests.render_fakes import RecordingRenderer

    window.viewport.renderer = RecordingRenderer()
    window.session.start_new()
    assert window.session.wait_for_idle(30_000)
    before = deepcopy(window.session.project.document)
    window.run_operation(
        REGISTRY.get("create_container"),
        {
            "shape": shape,
            "lid": lid,
            "kernel": "mesh",
            "width": 40.0,
            "depth": 30.0,
            "height": 20.0,
            "radius": 3.0,
            "insert": insert,
            "columns": 2,
        },
    )
    dialog = window._op_dialog
    assert dialog is not None
    order = dialog.preview_order()
    window._request_order_preview(window._preview_approval)
    assert window.session.wait_for_idle(60_000)
    qt_app.processEvents()
    assert dialog.can_accept(), dialog._refusal.text()
    dialog._accept_button.click()
    assert window.session.wait_for_idle(60_000)
    qt_app.processEvents()
    document = window.session.project.document
    assert len(document.transactions) == 1
    assert len(document.ops) == (2 if insert else 1)
    assert document.parameters and len(document.fits) == 1
    assert window.session.last_result.complete
    assert len(window.session.last_result.scene.objects) == (3 if insert else 2)
    assert [op.params for op in document.ops] == [draft.params for draft in order.drafts]
    written = tmp_path / "container.p3d"
    save(window.session.project, written)
    reopened = load(written)
    assert reopened.document == document
    complete = deepcopy(document)
    window.session.undo()
    assert window.session.wait_for_idle(30_000)
    assert not window.session.project.document.ops
    assert window.session.project.document.parameters == before.parameters
    assert not window.session.project.document.fits
    window.session.redo()
    assert window.session.wait_for_idle(60_000)
    assert window.session.project.document == complete


def test_container_invalid_geometry_recovers_and_rapid_changes_use_last_values(
    window: MainWindow, qt_app: QApplication
) -> None:
    """Ungültige Wände ändern nichts; erst die letzte gültige Vorschau darf übernommen werden."""
    before = deepcopy(window.session.project.document)
    dialog = _open_container(window, wall=8, depth=10)
    assert dialog.values()["wall"] == pytest.approx(8), dialog.values()
    assert dialog.values()["depth"] == pytest.approx(10), dialog.values()
    _show_preview(window, qt_app)
    assert not dialog.can_accept()
    assert dialog._refusal.text()
    assert window.session.project.document == before
    for wall, width in ((2, 42), (3, 44), (2.5, 48)):
        dialog.take_placement({"wall": wall, "width": width, "depth": 30})
        window._request_order_preview(window._preview_approval)
    assert window.session.wait_for_idle(60_000)
    qt_app.processEvents()
    assert dialog.can_accept(), dialog._refusal.text()
    expected = dialog.preview_order()
    dialog._accept_button.click()
    assert window.session.wait_for_idle(60_000)
    document = window.session.project.document
    assert document.parameters["container_wall"].value == pytest.approx(2.5)
    assert document.parameters["container_width"].value == pytest.approx(48)
    assert document.ops[-1].params == expected.drafts[0].params
    assert window.session.last_result.complete


@pytest.mark.parametrize("project_change", [False, True])
def test_container_discard_removes_uncommitted_parameters_and_fit(
    window: MainWindow, qt_app: QApplication, project_change: bool
) -> None:
    """Abbruch und Projektwechsel übernehmen auch nach gültiger Vorschau keine Assistentendaten."""
    before = deepcopy(window.session.project.document)
    dialog = _open_container(window, insert=True)
    _show_preview(window, qt_app)
    assert dialog.can_accept(), dialog._refusal.text()
    if project_change:
        window.session.start_new()
        assert window.session.wait_for_idle(30_000)
        assert window._op_dialog is None
        assert not window.session.project.document.ops
        assert not window.session.project.document.fits
        assert not any(
            name.startswith("container_") for name in window.session.project.document.parameters
        )
    else:
        dialog.reject()
        assert window.session.wait_for_idle(30_000)
        assert window.session.project.document == before


def test_two_container_wizards_keep_separate_parameter_names_and_undo(
    window: MainWindow, qt_app: QApplication
) -> None:
    """Ein zweiter Behälter überschreibt weder Maße noch Passung des ersten."""
    for width in (40, 50):
        dialog = _open_container(window, width=width)
        _show_preview(window, qt_app)
        assert dialog.can_accept(), dialog._refusal.text()
        dialog._accept_button.click()
        assert window.session.wait_for_idle(60_000)
    document = window.session.project.document
    assert document.parameters["container_width"].value == pytest.approx(40)
    assert document.parameters["container_2_width"].value == pytest.approx(50)
    assert len(document.fits) == 2
    assert len({fit.name for fit in document.fits}) == 2
    window.session.undo()
    assert window.session.wait_for_idle(60_000)
    assert "container_2_width" not in document.parameters
    assert document.parameters["container_width"].value == pytest.approx(40)
    assert len(document.fits) == 1


@pytest.mark.parametrize("lid", ["screw", "hinged"])
def test_editing_a_container_lid_keeps_the_fit_in_preview_commit_and_undo(
    window: MainWindow, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, lid: str
) -> None:
    """Ein anderer Deckel ersetzt das Passungspaar auch in der Vorschau, mitsamt Rückweg."""
    import app.ui.session as session_module
    from app.core.lid_flow import fit_for_container

    dialog = _open_container(window, insert=True)
    _show_preview(window, qt_app)
    assert dialog.can_accept()
    dialog._accept_button.click()
    assert window.session.wait_for_idle(60_000)
    before = deepcopy(window.session.project.document)
    step = next(op for op in before.ops if op.op == "create_container")
    observed = []
    original_evaluate = session_module.evaluate

    def evaluate_with_fit(document, *args, **kwargs):
        current = next((op for op in document.ops if op.id == step.id), None)
        if current is not None and current.params["lid"] == lid:
            expected = fit_for_container(current, before.fits)
            observed.append(tuple(document.fits))
            assert expected in document.fits
        return original_evaluate(document, *args, **kwargs)

    monkeypatch.setattr(session_module, "evaluate", evaluate_with_fit)
    window.edit_operation(step.id, given={"lid": lid})
    dialog = window._op_dialog
    assert dialog is not None
    _show_preview(window, qt_app)
    assert dialog.can_accept(), dialog._refusal.text()
    assert observed, "Die Vorschau selbst muss die geänderte Passung prüfen"
    assert window.session.project.document == before
    expected_order = dialog.preview_order()
    dialog._accept_button.click()
    assert window.session.wait_for_idle(60_000)
    document = window.session.project.document
    assert tuple(document.fits) == tuple(expected_order.changes.after.fits)
    assert document.fits[0].name == before.fits[0].name
    assert document.fits[0].tolerance == before.fits[0].tolerance
    assert window.session.last_result.complete
    after = deepcopy(document)
    window.session.undo()
    assert window.session.wait_for_idle(60_000)
    assert window.session.project.document.ops == before.ops
    assert window.session.project.document.fits == before.fits
    window.session.redo()
    assert window.session.wait_for_idle(60_000)
    assert window.session.project.document == after


@pytest.mark.parametrize("shape", ["round", "rectangular"])
@pytest.mark.parametrize("lid", ["screw", "push", "hinged"])
def test_container_parameter_row_resizes_lid_and_insert_together(
    window: MainWindow, qt_app: QApplication, shape: str, lid: str
) -> None:
    """Die echte Parameterzeile ändert Außenmaß, Deckel und Einlage mit einem Rückweg."""
    dialog = _open_container(window, shape=shape, lid=lid, insert=True)
    _show_preview(window, qt_app)
    assert dialog.can_accept(), dialog._refusal.text()
    dialog._accept_button.click()
    assert window.session.wait_for_idle(60_000)
    before = deepcopy(window.session.project.document)
    volumes = {
        key: body.mesh.volume for key, body in window.session.last_result.scene.objects.items()
    }
    # Der automatische Gewindehals folgt der schmaleren Innenweite: beim
    # rechteckigen Prüfteil ist das die Tiefe, nicht die größere Breite.
    name = "container_diameter" if shape == "round" else "container_depth"
    old = before.parameters[name].value
    window.parameters._editors[name].setValue(old + 10)
    qt_app.processEvents()
    assert window.session.wait_for_idle(60_000)
    document = window.session.project.document
    assert document.parameters[name].value == pytest.approx(old + 10)
    assert len(document.transactions) == len(before.transactions) + 1
    result = window.session.last_result
    assert result.complete
    assert len(result.scene.objects) == 3
    for key, body in result.scene.objects.items():
        assert body.mesh.volume > volumes[key], key
    assert document.fits == before.fits
    window.session.undo()
    assert window.session.wait_for_idle(60_000)
    assert window.session.project.document.parameters[name].value == pytest.approx(old)
    for key, body in window.session.last_result.scene.objects.items():
        assert body.mesh.volume == pytest.approx(volumes[key])


@pytest.mark.parametrize("lid", ["push", "screw", "hinged"])
def test_historical_container_shape_change_names_only_new_main_dimensions(
    window: MainWindow, qt_app: QApplication, tmp_path: Path, lid: str
) -> None:
    """Formwechsel bindet neue Hauptmaße in Vorschau und Übernahme, mit allen Rückwegen."""
    dialog = _open_container(window, shape="round", lid=lid, insert=True)
    _show_preview(window, qt_app)
    assert dialog.can_accept(), dialog._refusal.text()
    dialog._accept_button.click()
    assert window.session.wait_for_idle(60_000)
    before = deepcopy(window.session.project.document)
    assert set(before.parameters) == {"container_diameter", "container_height", "container_wall"}
    step = next(op for op in before.ops if op.op == "create_container")
    window.edit_operation(step.id, given={"shape": "rectangular", "width": 48, "depth": 36})
    dialog = window._op_dialog
    assert dialog is not None
    _show_preview(window, qt_app)
    assert dialog.can_accept(), dialog._refusal.text()
    order = dialog.preview_order()
    assert order.change_values["width"] == "=@container_width"
    assert order.change_values["depth"] == "=@container_depth"
    assert order.changes.after.parameters["container_width"].value == pytest.approx(48)
    assert window.session.project.document == before
    dialog._accept_button.click()
    assert window.session.wait_for_idle(60_000)
    qt_app.processEvents()
    document = window.session.project.document
    after = deepcopy(document)
    assert set(document.parameters) == set(before.parameters) | {
        "container_width",
        "container_depth",
    }
    assert set(window.parameters._editors) == set(document.parameters)
    assert document.ops[0].params == order.change_values
    assert window.session.last_result.complete
    assert len(window.session.last_result.scene.objects) == 3
    assert len(document.transactions) == len(before.transactions) + 1
    path = tmp_path / "changed-container-shape.p3d"
    save(window.session.project, path)
    assert load(path).document == window.session.project.document
    after = deepcopy(window.session.project.document)
    window.session.undo()
    assert window.session.wait_for_idle(60_000)
    assert window.session.project.document.parameters == before.parameters
    assert window.session.project.document.ops == before.ops
    window.session.redo()
    assert window.session.wait_for_idle(60_000)
    assert window.session.project.document == after
    window.edit_operation(step.id, given={"shape": "round"})
    dialog = window._op_dialog
    assert dialog is not None
    _show_preview(window, qt_app)
    assert dialog.can_accept(), dialog._refusal.text()
    dialog._accept_button.click()
    assert window.session.wait_for_idle(60_000)
    assert window.session.project.document.ops[0].params["diameter"] == "=@container_diameter"
    assert window.session.project.document.parameters == after.parameters
    assert window.session.last_result.complete
