"""Der Kundenweg verbindet Originaltreffer, lokale Auswahl, Vorschau und ein Undo."""

from __future__ import annotations

import copy
import importlib
import threading

import numpy as np
import pytest
from PySide6.QtWidgets import QMenu

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from app.ui.main_window import MainWindow
from app.ui.render.api import PointerEvent
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.test_local_detection import blind_cylinder, bore_seed
from tests.test_local_recognition_ui import choose_action
from tests.test_outline_dialog import _until


@pytest.fixture
def local_window(qt_app, monkeypatch, tmp_path):
    load_operations()
    evaluation = importlib.import_module("app.core.scene.evaluate")
    monkeypatch.setattr(evaluation, "FEATURE_LIMIT_TRIANGLES", 1)
    path = tmp_path / "blind.stl"
    path.write_bytes(blind_cylinder().raw.export(file_type="stl"))
    window = MainWindow(Session(), UiSettings())
    window.open_path(path)
    assert window.session.wait_for_idle(30000)
    assert window.session.last_result.complete
    entry = next(iter(window.session.last_result.scene.objects.values()))
    assert not entry.features
    return window


def surface_hit(window):
    entry = next(iter(window.session.last_result.scene.objects.values()))
    _seed, point, normal = bore_seed(entry.mesh)
    origin = tuple(np.asarray(point) + np.asarray(normal) * 0.5)
    direction = tuple(-np.asarray(normal))
    # Ein LOD-Treffer hat keine Originaldreieckskennung.
    return entry.id, point, -1, (origin, direction)


def start(window, app):
    flow = window.local_features()
    flow.begin(surface_hit(window))
    dialog = flow.dialog
    assert dialog is not None
    _until(app, dialog.save_button.isEnabled)
    return flow, dialog


def test_local_edit_has_one_transaction_and_restores_original_on_undo(local_window, qt_app):
    window, session = local_window, local_window.session
    before, document = session.last_result, copy.deepcopy(session.project.document)
    flow, dialog = start(window, qt_app)
    assert session.last_result is before
    assert session.project.document == document
    assert window.object_tree.tree.topLevelItem(0).childCount() == 0
    assert dialog.inspection.selected
    assert window.viewport.banner.legend.isHidden()
    assert not window.viewport._comparing
    choose_action(dialog, "resize_hole")
    dialog.editor._editors["diameter"].set_value(8)
    _until(qt_app, lambda: dialog._preview_valid)
    assert not window.viewport.banner.legend.isHidden()
    assert window.viewport._comparing
    assert session.last_result is before
    assert session.project.document == document
    dialog.editor.accept()
    assert flow.dialog is None
    assert session.wait_for_idle(30000)
    after = session.last_result
    assert after.complete
    assert [op.op for op in session.project.document.ops[-2:]] == ["detect_region", "resize_hole"]
    assert len(session.project.document.transactions) == len(document.transactions) + 1
    assert len(session.project.document.transactions[-1].ops) == 2
    bore = next(
        feature
        for feature in after.scene.objects["obj_1"].features.values()
        if feature.kind == "hole"
    )
    assert bore.params["diameter"] == pytest.approx(8, abs=1e-4)
    session.undo()
    assert session.wait_for_idle(30000)
    assert len(session.project.document.ops) == len(document.ops)
    assert session.last_result.scene.objects["obj_1"].mesh.volume == pytest.approx(
        before.scene.objects["obj_1"].mesh.volume
    )
    session.redo()
    assert session.wait_for_idle(30000)
    assert session.last_result.scene.objects["obj_1"].mesh.volume == pytest.approx(
        after.scene.objects["obj_1"].mesh.volume
    )


def test_cancel_restores_committed_view_and_selection(local_window, qt_app, monkeypatch):
    window = local_window
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    before = window.session.last_result
    shown = []
    original = window.viewport.show_scene

    def show(result):
        shown.append(result)
        original(result)

    monkeypatch.setattr(window.viewport, "show_scene", show)
    flow, dialog = start(window, qt_app)
    assert shown[-1] is dialog.inspection.evaluation
    dialog.reject()
    assert not flow.active
    assert shown[-1] is before
    assert window.object_tree.selected() == "obj_1"
    assert len(window.session.project.document.ops) == 1


