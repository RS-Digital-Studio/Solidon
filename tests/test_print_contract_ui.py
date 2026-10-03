"""Sichtbare Grundlage, Einzelheiten und Rückwege des Prüfberichts (RM-090)."""

from contextlib import suppress

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.core.scene import EvaluationResult
from app.core.types import Finding, Report, Scene
from app.ui.panels import ReportPanel
from tests.helpers import make_object


@pytest.mark.parametrize(
    "code, source, location",
    [
        ("mesh.open", "internal", (0.0, 0.0, 1.0)),
        ("wall.thin", "internal", (1.0, 0.0, 1.0)),
        ("overhang", "internal", None),
        ("profiles.missing", "internal", None),
        ("slice.island", "internal", (1.0, 1.0, 2.0)),
        ("gcode.time", "gcode", None),
    ],
)
def test_finding_details_are_visible_by_keyboard_and_clear_with_the_result(
    qt_app, code, source, location
):
    finding = Finding(
        code,
        "warning",
        "Prüfbefund",
        object_id="a",
        source=source,
        location=location,
        values={"value": 1.2, "unit": "mm"},
    )
    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(Scene(objects={"a": make_object("a")}, report=Report((finding,))))
        )
        panel.list.setCurrentRow(0)
        assert panel.finding_context.text()
        assert (
            "aus G-Code" if source == "gcode" else "intern geschätzt"
        ) in panel.finding_context.text()
        QTest.keyClick(panel.finding_details_toggle, Qt.Key.Key_Space)
        assert not panel.finding_details.isHidden()
        assert (
            "1,20" in panel.finding_details.toPlainText()
            or "1.2" in panel.finding_details.toPlainText()
        )
        selected = []
        panel.findingActivated.connect(selected.append)
        panel.finding_place.click()
        assert selected == [finding]
        panel.show_result(None)
        assert panel.finding_context.isHidden()
        assert panel.finding_details.isHidden()
        assert not panel.finding_details.toPlainText()
    finally:
        panel.close()
        panel.deleteLater()


def test_empty_findings_do_not_claim_print_readiness(qt_app):
    panel = ReportPanel()
    try:
        panel.show_result(EvaluationResult(Scene(objects={"a": make_object("a")})))
        assert "Bewertung unvollständig" in panel.summary.text()
        assert "druckbereit" not in panel.summary.text().casefold()
        panel.set_review_context("Geometrieprüfung: ganze Szene", ())
        assert "Bereit zur Übergabe" in panel.summary.text()
        panel.add_findings([Finding("problem", "error", "Schwerer Befund")])
        panel.set_review_context("Geometrieprüfung: ganze Szene", ("Zielprofil fehlt",))
        assert "Übergabe nicht empfohlen" in panel.summary.text()
        assert "Zielprofil fehlt" in panel.review_scope.text()
        assert not panel.to_slicer.isHidden(), "trotz Risiko bleibt die Vorbereitung erreichbar"
    finally:
        panel.close()
        panel.deleteLater()


def test_review_scope_keeps_a_long_list_scrollable_and_deduplicates_states(qt_app):
    from app.ui.style import TARGET_SIZE

    panel = ReportPanel()
    try:
        rows = [f"Körper {index}: läuft" for index in range(30)]
        panel.set_review_context("\n".join(rows), tuple(rows))
        panel.resize(360, 600)
        panel.show()
        panel.review_toggle.click()
        qt_app.processEvents()
        assert panel.review_scope.text().splitlines() == rows
        assert panel.review_scroll.height() <= 4 * TARGET_SIZE
        assert panel.review_scroll.verticalScrollBar().maximum() > 0
        assert panel.list.height() >= TARGET_SIZE
    finally:
        panel.close()
        panel.deleteLater()


