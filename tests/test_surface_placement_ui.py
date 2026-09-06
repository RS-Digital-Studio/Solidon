"""Die Mausplatzierung reicht echte Werte bis in Operation, Datei und Undo."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication, QWidget

from app.core.registry import REGISTRY
from app.core.scene.history import OperationDraft
from app.core.scene.project import load, save
from app.ui.op_dialog import OperationDialog
from app.ui.placement_flow import PlacementFlow
from app.ui.render.api import PointerEvent
from app.ui.session import Session


class _Item:
    def __init__(self) -> None:
        self.visible = True
        self.matrix = np.eye(4)

    def set_visible(self, visible: bool) -> None:
        self.visible = visible

    def set_matrix(self, matrix: np.ndarray) -> None:
        self.matrix = matrix


class _Renderer:
    widget = None

    def add_surface(self, *_args: Any, **_kwargs: Any) -> _Item:
        return _Item()

    def remove(self, _item: Any) -> None:
        pass

    def world_to_display(self, point: Any) -> tuple[float, float, float]:
        return 320 + point[0] * 10, 240 - point[1] * 10, 0.5


class _Viewport(QWidget):
    cameraMoved = Signal()  # noqa: N815 — Qt-Schnittstelle
    sceneApplied = Signal()  # noqa: N815 — Qt-Schnittstelle

    def __init__(self) -> None:
        super().__init__()
        self.renderer = _Renderer()
        self._object_colour = "#aaaaaa"
        self.hit: Any = None
        self.result: Any = None
        self.pointer: Any = None
        self.resize(900, 600)

    def set_placement_pointer(self, handler: Any) -> None:
        self.pointer = handler

    def placement_hit(self, _x: int, _y: int) -> Any:
        return self.hit

    def is_scene_applied(self, result: Any) -> bool:
        return result is not None and self.result is result

    def show_scene(self, result: Any) -> None:
        self.result = result
        self.sceneApplied.emit()

    def _section_planes(self) -> tuple[None, None]:
        return None, None

    def view_point_of(self, point: Any, _object_id: str) -> Any:
        return point

    def _device_ratio(self) -> float:
        return 1.0

    def _draw(self) -> None:
        pass


@pytest.fixture
def flow(qt_app: QApplication) -> Any:
    session = Session()
    viewport = _Viewport()
    dialog: OperationDialog | None = None
    controller: PlacementFlow | None = None
    try:
        session.import_model(Path(__file__).parent / "data/meshes/cube_clean.stl")
        assert session.wait_for_idle(30_000)
        result = session.last_result
        assert result is not None and result.complete
        viewport.show_scene(result)
        session.sceneChanged.connect(viewport.show_scene)
        object_id, entry = next(iter(result.scene.objects.items()))
        face = int(np.argmax(entry.mesh.raw.face_normals[:, 2]))
        point = tuple(entry.mesh.raw.triangles_center[face])
        viewport.hit = object_id, point, face, None
        spec = REGISTRY.get("drill_hole")
        dialog = OperationDialog(spec, {object_id: "Würfel"})
        window = SimpleNamespace(
            viewport=viewport, session=session, _clear_preview=session.cancel_preview
        )
        controller = PlacementFlow(dialog, window, lambda: spec, lambda: (object_id,))
        dialog.accepted.connect(
            lambda: session.apply(
                spec.title,
                [OperationDraft(op=spec.name, inputs=(object_id,), params=dialog.values())],
            )
        )
        yield controller, session, viewport, dialog
    finally:
        if controller is not None:
            controller.dispose()
        session.release(30_000)
        if dialog is not None:
            dialog.close()
        viewport.close()
        qt_app.processEvents()


def _point(controller: PlacementFlow, session: Session, *, confirm: bool = False) -> None:
    event = (
        PointerEvent("release", 320, 240, button="left")
        if confirm
        else PointerEvent("move", 320, 240)
    )
    assert controller.pointer(event)
    controller._timer.stop()
    controller._next_surface()
    assert session.wait_for_idle(30_000)


def test_the_placement_worker_returns_in_the_qt_thread(qt_app: QApplication) -> None:
    session = Session()
    threads: list[Any] = []
    failures: list[str] = []
    try:
        session.placement_async(
            lambda: QThread.currentThread(),
            lambda worker_thread: threads.extend((worker_thread, QThread.currentThread())),
            failures.append,
        )
        assert session.wait_for_idle(30_000)
        assert not failures
        assert len(threads) == 2
        assert threads[0] != qt_app.thread()
        assert threads[1] == qt_app.thread()
    finally:
        session.release()


def test_click_places_one_real_hole_and_undo_removes_it(flow: Any, tmp_path: Path) -> None:
    controller, session, _viewport, dialog = flow
    before = len(session.project.document.transactions)
    controller.start()
    assert session.wait_for_idle(30_000)
    _point(controller, session, confirm=True)
    assert not controller.active
    assert len(session.project.document.transactions) == before + 1
    assert session.last_result.complete
    operation = session.project.document.ops[-1]
    assert operation.op == "drill_hole"
    assert operation.params["nz"] == pytest.approx(1.0)
    assert operation.params["x"] == pytest.approx(dialog.values()["x"])
    path = tmp_path / "placed.p3d"
    save(session.project, path)
    assert load(path).document.ops[-1].params == operation.params
    session.undo()
    assert session.wait_for_idle(30_000)
    assert len(session.project.document.transactions) == before


def test_return_to_values_preserves_position_without_an_operation(flow: Any) -> None:
    controller, session, _viewport, dialog = flow
    before = len(session.project.document.ops)
    controller.start()
    _point(controller, session)
    values = dialog.values()
    controller.back()
    assert not controller.active
    assert dialog.isVisible()
    assert dialog.values() == values
    assert len(session.project.document.ops) == before


def test_escape_forgets_the_target_body(flow: Any) -> None:
    """Nach Escape bohrt der Dialog wieder, was der Nutzer gewählt hat — nicht den
    einen Körper, den die Platzierung getroffen hatte (Review 06.09.2026)."""
    controller, session, _viewport, _dialog = flow
    controller.start()
    assert session.wait_for_idle(30_000)
    _point(controller, session)
    assert controller.target, "der Treffer hat ein Ziel"
    controller.back()
    assert controller.target == "", "Escape gibt das Ziel frei; nur Übernehmen behält es"


def test_invalid_surface_cannot_reuse_the_previous_position(flow: Any) -> None:
    controller, session, viewport, _dialog = flow
    before = len(session.project.document.ops)
    controller.start()
    _point(controller, session)
    assert controller._surface is not None
    viewport.hit = None
    _point(controller, session, confirm=True)
    assert controller._surface is None
    assert not controller._accept.isEnabled()
    assert len(session.project.document.ops) == before


def test_editing_an_edge_distance_keeps_it_exact_until_accept(flow: Any) -> None:
    controller, session, _viewport, dialog = flow
    controller.start()
    _point(controller, session)
    assert len(controller._surface.edges) == 2
    before = len(session.project.document.ops)
    controller._measures[0].set_value_mm(2.3456789)
    controller._distance_changed(2.3456789)
    assert controller._distance_valid
    assert controller._surface.edges[0].distance == pytest.approx(2.3456789)
    assert len(session.project.document.ops) == before
    assert controller._frozen
    assert {name: dialog.values()[name] for name in ("x", "y", "z")} == dict(
        zip(("x", "y", "z"), controller._surface.point, strict=True)
    )


def test_surface_position_replaces_an_old_coordinate_expression(flow: Any) -> None:
    controller, session, _viewport, dialog = flow
    field = dialog._editors["x"]
    field.set_value("=5 + 2")
    assert isinstance(dialog.values()["x"], str)
    controller.start()
    _point(controller, session)
    assert not field.toggle.isChecked()
    assert dialog.values()["x"] == pytest.approx(controller._surface.point[0])


def test_undo_cannot_restart_placement_on_the_previous_result(flow: Any) -> None:
    controller, session, _viewport, dialog = flow
    controller.start()
    _point(controller, session)
    old = session.last_result
    session.undo()
    assert not controller.active
    assert session.last_result is old
    assert not session.result_current
    controller.start()
    assert not controller.active
    assert not dialog.surface_button.isEnabled()
    assert session.wait_for_idle(30_000)
    assert not dialog.surface_button.isEnabled()


def test_edit_uses_the_input_before_later_transforms(flow: Any) -> None:
    controller, session, viewport, _dialog = flow
    object_id = controller.inputs_of()[0]
    assert session.apply(
        "Bohrung", [OperationDraft(op="drill_hole", inputs=(object_id,), params={})]
    )
    assert session.wait_for_idle(30_000)
    drill = session.project.document.ops[-1]
    assert session.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=(object_id,), params={"dx": 50.0})],
    )
    assert session.wait_for_idle(30_000)
    final = session.last_result
    controller._change_op = drill.id
    controller.start()
    assert session.wait_for_idle(30_000)
    assert controller._result is not final
    original = controller._result.scene.objects[object_id].mesh.raw
    moved = final.scene.objects[object_id].mesh.raw
    assert float(moved.bounds[0, 0] - original.bounds[0, 0]) == pytest.approx(50.0)
    assert viewport.result is controller._result
    _point(controller, session)
    assert controller._surface.point[0] < 20.0
    controller.back()
    assert viewport.result is final


def test_an_invalid_historical_step_can_be_placed_again(flow: Any) -> None:
    """Die fertige Auswertung darf fehlerhaft sein, ihr gesunder Eingang bleibt bearbeitbar."""
    controller, session, viewport, dialog = flow
    object_id = controller.inputs_of()[0]
    assert session.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(object_id,),
                params={"diameter": 4.0, "widening_diameter": 1.0},
            )
        ],
    )
    assert session.wait_for_idle(30_000)
    assert not session.last_result.complete
    controller._change_op = session.project.document.ops[-1].id
    controller.start()
    assert session.wait_for_idle(30_000)
    assert controller.active and dialog.surface_button.isEnabled()
    assert controller._result.complete
    assert viewport.result is controller._result
    _point(controller, session)
    assert controller._surface is not None
    assert controller._accept.isEnabled()


def test_feature_hover_reuses_the_body_prepared_outside_qt(
    flow: Any,
    qt_app: QApplication,
    monkeypatch: Any,
) -> None:
    """Mausbewegungen und Maße dürfen den Merkmalskörper nicht erneut im Qt-Thread berechnen."""
    import app.core.geom.prepare_ops as module

    original, session, viewport, _dialog = flow
    original.dispose()
    object_id = original.inputs_of()[0]
    assert session.apply(
        "Bohrung", [OperationDraft(op="drill_hole", inputs=(object_id,), params={})]
    )
    assert session.wait_for_idle(30_000)
    entry = session.last_result.scene.objects[object_id]
    feature = next(value for value in entry.features.values() if value.kind == "hole")
    face = int(np.argmax(entry.mesh.raw.face_normals[:, 2]))
    viewport.hit = object_id, tuple(entry.mesh.raw.triangles_center[face]), face, None
    spec = REGISTRY.get("move_feature")
    dialog = OperationDialog(spec, {object_id: "Würfel"}, features={feature.id: "Bohrung"})
    dialog.take_placement({"at_feature": feature.id})
    window = SimpleNamespace(
        viewport=viewport, session=session, _clear_preview=session.cancel_preview
    )
    controller = PlacementFlow(dialog, window, lambda: spec, lambda: (object_id,))
    threads = []
    actual = module.feature_placement_geometry

    def measured(*args: Any, **kwargs: Any) -> Any:
        thread = QThread.currentThread()
        assert thread != qt_app.thread(), "feature geometry reached the Qt thread"
        threads.append(thread)
        return actual(*args, **kwargs)

    monkeypatch.setattr(module, "feature_placement_geometry", measured)
    try:
        controller.start()
        assert session.wait_for_idle(30_000)
        for _ in range(3):
            _point(controller, session)
            assert controller._surface is not None
            assert controller._tool_context is not None
            assert controller._set_values()
        assert len(threads) == 1
    finally:
        controller.dispose()
        assert session.wait_for_idle(30_000)
        dialog.close()


def test_late_tool_from_a_closed_run_is_discarded(flow: Any, monkeypatch: Any) -> None:
    controller, session, _viewport, _dialog = flow
    requests = []
    monkeypatch.setattr(
        session, "placement_async", lambda compute, then, failed: requests.append((compute, then))
    )
    controller.start()
    compute, then = requests.pop()
    controller.back()
    controller.start()
    then(compute())
    assert controller._tool is None
    assert len(requests) == 1
    current_compute, current_then = requests.pop()
    current_then(current_compute())
    assert controller._tool is not None


def test_centre_dimensions_keep_the_selected_hole_reference(flow: Any) -> None:
    controller, session, viewport, dialog = flow
    session.start_new()
    assert session.wait_for_idle(30_000)
    session.import_model(Path(__file__).parent / "data/meshes/plate_holes.stl")
    assert session.wait_for_idle(30_000)
    object_id, entry = next(iter(session.last_result.scene.objects.items()))
    face = int(np.argmax(entry.mesh.raw.face_normals[:, 2]))
    point = tuple(entry.mesh.raw.triangles_center[face])
    viewport.hit = object_id, point, face, None
    controller.start()
    _point(controller, session)
    assert controller._centre_id
    old_id = controller._centre_id
    current = next(c for c in controller._surface.centres if c.feature_id == old_id)
    changed = current.offset[0] + 0.123456789
    controller._centre_measures[0].set_value_mm(changed)
    controller._centre_changed(changed)
    assert controller._distance_valid
    assert controller._centre_id == old_id
    updated = next(c for c in controller._surface.centres if c.feature_id == old_id)
    assert updated.offset[0] == pytest.approx(changed)
    assert controller._frozen
    assert dialog.values()["x"] == pytest.approx(controller._surface.point[0])


def _keyboard_placement(flow: Any, qt_app: QApplication) -> Any:
    """Echte Qt-Felder an der Lochplatte öffnen; nur die Raumprojektion ist kontrolliert."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    controller, session, viewport, dialog = flow
    session.start_new()
    assert session.wait_for_idle(10_000)
    session.import_model(Path(__file__).parent / "data/meshes/plate_holes.stl")
    assert session.wait_for_idle(10_000)
    object_id, entry = next(iter(session.last_result.scene.objects.items()))
    face = int(np.argmax(entry.mesh.raw.face_normals[:, 2]))
    viewport.hit = object_id, tuple(entry.mesh.raw.triangles_center[face]), face, None
    viewport.show()
    dialog.show()
    qt_app.processEvents()
    QTest.mouseClick(dialog.surface_button, Qt.MouseButton.LeftButton)
    _point(controller, session)
    viewport.activateWindow()
    qt_app.processEvents()
    assert controller.active and controller._accept.isEnabled()
    assert controller._centre_id
    fields = (*controller._measures, *controller._centre_measures)
    assert all(field.isVisible() for field in fields)
    return fields