def test_source_snapshot_does_not_read_later_embedded_payload(local_window, qt_app, monkeypatch):
    import app.ui.local_recognition_flow as module

    captured = []
    original = module.LocalRecognitionDialog

    def make(*args, **kwargs):
        captured.append(kwargs["sources"])
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "LocalRecognitionDialog", make)
    flow, _dialog = start(local_window, qt_app)
    sources = captured[0]
    project = local_window.session.project
    source_id = next(iter(project.sources))
    previous = project.sources[source_id]
    project.sources[source_id] = b"a later document payload"
    assert sources.read(source_id) == previous
    assert sources.project.document is not project.document
    local_window.session.projectChanged.emit()
    assert not flow.active
    assert len(project.document.ops) == 1


def test_palette_click_and_escape_share_the_local_flow(local_window, qt_app, monkeypatch):
    window = local_window
    window.object_tree.tree.clearSelection()
    window._update_actions()
    assert window._palette_availability("detect_region") == (True, "")
    window.launch_operation(REGISTRY.get("detect_region"))
    flow = window.local_features()
    assert flow.armed
    monkeypatch.setattr(window.viewport, "placement_hit", lambda x, y: surface_hit(window))
    assert flow.pointer(PointerEvent(kind="release", x=5, y=7, button="left"))
    assert flow.dialog is not None
    _until(qt_app, flow.dialog.save_button.isEnabled)
    window._escape()
    assert not flow.active
    assert len(window.session.project.document.ops) == 1


def test_failed_preview_stays_visible_and_cannot_be_accepted(local_window, qt_app, monkeypatch):
    flow, dialog = start(local_window, qt_app)

    def crash(*args, **kwargs):
        raise RuntimeError("injected preview failure")

    monkeypatch.setattr(local_window.session, "_preview_outcome", crash)
    choose_action(dialog, "resize_hole")
    _until(qt_app, lambda: "Ändern Sie die Werte" in dialog.edit_notice.text())
    assert not dialog._preview_valid
    dialog.editor.accept()
    assert flow.dialog is dialog
    assert len(local_window.session.project.document.ops) == 1
    dialog.reject()


def test_local_search_requires_a_visible_mesh_on_the_current_plate(local_window):
    window = local_window
    window.viewport.set_hidden(frozenset({"obj_1"}))
    window._update_actions()
    assert not window._palette_availability("detect_region")[0]
    window.viewport.set_hidden(frozenset())
    window.viewport.set_plate(1)
    window._update_actions()
    assert not window._palette_availability("detect_region")[0]
    window.viewport.set_plate(-1)
    window._update_actions()
    assert window._palette_availability("detect_region") == (True, "")


def test_context_action_uses_the_clicked_original_instead_of_old_selection(
    local_window, qt_app, monkeypatch
):
    window = local_window
    hit = surface_hit(window)
    clicks = []
    monkeypatch.setattr(window.viewport, "placement_hit", lambda x, y: hit)

    def choose(menu, _point):
        matches = [
            action
            for action in menu.actions()
            if action.text() == str(REGISTRY.get("detect_region").title)
        ]
        assert len(matches) == 1
        clicks.append(matches[0].text())
        matches[0].trigger()

    menu = QMenu(window)
    monkeypatch.setattr(menu, "exec", lambda point: choose(menu, point))
    monkeypatch.setattr(window.object_tree, "context_menu", lambda: menu)
    window._on_viewport_context_menu(20, 30)
    flow = window.local_features()
    assert len(clicks) == 1 and flow.dialog is not None
    _until(qt_app, flow.dialog.save_button.isEnabled)
    assert flow.dialog.inspection.object_id == hit[0]
    window.run_operation(REGISTRY.get("scale_object"), on_bodies=(hit[0],))
    assert not flow.active
    assert window._op_dialog is not None
    window._op_dialog.reject()
    assert len(window.session.project.document.ops) == 1


def test_old_worker_crash_cannot_override_new_preview_status(qt_app, monkeypatch):
    session = Session()
    entered, release = threading.Event(), threading.Event()
    errors, results = [], []
    count = 0

    def compute(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 1:
            entered.set()
            assert release.wait(10)
            raise RuntimeError("obsolete preview")
        return None, None, ""

    monkeypatch.setattr(session, "_preview_outcome", compute)
    try:
        session.preview_async(results.append, failed=errors.append)
        _until(qt_app, entered.is_set)
        session.preview_async(results.append, failed=errors.append)
        _until(qt_app, lambda: results == [None])
        release.set()
        _until(qt_app, lambda: not session._previews)
        assert errors == []
    finally:
        release.set()
        session.cancel_preview()
        session.wait_for_idle(30000)
