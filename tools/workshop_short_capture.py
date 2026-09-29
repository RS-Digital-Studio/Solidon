"""Einzelne Bedienhandlungen für einen geführten Short in normalen Schritten aufnehmen."""

from __future__ import annotations

import math
from time import monotonic
from typing import Any


def capture_step(tutorial: Any, step: dict[str, Any], body: str) -> None:
    """Bohrung wirklich anklicken, sichtbare Tasten tippen und Übernehmen klicken."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from tools.make_workshop_videos import write_json

    window, session, recorder = tutorial.window, tutorial.session, tutorial.recorder
    viewport, renderer = window.viewport, window.viewport.renderer
    widget = renderer.widget
    stages = []
    bounds = {}
    pointer = widget.mapToGlobal(widget.rect().center())

    def position(target: Any) -> Any:
        return target if isinstance(target, QPoint) else target.mapToGlobal(target.rect().center())

    def still(seconds: float = 0.5, target: Any = None, click: bool = False) -> None:
        recorder.add("", "", seconds, target=target, click=click)

    def region(target: Any) -> list[int]:
        point = target.mapToGlobal(QPoint(0, 0)) - window.mapToGlobal(QPoint(0, 0))
        return [point.x(), point.y(), target.width(), target.height()]

    def record_range(action: Any) -> list[int]:
        first = len(recorder.slides)
        action()
        return [first, len(recorder.slides)]

    def move(target: Any, seconds: float = 0.6) -> None:
        nonlocal pointer
        endpoint = position(target)
        start = pointer
        count = max(1, round(seconds * 20))
        for index in range(1, count + 1):
            point = start + (endpoint - start) * (index / count)
            local = widget.mapFromGlobal(point)
            QTest.mouseMove(widget, local)
            renderer.render_now()
            recorder._pointer = None
            still(seconds / count, point)
        pointer = endpoint

    def click(target: Any, local: Any = None) -> None:
        point = local or target.rect().center()
        global_point = target.mapToGlobal(point)
        move(global_point)
        QTest.mousePress(target, Qt.MouseButton.LeftButton, pos=point)
        still(0.18, global_point, True)
        QTest.mouseRelease(target, Qt.MouseButton.LeftButton, pos=point)
        tutorial.settle(8)
        still(0.4, global_point)

    def segment(key: str, before: Any, action: Any, after: Any) -> None:
        stages.append(
            {
                "key": key,
                "before": record_range(before),
                "action": record_range(action),
                "after": record_range(after),
            }
        )

    if window.settings.right_panel_visible:
        window.action_toggle_right()
    if window.settings.bed_visible:
        window.action_toggle_bed()
    window.action_shading("flat")
    overview = record_range(lambda: tutorial.overview("", "", "", "", seconds=4, degrees=20))
    camera = renderer.camera_pose()
    parallel_scale = renderer.parallel_scale()
    feature = session.last_result.scene.objects[body].features[step["feature"]]
    centre = tuple(feature.params["centre"])
    depth = float(feature.params["depth"])
    hole_point = (centre[0], centre[1], centre[2] + depth / 2)
    projected = renderer.world_to_display(hole_point)
    viewport_region = region(widget)
    bounds["viewport"] = viewport_region
    bounds["opening_pixel"] = [
        projected[0] + viewport_region[0],
        projected[1] + viewport_region[1],
    ]
    close_before = record_range(
        lambda: tutorial.close_up(hole_point, 190, "", "", "", "", seconds=2)
    )
    viewport.set_camera_pose(
        camera.position, camera.focal_point, camera.view_up, parallel_scale=parallel_scale
    )
    viewport.settle_camera()
    renderer.render_now()
    tutorial.settle(12)
    segment("goal", lambda: still(1), lambda: None, lambda: still(1))

    def choose() -> None:
        # Die erste Stufe des Kundenwegs wählt den Körper, die zweite sein Merkmal.
        target = renderer.world_to_display((centre[0], centre[1], centre[2] - depth / 3))
        point = QPoint(round(target[0]), round(target[1]))
        click(widget, point)
        if body not in window.object_tree.selected_objects():
            raise RuntimeError("Der erste Klick hat den Halter nicht gewählt; Kamerapunkt prüfen.")
        # Die Mündung in der Mitte anklicken; ihr Rand ist eine eigene Kante.
        mouth = renderer.world_to_display(hole_point)
        click(widget, QPoint(round(mouth[0]), round(mouth[1])))
        if window.object_tree.selected_features() != ((body, step["feature"]),):
            raise RuntimeError("Der zweite Klick hat nicht die Bohrung gewählt; Aufnahme anhalten.")

    segment("select", lambda: still(1), choose, lambda: still(1.5))
    flow = window._quiet_placement
    if flow is None or flow.spec_of().name != "resize_hole":
        raise RuntimeError("Die native Bohrungsbearbeitung fehlt nach dem Klick.")
    group = window.feature_panel._measure_groups.get(id(flow.measure_group))
    if group is None:
        raise RuntimeError("Das Durchmesserfeld fehlt; Bedienzustand prüfen.")
    editor = group.widgets["diameter"]
    spin = getattr(editor, "spin", editor)
    line = spin.lineEdit()
    bounds["measure_box"] = region(flow._measure_box)
    bounds["diameter_field"] = region(spin)
    bounds["apply_button"] = region(flow._measure_accept)

    def enter() -> None:
        click(line)
        QTest.keyClick(line, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        still(0.6, line)
        for character in str(step["diameter"]):
            QTest.keyClicks(line, character)
            tutorial.settle(3)
            still(0.45, line)
        QTest.keyClick(line, Qt.Key.Key_Tab)
        tutorial.settle(10)
        still(0.8, spin)
        if not math.isclose(spin.value(), float(step["diameter"]), abs_tol=1e-6):
            raise RuntimeError("Der getippte Durchmesser stimmt nicht; sichtbaren Text prüfen.")

    segment("enter", lambda: still(1, spin), enter, lambda: still(1.5, spin))
    if step.get("show_settings"):
        from PySide6.QtWidgets import QCheckBox

        checkbox = group.widgets.get("compensate")
        if not isinstance(checkbox, QCheckBox) or checkbox.isChecked():
            raise RuntimeError("Die Materialtoleranz entspricht nicht dem geplanten Beispiel.")
        scrollbar = flow._measure_scroll.verticalScrollBar()

        def scroll_to(key: Any) -> None:
            click(scrollbar)
            QTest.keyClick(scrollbar, key)
            tutorial.settle(12)
            still(1.0, scrollbar)

        segment(
            "settings",
            lambda: still(1),
            lambda: scroll_to(Qt.Key.Key_End),
            lambda: still(6, checkbox),
        )
        segment(
            "settings-return",
            lambda: still(1, checkbox),
            lambda: scroll_to(Qt.Key.Key_Home),
            lambda: still(1.5, spin),
        )
    count = len(session.project.document.ops)

    def apply() -> None:
        deadline = monotonic() + 120
        while not flow._measure_accept.isEnabled():
            if monotonic() > deadline:
                raise RuntimeError("Übernehmen bleibt gesperrt; Vorschau prüfen.")
            tutorial.settle(5)
        click(flow._measure_accept)
        tutorial.checked("Echter Klick auf Übernehmen im Short")
        if len(session.project.document.ops) != count + 1:
            raise RuntimeError("Der sichtbare Klick hat keinen einzelnen Schritt erzeugt.")
        window.object_tree.tree.clearSelection()
        tutorial.settle(15)
        viewport.set_camera_pose(
            camera.position, camera.focal_point, camera.view_up, parallel_scale=parallel_scale
        )
        viewport.settle_camera()
        renderer.render_now()
        tutorial.settle(10)

    segment("apply", lambda: still(1, flow._measure_accept), apply, lambda: still(1.5))
    segment("compare", lambda: still(1), lambda: None, lambda: still(1.5))
    close_after = record_range(
        lambda: tutorial.close_up(hole_point, 190, "", "", "", "", seconds=5)
    )
    segment("finish", lambda: still(1), lambda: None, lambda: still(1.5))
    write_json(
        tutorial.folder / "interaction.json",
        {
            "schema": 1,
            "view_settings": {
                "theme": window.settings.theme,
                "shading": window.settings.shading,
                "display_mode": window.settings.display_mode,
                "bed_visible": window.settings.bed_visible,
            },
            "feature": step["feature"],
            "diameter": step["diameter"],
            "camera_before": {
                "position": camera.position,
                "focal_point": camera.focal_point,
                "view_up": camera.view_up,
                "parallel_scale": parallel_scale,
            },
            "bounds": bounds,
            "overview": overview,
            "close_before": close_before,
            "close_after": close_after,
            "stages": stages,
            "evidence": "Echte Qt-Maus- und Tastaturereignisse; keine Operation direkt angewendet.",
        },
    )