@pytest.mark.parametrize("position", range(4), ids=("edge-1", "edge-2", "centre-1", "centre-2"))
def test_escape_from_each_inner_dimension_editor_returns_to_values(
    flow: Any, qt_app: QApplication, position: int
) -> None:
    """Esc aus dem QLineEdit beider Maßgruppen erhält Werte und erzeugt keine Operation."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    fields = _keyboard_placement(flow, qt_app)
    controller, session, viewport, dialog = flow
    before = len(session.project.document.ops)
    values = dialog.values()
    field = fields[position]
    editor = field.lineEdit()
    assert editor is not None
    editor.setFocus(Qt.FocusReason.OtherFocusReason)
    qt_app.processEvents()
    assert field.hasFocus(), "das innere Eingabefeld muss vor Esc tatsächlich fokussiert sein"

    QTest.keyClick(editor, Qt.Key.Key_Escape)
    qt_app.processEvents()

    assert not controller.active
    assert dialog.isVisible()
    assert not controller._bar.isVisible()
    assert not any(field.isVisible() for field in fields)
    assert viewport.pointer is None
    assert dialog.values() == values
    assert len(session.project.document.ops) == before


def test_tab_reaches_both_dimension_groups_and_returns_to_editable_values(
    flow: Any, qt_app: QApplication
) -> None:
    """Tab erreicht alle Maße; Rückkehr und weitere Wertebearbeitung funktionieren per Taste."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    fields = _keyboard_placement(flow, qt_app)
    controller, session, _viewport, dialog = flow
    before = len(session.project.document.ops)
    placed = {name: dialog.values()[name] for name in ("x", "y", "z")}
    controller._back.setFocus(Qt.FocusReason.OtherFocusReason)
    qt_app.processEvents()
    assert controller._back.hasFocus()
    seen = []
    for _ in range(6):
        focused = qt_app.focusWidget()
        assert focused is not None
        QTest.keyClick(focused, Qt.Key.Key_Tab)
        qt_app.processEvents()
        current = next(
            (
                widget
                for widget in (controller._back, controller._accept, *fields)
                if widget.hasFocus()
            ),
            None,
        )
        assert current is not None, "Tab verlor den Fokus außerhalb der Platzierungsbedienung"
        seen.append(current)
    assert seen == [controller._accept, *fields, controller._back]
    assert controller._frozen, "beim Bearbeiten darf die Maus den Bezug nicht mehr wechseln"

    QTest.keyClick(controller._back, Qt.Key.Key_Space)
    qt_app.processEvents()
    assert not controller.active and dialog.isVisible()
    assert {name: dialog.values()[name] for name in placed} == placed

    diameter = dialog._editors["diameter"].spin
    editor = diameter.lineEdit()
    assert editor is not None
    editor.setFocus(Qt.FocusReason.OtherFocusReason)
    QTest.keyClick(editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(editor, "5.5")
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    qt_app.processEvents()
    assert dialog.values()["diameter"] == pytest.approx(5.5)
    assert {name: dialog.values()[name] for name in placed} == placed
    assert len(session.project.document.ops) == before

    QTest.mouseClick(dialog.surface_button, Qt.MouseButton.LeftButton)
    _point(controller, session)
    assert controller.active and controller._accept.isEnabled()
    assert dialog.values()["diameter"] == pytest.approx(5.5)
    assert len(session.project.document.ops) == before
