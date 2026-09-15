"""Maße, Einzelwände und Arbeiter stimmen mit der späteren Organizer-Operation überein."""

from __future__ import annotations

import threading

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

from app.core.organizer.build import build_organizer
from app.core.organizer.serialize import (
    LayoutSpec,
    Node,
    grid_layout,
    layout_to_text,
)
from app.ui.organizer_dialog import OrganizerDialog, OrganizerLayoutField
from tests.test_outline_dialog import _until


def dispose(dialog: OrganizerDialog, app: QApplication) -> None:
    dialog.release()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("blocked", [False, True])
def test_tree_rebuild_restores_the_previous_signal_state_on_error(qt_app, monkeypatch, blocked):
    """Ein fehlerhafter Baumaufbau darf den Wähler weder stummschalten noch fremd freigeben."""
    dialog = OrganizerDialog({})
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        dialog.tree.blockSignals(blocked)

        def refuse():
            raise ValueError("own tree probe")

        with monkeypatch.context() as patch:
            patch.setattr(dialog.tree, "clear", refuse)
            with pytest.raises(ValueError, match="own tree probe"):
                dialog._rebuild_tree()
        assert dialog.tree.signalsBlocked() is blocked
    finally:
        dispose(dialog, qt_app)


def test_editor_keeps_expressions_and_exact_preview_and_changes_one_repeated_wall(qt_app):
    dialog = OrganizerDialog(
        {"width": "=@outer_width", "layout": layout_to_text(grid_layout())},
        {"outer_width": 180},
        layout_only=True,
    )
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        before = dialog._layout
        wall = next(w for w in before.walls if "columns/wall_1" in w.id)
        dialog._graphic_chosen("wall", wall.id)
        assert dialog.tree.currentItem() is None
        assert not dialog.tree.selectedItems()
        _until(qt_app, dialog.accept_button.isEnabled)
        assert 'data-highlight="true"' in dialog._preview_svg
        assert 'data-selection-contour="true"' in dialog._preview_svg
        assert "Ausgewählt: Trennwand" in dialog._preview_svg
        dialog._edit_fields["height"].set_value(50)
        assert not dialog.accept_button.isEnabled()
        _until(qt_app, dialog.accept_button.isEnabled)
        assert [w.id for w in dialog._layout.walls if w.height == pytest.approx(50)] == [wall.id]
        assert dialog.values()["width"] == "=@outer_width"
        expected = build_organizer(dialog._layout)
        assert np.array_equal(expected.mesh.raw.vertices, dialog.result_preview.mesh.raw.vertices)
        assert np.array_equal(expected.mesh.raw.faces, dialog.result_preview.mesh.raw.faces)
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dispose(dialog, qt_app)


def test_split_preserves_inner_bounds_and_uses_existing_wall_value(qt_app):
    spec = LayoutSpec("inner", Node("cell", "cell", width=80, depth=60, radius=0))
    dialog = OrganizerDialog({"layout": layout_to_text(spec), "wall": 4, "radius": 0})
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        before = dialog._layout
        dialog._split_node("cell", "x")
        _until(qt_app, dialog.accept_button.isEnabled)
        assert (dialog._layout.width, dialog._layout.depth) == pytest.approx(
            (before.width, before.depth)
        )
        assert len(dialog._layout.cells) == 2
        assert dialog._layout.walls[0].rect.width == pytest.approx(4)
    finally:
        dispose(dialog, qt_app)


def test_layout_only_basis_change_preserves_original_outer_expression(qt_app):
    dialog = OrganizerDialog(
        {"width": "=@outer_width", "layout": layout_to_text(grid_layout(basis="inner"))},
        {"outer_width": 190},
        layout_only=True,
    )
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        dialog.basis.setCurrentIndex(0)
        _until(qt_app, dialog.accept_button.isEnabled)
        assert dialog.values()["width"] == "=@outer_width"
        assert dialog._layout.width == pytest.approx(190)
        assert "vorher" in dialog.basis_notice.text()
        assert "jetzt" in dialog.basis_notice.text()
    finally:
        dispose(dialog, qt_app)


