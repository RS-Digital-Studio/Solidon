"""Ein Neuaufbau ohne Eingabe des Kunden verliert keinen wartenden Klick (Review 1, RCI-2, FD-192).

*Übernehmen* während einer Auswertung wird getragen und bindet danach seinen
Auftrag; der Klick wartet an dieser Freigabe auf das Bild. Was danach ohne
Eingabe des Kunden neu bindet — der Neuaufbau des Merkmalfensters, die Antwort
des Merkmalsarbeiters an großen Körpern samt neuer Maßgruppe —, ersetzte die
Freigabe still: kein Schritt, kein Satz (``MainWindow._set_preview_order``,
``rebuilt``). Und das Anzeigen einer Textur meldete ihre Werte als Änderung,
stellte die Uhr der Vorschau und zeigte *Abbrechen* (FD-192).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from app.core.registry import REGISTRY
from app.ui.main_window import MainWindow
from app.ui.session import Session
from tests.ui_helpers import MESHES
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


def _until(done: Callable[[], bool], seconds: float = 60.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not done():
        QApplication.processEvents()
        time.sleep(0.01)


def _pump(seconds: float) -> None:
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        QApplication.processEvents()
        time.sleep(0.01)


def _settle(window: MainWindow) -> None:
    """Auswertung, Vorschau und ein wartender Klick laufen durch; das Bild gilt als gezeigt."""
    for _ in range(4):
        assert window.session.wait_for_idle(60_000)
        QApplication.processEvents()
        approval = window._preview_approval
        if approval is not None and approval.difference is not None:
            window.viewport.differenceApplied.emit(approval.difference)
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()


def _hold(monkeypatch: pytest.MonkeyPatch) -> tuple[threading.Event, threading.Event]:
    """Auswertung und Vorschau warten, bis ihr Ereignis gesetzt ist."""
    from app.ui.session import _PreviewWorker

    evaluated, previewed = threading.Event(), threading.Event()
    evaluate = Session.run_evaluation
    monkeypatch.setattr(
        Session,
        "run_evaluation",
        lambda self, *a, **k: (evaluated.wait(15), evaluate(self, *a, **k))[1],
    )
    work = _PreviewWorker.work
    monkeypatch.setattr(_PreviewWorker, "work", lambda self: (previewed.wait(15), work(self))[1])
    return evaluated, previewed


def _click_is_bound(window: MainWindow) -> Any:
    """Bis der getragene Klick an seiner Freigabe auf das Bild wartet."""
    _until(
        lambda: (
            window._preview_approval is not None
            and window._preview_approval.pending_click is not None
        )
    )
    approval = window._preview_approval
    assert approval is not None and approval.pending_click is not None, "die Lage: er wartet"
    return approval


def _textured(window: MainWindow) -> tuple[str, Any, Any, int]:
    """Die Platte mit einer Rippentextur auf der Oberseite, das Muster gewählt."""
    from app.core.scene.placement import top_face

    window.open_path(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(60_000)
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    object_id = window.object_tree.selected()
    assert object_id is not None
    result = window.session.last_result
    face = top_face(result.scene.objects[object_id].features)
    assert face is not None
    window._on_feature_picked(face.id)
    window.run_operation(
        REGISTRY.get("apply_texture"),
        {"coverage": "whole_face", "pattern": "rib", "pitch": 5.0},
    )
    assert window.session.wait_for_idle()
    assert window._op_dialog is not None
    window._op_dialog.accept()
    assert window.session.wait_for_idle()
    operation = window.session.project.document.ops[-1]
    body = window.session.last_result.scene.objects[object_id]
    created = next(
        feature
        for feature in body.features.values()
        if feature.created_by == operation.id and feature.kind == "pattern"
    )
    window._on_feature_picked(created.id)
    return object_id, created, operation, len(window.session.project.document.ops)


def test_showing_a_texture_neither_starts_a_preview_nor_offers_cancel(window: MainWindow) -> None:
    """FD-192: Die Werte des Schritts sind keine Änderung — keine Uhr, kein *Abbrechen*."""
    _textured(window)
    assert window._preview_approval is not None, "gebunden ist der Auftrag trotzdem"
    assert window._feature_pending is None
    assert not window._feature_preview.isActive(), "die Anzeige stellt keine Uhr"
    assert not window.feature_panel._cancel_offered, "kein *Abbrechen* ohne Änderung"


def test_a_rebuild_while_the_click_waits_for_its_preview_keeps_the_click(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RCI-2 an der Textur: Ein zweiter Neuaufbau des Merkmalfensters bindet neu."""
    from app.ui.op_dialog import ValueField

    object_id, created, operation, count = _textured(window)
    panel = window.feature_panel
    numeric = {
        field._entry.name: field for row in panel._built for field in row.findChildren(ValueField)
    }
    monkeypatch.setattr(window, "_show_preview", lambda _difference, **_kwargs: None)
    numeric["depth"].spin.setValue(0.9)
    window._feature_preview.stop()
    window._preview_feature_change()
    assert window.session.wait_for_idle(60_000)
    evaluated, previewed = _hold(monkeypatch)
    try:
        window.session.evaluate_async()
        assert window.session.busy, "die Lage: die Szene rechnet denselben Stand nach"
        panel._apply.click()
        assert window._click_after_evaluation is not None, "der Klick wartet"
        evaluated.set()
        _click_is_bound(window)
        # Wie die Auswahl, die der Baum nach einem Ergebnis wiederherstellt.
        window.object_tree.select_feature(object_id, created.id)
        _pump(0.5)
        previewed.set()
        _settle(window)
    finally:
        evaluated.set()
        previewed.set()

    assert len(window.session.project.document.ops) == count, "kein neuer Schritt"
    updated = window.session.project.document.ops[-1]
    assert updated.id == operation.id
    assert updated.params["depth"] == pytest.approx(0.9), "der Schritt ist geändert"