def test_empty_report_stays_compact_beside_a_taller_hidden_tab(qt_app):
    from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

    from app.ui.overlay import natural_height
    from app.ui.style import TARGET_SIZE

    tabs = QTabWidget()
    panel = ReportPanel()
    other = QWidget()
    layout = QVBoxLayout(other)
    label = QLabel("Großer verborgener Reiter")
    label.setMinimumHeight(700)
    layout.addWidget(label)
    tabs.addTab(panel, "Bericht")
    tabs.addTab(other, "Andere Seite")
    try:
        panel.show_result(EvaluationResult(Scene(objects={"a": make_object("a")})))
        panel.set_review_context("\n".join(f"Körper {i}: läuft" for i in range(30)), ())
        tabs.resize(360, 850)
        tabs.show()
        qt_app.processEvents()
        collapsed = natural_height(tabs)
        assert collapsed < 400, "ein verborgener Reiter bestimmt nicht die Kartenhöhe"
        assert panel.summary.height() <= panel.summary.heightForWidth(panel.summary.width()) + 2
        panel.review_toggle.click()
        qt_app.processEvents()
        assert natural_height(tabs) <= collapsed + 4 * TARGET_SIZE + 20
        panel.add_findings([Finding(f"note.{i}", "info", f"Befund {i}") for i in range(30)])
        qt_app.processEvents()
        assert panel.list.height() > panel.review_scroll.height()
    finally:
        tabs.close()
        tabs.deleteLater()


@pytest.mark.parametrize("code", ["repair.holes_filled", "ingest.multiple_components"])
def test_batch_import_bundles_notes_and_keeps_every_body_and_original_detail(qt_app, code):
    from dataclasses import replace

    from app.core.scene import History, OperationDraft
    from app.core.scene.project import new_project
    from app.ui.panels import _BODIES_ROLE

    project = new_project()
    history = History(project.document)
    transaction = history.apply(
        "Piratenschiff",
        [OperationDraft(op="load", params={"source": f"source_{index}"}) for index in range(17)],
    )
    bodies = {
        f"obj_{index}": replace(make_object(f"obj_{index}"), name=f"obj_{index}")
        for index in transaction.ops
    }
    findings = tuple(
        Finding(
            code,
            "info",
            "Ein Loch wurde geschlossen.",
            object_id=f"obj_{index}",
            op_id=index,
            values={"holes": index},
        )
        for index in transaction.ops
    )
    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(Scene(objects=bodies, report=Report(findings))), project.document
        )
        assert panel.list.count() == 1
        item = panel.list.item(0)
        assert item.text().startswith("(17)")
        assert set(item.data(_BODIES_ROLE)) == set(bodies)
        assert item.data(Qt.ItemDataRole.UserRole).op_id is None
        panel.list.setCurrentRow(0)
        panel.finding_details_toggle.click()
        for identifier in bodies:
            assert identifier in panel.finding_details.toPlainText()
        selected = []
        panel.bundleActivated.connect(lambda _finding, identifiers: selected.append(identifiers))
        panel.finding_place.click()
        assert set(selected[0]) == set(bodies)
        assert panel._findings == list(findings), "Originalbefunde bleiben vollständig erhalten"
    finally:
        panel.deleteLater()


def test_real_evaluation_exposes_checks_and_invalidates_them_on_replacement(qt_app):
    from app.core.scene import OperationDraft
    from app.core.types import CheckState
    from app.ui.session import Session, _EvaluationWorker

    session = Session()
    try:
        session.project.document.printer = ""
        session.project.document.material = ""
        session.history.apply("Quader", [OperationDraft(op="create_box")])
        session.evaluate_async()
        assert session.wait_for_idle()
        states = session.last_result.check_states
        assert any(state.key == "evaluation" and state.state == "completed" for state in states)
        assert any(state.missing_basis for state in states), (
            "fehlende Originalprofile bleiben offen"
        )
        old = _EvaluationWorker(session)
        before = dict(session.check_states)
        session._on_check_state(CheckState("late", state="completed"), finished=old)
        assert session.check_states == before
        old.deleteLater()
    finally:
        session.release()