@pytest.mark.parametrize("outer", [190.0, "=@outer_width"])
def test_standalone_basis_switch_keeps_free_measures_or_explains_bound_change(qt_app, outer):
    dialog = OrganizerDialog(
        {"width": outer, "layout": layout_to_text(grid_layout(basis="inner"))}, {"outer_width": 190}
    )
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        previous = dialog._layout.width
        dialog.basis.setCurrentIndex(0)
        _until(qt_app, dialog.accept_button.isEnabled)
        if isinstance(outer, str):
            assert dialog.values()["width"] == outer
            assert dialog._layout.width == pytest.approx(190)
        else:
            assert dialog.values()["width"] == pytest.approx(previous)
            assert dialog._layout.width == pytest.approx(previous)
        assert "vorher" in dialog.basis_notice.text()
    finally:
        dispose(dialog, qt_app)


def test_cancelled_slow_preview_never_becomes_an_accepted_result(qt_app, monkeypatch):
    import app.ui.organizer_dialog as module

    entered, gate = threading.Event(), threading.Event()
    original = module.build_organizer

    def slow(*args, **kwargs):
        entered.set()
        gate.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "build_organizer", slow)
    dialog = OrganizerDialog({})
    try:
        _until(qt_app, entered.is_set)
        dialog.reject()
        gate.set()
        dialog.release()
        qt_app.processEvents()
        assert dialog.result_preview is None
        assert not dialog.accept_button.isEnabled()
    finally:
        gate.set()
        dispose(dialog, qt_app)


def test_invalid_wall_height_blocks_acceptance_until_corrected(qt_app):
    dialog = OrganizerDialog({})
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        wall = dialog._layout.walls[0]
        dialog._graphic_chosen("wall", wall.id)
        dialog._edit_fields["height"].set_value(1)
        _until(qt_app, lambda: dialog._worker is None and not dialog._pending)
        dialog.accept()
        assert dialog.result() != QDialog.DialogCode.Accepted
        assert not dialog.accept_button.isEnabled()
        dialog._edit_fields["height"].set_value(30)
        _until(qt_app, dialog.accept_button.isEnabled)
    finally:
        dispose(dialog, qt_app)


def test_worker_calculates_layout_mesh_and_projection_off_main_thread(qt_app, monkeypatch):
    import app.ui.organizer_dialog as module

    main = threading.get_ident()
    calls = []
    for name in ("resolve_layout", "build_organizer"):
        original = getattr(module, name)

        def checked(*args, _name=name, _original=original, **kwargs):
            calls.append((_name, threading.get_ident()))
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, checked)
    original = module.drawing.project

    def project(*args, **kwargs):
        calls.append(("project", threading.get_ident()))
        return original(*args, **kwargs)

    monkeypatch.setattr(module.drawing, "project", project)
    dialog = OrganizerDialog({})
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        assert {name for name, _ in calls} == {"resolve_layout", "build_organizer", "project"}
        assert all(thread != main for _, thread in calls)
    finally:
        dispose(dialog, qt_app)


def test_invalid_field_is_preserved_and_never_shown_as_json(qt_app):
    field = OrganizerLayoutField("{damaged")
    try:
        assert field.value() == "{damaged"
        assert not field.valid
        assert not field.findChildren(QLineEdit)
        field.set_value(layout_to_text(grid_layout()))
        assert field.valid
    finally:
        field.deleteLater()
        qt_app.processEvents()


def test_selection_reprojects_existing_body_without_rebuilding_geometry(qt_app, monkeypatch):
    import app.ui.organizer_dialog as module

    calls = []
    build = module.build_organizer

    def counted(*args, **kwargs):
        calls.append(True)
        return build(*args, **kwargs)

    monkeypatch.setattr(module, "build_organizer", counted)
    dialog = OrganizerDialog({})
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        body = dialog.result_preview.mesh
        count = len(calls)
        dialog._graphic_chosen("wall", dialog._layout.walls[0].id)
        _until(qt_app, dialog.accept_button.isEnabled)
        assert len(calls) == count
        assert dialog.result_preview.mesh is body
        dialog._graphic_chosen("cell", dialog._layout.cells[0].id)
        _until(qt_app, dialog.accept_button.isEnabled)
        assert len(calls) == count
        assert 'data-highlight="true"' in dialog._preview_svg
    finally:
        dispose(dialog, qt_app)
