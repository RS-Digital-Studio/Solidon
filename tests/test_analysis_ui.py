"""Analysekarten, Merkmals-Überlagerung und Schichtanalyse in der
Oberfläche (§18.4, §18.5, §18.10).

Wieder offscreen: geprüft werden die Verdrahtung und die Legende, nicht das
Bild. Ob die Farben auf dem richtigen Dreieck landen, entscheidet der Kern, und
``tests/test_maps.py`` prüft es dort.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt, QThread
from PySide6.QtWidgets import QApplication

from app.core.perceive import maps
from app.core.types import Action, Finding
from app.i18n import TranslatableText, format_decimal, tr
from app.ui.analysis_bar import MAP_ORDER, AnalysisBar, LayerBar, MapLegend
from app.ui.labels import feature_label, length
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.render_fakes import RecordingItem, RecordingRenderer

MESHES = Path(__file__).parent / "data" / "meshes"


def _activate_report_navigation(state: Any, route: str, object_id: str) -> None:
    """Die vier Auswahlwege aus Befundzeile und angebotener Handlung."""
    from app.core.errors import AppError

    finding = Finding("perceive.deviation", "info", "Formabweichung", object_id=object_id, op_id=1)
    if route == "finding":
        MainWindow._on_finding_activated(state, finding)
    elif route == "bundle":
        MainWindow._on_bundle_activated(state, finding, (object_id,))
    elif route == "locations":
        MainWindow._show_error_location(state, AppError(object_id=object_id))
    else:
        assert route == "support"
        MainWindow._show_support_need(state, AppError(object_id=object_id))


@pytest.mark.parametrize("route", ["finding", "bundle", "locations", "support"])
@pytest.mark.parametrize("phase", ["absent", "passive", "editing", "committing"])
def test_report_navigation_preserves_a_started_draft_before_any_side_effect(
    route: str,
    phase: str,
) -> None:
    """Alle Berichtsauswahlen beachten denselben Besitz wie Baum und Viewport."""
    from app.ui.placement_flow import QuietHost

    host = None if phase == "absent" else QuietHost({"diameter": 7.0}, lambda values: False)
    if host is not None and phase in {"editing", "committing"}:
        host.begin_edit()
        host.committing = phase == "committing"
    events: list[Any] = []
    selection = ["obj_1"]
    awaiting = object()

    def select(objects: list[str]) -> None:
        selection[:] = objects
        events.append(("selection", tuple(objects)))

    state = SimpleNamespace(
        _quiet_host=host,
        _finding_awaiting_map=awaiting,
        _quiet_selection_allowed=lambda: MainWindow._quiet_selection_allowed(state),
        _quiet_command_allowed=lambda: MainWindow._quiet_command_allowed(state),
        _say_the_change_comes_first=lambda: events.append("refused"),
        _object_of=lambda error: MainWindow._object_of(state, error),
        viewport=SimpleNamespace(clear_finding_mark=lambda: events.append("clear_mark")),
        history_panel=SimpleNamespace(
            point_at=lambda op_id: events.append(("history", op_id)) or False
        ),
        session=SimpleNamespace(
            last_result=SimpleNamespace(
                scene=SimpleNamespace(objects={"obj_2": SimpleNamespace(id="obj_2")})
            )
        ),
        object_tree=SimpleNamespace(
            selected=lambda: selection[0],
            select_object=lambda body: select([body]),
            select_objects=select,
        ),
        tools=SimpleNamespace(activate=lambda tool: events.append(("tool", tool))),
        analysis_bar=SimpleNamespace(show_map=lambda kind: events.append(("map", kind))),
        _analysis_map=lambda kind, body, **kwargs: events.append(("analysis", kind, body)),
    )

    _activate_report_navigation(state, route, "obj_2")

    if phase == "editing":
        assert selection == ["obj_1"]
        assert state._finding_awaiting_map is awaiting
        assert events == ["refused"], "auch Karte, Ortsmarke und Verlauf bleiben unverändert"
    else:
        assert selection == ["obj_2"]
        assert "refused" not in events
        if route != "bundle":
            assert ("tool", "analysis") in events
    assert state._quiet_host is host
    if host is not None:
        assert host.values() == {"diameter": 7.0}


@pytest.mark.parametrize("route", ["finding", "bundle", "locations", "support"])
def test_report_navigation_keeps_the_selected_feature_and_its_measure_group(
    window: MainWindow,
    route: str,
) -> None:
    """Ein Berichtsklick beendet auch am echten Fenster keinen begonnenen Bohrungsentwurf.

    Die Maße im Bild brauchen einen Renderer (``MainWindow._measure_in_the_view``
    steigt ohne aus), und offscreen gibt es keinen — ohne die Attrappe stand
    nach dem Klick keine Maßgruppe, und der Test war seit seiner Entstehung rot.
    """
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.object_tree.select_object("obj_1")
    window.object_tree.select_feature("obj_1", "hole_1")
    if window._quiet_placement is None:
        window.feature_panel._in_view.click()
    assert window.session.wait_for_idle(30_000)
    for _ in range(40):
        QApplication.processEvents()
    host, flow = window._quiet_host, window._quiet_placement
    assert host is not None and flow is not None
    host.begin_edit()
    host.take_placement({"diameter": float(host.values()["diameter"]) + 0.5})
    values = host.values()
    panel = window.feature_panel.preview_values()
    approval = window._preview_approval
    shown_map = window.analysis_bar.chosen()

    _activate_report_navigation(window, route, "obj_1")

    assert window._quiet_host is host and window._quiet_placement is flow
    assert host.begun and flow.active and host.values() == values
    assert window.object_tree.selected_feature() == "hole_1"
    assert window.feature_panel.preview_values() == panel
    assert window._preview_approval is approval
    assert window.analysis_bar.chosen() == shown_map


@pytest.fixture
def deviation_host(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[MainWindow, list[Any]]]:
    """Zwei echte Körper und aufgehaltene Kartenarbeiter für die Release-Fensterfälle."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Scene, SceneObject

    host = MainWindow(Session(), UiSettings())
    bodies = {
        name: SceneObject(id=name, name=name, mesh=MeshData.of(trimesh.creation.box()))
        for name in ("obj_1", "obj_2")
    }
    result = EvaluationResult(Scene(objects=bodies))
    host.session.last_result = result
    host.session.result_current = True
    if host.viewport.renderer is None:
        host.viewport.renderer = RecordingRenderer()
    host.viewport.show_scene(result)
    host.object_tree.show_scene(result)
    host.object_tree.select_object("obj_1")
    # Die Druckgrundlage steht, wie nach dem ersten Lauf: Ihr Arbeiter startet
    # mit der Auswertung, nicht mit dem Klick auf einen Befund, und gezählt
    # werden hier die Arbeiter der Karte. Die Auswertung ist oben ersetzt.
    from app.core.export import manufacturer
    from app.core.knowledge import print_settings

    quality = print_settings.DEFAULT_QUALITY
    host.settings.print_quality = quality
    host._foundation_cache = (
        host._foundation_key(quality),
        manufacturer.base_settings(host.session.profile, quality, None),
    )
    workers: list[Any] = []
    monkeypatch.setattr(host._leash, "start", workers.append)
    try:
        yield host, workers
    finally:
        from shiboken6 import isValid

        if isValid(host):
            host.release()
            host.viewport.release_renderer()
        for worker in workers:
            worker.release_finished_references()
            worker.deleteLater()
        if isValid(host):
            host.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _deviation_result(*, known: int = 12) -> maps.AnalysisMap:
    """Gleiche Schranken gegenüberliegender Flächen, aber genau ein wirklicher Zeuge."""
    return maps.AnalysisMap(
        kind="deviation",
        title="Formabweichung",
        unit="mm",
        low=0.0,
        high=2e-7,
        values=(2e-7,) * known + (float("nan"),) * (12 - known),
        highlighted=(0, 10) if known else (),
        maximum_interval=(1e-7, 2e-7) if known else None,
        numerical_error=1e-7 if known else None,
        witness_point=(-0.5, 0.0, 0.0) if known else None,
        witness_face=0 if known else None,
        witness_distance=1e-7 if known else None,
        unknown_note="Keine Form sicher zugeordnet",
    )


@pytest.mark.parametrize("known", [0, 6, 12])
def test_deviation_legend_distinguishes_unknown_coverage_and_numerical_bounds(
    qt_app: QApplication, known: int
) -> None:
    legend = MapLegend()
    analysis = _deviation_result(known=known)
    try:
        legend.show_map(analysis)
        assert f"{known} von 12" in legend.note.text()
        assert bool(legend.entries) is bool(known)
        assert ("Größter Abstand" in legend.note.text()) is bool(known)
        if known:
            # Die Zeile ist die Auskunft, das Feine steht im Tooltip (Review
            # Fenster #13): Obergrenzen und die berechnete Spanne findet, wer
            # sie sucht — die Zeile nennt den Abstand und die Abdeckung.
            assert "Obergrenzen je Dreiecksfläche" not in legend.note.text()
            assert "Obergrenzen je Dreiecksfläche" in legend.note.toolTip()
            # Kleine Abstände bleiben von null verschieden — und stehen als
            # Dezimalzahl, nicht als Zehnerpotenz: Ein Kunde liest Millimeter.
            assert "0,000000099 mm bis 0,00000020 mm" in legend.note.text()
            assert "e-" not in legend.note.text()
            assert "je Dreiecksfläche: höchstens" not in legend.note.text()
            assert "je Dreiecksfläche: höchstens" in legend.note.toolTip()
            assert "keine Fertigungstoleranz" in legend.note.toolTip()
            assert "Raster" not in legend.note.text()
        else:
            assert "Keine Abweichungswerte" in legend.note.text()
            assert " mm" not in legend.note.text()
        assert legend.note.accessibleDescription() == legend.note.toolTip()
        assert legend.note.statusTip() == legend.note.toolTip()
    finally:
        legend.deleteLater()


@pytest.mark.parametrize("unit", ["mm", "in"])
@pytest.mark.parametrize("known", [0, 12])
def test_deviation_report_click_waits_for_its_real_witness_and_reuses_the_cache(
    deviation_host: tuple[MainWindow, list[Any]], unit: str, known: int
) -> None:
    host, workers = deviation_host
    host.set_display_unit(unit)
    finding = Finding("perceive.deviation", "info", "Formabweichung", object_id="obj_1")
    host._on_finding_activated(finding)
    assert len(workers) == 1
    assert host.analysis_bar.chosen() == "deviation"
    assert host.viewport._finding_mark is None
    analysis = _deviation_result(known=known)
    workers[0].done.emit(analysis)
    assert host.viewport.analysis_map is analysis
    assert host._finding_awaiting_map is None
    if known:
        point, text, body = host.viewport._finding_mark
        assert point == (-0.5, 0.0, 0.0), "kein Mittel gegenüberliegender Maximalflächen"
        assert body == "obj_1" and "Größter gefundener Abstand" in text
        assert unit in text
        assert "2,0e-7" not in text, "die Ortsmarke übernimmt keine obere Facettenschranke"
    else:
        assert host.viewport._finding_mark is None
    host._on_finding_activated(finding)
    assert len(workers) == 1 and host._finding_awaiting_map is None
    host.set_display_unit("in" if unit == "mm" else "mm")
    assert len(workers) == 1, "der Einheitenwechsel zeichnet nur vorhandene Werte neu"


@pytest.mark.parametrize("replacement", ["body", "kind", "document", "values", "cancel", "close"])
def test_deviation_late_signals_cannot_reuse_a_replaced_report_request(
    deviation_host: tuple[MainWindow, list[Any]], replacement: str
) -> None:
    from copy import deepcopy

    host, workers = deviation_host
    finding = Finding("perceive.deviation", "info", "Formabweichung", object_id="obj_1")
    host._on_finding_activated(finding)
    previous = workers[-1]
    if replacement == "body":
        host.object_tree.select_object("obj_2")
    elif replacement == "kind":
        host.analysis_bar.selector.setCurrentIndex(host.analysis_bar.selector.findData("wall"))
    elif replacement == "document":
        host.session.project.document = deepcopy(host.session.project.document)
        host._on_project()
    elif replacement == "values":
        from app.core.types import Parameter

        host.session.project.document.parameters["width"] = Parameter("width", 12.0)
        host._on_project()
    elif replacement == "cancel":
        host._render_progress_state(force_visible=True)
        assert host._progress_owner == "map"
        host.cancel_button.click()
        assert previous.cancelled.is_cancelled
        assert "abgebrochen" in host.analysis_bar.legend.note.text()
    else:
        host.release()
    before = host.viewport.analysis_map
    before_progress = host._progress_states["map"]
    previous.progressed.emit(0.7, "Veralteter Fortschritt")
    previous.done.emit(_deviation_result())
    previous.tooLarge.emit(1)
    previous.crashed.emit("veralteter Fehler")
    assert host.viewport.analysis_map is before
    assert host._progress_states["map"] == before_progress
    assert host.viewport._finding_mark is None


def test_deviation_empty_cache_hit_does_not_wait_for_a_nonexistent_worker(
    deviation_host: tuple[MainWindow, list[Any]],
) -> None:
    host, workers = deviation_host
    body = host.session.last_result.scene.objects["obj_1"]
    host._map_cache[host._analysis_cache_key(body, "deviation")] = None
    host._on_finding_activated(
        Finding("perceive.deviation", "info", "Formabweichung", object_id=body.id)
    )
    assert not workers
    assert host._finding_awaiting_map is None
    assert host.viewport._finding_mark is None


def test_deviation_cancel_and_unit_change_do_not_restart_the_measurement(
    deviation_host: tuple[MainWindow, list[Any]],
) -> None:
    host, workers = deviation_host
    host.analysis_bar.selector.setCurrentIndex(host.analysis_bar.selector.findData("deviation"))
    first = workers[-1]
    host.set_display_unit("in")
    assert workers == [first] and not first.cancelled.is_cancelled
    host._cancel_analysis()
    host.set_display_unit("mm")
    assert workers == [first]
    assert "abgebrochen" in host.analysis_bar.legend.note.text()
    # **Und der Weg zurück steht daneben** (Regel 17, Review Fenster #10):
    # Bis zum 21.09.2026 war „wurde abgebrochen" eine Sackgasse — wer die
    # Karte doch wollte, musste eine andere wählen und wieder zurück.
    button = host.analysis_bar.legend.action
    assert button is not None and button.text() == "Erneut berechnen"
    button.click()
    assert len(workers) == 2 and workers[-1] is not first, "dieselbe Karte, neu gestartet"
    assert host._map_cancelled_for is None


def test_deviation_old_worker_completion_leaves_the_new_progress_owner_active(
    deviation_host: tuple[MainWindow, list[Any]],
) -> None:
    host, workers = deviation_host
    host.analysis_bar.selector.setCurrentIndex(host.analysis_bar.selector.findData("deviation"))
    old = workers[-1]
    host.object_tree.select_object("obj_2")
    current = workers[-1]
    assert current is not old
    current.progressed.emit(0.4, "Aktuelle Karte")
    old.finished.emit()
    assert host._map_worker is current
    assert host._progress_states["map"].active
    assert host._progress_states["map"].text == "Aktuelle Karte"