def test_layer_status_ignores_replaced_jobs_and_preserves_cancellation(qt_app):
    from types import SimpleNamespace

    from PySide6.QtCore import QObject

    from app.core.knowledge import print_settings, profiles
    from app.core.types import CheckState
    from app.ui.print_findings_flow import PrintFindingsFlow

    class Owner(QObject):
        def current(self, result):
            return result is self.result

    owner = Owner()
    owner.result = EvaluationResult(Scene(objects={"a": make_object("a")}))
    leash = SimpleNamespace(start=lambda worker: None, retire=lambda worker: None)
    flow = PrintFindingsFlow(owner, leash, owner.current)
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    flow.start(owner.result, profile, settings, fitted=False)
    old = flow.worker
    flow._checked(CheckState("slice.print_findings", "a", state="running"), owner.result, old)
    flow.cancel()
    assert flow.check_states["slice.print_findings", "a"].state == "cancelled"
    flow.start(owner.result, profile, settings, fitted=False)
    latest = flow.worker
    flow._checked(CheckState("slice.print_findings", "a", state="completed"), owner.result, old)
    assert not flow.check_states
    flow._checked(CheckState("slice.print_findings", "a", state="failed"), owner.result, latest)
    assert flow.check_states["slice.print_findings", "a"].state == "failed"
    flow.cancel()
    old.deleteLater()
    latest.deleteLater()


@pytest.mark.parametrize("stop", ["cancel", "failure", "crash"])
def test_slicer_receipt_names_only_written_plates_and_successful_opens(
    qt_app, monkeypatch, tmp_path, stop
):
    from pathlib import Path
    from types import SimpleNamespace

    from app.core.errors import UserError
    from app.core.knowledge import print_settings, profiles
    from app.ui import print_settings_dialog as module

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    bodies = (make_object("a", "Rumpf"), make_object("b", "Segel"))
    bodies[1].plate = 1
    job = module._PlateJob(
        bodies,
        (0, 1),
        tmp_path,
        "Schiff",
        module.handover.SlicerSetup(Path("PrusaSlicer.exe"), "prusa"),
        print_settings.resolve(profile),
        profile,
        {},
        with_settings=False,
    )
    worker = module._OpenInSlicerWorker(job)
    monkeypatch.setattr(module, "prepare_usage", lambda *args, **kwargs: ())
    monkeypatch.setattr(
        module,
        "_prepare_plate",
        lambda job, plate: SimpleNamespace(
            model=tmp_path / f"plate-{plate}.3mf",
            slots=(),
            findings=(Finding("export.loss", "warning", f"Verlust auf Platte {plate}"),),
        ),
    )
    opened = []

    def open_file(path, setup):
        if opened and stop == "crash":
            raise RuntimeError("Unerwarteter Prozessfehler")
        if opened and stop == "failure":
            raise UserError("Testfehler")
        opened.append(path)
        if stop == "cancel":
            worker.cancel()

    monkeypatch.setattr(module.handover, "open_in_slicer", open_file)
    receipts = []
    worker.receipt.connect(receipts.append)
    if stop == "crash":
        with pytest.raises(RuntimeError, match="Prozessfehler"):
            worker.work()
    else:
        worker.work()
    assert len(receipts) == 1
    details = receipts[0].values["detail"]
    assert "erfolgreich geöffnete Dateien: 1" in details
    assert ("1 von 2 Körpern" if stop == "cancel" else "2 von 2 Körpern") in details
    assert "Rumpf" in details
    assert ("Segel" in details) is (stop != "cancel")
    assert ("plate-1.3mf" in details) is (stop != "cancel")
    assert "Verlust auf Platte 0" in details
    assert ("Verlust auf Platte 1" in details) is (stop != "cancel")
    assert "noch nicht erzeugt" not in details, "ein Teilfehler darf keine Erfolgsquittung tragen"
    worker.deleteLater()


def test_material_preview_explains_its_target_without_a_geometry_change(qt_app, tmp_path):
    from app.core.scene import OperationDraft
    from app.core.scene.project import load
    from app.ui.session import Session

    session = Session()
    try:
        session.apply("Platte", [OperationDraft(op="create_box", params={"name": "Platte"})])
        assert session.wait_for_idle()
        body_id = next(iter(session.last_result.scene.objects))
        before = len(session.history.transactions)
        draft = OperationDraft(op="set_material", inputs=(body_id,), params={"material": "petg"})
        scene, difference, reason = session._preview_outcome([draft])
        assert scene.objects[body_id].material == "petg"
        assert reason == "Dieser Körper wird in einem eigenen Material gerechnet."
        assert difference is not None and not difference.changed
        assert "Platte" in difference.explanation
        assert "Material „Platte“:" in difference.explanation and "PETG" in difference.explanation
        assert "Außenmaß „Platte“:" in difference.explanation
        assert "noch nicht vollständig geprüft" in difference.explanation
        assert len(session.history.transactions) == before
        session.apply("Material festlegen", [draft])
        assert session.wait_for_idle()
        assert session.last_result.scene.objects[body_id].material == "petg"
        assert len(session.history.transactions) == before + 1
        saved = session.save_project(tmp_path / "material.p3d")
        restored = load(saved)
        assert restored.document.ops[-1].params["material"] == "petg"
        session.undo()
        assert session.wait_for_idle()
        assert session.last_result.scene.objects[body_id].material != "petg"
    finally:
        session.release()


