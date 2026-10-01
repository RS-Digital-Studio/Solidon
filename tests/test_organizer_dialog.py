"""Maße, Einzelwände und Arbeiter stimmen mit der späteren Organizer-Operation überein."""

from __future__ import annotations

import threading

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QScrollArea

from app.core.organizer.build import build_organizer
from app.core.organizer.serialize import (
    LayoutSpec,
    Node,
    grid_layout,
    layout_to_text,
)
from app.ui.organizer_dialog import OrganizerDialog, OrganizerLayoutField
from tests.ui_helpers import wait_until


def dispose(dialog: OrganizerDialog, app: QApplication) -> None:
    dialog.release()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_translated_editor_wraps_long_labels_without_horizontal_scrolling(qt_app):
    """Lange spanische Beschriftungen bleiben im schmalen linken Formular lesbar."""
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language

    spoken = get_language()
    install_language("es")
    set_language("es")
    dialog = OrganizerDialog({})
    try:
        dialog.show()
        wait_until(qt_app, dialog.accept_button.isEnabled)
        scroll = dialog.editor.parentWidget().parentWidget()
        assert isinstance(scroll, QScrollArea)
        assert scroll.horizontalScrollBar().maximum() == 0
        for field in dialog._edit_fields.values():
            assert dialog.editor.rect().contains(field.geometry())
    finally:
        dispose(dialog, qt_app)
        install_language(spoken)
        set_language(spoken)


@pytest.mark.parametrize("blocked", [False, True])
def test_tree_rebuild_restores_the_previous_signal_state_on_error(qt_app, monkeypatch, blocked):
    """Ein fehlerhafter Baumaufbau darf den Wähler weder stummschalten noch fremd freigeben."""
    dialog = OrganizerDialog({})
    try:
        wait_until(qt_app, dialog.accept_button.isEnabled)
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
        wait_until(qt_app, dialog.accept_button.isEnabled)
        before = dialog._layout
        wall = next(w for w in before.walls if "columns/wall_1" in w.id)
        dialog._graphic_chosen("wall", wall.id)
        assert dialog.tree.currentItem() is None
        assert not dialog.tree.selectedItems()
        wait_until(qt_app, dialog.accept_button.isEnabled)
        assert 'data-highlight="true"' in dialog._preview_svg
        assert 'data-selection-contour="true"' in dialog._preview_svg
        assert "Ausgewählt: Trennwand" in dialog._preview_svg
        dialog._edit_fields["height"].set_value(50)
        assert not dialog.accept_button.isEnabled()
        wait_until(qt_app, dialog.accept_button.isEnabled)
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
        wait_until(qt_app, dialog.accept_button.isEnabled)
        before = dialog._layout
        dialog._split_node("cell", "x")
        wait_until(qt_app, dialog.accept_button.isEnabled)
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
        wait_until(qt_app, dialog.accept_button.isEnabled)
        dialog.basis.setCurrentIndex(0)
        wait_until(qt_app, dialog.accept_button.isEnabled)
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
        wait_until(qt_app, dialog.accept_button.isEnabled)
        previous = dialog._layout.width
        dialog.basis.setCurrentIndex(0)
        wait_until(qt_app, dialog.accept_button.isEnabled)
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
        wait_until(qt_app, entered.is_set)
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
        wait_until(qt_app, dialog.accept_button.isEnabled)
        wall = dialog._layout.walls[0]
        dialog._graphic_chosen("wall", wall.id)
        dialog._edit_fields["height"].set_value(1)
        wait_until(qt_app, lambda: dialog._worker is None and not dialog._pending)
        dialog.accept()
        assert dialog.result() != QDialog.DialogCode.Accepted
        assert not dialog.accept_button.isEnabled()
        dialog._edit_fields["height"].set_value(30)
        wait_until(qt_app, dialog.accept_button.isEnabled)
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
        wait_until(qt_app, dialog.accept_button.isEnabled)
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
        wait_until(qt_app, dialog.accept_button.isEnabled)
        body = dialog.result_preview.mesh
        count = len(calls)
        dialog._graphic_chosen("wall", dialog._layout.walls[0].id)
        wait_until(qt_app, dialog.accept_button.isEnabled)
        assert len(calls) == count
        assert dialog.result_preview.mesh is body
        dialog._graphic_chosen("cell", dialog._layout.cells[0].id)
        wait_until(qt_app, dialog.accept_button.isEnabled)
        assert len(calls) == count
        assert 'data-highlight="true"' in dialog._preview_svg
    finally:
        dispose(dialog, qt_app)


