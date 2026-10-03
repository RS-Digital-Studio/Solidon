"""Eine Vereinigung meldet ihre gemessenen Bohrungsfolgen im wirklichen Prüfbericht."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.registry import REGISTRY
from app.core.scene.history import OperationDraft
from app.ui.dialogs import handlers_of
from app.ui.main_window import MainWindow
from app.ui.panels import handled_actions
from tests.render_fakes import RecordingRenderer
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


@pytest.mark.parametrize(
    ("kind", "width", "height", "x", "z"),
    [
        ("partial", 10, 10, 5, 0),
        ("filled", 12, 10, 0, 0),
        ("blind", 12, 2, 0, 10),
        ("gap", 12, 2, 0, 10.1),
    ],
)
def test_union_menu_report_and_undo_keep_the_actual_bore_result(
    window: MainWindow,
    qt_app: QApplication,
    kind: str,
    width: float,
    height: float,
    x: float,
    z: float,
) -> None:
    """Teilweise, vollständig, einseitig und berührungsfrei bleiben unterscheidbar."""
    window.viewport.renderer = RecordingRenderer()
    assert window.start_empty()
    assert window.session.wait_for_idle(30_000)
    assert window.session.apply(
        "Bohrplatte und Steg",
        [
            OperationDraft("create_box", params={"width": 30, "depth": 30, "height": 10}),
            OperationDraft(
                "drill_hole",
                inputs=("obj_1",),
                params={"diameter": 9, "z": 10, "compensate": False},
                seed=7,
            ),
            OperationDraft(
                "create_box",
                params={"width": width, "depth": 12, "height": height, "x": x, "z": z},
            ),
        ],
    )
    assert window.session.wait_for_idle(30_000)
    qt_app.processEvents()
    before = deepcopy(window.session.project.document)
    window.object_tree.select_objects(("obj_1", "obj_2"))
    window.run_operation(REGISTRY.get("union_objects"))
    assert window._op_dialog is None
    assert window.session.wait_for_idle(60_000)
    qt_app.processEvents()
    assert window.session.last_result.complete
    document = window.session.project.document
    assert len(document.transactions) == len(before.transactions) + 1
    findings = [
        finding for finding in window.report._findings if finding.code.startswith("union.bore_")
    ]
    assert [finding.code for finding in findings] == (
        [] if kind == "gap" else [f"union.bore_{kind}"]
    )
    if findings:
        finding = findings[0]
        item = next(
            window.report.list.item(row)
            for row in range(window.report.list.count())
            if window.report.list.item(row).data(Qt.ItemDataRole.UserRole) is finding
        )
        assert str(finding.message) in item.text()
        assert finding.location is not None and not finding.feature_ids
        actions = handled_actions(
            finding,
            document,
            handlers_of(window.report),
            live_objects=window.session.last_result.scene.objects,
        )
        assert {"change_selection", "show_location"} <= {action.id for action in actions}
        unchanged = deepcopy(document)
        window.report._on_activated(item)
        assert document == unchanged
    after = deepcopy(document)
    window.session.undo()
    assert window.session.wait_for_idle(30_000)
    qt_app.processEvents()
    restored = window.session.project.document
    assert restored == replace(
        before, highest_transaction=restored.highest_transaction, highest_op=restored.highest_op
    )
    assert not [f for f in window.report._findings if f.code.startswith("union.bore_")]
    window.session.redo()
    assert window.session.wait_for_idle(30_000)
    qt_app.processEvents()
    assert window.session.project.document == after
    assert [f.code for f in window.report._findings if f.code.startswith("union.bore_")] == (
        [] if kind == "gap" else [f"union.bore_{kind}"]
    )