def test_full_preview_checks_both_actual_states_and_keeps_material_change(qt_app):
    from app.core.scene import OperationDraft
    from app.ui.session import Session

    session = Session()
    try:
        session.apply("Platte", [OperationDraft(op="create_box", params={"name": "Platte"})])
        assert session.wait_for_idle()
        key = next(iter(session.last_result.scene.objects))
        events = []
        session.preview_async(
            lambda difference: events.append(("checked", difference)),
            [OperationDraft(op="set_material", inputs=(key,), params={"material": "petg"})],
            pictured=lambda difference: events.append(("picture", difference)),
        )
        assert session.wait_for_idle(30_000)
        assert [kind for kind, _ in events] == ["picture", "checked"]
        final = events[-1][1]
        assert final is not None
        assert "genaue Auswertung und Schichtanalyse" in final.explanation
        assert "Material „Platte“:" in final.explanation
        assert "Vorher:" in final.explanation and "Nachher:" in final.explanation
        assert session.last_result.scene.objects[key].material != "petg"
    finally:
        session.release()


@pytest.mark.parametrize("ending", ["cancel", "newer", "failure", "complete"])
def test_picture_does_not_approve_a_pending_print_review(qt_app, monkeypatch, ending):
    from app.core.geom.difference import SceneDifference
    from app.core.scene import OperationDraft
    from app.ui.main_window import _PreviewOrder
    from tests.ui_helpers import shown_window

    windows = shown_window(qt_app)
    window = next(windows)
    try:
        window.session.evaluate_now()
        calls, shown, accepted = [], [], []
        monkeypatch.setattr(
            window.session,
            "preview_async",
            lambda then, drafts=None, **kw: calls.append((then, kw)),
        )
        monkeypatch.setattr(window, "_show_preview", lambda value, **kw: shown.append(value))
        order = _PreviewOrder(drafts=(OperationDraft(op="create_box"),))
        approval = window._set_preview_order(window.feature_panel, order)
        window._request_order_preview(approval)
        first, callbacks = calls[-1]
        picture = SceneDifference()
        callbacks["pictured"](picture)
        assert shown == [picture]
        assert approval.computing and approval.reviewing
        assert not approval.displayed and approval.difference is None
        assert not window._preview_can_apply(
            window.feature_panel, order, then=lambda: accepted.append(True)
        )
        assert not accepted
        if ending == "cancel":
            window._cancel_preview_run()
            assert approval.problem and not accepted
        elif ending == "newer":
            window._set_preview_order(
                window.feature_panel,
                _PreviewOrder(drafts=(OperationDraft(op="create_box", params={"width": 12.0}),)),
            )
            first(SceneDifference())
            assert not accepted
            assert window._preview_approval.difference is None
        elif ending == "failure":
            callbacks["failed"]("Prüfung unterbrochen")
            assert approval.problem and not accepted
        else:
            first(SceneDifference())
            assert accepted == [True]
    finally:
        with suppress(StopIteration):
            next(windows)


def test_consumed_body_id_is_not_appended_to_a_named_finding(qt_app):
    from app.ui.panels import _line_for

    finding = Finding(
        "union.bore_partial", "warning", "Quader verdeckt eine Bohrung.", object_id="obj_1"
    )
    assert _line_for(finding, {}) == str(finding.message)
    assert _line_for(finding, {"obj_1": "obj_1"}) == str(finding.message)
    assert _line_for(finding, {"obj_1": "Quader"}) == str(finding.message)