def test_one_compartment_is_named_in_the_singular(qt_app):
    """„Fachvorlage für 1 Fächer" stand da, sobald eine Vorlage ein Fach trug."""
    from app.ui.organizer_dialog import _template_line

    assert "ein Fach" in _template_line(1)
    assert "1 Fächer" not in _template_line(1)
    assert "3 Fächer" in _template_line(3)


def test_the_resting_accept_button_says_why(qt_app):
    """*Organizer anlegen* ruhte während der Vorschau ohne Grund an allen drei
    Kanälen; die Zeile darunter sagte es, der Knopf nicht (Regel 18)."""
    dialog = OrganizerDialog({})
    try:
        assert not dialog.accept_button.isEnabled()
        said = (
            dialog.accept_button.toolTip(),
            dialog.accept_button.statusTip(),
            dialog.accept_button.accessibleDescription(),
        )
        assert all(text.strip() for text in said), said
        wait_until(qt_app, dialog.accept_button.isEnabled)
        assert not dialog.accept_button.toolTip(), "frei trägt er keinen Sperrgrund"
    finally:
        dispose(dialog, qt_app)


def test_the_name_and_the_basis_carry_their_labels(qt_app):
    """Das Namensfeld stand ohne Beschriftung neben „Neues Raster" — sichtbar
    nur der Platzhalter „Organizer", der beim Tippen verschwindet; die
    Bezugswahl hatte gar keinen Namen."""
    from PySide6.QtWidgets import QLabel

    dialog = OrganizerDialog({})
    try:
        buddies = [
            label for label in dialog.findChildren(QLabel) if label.buddy() is dialog.name_field
        ]
        assert buddies and buddies[0].text().strip(), "das Feld trägt eine sichtbare Beschriftung"
        assert dialog.basis.accessibleName().strip()
    finally:
        dispose(dialog, qt_app)


def test_the_three_columns_share_heading_scale_and_labels_have_no_colon(qt_app):
    """Die Kopfzeilen bilden eine Reihe, und das Namensfeld bleibt schlicht benannt."""
    from PySide6.QtWidgets import QLabel

    dialog = OrganizerDialog({})
    try:
        expected = {"Aufteilung", "Draufsicht · Fach oder Wand anklicken", "So sieht Ihr Teil aus"}
        headings = [label for label in dialog.findChildren(QLabel) if label.text() in expected]
        assert {label.text() for label in headings} == expected
        assert all(label.property("level") == "section" for label in headings)
        assert dialog.tree.isHeaderHidden()
        name_labels = [
            label for label in dialog.findChildren(QLabel) if label.buddy() is dialog.name_field
        ]
        assert len(name_labels) == 1
        assert not name_labels[0].text().endswith(":")
    finally:
        dispose(dialog, qt_app)


def test_a_split_beyond_the_limit_is_said_not_thrown(qt_app):
    """Ab 1024 Fächern warf *Längs teilen* die Absage aus dem Slot."""
    spec = LayoutSpec("inner", Node("cell", "cell", width=80, depth=60, radius=0))
    dialog = OrganizerDialog({"layout": layout_to_text(spec), "wall": 4, "radius": 0})
    try:
        wait_until(qt_app, dialog.accept_button.isEnabled)
        full = dialog._nodes["cell"]
        dialog._nodes.update({f"cell_{index}": full for index in range(1, 1025)})
        dialog._split_node("cell", "x")
        assert "zu groß" in dialog.state.text(), dialog.state.text()
    finally:
        dispose(dialog, qt_app)