def test_deviation_failure_ends_progress_and_preserves_the_document(
    deviation_host: tuple[MainWindow, list[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    from copy import deepcopy

    host, workers = deviation_host
    before = deepcopy(host.session.project.document)
    errors: list[Any] = []
    monkeypatch.setattr(host, "_on_error", errors.append)
    host._on_finding_activated(
        Finding("perceive.deviation", "info", "Formabweichung", object_id="obj_1")
    )
    workers[-1].crashed.emit("Die Kartenrechnung ist nicht möglich.")
    assert len(errors) == 1 and errors[0].suggestions
    assert not host._progress_states["map"].active
    assert host._finding_awaiting_map is None and host._map_request is None
    assert host.viewport.analysis_map is None and host.viewport._finding_mark is None
    assert host.session.project.document == before
    assert host.analysis_bar.legend.note.toolTip() == host.analysis_bar.legend.note.text()


def test_deviation_callbacks_do_not_touch_a_deleted_window(
    deviation_host: tuple[MainWindow, list[Any]],
) -> None:
    from shiboken6 import isValid

    host, workers = deviation_host
    host.analysis_bar.selector.setCurrentIndex(host.analysis_bar.selector.findData("deviation"))
    worker = workers[-1]
    host.release()
    host.viewport.release_renderer()
    host.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(host)
    worker.progressed.emit(0.5, "Veraltete Karte")
    worker.done.emit(_deviation_result())
    worker.aborted.emit()
    worker.crashed.emit("Veralteter Fehler")
    worker.finished.emit()
    assert host._map_worker is None
    assert not host._progress_states["map"].active


@pytest.mark.parametrize("source", ["native", "fit"])
def test_a_real_deviation_report_click_computes_and_marks_one_original_triangle(
    qt_app: QApplication, source: str
) -> None:
    """Der sichtbare Bericht führt über den echten Arbeiter zum Zeugen statt zur Kugelmitte."""
    import math

    import numpy as np
    import trimesh
    from PySide6.QtTest import QTest

    from app.core.geom.mesh import MeshData
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Feature, Scene, SceneObject, SurfacePatch

    host = MainWindow(Session(), UiSettings())
    shape = trimesh.creation.icosphere(subdivisions=0, radius=8.0)
    faces = tuple(range(len(shape.faces)))
    feature = Feature(
        "sphere_1",
        "sphere",
        "detected",
        {"centre": (0.0, 0.0, 0.0), "diameter": 16.0},
        face_indices=faces,
        surface_patches=(
            SurfacePatch("sphere", {"centre": (0.0, 0.0, 0.0), "radius": 8.0}, faces, source),
        ),
    )
    body = SceneObject(
        id="obj_1", name="Kugel", mesh=MeshData.of(shape), features={feature.id: feature}
    )
    result = EvaluationResult(Scene(objects={body.id: body}))
    host.session.last_result = result
    host.session.result_current = True
    host.object_tree.show_scene(result)
    if host.viewport.renderer is None:
        host.viewport.renderer = RecordingRenderer()
    host.viewport.show_scene(result)
    finding = Finding("perceive.deviation", "info", "Formabweichung", object_id=body.id)
    host.report.add_findings([finding])
    host.resize(1040, 760)
    host.show()
    try:
        # Mehrere Runden: Der Träger setzt die Karten je Ereignisdurchlauf
        # einmal (``OverlayHost._place_later``), und die Zeile, auf die der
        # Klick zielt, hat ihren Platz erst, wenn die Karte ihren hat.
        for _ in range(4):
            QApplication.processEvents()
        row = next(
            host.report.list.item(index)
            for index in range(host.report.list.count())
            if host.report.list.item(index).data(Qt.ItemDataRole.UserRole) is finding
        )
        host.report.list.scrollToItem(row)
        for _ in range(4):
            QApplication.processEvents()
        QTest.mouseClick(
            host.report.list.viewport(),
            Qt.MouseButton.LeftButton,
            pos=host.report.list.visualItemRect(row).center(),
        )
        wait_for_map(host)
        analysis = host.viewport.analysis_map
        assert analysis is not None and analysis.kind == "deviation"
        assert len(analysis.known) == len(shape.faces), "die Karte umfasst den ganzen Körper"
        assert analysis.witness_point is not None and analysis.witness_face is not None
        assert analysis.witness_distance is not None and analysis.maximum_interval is not None
        expected = 8.0 * (1.0 - math.sqrt((5.0 + 2.0 * math.sqrt(5.0)) / 15.0))
        assert analysis.maximum_interval[0] <= expected <= analysis.maximum_interval[1]
        assert analysis.witness_distance == pytest.approx(expected, abs=1e-6)
        triangle = shape.triangles[analysis.witness_face]
        barycentric = trimesh.triangles.points_to_barycentric(
            np.array([triangle]), np.array([analysis.witness_point])
        )[0]
        assert min(barycentric) >= -1e-9 and sum(barycentric) == pytest.approx(1.0)
        assert np.linalg.norm(analysis.witness_point) > 6.0, "kein Mittel gegenüberliegender Orte"
        assert host.viewport._finding_mark is not None
        assert host.viewport._finding_mark[0] == analysis.witness_point
        assert len(host.viewport._finding_actors) == 2, (
            "der aufzeichnende Renderer bekommt Ring und Text als zwei Darsteller"
        )
        assert "keine neue Einpassung" in host.analysis_bar.legend.note.text()
        reference = (
            "ursprüngliche exakte Flächen" if source == "native" else "bereits eingepasste Flächen"
        )
        assert reference in host.analysis_bar.legend.note.text()
        before = host.viewport._finding_mark[0]
        host.set_display_unit("in")
        assert host.viewport.analysis_map is analysis
        assert host.viewport._finding_mark[0] is before
        assert " in" in host.viewport._finding_mark[1]
    finally:
        host.hide()
        host.release()
        host.viewport.release_renderer()
        host.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_a_deviation_size_limit_offers_to_close_the_map_without_changing_the_body(
    deviation_host: tuple[MainWindow, list[Any]],
) -> None:
    host, workers = deviation_host
    host.analysis_bar.selector.setCurrentIndex(host.analysis_bar.selector.findData("deviation"))
    before = tuple(host.session.project.document.ops)
    workers[-1].tooLarge.emit(2)
    button = host.analysis_bar.legend.action
    assert button is not None and button.text() == tr("Keine Karte")
    button.click()
    assert host.analysis_bar.chosen() is None
    assert tuple(host.session.project.document.ops) == before


def test_calibration_invalidates_analysis_caches_and_late_workers(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Neue Messwerte gelten auch ohne neue Dreiecke; alte Arbeiter bleiben zurück."""
    from app.core.knowledge import calibration, profiles
    from app.core.types import SliceResult

    workers = []
    with monkeypatch.context() as local:
        local.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
        local.setattr(window._leash, "start", workers.append)
        profiles.reload()
        try:
            result = window.session.last_result
            entry = next(iter(result.scene.objects.values()))
            window.object_tree.select_object(entry.id)
            window.analysis_bar.show_map("overhang")
            window._analysis_map("overhang", entry.id)
            previous = workers[-1]
            previous_map_key = window._analysis_cache_key(entry, "overhang")
            previous_slice_key = window._analysis_cache_key(entry)
            profile = window.session.profile
            old_limits = profiles.analysis_limits(profile, entry)
            calibration.apply(
                calibration.from_measurements(
                    profile.material.id,
                    minimum_wall=old_limits[0] + 0.3,
                    overhang_angle=old_limits[1] - 7.0,
                ),
                directory=tmp_path,
                process=profile,
            )
            assert window.session.last_result is result
            assert window._analysis_cache_key(entry, "overhang") != previous_map_key
            assert window._analysis_cache_key(entry) != previous_slice_key
            old_map = maps.AnalysisMap(
                kind="overhang",
                title="Überhang",
                values=(0.0,) * entry.mesh.triangle_count,
                unit="°",
                low=0.0,
                high=90.0,
            )
            previous.done.emit(old_map)
            assert previous_map_key not in window._map_cache
            assert window.viewport.analysis_map is not old_map
            window._map_cache[previous_map_key] = old_map
            before = len(workers)
            window._analysis_map("overhang", entry.id)
            assert len(workers) == before + 1
            assert window.viewport.analysis_map is not old_map

            outcome = SliceResult(
                layers=(), support_volume=0.0, first_layer_area=0.0, source="internal"
            )
            old_worker = object()
            served = []
            window._slice_worker = old_worker
            window._slice_pending = previous_slice_key
            window._slice_cache = None
            window._slice_waiters = [served.append]
            window._slice_ready(outcome, previous_slice_key, old_worker)
            assert window._slice_cache is None
            assert not served
            assert window._slice_pending is None
            window._slice_worker = None
            window._slice_cache = outcome
            window._slice_key = previous_slice_key
            before = len(workers)
            assert window._slice_of(entry.id) is None
            assert len(workers) == before + 1
        finally:
            window._map_worker = None
            window._slice_worker = None
            for worker in workers:
                worker.release_finished_references()
                worker.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    profiles.reload()


@pytest.mark.parametrize("chosen", [("obj_2", "obj_4"), ()])
def test_a_bundle_context_menu_uses_the_same_body_choice_as_its_button(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    chosen: tuple[str, ...],
) -> None:
    """Der Rechtsklick bietet dieselbe Körperwahl und denselben Abbruchweg."""
    import trimesh
    from PySide6.QtWidgets import QMenu

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject
    from app.ui import panels

    host = MainWindow(Session(), UiSettings())
    report = panels.ReportPanel(host)
    bodies = ("obj_1", "obj_2", "obj_3", "obj_4")
    # Die lebenden Körper sind eine Zuordnung Kennung → Szenenobjekt, keine
    # Menge mehr: Die örtliche Suche fragt je Körper, ob er ein Netz ist.
    report._live_objects = {
        body: SceneObject(id=body, name=body, mesh=MeshData.of(trimesh.creation.box()))
        for body in bodies
    }
    report.add_findings(
        [
            Finding(
                code="perceive.too_large",
                severity="info",
                message="Für die Merkmalserkennung ist dieses Modell zu groß.",
                object_id=body,
                values={"triangles": 4000000, "limit": 2000000},
            )
            for body in bodies
        ]
    )
    report.resize(650, 600)
    report.show()
    qt_app.processEvents()
    bundle = next(
        report.list.item(index)
        for index in range(report.list.count())
        if report.list.item(index).data(panels._BODIES_ROLE) == bodies
    )
    direct: list[str | None] = []
    offered: list[tuple[str, ...]] = []
    applied: list[tuple[str, tuple[str, ...]]] = []
    monkeypatch.setattr(
        host,
        "error_handlers",
        lambda: {"decimate_mesh": lambda error: direct.append(error.object_id)},
    )
    monkeypatch.setattr(
        panels.BodyChoiceDialog,
        "ask",
        lambda parent, title, ids, names: offered.append(tuple(ids)) or chosen,
    )

    class ChoosingMenu(QMenu):
        def exec(self, position):
            return self.actions()[0]

    monkeypatch.setattr(panels, "QMenu", ChoosingMenu)
    report.actionOnBodies.connect(lambda action, ids: applied.append((action, tuple(ids))))
    try:
        report._on_menu(report.list.visualItemRect(bundle).center())
        assert offered == [bodies]
        assert direct == [], "kein stillschweigender Auftrag am ersten Körper"
        assert applied == ([("decimate_mesh", chosen)] if chosen else [])
    finally:
        report.close()
        report.deleteLater()


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    """Ein Fenster für einen Test — und danach warten, bis es still ist.

    Ohne das lief nach dem Test noch ein Arbeiter, und beim Herunterfahren des
    Interpreters ist der Thread-Pool der Schichtanalyse längst zu: „cannot
    schedule new futures after interpreter shutdown", quer über eine grüne
    Suite. Gewartet wird auf **alle** Arbeiter des Fensters, nicht nur auf die
    der Sitzung — das Fenster führt vier eigene.

    **Einer davon, die Update-Prüfung, startet in der Suite allerdings nie**,
    und der Satz stand hier zwei Runden lang falsch: Sie hängt an
    ``UiSettings.check_for_updates``, das in der Vorgabe **aus** ist, und kein
    Test schaltet es ein. Im Betrieb startet sie bei jedem Fenster von selbst,
    in der Suite nicht — gemessen am 23.08.2026 von 3d-druck-b8, die wissen
    musste, ob ihre Frist von zwei Sekunden gegen die vier Sekunden dieses
    Arbeiters reicht. Sie reicht, weil er gar nicht läuft.

    **Gewartet, nicht gelöscht**, und nicht über ``close()``:

    * ``close()`` löst ``closeEvent`` aus, und der fragt bei ungesicherten
      Änderungen modal nach — der Test hängt dann an einem Fenster, das
      niemand sieht. Die Falle steht seit zwei Runden im Kopf von
      ``tests/test_ui.py``.
    * ``deleteLater`` brachte nichts und kostete Stabilität. Ein Fenster, das
      liegen bleibt, ist harmlos; ein Thread, der noch läuft, ist es nicht,
      und genau der war die Ursache des Rauschens.

    **Zum sporadischen Absturz** (``Windows fatal exception: access
    violation``, ohne Zeile, an wechselnder Stelle): der galt hier lange als
    unabhängig von jeder Aufräumung — nachgemessen an je vier Läufen mit
    Aufräumung, mit Löschen und ganz ohne, riss er in jeder Version.

    Eine Ursache ist inzwischen gefunden und behoben: der Interaktionsstil des
    Viewports hielt eine gebundene Methode und damit den Viewport, der damals
    den Plotter hielt, der den Interactor hielt, der den Stil hielt. Diese
    Schleife überlebt jedes Schließen; abgeräumt wird sie später, und dann
    steht ein C++-Objekt hinter einer Python-Referenz, die es nicht mehr gibt.
    Mit einer schwachen Referenz läuft die Suite wieder in einem Zug.

    Es bleibt dasselbe Muster, das die Roadmap als „ersetzte Arbeiter lassen
    ihre Referenz los" führt. Reißt es wieder, ist die erste Frage: welche
    Python-Referenz hält ein Qt- oder VTK-Objekt am Leben, das längst weg
    sein sollte?
    """
    window = MainWindow(Session(), UiSettings())
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    yield window
    wait_for_map(window)
    window.wait_for_workers()


def select_plate(window: MainWindow) -> None:
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)


def on_the_bore_wall(window: MainWindow, feature_id: str) -> tuple[float, float, float]:
    """Eine Stelle auf der Wand dieser Bohrung — also eine, die ein Klick
    wirklich trifft.

    Drei Tests dieser Datei zeigten bis zum 22.08.2026 auf den **Mittelpunkt**
    einer Bohrung. Der liegt auf ihrer Achse, mitten im Leeren, und dort ist
    keine Oberfläche: Ein ``vtkCellPicker`` kann diesen Punkt nicht
    zurückgeben. Grün waren sie, weil ``_feature_at`` damals das Merkmal mit
    dem nächsten Mittelpunkt nahm — sie prüften also gegen die Rechenweise und
    nicht gegen einen Klick. Seit die Reichweite an den Dreiecken des Merkmals
    hängt (§18.5), zeigen sie dorthin, wo gezeigt wird.

    Die eigentliche Auswahltiefe steht in ``tests/test_selection.py``; hier
    bleiben die drei Aussagen, um die es diesen Tests ging.
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    feature = entry.features[feature_id]
    centre = feature.params["centre"]
    radius = float(feature.params["diameter"]) * 0.5
    return (float(centre[0]) + radius, float(centre[1]), 2.0)


def wait_for_map(window: MainWindow) -> None:
    """§18.9: Karten werden im Hintergrund gebaut, der Test wartet also wie
    das Fenster.
    """
    worker = window._map_worker
    if worker is not None:
        worker.wait(20_000)
    QApplication.processEvents()


# --- die Kartenauswahl ----------------------------------------------------------


@pytest.mark.parametrize("late", ["too_large", "crashed", "done", "none", "scene"])
def test_a_map_request_discards_old_colours_and_late_replies(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    late: str,
) -> None:
    """Der echte Signalanschluss hält Karte, Absage und Fehler an ihrer Anfrage."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Scene, SceneObject

    def make_object() -> SceneObject:
        return SceneObject(id="obj_1", name="Quader", mesh=MeshData(trimesh.creation.box()))

    host = MainWindow(Session(), UiSettings())
    result = EvaluationResult(Scene(objects={"obj_1": make_object()}))
    host.session.last_result = result
    host.session.result_current = True
    host.object_tree.show_scene(result)
    host.object_tree.select_object("obj_1")
    workers: list[Any] = []
    errors: list[Any] = []

    def release_test_workers() -> None:
        """Die absichtlich nicht gestarteten Attrappen geordnet freigeben."""
        for worker in workers:
            worker.release_finished_references()
            worker.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    request.addfinalizer(release_test_workers)
    monkeypatch.setattr(host._leash, "start", workers.append)
    monkeypatch.setattr(host, "_on_error", errors.append)
    old_map = maps.AnalysisMap(
        kind="fits", title="Passung", values=(1.0,) * 12, unit="mm", low=0.0, high=1.0
    )
    host._show_map(old_map, "obj_1")
    host.analysis_bar.show_map("support")
    host._analysis_map("support", "obj_1")
    previous = workers[-1]
    assert host.viewport.analysis_map is None, "the previous map belongs to another kind"
    previous.tooLarge.emit(120000)
    assert host.viewport.analysis_map is None
    assert "120000" in host.analysis_bar.legend.note.text()

    newest = maps.AnalysisMap(
        kind="overhang", title="Überhang", values=(0.0,) * 12, unit="°", low=0.0, high=90.0
    )
    host._map_cache[host._analysis_cache_key(result.scene.objects["obj_1"], "overhang")] = newest
    host.analysis_bar.show_map("overhang")
    host._analysis_map("overhang", "obj_1")
    if late == "none":
        host.analysis_bar.show_map(None)
        host._on_map_changed(None)
    elif late == "scene":
        # Dieselbe Kennung und Dreieckszahl, aber eine andere Auswertung.
        host.session.last_result = EvaluationResult(Scene(objects={"obj_1": make_object()}))
    before = host.analysis_bar.legend.note.text()
    if late in {"none", "scene", "too_large"}:
        previous.tooLarge.emit(200000)
    elif late == "crashed":
        previous.crashed.emit("obsolete worker")
    else:
        previous.done.emit(old_map)
    assert host.analysis_bar.legend.note.text() == before
    assert not errors, "obsolete worker errors must not interrupt a new choice"
    assert host.viewport.analysis_map is (None if late == "none" else newest)
    assert host._analysis_cache_key(result.scene.objects["obj_1"], "support") not in host._map_cache
    host.release()


def test_every_map_of_the_table_is_offered(qt_app: QApplication) -> None:
    """§18.4 zählt sieben Karten auf; die Leiste bietet alle sieben an und
    „keine".
    """
    bar = AnalysisBar()
    offered = [bar.selector.itemData(index) for index in range(bar.selector.count())]

    assert offered[0] is None
    assert tuple(offered[1:]) == MAP_ORDER


def test_a_timed_out_support_map_offers_the_regular_decimation_dialog(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Laufzeitbudget endet mit einer bedienbaren Handlung, nicht leer."""
    called: list[tuple[str, object]] = []
    monkeypatch.setattr(
        type(window),
        "run_operation",
        lambda self, spec, given=None: called.append((spec.name, given)),
    )

    window._map_timed_out(3.0)

    assert "3" in window.analysis_bar.legend.note.text()
    button = window.analysis_bar.legend.action
    assert button is not None
    assert button.text() == tr("Dreiecke verringern")
    button.click()
    assert called == [("decimate_mesh", None)], (
        "a runtime cannot justify a guessed target triangle count"
    )


def test_the_map_worker_reports_a_used_budget_as_an_expected_result(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Zeitbudget ist weder Absturz noch stiller Nutzerabbruch."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject
    from app.ui.main_window import _MapWorker

    entry = SceneObject(
        id="obj_1", name="Probe", mesh=MeshData.of(trimesh.creation.box()), features={}
    )
    worker = _MapWorker("support", entry, None, None)
    timed_out: list[float] = []
    crashed: list[str] = []
    worker.timedOut.connect(timed_out.append)
    worker.crashed.connect(crashed.append)
    monkeypatch.setattr(
        maps, "build", lambda *_args, **_kwargs: (_ for _ in ()).throw(maps.MapBudgetExceeded())
    )

    worker.work()

    assert timed_out == [maps.SUPPORT_MAP_BUDGET_SECONDS]
    assert crashed == []


def test_every_map_says_what_it_shows(qt_app: QApplication) -> None:
    """Sieben Fachwörter ohne Erklärung waren ein Ratespiel (Review 02.09.2026).

    Der Name benennt, der Satz sagt, was die Karte zeigt — als Tooltip und als
    Beschreibung für Hilfstechniken, für jeden Eintrag und für den Haken.
    """
    from PySide6.QtCore import Qt

    bar = AnalysisBar()
    for index in range(bar.selector.count()):
        for role in (Qt.ItemDataRole.ToolTipRole, Qt.ItemDataRole.AccessibleDescriptionRole):
            sentence = bar.selector.itemData(index, role)
            assert isinstance(sentence, str) and sentence.endswith("."), (index, role)
    assert bar.overlay.toolTip().endswith(".")
    assert bar.overlay.accessibleDescription() == bar.overlay.toolTip()


def test_choosing_a_map_paints_the_body(window: MainWindow) -> None:
    select_plate(window)
    window.analysis_bar.selector.setCurrentIndex(window.analysis_bar.selector.findData("overhang"))
    wait_for_map(window)

    analysis = window.viewport.analysis_map
    assert analysis is not None
    assert analysis.kind == "overhang"
    assert window.analysis_bar.legend.entries, "a map always comes with a legend (§18.4)"


def test_the_map_goes_away_again(window: MainWindow) -> None:
    select_plate(window)
    window.analysis_bar.selector.setCurrentIndex(window.analysis_bar.selector.findData("features"))
    window.analysis_bar.selector.setCurrentIndex(0)

    assert window.viewport.analysis_map is None
    assert window.analysis_bar.legend.entries == []


def test_without_a_selection_the_bar_says_what_is_missing(window: MainWindow) -> None:
    """Bei mehreren Körpern und keiner Auswahl sagt die Leiste, was fehlt.

    Mit genau einem Körper gibt es nichts zu wählen — die Karte nimmt ihn
    selbst (KUNDE-15, ``3b57b3644``,
    ``test_the_defect_map_needs_no_choice_with_one_body``). Deshalb kommt hier
    ein zweiter Körper dazu.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.last_result
    assert result is not None and len(result.scene.objects) == 2
    window.object_tree.tree.clearSelection()
    window._on_map_changed("wall")

    assert window.object_tree.selected() is None, "bei zwei Körpern wählt niemand still"
    assert "Objekt" in window.analysis_bar.legend.note.text()


def test_ambient_occlusion_yields_to_a_map(qt_app: QApplication) -> None:
    """Schönheit vor Ablesbarkeit gibt es nicht (§18.4, Konzept P15 §7).

    Die Umgebungsverdeckung dunkelt Vertiefungen nach — auf einer Karte, die
    nach Zahlen färbt und ihren Wertebereich als Legende danebenstellt, wäre
    der abgelesene Wert damit ein anderer als der gemeldete.

    Geprüft wird die Regel, nicht der Renderer: offscreen gibt es keinen, und
    ein Test, der sich dort überspringt, prüft nie etwas.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        assert viewport.ambient_occlusion, "ohne Karte ist die Verdeckung an"
        assert viewport.contact_shadows, "und der Kontaktschatten ebenso"

        viewport.set_analysis_map(
            maps.AnalysisMap(kind="wall", title="x", values=(1.0,), unit="mm", low=1.0, high=4.0),
            None,
        )
        assert not viewport.ambient_occlusion, "mit Karte ist sie aus"
        assert not viewport.contact_shadows, "und der Schatten auch — er dunkelt genauso nach"

        viewport.set_analysis_map(None, None)
        assert viewport.ambient_occlusion, "danach wieder an"
    finally:
        # Ein Widget ohne Elternteil räumt sich nicht selbst weg, und was am
        # Ende des Laufs noch lebt, wird beim Herunterfahren des Interpreters
        # aufgeräumt — dann ist der Thread-Pool der Schichtanalyse längst zu,
        # und die Meldung darüber landet als Rauschen in einer grünen Suite.
        viewport.deleteLater()


def test_a_painted_body_is_drawn_in_its_filament_colours(qt_app: QApplication) -> None:
    """§20: die Farbe steht im Dokument und wird exportiert — sie gehört
    gezeigt, solange ein Fehlgriff noch billig ist.

    Geprüft wird die Farbtabelle, nicht das Bild: sie entscheidet, welcher
    Slot welche Farbe bekommt, und sie ist ohne OpenGL-Kontext zu haben.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import MaterialSlot, SceneObject
    from app.ui.viewport import Viewport

    body = trimesh.creation.box(extents=(10, 10, 10))
    # Halb rot, halb blau — zwölf Dreiecke, sechs je Farbe.
    mesh = MeshData.of(body, tuple([1] * 6 + [2] * 6))
    entry = SceneObject(
        id=1,
        name="Teil",
        mesh=mesh,
        material_slots=[
            MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0)),
            MaterialSlot(index=2, name="Blau", colour=(0.0, 0.0, 1.0)),
        ],
    )

    viewport = Viewport()
    try:
        colours = viewport._slot_colours(mesh, entry, 12)
        assert colours is not None and colours.categorical, "eine Tabelle je Slot, keine Leiter"
        assert colours.colormap is not None
        assert colours.colormap[1] == "#ff0000"
        assert colours.colormap[2] == "#0000ff"
        assert colours.limits == (0, 2)
        assert list(colours.values) == [1] * 6 + [2] * 6

        # Ein Körper ohne Bemalung bleibt in der Objektfarbe.
        plain = SceneObject(id=2, name="Grau", mesh=MeshData.of(body))
        assert viewport._slot_colours(plain.mesh, plain, 12) is None
    finally:
        viewport.deleteLater()


def test_feature_edges_leave_a_round_body_alone() -> None:
    """Eine Kugel hat keine Kante, und eine erfundene wäre schlimmer als keine.

    Geprüft wird die Auswahlregel selbst, nicht das Bild: der Winkel entscheidet,
    was als Kante des Körpers gilt. Ein fein aufgelöster Zylinder darf seine
    Facetten nicht als Kanten bekommen, sonst ist das Ergebnis dasselbe wie
    „Massiv mit Kanten" — und dafür gibt es diesen Modus schon.
    """
    import trimesh

    from app.ui.render.edges import feature_edges
    from app.ui.viewport import FEATURE_EDGE_ANGLE

    def edges_of(mesh: trimesh.Trimesh) -> int:
        found = feature_edges(mesh.vertices, mesh.faces, FEATURE_EDGE_ANGLE)
        return len(found) // 2

    assert edges_of(trimesh.creation.icosphere(subdivisions=5)) == 0
    assert edges_of(trimesh.creation.cylinder(radius=10.0, height=20.0, sections=96)) > 0, (
        "die Deckflächen eines Zylinders treffen die Mantelfläche im rechten Winkel"
    )
    assert edges_of(trimesh.creation.box(extents=(20.0, 20.0, 20.0))) == 12, (
        "ein Würfel hat zwölf Kanten"
    )


# --- die Legende ----------------------------------------------------------------


def test_a_measured_map_shows_its_range_and_its_origin(qt_app: QApplication) -> None:
    legend = MapLegend()
    legend.show_map(
        maps.AnalysisMap(
            kind="wall",
            title="x",
            values=(1.0, 4.0),
            unit="mm",
            low=1.0,
            high=4.0,
            resolution=0.3,
        )
    )

    labels = [text for text, _colour in legend.entries]
    assert labels[0].startswith("1")
    assert labels[-1].startswith("4")
    # §22.5: woher eine Zahl kommt, gehört neben die Zahl.
    assert "intern" in legend.note.text()
    assert "0,3" in legend.note.text(), "a sampled map says how fine it was sampled"


def test_the_report_names_the_origin_of_every_finding(window: MainWindow) -> None:
    """§22.5: eine Schätzung und eine Messung dürfen nie gleich aussehen."""
    window.report.show_result(window.session.last_result)
    if window.report.list.count() == 0:
        pytest.skip("this model produced no findings")

    assert "Herkunft" in window.report.list.item(0).toolTip()


def test_a_map_of_levels_names_them(qt_app: QApplication) -> None:
    legend = MapLegend()
    legend.show_map(
        maps.AnalysisMap(
            kind="defects",
            title="x",
            values=(0.0, 1.0),
            unit="",
            low=0.0,
            high=2.0,
            categories=maps.DEFECT_LEVELS,
        )
    )

    # Aufgelöst verglichen, nicht gegen die Message-ID: Die Stufen sind seit
    # Regel 20 übersetzbar (`maps.DEFECT_LEVELS`), und was in der Legende steht,
    # ist ihre Übersetzung.
    assert [text for text, _colour in legend.entries] == [
        str(level) for level in maps.DEFECT_LEVELS
    ]


def test_the_colours_of_the_legend_rise_in_luminance() -> None:
    """§19.1: die Rampe ist in Graustufen lesbar, sie darf also kein Regenbogen
    sein.
    """
    from app.ui.palette import VIRIDIS, is_monotonic

    assert is_monotonic(VIRIDIS)


def test_a_large_feature_legend_represents_the_whole_colour_range(qt_app: QApplication) -> None:
    """Viele Merkmale dürfen keine gleichfarbige, irreführende Legende ergeben."""
    from app.ui.analysis_bar import LEGEND_MAX_ENTRIES, _legend_entries

    categories = tuple(f"feature_{index}" for index in range(120))
    analysis = maps.AnalysisMap(
        kind="features",
        title="Merkmale",
        values=(0.0, 119.0),
        unit="",
        low=0.0,
        high=119.0,
        categories=categories,
    )
    names = {key: f"Fläche {index}" for index, key in enumerate(categories)}
    legend = MapLegend()
    try:
        legend.show_map(analysis, names)
        samples = legend.entries[:-1]
        assert len(samples) == LEGEND_MAX_ENTRIES
        assert len({colour for _label, colour in samples}) >= 7
        assert samples[0][0] == names[categories[0]]
        assert samples[-1][0] == names[categories[-1]]
        assert all(sample in _legend_entries(analysis, names) for sample in samples)
        assert "112" in legend.entries[-1][0]
    finally:
        legend.deleteLater()


# --- Von einer Warnung zur Stelle -------------------------------------------------


def test_curvature_legend_keeps_physical_units_with_nonlinear_colours(qt_app: QApplication) -> None:
    """Kleine Radien bleiben farblich unterscheidbar, während die Legende echte Maße nennt."""
    analysis = maps.AnalysisMap(
        kind="curvature",
        title="Krümmung",
        values=(1.0, 3.0, 5.5, 6508.77),
        unit="mm",
        low=0.0,
        high=6508.77,
        display_scale="asinh",
    )
    legend = MapLegend()
    try:
        legend.show_map(analysis)
        labels = [text for text, _colour in legend.entries]
        assert labels[0] == length(0.0)
        assert labels[-1] == length(6508.77)
        assert labels[2] == length(analysis.value_at_display_fraction(0.5))
        assert labels[2] != length(3254.385)
        assert "logarithmisch" in legend.note.text()
        assert analysis.values == (1.0, 3.0, 5.5, 6508.77)
        legend.show_map(dataclasses.replace(analysis, kind="wall", display_scale="linear"))
        assert legend.entries[2][0] == length(3254.385)
        assert "logarithmisch" not in legend.note.text()
    finally:
        legend.deleteLater()


def test_constant_map_legend_does_not_invent_a_larger_measured_range(qt_app: QApplication) -> None:
    """Ein konstanter Messbereich darf keine erfundene Spannweite von einem Millimeter nennen."""
    from app.ui.palette import VIRIDIS

    legend = MapLegend()
    try:
        legend.show_map(
            maps.AnalysisMap(
                kind="curvature", title="x", values=(0.0,), unit="mm", low=0.0, high=0.0
            )
        )
        assert legend.entries == [(length(0.0), VIRIDIS[0])]
    finally:
        legend.deleteLater()


@pytest.mark.parametrize("scale", ["linear", "asinh"])
def test_viewport_passes_the_maps_display_space_to_the_renderer(
    qt_app: QApplication, scale: Any
) -> None:
    """Renderer erhalten den Farbraum der Legende; die Messdaten bleiben im Kern unverändert."""
    import numpy as np
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.viewport import Viewport

    mesh = MeshData(trimesh.creation.box())
    values = (1.0, 3.0, 5.5, 6508.77) * 3
    analysis = maps.AnalysisMap(
        kind="curvature",
        title="x",
        values=values,
        unit="mm",
        low=0.0,
        high=6508.77,
        display_scale=scale,
    )
    result = EvaluationResult(
        scene=Scene(objects={"obj_1": SceneObject(id="obj_1", name="Prüfkörper", mesh=mesh)})
    )
    viewport = Viewport()
    renderer = RecordingRenderer()
    viewport.renderer = renderer
    try:
        viewport.show_scene(result)
        viewport.set_analysis_map(analysis, "obj_1")
        surfaces = [
            entry
            for kind, entry in renderer.drawn
            if kind == "surface" and entry["name"] == "object:obj_1"
        ]
        colours = surfaces[-1]["cell_colours"]
        assert colours is not None
        assert np.array_equal(colours.values, analysis.display_values())
        assert colours.limits == analysis.display_limits
        assert viewport._scalars_for("another-object", 12) is None
        assert viewport._scalars_for("obj_1", 11) is None
        assert analysis.values == values
    finally:
        viewport.release_renderer()
        viewport.deleteLater()


def test_clicking_a_warning_switches_the_map_and_moves_the_camera(window: MainWindow) -> None:
    """§18.4: der kürzeste Weg von „da ist ein Problem" zu „hier ist es"."""
    select_plate(window)
    finding = Finding(
        code="fit.violated",
        severity="warning",
        message="zu eng",
        object_id="obj_1",
        feature_ids=("hole_1",),
    )
    window._on_finding_activated(finding)
    wait_for_map(window)

    assert window.analysis_bar.chosen() == "fits"
    analysis = window.viewport.analysis_map
    assert analysis is not None and analysis.kind == "fits"


def test_a_report_click_keeps_its_mark_across_the_async_map(
    window: MainWindow,
) -> None:
    """Bericht, Kartenarbeiter, Renderer und Zeitgeber halten dieselbe Zusage.

    Der kleine Viewport-Test kann nur sagen, was ``show_scene`` mit einer
    Attrappe aufruft. Der Kundenfehler lag eine Ebene höher: Ein echter Klick
    zeichnete Ring und Text, die fertige Analysekarte baute danach die Szene
    neu und nahm beide wieder weg. Dieser Test fährt deshalb die ganze Kette
    von der sichtbaren Berichtszeile bis zu ``set_analysis_map`` und lässt den
    echten ``QTimer`` in der Qt-Ereignisschleife ablaufen.

    Offscreen hängt der Test einen aufzeichnenden Renderer in den Viewport,
    statt eine Methode zu ersetzen; auf einer Bildschirmplattform bleibt der
    wirkliche Renderer des Fensters im Einsatz. Damit prüft der normale Lauf
    die aufgezeichneten Elemente, und der Windows-Beleg zusätzlich die des
    echten Renderers.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.viewport import FINDING_MARK_MS

    viewport = window.viewport
    owned_renderer: RecordingRenderer | None = None
    before_rebuild: list[tuple[object | None, tuple[Any, ...], frozenset[str]]] = []
    after_rebuild: list[tuple[object | None, tuple[Any, ...], frozenset[str]]] = []
    original_set_map = viewport.set_analysis_map

    def actor_names() -> frozenset[str]:
        renderer = viewport.renderer
        assert renderer is not None
        if isinstance(renderer, RecordingRenderer):
            gone = {id(item) for item in renderer.removed}
            return frozenset(item.name for item in renderer.items if id(item) not in gone)
        # Der echte Renderer führt seine Elemente unter ihrem Aktor.
        return frozenset(item.name for item in getattr(renderer, "_items", {}).values())

    def has_actor(names: frozenset[str], wanted: str) -> bool:
        return wanted in names

    def observe_map(analysis: Any, object_id: Any) -> None:
        before_rebuild.append(
            (viewport._finding_mark, tuple(viewport._finding_actors), actor_names())
        )
        original_set_map(analysis, object_id)
        after_rebuild.append(
            (viewport._finding_mark, tuple(viewport._finding_actors), actor_names())
        )

    try:
        if viewport.renderer is None:
            owned_renderer = RecordingRenderer()
            viewport.renderer = owned_renderer
            viewport.show_scene(window.session.last_result)
        viewport.set_analysis_map = observe_map  # type: ignore[method-assign]

        select_plate(window)
        finding = Finding(
            code="fit.violated",
            severity="warning",
            message="Diese Passung ist zu eng.",
            object_id="obj_1",
            feature_ids=("hole_1",),
        )
        window.report.add_findings([finding])
        window.resize(1040, 760)
        window.show()
        QApplication.processEvents()

        item = next(
            window.report.list.item(row)
            for row in range(window.report.list.count())
            if window.report.list.item(row).data(Qt.ItemDataRole.UserRole) is finding
        )
        window.report.list.scrollToItem(item)
        QApplication.processEvents()
        QTest.mouseClick(
            window.report.list.viewport(),
            Qt.MouseButton.LeftButton,
            pos=window.report.list.visualItemRect(item).center(),
        )
        wait_for_map(window)

        assert before_rebuild and before_rebuild[-1][0] is not None, (
            "die Marke muss schon stehen, wenn die fertige Karte die Szene neu baut"
        )
        assert len(before_rebuild[-1][1]) == 2, "Ring und Text standen vor dem Kartenaufbau"
        assert has_actor(before_rebuild[-1][2], "finding_ring"), sorted(before_rebuild[-1][2])
        assert has_actor(before_rebuild[-1][2], "finding_label"), sorted(before_rebuild[-1][2])
        assert after_rebuild and after_rebuild[-1][0] == before_rebuild[-1][0]
        assert len(after_rebuild[-1][1]) == 2, "der Kartenaufbau zeichnet beide Aktoren neu"
        assert after_rebuild[-1][1] != before_rebuild[-1][1], (
            "alte Python-Referenzen dürfen keinen erhaltenen Renderer vortäuschen"
        )
        assert has_actor(after_rebuild[-1][2], "finding_ring"), sorted(after_rebuild[-1][2])
        assert has_actor(after_rebuild[-1][2], "finding_label"), sorted(after_rebuild[-1][2])
        assert viewport.analysis_map is not None and viewport.analysis_map.kind == "fits"
        assert viewport._finding_mark == before_rebuild[-1][0]
        assert viewport._finding_timer.isActive(), "die sichtbare Frist läuft nach dem Kartenaufbau"
        assert tuple(viewport._finding_actors) == after_rebuild[-1][1]
        current_names = actor_names()
        assert has_actor(current_names, "finding_ring"), sorted(current_names)
        assert has_actor(current_names, "finding_label"), sorted(current_names)

        QTest.qWait(FINDING_MARK_MS + 100)
        QApplication.processEvents()
        assert viewport._finding_mark is None, "der semantische Zustand läuft mit der Frist ab"
        assert viewport._finding_actors == [], "nach der Frist bleibt kein nativer Aktor"
        expired_names = actor_names()
        assert not has_actor(expired_names, "finding_ring")
        assert not has_actor(expired_names, "finding_label")
    finally:
        window.hide()
        viewport.set_analysis_map = original_set_map  # type: ignore[method-assign]
        viewport._finding_timer.stop()
        viewport._hide_finding_mark(render=False)
        if owned_renderer is not None:
            viewport.renderer = None


def test_a_warning_without_a_map_still_finds_its_place(window: MainWindow) -> None:
    select_plate(window)
    finding = Finding(
        code="etwas.anderes",
        severity="warning",
        message="x",
        object_id="obj_1",
        location=(1.0, 2.0, 3.0),
    )
    window._on_finding_activated(finding)

    assert window.analysis_bar.chosen() is None, "no map claims this code"


# --- feature overlay (§18.5) ----------------------------------------------------


def test_the_object_tree_lists_the_features(window: MainWindow) -> None:
    """Name links, Maß rechts — und beides lesbar.

    Vorher stand links die ganze Beschriftung und rechts der Typ („hole",
    „face"): links war abgeschnitten, was rechts gefehlt hat.
    """
    item = window.object_tree.tree.topLevelItem(0)

    assert item is not None and item.childCount() >= 4, "four bores and the faces"
    names = [item.child(index).text(0) for index in range(item.childCount())]
    measures = [item.child(index).text(1) for index in range(item.childCount())]

    assert any(text.startswith(tr("Bohrung")) for text in names)
    assert any(text.startswith("Ø") for text in measures), "das Maß gehört in die Maßspalte"
    assert not any(text in ("hole", "face") for text in measures), "der Typ ist kein Maß"


def test_a_fillet_says_what_it_is_and_how_big() -> None:
    """Im Objektbaum stand „fillet_1" — ein englisches Wort in der Oberfläche,
    an ``tr()`` vorbei, und daneben eine leere Maßspalte.

    Die Merkmalsart kam im August dazu; die Beschriftung wurde nicht
    nachgezogen, und ``feature_name`` fiel auf die Kennung zurück. **Kein Test
    hat es bemerkt, und das ist der eigentliche Befund:** Die Tests fragen, *ob*
    ein Merkmal erkannt wird, nicht, *was* dort steht. Gemeldet hat es
    3d-druck-3a beim Durchsehen der eigenen Arbeit.

    **R und nicht Ø**, weil eine Verrundung über ihren Radius benannt wird —
    der Kunde sagt „R3", der Slicer sagt „R3", Fusion sagt „R3".

    Und die Unterscheidung ist mehr als Kosmetik: Eine einspringende Ecke
    bedeutet für den Druck etwas anderes als eine ausspringende. Eine
    Hohlkehle ist die Stelle, an der später die Frage kommt, ob die Düse dort
    überhaupt hinkommt.
    """
    from app.core.types import Feature
    from app.ui.labels import feature_measure, feature_name

    def fillet(name: str, *, recess: bool) -> Feature:
        return Feature(
            id=name,
            kind="fillet",
            params={"radius": 3.0, "recess": recess},
            provenance="test",
            # Ein Maß ohne belegte Quelle trägt „Maßherkunft nicht bestimmt“ —
            # hier steht die Beschriftung selbst auf dem Prüfstand, nicht die Quelle.
            measure_sources={"radius": "native"},
        )

    assert feature_name("fillet_1", fillet("fillet_1", recess=False)) == tr("Verrundung")
    assert feature_name("fillet_2", fillet("fillet_2", recess=True)) == tr("Hohlkehle")
    assert feature_measure(fillet("fillet_1", recess=False)) == (
        f"R{length(3.0)} · {tr('aus der Konstruktion')}"
    )


def test_a_face_is_named_by_where_it_looks() -> None:
    """Im Baum stand `face_2` — die Kennung, mit der der Op-Stack rechnet, und
    für einen Menschen eine Nummer ohne Aussage.

    Eine ebene Fläche weiß, wohin sie zeigt. Die Kennung bleibt: sie steht im
    Tooltip und in jedem Parameterfeld.
    """
    from app.core.types import Feature
    from app.ui.labels import feature_name

    def face(name: str, normal: tuple[float, float, float]) -> Feature:
        return Feature(
            id=name, kind="face", params={"normal": normal, "area": 100.0}, provenance="test"
        )

    assert feature_name("face_2", face("face_2", (0.0, 0.0, 1.0))) == tr("Oberseite")
    assert feature_name("face_1", face("face_1", (0.0, 0.0, -1.0))) == tr("Unterseite")
    assert feature_name("face_3", face("face_3", (0.0, -1.0, 0.0))) == tr("Vorderseite")
    assert feature_name("face_9", face("face_9", (0.6, 0.0, 0.8))) == tr("Schrägfläche")


def test_a_curved_face_is_named_by_its_hollowness_and_not_by_a_direction() -> None:
    """Der Bogen eines D zeigt in jede Richtung seines Verlaufs — „Vorderseite"
    wäre eine Aussage über nichts. Was ihn vom anderen Bogen unterscheidet,
    ist, ob er hohl liegt: ``inner`` aus der Konvexität seiner Nähte. Das Maß
    ist seine Fläche, wie bei der ebenen."""
    from app.core.types import Feature
    from app.ui.labels import area, feature_measure, feature_name

    def curved(name: str, *, inner: bool) -> Feature:
        return Feature(
            id=name,
            kind="curved_face",
            params={"area": 381.7, "normal": (0.9, 0.0, 0.0), "inner": inner},
            measure_sources={"area": "facets"},
            provenance="test",
        )

    assert feature_name("curve_1", curved("curve_1", inner=False)) == tr("Gerundete Seite")
    assert feature_name("curve_2", curved("curve_2", inner=True)) == tr("Gerundete Seite innen")
    assert feature_measure(curved("curve_1", inner=False)) == (f"{area(381.7)} · {tr('gemessen')}")


def test_a_sphere_and_a_torus_say_which_way_they_point() -> None:
    """``recess`` trennt bei Kugel und Torus dasselbe wie beim Kegel zwischen
    Senkung und Verjüngung: hinein oder heraus.

    Eine ausgehöhlte Kugel ist eine Pfanne (Kugelgelenk, Magnettasche), eine
    aufgesetzte eine Kuppel; beim Torus heißen die beiden Formen Kehle und
    Wulst. Vor ``15d3d16`` stand dort die rohe Kennung — ``sphere_1`` im Baum,
    und der Nächste hält einen englischen Schlüssel für Absicht.

    Entworfen von 3d-druck-b8 zusammen mit den Beschriftungen; die Mutation
    (``recess`` bei der Kugel vertauscht) meldet beide Kugelzeilen und lässt
    die Torus-Zeilen grün, der Test trennt die vier Aussagen also wirklich.
    """
    from app.core.types import Feature
    from app.ui.labels import feature_name

    def round_one(kind: str, recess: bool) -> Feature:
        return Feature(id=f"{kind}_1", kind=kind, params={"recess": recess}, provenance="test")

    assert feature_name("sphere_1", round_one("sphere", True)) == tr("Pfanne")
    assert feature_name("sphere_1", round_one("sphere", False)) == tr("Kuppel")
    assert feature_name("torus_1", round_one("torus", True)) == tr("Kehle")
    assert feature_name("torus_1", round_one("torus", False)) == tr("Wulst")


def test_a_feature_offers_the_operations_that_apply_to_it(window: MainWindow) -> None:
    """§10, §18.5: das Kontextmenü kommt aus ``applies_to``, nicht aus einer
    Liste.
    """
    entries = window.object_tree.operations_for_feature("face")

    assert entries, "drilling applies to a face"
    assert all("face" in spec.applies_to for spec in entries)


def test_the_view_and_the_tree_show_the_same_menu(window: MainWindow) -> None:
    """Zwei Menüs mit derselben Aufgabe wären zwei Gelegenheiten,
    auseinanderzulaufen.

    Der Viewport baut deshalb keines: er lässt sich das des Objektbaums geben.
    Ohne Auswahl gibt es nichts anzubieten — und dann geht auch nichts auf.
    """
    window.object_tree.tree.clearSelection()
    assert window.object_tree.context_menu() is None

    select_plate(window)
    menu = window.object_tree.context_menu()

    assert menu is not None
    offered = {
        action.text()
        for entry in menu.actions()
        for action in (entry.menu().actions() if entry.menu() else [entry])
    }
    assert offered, "Sichtbarkeit steht darin"
    menu.deleteLater()


def test_the_context_menu_carries_no_operations_any_more(window: MainWindow) -> None:
    """Rechtsklick auf Körper oder Fläche: kein Operationsverzeichnis mehr.

    Bis zum 11.09.2026 stand dort dieselbe Liste wie rechts in der Karte der
    Handlungen — gruppiert, gefaltet, mit dem Katalog an der Stelle der
    Bausteine —, und zwei Orte für dieselbe Liste sind einer zu viel (Robert:
    „ebenso dann beim rechtsklick im objektbaum"). Was bleibt, gibt es nur
    hier: der Weg vom Ergebnis zurück zum Schritt, die Skizze auf der Fläche
    und die Sichtbarkeit. Die Operationen stehen rechts — an derselben
    Auswahl, mit Grund, wenn eine nicht geht.
    """
    from app.core.registry import REGISTRY

    titles = {str(spec.title) for spec in REGISTRY.all()}

    def offered(menu) -> set[str]:
        return {
            action.text().replace("&", "")
            for entry in menu.actions()
            for action in (entry.menu().actions() if entry.menu() else [entry])
            if not action.isSeparator()
        }

    select_plate(window)
    menu = window.object_tree.context_menu()
    assert menu is not None
    body = offered(menu)
    assert body, "Sichtbarkeit steht darin"
    assert not (body & titles), f"am Körper stehen noch Operationen: {sorted(body & titles)}"
    assert not any(entry.menu() is not None for entry in menu.actions()), "und kein Untermenü"
    menu.deleteLater()
    assert set(window.selection_operations._buttons) & {"union_objects", "hollow_object"}, (
        "die Operationen stehen rechts"
    )

    object_id = next(iter(window.session.last_result.scene.objects))
    entry = window.session.last_result.scene.objects[object_id]
    face = next(name for name, feature in entry.features.items() if feature.kind == "face")
    window.object_tree.select_feature(object_id, face)
    menu = window.object_tree.context_menu()
    assert menu is not None
    at_face = offered(menu)
    assert not (at_face & titles), (
        f"an der Fläche stehen noch Operationen: {sorted(at_face & titles)}"
    )
    assert tr("Auf dieser Fläche zeichnen") in at_face, (
        f"die Skizze auf der Fläche bleibt: {sorted(at_face)}"
    )
    menu.deleteLater()


def test_no_menu_shows_the_same_line_twice(window: MainWindow) -> None:
    """Zwei Zeilen mit demselben Text sind eine Frage ohne Antwort.

    An jeder Fläche stand **Bohrung setzen** zweimal: ``drill_hole`` und
    ``drill_brep_hole`` tragen denselben Titel, und der Kunde kann nicht
    wissen, welche gemeint ist — die Auswahl trifft er blind, und je nach
    Treffer bekommt er einen anderen Rechenkern.

    Die Menüleiste hat das Paar seit je zusammengelegt (``MENU_TWINS``): Der
    sichtbare Zwilling trägt den Eintrag, der andere ist über einen
    Umschalter in dessen Dialog erreichbar. ``operations_for_feature`` gab
    ``REGISTRY.for_feature`` ungefiltert weiter und kannte die Zusammenlegung
    nicht. **Dieselbe Frage, zwei Rechnungen** — genau der Grund, aus dem die
    Menütiefe in den Kern gewandert ist.

    Geprüft wird die Zusage und nicht der eine Fall: Kein Kontextmenü zeigt
    zwei Zeilen mit demselben Text, auf keiner Ebene. Ein Test auf „Bohrung
    setzen genau einmal" wäre am Tag des nächsten Zwillings still.

    Und **nicht** über ``operations_for_feature`` formuliert, obwohl der
    Filter dort sitzt: Ein Test, der seine Erwartung aus dem Prüfling holt,
    wird mit ihm zusammen falsch. Gezählt wird am gebauten Menü.
    """
    scene = window.session.last_result.scene.objects["obj_1"]
    features = [entry.id for entry in scene.features.values()]
    assert features, "das Testmodell hat keine Merkmale — dann prüft dieser Test nichts"

    seen = 0
    for feature_id in features:
        window.object_tree.select_feature("obj_1", feature_id)
        menu = window.object_tree.context_menu()
        assert menu is not None
        levels = [[action for action in menu.actions() if not action.isSeparator()]]
        levels += [
            [entry for entry in action.menu().actions() if not entry.isSeparator()]
            for action in menu.actions()
            if action.menu()
        ]
        for level in levels:
            texts = [action.text() for action in level]
            seen += len(texts)
            twice = sorted({text for text in texts if texts.count(text) > 1})
            assert not twice, f"{feature_id}: zweimal dieselbe Zeile {twice}"
        menu.deleteLater()

    assert seen > len(features), "keine Menüzeilen gezählt — dann prüft dieser Test nichts"


def _insert_a_thread(window: MainWindow) -> str:
    """Ein Gewinde einsetzen und die Kennung seines Merkmals zurückgeben.

    Die Fixture liest ein Modell ein, und dessen Merkmale sind **erkannt**.
    Ein erzeugtes entsteht, wo ein Baustein eines verspricht (§24.1) — beim
    Gewinde also, und das ist genau der Fall, an dem das leere Kontextmenü
    aufgefallen ist.

    Nicht am Bohren: ``drill_hole`` rechnet Geometrie und deklariert kein
    Merkmal. Was es hinterlässt, findet die Erkennung wieder, und ein
    erkanntes Merkmal trägt keinen Erzeuger.
    """
    from app.core.registry import REGISTRY

    select_plate(window)
    window.run_operation(REGISTRY.get("insert_printed_thread"))
    dialog = window._op_dialog
    assert dialog is not None

    # **Eine Stelle gehört dazu, seit der Baustein danach fragt.** Bis zum
    # 25.08.2026 kam dieser Test ohne aus: Ein Baustein ohne gewähltes Merkmal
    # landete still im Nullpunkt des Objekts, und der Test nahm das Ergebnis.
    # Jetzt hält die Auswertung an und sagt, was fehlt (Regel 21) — was der
    # Kunde im Katalog bekommt, bekommt dieser Test auch.
    before = window.session.last_result
    assert before is not None
    faces = [
        feature_id
        for entry in before.scene.objects.values()
        for feature_id, feature in entry.features.items()
        if feature.kind == "face"
    ]
    assert faces, "das eingelesene Modell trägt keine Fläche, an die etwas käme"
    picker = dialog._editors["at_feature"]
    index = picker.findData(faces[0])
    assert index >= 0, (
        f"{faces[0]} steht nicht zur Wahl: {[picker.itemData(i) for i in range(picker.count())]}"
    )
    picker.setCurrentIndex(index)
    dialog.accept()
    window.session.wait_for_idle()

    result = window.session.last_result
    assert result is not None
    made = [
        (object_id, feature_id)
        for object_id, entry in result.scene.objects.items()
        for feature_id, feature in entry.features.items()
        if feature.created_by is not None
    ]
    assert made, "der Baustein hat ein benanntes Merkmal hinterlassen"
    object_id, feature_id = made[0]
    window.object_tree.select_feature(object_id, feature_id)
    return feature_id


def test_a_created_feature_offers_the_step_that_made_it(window: MainWindow) -> None:
    """§21.2: Ein erzeugtes Merkmal bietet immer den Schritt an, der es erzeugt
    hat.

    Der einzige Weg vom *Ergebnis* zurück zum *Schritt*. Ohne ihn sucht der
    Kunde im Verlauf, welcher der Einträge die Bohrung war, die er gerade
    ansieht — mit ihm zeigt er auf das Ding, das er sieht.

    Die Frage lautete lange, welche Operation fachlich auf ein fertiges
    Gewinde gehört, und ``for_feature`` gab darauf nichts zurück. Über
    ``applies_to`` wäre die Antwort eine neue Operation je Merkmalsart
    gewesen; über die Provenienz gilt sie für alle.
    """
    _insert_a_thread(window)
    menu = window.object_tree.context_menu()

    assert menu is not None
    rows = [action.text() for action in menu.actions() if not action.isSeparator()]
    assert tr("Diesen Schritt ändern") in rows, rows
    menu.deleteLater()


def test_the_offered_step_is_the_one_that_made_the_feature(window: MainWindow) -> None:
    """Und zwar der richtige: die Kennung kommt aus ``created_by``, nicht aus
    dem Ende des Stapels.

    ``SceneObject.created_by`` wird bei **jeder** Operation neu gesetzt, die
    das Objekt ausgibt — sie zeigt auf die zuletzt beteiligte. Am Merkmal
    steht der Erzeuger.
    """
    feature_id = _insert_a_thread(window)
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[window.object_tree.selected()]
    expected = entry.features[feature_id].created_by

    asked: list[int] = []
    window.object_tree.stepRequested.connect(asked.append)
    menu = window.object_tree.context_menu()
    assert menu is not None
    for action in menu.actions():
        if action.text() == tr("Diesen Schritt ändern"):
            action.trigger()

    assert asked == [expected], (asked, expected)
    menu.deleteLater()


def test_the_menu_entry_opens_that_step(window: MainWindow) -> None:
    """Und der Klick landet im Dialog des Schritts, nicht in einem neuen.

    Die halbe Zusage wäre ein Menüeintrag, der ein Signal sendet, das niemand
    hört. Geprüft wird deshalb bis ans Ende: Der Dialog steht offen, er zeigt
    die Operation, die das Merkmal erzeugt hat, und er **ersetzt** ihren
    Schritt beim Übernehmen, statt einen zweiten anzulegen (§15.4).

    „Kein zweiter Schritt" wird an der **Schrittliste** gemessen, nicht an
    der Transaktionszahl: Die erste Fassung nagelte hier fest, dass die
    Änderung keine Transaktion anlegt — und damit den Fehler, dass sie nicht
    rücknehmbar war (Gesamtreview-b, Bericht 01, Szene 5; tests.md: „Prüft
    dieser Test eine Zusage — oder den Ist-Zustand?"). Seit Format v12 IST
    die Transaktion Teil der Zusage: eine dazu, der Stapel unverändert.
    """
    _insert_a_thread(window)
    steps_before = [entry.id for entry in window.session.project.document.ops]
    transactions_before = len(window.session.project.document.transactions)
    menu = window.object_tree.context_menu()
    assert menu is not None
    for action in menu.actions():
        if action.text() == tr("Diesen Schritt ändern"):
            action.trigger()
    menu.deleteLater()

    dialog = window._op_dialog
    assert dialog is not None, "der Schritt steht offen"
    assert dialog.spec.name == "insert_printed_thread", dialog.spec.name

    # Übernehmen wartet auf die dargestellte Vorschau (20.09.2026): erst
    # rechnen und zeigen lassen, dann klicken — wie der Kunde es sieht.
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    assert dialog.can_accept(), dialog.toolTip()
    dialog.accept()
    window.session.wait_for_idle()
    document = window.session.project.document
    assert [entry.id for entry in document.ops] == steps_before, (
        "derselbe Schritt, ersetzt — kein zweiter im Stapel, keiner weg"
    )
    assert len(document.transactions) == transactions_before + 1, (
        "und die Änderung ist rücknehmbar: genau eine Transaktion dazu (§15.5)"
    )


def test_a_detected_feature_has_no_step_to_offer(window: MainWindow) -> None:
    """Ein **erkanntes** Merkmal hat keinen Erzeuger, und der Eintrag entfällt
    dort ersatzlos.

    Ein Menüeintrag, der ins Leere führt, ist schlechter als keiner (§21.2).
    Die Bohrungen dieser Platte kommen aus einer STL — sie hat niemand
    gesetzt.
    """
    window.object_tree.select_feature("obj_1", "hole_2")
    result = window.session.last_result
    assert result is not None
    feature = result.scene.objects["obj_1"].features["hole_2"]
    assert feature.created_by is None, "eingelesen, nicht erzeugt"

    menu = window.object_tree.context_menu()

    assert menu is not None
    rows = [action.text() for action in menu.actions()]
    assert tr("Diesen Schritt ändern") not in rows, rows
    menu.deleteLater()


def test_selecting_a_feature_reaches_the_viewport(window: MainWindow) -> None:
    window.object_tree.select_feature("obj_1", "hole_2")

    assert window.object_tree.selected_feature() == "hole_2"
    assert window.object_tree.selected() == "obj_1"


def test_selecting_a_feature_passes_its_mesh_to_the_action_panel(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Randringbeweis erreicht das Panel zusammen mit den Merkmalen."""
    from app.core.geom.mesh import MeshData, as_mesh_data

    select_plate(window)
    entry = window.session.last_result.scene.objects["obj_1"]
    received: list[tuple[str, Any, Any, Any, MeshData | None]] = []

    def show_feature(
        feature_id: str,
        feature: Any,
        alike: Any = (),
        *,
        features: Any = None,
        mesh: MeshData | None = None,
        alone: bool = False,
        protected: bool = False,
    ) -> None:
        received.append((feature_id, feature, alike, features, mesh))

    monkeypatch.setattr(window.feature_panel, "show_feature", show_feature)

    window._on_feature_selected("hole_2")

    assert len(received) == 1
    feature_id, feature, _alike, available, mesh = received[0]
    assert feature_id == "hole_2"
    assert feature is entry.features[feature_id]
    assert available is entry.features
    assert mesh is as_mesh_data(entry.mesh)


def test_the_diameter_of_a_bore_reaches_the_status_bar(window: MainWindow) -> None:
    """§18.3: der Durchmesser kommt aus dem Merkmal, nicht aus einem Messklick."""
    select_plate(window)
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    window.object_tree.select_feature("obj_1", "hole_1")

    assert "Ø" in window.measurements.text()


def test_the_rotation_centre_is_the_body_and_not_the_scenery(window: MainWindow) -> None:
    """Gedreht wird um das Teil, nicht um den Bauraum (§2.9).

    Der Drehpunkt kam aus ``ComputeVisiblePropBounds`` — den Grenzen alles
    Sichtbaren, und dazu gehören Druckplatte und Bauraumrahmen. Der Rahmen ist
    250 mm hoch, das Teil 8: die Mitte lag über hundert Millimeter über dem
    Modell, die Kamera rückte dorthin mit, und im Bild stand die Kulisse,
    während das Teil unten aus der Ecke ragte. Genau so kam das Hauptfenster
    aus dem Abbildungswerkzeug heraus.

    Geprüft wird die Auskunft, nicht die Kamera: offscreen gibt es keinen
    Renderer, und ein Test, der sich dort überspringt, prüft nie etwas.
    """
    select_plate(window)
    window.viewport.show_scene(window.session.last_result)
    window.viewport.show_build_volume(window.session.profile)

    centre = window.viewport.rotation_centre()
    entry = window.session.last_result.scene.objects["obj_1"]
    box = entry.mesh.bounds

    assert centre is not None
    for axis in range(3):
        expected = (box.minimum[axis] + box.maximum[axis]) / 2.0
        assert centre[axis] == pytest.approx(expected), "die Mitte des Körpers"

    height = window.session.profile.printer.build_volume[2]
    assert centre[2] < height / 4.0, "und nicht die halbe Bauraumhöhe"


def test_a_chosen_feature_lights_up_instead_of_its_body(window: MainWindow) -> None:
    """Wer eine Bohrung anklickt, meint die Bohrung (§18.5).

    Gefärbt wurde der ganze Körper: die Auswahl zeigte das Objekt, und die
    Stelle, die gemeint war, unterschied sich von der Wand daneben durch
    nichts. Jetzt trägt das Merkmal die Auswahlfarbe auf seinen eigenen
    Dreiecken, und der Körper bleibt grau — dass er ausgewählt ist, steht im
    Objektbaum und in der Statusleiste, wie bei einer Analysekarte auch
    (§19.1).

    Geprüft wird die Entscheidung, nicht das Bild: offscreen gibt es keinen
    Renderer, und ein Test, der sich dort überspringt, prüft nie etwas.
    """
    select_plate(window)
    window.viewport.show_scene(window.session.last_result)
    window.viewport.select("obj_1")

    assert window.viewport.highlighted_object() == "obj_1", "ohne Merkmal färbt der Körper"
    assert window.viewport.highlighted_faces() == (), "und es leuchtet keine Fläche"

    window.object_tree.select_feature("obj_1", "hole_2")

    assert window.viewport.selected_feature == "hole_2"
    assert window.viewport.highlighted_object() is None, "jetzt nicht mehr der ganze Körper"
    faces = window.viewport.highlighted_faces()
    assert faces, "sondern die Dreiecke der Bohrung"
    entry = window.session.last_result.scene.objects["obj_1"]
    assert set(faces) == set(entry.features["hole_2"].face_indices)

    # Und zurück: ohne Merkmal gehört die Farbe wieder dem Körper.
    window.viewport.select_feature(None)
    assert window.viewport.highlighted_object() == "obj_1"
    assert window.viewport.highlighted_faces() == ()


def test_a_hidden_body_lights_up_nothing(window: MainWindow) -> None:
    """Ein ausgeblendeter Körper ist nicht im Bild, sein Merkmal also auch
    nicht — eine Fläche, die über einem unsichtbaren Teil schwebt, behauptet
    Geometrie, wo keine steht (§18.8)."""
    select_plate(window)
    window.viewport.show_scene(window.session.last_result)
    window.viewport.select("obj_1")
    window.viewport.select_feature("hole_2")
    assert window.viewport.highlighted_faces(), "sichtbar leuchtet sie"

    window.viewport.set_hidden(frozenset({"obj_1"}))
    assert window.viewport.highlighted_faces() == ()


def test_a_click_in_the_view_finds_the_feature_under_it(window: MainWindow) -> None:
    """§40 für P3: ein Klick muss die richtige Merkmal-ID liefern, keinen
    Beinahe-Treffer.

    Gezeigt wird auf die Bohrungswand (:func:`on_the_bore_wall`) und nicht
    daneben auf die Achse — dort ist keine Oberfläche, und ein Beinahe-Treffer
    war genau das, was der alte Mittelpunktsabstand lieferte.
    """
    select_plate(window)
    window.viewport.show_scene(window.session.last_result)
    window.viewport.select("obj_1")

    picked = window.viewport._feature_at(on_the_bore_wall(window, "hole_3"))
    assert picked == "hole_3"


def test_switching_navigation_keeps_the_navigator(qt_app: QApplication) -> None:
    """Ein Schemawechsel tauscht das Schema, nicht die Kameraführung (§2.9).

    Der Navigator hängt am Renderer und bekommt jede Zeigergeste; ihn bei
    jedem Wechsel neu anzumelden hieße, die Auswahl an der alten Anmeldung
    vorbeizuführen — genau der Fehler, den der pyvista-Stil zweimal hatte.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        viewport.renderer = RecordingRenderer()
        viewport.set_navigation("slicer")
        navigator = viewport._navigator
        assert navigator is not None and navigator.scheme == "slicer"

        viewport.set_navigation("solidon")
        assert viewport._navigator is navigator, "derselbe Navigator, neues Schema"
        assert navigator.scheme == "solidon"
    finally:
        viewport.renderer = None
        viewport.deleteLater()


def test_the_same_finding_is_not_listed_twice(qt_app: QApplication) -> None:
    """§17.3: zweimal gemeldet ist nicht zweimal passiert.

    „Kollisionen prüfen" und die Exportprüfung sehen dieselbe Sache. Nach
    beidem stand „Ein Objekt steht über den Bauraum hinaus" zweimal im Bericht,
    und wer das liest, sucht nach zwei Körpern, von denen es nur einen gibt.

    Geprüft wird das Panel allein: es braucht kein Fenster, und jedes Fenster
    bringt einen Viewport mit, der aufgeräumt werden will.
    """
    from app.ui.panels import ReportPanel

    finding = Finding(
        code="arrange.out_of_build_volume",
        severity="warning",
        message="Ein Objekt steht über den Bauraum hinaus.",
        object_id="obj_1",
        values={"object": "Halter", "excess": "15,00 mm"},
    )
    panel = ReportPanel()
    try:
        panel.add_findings([finding])
        panel.add_findings([finding])

        assert panel.list.count() == 1
    finally:
        panel.deleteLater()


def test_a_new_slicer_run_replaces_the_gcode_findings(qt_app: QApplication) -> None:
    """Die G-Code-Befunde beschreiben die jeweils letzte Druckdatei (Regel 14).

    Drei Läufe trugen dreimal die Druckzeit ein — jede mit anderer Zahl und
    darum nie „dasselbe" für die Wiedererkennung (Roberts Foto, 30.08.2026).
    Ein neuer Lauf ersetzt die Herkunft ``gcode``; was aus anderer Quelle
    stammt, bleibt stehen.
    """
    from app.ui.panels import ReportPanel

    def measured(minutes: str) -> Finding:
        return Finding(
            code="slicer.handover",
            severity="info",
            message="Diese Datei kommt aus dem externen Slicer.",
            values={"minutes": minutes},
            source="gcode",
        )

    kept = Finding(
        code="arrange.below_bed",
        severity="info",
        message="Ein Objekt steckt unter dem Druckbett.",
        object_id="obj_1",
        source="internal",
    )
    panel = ReportPanel()
    try:
        panel.add_findings([kept])
        panel.add_findings([measured("18")], replacing_source="gcode")
        panel.add_findings([measured("21")], replacing_source="gcode")

        assert panel.list.count() == 2, "ein Lauf, eine Messung — plus der fremde Befund"
        left = [
            panel.list.item(row).data(Qt.ItemDataRole.UserRole) for row in range(panel.list.count())
        ]
        assert any(entry.values.get("minutes") == "21" for entry in left), "die letzte Messung"
        assert not any(entry.values.get("minutes") == "18" for entry in left), "die alte ist fort"
        assert any(entry.code == "arrange.below_bed" for entry in left), "Fremdes bleibt"
    finally:
        panel.deleteLater()


def test_a_heavier_finding_replaces_the_lighter_same_one(qt_app: QApplication) -> None:
    """Derselbe Sachverhalt, zwei Gewichte — eine Zeile, die neuere gilt.

    Die Auswertung meldet „unter dem Druckbett" als Hinweis, die Exportprüfung
    beim Schreiben als Warnung (``about_to_write``). Beide nebeneinander lasen
    sich wie zwei Probleme (Roberts Foto, 30.08.2026); die severity steht mit
    Absicht nicht in der Wiedererkennung, also entscheidet die Reihenfolge —
    und der jüngere Stand einer Sache ist der, der gilt, in beide Richtungen.
    """
    from app.ui.panels import ReportPanel

    def sunk(severity: str) -> Finding:
        return Finding(
            code="arrange.below_bed",
            severity=severity,  # type: ignore[arg-type]
            message="Ein Objekt steckt unter dem Druckbett.",
            object_id="obj_1",
            values={"axes": "z", "excess": "10,00 mm"},
        )

    panel = ReportPanel()
    try:
        panel.add_findings([sunk("info")])
        panel.add_findings([sunk("warning")])

        assert panel.list.count() == 1, "ein Sachverhalt, eine Zeile"
        entry = panel.list.item(0).data(Qt.ItemDataRole.UserRole)
        assert entry.severity == "warning", "die Datei entsteht gleich — das wiegt schwerer"

        panel.add_findings([sunk("info")])
        assert panel.list.count() == 1
        entry = panel.list.item(0).data(Qt.ItemDataRole.UserRole)
        assert entry.severity == "info", "und zurück, sobald nur noch der Hinweis gilt"

        panel.add_findings([sunk("info")])
        assert panel.list.count() == 1, "gleich schwer bleibt stehen wie bisher"
    finally:
        panel.deleteLater()


def test_the_same_message_about_another_body_becomes_one_counted_line(
    qt_app: QApplication,
) -> None:
    """Zwei Körper stehen hinaus — eine Zeile „(2) …", beide Namen im Tooltip.

    Bis zum 11.09.2026 waren es zwei Zeilen („Zwei Körper stehen aus
    verschiedenen Gründen hinaus"); seit Roberts Ansage zählt der Satz, und
    die Zeile trägt beide Körper für den Klick.
    """
    from app.ui.panels import _BODIES_ROLE, ReportPanel

    first = Finding(
        code="arrange.out_of_build_volume",
        severity="warning",
        message="Ein Objekt steht über den Bauraum hinaus.",
        object_id="obj_1",
        values={"object": "Halter"},
    )
    second = dataclasses.replace(first, object_id="obj_2", values={"object": "Deckel"})
    panel = ReportPanel()
    try:
        panel.add_findings([first, second])

        assert panel.list.count() == 1
        item = panel.list.item(0)
        assert item.text() == "(2) Ein Objekt steht über den Bauraum hinaus."
        assert item.data(_BODIES_ROLE) == ("obj_1", "obj_2")
        assert "obj_1" in item.toolTip() and "obj_2" in item.toolTip()
    finally:
        panel.deleteLater()


def test_a_finding_says_in_its_line_what_it_is_about() -> None:
    """§17.3: „Zwei Objekte überschneiden sich" — welche zwei?

    Die Antwort stand schon in ``values``, aber nur im Tooltip: man musste
    wissen, dass dort etwas ist, und mit der Maus hinfahren. Ein Bericht, den
    man abfährt, um ihn zu lesen, wird nicht gelesen.
    """
    from app.ui.panels import _line_for

    finding = Finding(
        code="arrange.collision",
        severity="warning",
        message="Zwei Objekte überschneiden sich.",
        values={"a": "Gehäuse", "b": "Deckel", "shared": "12,40 mm³", "checked": "exact"},
    )

    line = _line_for(finding)
    assert "Gehäuse" in line and "Deckel" in line
    assert "12,40 mm³" in line, "und wie viel — ein Streifschuss ist kein Problem"
    assert "exact" not in line, "das Verfahren gehört in den Tooltip, nicht in die Zeile"


def test_a_finding_without_values_stays_as_it_is() -> None:
    """Kein Gedankenstrich ohne etwas dahinter."""
    from app.ui.panels import _line_for

    finding = Finding(code="ingest.welded", severity="info", message="Doppelte Punkte verschweißt.")

    assert _line_for(finding) == "Doppelte Punkte verschweißt."


def test_an_orphaned_feature_keeps_its_internal_name_in_details_only(
    qt_app: QApplication,
) -> None:
    """Einsteiger lesen Wirkung und Ausweg, die Diagnose behält die Kennung.

    „Merkmal face_3 hat keinen Nachfolger" beschreibt die interne Zuordnung
    statt der Folge für den Nutzer. Die Kennung bleibt im Tooltip und in der
    zugänglichen Beschreibung erreichbar; die sichtbare Zeile nennt Körper,
    Wirkung, nächsten Klick und dass die Bearbeitung erhalten ist.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    finding = Finding(
        code="perceive.orphaned",
        severity="info",
        message="Ein Formdetail ist nach diesem Schritt nicht mehr automatisch wiederzuerkennen.",
        object_id="obj_1",
        values={"feature": "face_3"},
    )
    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(
                scene=Scene(report=Report(findings=(finding,))),
                object_names={"obj_1": "Halter"},
            )
        )
        item = panel.list.item(0)
        assert "Formdetail" in item.text() and "Halter" in item.text()
        assert "Anklicken zeigt den Körper und den Schritt" in item.text()
        assert "Bearbeitung bleibt erhalten" in item.text()
        assert "Merkmal" not in item.text() and "Nachfolger" not in item.text()
        assert "face_3" not in item.text(), "interne Kennungen sind keine Kundensprache"
        assert "face_3" in item.toolTip()
        assert "face_3" in str(item.data(Qt.ItemDataRole.AccessibleDescriptionRole))
    finally:
        panel.deleteLater()


def test_a_mended_defect_keeps_its_internal_name_in_details_only(
    qt_app: QApplication,
) -> None:
    """Eine geschlossene Fehlstelle ist Wirkung, nicht `edge_loop_7`."""
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    finding = Finding(
        code="perceive.mended",
        severity="info",
        message="Eine offene Stelle ist geschlossen und damit fort.",
        object_id="obj_1",
        values={"feature": "edge_loop_7"},
    )
    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(
                scene=Scene(report=Report(findings=(finding,))),
                object_names={"obj_1": "Halter"},
            )
        )
        item = panel.list.item(0)
        assert "Halter" in item.text()
        assert "Merkmal" not in item.text() and "edge_loop_7" not in item.text()
        assert "edge_loop_7" in item.toolTip()
        assert "edge_loop_7" in str(item.data(Qt.ItemDataRole.AccessibleDescriptionRole))
    finally:
        panel.deleteLater()


def test_a_part_that_fits_gets_told_so(window: MainWindow) -> None:
    """§2.7: eine Handlung endet in einer Aussage, auch wenn nichts zu tun war.

    Der Kern sagt es sauber — ``transaction is None`` —, und das Fenster macht
    daraus einen Satz. Getestet war er bis hierher nicht, hätte also jederzeit
    verschwinden können; wer *Automatisch teilen* auf ein passendes Teil
    anwendet, stünde dann vor einem unveränderten Fenster und müsste raten, ob
    die Funktion kaputt ist oder das Teil in Ordnung.

    Die geladene Platte ist 80 × 50 × 8 mm und passt auf jedes Bett dieser
    Startbestückung.
    """
    window.action_auto_split("obj_1")
    window.session.wait_for_idle()
    window.wait_for_workers()

    assert "passt bereits" in window.status_message.text()


def test_a_right_click_opens_the_menu_and_a_drag_does_not() -> None:
    """§18.5: Weg 1 zeigt auf die Stelle, die stört — der Rechtsklick antwortet.

    Ein fremdes Modell wird angepasst, indem man auf die Stelle zeigt, die
    stört. Bis hierher zeigte ein Rechtsklick auf einen Körper gar nichts — das
    Menü gab es nur im Objektbaum, wo die Merkmale ``hole_3`` heißen.

    In jedem Schema tut die rechte Taste aber auch etwas an der Kamera: ein Zug
    meint sie, ein Klick meint das, worauf er zeigt. Sonst ginge nach jedem
    Drehen ein Menü auf.
    """
    from app.ui.render.navigator import is_click

    assert is_click((100, 200), (100, 200)), "stillgehalten ist ein Klick"
    assert is_click((100, 200), (101, 199)), "eine Maus steht beim Drücken selten ganz still"
    assert is_click((100, 200), (105, 204)), (
        "fünf Pixel Wandern sind beim Klicken normal — bis zum 23.08.2026 fiel dabei "
        "die Auswahl aus"
    )
    assert not is_click((100, 200), (160, 240)), "ein Zug öffnet kein Menü"
    assert not is_click((100, 200), (100, 240)), "auch senkrecht gezogen ist gezogen"
    assert not is_click(None, (100, 200)), "ohne Druck davor gibt es nichts zu beenden"


def test_fitting_measures_the_bodies_not_the_build_volume(window: MainWindow) -> None:
    """§18.1: „Alles einpassen" meint die Körper.

    Ein Kamera-Reset ohne übergebene Grenzen nimmt alle Szenenelemente, auch
    den Rahmen des Bauraums. Bei einem 80-mm-Teil in einem 256er Bauraum füllte
    damit die Kulisse das Bild — der Befehl tat sichtbar nichts, weil schon
    eingepasst war.
    """
    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    box = entry.mesh.bounds

    bounds = window.viewport._object_bounds()
    assert bounds is not None
    assert bounds == (
        box.minimum[0],
        box.maximum[0],
        box.minimum[1],
        box.maximum[1],
        box.minimum[2],
        box.maximum[2],
    )


def test_an_empty_scene_still_shows_the_build_volume(qt_app: QApplication) -> None:
    """Ohne Körper ist der Bauraum das Einzige, was es zu sehen gibt."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        assert viewport._object_bounds() is None
    finally:
        viewport.deleteLater()


def test_the_camera_is_fitted_once_and_then_left_alone(window: MainWindow) -> None:
    """Ein Zoom überlebt die nächste Auswahl.

    Die Ansicht wird bei jeder Änderung neu aufgebaut; unter PyVista, bis
    05.09.2026, setzte der Renderer die Kamera zurück, sobald er den ersten
    Aktor bekam, und nach dem Leerräumen war jeder Körper der erste. Damit
    sprang die Ansicht bei jedem Klick auf Anfang.
    """
    result = window.session.last_result
    window.viewport.show_scene(result)
    assert window.viewport._fitted_to == "objects", "das geöffnete Projekt steht im Bild"

    window.viewport.show_scene(result)
    assert window.viewport._fitted_to == "objects", "und der nächste Aufbau passt nicht erneut ein"

    window.viewport.show_scene(None)
    assert window.viewport._fitted_to == "bed", (
        "eine leere Szene macht den Weg für das nächste Projekt frei"
    )


def test_fitting_frames_the_bodies_with_air(window: MainWindow) -> None:
    """Eingepasst wird auf die Körper, **mit Luft**: genau auf die Grenzen
    berührte ein 40 mm großer Quader links und rechts den Bildrand."""
    from app.ui.viewport import with_margin

    window.viewport.show_scene(window.session.last_result)
    renderer = RecordingRenderer()
    window.viewport.renderer = renderer

    window.viewport.reset_camera()

    bounds = window.viewport._object_bounds()
    assert bounds is not None
    assert renderer.reset_bounds == [with_margin(bounds)], "auf die Körper, mit Luft darum"


def test_a_problem_note_stays_inside_the_legend_layout(qt_app: QApplication) -> None:
    """Der Problemsatz der Legende stand außerhalb jeder Anordnung.

    ``show_map`` nimmt beim Aufräumen **jedes** Element aus dem Layout — auch
    die Notiz (geschützt war nur ihr Löschen) — und hängte sie nur im
    Erfolgsfall wieder ein. „Die Analysekarte wird berechnet …" und „… zu
    groß" standen damit auf 100 × 30 Punkten Geometrie irgendwo im Nichts
    (Gesamtreview 25.08.2026, I-9). Geprüft wird die Zugehörigkeit zum
    Layout — Sichtbarkeit lügt offscreen.
    """
    from app.ui.analysis_bar import AnalysisBar

    bar = AnalysisBar(None)
    try:
        legend = bar.legend

        bar.show_problem("Für eine Analysekarte ist dieses Modell zu groß.")
        assert legend._layout.indexOf(legend.note) >= 0, "der Problemsatz braucht sein Layout"

        bar.show_legend(None)
        assert legend._layout.indexOf(legend.note) >= 0, "auch beim Leeren"
    finally:
        bar.deleteLater()


def test_an_axis_view_turns_around_the_current_focus(window: MainWindow) -> None:
    """Strg+0 bis Strg+6 drehen die Kamera um den Blickpunkt, sie rahmen nicht.

    Wer in eine Bohrung hineingezoomt hat und „Oben" drückt, will diese
    Bohrung von oben sehen. Bis zum 07.09.2026 stellte ``view_from`` die
    Kamera auf den Ursprung und passte die ganze Szene neu ein — der Zoom war
    weg, und das Einpassen gehört zu Pos1 (Entscheidung Robert, wie in
    Assist). Geprüft: Fokus und Abstand bleiben, die Richtung ist die der
    Vorgabe, und der Renderer wird nicht zum Einpassen gerufen — auch bei
    der Iso, deren Richtungsvektor nicht auf Länge eins steht.
    """
    import math

    from app.ui.render.api import CameraPose

    window.viewport.show_scene(window.session.last_result)
    renderer = RecordingRenderer()
    focus = (10.0, 20.0, 5.0)
    renderer.pose = CameraPose((40.0, -20.0, 5.0), focus, (0.0, 0.0, 1.0))
    window.viewport.renderer = renderer
    window.viewport._shadow_hulls.clear()

    window.viewport.view_from("top")

    assert renderer.reset_bounds == [], "eine Kameravorgabe passt nicht ein"
    assert tuple(renderer.pose.focal_point) == pytest.approx(focus), "der Blickpunkt bleibt"
    assert tuple(renderer.pose.position) == pytest.approx((10.0, 20.0, 55.0)), (
        "fünfzig Millimeter über dem Blickpunkt — der alte Abstand, die neue Richtung"
    )
    assert tuple(renderer.pose.view_up) == pytest.approx((0.0, 1.0, 0.0))

    window.viewport.view_from("iso")

    assert renderer.reset_bounds == []
    assert tuple(renderer.pose.focal_point) == pytest.approx(focus)
    assert math.dist(tuple(renderer.pose.position), focus) == pytest.approx(50.0), (
        "der Abstand wächst nicht mit der Länge des Iso-Vektors"
    )


def test_an_empty_scene_still_fits_on_something(window: MainWindow) -> None:
    """Ohne Körper bleibt der Bauraum das Maß — dann ist er das Einzige, was
    es zu sehen gibt.

    **Gerechnet wird er hier selbst**, statt ``reset_camera()`` ohne Grenzen zu
    rufen und den Renderer alle Szenenelemente suchen zu lassen. Zwei Gründe: nur so bekommt
    auch die leere Szene ihre Luft, und nur so hängt das Ergebnis nicht daran,
    welche Kulisse gerade zusätzlich im Bild steht. Ohne Grenzen rutschte die
    Platte ins untere Drittel und teilweise hinter die Werkzeugzeile.
    """
    from app.ui.viewport import with_margin

    window.viewport.show_scene(None)
    renderer = RecordingRenderer()
    window.viewport.renderer = renderer

    window.viewport.reset_camera()

    volume = window.viewport._volume_bounds()
    assert volume is not None, "das Fenster hat ein Profil, also gilt ein Bauraum"
    assert renderer.reset_bounds == [with_margin(volume)]


def test_a_new_project_puts_the_build_volume_in_the_picture(window: MainWindow) -> None:
    """Nach *Neues Projekt* muss die Druckplatte zu sehen sein.

    Sie war es nicht: eingepasst wurde nur, wenn Körper da waren, und die
    Startkamera stand aus dem Aufbau heraus auf (1, -1, 0,8) — anderthalb
    Millimeter vom Ursprung entfernt, während der Bauraum 220 mm misst. Wer
    ein neues Projekt anlegte, sah eine leere Fläche und musste Pos1 drücken,
    um zu erfahren, dass alles in Ordnung ist.

    Geprüft wird ``_fit_once_for`` und nicht ``show_scene``: die Entscheidung
    fällt dort, und der aufzeichnende Renderer kennt nur ``reset_camera``.
    """
    viewport = window.viewport
    viewport.show_scene(window.session.last_result)
    assert viewport._fitted_to == "objects"

    renderer = RecordingRenderer()
    viewport.renderer = renderer
    # In derselben Reihenfolge wie ``show_scene``: erst steht die neue Szene,
    # dann wird eingepasst. Andersherum misst ``reset_camera`` die Körper der
    # vorigen und passt auf etwas ein, das nicht mehr da ist.
    viewport._result = None
    viewport._fit_once_for(None)

    from app.ui.viewport import with_margin

    volume = viewport._volume_bounds()
    assert volume is not None
    assert renderer.reset_bounds == [with_margin(volume)], (
        "die leere Szene passt auf den Bauraum ein"
    )
    assert viewport._bed_extent is not None, "der Bauraum gilt auch ohne Renderfläche"
    assert viewport._fitted_to == "bed"

    renderer.reset_bounds.clear()
    viewport._fit_once_for(None)
    assert renderer.reset_bounds == [], "der nächste leere Aufbau lässt die Kamera in Ruhe"


def test_a_scene_that_outgrows_the_view_gets_fitted_again() -> None:
    """Der Sprung ist etwas anderes als die Feinarbeit.

    „Jeder weitere Aufbau lässt die Kamera in Ruhe" schützt den Zoom, und das
    bleibt so: Wer heranzoomt und eine Bohrung setzt, will seinen Zoom behalten.
    Aufgenommen am laufenden Fenster war aber auch der andere Fall zu sehen: In
    ein Teil von zwei Millimetern hineingezoomt und einen 400er Körper dazu
    erzeugt — die Kamera stand in dessen Innerem, und zu sehen war eine
    dunkelrote Fläche. Der Prüfbericht warnte richtig, das Bild sagte nichts.

    Geprüft wird die Entscheidung als reine Funktion: offscreen gibt es keinen
    Renderer, und was nur im Zeichnen steht, prüft niemand.
    """
    from app.ui.viewport import OUTGROWN_FACTOR, diagonal_of, outgrown

    tiny = (-1.0, 1.0, -1.0, 1.0, 0.0, 1.0)
    huge = (-200.0, 200.0, -150.0, 150.0, 0.0, 250.0)
    aside = (500.0, 520.0, 500.0, 520.0, 0.0, 20.0)
    nearby = (-2.0, 2.0, -2.0, 2.0, 0.0, 2.0)

    assert outgrown(tiny, huge), "gewachsen: die Kamera steht im neuen Körper"
    assert diagonal_of(huge) > OUTGROWN_FACTOR * diagonal_of(tiny), "und zwar deutlich"
    assert outgrown(tiny, aside), "weggerückt: das Modell liegt außerhalb des Bildes"

    assert not outgrown(tiny, nearby), "das Doppelte ist Feinarbeit — der Zoom bleibt"
    assert not outgrown(huge, tiny), "was kleiner wird, zieht die Kamera nicht an sich"
    assert not outgrown(None, huge), "ohne Vorher gibt es nichts zu vergleichen"
    assert not outgrown(huge, None), "und ohne Körper nichts einzupassen"


def test_a_body_the_user_dragged_leaves_the_camera_alone() -> None:
    """Wer selbst schiebt, behält seine Ansicht (§2.9).

    **Robert am 23.08.2026**, nachdem er einen Körper über die Platte gezogen
    hatte: „nach jedem verschieben springt die kamera und das modell immer
    komisch … kamera bei aktueller position dann immer lassen."

    Der Grund lag im zweiten Kriterium von :func:`outgrown` — *weggerückt*.
    Es ist für ein Modell gedacht, das außerhalb des Bildes liegt, und trifft
    auf jeden geschobenen Körper zu: Beim Loslassen rahmte die Kamera neu.

    **Das Größenkriterium gilt weiter**, und das ist die Grenze der Regel: Ein
    Körper, der beim Schieben plötzlich zwanzigmal so groß dasteht, ist kein
    Schieben mehr.
    """
    from app.ui.viewport import outgrown

    fitted = (-10.0, 10.0, -10.0, 10.0, 0.0, 20.0)
    dragged = (100.0, 120.0, 100.0, 120.0, 0.0, 20.0)
    grown = (-200.0, 200.0, -200.0, 200.0, 0.0, 250.0)

    assert outgrown(fitted, dragged), "ohne die Unterscheidung rahmt jedes Ziehen neu"
    assert not outgrown(fitted, dragged, moved_only=True), "geschoben heißt: Ansicht bleibt"
    assert outgrown(fitted, grown, moved_only=True), "gewachsen bleibt gewachsen"


def test_the_camera_follows_a_body_that_dwarfs_the_scene(window: MainWindow) -> None:
    """Dieselbe Sache am Fenster: erst eingepasst, dann entwachsen.

    Die Blickrichtung bleibt dabei, wo sie war — ``reset_camera`` rahmt neu und
    dreht nichts.
    """
    viewport = window.viewport
    viewport.show_scene(window.session.last_result)
    assert viewport._fitted_to == "objects"
    assert viewport._fitted_bounds is not None, "worauf eingepasst wurde, wird gemerkt"

    renderer = RecordingRenderer()
    viewport.renderer = renderer
    viewport._fit_once_for(window.session.last_result)
    assert renderer.reset_bounds == [], "derselbe Stand lässt die Kamera in Ruhe"

    # Die Szene wächst: derselbe Zustand „objects", aber ein Vielfaches groß.
    viewport._fitted_bounds = (-1.0, 1.0, -1.0, 1.0, 0.0, 1.0)
    viewport._fit_once_for(window.session.last_result)
    assert renderer.reset_bounds, "der Sprung wird neu gerahmt"


def test_a_fresh_split_asks_the_view_to_frame_all_parts(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-269 (4), KUNDE-11: Wer die Teile einer Teilung aufzieht, rahmt sie auch.

    Die Rahmung selbst prüft ``test_viewport_decisions``
    (``test_a_fresh_split_is_framed_once_with_all_its_parts``); hier der Draht:
    Das Aufziehen nach einer Teilung bittet die Ansicht darum, und zwar vor dem
    Auseinanderziehen, dessen Aufbau die Rahmung einlöst.
    """
    from types import SimpleNamespace

    order: list[str] = []
    monkeypatch.setattr(window.viewport, "frame_next_scene", lambda: order.append("frame"))
    monkeypatch.setattr(window.explode_bar, "reveal", lambda: order.append("reveal"))
    parts = SimpleNamespace(scene=SimpleNamespace(objects={"obj_2": None, "obj_3": None}))

    window._pending_split_reveal = frozenset({"obj_2", "obj_3"})
    window._reveal_split_result(parts)  # type: ignore[arg-type]

    assert order == ["frame", "reveal"]


def test_the_build_volume_is_a_hint_not_a_cage() -> None:
    """Als geschlossener Drahtkasten war die Oberkante aus der Vorgabeansicht
    eine große Raute weit über dem Bett — und das Teil darunter ein Fleck.

    Gebraucht wird zweierlei: wie hoch darf es werden, und wo hört die Fläche
    auf. Vier senkrechte Ecken und je zwei kurze Winkel oben tragen beides.
    """
    from app.ui.viewport import CORNER_FRACTION, volume_edges

    segments = volume_edges(200.0, 100.0, 250.0)
    assert len(segments) == 12, "vier Ecken mit je einer Senkrechten und zwei Winkeln"

    uprights = [pair for pair in segments if pair[0][2] != pair[1][2]]
    assert len(uprights) == 4
    for start, end in uprights:
        assert (start[2], end[2]) == (0.0, 250.0), "vom Bett bis nach oben"

    top = [pair for pair in segments if pair[0][2] == pair[1][2] == 250.0]
    assert len(top) == 8, "zwei Arme je Ecke, keine durchgehende Kante"
    for start, end in top:
        length = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
        assert length in (200.0 * CORNER_FRACTION, 100.0 * CORNER_FRACTION)
        # Nach innen: außerhalb der Fläche hätten sie nichts zu begrenzen.
        assert abs(end[0]) <= abs(start[0]) and abs(end[1]) <= abs(start[1])


def test_the_gizmo_axes_say_which_is_which() -> None:
    """Regel 18: Rot, Grün und Blau waren die einzige Unterscheidung.

    Wer die drei Farben nicht trennt, sah drei gleiche Pfeile — und der Gizmo
    ist das Werkzeug, mit dem man ein Teil bewegt, also ist „welche Achse" die
    einzige Frage, die er beantworten muss.
    """
    from app.ui.viewport import GIZMO_LABEL_GAP, gizmo_labels

    marks = gizmo_labels((10.0, 20.0, 30.0), 50.0)
    assert [text for _point, text in marks] == ["X", "Y", "Z"]

    reach = 50.0 * GIZMO_LABEL_GAP
    assert marks[0][0] == (10.0 + reach, 20.0, 30.0)
    assert marks[1][0] == (10.0, 20.0 + reach, 30.0)
    assert marks[2][0] == (10.0, 20.0, 30.0 + reach)
    assert reach > 50.0, "hinter der Spitze, nicht auf ihr — dort will man greifen"


def test_the_gizmo_labels_follow_the_body() -> None:
    """Der Griff sitzt am Objekt, also auch seine Beschriftung."""
    from app.ui.viewport import gizmo_labels

    near = gizmo_labels((0.0, 0.0, 0.0), 10.0)
    far = gizmo_labels((100.0, 0.0, 0.0), 10.0)
    assert far[0][0][0] - near[0][0][0] == 100.0


def test_the_gizmo_is_big_enough_to_grab() -> None:
    """pyvistas Vorgaben ergaben auf einem 80-mm-Teil ein Gebilde aus dünnen
    Linien von etwa vierzig Bildpunkten."""
    from app.ui.viewport import GIZMO_LINE_RADIUS, GIZMO_SCALE

    assert GIZMO_SCALE > 0.15, "die Vorgabe von pyvista"
    assert GIZMO_LINE_RADIUS > 0.02, "und ihre Strichstärke"


def _gizmo_viewport() -> tuple[Any, RecordingRenderer]:
    """Ein Viewport mit Renderer-Doppel und zwei Körpern im Bild.

    Zwanzig Bildpunkte je Millimeter, damit der Deckel des Griffs in
    Bildpunkten (``GIZMO_LEAST_PIXELS``) nicht greift und der Griff die Größe
    des Gewählten nimmt.
    """
    import numpy as np

    from app.ui.render import shapes
    from app.ui.viewport import Viewport

    viewport = Viewport()
    renderer = RecordingRenderer(scale=20.0)
    viewport.renderer = renderer
    vertices, _faces = shapes.cube((0.0, 0.0, 5.0), 10.0)
    viewport._actors = {
        "obj_1": RecordingItem("object:obj_1", np.asarray(vertices), "#b9c4d0"),
        "obj_2": RecordingItem(
            "object:obj_2", np.asarray(vertices) + np.array([30.0, 0.0, 0.0]), "#b9c4d0"
        ),
    }
    return viewport, renderer


def test_the_gizmo_comes_off_again(qt_app: QApplication) -> None:
    """Abschalten nimmt den Griff aus dem Bild — Pfeile, Ringe, Würfel, Buchstaben."""
    viewport, renderer = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        gizmo = viewport._gizmo
        assert gizmo is not None
        parts = list(gizmo.items)
        assert len(parts) == 6, "drei Pfeile, drei Ringe"

        viewport.set_gizmo(False)
        assert viewport._gizmo is None
        assert all(part in renderer.removed for part in parts), "der Griff geht aus dem Bild"
    finally:
        viewport.deleteLater()


def test_the_gizmo_follows_the_selection(qt_app: QApplication) -> None:
    """§18.11: wer ein anderes Objekt wählt, will es auch bewegen — nicht das
    vorige. Und ohne Auswahl bleibt die Entscheidung, nur der Griff geht."""
    viewport, renderer = _gizmo_viewport()
    try:
        viewport.set_gizmo(True)
        assert viewport._gizmo is None, "ohne Auswahl gibt es nichts zu greifen"

        viewport.select("obj_1")
        first = viewport._gizmo
        assert first is not None, "die Auswahl bringt den Griff mit"
        assert first.target is viewport._actors["obj_1"]
        first_parts = list(first.items)

        viewport.select("obj_2")
        assert all(part in renderer.removed for part in first_parts), "der alte Griff geht weg"
        assert viewport._gizmo is not None
        assert viewport._gizmo.target is viewport._actors["obj_2"], "der neue sitzt am neuen"

        viewport.select(None)
        assert viewport._gizmo is None
        assert viewport._gizmo_wanted, "die Entscheidung bleibt — nur der Griff geht"
    finally:
        viewport.deleteLater()


def test_a_new_grip_leaves_no_letters_of_the_old_one(qt_app: QApplication) -> None:
    """Jeder Aufbau des Griffs räumt die Buchstaben des vorigen ab — nicht nur
    der am Langloch.

    **Roberts Bild** (11.09.2026: „die ganzen weißen symbole im viewport … sind
    komisch"): ein Dutzend ``<->`` über einem Schriftzug, eines je Fläche, die
    er im Objektbaum angeklickt hatte. Seit 462be2f5 stand
    ``_drop_gizmo_labels`` im Zweig des Langlochgriffs, und ohne Langloch
    blieb die Beschriftung jedes vorigen Griffs stehen. Gemessen wird am
    Renderer-Doppel: Nach dem zweiten Aufbau steht genau **eine**
    Beschriftung im Bild, die erste ist entfernt.
    """
    viewport, renderer = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        first = viewport._gizmo_labels
        assert first is not None

        viewport.select("obj_2")
        second = viewport._gizmo_labels
        assert second is not None and second is not first, "der neue Griff hat neue Buchstaben"
        assert first in renderer.removed, "die alten sind aus dem Bild"
        standing = [
            entry["item"]
            for entry in renderer.entries("gizmo_labels")
            if entry["item"] not in renderer.removed
        ]
        assert standing == [second], f"im Bild steht eine Beschriftung, nicht {len(standing)}"
    finally:
        viewport.deleteLater()


def test_a_drag_below_the_snap_leaves_no_ghost(qt_app: QApplication) -> None:
    """Ein Zug unter der Fangschwelle erzeugt keine Operation — dann darf er
    auch keinen versetzten Griff hinterlassen: Er wird frisch angehängt."""
    from app.core.geom.transform import translation

    viewport, renderer = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        viewport.set_snapping(1.0, 15.0)
        first = viewport._gizmo
        assert first is not None
        first_parts = list(first.items)
        dragged: list[object] = []
        viewport.transformDragged.connect(dragged.append)

        viewport._on_gizmo_released(translation((0.4, 0.0, 0.0)))
        assert dragged == [], "0,4 mm bei 1 mm Raster ist kein Zug"
        assert all(part in renderer.removed for part in first_parts), (
            "der Griff wird frisch angehängt"
        )
        assert viewport._gizmo is not None
        assert viewport._gizmo is not first, "mit leerer Matrix statt der alten"

        second = viewport._gizmo
        second_parts = list(second.items)
        viewport._on_gizmo_released(translation((5.0, 0.0, 0.0)))
        assert len(dragged) == 1, "ein echter Zug kommt als Schritte an"
        assert all(part in renderer.removed for part in second_parts)
        assert viewport._gizmo is not second
    finally:
        viewport.deleteLater()


def test_the_axis_letters_travel_with_the_drag(qt_app: QApplication) -> None:
    """Regel 18 gilt auch während des Zugs, nicht nur davor und danach.

    Die Buchstaben standen fest an der Startposition — je weiter man zog,
    desto weiter lag das X von dem Pfeil weg, den es benennt. Jetzt hängen
    sie an einem lebenden PolyData, und jedes Move-Ereignis versetzt dessen
    Punkte um die Matrix des Zugs.
    """
    import numpy as np

    from app.core.geom.transform import rotation, translation
    from app.ui.viewport import moved_marks

    # Die reine Rechnung: verschieben verschiebt, drehen dreht um den Ursprung.
    base = np.array([[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]])
    shifted = moved_marks(base, translation((5.0, 0.0, 0.0)))
    assert shifted[0] == pytest.approx((15.0, 0.0, 0.0))
    turned = moved_marks(base, rotation("z", 90.0))
    assert turned[0] == pytest.approx((0.0, 10.0, 0.0), abs=1e-9), "X-Marke wandert auf die Y-Achse"

    # Und am Griff: die Punkte hinter der Beschriftung folgen dem Ereignis.
    viewport, renderer = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        labels = viewport._gizmo_labels
        assert labels is not None and viewport._gizmo_label_base is not None
        assert viewport._gizmo_label_texts == ["X", "Y", "Z", "S"], "X, Y, Z und das S des Würfels"
        before = viewport._gizmo_label_base.copy()

        viewport._on_gizmo_interacted(translation((7.0, 0.0, 0.0)))
        after = renderer.item_of("gizmo_labels").points
        assert after[:, 0] == pytest.approx(before[:, 0] + 7.0)

        viewport.set_gizmo(False)
        assert viewport._gizmo_labels is None, "mit dem Griff gehen auch die Buchstaben"
        assert labels in renderer.removed
    finally:
        viewport.deleteLater()


def test_the_scale_factor_is_the_ratio_of_distances() -> None:
    """§18.11 nennt Verschieben, Drehen und Skalieren — der Faktor eines
    Zugs ist Ist-Abstand durch Start-Abstand, eingespannt gegen Ausrutscher.
    """
    from app.ui.scale_widget import FACTOR_RANGE, dragged_factor, ray_plane_hit

    centre = (0.0, 0.0, 0.0)
    assert dragged_factor(centre, (10.0, 0.0, 0.0), (15.0, 0.0, 0.0)) == pytest.approx(1.5)
    assert dragged_factor(centre, (10.0, 0.0, 0.0), (5.0, 0.0, 0.0)) == pytest.approx(0.5)
    assert dragged_factor(centre, (10.0, 0.0, 0.0), (10.0, 0.0, 0.0)) == pytest.approx(1.0)

    # Eingespannt: durchs Zentrum gezogen heißt nicht „auf null geschrumpft".
    assert dragged_factor(centre, (10.0, 0.0, 0.0), (0.0, 0.0, 0.0)) == FACTOR_RANGE[0]
    assert dragged_factor(centre, (0.1, 0.0, 0.0), (1000.0, 0.0, 0.0)) == FACTOR_RANGE[1]
    # Ein Start im Zentrum wäre eine Division durch null — er zieht nichts.
    assert dragged_factor(centre, (0.0, 0.0, 0.0), (5.0, 0.0, 0.0)) == 1.0

    # Der Strahl auf die Kameraebene: senkrecht getroffen, parallel nichts.
    hit = ray_plane_hit((0.0, 0.0, 10.0), (0.0, 0.0, -1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    assert hit == pytest.approx((0.0, 0.0, 0.0))
    assert (
        ray_plane_hit((0.0, 0.0, 10.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)) is None
    )


def test_the_scale_handle_lives_and_dies_with_the_gizmo(qt_app: QApplication) -> None:
    """Der Würfel gehört zum Griffsatz: er kommt am Objekt, fehlt an der
    Fläche, und beim Abschalten meldet er seine Beobachter wieder ab.

    Ein vergessener Beobachter zöge am Griff der vorigen Auswahl weiter —
    dieselbe Familie Fehler wie das Widget, das nie abgeschaltet wurde.
    """
    from app.core.types import Feature

    viewport, renderer = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        handle = viewport._scale_handle
        assert handle is not None, "am Objekt gibt es den Würfel"
        assert handle.item in renderer.items and handle.item not in renderer.removed
        assert viewport._gizmo_label_texts == ["X", "Y", "Z", "S"], "X, Y, Z — und S"

        viewport.set_gizmo(False)
        assert viewport._scale_handle is None
        assert handle.item in renderer.removed, "der Würfel geht mit dem Griff"

        # An der Fläche gibt es keinen Würfel: sie kennt nur vor und zurück.
        face = Feature(
            id="face_1",
            kind="face",
            provenance="detected",
            params={"normal": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 5.0)},
        )
        # **Beide Attrappen**, seit ``set_gizmo`` zwei Fragen stellt: wo der
        # Griff *sitzt* (``gizmo_feature``, jedes versetzbare Merkmal) und was
        # er *tut* (``gizmo_target``, nur die Fläche mit Press/Pull). Nur die
        # zweite zu setzen liess die erste die echte Auswahl lesen — leer —,
        # und der Würfel kam an einer Fläche zurück, an der er nichts zu
        # suchen hat.
        viewport.gizmo_feature = lambda: face  # type: ignore[method-assign]
        viewport.gizmo_target = lambda: face  # type: ignore[method-assign]
        viewport.set_gizmo(True)
        assert viewport._scale_handle is None, "eine Fläche hat keine Größe zu ändern"
        # **Eine Marke und nicht drei**, seit die Beschriftung sagt, was der
        # Griff an einer Fläche kann: vor und zurück. Drei Achsenbuchstaben
        # versprachen dort drei Richtungen, von denen zwei verfallen — wer
        # nicht aus dem CAD kommt, zieht in eine davon und sieht nichts
        # passieren. Der Name der Fläche steht in der Statusleiste, wo Qt
        # zeichnet: Die Flächennamen werden übersetzt, und ein übersetzter
        # Text am Griff stünde in sechs Sprachen an einer Stelle, die keine
        # Prüfung sieht (``FACE_ARROW``).
        assert viewport._gizmo_label_texts == ["<->"], "an der Fläche eine Richtung"
    finally:
        viewport.deleteLater()


def test_a_scale_drag_becomes_an_operation(qt_app: QApplication) -> None:
    """Loslassen am Würfel meldet den Faktor — ein Zug, eine Operation,
    ein Undo (§18.11, §2.1). Ein Faktor von eins meldet nichts.
    """
    viewport, renderer = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        first = viewport._gizmo
        assert first is not None
        first_parts = list(first.items)
        factors: list[float] = []
        viewport.scaleDragged.connect(factors.append)

        viewport._on_scale_released(1.00001)
        assert factors == [], "wer nicht gezogen hat, hat nichts skaliert"
        assert all(part in renderer.removed for part in first_parts)
        assert viewport._gizmo is not first, "der Griffsatz ist frisch"

        viewport._on_scale_released(1.5)
        assert factors == [1.5]
    finally:
        viewport.deleteLater()


def test_the_drag_shows_its_number_while_it_runs(qt_app: QApplication) -> None:
    """§18.11: die Zahl zum Zug — lesbar, während gezogen wird.

    Wie weit man gezogen hatte, stand bis dahin erst hinterher im Verlauf.
    Jetzt füttert jedes Move-Ereignis das Feld über dem Bild: Achse und
    Millimeter beim Verschieben, Achse und Grad beim Drehen, der Faktor am
    Würfel — und solange niemand tippt, folgt das Feld dem Zeiger.
    """
    from app.core.geom.transform import rotation, translation

    viewport, _renderer = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)

        viewport._on_gizmo_interacted(translation((3.4, 0.0, 0.0)))
        assert viewport._drag_kind == "move"
        assert viewport._drag_axis == "x"
        # isHidden statt isVisible: offscreen ist der Viewport selbst nie
        # sichtbar, und ein Kind erbt das — gefragt ist, ob das Feld gezeigt
        # würde, nicht ob der Testlauf ein Fenster hat.
        assert not viewport.drag_bar.isHidden()
        assert viewport.drag_bar.value.text() == "3,40"

        viewport._on_gizmo_interacted(rotation("z", 30.0))
        assert viewport._drag_kind == "turn"
        assert viewport.drag_bar.value.text() == "30,0"
        assert viewport.drag_bar.unit.text() == "°"

        viewport._on_scale_interacted(1.375)
        assert viewport._drag_kind == "scale"
        assert viewport.drag_bar.value.text() == "1,375"

        # Sobald getippt wurde, gehört das Feld der Tastatur.
        viewport.drag_bar.typing = True
        viewport.drag_bar.value.setText("2")
        viewport._on_scale_interacted(1.8)
        assert viewport.drag_bar.value.text() == "2", "der Zeiger überschreibt keine Eingabe"
    finally:
        viewport.deleteLater()


def test_a_typed_number_is_applied_exactly(qt_app: QApplication) -> None:
    """§18.11 „Zahleneingabe während des Ziehens": Enter wendet genau die
    getippte Zahl an — ohne Rasterfang, denn wer tippt, meint es exakt.
    """
    from app.core.geom.transform import translation

    viewport, _renderer = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        viewport.set_snapping(1.0, 15.0)
        dragged: list[object] = []
        viewport.transformDragged.connect(dragged.append)

        viewport._on_gizmo_interacted(translation((3.4, 0.0, 0.0)))
        viewport.drag_bar.typing = True
        viewport.drag_bar.value.setText("12,5")
        viewport._apply_typed()

        assert len(dragged) == 1
        assert dragged[0].offset == pytest.approx((12.5, 0.0, 0.0)), (
            "exakt, kein Fang auf 12 oder 13"
        )
        assert viewport._drag_kind is None, "der Zug ist damit zu Ende"
        assert viewport.drag_bar.isHidden()

        # Loslassen während des Tippens wendet nichts an — die Zahl gilt.
        viewport._on_gizmo_interacted(translation((3.4, 0.0, 0.0)))
        viewport.drag_bar.typing = True
        viewport._on_gizmo_released(translation((3.4, 0.0, 0.0)))
        assert len(dragged) == 1, "das Release hat nicht zusätzlich angewandt"
        assert viewport._drag_kind == "move", "und der getippte Zug läuft weiter"

        # Eine Zahl, mit der sich nichts anfangen lässt, wendet nichts an.
        viewport.drag_bar.value.setText("keine Zahl")
        viewport._apply_typed()
        assert len(dragged) == 1
        assert viewport._drag_kind == "move", "der Zug bleibt offen, das Feld markiert sich"

        # Esc verwirft: nichts angewandt, Zustand weg.
        viewport._end_drag()
        assert viewport._drag_kind is None
        assert len(dragged) == 1
    finally:
        viewport.deleteLater()


def test_a_typed_scale_factor_becomes_the_operation(qt_app: QApplication) -> None:
    """Auch am Würfel gilt: die getippte Zahl schlägt den Mausweg — und ein
    Faktor, der nichts ändert oder nichts übrig ließe, wird nicht angewandt.
    """
    viewport, _renderer = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        factors: list[float] = []
        viewport.scaleDragged.connect(factors.append)

        viewport._on_scale_interacted(1.4)
        viewport.drag_bar.typing = True
        viewport.drag_bar.value.setText("2,0")
        viewport._apply_typed()
        assert factors == [2.0]

        viewport._on_scale_interacted(1.4)
        viewport.drag_bar.typing = True
        viewport.drag_bar.value.setText("0")
        viewport._apply_typed()
        assert factors == [2.0], "auf null schrumpfen gibt es nicht"
        assert viewport._drag_kind == "scale", "der Zug bleibt offen"
    finally:
        viewport.deleteLater()


def test_a_drag_leaves_the_navigation_in_place(qt_app: QApplication) -> None:
    """Nach dem Loslassen gilt weiter das gewählte Schema — ohne dass jemand
    es zurückstellen müsste.

    Bis zum 05.09.2026 schaltete PyVistas Griff beim Greifen auf seinen
    Trackball und stellte beim Loslassen **seinen** Standard wieder her;
    jedes Zugende rief deshalb ``set_navigation``. Der Navigator kennt keinen
    Stilwechsel: Der Griff nimmt seine Gesten vor der Kamera, sonst nichts.
    """
    from app.core.geom.transform import translation

    viewport, _renderer = _gizmo_viewport()
    try:
        viewport.set_navigation("blender")
        navigator = viewport._navigator
        assert navigator is not None
        viewport.select("obj_1")
        viewport.set_gizmo(True)

        viewport._on_gizmo_released(translation((5.0, 0.0, 0.0)))
        assert viewport._navigator is navigator and navigator.scheme == "blender"

        viewport._on_gizmo_released(translation((0.2, 0.0, 0.0)))
        assert viewport._navigator is navigator, "auch ein Zug unter der Fangschwelle"
    finally:
        viewport.deleteLater()


def test_a_click_on_the_body_selects_it(window: MainWindow) -> None:
    """§2.9 und §18.5: „links wählt aus" muss ohne den Baum gelten.

    Vorher lief das Picking nur, wenn Messen, Bemalen oder die
    Merkmalsbeschriftung eingeschaltet waren — ein Klick auf einen Körper tat
    in der Vorgabe nichts, obwohl Schema und Handbuch es versprechen.
    """
    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    centre = entry.mesh.bounds.centre

    assert window.viewport._object_at(centre) == "obj_1"


def test_a_click_beside_the_body_clears_the_selection(window: MainWindow) -> None:
    """Ein Klick daneben ist eine Aussage, kein Beinahe-Treffer.

    ``_nearest_mesh`` antwortet immer mit dem nächsten Körper; für die Auswahl
    wäre das falsch — sonst gäbe es keinen Weg, sie ohne den Baum loszuwerden.
    """
    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    far = tuple(value + 500.0 for value in entry.mesh.bounds.centre)

    assert window.viewport._object_at(far) is None


def test_the_smallest_body_wins_when_several_overlap(window: MainWindow) -> None:
    """Wer auf eine Schraube in einem Gehäuse zeigt, meint die Schraube."""
    result = window.session.last_result
    entry = result.scene.objects["obj_1"]
    centre = entry.mesh.bounds.centre

    # Der geladene Körper allein: er ist der kleinste und damit der Treffer.
    assert window.viewport._object_at(centre) == "obj_1"


def test_a_click_ignores_hidden_bodies(window: MainWindow) -> None:
    """§18.8: Ausblenden nimmt den Körper aus dem Bild — und damit aus dem Klick.

    ``_object_at`` prüfte nur den Hüllquader: Ein Klick wählte einen
    ausgeblendeten Körper, der Objektbaum sprang dorthin, und die nächste
    Operation traf ein Teil, das niemand sieht (Gesamtreview 25.08.2026, J-1).
    ``_nearest_mesh`` hatte dieselbe Lücke — es beliefert Messen und Bemalen.
    """
    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    centre = entry.mesh.bounds.centre
    window.viewport.set_hidden(frozenset({"obj_1"}))

    assert window.viewport._object_at(centre) is None
    assert window.viewport._nearest_mesh(centre) is None


def test_a_click_ignores_bodies_of_other_plates(window: MainWindow) -> None:
    """§25: Wer eine einzelne Platte ansieht, kann nur auf ihr wählen.

    Die Körper der anderen Platten liegen in Szenenkoordinaten am selben Ort —
    genau der Grund für die Plattenverschiebung. Ohne den Filter wählte ein
    Klick das unsichtbare Teil der fremden Platte (Gesamtreview J-1).
    """
    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    centre = entry.mesh.bounds.centre
    window.viewport.set_plate(entry.plate + 1)

    assert window.viewport._object_at(centre) is None
    assert window.viewport._nearest_mesh(centre) is None


def test_clicking_needs_no_overlay_switch(window: MainWindow) -> None:
    """Die Merkmalsbeschriftung schaltet Beschriftungen, nicht das Anklicken.

    §18.5 nennt das Zeigen auf ein Merkmal die wichtigste Einzelfunktion — sie
    hinter einem Häkchen zu verstecken hieße, sie für jeden abzuschalten, der
    das Häkchen nicht findet.
    """
    window.viewport.show_scene(window.session.last_result)
    window.viewport.set_feature_overlay(False)

    assert window.viewport._feature_at(on_the_bore_wall(window, "hole_3")) == "hole_3"


def test_the_label_names_the_feature_and_its_size(window: MainWindow) -> None:
    entry = window.session.last_result.scene.objects["obj_1"]
    label = feature_label("hole_1", entry.features["hole_1"])

    assert label.startswith(f"{tr('Bohrung')} 1 · Ø"), "gelesen wird der Name, nicht die Kennung"


# --- layer analysis (§18.10) ----------------------------------------------------


def _wait_for_slice(window: MainWindow, timeout_ms: int = 20_000) -> None:
    """Wartet auf den Schichtanalyse-Arbeiter des Fensters.

    Kein `processEvents` in einer Endlosschleife: der Thread wird abgewartet
    und danach einmal die Warteschlange geleert, damit sein Signal ankommt.
    """
    worker = window._slice_worker
    if worker is not None:
        worker.wait(timeout_ms)
    application = QApplication.instance()
    if application is not None:
        application.processEvents()


def test_the_layer_tool_is_called_what_it_is(window: MainWindow) -> None:
    """Keine Vorschau: sie zeigt Geometrie, keine Werkzeugwege (§18.10).

    Die Benennung trug früher das Auswahlfeld in der Leiste selbst; seit es
    weg ist, tragen sie der Werkzeugknopf und sein Hinweis.
    """
    title = window.tools.tool_titles()["layers"]
    hint = str(window.tools.tools()["layers"].hint)

    assert "Schichten" in title
    assert "Vorschau" not in title
    assert "Vorschau" not in hint


def test_opening_the_layer_tool_is_the_only_switch(window: MainWindow) -> None:
    """Ein Umschalter, nicht zwei.

    In der Leiste stand ein Auswahlfeld mit „Keine Schichtanalyse" und
    „Schichtanalyse" — hinter dem Werkzeugknopf, der die Leiste überhaupt
    erst öffnet. Wer *Schichten* anklickte, bekam einen toten Regler und
    musste erraten, dass er daneben noch einmal einschalten muss.
    """
    select_plate(window)
    assert not window.layer_bar.enabled(), "geschlossen ist aus"

    window.tools.activate("layers")
    assert window.layer_bar.enabled(), "der Knopf schaltet die Analyse ein"

    window.tools.activate(None)
    assert not window.layer_bar.enabled(), "und wieder aus"
    assert window.layer_bar.index() == -1


def test_scrubbing_shows_one_layer(window: MainWindow) -> None:
    """Die Schichtanalyse rechnet im Arbeiter (§2.8) — die Leiste füllt sich,
    sobald sie da ist, statt das Fenster so lange anzuhalten.
    """
    select_plate(window)
    window.layer_bar.set_active(True)
    _wait_for_slice(window)

    assert window.layer_bar.slider.maximum() > 0, "the plate has layers"
    window.layer_bar.slider.setValue(3)
    assert "z" in window.layer_bar.readout.text()
    assert "Schicht" in window.layer_bar.readout.text()


def test_a_finished_worker_never_drops_its_successor(window: MainWindow) -> None:
    """Ein auslaufender Arbeiter räumt seine eigene Referenz weg — und nur die.

    Hier stand ein ``lambda: setattr(self, "_slice_worker", None)``. Wer durch
    die Schichten schiebt, startet einen zweiten Schnitt, während der erste
    noch rechnet; dessen ``finished`` löschte dann die Referenz auf den
    **laufenden zweiten**. Einen ``QThread``, den niemand mehr hält, sammelt
    der Speicherbereiniger mitsamt C++-Objekt ein — die Zugriffsverletzung ohne
    Zeile, gegen die weiter oben schon ``_retired`` geschrieben wurde.

    Geprüft wird die Identitätsprüfung, nicht das Aufräumen: gestartet wird
    keiner der beiden, sonst hinge der Test am Timing des Absturzes, den er
    verhindern soll.
    """
    from app.ui.main_window import _SliceWorker

    entry = window.session.last_result.scene.objects["obj_1"]
    first = _SliceWorker(entry, 0.2)
    second = _SliceWorker(entry, 0.2)
    window._slice_worker = second

    window._slice_worker_done(first)

    assert window._slice_worker is second, "der Vorgänger hat den Nachfolger gelöscht"

    window._slice_worker_done(second)

    assert window._slice_worker is None, "seinen eigenen räumt er sehr wohl weg"


def test_scrubbing_starts_one_worker_per_body_not_one_per_step(window: MainWindow) -> None:
    """Beim Ziehen durch die Schichten rechnet genau ein Arbeiter je Körper.

    Vorher startete jeder Schieberschritt einen weiteren, solange das Ergebnis
    noch nicht im Cache lag — an einem texturierten Netz rechnete jeder davon
    Sekunden, alle gleichzeitig, und die Anwendung stand. Wer etwas vom
    laufenden Ergebnis will, stellt sich an; die Schichtansicht steht dabei nur
    einmal in der Reihe, egal wie oft geschoben wird.
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    key = window._analysis_cache_key(entry)
    sentinel = object()
    window._slice_key = None
    window._slice_worker = sentinel
    window._slice_pending = key
    window._slice_waiters = []
    try:
        assert window._slice_of("obj_1", window._show_current_layer) is None
        assert window._slice_of("obj_1", window._show_current_layer) is None

        assert window._slice_worker is sentinel, "es wurde ein zweiter Arbeiter gestartet"
        assert window._slice_waiters == [window._show_current_layer], (
            "die Schichtansicht steht genau einmal in der Reihe"
        )
    finally:
        # Von Hand gesetzt, von Hand weggeräumt: das Platzhalter-Objekt hat
        # kein ``wait``, und die Fixture wartet am Ende auf alle Arbeiter.
        window._slice_worker = None
        window._slice_pending = None
        window._slice_waiters = []


def test_a_superseded_workers_result_is_dropped(window: MainWindow) -> None:
    """Das Ergebnis eines abgelösten Arbeiters gilt nicht mehr.

    Inzwischen rechnet ein neuer an einem anderen Körper — das alte Ergebnis
    jetzt zu übernehmen zeigte dessen Schichten und riefe Rückrufe, die auf
    den neuen warten.
    """
    from app.core.types import SliceResult

    outcome = SliceResult(layers=(), support_volume=0.0, first_layer_area=0.0, source="internal")
    window._slice_cache = None
    window._slice_key = None
    window._slice_worker = None

    window._slice_ready(
        outcome,
        window._analysis_cache_key(window.session.last_result.scene.objects["obj_1"]),
        object(),
    )

    assert window._slice_cache is None, "ein abgelöster Arbeiter schreibt keinen Cache"
    assert window._slice_key is None


def test_the_layer_analysis_takes_both_limits_from_the_material(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Testart „Anschluss": Nicht „der Kern kann es", sondern „das Fenster tut es".

    ``slice_body`` nimmt die Brückenbreite seit RM-097 als Zahl entgegen, weil
    die Schichtanalyse von Profilen entkoppelt bleibt (Regel 7). Damit steht
    und fällt die Sache an der einen Zeile, die sie hereingibt — und die ist
    von außen unsichtbar: Ohne sie rechnete das Fenster weiter, nur mit dem
    runden Millimeter aus dem Code.

    Gemessen wird an derselben Quelle, aus der schon der Überhangwinkel kommt:
    ``profiles.analysis_limits`` liefert beide Grenzen in einem Aufruf, die
    größte Mindestwand und den kleinsten Winkel der verwendeten Materialien.
    """
    from app.core.knowledge import profiles as profile_module
    from app.core.types import SliceResult
    from app.ui import main_window as module

    seen: list[tuple[float | None, float | None]] = []

    def measure(_mesh, _height, *, overhang_angle, bridge_from):
        seen.append((overhang_angle, bridge_from))
        return SliceResult(layers=(), support_volume=0.0, first_layer_area=0.0)

    monkeypatch.setattr(module, "slice_body", measure)
    entry = window.session.last_result.scene.objects["obj_1"]
    wall, angle = profile_module.analysis_limits(window.session.profile, entry)

    window._slice_of("obj_1")
    worker = window._slice_worker
    assert worker is not None and worker.wait(20_000)
    QApplication.processEvents()

    assert seen == [(angle, wall)], (
        "das Fenster gibt beide Grenzen herein — die Wand ist die Brückenbreite"
    )
    assert wall == pytest.approx(0.84), "zwei Extrusionsbahnen, nicht der runde Millimeter"


def test_when_the_slice_arrives_every_waiter_is_served_once(window: MainWindow) -> None:
    """Wer sich angestellt hat, bekommt das Ergebnis — und die Reihe ist danach leer."""
    from app.core.types import SliceResult

    outcome = SliceResult(layers=(), support_volume=0.0, first_layer_area=0.0, source="internal")
    served: list[object] = []
    current = object()
    window._slice_worker = current
    key = window._analysis_cache_key(window.session.last_result.scene.objects["obj_1"])
    window._slice_pending = key
    window._slice_waiters = [served.append]
    try:
        window._slice_ready(outcome, key, current)

        assert served == [outcome]
        assert window._slice_cache is outcome
        assert window._slice_pending is None
        assert window._slice_waiters == []
    finally:
        window._slice_worker = None


def test_scrubbing_defers_the_body_cut_until_the_slider_rests(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Beim Fahren folgen die Konturen sofort, der Körperschnitt erst zur Ruhe.

    Die Körper an der Schichthöhe zu kappen ist echte Geometrie und kostet an
    einem texturierten Netz um die Sekunde — je Schieberschritt im Hauptthread
    war das die Blockade, die §2.8 ausschließt. Ein- und Ausschalten schneiden
    weiterhin sofort; nur der Schritt von Höhe zu Höhe wartet, bis der Schieber
    stehen bleibt.
    """
    from app.core.types import LayerInfo

    viewport = window.viewport
    first = LayerInfo(z=1.0, contours=(), area=0.0, overhang_area=0.0, islands=(), min_width=0.0)
    second = LayerInfo(z=2.0, contours=(), area=0.0, overhang_area=0.0, islands=(), min_width=0.0)

    viewport.set_layer(first)
    assert not viewport._layer_rebuild.isActive(), "Einschalten schneidet sofort"

    rebuilt: list[object] = []
    monkeypatch.setattr(viewport, "show_scene", rebuilt.append)
    viewport.set_layer(second)
    assert viewport._layer_rebuild.isActive(), "beim Fahren wird aufgeschoben"
    assert rebuilt == [], "und zwar wirklich: kein Schnitt im selben Atemzug"

    application = QApplication.instance()
    assert application is not None
    deadline = 200
    while not rebuilt and deadline > 0:
        application.processEvents()
        QThread.msleep(25)
        deadline -= 1
    assert rebuilt, "sobald der Schieber ruht, kommt der Schnitt nach"

    viewport.set_layer(None)
    assert not viewport._layer_rebuild.isActive(), "Ausschalten lässt nichts nachhängen"


def test_a_chosen_layer_cuts_away_what_lies_above(window: MainWindow) -> None:
    """„Durch die Höhe fahren und den Querschnitt ansehen" versprach der Text.

    Der Schieber lief, die Zahlen stimmten — und das Modell blieb vollständig
    undurchsichtig stehen; sichtbar wurde nur eine dünne Kontur darunter. Wer
    eine Schicht gewählt hat, will sehen, was auf dieser Höhe steht.
    """
    from app.core.types import LayerInfo

    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    full = entry.mesh.bounds

    window.viewport.set_layer(
        LayerInfo(
            z=full.minimum[2] + 1.0,
            contours=(),
            area=0.0,
            overhang_area=0.0,
            islands=(),
            min_width=0.0,
        )
    )
    cut_mesh = window.viewport._sectioned(entry.mesh)

    assert cut_mesh.bounds.maximum[2] < full.maximum[2], "oben ist etwas weg"
    assert cut_mesh.bounds.maximum[2] == pytest.approx(full.minimum[2] + 1.0, abs=0.2)

    window.viewport.set_layer(None)
    assert window.viewport._sectioned(entry.mesh).bounds.maximum[2] == pytest.approx(
        full.maximum[2]
    ), "und ohne Schicht steht wieder alles da"


def test_switching_it_off_clears_the_view(window: MainWindow) -> None:
    select_plate(window)
    window.layer_bar.set_active(True)
    window.layer_bar.set_active(False)

    assert window.layer_bar.index() == -1
    assert window.layer_bar.readout.text() == ""


# --- Maßstab an der Druckplatte (Konzept P15 §7 Etappe 1) ----------------------


def test_what_is_fitted_gets_air_around_it() -> None:
    """``reset_camera(bounds=…)`` passt genau ein — und das war zu genau.

    Ein 40 mm großer Quader berührte links und rechts den Bildrand, und von der
    Druckplatte war nichts mehr zu sehen. Zwölf Prozent je Achse, um die Mitte
    gelegt: die Mitte bleibt, wo sie war, und beide Seiten gewinnen gleich viel.

    Eine Achse ohne Ausdehnung bleibt unberührt — eine flache Skizze soll nicht
    in die Tiefe wachsen, nur weil jemand einpasst.
    """
    from app.ui.viewport import CAMERA_MARGIN, with_margin

    wide = with_margin((-20.0, 20.0, -15.0, 15.0, 0.0, 10.0))
    assert wide[0] == pytest.approx(-20.0 - 40.0 * CAMERA_MARGIN / 2.0)
    assert wide[1] == pytest.approx(20.0 + 40.0 * CAMERA_MARGIN / 2.0)
    # Die Mitte verschiebt sich nicht.
    assert (wide[0] + wide[1]) / 2.0 == pytest.approx(0.0)
    assert (wide[4] + wide[5]) / 2.0 == pytest.approx(5.0)

    flat = with_margin((-10.0, 10.0, -10.0, 10.0, 3.0, 3.0))
    assert flat[4] == pytest.approx(3.0)
    assert flat[5] == pytest.approx(3.0)


def test_the_bed_carries_numbers_not_just_lines() -> None:
    """Ein Raster ohne Zahlen sagt nur, dass es ein Raster gibt.

    Erst die Zahl daneben macht daraus einen Maßstab, an dem sich ein Teil
    einordnen lässt, ohne es zu messen — und genau dafür steht die Platte in
    echter Größe da.

    Als reine Rechnung geprüft: offscreen gibt es keinen Renderer, und ein
    Test, der sich dort überspringt, prüft nie etwas.
    """
    from app.ui.viewport import BED_SCALE_STEP, bed_scale

    marks = bed_scale(256.0, 256.0)
    labels = [text for _point, text in marks]

    assert "50" in labels
    assert "100" in labels
    # 128 mm je Seite, alle 50 mm: Null, 50 und 100 in beide Richtungen — je
    # Kante fünf Zahlen.
    assert len(marks) == 2 * 5

    steps = sorted({float(text) for text in labels})
    assert steps == [-2 * BED_SCALE_STEP, -BED_SCALE_STEP, 0.0, BED_SCALE_STEP, 2 * BED_SCALE_STEP]


def test_the_bed_scale_signs_its_numbers_and_puts_zero_in_the_middle() -> None:
    """Die Skala widersprach sich selbst.

    ``abs()`` nahm beiden Seiten das Vorzeichen — dieselbe „100" lag zweimal im
    Bild —, und die einzige Null stand in der **Ecke** der Platte, mit der
    Begründung, sie gehöre beiden Kanten. Der Nullpunkt der Szene ist aber die
    Mitte: bei 220 mm stand „0" bei x = -110 und zehn Millimeter weiter „100".
    Ein Körper aus ``create_box`` steht in dieser Mitte, und „Position X = -40"
    im Dialog meint dieselbe Achse.

    Geprüft wird beides — dass die Null dort liegt, wo sie hingehört, und dass
    die negative Seite ihr Vorzeichen behält.
    """
    from app.ui.viewport import bed_scale

    marks = bed_scale(220.0, 220.0)
    # Die Marken der Vorderkante liegen weiter vorn als seitlich, die der linken
    # Kante umgekehrt — das trennt die beiden Kanten, ohne den Abstand zu kennen,
    # mit dem sie vor der Platte stehen.
    front = [(point, text) for point, text in marks if point[1] < point[0]]

    zeros = [point for point, text in marks if text == "0"]
    assert len(zeros) == 2, "jede Kante trägt ihre eigene Null"
    for point in zeros:
        assert abs(point[0]) < 1e-9 or abs(point[1]) < 1e-9, (
            "die Null einer Kante liegt in ihrer Mitte, nicht in der Ecke"
        )

    assert "-100" in [text for _point, text in marks], "die negative Seite behält ihr Vorzeichen"
    assert [text for _point, text in front].count("100") == 1, "keine Zahl steht zweimal je Kante"


def test_a_small_bed_still_gets_a_scale() -> None:
    """Und eine Platte, die kleiner ist als ein Schritt, bekommt wenigstens
    ihren Nullpunkt — den Bezug, an dem eine Skala anfängt (und unter VTK, bis
    06.09.2026, stolperte der Renderer über eine leere Beschriftungsliste)."""
    from app.ui.viewport import bed_scale

    marks = bed_scale(60.0, 60.0)
    assert marks
    # Je Kante ihre Null, seit die Skala vorzeichenbehaftet ist — vorher war es
    # eine einzige in der Ecke, und die lag am falschen Ort.
    assert [text for _point, text in marks] == ["0", "0"]


def test_a_shadow_falls_beside_the_body_not_under_it() -> None:
    """Senkrecht projiziert ist ein Schatten unsichtbar.

    Der erste Versuch legte ihn genau unter den Körper — dort verdeckt ihn der
    Körper, und im Bild war schlicht kein Schatten. Er fällt deshalb entlang
    der Lichtrichtung, und sein Versatz wächst mit der Höhe: damit beantwortet
    er nebenbei die Frage, für die er da ist, denn ein schwebendes Teil hat
    seinen Schatten weiter weg.
    """
    import numpy as np

    from app.ui.viewport import shadow_points

    standing = shadow_points(np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 40.0]]), (0.3, 0.4))
    assert standing[0][0] == pytest.approx(0.0), "was aufliegt, wirft an Ort und Stelle"
    assert standing[1][0] == pytest.approx(40.0 * 0.3)
    assert standing[1][1] == pytest.approx(40.0 * 0.4)
    assert all(point[2] == 0.0 for point in standing), "der Schatten liegt auf der Platte"


def test_a_body_below_the_plate_throws_nothing_forward() -> None:
    """Sonst zöge ein halb versunkenes Teil seinen Schatten falsch herum."""
    import numpy as np

    from app.ui.viewport import shadow_points

    sunk = shadow_points(np.array([[5.0, 7.0, -12.0]]), (0.3, 0.4))
    assert sunk[0][0] == pytest.approx(5.0)
    assert sunk[0][1] == pytest.approx(7.0)


def test_the_shadow_steps_beside_the_body_and_never_towards_the_viewer() -> None:
    """Zur Seite, weil hinten das Teil selbst steht.

    Das Licht hängt an der Kamera, und ein Schatten, der von der Kamera weg
    fällt, liegt hinter dem Teil — von der Kamera aus also dort, wo das Teil
    ist. Er war damit nicht zu sehen: gemessen an zwei Aufnahmen desselben
    Bildes, einmal mit und einmal ohne die Schattenaktoren, waren von 260 000
    verglichenen Bildpunkten **vier** dunkler. Zur Seite geworfen sind es
    2 988, und die Frage aus §18.6 — steht das Teil auf der Platte oder
    darüber? — bekommt eine Antwort.

    Die Gegenrichtung ist ausdrücklich verboten: Ein Schatten, der auf den
    Betrachter zu fällt, wäre noch besser zu sehen (gemessen 5 053 Punkte) und
    behauptete ein Licht hinter dem Teil, dessen Vorderseite hell beleuchtet
    ist. Das war schon einmal der Stand und wurde aus genau diesem Grund
    verworfen; ohne diese Zusicherung wäre der Weg zurück offen.
    """
    import numpy as np

    from app.ui.viewport import VIEW_DIRECTIONS, shadow_direction

    for name, (position, _up) in VIEW_DIRECTIONS.items():
        if name in {"top", "bottom"}:
            continue  # Senkrecht von oben gibt es kein Hinten; siehe unten.
        step = np.array(shadow_direction(position, (0.0, 0.0, 0.0)))
        forward = np.array([-position[0], -position[1]], dtype=float)
        forward /= np.linalg.norm(forward)
        sideways = np.array([-forward[1], forward[0]])
        along = float(np.dot(step, forward))
        across = float(np.dot(step, sideways))
        assert abs(across) > abs(along), (
            f"in der Ansicht {name!r} läuft der Schatten hinter das Teil: "
            f"{along:.2f} nach hinten, {across:.2f} zur Seite"
        )
        assert along >= 0.0, (
            f"in der Ansicht {name!r} fällt der Schatten auf den Betrachter zu ({along:.2f})"
        )


def test_looking_straight_down_the_shadow_still_has_a_direction() -> None:
    """Eine Draufsicht hat kein Hinten, aber eine Oberkante.

    Ohne diesen Fall teilte die Rechnung durch null, und der Schatten wäre in
    der Ansicht verschwunden, in der man ihn zum Anordnen am ehesten braucht.
    """
    from app.ui.viewport import SHADOW_REACH, SHADOW_SIDE, shadow_direction

    assert shadow_direction((0.0, 0.0, 100.0), (0.0, 0.0, 0.0)) == (SHADOW_SIDE, SHADOW_REACH)


def test_the_shadow_of_a_standing_body_reaches_past_its_own_footprint() -> None:
    """Ein Schatten, der unter dem Teil bleibt, ist keiner.

    Die Richtung allein sagt es nicht: Erst zusammen mit der Höhe entsteht der
    Versatz, und der muss den eigenen Umriss verlassen, sonst deckt das Teil
    seinen Schatten selbst ab. Gerechnet an einem 40er Würfel — 20 mm hoch,
    also 12,6 mm Versatz — gegen die Hälfte seiner Kantenlänge.
    """
    import numpy as np

    from app.ui.viewport import VIEW_DIRECTIONS, shadow_direction, shadow_points

    hull = np.array(
        [(x, y, z) for x in (-20.0, 20.0) for y in (-20.0, 20.0) for z in (0.0, 20.0)],
        dtype=float,
    )
    for name, (position, _up) in VIEW_DIRECTIONS.items():
        if name in {"top", "bottom"}:
            continue  # Senkrecht von oben verdeckt das Teil seinen Schatten immer.
        step = shadow_direction(position, (0.0, 0.0, 0.0))
        cast = shadow_points(hull, step)
        forward = np.array([-position[0], -position[1]], dtype=float)
        forward /= np.linalg.norm(forward)
        sideways = np.array([-forward[1], forward[0]])
        # Gemessen wird **quer** zur Blickrichtung: nach hinten hinaus liegt
        # der Schatten hinter dem Teil, und von dort sieht ihn niemand.
        reach = float(np.max(np.abs(cast[:, :2] @ sideways))) - float(
            np.max(np.abs(hull[:, :2] @ sideways))
        )
        assert reach > 5.0, (
            f"in der Ansicht {name!r} tritt der Schatten nur {reach:.1f} mm "
            "seitlich unter dem Teil hervor"
        )


def test_the_shadow_keeps_its_length_whatever_the_view() -> None:
    """Ein Teil darf beim Drehen nicht zu wachsen scheinen."""
    import numpy as np

    from app.ui.viewport import VIEW_DIRECTIONS, shadow_direction

    lengths = [
        float(np.linalg.norm(shadow_direction(position, (0.0, 0.0, 0.0))))
        for position, _up in VIEW_DIRECTIONS.values()
    ]
    assert max(lengths) - min(lengths) < 1e-9


def test_the_shadow_hull_holds_the_corners_and_drops_the_rest(qt_app: QApplication) -> None:
    """Die Hülle wird einmal je Körper gerechnet, der Umriss je Ansicht.

    Vorher lief eine Triangulierung über **jeden** Punkt des Anzeigenetzes, und
    zwar bei jedem Szenenaufbau: 31 ms bei zwanzigtausend Dreiecken, 127 ms bei
    zweiundachtzigtausend, je Körper und im Qt-Hauptthread. Für den Umriss
    zählen nur die Punkte der konvexen Hülle — bei einem Quader acht von
    Hunderten.
    """
    import numpy as np
    import trimesh

    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        box = trimesh.creation.box(extents=(20.0, 20.0, 30.0)).subdivide().subdivide().subdivide()
        body = np.asarray(box.vertices, dtype=float) + np.array([10.0, 10.0, 15.0])
        hull = viewport._shadow_hull_of(body)
        assert len(hull) == 8, "ein Quader hat acht Ecken, wie fein er auch vernetzt ist"
        assert len(hull) < len(body) / 10

        outline = viewport._shadow_outline_of(hull, (0.5, 0.0))
        assert outline is not None and len(outline) > 0
        assert np.allclose(outline[:, 2], 0.05), "der Schatten liegt auf der Platte"
        # 30 mm hoch, halber Versatz je Millimeter: der Umriss reicht 15 mm
        # weiter als der Körper.
        assert outline[:, 0].max() == pytest.approx(35.0)
        assert outline[:, 1].max() == pytest.approx(20.0)
    finally:
        viewport.deleteLater()


def test_thinning_a_dense_body_keeps_its_corners() -> None:
    """Die Stichprobe hält die Form, die Stützpunkte halten die Ecken.

    Bei einer feinen Kugel liegt jeder Punkt auf der Hülle — dort kostete die
    Hüllenrechnung mehr als die Triangulierung, die sie ersetzen sollte. Sie
    bekommt deshalb einen Deckel. Nur darf der die Ecken nicht wegwerfen: ein
    gescannter Halter würfe sonst einen Schatten, der um Millimeter zu klein
    ist.
    """
    import numpy as np

    from app.ui.viewport import SHADOW_HULL_POINTS, _thinned_for_hull

    rng = np.random.default_rng(7)
    cloud = rng.uniform(-10.0, 10.0, size=(SHADOW_HULL_POINTS * 4, 3))
    corners = np.array([[-40.0, -40.0, 0.0], [40.0, -40.0, 0.0], [0.0, 40.0, 30.0]])
    # Die Ecken in die Mitte, wo keine Stichprobe sie zufällig erwischt.
    points = np.vstack((cloud[: len(cloud) // 2], corners, cloud[len(cloud) // 2 :]))

    thinned = _thinned_for_hull(points)
    assert len(thinned) < len(points) / 3, "ausgedünnt wurde"
    for corner in corners:
        assert np.any(np.all(np.isclose(thinned, corner), axis=1)), f"{corner} fehlt"


def test_a_small_body_is_not_thinned_at_all() -> None:
    """Unter dem Deckel bleibt die Hülle exakt — sie ist dort ohnehin billig."""
    import numpy as np

    from app.ui.viewport import SHADOW_HULL_POINTS, _thinned_for_hull

    points = np.zeros((SHADOW_HULL_POINTS, 3))
    assert _thinned_for_hull(points) is points


def test_a_body_too_thin_for_a_hull_still_gets_one(qt_app: QApplication) -> None:
    """Ein ebener Körper hat keine räumliche Hülle — er wirft trotzdem.

    Qhull gibt bei entarteten Punktwolken auf. Sein Fehler darf nicht der
    Fehler der Ansicht werden: die paar Punkte gehen dann unverändert weiter.
    """
    import numpy as np

    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        flat = np.array([[0.0, 0.0, 5.0], [10.0, 0.0, 5.0], [10.0, 10.0, 5.0], [0.0, 10.0, 5.0]])
        hull = viewport._shadow_hull_of(flat)
        assert hull is not None and len(hull) == 4
        assert viewport._shadow_outline_of(hull, (0.5, 0.5)) is not None
    finally:
        viewport.deleteLater()


def test_a_body_standing_on_another_throws_its_shadow_onto_it(qt_app: QApplication) -> None:
    """Sonst löst sich der Schatten von dem ab, was ihn wirft.

    Ein Turm auf einer zwölf Millimeter hohen Grundplatte warf seinen Schatten
    auf die Druckplatte: gemessen ab null statt ab der Fläche, auf der er
    steht, und damit um die volle Bauhöhe versetzt. Im Bild tauchte er erst
    neben der Grundplatte auf — ein Fleck ohne Verbindung zu dem, was ihn
    wirft.
    """
    import numpy as np

    from app.ui.viewport import Viewport, outline_of

    viewport = Viewport()
    try:
        plate = np.array(
            [[x, y, z] for x in (-40.0, 40.0) for y in (-40.0, 40.0) for z in (0.0, 12.0)]
        )
        tower = np.array(
            [[x, y, z] for x in (0.0, 10.0) for y in (0.0, 10.0) for z in (12.0, 52.0)]
        )
        viewport._shadow_ground["plate"] = (0.0, 12.0, outline_of(plate))
        viewport._shadow_ground["tower"] = (12.0, 52.0, outline_of(tower))

        catchers = viewport._shadow_catchers("tower")
        assert [ground for ground, _window in catchers] == [0.0, 12.0], (
            "die Grundplatte fängt, die Druckplatte fängt daneben"
        )

        ground, window = catchers[1]
        outline = viewport._shadow_outline_of(tower, (0.5, 0.0), ground, window)
        assert outline is not None
        assert np.allclose(outline[:, 2], 12.05), "er liegt auf der Grundplatte"
        # 40 mm über ihr, halber Versatz je Millimeter: 20 mm weiter als der
        # Turm, nicht 26 wie bei der Rechnung ab null.
        assert outline[:, 0].max() == pytest.approx(30.0)
    finally:
        viewport.deleteLater()


def test_a_body_on_the_plate_has_only_the_plate_below_it(qt_app: QApplication) -> None:
    """Ein Körper daneben ist kein Boden, solange er nicht darunter liegt."""
    import numpy as np

    from app.ui.viewport import Viewport, outline_of

    viewport = Viewport()
    try:
        neighbour = np.array(
            [[x, y, z] for x in (50.0, 60.0) for y in (0.0, 10.0) for z in (0.0, 30.0)]
        )
        viewport._shadow_ground["neighbour"] = (0.0, 30.0, outline_of(neighbour))
        viewport._shadow_ground["mine"] = (0.0, 20.0, outline_of(neighbour + 100.0))
        assert [ground for ground, _window in viewport._shadow_catchers("mine")] == [0.0]
    finally:
        viewport.deleteLater()


def test_the_shadow_is_cut_at_the_edge_of_the_plate(qt_app: QApplication) -> None:
    """Außerhalb der Platte liegt er auf blankem Hintergrund.

    Bei aufgezogener Explosion oder einem Körper weit vom Ursprung war das ein
    dunkler Umriss ohne Fläche darunter — die einzige Stelle, an der die
    Ansicht Boden behauptete, wo keiner ist.
    """
    import numpy as np

    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        viewport._bed_extent = (100.0, 100.0)
        body = np.array([[x, y, z] for x in (40.0, 80.0) for y in (0.0, 10.0) for z in (0.0, 20.0)])
        ground, window = viewport._shadow_catchers("body")[0]
        outline = viewport._shadow_outline_of(body, (0.5, 0.0), ground, window)
        assert outline is not None
        assert outline[:, 0].max() == pytest.approx(50.0), "an der Kante ist Schluss"

        far = body + np.array([200.0, 0.0, 0.0])
        assert viewport._shadow_outline_of(far, (0.5, 0.0), ground, window) is None, (
            "was ganz daneben fällt, wirft gar keinen Schatten"
        )
    finally:
        viewport.deleteLater()


def test_without_a_build_volume_nothing_is_cut(qt_app: QApplication) -> None:
    """Ohne gezeigten Bauraum gibt es keine Kante, an der zu schneiden wäre."""

    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        assert viewport._shadow_catchers("body") == [(0.0, None)]
    finally:
        viewport.deleteLater()


def test_clipping_keeps_the_part_inside_and_cuts_the_rest() -> None:
    """Sutherland und Hodgman, an einem Fall mit bekannter Antwort.

    Ein Quadrat, das zur Hälfte über das Fenster hinausragt, wird an dessen
    Kante abgeschnitten — nicht weggelassen und nicht ganz behalten.
    """
    import numpy as np

    from app.ui.viewport import bed_outline, clip_polygon

    window = bed_outline(100.0, 100.0)
    half_out = np.array([[30.0, -10.0], [70.0, -10.0], [70.0, 10.0], [30.0, 10.0]])
    clipped = clip_polygon(half_out, window)
    assert len(clipped) >= 3
    assert clipped[:, 0].max() == pytest.approx(50.0)
    assert clipped[:, 0].min() == pytest.approx(30.0)

    inside = np.array([[-10.0, -10.0], [10.0, -10.0], [10.0, 10.0], [-10.0, 10.0]])
    assert np.allclose(clip_polygon(inside, window), inside), "was drin liegt, bleibt wie es ist"

    outside = inside + 200.0
    assert len(clip_polygon(outside, window)) == 0


def test_a_list_in_the_bottom_bar_opens_upwards_when_it_has_to() -> None:
    """Qt hält eine Aufklappliste am Bildschirm, nicht am Fenster.

    Die Leisten unter dem Viewport sitzen an der Unterkante der Anwendung —
    ihre Listen klappten über das Fenster hinaus auf den Schreibtisch und
    verdeckten, was dort lag. Gerechnet wird in Bildschirmkoordinaten.

    **Der mittlere Zweig las sich einmal „sonst darüber", und das war ein Wort
    zu viel.** Das Ziel dieser Rechnung ist, die Liste im *Fenster* zu halten;
    dass sie dabei über dem Feld endet statt an dessen Unterkante, war die
    naheliegende Lesart von „nicht darunter" und keine eigene Zusage. Sie hat
    die Liste unbedienbar gemacht: Verschoben wird erst, **nachdem** Qt sie
    geöffnet hat, und wer eine Liste öffnet, hält die Maustaste über dem Feld.
    Endet sie an der Oberkante, liegt der Zeiger beim Loslassen außerhalb — und
    Qt schließt eine Aufklappliste, die ihren Zeiger verloren hat. Sie ging auf
    und sofort wieder zu (Roberts Fehlerbericht, 30.08.2026; an seiner
    Fenstergröße gerechnet lag der Zeiger bei 777 und die Liste endete bei
    767). Das Feld zu überdecken kostet nichts: Was dort steht, steht auch in
    der Liste, als der gewählte Eintrag.
    """
    from PySide6.QtCore import QRect

    from app.ui.tool_strip import list_top

    window = QRect(100, 100, 900, 600)  # unten bei 699

    roomy = QRect(120, 200, 160, 24)  # unten bei 223
    assert list_top(roomy, 200, window) == roomy.bottom(), "passt darunter — dann darunter"

    cramped = QRect(120, 640, 160, 24)  # unten bei 663, darunter nur 36
    assert list_top(cramped, 200, window) == cramped.bottom() - 200, (
        "sonst nach oben — bündig mit der Unterkante des Feldes, nicht darüber"
    )

    tall = list_top(cramped, 700, window)
    assert tall == window.top(), "passt nirgends: dann bündig, nicht über den Rand"
    assert tall + 700 >= window.bottom()


def test_every_list_in_the_bottom_bars_knows_that(qt_app: QApplication) -> None:
    """Und zwar jede — die Regel nützt nichts, wenn eine Leiste sie vergisst.

    Geprüft werden die Leisten unter dem Viewport. Listen in Dialogen haben das
    Problem nicht: die stehen in der Fenstermitte.
    """
    from PySide6.QtWidgets import QComboBox

    from app.ui.explode_bar import ExplodeBar
    from app.ui.section_bar import MeasureBar, SectionBar
    from app.ui.tool_strip import BarComboBox

    plain: list[str] = []
    for bar in (AnalysisBar(), LayerBar(), ExplodeBar(), MeasureBar(), SectionBar()):
        for child in bar.findChildren(QComboBox):
            if not isinstance(child, BarComboBox):
                plain.append(f"{type(bar).__name__}.{child.objectName() or '?'}")

    assert not plain, (
        f"Diese Listen klappen über den Fensterrand hinaus: {plain}. "
        "In einer Leiste unter dem Viewport ist BarComboBox die richtige Klasse."
    )


def test_a_click_on_a_feature_selects_its_body_too(window: MainWindow) -> None:
    """Sonst tut der erste Klick nichts (§18.5).

    Der Baum zeigt ein Merkmal nur unter der Zeile seines Objekts. Solange der
    Viewport bei einem Treffer allein ``featurePicked`` sendete, lief das ins
    Leere: ``_on_feature_picked`` fragt den Baum nach dem ausgewählten Objekt,
    und ausgewählt war noch keines. Im Fenster sah es aus, als käme der Klick
    nicht an — in Wahrheit war er angekommen und hatte niemanden.

    **Zwei Klicks statt einem**, seit die Auswahltiefe gestuft ist (§18.5): Der
    erste meint das Teil, der zweite die Bohrung darin. Die Aussage dieses
    Tests ist davon unberührt — sie betrifft die *Reihenfolge* im Klick, der
    ein Merkmal wählt, und die ist dieselbe geblieben.
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    hole = next((name for name, feature in entry.features.items() if feature.kind == "hole"), None)
    assert hole is not None, "die Platte aus dem Korpus hat Bohrungen"
    wall = on_the_bore_wall(window, hole)

    window.viewport._select_at(wall)  # erste Stufe: der Körper

    picked: list[str] = []
    features: list[str] = []
    window.viewport.objectPicked.connect(lambda name, add: picked.append(name))
    window.viewport.featurePicked.connect(lambda name, add: features.append(name))

    window.viewport._select_at(wall)  # zweite Stufe: das Merkmal darin

    # Der Körper steht nach dem ersten Klick schon allein in der Auswahl; der
    # zweite meldet ihn nicht noch einmal (Durchsicht 0.5.1), und der Baum
    # zeigt das Merkmal trotzdem unter seiner Zeile.
    assert picked == [], "der schon gewählte Körper wird nicht noch einmal gewählt"
    assert features == [hole], "das Merkmal, das darunter erscheint"
    assert window.object_tree.selected() == "obj_1"
    assert window.object_tree.selected_feature() == hole


def test_the_report_says_where_you_stand_not_only_what_to_do(qt_app: QApplication) -> None:
    """Ein Bericht aus Sätzen sagt, *was* zu tun ist — nicht, woran man ist.

    Die Kennzahlen darüber tun das, und sie kosten nichts: wasserdicht,
    Volumen, Zahl der Teile stehen im ausgewerteten Netz. Was einen Schnitt
    durch jede Schicht kostet — schmalste Wand, schlimmster Überhang —, steht
    bewusst nicht dort.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ReportPanel

    box = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    scene = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Klotz", mesh=box)})
    panel = ReportPanel()
    try:
        panel.show_result(EvaluationResult(scene=scene))

        assert panel.facts.isVisible() or panel.facts.text()
        text = panel.facts.text()
        assert tr("geschlossen") in text
        # Ein Wuerfel mit 20 mm Kante ist 8 Kubikzentimeter — die Zahl kommt aus
        # dem Netz, nicht aus
        # dem Test: eine abgeschriebene Konstante prüfte nur sich selbst.
        assert format_decimal(box.volume / 1000.0, 1) in text
        assert tr("Teil") in text

        panel.show_result(None)
        assert not panel.facts.text()
    finally:
        panel.deleteLater()


def test_a_flood_of_identical_findings_becomes_one_line_that_counts_them(
    qt_app: QApplication,
) -> None:
    """118 wortgleiche Zeilen begraben die fünf, die etwas Eigenes sagen.

    Nach dem Löschen früher Verlaufsschritte meldete ``perceive.orphaned``
    jedes verlorene Formdetail einzeln — 118 wortgleiche Zeilen — und die zwei
    Warnungen dazwischen fand niemand. Gebündelt wird in der Anzeige, nicht im
    Kern: Agent, Kommandozeile und Steckbrief lesen weiter jeden Befund
    einzeln.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    orphan_text = (
        "Ein Formdetail ist nach diesem Schritt nicht mehr automatisch "
        "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
        "Bearbeitung bleibt erhalten."
    )
    findings = (
        *(
            Finding(
                code="perceive.orphaned",
                severity="info",
                message=orphan_text,
                object_id="obj_1",
                values={"feature": f"hole_{n}"},
            )
            for n in range(118)
        ),
        Finding(code="mesh.thin_wall", severity="warning", message="Eine Wand ist zu dünn"),
        # Ein Kernbefund darf selbst einen ``count``-Wert führen („12 kleine
        # Objekte übergangen") — er bleibt eine Zeile und zählt als eine.
        Finding(
            code="ingest.small_components",
            severity="warning",
            message="Kleine Objekte wurden übergangen",
            values={"count": 12},
        ),
        *(
            Finding(code="mesh.gap_closed", severity="info", message="Eine Lücke wurde geschlossen")
            for _ in range(3)
        ),
    )
    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(
                scene=Scene(report=Report(findings=findings)),
                object_names={"obj_1": "Griff"},
            )
        )

        texts = [panel.list.item(row).text() for row in range(panel.list.count())]
        # Seit dem 11.09.2026 bündelt der Bericht jede gleiche Meldung ab zwei:
        # die drei geschlossenen Lücken sind eine Zeile „(3) …".
        assert len(texts) == 4, f"eine Sammelzeile statt 118, der Rest bleibt: {texts!r}"
        assert "(3) Eine Lücke wurde geschlossen" in texts, texts

        bundle = [text for text in texts if "(118) Formdetails" in text]
        assert bundle == [
            "(118) Formdetails sind nach diesem Schritt nicht mehr automatisch "
            "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
            "Bearbeitung bleibt erhalten. — Griff"
        ], "Zahl davor, nächster Klick und verständlicher Körpername stehen sichtbar an der Zeile"

        row = texts.index(bundle[0])
        tooltip = panel.list.item(row).toolTip()
        assert "hole_0" in tooltip, "die Betroffenen bleiben erreichbar"
        assert "+103" in tooltip, "und der Rest hinter den ersten fünfzehn wird beziffert"

        stored: Finding = panel.list.item(row).data(Qt.ItemDataRole.UserRole)
        assert stored.values.get("count") == 118

        # Die Kopfzeile zählt die Befunde, nicht die Zeilen — und der
        # ``count``-Wert des Kernbefunds bläht sie nicht auf.
        summary = panel.summary.text()
        assert f"2 × {tr('Warnung')}" in summary, summary
        assert f"121 × {tr('Hinweis')}" in summary, summary
    finally:
        panel.deleteLater()


def test_a_bundle_survives_findings_that_arrive_later(qt_app: QApplication) -> None:
    """Der Nachschub-Weg zerlegte die Sammelzeile — und bündelte selbst nie.

    ``add_findings`` (G-Code-Gegenprobe, Kollisions-, Exportprüfung) baute
    die Liste über die *Zeilen* neu statt über die Befunde: ``_resort`` las
    das ersetzte Bündel-Finding aus dem ``UserRole`` und hängte es als
    Einzelzeile wieder an — die Kopfzeile zählte 1 statt 118, und die
    Namensliste aus dem Tooltip stand plötzlich in der Zeile. Seitdem hält
    das Panel die rohen Befunde und baut Zeilen immer über dieselbe
    Bündelung. Der Weg-3-Fall aus dem Register ist genau diese Folge:
    erst die Auswertung mit den Waisen, dann die Gegenprobe obendrauf.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    orphan_text = (
        "Ein Formdetail ist nach diesem Schritt nicht mehr automatisch "
        "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
        "Bearbeitung bleibt erhalten."
    )
    orphans = tuple(
        Finding(
            code="perceive.orphaned",
            severity="info",
            message=orphan_text,
            values={"feature": f"hole_{n}"},
        )
        for n in range(118)
    )
    panel = ReportPanel()
    try:
        panel.show_result(EvaluationResult(scene=Scene(report=Report(findings=orphans))))
        assert panel.list.count() == 1

        panel.add_findings(
            [
                Finding(
                    code="gcode.print_time",
                    severity="info",
                    message="Die Druckzeit steht in der Druckdatei",
                    source="gcode",
                )
            ]
        )
        texts = [panel.list.item(row).text() for row in range(panel.list.count())]
        assert len(texts) == 2, f"die Sammelzeile übersteht den Nachschub: {texts!r}"
        assert any(text.startswith("(118) Formdetails") for text in texts)
        assert f"119 × {tr('Hinweis')}" in panel.summary.text(), panel.summary.text()

        # Der Nachschub-Weg dedupliziert identische Kernbefunde. Vier
        # wortgleiche Warnungen ohne weitere Unterscheidungsmerkmale sind
        # deshalb genau eine Zeile und zählen auch nur einmal.
        panel.add_findings(
            [
                Finding(
                    code="check.collision",
                    severity="warning",
                    message="Zwei Objekte berühren sich",
                )
                for _ in range(4)
            ]
        )
        texts = [panel.list.item(row).text() for row in range(panel.list.count())]
        assert texts.count("Zwei Objekte berühren sich") == 1, texts
        assert len(texts) == 3, texts
        assert f"1 × {tr('Warnung')}" in panel.summary.text(), panel.summary.text()
    finally:
        panel.deleteLater()


def test_a_bundle_never_crosses_the_body_or_step_its_click_will_show(
    qt_app: QApplication,
) -> None:
    """Eine kurze Zeile darf nicht auf einen zufälligen Körper zeigen.

    Die erste Bündelung gruppierte nur nach Kennung, Schwere und Wortlaut. Acht
    Waisen aus zwei Körpern und zwei Schritten wurden eine Zeile; deren
    künstlicher Befund verlor den Körper, behielt aber den ersten Schritt. Ein
    Klick wählte deshalb den gerade markierten, womöglich falschen Körper und
    sprang im Verlauf zum ersten zufälligen Schritt.

    Der echte Einzelklick auf jede sichtbare Sammelzeile muss genau die
    Navigationsdaten ausgeben, die für alle ihre Mitglieder gelten.
    """
    from PySide6.QtTest import QTest

    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    findings = tuple(
        Finding(
            code="perceive.orphaned",
            severity="info",
            message=(
                "Ein Formdetail ist nach diesem Schritt nicht mehr automatisch "
                "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
                "Bearbeitung bleibt erhalten."
            ),
            object_id=object_id,
            op_id=op_id,
            feature_ids=(f"face_{index}",),
            values={"feature": f"face_{index}"},
            location=(float(index), 0.0, 0.0),
        )
        for object_id, op_id in (("obj_1", 7), ("obj_2", 11))
        for index in range(4)
    )
    panel = ReportPanel()
    activated: list[Finding] = []
    panel.findingActivated.connect(activated.append)
    try:
        panel.resize(420, 520)
        panel.show_result(
            EvaluationResult(
                scene=Scene(report=Report(findings=findings)),
                object_names={"obj_1": "Griff", "obj_2": "Deckel"},
            )
        )
        panel.show()
        qt_app.processEvents()

        assert panel.list.count() == 2, "je Körper und Schritt steht eine ehrliche Sammelzeile"
        texts = [panel.list.item(row).text() for row in range(panel.list.count())]
        assert texts[0] != texts[1], "gleich große Bündel müssen sichtbar unterscheidbar bleiben"
        assert "Griff" in texts[0] and f"{tr('Schritt')} 7" in texts[0]
        assert "Deckel" in texts[1] and f"{tr('Schritt')} 11" in texts[1]
        for row, expected in enumerate((("obj_1", 7), ("obj_2", 11))):
            item = panel.list.item(row)
            bundled: Finding = item.data(Qt.ItemDataRole.UserRole)
            assert (bundled.object_id, bundled.op_id) == expected
            assert bundled.feature_ids == (), "verschiedene verlorene Details sind kein Einzelziel"
            assert bundled.location is None, (
                "der erste von vier Orten wäre ein erfundener Sammelort"
            )
            QTest.mouseClick(
                panel.list.viewport(),
                Qt.MouseButton.LeftButton,
                pos=panel.list.visualItemRect(item).center(),
            )
            assert (activated[-1].object_id, activated[-1].op_id) == expected
    finally:
        panel.deleteLater()


def test_a_bundle_over_many_bodies_selects_all_of_them_on_click(
    qt_app: QApplication,
) -> None:
    """Neun gleiche Sätze sind eine Zeile „(9) …", und ihr Klick wählt alle neun.

    **Roberts Bericht** (11.09.2026: „beim prüfbericht auch gleiche Meldungen
    zusammenfassen und anzahl dann davor in Klammer anzeigen"): ein Schriftzug,
    zerlegt und ausgerichtet, und der Bericht führte je Buchstabe „Ausrichtung
    über die Schichtanalyse gesucht." — neun Zeilen mit demselben Satz. Bis
    dahin trennte der Körper die Gruppen, damit ein Klick auf eine Sammelzeile
    nie den ersten zufälligen Körper zeigt. Der Vertrag bleibt, die Antwort ist
    eine andere: Die Zeile trägt alle Körper, und der Klick wählt sie **alle**.

    Ende zu Ende am Fenster: Schriftzug, zerlegen, ausrichten; dann die Zeile
    lesen, ihren Tooltip, und den Klick am Objektbaum messen.
    """
    from PySide6.QtTest import QTest

    from app.core.scene import OperationDraft
    from app.ui.panels import _BODIES_ROLE

    # Ein eigenes Fenster: Die Fixture öffnet eine Platte als ``obj_1``, und
    # die Zerlegung darunter meint den Schriftzug.
    window = MainWindow(Session(), UiSettings())
    window.session.apply(
        "Schriftzug",
        [
            OperationDraft(
                op="create_label",
                inputs=(),
                params={"text": "Solidon3D", "size": 60.0, "font": "DejaVu Sans"},
            )
        ],
    )
    window.session.wait_for_idle()
    window.session.apply(
        "Zerlegen",
        [OperationDraft(op="split_bodies", inputs=("obj_1",), params={"count": 10})],
    )
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)
    assert result.stopped_at is None and len(result.scene.objects) == 10

    # Der Befund der gründlichen Suche, je Buchstabe einer — hier über den
    # Nachschub statt über zehn Schichtanalysen, denn geprüft wird die Zeile.
    window.report.add_findings(
        [
            Finding(
                code="orient.searched",
                severity="info",
                message="Ausrichtung über die Schichtanalyse gesucht.",
                object_id=body,
                values={"candidates": 26, "support": round(0.1 * index, 2)},
            )
            for index, body in enumerate(result.scene.objects)
        ]
    )

    report = window.report
    rows = [report.list.item(row) for row in range(report.list.count())]
    # Seit dem 20.09.2026 trägt jeder Körper mit belegten Flächen auch den
    # Hinweis auf die Formabweichung — ein zweites Zehnerbündel; geprüft wird
    # die Zeile, die dieser Test nachgeschoben hat.
    bundles = [item for item in rows if item.text().startswith("(10) Ausrichtung")]
    assert len(bundles) == 1, [item.text() for item in rows]
    (bundle,) = bundles
    assert bundle.text() == "(10) Ausrichtung über die Schichtanalyse gesucht.", (
        "die Zahl davor in Klammern, der Satz einmal, kein einzelner Körpername"
    )
    bodies = bundle.data(_BODIES_ROLE)
    assert bodies is not None and len(bodies) == 10, "die Zeile kennt alle ihre Körper"
    assert "Solidon3D 1" in bundle.toolTip() and "Solidon3D 10" in bundle.toolTip(), (
        "und der Tooltip nennt sie beim Namen"
    )
    assert not any(
        item.text() == "Ausrichtung über die Schichtanalyse gesucht." for item in rows
    ), "keine der zehn Einzelzeilen bleibt daneben stehen"

    QTest.mouseClick(
        report.list.viewport(),
        Qt.MouseButton.LeftButton,
        pos=report.list.visualItemRect(bundle).center(),
    )
    assert set(window.object_tree.selected_objects()) == set(bodies), (
        "der Klick wählt alle Körper der Zeile, nicht den ersten zufälligen"
    )
    window.wait_for_workers()


def test_a_bundle_never_discards_different_actions(qt_app: QApplication) -> None:
    """Wortgleiche Fehler mit verschiedenen Auswegen bleiben getrennt.

    Der erste Gruppenschlüssel kannte die Vorschläge nicht. Acht Fehler wurden
    eine Zeile und der künstliche Befund bekam gar keine Handlung, sobald sich
    nur ein Vorschlag unterschied. Damit verlor eine verdichtete Fehlerzeile
    genau den Ausweg, den Regel 17 verlangt.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    first = Action(id="first_way", label="Ersten Ausweg verwenden")
    second = Action(id="second_way", label="Zweiten Ausweg verwenden")
    findings = tuple(
        Finding(
            code="probe.actionable",
            severity="error",
            message="Dieser Wert braucht eine Korrektur.",
            object_id="obj_1",
            op_id=4,
            suggestions=(action,),
        )
        for action in (first, second)
        for _ in range(4)
    )
    panel = ReportPanel()
    try:
        panel.show_result(EvaluationResult(scene=Scene(report=Report(findings=findings))))

        assert panel.list.count() == 2, "jeder andere Ausweg bildet ein eigenes Bündel"
        kept = {
            panel.list.item(row).data(Qt.ItemDataRole.UserRole).suggestions
            for row in range(panel.list.count())
        }
        assert kept == {(first,), (second,)}, "keine Fehlerzeile verliert ihre Handlung"
    finally:
        panel.deleteLater()


def test_a_bundle_over_different_places_claims_no_single_place(qt_app: QApplication) -> None:
    """Vier gleiche Warnungen an vier Stellen sind eine gezählte Zeile — ohne
    erfundenen Sammelort.

    Bis zum 11.09.2026 trennten Ort und Merkmal die Gruppen; seit Roberts
    Ansage („gleiche Meldungen zusammenfassen") zählt der Satz. Was die Zeile
    dafür **nicht** tun darf: mit dem ersten der vier Orte oder Merkmale
    dastehen — ein Klick flöge dann zu einer zufälligen Stelle. Sie trägt
    keinen Ort und keine Merkmale; der Körper bleibt, denn er ist allen
    gemeinsam.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    findings = tuple(
        Finding(
            code="probe.located",
            severity="warning",
            message="Diese Stelle braucht Aufmerksamkeit.",
            object_id="obj_1",
            op_id=4,
            feature_ids=(f"face_{index}",),
            location=(float(index), 0.0, 0.0),
        )
        for index in range(4)
    )
    panel = ReportPanel()
    try:
        panel.show_result(EvaluationResult(scene=Scene(report=Report(findings=findings))))

        assert panel.list.count() == 1, "vier gleiche Sätze sind eine Zeile"
        item = panel.list.item(0)
        assert item.text().startswith("(4) Diese Stelle braucht Aufmerksamkeit.")
        shown: Finding = item.data(Qt.ItemDataRole.UserRole)
        assert shown.location is None, "der erste von vier Orten wäre ein erfundener Sammelort"
        assert shown.feature_ids == ()
        assert shown.object_id == "obj_1", "der gemeinsame Körper bleibt das Klickziel"
    finally:
        panel.deleteLater()


def test_a_bundle_keeps_every_members_value_in_its_tooltip(qt_app: QApplication) -> None:
    """Vier Messungen werden eine Zeile; die Zahlen stehen je Mitglied im Tooltip.

    Die Zeile trägt die Zahl und den Satz, nicht den Wert des ersten
    zufälligen Mitglieds — vier Wände von 0,4 bis 0,7 mm sind vier Zahlen,
    und keine davon darf als *die* Wandstärke der Zeile dastehen.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    def shown(values: tuple[float | str | TranslatableText, ...]) -> list[Finding]:
        findings = tuple(
            Finding(
                code="probe.measured",
                severity="warning",
                message="Diese Stelle ist zu dünn.",
                object_id="obj_1",
                op_id=4,
                values={"wall_mm": value},
            )
            for value in values
        )
        panel.show_result(EvaluationResult(scene=Scene(report=Report(findings=findings))))
        return [
            panel.list.item(row).data(Qt.ItemDataRole.UserRole) for row in range(panel.list.count())
        ]

    panel = ReportPanel()
    try:
        bundled = shown((0.4, 0.5, 0.6, 0.7))
        assert len(bundled) == 1, "vier gleiche Sätze sind eine Zeile"
        assert "wall_mm" not in bundled[0].values, "kein zufälliger Wert an der Sammelzeile"
        assert bundled[0].values["count"] == 4
        tooltip = panel.list.item(0).toolTip()
        for value in ("0,4", "0,5", "0,6", "0,7"):
            assert value in tooltip, f"{value} fehlt im Tooltip: {tooltip!r}"
    finally:
        panel.deleteLater()


def test_identical_findings_bundle_from_two_and_never_across_severity(
    qt_app: QApplication,
) -> None:
    """Zwei gleiche Meldungen sind schon eine gezählte Zeile (Robert, 11.09.2026).

    Und gleicher Wortlaut mit anderem Schweregrad gehört nie ins selbe
    Bündel — eine Warnung, die in 118 Hinweisen aufgeht, wäre verschluckt.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    def shown(findings: tuple[Finding, ...]) -> list[str]:
        panel.show_result(EvaluationResult(scene=Scene(report=Report(findings=findings))))
        return [panel.list.item(row).text() for row in range(panel.list.count())]

    def echo(count: int, severity: str = "info") -> tuple[Finding, ...]:
        return tuple(
            Finding(
                code="mesh.gap_closed", severity=severity, message="Eine Lücke wurde geschlossen"
            )  # type: ignore[arg-type]
            for _ in range(count)
        )

    def orphans(count: int) -> tuple[Finding, ...]:
        return tuple(
            Finding(
                code="perceive.orphaned",
                severity="info",
                message=(
                    "Ein Formdetail ist nach diesem Schritt nicht mehr automatisch "
                    "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
                    "Bearbeitung bleibt erhalten."
                ),
                object_id="obj_1",
                op_id=7,
                values={"feature": f"face_{index}"},
            )
            for index in range(count)
        )

    panel = ReportPanel()
    try:
        assert shown(echo(1)) == ["Eine Lücke wurde geschlossen"], "eine Zeile trägt keine Zahl"
        assert shown(echo(2)) == ["(2) Eine Lücke wurde geschlossen"], "ab zwei wird gezählt"
        assert len(shown(echo(4) + echo(1, "warning"))) == 2, (
            "gleicher Wortlaut, anderer Schweregrad — zwei Zeilen"
        )
        assert shown(orphans(1))[0].startswith("Ein Formdetail ist")
        assert shown(orphans(2))[0].startswith("(2) Formdetails sind")
        assert shown(orphans(4))[0].startswith("(4) Formdetails sind")
    finally:
        panel.deleteLater()


def test_the_report_writes_a_volume_that_says_something(qt_app: QApplication) -> None:
    """„wasserdicht · 0,0 cm³ · 1 Teil" stand über einem Teil von 4 mm³.

    Die Zeile rechnete selbst — ``format_decimal(volume / 1000.0, 1)`` mit
    festem „cm³" dahinter. Zwei Fehler in einer Zeile: Unter einem
    Kubikzentimeter sagt eine Nachkommastelle Kubikzentimeter nichts mehr, und
    in Zoll stand die Zahl auch dann in Kubikzentimetern, wenn jede Länge
    daneben in Zoll gemessen war (§19.3). Der Kern beantwortet beide Fragen;
    diese Karte fragt ihn jetzt.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui import labels
    from app.ui.panels import ReportPanel

    def shown(extents: tuple[float, float, float]) -> str:
        box = MeshData.of(trimesh.creation.box(extents=extents))
        scene = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Teil", mesh=box)})
        panel.show_result(EvaluationResult(scene=scene))
        return panel.facts.text()

    panel = ReportPanel()
    try:
        tiny = shown((2.0, 2.0, 1.0))
        assert "mm³" in tiny, f"ein Teil von 4 mm³ steht als: {tiny!r}"
        assert "0,0" not in tiny, "eine Null mit Komma ist keine Auskunft"

        assert "8,0 cm³" in shown((20.0, 20.0, 20.0)), "im gewohnten Bereich bleibt es cm³"

        labels.set_display_unit("in")
        try:
            inches = shown((20.0, 20.0, 20.0))
        finally:
            labels.set_display_unit("mm")
        assert "in³" in inches, f"in Zoll steht Kubikzoll da, nicht: {inches!r}"
    finally:
        panel.deleteLater()


def test_the_object_tree_draws_its_bodies_once_per_shape(qt_app: QApplication) -> None:
    """Ein Bild je Form, nicht je Auswertung.

    Gerendert wird über den Hash des Körpers: „obj_1" bleibt dasselbe Objekt,
    wenn sich seine Wandstärke ändert — sein Bild nicht. Ohne den Vorrat
    zeichnete jede Auswertung alles neu, und das kostet bei einem gescannten
    Teil achtzig Millisekunden je Zeile im Hauptthread.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ObjectTree

    box = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    scene = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Klotz", mesh=box)})
    result = EvaluationResult(scene=scene, object_hashes={"obj_1": "abc"})

    tree = ObjectTree()
    try:
        tree.show_scene(result)
        # Der Baum steht sofort; die Bilder kommen nach — seit dem
        # 16.09.2026 aus einem Arbeiter, also wird auf sie gewartet.
        assert tree.tree.topLevelItemCount() == 1
        tree._render_pending()
        assert tree.wait_for_previews()
        assert len(tree._previews) == 1

        tree.show_scene(result)
        tree._render_pending()
        assert tree.wait_for_previews()
        assert len(tree._previews) == 1, "derselbe Körper wurde zweimal gezeichnet"
    finally:
        tree.deleteLater()


def test_a_hidden_body_keeps_its_own_mark(qt_app: QApplication) -> None:
    """Ein ausgeblendetes Objekt hat gerade nichts zu zeigen — es behält das
    Zeichen, das sagt, warum (Regel 18: Zeichen und Wort, nie Farbe allein)."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ObjectTree

    box = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    scene = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Klotz", mesh=box)})
    tree = ObjectTree()
    try:
        tree.set_hidden(frozenset({"obj_1"}))
        tree.show_scene(EvaluationResult(scene=scene))

        assert not tree._pending, "für ein ausgeblendetes Objekt wird nichts gerendert"
        assert tr("ausgeblendet") in tree.tree.topLevelItem(0).text(0)
    finally:
        tree.deleteLater()


def test_a_theme_change_redraws_the_previews(qt_app: QApplication) -> None:
    """Die Bilder sind SVG mit eingebackenen Farben — ein helles Teil auf
    hellem Grund ist kein Bild mehr."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ObjectTree

    box = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    scene = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Klotz", mesh=box)})
    tree = ObjectTree()
    try:
        tree.show_scene(EvaluationResult(scene=scene, object_hashes={"obj_1": "abc"}))
        tree._render_pending()
        assert tree.wait_for_previews()
        assert tree._previews

        tree.set_theme("light")
        assert not tree._previews, "der Vorrat gehört dem alten Thema"
    finally:
        tree.deleteLater()


def test_nothing_is_fitted_before_a_build_volume_exists(qt_app: QApplication) -> None:
    """Ein Einpassen ohne Bauraum zählt nicht als erledigt.

    Das Fenster baut die Ansicht auf, bevor ein Druckerprofil gilt. Passte man
    dort ein, gäbe es nichts zu messen — und der Zustand stünde danach auf
    „schon eingepasst", sodass das erste echte Projekt nie eingepasst würde.
    Genau so gemessen: ``_fitted_to`` sagte „bed", und die Kamera stand
    unverändert anderthalb Millimeter vom Ursprung entfernt.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        renderer = RecordingRenderer()
        viewport.renderer = renderer
        viewport._fit_once_for(None)

        assert renderer.reset_bounds == [], "ohne Bauraum wird nicht eingepasst"
        assert viewport._fitted_to == "", "und nichts gilt als erledigt"
    finally:
        viewport.deleteLater()


def test_the_feature_legend_reads_like_the_object_tree(window: MainWindow) -> None:
    """Eine Legende aus ``face_10`` und ``pin_3`` ist eine Debug-Ausgabe.

    Die Merkmalskarte führt ihre Stufen als Provenienz-IDs — richtig für die
    Karte, falsch für die Legende darunter. Bei einem Gehäuse standen dort
    vierundzwanzig bunte Kacheln über die volle Fensterbreite: „ohne Merkmal",
    elf Flächen, fünf Bohrungen, ein Deckelinneres, vier Stifte, alphabetisch
    sortiert, also ``face_10`` und ``face_11`` zwischen ``face_1`` und
    ``face_2``.

    Jetzt übersetzt das Fenster die Kennungen in dieselben Namen, die im
    Objektbaum stehen, und die Liste bekommt einen Deckel.
    """
    from app.core.perceive.maps import AnalysisMap

    analysis = AnalysisMap(
        kind="features",
        title="Merkmale",
        values=(0.0, 1.0, 2.0),
        unit="",
        low=0.0,
        high=2.0,
        categories=("ohne Merkmal", "hole_1", "face_2"),
    )
    window.analysis_bar.show_legend(analysis, {"hole_1": "Bohrung 1 · ⌀4,2 mm"})

    labels = [label for label, _colour in window.analysis_bar.legend.entries]
    assert "Bohrung 1 · ⌀4,2 mm" in labels, "was einen Namen hat, trägt ihn"
    assert "face_2" in labels, "und was keinen hat, bleibt lesbar"


def test_a_long_legend_says_how_much_it_leaves_out(window: MainWindow) -> None:
    """Eine gekürzte Liste, die ihre Kürzung verschweigt, behauptet
    Vollständigkeit."""
    from app.core.perceive.maps import AnalysisMap
    from app.ui.analysis_bar import LEGEND_MAX_ENTRIES

    many = tuple(f"feature_{index}" for index in range(LEGEND_MAX_ENTRIES + 5))
    analysis = AnalysisMap(
        kind="features",
        title="Merkmale",
        values=tuple(float(index) for index in range(len(many))),
        unit="",
        low=0.0,
        high=float(len(many) - 1),
        categories=many,
    )
    window.analysis_bar.show_legend(analysis)

    labels = [label for label, _colour in window.analysis_bar.legend.entries]
    assert len(labels) == LEGEND_MAX_ENTRIES + 1, "acht Felder und ein Rest"
    assert "5" in labels[-1], "der Rest wird gezählt, nicht verschwiegen"


def test_the_angle_maps_write_the_degree_sign(window: MainWindow) -> None:
    """„45°", nicht „45 grad" — wie überall sonst im Programm."""
    from app.core.perceive.maps import AnalysisMap

    analysis = AnalysisMap(
        kind="overhang",
        title="Überhang",
        values=(0.0, 45.0, 90.0),
        unit="°",
        low=0.0,
        high=90.0,
    )
    window.analysis_bar.show_legend(analysis)

    labels = [label for label, _colour in window.analysis_bar.legend.entries]
    assert all("grad" not in label for label in labels)
    assert any(label.endswith("°") for label in labels)


def test_a_finding_says_which_step_reported_it(window: MainWindow) -> None:
    """Die Liste sortiert nach Schwere — Sätze aus verschiedenen Schritten
    stehen also untereinander.

    Bei ``weg3-generiert-aufbereiten`` liest sich das als Widerspruch: „Das
    Modell ist nicht geschlossen." direkt neben „Eine offene Stelle ist
    geschlossen und damit fort." Beides stimmt, das eine kommt vom Einlesen, das
    andere von der Reparatur — und das stand nirgends. ``Finding`` trägt seine
    ``op_id`` seit je; gezeigt wurde sie nicht.

    Im Tooltip und nicht in der Zeile: die trägt schon Kennzahlen, und der
    Bericht ist die Ansicht, die ruhig bleiben muss.

    **Mit einem Netz, das einen Befund trägt.** Die Platte der Fixture ist
    seit dem 14.09.2026 ohne einen — das Verschweißen doppelter Punkte beim
    Lesen ist kein Befund mehr (B16) —, und ein Test über eine leere Liste
    prüft nichts. `broken_open.stl` meldet beim Einlesen, dass es nicht
    geschlossen ist, mit der Nummer des Schritts.
    """
    from PySide6.QtCore import Qt

    window.session.import_model(MESHES / "broken_open.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())
    report = window.report
    listed = [
        report.list.item(row)
        for row in range(report.list.count())
        if report.list.item(row).data(Qt.ItemDataRole.UserRole) is not None
    ]
    with_step = [
        item
        for item in listed
        if getattr(item.data(Qt.ItemDataRole.UserRole), "op_id", None) is not None
    ]
    assert with_step, "kein Befund im Bericht trägt eine Operationsnummer"

    # Die genaue Wendung, nicht bloß die Zahl: eine „2" steckt auch in
    # „2,40 mm", und ein Test, der darauf prüft, besteht auch ohne die Angabe.
    # (Genau das ist bei der Gegenprobe passiert.)
    from app.i18n import tr

    for item in with_step:
        finding = item.data(Qt.ItemDataRole.UserRole)
        wanted = f"{tr('aus Operation')} {finding.op_id}"
        assert wanted in item.toolTip(), (
            f"{finding.message!r} nennt seinen Schritt nicht: {item.toolTip()!r}"
        )


def test_the_context_menu_follows_the_titles_like_the_menu_bar() -> None:
    """Das Kontextmenü ordnete nach dem internen englischen Namen.

    ``REGISTRY.all()`` sortiert danach, und ``operations_for_object`` gab das
    ungefiltert weiter: „An Merkmal ausrichten", „Textur aufbringen", „Auf dem
    Bett anordnen", „Slot zuweisen" — dieselbe Zufallsfolge, die auch die
    Befehlspalette zeigte, während die Menüleiste daneben nach Titel sortiert.
    Drei Wege in dieselbe Funktion, zwei Ordnungen.

    Verglichen wird mit ``i18n.sort_key``, dem Schlüssel der Menüleiste: „Ü"
    steht im Zeichensatz hinter „z", und „Überhangfächer" landete roh
    verglichen hinter allem anderen.
    """
    from app.i18n import sort_key
    from app.ui.panels import ObjectTree

    titles = [str(spec.title) for spec in ObjectTree.operations_for_object(None)]  # type: ignore[arg-type]
    assert titles, "ohne Operationen prüft dieser Test nichts"
    assert titles == sorted(titles, key=sort_key), "das Kontextmenü folgt nicht dem Titel"
    assert any(title.startswith("Ü") for title in titles), (
        "ohne Umlaut am Wortanfang prüft der Vergleich den Sortierschlüssel nicht"
    )


def test_an_empty_report_offers_nothing_to_filter(qt_app: QApplication) -> None:
    """Der leere Bericht zeigte Suchfeld, Filterauswahl und einen leeren Kasten.

    Drei Bedienelemente, von denen keines etwas tun kann, und der einzige Satz
    mit Inhalt — „Keine Befunde." — stand darüber wie eine Überschrift. Das ist
    der häufigste Zustand des Berichts, nicht ein Randfall.

    Die Schwelle ist zwei: Bei einem einzigen Befund kann ein Filter nur ihn
    treffen oder die Zeile „Kein Befund passt zu …" erzeugen.
    """
    from app.ui.panels import FILTER_FROM, ReportPanel

    finding = Finding(
        code="arrange.out_of_build_volume",
        severity="warning",
        message="Ein Objekt steht über den Bauraum hinaus.",
        object_id="obj_1",
        values={"object": "Halter"},
    )
    panel = ReportPanel()
    try:
        panel.show_result(None)
        assert panel.list.isHidden(), "der leere Kasten steht noch da"
        assert panel.search.isHidden(), "gesucht wird in nichts"
        assert panel.severity.isHidden(), "gefiltert auch"
        assert panel.summary.text(), "und der Satz, der etwas sagt, bleibt"

        panel.add_findings([finding])
        assert not panel.list.isHidden(), "ein Befund gehört gezeigt"
        assert panel.search.isHidden(), f"ein Filter für {FILTER_FROM - 1} Befund"

        # Ein anderer Satz — derselbe würde seit dem 11.09.2026 mit dem
        # ersten zu einer gezählten Zeile, und die Filter gelten Zeilen.
        second = Finding(
            code="arrange.collision",
            severity="warning",
            message="Zwei Objekte überschneiden sich.",
            values={"a": "Halter", "b": "Deckel"},
        )
        panel.add_findings([second])
        assert not panel.search.isHidden(), "ab zwei Zeilen gibt es etwas zu filtern"
        assert not panel.severity.isHidden()

        # Und ein Filter, der wieder verschwindet, nimmt seine Wirkung mit:
        # sonst bliebe eine Auswahl gesetzt, die niemand mehr zurücknehmen kann.
        panel.search.setText("Bauraum")
        panel.severity.setCurrentIndex(1)
        panel.show_result(None)
        assert panel.search.text() == "", "der Suchbegriff überlebt sein Feld"
        assert panel.severity.currentIndex() == 0, "und die Stufe ihre Auswahl"
    finally:
        panel.deleteLater()


def test_the_object_tree_gives_the_names_the_larger_half(qt_app: QApplication) -> None:
    """Beide Körper des ersten Beispiels standen als derselbe Text da.

    Der Kommentar über der Kopfzeile sagt: „Die Maßspalte nimmt, was sie
    braucht; der Rest gehört den Namen." Gegolten hat er nicht —
    ``stretchLastSection`` steht auf Qts Vorgabe ``True`` und überstimmt das
    ``ResizeToContents`` der letzten Spalte. Gemessen: 128 zu 128 bei 258 Pixeln
    Baumbreite, und nach Abzug von Einzug und Vorschaubild blieben für
    „Gehäuseboden" und „Gehäuseboden (Kopie) Prüfstück" dieselbe abgeschnittene
    Zeichenkette.

    Den Deckel nur abzuschalten kippt es um: dann nimmt die Maßspalte ihre
    Inhaltsbreite, und bei „60 x 40 x 12 mm" waren das 186 von 258 — 70 für den
    Namen. Geprüft wird deshalb das Verhältnis und nicht der Schalter: Der Name
    behält die Mehrheit, das Maß bekommt höchstens seinen Anteil, und über die
    Breite hinweg bleibt beides so.
    """
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.panels import MEASURE_SHARE, ObjectTree

    panel = ObjectTree()
    try:
        panel.resize(258, 400)
        panel.show()
        for name, size in (
            ("Gehäuseboden", "60 x 40 x 12 mm"),
            ("Gehäuseboden (Kopie) Prüfstück", "20 x 20 x 5 mm"),
        ):
            panel.tree.addTopLevelItem(QTreeWidgetItem([name, size]))
        QApplication.processEvents()

        header = panel.tree.header()
        assert not header.stretchLastSection(), (
            "der Deckel überstimmt jede Einstellung der letzten Spalte"
        )
        for width in (258, 420, 700):
            panel.resize(width, 400)
            QApplication.processEvents()
            panel._size_columns()
            QApplication.processEvents()
            names, measures = header.sectionSize(0), header.sectionSize(1)
            assert names > measures, f"bei {width} px: Name {names}, Maß {measures}"
            assert measures <= int(panel.tree.viewport().width() * MEASURE_SHARE) + 1, (
                f"bei {width} px nimmt die Maßspalte {measures} und damit mehr als ihren Anteil"
            )
    finally:
        panel.deleteLater()


def test_the_layer_readout_follows_the_unit(qt_app: object) -> None:
    """Die Zeile der Schichtanalyse baute ihre Einheit selbst.

    `f"{layer.area:.0f} mm²"` stand dort, und daneben `z {length(layer.z)}` —
    dieselbe Zeile mit einer Länge, die umschaltet, und einer Fläche, die es
    nicht tut. Geprüft wird an der echten Leiste, nicht an einem nachgebauten
    Satz.
    """
    from app.core.types import LayerInfo, SliceResult
    from app.ui.analysis_bar import LayerBar
    from app.ui.labels import set_display_unit

    bar = LayerBar()
    # Eingeschaltet wie im Fenster, sonst bleibt die Zeile leer.
    bar.set_active(True)
    layer = LayerInfo(z=1.0, contours=(), area=4334.0, overhang_area=0.0, islands=(), min_width=1.0)
    bar.show_result(SliceResult(layers=(layer,), support_volume=0.0, first_layer_area=4334.0))

    try:
        set_display_unit("mm")
        bar._show_readout()
        assert "4334 mm²" in bar.readout.text(), bar.readout.text()

        set_display_unit("in")
        bar._show_readout()
        assert "6,72 in²" in bar.readout.text(), bar.readout.text()
        assert "mm²" not in bar.readout.text()
    finally:
        set_display_unit("mm")


def test_a_selected_body_moves_by_dragging_it(window: MainWindow) -> None:
    """Auswählen, anfassen, ziehen — ohne vorher ein Werkzeug zu holen.

    **Robert am 23.08.2026:** „Das Verschieben eines 3D-Modellkörpers ist noch
    bisschen kompliziert, man soll es auswählen und dann zuschlagen ziehen
    verschieben können oder prüfen wie andere CAD Programme das machen."

    Der Weg war: Körper anklicken → *Bewegen* in der Werkzeugzeile → am Griff
    ziehen. Drei Schritte, und der mittlere ist der, den niemand erwartet: In
    PrusaSlicer, OrcaSlicer und Cura zieht man ein Objekt direkt. Ihre Gizmos
    (nachgelesen in ihren eigenen Sprachkatalogen: „Gizmo move: Press to snap
    by 1mm", „Gizmo-Move") sind für das **Genaue** da — für achsweises
    Verschieben und Rasten —, nicht für den ersten Zug.

    **In der Bettebene und nicht frei im Raum.** Ein Körper, den man beim
    Ziehen unbeabsichtigt anhebt, liegt danach nicht mehr auf dem Bett, und das
    merkt man erst beim Schneiden. Die Höhe bleibt dem Griff und dem Dialog.

    **Ein Zug, ein Schritt im Verlauf** (Regel 2, §15.5): Was während des Zugs
    im Bild passiert, ist eine Vorschau; die Operation entsteht beim Loslassen.
    """
    select_plate(window)
    viewport = window.viewport
    chosen = window.object_tree.selected()
    assert chosen is not None, "ohne Auswahl prüft der Test nichts"

    steps: list[Any] = []
    viewport.transformDragged.connect(steps.append)

    # **Über den Weltpunkt und nicht über Bildschirmkoordinaten.** Offscreen
    # gibt es keinen Renderer, und ein Pick über einem nie gezeichneten Bild
    # trifft nichts — ein Test mit Pixelkoordinaten prüfte hier die
    # Testumgebung.
    entry = window.session.last_result.scene.objects[chosen]
    middle = entry.mesh.bounds.centre

    assert viewport.begin_body_drag_at(middle), "auf dem gewählten Körper beginnt ein Zug"
    viewport.continue_body_drag_at((middle[0] + 12.0, middle[1] + 5.0))
    viewport.finish_body_drag()

    assert steps, "aus dem Zug wurde kein Schritt"
    versatz = steps[-1].offset
    assert versatz[0] != 0.0 or versatz[1] != 0.0, f"nichts bewegt: {versatz}"
    assert versatz[2] == 0.0, f"die Höhe gehört dem Griff, nicht dem Zug: {versatz}"


class _FlatLook:
    """Ein Renderer, der fast waagerecht auf das Bett blickt.

    Der Sichtstrahl läuft in y und fällt je hundert Millimeter nur fünf ab
    (rund drei Grad); Bildschirm-x ist Welt-x, Bildschirm-y ist Welt-z. Genau
    der Blick, mit dem man die Rückwand eines Halters ansieht.
    """

    def display_to_world(self, x: float, y: float, depth: float) -> tuple[float, float, float]:
        return (
            float(x) / 10.0,
            -50.0 + 100.0 * float(depth),
            20.0 - float(y) / 10.0 - 5.0 * float(depth),
        )


def test_a_flat_look_at_the_bed_drags_beside_the_pointer_not_into_the_depth(
    window: MainWindow,
) -> None:
    """Robert, 16.09.2026: „beim verschieben von körpern springen sie auch
    einfach mal wohin" — mit dem Teil von vorn angesehen und direkt gepackt.

    Der Zug schnitt den Sichtstrahl mit der waagerechten Ebene durch den
    Griffpunkt. Fast waagerecht geblickt, trifft der Strahl sie so flach, dass
    zwölf Bildpunkte nach oben zur Tiefe werden — gemessen an dieser Attrappe
    vor dem Fix: 26 mm für 12 Bildpunkte, bei einem Blick von drei Grad; je
    flacher, desto mehr, bis der Schnitt hinter der Kamera liegt. Jetzt zieht der Zug bei flachem
    Blick in der Bildschirmebene — seitlich folgt der Körper dem Zeiger, in
    die Tiefe geht er nicht.
    """
    viewport = window.viewport
    real = viewport.renderer
    viewport.renderer = _FlatLook()  # type: ignore[assignment]
    try:
        # Der Griffpunkt, wie ihn ``begin_body_drag_at`` nach dem Pick setzt.
        viewport._body_drag_from = (30.0, 0.0, 15.0)
        start = viewport._plane_point(300, 50)
        sideways = viewport._plane_point(320, 50)
        upwards = viewport._plane_point(300, 38)
        assert start is not None and sideways is not None and upwards is not None
        assert sideways[0] - start[0] == pytest.approx(2.0, abs=0.01), (
            "seitlich folgt er dem Zeiger"
        )
        assert abs(sideways[1] - start[1]) < 0.01
        assert abs(upwards[1] - start[1]) < 1.0, (
            f"nach oben gezogen sprang er in die Tiefe: {upwards}"
        )
        assert abs(upwards[0] - start[0]) < 0.01
    finally:
        viewport._body_drag_from = None
        viewport.renderer = real


def test_a_drag_beside_the_body_still_turns_the_camera(window: MainWindow) -> None:
    """Neben dem Körper bleibt Ziehen, was es war.

    Sonst wäre das Verschieben ein Modus mit anderem Namen: Wer die Ansicht
    drehen will, dürfte nicht erst wegklicken müssen. Dieselbe Trennung machen
    die Slicer — auf dem Objekt bewegt es, daneben führt es die Kamera.
    """
    select_plate(window)
    viewport = window.viewport

    # Weit außerhalb: dort liegt kein Körper.
    assert not viewport.begin_body_drag_at((5000.0, 5000.0, 5000.0)), "daneben beginnt kein Zug"
    assert not viewport.begin_body_drag_at(None), "und ohne Treffer erst recht nicht"


def test_a_click_into_a_hole_selects_the_hole(window: MainWindow) -> None:
    """Wer eine Bohrung sieht und hineinklickt, meint sie.

    **Robert am 23.08.2026:** „Wenn ich ein 3D Modell auswähle und dann eine
    Bohrung in dem 3D Modell auswähle, wird die Bohrung nicht selektiert und
    nicht hervorgehoben." Auf die Frage, ob er auf die Wand oder ins Loch
    klickt: „beides, es sollte in beiden fällen gehen."

    **Der Klick auf die Wand ging schon**; gemessen trifft ``_feature_at`` dort
    das Merkmal. Der Klick ins Loch nicht — dort ist kein Dreieck der Bohrung,
    der Strahl trifft die Fläche dahinter oder die Platte darunter, und von der
    Bohrungsmitte aus ist ihre Wand einen **Radius** entfernt: bei dieser
    Bohrung 2,6 mm gegen 0,95 mm Reichweite.

    Die Reichweite dafür zu vergrößern wäre falsch — sie beantwortet „wie weit
    daneben zählt noch als darauf", und die Antwort soll klein bleiben. Gefragt
    wird stattdessen etwas anderes: **Steht der Punkt innerhalb des
    Bohrungszylinders?**
    """
    select_plate(window)
    viewport = window.viewport
    entry = window.session.last_result.scene.objects[window.object_tree.selected()]
    bohrungen = [name for name, feature in entry.features.items() if feature.kind == "hole"]
    assert bohrungen, "ohne Bohrung prüft dieser Test nichts"

    bohrung = entry.features[bohrungen[0]]
    mitte = bohrung.params["centre"]
    radius = float(bohrung.params["diameter"]) / 2.0

    auf_der_wand = (mitte[0] + radius, mitte[1], mitte[2])
    im_loch = (mitte[0], mitte[1], mitte[2])
    assert viewport._feature_at(auf_der_wand) == bohrungen[0], "auf der Wand traf es schon"
    assert viewport._feature_at(im_loch) == bohrungen[0], "und jetzt auch mitten hinein"

    # **Die Gegenprobe, ohne die der Test nichts wert wäre**: Ein Klick neben
    # der Bohrung darf sie nicht wählen. Sonst hätte die neue Frage nur die
    # Reichweite auf den ganzen Körper ausgedehnt.
    daneben = (mitte[0] + radius * 4.0, mitte[1] + radius * 4.0, mitte[2])
    assert viewport._feature_at(daneben) != bohrungen[0], (
        "vier Radien daneben ist nicht mehr diese Bohrung"
    )


def test_loading_a_model_gives_no_detected_feature_an_originator(
    window: MainWindow,
) -> None:
    """Und die Gegenrichtung: Nach ``load`` ist **jedes** erkannte Merkmal neu.

    Ohne den ``touches_features``-Riegel trüge jede Bohrung jedes importierten
    Modells den Lade-Schritt, und „Diesen Schritt ändern" öffnete den
    Lade-Dialog — der falsche Dialog, nur tausendfach und in Weg 1
    (Messung 3d-druck-61).
    """
    result = window.session.last_result
    assert result is not None
    features = [
        (feature_id, feature)
        for entry in result.scene.objects.values()
        for feature_id, feature in entry.features.items()
    ]

    assert features, "die eingelesene Platte trägt Merkmale — sonst prüft der Test nichts"
    assert all(feature.created_by is None for _name, feature in features), {
        name: feature.created_by for name, feature in features if feature.created_by is not None
    }


def _a_keyhole_on_the_plate(window: MainWindow) -> tuple[str, int]:
    """Ein Schlüsselloch bei (10 | 5) auf der Deckfläche — Körper und Schritt."""
    from app.core.scene import OperationDraft

    result = window.session.last_result
    assert result is not None
    object_id = next(iter(result.scene.objects))
    window.session.apply(
        "Schlüsselloch",
        [
            OperationDraft(
                op="insert_keyhole",
                inputs=(object_id,),
                params={"x": 10.0, "y": 5.0, "z": 8.0, "nx": 0.0, "ny": 0.0, "nz": 1.0},
            )
        ],
    )
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    step = window.session.project.document.ops[-1]
    assert step.op == "insert_keyhole"
    return object_id, int(step.id)


def _part_centres(window: MainWindow, object_id: str, step: int) -> dict[str, tuple[float, ...]]:
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[object_id]
    return {
        name: tuple(float(value) for value in feature.params["centre"])
        for name, feature in entry.features.items()
        if feature.created_by == step and feature.kind == "hole"
    }


def test_a_drag_at_a_part_feature_moves_the_whole_part(window: MainWindow) -> None:
    """Der Griff an einer Hälfte des Schlüssellochs versetzt das Schlüsselloch.

    Ein Schlüsselloch bringt zwölf Merkmale mit; wer die runde Tasche anfasst,
    meint das Schlüsselloch (`fenster.md`, „Ein Merkmal aus einem Baustein
    meint den Baustein"). Bis zum 14.09.2026 wurde der Zug ein
    ``move_feature`` auf die Tasche: sie wanderte um fünf Millimeter, der
    Schlitz blieb stehen, und zehn Verrundungen verloren ihre Erkennung —
    gemessen an der Sonde über alle Bausteine. Jetzt gehen die Zahlen in den
    Schritt, wie bei *Baustein verschieben* rechts.

    **Und drehen dreht den Baustein um seinen Anker.** Ein Ring um Z schreibt
    den Winkel, ein Ring um Y die Richtung — dieselbe Rundreise wie am Griff
    der Vorschau eines Grundkörpers, und nach beidem ist der Baustein noch
    gewählt.
    """
    from app.core.geom.transform import TransformSteps

    object_id, step = _a_keyhole_on_the_plate(window)
    before = _part_centres(window, object_id, step)
    assert len(before) == 2, before
    steps_before = len(window.session.project.document.ops)
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, "keyhole_pocket_1")
    for _ in range(40):
        QApplication.processEvents()
    assert window.feature_panel.shown_part_step() == step

    # Der Griff am Merkmal meldet die **neue Mitte** der Tasche — so, wie die
    # Ansicht es nach dem Loslassen tut (``featureMoved``).
    pocket = before["keyhole_pocket_1"]
    window.viewport.featureMoved.emit("keyhole_pocket_1", (pocket[0] + 5.0, pocket[1], pocket[2]))
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()

    ops = window.session.project.document.ops
    assert len(ops) == steps_before, "kein zweiter Schritt — der Baustein ändert seinen eigenen"
    moved = next(entry for entry in ops if entry.id == step)
    assert moved.params["x"] == pytest.approx(15.0), moved.params
    after = _part_centres(window, object_id, step)
    for name, centre in before.items():
        assert after[name][:2] == pytest.approx((centre[0] + 5.0, centre[1]), abs=0.05), name
    assert window.feature_panel.shown_part_step() == step, "der Baustein bleibt gewählt"

    window.viewport.featureTurned.emit("keyhole_pocket_1", "z", 30.0)
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    turned = next(entry for entry in window.session.project.document.ops if entry.id == step)
    assert turned.params["angle"] == pytest.approx(30.0)
    assert (turned.params["x"], turned.params["y"]) == pytest.approx((15.0, 5.0)), (
        "gedreht wird um den eigenen Anker, der bleibt stehen"
    )

    # Und die Bewegen-Leiste geht denselben Weg — ein getippter Versatz.
    window._on_transform_dragged(TransformSteps(offset=(0.0, -2.0, 0.0)))
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    typed = next(entry for entry in window.session.project.document.ops if entry.id == step)
    assert typed.params["y"] == pytest.approx(3.0), typed.params
    assert len(window.session.project.document.ops) == steps_before

    # **Und der Griff hängt auch an einer Verrundung des Schlüssellochs.** Für
    # sich trägt sie keine Operation (``fillet`` steht in keinem
    # ``applies_to``), aber sie kam aus dem Baustein — und der lässt sich
    # bewegen. Der Satz in der Statuszeile sagt, was der Zug tut.
    from app.ui.viewport import gizmo_sentence

    window.object_tree.select_feature(object_id, "fillet_1")
    for _ in range(40):
        QApplication.processEvents()
    at_the_fillet = window.viewport.gizmo_feature()
    assert at_the_fillet is not None and at_the_fillet.id == "fillet_1", (
        "an einem Bausteinmerkmal ohne eigene Operation steht der Griff trotzdem"
    )
    assert window.viewport.moves_as_a_part(at_the_fillet)
    # **Und die Statuszeile sagt es** — gemessen am gesendeten Satz, nicht an
    # der Funktion mit von Hand gesetzter Flagge: Wer in ``set_gizmo`` das
    # ``part=`` vergisst, sendet den Satz über „das gewählte Merkmal".
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.viewport.show_scene(window.session.last_result)
    said: list[str] = []
    window.viewport.gizmoStatus.connect(said.append)
    window.viewport.select(object_id)
    window.viewport.select_feature("fillet_1")
    window.viewport.set_gizmo(True)
    assert said, "der Griff meldet seinen Satz"
    assert "Baustein" in said[-1], said[-1]
    assert said[-1] != gizmo_sentence(at_the_fillet), "nicht der Satz über das eine Merkmal"


def test_a_part_on_a_wall_turns_about_the_wall_and_declines_the_rest(window: MainWindow) -> None:
    """An einem benannten Merkmal dreht der Ring um dessen Achse — und sonst sagt er es.

    Ein Schraubenloch an der Vorderwand (``at_feature`` = Fläche mit Normale
    -Y) trägt keine freie Richtung; seine Achse ist die der Wand. Bis zum
    Review vom 14.09.2026 nahm der Griff die Achse des **gezogenen** Merkmals:
    Der Ring um Z hätte um die Wandachse gedreht, der Ring um Y wäre abgelehnt
    worden — gespiegelt falsch. Jetzt trägt der Ring um Y (die Wandachse), und
    der um Z bekommt einen Satz mit dem Namen des Sitzmerkmals.
    """
    from app.core.scene import OperationDraft

    result = window.session.last_result
    assert result is not None
    object_id, entry = next(iter(result.scene.objects.items()))
    wall = next(
        name
        for name, feature in entry.features.items()
        if feature.kind == "face" and float(feature.params["normal"][1]) < -0.9
    )
    window.session.apply(
        "Schraubenloch",
        [OperationDraft(op="insert_screw_hole", inputs=(object_id,), params={"at_feature": wall})],
    )
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    step = window.session.project.document.ops[-1]
    assert step.op == "insert_screw_hole"
    result = window.session.last_result
    assert result is not None and result.stopped_at is None
    bore = next(
        name
        for name, feature in result.scene.objects[object_id].features.items()
        if feature.created_by == step.id and feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, bore)
    for _ in range(40):
        QApplication.processEvents()

    window.viewport.featureTurned.emit(bore, "y", 30.0)
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    turned = next(entry for entry in window.session.project.document.ops if entry.id == step.id)
    assert turned.params["angle"] == pytest.approx(-30.0), (
        "der Ring um Y dreht um die Wandachse — sie zeigt nach -Y, also mit umgekehrtem Vorzeichen"
    )
    assert turned.params["at_feature"] == wall, "der Sitz bleibt"

    window.viewport.featureTurned.emit(bore, "z", 30.0)
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    same = next(entry for entry in window.session.project.document.ops if entry.id == step.id)
    assert same.params["angle"] == pytest.approx(-30.0), "um Z dreht dieser Baustein nicht"
    assert not any(op.op == "rotate_feature" for op in window.session.project.document.ops), (
        "und es entsteht kein Schritt an der Bohrung allein"
    )
    # ``announce`` schreibt die bleibende Meldung (``_announcement``), nicht
    # den Fortschrittstext der Statusleiste.
    said = window._announcement
    assert wall in said and "dreht sich nur um dessen Achse" in said, said


def test_a_part_without_a_direction_turns_only_where_the_step_can_follow() -> None:
    """Ohne freie Richtung dreht der Ring, wo ``_matrix`` dieselbe Lage rechnet.

    Eine Rippe mit ``nx = ny = nz = 0`` und Achse Z steht aufrecht; ihre Lage
    ist ``frame_of(+Z)`` — die Einheit —, also darf die Rundreise rechnen und
    gibt eine freie Richtung zurück. Der Lochwand-Einhänger hat ein Oben
    (``keeps_up``): Sein freier Zweig dreht um 180 Grad mehr als sein
    Achsenzweig, deshalb bleibt es dort beim Winkel um die Achse — und ein Ring
    um X sagt, was fehlt, statt still zu drehen.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY

    load_operations()
    upright = {
        "x": 1.0,
        "y": 2.0,
        "z": 3.0,
        "nx": 0.0,
        "ny": 0.0,
        "nz": 0.0,
        "axis": "z",
        "angle": 10.0,
    }

    values, why = MainWindow._part_turned(REGISTRY.get("insert_rib"), upright, "z", 20.0, None)
    assert values is not None and why == ""
    assert values["angle"] == pytest.approx(30.0)
    assert (values["nx"], values["ny"], values["nz"]) == pytest.approx((0.0, 0.0, 1.0))
    assert (values["x"], values["y"], values["z"]) == pytest.approx((1.0, 2.0, 3.0))

    values, why = MainWindow._part_turned(
        REGISTRY.get("insert_pegboard_hook"), upright, "z", 20.0, None
    )
    assert values == {"angle": 30.0} and why == "", "ein Baustein mit Oben bleibt im Achsenzweig"

    values, why = MainWindow._part_turned(
        REGISTRY.get("insert_pegboard_hook"), upright, "x", 20.0, None
    )
    assert values is None and why == "direction"


def test_turning_a_slot_from_a_step_changes_that_step(window: MainWindow) -> None:
    """Ein Langloch, das ein Schritt gezogen hat, dreht sich über diesen Schritt.

    Bohrung → Langloch ist ein ``slot_hole``-Schritt; das Langloch trägt ihn
    als ``created_by``. Wer es danach dreht und übernimmt, bekam bis zum
    15.09.2026 einen **zweiten** Schritt obenauf, und der schnitt quer über das
    erste — „habe ich 2 langlöcher" (Robert). Jetzt bekommt der erste Schritt
    den Winkel (§21.2, dieselbe Regel wie beim Baustein), rechnet von der
    Bohrung aus neu, und im Verlauf steht weiter ein Schritt.

    **Nur Geändertes geht in den Schritt.** Das Fenster belegt die Felder mit
    den gemessenen Werten (18,02 für ein Langloch von 18,00); ein Feld, das
    darauf stehen blieb, hat niemand angefasst und wächst das Loch nicht.
    """
    from app.core.geom.prepare_ops import slot_angle_of
    from app.core.scene import OperationDraft

    result = window.session.last_result
    assert result is not None
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    centre = tuple(float(value) for value in entry.features[hole].params["centre"])
    window.session.apply(
        "Zum Langloch ziehen",
        [
            OperationDraft(
                op="slot_hole",
                inputs=(object_id,),
                params={
                    "at_feature": hole,
                    "slot_length": 18.0,
                    "slot_angle": 0.0,
                    "x": centre[0],
                    "y": centre[1],
                    "z": centre[2],
                },
            )
        ],
    )
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    step = window.session.project.document.ops[-1]
    assert step.op == "slot_hole"
    steps = len(window.session.project.document.ops)
    result = window.session.last_result
    assert result is not None and result.stopped_at is None
    slot_id, slot = next(
        (name, feature)
        for name, feature in result.scene.objects[object_id].features.items()
        if feature.kind == "slot"
    )
    assert slot.created_by == step.id
    measured = float(slot.params["length"])
    axis = tuple(float(value) for value in slot.params["axis"])
    where = tuple(float(value) for value in slot.params["centre"])

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, slot_id)
    for _ in range(40):
        QApplication.processEvents()
    # Ein gewähltes Langloch zeigt seine Maße von selbst im Bild; geprüft wird
    # der Weg über die Felder rechts.
    window.end_quiet_placement()
    # Was das Merkmalfenster beim Übernehmen schickt: die gemessene Länge, die
    # gemessene Mitte — und den neuen Winkel. Erst gemeldet und gezeigt, dann
    # übernommen: Übernehmen wartet auf die dargestellte Vorschau (20.09.2026),
    # und ein früher Klick wird nicht nachgeholt.
    turned_values = {
        "at_feature": slot_id,
        "slot_length": measured,
        "slot_angle": 45.0,
        "x": where[0],
        "y": where[1],
        "z": where[2],
    }
    window._on_feature_values_changed("slot_hole", turned_values)
    window._feature_preview.stop()
    window._preview_feature_change()
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    window._apply_from_feature_panel("slot_hole", turned_values)
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()

    ops = window.session.project.document.ops
    assert len(ops) == steps, "kein zweiter Schritt"
    turned = next(entry for entry in ops if entry.id == step.id)
    assert turned.params["slot_angle"] == pytest.approx(45.0)
    assert turned.params["slot_length"] == pytest.approx(18.0), (
        "die unveränderte, gemessene Länge geht nicht in den Schritt"
    )
    result = window.session.last_result
    assert result is not None and result.stopped_at is None
    kinds = [feature.kind for feature in result.scene.objects[object_id].features.values()]
    assert kinds.count("slot") == 1, f"ein Langloch, kein Kreuz: {kinds}"
    after = next(
        feature
        for feature in result.scene.objects[object_id].features.values()
        if feature.kind == "slot"
    )
    assert slot_angle_of(after, axis) == pytest.approx(45.0, abs=0.5)

    # Und der Zug an den Langlochknöpfen geht denselben Weg.
    window._on_slot_dragged(slot_id, 22.0, 45.0)
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    assert len(window.session.project.document.ops) == steps
    longer = next(entry for entry in window.session.project.document.ops if entry.id == step.id)
    assert longer.params["slot_length"] == pytest.approx(22.0)


def test_a_part_stays_chosen_when_its_measures_swap_its_features(window: MainWindow) -> None:
    """Nach *Maße ändern* ist der Baustein noch gewählt — auch mit anderen Merkmalen.

    Ein Steckverbinder als Stift hat andere Merkmale als einer als Bohrung;
    wer die Art umstellt, verliert das angeklickte Merkmal, und der Baum
    stellt nur wieder her, was es noch gibt. Rechts stand danach das leere
    Fenster, und für die nächste Zahl war der Baustein neu zu suchen (Sonde
    an Scharnier, Kabeldurchführung und Steckverbinder, 14.09.2026). Der
    Schritt bleibt derselbe; gewählt wird danach eines seiner Merkmale.
    """
    from app.core.scene import OperationDraft

    result = window.session.last_result
    assert result is not None
    object_id = next(iter(result.scene.objects))
    window.session.apply(
        "Steckverbinder",
        [
            OperationDraft(
                op="insert_snap_connector",
                inputs=(object_id,),
                params={"x": 10.0, "y": 5.0, "z": 8.0, "nx": 0.0, "ny": 0.0, "nz": 1.0},
            )
        ],
    )
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    step = int(window.session.project.document.ops[-1].id)
    result = window.session.last_result
    assert result is not None
    # **Das versprochene Merkmal, keine erkannte Fläche.** Erkannte Flächen des
    # Stifts tragen ebenfalls den Schritt (RM-186), und ihre Kennung kann nach
    # dem Umstellen zufällig wiederkommen — die Probe soll ein Merkmal
    # treffen, das wirklich verschwindet: der Arm, den nur der Stift hat.
    chosen = next(
        name
        for name, feature in result.scene.objects[object_id].features.items()
        if feature.created_by == step and name.startswith("snap_connector_")
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, chosen)
    for _ in range(40):
        QApplication.processEvents()
    assert window.feature_panel.shown_part_step() == step

    # Der Weg des Kunden, hier über die Privatmethoden dahinter nachgestellt —
    # nicht über Feld und Knopf: Der Wert im Merkmalfenster ändert sich, die
    # Vorschau rechnet und zeigt, erst dann übernimmt der Klick (20.09.2026:
    # Übernehmen wartet auf die dargestellte Vorschau, ein früher Klick wird
    # nicht nachgeholt). Was Feld und Knopf selbst tun, prüfen die Fensterfälle
    # in ``test_feature_panel.py``.
    window._on_feature_values_changed("insert_snap_connector", {"kind": "bore"})
    window._feature_preview.stop()
    window._preview_feature_change()
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    window._change_part_step(step, {"kind": "bore"})
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()

    result = window.session.last_result
    assert result is not None
    assert chosen not in result.scene.objects[object_id].features, (
        "die Probe trifft nur, wenn das angeklickte Merkmal wirklich weg ist"
    )
    selected = window.object_tree.selected_features()
    assert selected, "der Baustein ist noch gewählt"
    for owner, name in selected:
        assert result.scene.objects[owner].features[name].created_by == step
    assert window.feature_panel.shown_part_step() == step, "und rechts steht er noch"


def test_a_part_with_one_feature_gets_no_roof(window: MainWindow) -> None:
    """Ein Dach über einer einzigen Zeile ist keins.

    ``insert_printed_thread`` verspricht genau ein Merkmal (``features=[
    "thread"]``), und „Schraubenloch mit Senkung" trägt seine Senkung unter der
    Bohrung — beide Bausteine hatten damit ein Dach über einem einzigen
    direkten Kind, das nur wiederholte, was darunter steht. Angeklickt meinte
    diese Zeile den ganzen Körper, und das Auswahlpanel zeigte alle
    Körperoperationen statt der Bohrung (Befund Robert, 09.09.2026).

    **Der Weg zum Schritt bleibt.** Er steht in ``feature.created_by``, und
    beide Wege dorthin — Doppelklick und „Diesen Schritt ändern" — lesen ihn
    von dort, wenn die Rolle fehlt.
    """
    from app.ui.panels import _STEP_ROLE

    feature_id = _insert_a_thread(window)
    tree = window.object_tree.tree
    step = next(
        entry.id
        for entry in window.session.project.document.ops
        if entry.op == "insert_printed_thread"
    )

    daecher = []
    zeilen = []
    for index in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(index)
        for child_index in range(item.childCount()):
            child = item.child(child_index)
            if child.data(0, _STEP_ROLE) == step:
                daecher.append(child)
            if child.data(1, Qt.ItemDataRole.UserRole) == feature_id:
                zeilen.append(child)

    result = window.session.last_result
    assert result is not None
    feature = next(
        merkmal
        for entry in result.scene.objects.values()
        for kennung, merkmal in entry.features.items()
        if kennung == feature_id
    )
    assert feature.created_by == step, "und der Weg zu seinem Schritt hängt an ihm selbst"
    # **Gezählt, nicht angenommen** (16.09.2026): Das Gewinde verspricht ein
    # Merkmal, doch die Erkennung findet an seiner Stirnfläche auf dieser
    # Maschine eine zweite (22 mm², `created_by` des Schritts) — auf Ubuntu
    # nicht (RM-186). Die Zusage gilt in beide Richtungen: eines ohne Dach,
    # mehrere unter genau einem.
    aus_dem_schritt = [
        kennung
        for entry in result.scene.objects.values()
        for kennung, merkmal in entry.features.items()
        if merkmal.created_by == step
    ]
    if len(aus_dem_schritt) == 1:
        assert not daecher, f"ein Merkmal braucht kein Dach, gefunden: {len(daecher)}"
        assert len(zeilen) == 1, "das Merkmal des Bausteins steht direkt unter seinem Körper"
    else:
        assert len(daecher) == 1, f"mehrere Merkmale, genau ein Dach: {len(daecher)}"
        assert not zeilen, "und keines davon steht daneben direkt unter dem Körper"


def test_a_bore_with_its_countersink_shows_its_own_fields(window: MainWindow) -> None:
    """Eine Bohrung mit ihrer Senkung ist eine Wahl, keine Passung.

    Der Baum stellt die Senkung unter ihre Bohrung, und eine Zeile mit Kind
    meldet seit dem 07.09.2026 **beide** Merkmale („bei allen Dacheinträgen").
    Zwei gemeldete Merkmale las das Fenster als Passung: An der angeklickten
    Bohrung stand der Abstand zu ihrer eigenen Senkung — gemessen 5,20 mm an
    ``plate_countersunk.stl`` — statt ihres Durchmessers, und der Wert, den der
    Kunde ändern wollte, war nirgends zu sehen (Befund Robert, 09.09.2026:
    „hier soll immer nur für das ausgewählte etwas stehen").

    Geprüft wird am **Klick auf die Baumzeile** und nicht an ``show_feature``:
    Die falsche Auskunft entstand ja gerade auf dem Weg dorthin, und wer die
    Methode ruft, geht an ihm vorbei.
    """
    from PySide6.QtWidgets import QLabel

    # Die Fixture hat ``plate_holes.stl`` offen; die gesenkte Platte kommt
    # daneben. Gegriffen wird deshalb am Merkmal und nicht am ersten Eintrag
    # der Szene — beide Körper werden gebraucht, der zweite für die Gegenprobe.
    window.open_path(MESHES / "plate_countersunk.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(
        (kennung, eintrag)
        for kennung, eintrag in result.scene.objects.items()
        if any(merkmal.kind == "cone" for merkmal in eintrag.features.values())
    )
    bohrung = next(kennung for kennung, merkmal in entry.features.items() if merkmal.kind == "hole")
    senkung = next(kennung for kennung, merkmal in entry.features.items() if merkmal.kind == "cone")

    tree = window.object_tree
    zeile = None
    for oben in range(tree.tree.topLevelItemCount()):
        top = tree.tree.topLevelItem(oben)
        assert top is not None
        top.setExpanded(True)
        for index in range(top.childCount()):
            kind = top.child(index)
            if kind is not None and kind.data(1, Qt.ItemDataRole.UserRole) == bohrung:
                zeile = kind
    assert zeile is not None, "die Bohrung steht im Baum"
    tree.tree.clearSelection()
    zeile.setSelected(True)
    QCoreApplication.processEvents()

    # Die Voraussetzung des Falls, ausdrücklich hergestellt: Ohne die zwei
    # gemeldeten Merkmale prüft der Test die Passungsweiche gar nicht.
    assert set(tree.selected_features()) == {(object_id, bohrung), (object_id, senkung)}, (
        "die Zeile bündelt Bohrung und Senkung — sonst gibt es den Fall nicht"
    )
    assert window.feature_panel.feature_id == bohrung, (
        "das Fenster zeigt die angeklickte Bohrung und nicht den Abstand zu ihrer Senkung"
    )
    texte = [
        beschriftung.text()
        for beschriftung in window.feature_panel.findChildren(QLabel)
        if beschriftung.text().strip()
    ]
    assert any("Durchmesser" in text for text in texte), f"kein Maßfeld: {texte}"
    assert not any("Abstand" in text for text in texte), (
        f"die Passungsauskunft steht noch da: {texte}"
    )

    # **Und die Gegenprobe:** Zwei Bohrungen, die keine Kette bilden, bleiben
    # eine Passung — sonst hätte die Weiche die Auskunft ganz abgeschafft,
    # statt sie an der einen Stelle zu unterdrücken, an der sie falsch war.
    anderes_id, getrennt = next(
        (kennung, eintrag)
        for kennung, eintrag in result.scene.objects.items()
        if kennung != object_id
        and sum(merkmal.kind == "hole" for merkmal in eintrag.features.values()) >= 2
    )
    loecher = [
        (anderes_id, kennung)
        for kennung, merkmal in getrennt.features.items()
        if merkmal.kind == "hole"
    ][:2]
    tree.select_features(loecher)
    QCoreApplication.processEvents()
    weiter = [
        beschriftung.text()
        for beschriftung in window.feature_panel.findChildren(QLabel)
        if beschriftung.text().strip()
    ]
    assert any("Abstand" in text for text in weiter), (
        f"zwei getrennte Bohrungen bleiben eine Passung: {weiter}"
    )


def test_the_features_of_a_part_sit_under_its_own_node(window: MainWindow) -> None:
    """Was aus einem Baustein kam, steht im Baum unter ihm.

    Vierzehn Merkmale flach untereinander sagen nicht, welche zusammengehören.
    Der Knoten trägt den Namen des Bausteins und seinen Schritt — und ist damit
    die Zeile, auf die man zeigt, wenn man *ihn* ändern will und nicht eine
    seiner Flächen.

    **Zwei Merkmale, damit es ein Dach gibt.** Ein Baustein mit nur einem
    bekommt seit dem 09.09.2026 keines mehr (siehe der Test darüber); der
    einzige, der hier von Hand läuft, verspricht genau eines. Die zweite Zeile
    kommt deshalb aus einer gestellten Szene — die Bündelung liest allein
    ``created_by``, und der Wert stammt aus dem echten Lauf darüber.
    """
    from app.ui.panels import _STEP_ROLE

    _insert_a_thread(window)
    tree = window.object_tree.tree
    step = next(
        entry.id
        for entry in window.session.project.document.ops
        if entry.op == "insert_printed_thread"
    )

    result = window.session.last_result
    assert result is not None
    object_id, entry = next(
        (kennung, eintrag)
        for kennung, eintrag in result.scene.objects.items()
        if any(merkmal.created_by == step for merkmal in eintrag.features.values())
    )
    aus_dem_schritt = next(
        merkmal for merkmal in entry.features.values() if merkmal.created_by == step
    )
    zweites = dataclasses.replace(aus_dem_schritt, id="thread_zweit")
    window.object_tree.show_scene(
        dataclasses.replace(
            result,
            scene=dataclasses.replace(
                result.scene,
                objects={
                    **result.scene.objects,
                    object_id: dataclasses.replace(
                        entry, features={**entry.features, "thread_zweit": zweites}
                    ),
                },
            ),
        ),
        window.session.project.document,
    )

    nodes = []
    for index in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(index)
        for child_index in range(item.childCount()):
            child = item.child(child_index)
            if child.data(0, _STEP_ROLE) == step:
                nodes.append(child)

    assert len(nodes) == 1, f"genau ein Knoten je Baustein, gefunden: {len(nodes)}"
    # Alle Merkmale des Schritts — das echte Gewinde, auf dieser Maschine auch
    # seine erkannte Stirnfläche (RM-186) — plus das gestellte zweite.
    echte = sum(1 for merkmal in entry.features.values() if merkmal.created_by == step)
    assert nodes[0].childCount() == echte + 1, "und seine Merkmale hängen darunter"
    assert nodes[0].data(1, Qt.ItemDataRole.UserRole) is None, (
        "der Knoten ist selbst kein Merkmal — er ist ihr Dach"
    )

    # **Und ein Klick darauf wählt, was er bündelt** (Konzept „Ein Ort für die
    # Auswahl", E; Robert am 07.09.2026: „bei allen Dach einträgen"). Weil er
    # selbst kein Merkmal ist, meldete er bis dahin gar keines — die Handlungen
    # darunter galten dann nichts. Das Gleichart-Dach und die Bohrungskette
    # stehen in ``test_ui.py``; dieser Fall braucht einen echten Bausteinlauf
    # und gehört deshalb hierher.
    koerper = str(nodes[0].data(0, Qt.ItemDataRole.UserRole))
    darunter = {
        (koerper, str(kind.data(1, Qt.ItemDataRole.UserRole)))
        for index in range(nodes[0].childCount())
        if (kind := nodes[0].child(index)) is not None
    }
    tree.clearSelection()
    nodes[0].setSelected(True)
    assert set(window.object_tree.selected_features()) == darunter, (
        "das Baustein-Dach wählt die Merkmale seines Schritts"
    )
    assert window.object_tree.selected_feature() is None, (
        "es selbst bleibt keines — die Dachzeile ist eine Zeile"
    )


def test_the_layer_tool_takes_the_only_body_there_is(window: MainWindow) -> None:
    """Nach dem Öffnen gibt es ein Teil — und nichts auszuwählen.

    Wer *Schichten* anklickte, bekam einen Regler, der sich ziehen ließ und
    nichts bewegte. Der Grund stand als „Keine Auswahl" in der Statuszeile am
    unteren Fensterrand, also nicht dort, wo er gerade hinsah — und er war
    obendrein eine Frage mit nur einer möglichen Antwort: Es liegt genau ein
    Körper in der Szene.
    """
    # Das Fixture öffnet ``plate_holes.stl`` bereits — genau die Lage nach dem
    # Öffnen einer Datei, um die es hier geht. Ein zweites Laden machte daraus
    # zwei Körper und prüfte den anderen Fall.
    window.session.wait_for_idle()
    window.session.evaluate_now()
    window.object_tree.tree.clearSelection()
    assert window.object_tree.selected() is None, "nothing is selected on purpose"

    window.layer_bar.set_active(True)
    window.session.wait_for_idle()

    # ``isHidden`` und nicht ``isVisible``: Ein Fenster, das nie gezeigt wurde,
    # meldet jedes Kind als unsichtbar — geprüft wird, was *gesetzt* wurde.
    assert window.layer_bar.note.isHidden(), (
        f"one body needs no choosing, but the bar asks: {window.layer_bar.note.text()!r}"
    )
    assert not window.layer_bar.slider.isHidden(), "the slider is the point of the tool"


def test_with_several_bodies_the_bar_says_what_it_needs(window: MainWindow) -> None:
    """Bei mehreren Körpern muss der Kunde zeigen, welchen er meint.

    Dann steht der Grund **in der Leiste**, nicht in der Statuszeile — und er
    zeigt auf das Teil, nicht auf den Objektbaum: Wer aus einem Slicer kommt,
    klickt das Modell an, nicht eine Zeile in einer Liste.
    """
    # Eines bringt das Fixture mit, das zweite kommt dazu.
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    assert len(result.scene.objects) == 2, "the point of this test is the ambiguity"
    window.object_tree.tree.clearSelection()

    window.layer_bar.set_active(True)
    window.session.wait_for_idle()

    assert not window.layer_bar.note.isHidden(), "two bodies: the bar has to ask"
    assert "Teil" in window.layer_bar.note.text(), (
        f"the note should point at the part: {window.layer_bar.note.text()!r}"
    )
    assert window.layer_bar.slider.isHidden(), (
        "a slider next to a note saying there is nothing to slide is a contradiction"
    )


def test_the_history_shows_what_kind_of_step_each_line_is(qt_app: QApplication) -> None:
    """Der Verlauf war eine reine Textspalte mit halber Nummerierung.

    Siebzehn Kategoriesymbole lagen in ``icons.py`` bereit, und keine
    Verlaufszeile trug eines — wer seine Arbeit daran entlangliest, sucht
    „das mit der Bohrung" und findet lauter gleich aussehende Zeilen. Und die
    Nummern trugen nur die Kinder einer mehrschrittigen Transaktion: „3" und
    „4" eingerückt unter „Kabel und Befestigung", während „Aushöhlen" darüber
    keine hatte, obwohl auch das genau ein Schritt ist.

    Die Nummer ist keine Zierde — der Fehlerdialog nennt „Operation: 4", und
    ein geöffneter Schritt heißt „Bohrung setzen — Operation 4". Sie steht
    deshalb an jeder Zeile, die genau einen Schritt vertritt; eine
    Transaktion aus mehreren bekommt keine, ihre Kinder tragen ihre eigenen.
    """
    from pathlib import Path

    from app.ui.panels import HistoryPanel
    from app.ui.session import Session

    session = Session()
    session.open_project(Path(__file__).parent.parent / "app" / "examples" / "dose-mit-deckel.p3d")
    session.wait_for_idle()

    panel = HistoryPanel()
    try:
        panel.show_document(session.project.document)
        rows = [panel.list.item(index) for index in range(panel.list.count())]
        assert rows, "das Beispielprojekt hat keinen Verlauf — dann prüft dieser Test nichts"

        without_icon = [row.text() for row in rows if row.icon().isNull()]
        assert not without_icon, f"Zeilen ohne Symbol: {without_icon}"

        # Jede Zeile, die genau einen Schritt vertritt, nennt seine Nummer.
        for row in rows:
            single = row.data(Qt.ItemDataRole.UserRole)
            if single is None:
                continue
            assert str(single) in row.text(), (
                f"Schritt {single} nennt seine Nummer nicht: {row.text()!r}"
            )
    finally:
        panel.deleteLater()


def test_the_object_preview_is_large_enough_to_recognise(qt_app: QApplication) -> None:
    """Das Vorschaubild war ein Fleck, in dem auch vergrößert nichts zu sehen war.

    Bei Zeilenhöhe mal 1,2 — bei Standardschrift 19 Bildpunkte — zeigte der
    Objektbaum von einer Platte einen dunklen Punkt (B5). Ein Bild, das man
    nicht erkennt, kostet Spaltenbreite und liefert nichts; der Befund schließt
    „halbe Größe" ausdrücklich als Ausweg aus.

    **Der alte Grund gegen mehr ist nachgemessen und weggefallen.** Im
    Docstring stand, ab Zeilenhöhe mal 1,7 werde der Name gekürzt. Gemessen
    bleibt die Spalte „Objekt" bei 19, 32, 40 und 48 Punkten Vorschau konstant
    165 Punkte breit, und ``elidedText`` kürzt in keinem der vier Fälle. Was
    der Satz beschrieb, war eine Spaltenaufteilung von früher.

    Geprüft wird hier die Rechnung, nicht das Bild: Die Untergrenze, die
    Mitwachsen-Eigenschaft und der Deckel, der das Bild aus der Namensspalte
    heraushält.
    """
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QLabel

    from app.ui.panels import _preview_pixels

    probe = QLabel()
    try:
        assert _preview_pixels(probe) >= 40, (
            "unter vierzig Punkten ist ein Quader eine Silhouette ohne Kanten — "
            "gemessen an den Belegbildern der Durchsicht"
        )

        # **Es wächst mit der Schrift** — der ursprüngliche Zweck der Funktion,
        # und er darf beim Vergrößern nicht verlorengehen.
        gross = QFont(probe.font())
        gross.setPointSize(max(probe.font().pointSize(), 1) * 3)
        probe.setFont(gross)
        assert _preview_pixels(probe) > 40, "bei dreifacher Schrift wächst das Bild mit"

        # **Und es hört rechtzeitig auf.** Die Spalte „Objekt" ist 165 Punkte
        # breit; ein Bild über einem Drittel davon nähme dem Namen den Platz,
        # den die Messung ihm als Reserve gelassen hat.
        riesig = QFont(probe.font())
        riesig.setPointSize(max(probe.font().pointSize(), 1) * 4)
        probe.setFont(riesig)
        assert _preview_pixels(probe) <= 56, "über sechsundfünfzig frisst es die Namensspalte"
    finally:
        probe.deleteLater()


def test_a_click_with_a_place_also_selects_the_body(window: MainWindow) -> None:
    """Die drei Stufen eines Klicks schließen einander nicht aus (§18.4).

    **Der Fehler, den das hier fängt.** Die Regel und der Docstring der Funktion
    sagen beide dasselbe: Ort → die Kamera fliegt und eine Marke steht dort;
    Körper → er wird ausgewählt; Schritt → der Verlauf zeigt ihn. Der Code
    führte sie aber als Reihenfolge aus — nach dem Flug stand ein ``return``,
    und die Zeile mit der Auswahl darunter wurde nie erreicht. Wer auf eine
    Warnung mit Ort klickte, bekam den Flug **statt** der Auswahl.

    **Und der Wächter daneben sah es nicht**, weil er den Quelltext nach
    ``select_object`` absucht: Der Aufruf stand da, er lief nur nicht. Ein
    Test, der Anwesenheit prüft, ist gegen eine unerreichbare Zeile blind —
    deshalb misst dieser hier die Wirkung.
    """
    select_plate(window)
    finding = Finding(
        code="etwas.anderes",
        severity="warning",
        message="x",
        object_id="obj_1",
        location=(1.0, 2.0, 3.0),
    )

    window.object_tree.select_object("")
    assert window.object_tree.selected() != "obj_1", "die Auswahl steht nicht schon vorher"

    window._on_finding_activated(finding)

    assert window.object_tree.selected() == "obj_1", (
        "ein Klick mit Ort wählt den Körper trotzdem aus — die Stufen sind "
        "kumulativ, nicht alternativ"
    )


def test_the_camera_keeps_the_body_in_view_after_a_finding_flight(window: MainWindow) -> None:
    """Nach dem Flug steht der Körper im Bild, nicht eine Fläche davon (§18.4).

    **Vermessen, nicht geschätzt.** Die Kamera hielt den Abstand aus der
    Szenengröße geteilt durch drei — bei der Dose 24 mm, und davon war **eine**
    von acht Ecken des Hüllquaders im Bild. Der Kunde klickte auf eine Warnung
    und stand vor einer grauen Fläche.

    Gemessen wurde in Vielfachen der Hüllquader-Diagonale: bei 1,2 sind sechs
    von acht Ecken zu sehen — dort wird aus „irgendeiner Fläche" ein
    erkennbares Teil, und dort wird auch die Beschriftung der Marke sichtbar,
    also der Satz, für den die Marke überhaupt da ist. 1,4 ist der
    Sicherheitsabstand dazu; weiter hinaus (2,5) wird die Marke klein.

    Geprüft wird der Abstand und nicht die Zahl der Ecken: Die Ecken hängen am
    Blickwinkel und am Seitenverhältnis des Fensters, der Abstand ist die
    Größe, die der Code setzt.
    """
    select_plate(window)
    entry = next(iter(window.session.last_result.scene.objects.values()))
    finding = Finding(
        code="etwas.anderes",
        severity="warning",
        message="x",
        object_id=entry.id,
        location=tuple(entry.mesh.bounds.centre),
    )

    # **Gemessen wird der verlangte Abstand, nicht die Kamerastellung.** Im
    # Offscreen-Betrieb gibt es keinen Renderer und damit keine Kamera; was der
    # Code entscheidet, ist die Reichweite, die er `fly_to` mitgibt. Das
    # Umsetzen in eine Position ist Qt-Mechanik und gehört nicht hierher.
    verlangt: list[float | None] = []
    original = window.viewport.fly_to

    def merken(point: Any, distance_factor: float = 3.0, reach: float | None = None) -> None:
        verlangt.append(reach)
        original(point, distance_factor, reach)

    window.viewport.fly_to = merken  # type: ignore[method-assign]
    try:
        window._on_finding_activated(finding)
    finally:
        window.viewport.fly_to = original  # type: ignore[method-assign]

    assert verlangt, "der Klick ist geflogen"
    erwartet = 1.4 * float(entry.mesh.bounds.diagonal)
    assert verlangt[0] is not None and abs(verlangt[0] - erwartet) < 0.01, (
        f"der Flug verlangt {verlangt[0]} statt {erwartet:.1f} Abstand — bei zu"
        " wenig sieht der Kunde eine Fläche statt eines Teils"
    )


def test_the_layer_legend_goes_when_the_layer_does(qt_app: QApplication) -> None:
    """Die Ringlegende verschwindet mit der Schicht, die sie erklärt.

    **Der Fall, der diese Prüfung veranlasst hat** (gemessen 3d-druck-85 am
    03.09.2026): Aufgeräumt wurde die Legende nur am Kopf von ``_show_legend``,
    und das lief nur bei gezeigter Schicht. In vier Lagen stand deshalb die
    Legende des vorigen Körpers da — bei „keine Auswahl", nach dem Schließen
    des Werkzeugs und nach **jeder** Auswertung, weil das Fenster dann
    ``show_result(None)`` ruft. Mitsamt „Insel" und „Überhang", die es in der
    leeren Ansicht nicht gibt.

    Ein Zustand, den niemand abräumt, sieht aus wie eine Auskunft.
    """
    bar = LayerBar()
    bar.setEnabled(True)
    bar._on = True
    layer = SimpleNamespace(z=1.0, area=100.0, islands=[(0.0, 0.0)], overhang_area=5.0)
    bar._result = SimpleNamespace(layers=[layer])
    bar._show_readout()
    assert bar._legend.count() > 1, "die Legende steht, solange die Schicht steht"

    bar.show_result(None)

    assert bar._legend.count() == 0, "ohne Schicht bleibt keine Legende stehen"


def test_a_countersink_stands_under_its_bore(qt_app: QApplication) -> None:
    """Bohrung und Senkung sind ein Merkmal in zwei Flächen — der Baum zeigt es.

    **Der Fall.** Robert am 04.09.2026: „ich hab bei der Bohrung den
    Durchmesser geändert, allerdings hat die Bohrung auch noch eine Senkung."
    An seinem Halter standen zwei Bohrungen und zwei Senkungen als vier Zeilen
    nebeneinander, ohne erkennbaren Zusammenhang — wer die Bohrung anklickt,
    findet die Senkung nicht, und wer sie ändert, merkt erst am Teil, dass die
    Senkung stehen geblieben ist.

    Die Zuordnung kommt aus dem Kern (``widening_at_the_mouth``), damit Baum
    und Prüfbericht dieselbe Nachbarschaft meinen und nicht zwei.
    """
    from pathlib import Path

    from app.core.geom.mesh import read_mesh
    from app.core.ingest.loader import normalise
    from app.core.perceive.features import detect
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ObjectTree

    quelle = Path(__file__).parent / "data" / "meshes" / "plate_countersunk.stl"
    body = normalise(read_mesh(quelle.read_bytes(), ".stl"), "mm").mesh
    features = detect(body)
    bore = next(feature for feature in features.values() if feature.kind == "hole")
    sink = next(
        feature
        for feature in features.values()
        if feature.kind == "cone" and feature.params.get("recess")
    )

    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features=features)
    tree = ObjectTree()
    try:
        tree.show_scene(EvaluationResult(scene=Scene(objects={"obj_1": entry})))

        gefunden = _feature_row(tree.tree.topLevelItem(0), sink.id)
        assert gefunden is not None, "die Senkung steht gar nicht im Baum"
        eltern = gefunden.parent()
        assert eltern is not None, "die Senkung hängt am Objekt statt an ihrer Bohrung"
        assert eltern.data(1, Qt.ItemDataRole.UserRole) == bore.id, (
            "die Senkung hängt unter "
            f"{eltern.data(1, Qt.ItemDataRole.UserRole)} statt unter {bore.id}"
        )
    finally:
        tree.deleteLater()


def test_a_complete_cavity_chain_is_nested_with_one_topology_pass(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bohrung, Übergang und Senkung bilden einen Ast ohne wiederholte Netzanalyse."""
    from app.core.geom.mesh import read_mesh
    from app.core.ingest.loader import normalise
    from app.core.perceive import relations
    from app.core.perceive.features import detect
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ObjectTree

    quelle = Path(__file__).parent / "data" / "meshes" / "plate_countersunk.stl"
    body = normalise(read_mesh(quelle.read_bytes(), ".stl"), "mm").mesh
    detected = detect(body)
    bore = next(feature for feature in detected.values() if feature.kind == "hole")
    transition = next(feature for feature in detected.values() if feature.kind == "cone")
    counterbore = dataclasses.replace(
        bore,
        id="hole_outer",
        params={
            **bore.params,
            "centre": (0.0, 0.0, 4.0),
            "diameter": float(transition.params["diameter"]),
        },
    )
    linked = {
        counterbore.id: counterbore,
        transition.id: transition,
        bore.id: bore,
    }
    asked: list[tuple[Any, Any]] = []

    def chains_of(available: Any, mesh: Any) -> tuple[tuple[Any, ...], ...]:
        asked.append((available, mesh))
        return ((bore, transition, counterbore),)

    monkeypatch.setattr(relations, "cavity_chains", chains_of)
    entry = SceneObject(id="obj_1", name="Senkbohrung", mesh=body, features=linked)
    tree = ObjectTree()
    try:
        tree.show_scene(EvaluationResult(scene=Scene(objects={entry.id: entry})))

        assert asked == [(linked, body)], "je Körper genau eine Randringbildung"
        root = tree.tree.topLevelItem(0)
        middle = _feature_row(root, transition.id)
        outer = _feature_row(root, counterbore.id)
        assert middle is not None and outer is not None
        assert middle.parent().data(1, Qt.ItemDataRole.UserRole) == bore.id
        assert outer.parent().data(1, Qt.ItemDataRole.UserRole) == transition.id
    finally:
        tree.deleteLater()


def test_a_part_with_one_row_carries_its_own_name(qt_app: QApplication) -> None:
    """Ein Baustein mit einer einzigen Zeile heißt im Baum wie im Verlauf.

    Das Dach über einer einzigen Zeile entfällt (Befund Robert, 09.09.2026) —
    und mit ihm verschwand der Name des Bausteins: Eine eingesetzte
    Magnettasche stand im Baum als „Sackbohrung 1", im Verlauf und rechts im
    Fenster als „Magnettasche" (Kundenprüfung 0.5.1, Weg c, am exakten
    Quader). Die Zeile trägt seitdem den Namen des Dachs; was sie geometrisch
    ist, sagt ihre Kurzhilfe, und die Kennung des Merkmals bleibt.

    Die Gegenprobe steht am selben Körper: Ein Baustein mit zwei Zeilen
    behält sein Dach, und seine Zeilen behalten die Namen ihrer Merkmale.
    Gebaut wird die Szene von Hand, damit die Zahl der Zeilen an keiner
    Erkennung hängt.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.registry import REGISTRY
    from app.core.scene import EvaluationResult, History, OperationDraft
    from app.core.scene.project import new_project
    from app.core.types import Feature, Scene, SceneObject
    from app.ui.labels import feature_name
    from app.ui.panels import ObjectTree

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply("Quader", [OperationDraft(op="create_box", params={"height": 10.0})])
    history.apply(
        "Magnettasche",
        [OperationDraft(op="insert_magnet_pocket", inputs=("obj_1",), params={"z": 10.0})],
    )
    history.apply(
        "Wandhalter",
        [OperationDraft(op="insert_wall_mount", inputs=("obj_1",), params={"z": 10.0})],
    )
    pocket_step, mount_step = (entry.id for entry in project.document.ops[1:])

    def made(name: str, kind: str, step: int, **params: Any) -> Feature:
        return Feature(id=name, kind=kind, provenance="generated", params=params, created_by=step)

    pocket = made(
        "magnet_pocket_pocket_1",
        "hole",
        pocket_step,
        diameter=8.25,
        through=False,
        centre=(0.0, 0.0, 8.5),
        axis=(0.0, 0.0, 1.0),
    )
    plate = made("wall_mount_plate_1", "face", mount_step, normal=(0.0, 1.0, 0.0), area=750.0)
    bore = made(
        "wall_mount_bore_1",
        "hole",
        mount_step,
        diameter=4.5,
        through=True,
        centre=(10.0, 5.0, 20.0),
        axis=(0.0, 1.0, 0.0),
    )
    features = {feature.id: feature for feature in (pocket, plate, bore)}
    box = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 10.0)))
    entry = SceneObject(id="obj_1", name="Quader", mesh=box, features=features)
    tree = ObjectTree()
    try:
        tree.show_scene(EvaluationResult(scene=Scene(objects={"obj_1": entry})), project.document)

        root = tree.tree.topLevelItem(0)
        row = _feature_row(root, pocket.id)
        assert row is not None, "die Magnettasche steht gar nicht im Baum"
        assert row.parent() is root, "ein Dach über einer einzigen Zeile ist keins"
        title = str(REGISTRY.get("insert_magnet_pocket").title)
        assert row.text(0) == title, f"im Baum „{row.text(0)}“, im Verlauf „{title}“"
        assert row.data(1, Qt.ItemDataRole.UserRole) == pocket.id, "die Kennung bleibt"
        assert feature_name(pocket.id, pocket) in row.toolTip(0), (
            "was die Zeile geometrisch ist, sagt ihre Kurzhilfe"
        )

        mount_row = _feature_row(root, bore.id)
        assert mount_row is not None
        roof = mount_row.parent()
        assert roof is not root, "zwei Zeilen behalten ihr Dach"
        assert roof.text(0) == str(REGISTRY.get("insert_wall_mount").title)
        assert mount_row.text(0) == feature_name(bore.id, bore), (
            "unter dem Dach heißt jede Zeile wie ihr Merkmal"
        )
    finally:
        tree.deleteLater()


def _feature_row(item: Any, feature_id: str) -> Any:
    """Die Zeile eines Merkmals, gleich wie tief sie hängt."""
    for index in range(item.childCount()):
        child = item.child(index)
        if child.data(1, Qt.ItemDataRole.UserRole) == feature_id:
            return child
        deeper = _feature_row(child, feature_id)
        if deeper is not None:
            return deeper
    return None


def test_a_rejected_map_offers_the_way_out(qt_app: QApplication) -> None:
    """Regel 17 gilt auch für eine Karte, die nicht geht.

    „Für eine Analysekarte ist dieses Modell zu groß" sagte, was nicht geht,
    und ließ den Kunden dort stehen — während der Prüfbericht zu genau
    demselben Sachverhalt seit je *Dreiecke verringern* anbietet. Gemessen an
    neunzehn heruntergeladenen Kundendateien (04.09.2026) lagen zehn über der
    Kartengrenze; an keiner führte von hier aus ein Weg weiter.
    """
    from app.ui.analysis_bar import AnalysisBar

    bar = AnalysisBar(None)
    try:
        clicked: list[bool] = []
        bar.show_problem("zu groß", "Dreiecke verringern", lambda: clicked.append(True))

        button = bar.legend.action
        assert button is not None, "der Ausweg fehlt"
        assert button.text() == "Dreiecke verringern"
        assert bar.legend._layout.indexOf(button) >= 0, "der Knopf steht außerhalb der Anordnung"
        button.click()
        assert clicked == [True], "der Knopf löst seine Handlung nicht aus"

        # Und er verschwindet mit der nächsten Karte — sonst stünde er über
        # einer Legende, die gerade beweist, dass es doch geht.
        bar.show_legend(None)
        assert bar.legend.action is None, "der Ausweg überlebt seine Karte"
    finally:
        bar.deleteLater()


def test_a_problem_without_a_way_out_stays_a_sentence(qt_app: QApplication) -> None:
    """Wo die Anwendung keinen Ausweg kennt, erfindet sie keinen.

    Eine Handlung ohne Empfänger wäre schlimmer als keine: Der Knopf sähe aus
    wie eine Lösung und täte nichts.
    """
    from app.ui.analysis_bar import AnalysisBar

    bar = AnalysisBar(None)
    try:
        bar.show_problem("Die Analysekarte ließ sich nicht berechnen.")
        assert bar.legend.action is None, "ein Knopf ohne Handlung"
        assert bar.legend.note.text() == "Die Analysekarte ließ sich nicht berechnen."
    finally:
        bar.deleteLater()


def test_a_cached_map_replaces_the_shown_one_in_a_single_pass(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Wechsel zwischen zwei gerechneten Karten setzt die Ansicht einmal.

    Bis zum 06.09.2026 wurde erst geleert und dann gesetzt — zwei Szenenaufbauten
    für einen Klick, und der erste zeigte für einen Moment gar keine Karte.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Scene, SceneObject

    host = MainWindow(Session(), UiSettings())
    body = SceneObject(id="obj_1", name="Quader", mesh=MeshData(trimesh.creation.box()))
    result = EvaluationResult(Scene(objects={"obj_1": body}))
    host.session.last_result = result
    host.session.result_current = True
    host.object_tree.show_scene(result)
    host.object_tree.select_object("obj_1")
    first = maps.AnalysisMap(
        kind="support", title="Stützen", values=(1.0,) * 12, unit="mm", low=0.0, high=1.0
    )
    second = maps.AnalysisMap(
        kind="overhang", title="Überhang", values=(0.0,) * 12, unit="°", low=0.0, high=90.0
    )
    host._map_cache[host._analysis_cache_key(body, "support")] = first
    host._map_cache[host._analysis_cache_key(body, "overhang")] = second
    host.analysis_bar.show_map("support")
    host._analysis_map("support", "obj_1")
    assert host.viewport.analysis_map is first

    shown: list[Any] = []
    real = host.viewport.set_analysis_map

    def counted(analysis: Any, object_id: Any) -> None:
        shown.append(analysis)
        real(analysis, object_id)

    monkeypatch.setattr(host.viewport, "set_analysis_map", counted)
    host.analysis_bar.show_map("overhang")
    host._analysis_map("overhang", "obj_1")
    assert shown == [second], "eine gecachte Karte ersetzt die alte in einem Zug"
    assert host.viewport.analysis_map is second
    host.release()


def test_the_filament_picker_leaves_at_a_feature_that_carries_none(window: MainWindow) -> None:
    """An einer Bohrung tritt der Filamentwähler beiseite, an einer Fläche bleibt er.

    Robert am 09.09.2026 am laufenden Fenster: „hier steht auch
    Filamentzuweisung, im Baum bei Bohrungen fehlt das Feld, also auch rechts
    in der Auswahl bei Bohrungen entfernen". Der Baum hält sich seit je daran
    — ``paint_slot`` gilt für ``face`` und für nichts sonst, und eine Bohrung
    bekommt deshalb keine Filamentspalte. Der Wähler rechts fragte dagegen
    ``selected_features`` und bot vier Zeilen an, die dort nichts tun.
    """
    result = window.session.last_result
    assert result is not None
    features = result.scene.objects["obj_1"].features
    faces = [key for key, feature in features.items() if getattr(feature, "kind", "") == "face"]
    holes = [key for key, feature in features.items() if getattr(feature, "kind", "") == "hole"]
    assert faces and holes, "ohne beide Arten prüft der Test nichts"

    window.object_tree.select_feature("obj_1", holes[0])
    QApplication.processEvents()
    assert window.object_tree.selected_faces() == ()
    assert window.quick_filament.isHidden(), "eine Bohrung trägt kein eigenes Filament"

    window.object_tree.select_feature("obj_1", faces[0])
    QApplication.processEvents()
    assert window.object_tree.selected_faces() == (("obj_1", faces[0]),)
    assert not window.quick_filament.isHidden(), "an einer Fläche gibt es etwas zuzuweisen"


def test_a_curved_face_carries_a_filament_field_like_a_flat_one(qt_app: QApplication) -> None:
    """Roberts Fall (11.09.2026): „bei den Seiten fehlen die gerundeten
    flächen" — am D standen vier ebene Flächen im Baum, die zwei Bögen nicht,
    und dem Bogen war kein Filament zu geben.

    Ende zu Ende am Fenster: Ein D als Schriftzug, dann die Zeile der
    gerundeten Seite im Baum — mit Namen, Farbfeld und dem Klick, der nach
    dem Filament fragt —, und rechts der Filamentwähler, der an ihr bleibt,
    wie er an einer ebenen Fläche bleibt und an einer Bohrung geht.
    """
    from app.core.scene import OperationDraft
    from app.ui.panels import FILAMENT_COLUMN, _feature_item

    window = MainWindow(Session(), UiSettings())
    try:
        assert window.session.apply(
            "Schriftzug",
            [
                OperationDraft(
                    op="create_label",
                    inputs=(),
                    params={"text": "D", "size": 60.0, "font": "DejaVu Sans Mono"},
                )
            ],
        )
        assert window.session.wait_for_idle(30000)
        result = window.session.evaluate_now()
        window._on_scene(result)
        features = result.scene.objects["obj_1"].features
        curved = [key for key, feature in features.items() if feature.kind == "curved_face"]
        assert len(curved) == 2, "der Bogen außen und der Bogen innen"

        row = window.object_tree.tree.topLevelItem(0)
        assert row is not None
        for feature_id in curved:
            line = _feature_item(row, feature_id)
            assert line is not None, f"{feature_id} steht im Baum"
            assert line.text(0) in (tr("Gerundete Seite"), tr("Gerundete Seite innen"))
            assert not line.icon(FILAMENT_COLUMN).isNull(), "mit Farbfeld wie eine Ebene"
            assert line.toolTip(FILAMENT_COLUMN), "und dem Namen des Filaments daneben"

        asked: list[tuple[object, object]] = []
        window.object_tree.filamentRequested.connect(lambda obj, feat: asked.append((obj, feat)))
        line = _feature_item(row, curved[0])
        assert line is not None
        window.object_tree._on_cell_clicked(
            window.object_tree.tree.indexFromItem(line, FILAMENT_COLUMN)
        )
        assert asked == [("obj_1", curved[0])], "der Klick fragt nach dem Filament der Seite"

        window.object_tree.select_feature("obj_1", curved[0])
        QApplication.processEvents()
        assert window.object_tree.selected_faces() == (("obj_1", curved[0]),)
        assert not window.quick_filament.isHidden(), "eine gerundete Seite lässt sich färben"
    finally:
        window.wait_for_workers()


def _scene_with_fillets(radii: list[float]) -> Any:
    """Ein Körper mit lauter Hohlkehlen — ihre Radien sind das Unterscheidende.

    Zurück kommt ein EvaluationResult; der Typ steht hier nicht in der
    Signatur, weil er wie bei den Nachbarhelfern erst in der Funktion
    importiert wird.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Feature, Scene, SceneObject

    features = {
        f"fillet_{nummer + 1}": Feature(
            id=f"fillet_{nummer + 1}",
            kind="fillet",
            provenance="test",
            # recess macht daraus die **Hohlkehle** und nicht die
            # Verrundung — der Fall aus der STEP-Datei ist die konkave
            # Variante, und der Docstring nennt sie beim Namen.
            params={"radius": radius, "recess": True},
        )
        for nummer, radius in enumerate(radii)
    }
    body = SceneObject(
        "obj_1", "Platte", MeshData(trimesh.creation.box((40, 40, 10))), features=features
    )
    return EvaluationResult(Scene(objects={"obj_1": body}))


def test_a_roof_bundles_the_same_measure_and_not_merely_the_same_word(
    qt_app: QApplication,
) -> None:
    """Vier Hohlkehlen mit vier Radien sind nicht vier gleichartige Merkmale.

    Das Dach über gleichartigen Zeilen löst einen echten Fall: Eine STEP-Datei
    bringt Dutzende Hohlkehlen **desselben** Radius mit, und fünfzig gleiche
    Zeilen begraben die linke Spalte. Gezählt wurde dafür nach dem Namen
    allein — und damit verschwanden auch vier *verschiedene* Radien hinter
    einer Zeile „Hohlkehle (4)", die Gleichartigkeit behauptet, wo keine ist
    (Befund Robert, 09.09.2026: „Hohlkehle mit 4 Unterschritten").

    Geprüft werden beide Richtungen an derselben Schwelle: Vier gleiche Maße
    gehören unter ein Dach, vier verschiedene nicht. Ein Test nur für die eine
    Richtung ließe die jeweils andere frei — und die Bündelung ist erwünscht,
    sie soll nur das Richtige treffen.
    """
    from app.ui.panels import BUNDLE_FROM, ObjectTree

    tree_widget = ObjectTree()
    try:
        gleich = [2.5] * BUNDLE_FROM
        tree_widget.show_scene(_scene_with_fillets(gleich))
        oberste = tree_widget.tree.topLevelItem(0)
        assert oberste is not None, "ohne Körperzeile prüft der Test nichts"
        assert oberste.childCount() == 1, (
            f"{BUNDLE_FROM} gleiche Radien gehören unter ein Dach, "
            f"gefunden {oberste.childCount()} Zeilen"
        )
        dach = oberste.child(0)
        assert dach is not None and dach.childCount() == BUNDLE_FROM

        verschieden = [2.0 + nummer for nummer in range(BUNDLE_FROM)]
        tree_widget.show_scene(_scene_with_fillets(verschieden))
        oberste = tree_widget.tree.topLevelItem(0)
        assert oberste is not None
        assert oberste.childCount() == BUNDLE_FROM, (
            f"{BUNDLE_FROM} verschiedene Radien sind {BUNDLE_FROM} Zeilen, "
            f"gefunden {oberste.childCount()} — sie stehen hinter einem Dach"
        )
        masse = {oberste.child(index).text(1) for index in range(oberste.childCount())}
        assert len(masse) == BUNDLE_FROM, f"jede Zeile trägt ihr eigenes Maß: {masse}"

        # Zuletzt die Anschrift: Seit alle Kinder eines Dachs dasselbe Maß
        # tragen, ist es ihre gemeinsame Auskunft und keine Behauptung über
        # die übrigen mehr.
        tree_widget.show_scene(_scene_with_fillets(gleich))
        oberste = tree_widget.tree.topLevelItem(0)
        assert oberste is not None
        assert oberste.child(0).text(1), "das Dach schreibt das gemeinsame Maß an"
    finally:
        tree_widget.deleteLater()


def test_a_grabbable_preview_keeps_the_selection_gizmo_away(qt_app: QApplication) -> None:
    """Solange eine Vorschau greifbar ist, steht kein zweiter Griff daneben.

    Der Griff der Auswahl hängt am zuletzt gewählten Körper und trägt einen
    Skalierwürfel; die Vorschau daneben zeigt den Körper, den der offene Dialog
    gerade anlegt. Wer den Würfel anfasste, änderte die Maße eines fremden
    Teils, während die des neuen im Dialog stehen (Robert, 09.09.2026: „den
    Skalierwürfel brauchen wir nicht, der Dialog sollte ja noch offen sein zum
    Setzen, wo man die Maße eingibt").

    **Geprüft wird der Neubau, nicht das Abnehmen.** Ihn beim Einschalten der
    Vorschau einmal wegzunehmen genügt nicht: Sieben Stellen rufen
    ``set_gizmo(self._gizmo_wanted)`` — Auswahlwechsel, Merkmalswechsel,
    Szenenaufbau, Themenwechsel —, und jede käme mitten durch den offenen
    Dialog. Die Prüfung sitzt deshalb in ``set_gizmo`` selbst.
    """
    viewport, _renderer = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        assert viewport._gizmo is not None, "ohne Vorschau bringt die Auswahl ihren Griff"

        viewport.set_preview_gizmo(True)
        assert viewport._gizmo is None, "die greifbare Vorschau nimmt ihn"
        assert viewport._scale_handle is None, "und den Skalierwürfel mit"
        assert viewport._gizmo_wanted, "die Entscheidung bleibt, nur der Griff geht"

        # Der Fall, den das Abnehmen allein nicht deckt: ein Neubau mittendrin.
        viewport.select("obj_2")
        viewport.set_gizmo(True)
        assert viewport._gizmo is None, "auch ein Auswahlwechsel baut ihn nicht neu"

        viewport.set_preview_gizmo(False)
        assert viewport._gizmo is not None, "mit der Vorschau kommt er zurück"
    finally:
        viewport.deleteLater()


def test_replaced_map_legend_hides_before_deferred_deletion(qt_app: QApplication) -> None:
    """Alte Farbfelder und der Ausweg verschwinden im selben Aufruf wie die Karte."""
    legend = MapLegend()
    legend.show_map(
        maps.AnalysisMap(kind="wall", title="x", values=(1.0,), unit="mm", low=1.0, high=4.0)
    )
    legend.offer("Ausweg", lambda: None)
    legend.show()
    qt_app.processEvents()
    old = [
        legend._layout.itemAt(index).widget()
        for index in range(legend._layout.count())
        if legend._layout.itemAt(index).widget() is not legend.note
    ]
    assert old and all(widget.isVisible() for widget in old)
    legend.show_map(None)
    assert all(widget.isHidden() for widget in old)
    assert not legend.note.isHidden()
    legend.deleteLater()


def test_removed_layer_legend_hides_before_deferred_deletion(qt_app: QApplication) -> None:
    """Ohne Schicht sind auch die noch lebenden alten Legendeneinträge unsichtbar."""
    bar = LayerBar()
    bar.set_active(True)
    layer = SimpleNamespace(z=1.0, area=100.0, islands=[(0.0, 0.0)], overhang_area=5.0)
    bar.show_result(SimpleNamespace(layers=[layer]))
    bar.show()
    qt_app.processEvents()
    old = [
        bar._legend.itemAt(index).widget()
        for index in range(bar._legend.count())
        if bar._legend.itemAt(index).widget() is not None
    ]
    assert old and all(widget.isVisible() for widget in old)
    bar.show_result(None)
    assert all(widget.isHidden() for widget in old)
    bar.deleteLater()


@pytest.mark.parametrize("chosen", ["light", "dark"])
def test_existing_layer_stroke_border_follows_theme(qt_app: QApplication, chosen: str) -> None:
    """Ein echter Themenwechsel färbt den bestehenden Rand bei unverändertem Inhalt."""
    from PySide6.QtWidgets import QFrame

    from app.ui.palette import ROLES
    from app.ui.theme import THEMES, apply_theme, current_theme

    previous = current_theme()
    before = "dark" if chosen == "light" else "light"
    apply_theme(qt_app, before)
    bar = LayerBar()
    try:
        bar.set_active(True)
        layer = SimpleNamespace(z=1.0, area=100.0, islands=[], overhang_area=0.0)
        bar.show_result(SimpleNamespace(layers=[layer]))
        bar.show()
        qt_app.processEvents()
        entry = bar._legend.itemAt(0).widget()
        stroke = entry.layout().itemAt(0).widget()
        assert isinstance(stroke, QFrame)

        def colours() -> tuple[str, str]:
            picture = stroke.grab().toImage()
            return (
                picture.pixelColor(0, picture.height() // 2).name(),
                picture.pixelColor(picture.width() // 2, picture.height() // 2).name(),
            )

        assert colours() == (THEMES[before]["line"], ROLES["layer"])
        apply_theme(qt_app, chosen)
        qt_app.processEvents()
        assert bar._legend.itemAt(0).widget() is entry
        assert colours() == (THEMES[chosen]["line"], ROLES["layer"])
    finally:
        bar.close()
        bar.deleteLater()
        apply_theme(qt_app, previous)


@pytest.mark.parametrize(
    "slots, expected_body, expected_face",
    [
        ((2,) * 12, "PETG Rot", "PETG Rot"),
        ((0,) * 12, "Ohne Filament", "Ohne Filament"),
        ((1, 2) * 6, "PLA Weiß", "PETG Rot"),
    ],
)
def test_tree_filament_labels_follow_real_body_and_feature_slots(
    qt_app: QApplication, slots, expected_body, expected_face, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Körper und Fläche nennen die verwendeten Filamente statt verwaister Definitionen."""
    import trimesh

    from app.core.geom import attributes
    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Feature, MaterialSlot, Scene, SceneObject
    from app.ui.panels import FILAMENT_COLUMN, ObjectTree, _feature_item

    original = attributes.used_slots
    surveys = []

    def surveyed(mesh):
        surveys.append(mesh)
        return original(mesh)

    monkeypatch.setattr(attributes, "used_slots", surveyed)
    mesh = MeshData.of(trimesh.creation.box(), slots=slots)
    entry = SceneObject(
        "obj",
        "Körper",
        mesh,
        material_slots=[
            MaterialSlot(1, "PLA Weiß", (1.0, 1.0, 1.0, 1.0)),
            MaterialSlot(2, "PETG Rot", (1.0, 0.0, 0.0, 1.0)),
        ],
        features={"face": Feature("face", "face", "generated", {}, face_indices=(1,))},
    )
    tree = ObjectTree()
    try:
        tree.show_scene(EvaluationResult(scene=Scene(objects={entry.id: entry})))
        body = tree.tree.topLevelItem(0)
        face = _feature_item(body, "face")
        assert face is not None
        assert expected_body in body.toolTip(FILAMENT_COLUMN)
        assert expected_face in face.toolTip(FILAMENT_COLUMN)
        for row in (body, face):
            assert row.data(
                FILAMENT_COLUMN, Qt.ItemDataRole.AccessibleDescriptionRole
            ) == row.toolTip(FILAMENT_COLUMN)
        if len(set(slots)) == 1:
            assert "weitere" not in body.toolTip(FILAMENT_COLUMN)
        assert "weitere" not in face.toolTip(FILAMENT_COLUMN)
        assert len(surveys) == 1
    finally:
        tree.deleteLater()


def _a_rib_on_the_plate(window: MainWindow) -> tuple[str, int]:
    """Eine Versteifungsrippe auf der Deckfläche — der Baustein, der nur aus
    Flächen besteht. Körper und Schritt."""
    from app.core.scene import OperationDraft

    result = window.session.last_result
    assert result is not None
    object_id = next(iter(result.scene.objects))
    window.session.apply(
        "Versteifungsrippe",
        [
            OperationDraft(
                op="insert_rib",
                inputs=(object_id,),
                params={
                    "length": 30.0,
                    "height": 5.0,
                    "wall": 6.0,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 8.0,
                    "nx": 0.0,
                    "ny": 0.0,
                    "nz": 1.0,
                },
            )
        ],
    )
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    step = window.session.project.document.ops[-1]
    assert step.op == "insert_rib"
    return object_id, int(step.id)


def test_a_face_of_a_part_carries_the_grip_of_the_part(window: MainWindow) -> None:
    """Die Rippe besteht aus nichts als Flächen — und ihr Griff bewegt die Rippe.

    Bis zum 16.09.2026 hing an einer Bausteinfläche der Griff der Fläche: ein
    Pfeil entlang der Normalen, dessen Zug ein ``push_face`` auf den
    verschmolzenen Körper wurde (Robert: „bei manchen bausteinen keine
    möglichkeit zum verschieben"). Jetzt gilt die Regel aus `fenster.md`
    auch dort: Was aus einem Baustein kam, meint den Baustein — der Griff
    sitzt an der Fläche, kennt kein Press/Pull, und der Zug geht in den
    Schritt.
    """
    from app.ui.viewport import gizmo_sentence

    object_id, step = _a_rib_on_the_plate(window)
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[object_id]
    faces = sorted(
        fid for fid, f in entry.features.items() if f.created_by == step and f.kind == "face"
    )
    assert faces, "die Rippe bringt erkannte Flächen mit — sonst prüft der Test nichts"
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, faces[0])
    for _ in range(40):
        QApplication.processEvents()
    chosen = window.viewport.gizmo_feature()
    assert chosen is not None and chosen.id == faces[0], "der Griff sitzt an der Fläche"
    assert window.viewport.gizmo_target() is None, "aber nicht als Press/Pull entlang der Normalen"
    assert window.viewport.moves_as_a_part(chosen)
    assert "Baustein" in gizmo_sentence(chosen, part=True)

    steps_before = len(window.session.project.document.ops)
    centre = tuple(float(value) for value in chosen.params["centre"])
    window._on_feature_moved(faces[0], (centre[0], centre[1] - 2.0, centre[2]))
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    moved = next(entry for entry in window.session.project.document.ops if entry.id == step)
    assert moved.params["y"] == pytest.approx(-2.0), moved.params
    assert len(window.session.project.document.ops) == steps_before, "kein zweiter Schritt"
    assert all(entry.op != "push_face" for entry in window.session.project.document.ops)


def test_a_bound_axis_takes_the_drag_into_its_expression(window: MainWindow) -> None:
    """Ein Baustein, dessen Höhe am Parameter hängt, folgt dem Griff trotzdem.

    Das Beispielprojekt bindet ``z`` seiner Bausteine an ``@staerke``, und der
    Griff lehnte dort bis zum 16.09.2026 jede Bewegung ab — im Bild sprang der
    Baustein zurück (Robert: „das verschieben geht nicht springt immer wieder
    zurück"). Quer zur Bindung ändert sich die Zahl, und der Ausdruck bleibt
    unangetastet; entlang der Bindung wächst der Ausdruck um den Versatz
    (``=@hoehe - 2``). Die Bindung hält, der Verlauf bekommt keinen zweiten
    Schritt, und die Auswertung läuft durch.
    """
    from app.core.scene import OperationDraft
    from app.core.types import Parameter

    result = window.session.last_result
    assert result is not None
    object_id = next(iter(result.scene.objects))
    assert window.session.add_parameter(Parameter(name="hoehe", value=8.0, unit="mm"))
    window.session.wait_for_idle()
    window.session.apply(
        "Schlüsselloch",
        [
            OperationDraft(
                op="insert_keyhole",
                inputs=(object_id,),
                params={"x": 10.0, "y": 5.0, "z": "=@hoehe", "nx": 0.0, "ny": 0.0, "nz": 1.0},
            )
        ],
    )
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    step = window.session.project.document.ops[-1]
    assert step.op == "insert_keyhole" and step.params["z"] == "=@hoehe"
    steps_before = len(window.session.project.document.ops)

    def drag(dx: float, dz: float) -> Any:
        centres = _part_centres(window, object_id, int(step.id))
        hole = next(iter(centres))
        window.object_tree.select_object(object_id)
        window.object_tree.select_feature(object_id, hole)
        for _ in range(20):
            QApplication.processEvents()
        x, y, z = centres[hole]
        window._on_feature_moved(hole, (x + dx, y, z + dz))
        window.session.wait_for_idle()
        for _ in range(40):
            QApplication.processEvents()
        return next(entry for entry in window.session.project.document.ops if entry.id == step.id)

    moved = drag(5.0, 0.0)
    assert moved.params["x"] == pytest.approx(15.0), moved.params
    assert moved.params["z"] == "=@hoehe", "eine Achse ohne Zug behält ihren Ausdruck"

    moved = drag(0.0, -2.0)
    assert moved.params["z"] == "=@hoehe - 2", moved.params
    assert moved.params["x"] == pytest.approx(15.0)
    assert len(window.session.project.document.ops) == steps_before, "kein zweiter Schritt"
    latest = window.session.last_result
    assert latest is not None and latest.stopped_at is None


def test_delete_at_a_part_takes_its_step_and_never_the_body(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Entf am Bausteindach — und an einer einzelnen Verrundung — entfernt den Baustein.

    Bis zum 16.09.2026 gab ``selected_feature`` am Dach nichts zurück (mehrere
    Zeilen), der Zwilling fand keine Merkmalsoperation, und Entf löschte den
    ganzen Körper (Robert: „wenn ich etwas im objektbaum oder viewport auswähle
    und entf drücke … wird der ganze körper gelöscht"). Der Weg ist derselbe
    wie *Baustein entfernen* rechts, mit der Folgeauskunft des Verlaufs — hier
    abgefangen, weil die Nachfrage modal ist.
    """
    from app.core.registry import REGISTRY

    object_id, step = _a_keyhole_on_the_plate(window)
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[object_id]
    members = [fid for fid, f in entry.features.items() if f.created_by == step]
    assert len(members) > 1
    removed: list[list[int]] = []
    monkeypatch.setattr(window, "remove_history_operations", removed.append)

    window.object_tree.select_features([(object_id, fid) for fid in members])
    window.object_tree._on_selection()
    assert window.object_tree.selected_feature() is None, "am Dach gibt es kein einzelnes Merkmal"
    window.run_operation(REGISTRY.get("delete_object"))
    assert removed == [[step]]

    fillet = next(
        fid for fid, f in entry.features.items() if f.created_by == step and f.kind == "fillet"
    )
    window.object_tree.select_feature(object_id, fillet)
    window.run_operation(REGISTRY.get("delete_object"))
    assert removed == [[step], [step]]
    assert [entry.op for entry in window.session.project.document.ops] == [
        "load",
        "insert_keyhole",
    ], "kein delete_object und kein remove_feature im Verlauf"


def test_the_body_grip_with_the_part_roof_chosen_moves_the_part(window: MainWindow) -> None:
    """Das Dach eines Bausteins wählt seine Kinder — und der Körpergriff meint den Baustein.

    ``selected_feature`` schweigt bei mehreren Zeilen; ``_move_the_part``
    fragte nur danach und ließ den Zug an den ganzen Körper durch (Fund beim
    Nachsehen nach ähnlichen Fehlern, 16.09.2026). Jetzt fragt es den
    gemeinsamen Bausteinschritt der Auswahl, wie das Merkmalfenster.
    """
    from app.core.geom.transform import TransformSteps

    object_id, step = _a_keyhole_on_the_plate(window)
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[object_id]
    members = [fid for fid, f in entry.features.items() if f.created_by == step]
    window.object_tree.select_features([(object_id, fid) for fid in members])
    window.object_tree._on_selection()
    steps_before = len(window.session.project.document.ops)

    window._on_transform_dragged(TransformSteps(offset=(0.0, -2.0, 0.0)))
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    moved = next(entry for entry in window.session.project.document.ops if entry.id == step)
    assert moved.params["y"] == pytest.approx(3.0), moved.params
    assert len(window.session.project.document.ops) == steps_before
    assert all(entry.op != "translate_object" for entry in window.session.project.document.ops)


def test_a_face_of_a_part_offers_the_filament_for_the_whole_part(window: MainWindow) -> None:
    """Die Rippe verschmilzt mit der Wand und bringt mehrere Flächen mit — ein
    Klick auf eine davon färbt alle.

    Robert, 16.09.2026: „wo stelle ich von der Versteifungsrippe insgesamt das
    filament ein?" Bis dahin galt der Wähler der einen angeklickten Fläche, und
    alle zusammen bekam nur, wer die Dachzeile im Baum traf. Wähler, Zuweisen
    und Entfernen lesen dieselbe Menge (``_filament_targets``); eine fremde
    Fläche daneben bleibt eine Fläche.
    """
    object_id, step = _a_rib_on_the_plate(window)
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[object_id]
    faces = {
        fid
        for fid, f in entry.features.items()
        if f.created_by == step and f.kind == "face" and f.face_indices
    }
    assert len(faces) > 1, "sonst prüft der Test nichts"
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, min(faces))
    for _ in range(40):
        QApplication.processEvents()
    assert set(window._filament_targets()) == {(object_id, fid) for fid in faces}
    assert window.quick_filament.scope.text() == tr(
        "Die Zuweisung gilt dem ganzen Baustein: {count} Flächen."
    ).format(count=len(faces))
    assert window.quick_filament.picker.itemText(0) == tr("Filament für den Baustein wählen")

    other = next(
        fid for fid, f in entry.features.items() if f.kind == "face" and f.created_by != step
    )
    window.object_tree.select_feature(object_id, other)
    for _ in range(40):
        QApplication.processEvents()
    assert window._filament_targets() == ((object_id, other),)


def test_the_roof_of_a_part_carries_the_grip_in_the_view(window: MainWindow) -> None:
    """Das Dach eines Bausteins im Baum bekommt einen Griff — am Baustein.

    Robert, 16.09.2026, mit gewähltem „Kugellager einsetzen": „warum kann ich
    die bausteine nicht über den viewport verschieben?" Das Dach wählt alle
    seine Merkmale, „das gewählte Merkmal" hat dann keine Antwort, und der
    Griff fiel auf den Körper zurück — samt Skalierwürfel, der die Maße des
    ganzen Teils ändert. Jetzt sagt das Fenster der Ansicht, an welchem
    Merkmal er hängt (``set_part_grip``), und der Zug daran geht in den
    Schritt des Bausteins.
    """
    from app.ui.viewport import gizmo_sentence

    object_id, step = _a_keyhole_on_the_plate(window)
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[object_id]
    members = [fid for fid, f in entry.features.items() if f.created_by == step]
    assert len(members) > 1

    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.viewport.show_scene(window.session.last_result)
    said: list[str] = []
    window.viewport.gizmoStatus.connect(said.append)
    window.object_tree.select_features([(object_id, fid) for fid in members])
    window.object_tree._on_selection()
    for _ in range(40):
        QApplication.processEvents()

    chosen = window.viewport.gizmo_feature()
    assert chosen is not None and chosen.id in members, "der Griff hängt an einem seiner Merkmale"
    assert window.viewport.moves_as_a_part(chosen)
    assert said and said[-1] == gizmo_sentence(chosen, part=True), said
    assert window.viewport._scale_handle is None, (
        "kein Skalierwürfel: er änderte die Maße des ganzen Teils"
    )

    # Und ein einzeln gewähltes Merkmal daneben räumt ihn wieder ab.
    other = next(fid for fid, f in entry.features.items() if f.created_by != step)
    window.object_tree.select_feature(object_id, other)
    for _ in range(40):
        QApplication.processEvents()
    assert window.viewport._part_grip is None


# --- die Schichtanalyse im Prüfbericht (§22.2) ------------------------------------


def _wait_for_print_findings(window: MainWindow) -> None:
    """Die Berichtsanalyse läuft im Arbeiter nach der Auswertung; der Test
    wartet wie das Fenster, bis sie ihre Zeilen geliefert hat."""
    worker = window._print_findings.worker
    if worker is not None:
        worker.wait(60_000)
    for _round in range(5):
        QApplication.processEvents()


def test_an_island_reaches_the_report_with_place_and_actions(qt_app: QApplication) -> None:
    """Der Inselturm: eine Kontur, die in der Luft beginnt. Nach der
    Auswertung steht sie im Prüfbericht — mit Körper, Ort, Stützbedarf und
    den zwei Handlungen, die der Fensterhandler auch ausführen kann."""
    window = MainWindow(Session(), UiSettings())
    try:
        window.open_path(MESHES / "island_tower.stl")
        window.session.wait_for_idle()
        _wait_for_print_findings(window)

        islands = [
            finding
            for finding in window.report._findings
            if finding.code == "slice.island_needs_support"
        ]
        assert islands, "die Insel fehlt im Prüfbericht"
        island = islands[0]
        assert island.object_id in window.session.last_result.scene.objects
        assert island.location is not None
        assert island.source == "internal"
        handlers = window.error_handlers()
        assert all(action.id in handlers for action in island.suggestions)
    finally:
        window.wait_for_workers()


def test_a_stale_result_does_not_add_its_findings(qt_app: QApplication) -> None:
    """Ein Ergebnis, das nicht mehr gezeigt wird, liefert keine Zeilen nach."""
    window = MainWindow(Session(), UiSettings())
    try:
        window.open_path(MESHES / "island_tower.stl")
        window.session.wait_for_idle()
        _wait_for_print_findings(window)
        shown = list(window.report._findings)
        stale = object()

        window._print_findings._arrived(
            [Finding(code="slice.island_needs_support", severity="warning", message="x")],
            stale,
            window._print_findings.worker,
        )

        assert window.report._findings == shown
    finally:
        window.wait_for_workers()


def test_the_remote_orientation_analysis_is_prepared_not_computed(window: MainWindow) -> None:
    """RM-144: ``read_analysis`` mit ``orientation`` wurde abgelehnt, weil die
    Suche im Hauptthread Sekunden kostet. Jetzt gibt das Fenster eine
    Momentaufnahme zurück, die der Serverthread rechnet — und die Antwort
    ist dieselbe Analyse wie im Chat, mit Herkunft."""
    from unittest.mock import patch

    from app.core.agent.analysis import analysis_text
    from app.core.agent.tools import READ_ANALYSIS
    from app.core.scene.cancel import CancelSignal

    with patch("app.ui.main_window.analysis_text", wraps=analysis_text) as compute:
        prepared = window.run_remote(READ_ANALYSIS, {"kind": "orientation"})

        assert callable(prepared)
        compute.assert_not_called()
        cancelled = CancelSignal()
        answer = prepared(cancelled)
        compute.assert_called_once()
        assert compute.call_args.args[0] == "orientation"
        assert compute.call_args.kwargs["cancelled"] is cancelled

    assert "Schichtanalyse" in answer
    assert "obj_1" in answer


def test_a_summarised_loss_counts_its_details_and_nothing_else_does() -> None:
    """Die Zahl vor einer Zeile über verlorene Formdetails zählt die Details.

    Die Auswertung meldet sie seit dem 23.09.2026 einmal je Körper und
    Schritt (Handschmeichler: 55 Hinweise, 51 davon dieser Satz). Die Zahl
    steht in ``values["count"]`` und fehlt bei genau einem; ein anderer
    Befund mit eigenem ``count`` bleibt ein Satz.
    """
    from app.ui.panels import _lost_count

    def lost(code: str, **values: float | str) -> Finding:
        return Finding(code=code, severity="info", message="x", values=values)

    assert _lost_count(lost("perceive.orphaned", feature="face_1")) == 1
    assert _lost_count(lost("perceive.orphaned", feature="face_1, face_2", count=2)) == 2
    assert _lost_count(lost("perceive.mended", feature="edge_loop_1, edge_loop_2", count=2)) == 2
    assert _lost_count(lost("ingest.small_parts_skipped", count=12)) == 1


@pytest.mark.parametrize("code", ["perceive.orphaned", "perceive.mended"])
def test_a_bundle_of_summarised_losses_announces_the_same_count_everywhere(
    qt_app: QApplication, code: str
) -> None:
    """Zwei Kernbefunde über 49 Details müssen dieselbe Menge zeigen und vorlesen."""
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.labels import value_line
    from app.ui.panels import ReportPanel

    findings = tuple(
        Finding(
            code=code,
            severity="info",
            message="Formdetails wurden zusammengefasst.",
            object_id=body,
            op_id=4,
            values={"count": amount, "feature": "face_1, face_2"},
        )
        for body, amount in (("obj_1", 28), ("obj_2", 21))
    )
    panel = ReportPanel()
    try:
        panel.show_result(EvaluationResult(scene=Scene(report=Report(findings=findings))))

        assert panel.list.count() == 1
        item = panel.list.item(0)
        assert item.text().startswith("(49) ")
        assert value_line("count", 49) in item.toolTip()
        assert value_line("count", 49) in item.data(Qt.ItemDataRole.AccessibleDescriptionRole)
        stored: Finding = item.data(Qt.ItemDataRole.UserRole)
        assert stored.values["count"] == 49
        assert f"2 × {tr('Hinweis')}" in panel.summary.text()
    finally:
        panel.deleteLater()


def test_the_defect_legend_paints_all_right_in_the_body_colour() -> None:
    """Bedienweg B3: „in Ordnung" trägt die Körperfarbe, nicht den dunkelsten Rampenton.

    Sonst stand das ganze Modell violett da, und ein einzelnes Fehlerdreieck
    ging darin unter. Die Stufen darüber behalten ihre Farben — dieselbe
    Tabelle, aus der die Ansicht färbt (``palette.category_colours``).
    """
    from app.ui.analysis_bar import _legend_entries
    from app.ui.palette import category_colours

    levels = tuple(str(level) for level in maps.DEFECT_LEVELS)
    defects = maps.AnalysisMap(
        kind="defects",
        title="Netzfehler",
        values=(0.0, 3.0),
        unit="",
        low=0.0,
        high=4.0,
        categories=levels,
    )
    entries = _legend_entries(defects, None, "#abcdef")
    assert entries[0] == (levels[0], "#abcdef")
    assert [colour for _label, colour in entries[1:]] == list(category_colours(len(levels))[1:])

    features = dataclasses.replace(defects, kind="features")
    plain = _legend_entries(features, None, "#abcdef")
    assert plain[0][1] != "#abcdef", "nur Karten mit „in Ordnung“ zuerst tragen die Körperfarbe"


def test_the_viewport_paints_the_defect_levels_from_the_legend_table(qt_app: QApplication) -> None:
    """Bild und Legende lesen dieselbe Tabelle; die erste Stufe ist der Körper (B3)."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.palette import category_colours
    from app.ui.viewport import Viewport

    body = MeshData(trimesh.creation.box(extents=(20.0, 20.0, 10.0)))
    result = EvaluationResult(
        scene=Scene(objects={"obj_1": SceneObject(id="obj_1", name="Halter", mesh=body)})
    )
    viewport = Viewport()
    renderer = RecordingRenderer()
    viewport.renderer = renderer
    viewport.show_scene(result)
    levels = tuple(str(level) for level in maps.DEFECT_LEVELS)
    values = [0.0] * body.triangle_count
    values[0] = 3.0
    defects = maps.AnalysisMap(
        kind="defects",
        title="Netzfehler",
        values=tuple(values),
        unit="",
        low=0.0,
        high=4.0,
        categories=levels,
    )

    viewport.set_analysis_map(defects, "obj_1")

    drawn = [entry for kind, entry in renderer.drawn if entry.get("cell_colours") is not None]
    assert drawn, renderer.names()
    colours = drawn[-1]["cell_colours"]
    assert colours.categorical
    assert tuple(colours.colormap) == category_colours(len(levels), viewport.body_colour())


def test_an_incomplete_defect_search_says_so_once(window: MainWindow) -> None:
    """Die unvollständige Suche steht einmal da, nicht noch als Rohzahl (KUNDE-15).

    Am Laptopständer stand hinter „Die Suche nach Überschneidungen ist
    unvollständig …“ noch „33140 × nicht bestimmbar (Überschneidungen nicht
    vollständig geprüft)“ — dieselbe Aussage als Zahl ohne Handlung. Die Zahl
    steht jetzt im Tooltip.
    """
    import math

    result = window.session.last_result
    assert result is not None
    object_id = next(iter(result.scene.objects))
    body = result.scene.objects[object_id].mesh
    open_search = maps.AnalysisMap(
        kind="defects",
        title="Netzfehler",
        values=(math.nan,) * (body.triangle_count - 1) + (3.0,),
        unit="",
        low=0.0,
        high=4.0,
        categories=tuple(str(level) for level in maps.DEFECT_LEVELS),
        note="Die Suche nach Überschneidungen ist unvollständig.",
        unknown_note="Überschneidungen nicht vollständig geprüft",
    )
    window._show_map(open_search, object_id)
    note = window.analysis_bar.legend.note
    assert tr("nicht bestimmbar") not in note.text()
    assert tr("nicht bestimmbar") in note.toolTip()


def test_the_defect_map_needs_no_choice_with_one_body(window: MainWindow) -> None:
    """Mit einem Körper wählt die Karte ihn selbst (KUNDE-15).

    „Wählen Sie zuerst ein Objekt im Objektbaum“ stand am Laptopständer über
    einer Szene mit genau einem Teil.
    """
    result = window.session.last_result
    assert result is not None and len(result.scene.objects) == 1
    window.object_tree.select_object(None)
    window._on_map_changed("defects")
    assert window.object_tree.selected() == next(iter(result.scene.objects))
    asked = tr("Wählen Sie zuerst ein Objekt im Objektbaum.")
    assert asked not in window.analysis_bar.legend.note.text()


def test_the_defect_map_offers_the_repair_and_says_when_there_is_nothing(
    window: MainWindow,
) -> None:
    """Bedienweg B1: Von der Netzfehlerkarte führt ein Knopf zur Reparatur.

    Ohne Fehler steht der Satz der Karte und kein Knopf. Nach einem Einlesen,
    das schon geschlossen hat, hilft ein Reparieren nur an Überschneidungen —
    an einem Loch, das die Importreparatur offen ließ, stünde ein Knopf ins
    Leere. An einer Überschneidung heißt der Knopf wie die Operation, und ein
    Klick legt genau einen Reparaturschritt am Körper der Karte an; danach
    kommt er nicht wieder (ein Ring).
    """
    result = window.session.last_result
    assert result is not None
    object_id = next(iter(result.scene.objects))
    body = result.scene.objects[object_id].mesh
    levels = tuple(str(level) for level in maps.DEFECT_LEVELS)
    clean = maps.AnalysisMap(
        kind="defects",
        title="Netzfehler",
        values=(0.0,) * body.triangle_count,
        unit="",
        low=0.0,
        high=4.0,
        categories=levels,
        note="Keine Netzfehler gefunden.",
    )

    window._show_map(clean, object_id)
    assert window.analysis_bar.legend.action is None
    assert "Keine Netzfehler gefunden." in window.analysis_bar.legend.note.text()

    hole = dataclasses.replace(clean, values=(1.0,) + (0.0,) * (body.triangle_count - 1), note=None)
    window._show_map(hole, object_id)
    assert window.analysis_bar.legend.action is None, "das Einlesen hat schon geschlossen"

    crossing = dataclasses.replace(
        clean, values=(3.0,) + (0.0,) * (body.triangle_count - 1), note=None
    )
    window._show_map(crossing, object_id)
    button = window.analysis_bar.legend.action
    assert button is not None and button.text() == tr("Reparieren")
    steps = len(window.session.project.document.ops)

    button.click()
    window.session.wait_for_idle()

    ops = window.session.project.document.ops
    assert len(ops) == steps + 1
    assert ops[-1].op == "repair" and ops[-1].inputs == (object_id,)
    repaired = ops[-1].outputs[0]
    window._show_map(crossing, repaired)
    assert window.analysis_bar.legend.action is None, "gleich nach dem Reparieren kein Ring"


def test_the_repair_offer_outlives_a_change_of_the_display_unit() -> None:
    """Ein Neubau der Legende ohne neue Karte bietet *Reparieren* wieder an.

    ``MapLegend.show_map`` baut die Felder neu und nimmt den Knopf mit. Der
    Einheitenwechsel baut die Legende über ``_refresh_map_units`` neu, und
    dort fehlte der Ausweg: An derselben Netzfehlerkarte war *Reparieren*
    nach einem Wechsel auf Zoll verschwunden. Stellvertreter statt Fenster:
    Gefragt ist, ob beide Wege denselben Ausweg anbieten.
    """
    offered: list[tuple[Any, str]] = []
    legends: list[tuple[Any, ...]] = []
    viewport = SimpleNamespace(analysis_map=None, body_colour=lambda: "#b0b4ba")
    viewport.set_analysis_map = lambda analysis, _object: setattr(
        viewport, "analysis_map", analysis
    )
    viewport.finding_mark = lambda: None
    view = SimpleNamespace(
        viewport=viewport,
        analysis_bar=SimpleNamespace(show_legend=lambda *args: legends.append(args)),
        _feature_names=dict,
        _offer_repair_on_the_map=lambda analysis, object_id: offered.append((analysis, object_id)),
    )
    view._show_map_legend = lambda analysis, object_id: MainWindow._show_map_legend(
        view,  # type: ignore[arg-type]
        analysis,
        object_id,
    )
    defects = maps.AnalysisMap(
        kind="defects",
        title="Netzfehler",
        values=(3.0, 0.0),
        unit="",
        low=0.0,
        high=4.0,
        categories=tuple(str(level) for level in maps.DEFECT_LEVELS),
    )

    MainWindow._show_map(view, defects, "obj_1")  # type: ignore[arg-type]
    assert offered == [(defects, "obj_1")]

    MainWindow._refresh_map_units(view)  # type: ignore[arg-type]
    assert len(legends) == 2, "die Legende wurde nicht neu gebaut"
    assert offered == [(defects, "obj_1"), (defects, "obj_1")], "der Knopf ging mit der Einheit"


def test_the_chosen_map_comes_back_after_a_change(window: MainWindow) -> None:
    """Nach einer Änderung steht die gewählte Karte wieder da (Durchsicht 0.5.1).

    Jede neue Geometrie räumt die Karte ab, und die Auswahl, die sie neu
    anstoßen würde, kam noch während der Rechnung. Danach stand der Wähler auf
    „Netzfehler“, und Bild und Legende blieben leer — auch nach *Reparieren* aus
    der Legende selbst.
    """
    from app.core.scene import OperationDraft

    select_plate(window)
    QApplication.processEvents()
    selector = window.analysis_bar.selector
    selector.setCurrentIndex(selector.findData("defects"))
    selector.activated.emit(selector.currentIndex())
    wait_for_map(window)
    assert window.viewport.analysis_map is not None, "ohne Karte prüft dieser Test nichts"
    object_id = window.object_tree.selected()
    window.session.apply("Reparieren", [OperationDraft(op="repair", inputs=(object_id,))])
    assert window.session.wait_for_idle()
    QApplication.processEvents()
    wait_for_map(window)
    assert window.analysis_bar.chosen() == "defects"
    assert window.viewport.analysis_map is not None, "die gewählte Karte kam nicht wieder"


def test_a_part_with_only_notes_is_called_ready_to_print(qt_app: QApplication) -> None:
    """„Druckbereit · 1 × Hinweis“ statt einer Zählung neben Hinweisen (KUNDE-06).

    Der Hinweis zu den Startwerten des Materials steht bei jeder frischen
    Installation an jedem Teil; mit ihm stand der Satz praktisch nie da, und die
    Zeile des Hinweises war vorgewählt — in der Auswahlfarbe, mit orangem Knopf,
    wie eine Warnung. Ein Hinweis am Körper bleibt vorwählbar; eine Warnung
    nimmt das Urteil weg.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene, SceneObject
    from app.ui.panels import ReportPanel

    body = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 10.0)))
    objects = {"obj_1": SceneObject(id="obj_1", name="Kasten", mesh=body)}
    material = Finding(
        code="settings.uncalibrated_material",
        severity="info",
        message="Die Toleranzen dieses Materials sind Startwerte.",
        suggestions=(Action("calibrate_material", "Material kalibrieren"),),
    )
    from PySide6.QtWidgets import QWidget

    class Host(QWidget):
        """Ein Fenster mit dem Handler, den die Vorwahl sucht."""

        def error_handlers(self) -> dict[str, Any]:
            return {"calibrate_material": lambda _error: None, "place_on_bed": lambda _e: None}

    host = Host()
    panel = ReportPanel(host)
    try:
        panel.show_result(
            EvaluationResult(scene=Scene(objects=objects, report=Report(findings=(material,))))
        )
        assert panel.summary.text().startswith(tr("Druckbereit"))
        assert f"1 × {tr('Hinweis')}" in panel.summary.text()
        assert not panel.list.selectedItems(), "ein Hinweis zur Einrichtung ist nicht vorgewählt"

        warning = Finding(
            code="arrange.out_of_build_volume",
            severity="warning",
            message="Ein Objekt steht über den Bauraum hinaus.",
            object_id="obj_1",
        )
        panel.show_result(
            EvaluationResult(
                scene=Scene(objects=objects, report=Report(findings=(warning, material)))
            )
        )
        assert not panel.summary.text().startswith(tr("Druckbereit"))
        assert f"1 × {tr('Warnung')}" in panel.summary.text()

        # Gegenprobe: Ein Hinweis **am Körper** mit Handlung wird vorgewählt.
        below = Finding(
            code="arrange.below_bed",
            severity="info",
            message="Ein Objekt steckt unter dem Druckbett.",
            object_id="obj_1",
            suggestions=(Action("place_on_bed", "Auf das Bett setzen"),),
        )
        panel.list.clearSelection()
        panel.show_result(
            EvaluationResult(
                scene=Scene(objects=objects, report=Report(findings=(material, below)))
            )
        )
        chosen = panel.list.selectedItems()
        assert chosen and chosen[0].data(Qt.ItemDataRole.UserRole).code == "arrange.below_bed"
    finally:
        panel.deleteLater()
        host.deleteLater()