def test_a_late_feature_answer_on_a_large_body_keeps_the_waiting_click(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RCI-2 an der Maßgruppe: Die Antwort des Merkmalsarbeiters kommt nach dem Klick.

    Ab ``ANSWERS_IN_WORKER_FROM`` Dreiecken holt ein Arbeiter die Antworten zu
    den Merkmalen; seine Antwort baut das Merkmalfenster und die Maßgruppe neu
    auf. Die Schwelle steht hier auf 1, die Antwort wartet, bis der Klick
    gebunden ist.
    """
    from app.ui import main_window as module
    from app.ui.labels import LengthSpin
    from tests.render_fakes import RecordingRenderer

    monkeypatch.setattr(window.viewport, "is_difference_applied", lambda _difference: True)
    monkeypatch.setattr(window.viewport, "is_scene_applied", lambda _result: True)
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.open_path(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(60_000)
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    window.object_tree.select_feature(object_id, hole)
    window.feature_panel._in_view.click()
    assert window.session.wait_for_idle(30_000)
    for _ in range(40):
        QApplication.processEvents()
    flow = window._quiet_placement
    assert flow is not None and flow.active and flow._measure_group is not None
    diameter = next(
        field
        for field in flow._measure_group.findChildren(LengthSpin)
        if "Bohrung ändern" in field.accessibleName()
        and field.accessibleName().endswith("Durchmesser")
    )
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    QTest.keyClick(diameter.lineEdit(), Qt.Key.Key_End)
    wanted = diameter.value_mm() + 0.5
    diameter.set_value_mm(wanted)
    _settle(window)
    before = len(window.session.project.document.ops)

    monkeypatch.setattr(module, "ANSWERS_IN_WORKER_FROM", 1)
    answered = threading.Event()
    answer = module._FeatureAnswersWorker.work
    monkeypatch.setattr(
        module._FeatureAnswersWorker, "work", lambda self: (answered.wait(15), answer(self))[1]
    )
    evaluated, previewed = _hold(monkeypatch)
    try:
        window.session.evaluate_async()
        assert window.session.busy
        window._quiet_placement._measure_accept.click()
        assert window._click_after_evaluation is not None, "der Klick wartet"
        evaluated.set()
        _click_is_bound(window)
        answered.set()
        _pump(1.0)
        previewed.set()
        _settle(window)
        _pump(0.5)
        _settle(window)
    finally:
        evaluated.set()
        answered.set()
        previewed.set()

    ops = window.session.project.document.ops
    assert len(ops) == before + 1, ("ein neuer Schritt", window.status_message.text())
    assert ops[-1].op == "resize_hole"
    assert ops[-1].params["diameter"] == pytest.approx(wanted)
